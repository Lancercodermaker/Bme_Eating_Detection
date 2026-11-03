from pathlib import Path
import json

from eating_event.audit import audit_tsv_file
from scripts.audit_dataset import _diagnostic_config_audit


def test_audit_counts_duplicates_zero_timestamps_gaps_and_malformed_rows(tmp_path: Path) -> None:
    path = tmp_path / "sample.tsv"
    path.write_text(
        "\n".join(
            [
                "ACC_TIME\tPPG_TIME\tGYRO_TIME\tACC_X",
                "1000\t0\t1000\t1",
                "1000\t0\t1000\t2",
                "2000\t1000\t2000\t3",
                "5000\t2000\t5000\t4",
                "malformed",
            ]
        ),
        encoding="utf-8",
    )

    result = audit_tsv_file(path)

    assert result.total_rows == 5
    assert result.malformed_rows == 1
    assert result.modalities["ACC_TIME"].positive_rows == 4
    assert result.modalities["ACC_TIME"].unique_timestamps == 3
    assert result.modalities["ACC_TIME"].duplicate_rows == 1
    assert result.modalities["ACC_TIME"].max_gap_ms == 3000
    assert result.modalities["PPG_TIME"].missing_rows == 2


def test_audit_supports_bounded_sampling(tmp_path: Path) -> None:
    path = tmp_path / "sample.tsv"
    path.write_text(
        "ACC_TIME\tPPG_TIME\tGYRO_TIME\n"
        "1000\t0\t1000\n"
        "2000\t1000\t2000\n"
        "3000\t2000\t3000\n",
        encoding="utf-8",
    )

    result = audit_tsv_file(path, max_rows=2)

    assert result.total_rows == 2
    assert result.truncated is True
    assert result.modalities["ACC_TIME"].unique_timestamps == 2


def test_full_manifest_audit_materializes_canonical_skip_and_eligibility_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    raw_root = tmp_path / "raw"
    metadata = tmp_path / "metadata"
    repo.mkdir()
    metadata.mkdir()

    binary_session = raw_root / "p-binary" / "s1"
    binary_session.mkdir(parents=True)
    (raw_root / "p-binary" / "index.csv").write_text(
        "sequence,folder_name,startTime,endTime\n1,s1,1000,5000\n", encoding="utf-8"
    )
    (binary_session / "sensor.txt").write_bytes(bytes([0x00, 0xFF, 0x00]))

    missing_gyro_session = raw_root / "p-gyro" / "s1"
    missing_gyro_session.mkdir(parents=True)
    (raw_root / "p-gyro" / "index.csv").write_text(
        "sequence,folder_name,startTime,endTime\n1,s1,1000,5000\n", encoding="utf-8"
    )
    (missing_gyro_session / "sensor.txt").write_text(
        "ACC_TIME\tGYRO_TIME\tACC_X\tACC_Y\tACC_Z\tGYRO_X\tGYRO_Y\tGYRO_Z\n"
        "1000\t0\t1\t2\t3\t4\t5\t6\n",
        encoding="utf-8",
    )

    config = tmp_path / "config.yaml"
    config.write_text(
        f"repository_root: {repo}\nraw_data_root: {raw_root}\nmetadata_root: {metadata}\n",
        encoding="utf-8",
    )
    output = tmp_path / "manifest-audit.json"

    assert _diagnostic_config_audit(
        config,
        output,
        limit_files=None,
        run_id="g1-processed-only-manifest-audit",
        diagnostic_only=True,
        resource_dry_run=False,
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["discovered_file_count"] == 2
    assert payload["processed_file_count"] == 0
    assert payload["skipped_file_count"] == 2
    assert payload["skipped_reason_counts"] == {
        "missing_valid_gyro_timestamp": 1,
        "undecodable": 1,
    }
    assert payload["manifest_sha256"]
    assert payload["denominator_sha256"]
    assert set(payload["ineligible_participants"]) == {"p-binary", "p-gyro"}

