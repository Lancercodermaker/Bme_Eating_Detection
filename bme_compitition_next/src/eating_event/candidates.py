"""Candidate feature tables and a transparent tree-based candidate scorer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eating_event.data.labels import WindowLabel
from eating_event.data.timebase import RegularizedSeries
from eating_event.data.windows import WindowRecord
from eating_event.features import extract_imu_features


@dataclass(frozen=True)
class CandidateTable:
    features: np.ndarray
    feature_names: tuple[str, ...]
    labels: np.ndarray
    participant_ids: np.ndarray
    windows: tuple[WindowRecord, ...]


def eventize_windows(
    windows: list[WindowRecord] | tuple[WindowRecord, ...],
    scores: np.ndarray,
    *,
    threshold: float,
    min_duration_ms: int = 180_000,
    fuse_gap_ms: int = 600_000,
) -> list[tuple[int, int]]:
    """Merge selected dense windows into event intervals."""

    score_array = np.asarray(scores, dtype=np.float64)
    if score_array.ndim != 1 or score_array.size != len(windows):
        raise ValueError("scores must align with windows")
    if min_duration_ms <= 0 or fuse_gap_ms < 0:
        raise ValueError("min_duration_ms must be positive and fuse_gap_ms non-negative")
    selected = sorted(
        (record.window.start_ms, record.window.end_ms)
        for record, score in zip(windows, score_array)
        if score >= threshold
    )
    if not selected:
        return []

    merged: list[tuple[int, int]] = []
    current_start, current_end = selected[0]
    for start_ms, end_ms in selected[1:]:
        if start_ms <= current_end + fuse_gap_ms:
            current_end = max(current_end, end_ms)
        else:
            if current_end - current_start >= min_duration_ms:
                merged.append((current_start, current_end))
            current_start, current_end = start_ms, end_ms
    if current_end - current_start >= min_duration_ms:
        merged.append((current_start, current_end))
    return merged


def split_participants(
    participant_ids: list[str] | tuple[str, ...] | np.ndarray,
    *,
    valid_fraction: float = 0.2,
    seed: int = 20260910,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Create a deterministic participant-disjoint train/validation split."""

    if not 0 < valid_fraction < 1:
        raise ValueError("valid_fraction must be in (0, 1)")
    unique = sorted({str(participant) for participant in participant_ids})
    if len(unique) < 2:
        raise ValueError("at least two participants are required")
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(unique))
    valid_count = max(1, int(round(len(unique) * valid_fraction)))
    valid_count = min(valid_count, len(unique) - 1)
    valid = tuple(sorted(unique[index] for index in order[:valid_count]))
    valid_set = set(valid)
    train = tuple(participant for participant in unique if participant not in valid_set)
    return train, valid


def build_candidate_table(
    series: RegularizedSeries,
    windows: list[WindowRecord],
    *,
    participant_id: str,
) -> CandidateTable:
    feature_rows: list[np.ndarray] = []
    labels: list[int] = []
    participant_ids: list[str] = []
    feature_names: tuple[str, ...] | None = None
    for record in windows:
        start_index = int(np.searchsorted(series.timestamps_ms, record.window.start_ms, side="left"))
        end_index = int(np.searchsorted(series.timestamps_ms, record.window.end_ms, side="left"))
        if end_index <= start_index:
            raise ValueError("candidate window does not overlap the regularized series")
        vector = extract_imu_features(series.values[start_index:end_index], series.valid_mask[start_index:end_index])
        if feature_names is None:
            feature_names = vector.names
        elif vector.names != feature_names:
            raise ValueError("feature schema changed between candidate windows")
        feature_rows.append(vector.values)
        labels.append(
            1 if record.label is WindowLabel.POSITIVE else 0 if record.label is WindowLabel.NEGATIVE else -1
        )
        participant_ids.append(participant_id)
    if feature_names is None:
        feature_names = tuple()
    feature_width = len(feature_names)
    features = np.vstack(feature_rows) if feature_rows else np.empty((0, feature_width), dtype=np.float64)
    return CandidateTable(
        features=features,
        feature_names=feature_names,
        labels=np.asarray(labels, dtype=np.int8),
        participant_ids=np.asarray(participant_ids, dtype=object),
        windows=tuple(windows),
    )


class CandidateModel:
    def __init__(self, estimator: object) -> None:
        self.estimator = estimator

    def predict_scores(self, features: np.ndarray) -> np.ndarray:
        return np.asarray(self.estimator.predict_proba(features)[:, 1], dtype=np.float64)


def fit_candidate_model(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    random_state: int = 20260910,
    positive_weight: float = 3.0,
) -> CandidateModel:
    """Fit a deterministic high-recall candidate classifier on 0/1 rows."""

    from sklearn.ensemble import HistGradientBoostingClassifier

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.int8)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size:
        raise ValueError("features and labels must have aligned shapes")
    keep = y >= 0
    if keep.sum() == 0 or np.unique(y[keep]).size != 2:
        raise ValueError("candidate training needs both positive and negative labels")
    weights = np.ones(int(keep.sum()), dtype=np.float64)
    weights[y[keep] == 1] = positive_weight
    estimator = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=300,
        min_samples_leaf=1,
        max_leaf_nodes=31,
        l2_regularization=1e-3,
        random_state=random_state,
    )
    estimator.fit(x[keep], y[keep], sample_weight=weights)
    return CandidateModel(estimator)
