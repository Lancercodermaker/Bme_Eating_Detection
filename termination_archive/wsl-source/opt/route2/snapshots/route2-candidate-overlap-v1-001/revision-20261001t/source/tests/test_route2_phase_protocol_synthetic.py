"""No-data checks for the Route 2 phase-worker protocol.

These tests construct only synthetic intervals and receipts. They never open
Route 2 score, cache, candidate, GT, or model artifacts.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import random

import numpy as np
import pytest

from eating_event.a1.metrics import PredictionRecord, TruthRecord, evaluate_participants
from eating_event.metrics import EventInterval
from eating_event.route2_candidate_overlap.budget import AppendOnlyLedger, CALL_CEILINGS, PredictionFreezeReceipt
from eating_event.route2_candidate_overlap.contracts import StudyStage
from eating_event.route2_candidate_overlap.gt_provider import FrozenPredictionReceipt, TruthReadScope
from eating_event.route2_candidate_overlap.phase_worker import (
    LabelCandidate, commit_metric_gt_ids, execute_phase_operation,
)
from eating_event.route2_candidate_overlap.stage_b import (
    StageBAdapter, VerifierDataInsufficient, _RoleRows, _fit_arrays,
)


def test_pooled_reduction_matches_a1_evaluator_on_100_synthetic_five_fold_cases() -> None:
    rng = random.Random(20260929)
    synthetic_key = b"synthetic-only-controller-secret-key-v1"
    participants = tuple(f"p{index}" for index in range(5))
    for trial in range(100):
        predictions: list[PredictionRecord] = []
        truths: list[TruthRecord] = []
        for participant in participants:
            for index in range(rng.randrange(4)):
                start = rng.randrange(0, 5000, 50)
                duration = rng.randrange(1, 2000, 50)
                truths.append(TruthRecord(
                    f"{participant}:{index}", participant,
                    EventInterval(start, start + duration),
                ))
            for index in range(rng.randrange(4)):
                start = rng.randrange(0, 5000, 50)
                duration = rng.randrange(1, 8000, 50)
                predictions.append(PredictionRecord(
                    f"{participant}:{index}", participant, "r", "s", None,
                    EventInterval(start, start + duration),
                ))
        folds = tuple(
            evaluate_participants(
                tuple(row for row in predictions if row.participant_id == participant),
                tuple(row for row in truths if row.participant_id == participant),
                participant_ids=(participant,),
            )
            for participant in participants
        )
        expected = commit_metric_gt_ids(
            evaluate_participants(predictions, truths, participant_ids=participants), synthetic_key,
        )
        actual = StageBAdapter._pooled_from_disjoint_folds(
            tuple(commit_metric_gt_ids(fold, synthetic_key) for fold in folds), participants,
        )
        assert actual == expected, trial


def test_training_phase_uses_strict_iou_without_returning_truth_rows(tmp_path: Path) -> None:
    scope = TruthReadScope(
        stage=StudyStage.TRAIN_LABELS, outer_id="o1", role_ids=("candidate/o1/i1/s1/subinner",),
        participants=("p1",), eligibility_field="training_eligibility",
        consumer="candidate_labeler", role_graph_sha256="a" * 64,
        participant_scope_attestation="b" * 64,
    )
    row = {
        "participant_id": "p1", "event_index": 0, "start_ms": 0,
        "end_ms": 1000, "duration_ms": 1000, "training_eligibility": True,
    }
    content = (json.dumps(row, separators=(",", ":")) + "\n").encode("utf-8")
    view = tmp_path / "synthetic-training.jsonl"
    view.write_bytes(content)
    result = execute_phase_operation(
        scope=scope, view_path=view, expected_view_sha256=hashlib.sha256(content).hexdigest(),
        gt_commitment_key=b"synthetic-only-controller-secret-key-v1",
        operation="training_labels",
        candidates=(LabelCandidate("exact-0.25", "p1", 0, 250), LabelCandidate("over-0.25", "p1", 0, 260)),
    )
    assert result.labels == (0, 1)
    assert len(result.positive_gt_commitments) == 1
    assert result.positive_gt_commitments[0] != hashlib.sha256(
        b"route2-positive-gt-v1|p1:0"
    ).hexdigest()
    assert not hasattr(result, "truths")


def test_outer_metric_replaces_all_gt_ids_with_keyed_commitments() -> None:
    prediction = PredictionRecord("pred", "p1", "r", "s", None, EventInterval(0, 1000))
    truths = (
        TruthRecord("p1:matched", "p1", EventInterval(0, 1000)),
        TruthRecord("p1:unmatched", "p1", EventInterval(3000, 4000)),
    )
    metric = evaluate_participants((prediction,), truths, participant_ids=("p1",))
    key = b"synthetic-only-controller-secret-key-v1"
    committed = commit_metric_gt_ids(metric, key)
    assert (committed.tp, committed.fp, committed.fn, committed.f1) == (metric.tp, metric.fp, metric.fn, metric.f1)
    assert committed.participants[0].matched_pairs[0][0] == "pred"
    assert committed.participants[0].matched_pairs[0][1] != "p1:matched"
    assert committed.participants[0].unmatched_truth_ids[0] != "p1:unmatched"
    assert "p1:matched" not in repr(committed) and "p1:unmatched" not in repr(committed)
    assert committed != commit_metric_gt_ids(metric, b"a-different-synthetic-controller-secret")


def _inner_receipts(count: int) -> tuple[PredictionFreezeReceipt, ...]:
    result = []
    for role_index in range(4):
        role = f"candidate/o1/i{role_index}/inner"
        for threshold in ("0.10", "0.25", "0.50"):
            result.append(PredictionFreezeReceipt(
                phase="inner", role_id=role, outer_id="o1", threshold=threshold,
                prediction_path=f"/synthetic/{role_index}-{threshold}.jsonl",
                prediction_sha256="a" * 64, predict_attempt=role_index + 1,
                decoder_attempt=len(result) + 1, ledger_event_sha256=f"{len(result) + 1:064x}",
            ))
    return tuple(result[:count])


def test_inner_gt_release_requires_all_12_frozen_prediction_receipts() -> None:
    roles = tuple(f"candidate/o1/i{index}/inner" for index in range(4))
    with pytest.raises(ValueError, match="each role and threshold"):
        FrozenPredictionReceipt(
            outer_id="o1", role_ids=roles, thresholds=(0.10, 0.25, 0.50),
            predictions=_inner_receipts(11),
        )
    frozen = FrozenPredictionReceipt(
        outer_id="o1", role_ids=roles, thresholds=(0.10, 0.25, 0.50),
        predictions=_inner_receipts(12),
    )
    scope = TruthReadScope(
        stage=StudyStage.INNER_EVALUATION, outer_id="o1", role_ids=roles,
        participants=("p1",), eligibility_field="evaluation_eligibility",
        consumer="threshold_selector", prediction_receipt=frozen,
        role_graph_sha256="a" * 64, participant_scope_attestation="b" * 64,
    )

    class SyntheticLedger:
        _stage_b_volume_expanded = True
        _active_gt_release = None

        def __init__(self) -> None:
            self.checked: list[str] = []
            self.events: list[str] = []

        def _truth_scope_digest(self, value: TruthReadScope) -> str:
            return AppendOnlyLedger._truth_scope_digest(value)

        def require_frozen_prediction(self, item: PredictionFreezeReceipt, **_: object) -> None:
            self.checked.append(item.ledger_event_sha256)

        def append(self, event: str, _: dict[str, object]) -> str:
            self.events.append(event)
            return "c" * 64

    ledger = SyntheticLedger()
    assert AppendOnlyLedger.record_gt_release(ledger, scope) == "c" * 64
    assert len(ledger.checked) == 12
    assert ledger.events == ["gt_phase_released"]


def test_empty_training_candidates_stop_as_g3_before_fit_reservation() -> None:
    empty = _RoleRows(
        role=object(), candidates=(), candidate_ids=(),
        features=np.empty((0, 26), dtype=np.float32), labels=(),
    )
    with pytest.raises(VerifierDataInsufficient, match="G3"):
        _fit_arrays((empty,), ("p1",))


def test_frozen_evaluator_call_shape_is_15_inner_5_outer_1_pooled() -> None:
    source = Path(StageBAdapter.__module__.replace(".", "/") + ".py")
    if not source.is_file():
        source = Path(__file__).resolve().parents[1] / "src/eating_event/route2_candidate_overlap/stage_b.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    adapter = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "StageBAdapter")
    run = next(node for node in adapter.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    evaluator_calls = [
        node for node in ast.walk(run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "invoke_call"
        and node.args and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "event_evaluator"
    ]
    call_sites = {ast.unparse(node.args[1]) for node in evaluator_calls}
    assert call_sites == {
        "f'threshold/{outer_id}/{threshold:.2f}'",
        "f'outer/{outer_id}'",
        "'pooled/outer'",
    }
    # Four inner predictions are pooled once per threshold; they are not four
    # separate evaluator calls. Each outer fold therefore uses 3 + 1 calls.
    assert 5 * (3 + 1) + 1 == CALL_CEILINGS["event_evaluator"] == 21
