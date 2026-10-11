"""Fixed native C/D observation for the original private preparation Job.

This source does not install the missing readonly/pre-Python/native owner. It
has no caller path, threshold, clock, callback, serialized sample or receipt.
Only the original registered _KernelOwner and its SYSTEM32 kernel32 instance
can issue this once-only, process/thread/QPC-bound local monitor.

512 MiB is the bound MONITORED reporting budget. 384 MiB is a CANDIDATE local
conservative warning/stop-new-work threshold, not a newly frozen whole-task
allocation permission or a native disk hard cap. The positive high-water sum
is max(0, baseline total-free - current total-free) on each distinct held C/D
volume. Caller-available and quota-dependent caller-total are separate raw
outputs; neither replaces actual total-free. Deletion offsets, ambient writers,
missed peaks, registry/event logs/System/shared pagefile/WSL services, other
volumes, writer attribution, AllocationSize and complete physical backing all
remain UNKNOWN_NOT_ZERO. A GUID proves a volume, not all physical backing.

256 preallocated snapshots (224 ordinary, 32 reserved for cleanup) retain actual
native outputs, failures and attempts; cleanup also uses unused ordinary slots.
The owner's cooperative Wait/Sleep slice
is one second within its unchanged absolute 60/70-second private QPC deadlines.
Before/after polling cannot interrupt a synchronous native call. Sampling gaps,
native blocking, setup cost, inflight/cleanup growth and overshoot upper bounds
remain UNKNOWN; one second is not an external/native whole-task wall guarantee.
Fatal HANDLE-return conversion, OOM and owner death may leave unknown originals.
No launch, full-coverage, clean-quarantine, VM-exit, Stage or study authority.

ABI/semantics: Microsoft Learn fileapi.h volume enumeration/free-space and
GetFileInformationByHandleEx. FindNextVolume EOF is only ERROR_NO_MORE_FILES;
FindVolumeClose is the dedicated search close. Same-process numbers are
consumed before one close attempt and never retried after close failure.
Original native pointers/ABI and unbound methods are retained independently of
mutable owner fields or DLL attributes. Drift refuses new work; same-process
cleanup still uses those originals. Foreign process/thread probes reject before
HANDLE consumption and retain unknown holds. Baseline-derived counters remain
None until the complete original first snapshot and its final QPC commit.
"""

from __future__ import annotations

import ctypes as _c
import re as _re
from types import MappingProxyType as _MappingProxyType


_DWORD, _U64, _I64 = _c.c_uint32, _c.c_uint64, _c.c_int64
_HANDLE = _c.c_void_p
_GUID_CHARS, _VOLUME_CAPACITY = 64, 32
_SNAPSHOT_CAPACITY, _ORDINARY_CAPACITY = 256, 224
_WARNING_BYTES, _REPORT_BUDGET_BYTES = 384 * 1024 ** 2, 512 * 1024 ** 2
_INVALID_HANDLE = _c.c_void_p(-1).value
_GUID_PATTERN = _re.compile(
    r"\\\\\?\\Volume\{([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})\}\\",
    _re.IGNORECASE)
_FAULT_CLASS = None  # Installed only from the original owner module, before handles.


class _FileId128(_c.Structure):
    _fields_ = [("Identifier", _c.c_ubyte * 16)]


class _FileIdInfo(_c.Structure):
    _fields_ = [("VolumeSerialNumber", _U64), ("FileId", _FileId128)]


class _FileStandardInfo(_c.Structure):
    _fields_ = [
        ("AllocationSize", _I64), ("EndOfFile", _I64), ("NumberOfLinks", _DWORD),
        ("DeletePending", _c.c_ubyte), ("Directory", _c.c_ubyte)]


class _FileAttributeTagInfo(_c.Structure):
    _fields_ = [("FileAttributes", _DWORD), ("ReparseTag", _DWORD)]


class _RawCall:
    __slots__ = ("operation", "attempted", "arguments", "handle", "result",
                 "winerror", "exception", "recording_error", "acquired", "consumed")

    def __init__(self, operation):
        self.operation, self.attempted = operation, False
        self.arguments = self.handle = self.result = self.exception = None
        self.winerror, self.recording_error = 0, None
        self.acquired = self.consumed = False


class _ConsumeCall(_RawCall):
    """One actual process/thread probe before consuming an original number."""

    __slots__ = ("owner_pid", "owner_tid", "rejected")

    def __init__(self, operation):
        super().__init__(operation)
        self.owner_pid = _RawCall(operation + "_GetCurrentProcessId")
        self.owner_tid = _RawCall(operation + "_GetCurrentThreadId")
        self.rejected = False


class _RootRead:
    """Original outbuffers exist before any call or validation/helper work."""

    def __init__(self):
        self.owned_handle = _HANDLE()
        self.open, self.close = _RawCall("CreateFileW_non_e_root"), _RawCall("CloseHandle_non_e_temporary_root")
        self.consume = _ConsumeCall("non_e_temporary_root_consume")
        self.file_type = _RawCall("GetFileType_non_e_root")
        self.tag_call = _RawCall("GetFileInformationByHandleEx_non_e_TagInfo")
        self.standard_call = _RawCall("GetFileInformationByHandleEx_non_e_StandardInfo")
        self.id_call = _RawCall("GetFileInformationByHandleEx_non_e_FileIdInfo")
        self.path_call = _RawCall("GetFinalPathNameByHandleW_non_e_GUID")
        self.tags, self.standard, self.identity = _FileAttributeTagInfo(), _FileStandardInfo(), _FileIdInfo()
        self.guid_buffer = _c.create_unicode_buffer(_GUID_CHARS)
        self.observed_identity = None


class _RootObservation:
    def __init__(self):
        self.mount_before, self.mount_after = _c.create_unicode_buffer(_GUID_CHARS), _c.create_unicode_buffer(_GUID_CHARS)
        self.mount_before_call = _RawCall("GetVolumeNameForVolumeMountPointW_non_e_before")
        self.mount_after_call = _RawCall("GetVolumeNameForVolumeMountPointW_non_e_after")
        self.drive_type = _RawCall("GetDriveTypeW_non_e_fixed_root")
        self.held_before, self.held_after = _RootRead(), _RootRead()
        self.current_dos, self.current_guid = _RootRead(), _RootRead()
        self.available, self.caller_total, self.total_free = _U64(), _U64(), _U64()
        self.free_call = _RawCall("GetDiskFreeSpaceExW_non_e_total_free")
        self.free_dispatch = _RawCall("non_e_independent_raw_free_dispatch")
        self.dispatch = _RawCall("non_e_root_observation_dispatch")
        self.observed_guid, self.validated = None, False
        self.visible_delta_bytes, self.visible_high_water_bytes = None, None


class _VolumeEntry:
    def __init__(self):
        self.buffer = _c.create_unicode_buffer(_GUID_CHARS)
        self.find_call = _RawCall("FindNextVolumeW_non_e_topology")
        self.type_call = _RawCall("GetDriveTypeW_non_e_enumerated_volume")
        self.guid = None


class _Snapshot:
    def __init__(self, index):
        self.index, self.attempted = index, False
        self.baseline = self.cleanup = False
        self.owner_pid = _RawCall("GetCurrentProcessId_non_e_owner")
        self.owner_tid = _RawCall("GetCurrentThreadId_non_e_owner")
        self.start_call, self.end_call = _RawCall("QueryPerformanceCounter_non_e_start"), _RawCall("QueryPerformanceCounter_non_e_end")
        self.start_counter, self.end_counter = _I64(), _I64()
        self.roots = (_RootObservation(), _RootObservation())
        self.volumes = tuple(_VolumeEntry() for _ in range(_VOLUME_CAPACITY + 1))
        self.volumes[0].find_call.operation = "FindFirstVolumeW_non_e_topology"
        self.find_handle, self.find_close = _HANDLE(), _RawCall("FindVolumeClose_non_e_topology")
        self.find_consume = _ConsumeCall("non_e_topology_search_consume")
        self.topology_dispatch = _RawCall("non_e_topology_dispatch")
        self.dispatch = _RawCall("non_e_snapshot_dispatch")
        self.end_dispatch = _RawCall("non_e_snapshot_final_QPC_dispatch")
        self.binding_dispatch = _RawCall("non_e_original_binding_dispatch")
        self.reuse_dispatch = _RawCall("non_e_original_snapshot_slot_refused")
        self.commit_dispatch = _RawCall("non_e_baseline_commit_dispatch")
        self.warning = _RawCall("candidate_non_e_visible_warning_stop_new_work")
        self.warning_dispatch = _RawCall("candidate_non_e_warning_record_dispatch")
        self.validation_error = PermissionError("fixed non-E native identity/topology/sample is unknown")
        self.volume_count, self.topology = 0, None
        self.primary_error = None
        self.status, self.attribution = "NOT_ATTEMPTED", "UNKNOWN_NOT_ZERO"
        self.visible_positive_high_water_bytes = self.visible_budget_overshoot_bytes = None


class _HeldRoot:
    def __init__(self, letter):
        self.mount_path, self.open_path = letter + ":\\", "\\\\?\\" + letter + ":\\"
        self.handle, self.open, self.close = _HANDLE(), _RawCall("CreateFileW_non_e_held_root"), _RawCall("CloseHandle_non_e_held_root")
        self.consume = _ConsumeCall("non_e_held_root_consume")
        self.anchor_identity = None  # Held-handle fact, never baseline authority.
        self.guid = self.baseline_identity = self.baseline_total_free = self.baseline_raw = None
        self.visible_high_water_bytes = None


class _Issuance:
    def __init__(self):
        self.owner = self.kernel = self.monitor = self.epoch = None
        self.native = self.native_function = self.native_drifted = self.methods = self.record = None
        self.roots = self.samples = self.faults = self.baseline = None
        self.resources = None  # Original frame references, installed before acquisition.
        self.validated_observations = None  # Original completed native root facts, never a public bool.
        self.root_paths = self.baseline_facts = self.baseline_topology = None
        self.anchor_identities, self.high_water_bytes = [None, None], [None, None]
        self.attempted_samples = [False] * _SNAPSHOT_CAPACITY
        self.ordinary_cursor, self.cleanup_cursor, self.fault_index = 0, _ORDINARY_CAPACITY, 0
        self.first_error = self.threshold_origin = None
        self.unknown = self.stop_latched = self.closed = self.close_attempted = False
        self.visible_positive_high_water_bytes = self.visible_budget_overshoot_bytes = None
        self.close_binding = _RawCall("non_e_original_close_state_binding")


_ISSUANCE = _Issuance()  # Strong retained original issuance, including after cleanup.


def _invoke(monitor, name, *arguments, **keywords):
    # Exact saved unbound source method: no mutable instance callback dispatch.
    return _ISSUANCE.methods[name](monitor, *arguments, **keywords)


class _FixedNonEMonitor:
    """A raw local owner component; underscores are not deployment authority."""

    def __init__(self):
        self.owner, self.kernel, self.epoch = _ISSUANCE.owner, _ISSUANCE.kernel, _ISSUANCE.epoch
        self.roots = (_HeldRoot("C"), _HeldRoot("D"))
        self.samples = tuple(_Snapshot(index) for index in range(_SNAPSHOT_CAPACITY))
        self.native_faults = tuple(_FAULT_CLASS() for _ in range(64))
        self.fault_index, self.ordinary_cursor, self.cleanup_cursor = 0, 0, _ORDINARY_CAPACITY
        self.stop_error = PermissionError("candidate 384 MiB visible C/D warning: stop private new work")
        self.exhausted = PermissionError("bounded non-E raw sampling storage exhausted: UNKNOWN")
        self.fault_exhausted = PermissionError("bounded non-E raw native fault storage exhausted: UNKNOWN")
        self.binding_error = PermissionError("non-E original native owner/QPC binding changed: UNKNOWN")
        self.exhaustion_call = _RawCall("non_e_raw_storage_exhausted")
        self.first_error = self.threshold_origin = self.baseline_topology = None
        self.baseline_installed = self.stop_latched = self.unknown = self.closed = False
        self.close_attempted, self.exhausted_attempts = False, 0
        self.visible_positive_high_water_bytes = self.visible_budget_overshoot_bytes = None
        self.report_budget_bytes, self.candidate_warning_bytes = _REPORT_BUDGET_BYTES, _WARNING_BYTES
        self.budget_mode, self.warning_binding = "MONITORED", "CANDIDATE_NOT_OWNER_FROZEN"
        self.full_coverage = self.writer_attribution = self.inflight_upper_bound = "UNKNOWN_NOT_ZERO"

    def _retain(self, raw, error, sample=None):
        # Never put this aggregate wrapper back into its own raw/error slots.
        # No foreign wrapper/callback is made or accepted as a healthy sample.
        if error is _ISSUANCE.owner.capture.failure:
            error = _ISSUANCE.owner.capture.failure.primary_error or _ISSUANCE.owner.capture.first_error
            if error is None or error is _ISSUANCE.owner.capture.failure:
                error = self.binding_error
        raw.exception = error  # Actual error held before recording/report helpers.
        if sample is not None and sample.primary_error is None:
            sample.primary_error = error
        if _ISSUANCE.first_error is None:
            _ISSUANCE.first_error = error
        self.first_error = _ISSUANCE.first_error
        self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
        _ISSUANCE.owner.quarantine = "UNKNOWN"
        try:
            recording = _ISSUANCE.record(_ISSUANCE.owner, raw.operation, error, raw.handle)
            if recording is not None:
                raw.recording_error = recording  # Strong actual secondary, before more helpers.
                _ISSUANCE.owner.cleanup_integrity_lost = True
        except BaseException as recording:
            raw.recording_error = recording
            _ISSUANCE.owner.cleanup_integrity_lost = True
        return error

    def _call(self, raw, name, arguments, sample, handle=None):
        raw.arguments, raw.handle = arguments, handle
        try:
            function = _ISSUANCE.native_function(name)
            _c.set_last_error(0)  # UNKNOWN GetFileType must not inherit a stale error.
            raw.attempted = True
            raw.result = function(*arguments)
            if name in ("CreateFileW", "FindFirstVolumeW"):
                # Actual numeric return is held/owned BEFORE GetLastError or
                # HANDLE-holder assignment. Fatal return conversion is UNKNOWN.
                raw.acquired = raw.result is not None and raw.result != _INVALID_HANDLE
            raw.winerror = _c.get_last_error()  # No other native operation first.
        except BaseException as error:
            _invoke(self, "_retain", raw, error, sample)
            raise
        return raw.result

    def _failed_call(self, raw, sample):
        # Every actual return/code/buffer is already held. Reserve an original
        # fault object before invoking the owner's aggregation helper.
        index = _ISSUANCE.fault_index
        if index < len(_ISSUANCE.faults):
            error = _ISSUANCE.faults[index]
            _ISSUANCE.fault_index = self.fault_index = index + 1
            raw.exception = error
            error.operation, error.raw_winerror, error.original_handle = raw.operation, raw.winerror, raw.handle
        else:
            raw.exception = error = self.fault_exhausted
        raise _invoke(self, "_retain", raw, error, sample)

    def _require(self, raw, sample):
        if not raw.result:
            _invoke(self, "_failed_call", raw, sample)

    def _invalid(self, sample):
        raise _ISSUANCE.resources[sample]["validation_error"]

    def _guid(self, buffer, sample):
        value = buffer.value
        match = _GUID_PATTERN.fullmatch(value)
        if match is None:
            _invoke(self, "_invalid", sample)
        return "\\\\?\\Volume{" + match[1].lower() + "}\\"

    def _clock(self, raw, buffer, sample):
        _invoke(self, "_call", raw, "QueryPerformanceCounter", (_c.byref(buffer),), sample)
        _invoke(self, "_require", raw, sample)
        ticks = buffer.value
        if ticks <= 0 or ticks < _ISSUANCE.owner.last_ticks:
            _invoke(self, "_invalid", sample)
        _ISSUANCE.owner.last_ticks = ticks
        return ticks

    def _owner_binding(self, sample):
        if self is not _ISSUANCE.monitor:
            raise self.binding_error
        root_drift = False
        for index, root in enumerate(_ISSUANCE.roots):
            fact = None if _ISSUANCE.baseline_facts is None else _ISSUANCE.baseline_facts[index]
            if ((root.mount_path, root.open_path) != _ISSUANCE.root_paths[index]
                    or root.anchor_identity != _ISSUANCE.anchor_identities[index]
                    or (root.guid, root.baseline_identity, root.baseline_total_free)
                    != ((None, None, None) if fact is None else fact[2:])
                    or root.baseline_raw is not (None if fact is None else fact[1])
                    or root.visible_high_water_bytes != _ISSUANCE.high_water_bytes[index]):
                root_drift = True
        drift = (self.owner is not _ISSUANCE.owner or self.epoch is not _ISSUANCE.epoch
                or _ISSUANCE.owner.non_e_monitor is not self or self.kernel is not _ISSUANCE.kernel
                or _ISSUANCE.owner.kernel is not self.kernel or _ISSUANCE.closed or _ISSUANCE.close_attempted
                or self.roots is not _ISSUANCE.roots or self.samples is not _ISSUANCE.samples
                or self.native_faults is not _ISSUANCE.faults or root_drift
                or _invoke(self, "_resource_drift")
                or self.baseline_topology != _ISSUANCE.baseline_topology
                or self.baseline_installed is not (_ISSUANCE.baseline is not None)
                or self.visible_positive_high_water_bytes != _ISSUANCE.visible_positive_high_water_bytes
                or self.visible_budget_overshoot_bytes != _ISSUANCE.visible_budget_overshoot_bytes
                or (_ISSUANCE.owner.owner_pid, _ISSUANCE.owner.owner_tid, _ISSUANCE.owner.started_ticks,
                    _ISSUANCE.owner.frequency.value, _ISSUANCE.owner.stop_ticks, _ISSUANCE.owner.cleanup_ticks) != _ISSUANCE.epoch
                or _ISSUANCE.native_drifted())
        if drift:
            if not sample.cleanup:
                raise self.binding_error
            # Field/native-attribute drift is an UNKNOWN fact, never ownership.
            # Cleanup keeps the strong original roots and fixed native pointers.
            binding = _ISSUANCE.resources[sample]["binding_dispatch"]
            if binding.exception is None:
                _invoke(self, "_retain", binding, self.binding_error, sample)
        frame = _ISSUANCE.resources[sample]
        _invoke(self, "_call", frame["owner_pid"], "GetCurrentProcessId", (), sample)
        _invoke(self, "_call", frame["owner_tid"], "GetCurrentThreadId", (), sample)
        if (frame["owner_pid"].result, frame["owner_tid"].result) != _ISSUANCE.epoch[:2]:
            raise self.binding_error

    def _resource_drift(self):
        # Only reference ownership is checked; raw native values/buffer contents
        # are observations, not a Python object/global tampering sandbox.
        return any(getattr(source, name, None) is not original
            for source, references in _ISSUANCE.resources.items()
            for name, original in references.items())

    def _open(self, raw, holder, path, sample):
        _invoke(self, "_call", raw, "CreateFileW", (path, 0x1 | 0x80, 0x1 | 0x2,
            None, 3, 0x00200000 | 0x02000000, None), sample)
        if raw.result is None or raw.result == _INVALID_HANDLE:
            _invoke(self, "_failed_call", raw, sample)
        # Result is retained before HANDLE assignment or any identity checks.
        holder.value = raw.result

    def _consume_open(self, opened, holder, raw, sample):
        if not opened.acquired or opened.consumed:
            return None
        handle = opened.result  # Original strong numeric return, no HANDLE conversion.
        raw.handle = handle
        if raw.rejected:
            # Failed identity probes are retained once; neither the number nor
            # the probe slots are retried/reused by the later independent sweep.
            return None
        raw.attempted = True
        try:
            probes = _ISSUANCE.resources[raw]
            _invoke(self, "_call", probes["owner_pid"], "GetCurrentProcessId", (), sample)
            _invoke(self, "_call", probes["owner_tid"], "GetCurrentThreadId", (), sample)
            if (probes["owner_pid"].result, probes["owner_tid"].result) != _ISSUANCE.epoch[:2]:
                raise self.binding_error
        except BaseException as error:
            raw.rejected = True
            _invoke(self, "_retain", raw, error, sample)
            # Keep acquired original number and holder, unconsumed/unclosed.
            _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"
            return None
        opened.consumed = True  # After identity; never retry after any close attempt.
        raw.consumed = True
        try:
            holder.value = None
        except BaseException as error:
            raw.exception = error
            try:
                _invoke(self, "_retain", raw, error, sample)
            except BaseException as recording:
                raw.recording_error = recording
                self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
                _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"
        return handle

    def _read_root(self, read, handle, sample):
        frame = _ISSUANCE.resources[read]
        _invoke(self, "_call", frame["file_type"], "GetFileType", (handle,), sample, handle)
        if frame["file_type"].result == 0 and frame["file_type"].winerror:
            _invoke(self, "_failed_call", frame["file_type"], sample)
        if frame["file_type"].result != 1:
            _invoke(self, "_invalid", sample)
        for kind, out, raw in ((9, frame["tags"], frame["tag_call"]),
                (1, frame["standard"], frame["standard_call"]), (18, frame["identity"], frame["id_call"])):
            _invoke(self, "_call", raw, "GetFileInformationByHandleEx",
                (handle, kind, _c.byref(out), _c.sizeof(out)), sample, handle)
            _invoke(self, "_require", raw, sample)
        length = _invoke(self, "_call", frame["path_call"], "GetFinalPathNameByHandleW",
            (handle, frame["guid_buffer"], _GUID_CHARS, 1), sample, handle)
        _invoke(self, "_require", frame["path_call"], sample)
        if (length >= _GUID_CHARS or frame["guid_buffer"][length] != "\0"
                or len(frame["guid_buffer"].value.encode("utf-16-le")) // 2 != length):
            _invoke(self, "_invalid", sample)
        tags, standard, identity = frame["tags"], frame["standard"], frame["identity"]
        if (tags.FileAttributes & (0x400 | 0x40) or tags.ReparseTag
                or not tags.FileAttributes & 0x10
                or standard.DeletePending or standard.Directory != 1
                or standard.AllocationSize < 0 or standard.EndOfFile < 0):
            _invoke(self, "_invalid", sample)
        read.observed_identity = (
            _invoke(self, "_guid", frame["guid_buffer"], sample), identity.VolumeSerialNumber,
            bytes(identity.FileId.Identifier), tags.FileAttributes, tags.ReparseTag)
        return read.observed_identity

    def _close_root_read(self, read, sample):
        frame = _ISSUANCE.resources[read]
        closed = frame["close"]
        try:
            handle = _invoke(self, "_consume_open", frame["open"], frame["owned_handle"], frame["consume"], sample)
            if handle:
                _invoke(self, "_call", closed, "CloseHandle", (handle,), sample, handle)
                _invoke(self, "_require", closed, sample)
        except BaseException as error:
            if closed.exception is None:
                _invoke(self, "_retain", closed, error, sample)
            _ISSUANCE.owner.cleanup_integrity_lost = True

    def _take_root(self, root, observed, sample):
        root_frame, frame = _ISSUANCE.resources[root], _ISSUANCE.resources[observed]
        held_before, held_after = frame["held_before"], frame["held_after"]
        current_dos, current_guid = frame["current_dos"], frame["current_guid"]
        dos_frame, guid_frame = _ISSUANCE.resources[current_dos], _ISSUANCE.resources[current_guid]
        opened = root_frame["open"]
        try:
            root_index = _ISSUANCE.roots.index(root)
            mount_path, open_path = _ISSUANCE.root_paths[root_index]
            _invoke(self, "_call", frame["mount_before_call"], "GetVolumeNameForVolumeMountPointW",
                (mount_path, frame["mount_before"], _GUID_CHARS), sample)
            _invoke(self, "_require", frame["mount_before_call"], sample)
            guid = observed.observed_guid = _invoke(self, "_guid", frame["mount_before"], sample)
            _invoke(self, "_call", frame["drive_type"], "GetDriveTypeW", (guid,), sample)
            if frame["drive_type"].result != 3:  # DRIVE_FIXED; UNKNOWN/NO_ROOT never accepted.
                _invoke(self, "_invalid", sample)
            if sample.baseline:
                _invoke(self, "_open", opened, root_frame["handle"], open_path, sample)
            if not opened.acquired or opened.consumed:
                _invoke(self, "_invalid", sample)
            handle = opened.result  # Original acquisition record, not a replaced public reference.
            before = _invoke(self, "_read_root", held_before, handle, sample)
            if (before[0] != guid
                    or (_ISSUANCE.anchor_identities[root_index] is not None
                        and before != _ISSUANCE.anchor_identities[root_index])
                    or (_ISSUANCE.baseline_facts is not None
                        and before != _ISSUANCE.baseline_facts[root_index][3])):
                _invoke(self, "_invalid", sample)
            if _ISSUANCE.anchor_identities[root_index] is None:
                _ISSUANCE.anchor_identities[root_index] = root.anchor_identity = before
            _invoke(self, "_open", dos_frame["open"], dos_frame["owned_handle"], open_path, sample)
            if _invoke(self, "_read_root", current_dos, dos_frame["open"].result, sample) != before:
                _invoke(self, "_invalid", sample)
            _invoke(self, "_raw_free", observed, sample)
            _invoke(self, "_call", frame["mount_after_call"], "GetVolumeNameForVolumeMountPointW",
                (mount_path, frame["mount_after"], _GUID_CHARS), sample)
            _invoke(self, "_require", frame["mount_after_call"], sample)
            if _invoke(self, "_guid", frame["mount_after"], sample) != guid:
                _invoke(self, "_invalid", sample)
            if _invoke(self, "_read_root", held_after, handle, sample) != before:
                _invoke(self, "_invalid", sample)
            _invoke(self, "_open", guid_frame["open"], guid_frame["owned_handle"], guid, sample)
            if _invoke(self, "_read_root", current_guid, guid_frame["open"].result, sample) != before:
                _invoke(self, "_invalid", sample)
            _ISSUANCE.validated_observations[observed] = (guid, before, frame["total_free"].value)
            observed.validated = True
        except BaseException as error:
            _invoke(self, "_retain", frame["dispatch"], error, sample)
        finally:
            # Failed baseline/held-root validation cannot turn a successful raw
            # free read into zero or suppress the independent raw observation.
            # A failed/attempted free call is never retried. No baseline rebase.
            if (observed.observed_guid is not None and frame["drive_type"].result == 3
                    and frame["free_call"].arguments is None):
                try:
                    _invoke(self, "_raw_free", observed, sample)
                except BaseException as error:
                    _invoke(self, "_retain", frame["free_dispatch"], error, sample)
            # A temporary-read failure cannot skip either independent consumer.
            for read in (current_guid, current_dos):
                try:
                    _invoke(self, "_close_root_read", read, sample)
                except BaseException as error:
                    _ISSUANCE.resources[read]["close"].recording_error = error
                    self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
                    _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"

    def _raw_free(self, observed, sample):
        frame = _ISSUANCE.resources[observed]
        _invoke(self, "_call", frame["free_call"], "GetDiskFreeSpaceExW", (observed.observed_guid,
            _c.byref(frame["available"]), _c.byref(frame["caller_total"]),
            _c.byref(frame["total_free"])), sample)
        _invoke(self, "_require", frame["free_call"], sample)
        # Caller-total is quota-dependent: actual total-free can exceed it.
        if (not frame["caller_total"].value
                or frame["available"].value > min(frame["caller_total"].value, frame["total_free"].value)):
            _invoke(self, "_invalid", sample)

    def _close_enumeration(self, sample):
        frame = _ISSUANCE.resources[sample]
        opened = _ISSUANCE.resources[frame["volumes"][0]]["find_call"]
        closed = frame["find_close"]
        try:
            handle = _invoke(self, "_consume_open", opened,
                frame["find_handle"], frame["find_consume"], sample)
            if handle:
                _invoke(self, "_call", closed, "FindVolumeClose", (handle,), sample, handle)
                _invoke(self, "_require", closed, sample)
        except BaseException as error:
            if closed.exception is None:
                _invoke(self, "_retain", closed, error, sample)
            _ISSUANCE.owner.cleanup_integrity_lost = True

    def _topology(self, sample):
        frame = _ISSUANCE.resources[sample]
        volumes = frame["volumes"]
        first = _ISSUANCE.resources[volumes[0]]
        opened = first["find_call"]
        try:
            _invoke(self, "_call", opened, "FindFirstVolumeW", (first["buffer"], _GUID_CHARS), sample)
            if opened.result is None or opened.result == _INVALID_HANDLE:
                _invoke(self, "_failed_call", opened, sample)
            frame["find_handle"].value = opened.result
            for index, entry in enumerate(volumes):
                entry_frame = _ISSUANCE.resources[entry]
                found, drive_type = entry_frame["find_call"], entry_frame["type_call"]
                if index:
                    _invoke(self, "_call", found, "FindNextVolumeW",
                        (opened.result, entry_frame["buffer"], _GUID_CHARS), sample, opened.result)
                    if not found.result:
                        if found.winerror == 18:  # ERROR_NO_MORE_FILES only.
                            break
                        _invoke(self, "_failed_call", found, sample)
                if index == _VOLUME_CAPACITY:
                    _invoke(self, "_invalid", sample)
                entry.guid = _invoke(self, "_guid", entry_frame["buffer"], sample)
                _invoke(self, "_call", drive_type, "GetDriveTypeW", (entry.guid,), sample)
                if drive_type.result not in (2, 3, 4, 5, 6):
                    _invoke(self, "_invalid", sample)
                sample.volume_count = index + 1
            sample.topology = tuple(sorted((entry.guid, _ISSUANCE.resources[entry]["type_call"].result)
                for entry in volumes[:sample.volume_count]))
            root_guids = tuple(observed.observed_guid for observed in frame["roots"])
            if (not sample.topology or len({entry[0] for entry in sample.topology}) != sample.volume_count
                    or any((guid, 3) not in sample.topology for guid in root_guids)
                    or root_guids[0] is None or root_guids[0] == root_guids[1]):
                _invoke(self, "_invalid", sample)
            if _ISSUANCE.baseline is not None and sample.topology != _ISSUANCE.baseline_topology:
                _invoke(self, "_invalid", sample)  # New/disappeared/reclassified volumes stop new work.
        except BaseException as error:
            _invoke(self, "_retain", frame["topology_dispatch"], error, sample)
        finally:
            _invoke(self, "_close_enumeration", sample)

    def _sample(self, *, cleanup=False):
        # Public cursors/latches are reporting mirrors, never slot ownership.
        state_drift = (self.ordinary_cursor != _ISSUANCE.ordinary_cursor
            or self.cleanup_cursor != _ISSUANCE.cleanup_cursor or self.fault_index != _ISSUANCE.fault_index
            or self.unknown != _ISSUANCE.unknown or self.stop_latched != _ISSUANCE.stop_latched
            or self.first_error is not _ISSUANCE.first_error or self.threshold_origin is not _ISSUANCE.threshold_origin
            or self.close_attempted != _ISSUANCE.close_attempted or self.closed != _ISSUANCE.closed)
        use_ordinary = not cleanup or _ISSUANCE.ordinary_cursor < _ORDINARY_CAPACITY
        cursor, limit = ((_ISSUANCE.ordinary_cursor, _ORDINARY_CAPACITY) if use_ordinary
            else (_ISSUANCE.cleanup_cursor, _SNAPSHOT_CAPACITY))
        if cursor >= limit:
            self.exhausted_attempts += 1
            _invoke(self, "_retain", self.exhaustion_call, self.exhausted)
            return
        sample = _ISSUANCE.samples[cursor]  # Strong retained before any actual call.
        frame = _ISSUANCE.resources[sample]
        state_drift = state_drift or _invoke(self, "_resource_drift")
        baseline = not cleanup and cursor == 0  # Original first slot only; no caller rebase flag.
        if use_ordinary:
            _ISSUANCE.ordinary_cursor += 1
        else:
            _ISSUANCE.cleanup_cursor += 1
        self.ordinary_cursor, self.cleanup_cursor = _ISSUANCE.ordinary_cursor, _ISSUANCE.cleanup_cursor
        self.fault_index = _ISSUANCE.fault_index
        self.close_attempted, self.closed = _ISSUANCE.close_attempted, _ISSUANCE.closed
        if sample.attempted or _ISSUANCE.attempted_samples[cursor]:
            _ISSUANCE.attempted_samples[cursor] = True
            # Preserve every original raw slot, including the first baseline.
            _invoke(self, "_retain", frame["reuse_dispatch"], self.binding_error)
            return
        _ISSUANCE.attempted_samples[cursor] = True
        sample.attempted, sample.baseline, sample.cleanup, sample.status = True, baseline, cleanup, "UNKNOWN"
        if state_drift:
            _invoke(self, "_retain", frame["binding_dispatch"], self.binding_error, sample)
            if not cleanup:
                return  # Refuse drift before PID/QPC or any HANDLE/native call.
        try:
            _invoke(self, "_owner_binding", sample)
            _invoke(self, "_clock", frame["start_call"], frame["start_counter"], sample)
            for root, observed in zip(_ISSUANCE.roots, frame["roots"]):
                _invoke(self, "_take_root", root, observed, sample)
            _invoke(self, "_topology", sample)
            if sample.primary_error is None and all(_ISSUANCE.validated_observations[root] is not None
                    for root in frame["roots"]):
                sample.status = "OBSERVED_FIXED_C_D_ONLY"
        except BaseException as error:
            _invoke(self, "_retain", frame["dispatch"], error, sample)
        finally:
            try:
                _invoke(self, "_clock", frame["end_call"], frame["end_counter"], sample)
            except BaseException as error:
                _invoke(self, "_retain", frame["end_dispatch"], error, sample)
            if baseline:
                if sample.primary_error is None and not _ISSUANCE.unknown and sample.status == "OBSERVED_FIXED_C_D_ONLY":
                    try:
                        _invoke(self, "_commit_baseline", sample)  # Only after the final actual QPC.
                    except BaseException as error:
                        _invoke(self, "_retain", frame["commit_dispatch"], error, sample)
                        _invoke(self, "_discard_uninstalled_baseline", sample)
                else:
                    _invoke(self, "_discard_uninstalled_baseline", sample)
            if _ISSUANCE.baseline is not None and not baseline:
                try:
                    _invoke(self, "_derive_visible", sample)
                except BaseException as error:
                    _invoke(self, "_retain", frame["commit_dispatch"], error, sample)
            if sample.primary_error is not None or _ISSUANCE.baseline is None:
                sample.status = "UNKNOWN"

    def _commit_baseline(self, sample):
        # Raw successes are retained throughout; none of the derived counters
        # exist until both roots, bounded inventory and the final QPC succeed.
        frame = _ISSUANCE.resources[sample]
        if (sample is not _ISSUANCE.samples[0] or not sample.baseline
                or _ISSUANCE.baseline is not None or sample.primary_error is not None
                or not frame["end_call"].result or sample.topology is None
                or not all(_ISSUANCE.validated_observations[observed] is not None
                    for observed in frame["roots"])):
            raise self.binding_error
        staged = tuple((root, observed) + _ISSUANCE.validated_observations[observed]
            for root, observed in zip(_ISSUANCE.roots, frame["roots"]))
        for root, observed, guid, identity, free in staged:
            root.guid, root.baseline_identity = guid, identity
            root.baseline_total_free, root.baseline_raw = free, observed
        _ISSUANCE.baseline_facts = staged  # Immutable original GUID/identity/total-free facts.
        _ISSUANCE.baseline_topology = self.baseline_topology = sample.topology
        for index, (root, observed, _, _, _) in enumerate(staged):
            _ISSUANCE.high_water_bytes[index] = 0
            root.visible_high_water_bytes = 0
            observed.visible_delta_bytes = observed.visible_high_water_bytes = 0
        _ISSUANCE.visible_positive_high_water_bytes = _ISSUANCE.visible_budget_overshoot_bytes = 0
        self.visible_positive_high_water_bytes = self.visible_budget_overshoot_bytes = 0
        sample.visible_positive_high_water_bytes = sample.visible_budget_overshoot_bytes = 0
        _ISSUANCE.baseline = sample  # Once-only original first-slot authority.
        self.baseline_installed = True

    def _discard_uninstalled_baseline(self, sample):
        if _ISSUANCE.baseline is not None:
            return
        _ISSUANCE.baseline_facts = _ISSUANCE.baseline_topology = None
        _ISSUANCE.high_water_bytes[:] = [None, None]
        _ISSUANCE.visible_positive_high_water_bytes = _ISSUANCE.visible_budget_overshoot_bytes = None
        for root, observed in zip(_ISSUANCE.roots, _ISSUANCE.resources[sample]["roots"]):
            root.guid = root.baseline_identity = root.baseline_total_free = root.baseline_raw = None
            root.visible_high_water_bytes = None
            observed.visible_delta_bytes = observed.visible_high_water_bytes = None
        self.baseline_topology = None
        self.baseline_installed = False
        self.visible_positive_high_water_bytes = self.visible_budget_overshoot_bytes = None
        sample.visible_positive_high_water_bytes = sample.visible_budget_overshoot_bytes = None

    def _derive_visible(self, sample):
        roots = _ISSUANCE.resources[sample]["roots"]
        if _ISSUANCE.baseline is None:
            return
        # A failed peer leaves this a lower bound and the snapshot UNKNOWN;
        # it cannot erase a completed original volume observation or its peak.
        for index, (fact, observed) in enumerate(zip(_ISSUANCE.baseline_facts, roots)):
            root, _, _, _, free = fact
            current = _ISSUANCE.validated_observations[observed]
            if current is not None and current[:2] == fact[2:4]:
                observed.visible_delta_bytes = max(0, free - current[2])
                _ISSUANCE.high_water_bytes[index] = max(_ISSUANCE.high_water_bytes[index], observed.visible_delta_bytes)
            root.visible_high_water_bytes = observed.visible_high_water_bytes = _ISSUANCE.high_water_bytes[index]
        _ISSUANCE.visible_positive_high_water_bytes = sum(_ISSUANCE.high_water_bytes)
        _ISSUANCE.visible_budget_overshoot_bytes = max(0, _ISSUANCE.visible_positive_high_water_bytes - _REPORT_BUDGET_BYTES)
        self.visible_positive_high_water_bytes = _ISSUANCE.visible_positive_high_water_bytes
        self.visible_budget_overshoot_bytes = _ISSUANCE.visible_budget_overshoot_bytes
        sample.visible_positive_high_water_bytes = self.visible_positive_high_water_bytes
        sample.visible_budget_overshoot_bytes = self.visible_budget_overshoot_bytes
        if _ISSUANCE.visible_positive_high_water_bytes >= _WARNING_BYTES:
            self.stop_latched = _ISSUANCE.stop_latched = True
            if _ISSUANCE.threshold_origin is None:
                _ISSUANCE.threshold_origin = self.threshold_origin = sample
                frame = _ISSUANCE.resources[sample]
                frame["warning"].exception = self.stop_error  # Retain before report helper.
                try:
                    recording = _ISSUANCE.record(_ISSUANCE.owner, frame["warning"].operation, self.stop_error)
                    if recording is not None:
                        _invoke(self, "_retain", frame["warning_dispatch"], recording, sample)
                except BaseException as error:
                    _invoke(self, "_retain", frame["warning_dispatch"], error, sample)

    def _new_work_guard(self):
        if _ISSUANCE.unknown or _ISSUANCE.stop_latched or _ISSUANCE.close_attempted:
            self.unknown, self.stop_latched = _ISSUANCE.unknown, _ISSUANCE.stop_latched
            self.first_error, self.threshold_origin = _ISSUANCE.first_error, _ISSUANCE.threshold_origin
            raise _ISSUANCE.first_error if _ISSUANCE.first_error is not None else self.stop_error
        _invoke(self, "_sample")
        if _ISSUANCE.baseline is None or _ISSUANCE.unknown or _ISSUANCE.stop_latched:
            raise _ISSUANCE.first_error if _ISSUANCE.first_error is not None else self.stop_error

    def _cleanup_observation(self):
        # No threshold/unknown exception can bypass original Job termination,
        # wait or the other handle consumers. Continue actual bounded sampling.
        _invoke(self, "_sample", cleanup=True)

    def _close_once(self):
        if _ISSUANCE.close_attempted:
            self.close_attempted, self.closed = True, _ISSUANCE.closed
            self.unknown, self.stop_latched = _ISSUANCE.unknown, _ISSUANCE.stop_latched
            self.first_error, self.threshold_origin = _ISSUANCE.first_error, _ISSUANCE.threshold_origin
            return
        drift = (self.close_attempted or self.closed != _ISSUANCE.closed
            or self.unknown != _ISSUANCE.unknown or self.stop_latched != _ISSUANCE.stop_latched
            or self.first_error is not _ISSUANCE.first_error or self.threshold_origin is not _ISSUANCE.threshold_origin
            or _invoke(self, "_resource_drift"))
        self.close_attempted = _ISSUANCE.close_attempted = True
        self.unknown, self.stop_latched = _ISSUANCE.unknown, _ISSUANCE.stop_latched
        self.first_error, self.threshold_origin = _ISSUANCE.first_error, _ISSUANCE.threshold_origin
        if drift:
            _invoke(self, "_retain", _ISSUANCE.close_binding, self.binding_error)
        # Sweep retained original holders after a temporary read, formatter or
        # dispatch failed. Already-consumed numbers are never retried. Each
        # consumer is independent, including the dedicated search-handle API.
        for sample in _ISSUANCE.samples:
            frame = _ISSUANCE.resources[sample]
            for observed in frame["roots"]:
                observed_frame = _ISSUANCE.resources[observed]
                for read in (observed_frame["current_guid"], observed_frame["current_dos"]):
                    closed = _ISSUANCE.resources[read]["close"]
                    try:
                        _invoke(self, "_close_root_read", read, sample)
                    except BaseException as error:
                        closed.recording_error = error
                        self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
                        _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"
            try:
                _invoke(self, "_close_enumeration", sample)
            except BaseException as error:
                frame["find_close"].recording_error = error
                self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
                _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"
        for root in reversed(_ISSUANCE.roots):
            frame = _ISSUANCE.resources[root]
            closed = frame["close"]
            try:
                handle = _invoke(self, "_consume_open", frame["open"], frame["handle"], frame["consume"], None)
                if handle:
                    _invoke(self, "_call", closed, "CloseHandle", (handle,), None, handle)
                    _invoke(self, "_require", closed, None)
            except BaseException as error:
                if closed.exception is None:
                    try:
                        _invoke(self, "_retain", closed, error)
                    except BaseException as recording:
                        closed.recording_error = recording
                        self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
                        _ISSUANCE.owner.quarantine = "UNKNOWN"
                _ISSUANCE.owner.cleanup_integrity_lost = True
        pending = any(_ISSUANCE.resources[root]["open"].acquired
            and not _ISSUANCE.resources[root]["open"].consumed for root in _ISSUANCE.roots)
        for sample in _ISSUANCE.samples:
            frame = _ISSUANCE.resources[sample]
            opened = _ISSUANCE.resources[frame["volumes"][0]]["find_call"]
            pending = pending or (opened.acquired and not opened.consumed)
            for observed in frame["roots"]:
                observed_frame = _ISSUANCE.resources[observed]
                pending = pending or any(_ISSUANCE.resources[read]["open"].acquired
                    and not _ISSUANCE.resources[read]["open"].consumed
                    for read in (observed_frame["current_guid"], observed_frame["current_dos"]))
        self.closed = _ISSUANCE.closed = not pending  # Consumed attempts are never clean-closure proof.
        if pending:
            self.unknown = self.stop_latched = _ISSUANCE.unknown = _ISSUANCE.stop_latched = True
            _ISSUANCE.owner.cleanup_integrity_lost, _ISSUANCE.owner.quarantine = True, "UNKNOWN"


_ORIGINAL_METHODS = _MappingProxyType({name: method for name, method
    in _FixedNonEMonitor.__dict__.items() if name.startswith("_") and callable(method)})


def _registered_monitor(owner):
    return _ISSUANCE.monitor if owner is _ISSUANCE.owner else None


def _guard_original_monitor(owner):
    monitor = _registered_monitor(owner)
    if monitor is None:
        raise PermissionError("original non-E component is not installed")
    _invoke(monitor, "_new_work_guard")


def _observe_original_cleanup(owner):
    monitor = _registered_monitor(owner)
    if monitor is not None:
        _invoke(monitor, "_cleanup_observation")


def _close_original_monitor(owner):
    monitor = _registered_monitor(owner)
    if monitor is not None:
        _invoke(monitor, "_close_once")


def _install_for_original_owner(owner):
    """Issue raw component once; never create an earlier installation boundary."""
    from .windows_preparation_job import (
        _KernelOwner, _NativeFault, _ORIGINAL_OWNER, _ORIGINAL_KERNEL,
        _ORIGINAL_NATIVE, _ORIGINAL_IDENTITY, _ORIGINAL_EPOCH, _ORIGINAL_RECORD,
        _native_function, _native_drifted)

    global _FAULT_CLASS
    if (type(owner) is not _KernelOwner or owner is not _ORIGINAL_OWNER
            or owner.kernel is not _ORIGINAL_KERNEL or _ISSUANCE.owner is not None
            or owner.non_e_monitor is not None or not owner.attempted
            or owner.started_ticks <= 0 or owner.frequency.value <= 0
            or owner.stop_ticks != owner.started_ticks + 60 * owner.frequency.value
            or owner.cleanup_ticks != owner.started_ticks + 70 * owner.frequency.value):
        raise PermissionError("non-E monitor requires the original once-only private native owner")
    if ((owner.owner_pid, owner.owner_tid) != _ORIGINAL_IDENTITY
            or (owner.owner_pid, owner.owner_tid, owner.started_ticks,
                owner.frequency.value, owner.stop_ticks, owner.cleanup_ticks) != _ORIGINAL_EPOCH
            or _ORIGINAL_NATIVE is None or _native_drifted()):
        raise PermissionError("original non-E native binding/identity is unknown")
    if (_c.sizeof(_FileIdInfo) != 24 or _FileIdInfo.FileId.offset != 8
            or _c.sizeof(_FileStandardInfo) != 24 or _c.sizeof(_FileAttributeTagInfo) != 8):
        raise PermissionError("fixed non-E monitor Win32 structure ABI differs")
    _FAULT_CLASS = _NativeFault
    _ISSUANCE.owner, _ISSUANCE.kernel = owner, owner.kernel
    _ISSUANCE.native, _ISSUANCE.native_function, _ISSUANCE.native_drifted = (
        _ORIGINAL_NATIVE, _native_function, _native_drifted)
    _ISSUANCE.methods = _ORIGINAL_METHODS
    _ISSUANCE.record = _ORIGINAL_RECORD
    _ISSUANCE.epoch = _ORIGINAL_EPOCH
    monitor = _FixedNonEMonitor()  # Complete buffers/error storage before any handle.
    _ISSUANCE.monitor = owner.non_e_monitor = monitor
    _ISSUANCE.roots, _ISSUANCE.samples, _ISSUANCE.faults = monitor.roots, monitor.samples, monitor.native_faults
    _ISSUANCE.root_paths = tuple((root.mount_path, root.open_path) for root in _ISSUANCE.roots)
    # Preserve acquisition/consumer/close and raw-frame references independently
    # of every public attribute before the first native acquisition can occur.
    references = {}
    for root in _ISSUANCE.roots:
        references[root] = {name: getattr(root, name)
            for name in ("open", "handle", "consume", "close")}
    for sample in _ISSUANCE.samples:
        references[sample] = {name: getattr(sample, name) for name in (
            "roots", "volumes", "owner_pid", "owner_tid", "start_call", "end_call",
            "start_counter", "end_counter", "find_handle", "find_consume", "find_close",
            "topology_dispatch", "dispatch", "end_dispatch", "binding_dispatch", "reuse_dispatch",
            "commit_dispatch", "warning", "warning_dispatch", "validation_error")}
        for observed in sample.roots:
            references[observed] = {name: getattr(observed, name) for name in (
                "held_before", "held_after", "current_dos", "current_guid",
                "mount_before", "mount_after", "mount_before_call", "mount_after_call",
                "drive_type", "available", "caller_total", "total_free", "free_call",
                "free_dispatch", "dispatch")}
            for read in (observed.held_before, observed.held_after, observed.current_dos, observed.current_guid):
                references[read] = {name: getattr(read, name) for name in (
                    "open", "owned_handle", "consume", "close", "file_type", "tag_call",
                    "standard_call", "id_call", "path_call", "tags", "standard", "identity", "guid_buffer")}
        for entry in sample.volumes:
            references[entry] = {name: getattr(entry, name) for name in ("find_call", "type_call", "buffer")}
    for attributes in tuple(references.values()):
        consume = attributes.get("consume", attributes.get("find_consume"))
        if consume is not None:
            references[consume] = {"owner_pid": consume.owner_pid, "owner_tid": consume.owner_tid}
    _ISSUANCE.resources = _MappingProxyType({source: _MappingProxyType(attributes)
        for source, attributes in references.items()})
    _ISSUANCE.validated_observations = {observed: None for sample in _ISSUANCE.samples
        for observed in _ISSUANCE.resources[sample]["roots"]}
    owner.capture.failure.non_e_raw_samples = monitor.samples
    owner.capture.failure.non_e_held_roots = monitor.roots
    owner.capture.failure.non_e_native_faults = monitor.native_faults
    _invoke(monitor, "_sample")
    if _ISSUANCE.baseline is None or _ISSUANCE.unknown or _ISSUANCE.stop_latched:
        raise _ISSUANCE.first_error if _ISSUANCE.first_error is not None else monitor.stop_error
    return monitor


_ORIGINAL_DISPATCH = _MappingProxyType({
    "install": _install_for_original_owner, "registered": _registered_monitor,
    "guard": _guard_original_monitor, "observe": _observe_original_cleanup,
    "close": _close_original_monitor})
