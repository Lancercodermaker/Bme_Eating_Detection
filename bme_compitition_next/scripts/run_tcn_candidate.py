"""Train a small TCN candidate scorer on cached dense local windows."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from torch import nn

from eating_event.candidates import CandidateTable, eventize_windows, split_participants
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files, events_for_record, load_meal_events
from eating_event.data.raw import RawFileFormatError
from eating_event.metrics import EventInterval, evaluate_events
from eating_event.models.tcn import TCNConfig, TemporalConvNet
from scripts.run_candidate_baseline import _build_table, _cache_key, _load_table, _merge_intervals


def _metric_dict(metrics: object) -> dict[str, float | int]:
    return {
        "tp": metrics.tp,
        "fp": metrics.fp,
        "fn": metrics.fn,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "start_mae_ms": metrics.start_mae_ms,
        "end_mae_ms": metrics.end_mae_ms,
    }


def _parse_dilations(value: str) -> tuple[int, ...]:
    dilations = tuple(int(item) for item in value.split(",") if item.strip())
    if not dilations or any(item <= 0 for item in dilations):
        raise ValueError("--dilations must contain positive comma-separated integers")
    return dilations


def _standardizer(tables: list[CandidateTable]) -> tuple[np.ndarray, np.ndarray]:
    values = np.vstack([np.nan_to_num(table.features, nan=0.0, posinf=0.0, neginf=0.0) for table in tables])
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale < 1e-6] = 1.0
    return mean.astype(np.float32), scale.astype(np.float32)


def _score_table(
    model: TemporalConvNet,
    table: CandidateTable,
    mean: np.ndarray,
    scale: np.ndarray,
    device: torch.device,
) -> np.ndarray:
    values = np.nan_to_num(table.features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    tensor = torch.from_numpy(((values - mean) / scale).T[None]).to(device)
    with torch.inference_mode():
        return torch.sigmoid(model(tensor)).squeeze(0).cpu().numpy().astype(np.float64)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/tcn-candidate.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/tcn-candidate.pt"))
    parser.add_argument("--participants", nargs="*", default=None)
    parser.add_argument("--max-files-per-participant", type=int, default=None)
    parser.add_argument("--valid-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", type=int, default=20260910)
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--fuse-gap-ms", type=int, default=300_000)
    parser.add_argument("--decode-fuse-gap-ms", type=int, default=600_000)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--hidden-channels", type=int, default=32)
    parser.add_argument("--dilations", type=str, default="1,2,4,8,16")
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--pos-weight", type=float, default=None)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.epochs <= 0 or args.learning_rate <= 0:
        raise ValueError("epochs and learning rate must be positive")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device("cuda" if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()) else "cpu")

    torch.manual_seed(args.split_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.split_seed)
    config = load_config(args.config)
    if config.window_seconds != 15.0 or config.step_seconds != 7.5:
        config = replace(config, window_seconds=15.0, step_seconds=7.5)
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    records = discover_raw_files(config.raw_data_root)
    if args.participants:
        selected = set(args.participants)
        records = [record for record in records if record.participant_id in selected]
    if args.max_files_per_participant is not None:
        counts: dict[str, int] = defaultdict(int)
        limited = []
        for record in records:
            if counts[record.participant_id] >= args.max_files_per_participant:
                continue
            counts[record.participant_id] += 1
            limited.append(record)
        records = limited
    train_participants, valid_participants = split_participants(
        [record.participant_id for record in records], valid_fraction=args.valid_fraction, seed=args.split_seed
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
        raise ValueError("no train candidate tables were loaded")
    train_labels = np.concatenate([table.labels for table in train_tables])
    labeled = train_labels >= 0
    positives = int((train_labels[labeled] == 1).sum())
    negatives = int((train_labels[labeled] == 0).sum())
    if positives == 0 or negatives == 0:
        raise ValueError("TCN training needs both positive and negative window labels")
    pos_weight = args.pos_weight if args.pos_weight is not None else min(10.0, negatives / positives)
    if pos_weight <= 0:
        raise ValueError("pos_weight must be positive")
    mean, scale = _standardizer(train_tables)
    model = TemporalConvNet(
        input_channels=train_tables[0].features.shape[1],
        config=TCNConfig(
            hidden_channels=args.hidden_channels,
            dilations=_parse_dilations(args.dilations),
            dropout=args.dropout,
        ),
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, device=device))

    for epoch in range(1, args.epochs + 1):
        model.train()
        order = np.random.default_rng(args.split_seed + epoch).permutation(len(train_tables))
        losses: list[float] = []
        for index in order:
            table = train_tables[int(index)]
            values = np.nan_to_num(table.features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            tensor = torch.from_numpy(((values - mean) / scale).T[None]).to(device)
            labels = torch.from_numpy(table.labels.astype(np.float32)[None]).to(device)
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
        print(f"epoch={epoch} loss={sum(losses) / max(len(losses), 1):.6f} device={device}")

    model.eval()
    predictions_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    truths_by_participant: dict[str, list[EventInterval]] = defaultdict(list)
    for record, table in tables.values():
        if record.participant_id not in valid_set:
            continue
        scores = _score_table(model, table, mean, scale, device)
        predicted = eventize_windows(
            table.windows,
            scores,
            threshold=args.threshold,
            min_duration_ms=180_000,
            fuse_gap_ms=args.fuse_gap_ms,
        )
        predictions_by_participant[record.participant_id].extend(
            EventInterval(start_ms, end_ms) for start_ms, end_ms in predicted
        )
        truths_by_participant[record.participant_id].extend(events_for_record(record, meal_events))

    all_predictions: list[EventInterval] = []
    all_truths: list[EventInterval] = []
    participant_metrics: dict[str, object] = {}
    for participant in valid_participants:
        predictions = _merge_intervals(predictions_by_participant[participant], fuse_gap_ms=args.decode_fuse_gap_ms)
        truths = sorted(set(truths_by_participant[participant]))
        metrics = evaluate_events(predictions, truths)
        all_predictions.extend(predictions)
        all_truths.extend(truths)
        participant_metrics[participant] = _metric_dict(metrics)
    metrics = evaluate_events(all_predictions, all_truths)
    result = {
        "device": str(device),
        "train_participants": list(train_participants),
        "valid_participants": list(valid_participants),
        "epochs": args.epochs,
        "threshold": args.threshold,
        "fuse_gap_ms": args.fuse_gap_ms,
        "decode_fuse_gap_ms": args.decode_fuse_gap_ms,
        "pos_weight": pos_weight,
        "train_window_labels": {"positive": positives, "negative": negatives},
        "processed_records": len(tables),
        "skipped_files": skipped,
        "metrics": _metric_dict(metrics),
        "participant_metrics": participant_metrics,
    }
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "mean": mean, "scale": scale, "config": result}, args.checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()

