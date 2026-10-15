"""One readonly native snapshot of E: and its actual backing disk handles.

This producer performs real Win32 queries through the already-loaded, fixed
libffi gate.  It never loads a DLL, compiles, starts a process, reads sectors,
creates a directory, mounts a volume, or changes a disk.  Construction only
preallocates storage/calls.  The original owner must prepare the gate and run
``collect_once`` within its existing identity, resource, absolute-clock and
independent deadline boundary.  Integer clock arguments are raw inputs, never
an authorization or a replacement lease.  Cooperative QPC checks cannot bound
a synchronous driver call; the external owner remains responsible for it.

Read sharing is READ|WRITE so ordinary concurrent OS activity is not denied.
The actual original HANDLEs are retained until one consumed close attempt.
Equal before/after bytes establish endpoint agreement only, not continuous
identity, absence of ABA, physical exclusivity, all-writer accounting or a
capacity mechanism.  A disk GUID is reported as bytes, not a unique hardware
identity.  This module cannot declare admission or select a disk to modify.
The mount GUID is an E:\\ path query; it is explicitly NOT bound to the
retained volume HANDLE used by filesystem metadata and extent queries.  A
remap can mix those origins even when both endpoint observations agree.

Declarations: Microsoft Win32 SDK winioctl.h (native Win64, default pack 8):
https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/winioctl.h
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-deviceiocontrol
https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents
https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-drive_layout_information_ex
https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-partition_information_ex
https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-storage_access_alignment_descriptor

The direct gate preserves native return/output storage, but does not prove
LastError preservation: every error code below is explicitly UNKNOWN.  Failed
or short queries are never parsed as geometry.  Missing support/permission is
UNKNOWN, not proof that this machine cannot support the selected mechanism.
All native/provider/kernel/monitor/tail charges remain in the original scope;
this source does not measure them and never substitutes zero for unknown.
"""

from __future__ import annotations

import ctypes as _c
import re as _re
import struct as _s
from types import MappingProxyType as _Map

from .windows_compile_free_gate import _LoadedWin64Gate

_U32, _U64, _P = _c.c_uint32, _c.c_uint64, _c.c_void_p
_I64_MAX = (1 << 63) - 1
_INVALID_HANDLE = (1 << 64) - 1
_MAX_EXTENTS, _MAX_PARTITIONS = 8, 128
_LAYOUT_BYTES, _GEOMETRY_BYTES, _ALIGN_BYTES = 32768, 512, 256
_EXTENTS_BYTES = 8 + 24 * _MAX_EXTENTS
_LIVE_PROBE = None                    # Retains all original raw slots forever.
_MEMMOVE, _STRING_AT = _c.memmove, _c.string_at
_IOCTL_EXTENTS = 0x00560000
_IOCTL_GEOMETRY = 0x000700A0
_IOCTL_LAYOUT = 0x00070050
_IOCTL_PROPERTY = 0x002D1400
_IOCTL_DEVICE_NUMBER = 0x002D1080
_UNKNOWN_ERROR = "UNKNOWN_DIRECT_LIBFFI_LAST_ERROR"
_GUID_PATH = _re.compile(r"\\\\\?\\Volume\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
                         r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}\\")


class _Guid(_c.Structure):
    _fields_ = [("a", _U32), ("b", _c.c_uint16), ("c", _c.c_uint16),
                ("d", _c.c_uint8 * 8)]


class _DiskExtent(_c.Structure):
    _fields_ = [("disk", _U32), ("offset", _c.c_int64), ("length", _c.c_int64)]


class _PartitionGpt(_c.Structure):
    _fields_ = [("kind", _Guid), ("id", _Guid), ("attributes", _U64),
                ("name", _c.c_uint16 * 36)]


class _PartitionMbr(_c.Structure):
    _fields_ = [("kind", _c.c_uint8), ("boot", _c.c_uint8),
                ("recognized", _c.c_uint8), ("hidden", _U32), ("id", _Guid)]


class _PartitionUnion(_c.Union):
    _fields_ = [("gpt", _PartitionGpt), ("mbr", _PartitionMbr)]


class _PartitionEx(_c.Structure):
    _fields_ = [("style", _U32), ("offset", _c.c_int64),
                ("length", _c.c_int64), ("number", _U32),
                ("rewrite", _c.c_uint8), ("service", _c.c_uint8),
                ("detail", _PartitionUnion)]


class _LayoutGpt(_c.Structure):
    _fields_ = [("id", _Guid), ("offset", _c.c_int64),
                ("length", _c.c_int64), ("max_count", _U32)]


class _LayoutUnion(_c.Union):
    _fields_ = [("gpt", _LayoutGpt), ("mbr", _U32 * 2)]


class _LayoutPrefix(_c.Structure):
    _fields_ = [("style", _U32), ("count", _U32), ("detail", _LayoutUnion)]


def _layout_ok():
    # These are runtime ctypes guards, NOT compiled ABI validation evidence.
    expected = ((_Guid, 16, (0, 4, 6, 8)),
                (_DiskExtent, 24, (0, 8, 16)),
                (_PartitionGpt, 112, (0, 16, 32, 40)),
                (_PartitionMbr, 24, (0, 1, 2, 4, 8)),
                (_PartitionEx, 144, (0, 8, 16, 24, 28, 29, 32)),
                (_LayoutGpt, 40, (0, 16, 24, 32)),
                (_LayoutPrefix, 48, (0, 4, 8)))
    return (_c.sizeof(_P) == 8 and all(_c.sizeof(t) == size and
            tuple(getattr(t, n).offset for n, _ in t._fields_) == offsets
            for t, size, offsets in expected))


def _integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("bounded exact integer required")
    return value


def _span(offset, length, limit):
    if offset < 0 or length < 0 or offset > limit or length > limit - offset:
        raise ValueError("native byte range exceeds its original buffer")


def _u32(raw, offset):
    _span(offset, 4, len(raw))
    return _s.unpack_from("<I", raw, offset)[0]


def _i64(raw, offset):
    _span(offset, 8, len(raw))
    return _s.unpack_from("<q", raw, offset)[0]


def _terminated_utf16(raw):
    if len(raw) % 2:
        raise ValueError("odd native WCHAR buffer size")
    end = next((i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0"), None)
    if end is None:
        raise ValueError("native WCHAR output has no bounded terminator")
    return raw[:end].decode("utf-16-le", "strict")


def _extents(raw):
    if len(raw) < 8:
        raise ValueError("truncated VOLUME_DISK_EXTENTS header")
    count = _u32(raw, 0)
    if not 1 <= count <= _MAX_EXTENTS or len(raw) < 8 + 24 * count:
        raise ValueError("unsupported or truncated physical extent count")
    rows = []
    for i in range(count):
        p = 8 + 24 * i
        disk, offset, length = _u32(raw, p), _i64(raw, p + 8), _i64(raw, p + 16)
        if offset < 0 or length <= 0 or offset > _I64_MAX - length:
            raise ValueError("invalid signed disk extent")
        rows.append((disk, offset, length))
    if len(set(rows)) != len(rows):
        raise ValueError("duplicate physical extents")
    for disk in {r[0] for r in rows}:
        previous = None
        for _, offset, length in sorted(r for r in rows if r[0] == disk):
            if previous is not None and offset < previous:
                raise ValueError("overlapping extents on one physical disk")
            previous = offset + length
    return tuple(rows)


def _geometry(raw):
    if len(raw) < 32:
        raise ValueError("truncated DISK_GEOMETRY_EX")
    cylinders, disk_bytes = _i64(raw, 0), _i64(raw, 24)
    media, tracks, sectors, sector_bytes = (_u32(raw, n) for n in (8, 12, 16, 20))
    if cylinders < 0 or disk_bytes <= 0 or sector_bytes == 0 or disk_bytes % sector_bytes:
        raise ValueError("invalid native disk size or logical sector size")
    # CHS values are driver-reported geometry, not physical capacity arithmetic.
    return _Map({"cylinders": cylinders, "media_type": media,
                 "tracks_per_cylinder": tracks, "sectors_per_track": sectors,
                 "logical_sector_bytes": sector_bytes, "disk_bytes": disk_bytes})


def _alignment(raw, geometry):
    if len(raw) < 28:
        raise ValueError("truncated STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR")
    version, size, cache, cache_offset, logical, physical, sector_offset = (
        _u32(raw, n) for n in range(0, 28, 4))
    if not 28 <= version <= size <= len(raw):
        raise ValueError("invalid alignment descriptor version/size")
    if (logical == 0 or physical == 0 or physical % logical or
            physical < logical or sector_offset >= physical or
            sector_offset % logical or logical != geometry["logical_sector_bytes"] or
            (cache == 0 and cache_offset != 0) or (cache and cache_offset >= cache)):
        raise ValueError("invalid or inconsistent native sector alignment")
    return _Map({"version": version, "size": size, "cache_line_bytes": cache,
                 "cache_offset_bytes": cache_offset, "logical_sector_bytes": logical,
                 "physical_sector_bytes": physical, "sector_offset_bytes": sector_offset})


def _layout(raw, geometry):
    if len(raw) < 48:
        raise ValueError("truncated DRIVE_LAYOUT_INFORMATION_EX")
    style, count = _u32(raw, 0), _u32(raw, 4)
    if style not in (0, 1, 2) or count > _MAX_PARTITIONS or len(raw) < 48 + 144 * count:
        raise ValueError("unsupported or truncated partition layout")
    disk_bytes, sector = geometry["disk_bytes"], geometry["logical_sector_bytes"]
    entries, occupied = [], []
    for i in range(count):
        p = 48 + 144 * i
        row = raw[p:p + 144]
        part_style, offset, length = _u32(row, 0), _i64(row, 8), _i64(row, 16)
        number = _u32(row, 24)
        if (part_style not in (0, 1, 2) or offset < 0 or length < 0 or
                offset > disk_bytes or length > disk_bytes - offset or
                offset % sector or length % sector or row[28] not in (0, 1) or
                row[29] not in (0, 1)):
            raise ValueError("invalid partition offset/length/flags")
        if length and part_style != style:
            raise ValueError("partition style disagrees with containing disk")
        if length:
            occupied.append((offset, offset + length))
        entries.append(_Map({"style": part_style, "offset": offset, "length": length,
                             "number": number, "rewrite": row[28], "service": row[29],
                             "gpt_type_guid_bytes": row[32:48] if part_style == 1 else None,
                             "gpt_partition_guid_bytes": row[48:64] if part_style == 1 else None,
                             "gpt_attributes": _s.unpack_from("<Q", row, 64)[0] if part_style == 1 else None,
                             "gpt_name_bytes": row[72:144] if part_style == 1 else None,
                             "mbr_kind": row[32] if part_style == 0 else None,
                             "mbr_boot": row[33] if part_style == 0 else None,
                             "mbr_recognized": row[34] if part_style == 0 else None,
                             "mbr_hidden_sectors": _u32(row, 36) if part_style == 0 else None,
                             "mbr_partition_guid_bytes": row[40:56] if part_style == 0 else None,
                             "raw": row}))
    disk_guid, usable, max_count, gaps, gap_state = None, None, None, None, "UNKNOWN_NOT_GPT_USABLE_REGION"
    if style == 1:
        disk_guid = raw[8:24]
        start, length, max_count = _i64(raw, 24), _i64(raw, 32), _u32(raw, 40)
        if (start < 0 or length <= 0 or start > disk_bytes or length > disk_bytes - start or
                start % sector or length % sector or max_count < count):
            raise ValueError("invalid GPT usable geometry")
        usable, cursor, gap_rows = (start, length), start, []
        for lo, hi in sorted(occupied):
            if lo < start or hi > start + length or lo < cursor:
                raise ValueError("overlapping partitions or partitions outside GPT usable region")
            if lo > cursor:
                gap_rows.append((cursor, lo - cursor))
            cursor = hi
        if cursor < start + length:
            gap_rows.append((cursor, start + length - cursor))
        gaps, gap_state = tuple(gap_rows), "GPT_ENDPOINT_PARTITION_GAPS_ONLY"
    # MBR extended/container entries overlap logical partitions legitimately;
    # never infer writable free extents from that representation.
    return _Map({"style": style, "partition_count": count, "disk_guid_bytes": disk_guid,
                 "mbr_signature": _u32(raw, 8) if style == 0 else None,
                 "mbr_checksum": _u32(raw, 12) if style == 0 else None,
                 "gpt_usable_region": usable, "gpt_max_partition_count": max_count,
                 "entries": tuple(entries),
                 "unallocated_partition_gaps": gaps, "gap_state": gap_state})


def _volume_identity(snapshot):
    return tuple(snapshot[n] for n in ("mount_guid_path", "label", "filesystem", "serial",
                                      "max_component_chars", "filesystem_flags",
                                      "mount_guid_path_origin")) + (
        tuple(sorted(snapshot["extents"])),)


def _disk_identity(snapshot):
    layout = snapshot["layout"]
    # Ignore ABI padding and optional geometry Data[] bytes in equality, while
    # retaining every returned byte as provenance.  They are not identities.
    partition_keys = ("style", "offset", "length", "number", "rewrite", "service",
                      "gpt_type_guid_bytes", "gpt_partition_guid_bytes", "gpt_attributes",
                      "gpt_name_bytes", "mbr_kind", "mbr_boot", "mbr_recognized",
                      "mbr_hidden_sectors", "mbr_partition_guid_bytes")
    return (snapshot["disk_number"], snapshot["native_device_number"], tuple(snapshot["geometry"].items()),
            tuple(snapshot["alignment"].items()), layout["style"], layout["partition_count"],
            layout["disk_guid_bytes"], layout["mbr_signature"], layout["mbr_checksum"],
            layout["gpt_usable_region"], layout["gpt_max_partition_count"],
            tuple(tuple(row[n] for n in partition_keys) for row in layout["entries"]))


class _Arena:
    __slots__ = ("output", "base", "size")

    def __init__(self, gate, size):
        self.output = gate.output(size)
        self.base, self.size = _c.addressof(self.output.storage), size

    def pointer(self, offset, length=1):
        _span(offset, length, self.size)
        return _P(self.base + offset)

    def put(self, offset, raw):
        _span(offset, len(raw), self.size)
        _MEMMOVE(self.base + offset, raw, len(raw))

    def bytes(self, offset, length):
        _span(offset, length, self.size)
        return _STRING_AT(self.base + offset, length)


class _Query:
    __slots__ = ("label", "clock", "clock_offset", "call", "arena", "offset", "size", "returned_offset")

    def __init__(self, label, clock, clock_offset, call, arena=None, offset=0,
                 size=0, returned_offset=None):
        self.label, self.clock, self.clock_offset, self.call = label, clock, clock_offset, call
        self.arena, self.offset, self.size, self.returned_offset = arena, offset, size, returned_offset


class _ReadonlyEStorageProbe:
    """Actual query producer; raw outputs have no admission/capacity authority.

    Create this object before the original gate's single ``prepare_once``;
    collect after preparation, never before the upstream owner has installed
    the real independent deadline and resource/identity boundary.  No boolean
    claim or type/profile string can certify those upstream conditions here.
    """

    __slots__ = ("gate", "epoch", "frequency", "stop", "cleanup", "meta", "clocks",
                 "queries", "disk_slots", "volume", "volume_close", "close_clocks",
                 "qpf", "start_clock", "normal_end_clock", "end_clock", "end_offset", "_clock_next", "_started", "_last_qpc",
                 "_observed", "_primary", "_close_faults", "_end_faults", "_raw_calls",
                 "_report", "_baseline", "_after", "_disk_before", "_disk_after", "_stage",
                 "_primary_stage", "_close_fault_count", "_cleanup_slots", "_volume_fallback")

    def __init__(self, gate, *, original_epoch_qpc, qpc_frequency, stop_qpc, cleanup_qpc):
        global _LIVE_PROBE
        if (type(gate) is not _LoadedWin64Gate or gate._prepare_attempted or
                _LIVE_PROBE is not None or not _layout_ok()):
            raise TypeError("original unprepared Win64 gate and exact SDK layout required")
        self.gate = gate
        self.epoch = _integer(original_epoch_qpc, 0, _I64_MAX)
        self.frequency = _integer(qpc_frequency, 1, _I64_MAX)
        self.stop = _integer(stop_qpc, self.epoch + 1, _I64_MAX)
        self.cleanup = _integer(cleanup_qpc, self.stop + 1, _I64_MAX)
        self._started, self._last_qpc, self._report = False, None, None
        self._observed, self._primary, self._primary_stage = [], None, None
        self._close_faults = [[None, None] for _ in range(32)]
        self._close_fault_count = 0
        self._end_faults = [None]
        self._raw_calls, self._baseline, self._after = [], None, None
        self._disk_before, self._disk_after = [], []
        self._stage = "unstarted"
        self._clock_next = 0
        self.meta, self.clocks = _Arena(gate, 8192), _Arena(gate, 4096)
        self.meta.put(0, "E:\\".encode("utf-16-le") + b"\0\0")
        self.meta.put(64, "\\\\.\\E:".encode("utf-16-le") + b"\0\0")
        self.meta.put(6016, _s.pack("<III", 6, 0, 0))  # AlignmentProperty, StandardQuery.
        self.start_clock = self._clock()
        self.qpf = gate.new_call("QueryPerformanceFrequency", (self.meta.pointer(6032, 8),))
        self.volume = gate.new_call("CreateFileW", (self.meta.pointer(64, 16), _U32(0x80000000),
            _U32(3), _P(), _U32(3), _U32(), _P()))  # GENERIC_READ, share R/W, OPEN_EXISTING.
        self.volume_close = gate.own_handle(self.volume.result_reference)
        self._volume_fallback = self._fallback_storage()
        self.queries = {"open_volume": self._query("open_volume", self.volume)}
        self.queries["mount_before"] = self._mount("mount_before", 128)
        self.queries["mount_after"] = self._mount("mount_after", 640)
        self.queries["volume_before"] = self._volume_info("volume_before", 1152)
        self.queries["volume_after"] = self._volume_info("volume_after", 2304)
        self.queries["extents_before"] = self._ioctl("extents_before", self.volume.result_reference,
            _IOCTL_EXTENTS, self.meta, 3456, _EXTENTS_BYTES, self.meta, 6000)
        self.queries["extents_after"] = self._ioctl("extents_after", self.volume.result_reference,
            _IOCTL_EXTENTS, self.meta, 3712, _EXTENTS_BYTES, self.meta, 6004)
        slots = []
        for i in range(_MAX_EXTENTS):
            metadata, layouts = _Arena(gate, 4096), _Arena(gate, 65536)
            birth = gate.new_call("CreateFileW", (metadata.pointer(0, 128), _U32(0x80000000),
                _U32(3), _P(), _U32(3), _U32(), _P()))
            close = gate.own_handle(birth.result_reference)
            slot = {"meta": metadata, "layouts": layouts, "birth": self._query("disk_open", birth),
                    "close": close, "number": None, "fallback": self._fallback_storage()}
            for suffix, geo, align, layout, returned in (
                    ("before", 256, 1792, 0, 2600), ("after", 1024, 2304, 32768, 2604)):
                slot["geometry_" + suffix] = self._ioctl("disk_geometry_" + suffix,
                    birth.result_reference, _IOCTL_GEOMETRY, metadata, geo, _GEOMETRY_BYTES,
                    metadata, geo + _GEOMETRY_BYTES)
                slot["alignment_" + suffix] = self._ioctl("disk_alignment_" + suffix,
                    birth.result_reference, _IOCTL_PROPERTY, metadata, align, _ALIGN_BYTES,
                    metadata, align + _ALIGN_BYTES, property_query=True)
                slot["layout_" + suffix] = self._ioctl("disk_layout_" + suffix,
                    birth.result_reference, _IOCTL_LAYOUT, layouts, layout, _LAYOUT_BYTES,
                    metadata, returned)
                device_offset = 2800 if suffix == "before" else 2816
                slot["device_number_" + suffix] = self._ioctl("disk_device_number_" + suffix,
                    birth.result_reference, _IOCTL_DEVICE_NUMBER, metadata, device_offset, 12,
                    metadata, device_offset + 64)
            slots.append(slot)
        self.disk_slots = tuple(slots)
        self.close_clocks = tuple(self._clock() for _ in range(9))
        self._cleanup_slots = tuple((i, self.disk_slots[i], self.close_clocks[i + 1])
                                    for i in range(7, -1, -1))
        self.normal_end_clock = self._clock()
        self.end_clock, self.end_offset = self._clock()
        # Exactly 18 arenas: 8192+4096+8*(4096+65536)=569344 bytes.
        # Nine separately retained byte-check scratch buffers add 72 bytes.
        # Exactly 180 one-shot gate calls including 9 prebuilt CloseHandle calls.
        # Python objects/libffi/providers/kernel/etc are additional original-scope charges.
        _LIVE_PROBE = self

    def _clock(self):
        offset = self._clock_next
        _span(offset, 8, self.clocks.size)
        self._clock_next += 8
        return (self.gate.new_call("QueryPerformanceCounter", (self.clocks.pointer(offset, 8),)), offset)

    def _query(self, label, call, arena=None, offset=0, size=0, returned_offset=None):
        clock, clock_offset = self._clock()
        return _Query(label, clock, clock_offset, call, arena, offset, size, returned_offset)

    def _mount(self, label, offset):
        call = self.gate.new_call("GetVolumeNameForVolumeMountPointW",
            (self.meta.pointer(0, 8), self.meta.pointer(offset, 512), _U32(256)))
        return self._query(label, call, self.meta, offset, 512)

    def _volume_info(self, label, offset):
        call = self.gate.new_call("GetVolumeInformationByHandleW", (self.volume.result_reference,
            self.meta.pointer(offset, 512), _U32(256), self.meta.pointer(offset + 1024, 4),
            self.meta.pointer(offset + 1028, 4), self.meta.pointer(offset + 1032, 4),
            self.meta.pointer(offset + 512, 512), _U32(256)))
        return self._query(label, call, self.meta, offset, 1036)

    def _ioctl(self, label, handle, code, arena, offset, size, returned_arena,
               returned_offset, *, property_query=False):
        call = self.gate.new_call("DeviceIoControl", (handle, _U32(code),
            self.meta.pointer(6016, 12) if property_query else _P(),
            _U32(12 if property_query else 0), arena.pointer(offset, size), _U32(size),
            returned_arena.pointer(returned_offset, 4), _P()))
        query = self._query(label, call, arena, offset, size, (returned_arena, returned_offset))
        return query

    def _stamp(self, call, offset, *, cleanup=False):
        call.invoke_once()
        if not call.result.value:
            raise ValueError("native QPC returned false; LastError UNKNOWN")
        value = _i64(self.clocks.bytes(offset, 8), 0)
        if value < self.epoch or (self._last_qpc is not None and value < self._last_qpc):
            raise ValueError("native QPC precedes original epoch or regressed")
        self._last_qpc = value
        self._observed.append(value)
        if value >= (self.cleanup if cleanup else self.stop):
            raise TimeoutError("original absolute storage query/cleanup deadline reached")
        return value

    def _run(self, query, *, handle=False):
        self._stage = query.label
        self._stamp(query.clock, query.clock_offset)
        query.call.invoke_once()
        result = query.call.result.value
        # Record return provenance before parsing any output, never errno fiction.
        self._raw_calls.append((query.label, result, _UNKNOWN_ERROR))
        if (handle and result in (0, _INVALID_HANDLE)) or (not handle and not result):
            raise OSError("native readonly query failed; support/permission/LastError UNKNOWN")
        if query.arena is None:
            return None
        size = query.size
        if query.returned_offset is not None:
            arena, offset = query.returned_offset
            size = _u32(arena.bytes(offset, 4), 0)
            if not 0 < size <= query.size:
                raise ValueError("native bytesReturned exceeds original output or is zero")
        return query.arena.bytes(query.offset, size)

    def _volume_snapshot(self, suffix):
        mount = _terminated_utf16(self._run(self.queries["mount_" + suffix]))
        if _GUID_PATH.fullmatch(mount) is None:
            raise ValueError("native volume GUID path malformed")
        info = self._run(self.queries["volume_" + suffix])
        label, filesystem = _terminated_utf16(info[:512]), _terminated_utf16(info[512:1024])
        if not filesystem:
            raise ValueError("native filesystem name is empty")
        extents_raw = self._run(self.queries["extents_" + suffix])
        return _Map({"mount_guid_path": mount,
                     "mount_guid_path_origin": "E_PATH_QUERY_NOT_BOUND_TO_HELD_VOLUME_HANDLE",
                     "label": label, "filesystem": filesystem,
                     "serial": _u32(info, 1024), "max_component_chars": _u32(info, 1028),
                     "filesystem_flags": _u32(info, 1032), "extents": _extents(extents_raw),
                     "extents_raw": extents_raw,
                     "volume_unique_id": "UNKNOWN_NOT_QUERIED_NO_WDK_HEADER_BINDING"})

    def _disk_snapshot(self, slot, suffix):
        device_raw = self._run(slot["device_number_" + suffix])
        if len(device_raw) != 12:
            raise ValueError("invalid STORAGE_DEVICE_NUMBER byte count")
        device = tuple(_u32(device_raw, n) for n in (0, 4, 8))
        if device[0] != 7 or device[1] != slot["number"]:
            raise ValueError("original physical disk HANDLE disagrees with actual extent disk number")
        geometry_raw = self._run(slot["geometry_" + suffix])
        geometry = _geometry(geometry_raw)
        alignment_raw = self._run(slot["alignment_" + suffix])
        alignment = _alignment(alignment_raw, geometry)
        layout_raw = self._run(slot["layout_" + suffix])
        layout = _layout(layout_raw, geometry)
        for disk, offset, length in self._baseline["extents"]:
            if disk == slot["number"] and (offset > geometry["disk_bytes"] or
                    length > geometry["disk_bytes"] - offset or
                    offset % geometry["logical_sector_bytes"] or
                    length % geometry["logical_sector_bytes"]):
                raise ValueError("actual E extent exceeds backing geometry/alignment")
        return _Map({"disk_number": slot["number"], "native_device_number": device,
                     "geometry": geometry, "alignment": alignment,
                     "layout": layout, "geometry_raw": geometry_raw,
                     "alignment_raw": alignment_raw, "layout_raw": layout_raw})

    def _close(self, close, clock):
        try:
            self._stamp(*clock, cleanup=True)
        except BaseException as exc:
            self._record_close("preclose_clock", exc)
        # Mandatory single cleanup attempt even when deadline observation failed;
        # any late cost remains charged, never converted into a fresh budget.
        try:
            close.close_once()  # Raw original slot consumed BEFORE native close.
            if not close.call.result.value:
                raise OSError("native CloseHandle false; LastError UNKNOWN")
        except BaseException as exc:
            self._record_close("close", exc)

    def _record_close(self, kind, detail):
        # Fixed slots predate every acquisition.  Store exception references;
        # formatting/tuple allocation happens only after all close attempts.
        index = self._close_fault_count
        if index < len(self._close_faults):
            self._close_faults[index][0] = kind
            self._close_faults[index][1] = detail
            self._close_fault_count = index + 1

    @staticmethod
    def _fallback_storage():
        raw = (_c.c_uint8 * 8)()
        return raw, _c.addressof(raw)

    def _close_without_handle_conversion(self, close, clock, storage):
        # The first Python integer conversion failed.  Inspect a COPY of the
        # original eight bytes using cached byte values, never reconstruct a
        # HANDLE integer.  Unknown/zero/INVALID slots remain retained; do not
        # call CloseHandle on them or assert that acquisition did not happen.
        raw, address = storage
        try:
            _MEMMOVE(address, close.source.address, 8)
            any_bits = raw[0] | raw[1] | raw[2] | raw[3] | raw[4] | raw[5] | raw[6] | raw[7]
            all_bits = raw[0] & raw[1] & raw[2] & raw[3] & raw[4] & raw[5] & raw[6] & raw[7]
            if any_bits == 0 or all_bits == 255:
                self._record_close("raw_close_fallback_no_known_handle", None)
                return
        except BaseException as exc:
            self._record_close("raw_close_fallback_inspection", exc)
            return
        self._close(close, clock)  # Uses the unchanged original raw HANDLE slot.

    def collect_once(self):
        if _LIVE_PROBE is not self or self._started or not self.gate._prepared:
            raise PermissionError("single prepared original storage producer required")
        self._started = True
        try:
            self._stage = "original_start_qpc"
            self._stamp(*self.start_clock)
            self._stage = "original_frequency"
            self.qpf.invoke_once()
            if not self.qpf.result.value or _i64(self.meta.bytes(6032, 8), 0) != self.frequency:
                raise ValueError("native QPF does not match supplied original frequency")
            self._run(self.queries["open_volume"], handle=True)
            self._baseline = self._volume_snapshot("before")
            numbers = sorted({row[0] for row in self._baseline["extents"]})
            for slot, number in zip(self.disk_slots, numbers):
                slot["number"] = number
                path = ("\\\\.\\PhysicalDrive" + str(number)).encode("utf-16-le") + b"\0\0"
                _span(0, len(path), 128)
                slot["meta"].put(0, path)
                self._run(slot["birth"], handle=True)
                self._disk_before.append(self._disk_snapshot(slot, "before"))
            for slot in self.disk_slots[:len(numbers)]:
                self._disk_after.append(self._disk_snapshot(slot, "after"))
            self._after = self._volume_snapshot("after")
            if (_volume_identity(self._baseline) != _volume_identity(self._after) or
                    tuple(_disk_identity(x) for x in self._disk_before) !=
                    tuple(_disk_identity(x) for x in self._disk_after)):
                raise ValueError("native storage endpoint identities/geometry changed")
            self._stage = "snapshot_stop_qpc"
            self._stamp(*self.normal_end_clock)  # Work must finish before original STOP, not cleanup.
        except BaseException as exc:
            self._primary_stage, self._primary = self._stage, exc
        finally:
            # An FFI conversion exception cannot discard acquired raw HANDLEs.
            # Never retry an uncertain call or reopen by disk number for cleanup.
            for i, slot, close_clock in self._cleanup_slots:
                birth = slot["birth"].call
                if birth.attempted:
                    try:
                        value = birth.result.value
                        if value not in (0, _INVALID_HANDLE):
                            self._close(slot["close"], close_clock)
                        elif birth.faulted:
                            self._record_close("ambiguous_disk_acquisition", i)
                    except BaseException as exc:
                        self._record_close("disk_raw_close_inspection", exc)
                        self._close_without_handle_conversion(slot["close"], close_clock, slot["fallback"])
            if self.volume.attempted:
                try:
                    value = self.volume.result.value
                    if value not in (0, _INVALID_HANDLE):
                        self._close(self.volume_close, self.close_clocks[0])
                    elif self.volume.faulted:
                        self._record_close("ambiguous_volume_acquisition", None)
                except BaseException as exc:
                    self._record_close("volume_raw_close_inspection", exc)
                    self._close_without_handle_conversion(self.volume_close, self.close_clocks[0],
                                                          self._volume_fallback)
            try:
                self._stamp(self.end_clock, self.end_offset, cleanup=True)
            except BaseException as exc:
                self._end_faults[0] = exc
        close_faults = tuple((kind, type(detail).__name__ if isinstance(detail, BaseException)
                             else detail, _UNKNOWN_ERROR)
                            for kind, detail in self._close_faults[:self._close_fault_count])
        end_faults = (() if self._end_faults[0] is None else
                      ((type(self._end_faults[0]).__name__, _UNKNOWN_ERROR),))
        primary_fault = (None if self._primary is None else
                         (self._primary_stage, type(self._primary).__name__, _UNKNOWN_ERROR))
        self._report = _Map({
            "state": ("ENDPOINT_SNAPSHOT_COMPLETE" if self._primary is None and
                      not close_faults and not end_faults else "INCOMPLETE_UNKNOWN"),
            "original_epoch_qpc_raw_input": self.epoch, "original_frequency_raw_input": self.frequency,
            "original_stop_qpc_raw_input": self.stop, "original_cleanup_qpc_raw_input": self.cleanup,
            "observed_qpc": tuple(self._observed), "volume_before": self._baseline,
            "volume_after": self._after, "disks_before": tuple(self._disk_before),
            "disks_after": tuple(self._disk_after), "raw_call_results": tuple(self._raw_calls),
            "primary_fault": primary_fault, "close_faults": close_faults,
            "endpoint_faults": end_faults, "native_last_error": _UNKNOWN_ERROR,
            "physical_capacity_mechanism": "UNPROVEN", "continuous_coherence": "UNPROVEN",
            "budget_charges": "UNKNOWN_NOT_ZERO", "independent_owner": "UPSTREAM_REQUIRED",
            "admission_authority": None,
        })
        return self._report
