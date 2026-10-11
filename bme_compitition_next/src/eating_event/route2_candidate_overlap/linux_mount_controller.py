"""Privileged Linux bind and revoke operations for one Route 2 Stage A role.

The controller operates in the mount namespace of its caller.  It does not
create namespaces, and its caller must arrange an appropriately isolated
namespace before invoking these operations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import secrets
import stat
import subprocess
import threading
import time
from typing import Callable, Mapping, Sequence
import uuid

from .linux_enforcement import (
    ReadonlyFileBind,
    canonical_receipt_bytes,
    registered_file_binds,
    receipt_sha256,
)
from .path_map import (
    ActiveRoleMountSet,
    ExactPathMap,
    ExactFileMapping,
    MountReceipt,
    RoleMountController,
    file_mapping,
)
from .contracts import OUTER_CONTROL_CANDIDATES_PHASE, require_frozen_admission


_ALIAS_ROOT = PurePosixPath("/run/route2-input")
_ROLE_VIEW_PHASES = frozenset({
    "stage_a_input", "stage_a_reference", OUTER_CONTROL_CANDIDATES_PHASE,
})
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def _default_effective_uid() -> int:
    getuid = getattr(os, "geteuid", None)
    return getuid() if getuid is not None else -1


def _require_private_mount_namespace() -> None:
    if platform.system() != "Linux":
        raise PermissionError("controller requires a pre-existing private Linux mount namespace")
    try:
        current = os.stat("/proc/self/ns/mnt")
        init = os.stat("/proc/1/ns/mnt")
    except OSError as exc:
        raise PermissionError("controller cannot verify its Linux mount namespace") from exc
    if (current.st_dev, current.st_ino) == (init.st_dev, init.st_ino):
        raise PermissionError("controller requires a pre-existing private Linux mount namespace")
    try:
        mountinfo = _default_mountinfo_reader()
    except OSError as exc:
        raise PermissionError("controller cannot verify mount propagation") from exc
    _require_alias_root_not_shared(mountinfo)


def _default_mountinfo_reader() -> str:
    if os.name != "posix":
        raise PermissionError("Linux mountinfo is unavailable on this platform")
    return Path("/proc/self/mountinfo").read_text(encoding="utf-8")


def _default_command_runner(argv: tuple[str, ...]) -> None:
    subprocess.run(
        argv,
        check=True,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _decode_mountinfo_path(value: str) -> str:
    return re.sub(
        r"\\([0-7]{3})",
        lambda match: chr(int(match.group(1), 8)),
        value,
    )


@dataclass(frozen=True, slots=True)
class _MountInfo:
    mount_id: int
    device: str
    root: str
    mount_point: str
    options: frozenset[str]
    optional_fields: frozenset[str]

    @property
    def readonly(self) -> bool:
        return "ro" in self.options and "rw" not in self.options


def _parse_mountinfo(value: str) -> tuple[_MountInfo, ...]:
    if not isinstance(value, str):
        raise PermissionError("mountinfo reader returned a non-text value")
    result: list[_MountInfo] = []
    for line in value.splitlines():
        left, separator, right = line.partition(" - ")
        fields = left.split()
        after_separator = right.split()
        if not separator or len(fields) < 6 or len(after_separator) < 3:
            raise PermissionError("malformed Linux mountinfo")
        if not fields[0].isdecimal() or int(fields[0]) <= 0:
            raise PermissionError("mountinfo contains an invalid mount ID")
        if not re.fullmatch(r"[0-9]+:[0-9]+", fields[2]):
            raise PermissionError("mountinfo contains an invalid device identity")
        options = frozenset(fields[5].split(","))
        if not options or any(not option for option in options):
            raise PermissionError("mountinfo contains malformed mount options")
        result.append(
            _MountInfo(
                mount_id=int(fields[0]),
                device=fields[2],
                root=_decode_mountinfo_path(fields[3]),
                mount_point=_decode_mountinfo_path(fields[4]),
                options=options,
                optional_fields=frozenset(fields[6:]),
            )
        )
    return tuple(result)


def _require_alias_root_not_shared(mountinfo: str) -> None:
    """Refuse mounts beneath a shared parent that could propagate to peers."""

    root = str(_ALIAS_ROOT)
    covering = [
        item for item in _parse_mountinfo(mountinfo)
        if root == item.mount_point
        or root.startswith(item.mount_point.rstrip("/") + "/")
        or item.mount_point == "/"
    ]
    if not covering:
        raise PermissionError("controller cannot identify the mount covering the alias root")
    parent_mount = max(covering, key=lambda item: len(item.mount_point))
    if any(field.startswith("shared:") for field in parent_mount.optional_fields):
        raise PermissionError("controller refuses shared mount propagation at the alias root")


def _validate_root_owned_directory(path: Path) -> None:
    if not path.is_absolute():
        raise PermissionError("controller receipt root must be absolute")
    for ancestor in reversed((path, *path.parents)):
        info = ancestor.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("controller state path is mutable or not root-owned")


def _path_identity(path: Path) -> tuple[int, int]:
    info = path.stat()
    return info.st_dev, info.st_ino


def _identity_tuple(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(type(part) is not int or part < 0 for part in value)
    ):
        raise PermissionError("file identity hook returned invalid device or inode evidence")
    return value


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        raise PermissionError("durable controller receipts require Linux directory fsync")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _hash_regular_nonsymlink(path: Path) -> tuple[str, tuple[int, int]]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise PermissionError("registered Stage A source is unavailable") from exc
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise PermissionError("registered Stage A source must be a regular non-symlink file")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PermissionError("registered Stage A source could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise PermissionError("registered Stage A source changed during safe open")
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        after = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            raise PermissionError("registered Stage A source changed while it was hashed")
        return digest.hexdigest(), (opened.st_dev, opened.st_ino)
    finally:
        os.close(descriptor)


def _durable_write(path: Path, body: Mapping[str, object], directory_sync: Callable[[Path], None]) -> str:
    encoded = canonical_receipt_bytes(body)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(12)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(descriptor)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(descriptor)
    try:
        if path.exists():
            raise PermissionError("controller receipt path already exists")
        os.replace(temporary, path)
        directory_sync(path.parent)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return receipt_sha256(body)


@dataclass(frozen=True, slots=True)
class _PreparedFile:
    mapping: ExactFileMapping
    bind: ReadonlyFileBind
    source_path: Path
    alias_path: Path
    source_digest: str
    source_identity: tuple[int, int]


@dataclass(slots=True)
class _IssuedView:
    active: ActiveRoleMountSet
    request_key: tuple[object, ...]
    files: tuple[_PreparedFile, ...]


class LinuxRoleMountController(RoleMountController):
    """Mount and revoke one exact non-GT role view in Linux as root.

    The reviewed manifest and digest are pinned at construction. The command
    runner, mountinfo reader, platform/root/namespace checks, worker readiness
    check, path resolvers, file identity reader, receipt root validator, and
    directory sync are injectable so synthetic tests never call mount/umount
    or inspect project inputs.
    """

    def __init__(
        self,
        *,
        reviewed_manifest_bytes: bytes,
        expected_manifest_sha256: str,
        worker_prepublication_check: Callable[
            [str, tuple[ExactFileMapping, ...]], bool
        ] | None,
        receipt_root: str | Path = "/var/lib/route2-controller/role-mount-receipts",
        source_resolver: Callable[[ReadonlyFileBind], str | Path] | None = None,
        alias_path_resolver: Callable[[str], str | Path] | None = None,
        command_runner: Callable[[tuple[str, ...]], object] = _default_command_runner,
        mountinfo_reader: Callable[[], str] = _default_mountinfo_reader,
        platform_name: Callable[[], str] = platform.system,
        effective_uid: Callable[[], int] = _default_effective_uid,
        root_path_validator: Callable[[Path], None] = _validate_root_owned_directory,
        file_identity_reader: Callable[[Path], tuple[int, int]] = _path_identity,
        directory_sync: Callable[[Path], None] = _fsync_directory,
        mount_namespace_validator: Callable[[], None] = _require_private_mount_namespace,
        controller_run_id: str | None = None,
    ) -> None:
        if (
            not isinstance(reviewed_manifest_bytes, bytes)
            or not reviewed_manifest_bytes
            or not isinstance(expected_manifest_sha256, str)
            or not _SHA256_RE.fullmatch(expected_manifest_sha256.lower())
            or hashlib.sha256(reviewed_manifest_bytes).hexdigest()
            != expected_manifest_sha256.lower()
        ):
            raise PermissionError("reviewed canonical manifest bytes do not match their pinned digest")
        try:
            reviewed_path_map = ExactPathMap.from_bytes(
                reviewed_manifest_bytes,
                expected_manifest_sha256,
            )
        except (TypeError, ValueError, PermissionError) as exc:
            raise PermissionError("controller requires a canonical reviewed manifest") from exc
        reviewed_bind_root = str(reviewed_path_map.bind_root).replace("\\", "/")
        if reviewed_bind_root != str(_ALIAS_ROOT):
            raise PermissionError("canonical reviewed manifest does not use the exact Route 2 alias root")
        role_view_by_role: dict[str, list[ExactFileMapping]] = {}
        for item in reviewed_path_map._entries.values():
            if item.phase in _ROLE_VIEW_PHASES:
                if PurePosixPath(item.bind_path).parent != _ALIAS_ROOT:
                    raise PermissionError("canonical role mapping escapes the exact Route 2 alias root")
                role_view_by_role.setdefault(item.role_id, []).append(item)
        self._reviewed_manifest_sha256 = expected_manifest_sha256.lower()
        self._reviewed_manifest_bytes = reviewed_manifest_bytes
        self._reviewed_role_view_by_role = {
            role: tuple(sorted(items, key=lambda item: item.key))
            for role, items in role_view_by_role.items()
        }
        if not self._reviewed_role_view_by_role:
            raise PermissionError("canonical reviewed manifest has no non-GT role mappings")
        self._worker_prepublication_check = worker_prepublication_check
        self._receipt_root = Path(receipt_root)
        self._source_resolver = source_resolver or (lambda bind: bind.source_path)
        self._alias_path_resolver = alias_path_resolver or Path
        self._command_runner = command_runner
        self._mountinfo_reader = mountinfo_reader
        self._platform_name = platform_name
        self._effective_uid = effective_uid
        self._root_path_validator = root_path_validator
        self._file_identity_reader = file_identity_reader
        self._directory_sync = directory_sync
        self._mount_namespace_validator = mount_namespace_validator
        self._run_id = controller_run_id or uuid.uuid4().hex
        if not isinstance(self._run_id, str) or not _RUN_ID_RE.fullmatch(self._run_id):
            raise ValueError("controller run ID must be a safe opaque identifier")
        self._lock = threading.RLock()
        self._active: _IssuedView | None = None
        self._revoked: dict[str, tuple[ActiveRoleMountSet, str]] = {}
        self._revocation_failures: dict[str, str] = {}
        self._faulted = False

    @property
    def controller_run_id(self) -> str:
        return self._run_id

    @property
    def faulted(self) -> bool:
        return self._faulted

    def _require_linux_root(self) -> None:
        if self._platform_name() != "Linux" or self._effective_uid() != 0:
            raise PermissionError("role bind operations require Linux and effective UID 0")
        self._mount_namespace_validator()

    def _ensure_receipt_root(self) -> None:
        if not self._receipt_root.is_absolute():
            raise PermissionError("controller receipt root must be an absolute path")
        current = Path(self._receipt_root.anchor)
        for part in self._receipt_root.parts[1:]:
            child = current / part
            try:
                child.lstat()
            except FileNotFoundError:
                try:
                    child.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                else:
                    self._directory_sync(current)
            info = child.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise PermissionError("controller receipt root contains a link or non-directory")
            current = child
        self._root_path_validator(self._receipt_root)

    def _mounts_at(self, alias: str) -> tuple[_MountInfo, ...]:
        return tuple(
            item for item in _parse_mountinfo(self._mountinfo_reader())
            if item.mount_point == alias
        )

    def _validate_request_identity(
        self,
        *,
        manifest_sha256: str,
        manifest_bytes: bytes,
        role_id: str,
        mappings: tuple[ExactFileMapping, ...],
    ) -> tuple[
        tuple[object, ...],
        dict[str, ReadonlyFileBind],
        dict[str, ExactFileMapping],
    ]:
        if not isinstance(manifest_sha256, str) or not _SHA256_RE.fullmatch(manifest_sha256.lower()):
            raise PermissionError("role activation needs a reviewed manifest SHA-256")
        if manifest_sha256.lower() != self._reviewed_manifest_sha256:
            raise PermissionError("role activation differs from the pinned canonical manifest digest")
        if (
            not isinstance(manifest_bytes, bytes)
            or manifest_bytes != self._reviewed_manifest_bytes
            or hashlib.sha256(manifest_bytes).hexdigest() != self._reviewed_manifest_sha256
        ):
            raise PermissionError("role activation differs from the pinned canonical manifest bytes")
        if (
            not isinstance(role_id, str)
            or not role_id
            or role_id == "__study__"
            or not isinstance(mappings, tuple)
            or not mappings
            or any(type(item) is not ExactFileMapping for item in mappings)
        ):
            raise PermissionError("role activation needs one role and exact mappings")
        if any(item.role_id != role_id or item.phase not in _ROLE_VIEW_PHASES for item in mappings):
            raise PermissionError("controller accepts only this role's input, reference, and control candidates")
        if {item.phase for item in mappings} != _ROLE_VIEW_PHASES:
            raise PermissionError("role activation must include input, reference, and control candidate mappings")

        keys = [item.key for item in mappings]
        aliases = [item.bind_path for item in mappings]
        if len(keys) != len(set(keys)) or len(aliases) != len(set(aliases)):
            raise PermissionError("role activation repeats an exact mapping or alias")
        reviewed_role_set = self._reviewed_role_view_by_role.get(role_id, ())
        if tuple(sorted(mappings, key=lambda item: item.key)) != reviewed_role_set:
            raise PermissionError("mappings differ from the canonical manifest's complete role set")
        for item in mappings:
            expected = file_mapping(
                item.logical_path,
                item.sha256,
                role_id=item.role_id,
                phase=item.phase,
                bind_root=str(_ALIAS_ROOT),
            )
            alias = PurePosixPath(item.bind_path)
            if item.bind_path != expected.bind_path or alias.parent != _ALIAS_ROOT:
                raise PermissionError("registered file alias is outside the exact Route 2 alias root")

        binds = registered_file_binds(mappings)
        binds_by_alias = {item.alias_path: item for item in binds}
        mapping_by_alias = {item.bind_path: item for item in mappings}
        if set(binds_by_alias) != set(mapping_by_alias):
            raise PermissionError("exact registered Stage A mappings do not match Linux bind aliases")
        request_key: tuple[object, ...] = (
            manifest_sha256.lower(),
            role_id,
            tuple((item.key, item.bind_path) for item in sorted(mappings, key=lambda row: row.key)),
        )
        return request_key, binds_by_alias, mapping_by_alias

    def _prepare_files(
        self,
        *,
        binds_by_alias: dict[str, ReadonlyFileBind],
        mapping_by_alias: dict[str, ExactFileMapping],
        allow_mounted_aliases: frozenset[str] = frozenset(),
    ) -> tuple[_PreparedFile, ...]:
        prepared: list[_PreparedFile] = []
        for alias in sorted(mapping_by_alias):
            mapping = mapping_by_alias[alias]
            bind = binds_by_alias.get(alias)
            if bind is None:
                raise PermissionError("exact registered Stage A mapping has no Linux source bind")
            source_path = Path(self._source_resolver(bind))
            alias_path = Path(self._alias_path_resolver(alias))
            digest, source_identity = _hash_regular_nonsymlink(source_path)
            if digest != mapping.sha256.lower():
                raise PermissionError("registered Stage A source SHA-256 changed before activation")
            try:
                alias_info = alias_path.lstat()
            except OSError as exc:
                raise PermissionError("exact bind alias target is unavailable") from exc
            if not stat.S_ISREG(alias_info.st_mode) or stat.S_ISLNK(alias_info.st_mode):
                raise PermissionError("exact bind alias target must be a regular non-symlink file")
            self._root_path_validator(alias_path.parent)
            if self._mounts_at(alias) and alias not in allow_mounted_aliases:
                self._faulted = True
                raise PermissionError("exact role-view alias is already mounted before activation")
            prepared.append(
                _PreparedFile(
                    mapping=mapping,
                    bind=bind,
                    source_path=source_path,
                    alias_path=alias_path,
                    source_digest=digest,
                    source_identity=source_identity,
                )
            )
        return tuple(prepared)

    def _verify_mount(self, prepared: _PreparedFile, expected_mount_id: int | None = None) -> _MountInfo:
        found = self._mounts_at(prepared.mapping.bind_path)
        if len(found) != 1:
            raise PermissionError("approved alias is not one exact Linux file bind mount")
        mount = found[0]
        if not mount.readonly:
            raise PermissionError("approved exact file bind is not read-only in mountinfo")
        if expected_mount_id is not None and mount.mount_id != expected_mount_id:
            raise PermissionError("read-only bind mount ID differs from its active receipt")
        source_identity = _identity_tuple(self._file_identity_reader(prepared.source_path))
        target_identity = _identity_tuple(self._file_identity_reader(prepared.alias_path))
        if source_identity != prepared.source_identity or target_identity != source_identity:
            raise PermissionError("mountinfo alias does not identify the exact hashed source file")
        return mount

    def _record_activation(
        self,
        *,
        manifest_sha256: str,
        phase_id: str,
        mounts: tuple[MountReceipt, ...],
    ) -> str:
        body: dict[str, object] = {
            "schema": "route2_mount_receipt_v1",
            "manifest_sha256": manifest_sha256,
            "controller_run_id": self._run_id,
            "phase_id": phase_id,
            "mounts": [asdict(item) for item in mounts],
        }
        path = self._receipt_root / f"activation-{self._run_id}-{phase_id}.json"
        return _durable_write(path, body, self._directory_sync)

    def _record_revocation_failure(
        self,
        active: ActiveRoleMountSet,
        failures: Sequence[Mapping[str, object]],
        residual_aliases: Sequence[str],
    ) -> str:
        self._ensure_receipt_root()
        body: dict[str, object] = {
            "schema": "route2_mount_revocation_failure_v1",
            "manifest_sha256": active.mounts[0].manifest_sha256,
            "controller_run_id": active.controller_run_id,
            "phase_id": active.phase_id,
            "role_id": active.mounts[0].role_id,
            "activation_receipt_sha256": active.receipt_sha256,
            "mounts": [
                {"bind_path": item.bind_path, "mount_id": item.mount_id}
                for item in active.mounts
            ],
            "failures": [dict(item) for item in failures],
            "residual_aliases": sorted(set(residual_aliases)),
            "failed_at_ns": time.time_ns(),
        }
        path = self._receipt_root / (
            f"revocation-failure-{active.controller_run_id}-{active.phase_id}.json"
        )
        return _durable_write(path, body, self._directory_sync)

    def _rollback(self, aliases: Sequence[str]) -> None:
        failed = False
        for alias in reversed(tuple(dict.fromkeys(aliases))):
            try:
                found = self._mounts_at(alias)
                if found:
                    self._command_runner(("umount", alias))
                if self._mounts_at(alias):
                    failed = True
            except BaseException:
                failed = True
        if failed:
            self._faulted = True

    def activate_role_view(
        self,
        *,
        manifest_sha256: str,
        manifest_bytes: bytes,
        role_id: str,
        mappings: tuple[ExactFileMapping, ...],
    ) -> ActiveRoleMountSet:
        with self._lock:
            self._require_linux_root()
            if self._faulted:
                raise PermissionError("Linux role mount controller is faulted")
            frozen_path_map_sha256 = require_frozen_admission().path_map_sha256
            if (
                not isinstance(frozen_path_map_sha256, str)
                or not _SHA256_RE.fullmatch(frozen_path_map_sha256.lower())
                or frozen_path_map_sha256.lower() != self._reviewed_manifest_sha256
                or not isinstance(manifest_sha256, str)
                or manifest_sha256.lower() != frozen_path_map_sha256.lower()
            ):
                raise PermissionError(
                    "controller manifest differs from the frozen admission path-map pin"
                )
            self._ensure_receipt_root()
            request_key, binds_by_alias, mapping_by_alias = self._validate_request_identity(
                manifest_sha256=manifest_sha256,
                manifest_bytes=manifest_bytes,
                role_id=role_id,
                mappings=mappings,
            )
            if self._active is not None:
                if self._active.request_key != request_key:
                    raise PermissionError("another exact role view is already active")
            elif (
                self._worker_prepublication_check is None
                or self._worker_prepublication_check(role_id, mappings) is not True
            ):
                raise PermissionError("worker publication precondition is not satisfied")
            files = self._prepare_files(
                binds_by_alias=binds_by_alias,
                mapping_by_alias=mapping_by_alias,
                allow_mounted_aliases=(
                    frozenset(mapping_by_alias) if self._active is not None else frozenset()
                ),
            )
            if self._active is not None:
                receipts_by_alias = {
                    receipt.bind_path: receipt for receipt in self._active.active.mounts
                }
                if set(receipts_by_alias) != set(mapping_by_alias):
                    self._faulted = True
                    raise PermissionError("active role receipt does not cover its exact alias set")
                for prepared in files:
                    receipt = receipts_by_alias[prepared.mapping.bind_path]
                    self._verify_mount(prepared, receipt.mount_id)
                return self._active.active

            phase_id = uuid.uuid4().hex
            attempted: list[str] = []
            side_effects_possible = False
            try:
                receipts: list[MountReceipt] = []
                for prepared in files:
                    alias = prepared.mapping.bind_path
                    attempted.append(alias)
                    side_effects_possible = True
                    self._command_runner((
                        "mount", "--bind", str(prepared.source_path), alias,
                    ))
                    self._command_runner((
                        "mount", "-o", "remount,bind,ro", str(prepared.source_path), alias,
                    ))
                    mount = self._verify_mount(prepared)
                    digest_after_mount, identity_after_mount = _hash_regular_nonsymlink(
                        prepared.source_path
                    )
                    if (
                        digest_after_mount != prepared.mapping.sha256.lower()
                        or identity_after_mount != prepared.source_identity
                    ):
                        raise PermissionError("registered Stage A source changed during bind activation")
                    receipts.append(MountReceipt(
                        manifest_sha256=manifest_sha256.lower(),
                        logical_path=prepared.mapping.logical_path,
                        sha256=prepared.mapping.sha256,
                        role_id=prepared.mapping.role_id,
                        phase=prepared.mapping.phase,
                        bind_path=prepared.mapping.bind_path,
                        mount_id=mount.mount_id,
                    ))

                receipt_tuple = tuple(sorted(receipts, key=lambda item: item.key))
                active = ActiveRoleMountSet(
                    controller_run_id=self._run_id,
                    phase_id=phase_id,
                    receipt_sha256="0" * 64,
                    mounts=receipt_tuple,
                )
                receipt_digest = self._record_activation(
                    manifest_sha256=manifest_sha256.lower(),
                    phase_id=phase_id,
                    mounts=receipt_tuple,
                )
                active = ActiveRoleMountSet(
                    controller_run_id=self._run_id,
                    phase_id=phase_id,
                    receipt_sha256=receipt_digest,
                    mounts=receipt_tuple,
                )
                self._active = _IssuedView(active, request_key, files)
                return active
            except BaseException:
                if side_effects_possible:
                    self._rollback(attempted)
                    self._faulted = True
                raise

    @staticmethod
    def _same_active(left: ActiveRoleMountSet, right: ActiveRoleMountSet) -> bool:
        return (
            left.controller_run_id == right.controller_run_id
            and left.phase_id == right.phase_id
            and left.receipt_sha256 == right.receipt_sha256
            and left.mounts == right.mounts
        )

    def revoke_role_view(self, active: ActiveRoleMountSet) -> str:
        with self._lock:
            self._require_linux_root()
            if self._faulted:
                raise PermissionError("Linux role mount controller is faulted")
            if type(active) is not ActiveRoleMountSet:
                raise PermissionError("revocation requires this controller's exact active receipt")
            if active.controller_run_id != self._run_id:
                raise PermissionError("active receipt belongs to a different controller run")
            if self._active is None:
                previous = self._revoked.get(active.phase_id)
                if previous is None or not self._same_active(previous[0], active):
                    raise PermissionError("role view is not active in this controller")
                failures: list[dict[str, object]] = []
                residual_aliases: list[str] = []
                for receipt in active.mounts:
                    try:
                        found = self._mounts_at(receipt.bind_path)
                    except BaseException as exc:
                        residual_aliases.append(receipt.bind_path)
                        failures.append({
                            "bind_path": receipt.bind_path,
                            "mount_id": receipt.mount_id,
                            "stage": "mountinfo_after_prior_revoke",
                            "error_type": type(exc).__name__,
                        })
                        continue
                    if found:
                        residual_aliases.append(receipt.bind_path)
                        failures.append({
                            "bind_path": receipt.bind_path,
                            "mount_id": receipt.mount_id,
                            "stage": "alias_reappeared_after_revoke",
                            "error_type": "UnexpectedMount",
                            "observed_mount_ids": [item.mount_id for item in found],
                        })
                if failures:
                    self._faulted = True
                    try:
                        failure_digest = self._record_revocation_failure(
                            active, failures, residual_aliases,
                        )
                    except BaseException as exc:
                        raise PermissionError(
                            "revoked Stage A alias reappeared and durable failure evidence "
                            "could not be persisted"
                        ) from exc
                    self._revocation_failures[active.phase_id] = failure_digest
                    raise PermissionError(
                        "revoked Stage A alias reappeared; durable failure evidence was written"
                    )
                return previous[1]
            if not self._same_active(self._active.active, active):
                raise PermissionError("revocation receipt differs from the controller's active role view")

            failures: list[dict[str, object]] = []
            residual_aliases: list[str] = []
            for receipt in reversed(active.mounts):
                alias = receipt.bind_path
                prepared = next(
                    (
                        item for item in self._active.files
                        if item.mapping.bind_path == alias
                    ),
                    None,
                )
                if prepared is None:
                    failures.append({
                        "bind_path": alias,
                        "mount_id": receipt.mount_id,
                        "stage": "prepared_mapping_lookup",
                        "error_type": "PermissionError",
                    })

                found: tuple[_MountInfo, ...] | None
                try:
                    found = self._mounts_at(alias)
                    if not found:
                        failures.append({
                            "bind_path": alias,
                            "mount_id": receipt.mount_id,
                            "stage": "mountinfo_before_revoke",
                            "error_type": "MissingMount",
                        })
                    elif prepared is not None:
                        try:
                            self._verify_mount(prepared, receipt.mount_id)
                        except BaseException as exc:
                            failures.append({
                                "bind_path": alias,
                                "mount_id": receipt.mount_id,
                                "stage": "mount_identity_before_revoke",
                                "error_type": type(exc).__name__,
                            })
                except BaseException as exc:
                    found = None
                    failures.append({
                        "bind_path": alias,
                        "mount_id": receipt.mount_id,
                        "stage": "mountinfo_before_revoke",
                        "error_type": type(exc).__name__,
                    })

                if found is None or found:
                    try:
                        self._command_runner(("umount", alias))
                    except BaseException as exc:
                        failures.append({
                            "bind_path": alias,
                            "mount_id": receipt.mount_id,
                            "stage": "umount",
                            "error_type": type(exc).__name__,
                        })

                try:
                    if self._mounts_at(alias):
                        residual_aliases.append(alias)
                except BaseException as exc:
                    residual_aliases.append(alias)
                    failures.append({
                        "bind_path": alias,
                        "mount_id": receipt.mount_id,
                        "stage": "mountinfo_after_revoke",
                        "error_type": type(exc).__name__,
                    })

            if failures:
                self._faulted = True
                try:
                    failure_digest = self._record_revocation_failure(
                        active,
                        failures,
                        residual_aliases,
                    )
                except BaseException as exc:
                    raise PermissionError(
                        "role mount revocation failed and failure evidence could not be persisted"
                    ) from exc
                self._revocation_failures[active.phase_id] = failure_digest
                raise PermissionError(
                    "role mount revocation failed; durable failure evidence was written"
                )

            body: dict[str, object] = {
                "schema": "route2_mount_revocation_v1",
                "manifest_sha256": active.mounts[0].manifest_sha256,
                "controller_run_id": active.controller_run_id,
                "phase_id": active.phase_id,
                "role_id": active.mounts[0].role_id,
                "activation_receipt_sha256": active.receipt_sha256,
                "mounts": [
                    {"bind_path": item.bind_path, "mount_id": item.mount_id}
                    for item in active.mounts
                ],
                "revoked_at_ns": time.time_ns(),
            }
            path = self._receipt_root / f"revocation-{active.controller_run_id}-{active.phase_id}.json"
            try:
                self._ensure_receipt_root()
                digest = _durable_write(path, body, self._directory_sync)
            except BaseException as exc:
                self._faulted = True
                persistence_failure = [{
                    "bind_path": "",
                    "mount_id": 0,
                    "stage": "revocation_receipt_persist",
                    "error_type": type(exc).__name__,
                }]
                try:
                    self._revocation_failures[active.phase_id] = self._record_revocation_failure(
                        active,
                        persistence_failure,
                        (),
                    )
                except BaseException:
                    pass
                raise PermissionError(
                    "role mount revocation failed and failure evidence could not be persisted"
                ) from exc
            self._revoked[active.phase_id] = (active, digest)
            self._active = None
            return digest
