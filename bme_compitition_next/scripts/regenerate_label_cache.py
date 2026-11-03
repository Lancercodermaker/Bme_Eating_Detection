"""Regenerate label-bearing candidate caches without trusting old labels.

The approved data-contract change does not alter raw parsing, resampling,
window geometry, feature extraction, window length, or stride.  This bounded
tool therefore reuses only the old cache's geometry/features, recomputes every
window label from the approved v3 ledger, and writes a new cache identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from eating_event.cache import build_cache_key, load_candidate_table, save_candidate_table
from eating_event.config import load_config
from eating_event.data.labels import label_window
from eating_event.data.manifest import (
    discover_raw_files,
    events_for_record,
    filter_meal_events_by_ledger,
    load_meal_events,
)
from eating_event.data.contract import label_contract_identity
from eating_event.metrics import EventInterval
try:
    from scripts.run_candidate_baseline import _cache_metadata
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_candidate_baseline import _cache_metadata
from eating_event.candidates import CandidateTable
from eating_event.data.windows import WindowRecord


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha256(
        "|".join([str(path), str(stat.st_size), str(stat.st_mtime_ns)]).encode("utf-8")
    ).hexdigest()


def _legacy_cache_key(
    source_fingerprint: str,
    window_seconds: float,
    step_seconds: float,
    feature_schema_version: str,
    label_schema_version: str,
) -> str:
    """Reproduce the pre-v3 five-field key solely to locate old geometry."""

    return hashlib.sha256(
        "|".join(
            [
                source_fingerprint,
                str(window_seconds),
                str(step_seconds),
                feature_schema_version,
                label_schema_version,
            ]
        ).encode("utf-8")
    ).hexdigest()


def _relabel_table(table: CandidateTable, truths: tuple[EventInterval, ...], positive_overlap: float) -> CandidateTable:
    windows = tuple(
        WindowRecord(
            window=record.window,
            coverage=record.coverage,
            longest_invalid_run=record.longest_invalid_run,
            crosses_hard_gap=record.crosses_hard_gap,
            label_result=label_window(
                EventInterval(record.window.start_ms, record.window.end_ms),
                truths,
                positive_overlap=positive_overlap,
            ),
        )
        for record in table.windows
    )
    return CandidateTable(
        features=table.features,
        feature_names=table.feature_names,
        labels=np.asarray(
            [1 if window.label.value == "positive" else 0 if window.label.value == "negative" else -1 for window in windows],
            dtype=np.int8,
        ),
        participant_ids=table.participant_ids,
        windows=windows,
        session_ids=table.session_ids,
    )


def regenerate_label_cache(
    *,
    config_path: str | Path,
    old_cache_dir: str | Path,
    new_cache_dir: str | Path,
    eligibility_path: str | Path,
) -> dict[str, int]:
    config = load_config(config_path)
    old_root = Path(old_cache_dir).expanduser().resolve()
    new_root = Path(new_cache_dir).expanduser().resolve()
    new_root.mkdir(parents=True, exist_ok=True)
    eligibility_file = Path(eligibility_path).expanduser().resolve()
    eligibility_bytes = eligibility_file.read_bytes()
    eligibility = json.loads(eligibility_bytes.decode("utf-8"))
    if not isinstance(eligibility, dict) or eligibility.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("label-cache regeneration requires participant_eligibility_v3")
    eligibility_sha256 = str(eligibility.get("label_eligible_event_denominator_sha256", ""))
    if not eligibility_sha256:
        raise ValueError("eligibility artifact lacks stable label-eligible ledger hash")
    meal_events = load_meal_events(config.metadata_root / "t_zsstnnrj_mealinfo_puadqog70826_1857.csv")
    meal_events = filter_meal_events_by_ledger(meal_events, eligibility, eligibility_field="training_eligibility")
    records = discover_raw_files(config.raw_data_root)
    label_version, label_hash = label_contract_identity(
        window_seconds=config.window_seconds,
        step_seconds=config.step_seconds,
        positive_overlap=config.positive_overlap,
    )
    stats = {"discovered": len(records), "regenerated": 0, "already_present": 0, "missing_old_cache": 0}
    for record in records:
        source_fingerprint = _source_fingerprint(record.path)
        old_key = _legacy_cache_key(
            source_fingerprint,
            config.window_seconds,
            config.step_seconds,
            config.feature_schema_version,
            config.label_schema_version,
        )
        old_path = old_root / f"{old_key}.npz"
        metadata = _cache_metadata(
            record,
            config,
            eligibility_artifact_sha256=eligibility_sha256,
        )
        new_path = new_root / f"{metadata['cache_key']}.npz"
        if new_path.is_file():
            stats["already_present"] += 1
            continue
        if not old_path.is_file():
            stats["missing_old_cache"] += 1
            continue
        old_table = load_candidate_table(old_path)
        truths = events_for_record(record, meal_events)
        table = _relabel_table(old_table, truths, config.positive_overlap)
        save_candidate_table(new_path, table, metadata=metadata)
        stats["regenerated"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--old-cache-dir", type=Path, required=True)
    parser.add_argument("--new-cache-dir", type=Path, required=True)
    parser.add_argument("--eligibility", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(regenerate_label_cache(
        config_path=args.config,
        old_cache_dir=args.old_cache_dir,
        new_cache_dir=args.new_cache_dir,
        eligibility_path=args.eligibility,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
