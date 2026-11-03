"""No-project-data tests for the external Route 2 admission seal."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
import json

import pytest

from eating_event.route2_candidate_overlap.contracts import (
    FrozenAdmission,
    STUDY_ID,
    stage_a_registry_sha256,
)
from eating_event.route2_candidate_overlap.external_admission import (
    load_controller_sealed_admission,
)


_KEY = b"synthetic-only-controller-seal-key-32-bytes"


def _frozen() -> FrozenAdmission:
    role_graph = "1" * 64
    role_registry = "2" * 64
    reference_registry = "3" * 64
    volume = f"/var/lib/route2/studies/{STUDY_ID}-volume"
    revision = f"/opt/route2/snapshots/{STUDY_ID}/revision-20260930a"
    return FrozenAdmission(
        role_graph_sha256=role_graph,
        role_input_registry_sha256=role_registry,
        role_input_registry_path=r"C:\synthetic\roles.json",
        reference_registry_sha256=reference_registry,
        reference_registry_path=r"C:\synthetic\references.json",
        gt_view_registry_sha256="4" * 64,
        gt_role_graph_projection_sha256="5" * 64,
        path_map_sha256="6" * 64,
        gt_input_root_path=r"C:\synthetic\gt",
        combined_input_registry_sha256=stage_a_registry_sha256(
            role_graph, role_registry, reference_registry,
        ),
        budget_policy_sha256="7" * 64,
        resource_controller_sha256="8" * 64,
        phase_runner_sha256="9" * 64,
        phase_worker_sha256="a" * 64,
        stage_b_adapter_sha256="b" * 64,
        approved_write_volumes=(volume,),
        study_root_path=f"{volume}/{STUDY_ID}",
        budget_ledger_path=f"{volume}/{STUDY_ID}-budget.jsonl",
        lock_path=f"{volume}/{STUDY_ID}.lock",
        study_image_path=f"/var/lib/route2/images/{STUDY_ID}.ext4",
        source_registration_path=r"C:\synthetic\source-registration.json",
        source_registration_sha256="c" * 64,
        projection_manifest_path=r"C:\synthetic\projection.json",
        projection_manifest_sha256="d" * 64,
        a2_004_config_sha256="e" * 64,
        a2_004_audit_ready_sha256="f" * 64,
        a2_004_audit_ready_sidecar_sha256="1" * 64,
        a2_004_role_digests_sha256="2" * 64,
        g1_eligibility_sha256="3" * 64,
        linux_lock_path=r"C:\synthetic\requirements.lock",
        linux_lock_sha256="4" * 64,
        linux_identity_path=r"C:\synthetic\linux-identity.json",
        linux_identity_sha256="5" * 64,
        runtime_attestation_path=r"C:\synthetic\runtime.json",
        runtime_attestation_sha256="6" * 64,
        source_snapshot_root=f"{revision}/source",
        source_snapshot_manifest_path=f"{revision}/source.manifest.json",
        source_snapshot_sha256="7" * 64,
        runtime_snapshot_root=f"{revision}/venv",
        runtime_snapshot_manifest_path=f"{revision}/venv.manifest.json",
        runtime_snapshot_sha256="8" * 64,
        readiness_sha256="9" * 64,
        approval_record="route2-owner-synthetic-AB-001",
    )


def _seal(**overrides: object) -> bytes:
    frozen = _frozen()
    body = {
        "schema": "route2_controller_sealed_admission_v1",
        "study_id": STUDY_ID,
        "independent_review_id": "route2-review-synthetic-PASS-001",
        "review_result": "PASS",
        "owner_approval_id": "route2-owner-synthetic-AB-001",
        "owner_approved": True,
        "approval_scope": "A+B",
        "authorization_card_sha256": "a" * 64,
        "source_snapshot_sha256": frozen.source_snapshot_sha256,
        "runtime_snapshot_sha256": frozen.runtime_snapshot_sha256,
        "frozen_admission": asdict(frozen),
    }
    body.update(overrides)
    encoded_body = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    envelope = {
        "body": body,
        "controller_hmac_sha256": hmac.new(_KEY, encoded_body, hashlib.sha256).hexdigest(),
    }
    return json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def test_controller_seal_returns_pinned_admission_without_mutating_global_state() -> None:
    frozen = load_controller_sealed_admission(
        _seal(),
        controller_key=_KEY,
        expected_source_snapshot_sha256="7" * 64,
        expected_runtime_snapshot_sha256="8" * 64,
        expected_review_id="route2-review-synthetic-PASS-001",
        expected_owner_approval_id="route2-owner-synthetic-AB-001",
        expected_authorization_card_sha256="a" * 64,
    )
    assert frozen == _frozen()
    from eating_event.route2_candidate_overlap import contracts
    assert contracts.FROZEN_ADMISSION is None


@pytest.mark.parametrize("changed", [
    {"review_result": "FAIL"},
    {"owner_approved": False},
    {"approval_scope": "Stage A-only"},
    {"source_snapshot_sha256": "0" * 64},
    {"owner_approval_id": "different-owner-approval"},
])
def test_seal_rejects_incomplete_or_mismatched_approval(changed: dict[str, object]) -> None:
    with pytest.raises(PermissionError):
        load_controller_sealed_admission(
            _seal(**changed),
            controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )


def test_seal_rejects_changed_bytes_wrong_key_and_unknown_fields() -> None:
    good = _seal()
    with pytest.raises(PermissionError):
        load_controller_sealed_admission(
            good[:-1] + b" ", controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )
    with pytest.raises(PermissionError):
        load_controller_sealed_admission(
            good, controller_key=b"wrong-synthetic-controller-key-32-bytes",
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )
    with pytest.raises(PermissionError):
        load_controller_sealed_admission(
            _seal(unreviewed_extension="must fail"), controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )


def test_seal_rejects_modified_signed_body_duplicate_keys_bad_types_and_lone_surrogates() -> None:
    good = json.loads(_seal())
    good["body"]["review_result"] = "FAIL"
    changed_body = json.dumps(
        good, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    cases = (
        changed_body,
        b'{"body":{},"body":{},"controller_hmac_sha256":"' + b"0" * 64 + b'"}',
        b'{"body":NaN,"controller_hmac_sha256":"' + b"0" * 64 + b'"}',
        b'{"body":{"\\ud800":"x"},"controller_hmac_sha256":"' + b"0" * 64 + b'"}',
        json.dumps({"body": [], "controller_hmac_sha256": "0" * 64}).encode(),
        json.dumps({"body": {}, "controller_hmac_sha256": ["0" * 64]}).encode(),
    )
    for artifact in cases:
        with pytest.raises(PermissionError):
            load_controller_sealed_admission(
                artifact,
                controller_key=_KEY,
                expected_source_snapshot_sha256="7" * 64,
                expected_runtime_snapshot_sha256="8" * 64,
                expected_review_id="route2-review-synthetic-PASS-001",
                expected_owner_approval_id="route2-owner-synthetic-AB-001",
                expected_authorization_card_sha256="a" * 64,
            )


def test_seal_bounds_input_before_json_decode_and_normalizes_excessive_nesting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eating_event.route2_candidate_overlap import external_admission

    oversized = _seal() + b" " * (1 << 20)

    def unexpected_decode(*_: object, **__: object) -> object:
        raise AssertionError("oversized admission bytes reached JSON decoding")

    monkeypatch.setattr(external_admission.json, "loads", unexpected_decode)
    with pytest.raises(PermissionError, match="size"):
        load_controller_sealed_admission(
            oversized,
            controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )

    monkeypatch.undo()
    deeply_nested = b'{"body":' + b"[" * 2000 + b"0" + b"]" * 2000 + b'}'
    with pytest.raises(PermissionError):
        load_controller_sealed_admission(
            deeply_nested,
            controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
                expected_authorization_card_sha256="a" * 64,
            )


def test_seal_normalizes_recursion_failure_during_canonical_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eating_event.route2_candidate_overlap import external_admission

    def recursion_failure(_: object) -> bytes:
        raise RecursionError("synthetic canonicalizer depth fault")

    monkeypatch.setattr(external_admission, "_canonical", recursion_failure)
    monkeypatch.setattr(external_admission.json, "loads", lambda *_args, **_kwargs: {})
    with pytest.raises(PermissionError, match="canonically encoded"):
        load_controller_sealed_admission(
            b"synthetic input replaced by the parser stub",
            controller_key=_KEY,
            expected_source_snapshot_sha256="7" * 64,
            expected_runtime_snapshot_sha256="8" * 64,
            expected_review_id="route2-review-synthetic-PASS-001",
            expected_owner_approval_id="route2-owner-synthetic-AB-001",
            expected_authorization_card_sha256="a" * 64,
        )
