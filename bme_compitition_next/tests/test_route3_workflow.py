from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from eating_event.a2.execution import A2Candidate
from eating_event.metrics import EventInterval
from eating_event.route3.workflow import build_fit_compositions, validate_fit_compositions


def _role(role_id: str, kind: str, inner_fold: str | None, subinner_fold: str | None):
    return SimpleNamespace(
        role_id=role_id,
        kind=kind,
        outer_fold="outer-0",
        inner_fold=inner_fold,
        subinner_fold=subinner_fold,
    )


def _candidate(role_id: str, candidate_id: str, label: int) -> A2Candidate:
    return A2Candidate(
        role_id=role_id,
        candidate_id=candidate_id,
        participant_id=f"participant-{candidate_id}",
        record_id=f"record-{candidate_id}",
        session_id=f"session-{candidate_id}",
        component_id=f"component-{candidate_id}",
        interval=EventInterval(0, 100),
        source_16d=np.zeros(16, dtype=np.float64),
        features_26d=np.zeros(26, dtype=np.float32),
        support_indices=(),
        label=label,
    )


def test_fit_compositions_match_the_nested_role_graph():
    roles = (
        _role("candidate/outer-0/inner-0/subinner-0", "candidate", "inner-0", "subinner-0"),
        _role("candidate/outer-0/inner-0/subinner-1", "candidate", "inner-0", "subinner-1"),
        _role("candidate/outer-0/inner-0", "candidate", "inner-0", None),
        _role("candidate/outer-0/inner-1", "candidate", "inner-1", None),
        _role("verifier/outer-0/inner-0", "verifier", "inner-0", None),
        _role("verifier/outer-0/outer", "verifier", None, None),
    )
    rows = {
        "candidate/outer-0/inner-0/subinner-0": (_candidate("candidate/outer-0/inner-0/subinner-0", "s0", 1),),
        "candidate/outer-0/inner-0/subinner-1": (_candidate("candidate/outer-0/inner-0/subinner-1", "s1", 0),),
        "candidate/outer-0/inner-0": (_candidate("candidate/outer-0/inner-0", "i0", 1),),
        "candidate/outer-0/inner-1": (_candidate("candidate/outer-0/inner-1", "i1", 0),),
    }
    target_gt = {
        "candidate/outer-0/inner-0/subinner-0": {("candidate/outer-0/inner-0/subinner-0", "s0"): "gt-s0"},
        "candidate/outer-0/inner-0/subinner-1": {},
        "candidate/outer-0/inner-0": {("candidate/outer-0/inner-0", "i0"): "gt-i0"},
        "candidate/outer-0/inner-1": {},
    }

    compositions = build_fit_compositions(roles, rows, target_gt)

    assert [item.verifier_role_id for item in compositions] == [
        "verifier/outer-0/inner-0",
        "verifier/outer-0/outer",
    ]
    assert compositions[0].candidate_role_ids == (
        "candidate/outer-0/inner-0/subinner-0",
        "candidate/outer-0/inner-0/subinner-1",
    )
    assert compositions[0].positive_gt_ids == ("gt-s0",)
    assert compositions[1].candidate_role_ids == (
        "candidate/outer-0/inner-0",
        "candidate/outer-0/inner-1",
    )
    assert compositions[1].positive_gt_ids == ("gt-i0",)


def test_fit_precheck_rejects_any_role_that_fails_g3():
    roles = (
        _role("candidate/outer-0/inner-0/subinner-0", "candidate", "inner-0", "subinner-0"),
        _role("verifier/outer-0/inner-0", "verifier", "inner-0", None),
    )
    row = _candidate("candidate/outer-0/inner-0/subinner-0", "s0", 1)
    compositions = build_fit_compositions(
        roles,
        {"candidate/outer-0/inner-0/subinner-0": (row,)},
        {"candidate/outer-0/inner-0/subinner-0": {("candidate/outer-0/inner-0/subinner-0", "s0"): "gt-s0"}},
    )

    with pytest.raises(ValueError, match="G3"):
        validate_fit_compositions(compositions, expected_fit_count=1)
