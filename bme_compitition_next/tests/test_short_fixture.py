import json
from pathlib import Path

import pytest

from eating_event.data.manifest import RawFileRecord
from eating_event.short_fixture import (
    build_fixture_oof_folds,
    load_fixture_manifest,
    select_fixture_records,
)


def _record(participant: str, session: str, index: int) -> RawFileRecord:
    return RawFileRecord(
        participant_id=participant,
        path=Path(f"{participant}-{session}-{index}.txt"),
        session_folder=session,
        session_start_ms=index * 10_000,
        session_end_ms=index * 10_000 + 9_000,
    )


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "short_e2e_fixture_v1",
        "fixture_id": "test-fixture",
        "selection_seed": 20260910,
        "candidate_threshold": 0.35,
        "oof_folds": 5,
        "training_participants": ["p1", "p2", "p3", "p4", "p5"],
        "validation_participants": ["p6"],
        "selected_sessions": {
            participant: [f"{participant}-session"]
            for participant in ["p1", "p2", "p3", "p4", "p5", "p6"]
        },
        "selection_rationale": "fixed test manifest",
    }


def test_fixture_manifest_selects_exact_disjoint_records_deterministically(tmp_path: Path) -> None:
    manifest_path = tmp_path / "fixture.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    records = [
        _record(participant, f"{participant}-session", index)
        for index, participant in enumerate(["p6", "p3", "p1", "p5", "p2", "p4"])
    ]

    fixture = load_fixture_manifest(manifest_path)
    train, valid = select_fixture_records(records, fixture)

    assert [record.participant_id for record in train] == ["p1", "p2", "p3", "p4", "p5"]
    assert [record.participant_id for record in valid] == ["p6"]
    assert {record.session_folder for record in train + valid} == {
        f"p{index}-session" for index in range(1, 7)
    }


def test_fixture_manifest_rejects_missing_or_overlapping_selection(tmp_path: Path) -> None:
    payload = _manifest()
    payload["validation_participants"] = ["p5"]
    manifest_path = tmp_path / "fixture.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="disjoint"):
        load_fixture_manifest(manifest_path)

    payload = _manifest()
    payload["selected_sessions"] = dict(payload["selected_sessions"])
    del payload["selected_sessions"]["p6"]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    fixture = load_fixture_manifest(manifest_path)

    records = [_record(participant, f"{participant}-session", index) for index, participant in enumerate(["p1", "p2", "p3", "p4", "p5"])]
    with pytest.raises(ValueError, match="missing selected session"):
        select_fixture_records(records, fixture)


def test_fixture_oof_folds_are_deterministic_and_train_on_multiple_participants() -> None:
    first = build_fixture_oof_folds(["p1", "p2", "p3", "p4", "p5"], n_folds=5, seed=7)
    second = build_fixture_oof_folds(["p1", "p2", "p3", "p4", "p5"], n_folds=5, seed=7)

    assert first == second
    assert sorted(participant for fold in first for participant in fold) == [
        "p1",
        "p2",
        "p3",
        "p4",
        "p5",
    ]
    assert all(len(fold) == 1 for fold in first)
    assert all(len(set("p1 p2 p3 p4 p5".split()) - set(fold)) >= 4 for fold in first)
