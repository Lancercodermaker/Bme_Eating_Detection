from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CanonicalStream:
    timestamps_ms: np.ndarray
    values: np.ndarray
    duplicate_rows: int


def canonicalize_stream(
    timestamps_ms: np.ndarray, values: np.ndarray
) -> CanonicalStream:
    timestamps = np.asarray(timestamps_ms, dtype=np.int64)
    array = np.asarray(values, dtype=np.float32)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or len(timestamps) != len(array):
        raise ValueError("timestamps and values must have matching row counts")

    valid = (timestamps > 0) & np.isfinite(array).all(axis=1)
    timestamps = timestamps[valid]
    array = array[valid]
    order = np.argsort(timestamps, kind="stable")
    timestamps = timestamps[order]
    array = array[order]
    unique, starts, counts = np.unique(
        timestamps, return_index=True, return_counts=True
    )
    if len(unique):
        sums = np.add.reduceat(array, starts, axis=0)
        averaged = sums / counts[:, None]
    else:
        averaged = np.empty((0, array.shape[1]), dtype=np.float32)
    return CanonicalStream(
        timestamps_ms=unique.astype(np.int64),
        values=averaged,
        duplicate_rows=int(counts.sum() - len(unique)),
    )


def infer_rate_hz(timestamps_ms: np.ndarray) -> float:
    timestamps = np.unique(np.asarray(timestamps_ms, dtype=np.int64))
    timestamps = timestamps[timestamps > 0]
    deltas = np.diff(timestamps)
    deltas = deltas[deltas > 0]
    if len(deltas) == 0:
        raise ValueError("at least two positive timestamps are required")
    return float(1000.0 / np.median(deltas))


def interpolate_uniform(
    stream: CanonicalStream,
    rate_hz: float,
    start_ms: int,
    end_ms: int,
    max_gap_ms: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if rate_hz <= 0 or end_ms < start_ms or max_gap_ms < 0:
        raise ValueError("rate_hz must be positive and end_ms must not precede start_ms")
    if len(stream.timestamps_ms) == 0:
        raise ValueError("cannot interpolate an empty stream")

    step_ms = 1000.0 / rate_hz
    grid = np.arange(start_ms, end_ms + 0.5 * step_ms, step_ms)
    values = np.column_stack(
        [
            np.interp(grid, stream.timestamps_ms, stream.values[:, column])
            for column in range(stream.values.shape[1])
        ]
    )
    left = np.searchsorted(stream.timestamps_ms, grid, side="right") - 1
    right = np.clip(left + 1, 0, len(stream.timestamps_ms) - 1)
    left = np.clip(left, 0, len(stream.timestamps_ms) - 1)
    gap = stream.timestamps_ms[right] - stream.timestamps_ms[left]
    valid = (
        (grid >= stream.timestamps_ms[0])
        & (grid <= stream.timestamps_ms[-1])
        & (gap <= max_gap_ms)
    )
    return grid.astype(np.int64), values.astype(np.float32), valid.astype(bool)
