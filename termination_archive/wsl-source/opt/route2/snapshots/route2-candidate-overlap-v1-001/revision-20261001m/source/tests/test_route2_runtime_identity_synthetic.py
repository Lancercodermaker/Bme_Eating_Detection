"""No-data tests for Route 2 metadata identity and output image admission."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json

import pytest

from eating_event.route2_candidate_overlap.contracts import (
    ExperimentApproval,
    FrozenAdmission,
    STUDY_ID,
    stage_a_registry_sha256,
)
from eating_event.route2_candidate_overlap.runtime_identity import (
    validate_metadata_identity,
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


def test_readiness_schema_requires_runtime_metadata_pins() -> None:
    assert {
        "source_registration_sha256", "projection_manifest_sha256",
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


def test_metadata_identity_rejects_unreviewed_attestation() -> None:
    frozen = _frozen()
    with pytest.raises(PermissionError, match="independent|review"):
        validate_metadata_identity(
            frozen,
            attestation_bytes=_encoded({"schema": "route2_runtime_metadata_attestation_v1", "status": "PREPARED_UNREVIEWED"}),
            source_registration_bytes=b"{}",
            projection_manifest_bytes=b"{}",
            linux_lock_bytes=b"",
            linux_identity_bytes=b"{}",
        )


def test_metadata_identity_accepts_consistent_synthetic_metadata_only() -> None:
    base = _frozen()
    source = _encoded({
        "schema": "route2_source_registration_v1", "study_id": STUDY_ID,
        "status": "PREPARED_UNREVIEWED", "independent_review_id": None,
        "experiment_authorization": None,
        "a2_audit_ready_sidecar_sha256": base.a2_004_audit_ready_sidecar_sha256,
    })
    projection = _encoded({
        "schema": "route2_projection_manifest_v1", "study_id": STUDY_ID,
        "status": "PREPARED_UNREVIEWED", "independent_review_id": None,
        "experiment_authorization": None,
        "source_registration_sha256": _sha(source),
        "a1_role_graph_sha256": base.role_graph_sha256,
        "a2_004_config_sha256": base.a2_004_config_sha256,
        "a2_004_audit_ready_sha256": base.a2_004_audit_ready_sha256,
        "a2_004_role_digests_sha256": base.a2_004_role_digests_sha256,
        "g1_eligibility_sha256": base.g1_eligibility_sha256,
        "role_input_registry_sha256": base.role_input_registry_sha256,
        "reference_registry_sha256": base.reference_registry_sha256,
        "gt_view_registry_sha256": base.gt_view_registry_sha256,
        "gt_role_scopes_sha256": base.gt_role_graph_projection_sha256,
        "reference_view_count": 105, "training_gt_view_count": 100,
        "inner_gt_view_count": 5, "outer_gt_view_count": 5,
    })
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
            "source_registration": _sha(source), "projection_manifest": _sha(projection),
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
        source_registration_sha256=_sha(source),
        projection_manifest_sha256=_sha(projection),
        linux_lock_sha256=_sha(lock),
        linux_identity_sha256=_sha(identity),
        runtime_attestation_sha256=_sha(attestation),
    )
    runtime = validate_metadata_identity(
        frozen,
        attestation_bytes=attestation,
        source_registration_bytes=source,
        projection_manifest_bytes=projection,
        linux_lock_bytes=lock,
        linux_identity_bytes=identity,
    )
    assert runtime["soabi"] == "cpython-310-x86_64-linux-gnu"


def test_metadata_identity_rejects_projection_source_mismatch() -> None:
    source = _encoded({
        "schema": "route2_source_registration_v1", "study_id": STUDY_ID,
        "status": "PREPARED_UNREVIEWED", "independent_review_id": None,
        "experiment_authorization": None,
        "a2_audit_ready_sidecar_sha256": "b" * 64,
    })
    projection = _encoded({
        "schema": "route2_projection_manifest_v1", "study_id": STUDY_ID,
        "status": "PREPARED_UNREVIEWED", "independent_review_id": None,
        "experiment_authorization": None,
        "source_registration_sha256": "f" * 64,
        "a1_role_graph_sha256": "a" * 64,
        "a2_004_config_sha256": "c" * 64,
        "a2_004_audit_ready_sha256": "a" * 64,
        "a2_004_role_digests_sha256": "c" * 64,
        "g1_eligibility_sha256": "a" * 64,
        "role_input_registry_sha256": "b" * 64,
        "reference_registry_sha256": "c" * 64,
        "gt_view_registry_sha256": "a" * 64,
        "gt_role_scopes_sha256": "b" * 64,
        "reference_view_count": 105, "training_gt_view_count": 100,
        "inner_gt_view_count": 5, "outer_gt_view_count": 5,
    })
    lock = b"--require-hashes\n"
    identity = _encoded({
        "schema": "route2-linux-dependency-identity-v1", "study_id": STUDY_ID,
        "status": "PREPARATION_ONLY_NOT_EXPERIMENT_AUTHORIZED",
        "requirements": {"sha256": _sha(lock)},
        "runtime": {"python": "3.10.12", "soabi": "cpython-310-x86_64-linux-gnu"},
        "wheelhouse": {"wheels": []},
    })
    attestation = _encoded({
        "schema": "route2_runtime_metadata_attestation_v1", "study_id": STUDY_ID,
        "status": "INDEPENDENT_REVIEW_PASS", "independent_review_id": "review-1",
        "metadata_only_sha256": {
            "source_registration": _sha(source), "projection_manifest": _sha(projection),
            "linux_lock": _sha(lock), "linux_identity": _sha(identity),
        },
        "source_digest_pins": {
            "a2_004_config": "c" * 64, "a2_004_audit_ready": "a" * 64,
            "a2_004_audit_ready_sidecar": "b" * 64,
            "a2_004_role_digests": "c" * 64, "g1_eligibility": "a" * 64,
        },
    })
    frozen = _frozen(
        source_registration_sha256=_sha(source),
        projection_manifest_sha256=_sha(projection),
        linux_lock_sha256=_sha(lock),
        linux_identity_sha256=_sha(identity),
        runtime_attestation_sha256=_sha(attestation),
    )
    with pytest.raises(PermissionError, match="source registration"):
        validate_metadata_identity(
            frozen,
            attestation_bytes=attestation,
            source_registration_bytes=source,
            projection_manifest_bytes=projection,
            linux_lock_bytes=lock,
            linux_identity_bytes=identity,
        )
