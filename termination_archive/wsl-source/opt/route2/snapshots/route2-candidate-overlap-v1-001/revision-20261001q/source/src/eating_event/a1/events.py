"""A1 candidate semantics and constrained decoder."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

import numpy as np

from eating_event.a1.boundaries import SupportComponent, build_support_components
from eating_event.a1.contracts import EVENT_FEATURE_DIM, PredictionIdentity, WindowIdentity
from eating_event.a1.inputs import A1Window, TruthRecord
from eating_event.metrics import EventInterval, interval_iou


@dataclass(frozen=True)
class A1Candidate:
    candidate_id: str
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    interval: EventInterval
    features: np.ndarray
    support_indices: tuple[WindowIdentity, ...]
    source_segment_id: None = None
    boundary_kind: str = "observed_window_support_component_v1"
    label: int | None = None

    def __post_init__(self) -> None:
        values = np.asarray(self.features, dtype=np.float64)
        if values.shape != (EVENT_FEATURE_DIM,):
            raise ValueError(f"event features must have shape ({EVENT_FEATURE_DIM},)")
        if not np.isfinite(values).all():
            raise ValueError("event features must be finite")
        if self.label not in {None, 0, 1}:
            raise ValueError("candidate label must be None, 0, or 1")


@dataclass(frozen=True)
class DecodedPrediction:
    identity: PredictionIdentity
    interval: EventInterval
    source_candidate_ids: tuple[str, ...]


def _day_phase(time_ms: int) -> tuple[float, float]:
    day_ms = 86_400_000
    phase = 2.0 * math.pi * ((time_ms % day_ms) / day_ms)
    return math.sin(phase), math.cos(phase)


def _event_features(
    windows: Sequence[A1Window],
    relative_scores: np.ndarray,
    indices: Sequence[int],
    start_ms: int,
    end_ms: int,
) -> np.ndarray:
    selected = np.asarray([relative_scores[index] for index in indices], dtype=np.float64)
    coverages = np.asarray([windows[index].coverage for index in indices], dtype=np.float64)
    duration_seconds = (end_ms - start_ms) / 1000.0
    density = len(indices) / duration_seconds
    start_sin, start_cos = _day_phase(start_ms)
    end_sin, end_cos = _day_phase(end_ms)
    values = np.asarray(
        [
            selected.max(),
            selected.mean(),
            selected.std(),
            np.percentile(selected, 25),
            np.percentile(selected, 75),
            selected.min(),
            len(indices),
            duration_seconds,
            density,
            coverages.mean(),
            coverages.min(),
            coverages.max(),
            start_sin,
            start_cos,
            end_sin,
            end_cos,
        ],
        dtype=np.float64,
    )
    if values.shape != (EVENT_FEATURE_DIM,) or not np.isfinite(values).all():
        raise ValueError("event feature construction failed")
    return values


def build_candidates(
    windows: Sequence[A1Window],
    raw_scores: Sequence[float] | np.ndarray,
    *,
    threshold_reference: float,
    fuse_gap_ms: int,
) -> list[A1Candidate]:
    """Build candidates from scores only; truth is intentionally not accepted."""

    if not windows:
        return []
    scores = np.asarray(raw_scores, dtype=np.float64)
    if scores.ndim != 1 or scores.size != len(windows):
        raise ValueError("raw_scores must align with windows")
    if not np.isfinite(scores).all() or not np.isfinite(threshold_reference):
        raise ValueError("scores and threshold reference must be finite")
    if fuse_gap_ms < 0:
        raise ValueError("fuse_gap_ms must be non-negative")
    relative = scores - float(threshold_reference)
    selected = [index for index, score in enumerate(relative) if score >= 0]
    if not selected:
        return []
    components = build_support_components(list(windows))
    component_by_row = {
        row_index: component
        for component in components
        for row_index in component.window_indices
    }
    selected_by_component: dict[str, list[int]] = {}
    for index in selected:
        selected_by_component.setdefault(component_by_row[windows[index].identity.row_index].component_id, []).append(index)
    candidates: list[A1Candidate] = []
    for component in components:
        indices = selected_by_component.get(component.component_id, [])
        if not indices:
            continue
        indices.sort(key=lambda index: (windows[index].start_ms, windows[index].end_ms, index))
        current = [indices[0]]
        current_start = windows[indices[0]].start_ms
        current_end = windows[indices[0]].end_ms
        component_ordinal = 0

        def flush() -> None:
            nonlocal component_ordinal
            support = tuple(windows[index].identity for index in current)
            candidate_id = f"{component.component_id}|candidate-{component_ordinal}"
            candidates.append(
                A1Candidate(
                    candidate_id=candidate_id,
                    participant_id=component.participant_id,
                    record_id=component.record_id,
                    session_id=component.session_id,
                    component_id=component.component_id,
                    interval=EventInterval(current_start, current_end),
                    features=_event_features(windows, relative, current, current_start, current_end),
                    support_indices=support,
                )
            )
            component_ordinal += 1

        for index in indices[1:]:
            if windows[index].start_ms <= current_end + fuse_gap_ms:
                current.append(index)
                current_end = max(current_end, windows[index].end_ms)
            else:
                flush()
                current = [index]
                current_start = windows[index].start_ms
                current_end = windows[index].end_ms
        flush()
    return candidates


def label_candidates(candidates: Sequence[A1Candidate], truths: Sequence[EventInterval]) -> list[A1Candidate]:
    """Attach evaluation/training labels in a separate, truth-aware phase."""

    return [
        replace(candidate, label=int(any(interval_iou(candidate.interval, truth) > 0.25 for truth in truths)))
        for candidate in candidates
    ]


def decode_candidates(
    candidates: Sequence[A1Candidate],
    verifier_scores: Sequence[float] | np.ndarray,
    *,
    threshold: float,
    min_duration_ms: int,
    decode_fuse_gap_ms: int,
) -> list[DecodedPrediction]:
    """Apply threshold, duration, then same-component fusion in that order."""

    scores = np.asarray(verifier_scores, dtype=np.float64)
    if scores.ndim != 1 or scores.size != len(candidates):
        raise ValueError("verifier_scores must align with candidates")
    if not np.isfinite(scores).all():
        raise ValueError("verifier scores must be finite")
    if min_duration_ms < 0 or decode_fuse_gap_ms < 0:
        raise ValueError("decoder durations/gaps must be non-negative")
    selected = [
        index
        for index, (candidate, score) in enumerate(zip(candidates, scores))
        if score >= threshold and candidate.interval.end_ms - candidate.interval.start_ms >= min_duration_ms
    ]
    selected.sort(key=lambda index: (candidates[index].participant_id, candidates[index].component_id, candidates[index].interval.start_ms, index))
    predictions: list[DecodedPrediction] = []
    current: list[int] = []
    current_start = current_end = 0

    def flush() -> None:
        if not current:
            return
        first = candidates[current[0]]
        identity = PredictionIdentity(
            first.participant_id,
            first.record_id,
            first.session_id,
            first.component_id,
            len(predictions),
        )
        predictions.append(
            DecodedPrediction(
                identity=identity,
                interval=EventInterval(current_start, current_end),
                source_candidate_ids=tuple(candidates[index].candidate_id for index in current),
            )
        )

    for index in selected:
        candidate = candidates[index]
        if not current:
            current = [index]
            current_start, current_end = candidate.interval.start_ms, candidate.interval.end_ms
            continue
        previous = candidates[current[-1]]
        can_fuse = (
            candidate.participant_id == previous.participant_id
            and candidate.record_id == previous.record_id
            and candidate.session_id == previous.session_id
            and candidate.component_id == previous.component_id
            and candidate.interval.start_ms <= current_end + decode_fuse_gap_ms
        )
        if can_fuse:
            current.append(index)
            current_end = max(current_end, candidate.interval.end_ms)
        else:
            flush()
            current = [index]
            current_start, current_end = candidate.interval.start_ms, candidate.interval.end_ms
    flush()
    return predictions
