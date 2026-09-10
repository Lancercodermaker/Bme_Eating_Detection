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
        )

    period_ms = 1000.0 / grid_hz
    raw_grid = np.arange(
        float(series.timestamps_ms[0]),
        float(series.timestamps_ms[-1]) + period_ms * 0.5,
        period_ms,
        dtype=np.float64,
    )
    grid = np.unique(np.rint(raw_grid).astype(np.int64))
    values = np.full((grid.size, series.values.shape[1]), np.nan, dtype=np.float64)
    valid_mask = np.zeros(grid.size, dtype=bool)
    max_gap_ms = max_gap_seconds * 1000.0

    for timestamp, row in zip(series.timestamps_ms, series.values):
        index = _nearest_grid_index(grid, int(timestamp))
        if abs(int(grid[index]) - int(timestamp)) <= period_ms / 2:
            values[index] = row
            if np.isfinite(row).any():
                valid_mask[index] = True

    for left_index in range(series.timestamps_ms.size - 1):
        left_time = int(series.timestamps_ms[left_index])
        right_time = int(series.timestamps_ms[left_index + 1])
        if right_time - left_time > max_gap_ms:
            continue
        grid_slice = (grid >= left_time) & (grid <= right_time)
        if not grid_slice.any():
            continue
        left_row = series.values[left_index]
        right_row = series.values[left_index + 1]
        for channel in range(series.values.shape[1]):
            if np.isfinite(left_row[channel]) and np.isfinite(right_row[channel]):
                values[grid_slice, channel] = np.interp(
                    grid[grid_slice],
                    [left_time, right_time],
                    [left_row[channel], right_row[channel]],
                )
        valid_mask[grid_slice] = np.isfinite(values[grid_slice]).any(axis=1)

    return RegularizedSeries(timestamps_ms=grid, values=values, valid_mask=valid_mask)

