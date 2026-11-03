"""One-shot, proposal-only feasibility diagnostic.

The runner consumes one already-frozen A score lineage.  It never fits a
model, never reads labels while generating proposals, and writes only below
the independent bounded-proposal diagnostic artifact directory.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any

import joblib
import numpy as np

from eating_event.cache import load_candidate_table
from eating_event.candidates import eventize_windows
from eating_event.diagnostic_bounded_proposal import (
    Proposal,
    WindowEvidence,
    build_extra_proposals,
    union_proposals,
)
from eating_event.metrics import EventInterval, evaluate_events, interval_iou


ROOT = Path(__file__).resolve().parents[1]
PROBE_ID = "g1-bounded-proposal-set-feasibility-probe-v1"
DEFAULT_SPEC = ROOT / "configs" / f"formal-g1-{PROBE_ID.removeprefix('g1-')}.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / PROBE_ID
EXPECTED_FOLDS = tuple(f"outer-{index}" for index in range(5))
IOU_THRESHOLD = 0.25
FUSE_GAP_MS = 300_000


class ResourceBudgetExceeded(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def _rss_bytes() -> int:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except ImportError:
        return 0


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _budget_check(start_time: float, output_root: Path, budget: dict[str, Any], peak_rss: int) -> int:
    elapsed = time.monotonic() - start_time
    peak_rss = max(peak_rss, _rss_bytes())
    if elapsed > float(budget["wall_time_seconds"]):
        raise ResourceBudgetExceeded("wall-time budget exceeded")
    if peak_rss and peak_rss > float(budget["memory_gib"]) * 1024**3:
        raise ResourceBudgetExceeded("memory budget exceeded")
    if _directory_bytes(output_root) > float(budget["diagnostic_disk_gib"]) * 1024**3:
        raise ResourceBudgetExceeded("diagnostic disk budget exceeded")
    return peak_rss


def _resolve(path_text: str) -> Path:
    candidate = Path(path_text)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _verify_spec(spec_path: Path, spec_hash_path: Path | None = None) -> dict[str, Any]:
    spec = load_json(spec_path)
    sidecar = spec_hash_path or spec_path.with_suffix(".sha256")
    sidecar_text = sidecar.read_text(encoding="utf-8").strip().split()
    if not sidecar_text:
        raise ValueError(f"empty spec hash sidecar: {sidecar}")
    actual_spec_hash = sha256_file(spec_path)
    if sidecar_text[0].lower() != actual_spec_hash:
        raise ValueError("spec hash sidecar does not match spec")
    if spec.get("probe_id") != PROBE_ID:
        raise ValueError("unexpected bounded-proposal probe id")
    if spec.get("status") != "FROZEN_BEFORE_EVALUATION":
        raise ValueError("proposal spec is not frozen")
    for source in spec.get("source_artifacts", []):
        path = _resolve(str(source["path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != str(source["sha256"]).lower():
            raise ValueError(f"source hash mismatch: {path}")
    return spec


def _event_id(row: dict[str, Any]) -> str:
    return f"{row['participant_id']}:{int(row['start_ms'])}:{int(row['end_ms'])}"


def _load_events(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = load_json(path)
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in payload.get("event_eligibility", []):
        if not bool(row.get("training_eligibility")):
            continue
        event = {
            "event_id": _event_id(row),
            "event_index": int(row["event_index"]),
            "participant_id": str(row["participant_id"]),
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
            "duration_ms": int(row["end_ms"]) - int(row["start_ms"]),
            "positive_window_count": int(row.get("dense_window_count", 0)),
        }
        if event["event_id"] in by_id:
            raise ValueError(f"duplicate event id: {event['event_id']}")
        by_id[event["event_id"]] = event
        rows.append(event)
    rows.sort(key=lambda row: (row["participant_id"], row["start_ms"], row["end_ms"], row["event_index"]))
    if len(rows) != 234:
        raise ValueError(f"expected 234 eligible events, found {len(rows)}")
    return rows, by_id


def _row_key(path: str, start_ms: int, end_ms: int, index: int) -> str:
    return f"{path}|{int(start_ms)}|{int(end_ms)}|{index}"


def _load_entries(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = load_json(manifest_path)
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != 1127:
        raise ValueError("cache manifest does not contain the frozen 1127 records")
    entries: dict[str, dict[str, Any]] = {}
    feature_names: tuple[str, ...] | None = None
    total_rows = 0
    label_counts = {-1: 0, 0: 0, 1: 0}
    for raw in raw_entries:
        path = str(raw["path"])
        if path in entries:
            raise ValueError(f"duplicate recording path: {path}")
        cache_path = _resolve(str(raw["cache_path"]))
        if sha256_file(cache_path) != str(raw["cache_sha256"]).lower():
            raise ValueError(f"cache hash mismatch: {cache_path}")
        table = load_candidate_table(cache_path)
        if table.features.ndim != 2 or table.features.shape[1] != 111:
            raise ValueError(f"cache is not 111D imu_stats_v1: {path}")
        names = tuple(table.feature_names)
        if feature_names is None:
            feature_names = names
        elif names != feature_names:
            raise ValueError("feature schema changed across caches")
        participant = str(raw["participant_id"])
        if not np.all(table.participant_ids.astype(str) == participant):
            raise ValueError(f"participant mismatch in cache: {path}")
        keys = tuple(
            _row_key(path, record.window.start_ms, record.window.end_ms, index)
            for index, record in enumerate(table.windows)
        )
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate local row key: {path}")
        for label in table.labels:
            label_counts[int(label)] += 1
        total_rows += int(table.labels.size)
        entries[path] = {
            "path": path,
            "participant_id": participant,
            "session_id": str(raw["session_id"]),
            "cache_path": str(cache_path),
            "table": table,
            "row_keys": keys,
        }
    if total_rows != 632100 or label_counts != {-1: 13007, 0: 583145, 1: 35948}:
        raise ValueError(f"cache totals changed: rows={total_rows}, labels={label_counts}")
    return entries


def _load_folds(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    if tuple(payload) != EXPECTED_FOLDS:
        raise ValueError("unexpected outer fold ids")
    result: dict[str, dict[str, Any]] = {}
    for fold_id in EXPECTED_FOLDS:
        row = payload[fold_id]
        result[fold_id] = {
            "train_participants": tuple(str(value) for value in row["train_participants"]),
            "valid_participants": tuple(str(value) for value in row["valid_participants"]),
        }
        if set(result[fold_id]["train_participants"]) & set(result[fold_id]["valid_participants"]):
            raise ValueError(f"participant overlap in {fold_id}")
    return result


def _load_thresholds(path: Path) -> dict[str, float]:
    payload = load_json(path)
    values = {fold_id: float(payload["A"][fold_id]) for fold_id in EXPECTED_FOLDS}
    expected = {
        "outer-0": 0.32291220845742846,
        "outer-1": 0.31925593834148336,
        "outer-2": 0.3172483958521495,
        "outer-3": 0.34283713198829047,
        "outer-4": 0.3247059067028039,
    }
    for fold_id in EXPECTED_FOLDS:
        if not math.isclose(values[fold_id], expected[fold_id], rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"A threshold lineage mismatch in {fold_id}")
    return values


def _load_oof_fold(
    path: Path,
    entries: dict[str, dict[str, Any]],
    valid_participants: set[str],
) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as payload:
        keys = payload["row_keys"].astype(str, copy=False)
        labels = payload["labels"].astype(np.int8, copy=False)
        scores = payload["scores"].astype(np.float64, copy=False)
        participants = payload["participants"].astype(str, copy=False)
        starts = payload["starts"].astype(np.int64, copy=False)
        ends = payload["ends"].astype(np.int64, copy=False)
    if not (keys.size == labels.size == scores.size == participants.size == starts.size == ends.size):
        raise ValueError(f"OOF arrays misaligned: {path}")
    by_path: dict[str, np.ndarray] = {}
    seen: set[str] = set()
    for row_key, label, score, participant, start_ms, end_ms in zip(keys, labels, scores, participants, starts, ends):
        path_text, start_text, end_text, index_text = str(row_key).rsplit("|", 3)
        if path_text not in entries:
            raise ValueError(f"OOF row refers to unknown recording: {path_text}")
        entry = entries[path_text]
        if str(participant) != entry["participant_id"] or str(participant) not in valid_participants:
            raise ValueError(f"OOF participant/fold mismatch: {row_key}")
        index = int(index_text)
        if index < 0 or index >= len(entry["row_keys"]):
            raise ValueError(f"OOF local index out of range: {row_key}")
        if str(row_key) != entry["row_keys"][index] or int(start_text) != int(start_ms) or int(end_text) != int(end_ms):
            raise ValueError(f"OOF row-key alignment mismatch: {row_key}")
        if path_text not in by_path:
            by_path[path_text] = np.full(len(entry["row_keys"]), np.nan, dtype=np.float64)
        if not np.isnan(by_path[path_text][index]):
            raise ValueError(f"duplicate OOF row: {row_key}")
        table_label = int(entry["table"].labels[index])
        if table_label != int(label):
            raise ValueError(f"OOF label mismatch: {row_key}")
        by_path[path_text][index] = float(score)
        seen.add(path_text)
    expected_paths = {
        path_text
        for path_text, entry in entries.items()
        if entry["participant_id"] in valid_participants
    }
    if seen != expected_paths or any(np.isnan(values).any() for values in by_path.values()):
        raise ValueError("OOF coverage does not exactly match the outer-valid recordings")
    return by_path


def _baseline_proposals(path: str, entry: dict[str, Any], scores: np.ndarray, threshold: float) -> tuple[Proposal, ...]:
    windows = entry["table"].windows
    selected = sorted(
        (
            record.window.start_ms,
            record.window.end_ms,
            index,
            float(score),
        )
        for index, (record, score) in enumerate(zip(windows, scores))
        if float(score) >= threshold
    )
    if not selected:
        return ()
    proposals: list[Proposal] = []
    current_start, current_end = selected[0][0], selected[0][1]
    current_indices = [selected[0][2]]
    current_scores = [selected[0][3]]
    for start_ms, end_ms, index, score in selected[1:]:
        if start_ms <= current_end + FUSE_GAP_MS:
            current_end = max(current_end, end_ms)
            current_indices.append(index)
            current_scores.append(score)
            continue
        if current_end > current_start:
            proposals.append(
                Proposal(
                    path,
                    current_start,
                    current_end,
                    "A",
                    ("baseline",),
                    tuple(sorted(current_indices)),
                    max(current_scores),
                    sum(current_scores) / len(current_scores),
                )
            )
        current_start, current_end = start_ms, end_ms
        current_indices = [index]
        current_scores = [score]
    if current_end > current_start:
        proposals.append(
            Proposal(
                path,
                current_start,
                current_end,
                "A",
                ("baseline",),
                tuple(sorted(current_indices)),
                max(current_scores),
                sum(current_scores) / len(current_scores),
            )
        )
    return tuple(proposals)


def _extra_proposals(path: str, entry: dict[str, Any], scores: np.ndarray, threshold: float, rule: dict[str, Any]) -> tuple[Proposal, ...]:
    windows = tuple(
        WindowEvidence(
            index=index,
            start_ms=int(record.window.start_ms),
            end_ms=int(record.window.end_ms),
            score=float(score),
            crosses_hard_gap=bool(record.crosses_hard_gap),
        )
        for index, (record, score) in enumerate(zip(entry["table"].windows, scores))
    )
    return build_extra_proposals(
        path,
        windows,
        support_threshold=threshold,
        stride_ms=int(rule["stride_ms"]),
        min_support_windows=int(rule["min_support_windows"]),
        max_per_recording=int(rule["max_extra_per_recording"]),
        max_per_hour=int(rule["max_extra_per_hour"]),
    )


def _truths_by_participant(events: list[dict[str, Any]]) -> dict[str, list[EventInterval]]:
    truths: dict[str, list[EventInterval]] = defaultdict(list)
    for event in events:
        truths[event["participant_id"]].append(EventInterval(event["start_ms"], event["end_ms"]))
    return dict(truths)


def _event_strata(event: dict[str, Any]) -> dict[str, str]:
    duration = int(event["duration_ms"])
    support = int(event["positive_window_count"])
    if duration < 300_000:
        duration_bin = "<300s"
    elif duration > 1_200_000:
        duration_bin = ">1200s"
    else:
        duration_bin = "300-1200s"
    if support < 10:
        support_bin = "<10"
    elif support < 25:
        support_bin = "10-24"
    elif support < 50:
        support_bin = "25-49"
    else:
        support_bin = ">=50"
    return {"duration": duration_bin, "positive_windows": support_bin}


def _evaluate_variant(
    proposals_by_path: dict[str, tuple[Proposal, ...]],
    valid_paths: set[str],
    entries: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    predictions: dict[str, list[EventInterval]] = defaultdict(list)
    candidate_count = 0
    durations: list[int] = []
    for path in sorted(valid_paths):
        entry = entries[path]
        proposals = proposals_by_path.get(path, ())
        participant = entry["participant_id"]
        predictions[participant].extend(EventInterval(item.start_ms, item.end_ms) for item in proposals)
        candidate_count += len(proposals)
        durations.extend(item.end_ms - item.start_ms for item in proposals)

    truths = _truths_by_participant(events)
    event_outcomes: dict[str, bool] = {}
    participant_results: dict[str, Any] = {}
    covered = 0
    total = 0
    fp = tp = fn = 0
    for participant in sorted({entries[path]["participant_id"] for path in valid_paths}):
        participant_predictions = predictions.get(participant, [])
        participant_truths = truths.get(participant, [])
        metrics = evaluate_events(participant_predictions, participant_truths, iou_threshold=IOU_THRESHOLD)
        tp += metrics.tp
        fp += metrics.fp
        fn += metrics.fn
        participant_results[participant] = {
            "covered": sum(
                any(interval_iou(prediction, truth) > IOU_THRESHOLD for prediction in participant_predictions)
                for truth in participant_truths
            ),
            "total": len(participant_truths),
            "candidate_count": len(participant_predictions),
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "start_mae_ms": metrics.start_mae_ms,
            "end_mae_ms": metrics.end_mae_ms,
        }
        covered += int(participant_results[participant]["covered"])
        total += len(participant_truths)

    for event in events:
        participant = event["participant_id"]
        if participant not in participant_results:
            continue
        truth = EventInterval(event["start_ms"], event["end_ms"])
        event_outcomes[event["event_id"]] = any(
            interval_iou(prediction, truth) > IOU_THRESHOLD
            for prediction in predictions.get(participant, [])
        )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "covered": int(covered),
        "total": int(total),
        "recall": covered / total if total else 0.0,
        "candidate_count": int(candidate_count),
        "candidate_duration_ms": {
            "count": len(durations),
            "median": float(np.median(durations)) if durations else None,
            "p90": float(np.quantile(durations, 0.90)) if durations else None,
            "max": int(max(durations)) if durations else None,
        },
        "event_metrics": {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "event_outcomes": event_outcomes,
        "participant_results": participant_results,
    }


def _window_hours(paths: set[str], entries: dict[str, dict[str, Any]]) -> float:
    total_ms = 0
    for path in paths:
        windows = entries[path]["table"].windows
        if windows:
            total_ms += int(windows[-1].window.end_ms) - int(windows[0].window.start_ms)
    return total_ms / 3_600_000


def _proposal_stats(
    baseline_by_path: dict[str, tuple[Proposal, ...]],
    extra_by_path: dict[str, tuple[Proposal, ...]],
    union_by_path: dict[str, tuple[Proposal, ...]],
    valid_paths: set[str],
    entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline = [item for path in valid_paths for item in baseline_by_path.get(path, ())]
    extra = [item for path in valid_paths for item in extra_by_path.get(path, ())]
    union = [item for path in valid_paths for item in union_by_path.get(path, ())]
    base_keys = {(item.record_path, item.start_ms, item.end_ms) for item in baseline}
    extra_keys = {(item.record_path, item.start_ms, item.end_ms) for item in extra}
    exact_duplicates = len(base_keys & extra_keys)
    duration_hours = _window_hours(valid_paths, entries)
    return {
        "baseline_count": len(baseline),
        "extra_count": len(extra),
        "extra_exact_duplicate_count": exact_duplicates,
        "union_count": len(union),
        "new_interval_count": len(union) - len(baseline),
        "union_growth_fraction": (len(union) - len(baseline)) / len(baseline) if baseline else None,
        "recording_hours": duration_hours,
        "baseline_candidates_per_hour": len(baseline) / duration_hours if duration_hours else None,
        "extra_candidates_per_hour": len(extra) / duration_hours if duration_hours else None,
        "union_candidates_per_hour": len(union) / duration_hours if duration_hours else None,
        "extra_overlap_with_baseline_count": sum(
            any(
                interval_iou(EventInterval(item.start_ms, item.end_ms), EventInterval(other.start_ms, other.end_ms)) > 0
                for other in baseline
                if other.record_path == item.record_path
            )
            for item in extra
        ),
        "extra_duration_stats_ms": {
            "median": float(np.median([item.end_ms - item.start_ms for item in extra])) if extra else None,
            "p90": float(np.quantile([item.end_ms - item.start_ms for item in extra], 0.90)) if extra else None,
            "max": int(max((item.end_ms - item.start_ms for item in extra), default=0)),
        },
    }


def _proposal_record(proposal: Proposal, fold_id: str) -> dict[str, Any]:
    return {
        "fold_id": fold_id,
        "record_path": proposal.record_path,
        "start_ms": proposal.start_ms,
        "end_ms": proposal.end_ms,
        "source": proposal.source,
        "boundary_variants": list(proposal.boundary_variants),
        "source_window_indices": list(proposal.source_indices),
        "segment_id": proposal.segment_id,
        "region_id": proposal.region_id,
        "support_max": proposal.support_max,
        "support_mean": proposal.support_mean,
    }


def _build_event_rows(
    events: list[dict[str, Any]],
    fold_by_participant: dict[str, str],
    baseline_by_event: dict[str, bool],
    union_by_event: dict[str, bool],
    extra_by_path: dict[str, tuple[Proposal, ...]],
    entries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths_by_participant: dict[str, list[str]] = defaultdict(list)
    for path, entry in entries.items():
        paths_by_participant[entry["participant_id"]].append(path)
    for event in events:
        participant = event["participant_id"]
        truth = EventInterval(event["start_ms"], event["end_ms"])
        contributing: list[dict[str, Any]] = []
        for path in paths_by_participant.get(participant, []):
            for proposal in extra_by_path.get(path, ()):
                candidate = EventInterval(proposal.start_ms, proposal.end_ms)
                if interval_iou(candidate, truth) > IOU_THRESHOLD:
                    contributing.append(
                        {
                            "record_path": path,
                            "start_ms": proposal.start_ms,
                            "end_ms": proposal.end_ms,
                            "boundary_variants": list(proposal.boundary_variants),
                            "segment_id": proposal.segment_id,
                            "region_id": proposal.region_id,
                            "iou": interval_iou(candidate, truth),
                        }
                    )
        rows.append(
            {
                **event,
                "fold_id": fold_by_participant[participant],
                "strata": _event_strata(event),
                "A_covered": bool(baseline_by_event[event["event_id"]]),
                "union_covered": bool(union_by_event[event["event_id"]]),
                "recovered": not baseline_by_event[event["event_id"]] and union_by_event[event["event_id"]],
                "newly_lost": baseline_by_event[event["event_id"]] and not union_by_event[event["event_id"]],
                "extra_contributors": sorted(contributing, key=lambda item: (-item["iou"], item["start_ms"], item["end_ms"])),
            }
        )
    return rows


def run(spec_path: Path, output_root: Path) -> dict[str, Any]:
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    spec = _verify_spec(spec_path)
    budget = spec["resource_budget"]
    if (output_root / "report.json").is_file():
        raise FileExistsError(f"completed diagnostic output already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    source = spec["lineage"]
    events, event_by_id = _load_events(_resolve(source["eligibility_path"]))
    entries = _load_entries(_resolve(source["cache_manifest_path"]))
    folds = _load_folds(_resolve(source["fold_manifest_path"]))
    thresholds = _load_thresholds(_resolve(source["thresholds_path"]))
    peak_rss = _budget_check(started, output_root, budget, 0)

    fold_results: list[dict[str, Any]] = []
    all_event_rows: dict[str, dict[str, Any]] = {}
    all_participant_rows: dict[str, dict[str, Any]] = {}
    all_provenance: list[dict[str, Any]] = []
    support_thresholds: dict[str, float] = {}
    baseline_by_event: dict[str, bool] = {}
    union_by_event: dict[str, bool] = {}
    fold_by_participant = {
        participant: fold_id
        for fold_id, fold in folds.items()
        for participant in fold["valid_participants"]
    }

    for fold_id in EXPECTED_FOLDS:
        fold = folds[fold_id]
        valid_participants = set(fold["valid_participants"])
        train_participants = set(fold["train_participants"])
        oof_by_path = _load_oof_fold(
            _resolve(str(source["oof_paths"][fold_id])), entries, valid_participants
        )
        model_path = _resolve(str(source["model_paths"][fold_id]))
        model = joblib.load(model_path)
        support_scores = [
            np.asarray(model.predict_scores(entries[path]["table"].features), dtype=np.float64)
            for path in sorted(entries)
            if entries[path]["participant_id"] in train_participants
        ]
        if not support_scores:
            raise ValueError(f"empty outer-train support score source: {fold_id}")
        train_scores = np.concatenate(support_scores)
        support_threshold = float(
            np.quantile(train_scores, float(spec["proposal_rule"]["support_threshold"]["quantile"]))
        )
        support_thresholds[fold_id] = support_threshold

        baseline_by_path: dict[str, tuple[Proposal, ...]] = {}
        extra_by_path: dict[str, tuple[Proposal, ...]] = {}
        union_by_path: dict[str, tuple[Proposal, ...]] = {}
        for path in sorted(oof_by_path):
            entry = entries[path]
            scores = oof_by_path[path]
            baseline = _baseline_proposals(path, entry, scores, thresholds[fold_id])
            extra = _extra_proposals(path, entry, scores, support_threshold, spec["proposal_rule"])
            union = union_proposals(baseline, extra)
            baseline_by_path[path] = baseline
            extra_by_path[path] = extra
            union_by_path[path] = union
            all_provenance.extend(_proposal_record(item, fold_id) for item in union)

        valid_paths = set(oof_by_path)
        baseline_eval = _evaluate_variant(baseline_by_path, valid_paths, entries, events)
        union_eval = _evaluate_variant(union_by_path, valid_paths, entries, events)
        extra_eval = _evaluate_variant(extra_by_path, valid_paths, entries, events)
        fold_event_ids = [event["event_id"] for event in events if event["participant_id"] in valid_participants]
        for event_id in fold_event_ids:
            baseline_by_event[event_id] = bool(baseline_eval["event_outcomes"].get(event_id, False))
            union_by_event[event_id] = bool(union_eval["event_outcomes"].get(event_id, False))

        baseline_expected = spec["baseline_reproduction"]["expected_by_fold"][fold_id]
        actual_baseline = {
            "covered": baseline_eval["covered"],
            "total": baseline_eval["total"],
            "candidate_count": baseline_eval["candidate_count"],
        }
        if actual_baseline != baseline_expected:
            raise RuntimeError(
                f"A_LINEAGE_MISMATCH {fold_id}: expected {baseline_expected}, got {actual_baseline}"
            )
        stats = _proposal_stats(baseline_by_path, extra_by_path, union_by_path, valid_paths, entries)
        fold_results.append(
            {
                "fold_id": fold_id,
                "train_participant_count": len(train_participants),
                "valid_participant_count": len(valid_participants),
                "support_threshold": support_threshold,
                "baseline_A": baseline_eval,
                "extra_only": extra_eval,
                "union_new": union_eval,
                "proposal_counts": stats,
                "baseline_preserved": all(
                    {(item.record_path, item.start_ms, item.end_ms) for item in baseline_by_path[path]}
                    <= {(item.record_path, item.start_ms, item.end_ms) for item in union_by_path[path]}
                    for path in valid_paths
                ),
            }
        )
        for participant, row in union_eval["participant_results"].items():
            all_participant_rows[f"{fold_id}:{participant}"] = {
                "fold_id": fold_id,
                "participant_id": participant,
                "A": baseline_eval["participant_results"].get(participant),
                "extra_only": extra_eval["participant_results"].get(participant),
                "union": row,
            }
        peak_rss = _budget_check(started, output_root, budget, peak_rss)

    if set(baseline_by_event) != set(event_by_id) or set(union_by_event) != set(event_by_id):
        raise ValueError("event outcome map does not cover fixed 234-event cohort")
    # Reconstruct the extra map from the provenance without using labels.  This
    # keeps the persisted event audit independent from the evaluation loop.
    extra_for_audit: dict[str, list[Proposal]] = defaultdict(list)
    for row in all_provenance:
        if row["source"] not in {"extra", "A+extra"}:
            continue
        extra_for_audit[row["record_path"]].append(
            Proposal(
                row["record_path"],
                int(row["start_ms"]),
                int(row["end_ms"]),
                str(row["source"]),
                tuple(row["boundary_variants"]),
                tuple(int(value) for value in row["source_window_indices"]),
                float(row["support_max"]),
                float(row["support_mean"]),
                int(row["segment_id"]),
                int(row["region_id"]),
            )
        )
    event_rows = _build_event_rows(
        events,
        fold_by_participant,
        baseline_by_event,
        union_by_event,
        {path: tuple(items) for path, items in extra_for_audit.items()},
        entries,
    )

    event_results_path = output_root / "event-results.jsonl"
    with event_results_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in event_rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            stream.write("\n")
    provenance_path = output_root / "proposal-provenance.jsonl"
    with provenance_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in sorted(all_provenance, key=lambda item: (item["fold_id"], item["record_path"], item["start_ms"], item["end_ms"], item["source"])):
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            stream.write("\n")
    write_json(output_root / "fold-results.json", fold_results)

    new_fold_recall = [float(row["union_new"]["recall"]) for row in fold_results]
    g1_met = all(value >= float(spec["formal_gate"]["coverage_recall_min"]) for value in new_fold_recall)
    budget_status = "WITHIN_BUDGET"
    resource_status = "PASS"
    downstream = {
        "status": "INTERFACE_GAP",
        "reason": "current build_event_candidates accepts selected window streams, not arbitrary Proposal intervals; boundary variants need a diagnostic adapter before verifier use",
        "production_verifier_modified": False,
    }
    classification = (
        "BOUNDED_PROPOSAL_FEASIBILITY_SUPPORTED"
        if g1_met
        else "FROZEN_PROPOSAL_RULE_UNSUPPORTED_AS_G1_REMEDY"
    )
    ended_at = datetime.now(timezone.utc).isoformat()
    strata_summary: dict[str, dict[str, int]] = {}
    for dimension in ("duration", "positive_windows"):
        values = sorted({row["strata"][dimension] for row in event_rows})
        for value in values:
            selected = [row for row in event_rows if row["strata"][dimension] == value]
            strata_summary[f"{dimension}:{value}"] = {
                "total": len(selected),
                "A_covered": sum(bool(row["A_covered"]) for row in selected),
                "union_covered": sum(bool(row["union_covered"]) for row in selected),
            }

    report = {
        "probe_id": PROBE_ID,
        "status": "COMPLETED",
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_seconds": time.monotonic() - started,
        "spec": {"path": str(spec_path), "sha256": sha256_file(spec_path)},
        "lineage": source,
        "inputs": {
            "event_count": len(events),
            "auxiliary_exact_complete_denominator": 232,
            "record_count": len(entries),
            "row_count": 632100,
            "feature_schema": "imu_stats_v1",
            "feature_width": 111,
            "window_ms": 15000,
            "stride_ms": 7500,
            "test_used": False,
        },
        "support_thresholds": support_thresholds,
        "baseline_reproduction": {
            "status": "MATCHED",
            "expected_and_actual_by_fold": [
                {
                    "fold_id": row["fold_id"],
                    "expected": spec["baseline_reproduction"]["expected_by_fold"][row["fold_id"]],
                    "actual": {
                        "covered": row["baseline_A"]["covered"],
                        "total": row["baseline_A"]["total"],
                        "candidate_count": row["baseline_A"]["candidate_count"],
                    },
                }
                for row in fold_results
            ],
        },
        "fold_results": fold_results,
        "participant_results": list(all_participant_rows.values()),
        "event_results_path": str(event_results_path),
        "proposal_provenance_path": str(provenance_path),
        "event_summary": {
            "A_covered": sum(bool(row["A_covered"]) for row in event_rows),
            "union_covered": sum(bool(row["union_covered"]) for row in event_rows),
            "recovered_events": [row["event_id"] for row in event_rows if row["recovered"]],
            "newly_lost_events": [row["event_id"] for row in event_rows if row["newly_lost"]],
            "by_strata": strata_summary,
        },
        "decisions": {
            "G1_NUMERIC_CRITERION_MET": g1_met,
            "baseline_fold_recall": [float(row["baseline_A"]["recall"]) for row in fold_results],
            "union_fold_recall": new_fold_recall,
            "PROPOSAL_BUDGET_STATUS": budget_status,
            "RESOURCE_STATUS": resource_status,
            "DOWNSTREAM_COMPATIBILITY": downstream,
            "classification": classification,
            "formal_g1_status_unchanged": "FAIL",
        },
        "resource_status": {
            "status": resource_status,
            "budget": budget,
            "elapsed_seconds": time.monotonic() - started,
            "peak_rss_bytes": peak_rss,
            "diagnostic_disk_bytes": _directory_bytes(output_root),
        },
        "isolation": {
            "production": "UNCHANGED",
            "full_training": "BLOCKED",
            "production_architecture_replacement": "NOT_AUTHORIZED",
            "model_fit_count": 0,
            "new_scorer_trained": False,
            "verifier_trained": False,
            "gt_used_by_proposal_generator": False,
            "threshold_sweep": False,
            "stride_sweep": False,
            "aggregation_sweep": False,
        },
        "limitations": [
            "This is proposal-only diagnostic evidence on repeatedly used development outer folds, not independent confirmation.",
            "The current production verifier has no ProposalSet adapter, so downstream verifier compatibility is an interface gap, not an executed verifier result.",
            "Exact 232 completeness is auxiliary metadata only; the formal diagnostic denominator remains 234.",
        ],
    }
    write_json(output_root / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--spec-hash", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    spec_path = args.spec if args.spec.is_absolute() else ROOT / args.spec
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report = run(spec_path, output)
    print(json.dumps({"status": report["status"], "classification": report["decisions"]["classification"], "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
