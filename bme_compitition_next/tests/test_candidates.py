import numpy as np
import pytest

from scripts.run_candidate_baseline import _select_records_for_run
from eating_event.candidates import (
    CandidateTable,
    build_candidate_table,
    eventize_windows,
    fit_candidate_model,
    participant_oof_candidate_scores,
    split_participants,
)
from eating_event.data.timebase import aggregate_timestamp_rows, regularize_series
from eating_event.data.windows import generate_dense_windows
from eating_event.features import extract_imu_features
from eating_event.metrics import EventInterval
from eating_event.data.manifest import RawFileRecord


def test_diagnostic_file_limit_is_bounded_for_smoke_runs(tmp_path) -> None:
    records = [
        RawFileRecord(f"p{index // 2}", tmp_path / f"{index}.txt", f"s{index}", 0, 1000)
        for index in range(4)
    ]

    selected = _select_records_for_run(
        records,
        max_files_per_participant=2,
        diagnostic_only=True,
    )

    assert len(selected) == 4
    assert {record.participant_id for record in selected} == {"p0", "p1"}
    assert all(sum(item.participant_id == record.participant_id for item in selected) <= 2 for record in selected)


def test_features_are_invariant_to_duplicate_packets_after_timebase_reconstruction() -> None:
    unique_timestamps = np.array([1000, 2000, 3000], dtype=np.int64)
    unique_values = np.array(
        [[1.0, 0.0, 0.0, 0.1, 0.0, 0.0], [2.0, 0.0, 0.0, 0.2, 0.0, 0.0], [3.0, 0.0, 0.0, 0.3, 0.0, 0.0]]
    )
    duplicated_timestamps = np.array([1000, 1000, 2000, 3000], dtype=np.int64)
    duplicated_values = np.vstack([unique_values[0], unique_values[0], unique_values[1:]])

    direct = regularize_series(
        aggregate_timestamp_rows(unique_timestamps, unique_values),
        grid_hz=1,
        max_gap_seconds=2.0,
    )
    reconstructed = regularize_series(
        aggregate_timestamp_rows(duplicated_timestamps, duplicated_values),
        grid_hz=1,
        max_gap_seconds=2.0,
    )

    direct_features = extract_imu_features(direct.values, direct.valid_mask)
    reconstructed_features = extract_imu_features(reconstructed.values, reconstructed.valid_mask)

    np.testing.assert_array_equal(direct_features.names, reconstructed_features.names)
    np.testing.assert_allclose(direct_features.values, reconstructed_features.values)


def test_imu_feature_schema_has_111_finite_values() -> None:
    values = np.ones((150, 6), dtype=np.float32)

    vector = extract_imu_features(values, np.ones(150, dtype=bool))

    assert len(vector.names) == 111
    assert vector.values.shape == (111,)
    assert np.isfinite(vector.values).all()


def test_candidate_table_keeps_ignore_labels_out_of_binary_training_rows() -> None:
    timestamps = np.arange(0, 20_000, 1000, dtype=np.int64)
    values = np.tile(np.arange(6, dtype=np.float64), (timestamps.size, 1))
    series = regularize_series(
        aggregate_timestamp_rows(timestamps + 1, values),
        grid_hz=1,
        max_gap_seconds=2.0,
    )
    windows = generate_dense_windows(
        series.timestamps_ms,
        series.valid_mask,
        grid_hz=1,
        window_seconds=4,
        step_seconds=2,
        min_coverage=0.8,
        max_gap_seconds=2.0,
        truths=[EventInterval(5001, 7001)],
        positive_overlap=0.5,
        negative_distance_ms=3000,
    )

    table = build_candidate_table(series, windows, participant_id="P1")

    assert table.features.shape[0] == len(windows)
    assert set(table.labels.tolist()).issubset({-1, 0, 1})
    assert table.participant_ids.tolist() == ["P1"] * len(windows)


def test_hist_gradient_boosting_candidate_model_returns_probabilities() -> None:
    pytest.importorskip("sklearn")
    features = np.array([[0.0, 0.0], [0.1, 0.0], [1.0, 1.0], [1.1, 0.9]])
    labels = np.array([0, 0, 1, 1])

    model = fit_candidate_model(features, labels, random_state=7)
    scores = model.predict_scores(features)

    assert scores.shape == (4,)
    assert np.all((scores >= 0) & (scores <= 1))
    assert scores[3] > scores[0]


def test_participant_oof_scores_are_disjoint_and_deterministic() -> None:
    pytest.importorskip("sklearn")
    tables_by_participant = {}
    for participant_index, participant in enumerate(("P1", "P2", "P3")):
        features = np.asarray(
            [[0.0, float(participant_index)], [0.1, float(participant_index)], [1.0, float(participant_index)], [1.1, float(participant_index)]],
            dtype=np.float64,
        )
        tables_by_participant[participant] = [
            CandidateTable(
                features=features,
                feature_names=("x", "participant_hint"),
                labels=np.asarray([0, 0, 1, 1], dtype=np.int8),
                participant_ids=np.full(4, participant, dtype=object),
                windows=tuple(),
            )
        ]

    scores_a, fallback_a = participant_oof_candidate_scores(tables_by_participant, random_state=7, n_folds=3)
    scores_b, fallback_b = participant_oof_candidate_scores(tables_by_participant, random_state=7, n_folds=3)

    assert fallback_a == fallback_b == tuple()
    for participant in tables_by_participant:
        assert len(scores_a[participant]) == 1
        np.testing.assert_allclose(scores_a[participant][0], scores_b[participant][0])
        assert scores_a[participant][0].shape == (4,)


def test_eventizer_merges_selected_windows_into_one_event() -> None:
    timestamps = np.arange(0, 8_000, 1000, dtype=np.int64)
    values = np.tile(np.arange(6, dtype=np.float64), (timestamps.size, 1))
    series = regularize_series(
        aggregate_timestamp_rows(timestamps + 1, values),
        grid_hz=1,
        max_gap_seconds=2.0,
    )
    windows = generate_dense_windows(
        series.timestamps_ms,
        series.valid_mask,
        grid_hz=1,
        window_seconds=2,
        step_seconds=1,
        min_coverage=0.8,
        max_gap_seconds=2.0,
    )

    events = eventize_windows(windows, np.ones(len(windows)), threshold=0.5, min_duration_ms=3000)

    assert events == [(1, 8001)]


def test_participant_split_is_deterministic_and_disjoint() -> None:
    participants = ["P3", "P1", "P2", "P4", "P5"]

    train_a, valid_a = split_participants(participants, valid_fraction=0.4, seed=7)
    train_b, valid_b = split_participants(participants, valid_fraction=0.4, seed=7)

    assert (train_a, valid_a) == (train_b, valid_b)
    assert set(train_a).isdisjoint(valid_a)
    assert sorted(train_a + valid_a) == sorted(set(participants))
