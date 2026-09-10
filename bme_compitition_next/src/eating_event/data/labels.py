"""Window labels derived from event intervals without sampling shortcuts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from eating_event.metrics import EventInterval


class WindowLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    IGNORE = "ignore"


@dataclass(frozen=True)
class WindowLabelResult:
    label: WindowLabel
    overlap_fraction: float
    nearest_event_distance_ms: int | None


def _intersection_ms(left: EventInterval, right: EventInterval) -> int:
    return max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))


def _distance_ms(left: EventInterval, right: EventInterval) -> int:
    if _intersection_ms(left, right) > 0:
        return 0
    if left.end_ms <= right.start_ms:
        return right.start_ms - left.end_ms
    return left.start_ms - right.end_ms


def label_window(
    window: EventInterval,
    truths: Sequence[EventInterval],
    *,
    positive_overlap: float = 0.5,
    negative_distance_ms: int = 300_000,
) -> WindowLabelResult:
    """Assign positive/negative/ignore using explicit event proximity rules.

    Overlap is normalized by window duration. A window that is neither
    sufficiently covered by an event nor sufficiently far from every event is
    ignored instead of becoming a noisy negative.
    """

    if not 0 < positive_overlap <= 1:
        raise ValueError("positive_overlap must be in (0, 1]")
    if negative_distance_ms < 0:
        raise ValueError("negative_distance_ms must be non-negative")
    if not truths:
        return WindowLabelResult(WindowLabel.NEGATIVE, 0.0, None)

    overlap_fraction = max(
        _intersection_ms(window, truth) / (window.end_ms - window.start_ms)
        for truth in truths
    )
    nearest_distance = min(_distance_ms(window, truth) for truth in truths)
    if overlap_fraction >= positive_overlap:
        label = WindowLabel.POSITIVE
    elif nearest_distance >= negative_distance_ms:
        label = WindowLabel.NEGATIVE
    else:
        label = WindowLabel.IGNORE
    return WindowLabelResult(label, overlap_fraction, nearest_distance)

