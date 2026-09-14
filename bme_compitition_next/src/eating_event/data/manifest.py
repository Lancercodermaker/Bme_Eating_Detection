"""Participant/session manifest and train-only meal interval loading."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Mapping

from eating_event.metrics import EventInterval


@dataclass(frozen=True)
class RawFileRecord:
    participant_id: str
    path: Path
    session_folder: str
    session_start_ms: int
    session_end_ms: int


@dataclass
class ManifestAudit:
    """Explicit provenance for every discovery decision."""

    invalid_index_rows: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    records: list[dict[str, object]] = field(default_factory=list)

    def record(self, status: str, *, participant_id: str, reason: str, **details: object) -> None:
        self.status_counts[status] = self.status_counts.get(status, 0) + 1
        self.records.append(
            {
                "participant_id": participant_id,
                "status": status,
                "reason": reason,
                **details,
            }
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _timestamp(value: str) -> int:
    return int(round(float(value)))


def load_meal_events(path: str | Path) -> dict[str, tuple[EventInterval, ...]]:
    """Load valid target events, excluding the official test placeholder."""

    events: dict[str, list[EventInterval]] = defaultdict(list)
    with Path(path).expanduser().resolve().open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            participant_id = (row.get("externalid") or "").strip()
            if not participant_id or participant_id.lower() == "test":
                continue
            try:
                start_ms = _timestamp(row["beforeTime"])
                end_ms = _timestamp(row["afterTime"])
            except (KeyError, TypeError, ValueError):
                continue
            if end_ms <= start_ms:
                continue
            events[participant_id].append(EventInterval(start_ms, end_ms))
    return {participant: tuple(sorted(values)) for participant, values in events.items()}


def discover_raw_files(raw_root: str | Path, *, include_test: bool = False) -> list[RawFileRecord]:
    """Discover session files from each participant's explicit index.csv."""

    records, _ = discover_raw_files_with_audit(raw_root, include_test=include_test)
    return records


def discover_raw_files_with_audit(
    raw_root: str | Path,
    *,
    include_test: bool = False,
) -> tuple[list[RawFileRecord], ManifestAudit]:
    """Discover session files and retain provenance for every skipped item."""

    root = Path(raw_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"raw_root does not exist: {root}")
    records: list[RawFileRecord] = []
    audit = ManifestAudit()
    for participant_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        participant_id = participant_dir.name
        if participant_id == "_UNMAPPED_":
            audit.record("skipped_invalid_session", participant_id=participant_id, reason="unmapped participant")
            continue
        if participant_id.lower() == "test" and not include_test:
            audit.record("excluded_test_participant", participant_id=participant_id, reason="test participant excluded")
            continue
        index_path = participant_dir / "index.csv"
        if not index_path.is_file():
            audit.record(
                "skipped_missing_index",
                participant_id=participant_id,
                reason="participant index.csv is missing",
                path_or_file_id=str(index_path),
            )
            continue
        with index_path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader, start=2):
                folder_name = (row.get("folder_name") or "").strip()
                if not folder_name:
                    audit.invalid_index_rows += 1
                    audit.record(
                        "skipped_invalid_session",
                        participant_id=participant_id,
                        reason="index row has no folder_name",
                        path_or_file_id=str(index_path),
                        source_row_number=row_number,
                    )
                    continue
                try:
                    start_ms = _timestamp(row["startTime"])
                    end_ms = _timestamp(row["endTime"])
                except (KeyError, TypeError, ValueError):
                    audit.invalid_index_rows += 1
                    audit.record(
                        "skipped_invalid_session",
                        participant_id=participant_id,
                        reason="index row has invalid session bounds",
                        path_or_file_id=str(index_path),
                        source_row_number=row_number,
                        session_id=folder_name,
                    )
                    continue
                if end_ms <= start_ms:
                    audit.invalid_index_rows += 1
                    audit.record(
                        "skipped_invalid_session",
                        participant_id=participant_id,
                        reason="session end is not after session start",
                        path_or_file_id=str(index_path),
                        source_row_number=row_number,
                        session_id=folder_name,
                    )
                    continue
                session_dir = participant_dir / folder_name
                if not session_dir.is_dir():
                    audit.record(
                        "skipped_invalid_session",
                        participant_id=participant_id,
                        reason="session folder is missing",
                        path_or_file_id=str(session_dir),
                        source_row_number=row_number,
                        session_id=folder_name,
                    )
                    continue
                sensor_paths = sorted(session_dir.glob("*.txt"))
                if not sensor_paths:
                    audit.record(
                        "skipped_missing_required_imu",
                        participant_id=participant_id,
                        reason="session has no sensor files",
                        path_or_file_id=str(session_dir),
                        source_row_number=row_number,
                        session_id=folder_name,
                    )
                    continue
                for sensor_path in sensor_paths:
                    records.append(
                        RawFileRecord(
                            participant_id=participant_id,
                            path=sensor_path,
                            session_folder=folder_name,
                            session_start_ms=start_ms,
                            session_end_ms=end_ms,
                        )
                    )
                    audit.record(
                        "processed",
                        participant_id=participant_id,
                        reason="sensor file discovered",
                        path_or_file_id=str(sensor_path),
                        session_id=folder_name,
                        session_start_ms=start_ms,
                        session_end_ms=end_ms,
                    )
    return records, audit


def events_for_record(
    record: RawFileRecord,
    meal_events: Mapping[str, tuple[EventInterval, ...]],
) -> tuple[EventInterval, ...]:
    return tuple(
        event
        for event in meal_events.get(record.participant_id, ())
        if event.start_ms < record.session_end_ms and event.end_ms > record.session_start_ms
    )

