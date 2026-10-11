"""Bounded, read-only provenance for the original startup owner's phase events.

This observer issues no execution/admission capability. It does not prove the
Stage A role replay, scientific results, resource enforcement or GT isolation.
The private registry belongs to the trusted controller process. Windows is
supported for temporary synthetic journals; Linux opens use NOFOLLOW/NONBLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import hashlib
import json
import os
import platform
import re
import stat
import sys
import threading
import time
import weakref

from .budget import AppendOnlyLedger, BudgetGuard, DurableEventReceipt, _canonical
from .native_failure_capture import NativeFailureCapture
from .startup_ownership import registered_startup, require_startup_binding


_PHASES = ("stage_a_finished", "stage_b_entry_passed", "stage_b_volume_expanded", "stage_b_complete")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_MAX_BYTES = 16 * 1024 * 1024
_CHUNK_BYTES = 65536
_OBSERVERS = weakref.WeakKeyDictionary()
_LOCK = threading.RLock()
_FINALIZE = BudgetGuard.finalize


@dataclass(frozen=True, slots=True)
class _OFDAnchor:
    descriptor: int
    owner_fd: int
    identity: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class OwnedPhaseEvent:
    payload: dict
    event: str
    receipt: DurableEventReceipt


@dataclass(frozen=True, slots=True)
class _Accepted:
    event: str
    payload: bytes
    receipt_values: tuple[str, int]


@dataclass(frozen=True, slots=True)
class _Journal:
    records: tuple[dict, ...]
    frame: tuple[int, ...]
    seq: int
    tail: str


@dataclass(frozen=True, slots=True)
class _Pending:
    proof: OwnedPhaseEvent
    payload: bytes
    receipt: DurableEventReceipt
    receipt_values: tuple[str, int]
    journal: _Journal


@dataclass(slots=True)
class _Observer:
    binding: object
    role_graph: str
    owner_fd: int
    identity: tuple[int, ...]
    startup_hashes: tuple[str, ...] = ()
    startup_payload: bytes = b""
    accepted: list[_Accepted] = field(default_factory=list)
    _pending: _Pending | None = None
    failed: bool = False
    ofd_anchor: _OFDAnchor | None = None
    ofd_released: bool = False

    @property
    def pending(self):
        return self._pending

    @pending.setter
    def pending(self, value):
        self._pending = value
        if value is None and self.failed:
            # Native terminal failure already invalidates the phase this way.
            # Preparation only sets failed, retaining the anchor until its
            # final writer comparison. Failure cleanup issues no close proof.
            _gc_release_ofd_anchor(self)


def _deny(message: str) -> None:
    raise PermissionError(message)


def _digest(value) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _deny("phase digest must be an exact SHA256 string")
    return value.lower()


def _identity(info) -> tuple[int, ...]:
    values = tuple(getattr(info, name) for name in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid"))
    if any(type(value) is not int for value in values) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _deny("phase journal must remain a single-link regular file")
    return values


def _frame(info) -> tuple[int, ...]:
    extra = tuple(getattr(info, name) for name in ("st_size", "st_mtime_ns", "st_ctime_ns"))
    if any(type(value) is not int for value in extra) or not 0 < info.st_size <= _MAX_BYTES:
        _deny("phase journal exceeds the bounded byte frame")
    return _identity(info) + extra


def _state(guard) -> _Observer:
    if type(guard) is not BudgetGuard:
        _deny("phase observer requires its original BudgetGuard")
    state = _OBSERVERS.get(guard)
    if state is None:
        _deny("phase observer is not registered for this guard")
    if state.failed:
        _deny("phase observer has been consumed")
    return state


def _binding(guard, state: _Observer) -> None:
    binding = require_startup_binding(guard)
    if binding is None or binding is not state.binding or registered_startup(guard) is not state.binding:
        _deny("phase observer lost its original startup binding")
    ledger = binding.ledger
    if (type(ledger) is not AppendOnlyLedger or type(ledger._fd) is not int
            or ledger._fd != state.owner_fd or ledger._owner_thread_id != threading.get_ident()
            or ledger._invocation_id != binding.invocation_id
            or type(ledger._invocation_started_monotonic_ns) is not int
            or ledger._invocation_started_monotonic_ns != binding.started_ns
            or guard._started is not True or ledger._poisoned is not False or ledger._terminal is not False):
        _deny("phase observer requires the original live ledger writer")
    _require_writer_ofd(state)


def _same_open_description(descriptor, reference):
    """Native KCMP_FILE equality; denied/unsupported/ambiguous means refusal."""
    number = {"x86_64": 312, "aarch64": 272}.get(platform.machine())
    if (platform.system() != "Linux" or number is None
            or ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(ctypes.c_long) != 8
            or any(type(value) is not int or value < 0 for value in (descriptor, reference))
            or descriptor == reference):
        _deny("phase OFD identity requires two distinct FDs and a supported Linux 64-bit ABI")
    function = ctypes.CDLL(None, use_errno=True).syscall
    function.argtypes, function.restype = (ctypes.c_long,), ctypes.c_long
    pid = os.getpid()
    ctypes.set_errno(0)
    result = function(ctypes.c_long(number), ctypes.c_int(pid), ctypes.c_int(pid),
                      ctypes.c_int(0), ctypes.c_ulong(descriptor), ctypes.c_ulong(reference))
    if result < 0:
        error = ctypes.get_errno()
        raise PermissionError("native KCMP_FILE comparison is unavailable or denied") from OSError(error, os.strerror(error))
    if result != 0:
        _deny("phase original writer OFD was replaced or its kernel comparison is ambiguous")


def _require_writer_ofd(state):
    if os.name != "posix":
        return  # Existing Windows synthetic journal support; never Linux authority.
    anchor = state.ofd_anchor
    if (type(anchor) is not _OFDAnchor or state.ofd_released or anchor.owner_fd != state.owner_fd
            or anchor.identity != state.identity or state.binding.pid != os.getpid()
            or state.binding.thread is not threading.current_thread()
            or _identity(os.fstat(anchor.descriptor)) != anchor.identity
            or _identity(os.fstat(state.owner_fd)) != anchor.identity):
        _deny("phase observer lacks its held original writer OFD anchor")
    _same_open_description(state.owner_fd, anchor.descriptor)


def _release_ofd_anchor(state):
    anchor, state.ofd_anchor = state.ofd_anchor, None  # consume before close
    if anchor is not None:
        if _identity(os.fstat(anchor.descriptor)) != anchor.identity:
            _deny("phase OFD cleanup refuses a replaced private duplicate")
        os.close(anchor.descriptor)


def _gc_release_ofd_anchor(state):
    try:
        _release_ofd_anchor(state)
    except BaseException:
        pass  # Ambiguous/error close is never retried against a reused FD number.


def _before_native_terminal_writer_close(state):
    """Retire our writable dup only in the original native finalize frame.

    terminal.before_owned_terminal_close calls _writer after its terminal read.
    A successful comparison immediately before this close prevents retaining a
    duplicate writer beyond the native ledger close. No new anchor may follow.
    """
    frame = sys._getframe(1)
    for _ in range(12):
        if frame is None:
            break
        guard = frame.f_locals.get("self")
        if (frame.f_code is _FINALIZE.__code__ and type(guard) is BudgetGuard
                and _OBSERVERS.get(guard) is state
                and require_startup_binding(guard) is state.binding):
            _require_writer_ofd(state)
            _release_ofd_anchor(state)
            state.ofd_released = True  # only after the native close succeeded
            return
        frame = frame.f_back
    _deny("phase OFD release requires the original native terminal finalize frame")


def _require_retired_writer_ofd(state):
    """Closed GT handoff requires the previously checked and retired anchor."""
    if os.name == "posix" and (state.ofd_anchor is not None or state.ofd_released is not True):
        _deny("closed original owner lacks its native writer OFD retirement")


def _live_identity(guard, state: _Observer) -> None:
    _binding(guard, state)
    ledger = state.binding.ledger
    owner = os.fstat(state.owner_fd)
    visible = os.stat(ledger.path, follow_symlinks=False)
    if _identity(owner) != state.identity or _identity(visible) != state.identity:
        _deny("phase journal path or held owner FD identity changed")
    _binding(guard, state)


def _consume(state: _Observer, exc: BaseException) -> None:
    state.failed = True
    state.pending = None
    try:
        _release_ofd_anchor(state)
    except BaseException:
        pass
    if isinstance(exc, PermissionError):
        raise exc
    if not isinstance(exc, Exception):
        raise exc
    raise PermissionError("owned phase observation failed and was consumed") from exc


def _writer(state: _Observer) -> tuple[int, str]:
    ledger = state.binding.ledger
    if type(ledger._seq) is not int or ledger._seq < 2:
        _deny("phase writer sequence is invalid")
    tail = _digest(ledger._tail)
    if tail != ledger._tail:
        _deny("phase writer tail is not canonical")
    _require_writer_ofd(state)
    if os.name == "posix" and ledger._terminal is True:
        _before_native_terminal_writer_close(state)
    return ledger._seq, tail


def _parse(encoded: bytes, seq: int, tail: str) -> tuple[dict, ...]:
    if not encoded.endswith(b"\n"):
        _deny("phase journal has a partial final record")
    records = []
    previous = "0" * 64
    for index, line in enumerate(encoded[:-1].split(b"\n")):
        record = json.loads(line)
        if type(record) is not dict or set(record) != {"entry", "sha256"} or _canonical(record) != line:
            _deny("phase journal envelope is not exact canonical JSON")
        body = record["entry"]
        if (type(body) is not dict or set(body) != {"seq", "event", "payload", "previous_sha256"}
                or type(body["seq"]) is not int or body["seq"] != index
                or type(body["event"]) is not str or not body["event"]
                or type(body["payload"]) is not dict or body["previous_sha256"] != previous):
            _deny("phase journal entry schema or chain sequence is invalid")
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        if type(record["sha256"]) is not str or record["sha256"] != digest:
            _deny("phase journal hash chain differs from its bytes")
        previous = digest
        records.append(record)
    if len(records) != seq or previous != tail:
        _deny("phase journal sequence/tail differs from the live writer")
    if (len(records) < 2 or records[0]["entry"]["event"] != "study_created"
            or records[1]["entry"]["event"] != "invocation_started"
            or any(record["entry"]["event"] in ("study_created", "invocation_started") for record in records[2:])):
        _deny("phase journal startup prefix is not unique")
    return tuple(records)


def _journal(guard, state: _Observer) -> _Journal:
    """Read one bounded snapshot; the temporary descriptor is closed once."""
    _binding(guard, state)
    ledger = state.binding.ledger
    with ledger._guard:
        _live_identity(guard, state)
        seq, tail = _writer(state)
        owner_before = _frame(os.fstat(state.owner_fd))
        visible_before = _frame(os.stat(ledger.path, follow_symlinks=False))
        if owner_before != visible_before:
            _deny("phase journal changed before its readonly open")
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
        # Reserve report storage before acquiring this temporary descriptor.
        # The module remains portable; this buffer makes no native calls.
        failures = NativeFailureCapture(4)
        fd = os.open(ledger.path, flags)
        try:
            before = _frame(os.fstat(fd))
            if before != owner_before:
                _deny("phase readonly descriptor differs from its owner/path frame")
            remaining = before[5]
            chunks = []
            while remaining:
                chunk = os.read(fd, min(remaining, _CHUNK_BYTES))
                if type(chunk) is not bytes or not chunk or len(chunk) > min(remaining, _CHUNK_BYTES):
                    _deny("phase journal ended early or exceeded a bounded read")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1) != b"":
                _deny("phase journal grew beyond its bounded snapshot")
            after = _frame(os.fstat(fd))
            owner_after = _frame(os.fstat(state.owner_fd))
            visible_after = _frame(os.stat(ledger.path, follow_symlinks=False))
            _binding(guard, state)
            if (before != after or before != owner_after or before != visible_after
                    or (seq, tail) != _writer(state)):
                _deny("phase journal size/time/identity or writer changed during read")
            records = _parse(b"".join(chunks), seq, tail)
            startup_hashes = tuple(record["sha256"] for record in records[:2])
            if state.startup_hashes and startup_hashes != state.startup_hashes:
                _deny("phase journal startup digests drifted from registration")
            startup = records[1]["entry"]["payload"]
            if (startup.get("invocation_id") != state.binding.invocation_id
                    or type(startup.get("monotonic_ns")) is not int
                    or startup["monotonic_ns"] != state.binding.started_ns):
                _deny("phase journal invocation/start differs from its registered owner")
            return _Journal(records, before, seq, tail)
        except BaseException as exc:
            failures.failure.primary_error = exc
            raise
        finally:
            # Never retry close: a Linux error may mean the number was released.
            try:
                os.close(fd)
            except BaseException as close_error:
                if failures.failure.primary_error is None:
                    failures.failure.primary_error = close_error
                # No Python recording/report helper dispatch after acquisition.
                slot = next(failures._cursor)
                slot.operation = "journal_descriptor_close"
                slot.error = close_error
                slot.descriptor = fd
                failures.failure.secondary_errors = failures._slots
                raise failures.failure from failures.failure.primary_error


def register_phase_observer(guard, role_graph_sha256) -> None:
    """Freeze the original startup prefix and independent approved graph pin."""
    with _LOCK:
        if type(guard) is not BudgetGuard or guard in _OBSERVERS:
            _deny("phase observer registration is bound once to the original guard")
        binding = require_startup_binding(guard)
        if binding is None or type(binding.ledger) is not AppendOnlyLedger:
            _deny("phase observer requires an already registered startup owner")
        pin = _digest(role_graph_sha256)
        if pin != _digest(binding.approval.role_graph_sha256):
            _deny("phase graph pin differs from the original approved role graph")
        ledger = binding.ledger
        if type(ledger._fd) is not int or ledger._seq != 2 or type(ledger._seq) is not int:
            _deny("phase observer must register at the live startup sequence two")
        # Publish a consumed-on-failure entry before any descriptor observation.
        state = _Observer(binding, pin, ledger._fd, ())
        _OBSERVERS[guard] = state
        weakref.finalize(guard, _gc_release_ofd_anchor, state)
        try:
            state.identity = _identity(os.fstat(state.owner_fd))
            if os.name == "posix":
                descriptor = os.dup(state.owner_fd)
                state.ofd_anchor = _OFDAnchor(descriptor, state.owner_fd, state.identity)
                if os.get_inheritable(descriptor):
                    _deny("phase original OFD anchor must not be inherited by workers")
            _binding(guard, state)
            journal = _journal(guard, state)
            state.startup_hashes = tuple(record["sha256"] for record in journal.records[:2])
            state.startup_payload = _canonical(journal.records[1]["entry"]["payload"])
        except BaseException as exc:
            _consume(state, exc)


def require_phase_role_graph(guard) -> str:
    with _LOCK:
        state = _state(guard)
        try:
            _live_identity(guard, state)
            return state.role_graph
        except BaseException as exc:
            _consume(state, exc)


def require_owned_work(guard, *, stage_a: bool, fit: bool) -> None:
    """Require the private accepted phase before an owner starts work.

    Public admission flags cannot advance this gate. This readonly check
    advances no phase and provides no scientific/resource admission proof.
    """
    with _LOCK:
        state = _state(guard)
        try:
            _live_identity(guard, state)
            if type(stage_a) is not bool or type(fit) is not bool or state.pending is not None:
                _deny("owned work requires exact boolean intent and no pending phase proof")
            accepted = tuple(item.event for item in state.accepted)
            if accepted == () and stage_a is True and fit is False:
                return
            if accepted == _PHASES[:3] and stage_a is False:
                return
            _deny("owned work requires the private Stage A or accepted expansion phase")
        except BaseException as exc:
            _consume(state, exc)


def _phase_tail(state: _Observer, journal: _Journal, event: str) -> dict:
    phases = [record for record in journal.records if record["entry"]["event"] in _PHASES]
    expected = _PHASES[:len(state.accepted) + 1]
    if (tuple(record["entry"]["event"] for record in phases) != expected
            or not phases or phases[-1] is not journal.records[-1]
            or phases[-1]["entry"]["event"] != event):
        _deny("owned phase must occur once, in order, at the current ledger tail")
    for accepted, record in zip(state.accepted, phases):
        if record["sha256"] != accepted.receipt_values[0].lower():
            _deny("a previously accepted phase digest changed")
    payload = phases[-1]["entry"]["payload"]
    if payload.get("invocation_id") != state.binding.invocation_id:
        _deny("owned phase invocation differs from its original startup owner")
    return payload


def _receipt_values(state: _Observer, receipt, tail: str) -> tuple[str, int]:
    if type(receipt) is not DurableEventReceipt:
        _deny("owned phase requires the exact durable receipt type")
    digest = _digest(receipt.event_sha256)
    timestamp = receipt.fsynced_monotonic_ns
    if (digest != tail or type(timestamp) is not int
            or not state.binding.started_ns <= timestamp <= time.monotonic_ns()
            or (state.accepted and timestamp < state.accepted[-1].receipt_values[1])):
        _deny("owned phase receipt does not bind the actual tail and monotonic clock")
    return receipt.event_sha256, timestamp


def read_owned_phase_event(guard, event, receipt) -> OwnedPhaseEvent:
    with _LOCK:
        state = _state(guard)
        try:
            _binding(guard, state)
            if (state.pending is not None or type(event) is not str or len(state.accepted) >= len(_PHASES)
                    or event != _PHASES[len(state.accepted)]):
                _deny("owned phase read is pending, complete or out of order")
            journal = _journal(guard, state)
            payload = _canonical(_phase_tail(state, journal, event))
            values = _receipt_values(state, receipt, journal.tail)
            proof = OwnedPhaseEvent(json.loads(payload), event, receipt)
            state.pending = _Pending(proof, payload, receipt, values, journal)
            return proof
        except BaseException as exc:
            _consume(state, exc)


def accept_owned_phase_event(guard, proof) -> None:
    with _LOCK:
        state = _state(guard)
        try:
            _binding(guard, state)
            pending = state.pending
            if (pending is None or type(proof) is not OwnedPhaseEvent or proof is not pending.proof
                    or type(proof.event) is not str or proof.event != _PHASES[len(state.accepted)]
                    or proof.receipt is not pending.receipt or type(proof.payload) is not dict
                    or _canonical(proof.payload) != pending.payload):
                _deny("owned phase accept requires the same unchanged pending proof")
            journal = _journal(guard, state)
            if ((journal.seq, journal.tail, journal.frame)
                    != (pending.journal.seq, pending.journal.tail, pending.journal.frame)
                    or _canonical(_phase_tail(state, journal, proof.event)) != pending.payload
                    or _receipt_values(state, proof.receipt, journal.tail) != pending.receipt_values):
                _deny("owned phase proof receipt or live journal changed before accept")
            state.accepted.append(_Accepted(proof.event, pending.payload, pending.receipt_values))
            state.pending = None
        except BaseException as exc:
            _consume(state, exc)


def startup_owned_payload(guard) -> dict:
    with _LOCK:
        state = _state(guard)
        try:
            _live_identity(guard, state)
            return json.loads(state.startup_payload)
        except BaseException as exc:
            _consume(state, exc)


def accepted_owned_phase_event(guard, event) -> OwnedPhaseEvent:
    with _LOCK:
        state = _state(guard)
        try:
            _live_identity(guard, state)
        except BaseException as exc:
            _consume(state, exc)
        # A lookup of an unaccepted phase issues nothing and does not advance
        # or consume a pending valid read.
        for accepted in state.accepted:
            if type(event) is str and event == accepted.event:
                return OwnedPhaseEvent(json.loads(accepted.payload), accepted.event,
                                       DurableEventReceipt(*accepted.receipt_values))
        _deny("owned phase has not been accepted for this observer")


def fail_phase_observer(guard) -> None:
    """Poison an original observer and retire its private duplicate once."""
    with _LOCK:
        if type(guard) is not BudgetGuard:
            _deny("phase failure requires the original registered guard")
        state = _OBSERVERS.get(guard)
        if state is None or registered_startup(guard) is not state.binding:
            _deny("phase failure does not belong to a registered observer")
        state.failed = True
        # Poison precedes this check so restoring mutable fields cannot retry.
        try:
            _binding(guard, state)
        finally:
            state.pending = None
            _release_ofd_anchor(state)
