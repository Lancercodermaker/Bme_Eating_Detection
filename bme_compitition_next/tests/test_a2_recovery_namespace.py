from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from eating_event.a2.contracts import A2_CONFIG, load_config, validate_config


ROOT = Path(__file__).parents[1]
STUDY_001 = "a2-context-verifier-v1-001"
STUDY_002 = "a2-context-verifier-v1-002"
ALLOWED_002_DIFFERENCES = {"study_id", "study_output", "ledger_path", "lock_path", "predecessor"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_001_config_remains_the_default_and_its_frozen_bytes_are_unchanged() -> None:
    config, digest = load_config(ROOT)

    assert config == A2_CONFIG
    assert digest == "f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5"
    sidecar = (ROOT / "configs" / "a2-context-verifier-v1.sha256").read_text(encoding="ascii").split()[0]
    assert sidecar == digest


def test_002_config_is_a_new_allowlisted_namespace_with_identical_science() -> None:
    config, digest = load_config(ROOT, study_id=STUDY_002)
    old = copy.deepcopy(A2_CONFIG)

    assert digest == _sha(ROOT / "configs" / "a2-context-verifier-v1-002.json")
    assert config["study_id"] == STUDY_002
    assert config["study_output"] == "artifacts/a2-context-verifier-v1-002"
    assert config["ledger_path"] == "artifacts/a2-study-budget-v1-002.jsonl"
    assert config["lock_path"] == "artifacts/a2-study-budget-v1-002.lock"
    assert set(config) - set(old) == ALLOWED_002_DIFFERENCES - {"study_id", "study_output"}
    for key in ALLOWED_002_DIFFERENCES:
        old.pop(key, None)
    normalized = {key: value for key, value in config.items() if key not in ALLOWED_002_DIFFERENCES}
    assert normalized == old


@pytest.mark.parametrize(
    "path,value",
    [
        (("feature_dim",), 27),
        (("context_feature_names", 0), "changed"),
        (("verifier_hgb", "max_iter"), 101),
        (("nested_roles", "outer_folds"), 4),
        (("verifier_thresholds", 0), 0.11),
        (("min_duration_ms",), 181000),
        (("decode_fuse_ms",), 601000),
        (("seed",), 3),
        (("source_checksum_sha256",), "0" * 64),
        (("limits", "verifier_fit_attempts"), 26),
    ],
)
def test_002_rejects_any_change_to_frozen_scientific_fields(path, value) -> None:
    config, _ = load_config(ROOT, study_id=STUDY_002)
    changed = copy.deepcopy(config)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError):
        validate_config(changed, study_id=STUDY_002)


def test_002_rejects_unknown_namespace_and_modified_predecessor() -> None:
    config, _ = load_config(ROOT, study_id=STUDY_002)
    with pytest.raises(ValueError):
        load_config(ROOT, study_id="a2-context-verifier-v1-003")
    with pytest.raises(ValueError):
        validate_config({**config, "study_output": "artifacts/elsewhere"}, study_id=STUDY_002)


def test_002_runner_is_a_fixed_two_command_entry_point() -> None:
    runner = ROOT / "scripts" / "run_a2_context_verifier_002.py"
    assert runner.is_file()
    source = runner.read_text(encoding="utf-8")
    assert "a2-context-verifier-v1-002" in source
    assert 'args[0] not in {"audit", "run"}' in source
    assert "output_dir" not in source and "--study-id" not in source
