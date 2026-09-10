from pathlib import Path

from eating_event.audit import audit_tsv_file


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

