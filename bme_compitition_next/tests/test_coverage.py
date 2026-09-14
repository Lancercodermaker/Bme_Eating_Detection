import pytest

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
