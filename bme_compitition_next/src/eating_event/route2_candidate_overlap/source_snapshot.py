"""Content and Linux-mount checks for an immutable Route 2 source snapshot.

The manifest is metadata only.  Validation reads the frozen code/config tree,
never project inputs, and requires the worker's view of the snapshot to come
from a read-only Linux mount.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any


_SCHEMA = "route2_immutable_source_snapshot_v1"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _relative_name(value: object) -> str:
    if not isinstance(value, str):
        raise PermissionError("source snapshot file path is not text")
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
    ):
        raise PermissionError("source snapshot path is not canonical and relative")
    return value


def _tree_files(root: Path) -> dict[str, Path]:
    if root.is_symlink() or not root.is_dir():
        raise PermissionError("source snapshot root must be an ordinary directory")
    result: dict[str, Path] = {}
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in tuple(directory_names):
            path = base / name
            if path.is_symlink() or not path.is_dir():
                raise PermissionError("source snapshot tree contains a directory link")
        for name in file_names:
            path = base / name
            if path.is_symlink():
                raise PermissionError("source snapshot tree contains a file link")
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise PermissionError("source snapshot tree contains a nonregular file")
            relative = path.relative_to(root).as_posix()
            _relative_name(relative)
            if relative in result:
                raise PermissionError("source snapshot repeats a relative file path")
            result[relative] = path
    if not result:
        raise PermissionError("source snapshot tree is empty")
    return result


def build_source_manifest(root: Path) -> bytes:
    """Build canonical content identities for every regular file under ``root``."""

    root = Path(root)
    files = _tree_files(root)
    return _canonical({
        "schema": _SCHEMA,
        "files": [
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for name, path in sorted(files.items())
        ],
    })


@dataclass(frozen=True, slots=True)
class SourceSnapshotProof:
    manifest_sha256: str
    file_count: int
    total_bytes: int


def verify_source_snapshot(
    root: Path,
    manifest_bytes: bytes,
    *,
    expected_manifest_sha256: str,
) -> SourceSnapshotProof:
    """Require the complete current tree to equal its pinned canonical manifest."""

    if (
        not isinstance(manifest_bytes, bytes)
        or len(expected_manifest_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_manifest_sha256.lower())
        or hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256.lower()
    ):
        raise PermissionError("source snapshot manifest hash differs from its reviewed pin")
    try:
        value: Any = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PermissionError("source snapshot manifest is invalid JSON") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "files"}
        or value.get("schema") != _SCHEMA
        or not isinstance(value.get("files"), list)
        or _canonical(value) != manifest_bytes
    ):
        raise PermissionError("source snapshot manifest is not canonical or has unknown fields")

    identities: dict[str, tuple[int, str]] = {}
    for entry in value["files"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise PermissionError("source snapshot manifest has an unreviewed file entry")
        name = _relative_name(entry["path"])
        size = entry["bytes"]
        digest = entry["sha256"]
        if (
            name in identities
            or type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise PermissionError("source snapshot file identity is malformed or repeated")
        identities[name] = (size, digest.lower())

    files = _tree_files(Path(root))
    if set(files) != set(identities):
        raise PermissionError("source snapshot file set differs from its reviewed manifest")
    for name, path in files.items():
        expected_size, expected_digest = identities[name]
        info = path.stat()
        if info.st_size != expected_size or _sha256(path) != expected_digest:
            raise PermissionError(f"source snapshot file bytes differ from manifest: {name}")
    return SourceSnapshotProof(
        manifest_sha256=expected_manifest_sha256.lower(),
        file_count=len(files),
        total_bytes=sum(size for size, _ in identities.values()),
    )


@dataclass(frozen=True, slots=True)
class ReadonlyMountProof:
    mount_id: int
    mount_point: str
    major_minor: str
    filesystem: str
    source: str


@dataclass(frozen=True, slots=True)
class SnapshotModuleProof:
    snapshot: SourceSnapshotProof
    module_relative_path: str
    mount: ReadonlyMountProof


def _unescape_mount_field(value: str) -> str:
    return (
        value.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def require_readonly_mount(path: str, mountinfo_text: str) -> ReadonlyMountProof:
    """Resolve the most-specific covering mount and require its flags include ``ro``."""

    target = PurePosixPath(path)
    if (
        not target.is_absolute()
        or target.as_posix() != path
        or ".." in target.parts
        or not isinstance(mountinfo_text, str)
    ):
        raise PermissionError("source snapshot path or mountinfo is invalid")

    matches: list[tuple[int, int, list[str], list[str]]] = []
    for line in mountinfo_text.splitlines():
        left, separator, right_text = line.partition(" - ")
        if not separator:
            raise PermissionError("Linux mountinfo contains a malformed row")
        left_fields = left.split()
        right_fields = right_text.split()
        if len(left_fields) < 6 or len(right_fields) < 3:
            raise PermissionError("Linux mountinfo row is incomplete")
        try:
            mount_id = int(left_fields[0])
        except ValueError as exc:
            raise PermissionError("Linux mountinfo has an invalid mount ID") from exc
        mount_point = _unescape_mount_field(left_fields[4])
        mount = PurePosixPath(mount_point)
        if target == mount or mount in target.parents:
            matches.append((len(mount.parts), mount_id, left_fields, right_fields))
    if not matches:
        raise PermissionError("source snapshot is not covered by a Linux mount")
    _, _, left_fields, right_fields = max(matches, key=lambda item: (item[0], item[1]))
    options = set(left_fields[5].split(","))
    if "ro" not in options:
        raise PermissionError("source snapshot mount is not read-only")
    return ReadonlyMountProof(
        mount_id=int(left_fields[0]),
        mount_point=_unescape_mount_field(left_fields[4]),
        major_minor=left_fields[2],
        filesystem=right_fields[0],
        source=_unescape_mount_field(right_fields[1]),
    )


def verify_snapshot_module(
    root: Path,
    module_path: Path,
    manifest_bytes: bytes,
    *,
    expected_manifest_sha256: str,
    expected_module_relative_path: str,
    mount_path: str,
    mountinfo_text: str,
) -> SnapshotModuleProof:
    """Bind an imported module to a fully hashed tree on a read-only mount."""

    expected_relative = _relative_name(expected_module_relative_path)
    root_path = Path(root)
    module = Path(module_path)
    if module.is_symlink() or not module.is_file():
        raise PermissionError("imported source module must be an ordinary file")
    try:
        resolved_root = root_path.resolve(strict=True)
        resolved_module = module.resolve(strict=True)
        relative = resolved_module.relative_to(resolved_root).as_posix()
    except (OSError, ValueError) as exc:
        raise PermissionError("imported source module is outside the pinned snapshot root") from exc
    if relative != expected_relative:
        raise PermissionError("imported source module is outside its pinned snapshot location")
    tree = verify_source_snapshot(
        resolved_root,
        manifest_bytes,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    mount = require_readonly_mount(mount_path, mountinfo_text)
    return SnapshotModuleProof(tree, relative, mount)


def require_controller_owned_readonly_tree(root: Path) -> None:
    """Require root-owned, non-writable files after checking the read-only bind."""

    if os.name != "posix":
        raise PermissionError("immutable controller snapshot requires Linux ownership metadata")
    root = Path(root)
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in ("", *directory_names, *file_names):
            path = base if not name else base / name
            if path.is_symlink():
                raise PermissionError("controller snapshot contains a symbolic link")
            info = path.lstat()
            if (
                (name in directory_names and not stat.S_ISDIR(info.st_mode))
                or (name in file_names and not stat.S_ISREG(info.st_mode))
                or info.st_uid != 0
                or info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise PermissionError("controller snapshot is not root-owned and immutable")
