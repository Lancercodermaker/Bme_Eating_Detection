"""Execute the formal target-only candidate coverage gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from collections import defaultdict

import numpy as np

from eating_event.artifacts import RunArtifact
from eating_event.candidates import eventize_windows, fit_candidate_model
from eating_event.config import load_config
from eating_event.coverage import (
    CandidateCoverageReport,
    CoverageRunConfig,
    FoldCoverageResult,
    G1_CANDIDATE_FUSE_GAP_MS,
    G1_CANDIDATE_QUANTILE_GRID,
    G1_COVERAGE_THRESHOLD,
    QuantileResult,
    select_candidate_quantile,
    write_coverage_reports,
)
from eating_event.evaluation import build_inner_folds, build_outer_folds
from eating_event.data.manifest import discover_raw_files_with_audit, events_for_record, load_meal_events
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval, interval_iou
try:
    from scripts.run_candidate_baseline import _build_table
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import _build_table


def build_resource_failure_report(reason: str) -> CandidateCoverageReport:
    return CandidateCoverageReport(
        gate_id="G1",
        fold_results=(),
        result="fail",
        failure_class="RESOURCE",
    )


def run_candidate_coverage(
    *,
    config_path: str | Path,
    output: str | Path,
    cache_dir: str | Path,
    outer_folds: int = 5,
    formal: bool = False,
) -> CandidateCoverageReport:
    """Fit candidate scorers in nested participant folds and report G1 coverage."""

    config = load_config(config_path)
    run_config = CoverageRunConfig(formal=formal, outer_folds=outer_folds)
    output_path = Path(output).expanduser().resolve()
    artifact = RunArtifact(output_path.parent, "g1-candidate-coverage")
    artifact.record_event("run_start", {"workflow_path": "RESEARCH", "formal": formal})
    records, audit = discover_raw_files_with_audit(config.raw_data_root)
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    tables_by_participant: dict[str, list[tuple[object, object, tuple[object, ...]]]] = defaultdict(list)
    skipped_files: dict[str, str] = {}
    for record in records:
        truths = events_for_record(record, meal_events)
        try:
            table = _build_table(record, config, truths, Path(cache_dir).expanduser().resolve())
        except RawFileFormatError as exc:
            skipped_files[str(record.path)] = str(exc)
            continue
        tables_by_participant[record.participant_id].append((record, table, truths))
    participants = sorted({record.participant_id for record in records if record.participant_id.lower() != "test"})
    folds = build_outer_folds(participants, n_folds=run_config.outer_folds, seed=run_config.selection_seed)
    fold_results: list[FoldCoverageResult] = []
    failure_class: str | None = None

    def flatten(participant_subset: tuple[str, ...]) -> list[tuple[object, object, tuple[object, ...]]]:
        return [item for participant in participant_subset for item in tables_by_participant.get(participant, ())]

    def fit_subset(items: list[tuple[object, object, tuple[object, ...]]]):
        if not items:
            raise ValueError("candidate fold has no tables")
        features = np.vstack([table.features for _, table, _ in items])
        labels = np.concatenate([table.labels for _, table, _ in items])
        return fit_candidate_model(features, labels, random_state=run_config.selection_seed, max_iter=100)

    def evaluate_subset(
        model: object,
        fit_items: list[tuple[object, object, tuple[object, ...]]],
        valid_items: list[tuple[object, object, tuple[object, ...]]],
        quantile: float,
    ) -> tuple[float, dict[str, float], int]:
        fit_scores = np.concatenate([model.predict_scores(table.features) for _, table, _ in fit_items])
        threshold = float(np.quantile(fit_scores, quantile))
        predictions: dict[str, list[object]] = defaultdict(list)
        truths: dict[str, list[object]] = defaultdict(list)
        candidate_count = 0
        for record, table, record_truths in valid_items:
            scores = model.predict_scores(table.features)
            predictions[record.participant_id].extend(
                EventInterval(start_ms, end_ms)
                for start_ms, end_ms in eventize_windows(
                    table.windows,
                    scores,
                    threshold=threshold,
                    min_duration_ms=1,
                    fuse_gap_ms=G1_CANDIDATE_FUSE_GAP_MS,
                )
            )
            truths[record.participant_id].extend(record_truths)
            candidate_count += len(predictions[record.participant_id])
        pooled = 0
        total = 0
        participant_recall: dict[str, float] = {}
        for participant, participant_truths in truths.items():
            covered = sum(
                1
                for truth in participant_truths
                if any(interval_iou(prediction, truth) > 0.25 for prediction in predictions[participant])
            )
            pooled += covered
            total += len(participant_truths)
            participant_recall[participant] = covered / len(participant_truths) if participant_truths else 1.0
        return (pooled / total if total else 0.0), participant_recall, candidate_count

    for fold in folds:
        selected_quantile: float | None = None
        outer_train_items = flatten(fold.train_participants)
        outer_valid_items = flatten(fold.valid_participants)
        quantile_results = []
        try:
            inner_folds = build_inner_folds(
                fold.train_participants,
                n_folds=min(4, len(fold.train_participants)),
                seed=run_config.selection_seed,
            )
            for quantile in G1_CANDIDATE_QUANTILE_GRID:
                inner_rows = []
                for inner in inner_folds:
                    model = fit_subset(flatten(inner.train_participants))
                    pooled, participant_recall, candidate_count = evaluate_subset(
                        model,
                        flatten(inner.train_participants),
                        flatten(inner.valid_participants),
                        quantile,
                    )
                    event_bearing = [value for participant, value in participant_recall.items() if participant]
                    inner_rows.append((pooled, min(event_bearing, default=1.0), candidate_count))
                quantile_results.append(
                    QuantileResult(
                        quantile=quantile,
                        pooled_recall=float(np.mean([row[0] for row in inner_rows])),
                        worst_participant_recall=float(min((row[1] for row in inner_rows), default=0.0)),
                        candidate_count=int(sum(row[2] for row in inner_rows)),
                    )
                )
            selected_quantile = select_candidate_quantile(quantile_results).quantile
            model = fit_subset(outer_train_items)
            pooled, participant_recall, candidate_count = evaluate_subset(
                model, outer_train_items, outer_valid_items, selected_quantile
            )
        except (ValueError, RuntimeError) as exc:
            pooled = 0.0
            participant_recall = {participant: 0.0 for participant in fold.valid_participants}
            candidate_count = 0
            failure_class = "DATA/PIPELINE"
            skipped_files.setdefault(f"fold:{fold.fold_id}", str(exc))
        fold_results.append(
            FoldCoverageResult(
                fold_id=fold.fold_id,
                pooled_recall=pooled,
                participant_recall=participant_recall,
                selected_quantile=selected_quantile,
                candidate_count=candidate_count,
            )
        )
    gate_pass = bool(fold_results) and all(
        result.pooled_recall >= G1_COVERAGE_THRESHOLD for result in fold_results
    ) and not skipped_files
    if not gate_pass and failure_class is None:
        failure_class = "DATA/PIPELINE"
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=tuple(fold_results),
        result="pass" if gate_pass else "fail",
        failure_class=failure_class,
    )
    write_coverage_reports(
        report,
        output=output_path,
        by_fold=output_path.with_name("g1-candidate-coverage-by-fold.json"),
        by_participant=output_path.with_name("g1-candidate-coverage-by-participant.json"),
    )
    artifact.write_json("coverage.json", report.to_dict())
    artifact.write_json("skipped_files.json", skipped_files)
    artifact.record_event(
        "gate_result",
        {"gate_id": "G1", "result": report.result, "failure_class": report.failure_class},
    )
    artifact.record_event("run_end", {"final_status": report.result})
    artifact.finalize()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--outer-folds", type=int, default=5)
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    try:
        report = run_candidate_coverage(
            config_path=args.config,
            output=args.output,
            cache_dir=args.cache_dir,
            outer_folds=args.outer_folds,
            formal=args.formal,
        )
    except KeyboardInterrupt:
        report = build_resource_failure_report("formal coverage interrupted after bounded resource observation")
        output_path = args.output.expanduser().resolve()
        write_coverage_reports(
            report,
            output=output_path,
            by_fold=output_path.with_name("g1-candidate-coverage-by-fold.json"),
            by_participant=output_path.with_name("g1-candidate-coverage-by-participant.json"),
        )
        artifact = RunArtifact(output_path.parent, "g1-candidate-coverage")
        artifact.record_event("run_start", {"workflow_path": "RESEARCH", "resource_failure": True})
        artifact.record_event(
            "gate_result",
            {"gate_id": "G1", "result": "fail", "failure_class": "RESOURCE", "reason": "interrupted"},
        )
        artifact.record_event("run_end", {"final_status": "fail"})
        artifact.finalize()
    payload = report.to_dict()
    payload.update(
        {
            "run_id": "g1-candidate-coverage",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": report.result,
        }
    )
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if report.result != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
