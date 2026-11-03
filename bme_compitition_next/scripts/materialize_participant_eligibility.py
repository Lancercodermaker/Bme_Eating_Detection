"""Materialize a participant/event eligibility artifact from a completed audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from eating_event.coverage import (
    build_event_ledger_artifact,
    build_formal_eligibility,
    build_participant_eligibility_artifact,
)
from eating_event.data.manifest import ManifestAudit, RawFileRecord, load_meal_events


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _participant_ids_from_csv(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return {
            participant_id
            for row in csv.DictReader(stream)
            if (participant_id := (row.get("externalid") or "").strip())
            and participant_id.lower() != "test"
        }


def _records_from_audit(payload: Mapping[str, object]) -> tuple[RawFileRecord, ...]:
    rows = payload.get("manifest_records")
    if not isinstance(rows, list):
        raise ValueError("audit artifact lacks manifest_records")
    records: list[RawFileRecord] = []
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("path_or_file_id"):
            continue
        if not row.get("session_id"):
            continue
        try:
            records.append(
                RawFileRecord(
                    participant_id=str(row["participant_id"]),
                    path=Path(str(row["path_or_file_id"])),
                    session_folder=str(row["session_id"]),
                    session_start_ms=int(row["session_start_ms"]),
                    session_end_ms=int(row["session_end_ms"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("audit manifest record lacks valid file/session bounds") from exc
    return tuple(records)


def _source_fingerprint(record: RawFileRecord) -> str:
    stat = record.path.stat()
    return hashlib.sha256(
        "|".join([str(record.path), str(stat.st_size), str(stat.st_mtime_ns)]).encode("utf-8")
    ).hexdigest()


def _dense_window_counts_from_cache(
    cache_dir: Path,
    records: tuple[RawFileRecord, ...],
    meal_events: Mapping[str, tuple],
) -> dict[tuple[str, int], int]:
    """Read geometry only from candidate caches; labels are never trusted here."""

    cache_by_source: dict[str, Path] = {}
    for cache_path in sorted(cache_dir.glob("*.npz")):
        try:
            with np.load(cache_path, allow_pickle=True) as payload:
                metadata = json.loads(str(payload["metadata"].item()))
            source_fingerprint = str(metadata.get("source_fingerprint", ""))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if source_fingerprint:
            cache_by_source[source_fingerprint] = cache_path

    counts = {
        (participant, event_index): 0
        for participant, events in meal_events.items()
        for event_index, _ in enumerate(events)
    }
    processed_records = [record for record in records if record.path.exists()]
    for record in processed_records:
        cache_path = cache_by_source.get(_source_fingerprint(record))
        if cache_path is None:
            raise FileNotFoundError(f"candidate cache missing for processed record: {record.path}")
        with np.load(cache_path, allow_pickle=True) as payload:
            starts = payload["starts"].astype(np.int64, copy=False)
            ends = payload["ends"].astype(np.int64, copy=False)
        for event_index, event in enumerate(meal_events.get(record.participant_id, ())):
            counts[(record.participant_id, event_index)] += int(
                np.count_nonzero((starts < event.end_ms) & (ends > event.start_ms))
            )
    return counts


def materialize_participant_eligibility(
    audit_path: str | Path,
    meal_metadata_path: str | Path,
    output_path: str | Path,
    *,
    user_info_path: str | Path | None = None,
    sensor_index_path: str | Path | None = None,
    cache_dir: str | Path | None = None,
) -> dict[str, object]:
    """Build the event ledger from an existing audit and optional cache geometry."""

    audit_file = Path(audit_path).expanduser().resolve()
    meal_file = Path(meal_metadata_path).expanduser().resolve()
    payload = json.loads(audit_file.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("audit artifact must be a JSON object")
    records = _records_from_audit(payload)
    expected_count = int(payload.get("discovered_file_count", len(records)))
    if expected_count != len(records):
        raise ValueError(
            f"audit record count mismatch: discovered={expected_count}, manifest={len(records)}"
        )
    audit = ManifestAudit.from_dict(payload)
    eligibility = build_formal_eligibility(records, audit)
    meal_events = load_meal_events(meal_file)
    if cache_dir is None:
        report = build_participant_eligibility_artifact(
            eligibility,
            meal_events,
            records=records,
            source_audit_sha256=_sha256_file(audit_file),
        )
    else:
        dense_window_counts = _dense_window_counts_from_cache(
            Path(cache_dir).expanduser().resolve(), eligibility.eligible_records, meal_events
        )
        report = build_event_ledger_artifact(
            eligibility,
            meal_events,
            dense_window_counts=dense_window_counts,
            records=records,
            source_audit_sha256=_sha256_file(audit_file),
        )
    organized_raw_participants = set(eligibility.participant_session_eligibility)
    meal_participants = set(meal_events)
    sensor_participants = (
        _participant_ids_from_csv(Path(sensor_index_path).expanduser().resolve())
        if sensor_index_path is not None
        else set()
    )
    user_participants = (
        _participant_ids_from_csv(Path(user_info_path).expanduser().resolve())
        if user_info_path is not None
        else set()
    )
    source_union = organized_raw_participants | meal_participants | sensor_participants
    report["source_participant_reconciliation"] = {
        "user_profile_count": len(user_participants),
        "meal_metadata_count": len(meal_participants),
        "sensor_index_count": len(sensor_participants),
        "organized_raw_count": len(organized_raw_participants),
        "meal_metadata_only": sorted(meal_participants - organized_raw_participants),
        "organized_raw_only": sorted(organized_raw_participants - meal_participants),
        "sensor_index_only": sorted(sensor_participants - organized_raw_participants),
        "organized_raw_without_sensor_index": sorted(organized_raw_participants - sensor_participants)
        if sensor_index_path is not None
        else [],
        "user_profile_only": sorted(user_participants - source_union),
        "source_union_count": len(source_union),
        "source_intersection_raw_meal": len(organized_raw_participants & meal_participants),
    }
    report["source_audit_path"] = str(audit_file)
    report["meal_metadata_path"] = str(meal_file)
    if user_info_path is not None:
        report["user_info_path"] = str(Path(user_info_path).expanduser().resolve())
    if sensor_index_path is not None:
        report["sensor_index_path"] = str(Path(sensor_index_path).expanduser().resolve())
    if cache_dir is not None:
        report["representability_geometry_cache_dir"] = str(Path(cache_dir).expanduser().resolve())
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--meal-metadata", type=Path, required=True)
    parser.add_argument("--user-info", type=Path, default=None)
    parser.add_argument("--sensor-index", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = materialize_participant_eligibility(
        args.audit,
        args.meal_metadata,
        args.output,
        user_info_path=args.user_info,
        sensor_index_path=args.sensor_index,
        cache_dir=args.cache_dir,
    )
    print(
        json.dumps(
            {
                "result": "pass",
                "eligible_participant_count": report["eligible_participant_count"],
                "annotated_event_count": report.get("annotated_event_count", report["valid_event_count"]),
                "representable_event_count": report.get("representable_event_count"),
                "label_eligible_event_count": report.get("label_eligible_event_count"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
