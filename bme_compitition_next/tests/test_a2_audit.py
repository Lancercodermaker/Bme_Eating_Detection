from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from eating_event.a2.contracts import (
    A2_CONFIG,
    A2FeatureRow,
    CandidateKey,
    config_digest,
    load_config,
    validate_config,
)
from eating_event.metrics import EventInterval
from eating_event.a2.inputs import (
    authenticate_checksum_manifest,
    check_candidate_rows,
    resolve_approved_path,
    validate_a1_code_identity,
    validate_outer_exclusion,
    validate_outer_label,
    validate_score_payload,
    validate_score_provenance,
    validate_support_identity,
)
from eating_event.a2.audit import current_a2_code_identity


def test_frozen_config_accepts_only_the_single_a2_definition() -> None:
    validate_config(copy.deepcopy(A2_CONFIG))

    changed = copy.deepcopy(A2_CONFIG)
    changed["lookaround_ms"] += 1
    with pytest.raises(ValueError, match="frozen"):
        validate_config(changed)


def test_config_rejects_new_options_source_hash_or_width_drift() -> None:
    for key, value in (
        ("unapproved_sweep", True),
        ("source_checksum_sha256", "0" * 64),
        ("feature_dim", 27),
    ):
        changed = copy.deepcopy(A2_CONFIG)
        changed[key] = value
        with pytest.raises(ValueError):
            validate_config(changed)


def test_config_digest_binds_exact_canonical_payload() -> None:
    assert config_digest(A2_CONFIG) != config_digest({**A2_CONFIG, "seed": 1})


def test_checked_in_config_matches_its_byte_hash_and_frozen_definition() -> None:
    root = Path(__file__).parents[1]
    loaded, digest = load_config(root)

    assert loaded == A2_CONFIG
    assert digest == sha(root / "configs" / "a2-context-verifier-v1.json")


def test_a2_code_identity_is_confined_to_a2_sources_runner_and_tests() -> None:
    root = Path(__file__).parents[1]
    identity = current_a2_code_identity(root)

    assert "src/eating_event/a2/audit.py" in identity
    assert all(path.startswith("src/eating_event/a2/") or path.startswith("scripts/run_a2_") or path.startswith("tests/test_a2_") for path in identity)


def test_candidate_key_is_role_qualified() -> None:
    assert CandidateKey("candidate/o0/inner", "same-id") != CandidateKey("candidate/o1/inner", "same-id")
    with pytest.raises(ValueError, match="role-qualified"):
        CandidateKey("", "same-id")


def test_feature_row_is_typed_26d_and_contains_no_training_label() -> None:
    row = A2FeatureRow(
        key=CandidateKey("candidate/o0/inner", "candidate-0"),
        participant_id="p00",
        record_id="r00",
        session_id="s00",
        component_id="p00|r00|s00|component-0",
        interval=EventInterval(100, 200),
        source_16d=tuple(float(i) for i in range(16)),
        features_26d=tuple(float(i) for i in range(26)),
        support_stable_ids=("p00|r00|s00|0",),
        source_hashes={"candidate": "a" * 64},
    )

    assert row.features_26d.shape == (26,)
    assert row.features_26d.dtype.name == "float32"
    assert not hasattr(row, "label")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_altered_final_checksum_manifest_is_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "final-checksums.json"
    manifest.write_text('{"files":{}}', encoding="utf-8")

    with pytest.raises(ValueError, match="manifest hash"):
        authenticate_checksum_manifest(manifest, tmp_path, "0" * 64)


def test_listed_artifact_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "derived.json"
    artifact.write_text("approved", encoding="utf-8")
    manifest = tmp_path / "final-checksums.json"
    manifest.write_text(json.dumps({"files": {"derived.json": "0" * 64}}), encoding="utf-8")

    with pytest.raises(ValueError, match="listed artifact hash"):
        authenticate_checksum_manifest(manifest, tmp_path, sha(manifest))


def test_registered_a1_code_path_drift_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="registered A1 code hash"):
        validate_a1_code_identity({"source.py": "0" * 64}, tmp_path)


def test_score_model_signature_conflict_is_rejected() -> None:
    with pytest.raises(ValueError, match="provenance conflict"):
        validate_score_provenance(
            {"role_id": "candidate/o0", "model_hash": "a" * 64, "fit_signature": "b" * 64},
            {"role_id": "candidate/o0", "model_hash": "c" * 64, "fit_signature": "b" * 64},
        )


def test_score_path_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved root"):
        resolve_approved_path(tmp_path, "..\\outside.npz", tmp_path / "scores")


@pytest.mark.parametrize(
    "ids, raw, relative, expected",
    [
        (np.array([0, 3]), np.array([0.2, 0.4]), np.array([0.2, 0.4]), [0, 1, 3]),  # missing role coverage
        (np.array([3, 0]), np.array([0.2, 0.4]), np.array([0.2, 0.4]), [0, 3]),  # reordered
        (np.array([0, 1, 1]), np.array([0.2, 0.3, 0.4]), np.array([0.2, 0.3, 0.4]), [0, 1, 2]),  # duplicate
        (np.array([0, 4]), np.array([0.2, 0.4]), np.array([0.2, 0.4]), [0, 3]),  # out of role range/identity
    ],
)
def test_global_score_id_coverage_must_be_exact(ids, raw, relative, expected) -> None:
    with pytest.raises(ValueError, match="score IDs"):
        validate_score_payload(ids, raw, relative, expected, threshold=0.0)


def test_score_payload_rejects_nonfinite_scores_and_bad_relative_values() -> None:
    ids = np.array([0, 1], dtype=np.int64)
    with pytest.raises(ValueError, match="finite"):
        validate_score_payload(ids, np.array([0.2, np.nan]), np.array([0.2, np.nan]), [0, 1], threshold=0.0)
    with pytest.raises(ValueError, match="raw minus threshold"):
        validate_score_payload(ids, np.array([0.2, 0.4]), np.array([0.2, 0.5]), [0, 1], threshold=0.0)


def test_composite_candidate_keys_allow_repeated_bare_ids_across_roles() -> None:
    rows = [
        {"role_id": "candidate/o0", "candidate_id": "same"},
        {"role_id": "candidate/o1", "candidate_id": "same"},
    ]
    check_candidate_rows(rows)

    with pytest.raises(ValueError, match="duplicate composite"):
        check_candidate_rows(rows + [rows[0]])


def test_support_must_be_present_in_role_and_candidate_component() -> None:
    candidate = {
        "role_id": "candidate/o0",
        "component_id": "p|r|s|component-0",
        "support_indices": [{"participant_id": "p", "record_id": "r", "session_id": "s", "row_index": 7}],
    }
    with pytest.raises(ValueError, match="outside role/component"):
        validate_support_identity(candidate, role_id="candidate/o0", stable_ids={"p|r|s|8"}, component_by_stable_id={"p|r|s|8": candidate["component_id"]})


def test_outer_candidate_label_must_be_null() -> None:
    with pytest.raises(ValueError, match="outer.*label"):
        validate_outer_label({"role_id": "candidate/o0/outer", "label": 1}, outer_role=True)
    validate_outer_label({"role_id": "candidate/o0/outer", "label": None}, outer_role=True)


def test_outer_valid_participants_cannot_leak_into_fit_reference_or_selection() -> None:
    with pytest.raises(ValueError, match="outer-valid participant overlap"):
        validate_outer_exclusion(
            fit_participants=["p0"],
            reference_participants=["p1"],
            selection_participants=["p2"],
            outer_valid_participants=["p0", "p3"],
        )
