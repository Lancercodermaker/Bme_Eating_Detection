import json

import pytest

from eating_detection.cache import FeatureCacheConfig, build_feature_cache
from eating_detection.ppg_cache import PPGCacheConfig, build_ppg_cache
from eating_detection.training import fit_m1_cached


def _write_sensor(path, rows=61):
    path.parent.mkdir(parents=True, exist_ok=True)
    ppg_columns = [f"PPG{index}" for index in range(1, 45)]
    header = [
        "ACC_TIME", "PPG_TIME", "GYRO_TIME", *ppg_columns,
        "ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z",
    ]
    lines = ["\t".join(header)]
    for index in range(rows):
        timestamp = 1000 + index * 100
        lines.append("\t".join(map(str, [
            timestamp, timestamp, timestamp, *([index + 1] * 44),
            index + 1, index + 2, index + 3, index + 4, index + 5, index + 6,
        ])))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _paired_lazy_caches(tmp_path):
    imu_caches = []
    ppg_caches = []
    for participant in ("p1", "p2"):
        source = _write_sensor(tmp_path / "organized" / participant / "sensor.txt")
        intervals = [(1000, 2000)]
        imu = build_feature_cache(
            source,
            intervals,
            tmp_path / "cache",
            FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
        )
        ppg = build_ppg_cache(
            source,
            intervals,
            tmp_path / "cache",
            PPGCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
            imu.timestamps_ms,
            lazy=True,
        )
        imu_caches.append(
            build_feature_cache(
                source,
                intervals,
                tmp_path / "cache",
                FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
                lazy=True,
            )
        )
        ppg_caches.append(ppg)
    return imu_caches, ppg_caches


def test_m1_cached_ppg_only_training_uses_cache_and_writes_reproducible_outputs(monkeypatch, tmp_path):
    imu_caches, ppg_caches = _paired_lazy_caches(tmp_path)

    def fail_if_source_is_read(*args, **kwargs):
        raise AssertionError("cache-backed M1 training must not parse source files")

    monkeypatch.setattr("eating_detection.cache.iter_sensor_chunks", fail_if_source_is_read)
    monkeypatch.setattr("eating_detection.ppg_cache.iter_ppg_chunks", fail_if_source_is_read)
    result = fit_m1_cached(
        imu_caches=imu_caches,
        ppg_caches=ppg_caches,
        train_participants={"p1"},
        val_participants={"p2"},
        truth={"p2": [(1000, 2000)]},
        output_dir=tmp_path / "run",
        config_payload={"event_iou_threshold": 0.25},
        split_manifest={"train": ["p1"], "val": ["p2"], "excluded_test": ["test"]},
        epochs=1,
        batch_size=2,
        seed=7,
        iou_threshold=0.25,
        device_name="cpu",
        model_mode="ppg_only",
        embedding_dim=8,
        modality_dropout=0.25,
    )

    assert result["device"] == "cpu"
    assert result["metrics"]["model_mode"] == "ppg_only"
    assert result["metrics"]["modality_coverage"]["train"]["ppg_available"] > 0
    assert set(result["metrics"]["calibration"]) == {
        "binary_window_membership", "soft_overlap_target"
    }
    assert (tmp_path / "run" / "checkpoint.pt").exists()
    assert (tmp_path / "run" / "normalization.json").exists()
    assert (tmp_path / "run" / "window_probabilities.jsonl").exists()
    normalization = json.loads((tmp_path / "run" / "normalization.json").read_text(encoding="utf-8"))
    assert set(normalization) == {"imu", "ppg"}


def test_m1_cached_training_rejects_cache_participants_outside_the_frozen_split(tmp_path):
    imu_caches, ppg_caches = _paired_lazy_caches(tmp_path)

    with pytest.raises(ValueError, match="outside train/val"):
        fit_m1_cached(
            imu_caches=imu_caches,
            ppg_caches=ppg_caches,
            train_participants={"p1"},
            val_participants=set(),
            truth={},
            output_dir=tmp_path / "run",
            config_payload={"event_iou_threshold": 0.25},
            split_manifest={"train": ["p1"], "val": [], "excluded_test": ["p2"]},
            epochs=1,
            batch_size=2,
            seed=7,
            iou_threshold=0.25,
            device_name="cpu",
        )
