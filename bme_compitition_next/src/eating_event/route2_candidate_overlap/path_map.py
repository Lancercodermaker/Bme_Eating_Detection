"""Exact logical-input to Linux bind-mount mapping for the Route 2 worker.

The reviewed manifest contains metadata only.  A separate, privileged Linux
controller must issue mount receipts to a short-lived phase worker.  In
particular, the manifest never causes an unreleased GT file to be opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import threading
from typing import Any, BinaryIO, Iterator

from .contracts import (
    OUTER_CONTROL_CANDIDATES_PHASE,
    OUTER_CONTROL_FINAL_MATCHES_PHASE,
    STUDY_ID,
    StudyStage,
    require_frozen_admission,
)


_METADATA = "preflight_metadata"
_STAGE_A_INPUT = "stage_a_input"
_STAGE_A_REFERENCE = StudyStage.STAGE_A_REFERENCE.value
_OUTER_CONTROL_CANDIDATES = OUTER_CONTROL_CANDIDATES_PHASE
_ROLE_VIEW_PHASES = frozenset({
    _STAGE_A_INPUT, _STAGE_A_REFERENCE, _OUTER_CONTROL_CANDIDATES,
})
_GT_PHASES = frozenset({
    StudyStage.TRAIN_LABELS.value,
    StudyStage.INNER_EVALUATION.value,
    StudyStage.OUTER_EVALUATION.value,
})
_PHASES = frozenset({_METADATA, OUTER_CONTROL_FINAL_MATCHES_PHASE}) | _ROLE_VIEW_PHASES | _GT_PHASES
_STUDY_ROLE = "__study__"
_MANIFEST_V1 = "route2_exact_path_map_v1"
_MANIFEST_V2 = "route2_exact_path_map_v2"
_DIRECTORY_BIND_ROOT = "/run/route2-input"
# Dispatch marker only. The fixed private native owner independently verifies
# issuance and actual OS facts; neither this reference nor a schema grants IO.
_NATIVE_CONTEXT = None


def _sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _logical_windows_path(value: str) -> bool:
    path = PureWindowsPath(value)
    return (
        bool(value) and path.is_absolute() and len(path.drive) == 2
        and path.drive[1] == ":" and ".." not in path.parts
        and str(path) == value
    )


def _linux_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and path.is_absolute() and ".." not in path.parts and str(path) == value


def _key(
    logical_path: str, sha256: str, role_id: str, phase: str,
) -> tuple[str, str, str, str]:
    return logical_path, sha256.lower(), role_id, phase


def canonical_manifest_bytes(
    bind_root: str, entries: tuple["ExactFileMapping", ...], *, schema: str = _MANIFEST_V1,
) -> bytes:
    """Encode reviewed metadata without opening or copying any input file."""

    if not _linux_path(bind_root) or not entries:
        raise ValueError("manifest requires an absolute Linux bind root and exact files")
    if schema not in {_MANIFEST_V1, _MANIFEST_V2}:
        raise ValueError("unknown exact path-map manifest schema")
    ordered = sorted(entries, key=lambda item: item.key)
    if schema == _MANIFEST_V2:
        if bind_root != _DIRECTORY_BIND_ROOT or any(
            item != directory_file_mapping(item.logical_path, item.sha256,
                role_id=item.role_id, phase=item.phase) for item in ordered
        ):
            raise PermissionError("directory map requires its fixed derived exact aliases")
        wire = [{name: getattr(item, name) for name in ("logical_path", "sha256", "role_id", "phase")}
                for item in ordered]
    else:
        wire = [asdict(item) for item in ordered]
    payload = {
        "schema": schema,
        "study_id": STUDY_ID,
        "bind_root": bind_root,
        "entries": wire,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def file_mapping(
    logical_path: str,
    sha256: str,
    *,
    role_id: str,
    phase: str,
    bind_root: str,
) -> "ExactFileMapping":
    """Give one exact reviewed identity an opaque, deterministic file alias."""

    if not _linux_path(bind_root):
        raise ValueError("bind root must be a canonical Linux absolute path")
    identity = json.dumps(
        _key(logical_path, sha256, role_id, phase),
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    alias = str(PurePosixPath(bind_root) / hashlib.sha256(identity).hexdigest())
    return ExactFileMapping(logical_path, sha256, role_id, phase, alias)


def directory_file_mapping(logical_path: str, sha256: str, *, role_id: str,
                           phase: str) -> "ExactFileMapping":
    """Derive v2 aliases from reviewed identities, without granting native IO."""
    root = PurePosixPath(_DIRECTORY_BIND_ROOT)
    if phase == _METADATA:
        root /= "metadata"
    elif phase in _ROLE_VIEW_PHASES:
        root = root / "roles" / hashlib.sha256(role_id.encode("utf-8")).hexdigest()
    return file_mapping(logical_path, sha256, role_id=role_id, phase=phase, bind_root=str(root))


@dataclass(frozen=True, slots=True)
class ExactFileMapping:
    logical_path: str
    sha256: str
    role_id: str
    phase: str
    bind_path: str

    def __post_init__(self) -> None:
        if (
            not _logical_windows_path(self.logical_path)
            or not _sha256(self.sha256)
            or not self.role_id or self.phase not in _PHASES
            or not _linux_path(self.bind_path)
            or (self.phase == _METADATA and self.role_id != _STUDY_ROLE)
            or (self.phase != _METADATA and self.role_id == _STUDY_ROLE)
        ):
            raise ValueError("file mapping needs an exact Windows identity and Linux bind alias")

    @property
    def key(self) -> tuple[str, str, str, str]:
        return _key(self.logical_path, self.sha256, self.role_id, self.phase)


@dataclass(frozen=True, slots=True)
class MountReceipt:
    """OS-controller evidence for one currently visible read-only file bind.

    The Python object is not an authorization token.  It is useful only when
    the external controller has installed the corresponding isolated mount
    namespace and the worker can observe the exact read-only mount ID.
    """

    manifest_sha256: str
    logical_path: str
    sha256: str
    role_id: str
    phase: str
    bind_path: str
    mount_id: int
    release_ledger_event_sha256: str = ""

    def __post_init__(self) -> None:
        ExactFileMapping(
            self.logical_path, self.sha256, self.role_id, self.phase, self.bind_path
        )
        if (
            not _sha256(self.manifest_sha256)
            or type(self.mount_id) is not int or self.mount_id <= 0
            or (self.phase in _GT_PHASES and not _sha256(self.release_ledger_event_sha256))
            or (self.phase not in _GT_PHASES and self.release_ledger_event_sha256 != "")
        ):
            raise ValueError("mount receipt lacks an exact runtime mount or GT release")

    @property
    def key(self) -> tuple[str, str, str, str]:
        return _key(self.logical_path, self.sha256, self.role_id, self.phase)


@dataclass(frozen=True, slots=True)
class ActiveRoleMountSet:
    """One controller-issued, temporary non-GT role view.

    The controller is responsible for making these mounts in the worker's
    private mount namespace.  This value only binds the exact receipt set that
    the Python reader is allowed to use; it cannot create mount authority.
    """

    controller_run_id: str
    phase_id: str
    receipt_sha256: str
    mounts: tuple[MountReceipt, ...]

    def __post_init__(self) -> None:
        if any(type(item) is not MountReceipt for item in self.mounts):
            raise PermissionError("active role mount set contains an invalid receipt type")
        keys = [item.key for item in self.mounts]
        mount_ids = [item.mount_id for item in self.mounts]
        if (
            not self.controller_run_id or not self.phase_id
            or not _sha256(self.receipt_sha256)
            or not self.mounts or len(keys) != len(set(keys))
            or len(mount_ids) != len(set(mount_ids))
        ):
            raise PermissionError("active role mount set lacks a unique sealed controller receipt")


class RoleMountController:
    """Structural interface for the privileged, out-of-worker mount broker."""

    def activate_role_view(
        self,
        *,
        manifest_sha256: str,
        manifest_bytes: bytes,
        role_id: str,
        mappings: tuple[ExactFileMapping, ...],
    ) -> ActiveRoleMountSet:
        raise NotImplementedError

    def revoke_role_view(self, active: ActiveRoleMountSet) -> str:
        """Revoke all aliases and return the durable revocation receipt SHA-256."""
        raise NotImplementedError


def _mount_id_and_readonly(path: str) -> tuple[int, bool]:
    """Read the worker's own mount namespace; aliases must be file mounts."""

    if os.name != "posix" or not Path("/proc/self/mountinfo").is_file():
        raise PermissionError("WSL worker requires Linux mount namespace evidence")
    matches: list[tuple[int, bool]] = []
    with open("/proc/self/mountinfo", "r", encoding="utf-8") as stream:
        for line in stream:
            left, separator, _ = line.partition(" - ")
            if not separator:
                raise PermissionError("malformed Linux mountinfo")
            fields = left.split()
            if len(fields) < 6:
                raise PermissionError("malformed Linux mountinfo fields")
            # mountinfo escapes spaces and other separators as octal bytes.
            mount_point = re.sub(
                r"\\([0-7]{3})",
                lambda match: chr(int(match.group(1), 8)),
                fields[4],
            )
            if mount_point == path:
                matches.append((int(fields[0]), "ro" in fields[5].split(",")))
    if len(matches) != 1:
        raise PermissionError("approved alias is not one exact Linux bind mount")
    return matches[0]


def _require_safe_alias(path: Path, bind_root: Path) -> None:
    if path == bind_root or bind_root not in path.parents:
        raise PermissionError("mapped input escapes the approved read-only bind root")
    if bind_root.resolve(strict=True) != bind_root:
        raise PermissionError("input bind root traverses a symlink")
    current = bind_root
    for part in path.relative_to(bind_root).parts[:-1]:
        current = current / part
        info = current.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("mapped input parent is mutable or not controller-owned")
    for ancestor in (bind_root, *bind_root.parents):
        info = ancestor.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("input bind root traverses a mutable or noncontroller directory")
    file_info = path.lstat()
    if not stat.S_ISREG(file_info.st_mode) or path.is_symlink():
        raise PermissionError("mapped input must be an ordinary file bind")


def _controller_receipt_bytes(path: Path) -> bytes:
    """Read a controller-sealed file from the worker's protected namespace."""

    if os.name != "posix" or not path.is_absolute():
        raise PermissionError("controller receipt requires Linux absolute path")
    _, readonly = _mount_id_and_readonly(str(path))
    if not readonly:
        raise PermissionError("controller receipt must be a read-only file bind")
    for ancestor in path.parents:
        info = ancestor.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("controller receipt parent is mutable or not root-owned")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("controller receipt is mutable or not root-owned")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _exact_hash(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


class ExactPathMap:
    """An immutable reviewed map with short-lived, OS-observed phase receipts."""

    def __init__(
        self,
        *,
        manifest_sha256: str,
        bind_root: str,
        entries: tuple[ExactFileMapping, ...],
        receipts: tuple[MountReceipt, ...],
        controller_receipt_sha256: str = "",
        controller_run_id: str = "",
        phase_id: str = "",
        mount_controller: RoleMountController | None = None,
        manifest_schema: str = _MANIFEST_V1,
    ) -> None:
        if not _sha256(manifest_sha256) or not _linux_path(bind_root):
            raise ValueError("exact path map needs its reviewed digest and Linux input root")
        if manifest_schema == _MANIFEST_V2 and (
            receipts or mount_controller is not None or controller_receipt_sha256
            or controller_run_id or phase_id
        ):
            raise PermissionError("plain directory maps cannot accept caller mount authority")
        manifest_bytes = canonical_manifest_bytes(bind_root, entries, schema=manifest_schema)
        if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256.lower():
            raise PermissionError("exact path-map digest does not match its canonical manifest")
        if receipts and (
            not _sha256(controller_receipt_sha256)
            or not controller_run_id or not phase_id
        ):
            raise PermissionError("active mappings require a sealed controller receipt")
        root = PurePosixPath(bind_root)
        keys = [item.key for item in entries]
        aliases = [item.bind_path for item in entries]
        if (
            len(keys) != len(set(keys)) or len(aliases) != len(set(aliases))
            or any(root not in PurePosixPath(alias).parents for alias in aliases)
        ):
            raise ValueError("path map repeats an identity or escapes its bind root")
        by_key = {item.key: item for item in entries}
        active: dict[tuple[str, str, str, str], MountReceipt] = {}
        for receipt in receipts:
            mapped = by_key.get(receipt.key)
            if (
                mapped is None or mapped.bind_path != receipt.bind_path
                or receipt.manifest_sha256.lower() != manifest_sha256.lower()
                or receipt.key in active
            ):
                raise PermissionError("mount receipt differs from reviewed exact mapping")
            active[receipt.key] = receipt
        gt_active = [item for item in active.values() if item.phase in _GT_PHASES]
        role_view_active = [item for item in active.values() if item.phase in _ROLE_VIEW_PHASES]
        historical_active = [item for item in active.values() if item.phase == OUTER_CONTROL_FINAL_MATCHES_PHASE]
        if (
            len(gt_active) > 1
            or (gt_active and role_view_active)
            or len({item.role_id for item in role_view_active}) > 1
        ):
            raise PermissionError("worker receipt exposes more than one role or GT phase view")
        if historical_active and (len(historical_active) != 1 or len(gt_active) != 1
                or role_view_active or gt_active[0].phase != StudyStage.OUTER_EVALUATION.value
                or historical_active[0].role_id != gt_active[0].role_id):
            raise PermissionError("historical final matches require the same released outer evaluation view")
        if mount_controller is not None and any(
            item.phase in {*_ROLE_VIEW_PHASES, *_GT_PHASES, OUTER_CONTROL_FINAL_MATCHES_PHASE}
            for item in active.values()
        ):
            raise PermissionError("dynamic role controller cannot reuse static Stage A or GT receipts")
        self.manifest_sha256 = manifest_sha256.lower()
        self.manifest_schema = manifest_schema
        self._manifest_bytes = manifest_bytes
        self.bind_root = Path(bind_root)
        self._entries = by_key
        self._receipts = active
        self.controller_receipt_sha256 = controller_receipt_sha256
        self.controller_run_id = controller_run_id
        self.phase_id = phase_id
        self._base_controller_receipt_sha256 = controller_receipt_sha256
        self._base_controller_run_id = controller_run_id
        self._base_phase_id = phase_id
        self._mount_controller = mount_controller
        self._mount_lock = threading.RLock()
        self._active_role_id: str | None = None
        self._active_role_set: ActiveRoleMountSet | None = None
        self._active_role_depth = 0
        self._active_role_keys: set[tuple[str, str, str, str]] = set()
        self._mount_faulted = False
        self._closed = False

    @classmethod
    def from_bytes(
        cls,
        manifest_bytes: bytes,
        expected_sha256: str,
        *,
        mount_controller: RoleMountController | None = None,
    ) -> "ExactPathMap":
        if not _sha256(expected_sha256) or hashlib.sha256(manifest_bytes).hexdigest() != expected_sha256.lower():
            raise PermissionError("reviewed exact path-map bytes changed")
        value: Any = json.loads(manifest_bytes)
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "study_id", "bind_root", "entries"}
            or value["schema"] not in {_MANIFEST_V1, _MANIFEST_V2}
            or value["study_id"] != STUDY_ID
            or not isinstance(value["entries"], list)
            or not value["entries"]
        ):
            raise PermissionError("exact path-map schema or study identity differs")
        entries: list[ExactFileMapping] = []
        for item in value["entries"]:
            names = {"logical_path", "sha256", "role_id", "phase"}
            if value["schema"] == _MANIFEST_V1:
                names.add("bind_path")
            if not isinstance(item, dict) or set(item) != names:
                raise PermissionError("exact path map contains an unreviewed field")
            entries.append(ExactFileMapping(**item) if value["schema"] == _MANIFEST_V1
                           else directory_file_mapping(**item))
        if canonical_manifest_bytes(value["bind_root"], tuple(entries), schema=value["schema"]) != manifest_bytes:
            raise PermissionError("exact path map is not in its canonical reviewed byte form")
        return cls(
            manifest_sha256=expected_sha256,
            bind_root=value["bind_root"],
            entries=tuple(entries),
            receipts=(),
            mount_controller=mount_controller,
            manifest_schema=value["schema"],
        )

    @classmethod
    def from_controller_receipt(
        cls,
        manifest_bytes: bytes,
        expected_sha256: str,
        receipt_path: Path,
    ) -> "ExactPathMap":
        base = cls.from_bytes(manifest_bytes, expected_sha256)
        if base.manifest_schema != _MANIFEST_V1:
            raise PermissionError("directory maps require the original native owner, never serialized file receipts")
        encoded = _controller_receipt_bytes(receipt_path)
        value: Any = json.loads(encoded)
        if (
            not isinstance(value, dict)
            or set(value) != {
                "schema", "manifest_sha256", "controller_run_id", "phase_id", "mounts"
            }
            or value["schema"] != "route2_mount_receipt_v1"
            or value["manifest_sha256"] != expected_sha256.lower()
            or not isinstance(value["controller_run_id"], str)
            or not value["controller_run_id"]
            or not isinstance(value["phase_id"], str)
            or not value["phase_id"]
            or not isinstance(value["mounts"], list)
            or not value["mounts"]
            or _canonical_json(value) != encoded
        ):
            raise PermissionError("controller mount receipt is incomplete or not canonical")
        mounts: list[MountReceipt] = []
        field_names = {
            "manifest_sha256", "logical_path", "sha256", "role_id", "phase",
            "bind_path", "mount_id", "release_ledger_event_sha256",
        }
        for item in value["mounts"]:
            if not isinstance(item, dict) or set(item) != field_names:
                raise PermissionError("controller receipt contains an unreviewed mount field")
            mounts.append(MountReceipt(**item))
        return cls(
            manifest_sha256=base.manifest_sha256,
            bind_root=str(base.bind_root),
            entries=tuple(base._entries.values()),
            receipts=tuple(mounts),
            controller_receipt_sha256=hashlib.sha256(encoded).hexdigest(),
            controller_run_id=value["controller_run_id"],
            phase_id=value["phase_id"],
        )

    def require_file(
        self,
        logical_path: str,
        sha256: str,
        *,
        role_id: str,
        phase: str,
    ) -> Path:
        """Resolve exactly one released file, checking mount and hash at first use.

        GT hashes are deliberately *not* checked by constructor or preflight.
        A GT worker can call this only after its frozen-prediction ledger gate;
        the external controller must make the phase bind visible only then.
        """

        if self is _NATIVE_CONTEXT or self.manifest_schema == _MANIFEST_V2:
            from .linux_native_path_map import _require_original_metadata_entry
            entry = _require_original_metadata_entry(self, logical_path, sha256, role_id=role_id, phase=phase)
            with self.open_verified(logical_path, sha256, role_id=role_id, phase=phase):
                pass
            return Path(entry.bind_path)
        path, _ = self._require_active_file(
            logical_path, sha256, role_id=role_id, phase=phase
        )
        with self.open_verified(
            logical_path, sha256, role_id=role_id, phase=phase
        ):
            pass
        return path

    def _require_active_file(
        self,
        logical_path: str,
        sha256: str,
        *,
        role_id: str,
        phase: str,
    ) -> tuple[Path, ExactFileMapping]:
        if self is _NATIVE_CONTEXT or self.manifest_schema == _MANIFEST_V2:
            raise PermissionError("directory mount identity is not a legacy individual file receipt")
        if self._closed:
            raise PermissionError("phase path map was closed")
        key = _key(logical_path, sha256, role_id, phase)
        entry = self._entries.get(key)
        receipt = self._receipts.get(key)
        if entry is None or receipt is None:
            raise PermissionError("exact logical file is absent from the active phase mapping")
        path = Path(entry.bind_path)
        _require_safe_alias(path, self.bind_root)
        mount_id, readonly = _mount_id_and_readonly(entry.bind_path)
        if mount_id != receipt.mount_id or not readonly:
            raise PermissionError("phase bind mount ID or read-only flag differs from controller receipt")
        return path, entry

    @contextmanager
    def open_verified(
        self,
        logical_path: str,
        sha256: str,
        *,
        role_id: str,
        phase: str,
    ) -> Iterator[BinaryIO]:
        """Hash and consume identical bytes through one read-only descriptor."""
        if self is _NATIVE_CONTEXT or self.manifest_schema == _MANIFEST_V2:
            from .linux_native_path_map import _open_original_metadata
            with _open_original_metadata(self, logical_path, sha256, role_id=role_id, phase=phase) as stream:
                yield stream
            return
        path, entry = self._require_active_file(
            logical_path, sha256, role_id=role_id, phase=phase
        )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise PermissionError("mapped input descriptor is not a regular file")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                if _exact_hash(stream) != entry.sha256.lower():
                    raise ValueError("released mapped input hash differs from its reviewed registration")
                stream.seek(0)
                yield stream
        finally:
            os.close(descriptor)

    def require_registered(
        self,
        logical_path: str,
        sha256: str,
        *,
        role_id: str,
        phase: str,
    ) -> None:
        """Check map coverage using metadata only; safe before GT release."""

        if self is _NATIVE_CONTEXT:
            from .linux_native_path_map import _require_original_registered
            _require_original_registered(self, logical_path, sha256, role_id=role_id, phase=phase)
            return
        if self._closed or _key(logical_path, sha256, role_id, phase) not in self._entries:
            raise PermissionError("reviewed exact path map omits a required file identity")

    def require_registered_batch(
        self,
        identities: tuple[tuple[str, str, str, str], ...],
    ) -> None:
        """Check bounded ordered coverage; duplicates grant no IO authority."""
        if type(self) is not ExactPathMap or type(identities) is not tuple:
            raise PermissionError("registered coverage batch requires an exact map and identity tuple")
        if self is _NATIVE_CONTEXT:
            from .linux_native_path_map import _require_original_registered_batch
            _require_original_registered_batch(self, identities)
            return
        if (type(self._entries) is not dict or type(self._closed) is not bool
                or self._closed is not False or len(identities) > len(self._entries)):
            raise PermissionError("registered coverage batch requires a live map within its original size")
        for identity in identities:
            if (type(identity) is not tuple or len(identity) != 4
                    or any(type(value) is not str for value in identity)):
                raise PermissionError("registered coverage batch requires exact four-string identity tuples")
            ExactPathMap.require_registered(self, identity[0], identity[1],
                role_id=identity[2], phase=identity[3])

    def receipt_for(
        self,
        logical_path: str,
        sha256: str,
        *,
        role_id: str,
        phase: str,
    ) -> MountReceipt:
        if self is _NATIVE_CONTEXT or self.manifest_schema == _MANIFEST_V2:
            raise PermissionError("shared directory receipts cannot manufacture unique file mount receipts")
        key = _key(logical_path, sha256, role_id, phase)
        if self._closed or key not in self._receipts:
            raise PermissionError("phase has no active controller mount receipt")
        return self._receipts[key]

    @contextmanager
    def lease_role_view(self, role_id: str) -> Iterator[None]:
        """Expose exactly one role's approved non-GT files until its lease is closed.

        The lock spans the lease.  Same-thread nested reads of the same role
        share the controller mount; a different role is rejected while any
        reference remains.  The next role cannot activate until the current
        role has a durable revocation receipt.
        """
        if self is _NATIVE_CONTEXT or self.manifest_schema == _MANIFEST_V2:
            raise PermissionError("actual native directory role publisher is missing; caller controllers are forbidden")
        if not isinstance(role_id, str) or not role_id or role_id == _STUDY_ROLE:
            raise PermissionError("role view requires one registered non-study role")
        self._mount_lock.acquire()
        entered = False
        try:
            if self._closed or self._mount_faulted:
                raise PermissionError("role mount controller is closed or faulted")
            if self._active_role_id is not None:
                if self._active_role_id != role_id:
                    raise PermissionError("another role already has an active controller mount")
                self._active_role_depth += 1
                entered = True
            else:
                if self._mount_controller is None:
                    raise PermissionError("role view requires an active controller mount")
                admission = require_frozen_admission()
                frozen_path_map_sha256 = getattr(admission, "path_map_sha256", "")
                if (
                    not isinstance(frozen_path_map_sha256, str)
                    or frozen_path_map_sha256.lower() != self.manifest_sha256
                ):
                    raise PermissionError("exact path map differs from the frozen admission path-map pin")
                mappings = tuple(sorted(
                    (
                        item for item in self._entries.values()
                        if item.role_id == role_id
                        and item.phase in _ROLE_VIEW_PHASES
                    ),
                    key=lambda item: item.key,
                ))
                if not mappings:
                    raise PermissionError("role view has no exact registered mapping set")
                if {item.phase for item in mappings} != _ROLE_VIEW_PHASES:
                    raise PermissionError("role view must include its exact input, reference, and control mapping sets")
                self._active_role_id = role_id
                self._active_role_depth = 1
                active: ActiveRoleMountSet | None = None
                try:
                    active = self._mount_controller.activate_role_view(
                        manifest_sha256=self.manifest_sha256,
                        manifest_bytes=self._manifest_bytes,
                        role_id=role_id,
                        mappings=mappings,
                    )
                    if type(active) is not ActiveRoleMountSet:
                        raise PermissionError("controller did not return a sealed active role mount set")
                    expected = {item.key: item for item in mappings}
                    received: dict[tuple[str, str, str, str], MountReceipt] = {}
                    for receipt in active.mounts:
                        mapped = expected.get(receipt.key)
                        if (
                            mapped is None
                            or receipt.key in received
                            or receipt.manifest_sha256.lower() != self.manifest_sha256
                            or receipt.bind_path != mapped.bind_path
                            or receipt.role_id != role_id
                            or receipt.phase not in _ROLE_VIEW_PHASES
                        ):
                            raise PermissionError("controller mount differs from the exact registered mapping set")
                        received[receipt.key] = receipt
                    if set(received) != set(expected):
                        raise PermissionError("controller did not activate the exact registered mapping set")
                    self._receipts.update(received)
                    self.controller_receipt_sha256 = active.receipt_sha256.lower()
                    self.controller_run_id = active.controller_run_id
                    self.phase_id = active.phase_id
                    self._active_role_keys = set(received)
                    self._active_role_set = active
                    entered = True
                except BaseException:
                    # A malformed or partial activation still needs explicit
                    # revocation before another role can ever be considered.
                    if active is not None:
                        try:
                            self._mount_controller.revoke_role_view(active)
                        except BaseException:
                            pass
                    self._receipts = {
                        key: receipt for key, receipt in self._receipts.items()
                        if key not in {item.key for item in mappings}
                    }
                    self._active_role_id = None
                    self._active_role_depth = 0
                    self._active_role_set = None
                    self._active_role_keys.clear()
                    self.controller_receipt_sha256 = self._base_controller_receipt_sha256
                    self.controller_run_id = self._base_controller_run_id
                    self.phase_id = self._base_phase_id
                    # Any failed activation invalidates this broker instance,
                    # even when rollback succeeded: its exact mount behavior
                    # no longer matches the reviewed controller contract.
                    self._mount_faulted = True
                    raise
            yield
        finally:
            try:
                if entered:
                    self._active_role_depth -= 1
                    if self._active_role_depth == 0:
                        active = self._active_role_set
                        if active is None or self._mount_controller is None:
                            self._mount_faulted = True
                            self._receipts.clear()
                        else:
                            try:
                                revoke_digest = self._mount_controller.revoke_role_view(active)
                                if not _sha256(revoke_digest):
                                    raise PermissionError("controller revocation receipt is not a SHA-256 digest")
                                for key in self._active_role_keys:
                                    self._receipts.pop(key, None)
                            except BaseException:
                                # Keep the object unusable after uncertain OS state.
                                self._mount_faulted = True
                                for key in self._active_role_keys:
                                    self._receipts.pop(key, None)
                                raise
                            finally:
                                self._active_role_id = None
                                self._active_role_set = None
                                self._active_role_keys.clear()
                                self.controller_receipt_sha256 = self._base_controller_receipt_sha256
                                self.controller_run_id = self._base_controller_run_id
                                self.phase_id = self._base_phase_id
            finally:
                self._mount_lock.release()

    def close(self) -> None:
        if self is _NATIVE_CONTEXT:
            from .linux_native_path_map import _close_original_path_map
            _close_original_path_map(self)
            return
        with self._mount_lock:
            if self._active_role_id is not None:
                raise PermissionError("cannot close a path map while a role mount lease is active")
            self._receipts.clear()
            self._closed = True
