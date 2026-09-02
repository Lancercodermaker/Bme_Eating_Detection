from eating_detection.io import (
    canonical_participant_id,
    iter_sensor_chunks,
    read_meal_intervals,
)

import numpy as np


def test_timestamp_zero_and_ppg_zero_are_masked(toy_sensor_file):
    chunks = list(iter_sensor_chunks(toy_sensor_file, chunksize=2))
    assert len(chunks) == 2
    first = chunks[0]
    assert first.acc_valid.tolist() == [False, True]
    assert first.gyro_valid.tolist() == [True, True]
    assert first.ppg_valid.tolist() == [False, False]
    assert canonical_participant_id(" HNU 21013 ") == "hnu21013"


def test_imu_only_path_does_not_require_or_materialize_ppg(tmp_path, toy_sensor_file):
    imu_only = tmp_path / "imu_only.txt"
    imu_only.write_text(
        "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z\n"
        "1000\t1000\t1\t2\t3\t4\t5\t6\n"
        "2000\t2000\t2\t3\t4\t5\t6\t7\n",
        encoding="utf-8",
    )

    imu_chunks = list(iter_sensor_chunks(imu_only, chunksize=1, include_ppg=False))
    old_chunks = list(iter_sensor_chunks(toy_sensor_file, chunksize=2, include_ppg=True))
    fast_chunks = list(iter_sensor_chunks(toy_sensor_file, chunksize=2, include_ppg=False))

    assert len(imu_chunks) == 2
    assert all(chunk.ppg.shape[1] == 0 for chunk in imu_chunks)
    assert all(not chunk.ppg_valid.any() for chunk in imu_chunks)
    assert np.array_equal(old_chunks[0].timestamp_ms[:, [0, 2]], fast_chunks[0].timestamp_ms[:, [0, 2]])
    assert np.array_equal(old_chunks[0].acc, fast_chunks[0].acc)
    assert np.array_equal(old_chunks[0].gyro, fast_chunks[0].gyro)
    assert np.array_equal(old_chunks[0].acc_valid, fast_chunks[0].acc_valid)
    assert np.array_equal(old_chunks[0].gyro_valid, fast_chunks[0].gyro_valid)


def test_repeated_header_inside_sensor_file_is_masked_not_a_parse_failure(tmp_path):
    header = "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z"
    path = tmp_path / "repeated_header.txt"
    path.write_text(
        header
        + "\n1000\t1000\t1\t2\t3\t4\t5\t6\n"
        + header
        + "\n2000\t2000\t2\t3\t4\t5\t6\t7\n",
        encoding="utf-8",
    )

    chunks = list(iter_sensor_chunks(path, chunksize=10, include_ppg=False))

    assert len(chunks) == 1
    assert chunks[0].timestamp_ms[:, 0].tolist() == [1000, 0, 2000]
    assert chunks[0].acc_valid.tolist() == [True, False, True]
    assert chunks[0].gyro_valid.tolist() == [True, False, True]


def test_meal_intervals_are_canonicalized_and_zero_duration_is_excluded(tmp_path):
    path = tmp_path / "sample_mealinfo.csv"
    path.write_text(
        "externalid,beforeTime,afterTime\n"
        " HNU 1 ,2000,1000\n"
        "HNU2,3000,3000\n",
        encoding="utf-8",
    )
    intervals, report = read_meal_intervals(tmp_path)
    assert intervals == {"hnu1": [(1000, 2000)]}
    assert report["reversed_swapped"] == 1
    assert report["zero_duration_excluded"] == 1
