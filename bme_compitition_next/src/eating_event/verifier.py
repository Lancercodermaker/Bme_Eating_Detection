"""Event-level candidate clustering and verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from eating_event.data.windows import WindowRecord
from eating_event.metrics import EventInterval, interval_iou


@dataclass(frozen=True)
class EventCandidate:
    interval: EventInterval
    features: np.ndarray
    label: int
    window_indices: tuple[int, ...]


def _candidate_features(
    windows: Sequence[WindowRecord],
    scores: np.ndarray,
    indices: list[int],
    start_ms: int,
    end_ms: int,
) -> np.ndarray:
    selected_scores = scores[indices]
    coverages = np.asarray([windows[index].coverage for index in indices], dtype=np.float64)
    duration_seconds = (end_ms - start_ms) / 1000.0
    density = len(indices) / max(duration_seconds, 1.0)
    return np.asarray(
        [
            float(selected_scores.max()),
            float(selected_scores.mean()),
            float(selected_scores.std()),
            float(np.percentile(selected_scores, 25)),
            float(np.percentile(selected_scores, 75)),
            float(selected_scores.min()),
            float(len(indices)),
            float(duration_seconds),
            float(density),
            float(coverages.mean()),
            float(coverages.min()),
            float(coverages.max()),
        ],
        dtype=np.float64,
    )


def build_event_candidates(
    windows: Sequence[WindowRecord],
    window_scores: np.ndarray,
    *,
    candidate_threshold: float,
    fuse_gap_ms: int = 600_000,
    truths: Sequence[EventInterval] = (),
) -> list[EventCandidate]:
    """Cluster high-recall windows and label the resulting event candidates."""

    scores = np.asarray(window_scores, dtype=np.float64)
    if scores.ndim != 1 or scores.size != len(windows):
        raise ValueError("window_scores must align with windows")
    if fuse_gap_ms < 0:
        raise ValueError("fuse_gap_ms must be non-negative")
    selected = [index for index, score in enumerate(scores) if score >= candidate_threshold]
    if not selected:
        return []

    candidates: list[EventCandidate] = []
    current_indices = [selected[0]]
    current_start = windows[selected[0]].window.start_ms
    current_end = windows[selected[0]].window.end_ms

    def flush(indices: list[int], start_ms: int, end_ms: int) -> None:
        interval = EventInterval(start_ms, end_ms)
        label = int(any(interval_iou(interval, truth) > 0.25 for truth in truths))
        candidates.append(
            EventCandidate(
                interval=interval,
                features=_candidate_features(windows, scores, indices, start_ms, end_ms),
                label=label,
                window_indices=tuple(indices),
            )
        )

    for index in selected[1:]:
        start_ms = windows[index].window.start_ms
        end_ms = windows[index].window.end_ms
        if start_ms <= current_end + fuse_gap_ms:
            current_indices.append(index)
            current_end = max(current_end, end_ms)
        else:
            flush(current_indices, current_start, current_end)
            current_indices = [index]
            current_start, current_end = start_ms, end_ms
    flush(current_indices, current_start, current_end)
    return candidates


class EventVerifier:
    def __init__(self, estimator: object) -> None:
        self.estimator = estimator

    def predict_scores(self, features: np.ndarray) -> np.ndarray:
        return np.asarray(self.estimator.predict_proba(features)[:, 1], dtype=np.float64)


def fit_event_verifier(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    random_state: int = 20260910,
    positive_weight: float = 3.0,
) -> EventVerifier:
    from sklearn.ensemble import HistGradientBoostingClassifier

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int8)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size:
        raise ValueError("features and labels must have aligned shapes")
    keep = y >= 0
    if keep.sum() == 0 or np.unique(y[keep]).size != 2:
        raise ValueError("event verifier training needs both positive and negative labels")
    weights = np.ones(int(keep.sum()), dtype=np.float64)
    weights[y[keep] == 1] = positive_weight
    estimator = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=250,
        min_samples_leaf=1,
        max_leaf_nodes=15,
        l2_regularization=1e-3,
        random_state=random_state,
    )
    estimator.fit(x[keep], y[keep], sample_weight=weights)
    return EventVerifier(estimator)


def decode_event_candidates(
    candidates: Sequence[EventCandidate],
    scores: np.ndarray,
    *,
    threshold: float,
    min_duration_ms: int = 180_000,
) -> list[EventInterval]:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or values.size != len(candidates):
        raise ValueError("scores must align with event candidates")
    return [
        candidate.interval
        for candidate, score in zip(candidates, values)
        if score >= threshold and candidate.interval.end_ms - candidate.interval.start_ms >= min_duration_ms
    ]

