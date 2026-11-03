"""Native bound terminal hooks, with synthetic snapshots and temporary journals."""
import errno
import json
import os

import pytest

from eating_event.route2_candidate_overlap import terminal_observation as terminal
from eating_event.route2_candidate_overlap.budget import AppendOnlyLedger
from eating_event.route2_candidate_overlap.linux_supervisor import SupervisorState
from test_route2_startup_owner_synthetic import startup
from test_route2_terminal_reader_synthetic import mock_quiescence


@pytest.fixture
def owner(startup):
    from types import SimpleNamespace
    approval,ledger,guard,supervisor,ops,receipt,snapshot=startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    yield SimpleNamespace(approval=approval,ledger=ledger,guard=guard,supervisor=supervisor,ops=ops,snapshot=snapshot)
    ledger.close()


def test_startup_registers_original_terminal_owner_and_native_hooks(owner,monkeypatch):
    assert owner.guard in terminal._OBSERVERS
    owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    assert terminal._OBSERVERS[owner.guard].step=="closed"
    mock_quiescence(owner,monkeypatch)
    raw=owner.ledger.path.read_bytes()
    proof=owner.supervisor.observe_budget_terminal_close(owner.guard)
    assert proof.status=="INCOMPLETE_RESOURCE" and proof.ledger_bytes==raw
    assert owner.supervisor.state is SupervisorState.TERMINAL_PENDING
    assert owner.ledger.path.read_bytes()==raw
    assert [json.loads(line)["entry"]["event"] for line in raw.splitlines()].count("terminal")==1
    with pytest.raises(PermissionError): owner.supervisor.observe_budget_terminal_close(owner.guard)


def test_missing_actual_quiescence_cannot_issue_terminal_handoff(owner):
    owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    with pytest.raises(PermissionError): owner.supervisor.observe_budget_terminal_close(owner.guard)
    assert owner.supervisor.state is SupervisorState.FAILED and owner.supervisor._terminal is None


@pytest.mark.parametrize("failure",["sync","close"])
def test_original_ledger_close_failure_consumes_fd_without_retry(owner,monkeypatch,failure):
    descriptor=owner.ledger._fd
    close_count=[]
    native_close=os.close
    native_fsync=os.fsync
    def close(fd):
        if fd==descriptor: close_count.append(fd)
        native_close(fd)
        if fd==descriptor and failure=="close": raise OSError(errno.EIO,"synthetic released FD")
    def fsync(fd):
        if fd==descriptor and failure=="sync": raise OSError(errno.EIO,"synthetic fsync failure")
        native_fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,"close",close)
        patch.setattr(os,"fsync",fsync)
        with pytest.raises(OSError): owner.ledger.close()
        assert owner.ledger._fd is None and owner.ledger._poisoned
        owner.ledger.close()
    assert close_count==[descriptor]
    assert owner.ledger._closed_at_monotonic_ns is None
    with pytest.raises(PermissionError): owner.supervisor.observe_budget_terminal_close(owner.guard)


def test_public_reset_cannot_reopen_terminal_owner_or_start_work(owner,monkeypatch):
    owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    before=owner.ledger.path.read_bytes()
    owner.guard._finished=False
    owner.guard._started=True
    with pytest.raises(PermissionError):
        with owner.guard.activity("forged",stage_a=True,fit=False): pass
    assert owner.ledger.path.read_bytes()==before


def test_native_finalize_close_failure_releases_anchor_and_consumes(owner,monkeypatch):
    writer=owner.ledger._fd
    native_close=os.close
    def released(fd):
        native_close(fd)
        if fd==writer and terminal._OBSERVERS[owner.guard].step=="before_close":
            raise OSError(errno.EIO,"synthetic close after release")
    with monkeypatch.context() as context:
        context.setattr(os,"close",released)
        with pytest.raises(OSError): owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    state=terminal._OBSERVERS[owner.guard]
    assert state.failed and state.anchor_fd is None
    assert owner.ledger._fd is None and owner.ledger._closed_at_monotonic_ns is None
    with pytest.raises(PermissionError): terminal.read_owned_terminal_close(owner.guard)


def test_mutable_lifecycle_cannot_skip_hooks_or_reach_snapshot(owner,monkeypatch):
    before=owner.ledger.path.read_bytes()
    calls=[]
    monkeypatch.setattr(owner.ops,"current_snapshot",lambda *args:calls.append("snapshot") or owner.snapshot)
    owner.guard._lifecycle_supervisor=None
    with pytest.raises(PermissionError): owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    assert not calls and owner.ledger.path.read_bytes()==before
    owner.guard._lifecycle_supervisor=owner.supervisor
    with pytest.raises(PermissionError): owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})


def test_supervisor_precheck_failure_consumes_original_readonly_handoff(owner,monkeypatch):
    owner.guard.finalize("INCOMPLETE_RESOURCE",evidence={"synthetic":True})
    mock_quiescence(owner,monkeypatch)
    started=owner.supervisor.started_monotonic_ns
    owner.supervisor.started_monotonic_ns+=1
    with pytest.raises(PermissionError): owner.supervisor.observe_budget_terminal_close(owner.guard)
    owner.supervisor.started_monotonic_ns=started
    owner.supervisor._terminal_attempted=False
    owner.supervisor.state=SupervisorState.STARTED
    with pytest.raises(PermissionError): owner.supervisor.observe_budget_terminal_close(owner.guard)
    assert terminal._OBSERVERS[owner.guard].failed


def test_failed_native_close_cannot_gain_success_by_public_attribute_reset(owner,monkeypatch):
    from eating_event.route2_candidate_overlap import budget
    fd=owner.ledger._fd
    real=os.close
    def close(descriptor):
        real(descriptor)
        if descriptor==fd: raise OSError(errno.EIO,"synthetic release error")
    with monkeypatch.context() as patch:
        patch.setattr(os,"close",close)
        with pytest.raises(OSError): owner.ledger.close()
    owner.ledger._poisoned=False
    owner.ledger._closed_at_monotonic_ns=__import__('time').monotonic_ns()
    with pytest.raises(PermissionError): budget.require_owned_ledger_close_success(owner.ledger,fd)


def test_native_close_never_closes_a_reused_foreign_descriptor(owner,tmp_path):
    writer=owner.ledger._fd
    foreign=os.open(tmp_path/"foreign-synthetic-file",os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
    os.dup2(foreign,writer)
    try:
        with pytest.raises(PermissionError): owner.ledger.close()
        assert os.fstat(writer).st_ino==os.fstat(foreign).st_ino
        assert owner.ledger._fd is None and owner.ledger._poisoned
    finally:
        os.close(foreign)
        try: os.close(writer)
        except OSError as exc:
            if exc.errno!=errno.EBADF: raise
