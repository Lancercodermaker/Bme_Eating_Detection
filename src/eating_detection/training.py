import copy
import json
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from .cache import FeatureCache, LazyFeatureCache
from .dataset import (
    CachedWindowDataset,
    ParticipantBatchSampler,
    WindowDataset,
    WindowRecord,
    build_records_from_sensor_file,
    participant_from_sensor_path,
)
from .decoding import decode_windows, tune_decoder
from .metrics import EventMetrics, event_metrics
from .models import IMUCNN
from .preprocess import Standardizer, apply_standardizer, fit_standardizer


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.cuda.manual_seed_all(seed)


def compute_pos_weight(labels) -> float:
    positives = sum(float(label) > 0 for label in labels)
    negatives = sum(float(label) == 0 for label in labels)
    if positives == 0:
        raise ValueError("training split has no positive windows")
    return negatives / positives


def train_one_batch(model, optimizer, x, y, pos_weight: float) -> float:
    if x.ndim != 3 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("x must be (batch, channels, time) and y must be (batch,)")
    model.train()
    optimizer.zero_grad(set_to_none=True)
    logits = model(x)
    loss = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pos_weight, dtype=logits.dtype, device=logits.device)
    )(logits, y.to(dtype=logits.dtype))
    loss.backward()
    optimizer.step()
    return float(loss.detach().cpu())


def mirror_imu_axes(batch):
    """Mirror the raw x axes while preserving magnitudes and quality masks."""
    if getattr(batch, "ndim", None) != 3 or batch.shape[1] < 6:
        raise ValueError("batch must have shape (batch, channels, time) with six IMU channels")
    mirrored = batch.clone() if isinstance(batch, torch.Tensor) else np.array(batch, copy=True)
    mirrored[:, 0] *= -1
    mirrored[:, 3] *= -1
    return mirrored


def save_checkpoint(
    path: Path,
    model,
    optimizer,
    config,
    split_manifest,
    stats,
    epoch,
    metrics,
    seed: int | None = None,
) -> None:
    payload = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": config,
        "split_manifest": split_manifest,
        "stats": stats,
        "epoch": epoch,
        "metrics": metrics,
        "seed": seed,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_device(device_name: str) -> torch.device:
    if device_name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return device


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _gpu_runtime_stats(device: torch.device) -> dict[str, object]:
    stats: dict[str, object] = {"device": str(device), "gpu_utilization_percent": None}
    if device.type != "cuda":
        return stats
    stats.update(
        {
            "memory_allocated_mb": torch.cuda.memory_allocated(device) / 1_000_000,
            "memory_reserved_mb": torch.cuda.memory_reserved(device) / 1_000_000,
            "max_memory_allocated_mb": torch.cuda.max_memory_allocated(device) / 1_000_000,
        }
    )
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        stats["gpu_utilization_percent"] = float(output.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        stats["gpu_utilization_percent"] = None
    return stats


def _fit_cached_standardizer(
    caches: list[FeatureCache], train_participants: set[str]
) -> Standardizer:
    selected = [cache for cache in caches if cache.participant in train_participants]
    if not selected:
        raise ValueError("no training cache for the requested participants")
    signal_channels = int(selected[0].features.shape[0] - 2)
    if signal_channels <= 0 or signal_channels % 2:
        raise ValueError("cached feature channels must contain an even signal channel count")
    sums = np.zeros(signal_channels, dtype=np.float64)
    squares = np.zeros(signal_channels, dtype=np.float64)
    counts = np.zeros(signal_channels, dtype=np.int64)
    for cache in selected:
        if isinstance(cache, LazyFeatureCache):
            cache.ensure_features()
        try:
            if cache.feature_channels - 2 != signal_channels:
                raise ValueError("all cached files must have the same signal channel count")
            for channel in range(signal_channels):
                valid = cache.quality_mask[0 if channel < signal_channels // 2 else 1]
                values = cache.features[channel, valid]
                sums[channel] += values.sum(dtype=np.float64)
                squares[channel] += np.square(values, dtype=np.float64).sum(dtype=np.float64)
                counts[channel] += int(valid.sum())
        finally:
            if isinstance(cache, LazyFeatureCache):
                cache.release_features()
    if np.any(counts == 0):
        missing = np.flatnonzero(counts == 0).tolist()
        raise ValueError(f"cached signal channels have no valid training samples: {missing}")
    mean = sums / counts
    std = np.sqrt(np.maximum(squares / counts - mean * mean, 1e-12))
    return Standardizer(mean.astype(np.float32), std.astype(np.float32))


def _standardize_batch(batch: torch.Tensor, stats: Standardizer) -> torch.Tensor:
    if batch.ndim != 3 or batch.shape[1] < 3:
        raise ValueError("cached batch must have shape (batch, channels, time)")
    signal_channels = batch.shape[1] - 2
    mean = torch.as_tensor(stats.mean, dtype=batch.dtype, device=batch.device).view(1, -1, 1)
    std = torch.as_tensor(stats.std, dtype=batch.dtype, device=batch.device).view(1, -1, 1)
    if mean.shape[1] != signal_channels:
        raise ValueError("normalization statistics do not match cached signal channels")
    return torch.cat(((batch[:, :signal_channels] - mean) / std, batch[:, signal_channels:]), dim=1)


def _cached_loader(dataset: CachedWindowDataset, batch_size: int, device: torch.device):
    sampler = ParticipantBatchSampler(dataset, batch_size=batch_size)
    return DataLoader(
        dataset,
        batch_sampler=sampler,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )


def _predict_cached(
    model,
    dataset: CachedWindowDataset,
    stats: Standardizer,
    device: torch.device,
    batch_size: int,
) -> dict[str, list[tuple[int, int, float]]]:
    model.eval()
    predictions: dict[str, list[tuple[int, int, float]]] = {}
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )
    offset = 0
    with torch.inference_mode():
        for batch, _, _ in loader:
            batch = _standardize_batch(batch, stats).to(device, non_blocking=device.type == "cuda")
            probabilities = torch.sigmoid(model(batch)).detach().cpu().tolist()
            for probability in probabilities:
                participant, start_ms, end_ms = dataset.window_metadata(offset)
                predictions.setdefault(participant, []).append(
                    (start_ms, end_ms, float(probability))
                )
                offset += 1
    for participant in predictions:
        predictions[participant].sort(key=lambda item: item[0])
    return predictions


def fit_m0_cached(
    caches: list[FeatureCache],
    train_participants: set[str],
    val_participants: set[str],
    truth: dict[str, list[tuple[int, int]]],
    output_dir: Path,
    config_payload: dict[str, object],
    split_manifest: dict[str, object],
    epochs: int,
    batch_size: int,
    seed: int,
    iou_threshold: float,
    device_name: str = "auto",
    cache_issues: list[dict[str, str]] | None = None,
    min_quality_fraction: float = 0.0,
) -> dict[str, object]:
    """Train M0 from per-file caches without reading source sensor files."""
    if not caches:
        raise ValueError("no feature caches were built")
    if epochs <= 0 or batch_size <= 0:
        raise ValueError("epochs and batch_size must be positive")
    set_seed(seed)
    train_dataset = CachedWindowDataset(
        caches, train_participants, min_quality_fraction=min_quality_fraction
    )
    val_dataset = CachedWindowDataset(
        caches, val_participants, min_quality_fraction=min_quality_fraction
    )
    if not len(train_dataset):
        raise ValueError("no training windows for the requested participants")
    if not len(val_dataset):
        raise ValueError("no validation windows for the requested participants")
    stats = _fit_cached_standardizer(caches, train_participants)
    train_labels = [
        float(cache.window_labels[index])
        for cache in caches
        if cache.participant in train_participants
        for index, usable in enumerate(cache.window_loss_mask)
        if usable
    ]
    pos_weight = compute_pos_weight(train_labels)
    device = _resolve_device(device_name)
    input_channels = int(caches[0].feature_channels)
    model = IMUCNN(in_channels=input_channels).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loader = _cached_loader(train_dataset, batch_size, device)
    best_result = None
    best_state = None
    epoch_losses = []
    epoch_times = []
    epoch_gpu_stats = []
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()
    cache_stats = {
        "cache_files": len(caches),
        "cache_hit_files": sum(cache.cache_hit for cache in caches),
        "cache_miss_files": sum(not cache.cache_hit for cache in caches),
        "cache_build_sec": sum(cache.timings.get("build_sec", 0.0) for cache in caches),
        "cache_load_sec": sum(cache.timings.get("cache_load_sec", 0.0) for cache in caches),
        "cache_issues": cache_issues or [],
    }

    for epoch in range(1, epochs + 1):
        _synchronize(device)
        epoch_started = time.perf_counter()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        losses = []
        for batch, targets, participants in loader:
            if len(set(participants)) != 1:
                raise AssertionError("participant batch sampler mixed participant groups")
            batch = _standardize_batch(batch, stats).to(device, non_blocking=device.type == "cuda")
            targets = targets.to(device, non_blocking=device.type == "cuda")
            losses.append(train_one_batch(model, optimizer, batch, targets, pos_weight))
        _synchronize(device)
        predictions = _predict_cached(model, val_dataset, stats, device, batch_size)
        validation_participants = sorted(val_participants)
        decoder = tune_decoder(
            [[(start, end) for start, end, _ in predictions.get(participant, [])] for participant in validation_participants],
            [[probability for _, _, probability in predictions.get(participant, [])] for participant in validation_participants],
            [truth.get(participant, []) for participant in validation_participants],
            iou_threshold=iou_threshold,
        )
        aggregate, participant_metrics, events = evaluate_predictions(
            predictions, truth, decoder, iou_threshold, participants=val_participants
        )
        f1_values = [float(item["f1"]) for item in participant_metrics.values()]
        epoch_time = time.perf_counter() - epoch_started
        gpu_stats = _gpu_runtime_stats(device)
        result = {
            **aggregate.as_dict(),
            "participant_metrics": participant_metrics,
            "decoder": decoder,
            "events": events,
            "device": str(device),
        "batch_size": batch_size,
        "min_quality_fraction": min_quality_fraction,
            "pos_weight": pos_weight,
            "participant_f1_mean": float(np.mean(f1_values)) if f1_values else 0.0,
            "participant_f1_std": float(np.std(f1_values)) if f1_values else 0.0,
            "participant_f1_worst": min(f1_values) if f1_values else 0.0,
            "window_count": len(train_dataset) + len(val_dataset),
            "train_window_count": len(train_dataset),
            "val_window_count": len(val_dataset),
            "input_channels": input_channels,
            "window_samples": int(caches[0].window_indices[0, 1] - caches[0].window_indices[0, 0]),
            "epoch_time_sec": epoch_time,
            "gpu_stats": gpu_stats,
            "cache": cache_stats,
        }
        epoch_losses.append(float(np.mean(losses)) if losses else None)
        epoch_times.append(epoch_time)
        epoch_gpu_stats.append(gpu_stats)
        if best_result is None or result["f1"] > best_result["f1"]:
            best_result = result
            best_state = {
                "model": copy.deepcopy(model.state_dict()),
                "optimizer": copy.deepcopy(optimizer.state_dict()),
                "epoch": epoch,
            }
            save_checkpoint(
                output_dir / "checkpoint.pt",
                model,
                optimizer,
                config_payload,
                split_manifest,
                {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
                epoch,
                result,
                seed=seed,
            )

    if best_result is None or best_state is None:
        raise RuntimeError("cached training produced no checkpoint")
    best_result["training_time_sec"] = float(time.perf_counter() - started_at)
    best_result["epoch_times_sec"] = epoch_times
    best_result["epoch_gpu_stats"] = epoch_gpu_stats
    model.load_state_dict(best_state["model"])
    optimizer.load_state_dict(best_state["optimizer"])
    final_predictions = _predict_cached(model, val_dataset, stats, device, batch_size)
    rows = []
    for participant in sorted(final_predictions):
        for start, end, probability in final_predictions[participant]:
            rows.append(
                {
                    "participant": participant,
                    "start_ms": start,
                    "end_ms": end,
                    "probability": probability,
                    "split": "val",
                }
            )
    (output_dir / "window_probabilities.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    save_json(output_dir / "metrics.json", best_result)
    save_json(output_dir / "decoder.json", best_result["decoder"])
    save_json(output_dir / "normalization.json", {"mean": stats.mean.tolist(), "std": stats.std.tolist()})
    save_json(output_dir / "events_val.json", best_result["events"])
    save_json(
        output_dir / "training_log.json",
        {"epoch_losses": epoch_losses, "epoch_times_sec": epoch_times, "epoch_gpu_stats": epoch_gpu_stats, "cache": cache_stats},
    )
    save_json(output_dir / "cache_summary.json", cache_stats)
    save_checkpoint(
        output_dir / "checkpoint.pt",
        model,
        optimizer,
        config_payload,
        split_manifest,
        {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
        best_state["epoch"],
        best_result,
        seed=seed,
    )
    train_dataset.release_loaded()
    val_dataset.release_loaded()
    return {"metrics": best_result, "stats": stats, "device": str(device), "cache": cache_stats}


def standardize_window_records(
    records: list[WindowRecord], train_participants: set[str]
) -> tuple[list[WindowRecord], Standardizer]:
    train_records = [record for record in records if record.participant in train_participants]
    if not train_records:
        raise ValueError("no training windows for the requested participants")
    train_values = np.concatenate(
        [record.features[:-2].detach().cpu().numpy().T for record in train_records], axis=0
    )
    train_masks = np.concatenate(
        [record.features[-2:].detach().cpu().numpy().T > 0.5 for record in train_records], axis=0
    )
    stats = fit_standardizer(train_values, train_masks)
    return _apply_standardizer(records, stats), stats


def _apply_standardizer(
    records: list[WindowRecord], stats: Standardizer
) -> list[WindowRecord]:
    standardized = []
    for record in records:
        raw = record.features.detach().cpu().numpy()
        signal_values = apply_standardizer(raw[:-2].T, stats).T
        features = np.vstack([signal_values, raw[-2:]]).astype(np.float32)
        standardized.append(
            WindowRecord(
                participant=record.participant,
                start_ms=record.start_ms,
                end_ms=record.end_ms,
                features=torch.from_numpy(features),
                label=record.label,
                loss_mask=record.loss_mask,
            )
        )
    return standardized


def _predict_records(model, records: list[WindowRecord], device: torch.device):
    model.eval()
    predictions: dict[str, list[tuple[int, int, float]]] = {}
    with torch.no_grad():
        for record in records:
            logits = model(record.features.unsqueeze(0).to(device))
            probability = float(torch.sigmoid(logits).item())
            predictions.setdefault(record.participant, []).append(
                (record.start_ms, record.end_ms, probability)
            )
    for participant in predictions:
        predictions[participant].sort(key=lambda item: item[0])
    return predictions


def _aggregate_metrics(metrics: list[EventMetrics]) -> EventMetrics:
    if not metrics:
        return EventMetrics(0, 0, 0, 0.0, 0.0, 0.0, None, None)
    tp = sum(metric.tp for metric in metrics)
    fp = sum(metric.fp for metric in metrics)
    fn = sum(metric.fn for metric in metrics)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    start_values = [metric.start_mae_ms for metric in metrics if metric.start_mae_ms is not None]
    end_values = [metric.end_mae_ms for metric in metrics if metric.end_mae_ms is not None]
    return EventMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        start_mae_ms=float(np.mean(start_values)) if start_values else None,
        end_mae_ms=float(np.mean(end_values)) if end_values else None,
    )


def evaluate_predictions(
    predictions: dict[str, list[tuple[int, int, float]]],
    truth: dict[str, list[tuple[int, int]]],
    decoder: dict[str, int | float],
    iou_threshold: float,
    participants: set[str] | None = None,
) -> tuple[EventMetrics, dict[str, dict[str, object]], dict[str, list[tuple[int, int]]]]:
    participant_metrics: dict[str, dict[str, object]] = {}
    events: dict[str, list[tuple[int, int]]] = {}
    metrics = []
    scope = participants if participants is not None else set(predictions) | set(truth)
    for participant in sorted(scope):
        rows = predictions.get(participant, [])
        windows = [(start, end) for start, end, _ in rows]
        probabilities = [probability for _, _, probability in rows]
        predicted_events = decode_windows(
            windows,
            probabilities,
            threshold=float(decoder["threshold"]),
            merge_gap_ms=int(decoder["merge_gap_ms"]),
            min_duration_ms=int(decoder["min_duration_ms"]),
        )
        participant_result = event_metrics(
            predicted_events, truth.get(participant, []), iou_threshold
        )
        events[participant] = predicted_events
        participant_metrics[participant] = participant_result.as_dict()
        metrics.append(participant_result)
    return _aggregate_metrics(metrics), participant_metrics, events


def fit_m0(
    records: list[WindowRecord],
    train_participants: set[str],
    val_participants: set[str],
    truth: dict[str, list[tuple[int, int]]],
    output_dir: Path,
    config_payload: dict[str, object],
    split_manifest: dict[str, object],
    epochs: int,
    batch_size: int,
    seed: int,
    iou_threshold: float,
    device_name: str = "auto",
) -> dict[str, object]:
    if epochs <= 0 or batch_size <= 0:
        raise ValueError("epochs and batch_size must be positive")
    set_seed(seed)
    standardized, stats = standardize_window_records(records, train_participants)
    train_records = [
        record
        for record in standardized
        if record.participant in train_participants and record.loss_mask
    ]
    val_records = [
        record
        for record in standardized
        if record.participant in val_participants and record.loss_mask
    ]
    pos_weight = compute_pos_weight([record.label for record in train_records])
    device = torch.device(
        "cuda" if device_name == "auto" and torch.cuda.is_available() else
        "cpu" if device_name == "auto" else device_name
    )
    model = IMUCNN(in_channels=int(records[0].features.shape[0])).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    train_dataset = WindowDataset(train_records)
    sampler = ParticipantBatchSampler(train_dataset, batch_size=batch_size)
    best_result = None
    best_state = None
    epoch_losses = []
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.perf_counter()

    for epoch in range(1, epochs + 1):
        losses = []
        for batch in sampler:
            x = torch.stack([train_records[index].features for index in batch]).to(device)
            y = torch.tensor([train_records[index].label for index in batch], device=device)
            if (
                config_payload.get("preprocess_variant") == "p2_train_axis_augmentation"
                and random.random() < float(config_payload.get("axis_mirror_probability", 0.5))
            ):
                x = mirror_imu_axes(x)
            losses.append(train_one_batch(model, optimizer, x, y, pos_weight))
        predictions = _predict_records(model, val_records, device)
        val_participants_sorted = sorted(val_participants)
        validation_windows = [
            [(start, end) for start, end, _ in predictions.get(participant, [])]
            for participant in val_participants_sorted
        ]
        validation_probabilities = [
            [probability for _, _, probability in predictions.get(participant, [])]
            for participant in val_participants_sorted
        ]
        validation_truth = [truth.get(participant, []) for participant in val_participants_sorted]
        decoder = tune_decoder(
            validation_windows,
            validation_probabilities,
            validation_truth,
            iou_threshold=iou_threshold,
        )
        aggregate, participant_metrics, events = evaluate_predictions(
            predictions,
            truth,
            decoder,
            iou_threshold,
            participants=val_participants,
        )
        result = {
            **aggregate.as_dict(),
            "participant_metrics": participant_metrics,
            "decoder": decoder,
            "events": events,
            "device": str(device),
            "pos_weight": pos_weight,
        }
        f1_values = [float(item["f1"]) for item in participant_metrics.values()]
        result.update(
            {
                "participant_f1_mean": float(np.mean(f1_values)) if f1_values else 0.0,
                "participant_f1_std": float(np.std(f1_values)) if f1_values else 0.0,
                "participant_f1_worst": min(f1_values) if f1_values else 0.0,
                "window_count": len(train_records) + len(val_records),
                "train_window_count": len(train_records),
                "val_window_count": len(val_records),
                "input_channels": int(records[0].features.shape[0]),
                "window_samples": int(records[0].features.shape[1]),
            }
        )
        epoch_losses.append(float(np.mean(losses)) if losses else None)
        if best_result is None or result["f1"] > best_result["f1"]:
            best_result = result
            best_state = {
                "model": copy.deepcopy(model.state_dict()),
                "optimizer": copy.deepcopy(optimizer.state_dict()),
                "epoch": epoch,
            }
            save_checkpoint(
                output_dir / "checkpoint.pt",
                model,
                optimizer,
                config_payload,
                split_manifest,
                {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
                epoch,
                result,
                seed=seed,
            )

    if best_result is None or best_state is None:
        raise RuntimeError("training produced no checkpoint")
    best_result["training_time_sec"] = float(time.perf_counter() - started_at)
    model.load_state_dict(best_state["model"])
    optimizer.load_state_dict(best_state["optimizer"])
    final_predictions = _predict_records(model, val_records, device)
    rows = []
    for participant in sorted(final_predictions):
        for start, end, probability in final_predictions[participant]:
            rows.append(
                {
                    "participant": participant,
                    "start_ms": start,
                    "end_ms": end,
                    "probability": probability,
                    "split": "val",
                }
            )
    (output_dir / "window_probabilities.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    save_json(output_dir / "metrics.json", best_result)
    save_json(output_dir / "decoder.json", best_result["decoder"])
    save_json(output_dir / "normalization.json", {"mean": stats.mean.tolist(), "std": stats.std.tolist()})
    save_json(output_dir / "events_val.json", best_result["events"])
    save_json(output_dir / "training_log.json", {"epoch_losses": epoch_losses})
    save_checkpoint(
        output_dir / "checkpoint.pt",
        model,
        optimizer,
        config_payload,
        split_manifest,
        {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
        best_state["epoch"],
        best_result,
        seed=seed,
    )
    return {"metrics": best_result, "stats": stats, "device": str(device)}


def fit_m0_streaming(
    paths: list[Path],
    intervals: dict[str, list[tuple[int, int]]],
    resample_hz: int,
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
    chunksize: int,
    train_participants: set[str],
    val_participants: set[str],
    truth: dict[str, list[tuple[int, int]]],
    output_dir: Path,
    config_payload: dict[str, object],
    split_manifest: dict[str, object],
    epochs: int,
    batch_size: int,
    seed: int,
    iou_threshold: float,
    device_name: str = "auto",
    max_rows: int | None = None,
    max_gap_ms: int = 2_000,
) -> dict[str, object]:
    """Train M0 with per-file reads and a train-only first-pass standardizer."""
    if epochs <= 0 or batch_size <= 0:
        raise ValueError("epochs and batch_size must be positive")
    set_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: dict[str, str] = {}
    signal_channels = None
    sums = None
    squares = None
    counts = None
    window_samples = None
    train_positive = 0
    train_negative = 0
    train_window_count = 0
    val_window_count = 0

    def load_file(path: Path) -> list[WindowRecord] | None:
        participant = participant_from_sensor_path(path)
        try:
            return build_records_from_sensor_file(
                path,
                intervals=intervals.get(participant, []),
                resample_hz=resample_hz,
                window_sec=window_sec,
                step_sec=step_sec,
                positive_overlap=positive_overlap,
                boundary_mode=boundary_mode,
                max_rows=max_rows,
                chunksize=chunksize,
                preprocess_variant=str(config_payload.get("preprocess_variant", "p0_raw_mask")),
                lowpass_cutoff_hz=float(config_payload.get("lowpass_cutoff_hz", 1.0)),
                median_kernel=int(config_payload.get("median_kernel", 5)),
                max_gap_ms=max_gap_ms,
            )
        except (OSError, ValueError) as exc:
            issues[str(path)] = str(exc)
            return None

    def accumulate(records: list[WindowRecord]) -> None:
        nonlocal signal_channels, sums, squares, counts, window_samples
        for record in records:
            values = record.features[:-2].detach().cpu().numpy().T
            mask = record.features[-2:].detach().cpu().numpy().T > 0.5
            if window_samples is None:
                window_samples = int(record.features.shape[1])
            if signal_channels is None:
                signal_channels = values.shape[1]
                sums = np.zeros(signal_channels, dtype=np.float64)
                squares = np.zeros(signal_channels, dtype=np.float64)
                counts = np.zeros(signal_channels, dtype=np.int64)
            if values.shape[1] != signal_channels:
                raise ValueError("all files must produce the same number of signal channels")
            if signal_channels % 2:
                raise ValueError("signal channels must be divisible into ACC/GYRO mask groups")
            valid = np.column_stack(
                [mask[:, 0]] * (signal_channels // 2)
                + [mask[:, 1]] * (signal_channels // 2)
            )
            sums += np.where(valid, values, 0.0).sum(axis=0)
            squares += np.where(valid, values * values, 0.0).sum(axis=0)
            counts += valid.sum(axis=0)

    for path in paths:
        participant = participant_from_sensor_path(path)
        records = load_file(path)
        if records is None:
            continue
        if participant in train_participants:
            accumulate(records)
            train_records = [record for record in records if record.loss_mask]
            train_window_count += len(train_records)
            train_positive += sum(record.label > 0 for record in train_records)
            train_negative += sum(record.label == 0 for record in train_records)
        elif participant in val_participants:
            val_window_count += sum(record.loss_mask for record in records)

    if signal_channels is None or not train_window_count:
        save_json(output_dir / "input_issues.json", [{"path": key, "reason": value} for key, value in issues.items()])
        raise ValueError("no training windows for the requested participants")
    if train_positive == 0:
        raise ValueError("training split has no positive windows")
    if np.any(counts == 0):
        raise ValueError("a signal channel has no valid training samples")
    mean = sums / counts
    std = np.sqrt(np.maximum(squares / counts - mean * mean, 1e-12))
    stats = Standardizer(mean.astype(np.float32), std.astype(np.float32))
    pos_weight = train_negative / train_positive
    device = torch.device(
        "cuda" if device_name == "auto" and torch.cuda.is_available() else
        "cpu" if device_name == "auto" else device_name
    )
    model = IMUCNN(in_channels=signal_channels + 2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    best_result = None
    best_state = None
    epoch_losses = []
    started_at = time.perf_counter()

    for epoch in range(1, epochs + 1):
        losses = []
        for path in paths:
            participant = participant_from_sensor_path(path)
            if participant not in train_participants:
                continue
            records = load_file(path)
            if records is None:
                continue
            local_records = [
                record
                for record in _apply_standardizer(records, stats)
                if record.loss_mask
            ]
            sampler = ParticipantBatchSampler(WindowDataset(local_records), batch_size=batch_size)
            for batch in sampler:
                x = torch.stack([local_records[index].features for index in batch]).to(device)
                y = torch.tensor([local_records[index].label for index in batch], device=device)
                if (
                    config_payload.get("preprocess_variant") == "p2_train_axis_augmentation"
                    and random.random() < float(config_payload.get("axis_mirror_probability", 0.5))
                ):
                    x = mirror_imu_axes(x)
                losses.append(train_one_batch(model, optimizer, x, y, pos_weight))

        predictions: dict[str, list[tuple[int, int, float]]] = {}
        for path in paths:
            participant = participant_from_sensor_path(path)
            if participant not in val_participants:
                continue
            records = load_file(path)
            if records is None:
                continue
            local_records = [
                record
                for record in _apply_standardizer(records, stats)
                if record.loss_mask
            ]
            for key, values in _predict_records(model, local_records, device).items():
                predictions.setdefault(key, []).extend(values)
        for participant in predictions:
            predictions[participant].sort(key=lambda item: item[0])
        validation_participants = sorted(val_participants)
        decoder = tune_decoder(
            [[(start, end) for start, end, _ in predictions.get(participant, [])] for participant in validation_participants],
            [[probability for _, _, probability in predictions.get(participant, [])] for participant in validation_participants],
            [truth.get(participant, []) for participant in validation_participants],
            iou_threshold=iou_threshold,
        )
        aggregate, participant_metrics, events = evaluate_predictions(
            predictions,
            truth,
            decoder,
            iou_threshold,
            participants=val_participants,
        )
        f1_values = [float(item["f1"]) for item in participant_metrics.values()]
        result = {
            **aggregate.as_dict(),
            "participant_metrics": participant_metrics,
            "decoder": decoder,
            "events": events,
            "device": str(device),
            "pos_weight": pos_weight,
            "participant_f1_mean": float(np.mean(f1_values)) if f1_values else 0.0,
            "participant_f1_std": float(np.std(f1_values)) if f1_values else 0.0,
            "participant_f1_worst": min(f1_values) if f1_values else 0.0,
            "window_count": train_window_count + val_window_count,
            "train_window_count": train_window_count,
            "val_window_count": val_window_count,
            "input_channels": signal_channels + 2,
            "window_samples": window_samples,
        }
        epoch_losses.append(float(np.mean(losses)) if losses else None)
        if best_result is None or result["f1"] > best_result["f1"]:
            best_result = result
            best_state = {
                "model": copy.deepcopy(model.state_dict()),
                "optimizer": copy.deepcopy(optimizer.state_dict()),
                "epoch": epoch,
            }
            save_checkpoint(
                output_dir / "checkpoint.pt",
                model,
                optimizer,
                config_payload,
                split_manifest,
                {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
                epoch,
                result,
                seed=seed,
            )

    if best_result is None or best_state is None:
        raise RuntimeError("streaming training produced no checkpoint")
    best_result["training_time_sec"] = float(time.perf_counter() - started_at)
    model.load_state_dict(best_state["model"])
    optimizer.load_state_dict(best_state["optimizer"])
    final_predictions: dict[str, list[tuple[int, int, float]]] = {}
    for path in paths:
        participant = participant_from_sensor_path(path)
        if participant not in val_participants:
            continue
        records = load_file(path)
        if records is None:
            continue
        local_records = [
            record
            for record in _apply_standardizer(records, stats)
            if record.loss_mask
        ]
        for key, values in _predict_records(model, local_records, device).items():
            final_predictions.setdefault(key, []).extend(values)
    rows = []
    for participant in sorted(final_predictions):
        for start, end, probability in sorted(final_predictions[participant]):
            rows.append(
                {
                    "participant": participant,
                    "start_ms": start,
                    "end_ms": end,
                    "probability": probability,
                    "split": "val",
                }
            )
    (output_dir / "window_probabilities.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    save_json(output_dir / "input_issues.json", [{"path": key, "reason": value} for key, value in issues.items()])
    save_json(output_dir / "metrics.json", best_result)
    save_json(output_dir / "decoder.json", best_result["decoder"])
    save_json(output_dir / "normalization.json", {"mean": stats.mean.tolist(), "std": stats.std.tolist()})
    save_json(output_dir / "events_val.json", best_result["events"])
    save_json(output_dir / "training_log.json", {"epoch_losses": epoch_losses})
    save_checkpoint(
        output_dir / "checkpoint.pt",
        model,
        optimizer,
        config_payload,
        split_manifest,
        {"mean": stats.mean.tolist(), "std": stats.std.tolist()},
        best_state["epoch"],
        best_result,
        seed=seed,
    )
    return {"metrics": best_result, "stats": stats, "device": str(device)}
