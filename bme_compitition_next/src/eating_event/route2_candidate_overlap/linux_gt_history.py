"""Original startup owner's native GT broker and complete issuance history.

Installation is explicit, one-shot, at startup sequence two, before workers.
Metadata is read from frozen logical paths; GT contents are not read until a
privately accepted Stage B expansion and a durable prediction/release barrier.
No supplied history, receipt, readiness callback or boolean can install facts.
This module is trusted controller code, like startup/phase/terminal ownership.
It does not install a worker, prove its sandbox, or authorize an experiment.

The Ubuntu 22.04/glibc 2.35 mount bridge below is source integration only. Its
existing installation/write-boundary gate still refuses before helper loading.
The original bootstrap must establish the complete immutable interpreter,
stdlib, project, native and transitive dependency closure BEFORE any project or
ctypes import; this module cannot prove that earlier constructor boundary.
Pinned bytes and ELF/ABI inventories only reject drift after that real gate.
The cooperative ten-second read/load window uses the original Stage A/total
clocks and sixty-second stop margin. It cannot interrupt synchronous dlopen or
describe; the original armed kernel deadlines and independent full installation,
constructor/dependency and quarantine admission remain required.
There is no installed helper, full admission, or runtime evidence here.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import PurePosixPath, PureWindowsPath
import platform
import re
import stat
import sys
import threading
import time
from types import BuiltinFunctionType
import uuid
import weakref

from . import phase_observation as phase
from .budget import AppendOnlyLedger, BudgetGuard, _canonical
from .contracts import StudyStage, projection_scope_sha256, require_frozen_admission
from .gt_provider import FrozenRoleGraph, TruthReadScope, stage_gt_fields
from .linux_enforcement import registered_file_binds
from .native_failure_capture import NativeFailureCapture
from .path_map import (
    ExactFileMapping, ExactPathMap, MountReceipt, file_mapping,
    directory_file_mapping, _MANIFEST_V1, _MANIFEST_V2,
)
from .startup_ownership import StartupBinding, require_startup_binding


_ALIAS_ROOT = "/run/route2-input"
_GT_PHASES = frozenset(stage.value for stage in (
    StudyStage.TRAIN_LABELS, StudyStage.INNER_EVALUATION, StudyStage.OUTER_EVALUATION,
))
_LEDGER_EVENTS = frozenset({"gt_phase_released", "gt_phase_view_revoked", "gt_phase_result_accepted"})
_MAX_METADATA = 4 * 1024 * 1024
_MAX_GT_BYTES = 64 * 1024 * 1024
_MAX_HISTORY = 65536
_MAX_WORKER_IDENTITIES = 4096
_MOUNT_HELPER_LIBRARY = "lib/route2/mount_helper.so"
_MAX_MOUNT_HELPER_BYTES = 8 * 1024 * 1024
_MOUNT_HELPER_LOAD_NS = 10_000_000_000
_MOUNT_HELPER_STOP_MARGIN_NS = 60_000_000_000
_AT_EMPTY_PATH = 0x1000
_OPEN_TREE_CLONE = 1
_MOVE_EMPTY = 0x4 | 0x40  # MOVE_MOUNT_{F,T}_EMPTY_PATH
_UMOUNT_NOFOLLOW = 8
_MOUNT_ATTRIBUTES = 1 | 2 | 4 | 8  # RDONLY, NOSUID, NODEV, NOEXEC
_MS_PRIVATE = 1 << 18
_LOCK = threading.RLock()
_OWNERS = weakref.WeakKeyDictionary()
_BROKERS = weakref.WeakKeyDictionary()
# Capture, never invoke, the interpreter's original Linux builtin. Absence on
# another host is retained and refused only by the original active issuer.
_GETRANDOM = getattr(os, "getrandom", None)
_GRND_NONBLOCK = getattr(os, "GRND_NONBLOCK", None)
_GETRANDOM_MODULE = sys.modules.get("posix")
_METHODS = {name: getattr(AppendOnlyLedger, name) for name in (
    "append", "record_gt_release", "record_gt_revoke", "require_gt_release",
    "require_frozen_prediction", "_truth_scope_digest", "_hash_file", "_study_output",
)}


@dataclass(frozen=True, slots=True)
class _GTIdentity:
    source_path: str
    filesystem_root: str
    device: int
    inode: int
    mode: int
    uid: int
    nlink: int


@dataclass(frozen=True, slots=True)
class _WorkerBackingAnchor:
    study_root: str
    root: str
    study_identity: tuple[int, ...]
    study_mount_id: int
    filesystem_root: str


@dataclass(frozen=True, slots=True)
class _WorkerIdentity:
    path: str
    device: int
    inode: int
    mode: int


@dataclass(frozen=True, slots=True)
class _KernelAnchor:
    start_ticks: int
    native_tid: int
    mount_namespace: tuple[int, int]
    cgroup_namespace: tuple[int, int]
    pid_namespace: tuple[int, int]
    cgroup_mount_id: int
    cgroup_mount_device: str
    cgroup_directory: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _View:
    mapping: ExactFileMapping
    identity: _GTIdentity
    frame: tuple[int, ...]
    source_mount_id: int
    scope_sha256: str


@dataclass(frozen=True, slots=True)
class _Fact:
    event: str
    payload: bytes
    monotonic_ns: int
    previous_sha256: str
    sha256: str


@dataclass(frozen=True, slots=True)
class _LedgerFact:
    seq: int
    event: str
    payload: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class _Grant:
    view: _View
    scope: TruthReadScope
    scope_bytes: bytes
    release: str
    mount_id: int
    receipt: MountReceipt


@dataclass(frozen=True, slots=True)
class _OriginalRoleClosure:
    """Internal projection, usable only under the broker's held history lock."""

    binding: StartupBinding
    supervisor: object
    mount_controller: object
    controller_run_id: str
    manifest_sha256: str
    gt_registry_sha256: str
    gt_files: tuple[_GTIdentity, ...]
    gt_aliases: tuple[str, ...]
    issued_gt_mount_ids: tuple[int, ...]
    kernel: _KernelAnchor
    worker_backing: _WorkerBackingAnchor | None
    issued_worker_identities: tuple[_WorkerIdentity, ...] | None
    ledger_identity: tuple[int, int]
    ledger_fds: tuple[int, ...]
    phase_source_paths: tuple[str, ...]


@dataclass(slots=True)
class _CommitmentKey:
    """Original controller secret/attempt slots; no caller can supply a key."""

    producer: object | None = _GETRANDOM
    producer_module: object | None = _GETRANDOM_MODULE
    producer_type: type = BuiltinFunctionType
    flags: int | None = _GRND_NONBLOCK
    owner: object | None = None
    publisher: object | None = None
    binding: StartupBinding | None = None
    phase: object | None = None
    terminal: object | None = None
    ledger: object | None = None
    pins: tuple[str, ...] = ()
    pid: int | None = None
    thread: object | None = None
    batch: object | None = None
    grant: _Grant | None = None
    scope_bytes: bytes = b""
    release: str = ""
    stop_ns: int | None = None
    cleanup_ns: int | None = None
    clock: tuple = ()
    captures: tuple[NativeFailureCapture, ...] = ()
    origins: tuple[NativeFailureCapture, ...] = ()
    report_origin: NativeFailureCapture | None = None
    secondary_origin: NativeFailureCapture | None = None
    attempt_consumed: bool = False
    python_call_attempted: bool = False
    python_call_returned: bool = False
    raw: object | None = None
    raw_length: int | None = None
    secret_sha256: str | None = None
    return_validated: bool = False
    started_ns: int | None = None
    call_started_ns: int | None = None
    call_returned_ns: int | None = None
    finished_ns: int | None = None
    started_body: dict | None = None
    finished_body: dict | None = None
    started_sha256: str | None = None
    finished_sha256: str | None = None
    operation: str | None = None
    primary_error: BaseException | None = None
    secondary_error: BaseException | None = None
    ready: bool = False
    failed: bool = False
    unavailable_error: PermissionError = field(default_factory=lambda: PermissionError(
        "original Linux getrandom builtin is unavailable or replaced; provenance UNKNOWN"))
    invalid_return_error: PermissionError = field(default_factory=lambda: PermissionError(
        "original getrandom did not return exactly 32 bytes; key issuance refused"))


@dataclass(slots=True)
class _Owner:
    binding: StartupBinding
    broker: object
    phase: object
    terminal: object
    manifest: bytes
    pins: tuple[str, ...]
    run_id: str
    cgroup_path: str
    kernel: _KernelAnchor | None = None
    graph: FrozenRoleGraph | None = None
    views: tuple[_View, ...] = ()
    registry_sha256: str = ""
    facts: tuple[_Fact, ...] = ()
    ledger_facts: tuple[_LedgerFact, ...] = ()
    issued_ids: tuple[int, ...] = ()
    owned_fds: list[int] = field(default_factory=list)
    active: _Grant | None = None
    failed: bool = False
    installed: bool = False
    worker_backing: _WorkerBackingAnchor | None = None
    issued_worker_identities: tuple[_WorkerIdentity, ...] | None = None
    failure_errors: NativeFailureCapture = field(default_factory=lambda: NativeFailureCapture(1024))
    metadata_scopes: list = field(default_factory=lambda: [None, None])
    metadata_resources: list = field(default_factory=lambda: [None, None])
    mount_library: object | None = None
    mount_api: object | None = None
    mount_load_attempted: bool = False
    phase_publisher: object | None = None
    commitment_key: _CommitmentKey = field(default_factory=_CommitmentKey)
    # Strong original fixed-executor transactions, attached only on execution.
    # Installing the executor before guard.start does not create a GT actor.
    phase_executor: object | None = None
    phase_transactions: tuple = ()


class _MountAttr(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "attr_set", "attr_clr", "propagation", "userns_fd",
    )]


class _MountHelperABI(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "version", "glibc_major", "glibc_minor", "pointer_bytes", "long_bytes",
        "mount_attr_bytes", "attr_set_offset", "attr_clr_offset",
        "propagation_offset", "userns_fd_offset",
    )]


def _deny(message):
    raise PermissionError(message)


def _runtime():
    if (platform.system() != "Linux" or os.name != "posix" or os.geteuid() != 0
            or ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(ctypes.c_long) != 8):
        _deny("original GT broker requires the native root-owned Linux 64-bit runtime")


def _pins():
    frozen = require_frozen_admission()
    return tuple(getattr(frozen, name) for name in (
        "path_map_sha256", "gt_view_registry_sha256", "gt_role_graph_projection_sha256",
        "role_graph_sha256", "gt_input_root_path", "resource_controller_sha256",
    ))


def _native_methods(state):
    ledger = state.binding.ledger
    for name, function in _METHODS.items():
        actual = getattr(ledger, name)
        if isinstance(AppendOnlyLedger.__dict__[name], staticmethod):
            valid = actual is function
        else:
            valid = (getattr(actual, "__self__", None) is ledger
                     and getattr(actual, "__func__", None) is function)
        if not valid:
            _deny("GT broker requires the unchanged native ledger methods")


def _live(guard, state, *, closed=False):
    from . import terminal_observation as terminal

    _runtime()
    if (type(guard) is not BudgetGuard or _OWNERS.get(guard) is not state
            or require_startup_binding(guard) is not state.binding
            or _broker_guard(state.broker) is not guard
            or state.binding.owner() is None or state.pins != _pins()
            or phase._OBSERVERS.get(guard) is not state.phase
            or terminal._OBSERVERS.get(guard) is not state.terminal):
        _deny("original GT broker lost its private startup/owner/metadata binding")
    _native_methods(state)
    terminal._binding(guard, state.terminal)
    if closed:
        if state.terminal.step != "closed":
            _deny("original GT history requires the closed native terminal owner")
        terminal._actually_closed(state.terminal)
        phase._require_retired_writer_ofd(state.phase)
    else:
        phase._live_identity(guard, state.phase)
        if state.terminal.step != "registered":
            _deny("GT broker operations cannot continue after terminal preparation")


def _broker_guard(broker):
    reference = _BROKERS.get(broker)
    return reference() if reference is not None else None


def _private_fact(state, event, payload):
    # Append-only immutable values. Never discard failed attempts or overwrite
    # an active slot to manufacture an empty history. Overflow poisons forever.
    if len(state.facts) >= _MAX_HISTORY:
        state.failed = True
        _deny("original GT history exceeded its bounded complete-history limit")
    previous = state.facts[-1].sha256 if state.facts else "0" * 64
    stamp = time.monotonic_ns()
    encoded = _canonical(payload)
    digest = hashlib.sha256(_canonical(dict(event=event, payload=payload,
        monotonic_ns=stamp, previous_sha256=previous))).hexdigest()
    state.facts += (_Fact(event, encoded, stamp, previous, digest),)
    return digest


def _journal(guard, state):
    with phase._LOCK:
        try:
            return phase._journal(guard, state.phase)
        except BaseException as exc:
            # A journal read+close report retains its raw operation origin.
            # Preserve that origin in the broker before any other cleanup.
            report = getattr(exc, "failure_capture", None)
            if type(report) is NativeFailureCapture and report.failure is exc:
                if state.failure_errors.failure.primary_error is None:
                    state.failure_errors.failure.primary_error = report.failure.primary_error
                slot = next(state.failure_errors._cursor, None)
                if slot is None:
                    state.failure_errors.overflowed = True
                else:
                    slot.operation = "journal_reader_failure"
                    slot.error = exc
                    slot.descriptor = None
            raise


def _remember_tail(guard, state, event):
    journal = _journal(guard, state)
    record = journal.records[-1]
    if record["entry"]["event"] != event:
        _deny("native GT ledger append is not the actual durable owner tail")
    fact = _LedgerFact(record["entry"]["seq"], event,
                       _canonical(record["entry"]["payload"]), record["sha256"])
    state.ledger_facts += (fact,)
    return fact.sha256


def _record(guard, state, event, payload):
    payload = dict(payload, invocation_id=state.binding.invocation_id,
                   controller_run_id=state.run_id)
    history_digest = _private_fact(state, event, payload)
    body = dict(payload, history_sha256=history_digest)
    digest = state.binding.ledger.append(event, body)
    if _remember_tail(guard, state, event) != digest:
        _deny("GT broker durable append digest differs from the native writer")
    return digest


def _record_failure(guard, state, event, payload):
    """Preserve failure durably when the original writer is still available.

    Failed/partial fsync remains a private failed fact and poisons authority;
    failure preservation never creates a teardown or quiescence attestation.
    """
    try:
        _record(guard, state, event, payload)
    except BaseException as exc:
        state.failed = True
        return exc
    return None


def _raise_broker_failure(state, primary):
    """Retain original errors even when poisoned/full history cannot append.

    This is process-local failure evidence, never durable success, a revoke
    confirmation or permission to retry. Public messages contain no GT data.
    """
    state.failed = True
    try:
        state.failure_errors.record("primary", primary)
    except BaseException as aggregation_error:
        state.failure_errors.aggregation_error = aggregation_error
        # Inline reserved slots also cover failure to enter record().
        fallback_slot = next(state.failure_errors._cursor, None)
        if fallback_slot is None:
            state.failure_errors.overflowed = True
        else:
            fallback_slot.operation = 'primary'
            fallback_slot.error = primary
            fallback_slot.descriptor = None
        fallback_slot = next(state.failure_errors._cursor, None)
        if fallback_slot is None:
            state.failure_errors.overflowed = True
        else:
            fallback_slot.operation = 'record_entry_failure'
            fallback_slot.error = aggregation_error
            fallback_slot.descriptor = None
    state.failure_errors.raise_failure(primary)


def _check_ledger(state, records):
    observed = tuple(_LedgerFact(record["entry"]["seq"], record["entry"]["event"],
        _canonical(record["entry"]["payload"]), record["sha256"])
        for record in records if record["entry"]["event"] in _LEDGER_EVENTS
        or record["entry"]["event"].startswith("gt_broker_"))
    if observed != state.ledger_facts:
        _deny("GT ledger contains omitted, replaced or non-broker release/revocation history")


def _protected_file(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_nlink != 1 or info.st_mode & 0o022):
        _deny("original GT source/alias must be a protected root-owned single-link regular file")


def _file(scope, path, *, contents=False):
    from . import linux_quiescence as q

    q._path(path)
    parent = scope.directory(str(PurePosixPath(path).parent))
    name = PurePosixPath(path).name
    flags = (os.O_RDONLY if contents else os.O_PATH) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    descriptor = scope._open(name, flags, dir_fd=parent)
    info = os.fstat(descriptor)
    _protected_file(info)
    if q._frame(info) != q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False)):
        _deny("original GT source/alias changed during descriptor acquisition")
    scope.close_one(parent)
    return descriptor, q._frame(info)


def _mount_id(scope, descriptor, pid):
    from . import linux_quiescence as q

    directory = scope.directory(f"/proc/{pid}/fdinfo")
    primary = None
    try:
        encoded = scope.text(directory, str(descriptor), q._PROC_SUPER_MAGIC)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Lock the operation origin before entering one-FD cleanup.
        if primary is not None and scope.failures.failure.primary_error is None:
            scope.failures.failure.primary_error = primary
        try:
            scope.close_one(directory, primary_error=primary)
        except BaseException as close_one_dispatch_error:
            if scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = close_one_dispatch_error
            if close_one_dispatch_error is not scope.failures.failure:
                fallback_slot = next(scope.failures._cursor, None)
                if fallback_slot is None:
                    scope.failures.overflowed = True
                else:
                    fallback_slot.operation = 'close_one_dispatch_failure'
                    fallback_slot.error = close_one_dispatch_error
                    fallback_slot.descriptor = directory
            if directory in scope.owned:
                scope.owned.remove(directory)
                try:
                    os.close(directory)
                except BaseException as remaining_close_error:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'close_one_remaining_descriptor'
                        fallback_slot.error = remaining_close_error
                        fallback_slot.descriptor = directory
            scope.failures.failure.secondary_errors = scope.failures._slots
            scope.failures.failure.aggregation_error = scope.failures.aggregation_error
            raise scope.failures.failure from scope.failures.failure.primary_error
    fields = [line.split(b":", 1)[1].strip() for line in encoded.splitlines()
              if line.startswith(b"mnt_id:")]
    if len(fields) != 1 or re.fullmatch(rb"[1-9][0-9]*", fields[0]) is None:
        _deny("native GT descriptor lacks one kernel mount identity")
    return int(fields[0])


def _mounts(scope, pid):
    from . import linux_quiescence as q

    proc = scope.directory(f"/proc/{pid}")
    primary = None
    try:
        return q._mounts(scope.text(proc, "mountinfo", q._PROC_SUPER_MAGIC))
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Lock the operation origin before entering one-FD cleanup.
        if primary is not None and scope.failures.failure.primary_error is None:
            scope.failures.failure.primary_error = primary
        try:
            scope.close_one(proc, primary_error=primary)
        except BaseException as close_one_dispatch_error:
            if scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = close_one_dispatch_error
            if close_one_dispatch_error is not scope.failures.failure:
                fallback_slot = next(scope.failures._cursor, None)
                if fallback_slot is None:
                    scope.failures.overflowed = True
                else:
                    fallback_slot.operation = 'close_one_dispatch_failure'
                    fallback_slot.error = close_one_dispatch_error
                    fallback_slot.descriptor = proc
            if proc in scope.owned:
                scope.owned.remove(proc)
                try:
                    os.close(proc)
                except BaseException as remaining_close_error:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'close_one_remaining_descriptor'
                        fallback_slot.error = remaining_close_error
                        fallback_slot.descriptor = proc
            scope.failures.failure.secondary_errors = scope.failures._slots
            scope.failures.failure.aggregation_error = scope.failures.aggregation_error
            raise scope.failures.failure from scope.failures.failure.primary_error


def _source_mount(scope, descriptor, path, mounts, pid):
    from . import linux_quiescence as q

    mount_id = _mount_id(scope, descriptor, pid)
    found = [item for item in mounts if item.mount_id == mount_id]
    if len(found) != 1:
        _deny("original GT source mount is hidden or missing from the kernel namespace")
    mount = found[0]
    if ("ro" not in mount.options or "rw" in mount.options or mount.optional
            or not PurePosixPath(path).is_relative_to(mount.point)
            or mount.device != f"{os.major(os.fstat(descriptor).st_dev)}:{os.minor(os.fstat(descriptor).st_dev)}"):
        _deny("original GT inputs require a visible immutable private source mount")
    root = str(PurePosixPath(mount.root) / PurePosixPath(path).relative_to(mount.point))
    return mount_id, q._path(root)


def _source(mapping):
    # Translation is fixed by the reviewed logical identity; no resolver hook.
    return registered_file_binds((mapping,))[0].source_path


def _read_metadata(scope, mapping, pid):
    from . import linux_quiescence as q

    path = _source(mapping)
    fd, before = _file(scope, path, contents=True)
    _source_mount(scope, fd, path, _mounts(scope, pid), pid)
    if not 0 < before[6] <= _MAX_METADATA:
        _deny("GT metadata exceeds its bounded source frame")
    chunks, size = [], 0
    while True:
        scope.checkpoint()
        chunk = os.read(fd, min(65536, _MAX_METADATA - size + 1))
        size += len(chunk)
        if size > _MAX_METADATA:
            _deny("GT metadata grew beyond its bounded read")
        if not chunk:
            break
        chunks.append(chunk)
    encoded = b"".join(chunks)
    if (before != q._frame(os.fstat(fd)) or size != before[6]
            or hashlib.sha256(encoded).hexdigest() != mapping.sha256.lower()):
        _deny("original GT metadata differs from the frozen content pin")
    scope.close_one(fd)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _deny("GT metadata contains a repeated JSON key")
            result[key] = value
        return result
    return json.loads(encoded, object_pairs_hook=pairs)


def _registry(scope, state, path_map):
    from .linux_native_path_map import _get_original_metadata_path_map, _read_original_gt_metadata

    pins, pid = state.pins, state.binding.pid
    root = PureWindowsPath(pins[4])
    guard = _broker_guard(state.broker)
    original_map = _get_original_metadata_path_map(guard, state.manifest)
    if ((original_map is not None and path_map is not original_map)
            or (original_map is None and path_map.manifest_schema != _MANIFEST_V1)):
        _deny("GT registry requires its original issued map or the original legacy v1 map")
    def metadata(leaf, digest):
        key = (str(root / leaf), digest.lower(), "__study__", "preflight_metadata")
        mapping = path_map._entries.get(key)
        if mapping is None:
            _deny("original reviewed manifest omits pinned GT metadata")
        if original_map is not None:
            return _read_original_gt_metadata(guard, state, leaf)
        return _read_metadata(scope, mapping, pid)
    registry = metadata("gt-view-registry.json", pins[1])
    raw_graph = metadata("gt-role-scopes.json", pins[2])
    graph_names = ("training_label_participants", "training_outer_ids",
        "inner_evaluation_roles_by_outer", "outer_fit_participants", "outer_role_ids",
        "outer_evaluation_participants")
    if (type(raw_graph) is not dict or set(raw_graph) != {"schema", "role_graph_sha256", *graph_names}
            or raw_graph["schema"] != "route2_gt_role_scopes_v1"
            or raw_graph["role_graph_sha256"] != pins[3]
            or any(type(raw_graph[name]) is not dict for name in graph_names)):
        _deny("original GT role graph is not the complete pinned metadata projection")
    graph_maps = {}
    for name in graph_names:
        values = raw_graph[name]
        scalar = name in {"training_outer_ids", "outer_role_ids"}
        for key, value in values.items():
            if type(key) is not str or not key:
                _deny("pinned GT role graph contains a malformed role identity")
            if scalar:
                valid = type(value) is str and bool(value)
            else:
                valid = (type(value) is list and bool(value)
                         and all(type(item) is str and item for item in value)
                         and len(set(value)) == len(value))
            if not valid:
                _deny("pinned GT role graph contains malformed role/participant identities")
        graph_maps[name] = {key: value if scalar else tuple(value) for key, value in values.items()}
    graph = FrozenRoleGraph(sha256=pins[3], projection_sha256=pins[2], **graph_maps)
    if (type(registry) is not dict or set(registry) != {"schema", "role_graph_sha256",
            "gt_role_scopes_path", "gt_role_scopes_sha256", "views", "status"}
            or registry["schema"] != "route2_gt_view_registry_v1"
            or registry["status"] != "PREPARED_UNREVIEWED"
            or registry["role_graph_sha256"] != pins[3]
            or registry["gt_role_scopes_path"] != str(root / "gt-role-scopes.json")
            or registry["gt_role_scopes_sha256"] != pins[2]
            or type(registry["views"]) is not list or len(registry["views"]) != 110):
        _deny("original GT registry is not the complete pinned 100/5/5 projection")
    keys = {"kind", "phase", "role_id", "outer_id", "role_ids", "participants",
            "fields", "scope_sha256", "path", "sha256", "release_rule"}
    views, seen, counts = [], set(), dict.fromkeys(sorted(_GT_PHASES), 0)
    original_mounts = _mounts(scope, pid)
    for record in registry["views"]:
        if (type(record) is not dict or set(record) != keys or record["kind"] != "gt"
                or record["phase"] not in _GT_PHASES
                or any(type(record[name]) is not str for name in keys - {"role_ids", "participants", "fields"})
                or any(type(record[name]) is not list or any(type(item) is not str for item in record[name])
                       for name in ("role_ids", "participants", "fields"))):
            _deny("original GT registry contains an unapproved record")
        stage, role, outer = StudyStage(record["phase"]), record["role_id"], record["outer_id"]
        if stage == StudyStage.TRAIN_LABELS:
            roles, participants = (role,), graph.training_label_participants.get(role)
            expected_outer, directory, release = graph.training_outer_ids.get(role), "gt-training", "training_role_only"
        elif stage == StudyStage.INNER_EVALUATION:
            roles, participants = graph.inner_evaluation_roles_by_outer.get(outer), graph.outer_fit_participants.get(outer)
            expected_outer, directory, release = outer, "gt-inner", "after_matching_frozen_prediction_receipt"
        else:
            roles, participants = (graph.outer_role_ids.get(outer),), graph.outer_evaluation_participants.get(outer)
            expected_outer, directory, release = outer, "gt-outer", "after_matching_frozen_prediction_receipt"
        role_scope = role if stage == StudyStage.TRAIN_LABELS else outer
        expected_path = str(root / directory / (hashlib.sha256(role_scope.encode()).hexdigest()[:20] + ".jsonl"))
        if (roles is None or participants is None or outer != expected_outer or role != role_scope
                or tuple(record["role_ids"]) != roles or tuple(record["participants"]) != participants
                or tuple(record["fields"]) != stage_gt_fields(stage) or record["release_rule"] != release
                or record["path"] != expected_path):
            _deny("original GT registry escapes the frozen phase/role/participant projection")
        scope_hash = projection_scope_sha256(f"gt:{stage.value}:{outer}:{','.join(roles)}",
            outer, participants, stage_gt_fields(stage), role_graph_sha256=pins[3])
        mapping = path_map._entries.get((record["path"], record["sha256"].lower(), role, stage.value))
        key = (stage.value, role)
        if mapping is None or record["scope_sha256"] != scope_hash or key in seen:
            _deny("original GT registry is duplicated or differs from the exact reviewed manifest")
        seen.add(key)
        counts[stage.value] += 1
        path = _source(mapping)
        fd, frame = _file(scope, path)  # O_PATH: no GT content access at startup
        mount_id, fs_root = _source_mount(scope, fd, path, original_mounts, pid)
        if not 0 < frame[6] <= _MAX_GT_BYTES:
            _deny("original GT file size is outside its bounded registered frame")
        identity = _GTIdentity(path, fs_root, frame[0], frame[1], frame[2], frame[3], frame[5])
        views.append(_View(mapping, identity, frame, mount_id, scope_hash))
        scope.close_one(fd)
    if (original_mounts != _mounts(scope, pid)
            or counts != {"train_labels": 100, "inner_evaluation": 5, "outer_evaluation": 5}
            or {view.mapping.key for view in views} != {item.key for item in path_map._entries.values() if item.phase in _GT_PHASES}
            or len({(view.identity.device, view.identity.inode) for view in views}) != len(views)):
        _deny("original GT registry/manifest does not cover every unique protected GT identity")
    return graph, tuple(sorted(views, key=lambda item: item.mapping.key))


def _kernel(scope, binding, cgroup_path):
    from . import linux_quiescence as q

    proc = scope.directory(f"/proc/{binding.pid}")
    q._filesystem(proc, q._PROC_SUPER_MAGIC)
    ns = scope.open_at(proc, "ns", directory=True)
    identities = tuple(scope.namespace(ns, name)[1] for name in ("mnt", "cgroup", "pid"))
    init = scope.directory("/proc/1/ns")
    if scope.namespace(init, "mnt")[1] == identities[0]:
        _deny("native GT broker cannot operate in the initial mount namespace")
    ticks = q._start_ticks(scope.text(proc, "stat", q._PROC_SUPER_MAGIC), binding.pid)
    tid = threading.get_native_id()
    tasks = scope.open_at(proc, "task", directory=True)
    if tid != binding.pid or scope.names(tasks, 2) != (str(binding.pid),):
        _deny("original GT broker requires the sole original main controller task")
    q._membership(scope, proc, cgroup_path)
    mounts = _mounts(scope, binding.pid)
    cgroups = [item for item in mounts if item.point == "/sys/fs/cgroup"]
    if (len(cgroups) != 1 or cgroups[0].filesystem != "cgroup2" or cgroups[0].root != "/"
            or not {"ro", "nosuid", "nodev", "noexec"} <= cgroups[0].options
            or any(item.point.startswith("/sys/fs/cgroup/") for item in mounts)):
        _deny("original GT broker requires the protected unified cgroup mount")
    directory = scope.directory("/sys/fs/cgroup" + cgroup_path)
    q._require_only_controller(q._tree(scope, directory)[0], binding.pid)
    return _KernelAnchor(ticks, tid, *identities, cgroups[0].mount_id,
                         cgroups[0].device, q._identity(os.fstat(directory)))


def _closure(state):
    from .linux_phase_publication import _closure_additions

    copies, targets, retained_ids, phase_paths = _closure_additions(state)
    all_ids = state.issued_ids + tuple(value for value in retained_ids if value not in state.issued_ids)
    anchor = state.phase.ofd_anchor
    ledger_fds = (state.phase.owner_fd,)
    if anchor is not None:
        ledger_fds += (anchor.descriptor,)
    if type(state.terminal.anchor_fd) is int:
        ledger_fds += (state.terminal.anchor_fd,)
    return _OriginalRoleClosure(state.binding, state.binding.owner(), state.broker,
        state.run_id, state.pins[0], state.pins[1], tuple(view.identity for view in state.views) + copies,
        tuple(view.mapping.bind_path for view in state.views) + targets, all_ids, state.kernel,
        state.worker_backing, state.issued_worker_identities,
        (state.phase.identity[0], state.phase.identity[1]), ledger_fds, phase_paths)


def _worker_backing_snapshot(state, *, initial=False):
    """Metadata only, from the original study root; never accept caller paths.

    Root ownership protects the backing boundary; worker-owned descendants are
    inspected without following links or crossing devices/mounts. Missing,
    inaccessible, changing or excess evidence refuses rather than assuming an
    empty registry. The initial absence of .worker is observed before workers.
    """
    from . import linux_quiescence as q

    scope = q._ReadScope()
    primary = None
    try:
        study_path = q._path(str(state.binding.study_root))
        root_path = str(PurePosixPath(study_path) / ".worker")
        study = scope.directory(study_path)
        info = os.fstat(study)
        study_identity = q._identity(info)[:5]  # child creation can change nlink
        mount_id = _mount_id(scope, study, state.binding.pid)
        mounts = [row for row in _mounts(scope, state.binding.pid) if row.mount_id == mount_id]
        if (len(mounts) != 1 or not PurePosixPath(root_path).is_relative_to(mounts[0].point)
                or mounts[0].device != f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"):
            _deny("original worker backing filesystem root is unavailable or hidden")
        filesystem_root = q._path(str(PurePosixPath(mounts[0].root)
            / PurePosixPath(root_path).relative_to(mounts[0].point)))
        current = _WorkerBackingAnchor(study_path, root_path, study_identity, mount_id, filesystem_root)
        if initial:
            if state.worker_backing is not None or state.issued_worker_identities is not None:
                _deny("original worker backing anchor may be captured only once")
            state.worker_backing = current
        elif type(state.worker_backing) is not _WorkerBackingAnchor or current != state.worker_backing:
            _deny("original worker backing root/device/mount identity is unavailable or replaced")
        rows = []
        count = 0
        device = info.st_dev

        def visit(parent, name, path, depth):
            nonlocal count
            scope.checkpoint()
            count += 1
            if count > _MAX_WORKER_IDENTITIES or depth > q._MAX_DEPTH:
                _deny("worker backing identity scan exceeds its bounded complete registry")
            visible = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (visible.st_dev != device or not (stat.S_ISREG(visible.st_mode) or stat.S_ISDIR(visible.st_mode))
                    or visible.st_mode & 0o022 or stat.S_ISREG(visible.st_mode) and visible.st_nlink != 1):
                _deny("worker backing metadata contains a link, foreign device or unsafe object")
            flags = os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            flags |= os.O_RDONLY | os.O_DIRECTORY if stat.S_ISDIR(visible.st_mode) else os.O_PATH
            descriptor = scope._open(name, flags, dir_fd=parent)
            descriptor_primary = None
            try:
                before = q._frame(os.fstat(descriptor))
                if (before != q._frame(visible)
                        or _mount_id(scope, descriptor, state.binding.pid) != mount_id):
                    _deny("worker backing object changed or is on an unrecorded mount")
                rows.append(_WorkerIdentity(path, before[0], before[1], before[2]))
                if stat.S_ISDIR(visible.st_mode):
                    names = scope.names(descriptor, q._MAX_DIRECTORY_ENTRIES)
                    for child in names:
                        child_path = q._path(str(PurePosixPath(path) / child))
                        visit(descriptor, child, child_path, depth + 1)
                    if names != scope.names(descriptor, q._MAX_DIRECTORY_ENTRIES):
                        _deny("worker backing directory changed during identity capture")
                if (before != q._frame(os.fstat(descriptor))
                        or before != q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False))):
                    _deny("worker backing identity/frame changed during its native scan")
            except BaseException as exc:
                descriptor_primary = exc
                raise
            finally:
                # Lock the operation origin before entering one-FD cleanup.
                if descriptor_primary is not None and scope.failures.failure.primary_error is None:
                    scope.failures.failure.primary_error = descriptor_primary
                try:
                    scope.close_one(descriptor, primary_error=descriptor_primary)
                except BaseException as close_one_dispatch_error:
                    if scope.failures.failure.primary_error is None:
                        scope.failures.failure.primary_error = close_one_dispatch_error
                    if close_one_dispatch_error is not scope.failures.failure:
                        fallback_slot = next(scope.failures._cursor, None)
                        if fallback_slot is None:
                            scope.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'close_one_dispatch_failure'
                            fallback_slot.error = close_one_dispatch_error
                            fallback_slot.descriptor = descriptor
                    if descriptor in scope.owned:
                        scope.owned.remove(descriptor)
                        try:
                            os.close(descriptor)
                        except BaseException as remaining_close_error:
                            fallback_slot = next(scope.failures._cursor, None)
                            if fallback_slot is None:
                                scope.failures.overflowed = True
                            else:
                                fallback_slot.operation = 'close_one_remaining_descriptor'
                                fallback_slot.error = remaining_close_error
                                fallback_slot.descriptor = descriptor
                    scope.failures.failure.secondary_errors = scope.failures._slots
                    scope.failures.failure.aggregation_error = scope.failures.aggregation_error
                    raise scope.failures.failure from scope.failures.failure.primary_error

        try:
            worker_info = os.stat(".worker", dir_fd=study, follow_symlinks=False)
        except FileNotFoundError:
            # This is an actual ENOENT under the held original parent, not a
            # caller's empty list. A second name lookup fences its absence.
            if ".worker" in scope.names(study, q._MAX_DIRECTORY_ENTRIES):
                _deny("worker backing namespace appeared during its absence observation")
        else:
            q._protected(worker_info, directory=True)
            visit(study, ".worker", root_path, 0)
        if (q._identity(os.fstat(study))[:5] != study_identity
                or q._identity(os.stat(study_path, follow_symlinks=False))[:5] != study_identity):
            _deny("original study backing directory changed during worker identity capture")
        return tuple(rows)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Guard the Python cleanup entry as well as the native close.
        if primary is not None and scope.failures.failure.primary_error is None:
            scope.failures.failure.primary_error = primary
        try:
            scope.close(primary_error=primary)
        except BaseException as close_dispatch_error:
            if scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = close_dispatch_error
            if close_dispatch_error is not scope.failures.failure:
                fallback_slot = next(scope.failures._cursor, None)
                if fallback_slot is None:
                    scope.failures.overflowed = True
                else:
                    fallback_slot.operation = 'close_dispatch_failure'
                    fallback_slot.error = close_dispatch_error
                    fallback_slot.descriptor = None
            # Already consumed descriptor numbers never enter this fallback.
            while scope.owned:
                remaining_descriptor = scope.owned.pop()
                try:
                    os.close(remaining_descriptor)
                except BaseException as remaining_close_error:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'remaining_descriptor_close'
                        fallback_slot.error = remaining_close_error
                        fallback_slot.descriptor = remaining_descriptor
            scope.failures.failure.secondary_errors = scope.failures._slots
            scope.failures.failure.aggregation_error = scope.failures.aggregation_error
            raise scope.failures.failure from scope.failures.failure.primary_error


def _record_worker_backing(guard, state, *, initial=False):
    rows = _worker_backing_snapshot(state, initial=initial)
    previous = () if initial else state.issued_worker_identities
    if type(previous) is not tuple:
        _deny("original issued worker identity history is unavailable")
    known = set(previous)
    added = tuple(row for row in rows if row not in known)
    if len(previous) + len(added) > _MAX_WORKER_IDENTITIES:
        _deny("original issued worker identity history exceeds its bound")
    state.issued_worker_identities = previous + added
    if not initial and added:
        _record(guard, state, "gt_broker_worker_backing_observed", {
            "backing": asdict(state.worker_backing), "identities": [asdict(row) for row in added],
        })


def _require_recorded_worker_backing(state):
    if type(state.worker_backing) is not _WorkerBackingAnchor or type(state.issued_worker_identities) is not tuple:
        _deny("quiescence requires the original backing root and recorded issued worker identities")
    recorded = []
    registered = False
    for fact in state.facts:
        if fact.event not in {"gt_broker_registered", "gt_broker_worker_backing_observed"}:
            continue
        payload = json.loads(fact.payload)
        if fact.event == "gt_broker_registered":
            if registered:
                _deny("original worker backing registration was repeated")
            registered = True
            backing, identities = payload.get("worker_backing"), payload.get("issued_worker_identities")
        else:
            if not registered:
                _deny("worker backing history precedes original registration")
            backing, identities = payload.get("backing"), payload.get("identities")
        # The durable JSON representation uses arrays for the anchor's tuple.
        # Compare canonical JSON after requiring the exact recorded shape, so
        # an unchanged anchor survives decoding without relaxing its metadata.
        expected_backing = asdict(state.worker_backing)
        if (type(backing) is not dict or set(backing) != set(expected_backing)
                or type(backing.get("study_identity")) is not list
                or len(backing["study_identity"]) != len(state.worker_backing.study_identity)
                or any(type(value) is not int for value in backing["study_identity"])
                or _canonical(backing) != _canonical(expected_backing)
                or type(identities) is not list):
            _deny("original worker backing history differs from its native metadata anchor")
        recorded.extend(identities)
    if (not registered or _canonical(recorded)
            != _canonical([asdict(row) for row in state.issued_worker_identities])):
        _deny("original issued worker identities lack complete native recorded history")
    known = set(state.issued_worker_identities)
    if any(row not in known for row in _worker_backing_snapshot(state)):
        _deny("quiescence found worker backing objects without original native identity history")


def _kernel_identity(scope, state):
    """Revalidate original kernel anchors without requiring workers to be gone."""
    from . import linux_quiescence as q

    proc = scope.directory(f"/proc/{state.binding.pid}")
    ns = scope.open_at(proc, "ns", directory=True)
    observed = tuple(scope.namespace(ns, name)[1] for name in ("mnt", "cgroup", "pid"))
    if (observed != (state.kernel.mount_namespace, state.kernel.cgroup_namespace, state.kernel.pid_namespace)
            or q._start_ticks(scope.text(proc, "stat", q._PROC_SUPER_MAGIC), state.binding.pid) != state.kernel.start_ticks
            or threading.get_native_id() != state.kernel.native_tid):
        _deny("GT broker left its original startup namespace/task/process identity")
    tasks = scope.open_at(proc, "task", directory=True)
    if scope.names(tasks, 2) != (str(state.binding.pid),):
        _deny("GT broker syscall issuance requires the sole original controller task")
    q._membership(scope, proc, state.cgroup_path)
    directory = scope.directory("/sys/fs/cgroup" + state.cgroup_path)
    if q._identity(os.fstat(directory)) != state.kernel.cgroup_directory:
        _deny("GT broker original cgroup directory changed")
    mounts = _mounts(scope, state.binding.pid)
    cgroups = [item for item in mounts if item.point == "/sys/fs/cgroup"]
    if (len(cgroups) != 1 or cgroups[0].mount_id != state.kernel.cgroup_mount_id
            or cgroups[0].device != state.kernel.cgroup_mount_device or cgroups[0].root != "/"
            or cgroups[0].filesystem != "cgroup2"
            or not {"ro", "nosuid", "nodev", "noexec"} <= cgroups[0].options
            or any(item.point.startswith("/sys/fs/cgroup/") for item in mounts)):
        _deny("GT broker original protected cgroup mount changed")


def _require_worker_reference_closure_before_revoke(state):
    """Fence actual workers/references before unmounting the active GT view.

    The active bind is intentionally still present. No GT contents are read.
    Native repeated observations do not replace the missing original worker
    launch/wait history or independently enforced complete worker sandbox.
    """
    from . import linux_quiescence as q

    read = q._ReadScope()
    primary = None
    try:
        _kernel_identity(read, state)
        proc = read.directory(f"/proc/{state.binding.pid}")
        first_mount_text = read.text(proc, "mountinfo", q._PROC_SUPER_MAGIC)
        directory = read.directory("/sys/fs/cgroup" + state.cgroup_path)
        if q._identity(os.fstat(directory)) != state.kernel.cgroup_directory:
            _deny("GT revoke lost its original held cgroup identity")
        original = _closure(state)
        first_tree, held = q._tree(read, directory)
        q._require_only_controller(first_tree, state.binding.pid)
        q._require_no_children(read)
        descriptors = read.open_at(proc, "fd", directory=True)
        q._filesystem(descriptors, q._PROC_SUPER_MAGIC)
        first_fds = q._fd_snapshot(read, descriptors, original)
        q._require_no_gt_mappings(read.text(proc, "maps", q._PROC_SUPER_MAGIC), original)
        second_tree, _ = q._tree(read, directory, held=held)
        q._require_only_controller(second_tree, state.binding.pid)
        q._require_no_children(read)
        if first_tree != second_tree or first_fds != q._fd_snapshot(read, descriptors, original):
            _deny("worker population or controller references changed before native GT revoke")
        q._require_no_gt_mappings(read.text(proc, "maps", q._PROC_SUPER_MAGIC), original)
        if first_mount_text != read.text(proc, "mountinfo", q._PROC_SUPER_MAGIC):
            _deny("controller mount tree changed during the GT revoke reference fence")
        _kernel_identity(read, state)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Guard the Python cleanup entry as well as the native close.
        if primary is not None and read.failures.failure.primary_error is None:
            read.failures.failure.primary_error = primary
        try:
            read.close(primary_error=primary)
        except BaseException as close_dispatch_error:
            if read.failures.failure.primary_error is None:
                read.failures.failure.primary_error = close_dispatch_error
            if close_dispatch_error is not read.failures.failure:
                fallback_slot = next(read.failures._cursor, None)
                if fallback_slot is None:
                    read.failures.overflowed = True
                else:
                    fallback_slot.operation = 'close_dispatch_failure'
                    fallback_slot.error = close_dispatch_error
                    fallback_slot.descriptor = None
            # Already consumed descriptor numbers never enter this fallback.
            while read.owned:
                remaining_descriptor = read.owned.pop()
                try:
                    os.close(remaining_descriptor)
                except BaseException as remaining_close_error:
                    fallback_slot = next(read.failures._cursor, None)
                    if fallback_slot is None:
                        read.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'remaining_descriptor_close'
                        fallback_slot.error = remaining_close_error
                        fallback_slot.descriptor = remaining_descriptor
            read.failures.failure.secondary_errors = read.failures._slots
            read.failures.failure.aggregation_error = read.failures.aggregation_error
            raise read.failures.failure from read.failures.failure.primary_error
    read.checkpoint()


def _clear_mounts(scope, state):
    from . import linux_quiescence as q

    q._gt_mounts(_mounts(scope, state.binding.pid), _closure(state))


def _libc(guard, state, *, cleanup=False):
    """Return the original one-shot helper bridge; never confer installation.

    Cleanup only reuses a successfully bound original API. It neither reloads
    after failure nor requires a healthy journal; the revoke caller has already
    checked the original kernel/mount identity. No caller path, port callback,
    boolean or serialized descriptor can authorize loading this helper.
    """
    entered_ns = time.monotonic_ns()
    _runtime()
    if (type(guard) is not BudgetGuard or type(state) is not _Owner
            or _OWNERS.get(guard) is not state or type(state.broker) is not LinuxNativeGTBroker
            or _broker_guard(state.broker) is not guard or type(cleanup) is not bool
            or type(state.mount_load_attempted) is not bool):
        _deny("mount helper requires the original private GT broker owner")
    binding = require_startup_binding(guard)
    from .budget import BudgetLimits
    from .contracts import FrozenAdmission
    from .linux_production_controller import LinuxProductionController, LinuxProductionOSPorts
    from .linux_supervisor import Route2Supervisor

    if (type(binding) is not StartupBinding or binding is not state.binding
            or binding.pid != os.getpid() or binding.thread is not threading.current_thread()
            or type(binding.ledger) is not AppendOnlyLedger
            or type(binding.owner()) is not Route2Supervisor
            or type(binding.controller) is not LinuxProductionController
            or guard.enforcer is not binding.controller or type(binding.limits) is not BudgetLimits
            or type(state.failure_errors) is not NativeFailureCapture
            or platform.machine() != "x86_64" or (state.failed and not cleanup)):
        _deny("mount helper lost its original native startup/controller identity")
    controller = binding.controller
    assembly = LinuxProductionController._state(controller, allow_failed=cleanup)
    if (assembly.guard() is not guard or assembly.started_ns != binding.started_ns
            or assembly.limits is not binding.limits or type(assembly.ports) is not LinuxProductionOSPorts):
        _deny("mount helper forbids supplied controller or installation-port implementations")
    signatures = {
        "open_tree": ("route2_open_tree", (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)),
        "mount_setattr": ("route2_mount_setattr", (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
                           ctypes.POINTER(_MountAttr), ctypes.c_size_t)),
        "move_mount": ("route2_move_mount", (ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                                           ctypes.c_char_p, ctypes.c_uint)),
        "umount2": ("route2_umount2", (ctypes.c_char_p, ctypes.c_int)),
    }
    describe_args = (ctypes.POINTER(_MountHelperABI), ctypes.c_size_t)
    if state.mount_api is not None:
        library = state.mount_library
        if (type(library) is not ctypes.CDLL or state.mount_api is not library
                or state.mount_load_attempted is not True):
            _deny("mount helper cache is not the original retained native library")
        for bridge, (name, args) in signatures.items():
            function = getattr(library, name, None)
            if (type(function) is not library._FuncPtr or getattr(library, bridge, None) is not function
                    or function.argtypes != args or function.restype is not ctypes.c_int
                    or getattr(function, "errcheck", None) is not None):
                _deny("mount helper cache lost its original exact native callable bindings")
        describe = getattr(library, "route2_mount_helper_describe_v1", None)
        if (type(describe) is not library._FuncPtr or describe.argtypes != describe_args
                or describe.restype is not ctypes.c_int or getattr(describe, "errcheck", None) is not None):
            _deny("mount helper cache lost its original native description binding")
        return library
    if cleanup or state.mount_load_attempted:
        _deny("mount helper failed or absent first load cannot be retried, including cleanup")
    if (state.installed or state.active is not None or binding.ledger._seq != 2
            or state.phase.accepted or state.phase.pending is not None):
        _deny("mount helper first load requires the original pre-worker startup sequence two")
    state.mount_load_attempted = True
    deadline = min(entered_ns + _MOUNT_HELPER_LOAD_NS,
                   assembly.started_ns + assembly.limits.stage_a_wall_ns - _MOUNT_HELPER_STOP_MARGIN_NS,
                   assembly.started_ns + assembly.limits.total_wall_ns - _MOUNT_HELPER_STOP_MARGIN_NS)
    frozen, policy, _ = LinuxProductionController._policy(controller, assembly)
    # The unchanged concrete class gate still raises. It must independently
    # cover symbol providers/versions, constructors and every transitive readonly
    # path before dlopen; the later inventory below cannot replace that proof.
    LinuxProductionOSPorts.require_installation_and_write_boundary(
        assembly.ports, policy, frozen, assembly.unit_observation)
    from . import phase_worker_entry as wire
    from . import linux_deadline as deadline_owner
    from .linux_child_launch import _pinned_bytes
    from .linux_enforcement import ResourceEnvelope
    from .mount_helper_inspection import inspect_candidate_helper_elf, inspect_candidate_mount_abi

    wire._check(deadline)
    if (type(frozen) is not FrozenAdmission or frozen is not require_frozen_admission()
            or type(assembly.envelope) is not ResourceEnvelope
            or assembly.envelope.stop_margin_ns != _MOUNT_HELPER_STOP_MARGIN_NS
            or assembly.envelope.stage_a_wall_ns != assembly.limits.stage_a_wall_ns
            or assembly.envelope.total_wall_ns != assembly.limits.total_wall_ns
            or assembly.envelope.runtime_max_ns != assembly.limits.total_wall_ns - _MOUNT_HELPER_STOP_MARGIN_NS
            or assembly.envelope.stage_a_stop_ns != assembly.limits.stage_a_wall_ns - _MOUNT_HELPER_STOP_MARGIN_NS
            or assembly.total_timer_armed is not True or assembly.total_timer is assembly.stage_timer
            or ctypes.sizeof(ctypes.c_int) != 4 or ctypes.sizeof(ctypes.c_uint) != 4
            or ctypes.sizeof(ctypes.c_size_t) != 8 or ctypes.sizeof(_MountHelperABI) != 40
            or ctypes.sizeof(_MountAttr) != 32
            or tuple(getattr(_MountAttr, name).offset for name, _ in _MountAttr._fields_) != (0, 8, 16, 24)):
        _deny("mount helper lost its original LP64 ABI or controller budget envelope")
    for handle, original_deadline in (
            (assembly.total_timer, assembly.started_ns + assembly.envelope.runtime_max_ns),
            (assembly.stage_timer, assembly.started_ns + assembly.envelope.stage_a_stop_ns)):
        timer = deadline_owner._TIMERS.get(handle) if type(handle) is deadline_owner.LinuxKernelDeadline else None
        if (type(timer) is not deadline_owner._NativeTimer or timer.consumed is not False or timer.armed is not True
                or timer.pid != binding.pid or timer.thread is not binding.thread
                or type(timer.deadline_ns) is not int or timer.deadline_ns != original_deadline
                or type(timer.library) is not ctypes.CDLL or type(timer.timer_id) is not ctypes.c_void_p):
            _deny("mount helper requires the original unconsumed armed kernel Stage A/total deadlines")
    raw = _pinned_bytes(frozen.runtime_snapshot_manifest_path, frozen.runtime_snapshot_sha256.lower(),
                        wire._MAX_BYTES, deadline, state.failure_errors)
    manifest = wire._loads(raw, deadline)
    if (type(manifest) is not dict or set(manifest) != {"schema", "files"}
            or manifest["schema"] != "route2_immutable_source_snapshot_v1"
            or type(manifest["files"]) is not list or not manifest["files"]
            or _canonical(manifest) != raw):
        _deny("mount helper requires the complete canonical frozen runtime manifest")
    wire._check(deadline)
    names, entry = set(), None
    for row in manifest["files"]:
        wire._check(deadline)
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            _deny("mount helper runtime manifest contains an unreviewed file entry")
        name, size, digest = row["path"], row["bytes"], row["sha256"]
        if type(name) is not str:
            _deny("mount helper runtime manifest path is not plain text")
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or relative.as_posix() != name
                or any(part in ("", ".", "..") for part in relative.parts)
                or "\\" in name or "\x00" in name or name in names
                or type(size) is not int or size < 0 or type(digest) is not str
                or re.fullmatch(r"[0-9a-f]{64}", digest.lower()) is None):
            _deny("mount helper runtime manifest file identity is malformed or repeated")
        names.add(name)
        if name == _MOUNT_HELPER_LIBRARY:
            entry = row
    if entry is None or not 0 < entry["bytes"] <= _MAX_MOUNT_HELPER_BYTES:
        _deny("fixed reviewed mount helper is absent or exceeds its eight-MiB bound")
    root = frozen.runtime_snapshot_root
    if (type(root) is not str or not PurePosixPath(root).is_absolute()
            or PurePosixPath(root).as_posix() != root or ".." in PurePosixPath(root).parts
            or "\\" in root or "\x00" in root):
        _deny("mount helper requires the original canonical frozen runtime root")
    library_path = PurePosixPath(root) / _MOUNT_HELPER_LIBRARY
    image = _pinned_bytes(library_path, entry["sha256"].lower(), entry["bytes"], deadline, state.failure_errors)
    if len(image) != entry["bytes"]:
        _deny("mount helper bytes differ from the exact unique runtime manifest member")
    inventory = inspect_candidate_helper_elf(bytes(image))
    wire._check(deadline)
    if (inventory.needed != ("libc.so.6",) or inventory.rpath is not None
            or inventory.runpath is not None or inventory.soname not in (None, "mount_helper.so")):
        _deny("mount helper ELF inventory differs from the reviewed fixed dependency/search baseline")
    # This inventory only rejects unsupported ELF metadata; it proves no
    # provider, constructor, dependency closure or actual loaded mapping.
    library = ctypes.CDLL(str(library_path), mode=os.RTLD_NOW | os.RTLD_LOCAL, use_errno=True)
    state.mount_library = library  # Retain even a post-load failure; never dlclose/reload.
    wire._check(deadline)
    describe = getattr(library, "route2_mount_helper_describe_v1", None)
    if type(library) is not ctypes.CDLL or type(describe) is not library._FuncPtr:
        _deny("mount helper lacks its original exact native description export")
    describe.argtypes, describe.restype = describe_args, ctypes.c_int
    for bridge, (name, args) in signatures.items():
        function = getattr(library, name, None)
        if type(function) is not library._FuncPtr:
            _deny("mount helper lacks a reviewed namespaced native mount export")
        function.argtypes, function.restype = args, ctypes.c_int
        setattr(library, bridge, function)
    wire._check(deadline)
    description = _MountHelperABI()
    native_error = OSError("native GT mount helper description failed")
    native_error.strerror = "native GT mount helper description failed"
    ctypes.set_errno(0)
    result = describe(ctypes.byref(description), ctypes.sizeof(description))
    error = ctypes.get_errno()  # Capture immediately, before checks, parsing or cleanup.
    if result != 0:
        native_error.errno = error
        if state.failure_errors.failure.primary_error is None:
            state.failure_errors.failure.primary_error = native_error
        raise native_error
    wire._check(deadline)
    inspect_candidate_mount_abi(bytes(description))
    wire._check(deadline)
    state.mount_api = library
    return library


def _call(guard, state, libc, name, args, details, *, descriptor=False):
    if descriptor and len(state.owned_fds) >= 4:
        _deny("original GT broker exceeded its native descriptor bound")
    native_error = OSError("native GT mount syscall failed")
    native_error.strerror = "native GT mount syscall failed"
    _record(guard, state, "gt_broker_syscall_started", dict(details, syscall=name))
    ctypes.set_errno(0)
    result = getattr(libc, name)(*args)
    error = ctypes.get_errno() if result < 0 else 0
    if result < 0:
        native_error.errno = error
        if state.failure_errors.failure.primary_error is None:
            state.failure_errors.failure.primary_error = native_error
        try:
            state.failure_errors.record("native_syscall", native_error)
        except BaseException as aggregation_error:
            state.failure_errors.aggregation_error = aggregation_error
            # Inline reserved slots also cover failure to enter record().
            fallback_slot = next(state.failure_errors._cursor, None)
            if fallback_slot is None:
                state.failure_errors.overflowed = True
            else:
                fallback_slot.operation = 'native_syscall'
                fallback_slot.error = native_error
                fallback_slot.descriptor = None
            fallback_slot = next(state.failure_errors._cursor, None)
            if fallback_slot is None:
                state.failure_errors.overflowed = True
            else:
                fallback_slot.operation = 'record_entry_failure'
                fallback_slot.error = aggregation_error
                fallback_slot.descriptor = None
        try:
            _private_fact(state, "native_syscall_returned", dict(details, syscall=name, result=result, errno=error))
            _record(guard, state, "gt_broker_syscall_finished",
                    dict(details, syscall=name, result=result, errno=error))
        except BaseException as history_error:
            try:
                state.failure_errors.record("native_syscall_failure_history", history_error)
            except BaseException as aggregation_error:
                state.failure_errors.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'native_syscall_failure_history'
                    fallback_slot.error = history_error
                    fallback_slot.descriptor = None
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = None
            _raise_broker_failure(state, native_error)
        raise native_error
    # Own an acquired FD before a result append can fail. Interrupted/failed
    # syscalls are never blindly retried, even when publication may have begun.
    if descriptor and result >= 0:
        try:
            state.owned_fds.append(result)
        except BaseException as primary:
            # This FD never entered the owned table. Consume its one close
            # here; the outer failure handler must not close/retry its number.
            close_error = None
            if state.failure_errors.failure.primary_error is None:
                state.failure_errors.failure.primary_error = primary
            try:
                os.close(result)
            except BaseException as exc:
                close_error = exc
                try:
                    state.failure_errors.record("unregistered_native_descriptor_close", exc, result)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'unregistered_native_descriptor_close'
                        fallback_slot.error = exc
                        fallback_slot.descriptor = result
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = result
            try:
                state.failure_errors.record("native_descriptor_registration", primary, result)
            except BaseException as aggregation_error:
                state.failure_errors.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'native_descriptor_registration'
                    fallback_slot.error = primary
                    fallback_slot.descriptor = result
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = result
            try:
                _private_fact(state, "native_descriptor_registration_failed", dict(
                    details, syscall=name, result=result, errno=error,
                    error_type=type(primary).__name__,
                    close_error_type=type(close_error).__name__ if close_error is not None else None,
                    detached_mount_absence="NOT_ATTESTED"))
            except BaseException as exc:
                try:
                    state.failure_errors.record("native_descriptor_registration_history", exc, result)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'native_descriptor_registration_history'
                        fallback_slot.error = exc
                        fallback_slot.descriptor = result
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = result
            _raise_broker_failure(state, primary)
    _private_fact(state, "native_syscall_returned", dict(details, syscall=name, result=result, errno=error))
    if descriptor and result >= 0:
        from . import linux_quiescence as q

        scope = q._ReadScope()
        primary = None
        try:
            mount_id = _mount_id(scope, result, state.binding.pid)
            if mount_id in state.issued_ids:
                _deny("native detached GT mount identity was reused in this original history")
            state.issued_ids += (mount_id,)
            _private_fact(state, "detached_mount_created", dict(details, fd=result, mount_id=mount_id))
        except BaseException as exc:
            primary = exc
            raise
        finally:
            # Guard the Python cleanup entry as well as the native close.
            if primary is not None and scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = primary
            try:
                scope.close(primary_error=primary)
            except BaseException as close_dispatch_error:
                if scope.failures.failure.primary_error is None:
                    scope.failures.failure.primary_error = close_dispatch_error
                if close_dispatch_error is not scope.failures.failure:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'close_dispatch_failure'
                        fallback_slot.error = close_dispatch_error
                        fallback_slot.descriptor = None
                # Already consumed descriptor numbers never enter this fallback.
                while scope.owned:
                    remaining_descriptor = scope.owned.pop()
                    try:
                        os.close(remaining_descriptor)
                    except BaseException as remaining_close_error:
                        fallback_slot = next(scope.failures._cursor, None)
                        if fallback_slot is None:
                            scope.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'remaining_descriptor_close'
                            fallback_slot.error = remaining_close_error
                            fallback_slot.descriptor = remaining_descriptor
                scope.failures.failure.secondary_errors = scope.failures._slots
                scope.failures.failure.aggregation_error = scope.failures.aggregation_error
                raise scope.failures.failure from scope.failures.failure.primary_error
    _record(guard, state, "gt_broker_syscall_finished",
            dict(details, syscall=name, result=result, errno=error))
    return result


def _close_fds(state):
    first_error = None
    while state.owned_fds:
        descriptor = state.owned_fds.pop()  # consume before close, never retry
        try:
            os.close(descriptor)
        except BaseException as exc:
            state.failed = True
            if first_error is None:
                first_error = exc
            try:
                state.failure_errors.record("descriptor_close", exc, descriptor)
            except BaseException as aggregation_error:
                state.failure_errors.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'descriptor_close'
                    fallback_slot.error = exc
                    fallback_slot.descriptor = descriptor
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = descriptor
            close_error = exc
        else:
            close_error = None
        # History overflow/publication failure must not prevent attempting
        # every remaining native close exactly once.
        try:
            event = "descriptor_closed" if close_error is None else "descriptor_close_failed"
            payload = {"fd": descriptor}
            if close_error is not None:
                payload["error_type"] = type(close_error).__name__
            _private_fact(state, event, payload)
        except BaseException as exc:
            state.failed = True
            if first_error is None:
                first_error = exc
            try:
                state.failure_errors.record("descriptor_close_history", exc, descriptor)
            except BaseException as aggregation_error:
                state.failure_errors.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'descriptor_close_history'
                    fallback_slot.error = exc
                    fallback_slot.descriptor = descriptor
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = descriptor
    if first_error is not None:
        if state.failure_errors.failure.primary_error is None:
            state.failure_errors.failure.primary_error = first_error
        _raise_broker_failure(state, first_error)


def _revoke_mount(guard, state, view, mount_id, *, cleanup=False):
    from . import linux_quiescence as q

    scope = q._ReadScope()
    primary = None
    try:
        _kernel_identity(scope, state)
        alias = view.mapping.bind_path
        parent = scope.directory(str(PurePosixPath(alias).parent))
        mounts = _mounts(scope, state.binding.pid)
        exact = [mount for mount in mounts if mount.point == alias]
        if not exact and cleanup:
            if any(mount.mount_id == mount_id for mount in mounts):
                _deny("failed GT publication was relocated; cleanup cannot target another path")
            _private_fact(state, "failed_publication_absent", {"alias": alias, "mount_id": mount_id})
            return
        if len(exact) != 1 or exact[0].mount_id != mount_id:
            _deny("GT revoke refuses a missing, hidden or replaced native issuance")
        fd, frame = _file(scope, alias)
        if (frame != view.frame or _mount_id(scope, fd, state.binding.pid) != mount_id
                or exact[0].device != f"{os.major(view.identity.device)}:{os.minor(view.identity.device)}"
                or exact[0].root != view.identity.filesystem_root):
            _deny("GT revoke refuses a different source inode or native mount identity")
        # A held descriptor referring to the mounted file would make a normal
        # unmount busy. Release it before umount; retain the protected parent.
        scope.close_one(fd)
        if q._frame(os.fstat(parent)) != q._frame(os.stat(PurePosixPath(alias).parent, follow_symlinks=False)):
            _deny("GT alias parent changed before the native revoke syscall")
        details = {"alias": alias, "mount_id": mount_id, "flags": _UMOUNT_NOFOLLOW}
        if cleanup:
            _private_fact(state, "cleanup_umount_started", details)
            libc = _libc(guard, state, cleanup=True)
            native_error = OSError("native GT cleanup umount failed")
            native_error.strerror = "native GT cleanup umount failed"
            ctypes.set_errno(0)
            result = libc.umount2(alias.encode(), _UMOUNT_NOFOLLOW)
            error = ctypes.get_errno() if result < 0 else 0
            if result < 0:
                native_error.errno = error
                try:
                    state.failure_errors.record("cleanup_native_umount", native_error)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'cleanup_native_umount'
                        fallback_slot.error = native_error
                        fallback_slot.descriptor = None
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = None
                try:
                    _private_fact(state, "cleanup_umount_finished", dict(details, result=result, errno=error))
                except BaseException as history_error:
                    try:
                        state.failure_errors.record("cleanup_native_umount_history", history_error)
                    except BaseException as aggregation_error:
                        state.failure_errors.aggregation_error = aggregation_error
                        # Inline reserved slots also cover failure to enter record().
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'cleanup_native_umount_history'
                            fallback_slot.error = history_error
                            fallback_slot.descriptor = None
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'record_entry_failure'
                            fallback_slot.error = aggregation_error
                            fallback_slot.descriptor = None
                    _raise_broker_failure(state, native_error)
                raise native_error
            _private_fact(state, "cleanup_umount_finished", dict(details, result=result, errno=error))
        else:
            _call(guard, state, _libc(guard, state), "umount2", (alias.encode(), _UMOUNT_NOFOLLOW), details)
        _clear_mounts(scope, state)
        if cleanup:
            _private_fact(state, "cleanup_mount_absent", {"alias": alias, "mount_id": mount_id})
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Guard the Python cleanup entry as well as the native close.
        if primary is not None and scope.failures.failure.primary_error is None:
            scope.failures.failure.primary_error = primary
        try:
            scope.close(primary_error=primary)
        except BaseException as close_dispatch_error:
            if scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = close_dispatch_error
            if close_dispatch_error is not scope.failures.failure:
                fallback_slot = next(scope.failures._cursor, None)
                if fallback_slot is None:
                    scope.failures.overflowed = True
                else:
                    fallback_slot.operation = 'close_dispatch_failure'
                    fallback_slot.error = close_dispatch_error
                    fallback_slot.descriptor = None
            # Already consumed descriptor numbers never enter this fallback.
            while scope.owned:
                remaining_descriptor = scope.owned.pop()
                try:
                    os.close(remaining_descriptor)
                except BaseException as remaining_close_error:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'remaining_descriptor_close'
                        fallback_slot.error = remaining_close_error
                        fallback_slot.descriptor = remaining_descriptor
            scope.failures.failure.secondary_errors = scope.failures._slots
            scope.failures.failure.aggregation_error = scope.failures.aggregation_error
            raise scope.failures.failure from scope.failures.failure.primary_error


class LinuxNativeGTBroker:
    """Native one-view broker; constructing a lookalike grants no authority.

    grant(scope) owns the durable release and native bind. revoke() accepts no
    receipt: it closes the privately active issuance and records its teardown.
    Returned MountReceipt values are descriptive worker metadata only.
    """

    __slots__ = ("__weakref__",)

    def __init__(self):
        _deny("use the one-shot original startup owner GT broker installer")

    def grant(self, scope: TruthReadScope) -> MountReceipt:
        with _LOCK:
            guard = _broker_guard(self)
            state = _OWNERS.get(guard) if guard is not None else None
            if state is None or state.broker is not self or state.failed or not state.installed:
                _deny("native GT grant has no healthy original installed broker")
            from . import linux_quiescence as q

            read = q._ReadScope()
            view = None
            mount_id = None
            publish_attempted = False
            try:
                _live(guard, state)
                _kernel_identity(read, state)
                phase.require_owned_work(guard, stage_a=False, fit=False)
                _check_ledger(state, _journal(guard, state).records)
                _record_worker_backing(guard, state)
                if state.active is not None or type(scope) is not TruthReadScope:
                    _deny("native GT grant requires one exact scope and no private active grant")
                state.graph.validate_scope(scope)
                scope_id = scope.role_ids[0] if scope.stage == StudyStage.TRAIN_LABELS else scope.outer_id
                view = next((item for item in state.views
                             if item.mapping.phase == scope.stage.value and item.mapping.role_id == scope_id), None)
                if view is None or view.scope_sha256 != scope.participant_scope_attestation:
                    _deny("native GT grant is absent from the original complete registry")
                scope_bytes = _canonical(asdict(scope))
                _clear_mounts(read, state)
                _record(guard, state, "gt_broker_grant_started",
                        {"key": list(view.mapping.key), "scope_sha256": hashlib.sha256(scope_bytes).hexdigest()})
                release = state.binding.ledger.record_gt_release(scope)
                _private_fact(state, "release_fsynced", {"sha256": release})
                if _remember_tail(guard, state, "gt_phase_released") != release:
                    _deny("native GT release differs from the live durable owner event")
                state.binding.ledger.require_gt_release(scope, release)
                # Source content access starts only AFTER the durable barrier.
                source_fd, source_frame = _file(read, view.identity.source_path, contents=True)
                source_mount, source_root = _source_mount(read, source_fd, view.identity.source_path,
                                                         _mounts(read, state.binding.pid), state.binding.pid)
                if (source_frame != view.frame or source_mount != view.source_mount_id
                        or source_root != view.identity.filesystem_root):
                    _deny("GT source drifted from its original pre-worker inode/mount frame")
                digest, size = hashlib.sha256(), 0
                while True:
                    read.checkpoint()
                    block = os.read(source_fd, min(65536, _MAX_GT_BYTES - size + 1))
                    size += len(block)
                    if size > _MAX_GT_BYTES:
                        _deny("released GT source exceeded its bounded read")
                    if not block:
                        break
                    digest.update(block)
                if (size != view.frame[6] or q._frame(os.fstat(source_fd)) != view.frame
                        or digest.hexdigest() != view.mapping.sha256.lower()):
                    _deny("released GT source bytes differ from the original reviewed digest")
                target_fd, _ = _file(read, view.mapping.bind_path)
                covering = [item for item in _mounts(read, state.binding.pid)
                            if PurePosixPath(view.mapping.bind_path).is_relative_to(item.point)]
                if not covering or max(covering, key=lambda item: len(item.point)).optional:
                    _deny("native GT publication requires private alias-parent mount propagation")
                libc = _libc(guard, state)
                details = {"alias": view.mapping.bind_path, "source": view.identity.source_path,
                           "device": view.identity.device, "inode": view.identity.inode,
                           "source_fd": source_fd, "target_fd": target_fd}
                tree = _call(guard, state, libc, "open_tree",
                    (source_fd, b"", _OPEN_TREE_CLONE | os.O_CLOEXEC | _AT_EMPTY_PATH),
                    dict(details, flags=_OPEN_TREE_CLONE | os.O_CLOEXEC | _AT_EMPTY_PATH), descriptor=True)
                mount_id = _mount_id(read, tree, state.binding.pid)
                if mount_id not in state.issued_ids:
                    _deny("native detached GT mount identity is absent from original attempted issuance history")
                _record(guard, state, "gt_broker_mount_identified", dict(details, mount_id=mount_id))
                attributes = _MountAttr(_MOUNT_ATTRIBUTES, 0, _MS_PRIVATE, 0)
                _call(guard, state, libc, "mount_setattr",
                      (tree, b"", _AT_EMPTY_PATH, ctypes.byref(attributes), ctypes.sizeof(attributes)),
                      dict(details, mount_id=mount_id, tree_fd=tree, flags=_AT_EMPTY_PATH,
                           attr_set=_MOUNT_ATTRIBUTES, propagation=_MS_PRIVATE))
                publish_attempted = True
                _call(guard, state, libc, "move_mount", (tree, b"", target_fd, b"", _MOVE_EMPTY),
                      dict(details, mount_id=mount_id, tree_fd=tree, flags=_MOVE_EMPTY))
                mounts = _mounts(read, state.binding.pid)
                exact = [item for item in mounts if item.point == view.mapping.bind_path]
                visible, frame = _file(read, view.mapping.bind_path)
                if (len(exact) != 1 or exact[0].mount_id != mount_id
                        or not {"ro", "nosuid", "nodev", "noexec"} <= exact[0].options
                        or "rw" in exact[0].options or exact[0].optional
                        or exact[0].root != view.identity.filesystem_root or frame != view.frame
                        or _mount_id(read, visible, state.binding.pid) != mount_id):
                    _deny("published GT bind differs from the actual readonly native mount identity")
                receipt = MountReceipt(state.pins[0], view.mapping.logical_path, view.mapping.sha256,
                    view.mapping.role_id, view.mapping.phase, view.mapping.bind_path, mount_id, release)
                # No broker source/tree/target reference survives the grant.
                # Guard the Python cleanup entry as well as the native close.
                if None is not None and state.failure_errors.failure.primary_error is None:
                    state.failure_errors.failure.primary_error = None
                try:
                    _close_fds(state)
                except BaseException as close_dispatch_error:
                    if state.failure_errors.failure.primary_error is None:
                        state.failure_errors.failure.primary_error = close_dispatch_error
                    if close_dispatch_error is not state.failure_errors.failure:
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'close_dispatch_failure'
                            fallback_slot.error = close_dispatch_error
                            fallback_slot.descriptor = None
                    # Already consumed descriptor numbers never enter this fallback.
                    while state.owned_fds:
                        remaining_descriptor = state.owned_fds.pop()
                        try:
                            os.close(remaining_descriptor)
                        except BaseException as remaining_close_error:
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'remaining_descriptor_close'
                                fallback_slot.error = remaining_close_error
                                fallback_slot.descriptor = remaining_descriptor
                    state.failure_errors.failure.secondary_errors = state.failure_errors._slots
                    state.failure_errors.failure.aggregation_error = state.failure_errors.aggregation_error
                    raise state.failure_errors.failure from state.failure_errors.failure.primary_error
                # Guard the Python cleanup entry as well as the native close.
                if None is not None and read.failures.failure.primary_error is None:
                    read.failures.failure.primary_error = None
                try:
                    read.close()
                except BaseException as close_dispatch_error:
                    if read.failures.failure.primary_error is None:
                        read.failures.failure.primary_error = close_dispatch_error
                    if close_dispatch_error is not read.failures.failure:
                        fallback_slot = next(read.failures._cursor, None)
                        if fallback_slot is None:
                            read.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'close_dispatch_failure'
                            fallback_slot.error = close_dispatch_error
                            fallback_slot.descriptor = None
                    # Already consumed descriptor numbers never enter this fallback.
                    while read.owned:
                        remaining_descriptor = read.owned.pop()
                        try:
                            os.close(remaining_descriptor)
                        except BaseException as remaining_close_error:
                            fallback_slot = next(read.failures._cursor, None)
                            if fallback_slot is None:
                                read.failures.overflowed = True
                            else:
                                fallback_slot.operation = 'remaining_descriptor_close'
                                fallback_slot.error = remaining_close_error
                                fallback_slot.descriptor = remaining_descriptor
                    read.failures.failure.secondary_errors = read.failures._slots
                    read.failures.failure.aggregation_error = read.failures.aggregation_error
                    raise read.failures.failure from read.failures.failure.primary_error
                _record(guard, state, "gt_broker_grant_published", {"mount": asdict(receipt)})
                state.active = _Grant(view, scope, scope_bytes, release, mount_id, receipt)
                _live(guard, state)
                return receipt
            except BaseException as exc:
                state.failed = True
                if state.failure_errors.failure.primary_error is None:
                    state.failure_errors.failure.primary_error = exc
                try:
                    state.failure_errors.record("grant_primary", exc)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'grant_primary'
                        fallback_slot.error = exc
                        fallback_slot.descriptor = None
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = None
                # Close all references before normal (never lazy/forced) cleanup.
                # No error list or payload formatting precedes these closes.
                try:
                    # Guard the Python cleanup entry as well as the native close.
                    if None is not None and state.failure_errors.failure.primary_error is None:
                        state.failure_errors.failure.primary_error = None
                    try:
                        _close_fds(state)
                    except BaseException as close_dispatch_error:
                        if state.failure_errors.failure.primary_error is None:
                            state.failure_errors.failure.primary_error = close_dispatch_error
                        if close_dispatch_error is not state.failure_errors.failure:
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'close_dispatch_failure'
                                fallback_slot.error = close_dispatch_error
                                fallback_slot.descriptor = None
                        # Already consumed descriptor numbers never enter this fallback.
                        while state.owned_fds:
                            remaining_descriptor = state.owned_fds.pop()
                            try:
                                os.close(remaining_descriptor)
                            except BaseException as remaining_close_error:
                                fallback_slot = next(state.failure_errors._cursor, None)
                                if fallback_slot is None:
                                    state.failure_errors.overflowed = True
                                else:
                                    fallback_slot.operation = 'remaining_descriptor_close'
                                    fallback_slot.error = remaining_close_error
                                    fallback_slot.descriptor = remaining_descriptor
                        state.failure_errors.failure.secondary_errors = state.failure_errors._slots
                        state.failure_errors.failure.aggregation_error = state.failure_errors.aggregation_error
                        raise state.failure_errors.failure from state.failure_errors.failure.primary_error
                except BaseException as close_error:
                    try:
                        state.failure_errors.record("grant_owned_fd_close", close_error)
                    except BaseException as aggregation_error:
                        state.failure_errors.aggregation_error = aggregation_error
                        # Inline reserved slots also cover failure to enter record().
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'grant_owned_fd_close'
                            fallback_slot.error = close_error
                            fallback_slot.descriptor = None
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'record_entry_failure'
                            fallback_slot.error = aggregation_error
                            fallback_slot.descriptor = None
                try:
                    # Guard the Python cleanup entry as well as the native close.
                    if None is not None and read.failures.failure.primary_error is None:
                        read.failures.failure.primary_error = None
                    try:
                        read.close()
                    except BaseException as close_dispatch_error:
                        if read.failures.failure.primary_error is None:
                            read.failures.failure.primary_error = close_dispatch_error
                        if close_dispatch_error is not read.failures.failure:
                            fallback_slot = next(read.failures._cursor, None)
                            if fallback_slot is None:
                                read.failures.overflowed = True
                            else:
                                fallback_slot.operation = 'close_dispatch_failure'
                                fallback_slot.error = close_dispatch_error
                                fallback_slot.descriptor = None
                        # Already consumed descriptor numbers never enter this fallback.
                        while read.owned:
                            remaining_descriptor = read.owned.pop()
                            try:
                                os.close(remaining_descriptor)
                            except BaseException as remaining_close_error:
                                fallback_slot = next(read.failures._cursor, None)
                                if fallback_slot is None:
                                    read.failures.overflowed = True
                                else:
                                    fallback_slot.operation = 'remaining_descriptor_close'
                                    fallback_slot.error = remaining_close_error
                                    fallback_slot.descriptor = remaining_descriptor
                        read.failures.failure.secondary_errors = read.failures._slots
                        read.failures.failure.aggregation_error = read.failures.aggregation_error
                        raise read.failures.failure from read.failures.failure.primary_error
                except BaseException as close_error:
                    try:
                        state.failure_errors.record("grant_read_scope_close", close_error)
                    except BaseException as aggregation_error:
                        state.failure_errors.aggregation_error = aggregation_error
                        # Inline reserved slots also cover failure to enter record().
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'grant_read_scope_close'
                            fallback_slot.error = close_error
                            fallback_slot.descriptor = None
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'record_entry_failure'
                            fallback_slot.error = aggregation_error
                            fallback_slot.descriptor = None
                if publish_attempted and view is not None and mount_id is not None:
                    try:
                        _revoke_mount(guard, state, view, mount_id, cleanup=True)
                    except BaseException as cleanup_error:
                        try:
                            state.failure_errors.record("grant_mount_cleanup", cleanup_error)
                        except BaseException as aggregation_error:
                            state.failure_errors.aggregation_error = aggregation_error
                            # Inline reserved slots also cover failure to enter record().
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'grant_mount_cleanup'
                                fallback_slot.error = cleanup_error
                                fallback_slot.descriptor = None
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'record_entry_failure'
                                fallback_slot.error = aggregation_error
                                fallback_slot.descriptor = None
                try:
                    failure = {"error_type": type(exc).__name__,
                        "alias": view.mapping.bind_path if view else None,
                        "mount_id": mount_id, "publish_attempted": publish_attempted,
                        "cleanup_attestation": "NOT_ATTESTED"}
                    _private_fact(state, "grant_failed", failure)
                    record_error = _record_failure(guard, state, "gt_broker_grant_failed", failure)
                    if record_error is not None:
                        try:
                            state.failure_errors.record("grant_failure_ledger", record_error)
                        except BaseException as aggregation_error:
                            state.failure_errors.aggregation_error = aggregation_error
                            # Inline reserved slots also cover failure to enter record().
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'grant_failure_ledger'
                                fallback_slot.error = record_error
                                fallback_slot.descriptor = None
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'record_entry_failure'
                                fallback_slot.error = aggregation_error
                                fallback_slot.descriptor = None
                except BaseException as history_error:
                    try:
                        state.failure_errors.record("grant_failure_history", history_error)
                    except BaseException as aggregation_error:
                        state.failure_errors.aggregation_error = aggregation_error
                        # Inline reserved slots also cover failure to enter record().
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'grant_failure_history'
                            fallback_slot.error = history_error
                            fallback_slot.descriptor = None
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'record_entry_failure'
                            fallback_slot.error = aggregation_error
                            fallback_slot.descriptor = None
                _raise_broker_failure(state, exc)

    def revoke(self) -> str:
        with _LOCK:
            guard = _broker_guard(self)
            state = _OWNERS.get(guard) if guard is not None else None
            if state is None or state.broker is not self or state.failed or state.active is None:
                _deny("native GT revoke requires its privately active healthy original issuance")
            try:
                _live(guard, state)
                phase.require_owned_work(guard, stage_a=False, fit=False)
                _check_ledger(state, _journal(guard, state).records)
                active = state.active
                from .linux_phase_publication import _require_closed as _require_phase_copies_closed
                _require_phase_copies_closed(state)
                _record_worker_backing(guard, state)
                if _canonical(asdict(active.scope)) != active.scope_bytes:
                    _deny("original active GT scope changed after native release")
                _require_worker_reference_closure_before_revoke(state)
                _record(guard, state, "gt_broker_worker_references_absent", {
                    "release_sha256": active.release, "mount_id": active.mount_id,
                    "cgroup_path": state.cgroup_path, "controller_pid": state.binding.pid,
                    "individual_worker_exit_history": "NOT_ATTESTED",
                })
                _record(guard, state, "gt_broker_revoke_started",
                        {"release_sha256": active.release, "mount_id": active.mount_id})
                _revoke_mount(guard, state, active.view, active.mount_id)
                # The OS receipt is generated here from the actual syscall
                # history and durable absence event, never supplied by caller.
                os_receipt = _record(guard, state, "gt_broker_revoke_confirmed",
                    {"release_sha256": active.release, "mount_id": active.mount_id,
                     "alias": active.view.mapping.bind_path})
                digest = state.binding.ledger.record_gt_revoke(active.scope, active.release, os_receipt)
                _private_fact(state, "revocation_fsynced", {"sha256": digest, "mount_id": active.mount_id})
                if _remember_tail(guard, state, "gt_phase_view_revoked") != digest:
                    _deny("native GT revoke differs from the actual durable owner event")
                state.active = None
                _live(guard, state)
                return os_receipt
            except BaseException as exc:
                state.failed = True
                if state.failure_errors.failure.primary_error is None:
                    state.failure_errors.failure.primary_error = exc
                try:
                    state.failure_errors.record("revoke_primary", exc)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'revoke_primary'
                        fallback_slot.error = exc
                        fallback_slot.descriptor = None
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = None
                try:
                    failure = {"error_type": type(exc).__name__,
                               "mount_id": state.active.mount_id if state.active else None}
                    record_error = _record_failure(guard, state, "gt_broker_revoke_failed", failure)
                    if record_error is not None:
                        try:
                            state.failure_errors.record("revoke_failure_ledger", record_error)
                        except BaseException as aggregation_error:
                            state.failure_errors.aggregation_error = aggregation_error
                            # Inline reserved slots also cover failure to enter record().
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'revoke_failure_ledger'
                                fallback_slot.error = record_error
                                fallback_slot.descriptor = None
                            fallback_slot = next(state.failure_errors._cursor, None)
                            if fallback_slot is None:
                                state.failure_errors.overflowed = True
                            else:
                                fallback_slot.operation = 'record_entry_failure'
                                fallback_slot.error = aggregation_error
                                fallback_slot.descriptor = None
                except BaseException as history_error:
                    try:
                        state.failure_errors.record("revoke_failure_history", history_error)
                    except BaseException as aggregation_error:
                        state.failure_errors.aggregation_error = aggregation_error
                        # Inline reserved slots also cover failure to enter record().
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'revoke_failure_history'
                            fallback_slot.error = history_error
                            fallback_slot.descriptor = None
                        fallback_slot = next(state.failure_errors._cursor, None)
                        if fallback_slot is None:
                            state.failure_errors.overflowed = True
                        else:
                            fallback_slot.operation = 'record_entry_failure'
                            fallback_slot.error = aggregation_error
                            fallback_slot.descriptor = None
                _raise_broker_failure(state, exc)


def install_original_gt_broker(guard, *, reviewed_manifest_bytes: bytes) -> LinuxNativeGTBroker:
    """Bind once after phase/terminal registration, while startup seq is two.

    The controller assembly must call this before starting ANY role worker and
    route all GT phases through the returned broker. Existing Stage B direct
    ledger releases are deliberately incompatible with this history authority.
    """
    from . import linux_quiescence as q
    from . import terminal_observation as terminal
    from .linux_native_path_map import _get_original_metadata_path_map

    with terminal._LOCK, _LOCK, phase._LOCK:
        _runtime()
        if type(guard) is not BudgetGuard or guard in _OWNERS:
            _deny("original GT broker installation is one-shot for the original guard")
        binding = require_startup_binding(guard)
        if type(binding) is not StartupBinding or type(binding.ledger) is not AppendOnlyLedger:
            _deny("original GT broker needs the live registered startup owner")
        observed, closed = phase._state(guard), terminal._state(guard)
        if (observed.binding is not binding or closed.binding is not binding
                or closed.phase is not observed or observed.accepted or observed.pending is not None
                or binding.ledger._seq != 2 or closed.step != "registered"):
            _deny("original GT broker must install before workers at native startup sequence two")
        pins = _pins()
        if (type(reviewed_manifest_bytes) is not bytes
                or hashlib.sha256(reviewed_manifest_bytes).hexdigest() != pins[0]
                or binding.approval.path_map_sha256 != pins[0]
                or binding.approval.role_graph_sha256 != pins[3]
                or binding.controller_sha256 != pins[5]):
            _deny("GT broker metadata does not match the original approval and frozen pins")
        path_map = _get_original_metadata_path_map(guard, reviewed_manifest_bytes)
        if path_map is None:
            path_map = ExactPathMap.from_bytes(reviewed_manifest_bytes, pins[0])
            if path_map.manifest_schema != _MANIFEST_V1:
                _deny("plain compact v2 cannot install a GT broker without the original early metadata owner")
        if str(path_map.bind_root) != _ALIAS_ROOT or any(item != (
                directory_file_mapping(item.logical_path, item.sha256, role_id=item.role_id, phase=item.phase)
                if path_map.manifest_schema == _MANIFEST_V2 else file_mapping(item.logical_path,
                item.sha256, role_id=item.role_id, phase=item.phase, bind_root=_ALIAS_ROOT))
                for item in path_map._entries.values()):
            _deny("GT broker requires every reviewed deterministic exact alias")
        cgroup_path = json.loads(observed.startup_payload)["controller_receipt"]["parent_cgroup_path"]
        if type(cgroup_path) is not str or q._SERVICE.fullmatch(cgroup_path) is None:
            _deny("GT broker startup has no exact original service cgroup")
        broker = object.__new__(LinuxNativeGTBroker)
        state = _Owner(binding, broker, observed, closed, reviewed_manifest_bytes,
                       pins, uuid.uuid4().hex, cgroup_path)
        _OWNERS[guard], _BROKERS[broker] = state, weakref.ref(guard)
        scope = q._ReadScope()
        try:
            _live(guard, state)
            _libc(guard, state)  # Gate/load/describe only; no mount operation at install.
            state.kernel = _kernel(scope, binding, cgroup_path)
            state.graph, state.views = _registry(scope, state, path_map)
            state.registry_sha256 = hashlib.sha256(_canonical([asdict(view) for view in state.views])).hexdigest()
            _record_worker_backing(guard, state, initial=True)
            _clear_mounts(scope, state)
            for view in state.views:
                fd, _ = _file(scope, view.mapping.bind_path)
                scope.close_one(fd)
            # Guard the Python cleanup entry as well as the native close.
            if None is not None and scope.failures.failure.primary_error is None:
                scope.failures.failure.primary_error = None
            if (os.getpid() != binding.pid or threading.current_thread() is not binding.thread
                    or threading.get_native_id() != binding.pid):
                _deny("GT installation cleanup lost the original PID/thread; descriptors remain UNKNOWN")
            try:
                scope.close()
            except BaseException as close_dispatch_error:
                if scope.failures.failure.primary_error is None:
                    scope.failures.failure.primary_error = close_dispatch_error
                if close_dispatch_error is not scope.failures.failure:
                    fallback_slot = next(scope.failures._cursor, None)
                    if fallback_slot is None:
                        scope.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'close_dispatch_failure'
                        fallback_slot.error = close_dispatch_error
                        fallback_slot.descriptor = None
                # Already consumed descriptor numbers never enter this fallback.
                if (os.getpid() != binding.pid or threading.current_thread() is not binding.thread
                        or threading.get_native_id() != binding.pid):
                    _deny("GT installation fallback cleanup lost the original PID/thread; descriptors remain UNKNOWN")
                while scope.owned:
                    remaining_descriptor = scope.owned.pop()
                    try:
                        os.close(remaining_descriptor)
                    except BaseException as remaining_close_error:
                        fallback_slot = next(scope.failures._cursor, None)
                        if fallback_slot is None:
                            scope.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'remaining_descriptor_close'
                            fallback_slot.error = remaining_close_error
                            fallback_slot.descriptor = remaining_descriptor
                scope.failures.failure.secondary_errors = scope.failures._slots
                scope.failures.failure.aggregation_error = scope.failures.aggregation_error
                raise scope.failures.failure from scope.failures.failure.primary_error
            # Same bounded kernel collector proves startup absence before the
            # first grant: no worker descendants, GT aliases or deleted GT FDs.
            q._collect_kernel_quiescence(binding, cgroup_path, _closure(state))
            _record(guard, state, "gt_broker_registered", {
                "manifest_sha256": pins[0], "gt_registry_sha256": pins[1],
                "protected_registry_sha256": state.registry_sha256,
                "view_count": len(state.views), "kernel": asdict(state.kernel),
                "worker_backing": asdict(state.worker_backing),
                "issued_worker_identities": [asdict(row) for row in state.issued_worker_identities],
            })
            state.installed = True
            return broker
        except BaseException as exc:
            state.failed = True
            if state.failure_errors.failure.primary_error is None:
                state.failure_errors.failure.primary_error = exc
            # Keep the raw read/parse origin, while retaining the SAME-FD
            # report (including each postconsumer/close error) independently.
            report = getattr(exc, "failure_capture", None)
            if (type(report) is NativeFailureCapture and report.failure is exc
                    and report.failure.primary_error is not None
                    and state.failure_errors.failure.primary_error is exc):
                state.failure_errors.failure.primary_error = report.failure.primary_error
            try:
                state.failure_errors.record("installation_primary", exc)
            except BaseException as aggregation_error:
                state.failure_errors.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'installation_primary'
                    fallback_slot.error = exc
                    fallback_slot.descriptor = None
                fallback_slot = next(state.failure_errors._cursor, None)
                if fallback_slot is None:
                    state.failure_errors.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = None
            try:
                # Guard the Python cleanup entry as well as the native close.
                if scope.failures.failure.primary_error is None:
                    scope.failures.failure.primary_error = state.failure_errors.failure.primary_error
                if (os.getpid() != binding.pid or threading.current_thread() is not binding.thread
                        or threading.get_native_id() != binding.pid):
                    _deny("GT failed installation cleanup lost the original PID/thread; descriptors remain UNKNOWN")
                try:
                    scope.close()
                except BaseException as close_dispatch_error:
                    if scope.failures.failure.primary_error is None:
                        scope.failures.failure.primary_error = close_dispatch_error
                    if close_dispatch_error is not scope.failures.failure:
                        fallback_slot = next(scope.failures._cursor, None)
                        if fallback_slot is None:
                            scope.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'close_dispatch_failure'
                            fallback_slot.error = close_dispatch_error
                            fallback_slot.descriptor = None
                    # Already consumed descriptor numbers never enter this fallback.
                    if (os.getpid() != binding.pid or threading.current_thread() is not binding.thread
                            or threading.get_native_id() != binding.pid):
                        _deny("GT failed installation fallback lost the original PID/thread; descriptors remain UNKNOWN")
                    while scope.owned:
                        remaining_descriptor = scope.owned.pop()
                        try:
                            os.close(remaining_descriptor)
                        except BaseException as remaining_close_error:
                            fallback_slot = next(scope.failures._cursor, None)
                            if fallback_slot is None:
                                scope.failures.overflowed = True
                            else:
                                fallback_slot.operation = 'remaining_descriptor_close'
                                fallback_slot.error = remaining_close_error
                                fallback_slot.descriptor = remaining_descriptor
                    scope.failures.failure.secondary_errors = scope.failures._slots
                    scope.failures.failure.aggregation_error = scope.failures.aggregation_error
                    raise scope.failures.failure from scope.failures.failure.primary_error
            except BaseException as close_error:
                try:
                    state.failure_errors.record("installation_read_scope_close", close_error)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'installation_read_scope_close'
                        fallback_slot.error = close_error
                        fallback_slot.descriptor = None
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = None
            try:
                _private_fact(state, "installation_failed", {"error_type": type(exc).__name__})
            except BaseException as history_error:
                try:
                    state.failure_errors.record("installation_failure_history", history_error)
                except BaseException as aggregation_error:
                    state.failure_errors.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'installation_failure_history'
                        fallback_slot.error = history_error
                        fallback_slot.descriptor = None
                    fallback_slot = next(state.failure_errors._cursor, None)
                    if fallback_slot is None:
                        state.failure_errors.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = None
            _raise_broker_failure(state, exc)


def _require_complete_history(state):
    from .linux_phase_publication import _require_closed as _require_phase_copies_closed
    from .linux_phase_runner import _require_transaction_history

    _require_phase_copies_closed(state)
    if state.active is not None or state.owned_fds or len(state.views) != 110:
        _deny("original GT history contains an open or incomplete native issuance")
    # Revoke calls the publisher fence while the transaction is half closed.
    # Require terminal transaction continuity only here, at actual GT freedom.
    _require_transaction_history(state)
    _require_recorded_worker_backing(state)
    if hashlib.sha256(_canonical([asdict(view) for view in state.views])).hexdigest() != state.registry_sha256:
        _deny("original immutable protected GT registry changed")
    previous = "0" * 64
    for fact in state.facts:
        if (type(fact) is not _Fact or fact.previous_sha256 != previous
                or hashlib.sha256(_canonical(dict(event=fact.event, payload=json.loads(fact.payload),
                    monotonic_ns=fact.monotonic_ns, previous_sha256=previous))).hexdigest() != fact.sha256):
            _deny("original complete GT issuance history changed")
        previous = fact.sha256


def require_original_gt_registration(guard) -> bytes:
    """Return the actual pre-worker journal record, never supplied registration.

    This is used by the original expansion owner. Replay consumes these bytes
    as metadata; this private native owner establishes their provenance.
    """
    with _LOCK:
        state = _OWNERS.get(guard) if type(guard) is BudgetGuard else None
        if state is None or not state.installed or state.failed:
            _deny("expansion requires the healthy original installed GT broker registration")
        try:
            _live(guard, state)
            _require_complete_history(state)
            records = _journal(guard, state).records
            _check_ledger(state, records)
            facts = tuple(fact for fact in state.ledger_facts if fact.event == "gt_broker_registered")
            if (len(facts) != 1 or facts[0].seq != 2 or len(records) < 3
                    or records[2]["entry"]["event"] != "gt_broker_registered"
                    or records[2]["sha256"] != facts[0].sha256
                    or _canonical(records[2]["entry"]["payload"]) != facts[0].payload):
                _deny("expansion registration is not the exact original pre-worker journal fact")
            payload = json.loads(facts[0].payload)
            expected = {"manifest_sha256": state.pins[0], "gt_registry_sha256": state.pins[1],
                "protected_registry_sha256": state.registry_sha256, "view_count": 110,
                "kernel": asdict(state.kernel), "worker_backing": asdict(state.worker_backing),
                "invocation_id": state.binding.invocation_id, "controller_run_id": state.run_id}
            if any(_canonical(payload.get(key)) != _canonical(value) for key, value in expected.items()):
                _deny("original registration no longer binds its native registry/kernel/backing identity")
            return _canonical(records[2])
        except BaseException:
            state.failed = True
            raise


def require_original_linux_worker_quiescence(guard):
    """Native production-port hook AFTER worker teardown and broker.revoke().

    Parent integration supplies its ORIGINAL assembly guard. No activity flag,
    controller attribute, receipt, history or boolean is accepted as proof.
    The result identifies that guard's bound controller/run/cgroup and an actual
    sample time. This does not install workers or attest their access policy.
    An active/failed/absent GT broker or unclosed worker descendants refuse.
    """
    from . import linux_quiescence as q
    from . import terminal_observation as terminal
    from .linux_phase_publication import _snapshot as _phase_publication_snapshot

    with terminal._LOCK, _LOCK, phase._LOCK:
        state = _OWNERS.get(guard) if type(guard) is BudgetGuard else None
        if state is None or not state.installed or state.failed:
            _deny("worker quiescence requires the actually installed original native GT broker")
        try:
            _live(guard, state)
            if state.phase.pending is not None:
                _deny("worker quiescence cannot sample an unaccepted pending owner phase")
            _require_complete_history(state)
            _check_ledger(state, _journal(guard, state).records)
            frozen_history = (state.facts, state.ledger_facts, state.issued_ids,
                              state.worker_backing, state.issued_worker_identities,
                              _phase_publication_snapshot(state))
            sample = q._collect_kernel_quiescence(state.binding, state.cgroup_path, _closure(state))
            _live(guard, state)
            _require_recorded_worker_backing(state)
            _check_ledger(state, _journal(guard, state).records)
            if (state.facts, state.ledger_facts, state.issued_ids,
                    state.worker_backing, state.issued_worker_identities,
                    _phase_publication_snapshot(state)) != frozen_history:
                _deny("original GT history changed during worker quiescence sampling")
            return sample
        except BaseException:
            state.failed = True
            raise


@contextmanager
def _locked_original_gt_closure(guard, binding):
    """Private history query; serialize issuance across the entire OS sample."""
    from . import terminal_observation as terminal
    from .linux_phase_publication import _snapshot as _phase_publication_snapshot

    with _LOCK:
        state = _OWNERS.get(guard) if type(guard) is BudgetGuard else None
        if (state is None or not state.installed or state.failed or state.binding is not binding
                or type(state.broker) is not LinuxNativeGTBroker):
            _deny("Linux quiescence requires the actually installed original native GT broker")
        try:
            _live(guard, state, closed=True)
            _require_complete_history(state)
            records = phase._parse(terminal._read_anchor(state.terminal),
                                   state.terminal.terminal_seq, state.terminal.terminal_digest)
            _check_ledger(state, records)
            frozen_history = (state.facts, state.ledger_facts, state.issued_ids,
                              state.worker_backing, state.issued_worker_identities,
                              _phase_publication_snapshot(state))
            yield _closure(state)
            _live(guard, state, closed=True)
            _require_recorded_worker_backing(state)
            if ((state.facts, state.ledger_facts, state.issued_ids,
                    state.worker_backing, state.issued_worker_identities,
                    _phase_publication_snapshot(state)) != frozen_history
                    or state.active is not None):
                _deny("original GT history changed during locked kernel observation")
        except BaseException:
            state.failed = True
            raise
