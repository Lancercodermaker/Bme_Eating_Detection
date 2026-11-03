"""Bounded same-set overfit diagnostic for the approved candidate data contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from eating_event.candidates import eventize_windows, fit_candidate_model
from eating_event.cache import load_candidate_table
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files, filter_meal_events_by_ledger, load_meal_events
try:
    from scripts.run_candidate_baseline import _cache_key
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import _cache_key


def run_small_set_overfit(
    *,
    config_path: str | Path,
    cache_dir: str | Path,
    eligibility_path: str | Path,
    participant: str,
    max_files: int,
    output_path: str | Path,
) -> dict[str, object]:
    if max_files <= 0:
        raise ValueError("max_files must be positive")
    config = load_config(config_path)
    eligibility = json.loads(Path(eligibility_path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(eligibility, dict) or eligibility.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("small-set overfit requires participant_eligibility_v3")
    ledger_hash = str(eligibility.get("label_eligible_event_denominator_sha256", ""))
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    meal_events = filter_meal_events_by_ledger(meal_events, eligibility, eligibility_field="training_eligibility")
    records = [
        record
        for record in discover_raw_files(config.raw_data_root)
        if record.participant_id == participant
    ][:max_files]
    if not records:
        raise ValueError(f"no records found for participant {participant}")
    tables = []
    for record in records:
        cache_path = Path(cache_dir).expanduser().resolve() / (
            f"{_cache_key(record, config, eligibility_artifact_sha256=ledger_hash)}.npz"
        )
        tables.append(load_candidate_table(cache_path))
    features = np.vstack([table.features for table in tables])
    labels = np.concatenate([table.labels for table in tables])
    model = fit_candidate_model(features, labels, random_state=20260910, max_iter=300)
    scores = model.predict_scores(features)
    labeled = labels >= 0
    predictions = (scores[labeled] >= 0.5).astype(np.int8)
    window_accuracy = float((predictions == labels[labeled]).mean()) if bool(labeled.any()) else 0.0
    predicted_event_count = sum(
        len(eventize_windows(table.windows, model.predict_scores(table.features), threshold=0.5))
        for table in tables
    )
    payload: dict[str, object] = {
        "schema_version": "small_set_overfit_v1",
        "status": "pass" if window_accuracy >= 0.95 else "fail",
        "failure_class": None if window_accuracy >= 0.95 else "DATA/PIPELINE",
        "participant": participant,
        "records": len(records),
        "window_count": int(labels.size),
        "positive_windows": int((labels == 1).sum()),
        "negative_windows": int((labels == 0).sum()),
        "ignore_windows": int((labels < 0).sum()),
        "labeled_window_accuracy": window_accuracy,
        "predicted_event_count": predicted_event_count,
        "window_seconds": config.window_seconds,
        "step_seconds": config.step_seconds,
        "positive_overlap": config.positive_overlap,
    }
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--eligibility", type=Path, required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_small_set_overfit(
        config_path=args.config,
        cache_dir=args.cache_dir,
        eligibility_path=args.eligibility,
        participant=args.participant,
        max_files=args.max_files,
        output_path=args.output,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
