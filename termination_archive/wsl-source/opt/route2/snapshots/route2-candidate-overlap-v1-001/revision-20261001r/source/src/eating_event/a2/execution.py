"""Nested OOF execution for the single frozen 26D A2 verifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import pickle
from pathlib import Path
from typing import Mapping, Protocol, Sequence

import numpy as np

from eating_event.a1.contracts import WindowIdentity
from eating_event.a1.events import A1Candidate, decode_candidates
from eating_event.a1.metrics import (
    AggregateMetrics,
    PredictionRecord,
    TruthRecord,
    evaluate_participants,
    evaluate_quality,
)
from eating_event.a1.pipeline import Role, validate_role_graph
from eating_event.a1.scoring import fit_verifier_estimator, validate_g3
from eating_event.a2.contracts import CandidateKey
from eating_event.metrics import EventInterval, interval_iou


@dataclass(frozen=True)
class A2Candidate:
    role_id: str
    candidate_id: str
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    interval: EventInterval
    source_16d: np.ndarray | Sequence[float]
    features_26d: np.ndarray | Sequence[float]
    support_indices: tuple[WindowIdentity, ...] | tuple[object, ...]
    label: int | None

    @property
    def key(self) -> CandidateKey:
        return CandidateKey(self.role_id, self.candidate_id)

    def __post_init__(self) -> None:
        if not self.role_id or not self.candidate_id or not self.participant_id:
            raise ValueError("A2 candidate identity is incomplete")
        source = np.asarray(self.source_16d, dtype=np.float64)
        features = np.asarray(self.features_26d, dtype=np.float32)
        if source.shape != (16,) or not np.isfinite(source).all():
            raise ValueError("A2 decode candidate needs 16 finite original values")
        if features.shape != (26,) or not np.isfinite(features).all():
            raise ValueError("A2 fit candidate needs 26 finite float32 values")
        if self.label not in (None, 0, 1):
            raise ValueError("A2 label must be binary or absent")
        source = source.copy()
        features = features.copy()
        source.setflags(write=False)
        features.setflags(write=False)
        object.__setattr__(self, "source_16d", source)
        object.__setattr__(self, "features_26d", features)


@dataclass(frozen=True)
class FeatureCorpus:
    participants: tuple[str, ...]
    roles: tuple[Role, ...]
    candidates_by_role: Mapping[str, tuple[A2Candidate, ...]]
    truths_by_participant: Mapping[str, tuple[TruthRecord, ...]]
    output_dir: Path | None = None
    config: Mapping[str, object] | None = None
    a1_fn_ids: tuple[str, ...] = ()
    a1_fn_categories: Mapping[str, str] | None = None
    source_hashes: Mapping[str, str] | None = None
    input_digests: Mapping[str, Mapping[str, str]] | None = None


class VerifierBackend(Protocol):
    def fit(self, features: np.ndarray, labels: np.ndarray, participants: Sequence[str], role: Role) -> object: ...

    def score(self, model: object, features: np.ndarray, participants: Sequence[str], role: Role) -> np.ndarray: ...


class DefaultVerifierBackend:
    def __init__(self, config: Mapping[str, object] | None = None) -> None:
        self.config = dict(config or {})

    def fit(self, features: np.ndarray, labels: np.ndarray, participants: Sequence[str], role: Role) -> object:
        hgb = dict(self.config.get("verifier_hgb", {}))
        return fit_verifier_estimator(
            features,
            labels,
            participants,
            positive_weight=float(hgb.get("positive_weight", 3.0)),
            random_state=int(self.config.get("seed", 20260910)),
            max_iter=int(hgb.get("max_iter", 100)),
        )

    def score(self, model: object, features: np.ndarray, participants: Sequence[str], role: Role) -> np.ndarray:
        if len(participants) != len(features) or not set(participants) <= set(role.scored_participants):
            raise ValueError("verifier scoring rows are outside the held-out candidate role")
        if not len(features):
            return np.empty(0, dtype=np.float64)
        return np.asarray(model.predict_proba(np.asarray(features, dtype=np.float32))[:, 1], dtype=np.float64)


def _truths(corpus: FeatureCorpus, participants: Sequence[str]) -> list[TruthRecord]:
    return [truth for participant in participants for truth in corpus.truths_by_participant.get(participant, ())]


def _candidate_arrays(rows: Sequence[A2Candidate]) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    features = np.asarray([row.features_26d for row in rows], dtype=np.float32)
    labels = np.asarray([row.label for row in rows], dtype=np.int8)
    participants = tuple(row.participant_id for row in rows)
    if features.shape != (len(rows), 26) or not np.isfinite(features).all():
        raise ValueError("role feature matrix must be finite 26D float32")
    if labels.shape != (len(rows),) or not set(labels.tolist()) <= {0, 1}:
        raise ValueError("verifier fit requires a separate complete binary label join")
    return features, labels, participants


def _role_hash(rows: Sequence[A2Candidate]) -> str:
    value = [[row.role_id, row.candidate_id] for row in rows]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _labels_hash(rows: Sequence[A2Candidate]) -> str:
    value = [[row.role_id, row.candidate_id, row.label] for row in rows]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _decoded(
    rows: Sequence[A2Candidate],
    scores: Sequence[float],
    *,
    threshold: float,
    config: Mapping[str, object],
) -> tuple[list[PredictionRecord], list[dict[str, object]], list[tuple[int, int]]]:
    views = [
        A1Candidate(
            candidate_id=row.candidate_id,
            participant_id=row.participant_id,
            record_id=row.record_id,
            session_id=row.session_id,
            component_id=row.component_id,
            interval=row.interval,
            features=np.asarray(row.source_16d, dtype=np.float64),
            support_indices=tuple(item for item in row.support_indices if isinstance(item, WindowIdentity)),
            source_segment_id=None,
            boundary_kind="observed_window_support_component_v1",
            label=row.label,
        )
        for row in rows
    ]
    if any(np.asarray(candidate.features).shape != (16,) for candidate in views):
        raise ValueError("A2 decode view must preserve A1's 16D type")
    decoded = decode_candidates(
        views,
        scores,
        threshold=threshold,
        min_duration_ms=int(config.get("min_duration_ms", 180000)),
        decode_fuse_gap_ms=int(config.get("decode_fuse_ms", 600000)),
    )
    by_id = {row.candidate_id: row for row in rows}
    lineage: list[dict[str, object]] = []
    prediction_intervals: list[tuple[int, int]] = []
    predictions: list[PredictionRecord] = []
    for prediction in decoded:
        source_rows = [by_id[candidate_id] for candidate_id in prediction.source_candidate_ids]
        lineage.append({
            "prediction_id": prediction.identity.stable_id,
            "role_id": source_rows[0].role_id,
            "candidate_keys": [[row.role_id, row.candidate_id] for row in source_rows],
            "interval": {"start_ms": prediction.interval.start_ms, "end_ms": prediction.interval.end_ms},
        })
        prediction_intervals.append((prediction.interval.start_ms, prediction.interval.end_ms))
        predictions.append(PredictionRecord.from_decoded(prediction))
    return predictions, lineage, prediction_intervals


def _persist_fit(corpus: FeatureCorpus, role: Role, rows: Sequence[A2Candidate], model: object, fit_record: dict[str, object]) -> None:
    if corpus.output_dir is None:
        return
    output = corpus.output_dir / "verifiers"
    output.mkdir(parents=True, exist_ok=True)
    blob = pickle.dumps(model, protocol=5)
    model_hash = hashlib.sha256(blob).hexdigest()
    signature = str(fit_record["fit_signature"])
    target = output / f"{signature}.pickle"
    if target.exists():
        raise ValueError("A2 verifier artifact already exists for the reserved role")
    target.write_bytes(blob)
    fit_record["model_sha256"] = model_hash
    fit_record["model_path"] = str(target.relative_to(corpus.output_dir))
    _append_jsonl(corpus.output_dir / "verifier-fit-ledger.jsonl", fit_record)


def _append_jsonl(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()


def _fit(
    corpus: FeatureCorpus,
    rows: Sequence[A2Candidate],
    role: Role,
    backend: VerifierBackend,
    budget: object | None,
) -> tuple[object, dict[str, object]]:
    features, labels, participants = _candidate_arrays(rows)
    try:
        validate_g3(labels, participants)
    except ValueError as exc:
        raise ValueError(f"G3: {exc}") from exc
    if set(participants) - set(role.fit_participants) or set(role.outer_valid) & set(participants):
        raise ValueError("verifier fit participants violate the frozen role")
    positive_gt = {
        (row.participant_id, truth.event_id)
        for row in rows if row.label == 1
        for truth in corpus.truths_by_participant.get(row.participant_id, ())
        if interval_iou(row.interval, truth.interval) > 0.25
    }
    fit_record: dict[str, object] = {
        "role_id": role.role_id,
        "training_candidate_roles": sorted({row.role_id for row in rows}),
        "fit_participants": sorted(set(participants)),
        "positive_candidate_count": int(np.count_nonzero(labels == 1)),
        "positive_participant_count": len({p for p, label in zip(participants, labels) if label == 1}),
        "positive_canonical_gt_count": len(positive_gt),
        "ordered_candidate_keys_sha256": _role_hash(rows),
        "feature_matrix_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "training_label_join_sha256": _labels_hash(rows),
        "feature_schema": "a2_event_context_v1",
        "feature_dim": 26,
        "fit_signature": hashlib.sha256(json.dumps({
            "role_id": role.role_id,
            "ordered_candidate_keys_sha256": _role_hash(rows),
            "feature_matrix_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
            "training_label_join_sha256": _labels_hash(rows),
            "config": dict(corpus.config or {}),
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
    }
    if budget is not None:
        budget.reserve_fit(role.role_id)
        budget.start_fit(role.role_id)
    try:
        model = backend.fit(features, labels, participants, role)
        _persist_fit(corpus, role, rows, model, fit_record)
    except Exception:
        if budget is not None:
            budget.end_fit(role.role_id, "failed")
        raise
    if budget is not None:
        budget.end_fit(role.role_id, "success")
    return model, fit_record


def _score(
    backend: VerifierBackend,
    model: object,
    rows: Sequence[A2Candidate],
    role: Role,
    *,
    corpus: FeatureCorpus,
    fit_record: Mapping[str, object],
) -> np.ndarray:
    if set(row.participant_id for row in rows) - set(role.scored_participants):
        raise ValueError("verifier scoring rows are outside the held-out candidate role")
    features = np.asarray([row.features_26d for row in rows], dtype=np.float32)
    participants = tuple(row.participant_id for row in rows)
    scores = np.asarray(backend.score(model, features, participants, role), dtype=np.float64)
    if scores.shape != (len(rows),) or not np.isfinite(scores).all():
        raise ValueError("verifier scores are invalid or misaligned")
    if corpus.output_dir is not None:
        score_key = hashlib.sha256(role.role_id.encode("utf-8")).hexdigest()[:20]
        score_dir = corpus.output_dir / "verifier-scores"
        score_dir.mkdir(parents=True, exist_ok=True)
        score_path = score_dir / f"{score_key}.npz"
        if score_path.exists():
            raise ValueError("duplicate A2 verifier score role")
        np.savez_compressed(
            score_path,
            candidate_ids=np.asarray([row.candidate_id for row in rows], dtype=np.str_),
            scores=scores,
        )
        _append_jsonl(corpus.output_dir / "verifier-score-provenance.jsonl", {
            "score_role_id": role.role_id,
            "candidate_role_id": rows[0].role_id if rows else None,
            "model_sha256": fit_record.get("model_sha256"),
            "fit_signature": fit_record["fit_signature"],
            "ordered_candidate_keys_sha256": _role_hash(rows),
            "feature_matrix_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
            "score_values_sha256": hashlib.sha256(scores.tobytes()).hexdigest(),
            "score_file": score_path.relative_to(corpus.output_dir).as_posix(),
            "score_file_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest(),
            "candidate_count": len(rows),
            "scored_participants": sorted(set(participants)),
            "threshold_reference_participants": [],
            "threshold": None,
        })
    return scores


def execute_validation(
    corpus: FeatureCorpus,
    *,
    backend: VerifierBackend | None = None,
    budget: object | None = None,
) -> dict[str, object]:
    """Run the fixed 20 inner plus 5 outer verifier roles once."""

    validate_role_graph(corpus.roles, corpus.participants)
    backend = backend or DefaultVerifierBackend(corpus.config)
    role_by_id = {role.role_id: role for role in corpus.roles}
    candidate_roles = [role for role in corpus.roles if role.kind == "candidate"]
    for role in candidate_roles:
        rows = corpus.candidates_by_role.get(role.role_id)
        if rows is None:
            raise ValueError(f"missing A1 candidate role: {role.role_id}")
        if any(row.role_id != role.role_id for row in rows):
            raise ValueError("candidate rows are not role-qualified")
        if role.inner_fold is None and any(row.label is not None for row in rows):
            raise ValueError("outer candidate labels must remain null")
        if role.inner_fold is not None and any(row.label not in (0, 1) for row in rows):
            raise ValueError("inner candidate label join is incomplete")

    outer_roles = sorted(
        (role for role in candidate_roles if role.inner_fold is None),
        key=lambda item: item.outer_fold,
    )
    all_outer_predictions: list[PredictionRecord] = []
    fold_metrics: list[AggregateMetrics] = []
    outer_results: list[dict[str, object]] = []
    all_lineage: list[dict[str, object]] = []
    fit_provenance: list[dict[str, object]] = []
    config = dict(corpus.config or {})
    thresholds = tuple(config.get("verifier_thresholds", (0.1, 0.25, 0.5)))

    for outer in outer_roles:
        inner_roles = sorted(
            (role for role in candidate_roles if role.outer_fold == outer.outer_fold and role.inner_fold is not None and role.subinner_fold is None),
            key=lambda item: item.inner_fold or "",
        )
        predictions_by_threshold: dict[float, list[PredictionRecord]] = {float(value): [] for value in thresholds}
        outer_oof: list[A2Candidate] = []
        for inner in inner_roles:
            subinner_roles = sorted(
                (role for role in candidate_roles if role.outer_fold == inner.outer_fold and role.inner_fold == inner.inner_fold and role.subinner_fold is not None),
                key=lambda item: item.subinner_fold or "",
            )
            train_rows = [row for sub in subinner_roles for row in corpus.candidates_by_role[sub.role_id]]
            verifier_role = role_by_id[f"verifier/{outer.outer_fold}/{inner.inner_fold}"]
            model, provenance = _fit(corpus, train_rows, verifier_role, backend, budget)
            fit_provenance.append(provenance)
            valid_rows = corpus.candidates_by_role[inner.role_id]
            outer_oof.extend(valid_rows)
            scores = _score(backend, model, valid_rows, verifier_role, corpus=corpus, fit_record=provenance)
            for threshold in thresholds:
                decoded, _, _ = _decoded(valid_rows, scores, threshold=float(threshold), config=config)
                predictions_by_threshold[float(threshold)].extend(decoded)

        selection: list[tuple[float, int, float]] = []
        for threshold, predictions in predictions_by_threshold.items():
            metric = evaluate_participants(
                predictions,
                _truths(corpus, outer.fit_participants),
                iou_threshold=float(config.get("strict_iou", 0.25)),
                long_fp_ms=int(config.get("long_fp_ms", 600000)),
                participant_ids=outer.fit_participants,
            )
            selection.append((metric.f1 if metric.f1 is not None else -1.0, -metric.fp, threshold))
        selected = max(selection)[2]
        if corpus.output_dir is not None:
            _append_jsonl(corpus.output_dir / "threshold-selection.jsonl", {
                "outer_fold": outer.outer_fold,
                "selected_threshold": selected,
                "selection_tuple_results": [list(value) for value in selection],
                "selection_participants": list(outer.fit_participants),
            })

        outer_verifier_role = role_by_id[f"verifier/{outer.outer_fold}/outer"]
        model, provenance = _fit(corpus, outer_oof, outer_verifier_role, backend, budget)
        fit_provenance.append(provenance)
        outer_rows = corpus.candidates_by_role[outer.role_id]
        # One verifier score call per outer fold; outer outcomes are evaluation only.
        scores = _score(backend, model, outer_rows, outer_verifier_role, corpus=corpus, fit_record=provenance)
        predictions, lineage, intervals = _decoded(outer_rows, scores, threshold=float(selected), config=config)
        all_lineage.extend({"outer_fold": outer.outer_fold, **row} for row in lineage)
        metric = evaluate_participants(
            predictions,
            _truths(corpus, outer.scored_participants),
            iou_threshold=float(config.get("strict_iou", 0.25)),
            long_fp_ms=int(config.get("long_fp_ms", 600000)),
            participant_ids=outer.scored_participants,
        )
        coverage = sum(
            any(candidate.participant_id == truth.participant_id and interval_iou(candidate.interval, truth.interval) > float(config.get("strict_iou", 0.25)) for candidate in outer_rows)
            for truth in _truths(corpus, outer.scored_participants)
        )
        fold_metrics.append(metric)
        all_outer_predictions.extend(predictions)
        outer_results.append({
            "fold_id": outer.outer_fold,
            "selected_threshold": float(selected),
            "candidate_count": len(outer_rows),
            "candidate_covered_gt": int(coverage),
            "prediction_count": len(predictions),
            "tp": metric.tp,
            "fp": metric.fp,
            "fn": metric.fn,
            "precision": metric.precision,
            "recall": metric.recall,
            "f1": metric.f1,
            "long_fp_count": metric.long_fp_count,
            "long_fp_fraction": metric.long_fp_fraction,
            "matched_count": metric.matched_count,
            "start_mae_s": None if metric.start_mae_ms is None else metric.start_mae_ms / 1000.0,
            "end_mae_s": None if metric.end_mae_ms is None else metric.end_mae_ms / 1000.0,
            "prediction_intervals": [list(interval) for interval in intervals],
            "participant_ids": list(outer.scored_participants),
        })

    pooled = evaluate_participants(
        all_outer_predictions,
        _truths(corpus, corpus.participants),
        iou_threshold=float(config.get("strict_iou", 0.25)),
        long_fp_ms=int(config.get("long_fp_ms", 600000)),
        participant_ids=corpus.participants,
    )
    quality = evaluate_quality(fold_metrics, outer_fold_f1=[metric.f1 for metric in fold_metrics], pooled=pooled)
    participant_f1 = [metric.f1 for metric in pooled.participants if metric.f1 is not None]
    event_bearing_f1 = [metric.f1 for metric in pooled.participants if metric.tp + metric.fn > 0 and metric.f1 is not None]
    fold_f1 = [float(metric.f1) for metric in fold_metrics if metric.f1 is not None]
    transitions = []
    for gt_id in corpus.a1_fn_ids:
        transitions.append({
            "ground_truth_id": gt_id,
            "a1_first_break_category": (corpus.a1_fn_categories or {}).get(gt_id, "unclassified"),
            "a2_matched": any(pair[1] == gt_id for participant in pooled.participants for pair in participant.matched_pairs),
        })
    transition_counts: dict[str, dict[str, int]] = {}
    for row in transitions:
        counts = transition_counts.setdefault(str(row["a1_first_break_category"]), {"total": 0, "a2_matched": 0})
        counts["total"] += 1
        counts["a2_matched"] += int(bool(row["a2_matched"]))
    result: dict[str, object] = {
        "status": "COMPLETE",
        "interpretation": "development evidence only; no independent participant confirmation",
        "candidate_fit_attempts": 0,
        "candidate_predict_attempts": 0,
        "verifier_fit_attempts": len(fit_provenance),
        "verifier_fit_provenance": fit_provenance,
        "outer_results": outer_results,
        "pooled": asdict(pooled),
        "pooled_candidate_count": sum(int(row["candidate_count"]) for row in outer_results),
        "pooled_candidate_covered_gt": sum(int(row["candidate_covered_gt"]) for row in outer_results),
        "participant_metrics": [asdict(item) for item in pooled.participants],
        "event_bearing_participant_macro_f1": float(np.mean(event_bearing_f1)) if event_bearing_f1 else None,
        "participant_f1_summary": {
            "mean": float(np.mean(participant_f1)) if participant_f1 else None,
            "sd": float(np.std(participant_f1, ddof=0)) if participant_f1 else None,
            "worst": float(min(participant_f1)) if participant_f1 else None,
            "participants_with_defined_f1": len(participant_f1),
            "event_bearing_participant_count": len(event_bearing_f1),
            "participant_count": len(pooled.participants),
        },
        "outer_fold_f1_summary": {
            "mean": float(np.mean(fold_f1)) if fold_f1 else None,
            "median": float(np.median(fold_f1)) if fold_f1 else None,
            "sd": float(np.std(fold_f1, ddof=0)) if fold_f1 else None,
            "iqr": float(np.percentile(fold_f1, 75) - np.percentile(fold_f1, 25)) if fold_f1 else None,
        },
        "a2_numeric_minimum": bool(quality.numeric_minimum),
        "a2_numeric_ideal": bool(quality.numeric_ideal),
        "a2_stage_minimum": bool(quality.stage_minimum),
        "a2_stage_ideal": bool(quality.stage_ideal),
        "a2_protocol_status": "SUPPORTED_ON_DEVELOPMENT_FOLDS" if quality.stage_minimum else "CLOSED_STAGE_MINIMUM_FAIL",
        "quality": asdict(quality),
        "a1_fn_stage_transitions": transitions,
        "a1_fn_stage_transition_summary": transition_counts,
        "participant_count": len(corpus.participants),
        "participant_ids": list(corpus.participants),
        "evaluation_gt_count": sum(len(corpus.truths_by_participant.get(p, ())) for p in corpus.participants),
        "formal_g1": "FAIL",
        "full_training": "BLOCKED",
        "production": "UNCHANGED",
        "source_hashes": dict(corpus.source_hashes or {}),
        "input_digests": dict(corpus.input_digests or {}),
    }
    if corpus.output_dir is not None:
        _write_json(corpus.output_dir / "prediction-lineage.json", all_lineage)
        _write_json(corpus.output_dir / "metrics.json", result)
        (corpus.output_dir / "report.md").write_text(_render_report(result), encoding="utf-8")
    return result


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_report(result: Mapping[str, object]) -> str:
    pooled = result["pooled"]
    lines = [
        "# A2 event context verifier validation",
        "",
        "Status: `COMPLETE` (development folds only; no independent participant confirmation).",
        "",
        "| Scope | Candidates | Covered GT | TP | FP | FN | Matched | Precision | Recall | F1 | Long FP | Long-FP fraction | Start MAE (s) | End MAE (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["outer_results"]:
        f1 = "NA" if row["f1"] is None else f"{row['f1']:.6f}"
        lines.append(
            f"| {row['fold_id']} | {row['candidate_count']} | {row['candidate_covered_gt']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['matched_count']} | {row['precision']:.6f} | {row['recall']:.6f} | {f1} | {row['long_fp_count']} | {row['long_fp_fraction']:.6f} | {row['start_mae_s'] if row['start_mae_s'] is not None else 'NA'} | {row['end_mae_s'] if row['end_mae_s'] is not None else 'NA'} |"
        )
    pooled_f1 = "NA" if pooled["f1"] is None else f"{pooled['f1']:.6f}"
    lines.append(
        f"| pooled | {result['pooled_candidate_count']} | {result['pooled_candidate_covered_gt']} | {pooled['tp']} | {pooled['fp']} | {pooled['fn']} | {pooled['matched_count']} | {pooled['precision']:.6f} | {pooled['recall']:.6f} | {pooled_f1} | {pooled['long_fp_count']} | {pooled['long_fp_fraction']:.6f} | {pooled['start_mae_ms'] / 1000 if pooled['start_mae_ms'] is not None else 'NA'} | {pooled['end_mae_ms'] / 1000 if pooled['end_mae_ms'] is not None else 'NA'} |"
    )
    lines.extend([
        "",
        f"Evaluation population: {result['participant_count']} participants including 6C7; {result['evaluation_gt_count']} canonical GT; event-bearing participant macro F1: {result['event_bearing_participant_macro_f1'] if result['event_bearing_participant_macro_f1'] is not None else 'NA'}.",
        f"Participant F1 mean/SD/worst: {result['participant_f1_summary']['mean']}, {result['participant_f1_summary']['sd']}, {result['participant_f1_summary']['worst']}; outer-fold F1 mean/median/SD/IQR: {result['outer_fold_f1_summary']['mean']}, {result['outer_fold_f1_summary']['median']}, {result['outer_fold_f1_summary']['sd']}, {result['outer_fold_f1_summary']['iqr']}.",
        f"A1's 81 fixed false negatives have role-qualified transition details in metrics.json; category summary: {result['a1_fn_stage_transition_summary']}.",
        "",
        "## Frozen gates",
        "",
        f"- `A2_NUMERIC_MINIMUM`: {result['a2_numeric_minimum']}",
        f"- `A2_NUMERIC_IDEAL`: {result['a2_numeric_ideal']}",
        f"- `A2_STAGE_MINIMUM`: {result['a2_stage_minimum']}",
        f"- `A2_STAGE_IDEAL`: {result['a2_stage_ideal']}",
        "- Candidate model fit/predict: 0 / 0.",
        "- A1 remains closed; Formal G1=FAIL; full training=BLOCKED; production=UNCHANGED.",
        "- No independent participant confirmation exists. The historical 75 long FP with no recorded annotation overlap have unknown actual behavior; their suppression is only an annotation-contract FP reduction, not behavior adjudication.",
        "",
        "See `metrics.json`, `run-manifest.json`, `verifier-fit-ledger.jsonl`, and `resource-segments.jsonl` for complete provenance and accounting.",
        "",
    ])
    return "\n".join(lines)
