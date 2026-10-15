"""Compile-free, raw-result Win64 call substrate; never loads a native image.

This is a mechanism, not a preparation lease, preload verifier or admission.
The owner must FIRST bind the actual immutable loaded provider and its build to
the exact supported headers.  Selecting PROFILE does not establish that fact.
No constructor or module import loads an image or spawns an actor. Constructor
export resolution/native memory reads AND ``prepare_once`` libffi calls belong
inside the original, fully accounted preparation boundary, established first.

The supported declaration is libffi v3.3, X86_WIN64, MSVC (not generic x86-64):
https://github.com/libffi/libffi/blob/v3.3/include/ffi.h.in
https://github.com/libffi/libffi/blob/v3.3/src/x86/ffitarget.h
https://github.com/libffi/libffi/blob/v3.3/src/x86/ffiw64.c
ffi.h.in SHA256 c86413e56ef61322a67a6a61d773b62371137d1f9c1abc91e6aa6d4012b24e91
ffitarget.h SHA256 ce9a87677a9b9af9dcc6f8f632b62948214824174b65fe4361d3b662cc72aec0

ffi_call returns void; it writes the target's result into persistent native
storage before the outer ctypes return conversion.  Output HANDLEs likewise
stay in owned output buffers.  No Python HANDLE integer is needed to close an
original slot.  A conversion exception leaves the gate and its slots retained.
Direct nested-libffi calls do NOT prove Win32 LastError preservation.  Their
error metadata is UNKNOWN even when the return/output bytes are available.

The optional single fixed call/store stub captures RAX and GetLastError in the
same native frame.  Installing it uses one private RW allocation, changes it to
RX, flushes and checks its region.  No RWX allocation or post-RX patch exists.
Process-wide exclusion of outside protection/alias writers and actual provider
identity remain owner obligations. Installing this component never proves
those obligations; invocation belongs inside that verified owner closure.
"""

from __future__ import annotations

import ctypes as _c
import sys as _sys
from _thread import allocate_lock as _allocate_lock, RLock as _RLock
from types import MappingProxyType as _Map

PROFILE = "libffi-3.3/X86_WIN64/MSVC"
_U32, _I32 = _c.c_uint32, _c.c_int32
_U64, _I64, _P = _c.c_uint64, _c.c_int64, _c.c_void_p
_LIVE_GATE = None                 # Strong lifetime anchor, never reset/replaced.
_GATE_RESERVE_LOCK = _allocate_lock()
_MEMMOVE, _STRING_AT = _c.memmove, _c.string_at
_MAX_CALLS, _MAX_BUFFERS = 256, 32
class _GateFailure(RuntimeError):
    def __str__(self):
        return "compile-free native gate failed; retain original raw slots"


_ERROR = _GateFailure


class _FFIType(_c.Structure):
    _fields_ = [("size", _c.c_size_t), ("alignment", _c.c_uint16),
                ("type", _c.c_uint16), ("elements", _P)]


class _CIF(_c.Structure):
    _fields_ = [("abi", _U32), ("nargs", _U32), ("arg_types", _P),
                ("rtype", _P), ("bytes", _U32), ("flags", _U32)]


class _GuardedCIF(_c.Structure):
    _fields_ = [("before", _U64 * 2), ("cif", _CIF), ("after", _U64 * 2)]


class _Frame(_c.Structure):
    _fields_ = [("function", _U64), ("get_last_error", _U64),
                ("arguments", _U64 * 10), ("result", _U64),
                ("last_error", _U32), ("completed", _U32),
                ("entered", _U32), ("reserved", _U32)]


class _MemoryInfo(_c.Structure):
    _fields_ = [("base", _P), ("allocation_base", _P),
                ("allocation_protect", _U32), ("partition_id", _c.c_uint16),
                ("region_size", _c.c_size_t), ("state", _U32),
                ("protect", _U32), ("type", _U32)]


# Only these integer/pointer WinAPI signatures can be called.  No user function
# pointer, callback, Python callable, variadic or aggregate-by-value is accepted.
# See the corresponding Microsoft Learn Win32 function declarations.
_SIGNATURES = _Map({
    "CreateJobObjectW": ("p", ("p", "p")),
    "CreateFileW": ("p", ("p", "u", "u", "p", "u", "u", "p")),
    "DeviceIoControl": ("i", ("p", "u", "p", "u", "p", "u", "p", "p")),
    "GetVolumeInformationByHandleW": ("i", ("p", "p", "u", "p", "p", "p", "p", "u")),
    "GetVolumeNameForVolumeMountPointW": ("i", ("p", "p", "u")),
    "CreateEventW": ("p", ("p", "i", "i", "p")),
    "CreateThread": ("p", ("p", "q", "p", "p", "u", "p")),
    "SetEvent": ("i", ("p",)),
    "ResetEvent": ("i", ("p",)),
    "CloseHandle": ("i", ("p",)),
    "DuplicateHandle": ("i", ("p", "p", "p", "p", "u", "i", "u")),
    "SetInformationJobObject": ("i", ("p", "i", "p", "u")),
    "QueryInformationJobObject": ("i", ("p", "i", "p", "u", "p")),
    "InitializeProcThreadAttributeList": ("i", ("p", "u", "u", "p")),
    "UpdateProcThreadAttribute": ("i", ("p", "u", "q", "p", "q", "p", "p")),
    "DeleteProcThreadAttributeList": ("v", ("p",)),
    "CreateProcessW": ("i", ("p", "p", "p", "p", "i", "u", "p", "p", "p", "p")),
    "ResumeThread": ("u", ("p",)),
    "WaitForSingleObject": ("u", ("p", "u")),
    "TerminateJobObject": ("i", ("p", "u")),
    "TerminateProcess": ("i", ("p", "u")),
    "GetExitCodeProcess": ("i", ("p", "p")),
    "GetExitCodeThread": ("i", ("p", "p")),
    "GetProcessTimes": ("i", ("p", "p", "p", "p", "p")),
    "GetThreadTimes": ("i", ("p", "p", "p", "p", "p")),
    "GetCurrentProcess": ("p", ()),
    "GetCurrentProcessId": ("u", ()),
    "GetCurrentThreadId": ("u", ()),
    "GetSystemTimePreciseAsFileTime": ("v", ("p",)),
    "QueryPerformanceCounter": ("i", ("p",)),
    "QueryPerformanceFrequency": ("i", ("p",)),
    "VirtualAlloc": ("p", ("p", "q", "u", "u")),
    "VirtualProtect": ("i", ("p", "q", "u", "p")),
    "VirtualFree": ("i", ("p", "q", "u")),
    "VirtualQuery": ("q", ("p", "p", "q")),
    "FlushInstructionCache": ("i", ("p", "p", "q")),
    "GetLastError": ("u", ()),
    "RtlAddFunctionTable": ("b", ("p", "u", "q")),
    "RtlDeleteFunctionTable": ("b", ("p",)),
})
_CTYPES = _Map({"p": _P, "u": _U32, "i": _I32, "q": _U64, "v": None, "b": _c.c_uint8})
_TYPE_EXPORTS = _Map({
    "p": ("ffi_type_pointer", 8, 8, 14),
    "u": ("ffi_type_uint32", 4, 4, 9),
    "i": ("ffi_type_sint32", 4, 4, 10),
    "q": ("ffi_type_uint64", 8, 8, 11),
    "v": ("ffi_type_void", 1, 1, 0),
    "b": ("ffi_type_uint8", 1, 1, 5),
})
_CANARY = 0x6C69626666693333


def _layout():
    expected = ((_FFIType, 24, (0, 8, 10, 16)),
                (_CIF, 32, (0, 4, 8, 16, 24, 28)),
                (_Frame, 120, (0, 8, 16, 96, 104, 108, 112, 116)),
                (_MemoryInfo, 48, (0, 8, 16, 20, 24, 32, 36, 40)))
    return all(_c.sizeof(t) == size and tuple(getattr(t, n).offset
               for n, _ in t._fields_) == offsets for t, size, offsets in expected)


def _address(function):
    return _c.cast(function, _P).value


class _FrozenExport:
    __slots__ = ("lookup", "address", "original_type", "flags")

    def __init__(self, library, symbol):
        self.lookup = library[symbol]  # genuine existing native module lookup
        self.address = _address(self.lookup)
        self.original_type, self.flags = type(self.lookup), self.lookup._flags_
        if not self.address:
            raise _ERROR

    def unchanged(self):
        return (type(self.lookup) is self.original_type and
                self.lookup._flags_ == self.flags and
                _address(self.lookup) == self.address)


class _RawReference:
    """Pointer to original native bytes used AS an argument, not a HANDLE int."""
    __slots__ = ("owner", "address")

    def __init__(self, owner, address):
        self.owner, self.address = owner, address


class _Output:
    __slots__ = ("gate", "storage", "size", "pointer", "reference")

    def __init__(self, gate, size):
        if type(size) is not int or not 1 <= size <= 65536:
            raise ValueError("bounded native output size required")
        self.gate, self.size = gate, size
        self.storage = (_U64 * ((size + 7) // 8))()
        self.pointer = _P(_c.addressof(self.storage))
        self.reference = _RawReference(self, _c.addressof(self.pointer))

    def handle_reference(self, offset):
        if type(offset) is not int or offset < 0 or offset % 8 or offset + 8 > self.size:
            raise ValueError("aligned original HANDLE output slot required")
        return _RawReference(self, _c.addressof(self.storage) + offset)


class _RawCall:
    """One call, one permanent result slot; never cleared or reused."""
    __slots__ = ("gate", "name", "arguments", "values", "avalue", "cif",
                 "atypes", "result", "result_reference", "frame", "attempted",
                 "returned", "faulted", "close", "function", "cif_bytes",
                 "store_pointer", "store_avalue", "input_addresses", "atype_bytes", "_entry_lock",
                 "_program_entry", "_program_identity", "_thread_program", "_thread_identity")

    def __init__(self, gate, name, arguments, *, deadline_program=None):
        if type(name) is not str or name not in _SIGNATURES:
            raise TypeError("exact fixed native function identifier required")
        thread_owner = None
        if name == "CreateThread":
            module = _sys.modules.get(__package__ + ".windows_compile_free_deadline")
            cls = getattr(module, "_FixedDeadlineProgram", None) if module is not None else None
            if (arguments is not None or cls is None or type(deadline_program) is not cls or
                    deadline_program.gate is not gate or
                    type(deadline_program._entry_pointers["watchdog"]) is not _P or
                    type(deadline_program._context_pointer) is not _P):
                raise TypeError("CreateThread requires the exact owned watchdog program")
            start, context = deadline_program._entry_pointers["watchdog"], deadline_program._context_pointer
            thread_owner = (deadline_program, cls, cls._gate_entry, cls._check_entry, start, context)
            arguments = (_P(), _U64(65536), start, context, _U32(0x10000), _P())
        elif deadline_program is not None:
            raise TypeError("a deadline thread owner belongs only to dedicated CreateThread")
        result, codes = _SIGNATURES[name]
        if len(arguments) != len(codes):
            raise TypeError("wrong fixed native argument count")
        self.gate, self.name, self.arguments = gate, name, tuple(arguments)
        self._entry_lock = _allocate_lock()
        self._program_entry, self._program_identity = None, None
        self._thread_program, self._thread_identity = thread_owner, None
        self.function = gate._exports[name].address
        self.values = []
        self.avalue = (_P * max(1, len(codes)))()
        self.atypes = (_P * max(1, len(codes)))()
        self.cif, self.frame = _GuardedCIF(), _Frame()
        # The backing slot is ALWAYS aligned ffi_arg-sized (8 bytes). Scalar
        # observations use only ABI-defined return bits: a Win32 BOOL/DWORD or
        # BOOLEAN need not define the remainder of the raw RAX register.
        result_view = _U64 if result in ("p", "q", "v") else _CTYPES[result]
        self.result = result_view.from_buffer(self.frame, _Frame.result.offset)
        self.store_pointer = _P(_c.addressof(self.frame))
        self.store_avalue = (_P * 1)(_c.addressof(self.store_pointer))
        self.result_reference = _RawReference(self, _c.addressof(self.result))
        self.attempted = self.returned = self.faulted = False
        self.close, self.cif_bytes = None, None
        self.frame.function = self.function
        self.frame.get_last_error = gate._exports["GetLastError"].address
        for index, (code, argument) in enumerate(zip(codes, arguments)):
            self.atypes[index] = gate._types[code][1]
            if type(argument) is _RawReference:
                if argument.owner.gate is not gate:
                    raise TypeError("raw argument belongs to another owner")
                address = argument.address
            else:
                target = _CTYPES[code]
                if type(argument) is not target:
                    raise TypeError("exact fixed native scalar or original raw slot required")
                address = _c.addressof(argument)
            self.values.append(argument)
            self.avalue[index] = address
        for side in (self.cif.before, self.cif.after):
            side[0] = side[1] = _CANARY
        self.input_addresses = tuple(self.avalue)
        self.atype_bytes = _STRING_AT(_c.addressof(self.atypes), _c.sizeof(self.atypes))

    def _prepare(self):
        self.gate._check()
        result_code, codes = _SIGNATURES[self.name]
        status = self.gate._prep(_c.byref(self.cif.cif), 1, len(codes),
                                self.gate._types[result_code][1], self.atypes)
        cif = self.cif.cif
        if (status != 0 or tuple(self.cif.before) != (_CANARY, _CANARY) or
                tuple(self.cif.after) != (_CANARY, _CANARY) or cif.abi != 1 or
                cif.nargs != len(codes) or cif.arg_types != _c.addressof(self.atypes) or
                cif.rtype != self.gate._types[result_code][1] or
                cif.bytes != max(4, len(codes)) * 8 or
                cif.flags != _TYPE_EXPORTS[result_code][3]):
            self.gate._drifted = True
            raise _ERROR
        self.cif_bytes = _STRING_AT(_c.addressof(self.cif), _c.sizeof(self.cif))

    def _inputs_unchanged(self):
        return (tuple(self.avalue) == self.input_addresses and
                _STRING_AT(_c.addressof(self.atypes), _c.sizeof(self.atypes)) == self.atype_bytes and
                (self.name != "CreateThread" or self._thread_inputs_unchanged()) and
                ((self._program_entry is None and self.function == self.gate._exports[self.name].address) or
                 (self._program_entry is not None and self._program_identity is not None and
                  self.function != 0 and self.function == self._program_identity[3])) and
                self.frame.function == self.function and
                self.frame.get_last_error == self.gate._exports["GetLastError"].address)

    def _thread_inputs_unchanged(self):
        if self._thread_program is None or self._thread_identity is None:
            return False
        program, _, _, _, start, context = self._thread_program
        return (self.arguments[0].value is None and self.arguments[1].value == 65536 and
                self.arguments[2] is start and self.arguments[3] is context and
                self.arguments[4].value == 0x10000 and self.arguments[5].value is None and
                program._entry_pointers["watchdog"] is start and program._context_pointer is context and
                (start.value, context.value) == self._thread_identity[3:])

    def _resolve_thread(self):
        if self.name != "CreateThread":
            return
        if self._thread_program is None:
            raise _ERROR
        program, cls, get_entry, check_entry, start, context = self._thread_program
        module = _sys.modules.get(__package__ + ".windows_compile_free_deadline")
        context_alloc = program._allocations["context"]
        if (module is None or getattr(module, "_FixedDeadlineProgram", None) is not cls or
                type(program) is not cls or cls._gate_entry is not get_entry or
                cls._check_entry is not check_entry or program.gate is not self.gate or
                program._entry_pointers["watchdog"] is not start or program._context_pointer is not context or
                type(context_alloc) is not _RawCall or context_alloc.gate is not self.gate or
                context_alloc.name != "VirtualAlloc" or not context_alloc.result.value or
                context.value != context_alloc.result.value):
            self.gate._drifted = True
            raise _ERROR
        check_entry(program, "watchdog")
        reference, offset, digest = get_entry(program, "watchdog")
        if (type(reference) is not _RawReference or type(reference.owner) is not _RawCall or
                reference.owner.gate is not self.gate or reference.owner.name != "VirtualAlloc" or
                reference.address != _c.addressof(reference.owner.result) or
                type(offset) is not int or not 0 <= offset < reference.owner.arguments[1].value or
                type(digest) is not str or len(digest) != 64 or
                any(x not in "0123456789abcdef" for x in digest)):
            raise _ERROR
        allocation = reference.owner.result.value
        if not allocation or start.value != allocation + offset:
            raise _ERROR
        identity = (reference.address, offset, digest, allocation + offset, context_alloc.result.value)
        if self._thread_identity is None:
            self._thread_identity = identity
        elif self._thread_identity != identity:
            self.gate._drifted = True
            raise _ERROR

    def _resolve_program(self):
        if self._program_entry is None:
            return
        program, entry, get_entry, check_entry = self._program_entry
        cls = type(program)
        module = _sys.modules.get(__package__ + ".windows_compile_free_deadline")
        if (module is None or getattr(module, "_FixedDeadlineProgram", None) is not cls or
                cls._gate_entry is not get_entry or cls._check_entry is not check_entry or
                program.gate is not self.gate):
            self.gate._drifted = True
            raise _ERROR
        check_entry(program, entry)
        reference, offset, digest = get_entry(program, entry)
        if (type(reference) is not _RawReference or type(reference.owner) is not _RawCall or
                reference.owner.gate is not self.gate or reference.owner.name != "VirtualAlloc" or
                reference.address != _c.addressof(reference.owner.result) or
                type(offset) is not int or not 0 <= offset < 65536 or
                type(digest) is not str or len(digest) != 64 or
                any(x not in "0123456789abcdef" for x in digest)):
            raise _ERROR
        allocation = reference.owner.result.value
        if not allocation or offset >= reference.owner.arguments[1].value:
            raise _ERROR
        identity = (reference.address, offset, digest, allocation + offset)
        if self._program_identity is None:
            self._program_identity = identity
            self.function = self.frame.function = identity[3]
        elif self._program_identity != identity or self.function != identity[3]:
            self.gate._drifted = True
            raise _ERROR

    def invoke_once(self):
        """Direct raw libffi call; Win32 LastError remains UNKNOWN."""
        if not self._entry_lock.acquire(False):
            raise _ERROR
        self.gate._check()
        self._resolve_program()
        self._resolve_thread()
        self._invoke_direct()

    def _invoke_direct(self, *, cleanup=False):
        if self.attempted or not self.gate._prepared or self.cif_bytes is None:
            raise _ERROR
        if (not self._inputs_unchanged() or
                _STRING_AT(_c.addressof(self.cif), _c.sizeof(self.cif)) != self.cif_bytes):
            self.gate._drifted = True
            raise _ERROR
        self.attempted = True
        try:
            function = self.gate._cleanup_call if cleanup else self.gate._call
            function(_c.byref(self.cif.cif), self.function, _c.byref(self.result), self.avalue)
            self.returned = True
        except BaseException:
            self.faulted = True
            # The result/output memory and original function remain anchored.
            # No close, zeroing, interpretation or replacement occurs here.
            raise

    def invoke_store_once(self, installed_store):
        """Call fixed native store stub; original result and LastError stay raw.

        Requires the original trusted owner's immutable closure and alias
        exclusion preconditions.  ``completed`` distinguishes native return
        completion even if outer Python return conversion subsequently fails.
        """
        if not self._entry_lock.acquire(False):
            raise _ERROR
        self.gate._check()
        self._resolve_program()
        self._resolve_thread()
        if (type(installed_store) is not _FixedCallStore or installed_store.gate is not self.gate or
                not installed_store.ready or self.attempted or not self.gate._prepared or
                self.cif_bytes is None or not self._inputs_unchanged() or
                _STRING_AT(_c.addressof(self.cif), _c.sizeof(self.cif)) != self.cif_bytes or
                not self.gate._stub_unchanged()):
            raise _ERROR
        if not installed_store._lifecycle_lock.acquire(False):
            raise _ERROR
        try:
            installed_store._check_region()
            for index, code in enumerate(_SIGNATURES[self.name][1]):
                width = _c.sizeof(_CTYPES[code])
                _MEMMOVE(_c.addressof(self.frame) + 16 + 8 * index,
                         self.input_addresses[index], width)
            self.attempted = True
            try:
                self.gate._call(_c.byref(self.gate._stub_cif.cif), installed_store.address,
                                _c.byref(self.gate._stub_ignored), self.store_avalue)
                self.returned = True
                if self.frame.entered != 1 or self.frame.completed != 1:
                    self.faulted = True
                    raise _ERROR
            except BaseException:
                self.faulted = True
                raise
        finally:
            installed_store._lifecycle_lock.release()

    def close_handle_once(self):
        if self.close is None:
            raise _ERROR
        self.close.close_once()

    @property
    def last_error_state(self):
        return "RAW_CAPTURED" if self.frame.completed == 1 else "UNKNOWN"

    def invoke_cleanup_once(self):
        program_stop = self._program_entry is not None and self._program_entry[1] == "request_stop"
        if not program_stop and self.name not in ("CloseHandle", "VirtualFree", "RtlDeleteFunctionTable",
                             "TerminateJobObject", "TerminateProcess", "SetEvent",
                             "WaitForSingleObject", "GetExitCodeProcess", "GetProcessTimes", "GetThreadTimes"):
            raise _ERROR
        if not self._entry_lock.acquire(False):
            raise _ERROR
        self.gate._check_cleanup()
        self._resolve_program()
        self._invoke_direct(cleanup=True)


class _CloseSlot:
    __slots__ = ("gate", "source", "closing", "reference", "call", "consumed", "_entry_lock")

    def __init__(self, gate, source):
        if type(source) is not _RawReference or source.owner.gate is not gate:
            raise TypeError("original owner raw HANDLE slot required")
        self.gate, self.source, self.closing = gate, source, _U64()
        self._entry_lock = _allocate_lock()
        self.reference = _RawReference(self, _c.addressof(self.closing))
        self.call = gate.new_call("CloseHandle", (self.reference,))
        self.consumed = False

    def close_once(self):
        if not self._entry_lock.acquire(False) or self.consumed:
            raise _ERROR
        # Native byte copy: never read .value or construct a Python HANDLE int.
        # Consume before the close call, including on a conversion exception.
        _MEMMOVE(_c.addressof(self.closing), self.source.address, 8)
        self.consumed = True
        self.call.invoke_cleanup_once()


class _LoadedWin64Gate:
    """Already-loaded libffi + kernel32; exact profile choice is NOT proof.

    Actual mapped provider/version/header/immutable-image validation is an
    upstream precondition.  Nothing loads, discovers or substitutes an image.
    Construct all outputs, calls and close slots before ``prepare_once``.
    Retained objects survive every Python exception; no automatic retry/reset.
    """
    __slots__ = ("_ffi", "_kernel", "_handles", "_exports", "_types", "_call",
                 "_prep", "_call_address", "_prep_address", "_calls", "_outputs",
                 "_closed_slots", "_prepared", "_prepare_attempted", "_drifted",
                 "_call_type", "_prep_type", "_call_flags", "_prep_flags",
                 "_cleanup_call", "_cleanup_type", "_cleanup_flags",
                 "_stub_cif", "_stub_atypes", "_stub_bytes", "_stub_ignored", "_prepare_lock", "_build_lock")

    def __init__(self, loaded_libffi, loaded_kernel32, *, header_profile):
        global _LIVE_GATE
        if (_sys.platform != "win32" or _c.sizeof(_P) != 8 or not _layout() or
                header_profile != PROFILE):
            raise PermissionError("exact Windows AMD64 libffi3.3 header profile required")
        if not _GATE_RESERVE_LOCK.acquire(False) or _LIVE_GATE is not None:
            raise _ERROR
        for library in (loaded_libffi, loaded_kernel32):
            if type(library) not in (_c.CDLL, _c.WinDLL) or not library._handle:
                raise TypeError("genuine already loaded original native images required")
        self._ffi, self._kernel = loaded_libffi, loaded_kernel32
        self._handles = (loaded_libffi._handle, loaded_kernel32._handle)
        self._calls, self._outputs, self._closed_slots = [], [], []
        self._prepare_lock = _allocate_lock()
        self._build_lock = _RLock()
        self._prepared = self._prepare_attempted = self._drifted = False
        self._exports = {name: _FrozenExport(loaded_kernel32, name) for name in _SIGNATURES}
        self._exports["ffi_call"] = _FrozenExport(loaded_libffi, "ffi_call")
        self._exports["ffi_prep_cif"] = _FrozenExport(loaded_libffi, "ffi_prep_cif")
        self._exports = _Map(self._exports)
        types = {}
        for code, (symbol, size, alignment, tag) in _TYPE_EXPORTS.items():
            native = _FFIType.in_dll(loaded_libffi, symbol)
            if (native.size, native.alignment, native.type, native.elements) != (size, alignment, tag, None):
                raise _ERROR
            address = _c.addressof(native)
            types[code] = (native, address, _STRING_AT(address, 24))
        self._types = _Map(types)
        self._call_address = self._exports["ffi_call"].address
        self._prep_address = self._exports["ffi_prep_cif"].address
        self._call = _c.CFUNCTYPE(None, _P, _P, _P, _P)(self._call_address)
        self._cleanup_call = _c.CFUNCTYPE(None, _P, _P, _P, _P)(self._call_address)
        self._prep = _c.CFUNCTYPE(_U32, _P, _U32, _U32, _P, _P)(self._prep_address)
        self._call_type, self._prep_type = type(self._call), type(self._prep)
        self._call_flags, self._prep_flags = self._call._flags_, self._prep._flags_
        self._cleanup_type, self._cleanup_flags = type(self._cleanup_call), self._cleanup_call._flags_
        self._stub_cif, self._stub_atypes = _GuardedCIF(), (_P * 1)(self._types["p"][1])
        self._stub_bytes, self._stub_ignored = None, _U64()
        for side in (self._stub_cif.before, self._stub_cif.after):
            side[0] = side[1] = _CANARY
        _LIVE_GATE = self

    def _check(self):
        try:
            okay = (not self._drifted and _LIVE_GATE is self and
                    (self._ffi._handle, self._kernel._handle) == self._handles and
                    type(self._call) is self._call_type and type(self._prep) is self._prep_type and
                    self._call._flags_ == self._call_flags and self._prep._flags_ == self._prep_flags and
                    self._call.restype is None and self._prep.restype is _U32 and
                    getattr(self._call, "errcheck", None) is None and
                    getattr(self._prep, "errcheck", None) is None and
                    self._call.argtypes == (_P, _P, _P, _P) and
                    self._prep.argtypes == (_P, _U32, _U32, _P, _P) and
                    _address(self._call) == self._call_address and
                    _address(self._prep) == self._prep_address and
                    all(x.unchanged() for x in self._exports.values()) and
                    all(_STRING_AT(address, 24) == raw for _, address, raw in self._types.values()))
        except BaseException:
            self._drifted = True
            raise
        if not okay:
            self._drifted = True
            raise _ERROR

    def _check_cleanup(self):
        """Caller metadata drift stops new work, retains original safe cleanup.

        Actual module HANDLE/type/global/CIF drift still prevents invocation.
        No callback, mutated public wrapper or replacement HANDLE is used.
        """
        okay = (self._prepared and _LIVE_GATE is self and
                (self._ffi._handle, self._kernel._handle) == self._handles and
                type(self._cleanup_call) is self._cleanup_type and
                self._cleanup_call._flags_ == self._cleanup_flags and
                self._cleanup_call.restype is None and
                self._cleanup_call.argtypes == (_P, _P, _P, _P) and
                getattr(self._cleanup_call, "errcheck", None) is None and
                _address(self._cleanup_call) == self._call_address and
                all(_STRING_AT(address, 24) == raw for _, address, raw in self._types.values()))
        if not okay:
            self._drifted = True
            raise _ERROR

    def _stub_unchanged(self):
        return (self._stub_bytes is not None and
                _STRING_AT(_c.addressof(self._stub_cif), _c.sizeof(self._stub_cif)) == self._stub_bytes and
                self._stub_atypes[0] == self._types["p"][1])

    def output(self, size):
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            self._check()
            if self._prepare_attempted or len(self._outputs) >= _MAX_BUFFERS:
                raise _ERROR
            output = _Output(self, size)
            self._outputs.append(output)
            return output
        finally:
            self._build_lock.release()

    def new_call(self, name, arguments):
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            self._check()
            if (self._prepare_attempted or type(name) is not str or name not in _SIGNATURES or
                    name == "CreateThread" or len(self._calls) >= _MAX_CALLS):
                raise _ERROR
            call = _RawCall(self, name, arguments)
            self._calls.append(call)
            return call
        finally:
            self._build_lock.release()

    def new_deadline_call(self, program, entry_name, argument):
        """Four fixed owned program entries, never an arbitrary target address.

        The exact program module must already be loaded. Its original code
        allocation/offset/byte identity are checked when resolving the entry;
        selecting a class or entry name establishes no preparation authority.
        """
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            module = _sys.modules.get(__package__ + ".windows_compile_free_deadline")
            cls = getattr(module, "_FixedDeadlineProgram", None) if module is not None else None
            if (cls is None or type(program) is not cls or program.gate is not self or
                    argument is not program._context_pointer or type(entry_name) is not str or
                    entry_name not in ("watchdog", "birth_next", "resume_current", "request_stop")):
                raise TypeError("exact installed-owner deadline entry required")
            call = self.new_call("ResumeThread", (argument,))  # Exact u32(pointer) CIF.
            call._program_entry = (program, entry_name, cls._gate_entry, cls._check_entry)
            call.function = call.frame.function = 0  # Resolve only after actual code installation.
            return call
        finally:
            self._build_lock.release()

    def new_deadline_thread(self, program, context_argument):
        """Reserve only the exact fixed owner's watchdog thread, never a callback.

        All thread arguments are constructed here; the caller supplies only the
        same owner's original context cell. Native creation still resolves and
        verifies the installed watchdog code/context immediately before call.
        """
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            self._check()
            module = _sys.modules.get(__package__ + ".windows_compile_free_deadline")
            cls = getattr(module, "_FixedDeadlineProgram", None) if module is not None else None
            if cls is None or type(program) is not cls or program.gate is not self:
                raise TypeError("exact original fixed watchdog owner required")
            if (self._prepare_attempted or len(self._calls) >= _MAX_CALLS or
                    context_argument is not program._context_pointer):
                raise _ERROR
            call = _RawCall(self, "CreateThread", None, deadline_program=program)
            self._calls.append(call)
            return call
        finally:
            self._build_lock.release()

    def own_handle(self, original_reference):
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            self._check()
            if self._prepare_attempted:
                raise _ERROR
            close = _CloseSlot(self, original_reference)
            self._closed_slots.append(close)
            return close
        finally:
            self._build_lock.release()

    def prepare_once(self):
        if not self._prepare_lock.acquire(False):
            raise _ERROR
        if not self._build_lock.acquire(False):
            raise _ERROR
        try:
            self._prepare_locked()
        finally:
            self._build_lock.release()

    def _prepare_locked(self):
        self._check()
        if self._prepare_attempted:
            raise _ERROR
        self._prepare_attempted = True
        self._calls, self._outputs, self._closed_slots = tuple(self._calls), tuple(self._outputs), tuple(self._closed_slots)
        for call in self._calls:
            call._prepare()
        status = self._prep(_c.byref(self._stub_cif.cif), 1, 1,
                            self._types["v"][1], self._stub_atypes)
        cif = self._stub_cif.cif
        if (status != 0 or tuple(self._stub_cif.before) != (_CANARY, _CANARY) or
                tuple(self._stub_cif.after) != (_CANARY, _CANARY) or cif.abi != 1 or
                cif.nargs != 1 or cif.arg_types != _c.addressof(self._stub_atypes) or
                cif.rtype != self._types["v"][1] or cif.bytes != 32 or cif.flags != 0):
            self._drifted = True
            raise _ERROR
        self._stub_bytes = _STRING_AT(_c.addressof(self._stub_cif), _c.sizeof(self._stub_cif))
        self._prepared = True


# Fixed audited Win64 sequence, not an assembler or user-supplied code facility.
# Entry RSP%16=8; push RBX and subtract80 gives aligned target call with 32-byte
# shadow plus six stack arguments. RBX retains frame across both WinAPI calls.
# Store RAX at96, call GetLastError at8 immediately, store EAX104, completed108.
_CALL_STORE = bytes.fromhex(
    "f30f1efa 53 4883ec50 4889cb c7437001000000 "
    "488b4330 4889442420 488b4338 4889442428 "
    "488b4340 4889442430 488b4348 4889442438 "
    "488b4350 4889442440 488b4358 4889442448 "
    "488b4b10 488b5318 4c8b4320 4c8b4b28 ff13 "
    "48894360 ff5308 894368 c7436c01000000 4883c450 5b c3"
)
_UNWIND_OFFSET = (len(_CALL_STORE) + 3) & ~3
# Version1, prolog9, two unwind slots: alloc80 at9, pushRBX at5.
_UNWIND = bytes.fromhex("0109020009920530")
_FUNCTION_OFFSET = _UNWIND_OFFSET + len(_UNWIND)
_FUNCTION_ENTRY = (0).to_bytes(4, "little") + len(_CALL_STORE).to_bytes(4, "little") + _UNWIND_OFFSET.to_bytes(4, "little")
_CODE_IMAGE = (_CALL_STORE + bytes(_UNWIND_OFFSET - len(_CALL_STORE)) +
               _UNWIND + _FUNCTION_ENTRY)


class _FixedCallStore:
    """One fixed native return+LastError stub; installation is not activation.

    ``install_once`` performs real native allocation/protection/query and needs
    the original owner's permission/budget before it is called.  This component
    deliberately exposes no unchecked ``invoke(address)`` API.  It records a
    verified RX region, while provider closure and alias exclusion must still be
    established by the actual trusted owner before a production dispatcher is
    connected.  Allocation remains retained on ambiguous release.
    """
    __slots__ = ("gate", "alloc", "protect", "flush", "query", "free", "old",
                 "region", "attempted", "ready", "release_consumed", "address",
                 "register", "unregister", "table_pointer", "_lifecycle_lock")

    def __init__(self, gate):
        if type(gate) is not _LoadedWin64Gate or gate._prepare_attempted:
            raise TypeError("original unprepared native gate required")
        self.gate, self.attempted, self.ready = gate, False, False
        self._lifecycle_lock = _allocate_lock()
        self.release_consumed, self.address = False, None
        self.old, self.region = gate.output(4), gate.output(48)
        self.alloc = gate.new_call("VirtualAlloc", (_P(), _U64(4096), _U32(0x3000), _U32(4)))
        raw = self.alloc.result_reference
        self.protect = gate.new_call("VirtualProtect", (raw, _U64(4096), _U32(0x20), self.old.reference))
        self.flush = gate.new_call("FlushInstructionCache", (_P(-1), raw, _U64(len(_CODE_IMAGE))))
        self.query = gate.new_call("VirtualQuery", (raw, self.region.reference, _U64(48)))
        self.table_pointer = _P()
        self.register = gate.new_call("RtlAddFunctionTable", (self.table_pointer, _U32(1), raw))
        self.unregister = gate.new_call("RtlDeleteFunctionTable", (self.table_pointer,))
        self.free = gate.new_call("VirtualFree", (raw, _U64(), _U32(0x8000)))

    def install_once(self):
        if not self._lifecycle_lock.acquire(False):
            raise _ERROR
        try:
            if self.attempted or self.release_consumed:
                raise _ERROR
            self.attempted = True
            self.alloc.invoke_once()
            address = self.alloc.result.value  # Original native allocation stays anchored before conversion.
            if not address:
                raise _ERROR
            self.address = address
            self.table_pointer.value = address + _FUNCTION_OFFSET
            _MEMMOVE(address, _CODE_IMAGE, len(_CODE_IMAGE))
            self.protect.invoke_once()
            if not self.protect.result.value or _U32.from_buffer(self.old.storage).value != 4:
                raise _ERROR
            self.flush.invoke_once()
            if not self.flush.result.value:
                raise _ERROR
            self.query.invoke_once()
            info = _MemoryInfo.from_buffer(self.region.storage)
            if (self.query.result.value != 48 or info.base != address or
                    info.allocation_base != address or info.region_size != 4096 or
                    info.state != 0x1000 or info.protect != 0x20 or info.type != 0x20000 or
                    _STRING_AT(address, len(_CODE_IMAGE)) != _CODE_IMAGE):
                raise _ERROR
            self.register.invoke_once()
            if not self.register.result.value:
                raise _ERROR
            self.ready = True  # Region+unwind registration, NOT provider/lease admission.
        finally:
            self._lifecycle_lock.release()

    def _check_region(self):
        # The original query was performed after RW->RX and cache flush.  This
        # component never remaps, exports a section, or restores write access.
        # Immutable owner closure must exclude outside mutation/alias writers.
        if (not self.ready or self.release_consumed or not self.address or
                not self.query.returned or not self.protect.returned or
                not self.flush.returned or not self.register.returned or
                not self.register.result.value or
                _STRING_AT(self.address, len(_CODE_IMAGE)) != _CODE_IMAGE):
            raise _ERROR

    def release_once(self):
        if not self._lifecycle_lock.acquire(False):
            raise _ERROR
        try:
            if self.release_consumed or not self.alloc.attempted:
                raise _ERROR
            self.release_consumed = True
            self.ready = False
            # The owner MUST join every user of this code before entering here.
            # Ambiguous registration/delete keeps the original allocation alive.
            if self.register.attempted:
                if not (self.register.returned and self.register.result.value == 0):
                    self.unregister.invoke_cleanup_once()
                    if not self.unregister.returned or not self.unregister.result.value:
                        raise _ERROR
            self.free.invoke_cleanup_once()  # Native original allocation slot, no Python address copy.
            if not self.free.returned or not self.free.result.value:
                raise _ERROR
        finally:
            self._lifecycle_lock.release()
