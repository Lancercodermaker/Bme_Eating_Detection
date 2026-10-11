"""Concrete root issuance bridges; preparation imports do not touch native state.

Installation must supply a root-only HMAC policy containing the public trust
and ORIGINAL per-invocation session, plus separate 0400 raw Ed25519 secrets.
The policy must be produced by the installed launcher from its pre-bootstrap
clock and the Windows challenge, never by the study caller. This code neither
installs those objects nor produces an approval. Durable markers are on the
external control filesystem; their payload caps are not physical volume caps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import os
from pathlib import Path, PurePosixPath
import socket
import stat
import struct
import sys
import threading
import time
import weakref

from . import native_close_handoff as wire
from .budget import BudgetGuard, require_owned_ledger_close_success
from .contracts import STUDY_ID
from .linux_supervisor import Route2Supervisor
from .linux_volume_backend import LinuxLoopVolumeExpander, LinuxVolumeOSPorts, _close_temporary_fds
from .startup_ownership import require_startup_binding


POLICY_PATH = f"/etc/route2/{STUDY_ID}-native-close.seal"
NATIVE_SECRET_PATH = f"/etc/route2/{STUDY_ID}-native-close.ed25519"
EXIT_SECRET_PATH = f"/etc/route2/{STUDY_ID}-linux-exit.ed25519"
ATTEMPT_ROOT = "/var/lib/route2-controller/native-close-handoff-attempts"
_NATIVE_ATTEMPTS = weakref.WeakSet()
_EXIT_BRIDGES = weakref.WeakKeyDictionary()
_LOCK = threading.RLock()
_OBSERVE_CLOSE = Route2Supervisor.observe_budget_terminal_close


@dataclass(frozen=True, slots=True)
class _Policy:
    trust: dict
    session: dict
    frozen: object
    config_bytes: bytes
    seal_bytes: bytes
    policy_bytes: bytes


@dataclass(slots=True)
class _ExitBridge:
    policy: _Policy
    witness_state: object
    observer: dict
    pid: int
    thread: object
    launch_issued_ns: int
    attempted: bool = False
    native_attempted: bool = False
    native_sha256: str = ""


def _protected(path, maximum):
    ports = LinuxVolumeOSPorts()
    ports.require_linux_root()
    descriptor = ports.open_existing(path, kind="file")
    try:
        before = os.fstat(descriptor)
        if stat.S_IMODE(before.st_mode) != 0o400:
            raise PermissionError("handoff policy/secret must be a root-owned single-link 0400 file")
        encoded = ports.read_fd(descriptor, max_bytes=maximum)
        frame = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                              info.st_uid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if frame(before) != frame(os.fstat(descriptor)) or frame(before) != frame(ports.path_stat(path, kind="file")):
            raise PermissionError("handoff protected file changed during its held read")
        return encoded
    finally:
        os.close(descriptor)


def _policy():
    from .admission_bootstrap import parse_supervisor_config
    frozen, (config_bytes, controller_key, seal_bytes) = LinuxLoopVolumeExpander()._admission()
    config = parse_supervisor_config(config_bytes)
    policy_bytes = _protected(POLICY_PATH, wire.MAX_TRUST_BYTES)
    envelope = wire.parse(policy_bytes, wire.MAX_TRUST_BYTES)
    wire._exact(envelope, {"body", "controller_hmac_sha256"})
    body = envelope["body"]
    wire._exact(body, {"schema", "trust", "session"})
    signature = wire._hex(envelope["controller_hmac_sha256"], 64)
    message = b"route2-native-close-policy-v1\0" + wire.canonical(body)
    if not hmac.compare_digest(signature, hmac.new(controller_key, message, hashlib.sha256).hexdigest()):
        raise PermissionError("native-close policy is not authenticated by the protected full A+B controller")
    trust, session = body["trust"], body["session"]
    wire.validate_trust(trust)
    wire.validate_session(session)
    if (body["schema"] != "route2_native_close_policy_v1"
            or trust["full_ab_seal_sha256"] != wire.digest(seal_bytes)
            or trust["frozen_admission_sha256"] != wire.digest(wire.canonical(asdict(frozen)))
            or trust["authorization_card_sha256"] != config.authorization_card_sha256
            or trust["owner_approval_id"] != config.owner_approval_id
            or trust["independent_review_id"] != config.independent_review_id
            or trust["budget_policy_sha256"] != frozen.budget_policy_sha256
            or trust["ledger_path"] != frozen.budget_ledger_path
            or trust["role_graph_sha256"] != frozen.role_graph_sha256):
        raise PermissionError("handoff policy does not bind the complete protected A+B seal and budget")
    for path in (POLICY_PATH, NATIVE_SECRET_PATH, EXIT_SECRET_PATH, ATTEMPT_ROOT):
        if any(PurePosixPath(path).is_relative_to(PurePosixPath(root)) for root in (
                frozen.source_snapshot_root, frozen.runtime_snapshot_root, frozen.approved_write_volumes[0])):
            raise PermissionError("handoff secrets/trust/attempts must remain outside source, runtime and study storage")
    return _Policy(trust, session, frozen, config_bytes, seal_bytes, policy_bytes)


def _unchanged(policy):
    current = _policy()
    if (current.config_bytes != policy.config_bytes or current.seal_bytes != policy.seal_bytes
            or current.policy_bytes != policy.policy_bytes):
        raise PermissionError("original protected full A+B/handoff policy changed during issuance")


def _require_actual_observer_runtime_closure(config, snapshots, *, runtime_root):
    """Installation refusal, not a caller-supplied approval or bootstrap flag.

    ``snapshots`` describes files and actual readonly mounts in THIS process's
    namespace. It does not prove the external observer's loaded executable,
    stdlib/import closure, ELF interpreter/shared-library mappings, transitive
    provider dependencies, ABI or the protected pre-import launch continuity.
    A study-process bootstrap/attestation cannot establish those facts for this
    separate PID. No native producer for that complete observer boundary is
    installed or implemented here, so even matching snapshots must refuse.
    """
    raise PermissionError(
        "actual external signer/observer runtime identity producer is missing: "
        "loaded interpreter, stdlib/imports, ELF/native dependency closure, ABI "
        "and protected observer launch continuity are unproven; readonly study "
        "source/runtime snapshots or study bootstrap cannot substitute"
    )


def require_provider_origin():
    """Revalidate this process's snapshots, then require its native identity.

    The old 13-wheel snapshot cannot satisfy a new cryptography installation:
    the complete file-set/hash check must use a newly reviewed and sealed tree.
    Snapshot checks are concrete preliminary evidence, not a proof that the
    outer root observer ran that complete immutable closure. The missing actual
    observer producer below explicitly refuses BEFORE cryptography import.
    """
    from .admission_bootstrap import (parse_supervisor_config, _read_snapshot_manifest,
                                     _verify_live_snapshots, MAX_SOURCE_MANIFEST_BYTES)
    from .linux_quiescence import _ReadScope, _PROC_SUPER_MAGIC
    policy = _policy()
    config = parse_supervisor_config(policy.config_bytes)
    if sys.flags.isolated != 1 or sys.dont_write_bytecode is not True:
        raise PermissionError("provider bridge requires the immutable isolated no-bytecode interpreter")
    scope = _ReadScope()
    try:
        proc = scope.directory(f"/proc/{os.getpid()}/task/{threading.get_native_id()}")
        mountinfo = scope.text(proc, "mountinfo", _PROC_SUPER_MAGIC).decode("utf-8")
    finally:
        scope.close()
    snapshots = _verify_live_snapshots(config,
        source_manifest_bytes=_read_snapshot_manifest(config.source_manifest_path, max_bytes=MAX_SOURCE_MANIFEST_BYTES),
        runtime_manifest_bytes=_read_snapshot_manifest(config.runtime_manifest_path, max_bytes=MAX_SOURCE_MANIFEST_BYTES),
        mountinfo_text=mountinfo)
    root = Path(config.runtime_snapshot_root).resolve(strict=True)
    if Path(sys.prefix).resolve(strict=True) != root or not Path(sys.executable).resolve(strict=True).is_relative_to(root):
        raise PermissionError("provider bridge interpreter/prefix escaped the frozen immutable runtime")
    for entry in sys.path:
        if (type(entry) is not str or not Path(entry).is_absolute()
                or ("site-packages" in Path(entry).parts and not Path(entry).resolve(strict=True).is_relative_to(root))):
            raise PermissionError("provider bridge refuses ambient import/site-packages paths")
    _unchanged(policy)
    _require_actual_observer_runtime_closure(config, snapshots, runtime_root=root)
    return root


def _boot_id():
    from .linux_quiescence import _ReadScope, _PROC_SUPER_MAGIC
    scope = _ReadScope()
    try:
        directory = scope.directory("/proc/sys/kernel/random")
        encoded = scope.text(directory, "boot_id", _PROC_SUPER_MAGIC)
        if len(encoded) != 37 or not encoded.endswith(b"\n"):
            raise PermissionError("actual Linux boot identity is not a bounded kernel record")
        return encoded[:-1].decode("ascii")
    finally:
        scope.close()


def _reserve(policy, kind, study_device):
    """Exclusive, permanent one-study tombstone before any signing attempt.

    Empty file and parent are flushed before the bounded payload. Failure never
    unlinks or authorizes retry. A failed first fsync is NOT a crash-durability
    claim; the installed failure/quarantine controller must retain that state.
    """
    ports = LinuxVolumeOSPorts()
    parent = ports.open_existing(ATTEMPT_ROOT, kind="directory")
    owned = [parent]
    try:
        info = os.fstat(parent)
        if stat.S_IMODE(info.st_mode) != 0o700 or info.st_dev == study_device:
            raise PermissionError("handoff attempts require a root-only external control directory")
        encoded = wire.canonical({"schema": "route2_handoff_attempt_v1", "kind": kind,
                                  "context": wire.context(policy.trust, policy.session)})
        if len(encoded) > policy.trust["attempt_payload_cap_bytes"]:
            raise PermissionError("handoff attempt exceeds its explicitly installed marker cap")
        descriptor = os.open(STUDY_ID + "." + kind + ".attempt",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
        owned.append(descriptor)
        os.fsync(descriptor)
        os.fsync(parent)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if not 0 < written <= len(encoded) - offset:
                raise OSError("invalid handoff attempt write count")
            offset += written
        os.fsync(descriptor)
        os.fsync(parent)
    finally:
        _close_temporary_fds(owned)


def _clock(policy, *, terminal=None):
    now = time.monotonic_ns()
    started = policy.session["invocation_started_monotonic_ns"]
    limits = wire.validate_trust(policy.trust)
    if (now < started or ((terminal is None or terminal.status != "INCOMPLETE_RESOURCE")
            and now > started + limits.total_wall_ns)):
        raise PermissionError("handoff issuance and cleanup exceeded the original Linux wall frame")
    return now


def _require_owner(guard, policy):
    from .linux_initial_volume import LinuxInitialVolumeOSPorts
    from .linux_post_exit import _unit, _proc_start
    binding = require_startup_binding(guard)
    if binding is None or type(binding.owner()) is not Route2Supervisor:
        raise PermissionError("native signing requires the original bound guard/supervisor")
    owner = binding.owner()
    session = policy.session
    if (binding.pid != session["main_pid"] or binding.pid != os.getpid()
            or binding.invocation_id != session["invocation_id"]
            or binding.started_ns != session["invocation_started_monotonic_ns"]
            or asdict(binding.limits) != policy.trust["limits"]
            or str(binding.ledger.path) != policy.trust["ledger_path"]
            or owner.external_started_ticks != session["external_started_ticks"]
            or owner.qpc_frequency != session["qpc_frequency"]
            or _proc_start(binding.pid) != session["main_start_ticks"]
            or _boot_id() != session["linux_boot_id"]):
        raise PermissionError("native issuer is outside its protected original PID/start/budget/clock binding")
    properties = _unit(session["unit_name"])
    if (properties["InvocationID"] != session["systemd_invocation_id"]
            or properties["MainPID"] != str(binding.pid) or properties["ActiveState"] != "active"
            or properties["SubState"] != "running" or properties["Restart"] != "no"
            or properties["KillMode"] != "control-group"
            or properties["ControlGroup"] != "/system.slice/" + session["unit_name"]):
        raise PermissionError("native issuer does not belong to the original active one-shot service")
    LinuxInitialVolumeOSPorts().require_live_bootstrap(policy.frozen, policy.config_bytes, policy.seal_bytes)
    return binding, owner


def _prepare_native_close(guard):
    """Serialize once from the native owner for the authenticated outer channel.

    Call after native finalize and BEFORE any other terminal-handoff reader.
    Missing actual GT/worker history continues to refuse in the native reader.
    No terminal or durable externally accepted result is synthesized here.
    """
    with _LOCK:
        if type(guard) is not BudgetGuard or guard in _NATIVE_ATTEMPTS:
            raise PermissionError("native-close signing requires one unconsumed original BudgetGuard")
        _NATIVE_ATTEMPTS.add(guard)
    policy = _policy()
    binding, owner = _require_owner(guard, policy)
    from . import terminal_observation as native
    with native._LOCK:
        state = native._OBSERVERS.get(guard)
        if state is None or state.failed or state.step != "closed" or state.binding is not binding:
            raise PermissionError("native signing lacks the private original successful close observer")
        identity = state.identity
        if require_owned_ledger_close_success(binding.ledger, state.owner_fd) != state.closed_ns:
            raise PermissionError("native signing lost the private original ledger-close success fact")
        method = owner.observe_budget_terminal_close
        if getattr(method, "__self__", None) is not owner or getattr(method, "__func__", None) is not _OBSERVE_CLOSE:
            raise PermissionError("native close issuer method was replaced")
        terminal = _OBSERVE_CLOSE(owner, guard)
        if (native._OBSERVERS.get(guard) is not state or state.failed or state.step != "handed_off"
                or owner._terminal is not terminal or require_startup_binding(guard) is not binding):
            raise PermissionError("native close was not handed off by the original private owner")
    _require_owner(guard, policy)
    _unchanged(policy)
    wire.decode_terminal(wire.terminal_wire(terminal), policy.trust, policy.session)
    body = {"context": wire.context(policy.trust, policy.session), "terminal": wire.terminal_wire(terminal),
            "ledger_identity": list(identity), "ledger_sha256": wire.digest(terminal.ledger_bytes),
            "issued_monotonic_ns": _clock(policy, terminal=terminal)}
    encoded = wire.canonical(body)
    if len(encoded) > policy.trust["native_payload_cap_bytes"]:
        raise PermissionError("native owner channel request exceeds its explicit installed byte cap")
    _unchanged(policy)
    _require_owner(guard, policy)
    _clock(policy, terminal=terminal)
    return encoded


def _witness(witness, policy, *, state=None):
    from .linux_post_exit import LinuxPostExitWitness, _WITNESSES, _require_observer_identity
    current = _WITNESSES.get(witness)
    if (type(witness) is not LinuxPostExitWitness or current is None
            or (state is not None and current is not state)):
        raise PermissionError("signed exit bridge lacks the original native Linux witness")
    _require_observer_identity(current)
    session = policy.session
    if (current.unit_name != session["unit_name"] or current.service_cookie != session["systemd_invocation_id"]
            or current.main_pid != session["main_pid"] or current.main_start != session["main_start_ticks"]
            or _boot_id() != session["linux_boot_id"]):
        raise PermissionError("outer witness differs from the protected original unit/boot/PID identity")
    return current


def issue_linux_launch(witness):
    """Export signed original-unit pins while the independently held unit is active."""
    with _LOCK:
        if witness in _EXIT_BRIDGES:
            raise PermissionError("outer signed launch may be attempted only once")
        # A poisoned sentinel consumes failures before policy acquisition too.
        _EXIT_BRIDGES[witness] = None
    policy = _policy()
    state = _witness(witness, policy)
    if state.attempted:
        raise PermissionError("signed launch cannot reuse a consumed witness")
    require_provider_origin()  # Missing observer closure refuses before durable markers.
    from .linux_post_exit import _unit, _proc_start, _ledger
    properties = _unit(state.unit_name)
    if (properties["InvocationID"] != state.service_cookie or properties["ActiveState"] != "active"
            or properties["SubState"] != "running" or properties["MainPID"] != str(state.main_pid)
            or properties["Restart"] != "no" or properties["KillMode"] != "control-group"
            or _proc_start(state.main_pid) != state.main_start):
        raise PermissionError("signed launch requires the original unit still active")
    ports = LinuxVolumeOSPorts()
    info = ports.path_stat(policy.trust["ledger_path"], kind="file")
    # The ledger is read only to bind the exact startup clock/limits/invocation.
    identity = (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_uid)
    data, _ = _ledger(policy.trust["ledger_path"], identity)
    if len(data) > wire.MAX_TRUST_BYTES or not data.endswith(b"\n"):
        raise PermissionError("signed launch requires the bounded durable startup journal")
    lines = data.splitlines()
    if len(lines) != 2:
        raise PermissionError("signed launch must be pinned at startup, before any study work/terminal close")
    records = [wire.parse(line, wire.MAX_TRUST_BYTES) for line in lines]
    previous = "0" * 64
    for index, record in enumerate(records):
        wire._exact(record, {"entry", "sha256"})
        entry = record["entry"]
        wire._exact(entry, {"seq", "event", "payload", "previous_sha256"})
        if (type(entry["seq"]) is not int or entry["seq"] != index
                or entry["event"] != ("study_created", "invocation_started")[index]
                or entry["previous_sha256"] != previous or type(entry["payload"]) is not dict
                or record["sha256"] != wire.digest(wire.canonical(entry))):
            raise PermissionError("signed launch startup journal has an invalid original hash chain")
        previous = record["sha256"]
    created, started = (record["entry"]["payload"] for record in records)
    wire._exact(created, {"study_id", "approval_record", "input_registry_sha256", "budget_policy_sha256", "limits", "created_wall_ns"})
    wire._exact(started, {"invocation_id", "monotonic_ns", "controller_receipt", "startup_snapshot", "frozen_rss_ceiling_bytes"})
    if (created["study_id"] != STUDY_ID or created["approval_record"] != policy.trust["owner_approval_id"]
            or created["input_registry_sha256"] != policy.frozen.combined_input_registry_sha256
            or created["budget_policy_sha256"] != policy.trust["budget_policy_sha256"]
            or wire.canonical(created["limits"]) != wire.canonical(policy.trust["limits"])
            or started["invocation_id"] != policy.session["invocation_id"]
            or type(started["monotonic_ns"]) is not int
            or started["monotonic_ns"] != policy.session["invocation_started_monotonic_ns"]
            or type(started["controller_receipt"]) is not dict
            or started["controller_receipt"].get("parent_cgroup_path") != state.cgroup_path):
        raise PermissionError("signed launch startup journal differs from protected A+B inputs/budget/original epoch")
    wire._integer(created["created_wall_ns"])
    _reserve(policy, "linux_launch", info.st_dev)
    observer = {"pid": state.observer_pid, **asdict(state.observer_kernel)}
    observer = wire.parse(wire.canonical(observer), wire.MAX_EXIT_BYTES)
    body = {"context": wire.context(policy.trust, policy.session), "observer": observer,
            "issued_monotonic_ns": _clock(policy)}
    require_provider_origin()  # Complete outer identity BEFORE secret access.
    encoded = wire._sign("linux_launch", body, _protected(EXIT_SECRET_PATH, 32),
                         policy.trust["linux_exit_public_key"], policy.trust["exit_payload_cap_bytes"])
    _unchanged(policy)
    _witness(witness, policy, state=state)
    if _unit(state.unit_name) != properties:
        raise PermissionError("original active unit changed during signed launch export")
    _clock(policy)
    _EXIT_BRIDGES[witness] = _ExitBridge(policy, state, observer, os.getpid(), threading.current_thread(),
                                      body["issued_monotonic_ns"])
    return encoded


def issue_linux_exit(witness, native_bytes):
    """Verify the native signature, run the concrete witness, then sign its result."""
    with _LOCK:
        bridge = _EXIT_BRIDGES.get(witness)
        if (bridge is None or bridge.attempted or not bridge.native_attempted or not bridge.native_sha256
                or bridge.pid != os.getpid()
                or bridge.thread is not threading.current_thread()):
            raise PermissionError("signed Linux exit requires the original unconsumed launch bridge")
        bridge.attempted = True
    policy = bridge.policy
    state = bridge.witness_state
    try:
        _unchanged(policy)
        _witness(witness, policy, state=state)
        require_provider_origin()
        if type(native_bytes) is not bytes or wire.digest(native_bytes) != bridge.native_sha256:
            raise PermissionError("signed exit differs from this original root witness's issued native-close bytes")
        terminal, identity, _ = wire.decode_native(native_bytes, policy.trust, policy.session)
        _reserve(policy, "linux_exit", identity[0])
        from .linux_post_exit import LinuxPostExitWitness
        observation = LinuxPostExitWitness.observe(witness, terminal, ledger_path=policy.trust["ledger_path"],
            ledger_identity=identity, role_graph_sha256=policy.trust["role_graph_sha256"],
            limits=wire.validate_trust(policy.trust))
        wire.require_observation(observation, terminal, policy.session)
        body = {"context": wire.context(policy.trust, policy.session), "observer": bridge.observer,
                "native_handoff_sha256": wire.digest(native_bytes), "observation": observation,
                "issued_monotonic_ns": _clock(policy, terminal=terminal)}
        require_provider_origin()  # Study bootstrap cannot authenticate this observer.
        encoded = wire._sign("linux_exit", body, _protected(EXIT_SECRET_PATH, 32),
                             policy.trust["linux_exit_public_key"], policy.trust["exit_payload_cap_bytes"])
        _unchanged(policy)
        _witness(witness, policy, state=state)
        _clock(policy, terminal=terminal)
        return encoded
    finally:
        primary = sys.exc_info()[1]
        if not state.attempted:
            try:
                witness.close()
            except BaseException:
                if primary is None:
                    raise


def _channel(channel, expected_pid):
    """Authenticate the actual connected root process, not supplied credentials."""
    if (type(channel) is not socket.socket or channel.family != socket.AF_UNIX
            or channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM
            or channel.get_inheritable()):
        raise PermissionError("native-close bridge requires one owned CLOEXEC Unix stream endpoint")
    raw = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("=3i"))
    if struct.unpack("=3i", raw) != (expected_pid, 0, 0):
        raise PermissionError("native-close channel peer is not the original root process")
    info = os.fstat(channel.fileno())
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
        raise PermissionError("native-close channel is not its original root-owned kernel socket")
    return channel.fileno(), (info.st_dev, info.st_ino)


def _channel_live(channel, pin, reference, peer_pid):
    from .linux_post_exit import _same_open_description
    descriptor, identity = _channel(channel, peer_pid)
    if ((descriptor, identity) != pin or not _same_open_description(descriptor, reference)
            or (os.fstat(reference).st_dev, os.fstat(reference).st_ino) != identity):
        raise PermissionError("native-close endpoint lost its original held open file description")


def _release_channel_reference(reference, pin):
    """Release only our original socket dup; a foreign reused number is refused."""
    primary = sys.exc_info()[1]
    try:
        info = os.fstat(reference)
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0
                or (info.st_dev, info.st_ino) != pin[1]):
            raise PermissionError("native-close socket dup was reused for a foreign kernel object")
        os.close(reference)
    except BaseException:
        if primary is None:
            raise


def _transport_remaining(policy, transport_deadline):
    now = _clock(policy, terminal=None)
    remaining = min(transport_deadline, policy.session["invocation_started_monotonic_ns"]
                    + wire.validate_trust(policy.trust).total_wall_ns) - now
    if remaining <= 0:
        raise PermissionError("native-close transport exceeded its bounded original wall frame")
    return remaining / 1_000_000_000


def _receive_owner(channel, policy, pin, reference, transport_deadline):
    """Kernel credentials on EVERY chunk; exactly one bounded length+EOF frame.

    SO_PEERCRED binds the connecting process; SO_PASSCRED also refuses inherited
    endpoints used by a different sender. Unexpected rights are closed once,
    and unknown/truncated ancillary records never authenticate a handoff.
    """
    channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    expected = (policy.session["main_pid"], 0, 0)

    def receive(maximum):
        _channel_live(channel, pin, reference, expected[0])
        channel.settimeout(_transport_remaining(policy, transport_deadline))
        value, ancillary, flags, _ = channel.recvmsg(maximum, socket.CMSG_SPACE(12), socket.MSG_CMSG_CLOEXEC)
        credentials = []
        invalid = bool(flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC))
        failure = None
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                invalid = True
                if len(data) % struct.calcsize("=i"):
                    invalid = True
                for index in range(0, len(data) - len(data) % 4, 4):
                    number = struct.unpack("=i", data[index:index + 4])[0]
                    try:
                        os.close(number)  # Newly received ownership; never retried.
                    except BaseException as exc:
                        failure = failure or exc
            elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                credentials.append(struct.unpack("=3i", data))
            else:
                invalid = True
        _channel_live(channel, pin, reference, expected[0])
        if failure is not None:
            raise failure
        if invalid or (value and credentials != [expected]):
            raise PermissionError("native-close bytes have no exact original kernel sender credentials")
        return value

    def exactly(count):
        chunks = []
        while count:
            value = receive(min(65536, count))
            if not value:
                raise PermissionError("native-close owner frame ended before its declared size")
            chunks.append(value)
            count -= len(value)
        return b"".join(chunks)

    maximum = struct.unpack("!I", exactly(4))[0]
    if not 0 < maximum <= policy.trust["native_payload_cap_bytes"]:
        raise PermissionError("native-close owner frame exceeds the explicitly installed transport cap")
    encoded = exactly(maximum)
    if receive(1):
        raise PermissionError("native-close owner channel has trailing/replayed bytes")
    _transport_remaining(policy, transport_deadline)
    return encoded


def send_native_close(guard, channel, signed_launch_bytes):
    """Original root owner sends its PRIVATE native-close read to the outer root.

    The installed launcher must establish/protect the Unix endpoints and keep
    the controller alive through receipt. This function reads no signing key.
    It owns neither endpoint and never closes a caller's numeric descriptor.
    """
    policy = _policy()
    _require_owner(guard, policy)
    launch = wire.verify(signed_launch_bytes, "linux_launch", policy.trust["linux_exit_public_key"],
                         policy.trust["exit_payload_cap_bytes"])
    wire._exact(launch, {"context", "observer", "issued_monotonic_ns"})
    wire._require_context(launch["context"], policy.trust, policy.session)
    from .windows_native_close_handoff import _observer
    _observer(launch["observer"], policy.session)
    observer = launch["observer"]
    from .linux_post_exit import _proc_start
    from .linux_quiescence import _ReadScope, _PROC_SUPER_MAGIC
    if _proc_start(observer["pid"]) != observer["start_ticks"]:
        raise PermissionError("native-close receiver lost the original root observer process")
    scope = _ReadScope()
    try:
        task = scope.directory(f"/proc/{observer['pid']}/task/{observer['native_tid']}")
        if scope.text(task, "cgroup", _PROC_SUPER_MAGIC) != ("0::" + observer["membership"] + "\n").encode("ascii"):
            raise PermissionError("native-close receiver left its original independent cgroup")
        namespace = scope.open_at(task, "ns", directory=True)
        actual = [list(scope.namespace(namespace, name)[1]) for name in ("mnt", "cgroup", "pid")]
        if actual != observer["namespaces"]:
            raise PermissionError("native-close receiver left its original independent kernel namespaces")
    finally:
        scope.close()
    pin = _channel(channel, observer["pid"])
    reference = os.dup(pin[0])
    try:
        _channel_live(channel, pin, reference, observer["pid"])
        encoded = _prepare_native_close(guard)
        deadline = time.monotonic_ns() + 5_000_000_000
        frame = struct.pack("!I", len(encoded)) + encoded
        for offset in range(0, len(frame), 65536):
            _channel_live(channel, pin, reference, observer["pid"])
            channel.settimeout(_transport_remaining(policy, deadline))
            channel.sendall(frame[offset:offset + 65536])
        channel.shutdown(socket.SHUT_WR)
        _channel_live(channel, pin, reference, observer["pid"])
        _transport_remaining(policy, deadline)
    finally:
        # Only this freshly owned dup is released here; no endpoint retry.
        _release_channel_reference(reference, pin)


def issue_native_close(witness, channel):
    """The ORIGINAL root OUTSIDE the unit signs its kernel-authenticated channel.

    Neither terminal booleans nor caller-provided bytes can invoke this bridge.
    The immutable native owner must send the private successful-close handoff;
    the root issuer independently checks original kernel peer/PID/start, unit,
    complete sealed context and actual ledger bytes before reading its secret.
    """
    with _LOCK:
        bridge = _EXIT_BRIDGES.get(witness)
        if (bridge is None or bridge.attempted or bridge.native_attempted or bridge.pid != os.getpid()
                or bridge.thread is not threading.current_thread()):
            raise PermissionError("native-close signing requires the original unconsumed outer root launch witness")
        bridge.native_attempted = True
    policy, state = bridge.policy, bridge.witness_state
    _witness(witness, policy, state=state)  # Checks root observer outside unit/cgroup/mntns.
    if state.attempted:
        raise PermissionError("native-close issuer cannot reuse a consumed outer witness")
    require_provider_origin()  # Refuse before owner-channel IO, durable markers and secret access.
    from .linux_post_exit import _unit, _proc_start, _ledger
    session = policy.session
    properties = _unit(state.unit_name)
    if (properties["InvocationID"] != session["systemd_invocation_id"]
            or properties["MainPID"] != str(session["main_pid"]) or properties["ActiveState"] != "active"
            or properties["SubState"] != "running" or _proc_start(session["main_pid"]) != session["main_start_ticks"]):
        raise PermissionError("native-close kernel peer is not the original live root controller")
    pin = _channel(channel, session["main_pid"])
    reference = os.dup(pin[0])
    try:
        _channel_live(channel, pin, reference, session["main_pid"])
        info = LinuxVolumeOSPorts().path_stat(policy.trust["ledger_path"], kind="file")
        _reserve(policy, "native_close", info.st_dev)
        encoded = _receive_owner(channel, policy, pin, reference, time.monotonic_ns() + 5_000_000_000)
        body = wire.parse(encoded, policy.trust["native_payload_cap_bytes"])
        terminal, identity, _ = wire.decode_native_body(body, policy.trust, session)
        now = _clock(policy, terminal=terminal)
        if not bridge.launch_issued_ns <= body["issued_monotonic_ns"] <= now:
            raise PermissionError("native owner handoff is outside its original signed launch/close epoch")
        data, _ = _ledger(policy.trust["ledger_path"], identity)
        if data != terminal.ledger_bytes:
            raise PermissionError("native owner channel differs from the actual protected closed journal")
        if _proc_start(session["main_pid"]) != session["main_start_ticks"] or _unit(state.unit_name) != properties:
            raise PermissionError("original root controller exited or changed identity during the native owner channel read")
        _unchanged(policy)
        _witness(witness, policy, state=state)
    finally:
        _release_channel_reference(reference, pin)
    body["issued_monotonic_ns"] = _clock(policy, terminal=terminal)
    require_provider_origin()  # Refuse incomplete actual observer closure before reading its secret.
    signed = wire._sign("native_close", body, _protected(NATIVE_SECRET_PATH, 32),
                        policy.trust["native_close_public_key"], policy.trust["native_payload_cap_bytes"])
    _unchanged(policy)
    _witness(witness, policy, state=state)
    _clock(policy, terminal=terminal)
    bridge.native_sha256 = wire.digest(signed)
    return signed


__all__ = ["send_native_close", "issue_native_close"]
