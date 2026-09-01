from pathlib import Path
from typing import Iterable

import numpy as np

from .io import iter_sensor_chunks


def _update_stream_stats(
    report: dict[str, int | float | None],
    prefix: str,
    timestamps: np.ndarray,
    valid: np.ndarray,
) -> None:
    positive = timestamps[timestamps > 0]
    report[f"{prefix}_positive_timestamp_rows"] += int(len(positive))
    if len(positive):
        report[f"{prefix}_first_timestamp_ms"] = (
            int(positive[0])
            if report[f"{prefix}_first_timestamp_ms"] is None
            else min(report[f"{prefix}_first_timestamp_ms"], int(positive[0]))
        )
        report[f"{prefix}_last_timestamp_ms"] = (
            int(positive[-1])
            if report[f"{prefix}_last_timestamp_ms"] is None
            else max(report[f"{prefix}_last_timestamp_ms"], int(positive[-1]))
        )
        unique = np.unique(positive)
        report[f"{prefix}_duplicate_rows"] += int(len(positive) - len(unique))
        if len(unique) > 1:
            delta = np.diff(unique)
            report[f"{prefix}_interval_median_ms"] = float(np.median(delta))


def audit_sensor_files(
    paths: Iterable[Path], max_rows: int | None = None, chunksize: int = 50_000
) -> dict[str, int | float | None]:
    report: dict[str, int | float | None] = {
        "files_read": 0,
        "rows_read": 0,
        "timestamp_zero_rows": 0,
        "ppg_invalid_rows": 0,
        "acc_invalid_rows": 0,
        "gyro_invalid_rows": 0,
        "ppg_zero_rows": 0,
        "ppg_flat_rows": 0,
    }
    for prefix in ("acc", "gyro", "ppg"):
        report[f"{prefix}_positive_timestamp_rows"] = 0
        report[f"{prefix}_duplicate_rows"] = 0
        report[f"{prefix}_interval_median_ms"] = None
        report[f"{prefix}_first_timestamp_ms"] = None
        report[f"{prefix}_last_timestamp_ms"] = None

    for path in sorted(Path(p) for p in paths):
        report["files_read"] += 1
        remaining = max_rows
        for chunk in iter_sensor_chunks(path, chunksize=chunksize):
            take = len(chunk.acc) if remaining is None else min(len(chunk.acc), remaining)
            if take <= 0:
                break
            timestamps = chunk.timestamp_ms[:take]
            report["rows_read"] += take
            report["timestamp_zero_rows"] += int((timestamps == 0).any(axis=1).sum())
            report["ppg_invalid_rows"] += int((~chunk.ppg_valid[:take]).sum())
            report["acc_invalid_rows"] += int((~chunk.acc_valid[:take]).sum())
            report["gyro_invalid_rows"] += int((~chunk.gyro_valid[:take]).sum())

            ppg = chunk.ppg[:take]
            finite_ppg = np.isfinite(ppg).all(axis=1)
            report["ppg_zero_rows"] += int((finite_ppg & (np.abs(ppg).sum(axis=1) == 0)).sum())
            report["ppg_flat_rows"] += int((finite_ppg & (np.ptp(ppg, axis=1) == 0)).sum())
            _update_stream_stats(report, "acc", timestamps[:, 0], chunk.acc_valid[:take])
            _update_stream_stats(report, "ppg", timestamps[:, 1], chunk.ppg_valid[:take])
            _update_stream_stats(report, "gyro", timestamps[:, 2], chunk.gyro_valid[:take])

            if remaining is not None:
                remaining -= take
                if remaining <= 0:
                    break
    return report
