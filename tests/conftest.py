import pytest


@pytest.fixture
def toy_sensor_file(tmp_path):
    path = tmp_path / "sensor.txt"
    ppg_columns = [f"PPG{i}" for i in range(1, 45)]
    header = [
        "ACC_TIME",
        "PPG_TIME",
        "GYRO_TIME",
        *ppg_columns,
        "ACC_X",
        "ACC_Y",
        "ACC_Z",
        "GYRO_X",
        "GYRO_Y",
        "GYRO_Z",
    ]
    rows = [
        [0, 0, 1000, *([0] * 44), 1, 2, 3, 4, 5, 6],
        [1000, 0, 1000, *([0] * 44), 2, 3, 4, 5, 6, 7],
        [1000, 1100, 1000, *([10] * 44), 3, 4, 5, 6, 7, 8],
    ]
    text = "\n".join("\t".join(map(str, row)) for row in [header, *rows]) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
