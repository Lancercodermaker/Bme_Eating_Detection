"""Reconstruct and replay the frozen decision-probe A baseline only.

This is a bounded diagnostic. It performs exactly one outer A fit per fold,
does not run inner selection, does not construct N, and has no 3 s path.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import joblib
import numpy as np
import sklearn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eating_event.candidates import CandidateModel, eventize_windows, fit_candidate_model  # noqa: E402
from eating_event.data.labels import WindowLabel, WindowLabelResult  # noqa: E402
from eating_event.data.windows import WindowRecord, WindowSpec  # noqa: E402
from eating_event.evaluation import build_outer_folds  # noqa: E402
from eating_event.metrics import EventInterval, evaluate_events, interval_iou  # noqa: E402


SPEC_PATH = ROOT / "configs/formal-g1-a-baseline-reconstruction-v1.json"
HASH_PATH = ROOT / "configs/formal-g1-a-baseline-reconstruction-v1.sha256"
TARGET_SPEC_PATH = ROOT / "configs/formal-g1-decision-function-probe-v1.json"
TARGET_REPORT_PATH = ROOT / "artifacts/g1-decision-function-probe-v1/report.json"
TARGET_SCORES_PATH = ROOT / "artifacts/g1-decision-function-probe-v1/scores.npz"
FEATURE_TABLE_PATH = ROOT / "artifacts/g1-temporal-representation-probe-v1/feature-table.npz"
ELIGIBILITY_PATH = ROOT / "artifacts/g1-candidate-coverage-v4/eligibility.json"
REVIEW_PATH = ROOT / "artifacts/g1-model-temporal-representation-review-v1.json"
OUTPUT_DIR = ROOT / "artifacts/g1-a-baseline-reconstruction-v1"
SEED = 20260910
ATOL = 1e-12
RTOL = 1e-12
FUSE_GAP_MS = 300_000
IOU_THRESHOLD = 0.25
INCOMPLETE_IDS = {
    "HNU21012:1784723920000-1784728154000",
    "HNU21035:1785042527000-1785043718000",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_event_id(value: str) -> str:
    return value.replace(" ", "")


def stable_array_hash(values: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def training_input_hash(
    features: np.ndarray,
    labels: np.ndarray,
    row_keys: np.ndarray,
    indices: np.ndarray,
) -> str:
    digest = hashlib.sha256()
    selected_features = np.ascontiguousarray(features[indices], dtype=np.float64)
    selected_labels = np.ascontiguousarray(labels[indices], dtype=np.int8)
    digest.update(b"row_keys\0")
    for value in row_keys[indices]:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    digest.update(b"features_float64\0")
    digest.update(selected_features.tobytes())
    digest.update(b"labels_int8\0")
    digest.update(selected_labels.tobytes())
    return digest.hexdigest()


def load_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, np.ndarray]]:
    spec_bytes = SPEC_PATH.read_bytes()
    actual_spec_hash = hashlib.sha256(spec_bytes).hexdigest()
    expected_spec_hash = HASH_PATH.read_text(encoding="utf-8").split()[0].lower()
    if actual_spec_hash != expected_spec_hash:
        raise RuntimeError("reconstruction spec sidecar hash mismatch")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if spec.get("status") != "FROZEN_BEFORE_FIT":
        raise RuntimeError("reconstruction spec is not frozen before fit")

    target_spec_hash = sha256(TARGET_SPEC_PATH)
    if target_spec_hash != spec["source_of_truth"]["target_probe_spec"]["sha256"]:
        raise RuntimeError("target decision-function spec hash drift")
    if sha256(TARGET_REPORT_PATH) != spec["source_of_truth"]["target_report"]["sha256"]:
        raise RuntimeError("target decision-function report hash drift")
    if sha256(TARGET_SCORES_PATH) != spec["source_of_truth"]["target_scores"]["sha256"]:
        raise RuntimeError("target score artifact hash drift")
    if sha256(FEATURE_TABLE_PATH) != spec["dataset_and_stable_window_ids"]["feature_table_sha256"]:
        raise RuntimeError("feature table hash drift")

    target_spec = json.loads(TARGET_SPEC_PATH.read_text(encoding="utf-8"))
    for source in target_spec["source_of_truth"].values():
        path = ROOT / str(source["path"])
        if sha256(path) != str(source["sha256"]):
            raise RuntimeError(f"target source hash drift: {path}")
    target_report = json.loads(TARGET_REPORT_PATH.read_text(encoding="utf-8"))
    with np.load(FEATURE_TABLE_PATH, allow_pickle=True) as payload:
        features = payload["a"].astype(np.float64, copy=False)
        labels = payload["labels"].astype(np.int8, copy=False)
        participants = payload["participants"].astype(object, copy=False)
        starts = payload["starts"].astype(np.int64, copy=False)
        ends = payload["ends"].astype(np.int64, copy=False)
        row_keys = payload["row_keys"].astype(object, copy=False)
    with np.load(TARGET_SCORES_PATH, allow_pickle=True) as payload:
        target_scores = payload["baseline_scores"].astype(np.float64, copy=False)

    if features.shape != (632100, 111):
        raise RuntimeError(f"unexpected feature shape: {features.shape}")
    if not np.isfinite(features).all():
        raise RuntimeError("feature table contains non-finite values")
    arrays = (labels, participants, starts, ends, row_keys, target_scores)
    if {array.size for array in arrays} != {features.shape[0]}:
        raise RuntimeError("feature and stable-ID arrays are misaligned")
    if np.unique(row_keys).size != row_keys.size:
        raise RuntimeError("row_keys are not unique")

    return (
        spec,
        target_report,
        {
            "features": features,
            "labels": labels,
            "participants": participants,
            "starts": starts,
            "ends": ends,
            "row_keys": row_keys,
            "target_scores": target_scores,
        },
    )


def participant_indices(participants: np.ndarray, wanted: tuple[str, ...]) -> np.ndarray:
    wanted_set = set(wanted)
    return np.asarray(
        [index for index, participant in enumerate(participants) if str(participant) in wanted_set],
        dtype=np.int64,
    )


def record_path(row_key: object) -> str:
    return str(row_key).rsplit("|", 3)[0]


def window_records(data: dict[str, np.ndarray], indices: list[int]) -> list[WindowRecord]:
    ignored = WindowLabelResult(WindowLabel.IGNORE, 0.0, None)
    return [
        WindowRecord(
            window=WindowSpec(int(data["starts"][index]), int(data["ends"][index])),
            coverage=1.0,
            longest_invalid_run=0,
            label_result=ignored,
        )
        for index in indices
    ]


def eventize_replay(
    data: dict[str, np.ndarray],
    reconstructed_scores: np.ndarray,
    fold_id_by_participant: dict[str, str],
    thresholds: dict[str, float],
) -> dict[str, tuple[EventInterval, ...]]:
    by_record: dict[str, list[int]] = defaultdict(list)
    for index, row_key in enumerate(data["row_keys"]):
        by_record[record_path(row_key)].append(index)
    predictions: dict[str, list[EventInterval]] = defaultdict(list)
    for indices in by_record.values():
        if not indices:
            continue
        participant = str(data["participants"][indices[0]])
        fold_id = fold_id_by_participant[participant]
        scores = reconstructed_scores[np.asarray(indices, dtype=np.int64)]
        finite = np.isfinite(scores)
        if not finite.any():
            continue
        selected_indices = [index for index, keep in zip(indices, finite) if keep]
        selected_scores = scores[finite]
        intervals = eventize_windows(
            window_records(data, selected_indices),
            selected_scores,
            threshold=thresholds[fold_id],
            min_duration_ms=1,
            fuse_gap_ms=FUSE_GAP_MS,
        )
        predictions[participant].extend(
            EventInterval(int(start), int(end)) for start, end in intervals
        )
    return {participant: tuple(sorted(intervals)) for participant, intervals in predictions.items()}


def load_truths() -> tuple[dict[str, tuple[dict[str, Any], ...]], dict[str, str | None]]:
    eligibility = json.loads(ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    truths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligibility["event_eligibility"]:
        if not bool(row.get("training_eligibility")):
            continue
        participant = str(row["participant_id"])
        event_id = f"{participant}:{int(row['start_ms'])}-{int(row['end_ms'])}"
        truths[participant].append(
            {
                "event_id": event_id,
                "normalized_event_id": normalize_event_id(event_id),
                "participant": participant,
                "event_index": int(row["event_index"]),
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "duration_ms": int(row["duration_ms"]),
            }
        )
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    historical = {
        normalize_event_id(str(row["event_id"])): str(row["taxonomy"])
        for row in review["event_audit"]["rows"]
    }
    return (
        {participant: tuple(sorted(rows, key=lambda row: row["event_index"])) for participant, rows in truths.items()},
        historical,
    )


def best_iou(predictions: tuple[EventInterval, ...], truth: dict[str, Any]) -> float:
    interval = EventInterval(truth["start_ms"], truth["end_ms"])
    return max((interval_iou(prediction, interval) for prediction in predictions), default=0.0)


def event_replay_report(
    data: dict[str, np.ndarray],
    reconstructed_scores: np.ndarray,
    folds: tuple[Any, ...],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    truths, historical_taxonomy = load_truths()
    fold_id_by_participant = {
        participant: fold.fold_id
        for fold in folds
        for participant in fold.valid_participants
    }
    predictions = eventize_replay(data, reconstructed_scores, fold_id_by_participant, thresholds)
    all_events = [event for values in truths.values() for event in values]
    exact_events = [event for event in all_events if normalize_event_id(event["event_id"]) not in INCOMPLETE_IDS]

    def cohort_report(events: list[dict[str, Any]]) -> dict[str, Any]:
        by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            by_participant[event["event_id"].split(":", 1)[0]].append(event)
        per_fold: dict[str, Any] = {}
        total_covered = 0
        total_events = 0
        total_predictions = 0
        total_false = 0
        for fold in folds:
            fold_events = [event for event in events if event["event_id"].split(":", 1)[0] in fold.valid_participants]
            fold_truth_intervals = {
                participant: [EventInterval(event["start_ms"], event["end_ms"]) for event in values]
                for participant, values in by_participant.items()
                if participant in fold.valid_participants
            }
            fold_predictions = {
                participant: predictions.get(participant, ())
                for participant in fold.valid_participants
            }
            covered = sum(
                any(interval_iou(prediction, truth) > IOU_THRESHOLD for prediction in fold_predictions.get(participant, ()))
                for participant, intervals in fold_truth_intervals.items()
                for truth in intervals
            )
            fold_total = len(fold_events)
            fold_prediction_count = sum(len(values) for values in fold_predictions.values())
            fold_false = 0
            for participant in fold.valid_participants:
                metrics = evaluate_events(
                    fold_predictions.get(participant, ()),
                    fold_truth_intervals.get(participant, []),
                    iou_threshold=IOU_THRESHOLD,
                )
                fold_false += metrics.fp
            total_covered += covered
            total_events += fold_total
            total_predictions += fold_prediction_count
            total_false += fold_false
            per_fold[fold.fold_id] = {
                "covered": covered,
                "total": fold_total,
                "recall": covered / fold_total if fold_total else None,
                "predicted_event_count": fold_prediction_count,
                "false_event_count": fold_false,
                "formal_g1_gate_reference_only": bool(fold_total and covered / fold_total >= 0.90),
            }
        per_event = []
        for event in sorted(events, key=lambda item: (item["participant"], item["event_index"])):
            participant_predictions = predictions.get(event["event_id"].split(":", 1)[0], ())
            maximum_iou = best_iou(participant_predictions, event)
            per_event.append(
                {
                    **event,
                    "historical_taxonomy_annotation": historical_taxonomy.get(event["normalized_event_id"]),
                    "replay_best_iou": maximum_iou,
                    "replay_covered": bool(maximum_iou > IOU_THRESHOLD),
                    "participant_replay_prediction_count": len(participant_predictions),
                }
            )
        return {
            "event_count": total_events,
            "covered": total_covered,
            "recall": total_covered / total_events if total_events else None,
            "predicted_event_count": total_predictions,
            "false_event_count": total_false,
            "false_event_rate": total_false / total_predictions if total_predictions else 0.0,
            "per_fold": per_fold,
            "per_event": per_event,
        }

    return {
        "status": "COMPLETED_NEW_DIAGNOSTIC_REFERENCE",
        "target_historical_event_result_available": False,
        "target_historical_event_result": "decision-function-probe report recorded event replay NOT_RUN; old 207/234 is not treated as this target",
        "fixed_234": cohort_report(all_events),
        "exact_complete_232": cohort_report(exact_events),
    }


def main() -> None:
    spec, target_report, data = load_frozen_inputs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    models_dir = OUTPUT_DIR / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    expected_model_paths = [models_dir / f"outer-{index}.joblib" for index in range(5)]
    existing_model_paths = [path for path in expected_model_paths if path.is_file()]
    unexpected_model_files = [
        path for path in models_dir.iterdir() if path not in expected_model_paths
    ]
    if unexpected_model_files or existing_model_paths and len(existing_model_paths) != len(expected_model_paths):
        raise RuntimeError("diagnostic model directory is partially populated; no retry or overwrite permitted")
    reuse_existing_models = len(existing_model_paths) == len(expected_model_paths)

    participants = tuple(sorted(str(value) for value in np.unique(data["participants"])))
    folds = build_outer_folds(participants, n_folds=5, seed=SEED)
    expected_folds = spec["participant_disjoint_outer_protocol"]["folds"]
    actual_folds = {fold.fold_id: list(fold.valid_participants) for fold in folds}
    if actual_folds != expected_folds:
        raise RuntimeError("outer participant fold mapping drift")
    fold_id_by_participant = {
        participant: fold.fold_id
        for fold in folds
        for participant in fold.valid_participants
    }

    thresholds = {
        fold_id: float(value)
        for fold_id, value in spec["threshold_reconstruction"]["numeric_threshold_by_fold"].items()
    }
    selected_quantiles = {
        fold_id: float(value)
        for fold_id, value in spec["threshold_reconstruction"]["selected_quantile_by_fold"].items()
    }
    reconstructed_scores = np.full(data["labels"].size, np.nan, dtype=np.float64)
    reconstructed_fold = np.full(data["labels"].size, "", dtype=object)
    fold_manifest: list[dict[str, Any]] = []
    loadability_rows: list[dict[str, Any]] = []

    for fold in folds:
        train_indices = participant_indices(data["participants"], fold.train_participants)
        valid_indices = participant_indices(data["participants"], fold.valid_participants)
        model_path = models_dir / f"{fold.fold_id}.joblib"
        if reuse_existing_models:
            model = CandidateModel(joblib.load(model_path))
        else:
            model = fit_candidate_model(
                data["features"][train_indices],
                data["labels"][train_indices],
                random_state=SEED,
                max_iter=100,
            )
        train_scores = model.predict_scores(data["features"][train_indices])
        derived_threshold = float(np.quantile(train_scores, selected_quantiles[fold.fold_id]))
        valid_scores = model.predict_scores(data["features"][valid_indices])
        reconstructed_scores[valid_indices] = valid_scores
        reconstructed_fold[valid_indices] = fold.fold_id

        if not reuse_existing_models:
            joblib.dump(model.estimator, model_path, compress=3)
        loaded_estimator = joblib.load(model_path)
        loaded_scores = np.asarray(loaded_estimator.predict_proba(data["features"][valid_indices])[:, 1], dtype=np.float64)
        loadability_delta = np.abs(loaded_scores - valid_scores)
        loadability_row = {
            "fold_id": fold.fold_id,
            "path": str(model_path.relative_to(ROOT)),
            "sha256": sha256(model_path),
            "loadable": True,
            "loaded_vs_in_memory_max_abs_score_delta": float(loadability_delta.max(initial=0.0)),
            "loaded_vs_in_memory_rows_exceeding_tolerance": int(
                np.sum(~np.isclose(loaded_scores, valid_scores, atol=ATOL, rtol=RTOL))
            ),
        }
        loadability_rows.append(loadability_row)
        fold_manifest.append(
            {
                "fold_id": fold.fold_id,
                "train_participants": list(fold.train_participants),
                "valid_participants": list(fold.valid_participants),
                "train_row_count": int(train_indices.size),
                "train_supervised_row_count": int(np.sum(data["labels"][train_indices] >= 0)),
                "valid_row_count": int(valid_indices.size),
                "training_input_sha256": training_input_hash(
                    data["features"], data["labels"], data["row_keys"], train_indices
                ),
                "model": loadability_row,
                "selected_quantile": selected_quantiles[fold.fold_id],
                "saved_threshold": thresholds[fold.fold_id],
                "derived_threshold_check": {
                    "derived_from_outer_train_scores": derived_threshold,
                    "difference_derived_minus_saved": derived_threshold - thresholds[fold.fold_id],
                    "within_declared_tolerance": bool(
                        np.isclose(derived_threshold, thresholds[fold.fold_id], atol=ATOL, rtol=RTOL)
                    ),
                },
                "participant_disjoint_verified": not set(fold.train_participants).intersection(fold.valid_participants),
            }
        )

    if not np.isfinite(reconstructed_scores).all():
        raise RuntimeError("reconstruction did not produce a score for every feature-table row")

    target_map = {str(key): float(value) for key, value in zip(data["row_keys"], data["target_scores"])}
    reconstructed_map = {str(key): float(value) for key, value in zip(data["row_keys"], reconstructed_scores)}
    target_ids = set(target_map)
    reconstructed_ids = set(reconstructed_map)
    common_ids = sorted(target_ids.intersection(reconstructed_ids))
    if target_ids != reconstructed_ids:
        raise RuntimeError("target/reconstruction stable-ID sets differ")
    target_values = np.asarray([target_map[key] for key in common_ids], dtype=np.float64)
    reconstructed_values = np.asarray([reconstructed_map[key] for key in common_ids], dtype=np.float64)
    absolute_delta = np.abs(reconstructed_values - target_values)
    close = np.isclose(reconstructed_values, target_values, atol=ATOL, rtol=RTOL)

    def comparison(indices: np.ndarray) -> dict[str, Any]:
        target_local = data["target_scores"][indices]
        reconstructed_local = reconstructed_scores[indices]
        difference = np.abs(reconstructed_local - target_local)
        selected_target = target_local >= np.asarray([thresholds[str(fold)] for fold in reconstructed_fold[indices]], dtype=np.float64)
        selected_reconstructed = reconstructed_local >= np.asarray([thresholds[str(fold)] for fold in reconstructed_fold[indices]], dtype=np.float64)
        return {
            "row_count": int(indices.size),
            "target_finite_count": int(np.isfinite(target_local).sum()),
            "reconstructed_finite_count": int(np.isfinite(reconstructed_local).sum()),
            "max_abs_score_difference": float(difference.max(initial=0.0)),
            "median_abs_score_difference": float(np.median(difference)) if difference.size else None,
            "p90_abs_score_difference": float(np.percentile(difference, 90)) if difference.size else None,
            "rows_exceeding_tolerance": int(np.sum(~np.isclose(reconstructed_local, target_local, atol=ATOL, rtol=RTOL))),
            "selected_target_count": int(selected_target.sum()),
            "selected_reconstructed_count": int(selected_reconstructed.sum()),
            "selected_state_changes": int(np.sum(selected_target != selected_reconstructed)),
        }

    per_fold_comparison = {
        fold.fold_id: comparison(
            np.asarray([index for index, fold_id in enumerate(reconstructed_fold) if fold_id == fold.fold_id], dtype=np.int64)
        )
        for fold in folds
    }
    score_comparison = {
        "target": "decision-function-probe A baseline_scores",
        "stable_id_field": "row_keys",
        "target_id_count": len(target_ids),
        "reconstructed_id_count": len(reconstructed_ids),
        "missing_target_ids": sorted(reconstructed_ids - target_ids),
        "extra_target_ids": sorted(target_ids - reconstructed_ids),
        "common_id_count": len(common_ids),
        "global": {
            "row_count": len(common_ids),
            "max_abs_score_difference": float(absolute_delta.max(initial=0.0)),
            "median_abs_score_difference": float(np.median(absolute_delta)),
            "p90_abs_score_difference": float(np.percentile(absolute_delta, 90)),
            "rows_exceeding_tolerance": int(np.sum(~close)),
            "score_match": bool(np.all(close)),
        },
        "per_fold": per_fold_comparison,
        "tolerance": {"absolute": ATOL, "relative": RTOL},
        "decision_reproduction": {
            "selected_state_changes_global": int(
                sum(row["selected_state_changes"] for row in per_fold_comparison.values())
            ),
            "selected_state_match": bool(
                all(row["selected_state_changes"] == 0 for row in per_fold_comparison.values())
            ),
        },
    }

    np.savez_compressed(
        OUTPUT_DIR / "scores.npz",
        row_keys=data["row_keys"],
        target_baseline_scores=data["target_scores"],
        reconstructed_baseline_scores=reconstructed_scores,
        reconstructed_fold=reconstructed_fold,
    )
    (OUTPUT_DIR / "fold-manifest.json").write_text(
        json.dumps({"folds": fold_manifest, "loadability": loadability_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "window-id-manifest.json").write_text(
        json.dumps(
            {
                "row_id_field": "row_keys",
                "row_count": int(data["row_keys"].size),
                "unique_count": int(np.unique(data["row_keys"]).size),
                "row_keys_sha256": stable_array_hash(data["row_keys"]),
                "target_score_array_key": "baseline_scores",
                "target_score_array_shape": list(data["target_scores"].shape),
                "binding_source": "formal_g1_decision_function_probe.py global_scores[A] assignment into the frozen feature-table order",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    event_replay = event_replay_report(data, reconstructed_scores, folds, thresholds)
    (OUTPUT_DIR / "event-replay.json").write_text(
        json.dumps(event_replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "schema_version": "formal_g1_a_baseline_reconstruction_report_v1",
        "status": "MATCHED_A_BASELINE_RECONSTRUCTED" if score_comparison["global"]["score_match"] else "RECONSTRUCTION_MISMATCH",
        "spec_path": str(SPEC_PATH.relative_to(ROOT)),
        "spec_sha256": sha256(SPEC_PATH),
        "target_lineage": "decision-function-probe A",
        "model_loadability": {
            "status": "MATCHED" if all(row["loadable"] and row["loaded_vs_in_memory_rows_exceeding_tolerance"] == 0 for row in loadability_rows) else "MISMATCH",
            "outer_fit_count": len(folds),
            "additional_fit_count_during_finalization": 0 if reuse_existing_models else len(folds),
            "reused_models_after_post_fit_reporting_failure": reuse_existing_models,
            "inner_fit_count": 0,
            "folds": loadability_rows,
        },
        "score_reproduction": score_comparison,
        "threshold_reconstruction": {
            "status": "MATCHED" if all(row["derived_threshold_check"]["within_declared_tolerance"] for row in fold_manifest) else "BLOCKED_OR_MISMATCH",
            "used_saved_numeric_thresholds": True,
            "reran_inner_selection": False,
            "folds": [
                {
                    "fold_id": row["fold_id"],
                    "selected_quantile": row["selected_quantile"],
                    "saved_threshold": row["saved_threshold"],
                    "derived_threshold_check": row["derived_threshold_check"],
                }
                for row in fold_manifest
            ],
        },
        "event_replay_reproduction": {
            "status": "SCORE_MATCHED_EVENT_REFERENCE_NEW",
            "event_replay_artifact": "event-replay.json",
            "historical_event_target_available": False,
            "old_207_of_234_used_as_target": False,
            "fixed_234_and_exact_232_reported_separately": True,
        },
        "preserved_historical_status": {
            "DECISION_FUNCTION_EFFECT": "UNSUPPORTED",
            "FORMAL_G1_BASELINE": "FAIL",
            "CANDIDATE_MODEL_DESIGN_REVIEW": "NOT_JUSTIFIED",
        },
        "execution_scope": {
            "N_reconstructed": False,
            "three_second_feature_generation": False,
            "three_second_inference": False,
            "production_files_overwritten": False,
            "production_stride": "UNCHANGED",
            "architecture": "FROZEN",
            "full_training": "BLOCKED",
        },
        "artifacts": {
            "fold_manifest": "fold-manifest.json",
            "window_id_manifest": "window-id-manifest.json",
            "scores": "scores.npz",
            "event_replay": "event-replay.json",
        },
        "runtime": {
            "python": sys.version,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "stop": "Stop after A loadability, score comparison, threshold check, and new diagnostic event replay; do not start 3 s inference.",
    }
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "model_loadability": report["model_loadability"]["status"],
        "score_reproduction": report["score_reproduction"]["global"]["score_match"],
        "threshold_reconstruction": report["threshold_reconstruction"]["status"],
        "event_replay": report["event_replay_reproduction"]["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
