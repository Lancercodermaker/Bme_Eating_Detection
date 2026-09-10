"""Participant/session manifest and train-only meal interval loading."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
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

    root = Path(raw_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"raw_root does not exist: {root}")
    records: list[RawFileRecord] = []
    for participant_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        participant_id = participant_dir.name
        if participant_id == "_UNMAPPED_" or (participant_id.lower() == "test" and not include_test):
            continue
        index_path = participant_dir / "index.csv"
        if not index_path.is_file():
            continue
        with index_path.open("r", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                folder_name = (row.get("folder_name") or "").strip()
                if not folder_name:
                    continue
                try:
                    start_ms = _timestamp(row["startTime"])
                    end_ms = _timestamp(row["endTime"])
                except (KeyError, TypeError, ValueError):
                    continue
                if end_ms <= start_ms:
                    continue
                session_dir = participant_dir / folder_name
                if not session_dir.is_dir():
                    continue
                for sensor_path in sorted(session_dir.glob("*.txt")):
                    records.append(
                        RawFileRecord(
                            participant_id=participant_id,
                            path=sensor_path,
                            session_folder=folder_name,
                            session_start_ms=start_ms,
                            session_end_ms=end_ms,
                        )
                    )
    return records


def events_for_record(
    record: RawFileRecord,
    meal_events: Mapping[str, tuple[EventInterval, ...]],
) -> tuple[EventInterval, ...]:
    return tuple(
        event
        for event in meal_events.get(record.participant_id, ())
        if event.start_ms < record.session_end_ms and event.end_ms > record.session_start_ms
    )

