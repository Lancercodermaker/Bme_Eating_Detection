import pytest
from eating_event.a1.contracts import A1Config
from eating_event.a1.metrics import PredictionRecord, TruthRecord, evaluate_participants
from eating_event.metrics import EventInterval


def test_mae_is_weighted_by_matches():
    predictions, truths = [], []
    for person, count, error in [('a', 1, 1000), ('b', 9, 0)]:
        for i in range(count):
            start = i * 100000
            truths.append(TruthRecord(f'{person}{i}', person, EventInterval(start, start+10000)))
            predictions.append(PredictionRecord(f'{person}{i}', person, 'r', 's', None,
                                               EventInterval(start+error, start+10000+error)))
    result = evaluate_participants(predictions, truths)
    assert result.start_mae_ms == result.end_mae_ms == 100


@pytest.mark.parametrize('changes', [{'strict_iou': .5}, {'min_duration_ms': 0},
                                    {'candidate_fuse_ms': 1}, {'candidate_hgb': {'max_iter': 200}}])
def test_frozen_values_cannot_drift(changes):
    with pytest.raises(ValueError):
        A1Config(**changes)


def test_background_without_predictions_remains_in_population():
    result = evaluate_participants([], [], participant_ids=['6C7'])
    assert len(result.participants) == 1
    assert result.participants[0].f1 is None


def test_quality_requires_five_folds_and_explicit_pooled():
    from eating_event.a1.metrics import evaluate_quality
    result = evaluate_participants([], [], participant_ids=['6C7'])
    with pytest.raises(ValueError):
        evaluate_quality([result], outer_fold_f1=[.8]*5, pooled=result)


def test_negative_resource_limit_is_rejected():
    limits=dict(max_candidate_roles=105,max_verifier_roles=25,total_wall_seconds=21600,
                audit_wall_seconds=1800,fit_wall_seconds=7200,max_threads=-1,
                max_rss_bytes=8*1024**3,max_disk_bytes=2*1024**3)
    with pytest.raises(ValueError):
        A1Config(limits=limits)
