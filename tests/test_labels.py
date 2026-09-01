from eating_detection.labels import clean_interval, label_window


def test_reversed_interval_is_swapped_and_reported():
    interval, reason = clean_interval(20, 10, coverage=(0, 30))
    assert interval == (10, 20)
    assert reason == "reversed_swapped"


def test_equal_interval_is_excluded_from_positive_training():
    interval, reason = clean_interval(10, 10, coverage=(0, 30))
    assert interval is None
    assert reason == "zero_duration_excluded"


def test_window_label_uses_overlap_and_soft_boundary():
    assert label_window((0, 10), [(5, 15)], positive_overlap=0.25, mode="soft") == 0.5
    assert label_window((0, 10), [(0, 1)], positive_overlap=0.25, mode="soft") == 0.1
    assert label_window((0, 10), [(20, 30)], positive_overlap=0.25, mode="soft") == 0.0
    assert label_window((0, 10), [(1, 2)], positive_overlap=0.25, mode="ignore") is None
