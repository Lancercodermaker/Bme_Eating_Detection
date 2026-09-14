"""Run the participant-frozen IMU candidate baseline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

from eating_event.cache import build_cache_key, load_candidate_table, save_candidate_table
from eating_event.candidates import (
    CandidateTable,
    build_candidate_table,
    eventize_windows,
    fit_candidate_model,
    split_participants,
)
from eating_event.config import ProjectConfig, load_config
from eating_event.data.labels import WindowLabel, WindowLabelResult
from eating_event.data.manifest import (
    RawFileRecord,
    discover_raw_files,
    events_for_record,
    load_meal_events,
)
from eating_event.data.raw import RawFileFormatError, read_imu_tsv, regularize_imu
from eating_event.data.windows import WindowRecord, WindowSpec, generate_dense_windows
from eating_event.metrics import EventInterval, evaluate_events


def _cache_metadata(record: RawFileRecord, config: ProjectConfig) -> dict[str, object]:
    stat = record.path.stat()
    source_fingerprint = hashlib.sha256(
        "|".join([str(record.path), str(stat.st_size), str(stat.st_mtime_ns)]).encode("utf-8")
    ).hexdigest()
    cache_key = build_cache_key(
        source_fingerprint,
        config.window_seconds,
        config.step_seconds,
        config.feature_schema_version,
        config.label_schema_version,
    )
    return {
        "cache_key": cache_key,
        "source_fingerprint": source_fingerprint,
        "window_seconds": config.window_seconds,
        "step_seconds": config.step_seconds,
        "feature_schema_version": config.feature_schema_version,
        "label_schema_version": config.label_schema_version,
        "imu_grid_hz": config.imu_grid_hz,
        "min_coverage": config.min_coverage,
        "max_gap_seconds": config.max_gap_seconds,
    }


def _cache_key(record: RawFileRecord, config: ProjectConfig) -> str:
    """Compatibility helper used by the existing candidate runner variants."""

    return str(_cache_metadata(record, config)["cache_key"])


def _load_table(path: Path) -> CandidateTable:
    return load_candidate_table(path)


def _build_table(
    record: RawFileRecord,
    config: ProjectConfig,
    truths: tuple[EventInterval, ...],
    cache_dir: Path,
) -> CandidateTable:
    metadata = _cache_metadata(record, config)
    cache_path = cache_dir / f"{metadata['cache_key']}.npz"
    if cache_path.is_file():
        return load_candidate_table(cache_path, expected_metadata=metadata)
    raw = read_imu_tsv(record.path)
    series = regularize_imu(raw, grid_hz=config.imu_grid_hz, max_gap_seconds=config.max_gap_seconds)
    windows = generate_dense_windows(
        series.timestamps_ms,
        series.valid_mask,
        grid_hz=config.imu_grid_hz,
        window_seconds=config.window_seconds,
        step_seconds=config.step_seconds,
        min_coverage=config.min_coverage,
        max_gap_seconds=config.max_gap_seconds,
        hard_gap_mask=series.hard_gap_mask,
        segment_id=series.segment_id,
        truths=truths,
    )
    table = build_candidate_table(series, windows, participant_id=record.participant_id)
    save_candidate_table(cache_path, table, metadata=metadata)
    return table


def _merge_intervals(intervals: list[EventInterval], fuse_gap_ms: int = 600_000) -> list[EventInterval]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda event: (event.start_ms, event.end_ms))
    merged: list[EventInterval] = []
    start_ms, end_ms = ordered[0].start_ms, ordered[0].end_ms
    for event in ordered[1:]:
        if event.start_ms <= end_ms + fuse_gap_ms:
            end_ms = max(end_ms, event.end_ms)
        else:
            merged.append(EventInterval(start_ms, end_ms))
            start_ms, end_ms = event.start_ms, event.end_ms
    merged.append(EventInterval(start_ms, end_ms))
    return merged


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("artifacts/candidate_cache"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/candidate-baseline.json"))
    parser.add_argument("--participants", nargs="*", default=None)
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--valid-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260910)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--step-seconds", type=float, default=None)
    parser.add_argument("--run-id", default="candidate-baseline")
    parser.add_argument("--diagnostic-only", action="store_true")
    return parser.parse_args()


def _select_records_for_run(
    records: list[RawFileRecord],
    *,
    max_files_per_participant: int | None,
    diagnostic_only: bool,
) -> list[RawFileRecord]:
    if max_files_per_participant is None:
        return records
    if max_files_per_participant <= 0:
        raise ValueError("--max-files-per-participant must be positive")
    limited: list[RawFileRecord] = []
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        if counts[record.participant_id] >= max_files_per_participant:
            continue
        limited.append(record)
        counts[record.participant_id] += 1
    if diagnostic_only:
        by_participant: dict[str, list[RawFileRecord]] = defaultdict(list)
        participant_order: list[str] = []
        for record in limited:
            if record.participant_id not in by_participant:
                participant_order.append(record.participant_id)
            by_participant[record.participant_id].append(record)
        bounded: list[RawFileRecord] = []
        total_limit = max_files_per_participant * 2
        for round_index in range(max_files_per_participant):
            for participant in participant_order[:2]:
                values = by_participant[participant]
                if round_index < len(values):
                    bounded.append(values[round_index])
                    if len(bounded) == total_limit:
                        return bounded
        return bounded
    return limited


def main() -> None:
    args = _parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
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
    records = _select_records_for_run(
        records,
        max_files_per_participant=args.max_files_per_participant,
        diagnostic_only=args.diagnostic_only,
    )
    if args.limit_files is not None:
        if args.limit_files <= 0:
            raise ValueError("--limit-files must be positive")
        records = records[: args.limit_files]
    if not records:
        raise ValueError("no training records selected")

    participant_ids = [record.participant_id for record in records]
    train_participants, valid_participants = split_participants(
        participant_ids, valid_fraction=args.valid_fraction, seed=args.split_seed
    )
    train_set, valid_set = set(train_participants), set(valid_participants)
    print(f"records={len(records)} train_participants={train_participants} valid_participants={valid_participants}")

    tables: dict[Path, tuple[RawFileRecord, CandidateTable]] = {}
    skipped_files: dict[str, str] = {}
    for index, record in enumerate(records, start=1):
        truths = events_for_record(record, meal_events)
        try:
            table = _build_table(record, config, truths, args.cache_dir)
        except RawFileFormatError as exc:
            skipped_files[str(record.path)] = str(exc)
            print(f"skipped={record.path.name} reason={exc}")
            continue
        tables[record.path] = (record, table)
        if index == 1 or index % 10 == 0 or index == len(records):
            print(f"processed={index}/{len(records)} windows={len(table.windows)} path={record.path.name}")

    train_tables = [table for record, table in tables.values() if record.participant_id in train_set]
    train_features = np.vstack([table.features for table in train_tables])
    train_labels = np.concatenate([table.labels for table in train_tables])
    try:
        model = fit_candidate_model(train_features, train_labels, random_state=args.split_seed)
    except ValueError as exc:
        if not args.diagnostic_only:
            raise
        diagnostic_result = {
            "run_id": args.run_id,
            "diagnostic_only": True,
            "telemetry_scope": "diagnostic",
            "status": "fail",
            "failure_class": "DATA/PIPELINE",
            "reason": str(exc),
            "records": len(records),
            "processed_records": len(tables),
            "train_participants": list(train_participants),
            "valid_participants": list(valid_participants),
            "skipped_files": skipped_files,
            "started_at": started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(diagnostic_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(diagnostic_result, ensure_ascii=False))
        return

    predictions_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    truths_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    for record, table in tables.values():
        if record.participant_id not in valid_set:
            continue
        scores = model.predict_scores(table.features)
        predicted = eventize_windows(table.windows, scores, threshold=args.threshold)
        predictions_by_participant[record.participant_id].extend(
            EventInterval(start_ms, end_ms) for start_ms, end_ms in predicted
        )
        truths_by_participant[record.participant_id].extend(events_for_record(record, meal_events))

    all_predictions: list[EventInterval] = []
    all_truths: list[EventInterval] = []
    participant_metrics: dict[str, object] = {}
    for participant in valid_participants:
        predictions = _merge_intervals(predictions_by_participant[participant])
        truths = sorted(set(truths_by_participant[participant]))
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
        }
    metrics = evaluate_events(all_predictions, all_truths)
    result = {
        "config": str(args.config.resolve()),
        "records": len(records),
        "train_participants": list(train_participants),
        "valid_participants": list(valid_participants),
        "threshold": args.threshold,
        "processed_records": len(tables),
        "skipped_files": skipped_files,
        "metrics": {
            "tp": metrics.tp,
            "fp": metrics.fp,
            "fn": metrics.fn,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "start_mae_ms": metrics.start_mae_ms,
            "end_mae_ms": metrics.end_mae_ms,
        },
        "participant_metrics": participant_metrics,
        "run_id": args.run_id,
        "diagnostic_only": args.diagnostic_only,
        "telemetry_scope": "diagnostic" if args.diagnostic_only else "formal",
        "status": "pass",
        "failure_class": None,
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
