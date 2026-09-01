from eating_detection.metrics import event_metrics, interval_iou


def test_iou_threshold_is_strict():
    assert interval_iou((0, 10), (7, 17)) == 3 / 17
    assert interval_iou((0, 3), (1, 4)) == 0.5
    assert event_metrics([(0, 3)], [(1, 4)], iou_threshold=0.25).tp == 1
    assert interval_iou((0, 3), (2, 4)) == 0.25
    assert event_metrics([(0, 3)], [(2, 4)], iou_threshold=0.25).fp == 1
    assert event_metrics([(0, 10)], [(10, 20)], iou_threshold=0.25).fp == 1


def test_empty_predictions_and_truth_are_safe():
    assert event_metrics([], [], 0.25).as_dict() == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "start_mae_ms": None,
        "end_mae_ms": None,
    }
    assert event_metrics([(0, 10)], [], 0.25).fp == 1
    assert event_metrics([], [(0, 10)], 0.25).fn == 1


def test_matching_is_one_to_one_and_reports_boundary_mae():
    metrics = event_metrics([(0, 12), (20, 30)], [(2, 10)], 0.25)
    assert metrics.tp == 1
    assert metrics.fp == 1
    assert metrics.fn == 0
    assert metrics.start_mae_ms == 2.0
    assert metrics.end_mae_ms == 2.0
