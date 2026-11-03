"""Bounded diagnostic helpers for the approved event-balanced objective probe.

This module is intentionally not imported by the production candidate path.  It
keeps the event-weight formula and its audit checks separate from the frozen
production implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from eating_event.candidates import CandidateModel


def compute_event_balanced_sample_weights(
    labels: np.ndarray,
    event_ids: np.ndarray,
    *,
    positive_weight_total_per_row: float = 3.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return frozen event-balanced weights and a machine-checkable audit.

    Positive rows must have exactly one non-empty event id.  Negative rows keep
    weight one and IGNORE rows keep weight zero.  The total positive weight is
    ``positive_weight_total_per_row * N_pos`` and every included event receives
    the same total positive weight.
    """

    y = np.asarray(labels, dtype=np.int8)
    ids = np.asarray(event_ids, dtype=object)
    if y.ndim != 1 or ids.ndim != 1 or y.size != ids.size:
        raise ValueError("labels and event_ids must be aligned one-dimensional arrays")
    if positive_weight_total_per_row <= 0:
        raise ValueError("positive_weight_total_per_row must be positive")

    positive = y == 1
    negative = y == 0
    ignore = y == -1
    if np.any(~(positive | negative | ignore)):
        raise ValueError("labels must be in {-1, 0, 1}")

    positive_ids: list[str] = []
    for index in np.flatnonzero(positive):
        value = ids[index]
        if value is None or str(value).strip() == "":
            raise ValueError("every positive row must belong to exactly one event")
        positive_ids.append(str(value))

    event_counts: dict[str, int] = {}
    for event_id in positive_ids:
        event_counts[event_id] = event_counts.get(event_id, 0) + 1

    weights = np.zeros(y.size, dtype=np.float64)
    weights[negative] = 1.0
    n_positive = int(positive.sum())
    event_count = len(event_counts)
    if n_positive:
        if event_count == 0:
            raise ValueError("positive rows require at least one event")
        total_positive_weight = float(positive_weight_total_per_row) * n_positive
        for index in np.flatnonzero(positive):
            event_id = str(ids[index])
            weights[index] = total_positive_weight / (event_count * event_counts[event_id])

    event_masses = {
        event_id: float(weights[positive & (ids == event_id)].sum())
        for event_id in event_counts
    }
    if event_masses:
        masses = np.asarray(list(event_masses.values()), dtype=np.float64)
        if not np.allclose(masses, masses[0], rtol=1e-12, atol=1e-8):
            raise AssertionError("event-balanced positive masses are not equal")
    expected_total = float(positive_weight_total_per_row) * n_positive
    if not np.isclose(float(weights[positive].sum()), expected_total, rtol=1e-12, atol=1e-8):
        raise AssertionError("positive weight total does not match the frozen formula")
    if not np.all(weights[negative] == 1.0) or not np.all(weights[ignore] == 0.0):
        raise AssertionError("negative/IGNORE weights changed")

    positive_weights = weights[positive]
    audit = {
        "positive_row_count": n_positive,
        "negative_row_count": int(negative.sum()),
        "ignore_row_count": int(ignore.sum()),
        "event_count": event_count,
        "positive_weight_total": float(weights[positive].sum()),
        "expected_positive_weight_total": expected_total,
        "event_masses": event_masses,
        "positive_weight_min": float(positive_weights.min()) if n_positive else None,
        "positive_weight_median": float(np.median(positive_weights)) if n_positive else None,
        "positive_weight_max": float(positive_weights.max()) if n_positive else None,
        "positive_weight_max_min_ratio": (
            float(positive_weights.max() / positive_weights.min()) if n_positive else None
        ),
    }
    return weights, audit


def fit_diagnostic_candidate_model(
    features: np.ndarray,
    labels: np.ndarray,
    event_ids: np.ndarray,
    *,
    variant: str,
    random_state: int = 20260910,
    max_iter: int = 100,
) -> tuple[CandidateModel, dict[str, Any]]:
    """Fit exactly the frozen HGB A/E variant for the diagnostic runner."""

    from sklearn.ensemble import HistGradientBoostingClassifier

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int8)
    ids = np.asarray(event_ids, dtype=object)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size or ids.size != y.size:
        raise ValueError("features, labels, and event_ids must be aligned")
    if variant not in {"A", "E"}:
        raise ValueError("variant must be A or E")
    if max_iter <= 0:
        raise ValueError("max_iter must be positive")

    keep = y >= 0
    if keep.sum() == 0 or np.unique(y[keep]).size != 2:
        raise ValueError("candidate training needs both positive and negative labels")
    if variant == "E":
        full_weights, audit = compute_event_balanced_sample_weights(y, ids)
        weights = full_weights[keep]
    else:
        weights = np.ones(int(keep.sum()), dtype=np.float64)
        weights[y[keep] == 1] = 3.0
        audit = {
            "positive_row_count": int((y[keep] == 1).sum()),
            "negative_row_count": int((y[keep] == 0).sum()),
            "ignore_row_count": int((y < 0).sum()),
            "event_count": None,
            "positive_weight_total": float(weights[y[keep] == 1].sum()),
            "expected_positive_weight_total": float(3.0 * (y[keep] == 1).sum()),
            "event_masses": None,
            "positive_weight_min": 3.0,
            "positive_weight_median": 3.0,
            "positive_weight_max": 3.0,
            "positive_weight_max_min_ratio": 1.0,
        }
    if weights.size != int(keep.sum()):
        raise AssertionError("fit weights must align with non-IGNORE rows")

    estimator = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=max_iter,
        min_samples_leaf=1,
        max_leaf_nodes=31,
        l2_regularization=1e-3,
        random_state=random_state,
    )
    estimator.fit(x[keep], y[keep], sample_weight=weights if variant == "E" else weights)
    return CandidateModel(estimator), audit


def unique_overlapping_event_ids(
    participants: Sequence[str],
    starts_ms: np.ndarray,
    ends_ms: np.ndarray,
    labels: np.ndarray,
    events: Sequence[dict[str, Any]],
) -> tuple[np.ndarray, dict[str, int]]:
    """Resolve positive-row event ownership without using validation labels."""

    participant_array = np.asarray(participants, dtype=object)
    starts = np.asarray(starts_ms, dtype=np.int64)
    ends = np.asarray(ends_ms, dtype=np.int64)
    y = np.asarray(labels, dtype=np.int8)
    if not (participant_array.ndim == starts.ndim == ends.ndim == y.ndim == 1):
        raise ValueError("row ownership inputs must be one-dimensional")
    if not (participant_array.size == starts.size == ends.size == y.size):
        raise ValueError("row ownership inputs must be aligned")

    normalized_events = [
        {
            "event_id": str(event["event_id"]),
            "participant_id": str(event["participant_id"]),
            "start_ms": int(event["start_ms"]),
            "end_ms": int(event["end_ms"]),
        }
        for event in events
    ]
    owners = np.empty(y.size, dtype=object)
    owners[:] = None
    counts = {"positive_rows": 0, "zero_owner": 0, "multi_owner": 0, "max_owner": 0}
    for index in np.flatnonzero(y == 1):
        counts["positive_rows"] += 1
        matches = [
            event
            for event in normalized_events
            if event["participant_id"] == str(participant_array[index])
            and event["start_ms"] < int(ends[index])
            and int(starts[index]) < event["end_ms"]
        ]
        counts["max_owner"] = max(counts["max_owner"], len(matches))
        if len(matches) == 0:
            counts["zero_owner"] += 1
            continue
        if len(matches) > 1:
            counts["multi_owner"] += 1
            continue
        owners[index] = matches[0]["event_id"]
    if counts["zero_owner"] or counts["multi_owner"] or counts["max_owner"] != 1:
        raise ValueError(
            "positive row must have exactly one event owner: "
            f"zero={counts['zero_owner']} multi={counts['multi_owner']} max={counts['max_owner']}"
        )
    return owners, counts
