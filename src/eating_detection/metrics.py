from dataclasses import asdict, dataclass
from typing import Sequence


def interval_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class EventMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    start_mae_ms: float | None
    end_mae_ms: float | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def event_metrics(
    predicted: Sequence[tuple[int, int]],
    truth: Sequence[tuple[int, int]],
    iou_threshold: float,
) -> EventMetrics:
    if not 0 <= iou_threshold < 1:
        raise ValueError("iou_threshold must be in [0, 1)")
    candidates = sorted(
        (
            (score, predicted_index, truth_index)
            for predicted_index, prediction in enumerate(predicted)
            for truth_index, target in enumerate(truth)
            for score in (interval_iou(prediction, target),)
            if score > iou_threshold
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    used_predictions: set[int] = set()
    used_truth: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, predicted_index, truth_index in candidates:
        if predicted_index not in used_predictions and truth_index not in used_truth:
            used_predictions.add(predicted_index)
            used_truth.add(truth_index)
            matches.append((predicted_index, truth_index))

    tp = len(matches)
    fp = len(predicted) - tp
    fn = len(truth) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    if matches:
        start_mae = sum(
            abs(predicted[predicted_index][0] - truth[truth_index][0])
            for predicted_index, truth_index in matches
        ) / len(matches)
        end_mae = sum(
            abs(predicted[predicted_index][1] - truth[truth_index][1])
            for predicted_index, truth_index in matches
        ) / len(matches)
    else:
        start_mae = end_mae = None
    return EventMetrics(tp, fp, fn, precision, recall, f1, start_mae, end_mae)
