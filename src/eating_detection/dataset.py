from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset, Sampler

from .cache import LazyFeatureCache
from .io import iter_sensor_chunks
from .labels import label_window
from .preprocess import apply_feature_variant, imu_features, resample_uniform
from .timebase import canonicalize_stream, infer_rate_hz, interpolate_uniform


@dataclass(frozen=True)
class WindowRecord:
    participant: str
    start_ms: int
    end_ms: int
    features: torch.Tensor
    label: float
    loss_mask: bool = True


@dataclass(frozen=True)
class CachedBatch:
    features: torch.Tensor
    labels: torch.Tensor
    participants: tuple[str, ...]


def make_window_records(
    participant: str,
    start_ms: int,
    sample_hz: float,
    features: torch.Tensor,
    intervals: list[tuple[int, int]],
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
) -> list[WindowRecord]:
    if sample_hz <= 0 or window_sec <= 0 or step_sec <= 0:
        raise ValueError("sample_hz, window_sec, and step_sec must be positive")
    if step_sec > window_sec:
        raise ValueError("step_sec must not exceed window_sec")
    if features.ndim != 2:
        raise ValueError("features must have shape (channels, time)")
    window_samples = max(1, int(round(window_sec * sample_hz)))
    step_samples = max(1, int(round(step_sec * sample_hz)))
    records = []
    for offset in range(0, features.shape[1] - window_samples + 1, step_samples):
        window_start = int(round(start_ms + offset * 1000.0 / sample_hz))
        window_end = int(round(window_start + window_samples * 1000.0 / sample_hz))
        label = label_window(
            (window_start, window_end), intervals, positive_overlap, boundary_mode
        )
        records.append(
            WindowRecord(
                participant=participant,
                start_ms=window_start,
                end_ms=window_end,
                features=features[:, offset : offset + window_samples].clone(),
                label=0.0 if label is None else float(label),
                loss_mask=label is not None,
            )
        )
    return records


def participant_from_sensor_path(path: Path) -> str:
    parts = list(Path(path).parts)
    lowered = [part.casefold() for part in parts]
    if "organized" in lowered:
        index = lowered.index("organized")
        if index + 1 < len(parts):
            return parts[index + 1].replace(" ", "").casefold()
    return Path(path).parent.name.replace(" ", "").casefold()


def _read_sensor_file(
    path: Path, max_rows: int | None, chunksize: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    timestamps = []
    acc = []
    gyro = []
    acc_valid = []
    gyro_valid = []
    for chunk in iter_sensor_chunks(path, chunksize=chunksize, include_ppg=False):
        take = len(chunk.acc) if max_rows is None else min(len(chunk.acc), max_rows - sum(map(len, acc)))
        if take <= 0:
            break
        timestamps.append(chunk.timestamp_ms[:take])
        acc.append(chunk.acc[:take])
        gyro.append(chunk.gyro[:take])
        acc_valid.append(chunk.acc_valid[:take])
        gyro_valid.append(chunk.gyro_valid[:take])
        if max_rows is not None and sum(map(len, acc)) >= max_rows:
            break
    if not acc:
        raise ValueError("sensor file has no rows in the requested limit")
    timestamp_array = np.concatenate(timestamps, axis=0)
    return (
        timestamp_array[:, 0],
        timestamp_array[:, 1],
        timestamp_array[:, 2],
        np.concatenate(acc, axis=0),
        np.concatenate(gyro, axis=0),
        np.concatenate(acc_valid, axis=0),
        np.concatenate(gyro_valid, axis=0),
    )


def build_records_from_sensor_file(
    path: Path,
    intervals: list[tuple[int, int]],
    resample_hz: int,
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
    max_rows: int | None = None,
    chunksize: int = 50_000,
    max_gap_ms: int = 2_000,
    preprocess_variant: str = "p0_raw_mask",
    lowpass_cutoff_hz: float = 1.0,
    median_kernel: int = 5,
) -> list[WindowRecord]:
    acc_time, _, gyro_time, acc, gyro, _, _ = _read_sensor_file(
        path, max_rows=max_rows, chunksize=chunksize
    )
    acc_stream = canonicalize_stream(acc_time, acc)
    gyro_stream = canonicalize_stream(gyro_time, gyro)
    acc_hz = infer_rate_hz(acc_stream.timestamps_ms)
    gyro_hz = infer_rate_hz(gyro_stream.timestamps_ms)
    source_hz = max(acc_hz, gyro_hz)
    start_ms = max(acc_stream.timestamps_ms[0], gyro_stream.timestamps_ms[0])
    end_ms = min(acc_stream.timestamps_ms[-1], gyro_stream.timestamps_ms[-1])
    if end_ms <= start_ms:
        raise ValueError("ACC and GYRO streams have no overlapping time range")

    grid, acc_uniform, acc_mask = interpolate_uniform(
        acc_stream, source_hz, start_ms, end_ms, max_gap_ms
    )
    gyro_grid, gyro_uniform, gyro_mask = interpolate_uniform(
        gyro_stream, source_hz, start_ms, end_ms, max_gap_ms
    )
    if not np.array_equal(grid, gyro_grid):
        raise ValueError("aligned streams produced different time grids")
    features, mask = imu_features(acc_uniform, gyro_uniform, acc_mask, gyro_mask)
    resampled_features = resample_uniform(features, source_hz, resample_hz)
    resampled_features = apply_feature_variant(
        resampled_features,
        sample_hz=resample_hz,
        name=preprocess_variant,
        lowpass_cutoff_hz=lowpass_cutoff_hz,
        median_kernel=median_kernel,
    )
    resampled_mask = resample_uniform(mask.astype(np.float32), source_hz, resample_hz) > 0.5
    length = min(len(resampled_features), len(resampled_mask))
    feature_tensor = torch.from_numpy(
        np.vstack(
            [resampled_features[:length].T, resampled_mask[:length].astype(np.float32).T]
        ).astype(np.float32)
    )
    return make_window_records(
        participant=participant_from_sensor_path(path),
        start_ms=int(start_ms),
        sample_hz=resample_hz,
        features=feature_tensor,
        intervals=intervals,
        window_sec=window_sec,
        step_sec=step_sec,
        positive_overlap=positive_overlap,
        boundary_mode=boundary_mode,
    )


def build_records_from_sensor_files(
    paths: list[Path],
    meal_intervals: dict[str, list[tuple[int, int]]],
    resample_hz: int,
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
    max_rows: int | None = None,
    chunksize: int = 50_000,
    preprocess_variant: str = "p0_raw_mask",
    lowpass_cutoff_hz: float = 1.0,
    median_kernel: int = 5,
) -> tuple[list[WindowRecord], list[dict[str, str]]]:
    records: list[WindowRecord] = []
    issues: list[dict[str, str]] = []
    for path in paths:
        participant = participant_from_sensor_path(path)
        try:
            records.extend(
                build_records_from_sensor_file(
                    path,
                    intervals=meal_intervals.get(participant, []),
                    resample_hz=resample_hz,
                    window_sec=window_sec,
                    step_sec=step_sec,
                    positive_overlap=positive_overlap,
                    boundary_mode=boundary_mode,
                    max_rows=max_rows,
                    chunksize=chunksize,
                    preprocess_variant=preprocess_variant,
                    lowpass_cutoff_hz=lowpass_cutoff_hz,
                    median_kernel=median_kernel,
                )
            )
        except (OSError, ValueError) as exc:
            issues.append({"path": str(path), "reason": str(exc)})
    return records, issues


class WindowDataset(Dataset):
    def __init__(self, records):
        self.records = list(records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        return (
            record.features,
            torch.tensor(record.label, dtype=torch.float32),
            record.participant,
        )

    def participant_for_index(self, index: int) -> str:
        return self.records[index].participant


class CachedWindowDataset(Dataset):
    """Index-backed windows over per-file continuous feature arrays."""

    def __init__(
        self,
        caches,
        participants: set[str] | None = None,
        include_ignored: bool = False,
        min_quality_fraction: float = 0.0,
    ):
        if not 0.0 <= min_quality_fraction <= 1.0:
            raise ValueError("min_quality_fraction must be in [0, 1]")
        self.caches = list(caches)
        self._active_cache_index: int | None = None
        allowed = participants
        self._references = []
        for cache_index, cache in enumerate(self.caches):
            if allowed is not None and cache.participant not in allowed:
                continue
            if min_quality_fraction > 0.0:
                if isinstance(cache, LazyFeatureCache):
                    cache.ensure_quality_mask()
                quality_mask = cache.quality_mask
                indices = np.asarray(cache.window_indices, dtype=np.int64)
                prefix = np.concatenate(
                    [
                        np.zeros((quality_mask.shape[0], 1), dtype=np.int64),
                        np.cumsum(quality_mask, axis=1, dtype=np.int64),
                    ],
                    axis=1,
                )
                quality_counts = (
                    prefix[:, indices[:, 1]] - prefix[:, indices[:, 0]]
                ).sum(axis=0)
                durations = np.maximum(indices[:, 1] - indices[:, 0], 1)
                quality_fractions = quality_counts / (quality_mask.shape[0] * durations)
                quality_usable = quality_fractions >= min_quality_fraction
                if isinstance(cache, LazyFeatureCache):
                    cache.release_features()
            else:
                quality_usable = np.ones(len(cache.window_loss_mask), dtype=bool)
            for window_index, usable in enumerate(cache.window_loss_mask):
                if (include_ignored or bool(usable)) and quality_usable[window_index]:
                    self._references.append((cache_index, window_index))

    def __len__(self):
        return len(self._references)

    def participant_for_index(self, index: int) -> str:
        cache_index, _ = self._references[index]
        return self.caches[cache_index].participant

    def label_for_index(self, index: int) -> float:
        cache_index, window_index = self._references[index]
        return float(self.caches[cache_index].window_labels[window_index])

    def batch_group_for_index(self, index: int):
        cache_index, _ = self._references[index]
        return self.caches[cache_index].participant, cache_index

    def window_metadata(self, index: int) -> tuple[str, int, int]:
        cache_index, window_index = self._references[index]
        cache = self.caches[cache_index]
        return (
            cache.participant,
            int(cache.window_starts_ms[window_index]),
            int(cache.window_ends_ms[window_index]),
        )

    def _activate_cache(self, cache_index: int):
        if self._active_cache_index == cache_index:
            return
        if self._active_cache_index is not None:
            previous = self.caches[self._active_cache_index]
            if isinstance(previous, LazyFeatureCache):
                previous.release_features()
        cache = self.caches[cache_index]
        if isinstance(cache, LazyFeatureCache):
            cache.ensure_features()
        self._active_cache_index = cache_index

    def release_loaded(self) -> None:
        if self._active_cache_index is not None:
            cache = self.caches[self._active_cache_index]
            if isinstance(cache, LazyFeatureCache):
                cache.release_features()
            self._active_cache_index = None

    def __getitem__(self, index):
        cache_index, window_index = self._references[index]
        self._activate_cache(cache_index)
        cache = self.caches[cache_index]
        start, end = cache.window_indices[window_index]
        features = torch.from_numpy(cache.features[:, int(start):int(end)])
        label = torch.tensor(cache.window_labels[window_index], dtype=torch.float32)
        return features, label, cache.participant

    def __getitems__(self, indices):
        indices = [int(index) for index in indices]
        if not indices:
            raise IndexError("cannot fetch an empty batch")
        references = [self._references[index] for index in indices]
        cache_indices = {cache_index for cache_index, _ in references}
        if len(cache_indices) != 1:
            return [self[index] for index in indices]
        cache_index = references[0][0]
        self._activate_cache(cache_index)
        cache = self.caches[cache_index]
        window_indices = np.asarray([window_index for _, window_index in references])
        starts = cache.window_indices[window_indices, 0].astype(np.int64, copy=False)
        ends = cache.window_indices[window_indices, 1].astype(np.int64, copy=False)
        lengths = ends - starts
        if np.any(lengths != lengths[0]):
            return [self[index] for index in indices]
        offsets = starts[:, None] + np.arange(int(lengths[0]), dtype=np.int64)[None, :]
        features = np.ascontiguousarray(cache.features[:, offsets].transpose(1, 0, 2))
        labels = np.asarray(cache.window_labels[window_indices], dtype=np.float32)
        return CachedBatch(
            features=torch.from_numpy(features),
            labels=torch.from_numpy(labels),
            participants=(cache.participant,) * len(indices),
        )


class ParticipantBatchSampler(Sampler[list[int]]):
    def __init__(
        self,
        dataset: WindowDataset,
        batch_size: int,
        shuffle: bool = False,
        seed: int = 0,
    ):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.shuffle = shuffle
        self.seed = seed
        self._epoch = 0
        self.groups: dict[str, list[int]] = {}
        group_for_index = getattr(
            dataset, "batch_group_for_index", dataset.participant_for_index
        )
        for index in range(len(dataset)):
            group = group_for_index(index)
            self.groups.setdefault(group, []).append(index)
        self.batch_size = batch_size

    def __iter__(self):
        groups = list(self.groups.items())
        rng = np.random.default_rng(self.seed + self._epoch)
        self._epoch += 1
        if self.shuffle:
            rng.shuffle(groups)
        for _, original_indices in groups:
            indices = list(original_indices)
            if self.shuffle:
                rng.shuffle(indices)
            for start in range(0, len(indices), self.batch_size):
                yield indices[start : start + self.batch_size]

    def __len__(self):
        return sum(
            (len(indices) + self.batch_size - 1) // self.batch_size
            for indices in self.groups.values()
        )
