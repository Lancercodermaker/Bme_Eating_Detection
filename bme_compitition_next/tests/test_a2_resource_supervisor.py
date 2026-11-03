from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from eating_event.a2.budget import (
    FitAttemptLedger,
    StudyLedger,
    StudyResourceError,
    check_study_family_disk_budget_003,
    compute_003_rss_ceiling,
    minimum_run_available_bytes,
)
from eating_event.a2.contracts import PREDECESSOR_FAMILY_001_002, STUDY_003_ID, load_config
from eating_event.a2.control import launch, supervise_worker


ROOT = Path(__file__).parents[1]
GIB = 1024**3


def _synthetic_predecessor(**changes: object) -> dict[str, object]:
    value = copy.deepcopy(PREDECESSOR_FAMILY_001_002)
    value.update(changes)
    return value


def _make_003_ledger(tmp_path: Path, predecessor: dict[str, object] | None = None) -> tuple[StudyLedger, Path, Path]:
    artifacts = tmp_path / "artifacts"
    output = artifacts / "a2-context-verifier-v1-003"
    output.mkdir(parents=True, exist_ok=True)
    _, digest = load_config(ROOT, study_id=STUDY_003_ID)
    summary = copy.deepcopy(PREDECESSOR_FAMILY_001_002 if predecessor is None else predecessor)
    ledger = StudyLedger(
        artifacts,
        output,
        limits=load_config(ROOT, study_id=STUDY_003_ID)[0]["limits"],
        study_id=STUDY_003_ID,
        predecessor=summary,
        config_sha256=digest,
    )
    ledger.append("predecessor", {"predecessor": summary})
    return ledger, artifacts, output


def _prepare_disk_family(root: Path, *, spool_bytes: int = 0) -> tuple[Path, tuple[Path, ...]]:
    artifacts = root / "artifacts"
    output_001 = artifacts / "a2-context-verifier-v1-001"
    output_002 = artifacts / "a2-context-verifier-v1-002"
    output_003 = artifacts / "a2-context-verifier-v1-003"
    for output in (output_001, output_002, output_003):
        output.mkdir(parents=True, exist_ok=True)
    (output_001 / "nested").mkdir()
    (output_001 / "nested" / "old.bin").write_bytes(b"a" * 100)
    (output_002 / "old.bin").write_bytes(b"b" * 200)
    (output_003 / "materialized").mkdir()
    (output_003 / "materialized" / "role-spool.jsonl").write_bytes(b"s" * spool_bytes)
    ledger_paths = (
        artifacts / "a2-study-budget.jsonl",
        artifacts / "a2-study-budget-v1-002.jsonl",
        artifacts / "a2-study-budget-v1-003.jsonl",
        artifacts / "a2-study-budget-v1-003.lock",
    )
    for index, path in enumerate(ledger_paths):
        path.write_bytes(bytes([65 + index]) * (10 + index))
    (output_001 / "a2-study-budget.jsonl").write_bytes(ledger_paths[0].read_bytes())
    (output_002 / "a2-study-budget.jsonl").write_bytes(ledger_paths[1].read_bytes())
    (output_003 / "a2-study-budget.jsonl").write_bytes(ledger_paths[2].read_bytes())
    return output_003, ledger_paths


def _prepare_synthetic_003_launch_root(root: Path) -> tuple[dict[str, object], str]:
    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "configs" / "a2-context-verifier-v1-003.json", config_dir / "a2-context-verifier-v1-003.json")
    shutil.copyfile(ROOT / "configs" / "a2-context-verifier-v1-003.sha256", config_dir / "a2-context-verifier-v1-003.sha256")
    config, digest = load_config(root, study_id=STUDY_003_ID)

    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    for suffix, ledger_name in (("001", "a2-study-budget.jsonl"), ("002", "a2-study-budget-v1-002.jsonl")):
        old_output = artifacts / f"a2-context-verifier-v1-{suffix}"
        old_output.mkdir()
        old_ledger = artifacts / ledger_name
        old_ledger.write_bytes(f"synthetic predecessor {suffix}\n".encode("ascii"))
        (old_output / "a2-study-budget.jsonl").write_bytes(old_ledger.read_bytes())
    return config, digest


def _synthetic_003_code_identity() -> dict[str, str]:
    return {"synthetic-a2-code.py": "c" * 64}


def _patch_synthetic_003_launch(monkeypatch, code_identity: dict[str, str]) -> None:
    import eating_event.a2.control as control

    monkeypatch.setattr(control, "verify_predecessor_family_002", lambda _root: copy.deepcopy(PREDECESSOR_FAMILY_001_002))
    monkeypatch.setattr(control, "current_a2_code_identity", lambda _root: code_identity)
    monkeypatch.setattr(control, "require_environment", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 8 * GIB)


def _write_synthetic_audit_ready(
    output: Path,
    config: dict[str, object],
    config_digest: str,
    code_identity: dict[str, str],
    *,
    forged: str | None = None,
) -> str:
    report = {
        "status": "AUDIT_READY",
        "study_id": STUDY_003_ID,
        "study_output": config["study_output"],
        "config_sha256": config_digest,
        "a2_code_identity": code_identity,
    }
    if forged == "report-config":
        report["config_sha256"] = "0" * 64
    if forged == "report-status":
        report["status"] = "COMPLETE"
    path = output / "audit-ready.json"
    path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar_digest = "0" * 64 if forged == "sidecar" else report_digest
    (output / "audit-ready.sha256").write_text(f"{sidecar_digest}  audit-ready.json\n", encoding="ascii")
    return report_digest if forged != "worker-hash" else "f" * 64


def _seed_synthetic_003_ready_state(
    root: Path,
    config: dict[str, object],
    config_digest: str,
    code_identity: dict[str, str],
) -> StudyLedger:
    artifacts = root / "artifacts"
    output = artifacts / "a2-context-verifier-v1-003"
    output.mkdir()
    report_digest = _write_synthetic_audit_ready(output, config, config_digest, code_identity)
    ledger = StudyLedger(
        artifacts,
        output,
        limits=config["limits"],
        study_id=STUDY_003_ID,
        predecessor=copy.deepcopy(PREDECESSOR_FAMILY_001_002),
        config_sha256=config_digest,
    )
    ledger.append("predecessor", {"predecessor": copy.deepcopy(PREDECESSOR_FAMILY_001_002)})
    ledger.append("startup_resources", {"startup_available_bytes": 8 * GIB, "rss_ceiling_bytes": 4 * GIB})
    ledger.mark_status("AUDIT_READY", audit_ready_sha256=report_digest)
    (output / "run-status.json").write_text(json.dumps({
        "status": "AUDIT_READY",
        "study_id": STUDY_003_ID,
        "study_output": config["study_output"],
        "config_sha256": config_digest,
        "audit_ready_sha256": report_digest,
    }), encoding="utf-8")
    return ledger


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (5 * GIB, (5 * GIB * 60) // 100),
        (6 * GIB, (6 * GIB * 60) // 100),
        (8 * GIB, 4 * GIB),
    ],
)
def test_003_rss_ceiling_uses_only_the_new_fixed_resource_rule(available: int, expected: int) -> None:
    assert compute_003_rss_ceiling(available) == expected


def test_003_rss_startup_floor_and_run_headroom_boundary_are_exact() -> None:
    with pytest.raises(StudyResourceError, match="5 GiB"):
        compute_003_rss_ceiling(5 * GIB - 1)
    ceiling = compute_003_rss_ceiling(8 * GIB)
    required = minimum_run_available_bytes(ceiling)

    assert required == max(5 * GIB, (ceiling * 100 + 59) // 60)
    with pytest.raises(StudyResourceError, match="headroom"):
        minimum_run_available_bytes(4 * GIB + 1)


def test_003_family_active_wall_counts_both_predecessors_and_blocks_at_exact_limit(tmp_path: Path) -> None:
    ledger, _, _ = _make_003_ledger(tmp_path)
    ledger.append("invocation_start", {"id": "audit-003", "mode": "audit", "monotonic": 10.0})
    local = 7200.0 - float(PREDECESSOR_FAMILY_001_002["active_wall_seconds"])
    ledger.append("invocation_end", {"id": "audit-003", "duration_seconds": local})

    assert ledger.active_wall_seconds() == pytest.approx(7200.0)
    with pytest.raises(StudyResourceError, match="wall"):
        ledger.assert_can_start_invocation()


def test_003_fit_wall_and_interrupted_reservations_include_synthetic_family_use(tmp_path: Path) -> None:
    predecessor = _synthetic_predecessor(
        active_wall_seconds=100.0,
        fit_wall_seconds=3599.0,
        verifier_fit_attempts=3,
    )
    ledger, _, _ = _make_003_ledger(tmp_path, predecessor)
    fits = FitAttemptLedger(ledger)

    assert fits.attempt_count() == 3
    assert fits.fit_wall_seconds() == pytest.approx(3599.0)
    for number in range(22):
        fits.reserve_fit(f"verifier/interrupted-{number}")
    assert fits.attempt_count() == 25
    assert fits.local_attempt_count() == 22
    assert ledger.limits["candidate_fits"] == 0
    assert ledger.limits["candidate_predicts"] == 0
    with pytest.raises(StudyResourceError, match="attempt"):
        fits.reserve_fit("verifier/forbidden-26")


def test_003_family_disk_recurses_through_both_predecessors_ledgers_lock_and_spool(tmp_path: Path) -> None:
    output, ledger_paths = _prepare_disk_family(tmp_path, spool_bytes=100)
    measured = check_study_family_disk_budget_003(
        tmp_path,
        output,
        ledger_paths,
        max_disk_bytes=100_000,
    )

    assert measured == 100 + 200 + 100 + sum(path.stat().st_size for path in ledger_paths) + sum(
        (output / "a2-study-budget.jsonl").stat().st_size
        for output in (
            tmp_path / "artifacts" / "a2-context-verifier-v1-001",
            tmp_path / "artifacts" / "a2-context-verifier-v1-002",
            tmp_path / "artifacts" / "a2-context-verifier-v1-003",
        )
    )
    with pytest.raises(StudyResourceError, match="disk"):
        check_study_family_disk_budget_003(tmp_path, output, ledger_paths, max_disk_bytes=measured - 1)


def test_003_low_memory_preflight_creates_no_study_path_or_reads_a1_sources(tmp_path: Path, monkeypatch) -> None:
    import eating_event.a2.audit as audit
    import eating_event.a2.control as control

    _, digest = _prepare_synthetic_003_launch_root(tmp_path)
    _patch_synthetic_003_launch(monkeypatch, _synthetic_003_code_identity())
    output = tmp_path / "artifacts" / "a2-context-verifier-v1-003"
    ledger = tmp_path / "artifacts" / "a2-study-budget-v1-003.jsonl"
    lock = tmp_path / "artifacts" / "a2-study-budget-v1-003.lock"
    for path in (output, ledger, lock):
        assert not path.exists()
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 5 * GIB - 1)

    def forbidden(*args, **kwargs):
        raise AssertionError("preflight accessed A1 source content")

    monkeypatch.setattr(audit, "authenticate_checksum_manifest", forbidden)
    result = launch("preflight", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_003_ID)

    assert result["status"] == "NOT_STARTED_INSUFFICIENT_HEADROOM"
    assert not any(path.exists() for path in (output, ledger, lock))


def test_003_low_run_headroom_preserves_ready_without_interval_or_fit(tmp_path: Path, monkeypatch) -> None:
    import eating_event.a2.control as control

    config, digest = load_config(ROOT, study_id=STUDY_003_ID)
    (tmp_path / "configs").mkdir()
    shutil.copyfile(ROOT / "configs" / "a2-context-verifier-v1-003.json", tmp_path / "configs" / "a2-context-verifier-v1-003.json")
    shutil.copyfile(ROOT / "configs" / "a2-context-verifier-v1-003.sha256", tmp_path / "configs" / "a2-context-verifier-v1-003.sha256")
    artifacts = tmp_path / "artifacts"
    output = artifacts / "a2-context-verifier-v1-003"
    output.mkdir(parents=True)
    external = artifacts / "a2-study-budget-v1-003.jsonl"
    lock = artifacts / "a2-study-budget-v1-003.lock"
    _, family_paths = _prepare_disk_family(tmp_path)
    # The helper created the fixed output and all three ledger paths; reset these
    # synthetic 003 ledger paths before seeding the legitimate ready state.
    external.write_bytes(b"")
    lock.unlink()
    (output / "a2-study-budget.jsonl").write_bytes(b"")
    predecessor = copy.deepcopy(PREDECESSOR_FAMILY_001_002)
    ledger = StudyLedger(artifacts, output, limits=config["limits"], study_id=STUDY_003_ID, predecessor=predecessor, config_sha256=digest)
    ledger.append("predecessor", {"predecessor": predecessor})
    ledger.append("startup_resources", {"startup_available_bytes": 8 * GIB, "rss_ceiling_bytes": 4 * GIB})
    (output / "audit-ready.json").write_text(json.dumps({
        "status": "AUDIT_READY",
        "study_id": STUDY_003_ID,
        "study_output": config["study_output"],
        "config_sha256": digest,
        "a2_code_identity": {"sentinel": "code"},
    }), encoding="utf-8")
    ready_bytes = (output / "audit-ready.json").read_bytes()
    ready_digest = hashlib.sha256(ready_bytes).hexdigest()
    (output / "audit-ready.sha256").write_text(ready_digest + "  audit-ready.json\n", encoding="ascii")
    ledger.mark_status("AUDIT_READY", audit_ready_sha256=ready_digest)
    (output / "run-status.json").write_text(json.dumps({
        "status": "AUDIT_READY",
        "study_id": STUDY_003_ID,
        "study_output": config["study_output"],
        "config_sha256": digest,
        "audit_ready_sha256": ready_digest,
    }), encoding="utf-8")
    monkeypatch.setattr(control, "verify_predecessor_family_002", lambda root: PREDECESSOR_FAMILY_001_002)
    monkeypatch.setattr(control, "current_a2_code_identity", lambda root: {"sentinel": "code"})
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 5 * GIB)

    before = external.read_bytes()
    result = launch("run", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_003_ID)

    assert result["status"] == "RUN_NOT_STARTED_INSUFFICIENT_HEADROOM", result
    assert ledger.current_status() == "AUDIT_READY"
    assert not any(row.get("mode") == "run" for row in ledger.records() if row["event"] == "invocation_start")
    assert FitAttemptLedger(ledger).attempt_count() == 0
    assert external.read_bytes() == before
    assert not lock.exists()


@pytest.mark.parametrize("available", [5 * GIB - 1, 5 * GIB])
def test_003_run_headroom_below_startup_floor_returns_run_status_and_preserves_ready(tmp_path: Path, monkeypatch, available: int) -> None:
    import eating_event.a2.control as control

    config, digest = _prepare_synthetic_003_launch_root(tmp_path)
    code_identity = _synthetic_003_code_identity()
    ledger = _seed_synthetic_003_ready_state(tmp_path, config, digest, code_identity)
    _patch_synthetic_003_launch(monkeypatch, code_identity)
    monkeypatch.setattr(control, "available_memory_bytes", lambda: available)
    output = tmp_path / "artifacts" / "a2-context-verifier-v1-003"
    external = tmp_path / "artifacts" / "a2-study-budget-v1-003.jsonl"
    lock = tmp_path / "artifacts" / "a2-study-budget-v1-003.lock"
    before = external.read_bytes()

    result = launch("run", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_003_ID)

    assert result["status"] == "RUN_NOT_STARTED_INSUFFICIENT_HEADROOM", result
    assert ledger.current_status() == "AUDIT_READY"
    assert not any(row.get("mode") == "run" for row in ledger.records() if row["event"] == "invocation_start")
    assert FitAttemptLedger(ledger).attempt_count() == 0
    assert external.read_bytes() == before
    assert not lock.exists()
    assert json.loads((output / "run-status.json").read_text(encoding="utf-8"))["status"] == "AUDIT_READY"


def test_003_valid_worker_audit_persists_hash_bound_ready_state(tmp_path: Path, monkeypatch) -> None:
    import eating_event.a2.control as control

    config, digest = _prepare_synthetic_003_launch_root(tmp_path)
    code_identity = _synthetic_003_code_identity()
    _patch_synthetic_003_launch(monkeypatch, code_identity)

    def fake_supervisor(command, output_dir, ledger, *, response_path, **_kwargs):
        report_digest = _write_synthetic_audit_ready(Path(output_dir), config, digest, code_identity)
        Path(response_path).write_text(json.dumps({
            "status": "AUDIT_READY",
            "study_id": STUDY_003_ID,
            "study_output": str(Path(output_dir).resolve()),
            "config_sha256": digest,
            "audit_ready_sha256": report_digest,
        }), encoding="utf-8")
        return {"returncode": 0, "elapsed_seconds": 0.25, "peak_rss_bytes": 1234, "study_bytes": 0}

    monkeypatch.setattr(control, "supervise_worker", fake_supervisor)

    result = launch("audit", tmp_path, config_digest=digest, study_notes="synthetic", study_id=STUDY_003_ID)

    output = tmp_path / "artifacts" / "a2-context-verifier-v1-003"
    ready_bytes = (output / "audit-ready.json").read_bytes()
    ready_digest = hashlib.sha256(ready_bytes).hexdigest()
    status = json.loads((output / "run-status.json").read_text(encoding="utf-8"))
    ledger = StudyLedger(
        tmp_path / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_003_ID,
        predecessor=copy.deepcopy(PREDECESSOR_FAMILY_001_002),
        config_sha256=digest,
    )
    ready_rows = [row for row in ledger.records() if row.get("event") == "study_status" and row.get("status") == "AUDIT_READY"]

    assert result["status"] == "AUDIT_READY", result
    assert status["status"] == "AUDIT_READY"
    assert status["audit_ready_sha256"] == ready_digest
    assert (output / "audit-ready.sha256").read_text(encoding="ascii").split()[0] == ready_digest
    assert ready_rows and all(row.get("audit_ready_sha256") == ready_digest for row in ready_rows)
    assert ledger.current_status() == "AUDIT_READY"
    assert sum(row.get("event") == "invocation_start" and row.get("mode") == "audit" for row in ledger.records()) == 1
    assert sum(row.get("event") == "invocation_start" and row.get("mode") == "run" for row in ledger.records()) == 0


@pytest.mark.parametrize("forged", ["sidecar", "worker-hash", "missing-worker-hash", "report-config", "report-status"])
def test_003_forged_worker_audit_evidence_never_marks_ready(tmp_path: Path, monkeypatch, forged: str) -> None:
    import eating_event.a2.control as control

    config, digest = _prepare_synthetic_003_launch_root(tmp_path)
    code_identity = _synthetic_003_code_identity()
    _patch_synthetic_003_launch(monkeypatch, code_identity)

    def fake_supervisor(_command, output_dir, _ledger, *, response_path, **_kwargs):
        report_digest = _write_synthetic_audit_ready(Path(output_dir), config, digest, code_identity, forged=forged)
        response = {
            "status": "AUDIT_READY",
            "study_id": STUDY_003_ID,
            "study_output": str(Path(output_dir).resolve()),
            "config_sha256": digest,
        }
        if forged != "missing-worker-hash":
            response["audit_ready_sha256"] = report_digest
        Path(response_path).write_text(json.dumps(response), encoding="utf-8")
        return {"returncode": 0, "elapsed_seconds": 0.25, "peak_rss_bytes": 1234, "study_bytes": 0}

    monkeypatch.setattr(control, "supervise_worker", fake_supervisor)

    result = launch("audit", tmp_path, config_digest=digest, study_notes="synthetic", study_id=STUDY_003_ID)

    output = tmp_path / "artifacts" / "a2-context-verifier-v1-003"
    status = json.loads((output / "run-status.json").read_text(encoding="utf-8"))
    ledger = StudyLedger(
        tmp_path / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_003_ID,
        predecessor=copy.deepcopy(PREDECESSOR_FAMILY_001_002),
        config_sha256=digest,
    )

    assert result["status"] != "AUDIT_READY", result
    assert status["status"] != "AUDIT_READY"
    assert ledger.current_status() != "AUDIT_READY"
    assert not any(row.get("event") == "study_status" and row.get("status") == "AUDIT_READY" for row in ledger.records())
    assert json.loads((output / "validation-stop-record.json").read_text(encoding="utf-8"))["audit_ready"] is False


def test_003_run_failure_stop_record_preserves_verified_audit_ready_history(tmp_path: Path, monkeypatch) -> None:
    import eating_event.a2.control as control

    config, digest = _prepare_synthetic_003_launch_root(tmp_path)
    code_identity = _synthetic_003_code_identity()
    ledger = _seed_synthetic_003_ready_state(tmp_path, config, digest, code_identity)
    _patch_synthetic_003_launch(monkeypatch, code_identity)

    def failed_run_worker(command, output_dir, _ledger, *, response_path, **_kwargs):
        Path(response_path).write_text(json.dumps({
            "status": "INVALID",
            "reason": "synthetic run failure before fit",
            "study_id": STUDY_003_ID,
            "study_output": str(Path(output_dir).resolve()),
            "config_sha256": digest,
        }), encoding="utf-8")
        return {"returncode": 2, "elapsed_seconds": 0.25, "peak_rss_bytes": 1234, "study_bytes": 0}

    monkeypatch.setattr(control, "supervise_worker", failed_run_worker)

    result = launch("run", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_003_ID)

    output = tmp_path / "artifacts" / "a2-context-verifier-v1-003"
    assert result["status"] == "INVALID", result
    stop = json.loads((output / "validation-stop-record.json").read_text(encoding="utf-8"))

    assert stop["status"] == "INVALID"
    assert stop["audit_calls"] == 0
    assert stop["run_calls"] == 1
    assert stop["audit_ready"] is True
    assert ledger.current_status() == "INVALID"
    assert FitAttemptLedger(ledger).attempt_count() == 0


def test_003_supervisor_persists_failing_sample_and_completed_stage_before_raising(tmp_path: Path, monkeypatch) -> None:
    ledger, _, output = _make_003_ledger(tmp_path)
    active_ledger_bytes = ledger.external_path.read_bytes()
    family_output, family_paths = _prepare_disk_family(tmp_path)
    # Reuse the same fixed 003 directory; the test helper's empty external ledger
    # is replaced by the active ledger's mirrored append-only pair.
    family_output.joinpath("a2-study-budget.jsonl").write_bytes(active_ledger_bytes)
    family_paths[2].write_bytes(active_ledger_bytes)
    progress = output / "worker-progress.json"
    worker_script = tmp_path / "fake-worker.py"
    worker_script.write_text(
        "import json, pathlib, time\n"
        "p=pathlib.Path(r'" + str(progress) + "')\n"
        "p.write_text(json.dumps({'last_completed_stage':'candidate_spool'}))\n"
        "time.sleep(10)\n",
        encoding="utf-8",
    )
    samples = iter([90, 101])

    def sample_tree(pid):
        value = next(samples)
        return {"root_pid": pid, "processes": [{"pid": pid, "rss_bytes": value}], "rss_bytes": value}

    monkeypatch.setattr("eating_event.a2.control._sample_worker_process_tree", sample_tree)
    terminate_calls: list[dict[str, object]] = []

    def terminate_after_persist(worker, process_error):
        segment_rows = [json.loads(line) for line in (output / "resource-segments.jsonl").read_text(encoding="utf-8").splitlines()]
        ledger_rows = ledger.records()
        terminate_calls.append({"segments": segment_rows, "ledger": ledger_rows})
        assert segment_rows[-1]["rss_bytes"] == 101
        assert segment_rows[-1]["last_completed_stage"] == "candidate_spool"
        assert ledger_rows[-1]["event"] == "resource_sample"
        assert ledger_rows[-1]["rss_bytes"] == 101
        worker.kill()
        worker.wait(timeout=5)

    monkeypatch.setattr("eating_event.a2.control._terminate_worker_tree", terminate_after_persist)
    with pytest.raises(StudyResourceError, match="RSS") as caught:
        supervise_worker(
            [sys.executable, str(worker_script)],
            output,
            ledger,
            response_path=output / "worker-response-audit.json",
            max_rss_bytes=100,
            max_disk_bytes=10**7,
            wall_deadline_seconds=10,
            sample_interval_seconds=0.4,
        )

    assert terminate_calls
    assert getattr(caught.value, "failing_measurement_bytes", None) == 101
    assert getattr(caught.value, "last_completed_stage", None) == "candidate_spool"
    assert ledger.records()[-1]["event"] == "resource_sample"
    assert (output / "a2-study-budget.jsonl").read_bytes() == ledger.external_path.read_bytes()
