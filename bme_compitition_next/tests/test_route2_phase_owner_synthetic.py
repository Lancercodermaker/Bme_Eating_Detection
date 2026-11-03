"""Bound phase ownership only: fake snapshots and temporary journals, no study data.

These fixtures seed role counters; they do not represent full Stage A execution
or scientific equivalence. The complete reconstruction replay has its own suite.
"""

from dataclasses import replace
import hashlib
import json
import time

import pytest

from eating_event.route2_candidate_overlap.budget import DurableEventReceipt, _canonical
from eating_event.route2_candidate_overlap.linux_supervisor import SupervisorState
from test_route2_startup_owner_synthetic import startup  # noqa: F401
from test_route2_supervisor_lifecycle_synthetic import _synthetic_stage_b_projection


@pytest.fixture
def phases(startup, monkeypatch):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    roles = {f"synthetic-role-{index}" for index in range(105)}
    ledger._reference_passed = roles.copy()
    ledger._treatment_roles = roles.copy()
    ledger._treatment_finished = dict.fromkeys(roles, {})
    ledger._different_treatment_roles = {"synthetic-role-0"}
    expanded = replace(snapshot, study_fs_capacity_bytes=(4 << 30) - 65536,
                       study_image_length_bytes=4 << 30)
    ops.expansions = 0
    def expand(*args):
        # A zero-work fake controller can fit inside Windows Python 3.10's
        # monotonic clock tick. Preserve the production strict-after contract.
        while time.monotonic_ns() <= guard._stage_b_entry_event_receipt.fsynced_monotonic_ns:
            time.sleep(0.001)
        ops.expansions += 1
        monkeypatch.setattr(ops, "current_snapshot", lambda *args: expanded)
        return expanded
    monkeypatch.setattr(ops, "expand_after_stage_b_entry", expand, raising=False)
    for name in ("append_stage_b_entry", "append_expansion_receipt", "read_stage_a_boundary",
                 "expand_same_volume", "read_stage_b_completion"):
        monkeypatch.setattr(ops, name,
                            lambda *args: (_ for _ in ()).throw(AssertionError("duplicate OS phase writer")),
                            raising=False)
    yield startup
    ledger.close()


def events(ledger):
    return [json.loads(raw)["entry"]["event"] for raw in ledger.path.read_bytes().splitlines()]


def test_bound_guard_stage_a_is_observed_once_without_duplicate_writer(phases):
    _, ledger, guard, supervisor, *_ = phases
    guard.finish_stage_a()
    assert supervisor.state is SupervisorState.STAGE_A_FINISHED
    assert supervisor.stage_a.event_sha256 == guard._stage_a_event_receipt.event_sha256
    assert events(ledger).count("stage_a_finished") == 1


def test_bound_guard_entry_and_expansion_are_observed_before_any_calls(phases):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    projection = _synthetic_stage_b_projection(guard._stage_a_snapshot.study_disk_current_bytes)
    guard.require_stage_b_entry(projection)
    assert supervisor.state is SupervisorState.STAGE_B_READY
    assert ops.expansions == 1
    assert supervisor.stage_b_entry.event_sha256 == guard._stage_b_entry_event_receipt.event_sha256
    assert supervisor.expansion_receipt.event_sha256 == guard._stage_b_expansion_event_receipt.event_sha256
    assert supervisor.volume.image_length_bytes == guard.limits.total_disk_bytes
    assert events(ledger)[-3:] == ["stage_a_finished", "stage_b_entry_passed", "stage_b_volume_expanded"]


def test_frozen_role_graph_drift_is_rejected_before_physical_expansion(phases):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    projection = _synthetic_stage_b_projection(guard._stage_a_snapshot.study_disk_current_bytes,
                                              role_graph_sha256="f" * 64)
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(projection)
    assert ops.expansions == 0
    assert not guard._stage_b_admitted
    assert supervisor.state is SupervisorState.FAILED
    assert guard._boundary_failure is not None


@pytest.mark.parametrize("field", ["started_monotonic_ns", "deadline_monotonic_ns",
                                   "frozen_rss_ceiling_bytes", "volume", "stage_a"])
def test_mutable_supervisor_phase_anchors_cannot_replace_accepted_evidence(phases, field):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    original = getattr(supervisor, field)
    if field == "volume":
        changed = replace(original, image_inode=999)
    elif field == "stage_a":
        changed = replace(original, stage_a_disk_bytes=0)
    else:
        changed = original + 1
    setattr(supervisor, field, changed)
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    assert ops.expansions == 0
    assert guard._boundary_failure is not None


def test_resetting_public_phase_progress_cannot_retry_consumed_observer(phases):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    original = supervisor.stage_a
    supervisor.stage_a = replace(original, stage_a_disk_bytes=0)
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    before = ledger.path.read_bytes()
    supervisor.stage_a = original
    supervisor.state = SupervisorState.STAGE_A_FINISHED
    guard._boundary_failure = None
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    assert ops.expansions == 0
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize("entry", ["activity", "invoke_call"])
def test_resetting_guard_progress_after_failure_cannot_start_work(phases, entry):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    original = supervisor.stage_a
    supervisor.stage_a = replace(original, stage_a_disk_bytes=0)
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    supervisor.stage_a = original
    supervisor.state = SupervisorState.STAGE_B_READY
    guard._boundary_failure = None
    guard._stage_b_admitted = True
    before = ledger.path.read_bytes()
    with pytest.raises(PermissionError):
        if entry == "activity":
            with guard.activity("must-not-run", stage_a=False):
                pytest.fail("activity started after private observer failure")
        else:
            guard.invoke_call("verifier_fit", "must-not-run",
                              lambda: pytest.fail("call ran after private observer failure"))
    assert ops.expansions == 0
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize("entry", ["activity", "invoke_call"])
def test_healthy_observer_requires_private_expansion_before_any_stage_b_work(phases, monkeypatch, entry):
    _, ledger, guard, supervisor, ops, _, initial = phases
    guard.finish_stage_a()
    # Keep the observer healthy: no rejected proof or prior poison.
    guard._stage_b_admitted = True
    bypass_snapshot = replace(initial, study_fs_capacity_bytes=(4 << 30) - 65536,
                              study_image_length_bytes=4 << 30)
    counts = {"backend": 0, "operation": 0}
    def backend(*args, **kwargs):
        counts["backend"] += 1
        return object()
    def operation():
        counts["operation"] += 1
        return "forged-stage-b-work"
    monkeypatch.setattr(ops, "enforce_during_activity", backend, raising=False)
    monkeypatch.setattr(ops, "stop_activity", lambda *args: bypass_snapshot, raising=False)
    before = ledger.path.read_bytes()
    with pytest.raises(PermissionError):
        if entry == "activity":
            with guard.activity("forged-work", stage_a=False):
                operation()
        else:
            guard.invoke_call("verifier_fit", "verifier/outer-00/inner-00", operation)
    assert counts == {"backend": 0, "operation": 0}
    assert ledger.path.read_bytes() == before
    assert ops.expansions == 0
    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize("which", ["stage_a", "entry", "expansion"])
def test_observation_failure_consumes_boundary_and_blocks_downstream(phases, monkeypatch, which):
    _, ledger, guard, supervisor, ops, *_ = phases
    method = {"stage_a": "observe_budget_stage_a", "entry": "observe_budget_stage_b_entry",
              "expansion": "observe_budget_expansion"}[which]
    def reject(*args):
        raise PermissionError("synthetic observation failure")
    monkeypatch.setattr(supervisor, method, reject)
    if which != "stage_a":
        guard.finish_stage_a()
    with pytest.raises(PermissionError):
        if which == "stage_a":
            guard.finish_stage_a()
        else:
            guard.require_stage_b_entry(_synthetic_stage_b_projection(guard._stage_a_snapshot.study_disk_current_bytes))
    assert guard._boundary_failure is not None
    assert not guard._stage_b_admitted
    assert ops.expansions == (1 if which == "expansion" else 0)
    with pytest.raises(PermissionError):
        guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))


@pytest.mark.parametrize("which", ["stage_a", "entry", "expansion", "completion"])
def test_unbound_guard_cannot_adopt_phase_receipts(startup, which):
    _, ledger, guard, supervisor, *_ = startup
    method = {"stage_a": "observe_budget_stage_a", "entry": "observe_budget_stage_b_entry",
              "expansion": "observe_budget_expansion", "completion": "observe_budget_stage_b_completion"}[which]
    with pytest.raises(PermissionError):
        if which == "entry":
            getattr(supervisor, method)(guard, _synthetic_stage_b_projection(4096))
        else:
            getattr(supervisor, method)(guard)


def seed_completion(ledger, guard):
    # Only a receipt-observation fixture, deliberately no GT/model/evaluator.
    result = {"synthetic_fixture": True}
    payload = {"invocation_id": guard.invocation_id, "inner_roles_completed": 20,
               "outer_roles_completed": 5, "verifier_fit_calls": 25, "verifier_predict_calls": 25,
               "decoder_calls": 65, "evaluator_calls": 20, "pooled_aggregation_calls": 1,
               "pooled_aggregation_completed": True, "pooled_gt_reads": 0,
               "call_event_count": 408, "call_event_accounting_sha256": "1" * 64,
               "finished_monotonic_ns": time.monotonic_ns(),
               "result_sha256": hashlib.sha256(_canonical(result)).hexdigest()}
    guard._stage_b_result_evidence = result
    guard._stage_b_completion_event_receipt = ledger._append_durable("stage_b_complete", payload)
    return payload


def test_readonly_completion_adopts_same_owner_event_not_second_writer(phases):
    _, ledger, guard, supervisor, *_ = phases
    guard.finish_stage_a()
    guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    seed_completion(ledger, guard)
    before = ledger.path.read_bytes()
    supervisor.observe_budget_stage_b_completion(guard)
    assert supervisor.state is SupervisorState.STAGE_B_FINISHED
    assert supervisor.stage_b_completion.event_sha256 == guard._stage_b_completion_event_receipt.event_sha256
    assert ledger.path.read_bytes() == before
    with pytest.raises((PermissionError, RuntimeError)):
        supervisor.observe_budget_stage_b_completion(guard)


@pytest.mark.parametrize("entry", ["activity", "invoke_call"])
def test_healthy_completed_observer_forbids_work_after_public_completion_reset(phases, monkeypatch, entry):
    _, ledger, guard, supervisor, ops, *_ = phases
    guard.finish_stage_a()
    guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    seed_completion(ledger, guard)
    supervisor.observe_budget_stage_b_completion(guard)
    guard._stage_b_completion_event_receipt = None
    counts = {"backend": 0, "operation": 0}
    def backend(*args, **kwargs):
        counts["backend"] += 1
        return object()
    def operation():
        counts["operation"] += 1
    monkeypatch.setattr(ops, "enforce_during_activity", backend, raising=False)
    before = ledger.path.read_bytes()
    with pytest.raises(PermissionError):
        if entry == "activity":
            with guard.activity("must-not-run", stage_a=False):
                operation()
        else:
            guard.invoke_call("verifier_fit", "must-not-run", operation)
    assert counts == {"backend": 0, "operation": 0}
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize("failure", [False, True])
def test_guard_completion_hook_follows_durable_fixed_call_trace(phases, monkeypatch, failure):
    from test_route2_budget_wsl_synthetic import _append_fixed_call_events, _synthetic_stage_b_result
    _, ledger, guard, supervisor, *_ = phases
    guard.finish_stage_a()
    guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    _append_fixed_call_events(ledger)
    result = _synthetic_stage_b_result(guard.study_root)
    if failure:
        def reject(owner):
            assert events(ledger)[-1] == "stage_b_complete"
            assert owner._stage_b_completion_event_receipt.event_sha256 == ledger._tail
            raise PermissionError("synthetic completion observation failure")
        monkeypatch.setattr(supervisor, "observe_budget_stage_b_completion", reject)
        with pytest.raises(PermissionError):
            guard.finish_stage_b(result)
        assert guard._boundary_failure is not None
        assert supervisor.state is SupervisorState.FAILED
        with pytest.raises(PermissionError):
            with guard.activity("must-not-run", stage_a=False):
                pytest.fail("activity continued after completion observation failure")
    else:
        guard.finish_stage_b(result)
        assert supervisor.state is SupervisorState.STAGE_B_FINISHED
        assert supervisor.stage_b_completion.call_event_count == 408
        assert events(ledger).count("stage_b_complete") == 1


@pytest.mark.parametrize("field,value", [("evaluator_calls", 21), ("pooled_gt_reads", 1),
                                        ("inner_roles_completed", True), ("call_event_count", 407),
                                        ("result_sha256", "2" * 64)])
def test_completion_metadata_drift_is_refused(phases, field, value):
    _, ledger, guard, supervisor, *_ = phases
    guard.finish_stage_a()
    guard.require_stage_b_entry(_synthetic_stage_b_projection(4096))
    payload = seed_completion(ledger, guard)
    payload[field] = value
    # Replace only this mock fixture's final record, retaining a valid hash chain.
    records = [json.loads(line) for line in ledger.path.read_bytes().splitlines()]
    records[-1]["entry"]["payload"] = payload
    digest = hashlib.sha256(_canonical(records[-1]["entry"])).hexdigest()
    records[-1]["sha256"] = digest
    ledger.path.write_bytes(b"".join(_canonical(item) + b"\n" for item in records))
    ledger._tail = digest
    guard._stage_b_completion_event_receipt = DurableEventReceipt(digest, time.monotonic_ns())
    with pytest.raises(PermissionError):
        supervisor.observe_budget_stage_b_completion(guard)
    assert supervisor.state is SupervisorState.FAILED
