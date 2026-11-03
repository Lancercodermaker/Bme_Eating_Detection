import json

import pytest

from eating_event.a1.contracts import (
    A1Config,
    ScoreProvenance,
    load_config,
    require_disjoint,
    validate_outer_exclusion,
)


def test_heldout_participant_cannot_be_in_fit_set():
    with pytest.raises(ValueError, match="participant overlap"):
        require_disjoint({"p1", "p2"}, {"p2"})


def test_legal_score_partition():
    require_disjoint({"p1", "p2"}, {"p3"})


def test_outer_validation_rejects_fit_reference_or_selection_overlap():
    with pytest.raises(ValueError, match="outer-valid"):
        validate_outer_exclusion(
            fit_participants={"p1", "p4"},
            reference_participants={"p2"},
            selection_participants={"p3"},
            outer_valid_participants={"p4"},
        )
    with pytest.raises(ValueError, match="outer-valid"):
        validate_outer_exclusion(
            fit_participants={"p1"},
            reference_participants={"p2", "p4"},
            selection_participants={"p3"},
            outer_valid_participants={"p4"},
        )


def test_oof_provenance_rejects_fit_scored_overlap():
    with pytest.raises(ValueError, match="participant overlap"):
        ScoreProvenance(
            role="oof",
            fit_participants=("p1",),
            scored_participants=("p1",),
            selection_participants=(),
            threshold_reference_participants=("p1",),
            model_hash="m",
            fit_signature="s",
            reference_row_hash="r",
            reference_count=1,
            q=0.9,
            threshold=0.2,
            feature_schema="x",
        )


def test_config_freezes_a1_scope_and_defaults(tmp_path):
    config_path = tmp_path / "a1.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "a1_end_to_end_feasibility_v1",
                "candidate_quantile": 0.9,
                "verifier_thresholds": [0.1, 0.25, 0.5],
                "seed": 20260910,
                "outer_folds": 5,
                "inner_folds": 4,
                "subinner_folds": 4,
                "candidate_fuse_ms": 300000,
                "decode_fuse_ms": 600000,
                "min_duration_ms": 180000,
                "long_fp_ms": 600000,
                "strict_iou": 0.25,
                "feature_schema": "a1_relative_event_features_v1",
                "limits": {
                    "max_candidate_roles": 105,
                    "max_verifier_roles": 25,
                    "total_wall_seconds": 21600,
                    "audit_wall_seconds": 1800,
                    "fit_wall_seconds": 7200,
                    "max_rss_bytes": 8 * 1024**3,
                    "max_disk_bytes": 2 * 1024**3,
                    "max_threads": 4,
                },
                "paths": {},
            }
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert isinstance(config, A1Config)
    assert config.candidate_quantile == 0.9
    assert config.verifier_thresholds == (0.1, 0.25, 0.5)
    assert config.candidate_hgb["max_leaf_nodes"] == 31
    assert config.verifier_hgb["max_leaf_nodes"] == 15


def test_config_rejects_scope_expansion(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "a1_end_to_end_feasibility_v1",
                "candidate_quantile": 0.8,
                "verifier_thresholds": [0.1, 0.25, 0.5],
                "seed": 20260910,
                "outer_folds": 5,
                "inner_folds": 4,
                "subinner_folds": 4,
                "limits": {},
                "paths": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="candidate_quantile"):
        load_config(path)
