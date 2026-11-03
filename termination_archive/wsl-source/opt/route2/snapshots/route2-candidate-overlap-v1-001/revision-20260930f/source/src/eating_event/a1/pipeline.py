"""A1 nested role graph and bounded orchestration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from eating_event.evaluation import build_inner_folds, build_outer_folds


@dataclass(frozen=True)
class Role:
    role_id: str
    kind: str
    outer_fold: str
    inner_fold: str | None
    subinner_fold: str | None
    fit_participants: tuple[str, ...]
    reference_participants: tuple[str, ...]
    scored_participants: tuple[str, ...]
    selection_participants: tuple[str, ...]
    outer_valid: tuple[str, ...]
    thresholds: tuple[float, ...] = ()


def _ordered(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def build_role_graph(
    participants: Sequence[str],
    *,
    outer_folds: int = 5,
    inner_folds: int = 4,
    subinner_folds: int = 4,
    seed: int = 20260910,
) -> tuple[Role, ...]:
    participant_tuple = _ordered(participants)
    if len(participant_tuple) != 41:
        raise ValueError("A1 role graph requires the approved 41 participants")
    graph: list[Role] = []
    for outer in build_outer_folds(participant_tuple, n_folds=outer_folds, seed=seed):
        outer_train = _ordered(outer.train_participants)
        outer_valid = _ordered(outer.valid_participants)
        graph.append(
            Role(
                role_id=f"candidate/{outer.fold_id}/outer",
                kind="candidate",
                outer_fold=outer.fold_id,
                inner_fold=None,
                subinner_fold=None,
                fit_participants=outer_train,
                reference_participants=outer_train,
                scored_participants=outer_valid,
                selection_participants=(),
                outer_valid=outer_valid,
            )
        )
        for inner in build_inner_folds(outer_train, n_folds=inner_folds, seed=seed):
            inner_train = _ordered(inner.train_participants)
            inner_valid = _ordered(inner.valid_participants)
            graph.append(
                Role(
                    role_id=f"candidate/{outer.fold_id}/{inner.fold_id}/inner",
                    kind="candidate",
                    outer_fold=outer.fold_id,
                    inner_fold=inner.fold_id,
                    subinner_fold=None,
                    fit_participants=inner_train,
                    reference_participants=inner_train,
                    scored_participants=inner_valid,
                    selection_participants=inner_valid,
                    outer_valid=outer_valid,
                    thresholds=(0.1, 0.25, 0.5),
                )
            )
            for subinner in build_inner_folds(inner_train, n_folds=subinner_folds, seed=seed):
                sub_train = _ordered(subinner.train_participants)
                sub_valid = _ordered(subinner.valid_participants)
                graph.append(
                    Role(
                        role_id=f"candidate/{outer.fold_id}/{inner.fold_id}/{subinner.fold_id}/subinner",
                        kind="candidate",
                        outer_fold=outer.fold_id,
                        inner_fold=inner.fold_id,
                        subinner_fold=subinner.fold_id,
                        fit_participants=sub_train,
                        reference_participants=sub_train,
                        scored_participants=sub_valid,
                        selection_participants=(),
                        outer_valid=outer_valid,
                    )
                )
            graph.append(
                Role(
                    role_id=f"verifier/{outer.fold_id}/{inner.fold_id}",
                    kind="verifier",
                    outer_fold=outer.fold_id,
                    inner_fold=inner.fold_id,
                    subinner_fold=None,
                    fit_participants=inner_train,
                    reference_participants=inner_train,
                    scored_participants=inner_valid,
                    selection_participants=inner_valid,
                    outer_valid=outer_valid,
                    thresholds=(0.1, 0.25, 0.5),
                )
            )
        graph.append(
            Role(
                role_id=f"verifier/{outer.fold_id}/outer",
                kind="verifier",
                outer_fold=outer.fold_id,
                inner_fold=None,
                subinner_fold=None,
                fit_participants=outer_train,
                reference_participants=outer_train,
                scored_participants=outer_valid,
                selection_participants=(),
                outer_valid=outer_valid,
            )
        )
    return tuple(graph)


def validate_role_graph(graph: Sequence[Role], participants: Sequence[str]) -> None:
    if len(graph) != 130:
        raise ValueError(f"A1 role graph must contain 130 roles, found {len(graph)}")
    role_ids = [role.role_id for role in graph]
    if len(set(role_ids)) != len(role_ids):
        raise ValueError("role IDs must be unique")
    if len([role for role in graph if role.kind == "candidate"]) != 105:
        raise ValueError("A1 candidate role count must be 105")
    if len([role for role in graph if role.kind == "verifier"]) != 25:
        raise ValueError("A1 verifier role count must be 25")
    approved = set(map(str, participants))
    if approved != set(f"p{i:02d}" for i in range(41)) and len(approved) != 41:
        raise ValueError("role graph participants are not the approved 41 participants")
    from collections import Counter
    roots = [r for r in graph if r.kind == "candidate" and r.inner_fold is None]
    if len(roots) != 5 or Counter(p for r in roots for p in r.scored_participants) != Counter(approved):
        raise ValueError("outer validation must cover each participant once")
    for root in roots:
        if set(root.fit_participants) | set(root.scored_participants) != approved:
            raise ValueError("outer partition incomplete")
        inner = [r for r in graph if r.kind == "candidate" and r.outer_fold == root.outer_fold and r.inner_fold is not None and r.subinner_fold is None]
        if len(inner) != 4 or Counter(p for r in inner for p in r.scored_participants) != Counter(root.fit_participants):
            raise ValueError("inner validation partition incomplete")
        for item in inner:
            subs = [r for r in graph if r.kind == "candidate" and r.outer_fold == item.outer_fold and r.inner_fold == item.inner_fold and r.subinner_fold is not None]
            if len(subs) != 4 or Counter(p for r in subs for p in r.scored_participants) != Counter(item.fit_participants):
                raise ValueError("subinner validation partition incomplete")
            for child in subs:
                if set(child.fit_participants) | set(child.scored_participants) != set(item.fit_participants):
                    raise ValueError("subinner partition outside parent")
    for role in graph:
        if set(role.fit_participants) & set(role.scored_participants):
            raise ValueError("role fit/scored overlap")
        if not (set(role.fit_participants) | set(role.scored_participants)) <= approved:
            raise ValueError("role contains unapproved participant")
        if role.reference_participants != role.fit_participants:
            raise ValueError("role reference differs from fit")
        outer = set(role.outer_valid)
        if outer & set(role.fit_participants):
            raise ValueError(f"outer-valid participant in fit set for {role.role_id}")
        if outer & set(role.reference_participants):
            raise ValueError(f"outer-valid participant in reference set for {role.role_id}")
        if outer & set(role.selection_participants):
            raise ValueError(f"outer-valid participant in selection set for {role.role_id}")
        if any(participant.lower() == "test" for participant in role.fit_participants + role.scored_participants):
            raise ValueError("test participant is forbidden")


def execute_full_pipeline(bundle, config, run_dir, *, backend=None):
    from .execution import execute
    return execute(bundle, config, run_dir, backend=backend)
