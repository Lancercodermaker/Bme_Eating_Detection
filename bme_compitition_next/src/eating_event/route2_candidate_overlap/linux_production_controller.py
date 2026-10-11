"""Single bound-mode resource/lifecycle adapter for the Route 2 controller.

This is source assembly, not an installed or admitted runner. The concrete
installation/write-path/worker and abort-quarantine proof sources still refuse
by default. No CLI, admission installation, second journal writer, standalone
Stage A or in-process external wall acceptance is supplied here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import threading
import time
import weakref

from .admission_bootstrap import DEFAULT_SUPERVISOR_CONFIG, parse_supervisor_config
from .budget import (AppendOnlyLedger, BudgetGuard, BudgetLimits, EnforcementReceipt, ResourceSnapshot,
                     STAGE_A_CAPACITY_UPPER_BOUND_V2, require_fixed_native_budget,
                     require_nested_backing_sample, nested_backing_identity, _canonical)
from .contracts import ExperimentApproval, STUDY_ID, require_frozen_admission
from .linux_cgroup_backend import capture_active_study_service_observation, _cgroup2_mount_identity, _validate_unit_name
from .linux_deadline import LinuxKernelDeadline
from .linux_enforcement import capture_cgroup_v2_observation, derive_resource_envelope, validate_cgroup_enforcement
from .linux_initial_volume import (LinuxInitialVolumeCreator, LinuxInitialVolumeOSPorts,
                                  InitialFreeSample, MAX_POLICY_BYTES)
from .linux_supervisor import Route2Supervisor
from .linux_volume_backend import LinuxLoopVolumeExpander, LinuxVolumeOSPorts, _device
from .startup_ownership import require_startup_binding


PRODUCTION_POLICY_PATH = f"/etc/route2/{STUDY_ID}-production-controller.seal"
_POLICY_FIELDS = frozenset({
    "schema", "study_id", "invocation_id", "unit_name", "full_ab_seal_sha256",
    "authorization_card_sha256", "owner_approval_id", "budget_policy_sha256",
    "resource_controller_sha256", "budget_decision_id", "budget_decision_sha256",
    "installation_review_id", "installation_receipt_sha256", "stop_margin_ns",
    "billing_mode", "guest_control_cap_bytes", "host_control_cap_bytes",
    "stage_a_disk_accounting_mode",
})


class LinuxProductionOSPorts(LinuxInitialVolumeOSPorts):
    """Native volume ports with explicit remaining production-proof gates.

    These gates must be replaced by concrete reviewed OS producers, not bools
    in an authorization object or a supplied receipt mapping.
    """

    def require_installation_and_write_boundary(self, policy, frozen, observation):
        raise PermissionError("production controller/worker installation and complete write-path proof is missing")

    def require_original_startup_handshake(self, controller):
        """Hold the two-record startup boundary before publishing broker facts.

        The installed transport must join the original QPC launch challenge to
        the independent signed Linux-unit launch. Integer epochs, a policy flag
        or a supplied signed-looking receipt cannot satisfy this ordering gate.
        """
        if type(controller) is not LinuxProductionController:
            raise PermissionError("startup handshake requires the original concrete controller")
        state = controller._state()
        guard, supervisor = state.guard(), state.supervisor()
        from .linux_supervisor import SupervisorState
        from . import phase_observation as phase
        with phase._LOCK:
            observed = phase._state(guard)
            journal = phase._journal(guard, observed)
            if (state.ports is not self or state.volume is None or not state.total_timer_armed
                    or state.activity is not None or supervisor.state is not SupervisorState.STARTED
                    or observed.binding is not require_startup_binding(guard)
                    or observed.accepted or observed.pending is not None
                    or len(journal.records) != 2
                    or tuple(row["entry"]["event"] for row in journal.records)
                        != ("study_created", "invocation_started")):
                raise PermissionError("startup handshake lost its original two-record pre-worker boundary")
            raise PermissionError(
                "authenticated original QPC/signed Linux-unit startup handshake producer is missing; "
                "broker registration and all workers must wait at the two-record journal boundary"
            )

    def require_worker_quiescence(self, controller, *, activity):
        from .linux_gt_history import require_original_linux_worker_quiescence
        state = _ASSEMBLIES.get(controller)
        if state is None or state.pid != os.getpid() or state.thread is not threading.current_thread():
            raise PermissionError("worker quiescence lacks the original concrete production assembly")
        guard = state.guard()
        if guard is None or guard.enforcer is not controller:
            raise PermissionError("worker quiescence lost its original controller/guard binding")
        return require_original_linux_worker_quiescence(guard)

    def abort_owned_startup(self, controller, failure_phase, failure_kind):
        from .linux_failure_preservation import preserve_owned_failure, StartupPreservedWithoutTeardown
        receipt = preserve_owned_failure(controller, failure_phase, failure_kind)
        raise StartupPreservedWithoutTeardown(receipt)


@dataclass(slots=True)
class _Assembly:
    approval: ExperimentApproval
    invocation_id: str
    limits: BudgetLimits
    started_ns: int
    guard: object
    supervisor: object
    ports: object
    creator: object
    expander: object
    approval_ledger: object
    pid: int
    thread: object
    attempted: bool = False
    failed: bool = False
    abort_attempted: bool = False
    failure_preservation_attempted: bool = False
    control_mount_identity: tuple | None = None
    policy_bytes: bytes | None = None
    policy: dict | None = None
    envelope: object = None
    unit_observation: dict | None = None
    volume: object = None
    initial_sample: object = None
    available_ram: int | None = None
    peak_image_allocated: int = 0
    stage_timer: object = None
    total_timer: object = None
    total_timer_armed: bool = False
    activity: object = None


_ASSEMBLIES = weakref.WeakKeyDictionary()


class LinuxProductionController:
    """Same concrete object for ResourceEnforcer and bound SupervisorOps.

    Its construction is deliberately private to assemble_production_owners.
    Legacy SupervisorOps journal-writing methods are forbidden in bound mode.
    """

    def _state(self, *, allow_failed=False):
        state = _ASSEMBLIES.get(self)
        if (state is None or state.pid != os.getpid() or state.thread is not threading.current_thread()
                or (state.failed and not allow_failed)):
            raise PermissionError("production assembly is absent, consumed or in a different execution identity")
        guard, supervisor = state.guard(), state.supervisor()
        if (guard is None or supervisor is None or type(guard) is not BudgetGuard
                or type(supervisor) is not Route2Supervisor or guard.enforcer is not self
                or supervisor.ops is not self or guard.ledger is not state.approval_ledger
                or guard.limits is not state.limits or supervisor.limits is not state.limits
                or guard.invocation_id != state.invocation_id or supervisor.invocation_id != state.invocation_id
                or guard._invocation_started_ns != state.started_ns
                or supervisor.approval is not state.approval):
            raise PermissionError("production assembly lost its original guard/controller/approval")
        binding = require_startup_binding(guard, state.approval)
        if binding is None or binding.controller is not self:
            raise PermissionError("production operation requires its registered original startup owner")
        state.approval.require_full_ab()
        return state

    def _policy(self, state):
        frozen, _, protected = state.creator._policy()
        config_raw, key, seal, _initial_policy = protected
        config = parse_supervisor_config(config_raw)
        raw = state.ports.read_protected_file(PRODUCTION_POLICY_PATH, max_bytes=MAX_POLICY_BYTES)
        try:
            wrapped = json.loads(raw)
            body = wrapped["body"]
            if (type(wrapped) is not dict or set(wrapped) != {"body", "controller_hmac_sha256"}
                    or type(body) is not dict or set(body) != _POLICY_FIELDS or _canonical(wrapped) != raw
                    or type(wrapped["controller_hmac_sha256"]) is not str
                    or not hmac.compare_digest(hmac.new(key, _canonical(body), hashlib.sha256).hexdigest(),
                                               wrapped["controller_hmac_sha256"])):
                raise ValueError("invalid production policy seal")
            expected = dict(schema="route2_production_controller_policy_v2", study_id=STUDY_ID,
                invocation_id=state.invocation_id, full_ab_seal_sha256=hashlib.sha256(seal).hexdigest(),
                authorization_card_sha256=config.authorization_card_sha256, owner_approval_id=config.owner_approval_id,
                budget_policy_sha256=state.limits.digest(), resource_controller_sha256=frozen.resource_controller_sha256,
                stage_a_disk_accounting_mode=STAGE_A_CAPACITY_UPPER_BOUND_V2,
                stop_margin_ns=60_000_000_000)
            if any(body[name] != value for name, value in expected.items()):
                raise ValueError("production policy binding differs")
            _validate_unit_name(body["unit_name"])
            for name in ("budget_decision_id", "installation_review_id"):
                if type(body[name]) is not str or not body[name].strip():
                    raise ValueError("explicit owner/review decision is missing")
            for name in ("budget_decision_sha256", "installation_receipt_sha256"):
                if (type(body[name]) is not str or len(body[name]) != 64
                        or any(ch not in "0123456789abcdef" for ch in body[name])):
                    raise ValueError("decision/installation content pin is missing")
            for name in ("guest_control_cap_bytes", "host_control_cap_bytes", "stop_margin_ns"):
                if type(body[name]) is not int or body[name] <= 0:
                    raise ValueError("explicit control budget and stop margin required")
            if body["billing_mode"] != "loop_once_separate_hard_capped_controls":
                raise ValueError("this adapter requires a separately approved control billing decision")
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise PermissionError("production controller policy is incomplete or unauthenticated") from exc
        if state.policy_bytes is not None and raw != state.policy_bytes:
            raise PermissionError("protected production controller policy drifted")
        return frozen, body, raw

    def prepare_volume(self, study_root, ledger_path, lock_path, limits, invocation_started_monotonic_ns):
        state = self._state()
        if (state.attempted or type(limits) is not BudgetLimits or limits is not state.limits
                or invocation_started_monotonic_ns != state.started_ns
                or tuple(str(path) for path in (study_root, ledger_path, lock_path)) != (
                    state.approval.study_root_path, state.approval.budget_ledger_path, state.approval.lock_path)):
            raise PermissionError("production volume preparation is one-shot and bound to exact owner paths")
        state.attempted = True
        try:
            frozen, policy, raw = self._policy(state)
            fields = {}
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                name, separator, value = line.partition(":")
                if separator:
                    if name in fields:
                        raise PermissionError("duplicate live RAM field")
                    fields[name] = value.split()
            available = fields.get("MemAvailable", ())
            if len(available) != 2 or available[1] != "kB" or not available[0].isdecimal():
                raise PermissionError("complete live startup MemAvailable evidence is absent")
            state.available_ram = int(available[0]) * 1024
            state.envelope = derive_resource_envelope(limits, available_ram_bytes=state.available_ram,
                                                       stop_margin_ns=policy["stop_margin_ns"])
            observation = capture_active_study_service_observation(policy["unit_name"], state.envelope)
            if observation["systemd_unit"]["main_pid"] != state.pid:
                raise PermissionError("production controller is not the main PID of its approved service")
            # All unresolved admission/control-budget gates precede image or
            # attempt creation. Never mint hard_* from policy claims.
            state.ports.require_installation_and_write_boundary(policy, frozen, observation)
            state.ports.require_host_execution_boundary(state.creator._policy()[1])
            from .linux_failure_preservation import capture_failure_control_boundary
            state.control_mount_identity = capture_failure_control_boundary(policy["guest_control_cap_bytes"])
            state.policy, state.policy_bytes, state.unit_observation = policy, raw, observation
            total_timer, stage_timer = LinuxKernelDeadline(), LinuxKernelDeadline()
            state.total_timer, state.stage_timer = total_timer, stage_timer
            total_timer.arm(state.started_ns + state.envelope.runtime_max_ns)
            state.total_timer_armed = True
            stage_timer.arm(state.started_ns + state.envelope.stage_a_stop_ns)
            volume, sample = state.creator.create_stage_a_volume(state.invocation_id, limits,
                                                                 invocation_started_ns=state.started_ns)
            state.volume, state.initial_sample = volume, sample
            snapshot = self.current_snapshot(study_root)
            proof = validate_cgroup_enforcement(observation, state.envelope)
            evidence = _canonical(dict(policy_sha256=hashlib.sha256(raw).hexdigest(),
                unit=observation, initial_free=asdict(sample), volume=asdict(volume), snapshot=asdict(snapshot)))
            receipt = EnforcementReceipt("route2-linux-production-controller-v1", frozen.resource_controller_sha256,
                frozen.study_root_path, frozen.budget_ledger_path, frozen.lock_path, frozen.approved_write_volumes,
                proof.hard_rss, proof.hard_worker_threads, True, True, hashlib.sha256(evidence).hexdigest(),
                proof.cgroup_path, proof.memory_max_bytes, proof.memory_swap_max_bytes, proof.pids_max,
                state.envelope.rlimit_as_per_process_bytes, limits.stage_a_disk_bytes, limits.total_disk_bytes,
                sample.guest_mount_id, sample.windows_volume_id, state.started_ns, sample.sampled_monotonic_ns,
                volume.created_monotonic_ns, sample.guest_free_bytes, sample.windows_free_bytes,
                volume.filesystem_uuid, volume.loop_device, volume.image_path, volume.image_device,
                volume.image_inode, volume.image_length_bytes, sample.nested_backing)
            receipt.require_complete()
            return receipt, snapshot
        except BaseException:
            state.failed = True
            raise

    def current_snapshot(self, study_root):
        state = self._state()
        if state.volume is None or str(study_root) != state.approval.study_root_path:
            raise PermissionError("production snapshot requires its original created volume")
        self._policy(state)
        observation = capture_cgroup_v2_observation()
        proof = validate_cgroup_enforcement(observation, state.envelope)
        if (proof.cgroup_path != state.unit_observation["cgroup_path"]
                or _cgroup2_mount_identity(cgroup_root=Path("/sys/fs/cgroup"),
                    mountinfo_path=Path("/proc/self/mountinfo")) != state.unit_observation["cgroup2_mount"]):
            raise PermissionError("production resource membership or cgroup2 identity drifted")
        volume = state.volume
        ports = state.ports
        owned = []
        try:
            image = ports.open_existing(volume.image_path, kind="file"); owned.append(image)
            loop = ports.open_existing(volume.loop_device, kind="block"); owned.append(loop)
            root = ports.open_existing(state.approval.approved_write_volumes[0], kind="directory"); owned.append(root)
            info = ports.fstat(image)
            loop_info = ports.loop_state(loop)
            from .wsl_controller import mount_evidence
            from .linux_initial_volume import _mounts
            mount = mount_evidence(Path(state.approval.approved_write_volumes[0]))
            rows = [row for row in _mounts(ports.mountinfo()) if row[2] == state.approval.approved_write_volumes[0]]
            if len(rows) != 1:
                raise PermissionError("production study mount is absent or stacked")
            left, right, _, fs_root, source = rows[0]
            capacity = ports.filesystem_capacity(root)
            if ((info.st_dev, info.st_ino, info.st_size) != (volume.image_device, volume.image_inode, volume.image_length_bytes)
                    or (loop_info.backing_device, loop_info.backing_inode, loop_info.capacity_bytes) !=
                        (volume.image_device, volume.image_inode, volume.image_length_bytes)
                    or (str(mount.mount_id), mount.major_minor) != (volume.mount_id, volume.filesystem_device)
                    or _device(ports.fstat(root).st_dev) != volume.filesystem_device
                    or ports.filesystem_uuid(loop) != volume.filesystem_uuid
                    or capacity != volume.filesystem_capacity_bytes
                    or loop_info.number != int(volume.loop_device[9:]) or loop_info.offset != 0
                    or loop_info.sizelimit != 0 or loop_info.flags & ~16
                    or fs_root != "/" or source != volume.loop_device or right[0] != "ext4"
                    or not {"rw", "nosuid", "nodev", "noexec"} <= set(left[5].split(","))
                    or "ro" in right[2].split(",") or any(value.startswith("shared:") for value in left[6:])
                    or left[2] != volume.filesystem_device):
                raise PermissionError("production study volume identity or capacity drifted")
            allocated = info.st_blocks * 512
            values = os.fstatvfs(root)
            current = (values.f_blocks - values.f_bfree) * values.f_frsize
            # V2 uses the verified fixed image capacity as a strict upper
            # bound, never a measured/deleted-file peak. Keep actual inner
            # usage and sampled physical backing allocation separate.
            state.peak_image_allocated = max(state.peak_image_allocated, allocated)
            if (state.limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
                    or volume.image_length_bytes not in (state.limits.stage_a_disk_bytes, state.limits.total_disk_bytes)
                    or not 0 <= current <= capacity <= volume.image_length_bytes):
                raise PermissionError("explicit V2 disk accounting lacks its actual fixed volume capacity")
            inner_peak_bound = volume.image_length_bytes
            if proof.process_count != 1 or proof.task_count != 1:
                raise PermissionError("a synchronous host-free sample requires the sole controller task")
            _, initial_policy, _ = state.creator._policy()
            parent = ports._open_directory(str(PurePosixPath(volume.image_path).parent)); owned.append(parent)
            live = ports.sample_free(initial_policy, state.invocation_id, parent_fd=parent)
            require_nested_backing_sample(live.nested_backing,
                windows_vhdx_path=live.windows_vhdx_path,windows_volume_id=live.windows_volume_id,
                windows_free_bytes=live.windows_free_bytes)
            initial = state.initial_sample
            if type(initial) is not InitialFreeSample or type(live) is not InitialFreeSample:
                raise PermissionError("production snapshot lacks its original native V2 backing sample")
            def backing_identity(sample):
                return (sample.guest_mount_id, sample.guest_device,
                        nested_backing_identity(sample.nested_backing,
                            windows_vhdx_path=sample.windows_vhdx_path,
                            windows_volume_id=sample.windows_volume_id,
                            windows_free_bytes=sample.windows_free_bytes))
            if backing_identity(live) != backing_identity(initial):
                raise PermissionError("production live backing differs from the original precreate identity")
            ports.require_guest_sample_mount(initial_policy, live, parent_fd=parent)
            if time.monotonic_ns() - live.sampled_monotonic_ns > initial_policy["max_free_sample_age_ns"]:
                raise PermissionError("current two-layer free sample is stale")
            return ResourceSnapshot(proof.process_tree_rss_bytes, inner_peak_bound,
                max(0, proof.process_count - 1), state.available_ram, current, live.guest_free_bytes,
                live.guest_mount_id, live.guest_device, live.windows_vhdx_path, live.windows_volume_id,
                live.windows_free_bytes, volume.mount_id, volume.filesystem_device, capacity,
                volume.filesystem_uuid, volume.loop_device, volume.image_path, info.st_dev, info.st_ino,
                info.st_size, allocated, live.nested_backing)
        finally:
            from .linux_volume_backend import _close_temporary_fds
            _close_temporary_fds(owned)

    def enforce_during_activity(self, study_root, limits, activity, *, remaining_total_wall_ns,
                                remaining_stage_a_wall_ns, remaining_fit_wall_ns, frozen_rss_ceiling_bytes):
        state = self._state()
        if (state.activity is not None or limits is not state.limits or str(study_root) != state.approval.study_root_path
                or frozen_rss_ceiling_bytes != state.envelope.rss_cap_bytes or type(activity) is not str or not activity):
            raise PermissionError("production activity differs from its original resource owner")
        intervals = [remaining_total_wall_ns]
        intervals.extend(value for value in (remaining_stage_a_wall_ns, remaining_fit_wall_ns) if value is not None)
        if any(type(value) is not int or value <= state.envelope.stop_margin_ns for value in intervals):
            raise PermissionError("production activity has no remaining hard-stop interval")
        try:
            entered_ns = time.monotonic_ns()
            self.current_snapshot(study_root)
            state.ports.require_worker_quiescence(self, activity=activity)
            timer = LinuxKernelDeadline()
            deadline = min(entered_ns + min(intervals) - state.envelope.stop_margin_ns,
                           state.started_ns + state.envelope.runtime_max_ns)
            timer.arm(deadline)
            handle = object()
            state.activity = (handle, timer, activity)
            return handle
        except BaseException:
            state.failed = True
            raise

    def stop_activity(self, handle):
        state = self._state()
        if state.activity is None or state.activity[0] is not handle:
            raise PermissionError("production stop requires its exact original activity handle")
        _, timer, activity = state.activity
        try:
            state.ports.require_worker_quiescence(self, activity=activity)
            snapshot = self.current_snapshot(Path(state.approval.study_root_path))
            timer.finish()
            state.activity = None
            return snapshot
        except BaseException:
            state.failed = True
            raise

    def expand_after_stage_b_entry(self, study_root, limits, entry_event_sha256):
        state = self._state()
        if state.activity is not None or str(study_root) != state.approval.study_root_path or limits is not state.limits:
            raise PermissionError("production expansion requires an inactive original owner")
        try:
            state.ports.require_worker_quiescence(self, activity="stage_b_expansion")
            guard, supervisor = state.guard(), state.supervisor()
            from .linux_supervisor import SupervisorState
            from .phase_observation import _state as phase_state, accepted_owned_phase_event
            private_phase = phase_state(guard)
            accepted_entry = accepted_owned_phase_event(guard, "stage_b_entry_passed")
            if (supervisor.state is not SupervisorState.STAGE_B_ENTERED or len(private_phase.accepted) != 2
                    or private_phase.accepted[-1].event != "stage_b_entry_passed"
                    or private_phase.pending is not None
                    or accepted_entry.receipt.event_sha256 != entry_event_sha256):
                raise PermissionError("production expansion lacks its original accepted durable Stage B entry")
            # The original Stage A boundary ends at the durable entry gate.
            # Expansion is covered by the absolute total-study timer.
            state.stage_timer.finish()
            state.stage_timer = None
            expanded = state.expander.expand_same_volume(state.invocation_id, state.volume, entry_event_sha256, limits,
                                                        original_gt_guard=guard)
            state.volume = expanded
            snapshot = self.current_snapshot(study_root)
            return snapshot
        except BaseException:
            state.failed = True
            raise

    def abort_startup(self, invocation_id, approval, failure_phase, failure_kind):
        # Cleanup uses original private pins, including after public linkage
        # drift. Drift is a reason to abort, never a reason to skip cleanup.
        state = _ASSEMBLIES.get(self)
        if (state is None or state.pid != os.getpid() or state.thread is not threading.current_thread()
                or state.abort_attempted or invocation_id != state.invocation_id or approval is not state.approval):
            raise PermissionError("production abort differs from its original consumed startup")
        state.abort_attempted = True
        state.failed = True
        return state.ports.abort_owned_startup(self, failure_phase, failure_kind)

    @staticmethod
    def _forbid_legacy(*args, **kwargs):
        raise PermissionError("bound production mode forbids a second storage/phase/terminal owner or in-process wall acceptance")

    first_monotonic_sample = sample_startup_free = acquire_one_shot_lock = create_stage_a_volume = _forbid_legacy
    read_stage_a_boundary = append_stage_b_entry = expand_same_volume = append_expansion_receipt = _forbid_legacy
    read_stage_b_completion = close_terminal = observe_exit_and_persist_wall_receipt = _forbid_legacy


def assemble_production_owners(*, approval, limits, invocation_id, invocation_started_monotonic_ns,
                               external_started_ticks, qpc_frequency, role_registry_bytes):
    """Assemble one fresh ledger/guard/supervisor with one native controller.

    Call only inside the verified source/runtime bootstrap, then use the fixed
    ABExecutionBindings/run_bootstrapped_ab handoff. This does not bind/start
    the guard, create storage, consume admission, or confer authorization.
    The pre-bootstrap Linux start producer and complete data adapters remain
    separate requirements of the installed launcher.
    """
    if type(approval) is not ExperimentApproval or type(limits) is not BudgetLimits:
        raise PermissionError("production assembly requires fixed approval and budget types")
    require_fixed_native_budget(limits)
    if limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2:
        raise PermissionError("production assembly requires the owner-confirmed V2 strict disk capacity protocol")
    approval.require_full_ab()
    frozen = require_frozen_admission()
    if limits.digest() != frozen.budget_policy_sha256:
        raise PermissionError("production assembly budget differs from the frozen decision")
    from .stage_a_replay import MAX_ROLE_REGISTRY_BYTES
    if (type(role_registry_bytes) is not bytes or not 0 < len(role_registry_bytes) <= MAX_ROLE_REGISTRY_BYTES
            or hashlib.sha256(role_registry_bytes).hexdigest() != frozen.role_input_registry_sha256):
        raise PermissionError("production assembly lacks immutable registry bytes bound to frozen safe-role metadata")
    controller = LinuxProductionController()
    ledger = AppendOnlyLedger(Path(approval.budget_ledger_path), Path(approval.lock_path), Path(approval.study_root_path))
    guard = BudgetGuard(limits, ledger, controller, ledger.study_root,
        approved_controller_sha256=approval.resource_controller_sha256,
        approved_write_volumes=approval.approved_write_volumes,
        invocation_started_monotonic_ns=invocation_started_monotonic_ns, invocation_id=invocation_id)
    supervisor = Route2Supervisor(approval=approval, invocation_id=invocation_id, ops=controller, limits=limits,
        external_started_ticks=external_started_ticks, qpc_frequency=qpc_frequency)
    ports = LinuxProductionOSPorts()
    state = _Assembly(approval, invocation_id, limits, invocation_started_monotonic_ns, weakref.ref(guard),
        weakref.ref(supervisor), ports, LinuxInitialVolumeCreator(ports=ports),
        LinuxLoopVolumeExpander(ports=ports, role_registry_bytes=role_registry_bytes),
        ledger, os.getpid(), threading.current_thread())
    _ASSEMBLIES[controller] = state
    return ledger, guard, supervisor


__all__ = ["LinuxProductionController", "assemble_production_owners"]
