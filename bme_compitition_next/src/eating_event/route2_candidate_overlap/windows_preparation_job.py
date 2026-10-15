"""Private generic native-owned child lifecycle; no preparation deployment entry.

The immutable Windows interpreter, stdlib, PE images and complete native load
closure MUST be established by an actual installation/startup owner BEFORE
importing this module. Lazy kernel32 binding is not earlier-constructor proof.
The sole preparation operation below refuses: that owner and the fixed readonly
worker/PE closure have no concrete producer here. Underscores are not a security
boundary; the underlying kernel methods are primitives, never launch permission.

The original caller supplies raw intent and already-bound absolute QPC
deadlines through an ALREADY loaded C02 native component. No custom DLL is
loaded here. Native context-observed QPC is separate from the supplied epoch;
neither proves Python/preload/root history. The existing non-E monitor retains
one private 60/70-second subwindow, sampled ONCE and accepted only as a strict
subset of the supplied original lease deadlines. Original lease values remain
separate; no H1/root credit or epoch is reset. The Job caps only one owned child: 4 GiB commit,
one active process, at most two affinity bits and CPU rate control.
PeakProcessMemoryUsed/PeakJobMemoryUsed are commit peaks, not physical RAM/RSS.
Parent, external observer, WSLService/vmcompute/VM, total RAM and GPU are UNKNOWN.
The fixed C/D native component supplies actual bounded before/after polling,
not a whole-task non-E hard cap: 512 MiB remains MONITORED; 384 MiB is only a
candidate local warning/stop-new-work threshold. Its one-second Wait/Sleep slice
is cooperative within the same 60/70-second QPC deadlines. Synchronous blocking,
sampling gaps and inflight/cleanup overshoot upper bounds remain UNKNOWN.
Killing a wsl.exe child is not VM/service exit; .wslconfig existence is not proof
of applied VM settings. No GT/study authority, Stage entry or budget receipt.

Unclosed deployment dependencies include the readonly worker/runtime/launcher
and pre-Python QPC identity; E carrier/guest creation, allocation and history;
C/D/System writers and inflight/cleanup growth within 512 MiB; external WSL VM
lifecycle and whole-task RAM/GPU. Native call setup alone closes none of them.
ABI: Microsoft Learn winnt.h/jobapi2.h/processthreadsapi.h/winbase.h/tlhelp32.h.
Native C stores every successful Job/PROCESS_INFORMATION acquisition before
another API or foreign conversion. Recoverable ctypes result failures cannot
discard those originals. Unjoined/query/close residuals retain the native
component and Python owner strongly. Fatal owner death/OOM, asynchronous hard
deadlines and complete external containment still require the missing owner.
"""

from __future__ import annotations

import ctypes as _c
import sys as _sys
from types import MappingProxyType as _MappingProxyType

from .native_failure_capture import NativeFailureCapture as _NativeFailureCapture
from .windows_owned_child import (
    _LoadedOwnedChild, _OK as _OWN_OK, _PENDING as _OWN_PENDING,
    _EXITED as _OWN_EXITED, _FINISHED as _OWN_FINISHED, _RESIDUAL as _OWN_RESIDUAL,
    _DONE as _OWN_DONE, _ORIGINAL_DISPATCH as _OWN_DISPATCH,
)


_DWORD, _WORD, _BOOL = _c.c_uint32, _c.c_uint16, _c.c_int32
_SIZE, _HANDLE, _I64, _U64 = _c.c_size_t, _c.c_void_p, _c.c_int64, _c.c_uint64
_VOID, _WSTR = _c.c_void_p, _c.c_wchar_p
_WORKER = "E:\\Route2Dedicated\\control\\prep-worker.exe"
_DIRECTORY = "E:\\Route2Dedicated\\control"
_JOB_FLAGS = 0x00000008 | 0x00000010 | 0x00000200 | 0x00002000
_CPU_FLAGS = 0x1 | 0x4  # ENABLE | HARD_CAP; no weight/min-max interpretation.
_CREATE_FLAGS = 0x4 | 0x400 | 0x80000 | 0x08000000
_JOB_LIST = 0x0002000D  # ProcThreadAttributeValue(JobList=13, FALSE, TRUE, FALSE).
_WAIT_OBJECT_0, _WAIT_TIMEOUT, _WAIT_FAILED = 0, 258, 0xFFFFFFFF
_ORIGINAL_OWNER = _ORIGINAL_KERNEL = None  # Strong retained once-only raw binding.
_ORIGINAL_NATIVE = _ORIGINAL_IDENTITY = _ORIGINAL_EPOCH = _NON_E_DISPATCH = None
_ORIGINAL_OWNED_CHILD = None  # Strong native image/report/intent retention, including residual.


class _IoCounters(_c.Structure):
    _fields_ = [(name, _U64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimits(_c.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", _I64), ("PerJobUserTimeLimit", _I64),
        ("LimitFlags", _DWORD), ("MinimumWorkingSetSize", _SIZE),
        ("MaximumWorkingSetSize", _SIZE), ("ActiveProcessLimit", _DWORD),
        ("Affinity", _SIZE), ("PriorityClass", _DWORD), ("SchedulingClass", _DWORD)]


class _ExtendedLimits(_c.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", _SIZE), ("JobMemoryLimit", _SIZE),
        ("PeakProcessMemoryUsed", _SIZE), ("PeakJobMemoryUsed", _SIZE)]


class _MinMaxRate(_c.Structure):
    _fields_ = [("MinRate", _WORD), ("MaxRate", _WORD)]


class _RateUnion(_c.Union):
    _fields_ = [("CpuRate", _DWORD), ("Weight", _DWORD), ("MinMax", _MinMaxRate)]


class _CpuRate(_c.Structure):
    _fields_ = [("ControlFlags", _DWORD), ("Rate", _RateUnion)]


class _Accounting(_c.Structure):
    _fields_ = [
        ("TotalUserTime", _I64), ("TotalKernelTime", _I64),
        ("ThisPeriodTotalUserTime", _I64), ("ThisPeriodTotalKernelTime", _I64),
        ("TotalPageFaultCount", _DWORD), ("TotalProcesses", _DWORD),
        ("ActiveProcesses", _DWORD), ("TotalTerminatedProcesses", _DWORD)]


class _StartupInfo(_c.Structure):
    _fields_ = [
        ("cb", _DWORD), ("lpReserved", _WSTR), ("lpDesktop", _WSTR),
        ("lpTitle", _WSTR), ("dwX", _DWORD), ("dwY", _DWORD),
        ("dwXSize", _DWORD), ("dwYSize", _DWORD), ("dwXCountChars", _DWORD),
        ("dwYCountChars", _DWORD), ("dwFillAttribute", _DWORD), ("dwFlags", _DWORD),
        ("wShowWindow", _WORD), ("cbReserved2", _WORD), ("lpReserved2", _VOID),
        ("hStdInput", _HANDLE), ("hStdOutput", _HANDLE), ("hStdError", _HANDLE)]


class _StartupInfoEx(_c.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", _VOID)]


class _ProcessInfo(_c.Structure):
    _fields_ = [("hProcess", _HANDLE), ("hThread", _HANDLE),
                ("dwProcessId", _DWORD), ("dwThreadId", _DWORD)]


class _NativeFault(OSError):
    __slots__ = ("operation", "raw_winerror", "original_handle")

    def __init__(self):
        super().__init__("private Windows preparation native call failed")
        self.operation = self.original_handle = None
        self.raw_winerror = 0


class _NativeBinding:
    """Original SYSTEM32 function and an independent fixed-ABI native pointer."""

    __slots__ = ("saved", "drifted", "drift_error", "helper_error")

    def __init__(self, kernel, name, function, restype, argtypes):
        arguments = tuple(argtypes)
        address = _c.cast(function, _VOID).value
        if not address:
            raise PermissionError("original SYSTEM32 function has no native address")
        # The address comes only from this already-bound SYSTEM32 DLL. No new
        # library, caller function or errcheck callback participates in calls.
        fixed = _c.WINFUNCTYPE(restype, *arguments, use_last_error=True)(address)
        self.saved = (kernel, name, function, fixed, restype, arguments,
            address, type(function), type(fixed), function._flags_, fixed._flags_)
        self.drifted = False
        self.drift_error = PermissionError("original Windows native function/ABI drift: UNKNOWN")
        self.helper_error = None


def _native_binding_drift(binding):
    kernel, name, lookup, fixed, result, arguments, address, lookup_type, fixed_type, lookup_flags, fixed_flags = binding.saved
    current = vars(kernel).get(name)
    drift = current is not lookup or type(lookup) is not lookup_type or type(fixed) is not fixed_type
    for function, flags in ((lookup, lookup_flags), (fixed, fixed_flags)):
        if (function.restype is not result or function._flags_ != flags
                or getattr(function, "errcheck", None) is not None):
            drift = True
        actual = function.argtypes
        if (type(actual) not in (tuple, list) or len(actual) != len(arguments)
                or any(left is not right for left, right in zip(actual, arguments))):
            drift = True
        if _c.cast(function, _VOID).value != address:
            drift = True
    if drift:
        binding.drifted = True  # A later safe-ABI restoration cannot erase drift.
    return binding.drifted


def _native_function(name):
    """Call the retained real native pointer; never the current DLL attribute."""
    binding = _ORIGINAL_NATIVE[name]
    try:
        _native_binding_drift(binding)
        _, _, _, function, result, arguments, address, _, function_type, _, flags = binding.saved
        if type(function) is not function_type or _c.cast(function, _VOID).value != address:
            raise binding.drift_error
        # Fixed saved pointer, stdcall/use_last_error flags, original ctypes
        # types and no errcheck. ABI drift is latched even when cleanup can
        # safely restore these attributes and call the original pointer.
        if function._flags_ != flags:
            raise binding.drift_error
        function.restype, function.argtypes = result, arguments
        if getattr(function, "errcheck", None) is not None:
            del function.errcheck
        return function
    except BaseException as error:
        binding.helper_error = error  # Strong before any owner report helper.
        raise


def _native_drifted():
    return any(_native_binding_drift(binding) for binding in _ORIGINAL_NATIVE.values())


def _bind_kernel():
    """Bind Windows LLP64 ABI lazily; binding cannot authorize construction."""
    if _sys.platform != "win32" or _c.sizeof(_HANDLE) != 8:
        raise PermissionError("private preparation primitives require 64-bit Windows")
    kernel = _c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x00000800)
    declarations = (
        ("QueryPerformanceFrequency", _BOOL, [_c.POINTER(_I64)]),
        ("QueryPerformanceCounter", _BOOL, [_c.POINTER(_I64)]),
        ("GetCurrentProcess", _HANDLE, []),
        ("GetCurrentProcessId", _DWORD, []), ("GetCurrentThreadId", _DWORD, []),
        ("CreateFileW", _HANDLE, [_WSTR, _DWORD, _DWORD, _VOID, _DWORD, _DWORD, _HANDLE]),
        ("GetFileType", _DWORD, [_HANDLE]),
        ("GetFileInformationByHandleEx", _BOOL, [_HANDLE, _c.c_int32, _VOID, _DWORD]),
        ("GetFinalPathNameByHandleW", _DWORD,
         [_HANDLE, _c.POINTER(_c.c_wchar), _DWORD, _DWORD]),
        ("GetVolumeNameForVolumeMountPointW", _BOOL,
         [_WSTR, _c.POINTER(_c.c_wchar), _DWORD]),
        ("GetDriveTypeW", _DWORD, [_WSTR]),
        ("GetDiskFreeSpaceExW", _BOOL,
         [_WSTR, _c.POINTER(_U64), _c.POINTER(_U64), _c.POINTER(_U64)]),
        ("FindFirstVolumeW", _HANDLE, [_c.POINTER(_c.c_wchar), _DWORD]),
        ("FindNextVolumeW", _BOOL, [_HANDLE, _c.POINTER(_c.c_wchar), _DWORD]),
        ("FindVolumeClose", _BOOL, [_HANDLE]),
        ("CloseHandle", _BOOL, [_HANDLE]))
    bindings = {}
    for name, restype, argtypes in declarations:
        function = getattr(kernel, name)  # Only existing parent/file-monitor ABI here.
        function.restype, function.argtypes = restype, argtypes
        bindings[name] = _NativeBinding(kernel, name, function, restype, argtypes)
    return kernel, _MappingProxyType(bindings)


class _KernelOwner:
    """Original handles and one bounded native lifecycle for a future deployer.

    This private object is NOT an installed launch binding or a public factory.
    Its loaded native binding holds raw generic intent/original deadlines;
    neither a Python object nor these inputs verify an execution lease.
    The preparation operation does not construct it while the startup owner is
    missing. It offers no whole-task authority even after local child exit.
    """

    def __init__(self, *, owned_child=None):
        global _ORIGINAL_OWNER, _ORIGINAL_KERNEL, _ORIGINAL_NATIVE, _ORIGINAL_OWNED_CHILD
        if (type(self) is not _KernelOwner or hasattr(self, "capture")
                or _ORIGINAL_OWNER is not None):
            raise PermissionError("private native owner initialization is once only")
        if owned_child is not None and type(owned_child) is not _LoadedOwnedChild:
            raise TypeError("original already-loaded native owned-child binding required")
        self.owned_child = owned_child
        self.capture = _NativeFailureCapture(64)
        self.faults = [_NativeFault() for _ in range(32)]
        self.fault_index = 0
        self.violation = PermissionError("private Windows preparation lifecycle validation failed")
        self.exhausted = PermissionError("preallocated raw native error storage exhausted")
        self.incomplete_capture = PermissionError("private native cleanup/error capture is incomplete")
        self.capture.failure.quarantine = "UNKNOWN"
        self.capture.failure.outside_scope = "UNKNOWN"
        self.capture.failure.local_error_slots_complete = False
        self.capture.failure.raw_native_errors = self.faults
        self.capture.failure.cleanup_dispatch_error = self.capture.failure.report_dispatch_error = None
        self.capture.failure.metadata_error = self.capture.failure.recording_error = None
        self.capture.failure.non_e_raw_samples = self.capture.failure.non_e_held_roots = None
        self.capture.failure.non_e_native_faults = self.capture.failure.non_e_cleanup_dispatch_error = None
        self.capture.failure.non_e_close_dispatch_error = None
        self.capture.failure.non_e_budget_mode, self.capture.failure.non_e_warning_binding = "MONITORED", "CANDIDATE_NOT_OWNER_FROZEN"
        self.capture.failure.non_e_coverage = self.capture.failure.non_e_attribution = "UNKNOWN_NOT_ZERO"
        self.capture.failure.non_e_inflight_upper_bound = "UNKNOWN_NOT_ZERO"
        self.capture.failure.non_e_visible_high_water_bytes = self.capture.failure.non_e_visible_overshoot_bytes = None
        self.capture.failure.non_e_stop_latched, self.capture.failure.non_e_local_status = False, "NOT_INSTALLED"
        self.frequency, self.counter = _I64(), _I64()
        self.process_exited = False
        self.job_empty = self.attempted = self.cleanup_attempted = False
        self.cleanup_integrity_lost = False
        self.started_ticks = self.last_ticks = self.stop_ticks = self.cleanup_ticks = 0
        self.owner_pid = self.owner_tid = self.processor_count = self.affinity = 0
        self.identity_probe_pid = self.identity_probe_tid = None
        self.sample_ticks = 0
        self.context_observed_qpc = 0
        self.original_lease_values = None
        self.private_window = None
        self.non_e_monitor = None
        self.state, self.quarantine = "NEW", "UNKNOWN"
        self.kernel, bindings = _bind_kernel()  # No module-eager DLL load or handles.
        _ORIGINAL_OWNER, _ORIGINAL_KERNEL = self, self.kernel
        _ORIGINAL_NATIVE = bindings
        _ORIGINAL_OWNED_CHILD = owned_child
        self.capture.failure.raw_owned_child_report = None if owned_child is None else _OWN_DISPATCH["report"](owned_child)
        self.capture.failure.raw_owned_child_original_lease = None if owned_child is None else _OWN_DISPATCH["source_lease"](owned_child)

    def _record(self, operation, error, handle=None):
        try:
            self.capture.record(operation, error, handle)
        except BaseException as failure:
            if self.capture.aggregation_error is None:
                self.capture.aggregation_error = failure
            self.capture.failure.recording_error = failure
            self.quarantine = "UNKNOWN"
            return failure  # Monitor's original raw slot retains this helper failure.
        return None

    def _native_error(self, operation, handle=None):
        code = _c.get_last_error()  # Capture before any other native operation.
        if self.fault_index >= len(self.faults):
            self.capture.aggregation_error = self.exhausted
            self.quarantine = "UNKNOWN"
            self._record(operation, self.exhausted, handle)
            return self.exhausted
        error = self.faults[self.fault_index]
        self.fault_index += 1
        error.operation, error.raw_winerror, error.original_handle = operation, code, handle
        self._record(operation, error, handle)
        return error

    def _invalid(self, operation):
        self._record(operation, self.violation)
        raise self.violation

    def _clock(self):
        if not _native_function("QueryPerformanceCounter")(_c.byref(self.counter)):
            raise self._native_error("QueryPerformanceCounter")
        ticks = self.counter.value
        if ticks <= 0 or ticks < self.last_ticks:
            self._invalid("QPC_nonpositive_or_regressed")
        self.last_ticks = ticks
        return ticks

    def _start_clock(self):
        global _ORIGINAL_IDENTITY, _ORIGINAL_EPOCH
        if self is not _ORIGINAL_OWNER or _ORIGINAL_IDENTITY is not None:
            self._invalid("original_native_epoch_already_issued")
        if (self.owned_child is None or self.owned_child is not _ORIGINAL_OWNED_CHILD
                or not _OWN_DISPATCH["unchanged"](self.owned_child)):
            self._invalid("already_loaded_original_native_child_binding_absent")
        self.original_lease_values = _OWN_DISPATCH["source_lease"](self.owned_child)
        if not _native_function("QueryPerformanceFrequency")(_c.byref(self.frequency)):
            raise self._native_error("QueryPerformanceFrequency_private_subwindow")
        # One sample produces exactly the existing monitor's private window.
        # This is neither original H1 t0 nor native creator/preload birth.
        private_start = self._clock()
        self.private_window = _OWN_DISPATCH["restrict_private_window_once"](self.owned_child, private_start, self.frequency.value)
        result = _OWN_DISPATCH["begin"](self.owned_child)  # Native owns every acquired handle even if conversion raises.
        report = _OWN_DISPATCH["report"](self.owned_child)
        self.owner_pid, self.owner_tid = report.creator_pid, report.creator_tid
        self.frequency.value = report.qpc_frequency
        self.started_ticks = self.private_window[0]  # Private monitor start only, never original H1/root t0.
        self.context_observed_qpc = report.context_observed_qpc
        self.last_ticks = report.last_qpc
        self.stop_ticks, self.cleanup_ticks = report.stop_deadline_qpc, report.cleanup_deadline_qpc
        if (result != _OWN_OK or not self.owner_pid or not self.owner_tid
                or report.lease_epoch_qpc != self.original_lease_values[0]
                or (self.started_ticks, self.frequency.value, self.stop_ticks, self.cleanup_ticks) != self.private_window):
            self._invalid("native_owned_child_begin_failed")
        _ORIGINAL_IDENTITY = (self.owner_pid, self.owner_tid)
        _ORIGINAL_EPOCH = (_ORIGINAL_IDENTITY[0], _ORIGINAL_IDENTITY[1],
            self.started_ticks, self.frequency.value, self.stop_ticks, self.cleanup_ticks)

    def _identity_guard(self):
        # Retain actual original-native query returns before comparing. Never
        # use a replaced DLL attribute to prove a numeric HANDLE is ours here.
        self.identity_probe_pid = _native_function("GetCurrentProcessId")()
        self.identity_probe_tid = _native_function("GetCurrentThreadId")()
        if (self is not _ORIGINAL_OWNER or _ORIGINAL_IDENTITY is None
                or (self.identity_probe_pid, self.identity_probe_tid) != _ORIGINAL_IDENTITY):
            self._invalid("original_native_process_thread_changed")

    def _stop_guard(self):
        self._identity_guard()
        if (self is not _ORIGINAL_OWNER or self.kernel is not _ORIGINAL_KERNEL
                or (self.owner_pid, self.owner_tid) != _ORIGINAL_IDENTITY
                or (self.owner_pid, self.owner_tid, self.started_ticks,
                    self.frequency.value, self.stop_ticks, self.cleanup_ticks) != _ORIGINAL_EPOCH
                or self.owned_child is not _ORIGINAL_OWNED_CHILD
                or self.owned_child is None or not _OWN_DISPATCH["unchanged"](self.owned_child)
                or self.original_lease_values != _OWN_DISPATCH["source_lease"](self.owned_child)
                or self.private_window != _OWN_DISPATCH["private_window"](self.owned_child)
                or _native_drifted()):
            self._invalid("original_owner_identity_changed")
        if self._clock() >= _ORIGINAL_EPOCH[4]:
            self._invalid("absolute_private_stop_deadline")
        if _NON_E_DISPATCH is None or _NON_E_DISPATCH["registered"](self) is None:
            self._invalid("fixed_non_e_native_monitor_not_installed")
        # The retained original helper invokes the original method/component.
        # Its guard rejects mutable-field drift; no substituted sampler runs.
        _NON_E_DISPATCH["guard"](self)
        if self._clock() >= _ORIGINAL_EPOCH[4]:
            self._invalid("absolute_private_stop_deadline_after_non_e_poll")

    def _cleanup_non_e_observation(self):
        # This path never lets a threshold, read failure or report-helper error
        # bypass original terminate/wait/close. The operation primary stays held.
        if _NON_E_DISPATCH is not None:
            try:
                _NON_E_DISPATCH["observe"](self)
            except BaseException as error:
                self.capture.failure.non_e_cleanup_dispatch_error = error
                self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
                self._record("non_e_cleanup_observation_dispatch", error)

    def _close_non_e_once(self):
        if _NON_E_DISPATCH is not None:
            try:
                _NON_E_DISPATCH["close"](self)
            except BaseException as error:
                self.capture.failure.non_e_close_dispatch_error = error
                self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
                self._record("non_e_close_once_dispatch", error)

    def _wait_for_local_exit(self):
        """All child waits/accounting/identity now use the native originals."""
        while True:
            self._stop_guard()
            result = _OWN_DISPATCH["observe"](self.owned_child)
            report = _OWN_DISPATCH["report"](self.owned_child)
            self.sample_ticks = report.last_qpc
            self.process_exited, self.job_empty = bool(report.process_signaled), bool(report.job_empty)
            self._cleanup_non_e_observation()
            if result == _OWN_EXITED and not report.fault_count:
                self.state = "NATIVE_CHILD_GROUP_EXIT_PENDING_FINAL_SAMPLE"
                return
            if result != _OWN_PENDING:
                self._invalid("native_owned_child_observation_failed")
            self._stop_guard()

    def _cleanup_once(self, failed):
        """Native once-termination/joins/final-sampling/close; retain residuals.

        Native ownership survives any earlier return conversion/report failure.
        No Python HANDLE value or mutable cleanup flag is used to terminate a
        child. The original singleton and library are never cleared or reused.
        """
        if self.cleanup_attempted:
            return
        self.cleanup_attempted = True
        native = _ORIGINAL_OWNED_CHILD
        if native is None or not _OWN_DISPATCH["begin_attempted"](native):
            self.quarantine = "UNKNOWN"
            return
        self._cleanup_non_e_observation()
        try:
            _OWN_DISPATCH["stop_new"](native)
        except BaseException as error:
            # Still dispatch finish: stop is not a prerequisite for cleanup.
            self._record("native_owned_child_stop_dispatch", error)
            self.cleanup_integrity_lost = True
        try:
            while True:
                result = _OWN_DISPATCH["finish_step"](native)  # Each wait shares the original absolute deadline.
                self._cleanup_non_e_observation()
                if result == _OWN_PENDING:
                    continue
                report = _OWN_DISPATCH["report"](native)
                binding_drifted = (_OWN_DISPATCH["drifted"](native)
                    or not _OWN_DISPATCH["unchanged"](native))
                self.process_exited, self.job_empty = bool(report.process_signaled), bool(report.job_empty)
                if (result == _OWN_FINISHED and report.lifecycle == _OWN_DONE
                        and report.final_complete and not report.residual_bits):
                    self.state = "NATIVE_CHILD_GROUP_FINAL_FACTS_AND_CLOSES_OBSERVED"
                    if report.fault_count or binding_drifted:
                        self.cleanup_integrity_lost = True
                        self.quarantine = "UNKNOWN"
                    else:
                        monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
                        self.quarantine = ("UNKNOWN" if monitor is None or monitor.unknown
                            else "CHILD_GROUP_EXIT_OBSERVED")
                    self._close_non_e_once()
                else:
                    # Keep original native/library/owner and monitor roots held.
                    # No fresh wait, PID reopen, release-for-reuse or false EXITED.
                    self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
                    self.state = "NATIVE_CHILD_RESIDUAL_RETAINED"
                break
        except BaseException as error:
            self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
            self.state = "NATIVE_CHILD_RESIDUAL_RETAINED"
            self.capture.failure.cleanup_dispatch_error = error
            self._record("native_owned_child_finish_dispatch", error)
            self._cleanup_non_e_observation()  # Roots remain open on this path.

    def _capture_incomplete(self):
        monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
        native = _ORIGINAL_OWNED_CHILD
        report = None if native is None else _OWN_DISPATCH["report"](native)
        binding_drifted = native is not None and (_OWN_DISPATCH["drifted"](native)
            or not _OWN_DISPATCH["unchanged"](native))
        return (self.capture.aggregation_error is not None
                or self.capture.overflowed or self.cleanup_integrity_lost
                or binding_drifted
                or report is None or report.lifecycle != _OWN_DONE
                or not report.final_complete or bool(report.residual_bits) or bool(report.fault_count)
                or (report.process.acquired and
                    (report.final_exit_code.state != 1 or report.final_exit_code.value != 0))
                or (monitor is not None and (monitor.unknown or not monitor.baseline_installed)))

    def _finalize_capture(self):
        # Pre-reserved entries report local slots, never full native/OS/birth history.
        failure = self.capture.failure
        try:
            if self._capture_incomplete():
                self.quarantine = "UNKNOWN"
            failure.quarantine = self.quarantine
            failure.outside_scope, failure.history_complete = "UNKNOWN", False
            failure.local_error_slots_complete = not self._capture_incomplete()
            failure.aggregation_error = self.capture.aggregation_error
            monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
            if monitor is not None:
                failure.non_e_visible_high_water_bytes = monitor.visible_positive_high_water_bytes
                failure.non_e_visible_overshoot_bytes = monitor.visible_budget_overshoot_bytes
                failure.non_e_stop_latched = monitor.stop_latched
                failure.non_e_local_status = "UNKNOWN" if monitor.unknown or not monitor.baseline_installed else "OBSERVED_FIXED_C_D_ONLY"
        except BaseException as error:
            self.state = "FAILED"
            self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
            failure.quarantine, failure.history_complete = "UNKNOWN", False
            failure.local_error_slots_complete, failure.metadata_error = False, error
            self._record("failure_metadata_finalization", error)

    def _kernel_lifecycle(self):
        """Raw composition only; the absent installation owner cannot call it."""
        global _NON_E_DISPATCH
        if self.attempted:
            self._invalid("private_lifecycle_already_consumed")
        self.attempted = True
        primary = None
        try:
            self._start_clock()
            from .windows_non_e_monitor import _ORIGINAL_DISPATCH
            if _NON_E_DISPATCH is not None:
                self._invalid("original_non_e_dispatch_already_issued")
            # Retain the exact original entrypoints before installing handles.
            _NON_E_DISPATCH = _ORIGINAL_DISPATCH
            _NON_E_DISPATCH["install"](self)
            self._stop_guard()
            if _OWN_DISPATCH["birth"](self.owned_child) != _OWN_OK:
                self._invalid("native_owned_child_birth_failed")
            self._stop_guard()
            if _OWN_DISPATCH["resume"](self.owned_child) != _OWN_OK:
                self._invalid("native_owned_child_resume_failed")
            self._wait_for_local_exit()
        except BaseException as error:
            primary = error
            self._record("private_kernel_lifecycle", error)
        try:
            self._cleanup_once(primary is not None)
        except BaseException as error:
            self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
            self.capture.failure.cleanup_dispatch_error = error
            self._record("cleanup_once_dispatch", error)
        self._finalize_capture()
        if (primary is not None or self.capture.first_error is not None
                or self._capture_incomplete()):
            self.state = "FAILED"
            if primary is None:
                primary = self.capture.first_error
            if primary is None:
                primary = self.incomplete_capture
                self._record("incomplete_local_capture", primary)
            if self.capture.failure.primary_error is None:
                self.capture.failure.primary_error = primary
            try:
                self.capture.raise_failure(primary)
            except BaseException as error:
                if error is not self.capture.failure:
                    self.capture.failure.report_dispatch_error = error
                    self.cleanup_integrity_lost = True
                    self._record("failure_report_dispatch", error)
            finally:
                # Reconcile report fallback's new aggregation/overflow; retain the primary.
                self._finalize_capture()
            raise self.capture.failure from primary
        return self  # Raw samples/handles-consumed state, never an approval receipt.


_ORIGINAL_RECORD = _KernelOwner._record


def _prepare_fixed_worker():
    """No arguments and no present launch path around the missing owner gate."""
    raise PermissionError(
        "readonly Windows worker/PE closure and pre-import installation/startup owner are absent")
