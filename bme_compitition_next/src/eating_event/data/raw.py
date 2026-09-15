"""Chunked reader for the competition's raw sensor TSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eating_event.data.timebase import AggregatedSeries, RegularizedSeries, regularize_series


@dataclass(frozen=True)
class RawIMU:
    acc: AggregatedSeries
    gyro: AggregatedSeries


@dataclass(frozen=True)
class RawReadAudit:
    path: str
    status: str
    reason: str | None
    total_rows: int
    valid_rows: int
    malformed_rows: int
    malformed_row_details: tuple[dict[str, object], ...]
    duplicate_count: int
    dropped_timestamp_count: int


@dataclass(frozen=True)
class RawIMUReadResult:
    acc: AggregatedSeries
    gyro: AggregatedSeries
    audit: RawReadAudit

    @property
    def imu(self) -> RawIMU:
        return RawIMU(acc=self.acc, gyro=self.gyro)


class RawFileFormatError(ValueError):
    """The file is not a valid competition sensor TSV."""


def _aggregate_timestamp_values(
    timestamps: np.ndarray,
    values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Group one chunk by timestamp without scanning the full chunk per group."""

    timestamp_array = np.asarray(timestamps, dtype=np.int64)
    value_array = np.asarray(values, dtype=np.float64)
    if timestamp_array.ndim != 1 or value_array.ndim != 2:
        raise ValueError("timestamps must be 1-D and values must be 2-D")
    if timestamp_array.size != value_array.shape[0]:
        raise ValueError("timestamps and values must have aligned rows")
    unique, inverse = np.unique(timestamp_array, return_inverse=True)
    if unique.size == 0:
        return (
            unique,
            np.empty((0, value_array.shape[1]), dtype=np.float64),
            np.empty((0, value_array.shape[1]), dtype=np.int64),
        )
    finite = np.isfinite(value_array)
    sums = np.column_stack(
        [
            np.bincount(
                inverse,
                weights=np.where(finite[:, column], value_array[:, column], 0.0),
                minlength=unique.size,
            )
            for column in range(value_array.shape[1])
        ]
    )
    counts = np.column_stack(
        [
            np.bincount(inverse, weights=finite[:, column].astype(np.int64), minlength=unique.size)
            for column in range(value_array.shape[1])
        ]
    ).astype(np.int64, copy=False)
    return unique, sums, counts


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
        unique, sums_by_timestamp, counts_by_timestamp = _aggregate_timestamp_values(
            valid_timestamps,
            valid_values,
        )
        for group_index, timestamp in enumerate(unique):
            sums = sums_by_timestamp[group_index]
            counts = counts_by_timestamp[group_index]
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

    return read_imu_tsv_with_audit(path, chunk_size=chunk_size).imu


def read_imu_tsv_with_audit(path: str | Path, *, chunk_size: int = 200_000) -> RawIMUReadResult:
    """Read ACC/GYRO rows while preserving malformed-row provenance."""

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

    def read_large_with_pandas(encoding: str) -> RawIMUReadResult:
        """Use the bounded C parser for real files; keep the Python parser for fixtures."""

        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - dependency is declared in pyproject
            raise RawFileFormatError("pandas is required to read raw sensor files") from exc
        malformed_details: list[dict[str, object]] = []
        try:
            with file_path.open("r", encoding=encoding, newline="") as stream:
                reader = csv.reader(stream, delimiter="\t")
                header = next(reader)
                missing = sorted(set(required) - set(header))
                if missing:
                    raise RawFileFormatError(
                        f"sensor header missing required columns {missing}: {file_path}"
                    )
                total_rows = 0
                bad_source_rows: set[int] = set()
                indices = {name: header.index(name) for name in required}
                signal_names = [
                    "ACC_X",
                    "ACC_Y",
                    "ACC_Z",
                    "GYRO_X",
                    "GYRO_Y",
                    "GYRO_Z",
                ]
                invalid_timestamp_values = {"ACC_TIME": set(), "GYRO_TIME": set()}
                for source_row_number, row in enumerate(reader, start=2):
                    total_rows += 1
                    if len(row) != len(header):
                        bad_source_rows.add(source_row_number)
                        malformed_details.append(
                            {
                                "source_row_number": source_row_number,
                                "reason": "column_count_mismatch",
                            }
                        )
                        continue
                    malformed_signal = False
                    for name in signal_names:
                        text = row[indices[name]].strip()
                        if not text:
                            continue
                        try:
                            float(text)
                        except ValueError:
                            bad_source_rows.add(source_row_number)
                            malformed_details.append(
                                {
                                    "source_row_number": source_row_number,
                                    "reason": "non_numeric_required_signal",
                                }
                            )
                            malformed_signal = True
                            break
                    if malformed_signal:
                        continue
                    for name in ("ACC_TIME", "GYRO_TIME"):
                        text = row[indices[name]].strip()
                        if not text:
                            continue
                        try:
                            float(text)
                        except ValueError:
                            invalid_timestamp_values[name].add(text)
        except (OSError, UnicodeDecodeError, csv.Error, StopIteration) as exc:
            raise RawFileFormatError(f"cannot decode sensor rows: {file_path}") from exc

        acc = _TimestampAccumulator(width=3)
        gyro = _TimestampAccumulator(width=3)
        skiprows = lambda line_number: line_number + 1 in bad_source_rows
        try:
            reader = pd.read_csv(
                file_path,
                sep="\t",
                usecols=required,
                dtype={column: "float64" for column in required},
                    chunksize=chunk_size,
                    encoding=encoding,
                    on_bad_lines="skip",
                    skiprows=skiprows,
                    na_values=invalid_timestamp_values,
                )
            for chunk in reader:
                acc.update(chunk["ACC_TIME"].to_numpy(), chunk[["ACC_X", "ACC_Y", "ACC_Z"]].to_numpy())
                gyro.update(chunk["GYRO_TIME"].to_numpy(), chunk[["GYRO_X", "GYRO_Y", "GYRO_Z"]].to_numpy())
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError, TypeError) as exc:
            raise RawFileFormatError(f"cannot decode sensor rows: {file_path}") from exc
        acc_result = acc.finish()
        gyro_result = gyro.finish()
        if acc_result.timestamps_ms.size == 0 or gyro_result.timestamps_ms.size == 0:
            raise RawFileFormatError(f"no valid required ACC/GYRO timestamps: {file_path}")
        return RawIMUReadResult(
            acc=acc_result,
            gyro=gyro_result,
            audit=RawReadAudit(
                path=str(file_path),
                status="processed",
                reason=None,
                total_rows=total_rows,
                valid_rows=total_rows - len(malformed_details),
                malformed_rows=len(malformed_details),
                malformed_row_details=tuple(malformed_details),
                duplicate_count=acc_result.duplicate_count + gyro_result.duplicate_count,
                dropped_timestamp_count=(
                    acc_result.dropped_missing_timestamps + gyro_result.dropped_missing_timestamps
                ),
            ),
        )

    def read_with_encoding(encoding: str) -> RawIMU:
        if file_path.stat().st_size > 1_000_000:
            return read_large_with_pandas(encoding)  # type: ignore[return-value]
        try:
            stream = file_path.open("r", encoding=encoding, newline="")
        except (OSError, UnicodeDecodeError) as exc:
            raise RawFileFormatError(f"cannot decode sensor file: {file_path}") from exc
        reader = csv.reader(stream, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration as exc:
            stream.close()
            raise RawFileFormatError(f"empty sensor file: {file_path}") from exc
        except UnicodeDecodeError as exc:
            stream.close()
            raise RawFileFormatError(f"cannot decode sensor header: {file_path}") from exc
        missing = sorted(set(required) - set(header))
        if missing:
            stream.close()
            raise RawFileFormatError(f"sensor header missing required columns {missing}: {file_path}")
        indices = {name: header.index(name) for name in required}
        acc = _TimestampAccumulator(width=3)
        gyro = _TimestampAccumulator(width=3)
        malformed_details: list[dict[str, object]] = []
        total_rows = 0
        valid_rows = 0
        acc_times: list[float] = []
        gyro_times: list[float] = []
        acc_values: list[list[float]] = []
        gyro_values: list[list[float]] = []

        def flush() -> None:
            if not acc_times:
                return
            acc.update(np.asarray(acc_times), np.asarray(acc_values, dtype=np.float64))
            gyro.update(np.asarray(gyro_times), np.asarray(gyro_values, dtype=np.float64))
            acc_times.clear()
            gyro_times.clear()
            acc_values.clear()
            gyro_values.clear()

        try:
            for row_number, row in enumerate(reader, start=2):
                total_rows += 1
                if len(row) != len(header):
                    malformed_details.append(
                        {"source_row_number": row_number, "reason": "column_count_mismatch"}
                    )
                    continue

                def parse_value(name: str, *, timestamp: bool = False) -> float:
                    text = row[indices[name]].strip()
                    if not text:
                        return float("nan")
                    try:
                        value = float(text)
                    except ValueError:
                        if timestamp:
                            return float("nan")
                        raise
                    return value

                try:
                    values = {
                        name: parse_value(name, timestamp=name.endswith("_TIME"))
                        for name in required
                    }
                except ValueError:
                    malformed_details.append(
                        {"source_row_number": row_number, "reason": "non_numeric_required_signal"}
                    )
                    continue
                valid_rows += 1
                acc_times.append(values["ACC_TIME"])
                gyro_times.append(values["GYRO_TIME"])
                acc_values.append([values["ACC_X"], values["ACC_Y"], values["ACC_Z"]])
                gyro_values.append([values["GYRO_X"], values["GYRO_Y"], values["GYRO_Z"]])
                if len(acc_times) >= chunk_size:
                    flush()
            flush()
        except (UnicodeDecodeError, csv.Error, ValueError, TypeError) as exc:
            stream.close()
            raise RawFileFormatError(f"cannot decode sensor rows: {file_path}") from exc
        finally:
            stream.close()
        acc_result = acc.finish()
        gyro_result = gyro.finish()
        if acc_result.timestamps_ms.size == 0 or gyro_result.timestamps_ms.size == 0:
            raise RawFileFormatError(f"no valid required ACC/GYRO timestamps: {file_path}")
        audit = RawReadAudit(
            path=str(file_path),
            status="processed",
            reason=None,
            total_rows=total_rows,
            valid_rows=valid_rows,
            malformed_rows=len(malformed_details),
            malformed_row_details=tuple(malformed_details),
            duplicate_count=acc_result.duplicate_count + gyro_result.duplicate_count,
            dropped_timestamp_count=(
                acc_result.dropped_missing_timestamps + gyro_result.dropped_missing_timestamps
            ),
        )
        return RawIMUReadResult(acc=acc_result, gyro=gyro_result, audit=audit)

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
        raise RawFileFormatError("ACC and GYRO streams must both contain valid timestamps")
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
    hard_gap_mask = acc.hard_gap_mask | gyro.hard_gap_mask
    segment_id = np.where(hard_gap_mask, -1, np.minimum(acc.segment_id, gyro.segment_id)).astype(np.int32)
    return RegularizedSeries(
        timestamps_ms=acc.timestamps_ms,
        values=values,
        valid_mask=valid_mask,
        hard_gap_mask=hard_gap_mask,
        interpolated_mask=acc.interpolated_mask | gyro.interpolated_mask,
        segment_id=segment_id,
    )
