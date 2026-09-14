"""Participant-disjoint fold construction shared by formal evaluation stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class ParticipantFold:
    fold_id: str
    train_participants: tuple[str, ...]
    valid_participants: tuple[str, ...]


def _normalise_participants(participant_ids: Iterable[str]) -> tuple[str, ...]:
    participants = tuple(sorted({str(value) for value in participant_ids}))
    if any(value.lower() == "test" for value in participants):
        raise ValueError("test participant is not accepted by participant folds")
    if len(participants) < 2:
        raise ValueError("at least two participants are required")
    return participants


def _build_folds(participant_ids: Iterable[str], *, n_folds: int, seed: int) -> tuple[ParticipantFold, ...]:
    participants = _normalise_participants(participant_ids)
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    fold_count = min(n_folds, len(participants))
    rng = np.random.default_rng(seed)
    shuffled = [participants[index] for index in rng.permutation(len(participants))]
    valid_sets = [tuple(sorted(shuffled[index::fold_count])) for index in range(fold_count)]
    return tuple(
        ParticipantFold(
            fold_id=f"fold-{index}",
            train_participants=tuple(value for value in participants if value not in set(valid)),
            valid_participants=valid,
        )
        for index, valid in enumerate(valid_sets)
    )


def build_outer_folds(
    participant_ids: Iterable[str],
    *,
    n_folds: int = 5,
    seed: int = 20260910,
) -> tuple[ParticipantFold, ...]:
    return tuple(
        ParticipantFold(
            fold_id=f"outer-{fold.fold_id.removeprefix('fold-')}",
            train_participants=fold.train_participants,
            valid_participants=fold.valid_participants,
        )
        for fold in _build_folds(participant_ids, n_folds=n_folds, seed=seed)
    )


def build_inner_folds(
    participant_ids: Iterable[str],
    *,
    n_folds: int = 4,
    seed: int = 20260910,
) -> tuple[ParticipantFold, ...]:
    return tuple(
        ParticipantFold(
            fold_id=f"inner-{fold.fold_id.removeprefix('fold-')}",
            train_participants=fold.train_participants,
            valid_participants=fold.valid_participants,
        )
        for fold in _build_folds(participant_ids, n_folds=n_folds, seed=seed)
    )
