from dataclasses import dataclass


@dataclass(frozen=True)
class MealRecord:
    participant_id: str
    start_ms: int
    end_ms: int
    quality_reason: str


def clean_interval(
    start_ms: int | None,
    end_ms: int | None,
    coverage: tuple[int, int],
) -> tuple[tuple[int, int] | None, str]:
    if coverage[1] <= coverage[0]:
        raise ValueError("coverage must have positive duration")
    if start_ms is None or end_ms is None:
        return None, "missing_endpoint"
    start, end = int(start_ms), int(end_ms)
    reason = "ok"
    if start > end:
        start, end = end, start
        reason = "reversed_swapped"
    if start == end:
        return None, "zero_duration_excluded"
    original = (start, end)
    start = max(start, coverage[0])
    end = min(end, coverage[1])
    if end <= start:
        return None, "outside_sensor_coverage"
    if reason == "ok" and (start, end) != original:
        reason = "clipped_to_coverage"
    return (start, end), reason


def label_window(
    window: tuple[int, int],
    intervals: list[tuple[int, int]],
    positive_overlap: float,
    mode: str,
) -> float | None:
    """Return a window target using a continuous or thresholded boundary rule.

    ``soft`` preserves the overlap ratio for every window. ``ignore`` keeps
    zero-overlap windows negative, ignores partial overlaps below the
    threshold, and uses a hard positive target at or above the threshold.
    """
    if mode not in {"soft", "ignore"}:
        raise ValueError("mode must be soft or ignore")
    if not 0 < positive_overlap <= 1:
        raise ValueError("positive_overlap must be in (0, 1]")
    w0, w1 = window
    duration = w1 - w0
    if duration <= 0:
        raise ValueError("window must have positive duration")
    overlap = max(
        (min(w1, end) - max(w0, start) for start, end in intervals),
        default=0,
    )
    ratio = max(0.0, min(1.0, overlap / duration))
    if mode == "soft":
        return ratio
    if ratio == 0:
        return 0.0
    if ratio >= positive_overlap:
        return 1.0
    return None
