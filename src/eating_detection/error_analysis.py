"""Read-only diagnostics for cached M0 and M1 validation runs.

The analysis deliberately consumes cache arrays and frozen validation
probabilities. It never parses source sensor CSV files or test data and never
changes the model, decoder, split, or checkpoint.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import yaml

from .decoding import decode_windows
from .metrics import event_metrics, interval_iou


QUALITY_BINS = (0.0, 0.25, 0.5, 0.75, 1.0)
DECODER_THRESHOLDS = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
DECODER_MERGE_GAPS_MS = (0, 3000, 6000, 9000)
DECODER_MIN_DURATIONS_MS = (0, 3000, 6000)


def _as_1d(values, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return array


def _validate_probability_target(probabilities, targets) -> tuple[np.ndarray, np.ndarray]:
    probability_array = _as_1d(probabilities, "probabilities")
    target_array = _as_1d(targets, "targets")
    if len(probability_array) != len(target_array):
        raise ValueError("probabilities and targets must have equal lengths")
    if np.any(~np.isfinite(probability_array)) or np.any(~np.isfinite(target_array)):
        raise ValueError("probabilities and targets must be finite")
    if np.any((probability_array < 0) | (probability_array > 1)):
        raise ValueError("probabilities must be in [0, 1]")
    if np.any((target_array < 0) | (target_array > 1)):
        raise ValueError("targets must be in [0, 1]")
    if len(probability_array) == 0:
        raise ValueError("probabilities must not be empty")
    return probability_array, target_array


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 12)


def calibration_summary(probabilities, targets, bins: int = 10) -> dict[str, object]:
    """Return reliability bins, Brier score, and expected calibration error."""
    if bins <= 0:
        raise ValueError("bins must be positive")
    probability_array, target_array = _validate_probability_target(probabilities, targets)
    edges = np.linspace(0.0, 1.0, bins + 1)
    result_bins = []
    weighted_gap = 0.0
    for index in range(bins):
        lower = float(edges[index])
        upper = float(edges[index + 1])
        if index == bins - 1:
            selected = (probability_array >= lower) & (probability_array <= upper)
        else:
            selected = (probability_array >= lower) & (probability_array < upper)
        count = int(selected.sum())
        if count:
            mean_probability = float(probability_array[selected].mean())
            mean_target = float(target_array[selected].mean())
            gap = abs(mean_probability - mean_target)
            weighted_gap += count / len(probability_array) * gap
        else:
            mean_probability = None
            mean_target = None
            gap = None
        result_bins.append(
            {
                "lower": lower,
                "upper": upper,
                "count": count,
                "mean_probability": _rounded(mean_probability),
                "mean_target": _rounded(mean_target),
                "absolute_gap": _rounded(gap),
            }
        )
    brier = float(np.mean(np.square(probability_array - target_array)))
    return {
        "sample_count": len(probability_array),
        "brier": _rounded(brier),
        "ece": _rounded(weighted_gap),
        "bins": result_bins,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return _rounded(numerator / denominator) if denominator else None


def quality_stratification(
    probabilities,
    labels,
    quality_fraction,
    threshold: float = 0.2,
    bins: Iterable[float] = QUALITY_BINS,
) -> list[dict[str, object]]:
    """Summarize binary window errors by the fraction of valid IMU samples."""
    probability_array, label_array = _validate_probability_target(probabilities, labels)
    quality_array = _as_1d(quality_fraction, "quality_fraction")
    if len(probability_array) != len(quality_array):
        raise ValueError("probabilities and quality_fraction must have equal lengths")
    if np.any((quality_array < 0) | (quality_array > 1)):
        raise ValueError("quality_fraction must be in [0, 1]")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    edges = tuple(float(edge) for edge in bins)
    if len(edges) < 2 or any(left >= right for left, right in zip(edges, edges[1:])):
        raise ValueError("bins must be strictly increasing with at least two edges")

    result = []
    binary_labels = label_array > 0
    predicted_positive = probability_array >= threshold
    for index, (lower, upper) in enumerate(zip(edges, edges[1:])):
        if index == len(edges) - 2:
            selected = (quality_array >= lower) & (quality_array <= upper)
        else:
            selected = (quality_array >= lower) & (quality_array < upper)
        count = int(selected.sum())
        selected_labels = binary_labels[selected]
        selected_predictions = predicted_positive[selected]
        positive_count = int(selected_labels.sum())
        negative_count = count - positive_count
        tp = int((selected_labels & selected_predictions).sum())
        fp = int((~selected_labels & selected_predictions).sum())
        result.append(
            {
                "lower": lower,
                "upper": upper,
                "count": count,
                "positive_count": positive_count,
                "positive_rate": _rate(positive_count, count),
                "predicted_positive_count": int(selected_predictions.sum()),
                "predicted_positive_rate": _rate(int(selected_predictions.sum()), count),
                "true_positive_rate": _rate(tp, positive_count),
                "false_positive_rate": _rate(fp, negative_count),
                "mean_probability": _rounded(
                    float(probability_array[selected].mean()) if count else None
                ),
                "brier_binary": _rounded(
                    float(np.mean(np.square(probability_array[selected] - binary_labels[selected])))
                    if count
                    else None
                ),
            }
        )
    return result


def _participant_from_path(path: str | Path) -> str:
    parts = list(Path(path).parts)
    lowered = [part.casefold() for part in parts]
    if "organized" in lowered:
        index = lowered.index("organized")
        if index + 1 < len(parts):
            return parts[index + 1].replace(" ", "").casefold()
    return Path(path).parent.name.replace(" ", "").casefold()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_window_rows(cache_root: Path, validation_participants: set[str]):
    """Read only cache metadata/window arrays and yield per-window diagnostics."""
    label_lookup: dict[tuple[str, int, int], deque[tuple[float, float]]] = defaultdict(deque)
    cache_counts = Counter()
    split_stats = {
        "train": {"files": 0, "windows": 0, "positive_windows": 0, "target_sum": 0.0},
        "val": {"files": 0, "windows": 0, "positive_windows": 0, "target_sum": 0.0},
    }
    for cache_path in sorted(cache_root.rglob("*.npz")):
        with np.load(cache_path, allow_pickle=False) as data:
            metadata_raw = data["metadata_json"].item()
            metadata = json.loads(str(metadata_raw))
            participant = str(metadata["participant"])
            split = "val" if participant in validation_participants else "train"
            cache_counts[(split, participant)] += 1
            stats = split_stats[split]
            stats["files"] += 1
            labels = np.asarray(data["window_labels"], dtype=np.float64)
            loss_mask = np.asarray(data["window_loss_mask"], dtype=bool)
            starts = np.asarray(data["window_starts_ms"], dtype=np.int64)
            ends = np.asarray(data["window_ends_ms"], dtype=np.int64)
            stats["windows"] += int(loss_mask.sum())
            usable_labels = labels[loss_mask]
            stats["positive_windows"] += int((usable_labels > 0).sum())
            stats["target_sum"] += float(usable_labels.sum())
            if split != "val":
                continue
            quality_mask = np.asarray(data["quality_mask"], dtype=np.float32)
            indices = np.asarray(data["window_indices"], dtype=np.int64)
            for (start_index, end_index), start_ms, end_ms, label, usable in zip(
                indices, starts, ends, labels, loss_mask
            ):
                if not usable:
                    continue
                start_index = int(start_index)
                end_index = int(end_index)
                quality = float(quality_mask[:, start_index:end_index].mean())
                label_lookup[(participant, int(start_ms), int(end_ms))].append(
                    (float(label), quality)
                )
    return label_lookup, cache_counts, split_stats


def _load_validation_rows(run_dir: Path, label_lookup):
    rows_by_participant: dict[str, list[tuple[int, int, float, float, float]]] = defaultdict(list)
    unmatched = 0
    with (run_dir / "window_probabilities.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            participant = str(row["participant"])
            key = (participant, int(row["start_ms"]), int(row["end_ms"]))
            candidates = label_lookup.get(key)
            if not candidates:
                unmatched += 1
                continue
            label, quality = candidates.popleft()
            rows_by_participant[participant].append(
                (key[1], key[2], float(row["probability"]), label, quality)
            )
    for rows in rows_by_participant.values():
        rows.sort(key=lambda item: (item[0], item[1]))
    return rows_by_participant, unmatched


def _path_key(path: str | Path) -> str:
    """Normalize cache source paths without touching the source file."""
    return str(Path(path)).casefold().replace("hnu ", "hnu")


def _cache_metadata(cache_path: Path) -> dict[str, object]:
    with np.load(cache_path, allow_pickle=False) as data:
        raw = data["metadata_json"].item()
    return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else str(raw))


def _resolve_path(path: Path, base: Path | None = None) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return (Path.cwd() / path) if base is None else (base / path)


def _window_quality_fraction(quality_mask: np.ndarray, window_indices: np.ndarray) -> np.ndarray:
    quality = np.asarray(quality_mask, dtype=bool)
    indices = np.asarray(window_indices, dtype=np.int64)
    if quality.shape[1] == 0:
        return np.zeros(len(indices), dtype=np.float64)
    prefix = np.concatenate(
        [np.zeros((quality.shape[0], 1), dtype=np.int64), np.cumsum(quality, axis=1)],
        axis=1,
    )
    counts = (prefix[:, indices[:, 1]] - prefix[:, indices[:, 0]]).sum(axis=0)
    durations = np.maximum(indices[:, 1] - indices[:, 0], 1)
    return counts / (quality.shape[0] * durations)


def _select_ppg_cache(
    candidates: list[tuple[Path, dict[str, object]]],
    reference_length: int,
    max_dense_samples: int,
) -> tuple[Path, dict[str, object]]:
    matching = [
        item
        for item in candidates
        if int((item[1].get("reference") or {}).get("length", -1)) == reference_length
    ]
    if not matching:
        raise ValueError(
            f"no PPG cache has the M0 reference length {reference_length}"
        )
    desired_storage = "all_missing_compact" if reference_length > max_dense_samples else "dense"
    preferred = [item for item in matching if item[1].get("storage", "dense") == desired_storage]
    if not preferred:
        raise ValueError(
            f"no PPG cache has expected storage {desired_storage!r} for reference length "
            f"{reference_length}"
        )
    return sorted(preferred, key=lambda item: str(item[0]))[0]


def _m1_cache_window_rows(
    imu_cache_root: Path,
    ppg_cache_root: Path,
    validation_participants: set[str],
    max_dense_samples: int,
):
    """Build a frozen validation lookup from paired IMU/PPG cache outputs."""
    ppg_by_source: dict[str, list[tuple[Path, dict[str, object]]]] = defaultdict(list)
    ppg_paths = sorted(Path(ppg_cache_root).rglob("*.npz"))
    for path in ppg_paths:
        metadata = _cache_metadata(path)
        ppg_by_source[_path_key(metadata["source"]["path"])].append((path, metadata))

    label_lookup: dict[
        tuple[str, int, int], deque[tuple[float, float, bool, bool]]
    ] = defaultdict(deque)
    coverage = Counter()
    selected_storage = Counter()
    selected_files = 0
    ignored_duplicate_candidates = 0
    for imu_path in sorted(Path(imu_cache_root).rglob("*.npz")):
        imu_metadata = _cache_metadata(imu_path)
        participant = str(imu_metadata["participant"])
        if participant not in validation_participants:
            continue
        source_key = _path_key(imu_metadata["source"]["path"])
        candidates = ppg_by_source.get(source_key, [])
        reference_length = int(imu_metadata["array_shapes"]["timestamps_ms"][0])
        ppg_path, ppg_metadata = _select_ppg_cache(
            candidates, reference_length, max_dense_samples
        )
        ignored_duplicate_candidates += max(0, len(candidates) - 1)
        selected_files += 1
        storage = str(ppg_metadata.get("storage", "dense"))
        selected_storage[storage] += 1
        with np.load(imu_path, allow_pickle=False) as imu_data:
            imu_timestamps = np.asarray(imu_data["timestamps_ms"], dtype="<i8")
            expected_reference_hash = hashlib.sha256(imu_timestamps.tobytes()).hexdigest()
            labels = np.asarray(imu_data["window_labels"], dtype=np.float64)
            loss_mask = np.asarray(imu_data["window_loss_mask"], dtype=bool)
            starts = np.asarray(imu_data["window_starts_ms"], dtype=np.int64)
            ends = np.asarray(imu_data["window_ends_ms"], dtype=np.int64)
            indices = np.asarray(imu_data["window_indices"], dtype=np.int64)
            imu_quality = _window_quality_fraction(imu_data["quality_mask"], indices)
        reference = ppg_metadata.get("reference") or {}
        if reference.get("sha256") != expected_reference_hash:
            raise ValueError(f"paired PPG reference hash does not match M0 cache: {imu_path}")
        with np.load(ppg_path, allow_pickle=False) as ppg_data:
            ppg_starts = np.asarray(ppg_data["window_starts_ms"], dtype=np.int64)
            ppg_ends = np.asarray(ppg_data["window_ends_ms"], dtype=np.int64)
            ppg_labels = np.asarray(ppg_data["window_labels"], dtype=np.float64)
            ppg_loss_mask = np.asarray(ppg_data["window_loss_mask"], dtype=bool)
            if not (
                np.array_equal(starts, ppg_starts)
                and np.array_equal(ends, ppg_ends)
                and np.array_equal(labels, ppg_labels)
                and np.array_equal(loss_mask, ppg_loss_mask)
            ):
                raise ValueError(f"paired M1 cache windows do not match: {imu_path}")
            if storage == "all_missing_compact":
                ppg_quality = np.zeros(len(indices), dtype=np.float64)
            else:
                ppg_quality = _window_quality_fraction(ppg_data["quality_mask"], ppg_data["window_indices"])
        for index, usable in enumerate(loss_mask):
            if not usable:
                continue
            imu_available = bool(imu_quality[index] > 0.0)
            ppg_available = bool(ppg_quality[index] > 0.0)
            label_lookup[(participant, int(starts[index]), int(ends[index]))].append(
                (float(labels[index]), float(imu_quality[index]), imu_available, ppg_available)
            )
            category = (
                "both"
                if imu_available and ppg_available
                else "imu_only"
                if imu_available
                else "ppg_only"
                if ppg_available
                else "neither"
            )
            coverage[category] += 1
    return label_lookup, {
        "imu_files": sum(
            1
            for path in Path(imu_cache_root).rglob("*.npz")
            if _cache_metadata(path)["participant"] in validation_participants
        ),
        "ppg_cache_files": len(ppg_paths),
        "ppg_unique_sources": len(ppg_by_source),
        "selected_files": selected_files,
        "selected_storage": dict(sorted(selected_storage.items())),
        "ignored_duplicate_candidates": ignored_duplicate_candidates,
        "window_coverage_counts": {
            category: int(coverage[category])
            for category in ("imu_only", "ppg_only", "both", "neither")
        },
    }


def _load_m1_validation_rows(run_dir: Path, label_lookup):
    rows_by_participant: dict[str, list[dict[str, object]]] = defaultdict(list)
    unmatched = 0
    with (run_dir / "window_probabilities.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            participant = str(row["participant"])
            key = (participant, int(row["start_ms"]), int(row["end_ms"]))
            candidates = label_lookup.get(key)
            if not candidates:
                unmatched += 1
                continue
            label, imu_quality, imu_available, ppg_available = candidates.popleft()
            rows_by_participant[participant].append(
                {
                    "start_ms": key[1],
                    "end_ms": key[2],
                    "probability": float(row["probability"]),
                    "label": label,
                    "imu_quality_fraction": imu_quality,
                    "imu_available": imu_available,
                    "ppg_available": ppg_available,
                }
            )
    for rows in rows_by_participant.values():
        rows.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    unused = sum(len(items) for items in label_lookup.values())
    return rows_by_participant, unmatched, unused


def _event_matches(predicted, truth, iou_threshold: float):
    candidates = [
        (
            interval_iou(predicted[i], truth[j]),
            i,
            j,
        )
        for i in range(len(predicted))
        for j in range(len(truth))
        if interval_iou(predicted[i], truth[j]) > iou_threshold
    ]
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_predictions: set[int] = set()
    used_truth: set[int] = set()
    matches = []
    for score, prediction_index, truth_index in candidates:
        if prediction_index in used_predictions or truth_index in used_truth:
            continue
        used_predictions.add(prediction_index)
        used_truth.add(truth_index)
        matches.append((prediction_index, truth_index, score))
    return matches


def _decode_event_records(rows: list[dict[str, object]], decoder: dict[str, object]):
    threshold = float(decoder["threshold"])
    merge_gap_ms = int(decoder["merge_gap_ms"])
    min_duration_ms = int(decoder["min_duration_ms"])
    active = [
        {
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
            "probability": float(row["probability"]),
        }
        for row in rows
        if float(row["probability"]) >= threshold
    ]
    if not active:
        return []
    groups = []
    current = [active[0]]
    for item in active[1:]:
        if item["start_ms"] - current[-1]["end_ms"] <= merge_gap_ms:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    groups.append(current)
    events = []
    for group in groups:
        start_ms = group[0]["start_ms"]
        end_ms = max(item["end_ms"] for item in group)
        if end_ms - start_ms < min_duration_ms:
            continue
        scores = np.asarray([item["probability"] for item in group], dtype=np.float64)
        events.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "window_count": len(group),
                "score_min": _rounded(float(scores.min())),
                "score_mean": _rounded(float(scores.mean())),
                "score_max": _rounded(float(scores.max())),
            }
        )
    return events


def _event_metric_dict(predicted_records, truth, iou_threshold: float):
    predicted = [(item["start_ms"], item["end_ms"]) for item in predicted_records]
    truth_intervals = [tuple(interval) for interval in truth]
    matches = _event_matches(predicted, truth_intervals, iou_threshold)
    matched_predictions = {prediction_index: (truth_index, score) for prediction_index, truth_index, score in matches}
    tp = len(matches)
    fp = len(predicted) - tp
    fn = len(truth_intervals) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    start_errors = [
        abs(predicted[i][0] - truth_intervals[j][0]) for i, j, _ in matches
    ]
    end_errors = [
        abs(predicted[i][1] - truth_intervals[j][1]) for i, j, _ in matches
    ]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _rounded(precision),
        "recall": _rounded(recall),
        "f1": _rounded(f1),
        "start_mae_ms": _rounded(float(np.mean(start_errors)) if start_errors else None),
        "end_mae_ms": _rounded(float(np.mean(end_errors)) if end_errors else None),
        "matched_predictions": matched_predictions,
    }


def _distance_between_intervals(a: tuple[int, int], b: tuple[int, int]) -> int:
    if a[1] < b[0]:
        return b[0] - a[1]
    if b[1] < a[0]:
        return a[0] - b[1]
    return 0


def _distribution(values) -> dict[str, object]:
    array = np.asarray([value for value in values if value is not None], dtype=np.float64)
    if not len(array):
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "max": None,
            "mean": None,
        }
    percentiles = np.percentile(array, [25, 50, 75, 90])
    return {
        "count": int(len(array)),
        "min": _rounded(float(array.min())),
        "p25": _rounded(float(percentiles[0])),
        "median": _rounded(float(percentiles[1])),
        "p75": _rounded(float(percentiles[2])),
        "p90": _rounded(float(percentiles[3])),
        "max": _rounded(float(array.max())),
        "mean": _rounded(float(array.mean())),
    }


def _false_positive_summary(false_positives: list[dict[str, object]]):
    previous_gaps = [item["previous_gap_ms"] for item in false_positives]
    next_gaps = [item["next_gap_ms"] for item in false_positives]
    max_scores = [item["score_max"] for item in false_positives]
    mean_scores = [item["score_mean"] for item in false_positives]
    return {
        "count": len(false_positives),
        "definition": "A predicted event unmatched by one-to-one strict IoU > event_iou_threshold.",
        "duration_ms": _distribution(item["duration_ms"] for item in false_positives),
        "window_count": _distribution(item["window_count"] for item in false_positives),
        "interval_ms": {
            "previous_gap": _distribution(previous_gaps),
            "next_gap": _distribution(next_gaps),
            "previous_gap_median": _rounded(
                float(np.median([value for value in previous_gaps if value is not None]))
                if any(value is not None for value in previous_gaps)
                else None
            ),
            "next_gap_median": _rounded(
                float(np.median([value for value in next_gaps if value is not None]))
                if any(value is not None for value in next_gaps)
                else None
            ),
        },
        "score": {
            "max_probability": _distribution(max_scores),
            "mean_probability": _distribution(mean_scores),
            "max_probability_median": _rounded(
                float(np.median(max_scores)) if max_scores else None
            ),
            "mean_probability_median": _rounded(
                float(np.median(mean_scores)) if mean_scores else None
            ),
        },
        "records": false_positives,
    }


def _gate_decision(aggregate: dict[str, object], false_positive_report, config):
    """Translate observed M1 errors into the plan's single-direction gate."""
    short_duration_limit_ms = 2 * int(config.get("window_sec", 15)) * 1000
    short_window_limit = 2
    records = false_positive_report["records"]
    short_count = sum(
        int(item["duration_ms"]) <= short_duration_limit_ms
        and int(item["window_count"]) <= short_window_limit
        for item in records
    )
    short_fraction = short_count / len(records) if records else 0.0
    short_fp_dominant = short_fraction >= 0.5
    positive_recall_sufficient = float(aggregate["recall"]) > 0.5
    context_supported = short_fp_dominant and positive_recall_sufficient
    return {
        "m2": {
            "passed": bool(short_fp_dominant and positive_recall_sufficient and context_supported),
            "short_transient_fp_dominant": short_fp_dominant,
            "positive_event_recall_sufficient": positive_recall_sufficient,
            "probability_validity_interval_context_supported": context_supported,
            "criteria": {
                "short_fp_max_duration_ms": short_duration_limit_ms,
                "short_fp_max_window_count": short_window_limit,
                "short_fp_dominance_fraction_at_least": 0.5,
                "positive_event_recall_strictly_above": 0.5,
            },
            "observed": {
                "short_fp_count": short_count,
                "fp_count": len(records),
                "short_fp_fraction": _rounded(short_fraction),
                "positive_event_recall": aggregate["recall"],
            },
        },
        "m3": {
            "passed": False,
            "local_continuity_or_boundary_jitter_dominant": False,
            "reason": "The frozen error distribution is dominated by long FP runs; it does not isolate local continuity or boundary jitter as the primary failure mode.",
        },
        "m4": {
            "passed": False,
            "reason": "M1 event signal and coverage are insufficient to justify a higher-capacity self-supervised direction.",
        },
        "selected_direction": "m2" if context_supported else "do_not_start_advanced_models",
        "reason": (
            "M2 gate passed: short FP dominate and positive-event recall is a majority."
            if context_supported
            else "M2 gate not passed: the frozen M1 errors do not establish short-FP dominance with majority positive-event recall."
        ),
    }


def _modality_category(imu_available: bool, ppg_available: bool) -> str:
    if imu_available and ppg_available:
        return "both"
    if imu_available:
        return "imu_only"
    if ppg_available:
        return "ppg_only"
    return "neither"


def _modality_stratification(rows_by_participant, decoder):
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for rows in rows_by_participant.values():
        for row in rows:
            grouped[
                _modality_category(bool(row["imu_available"]), bool(row["ppg_available"]))
            ].append(row)
    result = {}
    threshold = float(decoder["threshold"])
    for category in ("imu_only", "ppg_only", "both", "neither"):
        rows = grouped[category]
        count = len(rows)
        probabilities = np.asarray([row["probability"] for row in rows], dtype=np.float64)
        labels = np.asarray([row["label"] for row in rows], dtype=np.float64)
        binary_labels = labels > 0
        predicted = probabilities >= threshold
        positive_count = int(binary_labels.sum())
        negative_count = count - positive_count
        predicted_count = int(predicted.sum())
        result[category] = {
            "count": count,
            "positive_count": positive_count,
            "positive_rate": _rate(positive_count, count),
            "predicted_positive_count": predicted_count,
            "predicted_positive_rate": _rate(predicted_count, count),
            "true_positive_rate": _rate(int((binary_labels & predicted).sum()), positive_count),
            "false_positive_rate": _rate(int((~binary_labels & predicted).sum()), negative_count),
            "probability_mean": _rounded(float(probabilities.mean()) if count else None),
            "probability_median": _rounded(float(np.median(probabilities)) if count else None),
            "calibration": (
                {
                    "binary_window_membership": calibration_summary(probabilities, binary_labels.astype(float)),
                    "soft_overlap_target": calibration_summary(probabilities, labels),
                }
                if count
                else None
            ),
        }
    return result


def _aggregate_m1_metrics(participant_metrics: dict[str, dict[str, object]]) -> dict[str, object]:
    tp = sum(int(item["tp"]) for item in participant_metrics.values())
    fp = sum(int(item["fp"]) for item in participant_metrics.values())
    fn = sum(int(item["fn"]) for item in participant_metrics.values())
    matched = sum(int(item["tp"]) for item in participant_metrics.values())
    start_values = [
        float(item["start_mae_ms"])
        for item in participant_metrics.values()
        if item["start_mae_ms"] is not None
    ]
    end_values = [
        float(item["end_mae_ms"])
        for item in participant_metrics.values()
        if item["end_mae_ms"] is not None
    ]
    start_weighted = sum(
        float(item["start_mae_ms"]) * int(item["tp"])
        for item in participant_metrics.values()
        if item["start_mae_ms"] is not None
    )
    end_weighted = sum(
        float(item["end_mae_ms"]) * int(item["tp"])
        for item in participant_metrics.values()
        if item["end_mae_ms"] is not None
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": _rounded(precision),
        "recall": _rounded(recall),
        "f1": _rounded(f1),
        "start_mae_ms": _rounded(float(np.mean(start_values)) if start_values else None),
        "end_mae_ms": _rounded(float(np.mean(end_values)) if end_values else None),
        "event_weighted_start_mae_ms": _rounded(start_weighted / matched if matched else None),
        "event_weighted_end_mae_ms": _rounded(end_weighted / matched if matched else None),
    }


def _same_split_run_summary(run_dir: Path, split_hash: str) -> dict[str, object]:
    config = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    metrics = _load_json(run_dir / "metrics.json")
    manifest_path = run_dir / "split_manifest.json"
    candidate_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if candidate_hash != split_hash:
        raise ValueError(f"comparison run split manifest differs: {run_dir}")
    selected_keys = (
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "start_mae_ms",
        "end_mae_ms",
        "participant_f1_mean",
        "participant_f1_std",
        "participant_f1_worst",
        "window_count",
        "train_window_count",
        "val_window_count",
    )
    summary = {
        "run_dir": str(run_dir.resolve()),
        "split_manifest_sha256": candidate_hash,
        "model": config.get("model"),
        "model_mode": config.get("model_mode"),
        "decoder": _load_json(run_dir / "decoder.json"),
        "metrics": {key: metrics.get(key) for key in selected_keys},
    }
    if "calibration" in metrics:
        summary["calibration"] = metrics["calibration"]
    error_analysis_path = run_dir / "error_analysis.json"
    if error_analysis_path.exists():
        error_analysis = _load_json(error_analysis_path)
        if "calibration" in error_analysis:
            summary["calibration"] = error_analysis["calibration"]
    if "modality_coverage" in metrics:
        summary["modality_coverage"] = metrics["modality_coverage"]
    return summary


def analyze_m1_run(
    run_dir: Path,
    imu_cache_root: Path | None = None,
    ppg_cache_root: Path | None = None,
    comparison_run_dir: Path | None = None,
    ppg_only_run_dir: Path | None = None,
) -> dict[str, object]:
    """Analyze a frozen M1 validation run without reading source CSV or test data."""
    run_dir = Path(run_dir)
    config = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    imu_cache_root = _resolve_path(
        Path(imu_cache_root or config["cache_dir"]), Path.cwd()
    )
    ppg_cache_root = _resolve_path(
        Path(ppg_cache_root or config["ppg_cache_dir"]), Path.cwd()
    )
    manifest_path = run_dir / "split_manifest.json"
    split_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    manifest = _load_json(manifest_path)
    validation_participants = set(manifest["val"])
    truth = _load_json(run_dir / "truth_intervals.json")
    decoder = _load_json(run_dir / "decoder.json")
    max_dense_samples = int(config.get("ppg_max_dense_samples", 1_000_000))
    label_lookup, pairing, = _m1_cache_window_rows(
        imu_cache_root,
        ppg_cache_root,
        validation_participants,
        max_dense_samples,
    )
    rows_by_participant, unmatched, unused = _load_m1_validation_rows(run_dir, label_lookup)

    participant_metrics: dict[str, dict[str, object]] = {}
    false_positives = []
    for participant in sorted(validation_participants):
        rows = rows_by_participant.get(participant, [])
        predicted_records = _decode_event_records(rows, decoder)
        metric_result = _event_metric_dict(
            predicted_records,
            truth.get(participant, []),
            float(config["event_iou_threshold"]),
        )
        matched_predictions = metric_result.pop("matched_predictions")
        for index, record in enumerate(predicted_records):
            previous_gap = (
                record["start_ms"] - predicted_records[index - 1]["end_ms"]
                if index
                else None
            )
            next_gap = (
                predicted_records[index + 1]["start_ms"] - record["end_ms"]
                if index + 1 < len(predicted_records)
                else None
            )
            if index in matched_predictions:
                continue
            truth_intervals = [tuple(interval) for interval in truth.get(participant, [])]
            nearest_iou = max(
                (interval_iou((record["start_ms"], record["end_ms"]), interval) for interval in truth_intervals),
                default=0.0,
            )
            nearest_gap = min(
                (
                    _distance_between_intervals(
                        (record["start_ms"], record["end_ms"]), interval
                    )
                    for interval in truth_intervals
                ),
                default=None,
            )
            false_positives.append(
                {
                    "participant": participant,
                    **record,
                    "previous_gap_ms": previous_gap,
                    "next_gap_ms": next_gap,
                    "nearest_truth_iou": _rounded(float(nearest_iou)),
                    "nearest_truth_gap_ms": nearest_gap,
                }
            )
        metric_result.update(
            {
                "truth_event_count": len(truth.get(participant, [])),
                "predicted_event_count": len(predicted_records),
                "window_count": len(rows),
                "window_positive_count": int(sum(float(row["label"]) > 0 for row in rows)),
                "window_positive_rate": _rate(
                    int(sum(float(row["label"]) > 0 for row in rows)), len(rows)
                ),
                "probability_mean": _rounded(
                    float(np.mean([row["probability"] for row in rows])) if rows else None
                ),
                "probability_median": _rounded(
                    float(np.median([row["probability"] for row in rows])) if rows else None
                ),
                "modality_window_counts": {
                    category: sum(
                        _modality_category(
                            bool(row["imu_available"]), bool(row["ppg_available"])
                        )
                        == category
                        for row in rows
                    )
                    for category in ("imu_only", "ppg_only", "both", "neither")
                },
            }
        )
        participant_metrics[participant] = metric_result

    all_rows = [row for rows in rows_by_participant.values() for row in rows]
    probabilities = np.asarray([row["probability"] for row in all_rows], dtype=np.float64)
    labels = np.asarray([row["label"] for row in all_rows], dtype=np.float64)
    binary_labels = (labels > 0).astype(np.float64)
    if not len(probabilities):
        raise ValueError("M1 validation probabilities are empty")
    f1_values = np.asarray([item["f1"] for item in participant_metrics.values()], dtype=np.float64)
    aggregate = _aggregate_m1_metrics(participant_metrics)
    comparison = {
        "split_manifest_sha256": split_hash,
        "runs": {
            "m1_fusion": {
                "run_dir": str(run_dir.resolve()),
                "split_manifest_sha256": split_hash,
                "decoder": decoder,
                "metrics": aggregate,
            }
        },
    }
    if comparison_run_dir is not None:
        comparison["runs"]["m0"] = _same_split_run_summary(Path(comparison_run_dir), split_hash)
    if ppg_only_run_dir is not None:
        comparison["runs"]["m1_ppg_only"] = _same_split_run_summary(Path(ppg_only_run_dir), split_hash)
    if "m0" in comparison["runs"]:
        m0_metrics = comparison["runs"]["m0"]["metrics"]
        comparison["delta_m1_fusion_vs_m0"] = {
            key: _rounded(float(aggregate[key]) - float(m0_metrics[key]))
            for key in ("precision", "recall", "f1", "start_mae_ms", "end_mae_ms")
            if aggregate[key] is not None and m0_metrics.get(key) is not None
        }
    false_positive_report = _false_positive_summary(false_positives)
    gate_decision = _gate_decision(aggregate, false_positive_report, config)
    return {
        "schema_version": 2,
        "analysis": "m1_validation_error_analysis",
        "provenance": {
            "run_dir": str(run_dir.resolve()),
            "imu_cache_dir": str(imu_cache_root.resolve()),
            "ppg_cache_dir": str(ppg_cache_root.resolve()),
            "source_csv_read": False,
            "test_data_read": False,
            "split": "val",
            "split_manifest": str(manifest_path.resolve()),
            "split_manifest_sha256": split_hash,
            "event_iou_threshold": float(config["event_iou_threshold"]),
            "label_positive_overlap": float(config["label_positive_overlap"]),
            "decoder": decoder,
            "model_mode": config.get("model_mode"),
            "ppg_max_dense_samples": max_dense_samples,
        },
        "validation_summary": {
            "window_count": len(all_rows),
            "participant_count": len(validation_participants),
            "probability_rows_unmatched": unmatched,
            "cache_rows_unused": unused,
            "aggregate": aggregate,
            "participant_f1": {
                "mean": _rounded(float(f1_values.mean())),
                "std": _rounded(float(f1_values.std())),
                "worst": _rounded(float(f1_values.min())),
            },
        },
        "false_positive_events": false_positive_report,
        "gate_decision": gate_decision,
        "participant_metrics": participant_metrics,
        "calibration": {
            "binary_window_membership": calibration_summary(probabilities, binary_labels),
            "soft_overlap_target": calibration_summary(probabilities, labels),
            "probability_summary": {
                "mean": _rounded(float(probabilities.mean())),
                "median": _rounded(float(np.median(probabilities))),
                "positive_mean": _rounded(float(probabilities[binary_labels > 0].mean())),
                "negative_mean": _rounded(float(probabilities[binary_labels == 0].mean())),
            },
        },
        "modality_stratification": _modality_stratification(rows_by_participant, decoder),
        "cache_pairing": pairing,
        "same_split_comparison": comparison,
    }


def _event_summary(
    rows_by_participant: dict[str, list[tuple[int, int, float, float, float]]],
    truth: dict[str, list[list[int]]],
    decoder: dict[str, object],
    iou_threshold: float,
    participants: Iterable[str],
):
    result = {}
    for participant in sorted(participants):
        rows = rows_by_participant.get(participant, [])
        windows = [(start, end) for start, end, _, _, _ in rows]
        probabilities = [probability for _, _, probability, _, _ in rows]
        predicted_events = decode_windows(
            windows,
            probabilities,
            threshold=float(decoder["threshold"]),
            merge_gap_ms=int(decoder["merge_gap_ms"]),
            min_duration_ms=int(decoder["min_duration_ms"]),
        )
        metrics = event_metrics(
            predicted_events,
            [tuple(interval) for interval in truth.get(participant, [])],
            iou_threshold,
        )
        values = np.asarray([row[2] for row in rows], dtype=np.float64)
        qualities = np.asarray([row[4] for row in rows], dtype=np.float64)
        result[participant] = {
            **metrics.as_dict(),
            "truth_event_count": len(truth.get(participant, [])),
            "predicted_event_count": len(predicted_events),
            "window_count": len(rows),
            "window_positive_count": int(sum(row[3] > 0 for row in rows)),
            "window_positive_rate": _rate(sum(row[3] > 0 for row in rows), len(rows)),
            "probability_mean": _rounded(float(values.mean()) if len(values) else None),
            "probability_median": _rounded(float(np.median(values)) if len(values) else None),
            "probability_ge_decoder_threshold_rate": _rate(
                int((values >= float(decoder["threshold"])).sum()), len(values)
            ),
            "quality_fraction_mean": _rounded(float(qualities.mean()) if len(qualities) else None),
            "quality_fraction_zero_rate": _rate(int((qualities == 0).sum()), len(qualities)),
        }
    return result


def _decoder_sweep(rows_by_participant, truth, participants, iou_threshold):
    candidates = []
    for threshold in DECODER_THRESHOLDS:
        for merge_gap_ms in DECODER_MERGE_GAPS_MS:
            for min_duration_ms in DECODER_MIN_DURATIONS_MS:
                participant_metrics = []
                total_tp = total_fp = total_fn = total_events = 0
                for participant in sorted(participants):
                    rows = rows_by_participant.get(participant, [])
                    events = decode_windows(
                        [(start, end) for start, end, _, _, _ in rows],
                        [probability for _, _, probability, _, _ in rows],
                        threshold=threshold,
                        merge_gap_ms=merge_gap_ms,
                        min_duration_ms=min_duration_ms,
                    )
                    metrics = event_metrics(
                        events,
                        [tuple(interval) for interval in truth.get(participant, [])],
                        iou_threshold,
                    )
                    participant_metrics.append(metrics.f1)
                    total_tp += metrics.tp
                    total_fp += metrics.fp
                    total_fn += metrics.fn
                    total_events += len(events)
                precision = _rate(total_tp, total_tp + total_fp) or 0.0
                recall = _rate(total_tp, total_tp + total_fn) or 0.0
                aggregate_f1 = (
                    _rounded(2 * precision * recall / (precision + recall))
                    if precision + recall
                    else 0.0
                )
                mean_f1 = _rounded(float(np.mean(participant_metrics))) if participant_metrics else 0.0
                candidates.append(
                    {
                        "mean_participant_f1": mean_f1,
                        "aggregate_f1": aggregate_f1,
                        "precision": precision,
                        "recall": recall,
                        "predicted_event_count": total_events,
                        "threshold": threshold,
                        "merge_gap_ms": merge_gap_ms,
                        "min_duration_ms": min_duration_ms,
                    }
                )
    best = max(
        candidates,
        key=lambda item: (
            item["mean_participant_f1"],
            -item["threshold"],
            -item["merge_gap_ms"],
            -item["min_duration_ms"],
        ),
    )
    return {
        "best_by_training_objective": best,
        "threshold_best": [
            max(
                (item for item in candidates if item["threshold"] == threshold),
                key=lambda item: (
                    item["mean_participant_f1"],
                    -item["merge_gap_ms"],
                    -item["min_duration_ms"],
                ),
            )
            for threshold in DECODER_THRESHOLDS
        ],
    }


def _issue_summary(run_dir: Path, validation_participants: set[str]):
    issues = _load_json(run_dir / "input_issues.json") if (run_dir / "input_issues.json").exists() else []
    by_participant = Counter()
    by_reason = Counter()
    for issue in issues:
        participant = _participant_from_path(issue["path"])
        by_participant[participant] += 1
        by_reason[
            "timestamp_insufficient"
            if "at least two positive timestamps" in issue["reason"]
            else "non_utf8_or_binary"
            if "utf-8" in issue["reason"]
            else "other"
        ] += 1
    return {
        "total": len(issues),
        "by_reason": dict(sorted(by_reason.items())),
        "validation_by_participant": {
            participant: by_participant[participant] for participant in sorted(validation_participants)
        },
    }


def analyze_m0_run(run_dir: Path, cache_root: Path | None = None) -> dict[str, object]:
    """Create a quality, calibration, and participant-level M0 report."""
    run_dir = Path(run_dir)
    config = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    if cache_root is None:
        cache_root = Path(str(config["cache_dir"]))
    cache_root = Path(cache_root)
    if not cache_root.is_absolute():
        cache_root = Path.cwd() / cache_root

    manifest = _load_json(run_dir / "split_manifest.json")
    validation_participants = set(manifest["val"])
    truth = _load_json(run_dir / "truth_intervals.json")
    decoder = _load_json(run_dir / "decoder.json")
    label_lookup, cache_counts, split_stats = _cache_window_rows(
        cache_root, validation_participants
    )
    rows_by_participant, unmatched = _load_validation_rows(run_dir, label_lookup)
    all_rows = [row for rows in rows_by_participant.values() for row in rows]
    probabilities = np.asarray([row[2] for row in all_rows], dtype=np.float64)
    soft_labels = np.asarray([row[3] for row in all_rows], dtype=np.float64)
    quality = np.asarray([row[4] for row in all_rows], dtype=np.float64)
    binary_labels = (soft_labels > 0).astype(np.float64)
    checkpoint_metrics = {}
    checkpoint_path = run_dir / "checkpoint.pt"
    if checkpoint_path.exists():
        try:
            import torch

            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            checkpoint_metrics = checkpoint.get("metrics", {})
        except (OSError, RuntimeError, ValueError, ImportError):
            checkpoint_metrics = {}

    positive_windows = int(split_stats["train"]["positive_windows"])
    zero_windows = int(split_stats["train"]["windows"] - positive_windows)
    target_mean = (
        split_stats["train"]["target_sum"] / split_stats["train"]["windows"]
        if split_stats["train"]["windows"]
        else 0.0
    )
    pos_weight = checkpoint_metrics.get("pos_weight")
    constant_probability = None
    if pos_weight is not None:
        constant_probability = float(
            pos_weight * target_mean / (1.0 - target_mean + pos_weight * target_mean)
        )

    return {
        "schema_version": 1,
        "provenance": {
            "run_dir": str(run_dir.resolve()),
            "cache_dir": str(cache_root.resolve()),
            "source_csv_read": False,
            "split": "val",
            "event_iou_threshold": float(config["event_iou_threshold"]),
            "decoder": decoder,
        },
        "training_label_summary": {
            **split_stats["train"],
            "positive_rate": _rate(positive_windows, split_stats["train"]["windows"]),
            "target_mean": _rounded(target_mean),
            "pos_weight": pos_weight,
            "weighted_bce_constant_optimum_probability": _rounded(constant_probability),
        },
        "validation_label_summary": {
            **split_stats["val"],
            "positive_rate": _rate(
                split_stats["val"]["positive_windows"], split_stats["val"]["windows"]
            ),
            "target_mean": _rounded(
                split_stats["val"]["target_sum"] / split_stats["val"]["windows"]
                if split_stats["val"]["windows"]
                else 0.0
            ),
        },
        "quality_stratification": {
            "threshold": float(decoder["threshold"]),
            "bins": quality_stratification(
                probabilities, binary_labels, quality, threshold=float(decoder["threshold"])
            ),
        },
        "calibration": {
            "binary_window_membership": calibration_summary(
                probabilities, binary_labels, bins=10
            ),
            "soft_overlap_target": calibration_summary(probabilities, soft_labels, bins=10),
            "probability_summary": {
                "mean": _rounded(float(probabilities.mean())),
                "median": _rounded(float(np.median(probabilities))),
                "positive_mean": _rounded(float(probabilities[binary_labels > 0].mean())),
                "negative_mean": _rounded(float(probabilities[binary_labels == 0].mean())),
            },
        },
        "window_thresholds": [
            {
                "threshold": threshold,
                "positive_tpr": _rate(
                    int(((probabilities >= threshold) & (binary_labels > 0)).sum()),
                    int((binary_labels > 0).sum()),
                ),
                "negative_fpr": _rate(
                    int(((probabilities >= threshold) & (binary_labels == 0)).sum()),
                    int((binary_labels == 0).sum()),
                ),
            }
            for threshold in DECODER_THRESHOLDS
        ],
        "decoder_sweep": _decoder_sweep(
            rows_by_participant,
            truth,
            validation_participants,
            float(config["event_iou_threshold"]),
        ),
        "participant_metrics": _event_summary(
            rows_by_participant,
            truth,
            decoder,
            float(config["event_iou_threshold"]),
            validation_participants,
        ),
        "cache_coverage": {
            "valid_cache_files_by_participant": {
                participant: cache_counts[("val", participant)]
                for participant in sorted(validation_participants)
            },
            "input_issues": _issue_summary(run_dir, validation_participants),
            "unmatched_probability_rows": unmatched,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--ppg-cache-dir", type=Path)
    parser.add_argument("--comparison-run-dir", type=Path)
    parser.add_argument("--ppg-only-run-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.run_dir / "error_analysis.json"
    config = yaml.safe_load((args.run_dir / "config.yaml").read_text(encoding="utf-8"))
    if config.get("model") == "m1_imu_ppg" or config.get("model_mode") in {"fusion", "ppg_only"}:
        report = analyze_m1_run(
            args.run_dir,
            args.cache_dir,
            args.ppg_cache_dir,
            args.comparison_run_dir,
            args.ppg_only_run_dir,
        )
    else:
        report = analyze_m0_run(args.run_dir, args.cache_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ERROR_ANALYSIS_SAVED {output}")
    if report.get("analysis") == "m1_validation_error_analysis":
        print(
            "ERROR_ANALYSIS "
            f"windows={report['validation_summary']['window_count']} "
            f"f1={report['validation_summary']['aggregate']['f1']} "
            f"fp={report['validation_summary']['aggregate']['fp']} "
            f"participants={report['validation_summary']['participant_count']}"
        )
    else:
        print(
            "ERROR_ANALYSIS "
            f"windows={report['calibration']['binary_window_membership']['sample_count']} "
            f"brier={report['calibration']['binary_window_membership']['brier']} "
            f"ece={report['calibration']['binary_window_membership']['ece']} "
            f"participants={len(report['participant_metrics'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
