"""Root-only admission bootstrap for the immutable Route 2 source/runtime.

The controller policy, HMAC key, and sealed A+B artifact live outside the
hashed source and runtime trees.  This module refuses to install
``FROZEN_ADMISSION`` until those files, the complete pinned snapshots, and the
read-only Linux mounts have all been verified in the current root process.
It never opens registered project inputs or GT views.

The formal image must install this module in the reviewed source snapshot and
provide the root-owned external controller files.  No such files are present
in the preparation workspace, so the bootstrap fails closed here.
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
import threading
from typing import Any

from . import contracts, external_admission, runtime_identity, source_snapshot
from .contracts import FrozenAdmission, STUDY_ID
from .external_admission import load_controller_sealed_admission
from .linux_start_clock import (
    LinuxStartClockProof, claim_preimport_start_for_ab,
    consume_preimport_start_clock, take_inherited_start_fd,
)
from .source_snapshot import (
    ReadonlyMountProof,
    SourceSnapshotProof,
    require_controller_owned_readonly_tree,
    require_readonly_mount,
    verify_snapshot_module,
    verify_source_snapshot,
)


DEFAULT_SUPERVISOR_CONFIG = Path(
    "/etc/route2/route2-candidate-overlap-v1-001-supervisor.json"
)
MAX_SUPERVISOR_CONFIG_BYTES = 1 << 16
MAX_CONTROLLER_KEY_BYTES = 1 << 12
MAX_SEALED_ADMISSION_BYTES = 1 << 20
MAX_SOURCE_MANIFEST_BYTES = 1 << 24
_SCHEMA = "route2_external_supervisor_config_v1"
_EXPECTED_BOOTSTRAP_MODULE = (
    "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
)
_EXPECTED_RUNTIME_IDENTITY_MODULE = (
    "src/eating_event/route2_candidate_overlap/runtime_identity.py"
)
_EXPECTED_SOURCE_SNAPSHOT_MODULE = (
    "src/eating_event/route2_candidate_overlap/source_snapshot.py"
)
_RUNTIME_IDENTITY_RELATIVE = "requirements/route2-linux-cp310.identity.json"
_RUNTIME_LOCK_RELATIVE = "requirements/route2-linux-cp310.lock"
_CONFIG_FIELDS = frozenset({
    "schema", "study_id", "controller_key_path", "sealed_admission_path",
    "source_snapshot_root", "source_manifest_path", "source_snapshot_sha256",
    "source_module_relative_path", "runtime_snapshot_root",
    "runtime_manifest_path", "runtime_snapshot_sha256", "source_mount_path",
    "runtime_mount_path", "independent_review_id", "owner_approval_id",
    "authorization_card_sha256",
})
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_INSTALL_LOCK = threading.Lock()
_ISSUED_BOOTSTRAP: _IssuedBootstrap | None = None


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate controller configuration key")
        value[key] = item
    return value


def _canonical_absolute_path(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise PermissionError(f"{name} must be an absolute canonical Linux path")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or path.as_posix() != value
        or ".." in path.parts
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        raise PermissionError(f"{name} is not an absolute canonical Linux path")
    return value


def _path_is_within(path: str, root: str) -> bool:
    return PurePosixPath(path) == PurePosixPath(root) or PurePosixPath(root) in PurePosixPath(path).parents


@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    study_id: str
    controller_key_path: str
    sealed_admission_path: str
    source_snapshot_root: str
    source_manifest_path: str
    source_snapshot_sha256: str
    source_module_relative_path: str
    runtime_snapshot_root: str
    runtime_manifest_path: str
    runtime_snapshot_sha256: str
    source_mount_path: str
    runtime_mount_path: str
    independent_review_id: str
    owner_approval_id: str
    authorization_card_sha256: str


def parse_supervisor_config(encoded: bytes) -> SupervisorConfig:
    """Parse one canonical, exact-field, no-secret controller policy record."""

    if type(encoded) is not bytes or not encoded or len(encoded) > MAX_SUPERVISOR_CONFIG_BYTES:
        raise PermissionError("external supervisor configuration is empty or oversized")
    try:
        value: Any = json.loads(encoded, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PermissionError("external supervisor configuration is invalid JSON") from exc
    try:
        canonical = _canonical(value)
    except (UnicodeError, TypeError, ValueError, RecursionError) as exc:
        raise PermissionError("external supervisor configuration cannot be canonicalized") from exc
    if not isinstance(value, dict) or canonical != encoded:
        raise PermissionError("external supervisor configuration is not canonical JSON")
    if set(value) != _CONFIG_FIELDS:
        raise PermissionError("external supervisor configuration has unknown or missing fields")
    if value.get("schema") != _SCHEMA or value.get("study_id") != STUDY_ID:
        raise PermissionError("external supervisor configuration has the wrong schema or study ID")

    paths = {
        name: _canonical_absolute_path(value.get(name), name)
        for name in (
            "controller_key_path", "sealed_admission_path", "source_snapshot_root",
            "source_manifest_path", "runtime_snapshot_root", "runtime_manifest_path",
            "source_mount_path", "runtime_mount_path",
        )
    }
    for name in ("source_snapshot_sha256", "runtime_snapshot_sha256", "authorization_card_sha256"):
        digest = value.get(name)
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise PermissionError(f"external supervisor {name} is not a lowercase SHA-256")
    for name in ("independent_review_id", "owner_approval_id"):
        if not isinstance(value.get(name), str) or not _IDENTITY_RE.fullmatch(value[name]):
            raise PermissionError(f"external supervisor {name} is malformed")

    module_relative = value.get("source_module_relative_path")
    if module_relative != _EXPECTED_BOOTSTRAP_MODULE:
        raise PermissionError("external supervisor points outside the reviewed bootstrap module")
    source_root = paths["source_snapshot_root"]
    runtime_root = paths["runtime_snapshot_root"]
    controller_files = (
        paths["controller_key_path"],
        paths["sealed_admission_path"],
        paths["source_manifest_path"],
        paths["runtime_manifest_path"],
    )
    if (
        source_root == runtime_root
        or _path_is_within(source_root, runtime_root)
        or _path_is_within(runtime_root, source_root)
        or len(set(controller_files)) != len(controller_files)
        or paths["source_mount_path"] != source_root
        or paths["runtime_mount_path"] != runtime_root
        or any(
            _path_is_within(manifest, root)
            for manifest in controller_files[2:]
            for root in (source_root, runtime_root)
        )
    ):
        raise PermissionError(
            "external supervisor snapshot roots, mounts or controller files must stay distinct"
        )
    for name in ("controller_key_path", "sealed_admission_path"):
        if any(_path_is_within(paths[name], root) for root in (source_root, runtime_root)):
            raise PermissionError("controller key and admission seal must stay outside snapshots")

    return SupervisorConfig(
        study_id=STUDY_ID,
        controller_key_path=paths["controller_key_path"],
        sealed_admission_path=paths["sealed_admission_path"],
        source_snapshot_root=source_root,
        source_manifest_path=paths["source_manifest_path"],
        source_snapshot_sha256=value["source_snapshot_sha256"],
        source_module_relative_path=module_relative,
        runtime_snapshot_root=runtime_root,
        runtime_manifest_path=paths["runtime_manifest_path"],
        runtime_snapshot_sha256=value["runtime_snapshot_sha256"],
        source_mount_path=paths["source_mount_path"],
        runtime_mount_path=paths["runtime_mount_path"],
        independent_review_id=value["independent_review_id"],
        owner_approval_id=value["owner_approval_id"],
        authorization_card_sha256=value["authorization_card_sha256"],
    )


def _effective_uid() -> int:
    getuid = getattr(os, "geteuid", None)
    return getuid() if getuid is not None else -1


def _require_linux_root() -> None:
    if platform.system() != "Linux" or _effective_uid() != 0:
        raise PermissionError("Route 2 admission bootstrap requires Linux root")


def _check_root_owned_directory_chain(parent: Path) -> None:
    if not parent.is_absolute():
        raise PermissionError("controller file parent must be absolute")
    for path in reversed((parent, *parent.parents)):
        try:
            info = path.lstat()
        except OSError as exc:
            raise PermissionError("controller file parent is unavailable") from exc
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("controller file parent is linked, mutable or not root-owned")


def _read_protected_file(path_value: str | Path, *, max_bytes: int) -> bytes:
    """Read one root-only immutable file without following its final symlink."""

    if os.name != "posix" or type(max_bytes) is not int or max_bytes <= 0:
        raise PermissionError("protected controller files require Linux and a fixed size limit")
    path = Path(path_value)
    if not path.is_absolute() or path.as_posix() != str(path_value):
        raise PermissionError("protected controller path is not canonical and absolute")
    if ".." in PurePosixPath(path.as_posix()).parts:
        raise PermissionError("protected controller path contains parent traversal")
    _check_root_owned_directory_chain(path.parent)
    try:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_uid != 0
            or stat.S_IMODE(before.st_mode) != 0o400
            or before.st_nlink != 1
            or before.st_size > max_bytes
        ):
            raise PermissionError("controller file is not a root-owned, single-link 0400 regular file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags)
    except PermissionError:
        raise
    except OSError as exc:
        raise PermissionError("protected controller file could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != 0
            or stat.S_IMODE(opened.st_mode) != 0o400
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise PermissionError("protected controller file changed during safe open")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, max_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > max_bytes:
                raise PermissionError("protected controller file exceeds its fixed size limit")
        after = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or total != opened.st_size
        ):
            raise PermissionError("protected controller file changed while being read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_snapshot_manifest(path_value: str, *, max_bytes: int) -> bytes:
    path = Path(path_value)
    if not path.is_absolute() or path.as_posix() != path_value or ".." in PurePosixPath(path_value).parts:
        raise PermissionError("snapshot manifest path is not canonical and absolute")
    _check_root_owned_directory_chain(path.parent)
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != 0
            or info.st_nlink != 1
            or info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            or info.st_size > max_bytes
        ):
            raise PermissionError("snapshot manifest is not a root-owned immutable regular file")
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
        )
    except PermissionError:
        raise
    except OSError as exc:
        raise PermissionError("snapshot manifest could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != 0
            or opened.st_nlink != 1
            or opened.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise PermissionError("snapshot manifest changed during safe open")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, max_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > max_bytes:
                raise PermissionError("snapshot manifest exceeds its fixed size limit")
        after = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or total != opened.st_size
        ):
            raise PermissionError("snapshot manifest changed while being read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_mountinfo() -> str:
    if platform.system() != "Linux":
        raise PermissionError("Route 2 mount verification requires Linux")
    try:
        return Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    except OSError as exc:
        raise PermissionError("Linux mount namespace evidence is unavailable") from exc


@dataclass(frozen=True, slots=True)
class SnapshotBootstrapProof:
    source: SourceSnapshotProof
    runtime: SourceSnapshotProof
    source_mount: ReadonlyMountProof
    runtime_mount: ReadonlyMountProof


def _verify_live_snapshots(
    config: SupervisorConfig,
    *,
    source_manifest_bytes: bytes,
    runtime_manifest_bytes: bytes,
    mountinfo_text: str,
) -> SnapshotBootstrapProof:
    source_root = Path(config.source_snapshot_root)
    runtime_root = Path(config.runtime_snapshot_root)
    if (
        source_snapshot.verify_snapshot_module is not verify_snapshot_module
        or source_snapshot.verify_source_snapshot is not verify_source_snapshot
        or source_snapshot.require_readonly_mount is not require_readonly_mount
        or source_snapshot.require_controller_owned_readonly_tree
        is not require_controller_owned_readonly_tree
    ):
        raise PermissionError("snapshot verifier functions differ from their imported module")
    module_proof = verify_snapshot_module(
        source_root,
        Path(__file__),
        source_manifest_bytes,
        expected_manifest_sha256=config.source_snapshot_sha256,
        expected_module_relative_path=_EXPECTED_BOOTSTRAP_MODULE,
        mount_path=config.source_mount_path,
        mountinfo_text=mountinfo_text,
    )
    if module_proof.mount.mount_point != config.source_mount_path:
        raise PermissionError("source snapshot is not on its exact reviewed read-only mount")
    source_root_real = source_root.resolve(strict=True)
    for module_name, relative in (
        (contracts.__name__, "src/eating_event/route2_candidate_overlap/contracts.py"),
        (
            external_admission.__name__,
            "src/eating_event/route2_candidate_overlap/external_admission.py",
        ),
        (runtime_identity.__name__, _EXPECTED_RUNTIME_IDENTITY_MODULE),
        (source_snapshot.__name__, _EXPECTED_SOURCE_SNAPSHOT_MODULE),
    ):
        module_path = Path(sys.modules[module_name].__file__ or "")
        try:
            imported_relative = module_path.resolve(strict=True).relative_to(source_root_real).as_posix()
        except (OSError, ValueError) as exc:
            raise PermissionError("Route 2 admission code was imported outside the pinned source tree") from exc
        if imported_relative != relative:
            raise PermissionError("Route 2 admission module path differs from its frozen source identity")
    require_controller_owned_readonly_tree(source_root)

    runtime_proof = verify_source_snapshot(
        runtime_root,
        runtime_manifest_bytes,
        expected_manifest_sha256=config.runtime_snapshot_sha256,
    )
    runtime_mount = require_readonly_mount(config.runtime_mount_path, mountinfo_text)
    if runtime_mount.mount_point != config.runtime_mount_path:
        raise PermissionError("runtime snapshot is not on its exact reviewed read-only mount")
    require_controller_owned_readonly_tree(runtime_root)
    return SnapshotBootstrapProof(
        source=module_proof.snapshot,
        runtime=runtime_proof,
        source_mount=module_proof.mount,
        runtime_mount=runtime_mount,
    )


@dataclass(frozen=True, slots=True)
class SupervisorBootstrapProof:
    study_id: str
    config_sha256: str
    seal_sha256: str
    source_snapshot_sha256: str
    runtime_snapshot_sha256: str
    independent_review_id: str
    owner_approval_id: str
    authorization_card_sha256: str
    frozen_admission: FrozenAdmission
    snapshots: SnapshotBootstrapProof
    start_clock: LinuxStartClockProof | None = None


@dataclass(slots=True)
class _IssuedBootstrap:
    proof: SupervisorBootstrapProof
    pid: int
    thread: threading.Thread
    consumed: bool = False


def claim_bootstrap_for_ab(proof: SupervisorBootstrapProof) -> FrozenAdmission:
    """Consume the live bootstrap handoff once in its issuing process/thread.

    A serialized or reconstructed proof is evidence only. It cannot recreate
    this handoff, including after a fork. This check supplies continuity; the
    protected seal/review/owner checks in bootstrap supply authorization.
    """
    with _INSTALL_LOCK:
        issued = _ISSUED_BOOTSTRAP
        if type(proof) is not SupervisorBootstrapProof or issued is None or issued.proof is not proof:
            raise PermissionError("A+B requires the live issued bootstrap proof")
        if issued.consumed:
            raise PermissionError("bootstrap A+B handoff has already been consumed")
        # A genuine handoff attempt is one-shot, even when a later check fails.
        issued.consumed = True
        claim_preimport_start_for_ab(
            proof.start_clock, config_sha256=proof.config_sha256,
            seal_sha256=proof.seal_sha256,
        )
        if (
            os.getpid() != issued.pid
            or threading.current_thread() is not issued.thread
            or contracts.FROZEN_ADMISSION is not proof.frozen_admission
            or type(proof.frozen_admission) is not FrozenAdmission
        ):
            raise PermissionError("bootstrap process, thread or frozen admission changed")
        return proof.frozen_admission


def _read_verified_source_file(root: Path, relative: str, *, max_bytes: int) -> bytes:
    name = PurePosixPath(relative)
    if name.is_absolute() or name.as_posix() != relative or ".." in name.parts:
        raise PermissionError("runtime identity source path is not canonical and relative")
    root_real = root.resolve(strict=True)
    path = root_real.joinpath(*name.parts)
    try:
        if path.is_symlink() or not path.is_file():
            raise PermissionError("runtime identity source file is not a regular snapshot file")
        resolved = path.resolve(strict=True)
        if resolved.relative_to(root_real).as_posix() != relative:
            raise PermissionError("runtime identity source file escaped the snapshot root")
        info = resolved.stat()
        if info.st_size > max_bytes:
            raise PermissionError("runtime identity source file exceeds its fixed size limit")
        data = resolved.read_bytes()
    except PermissionError:
        raise
    except (OSError, ValueError) as exc:
        raise PermissionError("runtime identity source file is unavailable") from exc
    if len(data) != info.st_size or len(data) > max_bytes:
        raise PermissionError("runtime identity source file changed while it was read")
    return data


def _verify_runtime_execution(config: SupervisorConfig, frozen: FrozenAdmission) -> None:
    """Bind this live interpreter and ABI to the pinned, immutable venv tree."""

    source_root = Path(config.source_snapshot_root)
    identity_bytes = _read_verified_source_file(
        source_root, _RUNTIME_IDENTITY_RELATIVE, max_bytes=MAX_SOURCE_MANIFEST_BYTES,
    )
    lock_bytes = _read_verified_source_file(
        source_root, _RUNTIME_LOCK_RELATIVE, max_bytes=1 << 20,
    )
    if (
        hashlib.sha256(identity_bytes).hexdigest() != frozen.linux_identity_sha256.lower()
        or hashlib.sha256(lock_bytes).hexdigest() != frozen.linux_lock_sha256.lower()
    ):
        raise PermissionError("Linux ABI identity or hashed dependency lock differs from admission")
    try:
        identity: Any = json.loads(identity_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PermissionError("Linux runtime identity is not valid JSON") from exc
    if (
        not isinstance(identity, dict)
        or set(identity) != {"schema", "study_id", "status", "runtime", "requirements", "wheelhouse"}
        or identity.get("schema") != "route2-linux-dependency-identity-v1"
        or identity.get("study_id") != STUDY_ID
        or identity.get("status") != "PREPARATION_ONLY_NOT_EXPERIMENT_AUTHORIZED"
        or not isinstance(identity.get("runtime"), dict)
        or not isinstance(identity.get("requirements"), dict)
        or identity["requirements"].get("path") != _RUNTIME_LOCK_RELATIVE
        or identity["requirements"].get("sha256") != hashlib.sha256(lock_bytes).hexdigest()
        or identity["runtime"].get("venv_path") != config.runtime_snapshot_root
    ):
        raise PermissionError("Linux runtime identity metadata differs from the pinned source snapshot")
    runtime_identity._require_linux_runtime(identity["runtime"], lock_bytes, frozen)


def _require_frozen_bindings(config: SupervisorConfig, frozen: FrozenAdmission) -> None:
    if type(frozen) is not FrozenAdmission:
        raise PermissionError("controller seal returned an invalid frozen admission")
    if (
        frozen.source_snapshot_root != config.source_snapshot_root
        or frozen.source_snapshot_manifest_path != config.source_manifest_path
        or frozen.source_snapshot_sha256 != config.source_snapshot_sha256
        or frozen.runtime_snapshot_root != config.runtime_snapshot_root
        or frozen.runtime_snapshot_manifest_path != config.runtime_manifest_path
        or frozen.runtime_snapshot_sha256 != config.runtime_snapshot_sha256
        or frozen.approval_record != config.owner_approval_id
    ):
        raise PermissionError("controller seal frozen paths and hashes differ from supervisor policy")


def _read_preimport_inputs(config_path: str | Path, start_fd: int):
    """Read protected inputs and close the inherited start fd even on failure."""
    try:
        return _verified_preimport_inputs(config_path, start_fd)
    finally:
        os.close(start_fd)


def _verified_preimport_inputs(config_path: str | Path, start_fd: int):
    config_path_obj = Path(config_path)
    if not config_path_obj.is_absolute():
        raise PermissionError("external supervisor configuration path must be absolute")
    config_bytes = _read_protected_file(
        config_path_obj,
        max_bytes=MAX_SUPERVISOR_CONFIG_BYTES,
    )
    config = parse_supervisor_config(config_bytes)
    config_path_posix = config_path_obj.as_posix()
    if (
        config_path_posix in {
            config.controller_key_path,
            config.sealed_admission_path,
            config.source_manifest_path,
            config.runtime_manifest_path,
        }
        or any(
            _path_is_within(config_path_posix, root)
            for root in (config.source_snapshot_root, config.runtime_snapshot_root)
        )
        or _path_is_within(config_path_posix, "/var/lib/route2/studies")
    ):
        raise PermissionError(
            "external supervisor configuration overlaps protected files, snapshots or study output"
        )

    key = _read_protected_file(config.controller_key_path, max_bytes=MAX_CONTROLLER_KEY_BYTES)
    artifact = _read_protected_file(
        config.sealed_admission_path,
        max_bytes=MAX_SEALED_ADMISSION_BYTES,
    )
    if len(key) < 32:
        raise PermissionError("external controller key is shorter than 256 bits")
    start_clock = consume_preimport_start_clock(
        start_fd, config_path=config_path_posix,
        config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        seal_sha256=hashlib.sha256(artifact).hexdigest(),
    )
    return config_bytes, config, key, artifact, start_clock


def bootstrap_frozen_admission(
    config_path: str | Path = DEFAULT_SUPERVISOR_CONFIG,
) -> SupervisorBootstrapProof:
    """Require pre-import continuity, then verify and install A+B admission.

    The inherited token is consumed before snapshot/runtime verification. A
    direct call without it, a forged token, or an already claimed invocation
    refuses. This admission step opens no project input or GT, creates no
    study image, and issues no review/owner decision.
    """
    global _ISSUED_BOOTSTRAP
    _require_linux_root()
    if contracts.FROZEN_ADMISSION is not None or _ISSUED_BOOTSTRAP is not None:
        raise PermissionError("Route 2 frozen admission has already been installed")
    start_fd = take_inherited_start_fd()
    config_bytes, config, key, artifact, start_clock = _read_preimport_inputs(config_path, start_fd)
    source_manifest = _read_snapshot_manifest(
        config.source_manifest_path,
        max_bytes=MAX_SOURCE_MANIFEST_BYTES,
    )
    runtime_manifest = _read_snapshot_manifest(
        config.runtime_manifest_path,
        max_bytes=MAX_SOURCE_MANIFEST_BYTES,
    )
    snapshots = _verify_live_snapshots(
        config,
        source_manifest_bytes=source_manifest,
        runtime_manifest_bytes=runtime_manifest,
        mountinfo_text=_read_mountinfo(),
    )
    frozen = load_controller_sealed_admission(
        artifact,
        controller_key=key,
        expected_source_snapshot_sha256=config.source_snapshot_sha256,
        expected_runtime_snapshot_sha256=config.runtime_snapshot_sha256,
        expected_review_id=config.independent_review_id,
        expected_owner_approval_id=config.owner_approval_id,
        expected_authorization_card_sha256=config.authorization_card_sha256,
    )
    _require_frozen_bindings(config, frozen)
    _verify_runtime_execution(config, frozen)
    proof = SupervisorBootstrapProof(
        study_id=STUDY_ID,
        config_sha256=hashlib.sha256(config_bytes).hexdigest(),
        seal_sha256=hashlib.sha256(artifact).hexdigest(),
        source_snapshot_sha256=snapshots.source.manifest_sha256,
        runtime_snapshot_sha256=snapshots.runtime.manifest_sha256,
        independent_review_id=config.independent_review_id,
        owner_approval_id=config.owner_approval_id,
        authorization_card_sha256=config.authorization_card_sha256,
        frozen_admission=frozen,
        snapshots=snapshots,
        start_clock=start_clock,
    )
    with _INSTALL_LOCK:
        if contracts.FROZEN_ADMISSION is not None or _ISSUED_BOOTSTRAP is not None:
            raise PermissionError("Route 2 frozen admission was concurrently installed")
        _ISSUED_BOOTSTRAP = _IssuedBootstrap(proof, os.getpid(), threading.current_thread())
        contracts.FROZEN_ADMISSION = frozen
    return proof
