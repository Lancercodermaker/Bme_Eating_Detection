from statistics import fmean

from .metrics import event_metrics


def decode_windows(
    windows,
    probabilities,
    threshold: float = 0.5,
    merge_gap_ms: int = 0,
    min_duration_ms: int = 0,
):
    if len(windows) != len(probabilities):
        raise ValueError("windows and probabilities must have equal lengths")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    if merge_gap_ms < 0 or min_duration_ms < 0:
        raise ValueError("merge_gap_ms and min_duration_ms must be non-negative")

    active = [window for window, probability in zip(windows, probabilities) if probability >= threshold]
    if not active:
        return []
    events = []
    start, end = active[0]
    for next_start, next_end in active[1:]:
        if next_start - end <= merge_gap_ms:
            end = max(end, next_end)
        else:
            if end - start >= min_duration_ms:
                events.append((start, end))
            start, end = next_start, next_end
    if end - start >= min_duration_ms:
        events.append((start, end))
    return events


def tune_decoder(
    validation_windows,
    validation_probabilities,
    validation_truth,
    iou_threshold: float = 0.25,
):
    if not (
        len(validation_windows)
        == len(validation_probabilities)
        == len(validation_truth)
    ):
        raise ValueError("validation inputs must have equal participant counts")

    best = None
    for threshold in (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80):
        for merge_gap_ms in (0, 3000, 6000, 9000):
            for min_duration_ms in (0, 3000, 6000):
                scores = []
                for windows, probabilities, truth in zip(
                    validation_windows, validation_probabilities, validation_truth
                ):
                    predicted = decode_windows(
                        windows,
                        probabilities,
                        threshold,
                        merge_gap_ms,
                        min_duration_ms,
                    )
                    scores.append(event_metrics(predicted, truth, iou_threshold).f1)
                score = fmean(scores) if scores else 0.0
                candidate = (
                    score,
                    -threshold,
                    -merge_gap_ms,
                    -min_duration_ms,
                    threshold,
                    merge_gap_ms,
                    min_duration_ms,
                )
                if best is None or candidate > best:
                    best = candidate
    if best is None:
        raise ValueError("validation data must contain at least one participant")
    return {
        "threshold": best[4],
        "merge_gap_ms": best[5],
        "min_duration_ms": best[6],
    }
