from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import multiprocessing
from pathlib import Path
import sys
import time

import pytest

from eating_event.a2 import budget
from eating_event.a2.contracts import STUDY_003_ID, STUDY_004_ID, load_config, validate_config


ROOT = Path(__file__).parents[1]
STUDY_004 = "a2-context-verifier-v1-004"
ALLOWED_004_DIFFERENCES = {
    "study_id",
    "study_output",
    "ledger_path",
    "lock_path",
    "predecessor",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _append_concurrent_004_ledger_record(
    config_root: str,
    workspace: str,
    writer: str,
    external_written,
    second_ready,
) -> None:
    config, digest = load_config(config_root, study_id=STUDY_004_ID)
    output = Path(workspace) / "artifacts" / "a2-context-verifier-v1-004"
    ledger = budget.StudyLedger(
        Path(workspace) / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_004_ID,
        predecessor=config["predecessor"],
        config_sha256=digest,
    )
    if writer == "first":
        append = budget._append_fsynced

        def delay_between_copies(path: Path, row: dict[str, object]) -> None:
            append(path, row)
            if Path(path).resolve() == ledger.external_path.resolve():
                external_written.set()
                time.sleep(0.25)

        budget._append_fsynced = delay_between_copies
    else:
        second_ready.set()
        if not external_written.wait(10):
            raise TimeoutError("first writer did not append the external ledger")
    ledger.append("synthetic_concurrent", {"writer": writer})


def test_004_concurrent_parent_and_worker_ledger_writes_preserve_mirror_order(tmp_path: Path) -> None:
    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    artifacts = tmp_path / "artifacts"
    output = artifacts / "a2-context-verifier-v1-004"
    artifacts.mkdir()
    output.mkdir()
    (artifacts / "a2-study-budget-v1-004.lock").write_bytes(b"pid=synthetic mode=run\n")
    ledger = budget.StudyLedger(
        artifacts,
        output,
        limits=config["limits"],
        study_id=STUDY_004_ID,
        predecessor=config["predecessor"],
        config_sha256=digest,
    )
    ledger.append("predecessor", {"predecessor": config["predecessor"]})

    context = multiprocessing.get_context("spawn")
    external_written = context.Event()
    second_ready = context.Event()
    first = context.Process(
        target=_append_concurrent_004_ledger_record,
        args=(str(ROOT), str(tmp_path), "first", external_written, second_ready),
    )
    second = context.Process(
        target=_append_concurrent_004_ledger_record,
        args=(str(ROOT), str(tmp_path), "second", external_written, second_ready),
    )
    second.start()
    assert second_ready.wait(10)
    first.start()
    assert external_written.wait(10)
    first.join(15)
    second.join(15)
    if first.is_alive():
        first.terminate()
        first.join()
    if second.is_alive():
        second.terminate()
        second.join()

    assert first.exitcode == 0
    assert second.exitcode == 0
    external = artifacts / "a2-study-budget-v1-004.jsonl"
    mirror = output / "a2-study-budget.jsonl"
    assert external.read_bytes() == mirror.read_bytes()
    assert sum(row["event"] == "synthetic_concurrent" for row in ledger.records()) == 2


def test_004_audit_lock_loser_does_not_unlink_the_winner_lock(tmp_path: Path, monkeypatch) -> None:
    from eating_event.a2 import control

    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    output = artifacts / "a2-context-verifier-v1-004"
    lock = artifacts / "a2-study-budget-v1-004.lock"
    identity = {"synthetic.py": "a" * 64}
    preflight = {"status": "PREFLIGHT_READY", "predecessor": config["predecessor"]}
    monkeypatch.setattr(
        control,
        "_a2_004_read_only_preflight",
        lambda *_args, **_kwargs: (preflight, config, output, identity),
    )
    winner_bytes = b"pid=winner mode=audit\n"

    def another_invocation_won(path: Path, _mode: str) -> None:
        path.write_bytes(winner_bytes)
        raise budget.StudyLedgerIntegrityError("A2-004 lock exists; this study cannot be resumed or retried")

    monkeypatch.setattr(control, "_create_004_lock", another_invocation_won)

    result = control.launch("audit", tmp_path, config_digest=digest, study_notes="synthetic", study_id=STUDY_004_ID)

    assert result["status"] == "NOT_STARTED_GATE_FAILED"
    assert lock.read_bytes() == winner_bytes
    assert not output.exists()


def test_004_owner_aware_cleanup_preserves_a_replaced_lock(tmp_path: Path) -> None:
    from eating_event.a2.control import _unlink_004_lock_if_owned

    lock = tmp_path / "a2-study-budget-v1-004.lock"
    replacement = b"pid=other mode=run token=other-owner\n"
    lock.write_bytes(replacement)

    _unlink_004_lock_if_owned(lock, "original-owner")

    assert lock.read_bytes() == replacement


def test_004_config_is_fixed_and_science_matches_003_except_disk_cap() -> None:
    config, digest = load_config(ROOT, study_id=STUDY_004)
    config_path = ROOT / "configs" / "a2-context-verifier-v1-004.json"
    sidecar = config_path.with_suffix(".sha256")
    predecessor, _ = load_config(ROOT, study_id=STUDY_003_ID)

    assert digest == _sha(config_path)
    assert sidecar.read_text(encoding="ascii").split()[0] == digest
    assert config["study_id"] == STUDY_004
    assert config["study_output"] == "artifacts/a2-context-verifier-v1-004"
    assert config["ledger_path"] == "artifacts/a2-study-budget-v1-004.jsonl"
    assert config["lock_path"] == "artifacts/a2-study-budget-v1-004.lock"
    assert config["limits"]["disk_bytes"] == int(1.5 * 1024**3)
    assert config["limits"]["candidate_fits"] == 0
    assert config["limits"]["candidate_predicts"] == 0
    assert config["limits"]["verifier_fit_attempts"] == 25
    assert config["predecessor"]["active_wall_seconds"] == pytest.approx(144.688)

    baseline = copy.deepcopy(predecessor)
    actual = copy.deepcopy(config)
    for key in ALLOWED_004_DIFFERENCES:
        baseline.pop(key, None)
        actual.pop(key, None)
    baseline["limits"].pop("disk_bytes")
    actual["limits"].pop("disk_bytes")
    assert actual == baseline


def test_004_rejects_changes_to_science_or_fixed_disk_cap() -> None:
    config, _ = load_config(ROOT, study_id=STUDY_004)
    for path, value in [
        (("feature_dim",), 27),
        (("verifier_thresholds", 0), 0.11),
        (("verifier_hgb", "max_iter"), 101),
        (("limits", "disk_bytes"), 1024**3),
        (("limits", "verifier_fit_attempts"), 26),
        (("nested_roles", "outer_folds"), 4),
    ]:
        changed = copy.deepcopy(config)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValueError):
            validate_config(changed, study_id=STUDY_004)


def test_003_predecessor_family_is_reauthenticated_from_fixed_files_and_archive() -> None:
    verify = getattr(budget, "verify_predecessor_family_003", None)
    assert callable(verify)

    predecessor = verify(ROOT)

    assert predecessor["schema"] == "a2_predecessor_family_v1"
    assert [row["study_id"] for row in predecessor["members"]] == [
        "a2-context-verifier-v1-001",
        "a2-context-verifier-v1-002",
        STUDY_003_ID,
    ]
    assert [row["status"] for row in predecessor["members"]] == [
        "INVALID",
        "INCOMPLETE_RESOURCE",
        "INVALID",
    ]
    assert predecessor["active_wall_seconds"] == pytest.approx(144.688)
    assert predecessor["fit_wall_seconds"] == 0.0
    assert predecessor["verifier_fit_attempts"] == 0
    assert predecessor["audit_calls"] == 3
    assert predecessor["run_calls"] == 0
    assert predecessor["members"][2]["output_tree_files"] == 164
    assert predecessor["members"][2]["output_tree_bytes"] == 339692500


def _make_004_family_disk_fixture(root: Path) -> tuple[Path, Path, Path]:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True)
    for suffix in ("001", "002", "003"):
        output = artifacts / f"a2-context-verifier-v1-{suffix}"
        output.mkdir()
        payload = (json.dumps({"event": f"synthetic_{suffix}"}) + "\n").encode("ascii")
        external = artifacts / ("a2-study-budget.jsonl" if suffix == "001" else f"a2-study-budget-v1-{suffix}.jsonl")
        external.write_bytes(payload)
        (output / "a2-study-budget.jsonl").write_bytes(payload)
    output_004 = artifacts / "a2-context-verifier-v1-004"
    output_004.mkdir()
    external_004 = artifacts / "a2-study-budget-v1-004.jsonl"
    payload_004 = (json.dumps({"event": "synthetic_004"}) + "\n").encode("ascii")
    external_004.write_bytes(payload_004)
    (output_004 / "a2-study-budget.jsonl").write_bytes(payload_004)
    lock_004 = artifacts / "a2-study-budget-v1-004.lock"
    lock_004.write_bytes(b"lock\n")
    return output_004, external_004, lock_004


def test_004_family_disk_budget_counts_all_predecessors_and_enforces_cap(tmp_path: Path) -> None:
    measure = getattr(budget, "check_study_family_disk_budget_004", None)
    assert callable(measure)
    output, external, lock = _make_004_family_disk_fixture(tmp_path)

    total = measure(tmp_path, output, (external, lock), max_disk_bytes=10_000)

    expected = sum(path.stat().st_size for path in (tmp_path / "artifacts").rglob("*") if path.is_file())
    assert total == expected
    with pytest.raises(budget.StudyResourceError, match="disk budget exceeded"):
        measure(tmp_path, output, (external, lock), max_disk_bytes=total - 1)
    external.unlink()
    (output / "a2-study-budget.jsonl").unlink()
    with pytest.raises(budget.StudyLedgerIntegrityError, match="A2-004 external/mirror ledger is missing"):
        measure(tmp_path, output, (external, lock), max_disk_bytes=10_000)


def test_004_family_disk_budget_fails_closed_for_missing_003_output(tmp_path: Path) -> None:
    measure = getattr(budget, "check_study_family_disk_budget_004", None)
    assert callable(measure)
    output, external, lock = _make_004_family_disk_fixture(tmp_path)
    (tmp_path / "artifacts" / "a2-context-verifier-v1-003" / "a2-study-budget.jsonl").unlink()

    with pytest.raises(budget.StudyLedgerIntegrityError, match="003|predecessor"):
        measure(tmp_path, output, (external, lock), max_disk_bytes=10_000)


def test_disk_measurement_fails_closed_when_output_snapshot_stays_unreadable(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "row.jsonl").write_bytes(b"row\n")
    original_rglob = Path.rglob

    def denied(path: Path, pattern: str):
        if path.resolve() == output.resolve():
            raise PermissionError("synthetic persistent scan failure")
        return original_rglob(path, pattern)

    monkeypatch.setattr(Path, "rglob", denied)
    with pytest.raises(budget.StudyResourceError, match="measurement unavailable"):
        budget.check_disk_budget(output, (), max_disk_bytes=1024)


def test_004_ledger_binds_three_predecessors_and_routes_family_disk_accounting(tmp_path: Path) -> None:
    output, external, lock = _make_004_family_disk_fixture(tmp_path)
    external.unlink()
    (output / "a2-study-budget.jsonl").unlink()
    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    ledger = budget.StudyLedger(
        tmp_path / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_004_ID,
        predecessor=config["predecessor"],
        config_sha256=digest,
    )

    ledger.append("predecessor", {"predecessor": config["predecessor"]})
    records = ledger.records()

    assert ledger.external_path == external
    assert ledger.lock_path == lock
    assert records[0]["study_id"] == STUDY_004_ID
    assert records[0]["study_output"] == "artifacts/a2-context-verifier-v1-004"
    assert records[0]["predecessor"] == config["predecessor"]
    assert ledger.measure_disk(max_disk_bytes=10_000) == sum(
        path.stat().st_size for path in (tmp_path / "artifacts").rglob("*") if path.is_file()
    )


def test_004_preflight_is_read_only_and_requires_the_fixed_three_predecessor_family(tmp_path: Path, monkeypatch) -> None:
    from eating_event.a2 import audit, control

    config_path = ROOT / "configs" / "a2-context-verifier-v1-004.json"
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / config_path.name).write_bytes(config_path.read_bytes())
    (config_dir / "a2-context-verifier-v1-004.sha256").write_bytes(config_path.with_suffix(".sha256").read_bytes())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    expected_environment = {
        "python": "3.10.11",
        "libraries": {"numpy": "2.2.6", "scipy": "1.15.3", "scikit-learn": "1.7.2", "psutil": "7.2.2"},
    }
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 8 * 1024**3)
    monkeypatch.setattr(control, "verify_predecessor_family_003", lambda _root: config_from_root["predecessor"], raising=False)
    monkeypatch.setattr(control, "current_a2_code_identity", lambda _root: {"synthetic.py": "1" * 64})
    monkeypatch.setattr(audit, "_environment_identity", lambda: expected_environment)
    config_from_root, digest = load_config(ROOT, study_id=STUDY_004_ID)

    result = control.launch("preflight", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_004_ID)

    assert result["status"] == "PREFLIGHT_READY"
    assert result["study_id"] == STUDY_004_ID
    assert result["config_sha256"] == digest
    assert result["startup_available_bytes"] == 8 * 1024**3
    assert result["rss_ceiling_bytes"] == 4 * 1024**3
    assert not (artifacts / "a2-context-verifier-v1-004").exists()
    assert not (artifacts / "a2-study-budget-v1-004.jsonl").exists()
    assert not (artifacts / "a2-study-budget-v1-004.lock").exists()


def test_004_runner_prints_chinese_result_through_cp1252_stream(monkeypatch) -> None:
    from eating_event.a2 import control

    runner_path = ROOT / "scripts" / "run_a2_context_verifier_004.py"
    assert runner_path.is_file()
    spec = importlib.util.spec_from_file_location("a2_004_runner_under_test", runner_path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    class Cp1252Output:
        encoding = "cp1252"

        def __init__(self) -> None:
            self.parts: list[bytes] = []

        def write(self, value: str) -> int:
            self.parts.append(value.encode("cp1252"))
            return len(value)

        def flush(self) -> None:
            return None

    output = Cp1252Output()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(control, "launch", lambda *args, **kwargs: {"status": "NOT_STARTED_GATE_FAILED", "reason": "磁盘采样失败"})

    exit_code = runner.main(["preflight"])

    assert exit_code == 0
    result = json.loads(b"".join(output.parts).decode("cp1252"))
    assert result["reason"] == "磁盘采样失败"


def test_004_supervisor_survives_high_frequency_atomic_worker_writes(tmp_path: Path) -> None:
    from eating_event.a2.control import supervise_worker

    output, external, lock = _make_004_family_disk_fixture(tmp_path)
    external.unlink()
    (output / "a2-study-budget.jsonl").unlink()
    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    ledger = budget.StudyLedger(
        tmp_path / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_004_ID,
        predecessor=config["predecessor"],
        config_sha256=digest,
    )
    ledger.append("predecessor", {"predecessor": config["predecessor"]})
    response = output / "worker-response-audit.json"
    worker_code = (
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "output = Path(sys.argv[1])\n"
        "response = Path(sys.argv[2])\n"
        "(output / 'worker-progress.json').write_text(json.dumps({'last_completed_stage': 'audit_complete'}) + '\\n', encoding='utf-8')\n"
        "temporary = output / 'labels.jsonl.tmp'\n"
        "final = output / 'labels.jsonl'\n"
        "for index in range(240):\n"
        "    with temporary.open('wb') as stream:\n"
        "        stream.write((str(index) + '\\n').encode('ascii') * 256)\n"
        "        stream.flush()\n"
        "        os.fsync(stream.fileno())\n"
        "    temporary.replace(final)\n"
        "    time.sleep(0.002)\n"
        "response.write_text('{}\\n', encoding='utf-8')\n"
    )
    telemetry = supervise_worker(
        [sys.executable, "-c", worker_code, str(output), str(response)],
        output,
        ledger,
        response_path=response,
        max_rss_bytes=2 * 1024**3,
        max_disk_bytes=8 * 1024**2,
        wall_deadline_seconds=10.0,
        sample_interval_seconds=0.01,
    )

    assert response.is_file()
    assert (output / "labels.jsonl").is_file()
    assert not (output / "labels.jsonl.tmp").exists()
    assert telemetry["returncode"] == 0
    assert telemetry["peak_rss_bytes"] > 0
    assert telemetry["study_bytes"] < 8 * 1024**2
    assert sum(row["event"] == "resource_sample" for row in ledger.records()) >= 2
    assert external.read_bytes() == (output / "a2-study-budget.jsonl").read_bytes()
    assert lock.is_file()


def test_004_audit_state_machine_releases_lock_after_fake_ready_worker(tmp_path: Path, monkeypatch) -> None:
    from eating_event.a2 import audit, control

    config_path = ROOT / "configs" / "a2-context-verifier-v1-004.json"
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / config_path.name).write_bytes(config_path.read_bytes())
    (config_dir / "a2-context-verifier-v1-004.sha256").write_bytes(config_path.with_suffix(".sha256").read_bytes())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for suffix in ("001", "002", "003"):
        old_output = artifacts / f"a2-context-verifier-v1-{suffix}"
        old_output.mkdir()
        payload = (json.dumps({"event": f"synthetic_{suffix}"}) + "\n").encode("ascii")
        (old_output / "a2-study-budget.jsonl").write_bytes(payload)
        external = artifacts / ("a2-study-budget.jsonl" if suffix == "001" else f"a2-study-budget-v1-{suffix}.jsonl")
        external.write_bytes(payload)

    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    expected_environment = {
        "python": "3.10.11",
        "platform": "synthetic",
        "libraries": {"numpy": "2.2.6", "scipy": "1.15.3", "scikit-learn": "1.7.2", "psutil": "7.2.2"},
    }
    code_identity = {"synthetic.py": "1" * 64}
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 8 * 1024**3)
    monkeypatch.setattr(control, "verify_predecessor_family_003", lambda _root: config["predecessor"])
    monkeypatch.setattr(control, "current_a2_code_identity", lambda _root: code_identity)
    monkeypatch.setattr(audit, "_environment_identity", lambda: expected_environment)

    def fake_supervise(command, output_dir, ledger, *, response_path, **kwargs):
        output = Path(output_dir)
        temporary = output / "fake.jsonl.tmp"
        final = output / "fake.jsonl"
        for index in range(20):
            temporary.write_text(f"{index}\n", encoding="ascii")
            temporary.replace(final)
        report = {
            "status": "AUDIT_READY",
            "study_id": STUDY_004_ID,
            "study_output": config["study_output"],
            "config_sha256": digest,
            "a2_code_identity": code_identity,
        }
        report_bytes = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        report_path = output / "audit-ready.json"
        report_path.write_bytes(report_bytes)
        ready_sha = hashlib.sha256(report_bytes).hexdigest()
        (output / "audit-ready.sha256").write_text(ready_sha + "  audit-ready.json\n", encoding="ascii")
        (output / "worker-progress.json").write_text('{"last_completed_stage":"audit_complete"}\n', encoding="utf-8")
        Path(response_path).write_text(json.dumps({
            "status": "AUDIT_READY",
            "study_id": STUDY_004_ID,
            "study_output": str(output),
            "config_sha256": digest,
            "audit_ready_sha256": ready_sha,
        }), encoding="utf-8")
        return {"elapsed_seconds": 0.1, "peak_rss_bytes": 123456, "study_bytes": 1024, "returncode": 0, "last_completed_stage": "audit_complete", "failing_measurement_bytes": None}

    monkeypatch.setattr(control, "supervise_worker", fake_supervise)

    result = control.launch("audit", tmp_path, config_digest=digest, study_notes="synthetic identity", study_id=STUDY_004_ID)

    output = artifacts / "a2-context-verifier-v1-004"
    external = artifacts / "a2-study-budget-v1-004.jsonl"
    mirror = output / "a2-study-budget.jsonl"
    lock = artifacts / "a2-study-budget-v1-004.lock"
    assert result["status"] == "AUDIT_READY"
    assert not lock.exists()
    assert output.is_dir() and external.is_file() and mirror.is_file()
    assert external.read_bytes() == mirror.read_bytes()
    records = [json.loads(line) for line in external.read_text(encoding="utf-8").splitlines()]
    assert sum(row.get("event") == "invocation_start" and row.get("mode") == "audit" for row in records) == 1
    assert sum(row.get("event") == "invocation_start" and row.get("mode") == "run" for row in records) == 0
    assert sum(row.get("event") == "fit_reserve" for row in records) == 0
    assert json.loads((output / "run-status.json").read_text(encoding="utf-8"))["status"] == "AUDIT_READY"


def test_004_run_with_low_current_memory_preserves_ready_without_lock_or_run_event(tmp_path: Path, monkeypatch) -> None:
    from eating_event.a2 import audit, control

    config_path = ROOT / "configs" / "a2-context-verifier-v1-004.json"
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / config_path.name).write_bytes(config_path.read_bytes())
    (config_dir / "a2-context-verifier-v1-004.sha256").write_bytes(config_path.with_suffix(".sha256").read_bytes())
    output, external, lock = _make_004_family_disk_fixture(tmp_path)
    external.unlink()
    (output / "a2-study-budget.jsonl").unlink()
    config, digest = load_config(ROOT, study_id=STUDY_004_ID)
    code_identity = {"synthetic.py": "2" * 64}
    expected_environment = {
        "python": "3.10.11",
        "platform": "synthetic",
        "libraries": {"numpy": "2.2.6", "scipy": "1.15.3", "scikit-learn": "1.7.2", "psutil": "7.2.2"},
    }
    monkeypatch.setattr(control, "available_memory_bytes", lambda: 4 * 1024**3)
    monkeypatch.setattr(control, "verify_predecessor_family_003", lambda _root: config["predecessor"])
    monkeypatch.setattr(control, "current_a2_code_identity", lambda _root: code_identity)
    monkeypatch.setattr(audit, "_environment_identity", lambda: expected_environment)
    ledger = budget.StudyLedger(
        tmp_path / "artifacts",
        output,
        limits=config["limits"],
        study_id=STUDY_004_ID,
        predecessor=config["predecessor"],
        config_sha256=digest,
    )
    report = {
        "status": "AUDIT_READY",
        "study_id": STUDY_004_ID,
        "study_output": config["study_output"],
        "config_sha256": digest,
        "a2_code_identity": code_identity,
    }
    report_bytes = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (output / "audit-ready.json").write_bytes(report_bytes)
    ready_sha = hashlib.sha256(report_bytes).hexdigest()
    (output / "audit-ready.sha256").write_text(ready_sha + "  audit-ready.json\n", encoding="ascii")
    ledger.append("predecessor", {"predecessor": config["predecessor"]})
    ledger.append("startup_resources", {"startup_available_bytes": 8 * 1024**3, "rss_ceiling_bytes": 4 * 1024**3})
    ledger.append("invocation_start", {"id": "audit-004", "mode": "audit", "monotonic": 100.0})
    ledger.append("invocation_end", {"id": "audit-004", "duration_seconds": 0.1})
    ledger.mark_status("AUDIT_READY", audit_ready_sha256=ready_sha)
    (output / "run-status.json").write_text(json.dumps({
        "status": "AUDIT_READY",
        "study_id": STUDY_004_ID,
        "study_output": config["study_output"],
        "config_sha256": digest,
        "audit_ready_sha256": ready_sha,
    }), encoding="utf-8")

    lock.unlink()

    result = control.launch("run", tmp_path, config_digest=digest, study_notes="", study_id=STUDY_004_ID)

    records = ledger.records()
    assert result["status"] == "RUN_NOT_STARTED_INSUFFICIENT_HEADROOM"
    assert json.loads((output / "run-status.json").read_text(encoding="utf-8"))["status"] == "AUDIT_READY"
    assert not lock.exists()
    assert sum(row.get("event") == "invocation_start" and row.get("mode") == "run" for row in records) == 0
    assert sum(row.get("event") == "fit_reserve" for row in records) == 0
