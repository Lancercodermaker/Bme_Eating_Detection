from pathlib import Path

import numpy as np
import pytest

from eating_event.data.raw import RawFileFormatError, RawIMU, read_imu_tsv, regularize_imu
from eating_event.data.timebase import AggregatedSeries


def test_read_imu_tsv_aggregates_duplicate_packets_across_chunks(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    path = tmp_path / "sensor.txt"
    path.write_text(
        "\n".join(
            [
                "ACC_TIME\tPPG_TIME\tGYRO_TIME\tPPG1\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z",
                "1000\t0\t1000\t0\t1\t2\t3\t4\t5\t6",
                "1000\t0\t1000\t0\t3\t4\t5\t6\t7\t8",
                "2000\t1000\t2000\t1\t5\t6\t7\t8\t9\t10",
            ]
        ),
        encoding="utf-8",
    )

    result = read_imu_tsv(path, chunk_size=2)

    np.testing.assert_array_equal(result.acc.timestamps_ms, [1000, 2000])
    np.testing.assert_allclose(result.acc.values[0], [2, 3, 4])
    np.testing.assert_allclose(result.gyro.values[0], [5, 6, 7])
    assert result.acc.duplicate_count == 1
    assert result.gyro.duplicate_count == 1


def test_regularize_imu_keeps_common_grid_and_requires_aligned_modalities(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    path = tmp_path / "sensor.txt"
    path.write_text(
        "\n".join(
            [
                "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z",
                "1000\t1000\t1\t2\t3\t4\t5\t6",
                "2000\t2000\t2\t3\t4\t5\t6\t7",
                "3000\t3000\t3\t4\t5\t6\t7\t8",
            ]
        ),
        encoding="utf-8",
    )

    regularized = regularize_imu(read_imu_tsv(path, chunk_size=2), grid_hz=1, max_gap_seconds=2)

    assert regularized.values.shape == (3, 6)
    assert regularized.valid_mask.tolist() == [True, True, True]
    np.testing.assert_array_equal(regularized.timestamps_ms, [1000, 2000, 3000])


def test_regularize_imu_aligns_streams_with_small_start_offset() -> None:
    acc = AggregatedSeries(
        timestamps_ms=np.array([1000, 1100, 1200], dtype=np.int64),
        values=np.ones((3, 3), dtype=np.float64),
        duplicate_count=0,
        dropped_missing_timestamps=0,
    )
    gyro = AggregatedSeries(
        timestamps_ms=np.array([1050, 1150, 1250], dtype=np.int64),
        values=np.ones((3, 3), dtype=np.float64),
        duplicate_count=0,
        dropped_missing_timestamps=0,
    )

    result = regularize_imu(RawIMU(acc=acc, gyro=gyro), grid_hz=10, max_gap_seconds=2)

    assert result.values.shape[1] == 6
    assert result.timestamps_ms[0] == 1000
    assert result.valid_mask.any()


def test_binary_sensor_file_is_reported_as_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "binary.txt"
    path.write_bytes(bytes([0xD2, 0x3B, 0x00, 0xDB, 0xCA, 0x3B, 0x00]))

    with pytest.raises(RawFileFormatError):
        read_imu_tsv(path)


def test_non_numeric_sensor_row_is_reported_as_unreadable(tmp_path: Path) -> None:
    path = tmp_path / "bad-row.txt"
    path.write_text(
        "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z\n"
        "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z\n",
        encoding="utf-8",
    )

    with pytest.raises(RawFileFormatError):
        read_imu_tsv(path)
