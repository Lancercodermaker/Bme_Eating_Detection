"""Timestamp de-duplication and gap-aware regularization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class AggregatedSeries:
    timestamps_ms: np.ndarray
    values: np.ndarray
    duplicate_count: int
    dropped_missing_timestamps: int


@dataclass(frozen=True)
class RegularizedSeries:
    timestamps_ms: np.ndarray
    values: np.ndarray
    valid_mask: np.ndarray
    hard_gap_mask: np.ndarray
    interpolated_mask: np.ndarray
    segment_id: np.ndarray

    @property
    def coverage(self) -> float:
        return float(self.valid_mask.mean()) if self.valid_mask.size else 0.0


def _as_value_matrix(values: Sequence[Sequence[float]] | np.ndarray, row_count: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)
    if matrix.ndim != 2 or matrix.shape[0] != row_count:
        raise ValueError("values must be a 2D array with one row per timestamp")
    return matrix


def aggregate_timestamp_rows(
    timestamps_ms: Sequence[int] | np.ndarray,
    values: Sequence[Sequence[float]] | np.ndarray,
) -> AggregatedSeries:
    """Sort packets, drop non-positive timestamps, and mean duplicate rows.

    Duplicate packets are aggregated independently for each channel with a
    NaN-safe mean. A timestamp with no finite value remains NaN instead of
    silently becoming zero.
    """

    timestamps = np.asarray(timestamps_ms, dtype=np.int64)
    if timestamps.ndim != 1:
        raise ValueError("timestamps_ms must be one-dimensional")
    matrix = _as_value_matrix(values, timestamps.size)
    valid_timestamp = timestamps > 0
    dropped_missing = int((~valid_timestamp).sum())
    timestamps = timestamps[valid_timestamp]
    matrix = matrix[valid_timestamp]
    if timestamps.size == 0:
        return AggregatedSeries(
            timestamps_ms=np.empty(0, dtype=np.int64),
            values=np.empty((0, matrix.shape[1]), dtype=np.float64),
            duplicate_count=0,
            dropped_missing_timestamps=dropped_missing,
        )

    order = np.argsort(timestamps, kind="stable")
    sorted_timestamps = timestamps[order]
    sorted_values = matrix[order]
    unique_timestamps, first_indices, counts = np.unique(
        sorted_timestamps, return_index=True, return_counts=True
    )
    aggregated = np.full(
        (unique_timestamps.size, sorted_values.shape[1]), np.nan, dtype=np.float64
    )
    for index, (first, count) in enumerate(zip(first_indices, counts)):
        group = sorted_values[first : first + count]
        finite = np.isfinite(group)
        has_finite = finite.any(axis=0)
        if has_finite.any():
            aggregated[index, has_finite] = np.nansum(group[:, has_finite], axis=0) / finite[:, has_finite].sum(axis=0)

    return AggregatedSeries(
        timestamps_ms=unique_timestamps,
        values=aggregated,
        duplicate_count=int(timestamps.size - unique_timestamps.size),
        dropped_missing_timestamps=dropped_missing,
    )


def _nearest_grid_index(grid: np.ndarray, timestamp_ms: int) -> int:
    index = int(np.searchsorted(grid, timestamp_ms))
    if index == 0:
        return 0
    if index == grid.size:
        return grid.size - 1
    before = index - 1
    after = index
    return before if timestamp_ms - grid[before] <= grid[after] - timestamp_ms else after


def regularize_series(
    series: AggregatedSeries,
    *,
    grid_hz: int,
    max_gap_seconds: float,
    grid_start_ms: int | None = None,
    grid_end_ms: int | None = None,
) -> RegularizedSeries:
    """Put a series on a regular grid without filling across large gaps."""

    if grid_hz <= 0:
        raise ValueError("grid_hz must be positive")
    if max_gap_seconds <= 0:
        raise ValueError("max_gap_seconds must be positive")
    if series.timestamps_ms.size == 0:
        return RegularizedSeries(
            timestamps_ms=np.empty(0, dtype=np.int64),
            values=np.empty_like(series.values),
            valid_mask=np.empty(0, dtype=bool),
            hard_gap_mask=np.empty(0, dtype=bool),
            interpolated_mask=np.empty(0, dtype=bool),
            segment_id=np.empty(0, dtype=np.int32),
        )

    period_ms = 1000.0 / grid_hz
    start_ms = int(series.timestamps_ms[0] if grid_start_ms is None else grid_start_ms)
    end_ms = int(series.timestamps_ms[-1] if grid_end_ms is None else grid_end_ms)
    if end_ms < start_ms:
        raise ValueError("grid_end_ms must not precede grid_start_ms")
    raw_grid = np.arange(
        float(start_ms),
        float(end_ms) + period_ms * 0.5,
        period_ms,
        dtype=np.float64,
    )
    grid = np.unique(np.rint(raw_grid).astype(np.int64))
    values = np.full((grid.size, series.values.shape[1]), np.nan, dtype=np.float64)
    valid_mask = np.zeros(grid.size, dtype=bool)
    hard_gap_mask = np.zeros(grid.size, dtype=bool)
    interpolated_mask = np.zeros(grid.size, dtype=bool)
    segment_id = np.full(grid.size, -1, dtype=np.int32)
    max_gap_ms = max_gap_seconds * 1000.0

    if series.timestamps_ms.size == 1:
        index = _nearest_grid_index(grid, int(series.timestamps_ms[0]))
        if abs(int(grid[index]) - int(series.timestamps_ms[0])) <= period_ms / 2:
                    values[index] = series.values[0]
                    valid_mask[index] = np.isfinite(series.values[0]).any()
                    segment_id[index] = 0
    else:
        long_gap_indices = np.flatnonzero(np.diff(series.timestamps_ms) > max_gap_ms)
        segment_starts = np.concatenate(([0], long_gap_indices + 1))
        segment_ends = np.concatenate((long_gap_indices, [series.timestamps_ms.size - 1]))
        for segment_number, (segment_start, segment_end) in enumerate(zip(segment_starts, segment_ends)):
            left_time = int(series.timestamps_ms[segment_start])
            right_time = int(series.timestamps_ms[segment_end])
            grid_slice = (grid >= left_time) & (grid <= right_time)
            if not grid_slice.any():
                continue
            segment_times = series.timestamps_ms[segment_start : segment_end + 1]
            segment_values = series.values[segment_start : segment_end + 1]
            for channel in range(series.values.shape[1]):
                finite = np.isfinite(segment_values[:, channel])
                if not finite.any():
                    continue
                finite_times = segment_times[finite]
                finite_values = segment_values[finite, channel]
                if finite_times.size == 1:
                    index = _nearest_grid_index(grid, int(finite_times[0]))
                    if abs(int(grid[index]) - int(finite_times[0])) <= period_ms / 2:
                        values[index, channel] = finite_values[0]
                else:
                    values[grid_slice, channel] = np.interp(
                        grid[grid_slice], finite_times, finite_values
                    )
            valid_mask[grid_slice] = np.isfinite(values[grid_slice]).any(axis=1)
            segment_id[grid_slice] = segment_number
            exact_timestamp = np.isin(grid[grid_slice], segment_times)
            interpolated_mask[grid_slice] |= np.isfinite(values[grid_slice]).any(axis=1) & ~exact_timestamp

        for gap_index in long_gap_indices:
            gap_start = int(series.timestamps_ms[gap_index])
            gap_end = int(series.timestamps_ms[gap_index + 1])
            gap_slice = (grid > gap_start) & (grid < gap_end)
            hard_gap_mask[gap_slice] = True
            valid_mask[gap_slice] = False
            values[gap_slice] = np.nan
            segment_id[gap_slice] = -1

    return RegularizedSeries(
        timestamps_ms=grid,
        values=values,
        valid_mask=valid_mask,
        hard_gap_mask=hard_gap_mask,
        interpolated_mask=interpolated_mask,
        segment_id=segment_id,
    )
