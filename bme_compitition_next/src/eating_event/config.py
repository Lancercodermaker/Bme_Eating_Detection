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
    window_seconds: float = 15.0
    step_seconds: float = 7.5
    min_coverage: float = 0.8
    imu_grid_hz: int = 10
    max_gap_seconds: float = 2.0
    local_window_seconds: float = 15.0
    local_step_seconds: float = 7.5
    coarse_window_seconds: float = 240.0
    coarse_step_seconds: float = 15.0
    use_coarse_context: bool = False
    feature_schema_version: str = "imu_stats_v1"
    label_schema_version: str = "window_event_labels_v1"
    raw_chunk_size: int = 200000
    host_memory_fraction: float = 0.60
    gpu_memory_limit_gb: float = 7.0
    audit_timeout_seconds: int = 1800
    cache_timeout_seconds: int = 21600
    fit_timeout_seconds: int = 7200


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


def _bounded_fraction(values: Mapping[str, Any], key: str, default: float) -> float:
    value = _positive_float(values, key, default)
    if value > 1.0:
        raise ValueError(f"{key} must be at most 1")
    return value


def _schema_version(values: Mapping[str, Any], key: str, default: str) -> str:
    value = values.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _bool_value(values: Mapping[str, Any], key: str, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


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

    window_seconds = _positive_float(values, "window_seconds", 15.0)
    step_seconds = _positive_float(values, "step_seconds", 7.5)
    if step_seconds > window_seconds:
        raise ValueError("step_seconds cannot exceed window_seconds")
    min_coverage = _positive_float(values, "min_coverage", 0.8)
    if min_coverage > 1.0:
        raise ValueError("min_coverage cannot exceed 1")
    local_window_seconds = _positive_float(values, "local_window_seconds", 15.0)
    local_step_seconds = _positive_float(values, "local_step_seconds", 7.5)
    if local_step_seconds > local_window_seconds:
        raise ValueError("local_step_seconds cannot exceed local_window_seconds")
    coarse_window_seconds = _positive_float(values, "coarse_window_seconds", 240.0)
    coarse_step_seconds = _positive_float(values, "coarse_step_seconds", 15.0)
    if coarse_step_seconds > coarse_window_seconds:
        raise ValueError("coarse_step_seconds cannot exceed coarse_window_seconds")

    return ProjectConfig(
        repository_root=repository_root,
        raw_data_root=raw_data_root,
        metadata_root=metadata_root,
        window_seconds=window_seconds,
        step_seconds=step_seconds,
        min_coverage=min_coverage,
        imu_grid_hz=_positive_int(values, "imu_grid_hz", 10),
        max_gap_seconds=_positive_float(values, "max_gap_seconds", 2.0),
        local_window_seconds=local_window_seconds,
        local_step_seconds=local_step_seconds,
        coarse_window_seconds=coarse_window_seconds,
        coarse_step_seconds=coarse_step_seconds,
        use_coarse_context=_bool_value(values, "use_coarse_context", False),
        feature_schema_version=_schema_version(values, "feature_schema_version", "imu_stats_v1"),
        label_schema_version=_schema_version(values, "label_schema_version", "window_event_labels_v1"),
        raw_chunk_size=_positive_int(values, "raw_chunk_size", 200000),
        host_memory_fraction=_bounded_fraction(values, "host_memory_fraction", 0.60),
        gpu_memory_limit_gb=_positive_float(values, "gpu_memory_limit_gb", 7.0),
        audit_timeout_seconds=_positive_int(values, "audit_timeout_seconds", 1800),
        cache_timeout_seconds=_positive_int(values, "cache_timeout_seconds", 21600),
        fit_timeout_seconds=_positive_int(values, "fit_timeout_seconds", 7200),
    )
