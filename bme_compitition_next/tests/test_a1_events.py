import numpy as np

from eating_event.a1.boundaries import build_support_components
from eating_event.a1.events import (
    build_candidates,
    decode_candidates,
    label_candidates,
)
from eating_event.a1.inputs import A1Window
from eating_event.a1.contracts import WindowIdentity
from eating_event.metrics import EventInterval


def w(row, start, end, coverage=1.0):
    return A1Window(
        identity=WindowIdentity("p", "r", "s", row),
        start_ms=start,
        end_ms=end,
        coverage=coverage,
        crosses_hard_gap=False,
        features=tuple(float(row + i) for i in range(111)),
        label=0,
        session_start_ms=0,
        session_end_ms=1000000,
    )


def test_relative_score_features_ignore_raw_reference_offset():
    windows = [w(0, 0, 15000), w(1, 7500, 22500)]
    first = build_candidates(windows, np.array([0.2, 0.4]), threshold_reference=0.1, fuse_gap_ms=300000)
    second = build_candidates(windows, np.array([0.7, 0.9]), threshold_reference=0.6, fuse_gap_ms=300000)
    np.testing.assert_allclose(first[0].features, second[0].features)


def test_candidate_generation_does_not_accept_truth_and_labeling_is_separate():
    windows = [w(0, 0, 15000), w(1, 7500, 22500)]
    candidates = build_candidates(windows, np.array([0.8, 0.9]), threshold_reference=0.5, fuse_gap_ms=300000)
    assert candidates[0].label is None
    labeled = label_candidates(candidates, [EventInterval(0, 20000)])
    assert labeled[0].label == 1


def test_short_candidates_are_filtered_before_decode_fusion():
    left = w(0, 0, 100000)
    right = w(1, 500000, 600000)
    candidates = build_candidates([left, right], np.array([0.9, 0.9]), threshold_reference=0.1, fuse_gap_ms=300000)
    predictions = decode_candidates(candidates, np.array([0.9, 0.9]), threshold=0.5, min_duration_ms=180000, decode_fuse_gap_ms=600000)
    assert predictions == []


def test_components_cannot_bridge_decode_fusion():
    windows = [w(0, 0, 200000), w(1, 500000, 700000)]
    candidates = build_candidates(windows, np.array([0.9, 0.9]), threshold_reference=0.1, fuse_gap_ms=0)
    assert len(candidates) == 2
    predictions = decode_candidates(candidates, np.array([0.9, 0.9]), threshold=0.5, min_duration_ms=180000, decode_fuse_gap_ms=600000)
    assert len(predictions) == 2


def test_prediction_generation_is_independent_of_validation_truth():
    windows = [w(0, 0, 200000)]
    candidates = build_candidates(windows, np.array([0.9]), threshold_reference=0.1, fuse_gap_ms=0)
    first = decode_candidates(candidates, np.array([0.8]), threshold=0.5, min_duration_ms=180000, decode_fuse_gap_ms=0)
    second = decode_candidates(candidates, np.array([0.8]), threshold=0.5, min_duration_ms=180000, decode_fuse_gap_ms=0)
    assert first == second
