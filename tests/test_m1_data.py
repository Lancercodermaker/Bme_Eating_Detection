from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
import torch

from eating_detection.cache import FeatureCacheConfig, build_feature_cache
from eating_detection.ppg_cache import PPGCacheConfig, build_ppg_cache
from eating_detection.dataset import PairedCachedWindowDataset
from eating_detection.training import fit_m1_ppg_standardizer, standardize_m1_ppg_batch


def _write_sensor(path, rows=101, zero_ppg=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    ppg_columns = [f"PPG{i}" for i in range(1, 45)]
    header = [
        "ACC_TIME", "PPG_TIME", "GYRO_TIME", *ppg_columns,
        "ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z",
    ]
    lines = ["\t".join(header)]
    for index in range(rows):
        timestamp = 1000 + index * 100
        ppg_value = 0 if zero_ppg else index + 1
        lines.append("\t".join(map(str, [
            timestamp, timestamp, timestamp, *([ppg_value] * 44),
            index + 1, index + 2, index + 3, index + 4, index + 5, index + 6,
        ])))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _paired_caches(tmp_path, zero_ppg=False, lazy=False):
    source = _write_sensor(tmp_path / "organized" / "p1" / "sensor.txt", zero_ppg=zero_ppg)
    imu = build_feature_cache(
        source, [(1500, 2500)], tmp_path / "cache",
        FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
        lazy=lazy,
    )
    ppg = build_ppg_cache(
        source, [(1500, 2500)], tmp_path / "cache",
        PPGCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
        None if lazy else imu.timestamps_ms,
        lazy=lazy,
    )
    return imu, ppg


def test_paired_cache_dataset_slices_aligned_modalities_and_derives_window_mask(tmp_path):
    imu, ppg = _paired_caches(tmp_path)

    dataset = PairedCachedWindowDataset([imu], [ppg], include_ignored=True)
    imu_window, ppg_window, modality_mask, label, participant = dataset[0]

    assert imu_window.shape == (10, 25)
    assert ppg_window.shape == (45, 25)
    assert modality_mask.tolist() == [1.0, 1.0]
    assert label.ndim == 0
    assert participant == "p1"


def test_paired_cache_dataset_retains_missing_ppg_with_an_explicit_modality_mask(tmp_path):
    imu, ppg = _paired_caches(tmp_path, zero_ppg=True)

    dataset = PairedCachedWindowDataset([imu], [ppg], include_ignored=True)
    _, ppg_window, modality_mask, _, _ = dataset[0]

    assert not ppg_window.any()
    assert modality_mask.tolist() == [1.0, 0.0]


def test_paired_dataset_uses_compact_all_missing_ppg_cache_for_an_excessive_reference(tmp_path):
    source = _write_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    imu = build_feature_cache(
        source,
        [(1500, 2500)],
        tmp_path / "cache",
        FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
    )
    ppg = build_ppg_cache(
        source,
        [(1500, 2500)],
        tmp_path / "cache",
        PPGCacheConfig(
            resample_hz=25,
            max_gap_ms=200,
            window_sec=1,
            step_sec=1,
            max_dense_samples=10,
        ),
        imu.timestamps_ms,
        lazy=True,
    )

    dataset = PairedCachedWindowDataset([imu], [ppg], include_ignored=True)
    _, ppg_window, modality_mask, _, _ = dataset[0]

    assert ppg.metadata["storage"] == "all_missing_compact"
    assert ppg_window.shape == (45, 25)
    assert not ppg_window.any()
    assert modality_mask.tolist() == [1.0, 0.0]


def test_compact_ppg_cache_hit_stays_lazy_when_ppg_reader_throws(tmp_path):
    source = _write_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    imu = build_feature_cache(
        source,
        [(1500, 2500)],
        tmp_path / "cache",
        FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
    )
    config = PPGCacheConfig(
        resample_hz=25,
        max_gap_ms=200,
        window_sec=1,
        step_sec=1,
        max_dense_samples=10,
    )
    first = build_ppg_cache(
        source, [(1500, 2500)], tmp_path / "cache", config, imu.timestamps_ms, lazy=True
    )
    assert first.cache_hit is False
    assert first.features_loaded is False

    with patch(
        "eating_detection.ppg_cache.iter_ppg_chunks",
        side_effect=AssertionError("compact cache hit must not read the source CSV"),
    ):
        hit = build_ppg_cache(
            source, [(1500, 2500)], tmp_path / "cache", config, imu.timestamps_ms, lazy=True
        )

    assert hit.cache_hit is True
    assert hit.metadata["storage"] == "all_missing_compact"
    assert hit.features_loaded is False


def test_compact_ppg_batch_fetch_synthesizes_only_local_zero_windows(tmp_path):
    source = _write_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    imu = build_feature_cache(
        source,
        [(1500, 2500)],
        tmp_path / "cache",
        FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
    )
    ppg = build_ppg_cache(
        source,
        [(1500, 2500)],
        tmp_path / "cache",
        PPGCacheConfig(
            resample_hz=25,
            max_gap_ms=200,
            window_sec=1,
            step_sec=1,
            max_dense_samples=10,
        ),
        imu.timestamps_ms,
        lazy=True,
    )
    dataset = PairedCachedWindowDataset([imu], [ppg], include_ignored=True)

    batch = dataset.__getitems__([0, 1])

    assert batch.ppg.shape == (2, 45, 25)
    assert batch.ppg.dtype == torch.float32
    assert torch.count_nonzero(batch.ppg) == 0
    assert batch.modality_mask.shape == (2, 2)
    assert torch.all(batch.modality_mask[:, 0] == 1)
    assert torch.all(batch.modality_mask[:, 1] == 0)
    assert ppg.features_loaded is False


def test_paired_cache_dataset_rejects_timestamp_window_or_label_mismatch(tmp_path):
    imu, ppg = _paired_caches(tmp_path)
    mismatched_labels = ppg.window_labels.copy()
    mismatched_labels[0] += 0.1

    with pytest.raises(ValueError, match="window labels"):
        PairedCachedWindowDataset([imu], [replace(ppg, window_labels=mismatched_labels)])


def test_paired_cache_dataset_validates_timestamps_even_when_caches_are_lazy(tmp_path):
    imu, ppg = _paired_caches(tmp_path, lazy=True)
    with np.load(ppg.cache_path, allow_pickle=False) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files if name != "timestamps_ms"}
        timestamps = np.array(data["timestamps_ms"], copy=True)
    timestamps[0] += 1
    with ppg.cache_path.open("wb") as handle:
        np.savez(handle, timestamps_ms=timestamps, **arrays)

    with pytest.raises(ValueError, match="timestamps"):
        PairedCachedWindowDataset([imu], [ppg])


def test_m1_ppg_standardizer_uses_train_quality_samples_only(tmp_path):
    _, ppg = _paired_caches(tmp_path)
    train_features = np.vstack([np.array([[1.0, 3.0]] * 44), np.array([1.0, 1.0])]).astype(np.float32)
    validation_features = np.vstack([np.array([[101.0, 103.0]] * 44), np.array([1.0, 1.0])]).astype(np.float32)
    quality = np.ones((1, 2), dtype=bool)
    train = replace(ppg, participant="train", features=train_features, quality_mask=quality)
    validation = replace(ppg, participant="validation", features=validation_features, quality_mask=quality)

    stats = fit_m1_ppg_standardizer([train, validation], {"train"})

    assert stats.mean.shape == (44,)
    assert np.allclose(stats.mean, 2.0)
    assert np.allclose(stats.std, 1.0)


def test_m1_ppg_standardization_rezeros_invalid_samples_after_scaling(tmp_path):
    _, ppg = _paired_caches(tmp_path)
    stats = replace(
        fit_m1_ppg_standardizer([ppg], {"p1"}),
        mean=np.full(44, 2.0, dtype=np.float32),
        std=np.ones(44, dtype=np.float32),
    )
    batch = torch.zeros(1, 45, 2)
    batch[:, :44, 0] = 1.0
    batch[:, -1, 0] = 1.0

    standardized = standardize_m1_ppg_batch(batch, stats)

    assert torch.all(standardized[:, :44, 1] == 0)
    assert torch.all(standardized[:, :44, 0] == -1)
    assert standardized[:, -1].tolist() == [[1.0, 0.0]]
