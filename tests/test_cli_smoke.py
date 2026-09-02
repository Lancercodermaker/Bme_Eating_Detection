import json

import yaml

from eating_detection.cli import build_parser, main, run_toy_pipeline


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


def test_evaluate_preserves_training_metadata(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump({"event_iou_threshold": 0.25}), encoding="utf-8"
    )
    (run_dir / "split_manifest.json").write_text(
        json.dumps({"train": ["p0"], "val": ["p1"], "excluded_test": []}),
        encoding="utf-8",
    )
    (run_dir / "truth_intervals.json").write_text(
        json.dumps({"p1": [[0, 100]]}), encoding="utf-8"
    )
    (run_dir / "decoder.json").write_text(
        json.dumps({"threshold": 0.5, "merge_gap_ms": 0, "min_duration_ms": 0}),
        encoding="utf-8",
    )
    (run_dir / "window_probabilities.jsonl").write_text(
        json.dumps({"participant": "p1", "start_ms": 0, "end_ms": 100, "probability": 1.0, "split": "val"})
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "metrics.json").write_text(
        json.dumps({"device": "cuda", "batch_size": 64, "training_time_sec": 12.5}),
        encoding="utf-8",
    )

    assert main(["evaluate", "--run-dir", str(run_dir), "--split", "val"]) == 0

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["device"] == "cuda"
    assert metrics["batch_size"] == 64
    assert metrics["training_time_sec"] == 12.5
    assert metrics["f1"] == 1.0
