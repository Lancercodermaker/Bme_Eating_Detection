"""Startup ownership checks using fake volume receipts and temporary journals.

No image, project input, GT or systemd service is created. Windows directory
fsync is replaced only in these tests; the Linux suite uses the real syscall.
"""

from dataclasses import asdict
from pathlib import Path
import json
import os
import time

import pytest

from eating_event.route2_candidate_overlap import budget
from eating_event.route2_candidate_overlap.budget import (
    AppendOnlyLedger, BudgetGuard, BudgetLimits, EnforcementReceipt, ResourceSnapshot,
)
from eating_event.route2_candidate_overlap.contracts import ExperimentApproval, STUDY_ID
from eating_event.route2_candidate_overlap.linux_supervisor import Route2Supervisor, SupervisorState
from eating_event.route2_candidate_overlap.linux_supervisor import StartupAbortReceipt
from test_route2_supervisor_lifecycle_synthetic import _approval, _synthetic_frozen_admission


@pytest.fixture
def startup(tmp_path, monkeypatch):
    # This fixture bypasses approval validation ONLY to exercise OS ordering.
    # Real admission validation is covered by the bootstrap/approval suites.
    monkeypatch.setattr(ExperimentApproval, "require_full_ab", lambda self: None)
    from eating_event.route2_candidate_overlap import contracts
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", _synthetic_frozen_admission())
    if os.name == "nt":
        monkeypatch.setattr(budget, "_sync_directory", lambda path: None, raising=False)
    limits = BudgetLimits()
    root = tmp_path / STUDY_ID
    ledger = AppendOnlyLedger(tmp_path / f"{STUDY_ID}-budget.jsonl", tmp_path / f"{STUDY_ID}.lock", root)
    from dataclasses import replace
    approval = replace(_approval(None), study_root_path=str(root),
                       budget_ledger_path=str(ledger.path), lock_path=str(ledger.lock_path),
                       study_image_path=str(tmp_path / "fake.ext4"),
                       approved_write_volumes=(str(tmp_path),), budget_policy_sha256=limits.digest())
    started = time.monotonic_ns() - 1_000_000
    snapshot = ResourceSnapshot(
        1024, 4096, 1, 8 << 30, 4096, 9 << 30, "11", "8:1",
        "E:\\synthetic\\ext4.vhdx", "synthetic-volume-guid", 9 << 30,
        "42", "7:7", (2 << 30) - 65536, "synthetic-uuid", "/dev/loop7",
        approval.study_image_path, 123, 456, 2 << 30, 4096,
    )
    receipt = EnforcementReceipt(
        "synthetic-controller", approval.resource_controller_sha256, str(root),
        str(ledger.path), str(ledger.lock_path), (str(tmp_path),),
        True, True, True, True, "e" * 64, "/system.slice/synthetic.service",
        4 << 30, 0, 2, 2 << 30, 2 << 30, 4 << 30, "11", "synthetic-volume-guid",
        started, started + 1, started + 2, 9 << 30, 9 << 30,
        snapshot.study_fs_uuid, snapshot.study_loop_device, snapshot.study_image_path,
        snapshot.study_image_dev, snapshot.study_image_inode, snapshot.study_image_length_bytes,
    )

    class OS:
        prepare_calls = 0
        abort_calls = 0

        def prepare_volume(self, *args):
            self.prepare_calls += 1
            return receipt, snapshot

        def current_snapshot(self, *args):
            return snapshot

        def acquire_one_shot_lock(self, *args):
            raise AssertionError("Supervisor must not create a second study lock")

        def create_stage_a_volume(self, *args):
            raise AssertionError("Supervisor must not create a second image")

        def abort_startup(self, invocation_id, approved, phase, failure_kind):
            self.abort_calls += 1
            return StartupAbortReceipt(invocation_id, approved.study_root_path,
                                       approved.budget_ledger_path, approved.lock_path,
                                       approved.study_image_path, True, True, True, True,
                                       time.monotonic_ns())

    ops = OS()
    guard = BudgetGuard(limits, ledger, ops, root,
                        approved_controller_sha256=approval.resource_controller_sha256,
                        approved_write_volumes=approval.approved_write_volumes,
                        invocation_started_monotonic_ns=started, invocation_id="synthetic-startup")
    supervisor = Route2Supervisor(approval=approval, invocation_id=guard.invocation_id,
                                 ops=ops, limits=limits, external_started_ticks=1, qpc_frequency=1)
    # Real Supervisor requires Linux paths; temporary Windows paths exist only
    # for this bounded file-ordering test, never in production configuration.
    monkeypatch.setattr(supervisor, "_require_approval_paths", lambda: None)
    return approval, ledger, guard, supervisor, ops, receipt, snapshot


def test_guard_is_the_only_startup_owner_and_supervisor_observes(startup):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    assert ops.prepare_calls == 1
    assert supervisor.state is SupervisorState.STARTED
    assert supervisor.started_monotonic_ns == guard._invocation_started_ns
    assert supervisor.volume.image_inode == snapshot.study_image_inode
    assert ledger._created_monotonic_ns >= receipt.image_created_monotonic_ns
    assert [json.loads(line)["entry"]["event"] for line in ledger.path.read_text().splitlines()] == [
        "study_created", "invocation_started",
    ]
    with pytest.raises(RuntimeError):
        supervisor.start()
    with pytest.raises(RuntimeError):
        guard.start(approval)
    assert ops.prepare_calls == 1
    ledger.close()


@pytest.mark.parametrize("changed", ["ops", "invocation", "limits", "paths", "clock", "stale"])
def test_binding_rejects_different_controller_or_stale_guard(startup, changed):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    if changed == "ops":
        supervisor.ops = object()
    elif changed == "invocation":
        supervisor.invocation_id = "other"
    elif changed == "limits":
        supervisor.limits = BudgetLimits(worker_limit=1)
    elif changed == "paths":
        guard.study_root = Path("/different")
    elif changed == "clock":
        guard._invocation_started_ns = 0
    else:
        guard._start_entered = True
    with pytest.raises(PermissionError):
        supervisor.bind_budget_guard(guard)
    assert ops.prepare_calls == 0
    assert not ledger.lock_path.exists()


def test_supervisor_rejects_hand_written_startup_receipts_without_bound_guard(startup):
    approval, ledger, guard, supervisor, *_ = startup
    with pytest.raises(PermissionError):
        supervisor.observe_budget_start(guard)


def test_failed_lock_payload_keeps_durable_occupied_tombstone_before_root(startup, monkeypatch):
    approval, ledger, guard, supervisor, *_ = startup
    trace = []
    real_sync = getattr(budget, "_sync_directory", lambda path: None)
    monkeypatch.setattr(budget, "_sync_directory", lambda path: (trace.append("parent-sync"), real_sync(path))[-1], raising=False)
    monkeypatch.setattr(budget.os, "write", lambda fd, payload: (_ for _ in ()).throw(OSError("payload failure")))
    with pytest.raises(OSError, match="payload failure"):
        ledger.create(approval, guard.limits)
    assert ledger.lock_path.exists()
    assert ledger.lock_path.stat().st_size == 0
    assert trace == ["parent-sync"]
    assert not ledger.study_root.exists()
    with pytest.raises(RuntimeError, match="once"):
        ledger.create(approval, guard.limits)


def test_startup_owner_rejects_ledger_without_parent_durability(startup, monkeypatch):
    approval, ledger, guard, supervisor, *_ = startup
    monkeypatch.setattr(budget, "_sync_directory", lambda path: (_ for _ in ()).throw(OSError("directory sync")), raising=False)
    with pytest.raises(OSError, match="directory sync"):
        ledger.create(approval, guard.limits)
    assert not ledger.study_root.exists()
    assert ledger.lock_path.exists()
    with pytest.raises(RuntimeError, match="once"):
        ledger.create(approval, guard.limits)


@pytest.mark.parametrize("failure", ["prepare", "ledger", "observe", "cleanup"])
def test_failed_bound_startup_closes_fd_aborts_once_and_cannot_retry(startup, monkeypatch, failure):
    approval, ledger, guard, supervisor, ops, *_ = startup
    supervisor.bind_budget_guard(guard)
    if failure in ("prepare", "cleanup"):
        monkeypatch.setattr(ops, "prepare_volume", lambda *args: (_ for _ in ()).throw(OSError("preparation failed")))
    elif failure == "ledger":
        real_sync = budget._sync_directory
        count = 0
        def failing_sync(path):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError("ledger parent sync failed")
            real_sync(path)
        monkeypatch.setattr(budget, "_sync_directory", failing_sync)
    else:
        monkeypatch.setattr(supervisor, "_verify_guard_startup_journal",
                            lambda guard: (_ for _ in ()).throw(PermissionError("observation failed")))
    if failure == "cleanup":
        def missing_cleanup(*args):
            ops.abort_calls += 1
            raise OSError("no cleanup proof")
        monkeypatch.setattr(ops, "abort_startup", missing_cleanup)
    with pytest.raises((OSError, PermissionError)):
        guard.start(approval)
    assert supervisor.state is SupervisorState.FAILED
    assert not guard._started
    assert guard._finished
    assert ledger._fd is None
    assert ops.abort_calls == 1
    with pytest.raises(RuntimeError):
        guard.start(approval)
    assert ops.abort_calls == 1


@pytest.mark.parametrize("method", ["finish_stage_a", "enter_stage_b", "finish_stage_b", "finalize"])
def test_bound_supervisor_cannot_duplicate_guard_phase_writes(startup, method):
    approval, ledger, guard, supervisor, *_ = startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    with pytest.raises(PermissionError, match="BudgetGuard"):
        if method == "enter_stage_b":
            getattr(supervisor, method)(None)
        elif method == "finalize":
            getattr(supervisor, method)("INCOMPLETE_RESOURCE", evidence={})
        else:
            getattr(supervisor, method)()
    ledger.close()


def test_direct_ledger_parent_sync_failure_closes_writer_and_forbids_append(startup, monkeypatch):
    approval, ledger, guard, *_ = startup
    original_sync = budget._sync_directory
    calls = 0
    def sync(path):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("after ledger append")
        original_sync(path)
    monkeypatch.setattr(budget, "_sync_directory", sync)
    with pytest.raises(OSError):
        ledger.create(approval, guard.limits)
    assert ledger._fd is None
    assert ledger._poisoned
    with pytest.raises(RuntimeError):
        ledger.append("invocation_started", {"invocation_id": "forged", "monotonic_ns": 1})


@pytest.mark.parametrize("field,value", [
    ("started_monotonic_ns", 1), ("deadline_monotonic_ns", 2), ("startup", object()),
    ("volume", object()), ("stage_a", object()), ("frozen_rss_ceiling_bytes", 1),
    ("expansion_receipt", object()), ("stage_b_entry", object()),
    ("_stage_b_projection", object()), ("_approved_role_graph_sha256", "a" * 64),
    ("stage_b_completion", object()), ("_terminal", object()),
    ("_terminal_attempted", True), ("_lock_attempted", True),
    ("_startup_failure_phase", "old failure"),
])
def test_lifecycle_binding_rejects_all_stale_supervisor_state(startup, field, value):
    approval, ledger, guard, supervisor, *_ = startup
    setattr(supervisor, field, value)
    with pytest.raises(PermissionError):
        supervisor.bind_budget_guard(guard)
    assert guard._lifecycle_supervisor is None


@pytest.mark.parametrize("which", ["receipt", "snapshot"])
def test_startup_rejects_structural_enforcer_receipt_before_storage(startup, monkeypatch, which):
    from types import SimpleNamespace
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    fake_receipt = SimpleNamespace(**asdict(receipt), require_complete=lambda: None)
    fake_snapshot = SimpleNamespace(**asdict(snapshot))
    monkeypatch.setattr(ops, "prepare_volume", lambda *args: (
        fake_receipt if which == "receipt" else receipt,
        fake_snapshot if which == "snapshot" else snapshot,
    ))
    with pytest.raises(PermissionError, match="exact"):
        guard.start(approval)
    assert not ledger.lock_path.exists()
    assert ops.abort_calls == 1


@pytest.mark.parametrize("mutation", ["truncate", "replace", "hash", "extra", "noncanonical"])
def test_startup_observer_replays_disk_bytes_and_rejects_tampering(startup, monkeypatch, mutation):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    def sample(*args):
        if ledger.path.exists():
            encoded = ledger.path.read_bytes()
            if mutation == "truncate":
                ledger.path.write_bytes(encoded[:-1])
            elif mutation == "replace":
                other = ledger.path.with_suffix(".replacement")
                other.write_bytes(encoded)
                os.replace(other, ledger.path)
            elif mutation == "hash":
                ledger.path.write_bytes(encoded.replace(b'"study_created"', b'"study_changed"'))
            elif mutation == "extra":
                ledger.path.write_bytes(encoded + encoded.splitlines(keepends=True)[0])
            else:
                ledger.path.write_bytes(encoded.replace(b'"entry":', b'"entry": '))
        return snapshot
    monkeypatch.setattr(ops, "current_snapshot", sample)
    with pytest.raises(PermissionError):
        guard.start(approval)
    assert ledger._fd is None
    assert supervisor.state is SupervisorState.FAILED
    assert ops.abort_calls == 1


@pytest.mark.parametrize("occupied", ["root", "lock", "ledger"])
def test_occupied_namespace_is_rejected_before_any_volume_preparation(startup, occupied):
    approval, ledger, guard, supervisor, ops, *_ = startup
    if occupied == "root":
        ledger.study_root.mkdir()
    elif occupied == "lock":
        ledger.lock_path.write_bytes(b"prior occupied ID")
    else:
        ledger.path.write_bytes(b"prior journal")
    supervisor.bind_budget_guard(guard)
    with pytest.raises(FileExistsError):
        guard.start(approval)
    assert ops.prepare_calls == 0
    assert ops.abort_calls == 0
    assert supervisor.state is SupervisorState.FAILED


def test_close_failure_cannot_skip_the_controller_abort(startup, monkeypatch):
    approval, ledger, guard, supervisor, ops, *_ = startup
    supervisor.bind_budget_guard(guard)
    real_close = budget.os.close
    def close(fd):
        real_close(fd)
        if ledger._fd is None and ledger._poisoned and ledger.path.exists():
            raise OSError("close failed after releasing writer")
    monkeypatch.setattr(budget.os, "close", close)
    monkeypatch.setattr(supervisor, "_verify_guard_startup_journal",
                        lambda guard: (_ for _ in ()).throw(PermissionError("journal failure")))
    with pytest.raises((OSError, PermissionError)):
        guard.start(approval)
    assert ops.abort_calls == 1
    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize("field,value", [
    ("enforcer", object()), ("_invocation_started_ns", 1), ("invocation_id", "different"),
    ("ledger", object()), ("_lifecycle_supervisor", None), ("limits", BudgetLimits(worker_limit=1)),
])
def test_bound_identity_drift_is_rejected_before_os_operations(startup, field, value):
    approval, ledger, guard, supervisor, ops, *_ = startup
    supervisor.bind_budget_guard(guard)
    setattr(guard, field, value)
    with pytest.raises(PermissionError):
        guard.start(approval)
    assert ops.prepare_calls == 0
    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize("field,value", [("ops", object()), ("invocation_id", "changed"), ("limits", BudgetLimits(worker_limit=1))])
def test_supervisor_identity_drift_is_rejected_before_os_operations(startup, field, value):
    approval, ledger, guard, supervisor, ops, *_ = startup
    supervisor.bind_budget_guard(guard)
    setattr(supervisor, field, value)
    with pytest.raises(PermissionError):
        guard.start(approval)
    assert ops.prepare_calls == 0


def test_drift_inside_prepare_aborts_using_original_controller_identity(startup, monkeypatch):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    def prepare(*args):
        guard.enforcer = object()
        guard.invocation_id = "changed"
        supervisor.ops = object()
        supervisor._budget_guard = None
        return receipt, snapshot
    monkeypatch.setattr(ops, "prepare_volume", prepare)
    with pytest.raises(PermissionError):
        guard.start(approval)
    assert ops.abort_calls == 1
    assert not ledger.lock_path.exists()


@pytest.mark.parametrize("mutation", ["delete", "replace", "content"])
def test_startup_observer_checks_actual_lock_identity(startup, monkeypatch, mutation):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    def sample(*args):
        if ledger.path.exists():
            if mutation == "delete":
                ledger.lock_path.unlink()
            elif mutation == "replace":
                other = ledger.lock_path.with_suffix(".other")
                other.write_bytes(ledger.lock_path.read_bytes())
                os.replace(other, ledger.lock_path)
            else:
                ledger.lock_path.write_bytes(b"forged study lock")
        return snapshot
    monkeypatch.setattr(ops, "current_snapshot", sample)
    with pytest.raises((PermissionError, OSError)):
        guard.start(approval)
    assert ops.abort_calls == 1


def test_same_uppercase_budget_digest_can_create_the_same_ledger(startup):
    from dataclasses import replace
    approval, ledger, guard, *_ = startup
    ledger.create(replace(approval, budget_policy_sha256=approval.budget_policy_sha256.upper()), guard.limits)
    ledger.close()


@pytest.mark.parametrize("field", ["_volume_prepare_entered", "_start_entered"])
def test_mutable_progress_flags_cannot_hide_prepare_or_enable_retry(startup, monkeypatch, field):
    approval, ledger, guard, supervisor, ops, *_ = startup
    supervisor.bind_budget_guard(guard)
    def prepare(*args):
        setattr(guard, field, False)
        raise OSError("failed after entering preparation")
    monkeypatch.setattr(ops, "prepare_volume", prepare)
    with pytest.raises(OSError):
        guard.start(approval)
    assert ops.abort_calls == 1
    with pytest.raises(RuntimeError):
        guard.start(approval)
