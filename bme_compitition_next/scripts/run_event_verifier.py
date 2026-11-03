"""Train and evaluate the event-level verifier on a candidate cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from eating_event.candidates import (
    fit_candidate_model,
    participant_oof_candidate_scores,
    split_participants,
)
from eating_event.config import load_config
from eating_event.data.manifest import (
    discover_raw_files,
    events_for_record,
    filter_meal_events_by_ledger,
    load_meal_events,
)
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval, evaluate_events, interval_iou
from eating_event.short_fixture import (
    build_fixture_oof_folds,
    load_fixture_manifest,
    select_fixture_records,
)
from eating_event.verifier import (
    build_event_candidates,
    decode_event_candidates,
    fit_event_verifier,
    validate_candidate_labels,
)

try:
    from scripts.run_candidate_baseline import (
        _build_table,
        _cache_key,
        _cache_metadata,
        _load_table,
        _merge_intervals,
    )
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import (
        _build_table,
        _cache_key,
        _cache_metadata,
        _load_table,
        _merge_intervals,
    )

from eating_event.provenance import build_cache_runtime_provenance, resolve_formal_cache_dir


def _long_false_positive_fraction(
    predictions: list[EventInterval],
    truths: list[EventInterval],
    *,
    long_duration_ms: int = 600_000,
) -> float:
    """Return the fraction of false-positive predictions that are long events."""

    metrics = evaluate_events(predictions, truths)
    matched_prediction_indices = {match.prediction_index for match in metrics.matches}
    false_positive_indices = [
        index for index in range(len(predictions)) if index not in matched_prediction_indices
    ]
    if not false_positive_indices:
        return 0.0
    long_count = sum(
        predictions[index].end_ms - predictions[index].start_ms >= long_duration_ms
        for index in false_positive_indices
    )
    return long_count / len(false_positive_indices)


def _event_coverage_recall(predictions: list[EventInterval], truths: list[EventInterval]) -> float:
    """Measure whether each truth has at least one candidate above official IoU."""

    if not truths:
        return 1.0
    covered = sum(any(interval_iou(prediction, truth) > 0.25 for prediction in predictions) for truth in truths)
    return covered / len(truths)


def _score_summary(values: list[float] | np.ndarray) -> dict[str, float | int]:
    scores = np.asarray(values, dtype=np.float64)
    if scores.size == 0:
        return {"count": 0}
    percentiles = np.percentile(scores, [0, 10, 25, 50, 75, 90, 100])
    return {
        "count": int(scores.size),
        "min": float(percentiles[0]),
        "p10": float(percentiles[1]),
        "p25": float(percentiles[2]),
        "median": float(percentiles[3]),
        "p75": float(percentiles[4]),
        "p90": float(percentiles[5]),
        "max": float(percentiles[6]),
    }


def _binary_score_metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, float | int]:
    keep = np.asarray(labels, dtype=np.int8) >= 0
    y = np.asarray(labels, dtype=np.int8)[keep]
    values = np.asarray(scores, dtype=np.float64)[keep]
    result: dict[str, float | int] = {
        "positive": int((y == 1).sum()),
        "negative": int((y == 0).sum()),
        "ignored": int((np.asarray(labels, dtype=np.int8) < 0).sum()),
        "supervised": int(y.size),
        "score_summary": _score_summary(values),
    }
    if y.size and np.unique(y).size == 2:
        from sklearn.metrics import average_precision_score, roc_auc_score

        result["auroc"] = float(roc_auc_score(y, values))
        result["auprc"] = float(average_precision_score(y, values))
    else:
        result["auroc"] = None
        result["auprc"] = None
    return result


def main() -> None:
    started_at = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--eligibility", type=Path, required=True)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/event-verifier.json"))
    parser.add_argument("--participants", nargs="*", default=None)
    parser.add_argument("--fixture-manifest", type=Path, default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--valid-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260910)
    parser.add_argument("--candidate-threshold", type=float, default=0.35)
    parser.add_argument("--candidate-quantile", type=float, default=None)
    parser.add_argument("--candidate-fuse-gap-ms", type=int, default=120_000)
    parser.add_argument("--decode-fuse-gap-ms", type=int, default=600_000)
    parser.add_argument("--verifier-threshold", type=float, default=0.5)
    parser.add_argument("--candidate-max-iter", type=int, default=100)
    parser.add_argument("--verifier-max-iter", type=int, default=100)
    parser.add_argument("--verifier-positive-weight", type=float, default=3.0)
    parser.add_argument("--oof-folds", type=int, default=5)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--step-seconds", type=float, default=None)
    args = parser.parse_args()
    if args.verifier_positive_weight <= 0:
        raise ValueError("--verifier-positive-weight must be positive")

    config = load_config(args.config)
    cache_root = resolve_formal_cache_dir(args.cache_dir)
    if args.window_seconds is not None or args.step_seconds is not None:
        config = replace(
            config,
            window_seconds=config.window_seconds if args.window_seconds is None else args.window_seconds,
            step_seconds=config.step_seconds if args.step_seconds is None else args.step_seconds,
        )
        if config.window_seconds <= 0 or config.step_seconds <= 0 or config.step_seconds > config.window_seconds:
            raise ValueError("window/step overrides must be positive and step <= window")
    eligibility_bytes = args.eligibility.expanduser().resolve().read_bytes()
    eligibility_payload = json.loads(eligibility_bytes.decode("utf-8"))
    if not isinstance(eligibility_payload, dict) or eligibility_payload.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("event verifier requires participant_eligibility_v3")
    eligibility_cache_hash = str(eligibility_payload.get("label_eligible_event_denominator_sha256", ""))
    if not eligibility_cache_hash:
        raise ValueError("eligibility artifact lacks stable label-eligible ledger hash")
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    meal_events = filter_meal_events_by_ledger(
        meal_events, eligibility_payload, eligibility_field="training_eligibility"
    )
    records = discover_raw_files(config.raw_data_root)
    fixture = load_fixture_manifest(args.fixture_manifest) if args.fixture_manifest else None
    if fixture is not None:
        if args.participants or args.max_files_per_participant is not None:
            raise ValueError("--fixture-manifest cannot be combined with participant/file limits")
        if not np.isclose(args.candidate_threshold, fixture.candidate_threshold):
            raise ValueError(
                "fixture candidate threshold mismatch; the frozen fixture retains its declared threshold"
            )
        train_records, valid_records = select_fixture_records(records, fixture)
        records = train_records + valid_records
        train_participants = fixture.training_participants
        valid_participants = fixture.validation_participants
    else:
        if args.participants:
            selected = set(args.participants)
            records = [record for record in records if record.participant_id in selected]
        if args.max_files_per_participant is not None:
            counts: dict[str, int] = defaultdict(int)
            limited = []
            for record in records:
                if counts[record.participant_id] >= args.max_files_per_participant:
                    continue
                limited.append(record)
                counts[record.participant_id] += 1
            records = limited
        train_participants, valid_participants = split_participants(
            [record.participant_id for record in records],
            valid_fraction=args.valid_fraction,
            seed=args.split_seed,
        )
    train_set, valid_set = set(train_participants), set(valid_participants)

    tables = {}
    cache_entries: list[dict[str, object]] = []
    skipped: dict[str, str] = {}
    for record in records:
        expected_metadata = _cache_metadata(
            record,
            config,
            eligibility_artifact_sha256=eligibility_cache_hash,
        )
        cache_path = cache_root / f"{expected_metadata['cache_key']}.npz"
        if cache_path.is_file():
            table = _load_table(cache_path, expected_metadata=expected_metadata)
        elif args.cache_only:
            skipped[str(record.path)] = "cache missing in --cache-only mode"
            continue
        else:
            try:
                table = _build_table(
                    record,
                    config,
                    events_for_record(record, meal_events),
                    cache_root,
                    eligibility_artifact_sha256=eligibility_cache_hash,
                )
            except RawFileFormatError as exc:
                skipped[str(record.path)] = str(exc)
                continue
        tables[record.path] = (record, table)
        cache_entries.append(
            {
                "participant_id": record.participant_id,
                "session_id": record.session_folder,
                "path": str(record.path),
                "cache_path": str(cache_path),
                "cache_sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
            }
        )

    if fixture is not None and skipped:
        failure = {
            "result": "fail",
            "failure_class": "VALIDATION_HARNESS / FIXTURE_DESIGN",
            "failure_stage": "fixture_loading",
            "fixture_id": fixture.fixture_id,
            "skipped_files": skipped,
            "reason": "frozen fixture records could not all be loaded",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ValueError(f"fixture-loading failure: {len(skipped)} frozen records unavailable")

    cache_provenance = None
    if cache_entries:
        first_record = next(iter(tables.values()))[0]
        first_metadata = _cache_metadata(
            first_record,
            config,
            eligibility_artifact_sha256=eligibility_cache_hash,
        )
        cache_provenance = build_cache_runtime_provenance(
            cache_root,
            cache_entries,
            first_metadata,
        )
    provenance_path = args.output.expanduser().resolve().with_name(
        args.output.expanduser().resolve().stem + "-provenance.json"
    )
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(cache_provenance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("cache_provenance=" + json.dumps(cache_provenance, ensure_ascii=False))

    tables_by_participant: dict[str, list[object]] = defaultdict(list)
    table_index_by_path: dict[Path, int] = {}
    for path, (record, table) in tables.items():
        table_index_by_path[path] = len(tables_by_participant[record.participant_id])
        tables_by_participant[record.participant_id].append(table)

    train_tables_by_participant = {
        participant: tables_by_participant[participant]
        for participant in train_participants
        if tables_by_participant[participant]
    }
    if fixture is not None and set(train_tables_by_participant) != set(train_participants):
        missing_participants = sorted(set(train_participants) - set(train_tables_by_participant))
        raise ValueError(f"fixture-loading failure: missing training participants {missing_participants}")
    if len(train_tables_by_participant) < 2:
        raise ValueError("event verifier OOF training needs at least two train participants with cached tables")
    oof_folds = build_fixture_oof_folds(
        train_participants,
        n_folds=args.oof_folds,
        seed=args.split_seed,
    )
    if fixture is not None and any(len(set(train_participants) - set(held_out)) < 2 for held_out in oof_folds):
        raise ValueError("fixture OOF design failure: every OOF model needs multiple training participants")
    train_table_list = [table for participant in train_participants for table in train_tables_by_participant.get(participant, [])]
    candidate_x = np.vstack([table.features for table in train_table_list])
    candidate_y = np.concatenate([table.labels for table in train_table_list])
    full_candidate_model = fit_candidate_model(
        candidate_x,
        candidate_y,
        random_state=args.split_seed,
        max_iter=args.candidate_max_iter,
    )
    oof_scores_by_participant, oof_fallback_participants = participant_oof_candidate_scores(
        train_tables_by_participant,
        random_state=args.split_seed,
        n_folds=min(args.oof_folds, len(train_tables_by_participant)),
        max_iter=args.candidate_max_iter,
    )
    if oof_fallback_participants:
        print(f"oof_fallback_participants={oof_fallback_participants}")

    verifier_features: list[np.ndarray] = []
    verifier_labels: list[int] = []
    scored_tables: list[tuple[object, object, np.ndarray]] = []
    score_summary: list[float] = []
    full_train_score_summary: list[float] = []
    for path, (record, table) in tables.items():
        if record.participant_id in train_set:
            window_scores = oof_scores_by_participant[record.participant_id][table_index_by_path[path]]
            full_train_score_summary.extend(full_candidate_model.predict_scores(table.features).tolist())
        else:
            window_scores = full_candidate_model.predict_scores(table.features)
        score_summary.extend(window_scores.tolist())
        scored_tables.append((record, table, window_scores))

    candidate_threshold = args.candidate_threshold
    if args.candidate_quantile is not None:
        if not 0 < args.candidate_quantile < 1:
            raise ValueError("candidate_quantile must be in (0, 1)")
        candidate_threshold = float(np.quantile(np.asarray(full_train_score_summary), args.candidate_quantile))

    validation_candidates: dict[str, list[object]] = defaultdict(list)
    validation_candidate_intervals: dict[str, list[EventInterval]] = defaultdict(list)
    truth_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    candidate_counts = {"train": 0, "valid": 0}
    fold_by_participant = {
        participant: f"oof-{index}"
        for index, held_out in enumerate(oof_folds)
        for participant in held_out
    }
    oof_fold_stats: dict[str, dict[str, object]] = {}
    for index, held_out in enumerate(oof_folds):
        fold_id = f"oof-{index}"
        fold_labels = np.concatenate(
            [
                table.labels
                for participant in held_out
                for table in train_tables_by_participant[participant]
            ]
        )
        oof_fold_stats[fold_id] = {
            "held_out_participants": list(held_out),
            "training_participants": sorted(set(train_participants) - set(held_out)),
            "window_label_counts": {
                "positive": int((fold_labels == 1).sum()),
                "negative": int((fold_labels == 0).sum()),
                "ignore": int((fold_labels < 0).sum()),
            },
            "candidate_label_counts": {"positive": 0, "negative": 0},
        }
    oof_label_values: list[int] = []
    oof_score_values: list[float] = []
    oof_fold_labels: dict[str, list[int]] = defaultdict(list)
    oof_fold_scores: dict[str, list[float]] = defaultdict(list)
    for record, table, window_scores in scored_tables:
        candidates = build_event_candidates(
            table.windows,
            window_scores,
            candidate_threshold=candidate_threshold,
            fuse_gap_ms=args.candidate_fuse_gap_ms,
            truths=events_for_record(record, meal_events),
        )
        if record.participant_id in train_set:
            verifier_features.extend(candidate.features for candidate in candidates)
            verifier_labels.extend(candidate.label for candidate in candidates)
            candidate_counts["train"] += len(candidates)
            fold_id = fold_by_participant[record.participant_id]
            fold_candidate_counts = oof_fold_stats[fold_id]["candidate_label_counts"]
            fold_candidate_counts["positive"] += sum(candidate.label == 1 for candidate in candidates)
            fold_candidate_counts["negative"] += sum(candidate.label == 0 for candidate in candidates)
        else:
            validation_candidates[record.participant_id].extend(candidates)
            validation_candidate_intervals[record.participant_id].extend(candidate.interval for candidate in candidates)
            truth_by_participant[record.participant_id].extend(events_for_record(record, meal_events))
            candidate_counts["valid"] += len(candidates)

        if record.participant_id in train_set:
            table_index = table_index_by_path[record.path]
            oof_scores = oof_scores_by_participant[record.participant_id][table_index]
            oof_label_values.extend(table.labels.tolist())
            oof_score_values.extend(oof_scores.tolist())
            fold_id = fold_by_participant[record.participant_id]
            oof_fold_labels[fold_id].extend(table.labels.tolist())
            oof_fold_scores[fold_id].extend(oof_scores.tolist())

    for fold_id in oof_fold_stats:
        oof_fold_stats[fold_id]["oof_metrics"] = _binary_score_metrics(
            np.asarray(oof_fold_labels[fold_id], dtype=np.int8),
            np.asarray(oof_fold_scores[fold_id], dtype=np.float64),
        )

    if score_summary:
        print(
            "candidate_score_quantiles="
            + json.dumps(np.percentile(np.asarray(score_summary), [0, 25, 50, 75, 90, 99, 100]).tolist())
        )
    verifier_y = np.asarray(verifier_labels, dtype=np.int8)
    candidate_label_counts = {
        "positive": int((verifier_y == 1).sum()),
        "negative": int((verifier_y == 0).sum()),
    }
    try:
        validate_candidate_labels(verifier_y)
    except ValueError as exc:
        failure = {
            "result": "fail",
            "failure_class": "VALIDATION_HARNESS / FIXTURE_DESIGN",
            "failure_stage": "candidate_generation",
            "error": str(exc),
            "fixture_id": fixture.fixture_id if fixture is not None else None,
            "candidate_threshold": candidate_threshold,
            "candidate_threshold_provenance": (
                fixture.candidate_threshold_provenance if fixture is not None else "untracked"
            ),
            "candidate_counts": candidate_counts,
            "candidate_label_counts": candidate_label_counts,
            "oof_metrics": _binary_score_metrics(
                np.asarray(oof_label_values, dtype=np.int8),
                np.asarray(oof_score_values, dtype=np.float64),
            ),
            "oof_fold_stats": oof_fold_stats,
            "runtime_seconds": time.perf_counter() - started_at,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
        print("candidate_generation_failure=" + json.dumps(failure, ensure_ascii=False))
        raise
    verifier_x = np.vstack(verifier_features)
    print(
        f"verifier_candidates={verifier_y.size} "
        f"positive={int((verifier_y == 1).sum())} negative={int((verifier_y == 0).sum())}"
    )
    verifier = fit_event_verifier(
        verifier_x,
        verifier_y,
        random_state=args.split_seed,
        positive_weight=args.verifier_positive_weight,
        max_iter=args.verifier_max_iter,
    )

    candidate_predictions: list[EventInterval] = []
    candidate_truths: list[EventInterval] = []
    candidate_participant_metrics: dict[str, object] = {}
    for participant in valid_participants:
        candidate_events = _merge_intervals(
            validation_candidate_intervals[participant], fuse_gap_ms=args.decode_fuse_gap_ms
        )
        truths = sorted(set(truth_by_participant[participant]))
        candidate_metric = evaluate_events(candidate_events, truths)
        candidate_predictions.extend(candidate_events)
        candidate_truths.extend(truths)
        candidate_participant_metrics[participant] = {
            "tp": candidate_metric.tp,
            "fp": candidate_metric.fp,
            "fn": candidate_metric.fn,
            "precision": candidate_metric.precision,
            "recall": candidate_metric.recall,
            "f1": candidate_metric.f1,
            "start_mae_ms": candidate_metric.start_mae_ms,
            "end_mae_ms": candidate_metric.end_mae_ms,
            "candidate_event_coverage_recall": _event_coverage_recall(validation_candidate_intervals[participant], truths),
            "long_fp_fraction": _long_false_positive_fraction(candidate_events, truths),
        }
    candidate_metrics = evaluate_events(candidate_predictions, candidate_truths)

    all_predictions: list[EventInterval] = []
    all_truths: list[EventInterval] = []
    participant_metrics: dict[str, object] = {}
    verifier_score_values: list[float] = []
    for participant in valid_participants:
        candidates = validation_candidates[participant]
        scores = verifier.predict_scores(np.vstack([candidate.features for candidate in candidates])) if candidates else np.empty(0)
        verifier_score_values.extend(scores.tolist())
        predictions = _merge_intervals(
            decode_event_candidates(candidates, scores, threshold=args.verifier_threshold),
            fuse_gap_ms=args.decode_fuse_gap_ms,
        )
        truths = sorted(set(truth_by_participant[participant]))
        metrics = evaluate_events(predictions, truths)
        all_predictions.extend(predictions)
        all_truths.extend(truths)
        participant_metrics[participant] = {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "start_mae_ms": metrics.start_mae_ms,
            "end_mae_ms": metrics.end_mae_ms,
            "long_fp_fraction": _long_false_positive_fraction(predictions, truths),
            "candidate": candidate_participant_metrics[participant],
        }
    metrics = evaluate_events(all_predictions, all_truths)
    fixture_payload = None
    if fixture is not None:
        fixture_payload = {
            "fixture_id": fixture.fixture_id,
            "manifest_path": str(args.fixture_manifest.expanduser().resolve()),
            "selection_seed": fixture.selection_seed,
            "oof_folds": fixture.oof_folds,
            "training_participants": list(fixture.training_participants),
            "validation_participants": list(fixture.validation_participants),
            "selected_sessions": {
                participant: list(sessions)
                for participant, sessions in fixture.selected_sessions.items()
            },
            "selection_rationale": fixture.selection_rationale,
            "candidate_threshold_provenance": fixture.candidate_threshold_provenance,
        }
    result = {
        "result": "pass",
        "fixture": fixture_payload,
        "train_participants": list(train_participants),
        "valid_participants": list(valid_participants),
        "candidate_threshold": candidate_threshold,
        "candidate_threshold_provenance": (
            fixture.candidate_threshold_provenance if fixture is not None else "untracked"
        ),
        "candidate_quantile": args.candidate_quantile,
        "candidate_fuse_gap_ms": args.candidate_fuse_gap_ms,
        "decode_fuse_gap_ms": args.decode_fuse_gap_ms,
        "verifier_threshold": args.verifier_threshold,
        "verifier_positive_weight": args.verifier_positive_weight,
        "candidate_counts": candidate_counts,
        "candidate_metrics": {
            "tp": candidate_metrics.tp,
            "fp": candidate_metrics.fp,
            "fn": candidate_metrics.fn,
            "precision": candidate_metrics.precision,
            "recall": candidate_metrics.recall,
            "f1": candidate_metrics.f1,
            "start_mae_ms": candidate_metrics.start_mae_ms,
            "end_mae_ms": candidate_metrics.end_mae_ms,
            "candidate_event_coverage_recall": _event_coverage_recall(
                [interval for participant in valid_participants for interval in validation_candidate_intervals[participant]],
                candidate_truths,
            ),
            "long_fp_fraction": _long_false_positive_fraction(candidate_predictions, candidate_truths),
        },
        "oof_fallback_participants": list(oof_fallback_participants),
        "oof_metrics": _binary_score_metrics(
            np.asarray(oof_label_values, dtype=np.int8),
            np.asarray(oof_score_values, dtype=np.float64),
        ),
        "oof_fold_stats": oof_fold_stats,
        "cache_provenance": cache_provenance,
        "verifier_fit_gate": {
            "status": "PASS",
            "candidate_label_counts": candidate_label_counts,
            "required_classes": [0, 1],
        },
        "verifier_output": {
            "generated": True,
            "candidate_count": int(verifier_y.size),
            "score_summary": _score_summary(verifier_score_values),
        },
        "verifier_label_counts": candidate_label_counts,
        "skipped_files": skipped,
        "metrics": {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "start_mae_ms": metrics.start_mae_ms,
            "end_mae_ms": metrics.end_mae_ms,
            "long_fp_fraction": _long_false_positive_fraction(all_predictions, all_truths),
        },
        "participant_metrics": participant_metrics,
        "runtime_seconds": time.perf_counter() - started_at,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
