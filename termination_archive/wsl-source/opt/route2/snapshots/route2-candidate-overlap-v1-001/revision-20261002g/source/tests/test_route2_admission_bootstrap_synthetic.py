"""Synthetic tests for the external Route 2 admission bootstrap."""

from __future__ import annotations

import json
from dataclasses import dataclass
import hashlib
import os

import pytest


def _config(**overrides: object) -> bytes:
    value: dict[str, object] = {
        "schema": "route2_external_supervisor_config_v1",
        "study_id": "route2-candidate-overlap-v1-001",
        "controller_key_path": "/etc/route2/controller.key",
        "sealed_admission_path": "/etc/route2/admission.json",
        "source_snapshot_root": "/opt/route2/snapshots/revision/source",
        "source_manifest_path": "/opt/route2/snapshots/revision/source-manifest.json",
        "source_snapshot_sha256": "1" * 64,
        "source_module_relative_path": "src/eating_event/route2_candidate_overlap/admission_bootstrap.py",
        "runtime_snapshot_root": "/opt/route2/snapshots/revision/venv",
        "runtime_manifest_path": "/opt/route2/snapshots/revision/runtime-manifest.json",
        "runtime_snapshot_sha256": "2" * 64,
        "source_mount_path": "/opt/route2/snapshots/revision/source",
        "runtime_mount_path": "/opt/route2/snapshots/revision/venv",
        "independent_review_id": "route2-review-synthetic-PASS-001",
        "owner_approval_id": "route2-owner-synthetic-AB-001",
        "authorization_card_sha256": "3" * 64,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_supervisor_config_is_canonical_exact_and_keeps_secrets_outside_snapshots() -> None:
    from eating_event.route2_candidate_overlap.admission_bootstrap import (
        parse_supervisor_config,
    )

    config = parse_supervisor_config(_config())
    assert config.study_id == "route2-candidate-overlap-v1-001"
    assert config.source_snapshot_sha256 == "1" * 64
    assert config.runtime_snapshot_sha256 == "2" * 64

    with pytest.raises(PermissionError, match="canonical"):
        parse_supervisor_config(_config() + b" ")
    with pytest.raises(PermissionError, match="unknown"):
        parse_supervisor_config(_config(unreviewed_switch=True))
    with pytest.raises(PermissionError, match="outside"):
        parse_supervisor_config(_config(controller_key_path="/opt/route2/snapshots/revision/source/key"))
    with pytest.raises(PermissionError, match="distinct"):
        parse_supervisor_config(
            _config(sealed_admission_path="/etc/route2/controller.key")
        )


def test_nonroot_bootstrap_fails_before_opening_any_external_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eating_event.route2_candidate_overlap import admission_bootstrap, contracts

    monkeypatch.setattr(admission_bootstrap.platform, "system", lambda: "Linux")
    monkeypatch.setattr(admission_bootstrap, "_effective_uid", lambda: 1000)

    def forbidden_read(*_: object, **__: object) -> bytes:
        raise AssertionError("untrusted process reached controller files")

    monkeypatch.setattr(admission_bootstrap, "_read_protected_file", forbidden_read)
    with pytest.raises(PermissionError, match="Linux root"):
        admission_bootstrap.bootstrap_frozen_admission("/etc/route2/supervisor.json")
    assert contracts.FROZEN_ADMISSION is None


def test_bootstrap_does_not_install_admission_when_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eating_event.route2_candidate_overlap import admission_bootstrap, contracts

    monkeypatch.setattr(admission_bootstrap.platform, "system", lambda: "Linux")
    monkeypatch.setattr(admission_bootstrap, "_effective_uid", lambda: 0)

    def missing_file(*_: object, **__: object) -> bytes:
        raise PermissionError("protected controller configuration is unavailable")

    monkeypatch.setattr(admission_bootstrap, "_read_protected_file", missing_file)
    with pytest.raises(PermissionError, match="configuration"):
        admission_bootstrap.bootstrap_frozen_admission("/etc/route2/supervisor.json")
    assert contracts.FROZEN_ADMISSION is None


def test_bootstrap_installs_only_after_external_pin_and_snapshot_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eating_event.route2_candidate_overlap import admission_bootstrap, contracts
    from eating_event.route2_candidate_overlap.source_snapshot import (
        ReadonlyMountProof,
        SourceSnapshotProof,
    )

    @dataclass(frozen=True)
    class SyntheticFrozen:
        source_snapshot_root: str = "/opt/route2/snapshots/revision/source"
        source_snapshot_manifest_path: str = "/opt/route2/snapshots/revision/source-manifest.json"
        source_snapshot_sha256: str = "1" * 64
        runtime_snapshot_root: str = "/opt/route2/snapshots/revision/venv"
        runtime_snapshot_manifest_path: str = "/opt/route2/snapshots/revision/runtime-manifest.json"
        runtime_snapshot_sha256: str = "2" * 64
        approval_record: str = "route2-owner-synthetic-AB-001"

    config_bytes = _config()
    config = admission_bootstrap.parse_supervisor_config(config_bytes)
    reads: list[str] = []
    validation_steps: list[str] = []

    def record_before_install(step: str) -> None:
        assert contracts.FROZEN_ADMISSION is None
        validation_steps.append(step)

    def protected_file(path: object, *, max_bytes: int) -> bytes:
        key = str(path).replace("\\", "/")
        record_before_install("protected_file")
        reads.append(key)
        if key.endswith("supervisor.json"):
            assert max_bytes == admission_bootstrap.MAX_SUPERVISOR_CONFIG_BYTES
            return config_bytes
        if key == config.controller_key_path:
            return b"synthetic-only-controller-key-32-bytes"
        if key == config.sealed_admission_path:
            return b"synthetic sealed admission bytes"
        raise AssertionError(f"unexpected protected file: {key}")

    snapshots = admission_bootstrap.SnapshotBootstrapProof(
        source=SourceSnapshotProof("1" * 64, 2, 10),
        runtime=SourceSnapshotProof("2" * 64, 3, 20),
        source_mount=ReadonlyMountProof(41, config.source_mount_path, "7:1", "ext4", "/dev/loop4"),
        runtime_mount=ReadonlyMountProof(42, config.runtime_mount_path, "7:1", "ext4", "/dev/loop4"),
    )
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", None)
    monkeypatch.setattr(admission_bootstrap, "_require_linux_root", lambda: None)
    monkeypatch.setattr(admission_bootstrap, "_read_protected_file", protected_file)
    monkeypatch.setattr(
        admission_bootstrap,
        "_read_snapshot_manifest",
        lambda path, *, max_bytes: (
            record_before_install("snapshot_manifest")
            or b"synthetic manifest " + path.encode()
        ),
    )
    monkeypatch.setattr(admission_bootstrap, "_read_mountinfo", lambda: "synthetic mountinfo")
    monkeypatch.setattr(
        admission_bootstrap,
        "_verify_live_snapshots",
        lambda *args, **kwargs: (record_before_install("snapshot_and_mounts") or snapshots),
    )
    runtime_checks: list[tuple[object, object]] = []
    monkeypatch.setattr(
        admission_bootstrap,
        "_verify_runtime_execution",
        lambda policy, frozen: (
            record_before_install("runtime_abi")
            or runtime_checks.append((policy, frozen))
        ),
    )
    monkeypatch.setattr(
        admission_bootstrap,
        "load_controller_sealed_admission",
        lambda artifact, **pins: (record_before_install("sealed_approval") or SyntheticFrozen()),
    )
    monkeypatch.setattr(admission_bootstrap, "FrozenAdmission", SyntheticFrozen)

    config_file = r"E:\external\supervisor.json" if os.name == "nt" else "/external/supervisor.json"
    proof = admission_bootstrap.bootstrap_frozen_admission(config_file)

    assert contracts.FROZEN_ADMISSION == SyntheticFrozen()
    assert proof.study_id == "route2-candidate-overlap-v1-001"
    assert proof.config_sha256 == hashlib.sha256(config_bytes).hexdigest()
    assert proof.seal_sha256 == hashlib.sha256(b"synthetic sealed admission bytes").hexdigest()
    assert proof.snapshots is snapshots
    assert runtime_checks == [(config, SyntheticFrozen())]
    assert validation_steps == [
        "protected_file", "protected_file", "protected_file",
        "snapshot_manifest", "snapshot_manifest", "snapshot_and_mounts",
        "sealed_approval", "runtime_abi",
    ]
    assert reads == [
        config_file.replace("\\", "/"),
        config.controller_key_path,
        config.sealed_admission_path,
    ]
