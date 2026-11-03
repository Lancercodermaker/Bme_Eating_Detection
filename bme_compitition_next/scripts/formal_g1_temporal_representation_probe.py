"""Execute the frozen Formal G1 bounded temporal representation probe."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

from eating_event.candidates import fit_candidate_model
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files
from eating_event.data.raw import RawIMU, regularize_imu
from eating_event.data.timebase import AggregatedSeries
from eating_event.diagnostic_temporal import (
    extract_temporal_probe_matrix,
    make_diagnostic_estimator,
)
from eating_event.evaluation import build_outer_folds
try:
    from scripts.run_candidate_baseline import _cache_metadata
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import _cache_metadata


SPEC_PATH = Path("configs/formal-g1-temporal-representation-probe-v1.json")
HASH_PATH = Path("configs/formal-g1-temporal-representation-probe-v1.sha256")
ELIGIBILITY_HASH = "6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d"
COMBINATIONS = ("A-L", "A-N", "B-L", "B-N")
TASKS = ("task_1_missing_vs_hard", "task_2_all_supervised", "task_3_participant")


@dataclass(frozen=True)
class ProbeDataset:
    a: np.ndarray
    b: np.ndarray
    labels: np.ndarray
    participants: np.ndarray
    starts: np.ndarray
    ends: np.ndarray
    row_keys: np.ndarray
    source_files: int


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _verify_spec() -> str:
    spec_bytes = SPEC_PATH.read_bytes()
    expected = HASH_PATH.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = hashlib.sha256(spec_bytes).hexdigest()
    if expected != actual:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: probe spec hash mismatch")
    payload = json.loads(spec_bytes.decode("utf-8"))
    if payload.get("probe_spec_status") != "FROZEN":
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: probe spec is not frozen")
    return actual


def balanced_sample_weights(labels: np.ndarray) -> np.ndarray:
    """Return the preregistered binary balanced weights for N."""

    values = np.asarray(labels, dtype=np.int8)
    if values.ndim != 1 or np.unique(values).tolist() != [0, 1]:
        raise ValueError("balanced sample weights require both binary classes")
    weights = np.asarray(compute_sample_weight(class_weight="balanced", y=values), dtype=np.float64)
    if not np.isfinite(weights).all():
        raise ValueError("balanced sample weights must be finite")
    return weights


def missing_event_window_mask(
    participants: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    missing_events: Sequence[tuple[str, int, int]],
) -> np.ndarray:
    """Mark rows whose window overlaps a frozen MissingEvent interval."""

    participant_values = np.asarray(participants, dtype=object)
    start_values = np.asarray(starts, dtype=np.int64)
    end_values = np.asarray(ends, dtype=np.int64)
    if not (participant_values.ndim == start_values.ndim == end_values.ndim == 1):
        raise ValueError("row identity arrays must be one-dimensional")
    if not (participant_values.size == start_values.size == end_values.size):
        raise ValueError("row identity arrays must align")
    result = np.zeros(start_values.size, dtype=bool)
    for participant, event_start, event_end in missing_events:
        result |= (
            (participant_values == participant)
            & (start_values < int(event_end))
            & (end_values > int(event_start))
        )
    return result


def _parse_event_id(event_id: str) -> tuple[str, int, int]:
    participant, interval = event_id.split(":", 1)
    start_text, end_text = interval.split("-", 1)
    return participant, int(start_text), int(end_text)


def _read_missing_events(report_path: Path) -> list[dict[str, object]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = [row for row in report["event_audit"]["rows"] if row["taxonomy"] != "COVERED"]
    if len(rows) != 27:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: expected exactly 27 MissingEvents")
    parsed: list[dict[str, object]] = []
    for row in rows:
        participant, start, end = _parse_event_id(str(row["event_id"]))
        parsed.append({**row, "participant": participant, "start_ms": start, "end_ms": end})
    taxonomy_counts: dict[str, int] = {}
    for row in parsed:
        taxonomy = str(row["taxonomy"])
        taxonomy_counts[taxonomy] = taxonomy_counts.get(taxonomy, 0) + 1
    if taxonomy_counts != {"AGGREGATION_FIRST": 23, "SCORE_THRESHOLD_FIRST": 4}:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: MissingEvent taxonomy mismatch")
    return parsed


def _aggregate_fast(timestamps: np.ndarray, values: np.ndarray) -> AggregatedSeries:
    timestamp_values = np.asarray(timestamps, dtype=np.float64)
    signal_values = np.asarray(values, dtype=np.float64)
    valid_time = np.isfinite(timestamp_values) & (timestamp_values > 0)
    dropped = int((~valid_time).sum())
    if not valid_time.any():
        return AggregatedSeries(
            timestamps_ms=np.empty(0, dtype=np.int64),
            values=np.empty((0, signal_values.shape[1]), dtype=np.float64),
            duplicate_count=0,
            dropped_missing_timestamps=dropped,
        )
    rounded = np.rint(timestamp_values[valid_time]).astype(np.int64)
    selected = signal_values[valid_time]
    order = np.argsort(rounded, kind="stable")
    ordered_timestamps = rounded[order]
    ordered_values = selected[order]
    unique, inverse = np.unique(ordered_timestamps, return_inverse=True)
    sums = np.zeros((unique.size, ordered_values.shape[1]), dtype=np.float64)
    counts = np.zeros((unique.size, ordered_values.shape[1]), dtype=np.int64)
    for column in range(ordered_values.shape[1]):
        finite = np.isfinite(ordered_values[:, column])
        sums[:, column] = np.bincount(
            inverse,
            weights=np.where(finite, ordered_values[:, column], 0.0),
            minlength=unique.size,
        )
        counts[:, column] = np.bincount(
            inverse,
            weights=finite.astype(np.int64),
            minlength=unique.size,
        ).astype(np.int64, copy=False)
    output = np.full_like(sums, np.nan, dtype=np.float64)
    finite = counts > 0
    output[finite] = sums[finite] / counts[finite]
    return AggregatedSeries(
        timestamps_ms=unique,
        values=output,
        duplicate_count=int(rounded.size - unique.size),
        dropped_missing_timestamps=dropped,
    )


def _read_fast_imu(path: str | Path, *, bad_source_rows: set[int] | None = None) -> RawIMU:
    """Read one approved raw file through pandas without changing production parsing."""

    import pandas as pd

    file_path = Path(path).expanduser().resolve()
    required = [
        "ACC_TIME",
        "ACC_X",
        "ACC_Y",
        "ACC_Z",
        "GYRO_TIME",
        "GYRO_X",
        "GYRO_Y",
        "GYRO_Z",
    ]
    skip_rows = set(bad_source_rows or ())
    read_error: BaseException | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            chunks = pd.read_csv(
                file_path,
                sep="\t",
                usecols=required,
                dtype={column: "float64" for column in required},
                chunksize=200_000,
                encoding=encoding,
                on_bad_lines="skip",
                skiprows=lambda line_number: line_number + 1 in skip_rows,
            )
            frames = list(chunks)
            break
        except (UnicodeDecodeError, LookupError, ValueError) as exc:
            read_error = exc
            continue
    else:
        raise RuntimeError(f"fast diagnostic raw reader failed for {file_path}: {read_error}") from read_error
    if not frames:
        raise RuntimeError(f"fast diagnostic raw reader returned no rows for {file_path}")
    frame = pd.concat(frames, ignore_index=True)
    return RawIMU(
        acc=_aggregate_fast(
            frame["ACC_TIME"].to_numpy(dtype=np.float64, copy=False),
            frame[["ACC_X", "ACC_Y", "ACC_Z"]].to_numpy(dtype=np.float64, copy=False),
        ),
        gyro=_aggregate_fast(
            frame["GYRO_TIME"].to_numpy(dtype=np.float64, copy=False),
            frame[["GYRO_X", "GYRO_Y", "GYRO_Z"]].to_numpy(dtype=np.float64, copy=False),
        ),
    )


def _load_or_build_dataset(
    *,
    config_path: Path,
    cache_dir: Path,
    output_dir: Path,
    expected_spec_hash: str,
) -> ProbeDataset:
    dataset_path = output_dir / "feature-table.npz"
    if dataset_path.is_file():
        payload = np.load(dataset_path, allow_pickle=True)
        metadata = json.loads(str(payload["metadata"].item()))
        if metadata.get("spec_sha256") == expected_spec_hash:
            return ProbeDataset(
                a=payload["a"],
                b=payload["b"],
                labels=payload["labels"],
                participants=payload["participants"].astype(object),
                starts=payload["starts"],
                ends=payload["ends"],
                row_keys=payload["row_keys"].astype(object),
                source_files=int(metadata["source_files"]),
            )

    config = load_config(config_path)
    records = discover_raw_files(config.raw_data_root)
    a_rows: list[np.ndarray] = []
    b_rows: list[np.ndarray] = []
    label_rows: list[np.ndarray] = []
    participant_rows: list[np.ndarray] = []
    start_rows: list[np.ndarray] = []
    end_rows: list[np.ndarray] = []
    key_rows: list[np.ndarray] = []
    processed_files = 0
    expected_points = int(round(config.window_seconds * config.imu_grid_hz))
    manifest_path = Path("artifacts/g1-processed-only-manifest-audit.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad_rows_by_path = {
        str(Path(row["path"]).expanduser().resolve()): {
            int(detail["source_row_number"])
            for detail in row.get("malformed_row_details", [])
            if "source_row_number" in detail
        }
        for row in manifest["files"]
        if row.get("status") == "processed"
    }

    for record_index, record in enumerate(records, start=1):
        metadata = _cache_metadata(record, config, eligibility_artifact_sha256=ELIGIBILITY_HASH)
        cache_path = cache_dir / f"{metadata['cache_key']}.npz"
        if not cache_path.is_file():
            continue
        payload = np.load(cache_path, allow_pickle=True)
        cache_metadata = json.loads(str(payload["metadata"].item()))
        if cache_metadata != metadata:
            raise RuntimeError(f"cache metadata mismatch for {record.path}")
        features = payload["features"].astype(np.float32, copy=False)
        labels = payload["labels"].astype(np.int8, copy=False)
        starts = payload["starts"].astype(np.int64, copy=False)
        ends = payload["ends"].astype(np.int64, copy=False)
        if features.ndim != 2 or features.shape[1] != 111 or features.shape[0] != labels.size:
            raise RuntimeError(f"approved cache shape mismatch for {record.path}")

        raw = _read_fast_imu(record.path, bad_source_rows=bad_rows_by_path.get(str(record.path.resolve()), set()))
        series = regularize_imu(raw, grid_hz=config.imu_grid_hz, max_gap_seconds=config.max_gap_seconds)
        window_values = np.empty((starts.size, expected_points, 6), dtype=np.float64)
        window_masks = np.empty((starts.size, expected_points), dtype=bool)
        for row_index, (start_ms, end_ms) in enumerate(zip(starts, ends)):
            start_index = int(np.searchsorted(series.timestamps_ms, int(start_ms), side="left"))
            end_index = int(np.searchsorted(series.timestamps_ms, int(end_ms), side="left"))
            if end_index - start_index != expected_points:
                raise RuntimeError(
                    f"PREREGISTRATION_IMPLEMENTATION_BLOCKER: window has {end_index - start_index} "
                    f"grid points, expected {expected_points}: {record.path} {start_ms}"
                )
            window_values[row_index] = series.values[start_index:end_index]
            window_masks[row_index] = series.valid_mask[start_index:end_index]
        temporal_matrix = extract_temporal_probe_matrix(
            window_values,
            window_masks,
            grid_hz=config.imu_grid_hz,
        ).values
        b_matrix = np.concatenate((features, temporal_matrix), axis=1)
        if b_matrix.shape[1] != 183 or not np.isfinite(b_matrix).all():
            raise RuntimeError(f"temporal feature contract failed for {record.path}")
        a_rows.append(features)
        b_rows.append(b_matrix)
        label_rows.append(labels)
        participant_rows.append(np.full(labels.size, record.participant_id, dtype=object))
        start_rows.append(starts)
        end_rows.append(ends)
        key_rows.append(
            np.asarray(
                [f"{record.path}|{int(start)}|{int(end)}|{index}" for index, (start, end) in enumerate(zip(starts, ends))],
                dtype=object,
            )
        )
        processed_files += 1
        if record_index == 1 or record_index % 50 == 0:
            print(f"feature_files={processed_files} discovered_index={record_index}/{len(records)}", flush=True)

    if not a_rows:
        raise RuntimeError("no approved cache rows were materialized")
    dataset = ProbeDataset(
        a=np.vstack(a_rows).astype(np.float32, copy=False),
        b=np.vstack(b_rows).astype(np.float32, copy=False),
        labels=np.concatenate(label_rows),
        participants=np.concatenate(participant_rows),
        starts=np.concatenate(start_rows),
        ends=np.concatenate(end_rows),
        row_keys=np.concatenate(key_rows),
        source_files=processed_files,
    )
    if dataset.a.shape != (dataset.labels.size, 111) or dataset.b.shape != (dataset.labels.size, 183):
        raise RuntimeError("materialized dataset shape contract failed")
    if not np.isfinite(dataset.a).all() or not np.isfinite(dataset.b).all():
        raise RuntimeError("materialized dataset contains non-finite features")
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "spec_sha256": expected_spec_hash,
        "source_files": dataset.source_files,
        "rows": int(dataset.labels.size),
        "a_width": int(dataset.a.shape[1]),
        "b_width": int(dataset.b.shape[1]),
    }
    np.savez_compressed(
        dataset_path,
        a=dataset.a,
        b=dataset.b,
        labels=dataset.labels,
        participants=dataset.participants,
        starts=dataset.starts,
        ends=dataset.ends,
        row_keys=dataset.row_keys,
        metadata=np.asarray(json.dumps(metadata, sort_keys=True), dtype=object),
    )
    return dataset


def _production_oof_scores(dataset: ProbeDataset, participants: Sequence[str]) -> np.ndarray:
    scores = np.full(dataset.labels.size, np.nan, dtype=np.float64)
    folds = build_outer_folds(participants, n_folds=5, seed=20260910)
    for fold in folds:
        train_mask = np.isin(dataset.participants, fold.train_participants)
        valid_mask = np.isin(dataset.participants, fold.valid_participants)
        train_rows = train_mask & (dataset.labels >= 0)
        model = fit_candidate_model(
            dataset.a[train_rows],
            dataset.labels[train_rows],
            random_state=20260910,
            positive_weight=3.0,
            max_iter=100,
        )
        scores[valid_mask] = model.predict_scores(dataset.a[valid_mask])
    if not np.isfinite(scores).all():
        raise RuntimeError("production OOF score construction left unscored rows")
    return scores


def _score_summary(scores: np.ndarray) -> dict[str, object]:
    values = np.asarray(scores, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0, "min": None, "median": None, "p90": None, "max": None}
    return {
        "count": int(values.size),
        "min": float(np.min(values)),
        "median": float(np.median(values)),
        "p90": float(np.quantile(values, 0.9)),
        "max": float(np.max(values)),
    }


def _metrics(labels: np.ndarray, scores: np.ndarray) -> dict[str, object]:
    y = np.asarray(labels, dtype=np.int8)
    s = np.asarray(scores, dtype=np.float64)
    keep = np.isfinite(s)
    y = y[keep]
    s = s[keep]
    if y.size == 0 or np.unique(y).size < 2:
        return {"auroc": None, "auprc": None, "reason": "missing both binary classes"}
    return {
        "auroc": float(roc_auc_score(y, s)),
        "auprc": float(average_precision_score(y, s)),
    }


def _fit_and_score(
    kind: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    valid_x: np.ndarray,
) -> np.ndarray:
    estimator = make_diagnostic_estimator(kind)
    if kind == "N":
        estimator.fit(train_x, train_y, sample_weight=balanced_sample_weights(train_y))
    else:
        estimator.fit(train_x, train_y)
    return np.asarray(estimator.predict_proba(valid_x)[:, 1], dtype=np.float64)


def _participant_rows(
    labels: np.ndarray,
    scores: np.ndarray,
    participants: np.ndarray,
    hard_negative: np.ndarray,
    valid_participants: Iterable[str],
) -> dict[str, object]:
    output: dict[str, object] = {}
    for participant in valid_participants:
        participant_mask = participants == participant
        positive = participant_mask & (labels == 1) & np.isfinite(scores)
        negative = participant_mask & (labels == 0) & np.isfinite(scores)
        hard = negative & hard_negative
        if positive.sum() == 0 or negative.sum() == 0:
            metrics = {"auroc": None, "auprc": None, "reason": "missing positive or negative rows"}
        else:
            metrics = _metrics(labels[participant_mask], scores[participant_mask])
        output[str(participant)] = {
            "positive_count": int(positive.sum()),
            "negative_count": int(negative.sum()),
            "hard_negative_count": int(hard.sum()),
            **metrics,
            "positive_score": _score_summary(scores[positive]),
            "negative_score": _score_summary(scores[negative]),
            "hard_negative_score": _score_summary(scores[hard]),
        }
    return output


def _evaluate_task(
    task_name: str,
    dataset: ProbeDataset,
    feature_matrix: np.ndarray,
    hard_negative: np.ndarray,
    task_mask: np.ndarray,
    folds: Sequence[object],
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    result: dict[str, object] = {}
    scores_by_combination: dict[str, np.ndarray] = {}
    for combination in COMBINATIONS:
        classifier = combination[-1]
        scores = np.full(dataset.labels.size, np.nan, dtype=np.float64)
        fold_rows: list[dict[str, object]] = []
        matrix = dataset.a if combination.startswith("A") else dataset.b
        for fold in folds:
            train_participant_mask = np.isin(dataset.participants, fold.train_participants)
            valid_participant_mask = np.isin(dataset.participants, fold.valid_participants)
            train_mask = task_mask & train_participant_mask
            valid_mask = task_mask & valid_participant_mask
            train_y = dataset.labels[train_mask]
            if np.unique(train_y).size < 2:
                raise RuntimeError(f"{task_name}/{combination}/{fold.fold_id}: training lacks both classes")
            if np.any(train_participant_mask & valid_participant_mask):
                raise RuntimeError(f"participant leakage in {fold.fold_id}")
            fold_scores = _fit_and_score(classifier, matrix[train_mask], train_y, matrix[valid_mask])
            scores[valid_mask] = fold_scores
            fold_y = dataset.labels[valid_mask]
            fold_hard = hard_negative[valid_mask] & (fold_y == 0)
            fold_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "train_participant_count": len(fold.train_participants),
                    "valid_participant_count": len(fold.valid_participants),
                    "train_row_count": int(train_y.size),
                    "valid_row_count": int(fold_y.size),
                    "metrics": _metrics(fold_y, fold_scores),
                    "positive_score": _score_summary(fold_scores[fold_y == 1]),
                    "negative_score": _score_summary(fold_scores[fold_y == 0]),
                    "hard_negative_score": _score_summary(fold_scores[fold_hard]),
                    "participant_metrics": _participant_rows(
                        dataset.labels,
                        scores,
                        dataset.participants,
                        hard_negative,
                        fold.valid_participants,
                    ),
                }
            )
        if not np.isfinite(scores[task_mask]).all():
            raise RuntimeError(f"{task_name}/{combination}: held-out scores are incomplete")
        task_scores = scores[task_mask]
        task_labels = dataset.labels[task_mask]
        hard_scores = scores[task_mask & hard_negative]
        all_negative_scores = scores[task_mask & (dataset.labels == 0)]
        result[combination] = {
            "task": task_name,
            "combination": combination,
            "pooled_metrics": _metrics(task_labels, task_scores),
            "positive_score": _score_summary(task_scores[task_labels == 1]),
            "negative_score": _score_summary(task_scores[task_labels == 0]),
            "hard_negative_score": _score_summary(hard_scores),
            "all_negative_score": _score_summary(all_negative_scores),
            "folds": fold_rows,
            "participant_metrics": _participant_rows(
                dataset.labels,
                scores,
                dataset.participants,
                hard_negative,
                sorted(set(dataset.participants[task_mask])),
            ),
        }
        scores_by_combination[combination] = scores
    return result, scores_by_combination


def _delta_value(left: object, right: object, field: str) -> float | None:
    left_value = left.get(field) if isinstance(left, Mapping) else None
    right_value = right.get(field) if isinstance(right, Mapping) else None
    if left_value is None or right_value is None:
        return None
    return float(left_value) - float(right_value)


def _compare_results(task_results: Mapping[str, object]) -> dict[str, object]:
    contrasts = {
        "B-L_vs_A-L": ("B-L", "A-L", "representation_effect"),
        "B-N_vs_A-N": ("B-N", "A-N", "representation_effect"),
        "A-N_vs_A-L": ("A-N", "A-L", "decision_function_effect"),
        "B-N_vs_B-L": ("B-N", "B-L", "decision_function_effect"),
    }
    comparisons: dict[str, object] = {}
    for task_name, task_result in task_results.items():
        task_comparisons: dict[str, object] = {}
        for contrast, (left_name, right_name, effect_type) in contrasts.items():
            left = task_result[left_name]
            right = task_result[right_name]
            fold_delta_auroc = [
                _delta_value(left_fold["metrics"], right_fold["metrics"], "auroc")
                for left_fold, right_fold in zip(left["folds"], right["folds"])
            ]
            fold_delta_auprc = [
                _delta_value(left_fold["metrics"], right_fold["metrics"], "auprc")
                for left_fold, right_fold in zip(left["folds"], right["folds"])
            ]
            participant_names = sorted(set(left["participant_metrics"]) & set(right["participant_metrics"]))
            participant_delta_auroc = {
                participant: _delta_value(
                    left["participant_metrics"][participant],
                    right["participant_metrics"][participant],
                    "auroc",
                )
                for participant in participant_names
            }
            participant_delta_auprc = {
                participant: _delta_value(
                    left["participant_metrics"][participant],
                    right["participant_metrics"][participant],
                    "auprc",
                )
                for participant in participant_names
            }
            task_comparisons[contrast] = {
                "effect_type": effect_type,
                "fold_delta_auroc": fold_delta_auroc,
                "fold_delta_auprc": fold_delta_auprc,
                "participant_delta_auroc": participant_delta_auroc,
                "participant_delta_auprc": participant_delta_auprc,
                "auroc_summary": _stability_summary(fold_delta_auroc, participant_delta_auroc),
                "auprc_summary": _stability_summary(fold_delta_auprc, participant_delta_auprc),
            }
        comparisons[task_name] = task_comparisons
    return comparisons


def _stability_summary(fold_deltas: Sequence[float | None], participant_deltas: Mapping[str, float | None]) -> dict[str, object]:
    finite_folds = np.asarray([value for value in fold_deltas if value is not None], dtype=np.float64)
    finite_participants = np.asarray([value for value in participant_deltas.values() if value is not None], dtype=np.float64)
    improved = int((finite_participants > 0).sum())
    degraded = int((finite_participants < 0).sum())
    stable = bool(
        finite_folds.size == 5
        and int((finite_folds > 0).sum()) >= 4
        and float(np.median(finite_folds)) > 0
        and finite_participants.size > 0
        and improved >= int(np.ceil(0.60 * finite_participants.size))
        and improved > degraded
        and float(np.min(finite_folds)) >= -0.02
    )
    return {
        "stable": stable,
        "fold_count": int(finite_folds.size),
        "positive_fold_count": int((finite_folds > 0).sum()),
        "median_fold_delta": float(np.median(finite_folds)) if finite_folds.size else None,
        "worst_fold_delta": float(np.min(finite_folds)) if finite_folds.size else None,
        "participant_count": int(finite_participants.size),
        "improved_participant_count": improved,
        "degraded_participant_count": degraded,
        "median_participant_delta": float(np.median(finite_participants)) if finite_participants.size else None,
    }


def _missing_event_audit(
    report_path: Path,
    dataset: ProbeDataset,
    task2_scores: Mapping[str, np.ndarray],
    hard_negative: np.ndarray,
) -> dict[str, object]:
    events = _read_missing_events(report_path)
    event_tuples = [(str(row["participant"]), int(row["start_ms"]), int(row["end_ms"])) for row in events]
    missing_mask = missing_event_window_mask(dataset.participants, dataset.starts, dataset.ends, event_tuples)
    groups: dict[str, list[dict[str, object]]] = {
        "all_missing_events": events,
        "short_events": [row for row in events if float(row["gt_duration_s"]) < 180],
        "positive_windows_lt_10": [row for row in events if int(row["positive_windows"]) < 10],
        "score_threshold_first": [row for row in events if row["taxonomy"] == "SCORE_THRESHOLD_FIRST"],
        "aggregation_first": [row for row in events if row["taxonomy"] == "AGGREGATION_FIRST"],
    }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    low_recall = {str(row["participant"]) for row in report["participant_audit"]["low_recall_participants"]}
    groups["low_recall_participants"] = [row for row in events if str(row["participant"]) in low_recall]
    output: dict[str, object] = {}
    for group_name, group_events in groups.items():
        tuples = [(str(row["participant"]), int(row["start_ms"]), int(row["end_ms"])) for row in group_events]
        group_mask = missing_event_window_mask(dataset.participants, dataset.starts, dataset.ends, tuples)
        group_mask &= dataset.labels == 1
        group_result: dict[str, object] = {
            "event_count": len(group_events),
            "positive_window_count": int(group_mask.sum()),
            "combinations": {},
        }
        for combination in COMBINATIONS:
            scores = task2_scores[combination]
            positives = group_mask & np.isfinite(scores)
            negatives = hard_negative & np.isfinite(scores)
            y = np.concatenate((np.ones(int(positives.sum()), dtype=np.int8), np.zeros(int(negatives.sum()), dtype=np.int8)))
            s = np.concatenate((scores[positives], scores[negatives]))
            group_result["combinations"][combination] = {
                "positive_score": _score_summary(scores[positives]),
                "hard_negative_score": _score_summary(scores[negatives]),
                "separability": _metrics(y, s),
            }
        output[group_name] = group_result
    output["all_missing_event_window_mask_count"] = int(missing_mask.sum())
    return output


def _classify(
    comparisons: Mapping[str, object],
    task1_results: Mapping[str, object],
) -> dict[str, object]:
    task2 = comparisons["task_2_all_supervised"]
    rep_linear = task2["B-L_vs_A-L"]["auroc_summary"]["stable"]
    rep_nonlinear = task2["B-N_vs_A-N"]["auroc_summary"]["stable"]
    decision_linear = task2["A-N_vs_A-L"]["auroc_summary"]["stable"]
    decision_nonlinear = task2["B-N_vs_B-L"]["auroc_summary"]["stable"]
    hard_guard = {}
    for contrast in ("B-L_vs_A-L", "B-N_vs_A-N"):
        left, right, _ = contrast.split("_vs_")[0], contrast.split("_vs_")[1], ""
        left_auc = task1_results[left]["pooled_metrics"].get("auroc")
        right_auc = task1_results[right]["pooled_metrics"].get("auroc")
        hard_guard[contrast] = {
            "auroc_delta": None if left_auc is None or right_auc is None else float(left_auc - right_auc),
            "passes": left_auc is not None and right_auc is not None and float(left_auc - right_auc) >= -0.03,
        }
    representation = "STRENGTHENED" if rep_linear and rep_nonlinear and all(row["passes"] for row in hard_guard.values()) else "NOT_STRENGTHENED"
    if decision_linear and not rep_linear and not rep_nonlinear:
        decision = "STRENGTHENED"
    elif decision_linear or decision_nonlinear:
        decision = "PLAUSIBLE"
    else:
        decision = "NOT_STRENGTHENED"
    if rep_linear and decision_linear and decision_nonlinear:
        probe = "POSITIVE"
        dominant = "MIXED"
    elif rep_linear and rep_nonlinear:
        probe = "POSITIVE"
        dominant = "FEATURE_REPRESENTATION"
    elif decision_linear and not rep_linear and not rep_nonlinear:
        probe = "POSITIVE"
        dominant = "MODEL_DECISION_FUNCTION"
    elif not rep_linear and not rep_nonlinear and not decision_linear and not decision_nonlinear:
        probe = "NEGATIVE"
        dominant = "BOUNDED_TEMPORAL_REPRESENTATION_HYPOTHESIS_UNSUPPORTED"
    else:
        probe = "INCONCLUSIVE"
        dominant = "INCONCLUSIVE"
    architecture_review = "JUSTIFIED" if (rep_linear or rep_nonlinear) and all(row["passes"] for row in hard_guard.values() if row["passes"] is not None) else "NOT_JUSTIFIED"
    return {
        "representation_effect": representation,
        "decision_function_effect": decision,
        "dominant_interpretation": dominant,
        "probe_result": probe,
        "bounded_temporal_representation_hypothesis": "SUPPORTED" if rep_linear or rep_nonlinear else "UNSUPPORTED",
        "architecture_design_review": architecture_review,
        "architecture": "FROZEN",
        "full_training": "BLOCKED",
        "hard_negative_guards": hard_guard,
    }


def run_probe(
    *,
    config_path: Path,
    cache_dir: Path,
    report_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    spec_hash = _verify_spec()
    dataset = _load_or_build_dataset(
        config_path=config_path,
        cache_dir=cache_dir,
        output_dir=output_dir,
        expected_spec_hash=spec_hash,
    )
    participants = sorted(set(map(str, dataset.participants)))
    folds = build_outer_folds(participants, n_folds=5, seed=20260910)
    production_scores = _production_oof_scores(dataset, participants)
    hard_negative = (dataset.labels == 0) & (production_scores >= 0.5)
    if int(hard_negative.sum()) == 0:
        raise RuntimeError("hard-negative control has no rows")
    missing_events = _read_missing_events(report_path)
    missing_tuples = [(str(row["participant"]), int(row["start_ms"]), int(row["end_ms"])) for row in missing_events]
    missing_positive = (dataset.labels == 1) & missing_event_window_mask(
        dataset.participants, dataset.starts, dataset.ends, missing_tuples
    )
    task_masks = {
        "task_1_missing_vs_hard": missing_positive | hard_negative,
        "task_2_all_supervised": (dataset.labels == 0) | (dataset.labels == 1),
    }
    task_results: dict[str, object] = {}
    score_tables: dict[str, dict[str, np.ndarray]] = {}
    for task_name, task_mask in task_masks.items():
        print(f"evaluation_start={task_name} rows={int(task_mask.sum())}", flush=True)
        task_result, scores = _evaluate_task(task_name, dataset, dataset.a, hard_negative, task_mask, folds)
        task_results[task_name] = task_result
        score_tables[task_name] = scores
        if task_name == "task_2_all_supervised":
            # Re-run the same evaluator with B selected by the fixed combination names.
            pass
        # _evaluate_task selects A/B from the combination and ignores this argument's columns.

    comparisons = _compare_results(task_results)
    task3: dict[str, object] = {}
    task2_scores = score_tables["task_2_all_supervised"]
    for combination, scores in task2_scores.items():
        task3[combination] = {
            "combination": combination,
            "participant_metrics": _participant_rows(
                dataset.labels,
                scores,
                dataset.participants,
                hard_negative,
                participants,
            ),
        }
    task_results["task_3_participant"] = task3
    missing_audit = _missing_event_audit(report_path, dataset, task2_scores, hard_negative)
    classification = _classify(comparisons, task_results["task_1_missing_vs_hard"])
    dataset_path = output_dir / "feature-table.npz"
    dataset_sha = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    result = {
        "schema_version": "formal_g1_temporal_representation_probe_report_v1",
        "probe_spec": {"path": str(SPEC_PATH), "sha256": spec_hash, "status": "FROZEN"},
        "source_artifacts": {
            "review_report": str(report_path),
            "approved_cache": str(cache_dir),
            "eligibility_hash": ELIGIBILITY_HASH,
        },
        "dataset": {
            "feature_table_path": str(dataset_path),
            "feature_table_sha256": dataset_sha,
            "source_files": dataset.source_files,
            "rows": int(dataset.labels.size),
            "supervised_rows": int((dataset.labels >= 0).sum()),
            "a_width": int(dataset.a.shape[1]),
            "b_width": int(dataset.b.shape[1]),
            "label_counts": {str(label): int((dataset.labels == label).sum()) for label in (-1, 0, 1)},
        },
        "folds": {
            "seed": 20260910,
            "folds": {fold.fold_id: {"train": list(fold.train_participants), "valid": list(fold.valid_participants)} for fold in folds},
        },
        "hard_negative": {
            "production_oof_score_cutoff": 0.5,
            "count": int(hard_negative.sum()),
            "score_summary": _score_summary(production_scores[hard_negative]),
            "production_oof_score_summary": _score_summary(production_scores[dataset.labels == 0]),
        },
        "missing_positive": {"count": int(missing_positive.sum()), "event_count": len(missing_events)},
        "tasks": task_results,
        "comparisons": comparisons,
        "missing_event_audit": missing_audit,
        "classification": classification,
        "verification": {
            "spec_hash_verified": True,
            "participant_disjoint_verified": True,
            "production_artifacts_modified": False,
            "production_threshold_created": False,
            "production_aggregation_modified": False,
        },
        "stop": "STOP after preregistered 2 representations x 2 classifiers x 3 tasks",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_dir / "scores.npz",
        production_oof_scores=production_scores,
        hard_negative=hard_negative,
        **{
            f"{task_name}_{combination}": scores
            for task_name, combinations in score_tables.items()
            for combination, scores in combinations.items()
        },
    )
    (output_dir / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    final = run_probe(
        config_path=args.config,
        cache_dir=args.cache_dir,
        report_path=args.report,
        output_dir=args.output_dir,
    )
    print(json.dumps(final["classification"], ensure_ascii=False, indent=2), flush=True)
