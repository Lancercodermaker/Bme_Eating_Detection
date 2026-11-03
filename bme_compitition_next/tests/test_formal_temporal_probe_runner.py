import numpy as np

from scripts.formal_g1_temporal_representation_probe import (
    _read_fast_imu,
    balanced_sample_weights,
    missing_event_window_mask,
)


def test_missing_event_window_mask_matches_participant_and_interval_overlap():
    participants = np.asarray(["p1", "p1", "p2", "p1"], dtype=object)
    starts = np.asarray([0, 100, 0, 500], dtype=np.int64)
    ends = np.asarray([50, 150, 100, 550], dtype=np.int64)
    missing_events = (("p1", 40, 60), ("p2", 200, 300))

    result = missing_event_window_mask(participants, starts, ends, missing_events)

    np.testing.assert_array_equal(result, np.asarray([True, False, False, False]))


def test_balanced_sample_weights_equalize_binary_class_totals():
    labels = np.asarray([0, 0, 0, 1], dtype=np.int8)

    weights = balanced_sample_weights(labels)

    assert weights.shape == labels.shape
    np.testing.assert_allclose(weights[labels == 0].sum(), weights[labels == 1].sum())
    assert np.isfinite(weights).all()


def test_fast_imu_reader_uses_audited_bad_rows_and_aggregates_duplicates(tmp_path):
    path = tmp_path / "sensor.txt"
    path.write_text(
        "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z\n"
        "1000\t1000\t1\t2\t3\t4\t5\t6\n"
        "1000\t1000\tbad\t2\t3\t4\t5\t6\n"
        "1000\t1000\t3\t4\t5\t6\t7\t8\n"
        "2000\t2000\t5\t6\t7\t8\t9\t10\n",
        encoding="utf-8",
    )

    raw = _read_fast_imu(path, bad_source_rows={3})

    np.testing.assert_array_equal(raw.acc.timestamps_ms, np.asarray([1000, 2000]))
    np.testing.assert_allclose(raw.acc.values[0], np.asarray([2.0, 3.0, 4.0]))
    np.testing.assert_allclose(raw.gyro.values[0], np.asarray([5.0, 6.0, 7.0]))
