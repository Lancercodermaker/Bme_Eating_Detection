"""Private pre-permit kernel observations of the original held native child.

No API accepts an observation, publisher, syscall callback or successful bool.
The launch registry and its registered GT batch select every input. All native
symbol calls use the already gate-approved phase library/dependency closure;
this unit neither loads a library nor supplies that missing installation proof.
Proc magic-link access must actually succeed after the child's UID/dumpable
transition. Root UID is not a substitute for ptrace/LSM permission.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import PurePosixPath
import select
import signal
import socket
import stat
import struct
import threading
import time

from . import linux_quiescence as q
from . import linux_phase_publication as publication

_MAX_BYTES, _MAX_FILE, _MAX_FDS, _MAX_OPENS = 4 << 20, 1 << 20, 64, 512
_MAX_MOUNTS, _MAX_LINES, _MAX_NODES = 2048, 8192, 32768
# Actual Linux v5.15 UAPI: include/uapi/linux/{nsfs,sched,unix_diag}.h,
# include/uapi/asm-generic/socket.h. No syscall number is inferred here.
_NS_GET_NSTYPE = 0xb703
_NAMESPACES = (("mnt", 0x20000), ("ipc", 0x08000000), ("net", 0x40000000),
    ("pid", 0x20000000), ("pid_for_children", 0x20000000), ("uts", 0x04000000),
    ("cgroup", 0x02000000), ("user", 0x10000000),
    ("time", 0x80), ("time_for_children", 0x80))
_NETLINK_SOCK_DIAG, _SOCK_DIAG_BY_FAMILY = 4, 20
_UDIAG_SHOW_PEER, _UNIX_DIAG_PEER, _SO_COOKIE = 4, 2, 57
_OBSERVATIONS = {}


@dataclass(slots=True)
class _FD:
    descriptor: int | None = None
    stream: object | None = None


@dataclass(slots=True)
class _Observed:
    state: object
    pid: int
    thread: object
    started_ns: int
    facts: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    completed_ns: int | None = None
    sealed: bool = False


class _Scope:
    """Cooperative absolute bound, pre-clipped reads, consumed FD slots."""
    def __init__(self, state):
        self.state, self.captures = state, state.captures
        self.deadline = min(state.stop_ns, time.monotonic_ns() + q._MAX_SAMPLE_NS)
        self.slots = tuple(_FD() for _ in range(_MAX_FDS))
        self.total = self.opens = self.nodes = 0
        self.native_error = OSError("original phase observation native call failed")
        # Resolve only through this exact already approved loaded object.
        # Its actual ELF provider/version/constructor closure is a prerequisite
        # of the original installation gate, never inferred by these bindings.
        self.functions = {}
        signatures = {
            "fstatfs": (ctypes.c_int, ctypes.c_void_p),
            "ioctl": (ctypes.c_int, ctypes.c_ulong),
            "getsockopt": (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                           ctypes.POINTER(ctypes.c_uint)),
            "fcntl": (ctypes.c_int, ctypes.c_int),
        }
        if type(state.library) is not ctypes.CDLL:
            raise PermissionError("observer has no original installation-approved native library")
        for name, args in signatures.items():
            function = state.library[name]
            if type(function) is not state.library._FuncPtr:
                raise PermissionError("observer native symbol is not its original library interface")
            function.argtypes, function.restype = args, ctypes.c_int
            if getattr(function, "errcheck", None) is not None:
                raise PermissionError("observer forbids native callback/errcheck implementations")
            self.functions[name] = function

    def checkpoint(self):
        if time.monotonic_ns() >= self.deadline:
            raise TimeoutError("original phase kernel sample reached its absolute stop/sample bound")
        if self.nodes >= _MAX_NODES:
            raise PermissionError("original phase kernel parsing exhausted its node budget")

    def node(self):
        self.checkpoint()
        self.nodes += 1

    def _reserve(self):
        self.checkpoint()
        if self.opens >= _MAX_OPENS:
            raise PermissionError("original phase kernel sample exhausted its acquisition bound")
        for slot in self.slots:
            if slot.descriptor is None and slot.stream is None:
                self.opens += 1
                return slot
        raise PermissionError("original phase kernel sample exhausted its held FD bound")

    def _open(self, path, flags, *, dir_fd=None):
        slot = self._reserve()
        descriptor = os.open(path, flags, dir_fd=dir_fd)
        slot.descriptor = descriptor
        self.checkpoint()
        return descriptor

    def _native(self, name, *args):
        self.checkpoint()
        ctypes.set_errno(0)
        result = self.functions[name](*args)
        number = ctypes.get_errno() if result < 0 else 0
        if result < 0:
            self.native_error.errno = number
            self.native_error.native_operation = name
            raise self.native_error
        self.checkpoint()
        return result

    def filesystem(self, descriptor, expected):
        if ctypes.sizeof(ctypes.c_long) != 8 or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise PermissionError("phase observation requires its reviewed native x86_64 LP64 ABI")
        buffer = (ctypes.c_long * 32)()
        self._native("fstatfs", descriptor, ctypes.byref(buffer))
        if buffer[0] != expected:
            raise PermissionError("phase observation descriptor is on a foreign kernel filesystem")

    def close_one(self, descriptor):
        for slot in self.slots:
            if slot.descriptor == descriptor:
                original, stream = slot.descriptor, slot.stream
                slot.descriptor = slot.stream = None  # consume BEFORE close
                try:
                    if stream is None:
                        os.close(original)
                    else:
                        stream.close()
                except BaseException as error:
                    for buffer in self.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = error
                        if buffer.first_error is None:
                            buffer.first_error = error
                        reserved = next(buffer._cursor, None)
                        if reserved is None:
                            buffer.overflowed = True
                        else:
                            reserved.operation, reserved.error, reserved.descriptor = (
                                "phase_observer_descriptor_close", error, original)
                    raise
                return
        raise PermissionError("phase observation refuses a consumed/foreign close number")

    def close(self):
        # Each raw error is retained inline before any later report/cleanup
        # entry. Failure/allocating a report never prevents the other closes.
        for slot in self.slots:
            original, stream = slot.descriptor, slot.stream
            slot.descriptor = slot.stream = None
            if original is None:
                continue
            try:
                if stream is None:
                    os.close(original)
                else:
                    stream.close()
            except BaseException as error:
                for buffer in self.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = error
                    if buffer.first_error is None:
                        buffer.first_error = error
                    reserved = next(buffer._cursor, None)
                    if reserved is None:
                        buffer.overflowed = True
                    else:
                        reserved.operation, reserved.error, reserved.descriptor = (
                            "phase_observer_descriptor_close", error, original)

    def open_at(self, parent, name, *, directory=False):
        self.node()
        if type(name) is not str or name in ("", ".", "..") or "/" in name:
            raise PermissionError("phase observation accepts only fixed relative kernel components")
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        descriptor = self._open(name, flags, dir_fd=parent)
        held = os.fstat(descriptor)
        if (not (stat.S_ISDIR(held.st_mode) if directory else stat.S_ISREG(held.st_mode))
                or q._frame(held) != q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False))):
            raise PermissionError("phase observation kernel path changed during acquisition")
        return descriptor

    def directory(self, path):
        q._path(path)
        descriptor = self._open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        for name in PurePosixPath(path).parts[1:]:
            following = self.open_at(descriptor, name, directory=True)
            self.close_one(descriptor)
            descriptor = following
        return descriptor

    def text(self, parent, name, filesystem):
        descriptor = self.open_at(parent, name)
        self.filesystem(descriptor, filesystem)
        before, body = q._frame(os.fstat(descriptor)), bytearray()
        while True:
            self.node()
            # A read cannot cross either real remaining byte budget. At an
            # exact bound we reject rather than make an over-budget EOF probe.
            available = min(65536, _MAX_FILE - len(body), _MAX_BYTES - self.total)
            if available <= 0:
                raise PermissionError("phase kernel read cannot prove EOF within its remaining byte budget")
            part = os.read(descriptor, available)
            self.total += len(part)
            if not part:
                break
            body.extend(part)
        if (before != q._frame(os.fstat(descriptor))
                or before != q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False))):
            raise PermissionError("phase kernel text identity changed during the bounded read")
        self.close_one(descriptor)
        self.checkpoint()
        return bytes(body)

    def names(self, descriptor, maximum):
        self.node()
        names = []
        # os.listdir(fd) returns an unbounded list before checking. Scandir
        # consumes entries cooperatively and has its own once-only close.
        iterator_slot = self._reserve()
        iterator = os.scandir(descriptor)
        iterator_slot.stream, iterator_slot.descriptor = iterator, -1
        primary = None
        try:
            for entry in iterator:
                self.node()
                if len(names) >= maximum:
                    raise PermissionError("phase kernel enumeration exhausted its entry budget")
                names.append(entry.name)
        except BaseException as error:
            primary = error
            for buffer in self.captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = error
                if buffer.first_error is None:
                    buffer.first_error = error
                reserved = next(buffer._cursor, None)
                if reserved is None:
                    buffer.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = (
                        "phase_observer_directory_read", error, descriptor)
            raise
        finally:
            iterator_slot.stream = iterator_slot.descriptor = None
            try:
                iterator.close()
            except BaseException as error:
                for buffer in self.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = error
                    if buffer.first_error is None:
                        buffer.first_error = error
                    reserved = next(buffer._cursor, None)
                    if reserved is None:
                        buffer.overflowed = True
                    else:
                        reserved.operation, reserved.error, reserved.descriptor = (
                            "phase_observer_directory_close", error, descriptor)
                if primary is None:
                    raise
        if len(set(names)) != len(names):
            raise PermissionError("phase kernel directory changed during enumeration")
        return tuple(sorted(names))

    def namespace(self, directory, name, expected):
        self.node()
        before = q._frame(os.stat(name, dir_fd=directory, follow_symlinks=False))
        target = os.readlink(name, dir_fd=directory)
        if not stat.S_ISLNK(before[2]):
            raise PermissionError("phase namespace is not a kernel magic link")
        descriptor = self._open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
        self.filesystem(descriptor, q._NSFS_MAGIC)
        held = os.fstat(descriptor)
        kind = self._native("ioctl", descriptor, _NS_GET_NSTYPE)
        label = "pid" if name == "pid_for_children" else "time" if name == "time_for_children" else name
        if (kind != expected or target != f"{label}:[{held.st_ino}]"
                or target != os.readlink(name, dir_fd=directory)
                or before != q._frame(os.stat(name, dir_fd=directory, follow_symlinks=False))):
            raise PermissionError("held phase namespace type/identity changed or differs from actual nsfs")
        return (held.st_dev, held.st_ino, kind)

    def magic(self, parent, name, *, directory=False):
        self.node()
        before = q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False))
        target = os.readlink(name, dir_fd=parent)
        if not stat.S_ISLNK(before[2]):
            raise PermissionError("phase root/FD reference is not the expected kernel magic link")
        flags = os.O_PATH | os.O_CLOEXEC
        if directory:
            flags |= os.O_DIRECTORY
        descriptor = self._open(name, flags, dir_fd=parent)
        frame = q._frame(os.fstat(descriptor))
        if (target != os.readlink(name, dir_fd=parent)
                or before != q._frame(os.stat(name, dir_fd=parent, follow_symlinks=False))
                or frame != q._frame(os.stat(name, dir_fd=parent))):
            raise PermissionError("held phase root/FD magic reference changed during observation")
        return descriptor, frame, target

    def path_fd(self, parent, components, *, directory=False):
        current = parent
        for index, name in enumerate(components):
            self.node()
            final = index == len(components) - 1
            flags = os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW
            if not final or directory:
                flags |= os.O_DIRECTORY
            descriptor = self._open(name, flags, dir_fd=current)
            held = os.fstat(descriptor)
            if (stat.S_ISLNK(held.st_mode)
                    or q._frame(held) != q._frame(os.stat(name, dir_fd=current, follow_symlinks=False))):
                raise PermissionError("phase root descendant changed or is an unsupported symlink")
            if not final or directory:
                _worker_bits(q._frame(held), execute=True)
            if current != parent:
                self.close_one(current)
            current = descriptor
        return current

    def lines(self, encoded):
        if not encoded or not encoded.endswith(b"\n") or b"\x00" in encoded:
            raise PermissionError("phase kernel text is absent/incomplete or contains NUL")
        count = cursor = 0
        while cursor < len(encoded):
            self.node()
            count += 1
            end = encoded.find(b"\n", cursor, min(len(encoded), cursor + 65537))
            if count > _MAX_LINES or end < 0:
                raise PermissionError("phase kernel parser exceeded its line bound")
            line = encoded[cursor:end]
            cursor = end + 1
            yield line

    def mounts(self, encoded):
        result = []
        for line in self.lines(encoded):
            self.node()
            if len(result) >= _MAX_MOUNTS:
                raise PermissionError("phase kernel mount parser exhausted its entry bound")
            result.append(q._mounts(line + b"\n")[0])
        if len({item.mount_id for item in result}) != len(result):
            raise PermissionError("phase kernel mount observation repeats an identity")
        return tuple(result)

    def option(self, descriptor, name, size):
        buffer, length = ctypes.create_string_buffer(size), ctypes.c_uint(size)
        self._native("getsockopt", descriptor, socket.SOL_SOCKET, name,
                     ctypes.byref(buffer), ctypes.byref(length))
        if length.value != size:
            raise PermissionError("original socket kernel option has an unsupported ABI size")
        return bytes(buffer)

    def diag_socket(self):
        slot = self._reserve()
        stream = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW | socket.SOCK_CLOEXEC | socket.SOCK_NONBLOCK,
                               _NETLINK_SOCK_DIAG)
        slot.stream = stream
        slot.descriptor = stream.fileno()
        stream.bind((0, 0))
        self.checkpoint()
        return stream


def _fields(scope, encoded):
    result = {}
    for line in scope.lines(encoded):
        key, separator, value = line.partition(b":")
        if not separator or key in result or len(key) > 64:
            raise PermissionError("phase kernel key/value record is malformed or duplicated")
        result[key] = value.strip()
    return result


def _number(value, *, base=10):
    if (not value or len(value) > 32 or any(byte not in (b"01234567" if base == 8 else b"0123456789")
                                          for byte in value)):
        raise PermissionError("phase kernel unsigned numeric record is malformed")
    return int(value, base)


def _process(scope, encoded, pid):
    prefix, separator, rest = encoded.rpartition(b") ")
    fields = rest.split()
    if (not separator or not prefix.startswith(f"{pid} (".encode("ascii"))
            or not 20 <= len(fields) <= 64 or fields[0] in (b"Z", b"X", b"x")):
        raise PermissionError("phase kernel process identity is absent/exited or malformed")
    scope.checkpoint()
    ppid, ticks = _number(fields[1]), _number(fields[19])
    if ticks <= 0:
        raise PermissionError("phase process start identity is unavailable; zero is not a ptrace proof")
    return ppid, ticks


def _fdinfo(scope, directory, descriptor):
    encoded = scope.text(directory, str(descriptor), q._PROC_SUPER_MAGIC)
    fields = _fields(scope, encoded)
    if not {b"flags", b"mnt_id", b"ino"} <= set(fields):
        raise PermissionError("phase kernel FD lacks actual flags/mount/inode metadata")
    return encoded, fields, _number(fields[b"flags"], base=8), _number(fields[b"mnt_id"])


def _mount_record(mount):
    return dict(mount_id=mount.mount_id, device=mount.device, filesystem_root=mount.root,
                point=mount.point, filesystem=mount.filesystem, options=sorted(mount.options),
                optional=list(mount.optional))


def _worker_bits(frame, *, read=False, execute=False):
    # The child has all four UID/GID values 65534, no supplementary groups and
    # no DAC capabilities. These mode bits are necessary, not proof that an
    # ACL/LSM permits a later child open/exec. That is installation's boundary.
    shift = 6 if frame[3] == 65534 else 3 if frame[4] == 65534 else 0
    bits = frame[2] >> shift & 7
    required = (4 if read else 0) | (1 if execute else 0)
    if bits & required != required:
        raise PermissionError("actual phase object lacks worker UID/GID65534 read/traverse/exec DAC mode bits")
    return bits


def _exact_mount(mounts, point, mount_id, frame, root=None, *, data=False):
    rows = [mount for mount in mounts if mount.point == point]
    if (len(rows) != 1 or rows[0].mount_id != mount_id
            or rows[0].device != f"{os.major(frame[0])}:{os.minor(frame[0])}"
            or (root is not None and rows[0].root != root)
            or not ({"ro", "nosuid", "nodev", "noexec"} if data else {"ro", "nosuid", "nodev"}) <= rows[0].options
            or "rw" in rows[0].options or rows[0].optional):
        raise PermissionError("phase held mount is hidden/replaced/writable or escapes its original source")
    return rows[0]


def _diag(scope, stream, inode, cookie, sequence, observed):
    """Targeted original socket lookup, never a dump or supplied peer claim."""
    scope.node()
    port, groups = stream.getsockname()
    if port <= 0 or groups:
        raise PermissionError("private UNIX diagnostic reader has a foreign kernel port/group")
    request = struct.pack("=IHHII", 40, _SOCK_DIAG_BY_FAMILY, 1, sequence, port) + struct.pack(
        "=BBHIIIII", socket.AF_UNIX, 0, 0, 0xffffffff, inode, _UDIAG_SHOW_PEER,
        cookie & 0xffffffff, cookie >> 32)
    # Precharge the entire bounded kernel datagram before asking for it. This
    # permits no read beyond remaining total bytes, even on a truncated reply.
    maximum = 4096
    if _MAX_BYTES - scope.total < maximum:
        raise PermissionError("UNIX diagnostic response has no remaining precharged byte budget")
    scope.total += maximum
    if stream.sendto(request, (0, 0)) != len(request):
        raise OSError("original UNIX diagnostic request was not completely sent")
    poller = select.poll()
    poller.register(stream.fileno(), select.POLLIN)
    while True:
        scope.checkpoint()
        remaining = scope.deadline - time.monotonic_ns()
        events = poller.poll(min(50, max(1, (remaining + 999999) // 1000000)))
        scope.checkpoint()
        if not events:
            continue
        if any(fd != stream.fileno() or flags & (select.POLLERR | select.POLLNVAL) for fd, flags in events):
            raise OSError("original UNIX diagnostic kernel channel poll failed")
        try:
            body, ancillary, flags, sender = stream.recvmsg(maximum, 0)
        except BlockingIOError:
            continue
        observed.raw[f"unix_diag_{sequence}"] = body  # raw reply before parsing
        if ancillary or flags or sender != (0, 0) or len(body) < 16:
            raise PermissionError("UNIX diagnostic reply is truncated/foreign or has unsupported ancillary data")
        length, kind, nl_flags, seq, destination = struct.unpack_from("=IHHII", body)
        if (seq != sequence or destination != port or nl_flags or length != len(body)
                or length & 3 or length < 20):
            raise PermissionError("UNIX diagnostic reply is multipart/unmatched or has an unsupported kernel envelope")
        if kind == 2:
            number, = struct.unpack_from("=i", body, 16)
            if number >= 0 or length < 36 or body[20:36] != request[:16]:
                raise PermissionError("UNIX diagnostic kernel error has an unsupported original-request ABI")
            raise OSError(-number, "original UNIX diagnostic kernel query refused")
        if kind != _SOCK_DIAG_BY_FAMILY or length < 32:
            raise PermissionError("UNIX diagnostic kernel reply is not its targeted socket observation")
        family, sock_type, state, pad, actual, low, high = struct.unpack_from("=BBBBIII", body, 16)
        actual_cookie = low | high << 32
        if (family != socket.AF_UNIX or sock_type != socket.SOCK_STREAM or state != 1
                or pad or actual != inode or (cookie != 0xffffffffffffffff and actual_cookie != cookie)):
            raise PermissionError("UNIX diagnostic target/cookie/type/live state changed")
        cursor, attributes = 32, {}
        while cursor < length:
            scope.node()
            if length - cursor < 4:
                raise PermissionError("UNIX diagnostic attribute is incomplete")
            size, attribute = struct.unpack_from("=HH", body, cursor)
            aligned = (size + 3) & ~3
            if size < 4 or cursor + aligned > length or attribute in attributes or attribute & 0xc000:
                raise PermissionError("UNIX diagnostic attribute is repeated/flagged or exceeds its original reply")
            value = body[cursor + 4:cursor + size]
            if any(body[cursor + size:cursor + aligned]):
                raise PermissionError("UNIX diagnostic kernel attribute has nonzero alignment padding")
            attributes[attribute] = value
            cursor += aligned
        # Current targeted peer-only requests may include UNIX_DIAG_SHUTDOWN
        # (6), which is a real one-byte kernel observation. No pathname/VFS,
        # listener/icon or undocumented attribute is accepted as an IPC route.
        if (not {_UNIX_DIAG_PEER} <= set(attributes) or set(attributes) - {_UNIX_DIAG_PEER, 6}
                or len(attributes[_UNIX_DIAG_PEER]) != 4
                or (6 in attributes and attributes[6] != b"\x00")):
            raise PermissionError("UNIX diagnostic peer topology/shutdown ABI is unavailable or unsupported")
        peer, = struct.unpack("=I", attributes[_UNIX_DIAG_PEER])
        if peer <= 0 or peer == inode:
            raise PermissionError("original UNIX diagnostic channel lacks a distinct live peer")
        return dict(inode=inode, cookie=actual_cookie, peer_inode=peer,
                    socket_type=sock_type, socket_state=state, kernel_port=port, sequence=sequence)


def _sample(scope, state, observed):
    publisher, batch = publication._phase_launch_owner(state)
    owner, binding = publisher.owner, state.binding
    parent, child = scope.directory(f"/proc/{binding.pid}"), scope.directory(f"/proc/{state.raw.pid}")
    scope.filesystem(parent, q._PROC_SUPER_MAGIC)
    scope.filesystem(child, q._PROC_SUPER_MAGIC)
    parent_info, child_info = scope.open_at(parent, "fdinfo", directory=True), scope.open_at(child, "fdinfo", directory=True)
    parent_fds, child_fds = scope.open_at(parent, "fd", directory=True), scope.open_at(child, "fd", directory=True)
    encoded, pid_fields, pid_flags, _ = _fdinfo(scope, parent_info, state.raw.pidfd)
    observed.raw["original_pidfd_fdinfo"] = encoded
    if (os.readlink(str(state.raw.pidfd), dir_fd=parent_fds) != "anon_inode:[pidfd]"
            or pid_fields.get(b"Pid") != str(state.raw.pid).encode("ascii")
            or not pid_flags & os.O_CLOEXEC):
        raise PermissionError("held atomic pidfd does not identify its original live child")
    before_wait = os.waitid(os.P_PIDFD, state.raw.pidfd, os.WEXITED | os.WNOWAIT | os.WNOHANG)
    state.prepermit_wait = before_wait  # raw result BEFORE a check/report
    state.waitable_parent = True
    if before_wait is not None:
        raise ChildProcessError("original child exited before pre-permit observation")
    parent_stat, child_stat = scope.text(parent, "stat", q._PROC_SUPER_MAGIC), scope.text(child, "stat", q._PROC_SUPER_MAGIC)
    observed.raw["parent_stat"], observed.raw["child_stat"] = parent_stat, child_stat
    _, parent_ticks = _process(scope, parent_stat, binding.pid)
    ppid, child_ticks = _process(scope, child_stat, state.raw.pid)
    if parent_ticks != owner.kernel.start_ticks or ppid != binding.pid:
        raise PermissionError("child process start/PPid differs from the original native parent")
    parent_status, child_status = scope.text(parent, "status", q._PROC_SUPER_MAGIC), scope.text(child, "status", q._PROC_SUPER_MAGIC)
    observed.raw["parent_status"], observed.raw["child_status"] = parent_status, child_status
    parent_fields, child_fields = _fields(scope, parent_status), _fields(scope, child_status)
    if (child_fields.get(b"Uid", b"").split() != [b"65534"] * 4
            or child_fields.get(b"Gid", b"").split() != [b"65534"] * 4
            or child_fields.get(b"Groups") != b"" or child_fields.get(b"Threads") != b"1"
            or child_fields.get(b"NoNewPrivs") != b"1" or child_fields.get(b"Seccomp") != b"2"
            or any(child_fields.get(name) != b"0000000000000000"
                   for name in (b"CapInh", b"CapPrm", b"CapEff", b"CapBnd", b"CapAmb"))
            or _number(child_fields.get(b"Seccomp_filters", b"")) < 1
            or child_fields.get(b"PPid") != str(binding.pid).encode("ascii")):
        raise PermissionError("actual child credentials/caps/threads/NNP/seccomp status differ from the fixed native boundary")
    nspids = child_fields.get(b"NSpid", b"").split()
    if (len(nspids) != len(parent_fields.get(b"NSpid", b"").split()) + 1
            or nspids[0] != str(state.raw.pid).encode("ascii") or nspids[-1] != b"1"):
        raise PermissionError("child's actual PID namespace hierarchy is unavailable or not its new PID-1 boundary")
    for directory, pid in ((parent, binding.pid), (child, state.raw.pid)):
        tasks = scope.open_at(directory, "task", directory=True)
        if scope.names(tasks, 2) != (str(pid),):
            raise PermissionError("original native phase sample found an additional process thread")
        scope.close_one(tasks)
    parent_ns, child_ns = scope.open_at(parent, "ns", directory=True), scope.open_at(child, "ns", directory=True)
    namespaces = []
    for name, kind in _NAMESPACES:
        original, isolated = scope.namespace(parent_ns, name, kind), scope.namespace(child_ns, name, kind)
        shared = name in ("user", "time", "time_for_children")
        if (original == isolated) is not shared:
            raise PermissionError("actual child namespace sharing/isolation differs from the fixed native clone flags")
        namespaces.append(dict(name=name, parent=original, child=isolated, shared=shared))
    identities = {row["name"]: row for row in namespaces}
    if (identities["mnt"]["parent"][:2] != owner.kernel.mount_namespace
            or identities["pid"]["parent"][:2] != owner.kernel.pid_namespace
            or identities["cgroup"]["parent"][:2] != owner.kernel.cgroup_namespace
            or identities["pid"]["child"] != identities["pid_for_children"]["child"]
            or identities["time"]["parent"] != identities["time_for_children"]["parent"]
            or identities["time"]["child"] != identities["time_for_children"]["child"]):
        raise PermissionError("original parent namespace anchor/child future namespace boundary changed")
    observed.facts["namespaces"] = namespaces
    parent_cgroup, child_cgroup = scope.text(parent, "cgroup", q._PROC_SUPER_MAGIC), scope.text(child, "cgroup", q._PROC_SUPER_MAGIC)
    observed.raw["parent_cgroup"], observed.raw["child_cgroup"] = parent_cgroup, child_cgroup
    # /proc/PID/cgroup is relative to the reader's cgroup namespace. The
    # child's CLONE_NEWCGROUP does NOT make this parent read equal to '/'.
    if parent_cgroup != f"0::{owner.cgroup_path}\n".encode("ascii") or child_cgroup != parent_cgroup:
        raise PermissionError("actual child/controller reader-relative unified cgroup membership changed")
    group = scope.directory("/sys/fs/cgroup" + owner.cgroup_path)
    scope.filesystem(group, q._CGROUP2_SUPER_MAGIC)
    if q._identity(os.fstat(group)) != owner.kernel.cgroup_directory:
        raise PermissionError("original controller's actual held cgroup directory changed")
    envelope = binding.controller._state().envelope
    assembly = binding.controller._state()
    controls = {}
    observed.raw["cgroup_controls"] = controls
    for name in ("memory.max", "memory.swap.max", "pids.max", "cpu.max", "cgroup.procs", "cgroup.threads"):
        controls[name] = scope.text(group, name, q._CGROUP2_SUPER_MAGIC)
    if (_number(controls["memory.max"].strip()) != envelope.memory_max_bytes
            or _number(controls["memory.swap.max"].strip()) != envelope.memory_swap_max_bytes
            or _number(controls["pids.max"].strip()) != envelope.pids_max or envelope.pids_max != 2
            or controls["cpu.max"].strip().decode("ascii") != assembly.unit_observation["cpu.max"]
            or tuple(sorted(_number(line) for line in scope.lines(controls["cgroup.procs"]))) != tuple(sorted((binding.pid, state.raw.pid)))
            or tuple(sorted(_number(line) for line in scope.lines(controls["cgroup.threads"]))) != tuple(sorted((binding.pid, state.raw.pid)))):
        raise PermissionError("actual original cgroup limits or its complete two-task membership changed")
    cpu = controls["cpu.max"].strip().split()
    if len(cpu) != 2 or _number(cpu[1]) <= 0 or _number(cpu[0]) * 100 > envelope.cpu_quota_percent * _number(cpu[1]):
        raise PermissionError("actual cgroup CPU limit exceeds the original resource envelope")
    control_facts = {name: _number(controls[name].strip())
        for name in ("memory.max", "memory.swap.max", "pids.max")}
    control_facts["cpu.max"] = tuple(_number(value) for value in cpu)
    for name in ("cgroup.procs", "cgroup.threads"):
        control_facts[name] = tuple(sorted(_number(line) for line in scope.lines(controls[name])))
    observed.facts["cgroup"] = dict(path=owner.cgroup_path, directory=owner.kernel.cgroup_directory,
        controls={name: value.decode("ascii") for name, value in controls.items()},
        normalized_controls=control_facts, original_controller_start_ticks=parent_ticks)
    parent_mount_text, child_mount_text = scope.text(parent, "mountinfo", q._PROC_SUPER_MAGIC), scope.text(child, "mountinfo", q._PROC_SUPER_MAGIC)
    observed.raw["parent_mountinfo"], observed.raw["child_mountinfo"] = parent_mount_text, child_mount_text
    parent_mounts, child_mounts = scope.mounts(parent_mount_text), scope.mounts(child_mount_text)
    cgroup_mount = [mount for mount in parent_mounts if mount.point == "/sys/fs/cgroup"]
    if (len(cgroup_mount) != 1 or cgroup_mount[0].mount_id != owner.kernel.cgroup_mount_id
            or cgroup_mount[0].device != owner.kernel.cgroup_mount_device or cgroup_mount[0].root != "/"
            or cgroup_mount[0].filesystem != "cgroup2"
            or not {"ro", "nosuid", "nodev", "noexec"} <= cgroup_mount[0].options
            or any(mount.point.startswith("/sys/fs/cgroup/") for mount in parent_mounts)):
        raise PermissionError("original controller's actual cgroup mount identity changed")
    root, root_frame, root_link = scope.magic(child, "root", directory=True)
    root_dac = _worker_bits(root_frame, execute=True)
    if root_frame != publisher.tree.root_frame or not os.fstatvfs(root).f_flag & os.ST_RDONLY:
        raise PermissionError("actual child root is not the original immutable phase-source clone")
    _, _, _, root_id = _fdinfo(scope, parent_info, root)
    if root_id == publisher.tree.mount_id:
        raise PermissionError("child root retains the parent's source mount rather than an observed clone")
    root_mount = _exact_mount(child_mounts, "/", root_id, root_frame, publisher.tree.filesystem_root)
    source_root = scope.directory(publication._ROOT)
    _, _, _, parent_root_id = _fdinfo(scope, parent_info, source_root)
    if q._frame(os.fstat(source_root)) != publisher.tree.root_frame or parent_root_id != publisher.tree.mount_id:
        raise PermissionError("original published phase source root changed during child clone observation")
    _exact_mount(parent_mounts, publication._ROOT, parent_root_id, publisher.tree.root_frame, publisher.tree.filesystem_root)
    inputs = scope.path_fd(root, ("inputs",), directory=True)
    if q._frame(os.fstat(inputs)) != publisher.tree.inputs_frame:
        raise PermissionError("actual child input directory differs from the original source frame")
    copies = []
    allowed_inputs = tuple("/inputs/" + PurePosixPath(copy.target).name for copy in batch.copies)
    if any((mount.point == "/inputs" or mount.point.startswith("/inputs/"))
           and mount.point not in allowed_inputs for mount in child_mounts):
        raise PermissionError("actual child root exposes an unregistered input submount")
    clone_ids = [root_id]
    for copy in batch.copies:
        scope.node()
        source = copy.source
        parent_copy, frame = publication.gt._file(scope, copy.target)
        _, _, _, parent_copy_id = _fdinfo(scope, parent_info, parent_copy)
        parent_mount = _exact_mount(parent_mounts, copy.target, parent_copy_id, frame, source.identity.filesystem_root, data=True)
        source_fd, source_frame = publication.gt._file(scope, source.path)
        _, _, _, source_id = _fdinfo(scope, parent_info, source_fd)
        source_mounts = [mount for mount in parent_mounts if mount.mount_id == source_id]
        if (frame != source.frame or source_frame != source.frame or parent_copy_id != copy.installed_mount_id
                or source_id != source.mount_id or q._identity(os.fstat(source_fd))[:4]
                != (source.identity.device, source.identity.inode, source.identity.mode, source.identity.uid)
                or len(source_mounts) != 1 or not {"ro"} <= source_mounts[0].options or source_mounts[0].optional
                or source_mounts[0].device != f"{os.major(source_frame[0])}:{os.minor(source_frame[0])}"
                or not PurePosixPath(source.path).is_relative_to(source_mounts[0].point)
                or str(PurePosixPath(source_mounts[0].root) /
                       PurePosixPath(source.path).relative_to(source_mounts[0].point)) != source.identity.filesystem_root):
            raise PermissionError("current original publisher copies/source identity changed after native clone")
        child_copy = scope.path_fd(inputs, (PurePosixPath(copy.target).name,))
        child_frame = q._frame(os.fstat(child_copy))
        child_dac = _worker_bits(child_frame, read=True)
        _, _, _, clone_id = _fdinfo(scope, parent_info, child_copy)
        if (child_frame != source.frame or clone_id in (parent_copy_id, source_id, publisher.tree.mount_id)
                or clone_id in clone_ids or not os.fstatvfs(child_copy).f_flag & os.ST_RDONLY):
            raise PermissionError("actual child input identity/clone mount differs from its original publication")
        mount = _exact_mount(child_mounts, "/inputs/" + PurePosixPath(copy.target).name,
                             clone_id, child_frame, source.identity.filesystem_root, data=True)
        clone_ids.append(clone_id)
        copies.append(dict(target=mount.point, frame=child_frame, mount=_mount_record(mount),
                           parent_mount=_mount_record(parent_mount), source_path=source.path,
                           source_mount_id=source_id, source_identity=tuple(source_frame[:6]), worker_dac_bits=child_dac))
        for descriptor in (parent_copy, source_fd, child_copy):
            scope.close_one(descriptor)
    # The unused fixed historical slot must remain the original empty source
    # placeholder, with no child mount of its own. No GT contents are opened.
    for target, frame in publisher.tree.targets:
        child_point = "/inputs/" + PurePosixPath(target).name
        if child_point not in allowed_inputs:
            unused = scope.path_fd(inputs, (PurePosixPath(target).name,))
            _, _, _, unused_id = _fdinfo(scope, parent_info, unused)
            if (q._frame(os.fstat(unused)) != frame or unused_id != root_id
                    or any(mount.point == child_point for mount in child_mounts)):
                raise PermissionError("unused child historical slot changed from its original immutable empty placeholder")
            scope.close_one(unused)
    observed.facts["root"] = dict(frame=root_frame, magic_link=root_link, mount=_mount_record(root_mount),
        parent_source_mount_id=parent_root_id, inputs_frame=publisher.tree.inputs_frame, copies=copies,
        worker_dac_bits=root_dac, inputs_worker_dac_bits=_worker_bits(publisher.tree.inputs_frame, execute=True))
    if scope.names(child_fds, 6) != ("3", "4", "5", "6", "7"):
        raise PermissionError("actual pre-exec child descriptor enumeration differs from the fixed native five-FD ABI")
    descriptors, endpoints = [], []
    diag = scope.diag_socket()
    sequence = 1
    for descriptor in (3, 4, 5, 6, 7):
        scope.node()
        before = q._frame(os.stat(str(descriptor), dir_fd=child_fds))
        link = os.readlink(str(descriptor), dir_fd=child_fds)
        raw, fields, flags, mount_id = _fdinfo(scope, child_info, descriptor)
        observed.raw[f"child_fdinfo_{descriptor}"] = raw
        if _number(fields[b"ino"]) != before[1] or flags & os.O_ACCMODE != (os.O_RDWR if descriptor in (3, 4, 6, 7) else os.O_RDONLY):
            raise PermissionError("actual child FD inode/access flags differ from the fixed native ABI")
        if bool(flags & os.O_CLOEXEC) is not (descriptor != 3):
            raise PermissionError("actual child FD close-on-exec flags differ from the fixed native ABI")
        if descriptor in (3, 4, 6):
            if not stat.S_ISSOCK(before[2]) or link != f"socket:[{before[1]}]" or not flags & os.O_NONBLOCK:
                raise PermissionError("actual child IPC/status/permit is not its fixed nonblocking UNIX channel")
            field = {3: "ipc_fd", 4: "status_fd", 6: "permit_fd"}[descriptor]
            original = getattr(state.raw, field)
            parent_frame = q._frame(os.fstat(original))
            if (not stat.S_ISSOCK(parent_frame[2])
                    or scope._native("fcntl", original, 1) != 1
                    or scope._native("fcntl", original, 3) & (os.O_ACCMODE | os.O_NONBLOCK) != (os.O_RDWR | os.O_NONBLOCK)
                    or struct.unpack("=i", scope.option(original, socket.SO_TYPE, 4))[0] != socket.SOCK_STREAM
                    or struct.unpack("=i", scope.option(original, socket.SO_DOMAIN, 4))[0] != socket.AF_UNIX
                    or struct.unpack("=i", scope.option(original, socket.SO_PROTOCOL, 4))[0] != 0):
                raise PermissionError("held original parent channel type/flags differ from its native birth")
            cookie, = struct.unpack("=Q", scope.option(original, _SO_COOKIE, 8))
            peer = _diag(scope, diag, parent_frame[1], cookie, sequence, observed)
            reverse = _diag(scope, diag, before[1], 0xffffffffffffffff, sequence + 1, observed)
            sequence += 2
            if peer["peer_inode"] != before[1] or reverse["peer_inode"] != parent_frame[1]:
                raise PermissionError("actual kernel UNIX peers do not pair the original held parent and fixed child channels")
            # SO_PEERCRED is creation-time parent metadata, NOT child identity.
            creator = struct.unpack("=iii", scope.option(original, socket.SO_PEERCRED, 12))
            parent_groups = parent_fields.get(b"Gid", b"").split()
            if (len(parent_groups) != 4 or creator != (binding.pid, 0, _number(parent_groups[1]))
                    or creator[2] != os.getegid()):
                raise PermissionError("original socketpair creation metadata differs from its root native parent")
            endpoints.append((parent_frame[1], before[1]))
            descriptors.append(dict(fd=descriptor, frame=before, flags=flags, mount_id=mount_id,
                link=link, parent_fd=original, parent_frame=parent_frame,
                kernel_peer=peer, reverse_kernel_peer=reverse, socketpair_creator=creator))
        elif descriptor == 5:
            executable, executable_frame, _ = scope.magic(child_fds, "5")
            runtime = scope.path_fd(root, ("runtime", "bin", "python3"))
            runtime_frame = q._frame(os.fstat(runtime))
            runtime_dac = _worker_bits(runtime_frame, read=True, execute=True)
            _, _, _, runtime_id = _fdinfo(scope, parent_info, runtime)
            _, _, _, executable_id = _fdinfo(scope, parent_info, executable)
            if (not stat.S_ISREG(before[2]) or before != executable_frame or runtime_frame != before
                    or executable_id != runtime_id or before[3] != 0 or before[2] & 0o022
                    or not os.fstatvfs(executable).f_flag & os.ST_RDONLY):
                raise PermissionError("actual pre-opened child FD5 differs from its readonly approved-runtime path")
            covering = [mount for mount in child_mounts if mount.mount_id == runtime_id]
            if (len(covering) != 1 or not {"ro", "nosuid", "nodev"} <= covering[0].options
                    or "noexec" in covering[0].options or covering[0].optional):
                raise PermissionError("actual child runtime executable mount is hidden or has an unsupported execution boundary")
            descriptors.append(dict(fd=5, frame=before, flags=flags, mount_id=runtime_id, link=link,
                runtime_mount=_mount_record(covering[0]), worker_dac_bits=runtime_dac))
            scope.close_one(executable)
            scope.close_one(runtime)
        else:
            if link != "anon_inode:[pidfd]" or fields.get(b"Pid") != str(binding.pid).encode("ascii"):
                raise PermissionError("actual child FD7 does not retain the original parent kernel pidfd")
            descriptors.append(dict(fd=7, frame=before, flags=flags, mount_id=mount_id, link=link,
                parent_pid=_number(fields[b"Pid"])))
        if (before != q._frame(os.stat(str(descriptor), dir_fd=child_fds))
                or link != os.readlink(str(descriptor), dir_fd=child_fds)):
            raise PermissionError("actual child FD changed during original channel observation")
    if len({number for pair in endpoints for number in pair}) != 6:
        raise PermissionError("native phase channels repeat a kernel UNIX socket endpoint")
    observed.facts["descriptors"] = descriptors
    limits = scope.text(child, "limits", q._PROC_SUPER_MAGIC)
    observed.raw["child_limits"] = limits
    matched = []
    for line in scope.lines(limits):
        if line.startswith(b"Max address space"):
            matched.append(line[len(b"Max address space"):].split())
    if matched != [[str(envelope.rlimit_as_per_process_bytes).encode("ascii")] * 2 + [b"bytes"]]:
        raise PermissionError("actual child address-space soft/hard limit differs from the original C/2 envelope")
    # Repeat immutable limits and complete membership on the same held anchor.
    # Retain each actual read before parsing or comparing; live usage is not a fence.
    final_controls = {}
    observed.raw["final_cgroup_controls"] = final_controls
    for name in ("memory.max", "memory.swap.max", "pids.max", "cpu.max", "cgroup.procs", "cgroup.threads"):
        final_controls[name] = scope.text(group, name, q._CGROUP2_SUPER_MAGIC)
    final_control_facts = {name: _number(final_controls[name].strip())
        for name in ("memory.max", "memory.swap.max", "pids.max")}
    final_control_facts["cpu.max"] = tuple(_number(value) for value in final_controls["cpu.max"].strip().split())
    for name in ("cgroup.procs", "cgroup.threads"):
        final_control_facts[name] = tuple(sorted(_number(line) for line in scope.lines(final_controls[name])))
    final_group_identity = q._identity(os.fstat(group))
    observed.facts["final_cgroup"] = dict(path=owner.cgroup_path, directory=final_group_identity,
        normalized_controls=final_control_facts)
    if final_group_identity != owner.kernel.cgroup_directory or final_control_facts != control_facts:
        raise PermissionError("actual held cgroup hard limits or complete task membership drifted before final permit")
    final_stat = scope.text(child, "stat", q._PROC_SUPER_MAGIC)
    final_status = scope.text(child, "status", q._PROC_SUPER_MAGIC)
    observed.raw["final_child_status"] = final_status
    final_security = _fields(scope, final_status)
    security_names = (b"Uid", b"Gid", b"Groups", b"Threads", b"NoNewPrivs", b"Seccomp",
                      b"Seccomp_filters", b"CapInh", b"CapPrm", b"CapEff", b"CapBnd", b"CapAmb",
                      b"PPid", b"Pid", b"NSpid")
    if (_process(scope, final_stat, state.raw.pid) != (ppid, child_ticks)
            or any(final_security.get(name) != child_fields.get(name) for name in security_names)
            or scope.names(child_fds, 6) != ("3", "4", "5", "6", "7")
            or scope.text(child, "mountinfo", q._PROC_SUPER_MAGIC) != child_mount_text
            or scope.text(parent, "mountinfo", q._PROC_SUPER_MAGIC) != parent_mount_text
            or scope.text(child, "cgroup", q._PROC_SUPER_MAGIC) != child_cgroup):
        raise PermissionError("actual child kernel identity/FD/mount/membership changed before final permit")
    # status has voluntary/nonvoluntary switch counters; whole status bytes
    # need not remain equal across a live blocked read. The caller rechecks
    # only the actual immutable security/identity fields below.
    observed.raw["final_child_stat"] = final_stat
    final_pidfd, final_fields, _, _ = _fdinfo(scope, parent_info, state.raw.pidfd)
    observed.raw["final_pidfd_fdinfo"] = final_pidfd
    state.prepermit_wait_final = os.waitid(os.P_PIDFD, state.raw.pidfd, os.WEXITED | os.WNOWAIT | os.WNOHANG)
    if state.prepermit_wait_final is not None or final_fields.get(b"Pid") != str(state.raw.pid).encode("ascii"):
        raise ChildProcessError("original held child exited or changed before final pre-permit confirmation")
    observed.facts["process"] = dict(pid=state.raw.pid, ppid=ppid, start_ticks=child_ticks,
        uid=[65534] * 4, gid=[65534] * 4, groups=[], threads=1, nspid=[_number(value) for value in nspids],
        capabilities={name.decode("ascii"): child_fields[name].decode("ascii")
                      for name in (b"CapInh", b"CapPrm", b"CapEff", b"CapBnd", b"CapAmb")},
        no_new_privs=_number(child_fields[b"NoNewPrivs"]), seccomp=_number(child_fields[b"Seccomp"]),
        seccomp_filters=_number(child_fields[b"Seccomp_filters"]),
        rlimit_as=envelope.rlimit_as_per_process_bytes, original_pidfd=state.raw.pidfd)
    scope.checkpoint()


def _observe_original_child(handle):
    from . import linux_child_launch as children

    state = children._original(handle)
    publication._phase_launch_owner(state)
    if handle in _OBSERVATIONS or state.observation is not None:
        raise PermissionError("original pre-permit kernel observation cannot be repeated/replaced")
    observed = _Observed(state, os.getpid(), threading.current_thread(), time.monotonic_ns())
    state.observation = observed
    state.errors.failure.kernel_observation = observed
    _OBSERVATIONS[handle] = observed  # retained even on partial sample/failure
    scope = None
    primary = None
    try:
        scope = _Scope(state)
        _sample(scope, state, observed)
    except BaseException as error:
        origin = error
        for original_capture in state.captures:
            if error is original_capture.failure:
                origin = original_capture.failure.primary_error
                break
        primary = origin
        for buffer in state.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            reserved = next(buffer._cursor, None)
            if reserved is None:
                buffer.overflowed = True
            else:
                reserved.operation, reserved.error, reserved.descriptor = ("phase_kernel_observation", origin, None)
    finally:
        if scope is not None:
            try:
                scope.close()
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
                        reserved.operation, reserved.error, reserved.descriptor = ("phase_kernel_close_entry", error, None)
                # No close-number retry; only still-owned preallocated slots.
                for slot in scope.slots:
                    descriptor, stream = slot.descriptor, slot.stream
                    slot.descriptor = slot.stream = None
                    if descriptor is None:
                        continue
                    try:
                        if stream is None:
                            os.close(descriptor)
                        else:
                            stream.close()
                    except BaseException as close_error:
                        for buffer in state.captures:
                            reserved = next(buffer._cursor, None)
                            if reserved is None:
                                buffer.overflowed = True
                            else:
                                reserved.operation, reserved.error, reserved.descriptor = (
                                    "phase_kernel_remaining_close", close_error, descriptor)
    if primary is not None or state.errors.first_error is not None:
        publication._phase_launch_failure(state, "phase_kernel_observation_failed", primary or state.errors.first_error)
        state.errors.raise_failure(primary)
    publication._phase_launch_owner(state)
    observed.completed_ns = time.monotonic_ns()
    if observed.completed_ns >= state.stop_ns:
        raise TimeoutError("original child observation crossed its absolute stop boundary")
    observed.sealed = True
    return observed


def _original_observation(state):
    observed = _OBSERVATIONS.get(state.handle)
    if (type(observed) is not _Observed or observed is not state.observation or observed.state is not state
            or observed.pid != os.getpid() or observed.thread is not threading.current_thread()
            or not observed.sealed or observed.completed_ns is None):
        raise PermissionError("phase permit/history lacks its original completed kernel observation")
    return observed


def _history_record(state):
    observed = _original_observation(state)
    # Actual raw bytes remain privately retained. Durable fields describe
    # their observed kernel identities, never substitute hashes as authority.
    return dict(started_monotonic_ns=observed.started_ns, completed_monotonic_ns=observed.completed_ns,
                facts=observed.facts, raw_text_sha256={name: hashlib.sha256(body).hexdigest()
                for name, body in observed.raw.items() if type(body) is bytes})


__all__ = []
