from __future__ import annotations

import json
from pathlib import Path

from scripts.probe_route2_cross_os_synthetic import _synthetic_model


def test_cross_os_probe_fit_limit_matches_frozen_a2_004_config() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (root / "configs/a2-context-verifier-v1-004.json").read_text(encoding="utf-8")
    )

    _, _, fit_max_iter = _synthetic_model()

    assert fit_max_iter == config["verifier_hgb"]["max_iter"] == 100
