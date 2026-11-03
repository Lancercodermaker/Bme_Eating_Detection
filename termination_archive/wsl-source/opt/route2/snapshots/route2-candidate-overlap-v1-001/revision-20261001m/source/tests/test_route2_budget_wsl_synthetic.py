"""No-data checks for Route 2's Linux admission accounting."""

import json
import os
import threading
import time
from dataclasses import asdict, replace
import hashlib

import pytest

from eating_event.route2_candidate_overlap.budget import (
    AppendOnlyLedger,
    BudgetGuard,
    BudgetLimits,
    ResourceSnapshot,
    StageBProjection,
    require_stage_filesystem,
    require_precreate_order,
    require_stage_b_entry,
    require_two_layer_startup_free,
)
from eating_event.route2_candidate_overlap.contracts import StudyStage, StudyStatus
from eating_event.route2_candidate_overlap.gt_provider import TruthReadScope
from eating_event.route2_candidate_overlap.linux_supervisor import (
    DurableLedgerReceipt,
    ImageVolumeReceipt,
    Route2Supervisor,
    StageABoundaryReceipt,
    StageBExecutionReceipt,
    TerminalCloseReceipt,
)
from eating_event.route2_candidate_overlap.stage_b import StageBResult
from eating_event.a1.metrics import AggregateMetrics, QualityDecision

_BINARY = getattr(os, "O_BINARY", 0)


def test_terminal_ledger_record_persists_monotonic_event_time(tmp_path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "synthetic.jsonl", tmp_path / "synthetic.lock", tmp_path / "synthetic")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"monotonic_ns": started, "invocation_id": "synthetic"})

    ledger.terminal("INCOMPLETE_RESOURCE", evidence={}, invocation_started_monotonic_ns=started)
    ledger.close()
    terminal = json.loads(ledger.path.read_bytes().splitlines()[-1])
    payload = terminal["entry"]["payload"]
    terminal_ns = payload.get("monotonic_ns")

    assert type(terminal_ns) is int
    assert started <= terminal_ns <= time.monotonic_ns()
    assert payload["wall_ns"] == terminal_ns - started
    assert type(payload["epoch_ns"]) is int and payload["epoch_ns"] > 0


def test_terminal_rejects_nonstandard_json_before_ledger_write(tmp_path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "synthetic.jsonl", tmp_path / "synthetic.lock", tmp_path / "synthetic")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"monotonic_ns": started, "invocation_id": "synthetic"})
    before = ledger.path.read_bytes()

    with pytest.raises(ValueError):
        ledger.terminal(
            "INCOMPLETE_RESOURCE",
            evidence={"nonstandard": float("nan")},
            invocation_started_monotonic_ns=started,
        )

    assert ledger.path.read_bytes() == before
    ledger.close()


def test_budget_ledger_unicode_bytes_match_supervisor_canonical_json(tmp_path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "unicode.jsonl", tmp_path / "unicode.lock", tmp_path / "study")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    ledger.append("synthetic_unicode", {"path_label": "研究/餐\u00e9", "tag": "niño"})
    ledger.close()

    raw = ledger.path.read_bytes()
    record = json.loads(raw)
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    escaped = json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    assert raw == canonical
    assert raw != escaped


@pytest.mark.parametrize("field,value", [
    ("reference_roles", 105.0),
    ("treatment_roles", True),
])
def test_stage_a_writer_rejects_non_integer_role_counts_before_append(tmp_path, field, value) -> None:
    ledger = AppendOnlyLedger(tmp_path / "strict-a.jsonl", tmp_path / "strict-a.lock", tmp_path / "study")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"invocation_id": "synthetic", "monotonic_ns": started})
    before = ledger.path.read_bytes()
    payload = {
        "invocation_id": "synthetic",
        "reference_roles": 105,
        "treatment_roles": 105,
        "different_treatment_roles": 1,
        "stage_a_disk_bytes": 0,
        "finished_monotonic_ns": started + 1,
    }
    payload[field] = value

    with pytest.raises(PermissionError, match="Stage A boundary"):
        ledger.mark_stage_a_finished(payload)

    assert ledger.path.read_bytes() == before
    ledger.close()


@pytest.mark.parametrize("field,value", [
    ("verifier_fit_calls", 25.0),
    ("decoder_calls", True),
])
def test_stage_b_completion_writer_rejects_non_integer_quotas_before_append(tmp_path, field, value) -> None:
    ledger = AppendOnlyLedger(tmp_path / "strict-b.jsonl", tmp_path / "strict-b.lock", tmp_path / "study")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"invocation_id": "synthetic", "monotonic_ns": started})
    ledger.mark_stage_a_finished({
        "invocation_id": "synthetic",
        "reference_roles": 105,
        "treatment_roles": 105,
        "different_treatment_roles": 1,
        "stage_a_disk_bytes": 0,
        "finished_monotonic_ns": started + 1,
    })
    entry = ledger.mark_stage_b_entry({}, invocation_id="synthetic")
    ledger.mark_stage_b_volume_expanded(
        entry.event_sha256, {"synthetic": True}, invocation_id="synthetic",
    )
    payload = {
        "invocation_id": "synthetic",
        "inner_roles_completed": 20,
        "outer_roles_completed": 5,
        "verifier_fit_calls": 25,
        "verifier_predict_calls": 25,
        "decoder_calls": 65,
        "evaluator_calls": 21,
        "pooled_aggregation_completed": True,
        "pooled_gt_reads": 0,
        "finished_monotonic_ns": started + 2,
        "result_sha256": "a" * 64,
    }
    payload[field] = value
    before = ledger.path.read_bytes()

    with pytest.raises(PermissionError, match="fixed quota"):
        ledger.mark_stage_b_complete(payload)

    assert ledger.path.read_bytes() == before
    ledger.close()


def test_budget_guard_stage_events_match_supervisor_receipt_schema(tmp_path) -> None:
    """Exercise real ledger writers and compare their records to consumer schemas."""

    limits = BudgetLimits()
    root = tmp_path / "synthetic-study"
    ledger = AppendOnlyLedger(
        tmp_path / "synthetic-budget.jsonl", tmp_path / "synthetic.lock", root,
    )
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"invocation_id": "synthetic-invocation", "monotonic_ns": started})

    initial = _snapshot(9 * 1024**3, 9 * 1024**3)
    expanded = ResourceSnapshot(
        **{
            **asdict(initial),
            "study_fs_capacity_bytes": limits.total_disk_bytes,
            "study_image_length_bytes": limits.total_disk_bytes,
        }
    )

    class SyntheticEnforcer:
        def current_snapshot(self, study_root):
            return initial

        def expand_after_stage_b_entry(self, study_root, budget_limits, entry_event_sha256):
            return expanded

    guard = BudgetGuard(
        limits,
        ledger,
        SyntheticEnforcer(),
        root,
        approved_controller_sha256="a" * 64,
        approved_write_volumes=(str(tmp_path),),
        invocation_started_monotonic_ns=started,
        invocation_id="synthetic-invocation",
    )
    guard._started = True
    guard._rss_ceiling_bytes = limits.rss_cap_bytes
    guard._volume_identity_snapshot = initial
    role_ids = {f"role-{index:03d}" for index in range(105)}
    ledger._reference_roles = set(role_ids)
    ledger._reference_passed = set(role_ids)
    ledger._treatment_roles = set(role_ids)
    ledger._treatment_finished = {role_id: object() for role_id in role_ids}
    ledger._different_treatment_roles = {"role-000"}

    guard.finish_stage_a()
    projection = StageBProjection(
        candidate_rows_n=0,
        maximum_fit_rows_m=0,
        prediction_rows_s=0,
        candidate_file_bytes_b=0,
        stage_a_disk_bytes_d_a=initial.study_disk_current_bytes,
    )
    guard.require_stage_b_entry(projection)

    empty_metrics = AggregateMetrics(
        tp=0, fp=0, fn=234, precision=0.0, recall=0.0, f1=0.0,
        start_mae_ms=None, end_mae_ms=None, matched_count=0,
        participants=(), long_fp_count=0, long_fp_fraction=0.0,
    )
    quality = QualityDecision(
        pooled_f1=0.0, numeric_minimum=False, numeric_ideal=False,
        majority_folds=False, quality_per_fold=False, stage_minimum=False,
        stage_ideal=False, long_fp_fraction=0.0,
        worst_start_mae_ms=None, worst_end_mae_ms=None,
    )
    result = StageBResult(
        status=StudyStatus.COMPLETE,
        selected_thresholds=tuple((f"inner-{index:02d}", 0.25) for index in range(20)),
        pooled_f1=0.0,
        pooled_gt_count=234,
        pooled_metrics=empty_metrics,
        fold_metrics=(empty_metrics,) * 5,
        quality=quality,
        fit_provenance=(),
        matched_gt_commitments=(),
        outer_candidate_counts=tuple((f"outer-{index}", 0) for index in range(5)),
        outer_candidate_covered_gt=tuple((f"outer-{index}", 0) for index in range(5)),
        verifier_fit_attempts=25,
        verifier_prediction_batches=25,
        decoder_calls=65,
        evaluator_calls=21,
        pooled_aggregation_completed=True,
        pooled_gt_reads=0,
    )
    guard.finish_stage_b(result)

    with pytest.raises(RuntimeError, match="cannot continue after the durable Stage B completion"):
        ledger.append("worker_write", {"path": "/scratch/after-result.bin"})

    records = [json.loads(line) for line in ledger.path.read_bytes().splitlines()]
    records_by_event = {record["entry"]["event"]: record for record in records}
    by_event = {event: record["entry"] for event, record in records_by_event.items()}
    stage_a = by_event["stage_a_finished"]["payload"]
    entry = by_event["stage_b_entry_passed"]["payload"]
    expansion = by_event["stage_b_volume_expanded"]["payload"]
    completion = by_event["stage_b_complete"]["payload"]

    assert set(stage_a) == {
        "invocation_id", "reference_roles", "treatment_roles",
        "different_treatment_roles", "stage_a_disk_bytes", "finished_monotonic_ns",
    }
    assert entry == {
        "invocation_id": "synthetic-invocation",
        "projection": asdict(projection),
    }
    assert expansion["invocation_id"] == "synthetic-invocation"
    assert expansion["entry_event_sha256"] == records_by_event["stage_b_entry_passed"]["sha256"]
    assert set(expansion["volume"]) == set(ImageVolumeReceipt.__dataclass_fields__)
    assert completion == {
        "invocation_id": "synthetic-invocation",
        "inner_roles_completed": 20,
        "outer_roles_completed": 5,
        "verifier_fit_calls": 25,
        "verifier_predict_calls": 25,
        "decoder_calls": 65,
        "evaluator_calls": 21,
        "pooled_aggregation_completed": True,
        "pooled_gt_reads": 0,
        "finished_monotonic_ns": completion["finished_monotonic_ns"],
        "result_sha256": hashlib.sha256(
            json.dumps(asdict(result), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }

    supervisor = object.__new__(Route2Supervisor)
    supervisor.invocation_id = "synthetic-invocation"
    supervisor.stage_a = StageABoundaryReceipt(
        **stage_a,
        fsynced_monotonic_ns=guard._stage_a_event_receipt.fsynced_monotonic_ns,
        event_sha256=records_by_event["stage_a_finished"]["sha256"],
        durable=True,
    )
    supervisor._stage_b_projection = projection
    supervisor.stage_b_entry = DurableLedgerReceipt(
        invocation_id="synthetic-invocation",
        event_sha256=records_by_event["stage_b_entry_passed"]["sha256"],
        fsynced_monotonic_ns=guard._stage_b_entry_event_receipt.fsynced_monotonic_ns,
        durable=True,
    )
    supervisor.volume = ImageVolumeReceipt(**expansion["volume"])
    supervisor.expansion_receipt = DurableLedgerReceipt(
        invocation_id="synthetic-invocation",
        event_sha256=records_by_event["stage_b_volume_expanded"]["sha256"],
        fsynced_monotonic_ns=guard._stage_b_expansion_event_receipt.fsynced_monotonic_ns,
        durable=True,
    )
    supervisor.stage_b_completion = StageBExecutionReceipt(
        invocation_id=completion["invocation_id"],
        inner_roles_completed=completion["inner_roles_completed"],
        outer_roles_completed=completion["outer_roles_completed"],
        verifier_fit_calls=completion["verifier_fit_calls"],
        verifier_predict_calls=completion["verifier_predict_calls"],
        decoder_calls=completion["decoder_calls"],
        evaluator_calls=completion["evaluator_calls"],
        pooled_aggregation_completed=completion["pooled_aggregation_completed"],
        pooled_gt_reads=completion["pooled_gt_reads"],
        finished_monotonic_ns=completion["finished_monotonic_ns"],
        fsynced_monotonic_ns=guard._stage_b_completion_event_receipt.fsynced_monotonic_ns,
        event_sha256=records_by_event["stage_b_complete"]["sha256"],
        result_sha256=completion["result_sha256"],
        durable=True,
    )
    expected = supervisor._expected_stage_payloads()
    assert expected == {
        "stage_a_finished": stage_a,
        "stage_b_entry_passed": entry,
        "stage_b_volume_expanded": expansion,
        "stage_b_complete": completion,
    }
    chain = {
        "study_id": "route2-candidate-overlap-v1-001",
        "invocation_id": "synthetic-invocation",
        "stage_a_event_sha256": records_by_event["stage_a_finished"]["sha256"],
        "stage_a_finished_monotonic_ns": stage_a["finished_monotonic_ns"],
        "stage_a_fsynced_monotonic_ns": guard._stage_a_event_receipt.fsynced_monotonic_ns,
        "stage_b_entry_event_sha256": records_by_event["stage_b_entry_passed"]["sha256"],
        "stage_b_entry_fsynced_monotonic_ns": guard._stage_b_entry_event_receipt.fsynced_monotonic_ns,
        "stage_b_expansion_event_sha256": records_by_event["stage_b_volume_expanded"]["sha256"],
        "stage_b_expansion_fsynced_monotonic_ns": guard._stage_b_expansion_event_receipt.fsynced_monotonic_ns,
        "stage_b_completion_event_sha256": records_by_event["stage_b_complete"]["sha256"],
        "stage_b_completion_finished_monotonic_ns": completion["finished_monotonic_ns"],
        "stage_b_completion_fsynced_monotonic_ns": guard._stage_b_completion_event_receipt.fsynced_monotonic_ns,
        "stage_b_result_sha256": completion["result_sha256"],
    }
    chain_sha256 = hashlib.sha256(
        json.dumps(chain, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    evidence = {
        "stage_b_result": asdict(result),
        "route2_supervisor_chain": chain,
        "route2_supervisor_chain_sha256": chain_sha256,
    }
    ledger._call_counts = {
        "verifier_fit": 25,
        "verifier_predict": 25,
        "decoder": 65,
        "event_evaluator": 21,
    }
    ledger.terminal(
        StudyStatus.COMPLETE.value,
        evidence=evidence,
        invocation_started_monotonic_ns=started,
    )
    ledger.close()
    ledger_records = ledger.path.read_bytes().splitlines(keepends=True)
    terminal_record = json.loads(ledger_records[-1])
    terminal = TerminalCloseReceipt(
        invocation_id="synthetic-invocation",
        unit_name="route2-synthetic.service",
        status=StudyStatus.COMPLETE.value,
        terminal_sha256=terminal_record["sha256"],
        terminal_binding_sha256=chain_sha256,
        invocation_started_monotonic_ns=started,
        terminal_closed_monotonic_ns=ledger.closed_at_monotonic_ns,
        deadline_monotonic_ns=started + limits.total_wall_ns,
        ledger_fsynced=True,
        ledger_closed=True,
        no_active_gt_view=True,
        no_active_worker=True,
        terminal_record_bytes=ledger_records[-1],
        ledger_bytes=b"".join(ledger_records),
    )
    Route2Supervisor._verify_terminal_record(
        terminal,
        StudyStatus.COMPLETE.value,
        evidence,
        chain_sha256,
        expected,
        started,
        started + limits.stage_a_wall_ns,
        started + limits.total_wall_ns,
    )


def _snapshot(guest_free: int, host_free: int) -> ResourceSnapshot:
    return ResourceSnapshot(
        process_tree_rss_bytes=0,
        study_disk_peak_bytes=0,
        compute_workers=1,
        available_ram_bytes=8 * 1024**3,
        study_disk_current_bytes=0,
        guest_backing_free_bytes=guest_free,
        guest_backing_mount_id="80",
        guest_backing_device="/dev/sdd",
        windows_vhdx_path=r"C:\\Users\\synthetic\\ext4.vhdx",
        windows_volume_id="synthetic-volume-guid",
        windows_volume_free_bytes=host_free,
        study_mount_id="scratch-mount-1",
        study_device="/dev/loop999",
        study_fs_capacity_bytes=2 * 1024**3,
        study_fs_uuid="synthetic-fs-uuid",
        study_loop_device="/dev/loop999",
        study_image_path="/var/lib/route2-scratch/synthetic.ext4",
        study_image_dev=42,
        study_image_inode=99,
        study_image_length_bytes=2 * 1024**3,
        study_image_allocated_bytes=0,
    )


def _active_budget_guard(tmp_path, *, limits=None):
    limits = limits or BudgetLimits()
    root = tmp_path / "synthetic-study"
    ledger = AppendOnlyLedger(
        tmp_path / "synthetic-budget.jsonl", tmp_path / "synthetic.lock", root,
    )
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"invocation_id": "synthetic-invocation", "monotonic_ns": started})
    initial = _snapshot(9 * 1024**3, 9 * 1024**3)
    expanded = ResourceSnapshot(**{
        **asdict(initial),
        "study_fs_capacity_bytes": limits.total_disk_bytes,
        "study_image_length_bytes": limits.total_disk_bytes,
    })

    class SyntheticEnforcer:
        def current_snapshot(self, study_root):
            return initial

        def expand_after_stage_b_entry(self, study_root, budget_limits, entry_event_sha256):
            return expanded

    guard = BudgetGuard(
        limits,
        ledger,
        SyntheticEnforcer(),
        root,
        approved_controller_sha256="a" * 64,
        approved_write_volumes=(str(tmp_path),),
        invocation_started_monotonic_ns=started,
        invocation_id="synthetic-invocation",
    )
    guard._started = True
    guard._rss_ceiling_bytes = limits.rss_cap_bytes
    guard._volume_identity_snapshot = initial
    role_ids = {f"role-{index:03d}" for index in range(105)}
    ledger._reference_roles = set(role_ids)
    ledger._reference_passed = set(role_ids)
    ledger._treatment_roles = set(role_ids)
    ledger._treatment_finished = {role_id: object() for role_id in role_ids}
    ledger._different_treatment_roles = {"role-000"}
    projection = StageBProjection(0, 0, 0, 0, initial.study_disk_current_bytes)
    return guard, ledger, initial, projection


def test_late_stage_a_boundary_permanently_blocks_guard_activity(tmp_path, monkeypatch):
    guard, ledger, _initial, _projection = _active_budget_guard(
        tmp_path, limits=replace(BudgetLimits(), stage_a_wall_ns=1_000_000_000),
    )
    append_stage_a = ledger.mark_stage_a_finished

    def late_stage_a(payload):
        receipt = append_stage_a(payload)
        return replace(
            receipt,
            fsynced_monotonic_ns=guard._invocation_started_ns + guard.limits.stage_a_wall_ns + 1,
        )

    monkeypatch.setattr(ledger, "mark_stage_a_finished", late_stage_a)
    with pytest.raises(RuntimeError, match="Stage A boundary append/fsync"):
        guard.finish_stage_a()

    with pytest.raises(PermissionError, match="boundary failure"):
        with guard.activity("must-not-run", stage_a=False):
            pytest.fail("activity entered after the late Stage A boundary")


def test_late_stage_b_entry_permanently_blocks_guard_activity(tmp_path, monkeypatch):
    guard, ledger, _initial, projection = _active_budget_guard(
        tmp_path, limits=replace(BudgetLimits(), stage_a_wall_ns=1_000_000_000),
    )
    guard.finish_stage_a()
    append_stage_b_entry = ledger.mark_stage_b_entry

    def late_stage_b_entry(projection_payload, *, invocation_id):
        receipt = append_stage_b_entry(projection_payload, invocation_id=invocation_id)
        return replace(
            receipt,
            fsynced_monotonic_ns=guard._invocation_started_ns + guard.limits.stage_a_wall_ns + 1,
        )

    monkeypatch.setattr(ledger, "mark_stage_b_entry", late_stage_b_entry)
    with pytest.raises(RuntimeError, match="Stage B entry append/fsync"):
        guard.require_stage_b_entry(projection)

    with pytest.raises(PermissionError, match="boundary failure"):
        with guard.activity("must-not-run", stage_a=False):
            pytest.fail("activity entered after the late Stage B entry")


def test_stage_b_completion_freezes_guard_activity(tmp_path):
    guard, _ledger, _initial, _projection = _active_budget_guard(tmp_path)
    # A completion receipt is enough to exercise the producer-side freeze; this
    # synthetic test does not run a Stage B worker or inspect project data.
    from eating_event.route2_candidate_overlap.budget import DurableEventReceipt

    guard._stage_b_admitted = True
    guard._stage_a_finished_ns = guard._invocation_started_ns + 1
    guard._stage_b_completion_event_receipt = DurableEventReceipt("a" * 64, time.monotonic_ns())

    with pytest.raises(PermissionError, match="completion receipt"):
        with guard.activity("must-not-run", stage_a=False):
            pytest.fail("activity entered after the Stage B completion receipt")


class _UncheckedProjection(StageBProjection):
    def __post_init__(self):
        pass


def test_projection_helper_rejects_subclass_and_noninteger_fields():
    projection = _UncheckedProjection(0.0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="exact reviewed type"):
        require_stage_b_entry(
            projection,
            limits=BudgetLimits(),
            frozen_rss_ceiling_bytes=BudgetLimits().rss_cap_bytes,
            stage_a_hard_lines_met=True,
        )


def test_projection_helper_rejects_mutated_exact_instance_fields():
    projection = StageBProjection(0, 0, 0, 0, 0)
    object.__setattr__(projection, "maximum_fit_rows_m", 0.0)

    with pytest.raises(ValueError, match="exact integers"):
        require_stage_b_entry(
            projection,
            limits=BudgetLimits(),
            frozen_rss_ceiling_bytes=BudgetLimits().rss_cap_bytes,
            stage_a_hard_lines_met=True,
        )


def test_budget_guard_rejects_projection_subclass_before_entry_event(tmp_path):
    guard, ledger, _initial, _projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    projection = _UncheckedProjection(0, 0, 0, 0, 0.0)

    with pytest.raises(ValueError, match="exact reviewed type"):
        guard.require_stage_b_entry(projection)

    assert "stage_b_entry_passed" not in [
        json.loads(line)["entry"]["event"] for line in ledger.path.read_bytes().splitlines()
    ]


@pytest.mark.parametrize("guest_free,host_free", [
    (8 * 1024**3 - 1, 9 * 1024**3),
    (9 * 1024**3, 8 * 1024**3 - 1),
])
def test_both_backing_layers_must_have_eight_gib(guest_free: int, host_free: int) -> None:
    with pytest.raises(RuntimeError, match="free"):
        require_two_layer_startup_free(_snapshot(guest_free, host_free), BudgetLimits())


def test_virtual_free_does_not_substitute_for_host_free() -> None:
    snapshot = _snapshot(1_000 * 1024**3, 9 * 1024**3)
    require_two_layer_startup_free(snapshot, BudgetLimits())


def test_identity_required_for_two_layer_check() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    object.__setattr__(snapshot, "windows_volume_id", "")
    with pytest.raises(PermissionError, match="identity"):
        require_two_layer_startup_free(snapshot, BudgetLimits())


def test_stage_a_filesystem_capacity_is_an_os_gate() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    expected = _snapshot(9 * 1024**3, 9 * 1024**3)
    require_stage_filesystem(snapshot, expected, 2 * 1024**3)
    object.__setattr__(snapshot, "study_fs_capacity_bytes", 2 * 1024**3 + 1)
    with pytest.raises(RuntimeError, match="capacity"):
        require_stage_filesystem(snapshot, expected, 2 * 1024**3)


def test_stage_transition_cannot_switch_devices() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    expected = _snapshot(9 * 1024**3, 9 * 1024**3)
    with pytest.raises(PermissionError, match="mount"):
        object.__setattr__(snapshot, "study_fs_uuid", "another-fs")
        require_stage_filesystem(snapshot, expected, 4 * 1024**3)


def test_two_layer_free_must_precede_image_creation() -> None:
    floor = BudgetLimits().startup_free_disk_bytes
    require_precreate_order(100, 110, 120, floor, floor, floor)
    with pytest.raises(PermissionError, match="pre-create"):
        require_precreate_order(100, 120, 110, floor, floor, floor)
    with pytest.raises(RuntimeError, match="free"):
        require_precreate_order(100, 110, 120, floor, floor - 1, floor)


def test_training_gt_release_requires_durable_unrevoked_event(tmp_path) -> None:
    """A fresh ledger object reconstructs the same gate from scratch bytes."""

    study_root = tmp_path / "synthetic-study"
    ledger_path = tmp_path / "synthetic-budget.jsonl"
    lock_path = tmp_path / "synthetic.lock"
    ledger = AppendOnlyLedger(ledger_path, lock_path, study_root)
    ledger._fd = os.open(ledger_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"invocation_id": "synthetic-invocation", "monotonic_ns": started})
    ledger.mark_stage_a_finished({
        "invocation_id": "synthetic-invocation",
        "reference_roles": 105,
        "treatment_roles": 105,
        "different_treatment_roles": 1,
        "stage_a_disk_bytes": 0,
        "finished_monotonic_ns": started + 1,
    })
    scope = TruthReadScope(
        stage=StudyStage.TRAIN_LABELS,
        outer_id="synthetic-outer",
        role_ids=("synthetic-role",),
        participants=("synthetic-participant",),
        eligibility_field="training_eligibility",
        consumer="candidate_labeler",
        role_graph_sha256="a" * 64,
        participant_scope_attestation="b" * 64,
    )
    entry_receipt = ledger.mark_stage_b_entry({}, invocation_id="synthetic-invocation")
    entry_hash = entry_receipt.event_sha256
    assert len(entry_hash) == 64
    with pytest.raises(PermissionError, match="Stage B"):
        ledger.record_gt_release(scope)
    ledger.mark_stage_b_volume_expanded(
        entry_hash,
        {"study_mount_id": "scratch-mount-1"},
        invocation_id="synthetic-invocation",
    )
    release_hash = ledger.record_gt_release(scope)
    with pytest.raises(RuntimeError, match="active GT"):
        ledger.terminal(
            "INCOMPLETE_RESOURCE",
            evidence={},
            invocation_started_monotonic_ns=time.monotonic_ns() - 1,
        )
    ledger.close()
    fresh_reader = AppendOnlyLedger(ledger_path, lock_path, study_root)
    fresh_reader.require_gt_release(scope, release_hash)

    ledger._fd = os.open(ledger_path, os.O_WRONLY | os.O_APPEND | _BINARY)
    ledger.record_gt_revoke(scope, release_hash, "c" * 64)
    ledger.close()
    with pytest.raises(PermissionError, match="revoked"):
        fresh_reader.require_gt_release(scope, release_hash)
