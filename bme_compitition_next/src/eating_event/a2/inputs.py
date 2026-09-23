"""Safe readers and structural checks for the approved A1-derived inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_approved_path(workspace: str | Path, value: str | Path, approved_root: str | Path) -> Path:
    root = Path(workspace).resolve()
    allowed = Path(approved_root)
    if not allowed.is_absolute():
        allowed = root / allowed
    allowed = allowed.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("input path is outside the approved root") from exc
    return path


def authenticate_checksum_manifest(
    manifest_path: str | Path,
    artifact_root: str | Path,
    expected_manifest_sha256: str,
) -> dict[str, str]:
    path = Path(manifest_path)
    if sha256_file(path) != expected_manifest_sha256:
        raise ValueError("final checksum manifest hash mismatch")
    root = Path(artifact_root).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("final checksum manifest must be an object")
    entries = payload.get("files", payload)
    if not isinstance(entries, dict) or not entries:
        raise ValueError("final checksum manifest has no file entries")
    result: dict[str, str] = {}
    for name, declared in entries.items():
        relative = Path(str(name))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("final checksum entry is outside the A1 artifact root")
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("final checksum entry is outside the A1 artifact root") from exc
        if not target.is_file() or sha256_file(target) != str(declared):
            raise ValueError(f"listed artifact hash mismatch: {relative.as_posix()}")
        result[relative.as_posix()] = str(declared)
    return result


def validate_a1_code_identity(code_identity: Mapping[str, str], workspace: str | Path) -> None:
    root = Path(workspace).resolve()
    if not isinstance(code_identity, Mapping) or not code_identity:
        raise ValueError("A1 registered code identity must be a nonempty path map")
    for name, declared in code_identity.items():
        relative = Path(str(name))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("registered A1 code path escaped workspace")
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("registered A1 code path escaped workspace") from exc
        if not target.is_file() or sha256_file(target) != str(declared):
            raise ValueError(f"registered A1 code hash mismatch: {relative.as_posix()}")


def validate_score_payload(
    ids: object,
    raw: object,
    relative: object,
    expected_ids: Sequence[int],
    *,
    threshold: float,
) -> None:
    ids_array = np.asarray(ids)
    raw_array = np.asarray(raw)
    relative_array = np.asarray(relative)
    if ids_array.ndim != 1 or not np.issubdtype(ids_array.dtype, np.integer):
        raise ValueError("score IDs must be an integer vector")
    expected = np.asarray(expected_ids, dtype=np.int64)
    if expected.ndim != 1 or expected.size != np.unique(expected).size or np.any(expected < 0):
        raise ValueError("expected score IDs are not a unique nonnegative vector")
    if ids_array.size != np.unique(ids_array).size or np.any(ids_array < 0):
        raise ValueError("score IDs contain duplicates or out-of-range positions")
    if not np.array_equal(ids_array.astype(np.int64, copy=False), expected):
        raise ValueError("score IDs do not exactly match ordered scored-participant windows")
    if raw_array.ndim != 1 or relative_array.ndim != 1 or raw_array.shape != ids_array.shape or relative_array.shape != ids_array.shape:
        raise ValueError("score arrays are not aligned")
    if not np.issubdtype(raw_array.dtype, np.number) or not np.issubdtype(relative_array.dtype, np.number):
        raise ValueError("score arrays must be numeric")
    if not np.isfinite(raw_array).all() or not np.isfinite(relative_array).all() or not np.isfinite(threshold):
        raise ValueError("score arrays must be finite")
    if not np.array_equal(relative_array, raw_array - float(threshold)):
        raise ValueError("relative scores are not exactly raw minus threshold")


def validate_score_provenance(actual: Mapping[str, object], expected: Mapping[str, object]) -> None:
    for key in ("role_id", "model_hash", "fit_signature"):
        if not actual.get(key) or actual.get(key) != expected.get(key):
            raise ValueError(f"score provenance conflict for {key}")
    for key in ("model_hash", "fit_signature"):
        value = str(actual[key])
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise ValueError(f"score provenance conflict for invalid {key}")


def check_candidate_rows(rows: Sequence[Mapping[str, object]]) -> None:
    seen: set[tuple[str, str]] = set()
    for row in rows:
        role_id = str(row.get("role_id", ""))
        candidate_id = str(row.get("candidate_id", ""))
        if not role_id or not candidate_id:
            raise ValueError("candidate identity requires role_id and candidate_id")
        key = (role_id, candidate_id)
        if key in seen:
            raise ValueError(f"duplicate composite candidate identity: {role_id}/{candidate_id}")
        seen.add(key)


def _stable_window_id(identity: Mapping[str, object]) -> str:
    fields = ("participant_id", "record_id", "session_id", "row_index")
    if any(field not in identity for field in fields):
        raise ValueError("support identity is incomplete")
    return "|".join(str(identity[field]) for field in fields)


def validate_support_identity(
    candidate: Mapping[str, object],
    *,
    role_id: str,
    stable_ids: set[str],
    component_by_stable_id: Mapping[str, str],
) -> None:
    if str(candidate.get("role_id", "")) != role_id:
        raise ValueError("candidate support role mismatch")
    component_id = str(candidate.get("component_id", ""))
    support = candidate.get("support_indices")
    if not component_id or not isinstance(support, list) or not support:
        raise ValueError("candidate support/component is missing")
    seen: set[str] = set()
    for item in support:
        if not isinstance(item, Mapping):
            raise ValueError("candidate support identity is malformed")
        stable_id = _stable_window_id(item)
        if stable_id in seen or stable_id not in stable_ids or component_by_stable_id.get(stable_id) != component_id:
            raise ValueError("candidate support is outside role/component")
        seen.add(stable_id)


def validate_outer_label(candidate: Mapping[str, object], *, outer_role: bool) -> None:
    label = candidate.get("label")
    if outer_role and label is not None:
        raise ValueError("outer candidate label must be null")
    if not outer_role and label not in (0, 1):
        raise ValueError("training/inner candidate label must be binary")


def validate_outer_exclusion(
    *,
    fit_participants: Sequence[str],
    reference_participants: Sequence[str],
    selection_participants: Sequence[str],
    outer_valid_participants: Sequence[str],
) -> None:
    outer = set(map(str, outer_valid_participants))
    for name, values in (
        ("fit", fit_participants),
        ("reference", reference_participants),
        ("selection", selection_participants),
    ):
        overlap = outer.intersection(map(str, values))
        if overlap:
            raise ValueError(f"outer-valid participant overlap in {name}: {sorted(overlap)}")
