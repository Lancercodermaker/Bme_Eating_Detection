"""Compare target-only Transformer training with training-only external pretraining."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from torch import nn

from eating_event.candidates import CandidateTable, eventize_windows, split_participants
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files, events_for_record, load_meal_events
from eating_event.data.raw import RawFileFormatError
from eating_event.external_training import ExternalWindowTable, collect_external_window_tables
from eating_event.metrics import EventInterval, evaluate_events
from eating_event.models.transformer import TransformerConfig, TemporalTransformer
from scripts.run_candidate_baseline import _build_table, _cache_key, _load_table, _merge_intervals
from scripts.run_tcn_candidate import _metric_dict, _standardizer
from scripts.run_transformer_candidate import _chunk_slices, _normalised_values, _score_table


def _positive_weight(labels: np.ndarray) -> float:
    values = np.asarray(labels, dtype=np.int8).reshape(-1)
    labeled = values >= 0
    positives = int((values[labeled] == 1).sum())
    negatives = int((values[labeled] == 0).sum())
    if positives == 0 or negatives == 0:
        raise ValueError("training needs both positive and negative labels")
    return min(10.0, negatives / positives)


def _normalised_features(features: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    return (values - mean) / scale


def _train_tables(
    model: TemporalTransformer,
    tables: Sequence[CandidateTable | ExternalWindowTable],
    *,
    mean: np.ndarray,
    scale: np.ndarray,
    device: torch.device,
    sequence_length: int,
    sequence_stride: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    pos_weight: float,
    seed: int,
    stage: str,
) -> list[float]:
    if epochs <= 0:
        return []
    chunks = [
        (table, start, end)
        for table in tables
        for start, end in _chunk_slices(len(table.labels), sequence_length, sequence_stride)
    ]
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, device=device))
    epoch_losses: list[float] = []
    for epoch in range(1, epochs + 1):
        model.train()
        order = np.random.default_rng(seed + epoch).permutation(len(chunks))
        losses: list[float] = []
        for chunk_index in order:
            table, start, end = chunks[int(chunk_index)]
            values = _normalised_features(table.features[start:end], mean, scale)
            tensor = torch.from_numpy(values[None]).to(device)
            labels = torch.from_numpy(table.labels[start:end].astype(np.float32)[None]).to(device)
            mask = labels >= 0
            if not bool(mask.any()):
                continue
            optimizer.zero_grad(set_to_none=True)
            logits = model(tensor)
            loss = criterion(logits[mask], labels[mask])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        mean_loss = sum(losses) / max(len(losses), 1)
        epoch_losses.append(mean_loss)
        print(f"stage={stage} epoch={epoch} loss={mean_loss:.6f} chunks={len(chunks)} device={device}")
    return epoch_losses


def _load_target_tables(args: argparse.Namespace):
    config = load_config(args.config)
    if config.window_seconds != 15.0 or config.step_seconds != 7.5:
        config = replace(config, window_seconds=15.0, step_seconds=7.5)
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    records = discover_raw_files(config.raw_data_root)
    if args.participants:
        selected = set(args.participants)
        records = [record for record in records if record.participant_id in selected]
    if args.max_files_per_participant is not None:
        if args.max_files_per_participant <= 0:
            raise ValueError("--max-files-per-participant must be positive")
        counts: dict[str, int] = defaultdict(int)
        limited = []
        for record in records:
            if counts[record.participant_id] >= args.max_files_per_participant:
                continue
            counts[record.participant_id] += 1
            limited.append(record)
        records = limited
    train_participants, valid_participants = split_participants(
        [record.participant_id for record in records],
        valid_fraction=args.valid_fraction,
        seed=args.split_seed,
    )
    train_set, valid_set = set(train_participants), set(valid_participants)
    tables: dict[Path, tuple[object, CandidateTable]] = {}
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
    train_tables = [table for record, table in tables.values() if record.participant_id in train_set]
    if not train_tables:
        raise ValueError("no target train candidate tables were loaded")
    return config, meal_events, tables, train_tables, train_participants, valid_participants, valid_set, skipped


def _evaluate_target(
    tables: dict[Path, tuple[object, CandidateTable]],
    *,
    meal_events: object,
    valid_participants: Sequence[str],
    valid_set: set[str],
    model: TemporalTransformer,
    mean: np.ndarray,
    scale: np.ndarray,
    device: torch.device,
    sequence_length: int,
    sequence_stride: int,
    threshold: float,
    fuse_gap_ms: int,
    decode_fuse_gap_ms: int,
) -> tuple[dict[str, float | int], dict[str, object]]:
    predictions_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    truths_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    for record, table in tables.values():
        if record.participant_id not in valid_set:
            continue
        scores = _score_table(model, table, mean, scale, device, sequence_length, sequence_stride)
        predicted = eventize_windows(
            table.windows,
            scores,
            threshold=threshold,
            min_duration_ms=180_000,
            fuse_gap_ms=fuse_gap_ms,
        )
        predictions_by_participant[record.participant_id].extend(
            EventInterval(start, end) for start, end in predicted
        )
        truths_by_participant[record.participant_id].extend(events_for_record(record, meal_events))

    all_predictions: list[EventInterval] = []
    all_truths: list[EventInterval] = []
    participant_metrics: dict[str, object] = {}
    for participant in valid_participants:
        predictions = _merge_intervals(
            predictions_by_participant[participant],
            fuse_gap_ms=decode_fuse_gap_ms,
        )
        truths = sorted(set(truths_by_participant[participant]))
        metrics = evaluate_events(predictions, truths)
        all_predictions.extend(predictions)
        all_truths.extend(truths)
        participant_metrics[participant] = _metric_dict(metrics)
    return _metric_dict(evaluate_events(all_predictions, all_truths)), participant_metrics


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--external-dataset", choices=("FD-I", "FD-II"), default="FD-I")
    parser.add_argument("--external-participants", nargs="*", type=int, default=None)
    parser.add_argument("--external-max-participants", type=int, default=8)
    parser.add_argument("--external-wrist", choices=("left", "right", "both"), default="both")
    parser.add_argument("--max-windows-per-sequence", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("artifacts/external-transformer-preflight.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/external-transformer-preflight.pt"))
    parser.add_argument("--participants", nargs="*", default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--valid-fraction", type=float, default=0.4)
    parser.add_argument("--split-seed", type=int, default=20260910)
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--fuse-gap-ms", type=int, default=300_000)
    parser.add_argument("--decode-fuse-gap-ms", type=int, default=600_000)
    parser.add_argument("--external-epochs", type=int, default=2)
    parser.add_argument("--finetune-epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--d-model", type=int, default=16)
    parser.add_argument("--nhead", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--dim-feedforward", type=int, default=32)
    parser.add_argument("--sequence-length", type=int, default=128)
    parser.add_argument("--sequence-stride", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.external_epochs < 0 or args.finetune_epochs <= 0:
        raise ValueError("external epochs must be non-negative and finetune epochs positive")
    if args.external_max_participants is not None and args.external_max_participants <= 0:
        raise ValueError("external max participants must be positive")
    if args.max_windows_per_sequence is not None and args.max_windows_per_sequence <= 0:
        raise ValueError("max windows per sequence must be positive")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        raise ValueError("learning rate must be positive and weight decay non-negative")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device(
        "cuda" if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()) else "cpu"
    )
    torch.manual_seed(args.split_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.split_seed)

    config, meal_events, target_tables, train_tables, train_participants, valid_participants, valid_set, skipped = _load_target_tables(args)
    target_labels = np.concatenate([table.labels for table in train_tables])
    target_pos_weight = _positive_weight(target_labels)
    mean, scale = _standardizer(train_tables)

    if args.external_participants is not None:
        external_indices = tuple(args.external_participants)
    elif args.external_max_participants is None:
        external_indices = None
    else:
        external_indices = tuple(range(args.external_max_participants))
    external_tables = collect_external_window_tables(
        args.external_root,
        dataset=args.external_dataset,
        participant_indices=external_indices,
        wrist=args.external_wrist,
        window_seconds=15.0,
        step_seconds=7.5,
        feature_hz=float(config.imu_grid_hz),
        max_windows_per_sequence=args.max_windows_per_sequence,
    )
    if not external_tables:
        raise ValueError("no external window tables were collected")
    external_labels = np.concatenate([table.labels for table in external_tables])
    external_pos_weight = _positive_weight(external_labels)

    model = TemporalTransformer(
        train_tables[0].features.shape[1],
        TransformerConfig(
            d_model=args.d_model,
            nhead=args.nhead,
            num_layers=args.num_layers,
            dim_feedforward=args.dim_feedforward,
            dropout=args.dropout,
            max_sequence_length=args.sequence_length,
        ),
    ).to(device)
    external_losses = _train_tables(
        model,
        external_tables,
        mean=mean,
        scale=scale,
        device=device,
        sequence_length=args.sequence_length,
        sequence_stride=args.sequence_stride,
        epochs=args.external_epochs,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        pos_weight=external_pos_weight,
        seed=args.split_seed + 100_000,
        stage="external-pretrain",
    )
    target_losses = _train_tables(
        model,
        train_tables,
        mean=mean,
        scale=scale,
        device=device,
        sequence_length=args.sequence_length,
        sequence_stride=args.sequence_stride,
        epochs=args.finetune_epochs,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        pos_weight=target_pos_weight,
        seed=args.split_seed,
        stage="target-finetune",
    )
    metrics, participant_metrics = _evaluate_target(
        target_tables,
        meal_events=meal_events,
        valid_participants=valid_participants,
        valid_set=valid_set,
        model=model,
        mean=mean,
        scale=scale,
        device=device,
        sequence_length=args.sequence_length,
        sequence_stride=args.sequence_stride,
        threshold=args.threshold,
        fuse_gap_ms=args.fuse_gap_ms,
        decode_fuse_gap_ms=args.decode_fuse_gap_ms,
    )
    valid_f1s = [float(value["f1"]) for value in participant_metrics.values()]
    result = {
        "model": "external_pretrained_lightweight_temporal_transformer",
        "device": str(device),
        "target_train_participants": list(train_participants),
        "target_valid_participants": list(valid_participants),
        "target_processed_records": len(target_tables),
        "target_skipped_files": skipped,
        "external_dataset": args.external_dataset,
        "external_participants": sorted({table.participant_id for table in external_tables}),
        "external_wrist": args.external_wrist,
        "external_table_count": len(external_tables),
        "external_window_labels": {
            "positive": int((external_labels == 1).sum()),
            "negative": int((external_labels == 0).sum()),
        },
        "external_epochs": args.external_epochs,
        "finetune_epochs": args.finetune_epochs,
        "external_losses": external_losses,
        "target_losses": target_losses,
        "dropout": args.dropout,
        "weight_decay": args.weight_decay,
        "target_pos_weight": target_pos_weight,
        "external_pos_weight": external_pos_weight,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "threshold": args.threshold,
        "fuse_gap_ms": args.fuse_gap_ms,
        "decode_fuse_gap_ms": args.decode_fuse_gap_ms,
        "metrics": metrics,
        "participant_metrics": participant_metrics,
        "worst_participant_f1": min(valid_f1s) if valid_f1s else 0.0,
    }
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "mean": mean,
            "scale": scale,
            "config": result,
        },
        args.checkpoint,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
