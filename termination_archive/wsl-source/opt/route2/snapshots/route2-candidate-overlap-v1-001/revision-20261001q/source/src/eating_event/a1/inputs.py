"""Read-only, hash-checked A1 inputs.

Raw sensor paths in the historical manifests are deliberately treated as opaque
identifiers. This module never opens, stats, or resolves those paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from eating_event.a1.contracts import A1Config, WINDOW_FEATURE_DIM, WindowIdentity, stable_hash
from eating_event.metrics import EventInterval


@dataclass(frozen=True)
class A1Window:
    identity: WindowIdentity
    start_ms: int
    end_ms: int
    coverage: float
    crosses_hard_gap: bool
    features: object
    label: int
    session_start_ms: int
    session_end_ms: int
    boundary_kind: str = "index_bounds"

    def __post_init__(self) -> None:
        if self.end_ms <= self.start_ms:
            raise ValueError("window end must be after start")
        if not 0 <= self.coverage <= 1:
            raise ValueError("window coverage must be in [0, 1]")
        if self.label not in {-1, 0, 1}:
            raise ValueError("window label must be -1, 0, or 1")
        if self.boundary_kind not in {"index_bounds", "observed_window_support_component_v1"}:
            raise ValueError("unknown boundary kind")
        if self.boundary_kind == "index_bounds" and (self.start_ms < self.session_start_ms or self.end_ms > self.session_end_ms):
            raise ValueError("window is outside session bounds")
        values = np.asarray(self.features, dtype=np.float32)
        if values.shape != (WINDOW_FEATURE_DIM,):
            raise ValueError(f"window features must have shape ({WINDOW_FEATURE_DIM},)")
        if not np.isfinite(values).all():
            raise ValueError("window features must be finite")


@dataclass(frozen=True)
class TruthRecord:
    event_id: str
    participant_id: str
    interval: EventInterval


@dataclass(frozen=True)
class InputBundle:
    windows: tuple[A1Window, ...]
    truths: Mapping[str, tuple[TruthRecord, ...]]
    manifest_entries: tuple[Mapping[str, object], ...]
    manifest_audit: Mapping[str, object]
    eligibility: Mapping[str, object]
    source_hashes: Mapping[str, str]
    identity_audit: tuple[Mapping[str, object], ...] = ()
    label_changes: tuple[Mapping[str, object], ...] = ()
    training_truths: Mapping[str, tuple[TruthRecord, ...]] = field(default_factory=dict)

    @property
    def participants(self) -> tuple[str, ...]:
        return tuple(sorted({str(entry["participant_id"]) for entry in self.manifest_entries}))

    @property
    def windows_by_participant(self) -> dict[str, tuple[A1Window, ...]]:
        result: dict[str, list[A1Window]] = {}
        for window in self.windows:
            result.setdefault(window.identity.participant_id, []).append(window)
        return {key: tuple(value) for key, value in result.items()}


def _read_json(path: Path, *, name: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read A1 {name}: {path}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_from_config(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _cache_path_allowed(path: Path, cache_root: Path) -> bool:
    try:
        path.resolve().relative_to(cache_root.resolve())
        return True
    except ValueError:
        return False


def _load_truths(eligibility: Mapping[str, object], eligibility_field: str = "evaluation_eligibility") -> dict[str, tuple[TruthRecord, ...]]:
    rows = eligibility.get("event_eligibility")
    if not isinstance(rows, list):
        raise ValueError("eligibility artifact lacks event_eligibility")
    by_participant: dict[str, dict[str, TruthRecord]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("eligibility event row must be an object")
        if not bool(row.get(eligibility_field)):
            continue
        participant = str(row.get("participant_id", ""))
        if not participant:
            raise ValueError("eligibility event row missing participant_id")
        try:
            event_index = int(row["event_index"])
            start_ms = int(row["start_ms"])
            end_ms = int(row["end_ms"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("eligibility event row missing canonical identity/bounds") from exc
        event_id = f"{participant}:{event_index}"
        record = TruthRecord(event_id, participant, EventInterval(start_ms, end_ms))
        existing = by_participant.setdefault(participant, {}).get(event_id)
        if existing is not None and existing != record:
            raise ValueError(f"conflicting canonical event identity: {event_id}")
        by_participant[participant][event_id] = record
    return {
        participant: tuple(sorted(events.values(), key=lambda item: item.event_id))
        for participant, events in by_participant.items()
    }


def load_inputs(root: str | Path, config: A1Config) -> InputBundle:
    """Load and validate the approved cache/ledger inputs without raw I/O."""

    base = Path(root).expanduser().resolve()
    paths = {
        key: _path_from_config(base, value)
        for key, value in config.paths.items()
        if isinstance(value, str)
    }
    required = {"cache_manifest", "manifest_audit", "eligibility", "cache_root"}
    missing = sorted(required - set(paths))
    if missing:
        raise ValueError(f"missing A1 input paths: {missing}")
    cache_manifest = _read_json(paths["cache_manifest"], name="cache manifest")
    manifest_audit = _read_json(paths["manifest_audit"], name="manifest audit")
    eligibility = _read_json(paths["eligibility"], name="eligibility")
    if not isinstance(cache_manifest, dict) or not isinstance(cache_manifest.get("entries"), list):
        raise ValueError("cache manifest must contain entries")
    if not isinstance(manifest_audit, dict) or not isinstance(manifest_audit.get("records"), list):
        raise ValueError("manifest audit must contain records")
    if not isinstance(eligibility, dict) or eligibility.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("A1 requires participant_eligibility_v3")
    if "label_eligible_event_denominator_sha256" not in eligibility:
        raise ValueError("eligibility artifact lacks label-eligible denominator hash")

    cache_root = paths["cache_root"]
    audit_records = {
        str(row.get("path_or_file_id")): row
        for row in manifest_audit["records"]
        if isinstance(row, dict) and row.get("path_or_file_id")
    }
    audit_keys = [str(row["path_or_file_id"]) for row in manifest_audit["records"] if isinstance(row, dict) and row.get("path_or_file_id")]
    if len(audit_keys) != len(set(audit_keys)):
        raise ValueError("duplicate audit path")
    training_truths = _load_truths(eligibility, "training_eligibility")
    identity_audit, label_changes = [], []
    seen_cache_paths, seen_cache_hashes, seen_sessions = set(), set(), set()
    all_windows: list[A1Window] = []
    source_hashes: dict[str, str] = {}
    seen_ids: set[str] = set()
    seen_records: set[tuple[str, str]] = set()
    for entry in cache_manifest["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("cache manifest entry must be an object")
        participant = str(entry.get("participant_id", ""))
        session_id = str(entry.get("session_id", ""))
        opaque_path = str(entry.get("path", entry.get("path_or_file_id", "")))
        if not participant:
            raise ValueError("cache entry missing participant_id")
        if not session_id:
            raise ValueError("cache entry missing session_id")
        audit = audit_records.get(opaque_path)
        if audit is None:
            raise ValueError(f"cache entry not present in manifest audit: {opaque_path}")
        if str(audit.get("participant_id", "")) != participant:
            raise ValueError("audit participant mismatch")
        if str(audit.get("session_id", "")) != session_id:
            raise ValueError("cache/session identity mismatch")
        if str(audit.get("status")) != "processed":
            raise ValueError("cache entry does not reference a processed manifest record")
        try:
            session_start = int(audit["session_start_ms"])
            session_end = int(audit["session_end_ms"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("manifest audit record lacks session bounds") from exc
        cache_path = _path_from_config(base, str(entry.get("cache_path", "")))
        if not _cache_path_allowed(cache_path, cache_root):
            raise ValueError("cache path is outside approved cache root")
        if not cache_path.is_file():
            raise ValueError(f"approved cache file is missing: {cache_path}")
        declared_hash = str(entry.get("cache_sha256", ""))
        actual_hash = _sha256_file(cache_path)
        if not declared_hash or actual_hash != declared_hash:
            raise ValueError(f"cache hash mismatch: {cache_path.name}")
        for seen, key in ((seen_cache_paths, str(cache_path.resolve())), (seen_cache_hashes, actual_hash), (seen_sessions, (participant, session_id))):
            if key in seen:
                raise ValueError("duplicate cache/session identity")
            seen.add(key)
        source_hashes[f"cache:{cache_path.name}"] = actual_hash
        with np.load(cache_path, allow_pickle=True) as payload:
            required_arrays = {
                "features",
                "labels",
                "starts",
                "ends",
                "coverage",
                "crosses_gap",
                "participant_ids",
                "session_ids",
            }
            absent = sorted(required_arrays - set(payload.files))
            if absent:
                raise ValueError(f"cache schema missing fields: {absent}")
            features = np.asarray(payload["features"], dtype=np.float32)
            labels = np.asarray(payload["labels"], dtype=np.int8)
            starts = np.asarray(payload["starts"], dtype=np.int64)
            ends = np.asarray(payload["ends"], dtype=np.int64)
            coverage = np.asarray(payload["coverage"], dtype=np.float32)
            crosses_gap = np.asarray(payload["crosses_gap"], dtype=bool)
            participants = np.asarray(payload["participant_ids"]).astype(str)
            sessions = np.asarray(payload["session_ids"]).astype(str)
            n = labels.size
            if features.shape != (n, WINDOW_FEATURE_DIM):
                raise ValueError("cache features must have shape [W, 111]")
            arrays = (starts, ends, coverage, crosses_gap, participants, sessions)
            if any(array.size != n for array in arrays):
                raise ValueError("cache arrays are not aligned")
            if not np.isfinite(features).all() or not np.isfinite(coverage).all():
                raise ValueError("cache contains non-finite values")
            if not np.isin(labels, (-1, 0, 1)).all():
                raise ValueError("cache labels must be in {-1, 0, 1}")
            revised = config.d3_revision == "D3-Ready-v1"
            if np.any(ends <= starts) or np.any(np.diff(starts) < 0):
                raise ValueError("invalid window times")
            if np.any(crosses_gap) or np.any(coverage < .8) or np.any(payload["invalid_runs"] > 20):
                raise ValueError("cache quality violation")
            if not revised and (np.any(starts < session_start) or np.any(ends > session_end)):
                raise ValueError("cache window bounds violate session bounds")
            if not np.array_equal(participants, np.full(n, participant)):
                raise ValueError("cache participant identity mismatch")
            if not np.array_equal(sessions, np.full(n, session_id)) and not (revised and np.all(sessions == "")):
                observed = sorted(set(sessions.tolist()))[:3]
                raise ValueError(
                    f"cache session identity mismatch for {participant}/{session_id} in "
                    f"{cache_path.name}: observed={observed}"
                )
            record_id = str(entry.get("record_id") or cache_path.stem)
            if revised:
                metadata = json.loads(str(payload["metadata"].item()))
                if metadata.get("cache_key") != cache_path.stem or record_id != cache_path.stem:
                    raise ValueError("cache metadata key mismatch")
            identity_audit.append(dict(record_id=record_id, participant_id=participant, session_id=session_id,
                                       cache_sha256=actual_hash, opaque_path=opaque_path,
                                       index_start_ms=session_start, index_end_ms=session_end,
                                       session_identity_source="approved_cache_manifest_v1" if revised else "cache",
                                       boundary_kind="observed_window_support_component_v1" if revised else "index_bounds",
                                       source_segment_id=None,
                                       outside_windows=int(((starts < session_start) | (ends > session_end)).sum())))
            if revised:
                overlap = np.zeros(n, dtype=np.int64)
                distance = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
                for truth in training_truths.get(participant, ()):
                    a, b = truth.interval.start_ms, truth.interval.end_ms
                    overlap = np.maximum(overlap, np.maximum(0, np.minimum(ends,b)-np.maximum(starts,a)))
                    distance = np.minimum(distance, np.maximum(0, np.maximum(a-ends, starts-b)))
                revised_labels = np.where(overlap*2 >= ends-starts, 1, np.where(distance >= 300000, 0, -1)).astype(np.int8)
                for idx in np.flatnonzero(labels != revised_labels):
                    label_changes.append(dict(stable_window_id=WindowIdentity(participant,record_id,session_id,int(idx)).stable_id,
                                              old_label=int(labels[idx]), new_label=int(revised_labels[idx]),
                                              schema="participant_training_truth_labels_v1"))
                labels = revised_labels
            record_key = (record_id, session_id)
            if record_key in seen_records:
                raise ValueError(f"duplicate cache record identity: {record_key}")
            seen_records.add(record_key)
            for row_index in range(n):
                identity = WindowIdentity(participant, record_id, session_id, row_index)
                if identity.stable_id in seen_ids:
                    raise ValueError(f"duplicate stable window identity: {identity.stable_id}")
                seen_ids.add(identity.stable_id)
                all_windows.append(
                    A1Window(
                        identity=identity,
                        start_ms=int(starts[row_index]),
                        end_ms=int(ends[row_index]),
                        coverage=float(coverage[row_index]),
                        crosses_hard_gap=bool(crosses_gap[row_index]),
                        features=features[row_index],
                        label=int(labels[row_index]),
                        session_start_ms=session_start,
                        session_end_ms=session_end,
                        boundary_kind="observed_window_support_component_v1" if revised else "index_bounds",
                    )
                )
    truths = _load_truths(eligibility)
    expected_count = eligibility.get("label_eligible_event_count")
    if expected_count is not None and sum(len(items) for items in truths.values()) != int(expected_count):
        raise ValueError("canonical eligible event count mismatch")
    if expected_count is not None and int(expected_count) != 234:
        raise ValueError("A1 requires 234 canonical eligible events")
    source_hashes["cache_manifest"] = _sha256_file(paths["cache_manifest"])
    source_hashes["manifest_audit"] = _sha256_file(paths["manifest_audit"])
    source_hashes["eligibility"] = _sha256_file(paths["eligibility"])
    source_hashes["eligibility_declared_denominator"] = str(
        eligibility["label_eligible_event_denominator_sha256"]
    )
    return InputBundle(
        windows=tuple(all_windows),
        truths=truths,
        manifest_entries=tuple(cache_manifest["entries"]),
        manifest_audit=manifest_audit,
        eligibility=eligibility,
        source_hashes=source_hashes,
        identity_audit=tuple(identity_audit), label_changes=tuple(label_changes), training_truths=training_truths,
    )
