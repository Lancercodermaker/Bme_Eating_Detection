"""Adapters for the external FD-I/FD-II point-labelled IMU datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle
from collections.abc import Iterator, Sequence

import numpy as np

from eating_event.features import extract_imu_features


@dataclass(frozen=True)
class ExternalSequence:
    dataset: str
    participant_id: str
    wrist: str
    values: np.ndarray
    labels: np.ndarray
    sampling_hz: float

    def __post_init__(self) -> None:
        values = np.asarray(self.values)
        labels = np.asarray(self.labels).reshape(-1)
        if values.ndim != 2 or values.shape[1] != 6:
            raise ValueError("external values must have shape [samples, 6]")
        if labels.ndim != 1 or labels.size != values.shape[0]:
            raise ValueError("external labels must align with values")
        if self.wrist not in {"left", "right"}:
            raise ValueError("wrist must be left or right")
        if self.sampling_hz <= 0:
            raise ValueError("sampling_hz must be positive")


def _read_pickle(path: Path) -> object:
    try:
        with path.open("rb") as handle:
            return pickle.load(handle)
    except (OSError, pickle.PickleError, EOFError) as exc:
        raise ValueError(f"cannot read external pickle: {path}") from exc


def _normalise_labels(values: object, *, path: Path) -> np.ndarray:
    labels = np.asarray(values).reshape(-1)
    if labels.size == 0:
        raise ValueError(f"external label sequence is empty: {path}")
    if not np.all(np.isfinite(labels)) or not np.allclose(labels, np.rint(labels)):
        raise ValueError(f"external labels must be finite integers: {path}")
    labels = np.rint(labels).astype(np.int8, copy=False)
    if not set(np.unique(labels).tolist()).issubset({0, 1, 2}):
        raise ValueError(f"external labels must be in {{0, 1, 2}}: {path}")
    return labels


def iter_fd_sequences(
    root: Path,
    *,
    dataset: str,
    participant_indices: Sequence[int] | None = None,
    wrist: str = "both",
) -> Iterator[ExternalSequence]:
    """Yield FD wrist sequences without retaining both wrists in memory.

    FD labels are point-wise: 1=eating, 2=drinking, 0=other.  This adapter
    keeps that distinction explicit; window conversion is handled separately.
    """

    if dataset not in {"FD-I", "FD-II"}:
        raise ValueError("dataset must be FD-I or FD-II")
    if wrist not in {"left", "right", "both"}:
        raise ValueError("wrist must be left, right, or both")
    dataset_root = Path(root) / dataset
    selected_wrist_names = ("left", "right") if wrist == "both" else (wrist,)
    for wrist_name in selected_wrist_names:
        values_payload = _read_pickle(dataset_root / f"X_{wrist_name[0].upper()}.pkl")
        labels_payload = _read_pickle(dataset_root / f"Y_{wrist_name[0].upper()}.pkl")
        if not isinstance(values_payload, (list, tuple)) or not isinstance(labels_payload, (list, tuple)):
            raise ValueError("FD pickle payloads must be lists or tuples")
        if len(values_payload) != len(labels_payload):
            raise ValueError("FD value and label participant counts differ")
        indices = range(len(values_payload)) if participant_indices is None else participant_indices
        for index in indices:
            if index < 0 or index >= len(values_payload):
                raise IndexError(f"external participant index out of range: {index}")
            values = np.asarray(values_payload[index], dtype=np.float32)
            labels = _normalise_labels(labels_payload[index], path=dataset_root / f"Y_{wrist_name[0].upper()}.pkl")
            if values.ndim != 2 or values.shape[1] != 6 or values.shape[0] != labels.size:
                raise ValueError(f"FD values and labels do not align for participant {index}")
            yield ExternalSequence(
                dataset=dataset,
                participant_id=f"{dataset}-{index:03d}",
                wrist=wrist_name,
                values=values,
                labels=labels,
                sampling_hz=64.0,
            )
        del values_payload, labels_payload


def windowize_external_sequence(
    sequence: ExternalSequence,
    *,
    window_seconds: float,
    step_seconds: float,
    feature_hz: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Map point-wise FD labels to binary eating-window labels and features.

    FD signals are sampled at 64 Hz while the target pipeline extracts its
    window statistics on a 10 Hz regularized grid.  Resampling each external
    window before feature extraction keeps difference-based features in the
    same approximate scale as target features.
    """

    if window_seconds <= 0 or step_seconds <= 0 or step_seconds > window_seconds:
        raise ValueError("window_seconds and step_seconds must be positive with step <= window")
    if feature_hz <= 0:
        raise ValueError("feature_hz must be positive")
    window_points = int(round(window_seconds * sequence.sampling_hz))
    step_points = int(round(step_seconds * sequence.sampling_hz))
    feature_points = int(round(window_seconds * feature_hz))
    if window_points <= 0 or step_points <= 0 or feature_points <= 0 or sequence.values.shape[0] < window_points:
        return np.empty((0, 111), dtype=np.float64), np.empty((0,), dtype=np.int8)

    source_times = np.arange(window_points, dtype=np.float64) / sequence.sampling_hz
    target_times = np.arange(feature_points, dtype=np.float64) / feature_hz
    features: list[np.ndarray] = []
    labels: list[int] = []
    for start in range(0, sequence.values.shape[0] - window_points + 1, step_points):
        end = start + window_points
        source_values = sequence.values[start:end]
        resampled = np.full((feature_points, source_values.shape[1]), np.nan, dtype=np.float64)
        for channel in range(source_values.shape[1]):
            finite = np.isfinite(source_values[:, channel])
            if finite.any():
                resampled[:, channel] = np.interp(
                    target_times,
                    source_times[finite],
                    source_values[finite, channel],
                )
        features.append(extract_imu_features(resampled).values)
        labels.append(int(np.any(sequence.labels[start:end] == 1)))
    return np.vstack(features), np.asarray(labels, dtype=np.int8)
