from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.probe_route2_cross_os_synthetic import _synthetic_model, build_payload


def test_cross_os_probe_fit_limit_matches_frozen_a2_004_config() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (root / "configs/a2-context-verifier-v1-004.json").read_text(encoding="utf-8")
    )

    _, _, fit_max_iter = _synthetic_model()

    assert fit_max_iter == config["verifier_hgb"]["max_iter"] == 100


def test_cross_os_probe_exposes_exact_synthetic_probability_vectors() -> None:
    payload = build_payload()
    numeric = payload["numeric"]
    probabilities = [float.fromhex(value) for value in numeric["verifier_probability_f64_hex"]]
    encoded = b"".join(struct.pack("<d", value) for value in probabilities)

    assert len(probabilities) == 200
    assert all(math.isfinite(value) for value in probabilities)
    assert hashlib.sha256(encoded).hexdigest() == numeric["verifier_probability_f64le_sha256"]
