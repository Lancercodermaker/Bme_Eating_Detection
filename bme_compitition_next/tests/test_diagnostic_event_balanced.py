import numpy as np
import pytest

from eating_event.diagnostic_event_balanced import (
    compute_event_balanced_sample_weights,
)


def test_event_balanced_weights_preserve_total_and_equal_event_mass():
    labels = np.array([1, 1, 1, 1, 0, -1])
    event_ids = np.array(["e1", "e1", "e2", "e3", None, None], dtype=object)

    weights, audit = compute_event_balanced_sample_weights(labels, event_ids)

    np.testing.assert_allclose(weights[:4].sum(), 3.0 * 4.0)
    np.testing.assert_allclose(weights[0:2].sum(), weights[2])
    np.testing.assert_allclose(weights[0:2].sum(), weights[3])
    assert weights[4] == 1.0
    assert weights[5] == 0.0
    assert audit["positive_row_count"] == 4
    assert audit["event_count"] == 3
    assert audit["positive_weight_total"] == pytest.approx(12.0)


def test_event_balanced_weights_reject_positive_without_unique_event():
    labels = np.array([1, 0])
    event_ids = np.array([None, None], dtype=object)

    with pytest.raises(ValueError, match="exactly one event"):
        compute_event_balanced_sample_weights(labels, event_ids)
