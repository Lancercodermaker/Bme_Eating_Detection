import numpy as np

from scripts.run_external_transformer_preflight import _positive_weight


def test_positive_weight_is_bounded_and_uses_labeled_class_ratio() -> None:
    labels = np.asarray([0, 0, 0, 1], dtype=np.int8)

    assert _positive_weight(labels) == 3.0


def test_positive_weight_rejects_one_class_training_data() -> None:
    labels = np.zeros(4, dtype=np.int8)

    try:
        _positive_weight(labels)
    except ValueError as exc:
        assert "both positive and negative" in str(exc)
    else:
        raise AssertionError("one-class labels must not produce a training weight")
