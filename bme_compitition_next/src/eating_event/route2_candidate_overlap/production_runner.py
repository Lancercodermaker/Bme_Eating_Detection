"""Fixed same-interpreter pre-import -> bootstrap -> native owners -> A+B.

There is no plugin/factory registry, timestamp CLI, or approval/review issuer.
Only existing concrete reviewed adapters can enter this orchestration. The
installed metadata is decoded only through the fixed protected loader. The
fixed native phase executor binds source/owner identity only; concrete native
data deployment and authenticated outer QPC transport remain missing;
their fixed production gates refuse explicitly. An internal
A+B result is not post-exit acceptance.
"""

from __future__ import annotations

from dataclasses import fields
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import threading
import time

from . import admission_bootstrap, contracts
from .admission_bootstrap import (
    DEFAULT_SUPERVISOR_CONFIG, SupervisorBootstrapProof, bootstrap_frozen_admission,
    claim_bootstrap_for_ab,
)
from .admitted_execution import ABExecutionBindings, run_bootstrapped_ab
from .budget import (
    AppendOnlyLedger, BudgetGuard, BudgetLimits, STAGE_A_CAPACITY_UPPER_BOUND_V2,
    require_fixed_native_budget,
)
from .contracts import CacheFileRegistration, ExperimentApproval, RegisteredFile, RoleInputRegistration, RoleSpec
from .control_matches import HistoricalControlMatchStore
from .execution import ABReadiness, RoleCandidateReconstructor, StageAResult, StageBEquivalenceReceipt
from .gt_provider import ScopedTruthProvider
from .inputs import LazyRoleLoader
from .linux_production_controller import (
    LinuxProductionController, LinuxProductionOSPorts, _ASSEMBLIES,
    assemble_production_owners,
)
from .linux_start_clock import LinuxStartClockProof, require_preimport_start_clock
from .linux_supervisor import Route2Supervisor, SupervisorState
from .path_map import ExactPathMap
from .production_metadata import (
    ProductionABMetadata, load_installed_metadata, require_installed_metadata, verify_metadata_pins,
)
from .references import ApprovedReferenceStore
from .stage_b import StageBAdapter, StageBResult


_ASSEMBLY_ENTERED = False
_RUN_ENTERED = False


def _require_bootstrap_start(proof: SupervisorBootstrapProof) -> LinuxStartClockProof:
    with admission_bootstrap._INSTALL_LOCK:
        issued = admission_bootstrap._ISSUED_BOOTSTRAP
        if (type(proof) is not SupervisorBootstrapProof or issued is None or issued.proof is not proof
                or issued.consumed or issued.pid != os.getpid()
                or issued.thread is not threading.current_thread()
                or contracts.FROZEN_ADMISSION is not proof.frozen_admission
                or type(proof.frozen_admission) is not contracts.FrozenAdmission
                or type(proof.start_clock) is not LinuxStartClockProof):
            raise PermissionError("production requires its live unclaimed bootstrap in the original interpreter")
        limits = BudgetLimits(stage_a_disk_accounting_mode=STAGE_A_CAPACITY_UPPER_BOUND_V2)
        _require_deadlines(proof.start_clock, limits)
        start = require_preimport_start_clock(proof.start_clock,
            config_sha256=proof.config_sha256, seal_sha256=proof.seal_sha256)
        _require_deadlines(start, limits)
        return start


def _burn_unused_bootstrap(proof: SupervisorBootstrapProof) -> None:
    with admission_bootstrap._INSTALL_LOCK:
        issued = admission_bootstrap._ISSUED_BOOTSTRAP
        unused = issued is not None and issued.proof is proof and not issued.consumed
    if unused:
        claim_bootstrap_for_ab(proof)


def _require_plain_metadata(value: object) -> None:
    """Reject callable/subclass containers before invoking metadata methods."""
    allowed = {ProductionABMetadata, ExperimentApproval, ABReadiness, StageBEquivalenceReceipt,
               BudgetLimits, RoleInputRegistration, RoleSpec, RegisteredFile, CacheFileRegistration}
    pending = [(value, 0)]
    observed = 0
    while pending:
        item, depth = pending.pop()
        observed += 1
        if observed > 1 << 20 or depth > 32:
            raise PermissionError("production metadata exceeds its bounded node/depth envelope")
        kind = type(item)
        if kind in {str, bytes}:
            if len(item) > 1 << 24:
                raise PermissionError("production metadata scalar exceeds its fixed byte bound")
        elif kind in {int, float, bool, type(None)}:
            continue
        elif kind is tuple:
            if len(item) > 1 << 16:
                raise PermissionError("production metadata tuple exceeds its fixed item bound")
            pending.extend((child, depth + 1) for child in item)
        elif kind in allowed:
            pending.extend((getattr(item, field.name), depth + 1) for field in fields(kind))
        else:
            raise PermissionError("production metadata contains an executable/injectable or unapproved value type")


def _require_metadata(metadata: ProductionABMetadata) -> tuple[RoleSpec, ...]:
    if type(metadata) is not ProductionABMetadata:
        raise PermissionError("production requires the fixed metadata-only A+B bundle")
    _require_plain_metadata(metadata)
    fixed = (
        (metadata.approval, ExperimentApproval), (metadata.readiness, ABReadiness),
        (metadata.limits, BudgetLimits),
    )
    if (any(type(value) is not expected for value, expected in fixed)
            or type(metadata.readiness.equivalence) is not StageBEquivalenceReceipt
            or type(metadata.role_registrations) is not tuple or len(metadata.role_registrations) != 105
            or any(type(item) is not RoleInputRegistration or type(item.role) is not RoleSpec
                   for item in metadata.role_registrations)
            or type(metadata.reference_projections) is not tuple or len(metadata.reference_projections) != 105
            or any(type(item) is not RegisteredFile for item in metadata.reference_projections)
            or type(metadata.control_final_match_projections) is not tuple
            or len(metadata.control_final_match_projections) != 5
            or any(type(item) is not RegisteredFile for item in metadata.control_final_match_projections)
            or type(metadata.role_registry_bytes) is not bytes or not 0 < len(metadata.role_registry_bytes) <= 1 << 24
            or type(metadata.path_map_manifest_bytes) is not bytes or not 0 < len(metadata.path_map_manifest_bytes) <= 1 << 24
            or type(metadata.config_path) is not str):
        raise PermissionError("production metadata must bind the exact complete reviewed input types")
    roles = tuple(item.role for item in metadata.role_registrations)
    config_path = PurePosixPath(metadata.config_path)
    frozen = contracts.require_frozen_admission()
    if (len({role.role_id for role in roles}) != 105
            or {item.role_id for item in metadata.reference_projections} != {role.role_id for role in roles}
            or not config_path.is_absolute() or config_path.as_posix() != metadata.config_path
            or ".." in config_path.parts
            or hashlib.sha256(metadata.role_registry_bytes).hexdigest() != frozen.role_input_registry_sha256.lower()
            or hashlib.sha256(metadata.path_map_manifest_bytes).hexdigest() != frozen.path_map_sha256.lower()):
        raise PermissionError("production metadata paths, role graph or registry bytes differ from frozen admission")
    approval, readiness = metadata.approval, metadata.readiness
    approval.require_full_ab()
    readiness.require_complete()
    require_fixed_native_budget(metadata.limits)
    if (metadata.limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or metadata.limits.digest() != frozen.budget_policy_sha256.lower()):
        raise PermissionError("production native budget differs from frozen admission")
    return verify_metadata_pins(metadata)


def _load_native_path_map(proof: SupervisorBootstrapProof, metadata: ProductionABMetadata,
                          guard: BudgetGuard) -> ExactPathMap:
    from .linux_native_path_map import _install_original_metadata_path_map
    return _install_original_metadata_path_map(proof, metadata, guard)


def _load_native_phase_runner(proof: SupervisorBootstrapProof, guard: BudgetGuard):
    from .linux_phase_runner import _install_original_phase_runner

    _require_bootstrap_start(proof)
    return _install_original_phase_runner(proof, guard)


def _require_native_nested_producers(path_map: ExactPathMap, phase_runner: object, guard: BudgetGuard) -> None:
    """No supplied implementation/hash/mount callback may run as a preflight."""
    if type(path_map) is not ExactPathMap or type(guard) is not BudgetGuard:
        raise PermissionError("production nested data owners require exact path-map/guard types")
    # The early metadata directory owner and fixed phase executor sources
    # exist, but installed directory role publishers, immutable phase/runtime
    # tree and complete native installation
    # authority still do not. Source assembly cannot pass this deployment gate.
    # Reject before implementation_sha256(), activate_role_view(), metadata
    # reads, provider construction or any user-supplied callable invocation.
    raise PermissionError("actual nested role/path publication and complete phase/runtime deployment are missing; injected callbacks are forbidden")


def _load_authenticated_outer_qpc(start: LinuxStartClockProof) -> tuple[int, int]:
    # The installed bridge must authenticate the original
    # WindowsQpcWallInvocation and bind it to this native invocation/unit.
    raise PermissionError("authenticated original Windows QPC-to-Linux launch transport is not installed")


def _require_authenticated_outer_qpc(start: LinuxStartClockProof, *, external_started_ticks: int,
                                     qpc_frequency: int) -> None:
    if (type(external_started_ticks) is not int or external_started_ticks <= 0
            or type(qpc_frequency) is not int or qpc_frequency <= 0):
        raise PermissionError("production requires the original positive outer QPC epoch and frequency")
    # Integer arguments cannot establish the actual host launch. Never convert
    # Linux ns to QPC or substitute a new host clock sample for the original.
    original_ticks, original_frequency = _load_authenticated_outer_qpc(start)
    if (external_started_ticks, qpc_frequency) != (original_ticks, original_frequency):
        raise PermissionError("production outer QPC differs from its authenticated original launch")


def _require_deadlines(start: LinuxStartClockProof, limits: BudgetLimits) -> None:
    require_fixed_native_budget(limits)
    if (limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or limits.digest() != contracts.require_frozen_admission().budget_policy_sha256.lower()):
        raise PermissionError("production native deadlines require the frozen V2 budget")
    now = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    if (now < start.invocation_started_monotonic_ns
            or now >= start.invocation_started_monotonic_ns + limits.stage_a_wall_ns - 60_000_000_000
            or now >= start.invocation_started_monotonic_ns + limits.total_wall_ns - 60_000_000_000):
        raise PermissionError("pre-import verification/assembly has exhausted the original native deadline")


def assemble_production_bindings(proof: SupervisorBootstrapProof, metadata: ProductionABMetadata, *,
                                 external_started_ticks: int, qpc_frequency: int) -> ABExecutionBindings:
    """Use the original native start for the single concrete controller owner.

    No read/write/worker backend is supplied through a callable factory. Native
    timers are armed by that controller after exec at the original absolute
    deadlines, including the preceding config/snapshot/bootstrap work.
    """
    global _ASSEMBLY_ENTERED
    if _ASSEMBLY_ENTERED:
        raise PermissionError("production owner assembly has already been attempted")
    _ASSEMBLY_ENTERED = True
    path_map = None
    try:
        start = _require_bootstrap_start(proof)
        roles = _require_metadata(metadata)
        require_installed_metadata(proof, metadata)
        _require_deadlines(start, metadata.limits)
        _require_authenticated_outer_qpc(start, external_started_ticks=external_started_ticks,
                                        qpc_frequency=qpc_frequency)
        ledger, guard, supervisor = assemble_production_owners(
            approval=metadata.approval, limits=metadata.limits, invocation_id=start.invocation_id,
            invocation_started_monotonic_ns=start.invocation_started_monotonic_ns,
            external_started_ticks=external_started_ticks, qpc_frequency=qpc_frequency,
            role_registry_bytes=metadata.role_registry_bytes,
        )
        path_map = _load_native_path_map(proof, metadata, guard)
        phase_runner = _load_native_phase_runner(proof, guard)
        _require_native_nested_producers(path_map, phase_runner, guard)
        # Every concrete data constructor is after the original owners and
        # nested native producer checks. No prepared Stage B/provider carries
        # an earlier ledger into this invocation.
        frozen = contracts.require_frozen_admission()
        loader = LazyRoleLoader(metadata.role_registrations,
            role_graph_sha256=frozen.role_graph_sha256, path_map=path_map)
        references = ApprovedReferenceStore(roles,
            {item.role_id: item for item in metadata.reference_projections}, loader, path_map)
        candidates = RoleCandidateReconstructor(loader, metadata.role_registrations)
        gt_root = PureWindowsPath(frozen.gt_input_root_path)
        truth_provider = ScopedTruthProvider(str(gt_root / "gt-view-registry.json"),
            str(gt_root / "gt-role-scopes.json"), ledger, path_map)
        control_matches = HistoricalControlMatchStore(metadata.control_final_match_projections, roles, path_map)
        stage_b = StageBAdapter(roles=roles, role_graph=truth_provider._role_graph,
            truth_provider=truth_provider, repo_root=Path(frozen.source_snapshot_root),
            control_matches=control_matches,
            config_path=Path(metadata.config_path), gt_view_registry_path=truth_provider._registry_path,
            gt_role_scopes_path=truth_provider._role_scopes_path, phase_runner=phase_runner)
        return ABExecutionBindings(metadata.approval, metadata.readiness, roles,
            references, candidates, stage_b, ledger, guard, supervisor)
    except BaseException as primary:
        close_error = burn_error = None
        try:
            if path_map is not None:
                ExactPathMap.close(path_map)  # Captured original map, independent of public data holders.
        except BaseException as error:
            close_error = error
        try:
            _burn_unused_bootstrap(proof)
        except BaseException as error:
            burn_error = error
        if close_error is not None or burn_error is not None:
            error = PermissionError("production assembly failed; original and map-close/bootstrap-burn errors retained")
            error.primary_error = primary
            error.secondary_errors = tuple(item for item in (close_error, burn_error) if item is not None)
            raise error from primary
        raise


def _require_data_bindings_before_preflight(bindings: ABExecutionBindings) -> None:
    fixed = ((bindings.approval, ExperimentApproval), (bindings.readiness, ABReadiness),
             (bindings.reference_provider, ApprovedReferenceStore),
             (bindings.candidate_builder, RoleCandidateReconstructor), (bindings.stage_b_adapter, StageBAdapter))
    if any(type(value) is not expected for value, expected in fixed):
        raise PermissionError("production requires the exact concrete data binding types")
    _require_plain_metadata(bindings.approval)
    _require_plain_metadata(bindings.readiness)
    _require_plain_metadata(bindings.roles)
    builder, stage_b = bindings.candidate_builder, bindings.stage_b_adapter
    loader = builder._loader
    if type(loader) is not LazyRoleLoader or type(loader.path_map) is not ExactPathMap:
        raise PermissionError("production input loader/path-map is not the exact concrete owner")
    path_map = loader.path_map
    if (type(stage_b.truth_provider) is not ScopedTruthProvider
            or stage_b.truth_provider._ledger is not bindings.ledger
            or stage_b.truth_provider.path_map is not path_map
            or stage_b.truth_provider._role_graph is not stage_b.role_graph
            or type(stage_b.control_matches) is not HistoricalControlMatchStore
            or stage_b.control_matches.path_map is not path_map
            or stage_b.control_matches.roles != bindings.roles
            or bindings.reference_provider.path_map is not path_map):
        raise PermissionError("production Stage B/provider must share the fresh original ledger/graph/path-map")
    # These producers are validated BEFORE run_bootstrapped_ab/run_ab can call
    # Stage B preflight, implementation_sha256 or role mount callbacks.
    _require_native_nested_producers(path_map, stage_b.phase_runner, bindings.guard)


def _preserve_original_run_failure(controller, original, primary) -> None:
    """Use captured private pins after dispatch, including public-link drift.

    This is only a preservation attempt on an already installed boundary.
    Startup aborts own their prior attempt; an absent/unarmed/disarmed boundary
    cannot write a marker. Neither branch attests teardown or permits retry.
    """
    if original is None:
        return
    if (type(controller) is not LinuxProductionController or _ASSEMBLIES.get(controller) is not original
            or original.pid != os.getpid() or original.thread is not threading.current_thread()
            or type(original.ports) is not LinuxProductionOSPorts):
        raise PermissionError("post-start preservation lost its captured original private controller")
    if (not original.attempted or original.abort_attempted or original.failure_preservation_attempted
            or original.policy is None or original.policy_bytes is None or original.unit_observation is None
            or original.control_mount_identity is None or original.envelope is None
            or not original.total_timer_armed):
        return
    from .linux_deadline import _TIMERS
    timer = _TIMERS.get(original.total_timer)
    if (timer is None or timer.consumed or not timer.armed or timer.pid != original.pid
            or timer.thread is not original.thread
            or timer.deadline_ns != original.started_ns + original.envelope.runtime_max_ns):
        return
    from .linux_failure_preservation import _SAFE
    kind = type(primary).__name__
    if type(kind) is not str or not _SAFE.fullmatch(kind):
        kind = "UnclassifiedRunnerFailure"
    # Call the exact class implementation with captured private identity, never
    # a later bindings.guard/enforcer/approval that may have drifted.
    LinuxProductionController.abort_startup(controller, original.invocation_id, original.approval,
                                            "post_start_runner", kind)


def run_production_ab(proof: SupervisorBootstrapProof, bindings: ABExecutionBindings) -> StageAResult | StageBResult:
    """Dispatch once to run_bootstrapped_ab with exact native start ownership."""
    global _RUN_ENTERED
    if _RUN_ENTERED:
        raise PermissionError("production A+B runner has already been attempted")
    _RUN_ENTERED = True
    controller = original = None
    try:
        start = _require_bootstrap_start(proof)
        if type(bindings) is not ABExecutionBindings:
            raise PermissionError("production requires the fixed concrete execution bindings")
        if (type(bindings.guard) is not BudgetGuard or type(bindings.ledger) is not AppendOnlyLedger
                or type(bindings.supervisor) is not Route2Supervisor
                or type(bindings.guard.enforcer) is not LinuxProductionController):
            raise PermissionError("production A+B requires the single native controller/guard/ledger/supervisor")
        _require_data_bindings_before_preflight(bindings)
        guard, supervisor = bindings.guard, bindings.supervisor
        controller = guard.enforcer
        candidate = _ASSEMBLIES.get(controller)
        if (candidate is None or candidate.pid != start.pid or candidate.thread is not threading.current_thread()
                or candidate.guard() is not guard or candidate.supervisor() is not supervisor
                or candidate.approval is not bindings.approval or candidate.approval_ledger is not bindings.ledger
                or type(candidate.ports) is not LinuxProductionOSPorts
                or candidate.attempted or candidate.failed or candidate.abort_attempted
                or candidate.limits is not guard.limits or supervisor.limits is not guard.limits
                or candidate.invocation_id != start.invocation_id or guard.invocation_id != start.invocation_id
                or supervisor.invocation_id != start.invocation_id
                or candidate.started_ns != start.invocation_started_monotonic_ns
                or guard._invocation_started_ns != start.invocation_started_monotonic_ns
                or guard.ledger is not bindings.ledger or supervisor.ops is not controller
                or supervisor.approval is not bindings.approval or supervisor.state is not SupervisorState.NEW):
            raise PermissionError("production owners lost the original pre-import process/invocation/clock binding")
        original = candidate
        _require_deadlines(start, guard.limits)
        _require_authenticated_outer_qpc(start, external_started_ticks=supervisor.external_started_ticks,
                                        qpc_frequency=supervisor.qpc_frequency)
        return run_bootstrapped_ab(proof, bindings)
    except BaseException as primary:
        secondary = []
        try:
            _burn_unused_bootstrap(proof)
        except BaseException as burn_error:
            secondary.append(burn_error)
        try:
            _preserve_original_run_failure(controller, original, primary)
        except BaseException as preservation_error:
            secondary.append(preservation_error)
        if secondary:
            from .linux_failure_preservation import StartupPreservedWithoutTeardown
            error = PermissionError("production runner failed; original failure and additional preservation errors retained")
            error.primary_error, error.secondary_errors = primary, tuple(secondary)
            error.preservation_receipts = tuple(item.preservation_receipt for item in secondary
                if type(item) is StartupPreservedWithoutTeardown)
            raise error from primary
        raise


def _load_installed_metadata(proof: SupervisorBootstrapProof) -> ProductionABMetadata:
    # The concrete loader authenticates the original unclaimed bootstrap and
    # decodes only records. main burns that original handoff on any refusal.
    metadata = load_installed_metadata(proof)
    _require_metadata(metadata)
    _require_deadlines(_require_bootstrap_start(proof), metadata.limits)
    return metadata


def main() -> StageAResult | StageBResult:
    """Pinned exec entry: bootstrap and continue to the fixed full A+B path."""
    proof = bootstrap_frozen_admission(DEFAULT_SUPERVISOR_CONFIG)
    try:
        metadata = _load_installed_metadata(proof)
        start = _require_bootstrap_start(proof)
        external_started_ticks, qpc_frequency = _load_authenticated_outer_qpc(start)
        bindings = assemble_production_bindings(proof, metadata,
            external_started_ticks=external_started_ticks, qpc_frequency=qpc_frequency)
        return run_production_ab(proof, bindings)
    except BaseException as primary:
        try:
            _burn_unused_bootstrap(proof)
        except BaseException as burn_error:
            error = PermissionError("production entry failed; original and bootstrap-burn error retained")
            error.primary_error, error.secondary_errors = primary, (burn_error,)
            raise error from primary
        raise


__all__ = ["ProductionABMetadata", "assemble_production_bindings", "run_production_ab", "main"]
