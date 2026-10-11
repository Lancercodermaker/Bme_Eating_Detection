"""Private fixed input copies owned by the original native GT broker.

This is source integration, used only by the fixed original phase executor. The unchanged
original helper installation gate must have succeeded before a cached API can
be used. Existing immutable root/placeholder observations do not establish the
missing original phase-tree creation/deletion history or installation authority.
Production data/installation gates still refuse, and it admits no experiment.
"""
from __future__ import annotations

import ctypes
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import PurePosixPath
import stat
import threading
import time
import weakref

from . import linux_gt_history as gt
from . import linux_quiescence as q
from .budget import AppendOnlyLedger, BudgetGuard, _canonical
from .contracts import (
    CONTROL_FINAL_MATCH_FIELDS, OUTER_CONTROL_FINAL_MATCHES_PHASE,
    RegisteredFile, StudyStage, projection_scope_sha256, require_frozen_admission,
)
from .gt_provider import TruthReadScope
from .native_failure_capture import NativeFailureCapture
from .path_map import ExactPathMap
from .startup_ownership import StartupBinding, require_startup_binding

_ROOT = "/run/route2-phase-source"
_INPUTS = _ROOT + "/inputs"
_TARGETS = (_INPUTS + "/gt-view.jsonl", _INPUTS + "/control-final-matches.jsonl")
_TARGET_BYTES = (b"/run/route2-phase-source/inputs/gt-view.jsonl",
                 b"/run/route2-phase-source/inputs/control-final-matches.jsonl")
_NATIVE_FAILURE_LABELS = ("phase_native_open_tree", "phase_native_mount_setattr", "phase_native_move_mount")
_PUBLISHERS = weakref.WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class _Tree:
    root_frame: tuple[int, ...]
    inputs_frame: tuple[int, ...]
    mount_id: int
    filesystem_root: str
    targets: tuple[tuple[str, tuple[int, ...]], ...]


@dataclass(frozen=True, slots=True)
class _Source:
    path: str
    mapping: object
    identity: gt._GTIdentity
    frame: tuple[int, ...]
    mount_id: int
    registered: RegisteredFile | None = None


@dataclass(slots=True)
class _Copy:
    target: str
    target_bytes: bytes = field(init=False)
    source: _Source | None = None
    tree_fd: int | None = None
    tree_mount_id: int | None = None
    installed_mount_id: int | None = None
    open_attempted: bool = False
    setattr_attempted: bool = False
    move_attempted: bool = False
    move_succeeded: bool = False
    close_attempted: bool = False
    remove_attempted: bool = False
    removed: bool = False
    absence_verified: bool = False
    native_errors: tuple[OSError, ...] = field(default_factory=lambda: tuple(
        OSError("fixed native phase publication syscall failed") for _ in range(4)))
    close_details: dict = field(init=False)
    remove_details: dict = field(init=False)

    def __post_init__(self):
        # Fixed native arguments exist before any publisher acquisition; no
        # encoding/allocation follows consumption of a removal attempt.
        if self.target == _TARGETS[0]:
            self.target_bytes = _TARGET_BYTES[0]
        elif self.target == _TARGETS[1]:
            self.target_bytes = _TARGET_BYTES[1]
        else:
            gt._deny("phase publication accepts only its two fixed native targets")
        self.close_details = {"fd": None, "mount_id": None, "target": self.target}
        self.remove_details = {"target": self.target, "mount_id": None,
            "flags": gt._UMOUNT_NOFOLLOW, "result": None, "errno": None}


@dataclass(slots=True)
class _Batch:
    grant: gt._Grant
    scope_bytes: bytes
    release: str
    stop_ns: int
    cleanup_ns: int
    copies: tuple[_Copy, ...]
    read: q._ReadScope = field(default_factory=q._ReadScope)
    cleanup_read: q._ReadScope = field(default_factory=q._ReadScope)
    errors: NativeFailureCapture = field(default_factory=lambda: NativeFailureCapture(1024))
    captures: tuple[NativeFailureCapture, ...] = ()
    # Original reports only; allocated before any batch descriptor acquisition.
    origins: tuple[NativeFailureCapture, ...] = ()
    published: bool = False
    closed: bool = False
    # Strong original issuances survive registry retirement and caller handle
    # loss. These are assigned only by the private original launch owner.
    launch: object | None = None
    outcome: object | None = None
    outcome_consumed: bool = False
    clock: tuple = ()
    commitment_key: gt._CommitmentKey | None = None
    failed: bool = False


@dataclass(slots=True)
class _Publisher:
    guard: object
    owner: gt._Owner
    handle: object
    binding: StartupBinding
    pid: int
    thread: object
    read: q._ReadScope
    tree: _Tree | None = None
    batches: tuple[_Batch, ...] = ()
    active: _Batch | None = None
    installed: bool = False
    failed: bool = False
    captures: tuple[NativeFailureCapture, ...] = ()
    origins: tuple[NativeFailureCapture, ...] = ()


def _capture(publisher, batch, operation, error, descriptor=None):
    """No report formatting or error-record entry can skip native cleanup."""
    publisher.failed = publisher.owner.failed = True
    buffers = publisher.captures if batch is None else batch.captures
    report = getattr(error, "failure_capture", None)
    primary = report.failure.primary_error if (
        type(report) is NativeFailureCapture and report.failure is error) else error
    for original_capture in buffers:
        if primary is original_capture.failure:
            primary = original_capture.failure.primary_error
            break
    for buffer in buffers:
        if primary is buffer.failure:
            continue
        if buffer.failure.primary_error is None:
            buffer.failure.primary_error = primary
        try:
            # Wrappers stay in their original retained capture. Copy only raw
            # origins/secondary errors, never a wrapper into another buffer.
            if primary is not None and primary is not buffer.failure:
                buffer.record(operation, primary, descriptor)
            if type(report) is NativeFailureCapture and report is not buffer and report.failure is error:
                for original in report._slots:
                    secondary = original.error
                    for original_capture in buffers:
                        if secondary is original_capture.failure:
                            secondary = original_capture.failure.primary_error
                            break
                    if secondary is not None and secondary is not buffer.failure and secondary is not report.failure:
                        buffer.record(original.operation, secondary, original.descriptor)
                if report.aggregation_error is not None:
                    secondary = report.aggregation_error
                    for original_capture in buffers:
                        if secondary is original_capture.failure:
                            secondary = original_capture.failure.primary_error
                            break
                    if secondary is not None and secondary is not buffer.failure and secondary is not report.failure:
                        buffer.record("read_report_aggregation", secondary)
                if report.overflowed:
                    buffer.record("read_report_overflow", report._overflow)
        except BaseException as aggregation_error:
            origin = aggregation_error
            for original_capture in buffers:
                if aggregation_error is original_capture.failure:
                    origin = original_capture.failure.primary_error
                    break
            buffer.aggregation_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = operation, primary, descriptor
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "record_entry_failure", origin, descriptor


def _safe_fact(publisher, batch, event, payload):
    try:
        gt._private_fact(publisher.owner, event, payload)
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        buffers = publisher.captures if batch is None else batch.captures
        origin = error
        for original in publisher.origins if batch is None else batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in buffers:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_publication_history", origin, None
        try:
            _capture(publisher, batch, "phase_publication_history", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in publisher.origins if batch is None else batch.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in buffers:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None


def _close_read(publisher, batch, read, primary=None):
    # The primary supplied to ReadScope.close must itself be the raw origin.
    if primary is read.failures.failure:
        primary = read.failures.failure.primary_error
    for original in publisher.origins if batch is None else batch.origins:
        if primary is original.failure:
            primary = original.failure.primary_error
            break
    try:
        read.close(primary_error=primary)
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        buffers = publisher.captures if batch is None else batch.captures
        origin = read.failures.failure.primary_error if error is read.failures.failure else error
        for original in publisher.origins if batch is None else batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in buffers:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = primary if primary is not None else origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_publication_read_close", origin, None
        try:
            _capture(publisher, batch, "phase_publication_read_close", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in publisher.origins if batch is None else batch.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in buffers:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        # Numbers already consumed by close() never enter this fallback.
        while read.owned:
            descriptor = read.owned.pop()
            try:
                os.close(descriptor)
            except BaseException as close_error:
                for buffer in buffers:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = close_error
                    if buffer.first_error is None:
                        buffer.first_error = close_error
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = (
                            "phase_publication_remaining_close", close_error, descriptor)
                try:
                    _capture(publisher, batch, "phase_publication_remaining_close", close_error, descriptor)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in publisher.origins if batch is None else batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in buffers:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = (
                                "phase_capture_entry_failure", raw_report_error, descriptor)


def _close_trees(publisher, batch):
    for copy in batch.copies:
        descriptor, copy.tree_fd = copy.tree_fd, None
        if descriptor is not None:
            copy.close_attempted = True
            try:
                os.close(descriptor)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_publication_tree_close", origin, descriptor
                try:
                    _capture(publisher, batch, "phase_publication_tree_close", error, descriptor)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in batch.captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = (
                                "phase_capture_entry_failure", raw_report_error, descriptor)
            copy.close_details["fd"] = descriptor
            copy.close_details["mount_id"] = copy.tree_mount_id
            try:
                _safe_fact(publisher, batch, "phase_copy_tree_close_attempted", copy.close_details)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    buffer.aggregation_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_close_history_entry_failure", origin, descriptor


def _close_resources(publisher, batch, read, primary=None):
    """Independent helper entries; fallback consumes only remaining ownership."""
    try:
        _close_trees(publisher, batch)
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        origin = error
        for original in batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in batch.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = primary if primary is not None else origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_tree_cleanup_entry_failure", origin, None
    for copy in batch.copies:
        descriptor, copy.tree_fd = copy.tree_fd, None
        if descriptor is None:
            continue
        copy.close_attempted = True
        try:
            os.close(descriptor)
        except BaseException as error:
            publisher.failed = publisher.owner.failed = True
            for buffer in batch.captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = error
                if buffer.first_error is None:
                    buffer.first_error = error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_remaining_tree_close", error, descriptor
        copy.close_details["fd"] = descriptor
        copy.close_details["mount_id"] = copy.tree_mount_id
    try:
        _close_read(publisher, batch, read, primary)
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        origin = error
        for original in batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in batch.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = primary if primary is not None else origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_read_cleanup_entry_failure", origin, None
    while read.owned:
        descriptor = read.owned.pop()
        try:
            os.close(descriptor)
        except BaseException as error:
            publisher.failed = publisher.owner.failed = True
            for buffer in batch.captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = error
                if buffer.first_error is None:
                    buffer.first_error = error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_remaining_read_close", error, descriptor


def _budget(publisher, *, cleanup=False):
    from . import linux_deadline as deadlines
    from .linux_enforcement import ResourceEnvelope
    from .linux_production_controller import LinuxProductionController, LinuxProductionOSPorts

    binding = publisher.binding
    if (type(binding.controller) is not LinuxProductionController
            or type(binding.ledger) is not AppendOnlyLedger):
        gt._deny("phase publication requires its original concrete native controller/ledger")
    assembly = LinuxProductionController._state(binding.controller, allow_failed=cleanup)
    envelope = assembly.envelope
    if (assembly.guard() is not publisher.guard() or assembly.approval is not binding.approval
            or assembly.limits is not binding.limits or assembly.started_ns != binding.started_ns
            or assembly.pid != binding.pid or assembly.thread is not binding.thread
            or type(assembly.ports) is not LinuxProductionOSPorts
            or type(envelope) is not ResourceEnvelope or assembly.total_timer_armed is not True
            or assembly.total_timer is assembly.stage_timer
            or envelope.stop_margin_ns != gt._MOUNT_HELPER_STOP_MARGIN_NS
            or envelope.stage_a_wall_ns != binding.limits.stage_a_wall_ns
            or envelope.total_wall_ns != binding.limits.total_wall_ns
            or envelope.runtime_max_ns != binding.limits.total_wall_ns - envelope.stop_margin_ns
            or envelope.stage_a_stop_ns != binding.limits.stage_a_wall_ns - envelope.stop_margin_ns):
        gt._deny("phase publication lost its original armed clock/resource envelope")
    handles = ((assembly.total_timer, binding.started_ns + envelope.runtime_max_ns),)
    if assembly.stage_timer is not None:
        handles += ((assembly.stage_timer, binding.started_ns + envelope.stage_a_stop_ns),)
    elif tuple(item.event for item in publisher.owner.phase.accepted)[:2] != (
            "stage_a_finished", "stage_b_entry_passed"):
        gt._deny("phase publication lacks the original accepted Stage A retirement boundary")
    if assembly.activity is not None:
        activity = assembly.activity
        if (type(activity) is not tuple or len(activity) != 3 or type(activity[0]) is not object
                or type(activity[2]) is not str or not activity[2]
                or activity[1] is assembly.total_timer or activity[1] is assembly.stage_timer):
            gt._deny("phase publication lost its original current activity deadline owner")
        timer = deadlines._TIMERS.get(activity[1]) if type(activity[1]) is deadlines.LinuxKernelDeadline else None
        if (type(timer) is not deadlines._NativeTimer or type(timer.deadline_ns) is not int
                or not binding.started_ns < timer.deadline_ns <= binding.started_ns + envelope.runtime_max_ns):
            gt._deny("phase publication lacks its current original armed activity interval")
        # This is the actual private timer's already armed absolute boundary,
        # including any earlier fit/activity boundary. Never renew a duration.
        handles += ((activity[1], timer.deadline_ns),)
    kill_ns = None
    for handle, expected in handles:
        timer = deadlines._TIMERS.get(handle) if type(handle) is deadlines.LinuxKernelDeadline else None
        if (type(timer) is not deadlines._NativeTimer or timer.consumed is not False
                or timer.armed is not True or timer.pid != binding.pid or timer.thread is not binding.thread
                or timer.deadline_ns != expected or type(timer.library) is not ctypes.CDLL
                or type(timer.timer_id) is not ctypes.c_void_p):
            gt._deny("phase publication refuses supplied or retired kernel deadline handles")
        kill_ns = expected if kill_ns is None else min(kill_ns, expected)
    # Reserve the original envelope's margin BEFORE the actual SIGKILL timer.
    # These absolute times have no caller-supplied duration or deadline input.
    stop_ns, cleanup_ns = kill_ns - envelope.stop_margin_ns, kill_ns
    if time.monotonic_ns() >= (cleanup_ns if cleanup else stop_ns):
        gt._deny("phase publication exhausted its original cleanup-reserved kernel deadline")
    return stop_ns, cleanup_ns


def _clock(publisher, *, cleanup=False):
    from .linux_production_controller import LinuxProductionController

    assembly = LinuxProductionController._state(publisher.binding.controller, allow_failed=cleanup)
    return (assembly.total_timer, assembly.stage_timer, assembly.activity)


def _original(handle, *, cleanup=False):
    publisher = _PUBLISHERS.get(handle) if type(handle) is _OriginalPhaseInputPublisher else None
    guard = publisher.guard() if publisher is not None else None
    if (publisher is None or type(guard) is not BudgetGuard
            or gt._OWNERS.get(guard) is not publisher.owner
            or publisher.owner.phase_publisher is not publisher
            or publisher.handle is not handle or gt._broker_guard(publisher.owner.broker) is not guard
            or type(publisher.owner.broker) is not gt.LinuxNativeGTBroker
            or publisher.pid != os.getpid() or publisher.thread is not threading.current_thread()
            or require_startup_binding(guard) is not publisher.binding
            or publisher.binding is not publisher.owner.binding
            or not publisher.owner.installed or not publisher.installed
            or ((publisher.failed or publisher.owner.failed) and not cleanup)):
        gt._deny("phase publisher has no healthy original privately installed broker authority")
    try:
        if publisher.owner.mount_api is None:
            gt._deny("phase publisher cannot first-load a mount helper")
        gt._libc(guard, publisher.owner, cleanup=cleanup)  # Cached original API only.
        if not cleanup:
            gt._live(guard, publisher.owner)
        _budget(publisher, cleanup=cleanup)
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        batch = publisher.active
        buffers = publisher.captures if batch is None else batch.captures
        origin = error
        for original in publisher.origins if batch is None else batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in buffers:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_publisher_identity", origin, None
        try:
            _capture(publisher, batch, "phase_publisher_identity", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in publisher.origins if publisher.active is None else publisher.active.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in buffers:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        raise
    return publisher


def _children_absent(publisher):
    from . import linux_child_launch as children

    # Even consumed entries must be removed by their original reaper. A bool,
    # passed exit result or PID lookup cannot retire a native registry entry.
    if children._CHILDREN:
        gt._deny("phase unpublication refuses any retained original native child issuance")
    if any(batch.outcome is not None and not batch.outcome_consumed for batch in publisher.batches):
        gt._deny("phase unpublication requires original once-only outcome consumption")
    gt._require_worker_reference_closure_before_revoke(publisher.owner)
    if children._CHILDREN:
        gt._deny("native child ownership changed during the original kernel reference fence")


def _commitment_batch(publisher, batch):
    """Current original grant/clock checks, independent of secret possession."""
    _original(publisher.handle)
    owner, guard = publisher.owner, publisher.guard()
    clock = _clock(publisher)
    if (type(batch) is not _Batch or publisher.active is not batch or batch.closed or batch.failed
            or not any(item is batch for item in publisher.batches)
            or batch.commitment_key is not owner.commitment_key
            or type(owner.commitment_key) is not gt._CommitmentKey
            or any(item.commitment_key is not owner.commitment_key for item in publisher.batches)
            or type(batch.grant) is not gt._Grant or owner.active is not batch.grant
            or batch.scope_bytes != batch.grant.scope_bytes or batch.release != batch.grant.release
            or _canonical(asdict(batch.grant.scope)) != batch.scope_bytes
            or len(batch.clock) != 3 or batch.clock[2] is None
            or any(current is not original for current, original in zip(clock, batch.clock))
            or _budget(publisher) != (batch.stop_ns, batch.cleanup_ns)):
        gt._deny("commitment key requires the exact original active GT batch and armed clock")
    gt.phase.require_owned_work(guard, stage_a=False, fit=False)
    owner.graph.validate_scope(batch.grant.scope)
    gt._check_ledger(owner, gt._journal(guard, owner).records)
    owner.binding.ledger.require_gt_release(batch.grant.scope, batch.release)
    return owner.commitment_key


def _commitment_record(key):
    # Only provenance/fingerprint/cost observations enter history. Raw secret
    # bytes remain strongly held in the original private record, including on
    # failed returns. Immutable Python bytes have no claimed erasure receipt.
    elapsed = (key.call_returned_ns - key.call_started_ns if key.call_returned_ns is not None
               and key.call_started_ns is not None else "UNKNOWN_NOT_ZERO")
    return {"producer": "posix.getrandom", "requested_bytes": 32, "flags": key.flags,
        "parent_pid": key.pid, "native_tid": key.owner.kernel.native_tid,
        "scope_sha256": hashlib.sha256(key.scope_bytes).hexdigest(), "release_sha256": key.release,
        "owner_started_ns": key.binding.started_ns, "stop_ns": key.stop_ns,
        "cleanup_ns": key.cleanup_ns, "attempt_consumed": key.attempt_consumed,
        "python_builtin_call_attempted": key.python_call_attempted,
        "python_builtin_call_returned": key.python_call_returned,
        # CPython may handle EINTR internally. One consumed Python call attempt
        # is not an observation of the number of underlying kernel syscalls.
        "native_syscall_count": "UNKNOWN_NOT_ZERO", "started_ns": key.started_ns,
        "call_started_ns": key.call_started_ns, "call_returned_ns": key.call_returned_ns,
        "validation_finished_ns": key.finished_ns, "observed_call_elapsed_ns": elapsed,
        "raw_length": key.raw_length, "secret_sha256": key.secret_sha256,
        "return_validated": key.return_validated,
        "resource_accounting": "original absolute clock and controller resource envelope",
        "incremental_ram_bytes": "UNKNOWN_NOT_ZERO", "incremental_vram_bytes": "UNKNOWN_NOT_ZERO",
        "incremental_non_e_bytes": "UNKNOWN_NOT_ZERO"}


def _require_commitment_history(owner, publisher):
    key = owner.commitment_key
    events = tuple(fact for fact in owner.ledger_facts if fact.event.startswith("gt_broker_commitment_key_"))
    if type(key) is not gt._CommitmentKey:
        gt._deny("original commitment key record was replaced")
    if not key.attempt_consumed:
        if (events or key.owner is not None or key.raw is not None or key.ready or key.failed
                or key.python_call_attempted or key.python_call_returned or key.primary_error is not None
                or key.secondary_error is not None or key.started_sha256 is not None
                or key.finished_sha256 is not None or (publisher is not None and publisher.batches)):
            gt._deny("unused original commitment key has a retained issuance or failure")
        return key
    if (type(publisher) is not _Publisher or key.owner is not owner or key.publisher is not publisher
            or key.binding is not owner.binding or key.phase is not owner.phase or key.terminal is not owner.terminal
            or key.ledger is not owner.binding.ledger or key.pins != owner.pins
            or key.pid != publisher.pid or key.thread is not publisher.thread
            or type(key.batch) is not _Batch or not any(item is key.batch for item in publisher.batches)
            or key.batch.commitment_key is not key or key.grant is not key.batch.grant
            or key.scope_bytes != key.batch.scope_bytes or key.release != key.batch.release
            or (key.stop_ns, key.cleanup_ns) != (key.batch.stop_ns, key.batch.cleanup_ns)
            or len(key.clock) != 3 or len(key.batch.clock) != 3
            or any(original is not retained for original, retained in zip(key.clock, key.batch.clock))
            or key.captures is not key.batch.captures or key.origins is not key.batch.origins
            or key.producer is not gt._GETRANDOM or key.producer_module is not gt._GETRANDOM_MODULE
            or key.producer_type is not gt.BuiltinFunctionType or type(key.producer) is not key.producer_type
            or key.flags != gt._GRND_NONBLOCK or key.flags != 1
            or key.failed or not key.ready or not key.python_call_attempted or not key.python_call_returned
            or not key.return_validated or type(key.raw) is not bytes or len(key.raw) != 32
            or key.raw_length != 32 or key.secret_sha256 != hashlib.sha256(key.raw).hexdigest()
            or key.primary_error is not None or key.secondary_error is not None
            or any(buffer.first_error is not None or buffer.failure.primary_error is not None
                or buffer.aggregation_error is not None or buffer.overflowed for buffer in key.origins)
            or key.started_body is None or key.finished_body is None or len(events) != 2
            or tuple(fact.event for fact in events) != (
                "gt_broker_commitment_key_started", "gt_broker_commitment_key_finished")
            or (events[0].sha256, events[1].sha256) != (key.started_sha256, key.finished_sha256)
            or not events[0].seq < events[1].seq
            or not (owner.binding.started_ns <= key.started_ns <= key.call_started_ns
                <= key.call_returned_ns <= key.finished_ns < key.stop_ns < key.cleanup_ns)
            or key.finished_body != _commitment_record(key)):
        gt._deny("original commitment key lacks its once-only healthy producer and durable history")
    for fact, body in zip(events, (key.started_body, key.finished_body)):
        expected = dict(body, invocation_id=owner.binding.invocation_id, controller_run_id=owner.run_id)
        payload = json.loads(fact.payload)
        private = tuple(item for item in owner.facts if item.event == fact.event
                        and item.sha256 == payload.get("history_sha256") and item.payload == _canonical(expected))
        if (len(private) != 1 or fact.payload != _canonical(dict(expected, history_sha256=private[0].sha256))):
            gt._deny("commitment key record differs from the original linked private/durable facts")
    return key


def _issue_commitment_key(publisher, batch):
    """Issue once from the system builtin, then reuse for this original owner."""
    owner, guard, key = publisher.owner, publisher.guard(), publisher.owner.commitment_key
    _commitment_batch(publisher, batch)
    if key.attempt_consumed:
        return _require_commitment_history(owner, publisher)
    if (len(publisher.batches) != 1 or publisher.batches[0] is not batch
            or key.owner is not None or key.batch is not None or key.raw is not None
            or key.ready or key.failed or key.python_call_attempted or key.python_call_returned
            or key.primary_error is not None or key.secondary_error is not None
            or key.started_body is not None or key.finished_body is not None
            or any(fact.event.startswith("gt_broker_commitment_key_") for fact in owner.ledger_facts)):
        gt._deny("original commitment key issuance cannot replace or retry a retained attempt")
    # All raw/attempt/error/origin/builtin slots were allocated with _Owner,
    # and the real batch captures/read buffers already exist. Keep their exact
    # identities before consuming the only issuance attempt or entering native.
    key.owner, key.publisher, key.binding = owner, publisher, owner.binding
    key.phase, key.terminal, key.ledger, key.pins = owner.phase, owner.terminal, owner.binding.ledger, owner.pins
    key.pid, key.thread, key.batch, key.grant = publisher.pid, publisher.thread, batch, batch.grant
    key.scope_bytes, key.release = batch.scope_bytes, batch.release
    key.stop_ns, key.cleanup_ns, key.clock = batch.stop_ns, batch.cleanup_ns, batch.clock
    key.captures, key.origins = batch.captures, batch.origins
    key.attempt_consumed = True
    try:
        key.operation = "gt_commitment_builtin_identity"
        if (key.producer is not gt._GETRANDOM or key.producer_type is not gt.BuiltinFunctionType
                or type(key.producer) is not key.producer_type or key.producer_module is None
                or key.producer_module is not gt._GETRANDOM_MODULE
                or key.producer_module is not gt.sys.modules.get("posix")
                or key.producer.__module__ != "posix" or key.producer.__name__ != "getrandom"
                or key.producer.__self__ is not key.producer_module
                or getattr(key.producer_module, "getrandom", None) is not key.producer
                or getattr(os, "getrandom", None) is not key.producer
                or type(key.flags) is not int or key.flags != 1 or key.flags != gt._GRND_NONBLOCK
                or getattr(os, "GRND_NONBLOCK", None) != key.flags):
            raise key.unavailable_error
        producer, flags = key.producer, key.flags
        key.started_ns = time.monotonic_ns()
        key.operation = "gt_commitment_started_history"
        key.started_body = _commitment_record(key)
        key.started_sha256 = gt._record(guard, owner, "gt_broker_commitment_key_started", key.started_body)
        # The durable start is observed before the only builtin invocation.
        # Revalidate the existing absolute budget; never create another timer,
        # resource sample, allowance, callback or entropy fallback.
        key.operation = "gt_commitment_native_preflight"
        _commitment_batch(publisher, batch)
        key.call_started_ns = time.monotonic_ns()
        key.operation = "gt_commitment_getrandom"
        key.python_call_attempted = True
        key.raw = producer(32, flags)
        # This original strong holder is populated BEFORE type, length, hash,
        # serialization, history, or another helper call can lose the return.
        key.python_call_returned = True
        key.call_returned_ns = time.monotonic_ns()
        key.operation = "gt_commitment_return_validation"
        if type(key.raw) is not bytes:
            raise key.invalid_return_error
        key.raw_length = len(key.raw)
        if key.raw_length != 32:
            raise key.invalid_return_error
        key.secret_sha256 = hashlib.sha256(key.raw).hexdigest()
        key.return_validated = True
        _commitment_batch(publisher, batch)
        key.finished_ns = time.monotonic_ns()
        key.operation = "gt_commitment_finished_history"
        key.finished_body = _commitment_record(key)
        key.finished_sha256 = gt._record(guard, owner, "gt_broker_commitment_key_finished", key.finished_body)
        _commitment_batch(publisher, batch)
        key.ready = True
        return _require_commitment_history(owner, publisher)
    except BaseException as error:
        key.failed = batch.failed = publisher.failed = owner.failed = True
        key.ready = False
        origin = error
        report = getattr(error, "failure_capture", None)
        if type(report) is NativeFailureCapture and report.failure is error:
            key.report_origin = report
            origin = report.failure.primary_error
        for original in key.origins:
            if origin is original.failure:
                key.report_origin = original
                origin = original.failure.primary_error
                break
        key.primary_error = origin
        # Save raw primary inline before any reporting/history/cleanup entry.
        # Reports remain in their original strong holders, never cross-buffer
        # wrapper slots that point back to one another.
        for buffer in key.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = key.operation, origin, None
        try:
            _capture(publisher, batch, key.operation, error)
        except BaseException as report_error:
            secondary = report_error
            report = getattr(report_error, "failure_capture", None)
            if type(report) is NativeFailureCapture and report.failure is report_error:
                key.secondary_origin = report
                secondary = report.failure.primary_error
            for original in key.origins:
                if secondary is original.failure:
                    key.secondary_origin = original
                    secondary = original.failure.primary_error
                    break
            key.secondary_error = secondary
            for buffer in key.captures:
                buffer.aggregation_error = secondary
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "gt_commitment_capture_entry_failure", secondary, None
        try:
            gt._record(guard, owner, "gt_broker_commitment_key_failed",
                       dict(_commitment_record(key), operation=key.operation))
        except BaseException as history_error:
            secondary = history_error
            report = getattr(history_error, "failure_capture", None)
            if type(report) is NativeFailureCapture and report.failure is history_error:
                key.secondary_origin = report
                secondary = report.failure.primary_error
            for original in key.origins:
                if secondary is original.failure:
                    key.secondary_origin = original
                    secondary = original.failure.primary_error
                    break
            key.secondary_error = secondary
            for buffer in key.captures:
                buffer.aggregation_error = secondary
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "gt_commitment_failure_history_entry", secondary, None
        raise


def _current_phase_commitment_key(guard, scope, release):
    """Private future fixed-caller read; secret possession grants no authority."""
    with gt._LOCK:
        owner = gt._OWNERS.get(guard) if type(guard) is BudgetGuard else None
        publisher = owner.phase_publisher if owner is not None else None
        batch = publisher.active if type(publisher) is _Publisher else None
        if (type(batch) is not _Batch or not batch.published or batch.closed
                or scope is not batch.grant.scope or release != batch.release):
            gt._deny("commitment key read requires the original currently published GT scope")
        _commitment_batch(publisher, batch)
        return _require_commitment_history(owner, publisher).raw


def _phase_launch_owner(state, *, cleanup=False):
    """Authenticate an internal issuance, never a caller publisher/receipt."""
    from . import linux_child_launch as children

    guard = state.guard if type(state) is children._Owned else None
    owner = gt._OWNERS.get(guard) if type(guard) is BudgetGuard else None
    publisher = owner.phase_publisher if owner is not None else None
    if (type(publisher) is not _Publisher or publisher is not state.publisher
            or _PUBLISHERS.get(publisher.handle) is not publisher
            or publisher.owner is not owner or publisher.binding is not state.binding
            or state.pid != os.getpid() or state.thread is not threading.current_thread()
            or state.binding.pid != state.pid or state.binding.thread is not state.thread
            or require_startup_binding(guard) is not state.binding
            or type(state.batch) is not _Batch or publisher.active is not state.batch
            or state.batch.launch is not state or state.batch.closed
            or not any(item is state.batch for item in publisher.batches)):
        gt._deny("native phase issuance lost its original publisher/batch/startup owner")
    _original(publisher.handle, cleanup=cleanup)
    if _budget(publisher, cleanup=cleanup) != (state.stop_ns, state.cleanup_ns):
        gt._deny("native phase deadlines differ from the original armed publisher clock")
    batch = state.batch
    current_clock = _clock(publisher, cleanup=cleanup)
    if (len(batch.clock) != 3 or batch.clock[2] is None
            or any(now is not original for now, original in zip(current_clock, batch.clock))):
        gt._deny("phase publication/launch cannot replace or retire its original activity clock")
    if (not batch.published or batch.grant is not owner.active
            or type(owner.active) is not gt._Grant or state.scope is not batch.grant.scope
            or batch.scope_bytes != batch.grant.scope_bytes
            or _canonical(asdict(state.scope)) != batch.scope_bytes
            or state.release != batch.release or batch.release != batch.grant.release
            or any(copy.source is None or not copy.move_succeeded or copy.removed
                   or copy.installed_mount_id not in owner.issued_ids for copy in batch.copies)):
        gt._deny("native phase issuance lost its current original GT authorization/copies")
    if not cleanup:
        owner.graph.validate_scope(state.scope)
        gt._check_ledger(owner, gt._journal(guard, owner).records)
        AppendOnlyLedger.require_gt_release(state.binding.ledger, state.scope, state.release)
    return publisher, batch


def _acquire_phase_launch(guard, scope, release, state, stop_ns, cleanup_ns):
    """Select the sole registered current batch internally and consume once."""
    from . import linux_child_launch as children

    with gt._LOCK:
        owner = gt._OWNERS.get(guard) if type(guard) is BudgetGuard else None
        publisher = owner.phase_publisher if owner is not None else None
        if (type(state) is not children._Owned or state.guard is not guard
                or type(publisher) is not _Publisher or publisher.owner is not owner):
            gt._deny("phase launch requires the original privately registered GT publisher")
        batch = publisher.active
        state.publisher, state.batch = publisher, batch
        state.binding, state.scope, state.release = publisher.binding, scope, release
        if type(batch) is _Batch:
            state.captures = (state.errors, batch.errors, owner.failure_errors)
        publisher = _original(publisher.handle)
        if (type(batch) is not _Batch or not batch.published or batch.closed
                or batch.launch is not None or batch.outcome is not None
                or owner.active is not batch.grant or scope is not batch.grant.scope
                or type(scope) is not TruthReadScope or release != batch.release
                or _canonical(asdict(scope)) != batch.scope_bytes
                or _budget(publisher) != (batch.stop_ns, batch.cleanup_ns)
                or type(stop_ns) is not int or type(cleanup_ns) is not int
                or (stop_ns, cleanup_ns) != (batch.stop_ns, batch.cleanup_ns)
                or children._CHILDREN):
            gt._deny("phase launch refuses repeated/foreign scope, release or renewed deadlines")
        # Preallocated launch/batch/broker buffers are shared before native
        # birth. A failed issuance is permanently retained; never retry it.
        state.publisher, state.batch = publisher, batch
        state.binding, state.scope, state.release = publisher.binding, scope, release
        state.stop_ns, state.cleanup_ns = batch.stop_ns, batch.cleanup_ns
        state.captures = (state.errors, batch.errors, owner.failure_errors)
        batch.launch = state
        _phase_launch_owner(state)
        return publisher, batch


def _phase_launch_failure(state, operation, error, descriptor=None):
    # Callers retain raw exceptions inline before entering this reporting
    # helper. Poisoning never depends on a journal/report succeeding.
    publisher = state.publisher
    if publisher is None:
        # A malformed launch payload can fail before batch acquisition. Its
        # original guard/startup still identifies the sole real failure owner;
        # this path only poisons/preserves, and cannot acquire a launch/grant.
        owner = gt._OWNERS.get(state.guard) if type(state.guard) is BudgetGuard else None
        original = owner.phase_publisher if owner is not None else None
        if (type(original) is _Publisher and _PUBLISHERS.get(original.handle) is original
                and original.binding is state.binding and state.pid == os.getpid()
                and state.thread is threading.current_thread()):
            publisher = state.publisher = original
            state.batch = original.active
            publisher.failed = owner.failed = state.failed = True
            state.captures = ((state.errors, state.batch.errors, owner.failure_errors)
                              if type(state.batch) is _Batch else (state.errors, owner.failure_errors))
    if publisher is not None:
        publisher.failed = publisher.owner.failed = state.failed = True
        try:
            _capture(publisher, state.batch, operation, error, descriptor)
        except BaseException as report_error:
            # A report-helper entry failure is secondary to the already saved
            # original operation. Never throw it across the cleanup loop.
            raw_report_error = report_error
            for original_capture in state.captures:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in state.captures:
                buffer.aggregation_error = raw_report_error
                reserved = next(buffer._cursor, None)
                if reserved is None:
                    buffer.overflowed = True
                else:
                    reserved.operation, reserved.error, reserved.descriptor = (
                        "phase_failure_report_entry", raw_report_error, descriptor)


def _phase_launch_payload(state, payload):
    publisher, batch = _phase_launch_owner(state)
    _commitment_batch(publisher, batch)
    key = _require_commitment_history(publisher.owner, publisher)
    expected = {StudyStage.TRAIN_LABELS: "training_labels", StudyStage.INNER_EVALUATION: "inner_evaluator",
                StudyStage.OUTER_EVALUATION: "outer_evaluator"}.get(state.scope.stage)
    outer = state.scope.stage is StudyStage.OUTER_EVALUATION
    if (type(payload["gt_commitment_key"]) is not bytes or payload["gt_commitment_key"] != key.raw
            or batch.commitment_key is not key
            or payload["scope"] is not state.scope or expected is None or payload["operation"] != expected
            or payload["expected_view_sha256"] != batch.grant.view.mapping.sha256.lower()
            or len(batch.copies) != (2 if outer else 1)
            or (outer and (payload["control_final_matches"] is not batch.copies[1].source.registered
                or payload["control_metrics_sha256"] != require_frozen_admission().a2_004_final_metrics_sha256.lower()
                or payload["reference_candidates"] is None))
            or (not outer and (payload["control_final_matches"] is not None
                or payload["control_metrics_sha256"] is not None or payload["reference_candidates"] is not None))):
        gt._deny("phase scientific operation/view/control payload differs from its original current authorization")
    # Compare the codec's decoded bytes with the sole original system-issued
    # key shared by this study's phases/control/treatment. Key/HMAC/handle data
    # do not install a grant, mount or native right, or freeze the whole payload.
    return expected


def _phase_launch_record(state, event, payload):
    with gt._LOCK:
        publisher, batch = _phase_launch_owner(state)
        if (state.errors.first_error is not None or state.errors.failure.primary_error is not None
                or state.errors.aggregation_error is not None or state.errors.overflowed
                or batch.errors.first_error is not None):
            gt._deny("phase history cannot convert a retained operation failure into success")
        return gt._record(state.guard, publisher.owner, event,
            dict(payload, release_sha256=batch.release,
                 scope_sha256=hashlib.sha256(batch.scope_bytes).hexdigest()))


def _tree(read, owner, expected=None, *, mounted=()):
    # Validate only the fixed input substrate. Runtime/source descendants are
    # executable installation closure owned by the original real gate, not
    # inferred from metadata here. Data-copy mounts are independently noexec.
    root, inputs = read.directory(_ROOT), read.directory(_INPUTS)
    root_frame, inputs_frame = q._frame(os.fstat(root)), q._frame(os.fstat(inputs))
    if root_frame[2] & 0o222 or inputs_frame[2] & 0o222:
        gt._deny("phase-source directories must already be immutable installer objects")
    mounts = gt._mounts(read, owner.binding.pid)
    root_id, filesystem_root = gt._source_mount(read, root, _ROOT, mounts, owner.binding.pid)
    inputs_id, _ = gt._source_mount(read, inputs, _INPUTS, mounts, owner.binding.pid)
    visible_root = [mount for mount in mounts if mount.point == _ROOT]
    if (len(visible_root) != 1 or visible_root[0].mount_id != root_id
            or not {"ro", "nosuid", "nodev"} <= visible_root[0].options
            or inputs_id != root_id or root_frame[0] != inputs_frame[0]
            or any(mount.point.startswith(_INPUTS + "/") and mount.point not in mounted for mount in mounts)):
        gt._deny("phase-source backing lacks its exact immutable private installer mount")
    targets = []
    for target in _TARGETS:
        if target in mounted:
            continue
        descriptor, frame = gt._file(read, target)
        if (frame[2] & 0o222 or frame[6] != 0
                or gt._mount_id(read, descriptor, owner.binding.pid) != root_id):
            gt._deny("phase target is absent or differs from its empty immutable placeholder contract")
        targets.append((target, frame))
        read.close_one(descriptor)
    tree = _Tree(root_frame, inputs_frame, root_id, filesystem_root, tuple(targets))
    if expected is not None:
        if (tree.root_frame != expected.root_frame or tree.inputs_frame != expected.inputs_frame
                or tree.mount_id != expected.mount_id or tree.filesystem_root != expected.filesystem_root
                or any((target, frame) not in expected.targets for target, frame in tree.targets)):
            gt._deny("phase-source backing or original placeholder was replaced")
    return tree, inputs


def _hash(read, descriptor, source, maximum):
    if not 0 < source.frame[6] <= maximum:
        gt._deny("authorized phase input exceeds its original bounded file frame")
    digest, offset = hashlib.sha256(), 0
    while offset < source.frame[6]:
        read.checkpoint()
        block = os.pread(descriptor, min(65536, source.frame[6] - offset), offset)
        if not block:
            gt._deny("authorized phase input ended before its protected frame")
        digest.update(block)
        offset += len(block)
    if (os.pread(descriptor, 1, offset) or q._frame(os.fstat(descriptor)) != source.frame
            or digest.hexdigest() != source.mapping.sha256.lower()):
        gt._deny("authorized held phase input changed or differs from the original frozen hash")
    read.checkpoint()


def _gt_source(publisher, batch):
    active, read, owner = batch.grant, batch.read, publisher.owner
    alias = active.view.mapping.bind_path
    descriptor, frame = gt._file(read, alias, contents=True)
    mounts = gt._mounts(read, owner.binding.pid)
    mount_id, root = gt._source_mount(read, descriptor, alias, mounts, owner.binding.pid)
    exact = [mount for mount in mounts if mount.point == alias]
    if (frame != active.view.frame or mount_id != active.mount_id
            or root != active.view.identity.filesystem_root or len(exact) != 1
            or exact[0].mount_id != active.mount_id
            or not {"ro", "nosuid", "nodev", "noexec"} <= exact[0].options):
        gt._deny("phase GT input is not the exact currently released original native broker alias")
    source = _Source(alias, active.view.mapping, active.view.identity, frame, mount_id)
    _hash(read, descriptor, source, gt._MAX_GT_BYTES)
    return descriptor, source


def _historical_source(publisher, batch):
    from . import admission_bootstrap as bootstrap, production_metadata as metadata
    from .control_matches import MAX_CONTROL_MATCH_BYTES, control_match_registry_bytes

    scope, owner = batch.grant.scope, publisher.owner
    if scope.stage is not StudyStage.OUTER_EVALUATION:
        gt._deny("historical phase publication is restricted to the released outer evaluation scope")
    original, issued = metadata._INSTALLED_METADATA, bootstrap._ISSUED_BOOTSTRAP
    frozen = require_frozen_admission()
    if (type(original) is not metadata._InstalledMetadata or type(issued) is not bootstrap._IssuedBootstrap
            or issued.proof is not original.proof or original.proof.frozen_admission is not frozen
            or issued.consumed is not True
            or issued.pid != publisher.pid or issued.thread is not publisher.thread
            or original.pid != publisher.pid or original.thread is not publisher.thread
            or original.start is not original.proof.start_clock
            or original.start.invocation_started_monotonic_ns != publisher.binding.started_ns
            or original.start.invocation_id != publisher.binding.invocation_id
            or original.metadata.approval is not publisher.binding.approval
            or original.metadata.limits is not publisher.binding.limits
            or original.metadata.path_map_manifest_bytes != owner.manifest):
        gt._deny("historical publication lacks the original privately installed metadata/start/approval")
    projections = original.metadata.control_final_match_projections
    if (type(projections) is not tuple or len(projections) != 5
            or any(type(row) is not RegisteredFile for row in projections)
            or tuple(row.role_id for row in projections) != tuple(sorted(owner.graph.outer_role_ids))
            or hashlib.sha256(control_match_registry_bytes(projections)).hexdigest()
                != frozen.control_final_match_registry_sha256.lower()):
        gt._deny("historical publication lost its exact original frozen five-outer registry")
    rows = [row for row in projections if row.role_id == scope.outer_id]
    if len(rows) != 1:
        gt._deny("historical publication has no unique original outer row")
    row = rows[0]
    from pathlib import PureWindowsPath
    expected_path = str(PureWindowsPath(frozen.gt_input_root_path) / "a2-004-final-matches" /
        (hashlib.sha256(scope.outer_id.encode()).hexdigest()[:20] + ".json"))
    if (row.path != expected_path or row.fields != CONTROL_FINAL_MATCH_FIELDS
            or type(row.projection_attestation) is not str or not row.projection_attestation.strip()
            or row.scope_sha256 != projection_scope_sha256("a2_004_final_matches", scope.outer_id,
                scope.participants, CONTROL_FINAL_MATCH_FIELDS, role_graph_sha256=scope.role_graph_sha256)):
        gt._deny("historical row escapes the original outer role/participant/field registration")
    path_map = ExactPathMap.from_bytes(owner.manifest, owner.pins[0])
    mapping = path_map._entries.get((row.path, row.sha256.lower(), scope.outer_id,
                                    OUTER_CONTROL_FINAL_MATCHES_PHASE))
    if mapping is None:
        gt._deny("historical row has no exact original manifest translation")
    # Translate this single sanctioned non-GT row separately. Mixing it into
    # registered_file_binds' GT set remains forbidden.
    path = gt._source(mapping)
    descriptor, frame = gt._file(batch.read, path, contents=True)
    mount_id, root = gt._source_mount(batch.read, descriptor, path,
        gt._mounts(batch.read, owner.binding.pid), owner.binding.pid)
    if frame[2] & 0o222:
        gt._deny("historical phase source must be an immutable root-owned ordinary file")
    source = _Source(path, mapping, gt._GTIdentity(path, root, frame[0], frame[1], frame[2], frame[3], frame[5]),
                     frame, mount_id, row)
    _hash(batch.read, descriptor, source, MAX_CONTROL_MATCH_BYTES)
    return descriptor, source


def _syscall(publisher, batch, copy, operation, args, details):
    owner, guard = publisher.owner, publisher.guard()
    api = gt._libc(guard, owner)
    gt._record(guard, owner, "gt_broker_phase_syscall_started", dict(details, syscall=operation))
    batch.read.checkpoint()
    if _budget(publisher) != (batch.stop_ns, batch.cleanup_ns):
        gt._deny("phase syscall lost its original cleanup-reserved deadline")
    index = {"open_tree": 0, "mount_setattr": 1, "move_mount": 2}[operation]
    setattr(copy, ("open_attempted", "setattr_attempted", "move_attempted")[index], True)
    ctypes.set_errno(0)
    result = getattr(api, operation)(*args)
    error = ctypes.get_errno() if result < 0 else 0
    # Raw original holders are updated BEFORE another history/validation call.
    if operation == "open_tree" and result >= 0:
        copy.tree_fd = result
        copy.tree_mount_id = gt._mount_id(batch.read, result, owner.binding.pid)
        if copy.tree_mount_id in owner.issued_ids:
            gt._deny("phase detached mount identity was reused in original broker history")
        owner.issued_ids += (copy.tree_mount_id,)
    elif operation == "move_mount" and result >= 0:
        copy.move_succeeded = True
        copy.installed_mount_id = copy.tree_mount_id
        actual = gt._mount_id(batch.read, copy.tree_fd, owner.binding.pid)
        copy.installed_mount_id = actual
        if actual != copy.tree_mount_id:
            if actual not in owner.issued_ids:
                owner.issued_ids += (actual,)
            gt._deny("phase move changed the original retained mount identity")
    if result < 0:
        native_error = copy.native_errors[index]
        native_error.errno = error
        publisher.failed = owner.failed = True
        for buffer in batch.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = native_error
            if buffer.first_error is None:
                buffer.first_error = native_error
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = _NATIVE_FAILURE_LABELS[index], native_error, copy.tree_fd
        try:
            _capture(publisher, batch, _NATIVE_FAILURE_LABELS[index], native_error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in batch.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in batch.captures:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        try:
            _safe_fact(publisher, batch, "phase_native_syscall_failed", dict(details,
                syscall=operation, result=result, errno=error))
        except BaseException as history_error:
            raw_history_error = history_error
            for original_capture in batch.origins:
                if history_error is original_capture.failure:
                    raw_history_error = original_capture.failure.primary_error
                    break
            for buffer in batch.captures:
                buffer.aggregation_error = raw_history_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_native_failure_history_entry", raw_history_error, None
        raise native_error
    gt._private_fact(owner, "phase_native_syscall_returned", dict(details, syscall=operation,
        result=result, errno=error, tree_mount_id=copy.tree_mount_id,
        installed_mount_id=copy.installed_mount_id))
    gt._record(guard, owner, "gt_broker_phase_syscall_finished", dict(details,
        syscall=operation, result=result, errno=error, tree_mount_id=copy.tree_mount_id,
        installed_mount_id=copy.installed_mount_id))
    return result


def _visible(read, owner, copy, *, contents=False):
    source = copy.source
    mounts = gt._mounts(read, owner.binding.pid)
    exact = [mount for mount in mounts if mount.point == copy.target]
    descriptor, frame = gt._file(read, copy.target, contents=contents)
    if (len(exact) != 1 or exact[0].mount_id != copy.installed_mount_id
            or gt._mount_id(read, descriptor, owner.binding.pid) != copy.installed_mount_id
            or exact[0].root != source.identity.filesystem_root
            or exact[0].device != f"{os.major(source.identity.device)}:{os.minor(source.identity.device)}"
            or not {"ro", "nosuid", "nodev", "noexec"} <= exact[0].options
            or "rw" in exact[0].options or exact[0].optional or frame != source.frame):
        gt._deny("phase copy was replaced, hidden, relocated or differs from its retained source/mount")
    return descriptor


def _absence(publisher, batch, read):
    mounts = gt._mounts(read, publisher.pid)
    ids = {value for copy in batch.copies for value in (copy.tree_mount_id, copy.installed_mount_id)
           if value is not None}
    if any(mount.mount_id in ids or mount.point in _TARGETS
           or any(mount.point.startswith(target + "/") for target in _TARGETS) for mount in mounts):
        gt._deny("phase copies remain visible or their exact original issuance was relocated")
    _tree(read, publisher.owner, publisher.tree)
    for copy in batch.copies:
        copy.absence_verified = True


def _remove(publisher, batch):
    owner, read = publisher.owner, batch.cleanup_read
    _children_absent(publisher)  # No removal attempt is consumed before this fence.
    _, cleanup_ns = _budget(publisher, cleanup=True)
    clock = _clock(publisher, cleanup=True)
    if (cleanup_ns != batch.cleanup_ns or len(batch.clock) != 3
            or any(now is not original for now, original in zip(clock, batch.clock))):
        gt._deny("phase cleanup deadline differs from its original issuance clock")
    read.deadline = min(time.monotonic_ns() + q._MAX_SAMPLE_NS, batch.cleanup_ns)
    api = gt._libc(publisher.guard(), owner, cleanup=True)
    primary = None
    try:
        for copy in batch.copies:
            if not copy.move_attempted or copy.removed:
                continue
            gt._kernel_identity(read, owner)
            mounts = gt._mounts(read, publisher.pid)
            exact = [mount for mount in mounts if mount.point == copy.target]
            retained = copy.installed_mount_id if copy.installed_mount_id is not None else copy.tree_mount_id
            if not exact:
                if retained is None or any(mount.mount_id == retained for mount in mounts):
                    gt._deny("failed phase publication has no provable original unrelocated absence")
                copy.removed = True
                copy.remove_details["mount_id"] = retained
                try:
                    _safe_fact(publisher, batch, "phase_copy_failed_publication_absent", copy.remove_details)
                except BaseException as error:
                    publisher.failed = publisher.owner.failed = True
                    origin = error
                    for original in batch.origins:
                        if error is original.failure:
                            origin = original.failure.primary_error
                            break
                    for buffer in batch.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = origin
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        buffer.aggregation_error = origin
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_remove_absent_history_entry_failure", origin, None
                continue
            if copy.remove_attempted or retained is None:
                gt._deny("phase cleanup cannot retry a consumed or unidentified native issuance")
            if len(exact) != 1 or exact[0].mount_id != retained:
                gt._deny("phase cleanup refuses a replaced or hidden retained target issuance")
            # A Python interruption may have hidden move_mount's return. Its
            # attempted original tree ID, exact visible target and source frame
            # can still verify cleanup; no success/healthy receipt is inferred.
            if copy.installed_mount_id is None:
                copy.installed_mount_id = retained
            _, parent = _tree(read, owner, publisher.tree,
                mounted=tuple(item.target for item in batch.copies if item.move_attempted and not item.removed))
            descriptor = _visible(read, owner, copy)
            read.close_one(descriptor)
            if (q._frame(os.fstat(parent)) != publisher.tree.inputs_frame
                    or q._frame(os.stat(_INPUTS, follow_symlinks=False)) != publisher.tree.inputs_frame):
                gt._deny("original phase target parent changed before normal native unmount")
            read.checkpoint()
            if time.monotonic_ns() >= batch.cleanup_ns:
                gt._deny("phase unmount reached its original armed kernel cleanup boundary")
            # Failure to format/append history cannot skip a verified original
            # native removal. No journal read, helper load or new grant follows.
            copy.remove_details["mount_id"] = retained
            try:
                _safe_fact(publisher, batch, "phase_copy_umount_started", copy.remove_details)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    buffer.aggregation_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_umount_started_history_entry_failure", origin, None
            copy.remove_attempted = True
            ctypes.set_errno(0)
            result = api.umount2(copy.target_bytes, gt._UMOUNT_NOFOLLOW)
            error = ctypes.get_errno() if result < 0 else 0
            if result >= 0:
                copy.removed = True
            else:
                native_error = copy.native_errors[3]
                native_error.errno = error
                publisher.failed = publisher.owner.failed = True
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = native_error
                    if buffer.first_error is None:
                        buffer.first_error = native_error
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_native_umount", native_error, None
                try:
                    _capture(publisher, batch, "phase_native_umount", native_error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in batch.captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
            copy.remove_details["result"] = result
            copy.remove_details["errno"] = error
            try:
                _safe_fact(publisher, batch, "phase_copy_umount_finished", copy.remove_details)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    buffer.aggregation_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_umount_finished_history_entry_failure", origin, None
        _absence(publisher, batch, read)  # Scoped; the original released alias remains active.
    except BaseException as error:
        publisher.failed = publisher.owner.failed = True
        origin = error
        for original in batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        primary = origin
        for buffer in batch.captures:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_copy_remove_verification", origin, None
        try:
            _capture(publisher, batch, "phase_copy_remove_verification", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in batch.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in batch.captures:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        raise
    finally:
        try:
            _close_read(publisher, batch, read, primary)
        except BaseException as error:
            publisher.failed = publisher.owner.failed = True
            origin = error
            for original in batch.origins:
                if error is original.failure:
                    origin = original.failure.primary_error
                    break
            for buffer in batch.captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = primary if primary is not None else origin
                if buffer.first_error is None:
                    buffer.first_error = origin
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_remove_read_cleanup_entry_failure", origin, None
        while read.owned:
            descriptor = read.owned.pop()
            try:
                os.close(descriptor)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = error
                    if buffer.first_error is None:
                        buffer.first_error = error
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_remove_remaining_read_close", error, descriptor


def _new_batch(publisher, scope, include_control_final_matches):
    owner, guard, active = publisher.owner, publisher.guard(), publisher.owner.active
    try:
        if (type(scope) is not TruthReadScope or type(active) is not gt._Grant
                or scope is not active.scope or _canonical(asdict(scope)) != active.scope_bytes
                or type(include_control_final_matches) is not bool or publisher.active is not None
                or any(batch.grant is active for batch in publisher.batches)
                or (include_control_final_matches and scope.stage is not StudyStage.OUTER_EVALUATION)):
            gt._deny("phase publication requires the exact new currently released GT scope")
        gt.phase.require_owned_work(guard, stage_a=False, fit=False)
        owner.graph.validate_scope(active.scope)
        gt._check_ledger(owner, gt._journal(guard, owner).records)
        owner.binding.ledger.require_gt_release(active.scope, active.release)
        _children_absent(publisher)
        if len(owner.issued_ids) + 2 > q._MAX_MOUNTS or len(owner.facts) + 32 >= gt._MAX_HISTORY:
            gt._deny("phase publications exceed the original identity/history bound")
        stop_ns, cleanup_ns = _budget(publisher)
        # All slots, close-error storage and both read scopes exist before
        # the first source/target/tree descriptor acquisition.
        batch = _Batch(active, active.scope_bytes, active.release, stop_ns, cleanup_ns,
            tuple(_Copy(target) for target in _TARGETS[:2 if include_control_final_matches else 1]))
        batch.clock = _clock(publisher)
        batch.captures = (batch.errors, owner.failure_errors)
        batch.origins = (batch.read.failures, batch.cleanup_read.failures, batch.errors, owner.failure_errors)
        batch.commitment_key = owner.commitment_key
        publisher.batches += (batch,)
        publisher.active = batch
        batch.read.deadline = min(time.monotonic_ns() + q._MAX_SAMPLE_NS, stop_ns)
        _issue_commitment_key(publisher, batch)
        return batch
    except BaseException as error:
        publisher.failed = owner.failed = True
        batch = publisher.active
        if type(batch) is _Batch:
            batch.failed = True
        buffers = publisher.captures if batch is None else batch.captures
        origin = error
        for original in publisher.origins if batch is None else batch.origins:
            if error is original.failure:
                origin = original.failure.primary_error
                break
        for buffer in buffers:
            if buffer.failure.primary_error is None:
                buffer.failure.primary_error = origin
            if buffer.first_error is None:
                buffer.first_error = origin
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_publication_preflight", origin, None
        try:
            _capture(publisher, batch, "phase_publication_preflight", error)
        except BaseException as report_error:
            raw_report_error = report_error
            for original_capture in publisher.origins if publisher.active is None else publisher.active.origins:
                if report_error is original_capture.failure:
                    raw_report_error = original_capture.failure.primary_error
                    break
            for buffer in buffers:
                buffer.aggregation_error = raw_report_error
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        owner.failure_errors.raise_failure(origin)


class _OriginalPhaseInputPublisher:
    __slots__ = ("__weakref__",)

    def __init__(self):
        gt._deny("phase input publication requires its one-shot original private installer")

    def publish(self, scope, *, include_control_final_matches=False):
        with gt._LOCK:
            publisher = _original(self)
            batch = _new_batch(publisher, scope, include_control_final_matches)
            owner, guard, active = publisher.owner, publisher.guard(), batch.grant
            primary = None
            try:
                gt._kernel_identity(batch.read, owner)
                _, parent = _tree(batch.read, owner, publisher.tree)
                for index, copy in enumerate(batch.copies):
                    source_fd, copy.source = (_gt_source(publisher, batch) if index == 0
                                              else _historical_source(publisher, batch))
                    target_fd, target_frame = gt._file(batch.read, copy.target)
                    if (copy.target, target_frame) not in publisher.tree.targets:
                        gt._deny("phase target differs from the original installed placeholder")
                    details = {"target": copy.target, "source": copy.source.path,
                        "source_mount_id": copy.source.mount_id, "source_frame": copy.source.frame,
                        "filesystem_root": copy.source.identity.filesystem_root,
                        "target_frame": target_frame, "parent_frame": publisher.tree.inputs_frame,
                        "release_sha256": batch.release}
                    flags = gt._OPEN_TREE_CLONE | os.O_CLOEXEC | gt._AT_EMPTY_PATH
                    tree = _syscall(publisher, batch, copy, "open_tree", (source_fd, b"", flags),
                                    dict(details, flags=flags))
                    attributes = gt._MountAttr(gt._MOUNT_ATTRIBUTES, 0, gt._MS_PRIVATE, 0)
                    _syscall(publisher, batch, copy, "mount_setattr",
                        (tree, b"", gt._AT_EMPTY_PATH, ctypes.byref(attributes), ctypes.sizeof(attributes)),
                        dict(details, mount_id=copy.tree_mount_id, attr_set=gt._MOUNT_ATTRIBUTES,
                             propagation=gt._MS_PRIVATE))
                    if (q._frame(os.fstat(parent)) != publisher.tree.inputs_frame
                            or q._frame(os.stat(_INPUTS, follow_symlinks=False)) != publisher.tree.inputs_frame
                            or q._frame(os.fstat(source_fd)) != copy.source.frame
                            or gt._mount_id(batch.read, source_fd, publisher.pid) != copy.source.mount_id
                            or q._frame(os.stat(PurePosixPath(copy.target).name, dir_fd=parent,
                                               follow_symlinks=False)) != target_frame):
                        gt._deny("phase held source/target parent changed before native publication")
                    batch.read.checkpoint()
                    _syscall(publisher, batch, copy, "move_mount", (tree, b"", target_fd, b"", gt._MOVE_EMPTY),
                             dict(details, mount_id=copy.tree_mount_id, flags=gt._MOVE_EMPTY))
                    visible = _visible(batch.read, owner, copy, contents=True)
                    maximum = gt._MAX_GT_BYTES if index == 0 else 1 << 20
                    _hash(batch.read, source_fd, copy.source, maximum)
                    _hash(batch.read, visible, copy.source, maximum)
                    batch.read.close_one(visible)
                _close_trees(publisher, batch)
                _close_read(publisher, batch, batch.read)
                if batch.errors.first_error is not None:
                    batch.errors.raise_failure(None)
                _original(self)
                owner.binding.ledger.require_gt_release(active.scope, active.release)
                gt._record(guard, owner, "gt_broker_phase_inputs_published", {
                    "release_sha256": batch.release, "scope_sha256": hashlib.sha256(batch.scope_bytes).hexdigest(),
                    "copies": [_copy_record(copy) for copy in batch.copies]})
                batch.published = True
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                primary = origin
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_publication_primary", origin, None
                try:
                    _capture(publisher, batch, "phase_publication_primary", error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in batch.captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
            finally:
                try:
                    _close_resources(publisher, batch, batch.read, primary)
                except BaseException as error:
                    publisher.failed = publisher.owner.failed = True
                    origin = error
                    for original in batch.origins:
                        if error is original.failure:
                            origin = original.failure.primary_error
                            break
                    for buffer in batch.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = primary if primary is not None else origin
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_cleanup_dispatch_entry_failure", origin, None
                    # No further helper entry before consuming remaining FDs.
                    for copy in batch.copies:
                        descriptor, copy.tree_fd = copy.tree_fd, None
                        if descriptor is None:
                            continue
                        copy.close_attempted = True
                        try:
                            os.close(descriptor)
                        except BaseException as close_error:
                            for buffer in batch.captures:
                                slot = next(buffer._cursor, None)
                                if slot is None:
                                    buffer.overflowed = True
                                else:
                                    slot.operation, slot.error, slot.descriptor = (
                                        "phase_dispatch_remaining_tree_close", close_error, descriptor)
                        copy.close_details["fd"] = descriptor
                        copy.close_details["mount_id"] = copy.tree_mount_id
                    while batch.read.owned:
                        descriptor = batch.read.owned.pop()
                        try:
                            os.close(descriptor)
                        except BaseException as close_error:
                            for buffer in batch.captures:
                                slot = next(buffer._cursor, None)
                                if slot is None:
                                    buffer.overflowed = True
                                else:
                                    slot.operation, slot.error, slot.descriptor = (
                                        "phase_dispatch_remaining_read_close", close_error, descriptor)
            # Return only after the finally cleanup itself succeeded. A late
            # helper-entry failure must still attempt original mount removal.
            if (primary is None and not publisher.failed and not owner.failed
                    and batch.errors.first_error is None and batch.errors.aggregation_error is None
                    and not batch.errors.overflowed):
                return batch.copies[-1].source.registered if include_control_final_matches else None
            try:
                _remove(publisher, batch)
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_publication_failure_cleanup", origin, None
                try:
                    _capture(publisher, batch, "phase_publication_failure_cleanup", error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in batch.captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
            batch.errors.raise_failure(primary)

    def close(self):
        with gt._LOCK:
            publisher = _original(self, cleanup=True)
            batch = publisher.active
            if batch is None or batch.closed:
                try:
                    gt._deny("phase publisher has no retained once-only original publication")
                except BaseException as error:
                    publisher.failed = publisher.owner.failed = True
                    buffers = publisher.captures if batch is None else batch.captures
                    origin = error
                    for original in publisher.origins if batch is None else batch.origins:
                        if error is original.failure:
                            origin = original.failure.primary_error
                            break
                    for buffer in buffers:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = origin
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_unpublication_refused", origin, None
                    try:
                        _capture(publisher, batch, "phase_unpublication_refused", error)
                    except BaseException as report_error:
                        raw_report_error = report_error
                        for original_capture in publisher.origins if batch is None else batch.origins:
                            if report_error is original_capture.failure:
                                raw_report_error = original_capture.failure.primary_error
                                break
                        for buffer in buffers:
                            buffer.aggregation_error = raw_report_error
                            slot = next(buffer._cursor, None)
                            if slot is None:
                                buffer.overflowed = True
                            else:
                                slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
                    publisher.owner.failure_errors.raise_failure(origin)
            primary = None
            try:
                _children_absent(publisher)
                try:
                    _close_resources(publisher, batch, batch.read)
                except BaseException as error:
                    publisher.failed = publisher.owner.failed = True
                    origin = error
                    for original in batch.origins:
                        if error is original.failure:
                            origin = original.failure.primary_error
                            break
                    for buffer in batch.captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = origin
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_cleanup_dispatch_entry_failure", origin, None
                    for copy in batch.copies:
                        descriptor, copy.tree_fd = copy.tree_fd, None
                        if descriptor is None:
                            continue
                        copy.close_attempted = True
                        try:
                            os.close(descriptor)
                        except BaseException as close_error:
                            for buffer in batch.captures:
                                slot = next(buffer._cursor, None)
                                if slot is None:
                                    buffer.overflowed = True
                                else:
                                    slot.operation, slot.error, slot.descriptor = (
                                        "phase_dispatch_remaining_tree_close", close_error, descriptor)
                        copy.close_details["fd"] = descriptor
                        copy.close_details["mount_id"] = copy.tree_mount_id
                    while batch.read.owned:
                        descriptor = batch.read.owned.pop()
                        try:
                            os.close(descriptor)
                        except BaseException as close_error:
                            for buffer in batch.captures:
                                slot = next(buffer._cursor, None)
                                if slot is None:
                                    buffer.overflowed = True
                                else:
                                    slot.operation, slot.error, slot.descriptor = (
                                        "phase_dispatch_remaining_read_close", close_error, descriptor)
                _remove(publisher, batch)
                if publisher.failed or batch.errors.first_error is not None:
                    batch.errors.raise_failure(None)
                _original(self)
                gt._record(publisher.guard(), publisher.owner, "gt_broker_phase_inputs_unpublished", {
                    "release_sha256": batch.release, "copies": [_copy_record(copy) for copy in batch.copies]})
                batch.closed = True
                publisher.active = None
            except BaseException as error:
                publisher.failed = publisher.owner.failed = True
                origin = error
                for original in batch.origins:
                    if error is original.failure:
                        origin = original.failure.primary_error
                        break
                primary = origin
                for buffer in batch.captures:
                    if buffer.failure.primary_error is None:
                        buffer.failure.primary_error = origin
                    if buffer.first_error is None:
                        buffer.first_error = origin
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_unpublication_primary", origin, None
                try:
                    _capture(publisher, batch, "phase_unpublication_primary", error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in publisher.origins if batch is None else batch.origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in batch.captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
            if primary is not None:
                batch.errors.raise_failure(primary)


def _install_original_phase_input_publisher(guard, broker):
    """One-shot private owner; no public result or native-ready bool is accepted."""
    with gt._LOCK:
        owner = gt._OWNERS.get(guard) if type(guard) is BudgetGuard else None
        if (owner is None or owner.broker is not broker or type(broker) is not gt.LinuxNativeGTBroker
                or gt._broker_guard(broker) is not guard or not owner.installed or owner.failed
                or owner.phase_publisher is not None or owner.mount_api is None):
            gt._deny("phase publisher requires the healthy original once-only installed GT broker")
        gt._live(guard, owner)
        gt._libc(guard, owner)  # Never first-load or install a helper here.
        # Original shared slots and this read's own slots precede construction
        # and every descriptor acquisition. The private owner retains the read.
        read = q._ReadScope()
        captures = (owner.failure_errors,)
        origins = (read.failures, owner.failure_errors)
        handle = publisher = None
        primary = None
        try:
            handle = object.__new__(_OriginalPhaseInputPublisher)
            publisher = _Publisher(weakref.ref(guard), owner, handle, owner.binding,
                os.getpid(), threading.current_thread(), read, captures=captures, origins=origins)
            owner.phase_publisher = publisher
            _PUBLISHERS[handle] = publisher
            stop_ns, _ = _budget(publisher)
            read.deadline = min(read.deadline, stop_ns)
            _children_absent(publisher)
            gt._kernel_identity(read, owner)
            publisher.tree, _ = _tree(read, owner)
        except BaseException as error:
            owner.failed = True
            if publisher is not None:
                publisher.failed = True
            origin = error
            for original in origins:
                if error is original.failure:
                    origin = original.failure.primary_error
                    break
            primary = origin
            for buffer in captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = origin
                if buffer.first_error is None:
                    buffer.first_error = origin
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_publisher_installation", origin, None
            if publisher is not None:
                try:
                    _capture(publisher, None, "phase_publisher_installation", error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        finally:
            if publisher is not None:
                try:
                    _close_read(publisher, None, read, primary)
                except BaseException as error:
                    publisher.failed = owner.failed = True
                    origin = error
                    for original in origins:
                        if error is original.failure:
                            origin = original.failure.primary_error
                            break
                    if primary is None:
                        primary = origin
                    for buffer in captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = primary
                        if buffer.first_error is None:
                            buffer.first_error = origin
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_install_read_cleanup_entry_failure", origin, None
            while read.owned:
                descriptor = read.owned.pop()
                try:
                    os.close(descriptor)
                except BaseException as error:
                    owner.failed = True
                    if publisher is not None:
                        publisher.failed = True
                    if primary is None:
                        primary = error
                    for buffer in captures:
                        if buffer.failure.primary_error is None:
                            buffer.failure.primary_error = primary
                        if buffer.first_error is None:
                            buffer.first_error = error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_install_remaining_read_close", error, descriptor
        try:
            if (primary is None and publisher is not None and not publisher.failed and not owner.failed
                    and not read.owned and all(buffer.first_error is None
                        and buffer.failure.primary_error is None and buffer.aggregation_error is None
                        and not buffer.overflowed for buffer in origins)):
                gt._record(guard, owner, "gt_broker_phase_publisher_registered", {
                    "tree": asdict(publisher.tree), "targets": list(_TARGETS),
                    "phase_tree_creation_deletion_history": "NOT_ATTESTED"})
                publisher.installed = True
                return handle
        except BaseException as error:
            owner.failed = True
            if publisher is not None:
                publisher.failed = True
            origin = error
            for original in origins:
                if error is original.failure:
                    origin = original.failure.primary_error
                    break
            if primary is None:
                primary = origin
            for buffer in captures:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = primary
                if buffer.first_error is None:
                    buffer.first_error = origin
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_publisher_registration", origin, None
            if publisher is not None:
                try:
                    _capture(publisher, None, "phase_publisher_registration", error)
                except BaseException as report_error:
                    raw_report_error = report_error
                    for original_capture in origins:
                        if report_error is original_capture.failure:
                            raw_report_error = original_capture.failure.primary_error
                            break
                    for buffer in captures:
                        buffer.aggregation_error = raw_report_error
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_capture_entry_failure", raw_report_error, None
        owner.failure_errors.raise_failure(primary)


def _copy_snapshot(copy):
    return (copy.target, copy.source, copy.tree_fd, copy.tree_mount_id, copy.installed_mount_id,
        copy.open_attempted, copy.setattr_attempted, copy.move_attempted, copy.move_succeeded,
        copy.close_attempted, copy.remove_attempted, copy.removed, copy.absence_verified)


def _copy_record(copy):
    # Durable bytes describe the retained original slots; callers never supply
    # this record and reconstructing it cannot install a publisher/issuance.
    return {"target": copy.target, "source": asdict(copy.source) if copy.source is not None else None,
        "tree_mount_id": copy.tree_mount_id, "installed_mount_id": copy.installed_mount_id,
        "open_attempted": copy.open_attempted, "setattr_attempted": copy.setattr_attempted,
        "move_attempted": copy.move_attempted, "move_succeeded": copy.move_succeeded,
        "tree_close_attempted": copy.close_attempted, "remove_attempted": copy.remove_attempted,
        "removed": copy.removed, "absence_verified": copy.absence_verified}


def _snapshot(owner):
    from . import linux_child_launch as children
    from .linux_phase_runner import _transaction_snapshot

    publisher = owner.phase_publisher
    key = owner.commitment_key
    # This is a process-private continuity tuple, never a durable/public secret
    # serialization. Retain actual raw/error/capture identities, not receipts.
    key_snapshot = (key, key.producer, key.producer_module, key.producer_type, key.flags,
        key.owner, key.publisher, key.binding, key.phase, key.terminal, key.ledger, key.pins,
        key.pid, key.thread, key.batch, key.grant, key.scope_bytes, key.release,
        key.stop_ns, key.cleanup_ns, key.clock, key.attempt_consumed,
        key.python_call_attempted, key.python_call_returned, key.raw, key.raw_length,
        key.secret_sha256, key.return_validated, key.started_ns, key.call_started_ns,
        key.call_returned_ns, key.finished_ns, key.started_sha256, key.finished_sha256,
        _canonical(key.started_body), _canonical(key.finished_body), key.operation,
        key.primary_error, key.secondary_error, key.report_origin, key.secondary_origin,
        key.ready, key.failed, key.captures, key.origins,
        tuple((buffer, buffer.failure, buffer.failure.primary_error, buffer.first_error,
            buffer.aggregation_error, buffer.overflowed)
              for buffer in key.origins))
    if publisher is None:
        return (None, key_snapshot, _transaction_snapshot(owner))
    return (publisher, publisher.tree, publisher.installed, publisher.failed, publisher.active,
        key_snapshot, _transaction_snapshot(owner),
        publisher.read, tuple(publisher.read.owned), publisher.read.failures.first_error,
        publisher.read.failures.failure.primary_error, publisher.read.failures.aggregation_error,
        publisher.read.failures.overflowed,
        tuple((batch, batch.grant, batch.scope_bytes, batch.release, batch.stop_ns, batch.cleanup_ns,
            tuple(_copy_snapshot(copy) for copy in batch.copies), tuple(batch.read.owned),
            tuple(batch.cleanup_read.owned), batch.published, batch.closed,
            batch.errors.first_error, batch.errors.aggregation_error, batch.errors.overflowed,
            batch.clock, batch.commitment_key, batch.failed, batch.outcome,
            batch.outcome_consumed, children._retained_batch_snapshot(batch))
              for batch in publisher.batches))


def _require_closed(owner):
    from . import linux_child_launch as children

    publisher = owner.phase_publisher
    key = _require_commitment_history(owner, publisher)
    if publisher is None:
        return
    if (type(publisher) is not _Publisher or _PUBLISHERS.get(publisher.handle) is not publisher
            or publisher.owner is not owner or publisher.binding is not owner.binding
            or publisher.failed or not publisher.installed or type(publisher.tree) is not _Tree
            or publisher.active is not None or type(publisher.read) is not q._ReadScope
            or publisher.read.owned or publisher.read.failures.first_error is not None
            or publisher.read.failures.failure.primary_error is not None
            or publisher.read.failures.aggregation_error is not None or publisher.read.failures.overflowed):
        gt._deny("original closure rejects an absent, active or failed private phase publisher")
    for batch in publisher.batches:
        if (not batch.closed or not batch.published or batch.failed or batch.commitment_key is not key
                or batch.read.owned or batch.cleanup_read.owned
                or not 1 <= len(batch.copies) <= 2 or batch.errors.first_error is not None
                or batch.errors.overflowed or batch.errors.aggregation_error is not None
                or type(batch.grant) is not gt._Grant or batch.scope_bytes != batch.grant.scope_bytes
                or _canonical(asdict(batch.grant.scope)) != batch.scope_bytes
                or batch.release != batch.grant.release
                or batch.copies[0].target != _TARGETS[0]
                or (len(batch.copies) == 2 and (batch.copies[1].target != _TARGETS[1]
                    or batch.grant.scope.stage is not StudyStage.OUTER_EVALUATION))
                or any(copy.tree_fd is not None or not copy.removed or not copy.absence_verified
                       or not copy.open_attempted or not copy.setattr_attempted or not copy.move_succeeded
                       or not copy.close_attempted or not copy.remove_attempted or copy.source is None
                       or copy.tree_mount_id not in owner.issued_ids
                       or copy.installed_mount_id not in owner.issued_ids for copy in batch.copies)):
            gt._deny("original history retains an open, failed or unrecorded phase-copy issuance")
        children._require_retired_phase_batch(publisher, batch)


def _closure_additions(owner):
    identities, ids = [], []
    publisher = owner.phase_publisher
    paths = ()
    if publisher is not None:
        paths = (_ROOT, _INPUTS)
        if publisher.tree is not None:
            for target, frame in publisher.tree.targets:
                relative = PurePosixPath(target).relative_to(_ROOT)
                identities.append(gt._GTIdentity(target, str(PurePosixPath(publisher.tree.filesystem_root) / relative),
                    frame[0], frame[1], frame[2], frame[3], frame[5]))
        for batch in publisher.batches:
            for copy in batch.copies:
                if copy.source is not None and copy.source.registered is not None:
                    if copy.source.identity not in identities:
                        identities.append(copy.source.identity)
                for value in (copy.tree_mount_id, copy.installed_mount_id):
                    if value is not None and value not in ids:
                        ids.append(value)
    return tuple(identities), _TARGETS, tuple(ids), paths


__all__ = []
