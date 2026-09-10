import numpy as np
import pytest

from eating_event.data.labels import WindowLabel, label_window
from eating_event.data.windows import WindowSpec, generate_dense_windows
from eating_event.metrics import EventInterval


def test_window_label_marks_positive_and_ambiguous_regions() -> None:
    window = WindowSpec(0, 1000)

    positive = label_window(window, [EventInterval(400, 900)], positive_overlap=0.5)
    ambiguous = label_window(window, [EventInterval(400, 899)], positive_overlap=0.5)

    assert positive.label is WindowLabel.POSITIVE
    assert positive.overlap_fraction == pytest.approx(0.5)
    assert ambiguous.label is WindowLabel.IGNORE


def test_window_is_negative_only_when_far_from_all_events() -> None:
    window = WindowSpec(2000, 3000)
    truth = [EventInterval(0, 100)]

    negative = label_window(window, truth, positive_overlap=0.5, negative_distance_ms=1000)
    ambiguous = label_window(window, truth, positive_overlap=0.5, negative_distance_ms=2500)

    assert negative.label is WindowLabel.NEGATIVE
    assert ambiguous.label is WindowLabel.IGNORE


def test_dense_windows_reject_long_gap_crossing_but_allow_small_missing_run() -> None:
    timestamps = np.arange(0, 11_000, 1000, dtype=np.int64)
    valid_mask = np.ones(timestamps.size, dtype=bool)
    valid_mask[5:8] = False

    windows = generate_dense_windows(
        timestamps,
        valid_mask,
        grid_hz=1,
        window_seconds=4,
        step_seconds=1,
        min_coverage=0.75,
        max_gap_seconds=1.0,
    )

    assert windows
    assert all(record.coverage >= 0.75 for record in windows)
    assert all(record.longest_invalid_run <= 1 for record in windows)
    assert not any(record.window.start_ms <= 5000 and record.window.end_ms >= 8000 for record in windows)


def test_dense_windows_report_coverage() -> None:
    timestamps = np.arange(0, 5_000, 1000, dtype=np.int64)
    valid_mask = np.array([True, True, True, True, False])

    windows = generate_dense_windows(
        timestamps,
        valid_mask,
        grid_hz=1,
        window_seconds=5,
        step_seconds=1,
        min_coverage=0.8,
        max_gap_seconds=1.0,
    )

    assert len(windows) == 1
    assert windows[0].coverage == pytest.approx(0.8)
