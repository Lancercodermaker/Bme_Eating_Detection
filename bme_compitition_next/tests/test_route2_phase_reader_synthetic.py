"""Owned phase provenance using temporary journals only, without volume IO."""

from copy import copy, deepcopy
from dataclasses import replace
import hashlib
import importlib
import importlib.util
import json
import os
import stat
import threading
import time
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap.budget import DurableEventReceipt, _canonical
from test_route2_startup_owner_synthetic import startup  # noqa: F401


MODULE = "eating_event.route2_candidate_overlap.phase_observation"
PHASES = ("stage_a_finished", "stage_b_entry_passed", "stage_b_volume_expanded", "stage_b_complete")


def phase():
    assert importlib.util.find_spec(MODULE) is not None, "bounded owned phase reader is missing"
    return importlib.import_module(MODULE)


def test_owned_phase_reader_exists():
    phase()


@pytest.fixture
def started(startup):
    approval, ledger, guard, supervisor, *_ = startup
    supervisor.bind_budget_guard(guard)
    guard.start(approval)
    if importlib.util.find_spec(MODULE) is not None:
        # Isolate this component if the disjoint lifecycle integration starts
        # automatically registering observers in the shared startup fixture.
        phase()._OBSERVERS.pop(guard, None)
    yield SimpleNamespace(approval=approval, ledger=ledger, guard=guard, supervisor=supervisor)
    ledger.close()
    if importlib.util.find_spec(MODULE) is not None:
        phase()._OBSERVERS.pop(guard, None)


def register(started):
    phase().register_phase_observer(started.guard, started.approval.role_graph_sha256)


def append(started, event=PHASES[0], payload=None):
    value = {"invocation_id": started.guard.invocation_id, "synthetic": {"rows": [1, 2]}}
    if payload is not None:
        value = payload
    return started.ledger._append_durable(event, value)


def read(started, event=PHASES[0], receipt=None):
    return phase().read_owned_phase_event(started.guard, event, receipt or append(started, event))


def assert_consumed(started):
    with pytest.raises(PermissionError):
        phase().require_phase_role_graph(started.guard)
    with pytest.raises(PermissionError):
        phase().register_phase_observer(started.guard, started.approval.role_graph_sha256)


def rewrite(started, records):
    previous = "0" * 64
    encoded = []
    for seq, record in enumerate(records):
        body = record["entry"]
        body.update(seq=seq, previous_sha256=previous)
        previous = hashlib.sha256(_canonical(body)).hexdigest()
        encoded.append(_canonical({"entry": body, "sha256": previous}) + b"\n")
    started.ledger.path.write_bytes(b"".join(encoded))
    started.ledger._tail = previous
    started.ledger._seq = len(records)


def test_four_owned_phases_advance_once_only_after_accept(started):
    register(started)
    for event in PHASES:
        receipt = append(started, event)
        proof = read(started, event, receipt)
        assert type(proof) is phase().OwnedPhaseEvent
        assert proof.event == event and proof.receipt is receipt
        assert proof.payload == {"invocation_id": started.guard.invocation_id, "synthetic": {"rows": [1, 2]}}
        phase().accept_owned_phase_event(started.guard, proof)
    assert phase().require_phase_role_graph(started.guard) == started.approval.role_graph_sha256.lower()
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, proof)
    assert_consumed(started)


def test_pin_is_frozen_independently_of_mutable_supervisor_fields(started):
    register(started)
    started.supervisor._approved_role_graph_sha256 = "e" * 64
    assert phase().require_phase_role_graph(started.guard) == started.approval.role_graph_sha256.lower()


@pytest.mark.parametrize("pin", [None, True, {}, "invalid", "e" * 64])
def test_registration_requires_exact_original_approved_role_graph_pin(started, pin):
    with pytest.raises(PermissionError):
        phase().register_phase_observer(started.guard, pin)


def test_registration_requires_live_startup_seq_two(started):
    append(started, "synthetic_note")
    with pytest.raises(PermissionError):
        register(started)


def test_registration_before_startup_cannot_create_an_observer(startup):
    approval, ledger, guard, supervisor, *_ = startup
    supervisor.bind_budget_guard(guard)
    with pytest.raises(PermissionError):
        phase().register_phase_observer(guard, approval.role_graph_sha256)
    assert not ledger.path.exists()


def test_unregistered_probe_does_not_poison_registered_guard(started):
    register(started)
    other = copy(started.guard)
    for operation in (
        lambda: phase().require_phase_role_graph(other),
        lambda: phase().read_owned_phase_event(other, PHASES[0], DurableEventReceipt("a" * 64, 1)),
        lambda: phase().accept_owned_phase_event(other, object()),
    ):
        with pytest.raises(PermissionError):
            operation()
    proof = read(started)
    phase().accept_owned_phase_event(started.guard, proof)


@pytest.mark.parametrize("event", [PHASES[1], PHASES[2], PHASES[3], "terminal", "unknown"])
def test_read_wrong_phase_consumes_only_its_observer(started, event):
    register(started)
    receipt = append(started, event)
    with pytest.raises(PermissionError):
        read(started, event, receipt)
    assert_consumed(started)


def test_read_without_accept_does_not_advance_and_pending_cannot_be_replaced(started):
    register(started)
    proof = read(started)
    receipt = append(started, PHASES[1])
    with pytest.raises(PermissionError):
        read(started, PHASES[1], receipt)
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, proof)
    assert_consumed(started)


@pytest.mark.parametrize("change", ["copy", "replace", "dict", "none", "payload", "event", "receipt"])
def test_accept_requires_original_proof_receipt_and_unchanged_payload(started, change):
    register(started)
    proof = read(started)
    if change == "copy":
        supplied = copy(proof)
    elif change == "replace":
        supplied = replace(proof)
    elif change == "dict":
        supplied = {"payload": proof.payload, "event": proof.event, "receipt": proof.receipt}
    elif change == "none":
        supplied = None
    else:
        supplied = proof
        if change == "payload":
            proof.payload["synthetic"]["rows"].append(3)
        elif change == "event":
            object.__setattr__(proof, "event", PHASES[1])
        else:
            object.__setattr__(proof, "receipt", replace(proof.receipt))
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, supplied)
    assert_consumed(started)


def test_accept_revalidates_original_receipt_values_even_after_object_mutation(started):
    register(started)
    proof = read(started)
    object.__setattr__(proof.receipt, "fsynced_monotonic_ns", proof.receipt.fsynced_monotonic_ns + 1)
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, proof)
    assert_consumed(started)


@pytest.mark.parametrize("value", [None, True, {}, SimpleNamespace(event_sha256="a" * 64, fsynced_monotonic_ns=1)])
def test_read_requires_exact_durable_event_receipt(started, value):
    register(started)
    append(started)
    with pytest.raises(PermissionError):
        phase().read_owned_phase_event(started.guard, PHASES[0], value)
    assert_consumed(started)


@pytest.mark.parametrize("change", ["hash", "boolean", "float", "before_start", "future", "subclass"])
def test_receipt_sha_time_and_exact_type_bind_actual_tail(started, change):
    register(started)
    original = append(started)
    if change == "hash":
        receipt = replace(original, event_sha256="e" * 64)
    elif change == "boolean":
        receipt = replace(original, fsynced_monotonic_ns=True)
    elif change == "float":
        receipt = replace(original, fsynced_monotonic_ns=float(original.fsynced_monotonic_ns))
    elif change == "before_start":
        receipt = replace(original, fsynced_monotonic_ns=started.guard._invocation_started_ns - 1)
    elif change == "future":
        receipt = replace(original, fsynced_monotonic_ns=time.monotonic_ns() + 10**15)
    else:
        class SubReceipt(DurableEventReceipt):
            pass
        receipt = SubReceipt(original.event_sha256, original.fsynced_monotonic_ns)
    with pytest.raises(PermissionError):
        read(started, receipt=receipt)
    assert_consumed(started)


@pytest.mark.parametrize("change", ["duplicate", "not_tail", "sequence", "tail", "partial", "noncanonical", "envelope", "startup", "invocation"])
def test_canonical_chain_startup_prefix_unique_phase_and_live_writer_are_fenced(started, change):
    register(started)
    receipt = append(started)
    if change == "duplicate":
        receipt = append(started)
    elif change == "not_tail":
        append(started, "synthetic_note")
    elif change == "sequence":
        started.ledger._seq += 1
    elif change == "tail":
        started.ledger._tail = "e" * 64
    elif change == "partial":
        started.ledger.path.write_bytes(started.ledger.path.read_bytes()[:-1])
    elif change == "noncanonical":
        started.ledger.path.write_bytes(b" " + started.ledger.path.read_bytes())
    else:
        records = [json.loads(line) for line in started.ledger.path.read_bytes().splitlines()]
        if change == "envelope":
            records[-1]["entry"]["extra"] = True
        elif change == "startup":
            records[0]["entry"]["payload"]["created_wall_ns"] += 1
        else:
            records[-1]["entry"]["payload"]["invocation_id"] = "another-invocation"
        rewrite(started, records)
        receipt = DurableEventReceipt(started.ledger._tail, time.monotonic_ns())
    with pytest.raises(PermissionError):
        read(started, receipt=receipt)
    assert_consumed(started)


def test_accept_reopens_and_rejects_tail_appended_after_read(started):
    register(started)
    proof = read(started)
    append(started, "synthetic_note")
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, proof)
    assert_consumed(started)


def test_owner_writer_fd_cannot_be_swapped_for_same_file(started):
    register(started)
    receipt = append(started)
    original = started.ledger._fd
    alternate = os.open(started.ledger.path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    started.ledger._fd = alternate
    try:
        with pytest.raises(PermissionError):
            read(started, receipt=receipt)
        assert_consumed(started)
    finally:
        started.ledger._fd = original
        os.close(alternate)


@pytest.mark.parametrize("attribute", ["st_dev", "st_ino", "st_mode", "st_nlink", "st_uid"])
def test_visible_path_identity_must_match_frozen_owner_fd(started, monkeypatch, attribute):
    register(started)
    receipt = append(started)
    original = os.stat
    def changed(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if os.fspath(path) == os.fspath(started.ledger.path):
            info = SimpleNamespace(**{name: getattr(info, name) for name in
                ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_size", "st_mtime_ns", "st_ctime_ns")})
            setattr(info, attribute, getattr(info, attribute) + 1)
        return info
    monkeypatch.setattr(phase().os, "stat", changed)
    with pytest.raises(PermissionError):
        read(started, receipt=receipt)
    assert_consumed(started)


def test_reader_uses_bounded_chunks_and_a_real_readonly_fd(started, monkeypatch):
    register(started)
    append(started, "synthetic_note", {"invocation_id": started.guard.invocation_id, "padding": "x" * 150000})
    receipt = append(started)
    reads, opens = [], []
    real_read, real_open = os.read, os.open
    def observed_read(fd, count):
        reads.append(count)
        assert fd != started.ledger._fd
        return real_read(fd, count)
    def observed_open(path, flags, *args, **kwargs):
        opens.append(flags)
        assert flags & os.O_RDWR == 0 and flags & os.O_WRONLY == 0
        for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
            assert flags & getattr(os, name, 0) == getattr(os, name, 0)
        return real_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(phase().os, "read", observed_read)
    monkeypatch.setattr(phase().os, "open", observed_open)
    proof = read(started, receipt=receipt)
    phase().accept_owned_phase_event(started.guard, proof)
    assert len(opens) == 2 and len(reads) >= 8
    assert max(reads) <= 65536 and reads[-1] == 1


@pytest.mark.parametrize("failure", ["read", "early_eof", "close", "changed_during_read"])
def test_real_observation_failures_consume_observer_and_close_once(started, monkeypatch, failure):
    register(started)
    receipt = append(started)
    real_read, real_close = os.read, os.close
    closed = []
    def broken_read(fd, maximum):
        if failure == "read":
            raise OSError("synthetic read failure")
        if failure == "early_eof":
            return b""
        encoded = real_read(fd, maximum)
        if failure == "changed_during_read" and encoded:
            append(started, "synthetic_note")
        return encoded
    def released_close(fd):
        closed.append(fd)
        real_close(fd)
        if failure == "close" and fd != started.ledger._fd:
            raise OSError("synthetic close after release")
    with monkeypatch.context() as context:
        context.setattr(phase().os, "read", broken_read)
        context.setattr(phase().os, "close", released_close)
        with pytest.raises((PermissionError, OSError)):
            read(started, receipt=receipt)
    assert len(closed) == 1
    assert_consumed(started)


@pytest.mark.parametrize("operation", ["pin", "read", "accept"])
def test_every_api_rejects_foreign_thread(started, operation):
    register(started)
    receipt = append(started)
    proof = read(started, receipt=receipt) if operation == "accept" else None
    errors = []
    def foreign():
        try:
            if operation == "pin":
                phase().require_phase_role_graph(started.guard)
            elif operation == "read":
                read(started, receipt=receipt)
            else:
                phase().accept_owned_phase_event(started.guard, proof)
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=foreign)
    thread.start()
    thread.join()
    assert len(errors) == 1 and isinstance(errors[0], PermissionError)


def test_startup_payload_getter_is_frozen_and_deep_copied(started):
    register(started)
    expected = json.loads(started.ledger.path.read_bytes().splitlines()[1])["entry"]["payload"]
    payload = phase().startup_owned_payload(started.guard)
    assert payload == expected
    payload["controller_receipt"]["controller_id"] = "tampered"
    started.supervisor.volume = object()
    assert phase().startup_owned_payload(started.guard) == expected


def test_accepted_getter_rejects_pending_and_returns_an_isolated_true_snapshot(started):
    register(started)
    proof = read(started)
    with pytest.raises(PermissionError):
        phase().accepted_owned_phase_event(started.guard, PHASES[0])
    phase().accept_owned_phase_event(started.guard, proof)
    accepted = phase().accepted_owned_phase_event(started.guard, PHASES[0])
    assert accepted.event == proof.event and accepted.receipt == proof.receipt
    assert accepted.payload == proof.payload
    accepted.payload["synthetic"]["rows"].append(42)
    object.__setattr__(accepted.receipt, "fsynced_monotonic_ns", 0)
    proof.payload["synthetic"]["rows"].append(99)
    again = phase().accepted_owned_phase_event(started.guard, PHASES[0])
    assert again.payload["synthetic"]["rows"] == [1, 2]
    assert again.receipt.fsynced_monotonic_ns > 0


def test_explicit_failure_consumes_pending_and_all_getters_without_io(started, monkeypatch):
    register(started)
    proof = read(started)
    def forbidden(*args, **kwargs):
        pytest.fail("explicit phase poison touched the filesystem")
    with monkeypatch.context() as context:
        for name in ("open", "read", "write", "fstat", "stat", "fsync"):
            context.setattr(phase().os, name, forbidden)
        phase().fail_phase_observer(started.guard)
        phase().fail_phase_observer(started.guard)
    for operation in (
        lambda: phase().startup_owned_payload(started.guard),
        lambda: phase().accepted_owned_phase_event(started.guard, PHASES[0]),
        lambda: phase().accept_owned_phase_event(started.guard, proof),
    ):
        with pytest.raises(PermissionError):
            operation()
    assert_consumed(started)


def test_failure_of_an_unregistered_copy_cannot_poison_original(started):
    register(started)
    with pytest.raises(PermissionError):
        phase().fail_phase_observer(copy(started.guard))
    phase().accept_owned_phase_event(started.guard, read(started))


def test_explicit_failure_with_lost_live_binding_still_consumes_original(started):
    register(started)
    original = started.guard.enforcer
    started.guard.enforcer = object()
    with pytest.raises(PermissionError):
        phase().fail_phase_observer(started.guard)
    started.guard.enforcer = original
    assert_consumed(started)


def accept_phases(started, count):
    for event in PHASES[:count]:
        phase().accept_owned_phase_event(started.guard, read(started, event))


@pytest.mark.parametrize("accepted", range(5))
@pytest.mark.parametrize("stage_a,fit", [(True, False), (True, True), (False, False), (False, True)])
def test_owned_work_uses_private_accepted_phase_not_healthy_public_flags(started, accepted, stage_a, fit):
    register(started)
    accept_phases(started, accepted)
    # Healthy public markers can be forged, including exactly the reported
    # exploit: after Stage A, flip admission without entry or expansion.
    started.guard._stage_b_admitted = True
    started.guard._stage_b_expansion_event_receipt = DurableEventReceipt("e" * 64, time.monotonic_ns())
    started.guard._boundary_failure = None
    started.supervisor.state = "forged-ready"
    allowed = (accepted == 0 and stage_a and not fit) or (accepted == 3 and not stage_a)
    touched_operation = []
    if allowed:
        phase().require_owned_work(started.guard, stage_a=stage_a, fit=fit)
        touched_operation.append(True)
        assert phase().require_phase_role_graph(started.guard) == started.approval.role_graph_sha256.lower()
        assert len(phase()._OBSERVERS[started.guard].accepted) == accepted
        assert phase()._OBSERVERS[started.guard].pending is None
    else:
        with pytest.raises(PermissionError):
            phase().require_owned_work(started.guard, stage_a=stage_a, fit=fit)
            touched_operation.append(True)
        assert not touched_operation
        # Resetting the public admission/failure markers cannot undo poison.
        started.guard._stage_b_admitted = False
        started.guard._boundary_failure = None
        with pytest.raises(PermissionError):
            phase().require_owned_work(started.guard, stage_a=True, fit=False)
        assert_consumed(started)


@pytest.mark.parametrize("accepted,stage_a,fit", [(0, True, False), (3, False, False), (3, False, True)])
def test_owned_work_rejects_even_allowed_phase_while_proof_is_pending(started, accepted, stage_a, fit):
    register(started)
    accept_phases(started, accepted)
    proof = read(started, PHASES[accepted])
    with pytest.raises(PermissionError):
        phase().require_owned_work(started.guard, stage_a=stage_a, fit=fit)
    with pytest.raises(PermissionError):
        phase().accept_owned_phase_event(started.guard, proof)
    assert_consumed(started)


@pytest.mark.parametrize("parameter", ["stage_a", "fit"])
@pytest.mark.parametrize("value", [0, 1, None, "false", {}, []])
def test_owned_work_requires_exact_boolean_arguments_and_consumes_on_confusion(started, parameter, value):
    register(started)
    supplied = {"stage_a": True, "fit": False, parameter: value}
    with pytest.raises(PermissionError):
        phase().require_owned_work(started.guard, **supplied)
    assert_consumed(started)


@pytest.mark.parametrize("change", ["controller", "path", "writer", "thread", "pid"])
def test_owned_work_requires_live_original_binding_and_storage_identity(started, monkeypatch, change):
    register(started)
    if change == "controller":
        original = started.guard.enforcer
        started.guard.enforcer = object()
    elif change == "writer":
        original = started.ledger._fd
        started.ledger._fd = None
    elif change == "path":
        # Existing original held writer does not authorize a replaced path.
        target = started.ledger.path.with_suffix(".replacement")
        target.write_bytes(started.ledger.path.read_bytes())
        real_stat = os.stat
        def replaced(path, *args, **kwargs):
            if os.fspath(path) == os.fspath(started.ledger.path):
                return real_stat(target, *args, **kwargs)
            return real_stat(path, *args, **kwargs)
        monkeypatch.setattr(phase().os, "stat", replaced)
    elif change == "thread":
        errors = []
        def foreign():
            try:
                phase().require_owned_work(started.guard, stage_a=True, fit=False)
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join()
        assert len(errors) == 1 and isinstance(errors[0], PermissionError)
        assert_consumed(started)
        return
    else:
        original = os.getpid()
        with monkeypatch.context() as context:
            context.setattr(phase().os, "getpid", lambda: original + 1)
            with pytest.raises(PermissionError):
                phase().require_owned_work(started.guard, stage_a=True, fit=False)
        assert_consumed(started)
        return
    try:
        with pytest.raises(PermissionError):
            phase().require_owned_work(started.guard, stage_a=True, fit=False)
    finally:
        if change == "controller":
            started.guard.enforcer = original
        elif change == "writer":
            started.ledger._fd = original
    assert_consumed(started)


def test_owned_work_unregistered_copy_cannot_acquire_or_poison_original(started):
    register(started)
    with pytest.raises(PermissionError):
        phase().require_owned_work(copy(started.guard), stage_a=True, fit=False)
    phase().require_owned_work(started.guard, stage_a=True, fit=False)


def test_owned_work_is_readonly_and_does_not_advance_phase_or_issue_proof(started, monkeypatch):
    register(started)
    accept_phases(started, 3)
    initial = started.ledger.path.read_bytes()
    sequence, tail = started.ledger._seq, started.ledger._tail
    def forbidden(*args, **kwargs):
        pytest.fail("owned work gate wrote or opened the journal")
    with monkeypatch.context() as context:
        for name in ("open", "write", "fsync", "close"):
            context.setattr(phase().os, name, forbidden)
        assert phase().require_owned_work(started.guard, stage_a=False, fit=True) is None
        assert phase().require_owned_work(started.guard, stage_a=False, fit=False) is None
    assert started.ledger.path.read_bytes() == initial
    assert (started.ledger._seq, started.ledger._tail) == (sequence, tail)
    assert len(phase()._OBSERVERS[started.guard].accepted) == 3
    assert phase()._OBSERVERS[started.guard].pending is None


def test_owned_work_cannot_restore_an_explicitly_failed_observer(started):
    register(started)
    accept_phases(started, 3)
    phase().fail_phase_observer(started.guard)
    started.guard._stage_b_admitted = True
    started.guard._boundary_failure = None
    with pytest.raises(PermissionError):
        phase().require_owned_work(started.guard, stage_a=False, fit=True)
    assert_consumed(started)
