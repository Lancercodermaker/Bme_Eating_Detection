"""Consume the external launcher's sealed native start; never mint a start.

The protected HMAC key authenticates the memfd, not an environment timestamp.
Installed native capture ordering is unproven: refuse before interpreting a
token timestamp or accepting systemd ExecMain as a pre-Python start origin.
The native capped/billed claim and armed deadline producer is missing: refuse
before any persistent write and before issuing live start authority. Root file
permissions alone cannot establish that boundary. This module never installs
approval, opens project inputs, or treats Linux time as host QPC time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
from typing import Any


STUDY_ID = "route2-candidate-overlap-v1-001"
START_FD_ENV = "ROUTE2_PREIMPORT_START_FD"
START_MEMFD_NAME = "route2-preimport-start-v2"
START_HMAC_DOMAIN = b"route2.preimport.start-clock.v2\x00"
START_CLAIM_ROOT = Path("/run/route2-controller/start-clock-claims")
PRODUCTION_POLICY_PATH = f"/etc/route2/{STUDY_ID}-production-controller.seal"
MAX_START_BYTES = 1 << 14
MAX_CLAIM_BYTES = 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_BOOT = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_BODY_FIELDS = frozenset({
    "schema", "study_id", "clock", "origin", "exec_main_start_monotonic_us", "started_monotonic_ns", "config_path",
    "config_sha256", "seal_sha256", "production_policy_sha256", "invocation_id",
    "unit_name", "pid", "process_start_ticks", "boot_id", "time_namespace_device",
    "time_namespace_inode", "nonce", "memfd_device", "memfd_inode",
})
_START_LOCK = threading.Lock()
_FD_TAKEN = False
_CONSUME_ATTEMPTED = False
_ISSUED_START: _IssuedStart | None = None


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate native start token key")
        result[key] = value
    return result


def _require_native_owner() -> None:
    if (sys.platform != "linux" or os.geteuid() != 0
            or threading.current_thread() is not threading.main_thread()):
        raise PermissionError("native start requires the original Linux root main thread")


def _native_identity() -> tuple[int, int, str, int, int]:
    _require_native_owner()
    pid = os.getpid()
    text = Path("/proc/self/stat").read_text(encoding="ascii")
    head, separator, tail = text.rpartition(") ")
    fields = tail.split()
    if (not separator or head.partition(" (")[0] != str(pid)
            or len(fields) < 20 or not fields[19].isdecimal()):
        raise PermissionError("native start process ticks are unavailable")
    ticks = int(fields[19])
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if ticks <= 0 or not _BOOT.fullmatch(boot):
        raise PermissionError("native start boot/process identity is malformed")
    namespace = Path("/proc/self/ns/time").stat()
    manager_namespace = Path("/proc/1/ns/time").stat()
    if (namespace.st_dev, namespace.st_ino) != (manager_namespace.st_dev, manager_namespace.st_ino):
        raise PermissionError("native start CLOCK_MONOTONIC namespace differs from systemd PID 1")
    return pid, ticks, boot, namespace.st_dev, namespace.st_ino


def _require_actual_start_origin() -> None:
    """Refuse until installed native capture ordering has actual authority.

    The installed manager's executable/source and spawn path must be
    independently reviewed and bound to this invocation to prove capture
    before process spawn and Python startup. Alternatively, a trusted native
    producer must capture the original CLOCK_MONOTONIC epoch before launching
    Python and bind it to the process, boot, time namespace and invocation.
    Neither producer is implemented here. A version string, protected policy,
    HMAC, caller boolean or review/installation receipt proves no such ordering;
    an origin before the first Python sample can still omit startup work.
    """
    raise PermissionError(
        "actual native pre-Python start-origin producer is missing: installed "
        "systemd pre-fork timestamp semantics require independent review and "
        "invocation binding, or a trusted native origin before Python launch; "
        "ExecMainStartTimestampMonotonic cannot yet be accepted"
    )


def _systemd_exec_origin(unit_name: str, invocation_id: str) -> int:
    """Require native capture authority before reading PID 1's ExecMain start."""
    _require_actual_start_origin()
    if (type(unit_name) is not str
            or not re.fullmatch(r"route2-[A-Za-z0-9_.@-]{1,220}\.service", unit_name)
            or ".." in unit_name or type(invocation_id) is not str
            or not re.fullmatch(r"[0-9a-f]{32}", invocation_id)):
        raise PermissionError("systemd start requires the exact sealed native unit/invocation")
    # Use the root manager's protected local socket and system helper, with no
    # inherited D-Bus address or executable override. Parent root is trusted.
    for path, socket in ((Path("/usr/bin/systemctl"), False), (Path("/run/systemd/private"), True)):
        for parent in reversed((path.parent, *path.parent.parents)):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
                raise PermissionError("systemd origin has an untrusted helper/socket parent")
        info = path.lstat()
        if (info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or (not stat.S_ISSOCK(info.st_mode) if socket
                    else not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_mode & stat.S_IXUSR)):
            raise PermissionError("systemd origin helper/socket is not the protected native subject")
    if Path("/proc/1/comm").read_text(encoding="ascii").strip() != "systemd":
        raise PermissionError("native monotonic origin is not owned by systemd PID 1")
    expected = {
        "Id": unit_name, "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Type": "exec", "MainPID": str(os.getpid()), "InvocationID": invocation_id,
        "ControlGroup": f"/system.slice/{unit_name}", "Restart": "no", "ProcSubset": "all",
    }
    names = (*expected, "ExecMainStartTimestampMonotonic")
    try:
        completed = subprocess.run(
            ["/usr/bin/systemctl", "--system", "show", "--all", "--no-pager",
             "--property=" + ",".join(names), unit_name],
            capture_output=True, text=True, encoding="ascii", errors="strict",
            timeout=5, check=False, shell=False, close_fds=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PermissionError("native systemd ExecMain origin could not be read") from exc
    if completed.returncode != 0 or type(completed.stdout) is not str or len(completed.stdout) > 4096:
        raise PermissionError("native systemd ExecMain origin is unavailable or oversized")
    properties = {}
    for line in completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if not separator or name not in names or name in properties:
            raise PermissionError("native systemd ExecMain origin has unknown/duplicate properties")
        properties[name] = value
    if set(properties) != set(names) or any(properties[name] != value for name, value in expected.items()):
        raise PermissionError("native systemd unit/PID/invocation differs from the sealed origin")
    if Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines() != [f"0::/system.slice/{unit_name}"]:
        raise PermissionError("native origin controller is outside the original unit cgroup")
    value = properties["ExecMainStartTimestampMonotonic"]
    if not re.fullmatch(r"[0-9]{1,20}", value) or not 0 < int(value) < (1 << 64) - 1:
        raise PermissionError("native systemd ExecMain start is not finite positive integer microseconds")
    # systemd floors CLOCK_MONOTONIC to microseconds. Multiplication retains
    # that lower bound; never round up or use a suspend-inclusive boot clock.
    start_us = int(value)
    if start_us * 1000 > time.clock_gettime_ns(time.CLOCK_MONOTONIC):
        raise PermissionError("native systemd ExecMain start is in a different/future clock epoch")
    return start_us



def take_inherited_start_fd() -> int:
    """Take the descriptor locator once. The locator itself supplies no trust."""
    global _FD_TAKEN
    _require_native_owner()
    with _START_LOCK:
        if _FD_TAKEN:
            raise PermissionError("pre-import start descriptor has already been attempted")
        _FD_TAKEN = True
    value = os.environ.pop(START_FD_ENV, None)
    if type(value) is not str or not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) < 3:
        raise PermissionError("production requires the inherited pre-import start memfd")
    fd = int(value)
    try:
        if not os.get_inheritable(fd):
            raise PermissionError("pre-import start descriptor did not survive exec")
        os.set_inheritable(fd, False)
    except BaseException:
        os.close(fd)
        raise
    return fd


@dataclass(frozen=True, slots=True)
class LinuxStartClockProof:
    invocation_started_monotonic_ns: int
    exec_main_start_monotonic_us: int
    invocation_id: str
    unit_name: str
    config_path: str
    config_sha256: str
    seal_sha256: str
    production_policy_sha256: str
    pid: int
    process_start_ticks: int
    boot_id: str
    time_namespace_device: int
    time_namespace_inode: int
    nonce: str
    token_sha256: str


@dataclass(slots=True)
class _IssuedStart:
    proof: LinuxStartClockProof
    proof_bytes: bytes
    thread: threading.Thread
    claim_path: Path
    claim_device: int
    claim_inode: int
    claim_bytes: bytes
    controller_key_sha256: str
    consumed: bool = False


def _claim_once(proof: LinuxStartClockProof, frozen) -> tuple[Path, int, int, bytes]:
    """No claim write until a fixed native producer owns all prerequisites.

    A future producer must hold/reverify the actual capped control volume,
    physical allocation/billing permission for this complete sealed A+B owner,
    and active original absolute deadlines through write/fsync/cleanup. A
    root-owned directory, JSON size bound or policy bool supplies none of that.
    It must retain per-boot/invocation tombstones, including failed attempts.
    """
    raise PermissionError(
        "native start claim producer is missing: actual capped control capacity, "
        "approved physical billing/complete sealed owner and active original "
        "absolute deadline must be proven before any claim create/write/fsync"
    )


def consume_preimport_start_clock(fd: int, *, config_path: str,
                                 config_sha256: str, seal_sha256: str) -> LinuxStartClockProof:
    """Authenticate the inherited, fully sealed read-only memfd and claim it.

    The bootstrap owns closing fd in every success/failure path. No unverified
    timestamp or serialized proof is accepted as a replacement for this read.
    """
    global _ISSUED_START, _CONSUME_ATTEMPTED
    import fcntl
    from .admission_bootstrap import (
        _read_protected_file, _require_frozen_bindings, parse_supervisor_config, MAX_CONTROLLER_KEY_BYTES,
        MAX_SUPERVISOR_CONFIG_BYTES, MAX_SEALED_ADMISSION_BYTES,
    )
    from .external_admission import load_controller_sealed_admission

    _require_native_owner()
    with _START_LOCK:
        if not _FD_TAKEN or _CONSUME_ATTEMPTED or _ISSUED_START is not None:
            raise PermissionError("native start is absent or already issued")
        _CONSUME_ATTEMPTED = True
        _require_actual_start_origin()
        # Never accept a caller's authentication key as start authority.
        config_bytes = _read_protected_file(config_path, max_bytes=MAX_SUPERVISOR_CONFIG_BYTES)
        config = parse_supervisor_config(config_bytes)
        controller_key = _read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
        admission = _read_protected_file(config.sealed_admission_path, max_bytes=MAX_SEALED_ADMISSION_BYTES)
        if (hashlib.sha256(config_bytes).hexdigest() != config_sha256
                or hashlib.sha256(admission).hexdigest() != seal_sha256):
            raise PermissionError("protected native start configuration/admission changed")
        if type(controller_key) is not bytes or len(controller_key) < 32:
            raise PermissionError("native start requires the protected controller HMAC key")
        seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        info = os.fstat(fd)
        if (type(fd) is not int or fd < 3 or not stat.S_ISREG(info.st_mode)
                or info.st_uid != 0 or info.st_nlink != 0 or stat.S_IMODE(info.st_mode) != 0o400
                or not 0 < info.st_size <= MAX_START_BYTES
                or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
                or fcntl.fcntl(fd, fcntl.F_GET_SEALS) != seals
                or os.readlink(f"/proc/self/fd/{fd}") != f"/memfd:{START_MEMFD_NAME} (deleted)"):
            raise PermissionError("native start descriptor is not the exact sealed read-only memfd")
        encoded = os.pread(fd, MAX_START_BYTES + 1, 0)
        after = os.fstat(fd)
        if (len(encoded) != info.st_size or fcntl.fcntl(fd, fcntl.F_GET_SEALS) != seals
                or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise PermissionError("native start memfd changed while reading")
        try:
            wrapped = json.loads(encoded, object_pairs_hook=_unique_object)
            body, signature = wrapped["body"], wrapped["controller_hmac_sha256"]
            if (type(wrapped) is not dict or set(wrapped) != {"body", "controller_hmac_sha256"}
                    or type(body) is not dict or set(body) != _BODY_FIELDS
                    or _canonical(wrapped) != encoded or type(signature) is not str or not _SHA.fullmatch(signature)
                    or not hmac.compare_digest(signature, hmac.new(controller_key,
                        START_HMAC_DOMAIN + _canonical(body), hashlib.sha256).hexdigest())):
                raise ValueError("native start HMAC/envelope is invalid")
            expected = dict(schema="route2_preimport_start_clock_v2", study_id=STUDY_ID,
                origin="systemd_exec_main",
                clock="CLOCK_MONOTONIC", config_path=config_path, config_sha256=config_sha256,
                seal_sha256=seal_sha256, memfd_device=info.st_dev, memfd_inode=info.st_ino)
            if any(body[name] != value for name, value in expected.items()):
                raise ValueError("native start binds different protected/kernel identities")
            for name in ("started_monotonic_ns", "exec_main_start_monotonic_us", "pid", "process_start_ticks", "time_namespace_inode", "memfd_inode"):
                if type(body[name]) is not int or body[name] <= 0:
                    raise ValueError("native start positive integer is malformed")
            for name in ("time_namespace_device", "memfd_device"):
                if type(body[name]) is not int or body[name] < 0:
                    raise ValueError("native start device is malformed")
            for name in ("config_sha256", "seal_sha256", "production_policy_sha256", "nonce"):
                if type(body[name]) is not str or not _SHA.fullmatch(body[name]):
                    raise ValueError("native start digest/nonce is malformed")
            if (type(body["boot_id"]) is not str or not _BOOT.fullmatch(body["boot_id"])
                    or type(body["invocation_id"]) is not str or not _ID.fullmatch(body["invocation_id"])
                    or type(body["unit_name"]) is not str
                    or not re.fullmatch(r"route2-[A-Za-z0-9_.@-]{1,220}\.service", body["unit_name"])
                    or ".." in body["unit_name"]):
                raise ValueError("native start invocation/boot/unit is malformed")
            if (body["pid"], body["process_start_ticks"], body["boot_id"],
                    body["time_namespace_device"], body["time_namespace_inode"]) != _native_identity():
                raise ValueError("native start is from another process, boot or clock namespace")
            if body["started_monotonic_ns"] > time.clock_gettime_ns(time.CLOCK_MONOTONIC):
                raise ValueError("native start is in the future")
            if (body["exec_main_start_monotonic_us"] != _systemd_exec_origin(body["unit_name"], body["invocation_id"])
                    or body["started_monotonic_ns"] != body["exec_main_start_monotonic_us"] * 1000):
                raise ValueError("native start differs from the original systemd ExecMain microsecond lower bound")
            policy_bytes = _read_protected_file(PRODUCTION_POLICY_PATH, max_bytes=1 << 16)
            if hashlib.sha256(policy_bytes).hexdigest() != body["production_policy_sha256"]:
                raise ValueError("native start production policy changed across exec")
        except (UnicodeError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise PermissionError("pre-import native start is forged, stale or differently bound") from exc
        # Full owner/review/card authorization and frozen path bindings precede
        # any possible persistent claim. A signed clock alone is not approval.
        frozen = load_controller_sealed_admission(admission, controller_key=controller_key,
            expected_source_snapshot_sha256=config.source_snapshot_sha256,
            expected_runtime_snapshot_sha256=config.runtime_snapshot_sha256,
            expected_review_id=config.independent_review_id,
            expected_owner_approval_id=config.owner_approval_id,
            expected_authorization_card_sha256=config.authorization_card_sha256)
        _require_frozen_bindings(config, frozen)
        proof = LinuxStartClockProof(body["started_monotonic_ns"], body["exec_main_start_monotonic_us"], body["invocation_id"], body["unit_name"],
            config_path, config_sha256, seal_sha256, body["production_policy_sha256"], body["pid"],
            body["process_start_ticks"], body["boot_id"], body["time_namespace_device"],
            body["time_namespace_inode"], body["nonce"], hashlib.sha256(encoded).hexdigest())
        claim_path, device, inode, claim_bytes = _claim_once(proof, frozen)
        _ISSUED_START = _IssuedStart(proof, _canonical(asdict(proof)), threading.current_thread(),
                                    claim_path, device, inode, claim_bytes,
                                    hashlib.sha256(controller_key).hexdigest())
        return proof


def _require_live(state: _IssuedStart, *, config_sha256: str, seal_sha256: str) -> LinuxStartClockProof:
    _require_actual_start_origin()
    from .admission_bootstrap import (
        _read_protected_file, parse_supervisor_config, MAX_CONTROLLER_KEY_BYTES,
        MAX_SUPERVISOR_CONFIG_BYTES, MAX_SEALED_ADMISSION_BYTES,
    )

    proof = state.proof
    if (_canonical(asdict(proof)) != state.proof_bytes or threading.current_thread() is not state.thread
            or proof.config_sha256 != config_sha256 or proof.seal_sha256 != seal_sha256
            or (proof.pid, proof.process_start_ticks, proof.boot_id,
                proof.time_namespace_device, proof.time_namespace_inode) != _native_identity()
            or proof.invocation_started_monotonic_ns > time.clock_gettime_ns(time.CLOCK_MONOTONIC)):
        raise PermissionError("original native start proof or live process identity changed")
    if (proof.exec_main_start_monotonic_us != _systemd_exec_origin(proof.unit_name, proof.invocation_id)
            or proof.invocation_started_monotonic_ns != proof.exec_main_start_monotonic_us * 1000):
        raise PermissionError("original native systemd ExecMain epoch changed before A+B")
    config_bytes = _read_protected_file(proof.config_path, max_bytes=MAX_SUPERVISOR_CONFIG_BYTES)
    config = parse_supervisor_config(config_bytes)
    key = _read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
    admission = _read_protected_file(config.sealed_admission_path, max_bytes=MAX_SEALED_ADMISSION_BYTES)
    if (hashlib.sha256(config_bytes).hexdigest() != proof.config_sha256
            or hashlib.sha256(admission).hexdigest() != proof.seal_sha256
            or hashlib.sha256(key).hexdigest() != state.controller_key_sha256):
        raise PermissionError("original protected configuration, admission seal or HMAC key changed before A+B")
    before = state.claim_path.lstat()
    record = _read_protected_file(state.claim_path, max_bytes=MAX_CLAIM_BYTES)
    after = state.claim_path.lstat()
    if (record != state.claim_bytes or (before.st_dev, before.st_ino) != (state.claim_device, state.claim_inode)
            or (after.st_dev, after.st_ino) != (state.claim_device, state.claim_inode)):
        raise PermissionError("original one-shot native start claim was removed or replaced")
    policy = _read_protected_file(PRODUCTION_POLICY_PATH, max_bytes=1 << 16)
    if hashlib.sha256(policy).hexdigest() != proof.production_policy_sha256:
        raise PermissionError("original production invocation policy changed before A+B")
    return proof


def require_preimport_start_clock(proof: LinuxStartClockProof, *, config_sha256: str,
                                 seal_sha256: str) -> LinuxStartClockProof:
    """A copied/deserialized object cannot recreate the live start authority."""
    with _START_LOCK:
        state = _ISSUED_START
        if type(proof) is not LinuxStartClockProof or state is None or state.proof is not proof or state.consumed:
            raise PermissionError("production requires its live unconsumed pre-import start")
        return _require_live(state, config_sha256=config_sha256, seal_sha256=seal_sha256)


def claim_preimport_start_for_ab(proof: LinuxStartClockProof, *, config_sha256: str, seal_sha256: str) -> None:
    """Consume the genuine start before subsequent A+B binding checks."""
    with _START_LOCK:
        state = _ISSUED_START
        if type(proof) is not LinuxStartClockProof or state is None or state.proof is not proof or state.consumed:
            raise PermissionError("A+B native start is missing, forged or already consumed")
        state.consumed = True
        _require_live(state, config_sha256=config_sha256, seal_sha256=seal_sha256)


__all__ = ["LinuxStartClockProof", "require_preimport_start_clock"]
