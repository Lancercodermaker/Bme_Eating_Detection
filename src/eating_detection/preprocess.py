from dataclasses import dataclass
from fractions import Fraction

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class Standardizer:
    mean: np.ndarray
    std: np.ndarray


def resample_uniform(
    values: np.ndarray, source_hz: float, target_hz: int
) -> np.ndarray:
    if source_hz <= 0 or target_hz <= 0:
        raise ValueError("source_hz and target_hz must be positive")
    array = np.asarray(values, dtype=np.float32)
    ratio = Fraction(float(target_hz) / float(source_hz)).limit_denominator(1000)
    return signal.resample_poly(
        array, ratio.numerator, ratio.denominator, axis=0
    ).astype(np.float32)


def _column_valid_mask(valid: np.ndarray, channels: int) -> np.ndarray:
    mask = np.asarray(valid, dtype=bool)
    if mask.ndim == 1:
        return np.broadcast_to(mask[:, None], (len(mask), channels))
    if mask.ndim != 2:
        raise ValueError("valid mask must be one- or two-dimensional")
    if mask.shape[1] == channels:
        return mask
    if mask.shape[1] == 2 and channels == 8:
        return np.column_stack(
            [mask[:, 0]] * 4 + [mask[:, 1]] * 4
        )
    raise ValueError("valid mask channel count does not match values")


def fit_standardizer(values: np.ndarray, valid: np.ndarray) -> Standardizer:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("values must have shape (rows, channels)")
    mask = _column_valid_mask(valid, array.shape[1])
    mean = np.zeros(array.shape[1], dtype=np.float32)
    std = np.ones(array.shape[1], dtype=np.float32)
    for column in range(array.shape[1]):
        selected = array[mask[:, column], column]
        if len(selected) == 0:
            raise ValueError(f"channel {column} has no valid training samples")
        mean[column] = selected.mean()
        std[column] = max(float(selected.std()), 1e-6)
    return Standardizer(mean=mean, std=std)


def imu_features(
    acc: np.ndarray,
    gyro: np.ndarray,
    acc_valid: np.ndarray,
    gyro_valid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    acc_array = np.asarray(acc, dtype=np.float32)
    gyro_array = np.asarray(gyro, dtype=np.float32)
    if acc_array.shape != gyro_array.shape or acc_array.ndim != 2 or acc_array.shape[1] != 3:
        raise ValueError("acc and gyro must both have shape (rows, 3)")
    features = np.column_stack(
        [
            acc_array,
            gyro_array,
            np.linalg.norm(acc_array, axis=1),
            np.linalg.norm(gyro_array, axis=1),
        ]
    )
    mask = np.column_stack([acc_valid, gyro_valid]).astype(bool)
    return features.astype(np.float32), mask


def apply_standardizer(values: np.ndarray, stats: Standardizer) -> np.ndarray:
    return ((np.asarray(values, dtype=np.float32) - stats.mean) / stats.std).astype(
        np.float32
    )


def lowpass_sos(values: np.ndarray, cutoff_hz: float, sample_hz: int) -> np.ndarray:
    if cutoff_hz <= 0 or cutoff_hz >= sample_hz / 2:
        raise ValueError("cutoff_hz must be between zero and the Nyquist frequency")
    array = np.asarray(values, dtype=np.float32)
    if len(array) < 32:
        raise ValueError("signal is too short for the configured zero-phase filter")
    sos = signal.butter(4, cutoff_hz, btype="lowpass", fs=sample_hz, output="sos")
    return signal.sosfiltfilt(sos, array, axis=0).astype(np.float32)
