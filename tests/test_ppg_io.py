import numpy as np
import pytest

from eating_detection import io


def write_ppg(path, rows, columns=None):
    columns = columns or ["PPG_TIME", *[f"PPG{i}" for i in range(1, 45)]]
    path.write_text("\n".join("\t".join(map(str, row)) for row in [columns, *rows]) + "\n", encoding="utf-8")
    return path


def test_ppg_only_reads_all_44_channels_without_imu(tmp_path):
    path = write_ppg(tmp_path / "ppg.txt", [[1000, *range(1, 45)]])
    assert hasattr(io, "iter_ppg_chunks"), "independent PPG parser is required"
    chunk = next(io.iter_ppg_chunks(path, chunksize=1))
    assert chunk.values.shape == (1, 44)
    assert chunk.values.dtype == np.float32
    assert chunk.values[0].tolist() == list(range(1, 45))
    assert chunk.valid.tolist() == [True]


@pytest.mark.parametrize("time,values,valid", [
    (0, [1] * 44, False),
    (1000, [0] * 44, False),
    (1000, [float("nan")] + [1] * 43, False),
    (1000, [float("inf")] + [1] * 43, False),
    (1000, [0] + [1] * 43, True),
])
def test_ppg_quality_preserves_existing_row_semantics(tmp_path, time, values, valid):
    path = write_ppg(tmp_path / "ppg.txt", [[time, *values]])
    assert hasattr(io, "iter_ppg_chunks"), "independent PPG parser is required"
    chunk = next(io.iter_ppg_chunks(path))
    assert chunk.valid.tolist() == [valid]


def test_missing_ppg_channels_are_explicitly_invalid(tmp_path):
    path = write_ppg(tmp_path / "partial.txt", [[1000, 1]], ["PPG_TIME", "PPG1"])
    assert hasattr(io, "iter_ppg_chunks"), "independent PPG parser is required"
    chunk = next(io.iter_ppg_chunks(path))
    assert chunk.values.shape == (1, 44)
    assert np.isnan(chunk.values[0, 1:]).all()
    assert not chunk.valid.any()


def test_ppg_path_matches_legacy_parser_and_ignores_invalid_imu(toy_sensor_file, tmp_path):
    assert hasattr(io, "iter_ppg_chunks"), "independent PPG parser is required"
    old = list(io.iter_sensor_chunks(toy_sensor_file, chunksize=2))
    new = list(io.iter_ppg_chunks(toy_sensor_file, chunksize=2))
    for before, after in zip(old, new):
        np.testing.assert_array_equal(before.timestamp_ms[:, 1], after.timestamps_ms)
        np.testing.assert_array_equal(before.ppg, after.values)
        np.testing.assert_array_equal(before.ppg_valid, after.valid)
    path = write_ppg(tmp_path / "bad_imu.txt", [[1000, *range(1, 45), "not-a-number"]],
                     ["PPG_TIME", *[f"PPG{i}" for i in range(1, 45)], "ACC_X"])
    assert next(io.iter_ppg_chunks(path)).valid.all()


def test_ppg_parser_honors_row_limit_and_repeated_header(tmp_path):
    columns = ["PPG_TIME", *[f"PPG{i}" for i in range(1, 45)]]
    path = write_ppg(tmp_path / "ppg.txt", [[1000, *range(1, 45)], columns, [2000, *range(1, 45)]])
    assert hasattr(io, "iter_ppg_chunks"), "independent PPG parser is required"
    chunks = list(io.iter_ppg_chunks(path, chunksize=1, max_rows=2))
    assert len(chunks) == 2
    assert chunks[1].timestamps_ms.tolist() == [0]
    assert not chunks[1].valid.any()
