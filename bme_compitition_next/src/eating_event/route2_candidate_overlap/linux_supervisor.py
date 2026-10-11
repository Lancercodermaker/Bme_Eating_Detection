"""Fail-closed Route 2 lifecycle coordinator for a trusted outer supervisor.

This module owns the ordering of controller operations.  It deliberately does
not implement privileged Linux/Windows operations: the ``SupervisorOps`` port
must be provided by the separately installed, independently reviewed
controller.  Receipts returned by an implementation are claims until that
implementation and its installation boundary have been reviewed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from typing import Mapping, Protocol

from .budget import (
    BudgetLimits,
    BudgetGuard,
    AppendOnlyLedger,
    EnforcementReceipt,
    ResourceSnapshot,
    NestedBackingSample,
    require_nested_backing_sample,
    _replay_call_event_accounting,
    _projection_call_role_ids,
    StageBProjection,
    _canonical as _budget_canonical,
    require_exact_stage_b_projection,
    require_stage_b_entry,
    stage_a_projection_disk_bytes,
)
from .contracts import ExperimentApproval, STUDY_ID, StudyStatus
from .linux_enforcement import verify_post_exit_receipt
from .startup_ownership import registered_startup, register_startup, require_startup_binding, volume_preparation_entered


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant {value} is forbidden")


def _canonical_json_bytes(value: object) -> bytes:
    return _budget_canonical(value)


def _require_external_role_graph_binding(
    projection_payload: Mapping[str, object],
    expected_role_graph_sha256: str,
) -> str:
    """Require a ledger projection to match the independent admission graph pin."""

    if (
        not isinstance(projection_payload, Mapping)
        or type(expected_role_graph_sha256) is not str
        or not _SHA256.fullmatch(expected_role_graph_sha256.lower())
    ):
        raise PermissionError("external frozen admission role graph hash is absent or malformed")
    projection_role_graph_sha256 = projection_payload.get("role_graph_sha256")
    if (
        type(projection_role_graph_sha256) is not str
        or not _SHA256.fullmatch(projection_role_graph_sha256.lower())
        or projection_role_graph_sha256.lower() != expected_role_graph_sha256.lower()
    ):
        raise PermissionError("Stage B projection role graph differs from the external frozen admission")
    return expected_role_graph_sha256.lower()


class SupervisorState(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    STARTED = "STARTED"
    STAGE_A_FINISHED = "STAGE_A_FINISHED"
    STAGE_B_ENTERED = "STAGE_B_ENTERED"
    STAGE_B_READY = "STAGE_B_READY"
    STAGE_B_FINISHED = "STAGE_B_FINISHED"
    TERMINAL_PENDING = "TERMINAL_PENDING"
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class BackingFreeReceipt:
    invocation_id: str
    sampled_monotonic_ns: int
    guest_free_bytes: int
    guest_mount_id: str
    guest_device: str
    windows_vhdx_path: str
    windows_volume_id: str
    windows_free_bytes: int
    available_ram_bytes: int
    nested_backing: NestedBackingSample | None = None


@dataclass(frozen=True, slots=True)
class OneShotLockReceipt:
    invocation_id: str
    study_id: str
    lock_path: str
    created_monotonic_ns: int
    exclusive_create: bool


@dataclass(frozen=True, slots=True)
class StartupAbortReceipt:
    invocation_id: str
    study_root_path: str
    ledger_path: str
    lock_path: str
    image_path: str
    mounts_detached: bool
    partial_resources_quarantined: bool
    failure_receipt_durable: bool
    retry_forbidden: bool
    completed_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class ImageVolumeReceipt:
    invocation_id: str
    study_id: str
    study_root_path: str
    ledger_path: str
    lock_path: str
    image_path: str
    created_monotonic_ns: int
    image_device: int
    image_inode: int
    loop_device: str
    filesystem_uuid: str
    mount_id: str
    filesystem_device: str
    filesystem_capacity_bytes: int
    image_length_bytes: int


@dataclass(frozen=True, slots=True)
class StageABoundaryReceipt:
    invocation_id: str
    reference_roles: int
    treatment_roles: int
    different_treatment_roles: int
    stage_a_disk_bytes: int
    finished_monotonic_ns: int
    fsynced_monotonic_ns: int
    event_sha256: str
    durable: bool


@dataclass(frozen=True, slots=True)
class DurableLedgerReceipt:
    invocation_id: str
    event_sha256: str
    fsynced_monotonic_ns: int
    durable: bool


@dataclass(frozen=True, slots=True)
class StageBExecutionReceipt:
    invocation_id: str
    inner_roles_completed: int
    outer_roles_completed: int
    verifier_fit_calls: int
    verifier_predict_calls: int
    decoder_calls: int
    evaluator_calls: int
    pooled_aggregation_calls: int
    pooled_aggregation_completed: bool
    pooled_gt_reads: int
    call_event_count: int
    call_event_accounting_sha256: str
    finished_monotonic_ns: int
    fsynced_monotonic_ns: int
    event_sha256: str
    result_sha256: str
    durable: bool


@dataclass(frozen=True, slots=True)
class TerminalCloseReceipt:
    invocation_id: str
    unit_name: str
    status: str
    terminal_sha256: str
    terminal_binding_sha256: str
    invocation_started_monotonic_ns: int
    terminal_closed_monotonic_ns: int
    deadline_monotonic_ns: int
    ledger_fsynced: bool
    ledger_closed: bool
    no_active_gt_view: bool
    no_active_worker: bool
    terminal_record_bytes: bytes
    ledger_bytes: bytes


@dataclass(frozen=True, slots=True)
class ExternalExitObservation:
    invocation_id: str
    unit_name: str
    unit_inactive: bool
    cgroup_empty: bool
    terminal_reverified: bool
    external_receipt_durable: bool
    receipt: Mapping[str, object]
    observed_monotonic_ns: int
    observed_external_ticks: int
    qpc_frequency: int
    external_started_ticks: int


@dataclass(frozen=True, slots=True)
class TerminalAcceptance:
    invocation_id: str
    status: str
    terminal_sha256: str
    accepted: bool


class SupervisorOps(Protocol):
    """Trusted OS adapter required by the lifecycle coordinator.

    ``first_monotonic_sample`` must be the first measured operation in the
    invocation.  ``acquire_one_shot_lock`` must be an atomic durable exclusive
    create.  ``observe_exit_and_persist_wall_receipt`` is an outer-controller
    operation: it may return only after the service is inactive, its cgroup is
    empty, the closed terminal has been rehashed, and the host-clock receipt
    has been fsynced.
    """

    def first_monotonic_sample(self) -> int: ...
    def sample_startup_free(self, invocation_id: str) -> BackingFreeReceipt: ...
    def acquire_one_shot_lock(self, invocation_id: str, approval: object) -> OneShotLockReceipt: ...
    def abort_startup(
        self, invocation_id: str, approval: object,
        failure_phase: str, failure_kind: str,
    ) -> StartupAbortReceipt: ...
    def create_stage_a_volume(
        self, invocation_id: str, approval: object, limits: BudgetLimits,
    ) -> ImageVolumeReceipt: ...
    def read_stage_a_boundary(self, invocation_id: str) -> StageABoundaryReceipt: ...
    def append_stage_b_entry(
        self, invocation_id: str, projection: StageBProjection,
    ) -> DurableLedgerReceipt: ...
    def expand_same_volume(
        self, invocation_id: str, current: ImageVolumeReceipt,
        event_sha256: str, limits: BudgetLimits,
    ) -> ImageVolumeReceipt: ...
    def append_expansion_receipt(
        self, invocation_id: str, event_sha256: str, expanded: ImageVolumeReceipt,
    ) -> DurableLedgerReceipt: ...
    def read_stage_b_completion(self, invocation_id: str) -> StageBExecutionReceipt: ...
    def close_terminal(
        self, invocation_id: str, status: str, evidence: Mapping[str, object],
        started_ns: int, deadline_ns: int,
    ) -> TerminalCloseReceipt: ...
    def observe_exit_and_persist_wall_receipt(
        self, terminal: TerminalCloseReceipt,
    ) -> ExternalExitObservation: ...


class Route2Supervisor:
    """One-shot coordinator; it cannot itself authorize or run Stage A/B."""

    def __init__(
        self,
        *,
        approval: object,
        invocation_id: str,
        ops: SupervisorOps,
        limits: BudgetLimits,
        external_started_ticks: int,
        qpc_frequency: int,
    ) -> None:
        if type(approval) is not ExperimentApproval:
            raise PermissionError("Route2Supervisor requires the exact ExperimentApproval type")
        if not invocation_id or invocation_id.isspace():
            raise ValueError("one invocation identity is required")
        if type(external_started_ticks) is not int or external_started_ticks <= 0:
            raise ValueError("the frozen outer QPC start sample is required")
        if type(qpc_frequency) is not int or qpc_frequency <= 0:
            raise ValueError("the outer QPC frequency must be a positive exact integer")
        self.approval = approval
        self.invocation_id = invocation_id
        self.ops = ops
        self.limits = limits
        self.external_started_ticks = external_started_ticks
        self.qpc_frequency = qpc_frequency
        self.state = SupervisorState.NEW
        self.started_monotonic_ns: int | None = None
        self.deadline_monotonic_ns: int | None = None
        self.startup: BackingFreeReceipt | None = None
        self.volume: ImageVolumeReceipt | None = None
        self.stage_a: StageABoundaryReceipt | None = None
        self.frozen_rss_ceiling_bytes: int | None = None
        self.expansion_receipt: DurableLedgerReceipt | None = None
        self.stage_b_entry: DurableLedgerReceipt | None = None
        self._stage_b_projection: StageBProjection | None = None
        self._approved_role_graph_sha256: str | None = None
        self.stage_b_completion: StageBExecutionReceipt | None = None
        self._terminal: TerminalCloseReceipt | None = None
        self._terminal_attempted = False
        self._lock_attempted = False
        self._startup_failure_phase = "approval"
        self._budget_guard: BudgetGuard | None = None

    def bind_budget_guard(self, guard: BudgetGuard) -> None:
        """Bind the canonical startup owner, before any OS operation.

        The admitted runner uses this mode. The standalone port-ordering model
        remains available for component checks, but cannot also create storage
        for a bound guard. Receipt adoption from another guard is forbidden.
        """
        if (type(guard) is not BudgetGuard or type(guard.ledger) is not AppendOnlyLedger
                or self.state is not SupervisorState.NEW or self._budget_guard is not None
                or any(getattr(self, name) is not None for name in (
                    "started_monotonic_ns", "deadline_monotonic_ns", "startup", "volume", "stage_a",
                    "frozen_rss_ceiling_bytes", "expansion_receipt", "stage_b_entry", "_stage_b_projection",
                    "_approved_role_graph_sha256", "stage_b_completion", "_terminal"))
                or self._terminal_attempted is not False or self._lock_attempted is not False
                or self._startup_failure_phase != "approval"
                or registered_startup(guard) is not None
                or guard._lifecycle_supervisor is not None or guard._start_entered
                or guard._started or guard.ledger._create_entered
                or guard.ledger._fd is not None or guard.ledger._seq != 0
                or guard.enforcer is not self.ops or guard.invocation_id != self.invocation_id
                or guard.limits != self.limits or type(guard._invocation_started_ns) is not int
                or guard._invocation_started_ns <= 0 or guard.study_root != guard.ledger.study_root
                or guard.study_root != Path(self.approval.study_root_path)
                or guard.ledger.path != Path(self.approval.budget_ledger_path)
                or guard.ledger.lock_path != Path(self.approval.lock_path)
                or guard.approved_controller_sha256 != self.approval.resource_controller_sha256.lower()
                or guard.approved_write_volumes != self.approval.approved_write_volumes):
            raise PermissionError("startup ownership requires one fresh guard, controller, clock and storage identity")
        self.approval.require_full_ab()
        self._require_approval_paths()
        register_startup(self, guard)
        self._budget_guard = guard
        guard._lifecycle_supervisor = self

    def observe_budget_start(self, guard: BudgetGuard) -> None:
        """Verify the live owner's durable startup without creating anything."""
        require_startup_binding(guard, self.approval)
        if (type(guard) is not BudgetGuard or guard is not self._budget_guard
                or guard._lifecycle_supervisor is not self or self.state is not SupervisorState.NEW
                or guard.enforcer is not self.ops or guard._started is not True
                or guard.ledger._owner_thread_id != threading.get_ident()
                or guard.ledger._fd is None or guard.ledger._seq != 2
                or guard.ledger._invocation_id != self.invocation_id
                or guard.ledger._invocation_started_monotonic_ns != guard._invocation_started_ns
                or type(guard._startup_receipt) is not EnforcementReceipt
                or type(guard._startup_snapshot) is not ResourceSnapshot
                or type(guard.ledger._created_monotonic_ns) is not int):
            raise PermissionError("startup observation requires the bound live ledger owner")
        self.state = SupervisorState.STARTING
        try:
            self.approval.require_full_ab()
            self._require_approval_paths()
            receipt, snapshot = guard._startup_receipt, guard._startup_snapshot
            self.started_monotonic_ns = guard._invocation_started_ns
            self.deadline_monotonic_ns = self.started_monotonic_ns + self.limits.total_wall_ns
            self._verify_guard_startup_journal(guard)
            self._verify_guard_startup_lock(guard)
            sample = BackingFreeReceipt(
                self.invocation_id, receipt.precreate_free_checked_monotonic_ns,
                receipt.precreate_guest_free_bytes, snapshot.guest_backing_mount_id,
                snapshot.guest_backing_device, snapshot.windows_vhdx_path,
                snapshot.windows_volume_id, receipt.precreate_windows_volume_free_bytes,
                snapshot.available_ram_bytes, receipt.precreate_nested_backing,
            )
            self._require_startup_sample(sample)
            # The guard owns the study lock after image creation. The outer OS
            # backend still owes its pre-image one-shot attempt/quarantine.
            lock = OneShotLockReceipt(self.invocation_id, STUDY_ID, self.approval.lock_path,
                                      guard.ledger._created_monotonic_ns, True)
            self._require_lock(lock, sample)
            volume = ImageVolumeReceipt(
                self.invocation_id, STUDY_ID, self.approval.study_root_path,
                self.approval.budget_ledger_path, self.approval.lock_path,
                receipt.study_image_path, receipt.image_created_monotonic_ns,
                receipt.study_image_dev, receipt.study_image_inode, receipt.study_loop_device,
                receipt.study_fs_uuid, snapshot.study_mount_id, snapshot.study_device,
                snapshot.study_fs_capacity_bytes, receipt.study_image_length_bytes,
            )
            # In canonical ownership mode lock creation is after image creation;
            # validate image/free ordering separately rather than inventing an
            # earlier lock receipt.
            if (not self.started_monotonic_ns <= sample.sampled_monotonic_ns
                    < volume.created_monotonic_ns <= lock.created_monotonic_ns
                    <= self.started_monotonic_ns + self.limits.stage_a_wall_ns):
                raise PermissionError("canonical startup storage is outside the measured Stage A boundary")
            if guard.frozen_rss_ceiling_bytes != min(self.limits.rss_cap_bytes, 3 * sample.available_ram_bytes // 5):
                raise PermissionError("guard and supervisor disagree on the frozen RSS ceiling")
            self.startup, self.volume = sample, volume
            self.frozen_rss_ceiling_bytes = guard.frozen_rss_ceiling_bytes
            from .contracts import require_frozen_admission
            from .phase_observation import register_phase_observer
            register_phase_observer(guard, require_frozen_admission().role_graph_sha256)
            from .terminal_observation import register_terminal_observer
            register_terminal_observer(guard)
            self.state = SupervisorState.STARTED
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def observe_budget_terminal_close(self, guard: BudgetGuard) -> TerminalCloseReceipt:
        """Read the original owner's close once, leaving external acceptance pending.

        This uses no SupervisorOps terminal writer or wall observer. The real
        controller must still supply the helper's worker/GT quiescence source;
        its absence refuses even a correctly closed journal. The returned
        close handoff is metadata evidence, never a legal scientific result.
        """
        from .terminal_observation import read_owned_terminal_close
        original = registered_startup(guard) if type(guard) is BudgetGuard else None
        try:
            binding = require_startup_binding(guard, self.approval)
            if (guard is not self._budget_guard or binding is None or binding.owner() is not self
                    or guard._lifecycle_supervisor is not self or self.ops is not binding.controller
                    or self.invocation_id != binding.invocation_id or self.limits != binding.limits
                    or self.started_monotonic_ns != binding.started_ns
                    or self.deadline_monotonic_ns != binding.started_ns + binding.limits.total_wall_ns
                    or self._terminal_attempted is not False or self._terminal is not None):
                raise PermissionError("terminal close requires the original bound owner and clock")
            self._terminal_attempted = True
            proof = read_owned_terminal_close(guard)
            if (type(proof) is not TerminalCloseReceipt or proof.invocation_id != binding.invocation_id
                    or proof.invocation_started_monotonic_ns != binding.started_ns
                    or proof.deadline_monotonic_ns != self.deadline_monotonic_ns):
                raise PermissionError("readonly terminal handoff differs from its original startup")
            self._terminal = proof
            self.state = SupervisorState.TERMINAL_PENDING
            return proof
        except BaseException:
            self.state = SupervisorState.FAILED
            if original is not None and original.owner() is self:
                from .terminal_observation import fail_owned_terminal
                try:
                    fail_owned_terminal(guard)
                except BaseException:
                    pass
            raise

    def _require_phase_owner(self, guard: BudgetGuard, state: SupervisorState) -> None:
        from .phase_observation import (startup_owned_payload, accepted_owned_phase_event,
                                        require_phase_role_graph)
        binding = require_startup_binding(guard, self.approval)
        if (binding is None or binding.owner() is not self
                or guard is not self._budget_guard or self.state is not state
                or guard._started is not True or guard._finished is not False
                or guard._activity_open is not False or guard.ledger._terminal is not False
                or guard._boundary_failure is not None):
            raise PermissionError("phase observation requires the live inactive bound ledger owner")
        startup = startup_owned_payload(guard)
        if (type(self.started_monotonic_ns) is not int or self.started_monotonic_ns != binding.started_ns
                or type(self.deadline_monotonic_ns) is not int
                or self.deadline_monotonic_ns != binding.started_ns + binding.limits.total_wall_ns
                or self.frozen_rss_ceiling_bytes != startup["frozen_rss_ceiling_bytes"]
                or guard.frozen_rss_ceiling_bytes != startup["frozen_rss_ceiling_bytes"]):
            raise PermissionError("phase clocks or RSS ceiling drifted from the startup anchor")
        initial, snapshot = startup["controller_receipt"], startup["startup_snapshot"]
        expected_volume = ImageVolumeReceipt(
            binding.invocation_id, STUDY_ID, binding.approval.study_root_path,
            binding.approval.budget_ledger_path, binding.approval.lock_path,
            initial["study_image_path"], initial["image_created_monotonic_ns"],
            initial["study_image_dev"], initial["study_image_inode"], initial["study_loop_device"],
            initial["study_fs_uuid"], snapshot["study_mount_id"], snapshot["study_device"],
            snapshot["study_fs_capacity_bytes"], initial["study_image_length_bytes"],
        )
        if state is not SupervisorState.STARTED:
            accepted = accepted_owned_phase_event(guard, "stage_a_finished")
            expected_a = StageABoundaryReceipt(**accepted.payload,
                                               fsynced_monotonic_ns=accepted.receipt.fsynced_monotonic_ns,
                                               event_sha256=accepted.receipt.event_sha256, durable=True)
            if type(self.stage_a) is not StageABoundaryReceipt or self.stage_a != expected_a:
                raise PermissionError("Stage A receipt drifted from its accepted owner event")
        if state in (SupervisorState.STAGE_B_ENTERED, SupervisorState.STAGE_B_READY):
            accepted = accepted_owned_phase_event(guard, "stage_b_entry_passed")
            expected_entry = DurableLedgerReceipt(binding.invocation_id, accepted.receipt.event_sha256,
                                                 accepted.receipt.fsynced_monotonic_ns, True)
            if (type(self.stage_b_entry) is not DurableLedgerReceipt or self.stage_b_entry != expected_entry
                    or type(self._stage_b_projection) is not StageBProjection
                    or _canonical_json_bytes(asdict(self._stage_b_projection))
                    != _canonical_json_bytes(accepted.payload["projection"])
                    or self._approved_role_graph_sha256 != require_phase_role_graph(guard)):
                raise PermissionError("Stage B entry drifted from its accepted owner event")
        if state is SupervisorState.STAGE_B_READY:
            accepted = accepted_owned_phase_event(guard, "stage_b_volume_expanded")
            expected_volume = ImageVolumeReceipt(**accepted.payload["volume"])
            expected_expansion = DurableLedgerReceipt(binding.invocation_id, accepted.receipt.event_sha256,
                                                     accepted.receipt.fsynced_monotonic_ns, True)
            if type(self.expansion_receipt) is not DurableLedgerReceipt or self.expansion_receipt != expected_expansion:
                raise PermissionError("expansion receipt drifted from its accepted owner event")
        if type(self.volume) is not ImageVolumeReceipt or self.volume != expected_volume:
            raise PermissionError("phase volume drifted from its accepted owner event")
        self._verify_guard_startup_lock(guard)

    def _reject_budget_phase(self, guard: BudgetGuard) -> None:
        from .phase_observation import fail_phase_observer
        self.state = SupervisorState.FAILED
        fail_phase_observer(guard)

    def fail_budget_phase(self, guard: BudgetGuard, error: BaseException) -> None:
        """Consume an invalid bound phase; OS teardown remains controller work."""
        binding = registered_startup(guard)
        if binding is None or binding.owner() is not self:
            raise PermissionError("phase failure does not belong to this registered owner")
        self._reject_budget_phase(guard)

    def observe_budget_stage_a(self, guard: BudgetGuard) -> StageABoundaryReceipt:
        """Adopt the owner's existing durable boundary, without appending it."""
        from .phase_observation import read_owned_phase_event, accept_owned_phase_event
        try:
            self._require_phase_owner(guard, SupervisorState.STARTED)
            event = guard._stage_a_event_receipt
            proof = read_owned_phase_event(guard, "stage_a_finished", event)
            receipt = StageABoundaryReceipt(**proof.payload,
                                           fsynced_monotonic_ns=event.fsynced_monotonic_ns,
                                           event_sha256=event.event_sha256, durable=True)
            if (receipt.invocation_id != self.invocation_id
                    or type(receipt.reference_roles) is not int or receipt.reference_roles != 105
                    or type(receipt.treatment_roles) is not int or receipt.treatment_roles != 105
                    or type(receipt.different_treatment_roles) is not int
                    or not 0 <= receipt.different_treatment_roles <= 105
                    or type(receipt.stage_a_disk_bytes) is not int
                    or not 0 <= receipt.stage_a_disk_bytes <= self.limits.stage_a_disk_bytes
                    or type(receipt.finished_monotonic_ns) is not int
                    or not self._required_start() <= receipt.finished_monotonic_ns
                    <= receipt.fsynced_monotonic_ns <= self._required_start() + self.limits.stage_a_wall_ns
                    or guard._stage_a_finished_ns != receipt.fsynced_monotonic_ns
                    or type(guard._stage_a_snapshot) is not ResourceSnapshot
                    or stage_a_projection_disk_bytes(guard._stage_a_snapshot, self.limits) != receipt.stage_a_disk_bytes):
                raise PermissionError("owned Stage A boundary differs from its durable snapshot")
            accept_owned_phase_event(guard, proof)
            self.stage_a = receipt
            self.state = SupervisorState.STAGE_A_FINISHED
            return receipt
        except BaseException:
            self._reject_budget_phase(guard)
            raise

    def observe_budget_stage_b_entry(self, guard: BudgetGuard,
                                     projection: StageBProjection) -> DurableLedgerReceipt:
        """Verify the persisted entry before the single controller expands."""
        from .phase_observation import (read_owned_phase_event, accept_owned_phase_event,
                                        require_phase_role_graph)
        try:
            self._require_phase_owner(guard, SupervisorState.STAGE_A_FINISHED)
            require_exact_stage_b_projection(projection)
            role_graph = require_phase_role_graph(guard)
            _require_external_role_graph_binding(asdict(projection), role_graph)
            projection.call_role_ids_by_kind()
            if (self.stage_a is None or self.stage_a.different_treatment_roles == 0
                    or projection.stage_a_disk_bytes_d_a != self.stage_a.stage_a_disk_bytes
                    or guard._stage_b_admitted is not False
                    or guard._stage_b_expansion_event_receipt is not None
                    or guard.ledger._active_gt_release is not None):
                raise PermissionError("owned Stage B entry lacks its distinct complete Stage A")
            require_stage_b_entry(projection, limits=self.limits,
                                  frozen_rss_ceiling_bytes=guard.frozen_rss_ceiling_bytes,
                                  stage_a_hard_lines_met=True)
            event = guard._stage_b_entry_event_receipt
            proof = read_owned_phase_event(guard, "stage_b_entry_passed", event)
            if (_canonical_json_bytes(proof.payload) != _canonical_json_bytes(
                    {"invocation_id": self.invocation_id, "projection": asdict(projection)})
                    or not self.stage_a.fsynced_monotonic_ns <= event.fsynced_monotonic_ns
                    <= self._required_start() + self.limits.stage_a_wall_ns):
                raise PermissionError("owned Stage B entry projection or fsync boundary differs")
            receipt = DurableLedgerReceipt(self.invocation_id, event.event_sha256,
                                           event.fsynced_monotonic_ns, True)
            accept_owned_phase_event(guard, proof)
            self.stage_b_entry = receipt
            self._stage_b_projection = projection
            self._approved_role_graph_sha256 = role_graph
            self.state = SupervisorState.STAGE_B_ENTERED
            return receipt
        except BaseException:
            self._reject_budget_phase(guard)
            raise

    def observe_budget_expansion(self, guard: BudgetGuard) -> ImageVolumeReceipt:
        """Adopt the same-volume expansion only after its owner fsyncs it."""
        from .phase_observation import read_owned_phase_event, accept_owned_phase_event
        try:
            self._require_phase_owner(guard, SupervisorState.STAGE_B_ENTERED)
            event = guard._stage_b_expansion_event_receipt
            proof = read_owned_phase_event(guard, "stage_b_volume_expanded", event)
            payload = proof.payload
            if (set(payload) != {"invocation_id", "entry_event_sha256", "volume"}
                    or self.stage_b_entry is None or self.volume is None
                    or payload["invocation_id"] != self.invocation_id
                    or payload["entry_event_sha256"] != self.stage_b_entry.event_sha256
                    or type(payload["volume"]) is not dict
                    or guard._stage_b_admitted is not False
                    or guard.ledger._active_gt_release is not None):
                raise PermissionError("owned expansion is not bound to the prior entry")
            expanded = ImageVolumeReceipt(**payload["volume"])
            self._require_same_expanded_volume(expanded, self.volume, self.stage_b_entry)
            if not expanded.created_monotonic_ns <= event.fsynced_monotonic_ns <= self._required_deadline():
                raise PermissionError("owned expansion fsync exceeded the total wall boundary")
            receipt = DurableLedgerReceipt(self.invocation_id, event.event_sha256,
                                           event.fsynced_monotonic_ns, True)
            accept_owned_phase_event(guard, proof)
            self.volume, self.expansion_receipt = expanded, receipt
            self.state = SupervisorState.STAGE_B_READY
            return expanded
        except BaseException:
            self._reject_budget_phase(guard)
            raise

    def observe_budget_stage_b_completion(self, guard: BudgetGuard) -> StageBExecutionReceipt:
        """Observe completion metadata; the guard owns call/science validation."""
        from .phase_observation import read_owned_phase_event, accept_owned_phase_event
        try:
            self._require_phase_owner(guard, SupervisorState.STAGE_B_READY)
            event = guard._stage_b_completion_event_receipt
            proof = read_owned_phase_event(guard, "stage_b_complete", event)
            receipt = StageBExecutionReceipt(**proof.payload,
                                             fsynced_monotonic_ns=event.fsynced_monotonic_ns,
                                             event_sha256=event.event_sha256, durable=True)
            counts = (receipt.inner_roles_completed, receipt.outer_roles_completed,
                      receipt.verifier_fit_calls, receipt.verifier_predict_calls,
                      receipt.decoder_calls, receipt.evaluator_calls,
                      receipt.pooled_aggregation_calls, receipt.pooled_gt_reads, receipt.call_event_count)
            if (self.expansion_receipt is None or guard._stage_b_admitted is not True
                    or guard.ledger._active_gt_release is not None
                    or receipt.invocation_id != self.invocation_id
                    or any(type(value) is not int for value in counts)
                    or counts != (20, 5, 25, 25, 65, 20, 1, 0, 408)
                    or receipt.pooled_aggregation_completed is not True
                    or type(receipt.finished_monotonic_ns) is not int
                    or not self.expansion_receipt.fsynced_monotonic_ns <= receipt.finished_monotonic_ns
                    <= receipt.fsynced_monotonic_ns <= self._required_deadline()
                    or type(receipt.call_event_accounting_sha256) is not str
                    or not _SHA256.fullmatch(receipt.call_event_accounting_sha256)
                    or type(receipt.result_sha256) is not str or not _SHA256.fullmatch(receipt.result_sha256)
                    or type(guard._stage_b_result_evidence) is not dict
                    or hashlib.sha256(_canonical_json_bytes(guard._stage_b_result_evidence)).hexdigest()
                    != receipt.result_sha256):
                raise PermissionError("owned Stage B completion metadata or result differs")
            accept_owned_phase_event(guard, proof)
            self.stage_b_completion = receipt
            self.state = SupervisorState.STAGE_B_FINISHED
            return receipt
        except BaseException:
            self._reject_budget_phase(guard)
            raise

    def _verify_guard_startup_journal(self, guard: BudgetGuard) -> None:
        ledger = guard.ledger
        fd = os.open(ledger.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
        try:
            before = os.fstat(fd)
            owner = os.fstat(ledger._fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 65536
                    or (before.st_dev, before.st_ino, before.st_size) != (owner.st_dev, owner.st_ino, owner.st_size)):
                raise PermissionError("startup journal is not the owner's bounded ordinary file")
            encoded = os.read(fd, 65537)
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise PermissionError("startup journal changed during observation")
        finally:
            os.close(fd)
        previous = "0" * 64
        payloads = []
        try:
            lines = encoded.splitlines(keepends=True)
            if len(lines) != 2:
                raise ValueError("expected exactly two startup records")
            for seq, raw in enumerate(lines):
                record = json.loads(raw)
                body, digest = record["entry"], record["sha256"]
                if (set(record) != {"entry", "sha256"} or _canonical_json_bytes(record) + b"\n" != raw
                        or set(body) != {"seq", "event", "payload", "previous_sha256"}
                        or type(body["seq"]) is not int or body["seq"] != seq
                        or body["event"] != ("study_created", "invocation_started")[seq]
                        or body["previous_sha256"] != previous
                        or hashlib.sha256(_canonical_json_bytes(body)).hexdigest() != digest
                        or type(body["payload"]) is not dict):
                    raise ValueError("invalid startup hash chain")
                previous = digest
                payloads.append(body["payload"])
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise PermissionError("startup journal cannot replay its exact durable hash chain") from exc
        created, started = payloads
        if (previous != ledger._tail
                or set(created) != {"study_id", "approval_record", "input_registry_sha256", "budget_policy_sha256", "limits", "created_wall_ns"}
                or created["study_id"] != STUDY_ID or created["approval_record"] != self.approval.approval_record
                or type(created["input_registry_sha256"]) is not str
                or created["input_registry_sha256"].lower() != self.approval.input_registry_sha256.lower()
                or created["budget_policy_sha256"] != self.limits.digest()
                or _canonical_json_bytes(created["limits"]) != _canonical_json_bytes(asdict(self.limits))
                or type(created["created_wall_ns"]) is not int or created["created_wall_ns"] <= 0
                or _canonical_json_bytes(started) != _canonical_json_bytes({"invocation_id": self.invocation_id, "monotonic_ns": guard._invocation_started_ns,
                               "controller_receipt": asdict(guard._startup_receipt),
                               "startup_snapshot": asdict(guard._startup_snapshot),
                               "frozen_rss_ceiling_bytes": guard.frozen_rss_ceiling_bytes})):
            raise PermissionError("startup journal differs from the bound approval, guard or controller")

    def _verify_guard_startup_lock(self, guard: BudgetGuard) -> None:
        ledger = guard.ledger
        fd = os.open(ledger.lock_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
        try:
            def identity(info):
                return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                        info.st_uid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 4096
                    or identity(before) != ledger._lock_identity):
                raise PermissionError("startup study lock was removed, replaced or modified")
            encoded = os.read(fd, 4097)
            if (identity(os.fstat(fd)) != ledger._lock_identity
                    or identity(ledger.lock_path.lstat()) != ledger._lock_identity
                    or hashlib.sha256(encoded).hexdigest() != ledger._lock_sha256):
                raise PermissionError("startup study lock bytes or visible identity changed")
        finally:
            os.close(fd)

    def fail_budget_start(self, guard: BudgetGuard, phase: str, error: BaseException) -> None:
        binding = registered_startup(guard)
        if binding is None or binding.owner() is not self:
            raise PermissionError("startup failure does not belong to the bound consumed guard")
        self.state = SupervisorState.FAILED
        self.started_monotonic_ns = binding.started_ns
        self.deadline_monotonic_ns = binding.started_ns + binding.limits.total_wall_ns
        if volume_preparation_entered(guard):
            try:
                abort = binding.controller.abort_startup(binding.invocation_id, binding.approval, phase, type(error).__name__)
                approved = binding.approval
                if (type(abort) is not StartupAbortReceipt
                        or abort.invocation_id != binding.invocation_id
                        or (abort.study_root_path, abort.ledger_path, abort.lock_path, abort.image_path) != (
                            approved.study_root_path, approved.budget_ledger_path, approved.lock_path, approved.study_image_path)
                        or any(getattr(abort, name) is not True for name in (
                            "mounts_detached", "partial_resources_quarantined", "failure_receipt_durable", "retry_forbidden"))
                        or type(abort.completed_monotonic_ns) is not int
                        or not binding.started_ns <= abort.completed_monotonic_ns <= self.deadline_monotonic_ns):
                    raise PermissionError("startup abort differs from the registered original controller binding")
            except BaseException as abort_error:
                raise PermissionError("startup abort lacks durable cleanup and no-retry proof") from abort_error

    def start(self) -> ImageVolumeReceipt:
        if self._budget_guard is not None:
            raise RuntimeError("bound lifecycle startup is owned only by BudgetGuard.start")
        if self.state is not SupervisorState.NEW:
            raise RuntimeError("Route 2 invocation startup may happen only once")
        self.state = SupervisorState.STARTING
        try:
            started = self.ops.first_monotonic_sample()
            if type(started) is not int or started <= 0:
                raise PermissionError("first monotonic sample is invalid")
            self.started_monotonic_ns = started
            self.deadline_monotonic_ns = started + self.limits.total_wall_ns

            self.approval.require_full_ab()
            self._require_approval_paths()

            self._startup_failure_phase = "startup_free_sample"
            sample = self.ops.sample_startup_free(self.invocation_id)
            self._require_startup_sample(sample)
            self.startup = sample

            self._startup_failure_phase = "one_shot_identity_lock"
            self._lock_attempted = True
            lock = self.ops.acquire_one_shot_lock(self.invocation_id, self.approval)
            self._require_lock(lock, sample)

            self._startup_failure_phase = "stage_a_image_create"
            volume = self.ops.create_stage_a_volume(self.invocation_id, self.approval, self.limits)
            self._require_volume(volume, sample, lock, self.limits.stage_a_disk_bytes)

            self.volume = volume
            self.frozen_rss_ceiling_bytes = min(
                self.limits.rss_cap_bytes,
                (3 * sample.available_ram_bytes) // 5,
            )
            if self.frozen_rss_ceiling_bytes <= 0:
                raise RuntimeError("frozen RSS ceiling is invalid")
            self.state = SupervisorState.STARTED
            return volume
        except BaseException as original_error:
            self.state = SupervisorState.FAILED
            if self._lock_attempted:
                try:
                    abort = self.ops.abort_startup(
                        self.invocation_id,
                        self.approval,
                        self._startup_failure_phase,
                        type(original_error).__name__,
                    )
                    self._require_startup_abort(abort)
                except BaseException as abort_error:
                    raise PermissionError("startup abort lacks durable cleanup and no-retry proof") from abort_error
            raise

    def _require_approval_paths(self) -> None:
        if (
            getattr(self.approval, "study_id", None) != STUDY_ID
            or getattr(self.approval, "scope", None) != "A+B"
            or getattr(self.approval, "approved", None) is not True
        ):
            raise PermissionError("a specific complete A+B approval is required")
        role_graph_sha256 = getattr(self.approval, "role_graph_sha256", None)
        if type(role_graph_sha256) is not str or not _SHA256.fullmatch(role_graph_sha256.lower()):
            raise PermissionError("approved frozen role graph identity must be an exact SHA-256")
        if not all(
            isinstance(getattr(self.approval, field, None), str)
            and getattr(self.approval, field).startswith("/")
            for field in ("study_root_path", "budget_ledger_path", "lock_path", "study_image_path")
        ):
            raise PermissionError("approved study paths must be exact absolute Linux paths")
        self._approved_role_graph_sha256 = role_graph_sha256.lower()

    def _require_startup_sample(self, sample: BackingFreeReceipt) -> None:
        started = self._required_start()
        required = self.limits.startup_free_disk_bytes
        if (
            sample.invocation_id != self.invocation_id
            or type(sample.sampled_monotonic_ns) is not int
            or not started <= sample.sampled_monotonic_ns
            or not all((sample.guest_mount_id, sample.guest_device, sample.windows_vhdx_path, sample.windows_volume_id))
            or any(
                type(value) is not int or value < 0
                for value in (sample.guest_free_bytes, sample.windows_free_bytes, sample.available_ram_bytes)
            )
            or sample.available_ram_bytes <= 0
        ):
            raise PermissionError("same-invocation two-layer backing identity/sample is incomplete")
        if min(sample.guest_free_bytes, sample.windows_free_bytes) < required:
            raise RuntimeError("two-layer pre-create free-space hard line is not met")
        if sample.nested_backing is not None:
            require_nested_backing_sample(sample.nested_backing,
                windows_vhdx_path=sample.windows_vhdx_path,windows_volume_id=sample.windows_volume_id,
                windows_free_bytes=sample.windows_free_bytes)
            if sample.nested_backing.carrier_free_bytes < sample.nested_backing.carrier_min_free_bytes:
                raise RuntimeError("separate precreate carrier reserve is not met")

    def _require_lock(self, lock: OneShotLockReceipt, sample: BackingFreeReceipt) -> None:
        if (
            lock.invocation_id != self.invocation_id
            or lock.study_id != STUDY_ID
            or lock.lock_path != self.approval.lock_path
            or lock.exclusive_create is not True
            or type(lock.created_monotonic_ns) is not int
            or lock.created_monotonic_ns < sample.sampled_monotonic_ns
        ):
            raise PermissionError("one-shot identity lock is absent, reused or outside the approved invocation")

    def _require_startup_abort(self, receipt: StartupAbortReceipt) -> None:
        started = self._required_start()
        deadline = self._required_deadline()
        sampled = self.startup.sampled_monotonic_ns if self.startup is not None else started
        if (
            receipt.invocation_id != self.invocation_id
            or receipt.study_root_path != self.approval.study_root_path
            or receipt.ledger_path != self.approval.budget_ledger_path
            or receipt.lock_path != self.approval.lock_path
            or receipt.image_path != self.approval.study_image_path
            or receipt.mounts_detached is not True
            or receipt.partial_resources_quarantined is not True
            or receipt.failure_receipt_durable is not True
            or receipt.retry_forbidden is not True
            or type(receipt.completed_monotonic_ns) is not int
            or not sampled <= receipt.completed_monotonic_ns
            or not started <= receipt.completed_monotonic_ns <= deadline
        ):
            raise PermissionError("startup abort did not durably detach, quarantine and prohibit retry")

    def _require_volume(
        self,
        volume: ImageVolumeReceipt,
        sample: BackingFreeReceipt,
        lock: OneShotLockReceipt,
        maximum_capacity_bytes: int,
    ) -> None:
        started = self._required_start()
        identities = (
            volume.loop_device,
            volume.filesystem_uuid,
            volume.mount_id,
            volume.filesystem_device,
        )
        numbers = (
            volume.image_device,
            volume.image_inode,
            volume.filesystem_capacity_bytes,
            volume.image_length_bytes,
            volume.created_monotonic_ns,
        )
        if (
            volume.invocation_id != self.invocation_id
            or volume.study_id != STUDY_ID
            or volume.study_root_path != self.approval.study_root_path
            or volume.ledger_path != self.approval.budget_ledger_path
            or volume.lock_path != self.approval.lock_path
            or volume.image_path != self.approval.study_image_path
            or not all(identities)
            or any(type(value) is not int or value <= 0 for value in numbers)
            or not started <= sample.sampled_monotonic_ns < volume.created_monotonic_ns
            or lock.created_monotonic_ns > volume.created_monotonic_ns
            or volume.filesystem_capacity_bytes > maximum_capacity_bytes
            or volume.image_length_bytes > maximum_capacity_bytes
        ):
            raise PermissionError("image creation is not bound to the pre-create gate and approved volume identity")

    def finish_stage_a(self) -> StageABoundaryReceipt:
        if self._budget_guard is not None:
            raise PermissionError("bound phase writes are owned only by BudgetGuard")
        if self.state is not SupervisorState.STARTED:
            raise RuntimeError("Stage A boundary requires one started invocation")
        try:
            receipt = self.ops.read_stage_a_boundary(self.invocation_id)
            started = self._required_start()
            if (
                receipt.invocation_id != self.invocation_id
                or type(receipt.reference_roles) is not int
                or receipt.reference_roles != 105
                or type(receipt.treatment_roles) is not int
                or receipt.treatment_roles != 105
                or type(receipt.different_treatment_roles) is not int
                or not 0 <= receipt.different_treatment_roles <= 105
                or type(receipt.stage_a_disk_bytes) is not int
                or not 0 <= receipt.stage_a_disk_bytes <= self.limits.stage_a_disk_bytes
                or type(receipt.finished_monotonic_ns) is not int
                or receipt.finished_monotonic_ns < started
                or type(receipt.fsynced_monotonic_ns) is not int
                or receipt.fsynced_monotonic_ns < receipt.finished_monotonic_ns
                or not _SHA256.fullmatch(receipt.event_sha256)
                or receipt.durable is not True
            ):
                raise PermissionError("Stage A boundary is incomplete or not durably frozen")
            self.stage_a = receipt
            if receipt.fsynced_monotonic_ns > started + self.limits.stage_a_wall_ns:
                raise PermissionError("Stage A boundary fsync exceeded the Stage A wall deadline")
            self.state = SupervisorState.STAGE_A_FINISHED
            return receipt
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def enter_stage_b(self, projection: StageBProjection) -> ImageVolumeReceipt:
        if self._budget_guard is not None:
            raise PermissionError("bound phase writes are owned only by BudgetGuard")
        if self.state is not SupervisorState.STAGE_A_FINISHED or self.stage_a is None or self.volume is None:
            raise RuntimeError("Stage B requires a durable complete Stage A boundary")
        if self.stage_a.different_treatment_roles == 0:
            raise PermissionError("identical treatment roles stop before Stage B")
        try:
            require_exact_stage_b_projection(projection)
            if self._approved_role_graph_sha256 is None:
                raise PermissionError("external frozen admission role graph pin is unavailable")
            _require_external_role_graph_binding(
                asdict(projection), self._approved_role_graph_sha256,
            )
            projection.call_role_ids_by_kind()
            if projection.stage_a_disk_bytes_d_a != self.stage_a.stage_a_disk_bytes:
                raise PermissionError("D_A differs from the durable Stage A disk observation")
            if self.frozen_rss_ceiling_bytes is None:
                raise RuntimeError("frozen RSS ceiling is unavailable")
            require_stage_b_entry(
                projection,
                limits=self.limits,
                frozen_rss_ceiling_bytes=self.frozen_rss_ceiling_bytes,
                stage_a_hard_lines_met=True,
            )
            entry = self.ops.append_stage_b_entry(self.invocation_id, projection)
            if (
                entry.invocation_id != self.invocation_id
                or not _SHA256.fullmatch(entry.event_sha256)
                or entry.durable is not True
                or type(entry.fsynced_monotonic_ns) is not int
                or entry.fsynced_monotonic_ns < self.stage_a.fsynced_monotonic_ns
            ):
                raise PermissionError("Stage B entry is not durably committed before expansion")
            self.stage_b_entry = entry
            self._stage_b_projection = projection
            if (
                entry.fsynced_monotonic_ns > self._required_start() + self.limits.stage_a_wall_ns
                or entry.fsynced_monotonic_ns > self._required_deadline()
            ):
                raise PermissionError("Stage B entry fsync exceeded its wall deadline")

            expanded = self.ops.expand_same_volume(
                self.invocation_id, self.volume, entry.event_sha256, self.limits,
            )
            self._require_same_expanded_volume(expanded, self.volume, entry)
            expansion = self.ops.append_expansion_receipt(
                self.invocation_id, entry.event_sha256, expanded,
            )
            if (
                expansion.invocation_id != self.invocation_id
                or not _SHA256.fullmatch(expansion.event_sha256)
                or expansion.durable is not True
                or type(expansion.fsynced_monotonic_ns) is not int
                or expansion.fsynced_monotonic_ns < expanded.created_monotonic_ns
                or expansion.fsynced_monotonic_ns < entry.fsynced_monotonic_ns
            ):
                raise PermissionError("same-volume expansion receipt is not durable")
            self.volume = expanded
            self.expansion_receipt = expansion
            if expansion.fsynced_monotonic_ns > self._required_deadline():
                raise PermissionError("Stage B expansion receipt fsync exceeded the total wall deadline")
            self.state = SupervisorState.STAGE_B_READY
            return expanded
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def finish_stage_b(self) -> StageBExecutionReceipt:
        if self._budget_guard is not None:
            raise PermissionError("bound phase writes are owned only by BudgetGuard")
        if self.state is not SupervisorState.STAGE_B_READY or self.expansion_receipt is None:
            raise RuntimeError("Stage B completion requires a durably expanded Stage B volume")
        try:
            receipt = self.ops.read_stage_b_completion(self.invocation_id)
            counts = (
                receipt.inner_roles_completed,
                receipt.outer_roles_completed,
                receipt.verifier_fit_calls,
                receipt.verifier_predict_calls,
                receipt.decoder_calls,
                receipt.evaluator_calls,
                receipt.pooled_aggregation_calls,
                receipt.pooled_gt_reads,
                receipt.call_event_count,
            )
            if (
                receipt.invocation_id != self.invocation_id
                or any(type(value) is not int for value in counts)
                or counts != (20, 5, 25, 25, 65, 20, 1, 0, 408)
                or receipt.pooled_aggregation_completed is not True
                or type(receipt.finished_monotonic_ns) is not int
                or receipt.finished_monotonic_ns < self.expansion_receipt.fsynced_monotonic_ns
                or type(receipt.fsynced_monotonic_ns) is not int
                or receipt.fsynced_monotonic_ns < receipt.finished_monotonic_ns
                or not _SHA256.fullmatch(receipt.event_sha256)
                or not _SHA256.fullmatch(receipt.result_sha256)
                or not _SHA256.fullmatch(receipt.call_event_accounting_sha256)
                or receipt.durable is not True
            ):
                raise PermissionError("Stage B execution, fixed call quotas or pooled no-GT receipt is incomplete")
            self.stage_b_completion = receipt
            if (
                receipt.finished_monotonic_ns > self._required_deadline()
                or receipt.fsynced_monotonic_ns > self._required_deadline()
            ):
                raise PermissionError("Stage B completion exceeded the total wall deadline")
            self.state = SupervisorState.STAGE_B_FINISHED
            return receipt
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def _require_same_expanded_volume(
        self,
        expanded: ImageVolumeReceipt,
        original: ImageVolumeReceipt,
        entry: DurableLedgerReceipt,
    ) -> None:
        if type(expanded) is not ImageVolumeReceipt:
            raise PermissionError("Stage B expansion requires the exact reviewed image-volume receipt type")
        numeric_fields = (
            expanded.created_monotonic_ns,
            expanded.image_device,
            expanded.image_inode,
            expanded.filesystem_capacity_bytes,
            expanded.image_length_bytes,
        )
        if any(type(value) is not int for value in numeric_fields):
            raise PermissionError("Stage B expansion numeric receipt fields must be exact integers")
        frozen = (
            original.invocation_id,
            original.study_id,
            original.study_root_path,
            original.ledger_path,
            original.lock_path,
            original.image_path,
            original.image_device,
            original.image_inode,
            original.loop_device,
            original.filesystem_uuid,
            original.mount_id,
            original.filesystem_device,
        )
        observed = (
            expanded.invocation_id,
            expanded.study_id,
            expanded.study_root_path,
            expanded.ledger_path,
            expanded.lock_path,
            expanded.image_path,
            expanded.image_device,
            expanded.image_inode,
            expanded.loop_device,
            expanded.filesystem_uuid,
            expanded.mount_id,
            expanded.filesystem_device,
        )
        if (
            observed != frozen
            or type(expanded.created_monotonic_ns) is not int
            or expanded.created_monotonic_ns <= entry.fsynced_monotonic_ns
            or expanded.image_length_bytes != self.limits.total_disk_bytes
            or expanded.filesystem_capacity_bytes <= self.limits.stage_a_disk_bytes
            or expanded.filesystem_capacity_bytes > self.limits.total_disk_bytes
        ):
            raise PermissionError("Stage B expansion changed identity or exceeded the approved image and filesystem bounds")

    def finalize(self, status: str, *, evidence: Mapping[str, object]) -> TerminalAcceptance:
        if self._budget_guard is not None:
            raise PermissionError("bound terminal writes are owned only by BudgetGuard; external acceptance is still required")
        if self._terminal_attempted:
            raise RuntimeError("terminal close is one-shot and has already been attempted")
        if self.state in {
            SupervisorState.NEW,
            SupervisorState.STARTING,
            SupervisorState.TERMINAL_PENDING,
            SupervisorState.ACCEPTED,
        }:
            raise RuntimeError("terminal acceptance requires a started, unfinished invocation")
        if self.volume is None:
            raise RuntimeError("no volume exists to finalize")
        if status not in {item.value for item in StudyStatus}:
            raise ValueError("unknown Route 2 terminal status")
        if self.state is SupervisorState.FAILED:
            status = StudyStatus.INCOMPLETE_RESOURCE.value
        if status == StudyStatus.COMPLETE.value and (
            self.state is not SupervisorState.STAGE_B_FINISHED
            or self.stage_b_completion is None
        ):
            raise PermissionError("COMPLETE requires a durable complete Stage B execution receipt")
        if not isinstance(evidence, Mapping):
            raise TypeError("terminal evidence must be a mapping")
        chain = {
            "study_id": STUDY_ID,
            "invocation_id": self.invocation_id,
            "role_graph_sha256": self._approved_role_graph_sha256,
            "stage_a_event_sha256": self.stage_a.event_sha256 if self.stage_a is not None else None,
            "stage_a_finished_monotonic_ns": (
                self.stage_a.finished_monotonic_ns if self.stage_a is not None else None
            ),
            "stage_a_fsynced_monotonic_ns": (
                self.stage_a.fsynced_monotonic_ns if self.stage_a is not None else None
            ),
            "stage_b_entry_event_sha256": self.stage_b_entry.event_sha256 if self.stage_b_entry is not None else None,
            "stage_b_entry_fsynced_monotonic_ns": (
                self.stage_b_entry.fsynced_monotonic_ns if self.stage_b_entry is not None else None
            ),
            "stage_b_expansion_event_sha256": (
                self.expansion_receipt.event_sha256 if self.expansion_receipt is not None else None
            ),
            "stage_b_expansion_fsynced_monotonic_ns": (
                self.expansion_receipt.fsynced_monotonic_ns if self.expansion_receipt is not None else None
            ),
            "stage_b_completion_event_sha256": (
                self.stage_b_completion.event_sha256 if self.stage_b_completion is not None else None
            ),
            "stage_b_completion_finished_monotonic_ns": (
                self.stage_b_completion.finished_monotonic_ns if self.stage_b_completion is not None else None
            ),
            "stage_b_completion_fsynced_monotonic_ns": (
                self.stage_b_completion.fsynced_monotonic_ns if self.stage_b_completion is not None else None
            ),
            "stage_b_call_event_count": (
                self.stage_b_completion.call_event_count if self.stage_b_completion is not None else None
            ),
            "stage_b_call_event_accounting_sha256": (
                self.stage_b_completion.call_event_accounting_sha256 if self.stage_b_completion is not None else None
            ),
            "stage_b_result_sha256": (
                self.stage_b_completion.result_sha256 if self.stage_b_completion is not None else None
            ),
        }
        chain_sha256 = hashlib.sha256(_canonical_json_bytes(chain)).hexdigest()
        terminal_evidence = dict(evidence)
        if (
            ("route2_supervisor_chain" in terminal_evidence and terminal_evidence["route2_supervisor_chain"] != chain)
            or (
                "route2_supervisor_chain_sha256" in terminal_evidence
                and terminal_evidence["route2_supervisor_chain_sha256"] != chain_sha256
            )
        ):
            raise PermissionError("caller terminal evidence conflicts with the supervisor binding")
        terminal_evidence["route2_supervisor_chain"] = chain
        terminal_evidence["route2_supervisor_chain_sha256"] = chain_sha256
        try:
            _canonical_json_bytes(terminal_evidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("terminal evidence must be finite canonical JSON") from exc
        if status == StudyStatus.COMPLETE.value:
            stage_b_result = evidence.get("stage_b_result")
            if not isinstance(stage_b_result, Mapping) or hashlib.sha256(
                _canonical_json_bytes(dict(stage_b_result))
            ).hexdigest() != chain["stage_b_result_sha256"]:
                raise PermissionError("terminal evidence does not contain the exact durably completed Stage B result")
        expected_stage_payloads = self._expected_stage_payloads()
        self.state = SupervisorState.TERMINAL_PENDING
        # The first close call may have durably written before raising.  Treat
        # every attempt as one-shot so recovery cannot append a second terminal.
        self._terminal_attempted = True
        try:
            started = self._required_start()
            deadline = self._required_deadline()
            terminal = self.ops.close_terminal(
                self.invocation_id, status, terminal_evidence, started, deadline,
            )
            if (
                terminal.invocation_id != self.invocation_id
                or terminal.status != status
                or not _SHA256.fullmatch(terminal.terminal_sha256)
                or terminal.terminal_binding_sha256 != chain_sha256
                or terminal.invocation_started_monotonic_ns != started
                or terminal.deadline_monotonic_ns != deadline
                or type(terminal.terminal_closed_monotonic_ns) is not int
                or terminal.terminal_closed_monotonic_ns < started
                or (
                    status != StudyStatus.INCOMPLETE_RESOURCE.value
                    and terminal.terminal_closed_monotonic_ns > deadline
                )
                or terminal.ledger_fsynced is not True
                or terminal.ledger_closed is not True
                or terminal.no_active_gt_view is not True
                or terminal.no_active_worker is not True
                or not terminal.unit_name
            ):
                raise PermissionError("terminal ledger close or process/GT teardown proof is incomplete")
            self._verify_terminal_record(
                terminal,
                status,
                terminal_evidence,
                chain_sha256,
                expected_stage_payloads,
                started,
                started + self.limits.stage_a_wall_ns,
                deadline,
                expected_role_graph_sha256=self._approved_role_graph_sha256,
            )
            self._terminal = terminal

            observation = self.ops.observe_exit_and_persist_wall_receipt(terminal)
            if (
                observation.invocation_id != self.invocation_id
                or observation.unit_name != terminal.unit_name
                or observation.unit_inactive is not True
                or observation.cgroup_empty is not True
                or observation.terminal_reverified is not True
                or observation.external_receipt_durable is not True
                or observation.qpc_frequency != self.qpc_frequency
                or observation.external_started_ticks != self.external_started_ticks
            ):
                raise PermissionError("post-terminal service, receipt durability or external clock identity is unproven")
            verify_post_exit_receipt(
                observation.receipt,
                invocation_id=self.invocation_id,
                unit_name=terminal.unit_name,
                terminal_sha256=terminal.terminal_sha256,
                observed_monotonic_ns=observation.observed_monotonic_ns,
                observed_external_ticks=observation.observed_external_ticks,
                total_wall_ns=self.limits.total_wall_ns,
                terminal_status=status,
                expected_qpc_frequency=self.qpc_frequency,
                expected_external_started_ticks=self.external_started_ticks,
            )
            self.state = SupervisorState.ACCEPTED
            return TerminalAcceptance(
                invocation_id=self.invocation_id,
                status=status,
                terminal_sha256=terminal.terminal_sha256,
                accepted=True,
            )
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def _expected_stage_payloads(self) -> dict[str, dict[str, object]]:
        payloads: dict[str, dict[str, object]] = {}
        if self.stage_a is not None:
            payloads["stage_a_finished"] = {
                "invocation_id": self.stage_a.invocation_id,
                "reference_roles": self.stage_a.reference_roles,
                "treatment_roles": self.stage_a.treatment_roles,
                "different_treatment_roles": self.stage_a.different_treatment_roles,
                "stage_a_disk_bytes": self.stage_a.stage_a_disk_bytes,
                "finished_monotonic_ns": self.stage_a.finished_monotonic_ns,
            }
        if self.stage_b_entry is not None:
            if self._stage_b_projection is None:
                raise PermissionError("durable Stage B entry has no frozen projection")
            payloads["stage_b_entry_passed"] = {
                "invocation_id": self.invocation_id,
                "projection": json.loads(_canonical_json_bytes(asdict(self._stage_b_projection))),
            }
        if self.expansion_receipt is not None:
            if self.stage_b_entry is None or self.volume is None:
                raise PermissionError("expansion receipt lacks its entry or expanded volume")
            payloads["stage_b_volume_expanded"] = {
                "invocation_id": self.invocation_id,
                "entry_event_sha256": self.stage_b_entry.event_sha256,
                "volume": asdict(self.volume),
            }
        if self.stage_b_completion is not None:
            item = self.stage_b_completion
            payloads["stage_b_complete"] = {
                "invocation_id": item.invocation_id,
                "inner_roles_completed": item.inner_roles_completed,
                "outer_roles_completed": item.outer_roles_completed,
                "verifier_fit_calls": item.verifier_fit_calls,
                "verifier_predict_calls": item.verifier_predict_calls,
                "decoder_calls": item.decoder_calls,
                "evaluator_calls": item.evaluator_calls,
                "pooled_aggregation_calls": item.pooled_aggregation_calls,
                "pooled_aggregation_completed": item.pooled_aggregation_completed,
                "pooled_gt_reads": item.pooled_gt_reads,
                "call_event_count": item.call_event_count,
                "call_event_accounting_sha256": item.call_event_accounting_sha256,
                "finished_monotonic_ns": item.finished_monotonic_ns,
                "result_sha256": item.result_sha256,
            }
        return payloads

    @staticmethod
    def _verify_terminal_record(
        terminal: TerminalCloseReceipt,
        status: str,
        expected_evidence: Mapping[str, object],
        expected_chain_sha256: str,
        expected_stage_payloads: Mapping[str, Mapping[str, object]],
        started_monotonic_ns: int,
        stage_a_deadline_monotonic_ns: int,
        deadline_monotonic_ns: int,
        expected_role_graph_sha256: str,
    ) -> None:
        """Bind the terminal digest to canonical bytes containing the supervisor chain.

        ``terminal_record_bytes`` must be read back from the closed ledger by
        the trusted backend.  The coordinator independently checks the record
        envelope, payload, chain digest and append-only ledger event digest.
        """
        if (
            type(expected_role_graph_sha256) is not str
            or not _SHA256.fullmatch(expected_role_graph_sha256)
        ):
            raise PermissionError("approved external frozen admission role graph pin is absent or malformed")
        ledger = terminal.ledger_bytes
        if type(ledger) is not bytes or not ledger.endswith(b"\n"):
            raise PermissionError("terminal ledger bytes are absent or not fully closed")
        records = ledger.splitlines(keepends=True)
        if not records or any(not line.endswith(b"\n") or line == b"\n" for line in records):
            raise PermissionError("terminal ledger has an incomplete or empty record")
        if type(terminal.terminal_record_bytes) is not bytes or terminal.terminal_record_bytes != records[-1]:
            raise PermissionError("terminal bytes differ from the final closed ledger record")

        previous = "0" * 64
        event_hashes: dict[str, dict[str, object]] = {}
        terminal_decoded: dict[str, object] | None = None
        for index, raw in enumerate(records):
            try:
                decoded = json.loads(raw[:-1].decode("utf-8"), parse_constant=_reject_json_constant)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise PermissionError("terminal ledger contains invalid UTF-8 JSON") from exc
            if not isinstance(decoded, dict) or set(decoded) != {"entry", "sha256"}:
                raise PermissionError("terminal ledger record has an unknown envelope")
            try:
                canonical_record = _canonical_json_bytes(decoded) + b"\n"
            except (TypeError, ValueError) as exc:
                raise PermissionError("terminal ledger contains nonstandard JSON values") from exc
            if canonical_record != raw:
                raise PermissionError("terminal ledger contains noncanonical serialization")
            entry = decoded.get("entry")
            if (
                not isinstance(entry, dict)
                or set(entry) != {"seq", "event", "payload", "previous_sha256"}
                or type(entry.get("seq")) is not int
                or entry["seq"] != index
                or entry.get("previous_sha256") != previous
                or not isinstance(entry.get("event"), str)
                or not entry["event"]
                or not isinstance(entry.get("payload"), dict)
            ):
                raise PermissionError("terminal ledger chain sequence or predecessor is invalid")
            event_sha256 = hashlib.sha256(_canonical_json_bytes(entry)).hexdigest()
            if decoded.get("sha256") != event_sha256:
                raise PermissionError("terminal ledger chain event digest is invalid")
            if entry["event"] == "terminal":
                if index != len(records) - 1:
                    raise PermissionError("terminal ledger event is not the final event")
                terminal_decoded = decoded
            event_hashes[event_sha256] = entry
            previous = event_sha256

        if terminal_decoded is None:
            raise PermissionError("terminal ledger has no final terminal event")
        entry = terminal_decoded["entry"]
        payload = entry["payload"]
        if not isinstance(entry, dict) or not isinstance(payload, dict):
            raise PermissionError("terminal ledger final event is malformed")
        try:
            evidence_matches = (
                isinstance(payload.get("evidence"), dict)
                and _canonical_json_bytes(payload["evidence"])
                == _canonical_json_bytes(dict(expected_evidence))
            )
        except (TypeError, ValueError) as exc:
            raise PermissionError("terminal evidence cannot be compared as canonical JSON") from exc
        if (
            set(payload) != {"status", "evidence", "wall_ns", "monotonic_ns", "epoch_ns"}
            or payload.get("status") != status
            or not evidence_matches
            or type(payload.get("wall_ns")) is not int
            or payload["wall_ns"] < 0
            or type(payload.get("monotonic_ns")) is not int
            or not started_monotonic_ns <= payload["monotonic_ns"] <= terminal.terminal_closed_monotonic_ns
            or payload["wall_ns"] != payload["monotonic_ns"] - started_monotonic_ns
            or type(payload.get("epoch_ns")) is not int
            or payload["epoch_ns"] <= 0
            or (
                status != StudyStatus.INCOMPLETE_RESOURCE.value
                and terminal.terminal_closed_monotonic_ns > deadline_monotonic_ns
            )
            or payload.get("evidence", {}).get("route2_supervisor_chain_sha256") != expected_chain_sha256
        ):
            raise PermissionError("terminal bytes do not contain the expected status, chain, wall duration and monotonic timestamp")
        invocation_events = [
            event for event in event_hashes.values()
            if event.get("event") == "invocation_started"
        ]
        chain = expected_evidence.get("route2_supervisor_chain")
        if not isinstance(chain, Mapping):
            raise PermissionError("terminal supervisor chain is missing")
        if chain.get("role_graph_sha256") != expected_role_graph_sha256:
            raise PermissionError("terminal supervisor chain role graph differs from the approved external frozen admission")
        external_role_graph_sha256 = expected_role_graph_sha256
        if (
            len(invocation_events) != 1
            or invocation_events[0].get("payload", {}).get("invocation_id") != chain.get("invocation_id")
            or invocation_events[0].get("payload", {}).get("monotonic_ns") != started_monotonic_ns
            or chain.get("study_id") != STUDY_ID
            or chain.get("invocation_id") != terminal.invocation_id
        ):
            raise PermissionError("terminal ledger chain is not bound to the started invocation")
        named_events = {
            "stage_a_event_sha256": "stage_a_finished",
            "stage_b_entry_event_sha256": "stage_b_entry_passed",
            "stage_b_expansion_event_sha256": "stage_b_volume_expanded",
            "stage_b_completion_event_sha256": "stage_b_complete",
        }
        stage_event_records = {
            event_name: [
                (digest, event)
                for digest, event in event_hashes.items()
                if event.get("event") == event_name
            ]
            for event_name in named_events.values()
        }
        stage_event_counts = {
            name: len(records)
            for name, records in stage_event_records.items()
        }
        if any(count > 1 for count in stage_event_counts.values()):
            raise PermissionError("terminal ledger has a duplicate stage event")
        if status == StudyStatus.COMPLETE.value and any(count != 1 for count in stage_event_counts.values()):
            raise PermissionError("COMPLETE requires exactly one event for each Stage A/B boundary")
        if set(expected_stage_payloads) != {
            name for name, count in stage_event_counts.items() if count == 1
        }:
            raise PermissionError("terminal ledger stage path differs from the accepted receipts")

        def reject_nonterminal_after(boundary_event: Mapping[str, object], message: str) -> None:
            boundary_sequence = boundary_event.get("seq")
            if type(boundary_sequence) is not int or any(
                event.get("event") != "terminal"
                and type(event.get("seq")) is int
                and event["seq"] > boundary_sequence
                for event in event_hashes.values()
            ):
                raise PermissionError(message)

        previous_sequence = -1
        latest_stage_monotonic_ns = started_monotonic_ns
        for field, event_name in named_events.items():
            digest = chain.get(field)
            records = stage_event_records[event_name]
            if (digest is None) != (len(records) == 0):
                raise PermissionError("terminal ledger stage event does not exactly match accepted receipt references")
            if digest is not None:
                if (
                    not isinstance(digest, str)
                    or not _SHA256.fullmatch(digest)
                    or len(records) != 1
                    or records[0][0] != digest
                ):
                    raise PermissionError("terminal ledger chain omits a bound Stage A/B event")
                event = records[0][1]
                if (
                    event.get("event") != event_name
                    or event.get("seq", -1) <= previous_sequence
                ):
                    raise PermissionError("terminal ledger chain omits a bound Stage A/B event")
                previous_sequence = event["seq"]
                expected_payload = expected_stage_payloads.get(event_name)
                try:
                    payload_matches = (
                        isinstance(event.get("payload"), Mapping)
                        and expected_payload is not None
                        and _canonical_json_bytes(dict(event["payload"]))
                        == _canonical_json_bytes(dict(expected_payload))
                    )
                except (TypeError, ValueError) as exc:
                    raise PermissionError("terminal stage receipt payload is not canonical JSON") from exc
                if not payload_matches:
                    raise PermissionError("terminal ledger stage event differs from its accepted receipt payload")
                timestamp_key = {
                    "stage_a_finished": "stage_a_finished_monotonic_ns",
                    "stage_b_entry_passed": "stage_b_entry_fsynced_monotonic_ns",
                    "stage_b_volume_expanded": "stage_b_expansion_fsynced_monotonic_ns",
                    "stage_b_complete": "stage_b_completion_finished_monotonic_ns",
                }[event_name]
                event_timestamp = chain.get(timestamp_key)
                if type(event_timestamp) is not int:
                    raise PermissionError("terminal ledger stage event lacks its monotonic receipt time")
                if event_name in {"stage_a_finished", "stage_b_complete"}:
                    event_time_key = "finished_monotonic_ns"
                    if expected_payload is None or expected_payload.get(event_time_key) != event_timestamp:
                        raise PermissionError("terminal ledger stage timestamp differs from its receipt chain")
                    if event_name == "stage_a_finished":
                        fsynced_ns = chain.get("stage_a_fsynced_monotonic_ns")
                        stage_b_events = (
                            chain.get("stage_b_entry_event_sha256"),
                            chain.get("stage_b_expansion_event_sha256"),
                            chain.get("stage_b_completion_event_sha256"),
                        )
                        if (
                            type(fsynced_ns) is not int
                            or fsynced_ns < event_timestamp
                            or (
                                (event_timestamp > stage_a_deadline_monotonic_ns
                                 or fsynced_ns > stage_a_deadline_monotonic_ns)
                                and (
                                    status != StudyStatus.INCOMPLETE_RESOURCE.value
                                    or any(item is not None for item in stage_b_events)
                                )
                            )
                        ):
                            raise PermissionError("Stage A boundary is late or precedes its finished receipt")
                        if (
                            event_timestamp > stage_a_deadline_monotonic_ns
                            or fsynced_ns > stage_a_deadline_monotonic_ns
                        ):
                            reject_nonterminal_after(
                                event,
                                "nonterminal work event follows late Stage A boundary",
                            )
                        latest_stage_monotonic_ns = max(latest_stage_monotonic_ns, fsynced_ns)
                    else:
                        fsynced_ns = chain.get("stage_b_completion_fsynced_monotonic_ns")
                        if (
                            type(fsynced_ns) is not int
                            or fsynced_ns < event_timestamp
                            or (
                                (event_timestamp > deadline_monotonic_ns
                                 or fsynced_ns > deadline_monotonic_ns)
                                and status != StudyStatus.INCOMPLETE_RESOURCE.value
                            )
                        ):
                            raise PermissionError("Stage B completion fsync is late or precedes its finished receipt")
                        latest_stage_monotonic_ns = max(latest_stage_monotonic_ns, fsynced_ns)
                elif event_name == "stage_b_entry_passed":
                    stage_a_fsynced_ns = chain.get("stage_a_fsynced_monotonic_ns")
                    later_events = (
                        chain.get("stage_b_expansion_event_sha256"),
                        chain.get("stage_b_completion_event_sha256"),
                    )
                    if (
                        type(stage_a_fsynced_ns) is not int
                        or event_timestamp < stage_a_fsynced_ns
                        or (
                            (event_timestamp > stage_a_deadline_monotonic_ns
                             or event_timestamp > deadline_monotonic_ns)
                            and (
                                status != StudyStatus.INCOMPLETE_RESOURCE.value
                                or any(item is not None for item in later_events)
                            )
                        )
                    ):
                        raise PermissionError("Stage B entry fsync is outside the durable Stage A deadline")
                    if (
                        event_timestamp > stage_a_deadline_monotonic_ns
                        or event_timestamp > deadline_monotonic_ns
                    ):
                        reject_nonterminal_after(
                            event,
                            "nonterminal work event follows late Stage B entry",
                        )
                elif event_name == "stage_b_volume_expanded":
                    volume_payload = expected_payload.get("volume") if expected_payload is not None else None
                    entry_fsynced_ns = chain.get("stage_b_entry_fsynced_monotonic_ns")
                    if (
                        not isinstance(volume_payload, Mapping)
                        or type(volume_payload.get("created_monotonic_ns")) is not int
                        or type(entry_fsynced_ns) is not int
                        or event_timestamp < entry_fsynced_ns
                        or event_timestamp < volume_payload["created_monotonic_ns"]
                        or (
                            event_timestamp > deadline_monotonic_ns
                            and (
                                status != StudyStatus.INCOMPLETE_RESOURCE.value
                                or chain.get("stage_b_completion_event_sha256") is not None
                            )
                        )
                    ):
                        raise PermissionError("expansion fsync time precedes the committed volume expansion")
                    if event_timestamp > deadline_monotonic_ns:
                        reject_nonterminal_after(
                            event,
                            "nonterminal work event follows late Stage B expansion",
                        )
                latest_stage_monotonic_ns = max(latest_stage_monotonic_ns, event_timestamp)
        completion_hash = chain.get("stage_b_completion_event_sha256")
        if completion_hash is not None:
            completion_event = event_hashes[completion_hash]
            reject_nonterminal_after(
                completion_event,
                "work event follows Stage B completion",
            )
            completion_payload = event_hashes[completion_hash].get("payload", {})
            completion_sequence = completion_event.get("seq")
            if type(completion_sequence) is not int:
                raise PermissionError("Stage B completion event lacks an ordered ledger position")
            prior_events = sorted(
                (event for event in event_hashes.values() if event.get("seq", -1) < completion_sequence),
                key=lambda event: event["seq"],
            )
            prior_tail_sha256 = (
                next(
                    digest for digest, event in event_hashes.items()
                    if event.get("seq") == completion_sequence - 1
                )
                if completion_sequence > 0
                else "0" * 64
            )
            prior_payloads = ((event["event"], event["payload"]) for event in prior_events)
            prior_payloads = tuple(prior_payloads)
            stage_b_entries = [payload for name, payload in prior_payloads if name == "stage_b_entry_passed"]
            if len(stage_b_entries) != 1 or not isinstance(stage_b_entries[0].get("projection"), Mapping):
                raise PermissionError("terminal call replay lacks the unique frozen Stage B role graph")
            role_graph_pin = _require_external_role_graph_binding(
                stage_b_entries[0]["projection"], external_role_graph_sha256,
            )
            role_graph_sha256, expected_role_ids_by_kind, expected_fit_training_roles = _projection_call_role_ids(
                stage_b_entries[0]["projection"],
            )
            if role_graph_sha256.lower() != role_graph_pin:
                raise PermissionError("terminal call role graph differs from the external frozen admission")
            replayed_calls = _replay_call_event_accounting(
                prior_payloads,
                ledger_tail_sha256=prior_tail_sha256,
                expected_role_ids_by_kind=expected_role_ids_by_kind,
                expected_role_graph_sha256=role_graph_pin,
                expected_fit_training_roles_by_verifier=expected_fit_training_roles,
            )
            if (
                not isinstance(completion_payload, Mapping)
                or completion_payload.get("call_event_count") != replayed_calls["call_event_count"]
                or completion_payload.get("call_event_accounting_sha256")
                != replayed_calls["call_event_accounting_sha256"]
                or chain.get("stage_b_call_event_count") != replayed_calls["call_event_count"]
                or chain.get("stage_b_call_event_accounting_sha256")
                != replayed_calls["call_event_accounting_sha256"]
            ):
                raise PermissionError("Stage B completion does not match replayed durable call events")
            if completion_payload.get("result_sha256") != chain.get("stage_b_result_sha256"):
                raise PermissionError("terminal ledger chain does not bind the Stage B result hash")
            stage_b_result = expected_evidence.get("stage_b_result")
            if (
                not isinstance(stage_b_result, Mapping)
                or hashlib.sha256(_canonical_json_bytes(dict(stage_b_result))).hexdigest()
                != chain.get("stage_b_result_sha256")
            ):
                raise PermissionError("terminal ledger evidence result differs from its durable completion hash")
            if _canonical_json_bytes(stage_b_result.get("fit_provenance")) != _canonical_json_bytes(
                replayed_calls["fit_provenance"]
            ):
                raise PermissionError("terminal Stage B result differs from durable fit provenance events")
            frozen_outer_ids = tuple(
                role_id.split("/")[1]
                for role_id in expected_role_ids_by_kind["verifier_predict"]
                if len(role_id.split("/")) == 3 and role_id.endswith("/outer")
            )
            selected_thresholds = stage_b_result.get("selected_thresholds")
            if (
                not isinstance(selected_thresholds, (list, tuple))
                or tuple(item[0] for item in selected_thresholds if isinstance(item, (list, tuple)) and len(item) == 2)
                != frozen_outer_ids
                or len(selected_thresholds) != len(frozen_outer_ids)
            ):
                raise PermissionError("terminal Stage B outer results differ from the frozen role graph schedule")
        elif any(
            chain.get(field) is not None
            for field in (
                "stage_b_call_event_count",
                "stage_b_call_event_accounting_sha256",
                "stage_b_result_sha256",
            )
        ):
            raise PermissionError("terminal ledger chain includes an uncommitted Stage B result hash")
        if payload.get("monotonic_ns", 0) < latest_stage_monotonic_ns:
            raise PermissionError("terminal record monotonic timestamp precedes the last stage completion")
        event_sha256 = terminal_decoded["sha256"]
        if (
            terminal_decoded.get("sha256") != event_sha256
            or terminal.terminal_sha256 != event_sha256
            or terminal.terminal_binding_sha256 != expected_chain_sha256
        ):
            raise PermissionError("terminal bytes hash does not bind the supervisor chain")

    def _required_start(self) -> int:
        if self.started_monotonic_ns is None:
            raise RuntimeError("invocation monotonic start has not been captured")
        return self.started_monotonic_ns

    def _required_deadline(self) -> int:
        if self.deadline_monotonic_ns is None:
            raise RuntimeError("invocation deadline has not been frozen")
        return self.deadline_monotonic_ns
