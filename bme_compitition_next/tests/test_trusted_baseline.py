import json

import pytest

from scripts.run_trusted_baseline import build_trusted_baseline_artifact


def test_trusted_baseline_artifact_freezes_value_split_and_metric_source(tmp_path):
    artifact = build_trusted_baseline_artifact(
        output_dir=tmp_path,
        audited_target_participants=("p-01", "p-02", "p-03", "p-04", "p-05"),
        baseline_id="m0-q50-groupnorm",
        split_seed=20260910,
        valid_fraction=0.20,
        expected_event_f1=0.17284,
    )
    assert artifact["schema_version"] == "trusted_baseline_v1"
    assert artifact["baseline_id"] == "m0-q50-groupnorm"
    assert artifact["metric"]["name"] == "event_f1"
    assert artifact["metric"]["value"] == pytest.approx(0.17284, abs=1e-5)
    assert artifact["metric"]["matching"] == "strict_iou_gt_0.25_one_to_one"
    assert artifact["metric"]["source_document"] == "docs/preflight-2026-09-10.md"
    assert artifact["split"] == {
        "strategy": "participant_frozen",
        "seed": 20260910,
        "valid_fraction": 0.20,
        "participant_order": "sorted_unique_target_train",
        "manifest": "split-manifest.json",
    }
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))["metric"]["value"] == pytest.approx(0.17284)
    assert (tmp_path / "split-manifest.json").is_file()
    assert (tmp_path / "manifest.json").is_file()


def test_trusted_baseline_records_participant_eligibility_contract(tmp_path):
    artifact = build_trusted_baseline_artifact(
        output_dir=tmp_path,
        audited_target_participants=("p-01", "p-02", "p-03", "p-04", "p-05"),
        baseline_id="m0-q50-groupnorm",
        split_seed=20260910,
        valid_fraction=0.20,
        expected_event_f1=0.17284,
        eligibility_contract={
            "schema_version": "participant_eligibility_v1",
            "manifest_sha256": "a" * 64,
            "denominator_sha256": "b" * 64,
            "event_denominator_sha256": "d" * 64,
            "source_audit_sha256": "c" * 64,
            "eligible_participant_count": 5,
            "effective_valid_event_count": 2,
        },
    )

    assert artifact["eligibility"]["manifest_sha256"] == "a" * 64
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["eligibility"]["denominator_sha256"] == "b" * 64
    assert manifest["eligibility"]["event_denominator_sha256"] == "d" * 64
