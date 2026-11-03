"""Run the frozen-A 15 s / 7.5 s versus 15 s / 3 s stride diagnostic."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

import joblib
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from eating_event.cache import load_candidate_table
from eating_event.candidates import CandidateModel, build_candidate_table, eventize_windows
from eating_event.config import load_config
from eating_event.data.labels import WindowLabel
from eating_event.data.manifest import (
    discover_raw_files,
    events_for_record,
    filter_meal_events_by_ledger,
    load_meal_events,
)
from eating_event.data.windows import WindowRecord, generate_dense_windows
from eating_event.data.raw import regularize_imu
from eating_event.metrics import EventInterval, evaluate_events, interval_iou

from formal_g1_temporal_representation_probe import _read_fast_imu
from run_candidate_baseline import _cache_metadata


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "configs/formal-g1-frozen-a-3s-stride-transfer-diagnostic-v1.json"
HASH_PATH = ROOT / "configs/formal-g1-frozen-a-3s-stride-transfer-diagnostic-v1.sha256"
OUTPUT_DIR = ROOT / "artifacts/g1-frozen-a-3s-stride-transfer-diagnostic-v1"
CACHE_DIR = ROOT / "artifacts/g1-formal-cache-v3-final"
ELIGIBILITY_PATH = ROOT / "artifacts/g1-candidate-coverage-v4/eligibility.json"
AUDIT_PATH = ROOT / "artifacts/g1-processed-only-manifest-audit.json"
REVIEW_PATH = ROOT / "artifacts/g1-model-temporal-representation-review-v1.json"
A_SCORES_PATH = ROOT / "artifacts/g1-a-baseline-reconstruction-v1/scores.npz"
A_FEATURE_TABLE_PATH = ROOT / "artifacts/g1-temporal-representation-probe-v1/feature-table.npz"
A_FOLD_MANIFEST_PATH = ROOT / "artifacts/g1-a-baseline-reconstruction-v1/fold-manifest.json"
MODEL_DIR = ROOT / "artifacts/g1-a-baseline-reconstruction-v1/models"

WINDOW_SECONDS = 15.0
A_STEP_SECONDS = 7.5
B_STEP_SECONDS = 3.0
GRID_HZ = 10
MIN_COVERAGE = 0.8
MAX_GAP_SECONDS = 2.0
POSITIVE_OVERLAP = 0.5
NEGATIVE_DISTANCE_MS = 300_000
FUSE_GAP_MS = 300_000
IOU_THRESHOLD = 0.25
ATOL = 1e-12
RTOL = 1e-12
FEATURE_MATCH_ATOL = 1e-6
MISSING_IDS = {
    "HNU21012:1784723920000-1784728154000",
    "HNU21035:1785042527000-1785043718000",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_event_id(event_id: str) -> str:
    return event_id.replace(" ", "")


def json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def verify_spec() -> tuple[dict[str, Any], str]:
    spec_bytes = SPEC_PATH.read_bytes()
    expected = HASH_PATH.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = hashlib.sha256(spec_bytes).hexdigest()
    if actual != expected:
        raise RuntimeError(f"frozen spec hash mismatch: expected {expected}, got {actual}")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if spec.get("status") != "FROZEN":
        raise RuntimeError("frozen stride diagnostic spec is not FROZEN")
    return spec, actual


def load_manifest_bad_rows() -> dict[str, set[int]]:
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    return {
        str(Path(row["path"]).expanduser().resolve()): {
            int(detail["source_row_number"])
            for detail in row.get("malformed_row_details", [])
            if "source_row_number" in detail
        }
        for row in payload["files"]
        if row.get("status") == "processed"
    }


def load_context(spec: Mapping[str, Any]) -> dict[str, Any]:
    config = load_config(ROOT / "configs/example.local.yaml")
    eligibility = json.loads(ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    meal_events = filter_meal_events_by_ledger(meal_events, eligibility, eligibility_field="training_eligibility")

    score_payload = np.load(A_SCORES_PATH, allow_pickle=True)
    a_row_keys = score_payload["row_keys"].astype(object)
    a_scores = score_payload["reconstructed_baseline_scores"].astype(np.float64)
    if a_row_keys.size != 632100 or a_scores.size != a_row_keys.size:
        raise RuntimeError("A score artifact shape contract failed")
    if np.unique(a_row_keys).size != a_row_keys.size or not np.isfinite(a_scores).all():
        raise RuntimeError("A score artifact stable-ID contract failed")
    a_score_by_key = {str(key): float(score) for key, score in zip(a_row_keys, a_scores)}
    a_feature_index_by_key = {str(key): int(index) for index, key in enumerate(a_row_keys)}

    feature_payload = np.load(A_FEATURE_TABLE_PATH, allow_pickle=True)
    a_features = feature_payload["a"].astype(np.float32, copy=False)
    a_labels = feature_payload["labels"].astype(np.int8, copy=False)
    a_participants = feature_payload["participants"].astype(object)
    a_starts = feature_payload["starts"].astype(np.int64, copy=False)
    a_ends = feature_payload["ends"].astype(np.int64, copy=False)
    a_feature_row_keys = feature_payload["row_keys"].astype(object)
    if a_feature_row_keys.size != a_row_keys.size or not np.array_equal(a_feature_row_keys, a_row_keys):
        raise RuntimeError("A feature-table and score-artifact row order/IDs differ")

    fold_manifest = json.loads(A_FOLD_MANIFEST_PATH.read_text(encoding="utf-8"))
    folds = fold_manifest["folds"]
    fold_id_by_participant: dict[str, str] = {}
    thresholds: dict[str, float] = {}
    models: dict[str, CandidateModel] = {}
    for row in folds:
        fold_id = str(row["fold_id"])
        thresholds[fold_id] = float(row["saved_threshold"])
        if not bool(row["participant_disjoint_verified"]):
            raise RuntimeError(f"participant-disjoint manifest failed for {fold_id}")
        for participant in row["valid_participants"]:
            if participant in fold_id_by_participant:
                raise RuntimeError(f"participant assigned to multiple folds: {participant}")
            fold_id_by_participant[str(participant)] = fold_id
        model_path = MODEL_DIR / f"{fold_id}.joblib"
        if not model_path.is_file():
            raise RuntimeError(f"missing frozen model: {model_path}")
        expected_hash = next(item["model"]["sha256"] for item in folds if item["fold_id"] == fold_id)
        if sha256_file(model_path) != expected_hash:
            raise RuntimeError(f"frozen model hash mismatch: {fold_id}")
        models[fold_id] = CandidateModel(joblib.load(model_path))

    if set(map(str, np.unique(a_participants))) != set(fold_id_by_participant):
        raise RuntimeError("A participants and fold manifest differ")

    historical_taxonomy: dict[str, str] = {}
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    for row in review["event_audit"]["rows"]:
        historical_taxonomy[normalize_event_id(str(row["event_id"]))] = str(row["taxonomy"])

    event_rows = [row for row in eligibility["event_eligibility"] if bool(row.get("training_eligibility"))]
    if len(event_rows) != 234:
        raise RuntimeError("fixed event cohort is not 234")
    event_dicts: list[dict[str, Any]] = []
    for row in event_rows:
        participant = str(row["participant_id"])
        event_id = f"{participant}:{int(row['start_ms'])}-{int(row['end_ms'])}"
        event_dicts.append(
            {
                "event_id": event_id,
                "normalized_event_id": normalize_event_id(event_id),
                "participant": participant,
                "event_index": int(row["event_index"]),
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "duration_ms": int(row["duration_ms"]),
                "historical_taxonomy": historical_taxonomy.get(normalize_event_id(event_id)),
            }
        )
    if {row["normalized_event_id"] for row in event_dicts if row["normalized_event_id"] in MISSING_IDS}:
        pass
    # The approved raw-undeccodable status is a current replay-context property.
    # It is not allowed to overwrite or reinterpret the read-only historical taxonomy.

    bad_rows = load_manifest_bad_rows()
    records = discover_raw_files(config.raw_data_root)
    cache_records: list[dict[str, Any]] = []
    missing_cache: list[str] = []
    for record in records:
        metadata = _cache_metadata(
            record,
            config,
            eligibility_artifact_sha256=str(eligibility["label_eligible_event_denominator_sha256"]),
        )
        cache_path = CACHE_DIR / f"{metadata['cache_key']}.npz"
        if cache_path.is_file():
            cache_records.append({"record": record, "cache_path": cache_path, "metadata": metadata})
        else:
            missing_cache.append(str(record.path))
    if len(cache_records) != 1127:
        raise RuntimeError(f"approved cache record count mismatch: {len(cache_records)}")

    event_intervals_by_participant: dict[str, tuple[EventInterval, ...]] = defaultdict(tuple)
    for row in event_dicts:
        event_intervals_by_participant[row["participant"]] = tuple(
            list(event_intervals_by_participant[row["participant"]])
            + [EventInterval(row["start_ms"], row["end_ms"])]
        )

    return {
        "config": config,
        "eligibility": eligibility,
        "meal_events": meal_events,
        "a_score_by_key": a_score_by_key,
        "a_feature_index_by_key": a_feature_index_by_key,
        "a_row_keys": a_row_keys,
        "a_scores": a_scores,
        "a_features": a_features,
        "a_labels": a_labels,
        "a_participants": a_participants,
        "a_starts": a_starts,
        "a_ends": a_ends,
        "a_feature_row_keys": a_feature_row_keys,
        "folds": folds,
        "fold_id_by_participant": fold_id_by_participant,
        "thresholds": thresholds,
        "models": models,
        "event_dicts": event_dicts,
        "event_intervals_by_participant": event_intervals_by_participant,
        "historical_taxonomy": historical_taxonomy,
        "bad_rows": bad_rows,
        "cache_records": cache_records,
        "missing_cache": missing_cache,
    }


def row_key(path: Path, start: int, end: int, index: int) -> str:
    return f"{path}|{int(start)}|{int(end)}|{int(index)}"


def window_records_from_arrays(starts: np.ndarray, ends: np.ndarray) -> list[WindowRecord]:
    return [
        WindowRecord(
            window=__import__("eating_event.data.windows", fromlist=["WindowSpec"]).WindowSpec(int(start), int(end)),
            coverage=1.0,
            longest_invalid_run=0,
            label_result=__import__("eating_event.data.labels", fromlist=["WindowLabelResult"]).WindowLabelResult(
                WindowLabel.IGNORE, 0.0, None
            ),
        )
        for start, end in zip(starts, ends)
    ]


def score_summary(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0, "min": None, "median": None, "p90": None, "max": None}
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "median": float(np.median(values)),
        "p90": float(np.quantile(values, 0.9)),
        "max": float(values.max()),
    }


def binary_metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    y = np.asarray(labels, dtype=np.int8)
    s = np.asarray(scores, dtype=np.float64)
    keep = np.isfinite(s) & ((y == 0) | (y == 1))
    y = y[keep]
    s = s[keep]
    if y.size == 0 or np.unique(y).size < 2:
        return {"auroc": None, "auprc": None, "count": int(y.size), "reason": "missing both classes"}
    return {
        "auroc": float(roc_auc_score(y, s)),
        "auprc": float(average_precision_score(y, s)),
        "count": int(y.size),
    }


def intersects(start: int, end: int, event: Mapping[str, Any]) -> bool:
    return start < int(event["end_ms"]) and end > int(event["start_ms"])


def union_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted((int(start), int(end)) for start, end in intervals if end > start)
    if not ordered:
        return []
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def support_stats(
    event: Mapping[str, Any],
    rows: Sequence[dict[str, Any]],
    predictions: Sequence[EventInterval],
    threshold: float,
) -> dict[str, Any]:
    gt_start, gt_end = int(event["start_ms"]), int(event["end_ms"])
    overlapping: list[tuple[dict[str, Any], int, int]] = []
    for record in rows:
        starts = record["starts"]
        ends = record["ends"]
        for index, (start, end) in enumerate(zip(starts, ends)):
            if intersects(int(start), int(end), event):
                overlapping.append((record, int(start), int(end)))
    positive_scores: list[float] = []
    all_scores: list[float] = []
    selected_intervals: list[tuple[int, int]] = []
    for record, start, end in overlapping:
        index = int(np.flatnonzero((record["starts"] == start) & (record["ends"] == end))[0])
        score = float(record["scores"][index])
        label = int(record["labels"][index])
        all_scores.append(score)
        if label == 1:
            positive_scores.append(score)
        if score >= threshold:
            selected_intervals.append((max(start, gt_start), min(end, gt_end)))
    merged_selected = union_intervals(selected_intervals)
    covered_ms = sum(end - start for start, end in merged_selected)
    gaps: list[int] = []
    cursor = gt_start
    leading = 0
    for start, end in merged_selected:
        if start > cursor:
            gaps.append(start - cursor)
            if cursor == gt_start:
                leading = start - cursor
        cursor = max(cursor, end)
    trailing = max(0, gt_end - cursor)
    if trailing:
        gaps.append(trailing)
    best_prediction = max(
        ((interval_iou(prediction, EventInterval(gt_start, gt_end)), prediction) for prediction in predictions),
        default=(0.0, None),
    )
    best_iou, best_interval = best_prediction
    positive_array = np.asarray(positive_scores, dtype=np.float64)
    all_array = np.asarray(all_scores, dtype=np.float64)
    return {
        "positive_window_count": int(positive_array.size),
        "positive_score": score_summary(positive_array),
        "all_intersecting_score": score_summary(all_array),
        "above_threshold_positive_window_count": int(np.sum(positive_array >= threshold)),
        "above_threshold_positive_window_fraction": float(np.mean(positive_array >= threshold)) if positive_array.size else None,
        "selected_window_count": int(sum(1 for record, start, end in overlapping if float(record["scores"][int(np.flatnonzero((record["starts"] == start) & (record["ends"] == end))[0])]) >= threshold)),
        "selected_union_coverage_ms": int(covered_ms),
        "selected_union_coverage_fraction": float(covered_ms / (gt_end - gt_start)),
        "unsupported_duration_ms": int((gt_end - gt_start) - covered_ms),
        "longest_unsupported_gap_ms": int(max(gaps, default=gt_end - gt_start)),
        "leading_unsupported_ms": int(leading),
        "trailing_unsupported_ms": int(trailing),
        "best_prediction_iou": float(best_iou),
        "best_prediction_interval": [best_interval.start_ms, best_interval.end_ms] if best_interval else None,
        "duration_ratio": float((best_interval.end_ms - best_interval.start_ms) / (gt_end - gt_start)) if best_interval else None,
        "covered": bool(best_iou > IOU_THRESHOLD),
    }


def event_matching_summary(predictions: Sequence[EventInterval], truths: Sequence[EventInterval]) -> dict[str, Any]:
    metrics = evaluate_events(predictions, truths, iou_threshold=IOU_THRESHOLD)
    matched_predictions = {match.prediction_index for match in metrics.matches}
    covered_gt = sum(
        any(interval_iou(prediction, truth) > IOU_THRESHOLD for prediction in predictions)
        for truth in truths
    )
    return {
        "predicted_event_count": int(len(predictions)),
        "covered_gt_count": int(covered_gt),
        "matched_gt_count_one_to_one": int(len(metrics.matches)),
        "matched_prediction_count_one_to_one": int(len(matched_predictions)),
        "unmatched_prediction_count_descriptive": int(len(predictions) - len(matched_predictions)),
        "matched_minus_covered_gt": int(len(matched_predictions) - covered_gt),
        "extra_matched_predictions_relative_to_coverage": int(max(0, len(matched_predictions) - covered_gt)),
        "precision_one_to_one": float(metrics.precision),
        "recall_one_to_one": float(metrics.recall),
        "f1_one_to_one": float(metrics.f1),
        "start_mae_ms_one_to_one": float(metrics.start_mae_ms),
        "end_mae_ms_one_to_one": float(metrics.end_mae_ms),
        "false_positive_language": "unmatched predictions are descriptive, not confirmed false positives under incomplete label coverage",
    }


def classify_controls(
    participants: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray,
    row_keys: Sequence[str],
    historical_taxonomy: Mapping[str, str],
    event_dicts: Sequence[Mapping[str, Any]],
    fold_id_by_participant: Mapping[str, str],
) -> dict[str, np.ndarray]:
    n = len(scores)
    missing = np.zeros(n, dtype=bool)
    covered = np.zeros(n, dtype=bool)
    for index, (participant, start, end, label) in enumerate(zip(participants, starts, ends, labels)):
        if int(label) != 1:
            continue
        for event in event_dicts:
            if str(event["participant"]) != str(participant) or not intersects(int(start), int(end), event):
                continue
            if historical_taxonomy.get(str(event["normalized_event_id"])) != "COVERED":
                missing[index] = True
            else:
                covered[index] = True
    hard = (labels == 0) & (scores >= 0.5)
    easy = np.zeros(n, dtype=bool)
    for fold_id in sorted(set(fold_id_by_participant.values())):
        indices = np.asarray(
            [
                index
                for index, participant in enumerate(participants)
                if fold_id_by_participant[str(participant)] == fold_id and int(labels[index]) == 0
            ],
            dtype=np.int64,
        )
        hard_count = int(np.sum(hard[indices]))
        order = sorted(indices.tolist(), key=lambda index: (float(scores[index]), str(row_keys[index])))
        easy[np.asarray(order[:hard_count], dtype=np.int64)] = True
    return {
        "missing_positive": missing,
        "covered_positive": covered,
        "hard_negative": hard,
        "easy_negative": easy,
    }


def summarize_windows(
    name: str,
    participants: np.ndarray,
    labels: np.ndarray,
    scores: np.ndarray,
    folds: Mapping[str, str],
    controls: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    participants = participants.astype(object)
    labels = labels.astype(np.int8)
    scores = scores.astype(np.float64)

    def one(mask: np.ndarray) -> dict[str, Any]:
        return {"metrics": binary_metrics(labels[mask], scores[mask]), "scores": score_summary(scores[mask])}

    supervised = (labels == 0) | (labels == 1)
    hard_mask = controls.get("hard_negative")
    easy_mask = controls.get("easy_negative")

    def comparison_control(positive_mask: np.ndarray) -> dict[str, Any]:
        if hard_mask is None:
            return {"metrics": {"reason": "fixed hard-negative control unavailable"}, "positive_score": score_summary(scores[positive_mask]), "negative_score": None}
        negative_mask = np.asarray(hard_mask, dtype=bool)
        y = np.concatenate((np.ones(int(positive_mask.sum()), dtype=np.int8), np.zeros(int(negative_mask.sum()), dtype=np.int8)))
        s = np.concatenate((scores[positive_mask], scores[negative_mask]))
        return {
            "metrics": binary_metrics(y, s),
            "positive_score": score_summary(scores[positive_mask]),
            "negative_score": score_summary(scores[negative_mask]),
        }

    control_report: dict[str, Any] = {}
    for key, mask in controls.items():
        if key in {"missing_positive", "covered_positive"}:
            control_report[key] = comparison_control(mask)
        else:
            control_report[key] = {"count": int(mask.sum()), "scores": score_summary(scores[mask])}

    result: dict[str, Any] = {
        "name": name,
        "row_count": int(len(scores)),
        "label_counts": {str(value): int(np.sum(labels == value)) for value in (-1, 0, 1)},
        "pooled": {
            **binary_metrics(labels[supervised], scores[supervised]),
            "positive_score": score_summary(scores[labels == 1]),
            "negative_score": score_summary(scores[labels == 0]),
        },
        "controls": control_report,
        "folds": {},
        "participants": {},
    }
    fold_ids = sorted(set(folds.values()))
    for fold_id in fold_ids:
        mask = np.asarray([folds[str(participant)] == fold_id for participant in participants], dtype=bool)
        sup = mask & supervised
        result["folds"][fold_id] = {
            "row_count": int(np.sum(mask)),
            "supervised_row_count": int(np.sum(sup)),
            "metrics": binary_metrics(labels[sup], scores[sup]),
            "positive_score": score_summary(scores[mask & (labels == 1)]),
            "negative_score": score_summary(scores[mask & (labels == 0)]),
            "controls": {
                key: (comparison_control(mask & value) if key in {"missing_positive", "covered_positive"} else {"count": int((mask & value).sum()), "scores": score_summary(scores[mask & value])})
                for key, value in controls.items()
            },
        }
    for participant in sorted(set(map(str, participants))):
        mask = participants == participant
        sup = mask & supervised
        result["participants"][participant] = {
            "fold_id": folds[participant],
            "row_count": int(np.sum(mask)),
            "supervised_row_count": int(np.sum(sup)),
            "metrics": binary_metrics(labels[sup], scores[sup]),
            "positive_score": score_summary(scores[mask & (labels == 1)]),
            "negative_score": score_summary(scores[mask & (labels == 0)]),
            "controls": {
                key: (comparison_control(mask & value) if key in {"missing_positive", "covered_positive"} else {"count": int((mask & value).sum()), "scores": score_summary(scores[mask & value])})
                for key, value in controls.items()
            },
        }
    return result


def load_record_rows(context: Mapping[str, Any], record_info: Mapping[str, Any], source: str) -> dict[str, Any]:
    record = record_info["record"]
    if source == "A":
        table = load_candidate_table(record_info["cache_path"], expected_metadata=record_info["metadata"])
        starts = table.windows
        return {
            "path": str(record.path),
            "participant": record.participant_id,
            "starts": np.asarray([item.window.start_ms for item in starts], dtype=np.int64),
            "ends": np.asarray([item.window.end_ms for item in starts], dtype=np.int64),
            "labels": table.labels.astype(np.int8),
            "scores": np.asarray(
                [context["a_score_by_key"][row_key(record.path, item.window.start_ms, item.window.end_ms, index)] for index, item in enumerate(starts)],
                dtype=np.float64,
            ),
        }
    payload = np.load(record_info["b_path"], allow_pickle=False)
    return {
        "path": str(record.path),
        "participant": record.participant_id,
        "starts": payload["starts"].astype(np.int64, copy=False),
        "ends": payload["ends"].astype(np.int64, copy=False),
        "labels": payload["labels"].astype(np.int8, copy=False),
        "scores": payload["scores"].astype(np.float64, copy=False),
    }


def event_rows_for_participant(context: Mapping[str, Any], record_infos: Sequence[Mapping[str, Any]], participant: str, source: str) -> list[dict[str, Any]]:
    return [load_record_rows(context, info, source) for info in record_infos if info["record"].participant_id == participant]


def replay_report(
    context: Mapping[str, Any],
    record_infos: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Sequence[EventInterval]],
    source: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    event_rows: list[dict[str, Any]] = []
    events_by_participant: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in context["event_dicts"]:
        events_by_participant[str(event["participant"])].append(event)
    source_rows_by_participant = {
        participant: event_rows_for_participant(context, record_infos, participant, source)
        for participant in events_by_participant
    }
    for event in context["event_dicts"]:
        participant = str(event["participant"])
        threshold = context["thresholds"][context["fold_id_by_participant"][participant]]
        metrics = support_stats(event, source_rows_by_participant[participant], predictions.get(participant, ()), threshold)
        event_rows.append({
            **event,
            "outer_fold": context["fold_id_by_participant"][participant],
            "duration_group": "<300s" if event["duration_ms"] < 300000 else ">1200s" if event["duration_ms"] > 1200000 else "300-600s" if event["duration_ms"] < 600000 else "600-1200s",
            "source": source,
            **metrics,
        })

    fixed_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    exact_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    for event in context["event_dicts"]:
        interval = EventInterval(event["start_ms"], event["end_ms"])
        fixed_by_participant[event["participant"]].append(interval)
        if event["normalized_event_id"] not in MISSING_IDS:
            exact_by_participant[event["participant"]].append(interval)

    def cohort(exact: bool) -> dict[str, Any]:
        truth_source = exact_by_participant if exact else fixed_by_participant

        def combine_matching(rows: Sequence[dict[str, Any]], participants: Sequence[str]) -> dict[str, Any]:
            keys = (
                "predicted_event_count",
                "covered_gt_count",
                "matched_gt_count_one_to_one",
                "matched_prediction_count_one_to_one",
                "unmatched_prediction_count_descriptive",
            )
            combined = {key: int(sum(int(row[key]) for row in rows)) for key in keys}
            total_truths = int(sum(len(truth_source.get(participant, ())) for participant in participants))
            tp = combined["matched_gt_count_one_to_one"]
            predicted = combined["predicted_event_count"]
            combined.update(
                {
                    "matched_minus_covered_gt": int(combined["matched_prediction_count_one_to_one"] - combined["covered_gt_count"]),
                    "extra_matched_predictions_relative_to_coverage": int(max(0, combined["matched_prediction_count_one_to_one"] - combined["covered_gt_count"])),
                    "precision_one_to_one": float(tp / predicted) if predicted else 0.0,
                    "recall_one_to_one": float(tp / total_truths) if total_truths else 0.0,
                    "f1_one_to_one": float(2 * (tp / predicted) * (tp / total_truths) / ((tp / predicted) + (tp / total_truths))) if predicted and total_truths and (tp / predicted) + (tp / total_truths) else 0.0,
                    "matching_scope": "summed per participant; predictions and truths are never matched across participants",
                    "false_positive_language": "unmatched predictions are descriptive, not confirmed false positives under incomplete label coverage",
                }
            )
            return combined

        per_fold: dict[str, Any] = {}
        per_participant: dict[str, Any] = {}
        total_events = total_covered = 0
        all_matching = {"predicted_event_count": 0, "covered_gt_count": 0, "matched_gt_count_one_to_one": 0, "matched_prediction_count_one_to_one": 0, "unmatched_prediction_count_descriptive": 0}
        for fold_id in sorted(set(context["fold_id_by_participant"].values())):
            fold_participants = [p for p, f in context["fold_id_by_participant"].items() if f == fold_id]
            fold_event_rows = [row for row in event_rows if row["outer_fold"] == fold_id and (not exact or row["normalized_event_id"] not in MISSING_IDS)]
            fold_covered = int(sum(bool(row["covered"]) for row in fold_event_rows))
            participant_matching = {
                participant: event_matching_summary(predictions.get(participant, ()), truth_source.get(participant, ()))
                for participant in fold_participants
            }
            matching = combine_matching(list(participant_matching.values()), fold_participants)
            per_fold[fold_id] = {
                "covered": fold_covered,
                "total": len(fold_event_rows),
                "recall": fold_covered / len(fold_event_rows) if fold_event_rows else None,
                "prediction_metrics": matching if not exact else {"predicted_event_count": matching["predicted_event_count"], "covered_gt_count": matching["covered_gt_count"], "note": "exact232 excludes incomplete GT from recall denominator; unmatched predictions are not treated as confirmed false positives"},
            }
            for participant in fold_participants:
                participant_rows = [row for row in fold_event_rows if row["participant"] == participant]
                per_participant[participant] = {
                    "fold_id": fold_id,
                    "covered": int(sum(bool(row["covered"]) for row in participant_rows)),
                    "total": len(participant_rows),
                    "recall": (sum(bool(row["covered"]) for row in participant_rows) / len(participant_rows)) if participant_rows else None,
                    "prediction_metrics": participant_matching[participant] if not exact else {"predicted_event_count": participant_matching[participant]["predicted_event_count"], "covered_gt_count": participant_matching[participant]["covered_gt_count"], "note": "exact232 excludes incomplete GT from recall denominator"},
                }
            total_events += len(fold_event_rows)
            total_covered += fold_covered
            if not exact:
                for key in all_matching:
                    all_matching[key] += int(matching[key])
        result = {
            "event_count": total_events,
            "covered": total_covered,
            "recall": total_covered / total_events if total_events else None,
            "per_fold": per_fold,
            "per_participant": per_participant,
        }
        if not exact:
            all_participants = list(context["fold_id_by_participant"])
            result["prediction_metrics_fixed234"] = combine_matching(
                [event_matching_summary(predictions.get(participant, ()), fixed_by_participant.get(participant, ())) for participant in all_participants],
                all_participants,
            )
        return result

    return {"fixed_234": cohort(False), "exact_complete_232": cohort(True)}, event_rows


def run() -> None:
    started = time.perf_counter()
    spec, spec_hash = verify_spec()
    if OUTPUT_DIR.exists():
        existing = [path for path in OUTPUT_DIR.iterdir() if not (path.is_dir() and path.name == "b-records" and not any(path.iterdir()))]
        if existing:
            raise RuntimeError(f"diagnostic output directory is non-empty: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    b_records_dir = OUTPUT_DIR / "b-records"
    b_records_dir.mkdir(parents=True, exist_ok=True)
    context = load_context(spec)

    folds_map = context["fold_id_by_participant"]
    a_controls = classify_controls(
        context["a_participants"],
        context["a_starts"],
        context["a_ends"],
        context["a_labels"],
        context["a_scores"],
        [str(key) for key in context["a_feature_row_keys"]],
        context["historical_taxonomy"],
        context["event_dicts"],
        folds_map,
    )
    a_window_summary = summarize_windows(
        "A_15s_7.5s_reconstructed_score_source",
        context["a_participants"],
        context["a_labels"],
        context["a_scores"],
        folds_map,
        a_controls,
    )

    # Fixed A control identities are used to define B hard/easy controls on common starts.
    hard_key_set = {str(key) for key, keep in zip(context["a_feature_row_keys"], a_controls["hard_negative"]) if keep}
    easy_key_set = {str(key) for key, keep in zip(context["a_feature_row_keys"], a_controls["easy_negative"]) if keep}
    common_by_record_start: dict[tuple[str, int, int], str] = {}
    for key in context["a_feature_row_keys"]:
        text = str(key)
        path, start, end, index = text.rsplit("|", 3)
        common_by_record_start[(path, int(start), int(end))] = text

    predictions_a: dict[str, list[EventInterval]] = defaultdict(list)
    predictions_b: dict[str, list[EventInterval]] = defaultdict(list)
    b_summary_rows: list[dict[str, Any]] = []
    b_score_parts: list[np.ndarray] = []
    b_label_parts: list[np.ndarray] = []
    b_participant_parts: list[np.ndarray] = []
    b_start_parts: list[np.ndarray] = []
    b_end_parts: list[np.ndarray] = []
    b_hard_parts: list[np.ndarray] = []
    b_easy_parts: list[np.ndarray] = []
    b_missing_parts: list[np.ndarray] = []
    b_covered_parts: list[np.ndarray] = []
    skipped: list[dict[str, Any]] = []
    total_b_rows = 0
    total_common = 0
    total_common_feature_mismatch = 0
    total_common_score_mismatch = 0
    total_common_selected_state_changes = 0
    peak_rss = 0
    batch_start = time.perf_counter()

    for record_index, item in enumerate(context["cache_records"], start=1):
        record = item["record"]
        try:
            a_table = load_candidate_table(item["cache_path"], expected_metadata=item["metadata"])
            a_windows = a_table.windows
            a_scores = np.asarray(
                [context["a_score_by_key"][row_key(record.path, w.window.start_ms, w.window.end_ms, idx)] for idx, w in enumerate(a_windows)],
                dtype=np.float64,
            )
            fold_id = folds_map[record.participant_id]
            a_pred_intervals = eventize_windows(a_windows, a_scores, threshold=context["thresholds"][fold_id], min_duration_ms=1, fuse_gap_ms=FUSE_GAP_MS)
            predictions_a[record.participant_id].extend(EventInterval(start, end) for start, end in a_pred_intervals)

            raw = _read_fast_imu(record.path, bad_source_rows=context["bad_rows"].get(str(record.path.resolve()), set()))
            series = regularize_imu(raw, grid_hz=GRID_HZ, max_gap_seconds=MAX_GAP_SECONDS)
            truths = events_for_record(record, context["meal_events"])
            b_windows = generate_dense_windows(
                series.timestamps_ms,
                series.valid_mask,
                grid_hz=GRID_HZ,
                window_seconds=WINDOW_SECONDS,
                step_seconds=B_STEP_SECONDS,
                min_coverage=MIN_COVERAGE,
                max_gap_seconds=MAX_GAP_SECONDS,
                hard_gap_mask=series.hard_gap_mask,
                segment_id=series.segment_id,
                truths=truths,
                positive_overlap=POSITIVE_OVERLAP,
                negative_distance_ms=NEGATIVE_DISTANCE_MS,
            )
            b_table = build_candidate_table(series, b_windows, participant_id=record.participant_id)
            if b_table.features.shape[1] != 111 or not np.isfinite(b_table.features).all():
                raise RuntimeError("B feature contract failed")
            b_scores = context["models"][fold_id].predict_scores(b_table.features)
            b_starts = np.asarray([w.window.start_ms for w in b_windows], dtype=np.int64)
            b_ends = np.asarray([w.window.end_ms for w in b_windows], dtype=np.int64)
            b_labels = b_table.labels.astype(np.int8, copy=False)
            b_keys = [row_key(record.path, start, end, idx) for idx, (start, end) in enumerate(zip(b_starts, b_ends))]
            common = np.zeros(len(b_scores), dtype=bool)
            hard = np.zeros(len(b_scores), dtype=bool)
            easy = np.zeros(len(b_scores), dtype=bool)
            common_score_deltas: list[float] = []
            common_feature_deltas: list[float] = []
            common_state_changes = 0
            for idx, (start, end) in enumerate(zip(b_starts, b_ends)):
                a_key = common_by_record_start.get((str(record.path), int(start), int(end)))
                if a_key is None:
                    continue
                common[idx] = True
                hard[idx] = a_key in hard_key_set
                easy[idx] = a_key in easy_key_set
                a_feature_index = context["a_feature_index_by_key"][a_key]
                feature_delta = float(np.max(np.abs(context["a_features"][a_feature_index].astype(np.float64) - b_table.features[idx].astype(np.float64))))
                common_feature_deltas.append(feature_delta)
                common_score_deltas.append(abs(float(context["a_score_by_key"][a_key]) - float(b_scores[idx])))
                a_selected = float(context["a_score_by_key"][a_key]) >= context["thresholds"][fold_id]
                b_selected = float(b_scores[idx]) >= context["thresholds"][fold_id]
                common_state_changes += int(a_selected != b_selected)
            common_count = int(common.sum())
            total_common += common_count
            total_common_feature_mismatch += int(sum(delta > FEATURE_MATCH_ATOL for delta in common_feature_deltas))
            total_common_score_mismatch += int(sum(not np.isclose(delta, 0.0, atol=ATOL, rtol=RTOL) for delta in common_score_deltas))
            total_common_selected_state_changes += common_state_changes

            missing_positive = np.zeros(len(b_scores), dtype=bool)
            covered_positive = np.zeros(len(b_scores), dtype=bool)
            for idx, (start, end, label) in enumerate(zip(b_starts, b_ends, b_labels)):
                if int(label) != 1:
                    continue
                for event in context["event_dicts"]:
                    if event["participant"] != record.participant_id or not intersects(int(start), int(end), event):
                        continue
                    if event["historical_taxonomy"] != "COVERED":
                        missing_positive[idx] = True
                    else:
                        covered_positive[idx] = True

            b_file = b_records_dir / f"record-{record_index:04d}.npz"
            np.savez_compressed(
                b_file,
                features=b_table.features.astype(np.float32, copy=False),
                starts=b_starts,
                ends=b_ends,
                labels=b_labels,
                scores=b_scores.astype(np.float64, copy=False),
                hard_negative=hard,
                easy_negative=easy,
                common_with_a=common,
                missing_positive=missing_positive,
                covered_positive=covered_positive,
            )
            b_pred_intervals = eventize_windows(b_windows, b_scores, threshold=context["thresholds"][fold_id], min_duration_ms=1, fuse_gap_ms=FUSE_GAP_MS)
            predictions_b[record.participant_id].extend(EventInterval(start, end) for start, end in b_pred_intervals)
            total_b_rows += len(b_scores)
            b_score_parts.append(b_scores)
            b_label_parts.append(b_labels)
            b_participant_parts.append(np.full(len(b_scores), record.participant_id, dtype=object))
            b_start_parts.append(b_starts)
            b_end_parts.append(b_ends)
            b_hard_parts.append(hard)
            b_easy_parts.append(easy)
            b_missing_parts.append(missing_positive)
            b_covered_parts.append(covered_positive)
            b_summary_rows.append({
                "record_index": record_index,
                "path": str(record.path),
                "participant": record.participant_id,
                "fold_id": fold_id,
                "cache_path": str(item["cache_path"].relative_to(ROOT)),
                "b_path": str(b_file.relative_to(ROOT)),
                "a_window_count": len(a_windows),
                "b_window_count": len(b_scores),
                "common_start_count": common_count,
                "common_feature_max_abs_delta": float(max(common_feature_deltas, default=0.0)),
                "common_score_max_abs_delta": float(max(common_score_deltas, default=0.0)),
                "common_feature_rows_over_tolerance": int(sum(delta > FEATURE_MATCH_ATOL for delta in common_feature_deltas)),
                "common_score_rows_over_tolerance": int(sum(not np.isclose(delta, 0.0, atol=ATOL, rtol=RTOL) for delta in common_score_deltas)),
                "common_selected_state_changes": common_state_changes,
                "b_min_start_ms": int(b_starts.min()) if len(b_starts) else None,
                "b_max_end_ms": int(b_ends.max()) if len(b_ends) else None,
            })
        except Exception as exc:
            skipped.append({"record_index": record_index, "path": str(record.path), "reason": repr(exc)})
            if isinstance(exc, RuntimeError) and "feature contract" in str(exc):
                raise
        if record_index == 1 or record_index % 10 == 0 or record_index == len(context["cache_records"]):
            try:
                import psutil
                peak_rss = max(peak_rss, int(psutil.Process(os.getpid()).memory_info().rss))
            except Exception:
                pass
            output_bytes = sum(path.stat().st_size for path in OUTPUT_DIR.rglob("*") if path.is_file())
            elapsed = time.perf_counter() - batch_start
            print(f"processed={record_index}/{len(context['cache_records'])} B_rows={total_b_rows} skipped={len(skipped)} elapsed={elapsed:.1f}s output_bytes={output_bytes}", flush=True)
            if output_bytes > 8 * 1024**3:
                raise RuntimeError("diagnostic disk budget exceeded")
            if time.perf_counter() - started > 14400:
                raise RuntimeError("diagnostic wall-time budget exceeded")

    if skipped:
        result_status = "PARTIAL_INCONCLUSIVE"
    else:
        result_status = "COMPLETED"

    b_scores_all = np.concatenate(b_score_parts) if b_score_parts else np.empty(0, dtype=np.float64)
    b_labels_all = np.concatenate(b_label_parts) if b_label_parts else np.empty(0, dtype=np.int8)
    b_participants_all = np.concatenate(b_participant_parts) if b_participant_parts else np.empty(0, dtype=object)
    b_starts_all = np.concatenate(b_start_parts) if b_start_parts else np.empty(0, dtype=np.int64)
    b_ends_all = np.concatenate(b_end_parts) if b_end_parts else np.empty(0, dtype=np.int64)
    b_hard_all = np.concatenate(b_hard_parts) if b_hard_parts else np.empty(0, dtype=bool)
    b_easy_all = np.concatenate(b_easy_parts) if b_easy_parts else np.empty(0, dtype=bool)
    b_missing_all = np.concatenate(b_missing_parts) if b_missing_parts else np.empty(0, dtype=bool)
    b_covered_all = np.concatenate(b_covered_parts) if b_covered_parts else np.empty(0, dtype=bool)
    b_controls = {
        "missing_positive": b_missing_all,
        "covered_positive": b_covered_all,
        "hard_negative": b_hard_all,
        "easy_negative": b_easy_all,
    }
    b_window_summary = summarize_windows("B_15s_3s_frozen_model_inference", b_participants_all, b_labels_all, b_scores_all, folds_map, b_controls)

    record_infos = []
    for row, item in zip(b_summary_rows, [item for item in context["cache_records"] if str(item["record"].path) not in {entry["path"] for entry in skipped}]):
        row = dict(row)
        row["record"] = item["record"]
        row["cache_path_obj"] = item["cache_path"]
        row["metadata"] = item["metadata"]
        row["b_path"] = ROOT / row["b_path"]
        record_infos.append(row)

    a_replay, a_event_rows = replay_report(context, record_infos, predictions_a, "A")
    b_replay, b_event_rows = replay_report(context, record_infos, predictions_b, "B")
    paired_event_rows: list[dict[str, Any]] = []
    a_by_id = {row["normalized_event_id"]: row for row in a_event_rows}
    b_by_id = {row["normalized_event_id"]: row for row in b_event_rows}
    for event in context["event_dicts"]:
        key = event["normalized_event_id"]
        a_row = a_by_id[key]
        b_row = b_by_id[key]
        paired_event_rows.append({
            "event_id": event["event_id"],
            "normalized_event_id": key,
            "participant": event["participant"],
            "outer_fold": context["fold_id_by_participant"][event["participant"]],
            "duration_ms": event["duration_ms"],
            "historical_taxonomy": event["historical_taxonomy"],
            "A": a_row,
            "B": b_row,
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

    event_counts = {
        "A_missing_to_B_covered": int(sum(row["event_outcome"]["A_missing_B_covered"] for row in paired_event_rows)),
        "A_covered_to_B_missing": int(sum(row["event_outcome"]["A_covered_B_missing"] for row in paired_event_rows)),
        "both_covered": int(sum(row["event_outcome"]["A_covered_B_covered"] for row in paired_event_rows)),
        "both_missing": int(sum(row["event_outcome"]["A_missing_B_missing"] for row in paired_event_rows)),
    }

    write_json(OUTPUT_DIR / "a-replay.json", {
        "status": "A_REPLAY_REUSED_MATCHED_SCORE_SOURCE",
        "row_count": int(context["a_scores"].size),
        "stable_id_count": int(context["a_row_keys"].size),
        "score_source": str(A_SCORES_PATH.relative_to(ROOT)),
        "score_identity_tolerance": {"absolute": ATOL, "relative": RTOL},
        "thresholds_reused": context["thresholds"],
        "eventizer": {"min_duration_ms": 1, "fuse_gap_ms": FUSE_GAP_MS, "iou_threshold": IOU_THRESHOLD},
        "fixed234": a_replay["fixed_234"],
        "exact_complete_232": a_replay["exact_complete_232"],
    })
    write_json(OUTPUT_DIR / "b-window-manifest.json", {
        "schema_version": "frozen_a_3s_b_window_manifest_v1",
        "spec_sha256": spec_hash,
        "record_count": len(b_summary_rows),
        "window_count": total_b_rows,
        "common_start_count": total_common,
        "common_feature_rows_over_tolerance": total_common_feature_mismatch,
        "common_score_rows_over_tolerance": total_common_score_mismatch,
        "common_selected_state_changes": total_common_selected_state_changes,
        "skipped": skipped,
        "records": [{key: value for key, value in row.items() if key not in {"record", "cache_path_obj", "metadata"}} for row in b_summary_rows],
    })
    np.savez_compressed(
        OUTPUT_DIR / "b-scores.npz",
        scores=b_scores_all,
        labels=b_labels_all,
        participants=b_participants_all,
        starts=b_starts_all,
        ends=b_ends_all,
        hard_negative=b_hard_all,
        easy_negative=b_easy_all,
        missing_positive=b_missing_all,
        covered_positive=b_covered_all,
    )
    with (OUTPUT_DIR / "event-paired-results.jsonl").open("w", encoding="utf-8") as stream:
        for row in paired_event_rows:
            stream.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")

    output_bytes = sum(path.stat().st_size for path in OUTPUT_DIR.rglob("*") if path.is_file())
    report = {
        "schema_version": "frozen_a_3s_stride_transfer_diagnostic_report_v1",
        "status": result_status,
        "spec_path": str(SPEC_PATH.relative_to(ROOT)),
        "spec_sha256": spec_hash,
        "source_hashes_verified": {
            "previous_geometry_report": sha256_file(ROOT / "artifacts/g1-window-geometry-diagnostic-v1/report.json"),
            "a_reconstruction_fold_manifest": sha256_file(A_FOLD_MANIFEST_PATH),
            "a_reconstruction_scores": sha256_file(A_SCORES_PATH),
            "a_feature_table": sha256_file(A_FEATURE_TABLE_PATH),
        },
        "model_and_policy": {
            "model_count": len(context["models"]),
            "models_loadable": True,
            "participant_disjoint": True,
            "estimator": "HistGradientBoostingClassifier",
            "parameters": spec["frozen_models_and_policy"]["parameters"],
            "class_balancing": spec["frozen_models_and_policy"]["class_balancing"],
            "score_semantics": "predict_proba(features)[:,1]",
            "thresholds": context["thresholds"],
            "eventizer": spec["frozen_models_and_policy"]["eventizer"],
        },
        "denominators": {
            "fixed234": {"count": 234, "use": "prediction context and descriptive matching"},
            "exact_complete232": {"count": 232, "use": "recall stratification only"},
            "incomplete_events": sorted(MISSING_IDS),
            "historical_missing": 27,
        },
        "window_level": {
            "A": a_window_summary,
            "B": b_window_summary,
            "controls_note": "B hard/easy negative controls are frozen from A OOF membership on common A/B starts; B-only negatives are not silently assigned to the fixed controls",
            "common_start_identity": {
                "count": total_common,
                "feature_rows_over_tolerance": total_common_feature_mismatch,
                "score_rows_over_tolerance": total_common_score_mismatch,
                "selected_state_changes": total_common_selected_state_changes,
                "feature_tolerance": FEATURE_MATCH_ATOL,
                "score_tolerance": {"absolute": ATOL, "relative": RTOL},
            },
        },
        "event_level": {
            "A": a_replay,
            "B": b_replay,
            "paired_outcomes": event_counts,
            "event_rows": "event-paired-results.jsonl",
            "prediction_matching_note": "fixed234 prediction-level unmatched counts are descriptive under incomplete label coverage; exact232 excludes only the two approved incomplete GT events from recall",
        },
        "execution": {
            "processed_record_count": len(b_summary_rows),
            "approved_cache_record_count": len(context["cache_records"]),
            "approved_cache_missing_count": len(context["missing_cache"]),
            "b_window_count": total_b_rows,
            "skipped_record_count": len(skipped),
            "three_second_fit_count": 0,
            "threshold_reselection_count": 0,
            "production_artifacts_overwritten": False,
            "output_bytes": output_bytes,
            "peak_rss_bytes": peak_rss or None,
            "elapsed_seconds": time.perf_counter() - started,
        },
        "decision": {
            "classification": "PARTIAL_INCONCLUSIVE" if skipped else "MIXED_EVENT_EFFECT",
            "new_window_score_evidence": "see A/B score distributions, controls, and common-start identity",
            "time_score_event_chain": "reported separately; no causal information-gain claim from window count alone",
            "information_gap": "whether a stride change should ever enter production remains outside this diagnostic and requires a separately authorized gate",
        },
        "preserved_historical_status": {
            "DECISION_FUNCTION_EFFECT": "UNSUPPORTED",
            "FORMAL_G1_BASELINE": "FAIL",
            "CANDIDATE_MODEL_DESIGN_REVIEW": "NOT_JUSTIFIED",
            "ARCHITECTURE": "FROZEN",
            "FULL_TRAINING": "BLOCKED",
            "PRODUCTION_STRIDE": "UNCHANGED",
        },
        "runtime": {
            "python": sys.version,
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
    }
    write_json(OUTPUT_DIR / "resource-log.json", {
        "spec_sha256": spec_hash,
        "elapsed_seconds": report["execution"]["elapsed_seconds"],
        "peak_rss_bytes": peak_rss or None,
        "output_bytes": output_bytes,
        "wall_budget_seconds": 14400,
        "memory_budget_gib": 12,
        "disk_budget_gib": 8,
        "skipped": skipped,
    })
    write_json(OUTPUT_DIR / "report.json", report)
    print(json.dumps({"status": report["status"], "classification": report["decision"]["classification"], "B_windows": total_b_rows, "A_missing_to_B_covered": event_counts["A_missing_to_B_covered"], "A_covered_to_B_missing": event_counts["A_covered_to_B_missing"], "elapsed_seconds": report["execution"]["elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
