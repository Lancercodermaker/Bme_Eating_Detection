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
import re
from typing import Mapping, Protocol

from .budget import (
    BudgetLimits,
    StageBProjection,
    require_stage_b_entry,
)
from .contracts import STUDY_ID, StudyStatus
from .linux_enforcement import verify_post_exit_receipt


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant {value} is forbidden")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class SupervisorState(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    STARTED = "STARTED"
    STAGE_A_FINISHED = "STAGE_A_FINISHED"
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
    pooled_aggregation_completed: bool
    pooled_gt_reads: int
    finished_monotonic_ns: int
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
        self.stage_b_completion: StageBExecutionReceipt | None = None
        self._terminal: TerminalCloseReceipt | None = None
        self._terminal_attempted = False
        self._lock_attempted = False
        self._startup_failure_phase = "approval"

    def start(self) -> ImageVolumeReceipt:
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
        if not all(
            isinstance(getattr(self.approval, field, None), str)
            and getattr(self.approval, field).startswith("/")
            for field in ("study_root_path", "budget_ledger_path", "lock_path", "study_image_path")
        ):
            raise PermissionError("approved study paths must be exact absolute Linux paths")

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
                or not started <= receipt.finished_monotonic_ns <= started + self.limits.stage_a_wall_ns
                or not _SHA256.fullmatch(receipt.event_sha256)
                or receipt.durable is not True
            ):
                raise PermissionError("Stage A boundary is incomplete, late or not durably frozen")
            self.stage_a = receipt
            self.state = SupervisorState.STAGE_A_FINISHED
            return receipt
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def enter_stage_b(self, projection: StageBProjection) -> ImageVolumeReceipt:
        if self.state is not SupervisorState.STAGE_A_FINISHED or self.stage_a is None or self.volume is None:
            raise RuntimeError("Stage B requires a durable complete Stage A boundary")
        if self.stage_a.different_treatment_roles == 0:
            raise PermissionError("identical treatment roles stop before Stage B")
        try:
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
                or entry.fsynced_monotonic_ns < self.stage_a.finished_monotonic_ns
                or entry.fsynced_monotonic_ns > self._required_deadline()
            ):
                raise PermissionError("Stage B entry is not durably committed before expansion")
            self.stage_b_entry = entry
            self._stage_b_projection = projection

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
                or expansion.fsynced_monotonic_ns > self._required_deadline()
            ):
                raise PermissionError("same-volume expansion receipt is not durable")
            self.volume = expanded
            self.expansion_receipt = expansion
            self.state = SupervisorState.STAGE_B_READY
            return expanded
        except BaseException:
            self.state = SupervisorState.FAILED
            raise

    def finish_stage_b(self) -> StageBExecutionReceipt:
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
                receipt.pooled_gt_reads,
            )
            if (
                receipt.invocation_id != self.invocation_id
                or any(type(value) is not int for value in counts)
                or counts != (20, 5, 25, 25, 65, 21, 0)
                or receipt.pooled_aggregation_completed is not True
                or type(receipt.finished_monotonic_ns) is not int
                or receipt.finished_monotonic_ns < self.expansion_receipt.fsynced_monotonic_ns
                or receipt.finished_monotonic_ns > self._required_deadline()
                or not _SHA256.fullmatch(receipt.event_sha256)
                or not _SHA256.fullmatch(receipt.result_sha256)
                or receipt.durable is not True
            ):
                raise PermissionError("Stage B execution, fixed call quotas or pooled no-GT receipt is incomplete")
            self.stage_b_completion = receipt
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
            or expanded.filesystem_capacity_bytes != self.limits.total_disk_bytes
            or expanded.image_length_bytes != self.limits.total_disk_bytes
        ):
            raise PermissionError("Stage B expansion changed identity or did not reach the exact approved capacity")

    def finalize(self, status: str, *, evidence: Mapping[str, object]) -> TerminalAcceptance:
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
            "stage_a_event_sha256": self.stage_a.event_sha256 if self.stage_a is not None else None,
            "stage_b_entry_event_sha256": self.stage_b_entry.event_sha256 if self.stage_b_entry is not None else None,
            "stage_b_expansion_event_sha256": (
                self.expansion_receipt.event_sha256 if self.expansion_receipt is not None else None
            ),
            "stage_b_completion_event_sha256": (
                self.stage_b_completion.event_sha256 if self.stage_b_completion is not None else None
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
                or not started <= terminal.terminal_closed_monotonic_ns <= deadline
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
                deadline,
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
                "projection": asdict(self._stage_b_projection),
                "fsynced_monotonic_ns": self.stage_b_entry.fsynced_monotonic_ns,
            }
        if self.expansion_receipt is not None:
            if self.stage_b_entry is None or self.volume is None:
                raise PermissionError("expansion receipt lacks its entry or expanded volume")
            payloads["stage_b_volume_expanded"] = {
                "entry_event_sha256": self.stage_b_entry.event_sha256,
                "volume": asdict(self.volume),
                "fsynced_monotonic_ns": self.expansion_receipt.fsynced_monotonic_ns,
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
                "pooled_aggregation_completed": item.pooled_aggregation_completed,
                "pooled_gt_reads": item.pooled_gt_reads,
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
        deadline_monotonic_ns: int,
    ) -> None:
        """Bind the terminal digest to canonical bytes containing the supervisor chain.

        ``terminal_record_bytes`` must be read back from the closed ledger by
        the trusted backend.  The coordinator independently checks the record
        envelope, payload, chain digest and append-only ledger event digest.
        """
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
        if (
            set(payload) != {"status", "evidence", "wall_ns", "monotonic_ns", "epoch_ns"}
            or payload.get("status") != status
            or payload.get("evidence") != dict(expected_evidence)
            or type(payload.get("wall_ns")) is not int
            or payload["wall_ns"] < 0
            or type(payload.get("monotonic_ns")) is not int
            or not started_monotonic_ns <= payload["monotonic_ns"] <= terminal.terminal_closed_monotonic_ns
            or payload["wall_ns"] != payload["monotonic_ns"] - started_monotonic_ns
            or type(payload.get("epoch_ns")) is not int
            or payload["epoch_ns"] <= 0
            or terminal.terminal_closed_monotonic_ns > deadline_monotonic_ns
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
                if event.get("payload") != expected_payload:
                    raise PermissionError("terminal ledger stage event differs from its accepted receipt payload")
                timestamp_key = {
                    "stage_a_finished": "finished_monotonic_ns",
                    "stage_b_entry_passed": "fsynced_monotonic_ns",
                    "stage_b_volume_expanded": "fsynced_monotonic_ns",
                    "stage_b_complete": "finished_monotonic_ns",
                }[event_name]
                event_timestamp = expected_payload.get(timestamp_key) if expected_payload is not None else None
                if type(event_timestamp) is not int:
                    raise PermissionError("terminal ledger stage event lacks its monotonic receipt time")
                latest_stage_monotonic_ns = max(latest_stage_monotonic_ns, event_timestamp)
        completion_hash = chain.get("stage_b_completion_event_sha256")
        if completion_hash is not None:
            completion_payload = event_hashes[completion_hash].get("payload", {})
            if completion_payload.get("result_sha256") != chain.get("stage_b_result_sha256"):
                raise PermissionError("terminal ledger chain does not bind the Stage B result hash")
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
