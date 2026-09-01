from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Config:
    data_root: Path
    index_dir: Path
    train_dir: Path
    output_dir: Path
    resample_hz: int = 25
    window_sec: int = 15
    step_sec: int = 3
    seed: int = 7


def load_config(path: Path, **overrides: Any) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw.update({key: value for key, value in overrides.items() if value is not None})
    if "data_root" not in raw:
        raise ValueError("data_root must be provided by YAML or CLI")

    data_root = Path(raw["data_root"])
    cfg = Config(
        data_root=data_root,
        index_dir=Path(raw.get("index_dir", data_root / "01_dataset")),
        train_dir=Path(raw.get("train_dir", data_root / "02_traindataset")),
        output_dir=Path(raw.get("output_dir", "artifacts")),
        resample_hz=int(raw.get("resample_hz", 25)),
        window_sec=int(raw.get("window_sec", 15)),
        step_sec=int(raw.get("step_sec", 3)),
        seed=int(raw.get("seed", 7)),
    )
    if cfg.resample_hz not in {15, 16, 25, 50}:
        raise ValueError("resample_hz must be one of 15, 16, 25, 50")
    if cfg.window_sec <= 0 or cfg.step_sec <= 0 or cfg.step_sec > cfg.window_sec:
        raise ValueError("step_sec must be positive and no greater than window_sec")
    return cfg
