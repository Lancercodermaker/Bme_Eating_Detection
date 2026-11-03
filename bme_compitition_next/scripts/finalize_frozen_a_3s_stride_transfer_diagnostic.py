"""Recompute only the frozen-A 3 s diagnostic reporting layer from saved B artifacts."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from eating_event.cache import load_candidate_table
from eating_event.candidates import eventize_windows
from eating_event.data.labels import WindowLabel
from eating_event.data.windows import WindowRecord, WindowSpec
from eating_event.metrics import EventInterval

import run_frozen_a_3s_stride_transfer_diagnostic as diag


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts/g1-frozen-a-3s-stride-transfer-diagnostic-v1"
GEOMETRY_PATH = ROOT / "artifacts/g1-window-geometry-diagnostic-v1/full-paired-geometry.jsonl"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=diag.json_default) + "\n", encoding="utf-8")


def main() -> None:
    spec, spec_hash = diag.verify_spec()
    report_path = OUTPUT_DIR / "report.json"
    old_report = json.loads(report_path.read_text(encoding="utf-8"))
    context = diag.load_context(spec)
    manifest = json.loads((OUTPUT_DIR / "b-window-manifest.json").read_text(encoding="utf-8"))
    records_by_path = {str(item["record"].path): item for item in context["cache_records"]}
    record_infos: list[dict[str, object]] = []
    b_score_parts: list[np.ndarray] = []
    b_label_parts: list[np.ndarray] = []
    b_participant_parts: list[np.ndarray] = []
    b_start_parts: list[np.ndarray] = []
    b_end_parts: list[np.ndarray] = []
    b_hard_parts: list[np.ndarray] = []
    b_easy_parts: list[np.ndarray] = []
    b_missing_parts: list[np.ndarray] = []
    b_covered_parts: list[np.ndarray] = []
    b_common_parts: list[np.ndarray] = []
    predictions_a: dict[str, list[EventInterval]] = defaultdict(list)
    predictions_b: dict[str, list[EventInterval]] = defaultdict(list)

    for row in manifest["records"]:
        record_path = str(row["path"])
        item = records_by_path[record_path]
        b_path = ROOT / str(row["b_path"])
        payload = np.load(b_path, allow_pickle=False)
        starts = payload["starts"].astype(np.int64, copy=False)
        ends = payload["ends"].astype(np.int64, copy=False)
        labels = payload["labels"].astype(np.int8, copy=False)
        scores = payload["scores"].astype(np.float64, copy=False)
        hard = payload["hard_negative"].astype(bool, copy=False)
        easy = payload["easy_negative"].astype(bool, copy=False)
        common = payload["common_with_a"].astype(bool, copy=False)
        missing = np.zeros(labels.size, dtype=bool)
        covered = np.zeros(labels.size, dtype=bool)
        for index, (start, end, label) in enumerate(zip(starts, ends, labels)):
            if int(label) != 1:
                continue
            for event in context["event_dicts"]:
                if event["participant"] != row["participant"] or not diag.intersects(int(start), int(end), event):
                    continue
                if event["historical_taxonomy"] != "COVERED":
                    missing[index] = True
                else:
                    covered[index] = True
        np.savez_compressed(
            b_path,
            features=payload["features"].astype(np.float32, copy=False),
            starts=starts,
            ends=ends,
            labels=labels,
            scores=scores,
            hard_negative=hard,
            easy_negative=easy,
            common_with_a=common,
            missing_positive=missing,
            covered_positive=covered,
        )
        record = item["record"]
        a_table = load_candidate_table(item["cache_path"], expected_metadata=item["metadata"])
        a_starts = np.asarray([window.window.start_ms for window in a_table.windows], dtype=np.int64)
        a_ends = np.asarray([window.window.end_ms for window in a_table.windows], dtype=np.int64)
        a_scores = np.asarray(
            [context["a_score_by_key"][diag.row_key(record.path, window.window.start_ms, window.window.end_ms, index)] for index, window in enumerate(a_table.windows)],
            dtype=np.float64,
        )
        fold_id = context["fold_id_by_participant"][record.participant_id]
        predictions_a[record.participant_id].extend(
            EventInterval(start, end)
            for start, end in eventize_windows(a_table.windows, a_scores, threshold=context["thresholds"][fold_id], min_duration_ms=1, fuse_gap_ms=diag.FUSE_GAP_MS)
        )
        b_windows = [
            WindowRecord(
                window=WindowSpec(int(start), int(end)),
                coverage=1.0,
                longest_invalid_run=0,
                label_result=__import__("eating_event.data.labels", fromlist=["WindowLabelResult"]).WindowLabelResult(WindowLabel.IGNORE, 0.0, None),
            )
            for start, end in zip(starts, ends)
        ]
        predictions_b[record.participant_id].extend(
            EventInterval(start, end)
            for start, end in eventize_windows(b_windows, scores, threshold=context["thresholds"][fold_id], min_duration_ms=1, fuse_gap_ms=diag.FUSE_GAP_MS)
        )
        b_score_parts.append(scores)
        b_label_parts.append(labels)
        b_participant_parts.append(np.full(labels.size, record.participant_id, dtype=object))
        b_start_parts.append(starts)
        b_end_parts.append(ends)
        b_hard_parts.append(hard)
        b_easy_parts.append(easy)
        b_missing_parts.append(missing)
        b_covered_parts.append(covered)
        b_common_parts.append(common)
        record_info = dict(row)
        record_info["record"] = record
        record_info["cache_path_obj"] = item["cache_path"]
        record_info["metadata"] = item["metadata"]
        record_info["b_path"] = b_path
        record_infos.append(record_info)

    b_scores = np.concatenate(b_score_parts)
    b_labels = np.concatenate(b_label_parts)
    b_participants = np.concatenate(b_participant_parts)
    b_starts = np.concatenate(b_start_parts)
    b_ends = np.concatenate(b_end_parts)
    b_hard = np.concatenate(b_hard_parts)
    b_easy = np.concatenate(b_easy_parts)
    b_missing = np.concatenate(b_missing_parts)
    b_covered = np.concatenate(b_covered_parts)
    b_common = np.concatenate(b_common_parts)
    np.savez_compressed(
        OUTPUT_DIR / "b-scores.npz",
        scores=b_scores,
        labels=b_labels,
        participants=b_participants,
        starts=b_starts,
        ends=b_ends,
        hard_negative=b_hard,
        easy_negative=b_easy,
        common_with_a=b_common,
        missing_positive=b_missing,
        covered_positive=b_covered,
    )
    a_controls = diag.classify_controls(
        context["a_participants"], context["a_starts"], context["a_ends"], context["a_labels"], context["a_scores"],
        [str(key) for key in context["a_feature_row_keys"]], context["historical_taxonomy"], context["event_dicts"], context["fold_id_by_participant"],
    )
    a_summary = diag.summarize_windows("A_15s_7.5s_reconstructed_score_source", context["a_participants"], context["a_labels"], context["a_scores"], context["fold_id_by_participant"], a_controls)
    b_summary = diag.summarize_windows(
        "B_15s_3s_frozen_model_inference", b_participants, b_labels, b_scores, context["fold_id_by_participant"],
        {"missing_positive": b_missing, "covered_positive": b_covered, "hard_negative": b_hard, "easy_negative": b_easy},
    )
    common_tuples = set()
    for row in manifest["records"]:
        payload = np.load(ROOT / str(row["b_path"]), allow_pickle=False)
        common = payload["common_with_a"].astype(bool, copy=False)
        for start, end in zip(payload["starts"][common], payload["ends"][common]):
            common_tuples.add((str(row["path"]), int(start), int(end)))
    a_common = np.asarray(
        [
            (str(key).rsplit("|", 3)[0], int(str(key).rsplit("|", 3)[1]), int(str(key).rsplit("|", 3)[2])) in common_tuples
            for key in context["a_feature_row_keys"]
        ],
        dtype=bool,
    )
    a_common_controls = {
        "missing_positive": a_controls["missing_positive"] & a_common,
        "covered_positive": a_controls["covered_positive"] & a_common,
        "hard_negative": a_controls["hard_negative"] & a_common,
        "easy_negative": a_controls["easy_negative"] & a_common,
    }
    b_common_controls = {
        "missing_positive": b_missing & b_common,
        "covered_positive": b_covered & b_common,
        "hard_negative": b_hard & b_common,
        "easy_negative": b_easy & b_common,
    }
    a_common_summary = diag.summarize_windows("A_common_starts", context["a_participants"], context["a_labels"], context["a_scores"], context["fold_id_by_participant"], a_common_controls)
    b_common_summary = diag.summarize_windows("B_common_starts", b_participants, b_labels, b_scores, context["fold_id_by_participant"], b_common_controls)
    a_replay, a_event_rows = diag.replay_report(context, record_infos, predictions_a, "A")
    b_replay, b_event_rows = diag.replay_report(context, record_infos, predictions_b, "B")
    a_by_id = {row["normalized_event_id"]: row for row in a_event_rows}
    b_by_id = {row["normalized_event_id"]: row for row in b_event_rows}
    paired: list[dict[str, object]] = []
    for event in context["event_dicts"]:
        key = event["normalized_event_id"]
        a_row, b_row = a_by_id[key], b_by_id[key]
        paired.append({
            "event_id": event["event_id"], "normalized_event_id": key, "participant": event["participant"],
            "outer_fold": context["fold_id_by_participant"][event["participant"]], "duration_ms": event["duration_ms"],
            "duration_group": "<300s" if event["duration_ms"] < 300000 else ">1200s" if event["duration_ms"] > 1200000 else "300-600s" if event["duration_ms"] < 600000 else "600-1200s",
            "historical_taxonomy": event["historical_taxonomy"], "A": a_row, "B": b_row,
            "delta_B_minus_A": {
                "positive_window_count": int(b_row["positive_window_count"] - a_row["positive_window_count"]),
                "positive_score_median": None if a_row["positive_score"]["median"] is None or b_row["positive_score"]["median"] is None else float(b_row["positive_score"]["median"] - a_row["positive_score"]["median"]),
                "positive_score_p90": None if a_row["positive_score"]["p90"] is None or b_row["positive_score"]["p90"] is None else float(b_row["positive_score"]["p90"] - a_row["positive_score"]["p90"]),
                "above_threshold_positive_window_fraction": None if a_row["above_threshold_positive_window_fraction"] is None or b_row["above_threshold_positive_window_fraction"] is None else float(b_row["above_threshold_positive_window_fraction"] - a_row["above_threshold_positive_window_fraction"]),
                "selected_union_coverage_ms": int(b_row["selected_union_coverage_ms"] - a_row["selected_union_coverage_ms"]),
                "unsupported_duration_ms": int(b_row["unsupported_duration_ms"] - a_row["unsupported_duration_ms"]),
                "longest_unsupported_gap_ms": int(b_row["longest_unsupported_gap_ms"] - a_row["longest_unsupported_gap_ms"]),
                "best_prediction_iou": float(b_row["best_prediction_iou"] - a_row["best_prediction_iou"]),
            },
            "event_outcome": {
                "A_covered_B_covered": bool(a_row["covered"] and b_row["covered"]),
                "A_missing_B_covered": bool(not a_row["covered"] and b_row["covered"]),
                "A_covered_B_missing": bool(a_row["covered"] and not b_row["covered"]),
                "A_missing_B_missing": bool(not a_row["covered"] and not b_row["covered"]),
            },
        })
    counts = {
        "A_missing_to_B_covered": int(sum(row["event_outcome"]["A_missing_B_covered"] for row in paired)),
        "A_covered_to_B_missing": int(sum(row["event_outcome"]["A_covered_B_missing"] for row in paired)),
        "both_covered": int(sum(row["event_outcome"]["A_covered_B_covered"] for row in paired)),
        "both_missing": int(sum(row["event_outcome"]["A_missing_B_missing"] for row in paired)),
    }
    geometry_groups = {}
    for line in GEOMETRY_PATH.read_text(encoding="utf-8").splitlines():
        geometry_row = json.loads(line)
        geometry_groups[str(geometry_row["event_id"]).replace(" ", "")] = geometry_row.get("original_support_group")
    for row in paired:
        row["original_support_group"] = geometry_groups.get(str(row["normalized_event_id"]))

    def strata_summary(field: str, values: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for value in values:
            subset = [row for row in paired if row.get(field) == value]
            result[value] = {
                "event_count": len(subset),
                "A_covered": int(sum(bool(row["A"]["covered"]) for row in subset)),
                "B_covered": int(sum(bool(row["B"]["covered"]) for row in subset)),
                "A_missing_to_B_covered": int(sum(bool(row["event_outcome"]["A_missing_B_covered"]) for row in subset)),
                "A_covered_to_B_missing": int(sum(bool(row["event_outcome"]["A_covered_B_missing"]) for row in subset)),
            }
        return result
    strata = {
        "duration": strata_summary("duration_group", ["<300s", "300-600s", "600-1200s", ">1200s"]),
        "original_support_group": strata_summary("original_support_group", ["<10", "10-24", "25-49", ">=50"]),
        "historical_taxonomy": strata_summary("historical_taxonomy", ["AGGREGATION_FIRST", "SCORE_THRESHOLD_FIRST", "COVERED"]),
    }
    write_json(OUTPUT_DIR / "a-replay.json", {"status": "A_REPLAY_REUSED_MATCHED_SCORE_SOURCE", "row_count": int(context["a_scores"].size), "stable_id_count": int(context["a_row_keys"].size), "score_source": "artifacts/g1-a-baseline-reconstruction-v1/scores.npz", "score_identity_tolerance": {"absolute": diag.ATOL, "relative": diag.RTOL}, "thresholds_reused": context["thresholds"], "eventizer": {"min_duration_ms": 1, "fuse_gap_ms": diag.FUSE_GAP_MS, "iou_threshold": diag.IOU_THRESHOLD}, "fixed234": a_replay["fixed_234"], "exact_complete_232": a_replay["exact_complete_232"]})
    with (OUTPUT_DIR / "event-paired-results.jsonl").open("w", encoding="utf-8") as stream:
        for row in paired:
            stream.write(json.dumps(row, ensure_ascii=False, default=diag.json_default) + "\n")
    old_report["spec_sha256"] = spec_hash
    old_report["window_level"] = {"A": a_summary, "B": b_summary, "common_start_controls": {"A": a_common_summary["controls"], "B": b_common_summary["controls"], "common_start_count": int(b_common.sum()), "note": "For fair A/B hard-negative comparison, both positive controls and fixed A-derived hard/easy membership are restricted to common starts."}, "controls_note": "B hard/easy controls are frozen from A OOF membership on common A/B starts; B-only negatives are not assigned to fixed controls", "common_start_identity": old_report["window_level"]["common_start_identity"]}
    old_report["event_level"] = {"A": a_replay, "B": b_replay, "paired_outcomes": counts, "strata": strata, "event_rows": "event-paired-results.jsonl", "prediction_matching_note": "fixed234 matching is summed per participant; unmatched counts are descriptive under incomplete coverage; exact232 excludes only two incomplete GT events from recall"}
    old_report["source_hashes_verified"]["previous_geometry_paired_results"] = diag.sha256_file(GEOMETRY_PATH)
    old_report["decision"]["window_level_transfer"] = "BOUNDED_SCORE_CHANGE_OBSERVED"
    old_report["decision"]["event_level_transfer"] = "UNSUPPORTED"
    old_report["decision"]["event_benefit"] = "NO_CLEAR_EVENT_BENEFIT"
    old_report["execution"]["report_finalization_repaired"] = True
    old_report["execution"]["repair_reason"] = ["recompute all 27 historical non-COVERED MissingEvent control memberships", "prevent cross-participant event matching"]
    write_json(report_path, old_report)
    print(json.dumps({"status": old_report["status"], "fixed_A": a_replay["fixed_234"], "fixed_B": b_replay["fixed_234"], "outcomes": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
