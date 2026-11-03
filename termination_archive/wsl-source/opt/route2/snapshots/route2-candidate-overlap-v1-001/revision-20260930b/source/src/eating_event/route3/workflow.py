"""Role-safe Route 3 corpus preparation and pre-fit G3 checks."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
from typing import Mapping, Sequence

import numpy as np

from eating_event.a1.pipeline import Role
from eating_event.a1.scoring import validate_g3
from eating_event.a2.execution import A2Candidate, FeatureCorpus
from eating_event.route3.budget import Route3ResourceError
from eating_event.route3.targets import assign_role_targets


ROUTE3_CODE_PATHS = (
    "src/eating_event/a1/contracts.py",
    "src/eating_event/a1/events.py",
    "src/eating_event/a1/metrics.py",
    "src/eating_event/a1/pipeline.py",
    "src/eating_event/a1/scoring.py",
    "src/eating_event/a2/audit.py",
    "src/eating_event/a2/contracts.py",
    "src/eating_event/a2/execution.py",
    "src/eating_event/metrics.py",
    "src/eating_event/route3/budget.py",
    "src/eating_event/route3/runner.py",
    "src/eating_event/route3/targets.py",
    "src/eating_event/route3/workflow.py",
    "src/eating_event/route3/__init__.py",
    "scripts/run_route3_matching_aware.py",
)

ROUTE3_CONFIGS = {
    "route3-matching-aware-v1-001": {
        "filename": "route3-matching-aware-v1.json",
        "study_output": "artifacts/route3-matching-aware-v1-001",
        "ledger_path": "artifacts/route3-matching-aware-v1-budget.jsonl",
        "lock_path": "artifacts/route3-matching-aware-v1-budget.lock",
    },
    "route3-matching-aware-v1-002": {
        "filename": "route3-matching-aware-v1-002.json",
        "study_output": "artifacts/route3-matching-aware-v1-002",
        "ledger_path": "artifacts/route3-matching-aware-v1-002-budget.jsonl",
        "lock_path": "artifacts/route3-matching-aware-v1-002-budget.lock",
    },
    "route3-matching-aware-v1-003": {
        "filename": "route3-matching-aware-v1-003.json",
        "study_output": "artifacts/route3-matching-aware-v1-003",
        "ledger_path": "artifacts/route3-matching-aware-v1-003-budget.jsonl",
        "lock_path": "artifacts/route3-matching-aware-v1-003-budget.lock",
    },
}


@dataclass(frozen=True)
class FitComposition:
    verifier_role_id: str
    candidate_role_ids: tuple[str, ...]
    rows: tuple[A2Candidate, ...]
    positive_gt_ids: tuple[str, ...]


def _json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_route3_config(
    workspace: str | Path,
    *,
    study_id: str = "route3-matching-aware-v1-001",
) -> tuple[dict[str, object], str]:
    root = Path(workspace).resolve()
    namespace = ROUTE3_CONFIGS.get(study_id)
    if namespace is None:
        raise ValueError(f"unknown Route 3 study identity: {study_id}")
    config_path = root / "configs" / str(namespace["filename"])
    raw = config_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    sidecar = config_path.with_suffix(".sha256").read_text(encoding="ascii").strip().split()[0]
    if actual_sha != sidecar:
        raise ValueError("Route 3 config SHA-256 sidecar mismatch")
    config = json.loads(raw)
    if not isinstance(config, dict) or config.get("schema") != "route3_matching_aware_config_v1":
        raise ValueError("Route 3 config schema is invalid")
    if config.get("study_id") != study_id:
        raise ValueError("Route 3 study identity is invalid")
    if (
        config.get("study_output") != namespace["study_output"]
        or config.get("ledger_path") != namespace["ledger_path"]
        or config.get("lock_path") != namespace["lock_path"]
    ):
        raise ValueError("Route 3 output namespace is not fixed")
    from eating_event.a2.contracts import STUDY_004_ID, load_config

    base_config, base_sha = load_config(root, study_id=STUDY_004_ID)
    source = config.get("source_a2")
    if not isinstance(source, dict) or (
        source.get("study_id") != STUDY_004_ID
        or source.get("config_sha256") != base_sha
        or source.get("study_output") != "artifacts/a2-context-verifier-v1-004"
        or source.get("feature_schema") != base_config.get("feature_schema")
        or source.get("feature_dim") != base_config.get("feature_dim")
    ):
        raise ValueError("Route 3 source does not match frozen A2-004")
    verifier = config.get("verifier")
    if not isinstance(verifier, dict):
        raise ValueError("Route 3 verifier config is missing")
    expected_hgb = dict(base_config["verifier_hgb"])
    expected_weight = float(expected_hgb.pop("positive_weight"))
    if (
        verifier.get("seed") != base_config.get("seed")
        or float(verifier.get("positive_weight", -1)) != expected_weight
        or _json_sha256(verifier.get("hgb")) != _json_sha256(expected_hgb)
        or config.get("thresholds") != base_config.get("verifier_thresholds")
    ):
        raise ValueError("Route 3 verifier settings differ from A2-004")
    decoder = config.get("decoder")
    if not isinstance(decoder, dict) or (
        decoder.get("candidate_fuse_ms") != base_config.get("candidate_fuse_ms")
        or decoder.get("final_fuse_ms") != base_config.get("decode_fuse_ms")
        or decoder.get("minimum_duration_ms") != base_config.get("min_duration_ms")
        or decoder.get("long_fp_ms") != base_config.get("long_fp_ms")
    ):
        raise ValueError("Route 3 decoder differs from A2-004")
    target = config.get("target")
    if not isinstance(target, dict) or (
        target.get("iou_threshold") != base_config.get("strict_iou")
        or target.get("outer_labels") is not None
        or target.get("method") != "candidate_selected_by_existing_participant_greedy_one_to_one_matcher"
        or target.get("construction_scope") != "each_non_outer_candidate_role_using_only_its_scored_participants_eligible_gt"
        or target.get("comparison") != "strictly_greater_than"
        or target.get("candidate_intervals") != "frozen_a2_004_post_300_second_fusion"
        or target.get("training_label_stage") != "before_verifier_threshold_and_final_decoder"
        or target.get("tie_break") != {
            "candidate_order": "candidate_id_ascending",
            "truth_order": "event_id_ascending",
            "edge_order": "iou_descending_then_candidate_index_then_truth_index",
        }
    ):
        raise ValueError("Route 3 target settings differ from the reviewed proposal")
    expected_roles = base_config.get("nested_roles")
    evaluator = config.get("evaluator")
    if not isinstance(expected_roles, dict) or not isinstance(evaluator, dict):
        raise ValueError("Route 3 role graph contract is missing")
    role_fields = {
        "participants": "participants",
        "eligible_ground_truth": "evaluation_gt",
        "outer_folds": "outer_folds",
        "inner_folds": "inner_folds",
        "subinner_folds": "subinner_folds",
        "candidate_roles": "candidate_roles",
        "verifier_roles": "verifier_roles",
    }
    if (
        any(evaluator.get(key) != expected_roles.get(source_key) for key, source_key in role_fields.items())
        or evaluator.get("strict_iou") != base_config.get("strict_iou")
    ):
        raise ValueError("Route 3 evaluator role graph differs from A2-004")
    outer_counts = evaluator.get("outer_candidate_counts")
    if (
        outer_counts != base_config.get("outer_candidate_counts")
        or sum(outer_counts or ()) != 4183
        or evaluator.get("outer_candidate_rows") != 4183
    ):
        raise ValueError("Route 3 outer candidate counts differ from A2-004")
    if (
        verifier.get("family") != "sklearn.ensemble.HistGradientBoostingClassifier"
        or verifier.get("fit_attempts") != 25
        or verifier.get("score_calls") != 25
        or evaluator.get("inner_threshold_decodes") != 60
        or evaluator.get("outer_decodes") != 5
        or evaluator.get("outer_evaluations") != 5
    ):
        raise ValueError("Route 3 call plan differs from its reviewed fixed graph")
    limits = config.get("limits")
    if not isinstance(limits, dict) or (
        limits.get("candidate_fits") != 0
        or limits.get("candidate_predicts") != 0
        or limits.get("verifier_fit_attempts") != verifier.get("fit_attempts")
        or limits.get("verifier_score_calls") != verifier.get("score_calls")
        or limits.get("threads") != 2
    ):
        raise ValueError("Route 3 resource and model-call limits are inconsistent")
    return config, actual_sha


def route3_environment_identity() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "scipy": importlib.metadata.version("scipy"),
        "scikit_learn": importlib.metadata.version("scikit-learn"),
        "threadpoolctl": importlib.metadata.version("threadpoolctl"),
        "psutil": importlib.metadata.version("psutil"),
    }


def route3_code_identity(workspace: str | Path) -> dict[str, str]:
    root = Path(workspace).resolve()
    return {relative: _file_sha256(root / relative) for relative in ROUTE3_CODE_PATHS}


def verify_a2_004_complete(workspace: str | Path, config: Mapping[str, object]) -> dict[str, object]:
    root = Path(workspace).resolve()
    source = config["source_a2"]
    output = root / str(source["study_output"])
    status = json.loads((output / "run-status.json").read_text(encoding="utf-8"))
    if not isinstance(status, dict) or (
        status.get("status") != "COMPLETE"
        or status.get("study_id") != source.get("study_id")
        or status.get("config_sha256") != source.get("config_sha256")
        or status.get("audit_ready_sha256") != source.get("audit_ready_sha256")
    ):
        raise ValueError("Route 3 requires the frozen completed A2-004 source")
    ready_path = output / "audit-ready.json"
    ready_sha = _file_sha256(ready_path)
    if ready_sha != source.get("audit_ready_sha256"):
        raise ValueError("A2-004 audit-ready identity changed")
    return {
        "study_id": status["study_id"],
        "status": status["status"],
        "config_sha256": status["config_sha256"],
        "audit_ready_sha256": ready_sha,
    }


def make_route3_audit_ready(
    workspace: str | Path,
    config: Mapping[str, object],
    config_sha256: str,
    corpus: FeatureCorpus,
    target_audit: Mapping[str, object],
) -> dict[str, object]:
    source_digests = {
        role_id: {
            "ordered_candidate_keys_sha256": digests["ordered_candidate_keys_sha256"],
            "feature_matrix_sha256": digests["feature_matrix_sha256"],
            "a2_training_label_sha256_not_used": digests["training_label_join_sha256"],
        }
        for role_id, digests in (corpus.input_digests or {}).items()
    }
    payload: dict[str, object] = {
        "schema": "route3_matching_aware_audit_ready_v1",
        "study_id": config["study_id"],
        "config_sha256": config_sha256,
        "source_a2": verify_a2_004_complete(workspace, config),
        "source_role_digests": source_digests,
        "route3_target_audit_sha256": target_audit["audit_sha256"],
        "route3_target_fit_precheck": target_audit["verifier_fits"],
        "route3_code_identity": route3_code_identity(workspace),
        "environment": route3_environment_identity(),
        "limits": dict(config["limits"]),
        "outer_labels_remain_null_until_evaluation": True,
    }
    payload["audit_ready_sha256"] = _json_sha256(payload)
    return payload


def verify_route3_audit_ready(
    workspace: str | Path,
    config: Mapping[str, object],
    config_sha256: str,
) -> dict[str, object]:
    root = Path(workspace).resolve()
    output = root / str(config["study_output"])
    status = json.loads((output / "run-status.json").read_text(encoding="utf-8"))
    ready_path = output / "audit-ready.json"
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    target_audit_path = output / "target-audit.json"
    size_profile_path = output / "synthetic-size-profile.json"
    target_audit = json.loads(target_audit_path.read_text(encoding="utf-8"))
    size_profile = json.loads(size_profile_path.read_text(encoding="utf-8"))
    provenance_precheck = json.loads((output / "fit-provenance-precheck.json").read_text(encoding="utf-8"))
    if not isinstance(status, dict) or not isinstance(ready, dict):
        raise ValueError("Route 3 audit-ready status is malformed")
    ready_sha = _file_sha256(ready_path)
    expected_content_sha = _json_sha256({key: value for key, value in ready.items() if key != "audit_ready_sha256"})
    if (
        status.get("status") != "AUDIT_READY"
        or status.get("study_id") != config["study_id"]
        or status.get("config_sha256") != config_sha256
        or status.get("audit_ready_sha256") != ready_sha
        or ready.get("audit_ready_sha256") != expected_content_sha
        or ready.get("route3_code_identity") != route3_code_identity(root)
        or ready.get("environment") != route3_environment_identity()
        or not isinstance(target_audit, dict)
        or target_audit.get("audit_sha256") != _json_sha256({
            key: value for key, value in target_audit.items() if key != "audit_sha256"
        })
        or ready.get("route3_target_audit_sha256") != target_audit.get("audit_sha256")
        or ready.get("route3_target_fit_precheck") != target_audit.get("verifier_fits")
        or ready.get("synthetic_size_profile_sha256") != _json_sha256(size_profile)
        or ready.get("actual_fit_provenance_precheck_sha256") != _json_sha256(provenance_precheck)
        or provenance_precheck.get("status") != "PASS"
        or provenance_precheck.get("fit_calls") != 0
    ):
        raise ValueError("Route 3 audit-ready identity is stale or inconsistent")
    verify_a2_004_complete(root, config)
    return ready


def verify_route3_environment(config: Mapping[str, object]) -> dict[str, str]:
    actual = route3_environment_identity()
    expected = dict(config["environment"])
    if actual != expected:
        raise ValueError(f"Route 3 environment differs from the frozen A1 environment: {actual}")
    return actual


def route3_size_profile(
    target_audit: Mapping[str, object],
    config: Mapping[str, object],
    *,
    rss_ceiling_bytes: int,
) -> dict[str, int | bool]:
    """Size synthetic feature/label arrays and a conservative output envelope."""

    role_rows = target_audit.get("candidate_roles")
    if not isinstance(role_rows, list) or not role_rows:
        raise ValueError("Route 3 sizing requires registered candidate role counts")
    candidate_count = sum(int(row["candidate_count"]) for row in role_rows)
    if candidate_count <= 0:
        raise ValueError("Route 3 sizing found no saved candidates")
    expected_candidate_count = config["evaluator"].get("candidate_rows_across_all_roles")
    if expected_candidate_count is not None and candidate_count != expected_candidate_count:
        raise ValueError("Route 3 all-role candidate count differs from the frozen resource review")
    import psutil

    process = psutil.Process(os.getpid())

    def process_tree_rss() -> int:
        total = int(process.memory_info().rss)
        for child in process.children(recursive=True):
            try:
                total += int(child.memory_info().rss)
            except psutil.Error:
                continue
        return total

    rss_before = process_tree_rss()
    synthetic_features = np.zeros((candidate_count, 26), dtype=np.float32)
    synthetic_labels = np.zeros(candidate_count, dtype=np.uint8)
    synthetic_features[-1, -1] = 1.0
    synthetic_labels[-1] = 1
    synthetic_matrix_bytes = int(synthetic_features.nbytes)
    synthetic_label_bytes = int(synthetic_labels.nbytes)
    synthetic_nonzero = float(np.sum(synthetic_features)) + int(np.sum(synthetic_labels))
    synthetic_peak_rss = process_tree_rss()
    del synthetic_features, synthetic_labels
    rss_after = process_tree_rss()

    target_audit_bytes = len(json.dumps(target_audit, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    conservative_label_artifact_bytes = candidate_count * 256
    model_artifact_allowance_bytes = int(config["verifier"]["fit_attempts"]) * 8 * 1024**2
    other_output_allowance_bytes = 4 * 1024**2
    projected_disk_bytes = (
        target_audit_bytes
        + conservative_label_artifact_bytes
        + model_artifact_allowance_bytes
        + other_output_allowance_bytes
    )
    candidate_object_estimate_bytes = candidate_count * 512
    base_audit_rss_comparator = int(config["resource_comparator_only"]["a2_004_audit_rss_bytes"])
    comparator_projected_rss = (
        base_audit_rss_comparator
        + 2 * synthetic_matrix_bytes
        + synthetic_label_bytes
        + candidate_count * 16 * 8
        + candidate_object_estimate_bytes
    )
    measured_projected_rss = rss_before + 2 * synthetic_matrix_bytes + synthetic_label_bytes
    projected_rss_bytes = max(comparator_projected_rss, measured_projected_rss)
    outer_rows = sorted(
        (row for row in role_rows if row.get("outer_label_free") is True),
        key=lambda row: int(str(row["role_id"]).split("outer-", 1)[1].split("/", 1)[0]),
    )
    outer_candidate_counts = [int(row["candidate_count"]) for row in outer_rows]
    expected_outer_counts = config["evaluator"]["outer_candidate_counts"]
    if outer_candidate_counts != expected_outer_counts or sum(outer_candidate_counts) != 4183:
        raise ValueError("Route 3 synthetic sizing outer counts differ from frozen A2-004")
    disk_cap = int(config["limits"]["disk_bytes"])
    if projected_disk_bytes * 2 > disk_cap:
        raise Route3ResourceError("synthetic Route 3 disk estimate lacks the required 2x cap margin")
    if projected_rss_bytes * 2 > rss_ceiling_bytes:
        raise Route3ResourceError("synthetic Route 3 RSS estimate lacks the required 2x cap margin")
    return {
        "candidate_rows_across_all_roles": candidate_count,
        "outer_candidate_counts": outer_candidate_counts,
        "outer_candidate_rows": sum(outer_candidate_counts),
        "feature_columns": 26,
        "synthetic_feature_matrix_bytes": synthetic_matrix_bytes,
        "synthetic_label_vector_bytes": synthetic_label_bytes,
        "synthetic_nonzero_check": int(synthetic_nonzero == 2.0),
        "feature_matrix_copies_written": 0,
        "conservative_label_artifact_bytes": conservative_label_artifact_bytes,
        "model_artifact_allowance_bytes": model_artifact_allowance_bytes,
        "target_audit_bytes": target_audit_bytes,
        "projected_route3_disk_bytes": projected_disk_bytes,
        "route3_disk_cap_bytes": disk_cap,
        "projected_route3_rss_bytes": projected_rss_bytes,
        "route3_rss_cap_bytes": rss_ceiling_bytes,
        "synthetic_rss_before_bytes": rss_before,
        "synthetic_peak_rss_bytes": synthetic_peak_rss,
        "synthetic_rss_after_bytes": rss_after,
        "comparator_projected_route3_rss_bytes": comparator_projected_rss,
        "measured_projected_route3_rss_bytes": measured_projected_rss,
        "two_x_disk_margin_pass": projected_disk_bytes * 2 <= disk_cap,
        "two_x_rss_margin_pass": projected_rss_bytes * 2 <= rss_ceiling_bytes,
    }


def write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_fit_compositions(
    roles: Sequence[Role],
    candidates_by_role: Mapping[str, Sequence[A2Candidate]],
    matched_gt_by_role: Mapping[str, Mapping[tuple[str, str], str]],
) -> tuple[FitComposition, ...]:
    """Compose training rows exactly as the frozen A2 nested executor does."""

    candidate_roles = tuple(role for role in roles if role.kind == "candidate")
    verifier_roles = sorted(
        (role for role in roles if role.kind == "verifier"),
        key=lambda role: (role.outer_fold, role.inner_fold is None, role.inner_fold or ""),
    )
    compositions: list[FitComposition] = []
    for verifier_role in verifier_roles:
        if verifier_role.inner_fold is None:
            training_roles = sorted(
                (
                    role for role in candidate_roles
                    if role.outer_fold == verifier_role.outer_fold
                    and role.inner_fold is not None
                    and role.subinner_fold is None
                ),
                key=lambda role: role.inner_fold or "",
            )
        else:
            training_roles = sorted(
                (
                    role for role in candidate_roles
                    if role.outer_fold == verifier_role.outer_fold
                    and role.inner_fold == verifier_role.inner_fold
                    and role.subinner_fold is not None
                ),
                key=lambda role: role.subinner_fold or "",
            )
        role_ids = tuple(role.role_id for role in training_roles)
        if not role_ids or any(role_id not in candidates_by_role for role_id in role_ids):
            raise ValueError(f"missing candidate rows for verifier fit {verifier_role.role_id}")
        rows = tuple(row for role_id in role_ids for row in candidates_by_role[role_id])
        positive_gt_ids = tuple(sorted({
            (row.participant_id, matched_gt_by_role[role_id][(role_id, row.candidate_id)])
            for role_id in role_ids
            for row in candidates_by_role[role_id]
            if row.label == 1 and (role_id, row.candidate_id) in matched_gt_by_role.get(role_id, {})
        }))
        compositions.append(FitComposition(
            verifier_role_id=verifier_role.role_id,
            candidate_role_ids=role_ids,
            rows=rows,
            positive_gt_ids=positive_gt_ids,
        ))
    return tuple(compositions)


def validate_fit_compositions(
    compositions: Sequence[FitComposition],
    *,
    expected_fit_count: int = 25,
) -> tuple[dict[str, object], ...]:
    """Fail closed unless every frozen verifier fit passes G3."""

    if len(compositions) != expected_fit_count:
        raise ValueError(f"expected {expected_fit_count} verifier fits, found {len(compositions)}")
    results: list[dict[str, object]] = []
    for composition in compositions:
        if any(row.label not in (0, 1) for row in composition.rows):
            raise ValueError(f"G3 {composition.verifier_role_id}: training labels are incomplete")
        labels = np.asarray([row.label for row in composition.rows], dtype=np.int8)
        participants = tuple(row.participant_id for row in composition.rows)
        try:
            validate_g3(labels, participants)
        except ValueError as exc:
            raise ValueError(f"G3 {composition.verifier_role_id}: {exc}") from exc
        positive_count = int(np.count_nonzero(labels == 1))
        positive_gt_count = len(composition.positive_gt_ids)
        if positive_gt_count != positive_count:
            raise ValueError(
                f"G3 {composition.verifier_role_id}: positive candidate and assigned GT counts differ"
            )
        feature_digest = hashlib.sha256()
        for row in composition.rows:
            feature_digest.update(np.asarray(row.features_26d, dtype=np.float32).tobytes())
        results.append({
            "verifier_role_id": composition.verifier_role_id,
            "training_candidate_role_ids": list(composition.candidate_role_ids),
            "candidate_count": len(composition.rows),
            "positive_candidate_count": positive_count,
            "positive_participant_count": len({
                participant for participant, label in zip(participants, labels) if label == 1
            }),
            "distinct_positive_gt_count": positive_gt_count,
            "class_values": sorted(map(int, np.unique(labels))),
            "ordered_candidate_keys_sha256": _json_sha256([
                [row.role_id, row.candidate_id] for row in composition.rows
            ]),
            "feature_matrix_sha256": feature_digest.hexdigest(),
            "training_label_join_sha256": _json_sha256([
                [row.role_id, row.candidate_id, int(row.label)] for row in composition.rows
            ]),
        })
    return tuple(results)


def prepare_matching_aware_corpus(
    corpus: FeatureCorpus,
    *,
    iou_threshold: float = 0.25,
    expected_fit_count: int = 25,
) -> tuple[FeatureCorpus, dict[str, object]]:
    """Replace saved overlap labels only in memory; preserve all frozen inputs."""

    rows_by_role: dict[str, tuple[A2Candidate, ...]] = {}
    matched_gt_by_role: dict[str, dict[tuple[str, str], str]] = {}
    role_audits: list[dict[str, object]] = []
    candidate_roles = sorted(
        (role for role in corpus.roles if role.kind == "candidate"),
        key=lambda role: (role.outer_fold, role.inner_fold is None, role.inner_fold or "", role.subinner_fold or ""),
    )
    for role in candidate_roles:
        source_rows = corpus.candidates_by_role.get(role.role_id)
        if source_rows is None:
            raise ValueError(f"missing A2-004 candidate role {role.role_id}")
        rows, matches = assign_role_targets(
            role,
            tuple(source_rows),
            corpus.truths_by_participant,
            iou_threshold=iou_threshold,
        )
        rows_by_role[role.role_id] = rows
        matched_gt_by_role[role.role_id] = matches
        labels = [int(row.label) for row in rows if row.label is not None]
        if role.inner_fold is None and any(row.label is not None for row in rows):
            raise ValueError("outer labels were materialized during target preparation")
        role_audits.append({
            "role_id": role.role_id,
            "candidate_count": len(rows),
            "outer_label_free": role.inner_fold is None and all(row.label is None for row in rows),
            "positive_candidate_count": None if role.inner_fold is None else sum(label == 1 for label in labels),
            "negative_candidate_count": None if role.inner_fold is None else sum(label == 0 for label in labels),
            "positive_participant_count": None if role.inner_fold is None else len({row.participant_id for row in rows if row.label == 1}),
            "distinct_positive_gt_count": len({
                (row.participant_id, matches[(role.role_id, row.candidate_id)])
                for row in rows
                if (role.role_id, row.candidate_id) in matches
            }),
            "ordered_candidate_keys_sha256": _json_sha256([
                [row.role_id, row.candidate_id] for row in rows
            ]),
            "target_label_join_sha256": _json_sha256([
                [row.role_id, row.candidate_id, row.label] for row in rows
            ]),
        })
    candidate_role_ids = {role.role_id for role in candidate_roles}
    if candidate_role_ids != set(rows_by_role):
        raise ValueError("candidate role set changed during target preparation")
    prepared = replace(corpus, candidates_by_role=rows_by_role)
    compositions = build_fit_compositions(prepared.roles, rows_by_role, matched_gt_by_role)
    fit_audits = validate_fit_compositions(compositions, expected_fit_count=expected_fit_count)
    report = {
        "schema": "route3_matching_aware_target_audit_v1",
        "target": "selected_by_local_strict_iou_one_to_one_assignment",
        "strict_iou_threshold": float(iou_threshold),
        "candidate_role_count": len(candidate_roles),
        "outer_label_accessed_for_target_construction": False,
        "candidate_roles": role_audits,
        "verifier_fit_count": len(compositions),
        "verifier_fits": list(fit_audits),
    }
    report["audit_sha256"] = _json_sha256(report)
    return prepared, report


def load_a2_004_corpus(workspace: str | Path, *, progress_callback=None) -> FeatureCorpus:
    """Load authenticated, already-materialized A2-004 inputs without rerunning A2."""

    from eating_event.a2.audit import load_audited_corpus
    from eating_event.a2.contracts import STUDY_004_ID

    output = Path(workspace).resolve() / "artifacts" / "a2-context-verifier-v1-004"
    return load_audited_corpus(
        workspace,
        output,
        study_id=STUDY_004_ID,
        progress_callback=progress_callback,
    )
