"""Terminal provenance only: temporary journals, synthetic counters, no GT/OS volume.

Tracing supplies the proposed hooks inside the actual BudgetGuard.finalize
without editing that file. Quiescence is mocked ONLY in receipt-success tests;
the production evidence source deliberately refuses the missing controller.
"""

from copy import copy
from contextlib import ExitStack
import errno
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from eating_event.route2_candidate_overlap import phase_observation as phase
from eating_event.route2_candidate_overlap import budget
from eating_event.route2_candidate_overlap.budget import BudgetGuard, CALL_CEILINGS, _canonical
from eating_event.route2_candidate_overlap.contracts import StudyStatus
from eating_event.route2_candidate_overlap.linux_supervisor import TerminalCloseReceipt
from test_route2_startup_owner_synthetic import startup  # noqa: F401


MODULE = "eating_event.route2_candidate_overlap.terminal_observation"


def terminal():
    assert importlib.util.find_spec(MODULE) is not None, "owned terminal reader is missing"
    return importlib.import_module(MODULE)


def test_terminal_component_exists():
    terminal()


@pytest.fixture
def owner(startup, monkeypatch):
    approval, ledger, guard, supervisor, ops, receipt, snapshot = startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    # Main may wire the readonly supervisor observation during this task. Keep
    # this component's handoff explicit, rather than consume it inside finalize.
    monkeypatch.setattr(supervisor, "observe_budget_terminal_close", lambda *args: None, raising=False)
    if importlib.util.find_spec(MODULE) is not None:
        terminal()._OBSERVERS.pop(guard, None)
    yield SimpleNamespace(approval=approval, ledger=ledger, guard=guard, supervisor=supervisor,
                          ops=ops, snapshot=snapshot)
    if importlib.util.find_spec(MODULE) is not None and terminal()._OBSERVERS.get(guard) is not None:
        try:
            terminal().fail_owned_terminal(guard)
        except PermissionError:
            # A drift test may intentionally break live fields. The failure
            # hook has already poisoned/released its own readonly descriptor.
            pass
    ledger.close()
    if importlib.util.find_spec(MODULE) is not None:
        terminal()._OBSERVERS.pop(guard, None)


def register(owner):
    terminal().register_terminal_observer(owner.guard)


def accept_phases(owner, count):
    payloads = (
        {"reference_roles": 105, "treatment_roles": 105, "different_treatment_roles": 1,
         "stage_a_disk_bytes": 4096, "finished_monotonic_ns": time.monotonic_ns()},
        {"projection": {"synthetic": True}},
        {"entry_event_sha256": "e" * 64, "volume": {"synthetic": True}},
        {"call_event_count": 408, "call_event_accounting_sha256": "1" * 64,
         "result_sha256": hashlib.sha256(_canonical({"synthetic": True})).hexdigest(),
         "finished_monotonic_ns": time.monotonic_ns()},
    )
    for event, values in zip(phase._PHASES[:count], payloads):
        payload = {"invocation_id": owner.guard.invocation_id, **values}
        receipt = owner.ledger._append_durable(event, payload)
        proof = phase.read_owned_phase_event(owner.guard, event, receipt)
        phase.accept_owned_phase_event(owner.guard, proof)


def seed_complete(owner):
    # This fixture verifies phase/terminal provenance, not 105 roles or science.
    owner.ledger._stage_a_finished = True
    owner.ledger._stage_b_complete = True
    owner.ledger._reference_passed = set(range(105))
    owner.ledger._treatment_roles = set(range(105))
    owner.ledger._call_counts = dict(CALL_CEILINGS)


def finish(owner, status="INCOMPLETE_RESOURCE", *, mutate=None, hooks=True, result="default", on_exception=None):
    source, first = inspect.getsourcelines(BudgetGuard.finalize)
    points = {name: first + next(i for i, text in enumerate(source) if needle in text)
              for name, needle in (("write", "self.ledger.terminal("), ("close", "self.ledger.close()"),
                                   ("closed", "return status"))}
    calls = []
    native_hooks = any("prepare_owned_terminal" in line for line in source)
    evidence = {"synthetic_terminal": True}
    if len(phase._OBSERVERS[owner.guard].accepted) == 4:
        if result == "default":
            evidence["stage_b_result"] = {"synthetic": True}
        elif result is not None:
            evidence["stage_b_result"] = result
    def trace(frame, event, arg):
        if frame.f_code is BudgetGuard.finalize.__code__ and frame.f_locals.get("self") is owner.guard:
            if event == "line" and hooks and not native_hooks:
                if frame.f_lineno == points["write"] and "prepare" not in calls:
                    calls.append("prepare")
                    frame.f_locals["evidence"].update(terminal().prepare_owned_terminal(owner.guard))
                elif frame.f_lineno == points["close"] and "before" not in calls:
                    calls.append("before")
                    terminal().before_owned_terminal_close(owner.guard)
                elif frame.f_lineno == points["closed"] and "after" not in calls:
                    calls.append("after")
                    terminal().after_owned_terminal_close(owner.guard)
            if event == "line" and mutate is not None:
                mutate(owner, frame, points)
            if event == "exception" and on_exception is not None:
                on_exception(owner, frame, arg, points)
            return trace
        return trace
    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        with ExitStack() as stack:
            if native_hooks and not hooks:
                for name, replacement in (("prepare_owned_terminal", lambda guard: {}),
                                          ("before_owned_terminal_close", lambda guard: None),
                                          ("after_owned_terminal_close", lambda guard: None)):
                    stack.enter_context(patch.object(terminal(), name, replacement))
            result = owner.guard.finalize(status, evidence=evidence)
    finally:
        sys.settrace(previous)
    if hooks and not native_hooks:
        assert calls == ["prepare", "before", "after"]
    return result


def mock_quiescence(owner, monkeypatch, **changes):
    def source(guard, binding, cgroup_path):
        assert guard is owner.guard and binding.controller is owner.ops
        values = dict(controller=owner.ops, invocation_id=binding.invocation_id,
                      pid=os.getpid(), cgroup_path=cgroup_path, controller_pids=(os.getpid(),),
                      worker_pids=(), gt_mount_ids=(), sampled_monotonic_ns=time.monotonic_ns())
        values.update(changes)
        return terminal()._Quiescence(**values)
    monkeypatch.setattr(terminal(), "_require_controller_quiescence", source)


def consumed(owner):
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    with pytest.raises(PermissionError):
        terminal().register_terminal_observer(owner.guard)


@pytest.mark.parametrize("status", [item.value for item in StudyStatus if item is not StudyStatus.COMPLETE])
def test_legal_partial_status_handoff_reads_real_closed_owner_journal(owner, monkeypatch, status):
    register(owner)
    finish(owner, status)
    mock_quiescence(owner, monkeypatch)
    before = owner.ledger.path.read_bytes()
    proof = terminal().read_owned_terminal_close(owner.guard)
    assert type(proof) is TerminalCloseReceipt
    assert proof.status == status and proof.invocation_id == owner.guard.invocation_id
    assert proof.ledger_bytes == before and proof.terminal_record_bytes == before.splitlines(keepends=True)[-1]
    assert proof.terminal_sha256 == owner.ledger.terminal_sha256 == owner.ledger._tail
    assert proof.terminal_closed_monotonic_ns == owner.ledger.closed_at_monotonic_ns
    assert proof.invocation_started_monotonic_ns == owner.guard._invocation_started_ns
    assert proof.deadline_monotonic_ns == proof.invocation_started_monotonic_ns + owner.guard.limits.total_wall_ns
    assert (proof.ledger_fsynced, proof.ledger_closed, proof.no_active_gt_view, proof.no_active_worker) == (True,) * 4
    assert proof.unit_name == "synthetic.service"
    assert owner.ledger.path.read_bytes() == before
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)


def test_complete_requires_all_four_privately_accepted_phases(owner, monkeypatch):
    register(owner)
    accept_phases(owner, 4)
    seed_complete(owner)
    finish(owner, "COMPLETE")
    mock_quiescence(owner, monkeypatch)
    proof = terminal().read_owned_terminal_close(owner.guard)
    body = json.loads(proof.terminal_record_bytes)["entry"]["payload"]
    chain = body["evidence"]["route2_supervisor_chain"]
    assert chain["stage_b_completion_event_sha256"] is not None
    assert proof.terminal_binding_sha256 == hashlib.sha256(_canonical(chain)).hexdigest()


@pytest.mark.parametrize("accepted", range(4))
def test_complete_rejects_fabricated_public_completion_even_with_ledger_flags(owner, accepted):
    register(owner)
    accept_phases(owner, accepted)
    seed_complete(owner)
    owner.guard._stage_b_admitted = True
    with pytest.raises(PermissionError):
        finish(owner, "COMPLETE")
    assert "terminal" not in [json.loads(line)["entry"]["event"] for line in owner.ledger.path.read_bytes().splitlines()]
    consumed(owner)


def test_failed_phase_can_close_partial_but_cannot_close_complete(owner, monkeypatch):
    register(owner)
    accept_phases(owner, 2)
    phase.fail_phase_observer(owner.guard)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    assert terminal().read_owned_terminal_close(owner.guard).status == "INCOMPLETE_RESOURCE"


def test_missing_real_controller_teardown_source_refuses_any_receipt(owner):
    register(owner)
    finish(owner)
    with pytest.raises(PermissionError, match="controller|quiescence|worker|GT"):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


@pytest.mark.parametrize("field,value", [("worker_pids", (123,)), ("gt_mount_ids", (42,)),
    ("controller_pids", ()), ("controller_pids", (1,)), ("pid", True),
    ("invocation_id", "wrong"), ("cgroup_path", "/system.slice/wrong.service"),
    ("sampled_monotonic_ns", 1), ("controller", object())])
def test_quiescence_must_be_exact_bound_observation_not_public_flags(owner, monkeypatch, field, value):
    register(owner)
    finish(owner)
    owner.guard._activity_open = False
    owner.ledger._active_gt_release = None
    mock_quiescence(owner, monkeypatch, **{field: value})
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


@pytest.mark.parametrize("value", [True, {}, SimpleNamespace(no_active_worker=True, no_active_gt_view=True)])
def test_ducktyped_quiescence_never_issues_terminal_receipt(owner, monkeypatch, value):
    register(owner)
    finish(owner)
    monkeypatch.setattr(terminal(), "_require_controller_quiescence", lambda *args: value)
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


@pytest.mark.parametrize("hook", ["prepare_owned_terminal", "before_owned_terminal_close", "after_owned_terminal_close"])
def test_hooks_require_real_original_guard_finalize_context(owner, hook):
    register(owner)
    with pytest.raises(PermissionError):
        getattr(terminal(), hook)(owner.guard)
    consumed(owner)


def test_no_hooks_public_closed_flags_and_actual_close_are_insufficient(owner, monkeypatch):
    register(owner)
    finish(owner, hooks=False)
    mock_quiescence(owner, monkeypatch)
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


def test_live_fd_cannot_be_hidden_by_setting_public_none(owner, monkeypatch):
    register(owner)
    real_close = owner.ledger.close
    original_fd = owner.ledger._fd
    def fake_close():
        owner.ledger._fd = None
        owner.ledger._closed_at_monotonic_ns = time.monotonic_ns()
    monkeypatch.setattr(owner.ledger, "close", fake_close)
    try:
        with pytest.raises(PermissionError):
            finish(owner)
        assert owner.ledger._fd is None
        with pytest.raises(OSError) as discarded:
            os.fstat(original_fd)
        assert discarded.value.errno == errno.EBADF
    finally:
        # Native finalize may already have consumed/closed the original FD on
        # this rejection. Never restore and retry a released descriptor number.
        if owner.ledger._fd is not None:
            owner.ledger.close = real_close
            real_close()
    consumed(owner)


@pytest.mark.parametrize("change", ["partial", "noncanonical", "tail", "sequence", "startup", "lock", "closed_time"])
def test_closed_journal_and_lock_cannot_change_before_readonly_handoff(owner, monkeypatch, change):
    register(owner)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    if change == "partial":
        owner.ledger.path.write_bytes(owner.ledger.path.read_bytes()[:-1])
    elif change == "noncanonical":
        owner.ledger.path.write_bytes(b" " + owner.ledger.path.read_bytes())
    elif change == "tail":
        owner.ledger._tail = "e" * 64
    elif change == "sequence":
        owner.ledger._seq += 1
    elif change == "startup":
        owner.ledger.path.write_bytes(owner.ledger.path.read_bytes().replace(b"created_wall_ns", b"created_wall_nx", 1))
    elif change == "lock":
        owner.ledger.lock_path.write_bytes(b"{}")
    else:
        owner.ledger._closed_at_monotonic_ns += 1
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


def test_unregistered_copy_cannot_issue_or_poison_original_terminal(owner, monkeypatch):
    register(owner)
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(copy(owner.guard))
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    assert terminal().read_owned_terminal_close(owner.guard).status == "INCOMPLETE_RESOURCE"


def test_terminal_handoff_rejects_foreign_thread_and_consumes_original(owner):
    register(owner)
    finish(owner)
    errors = []
    def foreign():
        try:
            terminal().read_owned_terminal_close(owner.guard)
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=foreign)
    thread.start()
    thread.join()
    assert len(errors) == 1 and isinstance(errors[0], PermissionError)
    consumed(owner)


def test_readonly_handoff_never_writes_or_fsyncs_and_closes_temp_fds_once(owner, monkeypatch):
    register(owner)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    original_close, original_read = os.close, os.read
    closes, reads = [], []
    def observed_close(fd):
        closes.append(fd)
        original_close(fd)
    def observed_read(fd, count):
        reads.append(count)
        return original_read(fd, count)
    def forbidden(*args, **kwargs):
        pytest.fail("terminal handoff performed a write/fsync")
    with monkeypatch.context() as context:
        context.setattr(terminal().os, "write", forbidden)
        context.setattr(terminal().os, "fsync", forbidden)
        context.setattr(terminal().os, "close", observed_close)
        context.setattr(terminal().os, "read", observed_read)
        terminal().read_owned_terminal_close(owner.guard)
    assert len(closes) == 2  # separately reopened lock and journal
    assert all(size <= 65536 for size in reads) and reads.count(1) >= 2


def test_temp_close_after_release_refuses_handoff_without_retry(owner, monkeypatch):
    register(owner)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    original = os.close
    closes = []
    def released(fd):
        closes.append(fd)
        original(fd)
        raise OSError(errno.EIO, "synthetic close after release")
    with monkeypatch.context() as context:
        context.setattr(terminal().os, "close", released)
        with pytest.raises(PermissionError):
            terminal().read_owned_terminal_close(owner.guard)
    assert len(closes) == 2 and len(set(closes)) == 2  # failed lock read plus held anchor cleanup
    consumed(owner)


@pytest.mark.parametrize("field", ["_seq", "_closed_at_monotonic_ns"])
def test_live_terminal_clock_and_sequence_require_exact_integer_types(owner, monkeypatch, field):
    register(owner)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    setattr(owner.ledger, field, float(getattr(owner.ledger, field)))
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


@pytest.mark.parametrize("change", ["journal", "lock", "sequence", "close_time", "tail"])
def test_handoff_rechecks_storage_and_live_close_after_controller_sampling(owner, monkeypatch, change):
    register(owner)
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    original = terminal()._require_controller_quiescence
    def mutate_during_sample(*args):
        result = original(*args)
        if change == "journal":
            owner.ledger.path.write_bytes(owner.ledger.path.read_bytes() + b"\n")
        elif change == "lock":
            owner.ledger.lock_path.write_bytes(b"{}")
        elif change == "sequence":
            owner.ledger._seq += 1
        elif change == "tail":
            owner.ledger._tail = "e" * 64
        else:
            owner.ledger._closed_at_monotonic_ns += 1
        return result
    monkeypatch.setattr(terminal(), "_require_controller_quiescence", mutate_during_sample)
    with pytest.raises(PermissionError):
        terminal().read_owned_terminal_close(owner.guard)
    consumed(owner)


def test_failed_private_phase_four_cannot_be_reset_to_complete(owner):
    register(owner)
    accept_phases(owner, 4)
    seed_complete(owner)
    phase.fail_phase_observer(owner.guard)
    owner.guard._boundary_failure = None
    owner.guard._stage_b_admitted = True
    with pytest.raises(PermissionError):
        finish(owner, "COMPLETE")
    consumed(owner)


@pytest.mark.parametrize("status", ["INCOMPLETE_RESOURCE", "INVALID"])
def test_only_resource_incomplete_close_may_overrun_frozen_deadline(owner, monkeypatch, status):
    register(owner)
    future = owner.guard._invocation_started_ns + owner.guard.limits.total_wall_ns + 1_000_000
    def late_close(current, frame, points):
        if frame.f_lineno == points["close"]:
            monkeypatch.setattr(terminal().time, "monotonic_ns", lambda: future)
    if status == "INCOMPLETE_RESOURCE":
        finish(owner, status, mutate=late_close)
        mock_quiescence(owner, monkeypatch)
        proof = terminal().read_owned_terminal_close(owner.guard)
        assert proof.terminal_closed_monotonic_ns > proof.deadline_monotonic_ns
    else:
        with pytest.raises(PermissionError):
            finish(owner, status, mutate=late_close)
        consumed(owner)


@pytest.mark.parametrize("result", [None, {}, {"synthetic": False}, True])
def test_complete_result_bytes_must_match_privately_accepted_completion_sha(owner, result):
    register(owner)
    accept_phases(owner, 4)
    seed_complete(owner)
    with pytest.raises(PermissionError):
        finish(owner, "COMPLETE", result=result)
    consumed(owner)


@pytest.mark.parametrize("failure", ["append", "append_fsync", "close_fsync", "close_after_release"])
def test_terminal_native_syscall_failure_consumes_attempt_and_cannot_restore_work(owner, monkeypatch, failure):
    register(owner)
    original_write, original_sync, original_close = os.write, os.fsync, os.close
    descriptor = owner.ledger._fd
    close_attempts = []
    syncs = []
    def broken_write(fd, data):
        if fd == descriptor and failure == "append":
            return original_write(fd, data[:len(data) // 2])
        return original_write(fd, data)
    def broken_sync(fd):
        if fd == descriptor:
            syncs.append(fd)
            if (failure == "append_fsync" and len(syncs) == 1) or (failure == "close_fsync" and len(syncs) == 2):
                raise OSError(errno.EIO, "synthetic terminal fsync failure")
        return original_sync(fd)
    def broken_close(fd):
        if fd == descriptor:
            close_attempts.append(fd)
        original_close(fd)
        if fd == descriptor and failure == "close_after_release":
            raise OSError(errno.EIO, "synthetic owner close after release")
    with monkeypatch.context() as context:
        context.setattr(terminal().os, "write", broken_write)
        context.setattr(terminal().os, "fsync", broken_sync)
        context.setattr(terminal().os, "close", broken_close)
        with pytest.raises((PermissionError, OSError)):
            finish(owner)
    terminal().fail_owned_terminal(owner.guard)
    assert terminal()._OBSERVERS[owner.guard].anchor_fd is None
    before = owner.ledger.path.read_bytes()
    owner.guard._finished = False
    owner.guard._boundary_failure = None
    owner.guard._stage_b_admitted = True
    with pytest.raises(PermissionError):
        phase.require_owned_work(owner.guard, stage_a=False, fit=True)
    with pytest.raises(PermissionError):
        finish(owner)
    assert owner.ledger.path.read_bytes() == before
    if failure.startswith("close"):
        assert close_attempts == [descriptor]
        assert owner.ledger._fd is None and owner.ledger._closed_at_monotonic_ns is None
        owner.ledger.close()
        assert close_attempts == [descriptor]
    consumed(owner)


@pytest.mark.parametrize("query", [None, True])
def test_after_close_refuses_missing_private_native_success_query(owner, monkeypatch, query):
    register(owner)
    monkeypatch.setattr(budget, "require_owned_ledger_close_success", query, raising=False)
    with pytest.raises(PermissionError, match="private|close|success"):
        finish(owner)
    consumed(owner)


def test_after_close_requires_native_success_fact_even_when_fd_is_really_closed(owner, monkeypatch):
    register(owner)
    original_fd = owner.ledger._fd
    calls = []
    def rejected(ledger, expectedoriginalfd):
        assert ledger is owner.ledger and expectedoriginalfd == original_fd
        calls.append(expectedoriginalfd)
        with pytest.raises(OSError) as actual:
            os.fstat(expectedoriginalfd)
        assert actual.value.errno == errno.EBADF
        raise PermissionError("synthetic private native close success fact rejected")
    monkeypatch.setattr(budget, "require_owned_ledger_close_success", rejected, raising=False)
    with pytest.raises(PermissionError, match="private native close success fact"):
        finish(owner)
    assert calls == [original_fd]
    consumed(owner)


def test_handoff_requeries_original_private_close_fact_before_readback(owner, monkeypatch):
    register(owner)
    original_fd = owner.ledger._fd
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    calls = []
    def rejected(ledger, expectedoriginalfd):
        assert ledger is owner.ledger and expectedoriginalfd == original_fd
        calls.append(expectedoriginalfd)
        raise PermissionError("synthetic private fact rejected at handoff")
    monkeypatch.setattr(budget, "require_owned_ledger_close_success", rejected, raising=False)
    with pytest.raises(PermissionError, match="private fact rejected at handoff"):
        terminal().read_owned_terminal_close(owner.guard)
    assert calls == [original_fd]
    consumed(owner)


def test_handoff_requeries_private_close_fact_after_controller_sample(owner, monkeypatch):
    register(owner)
    original_fd = owner.ledger._fd
    finish(owner)
    mock_quiescence(owner, monkeypatch)
    source = terminal()._require_controller_quiescence
    calls = []
    def rejected(ledger, expectedoriginalfd):
        assert ledger is owner.ledger and expectedoriginalfd == original_fd
        calls.append(expectedoriginalfd)
        raise PermissionError("synthetic private close fact changed during sampling")
    def changed(*args):
        sample = source(*args)
        monkeypatch.setattr(budget, "require_owned_ledger_close_success", rejected, raising=False)
        return sample
    monkeypatch.setattr(terminal(), "_require_controller_quiescence", changed)
    with pytest.raises(PermissionError, match="private close fact changed"):
        terminal().read_owned_terminal_close(owner.guard)
    assert calls == [original_fd]
    consumed(owner)


def test_traceerror_forged_public_success_after_close_error_cannot_issue_handoff(owner, monkeypatch):
    register(owner)
    mock_quiescence(owner, monkeypatch)
    original_fd = owner.ledger._fd
    real_close = os.close
    close_attempts = []
    outcome = []
    def close_after_release(fd):
        inject_error = fd == original_fd and not close_attempts
        if inject_error:
            close_attempts.append(fd)
        real_close(fd)
        if inject_error:
            raise OSError(errno.EIO, "synthetic native terminal close after release")
    def forge_public_success(current, frame, error, points):
        if outcome or frame.f_lineno != points["close"] or not isinstance(error[1], OSError):
            return
        current.ledger._fd = None
        current.ledger._poisoned = False
        current.ledger._closed_at_monotonic_ns = time.monotonic_ns()
        current.guard._finished = True
        # Keep the actual native finalize frame, stable file/phase anchors and
        # real EBADF. Only the private native success fact remains impossible.
        try:
            terminal().after_owned_terminal_close(current.guard)
            outcome.append(terminal().read_owned_terminal_close(current.guard))
        except PermissionError as rejected:
            outcome.append(rejected)
    with monkeypatch.context() as context:
        context.setattr(terminal().os, "close", close_after_release)
        with pytest.raises(OSError, match="close after release"):
            finish(owner, on_exception=forge_public_success)
    assert len(outcome) == 1 and isinstance(outcome[0], PermissionError)
    assert "private native success fact" in str(outcome[0])
    assert close_attempts == [original_fd]
    assert terminal()._OBSERVERS[owner.guard].anchor_fd is None
    consumed(owner)
