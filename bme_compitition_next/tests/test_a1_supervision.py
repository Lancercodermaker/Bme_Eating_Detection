import sys
import time
import pytest
from eating_event.a1 import budget


def test_supervisor_terminates_timed_out_worker(tmp_path):
    started = time.monotonic()
    with pytest.raises(budget.ResourceNotReady, match='wall'):
        budget.run_supervised([sys.executable, '-c', 'import time; time.sleep(30)'], tmp_path,
                              budget.BudgetLimits(total_wall_seconds=.3), prior_seconds=0)
    assert time.monotonic() - started < 10


def test_supervisor_rejects_rss_overrun(tmp_path):
    with pytest.raises(budget.ResourceNotReady, match='RSS'):
        budget.run_supervised([sys.executable, '-c', 'import time; time.sleep(30)'], tmp_path,
                              budget.BudgetLimits(max_rss_bytes=1), prior_seconds=0)


def test_supervisor_charges_failed_worker_time(tmp_path):
    result = budget.run_supervised([sys.executable, '-c', 'raise SystemExit(2)'], tmp_path,
                                   budget.BudgetLimits(), prior_seconds=0)
    assert result['returncode'] == 2
    assert result['elapsed_seconds'] > 0
