"""Pure, label-free extraction of the frozen ten A2 context features."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from eating_event.a2.contracts import ContextWindow
from eating_event.metrics import EventInterval


LOOKAROUND_MS = 300_000
OBSERVED_FRACTION_DIVISOR = 40


def _region_summary(items: Sequence[ContextWindow]) -> tuple[float, float, float]:
    if not items:
        return 0.0, 0.0, 0.0
    scores = np.asarray([item.relative for item in items], dtype=np.float64)
    return float(scores.mean()), float(np.count_nonzero(scores >= 0) / scores.size), float(min(scores.size / OBSERVED_FRACTION_DIVISOR, 1.0))


def _longest_positive_run_fraction(items: Sequence[ContextWindow]) -> float:
    run_count = 0
    run_end = 0
    largest = 0
    for item in items:
        if item.relative < 0:
            run_count = 0
            run_end = 0
            continue
        if run_count and item.start_ms < run_end:
            run_count += 1
            run_end = max(run_end, item.end_ms)
        else:
            run_count = 1
            run_end = item.end_ms
        largest = max(largest, run_count)
    return largest / len(items) if items else 0.0


def build_a2_features(
    *,
    source_16d: Sequence[int | float],
    interval: EventInterval,
    role_id: str,
    component_id: str,
    context_windows: Sequence[ContextWindow],
) -> np.ndarray:
    """Return a 26D float32 vector while retaining the 16D source values verbatim.

    The caller supplies one role/component stream. This function does not
    accept labels or evaluation truths, so feature construction cannot inspect
    either of them.
    """

    if len(source_16d) != 16:
        raise ValueError("source A1 candidate feature row must have 16 values")
    base = np.asarray(source_16d, dtype=np.float64)
    if not np.isfinite(base).all():
        raise ValueError("source A1 candidate feature row must be finite")
    if interval.end_ms <= interval.start_ms:
        raise ValueError("candidate interval must be nonempty")
    seen_indices: set[int] = set()
    ordered: list[ContextWindow] = []
    for item in context_windows:
        if item.role_id != role_id:
            raise ValueError("context window role mismatch")
        if item.component_id != component_id:
            raise ValueError("context window component mismatch")
        if item.global_window_index in seen_indices:
            raise ValueError("duplicate global context window index")
        seen_indices.add(item.global_window_index)
        ordered.append(item)
    ordered.sort(key=lambda item: (item.start_ms, item.end_ms, item.global_window_index))

    start_ms, end_ms = interval.start_ms, interval.end_ms
    inside: list[ContextWindow] = []
    pre: list[ContextWindow] = []
    post: list[ContextWindow] = []
    for item in ordered:
        midpoint = (item.start_ms + item.end_ms) // 2
        if start_ms <= midpoint < end_ms:
            inside.append(item)
        elif start_ms - LOOKAROUND_MS <= midpoint < start_ms:
            pre.append(item)
        elif end_ms <= midpoint < end_ms + LOOKAROUND_MS:
            post.append(item)
    if not inside:
        raise ValueError("candidate has no same-component scored window in its inside region")
    if any(item.end_ms > end_ms + LOOKAROUND_MS for item in post):
        raise ValueError("selected post window exceeds the frozen context lookahead")

    inside_scores = np.asarray([item.relative for item in inside], dtype=np.float64)
    inside_positive_fraction = float(np.count_nonzero(inside_scores >= 0) / inside_scores.size)
    pre_mean, pre_positive_fraction, pre_observed_fraction = _region_summary(pre)
    post_mean, post_positive_fraction, post_observed_fraction = _region_summary(post)
    context = (
        float(inside_scores.mean()),
        float(np.percentile(inside_scores, 25, method="linear")),
        inside_positive_fraction,
        _longest_positive_run_fraction(inside),
        pre_mean,
        pre_positive_fraction,
        pre_observed_fraction,
        post_mean,
        post_positive_fraction,
        post_observed_fraction,
    )
    values = np.asarray(tuple(source_16d) + context, dtype=np.float32)
    if values.shape != (26,) or not np.isfinite(values).all():
        raise ValueError("A2 feature extraction did not produce 26 finite values")
    return values
