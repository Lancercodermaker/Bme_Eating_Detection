from eating_detection.decoding import decode_windows


def test_decode_merges_adjacent_positive_windows_and_removes_short_segments():
    windows = [(0, 10), (5, 15), (30, 40)]
    events = decode_windows(
        windows,
        [0.9, 0.8, 0.7],
        threshold=0.5,
        merge_gap_ms=0,
        min_duration_ms=12,
    )
    assert events == [(0, 15)]


def test_decoder_tuning_returns_validation_only_parameters():
    from eating_detection.decoding import tune_decoder

    parameters = tune_decoder(
        [[(0, 10), (10, 20)]],
        [[0.9, 0.1]],
        [[(0, 20)]],
        iou_threshold=0.25,
    )
    assert set(parameters) == {"threshold", "merge_gap_ms", "min_duration_ms"}
