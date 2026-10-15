"""No-GT mechanism harness SOURCE. No CLI, provider loader or auto execution.

An authorized original preparation owner constructs the already-loaded gate,
calls ``reserve(gate)`` BEFORE prepare_once, establishes all original resource,
deadline, immutable-load and cleanup bounds, and then runs this fixture inside
those bounds. This file does not create/restart a preparation epoch. It creates
no child process/thread, writes no file, and consumes bounded existing call slots.

The owner-side MemoryError case is an exception AFTER native return. It is not
claimed to reproduce an allocator failure inside ctypes' return conversion.
All retained result/output storage is the same storage used by that path.
"""

import ctypes as c

from eating_event.route2_candidate_overlap.windows_compile_free_gate import (
    _LoadedWin64Gate, _FixedCallStore, _RawCall, _layout, _Frame, _CIF, _FFIType,
    _CALL_STORE, _CODE_IMAGE, _UNWIND, _UNWIND_OFFSET, _FUNCTION_OFFSET,
)


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _reject_unowned_thread_callbacks(gate):
    """Reservation-only negative cases: none may reach native CreateThread."""
    arguments = (c.c_void_p(), c.c_uint64(65536), c.c_void_p(0x11111111),
                 c.c_void_p(), c.c_uint32(0x10000), c.c_void_p())
    before = len(gate._calls)
    for reserve in (
        lambda: gate.new_call("CreateThread", arguments),
        lambda: _RawCall(gate, "CreateThread", arguments),
        lambda: _RawCall(gate, "CreateThread", None),
        lambda: gate.new_deadline_thread(object(), c.c_void_p()),
    ):
        try:
            reserve()
        except (RuntimeError, TypeError):
            pass
        else:
            raise AssertionError("unowned thread callback reservation was accepted")
    _require(len(gate._calls) == before, "rejected callback retained an activatable call")


def verify_unresolved_program_reservation(call):
    """Check the actual private-dispatch guard before any native preparation.

    Pass a real call returned by new_deadline_call while its owner is still
    uninstalled. This checks the same guard used by _invoke_direct; it does not
    fabricate a prepared gate/CIF, invoke ffi_call, or activate the program.
    """
    if (type(call) is not _RawCall or call.gate._prepare_attempted or
            call._program_entry is None or call._program_identity is not None):
        raise TypeError("original unresolved owned-program reservation required")
    _require(call.function == 0 and call.frame.function == 0, "reservation resolved too early")
    _require(not call._inputs_unchanged(), "unresolved private dispatch accepts target zero")
    _require(not call.attempted, "reservation check executed a native call")


class _Fixture:
    __slots__ = ("gate", "store", "events", "closes", "bad_event", "qpc",
                 "frequency", "qpc_output", "frequency_output", "started")

    def __init__(self, gate):
        if type(gate) is not _LoadedWin64Gate or gate._prepare_attempted:
            raise TypeError("original already-loaded unprepared gate required")
        _reject_unowned_thread_callbacks(gate)
        self.gate, self.started = gate, False
        self.store = _FixedCallStore(gate)
        self.events, self.closes = [], []
        for _ in range(3):
            call = gate.new_call("CreateEventW", (c.c_void_p(), c.c_int32(1),
                                                  c.c_int32(), c.c_void_p()))
            self.events.append(call)
            self.closes.append(gate.own_handle(call.result_reference))
        self.bad_event = gate.new_call("SetEvent", (c.c_void_p(),))
        self.qpc_output, self.frequency_output = gate.output(8), gate.output(8)
        self.qpc = gate.new_call("QueryPerformanceCounter", (self.qpc_output.reference,))
        self.frequency = gate.new_call("QueryPerformanceFrequency", (self.frequency_output.reference,))

    def run_once(self):
        if self.started or not self.gate._prepared:
            raise RuntimeError("prepared original one-shot fixture required")
        self.started = True
        primary = None
        close_errors = []
        try:
            _require(_layout(), "exact Win64 layouts differ")
            _require((c.sizeof(_CIF), c.sizeof(_FFIType), c.sizeof(_Frame)) == (32, 24, 120), "ABI sizes")
            _require(_CALL_STORE.startswith(bytes.fromhex("f30f1efa534883ec50")), "Win64 prolog")
            _require(_UNWIND == bytes.fromhex("0109020009920530"), "unwind program")
            _require(_CODE_IMAGE[_UNWIND_OFFSET:_FUNCTION_OFFSET] == _UNWIND, "immutable unwind image")
            self.qpc.invoke_once()
            self.frequency.invoke_once()
            _require(self.qpc.result.value and self.frequency.result.value, "raw QPC/frequency query failed")
            _require(c.c_int64.from_buffer(self.frequency_output.storage).value > 0, "nonpositive native frequency")
            _require(self.qpc.last_error_state == "UNKNOWN", "direct-call LastError mislabeled")

            self.events[0].invoke_once()
            _require(self.events[0].result.value != 0, "direct event creation failed")
            original_address = c.addressof(self.events[0].result)
            try:
                raise MemoryError("owner-side failure after native acquisition")
            except MemoryError:
                _require(c.addressof(self.events[0].result) == original_address, "raw result slot moved")
                self.closes[0].close_once()
                _require(self.closes[0].consumed and self.closes[0].call.result.value, "original raw close failed")

            self.store.install_once()
            self.events[1].invoke_store_once(self.store)
            _require(self.events[1].result.value != 0 and self.events[1].frame.completed == 1, "stored event acquisition")
            _require(self.events[1].last_error_state == "RAW_CAPTURED", "native error capture absent")
            self.bad_event.invoke_store_once(self.store)
            _require(self.bad_event.result.value == 0 and self.bad_event.frame.last_error == 6,
                     "invalid SetEvent did not retain ERROR_INVALID_HANDLE")
            try:
                self.events[1].invoke_store_once(self.store)
            except RuntimeError:
                pass
            else:
                raise AssertionError("same native call was reused")

            # A public wrapper metadata mutation must stop new work. A separate
            # original cleanup wrapper must still close already-owned HANDLEs.
            self.gate._call.restype = c.c_uint64
            try:
                self.events[2].invoke_once()
            except RuntimeError:
                _require(not self.events[2].attempted, "drift executed a new birth")
            else:
                raise AssertionError("caller wrapper drift was accepted")
            self.closes[1].close_once()
            _require(self.closes[1].consumed and self.closes[1].call.result.value, "cleanup after drift failed")
        except BaseException as error:
            primary = error
        finally:
            # All close attempts use original native slots, never extracted
            # Python HANDLE values. Uncertain outcomes remain retained; no retry.
            for call, close in zip(self.events, self.closes):
                if call.attempted and not close.consumed:
                    try:
                        close.close_once()
                    except BaseException as error:
                        close_errors.append(error)
            if self.store.alloc.attempted and not self.store.release_consumed:
                try:
                    self.store.release_once()
                except BaseException as error:
                    close_errors.append(error)
        if primary is not None or close_errors:
            return {"harness_passed": False, "primary": primary, "cleanup": tuple(close_errors),
                    "residual_owner": self}
        return {"harness_passed": True, "scenarios": ("raw_clock", "raw_handle",
                "owner_exception", "native_error_capture", "once_only", "drift_cleanup"), "cleanup": ()}


def reserve(gate):
    """Reserve fixture storage only. Native execution is a later owner action."""
    return _Fixture(gate)
