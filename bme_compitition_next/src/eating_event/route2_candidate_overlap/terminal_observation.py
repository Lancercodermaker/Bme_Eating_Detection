"""Original-owner terminal hooks and a bounded readonly close handoff.

Integration must register at startup sequence two, call prepare from the native
BudgetGuard.finalize immediately before ledger.terminal, merge its evidence,
and call the before/after hooks around the native ledger.close. This module
never writes or closes the owner's ledger and never performs external acceptance.

The Linux worker/GT syscall collector is in linux_quiescence. Its native
original role-controller/GT identity/complete-history channel remains missing,
so production receipt issuance still fails closed. Synthetic fixtures mock
this private source; journal/lock/hashchain/descriptor verification is native.
Python modules and these private registries belong to the trusted controller;
runtime replacement of native owner methods is refused, not an extension API.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import json
import os
import sys
import threading
import time
import uuid
import weakref

from . import phase_observation as phase
from . import budget as _budget
from .budget import AppendOnlyLedger, BudgetGuard, _canonical
from .contracts import STUDY_ID, StudyStatus
from .linux_supervisor import TerminalCloseReceipt
from .startup_ownership import require_startup_binding


_FINALIZE = BudgetGuard.finalize
_LEDGER_METHODS = {name: getattr(AppendOnlyLedger, name) for name in ("terminal", "append", "close")}
_OBSERVERS = weakref.WeakKeyDictionary()
_LOCK = threading.RLock()
_MAX_BYTES = 16 * 1024 * 1024
_CHUNK_BYTES = 65536


@dataclass(frozen=True, slots=True)
class _Quiescence:
    controller: object
    invocation_id: str
    pid: int
    cgroup_path: str
    controller_pids: tuple[int, ...]
    worker_pids: tuple[int, ...]
    gt_mount_ids: tuple[int, ...]
    sampled_monotonic_ns: int


@dataclass(slots=True)
class _Observer:
    binding: object
    phase: object
    owner_fd: int
    identity: tuple[int, ...]
    startup_hashes: tuple[str, ...]
    startup_payload: bytes
    role_graph: str
    limits_sha256: str
    deadline_ns: int
    lock_frame: tuple[int, ...]
    lock_sha256: str
    step: str = "registered"
    failed: bool = False
    accepted: tuple = ()
    phase_was_failed: bool = False
    frame_id: int | None = None
    status: str = ""
    prepared_ns: int = 0
    chain: bytes = b""
    before_bytes: bytes = b""
    before_seq: int = 0
    before_tail: str = ""
    terminal_bytes: bytes = b""
    terminal_frame: tuple[int, ...] = ()
    terminal_seq: int = 0
    terminal_digest: str = ""
    before_close_ns: int = 0
    closed_ns: int = 0
    anchor_fd: int | None = None


def _deny(message):
    raise PermissionError(message)


def _state(guard):
    if type(guard) is not BudgetGuard:
        _deny("terminal observer requires its original BudgetGuard")
    state = _OBSERVERS.get(guard)
    if state is None or state.failed:
        _deny("terminal observer is absent or consumed")
    return state


def _consume(state, error):
    state.failed = True
    with phase._LOCK:
        state.phase.failed = True
        state.phase.pending = None
    try:
        _release_anchor(state)
    except BaseException:
        # Every owned descriptor was popped before close; never retry its number.
        pass
    if isinstance(error, PermissionError) or not isinstance(error, Exception):
        raise error
    raise PermissionError("owned terminal verification failed and was consumed") from error


def _release_anchor(state):
    descriptor, state.anchor_fd = state.anchor_fd, None
    if descriptor is not None:
        os.close(descriptor)


def _gc_release_anchor(state):
    try:
        _release_anchor(state)
    except BaseException:
        pass


def _native_methods(guard):
    method = guard.finalize
    if getattr(method, "__self__", None) is not guard or getattr(method, "__func__", None) is not _FINALIZE:
        _deny("terminal owner finalize method was replaced")
    for name, function in _LEDGER_METHODS.items():
        method = getattr(guard.ledger, name)
        if getattr(method, "__self__", None) is not guard.ledger or getattr(method, "__func__", None) is not function:
            _deny("terminal writer/close must retain the native owner methods")


def _binding(guard, state):
    binding = require_startup_binding(guard)
    ledger = state.binding.ledger
    if (binding is not state.binding or type(ledger) is not AppendOnlyLedger
            or ledger._owner_thread_id != threading.get_ident()
            or ledger._invocation_id != binding.invocation_id
            or type(ledger._invocation_started_monotonic_ns) is not int
            or ledger._invocation_started_monotonic_ns != binding.started_ns
            or guard._started is not True or ledger._poisoned is not False
            or type(ledger._seq) is not int or type(ledger._tail) is not str
            or phase._digest(ledger._tail) != ledger._tail
            or binding.limits.digest() != state.limits_sha256):
        _deny("terminal observer lost its original owner, writer, clock or limits")
    _native_methods(guard)
    with phase._LOCK:
        original = phase._OBSERVERS.get(guard)
        if (original is not state.phase or original.binding is not binding
                or original.owner_fd != state.owner_fd or original.identity != state.identity
                or original.startup_hashes != state.startup_hashes
                or original.startup_payload != state.startup_payload or original.role_graph != state.role_graph):
            _deny("terminal observer's private phase/startup anchors drifted")


def _finalize_frame(guard, state):
    _binding(guard, state)
    frame = sys._getframe(1)
    for _ in range(12):
        if frame is None:
            break
        if frame.f_code is _FINALIZE.__code__ and frame.f_locals.get("self") is guard:
            if state.frame_id is not None and id(frame) != state.frame_id:
                _deny("terminal hooks belong to a different owner finalize invocation")
            return frame
        frame = frame.f_back
    _deny("terminal hook requires the native BudgetGuard.finalize invocation")


def _read_file(path, *, expected=None, owner_fd=None, maximum=_MAX_BYTES):
    """One real RO descriptor, bounded chunks/EOF and full stat fences."""
    visible = phase._frame(os.stat(path, follow_symlinks=False))
    if visible[5] > maximum or (expected is not None and visible != expected):
        _deny("terminal file exceeds its bound or changed from its frozen frame")
    if owner_fd is not None and phase._frame(os.fstat(owner_fd)) != visible:
        _deny("terminal visible journal differs from the held writer")
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    descriptor = os.open(path, flags)
    try:
        before = phase._frame(os.fstat(descriptor))
        if before != visible:
            _deny("terminal readonly file identity changed during open")
        remaining = before[5]
        chunks = []
        while remaining:
            limit = min(remaining, _CHUNK_BYTES)
            data = os.read(descriptor, limit)
            if type(data) is not bytes or not data or len(data) > limit:
                _deny("terminal readonly bounded stream ended early")
            chunks.append(data)
            remaining -= len(data)
        if os.read(descriptor, 1) != b"":
            _deny("terminal readonly stream exceeded its original size")
        if (phase._frame(os.fstat(descriptor)) != before
                or phase._frame(os.stat(path, follow_symlinks=False)) != before
                or (owner_fd is not None and phase._frame(os.fstat(owner_fd)) != before)):
            _deny("terminal file size/time/identity changed during read")
        return b"".join(chunks), before
    finally:
        # Close is attempted once, including close-after-release errors.
        os.close(descriptor)


def _open_anchor(state):
    ledger = state.binding.ledger
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    state.anchor_fd = os.open(ledger.path, flags)
    _anchor_frame(state)
    if phase._frame(os.fstat(state.owner_fd)) != state.terminal_frame:
        _deny("terminal readonly anchor differs from its original writer")


def _anchor_frame(state):
    if (type(state.anchor_fd) is not int or state.anchor_fd == state.owner_fd
            or phase._frame(os.fstat(state.anchor_fd)) != state.terminal_frame
            or phase._frame(os.stat(state.binding.ledger.path, follow_symlinks=False)) != state.terminal_frame):
        _deny("terminal held readonly anchor or visible journal changed")


def _read_anchor(state):
    _anchor_frame(state)
    if os.lseek(state.anchor_fd, 0, os.SEEK_SET) != 0:
        _deny("terminal readonly anchor could not rewind")
    remaining = state.terminal_frame[5]
    chunks = []
    while remaining:
        limit = min(remaining, _CHUNK_BYTES)
        data = os.read(state.anchor_fd, limit)
        if type(data) is not bytes or not data or len(data) > limit:
            _deny("terminal readonly anchor stream ended early")
        chunks.append(data)
        remaining -= len(data)
    if os.read(state.anchor_fd, 1) != b"":
        _deny("terminal readonly anchor grew beyond its bound")
    _anchor_frame(state)
    return b"".join(chunks)


def _lock_file(state):
    data, _ = _read_file(state.binding.ledger.lock_path, expected=state.lock_frame, maximum=_CHUNK_BYTES)
    if hashlib.sha256(data).hexdigest() != state.lock_sha256:
        _deny("terminal one-shot lock bytes changed")
    lock = json.loads(data)
    if (type(lock) is not dict or set(lock) != {"study_id", "lock_id"} or _canonical(lock) != data
            or lock["study_id"] != STUDY_ID or type(lock["lock_id"]) is not str):
        _deny("terminal one-shot lock envelope is not canonical")
    lock_id = uuid.UUID(lock["lock_id"])
    if lock_id.version != 4 or str(lock_id) != lock["lock_id"]:
        _deny("terminal one-shot lock identity is invalid")


def _accepted(state):
    with phase._LOCK:
        current = state.phase
        if current.pending is not None or type(current.failed) is not bool:
            _deny("terminal cannot freeze an unaccepted pending phase")
        accepted = tuple((item.event, item.payload, item.receipt_values) for item in current.accepted)
    if tuple(item[0] for item in accepted) != phase._PHASES[:len(accepted)] or len(accepted) > 4:
        _deny("terminal private accepted phase order is invalid")
    return accepted


def _chain(state):
    accepted = state.accepted
    payload = [json.loads(item[1]) for item in accepted]
    def value(index, name):
        return payload[index][name] if index < len(payload) else None
    def digest(index):
        return accepted[index][2][0] if index < len(accepted) else None
    def timestamp(index):
        return accepted[index][2][1] if index < len(accepted) else None
    return {
        "study_id": STUDY_ID, "invocation_id": state.binding.invocation_id,
        "role_graph_sha256": state.role_graph,
        "stage_a_event_sha256": digest(0), "stage_a_finished_monotonic_ns": value(0, "finished_monotonic_ns"),
        "stage_a_fsynced_monotonic_ns": timestamp(0),
        "stage_b_entry_event_sha256": digest(1), "stage_b_entry_fsynced_monotonic_ns": timestamp(1),
        "stage_b_expansion_event_sha256": digest(2), "stage_b_expansion_fsynced_monotonic_ns": timestamp(2),
        "stage_b_completion_event_sha256": digest(3),
        "stage_b_completion_finished_monotonic_ns": value(3, "finished_monotonic_ns"),
        "stage_b_completion_fsynced_monotonic_ns": timestamp(3),
        "stage_b_call_event_count": value(3, "call_event_count"),
        "stage_b_call_event_accounting_sha256": value(3, "call_event_accounting_sha256"),
        "stage_b_result_sha256": value(3, "result_sha256"),
    }


def _records(state, data, seq, tail):
    records = phase._parse(data, seq, tail)
    if tuple(record["sha256"] for record in records[:2]) != state.startup_hashes:
        _deny("terminal startup prefix digests changed")
    if _canonical(records[1]["entry"]["payload"]) != state.startup_payload:
        _deny("terminal invocation startup payload changed")
    phases = [record for record in records if record["entry"]["event"] in phase._PHASES]
    names = tuple(record["entry"]["event"] for record in phases)
    allowed_extra = 1 if state.phase_was_failed and state.status != "COMPLETE" else 0
    if (names != phase._PHASES[:len(names)] or len(phases) < len(state.accepted)
            or len(phases) > len(state.accepted) + allowed_extra):
        _deny("terminal ledger phase order differs from its private accepted prefix")
    for record, (event, payload, receipt) in zip(phases, state.accepted):
        if record["sha256"] != receipt[0].lower() or _canonical(record["entry"]["payload"]) != payload:
            _deny("terminal accepted phase bytes or receipt digest changed")
    return records


def _result_sha(state, evidence):
    if len(state.accepted) == 4:
        completion = json.loads(state.accepted[3][1])
        expected = phase._digest(completion["result_sha256"])
        result = evidence.get("stage_b_result")
        if type(result) is not dict or hashlib.sha256(_canonical(result)).hexdigest() != expected:
            _deny("terminal result bytes differ from the privately accepted completion SHA256")


def register_terminal_observer(guard) -> None:
    """Register only the original owner and authentic startup phase registry."""
    with _LOCK:
        if type(guard) is not BudgetGuard or guard in _OBSERVERS:
            _deny("terminal observer registration requires a fresh original guard")
        binding = require_startup_binding(guard)
        with phase._LOCK:
            current = phase._state(guard)
            phase._live_identity(guard, current)
            if binding is None or current.binding is not binding or binding.ledger._seq != 2:
                _deny("terminal observer must register at the bound startup sequence two")
            ledger = binding.ledger
            state = _Observer(binding, current, current.owner_fd, current.identity, current.startup_hashes,
                              current.startup_payload, current.role_graph, binding.limits.digest(),
                              binding.started_ns + binding.limits.total_wall_ns,
                              ledger._lock_identity, ledger._lock_sha256)
        _OBSERVERS[guard] = state
        # The weak registry must not leak a held readonly descriptor if its
        # original guard disappears before the caller invokes the failure hook.
        weakref.finalize(guard, _gc_release_anchor, state)
        try:
            _binding(guard, state)
            if (type(state.lock_frame) is not tuple or len(state.lock_frame) != 8
                    or any(type(item) is not int for item in state.lock_frame)
                    or phase._digest(state.lock_sha256) != state.lock_sha256):
                _deny("terminal startup one-shot lock anchor is missing")
            _lock_file(state)
        except BaseException as exc:
            _consume(state, exc)


def prepare_owned_terminal(guard) -> dict:
    """Native finalize hook before terminal append; returns reserved evidence."""
    with _LOCK:
        state = _state(guard)
        try:
            frame = _finalize_frame(guard, state)
            ledger = state.binding.ledger
            status = frame.f_locals.get("status")
            if (state.step != "registered" or ledger._terminal is not False
                    or type(ledger._fd) is not int or ledger._fd != state.owner_fd
                    or type(status) is not str or status not in {item.value for item in StudyStatus}):
                _deny("terminal preparation requires one native live owner append")
            state.accepted = _accepted(state)
            state.phase_was_failed = state.phase.failed
            if status == "COMPLETE" and (state.phase_was_failed or len(state.accepted) != 4):
                _deny("COMPLETE requires four healthy privately accepted owner phases")
            state.status = status
            state.chain = _canonical(_chain(state))
            markers = {"route2_supervisor_chain": json.loads(state.chain),
                       "route2_supervisor_chain_sha256": hashlib.sha256(state.chain).hexdigest()}
            evidence = frame.f_locals.get("evidence")
            if type(evidence) is not dict or any(key in evidence and _canonical(evidence[key]) != _canonical(value)
                                               for key, value in markers.items()):
                _deny("terminal caller evidence conflicts with the private owner chain")
            _result_sha(state, evidence)
            _lock_file(state)
            data, info = _read_file(ledger.path, owner_fd=state.owner_fd)
            if info[:5] != state.identity:
                _deny("terminal preparation journal identity changed")
            seq, tail = phase._writer(state.phase)
            records = _records(state, data, seq, tail)
            if any(record["entry"]["event"] == "terminal" for record in records):
                _deny("terminal preparation found a previous terminal")
            state.before_bytes, state.before_seq, state.before_tail = data, seq, tail
            state.frame_id = id(frame)
            state.prepared_ns = time.monotonic_ns()
            state.step = "prepared"
            with phase._LOCK:
                state.phase.failed = True  # terminal entry permanently stops work
            return markers
        except BaseException as exc:
            _consume(state, exc)


def _terminal_record(state, records):
    terminal_records = [record for record in records if record["entry"]["event"] == "terminal"]
    if len(terminal_records) != 1 or terminal_records[0] is not records[-1]:
        _deny("terminal must be the unique final canonical ledger record")
    payload = records[-1]["entry"]["payload"]
    if (set(payload) != {"status", "evidence", "wall_ns", "monotonic_ns", "epoch_ns"}
            or type(payload["status"]) is not str or payload["status"] != state.status
            or type(payload["evidence"]) is not dict
            or any(type(payload[name]) is not int for name in ("wall_ns", "monotonic_ns", "epoch_ns"))
            or not state.prepared_ns <= payload["monotonic_ns"] <= time.monotonic_ns()
            or payload["wall_ns"] != payload["monotonic_ns"] - state.binding.started_ns
            or payload["epoch_ns"] <= 0
            or _canonical(payload["evidence"].get("route2_supervisor_chain")) != state.chain
            or payload["evidence"].get("route2_supervisor_chain_sha256") != hashlib.sha256(state.chain).hexdigest()):
        _deny("terminal status, times or evidence differ from the private native owner append")
    if state.accepted and payload["monotonic_ns"] < state.accepted[-1][2][1]:
        _deny("terminal event precedes its last accepted phase fsync")
    _result_sha(state, payload["evidence"])
    return payload


def before_owned_terminal_close(guard) -> None:
    """Native finalize hook after terminal fsync and immediately before close."""
    with _LOCK:
        state = _state(guard)
        try:
            frame = _finalize_frame(guard, state)
            ledger = state.binding.ledger
            if (state.step != "prepared" or frame.f_locals.get("status") != state.status
                    or ledger._terminal is not True or type(ledger._fd) is not int or ledger._fd != state.owner_fd
                    or _accepted(state) != state.accepted):
                _deny("terminal close hook lacks its private native append or phase anchors")
            _lock_file(state)
            data, info = _read_file(ledger.path, owner_fd=state.owner_fd)
            seq, tail = phase._writer(state.phase)
            if (info[:5] != state.identity or seq != state.before_seq + 1
                    or not data.startswith(state.before_bytes) or ledger._terminal_sha256 != tail):
                _deny("terminal append changed the original journal or its current tail")
            records = _records(state, data, seq, tail)
            _terminal_record(state, records)
            if records[-1]["entry"]["previous_sha256"] != state.before_tail:
                _deny("terminal append predecessor differs from its private preparation")
            state.terminal_bytes, state.terminal_frame = data, info
            state.terminal_seq, state.terminal_digest = seq, tail
            _open_anchor(state)
            state.before_close_ns = time.monotonic_ns()
            state.step = "before_close"
        except BaseException as exc:
            _consume(state, exc)


def _actually_closed(state):
    # EBADF and public close-clock fields cannot authenticate a successful
    # native close. Budget owns the immutable original-FD success/failure fact;
    # this pure query must raise unless that exact native attempt succeeded.
    require_success = getattr(_budget, "require_owned_ledger_close_success", None)
    if not callable(require_success):
        _deny("private native ledger close-success query is missing")
    require_success(state.binding.ledger, state.owner_fd)
    try:
        os.fstat(state.owner_fd)
    except OSError as exc:
        if exc.errno == errno.EBADF:
            return
        raise
    _deny("original terminal writer descriptor is still open or its number was reused")


def after_owned_terminal_close(guard) -> None:
    """Native finalize hook after successful close, before returning status."""
    with _LOCK:
        state = _state(guard)
        try:
            frame = _finalize_frame(guard, state)
            ledger = state.binding.ledger
            if (state.step != "before_close" or frame.f_locals.get("status") != state.status
                    or ledger._fd is not None or guard._finished is not True
                    or (ledger._seq, ledger._tail, ledger._terminal_sha256)
                    != (state.terminal_seq, state.terminal_digest, state.terminal_digest)):
                _deny("terminal after-close hook lacks the original owner close")
            _actually_closed(state)
            _anchor_frame(state)
            closed = ledger.closed_at_monotonic_ns
            if (type(closed) is not int or not state.before_close_ns <= closed <= time.monotonic_ns()
                    or (state.status != "INCOMPLETE_RESOURCE" and closed > state.deadline_ns)):
                _deny("terminal close time is outside its original start/close/deadline frame")
            state.closed_ns = closed
            state.step = "closed"
        except BaseException as exc:
            _consume(state, exc)


def _require_controller_quiescence(guard, binding, cgroup_path):
    """Use the concrete readonly Linux source; missing native history refuses."""
    from .linux_quiescence import require_linux_terminal_quiescence

    sample = require_linux_terminal_quiescence(guard, binding, cgroup_path)
    return _Quiescence(sample.controller, sample.invocation_id, sample.pid,
                       sample.cgroup_path, sample.controller_pids, sample.worker_pids,
                       sample.gt_mount_ids, sample.sampled_monotonic_ns)


def _quiescence(guard, state):
    startup = json.loads(state.startup_payload)
    path = startup["controller_receipt"]["parent_cgroup_path"]
    parts = path.split("/") if type(path) is str else []
    if (len(parts) != 3 or parts[:2] != ["", "system.slice"]
            or not parts[2].endswith(".service") or any(char.isspace() for char in path)):
        _deny("terminal startup controller service identity is invalid")
    sample = _require_controller_quiescence(guard, state.binding, path)
    if (type(sample) is not _Quiescence or sample.controller is not state.binding.controller
            or type(sample.invocation_id) is not str or sample.invocation_id != state.binding.invocation_id
            or type(sample.cgroup_path) is not str or sample.cgroup_path != path
            or type(sample.pid) is not int or sample.pid != state.binding.pid
            or type(sample.controller_pids) is not tuple or sample.controller_pids != (sample.pid,)
            or any(type(pid) is not int for pid in sample.controller_pids)
            or type(sample.worker_pids) is not tuple or sample.worker_pids != ()
            or type(sample.gt_mount_ids) is not tuple or sample.gt_mount_ids != ()
            or type(sample.sampled_monotonic_ns) is not int
            or not state.closed_ns <= sample.sampled_monotonic_ns <= time.monotonic_ns()):
        _deny("terminal worker/GT quiescence is not exact live original-controller evidence")
    return parts[2]


def read_owned_terminal_close(guard) -> TerminalCloseReceipt:
    """One readonly handoff to the bound owner; never external acceptance."""
    with _LOCK:
        state = _state(guard)
        try:
            _binding(guard, state)
            ledger = state.binding.ledger
            if (state.step != "closed" or ledger._fd is not None or ledger._terminal is not True
                    or type(ledger.closed_at_monotonic_ns) is not int
                    or ledger.closed_at_monotonic_ns != state.closed_ns
                    or (ledger._seq, ledger._tail, ledger.terminal_sha256)
                    != (state.terminal_seq, state.terminal_digest, state.terminal_digest)
                    or _accepted(state) != state.accepted):
                _deny("terminal handoff lacks its original privately observed close")
            _actually_closed(state)
            _lock_file(state)
            data = _read_anchor(state)
            if data != state.terminal_bytes:
                _deny("closed terminal bytes changed before readonly handoff")
            records = _records(state, data, state.terminal_seq, state.terminal_digest)
            payload = _terminal_record(state, records)
            if not state.binding.started_ns <= payload["monotonic_ns"] <= state.closed_ns <= time.monotonic_ns():
                _deny("terminal event/start/close clock interval changed")
            _actually_closed(state)
            unit = _quiescence(guard, state)
            _binding(guard, state)
            _actually_closed(state)
            _anchor_frame(state)
            if (phase._frame(os.stat(ledger.lock_path, follow_symlinks=False)) != state.lock_frame
                    or type(ledger.closed_at_monotonic_ns) is not int or ledger.closed_at_monotonic_ns != state.closed_ns
                    or ledger._fd is not None or ledger._terminal is not True
                    or (ledger._seq, ledger._tail, ledger.terminal_sha256)
                    != (state.terminal_seq, state.terminal_digest, state.terminal_digest)
                    or _accepted(state) != state.accepted):
                _deny("terminal storage, phase or live close changed during controller sampling")
            _release_anchor(state)  # close failure rejects handoff, never retries
            state.step = "handed_off"
            return TerminalCloseReceipt(state.binding.invocation_id, unit, state.status, state.terminal_digest,
                                        hashlib.sha256(state.chain).hexdigest(), state.binding.started_ns,
                                        state.closed_ns, state.deadline_ns, True, True, True, True,
                                        data.splitlines(keepends=True)[-1], data)
        except BaseException as exc:
            _consume(state, exc)


def fail_owned_terminal(guard) -> None:
    """Finalize exception hook: poison and release only our readonly anchor.

    Caller remains responsible for owner-ledger cleanup. Repeating a native
    close after an error is forbidden; this hook never closes that descriptor.
    """
    with _LOCK:
        if type(guard) is not BudgetGuard:
            _deny("terminal failure requires its original registered guard")
        state = _OBSERVERS.get(guard)
        if state is None:
            _deny("terminal failure has no original registered observer")
        state.failed = True
        with phase._LOCK:
            state.phase.failed = True
            state.phase.pending = None
        _release_anchor(state)
        # A poisoned native ledger or replaced close method must still allow
        # cleanup of our readonly FD. This issues no proof or work permission.
        if require_startup_binding(guard) is not state.binding:
            _deny("terminal failure lost its original startup owner binding")
