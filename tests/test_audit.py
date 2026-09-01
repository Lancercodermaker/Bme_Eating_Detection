from eating_detection.audit import audit_sensor_files
from eating_detection.cli import main


def test_audit_is_bounded_and_reports_quality(toy_sensor_file):
    report = audit_sensor_files([toy_sensor_file], max_rows=2, chunksize=1)
    assert report["files_read"] == 1
    assert report["rows_read"] == 2
    assert report["timestamp_zero_rows"] >= 1
    assert report["ppg_invalid_rows"] == 2


def test_audit_cli_writes_bounded_json(toy_sensor_file, tmp_path):
    output_dir = tmp_path / "audit"
    result = main(
        [
            "audit",
            "--index-dir",
            str(tmp_path),
            "--train-dir",
            str(toy_sensor_file.parent),
            "--output-dir",
            str(output_dir),
            "--limit-files",
            "1",
            "--max-rows",
            "1",
        ]
    )
    assert result == 0
    assert (output_dir / "audit_sample.json").exists()
