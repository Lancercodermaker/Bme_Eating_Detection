import json
from pathlib import Path

import pytest

import eating_event.coverage as coverage
from eating_event.metrics import EventInterval
from eating_event.coverage import (
    build_formal_eligibility,
    build_participant_eligibility_artifact,
)
from eating_event.data.manifest import ManifestAudit, RawFileRecord
from scripts.materialize_participant_eligibility import materialize_participant_eligibility


def _audit_with_eligible_and_ineligible_participants(tmp_path: Path):
    processed_path = tmp_path / "p1" / "session-1" / "sensor.txt"
    skipped_path = tmp_path / "p2" / "session-2" / "sensor.txt"
    records = (
        RawFileRecord("p1", processed_path, "session-1", 1000, 5000),
        RawFileRecord("p2", skipped_path, "session-2", 1000, 5000),
    )
    audit = ManifestAudit()
    audit.record(
        "processed",
        participant_id="p1",
        reason="sensor file discovered",
        path_or_file_id=str(processed_path),
        session_id="session-1",
        session_start_ms=1000,
        session_end_ms=5000,
    )
    audit.record(
        "skipped_missing_required_imu",
        participant_id="p2",
        reason="missing_valid_gyro_timestamp",
        path_or_file_id=str(skipped_path),
        session_id="session-2",
        session_start_ms=1000,
        session_end_ms=5000,
    )
    return records, audit


def test_participant_eligibility_artifact_freezes_event_denominator(tmp_path: Path):
    records, audit = _audit_with_eligible_and_ineligible_participants(tmp_path)
    eligibility = build_formal_eligibility(records, audit)
    payload = build_participant_eligibility_artifact(
        eligibility,
        {
            "p1": (EventInterval(1000, 2000), EventInterval(3000, 4000)),
            "p2": (EventInterval(1000, 2000),),
        },
        records=records,
        source_audit_sha256="a" * 64,
    )

    assert payload["schema_version"] == "participant_eligibility_v2"
    assert payload["target_train_participant_count"] == 2
    assert payload["eligible_participant_count"] == 1
    assert payload["ineligible_participants"] == ["p2"]
    assert payload["valid_event_count"] == 3
    assert payload["excluded_event_count"] == 1
    assert payload["effective_valid_event_count"] == 2
    assert payload["event_denominator_sha256"]
    assert payload["participant_eligibility"]["p2"]["participant_status"] == (
        "ineligible_no_processed_session"
    )
    assert payload["source_audit_sha256"] == "a" * 64


def test_participant_eligibility_classifies_unusable_event_reasons(tmp_path: Path):
    records, audit = _audit_with_eligible_and_ineligible_participants(tmp_path)
    eligibility = build_formal_eligibility(records, audit)
    payload = build_participant_eligibility_artifact(
        eligibility,
        {
            "p1": (EventInterval(7000, 8000),),
            "p2": (EventInterval(1000, 2000),),
            "p3": (EventInterval(1000, 2000),),
        },
        records=records,
    )

    assert payload["valid_event_count"] == 3
    assert payload["excluded_event_count"] == 3
    assert payload["effective_valid_event_count"] == 0
    assert payload["event_exclusion_reason_counts"] == {
        "metadata_only_no_session": 1,
        "no_index_session_overlap": 1,
        "overlap_only_invalid_sensor": 1,
    }
    assert payload["participant_eligibility"]["p3"]["participant_status"] == (
        "ineligible_no_raw_session"
    )


def test_materialize_participant_eligibility_reads_audit_without_raw_rescan(tmp_path: Path):
    audit_payload = {
        "manifest_records": [
            {
                "participant_id": "p1",
                "status": "processed",
                "reason": "sensor file discovered",
                "path_or_file_id": str(tmp_path / "p1.txt"),
                "session_id": "s1",
                "session_start_ms": 1000,
                "session_end_ms": 5000,
            },
            {
                "participant_id": "p2",
                "status": "skipped_missing_required_imu",
                "reason": "missing_valid_gyro_timestamp",
                "path_or_file_id": str(tmp_path / "p2.txt"),
                "session_id": "s2",
                "session_start_ms": 1000,
                "session_end_ms": 5000,
            },
        ],
        "status_counts": {
            "processed": 1,
            "skipped_missing_required_imu": 1,
        },
    }
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit_payload), encoding="utf-8")
    meal_path = tmp_path / "meal.csv"
    meal_path.write_text(
        "externalid,beforeTime,afterTime\n"
        "p1,1,2\n"
        "p2,1,2\n",
        encoding="utf-8",
    )
    output = tmp_path / "eligibility.json"

    materialize_participant_eligibility(audit_path, meal_path, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["eligible_participant_count"] == 1
    assert payload["excluded_event_count"] == 2
    assert payload["effective_valid_event_count"] == 0
    assert payload["manifest_sha256"]
    assert payload["denominator_sha256"]


def test_materialize_reconciles_user_meal_sensor_and_raw_participant_sets(tmp_path: Path):
    audit_payload = {
        "manifest_records": [
            {
                "participant_id": "p1",
                "status": "processed",
                "reason": "sensor file discovered",
                "path_or_file_id": str(tmp_path / "p1.txt"),
                "session_id": "s1",
                "session_start_ms": 1000,
                "session_end_ms": 5000,
            },
            {
                "participant_id": "p2",
                "status": "skipped_missing_required_imu",
                "reason": "missing_valid_gyro_timestamp",
                "path_or_file_id": str(tmp_path / "p2.txt"),
                "session_id": "s2",
                "session_start_ms": 1000,
                "session_end_ms": 5000,
            },
        ],
        "status_counts": {
            "processed": 1,
            "skipped_missing_required_imu": 1,
        },
    }
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit_payload), encoding="utf-8")
    meal_path = tmp_path / "meal.csv"
    meal_path.write_text(
        "externalid,beforeTime,afterTime\n"
        "p1,1,2\n"
        "p3,1,2\n",
        encoding="utf-8",
    )
    user_path = tmp_path / "users.csv"
    user_path.write_text(
        "externalid,age\n"
        "p1,20\n"
        "p3,21\n"
        "p4,22\n",
        encoding="utf-8",
    )
    sensor_path = tmp_path / "sensor.csv"
    sensor_path.write_text(
        "externalid,sensorData\n"
        "p1,s1.zip\n"
        "p2,s2.zip\n",
        encoding="utf-8",
    )
    output = tmp_path / "eligibility.json"

    materialize_participant_eligibility(
        audit_path,
        meal_path,
        output,
        user_info_path=user_path,
        sensor_index_path=sensor_path,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    reconciliation = payload["source_participant_reconciliation"]

    assert reconciliation["user_profile_count"] == 3
    assert reconciliation["meal_metadata_count"] == 2
    assert reconciliation["sensor_index_count"] == 2
    assert reconciliation["organized_raw_count"] == 2
    assert reconciliation["meal_metadata_only"] == ["p3"]
    assert reconciliation["organized_raw_only"] == ["p2"]
    assert reconciliation["user_profile_only"] == ["p4"]


def test_v2_eligibility_validation_rejects_denominator_drift(tmp_path: Path):
    records, audit = _audit_with_eligible_and_ineligible_participants(tmp_path)
    eligibility = build_formal_eligibility(records, audit)
    expected = build_participant_eligibility_artifact(
        eligibility,
        {"p1": (EventInterval(1000, 2000),), "p2": (EventInterval(1000, 2000),)},
        records=records,
        source_audit_sha256="b" * 64,
    )

    coverage.validate_participant_eligibility_artifact(expected, expected)

    actual = json.loads(json.dumps(expected))
    actual["event_denominator_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="event_denominator_sha256"):
        coverage.validate_participant_eligibility_artifact(actual, expected)
