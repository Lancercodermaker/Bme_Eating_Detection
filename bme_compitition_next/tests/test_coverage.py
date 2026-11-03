import pytest

import eating_event.coverage as coverage
from eating_event.data.manifest import ManifestAudit, RawFileRecord
from eating_event.data.raw import RawFileFormatError
from eating_event.coverage import (
    CandidateCoverageReport,
    CoverageRunConfig,
    FoldCoverageResult,
    QuantileResult,
    select_candidate_quantile,
)
from scripts.run_candidate_coverage import build_resource_failure_report


def test_formal_coverage_rejects_file_limits():
    with pytest.raises(ValueError, match="formal"):
        CoverageRunConfig(formal=True, max_files_per_participant=2)


def test_coverage_report_contains_fold_and_participant_results():
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=(
            FoldCoverageResult(
                fold_id="outer-0",
                pooled_recall=0.95,
                participant_recall={"p1": 1.0},
            ),
        ),
    )
    assert report.gate_id == "G1"
    assert report.fold_results[0].pooled_recall == pytest.approx(0.95)
    assert report.fold_results[0].participant_recall["p1"] == pytest.approx(1.0)


def test_candidate_quantile_selection_is_frozen_and_deterministic():
    results = (
        QuantileResult(quantile=0.70, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=30),
        QuantileResult(quantile=0.80, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=20),
        QuantileResult(quantile=0.90, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=20),
    )
    assert select_candidate_quantile(results).quantile == pytest.approx(0.90)


def test_interrupted_formal_coverage_is_a_resource_failure():
    report = build_resource_failure_report("interrupted after bounded resource observation")
    assert report.result == "fail"
    assert report.failure_class == "RESOURCE"


def _single_record_audit(tmp_path):
    path = tmp_path / "sensor.txt"
    record = RawFileRecord(
        participant_id="p1",
        path=path,
        session_folder="session-1",
        session_start_ms=1000,
        session_end_ms=5000,
    )
    audit = ManifestAudit()
    audit.record(
        "processed",
        participant_id="p1",
        reason="sensor file discovered",
        path_or_file_id=str(path),
        session_id="session-1",
        session_start_ms=1000,
        session_end_ms=5000,
    )
    return record, audit


def test_expected_raw_skip_replaces_processed_manifest_status_and_stays_eligible_only_when_processed(tmp_path):
    record, audit = _single_record_audit(tmp_path)
    error = RawFileFormatError("binary input")
    error.manifest_status = "skipped_malformed"
    error.manifest_reason = "undecodable"

    apply_failure = getattr(__import__("eating_event.coverage", fromlist=["apply_raw_failure_to_manifest"]), "apply_raw_failure_to_manifest", None)
    build_eligibility = getattr(__import__("eating_event.coverage", fromlist=["build_formal_eligibility"]), "build_formal_eligibility", None)
    assert callable(apply_failure)
    assert callable(build_eligibility)
    apply_failure(audit, record, error)

    eligibility = build_eligibility((record,), audit)
    assert eligibility.discovered_count == 1
    assert eligibility.processed_count == 0
    assert eligibility.skipped_count == 1
    assert eligibility.eligible_records == ()
    assert eligibility.skipped_reason_counts == {"undecodable": 1}
    assert audit.status_counts == {"skipped_malformed": 1}


def test_unexpected_raw_failure_is_fail_closed(tmp_path):
    record, audit = _single_record_audit(tmp_path)
    apply_failure = getattr(__import__("eating_event.coverage", fromlist=["apply_raw_failure_to_manifest"]), "apply_raw_failure_to_manifest", None)
    assert callable(apply_failure)

    with pytest.raises(RuntimeError, match="unexpected raw parser/runtime failure"):
        apply_failure(audit, record, RuntimeError("new parser bug"))


def test_participant_with_only_skipped_sessions_is_reported_not_removed(tmp_path):
    record, audit = _single_record_audit(tmp_path)
    skipped_path = tmp_path / "skipped.txt"
    skipped_record = RawFileRecord(
        participant_id="p2",
        path=skipped_path,
        session_folder="session-2",
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
    build_eligibility = getattr(__import__("eating_event.coverage", fromlist=["build_formal_eligibility"]), "build_formal_eligibility", None)
    assert callable(build_eligibility)

    eligibility = build_eligibility((record, skipped_record), audit)
    assert eligibility.participant_session_eligibility["p2"]["processed_session_count"] == 0
    assert eligibility.participant_session_eligibility["p2"]["eligible"] is False
    assert eligibility.ineligible_participants == ("p2",)


def test_coverage_report_persists_denominator_skip_and_cache_hashes(tmp_path):
    record, audit = _single_record_audit(tmp_path)
    build_eligibility = getattr(__import__("eating_event.coverage", fromlist=["build_formal_eligibility"]), "build_formal_eligibility", None)
    assert callable(build_eligibility)
    eligibility = build_eligibility((record,), audit)
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=(),
        eligibility=eligibility,
        cache_manifest_sha256="a" * 64,
    )
    payload = report.to_dict()

    assert payload["eligibility"]["discovered_count"] == 1
    assert payload["eligibility"]["denominator_sha256"] == eligibility.denominator_sha256
    assert payload["eligibility"]["manifest_sha256"] == eligibility.manifest_sha256
    assert payload["cache_manifest_sha256"] == "a" * 64


def test_coverage_report_persists_event_denominator_contract():
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=(),
        event_denominator_sha256="b" * 64,
        effective_valid_event_count=246,
        eligibility_artifact_sha256="c" * 64,
    )

    payload = report.to_dict()

    assert payload["event_denominator_sha256"] == "b" * 64
    assert payload["effective_valid_event_count"] == 246
    assert payload["eligibility_artifact_sha256"] == "c" * 64


def test_expected_skips_do_not_fail_gate_but_unexpected_failures_do():
    gate_passes = getattr(__import__("eating_event.coverage", fromlist=["formal_gate_passes"]), "formal_gate_passes", None)
    assert callable(gate_passes)
    folds = (FoldCoverageResult(fold_id="outer-0", pooled_recall=0.95, participant_recall={"p1": 1.0}),)
    assert gate_passes(folds, unexpected_failures=()) is True
    assert gate_passes(folds, unexpected_failures=("broken",)) is False


def test_event_truths_are_deduplicated_when_one_event_overlaps_multiple_sessions():
    first = coverage.EventInterval(1000, 2000)
    second = coverage.EventInterval(3000, 4000)

    assert coverage.deduplicate_event_intervals((first, first, second, first)) == (first, second)
