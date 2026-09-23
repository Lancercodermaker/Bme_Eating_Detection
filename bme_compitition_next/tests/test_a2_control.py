from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from eating_event.a2.budget import (
    FitAttemptLedger,
    StudyInterrupted,
    StudyLedger,
    StudyResourceError,
    check_disk_budget,
    check_rss_ceiling,
    require_environment,
)
from eating_event.a2.control import supervise_worker


def make_ledger(tmp_path: Path) -> tuple[StudyLedger, Path, Path]:
    artifacts = tmp_path / "artifacts"
    output = artifacts / "a2-context-verifier-v1-001"
    output.mkdir(parents=True)
    return StudyLedger(artifacts, output), artifacts, output


def test_reserved_interrupted_fit_consumes_one_attempt_and_duplicate_role_is_rejected(tmp_path: Path) -> None:
    ledger, _, _ = make_ledger(tmp_path)
    fits = FitAttemptLedger(ledger)
    fits.reserve_fit("verifier/outer-0/inner-0")

    assert fits.attempt_count() == 1
    with pytest.raises(ValueError, match="already reserved"):
        fits.reserve_fit("verifier/outer-0/inner-0")


def test_total_active_wall_accumulates_every_audit_and_run_invocation(tmp_path: Path) -> None:
    ledger, _, _ = make_ledger(tmp_path)
    ledger.append("invocation_start", {"id": "audit-1", "mode": "audit", "monotonic": 10.0})
    ledger.append("invocation_end", {"id": "audit-1", "duration_seconds": 20.0})
    ledger.append("invocation_start", {"id": "audit-2", "mode": "audit", "monotonic": 31.0})
    ledger.append("invocation_end", {"id": "audit-2", "duration_seconds": 3.0})
    ledger.append("invocation_start", {"id": "run-1", "mode": "run", "monotonic": 35.0})

    assert ledger.active_wall_seconds(now=40.0) == pytest.approx(28.0)


def test_cumulative_fit_wall_includes_completed_and_active_fit(tmp_path: Path) -> None:
    ledger, _, _ = make_ledger(tmp_path)
    fits = FitAttemptLedger(ledger)
    fits.reserve_fit("verifier/a")
    fits.start_fit("verifier/a", now=10.0)
    fits.end_fit("verifier/a", "success", now=22.0)
    fits.reserve_fit("verifier/b")
    fits.start_fit("verifier/b", now=30.0)

    assert fits.fit_wall_seconds(now=35.0) == pytest.approx(17.0)


def test_sample_failure_and_disk_overage_raise_resource_status(tmp_path: Path) -> None:
    with pytest.raises(StudyResourceError, match="RSS"):
        check_rss_ceiling(None, max_rss_bytes=100)

    output = tmp_path / "output"
    output.mkdir()
    (output / "large.tmp").write_bytes(b"12345")
    with pytest.raises(StudyResourceError, match="disk"):
        check_disk_budget(output, (), max_disk_bytes=4)


def test_supervisor_terminates_worker_when_rss_sampling_fails(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    ledger, _, _ = make_ledger(tmp_path)
    monkeypatch.setattr("eating_event.a2.control.sample_process_tree_rss", lambda: None)

    with pytest.raises(StudyResourceError, match="RSS"):
        supervise_worker(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            output,
            ledger,
            response_path=output / "worker-response.json",
            max_rss_bytes=10**9,
            max_disk_bytes=10**7,
            wall_deadline_seconds=10,
        )


def test_output_disappearance_while_external_ledger_exists_is_fail_closed(tmp_path: Path) -> None:
    ledger, artifacts, output = make_ledger(tmp_path)
    ledger.append("study_status", {"status": "AUDIT_READY"})
    output.rename(artifacts / "renamed-output")

    with pytest.raises(ValueError, match="study output"):
        StudyLedger(artifacts, output)


def test_missing_or_corrupt_external_ledger_with_output_mirror_is_fail_closed(tmp_path: Path) -> None:
    ledger, artifacts, output = make_ledger(tmp_path)
    ledger.append("study_status", {"status": "AUDIT_READY"})
    (artifacts / "a2-study-budget.jsonl").unlink()
    with pytest.raises(ValueError, match="ledger mirror"):
        StudyLedger(artifacts, output)

    # Restore one syntactically valid external file whose contents disagree.
    (artifacts / "a2-study-budget.jsonl").write_text('{"event":"other"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="ledger mirror"):
        StudyLedger(artifacts, output)


@pytest.mark.parametrize("status", ["COMPLETE", "INVALID", "VERIFIER_DATA_INSUFFICIENT", "INCOMPLETE_RESOURCE", "INCOMPLETE_INTERRUPTED"])
def test_terminal_study_state_cannot_restart_run(tmp_path: Path, status: str) -> None:
    ledger, _, _ = make_ledger(tmp_path)
    ledger.mark_status(status)

    with pytest.raises(ValueError, match="terminal"):
        ledger.assert_can_start_run()


def test_a1_library_version_mismatch_is_rejected_before_fit() -> None:
    with pytest.raises(ValueError, match="environment version"):
        require_environment({"python": "3.10.11", "libraries": {"numpy": "0.0"}},
                            {"python": "3.10.11", "libraries": {"numpy": "2.2.6"}})


def test_supervisor_does_not_report_success_when_worker_disappears(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    ledger, _, _ = make_ledger(tmp_path)

    with pytest.raises(StudyInterrupted, match="worker"):
        supervise_worker(
            [sys.executable, "-c", "raise SystemExit(7)"],
            output,
            ledger,
            response_path=output / "worker-response.json",
            max_rss_bytes=10**9,
            max_disk_bytes=10**7,
            wall_deadline_seconds=10,
        )


def test_public_runner_has_no_candidate_estimator_fit_or_prediction_route() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "run_a2_context_verifier.py").read_text(encoding="utf-8")
    assert "fit_candidate_estimator" not in source
    assert "predict_proba" not in source
