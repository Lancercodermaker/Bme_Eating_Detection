import json

import pytest

from eating_event.a1.budget import BudgetLedger, BudgetLimits, BudgetState, ResourceNotReady


def test_fit_attempt_is_reserved_before_execution_and_not_retried(tmp_path):
    ledger = BudgetLedger(tmp_path / "fit-ledger.jsonl", BudgetLimits(max_candidate_fits=2, max_verifier_fits=1))
    ledger.reserve_fit("candidate", "role-1")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve_fit("candidate", "role-1")
    ledger.record_fit_result("role-1", "failed")
    state = ledger.state()
    assert state.candidate_fit_attempts == 1
    assert state.failed_fit_attempts == 1


def test_resume_preserves_consumed_attempts(tmp_path):
    path = tmp_path / "fit-ledger.jsonl"
    first = BudgetLedger(path, BudgetLimits(max_candidate_fits=1, max_verifier_fits=1))
    first.reserve_fit("candidate", "r")
    second = BudgetLedger(path, BudgetLimits(max_candidate_fits=1, max_verifier_fits=1))
    with pytest.raises(RuntimeError, match="candidate fit budget"):
        second.reserve_fit("candidate", "r2")


def test_budget_limits_reject_invalid_resource_sampler():
    with pytest.raises(ResourceNotReady):
        BudgetState.from_samples([{"rss_bytes": None}], max_rss_bytes=100)


def test_disk_ceiling_is_classified_as_resource_failure(tmp_path):
    (tmp_path/'data').write_bytes(b'xx')
    ledger=BudgetLedger(tmp_path/'ledger',BudgetLimits(max_disk_bytes=1))
    with pytest.raises(ResourceNotReady,match='disk'):
        ledger.check_output_size(tmp_path)
