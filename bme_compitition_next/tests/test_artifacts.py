import json

import pytest

from eating_event.artifacts import RunArtifact


def test_formal_run_artifact_requires_core_lifecycle_events(tmp_path):
    run = RunArtifact(tmp_path, "g1")
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G1", "result": "pass", "failure_class": None})
    with pytest.raises(ValueError, match="run_end"):
        run.finalize()


def test_artifact_finalize_writes_manifest_and_telemetry_checksum(tmp_path):
    run = RunArtifact(tmp_path, "m0")
    run.write_json("feature_schema.json", {"version": "imu_stats_v1", "width": 111})
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G0", "result": "pass", "failure_class": None})
    run.record_event("run_end", {"final_status": "pass"})

    manifest = run.finalize()

    assert manifest["schema_version"] == "artifact_v1"
    assert "feature_schema.json" in manifest["files"]
    assert "telemetry.jsonl" in manifest["files"]
    assert manifest["checksums"]["telemetry.jsonl"]
    assert json.loads((run.root / "manifest.json").read_text(encoding="utf-8"))["run_id"] == "m0"
