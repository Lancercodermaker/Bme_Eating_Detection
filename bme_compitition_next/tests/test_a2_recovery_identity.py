from __future__ import annotations

import pytest

from eating_event.a2 import audit


def _index(records, cache_entries):
    helper = getattr(audit, "index_approved_manifest_records", None)
    assert callable(helper), "cache/manifest join helper must be part of the real A2 audit path"
    return helper(records, cache_entries)


def _processed(identity="source-1", participant="p1", session="s1"):
    return {
        "path_or_file_id": identity,
        "participant_id": participant,
        "session_id": session,
        "status": "processed",
    }


def _cache(identity="source-1", participant="p1", session="s1"):
    return {"path": identity, "participant_id": participant, "session_id": session}


def test_manifest_join_allows_missing_identity_only_for_nonprocessed_exclusions() -> None:
    records = [
        _processed(),
        {"status": "skipped_invalid_session"},
        {"path_or_file_id": None, "status": "excluded_test_participant"},
    ]
    indexed = _index(records, [_cache()])

    assert list(indexed) == ["source-1"]
    assert indexed["source-1"] is records[0]


@pytest.mark.parametrize("record", [
    {"participant_id": "p1", "session_id": "s1", "status": "processed"},
    {"path_or_file_id": None, "participant_id": "p1", "session_id": "s1", "status": "processed"},
    {"path_or_file_id": "", "participant_id": "p1", "session_id": "s1", "status": "processed"},
])
def test_processed_manifest_record_requires_a_real_nonempty_identity(record) -> None:
    with pytest.raises(ValueError):
        _index([record], [_cache()])


def test_any_duplicate_nonempty_manifest_identity_is_rejected() -> None:
    records = [_processed(), {"path_or_file_id": "source-1", "status": "excluded_test_participant"}]
    with pytest.raises(ValueError, match="duplicate"):
        _index(records, [_cache()])


def test_every_cache_entry_must_have_one_processed_audit_match() -> None:
    with pytest.raises(ValueError, match="audit"):
        _index([_processed("source-1")], [_cache("missing")])
    with pytest.raises(ValueError, match="processed"):
        _index([{**_processed(), "status": "excluded_test_participant"}], [_cache()])
    with pytest.raises(ValueError, match="participant"):
        _index([_processed()], [_cache(participant="p2")])
    with pytest.raises(ValueError, match="session"):
        _index([_processed()], [_cache(session="s2")])


def test_duplicate_cache_references_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _index([_processed()], [_cache(), _cache()])


def test_eligibility_membership_uses_only_training_or_evaluation_eligible_gt() -> None:
    helper = getattr(audit, "validate_eligible_gt_participants", None)
    assert callable(helper), "eligible canonical GT membership helper must be part of the real A2 audit path"
    rows = [
        {"participant_id": "p-eval", "event_index": i, "evaluation_eligibility": True, "training_eligibility": False}
        for i in range(234)
    ]
    rows.extend(
        {"participant_id": f"excluded-{i}", "event_index": i, "evaluation_eligibility": False, "training_eligibility": False}
        for i in range(47)
    )

    assert helper(rows, {"p-eval", "6C7"}) == ("p-eval",)


@pytest.mark.parametrize("eligibility_field", ["training_eligibility", "evaluation_eligibility"])
def test_any_eligible_canonical_gt_participant_must_be_in_cache(eligibility_field) -> None:
    helper = getattr(audit, "validate_eligible_gt_participants", None)
    assert callable(helper), "eligible canonical GT membership helper must be part of the real A2 audit path"
    row = {
        "participant_id": "cache-external",
        "event_index": 0,
        "training_eligibility": eligibility_field == "training_eligibility",
        "evaluation_eligibility": eligibility_field == "evaluation_eligibility",
    }

    with pytest.raises(ValueError, match="eligible.*outside"):
        helper([row], {"p1", "6C7"})
