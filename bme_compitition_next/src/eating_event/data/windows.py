"""Dense, gap-aware candidate window generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from eating_event.data.labels import WindowLabel, WindowLabelResult, label_window
from eating_event.metrics import EventInterval


@dataclass(frozen=True)
class WindowSpec:
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.end_ms <= self.start_ms:
            raise ValueError("window end_ms must be greater than start_ms")


@dataclass(frozen=True)
class WindowRecord:
    window: WindowSpec
    coverage: float
    longest_invalid_run: int
    label_result: WindowLabelResult

    @property
    def label(self) -> WindowLabel:
        return self.label_result.label


def _longest_false_run(mask: np.ndarray) -> int:
    longest = 0
    current = 0
    for value in mask:
        if value:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def generate_dense_windows(
    timestamps_ms: Sequence[int] | np.ndarray,
    valid_mask: Sequence[bool] | np.ndarray,
    *,
    grid_hz: int,
    window_seconds: float,
    step_seconds: float,
    min_coverage: float,
    max_gap_seconds: float,
    truths: Sequence[EventInterval] = (),
    positive_overlap: float = 0.5,
    negative_distance_ms: int = 300_000,
) -> list[WindowRecord]:
    """Generate dense windows while refusing to bridge a long invalid run."""

    timestamps = np.asarray(timestamps_ms, dtype=np.int64)
    valid = np.asarray(valid_mask, dtype=bool)
    if timestamps.ndim != 1 or valid.ndim != 1 or timestamps.size != valid.size:
        raise ValueError("timestamps_ms and valid_mask must be one-dimensional and aligned")
    if grid_hz <= 0 or window_seconds <= 0 or step_seconds <= 0:
        raise ValueError("grid_hz, window_seconds, and step_seconds must be positive")
    if not 0 < min_coverage <= 1:
        raise ValueError("min_coverage must be in (0, 1]")
    if max_gap_seconds <= 0:
        raise ValueError("max_gap_seconds must be positive")
    if timestamps.size == 0:
        return []

    expected_period = 1000.0 / grid_hz
    if timestamps.size > 1 and not np.allclose(np.diff(timestamps), expected_period, atol=1.0):
        raise ValueError("timestamps_ms must be a regular grid")
    window_points = int(round(window_seconds * grid_hz))
    step_points = int(round(step_seconds * grid_hz))
    if window_points <= 0 or step_points <= 0:
        raise ValueError("window and step must contain at least one grid point")
    allowed_invalid_run = int(np.floor(max_gap_seconds * grid_hz))
    if window_points > timestamps.size:
        return []

    records: list[WindowRecord] = []
    for start_index in range(0, timestamps.size - window_points + 1, step_points):
        end_index = start_index + window_points
        window_valid = valid[start_index:end_index]
        coverage = float(window_valid.mean())
        longest_invalid_run = _longest_false_run(window_valid)
        if coverage < min_coverage or longest_invalid_run > allowed_invalid_run:
            continue
        window = WindowSpec(
            start_ms=int(timestamps[start_index]),
            end_ms=int(round(timestamps[start_index] + window_seconds * 1000)),
        )
        label_result = label_window(
            EventInterval(window.start_ms, window.end_ms),
            truths,
            positive_overlap=positive_overlap,
            negative_distance_ms=negative_distance_ms,
        )
        records.append(
            WindowRecord(
                window=window,
                coverage=coverage,
                longest_invalid_run=longest_invalid_run,
                label_result=label_result,
            )
        )
    return records
