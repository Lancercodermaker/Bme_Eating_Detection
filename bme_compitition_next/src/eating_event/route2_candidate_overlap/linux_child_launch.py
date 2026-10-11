"""Private native phase lifecycle source unit; deliberately not a runner.

The original bootstrap must establish the full readonly interpreter/project/
native closure BEFORE importing this unit. Controller imports transitively
import ctypes; this unit cannot establish that earlier constructor boundary.
Its existing installation/write-boundary gate precedes only its own phase
CDLL load and still refuses. The frozen runtime lacks lib/route2/phase_spawn.so.
Hashes/ABI/startup status cannot replace installation or dependency-closure/
preconstructor proof. No production entry calls this.

This unit now binds the registered original publisher/batch, its current GT
grant and its already armed clocks, samples the real child before final permit,
and retains once-only private outcomes. Installation/freeze, full phase-root
creation/deletion history, preconstructor dependency closure and external
quarantine remain separate missing assembly. No outcome is admission, a full
sandbox receipt or a complete GT-failure-preservation receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import platform
import signal
import socket
import stat
import struct
import threading
import time
import weakref

from .budget import AppendOnlyLedger, BudgetGuard
from .contracts import FrozenAdmission
from .gt_provider import TruthReadScope
from .linux_child_exit import _consume_pidfd_exit
from .linux_child_exit import _NativeExit
from .linux_enforcement import ResourceEnvelope
from .linux_production_controller import LinuxProductionController, LinuxProductionOSPorts
from .linux_supervisor import Route2Supervisor
from .native_failure_capture import NativeFailureCapture
from .startup_ownership import StartupBinding, require_startup_binding
from . import phase_worker_entry as wire

_LIBRARY = "lib/route2/phase_spawn.so"
_ABI, _STATUS_BYTES, _ERRORS = 1, 208, 16
_CLOSES = (("permit_fd", "phase_permit_fd_close"), ("status_fd", "phase_status_fd_close"),
           ("ipc_fd", "phase_ipc_fd_close"), ("pidfd", "phase_pidfd_close"))

class _Handle:
    __slots__ = ()

class _OutcomeHandle:
    __slots__ = ()

@dataclass(slots=True)
class _BirthError:
    operation: int = 0
    error_number: int = 0
    descriptor: int = -1

@dataclass(slots=True)
class _Birth:
    # All numeric snapshot slots exist before clone3. Closing raw Result FDs
    # cannot turn the original successful birth descriptors into -1.
    abi: int = 0
    size: int = 0
    pid: int = -1
    pidfd: int = -1
    ipc_fd: int = -1
    status_fd: int = -1
    permit_fd: int = -1
    native_return: int | None = None
    error_count: int = 0
    errors: tuple = field(default_factory=lambda: tuple(_BirthError() for _ in range(_ERRORS)))
    descriptor_frames: tuple = ()

@dataclass(slots=True)
class _Owned:
    guard: object
    binding: object
    raw: object
    library: object
    errors: object
    stop_ns: int
    cleanup_ns: int
    pid: int
    thread: object
    exit_attempted: bool = False
    consumed: bool = False
    handle: object | None = None
    publisher: object | None = None
    batch: object | None = None
    scope: object | None = None
    release: str | None = None
    captures: tuple = ()
    birth: _Birth = field(default_factory=_Birth)
    ready: object | None = None
    post_ready_status: object | None = None
    observation: object | None = None
    observation_history: str | None = None
    prepermit_wait: object | None = None
    prepermit_wait_final: object | None = None
    waitable_parent: bool = False
    wait_observed: object | None = None
    wait_reaped: object | None = None
    native_exit: object | None = None
    exit_failure: object | None = None
    failure_cleanup_exit: object | None = None
    reap_attempted: bool = False
    reaped: bool = False
    cleanup_attempted: bool = False
    close_complete: bool = False
    failed: bool = False
    result: object | None = None
    outcome_handle: object = field(default_factory=_OutcomeHandle)
    outcome: object | None = None
    outcome_history: str | None = None
    outcome_consumed: bool = False
    consumption_history: str | None = None

@dataclass(frozen=True, slots=True)
class _PhaseOutcome:
    birth: object
    ready: object
    observation: object
    wait_observed: object
    wait_reaped: object
    native_exit: object
    result: object
    observation_history: str
    outcome_history: str

@dataclass(frozen=True, slots=True)
class _KernelSnapshot:
    started_monotonic_ns: int
    completed_monotonic_ns: int
    facts: bytes
    raw: tuple


def _outcome_snapshot(state):
    # Return immutable diagnostic data, never the trusted mutable observer or
    # its original owner/state pointers. Strong batch state retains originals.
    from .budget import _canonical

    born = state.birth
    birth = (born.abi, born.size, born.pid, born.pidfd, born.ipc_fd, born.status_fd,
             born.permit_fd, born.native_return, born.error_count,
             tuple((row.operation, row.error_number, row.descriptor) for row in born.errors),
             born.descriptor_frames)
    observed = state.observation
    raw = tuple((name, body if type(body) is bytes else tuple(body.items())) for name, body in observed.raw.items())
    kernel = _KernelSnapshot(observed.started_ns, observed.completed_ns, _canonical(observed.facts), raw)
    return _PhaseOutcome(birth, bytes(state.ready), kernel, state.wait_observed, state.wait_reaped,
                         state.native_exit, state.result, state.observation_history, state.outcome_history)

_CHILDREN = {}
_OUTCOMES = {}
_FAILED = weakref.WeakSet()

def _owner(guard):
    if (type(guard) is not BudgetGuard or platform.system() != "Linux" or platform.machine() != "x86_64"
            or struct.calcsize("P") != 8 or threading.current_thread() is not threading.main_thread()
            or os.getresuid() != (0,) * 3 or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
            or signal.getsignal(signal.SIGPIPE) != signal.SIG_IGN or len(os.listdir("/proc/self/task")) != 1
            or not all(hasattr(os, name) for name in ("P_PIDFD", "WEXITED", "WNOWAIT", "WNOHANG"))
            or not hasattr(signal, "pidfd_send_signal")
            or guard in _FAILED):
        raise PermissionError("phase lifecycle requires its single original native root controller")
    binding = require_startup_binding(guard)
    if (type(binding) is not StartupBinding or type(binding.owner()) is not Route2Supervisor
            or type(binding.controller) is not LinuxProductionController or guard.enforcer is not binding.controller
            or type(binding.ledger) is not AppendOnlyLedger):
        raise PermissionError("phase lifecycle lacks exact original startup/guard/enforcer ownership")
    return binding, binding.controller._state()

def _close(errors, fd, operation):
    try: os.close(fd)
    except BaseException as error:
        if errors.failure.primary_error is None:
            errors.failure.primary_error = error
        if errors.first_error is None:
            errors.first_error = error
        reserved = next(errors._cursor, None)
        if reserved is None:
            errors.overflowed = True
        else:
            reserved.operation, reserved.error, reserved.descriptor = (operation, error, fd)

def _pinned_bytes(path, expected, maximum, deadline, errors):
    fd = None; primary = None; body = bytearray()
    try:
        wire._check(deadline)
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        identity = (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_nlink,
                    before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid or before.st_nlink != 1
                or before.st_mode & 0o022 or not 0 < before.st_size <= maximum
                or not os.fstatvfs(fd).f_flag & os.ST_RDONLY):
            raise PermissionError("phase installation file is not protected, bounded and readonly")
        while len(body) < before.st_size:
            wire._check(deadline)
            part = os.read(fd, min(65536, before.st_size - len(body)))
            if not part: raise EOFError("phase installation file is incomplete")
            body.extend(part)
        after = os.fstat(fd)
        if (identity != (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_nlink,
                         after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or hashlib.sha256(body).hexdigest() != expected):
            raise PermissionError("phase installation content differs from its frozen manifest pin")
        wire._check(deadline)
    except BaseException as error:
        primary = error
        if errors.failure.primary_error is None:
            errors.failure.primary_error = error
        if errors.first_error is None:
            errors.first_error = error
        reserved = next(errors._cursor, None)
        if reserved is None:
            errors.overflowed = True
        else:
            reserved.operation, reserved.error, reserved.descriptor = ("phase_installation_read", error, fd)
    finally:
        if fd is not None:
            original, fd = fd, None
            # Consume before the actual close, with no cleanup-helper frame
            # whose entry failure could skip this original held descriptor.
            try:
                os.close(original)
            except BaseException as error:
                if errors.failure.primary_error is None:
                    errors.failure.primary_error = error
                if errors.first_error is None:
                    errors.first_error = error
                reserved = next(errors._cursor, None)
                if reserved is None:
                    errors.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = ("phase_installation_close", error, original)
    if primary is not None or errors.first_error is not None: errors.raise_failure(primary)
    return body

def _native(guard, deadline, errors):
    binding, assembly = _owner(guard)
    if type(assembly.ports) is not LinuxProductionOSPorts:
        raise PermissionError("phase loader forbids supplied installation/OS-port implementations")
    frozen, policy, _ = binding.controller._policy(assembly)
    # Exact existing class implementation, not an instance callback or a new
    # successful boolean. Today this raises before manifest reads or dlopen.
    LinuxProductionOSPorts.require_installation_and_write_boundary(
        assembly.ports, policy, frozen, assembly.unit_observation)
    wire._check(deadline)
    if (type(frozen) is not FrozenAdmission or type(assembly.envelope) is not ResourceEnvelope
            or guard.limits.worker_limit != 2 or assembly.envelope.pids_max != 2
            or not 0 < guard.frozen_rss_ceiling_bytes <= 4 << 30
            or assembly.envelope.rlimit_as_per_process_bytes != guard.frozen_rss_ceiling_bytes // 2):
        raise PermissionError("phase loader lost the original C/2 two-task resource envelope")
    raw = _pinned_bytes(frozen.runtime_snapshot_manifest_path, frozen.runtime_snapshot_sha256.lower(),
                        wire._MAX_BYTES, deadline, errors)
    manifest = wire._loads(raw, deadline)
    if (type(manifest) is not dict or set(manifest) != {"schema", "files"}
            or manifest["schema"] != "route2_immutable_source_snapshot_v1" or type(manifest["files"]) is not list):
        raise PermissionError("phase library requires the original complete frozen runtime manifest")
    entries = [row for row in manifest["files"] if type(row) is dict and row.get("path") == _LIBRARY]
    if len(entries) != 1 or set(entries[0]) != {"path", "bytes", "sha256"}:
        raise PermissionError("reviewed fixed native phase library is absent or repeated in the runtime snapshot")
    entry = entries[0]
    if type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= wire._MAX_BYTES:
        raise PermissionError("reviewed native phase library exceeds its fixed bound")
    wire._walk("hash", entry["sha256"], False, deadline, [0])
    library_path = Path(frozen.runtime_snapshot_root) / _LIBRARY
    image = _pinned_bytes(library_path, entry["sha256"], entry["bytes"], deadline, errors)
    if len(image) != entry["bytes"]: raise PermissionError("native phase library size differs from its manifest")
    # Only the actual complete installation gate can authorize executing these
    # ELF constructors/dependencies. Hashing this file is merely a later check.
    import ctypes
    class Error(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int32) for name in ("operation", "error_number", "descriptor")]
    class Spec(ctypes.Structure):
        _fields_ = [("abi", ctypes.c_uint32), ("size", ctypes.c_uint32)] + [(name, ctypes.c_uint64)
            for name in ("as_limit_bytes", "stop_deadline_ns", "cleanup_deadline_ns")]
    class Result(ctypes.Structure):
        _fields_ = [("abi", ctypes.c_uint32), ("size", ctypes.c_uint32)] + [(name, ctypes.c_int32)
            for name in ("pid", "pidfd", "ipc_fd", "status_fd", "permit_fd")] + [
                ("error_count", ctypes.c_uint32), ("errors", Error * _ERRORS)]
    if ctypes.sizeof(Spec) != 32 or ctypes.sizeof(Result) != 224:
        raise PermissionError("native phase ABI differs from the fixed native x86_64 layout")
    library = ctypes.CDLL(str(library_path), mode=os.RTLD_NOW | os.RTLD_LOCAL, use_errno=True)
    library.route2_phase_spawn_abi.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    library.route2_phase_spawn_abi.restype = ctypes.c_uint32
    if library.route2_phase_spawn_abi(32, 224) != _ABI:
        raise PermissionError("native phase helper ABI is unsupported")
    library.route2_phase_spawn.argtypes = [ctypes.POINTER(Spec), ctypes.POINTER(Result)]
    library.route2_phase_spawn.restype = ctypes.c_int
    wire._check(deadline)
    return binding, library, Spec, Result, ctypes

def _original(handle):
    state = _CHILDREN.get(handle) if type(handle) is _Handle else None
    if (state is None or state.consumed or state.pid != os.getpid() or state.thread is not threading.current_thread()
            or state.handle is not handle or require_startup_binding(state.guard) is not state.binding):
        raise PermissionError("phase handle is absent, consumed or not owned by its original controller")
    from .linux_phase_publication import _phase_launch_owner
    _phase_launch_owner(state)
    return state

def _native_errors(errors, rows, captures=None):
    buffers = (errors,) if captures is None else captures
    for operation, number, descriptor in rows:
        if not 1 <= operation <= 26 or not 0 < number <= 4095 or descriptor < -1:
            raise PermissionError("native phase error capsule is malformed")
        error = OSError(number, "fixed native phase operation failed")
        error.native_operation = operation
        for buffer in buffers:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = error
            if buffer.first_error is None:
                buffer.first_error = error
            reserved = next(buffer._cursor, None)
            if reserved is None:
                buffer.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("native_phase_operation", error, descriptor)

def _status(state, body):
    abi, kind, count, reserved = struct.unpack_from("<IIII", body)
    if (abi != _ABI or reserved or kind not in (1, 2) or not 0 <= count <= _ERRORS
            or bool(count) != (kind == 2) or any(body[16 + count * 12:])):
        raise PermissionError("native startup status type/size differs")
    if kind == 2:
        _native_errors(state.errors, [struct.unpack_from("<iii", body, 16 + i * 12) for i in range(count)], state.captures)
        state.errors.raise_failure(None)

def _take_close(state, field, operation):
    fd = getattr(state.raw, field); setattr(state.raw, field, -1)
    if fd >= 0:
        try: os.close(fd)
        except BaseException as error:
            for buffer in state.captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = error
                if buffer.first_error is None:
                    buffer.first_error = error
                reserved = next(buffer._cursor, None)
                if reserved is None:
                    buffer.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = (operation, error, fd)
            state.failed = True
            if state.publisher is not None:
                state.publisher.failed = state.publisher.owner.failed = True

def _half_close(state):
    import ctypes
    function = state.library["shutdown"]
    if type(function) is not state.library._FuncPtr:
        raise PermissionError("phase half-close lacks its original approved native interface")
    function.argtypes, function.restype = (ctypes.c_int, ctypes.c_int), ctypes.c_int
    if getattr(function, "errcheck", None) is not None:
        raise PermissionError("phase half-close forbids callback native interfaces")
    error = OSError("original phase IPC write-half shutdown failed")
    wire._check(state.stop_ns)
    ctypes.set_errno(0)
    result = function(state.raw.ipc_fd, socket.SHUT_WR)
    number = ctypes.get_errno() if result < 0 else 0
    if result < 0:
        error.errno = number
        raise error
    wire._check(state.stop_ns)

def _failure_capsule(value):
    wire._mapping(value, (("schema", None), ("primary", None), ("secondary", None), ("truncated", None)))
    if (value["schema"] != "route2_phase_failure_v1" or type(value["secondary"]) is not list
            or len(value["secondary"]) > 16 or type(value["truncated"]) is not bool):
        raise ValueError("child failure capsule shape differs")
    for row in [value["primary"], *value["secondary"]]:
        wire._mapping(row, (("kind", None), ("errno", None), ("json_position", None)))
        if (any(type(row[name]) is not int for name in row) or not 1 <= row["kind"] <= 8
                or not 0 <= row["errno"] <= 4095 or not -1 <= row["json_position"] <= wire._MAX_BYTES):
            raise ValueError("child failure capsule numeric bounds differ")
    return value

def _birth_record(state):
    born = state.birth
    return dict(abi=born.abi, size=born.size, pid=born.pid, pidfd=born.pidfd,
                ipc_fd=born.ipc_fd, status_fd=born.status_fd, permit_fd=born.permit_fd,
                native_return=born.native_return, error_count=born.error_count,
                errors=[(row.operation, row.error_number, row.descriptor) for row in born.errors[:born.error_count]],
                descriptor_frames=born.descriptor_frames)


def _reap_success(state):
    """Store each raw actual wait before validation/allocation; reap once."""
    _original(state.handle)
    wire._check(state.stop_ns)
    state.exit_attempted = True
    while True:
        info = os.waitid(os.P_PIDFD, state.raw.pidfd, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        state.wait_observed = info
        state.waitable_parent = True
        if info is not None:
            observed_ns = time.monotonic_ns()
            break
        wire._poll(state.raw.pidfd, False, state.stop_ns)
    values = (info.si_pid, info.si_uid, info.si_signo, info.si_code, info.si_status)
    if (info.si_pid != state.birth.pid or info.si_signo != signal.SIGCHLD
            or info.si_code not in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)):
        raise PermissionError("original pidfd wait observation differs from its actual native child")
    wire._check(state.stop_ns)
    state.reap_attempted = True  # once even if the syscall raises
    actual = os.waitid(os.P_PIDFD, state.raw.pidfd, os.WEXITED | os.WNOHANG)
    state.wait_reaped = actual
    reaped_ns = time.monotonic_ns()
    if actual is not None and actual.si_pid == state.birth.pid:
        state.reaped = True  # only this original kernel reaper can retire it
    if actual is None or (actual.si_pid, actual.si_uid, actual.si_signo, actual.si_code, actual.si_status) != values:
        raise PermissionError("original child reap status differs from its held WNOWAIT observation")
    state.native_exit = _NativeExit(*values, observed_ns, reaped_ns)
    state.errors.failure.native_exit = state.native_exit
    wire._check(state.stop_ns)
    if state.native_exit.uid != 65534:
        raise PermissionError("phase exit did not retain the actual fixed non-root UID")
    if state.native_exit.code != os.CLD_EXITED or state.native_exit.status != 0:
        raise ChildProcessError("original phase child failed; raw wait/reap status retained")


def _raise_retained(errors, primary):
    try:
        errors.raise_failure(primary)
    except BaseException as report_error:
        if report_error is errors.failure:
            raise
        # A failure even to enter/format the report cannot replace the locked
        # raw operation origin. The reserved slots remain the complete buffer.
        errors.aggregation_error = report_error
        reserved = next(errors._cursor, None)
        if reserved is None:
            errors.overflowed = True
        else:
            reserved.operation, reserved.error, reserved.descriptor = ("phase_report_entry_failure", report_error, None)
        errors.failure.secondary_errors = errors._slots
        errors.failure.aggregation_error = report_error
        raise errors.failure from errors.failure.primary_error


def _poison_guard(state, guard, errors):
    if state is not None:
        state.failed = True
    if type(guard) is BudgetGuard:
        try:
            _FAILED.add(guard)
        except BaseException as error:
            reserved = next(errors._cursor, None)
            if reserved is None:
                errors.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("native_phase_owner_invalidation", error, None)


def _run_private_phase(guard, *, payload, release_event_sha256, stop_deadline_ns, cleanup_deadline_ns):
    """One original registered batch, one child, one privately consumable outcome.

    Supplied deadlines must equal the already armed original publisher times;
    they cannot start or renew an interval. Current production loading refuses.
    """
    from . import linux_phase_publication as publication
    from . import linux_phase_child_observation as observation

    errors = NativeFailureCapture(1024)
    errors.failure.child_failure = None
    errors.failure.native_exit = None
    errors.failure.native_birth = None
    errors.failure.native_startup = None
    errors.failure.post_ready_status = None
    errors.failure.kernel_observation = None
    errors.failure.original_phase_issuance = None
    errors.failure.child_exit_attestation = "NOT_ATTESTED"
    errors.failure.child_error_transport = "UNKNOWN"
    state = handle = None; primary = None
    try:
        binding, _ = _owner(guard)
        state = _Owned(guard, binding, None, None, errors, 0, 0, os.getpid(), threading.current_thread())
        state.captures = (errors,)
        handle = state.handle = _Handle()
        errors.failure.original_phase_issuance = state
        errors.failure.native_birth = state.birth
        wire._mapping(payload, wire._REQUEST)
        if type(payload["scope"]) is not TruthReadScope:
            raise PermissionError("phase release requires its exact scientific scope")
        publication._acquire_phase_launch(guard, payload["scope"], release_event_sha256, state,
                                           stop_deadline_ns, cleanup_deadline_ns)
        wire._check(state.stop_ns)
        wire._walk(TruthReadScope, state.scope, True, state.stop_ns, [0])
        wire._walk("hash", state.release, False, state.stop_ns, [0])
        publication._phase_launch_payload(state, payload)
        acquired, library, Spec, Result, ctypes = _native(guard, state.stop_ns, errors)
        if acquired is not state.binding:
            raise PermissionError("native phase loader changed the original publisher startup owner")
        state.library = library
        request = wire._request(payload, True, state.stop_ns)
        raw = Result(); raw.pid = raw.pidfd = raw.ipc_fd = raw.status_fd = raw.permit_fd = -1
        state.raw = raw
        _CHILDREN[handle] = state  # registry/all failure slots exist before birth
        spec = Spec(_ABI, 32, guard.frozen_rss_ceiling_bytes // 2, state.stop_ns, state.cleanup_ns)
        status = library.route2_phase_spawn(ctypes.byref(spec), ctypes.byref(raw))
        # Numeric snapshots precede any report/validation/close helper. Raw
        # Result remains owned for cleanup and can mutate without losing birth.
        state.birth.native_return = status
        state.birth.abi, state.birth.size = raw.abi, raw.size
        state.birth.pid, state.birth.pidfd = raw.pid, raw.pidfd
        state.birth.ipc_fd, state.birth.status_fd, state.birth.permit_fd = raw.ipc_fd, raw.status_fd, raw.permit_fd
        state.birth.error_count = raw.error_count
        for index in range(min(raw.error_count, _ERRORS)):
            original = state.birth.errors[index]
            original.operation, original.error_number, original.descriptor = (
                raw.errors[index].operation, raw.errors[index].error_number, raw.errors[index].descriptor)
        _original(handle)
        if raw.abi != _ABI or raw.size != 224 or not 0 <= raw.error_count <= _ERRORS:
            raise PermissionError("native phase birth result layout differs")
        _native_errors(errors, [(raw.errors[i].operation, raw.errors[i].error_number, raw.errors[i].descriptor)
                                for i in range(raw.error_count)], state.captures)
        if errors.first_error is not None: errors.raise_failure(None)
        if status != 0 or raw.pid <= 1 or any(getattr(raw, name) < 0 for name in ("pidfd", "ipc_fd", "status_fd", "permit_fd")):
            raise PermissionError("native phase birth lacks its original atomic pidfd/channels")
        if len({raw.pidfd, raw.ipc_fd, raw.status_fd, raw.permit_fd}) != 4:
            raise PermissionError("native phase birth repeats an original held descriptor")
        state.birth.descriptor_frames = tuple((name, os.fstat(getattr(raw, name)).st_dev,
            os.fstat(getattr(raw, name)).st_ino, os.fstat(getattr(raw, name)).st_mode)
            for name in ("pidfd", "ipc_fd", "status_fd", "permit_fd"))
        state.ready = errors.failure.native_startup = wire._read(raw.status_fd, _STATUS_BYTES, state.stop_ns)
        _status(state, state.ready)
        observation._observe_original_child(handle)
        errors.failure.kernel_observation = state.observation
        state.observation_history = publication._phase_launch_record(state, "gt_broker_phase_child_observed",
            dict(birth=_birth_record(state), ready_hex=bytes(state.ready).hex(),
                 observation=observation._history_record(state)))
        # Durable history exists before the last original ownership/live fence
        # and permit. A failed append/allocation never becomes a successful run.
        _original(handle)
        publication._phase_launch_payload(state, payload)
        state.prepermit_wait_final = os.waitid(os.P_PIDFD, raw.pidfd, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        if state.prepermit_wait_final is not None:
            raise ChildProcessError("original native child exited before the durable-history final permit")
        _original(handle); wire._write(raw.permit_fd, b"\x02", state.stop_ns)
        _take_close(state, "permit_fd", "phase_permit_fd_close")
        if errors.first_error is not None: errors.raise_failure(None)
        # CLOEXEC EOF is only an exec-transition observation, not installation
        # or sandbox authority. A native exec failure carries another capsule.
        wire._poll(raw.status_fd, False, state.stop_ns)
        first = os.read(raw.status_fd, _STATUS_BYTES)
        if first:
            if len(first) < _STATUS_BYTES:
                complete = bytearray(first)
                complete.extend(wire._read(raw.status_fd, _STATUS_BYTES - len(first), state.stop_ns))
                first = complete
            state.post_ready_status = errors.failure.post_ready_status = first
            _status(state, first)
            raise PermissionError("native setup emitted an unexpected second READY")
        _take_close(state, "status_fd", "phase_status_fd_close")
        if errors.first_error is not None: errors.raise_failure(None)
        wire._send(raw.ipc_fd, request, state.stop_ns); _half_close(state)
        response = wire._receive(raw.ipc_fd, state.stop_ns)
        if type(response) is dict and response.get("schema") == "route2_phase_failure_v1":
            errors.failure.child_failure = _failure_capsule(response)
            errors.failure.child_error_transport = "BOUNDED_NUMERIC_CAPSULE"
            raise ChildProcessError("private phase worker failed; numeric capsule retained, raw child objects unavailable")
        state.result = wire._result(response, payload["operation"], False, state.stop_ns)
        wire._eof(raw.ipc_fd, state.stop_ns)
        _reap_success(state)
    except BaseException as error:
        captures = (errors,) if state is None else state.captures
        origin = error
        for original_capture in captures:
            if error is original_capture.failure:
                origin = original_capture.failure.primary_error
                break
        primary = origin
        for buffer in captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            reserved = next(buffer._cursor, None)
            if reserved is None:
                buffer.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("native_phase_primary", origin, None)
        if state is not None:
            state.failed = True
            if state.publisher is not None:
                state.publisher.failed = state.publisher.owner.failed = True
    finally:
        if state is not None and state.raw is not None:
            if (state.raw.pidfd >= 0 and state.raw.pid > 1 and not state.reaped
                    and not state.reap_attempted and not state.cleanup_attempted):
                state.cleanup_attempted = True
                try:
                    state.failure_cleanup_exit = _consume_pidfd_exit(pidfd=state.raw.pidfd, expected_pid=state.raw.pid,
                        stop_deadline_ns=state.stop_ns, cleanup_deadline_ns=state.cleanup_ns, _failure_cleanup=True)
                    state.native_exit = errors.failure.native_exit = state.failure_cleanup_exit
                    state.reaped = True
                except BaseException as error:
                    state.exit_failure = error
                    origin = error
                    report = (error.__dict__.get("failure_capture")
                              if type(error) is PermissionError else None)
                    if type(report) is NativeFailureCapture and report.failure is error:
                        # The original reaper call's actual capture is strongly
                        # retained by exit_failure; do not link its wrapper back.
                        origin = report.failure.primary_error
                    for buffer in state.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = origin
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        reserved = next(buffer._cursor, None)
                        if reserved is None:
                            buffer.overflowed = True
                        else:
                            reserved.operation, reserved.error, reserved.descriptor = (
                                "native_phase_failure_cleanup", origin, state.raw.pidfd)
                    try:
                        report = getattr(error, "failure_capture", None)
                        if type(report) is NativeFailureCapture and report.failure is error:
                            # Only the original helper's actual reap can retire
                            # this registry. A malformed/absent report cannot.
                            state.reaped = report.failure.reaped is True
                    except BaseException as report_error:
                        raw_report_error = report_error
                        for original_capture in state.captures:
                            if report_error is original_capture.failure:
                                raw_report_error = original_capture.failure.primary_error
                                break
                        for buffer in state.captures:
                            buffer.aggregation_error = raw_report_error
                            reserved = next(buffer._cursor, None)
                            if reserved is None:
                                buffer.overflowed = True
                            else:
                                reserved.operation, reserved.error, reserved.descriptor = (
                                    "phase_cleanup_report_entry", raw_report_error, state.raw.pidfd)
                    state.failed = True
                    if state.publisher is not None:
                        state.publisher.failed = state.publisher.owner.failed = True
            for field, operation in _CLOSES:
                # No cleanup/report helper entry precedes consuming this FD.
                descriptor = getattr(state.raw, field)
                setattr(state.raw, field, -1)
                if descriptor < 0:
                    continue
                try:
                    os.close(descriptor)
                except BaseException as error:
                    for buffer in state.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = error
                        if buffer.first_error is None:
                            buffer.first_error = error
                        reserved = next(buffer._cursor, None)
                        if reserved is None:
                            buffer.overflowed = True
                        else:
                            reserved.operation, reserved.error, reserved.descriptor = (operation, error, descriptor)
                    state.failed = True
                    if state.publisher is not None:
                        state.publisher.failed = state.publisher.owner.failed = True
            state.close_complete = True
            # A failed/unattempted reap keeps the strong original registry and
            # fences publisher removal. No supplied PID/status retires it.
            if state.reaped:
                try:
                    if (_CHILDREN.get(handle) is not state or state.pid != os.getpid()
                            or state.thread is not threading.current_thread()
                            or require_startup_binding(guard) is not state.binding):
                        raise PermissionError("original reaper cannot retire a replaced/foreign native issuance")
                    state.consumed = True
                    del _CHILDREN[handle]
                except BaseException as error:
                    for buffer in state.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = error
                        if buffer.first_error is None:
                            buffer.first_error = error
                        reserved = next(buffer._cursor, None)
                        if reserved is None:
                            buffer.overflowed = True
                        else:
                            reserved.operation, reserved.error, reserved.descriptor = ("phase_registry_retirement", error, None)
                    state.failed = True
                    if state.publisher is not None:
                        state.publisher.failed = state.publisher.owner.failed = True
    if primary is not None or errors.first_error is not None:
        if state is not None:
            try:
                publication._phase_launch_failure(state, "native_phase_failed_after_cleanup", primary or errors.first_error)
            except BaseException as report_error:
                raw_report_error = report_error
                for original_capture in state.captures:
                    if report_error is original_capture.failure:
                        raw_report_error = original_capture.failure.primary_error
                        break
                for buffer in state.captures:
                    buffer.aggregation_error = raw_report_error
                    reserved = next(buffer._cursor, None)
                    if reserved is None:
                        buffer.overflowed = True
                    else:
                        reserved.operation, reserved.error, reserved.descriptor = (
                            "phase_failure_hook_entry", raw_report_error, None)
        _poison_guard(state, guard, errors)
        _raise_retained(errors, primary)
    try:
        if state is None or not state.reaped or not state.consumed or not state.close_complete:
            raise PermissionError("native phase outcome cannot precede original reap/descriptor cleanup")
        observation._original_observation(state)
        state.outcome_history = publication._phase_launch_record(state, "gt_broker_phase_child_finished", {
            "birth": _birth_record(state), "observation_history_sha256": state.observation_history,
            "wait_observed": tuple(state.wait_observed), "wait_reaped": tuple(state.wait_reaped),
            "exit": dict(pid=state.native_exit.pid, uid=state.native_exit.uid, signo=state.native_exit.signo,
                         code=state.native_exit.code, status=state.native_exit.status,
                         observed_monotonic_ns=state.native_exit.observed_monotonic_ns,
                         reaped_monotonic_ns=state.native_exit.reaped_monotonic_ns),
            "operation": payload["operation"]})
        state.outcome = _outcome_snapshot(state)
        _OUTCOMES[state.outcome_handle] = state
        state.batch.outcome = state.outcome_handle
        return state.outcome_handle
    except BaseException as error:
        origin = error
        for original_capture in state.captures:
            if error is original_capture.failure:
                origin = original_capture.failure.primary_error
                break
        for buffer in state.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            reserved = next(buffer._cursor, None)
            if reserved is None:
                buffer.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("phase_outcome_registration", origin, None)
        state.failed = True
        if state.publisher is not None:
            state.publisher.failed = state.publisher.owner.failed = True
        try:
            publication._phase_launch_failure(state, "phase_outcome_registration", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in state.captures:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in state.captures:
                buffer.aggregation_error = raw_report_error
                reserved = next(buffer._cursor, None)
                if reserved is None:
                    buffer.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = (
                        "phase_failure_hook_entry", raw_report_error, None)
        _poison_guard(state, guard, errors)
        _raise_retained(errors, error)


def _consume_private_phase_outcome(guard, handle):
    """Only the same privately registered original owner may consume once.

    The returned science data retains the unchanged wire/result validation.
    The diagnostic outcome is not a public sandbox/admission/clean-exit receipt.
    """
    from . import linux_phase_publication as publication
    from . import linux_phase_child_observation as observation

    state = _OUTCOMES.get(handle) if type(handle) is _OutcomeHandle else None
    if (type(state) is not _Owned or state.guard is not guard or state.outcome_handle is not handle
            or state.pid != os.getpid() or state.thread is not threading.current_thread()
            or state.outcome_consumed or state.failed or not state.consumed or not state.reaped
            or not state.close_complete or state.batch.outcome is not handle
            or state.batch.outcome_consumed or require_startup_binding(guard) is not state.binding):
        raise PermissionError("phase outcome is absent/consumed or not its original registered owner")
    try:
        publication._phase_launch_owner(state)
        observation._original_observation(state)
        state.consumption_history = publication._phase_launch_record(state, "gt_broker_phase_outcome_consumed", {
            "child_pid": state.birth.pid, "outcome_history_sha256": state.outcome_history})
        state.outcome_consumed = state.batch.outcome_consumed = True
        del _OUTCOMES[handle]
        # Batch/state strongly retain birth, READY, kernel and result evidence
        # after both registry consumptions and after publisher unpublication.
        del observation._OBSERVATIONS[state.handle]
        return state.outcome
    except BaseException as error:
        origin = error
        for original_capture in state.captures:
            if error is original_capture.failure:
                origin = original_capture.failure.primary_error
                break
        for buffer in state.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            reserved = next(buffer._cursor, None)
            if reserved is None:
                buffer.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("phase_outcome_consumption", origin, None)
        state.failed = True
        if state.publisher is not None:
            state.publisher.failed = state.publisher.owner.failed = True
        try:
            publication._phase_launch_failure(state, "phase_outcome_consumption", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in state.captures:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in state.captures:
                buffer.aggregation_error = raw_report_error
                reserved = next(buffer._cursor, None)
                if reserved is None:
                    buffer.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = (
                        "phase_failure_hook_entry", raw_report_error, None)
        _poison_guard(state, guard, state.errors)
        _raise_retained(state.errors, error)


def _retained_batch_snapshot(batch):
    state = batch.launch
    if state is None:
        return None
    return (state, state.guard, state.binding, state.publisher, state.batch, state.scope, state.release,
        state.stop_ns, state.cleanup_ns, state.pid, state.thread, state.birth.pid, state.birth.pidfd,
        state.birth.ipc_fd, state.birth.status_fd, state.birth.permit_fd, state.birth.descriptor_frames,
        state.ready, state.post_ready_status, state.observation, state.observation_history,
        state.wait_observed, state.wait_reaped, state.native_exit, state.exit_failure,
        state.failure_cleanup_exit, state.reap_attempted, state.reaped, state.cleanup_attempted,
        state.close_complete, state.consumed, state.failed, state.outcome_handle, state.outcome,
        state.outcome_history, state.outcome_consumed, state.consumption_history,
        state.errors.first_error, state.errors.failure.primary_error, state.errors.aggregation_error,
        state.errors.overflowed)


def _require_retired_phase_batch(publisher, batch):
    state = batch.launch
    if state is None:
        if batch.outcome is not None or batch.outcome_consumed:
            raise PermissionError("phase batch retains an outcome without its original launch issuance")
        return
    if (type(state) is not _Owned or state.publisher is not publisher or state.batch is not batch
            or state.guard is not publisher.guard() or state.binding is not publisher.binding
            or state.scope is not batch.grant.scope or state.release != batch.release
            or (state.stop_ns, state.cleanup_ns) != (batch.stop_ns, batch.cleanup_ns)
            or state.pid != publisher.pid or state.thread is not publisher.thread
            or state.failed or not state.reaped or not state.reap_attempted or not state.consumed
            or not state.close_complete or state.handle in _CHILDREN or state.outcome_handle in _OUTCOMES
            or state.raw is None or any(getattr(state.raw, name) != -1 for name, _ in _CLOSES)
            or type(state.native_exit) is not _NativeExit or state.native_exit.pid != state.birth.pid
            or state.native_exit.uid != 65534 or state.native_exit.code != os.CLD_EXITED
            or state.native_exit.status != 0 or state.wait_observed is None or state.wait_reaped is None
            or state.observation is None or not state.observation.sealed
            or state.outcome is None or state.outcome_handle is not batch.outcome
            or not state.outcome_consumed or not batch.outcome_consumed
            or state.errors.first_error is not None or state.errors.failure.primary_error is not None
            or state.errors.aggregation_error is not None or state.errors.overflowed):
        raise PermissionError("phase closure retains an unconsumed/failed/unreaped original child/outcome")
    facts = publisher.owner.ledger_facts
    for event, digest in (("gt_broker_phase_child_observed", state.observation_history),
                          ("gt_broker_phase_child_finished", state.outcome_history),
                          ("gt_broker_phase_outcome_consumed", state.consumption_history)):
        if type(digest) is not str or not any(fact.event == event and fact.sha256 == digest for fact in facts):
            raise PermissionError("phase closure lacks the original durable child/outcome history")

__all__ = []
