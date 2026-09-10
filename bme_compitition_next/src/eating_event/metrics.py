"""Official-style event-level evaluation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, order=True)
class EventInterval:
    """A half-open event interval in integer milliseconds."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.end_ms <= self.start_ms:
            raise ValueError("event end_ms must be greater than start_ms")


@dataclass(frozen=True)
class EventMatch:
    prediction_index: int
    truth_index: int
    iou: float


@dataclass(frozen=True)
class EventMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    start_mae_ms: float
    end_mae_ms: float
    matches: tuple[EventMatch, ...]


def interval_iou(left: EventInterval, right: EventInterval) -> float:
    intersection = max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))
    union = max(left.end_ms, right.end_ms) - min(left.start_ms, right.start_ms)
    return intersection / union


def _greedy_one_to_one_matches(
    predictions: Sequence[EventInterval],
    truths: Sequence[EventInterval],
    iou_threshold: float,
) -> tuple[EventMatch, ...]:
    possible: list[EventMatch] = []
    for prediction_index, prediction in enumerate(predictions):
        for truth_index, truth in enumerate(truths):
            iou = interval_iou(prediction, truth)
            if iou > iou_threshold:
                possible.append(EventMatch(prediction_index, truth_index, iou))

    possible.sort(key=lambda match: (-match.iou, match.prediction_index, match.truth_index))
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matches: list[EventMatch] = []
    for match in possible:
        if match.prediction_index in used_predictions or match.truth_index in used_truths:
            continue
        used_predictions.add(match.prediction_index)
        used_truths.add(match.truth_index)
        matches.append(match)
    return tuple(sorted(matches, key=lambda match: (match.prediction_index, match.truth_index)))


def evaluate_events(
    predictions: Sequence[EventInterval],
    truths: Sequence[EventInterval],
    *,
    iou_threshold: float = 0.25,
) -> EventMetrics:
    """Evaluate predicted events with strict IoU matching.

    A pair is a true positive only when ``IoU > iou_threshold``. Matching is
    one-to-one and deterministic; ties prefer lower input indices.
    """

    if not 0 <= iou_threshold < 1:
        raise ValueError("iou_threshold must be in [0, 1)")
    matches = _greedy_one_to_one_matches(predictions, truths, iou_threshold)
    tp = len(matches)
    fp = len(predictions) - tp
    fn = len(truths) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    if matches:
        start_errors = [
            abs(predictions[m.prediction_index].start_ms - truths[m.truth_index].start_ms)
            for m in matches
        ]
        end_errors = [
            abs(predictions[m.prediction_index].end_ms - truths[m.truth_index].end_ms)
            for m in matches
        ]
        start_mae_ms = sum(start_errors) / len(start_errors)
        end_mae_ms = sum(end_errors) / len(end_errors)
    else:
        start_mae_ms = 0.0
        end_mae_ms = 0.0

    return EventMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        start_mae_ms=start_mae_ms,
        end_mae_ms=end_mae_ms,
        matches=matches,
    )

