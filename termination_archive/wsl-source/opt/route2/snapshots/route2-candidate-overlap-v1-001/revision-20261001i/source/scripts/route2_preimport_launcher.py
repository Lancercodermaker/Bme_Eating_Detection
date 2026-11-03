#!/usr/bin/python3
"""External, stdlib-only trust gate for the Route 2 Python bootstrap.

Install an independently reviewed copy at a root-owned path outside both
snapshots (the planned path is ``/usr/local/libexec/route2-preimport-launcher.py``)
and invoke it with the system Python from the trusted supervisor. This file
imports no Route 2 module. It verifies the complete source and runtime trees
and their read-only mounts before exec'ing the pinned venv interpreter, where
the ordinary admission bootstrap may be imported. It never starts Stage A/B.

The repository copy is implementation source, not an installed trust anchor.
Until a protected launcher copy and supervisor invocation exist, production
admission remains unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
from typing import Any, Callable


DEFAULT_CONFIG_PATH = Path(
    "/etc/route2/route2-candidate-overlap-v1-001-supervisor.json"
)
STUDY_ID = "route2-candidate-overlap-v1-001"
MAX_CONFIG_BYTES = 1 << 16
MAX_MANIFEST_BYTES = 1 << 24
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


def _exec_pinned_bootstrap(config: _Config) -> None:
    python = Path(config.runtime_root) / "bin/python"
    if python.is_symlink() or not python.is_file():
        raise PermissionError("pinned runtime interpreter path is not a regular file")
    source_path = str(Path(config.source_root) / "src")
    code = (
        "import sys; sys.path.insert(0, " + repr(source_path) + "); "
        "from eating_event.route2_candidate_overlap.admission_bootstrap import "
        "bootstrap_frozen_admission; bootstrap_frozen_admission()"
    )
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    os.execve(python, [str(python), "-I", "-B", "-c", code], env)
    raise RuntimeError("execve unexpectedly returned")


def main() -> None:
    """Systemd entry point; absence of root-only config fails closed."""

    if platform.system() != "Linux" or os.geteuid() != 0:
        raise PermissionError("Route 2 pre-import launcher requires Linux root")
    if not sys.flags.isolated or not sys.flags.no_site:
        raise PermissionError("system Python must start with -I -S before any Route 2 import")
    config_bytes = _read_protected_file(str(DEFAULT_CONFIG_PATH), max_bytes=MAX_CONFIG_BYTES)
    config = parse_supervisor_config(config_bytes)
    _require_launcher_outside_snapshots(config)
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
    _exec_pinned_bootstrap(config)


if __name__ == "__main__":
    main()
