from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import numpy as np

from .io import iter_sensor_chunks
from .labels import label_window
from .preprocess import apply_feature_variant, imu_features, resample_uniform
from .timebase import canonicalize_stream, infer_rate_hz, interpolate_uniform


_CACHE_FORMAT_VERSION = 1


@dataclass(frozen=True)
class FeatureCacheConfig:
    resample_hz: int = 25
    max_gap_ms: int = 2_000
    preprocess_variant: str = "p0_raw_mask"
    lowpass_cutoff_hz: float = 1.0
    median_kernel: int = 5
    window_sec: float = 15.0
    step_sec: float = 3.0
    positive_overlap: float = 0.25
    boundary_mode: str = "soft"
    chunksize: int = 50_000
    max_rows: int | None = None

    def __post_init__(self):
        if self.resample_hz <= 0 or self.max_gap_ms < 0:
            raise ValueError("resample_hz must be positive and max_gap_ms must be non-negative")
        if self.window_sec <= 0 or self.step_sec <= 0 or self.step_sec > self.window_sec:
            raise ValueError("step_sec must be positive and no greater than window_sec")
        if not 0 <= self.positive_overlap <= 1:
            raise ValueError("positive_overlap must be between 0 and 1")
        if self.chunksize <= 0 or (self.max_rows is not None and self.max_rows <= 0):
            raise ValueError("chunksize and max_rows must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "resample_hz": self.resample_hz,
            "max_gap_ms": self.max_gap_ms,
            "preprocess_variant": self.preprocess_variant,
            "lowpass_cutoff_hz": self.lowpass_cutoff_hz,
            "median_kernel": self.median_kernel,
            "window_sec": self.window_sec,
            "step_sec": self.step_sec,
            "positive_overlap": self.positive_overlap,
            "boundary_mode": self.boundary_mode,
            "chunksize": self.chunksize,
            "max_rows": self.max_rows,
        }


@dataclass(frozen=True)
class FeatureCache:
    cache_path: Path
    cache_key: str
    source_path: Path
    participant: str
    timestamps_ms: np.ndarray
    features: np.ndarray
    quality_mask: np.ndarray
    window_indices: np.ndarray
    window_starts_ms: np.ndarray
    window_ends_ms: np.ndarray
    window_labels: np.ndarray
    window_loss_mask: np.ndarray
    cache_hit: bool
    timings: dict[str, float]
    metadata: dict[str, object]


def _participant_from_path(path: Path) -> str:
    parts = list(Path(path).parts)
    lowered = [part.casefold() for part in parts]
    if "organized" in lowered:
        index = lowered.index("organized")
        if index + 1 < len(parts):
            return parts[index + 1].replace(" ", "").casefold()
    return Path(path).parent.name.replace(" ", "").casefold()


def _source_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _key_payload(
    path: Path, intervals: list[tuple[int, int]], config: FeatureCacheConfig
) -> dict[str, object]:
    return {
        "cache_format_version": _CACHE_FORMAT_VERSION,
        "source": _source_metadata(path),
        "config": config.as_dict(),
        "intervals": [list(interval) for interval in sorted(intervals)],
    }


def _cache_location(cache_root: Path, key: str) -> Path:
    return Path(cache_root) / key[:2] / f"{key}.npz"


def _read_imu_rows(
    path: Path, max_rows: int | None, chunksize: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    acc_times = []
    gyro_times = []
    acc_values = []
    gyro_values = []
    acc_masks = []
    gyro_masks = []
    rows = 0
    for chunk in iter_sensor_chunks(path, chunksize=chunksize, include_ppg=False):
        take = len(chunk.acc) if max_rows is None else min(len(chunk.acc), max_rows - rows)
        if take <= 0:
            break
        acc_times.append(chunk.timestamp_ms[:take, 0])
        gyro_times.append(chunk.timestamp_ms[:take, 2])
        acc_values.append(chunk.acc[:take])
        gyro_values.append(chunk.gyro[:take])
        acc_masks.append(chunk.acc_valid[:take])
        gyro_masks.append(chunk.gyro_valid[:take])
        rows += take
        if max_rows is not None and rows >= max_rows:
            break
    if not acc_values:
        raise ValueError("sensor file has no rows in the requested limit")
    return (
        np.concatenate(acc_times),
        np.concatenate(gyro_times),
        np.concatenate(acc_values),
        np.concatenate(gyro_values),
        np.concatenate(acc_masks),
        np.concatenate(gyro_masks),
    )


def _build_arrays(
    path: Path,
    intervals: list[tuple[int, int]],
    config: FeatureCacheConfig,
) -> dict[str, np.ndarray]:
    acc_time, gyro_time, acc, gyro, _, _ = _read_imu_rows(
        path, max_rows=config.max_rows, chunksize=config.chunksize
    )
    acc_stream = canonicalize_stream(acc_time, acc)
    gyro_stream = canonicalize_stream(gyro_time, gyro)
    source_hz = max(
        infer_rate_hz(acc_stream.timestamps_ms), infer_rate_hz(gyro_stream.timestamps_ms)
    )
    start_ms = max(int(acc_stream.timestamps_ms[0]), int(gyro_stream.timestamps_ms[0]))
    end_ms = min(int(acc_stream.timestamps_ms[-1]), int(gyro_stream.timestamps_ms[-1]))
    if end_ms <= start_ms:
        raise ValueError("ACC and GYRO streams have no overlapping time range")

    grid, acc_uniform, acc_mask = interpolate_uniform(
        acc_stream, source_hz, start_ms, end_ms, config.max_gap_ms
    )
    gyro_grid, gyro_uniform, gyro_mask = interpolate_uniform(
        gyro_stream, source_hz, start_ms, end_ms, config.max_gap_ms
    )
    if not np.array_equal(grid, gyro_grid):
        raise ValueError("aligned streams produced different time grids")
    signal_features, mask = imu_features(
        acc_uniform, gyro_uniform, acc_mask, gyro_mask
    )
    resampled_features = resample_uniform(
        signal_features, source_hz, config.resample_hz
    )
    resampled_features = apply_feature_variant(
        resampled_features,
        sample_hz=config.resample_hz,
        name=config.preprocess_variant,
        lowpass_cutoff_hz=config.lowpass_cutoff_hz,
        median_kernel=config.median_kernel,
    )
    resampled_mask = (
        resample_uniform(mask.astype(np.float32), source_hz, config.resample_hz) > 0.5
    )
    length = min(len(resampled_features), len(resampled_mask))
    features = np.vstack(
        [
            resampled_features[:length].T,
            resampled_mask[:length].astype(np.float32).T,
        ]
    ).astype(np.float32, copy=False)
    quality_mask = resampled_mask[:length].T.astype(bool, copy=False)
    timestamps_ms = np.rint(
        start_ms + np.arange(length, dtype=np.float64) * 1000.0 / config.resample_hz
    ).astype(np.int64)

    window_samples = max(1, int(round(config.window_sec * config.resample_hz)))
    step_samples = max(1, int(round(config.step_sec * config.resample_hz)))
    offsets = np.arange(
        0, max(0, length - window_samples + 1), step_samples, dtype=np.int64
    )
    window_indices = np.column_stack(
        [offsets, offsets + window_samples]
    ).astype(np.int64, copy=False)
    window_starts_ms = np.rint(
        start_ms + offsets.astype(np.float64) * 1000.0 / config.resample_hz
    ).astype(np.int64)
    window_ends_ms = np.rint(
        window_starts_ms.astype(np.float64)
        + window_samples * 1000.0 / config.resample_hz
    ).astype(np.int64)
    labels = []
    loss_mask = []
    for window_start, window_end in zip(window_starts_ms, window_ends_ms):
        label = label_window(
            (int(window_start), int(window_end)),
            intervals,
            config.positive_overlap,
            config.boundary_mode,
        )
        labels.append(0.0 if label is None else float(label))
        loss_mask.append(label is not None)
    return {
        "timestamps_ms": timestamps_ms,
        "features": features,
        "quality_mask": quality_mask,
        "window_indices": window_indices,
        "window_starts_ms": window_starts_ms,
        "window_ends_ms": window_ends_ms,
        "window_labels": np.asarray(labels, dtype=np.float32),
        "window_loss_mask": np.asarray(loss_mask, dtype=bool),
    }


def _from_arrays(
    cache_path: Path,
    cache_key: str,
    source_path: Path,
    participant: str,
    arrays: dict[str, np.ndarray],
    metadata: dict[str, object],
    cache_hit: bool,
    timings: dict[str, float],
) -> FeatureCache:
    return FeatureCache(
        cache_path=cache_path,
        cache_key=cache_key,
        source_path=source_path,
        participant=participant,
        timestamps_ms=arrays["timestamps_ms"],
        features=arrays["features"],
        quality_mask=arrays["quality_mask"],
        window_indices=arrays["window_indices"],
        window_starts_ms=arrays["window_starts_ms"],
        window_ends_ms=arrays["window_ends_ms"],
        window_labels=arrays["window_labels"],
        window_loss_mask=arrays["window_loss_mask"],
        cache_hit=cache_hit,
        timings=timings,
        metadata=metadata,
    )


def _load_cache(
    cache_path: Path,
    expected_key: str,
    source_path: Path,
) -> FeatureCache:
    with np.load(cache_path, allow_pickle=False) as data:
        metadata_raw = data["metadata_json"].item()
        if isinstance(metadata_raw, bytes):
            metadata_raw = metadata_raw.decode("utf-8")
        metadata = json.loads(str(metadata_raw))
        if metadata.get("cache_key") != expected_key:
            raise ValueError("cache metadata key does not match requested configuration")
        arrays = {
            name: np.array(data[name], copy=True)
            for name in (
                "timestamps_ms",
                "features",
                "quality_mask",
                "window_indices",
                "window_starts_ms",
                "window_ends_ms",
                "window_labels",
                "window_loss_mask",
            )
        }
    return _from_arrays(
        cache_path,
        expected_key,
        source_path,
        str(metadata["participant"]),
        arrays,
        metadata,
        cache_hit=True,
        timings={"cache_load_sec": 0.0},
    )


def _write_cache(
    cache_path: Path, metadata: dict[str, object], arrays: dict[str, np.ndarray]
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_name(f"{cache_path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as handle:
            np.savez(handle, metadata_json=np.array(json.dumps(metadata, ensure_ascii=False), dtype=np.str_), **arrays)
        os.replace(temporary, cache_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_feature_cache(
    source_path: Path,
    intervals: list[tuple[int, int]],
    cache_root: Path,
    config: FeatureCacheConfig,
) -> FeatureCache:
    source_path = Path(source_path)
    key_payload = _key_payload(source_path, intervals, config)
    encoded = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cache_key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    cache_path = _cache_location(Path(cache_root), cache_key)
    participant = _participant_from_path(source_path)
    if cache_path.exists():
        started = time.perf_counter()
        cached = _load_cache(cache_path, cache_key, source_path)
        return FeatureCache(
            **{**cached.__dict__, "timings": {"cache_load_sec": time.perf_counter() - started}}
        )

    started = time.perf_counter()
    arrays = _build_arrays(source_path, intervals, config)
    metadata = {
        **key_payload,
        "cache_key": cache_key,
        "participant": participant,
        "array_shapes": {name: list(value.shape) for name, value in arrays.items()},
        "build_time_sec": time.perf_counter() - started,
    }
    _write_cache(cache_path, metadata, arrays)
    return _from_arrays(
        cache_path,
        cache_key,
        source_path,
        participant,
        arrays,
        metadata,
        cache_hit=False,
        timings={"build_sec": time.perf_counter() - started},
    )


def build_feature_caches(
    source_paths: list[Path],
    intervals_by_participant: dict[str, list[tuple[int, int]]],
    cache_root: Path,
    config: FeatureCacheConfig,
) -> tuple[list[FeatureCache], list[dict[str, str]]]:
    """Build files independently so completed cache files survive a later failure."""
    completed: list[FeatureCache] = []
    issues: list[dict[str, str]] = []
    for source_path in sorted(Path(path) for path in source_paths):
        participant = _participant_from_path(source_path)
        try:
            completed.append(
                build_feature_cache(
                    source_path,
                    intervals_by_participant.get(participant, []),
                    cache_root,
                    config,
                )
            )
        except (OSError, ValueError) as exc:
            issues.append({"path": str(source_path), "reason": str(exc)})
    return completed, issues
