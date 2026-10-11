"""Expansion only: one existing ext4 loop image, exactly 2 -> 4 GiB.

This is an OS primitive, not a ResourceEnforcer or a complete SupervisorOps.
It never creates an image, filesystem, mount, study ledger, or study lock.
It authenticates protected external policy/seal bytes and replays the protected
ledger before any write. OS ports are replaceable for synthetic tests; replacing
them is a trusted-controller operation, never an approval capability.

The installed controller must provision the protected attempt directory, keep
worker launches serialized with the existing study lock, and own its mount and
cgroup namespaces. A durable attempt is never removed, including after failure.
The caller must durably append the returned expansion receipt before Stage B.
Snapshot bootstrap, creation, full enforcement, and controller assembly remain
separate admission requirements; this component does not establish admission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import struct
import subprocess
import threading
import time
import uuid

from .admission_bootstrap import (
    DEFAULT_SUPERVISOR_CONFIG, MAX_CONTROLLER_KEY_BYTES,
    MAX_SEALED_ADMISSION_BYTES, MAX_SUPERVISOR_CONFIG_BYTES,
    _read_protected_file, _require_frozen_bindings, parse_supervisor_config,
)
from .budget import (
    BudgetLimits, DurableEventReceipt, EnforcementReceipt, ResourceSnapshot,
    StageBProjection, _canonical, _projection_call_role_ids,
    require_precreate_order, require_stage_b_entry, require_two_layer_startup_free,
    require_fixed_native_budget, STAGE_A_CAPACITY_UPPER_BOUND_V2,
    stage_a_projection_disk_bytes,
    nested_backing_from_payload, nested_backing_identity, require_stage_filesystem,
)
from .contracts import FrozenAdmission, STUDY_ID
from .external_admission import load_controller_sealed_admission
from .linux_supervisor import ImageVolumeReceipt
from .linux_volume_artifacts import CHUNK_BYTES, HeldTreatmentArtifacts
from .stage_a_replay import MAX_ROLE_REGISTRY_BYTES, replay_stage_a


GIB = 1 << 30
MAX_LEDGER_BYTES = 16 << 20
MAX_KERNEL_TEXT_BYTES = 4 << 20
MAX_COMMAND_SECONDS = 60
ATTEMPT_ROOT = "/var/lib/route2-controller/volume-expansion-attempts"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Linux UAPI loop.h and fs.h; supported production ABI is Linux 64 bit.
LOOP_GET_STATUS64 = 0x4C05
LOOP_SET_CAPACITY = 0x4C07
BLKGETSIZE64 = 0x80081272
_LOOP_INFO = struct.Struct("=5Q4I64s64s32s2Q")


def _path(value: object) -> str:
    if type(value) is not str:
        raise PermissionError("volume path must be canonical Linux text")
    parsed = PurePosixPath(value)
    if (not parsed.is_absolute() or parsed.as_posix() != value
            or ".." in parsed.parts or any(ch.isspace() or ord(ch) < 32 for ch in value)):
        raise PermissionError("volume path must be canonical and absolute")
    return value


def _identity(info) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_rdev


def _device(value: int) -> str:
    # Linux dev_t encoding, also usable with synthetic Linux stat on Windows.
    major = ((value >> 8) & 0xfff) | ((value >> 32) & 0xfffff000)
    minor = (value & 0xff) | ((value >> 12) & 0xffffff00)
    return f"{major}:{minor}"


def _digest_matches(value: object, expected: str) -> bool:
    return (type(value) is str and _SHA256.fullmatch(value.lower()) is not None
            and value.lower() == expected.lower())


def _require_protected_stat(info, kind: str) -> None:
    predicates = {"file": stat.S_ISREG, "directory": stat.S_ISDIR, "block": stat.S_ISBLK}
    if (kind not in predicates or not predicates[kind](info.st_mode)
            or info.st_uid != 0 or info.st_mode & stat.S_IWOTH
            or (kind != "block" and info.st_mode & stat.S_IWGRP)
            or (kind == "file" and (info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077))):
        raise PermissionError("volume object is linked, mutable by workers, or not root-owned")


def _close_temporary_fds(owned: list[int]) -> None:
    """Consume ownership before each close; attempt every FD without retry."""
    failure = None
    while owned:
        descriptor = owned.pop()
        try:
            os.close(descriptor)
        except BaseException as exc:
            failure = failure or exc
    if failure is not None:
        raise failure


@dataclass(frozen=True, slots=True)
class LoopState:
    backing_device: int
    backing_inode: int
    number: int
    offset: int
    sizelimit: int
    flags: int
    capacity_bytes: int


class LinuxVolumeOSPorts:
    """Concrete Linux syscalls; synthetic tests replace only this OS boundary."""

    def require_linux_root(self) -> None:
        if (platform.system() != "Linux" or getattr(os, "geteuid", lambda: -1)() != 0
                or struct.calcsize("P") != 8):
            raise PermissionError("volume expansion requires the installed 64-bit Linux root controller")

    def read_protected_file(self, path, *, max_bytes: int) -> bytes:
        return _read_protected_file(path, max_bytes=max_bytes)

    def _open_directory(self, path: str) -> int:
        _path(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        descriptor = os.open("/", flags)
        owned = [descriptor]
        try:
            _require_protected_stat(os.fstat(descriptor), "directory")
            for part in PurePosixPath(path).parts[1:]:
                following = os.open(part, flags, dir_fd=descriptor)
                owned.append(following)
                # Own the new FD before retiring the previous one. A close
                # error may mean the retired number is already released.
                retired = owned.pop(0)
                descriptor = following
                os.close(retired)
                _require_protected_stat(os.fstat(descriptor), "directory")
            return owned.pop()  # Transfer only on complete walk success.
        finally:
            _close_temporary_fds(owned)

    def open_existing(self, path: str, *, kind: str, writable: bool = False) -> int:
        parsed = PurePosixPath(_path(path))
        if kind == "directory":
            if writable:
                raise PermissionError("directory descriptors must be read-only")
            return self._open_directory(path)
        parent = self._open_directory(str(parsed.parent))
        owned = [parent]
        try:
            flags = (os.O_RDWR if writable else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            descriptor = os.open(parsed.name, flags, dir_fd=parent)
            owned.append(descriptor)
            _require_protected_stat(os.fstat(descriptor), kind)
            # Parent release is part of success. If it fails, the unreturned
            # artifact FD remains owned here and must also be closed.
            retired = owned.pop(0)
            os.close(retired)
            return owned.pop()
        finally:
            _close_temporary_fds(owned)

    def path_stat(self, path: str, *, kind: str):
        descriptor = self.open_existing(path, kind=kind)
        try:
            return os.fstat(descriptor)
        finally:
            os.close(descriptor)

    def fstat(self, descriptor: int):
        return os.fstat(descriptor)

    def read_fd(self, descriptor: int, *, max_bytes: int) -> bytes:
        before = os.fstat(descriptor)
        if before.st_size > max_bytes or before.st_size <= 0:
            raise PermissionError("protected ledger is empty or exceeds the fixed byte bound")
        chunks = []
        offset = 0
        while offset < before.st_size:
            chunk = os.pread(descriptor, min(65536, before.st_size - offset), offset)
            if not chunk:
                raise PermissionError("protected ledger read is incomplete")
            chunks.append(chunk)
            offset += len(chunk)
        after = os.fstat(descriptor)
        if (_identity(before), before.st_size, before.st_mtime_ns) != (
                _identity(after), after.st_size, after.st_mtime_ns):
            raise PermissionError("protected ledger changed while being read")
        return b"".join(chunks)

    def lock_exclusive(self, descriptor: int) -> None:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def rewind_fd(self, descriptor: int) -> None:
        if os.lseek(descriptor, 0, os.SEEK_SET) != 0:
            raise PermissionError("candidate artifact descriptor cannot be rewound")

    def read_chunk(self, descriptor: int, *, max_bytes: int) -> bytes:
        if type(max_bytes) is not int or not 0 < max_bytes <= CHUNK_BYTES:
            raise PermissionError("candidate artifact read exceeds the fixed streaming block bound")
        return os.read(descriptor, max_bytes)

    def close(self, descriptor: int) -> None:
        os.close(descriptor)

    def fsync(self, descriptor: int) -> None:
        os.fsync(descriptor)

    def fsync_parent(self, path: str) -> None:
        descriptor = self._open_directory(str(PurePosixPath(_path(path)).parent))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _kernel_text(self, path: Path) -> str:
        with path.open("rb") as stream:
            encoded = stream.read(MAX_KERNEL_TEXT_BYTES + 1)
        if len(encoded) > MAX_KERNEL_TEXT_BYTES:
            raise PermissionError("kernel evidence exceeds its fixed byte bound")
        return encoded.decode("utf-8", errors="strict")

    def mountinfo(self) -> str:
        return self._kernel_text(Path("/proc/self/mountinfo"))

    def filesystem_capacity(self, descriptor: int) -> int:
        info = os.fstatvfs(descriptor)
        return info.f_blocks * info.f_frsize

    def loop_state(self, descriptor: int) -> LoopState:
        import fcntl
        status = fcntl.ioctl(descriptor, LOOP_GET_STATUS64, bytes(_LOOP_INFO.size))
        values = _LOOP_INFO.unpack(status)
        capacity = struct.unpack("=Q", fcntl.ioctl(descriptor, BLKGETSIZE64, bytes(8)))[0]
        if values[6] != 0 or values[7] != 0:
            raise PermissionError("encrypted loop devices are outside the expansion primitive")
        return LoopState(values[0], values[1], values[5], values[3], values[4], values[8], capacity)

    def filesystem_uuid(self, descriptor: int) -> str:
        superblock = os.pread(descriptor, 1024, 1024)
        if len(superblock) != 1024 or struct.unpack_from("<H", superblock, 56)[0] != 0xEF53:
            raise PermissionError("loop filesystem lacks the ext superblock signature")
        return str(uuid.UUID(bytes=superblock[104:120]))

    def cgroup_members(self, cgroup_path: str) -> tuple[int, ...]:
        path = PurePosixPath(_path(cgroup_path))
        if len(path.parts) < 3 or path.parts[1] != "system.slice":
            raise PermissionError("volume gate lacks its exact study service cgroup")
        root = Path("/sys/fs/cgroup").joinpath(*path.parts[1:])
        pending = [(root, 0)]
        members: set[int] = set()
        count = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if count > 128 or depth > 8 or node.is_symlink() or not node.is_dir():
                raise PermissionError("cgroup tree is linked, absent, or outside the fixed traversal bound")
            for name in ("cgroup.procs", "cgroup.threads"):
                for line in self._kernel_text(node / name).splitlines():
                    if not line.isdecimal() or int(line) <= 0:
                        raise PermissionError("malformed cgroup task membership")
                    members.add(int(line))
            for child in node.iterdir():
                if child.is_symlink():
                    raise PermissionError("cgroup evidence contains a symlink")
                if child.is_dir():
                    pending.append((child, depth + 1))
        return tuple(sorted(members))

    def pid(self) -> int:
        return os.getpid()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def reserve_attempt(self, encoded: bytes, *, forbidden_device: int) -> None:
        """Durably consume the single attempt before touching the image.

        A failed write/fsync deliberately leaves the exclusive marker present.
        The installed controller must provision ATTEMPT_ROOT beforehand.
        """
        if type(forbidden_device) is not int or forbidden_device <= 0:
            raise PermissionError("attempt requires the bound study filesystem device")
        parent = self._open_directory(ATTEMPT_ROOT)
        owned = [parent]
        try:
            if os.fstat(parent).st_dev == forbidden_device:
                raise PermissionError("attempt directory is on the study filesystem")
            descriptor = os.open(
                STUDY_ID + ".attempt", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600, dir_fd=parent,
            )
            owned.append(descriptor)
            # Persist an empty tombstone before payload I/O. A short payload
            # write or later file-fsync failure cannot undo this reservation.
            # Failure of either initial sync remains unresolved durability:
            # propagate it without touching the image or permitting retry.
            os.fsync(descriptor)
            os.fsync(parent)
            if os.write(descriptor, encoded) != len(encoded):
                raise OSError("partial durable expansion attempt write")
            os.fsync(descriptor)
            os.fsync(parent)
        finally:
            _close_temporary_fds(owned)

    def truncate(self, descriptor: int, size: int) -> None:
        if type(size) is not int or size != 4 * GIB:
            raise PermissionError("expansion permits only the fixed 4 GiB target")
        os.ftruncate(descriptor, size)

    def refresh_capacity(self, descriptor: int) -> None:
        import fcntl
        fcntl.ioctl(descriptor, LOOP_SET_CAPACITY, 0)

    def command(self, argv: tuple[str, ...], *, pass_fds: tuple[int, ...], timeout: float) -> str:
        if (type(argv) is not tuple or len(pass_fds) != 1
                or argv != ("/usr/sbin/resize2fs", f"/proc/self/fd/{pass_fds[0]}", "4G")
                or type(timeout) not in (int, float) or not 0 < timeout <= MAX_COMMAND_SECONDS):
            raise PermissionError("volume command differs from the fixed bounded resize argv")
        completed = subprocess.run(
            argv, check=True, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            pass_fds=pass_fds, timeout=timeout,
            env={"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        return completed.stdout


def _ledger_entries(encoded: bytes) -> tuple[dict, ...]:
    """Replay the same canonical envelope/sequence/hash format as budget.py."""
    if type(encoded) is not bytes or not encoded or len(encoded) > MAX_LEDGER_BYTES or not encoded.endswith(b"\n"):
        raise PermissionError("durable gate ledger is absent, oversized or incomplete")
    previous = "0" * 64
    entries = []
    try:
        for seq, raw in enumerate(encoded.splitlines(keepends=True)):
            value = json.loads(raw)
            if type(value) is not dict or set(value) != {"entry", "sha256"} or _canonical(value) + b"\n" != raw:
                raise ValueError("noncanonical ledger envelope")
            entry = value["entry"]
            if (type(entry) is not dict or set(entry) != {"seq", "event", "payload", "previous_sha256"}
                    or type(entry["seq"]) is not int or entry["seq"] != seq
                    or entry["previous_sha256"] != previous or type(entry["event"]) is not str
                    or not entry["event"] or type(entry["payload"]) is not dict
                    or value["sha256"] != hashlib.sha256(_canonical(entry)).hexdigest()):
                raise ValueError("invalid ledger event chain")
            entries.append({**entry, "sha256": value["sha256"]})
            previous = value["sha256"]
    except (ValueError, TypeError, UnicodeError, RecursionError, KeyError) as exc:
        raise PermissionError("protected Stage B gate ledger cannot be verified") from exc
    return tuple(entries)


def _record(cls, payload: object):
    if type(payload) is not dict or set(payload) != {item.name for item in fields(cls)}:
        raise PermissionError("gate has incomplete typed resource evidence")
    normalized = dict(payload)
    nested_name = "precreate_nested_backing" if cls is EnforcementReceipt else "nested_backing" if cls is ResourceSnapshot else None
    if nested_name is not None:
        normalized[nested_name] = nested_backing_from_payload(normalized[nested_name])
    if cls is EnforcementReceipt:
        if type(normalized["covered_write_volumes"]) is not list:
            raise PermissionError("gate covered-write-volume evidence is malformed")
        normalized["covered_write_volumes"] = tuple(normalized["covered_write_volumes"])
    try:
        return cls(**normalized)
    except (ValueError, TypeError) as exc:
        raise PermissionError("gate has invalid typed resource evidence") from exc


class LinuxLoopVolumeExpander:
    """Authenticate and expand once; default construction performs no OS work."""

    def __init__(self, *, ports: LinuxVolumeOSPorts | None = None, role_registry_bytes: bytes | None = None):
        self._ports = ports if ports is not None else LinuxVolumeOSPorts()
        # Metadata delivery through the approved RO path map remains a separate
        # controller assembly step. Bytes alone are not a capability: _gate
        # verifies them against the external HMAC-sealed FrozenAdmission pin.
        self._role_registry_bytes = role_registry_bytes
        self._lock = threading.Lock()
        self._attempted = False
        self.entry_receipt: DurableEventReceipt | None = None

    def _admission(self) -> tuple[FrozenAdmission, tuple[bytes, bytes, bytes]]:
        ports = self._ports
        config_bytes = ports.read_protected_file(DEFAULT_SUPERVISOR_CONFIG, max_bytes=MAX_SUPERVISOR_CONFIG_BYTES)
        config = parse_supervisor_config(config_bytes)
        key = ports.read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
        seal = ports.read_protected_file(config.sealed_admission_path, max_bytes=MAX_SEALED_ADMISSION_BYTES)
        frozen = load_controller_sealed_admission(
            seal, controller_key=key, expected_source_snapshot_sha256=config.source_snapshot_sha256,
            expected_runtime_snapshot_sha256=config.runtime_snapshot_sha256,
            expected_review_id=config.independent_review_id,
            expected_owner_approval_id=config.owner_approval_id,
            expected_authorization_card_sha256=config.authorization_card_sha256,
        )
        _require_frozen_bindings(config, frozen)
        if type(frozen) is not FrozenAdmission:
            raise PermissionError("expansion requires the exact authenticated FrozenAdmission")
        return frozen, (config_bytes, key, seal)

    def _current(self, invocation_id, current, event_sha256, limits, frozen):
        require_fixed_native_budget(limits)
        if not _digest_matches(limits.digest(), frozen.budget_policy_sha256):
            raise PermissionError("expansion requires the complete fixed BudgetLimits and approved policy digest")
        if (type(current) is not ImageVolumeReceipt or type(invocation_id) is not str or not invocation_id
                or current.invocation_id != invocation_id or current.study_id != STUDY_ID
                or type(event_sha256) is not str or not _SHA256.fullmatch(event_sha256)):
            raise PermissionError("expansion lacks exact invocation, study, volume or entry identities")
        for name, expected in (
            ("study_root_path", frozen.study_root_path), ("ledger_path", frozen.budget_ledger_path),
            ("lock_path", frozen.lock_path), ("image_path", frozen.study_image_path),
        ):
            if _path(getattr(current, name)) != expected:
                raise PermissionError("volume path differs from authenticated admission")
        if (any(type(getattr(current, name)) is not int or getattr(current, name) <= 0 for name in
                ("created_monotonic_ns", "image_device", "image_inode", "filesystem_capacity_bytes", "image_length_bytes"))
                or current.image_length_bytes != 2 * GIB or current.filesystem_capacity_bytes > 2 * GIB
                or type(current.loop_device) is not str or not re.fullmatch(r"/dev/loop[0-9]+", current.loop_device)
                or type(current.mount_id) is not str or not current.mount_id.isdecimal()
                or int(current.mount_id) <= 0
                or current.filesystem_device != f"7:{int(current.loop_device[9:])}"):
            raise PermissionError("volume receipt is outside the fixed Stage A image contract")
        try:
            if type(current.filesystem_uuid) is not str or str(uuid.UUID(current.filesystem_uuid)) != current.filesystem_uuid:
                raise ValueError("noncanonical UUID")
        except ValueError as exc:
            raise PermissionError("volume UUID is malformed") from exc

    def _snapshot(self, payload, current, limits, rss):
        snapshot = _record(ResourceSnapshot, payload)
        identities = (
            snapshot.study_mount_id, snapshot.study_device, snapshot.study_fs_uuid,
            snapshot.study_loop_device, snapshot.study_image_path, snapshot.study_image_dev,
            snapshot.study_image_inode, snapshot.study_image_length_bytes,
        )
        if (identities != (current.mount_id, current.filesystem_device, current.filesystem_uuid,
                           current.loop_device, current.image_path, current.image_device,
                           current.image_inode, current.image_length_bytes)
                or snapshot.study_fs_capacity_bytes != current.filesystem_capacity_bytes
                or snapshot.process_tree_rss_bytes > rss or snapshot.compute_workers > limits.worker_limit
                or snapshot.study_disk_peak_bytes > limits.stage_a_disk_bytes):
            raise PermissionError("Stage A resource evidence changed identity or exceeded hard lines")
        stage_a_projection_disk_bytes(snapshot, limits)
        return snapshot

    def _gate(self, encoded, event_sha256, current, limits, frozen, *, broker_registration_bytes=None):
        role_registry_bytes = self._role_registry_bytes
        if (type(role_registry_bytes) is not bytes or not 0 < len(role_registry_bytes) <= MAX_ROLE_REGISTRY_BYTES
                or not _digest_matches(hashlib.sha256(role_registry_bytes).hexdigest(), frozen.role_input_registry_sha256)):
            raise PermissionError("expansion requires role registry bytes bound to authenticated FrozenAdmission")
        entries = _ledger_entries(encoded)
        names = [item["event"] for item in entries]
        for name in ("study_created", "invocation_started", "stage_a_finished", "stage_b_entry_passed"):
            if names.count(name) != 1:
                raise PermissionError("Stage B expansion lacks a unique complete durable gate")
        if (names[:2] != ["study_created", "invocation_started"]
                or names[-2:] != ["stage_a_finished", "stage_b_entry_passed"]
                or entries[-1]["sha256"] != event_sha256):
            raise PermissionError("entry gate is not the exact current ledger tail after Stage A")
        created, start, boundary, entry = (entries[index]["payload"] for index in (0, 1, -2, -1))
        if (created.get("study_id") != STUDY_ID or created.get("approval_record") != frozen.approval_record
                or not _digest_matches(created.get("input_registry_sha256"), frozen.combined_input_registry_sha256)
                or not _digest_matches(created.get("budget_policy_sha256"), limits.digest())
                or _canonical(created.get("limits")) != _canonical(asdict(limits))):
            raise PermissionError("ledger study creation differs from authenticated admission")
        if (set(start) != {"invocation_id", "monotonic_ns", "controller_receipt", "startup_snapshot", "frozen_rss_ceiling_bytes"}
                or start["invocation_id"] != current.invocation_id
                or type(start["monotonic_ns"]) is not int or start["monotonic_ns"] <= 0):
            raise PermissionError("gate lacks protected invocation startup and enforcement evidence")
        enforcement = _record(EnforcementReceipt, start["controller_receipt"])
        enforcement.require_complete()
        rss = start["frozen_rss_ceiling_bytes"]
        if type(rss) is not int or not 0 < rss <= limits.rss_cap_bytes:
            raise PermissionError("frozen RSS ceiling is invalid")
        startup = self._snapshot(start["startup_snapshot"], current, limits, rss)
        if (rss != min(limits.rss_cap_bytes, 3 * startup.available_ram_bytes // 5)
                or not _digest_matches(enforcement.controller_sha256, frozen.resource_controller_sha256)
                or enforcement.study_root != current.study_root_path or enforcement.ledger_path != current.ledger_path
                or enforcement.lock_path != current.lock_path or enforcement.covered_write_volumes != frozen.approved_write_volumes
                or enforcement.invocation_started_monotonic_ns != start["monotonic_ns"]
                or enforcement.image_created_monotonic_ns != current.created_monotonic_ns
                or enforcement.study_fs_uuid != current.filesystem_uuid or enforcement.study_loop_device != current.loop_device
                or enforcement.study_image_path != current.image_path or enforcement.study_image_dev != current.image_device
                or enforcement.study_image_inode != current.image_inode or enforcement.study_image_length_bytes != 2 * GIB
                or enforcement.stage_a_capacity_bytes != 2 * GIB or enforcement.total_capacity_bytes != 4 * GIB
                or any(getattr(enforcement, name) is not True for name in
                       ("hard_rss", "hard_worker_threads", "hard_disk_peak", "hard_wall"))
                or not 0 < enforcement.memory_max_bytes <= rss or enforcement.memory_swap_max_bytes != 0
                or enforcement.pids_max != 2 or not 0 < enforcement.rlimit_as_per_process_bytes * 2 <= rss
                or enforcement.guest_backing_mount_id != startup.guest_backing_mount_id
                or enforcement.windows_volume_id != startup.windows_volume_id):
            raise PermissionError("startup enforcement differs from the approved fixed resource envelope")
        # The adjacent durable receipt proves the pre-image >=8 GiB sample.
        # Startup's current post-allocation balance must not be required to
        # retain another unapproved 8 GiB after paying for the initial image.
        if not all((startup.guest_backing_mount_id, startup.guest_backing_device,
                    startup.windows_vhdx_path, startup.windows_volume_id)):
            raise PermissionError("expansion startup backing identity is incomplete")
        if enforcement.precreate_nested_backing is not None or startup.nested_backing is not None:
            before=nested_backing_identity(enforcement.precreate_nested_backing,
                windows_vhdx_path=startup.windows_vhdx_path,windows_volume_id=enforcement.windows_volume_id,
                windows_free_bytes=enforcement.precreate_windows_volume_free_bytes)
            after=nested_backing_identity(startup.nested_backing,
                windows_vhdx_path=startup.windows_vhdx_path,windows_volume_id=startup.windows_volume_id,
                windows_free_bytes=startup.windows_volume_free_bytes)
            if before!=after:
                raise PermissionError("expansion precreate/carrier/physical backing identity mismatch")
            if (enforcement.precreate_nested_backing.carrier_free_bytes
                    < enforcement.precreate_nested_backing.carrier_min_free_bytes):
                raise PermissionError("expansion original carrier reserve was not met")
        require_precreate_order(start["monotonic_ns"], enforcement.precreate_free_checked_monotonic_ns,
                                current.created_monotonic_ns, enforcement.precreate_guest_free_bytes,
                                enforcement.precreate_windows_volume_free_bytes, limits.startup_free_disk_bytes)
        if (set(boundary) != {"invocation_id", "reference_roles", "treatment_roles", "different_treatment_roles",
                             "stage_a_disk_bytes", "finished_monotonic_ns"}
                or boundary["invocation_id"] != current.invocation_id
                or any(type(boundary[key]) is not int for key in
                       ("reference_roles", "treatment_roles", "different_treatment_roles", "stage_a_disk_bytes", "finished_monotonic_ns"))
                or boundary["reference_roles"] != 105 or boundary["treatment_roles"] != 105
                or not 0 < boundary["different_treatment_roles"] <= 105
                or not 0 <= boundary["stage_a_disk_bytes"] <= 2 * GIB
                or not current.created_monotonic_ns < boundary["finished_monotonic_ns"] <= start["monotonic_ns"] + limits.stage_a_wall_ns
                or set(entry) != {"invocation_id", "projection"} or entry["invocation_id"] != current.invocation_id):
            raise PermissionError("Stage A boundary or entry does not bind the completed invocation")
        if (limits.stage_a_disk_accounting_mode == STAGE_A_CAPACITY_UPPER_BOUND_V2
                and boundary["stage_a_disk_bytes"] != limits.stage_a_disk_bytes):
            raise PermissionError("V2 expansion requires the exact Stage A hard capacity bound")
        active = None
        last_sampled_ns = current.created_monotonic_ns
        invocation_start = start["monotonic_ns"]
        stage_a_finish = boundary["finished_monotonic_ns"]
        for item in entries[2:-2]:
            name, payload = item["event"], item["payload"]
            if payload.get("invocation_id", current.invocation_id) != current.invocation_id:
                raise PermissionError("ledger contains a different invocation")
            if name == "gt_broker_registered":
                if broker_registration_bytes is None or item["seq"] != 2:
                    raise PermissionError("expansion registration lacks its original native pre-worker owner")
                continue  # Exact record/schema/count are replayed against original-owner bytes below.
            if name.startswith(("gt_", "call_", "stage_b_")) or name == "terminal":
                raise PermissionError("GT, Stage B calls, expansion or terminal preceded the expansion gate")
            if name == "activity_started":
                if (active is not None or set(payload) != {"name", "monotonic_ns", "fit", "stage_a"}
                        or payload.get("stage_a") is not True or payload.get("fit") is not False):
                    raise PermissionError("expansion gate has invalid Stage A activity")
                started_ns = payload["monotonic_ns"]
                if (type(payload["name"]) is not str or not payload["name"]
                        or type(started_ns) is not int or not last_sampled_ns <= started_ns <= stage_a_finish):
                    raise PermissionError("Stage A activity name or start time is outside the invocation boundary")
                active = (payload["name"], started_ns)
            elif name == "activity_finished":
                if (active is None or set(payload) != {"name", "monotonic_ns", "elapsed_ns", "invocation_wall_ns",
                                                      "fit_wall_ns", "failed", "snapshot"}
                        or payload.get("name") != active[0] or payload.get("failed") is not False):
                    raise PermissionError("expansion gate has unfinished or failed activity")
                if any(type(payload[key]) is not int for key in
                       ("monotonic_ns", "elapsed_ns", "invocation_wall_ns", "fit_wall_ns")):
                    raise PermissionError("Stage A activity wall observations must be exact integers")
                ended_ns, elapsed_ns = payload["monotonic_ns"], payload["elapsed_ns"]
                invocation_wall_ns, fit_wall_ns = payload["invocation_wall_ns"], payload["fit_wall_ns"]
                # BudgetGuard samples end before stop_activity's snapshot, then
                # elapsed_ns, then invocation_wall_ns. These are distinct clock
                # samples; their ordering, rather than equality, is required.
                elapsed_sample = active[1] + elapsed_ns
                invocation_sample = invocation_start + invocation_wall_ns
                if (not active[1] <= ended_ns <= elapsed_sample <= invocation_sample <= stage_a_finish
                        or not 0 <= elapsed_ns <= limits.stage_a_wall_ns
                        or not 0 <= invocation_wall_ns <= min(limits.stage_a_wall_ns, limits.total_wall_ns)
                        or not 0 <= fit_wall_ns <= min(limits.fit_wall_ns, invocation_wall_ns)
                        or fit_wall_ns != 0):
                    raise PermissionError("Stage A activity or snapshot samples violate wall order or fixed hard lines")
                observed=self._snapshot(payload.get("snapshot"), current, limits, rss)
                require_stage_filesystem(observed,startup,limits.stage_a_disk_bytes)
                last_sampled_ns = invocation_sample
                active = None
        if active is not None:
            raise PermissionError("a worker activity is still open in the ledger")
        value = entry["projection"]
        if type(value) is not dict:
            raise PermissionError("entry projection is not a durable projection object")
        graph, _, _ = _projection_call_role_ids(value)
        if not _digest_matches(graph, frozen.role_graph_sha256) or value["stage_a_disk_bytes_d_a"] != boundary["stage_a_disk_bytes"]:
            raise PermissionError("entry projection differs from exact approved role graph or Stage A disk")
        projection = StageBProjection(
            *(value[name] for name in ("candidate_rows_n", "maximum_fit_rows_m", "prediction_rows_s",
                                       "candidate_file_bytes_b", "stage_a_disk_bytes_d_a", "role_graph_sha256")),
            tuple(value["outer_role_ids"]),
            tuple((name, tuple(roles)) for name, roles in value["inner_role_ids_by_outer"]),
            tuple((name, tuple(roles)) for name, roles in value["fit_training_roles_by_verifier"]),
        )
        require_stage_b_entry(projection, limits=limits, frozen_rss_ceiling_bytes=rss, stage_a_hard_lines_met=True)
        # Rebuild all reservations/results from the protected chain. Summary
        # counts, supplied booleans and an entry projection cannot replace the
        # 105 reference + 105 treatment events. expand_same_volume must also
        # verify and retain every artifact FD before reserving its attempt.
        replay = replay_stage_a(
            encoded, invocation_id=current.invocation_id, study_root_path=current.study_root_path,
            expected_role_graph_sha256=frozen.role_graph_sha256, entry_event_sha256=event_sha256,
            role_registry_bytes=role_registry_bytes,
            expected_role_input_registry_sha256=frozen.role_input_registry_sha256,
            broker_registration_bytes=broker_registration_bytes,
        )
        return start["monotonic_ns"], boundary["finished_monotonic_ns"], enforcement.parent_cgroup_path, replay

    def _mount(self, current, frozen, members_path):
        ports = self._ports
        records = []
        for line in ports.mountinfo().splitlines():
            left, separator, right = line.partition(" - ")
            before, after = left.split(), right.split()
            if not separator or len(before) < 6 or len(after) < 3:
                raise PermissionError("malformed volume mountinfo")
            unescape = lambda text: re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), text)
            point = unescape(before[4])
            if any(point == alias or point.startswith(alias + "/") for alias in
                   ("/run/route2-input", "/run/route2-worker")):
                raise PermissionError("input or GT/worker mounts are still active")
            records.append((before, after, point, unescape(before[3]), unescape(after[1])))
        volume = frozen.approved_write_volumes[0]
        mounts = [item for item in records if item[2] == volume]
        if len(mounts) != 1:
            raise PermissionError("approved volume mount is absent or stacked")
        before, after, _, root, source = mounts[0]
        options = set(before[5].split(","))
        if (before[0] != current.mount_id or before[2] != current.filesystem_device or root != "/"
                or after[0] != "ext4" or source != current.loop_device
                or not {"rw", "nosuid", "nodev", "noexec"} <= options or "ro" in options
                or "ro" in after[2].split(",") or any(field.startswith("shared:") for field in before[6:])
                or any(item[2].startswith(volume + "/") for item in records)):
            raise PermissionError("mount identity, writable ext4 bounds or propagation changed")
        members_path = _path(members_path)
        if len(PurePosixPath(members_path).parts) < 3 or PurePosixPath(members_path).parts[1] != "system.slice":
            raise PermissionError("gate cgroup is outside the exact study service hierarchy")

        def live_membership():
            text = ports._kernel_text(Path("/proc/self/cgroup"))
            if type(text) is not str or not text or len(text) > MAX_KERNEL_TEXT_BYTES:
                raise PermissionError("controller's live cgroup membership is absent or oversized")
            unified = []
            for line in text.splitlines():
                values = line.split(":", 2)
                if len(values) != 3 or not values[0].isdecimal():
                    raise PermissionError("controller's live cgroup membership is malformed")
                if values[0] == "0":
                    if values[1] != "":
                        raise PermissionError("unified cgroup membership has controller aliases")
                    unified.append(_path(values[2]))
            if unified != [members_path]:
                raise PermissionError("gate cgroup differs from controller's exact live unified cgroup")
            return text

        membership_before = live_membership()
        cgroup_path = "/sys/fs/cgroup" + members_path
        descriptor = ports.open_existing(cgroup_path, kind="directory")
        try:
            opened = ports.fstat(descriptor)
            _require_protected_stat(opened, "directory")
            identity = (members_path, _identity(opened))
            frozen_identity = getattr(self, "_cgroup_identity", identity)
            if frozen_identity != identity:
                raise PermissionError("study cgroup identity changed between expansion checkpoints")
            pid = ports.pid()
            members = ports.cgroup_members(members_path)
            if (type(pid) is not int or pid <= 0 or type(members) is not tuple
                    or any(type(member) is not int or member <= 0 for member in members)
                    or members != (pid,)):
                raise PermissionError("study cgroup must contain exactly the controller PID and no extra threads")
            if live_membership() != membership_before:
                raise PermissionError("controller migrated while its cgroup membership was sampled")
            held, visible = ports.fstat(descriptor), ports.path_stat(cgroup_path, kind="directory")
            _require_protected_stat(held, "directory")
            _require_protected_stat(visible, "directory")
            if _identity(held) != identity[1] or _identity(visible) != identity[1]:
                raise PermissionError("study cgroup path was changed or recreated during sampling")
            self._cgroup_identity = identity
        finally:
            ports.close(descriptor)

    def expand_same_volume(self, invocation_id: str, current: ImageVolumeReceipt,
                           event_sha256: str, limits: BudgetLimits, *, original_gt_guard=None) -> ImageVolumeReceipt:
        """Match the SupervisorOps expansion signature; no supplied approval flag.

        The gate receipt is minted only after verified ledger bytes and their
        parent directory have actually been fsynced through the OS port.
        All failures after the attempt reservation forbid continuation/retry.
        """
        with self._lock:
            if self._attempted:
                raise PermissionError("volume expansion is one-shot; retry is forbidden")
            ports = self._ports
            ports.require_linux_root()
            frozen, admission_bytes = self._admission()
            self._current(invocation_id, current, event_sha256, limits, frozen)
            from .linux_production_controller import LinuxProductionOSPorts, LinuxProductionController, _ASSEMBLIES
            registration = None
            if type(ports) is LinuxProductionOSPorts or original_gt_guard is not None:
                from .budget import BudgetGuard
                from .linux_gt_history import require_original_gt_registration
                if type(original_gt_guard) is not BudgetGuard or type(original_gt_guard.enforcer) is not LinuxProductionController:
                    raise PermissionError("production expansion requires the original native guard")
                owner = _ASSEMBLIES.get(original_gt_guard.enforcer)
                if (owner is None or owner.guard() is not original_gt_guard or owner.expander is not self
                        or owner.ports is not ports or owner.volume is not current or owner.limits is not limits
                        or owner.pid != os.getpid() or owner.thread is not threading.current_thread()
                        or owner.failed or owner.activity is not None):
                    raise PermissionError("expansion broker owner differs from the original production assembly")
                registration = require_original_gt_registration(original_gt_guard)
            current = replace(current)
            descriptors = []
            objects = []
            artifacts = None
            try:
                handles = {}
                for name, path, kind in (
                    ("lock", current.lock_path, "file"), ("ledger", current.ledger_path, "file"),
                    ("volume", frozen.approved_write_volumes[0], "directory"),
                    ("study", current.study_root_path, "directory"),
                    ("image", current.image_path, "file"), ("loop", current.loop_device, "block"),
                ):
                    descriptor = ports.open_existing(path, kind=kind)
                    descriptors.append(descriptor)
                    info = ports.fstat(descriptor)
                    _require_protected_stat(info, kind)
                    handles[name] = descriptor
                    objects.append((path, kind, descriptor, _identity(info)))
                ports.lock_exclusive(handles["lock"])
                encoded = ports.read_fd(handles["ledger"], max_bytes=MAX_LEDGER_BYTES)
                started, finished, cgroup, replay = self._gate(encoded, event_sha256, current, limits, frozen,
                                                              broker_registration_bytes=registration)
                deadline = started + limits.total_wall_ns
                # Authenticate first, then read only the exact 105 output paths
                # supplied by replay. Keep their protected FDs and locks through
                # the entire operation under the already-held study lock.
                self._mount(current, frozen, cgroup)
                volume_device = ports.fstat(handles["volume"]).st_dev
                if _device(volume_device) != current.filesystem_device:
                    raise PermissionError("candidate artifacts escaped the frozen study filesystem")
                artifacts = HeldTreatmentArtifacts(
                    ports, replay, volume_device=volume_device,
                    deadline_ns=deadline, not_before_ns=finished,
                )
                artifacts.open_and_verify()

                def checkpoint(image_length, loop_capacity, *, expanded=False):
                    for path, kind, descriptor, identity in objects:
                        opened, visible = ports.fstat(descriptor), ports.path_stat(path, kind=kind)
                        _require_protected_stat(opened, kind)
                        _require_protected_stat(visible, kind)
                        if _identity(opened) != identity or _identity(visible) != identity:
                            raise PermissionError("volume, image, loop, lock or ledger path was changed or replaced")
                    image = ports.fstat(handles["image"])
                    device = ports.fstat(handles["loop"])
                    if ((image.st_dev, image.st_ino) != (current.image_device, current.image_inode)
                            or image.st_size != image_length
                            or _device(device.st_rdev) != current.filesystem_device):
                        raise PermissionError("image or loop descriptor differs from its frozen identity/length")
                    for name in ("volume", "study", "ledger", "lock"):
                        info = ports.fstat(handles[name])
                        if _device(info.st_dev) != current.filesystem_device:
                            raise PermissionError("study, ledger or lock escaped the frozen filesystem")
                    loop = ports.loop_state(handles["loop"])
                    if (type(loop) is not LoopState or any(type(value) is not int for value in asdict(loop).values())
                            or (loop.backing_device, loop.backing_inode, loop.number) !=
                            (current.image_device, current.image_inode, int(current.loop_device[9:]))
                            or loop.offset != 0 or loop.sizelimit != 0 or loop.flags & ~16
                            or loop.capacity_bytes != loop_capacity):
                        raise PermissionError("loop backing identity, flags or fixed capacity changed")
                    if ports.filesystem_uuid(handles["loop"]) != current.filesystem_uuid:
                        raise PermissionError("filesystem UUID changed")
                    self._mount(current, frozen, cgroup)
                    capacity = ports.filesystem_capacity(handles["volume"])
                    if (type(capacity) is not int or
                            (not expanded and capacity != current.filesystem_capacity_bytes) or
                            (expanded and not 2 * GIB < capacity <= 4 * GIB)):
                        raise PermissionError("actual filesystem capacity differs from the fixed expansion bounds")
                    if ports.read_fd(handles["ledger"], max_bytes=MAX_LEDGER_BYTES) != encoded:
                        raise PermissionError("entry ledger changed after its authenticated gate")
                    fresh_frozen, fresh_bytes = self._admission()
                    if fresh_frozen != frozen or fresh_bytes != admission_bytes:
                        raise PermissionError("protected approval changed during expansion")
                    artifacts.checkpoint()
                    # Hashing may take time: confirm quiescence again after the
                    # complete descriptor set has been streamed and fenced.
                    self._mount(current, frozen, cgroup)
                    now = ports.monotonic_ns()
                    if type(now) is not int or now < finished or now > deadline:
                        raise PermissionError("expansion exceeded the invocation wall deadline")
                    return capacity, now

                checkpoint(2 * GIB, 2 * GIB)
                ports.fsync(handles["ledger"])
                ports.fsync_parent(current.ledger_path)
                _, synced = checkpoint(2 * GIB, 2 * GIB)
                # This is a REPEAT sync after artifact verification, covered
                # by total wall. Original owned entry acceptance/deadline is
                # held by guard/supervisor before invoking this primitive.
                # Never reinterpret this later receipt as first acceptance.
                self.entry_receipt = DurableEventReceipt(event_sha256, synced)
                # Reopen for writing only after authentic durable admission;
                # both descriptors must still name the exact original object.
                for name in ("image", "loop"):
                    path = current.image_path if name == "image" else current.loop_device
                    kind = "file" if name == "image" else "block"
                    descriptor = ports.open_existing(path, kind=kind, writable=True)
                    descriptors.append(descriptor)
                    if _identity(ports.fstat(descriptor)) != _identity(ports.fstat(handles[name])):
                        raise PermissionError("volume descriptor changed during writable open")
                    handles[name] = descriptor
                    objects.append((path, kind, descriptor, _identity(ports.fstat(descriptor))))
                checkpoint(2 * GIB, 2 * GIB)
                self._attempted = True
                ports.reserve_attempt(_canonical({
                    "schema": "route2_fixed_volume_expansion_attempt_v1", "study_id": STUDY_ID,
                    "invocation_id": invocation_id, "entry_event_sha256": event_sha256,
                    "entry_fsynced_monotonic_ns": synced, "volume": asdict(current),
                    "before_image_bytes": 2 * GIB, "target_image_bytes": 4 * GIB,
                }) + b"\n", forbidden_device=ports.fstat(handles["volume"]).st_dev)
                checkpoint(2 * GIB, 2 * GIB)
                ports.truncate(handles["image"], 4 * GIB)
                ports.fsync(handles["image"])
                checkpoint(4 * GIB, 2 * GIB)
                ports.refresh_capacity(handles["loop"])
                _, now = checkpoint(4 * GIB, 4 * GIB)
                timeout = min(MAX_COMMAND_SECONDS, (deadline - now) / 1e9)
                if timeout <= 0:
                    raise PermissionError("no wall budget remains for resize2fs")
                ports.command(("/usr/sbin/resize2fs", f"/proc/self/fd/{handles['loop']}", "4G"),
                              pass_fds=(handles["loop"],), timeout=timeout)
                ports.fsync(handles["loop"])
                ports.fsync(handles["volume"])
                capacity, completed = checkpoint(4 * GIB, 4 * GIB, expanded=True)
                if completed <= synced:
                    raise PermissionError("expansion timestamp does not follow durable admission")
                return replace(current, created_monotonic_ns=completed,
                               image_length_bytes=4 * GIB, filesystem_capacity_bytes=capacity)
            finally:
                close_failure = None
                if artifacts is not None:
                    try:
                        artifacts.close()
                    except BaseException as exc:
                        close_failure = exc
                for descriptor in reversed(descriptors):
                    try:
                        ports.close(descriptor)
                    except BaseException as exc:
                        # Linux close errors can occur after release. Never
                        # retry a descriptor that may already have been reused.
                        close_failure = close_failure or exc
                if close_failure is not None:
                    raise close_failure
