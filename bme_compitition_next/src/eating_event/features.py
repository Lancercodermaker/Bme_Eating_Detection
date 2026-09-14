"""Fixed-shape IMU features for the high-recall candidate layer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


FEATURE_SCHEMA_VERSION = "imu_stats_v1"
IMU_FEATURE_WIDTH = 111


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: np.ndarray


_BASE_NAMES = ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")
_STAT_NAMES = (
    "mean",
    "std",
    "abs_mean",
    "rms",
    "min",
    "max",
    "range",
    "p10",
    "p50",
    "p90",
    "mean_abs_diff",
)


def _derived_signals(values: np.ndarray) -> tuple[tuple[str, np.ndarray], ...]:
    acc = values[:, :3]
    gyro = values[:, 3:6]
    acc_mag = np.linalg.norm(acc, axis=1)
    gyro_mag = np.linalg.norm(gyro, axis=1)
    acc_diff = np.linalg.norm(np.diff(acc, axis=0), axis=1)
    gyro_diff = np.linalg.norm(np.diff(gyro, axis=0), axis=1)
    if values.shape[0]:
        acc_diff = np.concatenate([[0.0], acc_diff])
        gyro_diff = np.concatenate([[0.0], gyro_diff])
    return (
        *((name, values[:, index]) for index, name in enumerate(_BASE_NAMES)),
        ("acc_mag", acc_mag),
        ("gyro_mag", gyro_mag),
        ("acc_diff_mag", acc_diff),
        ("gyro_diff_mag", gyro_diff),
    )


def extract_imu_features(values: np.ndarray, valid_mask: np.ndarray | None = None) -> FeatureVector:
    """Extract deterministic robust statistics from a regularized IMU window."""

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 6:
        raise ValueError("values must have shape [time, 6] for ACC xyz and GYRO xyz")
    if valid_mask is None:
        mask = np.ones(matrix.shape[0], dtype=bool)
    else:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.ndim != 1 or mask.size != matrix.shape[0]:
            raise ValueError("valid_mask must align with values")
    feature_names: list[str] = ["valid_fraction"]
    feature_values: list[float] = [float(mask.mean()) if mask.size else 0.0]

    for signal_name, signal in _derived_signals(matrix):
        finite_signal = signal[mask & np.isfinite(signal)]
        if finite_signal.size == 0:
            stats = np.zeros(len(_STAT_NAMES), dtype=np.float64)
        else:
            diffs = np.abs(np.diff(finite_signal))
            stats = np.array(
                [
                    np.mean(finite_signal),
                    np.std(finite_signal),
                    np.mean(np.abs(finite_signal)),
                    np.sqrt(np.mean(np.square(finite_signal))),
                    np.min(finite_signal),
                    np.max(finite_signal),
                    np.ptp(finite_signal),
                    np.percentile(finite_signal, 10),
                    np.percentile(finite_signal, 50),
                    np.percentile(finite_signal, 90),
                    np.mean(diffs) if diffs.size else 0.0,
                ],
                dtype=np.float64,
            )
        feature_names.extend(f"{signal_name}_{stat_name}" for stat_name in _STAT_NAMES)
        feature_values.extend(stats.tolist())

    values = np.asarray(feature_values, dtype=np.float32)
    if values.shape != (IMU_FEATURE_WIDTH,) or not np.isfinite(values).all():
        raise ValueError("IMU feature contract must produce 111 finite values")
    return FeatureVector(tuple(feature_names), values)

