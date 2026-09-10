import numpy as np
import pytest

from eating_event.data.timebase import aggregate_timestamp_rows, regularize_series


def test_duplicate_rows_are_sorted_and_nan_safe_aggregated() -> None:
    timestamps = np.array([2000, 1000, 1000, 2000, 4000], dtype=np.int64)
    values = np.array([[4.0], [1.0], [3.0], [2.0], [np.nan]], dtype=np.float64)

    result = aggregate_timestamp_rows(timestamps, values)

    np.testing.assert_array_equal(result.timestamps_ms, [1000, 2000, 4000])
    np.testing.assert_allclose(result.values[:2, 0], [2.0, 3.0])
    assert np.isnan(result.values[2, 0])
    assert result.duplicate_count == 2
    assert result.dropped_missing_timestamps == 0


def test_zero_timestamps_are_missing_and_not_time_zero() -> None:
    timestamps = np.array([0, 1000, 0, 2000], dtype=np.int64)
    values = np.ones((4, 2), dtype=np.float64)

    result = aggregate_timestamp_rows(timestamps, values)

    np.testing.assert_array_equal(result.timestamps_ms, [1000, 2000])
    assert result.dropped_missing_timestamps == 2


def test_regularization_does_not_interpolate_across_a_real_gap() -> None:
    timestamps = np.array([1000, 2000, 11000], dtype=np.int64)
    values = np.array([[0.0], [1.0], [10.0]], dtype=np.float64)
    aggregated = aggregate_timestamp_rows(timestamps, values)

    result = regularize_series(aggregated, grid_hz=1, max_gap_seconds=2.0)

    np.testing.assert_array_equal(result.timestamps_ms, np.arange(1000, 11001, 1000))
    assert result.valid_mask[:2].tolist() == [True, True]
    assert result.valid_mask[2:10].tolist() == [False] * 8
    assert result.valid_mask[10]
    assert np.isnan(result.values[5, 0])
    assert result.coverage == pytest.approx(3 / 11)
