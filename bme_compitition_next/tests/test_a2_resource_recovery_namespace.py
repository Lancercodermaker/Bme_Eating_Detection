from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from eating_event.a2.contracts import (
    A2_CONFIG,
    STUDY_001_ID,
    STUDY_002_ID,
    load_config,
    validate_config,
    validate_study_binding,
)
from eating_event.a2.budget import (
    StudyLedgerIntegrityError,
    validate_predecessor_family_summary,
    verify_predecessor_family_002,
)


ROOT = Path(__file__).parents[1]
STUDY_003 = "a2-context-verifier-v1-003"
ALLOWED_003_DIFFERENCES = {
    "study_id",
    "study_output",
    "ledger_path",
    "lock_path",
    "predecessor",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_003_config_is_fixed_and_scientific_projection_matches_002() -> None:
    config, digest = load_config(ROOT, study_id=STUDY_003)
    config_path = ROOT / "configs" / "a2-context-verifier-v1-003.json"
    sidecar = config_path.with_suffix(".sha256")
    old, old_digest = load_config(ROOT, study_id=STUDY_002_ID)

    assert digest == _sha(config_path)
    assert sidecar.read_text(encoding="ascii").split()[0] == digest
    assert config["study_id"] == STUDY_003
    assert config["study_output"] == "artifacts/a2-context-verifier-v1-003"
    assert config["ledger_path"] == "artifacts/a2-study-budget-v1-003.jsonl"
    assert config["lock_path"] == "artifacts/a2-study-budget-v1-003.lock"
    assert config["predecessor"] == verify_predecessor_family_002(ROOT)
    assert config["limits"]["rss_absolute_bytes"] == 4 * 1024**3
    assert config["limits"]["rss_min_startup_available_bytes"] == 5 * 1024**3
    assert config["limits"]["rss_startup_fraction"] == 0.6
    assert config["limits"]["active_wall_seconds"] == 7200
    assert config["limits"]["fit_wall_seconds"] == 3600
    assert config["limits"]["verifier_fit_attempts"] == 25
    assert config["limits"]["candidate_fits"] == 0
    assert config["limits"]["candidate_predicts"] == 0
    assert old_digest == "89d1a7697dadf3a92f1a2249a68d186ca3ffb48ad8b06697bf142f5952e78949"
    old_projection = copy.deepcopy(old)
    new_projection = copy.deepcopy(config)
    for key in ALLOWED_003_DIFFERENCES:
        old_projection.pop(key, None)
        new_projection.pop(key, None)
    old_projection["limits"].pop("rss_absolute_bytes")
    old_projection["limits"].pop("rss_startup_fraction")
    new_projection["limits"].pop("rss_absolute_bytes")
    new_projection["limits"].pop("rss_startup_fraction")
    new_projection["limits"].pop("rss_min_startup_available_bytes")
    assert new_projection == old_projection
    assert old["limits"]["rss_absolute_bytes"] == 8 * 1024**3
    assert A2_CONFIG["study_id"] == STUDY_001_ID
    assert _sha(ROOT / "configs" / "a2-context-verifier-v1.json") == "f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5"


@pytest.mark.parametrize(
    "path,value",
    [
        (("study_id",), "a2-context-verifier-v1-004"),
        (("study_output",), "artifacts/a2-context-verifier-v1-004"),
        (("source_checksum_sha256",), "0" * 64),
        (("verifier_thresholds", 0), 0.11),
        (("verifier_hgb", "max_iter"), 101),
        (("seed",), 123),
        (("min_duration_ms",), 180001),
        (("decode_fuse_ms",), 600001),
        (("nested_roles", "verifier_roles"), 24),
        (("limits", "verifier_fit_attempts"), 26),
        (("limits", "rss_absolute_bytes"), 5 * 1024**3),
    ],
)
def test_003_rejects_unapproved_identity_science_or_budget_changes(path, value) -> None:
    config, _ = load_config(ROOT, study_id=STUDY_003)
    changed = copy.deepcopy(config)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError):
        validate_config(changed, study_id=STUDY_003)


def test_003_rejects_unknown_ids_and_wrong_config_output_binding() -> None:
    config, digest = load_config(ROOT, study_id=STUDY_003)
    output = ROOT / str(config["study_output"])

    with pytest.raises(ValueError):
        load_config(ROOT, study_id="a2-context-verifier-v1-999")
    with pytest.raises(ValueError, match="output path"):
        validate_study_binding(ROOT, ROOT / "artifacts" / "wrong-output", study_id=STUDY_003, config_sha256=digest)
    with pytest.raises(ValueError, match="SHA"):
        validate_study_binding(ROOT, output, study_id=STUDY_003, config_sha256="0" * 64)


def test_dual_predecessor_evidence_recomputes_hashes_and_cumulative_use_read_only() -> None:
    evidence = verify_predecessor_family_002(ROOT)

    assert evidence["active_wall_seconds"] == pytest.approx(21.047000000005937)
    assert evidence["fit_wall_seconds"] == 0.0
    assert evidence["verifier_fit_attempts"] == 0
    assert [row["study_id"] for row in evidence["members"]] == [STUDY_001_ID, STUDY_002_ID]
    assert evidence["members"][0]["status"] == "INVALID"
    assert evidence["members"][1]["status"] == "INCOMPLETE_RESOURCE"
    assert evidence["members"][1]["run_calls"] == 0
    assert evidence["members"][1]["failing_measurement_bytes"] is None
    assert not (ROOT / "artifacts" / "a2-study-budget.lock").exists()
    assert not (ROOT / "artifacts" / "a2-study-budget-v1-002.lock").exists()


@pytest.mark.parametrize("field", ["active_wall_seconds", "fit_wall_seconds", "verifier_fit_attempts", "members"])
def test_dual_predecessor_summary_rejects_drift(field) -> None:
    evidence = verify_predecessor_family_002(ROOT)
    altered = copy.deepcopy(evidence)
    if field == "members":
        altered[field][1]["status"] = "COMPLETE"
    elif field == "active_wall_seconds":
        altered[field] += 0.001
    elif field == "fit_wall_seconds":
        altered[field] = 0.5
    else:
        altered[field] = 1

    with pytest.raises(StudyLedgerIntegrityError):
        validate_predecessor_family_summary(altered)


def test_003_runner_has_only_fixed_preflight_audit_run_modes_and_enters_code_identity() -> None:
    from eating_event.a2.audit import current_a2_code_identity

    runner = ROOT / "scripts" / "run_a2_context_verifier_003.py"
    identity = current_a2_code_identity(ROOT)
    source = runner.read_text(encoding="utf-8")

    assert "a2-context-verifier-v1-003" in source
    assert 'args[0] not in {"preflight", "audit", "run"}' in source
    assert "--study-id" not in source and "--output" not in source and "--rss" not in source
    assert "scripts/run_a2_context_verifier_003.py" in identity
    assert "tests/test_a2_resource_recovery_namespace.py" in identity


def test_003_entrypoints_bind_fixed_identity_before_any_source_read(tmp_path: Path) -> None:
    from eating_event.a2.audit import load_audited_corpus, run_audit, verify_audit_ready

    _, digest = load_config(ROOT, study_id=STUDY_003)
    wrong_output = tmp_path / "not-the-a2-003-output"
    for call in (
        lambda: run_audit(ROOT, wrong_output, config_sha256=digest, study_id=STUDY_003),
        lambda: verify_audit_ready(ROOT, wrong_output, expected_config_sha256=digest, study_id=STUDY_003),
        lambda: load_audited_corpus(ROOT, wrong_output, study_id=STUDY_003),
    ):
        with pytest.raises(ValueError, match="output path"):
            call()
