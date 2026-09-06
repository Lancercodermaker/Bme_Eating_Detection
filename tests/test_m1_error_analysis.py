import json
import hashlib
from pathlib import Path

import numpy as np
import yaml

from eating_detection import error_analysis


def _write_cache(path: Path, source: Path, *, ppg: bool, reference_hash: str | None = None) -> None:
    timestamps = np.arange(40, dtype=np.int64)
    windows = np.asarray([[0, 10], [10, 20], [30, 40]], dtype=np.int64)
    metadata = {
        "participant": "p1",
        "source": {"path": str(source), "size_bytes": 1, "mtime_ns": 1},
        "cache_key": path.stem,
        "array_shapes": {},
    }
    arrays = {
        "timestamps_ms": timestamps,
        "features": np.zeros((45 if ppg else 10, 40), dtype=np.float32),
        "quality_mask": np.ones((1 if ppg else 2, 40), dtype=bool),
        "window_indices": windows,
        "window_starts_ms": np.asarray([0, 10, 30], dtype=np.int64),
        "window_ends_ms": np.asarray([10, 20, 40], dtype=np.int64),
        "window_labels": np.asarray([1.0, 0.0, 0.0], dtype=np.float32),
        "window_loss_mask": np.ones(3, dtype=bool),
    }
    metadata["array_shapes"] = {name: list(value.shape) for name, value in arrays.items()}
    if ppg:
        metadata.update(
            {
                "modality": "ppg",
                "reference": {
                    "sha256": reference_hash
                    or hashlib.sha256(timestamps.astype("<i8").tobytes()).hexdigest(),
                    "length": 40,
                },
                "storage": "dense",
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, metadata_json=np.asarray(json.dumps(metadata), dtype="U"), **arrays)


def test_m1_analysis_reports_fp_event_details_and_modality_strata(tmp_path: Path):
    run_dir = tmp_path / "run"
    imu_dir = tmp_path / "imu"
    ppg_dir = tmp_path / "ppg"
    source = tmp_path / "organized" / "P1" / "sensor.txt"
    _write_cache(imu_dir / "imu.npz", source, ppg=False)
    _write_cache(ppg_dir / "ppg.npz", source, ppg=True)
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": "m1_imu_ppg",
                "model_mode": "fusion",
                "event_iou_threshold": 0.25,
                "label_positive_overlap": 0.25,
                "seed": 7,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "decoder.json").write_text(
        json.dumps({"threshold": 0.5, "merge_gap_ms": 0, "min_duration_ms": 0}),
        encoding="utf-8",
    )
    (run_dir / "split_manifest.json").write_text(
        json.dumps({"train": [], "val": ["p1"], "excluded_test": []}),
        encoding="utf-8",
    )
    (run_dir / "truth_intervals.json").write_text(
        json.dumps({"p1": [[0, 10]]}), encoding="utf-8"
    )
    (run_dir / "window_probabilities.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "participant": "p1",
                    "start_ms": start,
                    "end_ms": end,
                    "probability": probability,
                    "split": "val",
                }
            )
            for start, end, probability in ((0, 10, 0.9), (10, 20, 0.1), (30, 40, 0.9))
        )
        + "\n",
        encoding="utf-8",
    )

    assert hasattr(error_analysis, "analyze_m1_run")
    report = error_analysis.analyze_m1_run(run_dir, imu_dir, ppg_dir)

    assert report["false_positive_events"]["count"] == 1
    assert report["false_positive_events"]["duration_ms"]["median"] == 10.0
    assert report["false_positive_events"]["window_count"]["median"] == 1.0
    assert report["false_positive_events"]["interval_ms"]["previous_gap_median"] == 20.0
    assert report["false_positive_events"]["score"]["max_probability_median"] == 0.9
    assert report["modality_stratification"]["both"]["count"] == 3
    assert report["participant_metrics"]["p1"]["fp"] == 1
    assert report["gate_decision"]["m2"]["passed"] is True


def test_m1_analysis_rejects_mismatched_ppg_reference(tmp_path: Path):
    run_dir = tmp_path / "run"
    imu_dir = tmp_path / "imu"
    ppg_dir = tmp_path / "ppg"
    source = tmp_path / "organized" / "P1" / "sensor.txt"
    _write_cache(imu_dir / "imu.npz", source, ppg=False)
    _write_cache(ppg_dir / "ppg.npz", source, ppg=True, reference_hash="wrong")
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": "m1_imu_ppg",
                "model_mode": "fusion",
                "event_iou_threshold": 0.25,
                "label_positive_overlap": 0.25,
                "seed": 7,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "decoder.json").write_text(
        json.dumps({"threshold": 0.5, "merge_gap_ms": 0, "min_duration_ms": 0}),
        encoding="utf-8",
    )
    (run_dir / "split_manifest.json").write_text(
        json.dumps({"train": [], "val": ["p1"], "excluded_test": []}),
        encoding="utf-8",
    )
    (run_dir / "truth_intervals.json").write_text(
        json.dumps({"p1": [[0, 10]]}), encoding="utf-8"
    )
    (run_dir / "window_probabilities.jsonl").write_text(
        json.dumps(
            {
                "participant": "p1",
                "start_ms": 0,
                "end_ms": 10,
                "probability": 0.9,
                "split": "val",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(ValueError, match="reference"):
        error_analysis.analyze_m1_run(run_dir, imu_dir, ppg_dir)
