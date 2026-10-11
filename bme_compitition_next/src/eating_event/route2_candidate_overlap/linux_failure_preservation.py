"""Durable failure marker on a separately capped controller filesystem.

Preserves the original attempt and artifacts in place. This is not successful
teardown, quiescence, a terminal result, or permission to retry the study.
No GT bytes are opened and no image/ledger/lock is removed or moved.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

from .contracts import STUDY_ID

_CONTROL_ROOT = "/var/lib/route2-controller"
_FAILURE_ROOT = _CONTROL_ROOT + "/failures"
_MAX_RECEIPT_BYTES = 16384
_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def _close_all(owned):
    errors = []
    for descriptor in owned:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
    return tuple(errors)


def _report(primary, cleanup, *, wall=False, created=False):
    cause = primary
    if isinstance(primary, FailurePreservationError):
        cleanup = primary.cleanup_errors + tuple(cleanup)
        primary = primary.primary_error
    error = FailurePreservationError(primary, tuple(cleanup), wall, created)
    raise error from cause


def _directory(path: str) -> int:
    """Walk held no-follow ancestors; each acquired fd is closed at most once."""
    if PurePosixPath(path).as_posix() != path or ".." in PurePosixPath(path).parts:
        raise PermissionError("failure receipt path is not canonical")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    owned = []
    primary = None
    try:
        held = os.open("/", flags)
        owned.append(held)
        for component in PurePosixPath(path).parts[1:]:
            next_fd = os.open(component, flags, dir_fd=held)
            owned.append(next_fd)
            info = os.fstat(next_fd)
            if info.st_uid != 0 or info.st_mode & 0o022 or not stat.S_ISDIR(info.st_mode):
                raise PermissionError("failure receipt ancestor is not protected")
            owned.remove(held)  # consume before close; never retry a failed Linux close
            previous, held = held, next_fd
            os.close(previous)
        owned.remove(held)
        return held
    except BaseException as exc:
        primary = exc
    cleanup = _close_all(reversed(owned))
    _report(primary, cleanup)


def capture_failure_control_boundary(cap: int) -> tuple:
    """Capture the real capped control mount with bounded native metadata."""
    if os.name != "posix" or os.geteuid() != 0 or type(cap) is not int or cap <= 0:
        raise PermissionError("failure control boundary requires root Linux and explicit capacity")
    held = None
    primary = None
    result = None
    try:
        held = _directory(_FAILURE_ROOT)
        capacity = os.fstatvfs(held)
        with Path("/proc/self/mountinfo").open("r", encoding="utf-8") as stream:
            text = stream.read((4 << 20) + 1)
        if len(text) > 4 << 20:
            raise PermissionError("failure control mountinfo exceeds its bound")
        covering = []
        for line in text.splitlines():
            left, sep, right = line.partition(" - ")
            fields, tail = left.split(), right.split()
            if not sep or len(fields) < 6 or len(tail) < 3 or not fields[0].isdecimal():
                raise PermissionError("failure control mountinfo is malformed")
            point = fields[4]
            if point == _FAILURE_ROOT or _FAILURE_ROOT.startswith(point.rstrip("/") + "/"):
                covering.append((fields, tail))
        if not covering:
            raise PermissionError("failure control mount is absent")
        longest = max(len(fields[4]) for fields, _ in covering)
        selected = [(fields, tail) for fields, tail in covering if len(fields[4]) == longest]
        if len(selected) != 1:
            raise PermissionError("failure control mount is stacked or ambiguous")
        fields, tail = selected[0]
        options = set(fields[5].split(","))
        info = os.fstat(held)
        kernel = ctypes.CDLL(None, use_errno=True)
        kernel.fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
        kernel.fstatfs.restype = ctypes.c_int
        fs_type = ctypes.create_string_buffer(256)
        if kernel.fstatfs(held, fs_type) != 0:
            raise OSError(ctypes.get_errno(), "failure control fstatfs failed")
        device = f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
        size = capacity.f_blocks * capacity.f_frsize
        if (fields[4] != _CONTROL_ROOT or fields[3] != "/" or tail[0] != "ext4"
                or ctypes.c_long.from_buffer(fs_type).value != 0xEF53 or fields[2] != device
                or not {"rw", "nosuid", "nodev", "noexec"}.issubset(options)
                or any(item.startswith("shared:") for item in fields[6:]) or not 0 < size <= cap):
            raise PermissionError("held failure control mount is not a capped private ext4 filesystem")
        result = (int(fields[0]), device, tail[1], size, info.st_dev, info.st_ino,
                  info.st_mode, info.st_uid, info.st_gid)
    except BaseException as exc:
        primary = exc
    cleanup = _close_all((held,))
    if primary is not None or cleanup:
        _report(primary, cleanup)
    return result


def preserve_owned_failure(controller, failure_phase: str, failure_kind: str) -> dict:
    """Consume the original assembly's abort into one create-only marker.

    Called by its concrete OS port after abort_startup consumed the attempt.
    A missing installed write-boundary gate still blocks before any write.
    The marker records incomplete teardown explicitly, even when saving works.
    """
    from .linux_production_controller import _ASSEMBLIES
    import threading
    state = _ASSEMBLIES.get(controller)
    if (os.name != "posix" or os.geteuid() != 0 or state is None
            or state.pid != os.getpid() or state.thread is not threading.current_thread()
            or not state.abort_attempted or not state.failed or state.policy is None
            or state.policy_bytes is None or state.unit_observation is None
            or state.failure_preservation_attempted or state.control_mount_identity is None):
        raise PermissionError("failure preservation lacks original installed write-boundary ownership")
    state.failure_preservation_attempted = True
    for value in (failure_phase, failure_kind, state.invocation_id):
        if type(value) is not str or not _SAFE.fullmatch(value):
            raise PermissionError("failure marker contains an unsafe identity")
    deadline = state.started_ns + state.limits.total_wall_ns
    if time.monotonic_ns() >= deadline:
        raise TimeoutError("failure marker cannot start outside the original total wall")
    cap = state.policy["guest_control_cap_bytes"]
    if type(cap) is not int or cap <= 0:
        raise PermissionError("failure marker has no approved control capacity")
    from .linux_deadline import _TIMERS
    timer = _TIMERS.get(state.total_timer)
    if (timer is None or timer.consumed or not timer.armed or not state.total_timer_armed or timer.pid != state.pid
            or timer.thread is not state.thread or state.envelope is None
            or timer.deadline_ns != state.started_ns + state.envelope.runtime_max_ns):
        raise PermissionError("failure preservation requires the original successfully armed kernel deadline")
    deadline = min(deadline, timer.deadline_ns)

    def within_wall():
        if time.monotonic_ns() >= deadline:
            raise TimeoutError("failure preservation reached its original kernel wall deadline")

    within_wall()
    parent = None
    descriptor = None
    created = False
    primary = None
    cleanup = []
    name = STUDY_ID + "." + state.invocation_id + ".failure.json"
    try:
        parent = _directory(_FAILURE_ROOT)
        within_wall()
        if capture_failure_control_boundary(cap) != state.control_mount_identity:
            raise PermissionError("original capped failure control mount was replaced")
        pinned = os.fstat(parent)
        if (pinned.st_dev, pinned.st_ino) != state.control_mount_identity[4:6]:
            raise PermissionError("held failure receipt directory differs from original boundary")
        body = dict(schema="route2_failure_preservation_v1", study_id=STUDY_ID,
                    invocation_id=state.invocation_id, failure_phase=failure_phase,
                    failure_kind=failure_kind, controller_pid=state.pid,
                    invocation_started_monotonic_ns=state.started_ns,
                    observed_monotonic_ns=time.monotonic_ns(),
                    production_policy_sha256=hashlib.sha256(state.policy_bytes).hexdigest(),
                    budget_policy_sha256=state.limits.digest(),
                    artifacts="PRESERVED_IN_PLACE_NO_RETRY",
                    worker_teardown="NOT_ATTESTED", gt_revocation="NOT_ATTESTED",
                    terminal_acceptance=False, experiment_authorization_issued=False)
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(encoded) > min(cap, _MAX_RECEIPT_BYTES):
            raise PermissionError("failure marker exceeds its bounded payload")
        within_wall()
        descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                             0o600, dir_fd=parent)
        created = True
        info = os.fstat(descriptor)
        if info.st_dev != os.fstat(parent).st_dev or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PermissionError("failure marker escaped its held control directory")
        # Persist an empty create-only tombstone before payload I/O. A later
        # ENOSPC/interruption cannot turn this consumed attempt into a retry.
        within_wall()
        os.fsync(descriptor)
        within_wall()
        os.fsync(parent)
        offset = 0
        while offset < len(encoded):
            within_wall()
            count = os.write(descriptor, encoded[offset:])
            if count <= 0:
                raise OSError("failure marker short write")
            offset += count
        if os.fstat(descriptor).st_size != len(encoded) or os.pread(descriptor, len(encoded) + 1, 0) != encoded:
            raise PermissionError("failure marker did not read back as the exact bounded payload")
        within_wall()
        os.fsync(descriptor)
        within_wall()
        os.fsync(parent)
        if capture_failure_control_boundary(cap) != state.control_mount_identity:
            raise PermissionError("failure control boundary changed during marker persistence")
        result = dict(body, receipt_sha256=hashlib.sha256(encoded).hexdigest(),
                      marker_path=_FAILURE_ROOT + "/" + name, marker_fsynced=True)
    except BaseException as exc:
        primary = exc
    finally:
        # Failed/partial markers are deliberately retained as tombstones.
        cleanup = _close_all((descriptor, parent))
        exceeded = time.monotonic_ns() >= deadline
    if primary is not None or cleanup or exceeded or not created:
        _report(primary, cleanup, wall=exceeded, created=created)
    return result


class FailurePreservationError(RuntimeError):
    """Preserve primary/cleanup errors and the final wall classification."""

    def __init__(self, primary, cleanup_errors, wall_exceeded, marker_created):
        super().__init__("failure preservation denied after accounting for descriptor cleanup")
        self.primary_error = primary
        self.cleanup_errors = cleanup_errors
        self.wall_exceeded = wall_exceeded
        self.marker_created = marker_created


class StartupPreservedWithoutTeardown(PermissionError):
    """A saved marker cannot satisfy the complete StartupAbortReceipt contract."""

    def __init__(self, receipt):
        super().__init__("startup artifacts preserved; worker/GT/detach quarantine proof remains incomplete")
        self.preservation_receipt = receipt
