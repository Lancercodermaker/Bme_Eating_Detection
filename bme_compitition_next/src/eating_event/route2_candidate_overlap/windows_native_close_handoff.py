"""Windows public-trust reader and signature verification bridge.

The fixed trust filename beside the pinned interpreter must be installed on a read-only local volume
by the trusted host owner. No caller path, supplied key, policy digest or public
approval flag substitutes for that installation. This bridge performs reads
only and neither installs the trust nor writes an acceptance anchor.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import stat
import sys
import threading

from . import native_close_handoff as wire
from .contracts import STUDY_ID
from .windows_control_identity import _Win32, _report_cleanup_errors


TRUST_FILENAME = f"{STUDY_ID}-native-close-trust.json"


def require_provider_origin():
    """Require the ORIGINAL wall owner's held full readonly execution closure."""
    from .windows_wall import _INVOCATIONS
    from .windows_control_identity import _LEASES
    states = [state for state in tuple(_INVOCATIONS.values()) if state.pid == os.getpid()
              and state.thread() is threading.current_thread() and state.lease is not None
              and not state.cleanup_attempted and state.trust_bytes is not None]
    if len(states) != 1:
        raise PermissionError("provider verification requires one original held host wall invocation")
    state = states[0]
    state.lease.require_live_identity()
    held = _LEASES.get(state.lease)
    if held is None or held.closed:
        raise PermissionError("provider origin has no original immutable host runtime lease")
    return held.root.resolve(strict=True)


def load_installed_trust():
    if sys.platform != "win32":
        raise PermissionError("installed host public trust requires Windows")
    executable = Path(sys.executable)
    if not executable.is_absolute() or ".." in executable.parts:
        raise PermissionError("host trust requires the original pinned absolute interpreter path")
    # The calling wall owner checks this interpreter's complete held execution
    # lease first. This file must be included in that same immutable manifest.
    path = executable.parent / TRUST_FILENAME
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise PermissionError("installed host trust path/ancestor is a reparse point")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= wire.MAX_TRUST_BYTES:
        raise PermissionError("installed host public trust is not a bounded single-link regular file")
    win, owned = _Win32(), []
    primary = None
    try:
        parent = win.open_owned_readonly(owned, path.parent, directory=True)
        volume = win.readonly_volume(parent)
        descriptor = win.open_owned_readonly(owned, path)
        expected = win.path(parent).rstrip("\\") + "\\" + path.name
        if win.readonly_volume(descriptor) != volume or win.path(descriptor).lower() != expected.lower():
            raise PermissionError("host public trust escaped its held readonly installation directory")
        chunks, count = [], 0
        while True:
            maximum = min(4096, wire.MAX_TRUST_BYTES + 1 - count)
            buffer, read = ctypes.create_string_buffer(maximum), ctypes.c_uint32()
            if not win.kernel.ReadFile(descriptor, buffer, maximum, ctypes.byref(read), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not 0 <= read.value <= maximum:
                raise PermissionError("invalid native host trust read count")
            if not read.value:
                break
            chunks.append(buffer.raw[:read.value])
            count += read.value
            if count > wire.MAX_TRUST_BYTES:
                raise PermissionError("installed host public trust exceeds its byte cap")
        encoded = b"".join(chunks)
        if (len(encoded) != info.st_size or win.readonly_volume(parent) != volume
                or win.readonly_volume(descriptor) != volume or win.path(descriptor).lower() != expected.lower()):
            raise PermissionError("installed host trust identity changed during its held read")
        trust = wire.parse(encoded, wire.MAX_TRUST_BYTES)
        wire.validate_trust(trust)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        failures = []
        while owned:
            handle = owned.pop()
            try:
                win.close(handle)
            except BaseException as exc:
                failures.append(exc)
        _report_cleanup_errors(primary, failures, "host public trust read failed during consumed handle cleanup")
    return trust, encoded


def _observer(value, session):
    wire._exact(value, {"pid", "membership", "namespaces", "start_ticks", "native_tid", "task_start_ticks"})
    for name in ("pid", "start_ticks", "native_tid", "task_start_ticks"):
        wire._integer(value[name])
    from pathlib import PurePosixPath
    membership = value["membership"]
    group = "/system.slice/" + session["unit_name"]
    if (type(membership) is not str or not PurePosixPath(membership).is_absolute()
            or PurePosixPath(membership).as_posix() != membership or ".." in PurePosixPath(membership).parts
            or membership == group or membership.startswith(group + "/") or value["pid"] == session["main_pid"]):
        raise PermissionError("signed Linux observer lacks the independent original process/cgroup identity")
    namespaces = value["namespaces"]
    if type(namespaces) is not list or len(namespaces) != 3:
        raise PermissionError("signed Linux observer namespace identities are incomplete")
    for pair in namespaces:
        if type(pair) is not list or len(pair) != 2:
            raise PermissionError("signed Linux observer namespace inode identity is invalid")
        wire._integer(pair[0], minimum=0)
        wire._integer(pair[1])


def verify_launch(encoded, trust, *, nonce, started_ticks, frequency):
    body = wire.verify(encoded, "linux_launch", trust["linux_exit_public_key"], trust["exit_payload_cap_bytes"])
    wire._exact(body, {"context", "observer", "issued_monotonic_ns"})
    wire._exact(body["context"], {"trust_sha256", "session"})
    session = wire.validate_session(body["context"]["session"])
    wire._require_context(body["context"], trust, session)
    if (session["host_nonce"] != nonce or session["external_started_ticks"] != started_ticks
            or session["qpc_frequency"] != frequency):
        raise PermissionError("signed Linux launch is for a different original native QPC invocation/challenge")
    _observer(body["observer"], session)
    issued = wire._integer(body["issued_monotonic_ns"])
    limits = wire.validate_trust(trust)
    if not session["invocation_started_monotonic_ns"] <= issued <= session["invocation_started_monotonic_ns"] + limits.total_wall_ns:
        raise PermissionError("signed original-unit launch is outside the protected Linux wall frame")
    return body


def verify_pair(native_bytes, exit_bytes, trust, launch):
    session = launch["context"]["session"]
    terminal, _, native_body = wire.decode_native(native_bytes, trust, session)
    body = wire.verify(exit_bytes, "linux_exit", trust["linux_exit_public_key"], trust["exit_payload_cap_bytes"])
    wire._exact(body, {"context", "observer", "native_handoff_sha256", "observation", "issued_monotonic_ns"})
    wire._require_context(body["context"], trust, session)
    if (body["observer"] != launch["observer"] or wire.canonical(body["observer"]) != wire.canonical(launch["observer"])
            or body["native_handoff_sha256"] != wire.digest(native_bytes)
            or native_body["issued_monotonic_ns"] < launch["issued_monotonic_ns"]):
        raise PermissionError("signed exit is not from the original captured observer/native-close handoff")
    wire.require_observation(body["observation"], terminal, session)
    issued = wire._integer(body["issued_monotonic_ns"])
    if (issued < body["observation"]["observed_monotonic_ns"]
            or body["observation"]["observed_monotonic_ns"] < native_body["issued_monotonic_ns"]
            or (terminal.status != "INCOMPLETE_RESOURCE" and issued > terminal.deadline_monotonic_ns)):
        raise PermissionError("signed Linux exit issuance is outside the original monotonic close/exit frame")
    return terminal, body["observation"]


def wall_policy(trust):
    return {"total_wall_ns": wire.validate_trust(trust).total_wall_ns,
            "anchor_payload_cap_bytes": trust["anchor_payload_cap_bytes"],
            "full_ab_seal_sha256": trust["full_ab_seal_sha256"],
            "budget_policy_sha256": trust["budget_policy_sha256"],
            "handoff_trust_sha256": wire.digest(wire.canonical(trust))}


__all__ = []
