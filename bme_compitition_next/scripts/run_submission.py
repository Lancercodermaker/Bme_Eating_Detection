"""Train the frozen target-only stack and emit executable test predictions."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from eating_event.candidates import fit_candidate_model, participant_oof_candidate_scores
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files, events_for_record, load_meal_events
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval
from eating_event.verifier import build_event_candidates, decode_event_candidates, fit_event_verifier
from scripts.run_candidate_baseline import _build_table, _cache_key, _load_table, _merge_intervals


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/submission.json"))
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--step-seconds", type=float, default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--candidate-threshold", type=float, default=0.2)
    parser.add_argument("--candidate-fuse-gap-ms", type=int, default=300_000)
    parser.add_argument("--decode-fuse-gap-ms", type=int, default=600_000)
    parser.add_argument("--verifier-threshold", type=float, default=0.5)
    parser.add_argument("--candidate-max-iter", type=int, default=100)
    parser.add_argument("--verifier-max-iter", type=int, default=100)
    parser.add_argument("--verifier-positive-weight", type=float, default=3.0)
    parser.add_argument("--oof-folds", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.verifier_positive_weight <= 0:
        raise ValueError("--verifier-positive-weight must be positive")
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
    all_records = discover_raw_files(config.raw_data_root, include_test=True)
    train_records = [record for record in all_records if record.participant_id.lower() != "test"]
    test_records = [record for record in all_records if record.participant_id.lower() == "test"]
    if args.max_files_per_participant is not None:
        counts: dict[str, int] = defaultdict(int)
        limited: list[object] = []
        for record in train_records:
            if counts[record.participant_id] >= args.max_files_per_participant:
                continue
            counts[record.participant_id] += 1
            limited.append(record)
        train_records = limited
    if not train_records or not test_records:
        raise ValueError("submission runner needs both train records and official test records")

    participant_ids = [record.participant_id for record in train_records]
    train_participants = tuple(sorted(set(participant_ids)))
    tables: dict[Path, tuple[object, object]] = {}
    skipped: dict[str, str] = {}
    for record in [*train_records, *test_records]:
        cache_path = args.cache_dir / f"{_cache_key(record, config)}.npz"
        if cache_path.is_file():
            table = _load_table(cache_path)
        elif args.cache_only:
            skipped[str(record.path)] = "cache missing in --cache-only mode"
            continue
        else:
            truths = events_for_record(record, meal_events) if record.participant_id.lower() != "test" else ()
            try:
                table = _build_table(record, config, truths, args.cache_dir)
            except RawFileFormatError as exc:
                skipped[str(record.path)] = str(exc)
                continue
        tables[record.path] = (record, table)

    train_tables_by_participant: dict[str, list[object]] = defaultdict(list)
    test_table_records: list[tuple[object, object]] = []
    for path, (record, table) in tables.items():
        if record.participant_id.lower() == "test":
            test_table_records.append((record, table))
        else:
            train_tables_by_participant[record.participant_id].append(table)
    train_tables_by_participant = {
        participant: train_tables_by_participant[participant]
        for participant in train_participants
        if train_tables_by_participant[participant]
    }
    if len(train_tables_by_participant) < 2 or not test_table_records:
        raise ValueError("submission runner needs at least two train participants and one test table")

    train_table_list = [table for participant in train_participants for table in train_tables_by_participant.get(participant, [])]
    candidate_features = np.vstack([table.features for table in train_table_list])
    candidate_labels = np.concatenate([table.labels for table in train_table_list])
    full_candidate_model = fit_candidate_model(
        candidate_features,
        candidate_labels,
        max_iter=args.candidate_max_iter,
    )
    oof_scores, oof_fallback = participant_oof_candidate_scores(
        train_tables_by_participant,
        n_folds=min(args.oof_folds, len(train_tables_by_participant)),
        max_iter=args.candidate_max_iter,
    )

    verifier_features: list[np.ndarray] = []
    verifier_labels: list[int] = []
    table_indices: dict[Path, int] = {}
    for participant, participant_tables in train_tables_by_participant.items():
        for index, table in enumerate(participant_tables):
            for path, (record, candidate_table) in tables.items():
                if record.participant_id == participant and candidate_table is table:
                    table_indices[path] = index
                    truths = events_for_record(record, meal_events)
                    candidates = build_event_candidates(
                        candidate_table.windows,
                        oof_scores[participant][index],
                        candidate_threshold=args.candidate_threshold,
                        fuse_gap_ms=args.candidate_fuse_gap_ms,
                        truths=truths,
                    )
                    verifier_features.extend(candidate.features for candidate in candidates)
                    verifier_labels.extend(candidate.label for candidate in candidates)
                    break
    if not verifier_features:
        raise ValueError("submission runner produced no verifier candidates")
    verifier_x = np.vstack(verifier_features)
    verifier_y = np.asarray(verifier_labels, dtype=np.int8)
    verifier = fit_event_verifier(
        verifier_x,
        verifier_y,
        positive_weight=args.verifier_positive_weight,
        max_iter=args.verifier_max_iter,
    )

    events_by_session: dict[tuple[str, str], list[EventInterval]] = defaultdict(list)
    candidate_count = 0
    for record, table in test_table_records:
        scores = full_candidate_model.predict_scores(table.features)
        candidates = build_event_candidates(
            table.windows,
            scores,
            candidate_threshold=args.candidate_threshold,
            fuse_gap_ms=args.candidate_fuse_gap_ms,
        )
        candidate_count += len(candidates)
        verifier_scores = verifier.predict_scores(np.vstack([candidate.features for candidate in candidates])) if candidates else np.empty(0)
        predictions = decode_event_candidates(candidates, verifier_scores, threshold=args.verifier_threshold)
        events_by_session[(record.participant_id, record.session_folder)].extend(predictions)

    serialized_sessions: list[dict[str, object]] = []
    for (participant, session_folder), predictions in sorted(events_by_session.items()):
        merged = _merge_intervals(predictions, fuse_gap_ms=args.decode_fuse_gap_ms)
        serialized_sessions.append(
            {
                "participant_id": participant,
                "session_folder": session_folder,
                "events": [{"start_ms": event.start_ms, "end_ms": event.end_ms} for event in merged],
            }
        )
    result = {
        "config": str(args.config.resolve()),
        "method": "imu_local_tcn_rejected_hgb_candidate_event_verifier",
        "train_records": len(train_records),
        "test_records": len(test_records),
        "processed_train_records": len(train_table_list),
        "processed_test_records": len(test_table_records),
        "candidate_threshold": args.candidate_threshold,
        "candidate_fuse_gap_ms": args.candidate_fuse_gap_ms,
        "decode_fuse_gap_ms": args.decode_fuse_gap_ms,
        "verifier_threshold": args.verifier_threshold,
        "verifier_positive_weight": args.verifier_positive_weight,
        "candidate_count": candidate_count,
        "oof_fallback_participants": list(oof_fallback),
        "skipped_files": skipped,
        "test_sessions": serialized_sessions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"test_sessions": len(serialized_sessions), "candidate_count": candidate_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
