"""Fixed Win64 deadline/birth program for the original preparation owner.

SOURCE mechanism only. Import constructs bytes, never loads or executes code.
Installation and every invocation require the real, already accounted owner,
provider/preload closure, immutable Job/input ownership and physical boundary.
This module issues no lease and does not make complete RAM or admission claims.

One original Job, event, watcher and absolute QPC interval cover a fixed bank of
at most 32 SERIAL children. Slots, original PI and failures are never recycled.
The watchdog is native code, with no Python/managed callback or GIL dependency.
Only this exact fixed program is accepted by windows_compile_free_gate's bridge.

Official contracts: Microsoft x64 calling convention; ThreadProc; CreateThread;
CreateProcessW; ResumeThread; QueryPerformanceCounter; TerminateJobObject;
WaitForSingleObject; RtlAddFunctionTable; VirtualProtect/FlushInstructionCache.
The dynamic code carries its own x64 unwind table. API documentation is not
evidence that installation, identity, privileges or runtime validation occurred.
"""

from __future__ import annotations

import ctypes as _c
import hashlib as _hashlib
import struct as _struct
from dataclasses import dataclass as _dataclass
from types import MappingProxyType as _Map
from _thread import allocate_lock as _allocate_lock

from .windows_compile_free_gate import (
    _LoadedWin64Gate, _RawReference, _RawCall, _Output, _FixedCallStore, _MemoryInfo,
)

_P, _U32, _U64 = _c.c_void_p, _c.c_uint32, _c.c_uint64
_MOVE, _READ = _c.memmove, _c.string_at
_LIVE_PROGRAM = None                 # Original owner/history anchor; no reset.
_MAX_CHILDREN, _SLOT_BYTES, _STATE_BYTES = 32, 512, 20480
_CODE_BYTES, _CONTEXT_BYTES = 8192, 4096
_MAGIC = 0x3147445744325252
_NONE, _WAIT_TIMEOUT = 0xFFFFFFFF, 258
_ERROR = RuntimeError("native deadline program incomplete; retain original anchors")

# Immutable context: all addresses below are exact already-loaded API targets.
_F = _Map(dict(qpc=72, qpf=80, wait=88, kill_job=96, error=104,
              birth=112, resume=120, kill_process=128, event=136,
              job_query=144, process_times=152, thread_times=160,
              process_exit=168, thread_exit=176, reset_event=200))
_EXPORTS = _Map(dict(qpc="QueryPerformanceCounter", qpf="QueryPerformanceFrequency",
    wait="WaitForSingleObject", kill_job="TerminateJobObject", error="GetLastError",
    birth="CreateProcessW", resume="ResumeThread", kill_process="TerminateProcess",
    event="SetEvent", job_query="QueryInformationJobObject",
    process_times="GetProcessTimes", thread_times="GetThreadTimes",
    process_exit="GetExitCodeProcess", thread_exit="GetExitCodeThread",
    reset_event="ResetEvent"))


class _X64:
    """Private fixed-template encoder, not an arbitrary-code public facility.

    Registers: rax0 rcx1 rdx2 rbx3 rsp4 r8=8 r9=9 r10=10 r11=11.
    Every memory form uses disp32; RSP forms have the required SIB byte.
    Labels are internal constants. All rel32 targets must resolve in this image.
    """
    def __init__(self):
        self.code, self.labels, self.fixups, self.ranges = bytearray(), {}, [], []
        self.serial = 0

    def put(self, raw):
        self.code.extend(raw)

    def label(self, name):
        if name in self.labels:
            raise ValueError("duplicate fixed label")
        self.labels[name] = len(self.code)

    def unique(self, prefix):
        self.serial += 1
        return prefix + str(self.serial)

    def mem(self, opcode, reg, base, offset, *, wide=True, prefix=b""):
        self.put(prefix)
        rex = 0x40 | (8 if wide else 0) | (4 if reg >= 8 else 0) | (1 if base >= 8 else 0)
        if rex != 0x40:
            self.put(bytes((rex,)))
        self.put(opcode)
        self.put(bytes((0x80 | ((reg & 7) << 3) | (base & 7),)))
        if base & 7 == 4:
            self.put(b"\x24")
        self.put(_struct.pack("<i", offset))

    def load(self, reg, base, offset, wide=True):
        self.mem(b"\x8b", reg, base, offset, wide=wide)

    def store(self, base, offset, reg, wide=True):
        self.mem(b"\x89", reg, base, offset, wide=wide)

    def lea(self, reg, base, offset):
        self.mem(b"\x8d", reg, base, offset)

    def imm(self, reg, value, wide=False):
        if wide:
            self.put(bytes((0x48 | (1 if reg >= 8 else 0), 0xB8 | (reg & 7))))
            self.put(_struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))
        else:
            if reg >= 8:
                self.put(b"\x41")
            self.put(bytes((0xB8 | (reg & 7),)))
            self.put(_struct.pack("<I", value & 0xFFFFFFFF))

    def set32(self, base, offset, value):
        self.mem(b"\xc7", 0, base, offset, wide=False)
        self.put(_struct.pack("<I", value & 0xFFFFFFFF))

    def rr(self, opcode, left, right, wide=True):
        rex = 0x40 | (8 if wide else 0) | (4 if right >= 8 else 0) | (1 if left >= 8 else 0)
        if rex != 0x40:
            self.put(bytes((rex,)))
        self.put(bytes((opcode, 0xC0 | ((right & 7) << 3) | (left & 7))))

    def cmp_imm(self, reg, value, wide=False):
        rex = 0x40 | (8 if wide else 0) | (1 if reg >= 8 else 0)
        if rex != 0x40:
            self.put(bytes((rex,)))
        self.put(bytes((0x81, 0xF8 | (reg & 7))))
        self.put(_struct.pack("<I", value & 0xFFFFFFFF))

    def add_imm(self, reg, value):
        self.put(bytes((0x48 | (1 if reg >= 8 else 0), 0x81, 0xC0 | (reg & 7))))
        self.put(_struct.pack("<i", value))

    def jump(self, name, condition=None):
        self.put(b"\xe9" if condition is None else bytes((0x0F, condition)))
        self.fixups.append((len(self.code), name))
        self.put(b"\0" * 4)

    def call(self, name):
        self.mem(b"\xff", 2, 3, _F[name])

    def state(self):
        self.load(10, 3, 64)

    def slot(self):
        self.load(11, 4, 88)          # Callee-stable stack local, not R11 across API.

    def slot_from_index(self):
        # EAX is validated index. R10 is state. RAX becomes state+4096+index*512.
        self.put(b"\x48\xc1\xe0\x09")
        self.rr(0x01, 0, 10)
        self.add_imm(0, 4096)
        self.store(4, 88, 0)

    def atomic32(self, base, offset, reg):
        self.mem(b"\x87", reg, base, offset, wide=False)

    def cas32(self, base, offset, new_reg):
        self.mem(b"\x0f\xb1", new_reg, base, offset, wide=False, prefix=b"\xf0")

    def fault(self, bit):
        self.state()
        self.mem(b"\x0f\xba", 5, 10, 24, prefix=b"\xf0")
        self.put(bytes((bit,)))       # LOCK BTS qword[state+24], imm8.
        self.imm(0, 1)
        self.atomic32(10, 4, 0)

    def begin(self, name):
        while len(self.code) % 16:
            self.put(b"\x90")
        self.label(name)
        begin = len(self.code)
        self.put(bytes.fromhex("f30f1efa 53 4881ec80000000 4889cb"))
        self.imm(0, 0)
        self.store(4, 104, 0)       # Failure before first QPC has invalid raw zero.
        return begin

    def end(self, begin, name):
        self.label(name + "_return")
        self.put(bytes.fromhex("4881c480000000 5b c3"))
        self.ranges.append((begin, len(self.code), name))

    def finish(self):
        for offset, name in self.fixups:
            if name not in self.labels:
                raise ValueError("unresolved fixed native label")
            owner = next((r for r in self.ranges if r[0] <= offset < r[1]), None)
            if owner is None or not owner[0] <= self.labels[name] < owner[1]:
                raise ValueError("fixed branch escapes its original native frame")
            displacement = self.labels[name] - (offset + 4)
            self.code[offset:offset + 4] = _struct.pack("<i", displacement)
        while len(self.code) % 4:
            self.put(b"\0")
        unwind_offset = len(self.code)
        self.put(bytes.fromhex("010c03000c01100005300000"))
        table_offset = len(self.code)
        for begin, end, _ in self.ranges:
            self.put(_struct.pack("<III", begin, end, unwind_offset))
        if len(self.code) > _CODE_BYTES:
            raise ValueError("fixed deadline image exceeds 8192-byte source bound")
        return bytes(self.code), tuple(self.ranges), table_offset, unwind_offset


def _qpc(a, fail, *, watcher=False, stop_check=False):
    a.lea(1, 4, 104)
    a.call("qpc")
    a.rr(0x85, 0, 0, False)
    a.jump(fail, 0x84)
    a.load(0, 4, 104)
    a.load(2, 3, 16)
    a.rr(0x39, 0, 2)
    a.jump(fail, 0x8C)              # JL: now < original epoch.
    if watcher:
        a.state()
        a.load(2, 10, 40)
        a.rr(0x39, 0, 2)
        a.jump(fail, 0x8C)
        a.store(10, 40, 0)
    if stop_check:
        a.load(2, 3, 32)
        a.rr(0x39, 0, 2)
        a.jump(fail, 0x8D)          # JGE: never create/resume at STOP.
        a.state()
        a.load(2, 10, 4, False)
        a.rr(0x85, 2, 2, False)
        a.jump(fail, 0x85)


def _kill(a, *, second=False):
    offset = 92 if second else 80
    already = a.unique("kill_already")
    a.state()
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(10, offset, 1)
    a.jump(already, 0x85)
    a.load(0, 4, 104)
    a.store(10, 64 if second else 56, 0)
    a.load(1, 3, 48)
    a.load(2, 3, 228, False)
    a.call("kill_job")
    a.state()
    a.store(10, offset + 4, 0, False)
    okay = a.unique("kill_ok")
    a.rr(0x85, 0, 0, False)
    a.jump(okay, 0x85)
    a.call("error")
    a.state()
    a.store(10, offset + 8, 0, False)
    a.fault(3 if second else 2)
    a.label(okay)
    a.label(already)


def _capture_error(a, operation):
    """Immediate native LastError, bounded first-fault metadata, separate bit."""
    a.call("error")
    a.store(4, 120, 0, False)
    a.state()
    a.imm(0, 0)
    a.imm(1, operation)
    a.cas32(10, 240, 1)
    seen = a.unique("fault_seen")
    a.jump(seen, 0x85)
    a.load(0, 4, 120, False)
    a.store(10, 244, 0, False)
    a.load(0, 4, 104)
    a.store(10, 248, 0)
    a.label(seen)


def _wait_delay(a, deadline_offset):
    """EDX is 0 in last partial millisecond, otherwise 1; no fresh deadline."""
    a.load(0, 3, deadline_offset)
    a.load(2, 4, 104)
    a.rr(0x29, 0, 2)
    a.load(2, 3, 232)
    a.rr(0x39, 0, 2)
    short, done = a.unique("wait_short"), a.unique("wait_delay_done")
    a.jump(short, 0x82)
    a.imm(2, 1)
    a.jump(done)
    a.label(short)
    a.imm(2, 0)
    a.label(done)


def _job_query(a, fail):
    a.load(1, 3, 48)
    a.imm(2, 1)
    a.state()
    a.lea(8, 10, 128)
    a.imm(9, 48)
    a.imm(0, 0)
    a.store(4, 32, 0)
    a.call("job_query")
    a.state()
    a.store(10, 176, 0, False)
    a.rr(0x85, 0, 0, False)
    api_okay = a.unique("job_query_api_okay")
    a.jump(api_okay, 0x85)
    _capture_error(a, 16)
    a.jump(fail)
    a.label(api_okay)
    a.load(0, 10, 168, False)       # JOBOBJECT_BASIC_ACCOUNTING.ActiveProcesses.
    a.store(10, 180, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump(fail, 0x85)
    a.load(0, 10, 164, False)       # TotalProcesses == original successful births.
    a.load(2, 10, 104, False)
    a.rr(0x39, 0, 2, False)
    a.jump(fail, 0x85)


def _times(a, api, handle_offset, target, fail):
    a.slot()
    a.load(1, 11, handle_offset)
    a.lea(2, 11, target)
    a.lea(8, 11, target + 8)
    a.lea(9, 11, target + 16)
    a.lea(0, 11, target + 24)
    a.store(4, 32, 0)
    a.call(api)
    a.slot()
    a.store(11, 88 if api == "process_times" else 92, 0, False)
    a.rr(0x85, 0, 0, False)
    okay = a.unique("times_okay")
    a.jump(okay, 0x85)
    _capture_error(a, 17 if api == "process_times" else 18)
    a.jump(fail)
    a.label(okay)


def _build_image():
    a = _X64()
    # WATCHER. One native actor, no loader/CRT/Python callback.
    start = a.begin("watchdog")
    a.state()
    a.set32(10, 12, 1)
    a.lea(1, 4, 112)
    a.call("qpf")
    a.rr(0x85, 0, 0, False)
    a.jump("w_clock_fail", 0x84)
    a.load(0, 4, 112)
    a.load(2, 3, 24)
    a.rr(0x39, 0, 2)
    a.jump("w_clock_fail", 0x85)
    _qpc(a, "w_clock_fail", watcher=True)
    a.state()
    a.store(10, 32, 0)
    a.imm(0, 1)
    a.atomic32(10, 8, 0)
    a.label("w_loop")
    _qpc(a, "w_clock_fail", watcher=True)
    a.load(2, 3, 40)
    a.rr(0x39, 0, 2)
    a.jump("w_expired", 0x8D)
    a.state()
    a.load(0, 10, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_stopping", 0x85)
    a.load(0, 4, 104)
    a.load(2, 3, 32)
    a.rr(0x39, 0, 2)
    a.jump("w_stop_latch", 0x8D)
    a.jump("w_current")
    a.label("w_stop_latch")
    a.imm(0, 1)
    a.atomic32(10, 4, 0)
    a.load(0, 4, 104)
    a.store(10, 48, 0)
    a.label("w_stopping")
    a.state()
    a.load(0, 10, 80, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_current", 0x85)
    _kill(a)
    a.label("w_current")
    a.state()
    a.load(0, 10, 16, False)
    a.cmp_imm(0, _NONE)
    a.jump("w_idle", 0x84)
    a.cmp_imm(0, _MAX_CHILDREN)
    a.jump("w_bad", 0x83)
    a.slot_from_index()
    a.slot()
    a.load(0, 11, 0, False)
    a.cmp_imm(0, 2)
    a.jump("w_wait", 0x85)         # CLAIMED PI is never read by watcher.
    a.load(0, 11, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_failed_birth", 0x84)
    a.state()
    a.load(0, 10, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait_process", 0x84)
    a.load(0, 10, 92, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait_process", 0x85)
    _kill(a, second=True)
    # Original process fallback if Job termination failed; retained PI only.
    a.state()
    a.load(0, 10, 96, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait_process", 0x85)
    a.slot()
    a.set32(11, 268, 1)
    a.load(1, 11, 48)
    a.load(2, 3, 228, False)
    a.call("kill_process")
    a.slot()
    a.store(11, 272, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait_process", 0x85)
    a.call("error")
    a.slot()
    a.store(11, 276, 0, False)
    a.fault(4)
    a.label("w_wait_process")
    a.slot()
    a.load(1, 11, 48)
    a.imm(2, 0)
    a.call("wait")
    a.slot()
    a.store(11, 72, 0, False)
    a.cmp_imm(0, 0)
    a.jump("w_join_thread", 0x84)
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("w_wait", 0x84)
    a.jump("w_bad")
    a.label("w_join_thread")
    a.slot()
    a.load(1, 11, 56)
    a.imm(2, 0)
    a.call("wait")
    a.slot()
    a.store(11, 76, 0, False)
    a.cmp_imm(0, 0)
    a.jump("w_final_query", 0x84)
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("w_wait", 0x84)
    a.jump("w_bad")
    a.label("w_final_query")
    a.slot()
    a.set32(11, 24, 1)            # Both original HANDLEs actually signaled.
    # Birth/resume still own their stack slot and post-call checks until return.
    a.state()
    a.load(0, 10, 232, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait", 0x85)
    a.load(0, 10, 236, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait", 0x85)
    _job_query(a, "w_query_fail")
    _times(a, "process_times", 48, 96, "w_query_fail")
    _times(a, "thread_times", 56, 128, "w_query_fail")
    for api, handle, target in (("process_exit", 48, 80), ("thread_exit", 56, 84)):
        a.slot()
        a.load(1, 11, handle)
        a.lea(2, 11, target)
        a.call(api)
        a.rr(0x85, 0, 0, False)
        okay = a.unique("exit_code_okay")
        a.jump(okay, 0x85)
        _capture_error(a, 19 if api == "process_exit" else 20)
        a.jump("w_query_fail")
        a.label(okay)
    _qpc(a, "w_clock_fail", watcher=True)
    a.load(2, 3, 40)
    a.rr(0x39, 0, 2)
    a.jump("w_query_fail", 0x8D)
    a.slot()
    a.set32(11, 88, 1)
    a.set32(11, 92, 1)
    a.set32(11, 24, 3)            # Join plus complete final queries, not admission.
    # Copy fixed six qwords cumulative accounting, with no overlapping CPU sum.
    a.state()
    for off in range(0, 48, 8):
        a.load(0, 10, 128 + off)
        a.store(11, 208 + off, 0)
    a.set32(11, 0, 3)              # JOINED + final queries valid.
    a.set32(10, 16, _NONE)
    a.imm(0, 0)
    a.atomic32(10, 20, 0)
    a.jump("w_loop")
    a.label("w_failed_birth")
    a.fault(5)
    a.slot()
    a.set32(11, 0, 4)
    a.state()
    a.set32(10, 16, _NONE)
    a.imm(0, 0)
    a.atomic32(10, 20, 0)
    a.jump("w_loop")
    a.label("w_query_fail")
    a.fault(6)
    a.slot()
    a.set32(11, 0, 4)
    a.state()
    a.set32(10, 16, _NONE)
    a.imm(0, 0)
    a.atomic32(10, 20, 0)
    a.jump("w_loop")
    a.label("w_idle")
    a.state()
    a.load(0, 10, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("w_wait", 0x84)
    # STOP can race the CLAIMED phase before current_slot has been published.
    for offset in (20, 232, 236):
        a.load(0, 10, offset, False)
        a.rr(0x85, 0, 0, False)
        a.jump("w_wait", 0x85)
    a.jump("w_finish")
    a.label("w_wait")
    a.state()
    a.load(0, 10, 4, False)
    a.rr(0x85, 0, 0, False)
    waiting_cleanup = a.unique("waiting_cleanup")
    waiting_ready = a.unique("waiting_ready")
    a.jump(waiting_cleanup, 0x85)
    _wait_delay(a, 32)
    a.jump(waiting_ready)
    a.label(waiting_cleanup)
    _wait_delay(a, 40)
    a.label(waiting_ready)
    a.load(1, 3, 56)
    a.call("wait")
    a.cmp_imm(0, 0)
    a.jump("w_event_stop", 0x84)
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("w_loop", 0x84)
    a.jump("w_bad")
    a.label("w_event_stop")
    a.state()
    a.imm(0, 1)
    a.atomic32(10, 4, 0)
    # The irreversible STOP latch stays set. Reset ONLY the wake event so
    # cleanup polls do not busy-spin on a permanently signaled manual event.
    a.load(1, 3, 56)
    a.call("reset_event")
    a.rr(0x85, 0, 0, False)
    a.jump("w_loop", 0x85)
    _capture_error(a, 26)
    a.fault(26)
    _kill(a)
    a.jump("w_terminal_fault")
    a.label("w_finish")
    _job_query(a, "w_terminal_fault")
    _qpc(a, "w_clock_fail", watcher=True)
    a.load(2, 3, 40)
    a.rr(0x39, 0, 2)
    a.jump("w_expired", 0x8D)
    a.state()
    a.load(0, 10, 24)
    a.rr(0x85, 0, 0)
    a.jump("w_terminal_fault", 0x85)
    a.set32(10, 12, 2)             # RAW_CLEAN, not admission/COMPLETE.
    a.load(0, 4, 104)
    a.store(10, 72, 0)
    a.imm(0, 0)
    a.jump("watchdog_return")
    a.label("w_bad")
    a.fault(7)
    a.jump("w_loop")
    a.label("w_clock_fail")
    a.fault(1)
    _kill(a)
    a.jump("w_terminal_fault")
    a.label("w_expired")
    a.fault(8)
    _kill(a)
    a.label("w_terminal_fault")
    a.state()
    a.set32(10, 12, 3)             # RESIDUAL; handles/code remain retained.
    a.imm(0, 1)
    a.end(start, "watchdog")

    # BIRTH: claim/check/CreateProcess/write original PI/publish, no FFI gap.
    start = a.begin("birth_next")
    a.state()
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(10, 232, 1)
    a.jump("b_busy", 0x85)
    a.label("b_ready_wait")
    _qpc(a, "b_bad", stop_check=True)
    a.state()
    a.load(0, 10, 120, False)
    a.cmp_imm(0, 1)
    a.jump("b_bad", 0x85)
    a.load(1, 10, 112)
    a.imm(2, 0)
    a.call("wait")
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("b_bad", 0x85)
    a.state()
    a.load(0, 10, 8, False)
    a.cmp_imm(0, 1)
    a.jump("b_ready", 0x84)
    _wait_delay(a, 32)
    a.load(1, 3, 56)
    a.call("wait")
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("b_ready_wait", 0x84)
    a.jump("b_bad")
    a.label("b_ready")
    a.state()
    a.load(0, 10, 236, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_bad", 0x85)
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(10, 20, 1)
    a.jump("b_bad", 0x85)
    a.load(0, 10, 0, False)
    a.load(2, 3, 192, False)
    a.rr(0x39, 0, 2, False)
    a.jump("b_preclaim_fail", 0x83)
    a.cmp_imm(0, _MAX_CHILDREN)
    a.jump("b_preclaim_fail", 0x83)
    a.store(10, 16, 0, False)
    a.add_imm(0, 1)
    a.store(10, 0, 0, False)
    a.add_imm(0, -1)
    a.store(4, 80, 0)
    a.slot_from_index()
    a.slot()
    a.load(0, 11, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_bad", 0x85)
    a.set32(11, 0, 1)
    _job_query(a, "b_claim_fail")
    a.state()
    a.slot()
    for off in range(0, 48, 8):
        a.load(0, 10, 128+off)
        a.store(11, 160+off, 0)
    _qpc(a, "b_claim_fail", stop_check=True)
    a.slot()
    a.store(11, 32, 0)
    a.load(0, 4, 80)
    a.put(b"\x48\xc1\xe0\x06")
    a.load(10, 3, 184)
    a.rr(0x01, 0, 10)
    a.store(4, 96, 0)
    a.load(10, 4, 96)
    a.load(1, 10, 0)
    a.load(2, 10, 8)
    a.imm(8, 0)
    a.imm(9, 0)
    a.imm(0, 0)
    a.store(4, 32, 0)
    a.load(0, 3, 224, False)
    a.store(4, 40, 0)
    for src, dst in ((16, 48), (24, 56), (32, 64)):
        a.load(0, 10, src)
        a.store(4, dst, 0)
    a.slot()
    a.lea(0, 11, 48)
    a.store(4, 72, 0)
    a.call("birth")
    a.slot()
    a.store(11, 4, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_success", 0x85)
    a.call("error")
    a.slot()
    a.store(11, 8, 0, False)
    a.fault(9)
    a.jump("b_publish")
    a.label("b_success")
    a.state()
    a.load(0, 10, 104, False)
    a.add_imm(0, 1)
    a.store(10, 104, 0, False)
    a.label("b_publish")
    a.slot()
    a.imm(0, 2)
    a.atomic32(11, 0, 0)
    a.state()
    a.imm(0, 2)
    a.atomic32(10, 20, 0)
    _qpc(a, "b_late", stop_check=True)
    a.slot()
    a.store(11, 40, 0)
    a.load(0, 11, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_done", 0x85)
    a.jump("b_late")
    a.label("b_late")
    a.fault(10)
    a.slot()
    a.load(0, 11, 4, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_done_fail", 0x84)
    a.set32(11, 256, 1)
    a.load(1, 3, 48)
    a.load(2, 3, 228, False)
    a.call("kill_job")
    a.slot()
    a.store(11, 260, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_done_fail", 0x85)
    a.call("error")
    a.slot()
    a.store(11, 264, 0, False)
    a.set32(11, 268, 1)
    a.load(1, 11, 48)
    a.load(2, 3, 228, False)
    a.call("kill_process")
    a.slot()
    a.store(11, 272, 0, False)
    a.rr(0x85, 0, 0, False)
    a.jump("b_done_fail", 0x85)
    a.call("error")
    a.slot()
    a.store(11, 276, 0, False)
    a.jump("b_done_fail")
    a.label("b_claim_fail")
    a.state()
    a.load(0, 10, 16, False)
    a.cmp_imm(0, _NONE)
    a.jump("b_bad", 0x84)
    a.slot()
    a.set32(11, 0, 2)             # Failed consumed claim, no child PI authority.
    a.jump("b_bad")
    a.label("b_preclaim_fail")
    a.state()
    a.imm(0, 0)
    a.atomic32(10, 20, 0)         # No slot pointer has been initialized or used.
    a.label("b_bad")
    a.fault(11)
    a.label("b_done_fail")
    a.imm(0, 1)
    a.jump("b_clear")
    a.label("b_done")
    a.imm(0, 0)
    a.label("b_clear")
    a.state()
    a.set32(10, 232, 0)
    a.jump("birth_next_return")
    a.label("b_busy")
    a.fault(21)
    a.imm(0, 1)                  # Do not clear another native caller's active bit.
    a.end(start, "birth_next")

    # RESUME original primary thread once, checked in native original-QPC frame.
    start = a.begin("resume_current")
    a.state()
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(10, 236, 1)
    a.jump("r_busy", 0x85)
    a.load(0, 10, 232, False)
    a.rr(0x85, 0, 0, False)
    a.jump("r_bad", 0x85)
    a.load(0, 10, 16, False)
    a.cmp_imm(0, _MAX_CHILDREN)
    a.jump("r_bad", 0x83)
    a.slot_from_index()
    a.slot()
    a.load(0, 11, 0, False)
    a.cmp_imm(0, 2)
    a.jump("r_bad", 0x85)
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(11, 12, 1)
    a.jump("r_bad", 0x85)
    _qpc(a, "r_bad", stop_check=True)
    a.slot()
    a.load(1, 11, 56)
    a.call("resume")
    a.slot()
    a.store(11, 16, 0, False)
    a.cmp_imm(0, 1)
    a.jump("r_done", 0x84)
    a.call("error")
    a.slot()
    a.store(11, 20, 0, False)
    a.label("r_bad")
    a.fault(12)
    a.imm(0, 1)
    a.jump("r_clear")
    a.label("r_done")
    _qpc(a, "r_bad", stop_check=True)
    a.imm(0, 0)
    a.label("r_clear")
    a.state()
    a.set32(10, 236, 0)
    a.jump("resume_current_return")
    a.label("r_busy")
    a.fault(22)
    a.imm(0, 1)
    a.end(start, "resume_current")

    # STOP AND JOIN: original watcher HANDLE, final thread CPU, same cleanup.
    start = a.begin("request_stop")
    a.state()
    a.imm(0, 0)
    a.imm(1, 1)
    a.cas32(10, 844, 1)
    a.jump("s_busy", 0x85)
    a.imm(0, 1)
    a.atomic32(10, 4, 0)
    a.set32(10, 124, 1)
    a.load(1, 3, 56)
    a.call("event")
    a.rr(0x85, 0, 0, False)
    a.jump("s_loop", 0x85)
    a.fault(13)
    a.label("s_loop")
    _qpc(a, "s_bad")
    a.load(2, 3, 40)
    a.rr(0x39, 0, 2)
    a.jump("s_bad", 0x8D)
    a.state()
    a.load(0, 10, 120, False)
    a.cmp_imm(0, 1)
    a.jump("s_bad", 0x85)
    a.load(1, 10, 112)
    _wait_delay(a, 40)
    a.call("wait")
    a.cmp_imm(0, _WAIT_TIMEOUT)
    a.jump("s_loop", 0x84)
    a.cmp_imm(0, 0)
    a.jump("s_bad", 0x85)
    a.state()
    a.set32(10, 848, 1)           # Actual original watcher join survives query fail.
    a.load(1, 10, 112)
    a.lea(2, 10, 800)
    a.call("thread_exit")
    a.rr(0x85, 0, 0, False)
    s_exit_okay = a.unique("stop_exit_okay")
    a.jump(s_exit_okay, 0x85)
    _capture_error(a, 24)
    a.fault(24)
    a.label(s_exit_okay)
    a.state()
    a.load(1, 10, 112)
    a.lea(2, 10, 808)
    a.lea(8, 10, 816)
    a.lea(9, 10, 824)
    a.lea(0, 10, 832)
    a.store(4, 32, 0)
    a.call("thread_times")
    a.rr(0x85, 0, 0, False)
    s_times_okay = a.unique("stop_times_okay")
    s_after_times = a.unique("stop_after_times")
    a.jump(s_times_okay, 0x85)
    _capture_error(a, 25)
    a.fault(25)
    a.jump(s_after_times)
    a.label(s_times_okay)
    a.state()
    a.set32(10, 840, 1)            # Original thread signaled + final CPU queried.
    a.label(s_after_times)
    # A real final original-Job query is attempted even after a CPU/query fault.
    _job_query(a, "s_bad")
    a.state()
    a.load(0, 10, 800, False)
    a.rr(0x85, 0, 0, False)
    a.jump("s_bad", 0x85)
    a.load(0, 10, 12, False)
    a.cmp_imm(0, 2)
    a.jump("s_bad", 0x85)
    a.load(0, 10, 232, False)
    a.rr(0x85, 0, 0, False)
    a.jump("s_bad", 0x85)
    a.load(0, 10, 236, False)
    a.rr(0x85, 0, 0, False)
    a.jump("s_bad", 0x85)
    _qpc(a, "s_bad")
    a.load(2, 3, 40)
    a.rr(0x39, 0, 2)
    a.jump("s_bad", 0x8D)
    a.state()
    a.load(0, 10, 24)
    a.rr(0x85, 0, 0)
    a.jump("s_bad", 0x85)
    a.imm(0, 0)
    a.jump("s_clear")
    a.label("s_bad")
    a.fault(14)
    a.imm(0, 1)
    a.label("s_clear")
    a.state()
    a.set32(10, 852, 1)           # Native body completed, including failure body.
    a.set32(10, 844, 0)
    a.jump("request_stop_return")
    a.label("s_busy")
    a.fault(23)
    a.imm(0, 1)
    a.end(start, "request_stop")
    return a.finish()


_IMAGE, _RANGES, _TABLE_OFFSET, _UNWIND_OFFSET = _build_image()
_DIGEST = _hashlib.sha256(_IMAGE).hexdigest()
_ENTRIES = _Map({name: begin for begin, _, name in _RANGES})


@_dataclass(frozen=True)
class _BirthSpec:
    """Raw fixed build intent; not an authorization or executable identity.

    UTF-16LE buffers include their terminators; environment ends in two WCHAR
    NULs. startup is an original gate output pointer to STARTUPINFOEXW (112B).
    The actual owner must already configure the original Job-list attribute and
    retain/freeze its opaque backing through every native birth and drain.
    """
    application: bytes
    command_line: bytes
    environment: bytes
    directory: bytes
    startup: object
    intent_serial: int


def _utf16(raw, *, environment=False):
    if type(raw) is not bytes or not 2 <= len(raw) <= 65534 or len(raw) % 2:
        raise ValueError("bounded exact UTF16LE byte buffer required")
    if environment:
        if len(raw) < 4 or not raw.endswith(b"\0\0\0\0"):
            raise ValueError("double WCHAR environment terminator required")
        if any(raw[i:i+4] == b"\0\0\0\0" for i in range(0, len(raw)-4, 2)):
            raise ValueError("environment has payload after its terminal WCHAR pair")
    elif not raw.endswith(b"\0\0") or any(raw[i:i+2] == b"\0\0" for i in range(0, len(raw)-2, 2)):
        raise ValueError("one terminal WCHAR NUL required")
    raw.decode("utf-16-le", "strict")
    return raw


class _FixedDeadlineProgram:
    """One real native installation, one fixed serial bank, no lease/reset.

    Construction reserves every output/call/close slot BEFORE gate.prepare_once.
    It performs no WinAPI call. install_once/start_once/birth/resume/stop and
    release perform native calls and need the already verified execution owner.
    Original job/event are original result/output references from THIS gate.
    """
    ENTRY_SIGNATURES = _Map({n: ("u", ("p",)) for n in _ENTRIES})

    def __init__(self, gate, specs, *, epoch_qpc, frequency, stop_qpc, cleanup_qpc,
                 original_job, original_stop_event):
        global _LIVE_PROGRAM
        if type(gate) is not _LoadedWin64Gate or gate._prepare_attempted or _LIVE_PROGRAM is not None:
            raise _ERROR
        if type(specs) not in (tuple, list) or not (1 <= len(specs) <= _MAX_CHILDREN) or any(type(x) is not _BirthSpec for x in specs):
            raise ValueError("one bounded immutable fixed child bank required")
        if any(type(x) is not int for x in (epoch_qpc, frequency, stop_qpc, cleanup_qpc)) or not (
            0 <= epoch_qpc < stop_qpc < cleanup_qpc <= 0x7FFFFFFFFFFFFFFF and
            1 <= frequency <= 0x7FFFFFFFFFFFFFFF):
            raise ValueError("original absolute signed QPC interval/frequency required")
        for ref, name in ((original_job, "CreateJobObjectW"), (original_stop_event, "CreateEventW")):
            if (type(ref) is not _RawReference or type(ref.owner) is not _RawCall or
                ref.owner.gate is not gate or ref.owner.name != name or
                ref is not ref.owner.result_reference):
                raise TypeError("exact original same-gate creator return slot required")
        # Validate BEFORE any length arithmetic, allocation size or call reservation.
        for spec in specs:
            for raw in (spec.application, spec.command_line, spec.directory):
                _utf16(raw)
            _utf16(spec.environment, environment=True)
            ref = spec.startup
            if (type(ref) is not _RawReference or type(ref.owner) is not _Output or
                ref.owner.gate is not gate or ref is not ref.owner.reference or
                ref.owner not in gate._outputs or ref.owner.size < 112):
                raise TypeError("original same-gate STARTUPINFOEX output pointer required")
            if type(spec.intent_serial) is not int or not 1 <= spec.intent_serial <= 0xFFFFFFFFFFFFFFFF:
                raise ValueError("fixed nonzero intent serial required")
        if len({x.intent_serial for x in specs}) != len(specs):
            raise ValueError("duplicate fixed birth intent")
        self.gate, self.specs = gate, tuple(specs)
        self.clock = (epoch_qpc, frequency, stop_qpc, cleanup_qpc)
        self._job, self._event = original_job, original_stop_event
        self._lock = _allocate_lock()
        self.attempted = self.installed = self.started = self.released = False
        self.cleanup_faults = ()
        self._context_snapshot = None
        self.state = gate.output(_STATE_BYTES)
        _U32.from_buffer(self.state.storage, 16).value = _NONE
        self._entry_pointers = {n: _P() for n in _ENTRIES}
        self._context_pointer = _P()
        self._table_pointer = _P()
        self._allocations, self._frees = {}, {}
        # Fixed upper bounds. Only command lines remain writable to WinAPI.
        readonly_size = (sum(len(x.application)+len(x.environment)+len(x.directory)+119
                             for x in self.specs) + 4095) & ~4095
        command_size = (sum(len(x.command_line) for x in self.specs)+4095) & ~4095
        self._sizes = dict(code=_CODE_BYTES, context=_CONTEXT_BYTES,
                           readonly=readonly_size, command=command_size)
        self._old, self._regions = {}, {}
        self._protect, self._query = {}, {}
        for name, size in self._sizes.items():
            alloc = gate.new_call("VirtualAlloc", (_P(), _U64(size), _U32(0x3000), _U32(4)))
            self._allocations[name] = alloc
            self._frees[name] = gate.new_call("VirtualFree", (alloc.result_reference, _U64(), _U32(0x8000)))
            if name != "command":
                self._old[name], self._regions[name] = gate.output(4), gate.output(48)
                self._protect[name] = gate.new_call("VirtualProtect", (
                    alloc.result_reference, _U64(size), _U32(0x20 if name == "code" else 2),
                    self._old[name].reference))
                self._query[name] = gate.new_call("VirtualQuery", (
                    alloc.result_reference, self._regions[name].reference, _U64(48)))
        self.alloc = self._allocations["code"]  # Gate bridge checks exact original alloc.
        self._flush = gate.new_call("FlushInstructionCache", (_P(-1), self.alloc.result_reference, _U64(len(_IMAGE))))
        self._register = gate.new_call("RtlAddFunctionTable", (
            self._table_pointer, _U32(len(_RANGES)), self.alloc.result_reference))
        self._unregister = gate.new_call("RtlDeleteFunctionTable", (self._table_pointer,))
        self._thread = gate.new_deadline_thread(self, self._context_pointer)
        self._thread_close = gate.own_handle(self._thread.result_reference)
        self._job_close, self._event_close = gate.own_handle(original_job), gate.own_handle(original_stop_event)
        self._child_closes = tuple((
            gate.own_handle(self.state.handle_reference(4096+i*512+48)),
            gate.own_handle(self.state.handle_reference(4096+i*512+56))) for i in range(len(self.specs)))
        self._birth_calls = tuple(gate.new_deadline_call(self, "birth_next", self._context_pointer)
                                  for _ in self.specs)
        self._resume_calls = tuple(gate.new_deadline_call(self, "resume_current", self._context_pointer)
                                   for _ in self.specs)
        self._stop_call = gate.new_deadline_call(self, "request_stop", self._context_pointer)
        _LIVE_PROGRAM = self

    def _gate_entry(self, name):
        if type(name) is not str or name not in _ENTRIES:
            raise _ERROR
        return self.alloc.result_reference, _ENTRIES[name], _DIGEST

    def _check_entry(self, name):
        if (name not in _ENTRIES or _LIVE_PROGRAM is not self or not self.installed or
            self.released or not self._register.returned or self._register.result.value != 1):
            raise _ERROR
        address = self.alloc.result.value
        if (not address or _READ(address, len(_IMAGE)) != _IMAGE or
            _READ(self._context_pointer.value, 256+len(self.specs)*64) != self._context_snapshot):
            raise _ERROR
        if self._entry_pointers[name].value != address + _ENTRIES[name]:
            raise _ERROR

    def install_once(self, store):
        if type(store) is not _FixedCallStore or store.gate is not self.gate or not self._lock.acquire(False):
            raise _ERROR
        try:
            if self.attempted or self.released:
                raise _ERROR
            self.attempted = True
            for ref in (self._job, self._event):
                if not (ref.owner.returned or ref.owner.frame.completed == 1) or not _U64.from_address(ref.address).value:
                    raise _ERROR
            for alloc in self._allocations.values():
                alloc.invoke_store_once(store)
                if not alloc.result.value:
                    raise _ERROR
            code = self.alloc.result.value
            context = self._allocations["context"].result.value
            readonly = self._allocations["readonly"].result.value
            command = self._allocations["command"].result.value
            _MOVE(code, _IMAGE, len(_IMAGE))
            self._table_pointer.value = code + _TABLE_OFFSET
            self._context_pointer.value = context
            header = bytearray(256+len(self.specs)*64)
            _struct.pack_into("<QIIqqqq", header, 0, _MAGIC, 1, 256, *self.clock)
            _MOVE(context+48, self._job.address, 8)
            _MOVE(context+56, self._event.address, 8)
            _struct.pack_into("<Q", header, 64, _c.addressof(self.state.storage))
            for key, offset in _F.items():
                _struct.pack_into("<Q", header, offset, self.gate._exports[_EXPORTS[key]].address)
            _struct.pack_into("<Q", header, 184, context+256)
            _struct.pack_into("<I", header, 192, len(self.specs))
            _struct.pack_into("<IIQ", header, 224, 0x00080404, 0xE0000001,
                              self.clock[1]//1000 + (self.clock[1] % 1000 != 0))
            ro_cursor, command_cursor = readonly, command
            for i, spec in enumerate(self.specs):
                addresses = []
                for raw in (spec.application, spec.environment, spec.directory):
                    _MOVE(ro_cursor, raw, len(raw))
                    addresses.append(ro_cursor)
                    ro_cursor += len(raw)
                _MOVE(command_cursor, spec.command_line, len(spec.command_line))
                startup = _U64.from_address(spec.startup.address).value
                if not startup or _U32.from_address(startup).value != 112:
                    raise _ERROR
                ro_cursor = (ro_cursor+7) & ~7
                _MOVE(ro_cursor, startup, 112)
                _struct.pack_into("<QQQQQQIIQ", header, 256+i*64,
                    addresses[0], command_cursor, addresses[1], addresses[2],
                    ro_cursor, spec.intent_serial, 0x00080404, 0, 0)
                command_cursor += len(spec.command_line)
                ro_cursor += 112
            # Preserve original HANDLE bytes, then freeze full context including bank.
            header[48:64] = _READ(context+48, 16)
            _MOVE(context, bytes(header), len(header))
            self._context_snapshot = bytes(header)
            for name, protect in self._protect.items():
                protect.invoke_store_once(store)
                if not protect.result.value or _U32.from_buffer(self._old[name].storage).value != 4:
                    raise _ERROR
            self._flush.invoke_store_once(store)
            if not self._flush.result.value:
                raise _ERROR
            for name, query in self._query.items():
                query.invoke_store_once(store)
                info = _MemoryInfo.from_buffer(self._regions[name].storage)
                base = self._allocations[name].result.value
                if (query.result.value != 48 or info.base != base or info.allocation_base != base or
                    info.region_size != self._sizes[name] or info.state != 0x1000 or
                    info.protect != (0x20 if name == "code" else 2) or info.type != 0x20000):
                    raise _ERROR
            self._register.invoke_store_once(store)
            if self._register.result.value != 1:
                raise _ERROR
            for name, offset in _ENTRIES.items():
                self._entry_pointers[name].value = code + offset
            self.installed = True
        finally:
            self._lock.release()

    def start_once(self, store):
        if not self._lock.acquire(False):
            raise _ERROR
        try:
            self._check_entry("watchdog")
            if self.started:
                raise _ERROR
            self.started = True
            try:
                self._thread.invoke_store_once(store)
            finally:
                # The native store completed BEFORE any outer FFI conversion.
                # Preserve its original HANDLE even when that conversion throws.
                if self._thread.frame.completed == 1:
                    _MOVE(_c.addressof(self.state.storage)+112, self._thread.result_reference.address, 8)
                    if self._thread.result.value:
                        _U32.from_buffer(self.state.storage, 120).value = 1
            if _U32.from_buffer(self.state.storage, 120).value != 1:
                raise _ERROR
        finally:
            self._lock.release()

    def birth_next_once(self, index, store):
        if not self._lock.acquire(False):
            raise _ERROR
        try:
            if (type(index) is not int or not 0 <= index < len(self.specs) or not self.started or
                index != _U32.from_buffer(self.state.storage, 0).value):
                raise _ERROR
            self._birth_calls[index].invoke_store_once(store)
            return self._birth_calls[index]
        finally:
            self._lock.release()

    def resume_current_once(self, index, store):
        if not self._lock.acquire(False):
            raise _ERROR
        try:
            if (type(index) is not int or not 0 <= index < len(self.specs) or not self.started or
                index != _U32.from_buffer(self.state.storage, 16).value):
                raise _ERROR
            self._resume_calls[index].invoke_store_once(store)
            return self._resume_calls[index]
        finally:
            self._lock.release()

    def stop_and_join_once(self, store):
        if not self._lock.acquire(False):
            raise _ERROR
        try:
            if not self.started:
                raise _ERROR
            # Native body captures its own errors. Use the original cleanup FFI
            # directly, so public caller-wrapper drift cannot disable STOP/join.
            self._stop_call.invoke_cleanup_once()
            return self._stop_call
        finally:
            self._lock.release()

    def release_once(self):
        if not self._lock.acquire(False):
            raise _ERROR
        try:
            if self.released:
                raise _ERROR
            # Native original-thread join/final CPU and all native call returns.
            state = self.state.storage
            if self.started and (not self._stop_call.attempted or
                _U32.from_buffer(state, 852).value != 1 or
                _U32.from_buffer(state, 848).value != 1 or
                _U32.from_buffer(state, 232).value or _U32.from_buffer(state, 236).value or
                _U32.from_buffer(state, 844).value):
                raise _ERROR
            # Never close the Job or free a late-birth publication destination
            # using a stale pre-birth accounting sample.
            if self.started and (_U32.from_buffer(state, 176).value == 0 or
                _U32.from_buffer(state, 180).value != 0 or
                _U32.from_buffer(state, 164).value != _U32.from_buffer(state, 104).value):
                raise _ERROR
            closings = []
            if self.started:
                for i, pair in enumerate(self._child_closes):
                    phase = _U32.from_buffer(state, 4096+i*512).value
                    made = _U32.from_buffer(state, 4096+i*512+4).value
                    if made:
                        joined = _U32.from_buffer(state, 4096+i*512+24).value & 1
                        if phase not in (2, 3, 4) or not joined:
                            raise _ERROR
                        closings.extend(pair)
                closings.append(self._thread_close)
            closings.extend((self._event_close, self._job_close))
            # All safety checks precede consumption. Every remaining known safe
            # original close is attempted once despite another close's failure.
            self.released = True
            faults = []
            for index, close in enumerate(closings):
                try:
                    close.close_once()
                    # The gate preserves raw BOOL but does not interpret it.
                    # A consumed close is not proof that the object closed.
                    call = close.call
                    if (not close.consumed or not call.attempted or
                        not (call.returned or call.frame.completed == 1) or
                        call.result.value == 0):
                        raise RuntimeError("original CloseHandle FALSE or completion UNKNOWN")
                except BaseException as exc:
                    faults.append(("close", index, exc))
            self.cleanup_faults = tuple(faults)
            if self._register.attempted:
                if not (self._register.returned and self._register.result.value == 0):
                    try:
                        self._unregister.invoke_cleanup_once()
                        if self._unregister.result.value != 1:
                            raise _ERROR
                    except BaseException as exc:
                        faults.append(("unwind-delete", 0, exc))
                        self.cleanup_faults = tuple(faults)
                        # Unknown registration cannot permit any code release.
                        raise _ERROR from exc
            for name in ("command", "readonly", "context", "code"):
                if self._allocations[name].attempted and self._allocations[name].result.value:
                    try:
                        self._frees[name].invoke_cleanup_once()
                        if self._frees[name].result.value != 1:
                            raise _ERROR
                    except BaseException as exc:
                        faults.append(("free", name, exc))
            self.cleanup_faults = tuple(faults)
            if faults:
                raise _ERROR from faults[0][2]
        finally:
            self._lock.release()
