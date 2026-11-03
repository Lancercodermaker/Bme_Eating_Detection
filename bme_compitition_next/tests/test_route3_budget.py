from __future__ import annotations

from pathlib import Path

import pytest

from eating_event.route3.budget import Route3Budget, Route3ResourceError


LIMITS = {
    "active_wall_seconds": 30,
    "fit_wall_seconds": 10,
    "verifier_fit_attempts": 1,
    "disk_bytes": 1024 * 1024,
    "rss_absolute_bytes": 1024 * 1024,
    "rss_startup_fraction": 0.5,
}


def _budget(tmp_path: Path, mode: str, *, rss_value: int = 100):
    artifacts = tmp_path / "artifacts"
    return Route3Budget(
        output_dir=artifacts / "route3-out",
        ledger_path=artifacts / "route3-budget.jsonl",
        lock_path=artifacts / "route3-budget.lock",
        config_sha256="a" * 64,
        limits=LIMITS,
        startup_available_bytes=1024 * 1024,
        mode=mode,
        rss_reader=lambda: rss_value,
        clock=lambda: 10.0,
    )


def test_route3_budget_requires_audit_ready_before_run(tmp_path):
    with pytest.raises(ValueError, match="audit-ready"):
        _budget(tmp_path, "run")


def test_failed_fit_is_reserved_and_consumes_the_attempt(tmp_path):
    audit = _budget(tmp_path, "audit")
    audit.close("AUDIT_READY")

    run = _budget(tmp_path, "run")
    run.reserve_fit("verifier/outer-0/inner-0")
    run.start_fit("verifier/outer-0/inner-0")
    run.end_fit("verifier/outer-0/inner-0", "failed")
    with pytest.raises(Route3ResourceError, match="fit attempt cap"):
        run.reserve_fit("verifier/outer-0/inner-1")
    run.close("INCOMPLETE_RESOURCE")


def test_route3_budget_fails_closed_on_rss_overrun(tmp_path):
    budget = _budget(tmp_path, "audit", rss_value=600_000)

    with pytest.raises(Route3ResourceError, match="RSS"):
        budget.check()
    budget.close("INCOMPLETE_RESOURCE")
