"""Linux readonly observations authenticated by the original native GT broker.

The syscall collector below checks kernel objects, not controller public flags.
It never reads GT contents, changes cgroups/mounts, or starts a subprocess.
Its only public entry point requires the original terminal/startup owner.

The native linux_gt_history broker must actually install at the live original
startup sequence two and own every GT release/revoke. Missing installation or
incomplete/foreign history refuses before OS sampling. No caller-supplied
list, receipt, boolean or controller attribute is an authority fallback.
An observation is a bounded live sample, not admission or postexit acceptance.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import json
import os
from pathlib import PurePosixPath
import platform
import re
import stat
import threading
import time

from .budget import BudgetGuard
from .native_failure_capture import NativeFailureCapture
from .linux_gt_history import (
    LinuxNativeGTBroker, _GTIdentity, _KernelAnchor, _OriginalRoleClosure,
    _WorkerBackingAnchor, _WorkerIdentity, _MAX_WORKER_IDENTITIES, _locked_original_gt_closure,
)
from .startup_ownership import StartupBinding, require_startup_binding


_PROC_SUPER_MAGIC = 0x9FA0
_CGROUP2_SUPER_MAGIC = 0x63677270
_NSFS_MAGIC = 0x6E736673
_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_TOTAL_BYTES = 16 * 1024 * 1024
_MAX_DIRECTORIES = 128
_MAX_DIRECTORY_ENTRIES = 256
_MAX_MOUNTS = 8192
_MAX_DEPTH = 16
_MAX_FDS = 256
_MAX_MAPS = 8192
_MAX_SAMPLE_NS = 1_000_000_000
# Linux UAPI include/uapi/linux/wait.h: include clone and ordinary children.
# Unsupported installed kernels refuse; there is no proc/children fallback.
_LINUX_WALL = 0x40000000
_SERVICE = re.compile(r"/system\.slice/[A-Za-z0-9_.:@-]+\.service\Z")
_DECIMAL = re.compile(r"[1-9][0-9]*\Z")


@dataclass(frozen=True, slots=True)
class LinuxQuiescenceObservation:
    """Kernel sample only; no capability is issued by constructing this value."""

    controller: object
    invocation_id: str
    pid: int
    cgroup_path: str
    controller_pids: tuple[int, ...]
    worker_pids: tuple[int, ...]
    gt_mount_ids: tuple[int, ...]
    sampled_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class _Mount:
    mount_id: int
    device: str
    root: str
    point: str
    filesystem: str
    options: frozenset[str]
    optional: tuple[str, ...]


def _deny(message: str) -> None:
    raise PermissionError(message)


def _path(value: str) -> str:
    if (type(value) is not str or not value.startswith("/")
            or PurePosixPath(value).as_posix() != value
            or ".." in PurePosixPath(value).parts
            or any(ord(char) < 33 or ord(char) == 127 for char in value)):
        _deny("quiescence requires canonical protected Linux paths")
    return value


def _identity(info) -> tuple[int, ...]:
    return tuple(getattr(info, name) for name in (
        "st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink",
    ))


def _frame(info) -> tuple[int, ...]:
    return _identity(info) + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _protected(info, *, directory: bool) -> None:
    if (info.st_uid != 0 or info.st_mode & 0o022
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        _deny("quiescence kernel path is not protected and root-owned")


def _filesystem(descriptor: int, expected: int) -> None:
    # Linux 64-bit struct statfs is smaller than this buffer; only f_type (the
    # first native long) is inspected. No platform fallback or subprocess.
    if ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(ctypes.c_long) != 8:
        _deny("quiescence requires the Linux 64-bit syscall ABI")
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.fstatfs
    function.argtypes = (ctypes.c_int, ctypes.c_void_p)
    function.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(256)
    if function(descriptor, buffer) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if ctypes.c_long.from_buffer(buffer).value != expected:
        _deny("quiescence path is not on the required kernel filesystem")


class _ReadScope:
    """Bounded actual syscalls; explicit once-only temporary FD ownership."""

    def __init__(self):
        self.owned: list[int] = []
        self.failures = NativeFailureCapture(544)
        self.total = 0
        self.deadline = time.monotonic_ns() + _MAX_SAMPLE_NS

    def checkpoint(self):
        if time.monotonic_ns() > self.deadline:
            _deny("quiescence kernel sample exceeded its elapsed bound")

    def _open(self, path, flags, *, dir_fd=None):
        # Enter this Python frame and reserve list capacity BEFORE os.open.
        # A returned FD is published only by assignment to an existing slot.
        if type(self.owned) is not list or len(self.owned) >= _MAX_FDS:
            _deny("kernel read scope exceeded its exact owned-descriptor bound")
        self.owned.append(None)
        try:
            descriptor = os.open(path, flags, dir_fd=dir_fd)
        except BaseException:
            self.owned.pop()
            raise
        self.owned[-1] = descriptor
        return descriptor

    def close_one(self, descriptor, *, primary_error=None):
        if primary_error is not None and self.failures.failure.primary_error is None:
            self.failures.failure.primary_error = primary_error
        try:
            self.owned.remove(descriptor)  # consume before close; never blind retry
            os.close(descriptor)
        except BaseException as close_error:
            try:
                self.failures.record("descriptor_close", close_error, descriptor)
            except BaseException as aggregation_error:
                self.failures.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'descriptor_close'
                    fallback_slot.error = close_error
                    fallback_slot.descriptor = descriptor
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = descriptor
            if primary_error is None:
                raise
            try:
                self.failures.record("primary", primary_error)
            except BaseException as aggregation_error:
                self.failures.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'primary'
                    fallback_slot.error = primary_error
                    fallback_slot.descriptor = None
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = None
            self.failures.raise_failure(primary_error)

    def close(self, *, primary_error=None):
        if primary_error is not None and self.failures.failure.primary_error is None:
            self.failures.failure.primary_error = primary_error
        first_error = None
        while self.owned:
            descriptor = self.owned.pop()
            try:
                os.close(descriptor)
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
                try:
                    self.failures.record("descriptor_close", exc, descriptor)
                except BaseException as aggregation_error:
                    self.failures.aggregation_error = aggregation_error
                    # Inline reserved slots also cover failure to enter record().
                    fallback_slot = next(self.failures._cursor, None)
                    if fallback_slot is None:
                        self.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'descriptor_close'
                        fallback_slot.error = exc
                        fallback_slot.descriptor = descriptor
                    fallback_slot = next(self.failures._cursor, None)
                    if fallback_slot is None:
                        self.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'record_entry_failure'
                        fallback_slot.error = aggregation_error
                        fallback_slot.descriptor = descriptor
        if first_error is not None:
            primary = first_error if primary_error is None else primary_error
            if self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = primary
            try:
                self.failures.record("primary", primary)
            except BaseException as aggregation_error:
                self.failures.aggregation_error = aggregation_error
                # Inline reserved slots also cover failure to enter record().
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'primary'
                    fallback_slot.error = primary
                    fallback_slot.descriptor = None
                fallback_slot = next(self.failures._cursor, None)
                if fallback_slot is None:
                    self.failures.overflowed = True
                else:
                    fallback_slot.operation = 'record_entry_failure'
                    fallback_slot.error = aggregation_error
                    fallback_slot.descriptor = None
            self.failures.raise_failure(primary)

    def open_at(self, parent, name, *, directory=False):
        self.checkpoint()
        if type(name) is not str or name in {"", ".", ".."} or "/" in name:
            _deny("quiescence relative kernel component is invalid")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        if directory:
            flags |= os.O_DIRECTORY
        descriptor = self._open(name, flags, dir_fd=parent)
        held = os.fstat(descriptor)
        _protected(held, directory=directory)
        if _frame(held) != _frame(os.stat(name, dir_fd=parent, follow_symlinks=False)):
            _deny("quiescence path changed while acquiring its held descriptor")
        return descriptor

    def directory(self, path):
        _path(path)
        descriptor = self._open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                                | os.O_NONBLOCK | os.O_CLOEXEC)
        _protected(os.fstat(descriptor), directory=True)
        for name in PurePosixPath(path).parts[1:]:
            next_descriptor = self.open_at(descriptor, name, directory=True)
            self.close_one(descriptor)
            descriptor = next_descriptor
        return descriptor

    def text(self, parent, name, filesystem):
        descriptor = self.open_at(parent, name)
        primary = None
        try:
            _filesystem(descriptor, filesystem)
            before = _frame(os.fstat(descriptor))
            chunks = []
            count = 0
            while True:
                self.checkpoint()
                chunk = os.read(descriptor, min(65536, _MAX_FILE_BYTES - count + 1))
                count += len(chunk)
                self.total += len(chunk)
                if count > _MAX_FILE_BYTES or self.total > _MAX_TOTAL_BYTES:
                    _deny("quiescence kernel text exceeded its byte bound")
                if not chunk:
                    break
                chunks.append(chunk)
            if (before != _frame(os.fstat(descriptor))
                    or before != _frame(os.stat(name, dir_fd=parent, follow_symlinks=False))):
                _deny("quiescence kernel text identity changed during read")
            return b"".join(chunks)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            # Lock the operation origin before entering one-FD cleanup.
            if primary is not None and self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = primary
            try:
                self.close_one(descriptor, primary_error=primary)
            except BaseException as close_one_dispatch_error:
                if self.failures.failure.primary_error is None:
                    self.failures.failure.primary_error = close_one_dispatch_error
                if close_one_dispatch_error is not self.failures.failure:
                    fallback_slot = next(self.failures._cursor, None)
                    if fallback_slot is None:
                        self.failures.overflowed = True
                    else:
                        fallback_slot.operation = 'close_one_dispatch_failure'
                        fallback_slot.error = close_one_dispatch_error
                        fallback_slot.descriptor = descriptor
                if descriptor in self.owned:
                    self.owned.remove(descriptor)
                    try:
                        os.close(descriptor)
                    except BaseException as remaining_close_error:
                        fallback_slot = next(self.failures._cursor, None)
                        if fallback_slot is None:
                            self.failures.overflowed = True
                        else:
                            fallback_slot.operation = 'close_one_remaining_descriptor'
                            fallback_slot.error = remaining_close_error
                            fallback_slot.descriptor = descriptor
                self.failures.failure.secondary_errors = self.failures._slots
                self.failures.failure.aggregation_error = self.failures.aggregation_error
                raise self.failures.failure from self.failures.failure.primary_error

    def names(self, descriptor, maximum):
        self.checkpoint()
        names = []
        with os.scandir(descriptor) as entries:
            for entry in entries:
                self.checkpoint()
                names.append(entry.name)
                if len(names) > maximum:
                    _deny("quiescence kernel directory exceeded its entry bound")
        if len(set(names)) != len(names):
            _deny("quiescence kernel directory changed during enumeration")
        return tuple(sorted(names))

    def namespace(self, namespace_directory, name):
        # Deliberate exception: only these kernel nsfs magic links are followed.
        before = os.stat(name, dir_fd=namespace_directory, follow_symlinks=False)
        if not stat.S_ISLNK(before.st_mode) or before.st_uid != 0:
            _deny("controller namespace is not a root-owned kernel magic link")
        target = os.readlink(name, dir_fd=namespace_directory)
        descriptor = self._open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC,
                                dir_fd=namespace_directory)
        _filesystem(descriptor, _NSFS_MAGIC)
        held = os.fstat(descriptor)
        if (target != f"{name}:[{held.st_ino}]"
                or _frame(before) != _frame(os.stat(name, dir_fd=namespace_directory, follow_symlinks=False))
                or target != os.readlink(name, dir_fd=namespace_directory)):
            _deny("controller namespace changed while acquiring its original identity")
        return descriptor, (held.st_dev, held.st_ino)


def _unescape(value):
    def replace(match):
        escaped = match.group(0)
        if escaped not in {"\\040", "\\011", "\\012", "\\134"}:
            _deny("quiescence mountinfo contains an unknown escape")
        return chr(int(escaped[1:], 8))
    result = re.sub(r"\\[0-9]{3}", replace, value)
    if "\\" in result:
        _deny("quiescence mountinfo contains an unsupported path character")
    return _path(result)


def _mounts(encoded):
    if not encoded or not encoded.endswith(b"\n") or b"\x00" in encoded:
        _deny("quiescence mountinfo is absent or incomplete")
    result = []
    for line in encoded.decode("utf-8", errors="strict").splitlines():
        fields = line.split(" ")
        if fields.count("-") != 1:
            _deny("quiescence mountinfo has an invalid kernel record")
        split = fields.index("-")
        if (split < 6 or len(fields) != split + 4 or any(not value for value in fields)
                or not _DECIMAL.fullmatch(fields[0]) or not _DECIMAL.fullmatch(fields[1])
                or re.fullmatch(r"[0-9]+:[0-9]+", fields[2]) is None):
            _deny("quiescence mountinfo has an invalid kernel envelope")
        result.append(_Mount(int(fields[0]), fields[2], _unescape(fields[3]),
                             _unescape(fields[4]), fields[split + 1],
                             frozenset(fields[5].split(",")), tuple(fields[6:split])))
        if len(result) > _MAX_MOUNTS:
            _deny("quiescence mount count exceeds its bound")
    if len({item.mount_id for item in result}) != len(result):
        _deny("quiescence mountinfo repeats a mount identity")
    return tuple(result)


def _pids(encoded):
    if encoded and not encoded.endswith(b"\n"):
        _deny("quiescence task list is incomplete")
    lines = encoded.decode("ascii", errors="strict").splitlines()
    if any(_DECIMAL.fullmatch(line) is None for line in lines) or len(lines) > 2:
        _deny("quiescence found an invalid or excess live task list")
    values = tuple(sorted(int(line) for line in lines))
    if len(set(values)) != len(values):
        _deny("quiescence live task list contains duplicates")
    return values


def _membership(scope, proc, cgroup_path):
    if scope.text(proc, "cgroup", _PROC_SUPER_MAGIC) != f"0::{cgroup_path}\n".encode("ascii"):
        _deny("controller no longer belongs to its original unified cgroup")


def _tree(scope, descriptor, relative="", *, held=None, device=None):
    """Hold all child directory FDs across both recursive population scans."""
    if held is None:
        held = {"": descriptor}
    if device is None:
        device = os.fstat(descriptor).st_dev
    depth = len(relative.split("/")) if relative else 0
    if len(held) > _MAX_DIRECTORIES or depth > _MAX_DEPTH:
        _deny("quiescence descendant cgroup tree exceeds its bound")
    before = _frame(os.fstat(descriptor))
    if before[0] != device:
        _deny("quiescence encountered a different or replaced cgroup filesystem")
    _filesystem(descriptor, _CGROUP2_SUPER_MAGIC)
    processes = _pids(scope.text(descriptor, "cgroup.procs", _CGROUP2_SUPER_MAGIC))
    threads = _pids(scope.text(descriptor, "cgroup.threads", _CGROUP2_SUPER_MAGIC))
    if scope.text(descriptor, "cgroup.type", _CGROUP2_SUPER_MAGIC) != b"domain\n":
        _deny("quiescence requires a readable domain cgroup, including descendants")
    children = []
    names = scope.names(descriptor, _MAX_DIRECTORY_ENTRIES)
    for name in names:
        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            _deny("quiescence cgroup tree contains an unexpected symlink")
        if stat.S_ISDIR(info.st_mode):
            children.append(name)
    records = [(relative, before, tuple(children), processes, threads)]
    for name in children:
        key = f"{relative}/{name}" if relative else name
        if key not in held:
            # The root counts as one held directory. Refuse BEFORE acquiring
            # an excess FD; depth counts components, not intervening slashes.
            if len(held) >= _MAX_DIRECTORIES or depth >= _MAX_DEPTH:
                _deny("quiescence descendant cgroup tree exceeds its bound")
            held[key] = scope.open_at(descriptor, name, directory=True)
        child = held[key]
        if _frame(os.fstat(child)) != _frame(os.stat(name, dir_fd=descriptor, follow_symlinks=False)):
            _deny("quiescence descendant cgroup was removed or replaced")
        records.extend(_tree(scope, child, key, held=held, device=device)[0])
    if before != _frame(os.fstat(descriptor)) or names != scope.names(descriptor, _MAX_DIRECTORY_ENTRIES):
        _deny("quiescence cgroup tree changed during recursive observation")
    return tuple(records), held


def _require_only_controller(records, pid):
    if records[0][3:] != ((pid,), (pid,)) or any(item[3] or item[4] for item in records[1:]):
        _deny("quiescence requires exactly the original controller and no descendant workers/threads")


def _require_no_children(scope):
    """Supplement live cgroups with a non-reaping native child observation.

    Zombies are absent from cgroup.procs. Only ECHILD is accepted: None means
    children exist without a reportable exit, and a result means an unreaped
    child. WNOWAIT leaves either case for the original worker owner's wait.
    This does not attest an individual worker's issuance, exit status or sandbox.
    """
    scope.checkpoint()
    try:
        os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOWAIT | os.WNOHANG | _LINUX_WALL)
    except ChildProcessError as exc:
        if exc.errno != errno.ECHILD:
            _deny("native child observation returned an unexpected child error")
    except (AttributeError, OSError, ValueError) as exc:
        raise PermissionError("native non-reaping all-child observation is unavailable") from exc
    else:
        _deny("controller retains a live or unreaped child; original worker cleanup is required")
    scope.checkpoint()


def _gt_mounts(mounts, original):
    identities = {(f"{os.major(item.device)}:{os.minor(item.device)}", item.filesystem_root)
                  for item in original.gt_files}
    for mount in mounts:
        if (mount.mount_id in original.issued_gt_mount_ids
                or any(mount.point == alias or mount.point.startswith(alias + "/")
                       for alias in original.gt_aliases)
                or (mount.device, mount.root) in identities
                or _worker_path(mount.point, original)
                or (mount.device == f"{os.major(original.worker_backing.study_identity[0])}:"
                    f"{os.minor(original.worker_backing.study_identity[0])}"
                    and (mount.root == original.worker_backing.filesystem_root
                         or mount.root.startswith(original.worker_backing.filesystem_root + "/")))):
            _deny("quiescence found a GT/worker alias or a relocated registered GT file mount")


def _worker_path(path, original):
    return any(path == root or path.startswith(root + "/")
               for root in ("/run/route2-worker", original.worker_backing.root))


def _fd_snapshot(scope, directory, original):
    """Inspect target metadata only, including deleted files; never read GT."""
    identities = {(item.device, item.inode) for item in original.gt_files}
    identities |= {(item.device, item.inode) for item in original.issued_worker_identities}
    forbidden_paths = ({item.source_path for item in original.gt_files}
                       | set(original.gt_aliases) | set(original.phase_source_paths))
    directory_identity = _identity(os.fstat(directory))
    result = []
    count = 0
    seen = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            scope.checkpoint()
            count += 1
            if count > _MAX_FDS or re.fullmatch(r"0|[1-9][0-9]*", entry.name) is None:
                _deny("quiescence controller FD table is invalid or exceeds its bound")
            descriptor = int(entry.name)
            if descriptor in seen:
                _deny("controller FD table changed during bounded enumeration")
            seen.add(descriptor)
            before = _frame(os.fstat(descriptor))
            target = os.readlink(entry.name, dir_fd=directory)
            target_path = target[:-10] if target.endswith(" (deleted)") else target
            if ((before[0], before[1]) in identities or target_path in forbidden_paths
                    or any(target_path.startswith(alias + "/") for alias in original.gt_aliases)
                    or _worker_path(target_path, original)
                    or (before[0] == original.worker_backing.study_identity[0]
                        and not (descriptor in original.ledger_fds
                                 and before[:2] == original.ledger_identity
                                 and stat.S_ISREG(before[2])))):
                _deny("controller retains an open GT/worker target, including a deleted reference")
            # proc fd entries are kernel magic links, not user-selected paths.
            if (before != _frame(os.fstat(descriptor))
                    or before != _frame(os.stat(entry.name, dir_fd=directory, follow_symlinks=True))
                    or target != os.readlink(entry.name, dir_fd=directory)):
                _deny("controller FD target was replaced during quiescence observation")
            # scandir duplicates this held directory internally. Its temporary
            # FD is not stable across scans; it is a verified directory, never
            # a registered GT regular file. All other live FDs remain fenced.
            if _identity(os.fstat(descriptor)) != directory_identity:
                result.append((descriptor, before, target))
    return tuple(sorted(result))


def _require_no_gt_mappings(encoded, original):
    """Reject retained file mappings as well as FDs, including unlinked GT."""
    if not encoded or not encoded.endswith(b"\n") or b"\x00" in encoded:
        _deny("controller memory-map metadata is missing or incomplete")
    identities = {(os.major(item.device), os.minor(item.device), item.inode)
                  for item in original.gt_files}
    identities |= {(os.major(item.device), os.minor(item.device), item.inode)
                   for item in original.issued_worker_identities}
    paths = ({item.source_path for item in original.gt_files}
             | set(original.gt_aliases) | set(original.phase_source_paths))
    lines = encoded.decode("utf-8", errors="strict").splitlines()
    if len(lines) > _MAX_MAPS:
        _deny("controller memory-map count exceeds its bounded sample")
    for line in lines:
        fields = line.split(None, 5)
        if (len(fields) < 5 or re.fullmatch(r"[0-9a-f]+-[0-9a-f]+", fields[0]) is None
                or re.fullmatch(r"[r-][w-][x-][ps]", fields[1]) is None
                or re.fullmatch(r"[0-9a-f]+", fields[2]) is None
                or re.fullmatch(r"[0-9a-f]+:[0-9a-f]+", fields[3]) is None
                or re.fullmatch(r"0|[1-9][0-9]*", fields[4]) is None):
            _deny("controller memory-map kernel record is malformed")
        major, minor = (int(value, 16) for value in fields[3].split(":"))
        target = fields[5] if len(fields) == 6 else ""
        path = target[:-10] if target.endswith(" (deleted)") else target
        if ((major, minor, int(fields[4])) in identities or path in paths
                or _worker_path(path, original)
                or (major, minor) == (os.major(original.worker_backing.study_identity[0]),
                                      os.minor(original.worker_backing.study_identity[0]))
                or any(path.startswith(alias + "/") for alias in original.gt_aliases)):
            _deny("controller retains a GT/worker file mapping, including a deleted reference")


def _start_ticks(encoded, pid):
    prefix, separator, rest = encoded.rpartition(b") ")
    fields = rest.split()
    if (not separator or not prefix.startswith(f"{pid} (".encode("ascii"))
            or len(fields) < 20 or not fields[19].isdigit()):
        _deny("controller kernel start identity is malformed")
    return int(fields[19])


def _collect_kernel_quiescence(binding, cgroup_path, original):
    """Actual bounded OS implementation; private caller authenticates history.

    The native mount-history issuer must hold its original issuance lock while
    this runs. A single original controller task plus matching two recursive
    scans supplies a sample, not a guarantee about future/postexit state.
    """
    scope = _ReadScope()
    primary = None
    try:
        # This only validates the shape of authenticated issuer facts. It is
        # NOT their provenance gate, and cannot turn a constructed value into
        # authority. The public source never accepts one from a caller.
        if (type(original) is not _OriginalRoleClosure or original.binding is not binding
                or original.supervisor is not binding.owner()
                or type(original.mount_controller) is not LinuxNativeGTBroker
                or type(original.kernel) is not _KernelAnchor
                or type(original.gt_files) is not tuple or not original.gt_files
                or len(original.gt_files) > _MAX_FDS
                or any(type(item) is not _GTIdentity or not stat.S_ISREG(item.mode)
                       or item.uid != 0 or item.nlink != 1 or item.mode & 0o022
                       or type(item.device) is not int or type(item.inode) is not int
                       or item.device < 0 or item.inode <= 0 for item in original.gt_files)
                or type(original.gt_aliases) is not tuple or not original.gt_aliases
                or len(original.gt_aliases) > _MAX_MOUNTS
                or len(set(original.gt_aliases)) != len(original.gt_aliases)
                or type(original.issued_gt_mount_ids) is not tuple
                or len(original.issued_gt_mount_ids) > _MAX_MOUNTS
                or any(type(value) is not int or value <= 0 for value in original.issued_gt_mount_ids)
                or type(original.controller_run_id) is not str or not original.controller_run_id
                or type(original.worker_backing) is not _WorkerBackingAnchor
                or type(original.worker_backing.study_identity) is not tuple
                or len(original.worker_backing.study_identity) != 5
                or any(type(value) is not int or value < 0 for value in original.worker_backing.study_identity)
                or not stat.S_ISDIR(original.worker_backing.study_identity[2])
                or original.worker_backing.study_identity[3] != 0
                or type(original.worker_backing.study_mount_id) is not int
                or original.worker_backing.study_mount_id <= 0
                or type(original.issued_worker_identities) is not tuple
                or len(original.issued_worker_identities) > _MAX_WORKER_IDENTITIES
                or any(type(item) is not _WorkerIdentity or type(item.device) is not int
                       or type(item.inode) is not int or item.inode <= 0
                       or item.device != original.worker_backing.study_identity[0]
                       or type(item.mode) is not int or item.mode < 0
                       or not (stat.S_ISREG(item.mode) or stat.S_ISDIR(item.mode))
                       for item in original.issued_worker_identities)
                or type(original.ledger_identity) is not tuple or len(original.ledger_identity) != 2
                or any(type(value) is not int or value < 0 for value in original.ledger_identity)
                or type(original.ledger_fds) is not tuple or not original.ledger_fds
                or len(original.ledger_fds) > 3
                or any(type(value) is not int or value < 0 for value in original.ledger_fds)
                or type(original.phase_source_paths) is not tuple
                or original.phase_source_paths not in ((), ("/run/route2-phase-source", "/run/route2-phase-source/inputs"))
                or any(type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None
                       for value in (original.manifest_sha256, original.gt_registry_sha256))):
            _deny("quiescence lacks exact original protected controller/GT kernel facts")
        for item in original.gt_files:
            _path(item.source_path)
            _path(item.filesystem_root)
        backing = original.worker_backing
        if (backing.study_root != _path(str(binding.study_root))
                or backing.root != str(PurePosixPath(backing.study_root) / ".worker")):
            _deny("quiescence worker backing root differs from the original startup owner")
        _path(backing.filesystem_root)
        for item in original.issued_worker_identities:
            _path(item.path)
            if item.path != backing.root and not item.path.startswith(backing.root + "/"):
                _deny("quiescence issued worker identity escapes its original backing root")
        for alias in original.gt_aliases:
            _path(alias)
            if not alias.startswith("/run/route2-input/") and alias not in (
                    "/run/route2-phase-source/inputs/gt-view.jsonl",
                    "/run/route2-phase-source/inputs/control-final-matches.jsonl"):
                _deny("quiescence original GT alias is outside the reviewed role root")
        proc = scope.directory(f"/proc/{binding.pid}")
        _filesystem(proc, _PROC_SUPER_MAGIC)
        ns = scope.open_at(proc, "ns", directory=True)
        _filesystem(ns, _PROC_SUPER_MAGIC)
        namespaces = tuple(scope.namespace(ns, name) for name in ("mnt", "cgroup", "pid"))
        expected_namespaces = (original.kernel.mount_namespace, original.kernel.cgroup_namespace,
                               original.kernel.pid_namespace)
        if tuple(item[1] for item in namespaces) != expected_namespaces:
            _deny("controller left its original mount/cgroup/PID namespace")
        # ProcSubset=pid intentionally hides /proc/sys. The original live
        # startup object/PID/thread and pre-worker PID start ticks + namespace
        # anchors bind this run without accessing a hidden global boot file.
        if _start_ticks(scope.text(proc, "stat", _PROC_SUPER_MAGIC), binding.pid) != original.kernel.start_ticks:
            _deny("controller PID was reused or differs from its original run")
        if threading.get_native_id() != original.kernel.native_tid or original.kernel.native_tid != binding.pid:
            _deny("quiescence requires the original sole controller task")
        _membership(scope, proc, cgroup_path)
        tasks = scope.open_at(proc, "task", directory=True)
        _filesystem(tasks, _PROC_SUPER_MAGIC)
        if scope.names(tasks, 2) != (str(binding.pid),):
            _deny("controller process still has another live thread")
        first_mount_text = scope.text(proc, "mountinfo", _PROC_SUPER_MAGIC)
        mounts = _mounts(first_mount_text)
        cgroup_mounts = [item for item in mounts if item.point == "/sys/fs/cgroup"]
        if (len(cgroup_mounts) != 1 or cgroup_mounts[0].filesystem != "cgroup2"
                or cgroup_mounts[0].root != "/"
                or not {"ro", "nosuid", "nodev", "noexec"} <= cgroup_mounts[0].options
                or cgroup_mounts[0].mount_id != original.kernel.cgroup_mount_id
                or cgroup_mounts[0].device != original.kernel.cgroup_mount_device
                or any(item.point.startswith("/sys/fs/cgroup/") for item in mounts)):
            _deny("original protected unified cgroup mount was hidden, replaced or overmounted")
        _gt_mounts(mounts, original)
        cgroup = scope.directory("/sys/fs/cgroup" + cgroup_path)
        if _identity(os.fstat(cgroup)) != original.kernel.cgroup_directory:
            _deny("original controller cgroup directory was removed or replaced")
        if f"{os.major(os.fstat(cgroup).st_dev)}:{os.minor(os.fstat(cgroup).st_dev)}" != cgroup_mounts[0].device:
            _deny("controller cgroup directory is on a different mount device")
        first_tree, held = _tree(scope, cgroup)
        _require_only_controller(first_tree, binding.pid)
        _require_no_children(scope)
        descriptors = scope.open_at(proc, "fd", directory=True)
        _filesystem(descriptors, _PROC_SUPER_MAGIC)
        first_fds = _fd_snapshot(scope, descriptors, original)
        _require_no_gt_mappings(scope.text(proc, "maps", _PROC_SUPER_MAGIC), original)
        second_tree, _ = _tree(scope, cgroup, held=held)
        _require_only_controller(second_tree, binding.pid)
        _require_no_children(scope)
        if first_tree != second_tree or first_fds != _fd_snapshot(scope, descriptors, original):
            _deny("cgroup population or controller FD identities changed during sampling")
        _require_no_gt_mappings(scope.text(proc, "maps", _PROC_SUPER_MAGIC), original)
        if (first_mount_text != scope.text(proc, "mountinfo", _PROC_SUPER_MAGIC)
                or scope.names(tasks, 2) != (str(binding.pid),)
                or _start_ticks(scope.text(proc, "stat", _PROC_SUPER_MAGIC), binding.pid) != original.kernel.start_ticks):
            _deny("controller mount namespace/task/run identity changed during sampling")
        _membership(scope, proc, cgroup_path)
        visible_cgroup = scope.directory("/sys/fs/cgroup" + cgroup_path)
        visible_proc = scope.directory(f"/proc/{binding.pid}")
        if (_frame(os.fstat(visible_cgroup)) != _frame(os.fstat(cgroup))
                or _identity(os.fstat(visible_proc)) != _identity(os.fstat(proc))):
            _deny("visible controller cgroup/proc directory no longer matches the held kernel object")
        for (descriptor, identity), name in zip(namespaces, ("mnt", "cgroup", "pid")):
            visible = os.stat(name, dir_fd=ns, follow_symlinks=True)
            if identity != (visible.st_dev, visible.st_ino) or identity != (
                    os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino):
                _deny("held original namespace differs from its current kernel identity")
        scope.checkpoint()
        sampled = time.monotonic_ns()
    except BaseException as exc:
        primary = exc
        raise
    finally:
        # Even a close-after-release exception cannot skip another held FD.
        # A cleanup error refuses the sample; no descriptor number is retried.
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
    # Keep the timestamp of the actual kernel sample, but accept only after
    # every owned descriptor has closed within the same elapsed bound.
    scope.checkpoint()
    return LinuxQuiescenceObservation(binding.controller, binding.invocation_id, binding.pid,
                                      cgroup_path, (binding.pid,), (), (), sampled)


def _require_original_role_closure(guard, binding):
    """Return a held native history context, never accept caller history facts."""
    return _locked_original_gt_closure(guard, binding)


def require_linux_terminal_quiescence(guard, binding, cgroup_path) -> LinuxQuiescenceObservation:
    """Original-owner readonly terminal source; missing native broker refuses.

    Public reset cannot recover an already consumed terminal observer. Supplied
    bindings must be the exact registered object. No OS mutation or subprocess
    is ever performed by this observer.
    """
    from . import terminal_observation as terminal

    with terminal._LOCK:
        state = terminal._state(guard)
        try:
            terminal._binding(guard, state)
            if (type(guard) is not BudgetGuard or type(binding) is not StartupBinding
                    or binding is not state.binding or require_startup_binding(guard) is not binding
                    or state.step != "closed" or binding.owner() is not guard._lifecycle_supervisor
                    or binding.controller is not guard.enforcer or os.getpid() != binding.pid
                    or threading.current_thread() is not binding.thread
                    or type(cgroup_path) is not str or _SERVICE.fullmatch(cgroup_path) is None
                    or json.loads(state.startup_payload)["controller_receipt"]["parent_cgroup_path"] != cgroup_path
                    or terminal._accepted(state) != state.accepted
                    or (state.status == "COMPLETE" and len(state.accepted) != 4)):
                _deny("Linux quiescence requires the exact closed original controller/run/phase owner")
            terminal._actually_closed(state)
            if platform.system() != "Linux" or os.name != "posix" or os.geteuid() != 0:
                _deny("Linux controller quiescence requires the real root-owned Linux runtime")
            # Keep original issuance serialized through the kernel sample and
            # the final owner check. A returned snapshot alone is insufficient.
            with _require_original_role_closure(guard, binding) as original:
                sample = _collect_kernel_quiescence(binding, _path(cgroup_path), original)
                terminal._binding(guard, state)
                terminal._actually_closed(state)
                if state.step != "closed" or terminal._accepted(state) != state.accepted:
                    _deny("original terminal/phase owner changed during Linux quiescence sampling")
                return sample
        except BaseException as exc:
            terminal._consume(state, exc)
