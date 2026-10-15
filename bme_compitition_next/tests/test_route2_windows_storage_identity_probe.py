"""Synthetic producer/failure tests; these do not establish native ABI/runtime.

No DLL loading, provider calls, host disk queries or disk mutations occur in
these tests.  A separate supervised native integration invocation is required.
"""

import ctypes as c
import struct
import unittest
from unittest.mock import patch

from eating_event.route2_candidate_overlap import windows_storage_identity_probe as p
from eating_event.route2_candidate_overlap.windows_compile_free_gate import _Output, _RawReference


def geometry(size=1 << 30, sector=512):
    return struct.pack("<qIIIIq", 1024, 12, 255, 63, sector, size)


def alignment(logical=512, physical=4096):
    return struct.pack("<7I", 28, 28, 0, 0, logical, physical, 0)


def layout(start=1 << 20, length=1 << 20, second=False):
    count = 2 if second else 1
    prefix = bytearray(48)
    struct.pack_into("<II", prefix, 0, 1, count)
    prefix[8:24] = bytes(range(16))
    struct.pack_into("<qqI", prefix, 24, 1 << 20, (1 << 30) - (2 << 20), 128)
    row = bytearray(144)
    struct.pack_into("<I", row, 0, 1)
    struct.pack_into("<qqI", row, 8, start, length, 1)
    row[32:48], row[48:64] = bytes(range(16)), bytes(range(16, 32))
    return bytes(prefix + row + (row if second else b""))


class _FakeCall:
    def __init__(self, gate, name, arguments):
        self.gate, self.name, self.arguments = gate, name, arguments
        self.result = c.c_uint64()
        self.result_reference = _RawReference(self, c.addressof(self.result))
        self.attempted = self.faulted = self.returned = False

    def invoke_once(self):
        if self.attempted:
            raise AssertionError("test detected native call reuse")
        self.attempted = True
        try:
            self.gate.invoke(self)
            self.returned = True
        except BaseException:
            self.faulted = True
            raise


class _FakeClose:
    def __init__(self, gate, source):
        self.gate, self.source = gate, source
        self.call = gate.new_call("CloseHandle", (source,))
        self.consumed = False

    def close_once(self):
        if self.consumed:
            raise AssertionError("close retried")
        self.consumed = True
        self.call.invoke_once()


class _FailCleanupInspection:
    """First observation works; cleanup integer conversion fails after store."""
    def __init__(self, original):
        self.original, self.reads = original, 0

    @property
    def value(self):
        self.reads += 1
        if self.reads > 1:
            raise MemoryError("synthetic cleanup HANDLE integer conversion")
        return self.original.value

    @value.setter
    def value(self, value):
        self.original.value = value


class _FakeGate:
    """Native-memory simulator, deliberately not a runtime evidence producer."""

    def __init__(self):
        self._prepare_attempted = self._prepared = False
        self.calls, self.outputs, self.closes, self.events = [], [], [], []
        self.counter = 100
        self.fail_ioctl = self.raise_after_open = self.fail_close = False
        self.after_geometry_drift = False
        self.bad_device_number = self.bad_returned_bytes = False
        self.max_partition_drift = False
        self.layout_calls = 0
        self.invalid_disk_handle = None
        self.final_extent_clock = None
        self.final_extent_cross_stop = False
        self.extent_calls = 0
        self.end_call = None
        self.geometry_calls = 0

    def output(self, size):
        out = _Output(self, size)
        self.outputs.append(out)
        return out

    def new_call(self, name, arguments):
        call = _FakeCall(self, name, arguments)
        self.calls.append(call)
        return call

    def own_handle(self, source):
        close = _FakeClose(self, source)
        self.closes.append(close)
        return close

    def prepare_once(self):
        self._prepare_attempted = self._prepared = True

    @staticmethod
    def value(argument):
        if type(argument) is _RawReference:
            return c.c_uint64.from_address(argument.address).value
        return argument.value

    def invoke(self, call):
        a, name = call.arguments, call.name
        self.events.append(name)
        call.result.value = 1
        if name in ("QueryPerformanceCounter", "QueryPerformanceFrequency"):
            if call is self.end_call:
                call.result.value = 0
                return
            value = 10 if name.endswith("Frequency") else self.counter
            if name.endswith("Counter"):
                if call is self.final_extent_clock:
                    value = self.counter = 999
                self.counter += 1
            c.memmove(a[0].value, struct.pack("<q", value), 8)
        elif name == "CreateFileW":
            path = c.string_at(a[0].value, 64).decode("utf-16-le").split("\0", 1)[0]
            self.events.append(path)
            call.result.value = 0x100 if path == "\\\\.\\E:" else 0x200
            if path != "\\\\.\\E:" and self.invalid_disk_handle is not None:
                call.result.value = self.invalid_disk_handle
            if self.raise_after_open and path != "\\\\.\\E:":
                raise RuntimeError("synthetic return conversion fault after raw HANDLE store")
        elif name == "GetVolumeNameForVolumeMountPointW":
            raw = "\\\\?\\Volume{00000000-0000-0000-0000-000000000001}\\\0".encode("utf-16-le")
            c.memmove(a[1].value, raw, len(raw))
        elif name == "GetVolumeInformationByHandleW":
            for index, text in ((1, "label\0"), (6, "NTFS\0")):
                raw = text.encode("utf-16-le")
                c.memmove(a[index].value, raw, len(raw))
            for index, value in ((3, 123), (4, 255), (5, 3)):
                c.memmove(a[index].value, struct.pack("<I", value), 4)
        elif name == "DeviceIoControl":
            code = a[1].value
            if self.fail_ioctl:
                call.result.value = 0
                return
            if code == p._IOCTL_EXTENTS:
                raw = struct.pack("<I4xI4xqq", 1, 3, 1 << 20, 1 << 20)
                self.extent_calls += 1
                if self.final_extent_cross_stop and self.extent_calls == 2:
                    self.counter = 1005  # Synchronous final query returned after original STOP.
            elif code == p._IOCTL_GEOMETRY:
                self.geometry_calls += 1
                raw = geometry(size=(2 << 30) if self.after_geometry_drift and self.geometry_calls > 1 else 1 << 30)
            elif code == p._IOCTL_PROPERTY:
                raw = alignment()
            elif code == p._IOCTL_DEVICE_NUMBER:
                raw = struct.pack("<III", 7, 4 if self.bad_device_number else 3, 0)
            else:
                raw = layout()
                self.layout_calls += 1
                if self.max_partition_drift and self.layout_calls > 1:
                    raw = bytearray(raw)
                    struct.pack_into("<I", raw, 40, 129)
                    raw = bytes(raw)
            c.memmove(a[4].value, raw, len(raw))
            returned = a[5].value + 1 if self.bad_returned_bytes else len(raw)
            c.memmove(a[6].value, struct.pack("<I", returned), 4)
        elif name == "CloseHandle":
            handle = self.value(a[0])
            self.events.append(("close_original", handle))
            if self.fail_close:
                call.result.value = 0
        else:
            raise AssertionError("unexpected native function in producer")


class StorageProducerTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(p, "_LoadedWin64Gate", _FakeGate)
        self.patch.start()
        self.anchor = patch.object(p, "_LIVE_PROBE", None)
        self.anchor.start()

    def tearDown(self):
        self.anchor.stop()
        self.patch.stop()

    def make(self, **changes):
        gate = _FakeGate()
        for key, value in changes.items():
            setattr(gate, key, value)
        probe = p._ReadonlyEStorageProbe(gate, original_epoch_qpc=90, qpc_frequency=10,
                                         stop_qpc=1000, cleanup_qpc=1100)
        gate.prepare_once()
        return probe, gate

    def test_complete_real_producer_path_uses_actual_extent_disk_number(self):
        probe, gate = self.make()
        report = probe.collect_once()
        self.assertEqual(report["state"], "ENDPOINT_SNAPSHOT_COMPLETE")
        self.assertIn("\\\\.\\PhysicalDrive3", gate.events)
        self.assertEqual(report["disks_before"][0]["disk_number"], 3)
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                         [("close_original", 0x200), ("close_original", 0x100)])
        self.assertEqual(len(gate.calls), 180)
        self.assertEqual(len(gate.outputs), 18)
        self.assertEqual(sum(x.size for x in gate.outputs), 569344)
        self.assertIsNone(report["admission_authority"])
        self.assertEqual(report["volume_before"]["mount_guid_path_origin"],
                         "E_PATH_QUERY_NOT_BOUND_TO_HELD_VOLUME_HANDLE")
        with self.assertRaises(PermissionError):
            probe.collect_once()

    def test_query_failure_never_parses_zero_buffer_as_geometry(self):
        probe, gate = self.make(fail_ioctl=True)
        report = probe.collect_once()
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")
        self.assertEqual(report["disks_before"], ())
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)], [("close_original", 0x100)])

    def test_conversion_exception_keeps_original_disk_handle_for_close(self):
        probe, gate = self.make(raise_after_open=True)
        report = probe.collect_once()
        self.assertEqual(report["primary_fault"][1], "RuntimeError")
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                         [("close_original", 0x200), ("close_original", 0x100)])

    def test_primary_and_both_close_faults_are_separate(self):
        probe, gate = self.make(raise_after_open=True, fail_close=True)
        report = probe.collect_once()
        self.assertEqual(report["primary_fault"][1], "RuntimeError")
        self.assertEqual(len(report["close_faults"]), 2)
        self.assertTrue(all(x.consumed for x in gate.closes[:2]))

    def test_geometry_endpoint_change_stops_complete_claim(self):
        probe, _ = self.make(after_geometry_drift=True)
        self.assertEqual(probe.collect_once()["state"], "INCOMPLETE_UNKNOWN")

    def test_final_query_crossing_stop_cannot_use_cleanup_allowance_as_work_time(self):
        probe, gate = self.make(final_extent_cross_stop=True)
        gate.final_extent_clock = probe.queries["extents_after"].clock
        report = probe.collect_once()
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")
        self.assertEqual(report["primary_fault"][:2], ("snapshot_stop_qpc", "TimeoutError"))
        self.assertIn(999, report["observed_qpc"])
        self.assertIn(1005, report["observed_qpc"])
        self.assertLess(report["observed_qpc"][-1], 1100)
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                         [("close_original", 0x200), ("close_original", 0x100)])

    def test_only_gpt_max_partition_count_drift_prevents_complete(self):
        probe, _ = self.make(max_partition_drift=True)
        report = probe.collect_once()
        self.assertEqual(report["disks_before"][0]["layout"]["gpt_max_partition_count"], 128)
        self.assertEqual(report["disks_after"][0]["layout"]["gpt_max_partition_count"], 129)
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")

    def test_cleanup_integer_conversion_failure_still_closes_both_original_slots(self):
        probe, gate = self.make()
        for call in (probe.volume, probe.disk_slots[0]["birth"].call):
            call.result = _FailCleanupInspection(call.result)
        report = probe.collect_once()
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                         [("close_original", 0x200), ("close_original", 0x100)])
        self.assertEqual([x[0] for x in report["close_faults"]],
                         ["disk_raw_close_inspection", "volume_raw_close_inspection"])

    def test_cleanup_conversion_failure_never_closes_invalid_original_slot(self):
        for invalid in (0, (1 << 64) - 1):
            with self.subTest(invalid=invalid), patch.object(p, "_LIVE_PROBE", None):
                probe, gate = self.make(invalid_disk_handle=invalid)
                call = probe.disk_slots[0]["birth"].call
                call.result = _FailCleanupInspection(call.result)
                report = probe.collect_once()
                self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                                 [("close_original", 0x100)])
                self.assertIn("raw_close_fallback_no_known_handle",
                              [x[0] for x in report["close_faults"]])

    def test_original_disk_handle_must_report_matching_native_device_number(self):
        probe, gate = self.make(bad_device_number=True)
        report = probe.collect_once()
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")
        self.assertEqual(report["primary_fault"][0], "disk_device_number_before")
        self.assertEqual([x for x in gate.events if isinstance(x, tuple)],
                         [("close_original", 0x200), ("close_original", 0x100)])

    def test_bytes_returned_larger_than_original_buffer_stops_parser(self):
        probe, _ = self.make(bad_returned_bytes=True)
        report = probe.collect_once()
        self.assertEqual(report["state"], "INCOMPLETE_UNKNOWN")
        self.assertEqual(report["primary_fault"][0], "extents_before")

    def test_primary_close_and_final_clock_faults_remain_separate(self):
        probe, gate = self.make(raise_after_open=True, fail_close=True)
        gate.end_call = probe.end_clock
        report = probe.collect_once()
        self.assertEqual(report["primary_fault"][1], "RuntimeError")
        self.assertEqual(len(report["close_faults"]), 2)
        self.assertEqual(len(report["endpoint_faults"]), 1)

    def test_expired_original_stop_prevents_first_volume_open(self):
        probe, gate = self.make(counter=1000)
        report = probe.collect_once()
        self.assertEqual(report["primary_fault"][1], "TimeoutError")
        self.assertNotIn("CreateFileW", gate.events)

    def test_parser_rejects_truncation_sector_defaults_and_overlap(self):
        with self.assertRaises(ValueError):
            p._geometry(geometry()[:31])
        with self.assertRaises(ValueError):
            p._geometry(geometry(sector=0))
        with self.assertRaises(ValueError):
            p._alignment(alignment(logical=0), p._geometry(geometry()))
        with self.assertRaises(ValueError):
            p._layout(layout(second=True), p._geometry(geometry()))

    def test_gpt_gaps_are_only_inside_reported_usable_region(self):
        result = p._layout(layout(), p._geometry(geometry()))
        self.assertEqual(result["unallocated_partition_gaps"], ((2 << 20, (1 << 30) - (3 << 20)),))

    def test_pointer_sized_extent_overflow_is_rejected(self):
        raw = struct.pack("<I4xI4xqq", 1, 3, (1 << 63) - 2, 8)
        with self.assertRaises(ValueError):
            p._extents(raw)


if __name__ == "__main__":
    unittest.main()
