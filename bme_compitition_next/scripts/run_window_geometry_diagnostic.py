"""Run the preregistered exact 15 s / 7.5 s versus 3 s geometry diagnostic."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Iterable, Mapping, Sequence

import numpy as np

from eating_event.config import load_config
from eating_event.data.manifest import (
    RawFileRecord,
    discover_raw_files,
    events_for_record,
    filter_meal_events_by_ledger,
    load_meal_events,
)
from eating_event.data.raw import RawFileFormatError, read_imu_tsv, regularize_imu
from eating_event.data.windows import WindowRecord, generate_dense_windows
from eating_event.metrics import EventInterval
try:
    from scripts.run_candidate_baseline import _cache_metadata
except ModuleNotFoundError:  # direct ``python scripts/...py`` execution
    from run_candidate_baseline import _cache_metadata


SPEC_PATH = Path("configs/formal-g1-window-geometry-diagnostic-v1.json")
HASH_PATH = Path("configs/formal-g1-window-geometry-diagnostic-v1.sha256")
DEFAULT_OUTPUT = Path("artifacts/g1-window-geometry-diagnostic-v1")


@dataclass(frozen=True)
class EventKey:
    participant: str
    start_ms: int
    end_ms: int

    @property
    def event_id(self) -> str:
        return f"{self.participant}:{self.start_ms}-{self.end_ms}"


@dataclass(frozen=True)
class TaggedWindow:
    start_ms: int
    end_ms: int
    label: str
    recording: str


def _json_default(value: object) -> object:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def verify_spec() -> tuple[dict[str, object], str]:
    spec_bytes = SPEC_PATH.read_bytes()
    expected = HASH_PATH.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = hashlib.sha256(spec_bytes).hexdigest()
    if actual != expected:
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: spec hash mismatch")
    spec = json.loads(spec_bytes.decode("utf-8"))
    if spec.get("status") != "FROZEN_READ_ONLY":
        raise RuntimeError("PREREGISTRATION_IMPLEMENTATION_BLOCKER: spec is not frozen")
    return spec, actual


def _event_key(row: Mapping[str, object]) -> EventKey:
    return EventKey(str(row["participant_id"]), int(row["start_ms"]), int(row["end_ms"]))


def _event_interval(key: EventKey) -> EventInterval:
    return EventInterval(key.start_ms, key.end_ms)


def _intersect(left_start: int, left_end: int, right_start: int, right_end: int) -> tuple[int, int] | None:
    start = max(left_start, right_start)
    end = min(left_end, right_end)
    return (start, end) if end > start else None


def _merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted((int(start), int(end)) for start, end in intervals if end > start)
    if not ordered:
        return []
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(row[0], row[1]) for row in merged]


def _subtract_intervals(left: Sequence[tuple[int, int]], right: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    output: list[tuple[int, int]] = []
    right_merged = _merge_intervals(right)
    for start, end in _merge_intervals(left):
        cursor = start
        for other_start, other_end in right_merged:
            if other_end <= cursor:
                continue
            if other_start >= end:
                break
            if other_start > cursor:
                output.append((cursor, min(other_start, end)))
            cursor = max(cursor, other_end)
            if cursor >= end:
                break
        if cursor < end:
            output.append((cursor, end))
    return output


def _geometry_for_event(key: EventKey, windows: Sequence[TaggedWindow]) -> dict[str, object]:
    gt_start, gt_end = key.start_ms, key.end_ms
    gt_duration = gt_end - gt_start
    event_windows = [window for window in windows if window.start_ms < gt_end and window.end_ms > gt_start]
    positive_windows = [window for window in event_windows if window.label == "positive"]
    ignore_windows = [window for window in event_windows if window.label == "ignore"]
    positive_intervals = [
        clipped
        for window in positive_windows
        if (clipped := _intersect(window.start_ms, window.end_ms, gt_start, gt_end)) is not None
    ]
    positive_union = _merge_intervals(positive_intervals)
    covered_ms = sum(end - start for start, end in positive_union)
    unsupported = _subtract_intervals([(gt_start, gt_end)], positive_union)
    overlap_sum_ms = sum(end - start for start, end in positive_intervals)
    selected = [window for window in event_windows if window.label == "positive"]
    all_starts = sorted(window.start_ms for window in event_windows)
    return {
        "dense_window_count": len(event_windows),
        "positive_window_count": len(positive_windows),
        "ignore_window_count": len(ignore_windows),
        "positive_window_intervals": [[window.start_ms, window.end_ms] for window in positive_windows],
        "positive_window_intersections": [[start, end] for start, end in positive_intervals],
        "positive_union_intervals": [[start, end] for start, end in positive_union],
        "positive_union_coverage_ms": covered_ms,
        "positive_union_coverage_fraction": covered_ms / gt_duration if gt_duration else None,
        "unsupported_intervals": [[start, end] for start, end in unsupported],
        "unsupported_duration_ms": sum(end - start for start, end in unsupported),
        "longest_unsupported_gap_ms": max((end - start for start, end in unsupported), default=0),
        "leading_unsupported_ms": unsupported[0][1] - unsupported[0][0] if unsupported and unsupported[0][0] == gt_start else 0,
        "trailing_unsupported_ms": unsupported[-1][1] - unsupported[-1][0] if unsupported and unsupported[-1][1] == gt_end else 0,
        "positive_overlap_sum_ms": overlap_sum_ms,
        "positive_overlap_redundancy": overlap_sum_ms / covered_ms if covered_ms else None,
        "first_positive_offset_ms": min((window.start_ms - gt_start for window in selected), default=None),
        "last_positive_offset_ms": max((window.end_ms - gt_end for window in selected), default=None),
        "event_window_start_min_ms": min(all_starts, default=None),
        "event_window_start_max_ms": max(all_starts, default=None),
        "recordings_with_event_windows": sorted({window.recording for window in event_windows}),
    }


def _delta(a: Mapping[str, object], b: Mapping[str, object], field: str) -> object:
    left, right = a.get(field), b.get(field)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return right - left
    return None


def _support_group(positive_window_count: int) -> str:
    if positive_window_count < 10:
        return "<10"
    if positive_window_count < 25:
        return "10-24"
    if positive_window_count < 50:
        return "25-49"
    return ">=50"


def _load_truths(ledger: Mapping[str, object]) -> dict[str, tuple[EventInterval, ...]]:
    meal_metadata_path = Path(str(ledger["meal_metadata_path"]))
    all_events = load_meal_events(meal_metadata_path)
    return filter_meal_events_by_ledger(all_events, ledger, eligibility_field="training_eligibility")


def _expected_cache(config, record: RawFileRecord, ledger: Mapping[str, object]) -> Path:
    metadata = _cache_metadata(record, config, eligibility_artifact_sha256=str(ledger["event_denominator_sha256"]))
    return Path("artifacts/g1-formal-cache-v3-final") / f"{metadata['cache_key']}.npz"


def _compare_to_cache(
    config,
    record: RawFileRecord,
    ledger: Mapping[str, object],
    windows: Sequence[WindowRecord],
) -> dict[str, object]:
    cache_path = _expected_cache(config, record, ledger)
    if not cache_path.is_file():
        return {"status": "MISSING_APPROVED_CACHE", "path": str(cache_path)}
    payload = np.load(cache_path, allow_pickle=True)
    actual_starts = np.asarray([window.window.start_ms for window in windows], dtype=np.int64)
    actual_ends = np.asarray([window.window.end_ms for window in windows], dtype=np.int64)
    actual_labels = np.asarray([window.label.value for window in windows], dtype=object)
    expected_labels_raw = payload["labels"]
    label_names = {-1: "ignore", 0: "negative", 1: "positive"}
    expected_labels = np.asarray(
        [label_names.get(int(value), f"unknown:{int(value)}") for value in expected_labels_raw],
        dtype=object,
    )
    checks = {
        "starts": bool(np.array_equal(actual_starts, payload["starts"])),
        "ends": bool(np.array_equal(actual_ends, payload["ends"])),
        "labels": bool(np.array_equal(actual_labels, expected_labels)),
        "coverage": bool(np.allclose(np.asarray([window.coverage for window in windows]), payload["coverage"], atol=1e-12)),
        "invalid_runs": bool(np.array_equal(np.asarray([window.longest_invalid_run for window in windows]), payload["invalid_runs"])),
        "crosses_gap": bool(np.array_equal(np.asarray([window.crosses_hard_gap for window in windows]), payload["crosses_gap"])),
    }
    return {
        "status": "MATCH" if all(checks.values()) else "MISMATCH",
        "path": str(cache_path),
        "checks": checks,
        "actual_count": int(actual_starts.size),
        "expected_count": int(payload["starts"].size),
    }


def _build_pair(
    config,
    record: RawFileRecord,
    truths: Sequence[EventInterval],
) -> tuple[list[WindowRecord], list[WindowRecord], dict[str, object]]:
    started = time.perf_counter()
    raw = read_imu_tsv(record.path)
    series = regularize_imu(raw, grid_hz=config.imu_grid_hz, max_gap_seconds=config.max_gap_seconds)
    common = {
        "grid_origin_ms": int(series.timestamps_ms[0]) if series.timestamps_ms.size else None,
        "grid_end_ms": int(series.timestamps_ms[-1]) if series.timestamps_ms.size else None,
        "grid_points": int(series.timestamps_ms.size),
        "valid_points": int(series.valid_mask.sum()),
        "hard_gap_points": int(series.hard_gap_mask.sum()),
        "regularization_seconds": time.perf_counter() - started,
    }
    kwargs = {
        "timestamps_ms": series.timestamps_ms,
        "valid_mask": series.valid_mask,
        "grid_hz": config.imu_grid_hz,
        "window_seconds": config.window_seconds,
        "min_coverage": config.min_coverage,
        "max_gap_seconds": config.max_gap_seconds,
        "hard_gap_mask": series.hard_gap_mask,
        "segment_id": series.segment_id,
        "truths": truths,
        "positive_overlap": config.positive_overlap,
    }
    a = generate_dense_windows(**kwargs, step_seconds=config.step_seconds)
    b = generate_dense_windows(**kwargs, step_seconds=3.0)
    common["elapsed_seconds"] = time.perf_counter() - started
    return a, b, common


def _record_event_windows(
    record: RawFileRecord,
    event_keys: Sequence[EventKey],
    windows: Sequence[WindowRecord],
) -> dict[str, list[TaggedWindow]]:
    output = {key.event_id: [] for key in event_keys}
    for key in event_keys:
        event = _event_interval(key)
        output[key.event_id].extend(
            TaggedWindow(
                start_ms=window.window.start_ms,
                end_ms=window.window.end_ms,
                label=window.label.value,
                recording=str(record.path),
            )
            for window in windows
            if window.window.start_ms < event.end_ms and window.window.end_ms > event.start_ms
        )
    return output


def _start_classification(a: Sequence[TaggedWindow], b: Sequence[TaggedWindow]) -> dict[str, int]:
    a_starts = {window.start_ms for window in a}
    b_starts = {window.start_ms for window in b}
    return {
        "common_start_count": len(a_starts & b_starts),
        "a_only_start_count": len(a_starts - b_starts),
        "b_only_start_count": len(b_starts - a_starts),
    }


def _build_event_rows(
    event_keys: Sequence[EventKey],
    a_by_event: Mapping[str, Sequence[TaggedWindow]],
    b_by_event: Mapping[str, Sequence[TaggedWindow]],
    ledger_rows: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in event_keys:
        a = _geometry_for_event(key, a_by_event.get(key.event_id, ()))
        b = _geometry_for_event(key, b_by_event.get(key.event_id, ()))
        row: dict[str, object] = {
            "event_id": key.event_id,
            "participant": key.participant,
            "gt_start_ms": key.start_ms,
            "gt_end_ms": key.end_ms,
            "duration_ms": key.end_ms - key.start_ms,
            "outer_fold": ledger_rows[key.event_id].get("outer_fold"),
            "historical_status": ledger_rows[key.event_id].get("historical_status"),
            "original_support_group": _support_group(int(a["positive_window_count"])),
            "A": a,
            "B": b,
            "delta_B_minus_A": {
                field: _delta(a, b, field)
                for field in (
                    "dense_window_count",
                    "positive_window_count",
                    "ignore_window_count",
                    "positive_union_coverage_ms",
                    "positive_union_coverage_fraction",
                    "unsupported_duration_ms",
                    "longest_unsupported_gap_ms",
                    "leading_unsupported_ms",
                    "trailing_unsupported_ms",
                    "positive_overlap_redundancy",
                )
            },
            "new_support_intervals_B_minus_A": [
                list(interval)
                for interval in _subtract_intervals(
                    [tuple(interval) for interval in b["positive_union_intervals"]],
                    [tuple(interval) for interval in a["positive_union_intervals"]],
                )
            ],
            "lost_support_intervals_A_minus_B": [
                list(interval)
                for interval in _subtract_intervals(
                    [tuple(interval) for interval in a["positive_union_intervals"]],
                    [tuple(interval) for interval in b["positive_union_intervals"]],
                )
            ],
            "start_classification": _start_classification(a_by_event.get(key.event_id, ()), b_by_event.get(key.event_id, ())),
        }
        rows.append(row)
    return rows


def _ledger_rows(ledger: Mapping[str, object], spec: Mapping[str, object], fold_map: Mapping[str, str]) -> dict[str, dict[str, object]]:
    historical: dict[str, dict[str, object]] = {}
    try:
        review = json.loads(Path("artifacts/g1-model-temporal-representation-review-v1.json").read_text(encoding="utf-8"))
        for row in review["event_audit"]["rows"]:
            historical[str(row["event_id"])] = {
                "historical_status": "covered" if bool(row.get("covered")) else "missing",
                "historical_taxonomy": row.get("taxonomy"),
            }
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        historical = {}
    result: dict[str, dict[str, object]] = {}
    for raw_row in ledger["event_eligibility"]:
        if not raw_row.get("training_eligibility"):
            continue
        key = _event_key(raw_row)
        event_id = key.event_id
        prior = historical.get(event_id, {})
        result[event_id] = {
            **prior,
            "outer_fold": fold_map.get(key.participant),
            "original_support_group": None,
        }
    return result


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=_json_default) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("pilot", "full"), required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-wall-seconds", type=float, default=None)
    parser.add_argument("--allow-full", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    spec, spec_hash = verify_spec()
    if args.phase == "full" and not args.allow_full:
        raise SystemExit("full phase requires explicit --allow-full")
    config = load_config(Path("configs/example.local.yaml"))
    ledger = json.loads(Path("artifacts/g1-candidate-coverage-v4/eligibility.json").read_text(encoding="utf-8"))
    truths_by_participant = _load_truths(ledger)
    all_event_keys = [_event_key(row) for row in ledger["event_eligibility"] if row.get("training_eligibility")]
    fold_map: dict[str, str] = {}
    for fold in spec["participant_disjoint_outer_folds"]["folds"]:
        for participant in fold["valid_participants"]:
            fold_map[str(participant)] = str(fold["fold_id"])
    ledger_rows = _ledger_rows(ledger, spec, fold_map)
    records = discover_raw_files(config.raw_data_root)
    if args.phase == "pilot":
        pilot_paths = {str(row["path"]) for row in spec["pilot"]["recordings"]}
        records = [record for record in records if str(record.path.resolve()) in pilot_paths]
        expected = int(spec["pilot"]["fixed_recording_count"])
        if len(records) != expected:
            raise RuntimeError(f"pilot recording identity mismatch: found {len(records)} expected {expected}")
        selected_event_ids = {str(value) for value in spec["pilot"]["fixed_events"]}
        event_keys = [key for key in all_event_keys if key.event_id in selected_event_ids]
        if len(event_keys) != len(selected_event_ids):
            raise RuntimeError("pilot event identity mismatch")
        output_path = args.output_dir / "pilot-paired-geometry.jsonl"
        equivalence_path = args.output_dir / "pilot-equivalence.json"
    else:
        event_keys = all_event_keys
        output_path = args.output_dir / "full-paired-geometry.jsonl"
        equivalence_path = args.output_dir / "full-equivalence.json"
    event_ids = [key.event_id for key in event_keys]
    event_id_set = set(event_ids)
    a_by_event: dict[str, list[TaggedWindow]] = {event_id: [] for event_id in event_ids}
    b_by_event: dict[str, list[TaggedWindow]] = {event_id: [] for event_id in event_ids}
    equivalence: list[dict[str, object]] = []
    timings: list[dict[str, object]] = []
    started_all = time.perf_counter()
    stopped = False
    processed = 0
    for record in records:
        if args.max_wall_seconds is not None and time.perf_counter() - started_all >= args.max_wall_seconds:
            stopped = True
            break
        record_events = tuple(event for event in truths_by_participant.get(record.participant_id, ()) if event.start_ms < record.session_end_ms and event.end_ms > record.session_start_ms)
        relevant_keys = [key for key in event_keys if key.participant == record.participant_id and key.start_ms < record.session_end_ms and key.end_ms > record.session_start_ms]
        if not relevant_keys:
            continue
        file_started = time.perf_counter()
        try:
            a_windows, b_windows, common = _build_pair(config, record, record_events)
        except RawFileFormatError as exc:
            equivalence.append({"path": str(record.path), "status": "RAW_FAILURE", "error": str(exc)})
            continue
        cache_check = _compare_to_cache(config, record, ledger, a_windows)
        equivalence.append({"path": str(record.path), "participant": record.participant_id, "cache_check": cache_check, "A_count": len(a_windows), "B_count": len(b_windows)})
        a_tagged = _record_event_windows(record, relevant_keys, a_windows)
        b_tagged = _record_event_windows(record, relevant_keys, b_windows)
        for event_id in event_id_set.intersection(a_tagged):
            a_by_event[event_id].extend(a_tagged[event_id])
            b_by_event[event_id].extend(b_tagged[event_id])
        timings.append({"path": str(record.path), "participant": record.participant_id, "elapsed_seconds": time.perf_counter() - file_started, **common, "A_dense_count": len(a_windows), "B_dense_count": len(b_windows)})
        processed += 1
        print(json.dumps({"processed": processed, "total_selected": len(records), "path": str(record.path), "elapsed_seconds": timings[-1]["elapsed_seconds"]}, ensure_ascii=False), flush=True)
    rows = _build_event_rows(event_keys, a_by_event, b_by_event, ledger_rows)
    _write_jsonl(output_path, rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    equivalence_payload = {
        "schema_version": "g1_window_geometry_equivalence_v1",
        "spec_sha256": spec_hash,
        "phase": args.phase,
        "status": "PARTIAL" if stopped else "COMPLETE",
        "processed_recordings": processed,
        "selected_recordings": len(records),
        "elapsed_seconds": time.perf_counter() - started_all,
        "recordings": equivalence,
        "timings": timings,
    }
    equivalence_path.write_text(json.dumps(equivalence_payload, indent=2, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")
    summary_path = args.output_dir / ("pilot-summary.json" if args.phase == "pilot" else "full-summary.json")
    summary_path.write_text(json.dumps({"spec_sha256": spec_hash, "phase": args.phase, "status": equivalence_payload["status"], "event_count": len(rows), "recording_count": processed, "elapsed_seconds": equivalence_payload["elapsed_seconds"]}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase": args.phase, "status": equivalence_payload["status"], "event_count": len(rows), "recording_count": processed, "elapsed_seconds": equivalence_payload["elapsed_seconds"], "output": str(output_path)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
