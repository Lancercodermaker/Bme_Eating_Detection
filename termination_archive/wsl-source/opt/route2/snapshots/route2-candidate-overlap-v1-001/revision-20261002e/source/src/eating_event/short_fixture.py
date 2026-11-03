"""Frozen participant/session selection for the bounded Short E2E harness."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from eating_event.data.manifest import RawFileRecord


@dataclass(frozen=True)
class ShortE2EFixture:
    fixture_id: str
    selection_seed: int
    candidate_threshold: float
    oof_folds: int
    training_participants: tuple[str, ...]
    validation_participants: tuple[str, ...]
    selected_sessions: Mapping[str, tuple[str, ...]]
    selection_rationale: str
    candidate_threshold_provenance: str = "unspecified"

    @property
    def all_participants(self) -> tuple[str, ...]:
        return self.training_participants + self.validation_participants


def load_fixture_manifest(path: str | Path) -> ShortE2EFixture:
    manifest_path = Path(path).expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("short E2E fixture manifest must be a JSON object")
    if payload.get("schema_version") != "short_e2e_fixture_v1":
        raise ValueError("unsupported short E2E fixture manifest schema")
    training = tuple(str(value) for value in payload.get("training_participants", ()))
    validation = tuple(str(value) for value in payload.get("validation_participants", ()))
    if len(training) < 5:
        raise ValueError("short E2E fixture needs at least five training participants")
    if not validation:
        raise ValueError("short E2E fixture needs an independent validation participant")
    if set(training) & set(validation):
        raise ValueError("short E2E fixture participants must be disjoint")
    if len(set(training + validation)) != len(training) + len(validation):
        raise ValueError("short E2E fixture participant list contains duplicates")
    raw_sessions = payload.get("selected_sessions", {})
    if not isinstance(raw_sessions, Mapping):
        raise ValueError("short E2E fixture selected_sessions must be a mapping")
    selected_sessions: dict[str, tuple[str, ...]] = {}
    for participant, sessions in raw_sessions.items():
        if not isinstance(sessions, Sequence) or isinstance(sessions, (str, bytes)):
            raise ValueError("short E2E fixture sessions must be lists")
        normalized = tuple(str(session) for session in sessions)
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"duplicate selected session for {participant}")
        selected_sessions[str(participant)] = normalized
    if not str(payload.get("selection_rationale", "")).strip():
        raise ValueError("short E2E fixture needs a selection rationale")
    return ShortE2EFixture(
        fixture_id=str(payload.get("fixture_id", "")),
        selection_seed=int(payload.get("selection_seed")),
        candidate_threshold=float(payload.get("candidate_threshold")),
        oof_folds=int(payload.get("oof_folds")),
        training_participants=training,
        validation_participants=validation,
        selected_sessions=selected_sessions,
        selection_rationale=str(payload["selection_rationale"]),
        candidate_threshold_provenance=str(
            payload.get("candidate_threshold_provenance", "unspecified")
        ),
    )


def build_fixture_oof_folds(
    participants: Sequence[str],
    *,
    n_folds: int,
    seed: int,
) -> tuple[tuple[str, ...], ...]:
    """Build the same deterministic participant OOF partition used by the harness."""

    unique = tuple(sorted({str(participant) for participant in participants}))
    if len(unique) < 2:
        raise ValueError("fixture OOF scoring needs at least two participants")
    if n_folds < 2:
        raise ValueError("fixture OOF scoring needs at least two folds")
    fold_count = min(n_folds, len(unique))
    rng = np.random.default_rng(seed)
    shuffled = [unique[index] for index in rng.permutation(len(unique))]
    return tuple(tuple(shuffled[index::fold_count]) for index in range(fold_count))


def select_fixture_records(
    records: Sequence[RawFileRecord],
    fixture: ShortE2EFixture,
) -> tuple[list[RawFileRecord], list[RawFileRecord]]:
    by_key: dict[tuple[str, str], list[RawFileRecord]] = {}
    for record in records:
        by_key.setdefault((record.participant_id, record.session_folder), []).append(record)
    selected: dict[str, list[RawFileRecord]] = {}
    for participant in fixture.all_participants:
        sessions = fixture.selected_sessions.get(participant)
        if not sessions:
            raise ValueError(f"missing selected session manifest entry for {participant}")
        selected[participant] = []
        for session in sessions:
            matches = by_key.get((participant, session), [])
            if len(matches) != 1:
                raise ValueError(
                    f"selected session is not unique or missing: {participant}/{session}"
                )
            selected[participant].append(matches[0])
    train = [record for participant in fixture.training_participants for record in selected[participant]]
    valid = [record for participant in fixture.validation_participants for record in selected[participant]]
    if {record.path for record in train} & {record.path for record in valid}:
        raise ValueError("short E2E fixture train and validation records overlap")
    return train, valid
