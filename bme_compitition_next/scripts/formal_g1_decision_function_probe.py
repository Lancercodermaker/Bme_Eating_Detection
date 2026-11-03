"""Run the frozen Formal G1 CandidateModel decision-function probe."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

from eating_event.candidates import CandidateModel, eventize_windows, fit_candidate_model
from eating_event.data.labels import WindowLabel, WindowLabelResult
from eating_event.data.windows import WindowRecord, WindowSpec
from eating_event.diagnostic_temporal import make_diagnostic_estimator
from eating_event.evaluation import ParticipantFold, build_inner_folds, build_outer_folds
from eating_event.metrics import EventInterval, evaluate_events, interval_iou


SPEC_PATH = Path("configs/formal-g1-decision-function-probe-v1.json")
HASH_PATH = Path("configs/formal-g1-decision-function-probe-v1.sha256")
TEMPORAL_REVIEW_PATH = Path("artifacts/g1-model-temporal-representation-review-v1.json")
ELIGIBILITY_PATH = Path("artifacts/g1-candidate-coverage-v4/eligibility.json")
FEATURE_TABLE_PATH = Path("artifacts/g1-temporal-representation-probe-v1/feature-table.npz")
OUTPUT_DIR = Path("artifacts/g1-decision-function-probe-v1")
SEED = 20260910
OUTER_FOLDS = 5
QUANTILE_GRID = (0.70, 0.80, 0.90)
FUSE_GAP_MS = 300_000
G1_IOU_THRESHOLD = 0.25
G1_COVERAGE_THRESHOLD = 0.90
HARD_NEGATIVE_SCORE_CUTOFF = 0.5


@dataclass(frozen=True)
class ProbeDataset:
    features: np.ndarray
    labels: np.ndarray
    participants: np.ndarray
    starts: np.ndarray
    ends: np.ndarray
    row_keys: np.ndarray


@dataclass(frozen=True)
class EventIdentity:
    participant: str
    event_index: int
    interval: EventInterval
    taxonomy: str | None = None
    duration_seconds: float | None = None
    positive_windows: int | None = None


@dataclass(frozen=True)
class FittedFold:
    fold: ParticipantFold
    model: CandidateModel
    threshold: float
    quantile: float
    inner_results: tuple[dict[str, object], ...]
    valid_indices: np.ndarray
    valid_scores: np.ndarray


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_spec() -> tuple[dict[str, object], str]:
    spec_bytes = SPEC_PATH.read_bytes()
    actual = hashlib.sha256(spec_bytes).hexdigest()
    expected = HASH_PATH.read_text(encoding="utf-8").split()[0].lower()
    if actual != expected:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: decision-function probe spec hash mismatch")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if spec.get("status") != "FROZEN":
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: decision-function probe spec is not frozen")
    for details in spec["source_of_truth"].values():
        path = Path(str(details["path"]))
        expected_source_hash = str(details["sha256"])
        if _sha256(path) != expected_source_hash:
            raise RuntimeError(f"PREREGISTRATION_IMPLEMENTATION_BLOCKER: source hash drift: {path}")
    return spec, actual


def _load_dataset(spec: Mapping[str, object]) -> ProbeDataset:
    expected_hash = str(spec["dataset"]["feature_table_sha256"])
    if _sha256(FEATURE_TABLE_PATH) != expected_hash:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: feature table hash drift")
    payload = np.load(FEATURE_TABLE_PATH, allow_pickle=True)
    features = payload["a"].astype(np.float64, copy=False)
    labels = payload["labels"].astype(np.int8, copy=False)
    participants = payload["participants"].astype(object, copy=False)
    starts = payload["starts"].astype(np.int64, copy=False)
    ends = payload["ends"].astype(np.int64, copy=False)
    row_keys = payload["row_keys"].astype(object, copy=False)
    if features.ndim != 2 or features.shape[1] != 111:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: imu_stats_v1 width drift")
    if not np.isfinite(features).all():
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: non-finite imu_stats_v1 feature")
    sizes = {array.size for array in (labels, participants, starts, ends, row_keys)}
    if sizes != {features.shape[0]}:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: feature table arrays are misaligned")
    return ProbeDataset(features, labels, participants, starts, ends, row_keys)


def _parse_event_id(event_id: str) -> EventInterval:
    _, interval = event_id.split(":", 1)
    start, end = interval.split("-", 1)
    return EventInterval(int(start), int(end))


def _read_truth_events() -> dict[str, tuple[EventIdentity, ...]]:
    payload = json.loads(ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    rows = [row for row in payload["event_eligibility"] if bool(row.get("training_eligibility"))]
    result: dict[str, list[EventIdentity]] = defaultdict(list)
    for row in rows:
        participant = str(row["participant_id"])
        result[participant].append(
            EventIdentity(
                participant=participant,
                event_index=int(row["event_index"]),
                interval=EventInterval(int(row["start_ms"]), int(row["end_ms"])),
                duration_seconds=float(row["duration_ms"]) / 1000.0,
            )
        )
    return {participant: tuple(sorted(events, key=lambda item: item.event_index)) for participant, events in result.items()}


def _read_missing_events() -> tuple[EventIdentity, ...]:
    report = json.loads(TEMPORAL_REVIEW_PATH.read_text(encoding="utf-8"))
    rows = [row for row in report["event_audit"]["rows"] if row["taxonomy"] != "COVERED"]
    if len(rows) != 27:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: expected 27 MissingEvents")
    taxonomy_counts: dict[str, int] = defaultdict(int)
    result: list[EventIdentity] = []
    for row in rows:
        interval = _parse_event_id(str(row["event_id"]))
        taxonomy = str(row["taxonomy"])
        taxonomy_counts[taxonomy] += 1
        result.append(
            EventIdentity(
                participant=str(row["participant"]),
                event_index=int(row["event_index"]),
                interval=interval,
                taxonomy=taxonomy,
                duration_seconds=float(row["gt_duration_s"]),
                positive_windows=int(row["positive_windows"]),
            )
        )
    if dict(taxonomy_counts) != {"AGGREGATION_FIRST": 23, "SCORE_THRESHOLD_FIRST": 4}:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: MissingEvent taxonomy drift")
    return tuple(result)


def _record_paths(row_keys: np.ndarray) -> np.ndarray:
    return np.asarray([str(value).rsplit("|", 3)[0] for value in row_keys], dtype=object)


def _window_records(dataset: ProbeDataset, indices: Sequence[int]) -> list[WindowRecord]:
    ignored = WindowLabelResult(WindowLabel.IGNORE, 0.0, None)
    return [
        WindowRecord(
            window=WindowSpec(int(dataset.starts[index]), int(dataset.ends[index])),
            coverage=1.0,
            longest_invalid_run=0,
            label_result=ignored,
        )
        for index in indices
    ]


def _eventize_by_record(
    dataset: ProbeDataset,
    indices: Sequence[int],
    scores: np.ndarray,
    threshold: float,
) -> dict[str, tuple[EventInterval, ...]]:
    if len(indices) != scores.size:
        raise ValueError("eventization scores must align with indices")
    paths = _record_paths(dataset.row_keys[np.asarray(indices, dtype=np.int64)])
    grouped: dict[str, list[int]] = defaultdict(list)
    for local_index, path in enumerate(paths):
        grouped[str(path)].append(local_index)
    predictions: dict[str, list[EventInterval]] = defaultdict(list)
    for path_indices in grouped.values():
        global_indices = [int(indices[local_index]) for local_index in path_indices]
        local_scores = scores[np.asarray(path_indices, dtype=np.int64)]
        intervals = eventize_windows(
            _window_records(dataset, global_indices),
            local_scores,
            threshold=threshold,
            min_duration_ms=1,
            fuse_gap_ms=FUSE_GAP_MS,
        )
        participant = str(dataset.participants[global_indices[0]])
        predictions[participant].extend(EventInterval(int(start), int(end)) for start, end in intervals)
    return {participant: tuple(sorted(values)) for participant, values in predictions.items()}


def _coverage_support(event: EventInterval, selected_windows: Sequence[EventInterval]) -> dict[str, float | int]:
    intersections = sorted(
        (
            max(event.start_ms, window.start_ms),
            min(event.end_ms, window.end_ms),
        )
        for window in selected_windows
        if window.start_ms < event.end_ms and window.end_ms > event.start_ms
    )
    merged: list[list[int]] = []
    for start_ms, end_ms in intersections:
        if end_ms <= start_ms:
            continue
        if merged and start_ms <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end_ms)
        else:
            merged.append([start_ms, end_ms])
    covered_ms = sum(end_ms - start_ms for start_ms, end_ms in merged)
    cursor = event.start_ms
    longest_gap = 0
    for start_ms, end_ms in merged:
        longest_gap = max(longest_gap, start_ms - cursor)
        cursor = max(cursor, end_ms)
    longest_gap = max(longest_gap, event.end_ms - cursor)
    return {
        "coverage_fraction": covered_ms / float(event.end_ms - event.start_ms),
        "covered_ms": int(covered_ms),
        "longest_unsupported_interval_ms": int(longest_gap),
    }


def _score_summary(scores: np.ndarray) -> dict[str, float | int | None]:
    values = np.asarray(scores, dtype=np.float64)
    if values.size == 0:
        return {"count": 0, "min": None, "median": None, "p90": None, "max": None}
    return {
        "count": int(values.size),
        "min": float(np.min(values)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "max": float(np.max(values)),
    }


def _binary_metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, object]:
    y = np.asarray(labels, dtype=np.int8)
    values = np.asarray(scores, dtype=np.float64)
    if y.size != values.size:
        raise ValueError("metric labels and scores must align")
    keep = np.isfinite(values) & ((y == 0) | (y == 1))
    y = y[keep]
    values = values[keep]
    output: dict[str, object] = {
        "positive_count": int((y == 1).sum()),
        "negative_count": int((y == 0).sum()),
        "positive_score": _score_summary(values[y == 1]),
        "negative_score": _score_summary(values[y == 0]),
        "score_summary": _score_summary(values),
    }
    if np.unique(y).size == 2:
        output["auroc"] = float(roc_auc_score(y, values))
        output["auprc"] = float(average_precision_score(y, values))
    else:
        output["auroc"] = None
        output["auprc"] = None
        output["reason"] = "missing positive or negative rows"
    return output


def _select_score_quantile(rows: Sequence[Mapping[str, object]]) -> float:
    if not rows:
        raise ValueError("quantile selection requires rows")
    selected = max(
        rows,
        key=lambda row: (
            float(row["pooled_recall"]),
            float(row["worst_participant_recall"]),
            -int(row["candidate_count"]),
            float(row["quantile"]),
        ),
    )
    return float(selected["quantile"])


def select_easy_negative_indices(
    scores: np.ndarray,
    row_keys: np.ndarray,
    *,
    count: int,
) -> np.ndarray:
    if count < 0 or scores.size != row_keys.size:
        raise ValueError("easy-negative inputs must align and count must be non-negative")
    order = sorted(range(scores.size), key=lambda index: (float(scores[index]), str(row_keys[index])))
    return np.asarray(order[:count], dtype=np.int64)


def _fit_model(kind: str, features: np.ndarray, labels: np.ndarray) -> CandidateModel:
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int8)
    keep = y >= 0
    if keep.sum() == 0 or np.unique(y[keep]).tolist() != [0, 1]:
        raise ValueError("decision-function candidate fit needs both binary supervised classes")
    if kind == "A":
        return fit_candidate_model(x, y, random_state=SEED, max_iter=100)
    if kind == "N":
        estimator = make_diagnostic_estimator("N")
        weights = np.asarray(compute_sample_weight(class_weight="balanced", y=y[keep]), dtype=np.float64)
        estimator.fit(x[keep], y[keep], sample_weight=weights)
        return CandidateModel(estimator)
    raise ValueError("candidate kind must be A or N")


def _participant_indices(dataset: ProbeDataset, participants: Iterable[str]) -> np.ndarray:
    wanted = set(str(value) for value in participants)
    return np.asarray([index for index, value in enumerate(dataset.participants) if str(value) in wanted], dtype=np.int64)


def _g1_recall(
    predictions: Mapping[str, Sequence[EventInterval]],
    truths: Mapping[str, Sequence[EventIdentity]],
) -> tuple[float, dict[str, float], int, int]:
    participant_recall: dict[str, float] = {}
    covered_total = 0
    truth_total = 0
    for participant, events in truths.items():
        participant_predictions = predictions.get(participant, ())
        covered = sum(
            any(interval_iou(prediction, event.interval) > G1_IOU_THRESHOLD for prediction in participant_predictions)
            for event in events
        )
        covered_total += covered
        truth_total += len(events)
        participant_recall[participant] = covered / len(events) if events else 1.0
    return (covered_total / truth_total if truth_total else 0.0), participant_recall, covered_total, truth_total


def _event_behavior(
    predictions: Mapping[str, Sequence[EventInterval]],
    truths: Mapping[str, Sequence[EventIdentity]],
) -> dict[str, object]:
    prediction_count = 0
    false_count = 0
    ratios: list[float] = []
    start_errors: list[float] = []
    end_errors: list[float] = []
    for participant, events in truths.items():
        participant_predictions = tuple(predictions.get(participant, ()))
        metrics = evaluate_events(participant_predictions, [event.interval for event in events], iou_threshold=G1_IOU_THRESHOLD)
        prediction_count += len(participant_predictions)
        false_count += metrics.fp
        for match in metrics.matches:
            prediction = participant_predictions[match.prediction_index]
            truth = events[match.truth_index].interval
            ratios.append(
                (prediction.end_ms - prediction.start_ms) / float(truth.end_ms - truth.start_ms)
            )
            start_errors.append(abs(prediction.start_ms - truth.start_ms))
            end_errors.append(abs(prediction.end_ms - truth.end_ms))
    return {
        "predicted_event_count": int(prediction_count),
        "false_event_count": int(false_count),
        "false_event_rate": false_count / float(prediction_count) if prediction_count else 0.0,
        "duration_ratio_median": float(np.median(ratios)) if ratios else None,
        "duration_ratio_p90": float(np.percentile(ratios, 90)) if ratios else None,
        "boundary_start_mae_ms": float(np.mean(start_errors)) if start_errors else None,
        "boundary_end_mae_ms": float(np.mean(end_errors)) if end_errors else None,
    }


def _fit_fold(
    kind: str,
    fold: ParticipantFold,
    dataset: ProbeDataset,
    truths: Mapping[str, Sequence[EventIdentity]],
) -> FittedFold:
    train_indices = _participant_indices(dataset, fold.train_participants)
    valid_indices = _participant_indices(dataset, fold.valid_participants)
    inner_folds = build_inner_folds(fold.train_participants, n_folds=min(4, len(fold.train_participants)), seed=SEED)
    inner_evaluations: list[list[tuple[float, float, int]]] = []
    for inner in inner_folds:
        inner_train = _participant_indices(dataset, inner.train_participants)
        inner_valid = _participant_indices(dataset, inner.valid_participants)
        model = _fit_model(kind, dataset.features[inner_train], dataset.labels[inner_train])
        train_scores = model.predict_scores(dataset.features[inner_train])
        valid_scores = model.predict_scores(dataset.features[inner_valid])
        inner_truths = {participant: truths.get(participant, ()) for participant in inner.valid_participants}
        rows_for_inner: list[tuple[float, float, int]] = []
        for quantile in QUANTILE_GRID:
            threshold = float(np.quantile(train_scores, quantile))
            predictions = _eventize_by_record(dataset, inner_valid, valid_scores, threshold)
            recall, participant_recall, _, _ = _g1_recall(predictions, inner_truths)
            candidate_count = sum(len(values) for values in predictions.values())
            rows_for_inner.append((recall, min(participant_recall.values(), default=1.0), candidate_count))
        inner_evaluations.append(rows_for_inner)
    quantile_rows: list[dict[str, object]] = []
    for quantile_index, quantile in enumerate(QUANTILE_GRID):
        inner_rows = [evaluation[quantile_index] for evaluation in inner_evaluations]
        quantile_rows.append(
            {
                "quantile": quantile,
                "pooled_recall": float(np.mean([row[0] for row in inner_rows])),
                "worst_participant_recall": float(min((row[1] for row in inner_rows), default=0.0)),
                "candidate_count": int(sum(row[2] for row in inner_rows)),
                "inner_rows": [
                    {
                        "pooled_recall": float(row[0]),
                        "worst_participant_recall": float(row[1]),
                        "candidate_count": int(row[2]),
                    }
                    for row in inner_rows
                ],
            }
        )
    selected_quantile = _select_score_quantile(quantile_rows)
    model = _fit_model(kind, dataset.features[train_indices], dataset.labels[train_indices])
    threshold = float(np.quantile(model.predict_scores(dataset.features[train_indices]), selected_quantile))
    valid_scores = model.predict_scores(dataset.features[valid_indices])
    return FittedFold(
        fold=fold,
        model=model,
        threshold=threshold,
        quantile=selected_quantile,
        inner_results=tuple(quantile_rows),
        valid_indices=valid_indices,
        valid_scores=valid_scores,
    )


def _metric_block(dataset: ProbeDataset, indices: np.ndarray, scores: np.ndarray, positive_mask: np.ndarray, negative_mask: np.ndarray) -> dict[str, object]:
    local = np.asarray(indices, dtype=np.int64)
    local_scores = np.asarray(scores, dtype=np.float64)
    pos = positive_mask[local]
    neg = negative_mask[local]
    labels = np.concatenate((np.ones(int(pos.sum()), dtype=np.int8), np.zeros(int(neg.sum()), dtype=np.int8)))
    values = np.concatenate((local_scores[pos], local_scores[neg]))
    return _binary_metrics(labels, values)


def _participant_metric_blocks(
    dataset: ProbeDataset,
    indices: np.ndarray,
    scores: np.ndarray,
    positive_mask: np.ndarray,
    negative_mask: np.ndarray,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for participant in sorted({str(value) for value in dataset.participants[indices]}):
        local = indices[np.asarray([str(value) == participant for value in dataset.participants[indices]], dtype=bool)]
        local_scores = scores[np.asarray([str(value) == participant for value in dataset.participants[indices]], dtype=bool)]
        result[participant] = _metric_block(dataset, local, local_scores, positive_mask, negative_mask)
    return result


def _delta_summary(deltas: Sequence[float]) -> dict[str, object]:
    values = np.asarray([delta for delta in deltas if np.isfinite(delta)], dtype=np.float64)
    if values.size == 0:
        return {"stable": False, "fold_count": 0, "positive_fold_count": 0, "median_fold_delta": None, "worst_fold_delta": None}
    return {
        "stable": bool(
            int((values > 0).sum()) >= 4
            and float(np.median(values)) > 0
            and float(np.min(values)) >= -0.02
        ),
        "fold_count": int(values.size),
        "positive_fold_count": int((values > 0).sum()),
        "median_fold_delta": float(np.median(values)),
        "worst_fold_delta": float(np.min(values)),
    }


def _comparison_summary(
    baseline_folds: Sequence[Mapping[str, object]],
    nonlinear_folds: Sequence[Mapping[str, object]],
    participant_deltas: Mapping[str, float | None],
) -> dict[str, object]:
    fold_deltas = [
        float(nonlinear.get("auroc", np.nan)) - float(baseline.get("auroc", np.nan))
        if nonlinear.get("auroc") is not None and baseline.get("auroc") is not None
        else np.nan
        for baseline, nonlinear in zip(baseline_folds, nonlinear_folds)
    ]
    finite_participants = [value for value in participant_deltas.values() if value is not None and np.isfinite(value)]
    improved = sum(value > 0 for value in finite_participants)
    degraded = sum(value < 0 for value in finite_participants)
    summary = _delta_summary(fold_deltas)
    summary.update(
        {
            "participant_count": len(finite_participants),
            "improved_participant_count": int(improved),
            "degraded_participant_count": int(degraded),
            "median_participant_delta": float(np.median(finite_participants)) if finite_participants else None,
            "participant_guard": bool(improved >= 0.60 * len(finite_participants) and improved > degraded) if finite_participants else False,
        }
    )
    return {"fold_delta_auroc": fold_deltas, "auroc_summary": summary}


def _control_masks(dataset: ProbeDataset, missing_events: Sequence[EventIdentity]) -> dict[str, np.ndarray]:
    paths = _record_paths(dataset.row_keys)
    missing = np.zeros(dataset.labels.size, dtype=bool)
    covered = np.zeros(dataset.labels.size, dtype=bool)
    report = json.loads(TEMPORAL_REVIEW_PATH.read_text(encoding="utf-8"))
    event_rows = report["event_audit"]["rows"]
    for row in event_rows:
        event = _parse_event_id(str(row["event_id"]))
        mask = (
            (dataset.participants == str(row["participant"]))
            & (dataset.starts < event.end_ms)
            & (dataset.ends > event.start_ms)
        )
        if row["taxonomy"] == "COVERED":
            covered |= mask
        else:
            missing |= mask
    return {
        "missing_positive": (dataset.labels == 1) & missing,
        "covered_positive": (dataset.labels == 1) & covered,
        "all_positive": dataset.labels == 1,
        "all_negative": dataset.labels == 0,
        "record_paths_present": np.asarray([bool(value) for value in paths], dtype=bool),
    }


def _missing_event_row(
    event: EventIdentity,
    dataset: ProbeDataset,
    fold_id_by_participant: Mapping[str, str],
    scores_by_model: Mapping[str, np.ndarray],
    thresholds_by_model_fold: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    row: dict[str, object] = {
        "participant": event.participant,
        "event_index": event.event_index,
        "start_ms": event.interval.start_ms,
        "end_ms": event.interval.end_ms,
        "duration_seconds": event.duration_seconds,
        "positive_windows": event.positive_windows,
        "original_failure_taxonomy": event.taxonomy,
        "outer_fold": fold_id_by_participant.get(event.participant),
    }
    fold_id = fold_id_by_participant.get(event.participant)
    for kind in ("A", "N"):
        score_values = scores_by_model[kind]
        mask = (
            (dataset.participants == event.participant)
            & (dataset.starts < event.interval.end_ms)
            & (dataset.ends > event.interval.start_ms)
            & (dataset.labels == 1)
        )
        all_overlap = (
            (dataset.participants == event.participant)
            & (dataset.starts < event.interval.end_ms)
            & (dataset.ends > event.interval.start_ms)
        )
        positive_scores = score_values[mask]
        threshold = thresholds_by_model_fold[kind].get(str(fold_id), np.nan) if fold_id else np.nan
        row[f"{kind}_positive_score"] = _score_summary(positive_scores)
        row[f"{kind}_fraction_positive_windows_above_threshold"] = (
            float((positive_scores >= threshold).mean()) if positive_scores.size and np.isfinite(threshold) else None
        )
        selected_windows = [
            EventInterval(int(dataset.starts[index]), int(dataset.ends[index]))
            for index in np.flatnonzero(all_overlap)
            if np.isfinite(score_values[index]) and score_values[index] >= threshold
        ]
        support = _coverage_support(event.interval, selected_windows)
        row[f"{kind}_selected_temporal_coverage"] = support["coverage_fraction"]
        row[f"{kind}_longest_unsupported_interval_ms"] = support["longest_unsupported_interval_ms"]
    return row


def _summarize_missing_events(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    review = json.loads(TEMPORAL_REVIEW_PATH.read_text(encoding="utf-8"))
    low_recall_participants = {
        str(row["participant"])
        for row in review["participant_audit"].get("low_recall_participants", [])
    }
    groups = {
        "all_missing_events": lambda row: True,
        "aggregation_first": lambda row: row["original_failure_taxonomy"] == "AGGREGATION_FIRST",
        "score_threshold_first": lambda row: row["original_failure_taxonomy"] == "SCORE_THRESHOLD_FIRST",
        "short_events": lambda row: float(row["duration_seconds"] or 0.0) < 180.0,
        "positive_windows_lt_10": lambda row: int(row["positive_windows"] or 0) < 10,
        "low_recall_participants": lambda row: row["participant"] in low_recall_participants,
    }
    result: dict[str, object] = {}
    for group, predicate in groups.items():
        selected = [row for row in rows if predicate(row)]
        group_result: dict[str, object] = {"event_count": len(selected)}
        for kind in ("A", "N"):
            values = [row for row in selected if row[f"{kind}_positive_score"]["count"]]
            medians = [row[f"{kind}_positive_score"]["median"] for row in values]
            p90s = [row[f"{kind}_positive_score"]["p90"] for row in values]
            fractions = [row[f"{kind}_fraction_positive_windows_above_threshold"] for row in values if row[f"{kind}_fraction_positive_windows_above_threshold"] is not None]
            supports = [row[f"{kind}_selected_temporal_coverage"] for row in selected]
            group_result[kind] = {
                "events_with_positive_windows": len(values),
                "median_of_event_positive_score_medians": float(np.median(medians)) if medians else None,
                "median_of_event_positive_score_p90s": float(np.median(p90s)) if p90s else None,
                "median_fraction_positive_windows_above_threshold": float(np.median(fractions)) if fractions else None,
                "median_selected_temporal_coverage": float(np.median(supports)) if supports else None,
            }
        result[group] = group_result
    return result


def _run_probe(spec: Mapping[str, object], spec_hash: str) -> dict[str, object]:
    dataset = _load_dataset(spec)
    truths = _read_truth_events()
    missing_events = _read_missing_events()
    participants = tuple(sorted(str(value) for value in np.unique(dataset.participants)))
    folds = build_outer_folds(participants, n_folds=OUTER_FOLDS, seed=SEED)
    expected_validation = spec["outer_protocol"]["validation_participants"]
    if {fold.fold_id: list(fold.valid_participants) for fold in folds} != expected_validation:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: outer participant fold drift")

    fold_id_by_participant = {
        participant: fold.fold_id for fold in folds for participant in fold.valid_participants
    }
    fitted: dict[str, list[FittedFold]] = {"A": [], "N": []}
    global_scores = {"A": np.full(dataset.labels.size, np.nan, dtype=np.float64), "N": np.full(dataset.labels.size, np.nan, dtype=np.float64)}
    thresholds = {"A": {}, "N": {}}
    inner_policies: dict[str, dict[str, object]] = {"A": {}, "N": {}}
    for kind in ("A", "N"):
        for fold in folds:
            fit = _fit_fold(kind, fold, dataset, truths)
            fitted[kind].append(fit)
            global_scores[kind][fit.valid_indices] = fit.valid_scores
            thresholds[kind][fold.fold_id] = fit.threshold
            inner_policies[kind][fold.fold_id] = {
                "selected_quantile": fit.quantile,
                "threshold": fit.threshold,
                "inner_results": list(fit.inner_results),
            }

    controls = _control_masks(dataset, missing_events)
    hard_negative = (dataset.labels == 0) & (global_scores["A"] >= HARD_NEGATIVE_SCORE_CUTOFF)
    easy_negative = np.zeros(dataset.labels.size, dtype=bool)
    if not np.isfinite(global_scores["A"][dataset.labels >= 0]).all() or not np.isfinite(global_scores["N"][dataset.labels >= 0]).all():
        raise RuntimeError("probe score arrays contain non-finite supervised values")

    task_definitions = {
        "all_supervised": (controls["all_positive"], controls["all_negative"]),
        "missing_vs_hard": (controls["missing_positive"], hard_negative),
    }
    fold_results: dict[str, dict[str, list[dict[str, object]]]] = {
        task: {"A": [], "N": []} for task in task_definitions
    }
    participant_results: dict[str, dict[str, dict[str, object]]] = {
        task: {"A": {}, "N": {}} for task in task_definitions
    }
    control_scores: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    fold_controls: list[dict[str, object]] = []
    for fold_index, fold in enumerate(folds):
        valid_indices = fitted["A"][fold_index].valid_indices
        a_scores = fitted["A"][fold_index].valid_scores
        n_scores = fitted["N"][fold_index].valid_scores
        hard_local = controls["all_negative"][valid_indices] & (a_scores >= HARD_NEGATIVE_SCORE_CUTOFF)
        easy_candidates = np.flatnonzero(controls["all_negative"][valid_indices])
        hard_count = int(hard_local.sum())
        easy_local = select_easy_negative_indices(
            a_scores[easy_candidates],
            dataset.row_keys[valid_indices][easy_candidates],
            count=hard_count,
        )
        easy_local = easy_candidates[easy_local]
        easy_negative[valid_indices[easy_local]] = True
        fold_controls.append(
            {
                "fold_id": fold.fold_id,
                "hard_negative_count": hard_count,
                "easy_negative_count": int(easy_local.size),
            }
        )
        local_masks = {
            "hard_negative": np.zeros(valid_indices.size, dtype=bool),
            "easy_negative": np.zeros(valid_indices.size, dtype=bool),
        }
        local_masks["hard_negative"][np.flatnonzero(hard_local)] = True
        local_masks["easy_negative"][easy_local] = True
        for kind, scores in (("A", a_scores), ("N", n_scores)):
            control_scores[fold.fold_id][kind] = {
                "hard_negative": _score_summary(scores[local_masks["hard_negative"]]),
                "easy_negative": _score_summary(scores[local_masks["easy_negative"]]),
            }
            for task, (positive_mask, negative_mask) in task_definitions.items():
                fold_metric = _metric_block(dataset, valid_indices, scores, positive_mask, negative_mask)
                fold_results[task][kind].append({"fold_id": fold.fold_id, **fold_metric})
                participant_results[task][kind][fold.fold_id] = _participant_metric_blocks(
                    dataset, valid_indices, scores, positive_mask, negative_mask
                )

    pooled_results: dict[str, dict[str, dict[str, object]]] = {task: {} for task in task_definitions}
    participant_deltas: dict[str, dict[str, float | None]] = {task: {} for task in task_definitions}
    comparisons: dict[str, dict[str, object]] = {}
    for task, (positive_mask, negative_mask) in task_definitions.items():
        for kind in ("A", "N"):
            pooled_results[task][kind] = _metric_block(
                dataset,
                np.arange(dataset.labels.size, dtype=np.int64),
                global_scores[kind],
                positive_mask,
                negative_mask,
            )
        participants_with_metrics = sorted(
            set().union(*(participant_results[task]["A"][fold.fold_id].keys() for fold in folds))
        )
        for participant in participants_with_metrics:
            a_metric = next(
                (participant_results[task]["A"][fold.fold_id].get(participant) for fold in folds if participant in participant_results[task]["A"][fold.fold_id]),
                None,
            )
            n_metric = next(
                (participant_results[task]["N"][fold.fold_id].get(participant) for fold in folds if participant in participant_results[task]["N"][fold.fold_id]),
                None,
            )
            participant_deltas[task][participant] = (
                float(n_metric["auroc"] - a_metric["auroc"])
                if a_metric and n_metric and a_metric.get("auroc") is not None and n_metric.get("auroc") is not None
                else None
            )
        comparisons[task] = _comparison_summary(
            fold_results[task]["A"], fold_results[task]["N"], participant_deltas[task]
        )

    control_comparisons: dict[str, object] = {}
    control_definitions = {
        "covered_vs_hard": (controls["covered_positive"], hard_negative),
        "missing_vs_hard": (controls["missing_positive"], hard_negative),
        "covered_vs_easy": (controls["covered_positive"], easy_negative),
        "missing_vs_easy": (controls["missing_positive"], easy_negative),
    }
    for control_name, (positive_mask, negative_mask) in control_definitions.items():
        control_comparisons[control_name] = {
            "A": _metric_block(
                dataset,
                np.arange(dataset.labels.size, dtype=np.int64),
                global_scores["A"],
                positive_mask,
                negative_mask,
            ),
            "N": _metric_block(
                dataset,
                np.arange(dataset.labels.size, dtype=np.int64),
                global_scores["N"],
                positive_mask,
                negative_mask,
            ),
        }

    all_supervised_comparison = comparisons["all_supervised"]
    hard_negative_delta = (
        float(pooled_results["missing_vs_hard"]["N"]["auroc"])
        - float(pooled_results["missing_vs_hard"]["A"]["auroc"])
        if pooled_results["missing_vs_hard"]["N"].get("auroc") is not None
        and pooled_results["missing_vs_hard"]["A"].get("auroc") is not None
        else np.nan
    )
    hard_negative_guard = bool(np.isfinite(hard_negative_delta) and hard_negative_delta >= -0.03)
    window_gate = bool(
        all_supervised_comparison["auroc_summary"]["stable"]
        and all_supervised_comparison["auroc_summary"]["participant_guard"]
        and hard_negative_guard
    )
    if window_gate:
        event_level_status = "RUN"
    else:
        event_level_status = "NOT_RUN_WINDOW_EFFECT_NOT_REPRODUCED"

    report: dict[str, object] = {
        "schema_version": "formal_g1_decision_function_probe_report_v1",
        "probe_spec": {"path": str(SPEC_PATH), "sha256": spec_hash, "status": "FROZEN"},
        "dataset": {
            "feature_table_path": str(FEATURE_TABLE_PATH),
            "feature_table_sha256": _sha256(FEATURE_TABLE_PATH),
            "rows": int(dataset.labels.size),
            "feature_width": int(dataset.features.shape[1]),
            "label_counts": {str(value): int((dataset.labels == value).sum()) for value in (-1, 0, 1)},
        },
        "models": {
            "A": spec["baseline_candidate_model"],
            "N": spec["diagnostic_candidate_model"],
        },
        "score_selection": {"A": inner_policies["A"], "N": inner_policies["N"]},
        "controls": {
            "frozen_hard_negative_cutoff": HARD_NEGATIVE_SCORE_CUTOFF,
            "hard_negative_count": int(hard_negative.sum()),
            "folds": fold_controls,
            "score_summaries": {kind: dict(value) for kind, value in control_scores.items()},
            "easy_negative_count": int(easy_negative.sum()),
            "ranking_comparisons": control_comparisons,
        },
        "window_level": {
            "tasks": {
                "all_supervised": "label==1 versus label==0",
                "missing_vs_hard": "missing-event positive windows versus frozen hard negatives",
            },
            "pooled": pooled_results,
            "per_fold": fold_results,
            "participant": participant_results,
            "participant_auroc_deltas_N_minus_A": participant_deltas,
            "comparisons": comparisons,
            "reproduction_gate": {
                "task": "all_supervised",
                "passed": window_gate,
                "criteria": spec["window_level_metrics"]["reproduction_gate"],
                "hard_negative_auroc_delta": hard_negative_delta,
                "hard_negative_guard_passed": hard_negative_guard,
            },
        },
        "event_level_replay": {"status": event_level_status},
    }

    if window_gate:
        event_results: dict[str, dict[str, object]] = {}
        predictions_by_model_fold: dict[str, dict[str, dict[str, tuple[EventInterval, ...]]]] = {"A": {}, "N": {}}
        for kind in ("A", "N"):
            for fit in fitted[kind]:
                predictions_by_model_fold[kind][fit.fold.fold_id] = _eventize_by_record(
                    dataset, fit.valid_indices, fit.valid_scores, fit.threshold
                )
                fold_truths = {participant: truths.get(participant, ()) for participant in fit.fold.valid_participants}
                recall, participant_recall, covered, total = _g1_recall(
                    predictions_by_model_fold[kind][fit.fold.fold_id], fold_truths
                )
                event_results.setdefault(kind, {})[fit.fold.fold_id] = {
                    "pooled_recall": recall,
                    "covered": covered,
                    "total": total,
                    "participant_recall": participant_recall,
                    "behavior": _event_behavior(predictions_by_model_fold[kind][fit.fold.fold_id], fold_truths),
                    "formal_g1_pass": recall >= G1_COVERAGE_THRESHOLD,
                }
        missing_rows: list[dict[str, object]] = []
        global_score_by_kind = {"A": global_scores["A"], "N": global_scores["N"]}
        for event in missing_events:
            missing_rows.append(
                _missing_event_row(
                    event,
                    dataset,
                    fold_id_by_participant,
                    global_score_by_kind,
                    thresholds,
                )
            )
        replay_comparison: dict[str, object] = {"per_fold": {}, "recovered_events": [], "newly_lost_events": []}
        for fold in folds:
            fold_truths = {participant: truths.get(participant, ()) for participant in fold.valid_participants}
            a_pred = predictions_by_model_fold["A"][fold.fold_id]
            n_pred = predictions_by_model_fold["N"][fold.fold_id]
            a_recall = event_results["A"][fold.fold_id]["pooled_recall"]
            n_recall = event_results["N"][fold.fold_id]["pooled_recall"]
            replay_comparison["per_fold"][fold.fold_id] = {
                "baseline_recall": a_recall,
                "nonlinear_recall": n_recall,
                "delta": n_recall - a_recall,
                "baseline_formal_g1_pass": bool(a_recall >= G1_COVERAGE_THRESHOLD),
                "nonlinear_formal_g1_pass": bool(n_recall >= G1_COVERAGE_THRESHOLD),
            }
            for event in missing_events:
                if event.participant not in fold.valid_participants:
                    continue
                a_covered = any(interval_iou(prediction, event.interval) > G1_IOU_THRESHOLD for prediction in a_pred.get(event.participant, ()))
                n_covered = any(interval_iou(prediction, event.interval) > G1_IOU_THRESHOLD for prediction in n_pred.get(event.participant, ()))
                key = f"{event.participant}:{event.interval.start_ms}-{event.interval.end_ms}"
                if not a_covered and n_covered:
                    replay_comparison["recovered_events"].append(key)
                if a_covered and not n_covered:
                    replay_comparison["newly_lost_events"].append(key)
        replay_comparison["recovered_events"] = sorted(set(replay_comparison["recovered_events"]))
        replay_comparison["newly_lost_events"] = sorted(set(replay_comparison["newly_lost_events"]))
        replay_comparison["net_coverage_change"] = len(replay_comparison["recovered_events"]) - len(replay_comparison["newly_lost_events"])
        report["event_level_replay"] = {
            "status": "COMPLETED",
            "per_model": event_results,
            "missing_event_audit": {
                "per_event": missing_rows,
                "summary": _summarize_missing_events(missing_rows),
            },
            "comparison": replay_comparison,
            "formal_interpretation": "requires stable event-level improvement; no post-hoc threshold or aggregation changes permitted",
        }

    report["classification"] = {
        "decision_function_effect": "SUPPORTED" if window_gate else "UNSUPPORTED",
        "event_level_transfer": "INCONCLUSIVE" if not window_gate else "REQUIRES_EVENT_REVIEW",
        "candidate_model_design_review": "NOT_JUSTIFIED" if not window_gate else "PENDING_EVENT_REVIEW",
        "formal_g1": "NOT_RUN" if not window_gate else "REPLAY_REPORTED",
        "architecture": "FROZEN",
        "full_training": "BLOCKED",
    }
    report["_score_arrays"] = {
        "baseline_scores": global_scores["A"],
        "nonlinear_scores": global_scores["N"],
        "hard_negative": hard_negative,
    }
    report["stop"] = "STOP after A versus N under the preregistered imu_stats_v1 protocol"
    return report


def run_probe(output_dir: Path = OUTPUT_DIR) -> dict[str, object]:
    spec, spec_hash = _load_spec()
    report = _run_probe(spec, spec_hash)
    score_arrays = report.pop("_score_arrays", {})
    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_dir / "scores.npz",
        baseline_scores=np.asarray(score_arrays.get("baseline_scores", [])),
        nonlinear_scores=np.asarray(score_arrays.get("nonlinear_scores", [])),
        hard_negative=np.asarray(score_arrays.get("hard_negative", [])),
    )
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    report = run_probe(args.output_dir)
    print(json.dumps(report["classification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
