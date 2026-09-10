"""Train and evaluate the event-level verifier on a candidate cache."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from eating_event.candidates import fit_candidate_model, split_participants
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files, events_for_record, load_meal_events
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval, evaluate_events
from eating_event.verifier import (
    build_event_candidates,
    decode_event_candidates,
    fit_event_verifier,
)

from scripts.run_candidate_baseline import _build_table, _cache_key, _load_table, _merge_intervals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/event-verifier.json"))
    parser.add_argument("--participants", nargs="*", default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--valid-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260910)
    parser.add_argument("--candidate-threshold", type=float, default=0.35)
    parser.add_argument("--candidate-quantile", type=float, default=None)
    parser.add_argument("--candidate-fuse-gap-ms", type=int, default=120_000)
    parser.add_argument("--verifier-threshold", type=float, default=0.5)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--step-seconds", type=float, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.window_seconds is not None or args.step_seconds is not None:
        config = replace(
            config,
            window_seconds=config.window_seconds if args.window_seconds is None else args.window_seconds,
            step_seconds=config.step_seconds if args.step_seconds is None else args.step_seconds,
        )
        if config.window_seconds <= 0 or config.step_seconds <= 0 or config.step_seconds > config.window_seconds:
            raise ValueError("window/step overrides must be positive and step <= window")
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    records = discover_raw_files(config.raw_data_root)
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
    skipped: dict[str, str] = {}
    for record in records:
        cache_path = args.cache_dir / f"{_cache_key(record, config)}.npz"
        if cache_path.is_file():
            table = _load_table(cache_path)
        elif args.cache_only:
            skipped[str(record.path)] = "cache missing in --cache-only mode"
            continue
        else:
            try:
                table = _build_table(record, config, events_for_record(record, meal_events), args.cache_dir)
            except RawFileFormatError as exc:
                skipped[str(record.path)] = str(exc)
                continue
        tables[record.path] = (record, table)

    train_table_list = [table for record, table in tables.values() if record.participant_id in train_set]
    candidate_x = np.vstack([table.features for table in train_table_list])
    candidate_y = np.concatenate([table.labels for table in train_table_list])
    candidate_model = fit_candidate_model(candidate_x, candidate_y, random_state=args.split_seed)

    verifier_features: list[np.ndarray] = []
    verifier_labels: list[int] = []
    scored_tables: list[tuple[object, object, np.ndarray]] = []
    score_summary: list[float] = []
    for record, table in tables.values():
        window_scores = candidate_model.predict_scores(table.features)
        score_summary.extend(window_scores.tolist())
        scored_tables.append((record, table, window_scores))

    train_score_summary = [
        score
        for record, _, scores in scored_tables
        if record.participant_id in train_set
        for score in scores.tolist()
    ]
    candidate_threshold = args.candidate_threshold
    if args.candidate_quantile is not None:
        if not 0 < args.candidate_quantile < 1:
            raise ValueError("candidate_quantile must be in (0, 1)")
        candidate_threshold = float(np.quantile(np.asarray(train_score_summary), args.candidate_quantile))

    validation_candidates: dict[str, list[object]] = defaultdict(list)
    truth_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    candidate_counts = {"train": 0, "valid": 0}
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
        else:
            validation_candidates[record.participant_id].extend(candidates)
            truth_by_participant[record.participant_id].extend(events_for_record(record, meal_events))
            candidate_counts["valid"] += len(candidates)

    if score_summary:
        print(
            "candidate_score_quantiles="
            + json.dumps(np.percentile(np.asarray(score_summary), [0, 25, 50, 75, 90, 99, 100]).tolist())
        )
    verifier_x = np.vstack(verifier_features)
    verifier_y = np.asarray(verifier_labels, dtype=np.int8)
    print(
        f"verifier_candidates={verifier_y.size} "
        f"positive={int((verifier_y == 1).sum())} negative={int((verifier_y == 0).sum())}"
    )
    verifier = fit_event_verifier(verifier_x, verifier_y, random_state=args.split_seed)

    all_predictions: list[EventInterval] = []
    all_truths: list[EventInterval] = []
    participant_metrics: dict[str, object] = {}
    for participant in valid_participants:
        candidates = validation_candidates[participant]
        scores = verifier.predict_scores(np.vstack([candidate.features for candidate in candidates])) if candidates else np.empty(0)
        predictions = _merge_intervals(
            decode_event_candidates(candidates, scores, threshold=args.verifier_threshold)
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
        }
    metrics = evaluate_events(all_predictions, all_truths)
    result = {
        "train_participants": list(train_participants),
        "valid_participants": list(valid_participants),
        "candidate_threshold": candidate_threshold,
        "candidate_quantile": args.candidate_quantile,
        "candidate_fuse_gap_ms": args.candidate_fuse_gap_ms,
        "verifier_threshold": args.verifier_threshold,
        "candidate_counts": candidate_counts,
        "verifier_label_counts": {"negative": int((verifier_y == 0).sum()), "positive": int((verifier_y == 1).sum())},
        "skipped_files": skipped,
        "metrics": {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
        },
        "participant_metrics": participant_metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
