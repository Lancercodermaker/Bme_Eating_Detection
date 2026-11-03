"""Explicit scikit-learn scoring and fit provenance primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


@dataclass(frozen=True)
class ReferenceThreshold:
    threshold: float
    q: float
    row_hash: str
    row_count: int


def compute_reference_threshold(
    scores: Sequence[float] | np.ndarray,
    labels: Sequence[int] | np.ndarray,
    q: float,
    *,
    row_ids: Sequence[str] | None = None,
) -> ReferenceThreshold:
    values = np.asarray(scores, dtype=np.float64)
    label_values = np.asarray(labels, dtype=np.int8)
    if values.ndim != 1 or label_values.ndim != 1 or values.size != label_values.size:
        raise ValueError("reference scores and labels must align")
    if values.size == 0:
        raise ValueError("reference cannot be empty")
    if not np.isfinite(values).all():
        raise ValueError("reference scores must be finite")
    if not 0 < q < 1:
        raise ValueError("reference q must be in (0, 1)")
    if row_ids is None:
        canonical_ids = [str(index) for index in range(values.size)]
    else:
        if len(row_ids) != values.size or len(set(row_ids)) != values.size:
            raise ValueError("reference row IDs must align and be unique")
        canonical_ids = [str(value) for value in row_ids]
    row_hash = hashlib.sha256(
        json.dumps(sorted(canonical_ids), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return ReferenceThreshold(
        threshold=float(np.quantile(values, q, method="linear")),
        q=float(q),
        row_hash=row_hash,
        row_count=int(values.size),
    )


def _hgb_kwargs(*, verifier: bool, random_state: int, max_iter: int, positive_weight: float) -> dict[str, object]:
    return {
        "learning_rate": 0.05,
        "max_iter": max_iter,
        "max_leaf_nodes": 15 if verifier else 31,
        "max_depth": None,
        "min_samples_leaf": 1,
        "l2_regularization": 1e-3,
        "max_features": 1.0,
        "max_bins": 255,
        "categorical_features": None,
        "monotonic_cst": None,
        "interaction_cst": None,
        "warm_start": False,
        "early_stopping": False,
        "scoring": "loss",
        "validation_fraction": None,
        "n_iter_no_change": 10,
        "tol": 1e-7,
        "verbose": 0,
        "random_state": random_state,
        "class_weight": None,
    }


def _fit_hgb(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    verifier: bool,
    random_state: int,
    positive_weight: float,
    max_iter: int,
) -> HistGradientBoostingClassifier:
    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(labels, dtype=np.int8)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size:
        raise ValueError("fit features and labels must align")
    keep = y >= 0
    if keep.sum() == 0 or set(y[keep].tolist()) != {0, 1}:
        raise ValueError("fit requires both binary labels")
    if max_iter <= 0 or positive_weight <= 0:
        raise ValueError("fit parameters must be positive")
    weights = np.ones(int(keep.sum()), dtype=np.float64)
    weights[y[keep] == 1] = positive_weight
    estimator = HistGradientBoostingClassifier(**_hgb_kwargs(
        verifier=verifier,
        random_state=random_state,
        max_iter=max_iter,
        positive_weight=positive_weight,
    ))
    estimator.fit(x[keep], y[keep], sample_weight=weights)
    return estimator


def fit_candidate_estimator(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    positive_weight: float = 3.0,
    random_state: int = 20260910,
    max_iter: int = 100,
) -> HistGradientBoostingClassifier:
    return _fit_hgb(
        features,
        labels,
        verifier=False,
        random_state=random_state,
        positive_weight=positive_weight,
        max_iter=max_iter,
    )


def validate_g3(labels: Sequence[int], participant_ids: Sequence[str]) -> None:
    values = np.asarray(labels, dtype=np.int8)
    participants = tuple(map(str, participant_ids))
    if values.ndim != 1 or values.size != len(participants):
        raise ValueError("G3 labels and participant IDs must align")
    positives = values == 1
    if int(positives.sum()) < 20:
        raise ValueError("G3 requires at least 20 positive candidates")
    if len({participants[index] for index in np.flatnonzero(positives)}) < 5:
        raise ValueError("G3 requires positive candidates from at least 5 participants")
    if set(values.tolist()) != {0, 1}:
        raise ValueError("G3 requires both positive and negative candidates")


def fit_verifier_estimator(
    features: np.ndarray,
    labels: np.ndarray,
    participant_ids: Sequence[str],
    *,
    positive_weight: float = 3.0,
    random_state: int = 20260910,
    max_iter: int = 100,
) -> HistGradientBoostingClassifier:
    try:
        validate_g3(labels, participant_ids)
    except ValueError as exc:
        raise ValueError(f"G3: {exc}") from exc
    return _fit_hgb(
        features,
        labels,
        verifier=True,
        random_state=random_state,
        positive_weight=positive_weight,
        max_iter=max_iter,
    )


def predict_scores(estimator: object, features: np.ndarray) -> np.ndarray:
    values = np.asarray(estimator.predict_proba(np.asarray(features, dtype=np.float32))[:, 1], dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("estimator returned invalid scores")
    return values
