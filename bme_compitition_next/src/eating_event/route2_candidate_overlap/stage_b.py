"""A2-004-equivalent, staged-GT verifier adapter for the Route 2 study.

This module is preparation only.  Its entry points require the separately
frozen A+B admission, the Stage A candidate files, and the audited budget
controller.  Importing this module does not open an artifact or start a study.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing, nullcontext
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import pickle
from typing import Any, Protocol, Sequence

import numpy as np

from eating_event.a1.events import A1Candidate, decode_candidates
from eating_event.a1.metrics import (
    AggregateMetrics,
    PredictionRecord,
    QualityDecision,
    evaluate_quality,
)
from eating_event.a1.scoring import fit_verifier_estimator, validate_g3
from eating_event.metrics import EventInterval

from .budget import AppendOnlyLedger, BudgetGuard, PredictionFreezeReceipt, StageBProjection, stage_a_projection_disk_bytes
from .candidates import Candidate, CandidateFileReceipt, sorted_stream_fingerprint
from .control_matches import HistoricalControlMatchStore
from .contracts import (
    ExperimentApproval,
    OUTER_CONTROL_CANDIDATES_PHASE,
    RegisteredFile,
    RoleSpec,
    StudyStage,
    StudyStatus,
    TREATMENT_CANDIDATE_FIELDS,
    require_frozen_admission,
)
from .features import ContextWindow, build_26d, build_source_16d
from .gt_provider import FrozenPredictionReceipt, FrozenRoleGraph, ScopedTruthProvider, TruthReadScope
from .inputs import LazyRoleLoader
from .phase_worker import (
    EvaluationPhaseResult,
    InnerSelectionPhaseResult,
    LabelCandidate,
    PhaseOperation,
    PhaseResult,
    TrainingPhaseResult,
)
from .references import ApprovedReferenceStore
from .source_snapshot import (
    require_controller_owned_readonly_tree,
    verify_snapshot_module,
)


_CONFIG_SHA256 = "233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043"
_A2_ROLE_DIGESTS_SHA256 = "634ffeea5d877ff65f6f1f77d73c581ea2e1367d146bef971be4f9c6123702df"
_SOURCE_SHA256 = {
    "src/eating_event/a2/audit.py": "3da72cc775aaa2381a9f2d1fcd86801db425015e97f1bb4da4fb9d8a325d9bed",
    "src/eating_event/a2/execution.py": "6ca6cdff4c3adf4c1cba50dd72229dcf80ee2ff4aaad4c9c8bb6fdb6f9465e33",
    "src/eating_event/a2/features.py": "30eaffc5e3cd39455b1d3d429b82cbdf873755169343e67e4ec9db0e11e53581",
    "src/eating_event/a1/events.py": "294fcd6b2bb4af787209a99d57a66131347556a0f33d761d6a3102ae69e26a4f",
    "src/eating_event/a1/scoring.py": "244a34d02aa60bb58463b8848a09fefcedf6f49d4959a11d2a09137ae5c60f16",
    "src/eating_event/a1/metrics.py": "0f91566608c77694f1011214ea945afeb89e845d571f61049b73d4e37788f504",
    "src/eating_event/metrics.py": "3033f62a59ea59f2647c7c2e0dce298b80834dc4a62697853f95dd6f4b73b972",
}
_THRESHOLDS = (0.10, 0.25, 0.50)
_PREDICTION_FIELDS = (
    "prediction_id", "participant_id", "record_id", "session_id",
    "source_segment_id", "start_ms", "end_ms",
)
_MAX_ROW_BYTES = 1024 * 1024


class VerifierDataInsufficient(ValueError):
    """A frozen training role fails G3 before its fit reservation."""


@dataclass(frozen=True, slots=True)
class _RoleRows:
    role: RoleSpec
    candidates: tuple[Candidate, ...]
    candidate_ids: tuple[str, ...]
    features: np.ndarray
    labels: tuple[int, ...] | None = None
    positive_gt_commitments: tuple[str, ...] = ()

    def with_labels(self, labels: tuple[int, ...], positive_gt_commitments: tuple[str, ...]) -> "_RoleRows":
        if len(labels) != len(self.candidates) or any(value not in (0, 1) for value in labels):
            raise ValueError("training label join is incomplete or nonbinary")
        if any(len(item) != 64 or any(char not in "0123456789abcdef" for char in item) for item in positive_gt_commitments):
            raise ValueError("training positive GT commitments are malformed")
        return replace(self, labels=labels, positive_gt_commitments=positive_gt_commitments)


@dataclass(frozen=True, slots=True)
class FitSummary:
    verifier_role_id: str
    training_candidate_roles: tuple[str, ...]
    fit_participants: tuple[str, ...]
    candidate_count: int
    positive_candidate_count: int
    positive_participant_count: int
    distinct_positive_canonical_gt_count: int
    ordered_candidate_keys_sha256: str
    feature_matrix_sha256: str
    training_label_join_sha256: str
    model_path: str
    model_sha256: str
    fit_attempt: int


@dataclass(frozen=True, slots=True)
class StageBResult:
    status: StudyStatus
    selected_thresholds: tuple[tuple[str, float], ...]
    pooled_f1: float | None
    pooled_gt_count: int
    pooled_metrics: AggregateMetrics
    fold_metrics: tuple[AggregateMetrics, ...]
    quality: QualityDecision
    fit_provenance: tuple[FitSummary, ...]
    matched_gt_commitments: tuple[str, ...]
    control_matched_gt_commitments: tuple[str, ...]
    matched_gt_added_commitments: tuple[str, ...]
    matched_gt_lost_commitments: tuple[str, ...]
    outer_candidate_counts: tuple[tuple[str, int], ...]
    outer_candidate_covered_gt: tuple[tuple[str, int], ...]
    verifier_fit_attempts: int
    verifier_prediction_batches: int
    decoder_calls: int
    evaluator_calls: int
    pooled_aggregation_calls: int
    pooled_aggregation_completed: bool
    pooled_gt_reads: int
    outer_reference_candidate_covered_gt: tuple[tuple[str, int], ...] = ()
    outer_candidate_added_gt_commitments: tuple[tuple[str, tuple[str, ...]], ...] = ()
    outer_candidate_lost_gt_commitments: tuple[tuple[str, tuple[str, ...]], ...] = ()
    outer_control_matched_gt_commitments: tuple[tuple[str, tuple[str, ...]], ...] = ()
    outer_matched_gt_added_commitments: tuple[tuple[str, tuple[str, ...]], ...] = ()
    outer_matched_gt_lost_commitments: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class PhaseRunReceipt:
    """Descriptive data; native authority remains the original private transaction."""

    operation: PhaseOperation
    scope_sha256: str
    payload_sha256: str
    result_sha256: str
    authorization_event_sha256: str
    os_revoke_receipt_sha256: str
    child_exited: bool
    view_revoked: bool
    result: PhaseResult


class PhaseRunner(Protocol):
    """Reviewed OS boundary for one GT operation and one mounted view.

    The implementation must call phase_worker.execute_phase_operation in a
    short-lived child. It may use ledger/guard only in the parent controller;
    these live objects must not enter the GT child. It must wait for child exit,
    revoke the sole GT bind, and return an OS revocation receipt. The parent
    legacy adapter then appends the durable ledger revocation event. Native
    phases use the fixed original transaction and its broker-owned ledger facts.
    """

    def implementation_sha256(self) -> str: ...

    def execute(
        self,
        *,
        scope: TruthReadScope,
        registered_view: RegisteredFile,
        release_authorization_sha256: str,
        operation: PhaseOperation,
        candidates: tuple[LabelCandidate, ...],
        reference_candidates: tuple[LabelCandidate, ...] | None,
        control_final_matches: RegisteredFile | None,
        control_metrics_sha256: str | None,
        predictions: tuple[PredictionRecord, ...],
        participant_ids: tuple[str, ...],
        ledger: AppendOnlyLedger,
        guard: BudgetGuard,
    ) -> PhaseRunReceipt: ...


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fit_arrays(rows: Sequence[_RoleRows], fit_participants: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    if not rows or any(item.labels is None for item in rows):
        raise ValueError("fit requires role-scoped complete training labels")
    candidates = [candidate for item in rows for candidate in item.candidates]
    if not candidates:
        raise VerifierDataInsufficient("G3 requires positive and negative candidates")
    features = np.asarray([feature for item in rows for feature in item.features], dtype=np.float32)
    labels = np.asarray([label for item in rows for label in item.labels or ()], dtype=np.int8)
    participants = tuple(candidate.participant_id for candidate in candidates)
    if features.shape != (len(candidates), 26) or not np.isfinite(features).all():
        raise ValueError("verifier fit feature matrix is not finite 26D")
    if labels.shape != (len(candidates),) or set(labels.tolist()) != {0, 1}:
        raise VerifierDataInsufficient("G3 requires both positive and negative candidates")
    if set(participants) - set(fit_participants):
        raise PermissionError("training rows escape the verifier fit participant whitelist")
    try:
        validate_g3(labels, participants)
    except ValueError as exc:
        raise VerifierDataInsufficient(f"G3: {exc}") from exc
    return features, labels, participants


def _a1_decode_view(rows: _RoleRows) -> tuple[A1Candidate, ...]:
    return tuple(
        A1Candidate(
            candidate_id=candidate_id,
            participant_id=candidate.participant_id,
            record_id=candidate.record_id,
            session_id=candidate.session_id,
            component_id=candidate.component_id,
            interval=EventInterval(candidate.start_ms, candidate.end_ms),
            features=np.asarray(candidate.source_16d, dtype=np.float64),
            support_indices=(),  # A1 decoder reads only candidate geometry and identity.
            source_segment_id=None,
            boundary_kind=candidate.boundary_kind,
            label=None,
        )
        for candidate, candidate_id in zip(rows.candidates, rows.candidate_ids, strict=True)
    )


def _read_prediction_file(path: Path, receipt: PredictionFreezeReceipt) -> tuple[PredictionRecord, ...]:
    if _file_sha256(path) != receipt.prediction_sha256:
        raise PermissionError("frozen decoded prediction bytes have changed")
    result: list[PredictionRecord] = []
    seen: set[str] = set()
    with path.open("rb") as stream:
        while raw := stream.readline(_MAX_ROW_BYTES + 1):
            if len(raw) > _MAX_ROW_BYTES:
                raise ValueError("prediction row exceeds the frozen row bound")
            row = json.loads(raw)
            if not isinstance(row, dict) or set(row) != set(_PREDICTION_FIELDS):
                raise ValueError("prediction file contains an unknown field")
            if any(type(row[field]) is not str or not row[field] for field in _PREDICTION_FIELDS[:4]):
                raise ValueError("prediction identity is malformed")
            if row["source_segment_id"] is not None:
                raise ValueError("prediction source segment must remain null")
            if type(row["start_ms"]) is not int or type(row["end_ms"]) is not int:
                raise ValueError("prediction bounds must be exact integers")
            if row["end_ms"] <= row["start_ms"] or row["prediction_id"] in seen:
                raise ValueError("prediction interval or identity is invalid")
            seen.add(row["prediction_id"])
            result.append(PredictionRecord(
                prediction_id=row["prediction_id"],
                participant_id=row["participant_id"],
                record_id=row["record_id"],
                session_id=row["session_id"],
                source_segment_id=None,
                interval=EventInterval(row["start_ms"], row["end_ms"]),
            ))
    return tuple(result)


class StageBAdapter:
    """Fixed nested study; the caller cannot supply model or evaluator callbacks."""

    def __init__(
        self,
        *,
        roles: tuple[RoleSpec, ...],
        role_graph: FrozenRoleGraph,
        truth_provider: ScopedTruthProvider,
        control_matches: HistoricalControlMatchStore,
        repo_root: Path,
        config_path: Path,
        gt_view_registry_path: Path,
        gt_role_scopes_path: Path,
        phase_runner: PhaseRunner,
    ) -> None:
        if (type(role_graph) is not FrozenRoleGraph or type(truth_provider) is not ScopedTruthProvider
                or type(control_matches) is not HistoricalControlMatchStore
                or control_matches.path_map is not truth_provider.path_map
                or control_matches.roles != roles):
            raise PermissionError("Stage B requires the fixed physical-GT provider and role graph types")
        self.roles = roles
        self.role_graph = role_graph
        self.truth_provider = truth_provider
        self.control_matches = control_matches
        self.repo_root = repo_root
        self.config_path = config_path
        self.gt_view_registry_path = gt_view_registry_path
        self.gt_role_scopes_path = gt_role_scopes_path
        self.phase_runner = phase_runner
        self._role_by_id = {role.role_id: role for role in roles}
        self._outer: dict[str, RoleSpec] = {}
        self._inner: dict[str, tuple[RoleSpec, ...]] = {}
        self._subinner: dict[str, tuple[RoleSpec, ...]] = {}
        self._validate_role_shape()

    def _validate_role_shape(self) -> None:
        if len(self.roles) != 105 or len(self._role_by_id) != 105:
            raise ValueError("Stage B requires exactly 105 unique candidate roles")
        outer: dict[str, RoleSpec] = {}
        inner: dict[str, list[RoleSpec]] = defaultdict(list)
        subinner: dict[str, list[RoleSpec]] = defaultdict(list)
        for role in self.roles:
            parts = role.role_id.split("/")
            if role.kind == "outer":
                if parts != ["candidate", role.outer_id, "outer"] or role.outer_id in outer:
                    raise ValueError("outer role identity is not frozen A1 shape")
                outer[role.outer_id] = role
            elif role.kind == "inner_heldout":
                if len(parts) != 4 or parts[:2] != ["candidate", role.outer_id] or parts[3] != "inner":
                    raise ValueError("inner held-out role identity is not frozen A1 shape")
                inner[role.outer_id].append(role)
            elif role.kind == "inner_train":
                if len(parts) != 5 or parts[:2] != ["candidate", role.outer_id] or parts[4] != "subinner":
                    raise ValueError("subinner training role identity is not frozen A1 shape")
                subinner["/".join(parts[:3])].append(role)
            else:
                raise ValueError("candidate role has an unknown nested kind")
        if (
            len(outer) != 5
            or set(inner) != set(outer)
            or any(len(value) != 4 for value in inner.values())
            or len(subinner) != 20
            or any(len(value) != 4 for value in subinner.values())
            or sum(map(len, subinner.values())) != 80
        ):
            raise ValueError("Stage B roles are not the frozen 5/4/4 nested graph")
        for outer_id, outer_role in outer.items():
            ordered_inner = tuple(sorted(inner[outer_id], key=lambda item: item.role_id))
            if self.role_graph.outer_role_ids[outer_id] != outer_role.role_id:
                raise ValueError("outer role differs from staged GT role graph")
            if self.role_graph.inner_evaluation_roles_by_outer[outer_id] != tuple(
                item.role_id for item in ordered_inner
            ):
                raise ValueError("inner role order differs from staged GT role graph")
            if set(outer_role.fit_participants) != set(self.role_graph.outer_fit_participants[outer_id]):
                raise ValueError("outer training whitelist differs from GT graph")
            if set(outer_role.scored_participants) != set(self.role_graph.outer_evaluation_participants[outer_id]):
                raise ValueError("outer evaluation whitelist differs from GT graph")
            if Counter(p for role in ordered_inner for p in role.scored_participants) != Counter(outer_role.fit_participants):
                raise ValueError("inner held-out roles do not partition outer training participants")
            for role in ordered_inner:
                parent = role.role_id.removesuffix("/inner")
                children = tuple(sorted(subinner[parent], key=lambda item: item.role_id))
                if Counter(p for child in children for p in child.scored_participants) != Counter(role.fit_participants):
                    raise ValueError("subinner roles do not partition inner training participants")
                for child in children:
                    if set(child.fit_participants) | set(child.scored_participants) != set(role.fit_participants):
                        raise ValueError("subinner participant scope differs from its parent")
        for role in self.roles:
            if role.kind != "outer":
                if self.role_graph.training_outer_ids.get(role.role_id) != role.outer_id:
                    raise ValueError("training label role lacks an exact outer fold binding")
                if set(self.role_graph.training_label_participants.get(role.role_id, ())) != set(role.scored_participants):
                    raise ValueError("training label participants differ from candidate role")
        self._outer = outer
        self._inner = {key: tuple(sorted(value, key=lambda item: item.role_id)) for key, value in inner.items()}
        self._subinner = {key: tuple(sorted(value, key=lambda item: item.role_id)) for key, value in subinner.items()}

    def _require_historical_identity(self, readiness: Any) -> None:
        frozen = require_frozen_admission()
        root = self.repo_root.resolve(strict=True)
        if root != Path(frozen.source_snapshot_root).resolve(strict=True):
            raise PermissionError("A2 source identity must be checked in the frozen source snapshot")
        manifest_path = Path(frozen.source_snapshot_manifest_path)
        verify_snapshot_module(
            root,
            Path(__file__),
            manifest_path.read_bytes(),
            expected_manifest_sha256=frozen.source_snapshot_sha256,
            expected_module_relative_path="src/eating_event/route2_candidate_overlap/stage_b.py",
            mount_path=frozen.source_snapshot_root,
            mountinfo_text=Path("/proc/self/mountinfo").read_text(encoding="utf-8"),
        )
        require_controller_owned_readonly_tree(root)
        config = (root / "configs/a2-context-verifier-v1-004.json").resolve(strict=True)
        if self.config_path.resolve(strict=True) != config or _file_sha256(config) != _CONFIG_SHA256:
            raise PermissionError("A2-004 verifier configuration identity has changed")
        value = json.loads(config.read_text(encoding="utf-8"))
        expected = {
            "study_id": "a2-context-verifier-v1-004",
            "feature_schema": "a2_event_context_v1",
            "base_feature_dim": 16,
            "feature_dim": 26,
            "seed": 20260910,
            "lookaround_ms": 300000,
            "observed_fraction_divisor": 40,
            "verifier_thresholds": [0.1, 0.25, 0.5],
            "decode_fuse_ms": 600000,
            "min_duration_ms": 180000,
            "long_fp_ms": 600000,
            "strict_iou": 0.25,
        }
        if any(value.get(key) != expected_item for key, expected_item in expected.items()):
            raise PermissionError("A2-004 protocol constants differ from the frozen study")
        hgb = value.get("verifier_hgb")
        if not isinstance(hgb, dict) or hgb.get("positive_weight") != 3.0 or hgb.get("max_iter") != 100:
            raise PermissionError("A2-004 HGB fit parameters differ")
        for relative, digest in _SOURCE_SHA256.items():
            if _file_sha256((root / relative).resolve(strict=True)) != digest:
                raise PermissionError(f"historical A1/A2 implementation changed: {relative}")
        equivalence = readiness.equivalence
        if (
            equivalence.verifier_config_sha256.lower() != _CONFIG_SHA256
            or equivalence.a2_audit_code_sha256.lower() != _SOURCE_SHA256["src/eating_event/a2/audit.py"]
            or equivalence.a2_role_digests_sha256.lower() != _A2_ROLE_DIGESTS_SHA256
            or equivalence.interval_iou_code_sha256.lower() != _SOURCE_SHA256["src/eating_event/metrics.py"]
            or equivalence.a1_label_code_sha256.lower() != _SOURCE_SHA256["src/eating_event/a1/events.py"]
            or equivalence.feature_16d_code_sha256.lower() != _SOURCE_SHA256["src/eating_event/a1/events.py"]
            or equivalence.feature_10d_code_sha256.lower() != _SOURCE_SHA256["src/eating_event/a2/features.py"]
            or equivalence.threshold_selection_sha256.lower() != _SOURCE_SHA256["src/eating_event/a2/execution.py"]
            or equivalence.decoder_sha256.lower() != _SOURCE_SHA256["src/eating_event/a1/events.py"]
            or equivalence.matcher_evaluator_sha256.lower() != _SOURCE_SHA256["src/eating_event/a1/metrics.py"]
            or equivalence.role_graph_sha256.lower() != self.role_graph.sha256.lower()
        ):
            raise PermissionError("A2-004 equivalence receipt is not tied to the exact historical sources")

    def preflight(
        self,
        *,
        approval: ExperimentApproval,
        readiness: Any,
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
        loader: LazyRoleLoader,
    ) -> None:
        """Check registrations and code identity before any Stage A reconstruction."""

        from .execution import ABReadiness

        if type(self) is not StageBAdapter or type(readiness) is not ABReadiness:
            raise PermissionError("Stage B requires the fixed, independently reviewed adapter/readiness types")
        if type(guard) is not BudgetGuard or type(ledger) is not AppendOnlyLedger or type(loader) is not LazyRoleLoader:
            raise PermissionError("Stage B requires exact budget, ledger, and loader implementations")
        approval.require_full_ab()
        readiness.require_complete()
        frozen = require_frozen_admission()
        from .linux_production_controller import LinuxProductionController
        if type(guard.enforcer) is LinuxProductionController:
            from .linux_phase_runner import _require_original_executor
            runner_sha256 = _require_original_executor(self.phase_runner, guard, ledger).source_sha256
        else:
            runner_sha256 = self.phase_runner.implementation_sha256()
        if (
            self.roles != loader.role_specs
            or self.role_graph.sha256.lower() != frozen.role_graph_sha256.lower()
            or self.truth_provider._role_graph is not self.role_graph
            or self.truth_provider._ledger is not ledger
            or type(self.control_matches) is not HistoricalControlMatchStore
            or self.control_matches.path_map is not loader.path_map
            or self.control_matches.roles != self.roles
            or loader.registry_sha256 != frozen.role_input_registry_sha256.lower()
            or guard.ledger is not ledger
            or guard.study_root != ledger.study_root
            or readiness.stage_b_adapter_sha256.lower() != _file_sha256(Path(__file__))
            or frozen.stage_b_adapter_sha256.lower() != _file_sha256(Path(__file__))
            or readiness.phase_worker_sha256.lower() != _file_sha256(Path(__file__).with_name("phase_worker.py"))
            or frozen.phase_worker_sha256.lower() != _file_sha256(Path(__file__).with_name("phase_worker.py"))
            or runner_sha256 != frozen.phase_runner_sha256.lower()
        ):
            raise PermissionError("Stage B adapter or source graph differs from independently reviewed pins")
        self._require_historical_identity(readiness)
        self._require_gt_registry_identity(frozen)
        self.control_matches.require_pinned_registration()

    def _require_gt_registry_identity(self, frozen: Any) -> None:
        """Bind provider objects to approved physical registry bytes, not caller maps."""

        if (
            self.gt_view_registry_path.resolve(strict=True)
            != self.truth_provider._registry_path.resolve(strict=True)
            or self.gt_role_scopes_path.resolve(strict=True)
            != self.truth_provider._role_scopes_path.resolve(strict=True)
            or
            _file_sha256(self.gt_view_registry_path) != frozen.gt_view_registry_sha256.lower()
            or _file_sha256(self.gt_role_scopes_path) != frozen.gt_role_graph_projection_sha256.lower()
        ):
            raise PermissionError("staged GT registry or role-scope bytes differ from approval")
        self.truth_provider.require_pinned_registration()

    def _read_candidate_role(
        self,
        receipt: CandidateFileReceipt,
        role: RoleSpec,
        *,
        guard: BudgetGuard,
        loader: LazyRoleLoader,
    ) -> _RoleRows:
        if receipt.role_id != role.role_id or receipt.row_count < 0 or receipt.file_bytes < 0:
            raise PermissionError("Stage A candidate receipt differs from its role")
        path = Path(receipt.path)
        resolved = path.resolve(strict=True)
        root = guard.study_root.resolve(strict=True)
        if path.is_symlink() or root not in resolved.parents or not resolved.is_file():
            raise PermissionError("candidate receipt is outside the fixed study output")
        if resolved.stat().st_size != receipt.file_bytes or _file_sha256(resolved) != receipt.sha256.lower():
            raise PermissionError("Stage A treatment candidate file changed before Stage B")
        candidates: list[Candidate] = []
        candidate_ids: list[str] = []
        ordinal_by_component: dict[str, int] = defaultdict(int)
        with resolved.open("rb") as stream:
            while raw := stream.readline(_MAX_ROW_BYTES + 1):
                if len(raw) > _MAX_ROW_BYTES:
                    raise ValueError("candidate row exceeds the approved row bound")
                row = json.loads(raw)
                if not isinstance(row, dict) or set(row) != set(TREATMENT_CANDIDATE_FIELDS):
                    raise PermissionError("treatment file contains nonapproved candidate fields")
                if any(type(row[name]) is not str or not row[name] for name in (
                    "role_id", "candidate_id", "participant_id", "record_id", "session_id", "component_id", "boundary_kind"
                )):
                    raise ValueError("candidate identity fields are malformed")
                if any(type(row[name]) is not int for name in ("start_ms", "end_ms")):
                    raise ValueError("candidate interval must use exact integers")
                support = row["support_indices"]
                source = row["source_16d"]
                if (
                    type(support) is not list or not support or any(type(index) is not int for index in support)
                    or type(source) is not list or len(source) != 16
                    or any(type(value) not in (int, float) for value in source)
                    or row["source_segment_id"] is not None
                ):
                    raise ValueError("candidate support or new 16D source is malformed")
                candidate = Candidate(
                    role_id=row["role_id"],
                    participant_id=row["participant_id"],
                    record_id=row["record_id"],
                    session_id=row["session_id"],
                    component_id=row["component_id"],
                    start_ms=row["start_ms"],
                    end_ms=row["end_ms"],
                    support_indices=tuple(support),
                    source_16d=tuple(float(value) for value in source),
                    boundary_kind=row["boundary_kind"],
                    source_segment_id=None,
                )
                if candidate.role_id != role.role_id or candidate.participant_id not in role.scored_participants:
                    raise PermissionError("candidate row escapes its frozen scored role")
                ordinal = ordinal_by_component[candidate.component_id]
                if row["candidate_id"] != f"{candidate.component_id}|candidate-{ordinal}":
                    raise ValueError("candidate ID differs from A1 component ordinal rule")
                ordinal_by_component[candidate.component_id] = ordinal + 1
                candidates.append(candidate)
                candidate_ids.append(row["candidate_id"])
        if len(candidates) != receipt.row_count:
            raise ValueError("candidate row count differs from Stage A receipt")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate identity repeats within a role")
        if sorted_stream_fingerprint(candidates)[1] != receipt.interval_fingerprint:
            raise ValueError("treatment candidate intervals differ from the Stage A fingerprint")
        with loader.open_role(role.role_id) as loaded:
            registered = loader._registrations[role.role_id]
            support_windows = loaded.support_windows(registered)
        by_component: dict[str, list[Any]] = defaultdict(list)
        by_global: dict[int, Any] = {}
        for window in support_windows:
            by_component[window.component_id].append(window)
            by_global[window.global_index] = window
        context_by_component = {
            component_id: tuple(
                ContextWindow(
                    role_id=role.role_id,
                    component_id=component_id,
                    global_index=window.global_index,
                    start_ms=window.start_ms,
                    end_ms=window.end_ms,
                    relative=window.relative,
                )
                for window in component_windows
            )
            for component_id, component_windows in by_component.items()
        }
        features: list[np.ndarray] = []
        for candidate in candidates:
            source_support = [by_global.get(index) for index in candidate.support_indices]
            if any(item is None for item in source_support):
                raise ValueError("candidate support lacks a role-scoped scored window")
            windows = [item for item in source_support if item is not None]
            if (
                any(item.component_id != candidate.component_id or item.relative < 0 for item in windows)
                or min(item.start_ms for item in windows) != candidate.start_ms
                or max(item.end_ms for item in windows) != candidate.end_ms
            ):
                raise ValueError("candidate support differs from its interval/component")
            reconstructed_16d = build_source_16d(windows, start_ms=candidate.start_ms, end_ms=candidate.end_ms)
            if not np.array_equal(reconstructed_16d, np.asarray(candidate.source_16d, dtype=np.float64)):
                raise ValueError("Stage A new 16D differs from registered score/window support")
            features.append(build_26d(candidate, context_by_component[candidate.component_id]))
        matrix = np.asarray(features, dtype=np.float32).reshape((len(candidates), 26))
        if not np.isfinite(matrix).all():
            raise ValueError("new A2 26D matrix has a nonfinite value")
        return _RoleRows(role, tuple(candidates), tuple(candidate_ids), matrix)

    def _materialize_role(
        self,
        receipt: CandidateFileReceipt,
        role: RoleSpec,
        *,
        guard: BudgetGuard,
        loader: LazyRoleLoader,
    ) -> _RoleRows:
        with guard.activity(f"stage_b_role_features:{role.role_id}"):
            return self._read_candidate_role(receipt, role, guard=guard, loader=loader)

    def _execute_phase(
        self,
        *,
        scope: TruthReadScope,
        operation: PhaseOperation,
        candidates: tuple[LabelCandidate, ...] = (),
        reference_candidates: tuple[LabelCandidate, ...] | None = None,
        predictions: tuple[PredictionRecord, ...] = (),
        participant_ids: tuple[str, ...] = (),
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
    ) -> PhaseResult:
        """Authorize one view, then accept only a closed, revoked child receipt."""

        if scope.stage != {
            "training_labels": StudyStage.TRAIN_LABELS,
            "inner_evaluator": StudyStage.INNER_EVALUATION,
            "outer_evaluator": StudyStage.OUTER_EVALUATION,
        }[operation]:
            raise PermissionError("GT operation differs from its release stage")
        if (
            operation == "outer_evaluator" and reference_candidates is None
        ) or (
            operation != "outer_evaluator" and reference_candidates is not None
        ):
            raise PermissionError("control-candidate snapshot is required only for outer evaluation")
        if operation != "training_labels" and not guard._activity_open:
            raise PermissionError("phase evaluator requires its reserved budget activity")
        with (
            guard.activity(f"stage_b_training_phase:{scope.role_ids[0]}")
            if operation == "training_labels" else nullcontext()
        ):
            self.role_graph.validate_scope(scope)
            control_final_matches = self.control_matches.registered_for(scope) if operation == "outer_evaluator" else None
            control_metrics_sha256 = require_frozen_admission().a2_004_final_metrics_sha256.lower() if operation == "outer_evaluator" else None
            scope_id = scope.role_ids[0] if scope.stage.value == "train_labels" else scope.outer_id
            try:
                registered = self.truth_provider._views[(scope.stage, scope_id)]
            except KeyError as exc:
                raise PermissionError("stage-scoped GT view is absent from the frozen registry") from exc
            if registered.scope_sha256 != scope.participant_scope_attestation:
                raise PermissionError("phase view differs from the approved role scope")
            scope_sha256 = hashlib.sha256(_canonical(asdict(scope))).hexdigest()
            payload_sha256 = hashlib.sha256(_canonical({
                "candidates": [asdict(item) for item in candidates],
                "reference_candidates": (
                    None if reference_candidates is None
                    else [asdict(item) for item in reference_candidates]
                ),
                "control_final_matches": None if control_final_matches is None else asdict(control_final_matches),
                "control_metrics_sha256": control_metrics_sha256,
                "predictions": [asdict(item) for item in predictions],
                "participant_ids": list(participant_ids),
            })).hexdigest()
            # Native release/revoke belong solely to the actual original
            # broker. A same-type caller receipt never installs a transaction.
            from .linux_production_controller import LinuxProductionController
            native_controller = type(guard.enforcer) is LinuxProductionController
            native_transaction = None
            if native_controller:
                from .linux_phase_runner import (
                    _execute_original_phase, _take_original_phase_result,
                    _accept_original_phase_result, _reject_original_phase_result,
                )
                native_transaction = _execute_original_phase(self.phase_runner,
                    scope=scope,
                    registered_view=registered,
                    operation=operation,
                    candidates=candidates,
                    reference_candidates=reference_candidates,
                    control_final_matches=control_final_matches,
                    control_metrics_sha256=control_metrics_sha256,
                    predictions=predictions,
                    participant_ids=participant_ids,
                    ledger=ledger,
                    guard=guard,
                )
                receipt, authorization, revoke_event = _take_original_phase_result(
                    self.phase_runner, native_transaction, scope=scope, operation=operation,
                    guard=guard, ledger=ledger)
            else:
                authorization = ledger.record_gt_release(scope)
                receipt = self.phase_runner.execute(
                    scope=scope,
                    registered_view=registered,
                    release_authorization_sha256=authorization,
                    operation=operation,
                    candidates=candidates,
                    reference_candidates=reference_candidates,
                    control_final_matches=control_final_matches,
                    control_metrics_sha256=control_metrics_sha256,
                    predictions=predictions,
                    participant_ids=participant_ids,
                    ledger=ledger,
                    guard=guard,
                )
            try:
                if (
                    type(receipt) is not PhaseRunReceipt
                    or receipt.operation != operation
                    or receipt.scope_sha256 != scope_sha256
                    or receipt.payload_sha256 != payload_sha256
                    or receipt.authorization_event_sha256 != authorization
                    or receipt.child_exited is not True
                    or receipt.view_revoked is not True
                    or len(receipt.os_revoke_receipt_sha256) != 64
                    or any(ch not in "0123456789abcdef" for ch in receipt.os_revoke_receipt_sha256)
                    or receipt.result_sha256 != hashlib.sha256(_canonical(asdict(receipt.result))).hexdigest()
                ):
                    raise PermissionError("phase worker lacks a complete view-revocation receipt")
                if operation == "training_labels":
                    if type(receipt.result) is not TrainingPhaseResult:
                        raise PermissionError("training phase returned an evaluation payload")
                    if (
                        len(receipt.result.labels) != len(candidates)
                        or any(type(label) is not int or label not in (0, 1) for label in receipt.result.labels)
                        or len(set(receipt.result.positive_gt_commitments))
                        != len(receipt.result.positive_gt_commitments)
                    ):
                        raise PermissionError("training phase returned an incomplete label join")
                elif operation == "inner_evaluator":
                    if type(receipt.result) is not InnerSelectionPhaseResult:
                        raise PermissionError("inner evaluation returned a nonminimal GT result")
                    result = receipt.result
                    if (
                        type(result.fp) is not int or result.fp < 0
                        or type(result.eligible_gt_count) is not int or result.eligible_gt_count < 0
                        or type(result.prediction_count) is not int or result.prediction_count != len(predictions)
                        or result.fp > result.prediction_count
                        or (result.f1 is not None and (type(result.f1) is not float or not 0 <= result.f1 <= 1))
                    ):
                        raise PermissionError("inner selection values are malformed")
                else:
                    if type(receipt.result) is not EvaluationPhaseResult:
                        raise PermissionError("evaluation phase returned a training payload")
                    result = receipt.result
                    metric = result.metric
                    if (
                        type(metric) is not AggregateMetrics
                        or type(result.eligible_gt_count) is not int
                        or result.eligible_gt_count < 0
                        or metric.tp + metric.fn != result.eligible_gt_count
                        or metric.tp + metric.fp != len(predictions)
                        or metric.matched_count != metric.tp
                        or set(item.participant_id for item in metric.participants) != set(scope.participants)
                        or len(metric.participants) != len(scope.participants)
                    ):
                        raise PermissionError("evaluation phase returned inconsistent participant metrics")
                    if (
                        type(result.candidate_covered_gt) is not int
                        or not 0 <= result.candidate_covered_gt <= result.eligible_gt_count
                        or type(result.reference_candidate_covered_gt) is not int
                        or not 0 <= result.reference_candidate_covered_gt <= result.eligible_gt_count
                        or type(result.candidate_added_gt_commitments) is not tuple
                        or type(result.candidate_lost_gt_commitments) is not tuple
                    ):
                        raise PermissionError("outer phase returned invalid candidate coverage")
                    additions = result.candidate_added_gt_commitments
                    losses = result.candidate_lost_gt_commitments
                    if (
                        tuple(sorted(set(additions))) != additions
                        or tuple(sorted(set(losses))) != losses
                        or set(additions) & set(losses)
                        or any(
                            type(value) is not str or len(value) != 64
                            or any(char not in "0123456789abcdef" for char in value)
                            for value in (*additions, *losses)
                        )
                        or result.candidate_covered_gt - result.reference_candidate_covered_gt
                        != len(additions) - len(losses)
                    ):
                        raise PermissionError("outer phase returned inconsistent candidate-coverage additions or losses")
                    control_matched = result.control_matched_gt_commitments
                    matched_additions = result.matched_gt_added_commitments
                    matched_losses = result.matched_gt_lost_commitments
                    treatment_matched = {
                        gt_id for participant in metric.participants
                        for _, gt_id, _ in participant.matched_pairs
                    }
                    eligible = treatment_matched | {
                        gt_id for participant in metric.participants for gt_id in participant.unmatched_truth_ids
                    }
                    if (any(type(items) is not tuple or any(type(item) is not str or len(item) != 64
                                or any(char not in "0123456789abcdef" for char in item) for item in items)
                            or tuple(sorted(set(items))) != items
                            for items in (control_matched, matched_additions, matched_losses))
                            or len(treatment_matched) != metric.tp
                            or not set(control_matched) <= eligible
                            or matched_additions != tuple(sorted(treatment_matched - set(control_matched)))
                            or matched_losses != tuple(sorted(set(control_matched) - treatment_matched))):
                        raise PermissionError("outer phase omitted or changed the saved-control final matched-GT comparison")
                if native_controller:
                    _accept_original_phase_result(self.phase_runner, native_transaction, receipt,
                                                  guard=guard, ledger=ledger)
                else:
                    revoke_event = ledger.record_gt_revoke(
                        scope, authorization, receipt.os_revoke_receipt_sha256,
                    )
                    ledger.append("gt_phase_result_accepted", {
                        "stage": scope.stage.value,
                        "outer_id": scope.outer_id,
                        "role_ids": list(scope.role_ids),
                        "operation": operation,
                        "authorization_event_sha256": authorization,
                        "revocation_event_sha256": revoke_event,
                        "os_revoke_receipt_sha256": receipt.os_revoke_receipt_sha256,
                        "result_sha256": receipt.result_sha256,
                    })
                return receipt.result
            except BaseException as error:
                if native_transaction is not None:
                    _reject_original_phase_result(self.phase_runner, native_transaction, error,
                                                  guard=guard, ledger=ledger)
                raise

    def _training_labels(self, rows: _RoleRows, *, guard: BudgetGuard, ledger: AppendOnlyLedger) -> _RoleRows:
        scope = self.role_graph.training_scope(rows.role.role_id)
        result = self._execute_phase(
            scope=scope, operation="training_labels",
            candidates=tuple(
                LabelCandidate(candidate_id, candidate.participant_id, candidate.start_ms, candidate.end_ms)
                for candidate, candidate_id in zip(rows.candidates, rows.candidate_ids, strict=True)
            ),
            guard=guard, ledger=ledger,
        )
        if type(result) is not TrainingPhaseResult:
            raise PermissionError("training label result has the wrong type")
        return rows.with_labels(result.labels, result.positive_gt_commitments)

    @staticmethod
    def _read_frozen_predictions(
        receipt: PredictionFreezeReceipt,
        *,
        phase: str,
        outer_id: str,
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
        participants: tuple[str, ...],
    ) -> tuple[PredictionRecord, ...]:
        with guard.activity(f"read_decoded:{receipt.role_id}:{receipt.threshold}"):
            ledger.require_frozen_prediction(
                receipt,
                phase=phase,  # type: ignore[arg-type]
                role_id=receipt.role_id,
                outer_id=outer_id,
                threshold=receipt.threshold,
            )
            rows = _read_prediction_file(Path(receipt.prediction_path), receipt)
            if any(item.participant_id not in participants for item in rows):
                raise PermissionError("frozen decoded prediction escapes its held-out role")
            return rows

    @staticmethod
    def _prediction_path(guard: BudgetGuard, *, phase: str, role_id: str, threshold: float) -> Path:
        key = hashlib.sha256(f"{phase}|{role_id}|{threshold:.2f}".encode("utf-8")).hexdigest()
        directory = guard.study_root / "decoded-predictions"
        directory.mkdir(exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise PermissionError("decoded prediction directory is not an ordinary study directory")
        return directory / f"{key}.jsonl"

    def _freeze_decoded(
        self,
        *,
        rows: _RoleRows,
        scores: np.ndarray,
        threshold: float,
        phase: str,
        predict_attempt: int,
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
    ) -> PredictionFreezeReceipt:
        decoder_attempt, decoded = guard.invoke_call(
            "decoder",
            rows.role.role_id,
            lambda: decode_candidates(
                _a1_decode_view(rows), scores,
                threshold=threshold, min_duration_ms=180000, decode_fuse_gap_ms=600000,
            ),
        )
        records = tuple(PredictionRecord.from_decoded(item) for item in decoded)
        with guard.activity(f"persist_decoded:{rows.role.role_id}:{threshold:.2f}"):
            path = self._prediction_path(guard, phase=phase, role_id=rows.role.role_id, threshold=threshold)
            with path.open("xb") as stream:
                for item in records:
                    value = {
                        "prediction_id": item.prediction_id,
                        "participant_id": item.participant_id,
                        "record_id": item.record_id,
                        "session_id": item.session_id,
                        "source_segment_id": item.source_segment_id,
                        "start_ms": item.interval.start_ms,
                        "end_ms": item.interval.end_ms,
                    }
                    stream.write(_canonical(value) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            receipt = ledger.freeze_prediction(
                phase=phase,  # type: ignore[arg-type]
                role_id=rows.role.role_id,
                outer_id=rows.role.outer_id,
                threshold=f"{threshold:.2f}",
                prediction_path=path,
                predict_attempt=predict_attempt,
                decoder_attempt=decoder_attempt,
            )
            if phase == "outer":
                available = set(rows.candidate_ids)
                lineage: list[dict[str, object]] = []
                for decoded_item in decoded:
                    source_ids = tuple(decoded_item.source_candidate_ids)
                    if not source_ids or len(set(source_ids)) != len(source_ids) or set(source_ids) - available:
                        raise ValueError("outer prediction lineage contains an unknown candidate")
                    lineage.append({
                        "prediction_id": decoded_item.identity.stable_id,
                        "role_id": rows.role.role_id,
                        "candidate_keys": [[rows.role.role_id, candidate_id] for candidate_id in source_ids],
                        "interval": {
                            "start_ms": decoded_item.interval.start_ms,
                            "end_ms": decoded_item.interval.end_ms,
                        },
                    })
                ledger.append("outer_prediction_lineage_frozen", {
                    "outer_id": rows.role.outer_id,
                    "prediction_event_sha256": receipt.ledger_event_sha256,
                    "lineage": lineage,
                })
        return receipt

    @staticmethod
    def _score(model: object, rows: _RoleRows) -> np.ndarray:
        if set(candidate.participant_id for candidate in rows.candidates) - set(rows.role.scored_participants):
            raise PermissionError("verifier scoring rows escape the held-out role")
        if not len(rows.candidates):
            return np.empty(0, dtype=np.float64)
        result = np.asarray(model.predict_proba(rows.features)[:, 1], dtype=np.float64)
        if result.shape != (len(rows.candidates),) or not np.isfinite(result).all():
            raise ValueError("verifier scores are nonfinite or misaligned")
        return result

    @staticmethod
    def _fit_model(
        rows: Sequence[_RoleRows],
        *,
        verifier_role_id: str,
        fit_participants: tuple[str, ...],
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
    ) -> tuple[object, FitSummary]:
        with guard.activity(f"prepare_fit:{verifier_role_id}"):
            x, y, participants = _fit_arrays(rows, fit_participants)
            candidate_keys = [
                [item.role.role_id, candidate_id]
                for item in rows for candidate_id in item.candidate_ids
            ]
            label_keys = [
                [item.role.role_id, candidate_id, label]
                for item in rows
                for candidate_id, label in zip(item.candidate_ids, item.labels or (), strict=True)
            ]
            keys_sha = hashlib.sha256(_canonical(candidate_keys)).hexdigest()
            labels_sha = hashlib.sha256(_canonical(label_keys)).hexdigest()
            matrix_sha = hashlib.sha256(x.tobytes()).hexdigest()
            positive_gt_commitments = {
                digest for item in rows for digest in item.positive_gt_commitments
            }
            positive_candidate_count = int(np.count_nonzero(y == 1))
            positive_participant_count = len({
                participant for participant, label in zip(participants, y.tolist(), strict=True)
                if label == 1
            })

        def fit_and_persist() -> tuple[object, str, str]:
            model = fit_verifier_estimator(
                x, y, participants, positive_weight=3.0,
                random_state=20260910, max_iter=100,
            )
            output_dir = guard.study_root / "verifier-models"
            if not output_dir.exists():
                output_dir.mkdir()
            if output_dir.is_symlink() or not output_dir.is_dir():
                raise PermissionError("verifier model directory is not a study directory")
            stem = hashlib.sha256(verifier_role_id.encode("utf-8")).hexdigest()
            target = output_dir / f"{stem}.pickle"
            content = pickle.dumps(model, protocol=5)
            with target.open("xb") as stream:
                if stream.write(content) != len(content):
                    raise OSError("partial verifier model write")
                stream.flush()
                os.fsync(stream.fileno())
            return model, str(target), hashlib.sha256(content).hexdigest()

        attempt, (model, model_path, model_sha) = guard.invoke_call(
            "verifier_fit", verifier_role_id, fit_and_persist,
        )
        summary = FitSummary(
            verifier_role_id=verifier_role_id,
            training_candidate_roles=tuple(item.role.role_id for item in rows),
            fit_participants=tuple(sorted(set(participants))),
            candidate_count=len(participants),
            positive_candidate_count=positive_candidate_count,
            positive_participant_count=positive_participant_count,
            distinct_positive_canonical_gt_count=len(positive_gt_commitments),
            ordered_candidate_keys_sha256=keys_sha,
            feature_matrix_sha256=matrix_sha,
            training_label_join_sha256=labels_sha,
            model_path=model_path,
            model_sha256=model_sha,
            fit_attempt=attempt,
        )
        ledger.append("verifier_fit_provenance", asdict(summary))
        return model, summary

    @staticmethod
    def _pooled_from_disjoint_folds(
        folds: Sequence[AggregateMetrics], participant_ids: tuple[str, ...],
    ) -> AggregateMetrics:
        """One GT-free pooled-reduction reservation over disjoint outer folds.

        ``evaluate_participants`` computes each participant independently,
        sorts participants by ID, then reduces TP/FP/FN and matched errors.
        Frozen outer folds partition the 41 participants, so reducing their
        participant metrics is identical to evaluating pooled predictions and
        truths. This consumes the 21st evaluation/reduction protocol slot, not a
        GT-backed evaluator call, and keeps raw GT intervals in short-lived
        children.
        """

        per_participant = tuple(sorted(
            (part for fold in folds for part in fold.participants),
            key=lambda item: item.participant_id,
        ))
        if (
            len(folds) != 5
            or tuple(item.participant_id for item in per_participant) != tuple(sorted(participant_ids))
            or len(set(participant_ids)) != len(participant_ids)
        ):
            raise ValueError("pooled participant set differs from disjoint outer folds")
        tp = sum(item.tp for item in per_participant)
        fp = sum(item.fp for item in per_participant)
        fn = sum(item.fn for item in per_participant)
        matches = sum(len(item.matched_pairs) for item in per_participant)
        long_fp_count = sum(item.long_fp_count for item in per_participant)
        return AggregateMetrics(
            tp=tp, fp=fp, fn=fn,
            precision=tp / (tp + fp) if tp + fp else 0.0,
            recall=tp / (tp + fn) if tp + fn else 0.0,
            f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            start_mae_ms=(
                sum((item.start_mae_ms or 0) * len(item.matched_pairs) for item in per_participant) / matches
                if matches else None
            ),
            end_mae_ms=(
                sum((item.end_mae_ms or 0) * len(item.matched_pairs) for item in per_participant) / matches
                if matches else None
            ),
            matched_count=matches,
            participants=per_participant,
            long_fp_count=long_fp_count,
            long_fp_fraction=long_fp_count / fp if fp else 0.0,
        )

    def run(
        self,
        *,
        stage_a: Any,
        reference_provider: ApprovedReferenceStore,
        guard: BudgetGuard,
        ledger: AppendOnlyLedger,
        loader: LazyRoleLoader,
        approval: ExperimentApproval,
        readiness: Any,
    ) -> StageBResult:
        """Continue a complete Stage A in the same one-shot A+B ledger."""

        from .execution import StageAResult

        self.preflight(
            approval=approval, readiness=readiness, guard=guard, ledger=ledger, loader=loader,
        )
        if (
            type(reference_provider) is not ApprovedReferenceStore
            or reference_provider.identity_loader is not loader
            or reference_provider.path_map is not loader.path_map
            or reference_provider.roles != self.roles
            or reference_provider.registry_sha256.lower() != readiness.reference_registry_sha256.lower()
        ):
            raise PermissionError("Stage B control references differ from the frozen 105-role registry")
        reference_provider.require_pinned_registration()
        self.control_matches.require_pinned_registration()
        if (
            type(stage_a) is not StageAResult
            or stage_a.status is not None
            or stage_a.reference_roles != 105
            or stage_a.treatment_roles != 105
        ):
            raise PermissionError("Stage B requires the successful, unterminated Stage A result")
        files = tuple(stage_a.treatment_files)
        if len(files) != 105 or any(type(item) is not CandidateFileReceipt for item in files):
            raise PermissionError("Stage A candidate receipts have the wrong count or type")
        receipts = {item.role_id: item for item in files}
        if set(receipts) != set(self._role_by_id):
            raise PermissionError("Stage A did not freeze each of the 105 treatment candidate roles")
        maximum_rows = max(
            [
                sum(receipts[child.role_id].row_count for child in self._subinner[
                    inner.role_id.removesuffix("/inner")
                ]) + receipts[inner.role_id].row_count
                for roles in self._inner.values() for inner in roles
            ] + [
                sum(receipts[inner.role_id].row_count for inner in self._inner[outer_id])
                + receipts[outer_role.role_id].row_count
                for outer_id, outer_role in self._outer.items()
            ]
        )
        heldout_rows = sum(receipts[role.role_id].row_count for roles in self._inner.values() for role in roles)
        heldout_rows += sum(receipts[role.role_id].row_count for role in self._outer.values())
        if guard._stage_a_snapshot is None:
            raise PermissionError("Stage A did not freeze a current disk observation")
        frozen = require_frozen_admission()
        if self.role_graph.sha256.lower() != frozen.role_graph_sha256.lower():
            raise PermissionError("Stage B role schedule differs from the frozen admission graph")
        projection = StageBProjection(
            candidate_rows_n=sum(item.row_count for item in files),
            maximum_fit_rows_m=maximum_rows,
            prediction_rows_s=heldout_rows,
            candidate_file_bytes_b=sum(item.file_bytes for item in files),
            stage_a_disk_bytes_d_a=stage_a_projection_disk_bytes(guard._stage_a_snapshot, guard.limits),
            role_graph_sha256=self.role_graph.sha256.lower(),
            outer_role_ids=tuple(
                self.role_graph.outer_role_ids[outer_id] for outer_id in sorted(self._outer)
            ),
            inner_role_ids_by_outer=tuple(
                (outer_id, tuple(role.role_id for role in self._inner[outer_id]))
                for outer_id in sorted(self._outer)
            ),
            fit_training_roles_by_verifier=tuple(
                entry
                for outer_id in sorted(self._outer)
                for entry in (
                    *(
                        (
                            f"verifier/{outer_id}/{inner.role_id.split('/')[2]}",
                            tuple(
                                role.role_id
                                for role in self._subinner[inner.role_id.removesuffix("/inner")]
                            ),
                        )
                        for inner in self._inner[outer_id]
                    ),
                    (
                        f"verifier/{outer_id}/outer",
                        tuple(role.role_id for role in self._inner[outer_id]),
                    ),
                )
            ),
        )
        guard.require_stage_b_entry(projection)
        # The bound owner allows ordinary Stage B work only AFTER accepting
        # the durable expansion. Native expansion has already replayed and
        # verified all candidate artifacts before changing image capacity.
        with guard.activity("stage_b_candidate_receipt_preflight"):
            for item in files:
                ledger.require_frozen_candidate(item)
        selected: list[tuple[str, float]] = []
        fit_provenance: list[FitSummary] = []
        fold_metrics: list[AggregateMetrics] = []
        pooled_gt_count = 0
        outer_candidate_counts: list[tuple[str, int]] = []
        outer_candidate_covered_gt: list[tuple[str, int]] = []
        outer_reference_candidate_covered_gt: list[tuple[str, int]] = []
        outer_candidate_added_gt_commitments: list[tuple[str, tuple[str, ...]]] = []
        outer_candidate_lost_gt_commitments: list[tuple[str, tuple[str, ...]]] = []
        outer_control_matched_gt_commitments: list[tuple[str, tuple[str, ...]]] = []
        outer_matched_gt_added_commitments: list[tuple[str, tuple[str, ...]]] = []
        outer_matched_gt_lost_commitments: list[tuple[str, tuple[str, ...]]] = []
        fits = predicts = decoders = evaluations = pooled_aggregations = 0
        try:
            for outer_id in sorted(self._outer):
                outer_role = self._outer[outer_id]
                inner_receipts: list[PredictionFreezeReceipt] = []
                for inner in self._inner[outer_id]:
                    train = [
                        self._training_labels(self._materialize_role(
                            receipts[child.role_id], child, guard=guard, loader=loader,
                        ), guard=guard, ledger=ledger)
                        for child in self._subinner[inner.role_id.removesuffix("/inner")]
                    ]
                    verifier_role = f"verifier/{outer_id}/{inner.role_id.split('/')[2]}"
                    model, provenance = self._fit_model(
                        train, verifier_role_id=verifier_role,
                        fit_participants=inner.fit_participants, guard=guard, ledger=ledger,
                    )
                    fit_provenance.append(provenance)
                    fits += 1
                    del train
                    heldout = self._materialize_role(receipts[inner.role_id], inner, guard=guard, loader=loader)
                    predict_attempt, scores = guard.invoke_call(
                        "verifier_predict", inner.role_id,
                        lambda: self._score(model, heldout),
                    )
                    predicts += 1
                    del model
                    for threshold in _THRESHOLDS:
                        inner_receipts.append(self._freeze_decoded(
                            rows=heldout, scores=scores, threshold=threshold, phase="inner",
                            predict_attempt=predict_attempt, guard=guard, ledger=ledger,
                        ))
                        decoders += 1
                    del heldout, scores
                frozen_inner = FrozenPredictionReceipt(
                    outer_id=outer_id,
                    role_ids=tuple(role.role_id for role in self._inner[outer_id]),
                    thresholds=_THRESHOLDS,
                    predictions=tuple(inner_receipts),
                )
                inner_scope = self.role_graph.inner_evaluation_scope(outer_id, frozen_inner)
                selection: list[tuple[float, int, float]] = []
                for threshold in _THRESHOLDS:
                    predictions: list[PredictionRecord] = []
                    for receipt in inner_receipts:
                        if receipt.threshold == f"{threshold:.2f}":
                            predictions.extend(self._read_frozen_predictions(
                                receipt, phase="inner", outer_id=outer_id,
                                guard=guard, ledger=ledger,
                                participants=self._role_by_id[receipt.role_id].scored_participants,
                            ))
                    _, phase_result = guard.invoke_call(
                        "event_evaluator", f"threshold/{outer_id}/{threshold:.2f}",
                        lambda: self._execute_phase(
                            scope=inner_scope, operation="inner_evaluator",
                            predictions=tuple(predictions),
                            participant_ids=outer_role.fit_participants,
                            guard=guard, ledger=ledger,
                        ),
                    )
                    if type(phase_result) is not InnerSelectionPhaseResult:
                        raise PermissionError("inner evaluator returned an invalid phase result")
                    evaluations += 1
                    selection.append((phase_result.f1 if phase_result.f1 is not None else -1.0, -phase_result.fp, threshold))
                threshold = max(selection)[2]
                selected.append((outer_id, threshold))
                ledger.append("threshold_selected", {
                    "outer_id": outer_id,
                    "selection_tuples": [list(item) for item in selection],
                    "selected_threshold": threshold,
                })
                # Only now open the training six-field views for the four OOF
                # roles that become this outer verifier's fit rows.
                labeled_oof = [
                    self._training_labels(
                        self._materialize_role(receipts[inner.role_id], inner, guard=guard, loader=loader),
                        guard=guard, ledger=ledger,
                    )
                    for inner in self._inner[outer_id]
                ]
                outer_model, provenance = self._fit_model(
                    labeled_oof,
                    verifier_role_id=f"verifier/{outer_id}/outer",
                    fit_participants=outer_role.fit_participants,
                    guard=guard, ledger=ledger,
                )
                fit_provenance.append(provenance)
                fits += 1
                del labeled_oof
                heldout_outer = self._materialize_role(
                    receipts[outer_role.role_id], outer_role, guard=guard, loader=loader,
                )
                predict_attempt, scores = guard.invoke_call(
                    "verifier_predict", outer_role.role_id,
                    lambda: self._score(outer_model, heldout_outer),
                )
                predicts += 1
                del outer_model
                outer_receipt = self._freeze_decoded(
                    rows=heldout_outer, scores=scores, threshold=threshold, phase="outer",
                    predict_attempt=predict_attempt, guard=guard, ledger=ledger,
                )
                decoders += 1
                frozen_outer = FrozenPredictionReceipt(
                    outer_id=outer_id,
                    role_ids=(outer_role.role_id,),
                    thresholds=(threshold,),
                    predictions=(outer_receipt,),
                )
                outer_scope = self.role_graph.outer_evaluation_scope(outer_id, frozen_outer)
                outer_predictions = self._read_frozen_predictions(
                    outer_receipt, phase="outer", outer_id=outer_id,
                    guard=guard, ledger=ledger,
                    participants=outer_role.scored_participants,
                )
                with guard.activity(f"stage_b_control_reference:{outer_id}"):
                    with closing(reference_provider.open_role(
                        outer_role, phase=OUTER_CONTROL_CANDIDATES_PHASE,
                    )) as reference_rows:
                        outer_reference_candidates = tuple(
                            LabelCandidate(
                                f"reference-{ordinal:08d}", row.participant_id,
                                row.start_ms, row.end_ms,
                            )
                            for ordinal, row in enumerate(reference_rows)
                        )
                _, phase_result = guard.invoke_call(
                    "event_evaluator", f"outer/{outer_id}",
                    lambda: self._execute_phase(
                        scope=outer_scope, operation="outer_evaluator",
                        candidates=tuple(
                            LabelCandidate(candidate_id, candidate.participant_id, candidate.start_ms, candidate.end_ms)
                            for candidate, candidate_id in zip(
                                heldout_outer.candidates, heldout_outer.candidate_ids, strict=True,
                            )
                        ),
                        reference_candidates=outer_reference_candidates,
                        predictions=outer_predictions,
                        participant_ids=outer_role.scored_participants,
                        guard=guard, ledger=ledger,
                    ),
                )
                if (
                    type(phase_result) is not EvaluationPhaseResult
                    or type(phase_result.candidate_covered_gt) is not int
                ):
                    raise PermissionError("outer evaluator returned an invalid phase result")
                metric = phase_result.metric
                coverage = phase_result.candidate_covered_gt
                reference_coverage = phase_result.reference_candidate_covered_gt
                additions = phase_result.candidate_added_gt_commitments
                losses = phase_result.candidate_lost_gt_commitments
                if type(reference_coverage) is not int:
                    raise PermissionError("outer evaluator omitted reference matched-GT coverage")
                evaluations += 1
                fold_metrics.append(metric)
                outer_candidate_counts.append((outer_id, len(heldout_outer.candidates)))
                outer_candidate_covered_gt.append((outer_id, coverage))
                outer_reference_candidate_covered_gt.append((outer_id, reference_coverage))
                outer_candidate_added_gt_commitments.append((outer_id, additions))
                outer_candidate_lost_gt_commitments.append((outer_id, losses))
                outer_control_matched_gt_commitments.append((outer_id, phase_result.control_matched_gt_commitments))
                outer_matched_gt_added_commitments.append((outer_id, phase_result.matched_gt_added_commitments))
                outer_matched_gt_lost_commitments.append((outer_id, phase_result.matched_gt_lost_commitments))
                pooled_gt_count += phase_result.eligible_gt_count
                ledger.append("outer_evaluated", {
                    "outer_id": outer_id, "selected_threshold": threshold,
                    "candidate_count": len(heldout_outer.candidates),
                    "prediction_count": len(outer_predictions),
                    "gt_count": phase_result.eligible_gt_count, "candidate_covered_gt": coverage,
                    "reference_candidate_covered_gt": reference_coverage,
                    "candidate_added_gt": len(additions), "candidate_lost_gt": len(losses),
                    "control_matched_gt": len(phase_result.control_matched_gt_commitments),
                    "matched_gt_added": len(phase_result.matched_gt_added_commitments),
                    "matched_gt_lost": len(phase_result.matched_gt_lost_commitments),
                    "tp": metric.tp, "fp": metric.fp,
                    "fn": metric.fn, "f1": metric.f1,
                })
                # Keep only fold summaries for pooled aggregation.  Release
                # the full candidate matrix and decoded score vectors before
                # beginning the next outer fold's four inner fits.
                del (
                    heldout_outer, scores, outer_predictions, phase_result,
                    outer_receipt, frozen_outer, outer_scope,
                    outer_reference_candidates,
                )
            participant_ids = tuple(sorted({p for role in self._outer.values() for p in role.scored_participants}))
            if len(participant_ids) != 41 or pooled_gt_count != 234:
                raise ValueError("pooled denominator differs from the frozen 41/234 A2-004 protocol")
            _, pooled = guard.invoke_call(
                "pooled_reduction", "pooled/outer",
                lambda: self._pooled_from_disjoint_folds(fold_metrics, participant_ids),
            )
            pooled_aggregations += 1
            quality = evaluate_quality(fold_metrics, outer_fold_f1=[item.f1 for item in fold_metrics], pooled=pooled)
            matched_gt_commitments = tuple(sorted({
                matched_truth_commitment
                for participant in pooled.participants
                for _, matched_truth_commitment, _ in participant.matched_pairs
            }))
            control_matched_gt_commitments = tuple(sorted({
                item for _, items in outer_control_matched_gt_commitments for item in items
            }))
            matched_gt_added_commitments = tuple(sorted(set(matched_gt_commitments) - set(control_matched_gt_commitments)))
            matched_gt_lost_commitments = tuple(sorted(set(control_matched_gt_commitments) - set(matched_gt_commitments)))
            if (len(control_matched_gt_commitments) != 154
                    or sum(len(items) for _, items in outer_control_matched_gt_commitments) != 154
                    or matched_gt_added_commitments != tuple(sorted(item for _, items in outer_matched_gt_added_commitments for item in items))
                    or matched_gt_lost_commitments != tuple(sorted(item for _, items in outer_matched_gt_lost_commitments for item in items))):
                raise PermissionError("five-fold final match comparison differs from the saved A2-004 TP=154 control")
            if (fits, predicts, decoders, evaluations, pooled_aggregations) != (25, 25, 65, 20, 1):
                raise RuntimeError("Stage B call counts differ from the approved 25/25/65/21 protocol")
            result = StageBResult(
                status=StudyStatus.COMPLETE,
                selected_thresholds=tuple(selected),
                pooled_f1=pooled.f1,
                pooled_gt_count=pooled_gt_count,
                pooled_metrics=pooled,
                fold_metrics=tuple(fold_metrics),
                quality=quality,
                fit_provenance=tuple(fit_provenance),
                matched_gt_commitments=matched_gt_commitments,
                control_matched_gt_commitments=control_matched_gt_commitments,
                matched_gt_added_commitments=matched_gt_added_commitments,
                matched_gt_lost_commitments=matched_gt_lost_commitments,
                outer_candidate_counts=tuple(outer_candidate_counts),
                outer_candidate_covered_gt=tuple(outer_candidate_covered_gt),
                verifier_fit_attempts=fits,
                verifier_prediction_batches=predicts,
                decoder_calls=decoders,
                evaluator_calls=evaluations,
                pooled_aggregation_calls=pooled_aggregations,
                pooled_aggregation_completed=True,
                pooled_gt_reads=0,
                outer_reference_candidate_covered_gt=tuple(outer_reference_candidate_covered_gt),
                outer_candidate_added_gt_commitments=tuple(outer_candidate_added_gt_commitments),
                outer_candidate_lost_gt_commitments=tuple(outer_candidate_lost_gt_commitments),
                outer_control_matched_gt_commitments=tuple(outer_control_matched_gt_commitments),
                outer_matched_gt_added_commitments=tuple(outer_matched_gt_added_commitments),
                outer_matched_gt_lost_commitments=tuple(outer_matched_gt_lost_commitments),
            )
            return result
        finally:
            fold_metrics.clear()
