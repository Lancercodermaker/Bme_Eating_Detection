"""Validated configuration for reproducible local experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class ProjectConfig:
    repository_root: Path
    raw_data_root: Path
    metadata_root: Path
    window_seconds: int = 240
    step_seconds: int = 15
    min_coverage: float = 0.8
    imu_grid_hz: int = 10
    max_gap_seconds: float = 2.0


def _path_value(values: Mapping[str, Any], key: str) -> Path:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty path string")
    return Path(value).expanduser().resolve()


def _positive_int(values: Mapping[str, Any], key: str, default: int) -> int:
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _positive_float(values: Mapping[str, Any], key: str, default: float) -> float:
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


def load_config(path: str | Path) -> ProjectConfig:
    """Load and validate one YAML configuration file.

    Raw data must live outside the repository so that a full dataset cannot be
    accidentally copied into source control or experiment artifacts.
    """

    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, Mapping):
        raise ValueError("configuration must be a YAML mapping")

    repository_root = _path_value(values, "repository_root")
    raw_data_root = _path_value(values, "raw_data_root")
    metadata_root = _path_value(values, "metadata_root")
    if not repository_root.is_dir():
        raise FileNotFoundError(f"repository_root does not exist: {repository_root}")
    if not raw_data_root.is_dir():
        raise FileNotFoundError(f"raw_data_root does not exist: {raw_data_root}")
    if not metadata_root.is_dir():
        raise FileNotFoundError(f"metadata_root does not exist: {metadata_root}")
    if raw_data_root.is_relative_to(repository_root):
        raise ValueError("raw_data_root is inside repository")

    window_seconds = _positive_int(values, "window_seconds", 240)
    step_seconds = _positive_int(values, "step_seconds", 15)
    if step_seconds > window_seconds:
        raise ValueError("step_seconds cannot exceed window_seconds")
    min_coverage = _positive_float(values, "min_coverage", 0.8)
    if min_coverage > 1.0:
        raise ValueError("min_coverage cannot exceed 1")

    return ProjectConfig(
        repository_root=repository_root,
        raw_data_root=raw_data_root,
        metadata_root=metadata_root,
        window_seconds=window_seconds,
        step_seconds=step_seconds,
        min_coverage=min_coverage,
        imu_grid_hz=_positive_int(values, "imu_grid_hz", 10),
        max_gap_seconds=_positive_float(values, "max_gap_seconds", 2.0),
    )

