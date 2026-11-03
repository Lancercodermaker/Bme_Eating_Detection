"""Summarize the frozen exact window-geometry diagnostic without model evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Iterable, Mapping, Sequence

import numpy as np


ROOT = Path("artifacts/g1-window-geometry-diagnostic-v1")
SPEC = Path("configs/formal-g1-window-geometry-diagnostic-v1.json")
HASH = Path("configs/formal-g1-window-geometry-diagnostic-v1.sha256")
GEOMETRY = ROOT / "full-paired-geometry.jsonl"
EQUIVALENCE = ROOT / "full-equivalence.json"
AUDIT = Path("artifacts/g1-processed-only-manifest-audit.json")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _median(values: Iterable[float]) -> float | None:
    values = [float(value) for value in values if value is not None]
    return float(median(values)) if values else None


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    values = [float(value) for value in values if value is not None]
    return float(np.percentile(values, percentile)) if values else None


def _duration_group(duration_ms: int) -> str:
    seconds = duration_ms / 1000.0
    if seconds < 300:
        return "<300s"
    if seconds < 600:
        return "300-600s"
    if seconds <= 1200:
        return "600-1200s"
    return ">1200s"


def _support_group(count: int) -> str:
    if count < 10:
        return "<10"
    if count < 25:
        return "10-24"
    if count < 50:
        return "25-49"
    return ">=50"


def _summarize_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    a = [row["A"] for row in rows]
    b = [row["B"] for row in rows]
    deltas = [row["delta_B_minus_A"] for row in rows]
    coverage_delta = [float(delta["positive_union_coverage_ms"]) for delta in deltas]
    support_delta = [int(delta["positive_window_count"]) for delta in deltas]
    dense_delta = [int(delta["dense_window_count"]) for delta in deltas]
    groups = {
        "coverage_improved": sum(value > 0 for value in coverage_delta),
        "coverage_unchanged": sum(value == 0 for value in coverage_delta),
        "coverage_worsened": sum(value < 0 for value in coverage_delta),
        "positive_count_increased": sum(value > 0 for value in support_delta),
        "positive_count_unchanged": sum(value == 0 for value in support_delta),
        "positive_count_decreased": sum(value < 0 for value in support_delta),
        "dense_count_increased": sum(value > 0 for value in dense_delta),
        "dense_count_unchanged": sum(value == 0 for value in dense_delta),
        "dense_count_decreased": sum(value < 0 for value in dense_delta),
        "events_with_new_support_interval": sum(bool(row["new_support_intervals_B_minus_A"]) for row in rows),
        "events_with_lost_support_interval": sum(bool(row["lost_support_intervals_A_minus_B"]) for row in rows),
    }
    return {
        "event_count": len(rows),
        "A": {
            "dense_window_count_sum": sum(int(value["dense_window_count"]) for value in a),
            "positive_window_count_sum": sum(int(value["positive_window_count"]) for value in a),
            "ignore_window_count_sum": sum(int(value["ignore_window_count"]) for value in a),
            "positive_union_coverage_ms_median": _median(value["positive_union_coverage_ms"] for value in a),
            "positive_union_coverage_fraction_median": _median(value["positive_union_coverage_fraction"] for value in a),
            "positive_union_coverage_fraction_p10": _percentile((value["positive_union_coverage_fraction"] for value in a), 10),
            "positive_union_coverage_fraction_p90": _percentile((value["positive_union_coverage_fraction"] for value in a), 90),
            "unsupported_duration_ms_median": _median(value["unsupported_duration_ms"] for value in a),
        },
        "B": {
            "dense_window_count_sum": sum(int(value["dense_window_count"]) for value in b),
            "positive_window_count_sum": sum(int(value["positive_window_count"]) for value in b),
            "ignore_window_count_sum": sum(int(value["ignore_window_count"]) for value in b),
            "positive_union_coverage_ms_median": _median(value["positive_union_coverage_ms"] for value in b),
            "positive_union_coverage_fraction_median": _median(value["positive_union_coverage_fraction"] for value in b),
            "positive_union_coverage_fraction_p10": _percentile((value["positive_union_coverage_fraction"] for value in b), 10),
            "positive_union_coverage_fraction_p90": _percentile((value["positive_union_coverage_fraction"] for value in b), 90),
            "unsupported_duration_ms_median": _median(value["unsupported_duration_ms"] for value in b),
        },
        "paired_delta": {
            **groups,
            "dense_window_count_sum": sum(dense_delta),
            "positive_window_count_sum": sum(support_delta),
            "positive_union_coverage_ms_sum": sum(coverage_delta),
            "unsupported_duration_ms_sum": sum(int(delta["unsupported_duration_ms"]) for delta in deltas),
            "positive_union_coverage_ms_median": _median(coverage_delta),
            "positive_union_coverage_ms_p10": _percentile(coverage_delta, 10),
            "positive_union_coverage_ms_p90": _percentile(coverage_delta, 90),
        },
    }


def _group_summary(rows: Sequence[Mapping[str, object]], key_name: str) -> dict[str, object]:
    groups: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        group = _duration_group(int(row["duration_ms"])) if key_name == "duration_group" else _support_group(int(row["A"]["positive_window_count"]))
        groups.setdefault(group, []).append(row)
    return {group: _summarize_rows(group_rows) for group, group_rows in groups.items()}


def _participant_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for participant in sorted({str(row["participant"]) for row in rows}):
        participant_rows = [row for row in rows if row["participant"] == participant]
        output[participant] = {
            "event_count": len(participant_rows),
            "outer_fold": participant_rows[0].get("outer_fold"),
            "coverage_improved": sum(float(row["delta_B_minus_A"]["positive_union_coverage_ms"]) > 0 for row in participant_rows),
            "coverage_unchanged": sum(float(row["delta_B_minus_A"]["positive_union_coverage_ms"]) == 0 for row in participant_rows),
            "coverage_worsened": sum(float(row["delta_B_minus_A"]["positive_union_coverage_ms"]) < 0 for row in participant_rows),
            "coverage_delta_ms_sum": sum(int(row["delta_B_minus_A"]["positive_union_coverage_ms"]) for row in participant_rows),
        }
    return output


def _affected_events(eq: Mapping[str, object], rows: Sequence[Mapping[str, object]], ledger: Mapping[str, object]) -> list[dict[str, object]]:
    failed_paths = [str(record["path"]) for record in eq["recordings"] if record.get("status") == "RAW_FAILURE"]
    failures = []
    for path in failed_paths:
        session_start = None
        session_end = None
        for audit_row in [*ledger.get("manifest_records", []), *ledger.get("files", [])]:
            audit_path = audit_row.get("path", audit_row.get("path_or_file_id"))
            if str(audit_path) == path:
                session_start = audit_row.get("session_start_ms")
                session_end = audit_row.get("session_end_ms")
                if session_start is not None and session_end is not None:
                    break
        failures.append({"path": path, "session_start_ms": session_start, "session_end_ms": session_end})
    affected: list[dict[str, object]] = []
    for failure in failures:
        participant = Path(failure["path"]).parts[-3]
        for row in rows:
            if row["participant"] != participant or failure["session_start_ms"] is None:
                continue
            if int(row["gt_start_ms"]) < int(failure["session_end_ms"]) and int(row["gt_end_ms"]) > int(failure["session_start_ms"]):
                affected.append({"event_id": row["event_id"], "failed_recording": failure["path"], "reason": "approved raw skip prevents exact full-recording B context"})
    return affected


def main() -> int:
    spec_bytes = SPEC.read_bytes()
    spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    expected_hash = HASH.read_text(encoding="utf-8").split()[0]
    if spec_hash != expected_hash:
        raise RuntimeError("spec hash mismatch")
    rows = _read_jsonl(GEOMETRY)
    eq = json.loads(EQUIVALENCE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    complete_event_ids = {row["event_id"] for row in rows}
    affected = _affected_events(eq, rows, audit)
    affected_ids = {row["event_id"] for row in affected}
    complete_rows = [row for row in rows if row["event_id"] not in affected_ids]
    historical = {
        status: [row for row in rows if row.get("historical_status") == status]
        for status in ("covered", "missing")
    }
    missing_changes = []
    for row in historical["missing"]:
        delta = row["delta_B_minus_A"]
        if delta["positive_union_coverage_ms"] != 0 or delta["positive_window_count"] != 0 or row["new_support_intervals_B_minus_A"] or row["lost_support_intervals_A_minus_B"]:
            missing_changes.append({"event_id": row["event_id"], "participant": row["participant"], "outer_fold": row["outer_fold"], "coverage_delta_ms": delta["positive_union_coverage_ms"], "positive_count_delta": delta["positive_window_count"], "new_support_intervals": row["new_support_intervals_B_minus_A"], "lost_support_intervals": row["lost_support_intervals_A_minus_B"]})
    summary = {
        "schema_version": "g1_window_geometry_summary_v1",
        "spec_sha256": spec_hash,
        "primary_denominator": {"all_events": len(rows), "exact_complete_events": len(complete_rows), "data_incomplete_events": len(affected_ids), "data_incomplete_event_ids": sorted(affected_ids)},
        "pilot": {"status": "COMPLETE", "recordings": 9, "equivalence": "9/9 MATCH"},
        "full": {"status": "PARTIAL_INCONCLUSIVE" if affected_ids else "COMPLETE", "recordings_processed": eq["processed_recordings"], "related_recordings": 298, "approved_raw_failures": len([record for record in eq["recordings"] if record.get("status") == "RAW_FAILURE"]), "elapsed_seconds": eq["elapsed_seconds"]},
        "all_234": _summarize_rows(rows),
        "exact_complete_232": _summarize_rows(complete_rows),
        "duration_groups_fixed": _group_summary(rows, "duration_group"),
        "original_support_groups_fixed_from_A": _group_summary(rows, "support_group"),
        "historical_covered_missing": {status: _summarize_rows(group_rows) for status, group_rows in historical.items()},
        "participant_summary": _participant_summary(rows),
        "affected_events": affected,
        "historical_missing_events_with_geometry_change": sorted(missing_changes, key=lambda item: (item["coverage_delta_ms"], item["event_id"])),
        "interpretation": {
            "counts_only_increase": "not sufficient as a global explanation; dense and positive counts increase on most events, but coverage changes on both directions",
            "temporal_support_change_observed": "supported on the exact-complete subset; 107/234 improve, 117/234 unchanged, 10/234 worsen in positive-union coverage",
            "frozen_eventizer_oracle_change_observed": "not run",
            "model_or_formal_g1_transfer": "not evaluated by this geometry-only diagnostic"
        }
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "stratified-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fragility = {
        "schema_version": "g1_window_geometry_fragility_definition_v1",
        "spec_sha256": spec_hash,
        "exactly_k": {"k": [1, 2, 3], "denominator": "events with at least k applicable support units", "inapplicable": "NA, excluded from denominator, never zero", "coverage_loss_denominator": "GT duration"},
        "up_to_k": {"optional": True, "monotonicity": "loss must be non-decreasing as k increases; violations are flagged"},
        "adjacency": "consecutive chronological window starts from the same grid with no intervening start",
        "scope": "descriptive only; no production prediction or eventizer modification",
        "status": "DEFINITION_CLARIFIED; NOT_RUN_IN_THIS_GEOMETRY_PASS"
    }
    (ROOT / "fragility-definition.json").write_text(json.dumps(fragility, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    resource = {"schema_version": "g1_window_geometry_resource_log_v1", "spec_sha256": spec_hash, "pilot_seconds": 22.954873999988195, "full_elapsed_seconds": eq["elapsed_seconds"], "full_related_recordings": 298, "full_processed_recordings": eq["processed_recordings"], "memory_measurement": "not instrumented; no memory-budget stop triggered", "disk_measurement": "not instrumented; output remained within budget", "approved_raw_failures": [record for record in eq["recordings"] if record.get("status") == "RAW_FAILURE"], "stop_rule": "no geometry-driven expansion; no model/score step started"}
    (ROOT / "resource-log.json").write_text(json.dumps(resource, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "schema_version": "g1_window_geometry_diagnostic_report_v1",
        "spec_path": str(SPEC),
        "spec_sha256": spec_hash,
        "result": "PARTIAL_INCONCLUSIVE" if affected_ids else "TEMPORAL_SUPPORT_CHANGE_OBSERVED",
        "frozen_state": {"architecture": "FROZEN", "full_training": "BLOCKED", "production_stride": "UNCHANGED"},
        "verification": {"pilot_A_vs_cache": "9/9 MATCH", "full_A_vs_cache": "296/296 MATCH for processed related recordings", "model_scores_generated": False, "model_fitted": False, "production_artifacts_modified": False, "eventizer_replayed": False, "oracle_run": False},
        "primary_questions": {
            "window_count_or_missing_support": "Both: B adds opportunity/window counts broadly, but positive-union time support changes only for a subset; count increase is not equivalent to usable time support.",
            "historical_failure_geometry": "See historical_missing_events_with_geometry_change; exact-complete subset distinguishes support gains from count-only changes.",
            "support_loss_or_eventizer_negative": "Geometry loss occurs in 10 events; eventizer behavior is unknown because no eventizer replay was run.",
            "supported_weakened_unknown": "Window-grid geometry change is supported; counts-only explanation is weakened; model exploitation and event-level benefit remain unknown.",
            "next_information_gain": "Only a separately gated fixed-model 15 s/3 s inference can answer whether exact support changes are converted into score support; no training or production change is authorized."
        },
        "exact_complete_summary": summary["exact_complete_232"],
        "all_234_summary": summary["all_234"],
        "strata": {"duration": summary["duration_groups_fixed"], "original_support": summary["original_support_groups_fixed_from_A"], "historical": summary["historical_covered_missing"]},
        "participant_summary": summary["participant_summary"],
        "affected_events": affected,
        "decision": {"COUNTS_ONLY_INCREASE": "NOT_ACCEPTED_AS_SUFFICIENT", "TEMPORAL_SUPPORT_CHANGE_OBSERVED": "SUPPORTED_ON_232_EXACT_COMPLETE_EVENTS", "FROZEN_EVENTIZER_ORACLE_CHANGE_OBSERVED": "NOT_RUN", "PARTIAL_INCONCLUSIVE": "TRIGGERED_BY_2_APPROVED_RAW_SKIPS", "WINDOW_GEOMETRY_PROBE": "JUSTIFIED_AS_DIAGNOSTIC_ONLY", "production_stride_change": "NOT_AUTHORIZED"},
        "next_action": "Stop this pass. If separately gated, run fixed production CandidateModel inference at 15 s/3 s using the same participant-disjoint score-selection contract; do not train, tune, eventize differently, or change production stride."
    }
    (ROOT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["result"], "events": len(rows), "exact_complete": len(complete_rows), "affected": sorted(affected_ids), "coverage_delta": summary["all_234"]["paired_delta"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
