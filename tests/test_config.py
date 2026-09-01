from pathlib import Path

import pytest

from eating_detection.config import load_config


def test_cli_path_overrides_yaml(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        "data_root: old\nresample_hz: 25\nwindow_sec: 15\nstep_sec: 3\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file, data_root=tmp_path / "data", resample_hz=16)
    assert cfg.data_root == tmp_path / "data"
    assert cfg.resample_hz == 16
    assert cfg.window_sec == 15


def test_invalid_window_is_rejected(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text("data_root: data\nwindow_sec: 2\nstep_sec: 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="step_sec"):
        load_config(cfg_file)


def test_cache_processing_options_are_loaded(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        "data_root: data\ncache_dir: cache/features\nmax_gap_ms: 1500\n"
        "preprocess_variant: p1_lowpass_dynamic\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.cache_dir == Path("cache/features")
    assert cfg.max_gap_ms == 1500
    assert cfg.preprocess_variant == "p1_lowpass_dynamic"
