"""Frozen 16D candidate and A2 10D context feature definitions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, pi, sin, cos

import numpy as np

from .candidates import Candidate, SupportWindow

LOOKAROUND_MS = 300_000
OBSERVED_FRACTION_DIVISOR = 40


@dataclass(frozen=True, slots=True)
class ContextWindow:
    role_id: str
    component_id: str
    global_index: int
    start_ms: int
    end_ms: int
    relative: float


def _day_phase(time_ms: int) -> tuple[float, float]:
    phase = 2.0 * pi * ((time_ms % 86_400_000) / 86_400_000)
    return sin(phase), cos(phase)


def build_source_16d(
    support: Sequence[SupportWindow],
    *,
    start_ms: int,
    end_ms: int,
) -> np.ndarray:
    if not support or end_ms <= start_ms:
        raise ValueError("candidate support and nonempty interval are required")
    relatives = np.asarray([window.relative for window in support], dtype=np.float64)
    coverage = np.asarray([window.coverage for window in support], dtype=np.float64)
    if not np.isfinite(relatives).all() or not np.isfinite(coverage).all():
        raise ValueError("candidate source values must be finite")
    duration_seconds = (end_ms - start_ms) / 1000.0
    start_sin, start_cos = _day_phase(start_ms)
    end_sin, end_cos = _day_phase(end_ms)
    values = np.asarray(
        (
            relatives.max(),
            relatives.mean(),
            relatives.std(ddof=0),
            np.percentile(relatives, 25),
            np.percentile(relatives, 75),
            relatives.min(),
            len(support),
            duration_seconds,
            len(support) / duration_seconds,
            coverage.mean(),
            coverage.min(),
            coverage.max(),
            start_sin,
            start_cos,
            end_sin,
            end_cos,
        ),
        dtype=np.float64,
    )
    if values.shape != (16,) or not np.isfinite(values).all():
        raise ValueError("candidate feature construction failed")
    return values


def _region_summary(items: Sequence[ContextWindow]) -> tuple[float, float, float]:
    if not items:
        return 0.0, 0.0, 0.0
    scores = np.asarray([item.relative for item in items], dtype=np.float64)
    return (
        float(scores.mean()),
        float(np.count_nonzero(scores >= 0) / scores.size),
        float(min(scores.size / OBSERVED_FRACTION_DIVISOR, 1.0)),
    )


def _longest_positive_run_fraction(items: Sequence[ContextWindow]) -> float:
    run_count = 0
    run_end = 0
    largest = 0
    for item in items:
        if item.relative < 0:
            run_count = 0
            run_end = 0
        elif run_count and item.start_ms < run_end:
            run_count += 1
            run_end = max(run_end, item.end_ms)
        else:
            run_count = 1
            run_end = item.end_ms
        largest = max(largest, run_count)
    return largest / len(items) if items else 0.0


def build_26d(
    candidate: Candidate,
    context_windows: Sequence[ContextWindow],
) -> np.ndarray:
    """Construct the fixed 26D vector from the new 16D and role-local context."""

    ordered: list[ContextWindow] = []
    seen: set[int] = set()
    for item in context_windows:
        if item.role_id != candidate.role_id or item.component_id != candidate.component_id:
            raise ValueError("context window crosses role/component boundary")
        if item.global_index in seen:
            raise ValueError("duplicate global context-window index")
        if item.end_ms <= item.start_ms or not isfinite(item.relative):
            raise ValueError("invalid context window")
        seen.add(item.global_index)
        ordered.append(item)
    ordered.sort(key=lambda item: (item.start_ms, item.end_ms, item.global_index))

    inside: list[ContextWindow] = []
    pre: list[ContextWindow] = []
    post: list[ContextWindow] = []
    for item in ordered:
        midpoint = (item.start_ms + item.end_ms) // 2
        if candidate.start_ms <= midpoint < candidate.end_ms:
            inside.append(item)
        elif candidate.start_ms - LOOKAROUND_MS <= midpoint < candidate.start_ms:
            pre.append(item)
        elif candidate.end_ms <= midpoint < candidate.end_ms + LOOKAROUND_MS:
            post.append(item)
    if not inside:
        raise ValueError("candidate has no same-component scored window inside")
    if any(item.end_ms > candidate.end_ms + LOOKAROUND_MS for item in post):
        raise ValueError("post context exceeds the frozen lookahead")

    scores = np.asarray([item.relative for item in inside], dtype=np.float64)
    pre_mean, pre_positive, pre_observed = _region_summary(pre)
    post_mean, post_positive, post_observed = _region_summary(post)
    context = (
        float(scores.mean()),
        float(np.percentile(scores, 25, method="linear")),
        float(np.count_nonzero(scores >= 0) / scores.size),
        _longest_positive_run_fraction(inside),
        pre_mean,
        pre_positive,
        pre_observed,
        post_mean,
        post_positive,
        post_observed,
    )
    result = np.asarray(candidate.source_16d + context, dtype=np.float32)
    if result.shape != (26,) or not np.isfinite(result).all():
        raise ValueError("A2 feature vector must have 26 finite values")
    return result

