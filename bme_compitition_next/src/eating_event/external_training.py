"""Training-only window tables and deterministic sampling for external FD data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

import numpy as np

from eating_event.external import iter_fd_sequences, windowize_external_sequence


@dataclass(frozen=True)
class ExternalWindowTable:
    dataset: str
    participant_id: str
    wrist: str
    features: np.ndarray
    labels: np.ndarray


def _evenly_spaced(indices: np.ndarray, count: int) -> np.ndarray:
    if count <= 0 or indices.size == 0:
        return np.empty(0, dtype=np.int64)
    if count >= indices.size:
        return indices.astype(np.int64, copy=False)
    positions = np.linspace(0, indices.size - 1, count, dtype=np.int64)
    return indices[positions].astype(np.int64, copy=False)


def select_external_window_indices(labels: np.ndarray, *, max_windows: int | None) -> np.ndarray:
    """Select a deterministic, temporally ordered, approximately balanced subset."""

    values = np.asarray(labels, dtype=np.int8).reshape(-1)
    if max_windows is not None and max_windows <= 0:
        raise ValueError("max_windows must be positive when provided")
    all_indices = np.arange(values.size, dtype=np.int64)
    if max_windows is None or max_windows >= values.size:
        return all_indices

    positive = np.flatnonzero(values == 1)
    negative = np.flatnonzero(values == 0)
    positive_count = min(positive.size, max_windows // 2)
    negative_count = min(negative.size, max_windows - positive_count)
    remaining = max_windows - positive_count - negative_count
    if remaining:
        positive_count += min(positive.size - positive_count, remaining)
        remaining = max_windows - positive_count - negative_count
    if remaining:
        negative_count += min(negative.size - negative_count, remaining)
    selected = np.concatenate(
        (
            _evenly_spaced(positive, positive_count),
            _evenly_spaced(negative, negative_count),
        )
    )
    return np.sort(selected.astype(np.int64, copy=False))


def collect_external_window_tables(
    root: Path,
    *,
    dataset: str,
    participant_indices: Sequence[int] | None,
    wrist: str = "both",
    window_seconds: float = 15.0,
    step_seconds: float = 7.5,
    feature_hz: float = 10.0,
    max_windows_per_sequence: int | None = None,
) -> tuple[ExternalWindowTable, ...]:
    """Build feature tables for training; never used by submission inference."""

    tables: list[ExternalWindowTable] = []
    for sequence in iter_fd_sequences(
        root,
        dataset=dataset,
        participant_indices=participant_indices,
        wrist=wrist,
    ):
        features, labels = windowize_external_sequence(
            sequence,
            window_seconds=window_seconds,
            step_seconds=step_seconds,
            feature_hz=feature_hz,
        )
        selected = select_external_window_indices(labels, max_windows=max_windows_per_sequence)
        tables.append(
            ExternalWindowTable(
                dataset=sequence.dataset,
                participant_id=sequence.participant_id,
                wrist=sequence.wrist,
                features=features[selected],
                labels=labels[selected],
            )
        )
    return tuple(tables)
