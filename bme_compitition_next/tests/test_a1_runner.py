import json

import pytest

from eating_event.a1.budget import ResourceNotReady
from scripts.run_a1_feasibility import audit_run, execute_run, parse_args


def test_runner_requires_explicit_mode():
    with pytest.raises(SystemExit):
        parse_args([])


def test_run_requires_matching_ready_audit(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="audit"):
        execute_run(config, tmp_path / "run", root=tmp_path)


def test_audit_reports_resource_unready_instead_of_silent_zero(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.run_a1_feasibility.measure_startup_resources", lambda: (_ for _ in ()).throw(ResourceNotReady("no sampler")))
    with pytest.raises(ResourceNotReady, match="no sampler"):
        audit_run(tmp_path / "config.json", tmp_path / "run", root=tmp_path)
