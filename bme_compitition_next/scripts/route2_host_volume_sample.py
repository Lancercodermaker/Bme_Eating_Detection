"""Read-only nested Windows backing-volume sample for a trusted host owner.

v2 binds the registered inner ext4.vhdx to carrier_volume_id and the carrier
backing file to windows_volume_id, the externally sealed original outer volume
GUID (the expected original E: topology). GetVirtualDiskPhysicalPath identifies
the *mounted carrier disk*, not the physical disk containing its backing file.
The latter disk number comes from the held outer volume's actual disk extent.
Only a fixed/dynamic carrier and one extent per volume are supported. Matching
the sealed outer GUID does not prove a nonvirtual outer disk on other topologies.

Directory/file handles exclude delete sharing throughout sampling. Incompatible
sharing, unavailable information or any identity/topology drift fails closed.
There are no attaches, detaches, WSL launches, privilege changes or file writes.
This observation does not establish the actual executed interpreter identity,
enforce a lifetime cap, grant admission, or enforce any physical storage budget.
The controller must pin this source and its isolated interpreter, authenticate
the sealed request/nonce, and bound the whole synchronous call in its own clock.
Free space may change during or immediately after this non-atomic observation.

Win32 contracts (Microsoft Learn, consulted for this implementation):
https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-openvirtualdisk
https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-open_virtual_disk_parameters
https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskphysicalpath
https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-get_virtual_disk_info
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info
https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-volume_disk_extents
WSL upstream registration semantics (installed version still needs binding):
https://github.com/microsoft/WSL/blob/master/src/windows/service/exe/DistributionRegistration.cpp
https://github.com/microsoft/WSL/blob/master/src/windows/service/exe/DistributionRegistration.h
https://github.com/microsoft/WSL/blob/master/src/windows/service/inc/wslservice.idl
"""
from __future__ import annotations

import ctypes
import json
from pathlib import PureWindowsPath
import re
import sys


_SCHEMA = "route2_host_backing_sample_v2"
_FIELDS = {
    "schema", "distro", "distro_registry_id", "windows_vhdx_path",
    "carrier_vhdx_path", "carrier_volume_id", "windows_volume_id", "nonce",
}
_GUID_TEXT = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_VOLUME_TEXT = r"\\\\\?\\Volume\{(" + _GUID_TEXT + r")\}\\"
_MAX_MESSAGE_BYTES = 4096
_MAX_PATH_CHARS = 32768
_FILE_READ_ATTRIBUTES = 0x80
_FILE_READ_DATA = 0x1
_FILE_LIST_DIRECTORY = 0x1
_SHARE_READ_WRITE = 0x3  # Deliberately no FILE_SHARE_DELETE, including ancestors.
_OPEN_EXISTING = 3
_OPEN_REPARSE_POINT = 0x00200000
_BACKUP_SEMANTICS = 0x02000000
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_DEVICE = 0x40
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_STANDARD_INFO = 1
_FILE_ATTRIBUTE_TAG_INFO = 9
_FILE_ID_INFO = 18
_VOLUME_NAME_GUID = 1
_IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
_VIRTUAL_DISK_ACCESS_GET_INFO = 0x00080000
_UINT32_MAX = (1 << 32) - 1


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )


def _bounded_message(value, *, newline=False):
    encoded = _canonical(value)
    if len(encoded.encode("utf-8")) + int(newline) > _MAX_MESSAGE_BYTES:
        raise PermissionError("host volume message exceeds 4096 bytes")
    return encoded


def _local_path(value, *, directory=False):
    path = PureWindowsPath(value)
    if (not path.is_absolute() or not re.fullmatch(r"[A-Z]:", path.drive)
            or str(path) != value
            or len(value.encode("utf-16-le")) // 2 >= _MAX_PATH_CHARS - 4
            or (not directory and len(path.parts) < 2)):
        raise PermissionError("host path is not a canonical local drive path")
    for part in path.parts[1:]:
        if (part in {".", ".."} or part.endswith((".", " "))
                or re.search(r'[<>:"/\\|?*\x00-\x1f\x7f]', part)
                or re.fullmatch(
                    r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3])(?:\..*)?",
                    part, re.IGNORECASE,
                )):
            raise PermissionError("host path has a stream, device or ambiguous component")
    # Reject lone surrogates before passing any string to a native API.
    value.encode("utf-8")
    return path


def _request(value):
    if type(value) is not dict or set(value) != _FIELDS:
        raise PermissionError("host volume request has missing/unknown fields")
    if any(type(item) is not str for item in value.values()):
        raise PermissionError("host volume request requires exact text identities")
    if (value["schema"] != _SCHEMA
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value["distro"])
            or not re.fullmatch(r"\{" + _GUID_TEXT + r"\}", value["distro_registry_id"])
            or not re.fullmatch(_VOLUME_TEXT, value["carrier_volume_id"])
            or not re.fullmatch(_VOLUME_TEXT, value["windows_volume_id"])
            or value["carrier_volume_id"] == value["windows_volume_id"]
            or not re.fullmatch(r"[0-9a-f]{32}", value["nonce"])):
        raise PermissionError("host volume request identity malformed")
    guest = _local_path(value["windows_vhdx_path"])
    carrier = _local_path(value["carrier_vhdx_path"])
    if guest.name != "ext4.vhdx" or carrier.suffix != ".vhdx" or guest == carrier:
        raise PermissionError("host request requires distinct inner and carrier VHDX paths")
    _bounded_message(value)
    return guest, carrier


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_uint8 * 8),
    ]


class _FileId128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_uint8 * 16)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [("VolumeSerialNumber", ctypes.c_uint64), ("FileId", _FileId128)]


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_int64), ("EndOfFile", ctypes.c_int64),
        ("NumberOfLinks", ctypes.c_uint32), ("DeletePending", ctypes.c_uint8),
        ("Directory", ctypes.c_uint8),
    ]


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [("FileAttributes", ctypes.c_uint32), ("ReparseTag", ctypes.c_uint32)]


class _DiskExtent(ctypes.Structure):
    _fields_ = [
        ("DiskNumber", ctypes.c_uint32), ("StartingOffset", ctypes.c_int64),
        ("ExtentLength", ctypes.c_int64),
    ]


class _VolumeDiskExtents(ctypes.Structure):
    _fields_ = [("NumberOfDiskExtents", ctypes.c_uint32), ("Extents", _DiskExtent * 1)]


class _VirtualStorageType(ctypes.Structure):
    _fields_ = [("DeviceId", ctypes.c_uint32), ("VendorId", _Guid)]


class _OpenVirtualDiskParametersV1(ctypes.Structure):
    # The version-1 prefix only: the API reads Version1.RWDepth when Version=1.
    _fields_ = [("Version", ctypes.c_uint32), ("RWDepth", ctypes.c_uint32)]


class _VirtualDiskInfoData(ctypes.Union):
    # Fixed union size/alignment from GET_VIRTUAL_DISK_INFO.Size (24 bytes).
    # Only the fixed ProviderSubtype member is requested; no variable buffers.
    _fields_ = [("Size", ctypes.c_uint64 * 3), ("ProviderSubtype", ctypes.c_uint32)]


class _VirtualDiskInfo(ctypes.Structure):
    _fields_ = [("Version", ctypes.c_uint32), ("Data", _VirtualDiskInfoData)]


def _native_error(code=None):
    return ctypes.WinError(ctypes.get_last_error() if code is None else code)


class _Native:
    def __init__(self):
        # Fixed Windows widths and natural SDK alignment, on either Python ABI.
        if (ctypes.sizeof(ctypes.c_wchar) != 2
                or ctypes.sizeof(_Guid) != 16
                or ctypes.sizeof(_FileIdInfo) != 24 or _FileIdInfo.FileId.offset != 8
                or ctypes.sizeof(_FileStandardInfo) != 24
                or ctypes.sizeof(_FileAttributeTagInfo) != 8
                or ctypes.sizeof(_DiskExtent) != 24 or _DiskExtent.StartingOffset.offset != 8
                or ctypes.sizeof(_VolumeDiskExtents) != 32 or _VolumeDiskExtents.Extents.offset != 8
                or ctypes.sizeof(_VirtualStorageType) != 20
                or ctypes.sizeof(_OpenVirtualDiskParametersV1) != 8
                or ctypes.sizeof(_VirtualDiskInfo) != 32 or _VirtualDiskInfo.Data.offset != 8):
            raise PermissionError("unsupported Windows native structure layout")
        # Resolve system DLLs explicitly; never search a project/current directory.
        self.kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        self.virtual = ctypes.WinDLL("virtdisk.dll", use_last_error=True, winmode=0x800)
        handle, u32, ptr = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p
        wchar_ptr, u32_ptr = ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(u32)
        u64_ptr = ctypes.POINTER(ctypes.c_uint64)
        self.create = self._bind(self.kernel, "CreateFileW", [
            ctypes.c_wchar_p, u32, u32, ptr, u32, u32, handle,
        ], handle)
        self.close = self._bind(self.kernel, "CloseHandle", [handle], ctypes.c_int32)
        self.get_type = self._bind(self.kernel, "GetFileType", [handle], u32)
        self.get_info = self._bind(self.kernel, "GetFileInformationByHandleEx", [
            handle, ctypes.c_int32, ptr, u32,
        ], ctypes.c_int32)
        self.get_path = self._bind(self.kernel, "GetFinalPathNameByHandleW", [
            handle, wchar_ptr, u32, u32,
        ], u32)
        self.get_free = self._bind(self.kernel, "GetDiskFreeSpaceExW", [
            ctypes.c_wchar_p, u64_ptr, u64_ptr, u64_ptr,
        ], ctypes.c_int32)
        self.ioctl = self._bind(self.kernel, "DeviceIoControl", [
            handle, u32, ptr, u32, ptr, u32, u32_ptr, ptr,
        ], ctypes.c_int32)
        self.open_virtual = self._bind(self.virtual, "OpenVirtualDisk", [
            ctypes.POINTER(_VirtualStorageType), ctypes.c_wchar_p,
            ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(_OpenVirtualDiskParametersV1),
            ctypes.POINTER(handle),
        ], u32)
        self.virtual_path = self._bind(self.virtual, "GetVirtualDiskPhysicalPath", [
            handle, u32_ptr, wchar_ptr,
        ], u32)
        self.virtual_info = self._bind(self.virtual, "GetVirtualDiskInformation", [
            handle, u32_ptr, ctypes.POINTER(_VirtualDiskInfo), u32_ptr,
        ], u32)

    @staticmethod
    def _bind(library, name, arguments, result):
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
        return function

    def open_file(self, handles, path, *, directory=False, volume=False):
        flags = 0 if volume else _OPEN_REPARSE_POINT | (_BACKUP_SEMANTICS if directory else 0)
        # Attribute-only access is exempt from Win32 share checking. Counted
        # data/list read access makes the held no-delete share mode meaningful;
        # incompatible permissions/sharing refuse without a weaker retry.
        access = 0 if volume else _FILE_READ_ATTRIBUTES | (
            _FILE_LIST_DIRECTORY if directory else _FILE_READ_DATA)
        handle = self.create(
            path, access, _SHARE_READ_WRITE,
            None, _OPEN_EXISTING, flags, None,
        )
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise _native_error()
        return handles.own(handle)

    def info(self, handle, kind, structure):
        result = structure()
        if not self.get_info(handle, kind, ctypes.byref(result), ctypes.sizeof(result)):
            raise _native_error()
        return result

    def final_path(self, handle, flags):
        result = ctypes.create_unicode_buffer(_MAX_PATH_CHARS)
        length = self.get_path(handle, result, len(result), flags)
        if not length:
            raise _native_error()
        if (length >= len(result) or result[length] != "\0"
                or len(result.value.encode("utf-16-le")) // 2 != length):
            raise PermissionError("held final path unavailable, unterminated or oversized")
        return result.value

    def snapshot(self, handle, *, directory):
        ctypes.set_last_error(0)
        kind = self.get_type(handle)
        if kind == 0 and ctypes.get_last_error():
            raise _native_error()
        if kind != 1:  # FILE_TYPE_DISK
            raise PermissionError("held host path is not a disk file/directory")
        attributes = self.info(handle, _FILE_ATTRIBUTE_TAG_INFO, _FileAttributeTagInfo)
        standard = self.info(handle, _FILE_STANDARD_INFO, _FileStandardInfo)
        if (attributes.FileAttributes & (_FILE_ATTRIBUTE_REPARSE_POINT | _FILE_ATTRIBUTE_DEVICE)
                or attributes.ReparseTag or standard.DeletePending
                or bool(standard.Directory) != directory
                or bool(attributes.FileAttributes & _FILE_ATTRIBUTE_DIRECTORY) != directory
                or (not directory and standard.NumberOfLinks != 1)):
            raise PermissionError("held host path is reparse, deleting or not a single-link regular file")
        identity = self.info(handle, _FILE_ID_INFO, _FileIdInfo)
        guid_path = self.final_path(handle, _VOLUME_NAME_GUID)
        match = re.match(_VOLUME_TEXT, guid_path, re.IGNORECASE)
        if match is None:
            raise PermissionError("held path has no local volume GUID")
        # Canonicalize only the GUID returned by Windows; request GUIDs are strict.
        volume = "\\\\?\\Volume{" + match[1].lower() + "}\\"
        guid_path = volume + guid_path[match.end():]
        dos_path = self.final_path(handle, 0)
        return (
            identity.VolumeSerialNumber, bytes(identity.FileId.Identifier).hex(),
            guid_path, dos_path,
        )

    def extent(self, handle):
        result, used = _VolumeDiskExtents(), ctypes.c_uint32()
        if not self.ioctl(
            handle, _IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, None, 0,
            ctypes.byref(result), ctypes.sizeof(result), ctypes.byref(used), None,
        ):
            # ERROR_MORE_DATA (including multiple extents) is rejected, not retried.
            raise _native_error()
        if used.value != ctypes.sizeof(result) or result.NumberOfDiskExtents != 1:
            raise PermissionError("host volume requires exactly one complete disk extent")
        extent = result.Extents[0]
        if (extent.DiskNumber == _UINT32_MAX or extent.StartingOffset < 0
                or extent.ExtentLength <= 0
                or extent.StartingOffset + extent.ExtentLength > (1 << 63) - 1):
            raise PermissionError("host volume disk extent is unknown or malformed")
        return extent.DiskNumber, extent.StartingOffset, extent.ExtentLength

    def free_space(self, volume):
        available, total, free = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64()
        if not self.get_free(volume, ctypes.byref(available), ctypes.byref(total), ctypes.byref(free)):
            raise _native_error()
        # total is caller-quota dependent; total_free may legitimately exceed it.
        if not total.value or available.value > min(total.value, free.value):
            raise PermissionError("host free-space result is inconsistent")
        return available.value, free.value

    def open_carrier(self, handles, held):
        held.recheck()
        storage = _VirtualStorageType()
        storage.DeviceId = 3  # VIRTUAL_STORAGE_TYPE_DEVICE_VHDX
        storage.VendorId = _Guid(
            0xEC984AEC, 0xA0F9, 0x47E9,
            (ctypes.c_uint8 * 8)(0x90, 0x1F, 0x71, 0x41, 0x5A, 0x66, 0x34, 0x5B),
        )
        parameters = _OpenVirtualDiskParametersV1(1, 0)
        handle = ctypes.c_void_p()
        # VERSION_1/RWDepth=0 opens every store read-only. GET_INFO is the only
        # access requested; flags=NONE. A permanent attachment can require DETACH
        # access even to open a query handle. Such opens (and all other unsupported
        # queries/sharing errors) fail closed: no access escalation or attach retry.
        status = self.open_virtual(
            ctypes.byref(storage), held.guid_path, _VIRTUAL_DISK_ACCESS_GET_INFO,
            0, ctypes.byref(parameters), ctypes.byref(handle),
        )
        if status:
            # On failure the output handle is undefined, not an owned handle.
            raise _native_error(status)
        if handle.value is None or handle.value == ctypes.c_void_p(-1).value:
            raise PermissionError("OpenVirtualDisk returned an invalid query handle")
        owned = handles.own(handle.value)
        held.recheck()
        return owned

    def carrier_mapping(self, handle):
        info = _VirtualDiskInfo()
        info.Version = 7  # GET_VIRTUAL_DISK_INFO_PROVIDER_SUBTYPE
        size, used = ctypes.c_uint32(ctypes.sizeof(info)), ctypes.c_uint32()
        status = self.virtual_info(handle, ctypes.byref(size), ctypes.byref(info), ctypes.byref(used))
        if status:
            raise _native_error(status)
        minimum = _VirtualDiskInfo.Data.offset + ctypes.sizeof(ctypes.c_uint32)
        if (info.Version != 7 or not minimum <= used.value <= ctypes.sizeof(info)
                or not minimum <= size.value <= ctypes.sizeof(info)
                or info.Data.ProviderSubtype not in {2, 3}):
            raise PermissionError("carrier is differencing or has an unsupported backing topology")
        result = ctypes.create_unicode_buffer(256)
        size = ctypes.c_uint32(ctypes.sizeof(result))  # API counts bytes, not WCHARs.
        status = self.virtual_path(handle, ctypes.byref(size), result)
        if status:
            raise _native_error(status)
        end = result[:].find("\0")
        if (not 0 < end < len(result) or size.value > ctypes.sizeof(result)
                or size.value % 2 or size.value < (end + 1) * 2):
            raise PermissionError("mounted carrier disk path is unavailable/oversized")
        match = re.fullmatch(r"\\\\\.\\PhysicalDrive(0|[1-9][0-9]{0,9})", result.value)
        if match is None or int(match[1]) >= _UINT32_MAX:
            raise PermissionError("mounted carrier disk number is unknown")
        return info.Data.ProviderSubtype, int(match[1])


class _Handles:
    """One CloseHandle attempt per acquired handle; preserve a primary failure."""

    def __init__(self, api):
        self.api, self.handles = api, []

    def __enter__(self):
        return self

    def own(self, handle):
        try:
            self.handles.append(handle)
        except BaseException:
            # Ownership transfer can fail (e.g. MemoryError); still close once.
            try:
                self.api.close(handle)
            except BaseException:
                pass
            raise
        return handle

    def __exit__(self, exc_type, exc, traceback):
        close_error = None
        while self.handles:
            handle = self.handles.pop()  # Never retry a possibly closed handle.
            try:
                if not self.api.close(handle):
                    raise _native_error()
            except BaseException as error:
                if close_error is None:
                    close_error = error
        if exc is None and close_error is not None:
            raise close_error
        return False


class _HeldPath:
    def __init__(self, api, handles, path, volume):
        self.api, self.nodes = api, []
        # Root first: each already-held parent blocks rename of the next path.
        chain = [*reversed(path.parents), path]
        for index, part in enumerate(chain):
            directory = index != len(chain) - 1
            opened = "\\\\?\\" + str(part)
            handle = api.open_file(handles, opened, directory=directory)
            snapshot = api.snapshot(handle, directory=directory)
            expected_guid = volume + "\\".join(part.parts[1:])
            if snapshot[2:] != (expected_guid, opened):
                raise PermissionError("held local path differs from sealed volume/path")
            if self.nodes and snapshot[0] != self.nodes[0][3][0]:
                raise PermissionError("host ancestor chain crosses volumes")
            self.nodes.append((opened, handle, directory, snapshot))
        self.guid_path = self.nodes[-1][3][2]
        # Sample/open the GUID root derived from the held file, after checking
        # that it matches the sealed request. Never select a volume by drive alone.
        self.volume_id = re.match(_VOLUME_TEXT, self.guid_path)[0]
        self.identity = {
            "volume_serial_number": self.nodes[-1][3][0],
            "file_id_hex": self.nodes[-1][3][1],
        }

    def recheck(self):
        for opened, handle, directory, before in self.nodes:
            if self.api.snapshot(handle, directory=directory) != before:
                raise PermissionError("held host path/identity changed during sampling")
            # Read the actual current namespace, not just the retained handles.
            # Both DOS and final GUID names must still refer to that held object.
            with _Handles(self.api) as temporary:
                for current_path in (opened, before[2]):
                    current = self.api.open_file(temporary, current_path, directory=directory)
                    if self.api.snapshot(current, directory=directory) != before:
                        raise PermissionError("host namespace no longer names the held identity")


def _registry(request):
    import winreg

    registry = r"Software\Microsoft\Windows\CurrentVersion\Lxss" + "\\" + request["distro_registry_id"]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry, 0, winreg.KEY_READ) as entry:
        name, name_type = winreg.QueryValueEx(entry, "DistributionName")
        raw_base, base_type = winreg.QueryValueEx(entry, "BasePath")
        try:
            raw_vhd, vhd_type = winreg.QueryValueEx(entry, "VhdFileName")
        except FileNotFoundError as missing:
            # Only ERROR_FILE_NOT_FOUND means the optional value is absent.
            # WSL's VhdFileName default is LXSS_VM_MODE_VHD_NAME/ext4.vhdx.
            # Keep absence distinct from an explicitly stored identical name.
            if missing.winerror != 2:
                raise
            vhd_present, raw_vhd, vhd_type = False, None, None
            effective_vhd = "ext4.vhdx"
        else:
            vhd_present = True
            if type(raw_vhd) is not str or vhd_type != winreg.REG_SZ or raw_vhd != "ext4.vhdx":
                raise PermissionError("unsupported registered WSL VhdFileName")
            effective_vhd = raw_vhd
    if (type(name) is not str or name != request["distro"] or name_type != winreg.REG_SZ
            or type(raw_base) is not str or base_type != winreg.REG_SZ):
        raise PermissionError("registered WSL distribution identity drift")
    # REG_SZ is literal, including percent-delimited directory names. Refuse
    # REG_EXPAND_SZ until the installed WSL expansion contract is established.
    base = raw_base
    # Lxss commonly stores an extended local path. Strip only that prefix;
    # never resolve links or normalize ambiguous path components.
    if base.startswith("\\\\?\\"):
        base = base[4:]
    base = _local_path(base, directory=True)
    if str(base / effective_vhd) != request["windows_vhdx_path"]:
        raise PermissionError("VHDX path differs from the registered BasePath/VhdFileName")
    return name, name_type, raw_base, base_type, str(base), vhd_present, raw_vhd, vhd_type, effective_vhd


def _mapping(api, virtual, carrier_volume, outer_volume):
    subtype, mounted_disk = api.carrier_mapping(virtual)
    carrier_extent, outer_extent = api.extent(carrier_volume), api.extent(outer_volume)
    if carrier_extent[0] != mounted_disk or outer_extent[0] == mounted_disk:
        raise PermissionError("carrier/outer disk relation differs from the nested topology")
    return subtype, mounted_disk, carrier_extent, outer_extent


def sample_host_volume(request):
    # Snapshot caller-owned input so the echoed binding cannot change mid-call.
    if type(request) is not dict:
        raise PermissionError("host volume request requires an exact dictionary")
    request = dict(request)
    guest_path, carrier_path = _request(request)
    if sys.platform != "win32":
        raise PermissionError("host volume sampler requires Windows")
    registry_before = _registry(request)
    api = _Native()
    with _Handles(api) as handles:
        carrier = _HeldPath(api, handles, carrier_path, request["windows_volume_id"])
        guest = _HeldPath(api, handles, guest_path, request["carrier_volume_id"])
        carrier.recheck()
        guest.recheck()
        virtual = api.open_carrier(handles, carrier)
        carrier_volume = api.open_file(handles, guest.volume_id[:-1], volume=True)
        outer_volume = api.open_file(handles, carrier.volume_id[:-1], volume=True)
        mapping_before = _mapping(api, virtual, carrier_volume, outer_volume)
        if _registry(request) != registry_before:
            raise PermissionError("WSL registry changed before free-space sampling")
        carrier_available, carrier_free = api.free_space(guest.volume_id)
        available, free = api.free_space(carrier.volume_id)
        carrier.recheck()
        guest.recheck()
        if _mapping(api, virtual, carrier_volume, outer_volume) != mapping_before:
            raise PermissionError("held carrier/outer extent mapping changed during sampling")
        # Reopen each actual GUID volume to detect a namespace/device remapping.
        with _Handles(api) as temporary:
            current_carrier = api.open_file(temporary, guest.volume_id[:-1], volume=True)
            current_outer = api.open_file(temporary, carrier.volume_id[:-1], volume=True)
            if _mapping(api, virtual, current_carrier, current_outer) != mapping_before:
                raise PermissionError("current GUID volume mapping differs from held volumes")
        carrier.recheck()
        guest.recheck()
        if _registry(request) != registry_before:
            raise PermissionError("WSL registry changed during free-space sampling")
        response = {
            **request,
            "carrier_available_bytes": carrier_available,
            "carrier_total_free_bytes": carrier_free,
            "available_bytes": available,
            "total_free_bytes": free,
            "carrier_file_identity": carrier.identity,
            "guest_vhdx_file_identity": guest.identity,
            "carrier_disk_number": mapping_before[1],
            "physical_disk_number": mapping_before[3][0],
        }
        _bounded_message(response, newline=True)
    return response


def main():
    if len(sys.argv) != 2 or len(sys.argv[1].encode("utf-8")) > _MAX_MESSAGE_BYTES:
        raise PermissionError("one bounded host volume request is required")
    request = json.loads(sys.argv[1])
    if _canonical(request) != sys.argv[1]:
        raise PermissionError("host request is not canonical")
    response = _bounded_message(sample_host_volume(request), newline=True)
    sys.stdout.buffer.write(response.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
