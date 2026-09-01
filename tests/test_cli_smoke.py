import json

from eating_detection.cli import build_parser, run_toy_pipeline


def test_toy_pipeline_writes_event_metrics(tmp_path):
    result = run_toy_pipeline(tmp_path, seed=7)
    assert result["status"] == "PASS"
    report = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert {"precision", "recall", "f1", "start_mae_ms", "end_mae_ms"} <= set(report)


def test_train_cli_accepts_explicit_data_directories():
    args = build_parser().parse_args(
        [
            "train",
            "--config",
            "config.yaml",
            "--data-root",
            "data",
            "--index-dir",
            "index",
            "--train-dir",
            "sensor.txt",
            "--sensor-file",
            "sample.txt",
            "--cache-dir",
            "cache/features",
        ]
    )
    assert args.index_dir == "index"
    assert args.train_dir == "sensor.txt"
    assert args.sensor_files == ["sample.txt"]
    assert args.cache_dir == "cache/features"
