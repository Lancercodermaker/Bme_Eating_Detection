import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import yaml

from .audit import audit_sensor_files
from .cache import FeatureCacheConfig, build_feature_caches
from .config import Config, load_config
from .dataset import participant_from_sensor_path
from .decoding import decode_windows
from .io import read_meal_intervals
from .metrics import event_metrics
from .splits import load_manifest, make_manifest_from_directories
from .preprocess import apply_variant
from .training import evaluate_predictions, fit_m0_cached, save_json


def _sensor_files(train_dir: Path, limit_files: int | None) -> list[Path]:
    if train_dir.is_file():
        paths = [train_dir]
    else:
        paths = sorted(train_dir.rglob("*.txt"))
    return paths if limit_files is None else paths[:limit_files]


def _training_sensor_files(
    train_dir: Path,
    allowed_participants: set[str],
    limit_files: int | None,
    explicit_paths: list[str] | None = None,
) -> list[Path]:
    paths = [Path(path) for path in explicit_paths] if explicit_paths else _sensor_files(train_dir, None)
    paths = [
        path
        for path in paths
        if participant_from_sensor_path(path) in allowed_participants
    ]
    return paths if limit_files is None else paths[:limit_files]


def _config_payload(config: Config, args: argparse.Namespace) -> dict[str, object]:
    payload = {key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()}
    raw_config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    payload.update({key: value for key, value in raw_config.items() if key not in payload})
    payload.update(
        {
            "limit_files": args.limit_files,
            "max_rows": args.max_rows,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "device": args.device,
            "sensor_files": args.sensor_files,
            "min_quality_fraction": args.min_quality_fraction,
            "model_normalization": args.model_normalization,
            "model_pooling": args.model_pooling,
        }
    )
    return payload


def _write_config(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )


def run_toy_pipeline(output_dir: Path, seed: int = 7) -> dict[str, object]:
    """Run the smallest in-memory end-to-end event scoring path."""
    del seed  # The toy inputs are deterministic by construction.
    windows = [(0, 10), (10, 20)]
    probabilities = [0.8, 0.7]
    predicted = decode_windows(windows, probabilities, threshold=0.5, merge_gap_ms=0)
    result = event_metrics(predicted, [(0, 20)], iou_threshold=0.25)
    payload = {"status": "PASS", **result.as_dict()}
    save_json(Path(output_dir) / "metrics.json", payload)
    save_json(Path(output_dir) / "events.json", {"toy": predicted})
    return payload


def _run_audit(args: argparse.Namespace) -> int:
    paths = _sensor_files(Path(args.train_dir), args.limit_files)
    report = audit_sensor_files(paths, max_rows=args.max_rows, chunksize=args.chunksize)
    report["index_dir"] = str(Path(args.index_dir))
    report["train_dir"] = str(Path(args.train_dir))
    report["resample_hz"] = args.resample_hz
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "audit_sample.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AUDIT_PASS files={report['files_read']} rows={report['rows_read']}")
    return 0


def _run_make_manifest(args: argparse.Namespace) -> int:
    split = make_manifest_from_directories(
        index_dir=Path(args.index_dir),
        train_dir=Path(args.train_dir),
        output=Path(args.output),
        seed=args.seed,
        val_fraction=args.val_fraction,
    )
    print(f"SPLIT_PASS train_groups={len(split.train)} val_groups={len(split.val)}")
    return 0


def _run_train(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root) if args.data_root else None
    index_dir = Path(args.index_dir) if args.index_dir else None
    train_dir = Path(args.train_dir) if args.train_dir else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    config = load_config(
        Path(args.config),
        data_root=data_root,
        index_dir=index_dir,
        train_dir=train_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
    )
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    config_payload = _config_payload(config, args)
    preprocess_variant = str(config_payload.get("preprocess_variant", "p0_raw_mask"))
    config_payload["variant"] = apply_variant(
        preprocess_variant, raw_imu_channels=6, magnitude_channels=2, mask_channels=2
    )
    _write_config(output_dir / "config.yaml", config_payload)
    print(f"CONFIG_SAVED {output_dir / 'config.yaml'}")

    manifest_path = Path(args.split_manifest) if args.split_manifest else output_dir / "split_manifest.json"
    if args.split_manifest:
        source = Path(args.split_manifest)
        if source.resolve() != manifest_path.resolve():
            shutil.copyfile(source, manifest_path)
    else:
        make_manifest_from_directories(
            index_dir=config.index_dir,
            train_dir=config.train_dir,
            output=manifest_path,
            seed=config.seed,
            val_fraction=0.2,
        )
    manifest = load_manifest(manifest_path)
    if manifest_path.resolve() != (output_dir / "split_manifest.json").resolve():
        save_json(output_dir / "split_manifest.json", manifest)
        manifest_path = output_dir / "split_manifest.json"
    print(f"SPLIT_SAVED {output_dir / 'split_manifest.json'}")

    train_participants = set(manifest["train"])
    val_participants = set(manifest["val"])
    print(f"participants train={len(train_participants)} val={len(val_participants)}")
    intervals, interval_report = read_meal_intervals(config.index_dir)
    save_json(output_dir / "label_quality.json", interval_report)
    allowed = train_participants | val_participants
    paths = _training_sensor_files(
        config.train_dir,
        allowed,
        args.limit_files,
        explicit_paths=args.sensor_files,
    )
    truth = {
        participant: [list(interval) for interval in intervals.get(participant, [])]
        for participant in allowed
    }
    save_json(output_dir / "truth_intervals.json", truth)
    try:
        truth_tuples = {key: [tuple(item) for item in value] for key, value in truth.items()}
        cache_config = FeatureCacheConfig(
            resample_hz=config.resample_hz,
            max_gap_ms=config.max_gap_ms,
            preprocess_variant=preprocess_variant,
            lowpass_cutoff_hz=config.lowpass_cutoff_hz,
            median_kernel=config.median_kernel,
            window_sec=config.window_sec,
            step_sec=config.step_sec,
            positive_overlap=config.label_positive_overlap,
            boundary_mode=config.boundary_mode,
            chunksize=config.chunksize,
            max_rows=args.max_rows,
        )
        config_payload["cache_dir"] = str(config.cache_dir)
        caches, issues = build_feature_caches(
            paths, intervals, config.cache_dir, cache_config, lazy=True
        )
        save_json(output_dir / "input_issues.json", issues)
        if not caches:
            print("TRAIN_BLOCKED reason=no feature caches were built")
            return 2
        total_windows = sum(len(cache.window_indices) for cache in caches)
        print(
            f"CACHE_SUMMARY files={len(caches)} hits={sum(cache.cache_hit for cache in caches)} "
            f"misses={sum(not cache.cache_hit for cache in caches)} windows={total_windows}"
        )
        print(
            f"features shape=({total_windows},{caches[0].features.shape[0]},"
            f"{caches[0].window_indices[0, 1] - caches[0].window_indices[0, 0]})"
        )
        result = fit_m0_cached(
            caches=caches,
            train_participants=train_participants,
            val_participants=val_participants,
            truth=truth_tuples,
            output_dir=output_dir,
            config_payload=config_payload,
            split_manifest=manifest,
            epochs=args.epochs,
            batch_size=args.batch_size,
            seed=config.seed,
            iou_threshold=config.event_iou_threshold,
            device_name=args.device,
            cache_issues=issues,
            min_quality_fraction=args.min_quality_fraction,
            model_normalization=args.model_normalization,
            model_pooling=args.model_pooling,
        )
    except ValueError as exc:
        print(f"TRAIN_BLOCKED reason={exc}")
        return 2
    training_log = json.loads((output_dir / "training_log.json").read_text(encoding="utf-8"))
    for epoch, loss in enumerate(training_log["epoch_losses"], start=1):
        print(f"TRAIN_EPOCH epoch={epoch} loss={loss}")
    metrics = result["metrics"]
    print(
        "VAL_EVENTS "
        f"f1={metrics['f1']} precision={metrics['precision']} recall={metrics['recall']} "
        f"start_mae_ms={metrics['start_mae_ms']} end_mae_ms={metrics['end_mae_ms']}"
    )
    print(f"pos_weight={metrics['pos_weight']}")
    print("test_not_used=true")
    print("TRAIN_SMOKE_PASS")
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    rows = []
    with (run_dir / "window_probabilities.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row.get("split", "val") == args.split:
                    rows.append(row)
    predictions: dict[str, list[tuple[int, int, float]]] = {}
    for row in rows:
        predictions.setdefault(row["participant"], []).append(
            (int(row["start_ms"]), int(row["end_ms"]), float(row["probability"]))
        )
    truth_payload = json.loads((run_dir / "truth_intervals.json").read_text(encoding="utf-8"))
    truth = {key: [tuple(interval) for interval in value] for key, value in truth_payload.items()}
    manifest = load_manifest(run_dir / "split_manifest.json")
    if args.split == "test":
        scope = set(manifest.get("excluded_test", []))
    else:
        scope = set(manifest[args.split])
    decoder = json.loads((run_dir / "decoder.json").read_text(encoding="utf-8"))
    config_payload = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    aggregate, participant_metrics, events = evaluate_predictions(
        predictions,
        truth,
        decoder,
        float(config_payload["event_iou_threshold"]),
        participants=scope,
    )
    metrics_path = run_dir / "metrics.json"
    existing_metrics = {}
    if metrics_path.exists():
        existing_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = {
        **existing_metrics,
        **aggregate.as_dict(),
        "participant_metrics": participant_metrics,
        "events": events,
    }
    save_json(metrics_path, metrics)
    save_json(run_dir / f"events_{args.split}.json", events)
    print(
        f"EVAL_EVENTS split={args.split} f1={aggregate.f1} precision={aggregate.precision} "
        f"recall={aggregate.recall} start_mae_ms={aggregate.start_mae_ms} "
        f"end_mae_ms={aggregate.end_mae_ms} test_not_used={str(args.split != 'test').lower()}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eating-detection")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--index-dir", required=True)
    audit_parser.add_argument("--train-dir", required=True)
    audit_parser.add_argument("--output-dir", required=True)
    audit_parser.add_argument("--limit-files", type=int)
    audit_parser.add_argument("--max-rows", type=int)
    audit_parser.add_argument("--chunksize", type=int, default=50_000)
    audit_parser.add_argument("--resample-hz", type=int, default=25)
    audit_parser.set_defaults(handler=_run_audit)

    manifest_parser = subparsers.add_parser("make-manifest")
    manifest_parser.add_argument("--index-dir", required=True)
    manifest_parser.add_argument("--train-dir", required=True)
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.add_argument("--seed", type=int, default=7)
    manifest_parser.add_argument("--val-fraction", type=float, default=0.2)
    manifest_parser.set_defaults(handler=_run_make_manifest)

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--config", required=True)
    train_parser.add_argument("--data-root")
    train_parser.add_argument("--index-dir")
    train_parser.add_argument("--train-dir")
    train_parser.add_argument("--sensor-file", dest="sensor_files", action="append")
    train_parser.add_argument("--split-manifest")
    train_parser.add_argument("--output-dir")
    train_parser.add_argument("--cache-dir")
    train_parser.add_argument("--limit-files", type=int)
    train_parser.add_argument("--max-rows", type=int)
    train_parser.add_argument("--epochs", type=int, default=1)
    train_parser.add_argument("--batch-size", type=int, default=4)
    train_parser.add_argument("--device", default="auto")
    train_parser.add_argument("--min-quality-fraction", type=float, default=0.0)
    train_parser.add_argument(
        "--model-normalization", choices=("batch", "group"), default="batch"
    )
    train_parser.add_argument(
        "--model-pooling", choices=("avg", "avgmax"), default="avg"
    )
    train_parser.set_defaults(handler=_run_train)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--run-dir", required=True)
    evaluate_parser.add_argument("--split", choices=("train", "val", "test"), default="val")
    evaluate_parser.set_defaults(handler=_run_evaluate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
