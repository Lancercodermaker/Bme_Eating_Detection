import numpy as np
import pytest

from eating_event.a1.scoring import (
    compute_reference_threshold,
    fit_candidate_estimator,
    fit_verifier_estimator,
    validate_g3,
)


def test_reference_contains_ignore_rows_but_fit_uses_only_binary_labels():
    features = np.arange(12 * 2, dtype=np.float32).reshape(12, 2)
    labels = np.array([0, 1, -1, 0, 1, -1, 0, 1, 0, 1, 0, 1], dtype=np.int8)
    reference = compute_reference_threshold(np.linspace(0.0, 1.0, 12), labels, 0.9)
    assert reference.row_count == 12
    estimator = fit_candidate_estimator(features, labels, positive_weight=3.0, random_state=20260910, max_iter=2)
    assert set(estimator.classes_) == {0, 1}


def test_reference_rejects_empty_or_nonfinite_scores():
    with pytest.raises(ValueError, match="reference"):
        compute_reference_threshold(np.array([]), np.array([]), 0.9)
    with pytest.raises(ValueError, match="finite"):
        compute_reference_threshold(np.array([0.1, np.nan]), np.array([0, 1]), 0.9)


def test_g3_requires_two_classes_20_candidates_and_5_participants():
    with pytest.raises(ValueError, match="20"):
        validate_g3([1] * 19 + [0], [f"p{i % 5}" for i in range(20)])
    with pytest.raises(ValueError, match="5 participants"):
        validate_g3([1] * 20 + [0], [f"p{i % 4}" for i in range(21)])
    with pytest.raises(ValueError, match="both"):
        validate_g3([1] * 21, [f"p{i % 5}" for i in range(21)])
    validate_g3([1] * 20 + [0] * 5, [f"p{i % 5}" for i in range(25)])


def test_verifier_fit_fails_closed_on_g3():
    with pytest.raises(ValueError, match="G3"):
        fit_verifier_estimator(np.zeros((20, 16)), np.ones(20, dtype=np.int8), [f"p{i % 5}" for i in range(20)])
