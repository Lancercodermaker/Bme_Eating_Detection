from eating_event.a1.metrics import (
    PredictionRecord,
    TruthRecord,
    evaluate_participants,
    evaluate_quality,
)
from eating_event.metrics import EventInterval


def truth(pid, eid, start=0, end=100000):
    return TruthRecord(eid, pid, EventInterval(start, end))


def pred(pid, eid, start=0, end=100000):
    return PredictionRecord(eid, pid, "r", "s", None, EventInterval(start, end))


def test_matching_is_partitioned_by_participant_and_counts_are_summed():
    result = evaluate_participants(
        predictions=[pred("p2", "pred-p2")],
        truths=[truth("p1", "gt-p1")],
    )
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)


def test_strict_iou_boundary_and_duplicate_predictions():
    result = evaluate_participants(
        predictions=[pred("p", "a", 75000, 175000), pred("p", "b")],
        truths=[truth("p", "gt")],
    )
    assert result.tp == 1
    assert result.fp == 1
    assert result.fn == 0
    boundary = evaluate_participants(
        predictions=[pred("p", "edge", 75000, 175000)],
        truths=[truth("p", "gt")],
    )
    assert boundary.tp == 0


def test_empty_truth_and_no_matches_use_null_f1_and_mae():
    result = evaluate_participants(predictions=[], truths=[])
    assert result.f1 is None
    assert result.start_mae_ms is None
    assert result.end_mae_ms is None
    no_match = evaluate_participants(predictions=[pred("p", "x")], truths=[truth("p", "g", 300000, 400000)])
    assert no_match.start_mae_ms is None


def test_quality_uses_same_unmatched_predictions_and_separates_numeric_from_stage():
    result = evaluate_participants(
        predictions=[pred("p", "tp"), pred("p", "long-fp", 1000000, 2000000)],
        truths=[truth("p", "gt")],
    )
    quality = evaluate_quality([result], outer_fold_f1=[0.66, 0.2, 0.7, 0.1, 0.3])
    assert quality.long_fp_fraction == 1.0
    assert quality.numeric_minimum is True
    assert quality.stage_minimum is False
