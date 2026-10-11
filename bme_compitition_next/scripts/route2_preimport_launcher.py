#!/usr/bin/python3
"""External, stdlib-only trust gate for the Route 2 Python bootstrap.

Install an independently reviewed copy at a root-owned path outside both
snapshots (the planned path is ``/usr/local/libexec/route2-preimport-launcher.py``)
and invoke it with the system Python from the trusted supervisor. This file
imports no Route 2 module. It verifies the complete source and runtime trees
and their read-only mounts before exec'ing the pinned venv interpreter, where
the admission bootstrap and fixed production A+B runner may be imported. A
systemd ExecMain timestamp does not itself prove an origin before process
spawn or interpreter/stdlib startup. Until an actual installed native producer
establishes that ordering, refuse before accepting or sealing a start epoch.

The repository copy is implementation source, not an installed trust anchor.
Until a protected launcher copy, supervisor invocation and independently
reviewed native start-origin producer exist, production admission remains
unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import time
from typing import Any, Callable


DEFAULT_CONFIG_PATH = Path(
    "/etc/route2/route2-candidate-overlap-v1-001-supervisor.json"
)
STUDY_ID = "route2-candidate-overlap-v1-001"
MAX_CONFIG_BYTES = 1 << 16
MAX_MANIFEST_BYTES = 1 << 24
MAX_CONTROLLER_KEY_BYTES = 1 << 12
MAX_ADMISSION_BYTES = 1 << 20
MAX_START_BYTES = 1 << 14
PRODUCTION_POLICY_PATH = f"/etc/route2/{STUDY_ID}-production-controller.seal"
START_FD_ENV = "ROUTE2_PREIMPORT_START_FD"
START_MEMFD_NAME = "route2-preimport-start-v2"
START_HMAC_DOMAIN = b"route2.preimport.start-clock.v2\x00"
_PRODUCTION_POLICY_FIELDS = frozenset({
    "schema", "study_id", "invocation_id", "unit_name", "full_ab_seal_sha256",
    "authorization_card_sha256", "owner_approval_id", "budget_policy_sha256",
    "resource_controller_sha256", "budget_decision_id", "budget_decision_sha256",
    "installation_review_id", "installation_receipt_sha256", "stop_margin_ns",
    "billing_mode", "guest_control_cap_bytes", "host_control_cap_bytes",
    "stage_a_disk_accounting_mode",
})
_CONFIG_FIELDS = frozenset({
    "schema", "study_id", "controller_key_path", "sealed_admission_path",
    "source_snapshot_root", "source_manifest_path", "source_snapshot_sha256",
    "source_module_relative_path", "runtime_snapshot_root",
    "runtime_manifest_path", "runtime_snapshot_sha256", "source_mount_path",
    "runtime_mount_path", "independent_review_id", "owner_approval_id",
    "authorization_card_sha256",
})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SOURCE_SCHEMA = "route2_immutable_source_snapshot_v1"
_BOOTSTRAP_RELATIVE = (
    "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
)
_LAUNCH_ATTEMPTED = False


@dataclass(frozen=True, slots=True)
class TreeProof:
    manifest_sha256: str
    file_count: int
    total_bytes: int
    mount_path: str
    mount_id: int
    major_minor: str
    filesystem: str
    mount_source: str


@dataclass(frozen=True, slots=True)
class _Config:
    source_root: str
    source_manifest: str
    source_sha256: str
    runtime_root: str
    runtime_manifest: str
    runtime_sha256: str
    source_mount: str
    runtime_mount: str
    controller_key_path: str
    sealed_admission_path: str
    owner_approval_id: str
    authorization_card_sha256: str


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def _canonical_path(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise PermissionError(f"{name} is not a Linux path")
    path = PurePosixPath(value)
    if (
        not path.is_absolute() or path.as_posix() != value or ".." in path.parts
        or any(ord(char) < 32 or char.isspace() for char in value)
    ):
        raise PermissionError(f"{name} is not canonical")
    return value


def parse_supervisor_config(encoded: bytes) -> _Config:
    if type(encoded) is not bytes or not encoded or len(encoded) > MAX_CONFIG_BYTES:
        raise PermissionError("external supervisor configuration is empty or oversized")
    try:
        value = json.loads(encoded, object_pairs_hook=_unique_object)
        canonical = _canonical(value)
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PermissionError("external supervisor configuration is malformed") from exc
    if (
        not isinstance(value, dict) or canonical != encoded
        or set(value) != _CONFIG_FIELDS
        or value.get("schema") != "route2_external_supervisor_config_v1"
        or value.get("study_id") != STUDY_ID
    ):
        raise PermissionError("external supervisor configuration is noncanonical or unpinned")

    path_fields = (
        "controller_key_path", "sealed_admission_path", "source_snapshot_root",
        "source_manifest_path", "runtime_snapshot_root", "runtime_manifest_path",
        "source_mount_path", "runtime_mount_path",
    )
    paths = {name: _canonical_path(value.get(name), name) for name in path_fields}
    for name in ("source_snapshot_sha256", "runtime_snapshot_sha256", "authorization_card_sha256"):
        if not isinstance(value.get(name), str) or not _SHA256.fullmatch(value[name]):
            raise PermissionError(f"external supervisor {name} is not pinned")
    for name in ("independent_review_id", "owner_approval_id"):
        if not isinstance(value.get(name), str) or not _IDENTITY.fullmatch(value[name]):
            raise PermissionError(f"external supervisor {name} is malformed")
    if value.get("source_module_relative_path") != _BOOTSTRAP_RELATIVE:
        raise PermissionError("external supervisor names an unexpected bootstrap module")
    source_root = paths["source_snapshot_root"]
    runtime_root = paths["runtime_snapshot_root"]
    if (
        source_root == runtime_root
        or PurePosixPath(source_root) in PurePosixPath(runtime_root).parents
        or PurePosixPath(runtime_root) in PurePosixPath(source_root).parents
        or paths["source_mount_path"] != source_root
        or paths["runtime_mount_path"] != runtime_root
    ):
        raise PermissionError("source/runtime roots or mounts overlap or are not exact")
    for name in ("controller_key_path", "sealed_admission_path"):
        candidate = PurePosixPath(paths[name])
        if any(candidate == PurePosixPath(root) or PurePosixPath(root) in candidate.parents
               for root in (source_root, runtime_root)):
            raise PermissionError("controller material is inside a pinned snapshot")
    for name in ("source_manifest_path", "runtime_manifest_path"):
        candidate = PurePosixPath(paths[name])
        if any(candidate == PurePosixPath(root) or PurePosixPath(root) in candidate.parents
               for root in (source_root, runtime_root)):
            raise PermissionError("snapshot manifest is inside a pinned snapshot")
    return _Config(
        source_root=source_root,
        source_manifest=paths["source_manifest_path"],
        source_sha256=value["source_snapshot_sha256"],
        runtime_root=runtime_root,
        runtime_manifest=paths["runtime_manifest_path"],
        runtime_sha256=value["runtime_snapshot_sha256"],
        source_mount=paths["source_mount_path"],
        runtime_mount=paths["runtime_mount_path"],
        controller_key_path=paths["controller_key_path"],
        sealed_admission_path=paths["sealed_admission_path"],
        owner_approval_id=value["owner_approval_id"],
        authorization_card_sha256=value["authorization_card_sha256"],
    )


def _decode_mount(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t").replace(
        "\\012", "\n"
    ).replace("\\134", "\\")


def _readonly_mount(path: str, mountinfo_text: str) -> tuple[int, str, str, str]:
    target = PurePosixPath(path)
    if not target.is_absolute() or target.as_posix() != path:
        raise PermissionError("snapshot mount path is not canonical")
    matches: list[tuple[int, int, list[str], list[str]]] = []
    for line in mountinfo_text.splitlines():
        left, separator, right = line.partition(" - ")
        left_fields, right_fields = left.split(), right.split()
        if not separator or len(left_fields) < 6 or len(right_fields) < 3:
            raise PermissionError("mountinfo contains a malformed row")
        try:
            mount_id = int(left_fields[0])
        except ValueError as exc:
            raise PermissionError("mountinfo mount ID is malformed") from exc
        mount_point = PurePosixPath(_decode_mount(left_fields[4]))
        if target == mount_point:
            matches.append((len(mount_point.parts), mount_id, left_fields, right_fields))
    if not matches:
        raise PermissionError("snapshot does not have its exact mount in this namespace")
    if len(matches) != 1:
        raise PermissionError("snapshot has duplicate stacked exact mounts")
    _, mount_id, left_fields, right_fields = matches[0]
    mount_point = _decode_mount(left_fields[4])
    if "ro" not in set(left_fields[5].split(",")):
        raise PermissionError("snapshot mount is writable")
    return (
        mount_id, left_fields[2], right_fields[0], _decode_mount(right_fields[1]),
    )


def _relative_name(value: object) -> str:
    if not isinstance(value, str):
        raise PermissionError("snapshot manifest path is not text")
    path = PurePosixPath(value)
    if (
        not value or path.is_absolute() or path.as_posix() != value
        or "\\" in value or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PermissionError("snapshot manifest path is not canonical and relative")
    return value


def _tree_files(root: Path, *, require_root_immutable: bool) -> dict[str, Path]:
    if root.is_symlink() or not root.is_dir():
        raise PermissionError("snapshot root is not an ordinary directory")
    result: dict[str, Path] = {}
    for directory, names, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in ("", *names, *filenames):
            path = base if not name else base / name
            info = path.lstat()
            if path.is_symlink():
                raise PermissionError("snapshot contains a symbolic link")
            if require_root_immutable and (
                info.st_uid != 0
                or info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise PermissionError("snapshot is not root-owned and immutable")
            if name in names:
                if not stat.S_ISDIR(info.st_mode):
                    raise PermissionError("snapshot directory entry is not a directory")
            elif name in filenames:
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise PermissionError("snapshot file entry is not a private regular file")
                relative = _relative_name(path.relative_to(root).as_posix())
                result[relative] = path
    if not result:
        raise PermissionError("snapshot tree is empty")
    return result


def _hash_stable_file(
    path: Path, *, require_root_immutable: bool,
) -> tuple[int, str]:
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (
            opened.st_dev, opened.st_ino, opened.st_size
        ) or not stat.S_ISREG(opened.st_mode):
            raise PermissionError("snapshot file changed while opening")
        if require_root_immutable and (
            opened.st_uid != 0 or opened.st_nlink != 1
            or opened.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("opened snapshot file is not root-owned and immutable")
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                total += len(block)
        after = os.fstat(fd)
        if (
            total != opened.st_size
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        ):
            raise PermissionError("snapshot file changed while hashing")
        return total, digest.hexdigest()
    finally:
        os.close(fd)


def verify_snapshot_before_import(
    root: Path,
    manifest_bytes: bytes,
    *,
    expected_manifest_sha256: str,
    expected_module_relative_path: str | None,
    mount_path: str,
    mountinfo_text: str,
    require_linux_root: bool = True,
) -> TreeProof:
    """Verify every byte and the read-only mount before any Route 2 import."""

    if require_linux_root and (platform.system() != "Linux" or os.geteuid() != 0):
        raise PermissionError("pre-import Route 2 launcher requires Linux root")
    root = Path(root)
    if not root.is_absolute() or root.is_symlink():
        raise PermissionError("snapshot root must be an absolute ordinary directory")
    root_text = root.as_posix()
    if _canonical_path(mount_path, "mount_path") != mount_path:
        raise PermissionError("snapshot mount path is not canonical")
    if require_linux_root and root_text != mount_path:
        raise PermissionError("snapshot root and exact read-only mount path differ")
    mount_id, major_minor, filesystem, mount_source = _readonly_mount(mount_path, mountinfo_text)
    if (
        type(manifest_bytes) is not bytes
        or not isinstance(expected_manifest_sha256, str)
        or not _SHA256.fullmatch(expected_manifest_sha256)
        or hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256
    ):
        raise PermissionError("snapshot manifest bytes differ from the protected pin")
    try:
        value = json.loads(manifest_bytes, object_pairs_hook=_unique_object)
        canonical = _canonical(value)
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PermissionError("snapshot manifest is malformed") from exc
    if (
        not isinstance(value, dict) or set(value) != {"schema", "files"}
        or value.get("schema") != _SOURCE_SCHEMA or not isinstance(value.get("files"), list)
        or canonical != manifest_bytes
    ):
        raise PermissionError("snapshot manifest is noncanonical or has unknown fields")
    identities: dict[str, tuple[int, str]] = {}
    for entry in value["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise PermissionError("snapshot manifest entry is malformed")
        name = _relative_name(entry["path"])
        size, digest = entry["bytes"], entry["sha256"]
        if (
            name in identities or type(size) is not int or size < 0
            or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
        ):
            raise PermissionError("snapshot manifest identity is malformed or duplicated")
        identities[name] = (size, digest)
    if expected_module_relative_path is not None:
        if expected_module_relative_path != _BOOTSTRAP_RELATIVE:
            raise PermissionError("pre-import target is not the exact admission bootstrap")
        if expected_module_relative_path not in identities:
            raise PermissionError("admission bootstrap is absent from the pinned source tree")
    files = _tree_files(root, require_root_immutable=require_linux_root)
    if set(files) != set(identities):
        raise PermissionError("snapshot tree differs from the complete pinned manifest")
    for name, path in files.items():
        size, digest = identities[name]
        if _hash_stable_file(
            path, require_root_immutable=require_linux_root,
        ) != (size, digest):
            raise PermissionError(f"snapshot bytes differ from the pinned manifest: {name}")
    return TreeProof(
        manifest_sha256=expected_manifest_sha256,
        file_count=len(files),
        total_bytes=sum(size for size, _ in identities.values()),
        mount_path=mount_path,
        mount_id=mount_id,
        major_minor=major_minor,
        filesystem=filesystem,
        mount_source=mount_source,
    )


def verify_then_handoff(
    root: Path,
    manifest_bytes: bytes,
    *,
    expected_manifest_sha256: str,
    expected_module_relative_path: str | None,
    mount_path: str,
    mountinfo_text: str,
    handoff: Callable[[], object],
    require_linux_root: bool = True,
) -> tuple[TreeProof, object]:
    """Call the import/exec handoff only after complete source verification."""

    proof = verify_snapshot_before_import(
        root, manifest_bytes,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_module_relative_path=expected_module_relative_path,
        mount_path=mount_path,
        mountinfo_text=mountinfo_text,
        require_linux_root=require_linux_root,
    )
    return proof, handoff()


def _read_protected_file(
    path_text: str,
    *,
    max_bytes: int,
    expected_mode: int | None = 0o400,
) -> bytes:
    path = Path(path_text)
    if not path.is_absolute() or path.is_symlink():
        raise PermissionError("protected controller file path is not absolute and regular")
    for parent in reversed((path.parent, *path.parent.parents)):
        info = parent.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("protected controller file has an untrusted parent directory")
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode) or before.st_uid != 0
        or (
            stat.S_IMODE(before.st_mode) != expected_mode
            if expected_mode is not None
            else bool(before.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        )
        or before.st_nlink != 1
        or before.st_size > max_bytes
    ):
        raise PermissionError("protected controller file identity or mode is invalid")
    fd = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise PermissionError("protected controller file changed while opening")
        if (
            not stat.S_ISREG(opened.st_mode) or opened.st_uid != 0 or opened.st_nlink != 1
            or (
                stat.S_IMODE(opened.st_mode) != expected_mode
                if expected_mode is not None
                else bool(opened.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            )
        ):
            raise PermissionError("opened controller file mode or ownership is invalid")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            encoded = stream.read(max_bytes + 1)
        after = os.fstat(fd)
        if (
            len(encoded) > max_bytes
            or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        ):
            raise PermissionError("protected controller file changed while reading")
        return encoded
    finally:
        os.close(fd)


def _require_launcher_outside_snapshots(config: _Config) -> None:
    launcher = Path(__file__).resolve(strict=True)
    for root in (Path(config.source_root), Path(config.runtime_root)):
        try:
            launcher.relative_to(root.resolve(strict=True))
        except ValueError:
            continue
        raise PermissionError("pre-import launcher must be installed outside both snapshots")
    for parent in reversed((launcher.parent, *launcher.parent.parents)):
        info = parent.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("installed pre-import launcher has an untrusted parent")
    info = launcher.lstat()
    if (
        not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
        or info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise PermissionError("installed pre-import launcher is not root-owned and immutable")


def _native_process_identity() -> tuple[int, int, str, int, int]:
    """Read the identity that survives exec, including its monotonic namespace."""
    pid = os.getpid()
    text = Path("/proc/self/stat").read_text(encoding="ascii")
    head, separator, tail = text.rpartition(") ")
    fields = tail.split()
    if (not separator or head.partition(" (")[0] != str(pid)
            or len(fields) < 20 or not fields[19].isdecimal()):
        raise PermissionError("pre-import process start ticks are unavailable")
    ticks = int(fields[19])
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if ticks <= 0 or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", boot):
        raise PermissionError("pre-import boot/process identity is malformed")
    namespace = Path("/proc/self/ns/time").stat()
    manager_namespace = Path("/proc/1/ns/time").stat()
    if (namespace.st_dev, namespace.st_ino) != (manager_namespace.st_dev, manager_namespace.st_ino):
        raise PermissionError("pre-import CLOCK_MONOTONIC namespace differs from systemd PID 1")
    return pid, ticks, boot, namespace.st_dev, namespace.st_ino


def _require_actual_start_origin() -> None:
    """Refuse until installed native capture ordering has actual authority.

    The installed manager's executable/source and spawn path must be
    independently reviewed and bound to this invocation to prove capture
    before process spawn and Python startup. Alternatively, a trusted native
    producer must capture the original CLOCK_MONOTONIC epoch before launching
    Python and bind it to the process, boot, time namespace and invocation.
    Neither producer is implemented here. A version string, protected policy,
    HMAC, caller boolean or review/installation receipt proves no such ordering;
    an origin before the first Python sample can still omit startup work.
    """
    raise PermissionError(
        "actual native pre-Python start-origin producer is missing: installed "
        "systemd pre-fork timestamp semantics require independent review and "
        "invocation binding, or a trusted native origin before Python launch; "
        "ExecMainStartTimestampMonotonic cannot yet be accepted"
    )


def _systemd_exec_origin(unit_name: str, invocation_id: str) -> int:
    """Require native capture authority before reading PID 1's ExecMain start."""
    _require_actual_start_origin()
    if (type(unit_name) is not str
            or not re.fullmatch(r"route2-[A-Za-z0-9_.@-]{1,220}\.service", unit_name)
            or ".." in unit_name or type(invocation_id) is not str
            or not re.fullmatch(r"[0-9a-f]{32}", invocation_id)):
        raise PermissionError("systemd start requires the exact sealed native unit/invocation")
    # Use the root manager's protected local socket and system helper, with no
    # inherited D-Bus address or executable override. Parent root is trusted.
    for path, socket in ((Path("/usr/bin/systemctl"), False), (Path("/run/systemd/private"), True)):
        for parent in reversed((path.parent, *path.parent.parents)):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
                raise PermissionError("systemd origin has an untrusted helper/socket parent")
        info = path.lstat()
        if (info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                or (not stat.S_ISSOCK(info.st_mode) if socket
                    else not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_mode & stat.S_IXUSR)):
            raise PermissionError("systemd origin helper/socket is not the protected native subject")
    if Path("/proc/1/comm").read_text(encoding="ascii").strip() != "systemd":
        raise PermissionError("native monotonic origin is not owned by systemd PID 1")
    expected = {
        "Id": unit_name, "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Type": "exec", "MainPID": str(os.getpid()), "InvocationID": invocation_id,
        "ControlGroup": f"/system.slice/{unit_name}", "Restart": "no", "ProcSubset": "all",
    }
    names = (*expected, "ExecMainStartTimestampMonotonic")
    try:
        completed = subprocess.run(
            ["/usr/bin/systemctl", "--system", "show", "--all", "--no-pager",
             "--property=" + ",".join(names), unit_name],
            capture_output=True, text=True, encoding="ascii", errors="strict",
            timeout=5, check=False, shell=False, close_fds=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PermissionError("native systemd ExecMain origin could not be read") from exc
    if completed.returncode != 0 or type(completed.stdout) is not str or len(completed.stdout) > 4096:
        raise PermissionError("native systemd ExecMain origin is unavailable or oversized")
    properties = {}
    for line in completed.stdout.splitlines():
        name, separator, value = line.partition("=")
        if not separator or name not in names or name in properties:
            raise PermissionError("native systemd ExecMain origin has unknown/duplicate properties")
        properties[name] = value
    if set(properties) != set(names) or any(properties[name] != value for name, value in expected.items()):
        raise PermissionError("native systemd unit/PID/invocation differs from the sealed origin")
    if Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines() != [f"0::/system.slice/{unit_name}"]:
        raise PermissionError("native origin controller is outside the original unit cgroup")
    value = properties["ExecMainStartTimestampMonotonic"]
    if not re.fullmatch(r"[0-9]{1,20}", value) or not 0 < int(value) < (1 << 64) - 1:
        raise PermissionError("native systemd ExecMain start is not finite positive integer microseconds")
    # systemd floors CLOCK_MONOTONIC to microseconds. Multiplication retains
    # that lower bound; never round up or use a suspend-inclusive boot clock.
    start_us = int(value)
    if start_us * 1000 > time.clock_gettime_ns(time.CLOCK_MONOTONIC):
        raise PermissionError("native systemd ExecMain start is in a different/future clock epoch")
    return start_us



def _start_policy(config: _Config, key: bytes, admission: bytes, encoded: bytes) -> dict[str, Any]:
    try:
        wrapped = json.loads(encoded, object_pairs_hook=_unique_object)
        body = wrapped["body"]
        signature = wrapped["controller_hmac_sha256"]
        if (type(wrapped) is not dict or set(wrapped) != {"body", "controller_hmac_sha256"}
                or type(body) is not dict or set(body) != _PRODUCTION_POLICY_FIELDS
                or _canonical(wrapped) != encoded or type(signature) is not str
                or not _SHA256.fullmatch(signature)
                or not hmac.compare_digest(signature, hmac.new(key, _canonical(body), hashlib.sha256).hexdigest())):
            raise ValueError("production policy seal is invalid")
        expected = {
            "schema": "route2_production_controller_policy_v2", "study_id": STUDY_ID,
            "full_ab_seal_sha256": hashlib.sha256(admission).hexdigest(),
            "owner_approval_id": config.owner_approval_id,
            "authorization_card_sha256": config.authorization_card_sha256,
        }
        if any(body[name] != value for name, value in expected.items()):
            raise ValueError("production policy binds different admission bytes")
        if (type(body["invocation_id"]) is not str or not _IDENTITY.fullmatch(body["invocation_id"])
                or type(body["unit_name"]) is not str
                or not re.fullmatch(r"route2-[A-Za-z0-9_.@-]{1,220}\.service", body["unit_name"])
                or ".." in body["unit_name"]):
            raise ValueError("production invocation/unit is invalid")
        return body
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise PermissionError("pre-import production invocation policy is unauthenticated") from exc


def _sealed_start_fd(*, exec_main_start_us: int, identity: tuple[int, int, str, int, int],
                     config_bytes: bytes, config: _Config, key: bytes,
                     admission: bytes, policy_bytes: bytes) -> int:
    """The external launcher is the sole producer; the source tree only consumes."""
    import fcntl

    policy = _start_policy(config, key, admission, policy_bytes)
    if (type(exec_main_start_us) is not int or exec_main_start_us <= 0
            or exec_main_start_us != _systemd_exec_origin(policy["unit_name"], policy["invocation_id"])
            or identity != _native_process_identity()):
        raise PermissionError("pre-import native clock/process changed before exec")
    started_ns = exec_main_start_us * 1000
    fd = os.memfd_create(START_MEMFD_NAME, os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
    inherited = None
    try:
        os.fchmod(fd, 0o400)
        info = os.fstat(fd)
        pid, ticks, boot, time_device, time_inode = identity
        body = {
            "schema": "route2_preimport_start_clock_v2", "study_id": STUDY_ID,
            "origin": "systemd_exec_main", "exec_main_start_monotonic_us": exec_main_start_us,
            "clock": "CLOCK_MONOTONIC", "started_monotonic_ns": started_ns,
            "config_path": str(DEFAULT_CONFIG_PATH),
            "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "seal_sha256": hashlib.sha256(admission).hexdigest(),
            "production_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
            "invocation_id": policy["invocation_id"], "unit_name": policy["unit_name"],
            "pid": pid, "process_start_ticks": ticks, "boot_id": boot,
            "time_namespace_device": time_device, "time_namespace_inode": time_inode,
            "nonce": os.urandom(32).hex(), "memfd_device": info.st_dev, "memfd_inode": info.st_ino,
        }
        encoded = _canonical({"body": body, "controller_hmac_sha256": hmac.new(
            key, START_HMAC_DOMAIN + _canonical(body), hashlib.sha256,
        ).hexdigest()})
        if not 0 < len(encoded) <= MAX_START_BYTES:
            raise PermissionError("pre-import start token exceeds its fixed bound")
        offset = 0
        while offset < len(encoded):
            written = os.write(fd, encoded[offset:])
            if written <= 0:
                raise OSError("short pre-import start token write")
            offset += written
        seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
        if fcntl.fcntl(fd, fcntl.F_GET_SEALS) != seals or os.pread(fd, MAX_START_BYTES + 1, 0) != encoded:
            raise PermissionError("pre-import start token was not completely sealed")
        # Only a read-only descriptor crosses exec. No timer crosses this
        # boundary: production arms absolute deadlines from started_ns later.
        inherited = os.open(f"/proc/self/fd/{fd}", os.O_RDONLY | os.O_CLOEXEC)
        if (os.fstat(inherited).st_dev, os.fstat(inherited).st_ino) != (info.st_dev, info.st_ino):
            raise PermissionError("pre-import read-only memfd identity changed")
        return inherited
    except BaseException:
        if inherited is not None:
            os.close(inherited)
        raise
    finally:
        os.close(fd)


def _exec_pinned_bootstrap(config: _Config, start_fd: int) -> None:
    python = Path(config.runtime_root) / "bin/python"
    if python.is_symlink() or not python.is_file():
        raise PermissionError("pinned runtime interpreter path is not a regular file")
    source_path = str(Path(config.source_root) / "src")
    code = (
        "import sys; sys.path.insert(0, " + repr(source_path) + "); "
        "from eating_event.route2_candidate_overlap.production_runner import "
        "main; main()"
    )
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "BLIS_NUM_THREADS": "1",
        START_FD_ENV: str(start_fd),
    }
    os.set_inheritable(start_fd, True)
    os.execve(python, [str(python), "-I", "-B", "-c", code], env)
    raise RuntimeError("execve unexpectedly returned")


def main() -> None:
    """Systemd entry point; absence of root-only config fails closed."""

    global _LAUNCH_ATTEMPTED
    if _LAUNCH_ATTEMPTED:
        raise PermissionError("pre-import launch has already been attempted")
    _LAUNCH_ATTEMPTED = True
    if sys.platform != "linux":
        raise PermissionError("Route 2 pre-import launcher requires Linux")
    # This sample only rejects a later/reset manager origin. It cannot prove
    # pre-fork ordering or be the budget epoch: Python startup precedes it.
    first_observed_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    if platform.system() != "Linux" or os.geteuid() != 0:
        raise PermissionError("Route 2 pre-import launcher requires Linux root")
    if not sys.flags.isolated or not sys.flags.no_site:
        raise PermissionError("system Python must start with -I -S before any Route 2 import")
    identity = _native_process_identity()
    config_bytes = _read_protected_file(str(DEFAULT_CONFIG_PATH), max_bytes=MAX_CONFIG_BYTES)
    config = parse_supervisor_config(config_bytes)
    _require_launcher_outside_snapshots(config)
    key = _read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
    if len(key) < 32:
        raise PermissionError("external controller key is shorter than 256 bits")
    admission = _read_protected_file(config.sealed_admission_path, max_bytes=MAX_ADMISSION_BYTES)
    policy_bytes = _read_protected_file(PRODUCTION_POLICY_PATH, max_bytes=MAX_CONFIG_BYTES)
    policy = _start_policy(config, key, admission, policy_bytes)
    exec_main_start_us = _systemd_exec_origin(policy["unit_name"], policy["invocation_id"])
    if exec_main_start_us * 1000 > first_observed_ns:
        raise PermissionError("systemd ExecMain origin does not precede pre-import Python/configuration work")
    source_manifest = _read_protected_file(
        config.source_manifest, max_bytes=MAX_MANIFEST_BYTES, expected_mode=None,
    )
    runtime_manifest = _read_protected_file(
        config.runtime_manifest, max_bytes=MAX_MANIFEST_BYTES, expected_mode=None,
    )
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    verify_snapshot_before_import(
        Path(config.source_root), source_manifest,
        expected_manifest_sha256=config.source_sha256,
        expected_module_relative_path=_BOOTSTRAP_RELATIVE,
        mount_path=config.source_mount,
        mountinfo_text=mountinfo,
    )
    verify_snapshot_before_import(
        Path(config.runtime_root), runtime_manifest,
        expected_manifest_sha256=config.runtime_sha256,
        expected_module_relative_path=None,
        mount_path=config.runtime_mount,
        mountinfo_text=mountinfo,
    )
    if (config_bytes != _read_protected_file(str(DEFAULT_CONFIG_PATH), max_bytes=MAX_CONFIG_BYTES)
            or key != _read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
            or admission != _read_protected_file(config.sealed_admission_path, max_bytes=MAX_ADMISSION_BYTES)
            or policy_bytes != _read_protected_file(PRODUCTION_POLICY_PATH, max_bytes=MAX_CONFIG_BYTES)):
        raise PermissionError("protected startup material changed during snapshot verification")
    start_fd = _sealed_start_fd(exec_main_start_us=exec_main_start_us, identity=identity,
        config_bytes=config_bytes, config=config, key=key, admission=admission, policy_bytes=policy_bytes)
    try:
        _exec_pinned_bootstrap(config, start_fd)
    finally:
        # Successful exec replaces this interpreter. A failed exec consumes
        # and closes the sole inherited descriptor instead of retrying.
        os.close(start_fd)


if __name__ == "__main__":
    main()
