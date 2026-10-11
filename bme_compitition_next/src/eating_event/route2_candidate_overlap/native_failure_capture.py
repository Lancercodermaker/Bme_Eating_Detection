"""Preallocated, process-local errors for once-only native cleanup.

Allocate this buffer BEFORE acquiring descriptors. Recording uses existing
slots; neither list growth nor error formatting may stop remaining closes.
This is not durable storage, a clean teardown receipt or an approval object.
It cannot make process death/OOM-kill safe; the external quarantine boundary
and its budget remain separate requirements.
"""

from __future__ import annotations


class _ErrorSlot:
    __slots__ = ("operation", "error", "descriptor")

    def __init__(self):
        self.operation = self.error = self.descriptor = None


class NativeFailureCapture:
    __slots__ = ("_slots", "_cursor", "first_error", "aggregation_error", "overflowed", "failure", "_overflow")

    def __init__(self, capacity):
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("native failure buffer requires a bounded exact capacity")
        self._slots = [_ErrorSlot() for _ in range(capacity)]
        self._cursor = iter(self._slots)
        self.first_error = self.aggregation_error = None
        self.overflowed = False
        self._overflow = PermissionError("preallocated native failure buffer exhausted; history incomplete")
        self.failure = PermissionError("native operation failed; original and cleanup errors retained")
        # Allocate all exception dictionary entries before native resources.
        self.failure.primary_error = None
        self.failure.secondary_errors = self._slots
        self.failure.failure_capture = self
        self.failure.aggregation_error = None
        self.failure.history_complete = False

    def record(self, operation, error, descriptor=None):
        # A previously raised wrapper already contains this same buffer. Do
        # not introduce a recursive exception/cause record for the wrapper.
        if error is self.failure:
            return
        if self.first_error is None:
            self.first_error = error
        try:
            slot = next(self._cursor)
            slot.operation = operation
            slot.error = error
            slot.descriptor = descriptor
        except StopIteration:
            self.overflowed = True
            self.aggregation_error = self._overflow
        except BaseException as exc:
            # Keep formatting/recording failure visible; cleanup callers do
            # not depend on record succeeding. No allocation or retry here.
            self.aggregation_error = exc
            slot = next(self._cursor, None)
            if slot is None:
                self.overflowed = True
            else:
                slot.operation = "record_aggregation_failure"
                slot.error = exc
                slot.descriptor = descriptor

    def raise_failure(self, primary):
        if primary is self.failure:
            primary = self.failure.primary_error
        if primary is None:
            primary = self.first_error
        # A wrapper can still be held by an outer failure handler while
        # cleanup raises through this buffer again. Never rewrite its origin.
        if self.failure.primary_error is None:
            self.failure.primary_error = primary
        primary = self.failure.primary_error
        self.failure.aggregation_error = self.aggregation_error
        # Only after the caller has attempted every owned close, make a
        # convenient report. Allocation failure leaves all reserved slots.
        try:
            self.failure.secondary_errors = tuple(
                (slot.operation, slot.error, slot.descriptor)
                for slot in self._slots if slot.error is not None and slot.error is not primary)
        except BaseException as exc:
            self.aggregation_error = self.failure.aggregation_error = exc
            # Every failed report is an error fact, not just the latest
            # aggregation-error index. Repeated cleanup cannot erase it.
            slot = next(self._cursor, None)
            if slot is None:
                self.overflowed = True
            else:
                slot.operation = "report_format_failure"
                slot.error = exc
                slot.descriptor = None
            self.failure.secondary_errors = self._slots
        raise self.failure from primary
