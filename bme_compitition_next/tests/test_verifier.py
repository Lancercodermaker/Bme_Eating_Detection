import numpy as np
import pytest

from eating_event.data.labels import WindowLabel, WindowLabelResult
from eating_event.data.windows import WindowRecord, WindowSpec
from eating_event.metrics import EventInterval
from eating_event.verifier import build_event_candidates, fit_event_verifier
from scripts.run_event_verifier import _event_coverage_recall, _long_false_positive_fraction


def _record(start: int, end: int) -> WindowRecord:
    return WindowRecord(
        window=WindowSpec(start, end),
        coverage=1.0,
        longest_invalid_run=0,
        label_result=WindowLabelResult(WindowLabel.NEGATIVE, 0.0, None),
    )


def test_event_candidates_cluster_window_scores_and_use_strict_iou_label() -> None:
    windows = [_record(0, 1000), _record(1000, 2000), _record(5000, 6000)]
    scores = np.array([0.8, 0.7, 0.9])

    candidates = build_event_candidates(
        windows,
        scores,
        candidate_threshold=0.5,
        fuse_gap_ms=500,
        truths=[EventInterval(0, 2000)],
    )

    assert len(candidates) == 2
    assert candidates[0].interval == EventInterval(0, 2000)
    assert candidates[0].label == 1
    assert candidates[1].label == 0
    assert candidates[0].features.shape == candidates[1].features.shape == (16,)


def test_event_verifier_returns_probability_scores() -> None:
    pytest.importorskip("sklearn")
    features = np.array([[0.1, 0.2, 0.0], [0.2, 0.1, 0.0], [0.9, 0.8, 1.0], [0.8, 0.9, 1.0]])
    labels = np.array([0, 0, 1, 1])

    verifier = fit_event_verifier(features, labels, random_state=7)
    scores = verifier.predict_scores(features)

    assert scores.shape == (4,)
    assert np.all((scores >= 0) & (scores <= 1))
    assert scores[2] > scores[0]


def test_long_false_positive_fraction_ignores_matched_long_events() -> None:
    truths = [EventInterval(0, 1_000)]
    predictions = [EventInterval(0, 1_000), EventInterval(10_000, 710_000)]

    assert _long_false_positive_fraction(predictions, truths, long_duration_ms=600_000) == 1.0


def test_event_coverage_recall_counts_truths_with_any_matching_candidate() -> None:
    truths = [EventInterval(0, 1_000), EventInterval(10_000, 11_000)]
    candidates = [EventInterval(0, 1_000), EventInterval(20_000, 21_000)]

    assert _event_coverage_recall(candidates, truths) == 0.5
