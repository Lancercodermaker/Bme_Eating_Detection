"""No-data checks for Route 2's Linux admission accounting."""

import json
import os
import threading
import time
from dataclasses import asdict, replace
import hashlib
from pathlib import Path

import pytest

from eating_event.route2_candidate_overlap.budget import (
    AppendOnlyLedger,
    BudgetGuard,
    BudgetLimits,
    CALL_CEILINGS,
    ResourceSnapshot,
    StageBProjection,
    _replay_call_event_accounting,
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
from eating_event.route2_candidate_overlap.stage_b import FitSummary, StageBResult
from eating_event.a1.metrics import AggregateMetrics, QualityDecision

_BINARY = getattr(os, "O_BINARY", 0)


def _synthetic_fixed_call_role_ids() -> dict[str, tuple[str, ...]]:
    fits: list[str] = []
    predictions: list[str] = []
    decoders: list[str] = []
    evaluators: list[str] = []
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
            decoders.extend((role_id, role_id, role_id))
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


def _synthetic_stage_b_projection(*, stage_a_disk_bytes: int = 0) -> StageBProjection:
    outer_ids = tuple(f"outer-{index:02d}" for index in range(5))
    return StageBProjection(
        candidate_rows_n=0,
        maximum_fit_rows_m=0,
        prediction_rows_s=0,
        candidate_file_bytes_b=0,
        stage_a_disk_bytes_d_a=stage_a_disk_bytes,
        role_graph_sha256="a" * 64,
        outer_role_ids=tuple(f"candidate/{outer_id}/outer" for outer_id in outer_ids),
        inner_role_ids_by_outer=tuple(
            (
                outer_id,
                tuple(f"candidate/{outer_id}/inner-{inner_index:02d}/inner" for inner_index in range(4)),
            )
            for outer_id in outer_ids
        ),
        fit_training_roles_by_verifier=tuple(
            entry
            for outer_id in outer_ids
            for entry in (
                *(
                    (
                        f"verifier/{outer_id}/inner-{inner_index:02d}",
                        tuple(
                            f"candidate/{outer_id}/inner-{inner_index:02d}/subinner-{child_index:02d}/subinner"
                            for child_index in range(4)
                        ),
                    )
                    for inner_index in range(4)
                ),
                (
                    f"verifier/{outer_id}/outer",
                    tuple(f"candidate/{outer_id}/inner-{inner_index:02d}/inner" for inner_index in range(4)),
                ),
            )
        ),
    )


def _synthetic_global_call_order(outer_prefix="outer"):
    calls = []
    for outer_index in range(5):
        outer_id = f"{outer_prefix}-{outer_index:02d}"
        for inner_index in range(4):
            role_id = f"candidate/{outer_id}/inner-{inner_index:02d}/inner"
            calls.extend((
                ("verifier_fit", f"verifier/{outer_id}/inner-{inner_index:02d}"),
                ("verifier_predict", role_id),
                *(("decoder", role_id),) * 3,
            ))
        calls.extend(("event_evaluator", f"threshold/{outer_id}/{threshold}") for threshold in ("0.10", "0.25", "0.50"))
        calls.extend((
            ("verifier_fit", f"verifier/{outer_id}/outer"),
            ("verifier_predict", f"candidate/{outer_id}/outer"),
            ("decoder", f"candidate/{outer_id}/outer"),
            ("event_evaluator", f"outer/{outer_id}"),
        ))
    calls.append(("pooled_reduction", "pooled/outer"))
    return tuple(calls)


def _synthetic_fit_event_payload(role_id, attempt):
    model_name = f"{hashlib.sha256(role_id.encode('utf-8')).hexdigest()}.pickle"
    _verifier, outer_id, fit_role = role_id.split("/")
    if fit_role == "outer":
        training_roles = [
            f"candidate/{outer_id}/inner-{inner_index:02d}/inner" for inner_index in range(4)
        ]
    else:
        training_roles = [
            f"candidate/{outer_id}/{fit_role}/subinner-{child_index:02d}/subinner"
            for child_index in range(4)
        ]
    return {
        "verifier_role_id": role_id,
        "training_candidate_roles": training_roles,
        "fit_participants": [],
        "candidate_count": 0,
        "positive_candidate_count": 0,
        "positive_participant_count": 0,
        "distinct_positive_canonical_gt_count": 0,
        "ordered_candidate_keys_sha256": "1" * 64,
        "feature_matrix_sha256": "2" * 64,
        "training_label_join_sha256": "3" * 64,
        "model_path": f"/synthetic/verifier-models/{model_name}",
        "model_sha256": "4" * 64,
        "fit_attempt": attempt,
    }


def _synthetic_ordered_call_events(outer_prefix="outer"):
    events = []
    attempts = dict.fromkeys(CALL_CEILINGS, 0)
    for kind, role_id in _synthetic_global_call_order(outer_prefix):
        attempts[kind] += 1
        attempt = attempts[kind]
        ceiling = CALL_CEILINGS[kind]
        events.extend((
            ("call_reserved", {"kind": kind, "role_id": role_id, "attempt": attempt, "ceiling": ceiling}),
            ("call_started", {"kind": kind, "role_id": role_id, "attempt": attempt}),
            ("call_finished", {"kind": kind, "role_id": role_id, "attempt": attempt, "outcome": "succeeded"}),
        ))
        if kind == "verifier_fit":
            events.append(("verifier_fit_provenance", _synthetic_fit_event_payload(role_id, attempt)))
    return events


def test_call_event_replay_rejects_generic_role_ids_even_when_quotas_match() -> None:
    events: list[tuple[str, dict[str, object]]] = []
    for kind, ceiling in CALL_CEILINGS.items():
        for attempt in range(1, ceiling + 1):
            role_id = f"synthetic/{kind}"
            events.extend((
                ("call_reserved", {"kind": kind, "role_id": role_id, "attempt": attempt, "ceiling": ceiling}),
                ("call_started", {"kind": kind, "role_id": role_id, "attempt": attempt}),
                ("call_finished", {"kind": kind, "role_id": role_id, "attempt": attempt, "outcome": "succeeded"}),
            ))

    with pytest.raises(PermissionError, match="role schedule"):
        _replay_call_event_accounting(events, ledger_tail_sha256="a" * 64)


def test_call_event_replay_rejects_valid_role_quotas_in_wrong_global_order() -> None:
    events: list[tuple[str, dict[str, object]]] = []
    for kind, role_ids in _synthetic_fixed_call_role_ids().items():
        ceiling = CALL_CEILINGS[kind]
        for attempt, role_id in enumerate(role_ids, start=1):
            events.extend((
                ("call_reserved", {"kind": kind, "role_id": role_id, "attempt": attempt, "ceiling": ceiling}),
                ("call_started", {"kind": kind, "role_id": role_id, "attempt": attempt}),
                ("call_finished", {"kind": kind, "role_id": role_id, "attempt": attempt, "outcome": "succeeded"}),
            ))

    with pytest.raises(PermissionError, match="global call order"):
        _replay_call_event_accounting(events, ledger_tail_sha256="b" * 64)


def test_call_event_replay_binds_roles_to_the_frozen_graph_projection() -> None:
    projection = _synthetic_stage_b_projection()
    events = _synthetic_ordered_call_events(outer_prefix="attacker")

    with pytest.raises(PermissionError, match="frozen role graph"):
        _replay_call_event_accounting(
            events,
            ledger_tail_sha256="c" * 64,
            expected_role_ids_by_kind=projection.call_role_ids_by_kind(),
            expected_role_graph_sha256=projection.role_graph_sha256,
            expected_fit_training_roles_by_verifier=dict(projection.fit_training_roles_by_verifier),
        )


@pytest.mark.parametrize("mutation", ["missing", "extra", "unknown_field", "model_path", "training_role"])
def test_call_event_replay_rejects_unbound_or_malformed_fit_provenance(mutation) -> None:
    events = _synthetic_ordered_call_events()
    fit_index = next(index for index, item in enumerate(events) if item[0] == "verifier_fit_provenance")
    if mutation == "missing":
        del events[fit_index]
    elif mutation == "extra":
        events.insert(fit_index + 1, events[fit_index])
    elif mutation == "unknown_field":
        events[fit_index][1]["unreviewed"] = True
    elif mutation == "model_path":
        events[fit_index][1]["model_path"] = "/synthetic/verifier-models/wrong.pickle"
    else:
        events[fit_index][1]["training_candidate_roles"][0] = "candidate/outer-00/forged/subinner-00/subinner"

    with pytest.raises(PermissionError, match="fit provenance|durable call-event accounting"):
        _replay_call_event_accounting(
            events,
            ledger_tail_sha256="d" * 64,
            expected_role_ids_by_kind=_synthetic_stage_b_projection().call_role_ids_by_kind(),
            expected_role_graph_sha256=_synthetic_stage_b_projection().role_graph_sha256,
            expected_fit_training_roles_by_verifier=dict(_synthetic_stage_b_projection().fit_training_roles_by_verifier),
        )


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
        "evaluator_calls": 20,
        "pooled_aggregation_calls": 1,
        "pooled_aggregation_completed": True,
        "pooled_gt_reads": 0,
        "call_event_count": 408,
        "call_event_accounting_sha256": "b" * 64,
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

    _wait_for_monotonic_tick_after(started)
    guard.finish_stage_a()
    projection = _synthetic_stage_b_projection(stage_a_disk_bytes=initial.study_disk_current_bytes)
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
        selected_thresholds=tuple((f"outer-{index:02d}", 0.25) for index in range(5)),
        pooled_f1=0.0,
        pooled_gt_count=234,
        pooled_metrics=empty_metrics,
        fold_metrics=(empty_metrics,) * 5,
        quality=quality,
        fit_provenance=_synthetic_fit_summaries(root),
        matched_gt_commitments=(),
        outer_candidate_counts=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_candidate_covered_gt=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_reference_candidate_covered_gt=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_candidate_added_gt_commitments=tuple((f"outer-{index:02d}", ()) for index in range(5)),
        outer_candidate_lost_gt_commitments=tuple((f"outer-{index:02d}", ()) for index in range(5)),
        verifier_fit_attempts=25,
        verifier_prediction_batches=25,
        decoder_calls=65,
        evaluator_calls=20,
        pooled_aggregation_calls=1,
        pooled_aggregation_completed=True,
        pooled_gt_reads=0,
    )
    with pytest.raises(PermissionError, match="durable call-event accounting"):
        guard.finish_stage_b(result)

    _append_fixed_call_events(ledger)
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
        "projection": json.loads(json.dumps(asdict(projection))),
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
        "evaluator_calls": 20,
        "pooled_aggregation_calls": 1,
        "pooled_aggregation_completed": True,
        "pooled_gt_reads": 0,
        "call_event_count": 408,
        "call_event_accounting_sha256": completion["call_event_accounting_sha256"],
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
        pooled_aggregation_calls=completion["pooled_aggregation_calls"],
        pooled_aggregation_completed=completion["pooled_aggregation_completed"],
        pooled_gt_reads=completion["pooled_gt_reads"],
        call_event_count=completion["call_event_count"],
        call_event_accounting_sha256=completion["call_event_accounting_sha256"],
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
        "stage_b_call_event_count": completion["call_event_count"],
        "stage_b_call_event_accounting_sha256": completion["call_event_accounting_sha256"],
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


def _wait_for_monotonic_tick_after(started_ns: int) -> None:
    """Make strict timestamp-order tests portable to coarse Windows clocks."""

    while time.monotonic_ns() <= started_ns:
        time.sleep(0.001)


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
    projection = _synthetic_stage_b_projection(stage_a_disk_bytes=initial.study_disk_current_bytes)
    _wait_for_monotonic_tick_after(started)
    return guard, ledger, initial, projection


def _synthetic_stage_b_result(study_root=None):
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
    return StageBResult(
        status=StudyStatus.COMPLETE,
        selected_thresholds=tuple((f"outer-{index:02d}", 0.25) for index in range(5)),
        pooled_f1=0.0,
        pooled_gt_count=234,
        pooled_metrics=empty_metrics,
        fold_metrics=(empty_metrics,) * 5,
        quality=quality,
        fit_provenance=_synthetic_fit_summaries(study_root),
        matched_gt_commitments=(),
        outer_candidate_counts=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_candidate_covered_gt=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_reference_candidate_covered_gt=tuple((f"outer-{index:02d}", 0) for index in range(5)),
        outer_candidate_added_gt_commitments=tuple((f"outer-{index:02d}", ()) for index in range(5)),
        outer_candidate_lost_gt_commitments=tuple((f"outer-{index:02d}", ()) for index in range(5)),
        verifier_fit_attempts=25,
        verifier_prediction_batches=25,
        decoder_calls=65,
        evaluator_calls=20,
        pooled_aggregation_calls=1,
        pooled_aggregation_completed=True,
        pooled_gt_reads=0,
    )


def _synthetic_fit_summaries(study_root=None) -> tuple[FitSummary, ...]:
    fit_roles = _synthetic_fixed_call_role_ids()["verifier_fit"]
    if study_root is None:
        study_root = Path.cwd() / "synthetic-study-without-ledger"
    model_dir = study_root / "verifier-models"
    model_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for attempt, role_id in enumerate(fit_roles, start=1):
        _verifier, outer_id, fit_role = role_id.split("/")
        if fit_role == "outer":
            training_roles = tuple(
                f"candidate/{outer_id}/inner-{inner_index:02d}/inner" for inner_index in range(4)
            )
        else:
            training_roles = tuple(
                f"candidate/{outer_id}/{fit_role}/subinner-{child_index:02d}/subinner"
                for child_index in range(4)
            )
        model_bytes = f"synthetic-model-{role_id}".encode("utf-8")
        model_path = model_dir / f"{hashlib.sha256(role_id.encode('utf-8')).hexdigest()}.pickle"
        if model_path.exists():
            assert model_path.read_bytes() == model_bytes
        else:
            model_path.write_bytes(model_bytes)
        summaries.append(FitSummary(
            verifier_role_id=role_id,
            training_candidate_roles=training_roles,
            fit_participants=(),
            candidate_count=0,
            positive_candidate_count=0,
            positive_participant_count=0,
            distinct_positive_canonical_gt_count=0,
            ordered_candidate_keys_sha256="1" * 64,
            feature_matrix_sha256="2" * 64,
            training_label_join_sha256="3" * 64,
            model_path=str(model_path.resolve()),
            model_sha256=hashlib.sha256(model_bytes).hexdigest(),
            fit_attempt=attempt,
        ))
    return tuple(summaries)


def _append_fixed_call_events(ledger):
    summaries = {
        item.verifier_role_id: item for item in _synthetic_fit_summaries(ledger.study_root)
    }
    calls = []
    for outer_index in range(5):
        outer_id = f"outer-{outer_index:02d}"
        inner_roles = tuple(
            f"candidate/{outer_id}/inner-{inner_index:02d}/inner" for inner_index in range(4)
        )
        for inner_index, role_id in enumerate(inner_roles):
            calls.extend((
                ("verifier_fit", f"verifier/{outer_id}/inner-{inner_index:02d}"),
                ("verifier_predict", role_id),
                *(("decoder", role_id),) * 3,
            ))
        calls.extend(("event_evaluator", f"threshold/{outer_id}/{threshold}") for threshold in ("0.10", "0.25", "0.50"))
        calls.extend((
            ("verifier_fit", f"verifier/{outer_id}/outer"),
            ("verifier_predict", f"candidate/{outer_id}/outer"),
            ("decoder", f"candidate/{outer_id}/outer"),
            ("event_evaluator", f"outer/{outer_id}"),
        ))
    calls.append(("pooled_reduction", "pooled/outer"))
    for kind, role_id in calls:
        attempt = ledger._call_counts[kind] + 1
        ledger.reserve_call(kind, role_id)
        ledger.start_call(kind, role_id, attempt)
        ledger.finish_call(kind, role_id, attempt, succeeded=True)
        if kind == "verifier_fit":
            ledger.append("verifier_fit_provenance", asdict(summaries[role_id]))


def test_stage_b_completion_rejects_fit_summary_not_bound_to_durable_provenance(tmp_path):
    guard, ledger, _initial, projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    guard.require_stage_b_entry(projection)
    _append_fixed_call_events(ledger)
    result = _synthetic_stage_b_result(guard.study_root)
    changed = replace(
        result.fit_provenance[7],
        model_sha256="f" * 64,
    )
    tampered_result = replace(
        result,
        fit_provenance=(*result.fit_provenance[:7], changed, *result.fit_provenance[8:]),
    )

    with pytest.raises(PermissionError, match="fit provenance"):
        guard.finish_stage_b(tampered_result)


def test_stage_b_completion_rejects_self_consistent_outer_ids_outside_frozen_graph(tmp_path):
    guard, ledger, _initial, projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    guard.require_stage_b_entry(projection)
    _append_fixed_call_events(ledger)
    result = _synthetic_stage_b_result(guard.study_root)
    fake_outer_ids = tuple(f"invented-{index:02d}" for index in range(5))
    def replace_outer_ids(items):
        return tuple((fake_outer_ids[index], *item[1:]) for index, item in enumerate(items))
    tampered_result = replace(
        result,
        selected_thresholds=tuple((outer_id, threshold) for outer_id, (_, threshold) in zip(fake_outer_ids, result.selected_thresholds, strict=True)),
        outer_candidate_counts=replace_outer_ids(result.outer_candidate_counts),
        outer_candidate_covered_gt=replace_outer_ids(result.outer_candidate_covered_gt),
        outer_reference_candidate_covered_gt=replace_outer_ids(result.outer_reference_candidate_covered_gt),
        outer_candidate_added_gt_commitments=replace_outer_ids(result.outer_candidate_added_gt_commitments),
        outer_candidate_lost_gt_commitments=replace_outer_ids(result.outer_candidate_lost_gt_commitments),
    )

    with pytest.raises(PermissionError, match="exact outer folds"):
        guard.finish_stage_b(tampered_result)


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


def test_late_stage_b_expansion_permanently_blocks_guard_activity(tmp_path, monkeypatch):
    guard, ledger, _initial, projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    append_expansion = ledger.mark_stage_b_volume_expanded

    def late_expansion(entry_hash, volume, *, invocation_id):
        receipt = append_expansion(entry_hash, volume, invocation_id=invocation_id)
        return replace(
            receipt,
            fsynced_monotonic_ns=guard._invocation_started_ns + guard.limits.total_wall_ns + 1,
        )

    monkeypatch.setattr(ledger, "mark_stage_b_volume_expanded", late_expansion)
    with pytest.raises(RuntimeError, match="Stage B expansion append/fsync"):
        guard.require_stage_b_entry(projection)

    with pytest.raises(PermissionError, match="boundary failure"):
        with guard.activity("must-not-run", stage_a=False):
            pytest.fail("activity entered after the late Stage B expansion")


def test_late_stage_b_completion_permanently_blocks_guard_activity(tmp_path, monkeypatch):
    guard, ledger, _initial, projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    guard.require_stage_b_entry(projection)
    _append_fixed_call_events(ledger)
    append_completion = ledger.mark_stage_b_complete

    def late_completion(payload):
        receipt = append_completion(payload)
        return replace(
            receipt,
            fsynced_monotonic_ns=guard._invocation_started_ns + guard.limits.total_wall_ns + 1,
        )

    monkeypatch.setattr(ledger, "mark_stage_b_complete", late_completion)
    with pytest.raises(RuntimeError, match="Stage B completion append/fsync"):
        guard.finish_stage_b(_synthetic_stage_b_result(guard.study_root))

    with pytest.raises(PermissionError, match="boundary failure"):
        with guard.activity("must-not-run", stage_a=False):
            pytest.fail("activity entered after the late Stage B completion")


def test_late_stage_b_completion_terminal_preserves_committed_result(tmp_path, monkeypatch):
    guard, ledger, _initial, projection = _active_budget_guard(tmp_path)
    guard.finish_stage_a()
    guard.require_stage_b_entry(projection)
    _append_fixed_call_events(ledger)
    append_completion = ledger.mark_stage_b_complete

    def late_completion(payload):
        receipt = append_completion(payload)
        return replace(
            receipt,
            fsynced_monotonic_ns=guard._invocation_started_ns + guard.limits.total_wall_ns + 1,
        )

    monkeypatch.setattr(ledger, "mark_stage_b_complete", late_completion)
    result = _synthetic_stage_b_result(guard.study_root)
    with pytest.raises(RuntimeError, match="Stage B completion append/fsync"):
        guard.finish_stage_b(result)

    assert guard.finalize(
        "INCOMPLETE_RESOURCE", evidence={"exception_type": "RuntimeError"},
    ) == "INCOMPLETE_RESOURCE"
    terminal = json.loads(ledger.path.read_bytes().splitlines()[-1])
    evidence = terminal["entry"]["payload"]["evidence"]
    assert evidence["stage_b_result"] == json.loads(json.dumps(asdict(result)))


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
