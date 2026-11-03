"""Audit per-event dense and positive-window representability."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from eating_event.data.labels import label_window
from eating_event.data.manifest import load_meal_events
from eating_event.metrics import EventInterval


def audit_event_representability(
    *,
    eligibility_path: str | Path,
    cache_dir: str | Path,
    meal_metadata_path: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    eligibility_file = Path(eligibility_path).expanduser().resolve()
    eligibility = json.loads(eligibility_file.read_text(encoding="utf-8"))
    if not isinstance(eligibility, dict) or eligibility.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("representability audit requires participant_eligibility_v3")
    rows = eligibility.get("event_eligibility")
    if not isinstance(rows, list):
        raise ValueError("eligibility artifact lacks event_eligibility")
    meal_events = load_meal_events(meal_metadata_path)
    labels_by_participant: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    aggregate = {1: 0, 0: 0, -1: 0}
    cache_files = 0
    for cache_path in sorted(Path(cache_dir).expanduser().resolve().glob("*.npz")):
        with np.load(cache_path, allow_pickle=True) as payload:
            starts = payload["starts"].astype(np.int64, copy=False)
            ends = payload["ends"].astype(np.int64, copy=False)
            labels = payload["labels"].astype(np.int8, copy=False)
            participants = payload["participant_ids"].astype(str, copy=False)
        cache_files += 1
        for label in labels.tolist():
            if int(label) not in aggregate:
                raise ValueError(f"cache contains invalid label: {label}")
            aggregate[int(label)] += 1
        for participant, start, end, label in zip(participants, starts, ends, labels):
            labels_by_participant[str(participant)].append((int(start), int(end), int(label)))

    audit_rows: list[dict[str, object]] = []
    positive_eligible_count = 0
    short_positive_count = 0
    participant_positive: dict[str, int] = defaultdict(int)
    participant_expected: dict[str, int] = defaultdict(int)
    for row in rows:
        participant = str(row["participant_id"])
        event = EventInterval(int(row["start_ms"]), int(row["end_ms"]))
        candidates = labels_by_participant.get(participant, [])
        dense_count = sum(start < event.end_ms and end > event.start_ms for start, end, _ in candidates)
        positive_count = sum(
            label_window(
                EventInterval(start, end),
                (event,),
                positive_overlap=0.5,
            ).label.value == "positive"
            for start, end, _ in candidates
        )
        label_eligible = bool(row["training_eligibility"])
        positive_representable = label_eligible and positive_count > 0
        if label_eligible:
            participant_expected[participant] += 1
            if positive_representable:
                positive_eligible_count += 1
                participant_positive[participant] += 1
        if row["annotation_quality_status"] == "SHORT_DURATION_SUSPECT" and positive_count > 0:
            short_positive_count += 1
        audit_rows.append(
            {
                "participant_id": participant,
                "event_index": int(row["event_index"]),
                "annotation_status": row["annotation_status"],
                "sensor_status": row["sensor_status"],
                "representability_status": row["representability_status"],
                "annotation_quality_status": row["annotation_quality_status"],
                "training_eligibility": label_eligible,
                "dense_window_count": int(dense_count),
                "positive_window_count": int(positive_count),
                "positive_representable": bool(positive_representable),
                "unrepresentable_reason": row["unrepresentable_reason"],
                "exclusion_reason": row["exclusion_reason"],
            }
        )

    expected = int(eligibility["sensor_backed_event_count"])
    representable = int(eligibility["representable_event_count"])
    payload: dict[str, object] = {
        "schema_version": "event_representability_audit_v1",
        "eligibility_schema_version": eligibility["schema_version"],
        "eligibility_contract_hash": eligibility["eligibility_contract_hash"],
        "cache_file_count": cache_files,
        "window_length_seconds": 15.0,
        "stride_seconds": 7.5,
        "positive_overlap": 0.5,
        "window_label_counts": {
            "positive": aggregate[1],
            "negative": aggregate[0],
            "ignore": aggregate[-1],
        },
        "annotated_event_count": int(eligibility["annotated_event_count"]),
        "sensor_backed_event_count": expected,
        "representable_event_count": representable,
        "label_eligible_event_count": int(eligibility["label_eligible_event_count"]),
        "positive_candidate_event_count": positive_eligible_count,
        "event_representability": {
            "numerator_positive_candidate_events": positive_eligible_count,
            "denominator_sensor_backed_events": expected,
            "fraction": positive_eligible_count / expected if expected else 0.0,
        },
        "positive_coverage_among_representable_events": {
            "numerator": positive_eligible_count,
            "denominator": representable,
            "fraction": positive_eligible_count / representable if representable else 0.0,
        },
        "short_suspect_positive_event_count": short_positive_count,
        "participant_level_label_coverage": {
            participant: {
                "positive_representable_events": participant_positive[participant],
                "label_eligible_events": participant_expected[participant],
                "fraction": participant_positive[participant] / participant_expected[participant]
                if participant_expected[participant]
                else None,
            }
            for participant in sorted(participant_expected)
        },
        "event_audit": audit_rows,
    }
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eligibility", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--meal-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = audit_event_representability(
        eligibility_path=args.eligibility,
        cache_dir=args.cache_dir,
        meal_metadata_path=args.meal_metadata,
        output_path=args.output,
    )
    print(json.dumps({
        "result": "pass",
        "annotated_event_count": payload["annotated_event_count"],
        "representable_event_count": payload["representable_event_count"],
        "positive_candidate_event_count": payload["positive_candidate_event_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
