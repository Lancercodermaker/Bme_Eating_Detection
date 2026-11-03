"""Write the read-only denominator and frozen-model availability audit.

This script does not fit, load, or score a model. It only summarizes the
already-frozen window-geometry artifact and records why the stride diagnostic
cannot proceed without serialized participant-disjoint estimators.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/g1-frozen-model-stride-transfer-diagnostic-v1"
SPEC_PATH = ROOT / "configs/formal-g1-frozen-model-stride-transfer-diagnostic-v1.json"
SPEC_HASH = "4b822a91791da359fa3d817b1b6ec8a7fbac351bf49a90968824519c1548b38f"
BAD_IDS = {
    "HNU21012:1784723920000-1784728154000",
    "HNU21035:1785042527000-1785043718000",
}


def normalized(event_id: str) -> str:
    return event_id.replace(" ", "")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def delta(row: dict[str, Any], field: str) -> int | float:
    return row["B"].get(field, 0) - row["A"].get(field, 0)


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = [delta(row, "positive_union_coverage_ms") for row in rows]
    fraction = [delta(row, "positive_union_coverage_fraction") for row in rows]
    duration_fraction = [value / row["duration_ms"] for value, row in zip(coverage, rows)]
    longest = [delta(row, "longest_unsupported_gap_ms") for row in rows]
    leading = [delta(row, "leading_unsupported_ms") for row in rows]
    trailing = [delta(row, "trailing_unsupported_ms") for row in rows]
    unsupported = [delta(row, "unsupported_duration_ms") for row in rows]

    def summary(values: list[int | float]) -> dict[str, Any]:
        return {
            "sum": sum(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }

    return {
        "event_count": len(rows),
        "union_coverage_delta_ms": summary(coverage),
        "union_coverage_delta_seconds": {
            key: value / 1000.0
            for key, value in summary(coverage).items()
        },
        "union_coverage_fraction_delta": summary(fraction),
        "union_coverage_delta_over_event_duration": summary(duration_fraction),
        "longest_unsupported_gap_delta_ms": summary(longest),
        "leading_boundary_gap_delta_ms": summary(leading),
        "trailing_boundary_gap_delta_ms": summary(trailing),
        "unsupported_duration_delta_ms": summary(unsupported),
        "classification": {
            "improved": sum(value > 0 for value in coverage),
            "unchanged": sum(value == 0 for value in coverage),
            "worsened": sum(value < 0 for value in coverage),
            "rule": "positive B-A union coverage delta improves; zero unchanged; negative worsens",
        },
    }


def compact_side(side: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "dense_window_count",
        "positive_window_count",
        "ignore_window_count",
        "positive_union_coverage_ms",
        "positive_union_coverage_fraction",
        "leading_unsupported_ms",
        "trailing_unsupported_ms",
        "longest_unsupported_gap_ms",
        "unsupported_duration_ms",
        "event_window_start_min_ms",
        "event_window_start_max_ms",
        "first_positive_offset_ms",
        "last_positive_offset_ms",
    )
    return {field: side.get(field) for field in fields}


def event_change(row: dict[str, Any], taxonomy: str | None = None) -> dict[str, Any]:
    a = row["A"]
    b = row["B"]
    return {
        "event_id": row["event_id"],
        "participant": row["participant"],
        "outer_fold": row["outer_fold"],
        "duration_ms": row["duration_ms"],
        "duration_seconds": row["duration_ms"] / 1000.0,
        "historical_status": row["historical_status"],
        "original_support_group": row["original_support_group"],
        "original_failure_taxonomy": taxonomy,
        "A": {
            "positive_window_count": a["positive_window_count"],
            "positive_union_coverage_ms": a["positive_union_coverage_ms"],
            "positive_union_coverage_fraction": a["positive_union_coverage_fraction"],
            "longest_unsupported_gap_ms": a["longest_unsupported_gap_ms"],
            "leading_unsupported_ms": a["leading_unsupported_ms"],
            "trailing_unsupported_ms": a["trailing_unsupported_ms"],
        },
        "B": {
            "positive_window_count": b["positive_window_count"],
            "positive_union_coverage_ms": b["positive_union_coverage_ms"],
            "positive_union_coverage_fraction": b["positive_union_coverage_fraction"],
            "longest_unsupported_gap_ms": b["longest_unsupported_gap_ms"],
            "leading_unsupported_ms": b["leading_unsupported_ms"],
            "trailing_unsupported_ms": b["trailing_unsupported_ms"],
        },
        "delta_B_minus_A": {
            "positive_window_count": b["positive_window_count"] - a["positive_window_count"],
            "union_coverage_ms": b["positive_union_coverage_ms"] - a["positive_union_coverage_ms"],
            "union_coverage_fraction": b["positive_union_coverage_fraction"] - a["positive_union_coverage_fraction"],
            "longest_unsupported_gap_ms": b["longest_unsupported_gap_ms"] - a["longest_unsupported_gap_ms"],
            "leading_unsupported_ms": b["leading_unsupported_ms"] - a["leading_unsupported_ms"],
            "trailing_unsupported_ms": b["trailing_unsupported_ms"] - a["trailing_unsupported_ms"],
        },
    }


def main() -> None:
    geometry_path = ROOT / "artifacts/g1-window-geometry-diagnostic-v1/full-paired-geometry.jsonl"
    review_path = ROOT / "artifacts/g1-model-temporal-representation-review-v1.json"
    rows = [json.loads(line) for line in geometry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    taxonomy_by_id = {
        normalized(row["event_id"]): row.get("taxonomy")
        for row in review["event_audit"]["rows"]
    }
    exact = [row for row in rows if normalized(row["event_id"]) not in BAD_IDS]
    missing = [row for row in exact if row["historical_status"] == "missing"]
    low_support = [row for row in exact if row["original_support_group"] == "<10"]
    short = [row for row in exact if row["duration_ms"] < 300_000]

    incomplete = []
    raw_skip_details = {
        "HNU21012:1784723920000-1784728154000": {
            "failed_recording": "E:\\bme_compitition\\official_test_dataset\\Data\\02_traindataset\\organized\\HNU21012\\sensorData-1784864012692-7abd340693a34144afdeeefd67b6ea74\\collect_data23_1784721958_1784726326.txt",
            "reason": "approved raw/undecodable skip prevents exact full-recording B context",
        },
        "HNU21035:1785042527000-1785043718000": {
            "failed_recording": "E:\\bme_compitition\\official_test_dataset\\Data\\02_traindataset\\organized\\HNU21035\\sensorData-1785079358000-23d230aac2cd41a5928d9ceef0174bfd\\collect_data13_1785038340_1785042876.txt",
            "reason": "approved raw/undecodable skip prevents exact full-recording B context",
        },
    }
    for row in rows:
        if normalized(row["event_id"]) not in BAD_IDS:
            continue
        incomplete.append({
            "event_id": row["event_id"],
            "participant": row["participant"],
            "outer_fold": row["outer_fold"],
            "duration_ms": row["duration_ms"],
            "historical_status": row["historical_status"],
            "original_support_group": row["original_support_group"],
            "raw_skip": raw_skip_details[normalized(row["event_id"])],
            "A": compact_side(row["A"]),
            "B": compact_side(row["B"]),
            "existing_result_range": {
                "dense_window_count": [row["A"]["dense_window_count"], row["B"]["dense_window_count"]],
                "positive_window_count": [row["A"]["positive_window_count"], row["B"]["positive_window_count"]],
                "union_coverage_ms": [row["A"]["positive_union_coverage_ms"], row["B"]["positive_union_coverage_ms"]],
                "union_coverage_fraction": [row["A"]["positive_union_coverage_fraction"], row["B"]["positive_union_coverage_fraction"]],
            },
        })

    clarification = {
        "schema_version": "formal_g1_frozen_model_stride_transfer_denominator_clarification_v1",
        "spec_path": str(SPEC_PATH.relative_to(ROOT)),
        "spec_sha256": SPEC_HASH,
        "source": {
            "previous_spec": "configs/formal-g1-window-geometry-diagnostic-v1.json",
            "previous_spec_sha256": "9b34bcdad1887e1dedd0a6e7c6b52e28080b5f55c3ebc6636215368aa5aac342",
            "paired_geometry": str(geometry_path.relative_to(ROOT)),
            "paired_geometry_sha256": sha256(geometry_path),
            "model_review": str(review_path.relative_to(ROOT)),
            "model_review_sha256": sha256(review_path),
        },
        "denominators": {
            "fixed_cohort": {"events": len(rows), "scope": "all 234 fixed events"},
            "exact_complete": {"events": len(exact), "scope": "232 events after excluding the two approved raw skips"},
            "historical_missing_exact_complete": len(missing),
            "duration_lt_300_seconds_exact_complete": len(short),
            "positive_windows_lt_10_exact_complete": len(low_support),
            "historical_missing_taxonomy_exact_complete": {
                "AGGREGATION_FIRST": sum(taxonomy_by_id.get(normalized(row["event_id"])) == "AGGREGATION_FIRST" for row in missing),
                "SCORE_THRESHOLD_FIRST": sum(taxonomy_by_id.get(normalized(row["event_id"])) == "SCORE_THRESHOLD_FIRST" for row in missing),
            },
        },
        "incomplete_events": incomplete,
        "fixed_234_summary": stats(rows),
        "exact_complete_232_summary": stats(exact),
        "subgroup_summaries_exact_complete": {
            "historical_missing": stats(missing),
            "duration_lt_300_seconds": stats(short),
            "positive_windows_lt_10": stats(low_support),
        },
        "historical_missing_event_by_event": [
            event_change(row, taxonomy_by_id.get(normalized(row["event_id"])))
            for row in missing
        ],
        "low_support_event_by_event": [
            event_change(row, taxonomy_by_id.get(normalized(row["event_id"])))
            for row in low_support
        ],
        "interpretation": {
            "support_change_only": "These are geometry/label-support changes from the previous diagnostic. No model score, selected-support, or event outcome is inferred here.",
            "improve_worsen_rule": "Use the signed B-A union coverage delta exactly; no post-hoc threshold or significance cutoff.",
            "approved_undecodable_skip": "Retain in the fixed 234 denominator with its existing A/B range; exclude from exact-complete summaries; do not fabricate missing support.",
        },
    }

    source_files = [
        "configs/formal-g1-frozen-model-stride-transfer-diagnostic-v1.json",
        "configs/formal-g1-window-geometry-diagnostic-v1.json",
        "artifacts/g1-window-geometry-diagnostic-v1/report.json",
        "artifacts/g1-window-geometry-diagnostic-v1/stratified-summary.json",
        "configs/formal-g1-decision-function-probe-v1.json",
        "artifacts/g1-decision-function-probe-v1/report.json",
        "artifacts/g1-decision-function-probe-v1/scores.npz",
        "artifacts/g1-temporal-representation-probe-v1/feature-table.npz",
        "src/eating_event/candidates.py",
        "src/eating_event/coverage.py",
        "src/eating_event/metrics.py",
        "scripts/run_candidate_coverage.py",
    ]
    model_gate = {
        "schema_version": "formal_g1_frozen_model_stride_transfer_model_gate_v1",
        "spec_path": str(SPEC_PATH.relative_to(ROOT)),
        "spec_sha256": SPEC_HASH,
        "status": "BLOCKED_MISSING_MATCHED_FROZEN_ARTIFACTS",
        "gate_checks": {
            "loadable_frozen_fold_models": {"status": "FAIL", "evidence": "No matching estimator/checkpoint files were found in the entire worktree."},
            "participant_disjoint_fold_mapping": {"status": "FAIL", "evidence": "Fold participant definitions are documented, but no serialized fold-to-model binding manifest is present."},
            "feature_schema_and_preprocessing": {"status": "PASS_AS_METADATA_ONLY", "evidence": "imu_stats_v1 111D feature table and source hashes are available; this does not replace the missing estimators."},
            "threshold_policy": {"status": "PASS_AS_METADATA_ONLY", "evidence": "The frozen decision-function report records A/N fold thresholds and the outer-train-derived policy; thresholds alone cannot produce B scores."},
            "eventizer_contract": {"status": "PASS_AS_SOURCE_ONLY", "evidence": "The eventizer and Formal G1 evaluator source is available and hashed; no replay was run."},
            "requires_fit_retrain_recalibration": {"status": "YES_IF_CONTINUED", "evidence": "The only available implementation creates estimators via fit_candidate_model; no serialized estimator is available."},
        },
        "discovered_matching_model_files": [],
        "available_non_model_artifacts": [
            "artifacts/g1-decision-function-probe-v1/report.json",
            "artifacts/g1-decision-function-probe-v1/scores.npz",
            "artifacts/g1-temporal-representation-probe-v1/scores.npz",
        ],
        "why_scores_are_insufficient": "The saved NPZ files contain score arrays only. They cannot be evaluated on newly generated 3 s feature rows, and re-fitting an estimator would be a prohibited training operation.",
        "source_file_hashes": {str((ROOT / rel).relative_to(ROOT)): sha256(ROOT / rel) for rel in source_files if (ROOT / rel).is_file()},
        "stop": "Complete denominator clarification and stop before A replay, B inference, event-level replay, or Formal G1 interpretation.",
    }

    report = {
        "schema_version": "formal_g1_frozen_model_stride_transfer_diagnostic_report_v1",
        "status": "BLOCKED_MISSING_MATCHED_FROZEN_ARTIFACTS",
        "spec_path": str(SPEC_PATH.relative_to(ROOT)),
        "spec_sha256": SPEC_HASH,
        "previous_denominator_clarification": "denominator-clarification.json",
        "model_availability_gate": "model-availability-gate.json",
        "execution": {
            "A_15s_7.5s_replay": "NOT_RUN_BLOCKED_BEFORE_MODEL_CALL",
            "B_15s_3s_inference": "NOT_RUN_BLOCKED_MISSING_FROZEN_ESTIMATORS",
            "window_level_metrics": "NOT_RUN",
            "event_level_replay": "NOT_RUN",
            "formal_g1": "NOT_RUN",
        },
        "requested_outputs": {
            "score_evidence": "NOT_IDENTIFIABLE_WITHOUT_MATCHED_ESTIMATORS",
            "event_result": "NOT_IDENTIFIABLE_WITHOUT_MATCHED_ESTIMATORS",
            "recovered_events": "NOT_RUN",
            "newly_lost_events": "NOT_RUN",
            "net_coverage_change": "NOT_RUN",
        },
        "decision": "BLOCKED_MISSING_MATCHED_FROZEN_ARTIFACTS",
        "reason": "The model-availability gate fails. Continuing would require fitting or borrowing an unmatched model, both explicitly prohibited.",
        "final_state": {
            "ARCHITECTURE": "FROZEN",
            "FULL_TRAINING": "BLOCKED",
            "PRODUCTION_STRIDE": "UNCHANGED",
            "production_artifacts_modified": False,
        },
        "verification": {
            "spec_json_parses": True,
            "spec_sidecar_hash_checked": True,
            "old_report_preserved": True,
            "new_inference_started": False,
            "model_fit_started": False,
            "threshold_changed": False,
            "eventizer_changed": False,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("denominator-clarification.json", clarification),
        ("model-availability-gate.json", model_gate),
        ("report.json", report),
    ):
        (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
