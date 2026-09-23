"""Frozen A2 study configuration and label-free feature-row contracts."""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from eating_event.metrics import EventInterval


A2_CONFIG: dict[str, object] = {
    "schema": "a2_context_verifier_config_v1",
    "study_id": "a2-context-verifier-v1-001",
    "study_output": "artifacts/a2-context-verifier-v1-001",
    "a1_run_id": "a1-end-to-end-feasibility-v1-005",
    "a1_artifact_root": "artifacts/a1-end-to-end-feasibility-v1-005",
    "a1_config_path": "configs/a1-end-to-end-feasibility-v1.json",
    "source_checksum_sha256": "0543791e90df9e1bcf93111dc45e80678089898409e6888b90584fd18c469025",
    "eligibility_sha256": "68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30",
    "denominator_sha256": "6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d",
    "feature_schema": "a2_event_context_v1",
    "base_feature_schema": "a1_relative_event_features_v1",
    "base_feature_dim": 16,
    "feature_dim": 26,
    "context_feature_names": [
        "inside_mean_relative",
        "inside_p25_relative",
        "inside_positive_fraction",
        "inside_longest_positive_run_fraction",
        "pre_mean_relative",
        "pre_positive_fraction",
        "pre_observed_fraction",
        "post_mean_relative",
        "post_positive_fraction",
        "post_observed_fraction",
    ],
    "seed": 20260910,
    "candidate_quantile": 0.9,
    "lookaround_ms": 300000,
    "observed_fraction_divisor": 40,
    "verifier_thresholds": [0.1, 0.25, 0.5],
    "candidate_fuse_ms": 300000,
    "decode_fuse_ms": 600000,
    "min_duration_ms": 180000,
    "long_fp_ms": 600000,
    "strict_iou": 0.25,
    "verifier_hgb": {
        "learning_rate": 0.05,
        "max_iter": 100,
        "max_leaf_nodes": 15,
        "max_depth": None,
        "min_samples_leaf": 1,
        "l2_regularization": 1e-3,
        "max_features": 1.0,
        "max_bins": 255,
        "categorical_features": None,
        "monotonic_cst": None,
        "interaction_cst": None,
        "warm_start": False,
        "early_stopping": False,
        "scoring": "loss",
        "validation_fraction": None,
        "n_iter_no_change": 10,
        "tol": 1e-7,
        "verbose": 0,
        "random_state": 20260910,
        "class_weight": None,
        "positive_weight": 3.0,
    },
    "limits": {
        "candidate_fits": 0,
        "candidate_predicts": 0,
        "verifier_fit_attempts": 25,
        "active_wall_seconds": 7200,
        "fit_wall_seconds": 3600,
        "threads": 4,
        "disk_bytes": 1024**3,
        "rss_absolute_bytes": 8 * 1024**3,
        "rss_startup_fraction": 0.6,
    },
    "nested_roles": {
        "outer_folds": 5,
        "inner_folds": 4,
        "subinner_folds": 4,
        "candidate_roles": 105,
        "verifier_roles": 25,
        "participants": 41,
        "evaluation_gt": 234,
    },
    "outer_candidate_counts": [946, 892, 929, 653, 763],
    "outer_candidate_covered_gt": [46, 48, 47, 31, 41],
}

STUDY_001_ID = "a2-context-verifier-v1-001"
STUDY_002_ID = "a2-context-verifier-v1-002"
DEFAULT_STUDY_ID = STUDY_001_ID
PREDECESSOR_001: dict[str, object] = {
    "study_id": STUDY_001_ID,
    "status": "INVALID",
    "run_status_sha256": "321ff020f82e3a81172959c86a7f44b7cf801234b6dc4ed210bdc34c65dfcb60",
    "external_ledger_sha256": "1f8698d4957b468f0dc67fd4dfb9a42483c8b71334d8fb5808ec03999a576453",
    "mirror_ledger_sha256": "1f8698d4957b468f0dc67fd4dfb9a42483c8b71334d8fb5808ec03999a576453",
    "config_sha256": "f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5",
    "output_tree_sha256": "e58935ebfcac05a22481e14835b80e00f213304940834527116789bfb2acb4a0",
    "active_wall_seconds": 3.5,
    "fit_wall_seconds": 0.0,
    "verifier_fit_attempts": 0,
    "rss_ceiling_bytes": 2127893299,
    "output_tree_bytes": 2671,
    "external_ledger_bytes": 634,
}


def expected_study_config(study_id: str) -> dict[str, object]:
    if study_id == STUDY_001_ID:
        return copy.deepcopy(A2_CONFIG)
    if study_id != STUDY_002_ID:
        raise ValueError(f"unapproved A2 study identity: {study_id}")
    expected = copy.deepcopy(A2_CONFIG)
    expected.update({
        "study_id": STUDY_002_ID,
        "study_output": "artifacts/a2-context-verifier-v1-002",
        "ledger_path": "artifacts/a2-study-budget-v1-002.jsonl",
        "lock_path": "artifacts/a2-study-budget-v1-002.lock",
        "predecessor": copy.deepcopy(PREDECESSOR_001),
    })
    return expected


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def config_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def validate_config(config: object, *, study_id: str = DEFAULT_STUDY_ID) -> dict[str, object]:
    expected = expected_study_config(study_id)
    if not isinstance(config, dict) or canonical_json(config) != canonical_json(expected):
        raise ValueError("A2 config differs from the frozen study definition/namespace")
    return config


def config_path(root: str | Path, study_id: str = DEFAULT_STUDY_ID) -> Path:
    expected_study_config(study_id)
    filename = "a2-context-verifier-v1.json" if study_id == STUDY_001_ID else "a2-context-verifier-v1-002.json"
    return Path(root).resolve() / "configs" / filename


def load_config(root: str | Path, *, study_id: str = DEFAULT_STUDY_ID) -> tuple[dict[str, object], str]:
    workspace = Path(root).resolve()
    path = config_path(workspace, study_id)
    sidecar = path.with_suffix(".sha256")
    raw = path.read_bytes()
    expected = sidecar.read_text(encoding="ascii").strip().split()[0]
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError(f"{study_id} config SHA-256 sidecar mismatch")
    parsed = json.loads(raw)
    validate_config(parsed, study_id=study_id)
    return parsed, actual


def study_output_path(root: str | Path, config: Mapping[str, object], *, study_id: str) -> Path:
    validate_config(dict(config), study_id=study_id)
    workspace = Path(root).resolve()
    path = (workspace / str(config["study_output"])).resolve()
    expected = (workspace / ("artifacts/a2-context-verifier-v1-001" if study_id == STUDY_001_ID else "artifacts/a2-context-verifier-v1-002")).resolve()
    if path != expected:
        raise ValueError("A2 study output path differs from its fixed namespace")
    return path


def validate_study_binding(
    root: str | Path,
    output: str | Path,
    *,
    study_id: str,
    config_sha256: str,
) -> tuple[dict[str, object], Path]:
    config, actual_sha = load_config(root, study_id=study_id)
    if actual_sha != config_sha256:
        raise ValueError("A2 config SHA does not match the supervised study request")
    expected_output = study_output_path(root, config, study_id=study_id)
    if Path(output).resolve() != expected_output:
        raise ValueError("A2 output path does not match the fixed study namespace")
    return config, expected_output


class CandidateKey(tuple):
    """Role-scoped candidate identity; bare candidate IDs are never keys."""

    def __new__(cls, role_id: str, candidate_id: str) -> "CandidateKey":
        role, candidate = str(role_id), str(candidate_id)
        if not role or not candidate:
            raise ValueError("candidate key must be role-qualified")
        return tuple.__new__(cls, (role, candidate))

    @property
    def role_id(self) -> str:
        return self[0]

    @property
    def candidate_id(self) -> str:
        return self[1]


@dataclass(frozen=True)
class A2FeatureRow:
    """Label-free A2 row. Labels are joined separately by role and key."""

    key: CandidateKey
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    interval: EventInterval
    source_16d: tuple[int | float, ...]
    features_26d: np.ndarray | tuple[float, ...]
    support_stable_ids: tuple[str, ...]
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.key, CandidateKey):
            raise ValueError("A2 feature row needs a role-qualified CandidateKey")
        if not all((self.participant_id, self.record_id, self.session_id, self.component_id)):
            raise ValueError("A2 feature row identity must be complete")
        base = np.asarray(self.source_16d, dtype=np.float64)
        values = np.asarray(self.features_26d, dtype=np.float32)
        if base.shape != (16,) or not np.isfinite(base).all():
            raise ValueError("saved A1 source feature row must contain 16 finite values")
        if values.shape != (26,) or not np.isfinite(values).all():
            raise ValueError("A2 feature row must contain 26 finite float32 values")
        if not self.support_stable_ids or len(set(self.support_stable_ids)) != len(self.support_stable_ids):
            raise ValueError("A2 feature row support IDs must be nonempty and unique")
        values = values.copy()
        values.setflags(write=False)
        object.__setattr__(self, "features_26d", values)


@dataclass(frozen=True)
class ContextWindow:
    role_id: str
    global_window_index: int
    stable_id: str
    component_id: str
    start_ms: int
    end_ms: int
    relative: float

    def __post_init__(self) -> None:
        if not self.role_id or not self.stable_id or not self.component_id:
            raise ValueError("context window identity is incomplete")
        if self.global_window_index < 0 or self.end_ms <= self.start_ms:
            raise ValueError("context window index or interval is invalid")
        if not np.isfinite(self.relative):
            raise ValueError("context score must be finite")
