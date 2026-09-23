from __future__ import annotations

from dataclasses import replace

import numpy as np

from eating_event.a1.metrics import PredictionRecord, TruthRecord, evaluate_participants, evaluate_quality
from eating_event.a2.execution import A2Candidate, FeatureCorpus, execute_validation
from eating_event.a1.pipeline import build_role_graph
from eating_event.metrics import EventInterval


class FakeVerifierBackend:
    def __init__(self) -> None:
        self.fits: list[dict[str, object]] = []
        self.scores: list[dict[str, object]] = []

    def fit(self, features, labels, participants, role):
        self.fits.append({
            "role_id": role.role_id,
            "features": np.asarray(features),
            "labels": np.asarray(labels),
            "participants": tuple(participants),
            "outer_valid": tuple(role.outer_valid),
        })
        return {"role_id": role.role_id}

    def score(self, model, features, participants, role):
        self.scores.append({
            "model": model,
            "role_id": role.role_id,
            "participants": tuple(participants),
            "schema": 26,
        })
        values = np.asarray(features, dtype=np.float32)
        return np.where(values[:, 0] > 0.5, 0.9, 0.01)


def make_corpus(*, moved_truth_participant: str | None = None) -> FeatureCorpus:
    participants = tuple(f"p{i:02d}" for i in range(41))
    roles = build_role_graph(participants)
    rows_by_role: dict[str, tuple[A2Candidate, ...]] = {}
    truths_by_participant: dict[str, tuple[TruthRecord, ...]] = {}
    for participant in participants:
        truth_interval = EventInterval(0, 180_000)
        if participant == moved_truth_participant:
            truth_interval = EventInterval(2_000_000, 2_180_000)
        truths_by_participant[participant] = (
            TruthRecord(f"{participant}:0", participant, truth_interval),
        )
    for role in roles:
        if role.kind != "candidate":
            continue
        items = []
        for participant in role.scored_participants:
            for is_positive, label, start in (
                (True, None if role.inner_fold is None and role.subinner_fold is None else 1, 0),
                (False, None if role.inner_fold is None and role.subinner_fold is None else 0, 500_000),
            ):
                features = np.zeros(26, dtype=np.float32)
                features[0] = 1.0 if is_positive else 0.0
                source16 = np.zeros(16, dtype=np.float64)
                source16[0] = features[0]
                items.append(A2Candidate(
                    role_id=role.role_id,
                    candidate_id=f"{participant}-{'positive' if is_positive else 'negative'}",
                    participant_id=participant,
                    record_id=f"r-{participant}",
                    session_id="s0",
                    component_id=f"{participant}|r-{participant}|s0|component-0",
                    interval=EventInterval(start, start + 180_000),
                    source_16d=source16,
                    features_26d=features,
                    support_indices=(),
                    label=label,
                ))
        rows_by_role[role.role_id] = tuple(items)
    return FeatureCorpus(
        participants=participants,
        roles=roles,
        candidates_by_role=rows_by_role,
        truths_by_participant=truths_by_participant,
        output_dir=None,
    )


def test_fake_full_run_uses_only_nested_verifier_roles_and_never_candidate_models() -> None:
    backend = FakeVerifierBackend()
    result = execute_validation(make_corpus(), backend=backend)

    assert result["status"] == "COMPLETE"
    assert len(backend.fits) == 25
    assert sum(not fit["role_id"].endswith("/outer") for fit in backend.fits) == 20
    assert sum(fit["role_id"].endswith("/outer") for fit in backend.fits) == 5
    assert all(fit["features"].shape[1] == 26 for fit in backend.fits)
    assert all(not (set(fit["participants"]) & set(fit["outer_valid"])) for fit in backend.fits)
    assert all(call["schema"] == 26 for call in backend.scores)
    assert all(call["role_id"].startswith("verifier/") for call in backend.scores)
    assert len([call for call in backend.scores if call["role_id"].endswith("/outer")]) == 5
    assert len(backend.scores) == 25
    assert all(len(fit["training_candidate_roles"]) == 4 for fit in result["verifier_fit_provenance"])
    assert all(fit["positive_canonical_gt_count"] >= 5 for fit in result["verifier_fit_provenance"])
    assert result["candidate_fit_attempts"] == 0
    assert result["candidate_predict_attempts"] == 0


def test_feature_values_ignore_labels_and_ground_truth_inputs() -> None:
    from eating_event.a2.features import ContextWindow, build_a2_features

    windows = [ContextWindow("candidate/x", 0, "p|r|s|0", "c", 0, 200, 1.0)]
    arguments = dict(
        source_16d=tuple(float(i) for i in range(16)),
        interval=EventInterval(0, 200),
        role_id="candidate/x",
        component_id="c",
        context_windows=windows,
    )
    untrusted_training_row = {**arguments, "label": 1, "evaluation_truths": [EventInterval(0, 200)]}
    first = build_a2_features(**arguments)
    second = build_a2_features(**{key: value for key, value in untrusted_training_row.items() if key in arguments})

    assert np.array_equal(first, second)


def test_outer_valid_ground_truth_perturbation_cannot_change_that_folds_selection_or_predictions() -> None:
    roles = build_role_graph(tuple(f"p{i:02d}" for i in range(41)))
    outer0 = next(role for role in roles if role.role_id == "candidate/outer-0/outer")
    participant = outer0.scored_participants[0]
    base = execute_validation(make_corpus(), backend=FakeVerifierBackend())
    perturbed = execute_validation(make_corpus(moved_truth_participant=participant), backend=FakeVerifierBackend())

    before = next(row for row in base["outer_results"] if row["fold_id"] == "outer-0")
    after = next(row for row in perturbed["outer_results"] if row["fold_id"] == "outer-0")
    assert before["selected_threshold"] == after["selected_threshold"]
    assert before["prediction_intervals"] == after["prediction_intervals"]


def test_zero_gt_zero_prediction_and_zero_gt_fp_have_defined_metrics() -> None:
    empty = evaluate_participants([], [], participant_ids=("6C7",))
    assert empty.tp == empty.fp == empty.fn == 0
    assert empty.f1 is None
    assert empty.participants[0].recall is None

    fp = PredictionRecord("p|r|s|c|0", "p", "r", "s", None, EventInterval(0, 600_000))
    fp_metrics = evaluate_participants([fp], [], participant_ids=("p",))
    assert (fp_metrics.tp, fp_metrics.fp, fp_metrics.fn) == (0, 1, 0)
    assert fp_metrics.long_fp_fraction == 1.0


def test_fp_zero_long_fraction_and_no_match_mae_quality_failure() -> None:
    truth = TruthRecord("p:0", "p", EventInterval(0, 180_000))
    matched = PredictionRecord("p|r|s|c|0", "p", "r", "s", None, truth.interval)
    metric = evaluate_participants([matched], [truth], participant_ids=("p",))
    assert metric.fp == 0 and metric.long_fp_fraction == 0.0

    no_match = evaluate_participants([], [truth], participant_ids=("p",))
    five_folds = [no_match] * 5
    quality = evaluate_quality(five_folds, outer_fold_f1=[None] * 5, pooled=no_match)
    assert no_match.start_mae_ms is None and no_match.end_mae_ms is None
    assert quality.stage_minimum is False


def test_one_to_one_match_competition_is_preserved() -> None:
    truth = TruthRecord("p:0", "p", EventInterval(0, 1000))
    exact = PredictionRecord("a", "p", "r", "s", None, EventInterval(0, 1000))
    partial = PredictionRecord("b", "p", "r", "s", None, EventInterval(0, 700))
    result = evaluate_participants([exact, partial], [truth], participant_ids=("p",))

    assert result.tp == 1
    assert result.fp == 1
    assert result.fn == 0
