import json

import pytest

from eating_detection.cache import FeatureCacheConfig, build_feature_cache
from eating_detection.dataset import PairedCachedWindowDataset
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


def test_m1_paired_dataset_filters_windows_below_imu_quality_threshold(tmp_path):
    imu_caches, ppg_caches = _paired_lazy_caches(tmp_path)
    imu_caches[0] = build_feature_cache(
        imu_caches[0].source_path,
        [(1000, 2000)],
        tmp_path / "cache",
        FeatureCacheConfig(resample_hz=25, max_gap_ms=200, window_sec=1, step_sec=1),
    )
    imu_caches[0].quality_mask[:, : imu_caches[0].quality_mask.shape[1] // 2] = False

    unfiltered = PairedCachedWindowDataset(
        imu_caches, ppg_caches, participants={"p1"}
    )
    filtered = PairedCachedWindowDataset(
        imu_caches,
        ppg_caches,
        participants={"p1"},
        min_quality_fraction=0.5,
    )

    assert len(filtered) < len(unfiltered)
    assert all(
        filtered._window_quality_fractions(imu_caches[0])[window_index] >= 0.5
        for _, window_index in filtered._references
    )


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
        min_quality_fraction=0.5,
    )

    assert result["device"] == "cpu"
    assert result["metrics"]["model_mode"] == "ppg_only"
    assert result["metrics"]["loss_mode"] == "global_bce"
    assert result["metrics"]["min_quality_fraction"] == 0.5
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


def test_m1_negative_run_bce_records_train_only_weighting(tmp_path):
    imu_caches, ppg_caches = _paired_lazy_caches(tmp_path)

    result = fit_m1_cached(
        imu_caches=imu_caches,
        ppg_caches=ppg_caches,
        train_participants={"p1"},
        val_participants={"p2"},
        truth={"p2": [(1000, 2000)]},
        output_dir=tmp_path / "run",
        config_payload={
            "event_iou_threshold": 0.25,
            "m1_loss_mode": "negative_run_bce",
            "step_sec": 1,
            "m1_negative_run_reference_windows": 2.0,
            "m1_negative_run_max_weight": 3.0,
        },
        split_manifest={"train": ["p1"], "val": ["p2"], "excluded_test": ["test"]},
        epochs=1,
        batch_size=2,
        seed=7,
        iou_threshold=0.25,
        device_name="cpu",
        model_mode="ppg_only",
        embedding_dim=8,
        modality_dropout=0.0,
    )

    metrics = result["metrics"]
    assert metrics["loss_mode"] == "negative_run_bce"
    assert metrics["negative_run_reference_windows"] == 2.0
    assert metrics["negative_run_max_weight"] == 3.0
    assert metrics["negative_run_weight_summary"]["max"] >= 1.0
