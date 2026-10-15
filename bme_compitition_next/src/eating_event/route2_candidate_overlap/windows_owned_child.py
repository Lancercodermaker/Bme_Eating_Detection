"""Private FFI for the native C02 owned-child component; no DLL loader.

An upstream owner must establish permission, the original lease/deadlines and
the complete immutable loaded image closure before constructing this binding.
Accepting a loaded image and raw intent does not verify those obligations.
The public preparation entry continues to refuse while that producer is absent.
All original Job/process/thread HANDLEs stay in C, including after a foreign
result-conversion exception. Keep this object/library strongly held on residual.
"""

from __future__ import annotations

import ctypes as _c
import sys as _sys
from types import MappingProxyType as _MappingProxyType

_U32, _U64, _I64 = _c.c_uint32, _c.c_uint64, _c.c_int64
_OK, _PENDING, _EXITED, _NEEDS_CLEANUP = 1, 2, 3, 4
_FINISHED, _RESIDUAL, _BUSY = 5, 6, 9
_DONE, _RETAINED = 9, 10


class _U32Fact(_c.Structure):
    _fields_ = [("value", _U32), ("state", _U32)]


class _U64Fact(_c.Structure):
    _fields_ = [("value", _U64), ("state", _U32), ("reserved", _U32)]


class _I64Fact(_c.Structure):
    _fields_ = [("value", _I64), ("state", _U32), ("reserved", _U32)]


class _Snapshot(_c.Structure):
    _fields_ = [(name, _U32) for name in (
        "limits_readback_state", "cpu_readback_state", "accounting_state", "reserved")]
    _fields_ += [("limit_flags", _U32Fact), ("active_process_limit", _U32Fact)]
    _fields_ += [(name, _U64Fact) for name in (
        "affinity", "job_commit_limit", "process_commit_limit", "peak_process_commit", "peak_job_commit")]
    _fields_ += [("cpu_control_flags", _U32Fact), ("cpu_rate", _U32Fact)]
    _fields_ += [(name, _I64Fact) for name in (
        "total_user_100ns", "total_kernel_100ns", "period_user_100ns", "period_kernel_100ns")]
    _fields_ += [(name, _U32Fact) for name in (
        "page_faults", "total_processes", "active_processes", "terminated_by_limits")]


class _Text(_c.Structure):
    _fields_ = [("text", _c.POINTER(_c.c_uint16)), ("units", _U32), ("reserved", _U32)]


class _Spec(_c.Structure):
    _fields_ = [("abi", _U32), ("size", _U32)]
    _fields_ += [(name, _I64) for name in (
        "lease_epoch_qpc", "lease_qpc_frequency", "stop_deadline_qpc", "cleanup_deadline_qpc")]
    _fields_ += [("intent_serial", _U64)]
    _fields_ += [(name, _Text) for name in (
        "application", "command_line", "current_directory", "environment")]


class _Fault(_c.Structure):
    _fields_ = [(name, _U32) for name in (
        "operation", "kind", "code", "win32_error", "win32_error_valid", "occurrences")]


class _HandleState(_c.Structure):
    _fields_ = [(name, _U32) for name in ("acquired", "consumed", "close_state", "reserved")]


class _Report(_c.Structure):
    _fields_ = [(name, _U32) for name in (
        "abi", "size", "status", "lifecycle",
        "attempt_consumed", "stop_new", "birth_attempted", "resume_attempted",
        "finish_started", "membership", "process_signaled", "thread_signaled",
        "job_empty", "final_complete", "residual_bits", "fault_count",
        "configured_valid", "latest_valid", "final_valid", "clock_valid",
        "creator_pid", "creator_tid", "child_pid", "child_tid",
        "terminate_job_state", "terminate_process_state", "attribute_initialized", "attribute_deleted",
        "thread_scan_state", "thread_scan_entries", "parent_threads", "child_threads",
        "thread_live_at_both_polls", "thread_warning_limit", "thread_transient_coverage", "complete_birth_history")]
    _fields_ += [("intent_serial", _U64)]
    _fields_ += [(name, _I64) for name in (
        "lease_epoch_qpc", "qpc_frequency", "context_observed_qpc", "stop_deadline_qpc", "cleanup_deadline_qpc", "last_qpc")]
    _fields_ += [(name, _U64Fact) for name in (
        "creator_creation_100ns", "child_creation_100ns", "primary_creation_100ns",
        "final_exit_100ns", "final_kernel_100ns", "final_user_100ns",
        "final_thread_kernel_100ns", "final_thread_user_100ns")]
    _fields_ += [(name, _U32Fact) for name in (
        "final_exit_code", "wait_before", "wait_after", "thread_wait", "processor_groups", "processor_count")]
    _fields_ += [(name, _U64Fact) for name in ("allowed_affinity", "system_affinity", "selected_affinity")]
    _fields_ += [(name, _HandleState) for name in ("creator", "job", "process", "thread", "snapshot")]
    _fields_ += [("primary", _Fault), ("faults", _Fault * 64)]
    _fields_ += [(name, _Snapshot) for name in ("configured", "latest", "final_sample")]


class _ABI(_c.Structure):
    _fields_ = [(name, _U32) for name in (
        "abi", "size", "spec_size", "report_size", "pointer_size", "text_size",
        "fault_size", "handle_state_size", "snapshot_size", "report_faults_offset",
        "report_configured_offset", "reserved")]


class _RawChildIntent:
    """Copied raw inputs; this type is not a verified lease or an approval."""

    __slots__ = ("values",)

    def __init__(self, *, application, command_line, current_directory, environment,
                 lease_epoch_qpc, lease_qpc_frequency, stop_deadline_qpc,
                 cleanup_deadline_qpc, intent_serial=0):
        for value in (application, command_line, current_directory, environment):
            if type(value) is not str:
                raise TypeError("raw child text must be exact str")
        numbers = (lease_epoch_qpc, lease_qpc_frequency, stop_deadline_qpc, cleanup_deadline_qpc)
        if any(type(value) is not int or not 0 < value <= (1 << 63) - 1 for value in numbers):
            raise ValueError("raw original QPC values must be positive signed64")
        if not lease_epoch_qpc < stop_deadline_qpc < cleanup_deadline_qpc:
            raise ValueError("raw original deadlines must remain ordered")
        if type(intent_serial) is not int or not 0 <= intent_serial <= (1 << 64) - 1:
            raise ValueError("raw serial must fit uint64")
        self.values = (application, command_line, current_directory, environment,
            lease_epoch_qpc, lease_qpc_frequency, stop_deadline_qpc, cleanup_deadline_qpc, intent_serial)


def _utf16(value, *, environment=False, command=False):
    if environment:
        if not value.endswith("\0\0") or "\0\0" in value[:-2]:
            raise ValueError("raw environment needs exactly one terminal double NUL")
    else:
        if "\0" in value:
            raise ValueError("raw path/command contains NUL")
        value += "\0"
    data = value.encode("utf-16-le", errors="strict")
    units = len(data) // 2
    if units > (32767 if command else 32768):
        raise ValueError("raw owned-child text exceeds native fixed capacity")
    return (_c.c_uint16 * units).from_buffer_copy(data)


class _LoadedOwnedChild:
    """Retained native addresses from an ALREADY loaded image, never a loader.

    The image's authenticity and preload permission are upstream obligations.
    The descriptor proves only layout agreement. No caller callback/table of
    arbitrary Python functions is accepted. Exports resolve from the exact
    ctypes library object's existing native handle, rather than its attributes.
    """

    __slots__ = ("_library", "_library_handle", "_calls", "_report", "_spec",
                 "_buffers", "_begin_attempted", "_drifted", "_error", "_abi",
                 "_source_lease", "_private_window")

    def __init__(self, loaded_library, raw_intent):
        if _sys.platform != "win32" or _c.sizeof(_c.c_void_p) != 8:
            raise PermissionError("owned-child binding requires native Windows x64")
        if type(loaded_library) not in (_c.CDLL, _c.WinDLL) or not loaded_library._handle:
            raise TypeError("an already loaded original ctypes native image is required")
        if type(raw_intent) is not _RawChildIntent:
            raise TypeError("exact raw intent required; it is not lease verification")
        self._library, self._library_handle = loaded_library, loaded_library._handle
        self._report, self._spec, self._abi = _Report(), _Spec(), _ABI()
        self._begin_attempted, self._drifted = False, False
        self._error = PermissionError("original owned-child native ABI/binding or lifecycle failed")
        declarations = {
            "describe": (_c.POINTER(_ABI), _c.c_size_t),
            "begin_once": (_c.POINTER(_Spec), _c.c_size_t),
            "birth_suspended_once": (), "resume_once": (), "observe_step": (),
            "stop_new": (), "finish_step": (),
            "copy_report": (_c.POINTER(_Report), _c.c_size_t),
        }
        calls = {}
        for name, arguments in declarations.items():
            lookup = loaded_library["route2_win_owned_child_" + name + "_v1"]
            lookup.restype, lookup.argtypes = _U32, arguments
            address = _c.cast(lookup, _c.c_void_p).value
            if not address:
                raise self._error
            fixed = _c.CFUNCTYPE(_U32, *arguments)(address)
            calls[name] = (lookup, fixed, address, arguments, type(lookup), type(fixed), lookup._flags_, fixed._flags_)
        self._calls = _MappingProxyType(calls)
        if _ORIGINAL_DISPATCH["_call"](self, "describe", _c.byref(self._abi), _c.sizeof(self._abi)) != _OK:
            raise self._error
        expected = (1, _c.sizeof(_ABI), _c.sizeof(_Spec), _c.sizeof(_Report), 8,
            _c.sizeof(_Text), _c.sizeof(_Fault), _c.sizeof(_HandleState), _c.sizeof(_Snapshot),
            _Report.faults.offset, _Report.configured.offset, 0)
        if tuple(getattr(self._abi, name) for name, _ in _ABI._fields_) != expected:
            raise self._error
        if _c.sizeof(_Spec) != 112 or _c.sizeof(_Text) != 16:
            raise self._error
        application, command, directory, environment, epoch, frequency, stop, cleanup, serial = raw_intent.values
        self._source_lease = (epoch, frequency, stop, cleanup)
        self._private_window = None
        self._buffers = (_utf16(application), _utf16(command, command=True),
            _utf16(directory), _utf16(environment, environment=True))
        self._spec.abi, self._spec.size = 1, _c.sizeof(self._spec)
        self._spec.lease_epoch_qpc, self._spec.lease_qpc_frequency = epoch, frequency
        self._spec.stop_deadline_qpc, self._spec.cleanup_deadline_qpc = stop, cleanup
        self._spec.intent_serial = serial
        for name, buffer in zip(("application", "command_line", "current_directory", "environment"), self._buffers):
            setattr(self._spec, name, _Text(_c.cast(buffer, _c.POINTER(_c.c_uint16)), len(buffer), 0))

    @property
    def report(self):
        return self._report

    @property
    def begin_attempted(self):
        return self._begin_attempted

    @property
    def drifted(self):
        """Sticky incompleteness, including safely restored cleanup ABI drift."""
        return self._drifted

    @property
    def source_lease(self):
        """Original supplied raw values; these are not native lease attestation."""
        return self._source_lease

    @property
    def private_window(self):
        return self._private_window

    def restrict_private_window_once(self, start, frequency):
        """Existing non-E monitor's single stricter 60/70s subwindow.

        The caller samples start ONCE. Never choose another now or extend an
        original source deadline. Native observed_qpc is a different fact.
        Generic direct native use does not require this private wrapper window.
        """
        if self._begin_attempted or self._private_window is not None:
            raise self._error
        epoch, original_frequency, original_stop, original_cleanup = self._source_lease
        if (type(start) is not int or type(frequency) is not int or frequency != original_frequency
                or not epoch <= start or frequency <= 0 or start > (1 << 63) - 1 - 70 * frequency):
            raise self._error
        stop, cleanup = start + 60 * frequency, start + 70 * frequency
        if stop > original_stop or cleanup > original_cleanup:
            raise self._error
        self._private_window = (start, frequency, stop, cleanup)
        self._spec.stop_deadline_qpc, self._spec.cleanup_deadline_qpc = stop, cleanup
        return self._private_window

    def unchanged(self):
        drift = self._library._handle != self._library_handle
        for lookup, fixed, address, arguments, lookup_type, fixed_type, lookup_flags, fixed_flags in self._calls.values():
            for function, expected_type, flags in ((lookup, lookup_type, lookup_flags), (fixed, fixed_type, fixed_flags)):
                actual = function.argtypes
                if (type(function) is not expected_type or function._flags_ != flags
                        or function.restype is not _U32 or getattr(function, "errcheck", None) is not None
                        or type(actual) not in (tuple, list) or tuple(actual) != arguments
                        or _c.cast(function, _c.c_void_p).value != address):
                    drift = True
        self._drifted = self._drifted or drift
        return not self._drifted

    def _call(self, name, *arguments, cleanup=False):
        unchanged = _ORIGINAL_DISPATCH["unchanged"](self)
        if not unchanged and not cleanup:
            raise self._error
        _, fixed, address, types, _, fixed_type, _, flags = self._calls[name]
        if (type(fixed) is not fixed_type or fixed._flags_ != flags
                or _c.cast(fixed, _c.c_void_p).value != address
                or self._library._handle != self._library_handle):
            raise self._error
        fixed.restype, fixed.argtypes = _U32, types
        if getattr(fixed, "errcheck", None) is not None:
            del fixed.errcheck
        return fixed(*arguments)

    def refresh(self, *, cleanup=False):
        result = _ORIGINAL_DISPATCH["_call"](self, "copy_report", _c.byref(self._report), _c.sizeof(self._report), cleanup=cleanup)
        if result != _OK or self._report.abi != 1 or self._report.size != _c.sizeof(self._report):
            raise self._error
        return self._report

    def begin(self):
        if self._begin_attempted:
            raise self._error
        self._begin_attempted = True  # Before native call/result conversion.
        result = _ORIGINAL_DISPATCH["_call"](self, "begin_once", _c.byref(self._spec), _c.sizeof(self._spec))
        _ORIGINAL_DISPATCH["refresh"](self)
        return result

    def birth(self):
        result = _ORIGINAL_DISPATCH["_call"](self, "birth_suspended_once")
        _ORIGINAL_DISPATCH["refresh"](self)
        return result

    def resume(self):
        result = _ORIGINAL_DISPATCH["_call"](self, "resume_once")
        _ORIGINAL_DISPATCH["refresh"](self)
        return result

    def observe(self):
        result = _ORIGINAL_DISPATCH["_call"](self, "observe_step")
        _ORIGINAL_DISPATCH["refresh"](self)
        return result

    def stop_new(self):
        return _ORIGINAL_DISPATCH["_call"](self, "stop_new", cleanup=True)

    def finish_step(self):
        result = _ORIGINAL_DISPATCH["_call"](self, "finish_step", cleanup=True)
        _ORIGINAL_DISPATCH["refresh"](self, cleanup=True)
        return result


# Freeze original implementation functions; class attribute restoration cannot
# erase latched native ABI drift or substitute a Python cleanup callback.
_ORIGINAL_DISPATCH = _MappingProxyType({
    name: getattr(_LoadedOwnedChild, name) for name in (
        "unchanged", "_call", "refresh", "begin", "birth", "resume", "observe",
        "stop_new", "finish_step", "restrict_private_window_once")
} | {
    "report": _LoadedOwnedChild.report.fget,
    "begin_attempted": _LoadedOwnedChild.begin_attempted.fget,
    "drifted": _LoadedOwnedChild.drifted.fget,
    "source_lease": _LoadedOwnedChild.source_lease.fget,
    "private_window": _LoadedOwnedChild.private_window.fget,
})
