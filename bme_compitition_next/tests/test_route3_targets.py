from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from eating_event.a1.metrics import TruthRecord
from eating_event.a2.execution import A2Candidate
from eating_event.metrics import EventInterval
from eating_event.route3.targets import assign_role_targets


def _candidate(
    candidate_id: str,
    participant_id: str,
    start_ms: int,
    end_ms: int,
    *,
    role_id: str = "candidate/outer-0/inner-0/subinner-0",
    label: int | None = 0,
) -> A2Candidate:
    return A2Candidate(
        role_id=role_id,
        candidate_id=candidate_id,
        participant_id=participant_id,
        record_id=f"record-{participant_id}",
        session_id=f"session-{participant_id}",
        component_id=f"component-{participant_id}",
        interval=EventInterval(start_ms, end_ms),
        source_16d=np.zeros(16, dtype=np.float64),
        features_26d=np.zeros(26, dtype=np.float32),
        support_indices=(),
        label=label,
    )


def _role(*, inner_fold: str | None = "inner-0", participants: tuple[str, ...] = ("p1",)):
    return SimpleNamespace(
        role_id="candidate/outer-0/inner-0/subinner-0",
        inner_fold=inner_fold,
        scored_participants=participants,
    )


def test_matching_target_uses_strict_threshold_and_one_to_one_assignment():
    role = _role()
    rows = (
        _candidate("candidate-a", "p1", 40, 140),
        _candidate("candidate-b", "p1", 10, 110),
        _candidate("candidate-at-threshold", "p1", 60, 160),
    )
    truths = {"p1": (TruthRecord("gt-1", "p1", EventInterval(0, 100)),)}

    labeled, matched_gt = assign_role_targets(role, rows, truths, iou_threshold=0.25)

    assert [row.label for row in labeled] == [0, 1, 0]
    assert matched_gt == {(role.role_id, "candidate-b"): "gt-1"}


def test_matching_targets_are_independent_per_participant():
    role = _role(participants=("p1", "p2"))
    rows = (
        _candidate("p1-candidate", "p1", 0, 100),
        _candidate("p2-candidate", "p2", 0, 100),
    )
    truths = {
        "p1": (TruthRecord("p1-gt", "p1", EventInterval(0, 100)),),
        "p2": (TruthRecord("p2-gt", "p2", EventInterval(0, 100)),),
    }

    labeled, matched_gt = assign_role_targets(role, rows, truths, iou_threshold=0.25)

    assert [row.label for row in labeled] == [1, 1]
    assert matched_gt == {
        (role.role_id, "p1-candidate"): "p1-gt",
        (role.role_id, "p2-candidate"): "p2-gt",
    }


def test_outer_role_preserves_null_labels_without_reading_truths():
    class ForbiddenTruths(dict):
        def __getitem__(self, key):
            raise AssertionError("outer GT was accessed during target construction")

    role = _role(inner_fold=None)
    rows = (_candidate("outer-candidate", "p1", 0, 100, label=None),)

    labeled, matched_gt = assign_role_targets(role, rows, ForbiddenTruths(), iou_threshold=0.25)

    assert labeled == rows
    assert labeled[0].label is None
    assert matched_gt == {}


def test_inner_role_rejects_candidates_outside_its_saved_participants():
    role = _role(participants=("p1",))
    rows = (_candidate("foreign-candidate", "p2", 0, 100),)

    with pytest.raises(ValueError, match="outside the role's scored participants"):
        assign_role_targets(role, rows, {}, iou_threshold=0.25)
