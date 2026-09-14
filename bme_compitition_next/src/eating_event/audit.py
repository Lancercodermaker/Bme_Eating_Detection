"""Bounded, streaming audit for the competition TSV packet format."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ModalityAudit:
    positive_rows: int
    missing_rows: int
    unique_timestamps: int
    duplicate_rows: int
    max_gap_ms: int


@dataclass(frozen=True)
class FileAudit:
    path: str
    total_rows: int
    malformed_rows: int
    truncated: bool
    modalities: dict[str, ModalityAudit]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_timestamp(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        timestamp = float(value)
    except ValueError:
        return None
    if not math.isfinite(timestamp) or timestamp <= 0:
        return None
    return int(round(timestamp))


def _modality_audit(positive: int, missing: int, timestamps: set[int]) -> ModalityAudit:
    ordered = sorted(timestamps)
    max_gap = max((right - left for left, right in zip(ordered, ordered[1:])), default=0)
    return ModalityAudit(
        positive_rows=positive,
        missing_rows=missing,
        unique_timestamps=len(timestamps),
        duplicate_rows=positive - len(timestamps),
        max_gap_ms=max_gap,
    )


def audit_tsv_file(path: str | Path, *, max_rows: int | None = None) -> FileAudit:
    """Audit one TSV without retaining signal rows in memory."""

    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be positive when provided")
    file_path = Path(path).expanduser().resolve()
    positive: dict[str, int] = {}
    missing: dict[str, int] = {}
    timestamps: dict[str, set[int]] = {}
    total_rows = 0
    malformed_rows = 0
    truncated = False

    with file_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"empty TSV file: {file_path}") from exc
        modality_columns = {
            name: index
            for index, name in enumerate(header)
            if name in {"ACC_TIME", "GYRO_TIME", "PPG_TIME"}
        }
        for name in modality_columns:
            positive[name] = 0
            missing[name] = 0
            timestamps[name] = set()

        for row in reader:
            if max_rows is not None and total_rows >= max_rows:
                truncated = True
                break
            total_rows += 1
            if len(row) != len(header):
                malformed_rows += 1
                continue
            for name, index in modality_columns.items():
                timestamp = _parse_timestamp(row[index])
                if timestamp is None:
                    missing[name] += 1
                else:
                    positive[name] += 1
                    timestamps[name].add(timestamp)

    return FileAudit(
        path=str(file_path),
        total_rows=total_rows,
        malformed_rows=malformed_rows,
        truncated=truncated,
        modalities={
            name: _modality_audit(positive[name], missing[name], timestamps[name])
            for name in modality_columns
        },
    )


def audit_tsv_files(paths: Iterable[str | Path], *, max_rows: int | None = None) -> list[FileAudit]:
    return [audit_tsv_file(path, max_rows=max_rows) for path in paths]


def write_audit_json(audits: Iterable[FileAudit], output_path: str | Path) -> None:
    payload = [audit.to_dict() for audit in audits]
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_dataset_audit_report(payload: dict[str, object], output_path: str | Path) -> None:
    """Write one bounded dataset-audit report without opening a formal run."""

    report = dict(payload)
    report.setdefault("schema_version", "dataset_audit_v1")
    report.setdefault("started_at", datetime.now(timezone.utc).isoformat())
    report.setdefault("ended_at", datetime.now(timezone.utc).isoformat())
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

