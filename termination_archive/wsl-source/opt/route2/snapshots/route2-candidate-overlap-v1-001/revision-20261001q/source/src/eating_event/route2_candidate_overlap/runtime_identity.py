"""Fail-closed, metadata-only Route 2 runtime identity checks.

This module never opens original A2 role-digests, G1 eligibility, mixed
source artifacts, full source-registration/projection manifests, or physical
GT views. A separately reviewed metadata projection binds only their hashes
and necessary identity pins. All preflight files arrive through
controller-sealed read-only binds.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
import sysconfig
from typing import Any

from .contracts import FrozenAdmission, STUDY_ID
from .path_map import ExactPathMap
from .source_snapshot import (
    require_controller_owned_readonly_tree,
    require_readonly_mount,
    verify_snapshot_module,
    verify_source_snapshot,
)


_METADATA_PHASE = "preflight_metadata"
_METADATA_ROLE = "__study__"
_FILE_NAMES = (
    "admission_metadata_projection", "linux_lock", "linux_identity"
)
_SOURCE_DIGEST_NAMES = (
    "a2_004_config", "a2_004_audit_ready", "a2_004_audit_ready_sidecar",
    "a2_004_role_digests", "g1_eligibility",
)
_ADMISSION_METADATA_KEYS = {
    "schema", "study_id", "status", "experiment_authorization",
    "source_registration_sha256", "projection_manifest_sha256", "identity_pins",
}
_ADMISSION_IDENTITY_PIN_NAMES = (
    "a1_role_graph_sha256", "a2_004_config_sha256", "a2_004_audit_ready_sha256",
    "a2_audit_ready_sidecar_sha256", "a2_004_role_digests_sha256",
    "g1_eligibility_sha256", "role_input_registry_sha256",
    "reference_registry_sha256", "gt_view_registry_sha256", "gt_role_scopes_sha256",
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_object(value: bytes, what: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PermissionError(f"{what} is not valid reviewed JSON") from exc
    if not isinstance(decoded, dict):
        raise PermissionError(f"{what} is not a reviewed JSON object")
    return decoded


def _digest_map(values: object, expected_names: tuple[str, ...], what: str) -> dict[str, str]:
    if not isinstance(values, dict) or set(values) != set(expected_names):
        raise PermissionError(f"{what} digest map is incomplete")
    if any(
        not isinstance(value, str) or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value.lower())
        for value in values.values()
    ):
        raise PermissionError(f"{what} digest map is malformed")
    return values


def _require_pinned_hash(value: bytes, expected: str, what: str) -> None:
    if _sha(value) != expected.lower():
        raise PermissionError(f"{what} actual bytes differ from the frozen SHA-256")


def _require_review_attestation(frozen: FrozenAdmission, encoded: bytes) -> dict[str, Any]:
    attestation = _json_object(encoded, "runtime metadata attestation")
    if (
        set(attestation) != {
            "schema", "study_id", "status", "independent_review_id",
            "metadata_only_sha256", "source_digest_pins",
        }
        or attestation.get("schema") != "route2_runtime_metadata_attestation_v1"
        or attestation.get("study_id") != STUDY_ID
        or attestation.get("status") != "INDEPENDENT_REVIEW_PASS"
        or not isinstance(attestation.get("independent_review_id"), str)
        or not attestation["independent_review_id"]
    ):
        raise PermissionError("runtime metadata lacks an independent review PASS attestation")
    _require_pinned_hash(encoded, frozen.runtime_attestation_sha256, "runtime attestation")
    canonical = json.dumps(
        attestation, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if canonical != encoded:
        raise PermissionError("runtime metadata attestation is not canonical reviewed JSON")
    reviewed_files = _digest_map(
        attestation["metadata_only_sha256"], _FILE_NAMES, "metadata-only"
    )
    reviewed_sources = _digest_map(
        attestation["source_digest_pins"], _SOURCE_DIGEST_NAMES, "source"
    )
    expected = {
        "admission_metadata_projection": frozen.admission_metadata_projection_sha256,
        "linux_lock": frozen.linux_lock_sha256,
        "linux_identity": frozen.linux_identity_sha256,
    }
    if any(reviewed_files[name].lower() != digest.lower() for name, digest in expected.items()):
        raise PermissionError("runtime attestation omits approved metadata-only files")
    source_expectations = {
        "a2_004_config": frozen.a2_004_config_sha256,
        "a2_004_audit_ready": frozen.a2_004_audit_ready_sha256,
        "a2_004_audit_ready_sidecar": frozen.a2_004_audit_ready_sidecar_sha256,
        "a2_004_role_digests": frozen.a2_004_role_digests_sha256,
        "g1_eligibility": frozen.g1_eligibility_sha256,
    }
    if any(
        reviewed_sources[name].lower() != digest.lower()
        for name, digest in source_expectations.items()
    ):
        raise PermissionError("historical A2/G1 source digests differ from reviewed pins")
    return attestation


def _parse_lock(lock: bytes) -> dict[str, tuple[str, str]]:
    try:
        lines = lock.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise PermissionError("Linux lock is not UTF-8") from exc
    if "--require-hashes" not in lines or "--only-binary=:all:" not in lines:
        raise PermissionError("Linux lock does not require hashed binary distributions")
    result: dict[str, tuple[str, str]] = {}
    rule = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:([0-9a-f]{64})$")
    for line in lines:
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        match = rule.fullmatch(line)
        if match is None:
            raise PermissionError("Linux lock has an unpinned distribution")
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in result:
            raise PermissionError("Linux lock repeats a distribution")
        result[name] = (match.group(2), match.group(3))
    if not result:
        raise PermissionError("Linux lock has no pinned distributions")
    return result


def _validate_admission_metadata_projection(
    frozen: FrozenAdmission, encoded: bytes,
) -> None:
    _require_pinned_hash(
        encoded, frozen.admission_metadata_projection_sha256,
        "admission metadata projection",
    )
    projection = _json_object(encoded, "admission metadata projection")
    if (
        set(projection) != _ADMISSION_METADATA_KEYS
        or projection.get("schema") != "route2_admission_metadata_projection_v1"
        or projection.get("study_id") != STUDY_ID
        or projection.get("status") != "PREPARED_UNREVIEWED"
        or projection.get("experiment_authorization") is not None
        or projection.get("source_registration_sha256") != frozen.source_registration_sha256.lower()
        or projection.get("projection_manifest_sha256") != frozen.projection_manifest_sha256.lower()
    ):
        raise PermissionError("admission metadata projection schema or source digest pins differ")
    expected_pins = {
        "a1_role_graph_sha256": frozen.role_graph_sha256,
        "a2_004_config_sha256": frozen.a2_004_config_sha256,
        "a2_004_audit_ready_sha256": frozen.a2_004_audit_ready_sha256,
        "a2_audit_ready_sidecar_sha256": frozen.a2_004_audit_ready_sidecar_sha256,
        "a2_004_role_digests_sha256": frozen.a2_004_role_digests_sha256,
        "g1_eligibility_sha256": frozen.g1_eligibility_sha256,
        "role_input_registry_sha256": frozen.role_input_registry_sha256,
        "reference_registry_sha256": frozen.reference_registry_sha256,
        "gt_view_registry_sha256": frozen.gt_view_registry_sha256,
        "gt_role_scopes_sha256": frozen.gt_role_graph_projection_sha256,
    }
    identity_pins = projection.get("identity_pins")
    if (
        not isinstance(identity_pins, dict)
        or set(identity_pins) != set(_ADMISSION_IDENTITY_PIN_NAMES)
        or any(identity_pins.get(name) != digest.lower() for name, digest in expected_pins.items())
    ):
        raise PermissionError("admission metadata projection identity pins differ")
    canonical = json.dumps(
        projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if canonical != encoded:
        raise PermissionError("admission metadata projection is not canonical reviewed JSON")


def validate_metadata_identity(
    frozen: FrozenAdmission,
    *,
    attestation_bytes: bytes,
    admission_metadata_projection_bytes: bytes,
    linux_lock_bytes: bytes,
    linux_identity_bytes: bytes,
) -> dict[str, Any]:
    """Validate only approved metadata bytes; return Linux ABI expectations."""

    _require_review_attestation(frozen, attestation_bytes)
    _validate_admission_metadata_projection(frozen, admission_metadata_projection_bytes)
    actual = {
        "admission_metadata_projection": admission_metadata_projection_bytes,
        "linux_lock": linux_lock_bytes,
        "linux_identity": linux_identity_bytes,
    }
    expected = {
        "admission_metadata_projection": frozen.admission_metadata_projection_sha256,
        "linux_lock": frozen.linux_lock_sha256,
        "linux_identity": frozen.linux_identity_sha256,
    }
    for name, contents in actual.items():
        _require_pinned_hash(contents, expected[name], name)

    locked = _parse_lock(linux_lock_bytes)
    identity = _json_object(linux_identity_bytes, "Linux dependency identity")
    if (
        identity.get("schema") != "route2-linux-dependency-identity-v1"
        or identity.get("study_id") != STUDY_ID
        or identity.get("status") != "PREPARATION_ONLY_NOT_EXPERIMENT_AUTHORIZED"
        or not isinstance(identity.get("requirements"), dict)
        or identity["requirements"].get("sha256") != _sha(linux_lock_bytes)
        or not isinstance(identity.get("runtime"), dict)
        or not isinstance(identity.get("wheelhouse"), dict)
        or not isinstance(identity["wheelhouse"].get("wheels"), list)
    ):
        raise PermissionError("Linux dependency identity differs from frozen lock")
    wheel_hashes = [item.get("sha256") for item in identity["wheelhouse"]["wheels"]
                    if isinstance(item, dict)]
    if len(wheel_hashes) != len(locked) or set(wheel_hashes) != {
        digest for _, digest in locked.values()
    }:
        raise PermissionError("Linux wheel identity and hashed lock differ")
    return identity["runtime"]


def _require_linux_runtime(
    runtime: dict[str, Any], lock: bytes, frozen: FrozenAdmission,
) -> None:
    """Bind the live interpreter ABI and installed versions before any data read."""

    if platform.system() != "Linux":
        raise PermissionError("Route 2 approved runtime requires Linux")
    observed = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "glibc": platform.libc_ver()[1],
        "soabi": sysconfig.get_config_var("SOABI"),
        "python_realpath": os.path.realpath(sys.executable),
    }
    if any(observed[name] != runtime.get(name) for name in observed):
        raise PermissionError("live Linux interpreter ABI differs from reviewed identity")
    executable = Path(observed["python_realpath"])
    if not executable.is_file() or _sha(executable.read_bytes()) != runtime.get("python_sha256"):
        raise PermissionError("live Linux Python executable differs from reviewed identity")
    try:
        os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError as exc:
        raise PermissionError("Linux distro identity is unavailable") from exc
    if runtime.get("distro") != "Ubuntu-22.04" or not re.search(r"^ID=ubuntu$", os_release, re.M) or not re.search(r'^VERSION_ID="22.04"$', os_release, re.M):
        raise PermissionError("Linux distribution differs from reviewed identity")
    if not isinstance(runtime.get("venv_path"), str) or not os.path.realpath(sys.prefix).startswith(runtime["venv_path"] + os.sep):
        # sys.prefix equals the venv root, so accept exact equality too.
        if os.path.realpath(sys.prefix) != runtime.get("venv_path"):
            raise PermissionError("active venv differs from reviewed identity")
    if (
        runtime.get("venv_path") != frozen.runtime_snapshot_root
        or os.path.realpath(sys.prefix) != frozen.runtime_snapshot_root
    ):
        raise PermissionError("active venv is not the frozen immutable runtime snapshot")
    for name, (version, _) in _parse_lock(lock).items():
        if metadata.version(name) != version:
            raise PermissionError(f"installed Linux distribution differs from frozen lock: {name}")


def verify_runtime_metadata(frozen: FrozenAdmission, path_map: ExactPathMap) -> None:
    """Use only controller-mounted metadata aliases, never caller byte strings."""

    if type(frozen) is not FrozenAdmission or type(path_map) is not ExactPathMap:
        raise PermissionError("runtime metadata requires frozen admission and exact path map")
    if path_map.manifest_sha256 != frozen.path_map_sha256.lower():
        raise PermissionError("runtime metadata path map differs from frozen review")
    if not path_map.controller_receipt_sha256 or not path_map.controller_run_id:
        raise PermissionError("runtime metadata requires a sealed controller mount receipt")

    # Bind the code already imported into this process and the installed
    # dependency tree to controller-owned, read-only mounts before exposing any
    # registered project input.
    source_root = Path(frozen.source_snapshot_root)
    source_manifest = Path(frozen.source_snapshot_manifest_path).read_bytes()
    verify_snapshot_module(
        source_root,
        Path(__file__),
        source_manifest,
        expected_manifest_sha256=frozen.source_snapshot_sha256,
        expected_module_relative_path="src/eating_event/route2_candidate_overlap/runtime_identity.py",
        mount_path=frozen.source_snapshot_root,
        mountinfo_text=Path("/proc/self/mountinfo").read_text(encoding="utf-8"),
    )
    require_controller_owned_readonly_tree(source_root)
    runtime_root = Path(frozen.runtime_snapshot_root)
    runtime_manifest = Path(frozen.runtime_snapshot_manifest_path).read_bytes()
    verify_source_snapshot(
        runtime_root,
        runtime_manifest,
        expected_manifest_sha256=frozen.runtime_snapshot_sha256,
    )
    require_readonly_mount(
        frozen.runtime_snapshot_root,
        Path("/proc/self/mountinfo").read_text(encoding="utf-8"),
    )
    require_controller_owned_readonly_tree(runtime_root)

    def read_metadata(logical_path: str, digest: str) -> bytes:
        with path_map.open_verified(
            logical_path, digest, role_id=_METADATA_ROLE, phase=_METADATA_PHASE
        ) as stream:
            return stream.read()

    # Read the independent classification before any source/projection metadata.
    attestation = read_metadata(
        frozen.runtime_attestation_path, frozen.runtime_attestation_sha256
    )
    _require_review_attestation(frozen, attestation)
    admission_metadata = read_metadata(
        frozen.admission_metadata_projection_path,
        frozen.admission_metadata_projection_sha256,
    )
    lock = read_metadata(frozen.linux_lock_path, frozen.linux_lock_sha256)
    identity = read_metadata(frozen.linux_identity_path, frozen.linux_identity_sha256)
    runtime = validate_metadata_identity(
        frozen,
        attestation_bytes=attestation,
        admission_metadata_projection_bytes=admission_metadata,
        linux_lock_bytes=lock,
        linux_identity_bytes=identity,
    )
    _require_linux_runtime(runtime, lock, frozen)
