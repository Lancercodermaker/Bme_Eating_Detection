import json

import pytest

from eating_event.artifacts import RunArtifact


def test_run_artifact_records_all_required_telemetry_events(tmp_path):
    run = RunArtifact(tmp_path, "m5")
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G1", "result": "pass", "failure_class": None})
    run.record_event(
        "escalation",
        {"reason": "resource threshold", "hypothesis_count": 3, "circuit_breaker_fired": True},
    )
    run.record_event("run_end", {"final_status": "failed"})
    run.finalize()
    events = [
        json.loads(line)
        for line in (run.root / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event_type"] for event in events] == [
        "run_start", "gate_result", "escalation", "run_end"
    ]
    assert all(event["schema_version"] == "telemetry_v1" for event in events)
    assert all(event["run_id"] == "m5" for event in events)


def test_escalation_requires_circuit_breaker_flag(tmp_path):
    run = RunArtifact(tmp_path, "m5-no-escalation")
    with pytest.raises(ValueError, match="circuit_breaker_fired"):
        run.record_event(
            "escalation",
            {"reason": "ordinary retry", "hypothesis_count": 1, "circuit_breaker_fired": False},
        )


def test_telemetry_rejects_forbidden_payload_fields(tmp_path):
    run = RunArtifact(tmp_path, "forbidden")
    with pytest.raises(ValueError, match="forbidden"):
        run.record_event("run_start", {"workflow_path": "RESEARCH", "test_truth": ["secret"]})
