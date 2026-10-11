"""Independent Linux post-exit witness; no in-process acceptance shortcut.

The outer observer must instantiate this witness while the approved unit is
active, outside its cgroup and mount namespace. It holds the original cgroup
directory and kernel files through exit. Missing/offline kernel evidence is a
refusal, never an inference that a disappeared cgroup was empty. Windows QPC
and durable host anchors are separate requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import stat
import subprocess
import sys
import threading
import time
import weakref

from .budget import BudgetLimits, _canonical
from .linux_cgroup_backend import _cgroup2_mount_identity, _validate_unit_name
from .linux_supervisor import Route2Supervisor, TerminalCloseReceipt


_EXIT_PROPERTIES = ("LoadState", "ActiveState", "SubState", "Result", "ExecMainCode",
                    "ExecMainStatus", "MainPID", "InvocationID", "ControlGroup", "Restart", "KillMode")
_MAX_LEDGER_BYTES = 16 << 20
_MAX_UNIT_BYTES = 16 << 10
_UNIT_TIMEOUT = 5.0
_REAP_TIMEOUT = 1.0
_WITNESSES = weakref.WeakKeyDictionary()


def _unit_output(argv):
    """Enforce the byte cap DURING pipe reads, including after child exit."""
    process = stream = selector = None
    deadline = time.monotonic() + _UNIT_TIMEOUT
    chunks, count = [], 0
    try:
        process = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
            close_fds=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        stream = process.stdout
        if stream is None:
            raise PermissionError("outer unit observation has no owned output pipe")
        descriptor = stream.fileno()
        os.set_blocking(descriptor, False)
        selector = selectors.DefaultSelector()
        selector.register(descriptor, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise subprocess.TimeoutExpired(argv, _UNIT_TIMEOUT)
            try:
                value = os.read(descriptor, min(4096, _MAX_UNIT_BYTES - count + 1))
            except BlockingIOError:
                continue
            if not value:
                break
            count += len(value)
            if count > _MAX_UNIT_BYTES:
                raise PermissionError("outer unit observation exceeds its bounded record")
            chunks.append(value)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(argv, _UNIT_TIMEOUT)
        status = process.wait(timeout=remaining)
        if status != 0:
            raise subprocess.CalledProcessError(status, argv)
        return b"".join(chunks)
    finally:
        # A kill/wait failure must not skip pipe or selector cleanup. Preserve
        # the primary read/timeout error; reject cleanup failure on success.
        primary = sys.exc_info()[1]
        failure = None
        if process is not None:
            needs_kill = True
            try:
                needs_kill = process.poll() is None
            except BaseException as exc:
                failure = exc
            if needs_kill:
                try:
                    process.kill()
                except BaseException as exc:
                    failure = failure or exc
            try:
                process.wait(timeout=_REAP_TIMEOUT)
            except BaseException as exc:
                failure = failure or exc
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                failure = failure or exc
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                failure = failure or exc
        if primary is None and failure is not None:
            raise failure


def _unit(unit):
    name = _validate_unit_name(unit)
    encoded = _unit_output(("/usr/bin/systemctl", "show", "--no-pager",
        "--property=" + ",".join(_EXIT_PROPERTIES), name))
    values = {}
    for line in encoded.decode("ascii").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in _EXIT_PROPERTIES or key in values:
            raise PermissionError("outer unit observation is malformed or ambiguous")
        values[key] = value
    if set(values) != set(_EXIT_PROPERTIES):
        raise PermissionError("outer unit observation is incomplete")
    return values


def _proc_start(pid):
    from .linux_quiescence import _ReadScope, _PROC_SUPER_MAGIC, _filesystem, _start_ticks
    scope = _ReadScope()
    try:
        proc = scope.directory(f"/proc/{pid}")
        _filesystem(proc, _PROC_SUPER_MAGIC)
        return _start_ticks(scope.text(proc, "stat", _PROC_SUPER_MAGIC), pid)
    finally:
        scope.close()


def _kernel_read(fd, maximum=65536):
    os.lseek(fd, 0, os.SEEK_SET)
    value = os.read(fd, maximum + 1)
    if len(value) > maximum or os.read(fd, 1):
        raise PermissionError("outer kernel observation exceeds its bounded frame")
    return value.decode("ascii")


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_uid)


def _frame(info):
    return _identity(info) + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _same_open_description(descriptor, reference):
    """Native KCMP_FILE equality, not inode equality; no weaker fallback.

    Syscall numbers are from Linux syscall_64.tbl / asm-generic/unistd.h;
    KCMP_FILE compares struct file pointers in kernel/kcmp.c. Missing/denied
    kernel support raises before issuance, never authenticates an FD by stat.
    """
    numbers = {"x86_64": 312, "aarch64": 272}
    number = numbers.get(platform.machine())
    if number is None or ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(ctypes.c_long) != 8:
        raise PermissionError("outer witness OFD identity requires a supported Linux 64-bit kernel ABI")
    function = ctypes.CDLL(None, use_errno=True).syscall
    function.argtypes = (ctypes.c_long,)
    function.restype = ctypes.c_long
    pid = os.getpid()
    result = function(ctypes.c_long(number), ctypes.c_int(pid), ctypes.c_int(pid),
                      ctypes.c_int(0), ctypes.c_ulong(descriptor), ctypes.c_ulong(reference))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result == 0


@dataclass(frozen=True, slots=True)
class _ObserverKernelIdentity:
    membership: str
    namespaces: tuple[tuple[int, int], ...]
    start_ticks: int
    native_tid: int
    task_start_ticks: int


def _observer_kernel_identity(pid):
    """Read real protected procfs/nsfs; no supplied observer flags or lists."""
    from .linux_quiescence import _ReadScope, _PROC_SUPER_MAGIC, _filesystem, _path, _start_ticks
    scope = _ReadScope()
    try:
        native_tid = threading.get_native_id()
        proc = scope.directory(f"/proc/{pid}")
        _filesystem(proc, _PROC_SUPER_MAGIC)
        start = _start_ticks(scope.text(proc, "stat", _PROC_SUPER_MAGIC), pid)
        # Namespace and membership can differ PER THREAD after setns. Reading
        # only /proc/<tgid>/ns would silently inspect the group leader instead.
        tasks = scope.open_at(proc, "task", directory=True)
        task = scope.open_at(tasks, str(native_tid), directory=True)
        _filesystem(tasks, _PROC_SUPER_MAGIC)
        _filesystem(task, _PROC_SUPER_MAGIC)
        task_start = _start_ticks(scope.text(task, "stat", _PROC_SUPER_MAGIC), native_tid)
        membership = scope.text(task, "cgroup", _PROC_SUPER_MAGIC)
        lines = membership.decode("ascii").splitlines()
        if len(lines) != 1 or not lines[0].startswith("0::") or not membership.endswith(b"\n"):
            raise PermissionError("outer observer unified membership is ambiguous")
        group = _path(lines[0][3:])
        directory = scope.open_at(task, "ns", directory=True)
        _filesystem(directory, _PROC_SUPER_MAGIC)
        namespaces = tuple(scope.namespace(directory, name) for name in ("mnt", "cgroup", "pid"))
        if (membership != scope.text(task, "cgroup", _PROC_SUPER_MAGIC)
                or start != _start_ticks(scope.text(proc, "stat", _PROC_SUPER_MAGIC), pid)
                or task_start != _start_ticks(scope.text(task, "stat", _PROC_SUPER_MAGIC), native_tid)
                or os.getpid() != pid or threading.get_native_id() != native_tid):
            raise PermissionError("outer observer process/membership changed during identity capture")
        for (descriptor, identity), name in zip(namespaces, ("mnt", "cgroup", "pid")):
            visible = os.stat(name, dir_fd=directory, follow_symlinks=True)
            held = os.fstat(descriptor)
            if identity != (visible.st_dev, visible.st_ino) or identity != (held.st_dev, held.st_ino):
                raise PermissionError("outer observer namespace changed during identity capture")
        return _ObserverKernelIdentity(group, tuple(item[1] for item in namespaces), start, native_tid, task_start)
    finally:
        scope.close()


def _require_observer_identity(state):
    if state.observer_pid != os.getpid() or state.observer_thread is not threading.current_thread():
        raise PermissionError("outer witness lost its original observer PID/thread")
    current = _observer_kernel_identity(state.observer_pid)
    if (current != state.observer_kernel or current.membership == state.cgroup_path
            or current.membership.startswith(state.cgroup_path + "/")
            or current.namespaces[0] == state.mount_namespace):
        raise PermissionError("outer observer membership/start/TID/namespace isolation drifted")


def _release_witness_descriptors(state):
    # Transfer ownership out of state BEFORE any close attempt. A failed close
    # consumes that number too; neither cancellation nor GC will retry it.
    descriptors, state.descriptors = state.descriptors, ()
    identities, state.descriptor_identities = state.descriptor_identities, ()
    references, state.descriptor_references = state.descriptor_references, ()
    if state.observer_pid != os.getpid():
        raise PermissionError("outer witness cleanup belongs to its original process")
    failure = None
    for index in reversed(range(len(descriptors))):
        descriptor = descriptors[index]
        try:
            if index >= len(identities) or index >= len(references):
                raise PermissionError("outer witness FD has no original identity")
            current = _identity(os.fstat(descriptor))
            reference = references[index]
            anchor = _identity(os.fstat(reference))
            original = identities[index]
            # Link count/permissions can change on the ORIGINAL kernel inode;
            # those changes refuse observation but do not prevent releasing it.
            # A number now referring to a different kernel object is never closed.
            expected_object = (original[:2], stat.S_IFMT(original[2]))
            if ((current[:2], stat.S_IFMT(current[2])) != expected_object
                    or (anchor[:2], stat.S_IFMT(anchor[2])) != expected_object
                    or not _same_open_description(descriptor, reference)):
                raise PermissionError("outer witness FD number was reused for a foreign object")
        except BaseException as exc:
            failure = failure or exc
            # An ambiguous pair cannot authorize closing either number. Still
            # inspect/release all other original pairs; never blind retry.
            continue
        for number in (descriptor, reference):
            try:
                # Both OFDs were authenticated before consuming the pair. A
                # close error on the first must not skip its private dup anchor.
                info = _identity(os.fstat(number))
                if (info[:2], stat.S_IFMT(info[2])) != expected_object:
                    raise PermissionError("outer witness FD changed immediately before cleanup")
                os.close(number)
            except BaseException as exc:
                failure = failure or exc
    if failure is not None:
        raise failure


def _finish_witness(state):
    """Check live isolation before cleanup; preserve primary failure and try all."""
    primary = sys.exc_info()[1]
    failure = None
    try:
        _require_observer_identity(state)
    except BaseException as exc:
        failure = exc
    try:
        _release_witness_descriptors(state)
    except BaseException as exc:
        failure = failure or exc
    if primary is None and failure is not None:
        raise failure


def _abandon_witness(state):
    """Best effort GC cleanup only; never issue evidence or close in a fork."""
    if state.observer_pid != os.getpid():
        return
    state.attempted = True
    try:
        _release_witness_descriptors(state)
    except BaseException:
        pass


def _ledger(path, expected_identity):
    from .linux_volume_backend import LinuxVolumeOSPorts
    ports = LinuxVolumeOSPorts()
    fd = ports.open_existing(path, kind="file")
    try:
        before = os.fstat(fd)
        if (_identity(before) != expected_identity or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1 or before.st_uid != 0 or before.st_mode & 0o022
                or not 0 < before.st_size <= _MAX_LEDGER_BYTES):
            raise PermissionError("post-exit journal is not its original protected inode")
        chunks, remaining = [], before.st_size
        while remaining:
            value = os.read(fd, min(65536, remaining))
            if not value:
                raise PermissionError("post-exit journal ended before its frozen size")
            chunks.append(value); remaining -= len(value)
        if (os.read(fd, 1) or _frame(before) != _frame(os.fstat(fd))
                or _frame(before) != _frame(ports.path_stat(path, kind="file"))):
            raise PermissionError("post-exit held or visible journal changed during readback")
        return b"".join(chunks), _frame(before)
    finally:
        os.close(fd)


@dataclass(slots=True)
class _LiveWitness:
    unit_name: str
    service_cookie: str
    main_pid: int
    main_start: int
    cgroup_path: str
    cgroup_identity: tuple
    cgroup_mount: dict
    mount_namespace: tuple
    descriptors: tuple[int, ...]
    descriptor_identities: tuple[tuple[int, ...], ...]
    descriptor_references: tuple[int, ...]
    observer_pid: int
    observer_thread: object
    observer_kernel: _ObserverKernelIdentity
    attempted: bool = False


class LinuxPostExitWitness:
    """One original-unit witness, captured before terminal close and exit.

    Runtime installation must bind construction to protected full admission
    and a trusted outer launcher. Public constructor inputs are observations,
    not an admission capability or signed approval.
    """

    def __init__(self, unit_name):
        if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise PermissionError("outer Linux witness requires the installed Linux root observer")
        observer_pid = os.getpid()
        observer_thread = threading.current_thread()
        observer_kernel = _observer_kernel_identity(observer_pid)
        before = _unit(unit_name)
        if (before["LoadState"] != "loaded" or before["ActiveState"] != "active"
                or before["SubState"] != "running" or before["Restart"] != "no"
                or before["KillMode"] != "control-group" or not before["MainPID"].isdecimal()
                or int(before["MainPID"]) <= 0 or len(before["InvocationID"]) != 32
                or any(ch not in "0123456789abcdef" for ch in before["InvocationID"].lower())
                or before["ControlGroup"] != "/system.slice/" + unit_name):
            raise PermissionError("outer witness lacks the original active one-shot service")
        main_pid = int(before["MainPID"])
        group = before["ControlGroup"]
        own_group = observer_kernel.membership
        if own_group == group or own_group.startswith(group + "/"):
            raise PermissionError("post-exit witness must run outside the study cgroup")
        namespace = os.stat(f"/proc/{main_pid}/ns/mnt")
        if (namespace.st_dev, namespace.st_ino) == observer_kernel.namespaces[0]:
            raise PermissionError("outer observer must not inherit the study GT mount namespace")
        mount = _cgroup2_mount_identity(cgroup_root=Path("/sys/fs/cgroup"), mountinfo_path=Path("/proc/self/mountinfo"))
        root = Path("/sys/fs/cgroup") / group.lstrip("/")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        owned = []
        try:
            parent = os.open(root, flags | os.O_DIRECTORY); owned.append(parent)
            info = os.fstat(parent)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise PermissionError("outer witness cgroup directory is not protected")
            for name in ("cgroup.procs", "cgroup.threads", "cgroup.events"):
                owned.append(os.open(name, flags, dir_fd=parent))
            started = _proc_start(main_pid)
            if before != _unit(unit_name) or _identity(info) != _identity(os.stat(root, follow_symlinks=False)):
                raise PermissionError("service/cgroup identity drifted while the outer witness was acquired")
            if str(main_pid) not in _kernel_read(owned[1]).splitlines():
                raise PermissionError("original main PID is absent from the held cgroup")
            if (os.getpid() != observer_pid or threading.current_thread() is not observer_thread
                    or _observer_kernel_identity(observer_pid) != observer_kernel):
                raise PermissionError("original outer observer isolation changed during witness acquisition")
            descriptors = tuple(owned)
            references = []
            for descriptor in descriptors:
                reference = os.dup(descriptor)
                owned.append(reference)
                os.set_inheritable(reference, False)
                if not _same_open_description(descriptor, reference):
                    raise PermissionError("outer witness could not pin its original open file description")
                references.append(reference)
            state = _LiveWitness(unit_name, before["InvocationID"], main_pid, started, group,
                _identity(info), mount, (namespace.st_dev, namespace.st_ino), descriptors,
                tuple(_identity(os.fstat(fd)) for fd in descriptors), tuple(references),
                observer_pid, observer_thread, observer_kernel)
            _require_observer_identity(state)
            # Explicit transfer prevents constructor cleanup and GC from
            # independently owning the same descriptor numbers.
            owned.clear()
            try:
                _WITNESSES[self] = state
                weakref.finalize(self, _abandon_witness, state)
            except BaseException:
                state.attempted = True
                try:
                    _release_witness_descriptors(state)
                except BaseException:
                    pass
                raise
        finally:
            primary = sys.exc_info()[1]
            failure = None
            while owned:
                descriptor = owned.pop()
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    failure = failure or exc
            if primary is None and failure is not None:
                raise failure

    def close(self):
        """Original-owner cancellation before observe; one attempt, no proof.

        Call from the trusted outer launcher's finally path if observation is
        abandoned. Repeating close/observe after consumption is forbidden.
        """
        state = _WITNESSES.get(self)
        if (state is None or state.attempted or state.observer_pid != os.getpid()
                or state.observer_thread is not threading.current_thread()):
            raise PermissionError("outer witness cancellation requires its unconsumed original owner")
        state.attempted = True
        try:
            _require_observer_identity(state)
        finally:
            _finish_witness(state)
        _require_observer_identity(state)

    def signed_launch(self):
        """Export protected original-unit/QPC pins before native close and exit.

        Requires the installed root handoff policy, separate exit secret and
        permanent external attempt directory; it creates no approval.
        """
        try:
            from .linux_native_close_handoff import issue_linux_launch
            return issue_linux_launch(self)
        except BaseException:
            state = _WITNESSES.get(self)
            if (state is not None and not state.attempted and state.observer_pid == os.getpid()
                    and state.observer_thread is threading.current_thread()):
                try:
                    self.close()
                except BaseException:
                    pass
            raise

    def sign_native_close(self, owner_channel):
        """Original outer root signs the kernel-authenticated native owner channel.

        Signing secrets are read here outside the unit, never by the native
        ledger owner. The installed launcher must supply/protect the endpoint.
        """
        try:
            from .linux_native_close_handoff import issue_native_close
            return issue_native_close(self, owner_channel)
        except BaseException:
            state = _WITNESSES.get(self)
            if (state is not None and not state.attempted and state.observer_pid == os.getpid()
                    and state.observer_thread is threading.current_thread()):
                try:
                    self.close()
                except BaseException:
                    pass
            raise

    def observe_signed(self, native_close_bytes):
        """Verify a bounded native signature and sign the actual post-exit read.

        Plain TerminalCloseReceipt/dict inputs cannot cross this bridge. The
        original held cgroup/OFD, isolation, exit and ledger checks still run.
        """
        try:
            from .linux_native_close_handoff import issue_linux_exit
            return issue_linux_exit(self, native_close_bytes)
        except BaseException:
            state = _WITNESSES.get(self)
            if (state is not None and not state.attempted and state.observer_pid == os.getpid()
                    and state.observer_thread is threading.current_thread()):
                try:
                    self.close()
                except BaseException:
                    pass
            raise

    def observe(self, terminal, *, ledger_path, ledger_identity, role_graph_sha256, limits):
        """Observe actual inactive/empty state and reverify a protected close.

        A verified signed native-close handoff must supply these expected
        values. This method does not authenticate that cross-process handoff;
        the installed outer launcher must do so before any acceptance.
        """
        state = _WITNESSES.get(self)
        if (state is None or state.attempted or state.observer_pid != os.getpid()
                or state.observer_thread is not threading.current_thread()):
            raise PermissionError("outer witness is absent, consumed or in a different observer identity")
        state.attempted = True
        try:
            _require_observer_identity(state)
            if type(terminal) is not TerminalCloseReceipt or terminal.unit_name != state.unit_name:
                raise PermissionError("closed terminal differs from the original observed service")
            from .linux_volume_backend import LinuxLoopVolumeExpander
            frozen, _ = LinuxLoopVolumeExpander()._admission()
            if (type(limits) is not BudgetLimits or limits.digest() != frozen.budget_policy_sha256
                    or str(ledger_path) != frozen.budget_ledger_path or role_graph_sha256 != frozen.role_graph_sha256
                    or terminal.deadline_monotonic_ns != terminal.invocation_started_monotonic_ns + limits.total_wall_ns):
                raise PermissionError("outer terminal paths, role graph or wall budget differ from protected full admission")
            before = _unit(state.unit_name)
            _require_observer_identity(state)
            self._inactive(state, before)
            self._empty(state)
            _require_observer_identity(state)
            data, frame = _ledger(ledger_path, ledger_identity)
            _require_observer_identity(state)
            if data != terminal.ledger_bytes:
                raise PermissionError("post-exit journal bytes differ from the native close handoff")
            decoded = json.loads(terminal.terminal_record_bytes)
            evidence = decoded["entry"]["payload"]["evidence"]
            chain = evidence["route2_supervisor_chain"]
            expected_phases = {}
            for raw in data.splitlines():
                event = json.loads(raw)["entry"]
                if event["event"] in ("stage_a_finished", "stage_b_entry_passed", "stage_b_volume_expanded", "stage_b_complete"):
                    if event["event"] in expected_phases:
                        raise PermissionError("duplicate phase in post-exit journal")
                    expected_phases[event["event"]] = event["payload"]
            if hashlib.sha256(_canonical(chain)).hexdigest() != terminal.terminal_binding_sha256:
                raise PermissionError("post-exit chain identity differs from the native close")
            Route2Supervisor._verify_terminal_record(terminal, terminal.status, evidence,
                terminal.terminal_binding_sha256, expected_phases, terminal.invocation_started_monotonic_ns,
                terminal.invocation_started_monotonic_ns + limits.stage_a_wall_ns,
                terminal.deadline_monotonic_ns, role_graph_sha256)
            self._empty(state)
            _require_observer_identity(state)
            if _unit(state.unit_name) != before:
                raise PermissionError("inactive service identity changed during external terminal verification")
            _require_observer_identity(state)
            data_after, after_frame = _ledger(ledger_path, ledger_identity)
            _require_observer_identity(state)
            if data_after != data or after_frame != frame:
                raise PermissionError("post-exit terminal changed after full verification")
            observation = {"unit_name": state.unit_name, "systemd_invocation_id": state.service_cookie,
                "unit_result": before["Result"], "exit_status": int(before["ExecMainStatus"]),
                "active_state": before["ActiveState"], "cgroup_path": state.cgroup_path,
                "cgroup_empty": True, "terminal_reverified": True,
                "terminal_sha256": terminal.terminal_sha256,
                "ledger_sha256": hashlib.sha256(data).hexdigest()}
        finally:
            _finish_witness(state)
        _require_observer_identity(state)
        observed = time.monotonic_ns()
        if observed < terminal.terminal_closed_monotonic_ns:
            raise PermissionError("outer Linux observation precedes the native terminal close")
        if terminal.status != "INCOMPLETE_RESOURCE" and observed > terminal.deadline_monotonic_ns:
            raise PermissionError("outer Linux observation and descriptor cleanup exceeded the full-study wall deadline")
        return {**observation, "observed_monotonic_ns": observed}

    @staticmethod
    def _inactive(state, properties):
        if (properties["LoadState"] != "loaded" or properties["ActiveState"] != "inactive"
                or properties["SubState"] != "dead" or properties["Result"] != "success"
                or properties["ExecMainCode"] != "1" or properties["ExecMainStatus"] != "0"
                or properties["MainPID"] != "0" or properties["InvocationID"] != state.service_cookie
                or properties["ControlGroup"] not in ("", state.cgroup_path)
                or properties["Restart"] != "no" or properties["KillMode"] != "control-group"):
            raise PermissionError("external service exit is not the same successful inactive one-shot invocation")
        try:
            if _proc_start(state.main_pid) == state.main_start:
                raise PermissionError("original study main process is still alive")
        except FileNotFoundError:
            pass

    @staticmethod
    def _empty(state):
        if (len(state.descriptors) != 4 or len(state.descriptor_identities) != 4
                or len(state.descriptor_references) != 4):
            raise PermissionError("outer witness lost its original held kernel FD set")
        if _cgroup2_mount_identity(cgroup_root=Path("/sys/fs/cgroup"), mountinfo_path=Path("/proc/self/mountinfo")) != state.cgroup_mount:
            raise PermissionError("outer cgroup2 mount identity changed")
        if _identity(os.fstat(state.descriptors[0])) != state.cgroup_identity:
            raise PermissionError("outer witness lost its original cgroup inode")
        for descriptor, identity, reference in zip(state.descriptors, state.descriptor_identities, state.descriptor_references):
            if (_identity(os.fstat(descriptor)) != identity
                    or _identity(os.fstat(reference)) != identity
                    or not _same_open_description(descriptor, reference)):
                raise PermissionError("outer witness kernel FD was replaced before population read")
        if _kernel_read(state.descriptors[1]).strip() or _kernel_read(state.descriptors[2]).strip():
            raise PermissionError("study cgroup retains process or thread membership")
        events = {}
        for line in _kernel_read(state.descriptors[3]).splitlines():
            pair = line.split()
            if len(pair) != 2 or pair[0] in events or not pair[1].isdecimal():
                raise PermissionError("held cgroup event evidence is malformed")
            events[pair[0]] = int(pair[1])
        if events.get("populated") != 0:
            raise PermissionError("study cgroup or a descendant remains populated")
        for descriptor, identity, reference in zip(state.descriptors, state.descriptor_identities, state.descriptor_references):
            if (_identity(os.fstat(descriptor)) != identity
                    or _identity(os.fstat(reference)) != identity
                    or not _same_open_description(descriptor, reference)):
                raise PermissionError("outer witness kernel FD changed during population read")


__all__ = ["LinuxPostExitWitness"]
