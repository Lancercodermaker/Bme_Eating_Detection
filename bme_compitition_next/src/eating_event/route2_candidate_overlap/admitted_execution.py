"""One-shot, same-process handoff from verified admission to the fixed A+B runner.

There is no CLI, plugin factory, subprocess handoff or experiment authorization
here. The privileged controller must assemble the complete reviewed OS/data
backends before calling this module. Launcher installation, resource/GT
enforcement and post-exit acceptance remain separate requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import execution
from .admission_bootstrap import (
    DEFAULT_SUPERVISOR_CONFIG, SupervisorBootstrapProof,
    bootstrap_frozen_admission, claim_bootstrap_for_ab,
)
from .budget import AppendOnlyLedger, BudgetGuard, BudgetLimits, CALL_CEILINGS, ZERO_HASH
from .contracts import ExperimentApproval, RoleSpec
from .execution import ABReadiness, RoleCandidateReconstructor, StageAResult
from .references import ApprovedReferenceStore
from .stage_b import StageBAdapter, StageBResult
from .linux_supervisor import Route2Supervisor, SupervisorState


@dataclass(frozen=True, slots=True)
class ABExecutionBindings:
    approval: ExperimentApproval
    readiness: ABReadiness
    roles: tuple[RoleSpec, ...]
    reference_provider: ApprovedReferenceStore
    candidate_builder: RoleCandidateReconstructor
    stage_b_adapter: StageBAdapter
    ledger: AppendOnlyLedger
    guard: BudgetGuard
    supervisor: Route2Supervisor


def _require_fresh(guard: BudgetGuard, ledger: AppendOnlyLedger) -> None:
    """Reject every stateful field that could carry prior budget/phase work."""
    guard_false = (
        "_start_entered", "_started", "_activity_open", "_finished", "_stage_b_admitted",
        "_volume_prepare_entered",
    )
    guard_none = (
        "_stage_a_finished_ns", "_rss_ceiling_bytes", "_stage_a_snapshot",
        "_volume_identity_snapshot", "_stage_a_event_receipt",
        "_stage_b_entry_event_receipt", "_stage_b_expansion_event_receipt",
        "_stage_b_completion_event_receipt", "_stage_b_result_evidence", "_boundary_failure",
        "_startup_receipt", "_startup_snapshot", "_lifecycle_supervisor",
        "_startup_failure", "_startup_close_failure",
    )
    ledger_false = (
        "_poisoned", "_terminal", "_stage_b_entry_passed", "_stage_b_volume_expanded",
        "_stage_a_finished", "_stage_b_complete",
        "_create_entered",
    )
    ledger_none = (
        "_fd", "_owner_thread_id", "_stage_b_entry_event_hash", "_active_gt_release",
        "_terminal_sha256", "_closed_at_monotonic_ns", "_invocation_id",
        "_invocation_started_monotonic_ns",
        "_created_monotonic_ns",
        "_lock_identity", "_lock_sha256",
    )
    ledger_sets = (
        "_reference_roles", "_reference_passed", "_treatment_roles", "_different_treatment_roles",
    )
    ledger_dicts = ("_treatment_finished", "_call_state", "_frozen_predictions")
    counts = ledger._call_counts
    if (
        any(getattr(guard, name) is not False for name in guard_false)
        or guard._startup_phase != "approval"
        or any(getattr(guard, name) is not None for name in guard_none)
        or type(guard._fit_wall_ns) is not int or guard._fit_wall_ns != 0
        or any(getattr(ledger, name) is not False for name in ledger_false)
        or any(getattr(ledger, name) is not None for name in ledger_none)
        or type(ledger._seq) is not int or ledger._seq != 0 or ledger._tail != ZERO_HASH
        or any(type(getattr(ledger, name)) is not set or getattr(ledger, name) for name in ledger_sets)
        or any(type(getattr(ledger, name)) is not dict or getattr(ledger, name) for name in ledger_dicts)
        or type(counts) is not dict or set(counts) != set(CALL_CEILINGS)
        or any(type(count) is not int or count != 0 for count in counts.values())
    ):
        raise PermissionError("bootstrap handoff requires a fresh unstarted guard and ledger")


def run_bootstrapped_ab(
    proof: SupervisorBootstrapProof, bindings: ABExecutionBindings,
) -> StageAResult | StageBResult:
    """Enter exactly ``execution.run_ab`` once; return its internal result.

    This does not issue post-terminal acceptance. The external observer must
    still prove exit, teardown, durable final receipt and both wall clocks.
    Every genuine handoff attempt is consumed before checking the bindings.
    """
    frozen = claim_bootstrap_for_ab(proof)
    if type(bindings) is not ABExecutionBindings:
        raise PermissionError("A+B handoff requires the fixed execution bindings")
    fixed = (
        (bindings.approval, ExperimentApproval), (bindings.readiness, ABReadiness),
        (bindings.reference_provider, ApprovedReferenceStore),
        (bindings.candidate_builder, RoleCandidateReconstructor),
        (bindings.stage_b_adapter, StageBAdapter),
        (bindings.ledger, AppendOnlyLedger), (bindings.guard, BudgetGuard),
        (bindings.supervisor, Route2Supervisor),
    )
    if any(type(value) is not expected for value, expected in fixed) or type(bindings.roles) is not tuple:
        raise PermissionError("A+B handoff requires the fixed reviewed adapter types")
    approval, ledger, guard = bindings.approval, bindings.ledger, bindings.guard
    approval.require_full_ab()
    if (
        guard.ledger is not ledger or guard.study_root != ledger.study_root
        or ledger.study_root.as_posix() != frozen.study_root_path
        or ledger.path.as_posix() != frozen.budget_ledger_path
        or ledger.lock_path.as_posix() != frozen.lock_path
        or type(guard.limits) is not BudgetLimits
        or guard.limits.digest() != frozen.budget_policy_sha256.lower()
        or guard.approved_controller_sha256 != frozen.resource_controller_sha256.lower()
        or guard.approved_write_volumes != frozen.approved_write_volumes
    ):
        raise PermissionError("bootstrap handoff ledger, paths or budget differ from frozen admission")
    _require_fresh(guard, ledger)
    supervisor = bindings.supervisor
    if supervisor.approval is not approval or supervisor.state is not SupervisorState.NEW:
        raise PermissionError("bootstrap handoff requires the same fresh lifecycle approval and owner")
    supervisor.bind_budget_guard(guard)
    # run_ab performs complete readiness, metadata and Stage B preflight before
    # its Stage A code calls guard.start. No second interpreter loses admission.
    return execution.run_ab(
        approval=approval, readiness=bindings.readiness, roles=bindings.roles,
        reference_provider=bindings.reference_provider,
        candidate_builder=bindings.candidate_builder,
        stage_b_adapter=bindings.stage_b_adapter, ledger=ledger, guard=guard,
    )


def bootstrap_and_run_ab(
    bindings: ABExecutionBindings, *, config_path: str | Path = DEFAULT_SUPERVISOR_CONFIG,
) -> StageAResult | StageBResult:
    """Verify protected external admission and continue without exec or fork."""
    return run_bootstrapped_ab(bootstrap_frozen_admission(config_path), bindings)
