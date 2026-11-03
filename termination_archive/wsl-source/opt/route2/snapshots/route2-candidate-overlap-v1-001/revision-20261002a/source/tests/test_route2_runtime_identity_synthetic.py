"""No-data tests for Route 2 metadata identity and output image admission."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest

from eating_event.route2_candidate_overlap.contracts import (
    ExperimentApproval,
    FrozenAdmission,
    STUDY_ID,
    stage_a_registry_sha256,
)
from eating_event.route2_candidate_overlap.runtime_identity import (
    validate_metadata_identity,
    verify_runtime_metadata,
)
from eating_event.route2_candidate_overlap.path_map import (
    ExactPathMap,
    MountReceipt,
    canonical_manifest_bytes,
    file_mapping,
)
from eating_event.route2_candidate_overlap.execution import (
    ABReadiness, StageBEquivalenceReceipt,
)


def _encoded(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _frozen(**changes: object) -> FrozenAdmission:
    one, two, three = "a" * 64, "b" * 64, "c" * 64
    values: dict[str, object] = {
        "role_graph_sha256": one,
        "role_input_registry_sha256": two,
        "role_input_registry_path": r"E:\route2\role-input-registry.json",
        "reference_registry_sha256": three,
        "reference_registry_path": r"E:\route2\reference-registry.json",
        "gt_view_registry_sha256": one,
        "gt_role_graph_projection_sha256": two,
        "path_map_sha256": three,
        "gt_input_root_path": r"E:\route2\inputs",
        "combined_input_registry_sha256": stage_a_registry_sha256(one, two, three),
        "budget_policy_sha256": one,
        "resource_controller_sha256": two,
        "phase_runner_sha256": three,
        "phase_worker_sha256": one,
        "stage_b_adapter_sha256": two,
        "approved_write_volumes": ("/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume",),
        "study_root_path": "/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/" + STUDY_ID,
        "budget_ledger_path": "/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/" + STUDY_ID + "-budget.jsonl",
        "lock_path": "/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/" + STUDY_ID + ".lock",
        "study_image_path": "/var/lib/route2/images/" + STUDY_ID + ".ext4",
        "source_registration_path": r"E:\route2\source-registration.json",
        "source_registration_sha256": one,
        "projection_manifest_path": r"E:\route2\projection-manifest.json",
        "projection_manifest_sha256": two,
        "admission_metadata_projection_path": r"E:\route2\runtime-admission-metadata.json",
        "admission_metadata_projection_sha256": three,
        "a2_004_config_sha256": three,
        "a2_004_audit_ready_sha256": one,
        "a2_004_audit_ready_sidecar_sha256": two,
        "a2_004_role_digests_sha256": three,
        "g1_eligibility_sha256": one,
        "linux_lock_path": r"E:\route2\route2-linux-cp310.lock",
        "linux_lock_sha256": two,
        "linux_identity_path": r"E:\route2\route2-linux-cp310.identity.json",
        "linux_identity_sha256": three,
        "runtime_attestation_path": r"E:\route2\runtime-attestation.json",
        "runtime_attestation_sha256": one,
        "source_snapshot_root": "/opt/route2/snapshots/" + STUDY_ID + "/source",
        "source_snapshot_manifest_path": "/opt/route2/snapshots/" + STUDY_ID + "/source-manifest.json",
        "source_snapshot_sha256": two,
        "runtime_snapshot_root": "/opt/route2/snapshots/" + STUDY_ID + "/venv",
        "runtime_snapshot_manifest_path": "/opt/route2/snapshots/" + STUDY_ID + "/runtime-manifest.json",
        "runtime_snapshot_sha256": three,
        "readiness_sha256": three,
        "approval_record": "approved-review-record",
    }
    values.update(changes)
    return FrozenAdmission(**values)


def test_frozen_admission_requires_exact_study_image_path() -> None:
    frozen = _frozen()
    assert frozen.study_image_path == "/var/lib/route2/images/" + STUDY_ID + ".ext4"
    with pytest.raises(ValueError, match="image"):
        replace(frozen, study_image_path="/tmp/route2.ext4")


def test_ab_approval_rejects_different_image_or_metadata_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    import eating_event.route2_candidate_overlap.contracts as contracts

    frozen = _frozen()
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", frozen)
    approval = ExperimentApproval(
        study_id=STUDY_ID, scope="A+B", approved=True,
        input_registry_sha256=frozen.combined_input_registry_sha256,
        budget_policy_sha256=frozen.budget_policy_sha256,
        resource_controller_sha256=frozen.resource_controller_sha256,
        phase_runner_sha256=frozen.phase_runner_sha256,
        phase_worker_sha256=frozen.phase_worker_sha256,
        path_map_sha256=frozen.path_map_sha256,
        approved_write_volumes=frozen.approved_write_volumes,
        study_root_path=frozen.study_root_path,
        budget_ledger_path=frozen.budget_ledger_path,
        lock_path=frozen.lock_path,
        study_image_path=frozen.study_image_path,
        source_registration_sha256=frozen.source_registration_sha256,
        projection_manifest_sha256=frozen.projection_manifest_sha256,
        admission_metadata_projection_path=frozen.admission_metadata_projection_path,
        admission_metadata_projection_sha256=frozen.admission_metadata_projection_sha256,
        linux_lock_sha256=frozen.linux_lock_sha256,
        linux_identity_sha256=frozen.linux_identity_sha256,
        runtime_attestation_sha256=frozen.runtime_attestation_sha256,
        source_snapshot_root=frozen.source_snapshot_root,
        source_snapshot_manifest_path=frozen.source_snapshot_manifest_path,
        source_snapshot_sha256=frozen.source_snapshot_sha256,
        runtime_snapshot_root=frozen.runtime_snapshot_root,
        runtime_snapshot_manifest_path=frozen.runtime_snapshot_manifest_path,
        runtime_snapshot_sha256=frozen.runtime_snapshot_sha256,
        approval_record=frozen.approval_record,
    )
    approval.require_full_ab()
    with pytest.raises(PermissionError, match=r"A\+B"):
        replace(approval, study_image_path="/tmp/other.ext4").require_full_ab()
    with pytest.raises(PermissionError, match=r"A\+B"):
        replace(approval, runtime_attestation_sha256="f" * 64).require_full_ab()
    with pytest.raises(PermissionError, match=r"A\+B"):
        replace(approval, admission_metadata_projection_sha256="f" * 64).require_full_ab()
    with pytest.raises(PermissionError, match=r"A\+B"):
        replace(approval, admission_metadata_projection_path=r"E:\route2\other.json").require_full_ab()


def test_readiness_schema_requires_runtime_metadata_pins() -> None:
    assert {
        "source_registration_sha256", "projection_manifest_sha256",
        "admission_metadata_projection_path", "admission_metadata_projection_sha256",
        "linux_lock_sha256", "linux_identity_sha256",
        "runtime_attestation_sha256", "runtime_metadata_review_id",
        "source_snapshot_sha256", "runtime_snapshot_sha256",
        "source_snapshot_review_id", "runtime_snapshot_review_id",
    }.issubset(ABReadiness.__dataclass_fields__)


def test_frozen_and_approved_identity_bind_immutable_source_and_runtime_snapshots() -> None:
    from dataclasses import fields

    names = {item.name for item in fields(FrozenAdmission)}
    assert {
        "source_snapshot_root", "source_snapshot_manifest_path", "source_snapshot_sha256",
        "runtime_snapshot_root", "runtime_snapshot_manifest_path", "runtime_snapshot_sha256",
    }.issubset(names)
    approval_names = {item.name for item in fields(ExperimentApproval)}
    assert {
        "source_snapshot_root", "source_snapshot_manifest_path", "source_snapshot_sha256",
        "runtime_snapshot_root", "runtime_snapshot_manifest_path", "runtime_snapshot_sha256",
    }.issubset(approval_names)


def test_readiness_rejects_changed_runtime_metadata_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    import eating_event.route2_candidate_overlap.contracts as contracts

    base = _frozen()
    digest = "a" * 64
    equivalence = StageBEquivalenceReceipt(
        a1_label_code_sha256=digest,
        a2_audit_code_sha256=digest,
        a2_role_digests_sha256=base.a2_004_role_digests_sha256,
        interval_iou_code_sha256=digest,
        feature_16d_code_sha256=digest,
        feature_10d_code_sha256=digest,
        verifier_config_sha256=base.a2_004_config_sha256,
        role_graph_sha256=base.role_graph_sha256,
        threshold_selection_sha256=digest,
        decoder_sha256=digest,
        matcher_evaluator_sha256=digest,
        independent_review_id="synthetic-review",
    )
    readiness = ABReadiness(
        equivalence=equivalence,
        role_input_registry_sha256=base.role_input_registry_sha256,
        reference_registry_sha256=base.reference_registry_sha256,
        gt_view_registry_sha256=base.gt_view_registry_sha256,
        gt_role_graph_projection_sha256=base.gt_role_graph_projection_sha256,
        path_map_sha256=base.path_map_sha256,
        phase_runner_sha256=base.phase_runner_sha256,
        phase_worker_sha256=base.phase_worker_sha256,
        stage_b_adapter_sha256=base.stage_b_adapter_sha256,
        source_registration_sha256=base.source_registration_sha256,
        projection_manifest_sha256=base.projection_manifest_sha256,
        admission_metadata_projection_path=base.admission_metadata_projection_path,
        admission_metadata_projection_sha256=base.admission_metadata_projection_sha256,
        linux_lock_sha256=base.linux_lock_sha256,
        linux_identity_sha256=base.linux_identity_sha256,
        runtime_attestation_sha256=base.runtime_attestation_sha256,
        source_snapshot_sha256=base.source_snapshot_sha256,
        runtime_snapshot_sha256=base.runtime_snapshot_sha256,
        runtime_metadata_review_id="synthetic-review",
        source_snapshot_review_id="synthetic-review",
        runtime_snapshot_review_id="synthetic-review",
        reference_projection_review_id="synthetic-review",
        gt_projection_review_id="synthetic-review",
        lazy_loader_review_id="synthetic-review",
        resource_enforcer_review_id="synthetic-review",
        stage_b_adapter_review_id="synthetic-review",
        path_map_review_id="synthetic-review",
        phase_runner_review_id="synthetic-review",
        phase_worker_review_id="synthetic-review",
        all_inputs_explicitly_approved=True,
        stage_b_resources_preapproved=True,
    )
    frozen = replace(base, readiness_sha256=_sha(_encoded(asdict(readiness))))
    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", frozen)
    readiness.require_complete()
    with pytest.raises(PermissionError, match="metadata"):
        replace(readiness, linux_lock_sha256="f" * 64).require_complete()
    with pytest.raises(PermissionError, match="metadata"):
        replace(readiness, runtime_snapshot_sha256="f" * 64).require_complete()
    with pytest.raises(PermissionError, match="metadata"):
        replace(readiness, admission_metadata_projection_sha256="f" * 64).require_complete()
    with pytest.raises(PermissionError, match="metadata"):
        replace(readiness, admission_metadata_projection_path=r"E:\route2\other.json").require_complete()


def test_metadata_identity_rejects_unreviewed_attestation() -> None:
    frozen = _frozen()
    with pytest.raises(PermissionError, match="independent|review"):
        validate_metadata_identity(
            frozen,
            attestation_bytes=_encoded({"schema": "route2_runtime_metadata_attestation_v1", "status": "PREPARED_UNREVIEWED"}),
            admission_metadata_projection_bytes=b"{}",
            linux_lock_bytes=b"",
            linux_identity_bytes=b"{}",
        )


def _safe_admission_metadata(base: FrozenAdmission) -> dict[str, object]:
    return {
        "schema": "route2_admission_metadata_projection_v1",
        "study_id": STUDY_ID,
        "status": "PREPARED_UNREVIEWED",
        "experiment_authorization": None,
        "source_registration_sha256": base.source_registration_sha256,
        "projection_manifest_sha256": base.projection_manifest_sha256,
        "identity_pins": {
            "a1_role_graph_sha256": base.role_graph_sha256,
            "a2_004_config_sha256": base.a2_004_config_sha256,
            "a2_004_audit_ready_sha256": base.a2_004_audit_ready_sha256,
            "a2_audit_ready_sidecar_sha256": base.a2_004_audit_ready_sidecar_sha256,
            "a2_004_role_digests_sha256": base.a2_004_role_digests_sha256,
            "g1_eligibility_sha256": base.g1_eligibility_sha256,
            "role_input_registry_sha256": base.role_input_registry_sha256,
            "reference_registry_sha256": base.reference_registry_sha256,
            "gt_view_registry_sha256": base.gt_view_registry_sha256,
            "gt_role_scopes_sha256": base.gt_role_graph_projection_sha256,
        },
    }


def _runtime_metadata_fixture(base: FrozenAdmission, *, projection: dict[str, object] | None = None):
    admission_metadata = _encoded(projection or _safe_admission_metadata(base))
    wheel_digest = "d" * 64
    lock = ("--only-binary=:all:\n--require-hashes\n"
            f"example==1.0 --hash=sha256:{wheel_digest}\n").encode()
    identity = _encoded({
        "schema": "route2-linux-dependency-identity-v1", "study_id": STUDY_ID,
        "status": "PREPARATION_ONLY_NOT_EXPERIMENT_AUTHORIZED",
        "requirements": {"sha256": _sha(lock)},
        "runtime": {"python": "3.10.12", "soabi": "cpython-310-x86_64-linux-gnu"},
        "wheelhouse": {"wheels": [{"sha256": wheel_digest}]},
    })
    attestation = _encoded({
        "schema": "route2_runtime_metadata_attestation_v1", "study_id": STUDY_ID,
        "status": "INDEPENDENT_REVIEW_PASS", "independent_review_id": "synthetic-review",
        "metadata_only_sha256": {
            "admission_metadata_projection": _sha(admission_metadata),
            "linux_lock": _sha(lock), "linux_identity": _sha(identity),
        },
        "source_digest_pins": {
            "a2_004_config": base.a2_004_config_sha256,
            "a2_004_audit_ready": base.a2_004_audit_ready_sha256,
            "a2_004_audit_ready_sidecar": base.a2_004_audit_ready_sidecar_sha256,
            "a2_004_role_digests": base.a2_004_role_digests_sha256,
            "g1_eligibility": base.g1_eligibility_sha256,
        },
    })
    frozen = replace(
        base,
        admission_metadata_projection_sha256=_sha(admission_metadata),
        linux_lock_sha256=_sha(lock),
        linux_identity_sha256=_sha(identity),
        runtime_attestation_sha256=_sha(attestation),
    )
    return frozen, admission_metadata, lock, identity, attestation


def test_metadata_identity_accepts_sanitized_synthetic_admission_projection() -> None:
    base = _frozen()
    frozen, admission_metadata, lock, identity, attestation = _runtime_metadata_fixture(base)
    runtime = validate_metadata_identity(
        frozen,
        attestation_bytes=attestation,
        admission_metadata_projection_bytes=admission_metadata,
        linux_lock_bytes=lock,
        linux_identity_bytes=identity,
    )
    assert runtime["soabi"] == "cpython-310-x86_64-linux-gnu"


def test_metadata_identity_rejects_gt_derived_count_fields() -> None:
    base = _frozen()
    projection = _safe_admission_metadata(base)
    projection["eligible_gt_count"] = 234
    frozen, admission_metadata, lock, identity, attestation = _runtime_metadata_fixture(
        base, projection=projection,
    )
    with pytest.raises(PermissionError, match="metadata"):
        validate_metadata_identity(
            frozen,
            attestation_bytes=attestation,
            admission_metadata_projection_bytes=admission_metadata,
            linux_lock_bytes=lock,
            linux_identity_bytes=identity,
        )


def test_metadata_identity_rejects_nested_gt_derived_fields() -> None:
    base = _frozen()
    projection = _safe_admission_metadata(base)
    projection["identity_pins"]["eligible_row_count"] = 234
    frozen, admission_metadata, lock, identity, attestation = _runtime_metadata_fixture(
        base, projection=projection,
    )
    with pytest.raises(PermissionError, match="identity pins"):
        validate_metadata_identity(
            frozen,
            attestation_bytes=attestation,
            admission_metadata_projection_bytes=admission_metadata,
            linux_lock_bytes=lock,
            linux_identity_bytes=identity,
        )


def test_runtime_preflight_never_opens_full_registration_or_projection(monkeypatch):
    import eating_event.route2_candidate_overlap.runtime_identity as runtime_identity

    base = _frozen()
    frozen, admission_metadata, lock, identity, attestation = _runtime_metadata_fixture(base)
    payloads = {
        frozen.runtime_attestation_path: attestation,
        frozen.admission_metadata_projection_path: admission_metadata,
        frozen.linux_lock_path: lock,
        frozen.linux_identity_path: identity,
    }
    safe_paths = set(payloads)
    bind_root = "/run/route2/synthetic-preflight"
    entries = tuple(
        file_mapping(
            logical_path,
            hashlib.sha256(contents).hexdigest(),
            role_id="__study__",
            phase="preflight_metadata",
            bind_root=bind_root,
        )
        for logical_path, contents in payloads.items()
    )
    manifest = canonical_manifest_bytes(bind_root, entries)
    map_sha256 = _sha(manifest)
    frozen = replace(frozen, path_map_sha256=map_sha256)
    receipts = tuple(
        MountReceipt(
            manifest_sha256=map_sha256,
            logical_path=item.logical_path,
            sha256=item.sha256,
            role_id=item.role_id,
            phase=item.phase,
            bind_path=item.bind_path,
            mount_id=index + 1,
        )
        for index, item in enumerate(entries)
    )
    path_map = ExactPathMap(
        manifest_sha256=map_sha256,
        bind_root=bind_root,
        entries=entries,
        receipts=receipts,
        controller_receipt_sha256="e" * 64,
        controller_run_id="synthetic-preflight-run",
        phase_id="preflight_metadata",
    )
    opened: list[str] = []

    def open_mapped(_self, logical_path, _digest, *, role_id, phase):
        assert logical_path in safe_paths
        assert role_id == "__study__"
        assert phase == "preflight_metadata"
        opened.append(logical_path)
        return BytesIO(payloads[logical_path])

    monkeypatch.setattr(ExactPathMap, "open_verified", open_mapped)
    monkeypatch.setattr(runtime_identity, "verify_snapshot_module", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_identity, "require_controller_owned_readonly_tree", lambda *args: None)
    monkeypatch.setattr(runtime_identity, "verify_source_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_identity, "require_readonly_mount", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_identity, "_require_linux_runtime", lambda *args, **kwargs: None)

    snapshot_manifest_paths = {
        str(Path(frozen.source_snapshot_manifest_path)),
        str(Path(frozen.runtime_snapshot_manifest_path)),
    }

    def read_bytes(path):
        if str(path) in snapshot_manifest_paths:
            return b"synthetic snapshot manifest"
        raise AssertionError(f"unexpected preflight file read: {path}")

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(
        Path, "read_text",
        lambda path, *args, **kwargs: "synthetic mountinfo" if path.as_posix() == "/proc/self/mountinfo"
        else (_ for _ in ()).throw(AssertionError(f"unexpected preflight text read: {path}")),
    )

    verify_runtime_metadata(frozen, path_map)

    assert set(opened) == safe_paths
    assert frozen.source_registration_path not in opened
    assert frozen.projection_manifest_path not in opened
