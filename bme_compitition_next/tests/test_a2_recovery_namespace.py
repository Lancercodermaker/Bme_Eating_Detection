from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from eating_event.a2.contracts import A2_CONFIG, PREDECESSOR_001, load_config, validate_config, validate_study_binding
from eating_event.a2.budget import (
    FitAttemptLedger,
    StudyLedger,
    StudyResourceError,
    check_study_family_disk_budget,
    compute_rss_ceiling,
    validate_predecessor_summary,
    verify_predecessor_001,
)


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


def test_002_runner_is_in_the_frozen_a2_code_identity() -> None:
    from eating_event.a2.audit import current_a2_code_identity

    identity = current_a2_code_identity(ROOT)

    assert "scripts/run_a2_context_verifier_002.py" in identity


def _make_002_ledger(tmp_path: Path, predecessor=None):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    output = artifacts / "a2-context-verifier-v1-002"
    output.mkdir(exist_ok=True)
    source = copy.deepcopy(PREDECESSOR_001 if predecessor is None else predecessor)
    _, config_digest = load_config(ROOT, study_id=STUDY_002)
    ledger = StudyLedger(
        artifacts,
        output,
        study_id=STUDY_002,
        predecessor=source,
        config_sha256=config_digest,
    )
    ledger.append("predecessor", {"predecessor": source})
    return ledger, artifacts, output


def test_002_ledger_requires_and_binds_fixed_config_identity(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    output = artifacts / "a2-context-verifier-v1-002"
    artifacts.mkdir()
    output.mkdir()
    with pytest.raises(ValueError, match="config SHA"):
        StudyLedger(artifacts, output, study_id=STUDY_002, predecessor=PREDECESSOR_001)

    _, digest = load_config(ROOT, study_id=STUDY_002)
    ledger = StudyLedger(
        artifacts,
        output,
        study_id=STUDY_002,
        predecessor=PREDECESSOR_001,
        config_sha256=digest,
    )
    ledger.append("predecessor", {"predecessor": PREDECESSOR_001})
    row = ledger.records()[0]
    assert row["study_id"] == STUDY_002
    assert row["study_output"] == "artifacts/a2-context-verifier-v1-002"
    assert row["config_sha256"] == digest
    assert row["predecessor"] == PREDECESSOR_001

    changed = dict(row, config_sha256="0" * 64)
    payload = (json.dumps(changed, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    ledger.external_path.write_bytes(payload)
    ledger.mirror_path.write_bytes(payload)
    with pytest.raises(ValueError, match="identity"):
        ledger.records()


def test_001_terminal_ledger_and_002_namespace_are_isolated(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    old_output = artifacts / "a2-context-verifier-v1-001"
    new_output = artifacts / "a2-context-verifier-v1-002"
    old_output.mkdir()
    new_output.mkdir()
    old = StudyLedger(artifacts, old_output)
    old.append("study_status", {"status": "INVALID"})

    with pytest.raises(ValueError, match="terminal"):
        old.assert_can_start_run()
    new, _, _ = _make_002_ledger(tmp_path)
    assert new.external_path == artifacts / "a2-study-budget-v1-002.jsonl"
    assert new.mirror_path == new_output / "a2-study-budget.jsonl"
    assert new.lock_path == artifacts / "a2-study-budget-v1-002.lock"
    assert old.external_path == artifacts / "a2-study-budget.jsonl"


def test_002_missing_output_or_one_ledger_copy_is_fail_closed(tmp_path: Path) -> None:
    _, digest = load_config(ROOT, study_id=STUDY_002)
    ledger, artifacts, output = _make_002_ledger(tmp_path)
    output.rename(artifacts / "renamed-output")
    with pytest.raises(ValueError, match="study output"):
        StudyLedger(artifacts, output, study_id=STUDY_002, predecessor=PREDECESSOR_001, config_sha256=digest)

    other, artifacts2, output2 = _make_002_ledger(tmp_path / "other")
    other.external_path.unlink()
    with pytest.raises(ValueError, match="ledger mirror"):
        StudyLedger(artifacts2, output2, study_id=STUDY_002, predecessor=PREDECESSOR_001, config_sha256=digest)


def test_002_active_wall_includes_predecessor_and_exact_limit_blocks_next_invocation(tmp_path: Path) -> None:
    ledger, _, _ = _make_002_ledger(tmp_path)
    ledger.append("invocation_start", {"id": "audit-002", "mode": "audit", "monotonic": 10.0})
    ledger.append("invocation_end", {"id": "audit-002", "duration_seconds": 7196.5})

    assert ledger.active_wall_seconds() == pytest.approx(7200.0)
    with pytest.raises(StudyResourceError, match="wall"):
        ledger.assert_can_start_invocation()


def test_002_fit_wall_and_attempts_include_nonzero_synthetic_predecessor(tmp_path: Path) -> None:
    predecessor = copy.deepcopy(PREDECESSOR_001)
    predecessor.update({"active_wall_seconds": 11.0, "fit_wall_seconds": 17.5, "verifier_fit_attempts": 2})
    ledger, _, _ = _make_002_ledger(tmp_path, predecessor)
    fits = FitAttemptLedger(ledger)

    assert fits.attempt_count() == 2
    assert fits.fit_wall_seconds() == pytest.approx(17.5)
    fits.reserve_fit("verifier/test")
    assert fits.attempt_count() == 3
    assert ledger.records()[-1]["attempt"] == 3


def test_002_rss_ceiling_is_capped_by_the_frozen_predecessor() -> None:
    assert compute_rss_ceiling(8 * 1024**3) == min(8 * 1024**3, 2127893299, int(8 * 1024**3 * 0.60))
    assert compute_rss_ceiling(1024**3) == int(1024**3 * 0.60)


def test_002_family_disk_budget_recurses_into_001_and_002_and_counts_ledgers(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    old_output = artifacts / "a2-context-verifier-v1-001"
    new_output = artifacts / "a2-context-verifier-v1-002"
    old_output.mkdir(parents=True)
    new_output.mkdir()
    (old_output / "nested").mkdir()
    (old_output / "nested" / "old.bin").write_bytes(b"o" * 100)
    old_external = artifacts / "a2-study-budget.jsonl"
    old_external.write_bytes(b"l" * 20)
    (new_output / "new.bin").write_bytes(b"n" * 100)
    new_external = artifacts / "a2-study-budget-v1-002.jsonl"
    new_lock = artifacts / "a2-study-budget-v1-002.lock"
    new_external.write_bytes(b"e" * 20)
    new_lock.write_bytes(b"k" * 5)

    measured = check_study_family_disk_budget(tmp_path, new_output, (new_external, new_lock), max_disk_bytes=245)
    assert measured == 245
    with pytest.raises(StudyResourceError, match="disk"):
        check_study_family_disk_budget(tmp_path, new_output, (new_external, new_lock), max_disk_bytes=244)


def test_002_study_binding_rejects_hash_id_and_output_mismatch_before_source_reads() -> None:
    config, digest = load_config(ROOT, study_id=STUDY_002)
    output = ROOT / str(config["study_output"])
    with pytest.raises(ValueError, match="SHA"):
        validate_study_binding(ROOT, output, study_id=STUDY_002, config_sha256="0" * 64)
    with pytest.raises(ValueError, match="output path"):
        validate_study_binding(ROOT, ROOT / "artifacts" / "elsewhere", study_id=STUDY_002, config_sha256=digest)
    with pytest.raises(ValueError):
        validate_study_binding(ROOT, output, study_id=STUDY_001, config_sha256=digest)


def test_predecessor_evidence_recomputes_all_frozen_001_values_read_only() -> None:
    evidence = verify_predecessor_001(ROOT)

    assert evidence == PREDECESSOR_001


@pytest.mark.parametrize("key,value", [
    ("run_status_sha256", "0" * 64),
    ("external_ledger_sha256", "1" * 64),
    ("output_tree_sha256", "2" * 64),
    ("active_wall_seconds", 0.0),
    ("rss_ceiling_bytes", 1),
])
def test_predecessor_hash_budget_or_rss_drift_fails_closed(key, value) -> None:
    altered = copy.deepcopy(PREDECESSOR_001)
    altered[key] = value

    with pytest.raises(ValueError, match="predecessor"):
        validate_predecessor_summary(altered)


def test_each_002_data_entrypoint_rejects_wrong_identity_before_reading_sources(tmp_path: Path) -> None:
    from eating_event.a2.audit import load_audited_corpus, run_audit, verify_audit_ready

    _, digest = load_config(ROOT, study_id=STUDY_002)
    wrong_output = tmp_path / "not-the-a2-output"
    with pytest.raises(ValueError, match="output path"):
        run_audit(ROOT, wrong_output, config_sha256=digest, study_id=STUDY_002)
    with pytest.raises(ValueError, match="output path"):
        verify_audit_ready(ROOT, wrong_output, expected_config_sha256=digest, study_id=STUDY_002)
    with pytest.raises(ValueError, match="output path"):
        load_audited_corpus(ROOT, wrong_output, study_id=STUDY_002)


def test_worker_request_is_bound_to_the_study_config_and_output(tmp_path: Path, monkeypatch) -> None:
    import sys

    from eating_event.a2.worker import main as worker_main

    _, digest = load_config(ROOT, study_id=STUDY_002)
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    request_path.write_text(json.dumps({
        "mode": "audit",
        "study_id": STUDY_002,
        "workspace": str(ROOT),
        "output": str(tmp_path / "wrong-output"),
        "config_sha256": digest,
        "response": str(response_path),
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["worker", str(request_path)])
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        monkeypatch.setenv(variable, "4")

    assert worker_main() != 0
    response = json.loads(response_path.read_text(encoding="utf-8"))
    assert response["status"] == "INVALID"
    assert "output path" in response["reason"]
