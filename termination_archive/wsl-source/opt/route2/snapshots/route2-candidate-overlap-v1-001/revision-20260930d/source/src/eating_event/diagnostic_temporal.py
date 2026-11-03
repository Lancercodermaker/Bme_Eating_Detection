"""Production-isolated temporal features and fixed diagnostic estimators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


TEMPORAL_PROBE_FEATURE_COUNT = 72
_SUMMARY_SIGNALS = ("acc_mag", "gyro_mag", "acc_diff_mag", "gyro_diff_mag")
_BURST_SIGNALS = ("acc_diff_mag", "gyro_diff_mag")
_AUTOCORR_SIGNALS = ("acc_mag", "gyro_mag")
_SUMMARY_NAMES = ("mean", "std_population", "rms", "mean_abs_successive_difference")
_SLICE_NAMES = ("early", "middle", "late")
_TRANSITION_NAMES = ("early_minus_middle", "middle_minus_late", "early_minus_late")


@dataclass(frozen=True)
class TemporalFeatureVector:
    names: tuple[str, ...]
    values: np.ndarray


def _derived_signals(values: np.ndarray) -> dict[str, np.ndarray]:
    acc = values[:, :3]
    gyro = values[:, 3:6]
    acc_mag = np.linalg.norm(acc, axis=1)
    gyro_mag = np.linalg.norm(gyro, axis=1)
    acc_diff = np.linalg.norm(np.diff(acc, axis=0), axis=1)
    gyro_diff = np.linalg.norm(np.diff(gyro, axis=0), axis=1)
    if values.shape[0]:
        acc_diff = np.concatenate([[0.0], acc_diff])
        gyro_diff = np.concatenate([[0.0], gyro_diff])
    return {
        "acc_mag": acc_mag,
        "gyro_mag": gyro_mag,
        "acc_diff_mag": acc_diff,
        "gyro_diff_mag": gyro_diff,
    }


def _usable(signal: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    return valid_mask & np.isfinite(signal)


def _summary(signal: np.ndarray, mask: np.ndarray) -> tuple[float, float, float, float]:
    selected = signal[mask]
    if selected.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    differences = np.abs(np.diff(selected))
    return (
        float(np.mean(selected)),
        float(np.std(selected)),
        float(np.sqrt(np.mean(np.square(selected)))),
        float(np.mean(differences)) if differences.size else 0.0,
    )


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate(([False], mask, [False]))
    starts = np.flatnonzero(padded[1:] & ~padded[:-1])
    ends = np.flatnonzero(~padded[1:] & padded[:-1])
    return [(int(start), int(end)) for start, end in zip(starts, ends)]


def _burst_features(signal: np.ndarray, valid_mask: np.ndarray, grid_hz: int) -> tuple[float, float, float, float]:
    usable = _usable(signal, valid_mask)
    selected = signal[usable]
    if selected.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    threshold = float(np.median(selected) + 2.0 * np.std(selected))
    active = usable & (signal > threshold)
    qualifying = [(start, end) for start, end in _runs(active) if end - start >= 2]
    if not qualifying:
        longest = 0.0
    else:
        longest = max(end - start for start, end in qualifying) / float(grid_hz)
    peak_index = int(np.flatnonzero(usable)[np.argmax(signal[usable])])
    position = peak_index / float(max(1, signal.size - 1))
    return (
        float(sum(end - start for start, end in qualifying) / max(1, signal.size)),
        float(len(qualifying)),
        float(longest),
        float(position),
    )


def _autocorrelation(signal: np.ndarray, valid_mask: np.ndarray, lag: int) -> float:
    usable = _usable(signal, valid_mask)
    left_values: list[float] = []
    right_values: list[float] = []
    for start, end in _runs(usable):
        if end - start <= lag:
            continue
        left_values.extend(signal[start : end - lag].tolist())
        right_values.extend(signal[start + lag : end].tolist())
    if len(left_values) < 2:
        return 0.0
    left = np.asarray(left_values, dtype=np.float64)
    right = np.asarray(right_values, dtype=np.float64)
    center = float(np.mean(np.concatenate((left, right))))
    left -= center
    right -= center
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(left, right) / denominator)


def extract_temporal_probe_features(
    values: np.ndarray,
    valid_mask: np.ndarray | None = None,
    *,
    grid_hz: int = 10,
) -> TemporalFeatureVector:
    """Extract the preregistered bounded temporal probe vector from one window."""

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 6 or matrix.shape[0] < 3:
        raise ValueError("values must have shape [time>=3, 6]")
    if grid_hz <= 0:
        raise ValueError("grid_hz must be positive")
    if valid_mask is None:
        mask = np.ones(matrix.shape[0], dtype=bool)
    else:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.ndim != 1 or mask.size != matrix.shape[0]:
            raise ValueError("valid_mask must align with values")

    signals = _derived_signals(matrix)
    boundaries = np.linspace(0, matrix.shape[0], 4, dtype=int)
    names: list[str] = []
    output: list[float] = []

    for signal_name in _SUMMARY_SIGNALS:
        signal = signals[signal_name]
        for slice_name, start, end in zip(_SLICE_NAMES, boundaries[:-1], boundaries[1:]):
            slice_mask = mask[start:end] & np.isfinite(signal[start:end])
            summary = _summary(signal[start:end], slice_mask)
            for summary_name, value in zip(_SUMMARY_NAMES, summary):
                names.append(f"{signal_name}_{slice_name}_{summary_name}")
                output.append(value)

    for signal_name in _BURST_SIGNALS:
        signal = signals[signal_name]
        for feature_name, value in zip(
            ("burst_occupancy_fraction", "burst_count", "longest_burst_duration_seconds", "peak_temporal_position"),
            _burst_features(signal, mask, grid_hz),
        ):
            names.append(f"{signal_name}_{feature_name}")
            output.append(value)

    for signal_name in _AUTOCORR_SIGNALS:
        signal = signals[signal_name]
        for lag_seconds, lag_samples in ((1.0, grid_hz), (2.0, 2 * grid_hz)):
            names.append(f"{signal_name}_autocorrelation_lag_{lag_seconds:g}s")
            output.append(_autocorrelation(signal, mask, lag_samples))

    for signal_name in _SUMMARY_SIGNALS:
        signal = signals[signal_name]
        means = []
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            slice_mask = mask[start:end] & np.isfinite(signal[start:end])
            means.append(_summary(signal[start:end], slice_mask)[0])
        for transition_name, left, right in zip(_TRANSITION_NAMES, (0, 1, 0), (1, 2, 2)):
            names.append(f"{signal_name}_{transition_name}_mean")
            output.append(means[left] - means[right])

    result = np.asarray(output, dtype=np.float32)
    if len(names) != TEMPORAL_PROBE_FEATURE_COUNT or result.shape != (TEMPORAL_PROBE_FEATURE_COUNT,):
        raise AssertionError("temporal probe feature contract width changed")
    if not np.isfinite(result).all():
        raise ValueError("temporal probe features must be finite")
    return TemporalFeatureVector(tuple(names), result)


def extract_temporal_probe_matrix(
    values: np.ndarray,
    valid_mask: np.ndarray | None = None,
    *,
    grid_hz: int = 10,
) -> TemporalFeatureVector:
    """Vectorized equivalent of :func:`extract_temporal_probe_features` for one file."""

    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 3 or matrix.shape[2] != 6 or matrix.shape[1] < 3:
        raise ValueError("values must have shape [batch, time>=3, 6]")
    if grid_hz <= 0:
        raise ValueError("grid_hz must be positive")
    if valid_mask is None:
        mask = np.ones(matrix.shape[:2], dtype=bool)
    else:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape != matrix.shape[:2]:
            raise ValueError("valid_mask must align with values")

    batch, time_points = matrix.shape[:2]
    acc = matrix[:, :, :3]
    gyro = matrix[:, :, 3:6]
    signals = {
        "acc_mag": np.linalg.norm(acc, axis=2),
        "gyro_mag": np.linalg.norm(gyro, axis=2),
        "acc_diff_mag": np.concatenate(
            (np.zeros((batch, 1), dtype=np.float64), np.linalg.norm(np.diff(acc, axis=1), axis=2)),
            axis=1,
        ),
        "gyro_diff_mag": np.concatenate(
            (np.zeros((batch, 1), dtype=np.float64), np.linalg.norm(np.diff(gyro, axis=1), axis=2)),
            axis=1,
        ),
    }
    boundaries = np.linspace(0, time_points, 4, dtype=int)
    columns: list[np.ndarray] = []

    def slice_summary(signal: np.ndarray, start: int, end: int) -> tuple[np.ndarray, ...]:
        selected_signal = signal[:, start:end]
        usable = mask[:, start:end] & np.isfinite(selected_signal)
        count = usable.sum(axis=1).astype(np.float64)
        safe_count = np.maximum(count, 1.0)
        finite_values = np.where(usable, selected_signal, 0.0)
        mean = finite_values.sum(axis=1) / safe_count
        square_mean = np.square(finite_values).sum(axis=1) / safe_count
        std = np.sqrt(np.maximum(0.0, square_mean - np.square(mean)))
        rms = np.sqrt(square_mean)
        indices = np.broadcast_to(np.arange(end - start), selected_signal.shape)
        previous = np.maximum.accumulate(np.where(usable, indices, -1), axis=1)
        previous = np.concatenate((np.full((batch, 1), -1, dtype=np.int64), previous[:, :-1]), axis=1)
        safe_previous = np.clip(previous, 0, max(0, end - start - 1))
        previous_values = np.take_along_axis(selected_signal, safe_previous, axis=1)
        differences = np.where(
            usable & (previous >= 0),
            np.abs(selected_signal - previous_values),
            0.0,
        )
        mean_abs_difference = differences.sum(axis=1) / np.maximum(count - 1.0, 1.0)
        return mean, std, rms, mean_abs_difference

    summary_means: dict[str, list[np.ndarray]] = {}
    for signal_name in _SUMMARY_SIGNALS:
        signal = signals[signal_name]
        means: list[np.ndarray] = []
        for start, end in zip(boundaries[:-1], boundaries[1:]):
            summary = slice_summary(signal, int(start), int(end))
            means.append(summary[0])
            columns.extend(summary)
        summary_means[signal_name] = means

    for signal_name in _BURST_SIGNALS:
        signal = signals[signal_name]
        usable = mask & np.isfinite(signal)
        count = usable.sum(axis=1).astype(np.float64)
        safe_count = np.maximum(count, 1.0)
        selected = np.where(usable, signal, np.nan)
        medians = np.nanmedian(selected, axis=1)
        medians = np.where(count > 0, medians, 0.0)
        finite_values = np.where(usable, signal, 0.0)
        means = finite_values.sum(axis=1) / safe_count
        stds = np.sqrt(
            np.maximum(0.0, np.square(finite_values).sum(axis=1) / safe_count - np.square(means))
        )
        active = usable & (signal > (medians + 2.0 * stds)[:, None])
        previous_active = np.concatenate((np.zeros((batch, 1), dtype=bool), active[:, :-1]), axis=1)
        next_active = np.concatenate((active[:, 1:], np.zeros((batch, 1), dtype=bool)), axis=1)
        qualifying = active & (previous_active | next_active)
        run_lengths = np.zeros_like(active, dtype=np.int16)
        for index in range(time_points):
            if index == 0:
                run_lengths[:, index] = active[:, index]
            else:
                run_lengths[:, index] = np.where(active[:, index], run_lengths[:, index - 1] + 1, 0)
        starts = active & ~previous_active & next_active
        peak_values = np.where(usable, signal, -np.inf)
        peak_indices = np.argmax(peak_values, axis=1)
        peak_positions = np.where(count > 0, peak_indices / float(max(1, time_points - 1)), 0.0)
        columns.extend(
            [
                qualifying.sum(axis=1) / float(time_points),
                starts.sum(axis=1).astype(np.float64),
                run_lengths.max(axis=1) / float(grid_hz),
                peak_positions,
            ]
        )

    for signal_name in _AUTOCORR_SIGNALS:
        signal = signals[signal_name]
        usable = mask & np.isfinite(signal)
        for lag in (grid_hz, 2 * grid_hz):
            if time_points <= lag:
                columns.append(np.zeros(batch, dtype=np.float64))
                continue
            windows = np.lib.stride_tricks.sliding_window_view(usable, lag + 1, axis=1)
            pair_mask = windows.all(axis=-1)
            left = signal[:, :-lag]
            right = signal[:, lag:]
            pair_count = pair_mask.sum(axis=1).astype(np.float64)
            safe_pair_count = np.maximum(pair_count, 1.0)
            pair_sum = np.where(pair_mask, left, 0.0).sum(axis=1) + np.where(pair_mask, right, 0.0).sum(axis=1)
            center = pair_sum / (2.0 * safe_pair_count)
            left_centered = np.where(pair_mask, left - center[:, None], 0.0)
            right_centered = np.where(pair_mask, right - center[:, None], 0.0)
            numerator = (left_centered * right_centered).sum(axis=1)
            denominator = np.linalg.norm(left_centered, axis=1) * np.linalg.norm(right_centered, axis=1)
            correlation = np.zeros(batch, dtype=np.float64)
            valid_correlation = (pair_count >= 2) & (denominator != 0.0)
            np.divide(numerator, denominator, out=correlation, where=valid_correlation)
            columns.append(correlation)

    for signal_name in _SUMMARY_SIGNALS:
        means = summary_means[signal_name]
        columns.extend((means[0] - means[1], means[1] - means[2], means[0] - means[2]))

    result = np.column_stack(columns).astype(np.float32, copy=False)
    names = extract_temporal_probe_features(
        np.zeros((time_points, 6), dtype=np.float64),
        np.ones(time_points, dtype=bool),
        grid_hz=grid_hz,
    ).names
    if result.shape != (batch, TEMPORAL_PROBE_FEATURE_COUNT) or not np.isfinite(result).all():
        raise ValueError("temporal probe matrix contract must be finite with width 72")
    return TemporalFeatureVector(names, result)


def make_diagnostic_estimator(kind: str):
    """Return exactly one preregistered diagnostic estimator."""

    if kind == "L":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        C=1.0,
                        max_iter=300,
                        random_state=20260910,
                    ),
                ),
            ]
        )
    if kind == "N":
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_iter=100,
            max_leaf_nodes=7,
            min_samples_leaf=20,
            learning_rate=0.05,
            l2_regularization=1e-3,
            random_state=20260910,
        )
    raise ValueError("diagnostic estimator kind must be 'L' or 'N'")
