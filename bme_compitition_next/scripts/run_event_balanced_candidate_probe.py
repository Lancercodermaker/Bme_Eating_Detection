"""Run the one-shot event-balanced candidate-objective diagnostic.

The runner has two explicit phases:

* ``prepare``: resolve and audit the frozen positive-row event ownership, then
  write an independent diagnostic sidecar.  No estimator is fitted.
* ``run``: verify the frozen specification and sidecar, then execute exactly
  the pre-registered A/E nested participant-disjoint fits.

This script does not write production caches or formal-gate artifacts.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
from typing import Any, Iterable

import numpy as np

try:
    import joblib
except ImportError as exc:  # pragma: no cover - environment failure
    raise RuntimeError("joblib is required for estimator preservation") from exc

from eating_event.cache import load_candidate_table
from eating_event.candidates import eventize_windows
from eating_event.coverage import (
    G1_CANDIDATE_FUSE_GAP_MS,
    G1_CANDIDATE_QUANTILE_GRID,
    QuantileResult,
    deduplicate_event_intervals,
    select_candidate_quantile,
)
from eating_event.diagnostic_event_balanced import (
    fit_diagnostic_candidate_model,
    unique_overlapping_event_ids,
)
from eating_event.evaluation import build_inner_folds, build_outer_folds
from eating_event.metrics import EventInterval, evaluate_events, interval_iou


PROBE_ID = "g1-event-balanced-candidate-objective-probe-v1"
FEATURE_TABLE_PATH = Path("artifacts/g1-temporal-representation-probe-v1/feature-table.npz")
ELIGIBILITY_PATH = Path("artifacts/g1-candidate-coverage-v4/eligibility.json")
CACHE_MANIFEST_PATH = Path("artifacts/g1-candidate-coverage-v4/cache-manifest.json")
DEFAULT_OUTPUT = Path("artifacts") / PROBE_ID
DEFAULT_SIDECAR = DEFAULT_OUTPUT / "positive-row-event-map.jsonl"
DEFAULT_PREFIT_AUDIT = DEFAULT_OUTPUT / "prefit-label-audit.json"


class ResourceBudgetExceeded(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def event_id_for(row: dict[str, Any]) -> str:
    return f"{row['participant_id']}:{int(row['start_ms'])}:{int(row['end_ms'])}"


def load_eligible_events(eligibility_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = load_json(eligibility_path)
    if payload.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("event-balanced probe requires participant_eligibility_v3")
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in payload.get("event_eligibility", []):
        if not bool(row.get("training_eligibility")):
            continue
        event = {
            "event_id": event_id_for(row),
            "event_index": int(row["event_index"]),
            "participant_id": str(row["participant_id"]),
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
            "duration_ms": int(row["end_ms"]) - int(row["start_ms"]),
        }
        if event["event_id"] in by_id:
            raise ValueError(f"duplicate eligible event identity: {event['event_id']}")
        rows.append(event)
        by_id[event["event_id"]] = event
    rows.sort(key=lambda row: (row["participant_id"], row["start_ms"], row["end_ms"], row["event_index"]))
    if len(rows) != 234:
        raise ValueError(f"expected 234 training-eligible events, found {len(rows)}")
    return rows, by_id


def _row_key(path: str, start_ms: int, end_ms: int, within_record_index: int) -> str:
    return f"{path}|{int(start_ms)}|{int(end_ms)}|{within_record_index}"


def prepare_sidecar(
    *,
    feature_table_path: Path = FEATURE_TABLE_PATH,
    eligibility_path: Path = ELIGIBILITY_PATH,
    output_path: Path = DEFAULT_SIDECAR,
    audit_path: Path = DEFAULT_PREFIT_AUDIT,
) -> dict[str, Any]:
    """Build the independent positive-row -> event sidecar and audit it."""

    events, event_by_id = load_eligible_events(eligibility_path)
    with np.load(feature_table_path, allow_pickle=True) as payload:
        participants = payload["participants"].astype(str, copy=False)
        starts = payload["starts"].astype(np.int64, copy=False)
        ends = payload["ends"].astype(np.int64, copy=False)
        labels = payload["labels"].astype(np.int8, copy=False)
        row_keys = payload["row_keys"].astype(str, copy=False)
        features = payload["a"]
        feature_names = payload["metadata"].item()
    if features.ndim != 2 or features.shape[1] != 111:
        raise ValueError("frozen feature table is not 111D imu_stats_v1")
    if row_keys.size != np.unique(row_keys).size:
        raise ValueError("frozen feature-table row_keys are not unique")
    if not (participants.size == starts.size == ends.size == labels.size == row_keys.size == features.shape[0]):
        raise ValueError("frozen feature table arrays are not aligned")

    owners, ownership_counts = unique_overlapping_event_ids(
        participants, starts, ends, labels, events
    )
    positive_indexes = np.flatnonzero(labels == 1)
    records: list[dict[str, Any]] = []
    for index in positive_indexes:
        owner = str(owners[index])
        event = event_by_id[owner]
        records.append(
            {
                "row_key": str(row_keys[index]),
                "participant_id": str(participants[index]),
                "window_start_ms": int(starts[index]),
                "window_end_ms": int(ends[index]),
                "event_id": owner,
                "event_index": int(event["event_index"]),
            }
        )
    records.sort(key=lambda row: row["row_key"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            stream.write("\n")
    temporary.replace(output_path)
    sidecar_hash = sha256_file(output_path)
    label_counts = {str(value): int((labels == value).sum()) for value in (-1, 0, 1)}
    audit = {
        "probe_id": PROBE_ID,
        "phase": "PREFIT_LABEL_CONTRACT_AUDIT",
        "feature_table": {
            "path": str(feature_table_path),
            "sha256": sha256_file(feature_table_path),
            "rows": int(labels.size),
            "feature_width": int(features.shape[1]),
            "representation": "imu_stats_v1",
            "metadata_raw": str(feature_names),
            "label_counts": label_counts,
            "row_keys_unique_count": int(np.unique(row_keys).size),
        },
        "eligible_event_count": len(events),
        "ownership": ownership_counts,
        "contract_result": "PASS"
        if ownership_counts["zero_owner"] == 0
        and ownership_counts["multi_owner"] == 0
        and ownership_counts["max_owner"] == 1
        else "FAIL",
        "sidecar": {
            "path": str(output_path),
            "sha256": sidecar_hash,
            "positive_row_count": len(records),
            "format": "JSONL sorted by row_key; one row per positive row",
        },
        "source_of_truth": {
            "labels": "feature_table.npz labels; no inner-valid or outer-valid labels used",
            "event_identity": "participant_id:start_ms:end_ms from training-eligible event_eligibility rows",
            "ownership_rule": "half-open window/event overlap; exactly one eligible event required",
        },
    }
    write_json(audit_path, audit)
    return audit


def load_sidecar(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row["row_key"])
            value = str(row["event_id"])
            if key in mapping:
                raise ValueError(f"duplicate sidecar row_key at line {line_number}: {key}")
            mapping[key] = value
    return mapping


def _current_rss_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except ImportError:
        return 0


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _check_budget(start_time: float, output_root: Path, budget: dict[str, Any], peak_rss: int) -> int:
    elapsed = time.monotonic() - start_time
    rss = _current_rss_bytes()
    peak_rss = max(peak_rss, rss)
    if elapsed > float(budget["wall_time_seconds"]):
        raise ResourceBudgetExceeded("wall-time budget exceeded")
    if peak_rss and peak_rss > float(budget["memory_gib"]) * (1024**3):
        raise ResourceBudgetExceeded("memory budget exceeded")
    if _directory_bytes(output_root) > float(budget["diagnostic_disk_gib"]) * (1024**3):
        raise ResourceBudgetExceeded("diagnostic disk budget exceeded")
    return peak_rss


def _interval_from_event(event: dict[str, Any]) -> EventInterval:
    return EventInterval(int(event["start_ms"]), int(event["end_ms"]))


def _event_bin(event: dict[str, Any], support_count: int) -> dict[str, str]:
    duration_seconds = int(event["duration_ms"]) / 1000.0
    if duration_seconds < 300:
        duration_bin = "<300s"
    elif duration_seconds > 1200:
        duration_bin = ">1200s"
    else:
        duration_bin = "300-1200s"
    if support_count < 10:
        support_bin = "<10"
    elif support_count < 25:
        support_bin = "10-24"
    elif support_count < 50:
        support_bin = "25-49"
    else:
        support_bin = ">=50"
    return {"duration": duration_bin, "positive_windows": support_bin}


def _score_stats(values: np.ndarray, threshold: float) -> dict[str, Any]:
    scores = np.asarray(values, dtype=np.float64)
    if scores.size == 0:
        return {
            "count": 0,
            "median": None,
            "p90": None,
            "max": None,
            "above_threshold_count": 0,
            "above_threshold_fraction": None,
        }
    above = scores >= threshold
    return {
        "count": int(scores.size),
        "median": float(np.median(scores)),
        "p90": float(np.quantile(scores, 0.90)),
        "max": float(np.max(scores)),
        "above_threshold_count": int(above.sum()),
        "above_threshold_fraction": float(above.mean()),
    }


def _safe_auc(labels: np.ndarray, scores: np.ndarray) -> dict[str, float | None]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(labels, dtype=np.int8)
    s = np.asarray(scores, dtype=np.float64)
    if y.size == 0 or np.unique(y).size < 2:
        return {"auroc": None, "auprc": None}
    return {
        "auroc": float(roc_auc_score(y, s)),
        "auprc": float(average_precision_score(y, s)),
    }


def _flatten(items_by_participant: dict[str, list[dict[str, Any]]], participants: Iterable[str]) -> list[dict[str, Any]]:
    return [entry for participant in participants for entry in items_by_participant.get(participant, [])]


def _fit_arrays(items: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not items:
        raise ValueError("fit subset is empty")
    return (
        np.vstack([entry["table"].features for entry in items]),
        np.concatenate([entry["table"].labels for entry in items]),
        np.concatenate([entry["event_ids"] for entry in items]),
    )


def _model_path(output_root: Path, variant: str, kind: str, fold_id: str, suffix: str = "") -> Path:
    return output_root / "models" / variant / kind / f"{fold_id}{suffix}.joblib"


def _save_model(model: object, path: Path, probe_features: np.ndarray) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path, compress=3)
    loaded = joblib.load(path)
    before = model.predict_scores(probe_features)
    after = loaded.predict_scores(probe_features)
    if not np.array_equal(before, after):
        raise ValueError(f"serialized estimator score mismatch: {path}")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "loadable": True,
        "probe_score_identity": True,
    }


def _event_truths_for_entry(events_by_participant: dict[str, list[dict[str, Any]]], participant: str, table: Any) -> list[EventInterval]:
    if not table.windows:
        return []
    start = min(window.window.start_ms for window in table.windows)
    end = max(window.window.end_ms for window in table.windows)
    return [
        _interval_from_event(event)
        for event in events_by_participant.get(participant, [])
        if int(event["start_ms"]) < end and int(event["end_ms"]) > start
    ]


def load_frozen_entries(
    *,
    cache_manifest_path: Path,
    eligibility_path: Path,
    sidecar_path: Path,
    expected_rows: int,
    expected_positive_rows: int,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    events, event_by_id = load_eligible_events(eligibility_path)
    events_by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_participant[event["participant_id"]].append(event)
    row_to_event = load_sidecar(sidecar_path)
    manifest = load_json(cache_manifest_path)
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("cache manifest lacks entries")
    tables_by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_row_keys: set[str] = set()
    seen_positive_keys: set[str] = set()
    total_rows = 0
    label_counts = {-1: 0, 0: 0, 1: 0}
    feature_names: tuple[str, ...] | None = None
    for manifest_entry in raw_entries:
        participant = str(manifest_entry["participant_id"])
        path = str(manifest_entry["path"])
        table = load_candidate_table(Path(str(manifest_entry["cache_path"])))
        if table.features.shape[1] != 111:
            raise ValueError(f"cache feature width is not 111: {path}")
        if feature_names is None:
            feature_names = table.feature_names
        elif table.feature_names != feature_names:
            raise ValueError("cache feature schema changed across records")
        if not np.all(table.participant_ids.astype(str) == participant):
            raise ValueError(f"cache participant IDs mismatch manifest: {path}")
        local_keys = [
            _row_key(path, record.window.start_ms, record.window.end_ms, index)
            for index, record in enumerate(table.windows)
        ]
        if len(local_keys) != len(set(local_keys)):
            raise ValueError(f"duplicate row keys within cache: {path}")
        duplicate = all_row_keys.intersection(local_keys)
        if duplicate:
            raise ValueError(f"duplicate row keys across caches: {next(iter(duplicate))}")
        all_row_keys.update(local_keys)
        event_ids = np.empty(table.labels.size, dtype=object)
        event_ids[:] = None
        for index, (key, label) in enumerate(zip(local_keys, table.labels)):
            label_counts[int(label)] += 1
            if int(label) == 1:
                if key not in row_to_event:
                    raise ValueError(f"positive cache row missing from event sidecar: {key}")
                event_id = row_to_event[key]
                if event_id not in event_by_id:
                    raise ValueError(f"sidecar refers to unknown eligible event: {event_id}")
                event_ids[index] = event_id
                seen_positive_keys.add(key)
        entry = {
            "participant_id": participant,
            "path": path,
            "table": table,
            "event_ids": event_ids,
            "row_keys": local_keys,
            "truths": _event_truths_for_entry(events_by_participant, participant, table),
        }
        tables_by_participant[participant].append(entry)
        total_rows += int(table.labels.size)
    if total_rows != expected_rows:
        raise ValueError(f"cache row count mismatch: {total_rows} != {expected_rows}")
    if label_counts != {-1: 13007, 0: 583145, 1: expected_positive_rows}:
        raise ValueError(f"cache label counts mismatch: {label_counts}")
    if len(seen_positive_keys) != expected_positive_rows or seen_positive_keys != set(row_to_event):
        raise ValueError("cache positive rows and sidecar positive rows are not identical")
    support_counts = {event_id: 0 for event_id in event_by_id}
    for entries in tables_by_participant.values():
        for entry in entries:
            for event_id in entry["event_ids"]:
                if event_id is not None:
                    support_counts[str(event_id)] += 1
    if any(count <= 0 for count in support_counts.values()):
        missing = [event_id for event_id, count in support_counts.items() if count <= 0]
        raise ValueError(f"eligible events lack positive cache support: {missing[:3]}")
    stats = {
        "record_count": len(raw_entries),
        "participant_count": len(tables_by_participant),
        "row_count": total_rows,
        "positive_row_count": label_counts[1],
        "negative_row_count": label_counts[0],
        "ignore_row_count": label_counts[-1],
        "event_count": len(event_by_id),
    }
    return tables_by_participant, events, support_counts


def _evaluate(
    *,
    model: Any,
    fit_items: list[dict[str, Any]],
    valid_items: list[dict[str, Any]],
    quantile: float | None = None,
    threshold: float | None = None,
    events: list[dict[str, Any]],
    support_counts: dict[str, int],
    collect_event_rows: bool,
) -> dict[str, Any]:
    fit_scores = np.concatenate([model.predict_scores(entry["table"].features) for entry in fit_items])
    if threshold is None:
        if quantile is None:
            raise ValueError("quantile or threshold is required")
        threshold = float(np.quantile(fit_scores, quantile))
    threshold = float(threshold)
    predictions: dict[str, list[EventInterval]] = defaultdict(list)
    truths: dict[str, list[EventInterval]] = defaultdict(list)
    valid_labels: list[np.ndarray] = []
    valid_scores: list[np.ndarray] = []
    candidate_count = 0
    event_score_values: dict[str, list[float]] = defaultdict(list)
    score_rows: list[dict[str, Any]] = []
    for entry in valid_items:
        scores = model.predict_scores(entry["table"].features)
        table = entry["table"]
        valid_mask = table.labels >= 0
        valid_labels.append(table.labels[valid_mask])
        valid_scores.append(scores[valid_mask])
        for event_id, score in zip(entry["event_ids"], scores):
            if event_id is not None:
                event_score_values[str(event_id)].append(float(score))
        intervals = [
            EventInterval(start, end)
            for start, end in eventize_windows(
                table.windows,
                scores,
                threshold=threshold,
                min_duration_ms=1,
                fuse_gap_ms=G1_CANDIDATE_FUSE_GAP_MS,
            )
        ]
        predictions[entry["participant_id"]].extend(intervals)
        truths[entry["participant_id"]].extend(entry["truths"])
        candidate_count += len(intervals)
        score_rows.append(
            {
                "row_keys": entry["row_keys"],
                "labels": table.labels.astype(np.int8, copy=True),
                "scores": scores,
                "participants": table.participant_ids.astype(str, copy=True),
                "starts": np.asarray([window.window.start_ms for window in table.windows], dtype=np.int64),
                "ends": np.asarray([window.window.end_ms for window in table.windows], dtype=np.int64),
                "event_ids": entry["event_ids"],
            }
        )

    pooled_covered = 0
    pooled_total = 0
    participant_recall: dict[str, float] = {}
    event_metrics_by_participant: dict[str, Any] = {}
    event_outcomes: dict[str, bool] = {}
    for participant in sorted(truths):
        participant_truths = deduplicate_event_intervals(truths[participant])
        participant_predictions = predictions[participant]
        covered = sum(
            1
            for truth in participant_truths
            if any(interval_iou(prediction, truth) > 0.25 for prediction in participant_predictions)
        )
        pooled_covered += covered
        pooled_total += len(participant_truths)
        participant_recall[participant] = covered / len(participant_truths) if participant_truths else 1.0
        metrics = evaluate_events(participant_predictions, participant_truths, iou_threshold=0.25)
        event_metrics_by_participant[participant] = {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "start_mae_ms": metrics.start_mae_ms,
            "end_mae_ms": metrics.end_mae_ms,
            "prediction_count": len(participant_predictions),
            "truth_count": len(participant_truths),
        }
    for event in events:
        participant = str(event["participant_id"])
        if participant not in predictions:
            continue
        truth = _interval_from_event(event)
        event_outcomes[event["event_id"]] = any(
            interval_iou(prediction, truth) > 0.25 for prediction in predictions[participant]
        )
    all_valid_labels = np.concatenate(valid_labels) if valid_labels else np.empty(0, dtype=np.int8)
    all_valid_scores = np.concatenate(valid_scores) if valid_scores else np.empty(0, dtype=np.float64)
    auc = _safe_auc(all_valid_labels, all_valid_scores)
    for event_id, values in event_score_values.items():
        summary = _score_stats(np.asarray(values, dtype=np.float64), threshold)
        score_rows.append({"event_score_summary": event_id, **summary})
    aggregate_metrics = {
        "tp": int(sum(row["tp"] for row in event_metrics_by_participant.values())),
        "fp": int(sum(row["fp"] for row in event_metrics_by_participant.values())),
        "fn": int(sum(row["fn"] for row in event_metrics_by_participant.values())),
        "candidate_count": int(candidate_count),
    }
    aggregate_metrics["precision"] = (
        aggregate_metrics["tp"] / (aggregate_metrics["tp"] + aggregate_metrics["fp"])
        if aggregate_metrics["tp"] + aggregate_metrics["fp"]
        else 0.0
    )
    aggregate_metrics["recall"] = (
        aggregate_metrics["tp"] / (aggregate_metrics["tp"] + aggregate_metrics["fn"])
        if aggregate_metrics["tp"] + aggregate_metrics["fn"]
        else 0.0
    )
    aggregate_metrics["f1"] = (
        2 * aggregate_metrics["precision"] * aggregate_metrics["recall"]
        / (aggregate_metrics["precision"] + aggregate_metrics["recall"])
        if aggregate_metrics["precision"] + aggregate_metrics["recall"]
        else 0.0
    )
    aggregate_metrics["prediction_count"] = aggregate_metrics["candidate_count"]
    return {
        "threshold": threshold,
        "pooled_covered": int(pooled_covered),
        "pooled_total": int(pooled_total),
        "pooled_recall": pooled_covered / pooled_total if pooled_total else 0.0,
        "participant_recall": participant_recall,
        "candidate_count": int(candidate_count),
        "window_metrics": auc,
        "event_metrics": aggregate_metrics,
        "event_metrics_by_participant": event_metrics_by_participant,
        "event_outcomes": event_outcomes,
        "event_score_values": event_score_values,
        "score_rows": score_rows,
        "valid_labels": all_valid_labels,
        "valid_scores": all_valid_scores,
    }


def _save_oof_scores(output_root: Path, variant: str, fold_id: str, score_rows: list[dict[str, Any]]) -> str:
    row_keys = np.asarray([key for row in score_rows if "row_keys" in row for key in row["row_keys"]], dtype=str)
    labels = np.concatenate([row["labels"] for row in score_rows if "labels" in row])
    scores = np.concatenate([row["scores"] for row in score_rows if "scores" in row])
    participants = np.concatenate([row["participants"] for row in score_rows if "participants" in row])
    starts = np.concatenate([row["starts"] for row in score_rows if "starts" in row])
    ends = np.concatenate([row["ends"] for row in score_rows if "ends" in row])
    event_ids = np.concatenate([row["event_ids"] for row in score_rows if "event_ids" in row])
    if not (row_keys.size == labels.size == scores.size == participants.size == starts.size == ends.size == event_ids.size):
        raise ValueError("OOF score arrays are not aligned")
    destination = output_root / "oof-scores" / variant / f"{fold_id}.npz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        destination,
        row_keys=row_keys,
        labels=labels,
        scores=scores,
        participants=participants,
        starts=starts,
        ends=ends,
        event_ids=event_ids,
    )
    return str(destination)


def _summarize_variant_events(
    outcomes_by_fold: list[dict[str, Any]],
    events: list[dict[str, Any]],
    support_counts: dict[str, int],
) -> dict[str, Any]:
    by_event: dict[str, bool] = {}
    event_fold: dict[str, str] = {}
    for fold in outcomes_by_fold:
        for event_id, covered in fold["event_outcomes"].items():
            by_event[event_id] = bool(covered)
            event_fold[event_id] = fold["fold_id"]
    rows = []
    for event in events:
        event_id = event["event_id"]
        if event_id not in by_event:
            continue
        rows.append(
            {
                **event,
                "fold_id": event_fold[event_id],
                "positive_window_count": support_counts[event_id],
                "covered": by_event[event_id],
                "strata": _event_bin(event, support_counts[event_id]),
            }
        )
    strata: dict[str, dict[str, int]] = {}
    for row in rows:
        for dimension, value in row["strata"].items():
            key = f"{dimension}:{value}"
            summary = strata.setdefault(key, {"covered": 0, "total": 0})
            summary["total"] += 1
            summary["covered"] += int(row["covered"])
    for summary in strata.values():
        summary["recall"] = summary["covered"] / summary["total"] if summary["total"] else 0.0
    return {
        "event_rows": rows,
        "covered": sum(bool(row["covered"]) for row in rows),
        "total": len(rows),
        "recall": sum(bool(row["covered"]) for row in rows) / len(rows) if rows else 0.0,
        "strata": strata,
    }


def _participant_comparison(
    event_rows_a: list[dict[str, Any]], event_rows_e: list[dict[str, Any]]
) -> dict[str, Any]:
    a_by = defaultdict(lambda: {"covered": 0, "total": 0})
    e_by = defaultdict(lambda: {"covered": 0, "total": 0})
    for row in event_rows_a:
        a_by[row["participant_id"]]["total"] += 1
        a_by[row["participant_id"]]["covered"] += int(row["covered"])
    for row in event_rows_e:
        e_by[row["participant_id"]]["total"] += 1
        e_by[row["participant_id"]]["covered"] += int(row["covered"])
    result = {}
    for participant in sorted(set(a_by) | set(e_by)):
        result[participant] = {
            "A": a_by[participant],
            "E": e_by[participant],
            "A_recall": a_by[participant]["covered"] / a_by[participant]["total"] if a_by[participant]["total"] else 0.0,
            "E_recall": e_by[participant]["covered"] / e_by[participant]["total"] if e_by[participant]["total"] else 0.0,
        }
    return result


def _verify_frozen_spec(spec_path: Path, spec_hash_path: Path) -> dict[str, Any]:
    spec = load_json(spec_path)
    if spec.get("status") != "FROZEN_BEFORE_FIT":
        raise ValueError("event-balanced probe spec is not frozen before fit")
    digest = sha256_file(spec_path)
    hash_text = spec_hash_path.read_text(encoding="utf-8").strip().split()[0]
    if digest != hash_text:
        raise ValueError(f"spec hash sidecar mismatch: {digest} != {hash_text}")
    for source in spec["source_of_truth"]["files"]:
        path = Path(source["path"])
        actual = sha256_file(path)
        if actual != source["sha256"]:
            raise ValueError(f"source hash drift: {path}: {actual} != {source['sha256']}")
    sidecar = Path(spec["row_event_sidecar"]["path"])
    actual_sidecar_hash = sha256_file(sidecar)
    if actual_sidecar_hash != spec["row_event_sidecar"]["sha256"]:
        raise ValueError("row-event sidecar hash drift")
    return spec


def run_probe(spec_path: Path, spec_hash_path: Path) -> dict[str, Any]:
    spec = _verify_frozen_spec(spec_path, spec_hash_path)
    output_root = Path(spec["outputs"]["diagnostic_directory"])
    if any((output_root / "models").rglob("*.joblib")) if (output_root / "models").exists() else False:
        raise RuntimeError("diagnostic models already exist; one-shot probe will not retry")
    output_root.mkdir(parents=True, exist_ok=True)
    start_time = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    peak_rss = _current_rss_bytes()
    budget = spec["resource_budget"]
    sidecar_path = Path(spec["row_event_sidecar"]["path"])
    tables_by_participant, events, support_counts = load_frozen_entries(
        cache_manifest_path=Path(spec["inputs"]["cache_manifest_path"]),
        eligibility_path=Path(spec["inputs"]["eligibility_path"]),
        sidecar_path=sidecar_path,
        expected_rows=int(spec["inputs"]["rows"]),
        expected_positive_rows=int(spec["inputs"]["positive_rows"]),
    )
    participants = tuple(sorted(tables_by_participant))
    if "test" in {value.lower() for value in participants}:
        raise ValueError("test participant reached event-balanced probe")
    folds = build_outer_folds(participants, n_folds=5, seed=20260910)
    if len(folds) != 5:
        raise ValueError("outer fold count drifted")
    inner_fold_counts = [len(build_inner_folds(fold.train_participants, n_folds=4, seed=20260910)) for fold in folds]
    if inner_fold_counts != [4, 4, 4, 4, 4]:
        raise ValueError(f"inner fold count drifted: {inner_fold_counts}")
    fold_manifest = {
        fold.fold_id: {
            "train_participants": list(fold.train_participants),
            "valid_participants": list(fold.valid_participants),
            "inner_fold_count": 4,
        }
        for fold in folds
    }
    write_json(output_root / "fold-manifest.json", fold_manifest)
    expected_fit_count = int(spec["fit_budget"]["total_fits"])
    actual_fit_count = 0
    variant_results: dict[str, Any] = {}
    models_manifest: list[dict[str, Any]] = []
    thresholds: dict[str, dict[str, float]] = {"A": {}, "E": {}}

    def fit_variant(items: list[dict[str, Any]], variant: str, save_path: Path) -> tuple[Any, dict[str, Any]]:
        nonlocal actual_fit_count, peak_rss
        _check_budget(start_time, output_root, budget, peak_rss)
        features, labels, event_ids = _fit_arrays(items)
        model, audit = fit_diagnostic_candidate_model(
            features,
            labels,
            event_ids,
            variant=variant,
            random_state=20260910,
            max_iter=100,
        )
        actual_fit_count += 1
        peak_rss = max(peak_rss, _current_rss_bytes())
        probe_features = features[: min(3, features.shape[0])]
        model_record = _save_model(model, save_path, probe_features)
        models_manifest.append({"variant": variant, "fit_index": actual_fit_count, **model_record, "weight_audit": audit})
        peak_rss = _check_budget(start_time, output_root, budget, peak_rss)
        return model, audit

    for variant in ("A", "E"):
        fold_results: list[dict[str, Any]] = []
        for fold in folds:
            outer_train_items = _flatten(tables_by_participant, fold.train_participants)
            outer_valid_items = _flatten(tables_by_participant, fold.valid_participants)
            inner_folds = build_inner_folds(fold.train_participants, n_folds=4, seed=20260910)
            quantile_results: list[QuantileResult] = []
            inner_records: list[dict[str, Any]] = []
            for quantile in G1_CANDIDATE_QUANTILE_GRID:
                inner_rows: list[tuple[float, float, int]] = []
                for inner in inner_folds:
                    inner_train_items = _flatten(tables_by_participant, inner.train_participants)
                    inner_valid_items = _flatten(tables_by_participant, inner.valid_participants)
                    inner_model_path = _model_path(
                        output_root, variant, "inner", fold.fold_id, f"-{inner.fold_id}-q{quantile:.2f}"
                    )
                    model, audit = fit_variant(inner_train_items, variant, inner_model_path)
                    evaluated = _evaluate(
                        model=model,
                        fit_items=inner_train_items,
                        valid_items=inner_valid_items,
                        quantile=quantile,
                        events=events,
                        support_counts=support_counts,
                        collect_event_rows=False,
                    )
                    inner_rows.append(
                        (
                            float(evaluated["pooled_recall"]),
                            min(evaluated["participant_recall"].values(), default=1.0),
                            int(evaluated["candidate_count"]),
                        )
                    )
                    inner_records.append(
                        {
                            "outer_fold": fold.fold_id,
                            "inner_fold": inner.fold_id,
                            "quantile": quantile,
                            "pooled_recall": evaluated["pooled_recall"],
                            "worst_participant_recall": min(evaluated["participant_recall"].values(), default=1.0),
                            "candidate_count": evaluated["candidate_count"],
                            "model_path": str(inner_model_path),
                            "weight_audit": audit,
                        }
                    )
                quantile_results.append(
                    QuantileResult(
                        quantile=float(quantile),
                        pooled_recall=float(np.mean([row[0] for row in inner_rows])),
                        worst_participant_recall=float(min((row[1] for row in inner_rows), default=0.0)),
                        candidate_count=int(sum(row[2] for row in inner_rows)),
                    )
                )
            selected = select_candidate_quantile(quantile_results)
            outer_model_path = _model_path(output_root, variant, "outer", fold.fold_id)
            outer_model, outer_audit = fit_variant(outer_train_items, variant, outer_model_path)
            outer_evaluated = _evaluate(
                model=outer_model,
                fit_items=outer_train_items,
                valid_items=outer_valid_items,
                threshold=None,
                quantile=selected.quantile,
                events=events,
                support_counts=support_counts,
                collect_event_rows=True,
            )
            thresholds[variant][fold.fold_id] = float(outer_evaluated["threshold"])
            oof_path = _save_oof_scores(output_root, variant, fold.fold_id, outer_evaluated["score_rows"])
            fold_results.append(
                {
                    "fold_id": fold.fold_id,
                    "train_participant_count": len(fold.train_participants),
                    "valid_participant_count": len(fold.valid_participants),
                    "valid_participants": list(fold.valid_participants),
                    "selected_quantile": float(selected.quantile),
                    "inner_quantile_results": [
                        {
                            "quantile": result.quantile,
                            "pooled_recall": result.pooled_recall,
                            "worst_participant_recall": result.worst_participant_recall,
                            "candidate_count": result.candidate_count,
                        }
                        for result in quantile_results
                    ],
                    "inner_fit_records": inner_records,
                    "outer_threshold": outer_evaluated["threshold"],
                    "outer_weight_audit": outer_audit,
                    "pooled_covered": outer_evaluated["pooled_covered"],
                    "pooled_total": outer_evaluated["pooled_total"],
                    "pooled_recall": outer_evaluated["pooled_recall"],
                    "participant_recall": outer_evaluated["participant_recall"],
                    "candidate_count": outer_evaluated["candidate_count"],
                    "window_metrics": outer_evaluated["window_metrics"],
                    "event_metrics": outer_evaluated["event_metrics"],
                    "event_metrics_by_participant": outer_evaluated["event_metrics_by_participant"],
                    "event_outcomes": outer_evaluated["event_outcomes"],
                    "model": models_manifest[-1],
                    "oof_scores": oof_path,
                }
            )
            write_json(output_root / "inner-selection" / variant / f"{fold.fold_id}.json", {
                "quantile_results": [
                    {
                        "quantile": result.quantile,
                        "pooled_recall": result.pooled_recall,
                        "worst_participant_recall": result.worst_participant_recall,
                        "candidate_count": result.candidate_count,
                    }
                    for result in quantile_results
                ],
                "selected_quantile": selected.quantile,
                "records": inner_records,
            })
        variant_summary = _summarize_variant_events(fold_results, events, support_counts)
        variant_results[variant] = {
            "folds": fold_results,
            "event_summary": variant_summary,
            "g1_numeric_criterion_met": all(float(row["pooled_recall"]) >= 0.90 for row in fold_results),
            "fold_recall_values": [float(row["pooled_recall"]) for row in fold_results],
            "pooled_covered": variant_summary["covered"],
            "pooled_total": variant_summary["total"],
            "pooled_recall": variant_summary["recall"],
        }
        peak_rss = _check_budget(start_time, output_root, budget, peak_rss)

    if actual_fit_count != expected_fit_count:
        raise RuntimeError(f"fit count mismatch: {actual_fit_count} != {expected_fit_count}")
    a_rows = variant_results["A"]["event_summary"]["event_rows"]
    e_rows = variant_results["E"]["event_summary"]["event_rows"]
    a_by_id = {row["event_id"]: row for row in a_rows}
    e_by_id = {row["event_id"]: row for row in e_rows}
    recovered = [event_id for event_id in sorted(a_by_id) if not a_by_id[event_id]["covered"] and e_by_id[event_id]["covered"]]
    newly_lost = [event_id for event_id in sorted(a_by_id) if a_by_id[event_id]["covered"] and not e_by_id[event_id]["covered"]]
    both_covered = [event_id for event_id in sorted(a_by_id) if a_by_id[event_id]["covered"] and e_by_id[event_id]["covered"]]
    both_missing = [event_id for event_id in sorted(a_by_id) if not a_by_id[event_id]["covered"] and not e_by_id[event_id]["covered"]]
    elapsed = time.monotonic() - start_time
    peak_rss = max(peak_rss, _current_rss_bytes())
    disk_bytes = _directory_bytes(output_root)
    resource_status = {
        "within_wall_time": elapsed <= float(budget["wall_time_seconds"]),
        "within_memory": not peak_rss or peak_rss <= float(budget["memory_gib"]) * (1024**3),
        "within_diagnostic_disk": disk_bytes <= float(budget["diagnostic_disk_gib"]) * (1024**3),
    }
    report = {
        "probe_id": PROBE_ID,
        "status": "COMPLETED",
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "spec": {"path": str(spec_path), "sha256": sha256_file(spec_path)},
        "inputs": {
            "rows": int(spec["inputs"]["rows"]),
            "positive_rows": int(spec["inputs"]["positive_rows"]),
            "event_count": len(events),
            "participant_count": len(participants),
            "cache_record_count": sum(len(items) for items in tables_by_participant.values()),
        },
        "variants": variant_results,
        "comparison": {
            "recovered_events": recovered,
            "newly_lost_events": newly_lost,
            "both_covered_events": both_covered,
            "both_missing_events": both_missing,
            "net_coverage_change": len(recovered) - len(newly_lost),
            "participant_results": _participant_comparison(a_rows, e_rows),
            "event_rows_A_vs_E": {
                event_id: {"A": a_by_id[event_id], "E": e_by_id[event_id]}
                for event_id in sorted(a_by_id)
            },
        },
        "g1_numeric_criterion_met": {
            "A": variant_results["A"]["g1_numeric_criterion_met"],
            "E": variant_results["E"]["g1_numeric_criterion_met"],
            "criterion": "all 5 participant-disjoint outer fold pooled recalls >= 0.90",
        },
        "resource_status": {
            "budget": budget,
            "actual_fit_count": actual_fit_count,
            "expected_fit_count": expected_fit_count,
            "elapsed_seconds": elapsed,
            "peak_rss_bytes": peak_rss,
            "diagnostic_disk_bytes": disk_bytes,
            **resource_status,
            "status": "WITHIN_BUDGET" if all(resource_status.values()) else "OVER_BUDGET",
        },
        "diagnostic_limitations": [
            "A and E reuse the previously analyzed outer participants and are diagnostic candidate results, not independent confirmation.",
            "A/B comparison is limited to the single preregistered event-balanced formula; no weight sweep or clipping was run.",
            "Formal G1 status and production artifacts were not modified by this probe.",
        ],
        "preserved_status": {
            "PRODUCTION": "UNCHANGED",
            "FULL_TRAINING": "BLOCKED",
            "ARCHITECTURE_REPLACEMENT": "NOT_AUTHORIZED",
        },
        "models_manifest": models_manifest,
        "thresholds": thresholds,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
    }
    write_json(output_root / "models-manifest.json", models_manifest)
    write_json(output_root / "thresholds.json", thresholds)
    write_json(output_root / "report.json", report)
    write_json(output_root / "run-status.json", {"status": "COMPLETED", "report": str(output_root / "report.json")})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    parser.add_argument("--spec", type=Path, default=Path("configs/formal-g1-event-balanced-candidate-objective-probe-v1.json"))
    parser.add_argument("--spec-hash", type=Path, default=Path("configs/formal-g1-event-balanced-candidate-objective-probe-v1.sha256"))
    parser.add_argument("--feature-table", type=Path, default=FEATURE_TABLE_PATH)
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.mode == "prepare":
        audit = prepare_sidecar(
            feature_table_path=args.feature_table,
            eligibility_path=args.eligibility,
            output_path=args.output / "positive-row-event-map.jsonl",
            audit_path=args.output / "prefit-label-audit.json",
        )
        print(json.dumps(audit, indent=2, sort_keys=True))
        return
    report = run_probe(args.spec, args.spec_hash)
    print(json.dumps({"status": report["status"], "report": str(args.output / "report.json")}, indent=2))


if __name__ == "__main__":
    main()
