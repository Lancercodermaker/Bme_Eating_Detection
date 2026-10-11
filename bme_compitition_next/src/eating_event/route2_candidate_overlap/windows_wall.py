"""Native Windows QPC and durable outer wall anchors, without a study CLI.

QPC starts before host identity validation/WSL launch. Real file and volume
flushes bracket the final anchor. Linux handoff requires installed public trust
and both original signatures. The separately capped host-control installation
gate still refuses before any write; a dict alone cannot become acceptance.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import weakref

from .linux_enforcement import canonical_receipt_bytes, verify_post_exit_receipt
from .linux_supervisor import ExternalExitObservation
from .windows_control_identity import WindowsReadonlyExecutionLease, _Win32, _report_cleanup_errors


_INVOCATIONS = weakref.WeakKeyDictionary()
_INITIALIZED_INVOCATIONS = weakref.WeakSet()
_INITIALIZATION_LOCK = threading.Lock()


def _qpc(kernel):
    kernel.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
    kernel.QueryPerformanceFrequency.restype = ctypes.c_int
    kernel.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
    kernel.QueryPerformanceCounter.restype = ctypes.c_int
    frequency, counter = ctypes.c_longlong(), ctypes.c_longlong()
    if not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)) or not kernel.QueryPerformanceCounter(ctypes.byref(counter)):
        raise ctypes.WinError(ctypes.get_last_error())
    if frequency.value <= 0 or counter.value <= 0:
        raise PermissionError("native host QPC is not a positive clock sample")
    return counter.value, frequency.value


def _flush(kernel, handle):
    kernel.FlushFileBuffers.argtypes = [ctypes.c_void_p]
    kernel.FlushFileBuffers.restype = ctypes.c_int
    if not kernel.FlushFileBuffers(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _burn_and_close(state, primary):
    state.attempted = True
    try:
        _close_execution(state)
    except BaseException as cleanup:
        _report_cleanup_errors(primary, (cleanup,), "outer QPC operation and execution cleanup failed")


def _durable_create(kernel, path, data, volume_handle, *, maximum):
    """Exclusive write/readback plus volume flush; never mkdir or overwrite.

    A volume handle with GENERIC_WRITE must have been acquired by the installed
    privileged host controller. File flush alone is insufficient evidence for
    durable newly created namespace entries here.
    """
    if type(data) is not bytes or type(maximum) is not int or not 0 < len(data) <= maximum:
        raise PermissionError("host wall anchor exceeds its explicitly approved payload cap")
    handle = kernel.CreateFileW(str(path), 0xC0000000, 1, None, 1,
                               0x80000000 | 0x00200000, None)  # CREATE_NEW, WRITE_THROUGH, OPEN_REPARSE_POINT
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    primary = None
    try:
        kernel.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        kernel.WriteFile.restype = ctypes.c_int
        offset = 0
        while offset < len(data):
            value = data[offset:offset + 65536]
            buffer, count = ctypes.create_string_buffer(value), ctypes.c_uint32()
            if not kernel.WriteFile(handle, buffer, len(value), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not 0 < count.value <= len(value):
                raise OSError("invalid or zero host wall anchor write")
            offset += count.value
        _flush(kernel, handle)
        _flush(kernel, volume_handle)
        if not kernel.SetFilePointerEx(handle, 0, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        buffer, count = ctypes.create_string_buffer(len(data) + 1), ctypes.c_uint32()
        if not kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value != len(data) or buffer.raw[:count.value] != data:
            raise PermissionError("durable host wall anchor readback differs from its exact written bytes")
        return hashlib.sha256(data).hexdigest()
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as cleanup:
            _report_cleanup_errors(primary, (cleanup,),
                                   "host anchor operation failed during consumed handle cleanup")


def _require_authenticated_linux_handoff(state, native_close_bytes, linux_exit_bytes, policy):
    from .windows_native_close_handoff import load_installed_trust, verify_pair, wall_policy
    from .native_close_handoff import canonical
    if state.trust_bytes is None or state.launch is None:
        raise PermissionError("signed handoff requires installed public trust and the original active-unit launch pin")
    trust, encoded = load_installed_trust()
    expected_policy = wall_policy(trust)
    if (encoded != state.trust_bytes or type(policy) is not dict or policy != expected_policy
            or canonical(policy) != canonical(expected_policy)):
        raise PermissionError("outer wall policy differs from the original installed full-seal/budget trust")
    terminal, linux_exit = verify_pair(native_close_bytes, linux_exit_bytes, trust, state.launch)
    # Signature verification loads the provider; its entire Python/native closure
    # must also satisfy the held execution identity before any anchor write.
    state.lease.require_live_identity()
    return terminal, linux_exit


def _require_host_control_boundary(policy, root, kernel):
    """Must return held protected directory/volume handles after actual OS proof.

    A logical JSON length limit, free-space snapshot, directory ACL assertion or
    unverified policy digest cannot establish the physical control-volume cap.
    """
    raise PermissionError("separately hard-capped host control volume and protected policy installation proof is missing")


@dataclass(slots=True)
class _Invocation:
    started_ticks: int
    frequency: int
    kernel: object
    pid: int
    thread: object
    nonce: str
    lease: object = None
    trust_bytes: bytes | None = None
    launch: dict | None = None
    attempted: bool = False
    cleanup_attempted: bool = False
    finalizer: object = None


def _abandon_invocation(state):
    """Release its original held lease without creating a wall observation."""
    if state.pid != os.getpid() or state.cleanup_attempted:
        return
    state.attempted = state.cleanup_attempted = True
    if state.lease is not None:
        from .windows_control_identity import _LEASES, _abandon_held_execution
        _abandon_held_execution(_LEASES.get(state.lease))


def _close_execution(state):
    if state.cleanup_attempted:
        return
    state.cleanup_attempted = True
    if state.lease is not None:
        state.lease.close()


class WindowsQpcWallInvocation:
    """One actual outer clock epoch; persist only after authenticated unit exit.

    Construct first in the installed outer launcher, then hold/validate the
    complete host execution lease and record WSL launch. No timestamp argument
    or public bool can replace the original native QPC start.
    """

    def __init__(self):
        with _INITIALIZATION_LOCK:
            if type(self) is not WindowsQpcWallInvocation or self in _INITIALIZED_INVOCATIONS:
                raise PermissionError("outer QPC initialization may be attempted only once")
            _INITIALIZED_INVOCATIONS.add(self)
        if sys.platform != "win32":
            raise PermissionError("outer QPC invocation requires Windows")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        started, frequency = _qpc(kernel)
        state = _Invocation(started, frequency, kernel, os.getpid(), weakref.ref(threading.current_thread()),
                            os.urandom(32).hex())
        _INVOCATIONS[self] = state
        try:
            state.finalizer = weakref.finalize(self, _abandon_invocation, state)
        except BaseException:
            state.attempted = state.cleanup_attempted = True
            raise

    def _state(self):
        state = _INVOCATIONS.get(self)
        if (state is None or state.attempted or state.pid != os.getpid()
                or state.thread() is not threading.current_thread()):
            raise PermissionError("outer QPC invocation is absent, consumed or in a different execution identity")
        try:
            ticks, frequency = _qpc(state.kernel)
            if ticks < state.started_ticks or frequency != state.frequency:
                raise PermissionError("native outer QPC identity drifted")
        except BaseException as primary:
            # Only the original PID/thread may consume this epoch. A failed
            # native clock sample must burn it and close the held lease before
            # callers enter their own try/finally blocks.
            state.attempted = True
            try:
                _close_execution(state)
            except BaseException as cleanup:
                error = PermissionError("native outer QPC failed and held execution cleanup also failed")
                error.clock_error, error.cleanup_error = primary, cleanup
                raise error from primary
            raise
        return state

    def bind_host_identity(self, *, snapshot_root, manifest_bytes, expected_manifest_sha256):
        state = self._state()
        try:
            if state.lease is not None:
                raise PermissionError("outer clock requires exactly one complete held host execution lease")
            # Own construction after the native QPC start; accepting an
            # already hashed lease would exclude its initial work from wall.
            lease = WindowsReadonlyExecutionLease(snapshot_root, manifest_bytes, expected_manifest_sha256)
            state.lease = lease
            lease.require_live_identity()
            from .windows_native_close_handoff import load_installed_trust
            _, state.trust_bytes = load_installed_trust()
            lease.require_live_identity()
        except BaseException as primary:
            _burn_and_close(state, primary)
            raise
        return state.started_ticks, state.frequency

    def handoff_challenge(self):
        """Bytes for the protected launcher session, from this actual QPC epoch.

        This challenge is freshness data, never an approval or launch receipt.
        The installed bridge must transmit it before Linux launch is pinned.
        """
        state = self._state()
        try:
            if state.lease is None or state.trust_bytes is None or state.launch is not None:
                raise PermissionError("handoff challenge requires the held installed identity before launch pinning")
            state.lease.require_live_identity()
            from .native_close_handoff import canonical
            return canonical({"host_nonce": state.nonce, "external_started_ticks": state.started_ticks,
                              "qpc_frequency": state.frequency})
        except BaseException as primary:
            _burn_and_close(state, primary)
            raise

    def bind_linux_launch(self, signed_launch_bytes):
        """Pin once the signed original unit captured by the outer Linux witness."""
        state = self._state()
        try:
            if state.lease is None or state.trust_bytes is None or state.launch is not None:
                raise PermissionError("outer QPC requires exactly one authenticated active-unit launch pin")
            state.lease.require_live_identity()
            from .windows_native_close_handoff import load_installed_trust, verify_launch
            trust, encoded = load_installed_trust()
            if encoded != state.trust_bytes:
                raise PermissionError("installed public trust changed after original host identity binding")
            launch = verify_launch(signed_launch_bytes, trust, nonce=state.nonce,
                                  started_ticks=state.started_ticks, frequency=state.frequency)
            state.lease.require_live_identity()
            ticks, frequency = _qpc(state.kernel)
            deadline = state.started_ticks + (trust["limits"]["total_wall_ns"] * state.frequency + 999_999_999) // 1_000_000_000
            if frequency != state.frequency or ticks < state.started_ticks or ticks > deadline:
                raise PermissionError("active-unit handoff verification exceeded the original native QPC wall frame")
            state.launch = launch
        except BaseException as primary:
            _burn_and_close(state, primary)
            raise

    def persist_after_exit(self, *, terminal, linux_exit, policy, control_root):
        """Produce ExternalExitObservation after final file/volume flush.

        The final QPC observation includes identity checks, readback, final seal
        creation and volume flush. receipt_fsynced_ticks describes the actual
        core flush; it cannot stand in for the later final-anchor observation.
        Signature and host-control installation gates are checked before writing.
        terminal/linux_exit must be their bounded signed wire bytes.
        """
        state = self._state()
        state.attempted = True
        primary = None
        try:
            return self._persist_owned(state, terminal=terminal, linux_exit=linux_exit,
                                       policy=policy, control_root=control_root)
        except BaseException as exc:
            primary = exc
            raise
        finally:
            # Missing proof gates and early exceptions still consume and close
            # the original held runtime; cleanup never manufactures acceptance.
            try:
                _close_execution(state)
            except BaseException as cleanup:
                _report_cleanup_errors(primary, (cleanup,), "outer persistence failed during execution cleanup")

    def _persist_owned(self, state, *, terminal, linux_exit, policy, control_root):
        if state.lease is None:
            raise PermissionError("outer receipt requires the original held identity")
        state.lease.require_live_identity()
        terminal, linux_exit = _require_authenticated_linux_handoff(state, terminal, linux_exit, policy)
        root = Path(control_root)
        if not root.is_absolute() or ".." in root.parts:
            raise PermissionError("host control root must be its exact protected absolute path")
        win = _Win32()
        held_root, held_volume = _require_host_control_boundary(policy, root, win.kernel)
        primary = None
        try:
            if (type(policy) is not dict or type(policy.get("total_wall_ns")) is not int
                    or policy["total_wall_ns"] <= 0 or type(policy.get("anchor_payload_cap_bytes")) is not int
                    or not 0 < policy["anchor_payload_cap_bytes"] <= 65536):
                raise PermissionError("outer wall policy has no explicit approved wall and payload limits")
            if (type(linux_exit) is not dict or linux_exit.get("unit_name") != terminal.unit_name
                    or linux_exit.get("terminal_sha256") != terminal.terminal_sha256
                    or linux_exit.get("unit_result") != "success" or linux_exit.get("exit_status") != 0
                    or linux_exit.get("active_state") != "inactive" or linux_exit.get("cgroup_empty") is not True
                    or linux_exit.get("terminal_reverified") is not True
                    or type(linux_exit.get("observed_monotonic_ns")) is not int):
                raise PermissionError("authenticated Linux exit witness is incomplete")
            terminal_seen, frequency = _qpc(state.kernel)
            inactive_seen, inactive_frequency = _qpc(state.kernel)
            if frequency != state.frequency or inactive_frequency != state.frequency:
                raise PermissionError("host QPC frequency drifted after actual Linux exit")
            total_wall = policy["total_wall_ns"]
            deadline = state.started_ticks + (total_wall * state.frequency + 999_999_999) // 1_000_000_000
            if terminal.status != "INCOMPLETE_RESOURCE" and inactive_seen > deadline:
                raise PermissionError("authenticated service exit arrived after the outer wall deadline")
            core = dict(schema="route2_post_exit_receipt_v1", invocation_id=terminal.invocation_id,
                unit_name=terminal.unit_name, terminal_sha256=terminal.terminal_sha256,
                unit_result="success", exit_status=0, active_state="inactive",
                invocation_started_ns=terminal.invocation_started_monotonic_ns,
                terminal_closed_ns=terminal.terminal_closed_monotonic_ns, deadline_ns=terminal.deadline_monotonic_ns,
                external_clock="windows_qpc", qpc_frequency=state.frequency,
                external_started_ticks=state.started_ticks, external_terminal_detected_ticks=terminal_seen,
                external_unit_inactive_ticks=inactive_seen, external_deadline_ticks=deadline)
            # Hash-derived names cannot escape the protected control directory.
            name = hashlib.sha256(terminal.invocation_id.encode("utf-8")).hexdigest()
            core_sha = _durable_create(win.kernel, root / (name + ".core.json"), canonical_receipt_bytes(core),
                                       held_volume, maximum=policy["anchor_payload_cap_bytes"])
            core_fsynced, frequency = _qpc(state.kernel)
            if frequency != state.frequency:
                raise PermissionError("QPC frequency changed after durable core flush")
            seal = dict(schema="route2_windows_qpc_wall_seal_v1", invocation_id=terminal.invocation_id,
                core_sha256=core_sha, external_receipt_fsynced_ticks=core_fsynced,
                execution_manifest_sha256=state.lease.require_live_identity(),
                linux_exit_sha256=hashlib.sha256(canonical_receipt_bytes(linux_exit)).hexdigest())
            _durable_create(win.kernel, root / (name + ".seal.json"), canonical_receipt_bytes(seal),
                            held_volume, maximum=policy["anchor_payload_cap_bytes"])
            receipt = {**core, "durable_external_event": True, "external_receipt_fsynced_ticks": core_fsynced}
        except BaseException as exc:
            primary = exc
            raise
        finally:
            failures = []
            for handle in (held_volume, held_root):
                try:
                    win.close(handle)
                except BaseException as exc:
                    failures.append(exc)
            _report_cleanup_errors(primary, failures, "outer persistence failed during control handle cleanup")
        # Include both volume/directory handle closes and complete live host
        # identity verification in the final native QPC acceptance sample.
        state.lease.require_live_identity()
        before_cleanup_ticks, frequency = _qpc(state.kernel)
        if frequency != state.frequency:
            raise PermissionError("QPC frequency changed after final durable anchor, cleanup and identity checks")
        verify_post_exit_receipt(receipt, invocation_id=terminal.invocation_id, unit_name=terminal.unit_name,
            terminal_sha256=terminal.terminal_sha256, observed_monotonic_ns=linux_exit["observed_monotonic_ns"],
            observed_external_ticks=before_cleanup_ticks, total_wall_ns=total_wall, terminal_status=terminal.status,
            expected_qpc_frequency=state.frequency, expected_external_started_ticks=state.started_ticks)
        # Keep identity held through complete receipt verification, then
        # consume every execution handle before the final deadline sample.
        _close_execution(state)
        observed_ticks, frequency = _qpc(state.kernel)
        if (frequency != state.frequency or observed_ticks < before_cleanup_ticks
                or (terminal.status != "INCOMPLETE_RESOURCE" and observed_ticks > deadline)):
            raise PermissionError("final host verification and complete lease teardown exceeded the outer wall deadline")
        return ExternalExitObservation(terminal.invocation_id, terminal.unit_name, True, True, True, True,
            receipt, linux_exit["observed_monotonic_ns"], observed_ticks, state.frequency, state.started_ticks)

    def close(self):
        """Cancel once before persistence, using only original private owner pins."""
        state = _INVOCATIONS.get(self)
        if (state is None or state.pid != os.getpid() or state.thread() is not threading.current_thread()
                or state.cleanup_attempted):
            raise PermissionError("outer clock cancellation is absent or already consumed")
        state.attempted = True
        _close_execution(state)


__all__ = ["WindowsQpcWallInvocation"]
