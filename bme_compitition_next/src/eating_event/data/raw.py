"""Chunked reader for the competition's raw sensor TSV files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eating_event.data.timebase import AggregatedSeries, RegularizedSeries, regularize_series


@dataclass(frozen=True)
class RawIMU:
    acc: AggregatedSeries
    gyro: AggregatedSeries


class RawFileFormatError(ValueError):
    """The file is not a valid competition sensor TSV."""


class _TimestampAccumulator:
    def __init__(self, width: int) -> None:
        self.width = width
        self.sums: dict[int, np.ndarray] = {}
        self.counts: dict[int, np.ndarray] = {}
        self.positive_rows = 0
        self.missing_rows = 0

    def update(self, timestamps: np.ndarray, values: np.ndarray) -> None:
        finite_time = np.isfinite(timestamps)
        positive_time = finite_time & (timestamps > 0)
        self.missing_rows += int((~positive_time).sum())
        self.positive_rows += int(positive_time.sum())
        valid_timestamps = np.rint(timestamps[positive_time]).astype(np.int64)
        valid_values = values[positive_time]
        unique, inverse = np.unique(valid_timestamps, return_inverse=True)
        for group_index, timestamp in enumerate(unique):
            group = valid_values[inverse == group_index]
            finite_values = np.isfinite(group)
            sums = np.nansum(group, axis=0)
            counts = finite_values.sum(axis=0).astype(np.int64)
            if int(timestamp) not in self.sums:
                self.sums[int(timestamp)] = sums
                self.counts[int(timestamp)] = counts
            else:
                self.sums[int(timestamp)] += sums
                self.counts[int(timestamp)] += counts

    def finish(self) -> AggregatedSeries:
        timestamps = np.asarray(sorted(self.sums), dtype=np.int64)
        values = np.full((timestamps.size, self.width), np.nan, dtype=np.float64)
        for index, timestamp in enumerate(timestamps):
            counts = self.counts[int(timestamp)]
            finite = counts > 0
            if finite.any():
                values[index, finite] = self.sums[int(timestamp)][finite] / counts[finite]
        return AggregatedSeries(
            timestamps_ms=timestamps,
            values=values,
            duplicate_count=int(self.positive_rows - timestamps.size),
            dropped_missing_timestamps=self.missing_rows,
        )


def read_imu_tsv(path: str | Path, *, chunk_size: int = 200_000) -> RawIMU:
    """Read only ACC/GYRO columns and aggregate repeated packet timestamps."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    file_path = Path(path).expanduser().resolve()
    required = [
        "ACC_TIME",
        "ACC_X",
        "ACC_Y",
        "ACC_Z",
        "GYRO_TIME",
        "GYRO_X",
        "GYRO_Y",
        "GYRO_Z",
    ]
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - dependency is declared in pyproject
        raise RawFileFormatError("pandas is required to read raw sensor files") from exc

    def read_with_encoding(encoding: str) -> RawIMU:
        try:
            header = pd.read_csv(file_path, sep="\t", encoding=encoding, nrows=0)
        except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            raise RawFileFormatError(f"cannot decode sensor header: {file_path}") from exc
        missing = sorted(set(required) - set(header.columns))
        if missing:
            raise RawFileFormatError(f"sensor header missing required columns {missing}: {file_path}")
        reader = pd.read_csv(
            file_path,
            sep="\t",
            usecols=required,
            dtype={column: "float64" for column in required},
            chunksize=chunk_size,
            encoding=encoding,
            on_bad_lines="skip",
        )
        acc = _TimestampAccumulator(width=3)
        gyro = _TimestampAccumulator(width=3)
        try:
            for chunk in reader:
                acc.update(chunk["ACC_TIME"].to_numpy(), chunk[["ACC_X", "ACC_Y", "ACC_Z"]].to_numpy())
                gyro.update(chunk["GYRO_TIME"].to_numpy(), chunk[["GYRO_X", "GYRO_Y", "GYRO_Z"]].to_numpy())
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError, TypeError) as exc:
            raise RawFileFormatError(f"cannot decode sensor rows: {file_path}") from exc
        return RawIMU(acc=acc.finish(), gyro=gyro.finish())

    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return read_with_encoding(encoding)
        except RawFileFormatError as exc:
            if "missing required columns" in str(exc):
                raise
    raise RawFileFormatError(f"unsupported or corrupted sensor file: {file_path}")


def regularize_imu(raw: RawIMU, *, grid_hz: int, max_gap_seconds: float) -> RegularizedSeries:
    """Regularize ACC and GYRO independently, then combine aligned grids."""

    if raw.acc.timestamps_ms.size == 0 or raw.gyro.timestamps_ms.size == 0:
        raise ValueError("ACC and GYRO streams must both contain valid timestamps")
    grid_start_ms = int(min(raw.acc.timestamps_ms[0], raw.gyro.timestamps_ms[0]))
    grid_end_ms = int(max(raw.acc.timestamps_ms[-1], raw.gyro.timestamps_ms[-1]))
    acc = regularize_series(
        raw.acc,
        grid_hz=grid_hz,
        max_gap_seconds=max_gap_seconds,
        grid_start_ms=grid_start_ms,
        grid_end_ms=grid_end_ms,
    )
    gyro = regularize_series(
        raw.gyro,
        grid_hz=grid_hz,
        max_gap_seconds=max_gap_seconds,
        grid_start_ms=grid_start_ms,
        grid_end_ms=grid_end_ms,
    )
    values = np.concatenate([acc.values, gyro.values], axis=1)
    valid_mask = acc.valid_mask & gyro.valid_mask
    return RegularizedSeries(acc.timestamps_ms, values, valid_mask)
