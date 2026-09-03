"""Read-only diagnostics for a cached M0 validation run.

The analysis deliberately consumes cache arrays and frozen validation
probabilities.  It never parses the source sensor CSV files and never changes
the model, decoder, split, or checkpoint.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import yaml

from .decoding import decode_windows
from .metrics import event_metrics


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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.run_dir / "error_analysis.json"
    report = analyze_m0_run(args.run_dir, args.cache_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ERROR_ANALYSIS_SAVED {output}")
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
