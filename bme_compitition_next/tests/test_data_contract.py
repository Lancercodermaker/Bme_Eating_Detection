from pathlib import Path

import pytest

from eating_event.cache import build_cache_key
from eating_event.coverage import (
    build_event_ledger_artifact,
    validate_event_ledger_artifact,
    build_formal_eligibility,
)
from eating_event.data.contract import APPROVED_STEP_SECONDS, APPROVED_WINDOW_SECONDS
from eating_event.data.manifest import ManifestAudit, RawFileRecord, filter_meal_events_by_ledger
from eating_event.data.labels import WindowLabel, label_window
from eating_event.metrics import EventInterval


def _eligibility_fixture(tmp_path: Path):
    processed = tmp_path / "p1" / "s1" / "imu.txt"
    skipped = tmp_path / "p2" / "s2" / "imu.txt"
    records = (
        RawFileRecord("p1", processed, "s1", 1_000, 20_000),
        RawFileRecord("p2", skipped, "s2", 1_000, 20_000),
    )
    audit = ManifestAudit()
    audit.record(
        "processed",
        participant_id="p1",
        path_or_file_id=str(processed),
        session_id="s1",
        session_start_ms=1_000,
        session_end_ms=20_000,
        reason="sensor file discovered",
    )
    audit.record(
        "skipped_missing_required_imu",
        participant_id="p2",
        path_or_file_id=str(skipped),
        session_id="s2",
        session_start_ms=1_000,
        session_end_ms=20_000,
        reason="missing valid gyro timestamp",
    )
    return records, build_formal_eligibility(records, audit)


def test_event_ledger_preserves_orthogonal_statuses_and_denominators(tmp_path: Path):
    records, eligibility = _eligibility_fixture(tmp_path)
    meal_events = {
        "p1": (
            EventInterval(2_000, 12_000),  # accepted + representable
            EventInterval(13_000, 14_000),  # short + representable
            EventInterval(15_000, 16_000),  # sensor-backed but no dense support
        ),
        "p2": (EventInterval(2_000, 3_000),),  # overlap-only invalid sensor
        "p3": (EventInterval(2_000, 3_000),),  # metadata-only
    }

    artifact = build_event_ledger_artifact(
        eligibility,
        meal_events,
        dense_window_counts={
            ("p1", 0): 2,
            ("p1", 1): 1,
            ("p1", 2): 0,
            ("p2", 0): 0,
            ("p3", 0): 0,
        },
        records=records,
        source_audit_sha256="a" * 64,
    )

    assert artifact["schema_version"] == "participant_eligibility_v3"
    assert artifact["annotated_event_count"] == 5
    assert artifact["sensor_backed_event_count"] == 3
    assert artifact["representable_event_count"] == 2
    assert artifact["label_eligible_event_count"] == 1
    assert artifact["unrepresentable_event_count"] == 3
    assert artifact["unrepresentable_reason_counts"] == {
        "METADATA_ONLY_NO_SESSION": 1,
        "NO_DENSE_WINDOW_SUPPORT": 1,
        "OVERLAP_ONLY_INVALID_SENSOR": 1,
    }

    rows = {(row["participant_id"], row["event_index"]): row for row in artifact["event_eligibility"]}
    assert rows[("p1", 0)]["annotation_status"] == "annotated"
    assert rows[("p1", 0)]["sensor_status"] == "sensor_backed"
    assert rows[("p1", 0)]["representability_status"] == "representable"
    assert rows[("p1", 0)]["training_eligibility"] is True
    assert rows[("p1", 0)]["exclusion_reason"] is None

    assert rows[("p1", 1)]["annotation_quality_status"] == "SHORT_DURATION_SUSPECT"
    assert rows[("p1", 1)]["training_eligibility"] is False
    assert rows[("p1", 1)]["exclusion_reason"] == "SHORT_DURATION_SUSPECT"

    assert rows[("p1", 2)]["representability_status"] == "unrepresentable"
    assert rows[("p1", 2)]["unrepresentable_reason"] == "NO_DENSE_WINDOW_SUPPORT"
    assert rows[("p1", 2)]["training_eligibility"] is False
    assert rows[("p1", 2)]["exclusion_reason"] == "NO_DENSE_WINDOW_SUPPORT"

    assert rows[("p2", 0)]["unrepresentable_reason"] == "OVERLAP_ONLY_INVALID_SENSOR"
    assert rows[("p3", 0)]["unrepresentable_reason"] == "METADATA_ONLY_NO_SESSION"
    assert artifact["annotated_event_count"] == len(artifact["event_eligibility"])


def test_short_suspect_events_are_not_training_truths(tmp_path: Path):
    records, eligibility = _eligibility_fixture(tmp_path)
    meal_events = {"p1": (EventInterval(2_000, 12_000), EventInterval(13_000, 14_000))}
    artifact = build_event_ledger_artifact(
        eligibility,
        meal_events,
        dense_window_counts={("p1", 0): 1, ("p1", 1): 1},
        records=records,
    )

    filtered = filter_meal_events_by_ledger(meal_events, artifact, eligibility_field="training_eligibility")
    assert filtered == {"p1": (EventInterval(2_000, 12_000),)}


def test_event_ledger_validation_rejects_count_or_reason_drift(tmp_path: Path):
    records, eligibility = _eligibility_fixture(tmp_path)
    events = {"p1": (EventInterval(2_000, 12_000),)}
    expected = build_event_ledger_artifact(
        eligibility,
        events,
        dense_window_counts={("p1", 0): 1},
        records=records,
    )
    validate_event_ledger_artifact(expected, expected)

    actual = {**expected, "representable_event_count": 0}
    with pytest.raises(ValueError, match="representable_event_count"):
        validate_event_ledger_artifact(actual, expected)


def test_cache_key_changes_with_contract_identity():
    base = build_cache_key(
        "abc",
        15.0,
        7.5,
        "imu_stats_v1",
        "window_event_labels_v1",
        eligibility_contract_version="event_eligibility_v1",
        eligibility_contract_hash="a" * 64,
        label_contract_version="window_event_overlap_v1",
        label_contract_hash="b" * 64,
    )
    changed_eligibility = build_cache_key(
        "abc",
        15.0,
        7.5,
        "imu_stats_v1",
        "window_event_labels_v1",
        eligibility_contract_version="event_eligibility_v1",
        eligibility_contract_hash="c" * 64,
        label_contract_version="window_event_overlap_v1",
        label_contract_hash="b" * 64,
    )
    changed_label = build_cache_key(
        "abc",
        15.0,
        7.5,
        "imu_stats_v1",
        "window_event_labels_v1",
        eligibility_contract_version="event_eligibility_v1",
        eligibility_contract_hash="a" * 64,
        label_contract_version="window_event_overlap_v1",
        label_contract_hash="d" * 64,
    )
    assert len({base, changed_eligibility, changed_label}) == 3


def test_approved_window_label_contract_is_15s_7_5s_and_50_percent():
    positive = label_window(
        EventInterval(0, 15_000),
        (EventInterval(0, 7_500),),
        positive_overlap=0.5,
    )
    below_threshold = label_window(
        EventInterval(0, 15_000),
        (EventInterval(0, 7_499),),
        positive_overlap=0.5,
    )
    assert positive.label is WindowLabel.POSITIVE
    assert below_threshold.label is WindowLabel.IGNORE
    assert APPROVED_WINDOW_SECONDS == 15.0
    assert APPROVED_STEP_SECONDS == 7.5
