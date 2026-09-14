"""Versioned candidate-table cache serialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from eating_event.candidates import CandidateTable
from eating_event.data.labels import WindowLabel, WindowLabelResult
from eating_event.data.windows import WindowRecord, WindowSpec


def build_cache_key(
    source_fingerprint: str,
    window_seconds: float,
    step_seconds: float,
    feature_schema_version: str,
    label_schema_version: str,
) -> str:
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


def _metadata_json(metadata: Mapping[str, object]) -> str:
    return json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def save_candidate_table(
    path: str | Path,
    table: CandidateTable,
    *,
    metadata: Mapping[str, object],
) -> None:
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    features = np.asarray(table.features, dtype=np.float32)
    labels = np.asarray(table.labels, dtype=np.int8)
    if features.ndim != 2 or labels.ndim != 1 or features.shape[0] != labels.size:
        raise ValueError("candidate table features and labels are misaligned")
    if len(table.windows) != labels.size:
        raise ValueError("candidate table windows are misaligned")
    starts = np.asarray([record.window.start_ms for record in table.windows], dtype=np.int64)
    ends = np.asarray([record.window.end_ms for record in table.windows], dtype=np.int64)
    coverage = np.asarray([record.coverage for record in table.windows], dtype=np.float32)
    invalid_runs = np.asarray([record.longest_invalid_run for record in table.windows], dtype=np.int32)
    crosses_gap = np.asarray([record.crosses_hard_gap for record in table.windows], dtype=bool)
    participant_ids = np.asarray(table.participant_ids, dtype=str)
    if participant_ids.size != labels.size:
        raise ValueError("candidate table participant identifiers are misaligned")
    if table.session_ids is None:
        session_ids = np.full(labels.size, "", dtype=str)
    else:
        session_ids = np.asarray(table.session_ids, dtype=str)
        if session_ids.size != labels.size:
            raise ValueError("candidate table session identifiers are misaligned")
    with destination.open("wb") as stream:
        np.savez_compressed(
            stream,
            features=features,
            feature_names=np.asarray(json.dumps(table.feature_names), dtype=object),
            labels=labels,
            starts=starts,
            ends=ends,
            coverage=coverage,
            invalid_runs=invalid_runs,
            crosses_gap=crosses_gap,
            participant_ids=participant_ids,
            session_ids=session_ids,
            metadata=np.asarray(_metadata_json(metadata), dtype=object),
        )


def load_candidate_table(
    path: str | Path,
    *,
    expected_metadata: Mapping[str, object] | None = None,
) -> CandidateTable:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"candidate cache does not exist: {source}")
    try:
        payload = np.load(source, allow_pickle=True)
        metadata = json.loads(str(payload["metadata"].item()))
        if expected_metadata is not None and metadata != dict(expected_metadata):
            raise ValueError("candidate cache metadata mismatch")
        labels = payload["labels"].astype(np.int8, copy=False)
        features = payload["features"].astype(np.float32, copy=False)
        names = tuple(json.loads(str(payload["feature_names"].item())))
        participant_ids = payload["participant_ids"].astype(str, copy=False)
        session_ids = payload["session_ids"].astype(str, copy=False)
        crosses_gap = payload["crosses_gap"].astype(bool, copy=False)
        windows: list[WindowRecord] = []
        label_map = {1: WindowLabel.POSITIVE, 0: WindowLabel.NEGATIVE, -1: WindowLabel.IGNORE}
        for start, end, cov, invalid_run, label, crossed in zip(
            payload["starts"],
            payload["ends"],
            payload["coverage"],
            payload["invalid_runs"],
            labels,
            crosses_gap,
        ):
            if int(label) not in label_map:
                raise ValueError("candidate cache contains invalid label")
            windows.append(
                WindowRecord(
                    window=WindowSpec(int(start), int(end)),
                    coverage=float(cov),
                    longest_invalid_run=int(invalid_run),
                    label_result=WindowLabelResult(label_map[int(label)], 0.0, None),
                    crosses_hard_gap=bool(crossed),
                )
            )
        if features.ndim != 2 or features.shape[0] != labels.size:
            raise ValueError("candidate cache features are malformed")
        return CandidateTable(
            features=features,
            feature_names=names,
            labels=labels,
            participant_ids=participant_ids.astype(object),
            windows=tuple(windows),
            session_ids=session_ids.astype(object),
        )
    except KeyError as exc:
        raise ValueError(f"candidate cache schema missing field: {exc.args[0]}") from exc
