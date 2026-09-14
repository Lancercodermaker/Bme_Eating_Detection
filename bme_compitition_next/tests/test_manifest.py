from pathlib import Path

from eating_event.data.manifest import (
    discover_raw_files,
    discover_raw_files_with_audit,
    load_meal_events,
    events_for_record,
)


def test_manifest_maps_sessions_and_excludes_test_by_default(tmp_path: Path) -> None:
    participant = tmp_path / "P1"
    session = participant / "sessionA"
    session.mkdir(parents=True)
    (participant / "index.csv").write_text(
        "sequence,folder_name,startTime,endTime\n1,sessionA,1000,5000\n",
        encoding="utf-8",
    )
    (session / "collect_data.txt").write_text("header\n", encoding="utf-8")
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "index.csv").write_text(
        "sequence,folder_name,startTime,endTime\n1,sessionA,1000,5000\n",
        encoding="utf-8",
    )
    (test_dir / "sessionA").mkdir()
    (test_dir / "sessionA" / "collect_data.txt").write_text("header\n", encoding="utf-8")

    meal_path = tmp_path / "meal.csv"
    meal_path.write_text(
        "externalid,beforeTime,afterTime\nP1,2000,3000\ntest,0,0\n",
        encoding="utf-8",
    )

    records = discover_raw_files(tmp_path)
    meals = load_meal_events(meal_path)

    assert len(records) == 1
    assert records[0].participant_id == "P1"
    assert records[0].session_start_ms == 1000
    assert len(events_for_record(records[0], meals)) == 1
    assert "test" not in meals


def test_bad_index_row_is_reported(tmp_path: Path) -> None:
    participant = tmp_path / "P1"
    participant.mkdir()
    (participant / "index.csv").write_text(
        "sequence,folder_name,startTime,endTime\n1,sessionA,bad,5000\n",
        encoding="utf-8",
    )

    records, audit = discover_raw_files_with_audit(tmp_path)

    assert records == []
    assert audit.invalid_index_rows == 1
    assert audit.status_counts["skipped_invalid_session"] == 1

