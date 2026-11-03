"""Immutable identities, provenance and frozen A1 configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence


WINDOW_FEATURE_DIM = 111
EVENT_FEATURE_DIM = 16
FEATURE_SCHEMA = "a1_relative_event_features_v1"
CONFIG_SCHEMA = "a1_end_to_end_feasibility_v1"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_disjoint(left: Iterable[str], right: Iterable[str]) -> None:
    overlap = set(map(str, left)) & set(map(str, right))
    if overlap:
        raise ValueError(f"participant overlap: {sorted(overlap)}")


def validate_outer_exclusion(
    *,
    fit_participants: Iterable[str],
    reference_participants: Iterable[str],
    selection_participants: Iterable[str],
    outer_valid_participants: Iterable[str],
) -> None:
    outer = set(map(str, outer_valid_participants))
    for name, values in (
        ("fit", fit_participants),
        ("reference", reference_participants),
        ("selection", selection_participants),
    ):
        overlap = outer & set(map(str, values))
        if overlap:
            raise ValueError(f"outer-valid participant overlap in {name}: {sorted(overlap)}")


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(sorted({str(value) for value in values}))
    if any(not value for value in result):
        raise ValueError("participant identifiers must be non-empty")
    return result


@dataclass(frozen=True, order=True)
class WindowIdentity:
    participant_id: str
    record_id: str
    session_id: str
    row_index: int

    def __post_init__(self) -> None:
        if not self.participant_id or not self.record_id or not self.session_id:
            raise ValueError("window identity fields must be non-empty")
        if self.row_index < 0:
            raise ValueError("window row_index must be non-negative")

    @property
    def stable_id(self) -> str:
        return f"{self.participant_id}|{self.record_id}|{self.session_id}|{self.row_index}"


@dataclass(frozen=True)
class PredictionIdentity:
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    ordinal: int

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("prediction ordinal must be non-negative")

    @property
    def stable_id(self) -> str:
        return "|".join(
            [self.participant_id, self.record_id, self.session_id, self.component_id, str(self.ordinal)]
        )


@dataclass(frozen=True)
class ScoreProvenance:
    role: str
    fit_participants: tuple[str, ...]
    scored_participants: tuple[str, ...]
    selection_participants: tuple[str, ...]
    threshold_reference_participants: tuple[str, ...]
    model_hash: str
    fit_signature: str
    reference_row_hash: str
    reference_count: int
    q: float
    threshold: float
    feature_schema: str
    outer_valid_participants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in {"reference", "oof", "heldout", "verifier_oof", "inner_selection"}:
            raise ValueError(f"unknown score role: {self.role}")
        if self.reference_count <= 0:
            raise ValueError("reference_count must be positive")
        if not 0 < self.q < 1:
            raise ValueError("q must be in (0, 1)")
        for field_name in (
            "fit_participants",
            "scored_participants",
            "selection_participants",
            "threshold_reference_participants",
            "outer_valid_participants",
        ):
            values = getattr(self, field_name)
            if tuple(values) != _sorted_unique(values):
                raise ValueError(f"{field_name} must be sorted and unique")
        if self.role != "reference":
            require_disjoint(self.fit_participants, self.scored_participants)
        validate_outer_exclusion(
            fit_participants=self.fit_participants,
            reference_participants=self.threshold_reference_participants,
            selection_participants=self.selection_participants,
            outer_valid_participants=self.outer_valid_participants,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "fit_participants": list(self.fit_participants),
            "scored_participants": list(self.scored_participants),
            "selection_participants": list(self.selection_participants),
            "threshold_reference_participants": list(self.threshold_reference_participants),
            "model_hash": self.model_hash,
            "fit_signature": self.fit_signature,
            "reference_row_hash": self.reference_row_hash,
            "reference_count": self.reference_count,
            "q": self.q,
            "threshold": self.threshold,
            "feature_schema": self.feature_schema,
            "outer_valid_participants": list(self.outer_valid_participants),
        }


@dataclass(frozen=True)
class A1Config:
    schema_version: str = CONFIG_SCHEMA
    candidate_quantile: float = 0.9
    verifier_thresholds: tuple[float, ...] = (0.1, 0.25, 0.5)
    seed: int = 20260910
    outer_folds: int = 5
    inner_folds: int = 4
    subinner_folds: int = 4
    candidate_fuse_ms: int = 300_000
    decode_fuse_ms: int = 600_000
    min_duration_ms: int = 180_000
    long_fp_ms: int = 600_000
    strict_iou: float = 0.25
    feature_schema: str = FEATURE_SCHEMA
    candidate_hgb: Mapping[str, object] = field(default_factory=dict)
    verifier_hgb: Mapping[str, object] = field(default_factory=dict)
    limits: Mapping[str, int] = field(default_factory=dict)
    paths: Mapping[str, str] = field(default_factory=dict)
    d3_revision: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != CONFIG_SCHEMA:
            raise ValueError(f"unsupported A1 config schema: {self.schema_version}")
        if self.candidate_quantile != 0.9:
            raise ValueError("candidate_quantile is frozen at 0.9")
        if tuple(self.verifier_thresholds) != (0.1, 0.25, 0.5):
            raise ValueError("verifier_thresholds are frozen at [0.1, 0.25, 0.5]")
        if self.seed != 20260910:
            raise ValueError("seed is frozen at 20260910")
        if (self.outer_folds, self.inner_folds, self.subinner_folds) != (5, 4, 4):
            raise ValueError("A1 fold counts are frozen at 5/4/4")
        if self.feature_schema != FEATURE_SCHEMA:
            raise ValueError(f"feature schema is frozen at {FEATURE_SCHEMA}")
        frozen = {"strict_iou": .25, "candidate_fuse_ms": 300000, "decode_fuse_ms": 600000,
                  "min_duration_ms": 180000, "long_fp_ms": 600000}
        for key, value in frozen.items():
            if getattr(self, key) != value:
                raise ValueError(f"{key} is frozen at {value}")
        for name, candidate in (("candidate_hgb", True), ("verifier_hgb", False)):
            expected = _explicit_hgb(candidate)
            supplied = dict(getattr(self, name))
            if any(key not in expected or value != expected[key] for key, value in supplied.items()):
                raise ValueError(f"{name} differs from frozen HGB")
            object.__setattr__(self, name, expected)
        if self.d3_revision not in (None, "D3-Ready-v1"):
            raise ValueError("unapproved D3 revision")
        if not 0 < self.strict_iou < 1:
            raise ValueError("strict_iou must be in (0, 1)")
        for name in ("candidate_fuse_ms", "decode_fuse_ms", "min_duration_ms", "long_fp_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        expected_limits = dict(max_candidate_roles=105,max_verifier_roles=25,total_wall_seconds=21600,
                               audit_wall_seconds=1800,fit_wall_seconds=7200,max_threads=4,
                               max_rss_bytes=8*1024**3,max_disk_bytes=2*1024**3)
        if self.limits and dict(self.limits) != expected_limits:
            raise ValueError("A1 resource limits differ from frozen authorization")
        object.__setattr__(self, "limits", expected_limits)

    def resolved_paths(self, config_path: Path) -> dict[str, Path]:
        root = config_path.resolve().parents[1]
        return {key: (root / value).resolve() for key, value in self.paths.items()}


def _explicit_hgb(candidate: bool) -> dict[str, object]:
    return {
        "learning_rate": 0.05,
        "max_iter": 100,
        "max_leaf_nodes": 31 if candidate else 15,
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
    }


def load_config(path: str | Path) -> A1Config:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("A1 config must be a JSON object")
    config = A1Config(
        schema_version=str(payload.get("schema_version", CONFIG_SCHEMA)),
        candidate_quantile=float(payload.get("candidate_quantile", 0.9)),
        verifier_thresholds=tuple(float(value) for value in payload.get("verifier_thresholds", (0.1, 0.25, 0.5))),
        seed=int(payload.get("seed", 20260910)),
        outer_folds=int(payload.get("outer_folds", 5)),
        inner_folds=int(payload.get("inner_folds", 4)),
        subinner_folds=int(payload.get("subinner_folds", 4)),
        candidate_fuse_ms=int(payload.get("candidate_fuse_ms", 300_000)),
        decode_fuse_ms=int(payload.get("decode_fuse_ms", 600_000)),
        min_duration_ms=int(payload.get("min_duration_ms", 180_000)),
        long_fp_ms=int(payload.get("long_fp_ms", 600_000)),
        strict_iou=float(payload.get("strict_iou", 0.25)),
        feature_schema=str(payload.get("feature_schema", FEATURE_SCHEMA)),
        candidate_hgb={**_explicit_hgb(True), **dict(payload.get("candidate_hgb", {}))},
        verifier_hgb={**_explicit_hgb(False), **dict(payload.get("verifier_hgb", {}))},
        limits=dict(payload.get("limits", {})),
        paths=dict(payload.get("paths", {})),
        d3_revision=payload.get("d3_revision"),
    )
    return config
