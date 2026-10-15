"""Offline encoder/input test SOURCE; not run in the SOURCE implementation.

Passing these checks cannot prove Windows execution, deadline, cleanup, budget
or admission. Real no-GT production-path tests remain separately required.
"""

import struct
import unittest
from types import SimpleNamespace
from _thread import allocate_lock

from eating_event.route2_candidate_overlap import windows_compile_free_deadline as d


class FixedEncoding(unittest.TestCase):
    def test_rsp_sib_extended_argument_register(self):
        a = d._X64()
        a.load(9, 4, 32)
        self.assertEqual(bytes(a.code), bytes.fromhex("4c8b8c2420000000"))

    def test_cas_has_lock_and_dword_width(self):
        a = d._X64()
        a.cas32(10, 232, 1)
        self.assertEqual(bytes(a.code), bytes.fromhex("f0410fb18ae8000000"))

    def test_extended_base_bts_is_qword(self):
        a = d._X64()
        a.mem(b"\x0f\xba", 5, 10, 24, prefix=b"\xf0")
        a.put(b"\x07")
        self.assertEqual(bytes(a.code), bytes.fromhex("f0490fbaaa1800000007"))

    def test_birth_call_memory_indirection(self):
        a = d._X64()
        a.call("birth")
        self.assertEqual(bytes(a.code), bytes.fromhex("48ff9370000000"))

    def test_image_ranges_and_windows_unwind(self):
        self.assertLessEqual(len(d._IMAGE), 8192)
        self.assertEqual(len(d._RANGES), 4)
        self.assertEqual(set(d._ENTRIES), {
            "watchdog", "birth_next", "resume_current", "request_stop"})
        self.assertEqual(d._IMAGE[d._UNWIND_OFFSET:d._UNWIND_OFFSET+12],
                         bytes.fromhex("010c03000c01100005300000"))
        previous = 0
        for i, (begin, end, name) in enumerate(d._RANGES):
            self.assertGreaterEqual(begin, previous)
            self.assertEqual(begin % 16, 0)
            self.assertLess(begin, end)
            self.assertLessEqual(end, d._UNWIND_OFFSET)
            self.assertEqual(d._IMAGE[begin:begin+12],
                             bytes.fromhex("f30f1efa534881ec80000000"))
            self.assertEqual(d._IMAGE[end-9:end],
                             bytes.fromhex("4881c4800000005bc3"))
            self.assertEqual(struct.unpack_from("<III", d._IMAGE,
                             d._TABLE_OFFSET+12*i), (begin, end, d._UNWIND_OFFSET))
            self.assertEqual(d._ENTRIES[name], begin)
            previous = end

    def test_unknown_branch_is_rejected(self):
        a = d._X64()
        begin = a.begin("one")
        a.jump("absent")
        a.end(begin, "one")
        with self.assertRaises(ValueError):
            a.finish()

    def test_branch_cannot_leave_original_unwind_frame(self):
        a = d._X64()
        first = a.begin("one")
        a.jump("two")
        a.end(first, "one")
        second = a.begin("two")
        a.end(second, "two")
        with self.assertRaises(ValueError):
            a.finish()


class InputBounds(unittest.TestCase):
    def test_utf16_terminator_and_surrogate(self):
        good = "E:\\tool.exe\0".encode("utf-16-le")
        self.assertEqual(d._utf16(good), good)
        for bad in (b"x", b"x\0", b"x\0\0\0z\0\0\0", b"\x00\xd8\0\0"):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, UnicodeError)):
                    d._utf16(bad)

    def test_environment_does_not_hide_trailing_payload(self):
        good = "A=B\0C=D\0\0".encode("utf-16-le")
        self.assertEqual(d._utf16(good, environment=True), good)
        self.assertEqual(d._utf16(b"\0\0\0\0", environment=True), b"\0\0\0\0")
        for bad in ("A=B\0".encode("utf-16-le"),
                    "A=B\0\0HIDDEN=1\0\0".encode("utf-16-le")):
            with self.assertRaises(ValueError):
                d._utf16(bad, environment=True)

    def test_limit_counts_terminator_and_rejects_writable_alias(self):
        boundary = b"A\0"*32766+b"\0\0"
        self.assertEqual(len(d._utf16(boundary)), 65534)
        with self.assertRaises(ValueError):
            d._utf16(b"A\0"*32767+b"\0\0")
        with self.assertRaises(ValueError):
            d._utf16(bytearray(boundary))


class RawCloseFailure(unittest.TestCase):
    def test_false_bool_does_not_skip_later_closes_or_reuse_originals(self):
        # Native-free fixture of the ACTUAL release_once implementation. The
        # first original close returns FALSE normally; no exception is injected.
        class Close:
            def __init__(self, result):
                self.source = object()
                self.consumed = False
                self.invocations = 0
                self.call = SimpleNamespace(attempted=False, returned=False,
                    frame=SimpleNamespace(completed=0),
                    result=SimpleNamespace(value=result))

            def close_once(self):
                if self.consumed:
                    raise AssertionError("original close was retried")
                self.consumed = True
                self.invocations += 1
                self.call.attempted = self.call.returned = True

        program = d._FixedDeadlineProgram.__new__(d._FixedDeadlineProgram)
        program._lock = allocate_lock()
        program.released = program.started = False
        program.state = SimpleNamespace(storage=(d._U64 * 1)())
        first, later = Close(0), Close(1)
        identities = first.source, later.source
        program._event_close, program._job_close = first, later
        program.cleanup_faults = ()
        program._register = SimpleNamespace(attempted=False)
        program._allocations = {name: SimpleNamespace(attempted=False)
            for name in ("command", "readonly", "context", "code")}
        program._frees = {}
        with self.assertRaises(RuntimeError):
            program.release_once()
        self.assertEqual((first.invocations, later.invocations), (1, 1))
        self.assertTrue(first.consumed and later.consumed)
        self.assertEqual(len(program.cleanup_faults), 1)
        self.assertEqual(program.cleanup_faults[0][:2], ("close", 0))
        self.assertIs(first.source, identities[0])
        self.assertIs(later.source, identities[1])
        with self.assertRaises(RuntimeError):
            program.release_once()
        self.assertEqual((first.invocations, later.invocations), (1, 1))


if __name__ == "__main__":
    unittest.main()
