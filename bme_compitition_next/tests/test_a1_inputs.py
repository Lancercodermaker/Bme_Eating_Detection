import hashlib
import json

import numpy as np
import pytest

from eating_event.a1.contracts import A1Config
from eating_event.a1.inputs import load_inputs


def write_fixture(tmp_path, *, tamper=False, missing_session=False):
    root = tmp_path
    cache_root = root / "artifacts" / "g1-formal-cache-v3-final"
    cache_root.mkdir(parents=True)
    cache_path = cache_root / "record-a.npz"
    np.savez_compressed(
        cache_path,
        features=np.ones((2, 111), dtype=np.float32),
        labels=np.array([0, 1], dtype=np.int8),
        starts=np.array([0, 7500], dtype=np.int64),
        ends=np.array([15000, 22500], dtype=np.int64),
        coverage=np.ones(2, dtype=np.float32),
        invalid_runs=np.zeros(2, dtype=np.int32),
        crosses_gap=np.zeros(2, dtype=bool),
        participant_ids=np.array(["p1", "p1"]),
        session_ids=np.array(["s1", "s1"]),
        feature_names=np.asarray(json.dumps([f"f{i}" for i in range(111)]), dtype=object),
        metadata=np.asarray(json.dumps({"feature_schema_version": "imu_stats_v1"}), dtype=object),
    )
    cache_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    if tamper:
        cache_hash = "0" * 64
    (root / "artifacts" / "cache-manifest.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "participant_id": "p1",
                        "session_id": "s1",
                        "path": "opaque/raw/path.txt",
                        "cache_path": str(cache_path),
                        "cache_sha256": cache_hash,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "artifacts" / "manifest-audit.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "participant_id": "p1",
                        "status": "processed",
                        "path_or_file_id": "opaque/raw/path.txt",
                        "session_id": "s1",
                        "session_start_ms": 0,
                        "session_end_ms": 100000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    event = {
        "participant_id": "p1",
        "event_index": 0,
        "training_eligibility": True,
        "evaluation_eligibility": True,
        "start_ms": 0,
        "end_ms": 10000,
    }
    if missing_session:
        event.pop("participant_id")
    (root / "artifacts" / "eligibility.json").write_text(
        json.dumps(
            {
                "schema_version": "participant_eligibility_v3",
                "label_eligible_event_denominator_sha256": "6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d",
                "event_eligibility": [event],
            }
        ),
        encoding="utf-8",
    )
    config = A1Config(
        limits={
            "max_candidate_roles": 105,
            "max_verifier_roles": 25,
            "total_wall_seconds": 21600,
            "audit_wall_seconds": 1800,
            "fit_wall_seconds": 7200,
            "max_rss_bytes": 8 * 1024**3,
            "max_disk_bytes": 2 * 1024**3,
            "max_threads": 4,
        },
        paths={
            "cache_manifest": "artifacts/cache-manifest.json",
            "manifest_audit": "artifacts/manifest-audit.json",
            "eligibility": "artifacts/eligibility.json",
            "cache_root": "artifacts/g1-formal-cache-v3-final",
        },
    )
    return root, config


def test_cache_hash_tampering_fails(tmp_path):
    root, config = write_fixture(tmp_path, tamper=True)
    with pytest.raises(ValueError, match="cache hash"):
        load_inputs(root, config)


def test_missing_participant_identity_fails(tmp_path):
    root, config = write_fixture(tmp_path, missing_session=True)
    with pytest.raises(ValueError, match="participant_id"):
        load_inputs(root, config)


def test_raw_path_is_opaque_and_not_opened(tmp_path, monkeypatch):
    root, config = write_fixture(tmp_path)
    original_open = open

    def guarded_open(path, *args, **kwargs):
        if "opaque/raw/path.txt" in str(path):
            raise AssertionError("raw path was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded_open)
    bundle = load_inputs(root, config)
    assert len(bundle.windows) == 2


def test_same_canonical_event_is_not_duplicated_across_records(tmp_path):
    root, config = write_fixture(tmp_path)
    bundle = load_inputs(root, config)
    assert len(bundle.truths["p1"]) == 1


def test_missing_gt_participant_is_retained_as_background(tmp_path):
    root, config = write_fixture(tmp_path)
    (root / "artifacts" / "eligibility.json").write_text(
        json.dumps(
            {
                "schema_version": "participant_eligibility_v3",
                "label_eligible_event_denominator_sha256": "6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d",
                "event_eligibility": [
                    {
                        "participant_id": "6C7",
                        "event_index": 0,
                        "training_eligibility": False,
                        "evaluation_eligibility": False,
                        "start_ms": 0,
                        "end_ms": 10000,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bundle = load_inputs(root, config)
    assert "6C7" not in bundle.truths
