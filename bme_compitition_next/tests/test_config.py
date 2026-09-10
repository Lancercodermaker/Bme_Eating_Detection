from pathlib import Path

import pytest

from eating_event.config import load_config


def test_load_config_preserves_paths_and_numeric_contract(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    raw_root = tmp_path / "raw"
    metadata_root = tmp_path / "metadata"
    repository_root.mkdir()
    raw_root.mkdir()
    metadata_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                f"repository_root: '{repository_root.as_posix()}'",
                f"raw_data_root: '{raw_root.as_posix()}'",
                f"metadata_root: '{metadata_root.as_posix()}'",
                "window_seconds: 240",
                "step_seconds: 15",
                "min_coverage: 0.8",
                "imu_grid_hz: 10",
                "max_gap_seconds: 2.0",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.raw_data_root == raw_root.resolve()
    assert config.metadata_root == metadata_root.resolve()
    assert config.window_seconds == 240
    assert config.step_seconds == 15
    assert config.min_coverage == pytest.approx(0.8)
    assert config.imu_grid_hz == 10
    assert config.max_gap_seconds == pytest.approx(2.0)


def test_load_config_rejects_missing_raw_root(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    metadata_root = tmp_path / "metadata"
    repository_root.mkdir()
    metadata_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                f"repository_root: '{repository_root.as_posix()}'",
                f"raw_data_root: '{(tmp_path / 'missing').as_posix()}'",
                f"metadata_root: '{metadata_root.as_posix()}'",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="raw_data_root"):
        load_config(config_path)


def test_load_config_rejects_raw_root_inside_repository(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    (repository_root / "raw").mkdir()
    metadata_root = tmp_path / "metadata"
    metadata_root.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                f"repository_root: '{repository_root.as_posix()}'",
                f"raw_data_root: '{(repository_root / 'raw').as_posix()}'",
                f"metadata_root: '{metadata_root.as_posix()}'",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="inside repository"):
        load_config(config_path)

