"""Held Windows source/runtime identity for the trusted outer controller.

Only a complete snapshot on an actually read-only Windows volume qualifies.
The ordinary writable host Python installation is deliberately refused. This
source primitive neither installs that snapshot nor authenticates the WSL
worker's access boundary or authorizes an experiment.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import threading
import weakref


_LEASES = weakref.WeakKeyDictionary()
_INITIALIZED_LEASES = weakref.WeakSet()
_INITIALIZATION_LOCK = threading.Lock()
_ABANDONED_LEASE_ERRORS = []


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


class _Win32:
    def __init__(self):
        if sys.platform != "win32":
            raise PermissionError("Windows execution identity requires the native host controller")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        self.kernel.CreateFileW.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.restype = ctypes.c_int
        self.kernel.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        self.kernel.ReadFile.restype = ctypes.c_int
        self.kernel.SetFilePointerEx.argtypes = [ctypes.c_void_p, ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong), ctypes.c_uint32]
        self.kernel.SetFilePointerEx.restype = ctypes.c_int
        self.kernel.GetFinalPathNameByHandleW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
        self.kernel.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        self.kernel.GetVolumeInformationW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_wchar_p, ctypes.c_uint32]
        self.kernel.GetVolumeInformationW.restype = ctypes.c_int
        self.kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        self.kernel.GetFileInformationByHandleEx.restype = ctypes.c_int

    def open_readonly(self, path, *, directory=False):
        handle = self.kernel.CreateFileW(str(path), 0x80000000, 1, None, 3,
            0x00200000 | (0x02000000 if directory else 0), None)  # no write/delete sharing
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            tags = (ctypes.c_uint32 * 2)()
            if not self.kernel.GetFileInformationByHandleEx(handle, 9, tags, ctypes.sizeof(tags)):
                raise ctypes.WinError(ctypes.get_last_error())
            if tags[0] & 0x400 or bool(tags[0] & 0x10) is not directory:
                raise PermissionError("held snapshot object is linked or has the wrong file type")
            return handle
        except BaseException as primary:
            try:
                self.close(handle)
            except BaseException as cleanup:
                _report_cleanup_errors(primary, (cleanup,), "snapshot open validation failed during handle cleanup")
            raise

    def open_owned_readonly(self, owned, path, *, directory=False):
        """Publish ownership atomically or close the unregistered handle once."""
        if type(owned) is not list:
            raise PermissionError("native handle ownership requires the original plain list")
        handle = self.open_readonly(path, directory=directory)
        try:
            owned.append(handle)
        except BaseException as primary:
            try:
                self.close(handle)
            except BaseException as cleanup:
                _report_cleanup_errors(primary, (cleanup,), "native handle registration failed during cleanup")
            raise
        return handle

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def path(self, handle):
        buffer = ctypes.create_unicode_buffer(32768)
        length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 1)
        if not 0 < length < len(buffer):
            raise PermissionError("held host snapshot path is absent or oversized")
        return buffer.value

    def readonly_volume(self, handle):
        value = self.path(handle)
        if not value.lower().startswith("\\\\?\\volume{") or "}\\" not in value:
            raise PermissionError("host snapshot is outside a canonical local volume")
        guid = value[:value.index("}\\") + 2]
        flags, serial, component = ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32()
        if not self.kernel.GetVolumeInformationW(guid, None, 0, ctypes.byref(serial), ctypes.byref(component),
                                                 ctypes.byref(flags), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not flags.value & 0x00080000:  # FILE_READ_ONLY_VOLUME
            raise PermissionError("host execution snapshot volume is writable")
        return guid.lower(), serial.value

    def digest(self, handle, *, maximum):
        if type(maximum) is not int or maximum < 0:
            raise PermissionError("held host file requires its exact manifest size bound")
        if not self.kernel.SetFilePointerEx(handle, 0, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        digest, size = hashlib.sha256(), 0
        buffer = ctypes.create_string_buffer(65536)
        while True:
            count = ctypes.c_uint32()
            if not self.kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if count.value == 0:
                return digest.hexdigest(), size
            digest.update(buffer.raw[:count.value]); size += count.value
            if size > maximum:
                raise PermissionError("held host file exceeds its frozen manifest size")


@dataclass(slots=True)
class _HeldExecution:
    root: Path
    manifest_sha256: str
    files: dict
    identities: dict
    handles: tuple
    volume: tuple
    kernel: object
    pid: int
    thread: object
    closed: bool = False
    finalizer: object = None


def _report_cleanup_errors(primary, cleanup, message):
    """Every close is consumed; retain this operation's own primary failure."""
    if cleanup:
        error = PermissionError(message)
        error.primary_error, error.cleanup_errors = primary, tuple(cleanup)
        raise error from (primary if primary is not None else cleanup[0])


def _close_held_execution(state):
    state.closed = True
    handles, state.handles = state.handles, ()
    failures = []
    for handle in reversed(handles):
        try:
            state.kernel.close(handle)
        except BaseException as exc:
            failures.append(exc)
    _report_cleanup_errors(None, failures, "host execution lease cleanup failed after consuming every handle")


def _abandon_held_execution(state):
    """Cleanup only, possibly on a different thread; never attest acceptance."""
    if state is None or state.closed or state.pid != os.getpid():
        return
    try:
        _close_held_execution(state)
    except BaseException as exc:
        # Keep failure evidence in this process even after the weak owner is
        # gone. No callback retries handles, writes a receipt or signs success.
        _ABANDONED_LEASE_ERRORS.append((state.manifest_sha256, exc))


class WindowsReadonlyExecutionLease:
    """Hold every declared host source/runtime file until outer acceptance.

    The manifest must itself be authenticated by the installed outer launcher's
    frozen policy. A matching hash supplied by a caller is not authorization.
    Windows OS native libraries remain in the trusted host OS boundary; this
    lease covers the declared Python/source closure, not arbitrary OS changes.
    """

    def __init__(self, root, manifest_bytes, expected_manifest_sha256):
        with _INITIALIZATION_LOCK:
            if type(self) is not WindowsReadonlyExecutionLease or self in _INITIALIZED_LEASES:
                raise PermissionError("host execution lease initialization may be attempted only once")
            _INITIALIZED_LEASES.add(self)
        if (type(manifest_bytes) is not bytes or not 0 < len(manifest_bytes) <= 8 << 20
                or type(expected_manifest_sha256) is not str
                or hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256):
            raise PermissionError("host execution manifest identity differs from frozen policy")
        manifest = json.loads(manifest_bytes)
        if (type(manifest) is not dict or set(manifest) != {"schema", "root", "files"}
                or manifest["schema"] != "route2_windows_execution_snapshot_v1" or _canonical(manifest) != manifest_bytes
                or type(manifest["files"]) is not dict or not manifest["files"]):
            raise PermissionError("host execution manifest is incomplete or noncanonical")
        path = Path(root)
        if not path.is_absolute() or str(path) != manifest["root"] or ".." in path.parts:
            raise PermissionError("host snapshot root differs from its exact frozen path")
        for entry in reversed((path, *path.parents)):
            info = entry.lstat()
            if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise PermissionError("host snapshot root or ancestor is a reparse point")
        kernel, handles, identities = _Win32(), [], {}
        primary = None
        published = None
        try:
            root_handle = kernel.open_owned_readonly(handles, path, directory=True)
            volume = kernel.readonly_volume(root_handle)
            held_prefix = kernel.path(root_handle).rstrip("\\") + "\\"
            actual = set()
            for entry in path.rglob("*"):
                info = entry.lstat()
                if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise PermissionError("host execution closure contains a reparse point")
                if not stat.S_ISDIR(info.st_mode):
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise PermissionError("host execution closure contains an unsupported object")
                    actual.add(entry.relative_to(path).as_posix())
            if actual != set(manifest["files"]):
                raise PermissionError("host manifest does not cover every snapshot file")
            seen_paths = set()
            for relative, record in manifest["files"].items():
                if (type(relative) is not str or PurePosixPath(relative).is_absolute()
                        or PurePosixPath(relative).as_posix() != relative or ".." in PurePosixPath(relative).parts
                        or "\\" in relative or ":" in relative or type(record) is not dict
                        or set(record) != {"sha256", "size_bytes"} or type(record["size_bytes"]) is not int
                        or record["size_bytes"] < 0 or type(record["sha256"]) is not str
                        or len(record["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in record["sha256"])):
                    raise PermissionError("host execution manifest contains an invalid exact file record")
                handle = kernel.open_owned_readonly(handles, path / relative)
                actual_path = kernel.path(handle)
                expected_path = held_prefix + relative.replace("/", "\\")
                if (actual_path.lower() != expected_path.lower() or actual_path.lower() in seen_paths
                        or kernel.readonly_volume(handle) != volume
                        or kernel.digest(handle, maximum=record["size_bytes"]) != (record["sha256"], record["size_bytes"])):
                    raise PermissionError("held host execution bytes or volume differ from the full manifest")
                identities[relative] = kernel.path(handle)
                seen_paths.add(actual_path.lower())
            state = _HeldExecution(path, expected_manifest_sha256, manifest["files"], identities, tuple(handles),
                                   volume, kernel, os.getpid(), weakref.ref(threading.current_thread()))
            _LEASES[self] = state
            published = state
            state.finalizer = weakref.finalize(self, _abandon_held_execution, state)
            self.require_live_identity()
            handles.clear()
        except BaseException as exc:
            primary = exc
            if published is not None:
                published.closed = True
                published.handles = ()
            raise
        finally:
            failures = []
            while handles:
                handle = handles.pop()
                try:
                    kernel.close(handle)
                except BaseException as exc:
                    failures.append(exc)
            _report_cleanup_errors(primary, failures, "host execution construction failed during consumed handle cleanup")

    def require_live_identity(self):
        state = _LEASES.get(self)
        if (state is None or state.closed or state.pid != os.getpid()
                or state.thread() is not threading.current_thread()):
            raise PermissionError("host execution lease is not held by the original outer controller")
        if sys.flags.isolated != 1 or sys.dont_write_bytecode is not True:
            raise PermissionError("host outer controller requires the pinned isolated no-bytecode interpreter")
        for path in (sys.executable, __file__, *sys.path):
            self._require_snapshot_path(state, path, exact_file=path in (sys.executable, __file__))
        for module in tuple(sys.modules.values()):
            origin = getattr(module, "__file__", None)
            if origin is not None:
                self._require_snapshot_path(state, origin, exact_file=True)
        if state.kernel.readonly_volume(state.handles[0]) != state.volume:
            raise PermissionError("held host execution volume identity or readonly state drifted")
        for (relative, record), handle in zip(state.files.items(), state.handles[1:]):
            if (state.kernel.path(handle) != state.identities[relative]
                    or state.kernel.readonly_volume(handle) != state.volume
                    or state.kernel.digest(handle, maximum=record["size_bytes"]) != (record["sha256"], record["size_bytes"])):
                raise PermissionError("held host runtime file identity drifted during execution")
        return state.manifest_sha256

    @staticmethod
    def _require_snapshot_path(state, value, *, exact_file):
        if (type(value) is not str or not value or not Path(value).is_absolute()
                or ".." in Path(value).parts or not Path(value).is_relative_to(state.root)):
            raise PermissionError("host executable/module/import path escaped its held snapshot")
        # All snapshot entries were checked for reparse points and the volume
        # remains read-only. Resolve the real existing parent too; a lexical
        # containment check alone is never sufficient.
        resolved = Path(value).resolve(strict=False)
        root = state.root.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise PermissionError("real host import path resolves outside its readonly snapshot")
        if exact_file:
            relative = Path(value).relative_to(state.root).as_posix()
            if relative not in state.files:
                # This producer requires unpacked Python modules; zip virtual
                # origins need a separately reviewed zip member identity map.
                raise PermissionError("executed host module is absent from the complete held file manifest")

    def close(self):
        state = _LEASES.get(self)
        if (state is None or state.closed or state.pid != os.getpid()
                or state.thread() is not threading.current_thread()):
            raise PermissionError("host execution lease may close only once in its original owner")
        _close_held_execution(state)


__all__ = ["WindowsReadonlyExecutionLease"]
