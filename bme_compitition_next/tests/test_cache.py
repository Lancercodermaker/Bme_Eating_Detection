import numpy as np
import pytest

from eating_event.cache import build_cache_key, load_candidate_table, save_candidate_table
from eating_event.candidates import CandidateTable
from eating_event.data.labels import WindowLabel, WindowLabelResult
from eating_event.data.windows import WindowRecord, WindowSpec


def _table() -> CandidateTable:
    windows = (
        WindowRecord(
            window=WindowSpec(1000, 2500),
            coverage=0.9,
            longest_invalid_run=1,
            label_result=WindowLabelResult(WindowLabel.POSITIVE, 0.5, 0),
        ),
    )
    return CandidateTable(
        features=np.asarray([[1.0, 2.0]], dtype=np.float64),
        feature_names=("f1", "f2"),
        labels=np.asarray([1], dtype=np.int64),
        participant_ids=np.asarray(["p1"], dtype=object),
        windows=windows,
    )


def test_cache_key_changes_with_feature_schema_version():
    first = build_cache_key("abc", 15.0, 7.5, "imu_stats_v1", "labels_v1")
    second = build_cache_key("abc", 15.0, 7.5, "imu_stats_v2", "labels_v1")
    assert first != second


def test_candidate_cache_round_trip_preserves_contract(tmp_path):
    table = _table()
    metadata = {
        "source_fingerprint": "abc",
        "window_seconds": 15.0,
        "step_seconds": 7.5,
        "feature_schema_version": "imu_stats_v1",
        "label_schema_version": "labels_v1",
    }
    path = tmp_path / "candidate.npz"

    save_candidate_table(path, table, metadata=metadata)
    restored = load_candidate_table(path, expected_metadata=metadata)

    assert restored.features.dtype == np.float32
    assert restored.labels.dtype == np.int8
    np.testing.assert_array_equal(restored.labels, np.asarray([1], dtype=np.int8))
    np.testing.assert_array_equal(restored.windows[0].window, table.windows[0].window)
    assert restored.participant_ids.tolist() == ["p1"]


def test_candidate_cache_rejects_metadata_mismatch(tmp_path):
    metadata = {
        "source_fingerprint": "abc",
        "window_seconds": 15.0,
        "step_seconds": 7.5,
        "feature_schema_version": "imu_stats_v1",
        "label_schema_version": "labels_v1",
    }
    path = tmp_path / "candidate.npz"
    save_candidate_table(path, _table(), metadata=metadata)

    with pytest.raises(ValueError, match="metadata"):
        load_candidate_table(path, expected_metadata={**metadata, "step_seconds": 15.0})
