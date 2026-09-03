from pathlib import Path
from dataclasses import replace

import numpy as np

from eating_detection.cache import (
    FeatureCacheConfig,
    LazyFeatureCache,
    build_feature_cache,
    build_feature_caches,
)
from eating_detection.dataset import CachedWindowDataset, build_records_from_sensor_file


def _write_imu_only_sensor(path: Path, rows: int = 31) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z"]
    for index in range(rows):
        timestamp = 1000 + index * 100
        values = [timestamp, timestamp, index + 1, index + 2, index + 3, index + 4, index + 5, index + 6]
        lines.append("\t".join(map(str, values)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _config(**overrides):
    values = {
        "resample_hz": 25,
        "max_gap_ms": 200,
        "preprocess_variant": "p0_raw_mask",
        "window_sec": 1,
        "step_sec": 1,
        "positive_overlap": 0.25,
        "boundary_mode": "soft",
    }
    values.update(overrides)
    return FeatureCacheConfig(**values)


def test_cache_miss_writes_continuous_features_and_window_index(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")

    cached = build_feature_cache(
        sensor,
        intervals=[(1500, 2500)],
        cache_root=tmp_path / "cache",
        config=_config(),
    )

    assert cached.cache_hit is False
    assert cached.cache_path.exists()
    assert cached.features.shape[0] == 10
    assert cached.quality_mask.shape == (2, cached.features.shape[1])
    assert cached.window_indices.ndim == 2
    assert cached.window_indices.shape[1] == 2
    assert len(cached.window_indices) == len(cached.window_labels) == len(cached.window_loss_mask)
    assert cached.features.flags.owndata is True


def test_cache_hit_does_not_read_source_again(monkeypatch, tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    config = _config()
    first = build_feature_cache(sensor, [], tmp_path / "cache", config)

    def fail_if_source_is_read(*args, **kwargs):
        raise AssertionError("cache hit must not parse the source CSV")

    monkeypatch.setattr("eating_detection.cache.iter_sensor_chunks", fail_if_source_is_read)
    second = build_feature_cache(sensor, [], tmp_path / "cache", config)

    assert first.cache_key == second.cache_key
    assert second.cache_hit is True
    assert np.array_equal(first.features, second.features)
    assert np.array_equal(first.window_indices, second.window_indices)
    assert np.array_equal(first.window_labels, second.window_labels)


def test_cache_key_includes_preprocessing_and_window_label_contract(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    base = build_feature_cache(sensor, [], tmp_path / "cache", _config())
    changed_preprocess = build_feature_cache(
        sensor,
        [],
        tmp_path / "cache",
        _config(preprocess_variant="p1_lowpass_dynamic"),
    )
    changed_label = build_feature_cache(
        sensor,
        [(1500, 2500)],
        tmp_path / "cache",
        _config(),
    )

    assert len({base.cache_key, changed_preprocess.cache_key, changed_label.cache_key}) == 3


def test_cached_window_dataset_slices_continuous_array(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    cached = build_feature_cache(
        sensor,
        [(1500, 2500)],
        tmp_path / "cache",
        _config(),
    )
    dataset = CachedWindowDataset([cached], include_ignored=True)

    features, label, participant = dataset[0]
    assert tuple(features.shape) == (10, 25)
    assert label.ndim == 0
    assert participant == "p1"
    assert dataset.participant_for_index(0) == "p1"


def test_cached_window_dataset_filters_windows_below_quality_threshold(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt", rows=101)
    cached = build_feature_cache(
        sensor,
        [(1500, 2500)],
        tmp_path / "cache",
        _config(),
    )
    quality = np.zeros_like(cached.quality_mask)
    quality[:, : quality.shape[1] // 2] = True
    degraded = replace(cached, quality_mask=quality)

    all_windows = CachedWindowDataset([degraded], include_ignored=True)
    quality_windows = CachedWindowDataset(
        [degraded], include_ignored=True, min_quality_fraction=0.75
    )

    assert len(all_windows) > len(quality_windows)


def test_cached_window_dataset_label_lookup_matches_quality_filtered_windows(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt", rows=101)
    cached = build_feature_cache(
        sensor,
        [(1500, 2500)],
        tmp_path / "cache",
        _config(),
    )
    quality = np.zeros_like(cached.quality_mask)
    quality[:, : quality.shape[1] // 2] = True
    degraded = replace(cached, quality_mask=quality)
    dataset = CachedWindowDataset(
        [degraded], include_ignored=True, min_quality_fraction=0.75
    )

    expected = [float(degraded.window_labels[index]) for _, index in dataset._references]

    assert [dataset.label_for_index(index) for index in range(len(dataset))] == expected


def test_quality_filter_does_not_load_lazy_feature_array(monkeypatch, tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt", rows=101)
    cached = build_feature_cache(
        sensor,
        [],
        tmp_path / "cache",
        _config(),
        lazy=True,
    )

    def fail_if_features_are_loaded(_cache):
        raise AssertionError("quality filtering must not load the feature array")

    monkeypatch.setattr(LazyFeatureCache, "ensure_features", fail_if_features_are_loaded)
    dataset = CachedWindowDataset(
        [cached], include_ignored=True, min_quality_fraction=0.75
    )

    assert len(dataset) > 0


def test_cache_windows_match_legacy_records(tmp_path):
    sensor = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    config = _config()
    cached = build_feature_cache(sensor, [(1500, 2500)], tmp_path / "cache", config)
    legacy = build_records_from_sensor_file(
        sensor,
        intervals=[(1500, 2500)],
        resample_hz=config.resample_hz,
        window_sec=config.window_sec,
        step_sec=config.step_sec,
        positive_overlap=config.positive_overlap,
        boundary_mode=config.boundary_mode,
        max_gap_ms=config.max_gap_ms,
    )

    assert len(legacy) == len(cached.window_indices)
    assert [(r.start_ms, r.end_ms) for r in legacy] == list(
        zip(cached.window_starts_ms.tolist(), cached.window_ends_ms.tolist())
    )
    assert [r.label for r in legacy] == cached.window_labels.tolist()
    for index, record in enumerate(legacy):
        start, end = cached.window_indices[index]
        assert np.allclose(record.features.numpy(), cached.features[:, start:end])


def test_cache_build_resumes_completed_files_after_one_file_failure(monkeypatch, tmp_path):
    first = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    second = _write_imu_only_sensor(tmp_path / "organized" / "p2" / "sensor.txt")
    cache_module = __import__("eating_detection.cache", fromlist=["build_feature_cache"])
    real_build = cache_module.build_feature_cache

    def fail_second(source_path, *args, **kwargs):
        if Path(source_path).parent.name == "p2":
            raise ValueError("simulated file failure")
        return real_build(source_path, *args, **kwargs)

    monkeypatch.setattr(cache_module, "build_feature_cache", fail_second)
    completed, issues = build_feature_caches([first, second], {}, tmp_path / "cache", _config())
    assert [cache.participant for cache in completed] == ["p1"]
    assert len(issues) == 1
    assert first.exists()

    monkeypatch.setattr(cache_module, "build_feature_cache", real_build)
    resumed, resumed_issues = build_feature_caches([first, second], {}, tmp_path / "cache", _config())
    assert resumed_issues == []
    assert [cache.participant for cache in resumed] == ["p1", "p2"]
    assert resumed[0].cache_hit is True
    assert resumed[1].cache_hit is False


def test_lazy_cache_releases_previous_feature_array_when_switching_files(tmp_path):
    first = _write_imu_only_sensor(tmp_path / "organized" / "p1" / "sensor.txt")
    second = _write_imu_only_sensor(tmp_path / "organized" / "p2" / "sensor.txt")
    caches, issues = build_feature_caches(
        [first, second],
        {},
        tmp_path / "cache",
        _config(),
        lazy=True,
    )
    assert issues == []
    assert all(cache.features_loaded is False for cache in caches)

    dataset = CachedWindowDataset(caches, include_ignored=True)
    dataset[0]
    assert caches[0].features_loaded is True
    dataset[len(dataset) - 1]
    assert caches[0].features_loaded is False
    assert caches[1].features_loaded is True
