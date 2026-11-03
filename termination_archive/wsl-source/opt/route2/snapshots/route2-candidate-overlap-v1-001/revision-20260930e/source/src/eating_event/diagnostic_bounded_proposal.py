"""Deterministic, non-production proposal-set diagnostics.

This module deliberately has no label, event, or model dependencies.  It turns
one recording's window score stream into a bounded set of interval hypotheses
and preserves a separately supplied baseline proposal set.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil
from typing import Iterable


@dataclass(frozen=True)
class WindowEvidence:
    index: int
    start_ms: int
    end_ms: int
    score: float
    crosses_hard_gap: bool


@dataclass(frozen=True)
class Proposal:
    record_path: str
    start_ms: int
    end_ms: int
    source: str
    boundary_variants: tuple[str, ...]
    source_indices: tuple[int, ...]
    support_max: float
    support_mean: float
    segment_id: int = -1
    region_id: int = -1


def build_contiguous_segments(
    windows: Iterable[WindowEvidence],
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    """Return deterministic contiguous, gap-safe segments.

    A window marked as crossing a hard gap is isolated.  A segment also ends
    when the local window indices are discontinuous or the next window starts
    after the previous window ends.  No labels or event boundaries are used.
    """

    ordered = tuple(sorted(windows, key=lambda item: item.index))
    if not ordered:
        return ()

    segments: list[tuple[int, tuple[int, ...]]] = []
    current: list[int] = []
    segment_id = 0
    previous: WindowEvidence | None = None

    for window in ordered:
        starts_new = (
            previous is None
            or not current
            or window.index != previous.index + 1
            or window.start_ms > previous.end_ms
            or previous.crosses_hard_gap
            or window.crosses_hard_gap
        )
        if starts_new and current:
            segments.append((segment_id, tuple(current)))
            segment_id += 1
            current = []
        current.append(window.index)
        previous = window

    if current:
        segments.append((segment_id, tuple(current)))
    return tuple(segments)


def _proposal_key(proposal: Proposal) -> tuple[str, int, int]:
    return proposal.record_path, proposal.start_ms, proposal.end_ms


def _merge_exact_duplicates(proposals: Iterable[Proposal]) -> tuple[Proposal, ...]:
    merged: dict[tuple[str, int, int], Proposal] = {}
    for proposal in proposals:
        key = _proposal_key(proposal)
        existing = merged.get(key)
        if existing is None:
            merged[key] = proposal
            continue
        merged[key] = replace(
            existing,
            boundary_variants=tuple(
                dict.fromkeys(existing.boundary_variants + proposal.boundary_variants)
            ),
            source_indices=tuple(sorted(set(existing.source_indices + proposal.source_indices))),
            support_max=max(existing.support_max, proposal.support_max),
            support_mean=max(existing.support_mean, proposal.support_mean),
        )
    return tuple(sorted(merged.values(), key=lambda item: (item.start_ms, item.end_ms)))


def build_extra_proposals(
    record_path: str,
    windows: Iterable[WindowEvidence],
    *,
    support_threshold: float,
    stride_ms: int = 7_500,
    min_support_windows: int = 2,
    max_per_recording: int = 24,
    max_per_hour: int = 16,
) -> tuple[Proposal, ...]:
    """Generate one frozen bounded set of low-score support hypotheses.

    Active support is a maximal run of score-qualified windows within one
    gap-safe segment.  Each run emits exactly three boundary hypotheses:
    support core, the highest-scoring window, and a one-stride expansion
    clipped to the segment.  Exact duplicate intervals are merged before the
    deterministic extra-only budget is applied.
    """

    if stride_ms <= 0 or min_support_windows <= 0:
        raise ValueError("stride_ms and min_support_windows must be positive")
    if max_per_recording < 0 or max_per_hour < 0:
        raise ValueError("proposal budgets must be non-negative")

    ordered = tuple(sorted(windows, key=lambda item: item.index))
    by_index = {window.index: window for window in ordered}
    segments = build_contiguous_segments(ordered)
    proposals: list[Proposal] = []

    for segment_id, indices in segments:
        segment_windows = tuple(by_index[index] for index in indices)
        segment_start = segment_windows[0].start_ms
        segment_end = segment_windows[-1].end_ms
        active_runs: list[tuple[WindowEvidence, ...]] = []
        current: list[WindowEvidence] = []

        for window in segment_windows:
            if window.score >= support_threshold:
                current.append(window)
            else:
                if len(current) >= min_support_windows:
                    active_runs.append(tuple(current))
                current = []
        if len(current) >= min_support_windows:
            active_runs.append(tuple(current))

        for region_id, region in enumerate(active_runs):
            region_indices = tuple(window.index for window in region)
            support_max = max(window.score for window in region)
            support_mean = sum(window.score for window in region) / len(region)
            core_start = region[0].start_ms
            core_end = region[-1].end_ms
            peak = max(region, key=lambda item: (-item.score, item.index))
            variants = (
                ("support_core", core_start, core_end),
                ("peak_window", peak.start_ms, peak.end_ms),
                (
                    "boundary_expanded",
                    max(segment_start, core_start - stride_ms),
                    min(segment_end, core_end + stride_ms),
                ),
            )
            for variant, start_ms, end_ms in variants:
                if end_ms <= start_ms:
                    continue
                proposals.append(
                    Proposal(
                        record_path=record_path,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        source="extra",
                        boundary_variants=(variant,),
                        source_indices=region_indices,
                        support_max=support_max,
                        support_mean=support_mean,
                        segment_id=segment_id,
                        region_id=region_id,
                    )
                )

    deduplicated = _merge_exact_duplicates(proposals)
    if not deduplicated:
        return ()

    record_start = min(window.start_ms for window in ordered)
    record_end = max(window.end_ms for window in ordered)
    duration_hours = max(1, record_end - record_start) / 3_600_000
    hour_cap = max(1, ceil(duration_hours * max_per_hour))
    effective_cap = min(max_per_recording, hour_cap)
    if effective_cap <= 0:
        return ()

    ranked = sorted(
        deduplicated,
        key=lambda item: (
            -item.support_max,
            -item.support_mean,
            item.boundary_variants[0],
            item.start_ms,
            item.end_ms,
        ),
    )
    return tuple(sorted(ranked[:effective_cap], key=lambda item: (item.start_ms, item.end_ms)))


def union_proposals(
    baseline: Iterable[Proposal],
    extra: Iterable[Proposal],
) -> tuple[Proposal, ...]:
    """Union A and extra proposals while preserving every A interval."""

    baseline_items = tuple(baseline)
    extra_items = tuple(extra)
    merged: dict[tuple[str, int, int], Proposal] = {}
    for proposal in baseline_items:
        key = _proposal_key(proposal)
        if key in merged:
            raise ValueError(f"duplicate baseline proposal: {key}")
        merged[key] = proposal

    for proposal in extra_items:
        key = _proposal_key(proposal)
        existing = merged.get(key)
        if existing is None:
            merged[key] = proposal
            continue
        if existing.source != "A":
            raise ValueError(f"duplicate non-baseline proposal: {key}")
        merged[key] = replace(
            existing,
            source="A+extra",
            boundary_variants=tuple(
                dict.fromkeys(existing.boundary_variants + proposal.boundary_variants)
            ),
            support_max=max(existing.support_max, proposal.support_max),
            support_mean=max(existing.support_mean, proposal.support_mean),
        )

    return tuple(
        sorted(
            merged.values(),
            key=lambda item: (item.record_path, item.start_ms, item.end_ms),
        )
    )
