"""GT operations for a short-lived, single-view Stage B process.

The OS phase runner must expose exactly one approved six-field view to this
process, wait for process exit, and revoke that view before returning a result.
This module has no authority to mount a view or approve an experiment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import hmac
import json
from pathlib import Path
from typing import Literal, Sequence

from eating_event.a1.metrics import (
    AggregateMetrics,
    PredictionRecord,
    TruthRecord,
    evaluate_participants,
)
from eating_event.metrics import EventInterval, interval_iou

from .contracts import RegisteredFile, StudyStage
from .control_matches import read_control_final_matches
from .gt_provider import TruthReadScope, stage_gt_fields


@dataclass(frozen=True, slots=True)
class LabelCandidate:
    candidate_id: str
    participant_id: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class TrainingPhaseResult:
    labels: tuple[int, ...]
    positive_gt_commitments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InnerSelectionPhaseResult:
    """Only the two numbers allowed to influence threshold choice leave the child."""

    f1: float | None
    fp: int
    eligible_gt_count: int
    prediction_count: int


@dataclass(frozen=True, slots=True)
class EvaluationPhaseResult:
    metric: AggregateMetrics
    eligible_gt_count: int
    candidate_covered_gt: int | None
    reference_candidate_covered_gt: int | None = None
    candidate_added_gt_commitments: tuple[str, ...] = ()
    candidate_lost_gt_commitments: tuple[str, ...] = ()
    control_matched_gt_commitments: tuple[str, ...] | None = None
    matched_gt_added_commitments: tuple[str, ...] = ()
    matched_gt_lost_commitments: tuple[str, ...] = ()


PhaseOperation = Literal["training_labels", "inner_evaluator", "outer_evaluator"]
PhaseResult = TrainingPhaseResult | InnerSelectionPhaseResult | EvaluationPhaseResult


def _gt_commitment(event_id: str, key: bytes) -> str:
    return hmac.new(key, b"route2-gt-identity-v1\0" + event_id.encode("utf-8"), hashlib.sha256).hexdigest()


def commit_metric_gt_ids(metric: AggregateMetrics, key: bytes) -> AggregateMetrics:
    """Replace every GT event ID in an A1 metric with a keyed commitment."""

    return replace(metric, participants=tuple(
        replace(
            participant,
            matched_pairs=tuple(
                (prediction_id, _gt_commitment(gt_id, key), iou)
                for prediction_id, gt_id, iou in participant.matched_pairs
            ),
            unmatched_truth_ids=tuple(
                _gt_commitment(gt_id, key) for gt_id in participant.unmatched_truth_ids
            ),
        )
        for participant in metric.participants
    ))


def _read_exact_view(
    *, scope: TruthReadScope, view_path: Path, expected_sha256: str,
) -> tuple[TruthRecord, ...]:
    """Read only the bound view, checking its bytes before semantic access."""

    if scope.stage in (StudyStage.STAGE_A_REFERENCE, StudyStage.STAGE_A_TREATMENT):
        raise PermissionError("Stage A has no GT view")
    if view_path.is_symlink() or not view_path.is_file():
        raise PermissionError("phase GT view must be an ordinary mounted file")
    digest = hashlib.sha256()
    with view_path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
        if digest.hexdigest() != expected_sha256.lower():
            raise PermissionError("phase GT view differs from its reviewed digest")
        stream.seek(0)
        allowed = set(scope.participants)
        seen: set[tuple[str, int]] = set()
        truths: list[TruthRecord] = []
        expected_fields = set(stage_gt_fields(scope.stage))
        while raw := stream.readline(1024 * 1024 + 1):
            if len(raw) > 1024 * 1024:
                raise ValueError("phase GT row exceeds the frozen row bound")
            row = json.loads(raw)
            if not isinstance(row, dict) or set(row) != expected_fields:
                raise PermissionError("phase GT row has an unapproved field")
            participant = row["participant_id"]
            if type(participant) is not str or participant not in allowed:
                raise PermissionError("phase GT participant escapes its role")
            if type(row[scope.eligibility_field]) is not bool:
                raise ValueError("phase GT eligibility must be a boolean")
            if any(type(row[field]) is not int for field in (
                "event_index", "start_ms", "end_ms", "duration_ms",
            )):
                raise ValueError("phase GT index and times must be integers")
            index = row["event_index"]
            key = (participant, index)
            if index < 0 or key in seen:
                raise ValueError("phase GT identity repeats or is negative")
            seen.add(key)
            start_ms, end_ms = row["start_ms"], row["end_ms"]
            if end_ms <= start_ms or row["duration_ms"] != end_ms - start_ms:
                raise ValueError("phase GT interval or duration is invalid")
            if row[scope.eligibility_field]:
                truths.append(TruthRecord(
                    f"{participant}:{index}", participant, EventInterval(start_ms, end_ms),
                ))
    return tuple(sorted(truths, key=lambda truth: truth.event_id))


def execute_phase_operation(
    *,
    scope: TruthReadScope,
    view_path: Path,
    expected_view_sha256: str,
    gt_commitment_key: bytes,
    operation: PhaseOperation,
    candidates: Sequence[LabelCandidate] = (),
    reference_candidates: Sequence[LabelCandidate] | None = None,
    control_final_matches: RegisteredFile | None = None,
    control_final_matches_path: Path | None = None,
    control_metrics_sha256: str | None = None,
    predictions: Sequence[PredictionRecord] = (),
    participant_ids: Sequence[str] = (),
) -> PhaseResult:
    """Run one GT-consuming operation inside the controller's single-view child.

    The caller must validate the frozen role graph and prediction ledger before
    spawning this child. No raw truth row or interval is returned to the parent.
    """

    expected_stage = {
        "training_labels": StudyStage.TRAIN_LABELS,
        "inner_evaluator": StudyStage.INNER_EVALUATION,
        "outer_evaluator": StudyStage.OUTER_EVALUATION,
    }.get(operation)
    if expected_stage is None or scope.stage != expected_stage:
        raise PermissionError("phase operation differs from its GT release stage")
    if type(gt_commitment_key) is not bytes or len(gt_commitment_key) < 32:
        raise PermissionError("GT identity commitments require a controller-only key")
    if operation == "outer_evaluator":
        if (type(control_final_matches) is not RegisteredFile or control_final_matches_path is None
                or type(control_metrics_sha256) is not str):
            raise PermissionError("outer evaluation requires the saved A2-004 final match projection")
    elif any(value is not None for value in (control_final_matches, control_final_matches_path, control_metrics_sha256)):
        raise PermissionError("historical final matches are forbidden outside outer evaluation")
    if operation == "training_labels":
        if predictions or participant_ids or reference_candidates is not None or any(
            candidate.participant_id not in scope.participants
            or type(candidate.start_ms) is not int
            or type(candidate.end_ms) is not int
            or candidate.end_ms <= candidate.start_ms
            for candidate in candidates
        ):
            raise PermissionError("training label payload escapes its candidate role")
    else:
        if candidates and operation == "inner_evaluator":
            raise PermissionError("inner evaluation does not accept candidate intervals")
        if operation == "inner_evaluator" and reference_candidates is not None:
            raise PermissionError("inner evaluation does not accept reference candidate intervals")
        if operation == "outer_evaluator" and reference_candidates is None:
            raise PermissionError("outer evaluation requires a reference candidate snapshot")
        if set(participant_ids) != set(scope.participants) or len(participant_ids) != len(scope.participants):
            raise PermissionError("evaluation participant scope differs from the frozen role")
        if any(prediction.participant_id not in scope.participants for prediction in predictions):
            raise PermissionError("evaluation prediction escapes its held-out scope")
        if any(
            candidate.participant_id not in scope.participants
            or type(candidate.start_ms) is not int
            or type(candidate.end_ms) is not int
            or candidate.end_ms <= candidate.start_ms
            for candidate in candidates
        ):
            raise PermissionError("evaluation candidate escapes its held-out scope")
        if reference_candidates is not None and any(
            candidate.participant_id not in scope.participants
            or type(candidate.start_ms) is not int
            or type(candidate.end_ms) is not int
            or candidate.end_ms <= candidate.start_ms
            for candidate in reference_candidates
        ):
            raise PermissionError("reference candidate escapes its held-out scope")
    truths = _read_exact_view(
        scope=scope, view_path=view_path, expected_sha256=expected_view_sha256,
    )
    if operation == "training_labels":
        by_participant: dict[str, list[TruthRecord]] = defaultdict(list)
        for truth in truths:
            by_participant[truth.participant_id].append(truth)
        labels: list[int] = []
        positive_ids: set[str] = set()
        for candidate in candidates:
            interval = EventInterval(candidate.start_ms, candidate.end_ms)
            matched = {
                truth.event_id
                for truth in by_participant.get(candidate.participant_id, ())
                if interval_iou(interval, truth.interval) > 0.25
            }
            labels.append(int(bool(matched)))
            positive_ids.update(matched)
        # Stable across training roles under the controller-only key. No raw GT
        # identity or interval leaves the child; A2 needs only the distinct count.
        commitments = tuple(sorted(
            _gt_commitment(item, gt_commitment_key)
            for item in positive_ids
        ))
        return TrainingPhaseResult(tuple(labels), commitments)
    metric = evaluate_participants(
        predictions, truths, iou_threshold=0.25, long_fp_ms=600000,
        participant_ids=tuple(participant_ids),
    )
    if operation == "inner_evaluator":
        return InnerSelectionPhaseResult(metric.f1, metric.fp, len(truths), len(predictions))
    control_matched = set(read_control_final_matches(
        scope=scope, registered=control_final_matches, path=control_final_matches_path,
        source_metrics_sha256=control_metrics_sha256,
    ))
    if not control_matched <= {truth.event_id for truth in truths}:
        raise PermissionError("saved A2-004 final matches include an ineligible or foreign outer GT")
    treatment_matched = {
        truth_id for participant in metric.participants
        for _, truth_id, _ in participant.matched_pairs
    }
    control_commitments = tuple(sorted(_gt_commitment(item, gt_commitment_key) for item in control_matched))
    matched_additions = tuple(sorted(
        _gt_commitment(item, gt_commitment_key) for item in treatment_matched - control_matched
    ))
    matched_losses = tuple(sorted(
        _gt_commitment(item, gt_commitment_key) for item in control_matched - treatment_matched
    ))
    treatment_covered = {
        truth.event_id
        for truth in truths
        if any(
            candidate.participant_id == truth.participant_id
            and interval_iou(EventInterval(candidate.start_ms, candidate.end_ms), truth.interval) > 0.25
            for candidate in candidates
        )
    }
    assert reference_candidates is not None
    reference_covered = {
        truth.event_id
        for truth in truths
        if any(
            candidate.participant_id == truth.participant_id
            and interval_iou(EventInterval(candidate.start_ms, candidate.end_ms), truth.interval) > 0.25
            for candidate in reference_candidates
        )
    }
    additions = tuple(sorted(
        _gt_commitment(event_id, gt_commitment_key)
        for event_id in treatment_covered - reference_covered
    ))
    losses = tuple(sorted(
        _gt_commitment(event_id, gt_commitment_key)
        for event_id in reference_covered - treatment_covered
    ))
    return EvaluationPhaseResult(
        commit_metric_gt_ids(metric, gt_commitment_key), len(truths),
        len(treatment_covered), len(reference_covered), additions, losses,
        control_commitments, matched_additions, matched_losses,
    )
