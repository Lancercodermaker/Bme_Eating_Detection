"""Formal high-recall candidate coverage gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from eating_event.metrics import EventInterval, interval_iou
from eating_event.data.manifest import ManifestAudit, RawFileRecord
from eating_event.data.raw import RawFailureClassification, classify_raw_failure
from eating_event.data.contract import (
    ELIGIBILITY_SCHEMA_VERSION,
    SHORT_DURATION_THRESHOLD_SECONDS,
    eligibility_contract_identity,
)


G1_CANDIDATE_QUANTILE_GRID = (0.70, 0.80, 0.90)
G1_CANDIDATE_FUSE_GAP_MS = 300_000
G1_COVERAGE_THRESHOLD = 0.90


@dataclass(frozen=True)
class CoverageRunConfig:
    formal: bool = False
    max_files_per_participant: int | None = None
    outer_folds: int = 5
    selection_seed: int = 20260910

    def __post_init__(self) -> None:
        if self.formal and self.max_files_per_participant is not None:
            raise ValueError("formal coverage cannot use max-files-per-participant")
        if self.outer_folds < 2:
            raise ValueError("outer_folds must be at least 2")


@dataclass(frozen=True)
class QuantileResult:
    quantile: float
    pooled_recall: float
    worst_participant_recall: float
    candidate_count: int


@dataclass(frozen=True)
class FormalEligibility:
    """Auditable processed-only population for formal candidate coverage."""

    eligible_records: tuple[RawFileRecord, ...]
    discovered_count: int
    processed_count: int
    skipped_count: int
    skipped_reason_counts: Mapping[str, int]
    participant_session_eligibility: Mapping[str, Mapping[str, object]]
    ineligible_participants: tuple[str, ...]
    manifest_sha256: str
    denominator_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "discovered_count": self.discovered_count,
            "processed_count": self.processed_count,
            "skipped_count": self.skipped_count,
            "skipped_reason_counts": dict(self.skipped_reason_counts),
            "participant_session_eligibility": {
                participant: dict(details)
                for participant, details in self.participant_session_eligibility.items()
            },
            "ineligible_participants": list(self.ineligible_participants),
            "manifest_sha256": self.manifest_sha256,
            "denominator_sha256": self.denominator_sha256,
        }


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def apply_raw_failure_to_manifest(
    manifest_audit: ManifestAudit,
    record: RawFileRecord,
    error: BaseException,
) -> RawFailureClassification:
    """Record an approved raw skip and reject every unclassified failure."""

    classification = classify_raw_failure(error)
    if classification is None:
        raise RuntimeError(f"unexpected raw parser/runtime failure: {record.path}: {error}") from error
    manifest_audit.replace_file_status(
        record.path,
        status=classification.status,
        reason=classification.reason,
        parser_error=str(error),
    )
    return classification


def build_formal_eligibility(
    records: Sequence[RawFileRecord],
    manifest_audit: ManifestAudit,
) -> FormalEligibility:
    """Build the exact processed-only population and its audit digests."""

    manifest_audit.validate_unique_file_statuses()
    rows_by_path = {
        str(row["path_or_file_id"]): row
        for row in manifest_audit.records
        if row.get("path_or_file_id")
    }
    missing_paths = [str(record.path) for record in records if str(record.path) not in rows_by_path]
    if missing_paths:
        raise ValueError(f"manifest is missing discovered files: {missing_paths[:3]}")
    status_by_path = {path: str(row["status"]) for path, row in rows_by_path.items()}
    eligible_records = tuple(record for record in records if status_by_path[str(record.path)] == "processed")
    skipped_rows = [
        row
        for row in rows_by_path.values()
        if str(row["status"]).startswith("skipped_")
    ]
    skipped_reason_counts: dict[str, int] = {}
    for row in skipped_rows:
        reason = str(row.get("reason") or "unspecified")
        skipped_reason_counts[reason] = skipped_reason_counts.get(reason, 0) + 1

    participant_sessions: dict[str, dict[str, set[str]]] = {}
    for record in records:
        if record.participant_id.lower() == "test":
            continue
        details = participant_sessions.setdefault(
            record.participant_id,
            {"discovered": set(), "processed": set(), "skipped": set()},
        )
        details["discovered"].add(record.session_folder)
        if status_by_path[str(record.path)] == "processed":
            details["processed"].add(record.session_folder)
        else:
            details["skipped"].add(record.session_folder)

    participant_session_eligibility: dict[str, Mapping[str, object]] = {}
    for participant in sorted(participant_sessions):
        details = participant_sessions[participant]
        participant_session_eligibility[participant] = {
            "discovered_session_count": len(details["discovered"]),
            "processed_session_count": len(details["processed"]),
            "skipped_session_count": len(details["skipped"]),
            "discovered_sessions": sorted(details["discovered"]),
            "processed_sessions": sorted(details["processed"]),
            "skipped_sessions": sorted(details["skipped"]),
            "eligible": bool(details["processed"]),
        }
    ineligible_participants = tuple(
        participant
        for participant, details in participant_session_eligibility.items()
        if not bool(details["eligible"])
    )
    canonical_manifest = sorted(
        (dict(row) for row in manifest_audit.records),
        key=lambda row: (
            str(row.get("participant_id", "")),
            str(row.get("session_id", "")),
            str(row.get("path_or_file_id", "")),
        ),
    )
    canonical_denominator = [
        {
            "participant_id": record.participant_id,
            "session_id": record.session_folder,
            "path": str(record.path),
        }
        for record in sorted(
            eligible_records,
            key=lambda item: (item.participant_id, item.session_folder, str(item.path)),
        )
    ]
    return FormalEligibility(
        eligible_records=eligible_records,
        discovered_count=len(records),
        processed_count=len(eligible_records),
        skipped_count=len(skipped_rows),
        skipped_reason_counts=dict(sorted(skipped_reason_counts.items())),
        participant_session_eligibility=participant_session_eligibility,
        ineligible_participants=ineligible_participants,
        manifest_sha256=_canonical_sha256(canonical_manifest),
        denominator_sha256=_canonical_sha256(canonical_denominator),
    )


def build_participant_eligibility_artifact(
    eligibility: FormalEligibility,
    meal_events: Mapping[str, Sequence[EventInterval]],
    *,
    records: Sequence[RawFileRecord] | None = None,
    source_audit_sha256: str | None = None,
) -> dict[str, object]:
    """Materialize participant and event eligibility without reading raw data."""

    session_participants = set(eligibility.participant_session_eligibility)
    event_participants = {str(participant) for participant in meal_events}
    raw_records = tuple(records) if records is not None else eligibility.eligible_records
    processed_paths = {str(record.path) for record in eligibility.eligible_records}
    sessions: dict[tuple[str, str], dict[str, object]] = {}
    for record in raw_records:
        key = (record.participant_id, record.session_folder)
        session = sessions.setdefault(
            key,
            {
                "start_ms": record.session_start_ms,
                "end_ms": record.session_end_ms,
                "processed": False,
            },
        )
        session["processed"] = bool(session["processed"]) or str(record.path) in processed_paths

    event_rows: list[dict[str, object]] = []
    event_exclusion_reason_counts: dict[str, int] = {}
    event_counts_by_participant: dict[str, dict[str, int]] = {}
    for participant in sorted(event_participants):
        for event_index, event in enumerate(meal_events[participant]):
            participant_sessions = [
                session
                for (session_participant, _), session in sessions.items()
                if session_participant == participant
            ]
            overlaps = [
                session
                for session in participant_sessions
                if event.start_ms < int(session["end_ms"])
                and event.end_ms > int(session["start_ms"])
            ]
            processed_overlaps = [session for session in overlaps if bool(session["processed"])]
            if processed_overlaps:
                status = "usable_processed_overlap"
            elif not participant_sessions:
                status = "metadata_only_no_session"
            elif overlaps:
                status = "overlap_only_invalid_sensor"
            else:
                status = "no_index_session_overlap"
            event_rows.append(
                {
                    "participant_id": participant,
                    "event_index": event_index,
                    "start_ms": event.start_ms,
                    "end_ms": event.end_ms,
                    "status": status,
                    "overlapping_session_count": len(overlaps),
                    "processed_overlap_count": len(processed_overlaps),
                }
            )
            counts = event_counts_by_participant.setdefault(participant, {})
            counts[status] = counts.get(status, 0) + 1
            if status != "usable_processed_overlap":
                event_exclusion_reason_counts[status] = event_exclusion_reason_counts.get(status, 0) + 1

    participant_rows: dict[str, dict[str, object]] = {}
    valid_event_count = 0
    excluded_event_count = 0
    all_participants = sorted(session_participants | event_participants)
    for participant in all_participants:
        details = eligibility.participant_session_eligibility.get(
            participant,
            {
                "discovered_session_count": 0,
                "processed_session_count": 0,
                "skipped_session_count": 0,
                "discovered_sessions": [],
                "processed_sessions": [],
                "skipped_sessions": [],
                "eligible": False,
            },
        )
        event_count = len(tuple(meal_events.get(participant, ())))
        is_eligible = bool(details.get("eligible"))
        participant_status = (
            "eligible"
            if is_eligible
            else (
                "ineligible_no_processed_session"
                if participant in session_participants
                else "ineligible_no_raw_session"
            )
        )
        valid_event_count += event_count
        counts = event_counts_by_participant.get(participant, {})
        excluded_count = event_count - counts.get("usable_processed_overlap", 0)
        excluded_event_count += excluded_count
        participant_rows[participant] = {
            **dict(details),
            "participant_status": participant_status,
            "valid_event_count": event_count,
            "excluded_event_count": excluded_count,
            "event_status_counts": dict(sorted(counts.items())),
        }

    payload: dict[str, object] = {
        "schema_version": "participant_eligibility_v2",
        "discovered_file_count": eligibility.discovered_count,
        "processed_file_count": eligibility.processed_count,
        "skipped_file_count": eligibility.skipped_count,
        "skipped_reason_counts": dict(eligibility.skipped_reason_counts),
        "target_train_participant_count": len(all_participants),
        "raw_target_train_participant_count": len(session_participants),
        "meal_metadata_participant_count": len(event_participants),
        "participant_intersection_count": len(session_participants & event_participants),
        "eligible_participant_count": sum(
            1 for details in participant_rows.values() if details["participant_status"] == "eligible"
        ),
        "ineligible_participants": [
            participant
            for participant, details in participant_rows.items()
            if details["participant_status"] != "eligible"
        ],
        "valid_event_count": valid_event_count,
        "excluded_event_count": excluded_event_count,
        "effective_valid_event_count": valid_event_count - excluded_event_count,
        "event_exclusion_reason_counts": dict(sorted(event_exclusion_reason_counts.items())),
        "event_denominator_sha256": _canonical_sha256(
            [row for row in event_rows if row["status"] == "usable_processed_overlap"]
        ),
        "event_eligibility": event_rows,
        "participant_eligibility": participant_rows,
        "manifest_sha256": eligibility.manifest_sha256,
        "denominator_sha256": eligibility.denominator_sha256,
    }
    if source_audit_sha256 is not None:
        payload["source_audit_sha256"] = source_audit_sha256
    return payload


def validate_participant_eligibility_artifact(
    actual: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    """Reject a stale or drifted participant/event eligibility contract."""

    if actual.get("schema_version") != "participant_eligibility_v2":
        raise ValueError("eligibility artifact schema must be participant_eligibility_v2")
    contract_fields = (
        "discovered_file_count",
        "processed_file_count",
        "skipped_file_count",
        "skipped_reason_counts",
        "target_train_participant_count",
        "raw_target_train_participant_count",
        "meal_metadata_participant_count",
        "participant_intersection_count",
        "eligible_participant_count",
        "ineligible_participants",
        "valid_event_count",
        "excluded_event_count",
        "effective_valid_event_count",
        "event_exclusion_reason_counts",
        "event_denominator_sha256",
        "manifest_sha256",
        "denominator_sha256",
        "event_eligibility",
        "participant_eligibility",
    )
    for field in contract_fields:
        if actual.get(field) != expected.get(field):
            raise ValueError(f"eligibility artifact mismatch: {field}")
    if "source_audit_sha256" in expected and actual.get("source_audit_sha256") != expected.get(
        "source_audit_sha256"
    ):
        raise ValueError("eligibility artifact mismatch: source_audit_sha256")


def build_event_ledger_artifact(
    eligibility: FormalEligibility,
    meal_events: Mapping[str, Sequence[EventInterval]],
    *,
    dense_window_counts: Mapping[tuple[str, int], int],
    records: Sequence[RawFileRecord] | None = None,
    source_audit_sha256: str | None = None,
) -> dict[str, object]:
    """Build the approved orthogonal annotated-event ledger.

    The ledger intentionally retains every parsed annotation.  Sensor support,
    candidate-window representability, annotation quality, and training
    eligibility are separate dimensions so downstream exclusions cannot make
    an annotation disappear from the audit denominator.
    """

    session_participants = set(eligibility.participant_session_eligibility)
    event_participants = {str(participant) for participant in meal_events}
    raw_records = tuple(records) if records is not None else eligibility.eligible_records
    processed_paths = {str(record.path) for record in eligibility.eligible_records}
    sessions: dict[tuple[str, str], dict[str, object]] = {}
    for record in raw_records:
        key = (record.participant_id, record.session_folder)
        session = sessions.setdefault(
            key,
            {
                "start_ms": record.session_start_ms,
                "end_ms": record.session_end_ms,
                "processed": False,
            },
        )
        session["processed"] = bool(session["processed"]) or str(record.path) in processed_paths

    expected_dense_keys = {
        (participant, event_index)
        for participant, events in meal_events.items()
        for event_index, _ in enumerate(events)
    }
    missing_dense_keys = sorted(expected_dense_keys - set(dense_window_counts))
    if missing_dense_keys:
        raise ValueError(
            "dense-window support map is incomplete; missing event keys "
            f"{missing_dense_keys[:3]}"
        )
    unexpected_dense_keys = sorted(set(dense_window_counts) - expected_dense_keys)
    if unexpected_dense_keys:
        raise ValueError(f"dense-window support map has unexpected event keys {unexpected_dense_keys[:3]}")

    event_rows: list[dict[str, object]] = []
    reason_counts: dict[str, int] = {}
    participant_counts: dict[str, dict[str, int]] = {}
    for participant in sorted(event_participants):
        participant_sessions = [
            session
            for (session_participant, _), session in sessions.items()
            if session_participant == participant
        ]
        for event_index, event in enumerate(meal_events[participant]):
            overlaps = [
                session
                for session in participant_sessions
                if event.start_ms < int(session["end_ms"])
                and event.end_ms > int(session["start_ms"])
            ]
            processed_overlaps = [session for session in overlaps if bool(session["processed"])]
            if processed_overlaps:
                sensor_status = "sensor_backed"
            elif not participant_sessions:
                sensor_status = "metadata_only"
            elif overlaps:
                sensor_status = "overlap_only_invalid_sensor"
            else:
                sensor_status = "no_index_session_overlap"

            dense_count = int(dense_window_counts[(participant, event_index)])
            if dense_count < 0:
                raise ValueError("dense-window support counts must be non-negative")
            representable = sensor_status == "sensor_backed" and dense_count > 0
            representability_status = "representable" if representable else "unrepresentable"
            if sensor_status == "metadata_only":
                unrepresentable_reason = "METADATA_ONLY_NO_SESSION"
            elif sensor_status == "no_index_session_overlap":
                unrepresentable_reason = "NO_INDEX_SESSION_OVERLAP"
            elif sensor_status == "overlap_only_invalid_sensor":
                unrepresentable_reason = "OVERLAP_ONLY_INVALID_SENSOR"
            elif not representable:
                unrepresentable_reason = "NO_DENSE_WINDOW_SUPPORT"
            else:
                unrepresentable_reason = None

            annotation_quality_status = (
                "SHORT_DURATION_SUSPECT"
                if (event.end_ms - event.start_ms) < int(round(SHORT_DURATION_THRESHOLD_SECONDS * 1000))
                else "accepted"
            )
            training_eligible = representable and annotation_quality_status == "accepted"
            if unrepresentable_reason is not None:
                exclusion_reason = unrepresentable_reason
            elif annotation_quality_status != "accepted":
                exclusion_reason = annotation_quality_status
            else:
                exclusion_reason = None
            row = {
                "participant_id": participant,
                "event_index": event_index,
                "annotation_status": "annotated",
                "sensor_status": sensor_status,
                "representability_status": representability_status,
                "unrepresentable_reason": unrepresentable_reason,
                "annotation_quality_status": annotation_quality_status,
                "training_eligibility": training_eligible,
                "evaluation_eligibility": training_eligible,
                "exclusion_reason": exclusion_reason,
                "start_ms": event.start_ms,
                "end_ms": event.end_ms,
                "duration_ms": event.end_ms - event.start_ms,
                "dense_window_count": dense_count,
                "overlapping_session_count": len(overlaps),
                "processed_overlap_count": len(processed_overlaps),
            }
            event_rows.append(row)
            counts = participant_counts.setdefault(participant, {})
            for key, value in (
                ("annotation_count", 1),
                (f"sensor_status:{sensor_status}", 1),
                (f"representability_status:{representability_status}", 1),
                (f"annotation_quality_status:{annotation_quality_status}", 1),
                ("training_eligible_count", int(training_eligible)),
            ):
                counts[key] = counts.get(key, 0) + value
            if unrepresentable_reason is not None:
                reason_counts[unrepresentable_reason] = reason_counts.get(unrepresentable_reason, 0) + 1
            if exclusion_reason is not None:
                reason_counts[f"EXCLUSION:{exclusion_reason}"] = reason_counts.get(
                    f"EXCLUSION:{exclusion_reason}", 0
                ) + 1

    all_participants = sorted(session_participants | event_participants)
    participant_rows: dict[str, dict[str, object]] = {}
    for participant in all_participants:
        details = eligibility.participant_session_eligibility.get(
            participant,
            {
                "discovered_session_count": 0,
                "processed_session_count": 0,
                "skipped_session_count": 0,
                "discovered_sessions": [],
                "processed_sessions": [],
                "skipped_sessions": [],
                "eligible": False,
            },
        )
        rows = [row for row in event_rows if row["participant_id"] == participant]
        counts = participant_counts.get(participant, {})
        participant_rows[participant] = {
            **dict(details),
            "participant_status": "eligible" if bool(details.get("eligible")) else "ineligible",
            "annotated_event_count": len(rows),
            "sensor_backed_event_count": sum(row["sensor_status"] == "sensor_backed" for row in rows),
            "representable_event_count": sum(row["representability_status"] == "representable" for row in rows),
            "label_eligible_event_count": sum(bool(row["training_eligibility"]) for row in rows),
            "event_status_counts": dict(sorted(counts.items())),
        }

    identity_version, identity_hash = eligibility_contract_identity()
    annotated_rows = list(event_rows)
    sensor_rows = [row for row in event_rows if row["sensor_status"] == "sensor_backed"]
    representable_rows = [row for row in event_rows if row["representability_status"] == "representable"]
    label_rows = [row for row in event_rows if bool(row["training_eligibility"])]
    payload: dict[str, object] = {
        "schema_version": ELIGIBILITY_SCHEMA_VERSION,
        "eligibility_contract_version": identity_version,
        "eligibility_contract_hash": identity_hash,
        "event_ledger_complete": True,
        "discovered_file_count": eligibility.discovered_count,
        "processed_file_count": eligibility.processed_count,
        "skipped_file_count": eligibility.skipped_count,
        "skipped_reason_counts": dict(eligibility.skipped_reason_counts),
        "target_train_participant_count": len(all_participants),
        "raw_target_train_participant_count": len(session_participants),
        "meal_metadata_participant_count": len(event_participants),
        "participant_intersection_count": len(session_participants & event_participants),
        "eligible_participant_count": sum(
            1 for details in participant_rows.values() if details["participant_status"] == "eligible"
        ),
        "ineligible_participants": [
            participant
            for participant, details in participant_rows.items()
            if details["participant_status"] != "eligible"
        ],
        "annotated_event_count": len(annotated_rows),
        "sensor_backed_event_count": len(sensor_rows),
        "representable_event_count": len(representable_rows),
        "unrepresentable_event_count": len(event_rows) - len(representable_rows),
        "label_eligible_event_count": len(label_rows),
        "valid_event_count": len(annotated_rows),
        "excluded_event_count": len(annotated_rows) - len(label_rows),
        "effective_valid_event_count": len(label_rows),
        "unrepresentable_reason_counts": {
            reason: count
            for reason, count in sorted(reason_counts.items())
            if not reason.startswith("EXCLUSION:")
        },
        "exclusion_reason_counts": {
            reason.removeprefix("EXCLUSION:"): count
            for reason, count in sorted(reason_counts.items())
            if reason.startswith("EXCLUSION:")
        },
        "annotated_event_denominator_sha256": _canonical_sha256(annotated_rows),
        "sensor_backed_event_denominator_sha256": _canonical_sha256(sensor_rows),
        "representable_event_denominator_sha256": _canonical_sha256(representable_rows),
        "label_eligible_event_denominator_sha256": _canonical_sha256(label_rows),
        "event_denominator_sha256": _canonical_sha256(label_rows),
        "event_eligibility": event_rows,
        "participant_eligibility": participant_rows,
        "manifest_sha256": eligibility.manifest_sha256,
        "denominator_sha256": eligibility.denominator_sha256,
    }
    if source_audit_sha256 is not None:
        payload["source_audit_sha256"] = source_audit_sha256
    return payload


def validate_event_ledger_artifact(
    actual: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    """Fail closed when the approved v3 event ledger drifts."""

    if actual.get("schema_version") != ELIGIBILITY_SCHEMA_VERSION:
        raise ValueError(f"eligibility artifact schema must be {ELIGIBILITY_SCHEMA_VERSION}")
    fields = (
        "eligibility_contract_version",
        "eligibility_contract_hash",
        "event_ledger_complete",
        "annotated_event_count",
        "sensor_backed_event_count",
        "representable_event_count",
        "unrepresentable_event_count",
        "label_eligible_event_count",
        "valid_event_count",
        "excluded_event_count",
        "effective_valid_event_count",
        "unrepresentable_reason_counts",
        "exclusion_reason_counts",
        "annotated_event_denominator_sha256",
        "sensor_backed_event_denominator_sha256",
        "representable_event_denominator_sha256",
        "label_eligible_event_denominator_sha256",
        "event_denominator_sha256",
        "event_eligibility",
        "participant_eligibility",
        "manifest_sha256",
        "denominator_sha256",
    )
    for field in fields:
        if actual.get(field) != expected.get(field):
            raise ValueError(f"eligibility artifact mismatch: {field}")
    if "source_audit_sha256" in expected and actual.get("source_audit_sha256") != expected.get(
        "source_audit_sha256"
    ):
        raise ValueError("eligibility artifact mismatch: source_audit_sha256")
    required_row_fields = {
        "annotation_status",
        "sensor_status",
        "representability_status",
        "unrepresentable_reason",
        "annotation_quality_status",
        "training_eligibility",
        "exclusion_reason",
    }
    for row in actual.get("event_eligibility", []):
        if not required_row_fields.issubset(row):
            raise ValueError("eligibility artifact event row lacks orthogonal status fields")
        if row["representability_status"] == "unrepresentable" and not row["unrepresentable_reason"]:
            raise ValueError("unrepresentable event lacks unrepresentable_reason")
        if row["representability_status"] == "representable" and row["unrepresentable_reason"]:
            raise ValueError("representable event cannot have unrepresentable_reason")
        if not row["training_eligibility"] and not row["exclusion_reason"]:
            raise ValueError("excluded event lacks exclusion_reason")
        if row["exclusion_reason"] and row["training_eligibility"]:
            raise ValueError("training-eligible event cannot have exclusion_reason")


def deduplicate_event_intervals(intervals: Sequence[EventInterval]) -> tuple[EventInterval, ...]:
    """Keep first-seen event intervals once per participant evaluation."""

    seen: set[tuple[int, int]] = set()
    result: list[EventInterval] = []
    for interval in intervals:
        key = (interval.start_ms, interval.end_ms)
        if key in seen:
            continue
        seen.add(key)
        result.append(interval)
    return tuple(result)


def cache_manifest_sha256(entries: Sequence[Mapping[str, object]]) -> str:
    """Hash the sorted cache provenance entries used by formal G1."""

    canonical = sorted(
        (dict(entry) for entry in entries),
        key=lambda entry: (str(entry.get("participant_id", "")), str(entry.get("session_id", "")), str(entry.get("path", ""))),
    )
    return _canonical_sha256(canonical)


def formal_gate_passes(
    fold_results: Sequence["FoldCoverageResult"],
    *,
    unexpected_failures: Sequence[str],
) -> bool:
    return bool(fold_results) and all(
        result.pooled_recall >= G1_COVERAGE_THRESHOLD for result in fold_results
    ) and not unexpected_failures


def select_candidate_quantile(results: Sequence[QuantileResult]) -> QuantileResult:
    if not results:
        raise ValueError("candidate quantile selection needs results")
    if any(result.quantile not in G1_CANDIDATE_QUANTILE_GRID for result in results):
        raise ValueError("candidate quantile is outside the frozen G1 grid")
    return max(
        results,
        key=lambda result: (
            result.pooled_recall,
            result.worst_participant_recall,
            -result.candidate_count,
            result.quantile,
        ),
    )


@dataclass(frozen=True)
class FoldCoverageResult:
    fold_id: str
    pooled_recall: float
    participant_recall: Mapping[str, float]
    selected_quantile: float | None = None
    candidate_count: int = 0


@dataclass(frozen=True)
class CandidateCoverageReport:
    gate_id: str
    fold_results: tuple[FoldCoverageResult, ...]
    result: str = "pass"
    failure_class: str | None = None
    eligibility: FormalEligibility | None = None
    cache_manifest_sha256: str | None = None
    event_denominator_sha256: str | None = None
    effective_valid_event_count: int | None = None
    eligibility_artifact_sha256: str | None = None
    cache_provenance: Mapping[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "gate_id": self.gate_id,
            "result": self.result,
            "failure_class": self.failure_class,
            "fold_results": [asdict(result) for result in self.fold_results],
        }
        if self.eligibility is not None:
            payload["eligibility"] = self.eligibility.to_dict()
        if self.cache_manifest_sha256 is not None:
            payload["cache_manifest_sha256"] = self.cache_manifest_sha256
        if self.event_denominator_sha256 is not None:
            payload["event_denominator_sha256"] = self.event_denominator_sha256
        if self.effective_valid_event_count is not None:
            payload["effective_valid_event_count"] = self.effective_valid_event_count
        if self.eligibility_artifact_sha256 is not None:
            payload["eligibility_artifact_sha256"] = self.eligibility_artifact_sha256
        if self.cache_provenance is not None:
            payload["cache_provenance"] = dict(self.cache_provenance)
        return payload


def _truth_covered(predictions: Sequence[EventInterval], truths: Sequence[EventInterval]) -> tuple[int, int]:
    covered = sum(1 for truth in truths if any(interval_iou(prediction, truth) > 0.25 for prediction in predictions))
    return covered, len(truths)


def evaluate_candidate_coverage(
    predictions_by_participant: Mapping[str, Sequence[EventInterval]],
    truths_by_participant: Mapping[str, Sequence[EventInterval]],
) -> tuple[float, dict[str, float]]:
    participant_recall: dict[str, float] = {}
    total_covered = 0
    total_truths = 0
    for participant in sorted(truths_by_participant):
        covered, truth_count = _truth_covered(
            predictions_by_participant.get(participant, ()),
            truths_by_participant[participant],
        )
        participant_recall[participant] = covered / truth_count if truth_count else 1.0
        total_covered += covered
        total_truths += truth_count
    pooled = total_covered / total_truths if total_truths else 1.0
    return pooled, participant_recall


def write_coverage_reports(
    report: CandidateCoverageReport,
    *,
    output: str | Path,
    by_fold: str | Path,
    by_participant: str | Path,
) -> None:
    payload = report.to_dict()
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(by_fold).expanduser().resolve().write_text(
        json.dumps(payload["fold_results"], indent=2), encoding="utf-8"
    )
    participant_rows = []
    for fold in report.fold_results:
        for participant, recall in fold.participant_recall.items():
            participant_rows.append({"fold_id": fold.fold_id, "participant_id": participant, "recall": recall})
    Path(by_participant).expanduser().resolve().write_text(
        json.dumps(participant_rows, indent=2), encoding="utf-8"
    )
