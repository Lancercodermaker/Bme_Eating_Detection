import pytest

from eating_event.metrics import EventInterval, evaluate_events, interval_iou


def test_iou_boundary_is_strictly_greater_than_point_25() -> None:
    truth = EventInterval(0, 100)

    assert interval_iou(EventInterval(0, 25), truth) == pytest.approx(0.25)
    assert interval_iou(EventInterval(0, 25), truth) <= 0.25
    assert interval_iou(EventInterval(0, 26), truth) > 0.25


def test_exact_point_25_is_not_a_true_positive() -> None:
    result = evaluate_events([EventInterval(0, 25)], [EventInterval(0, 100)])

    assert result.tp == 0
    assert result.fp == 1
    assert result.fn == 1
    assert result.f1 == 0.0


def test_matching_is_one_to_one() -> None:
    result = evaluate_events(
        [EventInterval(0, 100)],
        [EventInterval(0, 100), EventInterval(0, 100)],
    )

    assert (result.tp, result.fp, result.fn) == (1, 0, 1)


def test_empty_sets_have_defined_counts_and_scores() -> None:
    no_predictions = evaluate_events([], [EventInterval(0, 100)])
    no_truth = evaluate_events([EventInterval(0, 100)], [])
    neither = evaluate_events([], [])

    assert (no_predictions.tp, no_predictions.fp, no_predictions.fn) == (0, 0, 1)
    assert (no_truth.tp, no_truth.fp, no_truth.fn) == (0, 1, 0)
    assert (neither.tp, neither.fp, neither.fn) == (0, 0, 0)
    assert neither.precision == 0.0
    assert neither.recall == 0.0
    assert neither.f1 == 0.0


def test_boundary_mae_is_reported_for_matched_events_only() -> None:
    result = evaluate_events(
        [EventInterval(10, 110), EventInterval(1000, 1100)],
        [EventInterval(0, 100)],
    )

    assert result.tp == 1
    assert result.start_mae_ms == pytest.approx(10.0)
    assert result.end_mae_ms == pytest.approx(10.0)

