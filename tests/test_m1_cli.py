import json

import yaml

from eating_detection.cli import main


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


def test_m1_train_cli_builds_paired_ppg_cache_and_runs_ppg_only_diagnostic(tmp_path):
    data_root = tmp_path / "data"
    train_dir = data_root / "sensors"
    index_dir = data_root / "index"
    _write_sensor(train_dir / "organized" / "p1" / "sensor.txt")
    _write_sensor(train_dir / "organized" / "p2" / "sensor.txt")
    index_dir.mkdir(parents=True)
    (index_dir / "mealinfo.csv").write_text(
        "externalid,beforeTime,afterTime\np1,1000,2000\np2,1000,2000\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"train": ["p1"], "val": ["p2"], "excluded_test": ["test"]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "run"
    config = tmp_path / "m1.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "data_root": str(data_root),
                "index_dir": str(index_dir),
                "train_dir": str(train_dir),
                "output_dir": str(output_dir),
                "cache_dir": str(tmp_path / "cache" / "imu"),
                "ppg_cache_dir": str(tmp_path / "cache" / "ppg"),
                "model": "m1_imu_ppg",
                "model_mode": "ppg_only",
                "m1_embedding_dim": 8,
                "m1_modality_dropout": 0.0,
                "resample_hz": 25,
                "max_gap_ms": 200,
                "window_sec": 1,
                "step_sec": 1,
                "label_positive_overlap": 0.25,
                "boundary_mode": "soft",
                "event_iou_threshold": 0.25,
            }
        ),
        encoding="utf-8",
    )

    assert main(
        [
            "train",
            "--config", str(config),
            "--split-manifest", str(manifest),
            "--epochs", "1",
            "--batch-size", "2",
            "--device", "cpu",
        ]
    ) == 0

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    saved_config = yaml.safe_load((output_dir / "config.yaml").read_text(encoding="utf-8"))
    assert metrics["model_mode"] == "ppg_only"
    assert metrics["cache"]["ppg"]["files"] == 2
    assert saved_config["model"] == "m1_imu_ppg"
    assert saved_config["ppg_cache_dir"] == str(tmp_path / "cache" / "ppg")
