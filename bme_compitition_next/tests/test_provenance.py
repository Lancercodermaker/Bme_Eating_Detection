import pytest

from eating_event.provenance import (
    FORMAL_CACHE_DIR_NAME,
    build_cache_runtime_provenance,
    resolve_formal_cache_dir,
)


def test_formal_cache_dir_requires_the_approved_final_root(tmp_path):
    final_root = tmp_path / FORMAL_CACHE_DIR_NAME
    assert resolve_formal_cache_dir(final_root) == final_root.resolve()

    with pytest.raises(ValueError, match=FORMAL_CACHE_DIR_NAME):
        resolve_formal_cache_dir(tmp_path / "g1-formal-cache-v3")


def test_runtime_provenance_records_path_identity_and_manifest_hash(tmp_path):
    cache_root = tmp_path / FORMAL_CACHE_DIR_NAME
    entries = [
        {
            "participant_id": "p1",
            "session_id": "s1",
            "path": "raw.txt",
            "cache_path": str(cache_root / "a.npz"),
            "cache_sha256": "a" * 64,
        }
    ]
    metadata = {
        "eligibility_contract_version": "event_eligibility_v1",
        "eligibility_contract_hash": "eligibility-hash",
        "eligibility_artifact_sha256": "artifact-hash",
        "label_contract_version": "window_event_overlap_v1",
        "label_contract_hash": "label-hash",
        "window_seconds": 15.0,
        "step_seconds": 7.5,
    }

    provenance = build_cache_runtime_provenance(cache_root, entries, metadata)

    assert provenance["resolved_cache_path"] == str(cache_root.resolve())
    assert provenance["cache_entry_count"] == 1
    assert provenance["cache_manifest_sha256"]
    assert provenance["eligibility_contract_hash"] == "eligibility-hash"
    assert provenance["label_contract_hash"] == "label-hash"
    assert provenance["window_seconds"] == 15.0
    assert provenance["step_seconds"] == 7.5
