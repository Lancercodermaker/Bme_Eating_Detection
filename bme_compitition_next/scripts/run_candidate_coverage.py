"""Execute the formal target-only candidate coverage gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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
    apply_raw_failure_to_manifest,
    build_formal_eligibility,
    build_event_ledger_artifact,
    build_participant_eligibility_artifact,
    cache_manifest_sha256,
    deduplicate_event_intervals,
    formal_gate_passes,
    select_candidate_quantile,
    validate_participant_eligibility_artifact,
    validate_event_ledger_artifact,
    write_coverage_reports,
)
from eating_event.evaluation import build_inner_folds, build_outer_folds
from eating_event.data.manifest import (
    ManifestAudit,
    discover_raw_files_with_audit,
    events_for_record,
    filter_meal_events_by_ledger,
    load_meal_events,
)
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval, interval_iou
try:
    from scripts.run_candidate_baseline import _build_table, _cache_key, _cache_metadata
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import _build_table, _cache_key, _cache_metadata

from eating_event.provenance import build_cache_runtime_provenance, resolve_formal_cache_dir


def build_resource_failure_report(reason: str) -> CandidateCoverageReport:
    return CandidateCoverageReport(
        gate_id="G1",
        fold_results=(),
        result="fail",
        failure_class="RESOURCE",
    )


def _dense_window_counts_from_tables(
    meal_events: dict[str, tuple[object, ...]],
    tables_by_participant: dict[str, list[tuple[object, object, tuple[object, ...]]]],
) -> dict[tuple[str, int], int]:
    counts = {
        (participant, event_index): 0
        for participant, events in meal_events.items()
        for event_index, _ in enumerate(events)
    }
    for participant, entries in tables_by_participant.items():
        for _, table, _ in entries:
            for window in table.windows:
                for event_index, event in enumerate(meal_events.get(participant, ())):
                    if window.window.start_ms < event.end_ms and window.window.end_ms > event.start_ms:
                        counts[(participant, event_index)] += 1
    return counts


def _finalize_unexpected_failure(artifact: RunArtifact, error: BaseException) -> None:
    """Persist a fail-closed lifecycle before re-raising the unexpected error."""

    try:
        artifact.write_json(
            "unexpected-failure.json",
            {"failure_class": "IMPLEMENTATION", "reason": str(error)},
        )
        artifact.record_event(
            "gate_result",
            {"gate_id": "G1", "result": "fail", "failure_class": "IMPLEMENTATION"},
        )
        artifact.record_event("run_end", {"final_status": "fail"})
        artifact.finalize()
    except Exception:
        # Preserve the original parser/runtime exception as the actionable error.
        return


def run_candidate_coverage(
    *,
    config_path: str | Path,
    output: str | Path,
    cache_dir: str | Path,
    outer_folds: int = 5,
    formal: bool = False,
    manifest_audit_path: str | Path | None = None,
    eligibility_artifact_path: str | Path | None = None,
) -> CandidateCoverageReport:
    """Fit candidate scorers in nested participant folds and report G1 coverage."""

    config = load_config(config_path)
    run_config = CoverageRunConfig(formal=formal, outer_folds=outer_folds)
    output_path = Path(output).expanduser().resolve()
    cache_root = (
        resolve_formal_cache_dir(cache_dir)
        if formal
        else Path(cache_dir).expanduser().resolve()
    )
    cache_provenance: dict[str, object] | None = None
    artifact = RunArtifact(output_path.parent, output_path.stem)
    artifact.record_event(
        "run_start",
        {"workflow_path": "RESEARCH", "formal": formal, "resolved_cache_path": str(cache_root)},
    )
    if formal and (manifest_audit_path is None or eligibility_artifact_path is None):
        raise ValueError("formal coverage requires --manifest-audit and --eligibility")
    eligibility_payload: dict[str, object] | None = None
    eligibility_artifact_sha256: str | None = None
    eligibility_cache_hash: str | None = None
    source_audit_sha256: str | None = None
    if eligibility_artifact_path is not None:
        eligibility_path = Path(eligibility_artifact_path).expanduser().resolve()
        eligibility_bytes = eligibility_path.read_bytes()
        eligibility_artifact_sha256 = hashlib.sha256(eligibility_bytes).hexdigest()
        payload = json.loads(eligibility_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("eligibility artifact must be a JSON object")
        eligibility_payload = payload
        eligibility_cache_hash = str(payload.get("label_eligible_event_denominator_sha256", ""))
        if not eligibility_cache_hash:
            raise ValueError("eligibility artifact lacks stable label-eligible ledger hash")
    records, discovered_audit = discover_raw_files_with_audit(config.raw_data_root)
    if manifest_audit_path is None:
        audit = discovered_audit
    else:
        manifest_path = Path(manifest_audit_path).expanduser().resolve()
        manifest_bytes = manifest_path.read_bytes()
        source_audit_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        audit_payload = json.loads(
            manifest_bytes.decode("utf-8")
        )
        if not isinstance(audit_payload, dict):
            raise ValueError("manifest audit artifact must be a JSON object")
        audit = ManifestAudit.from_dict(audit_payload)
        discovered_paths = {str(record.path) for record in records}
        audited_paths = {
            str(row["path_or_file_id"])
            for row in audit.records
            if row.get("path_or_file_id")
        }
        if discovered_paths != audited_paths:
            raise ValueError("manifest audit does not cover exactly the discovered files")
    all_meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    meal_events = all_meal_events
    if eligibility_payload is not None:
        if eligibility_payload.get("schema_version") != "participant_eligibility_v3":
            raise ValueError("formal coverage requires participant_eligibility_v3")
        meal_events = filter_meal_events_by_ledger(
            all_meal_events, eligibility_payload, eligibility_field="training_eligibility"
        )
    tables_by_participant: dict[str, list[tuple[object, object, tuple[object, ...]]]] = defaultdict(list)
    skipped_files: dict[str, dict[str, str]] = {}
    status_by_path = {
        str(row["path_or_file_id"]): str(row["status"])
        for row in audit.records
        if row.get("path_or_file_id")
    }
    details_by_path = {
        str(row["path_or_file_id"]): row
        for row in audit.records
        if row.get("path_or_file_id")
    }
    for record in records:
        if status_by_path.get(str(record.path)) != "processed":
            row = details_by_path.get(str(record.path), {})
            skipped_files[str(record.path)] = {
                "status": str(row.get("status", "unknown")),
                "reason": str(row.get("reason", "missing manifest status")),
                "error": str(row.get("parser_error", "")),
            }
            continue
        truths = events_for_record(record, meal_events)
        try:
            table = _build_table(
                record,
                config,
                truths,
                cache_root,
                eligibility_artifact_sha256=eligibility_cache_hash,
            )
        except RawFileFormatError as exc:
            classification = apply_raw_failure_to_manifest(audit, record, exc)
            skipped_files[str(record.path)] = {
                "status": classification.status,
                "reason": classification.reason,
                "error": str(exc),
            }
            continue
        except Exception as exc:
            _finalize_unexpected_failure(artifact, exc)
            raise
        tables_by_participant[record.participant_id].append((record, table, truths))
    try:
        eligibility = build_formal_eligibility(records, audit)
        if formal:
            if eligibility_payload is None or source_audit_sha256 is None:
                raise ValueError("formal coverage eligibility contract was not loaded")
            dense_window_counts = _dense_window_counts_from_tables(all_meal_events, tables_by_participant)
            expected_eligibility = build_event_ledger_artifact(
                eligibility,
                all_meal_events,
                dense_window_counts=dense_window_counts,
                records=records,
                source_audit_sha256=source_audit_sha256,
            )
            validate_event_ledger_artifact(eligibility_payload, expected_eligibility)
            expected_eligible_participants = {
                participant
                for participant, details in expected_eligibility["participant_eligibility"].items()
                if details["participant_status"] == "eligible"
            }
            actual_eligible_participants = {
                record.participant_id
                for record in eligibility.eligible_records
                if record.participant_id.lower() != "test"
            }
            if actual_eligible_participants != expected_eligible_participants:
                raise ValueError("eligibility artifact mismatch: eligible participant set")
        processed_records = eligibility.eligible_records
        cache_entries: list[dict[str, object]] = []
        for record in processed_records:
            cache_path = cache_root / f"{_cache_key(record, config, eligibility_artifact_sha256=eligibility_cache_hash)}.npz"
            if not cache_path.is_file():
                raise RuntimeError(f"processed record has no cache: {record.path}")
            digest = hashlib.sha256(cache_path.read_bytes()).hexdigest()
            cache_entries.append(
                {
                    "participant_id": record.participant_id,
                    "session_id": record.session_folder,
                    "path": str(record.path),
                    "cache_path": str(cache_path),
                    "cache_sha256": digest,
                }
            )
        cache_digest = cache_manifest_sha256(cache_entries)
        if formal:
            if not processed_records:
                raise RuntimeError("formal coverage has no processed records for cache provenance")
            expected_metadata = _cache_metadata(
                processed_records[0],
                config,
                eligibility_artifact_sha256=eligibility_cache_hash,
            )
            cache_provenance = build_cache_runtime_provenance(
                cache_root,
                cache_entries,
                expected_metadata,
            )
            artifact.write_json("cache-provenance.json", cache_provenance)
    except Exception as exc:
        _finalize_unexpected_failure(artifact, exc)
        raise
    participants = sorted({record.participant_id for record in processed_records if record.participant_id.lower() != "test"})
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
            record_predictions = [
                EventInterval(start_ms, end_ms)
                for start_ms, end_ms in eventize_windows(
                    table.windows,
                    scores,
                    threshold=threshold,
                    min_duration_ms=1,
                    fuse_gap_ms=G1_CANDIDATE_FUSE_GAP_MS,
                )
            ]
            predictions[record.participant_id].extend(record_predictions)
            truths[record.participant_id].extend(record_truths)
            candidate_count += len(record_predictions)
        pooled = 0
        total = 0
        participant_recall: dict[str, float] = {}
        for participant, raw_participant_truths in truths.items():
            participant_truths = deduplicate_event_intervals(raw_participant_truths)
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
        except ValueError as exc:
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
    unexpected_failures: tuple[str, ...] = ()
    gate_pass = formal_gate_passes(fold_results, unexpected_failures=unexpected_failures)
    if not gate_pass and failure_class is None:
        failure_class = "DATA/PIPELINE"
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=tuple(fold_results),
        result="pass" if gate_pass else "fail",
        failure_class=failure_class,
        eligibility=eligibility,
        cache_manifest_sha256=cache_digest,
        event_denominator_sha256=(
            str(eligibility_payload["event_denominator_sha256"])
            if eligibility_payload is not None and "event_denominator_sha256" in eligibility_payload
            else None
        ),
        effective_valid_event_count=(
            int(eligibility_payload["effective_valid_event_count"])
            if eligibility_payload is not None and "effective_valid_event_count" in eligibility_payload
            else None
        ),
        eligibility_artifact_sha256=eligibility_artifact_sha256,
        cache_provenance=cache_provenance,
    )
    write_coverage_reports(
        report,
        output=output_path,
        by_fold=output_path.with_name("g1-candidate-coverage-by-fold.json"),
        by_participant=output_path.with_name("g1-candidate-coverage-by-participant.json"),
    )
    artifact.write_json("coverage.json", report.to_dict())
    artifact.write_json("skipped_files.json", skipped_files)
    artifact.write_json("manifest-audit.json", audit.to_dict())
    artifact.write_json("cache-manifest.json", {"entries": cache_entries, "sha256": cache_digest})
    if eligibility_payload is not None:
        artifact.write_json("eligibility.json", eligibility_payload)
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
    parser.add_argument("--manifest-audit", type=Path, default=None)
    parser.add_argument("--eligibility", type=Path, default=None)
    args = parser.parse_args()
    try:
        report = run_candidate_coverage(
            config_path=args.config,
            output=args.output,
            cache_dir=args.cache_dir,
            outer_folds=args.outer_folds,
            formal=args.formal,
            manifest_audit_path=args.manifest_audit,
            eligibility_artifact_path=args.eligibility,
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
        artifact = RunArtifact(output_path.parent, output_path.stem)
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
