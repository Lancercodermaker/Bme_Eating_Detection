"""Synthetic bootstrap continuity tests; no project inputs or OS resources."""

from dataclasses import replace
from pathlib import Path
import os
import threading

import pytest

from eating_event.route2_candidate_overlap import admission_bootstrap, contracts
from eating_event.route2_candidate_overlap.source_snapshot import (
    ReadonlyMountProof, SourceSnapshotProof,
)
from test_route2_admission_bootstrap_synthetic import _config
from test_route2_supervisor_lifecycle_synthetic import _synthetic_frozen_admission


@pytest.fixture
def issued(monkeypatch, tmp_path):
    """Issue through the real bootstrap, replacing only external proof reads."""
    from eating_event.route2_candidate_overlap.budget import BudgetLimits

    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", None)
    monkeypatch.setattr(admission_bootstrap, "_ISSUED_BOOTSTRAP", None, raising=False)
    cfg_bytes = _config()
    cfg = admission_bootstrap.parse_supervisor_config(cfg_bytes)
    frozen = replace(
        _synthetic_frozen_admission(),
        source_snapshot_root=cfg.source_snapshot_root,
        source_snapshot_manifest_path=cfg.source_manifest_path,
        source_snapshot_sha256=cfg.source_snapshot_sha256,
        runtime_snapshot_root=cfg.runtime_snapshot_root,
        runtime_snapshot_manifest_path=cfg.runtime_manifest_path,
        runtime_snapshot_sha256=cfg.runtime_snapshot_sha256,
        approval_record=cfg.owner_approval_id,
        budget_policy_sha256=BudgetLimits().digest(),
    )
    snapshots = admission_bootstrap.SnapshotBootstrapProof(
        source=SourceSnapshotProof(cfg.source_snapshot_sha256, 1, 1),
        runtime=SourceSnapshotProof(cfg.runtime_snapshot_sha256, 1, 1),
        source_mount=ReadonlyMountProof(41, cfg.source_mount_path, "7:1", "ext4", "/dev/loop4"),
        runtime_mount=ReadonlyMountProof(42, cfg.runtime_mount_path, "7:2", "ext4", "/dev/loop5"),
    )
    monkeypatch.setattr(admission_bootstrap, "_require_linux_root", lambda: None)
    monkeypatch.setattr(admission_bootstrap, "_read_protected_file", lambda path, **kw: (
        cfg_bytes if str(path).endswith("supervisor.json") else b"x" * 32
    ))
    monkeypatch.setattr(admission_bootstrap, "_read_snapshot_manifest", lambda *a, **k: b"manifest")
    monkeypatch.setattr(admission_bootstrap, "_read_mountinfo", lambda: "synthetic")
    monkeypatch.setattr(admission_bootstrap, "_verify_live_snapshots", lambda *a, **k: snapshots)
    monkeypatch.setattr(admission_bootstrap, "load_controller_sealed_admission", lambda *a, **k: frozen)
    monkeypatch.setattr(admission_bootstrap, "_verify_runtime_execution", lambda *a: None)
    proof = admission_bootstrap.bootstrap_frozen_admission(tmp_path / "supervisor.json")
    return proof


def test_bootstrap_claim_requires_the_issued_object_and_is_once_only(issued):
    with pytest.raises(PermissionError, match="issued"):
        admission_bootstrap.claim_bootstrap_for_ab(replace(issued))
    # A forged claim does not consume the genuine proof.
    assert admission_bootstrap.claim_bootstrap_for_ab(issued) is issued.frozen_admission
    with pytest.raises(PermissionError, match="consumed"):
        admission_bootstrap.claim_bootstrap_for_ab(issued)


@pytest.mark.parametrize("changed", ["pid", "thread", "frozen"])
def test_claim_rejects_changed_execution_identity(issued, monkeypatch, changed):
    if changed == "pid":
        original = os.getpid()
        monkeypatch.setattr(admission_bootstrap.os, "getpid", lambda: original + 1)
    elif changed == "thread":
        monkeypatch.setattr(admission_bootstrap.threading, "current_thread", lambda: object())
    else:
        monkeypatch.setattr(contracts, "FROZEN_ADMISSION", replace(issued.frozen_admission))
    with pytest.raises(PermissionError):
        admission_bootstrap.claim_bootstrap_for_ab(issued)


def _bindings(proof):
    from eating_event.route2_candidate_overlap.admitted_execution import ABExecutionBindings
    from eating_event.route2_candidate_overlap.budget import AppendOnlyLedger, BudgetGuard, BudgetLimits
    from eating_event.route2_candidate_overlap.execution import ABReadiness, RoleCandidateReconstructor
    from eating_event.route2_candidate_overlap.references import ApprovedReferenceStore
    from eating_event.route2_candidate_overlap.stage_b import StageBAdapter
    from eating_event.route2_candidate_overlap.linux_supervisor import Route2Supervisor
    from test_route2_supervisor_lifecycle_synthetic import _approval

    frozen = proof.frozen_admission
    ledger = AppendOnlyLedger(Path(frozen.budget_ledger_path), Path(frozen.lock_path), Path(frozen.study_root_path))
    guard = BudgetGuard(
        BudgetLimits(), ledger, object(), ledger.study_root,
        approved_controller_sha256=frozen.resource_controller_sha256,
        approved_write_volumes=frozen.approved_write_volumes,
        invocation_started_monotonic_ns=1, invocation_id="synthetic-invocation",
    )
    # Never executed: exact typed placeholders allow testing handoff identity
    # without constructing project loaders or opening registered paths.
    approval = _approval(None)
    supervisor = Route2Supervisor(approval=approval, invocation_id=guard.invocation_id,
                                 ops=guard.enforcer, limits=guard.limits,
                                 external_started_ticks=1, qpc_frequency=1)
    return ABExecutionBindings(
        approval=approval, readiness=object.__new__(ABReadiness), roles=(),
        reference_provider=object.__new__(ApprovedReferenceStore),
        candidate_builder=object.__new__(RoleCandidateReconstructor),
        stage_b_adapter=object.__new__(StageBAdapter), ledger=ledger, guard=guard, supervisor=supervisor,
    )


def test_handoff_calls_fixed_run_ab_in_the_bootstrapped_process_once(issued, monkeypatch):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    bindings = _bindings(issued)
    calls = []
    expected = object()

    def fixed_runner(**kwargs):
        assert contracts.FROZEN_ADMISSION is issued.frozen_admission
        assert os.getpid() == original_pid
        assert threading.current_thread() is original_thread
        calls.append(kwargs)
        return expected

    original_pid, original_thread = os.getpid(), threading.current_thread()
    monkeypatch.setattr(execution, "run_ab", fixed_runner)
    assert admitted_execution.run_bootstrapped_ab(issued, bindings) is expected
    assert len(calls) == 1
    assert calls[0]["ledger"] is bindings.ledger
    assert calls[0]["guard"] is bindings.guard
    assert bindings.supervisor._budget_guard is bindings.guard
    assert bindings.guard._lifecycle_supervisor is bindings.supervisor
    with pytest.raises(PermissionError, match="consumed"):
        admitted_execution.run_bootstrapped_ab(issued, bindings)
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["approval", "ledger", "budget", "started", "paths", "runner"])
def test_rejected_handoff_is_not_retried_or_allowed_to_reach_run_ab(issued, monkeypatch, failure):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    bindings = _bindings(issued)
    if failure == "approval":
        bindings = replace(bindings, approval=object())
    elif failure == "ledger":
        bindings.guard.ledger = object()
    elif failure == "budget":
        bindings.guard.limits = replace(bindings.guard.limits, fit_wall_ns=1)
    elif failure == "started":
        bindings.guard._start_entered = True
    elif failure == "paths":
        bindings.ledger.path = bindings.ledger.path.with_name("other.jsonl")
    elif failure == "runner":
        bindings = replace(bindings, stage_b_adapter=object())
    calls = []
    monkeypatch.setattr(execution, "run_ab", lambda **kw: calls.append(kw))
    with pytest.raises((PermissionError, ValueError)):
        admitted_execution.run_bootstrapped_ab(issued, bindings)
    assert calls == []
    with pytest.raises(PermissionError, match="consumed"):
        admitted_execution.run_bootstrapped_ab(issued, _bindings(issued))


def test_runner_error_consumes_the_same_process_handoff(issued, monkeypatch):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    bindings = _bindings(issued)
    def failed_runner(**kw):
        raise RuntimeError("synthetic controller failure")
    monkeypatch.setattr(execution, "run_ab", failed_runner)
    with pytest.raises(RuntimeError, match="controller failure"):
        admitted_execution.run_bootstrapped_ab(issued, bindings)
    with pytest.raises(PermissionError, match="consumed"):
        admitted_execution.run_bootstrapped_ab(issued, bindings)


def test_clearing_the_public_frozen_global_does_not_allow_rebootstrap(issued, monkeypatch, tmp_path):
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", None)
    def forbidden_read(*a, **kw):
        raise AssertionError("rebootstrap reached protected files")
    monkeypatch.setattr(admission_bootstrap, "_read_protected_file", forbidden_read)
    with pytest.raises(PermissionError, match="already"):
        admission_bootstrap.bootstrap_frozen_admission(tmp_path / "supervisor.json")


def test_exact_proof_without_a_live_issuance_cannot_handoff(issued, monkeypatch):
    monkeypatch.setattr(admission_bootstrap, "_ISSUED_BOOTSTRAP", None)
    with pytest.raises(PermissionError, match="issued"):
        admission_bootstrap.claim_bootstrap_for_ab(issued)


def test_other_thread_cannot_claim_or_retry_the_genuine_handoff(issued):
    errors = []
    def other_thread():
        try:
            admission_bootstrap.claim_bootstrap_for_ab(issued)
        except PermissionError as error:
            errors.append(str(error))
    child = threading.Thread(target=other_thread)
    child.start()
    child.join(timeout=2)
    assert not child.is_alive()
    assert len(errors) == 1
    assert "thread" in errors[0]
    with pytest.raises(PermissionError, match="consumed"):
        admission_bootstrap.claim_bootstrap_for_ab(issued)


def test_combined_entry_bootstraps_then_uses_fixed_runner_without_exec(issued, monkeypatch):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    bindings = _bindings(issued)
    order = []
    def bootstrap(config_path):
        assert config_path == "/synthetic/supervisor.json"
        order.append("bootstrap")
        return issued
    def run_ab(**kw):
        assert kw["approval"] is bindings.approval
        order.append("fixed_runner")
        return "synthetic-result"
    monkeypatch.setattr(admitted_execution, "bootstrap_frozen_admission", bootstrap)
    monkeypatch.setattr(execution, "run_ab", run_ab)
    assert admitted_execution.bootstrap_and_run_ab(
        bindings, config_path="/synthetic/supervisor.json",
    ) == "synthetic-result"
    assert order == ["bootstrap", "fixed_runner"]


@pytest.mark.parametrize("object_name,field,value", [
    ("guard", "_fit_wall_ns", -900_000_000_000),
    ("guard", "_stage_a_finished_ns", 1),
    ("guard", "_rss_ceiling_bytes", 1),
    ("guard", "_stage_a_snapshot", object()),
    ("guard", "_stage_b_admitted", True),
    ("guard", "_volume_identity_snapshot", object()),
    ("guard", "_stage_a_event_receipt", object()),
    ("guard", "_stage_b_entry_event_receipt", object()),
    ("guard", "_stage_b_expansion_event_receipt", object()),
    ("guard", "_stage_b_completion_event_receipt", object()),
    ("guard", "_stage_b_result_evidence", {}),
    ("guard", "_boundary_failure", "old error"),
    ("guard", "_startup_receipt", object()),
    ("guard", "_startup_snapshot", object()),
    ("guard", "_lifecycle_supervisor", object()),
    ("guard", "_volume_prepare_entered", True),
    ("guard", "_startup_failure", "prior failure"),
    ("guard", "_startup_close_failure", "close failure"),
    ("guard", "_startup_phase", "ledger_create"),
    ("ledger", "_tail", "f" * 64),
    ("ledger", "_owner_thread_id", 1),
    ("ledger", "_reference_roles", {"old"}),
    ("ledger", "_reference_passed", {"old"}),
    ("ledger", "_treatment_roles", {"old"}),
    ("ledger", "_treatment_finished", {"old": object()}),
    ("ledger", "_different_treatment_roles", {"old"}),
    ("ledger", "_call_counts", {}),
    ("ledger", "_call_state", {("fit", 1): ("old", "finished")}),
    ("ledger", "_frozen_predictions", {"old": object()}),
    ("ledger", "_stage_b_entry_passed", True),
    ("ledger", "_stage_b_entry_event_hash", "f" * 64),
    ("ledger", "_stage_b_volume_expanded", True),
    ("ledger", "_active_gt_release", "old"),
    ("ledger", "_terminal_sha256", "f" * 64),
    ("ledger", "_closed_at_monotonic_ns", 1),
    ("ledger", "_invocation_id", "old"),
    ("ledger", "_invocation_started_monotonic_ns", 1),
    ("ledger", "_stage_a_finished", True),
    ("ledger", "_stage_b_complete", True),
    ("ledger", "_create_entered", True),
    ("ledger", "_created_monotonic_ns", 1),
    ("ledger", "_lock_identity", (1, 2)),
    ("ledger", "_lock_sha256", "a" * 64),
])
def test_handoff_rejects_all_stale_budget_and_ledger_state(
    issued, monkeypatch, object_name, field, value,
):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    bindings = _bindings(issued)
    setattr(getattr(bindings, object_name), field, value)
    calls = []
    monkeypatch.setattr(execution, "run_ab", lambda **kw: calls.append(kw))
    with pytest.raises(PermissionError, match="fresh"):
        admitted_execution.run_bootstrapped_ab(issued, bindings)
    assert calls == []
    with pytest.raises(PermissionError, match="consumed"):
        admitted_execution.run_bootstrapped_ab(issued, _bindings(issued))


def test_equivalent_uppercase_budget_and_controller_digests_are_accepted(issued, monkeypatch):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    upper = replace(issued.frozen_admission,
        resource_controller_sha256=issued.frozen_admission.resource_controller_sha256.upper(),
        budget_policy_sha256=issued.frozen_admission.budget_policy_sha256.upper(),
    )
    # Synthetic external seal fixture: issue this exact FrozenAdmission.
    proof = replace(issued, frozen_admission=upper)
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", upper)
    monkeypatch.setattr(admission_bootstrap, "_ISSUED_BOOTSTRAP",
        admission_bootstrap._IssuedBootstrap(proof, os.getpid(), threading.current_thread()))
    bindings = _bindings(proof)
    monkeypatch.setattr(execution, "run_ab", lambda **kw: "same-digest")
    assert admitted_execution.run_bootstrapped_ab(proof, bindings) == "same-digest"


@pytest.mark.parametrize("changed", ["missing", "ops", "guard", "approval", "state"])
def test_handoff_requires_same_fresh_lifecycle_owner(issued, monkeypatch, changed):
    from eating_event.route2_candidate_overlap import admitted_execution, execution
    from eating_event.route2_candidate_overlap.linux_supervisor import SupervisorState
    bindings = _bindings(issued)
    if changed == "missing":
        bindings = replace(bindings, supervisor=None)
    elif changed == "ops":
        bindings.supervisor.ops = object()
    elif changed == "guard":
        bindings.supervisor._budget_guard = object()
    elif changed == "approval":
        bindings.supervisor.approval = replace(bindings.approval)
    else:
        bindings.supervisor.state = SupervisorState.STARTED
    monkeypatch.setattr(execution, "run_ab", lambda **kwargs: pytest.fail("invalid lifecycle reached runner"))
    with pytest.raises(PermissionError):
        admitted_execution.run_bootstrapped_ab(issued, bindings)
