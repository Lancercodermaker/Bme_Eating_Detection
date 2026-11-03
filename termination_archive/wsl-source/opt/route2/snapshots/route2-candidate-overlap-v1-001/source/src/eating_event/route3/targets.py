"""Training-only one-to-one candidate target construction for Route 3."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from eating_event.a1.metrics import PredictionRecord, TruthRecord, evaluate_participants
from eating_event.a1.pipeline import Role
from eating_event.a2.execution import A2Candidate


def assign_role_targets(
    role: Role,
    rows: Sequence[A2Candidate],
    truths_by_participant: Mapping[str, Sequence[TruthRecord]],
    *,
    iou_threshold: float = 0.25,
) -> tuple[tuple[A2Candidate, ...], dict[tuple[str, str], str]]:
    """Apply the saved local one-to-one matcher within one candidate role.

    Outer candidate roles are returned label-free without looking up any truth.
    Every non-outer role uses only truths for its own scored participants.
    """

    role_id = str(role.role_id)
    if not role_id:
        raise ValueError("candidate role identity is missing")
    if any(row.role_id != role_id for row in rows):
        raise ValueError("candidate rows do not match their role identity")

    if role.inner_fold is None:
        if any(row.label is not None for row in rows):
            raise ValueError("outer candidate labels must remain null")
        return tuple(rows), {}

    participants = tuple(map(str, role.scored_participants))
    if len(set(participants)) != len(participants) or not participants:
        raise ValueError("non-outer candidate role needs unique scored participants")
    participant_set = set(participants)
    candidate_participants = {str(row.participant_id) for row in rows}
    if not candidate_participants <= participant_set:
        raise ValueError("candidate rows are outside the role's scored participants")
    candidate_ids = [str(row.candidate_id) for row in rows]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate IDs must be unique within a role")

    truths: list[TruthRecord] = []
    for participant_id in participants:
        participant_truths = tuple(truths_by_participant.get(participant_id, ()))
        if any(truth.participant_id != participant_id for truth in participant_truths):
            raise ValueError("truth participant identity differs from its map key")
        truths.extend(participant_truths)

    predictions = [
        PredictionRecord(
            prediction_id=str(row.candidate_id),
            participant_id=str(row.participant_id),
            record_id=str(row.record_id),
            session_id=str(row.session_id),
            source_segment_id=None,
            interval=row.interval,
        )
        for row in rows
    ]
    metrics = evaluate_participants(
        predictions,
        truths,
        iou_threshold=float(iou_threshold),
        participant_ids=participants,
    )
    matched_gt_by_key: dict[tuple[str, str], str] = {}
    for participant_metric in metrics.participants:
        for candidate_id, truth_id, _ in participant_metric.matched_pairs:
            matched_gt_by_key[(role_id, candidate_id)] = truth_id

    labeled = tuple(
        replace(row, label=int((role_id, str(row.candidate_id)) in matched_gt_by_key))
        for row in rows
    )
    return labeled, matched_gt_by_key
