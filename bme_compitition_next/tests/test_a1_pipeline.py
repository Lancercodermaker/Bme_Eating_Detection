from eating_event.a1.pipeline import build_role_graph, validate_role_graph


def test_role_graph_has_105_candidate_and_25_verifier_roles():
    participants = [f"p{i:02d}" for i in range(41)]
    graph = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    validate_role_graph(graph, participants)
    assert len([r for r in graph if r.kind == "candidate"]) == 105
    assert len([r for r in graph if r.kind == "verifier"]) == 25


def test_outer_valid_never_enters_role_fit_reference_or_selection():
    participants = [f"p{i:02d}" for i in range(41)]
    graph = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    for role in graph:
        assert not (set(role.outer_valid) & (set(role.fit_participants) | set(role.reference_participants) | set(role.selection_participants)))


def test_threshold_candidates_do_not_create_additional_fit_roles():
    participants = [f"p{i:02d}" for i in range(41)]
    graph = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    assert len({r.role_id for r in graph}) == len(graph)
    assert all(getattr(r, "thresholds", ()) in ((), (0.1, 0.25, 0.5)) for r in graph)


def test_corrupted_subinner_overlap_is_rejected():
    from dataclasses import replace
    import pytest
    participants = [f'p{i:02d}' for i in range(41)]
    graph = list(build_role_graph(participants))
    index = next(i for i,r in enumerate(graph) if r.subinner_fold is not None)
    graph[index] = replace(graph[index], scored_participants=graph[index].fit_participants)
    with pytest.raises(ValueError):
        validate_role_graph(graph, participants)
