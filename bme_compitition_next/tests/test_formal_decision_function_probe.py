import numpy as np

from eating_event.metrics import EventInterval

from scripts.formal_g1_decision_function_probe import (
    _coverage_support,
    _binary_metrics,
    _fit_model,
    _select_score_quantile,
    select_easy_negative_indices,
)


def test_quantile_selection_matches_formal_g1_tie_break_order():
    rows = [
        {"quantile": 0.7, "pooled_recall": 0.8, "worst_participant_recall": 0.8, "candidate_count": 10},
        {"quantile": 0.8, "pooled_recall": 0.8, "worst_participant_recall": 0.8, "candidate_count": 9},
        {"quantile": 0.9, "pooled_recall": 0.8, "worst_participant_recall": 0.8, "candidate_count": 9},
    ]

    assert _select_score_quantile(rows) == 0.9


def test_easy_negative_control_selects_lowest_frozen_scores_with_stable_ties():
    scores = np.asarray([0.2, 0.1, 0.1, 0.3], dtype=np.float64)
    row_keys = np.asarray(["z", "b", "a", "c"], dtype=object)

    selected = select_easy_negative_indices(scores, row_keys, count=2)

    np.testing.assert_array_equal(selected, np.asarray([2, 1], dtype=np.int64))


def test_coverage_support_reports_union_fraction_and_longest_gap():
    event = EventInterval(0, 1000)
    selected_windows = (EventInterval(0, 300), EventInterval(700, 1200))

    support = _coverage_support(event, selected_windows)

    assert support["coverage_fraction"] == 0.6
    assert support["longest_unsupported_interval_ms"] == 400


def test_nonlinear_candidate_excludes_unsupervised_rows_from_fit():
    features = np.asarray([[0.0], [1.0], [2.0]], dtype=np.float64)
    labels = np.asarray([-1, 0, 1], dtype=np.int8)

    model = _fit_model("N", features, labels)

    scores = model.predict_scores(features[1:])
    np.testing.assert_array_equal(model.estimator.classes_, np.asarray([0, 1], dtype=np.int8))
    assert scores.shape == (2,)
    assert np.isfinite(scores).all()


def test_binary_metrics_reports_separate_positive_and_negative_scores():
    result = _binary_metrics(np.asarray([1, 0, 1], dtype=np.int8), np.asarray([0.8, 0.2, 0.6]))

    assert result["positive_score"]["count"] == 2
    assert result["negative_score"]["count"] == 1
