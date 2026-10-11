"""Live binding of the Route 2 cgroup observation to its systemd service.

This adapter adds the missing unit and cgroup2 mount identity checks around
``linux_enforcement``'s existing study-wide process/cgroup capture. Its result
is an observation mapping accepted by ``validate_cgroup_enforcement``. It is a
point-in-time resource proof, not a complete lifecycle or approval receipt.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Callable, Mapping, Sequence

from .linux_enforcement import (
    ResourceEnvelope,
    capture_cgroup_v2_observation,
    validate_cgroup_enforcement,
)


_SYSTEMD_PROPERTIES = (
    "LoadState",
    "ActiveState",
    "SubState",
    "Type",
    "Restart",
    "KillMode",
    "SendSIGKILL",
    "RemainAfterExit",
    "ControlGroup",
    "MainPID",
    "InvocationID",
    "MemoryAccounting",
    "MemoryMax",
    "MemorySwapMax",
    "TasksAccounting",
    "TasksMax",
    "CPUQuotaPerSecUSec",
    "RuntimeMaxUSec",
    "TimeoutStopUSec",
)
_UNIT_RE = re.compile(r"route2-[A-Za-z0-9_.@-]{1,220}\.service\Z", re.ASCII)
_UINT_RE = re.compile(r"[0-9]+\Z", re.ASCII)
_INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z", re.ASCII | re.IGNORECASE)
_DURATION_TOKEN_RE = re.compile(r"([0-9]+)(ns|us|ms|s|min|h|d|w)", re.ASCII)
_DURATION_NS = {
    "ns": 1,
    "us": 1_000,
    "ms": 1_000_000,
    "s": 1_000_000_000,
    "min": 60_000_000_000,
    "h": 3_600_000_000_000,
    "d": 86_400_000_000_000,
    "w": 604_800_000_000_000,
}


def _device_major_minor(device: int) -> str:
    if hasattr(os, "major") and hasattr(os, "minor"):
        return f"{os.major(device)}:{os.minor(device)}"
    # Linux dev_t encoding, retained here so synthetic fixtures can run on
    # hosts whose os module does not expose the POSIX major/minor helpers.
    major = ((device >> 8) & 0xFFF) | ((device >> 32) & 0xFFFFF000)
    minor = (device & 0xFF) | ((device >> 12) & 0xFFFFFF00)
    return f"{major}:{minor}"


def _validate_unit_name(unit_name: object) -> str:
    if (
        not isinstance(unit_name, str)
        or not _UNIT_RE.fullmatch(unit_name)
        or ".." in unit_name
    ):
        raise PermissionError("study systemd unit name is not a canonical Route 2 service")
    return unit_name


def read_systemd_unit_properties(
    unit_name: str,
    *,
    systemctl_path: str = "/usr/bin/systemctl",
    run: Callable[..., object] = subprocess.run,
) -> dict[str, str]:
    """Read a fixed set of unit fields through direct argv, never a shell."""

    unit = _validate_unit_name(unit_name)
    if (
        not isinstance(systemctl_path, str)
        or not systemctl_path.startswith("/")
        or "\x00" in systemctl_path
        or any(ch.isspace() for ch in systemctl_path)
    ):
        raise PermissionError("systemctl executable path must be an absolute canonical path")
    argv = [
        systemctl_path,
        "show",
        "--no-pager",
        f"--property={','.join(_SYSTEMD_PROPERTIES)}",
        unit,
    ]
    try:
        completed = run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=5,
            check=False,
            shell=False,
        )
    except Exception as exc:
        raise PermissionError("systemd unit properties could not be read") from exc
    if (
        getattr(completed, "returncode", None) != 0
        or not isinstance(getattr(completed, "stdout", None), str)
    ):
        raise PermissionError("systemd did not return a successful unit property snapshot")

    properties: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if not separator or name not in _SYSTEMD_PROPERTIES or name in properties:
            raise PermissionError("systemd returned malformed, duplicate or unexpected properties")
        properties[name] = value
    if set(properties) != set(_SYSTEMD_PROPERTIES):
        raise PermissionError("systemd unit property snapshot is incomplete")
    return properties


def _parse_uint_property(properties: Mapping[str, str], name: str) -> int:
    value = properties.get(name)
    if not isinstance(value, str) or not _UINT_RE.fullmatch(value):
        raise PermissionError(f"systemd {name} is not an exact finite integer")
    return int(value)


def _parse_systemd_timespan_ns(value: object, name: str) -> int:
    """Parse systemctl's human-readable integer-unit ``*USec`` rendering."""

    if value == "0":
        return 0
    if not isinstance(value, str) or not value:
        raise PermissionError(f"systemd {name} is not a finite timespan")
    cursor = 0
    result = 0
    seen: set[str] = set()
    while cursor < len(value):
        if cursor:
            if value[cursor] != " ":
                raise PermissionError(f"systemd {name} has a malformed timespan")
            cursor += 1
        match = _DURATION_TOKEN_RE.match(value, cursor)
        if match is None:
            raise PermissionError(f"systemd {name} has a malformed timespan")
        amount_text, unit = match.groups()
        if unit in seen:
            raise PermissionError(f"systemd {name} repeats a timespan unit")
        seen.add(unit)
        result += int(amount_text) * _DURATION_NS[unit]
        cursor = match.end()
    return result


def _verify_systemd_service(
    unit_name: str,
    properties: Mapping[str, object],
    envelope: ResourceEnvelope,
) -> tuple[str, int, str]:
    unit = _validate_unit_name(unit_name)
    if type(envelope) is not ResourceEnvelope or not isinstance(properties, Mapping):
        raise TypeError("active study service verification requires the fixed resource envelope")
    if set(properties) != set(_SYSTEMD_PROPERTIES):
        raise PermissionError("systemd unit properties are missing or contain unknown fields")

    expected_cgroup = f"/system.slice/{unit}"
    expected_text = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "Type": "exec",
        "Restart": "no",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "RemainAfterExit": "no",
        "ControlGroup": expected_cgroup,
        "MemoryAccounting": "yes",
        "MemoryMax": str(envelope.memory_max_bytes),
        "MemorySwapMax": str(envelope.memory_swap_max_bytes),
        "TasksAccounting": "yes",
        "TasksMax": str(envelope.pids_max),
    }
    if any(properties.get(name) != expected for name, expected in expected_text.items()):
        raise PermissionError("active systemd service semantics or hard limits differ from the frozen envelope")

    main_pid = _parse_uint_property(properties, "MainPID")
    if main_pid <= 0:
        raise PermissionError("active systemd service has no positive main PID")
    invocation_id = properties.get("InvocationID")
    if not isinstance(invocation_id, str) or not _INVOCATION_ID_RE.fullmatch(invocation_id):
        raise PermissionError("active systemd service has no exact invocation identity")
    if _parse_systemd_timespan_ns(
        properties.get("CPUQuotaPerSecUSec"), "CPUQuotaPerSecUSec",
    ) != envelope.cpu_quota_percent * 10_000_000:
        raise PermissionError("systemd CPU quota differs from the frozen resource envelope")
    if _parse_systemd_timespan_ns(
        properties.get("RuntimeMaxUSec"), "RuntimeMaxUSec",
    ) != envelope.runtime_max_ns:
        raise PermissionError("systemd runtime ceiling differs from the frozen resource envelope")
    if _parse_systemd_timespan_ns(
        properties.get("TimeoutStopUSec"), "TimeoutStopUSec",
    ) != envelope.stop_margin_ns:
        raise PermissionError("systemd stop timeout differs from the frozen resource envelope")
    return expected_cgroup, main_pid, invocation_id


def _decode_mountinfo_path(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 8))

    decoded = re.sub(r"\\([0-7]{3})", replace, value)
    path = PurePosixPath(decoded)
    if not path.is_absolute() or path.as_posix() != decoded or ".." in path.parts:
        raise PermissionError("cgroup2 mountinfo contains a noncanonical path")
    return decoded


def _cgroup2_mount_identity(
    *,
    cgroup_root: Path,
    mountinfo_path: Path,
) -> dict[str, object]:
    if not isinstance(cgroup_root, Path) or not isinstance(mountinfo_path, Path):
        raise TypeError("cgroup root and mountinfo path must be pathlib paths")
    if not cgroup_root.is_absolute() or cgroup_root.is_symlink() or not cgroup_root.is_dir():
        raise PermissionError("unified cgroup root must be a real mounted directory")
    resolved_root = cgroup_root.resolve(strict=True)
    expected_mount_point = resolved_root.as_posix()
    if not expected_mount_point.startswith("/"):
        # Synthetic Windows-host fixtures map their absolute temp paths into
        # mountinfo's POSIX namespace with a leading slash.
        expected_mount_point = f"/{expected_mount_point.lstrip('/')}"

    rows: list[tuple[int, str, str, str]] = []
    for line in mountinfo_path.read_text(encoding="ascii").splitlines():
        left, separator, right = line.partition(" - ")
        if not separator:
            raise PermissionError("mountinfo contains a malformed mount row")
        before = left.split()
        after = right.split()
        if len(before) < 6 or len(after) < 3:
            raise PermissionError("mountinfo contains an incomplete mount row")
        if after[0] != "cgroup2":
            continue
        if not _UINT_RE.fullmatch(before[0]) or not re.fullmatch(r"[0-9]+:[0-9]+", before[2]):
            raise PermissionError("cgroup2 mountinfo identity is malformed")
        rows.append((
            int(before[0]),
            before[2],
            _decode_mountinfo_path(before[3]),
            _decode_mountinfo_path(before[4]),
        ))
    if len(rows) != 1:
        raise PermissionError("mount namespace must expose one unambiguous cgroup2 mount")
    mount_id, device, mount_root, mount_point = rows[0]
    if mount_id <= 0 or mount_root != "/" or mount_point != expected_mount_point:
        raise PermissionError("cgroup2 mount root or mount point differs from the resolved cgroup root")

    info = resolved_root.stat()
    actual_device = _device_major_minor(info.st_dev)
    if actual_device != device:
        raise PermissionError("cgroup root device differs from the cgroup2 mount identity")
    return {
        "mount_id": mount_id,
        "device": device,
        "mount_root": mount_root,
        "mount_point": mount_point,
        "root_device": info.st_dev,
        "root_inode": info.st_ino,
    }


def capture_active_study_service_observation(
    unit_name: str,
    envelope: ResourceEnvelope,
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    mountinfo_path: Path = Path("/proc/self/mountinfo"),
) -> dict[str, object]:
    """Capture a validator-compatible observation bound to one active unit.

    The unit is sampled on both sides of the existing complete cgroup/process
    capture. A mismatch, missing field, weak limit, alternate service boundary,
    cgroup namespace or mount identity aborts closed.
    """

    unit = _validate_unit_name(unit_name)
    if type(envelope) is not ResourceEnvelope:
        raise TypeError("active study capture requires the fixed resource envelope")
    before = read_systemd_unit_properties(unit)
    expected_cgroup, main_pid, invocation_id = _verify_systemd_service(
        unit, before, envelope,
    )
    mount = _cgroup2_mount_identity(
        cgroup_root=cgroup_root,
        mountinfo_path=mountinfo_path,
    )
    observation = capture_cgroup_v2_observation(
        proc_root=proc_root,
        cgroup_root=cgroup_root,
    )
    after = read_systemd_unit_properties(unit)
    after_cgroup, after_main_pid, after_invocation_id = _verify_systemd_service(
        unit, after, envelope,
    )
    after_mount = _cgroup2_mount_identity(
        cgroup_root=cgroup_root,
        mountinfo_path=mountinfo_path,
    )
    if mount != after_mount:
        raise PermissionError("cgroup2 mount identity changed during cgroup evidence capture")
    if (
        before != after
        or after_cgroup != expected_cgroup
        or after_main_pid != main_pid
        or after_invocation_id != invocation_id
    ):
        raise PermissionError("systemd unit identity changed during cgroup evidence capture")
    if observation.get("cgroup_path") != expected_cgroup:
        raise PermissionError("active process cgroup differs from the systemd service boundary")
    raw_rlimits = observation.get("rlimit_as_bytes_by_pid")
    if not isinstance(raw_rlimits, Mapping) or str(main_pid) not in raw_rlimits:
        raise PermissionError("systemd main process is absent from study-wide cgroup task evidence")
    if any(value != envelope.rlimit_as_per_process_bytes for value in raw_rlimits.values()):
        raise PermissionError("a study process RLIMIT_AS differs from the frozen resource envelope")
    validate_cgroup_enforcement(observation, envelope)

    observation["systemd_unit"] = {
        "name": unit,
        "load_state": "loaded",
        "active_state": "active",
        "sub_state": "running",
        "type": "exec",
        "restart": "no",
        "kill_mode": "control-group",
        "control_group": expected_cgroup,
        "main_pid": main_pid,
        "invocation_id": invocation_id,
        "properties": dict(before),
    }
    observation["cgroup2_mount"] = mount
    return observation


__all__ = [
    "capture_active_study_service_observation",
    "read_systemd_unit_properties",
]
