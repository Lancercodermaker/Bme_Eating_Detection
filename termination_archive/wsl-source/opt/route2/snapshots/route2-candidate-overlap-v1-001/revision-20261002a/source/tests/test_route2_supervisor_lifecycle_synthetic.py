"""Synthetic checks for the Route 2 supervisor's one-shot lifecycle ordering."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap.budget import (
    CALL_CEILINGS,
    BudgetLimits,
    StageBProjection,
    _replay_call_event_accounting,
)
from eating_event.route2_candidate_overlap.linux_supervisor import (
    BackingFreeReceipt,
    DurableLedgerReceipt,
    ExternalExitObservation,
    ImageVolumeReceipt,
    OneShotLockReceipt,
    StageABoundaryReceipt,
    StageBExecutionReceipt,
    TerminalCloseReceipt,
    Route2Supervisor,
    SupervisorState,
)
from eating_event.route2_candidate_overlap.contracts import StudyStatus


GIB = 1024**3
EXT4_CAPACITY_AFTER_4_GIB_IMAGE = 4_152_066_048


def _approval(tmp_path):
    study_root = "/scratch/route2-synthetic/study"
    return SimpleNamespace(
        study_id="route2-candidate-overlap-v1-001",
        scope="A+B",
        approved=True,
        study_root_path=study_root,
        budget_ledger_path="/scratch/route2-synthetic/study-budget.jsonl",
        lock_path="/scratch/route2-synthetic/study.lock",
        study_image_path="/scratch/route2-synthetic/study.ext4",
        require_full_ab=lambda: None,
    )


def _volume(approval, *, created_ns=120, capacity=2 * GIB, image_length=2 * GIB):
    return ImageVolumeReceipt(
        invocation_id="synthetic-invocation",
        study_id=approval.study_id,
        study_root_path=approval.study_root_path,
        ledger_path=approval.budget_ledger_path,
        lock_path=approval.lock_path,
        image_path=approval.study_image_path,
        created_monotonic_ns=created_ns,
        image_device=8,
        image_inode=99,
        loop_device="/dev/loop900",
        filesystem_uuid="synthetic-uuid",
        mount_id="900",
        filesystem_device="/dev/loop900",
        filesystem_capacity_bytes=capacity,
        image_length_bytes=image_length,
    )


def _valid_post_exit(invocation_id, terminal_hash, start_ns, terminal_ns, deadline_ns):
    qpc_frequency = 10_000_000
    host_started = 50_000
    host_deadline = host_started + (deadline_ns - start_ns) * qpc_frequency // 1_000_000_000
    receipt = {
        "schema": "route2_post_exit_receipt_v1",
        "invocation_id": invocation_id,
        "unit_name": "route2-study-synthetic.service",
        "terminal_sha256": terminal_hash,
        "unit_result": "success",
        "exit_status": 0,
        "active_state": "inactive",
        "durable_external_event": True,
        "invocation_started_ns": start_ns,
        "terminal_closed_ns": terminal_ns,
        "deadline_ns": deadline_ns,
        "external_clock": "windows_qpc",
        "qpc_frequency": qpc_frequency,
        "external_started_ticks": host_started,
        "external_terminal_detected_ticks": host_started + 10,
        "external_unit_inactive_ticks": host_started + 20,
        "external_receipt_fsynced_ticks": host_started + 30,
        "external_deadline_ticks": host_deadline,
    }
    return ExternalExitObservation(
        invocation_id=invocation_id,
        unit_name="route2-study-synthetic.service",
        unit_inactive=True,
        cgroup_empty=True,
        terminal_reverified=True,
        external_receipt_durable=True,
        receipt=receipt,
        observed_monotonic_ns=terminal_ns + 100,
        observed_external_ticks=host_started + 40,
        qpc_frequency=qpc_frequency,
        external_started_ticks=host_started,
    )


def _synthetic_fixed_call_role_ids():
    fits = []
    predictions = []
    decoders = []
    evaluators = []
    for outer_index in range(5):
        outer_id = f"outer-{outer_index:02d}"
        inner_roles = tuple(
            f"candidate/{outer_id}/inner-{inner_index:02d}/inner"
            for inner_index in range(4)
        )
        fits.extend(
            f"verifier/{outer_id}/inner-{inner_index:02d}"
            for inner_index in range(4)
        )
        fits.append(f"verifier/{outer_id}/outer")
        predictions.extend(inner_roles)
        predictions.append(f"candidate/{outer_id}/outer")
        for role_id in inner_roles:
            decoders.extend((role_id,) * 3)
        decoders.append(f"candidate/{outer_id}/outer")
        evaluators.extend(
            f"threshold/{outer_id}/{threshold}"
            for threshold in ("0.10", "0.25", "0.50")
        )
        evaluators.append(f"outer/{outer_id}")
    return {
        "verifier_fit": tuple(fits),
        "verifier_predict": tuple(predictions),
        "decoder": tuple(decoders),
        "event_evaluator": tuple(evaluators),
        "pooled_reduction": ("pooled/outer",),
    }


def _complete_evidence():
    return {"stage_b_result": {"synthetic": True}}


class FakeSupervisorOps:
    def __init__(self, approval):
        self.approval = approval
        self.events = []
        self.sample = BackingFreeReceipt(
            invocation_id="synthetic-invocation",
            sampled_monotonic_ns=110,
            guest_free_bytes=9 * GIB,
            guest_mount_id="scratch-mount",
            guest_device="/dev/scratch",
            windows_vhdx_path=r"C:\scratch\ext4.vhdx",
            windows_volume_id="scratch-volume",
            windows_free_bytes=9 * GIB,
            available_ram_bytes=8 * GIB,
        )
        self.lock = OneShotLockReceipt(
            invocation_id="synthetic-invocation",
            study_id=approval.study_id,
            lock_path=approval.lock_path,
            created_monotonic_ns=115,
            exclusive_create=True,
        )
        self.volume = _volume(approval)
        self.stage_a = StageABoundaryReceipt(
            invocation_id="synthetic-invocation",
            reference_roles=105,
            treatment_roles=105,
            different_treatment_roles=1,
            stage_a_disk_bytes=100 * 1024**2,
            finished_monotonic_ns=1_000,
            fsynced_monotonic_ns=1_005,
            event_sha256="a" * 64,
            durable=True,
        )
        self.stage_b_entry = DurableLedgerReceipt(
            invocation_id="synthetic-invocation",
            event_sha256="b" * 64,
            fsynced_monotonic_ns=1_100,
            durable=True,
        )
        self.expanded = replace(
            self.volume,
            created_monotonic_ns=1_200,
            filesystem_capacity_bytes=4 * GIB,
            image_length_bytes=4 * GIB,
        )
        self.expansion_receipt = DurableLedgerReceipt(
            invocation_id="synthetic-invocation",
            event_sha256="c" * 64,
            fsynced_monotonic_ns=1_300,
            durable=True,
        )
        self.stage_b_completion = StageBExecutionReceipt(
            invocation_id="synthetic-invocation",
            inner_roles_completed=20,
            outer_roles_completed=5,
            verifier_fit_calls=25,
            verifier_predict_calls=25,
            decoder_calls=65,
            evaluator_calls=20,
            pooled_aggregation_calls=1,
            pooled_aggregation_completed=True,
            pooled_gt_reads=0,
            call_event_count=408,
            call_event_accounting_sha256="f" * 64,
            finished_monotonic_ns=1_400,
            fsynced_monotonic_ns=1_405,
            event_sha256="e" * 64,
            result_sha256=hashlib.sha256(
                json.dumps({"synthetic": True}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            durable=True,
        )
        self.terminal = TerminalCloseReceipt(
            invocation_id="synthetic-invocation",
            unit_name="route2-study-synthetic.service",
            status=StudyStatus.COMPLETE.value,
            terminal_sha256="d" * 64,
            terminal_binding_sha256="0" * 64,
            invocation_started_monotonic_ns=100,
            terminal_closed_monotonic_ns=1_500,
            deadline_monotonic_ns=100 + BudgetLimits().total_wall_ns,
            ledger_fsynced=True,
            ledger_closed=True,
            no_active_gt_view=True,
            no_active_worker=True,
            terminal_record_bytes=b"",
            ledger_bytes=b"",
        )
        self.post_exit = _valid_post_exit(
            "synthetic-invocation", self.terminal.terminal_sha256,
            self.terminal.invocation_started_monotonic_ns,
            self.terminal.terminal_closed_monotonic_ns,
            self.terminal.deadline_monotonic_ns,
        )
        self.precreate_at = None
        self.stage_b_at = None
        self.terminal_evidence = None
        self.fail_volume_creation = False
        self.corrupt_terminal_digest = False
        self.corrupt_terminal_chain = False
        self.corrupt_ledger_previous = False
        self.corrupt_stage_a_payload = False
        self.corrupt_stage_a_payload_float_type = False
        self.corrupt_stage_a_payload_bool_type = False
        self.corrupt_stage_b_entry_payload = False
        self.corrupt_stage_b_expansion_payload = False
        self.corrupt_stage_b_completion_payload = False
        self.duplicate_stage_events = False
        self.corrupt_terminal_wall_duration = False
        self.terminal_record_monotonic_ns = 1_450
        self._ledger_records = []
        self._ledger_tail = "0" * 64
        self.omit_call_event_records = False
        self._append_ledger_event("invocation_started", {
            "invocation_id": "synthetic-invocation",
            "monotonic_ns": 100,
        })
        self.abort_receipt = SimpleNamespace(
            invocation_id="synthetic-invocation",
            study_root_path=approval.study_root_path,
            ledger_path=approval.budget_ledger_path,
            lock_path=approval.lock_path,
            image_path=approval.study_image_path,
            mounts_detached=True,
            partial_resources_quarantined=True,
            failure_receipt_durable=True,
            retry_forbidden=True,
            completed_monotonic_ns=125,
        )

    def first_monotonic_sample(self):
        self.events.append("start_clock")
        return 100

    def sample_startup_free(self, invocation_id):
        self.events.append("sample_free")
        return self.sample

    def acquire_one_shot_lock(self, invocation_id, approval):
        self.events.append("lock")
        return self.lock

    def create_stage_a_volume(self, invocation_id, approval, limits):
        self.events.append("create_stage_a")
        self.precreate_at = len(self.events)
        if self.fail_volume_creation:
            raise OSError("synthetic image creation interruption")
        return self.volume

    def abort_startup(self, invocation_id, approval, failure_phase, failure_kind):
        self.events.append("abort_startup")
        return self.abort_receipt

    def read_stage_a_boundary(self, invocation_id):
        self.events.append("stage_a_boundary")
        payload = {
            "invocation_id": self.stage_a.invocation_id,
            "reference_roles": self.stage_a.reference_roles,
            "treatment_roles": self.stage_a.treatment_roles,
            "different_treatment_roles": self.stage_a.different_treatment_roles,
            "stage_a_disk_bytes": self.stage_a.stage_a_disk_bytes,
            "finished_monotonic_ns": self.stage_a.finished_monotonic_ns,
        }
        if self.corrupt_stage_a_payload:
            payload["different_treatment_roles"] += 1
        if self.corrupt_stage_a_payload_float_type:
            payload["reference_roles"] = 105.0
        if self.corrupt_stage_a_payload_bool_type:
            payload["different_treatment_roles"] = True
        event_sha256, _ = self._append_ledger_event("stage_a_finished", payload)
        self.stage_a = replace(self.stage_a, event_sha256=event_sha256)
        return self.stage_a

    def append_stage_b_entry(self, invocation_id, projection):
        self.events.append("stage_b_entry_fsync")
        self.stage_b_at = len(self.events)
        projected_values = projection.__dict__ if hasattr(projection, "__dict__") else {
                "candidate_rows_n": projection.candidate_rows_n,
                "maximum_fit_rows_m": projection.maximum_fit_rows_m,
                "prediction_rows_s": projection.prediction_rows_s,
                "candidate_file_bytes_b": projection.candidate_file_bytes_b,
                "stage_a_disk_bytes_d_a": projection.stage_a_disk_bytes_d_a,
            }
        if self.corrupt_stage_b_entry_payload:
            projected_values = dict(projected_values)
            projected_values["maximum_fit_rows_m"] += 1
        event_sha256, _ = self._append_ledger_event("stage_b_entry_passed", {
            "invocation_id": invocation_id,
            "projection": projected_values,
        })
        self.stage_b_entry = replace(self.stage_b_entry, event_sha256=event_sha256)
        return self.stage_b_entry

    def expand_same_volume(self, invocation_id, current, event_sha256, limits):
        self.events.append("expand_same_volume")
        return self.expanded

    def append_expansion_receipt(self, invocation_id, event_sha256, expanded):
        self.events.append("expansion_receipt_fsync")
        expanded_payload = {
            "invocation_id": invocation_id,
            "entry_event_sha256": self.stage_b_entry.event_sha256,
            "volume": {
                "invocation_id": expanded.invocation_id,
                "study_id": expanded.study_id,
                "study_root_path": expanded.study_root_path,
                "ledger_path": expanded.ledger_path,
                "lock_path": expanded.lock_path,
                "image_path": expanded.image_path,
                "created_monotonic_ns": expanded.created_monotonic_ns,
                "image_device": expanded.image_device,
                "image_inode": expanded.image_inode,
                "loop_device": expanded.loop_device,
                "filesystem_uuid": expanded.filesystem_uuid,
                "mount_id": expanded.mount_id,
                "filesystem_device": expanded.filesystem_device,
                "filesystem_capacity_bytes": expanded.filesystem_capacity_bytes,
                "image_length_bytes": expanded.image_length_bytes,
            },
        }
        if self.corrupt_stage_b_expansion_payload:
            expanded_payload["volume"]["filesystem_uuid"] = "different-volume-uuid"
        receipt_hash, _ = self._append_ledger_event("stage_b_volume_expanded", expanded_payload)
        self.expansion_receipt = replace(self.expansion_receipt, event_sha256=receipt_hash)
        return self.expansion_receipt

    def read_stage_b_completion(self, invocation_id):
        self.events.append("stage_b_complete")
        if not self.omit_call_event_records:
            for kind, role_ids in _synthetic_fixed_call_role_ids().items():
                for attempt, role_id in enumerate(role_ids, start=1):
                    ceiling = CALL_CEILINGS[kind]
                    self._append_ledger_event("call_reserved", {
                        "kind": kind,
                        "role_id": role_id,
                        "attempt": attempt,
                        "ceiling": ceiling,
                    })
                    self._append_ledger_event("call_started", {
                        "kind": kind,
                        "role_id": role_id,
                        "attempt": attempt,
                    })
                    self._append_ledger_event("call_finished", {
                        "kind": kind,
                        "role_id": role_id,
                        "attempt": attempt,
                        "outcome": "succeeded",
                    })
            prior_entries = [json.loads(record[:-1])["entry"] for record in self._ledger_records]
            call_accounting = _replay_call_event_accounting(
                ((entry["event"], entry["payload"]) for entry in prior_entries),
                ledger_tail_sha256=self._ledger_tail,
            )
            self.stage_b_completion = replace(
                self.stage_b_completion,
                call_event_count=call_accounting["call_event_count"],
                call_event_accounting_sha256=call_accounting["call_event_accounting_sha256"],
            )
        payload = {
            "invocation_id": self.stage_b_completion.invocation_id,
            "inner_roles_completed": self.stage_b_completion.inner_roles_completed,
            "outer_roles_completed": self.stage_b_completion.outer_roles_completed,
            "verifier_fit_calls": self.stage_b_completion.verifier_fit_calls,
            "verifier_predict_calls": self.stage_b_completion.verifier_predict_calls,
            "decoder_calls": self.stage_b_completion.decoder_calls,
            "evaluator_calls": self.stage_b_completion.evaluator_calls,
            "pooled_aggregation_calls": self.stage_b_completion.pooled_aggregation_calls,
            "pooled_aggregation_completed": self.stage_b_completion.pooled_aggregation_completed,
            "pooled_gt_reads": self.stage_b_completion.pooled_gt_reads,
            "call_event_count": self.stage_b_completion.call_event_count,
            "call_event_accounting_sha256": self.stage_b_completion.call_event_accounting_sha256,
            "finished_monotonic_ns": self.stage_b_completion.finished_monotonic_ns,
            "result_sha256": self.stage_b_completion.result_sha256,
        }
        if self.corrupt_stage_b_completion_payload:
            payload["decoder_calls"] -= 1
        event_sha256, _ = self._append_ledger_event("stage_b_complete", payload)
        self.stage_b_completion = replace(self.stage_b_completion, event_sha256=event_sha256)
        return self.stage_b_completion

    def _append_ledger_event(self, event, payload, *, previous_sha256=None):
        body = {
            "seq": len(self._ledger_records),
            "event": event,
            "payload": payload,
            "previous_sha256": previous_sha256 if previous_sha256 is not None else self._ledger_tail,
        }
        encoded_body = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded_body).hexdigest()
        record = json.dumps(
            {"entry": body, "sha256": digest}, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        self._ledger_records.append(record)
        self._ledger_tail = digest
        return digest, record

    def close_terminal(self, invocation_id, status, evidence, started_ns, deadline_ns):
        self.events.append("terminal_fsync_close")
        self.terminal_evidence = dict(evidence)
        if self.duplicate_stage_events:
            duplicate_payload = {
                "invocation_id": self.stage_b_completion.invocation_id,
                "inner_roles_completed": self.stage_b_completion.inner_roles_completed,
                "outer_roles_completed": self.stage_b_completion.outer_roles_completed,
                "verifier_fit_calls": self.stage_b_completion.verifier_fit_calls,
                "verifier_predict_calls": self.stage_b_completion.verifier_predict_calls,
                "decoder_calls": self.stage_b_completion.decoder_calls,
                "evaluator_calls": self.stage_b_completion.evaluator_calls,
                "pooled_aggregation_calls": self.stage_b_completion.pooled_aggregation_calls,
                "pooled_aggregation_completed": self.stage_b_completion.pooled_aggregation_completed,
                "pooled_gt_reads": self.stage_b_completion.pooled_gt_reads,
                "call_event_count": self.stage_b_completion.call_event_count,
                "call_event_accounting_sha256": self.stage_b_completion.call_event_accounting_sha256,
                "finished_monotonic_ns": self.stage_b_completion.finished_monotonic_ns,
                "result_sha256": self.stage_b_completion.result_sha256,
            }
            self._append_ledger_event("stage_b_complete", duplicate_payload)
        record_evidence = dict(evidence)
        if self.corrupt_terminal_chain:
            record_evidence["route2_supervisor_chain_sha256"] = "0" * 64
        previous = "7" * 64 if self.corrupt_ledger_previous else self._ledger_tail
        digest, record = self._append_ledger_event("terminal", {
            "status": status,
            "evidence": record_evidence,
            "wall_ns": (
                1 if self.corrupt_terminal_wall_duration
                else self.terminal_record_monotonic_ns - started_ns
            ),
            "monotonic_ns": self.terminal_record_monotonic_ns,
            "epoch_ns": 1_700_000_000_000_000_000,
        }, previous_sha256=previous)
        terminal = replace(
            self.terminal,
            status=status,
            terminal_sha256="9" * 64 if self.corrupt_terminal_digest else digest,
            terminal_binding_sha256=evidence.get("route2_supervisor_chain_sha256", "0" * 64),
            terminal_record_bytes=record,
            ledger_bytes=b"".join(self._ledger_records),
        )
        self.terminal = terminal
        receipt = dict(self.post_exit.receipt)
        receipt["terminal_sha256"] = terminal.terminal_sha256
        self.post_exit = replace(self.post_exit, receipt=receipt)
        return terminal

    def observe_exit_and_persist_wall_receipt(self, terminal):
        self.events.append("wait_inactive_then_wall_receipt")
        return self.post_exit


def _supervisor(tmp_path, ops=None, limits=None):
    approval = _approval(tmp_path)
    backend = ops or FakeSupervisorOps(approval)
    supervisor = Route2Supervisor(
        approval=approval,
        invocation_id="synthetic-invocation",
        ops=backend,
        limits=limits or BudgetLimits(),
        external_started_ticks=50_000,
        qpc_frequency=10_000_000,
    )
    return supervisor, backend


def test_two_layer_free_gate_runs_before_lock_and_image(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.sample = replace(ops.sample, windows_free_bytes=8 * GIB - 1)

    with pytest.raises(RuntimeError, match="two-layer"):
        supervisor.start()

    assert ops.events == ["start_clock", "sample_free"]
    assert supervisor.state is SupervisorState.FAILED


def test_missing_explicit_ab_approval_is_rejected_before_backing_sample(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    del supervisor.approval.approved

    with pytest.raises(PermissionError, match="approval"):
        supervisor.start()

    assert ops.events == ["start_clock"]
    assert supervisor.state is SupervisorState.FAILED


def test_one_shot_invocation_cannot_be_started_twice(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    before = list(ops.events)

    with pytest.raises(RuntimeError, match="once"):
        supervisor.start()

    assert ops.events == before


def test_image_must_be_created_after_same_invocation_two_layer_sample(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.volume = replace(ops.volume, created_monotonic_ns=ops.sample.sampled_monotonic_ns)

    with pytest.raises(PermissionError, match="pre-create"):
        supervisor.start()

    assert "lock" in ops.events
    assert "create_stage_a" in ops.events
    assert supervisor.state is SupervisorState.FAILED


def test_stage_a_fsync_must_finish_before_stage_a_deadline(tmp_path):
    limits = replace(BudgetLimits(), stage_a_wall_ns=1_000)
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_101)
    supervisor.start()

    with pytest.raises(PermissionError, match="Stage A boundary"):
        supervisor.finish_stage_a()

    assert supervisor.state is SupervisorState.FAILED
    assert "expand_same_volume" not in ops.events


def test_late_stage_a_receipt_is_retained_for_incomplete_terminal(tmp_path):
    limits = replace(BudgetLimits(), stage_a_wall_ns=1_000)
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_101)
    supervisor.start()

    with pytest.raises(PermissionError, match="Stage A boundary fsync"):
        supervisor.finish_stage_a()

    accepted = supervisor.finalize(StudyStatus.COMPLETE.value, evidence={})
    assert accepted.accepted is True
    assert accepted.status == StudyStatus.INCOMPLETE_RESOURCE.value
    assert supervisor.stage_a is not None
    names = [json.loads(record)["entry"]["event"] for record in ops._ledger_records]
    assert "stage_a_finished" in names
    assert "stage_b_entry_passed" not in names


def test_stage_b_entry_fsync_must_finish_before_stage_a_deadline(tmp_path):
    limits = replace(BudgetLimits(), stage_a_wall_ns=1_000)
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_005)
    ops.stage_b_entry = replace(ops.stage_b_entry, fsynced_monotonic_ns=1_101)
    supervisor.start()
    supervisor.finish_stage_a()

    with pytest.raises(PermissionError, match="Stage B entry"):
        supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    assert supervisor.state is SupervisorState.FAILED
    assert "expand_same_volume" not in ops.events


def test_late_stage_b_entry_receipt_is_retained_without_expansion(tmp_path):
    limits = replace(BudgetLimits(), stage_a_wall_ns=1_000)
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_005)
    ops.stage_b_entry = replace(ops.stage_b_entry, fsynced_monotonic_ns=1_101)
    supervisor.start()
    supervisor.finish_stage_a()

    with pytest.raises(PermissionError, match="Stage B entry fsync"):
        supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    accepted = supervisor.finalize(StudyStatus.COMPLETE.value, evidence={})
    assert accepted.accepted is True
    assert accepted.status == StudyStatus.INCOMPLETE_RESOURCE.value
    assert supervisor.stage_b_entry is not None
    assert supervisor.expansion_receipt is None
    assert "expand_same_volume" not in ops.events
    names = [json.loads(record)["entry"]["event"] for record in ops._ledger_records]
    assert names.count("stage_b_entry_passed") == 1
    assert "stage_b_volume_expanded" not in names


@pytest.mark.parametrize("boundary", ["stage_a", "stage_b_entry"])
def test_terminal_rejects_work_events_after_late_stage_boundary(boundary, tmp_path):
    limits = replace(BudgetLimits(), stage_a_wall_ns=1_000)
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    if boundary == "stage_a":
        ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_101)
        supervisor.start()
        with pytest.raises(PermissionError, match="Stage A boundary"):
            supervisor.finish_stage_a()
    else:
        ops.stage_a = replace(ops.stage_a, finished_monotonic_ns=1_000, fsynced_monotonic_ns=1_005)
        ops.stage_b_entry = replace(ops.stage_b_entry, fsynced_monotonic_ns=1_101)
        supervisor.start()
        supervisor.finish_stage_a()
        with pytest.raises(PermissionError, match="Stage B entry"):
            supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    ops._append_ledger_event("activity_started", {
        "name": "unbound-post-deadline-work",
        "monotonic_ns": 1_102,
    })
    with pytest.raises(PermissionError, match="work event follows late"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence={})


def test_terminal_rejects_work_events_after_late_stage_b_expansion(tmp_path):
    limits = replace(
        BudgetLimits(), stage_a_wall_ns=1_000, total_wall_ns=1_400, fit_wall_ns=1_300,
    )
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.expansion_receipt = replace(ops.expansion_receipt, fsynced_monotonic_ns=1_501)
    ops.terminal = replace(ops.terminal, deadline_monotonic_ns=1_500)
    supervisor.start()
    supervisor.finish_stage_a()

    with pytest.raises(PermissionError, match="expansion receipt fsync"):
        supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    ops._append_ledger_event("worker_write", {"path": "/scratch/after-late-expansion.bin"})
    with pytest.raises(PermissionError, match="work event follows late"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence={})


def test_complete_terminal_rejects_any_work_event_after_stage_b_completion(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops._append_ledger_event("worker_write", {"path": "/scratch/post-result.bin"})

    with pytest.raises(PermissionError, match="work event follows Stage B completion"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())


def test_stage_b_completion_fsync_must_finish_before_total_deadline(tmp_path):
    limits = replace(
        BudgetLimits(), stage_a_wall_ns=1_200, total_wall_ns=1_500, fit_wall_ns=1_000,
    )
    supervisor, ops = _supervisor(tmp_path, limits=limits)
    ops.stage_b_completion = replace(
        ops.stage_b_completion, finished_monotonic_ns=1_400, fsynced_monotonic_ns=1_601,
    )
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    with pytest.raises(PermissionError, match="Stage B completion"):
        supervisor.finish_stage_b()

    assert supervisor.state is SupervisorState.FAILED
    ops.terminal_record_monotonic_ns = 1_700
    ops.terminal = replace(
        ops.terminal,
        terminal_closed_monotonic_ns=1_800,
        deadline_monotonic_ns=1_600,
    )
    ops.post_exit = _valid_post_exit(
        "synthetic-invocation", ops.terminal.terminal_sha256, 100, 1_800, 1_600,
    )
    late_external = dict(ops.post_exit.receipt)
    late_external.update({
        "external_terminal_detected_ticks": 50_016,
        "external_unit_inactive_ticks": 50_017,
        "external_receipt_fsynced_ticks": 50_018,
        "external_deadline_ticks": 50_015,
    })
    ops.post_exit = replace(
        ops.post_exit,
        receipt=late_external,
        observed_monotonic_ns=1_900,
        observed_external_ticks=50_019,
    )
    accepted = supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())
    assert accepted.accepted is True
    assert accepted.status == StudyStatus.INCOMPLETE_RESOURCE.value
    assert ops.stage_b_completion.fsynced_monotonic_ns > supervisor.deadline_monotonic_ns


def test_partial_startup_failure_is_quarantined_and_made_nonreusable(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.fail_volume_creation = True

    with pytest.raises(OSError, match="synthetic image creation"):
        supervisor.start()

    assert ops.events[-1] == "abort_startup"
    assert supervisor.state is SupervisorState.FAILED


def test_partial_startup_without_durable_abort_receipt_is_not_retried(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.fail_volume_creation = True
    ops.abort_receipt.failure_receipt_durable = False

    with pytest.raises(PermissionError, match="startup abort"):
        supervisor.start()

    before_retry = list(ops.events)
    with pytest.raises(RuntimeError, match="only once"):
        supervisor.start()
    assert ops.events == before_retry


def test_startup_abort_receipt_must_complete_before_invocation_deadline(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.fail_volume_creation = True
    ops.abort_receipt.completed_monotonic_ns = supervisor.limits.total_wall_ns + 101

    with pytest.raises(PermissionError, match="startup abort"):
        supervisor.start()

    assert supervisor.state is SupervisorState.FAILED


def test_stage_b_requires_durable_entry_before_same_image_expansion(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    ops.stage_b_entry = replace(ops.stage_b_entry, durable=False)

    with pytest.raises(PermissionError, match="durab"):
        supervisor.enter_stage_b(
            StageBProjection(
                candidate_rows_n=1,
                maximum_fit_rows_m=1,
                prediction_rows_s=1,
                candidate_file_bytes_b=1,
                stage_a_disk_bytes_d_a=ops.stage_a.stage_a_disk_bytes,
            ),
        )

    assert "expand_same_volume" not in ops.events
    assert supervisor.state is SupervisorState.FAILED


def test_stage_a_boundary_counts_must_be_exact_integers(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    ops.stage_a = replace(ops.stage_a, reference_roles=105.0)

    with pytest.raises(PermissionError, match="Stage A boundary"):
        supervisor.finish_stage_a()

    assert supervisor.state is SupervisorState.FAILED


def test_stage_b_expansion_must_keep_all_frozen_filesystem_identity(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    ops.expanded = replace(ops.expanded, filesystem_uuid="different-filesystem")

    with pytest.raises(PermissionError, match="identity"):
        supervisor.enter_stage_b(
            StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes),
        )

    assert "stage_b_entry_fsync" in ops.events
    assert "expand_same_volume" in ops.events
    assert "expansion_receipt_fsync" not in ops.events
    assert supervisor.state is SupervisorState.FAILED


def test_expansion_accepts_realistic_ext4_capacity_below_image_length(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    ops.expanded = replace(
        ops.expanded,
        filesystem_capacity_bytes=EXT4_CAPACITY_AFTER_4_GIB_IMAGE,
        image_length_bytes=4 * GIB,
    )

    receipt = supervisor.enter_stage_b(
        StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes),
    )

    assert receipt.filesystem_capacity_bytes == EXT4_CAPACITY_AFTER_4_GIB_IMAGE
    assert receipt.image_length_bytes == 4 * GIB
    assert supervisor.state is SupervisorState.STAGE_B_READY


def test_expansion_timestamp_requires_an_exact_integer(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    ops.expanded = replace(ops.expanded, created_monotonic_ns=1_201.0)

    with pytest.raises(PermissionError, match="exact integers"):
        supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_device", 8.0),
        ("image_inode", 99.0),
        ("filesystem_capacity_bytes", float(4 * GIB)),
        ("image_length_bytes", float(4 * GIB)),
    ],
)
def test_expansion_rejects_noninteger_identity_and_capacity_fields(field, value, tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    ops.expanded = replace(ops.expanded, **{field: value})

    with pytest.raises(PermissionError, match="exact integers"):
        supervisor.enter_stage_b(
            StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes),
        )

    assert "expansion_receipt_fsync" not in ops.events
    assert supervisor.state is SupervisorState.FAILED


class _UncheckedLifecycleProjection(StageBProjection):
    def __post_init__(self):
        pass


def test_lifecycle_rejects_stage_b_projection_subclass_before_entry(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    projection = _UncheckedLifecycleProjection(
        candidate_rows_n=0,
        maximum_fit_rows_m=0.0,
        prediction_rows_s=0,
        candidate_file_bytes_b=0,
        stage_a_disk_bytes_d_a=ops.stage_a.stage_a_disk_bytes,
    )

    with pytest.raises(ValueError, match="exact reviewed type"):
        supervisor.enter_stage_b(projection)

    assert "stage_b_entry_fsync" not in ops.events


def test_terminal_is_accepted_only_after_durable_receipt_and_inactive_empty_unit(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()

    result = supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert result.accepted is True
    assert ops.events[-2:] == ["terminal_fsync_close", "wait_inactive_then_wall_receipt"]
    assert ops.terminal_evidence["route2_supervisor_chain"] == {
        "study_id": supervisor.approval.study_id,
        "invocation_id": supervisor.invocation_id,
        "stage_a_event_sha256": ops.stage_a.event_sha256,
        "stage_a_finished_monotonic_ns": ops.stage_a.finished_monotonic_ns,
        "stage_a_fsynced_monotonic_ns": ops.stage_a.fsynced_monotonic_ns,
        "stage_b_entry_event_sha256": ops.stage_b_entry.event_sha256,
        "stage_b_entry_fsynced_monotonic_ns": ops.stage_b_entry.fsynced_monotonic_ns,
        "stage_b_expansion_event_sha256": ops.expansion_receipt.event_sha256,
        "stage_b_expansion_fsynced_monotonic_ns": ops.expansion_receipt.fsynced_monotonic_ns,
        "stage_b_completion_event_sha256": ops.stage_b_completion.event_sha256,
        "stage_b_completion_finished_monotonic_ns": ops.stage_b_completion.finished_monotonic_ns,
        "stage_b_completion_fsynced_monotonic_ns": ops.stage_b_completion.fsynced_monotonic_ns,
        "stage_b_call_event_count": ops.stage_b_completion.call_event_count,
        "stage_b_call_event_accounting_sha256": ops.stage_b_completion.call_event_accounting_sha256,
        "stage_b_result_sha256": ops.stage_b_completion.result_sha256,
    }
    assert supervisor.state is SupervisorState.ACCEPTED


def test_caller_cannot_override_terminal_stage_hash_bindings(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()

    with pytest.raises(PermissionError, match="supervisor binding"):
        supervisor.finalize(
            StudyStatus.COMPLETE.value,
            evidence={"route2_supervisor_chain": {"stage_a_event_sha256": "0" * 64}},
        )

    assert "terminal_fsync_close" not in ops.events
    assert supervisor.state is SupervisorState.STAGE_B_FINISHED


def test_terminal_record_bytes_must_hash_to_the_supervisor_chain_bound_terminal(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.corrupt_terminal_digest = True

    with pytest.raises(PermissionError, match="terminal bytes"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert ops.events[-1] == "terminal_fsync_close"
    assert supervisor.state is SupervisorState.FAILED


def test_terminal_record_must_contain_the_exact_supervisor_chain_digest(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.corrupt_terminal_chain = True

    with pytest.raises(PermissionError, match="terminal bytes"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert ops.events[-1] == "terminal_fsync_close"
    assert supervisor.state is SupervisorState.FAILED


def test_terminal_event_must_be_the_last_link_in_the_complete_ledger_chain(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.corrupt_ledger_previous = True

    with pytest.raises(PermissionError, match="ledger chain"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_monotonic_event_time_is_inside_closed_invocation(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.terminal_record_monotonic_ns = 99

    with pytest.raises(PermissionError, match="monotonic timestamp"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize(
    "corruption",
    [
        "corrupt_stage_a_payload",
        "corrupt_stage_a_payload_float_type",
        "corrupt_stage_a_payload_bool_type",
        "corrupt_stage_b_entry_payload",
        "corrupt_stage_b_expansion_payload",
        "corrupt_stage_b_completion_payload",
    ],
)
def test_terminal_chain_checks_each_stage_receipt_payload(corruption, tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    if corruption.startswith("corrupt_stage_a_payload"):
        setattr(ops, corruption, True)
    supervisor.finish_stage_a()
    if corruption in {"corrupt_stage_b_entry_payload", "corrupt_stage_b_expansion_payload"}:
        setattr(ops, corruption, True)
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    if corruption == "corrupt_stage_b_completion_payload":
        ops.corrupt_stage_b_completion_payload = True
    supervisor.finish_stage_b()

    with pytest.raises(PermissionError, match="receipt payload"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_complete_terminal_rejects_duplicate_stage_events(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.duplicate_stage_events = True

    with pytest.raises(PermissionError, match="duplicate stage event"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_wall_duration_matches_monotonic_event_time(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.corrupt_terminal_wall_duration = True

    with pytest.raises(PermissionError, match="wall duration"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_record_time_must_follow_last_stage_completion(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.terminal_record_monotonic_ns = ops.stage_b_completion.finished_monotonic_ns - 1

    with pytest.raises(PermissionError, match="last stage completion"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())


def test_terminal_replays_call_events_instead_of_trusting_completion_receipt(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    ops.omit_call_event_records = True
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()

    with pytest.raises(PermissionError, match="durable call-event accounting"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_evidence_rejects_nonstandard_json_constants(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()

    with pytest.raises(ValueError, match="finite canonical JSON"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence={"synthetic": float("nan")})

    assert "terminal_fsync_close" not in ops.events


def test_complete_cannot_be_accepted_from_stage_b_volume_expansion_alone(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))

    with pytest.raises(PermissionError, match="Stage B execution"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert "terminal_fsync_close" not in ops.events
    assert supervisor.state is SupervisorState.STAGE_B_READY


@pytest.mark.parametrize(
    "field,value",
    [("outer_roles_completed", 4), ("pooled_aggregation_calls", 0), ("pooled_gt_reads", 1)],
)
def test_incomplete_stage_b_receipt_cannot_complete(tmp_path, field, value):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    ops.stage_b_completion = replace(ops.stage_b_completion, **{field: value})

    with pytest.raises(PermissionError, match="Stage B execution"):
        supervisor.finish_stage_b()

    assert "terminal_fsync_close" not in ops.events
    assert supervisor.state is SupervisorState.FAILED


@pytest.mark.parametrize(
    "field,value",
    [("unit_inactive", False), ("cgroup_empty", False), ("terminal_reverified", False),
     ("external_receipt_durable", False)],
)
def test_terminal_rejected_without_all_post_exit_observations(tmp_path, field, value):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.post_exit = replace(ops.post_exit, **{field: value})

    with pytest.raises(PermissionError):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_clock_fields_and_outer_clock_identity_are_exact(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.terminal = replace(ops.terminal, terminal_closed_monotonic_ns=1_400.0)

    with pytest.raises(PermissionError, match="terminal ledger close"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_outer_exit_observation_clock_identity_must_match_frozen_qpc(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.post_exit = replace(ops.post_exit, qpc_frequency=ops.post_exit.qpc_frequency + 1)

    with pytest.raises(PermissionError, match="clock identity"):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    assert supervisor.state is SupervisorState.FAILED


def test_terminal_failure_cannot_be_retried_or_resealed(tmp_path):
    supervisor, ops = _supervisor(tmp_path)
    supervisor.start()
    supervisor.finish_stage_a()
    supervisor.enter_stage_b(StageBProjection(1, 1, 1, 1, ops.stage_a.stage_a_disk_bytes))
    supervisor.finish_stage_b()
    ops.post_exit = replace(ops.post_exit, cgroup_empty=False)

    with pytest.raises(PermissionError):
        supervisor.finalize(StudyStatus.COMPLETE.value, evidence=_complete_evidence())

    ops.post_exit = _valid_post_exit(
        "synthetic-invocation", ops.terminal.terminal_sha256,
        ops.terminal.invocation_started_monotonic_ns,
        ops.terminal.terminal_closed_monotonic_ns,
        ops.terminal.deadline_monotonic_ns,
    )
    before_retry = list(ops.events)
    with pytest.raises(RuntimeError, match="one-shot|closed"):
        supervisor.finalize(StudyStatus.INCOMPLETE_RESOURCE.value, evidence=_complete_evidence())

    assert ops.events == before_retry
