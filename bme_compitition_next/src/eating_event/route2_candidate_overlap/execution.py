"""A+B orchestration gates; data/backend adapters are injected and reviewed."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .budget import AppendOnlyLedger, BudgetGuard
from .candidates import (
    Candidate,
    CandidateFileReceipt,
    ReferenceInterval,
    build_candidates,
    compare_reference_and_fingerprint,
    sorted_stream_fingerprint,
)
from .contracts import (
    ExperimentApproval,
    RoleInputRegistration,
    RoleSpec,
    StudyStatus,
    TREATMENT_CANDIDATE_FIELDS,
    require_frozen_admission,
    stage_a_registry_sha256,
)
from .inputs import LazyRoleLoader
from .references import ApprovedReferenceStore

if TYPE_CHECKING:
    from .stage_b import StageBAdapter, StageBResult


class TerminalFinalizationFailure(RuntimeError):
    """One failed stage and its failed, once-only terminal attempt.

    Reserve the error and secondary slot before the stage starts. A failure to
    save a terminal remains INCOMPLETE_RESOURCE; it cannot hide either raw
    exception or cause another terminal attempt.
    """

    def __init__(self) -> None:
        super().__init__("stage failed and terminal finalization also failed")
        self.primary_error = None
        self.terminal_error = None
        self.secondary_errors = [None]
        self.requested_status = None
        self.status = StudyStatus.INCOMPLETE_RESOURCE


class RoleCandidateReconstructor:
    """Reconstructs candidates inside one lazy role lease and no GT scope."""

    def __init__(
        self,
        loader: LazyRoleLoader,
        registrations: tuple[RoleInputRegistration, ...],
    ):
        if type(loader) is not LazyRoleLoader:
            raise PermissionError("candidate reconstruction requires the exact reviewed role loader")
        if len(registrations) != 105:
            raise ValueError("candidate reconstructor requires all 105 role registrations")
        self._registrations = {item.role.role_id: item for item in registrations}
        if len(self._registrations) != 105:
            raise ValueError("candidate input registration repeats a role")
        if self._registrations != loader._registrations:
            raise PermissionError("candidate builder and lazy loader have different exact registrations")
        if tuple(item.role for item in registrations) != loader.role_specs:
            raise PermissionError("candidate builder and lazy loader have different role order")
        self._loader = loader

    @property
    def loader(self) -> LazyRoleLoader:
        return self._loader

    def __call__(self, role: RoleSpec, rule: str) -> Iterator[Candidate]:
        registration = self._registrations.get(role.role_id)
        if registration is None or registration.role != role:
            raise PermissionError("candidate request differs from the frozen role registration")
        if rule not in {"reference_300s", "strict_overlap"}:
            raise ValueError("candidate rule is outside the frozen A+B design")
        with self._loader.open_role(role.role_id) as loaded:
            yield from build_candidates(
                loaded.support_windows(registration),
                rule=rule,  # type: ignore[arg-type]
            )


def _scoped_reference_rows(
    rows: Iterator[ReferenceInterval],
    role: RoleSpec,
) -> Iterator[ReferenceInterval]:
    allowed = set(role.scored_participants)
    try:
        for row in rows:
            if row.role_id != role.role_id or row.participant_id not in allowed:
                raise PermissionError("reference row escapes its registered role/participant scope")
            yield row
    finally:
        close = getattr(rows, "close", None)
        if close is not None:
            close()


def _scoped_candidate_rows(
    rows: Iterator[Candidate],
    role: RoleSpec,
) -> Iterator[Candidate]:
    allowed = set(role.scored_participants)
    try:
        for row in rows:
            if row.role_id != role.role_id or row.participant_id not in allowed:
                raise PermissionError("candidate row escapes its registered role/participant scope")
            yield row
    finally:
        close = getattr(rows, "close", None)
        if close is not None:
            close()


def _freeze_treatment_role(
    rows: Iterator[Candidate], role: RoleSpec, study_root: Path
) -> CandidateFileReceipt:
    """Persist a treatment stream once, while its single reconstruction lease is open."""

    output_dir = study_root / "treatment-candidates"
    if not output_dir.exists():
        output_dir.mkdir()
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise PermissionError("treatment output is not an ordinary study directory")
    role_stem = hashlib.sha256(role.role_id.encode("utf-8")).hexdigest()[:20]
    final_path = output_dir / f"{role_stem}.jsonl"
    temporary_path = output_dir / f"{role_stem}.jsonl.tmp"
    if final_path.exists() or temporary_path.exists():
        raise FileExistsError("treatment role output is already occupied")
    content_sha = hashlib.sha256()
    file_bytes = 0
    group_key: tuple[str, str, str, str, str] | None = None
    component_ordinal = 0
    seen_groups: set[tuple[str, str, str, str, str]] = set()
    seen_candidate_ids: set[str] = set()
    with temporary_path.open("xb") as output:
        def persisted_rows() -> Iterator[Candidate]:
            nonlocal file_bytes, group_key, component_ordinal
            for candidate in rows:
                if candidate.role_id != role.role_id:
                    raise PermissionError("treatment candidate differs from its output role")
                current_group = (
                    candidate.role_id,
                    candidate.participant_id,
                    candidate.record_id,
                    candidate.session_id,
                    candidate.component_id,
                )
                if current_group != group_key:
                    if current_group in seen_groups:
                        raise ValueError("treatment component reappears after another group")
                    seen_groups.add(current_group)
                    group_key = current_group
                    component_ordinal = 0
                candidate_id = f"{candidate.component_id}|candidate-{component_ordinal}"
                if candidate_id in seen_candidate_ids:
                    raise ValueError("treatment candidate ID repeats within a role")
                seen_candidate_ids.add(candidate_id)
                payload = {
                    "role_id": candidate.role_id,
                    "candidate_id": candidate_id,
                    "participant_id": candidate.participant_id,
                    "record_id": candidate.record_id,
                    "session_id": candidate.session_id,
                    "component_id": candidate.component_id,
                    "start_ms": candidate.start_ms,
                    "end_ms": candidate.end_ms,
                    "support_indices": candidate.support_indices,
                    "source_16d": candidate.source_16d,
                    "boundary_kind": candidate.boundary_kind,
                    "source_segment_id": candidate.source_segment_id,
                }
                if tuple(payload) != TREATMENT_CANDIDATE_FIELDS:
                    raise RuntimeError("treatment output schema differs from its frozen allowlist")
                encoded = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8") + b"\n"
                if len(encoded) > 1024 * 1024:
                    raise RuntimeError("treatment row exceeds the frozen Stage B line bound")
                if output.write(encoded) != len(encoded):
                    raise OSError("partial treatment candidate write")
                content_sha.update(encoded)
                file_bytes += len(encoded)
                component_ordinal += 1
                yield candidate

        row_count, interval_fingerprint = sorted_stream_fingerprint(persisted_rows())
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary_path, final_path)
    receipt = CandidateFileReceipt(
        role_id=role.role_id,
        path=str(final_path),
        sha256=content_sha.hexdigest(),
        row_count=row_count,
        file_bytes=file_bytes,
        interval_fingerprint=interval_fingerprint,
    )
    return receipt


@dataclass(frozen=True, slots=True)
class StageAResult:
    status: StudyStatus | None
    reference_roles: int
    treatment_roles: int
    treatment_files: tuple[CandidateFileReceipt, ...] = ()
    fit_attempts: int = 0
    prediction_batches: int = 0
    decoder_calls: int = 0
    evaluator_calls: int = 0


def _run_stage_a(
    *,
    approval: ExperimentApproval,
    readiness: "ABReadiness",
    roles: tuple[RoleSpec, ...],
    reference_provider: ApprovedReferenceStore,
    candidate_builder: RoleCandidateReconstructor,
    ledger: AppendOnlyLedger,
    guard: BudgetGuard,
) -> StageAResult:
    """Private A+B step: keep the same ledger open when treatment changes."""

    approval.require_full_ab()
    readiness.require_complete()
    if type(reference_provider) is not ApprovedReferenceStore:
        raise PermissionError("Stage A accepts only the approved sanitized reference store")
    if type(candidate_builder) is not RoleCandidateReconstructor:
        raise PermissionError("Stage A accepts only the registered lazy role reconstructor")
    if len(roles) != 105 or len({role.role_id for role in roles}) != 105:
        raise ValueError("Stage A requires the frozen 105-role registry")
    if (
        candidate_builder.loader is not reference_provider.identity_loader
        or roles != reference_provider.roles
        or roles != candidate_builder.loader.role_specs
    ):
        raise PermissionError("Stage A must use one loader and one exact 105-role graph")
    candidate_builder.loader.require_pinned_registration()
    reference_provider.require_pinned_registration()
    frozen = require_frozen_admission()
    combined_registry = stage_a_registry_sha256(
        candidate_builder.loader.role_graph_sha256,
        candidate_builder.loader.registry_sha256,
        reference_provider.registry_sha256,
    )
    if (
        combined_registry != frozen.combined_input_registry_sha256.lower()
        or approval.input_registry_sha256.lower() != combined_registry
        or readiness.role_input_registry_sha256.lower() != candidate_builder.loader.registry_sha256
        or readiness.reference_registry_sha256.lower() != reference_provider.registry_sha256
        or readiness.equivalence.role_graph_sha256.lower() != candidate_builder.loader.role_graph_sha256
        or guard.limits.digest() != approval.budget_policy_sha256.lower()
        or guard.ledger is not ledger
        or guard.study_root != ledger.study_root
        or str(guard.study_root) != approval.study_root_path
        or str(ledger.path) != approval.budget_ledger_path
        or str(ledger.lock_path) != approval.lock_path
        or candidate_builder.loader.path_map is not reference_provider.path_map
        or candidate_builder.loader.path_map.manifest_sha256 != frozen.path_map_sha256.lower()
        or approval.path_map_sha256.lower() != frozen.path_map_sha256.lower()
        or readiness.path_map_sha256.lower() != frozen.path_map_sha256.lower()
    ):
        raise PermissionError("approval, readiness, source registries and budget do not match")
    terminal_failure = TerminalFinalizationFailure()
    guard.start(approval)
    terminal_attempted = False
    try:
        from .linux_production_controller import LinuxProductionController
        if type(guard.enforcer) is LinuxProductionController:
            from .linux_gt_history import install_original_gt_broker
            original = guard.enforcer._state()
            original.ports.require_original_startup_handshake(guard.enforcer)
            install_original_gt_broker(guard, reviewed_manifest_bytes=candidate_builder.loader.path_map._manifest_bytes)
        reference_fingerprints: dict[str, tuple[int, str]] = {}
        reference_failure: tuple[int, str] | None = None
        with guard.activity("stage_a_reference", stage_a=True):
            for ordinal, role in enumerate(roles, 1):
                ledger.reserve_candidate_reconstruction("reference", role.role_id)
                # Close the identity lease before opening the scored role lease.
                # At most one role's sanitized reference rows are held.
                with closing(_scoped_reference_rows(reference_provider.open_role(role), role)) as reference_rows:
                    expected = tuple(reference_rows)
                with closing(_scoped_candidate_rows(candidate_builder(role, "reference_300s"), role)) as actual:
                    same, fingerprint = compare_reference_and_fingerprint(expected, actual)
                if not same:
                    reference_failure = (ordinal, role.role_id)
                    break
                reference_fingerprints[role.role_id] = fingerprint
                ledger.mark_reference_passed(
                    role.role_id,
                    candidate_count=fingerprint[0],
                    fingerprint=fingerprint[1],
                )

        if reference_failure is not None:
            ordinal, failed_role_id = reference_failure
            terminal_attempted = True
            actual_status = guard.finalize(
                StudyStatus.REFERENCE_NOT_REPRODUCED.value,
                evidence={"role_id": failed_role_id, "reference_roles": ordinal, "treatment_roles": 0},
            )
            if actual_status != StudyStatus.REFERENCE_NOT_REPRODUCED.value:
                raise RuntimeError("reference terminal was replaced by a resource terminal")
            return StageAResult(StudyStatus.REFERENCE_NOT_REPRODUCED, ordinal, 0)

        changed = False
        treatment_count = 0
        treatment_files: list[CandidateFileReceipt] = []
        with guard.activity("stage_a_treatment", stage_a=True):
            for role in roles:
                ledger.reserve_candidate_reconstruction("treatment", role.role_id)
                treatment_count += 1
                with closing(_scoped_candidate_rows(candidate_builder(role, "strict_overlap"), role)) as treatment:
                    receipt = _freeze_treatment_role(treatment, role, guard.study_root)
                treatment_files.append(receipt)
                same = (receipt.row_count, receipt.interval_fingerprint) == reference_fingerprints[role.role_id]
                changed = changed or not same
                ledger.mark_treatment_finished(receipt, interval_set_same=same)
        guard.finish_stage_a()
        if not changed:
            terminal_attempted = True
            actual_status = guard.finalize(
                StudyStatus.MECHANISM_NOT_SUPPORTED.value,
                evidence={
                    "reference_roles": 105,
                    "treatment_roles": treatment_count,
                    "candidate_model_fits": 0,
                    "candidate_model_predictions": 0,
                },
            )
            if actual_status != StudyStatus.MECHANISM_NOT_SUPPORTED.value:
                raise RuntimeError("mechanism terminal was replaced by a resource terminal")
            return StageAResult(
                StudyStatus.MECHANISM_NOT_SUPPORTED, 105, treatment_count, tuple(treatment_files)
            )
        return StageAResult(None, 105, treatment_count, tuple(treatment_files))
    except BaseException as exc:
        # If terminal persistence itself fails, the occupied namespace remains
        # an unrecoverable incomplete study; never retry with a new ledger.
        status = (
            StudyStatus.INPUT_NOT_AUTHORIZED
            if isinstance(exc, PermissionError)
            else StudyStatus.INVALID
            if isinstance(exc, ValueError)
            else StudyStatus.INCOMPLETE_RESOURCE
        )
        if not terminal_attempted:
            try:
                actual_status = guard.finalize(
                    status.value, evidence={"exception_type": type(exc).__name__}
                )
                if actual_status != status.value:
                    raise RuntimeError("Stage A exception terminal was replaced by resource failure")
            except BaseException as terminal_error:
                terminal_failure.primary_error = exc
                terminal_failure.terminal_error = terminal_error
                terminal_failure.secondary_errors[0] = terminal_error
                terminal_failure.requested_status = status
                raise terminal_failure from exc
        raise


@dataclass(frozen=True, slots=True)
class StageBEquivalenceReceipt:
    """Exact frozen identity for every non-candidate protocol component."""

    a1_label_code_sha256: str
    a2_audit_code_sha256: str
    a2_role_digests_sha256: str
    interval_iou_code_sha256: str
    feature_16d_code_sha256: str
    feature_10d_code_sha256: str
    verifier_config_sha256: str
    role_graph_sha256: str
    threshold_selection_sha256: str
    decoder_sha256: str
    matcher_evaluator_sha256: str
    independent_review_id: str

    def require_complete(self) -> None:
        hashes = (
            self.a1_label_code_sha256,
            self.a2_audit_code_sha256,
            self.a2_role_digests_sha256,
            self.interval_iou_code_sha256,
            self.feature_16d_code_sha256,
            self.feature_10d_code_sha256,
            self.verifier_config_sha256,
            self.role_graph_sha256,
            self.threshold_selection_sha256,
            self.decoder_sha256,
            self.matcher_evaluator_sha256,
        )
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower())
            for value in hashes
        ) or not self.independent_review_id:
            raise PermissionError("A2-004 protocol equivalence receipt is incomplete")


@dataclass(frozen=True, slots=True)
class ABReadiness:
    """One preflight result spanning every Stage A and Stage B admission gate."""

    equivalence: StageBEquivalenceReceipt
    role_input_registry_sha256: str
    reference_registry_sha256: str
    gt_view_registry_sha256: str
    gt_role_graph_projection_sha256: str
    path_map_sha256: str
    phase_runner_sha256: str
    phase_worker_sha256: str
    stage_b_adapter_sha256: str
    source_registration_sha256: str
    projection_manifest_sha256: str
    admission_metadata_projection_path: str
    admission_metadata_projection_sha256: str
    linux_lock_sha256: str
    linux_identity_sha256: str
    runtime_attestation_sha256: str
    source_snapshot_sha256: str
    runtime_snapshot_sha256: str
    runtime_metadata_review_id: str
    source_snapshot_review_id: str
    runtime_snapshot_review_id: str
    reference_projection_review_id: str
    gt_projection_review_id: str
    lazy_loader_review_id: str
    resource_enforcer_review_id: str
    stage_b_adapter_review_id: str
    path_map_review_id: str
    phase_runner_review_id: str
    phase_worker_review_id: str
    all_inputs_explicitly_approved: bool
    stage_b_resources_preapproved: bool

    def require_complete(self) -> None:
        frozen = require_frozen_admission()
        self.equivalence.require_complete()
        digests = (
            self.role_input_registry_sha256,
            self.reference_registry_sha256,
            self.gt_view_registry_sha256,
            self.gt_role_graph_projection_sha256,
            self.path_map_sha256,
            self.phase_runner_sha256,
            self.phase_worker_sha256,
            self.stage_b_adapter_sha256,
            self.source_registration_sha256,
            self.projection_manifest_sha256,
            self.admission_metadata_projection_sha256,
            self.linux_lock_sha256,
            self.linux_identity_sha256,
            self.runtime_attestation_sha256,
            self.source_snapshot_sha256,
            self.runtime_snapshot_sha256,
        )
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower())
            for value in digests
        ):
            raise PermissionError("A+B input registry hash is missing or malformed")
        review_ids = (
            self.reference_projection_review_id,
            self.gt_projection_review_id,
            self.lazy_loader_review_id,
            self.resource_enforcer_review_id,
            self.stage_b_adapter_review_id,
            self.path_map_review_id,
            self.phase_runner_review_id,
            self.phase_worker_review_id,
            self.runtime_metadata_review_id,
            self.source_snapshot_review_id,
            self.runtime_snapshot_review_id,
        )
        if any(not value for value in review_ids):
            raise PermissionError("the complete A+B independent review set is incomplete")
        if not self.all_inputs_explicitly_approved or not self.stage_b_resources_preapproved:
            raise PermissionError("all inputs and both stage budgets require prior approval")
        if (
            self.gt_view_registry_sha256.lower() != frozen.gt_view_registry_sha256.lower()
            or self.gt_role_graph_projection_sha256.lower()
            != frozen.gt_role_graph_projection_sha256.lower()
            or self.path_map_sha256.lower() != frozen.path_map_sha256.lower()
            or self.phase_runner_sha256.lower() != frozen.phase_runner_sha256.lower()
            or self.phase_worker_sha256.lower() != frozen.phase_worker_sha256.lower()
            or self.stage_b_adapter_sha256.lower() != frozen.stage_b_adapter_sha256.lower()
            or self.source_registration_sha256.lower() != frozen.source_registration_sha256.lower()
            or self.projection_manifest_sha256.lower() != frozen.projection_manifest_sha256.lower()
            or self.admission_metadata_projection_path != frozen.admission_metadata_projection_path
            or self.admission_metadata_projection_sha256.lower()
            != frozen.admission_metadata_projection_sha256.lower()
            or self.linux_lock_sha256.lower() != frozen.linux_lock_sha256.lower()
            or self.linux_identity_sha256.lower() != frozen.linux_identity_sha256.lower()
            or self.runtime_attestation_sha256.lower() != frozen.runtime_attestation_sha256.lower()
            or self.source_snapshot_sha256.lower() != frozen.source_snapshot_sha256.lower()
            or self.runtime_snapshot_sha256.lower() != frozen.runtime_snapshot_sha256.lower()
            or self.equivalence.a2_role_digests_sha256.lower()
            != frozen.a2_004_role_digests_sha256.lower()
            or self.equivalence.verifier_config_sha256.lower()
            != frozen.a2_004_config_sha256.lower()
            or self.equivalence.role_graph_sha256.lower() != frozen.role_graph_sha256.lower()
        ):
            raise PermissionError("A+B metadata, GT views or role graph differ from reviewed pins")
        encoded = json.dumps(
            asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != frozen.readiness_sha256.lower():
            raise PermissionError("A+B readiness differs from the independently reviewed receipt")


def run_ab(
    *,
    approval: ExperimentApproval,
    readiness: ABReadiness,
    roles: tuple[RoleSpec, ...],
    reference_provider: ApprovedReferenceStore,
    candidate_builder: RoleCandidateReconstructor,
    stage_b_adapter: StageBAdapter,
    ledger: AppendOnlyLedger,
    guard: BudgetGuard,
) -> StageAResult | StageBResult:
    """One approved invocation: review all A+B gates, then run both stages."""

    from .stage_b import StageBAdapter, VerifierDataInsufficient

    if (
        type(approval) is not ExperimentApproval
        or type(readiness) is not ABReadiness
        or type(reference_provider) is not ApprovedReferenceStore
        or type(candidate_builder) is not RoleCandidateReconstructor
        or type(ledger) is not AppendOnlyLedger
        or type(guard) is not BudgetGuard
    ):
        raise PermissionError("A+B requires the fixed reviewed approval and adapter types")
    if type(stage_b_adapter) is not StageBAdapter:
        raise PermissionError("A+B requires the fixed, independently reviewed Stage B adapter")
    terminal_failure = TerminalFinalizationFailure()
    approval.require_full_ab()
    readiness.require_complete()
    # The independent review attestation and its metadata-only inputs must be
    # visible through controller-sealed read-only binds before any Stage A or B
    # adapter can inspect source data. No mixed G1/A2 or physical GT file is
    # opened here.
    from .runtime_identity import verify_runtime_metadata

    verify_runtime_metadata(require_frozen_admission(), candidate_builder.loader.path_map)
    stage_b_adapter.preflight(
        approval=approval,
        readiness=readiness,
        guard=guard,
        ledger=ledger,
        loader=candidate_builder.loader,
    )
    stage_a = _run_stage_a(
        approval=approval,
        readiness=readiness,
        roles=roles,
        reference_provider=reference_provider,
        candidate_builder=candidate_builder,
        ledger=ledger,
        guard=guard,
    )
    if stage_a.status is not None:
        return stage_a

    terminal_attempted = False
    try:
        result = stage_b_adapter.run(
            stage_a=stage_a,
            reference_provider=reference_provider,
            guard=guard,
            ledger=ledger,
            loader=candidate_builder.loader,
            approval=approval,
            readiness=readiness,
        )
        if result.status is not StudyStatus.COMPLETE:
            raise ValueError("Stage B returned a nonterminal success status")
        guard.finish_stage_b(result)
        terminal_attempted = True
        actual_status = guard.finalize(
            StudyStatus.COMPLETE.value,
            evidence={"stage_b_result": asdict(result)},
        )
        if actual_status != StudyStatus.COMPLETE.value:
            raise RuntimeError("COMPLETE terminal was replaced by resource failure")
        return result
    except BaseException as exc:
        status = (
            StudyStatus.VERIFIER_DATA_INSUFFICIENT
            if isinstance(exc, VerifierDataInsufficient)
            else StudyStatus.INPUT_NOT_AUTHORIZED
            if isinstance(exc, PermissionError)
            else StudyStatus.INVALID
            if isinstance(exc, ValueError)
            else StudyStatus.INCOMPLETE_RESOURCE
        )
        if not terminal_attempted:
            try:
                actual_status = guard.finalize(
                    status.value, evidence={"exception_type": type(exc).__name__}
                )
                if actual_status != status.value:
                    raise RuntimeError("Stage B exception terminal was replaced by resource failure")
            except BaseException as terminal_error:
                terminal_failure.primary_error = exc
                terminal_failure.terminal_error = terminal_error
                terminal_failure.secondary_errors[0] = terminal_error
                terminal_failure.requested_status = status
                raise terminal_failure from exc
        raise


def refuse_stage_b_until_equivalence() -> None:
    raise PermissionError(
        "Stage B adapter is not executable until A2-004 identities and independent "
        "protocol-equivalence review are registered"
    )
