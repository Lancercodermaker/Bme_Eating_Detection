"""Private native child-Job lifecycle source; no preparation deployment entry.

The immutable Windows interpreter, stdlib, PE images and complete native load
closure MUST be established by an actual installation/startup owner BEFORE
importing this module. Lazy kernel32 binding is not earlier-constructor proof.
The sole preparation operation below refuses: that owner and the fixed readonly
worker/PE closure have no concrete producer here. Underscores are not a security
boundary; the underlying kernel methods are primitives, never launch permission.

The raw QPC epoch begins here before child birth, not before Python startup or
the original whole preparation/study. Fixed 60/70-second absolute deadlines
cover only this private lifecycle. The Job caps only its child group: 4 GiB
commit, four active processes, at most two affinity bits and CPU rate control.
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
ABI: Microsoft Learn winnt.h/jobapi2.h/processthreadsapi.h/winbase.h.
Arbitrary/fatal OOM or owner death is not recoverably contained here. In
particular, ctypes HANDLE-return conversion can fail after native Job creation;
only a future native/external owner can close that UNKNOWN quarantine gap.
"""

from __future__ import annotations

import ctypes as _c
import sys as _sys
from types import MappingProxyType as _MappingProxyType

from .native_failure_capture import NativeFailureCapture as _NativeFailureCapture


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
    # Fail closed on another ABI rather than assuming POSIX c_long layout.
    if (_c.sizeof(_BasicLimits), _c.sizeof(_ExtendedLimits), _c.sizeof(_CpuRate),
            _c.sizeof(_Accounting), _c.sizeof(_StartupInfoEx), _c.sizeof(_ProcessInfo)) != (
                64, 144, 8, 48, 112, 24):
        raise PermissionError("private preparation Win32 structure ABI differs")
    kernel = _c.WinDLL("kernel32.dll", use_last_error=True, winmode=0x00000800)
    declarations = (
        ("QueryPerformanceFrequency", _BOOL, [_c.POINTER(_I64)]),
        ("QueryPerformanceCounter", _BOOL, [_c.POINTER(_I64)]),
        ("GetCurrentProcess", _HANDLE, []),
        ("GetCurrentProcessId", _DWORD, []), ("GetCurrentThreadId", _DWORD, []),
        ("GetActiveProcessorGroupCount", _WORD, []),
        ("GetActiveProcessorCount", _DWORD, [_WORD]),
        ("GetProcessAffinityMask", _BOOL, [_HANDLE, _c.POINTER(_SIZE), _c.POINTER(_SIZE)]),
        ("CreateJobObjectW", _HANDLE, [_VOID, _WSTR]),
        ("SetInformationJobObject", _BOOL, [_HANDLE, _c.c_int32, _VOID, _DWORD]),
        ("QueryInformationJobObject", _BOOL,
         [_HANDLE, _c.c_int32, _VOID, _DWORD, _c.POINTER(_DWORD)]),
        ("InitializeProcThreadAttributeList", _BOOL,
         [_VOID, _DWORD, _DWORD, _c.POINTER(_SIZE)]),
        ("UpdateProcThreadAttribute", _BOOL,
         [_VOID, _DWORD, _SIZE, _VOID, _SIZE, _VOID, _c.POINTER(_SIZE)]),
        ("DeleteProcThreadAttributeList", None, [_VOID]),
        ("CreateProcessW", _BOOL,
         [_WSTR, _c.POINTER(_c.c_wchar), _VOID, _VOID, _BOOL, _DWORD,
          _VOID, _WSTR, _c.POINTER(_StartupInfo), _c.POINTER(_ProcessInfo)]),
        ("GetProcessId", _DWORD, [_HANDLE]), ("GetThreadId", _DWORD, [_HANDLE]),
        ("IsProcessInJob", _BOOL, [_HANDLE, _HANDLE, _c.POINTER(_BOOL)]),
        ("ResumeThread", _DWORD, [_HANDLE]),
        ("WaitForSingleObject", _DWORD, [_HANDLE, _DWORD]),
        ("GetExitCodeProcess", _BOOL, [_HANDLE, _c.POINTER(_DWORD)]),
        ("TerminateJobObject", _BOOL, [_HANDLE, _DWORD]),
        ("TerminateProcess", _BOOL, [_HANDLE, _DWORD]),
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
        ("CloseHandle", _BOOL, [_HANDLE]), ("Sleep", None, [_DWORD]))
    bindings = {}
    for name, restype, argtypes in declarations:
        function = getattr(kernel, name)  # Missing JOB_LIST support is never emulated.
        function.restype, function.argtypes = restype, argtypes
        bindings[name] = _NativeBinding(kernel, name, function, restype, argtypes)
    return kernel, _MappingProxyType(bindings)


class _KernelOwner:
    """Original handles and one bounded native lifecycle for a future deployer.

    This private object is NOT an installed launch binding or a public factory.
    It deliberately has no caller path, command, callback or receipt parameters.
    The preparation operation does not construct it while the startup owner is
    missing. It offers no whole-task authority even after local child exit.
    """

    def __init__(self):
        global _ORIGINAL_OWNER, _ORIGINAL_KERNEL, _ORIGINAL_NATIVE
        if (type(self) is not _KernelOwner or hasattr(self, "capture")
                or _ORIGINAL_OWNER is not None):
            raise PermissionError("private native owner initialization is once only")
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
        self.job, self.pi = _HANDLE(), _ProcessInfo()
        self.limits, self.seen, self.cpu, self.cpu_seen = (
            _ExtendedLimits(), _ExtendedLimits(), _CpuRate(), _CpuRate())
        self.accounting, self.returned = _Accounting(), _DWORD()
        self.frequency, self.counter = _I64(), _I64()
        self.process_mask, self.system_mask = _SIZE(), _SIZE()
        self.membership, self.exit_code, self.attribute_size = _BOOL(), _DWORD(), _SIZE()
        self.jobs, self.startup = (_HANDLE * 1)(), _StartupInfoEx()
        # Fixed absolute ApplicationName and quoted argv[0]; no caller command/PATH search.
        self.command = _c.create_unicode_buffer('"E:\\Route2Dedicated\\control\\prep-worker.exe"')
        self.environment = _c.create_unicode_buffer("SystemRoot=C:\\Windows\0\0")
        self.attribute_buffer = None
        self.attribute_live = self.member_verified = self.process_exited = False
        self.job_empty = self.attempted = self.cleanup_attempted = False
        self.cleanup_integrity_lost = False
        self.started_ticks = self.last_ticks = self.stop_ticks = self.cleanup_ticks = 0
        self.owner_pid = self.owner_tid = self.processor_count = self.affinity = 0
        self.identity_probe_pid = self.identity_probe_tid = None
        self.sample_ticks = 0
        self.non_e_monitor = None
        self.state, self.quarantine = "NEW", "UNKNOWN"
        self.kernel, bindings = _bind_kernel()  # No module-eager DLL load or handles.
        _ORIGINAL_OWNER, _ORIGINAL_KERNEL = self, self.kernel
        _ORIGINAL_NATIVE = bindings

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
        self.owner_pid = _native_function("GetCurrentProcessId")()
        self.owner_tid = _native_function("GetCurrentThreadId")()
        if not self.owner_pid or not self.owner_tid:
            self._invalid("original_native_owner_identity_missing")
        _ORIGINAL_IDENTITY = (self.owner_pid, self.owner_tid)
        if not _native_function("QueryPerformanceFrequency")(_c.byref(self.frequency)):
            raise self._native_error("QueryPerformanceFrequency")
        if self.frequency.value <= 0:
            self._invalid("QPC_frequency_nonpositive")
        self.started_ticks = self._clock()
        self.stop_ticks = self.started_ticks + 60 * self.frequency.value
        self.cleanup_ticks = self.started_ticks + 70 * self.frequency.value
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

    def _cpu_profile(self):
        groups = _native_function("GetActiveProcessorGroupCount")()
        if not groups:
            raise self._native_error("GetActiveProcessorGroupCount")
        count = _native_function("GetActiveProcessorCount")(0xFFFF)  # ALL_PROCESSOR_GROUPS.
        if not count:
            raise self._native_error("GetActiveProcessorCount")
        if groups != 1 or not 1 <= count <= 64:
            self._invalid("unsupported_processor_groups")
        if not _native_function("GetProcessAffinityMask")(_native_function("GetCurrentProcess")(),
                _c.byref(self.process_mask), _c.byref(self.system_mask)):
            raise self._native_error("GetProcessAffinityMask")
        allowed, system = self.process_mask.value, self.system_mask.value
        if not allowed or allowed & ~system or system.bit_count() != count:
            self._invalid("native_affinity_topology_inconsistent")
        first = allowed & -allowed
        remaining = allowed ^ first
        self.affinity = first | (remaining & -remaining)
        self.processor_count = count
        self.cpu.ControlFlags, self.cpu.Rate.CpuRate = _CPU_FLAGS, min(10000, 20000 // count)
        basic = self.limits.BasicLimitInformation
        basic.LimitFlags, basic.ActiveProcessLimit, basic.Affinity = _JOB_FLAGS, 4, self.affinity
        self.limits.JobMemoryLimit = 4 * 1024 ** 3

    def _initialize_attributes(self):
        result = _native_function("InitializeProcThreadAttributeList")(
            None, 1, 0, _c.byref(self.attribute_size))
        sizing_error = _c.get_last_error()
        if not result and sizing_error != 122:
            raise self._native_error("InitializeProcThreadAttributeList_sizing")
        if result or not 0 < self.attribute_size.value <= 65536:
            self._invalid("attribute_list_expected_insufficient_buffer")
        units = (self.attribute_size.value + _c.sizeof(_SIZE) - 1) // _c.sizeof(_SIZE)
        self.attribute_buffer = (_SIZE * units)()  # Pointer-aligned, held through deletion.
        self.startup.lpAttributeList = _c.cast(self.attribute_buffer, _VOID)
        if not _native_function("InitializeProcThreadAttributeList")(self.startup.lpAttributeList,
                1, 0, _c.byref(self.attribute_size)):
            raise self._native_error("InitializeProcThreadAttributeList")
        self.attribute_live = True

    def _create_job(self):
        self._stop_guard()  # Before creating any new Job, then after actual creation.
        self.job.value = _native_function("CreateJobObjectW")(None, None)  # Unnamed, noninheritable.
        if not self.job.value:
            raise self._native_error("CreateJobObjectW")
        self._stop_guard()
        for information_class, value in ((9, self.limits), (15, self.cpu)):
            if not _native_function("SetInformationJobObject")(self.job, information_class,
                    _c.byref(value), _c.sizeof(value)):
                raise self._native_error("SetInformationJobObject", self.job.value)
        self._read_limits()
        self.jobs[0] = self.job.value
        if not _native_function("UpdateProcThreadAttribute")(self.startup.lpAttributeList, 0,
                _JOB_LIST, self.jobs, _c.sizeof(self.jobs), None, None):
            # Win10+ atomic birth association is required. No AssignProcess
            # suspended fallback: it cannot cover allocations before association.
            raise self._native_error("UpdateProcThreadAttribute_JOB_LIST", self.job.value)
        self._stop_guard()

    def _query(self, information_class, value):
        self.returned.value = 0
        if not _native_function("QueryInformationJobObject")(self.job, information_class,
                _c.byref(value), _c.sizeof(value), _c.byref(self.returned)):
            raise self._native_error("QueryInformationJobObject", self.job.value)
        if self.returned.value != _c.sizeof(value):
            self._invalid("job_information_readback_size")

    def _read_limits(self):
        self._query(9, self.seen)
        self._query(15, self.cpu_seen)
        actual, expected = self.seen.BasicLimitInformation, self.limits.BasicLimitInformation
        # Compare every enabled limit and the entire flag word, including absence
        # of both breakaway flags. Disabled fields (e.g. default scheduling class)
        # are not limit values; Microsoft documents them as ignored.
        if (actual.LimitFlags != expected.LimitFlags
                or actual.ActiveProcessLimit != expected.ActiveProcessLimit
                or actual.Affinity != expected.Affinity):
            self._invalid("job_basic_limit_readback_changed")
        if (self.seen.JobMemoryLimit != self.limits.JobMemoryLimit
                or self.seen.ProcessMemoryLimit != 0
                or self.cpu_seen.ControlFlags != _CPU_FLAGS
                or self.cpu_seen.Rate.CpuRate != self.cpu.Rate.CpuRate):
            self._invalid("job_memory_or_cpu_limit_readback_changed")

    def _birth_suspended(self):
        self._stop_guard()  # Current actual non-E sample before atomic child birth.
        if self.pi.hProcess or self.pi.hThread:
            self._invalid("private_child_birth_repeated")
        self.startup.StartupInfo.cb = _c.sizeof(_StartupInfoEx)
        # STARTF_USESTDHANDLES remains clear with bInheritHandles=False.
        if not _native_function("CreateProcessW")(_WORKER, self.command, None, None, False,
                _CREATE_FLAGS, self.environment, _DIRECTORY,
                _c.cast(_c.byref(self.startup), _c.POINTER(_StartupInfo)), _c.byref(self.pi)):
            raise self._native_error("CreateProcessW_atomic_job_birth", self.job.value)
        # Native PROCESS_INFORMATION holds originals even if the return path raises.
        self.state = "SUSPENDED_CHILD"
        self._stop_guard()
        pid = _native_function("GetProcessId")(self.pi.hProcess)
        if not pid:
            raise self._native_error("GetProcessId", self.pi.hProcess)
        tid = _native_function("GetThreadId")(self.pi.hThread)
        if not tid:
            raise self._native_error("GetThreadId", self.pi.hThread)
        if pid != self.pi.dwProcessId or tid != self.pi.dwThreadId:
            self._invalid("original_child_handle_identity_changed")
        self.membership.value = 0
        if not _native_function("IsProcessInJob")(self.pi.hProcess, self.job, _c.byref(self.membership)):
            raise self._native_error("IsProcessInJob", self.pi.hProcess)
        if self.membership.value != 1:
            self._invalid("atomic_child_job_membership_absent")
        self.member_verified = True
        self._read_limits()
        self._stop_guard()
        prior = _native_function("ResumeThread")(self.pi.hThread)
        if prior == 0xFFFFFFFF:
            raise self._native_error("ResumeThread", self.pi.hThread)
        if prior != 1:
            self._invalid("unexpected_original_thread_suspend_count")
        self.state = "RUNNING_CHILD"
        self._stop_guard()  # ResumeThread is synchronous; no interrupt/overshoot bound.
        self._close_thread()
        if self.capture.first_error is not None:
            raise self.capture.first_error
        if self._capture_incomplete():
            raise self.incomplete_capture

    def _sample(self):
        self._query(1, self.accounting)
        self._read_limits()  # Includes raw Job/individual commit peaks in self.seen.
        self.sample_ticks = self._clock()
        if self.accounting.ActiveProcesses > 4 or self.seen.PeakJobMemoryUsed > 4 * 1024 ** 3:
            self._invalid("raw_job_accounting_exceeded_cap")

    def _observe_exit(self, timeout_ms):
        self._identity_guard()
        if self.pi.hProcess and not self.process_exited:
            result = _native_function("WaitForSingleObject")(self.pi.hProcess, timeout_ms)
            if result == _WAIT_FAILED:
                raise self._native_error("WaitForSingleObject", self.pi.hProcess)
            if result == _WAIT_OBJECT_0:
                if not _native_function("GetExitCodeProcess")(self.pi.hProcess, _c.byref(self.exit_code)):
                    raise self._native_error("GetExitCodeProcess", self.pi.hProcess)
                self.process_exited = True  # Signaled original handle, not PID existence.
            elif result != _WAIT_TIMEOUT:
                self._invalid("unexpected_process_wait_result")
        elif timeout_ms:
            _native_function("Sleep")(timeout_ms)  # Descendants may outlive the original child.
        if self.job.value:
            self._query(1, self.accounting)
            self.job_empty = self.accounting.ActiveProcesses == 0
        return (not self.pi.hProcess or self.process_exited) and (not self.job.value or self.job_empty)

    def _wait_for_local_exit(self):
        while True:
            self._stop_guard()
            remaining_ms = (_ORIGINAL_EPOCH[4] - self.last_ticks) * 1000 // _ORIGINAL_EPOCH[3]
            cleared = self._observe_exit(min(1000, remaining_ms))
            self._sample()
            self._stop_guard()
            if self.process_exited and self.exit_code.value != 0:
                self._invalid("original_child_nonzero_exit")
            if cleared:
                self.state = "NATIVE_CHILD_GROUP_EXIT_OBSERVED"
                return

    def _terminate_originals(self):
        self._identity_guard()  # Foreign-process numbers are never terminated.
        job_terminated = False
        if self.job.value:
            try:
                job_terminated = bool(_native_function("TerminateJobObject")(self.job, 0xE0000001))
                if not job_terminated:
                    self._native_error("TerminateJobObject", self.job.value)
            except BaseException as error:
                self._record("TerminateJobObject_exception", error, self.job.value)
        # Before verified membership, or after a failed Job termination, retain
        # the actual process handle path. Never reopen a PID or invoke taskkill.
        if (self.pi.hProcess and not self.process_exited
                and (not self.member_verified or not job_terminated)):
            try:
                if not _native_function("TerminateProcess")(self.pi.hProcess, 0xE0000001):
                    self._native_error("TerminateProcess", self.pi.hProcess)
            except BaseException as error:
                self._record("TerminateProcess_exception", error, self.pi.hProcess)

    def _bounded_cleanup_wait(self):
        while True:
            self._cleanup_non_e_observation()
            ticks = self._clock()
            if ticks >= _ORIGINAL_EPOCH[5]:
                self._invalid("absolute_private_cleanup_deadline")
            remaining_ms = (_ORIGINAL_EPOCH[5] - ticks) * 1000 // _ORIGINAL_EPOCH[3]
            try:
                cleared = self._observe_exit(min(1000, remaining_ms))
            finally:
                self._cleanup_non_e_observation()  # Preserve a failed wait's primary.
            if cleared:
                if self._clock() >= _ORIGINAL_EPOCH[5]:
                    self._invalid("cleanup_exit_observed_after_deadline")
                monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
                if monitor is None or monitor.unknown:
                    self.quarantine = "UNKNOWN"
                else:
                    self.quarantine = "CHILD_GROUP_EXIT_OBSERVED"  # Local handles only, not VM/full-scope clean.
                return

    def _close_thread(self):
        if self.pi.hThread:
            self._identity_guard()  # Reject before consuming a foreign number.
        handle, self.pi.hThread = self.pi.hThread, None
        self._close_consumed(handle, "CloseHandle_thread")

    def _close_process(self):
        if self.pi.hProcess:
            self._identity_guard()
        handle, self.pi.hProcess = self.pi.hProcess, None
        self._close_consumed(handle, "CloseHandle_process")

    def _close_job(self):
        if self.job.value:
            self._identity_guard()
        handle, self.job.value = self.job.value, None
        self._close_consumed(handle, "CloseHandle_job")

    def _close_consumed(self, handle, operation):
        # Only the three original-handle consumers above supply these literals.
        if handle:
            try:
                if not _native_function("CloseHandle")(handle):
                    self._native_error(operation, handle)
                    self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"
            except BaseException as error:
                self._record(operation, error, handle)
                self.cleanup_integrity_lost, self.quarantine = True, "UNKNOWN"

    def _delete_attributes(self):
        if self.attribute_live:
            self._identity_guard()  # The original buffer also belongs to this process.
            self.attribute_live = False
            try:
                _native_function("DeleteProcThreadAttributeList")(self.startup.lpAttributeList)
            except BaseException as error:
                self._record("DeleteProcThreadAttributeList_exception", error)
                self.cleanup_integrity_lost = True
                self.quarantine = "UNKNOWN"

    def _cleanup_once(self, failed):
        if self.cleanup_attempted:
            return
        self.cleanup_attempted = True
        self._cleanup_non_e_observation()
        monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
        if monitor is not None and monitor.stop_latched:
            failed = True
        if failed:
            try:
                self._terminate_originals()
            except BaseException as error:
                self._record("terminate_originals_dispatch", error)
                self.quarantine = "UNKNOWN"
            finally:
                self._cleanup_non_e_observation()
        if self.pi.hProcess or self.job.value:
            try:
                self._bounded_cleanup_wait()
            except BaseException as error:
                self._record("bounded_original_handle_cleanup_wait", error)
                self.quarantine = "UNKNOWN"
        # Independent guarded closes: one recoverable close error cannot skip
        # the remaining originals. Every handle is consumed before its attempt.
        try:
            self._delete_attributes()
        except BaseException as error:
            self._record("delete_attributes_dispatch", error)
            self.cleanup_integrity_lost = True
        try:
            self._close_thread()
        except BaseException as error:
            self._record("close_thread_dispatch", error)
            self.cleanup_integrity_lost = True
        try:
            self._close_process()
        except BaseException as error:
            self._record("close_process_dispatch", error)
            self.cleanup_integrity_lost = True
        try:
            self._close_job()
        except BaseException as error:
            self._record("close_job_dispatch", error)
            self.cleanup_integrity_lost = True
        # Roots remain held through final observed cleanup growth. Monitor
        # cleanup remains independent of all three original Job-handle closes.
        self._cleanup_non_e_observation()
        self._close_non_e_once()
        if self.started_ticks:
            try:
                if _ORIGINAL_EPOCH is None or self._clock() >= _ORIGINAL_EPOCH[5]:
                    self._invalid("complete_handle_cleanup_after_deadline")
            except BaseException as error:
                self._record("final_cleanup_QPC", error)
                self.quarantine = "UNKNOWN"

    def _capture_incomplete(self):
        monitor = None if _NON_E_DISPATCH is None else _NON_E_DISPATCH["registered"](self)
        return (self.capture.aggregation_error is not None
                or self.capture.overflowed or self.cleanup_integrity_lost
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
            self._cpu_profile()
            self._initialize_attributes()
            self._create_job()
            self._stop_guard()
            self._birth_suspended()
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
