"""Original early metadata directory owner; SOURCE only, no mount installer.

Only the fixed factory binds the protected retained map to actual kernel
directory observations. Plain maps and descriptive receipts grant no IO.
There is no role publisher, helper load, GT parent reader or terminal resource
here. Every observation owns a temporary scope, closed before registration or
consumer return. Missing original launch/installation facts still refuse at
their existing producers; this module cannot mint those facts.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import PurePosixPath, PureWindowsPath
import re
import stat
import threading
import time

from . import admission_bootstrap as bootstrap, contracts, linux_start_clock, production_metadata as metadata, path_map as mappings
from .budget import AppendOnlyLedger, BudgetGuard
from .linux_production_controller import LinuxProductionController, LinuxProductionOSPorts, _ASSEMBLIES
from .linux_quiescence import _frame, _mounts, _start_ticks
from .native_failure_capture import NativeFailureCapture
from .path_map import ExactPathMap, _MANIFEST_V2, _METADATA, _STUDY_ROLE, _key

_DIRECTORY = "/run/route2-input/metadata"
_GT_METADATA_MAX_BYTES = 4 * 1024 * 1024
_ENTERED = False
_ATTEMPT = None  # Strong failed/unfinished issuance, never a retry slot.
_ORIGINAL = None


@dataclass(frozen=True, slots=True)
class _DirectoryReceiptV2:
    """One shared directory mount fact, never individual file mount receipts."""
    manifest_sha256: str
    directory_frame: tuple
    ancestors: tuple
    mount: object
    kernel: tuple
    schema: str = field(default="route2_directory_mount_receipt_v2", init=False)


@dataclass(slots=True)
class _Resource:
    # Allocate raw/return/error/once-close slots BEFORE each actual acquisition.
    descriptor: object = None
    path: str = ""
    parent: object = None
    name: str = ""
    directory: bool = False
    before: object = None
    info: object = None
    named: object = None
    vfs: object = None
    frame: object = None
    raw: object = None
    chunks: list = field(default_factory=list)
    read_error: object = None
    consumer_raw: object = None
    consumer_chunks: list = field(default_factory=list)
    consumer_result: object = None
    consumer_error: object = None
    mount: object = None
    fdinfo: object = None
    inheritable: object = None
    stream: object = None
    scanner: object = None
    scanner_close: object = None
    scan_entry: object = None
    scan_names: list = field(default_factory=list)
    stream_close_attempted: bool = False
    stream_close_returned: bool = False
    stream_close_raw: object = None
    stream_error: object = None
    scan_close_attempted: bool = False
    scan_close_returned: bool = False
    scan_close_raw: object = None
    scan_error: object = None
    close_attempted: bool = False
    close_returned: bool = False
    close_raw: object = None
    close_error: object = None


@dataclass(slots=True)
class _Owner:
    proof: object
    issued: object
    start_issued: object
    installed: object
    protected_metadata: object
    retained: object
    guard: object
    controller: object
    assembly: object
    supervisor: object
    ports: object
    ledger: object
    limits: object
    start: object
    frozen: object
    pid: int
    thread: object
    tid: int
    map: object = None
    entries: object = None
    original_entries: object = None
    original_fields: object = None
    manifest_bytes: object = None
    manifest_schema: object = None
    manifest_sha256: object = None
    receipts: object = None
    bind_root: object = None
    receipt: object = None
    scope: object = None
    active: bool = False
    installed_ok: bool = False
    failed: bool = False
    closed: bool = False
    primary_report: object = None
    actual_pid: object = None
    actual_thread: object = None
    actual_tid: object = None
    errors: object = field(default_factory=lambda: NativeFailureCapture(1024))


def _capture(errors, operation, error, descriptor=None):
    """Reserved slots only; original raw errors are held before this entry."""
    if error is errors.failure:
        return
    if errors.failure.primary_error is None:
        errors.failure.primary_error = error
    if errors.first_error is None:
        errors.first_error = error
    slot = next(errors._cursor, None)
    if slot is None:
        errors.overflowed = True
        errors.aggregation_error = errors._overflow
    else:
        slot.operation, slot.error, slot.descriptor = operation, error, descriptor


def _identity(owner, *, assembly=False):
    """Original registry/reference continuity; no supplied clock or callback."""
    owner.actual_pid = os.getpid()
    owner.actual_thread = threading.current_thread()
    owner.actual_tid = threading.get_native_id()
    if (owner.pid != owner.actual_pid or owner.thread is not owner.actual_thread
            or owner.tid != owner.actual_tid or owner.tid != owner.pid
            or owner.failed or owner.closed
            or bootstrap._ISSUED_BOOTSTRAP is not owner.issued or owner.issued.proof is not owner.proof
            or owner.issued.pid != owner.pid or owner.issued.thread is not owner.thread
            or linux_start_clock._ISSUED_START is not owner.start_issued
            or owner.start_issued.proof is not owner.start or owner.start_issued.thread is not owner.thread
            or metadata._INSTALLED_METADATA is not owner.installed
            or owner.installed.metadata is not owner.protected_metadata
            or owner.installed.pid != owner.pid or owner.installed.thread is not owner.thread
            or owner.installed.frozen is not owner.frozen
            or owner.installed.proof is not owner.proof or owner.installed.start is not owner.start
            or owner.installed.path_map is not owner.retained or owner.retained.raw is not owner.manifest_bytes
            or owner.proof.start_clock is not owner.start or owner.proof.frozen_admission is not owner.frozen
            or contracts.FROZEN_ADMISSION is not owner.frozen
            or _ASSEMBLIES.get(owner.controller) is not owner.assembly
            or owner.assembly.guard() is not owner.guard or owner.assembly.supervisor() is not owner.supervisor
            or owner.guard.enforcer is not owner.controller or owner.supervisor.ops is not owner.controller
            or owner.assembly.ports is not owner.ports or type(owner.ports) is not LinuxProductionOSPorts
            or owner.guard.ledger is not owner.ledger or owner.assembly.approval_ledger is not owner.ledger
            or owner.guard.limits is not owner.limits or owner.supervisor.limits is not owner.limits
            or owner.assembly.limits is not owner.limits
            or owner.assembly.approval is not owner.installed.metadata.approval
            or owner.supervisor.approval is not owner.assembly.approval
            or owner.guard.invocation_id != owner.start.invocation_id
            or owner.supervisor.invocation_id != owner.start.invocation_id
            or owner.assembly.invocation_id != owner.start.invocation_id
            or owner.guard._invocation_started_ns != owner.start.invocation_started_monotonic_ns
            or owner.assembly.started_ns != owner.start.invocation_started_monotonic_ns
            or owner.assembly.pid != owner.pid or owner.assembly.thread is not owner.thread
            or owner.assembly.failed or owner.assembly.abort_attempted or owner.assembly.failure_preservation_attempted):
        raise PermissionError("early metadata owner lost original process/thread/bootstrap/controller/data references")
    if (owner.installed.role_registry_bytes is not owner.installed.metadata.role_registry_bytes
            or owner.retained.raw is not owner.installed.metadata.path_map_manifest_bytes
            or metadata._canonical(metadata.asdict(owner.start)) != owner.start_issued.proof_bytes
            or metadata._canonical(metadata.asdict(owner.proof)) != owner.installed.bindings_bytes
            or metadata._record_bytes(owner.installed.metadata) != owner.installed.record_bytes):
        raise PermissionError("early metadata original bootstrap or protected records drifted")
    if assembly and (owner.issued.consumed or owner.start_issued.consumed
            or owner.guard._start_entered or owner.guard._started or owner.assembly.attempted
            or owner.ledger._seq != 0):
        raise PermissionError("early metadata factory must precede guard.start and bootstrap consumption")
    if owner.issued.consumed or owner.start_issued.consumed or owner.guard._start_entered:
        from .startup_ownership import require_startup_binding
        binding = require_startup_binding(owner.guard, owner.assembly.approval)
        if (binding is None or binding.controller is not owner.controller or binding.ledger is not owner.ledger
                or binding.owner() is not owner.supervisor):
            raise PermissionError("metadata reads lost their later original native startup binding")
    metadata._deadline(owner.start, owner.limits)


class _Scope:
    def __init__(self, owner):
        self.owner = owner
        self.records = tuple(_Resource() for _ in range(metadata.MAX_METADATA_FDS))
        self.cursor = iter(self.records)
        self.errors = NativeFailureCapture(1024)
        self.directories = {}
        self.total = self.proc_total = 0
        self.deadline = min(time.clock_gettime_ns(time.CLOCK_MONOTONIC) + metadata.MAX_LOAD_NS,
                            metadata._deadline(owner.start, owner.limits))
        self.primary_report = self.after_error = self.capture_error = self.cleanup_identity_error = None
        self.kernel_raw = None
        self.kernel = None
        self.sampled_ns = None

    def checkpoint(self):
        _identity(self.owner)
        self.sampled_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        if self.sampled_ns >= self.deadline:
            raise PermissionError("metadata directory scope exhausted its bounded original absolute deadline")

    def open_at(self, path, *, parent=None, directory=False):
        self.checkpoint()
        record = next(self.cursor, None)
        if record is None:
            raise PermissionError("metadata directory scope exceeded the original 64-FD bound")
        record.path, record.parent, record.name, record.directory = path, parent, PurePosixPath(path).name, directory
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        # The reserved record holds the actual return BEFORE any type/helper.
        record.descriptor = os.open(path if parent is None else record.name, flags, dir_fd=parent)
        if type(record.descriptor) is not int or record.descriptor < 0:
            raise PermissionError("native metadata acquisition did not return an exact descriptor")
        self.checkpoint()  # Actual PID/thread before consuming the returned FD.
        record.info = os.fstat(record.descriptor)
        record.before = record.info
        record.named = os.stat(path if parent is None else record.name, dir_fd=parent, follow_symlinks=False)
        record.inheritable = os.get_inheritable(record.descriptor)
        record.frame = _frame(record.info)
        if (record.frame != _frame(record.named) or record.info.st_uid != 0
                or record.info.st_mode & 0o022
                or not (stat.S_ISDIR(record.info.st_mode) if directory else stat.S_ISREG(record.info.st_mode))
                or record.inheritable):
            raise PermissionError("metadata actual nofollow leaf/ancestor is mutable, inherited or changed")
        return record

    def directory(self, path):
        if "/" not in self.directories:
            self.directories["/"] = self.open_at("/", directory=True)
        parent = self.directories["/"]
        current = PurePosixPath("/")
        for name in PurePosixPath(path).parts[1:]:
            current /= name
            key = str(current)
            if key not in self.directories:
                self.directories[key] = self.open_at(key, parent=parent.descriptor, directory=True)
            parent = self.directories[key]
        return parent

    def names(self, record, maximum):
        self.checkpoint()
        record.scanner = os.scandir(record.descriptor)
        record.scanner_close = record.scanner.close
        self.checkpoint()
        # The iterator and each original entry are strong before inspection.
        for entry in record.scanner:
            record.scan_entry = entry
            self.checkpoint()
            record.scan_names.append(entry.name)
            if len(record.scan_names) > maximum:
                raise PermissionError("metadata/proc directory exceeded its original registered entry set")
        if len(set(record.scan_names)) != len(record.scan_names):
            raise PermissionError("metadata/proc directory enumeration changed")
        return tuple(sorted(record.scan_names))

    def proc_text(self, path):
        parent = self.directory(str(PurePosixPath(path).parent))
        record = self.open_at(path, parent=parent.descriptor)
        count = 0
        while True:
            self.checkpoint()
            request = min(65536, metadata._PROC_MAX_FILE_BYTES - count + 1,
                          metadata._PROC_MAX_TOTAL_BYTES - self.proc_total,
                          metadata.MAX_TOTAL_READ_BYTES - self.total)
            if request <= 0:
                raise PermissionError("metadata/proc reads exhausted original per-file/joint byte limits")
            record.raw = os.read(record.descriptor, request)
            if type(record.raw) is not bytes:
                raise PermissionError("native proc read did not return actual bytes")
            self.total += len(record.raw)
            self.proc_total += len(record.raw)
            count += len(record.raw)
            self.checkpoint()
            if count > metadata._PROC_MAX_FILE_BYTES:
                raise PermissionError("metadata kernel text exceeded its original byte bound")
            if not record.raw:
                break
            record.chunks.append(record.raw)
        self.verify_record(record)
        record.raw = b"".join(record.chunks)
        return record.raw

    def verify_record(self, record):
        self.checkpoint()
        record.info = os.fstat(record.descriptor)
        record.named = os.stat(record.path if record.parent is None else record.name,
                               dir_fd=record.parent, follow_symlinks=False)
        record.inheritable = os.get_inheritable(record.descriptor)
        if (record.frame != _frame(record.info) or record.frame != _frame(record.named)
                or record.inheritable):
            raise PermissionError("original metadata FD or the actual same nofollow leaf changed")

    def readonly(self, record, mounts):
        self.checkpoint()
        record.fdinfo = self.proc_text(f"/proc/{self.owner.pid}/fdinfo/{record.descriptor}")
        ids = [line[7:].strip() for line in record.fdinfo.splitlines() if line.startswith(b"mnt_id:")]
        flags = [line[6:].strip() for line in record.fdinfo.splitlines() if line.startswith(b"flags:")]
        if (len(ids) != 1 or re.fullmatch(rb"[1-9][0-9]*", ids[0]) is None
                or len(flags) != 1 or re.fullmatch(rb"[0-7]+", flags[0]) is None):
            raise PermissionError("metadata FD lacks its actual kernel mount ID/read-only flags")
        actual_flags = int(flags[0], 8)
        required = os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        if (actual_flags & os.O_ACCMODE != os.O_RDONLY or actual_flags & required != required
                or actual_flags & os.O_PATH or (record.directory and not actual_flags & os.O_DIRECTORY)):
            raise PermissionError("metadata actual descriptor flags differ from original readonly acquisition")
        matches = [mount for mount in mounts if mount.mount_id == int(ids[0])]
        covering = [mount for mount in mounts if PurePosixPath(record.path).is_relative_to(mount.point)]
        self.checkpoint()
        record.info = os.fstat(record.descriptor)
        record.vfs = os.fstatvfs(record.descriptor)
        if len(matches) != 1 or not covering:
            raise PermissionError("metadata actual kernel mount is missing or hidden")
        record.mount = matches[0]
        if (record.mount != max(covering, key=lambda mount: (len(PurePosixPath(mount.point).parts), mount.mount_id))
                or record.mount.point != _DIRECTORY or "ro" not in record.mount.options
                or "rw" in record.mount.options or record.mount.optional
                or record.mount.device != f"{os.major(record.info.st_dev)}:{os.minor(record.info.st_dev)}"
                or not record.vfs.f_flag & os.ST_RDONLY):
            raise PermissionError("metadata requires the real private readonly directory mount")
        self.verify_record(record)
        return record.mount

    def kernel_probe(self):
        self.checkpoint()
        pid = self.owner.pid
        proc = self.directory("/proc")
        self.kernel_raw = self.proc_text(f"/proc/{pid}/mountinfo")
        mounts = _mounts(self.kernel_raw)
        proc_mounts = [mount for mount in mounts if mount.point == "/proc"]
        if (len(proc_mounts) != 1 or proc_mounts[0].filesystem != "proc"
                or proc_mounts[0].device != f"{os.major(proc.before.st_dev)}:{os.minor(proc.before.st_dev)}"):
            raise PermissionError("actual metadata kernel observations are not on the original proc filesystem")
        self.kernel_raw = self.proc_text(f"/proc/{pid}/stat")
        ticks = _start_ticks(self.kernel_raw, pid)
        self.kernel_raw = self.proc_text("/proc/sys/kernel/random/boot_id")
        if (ticks != self.owner.start.process_start_ticks
                or self.kernel_raw != (self.owner.start.boot_id + "\n").encode("ascii")):
            raise PermissionError("metadata owner process/boot epoch differs from the original native start")
        tasks = self.directory(f"/proc/{pid}/task")
        if tasks.scanner is None:
            names = self.names(tasks, 2)
        else:
            # A fresh iterator is independently owned by a fresh directory FD.
            tasks = self.open_at(tasks.path, parent=self.directories[f"/proc/{pid}"].descriptor, directory=True)
            names = self.names(tasks, 2)
        if names != (str(pid),):
            raise PermissionError("metadata original controller must remain its single native thread")
        ns = self.directory(f"/proc/{pid}/ns")
        identities = []
        for name in ("time", "mnt"):
            self.checkpoint()
            # Only the two fixed kernel namespace magic links may be followed.
            ns.named = os.stat(name, dir_fd=ns.descriptor, follow_symlinks=False)
            ns.raw = os.readlink(name, dir_fd=ns.descriptor)
            ns.info = os.stat(name, dir_fd=ns.descriptor, follow_symlinks=True)
            if (not stat.S_ISLNK(ns.named.st_mode) or ns.named.st_uid != 0
                    or ns.raw != f"{name}:[{ns.info.st_ino}]"):
                raise PermissionError("metadata namespace observation is not its actual fixed kernel magic link")
            ns.chunks.append((ns.named, ns.raw, ns.info))
            identities.append((ns.info.st_dev, ns.info.st_ino))
        if identities[0] != (self.owner.start.time_namespace_device, self.owner.start.time_namespace_inode):
            raise PermissionError("metadata clock namespace differs from the original native absolute epoch")
        self.kernel = (ticks, self.owner.start.boot_id, *identities)
        self.checkpoint()
        return mounts, self.kernel


@contextmanager
def _owned_scope(owner):
    scope = _Scope(owner)
    # Pin each original resource container BEFORE acquire; public map drift
    # cannot change cleanup targets or replace this original failure buffer.
    records, errors = scope.records, scope.errors
    owner.scope = scope
    try:
        yield scope
    except BaseException as error:
        if scope.primary_report is None:
            scope.primary_report = error
        if owner.primary_report is None:
            owner.primary_report = scope.primary_report
        owner.failed = True
        if errors.failure.primary_error is None:
            errors.failure.primary_error = error
        try:
            _capture(errors, "metadata_scope_primary", error)
        except BaseException as capture_error:
            scope.capture_error = capture_error
            errors.aggregation_error = capture_error
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "metadata_scope_primary", error, None
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "metadata_capture_entry", capture_error, None
    finally:
        # Check actual identity before consuming any original FD number. On a
        # changed process/thread leave originals UNKNOWN, not falsely closed.
        if (os.getpid() != owner.pid or threading.current_thread() is not owner.thread
                or threading.get_native_id() != owner.tid):
            scope.cleanup_identity_error = PermissionError("metadata cleanup lost its actual original PID/thread")
            _capture(errors, "metadata_cleanup_identity", scope.cleanup_identity_error)
        else:
            for resource in reversed(records):
                if resource.scanner is not None and not resource.scan_close_attempted:
                    resource.scan_close_attempted = True
                    try:
                        # Use the captured original object even if later fields
                        # on the public map/consumer holder have been replaced.
                        resource.scan_close_raw = (resource.scanner_close() if resource.scanner_close is not None
                                                   else resource.scanner.close())
                        resource.scan_close_returned = True
                    except BaseException as close_error:
                        resource.scan_error = close_error
                        if errors.failure.primary_error is None:
                            errors.failure.primary_error = close_error
                        if errors.first_error is None:
                            errors.first_error = close_error
                        slot = next(errors._cursor, None)
                        if slot is None:
                            errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "metadata_scandir_close", close_error, resource.descriptor
                if resource.stream is not None and not resource.stream_close_attempted:
                    resource.stream_close_attempted = True
                    try:
                        resource.stream_close_raw = io.FileIO.close(resource.stream)
                        resource.stream_close_returned = True
                    except BaseException as close_error:
                        resource.stream_error = close_error
                        if errors.failure.primary_error is None:
                            errors.failure.primary_error = close_error
                        if errors.first_error is None:
                            errors.first_error = close_error
                        slot = next(errors._cursor, None)
                        if slot is None:
                            errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "metadata_consumer_stream_close", close_error, resource.descriptor
                if resource.descriptor is not None and not resource.close_attempted:
                    if type(resource.descriptor) is not int or resource.descriptor < 0:
                        continue  # Retained unknown acquisition; never guess a FD.
                    resource.close_attempted = True  # Consume BEFORE close; never retry this number.
                    try:
                        resource.close_raw = os.close(resource.descriptor)
                        resource.close_returned = True
                    except BaseException as close_error:
                        resource.close_error = close_error
                        if errors.failure.primary_error is None:
                            errors.failure.primary_error = close_error
                        if errors.first_error is None:
                            errors.first_error = close_error
                        slot = next(errors._cursor, None)
                        if slot is None:
                            errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "metadata_descriptor_close", close_error, resource.descriptor
    if (errors.failure.primary_error is not None or errors.first_error is not None
            or errors.aggregation_error is not None or errors.overflowed):
        owner.failed = True
        if owner.primary_report is None:
            owner.primary_report = errors.failure
        try:
            errors.raise_failure(errors.failure.primary_error)
        except BaseException as report_error:
            if report_error is errors.failure:
                raise
            scope.capture_error = report_error
            errors.aggregation_error = report_error
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = report_error
            raise errors.failure from errors.failure.primary_error
    scope.checkpoint()


def _directory_fact(scope, mappings):
    directory = scope.directory(_DIRECTORY)
    names = scope.names(directory, len(mappings) + 1)
    if names != tuple(sorted(PurePosixPath(item.bind_path).name for item in mappings)):
        raise PermissionError("early metadata directory differs from the original registered metadata-only set")
    mounts, kernel = scope.kernel_probe()
    mount = scope.readonly(directory, mounts)
    ancestors = tuple((path, item.frame) for path, item in scope.directories.items()
                      if path in {"/", "/run", "/run/route2-input", _DIRECTORY})
    for path, before in ancestors:
        scope.verify_record(scope.directories[path])
        if scope.directories[path].frame != before:
            raise PermissionError("metadata protected ancestor frame changed")
    return _DirectoryReceiptV2(scope.owner.frozen.path_map_sha256.lower(), directory.frame, ancestors, mount, kernel)


def _require_original_map_fields(owner, path_map):
    """Reject public holder drift before comparison, truth or mapping methods."""
    if (owner is None or owner.map is not path_map or type(path_map) is not ExactPathMap
            or not owner.installed_ok or owner.failed or owner.closed):
        raise PermissionError("native map requires its healthy original private issuance")
    schema, digest = path_map.manifest_schema, path_map.manifest_sha256
    entries, receipts = path_map._entries, path_map._receipts
    raw, root, closed = path_map._manifest_bytes, path_map.bind_root, path_map._closed
    if (type(schema) is not str or schema is not owner.manifest_schema
            or type(digest) is not str or digest is not owner.manifest_sha256
            or type(entries) is not dict or entries is not owner.entries
            or type(receipts) is not dict or receipts is not owner.receipts
            or type(raw) is not bytes or raw is not owner.manifest_bytes
            or root is not owner.bind_root or type(root) is not type(owner.bind_root)
            or type(closed) is not bool or closed is not False
            or path_map._mount_controller is not None):
        raise PermissionError("metadata public map holder drifted; original cleanup stays owned")
    # Only exact original containers and plain strings reach these operations.
    if (schema != _MANIFEST_V2 or digest != owner.frozen.path_map_sha256.lower()
            or len(receipts) != 0 or len(entries) != len(owner.retained.mappings)
            or len(entries) != len(owner.original_fields)):
        raise PermissionError("native metadata map fields differ from original registration")
    for index, key in enumerate(entries):
        if index % 64 == 0:
            _identity(owner)
        if (type(key) is not tuple or len(key) != 4
                or any(type(value) is not str for value in key)):
            raise PermissionError("native metadata map contains a non-original key type")
    if frozenset(entries) != owner.retained.keys:
        raise PermissionError("native metadata map key set differs from its original retained registration")
    for index, (item, original) in enumerate(zip(owner.retained.mappings, owner.original_fields)):
        if index % 64 == 0:
            _identity(owner)
        if type(item) is not mappings.ExactFileMapping:
            raise PermissionError("native metadata map lost its original concrete mapping type")
        fields = (item.logical_path, item.sha256, item.role_id, item.phase, item.bind_path)
        if any(type(value) is not str for value in fields):
            raise PermissionError("native metadata mapping fields require exact original plain types")
        if fields != original:
            raise PermissionError("native metadata mapping scalars differ from their original independent snapshot")
        derived = mappings.directory_file_mapping(original[0], original[1],
                    role_id=original[2], phase=original[3])
        if fields[4] != derived.bind_path or entries.get(_key(*original[:4])) is not item:
            raise PermissionError("native metadata map entries differ from original registration")
    _identity(owner)


def _require_original_registered(path_map, logical_path, sha256, *, role_id, phase):
    """Original map coverage only; this entry grants no file IO authority."""
    owner = _ORIGINAL
    _require_original_map_fields(owner, path_map)
    if any(type(value) is not str for value in (logical_path, sha256, role_id, phase)):
        raise PermissionError("native metadata identities require exact plain strings")
    if _key(logical_path, sha256, role_id, phase) not in owner.entries:
        raise PermissionError("reviewed exact path map omits a required file identity")


def _require_original_registered_batch(path_map, identities):
    """Two whole-map checks plus ordered immutable-key coverage; never IO."""
    if type(identities) is not tuple:
        raise PermissionError("native registered coverage requires an exact identity tuple")
    owner = _ORIGINAL
    _require_original_map_fields(owner, path_map)
    keys = owner.retained.keys
    if len(identities) > len(keys):
        raise PermissionError("native registered coverage batch exceeds the original retained map size")
    for index, identity in enumerate(identities):
        if index % 64 == 0:
            _identity(owner)
        if (type(identity) is not tuple or len(identity) != 4
                or any(type(value) is not str for value in identity)):
            raise PermissionError("native registered coverage requires exact four-string identity tuples")
        if _key(*identity) not in keys:
            raise PermissionError("reviewed exact path map omits a required file identity")
    _require_original_map_fields(owner, path_map)


def _require_original_metadata_entry(path_map, logical_path, sha256, *, role_id, phase):
    owner = _ORIGINAL
    if (owner is None or owner.map is not path_map or type(path_map) is not ExactPathMap
            or not owner.installed_ok or owner.active or owner.failed or owner.closed):
        raise PermissionError("native metadata IO requires the healthy originally issued early directory owner")
    _require_original_map_fields(owner, path_map)
    if any(type(value) is not str for value in (logical_path, sha256, role_id, phase)):
        raise PermissionError("native metadata identities require exact plain strings")
    if role_id != _STUDY_ROLE or phase != _METADATA:
        raise PermissionError("native parent metadata map drifted or requested role/GT/historical IO")
    key = _key(logical_path, sha256, role_id, phase)
    entry = owner.original_entries.get(key)
    if (entry is None or path_map._entries.get(key) is not entry or entry.key != key
            or PurePosixPath(entry.bind_path).parent != PurePosixPath(_DIRECTORY)
            or entry != metadata.directory_file_mapping(logical_path, sha256, role_id=role_id, phase=phase)):
        raise PermissionError("native metadata request is absent from the original exact registered identity set")
    return entry


def _get_original_metadata_path_map(guard, reviewed_manifest_bytes):
    """Join the broker to the issued map; absence only permits legacy v1."""
    from .startup_ownership import require_startup_binding

    owner = _ORIGINAL
    if owner is None:
        if _ATTEMPT is not None and _ATTEMPT.guard is guard:
            raise PermissionError("original early metadata issuance is unfinished or failed; no fallback")
        return None
    if (type(owner) is not _Owner or type(guard) is not BudgetGuard
            or owner.guard is not guard or type(guard.enforcer) is not LinuxProductionController
            or guard.enforcer is not owner.controller or _ATTEMPT is not owner or _ENTERED is not True
            or owner.installed_ok is not True or owner.active is not False
            or owner.failed is not False or owner.closed is not False
            or guard._start_entered is not True or guard._started is not True
            or mappings._NATIVE_CONTEXT is not owner.map
            or type(reviewed_manifest_bytes) is not bytes
            or reviewed_manifest_bytes is not owner.manifest_bytes):
        raise PermissionError("GT metadata requires the same healthy original guard/map/manifest objects")
    _identity(owner)
    _require_original_map_fields(owner, owner.map)
    binding = require_startup_binding(guard, owner.assembly.approval)
    if (binding is None or binding.controller is not owner.controller
            or binding.ledger is not owner.ledger or binding.limits is not owner.limits
            or binding.owner() is not owner.supervisor or binding.pid != owner.pid
            or binding.thread is not owner.thread or binding.started_ns != owner.start.invocation_started_monotonic_ns
            or owner.ledger._poisoned is not False
            or owner.map._manifest_bytes is not reviewed_manifest_bytes
            or owner.retained.raw is not reviewed_manifest_bytes
            or owner.protected_metadata.path_map_manifest_bytes is not reviewed_manifest_bytes):
        raise PermissionError("GT metadata lost its original startup/ledger/protected manifest binding")
    scope = owner.scope
    if (type(owner.errors) is not NativeFailureCapture or owner.primary_report is not None
            or owner.errors.failure.primary_error is not None or owner.errors.first_error is not None
            or owner.errors.aggregation_error is not None or owner.errors.overflowed
            or type(scope) is not _Scope or scope.owner is not owner
            or type(scope.errors) is not NativeFailureCapture
            or scope.errors.failure.primary_error is not None or scope.errors.first_error is not None
            or scope.errors.aggregation_error is not None or scope.errors.overflowed):
        raise PermissionError("GT metadata requires the healthy original completed metadata scope")
    return owner.map


def _install_original_metadata_path_map(proof, protected_metadata, guard):
    """Fixed one-shot pre-start factory; no caller paths/receipts/IO adapters."""
    global _ENTERED, _ATTEMPT, _ORIGINAL
    with bootstrap._INSTALL_LOCK, linux_start_clock._START_LOCK:
        if type(guard) is not BudgetGuard or type(guard.enforcer) is not LinuxProductionController:
            raise PermissionError("early metadata factory requires the original concrete guard/controller")
        retained = metadata._require_retained_path_map(proof, protected_metadata)
        assembly = _ASSEMBLIES.get(guard.enforcer)
        issued, start_issued, installed = bootstrap._ISSUED_BOOTSTRAP, linux_start_clock._ISSUED_START, metadata._INSTALLED_METADATA
        if (assembly is None or issued is None or start_issued is None
                or type(guard.ledger) is not AppendOnlyLedger or retained.schema != _MANIFEST_V2):
            raise PermissionError("early native metadata requires original retained compact-v2 installation/start owners")
        if _ENTERED:
            raise PermissionError("original early metadata factory has already been consumed")
        owner = _Owner(proof, issued, start_issued, installed, protected_metadata, retained, guard, guard.enforcer,
                       assembly, assembly.supervisor(), assembly.ports, guard.ledger, assembly.limits,
                       proof.start_clock, proof.frozen_admission, os.getpid(), threading.current_thread(),
                       threading.get_native_id(), manifest_bytes=retained.raw)
        _ENTERED = True
        _ATTEMPT = owner  # Strong origin before the first OS acquisition; no failed-factory retry.
    try:
        _identity(owner, assembly=True)
        if os.name != "posix" or os.geteuid() != 0:
            raise PermissionError("native metadata directory owner requires the original Linux root controller")
        # Capture plain immutable scalar values before the public map exists;
        # retained.mappings itself shares its objects with that later holder.
        original_fields = []
        for item in retained.mappings:
            if type(item) is not mappings.ExactFileMapping:
                raise PermissionError("original metadata map requires concrete mappings before snapshot")
            fields = (item.logical_path, item.sha256, item.role_id, item.phase, item.bind_path)
            if any(type(value) is not str for value in fields):
                raise PermissionError("original metadata mapping snapshot requires plain scalar strings")
            original_fields.append(fields)
        owner.original_fields = tuple(original_fields)
        metadata_entries = tuple(item for item in retained.mappings
                                 if item.phase == _METADATA and item.role_id == _STUDY_ROLE)
        if not metadata_entries:
            raise PermissionError("retained original map has no registered early metadata files")
        with _owned_scope(owner) as scope:
            candidate_receipt = _directory_fact(scope, metadata_entries)
            scope.checkpoint()
        # All temporary descriptors and iterator handles closed successfully;
        # no long-lived FD requires a missing terminal-close assembly.
        _identity(owner, assembly=True)
        path_map = ExactPathMap(manifest_sha256=owner.frozen.path_map_sha256.lower(),
            bind_root=retained.bind_root, entries=retained.mappings, receipts=(), manifest_schema=retained.schema)
        owner.map = path_map
        owner.entries = path_map._entries
        owner.original_entries = {item.key: item for item in metadata_entries}
        owner.manifest_schema = path_map.manifest_schema
        owner.manifest_sha256 = path_map.manifest_sha256
        owner.receipts = path_map._receipts
        owner.bind_root = path_map.bind_root
        # Retain the protected original raw bytes; constructor canonicalization
        # verifies them but must not substitute a second JSON decode or authority.
        path_map._manifest_bytes = owner.manifest_bytes
        owner.receipt = candidate_receipt
        _identity(owner, assembly=True)
        owner.installed_ok = True
        _ORIGINAL = owner
        mappings._NATIVE_CONTEXT = path_map
        return path_map
    except BaseException as error:
        owner.primary_report = error
        owner.failed = True
        if owner.errors.failure.primary_error is None:
            owner.errors.failure.primary_error = error
        _capture(owner.errors, "early_metadata_factory", error)
        raise


@contextmanager
def _open_original_metadata_engine(path_map, logical_path, sha256, maximum, *, role_id, phase):
    if type(maximum) is not int or maximum not in {_GT_METADATA_MAX_BYTES, metadata.MAX_REGISTRY_V2_BYTES}:
        raise PermissionError("native metadata engine only accepts its two fixed internal byte bounds")
    entry = _require_original_metadata_entry(path_map, logical_path, sha256, role_id=role_id, phase=phase)
    owner = _ORIGINAL
    owner.active = True
    try:
        with _owned_scope(owner) as scope:
            fact = _directory_fact(scope, tuple(owner.original_entries.values()))
            if fact != owner.receipt:
                raise PermissionError("metadata directory/native epoch changed after original early registration")
            directory = scope.directories[_DIRECTORY]
            resource = scope.open_at(entry.bind_path, parent=directory.descriptor)
            if (resource.before.st_nlink != 1 or resource.before.st_mode & 0o222
                    or not 0 < resource.before.st_size <= maximum):
                raise PermissionError("registered metadata file must be immutable, single-link and bounded")
            mounts, before_kernel = scope.kernel_probe()
            if before_kernel != fact.kernel or scope.readonly(resource, mounts) != fact.mount:
                raise PermissionError("metadata file does not share its original actual directory mount identity")
            digest, offset = hashlib.sha256(), 0
            while offset < resource.before.st_size:
                scope.checkpoint()
                request = min(65536, resource.before.st_size - offset,
                              metadata.MAX_TOTAL_READ_BYTES - scope.total)
                if request <= 0:
                    raise PermissionError("metadata hash exhausted its original joint read budget")
                try:
                    resource.raw = os.pread(resource.descriptor, request, offset)
                except BaseException as read_error:
                    resource.read_error = read_error
                    scope.primary_report = read_error
                    if scope.errors.failure.primary_error is None:
                        scope.errors.failure.primary_error = read_error
                    raise
                scope.checkpoint()
                if type(resource.raw) is not bytes:
                    raise PermissionError("native metadata hash did not return actual bytes")
                scope.total += len(resource.raw)
                offset += len(resource.raw)
                scope.checkpoint()
                if not resource.raw:
                    raise PermissionError("registered metadata ended before its original file frame")
                resource.chunks.append(resource.raw)
                digest.update(resource.raw)
            scope.checkpoint()
            if scope.total >= metadata.MAX_TOTAL_READ_BYTES:
                raise PermissionError("metadata hash has no remaining EOF-probe budget")
            try:
                resource.raw = os.pread(resource.descriptor, 1, offset)
            except BaseException as read_error:
                resource.read_error = read_error
                scope.primary_report = read_error
                if scope.errors.failure.primary_error is None:
                    scope.errors.failure.primary_error = read_error
                raise
            scope.checkpoint()
            if type(resource.raw) is not bytes:
                raise PermissionError("native metadata EOF probe did not return actual bytes")
            scope.total += len(resource.raw)
            if resource.raw or digest.hexdigest() != entry.sha256.lower():
                raise PermissionError("actual registered metadata content differs from its original exact pin")
            scope.verify_record(resource)
            mounts, kernel = scope.kernel_probe()
            if kernel != fact.kernel or scope.readonly(resource, mounts) != fact.mount:
                raise PermissionError("metadata native identity changed between hash and consumption")
            scope.checkpoint()
            resource.stream = io.FileIO(resource.descriptor, mode="rb", closefd=False)
            try:
                yield scope, resource  # Hash and consumer use this SAME readonly FD.
            except BaseException as consumer_error:
                resource.consumer_error = consumer_error
                scope.primary_report = consumer_error
                if scope.errors.failure.primary_error is None:
                    scope.errors.failure.primary_error = consumer_error
                raise
            finally:
                try:
                    scope.verify_record(resource)
                    for path, before in fact.ancestors:
                        scope.verify_record(scope.directories[path])
                    mounts, kernel = scope.kernel_probe()
                    if kernel != fact.kernel or scope.readonly(resource, mounts) != fact.mount:
                        raise PermissionError("metadata native mount/epoch changed during original consumer use")
                    _require_map_after_consumer(owner, path_map, entry)
                except BaseException as after_error:
                    scope.after_error = after_error
                    if scope.errors.failure.primary_error is None:
                        scope.errors.failure.primary_error = after_error
                    try:
                        _capture(scope.errors, "metadata_after_consumer", after_error, resource.descriptor)
                    except BaseException as capture_error:
                        scope.capture_error = capture_error
                        scope.errors.aggregation_error = capture_error
                        slot = next(scope.errors._cursor, None)
                        if slot is None:
                            scope.errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "metadata_after_consumer", after_error, resource.descriptor
                        slot = next(scope.errors._cursor, None)
                        if slot is None:
                            scope.errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "metadata_after_capture_entry", capture_error, resource.descriptor
                        raise
                    raise
    except BaseException as error:
        if owner.primary_report is None:
            owner.primary_report = error
        owner.failed = True
        if owner.errors.failure.primary_error is None:
            owner.errors.failure.primary_error = error
        report = getattr(error, "failure_capture", None)
        if type(report) is NativeFailureCapture and report.failure is error:
            if owner.errors.failure.primary_error is error and report.failure.primary_error is not None:
                owner.errors.failure.primary_error = report.failure.primary_error
        try:
            _capture(owner.errors, "original_metadata_read", error)
        except BaseException as capture_error:
            owner.errors.aggregation_error = capture_error
            slot = next(owner.errors._cursor, None)
            if slot is None:
                owner.errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "metadata_read_capture_entry", capture_error, None
            owner.errors.failure.secondary_errors = owner.errors._slots
            owner.errors.failure.aggregation_error = capture_error
            raise owner.errors.failure from owner.errors.failure.primary_error
        raise
    finally:
        owner.active = False


@contextmanager
def _open_original_metadata(path_map, logical_path, sha256, *, role_id, phase):
    with _open_original_metadata_engine(path_map, logical_path, sha256, metadata.MAX_REGISTRY_V2_BYTES,
                                       role_id=role_id, phase=phase) as (_, resource):
        yield resource.stream


def _read_original_gt_metadata(guard, state, leaf):
    """Only the two original GT metadata leaves; no caller map, pin or cap."""
    from . import linux_gt_history as history
    from .startup_ownership import require_startup_binding

    if type(state) is not history._Owner or history._OWNERS.get(guard) is not state:
        raise PermissionError("GT metadata requires the original private installing broker state")
    path_map = _get_original_metadata_path_map(guard, state.manifest)
    owner = _ORIGINAL
    if path_map is None or owner is None:
        raise PermissionError("GT directory metadata requires the original issued map")
    history._live(guard, state)
    if (require_startup_binding(guard) is not state.binding or state.binding.controller is not owner.controller
            or state.binding.ledger is not owner.ledger or state.binding.owner() is not owner.supervisor
            or state.installed or state.failed or state.active is not None or state.binding.ledger._seq != 2
            or state.phase.accepted or state.phase.pending is not None
            or type(leaf) is not str or leaf not in {"gt-view-registry.json", "gt-role-scopes.json"}):
        raise PermissionError("GT metadata reader lost its same original pre-worker startup state")
    root = PureWindowsPath(owner.frozen.gt_input_root_path)
    digest = (owner.frozen.gt_view_registry_sha256 if leaf == "gt-view-registry.json"
              else owner.frozen.gt_role_graph_projection_sha256)
    index = 0 if leaf == "gt-view-registry.json" else 1
    if state.metadata_scopes[index] is not None or state.metadata_resources[index] is not None:
        raise PermissionError("the original GT metadata leaf has already consumed its broker read slot")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PermissionError("GT metadata contains a repeated JSON key")
            result[key] = value
        return result

    with _open_original_metadata_engine(path_map, str(root / leaf), digest, _GT_METADATA_MAX_BYTES,
                                       role_id=_STUDY_ROLE, phase=_METADATA) as (scope, resource):
        state.metadata_scopes[index] = scope
        state.metadata_resources[index] = resource
        try:
            size = 0
            while True:
                scope.checkpoint()  # Actual original PID/thread BEFORE consuming the SAME FD.
                request = min(65536, _GT_METADATA_MAX_BYTES - size + 1,
                              metadata.MAX_TOTAL_READ_BYTES - scope.total)
                if request <= 0:
                    raise PermissionError("GT metadata exhausted its original joint read budget")
                try:
                    resource.consumer_raw = io.FileIO.read(resource.stream, request)
                except BaseException as read_error:
                    resource.read_error = read_error
                    resource.consumer_error = read_error
                    scope.primary_report = read_error
                    if scope.errors.failure.primary_error is None:
                        scope.errors.failure.primary_error = read_error
                    raise
                scope.checkpoint()
                if type(resource.consumer_raw) is not bytes:
                    raise PermissionError("native GT metadata consumer did not return actual bytes")
                size += len(resource.consumer_raw)
                scope.total += len(resource.consumer_raw)
                if size > _GT_METADATA_MAX_BYTES or scope.total > metadata.MAX_TOTAL_READ_BYTES:
                    raise PermissionError("GT metadata grew beyond its bounded original read")
                if not resource.consumer_raw:
                    break
                resource.consumer_chunks.append(resource.consumer_raw)
            resource.consumer_raw = b"".join(resource.consumer_chunks)
            if size != resource.before.st_size:
                raise PermissionError("GT metadata consumer differs from its original source frame")
            resource.consumer_result = json.loads(resource.consumer_raw, object_pairs_hook=pairs)
            # Check the metadata structure while its original resource and parse
            # outcome are owned; cross-record and GT authority checks remain in the broker.
            value, pins = resource.consumer_result, state.pins
            if leaf == "gt-role-scopes.json":
                names = ("training_label_participants", "training_outer_ids", "inner_evaluation_roles_by_outer",
                         "outer_fit_participants", "outer_role_ids", "outer_evaluation_participants")
                if (type(value) is not dict or set(value) != {"schema", "role_graph_sha256", *names}
                        or value["schema"] != "route2_gt_role_scopes_v1" or value["role_graph_sha256"] != pins[3]
                        or any(type(value[name]) is not dict for name in names)):
                    raise PermissionError("original GT role graph is not the complete pinned metadata projection")
                for name in names:
                    values = value[name]
                    scalar = name in {"training_outer_ids", "outer_role_ids"}
                    for key, entry in values.items():
                        if type(key) is not str or not key:
                            raise PermissionError("pinned GT role graph contains a malformed role identity")
                        if scalar:
                            valid = type(entry) is str and bool(entry)
                        else:
                            valid = (type(entry) is list and bool(entry)
                                     and all(type(item) is str and item for item in entry)
                                     and len(set(entry)) == len(entry))
                        if not valid:
                            raise PermissionError("pinned GT role graph contains malformed role/participant identities")
            elif (type(value) is not dict or set(value) != {"schema", "role_graph_sha256", "gt_role_scopes_path",
                    "gt_role_scopes_sha256", "views", "status"}
                    or value["schema"] != "route2_gt_view_registry_v1" or value["status"] != "PREPARED_UNREVIEWED"
                    or value["role_graph_sha256"] != pins[3]
                    or value["gt_role_scopes_path"] != str(root / "gt-role-scopes.json")
                    or value["gt_role_scopes_sha256"] != pins[2]
                    or type(value["views"]) is not list or len(value["views"]) != 110):
                raise PermissionError("original GT registry is not the complete pinned 100/5/5 projection")
            else:
                keys = {"kind", "phase", "role_id", "outer_id", "role_ids", "participants",
                        "fields", "scope_sha256", "path", "sha256", "release_rule"}
                for record in value["views"]:
                    if (type(record) is not dict or set(record) != keys or record["kind"] != "gt"
                            or record["phase"] not in history._GT_PHASES
                            or any(type(record[name]) is not str for name in keys - {"role_ids", "participants", "fields"})
                            or any(type(record[name]) is not list or any(type(item) is not str for item in record[name])
                                   for name in ("role_ids", "participants", "fields"))):
                        raise PermissionError("original GT registry contains an unapproved record")
            history._live(guard, state)
            if require_startup_binding(guard) is not state.binding:
                raise PermissionError("GT metadata broker startup binding drifted during its consumer")
        except BaseException as consumer_error:
            resource.consumer_error = consumer_error
            scope.primary_report = consumer_error
            if scope.errors.failure.primary_error is None:
                scope.errors.failure.primary_error = consumer_error
            raise
    # _owned_scope has checked the postconsumer frame, all once-closes and its
    # failure buffer before this result can escape the original strong resource.
    return resource.consumer_result


def _require_map_after_consumer(owner, path_map, entry):
    _require_original_map_fields(owner, path_map)
    if owner.entries.get(entry.key) is not entry:
        raise PermissionError("metadata public map holder drifted during consumption; original cleanup stays owned")


def _close_original_path_map(path_map):
    owner = _ORIGINAL
    if owner is None or owner.map is not path_map:
        raise PermissionError("native metadata close has no original private issuance")
    if owner.active:
        raise PermissionError("cannot retire metadata map during an original live consumer scope")
    if owner.closed:
        if owner.failed:
            raise owner.primary_report if owner.primary_report is not None else owner.errors.failure
        return
    owner.closed = True  # Independent of mutable legacy/public close fields.
    path_map._closed = True
    if owner.failed:
        raise owner.primary_report if owner.primary_report is not None else owner.errors.failure
