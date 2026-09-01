from eating_detection.io import (
    canonical_participant_id,
    iter_sensor_chunks,
    read_meal_intervals,
)


def test_timestamp_zero_and_ppg_zero_are_masked(toy_sensor_file):
    chunks = list(iter_sensor_chunks(toy_sensor_file, chunksize=2))
    assert len(chunks) == 2
    first = chunks[0]
    assert first.acc_valid.tolist() == [False, True]
    assert first.gyro_valid.tolist() == [True, True]
    assert first.ppg_valid.tolist() == [False, False]
    assert canonical_participant_id(" HNU 21013 ") == "hnu21013"


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
