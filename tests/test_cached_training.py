from pathlib import Path

from eating_detection.cache import FeatureCacheConfig, build_feature_caches
from eating_detection.training import fit_m0_cached


def _write_sensor(path: Path, rows: int = 31) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z"]
    for index in range(rows):
        timestamp = 1000 + index * 100
        values = [timestamp, timestamp, index + 1, index + 2, index + 3, index + 4, index + 5, index + 6]
        lines.append("\t".join(map(str, values)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_cached_training_does_not_read_source_after_cache_hit(monkeypatch, tmp_path):
    paths = [
        _write_sensor(tmp_path / "organized" / "p1" / "sensor.txt"),
        _write_sensor(tmp_path / "organized" / "p2" / "sensor.txt"),
    ]
    cache_config = FeatureCacheConfig(
        resample_hz=25,
        max_gap_ms=200,
        window_sec=1,
        step_sec=1,
        positive_overlap=0.25,
        boundary_mode="soft",
    )
    caches, issues = build_feature_caches(
        paths,
        {"p1": [(1000, 4000)], "p2": [(1000, 4000)]},
        tmp_path / "cache",
        cache_config,
    )
    assert issues == []

    def fail_if_source_is_read(*args, **kwargs):
        raise AssertionError("cache-backed training must not parse source files")

    monkeypatch.setattr("eating_detection.cache.iter_sensor_chunks", fail_if_source_is_read)
    result = fit_m0_cached(
        caches=caches,
        train_participants={"p1"},
        val_participants={"p2"},
        truth={"p2": [(1000, 4000)]},
        output_dir=tmp_path / "run",
        config_payload={"preprocess_variant": "p0_raw_mask", "event_iou_threshold": 0.25},
        split_manifest={"train": ["p1"], "val": ["p2"], "excluded_test": []},
        epochs=1,
        batch_size=2,
        seed=7,
        iou_threshold=0.25,
        device_name="cpu",
    )

    assert result["device"] == "cpu"
    assert (tmp_path / "run" / "checkpoint.pt").exists()
    assert (tmp_path / "run" / "metrics.json").exists()
