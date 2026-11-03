"""Participant-safe A1 event metrics and separate acceptance decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from eating_event.a1.contracts import PredictionIdentity
from eating_event.metrics import EventInterval, interval_iou


@dataclass(frozen=True)
class TruthRecord:
    event_id: str
    participant_id: str
    interval: EventInterval


@dataclass(frozen=True)
class PredictionRecord:
    prediction_id: str
    participant_id: str
    record_id: str
    session_id: str
    source_segment_id: str | None
    interval: EventInterval

    @classmethod
    def from_decoded(cls, decoded: object) -> "PredictionRecord":
        identity = getattr(decoded, "identity")
        if not isinstance(identity, PredictionIdentity):
            raise ValueError("decoded prediction lacks PredictionIdentity")
        return cls(
            prediction_id=identity.stable_id if hasattr(identity, "stable_id") else str(identity),
            participant_id=identity.participant_id,
            record_id=identity.record_id,
            session_id=identity.session_id,
            source_segment_id=None,
            interval=getattr(decoded, "interval"),
        )


@dataclass(frozen=True)
class ParticipantMetrics:
    participant_id: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float | None
    f1: float | None
    start_mae_ms: float | None
    end_mae_ms: float | None
    matched_pairs: tuple[tuple[str, str, float], ...]
    unmatched_prediction_ids: tuple[str, ...]
    unmatched_truth_ids: tuple[str, ...]
    long_fp_count: int
    long_fp_fraction: float
    fp_per_hour: float | None
    fp_per_hour_reason: str | None


@dataclass(frozen=True)
class AggregateMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float | None
    start_mae_ms: float | None
    end_mae_ms: float | None
    matched_count: int
    participants: tuple[ParticipantMetrics, ...]
    long_fp_count: int
    long_fp_fraction: float


@dataclass(frozen=True)
class QualityDecision:
    pooled_f1: float | None
    numeric_minimum: bool
    numeric_ideal: bool
    majority_folds: bool
    quality_per_fold: bool
    stage_minimum: bool
    stage_ideal: bool
    long_fp_fraction: float
    worst_start_mae_ms: float | None
    worst_end_mae_ms: float | None


def _match(
    predictions: Sequence[PredictionRecord],
    truths: Sequence[TruthRecord],
    iou_threshold: float,
) -> tuple[tuple[int, int, float], ...]:
    possible: list[tuple[int, int, float]] = []
    for p_index, prediction in enumerate(predictions):
        for t_index, truth in enumerate(truths):
            iou = interval_iou(prediction.interval, truth.interval)
            if iou > iou_threshold:
                possible.append((p_index, t_index, iou))
    possible.sort(key=lambda item: (-item[2], item[0], item[1]))
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matches = []
    for match in possible:
        if match[0] in used_predictions or match[1] in used_truths:
            continue
        used_predictions.add(match[0])
        used_truths.add(match[1])
        matches.append(match)
    return tuple(sorted(matches, key=lambda item: (item[0], item[1])))


def _participant_metrics(
    participant_id: str,
    predictions: Sequence[PredictionRecord],
    truths: Sequence[TruthRecord],
    *,
    iou_threshold: float,
    long_fp_ms: int,
    monitor_ms: int | None,
) -> ParticipantMetrics:
    ordered_predictions = tuple(sorted(predictions, key=lambda item: item.prediction_id))
    ordered_truths = tuple(sorted(truths, key=lambda item: item.event_id))
    matches = _match(ordered_predictions, ordered_truths, iou_threshold)
    matched_predictions = {item[0] for item in matches}
    matched_truths = {item[1] for item in matches}
    unmatched_predictions = tuple(
        prediction.prediction_id
        for index, prediction in enumerate(ordered_predictions)
        if index not in matched_predictions
    )
    unmatched_truths = tuple(
        truth.event_id for index, truth in enumerate(ordered_truths) if index not in matched_truths
    )
    tp = len(matches)
    fp = len(unmatched_predictions)
    fn = len(unmatched_truths)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    if matches:
        start_mae = sum(
            abs(ordered_predictions[p].interval.start_ms - ordered_truths[t].interval.start_ms)
            for p, t, _ in matches
        ) / len(matches)
        end_mae = sum(
            abs(ordered_predictions[p].interval.end_ms - ordered_truths[t].interval.end_ms)
            for p, t, _ in matches
        ) / len(matches)
    else:
        start_mae = end_mae = None
    matched_pairs = tuple(
        (ordered_predictions[p].prediction_id, ordered_truths[t].event_id, iou)
        for p, t, iou in matches
    )
    long_fp_count = sum(
        ordered_predictions[index].interval.end_ms - ordered_predictions[index].interval.start_ms >= long_fp_ms
        for index in range(len(ordered_predictions))
        if index not in matched_predictions
    )
    long_fraction = long_fp_count / fp if fp else 0.0
    if monitor_ms is None or monitor_ms <= 0:
        fp_per_hour = None
        fp_reason = "accepted monitoring duration unavailable"
    else:
        fp_per_hour = fp / (monitor_ms / 3_600_000.0)
        fp_reason = None
    return ParticipantMetrics(
        participant_id=participant_id,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        start_mae_ms=start_mae,
        end_mae_ms=end_mae,
        matched_pairs=matched_pairs,
        unmatched_prediction_ids=unmatched_predictions,
        unmatched_truth_ids=unmatched_truths,
        long_fp_count=long_fp_count,
        long_fp_fraction=long_fraction,
        fp_per_hour=fp_per_hour,
        fp_per_hour_reason=fp_reason,
    )


def evaluate_participants(
    predictions: Sequence[PredictionRecord],
    truths: Sequence[TruthRecord],
    *,
    iou_threshold: float = 0.25,
    long_fp_ms: int = 600_000,
    monitoring_ms_by_participant: dict[str, int] | None = None,
    participant_ids: Sequence[str] = (),
) -> AggregateMetrics:
    if not 0 <= iou_threshold < 1:
        raise ValueError("iou_threshold must be in [0, 1)")
    prediction_by_participant: dict[str, list[PredictionRecord]] = {}
    truth_by_participant: dict[str, list[TruthRecord]] = {}
    for prediction in predictions:
        prediction_by_participant.setdefault(prediction.participant_id, []).append(prediction)
    for truth in truths:
        truth_by_participant.setdefault(truth.participant_id, []).append(truth)
    participants = sorted(set(participant_ids) | set(prediction_by_participant) | set(truth_by_participant))
    per_participant = tuple(
        _participant_metrics(
            participant,
            prediction_by_participant.get(participant, ()),
            truth_by_participant.get(participant, ()),
            iou_threshold=iou_threshold,
            long_fp_ms=long_fp_ms,
            monitor_ms=(monitoring_ms_by_participant or {}).get(participant),
        )
        for participant in participants
    )
    tp = sum(item.tp for item in per_participant)
    fp = sum(item.fp for item in per_participant)
    fn = sum(item.fn for item in per_participant)
    matches = sum(len(item.matched_pairs) for item in per_participant)
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    start_values = [item.start_mae_ms for item in per_participant if item.start_mae_ms is not None]
    end_values = [item.end_mae_ms for item in per_participant if item.end_mae_ms is not None]
    return AggregateMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=tp / (tp + fp) if tp + fp else 0.0,
        recall=tp / (tp + fn) if tp + fn else 0.0,
        f1=f1,
        start_mae_ms=sum((item.start_mae_ms or 0) * len(item.matched_pairs) for item in per_participant) / matches if matches else None,
        end_mae_ms=sum((item.end_mae_ms or 0) * len(item.matched_pairs) for item in per_participant) / matches if matches else None,
        matched_count=matches,
        participants=per_participant,
        long_fp_count=sum(item.long_fp_count for item in per_participant),
        long_fp_fraction=(sum(item.long_fp_count for item in per_participant) / fp) if fp else 0.0,
    )


def evaluate_quality(results: Sequence[AggregateMetrics], *, outer_fold_f1: Sequence[float | None], pooled: AggregateMetrics | None = None) -> QualityDecision:
    if not results:
        raise ValueError("at least one result is required")
    if pooled is not None and (len(results) != 5 or len(outer_fold_f1) != 5):
        raise ValueError("quality requires five complete folds")
    pooled = pooled if pooled is not None else results[-1]
    f1 = pooled.f1
    fold_values = [float(value) for value in outer_fold_f1 if value is not None]
    majority = len(fold_values) == 5 and sum(value >= 0.66 for value in fold_values) >= 3
    quality = all(
        result.start_mae_ms is not None
        and result.end_mae_ms is not None
        and result.start_mae_ms <= 900_000
        and result.end_mae_ms <= 900_000
        and result.long_fp_fraction <= 0.25
        for result in results
    )
    worst_start = max(
        (result.start_mae_ms for result in results if result.start_mae_ms is not None),
        default=None,
    )
    worst_end = max(
        (result.end_mae_ms for result in results if result.end_mae_ms is not None),
        default=None,
    )
    long_fraction = max((result.long_fp_fraction for result in results), default=0.0)
    numeric_minimum = f1 is not None and f1 >= 0.66
    numeric_ideal = f1 is not None and f1 >= 0.80
    return QualityDecision(
        pooled_f1=f1,
        numeric_minimum=numeric_minimum,
        numeric_ideal=numeric_ideal,
        majority_folds=majority,
        quality_per_fold=quality,
        stage_minimum=bool(numeric_minimum and majority and quality),
        stage_ideal=bool(numeric_ideal and majority and quality),
        long_fp_fraction=long_fraction,
        worst_start_mae_ms=worst_start,
        worst_end_mae_ms=worst_end,
    )
