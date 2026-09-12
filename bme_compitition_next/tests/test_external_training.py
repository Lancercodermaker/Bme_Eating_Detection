import numpy as np

from eating_event.external_training import select_external_window_indices


def test_select_external_window_indices_keeps_temporal_order_and_both_classes() -> None:
    labels = np.asarray([0, 0, 1, 0, 1, 0, 0, 1, 0, 0], dtype=np.int8)

    selected = select_external_window_indices(labels, max_windows=6)

    assert selected.tolist() == sorted(selected.tolist())
    assert len(selected) == 6
    assert set(labels[selected].tolist()) == {0, 1}


def test_select_external_window_indices_returns_all_when_uncapped() -> None:
    labels = np.asarray([0, 1, 0], dtype=np.int8)

    selected = select_external_window_indices(labels, max_windows=None)

    np.testing.assert_array_equal(selected, np.arange(3))
