"""Hash-bound, no-fit authentication and materialization of the A2 inputs."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eating_event.a1.boundaries import build_support_components
from eating_event.a1.contracts import WindowIdentity, canonical_json as a1_canonical_json
from eating_event.a1.inputs import A1Window, TruthRecord
from eating_event.a1.pipeline import Role, build_role_graph, validate_role_graph
from eating_event.a2.budget import StudyResourceError, require_environment
from eating_event.a2.contracts import (
    A2_CONFIG,
    A2FeatureRow,
    CandidateKey,
    ContextWindow,
    DEFAULT_STUDY_ID,
    load_config,
    validate_study_binding,
)
from eating_event.a2.features import build_a2_features
from eating_event.a2.inputs import (
    authenticate_checksum_manifest,
    check_candidate_rows,
    resolve_approved_path,
    sha256_file,
    validate_a1_code_identity,
    validate_outer_exclusion,
    validate_outer_label,
    validate_score_payload,
    validate_score_provenance,
    validate_support_identity,
)
from eating_event.metrics import EventInterval, interval_iou


class VerifierDataInsufficient(ValueError):
    """A frozen verifier role cannot satisfy the pre-fit G3 contract."""


class InvalidA2Source(ValueError):
    """The approved A1 identity or data contract does not authenticate."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise InvalidA2Source(f"JSONL row {number} is not an object: {path.name}")
            rows.append(value)
    return rows


def current_a2_code_identity(workspace: str | Path) -> dict[str, str]:
    root = Path(workspace).resolve()
    paths = sorted((root / "src" / "eating_event" / "a2").glob("*.py"))
    paths += sorted((root / "scripts").glob("run_a2_context_verifier*.py"))
    paths += sorted((root / "tests").glob("test_a2_*.py"))
    result: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_file(path)
    if not result:
        raise InvalidA2Source("A2 code identity is empty")
    return result


def _role_from_row(row: Mapping[str, object]) -> Role:
    tuple_fields = ("fit_participants", "reference_participants", "scored_participants", "selection_participants", "outer_valid", "thresholds")
    values = dict(row)
    for field in tuple_fields:
        values[field] = tuple(values.get(field, ()))
    return Role(**values)  # type: ignore[arg-type]


def _role_json(role: Role) -> dict[str, object]:
    return {key: list(value) if isinstance(value, tuple) else value for key, value in asdict(role).items()}


def _environment_identity() -> dict[str, object]:
    import importlib.metadata
    import platform

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "libraries": {
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "scikit-learn": importlib.metadata.version("scikit-learn"),
            "psutil": importlib.metadata.version("psutil"),
        },
    }


_EXPECTED_ENVIRONMENT = {
    "python": "3.10.11",
    "libraries": {
        "numpy": "2.2.6",
        "scipy": "1.15.3",
        "scikit-learn": "1.7.2",
        "psutil": "7.2.2",
    },
}


def _assert_workspace_artifact(root: Path, value: object, *, name: str, directory: bool = False) -> Path:
    if not isinstance(value, str) or not value:
        raise InvalidA2Source(f"A1 config path is missing: {name}")
    artifacts_root = root / "artifacts"
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(artifacts_root.resolve())
    except ValueError as exc:
        raise InvalidA2Source(f"A1 {name} is outside approved derived artifacts") from exc
    if directory and not resolved.is_dir():
        raise InvalidA2Source(f"approved A1 {name} directory is unavailable")
    if not directory and not resolved.is_file():
        raise InvalidA2Source(f"approved A1 {name} file is unavailable")
    return resolved


def _load_eligibility(path: Path, expected_sha: str, expected_denominator_sha: str) -> tuple[dict[str, tuple[TruthRecord, ...]], dict[str, tuple[TruthRecord, ...]], tuple[str, ...], dict[str, object]]:
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise InvalidA2Source("approved eligibility file hash mismatch")
    payload = _read_json(path)
    if not isinstance(payload, dict) or payload.get("schema_version") != "participant_eligibility_v3":
        raise InvalidA2Source("approved eligibility schema mismatch")
    if payload.get("label_eligible_event_denominator_sha256") != expected_denominator_sha:
        raise InvalidA2Source("approved canonical denominator hash mismatch")
    rows = payload.get("event_eligibility")
    if not isinstance(rows, list):
        raise InvalidA2Source("approved eligibility rows are missing")
    evaluation: dict[str, dict[str, TruthRecord]] = {}
    training: dict[str, dict[str, TruthRecord]] = {}
    participant_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise InvalidA2Source("eligibility event row is malformed")
        participant = str(row.get("participant_id", ""))
        if not participant:
            raise InvalidA2Source("eligibility participant is missing")
        evaluation_eligible = bool(row.get("evaluation_eligibility"))
        training_eligible = bool(row.get("training_eligibility"))
        if evaluation_eligible or training_eligible:
            participant_ids.add(participant)
        if not evaluation_eligible and not training_eligible:
            continue
        try:
            event_index = int(row["event_index"])
            start_ms = int(row["start_ms"])
            end_ms = int(row["end_ms"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidA2Source("eligible event identity/bounds are invalid") from exc
        if end_ms <= start_ms:
            raise InvalidA2Source("eligible event interval is empty")
        event_id = f"{participant}:{event_index}"
        item = TruthRecord(event_id, participant, EventInterval(start_ms, end_ms))
        if bool(row.get("evaluation_eligibility")):
            prior = evaluation.setdefault(participant, {}).get(event_id)
            if prior is not None and prior != item:
                raise InvalidA2Source("conflicting eligible evaluation event")
            evaluation[participant][event_id] = item
        if bool(row.get("training_eligibility")):
            prior = training.setdefault(participant, {}).get(event_id)
            if prior is not None and prior != item:
                raise InvalidA2Source("conflicting eligible training event")
            training[participant][event_id] = item
    evaluation_rows = {p: tuple(sorted(rows.values(), key=lambda row: row.event_id)) for p, rows in evaluation.items()}
    training_rows = {p: tuple(sorted(rows.values(), key=lambda row: row.event_id)) for p, rows in training.items()}
    if sum(map(len, evaluation_rows.values())) != 234:
        raise InvalidA2Source("approved evaluation cohort is not 234 canonical GT")
    return evaluation_rows, training_rows, tuple(sorted(participant_ids)), payload


def validate_eligible_gt_participants(
    event_rows: Sequence[Mapping[str, object]],
    cache_participants: Sequence[str] | set[str],
) -> tuple[str, ...]:
    """Require only training/evaluation-eligible canonical GT people in cache."""

    eligible: set[str] = set()
    for row in event_rows:
        participant = str(row.get("participant_id", ""))
        if not participant:
            raise InvalidA2Source("eligibility participant is missing")
        if bool(row.get("evaluation_eligibility")) or bool(row.get("training_eligibility")):
            eligible.add(participant)
    outside = eligible - set(map(str, cache_participants))
    if outside:
        raise InvalidA2Source(f"eligible canonical GT participant outside approved cache population: {sorted(outside)}")
    return tuple(sorted(eligible))


def index_approved_manifest_records(
    audit_records: Sequence[Mapping[str, object]],
    cache_entries: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    """Index nonempty opaque IDs, then bind each cache entry to one processed row."""

    indexed: dict[str, Mapping[str, object]] = {}
    for row in audit_records:
        if not isinstance(row, Mapping):
            raise InvalidA2Source("approved record audit row is malformed")
        status = str(row.get("status", ""))
        opaque_value = row.get("path_or_file_id")
        if opaque_value is None or opaque_value == "":
            if status == "processed":
                raise InvalidA2Source("processed manifest audit identity is missing")
            continue
        opaque = str(opaque_value)
        if not opaque.strip():
            if status == "processed":
                raise InvalidA2Source("processed manifest audit identity is empty")
            continue
        if opaque in indexed:
            raise InvalidA2Source("duplicate nonempty manifest audit identity")
        indexed[opaque] = row

    referenced: set[str] = set()
    for entry in cache_entries:
        if not isinstance(entry, Mapping):
            raise InvalidA2Source("approved cache manifest entry is malformed")
        opaque_value = entry.get("path", entry.get("path_or_file_id"))
        if opaque_value is None or opaque_value == "" or not str(opaque_value).strip():
            raise InvalidA2Source("approved cache entry has no manifest audit identity")
        opaque = str(opaque_value)
        if opaque in referenced:
            raise InvalidA2Source("duplicate cache reference to one manifest audit identity")
        referenced.add(opaque)
        row = indexed.get(opaque)
        if row is None:
            raise InvalidA2Source(f"cache entry is absent from approved manifest audit: {opaque}")
        if str(row.get("status", "")) != "processed":
            raise InvalidA2Source("cache entry must map to a processed manifest audit record")
        if str(row.get("participant_id", "")) != str(entry.get("participant_id", "")):
            raise InvalidA2Source("cache/manifest participant identity mismatch")
        if str(row.get("session_id", "")) != str(entry.get("session_id", "")):
            raise InvalidA2Source("cache/manifest session identity mismatch")
    return indexed


def _load_cache_geometry(
    root: Path,
    cache_manifest_path: Path,
    manifest_audit_path: Path,
    cache_root: Path,
) -> tuple[list[dict[str, object]], dict[str, str], str, str]:
    manifest = _read_json(cache_manifest_path)
    audit = _read_json(manifest_audit_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        raise InvalidA2Source("approved cache manifest is malformed")
    if not isinstance(audit, dict) or not isinstance(audit.get("records"), list):
        raise InvalidA2Source("approved record audit is malformed")
    audit_by_opaque = index_approved_manifest_records(audit["records"], manifest["entries"])
    geometry: list[dict[str, object]] = []
    cache_hashes: dict[str, str] = {}
    seen_sessions: set[tuple[str, str]] = set()
    for entry in manifest["entries"]:
        if not isinstance(entry, dict):
            raise InvalidA2Source("approved cache manifest entry is malformed")
        participant = str(entry.get("participant_id", ""))
        session = str(entry.get("session_id", ""))
        opaque_value = entry.get("path", entry.get("path_or_file_id"))
        opaque = "" if opaque_value is None else str(opaque_value)
        cache_value = str(entry.get("cache_path", ""))
        if not participant or not session or not opaque or not cache_value:
            raise InvalidA2Source("approved cache identity is incomplete")
        audit_record = audit_by_opaque.get(opaque)
        if audit_record is None or audit_record.get("participant_id") != participant or audit_record.get("session_id") != session or audit_record.get("status") != "processed":
            raise InvalidA2Source("approved cache record/participant/session mapping mismatch")
        cache_path = resolve_approved_path(root, cache_value, cache_root)
        declared = str(entry.get("cache_sha256", ""))
        actual = sha256_file(cache_path)
        if not declared or declared != actual:
            raise InvalidA2Source("approved cache hash mismatch")
        cache_hashes[cache_path.relative_to(root).as_posix()] = actual
        record_id = str(entry.get("record_id") or cache_path.stem)
        session_key = (participant, session)
        if session_key in seen_sessions:
            raise InvalidA2Source("duplicate participant/session cache identity")
        seen_sessions.add(session_key)
        with np.load(cache_path, allow_pickle=False) as content:
            required = {"starts", "ends", "coverage", "crosses_gap"}
            if not required <= set(content.files):
                raise InvalidA2Source("approved cache lacks safe numeric time/coverage arrays")
            starts = np.asarray(content["starts"])
            ends = np.asarray(content["ends"])
            coverage = np.asarray(content["coverage"])
            crosses_gap = np.asarray(content["crosses_gap"])
        if starts.ndim != 1 or ends.shape != starts.shape or coverage.shape != starts.shape or crosses_gap.shape != starts.shape:
            raise InvalidA2Source("approved cache numeric arrays are misaligned")
        if not np.issubdtype(starts.dtype, np.integer) or not np.issubdtype(ends.dtype, np.integer):
            raise InvalidA2Source("approved cache times must be integer milliseconds")
        if not np.issubdtype(coverage.dtype, np.number) or not np.isfinite(coverage).all() or crosses_gap.dtype != np.bool_:
            raise InvalidA2Source("approved cache coverage/gap arrays have invalid types")
        if starts.size == 0 or np.any(ends <= starts) or np.any(np.diff(starts) < 0) or np.any(crosses_gap) or np.any(coverage < 0.8) or np.any(coverage > 1.0):
            raise InvalidA2Source("approved cache window geometry violates A1 quality constraints")
        for row_index in range(starts.size):
            identity = WindowIdentity(participant, record_id, session, row_index)
            geometry.append({
                "identity": identity,
                "stable_id": identity.stable_id,
                "participant_id": participant,
                "record_id": record_id,
                "session_id": session,
                "row_index": row_index,
                "start_ms": int(starts[row_index]),
                "end_ms": int(ends[row_index]),
                "coverage": float(coverage[row_index]),
                "crosses_gap": bool(crosses_gap[row_index]),
            })
    if len(geometry) != 632100 or len(manifest["entries"]) != 1127:
        raise InvalidA2Source("approved cache row/record counts differ from the A1 run")
    return geometry, cache_hashes, sha256_file(cache_manifest_path), sha256_file(manifest_audit_path)


def _load_global_identity(path: Path, geometry: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], dict[str, int], str]:
    raw = _read_json(path)
    if not isinstance(raw, list) or len(raw) != 632100:
        raise InvalidA2Source("A1 global window identity has the wrong row count")
    if len(raw) != len(geometry):
        raise InvalidA2Source("global identity/cache geometry row count mismatch")
    identities: list[dict[str, object]] = []
    index_by_stable: dict[str, int] = {}
    for index, (identity_row, geometry_row) in enumerate(zip(raw, geometry)):
        if not isinstance(identity_row, dict):
            raise InvalidA2Source("global window identity row is malformed")
        identity = WindowIdentity(
            str(identity_row.get("participant_id", "")),
            str(identity_row.get("record_id", "")),
            str(identity_row.get("session_id", "")),
            int(identity_row.get("row_index", -1)),
        )
        if identity.stable_id != geometry_row["stable_id"]:
            raise InvalidA2Source("global identity order differs from approved cache order")
        if identity.stable_id in index_by_stable:
            raise InvalidA2Source("duplicate stable global window identity")
        index_by_stable[identity.stable_id] = index
        identities.append({**identity_row, "stable_id": identity.stable_id})
    return identities, index_by_stable, sha256_file(path)


def _load_a1_roles(path: Path, participants: Sequence[str]) -> tuple[Role, ...]:
    value = _read_json(path)
    if not isinstance(value, list):
        raise InvalidA2Source("A1 role graph is malformed")
    roles = tuple(_role_from_row(row) for row in value if isinstance(row, dict))
    if len(roles) != len(value):
        raise InvalidA2Source("A1 role graph has malformed rows")
    validate_role_graph(roles, participants)
    rebuilt = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    if [_role_json(role) for role in roles] != [_role_json(role) for role in rebuilt]:
        raise InvalidA2Source("A1 stored role graph differs from the frozen 5/4/4 graph")
    for role in roles:
        validate_outer_exclusion(
            fit_participants=role.fit_participants,
            reference_participants=role.reference_participants,
            selection_participants=role.selection_participants,
            outer_valid_participants=role.outer_valid,
        )
    return roles


def _candidate_interval(row: Mapping[str, object]) -> EventInterval:
    interval = row.get("interval")
    if not isinstance(interval, dict):
        raise InvalidA2Source("saved candidate interval is malformed")
    try:
        return EventInterval(int(interval["start_ms"]), int(interval["end_ms"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidA2Source("saved candidate interval is invalid") from exc


def _parse_score_rows(
    a1_root: Path,
    rows: Sequence[Mapping[str, object]],
    expected_roles: Mapping[str, Role],
    model_rows: Mapping[str, Mapping[str, object]],
    candidate_ids_by_role: Mapping[str, Sequence[str]] | None,
    global_identity: Sequence[Mapping[str, object]] | None,
    *,
    expected_source_hashes: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], int, dict[str, str]]:
    if len(rows) != 130 or len({str(row.get("role_id", "")) for row in rows}) != 130:
        raise InvalidA2Source("A1 score provenance must contain 130 unique role records")
    if set(map(lambda row: str(row.get("role_id", "")), rows)) != set(expected_roles):
        raise InvalidA2Source("A1 score provenance role set differs from the frozen graph")
    provenance: dict[str, dict[str, object]] = {}
    candidate_role_count = 0
    score_hashes: dict[str, str] = {}
    for row in rows:
        role_id = str(row["role_id"])
        role = expected_roles[role_id]
        model = model_rows.get(role_id)
        if model is None:
            raise InvalidA2Source("score provenance has no matching model provenance")
        validate_score_provenance(row, model)
        if str(row.get("kind")) != role.kind:
            raise InvalidA2Source("A1 score provenance kind differs from the role graph")
        if tuple(row.get("fit_participants", ())) != role.fit_participants:
            raise InvalidA2Source("A1 score fit participants differ from role graph")
        if tuple(row.get("scored_participants", ())) != role.scored_participants:
            raise InvalidA2Source("A1 score participant set differs from role graph")
        if tuple(row.get("selection_participants", ())) != role.selection_participants:
            raise InvalidA2Source("A1 score selection participants differ from role graph")
        reference = tuple(row.get("threshold_reference_participants", ()))
        outer_valid = tuple(row.get("outer_valid", ()))
        if outer_valid != role.outer_valid:
            raise InvalidA2Source("A1 score outer-valid participant set differs from role graph")
        validate_outer_exclusion(
            fit_participants=role.fit_participants,
            reference_participants=reference,
            selection_participants=role.selection_participants,
            outer_valid_participants=role.outer_valid,
        )
        if row.get("input_hashes") != expected_source_hashes:
            raise InvalidA2Source("A1 score provenance source hashes conflict")
        if role.kind == "candidate":
            if row.get("threshold") is None:
                raise InvalidA2Source("candidate score threshold reference is missing")
            threshold = float(row["threshold"])
            if row.get("q") != 0.9 or reference != role.reference_participants:
                raise InvalidA2Source("candidate score threshold reference provenance is invalid")
            if int(row.get("reference_count", 0)) <= 0 or not row.get("reference_row_hash"):
                raise InvalidA2Source("candidate score reference provenance is incomplete")
            if global_identity is None:
                raise InvalidA2Source("candidate threshold reference cannot be tied to global identities")
            reference_ids = [str(item["stable_id"]) for item in global_identity if str(item["participant_id"]) in set(role.reference_participants)]
            expected_reference_hash = hashlib.sha256(
                json.dumps(sorted(reference_ids), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if int(row["reference_count"]) != len(reference_ids) or row["reference_row_hash"] != expected_reference_hash:
                raise InvalidA2Source("candidate threshold reference row count/hash conflicts with its role")
        else:
            threshold = 0.0
            if row.get("threshold") is not None or row.get("q") is not None or reference or int(row.get("reference_count", 0)) != 0:
                raise InvalidA2Source("A1 verifier provenance must use no candidate threshold reference")
        score_name = str(row.get("score_file", ""))
        if not score_name:
            raise InvalidA2Source("A1 score file reference is missing")
        score_path = resolve_approved_path(a1_root, score_name, a1_root / "scores")
        score_hash = sha256_file(score_path)
        if score_hash != row.get("score_file_sha256"):
            raise InvalidA2Source("A1 score file hash differs from score provenance")
        score_hashes[score_path.relative_to(a1_root).as_posix()] = score_hash
        with np.load(score_path, allow_pickle=False) as content:
            if not {"ids", "raw", "relative"} <= set(content.files):
                raise InvalidA2Source("A1 score NPZ schema is incomplete")
            ids = np.asarray(content["ids"])
            raw = np.asarray(content["raw"])
            relative = np.asarray(content["relative"])
        if role.kind == "candidate":
            if global_identity is None:
                raise InvalidA2Source("global window identity table is missing")
            expected_ids = [index for index, identity in enumerate(global_identity) if str(identity["participant_id"]) in set(role.scored_participants)]
            validate_score_payload(ids, raw, relative, expected_ids, threshold=threshold)
            candidate_role_count += 1
        else:
            if candidate_ids_by_role is None:
                raise InvalidA2Source("A1 verifier candidate identity set is missing")
            target = f"candidate/{role.outer_fold}/outer" if role.inner_fold is None else f"candidate/{role.outer_fold}/{role.inner_fold}/inner"
            expected_ids = np.asarray(candidate_ids_by_role.get(target, ()), dtype=str)
            if ids.ndim != 1 or ids.dtype.kind not in {"U", "S"} or not np.array_equal(ids.astype(str), expected_ids):
                raise InvalidA2Source("A1 verifier score candidate IDs differ from held-out candidate role")
            if raw.ndim != 1 or relative.shape != raw.shape or raw.shape != ids.shape or not np.isfinite(raw).all() or not np.isfinite(relative).all():
                raise InvalidA2Source("A1 verifier score arrays are invalid")
            if not np.array_equal(relative, raw):
                raise InvalidA2Source("A1 verifier score relative values differ from raw scores")
        provenance[role_id] = dict(row)
    return provenance, candidate_role_count, score_hashes


def _load_model_provenance(path: Path) -> dict[str, dict[str, object]]:
    rows = _read_jsonl(path)
    if len(rows) != 130:
        raise InvalidA2Source("A1 model provenance must contain 130 rows")
    result = {str(row.get("role_id", "")): row for row in rows}
    if len(result) != 130 or "" in result:
        raise InvalidA2Source("A1 model provenance roles are missing or duplicated")
    return result


def _validate_model_blobs(a1_root: Path, model_rows: Mapping[str, Mapping[str, object]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for role_id, row in model_rows.items():
        signature = str(row.get("fit_signature", ""))
        expected = str(row.get("model_hash", ""))
        if len(signature) != 64 or len(expected) != 64:
            raise InvalidA2Source("A1 model provenance signature is malformed")
        model_path = a1_root / "models" / f"{signature}.pickle"
        # Hash the frozen artifact only; it is never deserialized.
        if not model_path.is_file() or sha256_file(model_path) != expected:
            raise InvalidA2Source("A1 model artifact hash/signature mismatch")
        hashes[model_path.relative_to(a1_root).as_posix()] = expected
    return hashes


def _all_training_rows(
    candidate_rows: Mapping[str, Sequence[Mapping[str, object]]],
    roles: Sequence[Role],
    training_truths: Mapping[str, Sequence[TruthRecord]],
) -> list[dict[str, object]]:
    from eating_event.a1.scoring import validate_g3

    role_map = {role.role_id: role for role in roles}
    result: list[dict[str, object]] = []
    for verifier in (role for role in roles if role.kind == "verifier"):
        if verifier.inner_fold is None:
            training_roles = [f"candidate/{verifier.outer_fold}/{inner.inner_fold}/inner" for inner in roles if inner.kind == "candidate" and inner.outer_fold == verifier.outer_fold and inner.inner_fold is not None and inner.subinner_fold is None]
        else:
            training_roles = [f"candidate/{verifier.outer_fold}/{verifier.inner_fold}/{sub.subinner_fold}/subinner" for sub in roles if sub.kind == "candidate" and sub.outer_fold == verifier.outer_fold and sub.inner_fold == verifier.inner_fold and sub.subinner_fold is not None]
        if len(training_roles) != 4 or any(role_id not in candidate_rows for role_id in training_roles):
            raise InvalidA2Source("verifier OOF training graph does not contain four candidate roles")
        rows = [row for role_id in training_roles for row in candidate_rows[role_id]]
        labels = [int(row["label"]) for row in rows]
        participants = [str(row["participant_id"]) for row in rows]
        try:
            validate_g3(labels, participants)
        except ValueError as exc:
            raise VerifierDataInsufficient(f"G3: {verifier.role_id}: {exc}") from exc
        positive_gt = {
            (str(row["participant_id"]), truth.event_id)
            for row in rows if int(row["label"]) == 1
            for truth in training_truths.get(str(row["participant_id"]), ())
            if interval_iou(_candidate_interval(row), truth.interval) > 0.25
        }
        fit_participants = set(participants)
        if not fit_participants <= set(verifier.fit_participants) or fit_participants & set(verifier.outer_valid):
            raise InvalidA2Source("verifier candidate fit rows violate participant isolation")
        result.append({
            "verifier_role_id": verifier.role_id,
            "candidate_training_roles": training_roles,
            "positive_candidate_count": sum(label == 1 for label in labels),
            "positive_participant_count": len({p for p, label in zip(participants, labels) if label == 1}),
            "positive_canonical_gt_count": len(positive_gt),
            "both_classes": len(set(labels)) == 2,
        })
    if len(result) != 25:
        raise InvalidA2Source("G3 audit did not cover all 25 verifier roles")
    return result


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
    temporary.replace(path)


def _materialize_role(
    output: Path,
    role: Role,
    raw_rows: Sequence[Mapping[str, object]],
    geometry_by_component: Mapping[str, Sequence[ContextWindow]],
    score_hash: str,
    cache_hash_digest: str,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    labels: list[dict[str, object]] = []
    matrix_rows: list[np.ndarray] = []
    pre_empty = post_empty = 0
    for row in raw_rows:
        component_id = str(row["component_id"])
        interval = _candidate_interval(row)
        source_16d = tuple(row["features"])
        context = geometry_by_component.get(component_id)
        if context is None:
            raise InvalidA2Source("candidate component has no scored-window geometry")
        key = CandidateKey(role.role_id, str(row["candidate_id"]))
        features = build_a2_features(
            source_16d=source_16d,
            interval=interval,
            role_id=role.role_id,
            component_id=component_id,
            context_windows=context,
        )
        feature_row = A2FeatureRow(
            key=key,
            participant_id=str(row["participant_id"]),
            record_id=str(row["record_id"]),
            session_id=str(row["session_id"]),
            component_id=component_id,
            interval=interval,
            source_16d=source_16d,
            features_26d=features,
            support_stable_ids=tuple("|".join(str(item[key]) for key in ("participant_id", "record_id", "session_id", "row_index")) for item in row["support_indices"]),
            source_hashes={"a1_candidate_score": score_hash, "approved_cache_hash_manifest": cache_hash_digest},
        )
        values = np.asarray(feature_row.features_26d, dtype=np.float32)
        if not np.isfinite(values).all() or values.shape != (26,):
            raise InvalidA2Source("A2 feature row is not finite 26D")
        matrix_rows.append(values)
        if not any((item.start_ms + item.end_ms) // 2 >= interval.start_ms - 300000 and (item.start_ms + item.end_ms) // 2 < interval.start_ms for item in context):
            pre_empty += 1
        if not any((item.start_ms + item.end_ms) // 2 >= interval.end_ms and (item.start_ms + item.end_ms) // 2 < interval.end_ms + 300000 for item in context):
            post_empty += 1
        labels_raw = row.get("label")
        if labels_raw is not None:
            labels.append({"role_id": role.role_id, "candidate_id": str(row["candidate_id"]), "label": int(labels_raw)})
        rows.append({
            "role_id": role.role_id,
            "candidate_id": key.candidate_id,
            "participant_id": feature_row.participant_id,
            "record_id": feature_row.record_id,
            "session_id": feature_row.session_id,
            "component_id": feature_row.component_id,
            "interval": {"start_ms": interval.start_ms, "end_ms": interval.end_ms},
            "source_16d": list(feature_row.source_16d),
            "support_indices": list(row["support_indices"]),
            "boundary_kind": str(row["boundary_kind"]),
            "source_segment_id": row.get("source_segment_id"),
        })
    matrix = np.asarray(matrix_rows, dtype=np.float32)
    if matrix.shape != (len(raw_rows), 26) or not np.isfinite(matrix).all():
        raise InvalidA2Source("A2 role matrix is incomplete or nonfinite")
    key = hashlib.sha256(role.role_id.encode("utf-8")).hexdigest()[:20]
    materialized = output / "materialized"
    row_path = materialized / "candidate-rows" / f"{key}.jsonl"
    matrix_path = materialized / "feature-matrices" / f"{key}.npy"
    label_path = materialized / "training-labels" / f"{key}.jsonl" if labels else None
    _write_jsonl(row_path, rows)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(matrix_path, matrix, allow_pickle=False)
    if label_path is not None:
        _write_jsonl(label_path, labels)
    keys = [[role.role_id, row["candidate_id"]] for row in rows]
    label_digest = _digest([[item["role_id"], item["candidate_id"], item["label"]] for item in labels]) if labels else None
    digest_record = {
        "role_id": role.role_id,
        "candidate_count": len(rows),
        "ordered_candidate_keys_sha256": _digest(keys),
        "feature_matrix_sha256": hashlib.sha256(matrix.tobytes()).hexdigest(),
        "training_label_join_sha256": label_digest,
        "candidate_rows_file": row_path.relative_to(output).as_posix(),
        "feature_matrix_file": matrix_path.relative_to(output).as_posix(),
        "training_label_file": None if label_path is None else label_path.relative_to(output).as_posix(),
        "source_16d_sha256": _digest([row["source_16d"] for row in rows]),
        "pre_empty_count": pre_empty,
        "post_empty_count": post_empty,
        "all_features_finite": bool(np.isfinite(matrix).all()),
    }
    return digest_record


def run_audit(
    workspace: str | Path,
    output: str | Path,
    *,
    config_sha256: str,
    startup_resources: Mapping[str, int] | None = None,
    study_id: str = DEFAULT_STUDY_ID,
) -> dict[str, object]:
    """Authenticate source artifacts and materialize fixed features; never fits or predicts."""

    root = Path(workspace).resolve()
    output_dir = Path(output).resolve()
    config, output_dir = validate_study_binding(
        root,
        output_dir,
        study_id=study_id,
        config_sha256=config_sha256,
    )
    actual_config_sha = config_sha256
    frozen_a2_code = current_a2_code_identity(root)
    if not startup_resources:
        raise StudyResourceError("persisted startup resource sample is unavailable")
    available_bytes = int(startup_resources.get("startup_available_bytes", 0))
    rss_ceiling = int(startup_resources.get("rss_ceiling_bytes", 0))
    if available_bytes <= 0 or rss_ceiling <= 0 or rss_ceiling > min(8 * 1024**3, int(available_bytes * 0.60)):
        raise StudyResourceError("persisted startup RSS ceiling is invalid")
    a1_root = root / str(config["a1_artifact_root"])
    checksum_path = a1_root / "final-checksums.json"
    checksums = authenticate_checksum_manifest(checksum_path, a1_root, str(config["source_checksum_sha256"]))
    if len(checksums) != 282:
        raise InvalidA2Source("A1 final checksum manifest must contain 282 files")
    a1_manifest_path = a1_root / "run-manifest.json"
    a1_manifest = _read_json(a1_manifest_path)
    if not isinstance(a1_manifest, dict) or a1_manifest.get("run_schema") != "a1_run_manifest_v1":
        raise InvalidA2Source("A1 run manifest schema mismatch")
    code_identity = a1_manifest.get("code_identity")
    if not isinstance(code_identity, dict) or len(code_identity) != 45:
        raise InvalidA2Source("A1 run manifest must register exactly 45 code paths")
    validate_a1_code_identity(code_identity, root)
    environment = a1_manifest.get("environment")
    if not isinstance(environment, dict):
        raise InvalidA2Source("A1 environment identity is missing")
    require_environment(environment, _EXPECTED_ENVIRONMENT)
    runtime_environment = _environment_identity()
    require_environment(runtime_environment, _EXPECTED_ENVIRONMENT)
    a1_config_path = root / str(config["a1_config_path"])
    if not a1_config_path.is_file() or sha256_file(a1_config_path) != a1_manifest.get("config_sha256"):
        raise InvalidA2Source("A1 frozen config path/hash mismatch")
    a1_config = _read_json(a1_config_path)
    if not isinstance(a1_config, dict) or not isinstance(a1_config.get("paths"), dict):
        raise InvalidA2Source("A1 approved input path contract is malformed")
    paths = a1_config["paths"]
    cache_root = _assert_workspace_artifact(root, paths.get("cache_root"), name="cache_root", directory=True)
    cache_manifest = _assert_workspace_artifact(root, paths.get("cache_manifest"), name="cache_manifest")
    manifest_audit = _assert_workspace_artifact(root, paths.get("manifest_audit"), name="manifest_audit")
    eligibility = _assert_workspace_artifact(root, paths.get("eligibility"), name="eligibility")
    evaluation_truths, training_truths, _eligibility_participants, eligibility_payload = _load_eligibility(
        eligibility,
        str(config["eligibility_sha256"]),
        str(config["denominator_sha256"]),
    )
    geometry, cache_hashes, cache_manifest_sha, manifest_audit_sha = _load_cache_geometry(
        root,
        cache_manifest,
        manifest_audit,
        cache_root,
    )
    participants = tuple(sorted({str(row["participant_id"]) for row in geometry}))
    if len(participants) != 41 or "6C7" not in participants:
        raise InvalidA2Source("approved cache population must include all 41 participants and 6C7")
    validated_eligible = validate_eligible_gt_participants(eligibility_payload["event_eligibility"], participants)
    if validated_eligible != _eligibility_participants:
        raise InvalidA2Source("eligible canonical GT participant collection is inconsistent")
    global_identity, global_index_by_stable, window_identity_sha = _load_global_identity(a1_root / "window-identity.json", geometry)
    if len({str(row["participant_id"]) for row in global_identity}) != 41:
        raise InvalidA2Source("global window identities do not contain the approved 41 participants")
    roles = _load_a1_roles(a1_root / "role-graph.json", participants)
    role_by_id = {role.role_id: role for role in roles}
    candidate_roles = {role.role_id: role for role in roles if role.kind == "candidate"}
    all_roles = role_by_id

    candidate_path = a1_root / "event-candidates.jsonl"
    raw_candidate_rows = _read_jsonl(candidate_path)
    for row in raw_candidate_rows:
        row["role_id"] = str(row.get("role_id", ""))
    check_candidate_rows(raw_candidate_rows)
    candidates_by_role_raw: dict[str, list[dict[str, object]]] = {role_id: [] for role_id in candidate_roles}
    for row in raw_candidate_rows:
        role_id = str(row["role_id"])
        role = candidate_roles.get(role_id)
        if role is None:
            raise InvalidA2Source("A1 candidate row references an unapproved role")
        is_outer = role.inner_fold is None
        validate_outer_label(row, outer_role=is_outer)
        if row.get("boundary_kind") != "observed_window_support_component_v1" or row.get("source_segment_id") is not None:
            raise InvalidA2Source("A1 candidate boundary/source-segment contract differs")
        features = row.get("features")
        if not isinstance(features, list) or len(features) != 16 or not np.isfinite(np.asarray(features, dtype=np.float64)).all():
            raise InvalidA2Source("A1 candidate must preserve exactly 16 finite saved features")
        candidates_by_role_raw[role_id].append(row)
    if sum(map(len, candidates_by_role_raw.values())) != 72112:
        raise InvalidA2Source("A1 role-qualified candidate count differs from the approved source")

    model_rows = _load_model_provenance(a1_root / "model-provenance.jsonl")
    if set(model_rows) != set(all_roles):
        raise InvalidA2Source("A1 model provenance role set differs from the frozen graph")
    model_hashes = _validate_model_blobs(a1_root, model_rows)
    score_rows = _read_jsonl(a1_root / "score-provenance.jsonl")
    candidate_ids_by_role = {role_id: [str(row["candidate_id"]) for row in rows] for role_id, rows in candidates_by_role_raw.items()}
    input_audit_path = a1_root / "input-audit.json"
    input_audit = _read_json(input_audit_path)
    if not isinstance(input_audit, dict) or input_audit.get("status") != "READY":
        raise InvalidA2Source("A1 approved input audit is not READY")
    source_hashes = dict(input_audit.get("source_hashes", {}))
    if not source_hashes:
        raise InvalidA2Source("A1 input audit has no source hashes")
    expected_external_hashes = {
        "cache_manifest": cache_manifest_sha,
        "manifest_audit": manifest_audit_sha,
        "eligibility": sha256_file(eligibility),
        "eligibility_declared_denominator": str(eligibility_payload["label_eligible_event_denominator_sha256"]),
    }
    for name, actual in expected_external_hashes.items():
        if source_hashes.get(name) != actual:
            raise InvalidA2Source(f"A1 input audit source hash mismatch for {name}")
    for relative_name, actual in cache_hashes.items():
        source_key = f"cache:{Path(relative_name).name}"
        if source_hashes.get(source_key) != actual:
            raise InvalidA2Source(f"A1 input audit source hash mismatch for approved cache {Path(relative_name).name}")
    score_provenance, candidate_score_role_count, score_hashes = _parse_score_rows(
        a1_root,
        score_rows,
        all_roles,
        model_rows,
        candidate_ids_by_role,
        global_identity,
        expected_source_hashes=source_hashes,
    )
    score_hashes.update(model_hashes)
    if len(score_provenance) != 130 or candidate_score_role_count != 105:
        raise InvalidA2Source("A1 score role count is incomplete")

    geometry_by_identity = {str(row["stable_id"]): row for row in geometry}
    output_dir.mkdir(parents=True, exist_ok=True)
    materialized = output_dir / "materialized"
    source_hashes.update({
        "a1_final_checksums_sha256": sha256_file(checksum_path),
        "a1_run_manifest_sha256": sha256_file(a1_manifest_path),
        "a1_config_sha256": sha256_file(a1_config_path),
        "a1_event_candidates_sha256": sha256_file(candidate_path),
        "a1_window_identity_sha256": window_identity_sha,
        "a1_role_graph_sha256": sha256_file(a1_root / "role-graph.json"),
        "a1_score_provenance_sha256": sha256_file(a1_root / "score-provenance.jsonl"),
        "a1_model_provenance_sha256": sha256_file(a1_root / "model-provenance.jsonl"),
        "a1_matches_sha256": sha256_file(a1_root / "matches.json"),
        "a1_threshold_selection_sha256": sha256_file(a1_root / "threshold-selection.jsonl"),
        "approved_cache_manifest_sha256": cache_manifest_sha,
        "approved_manifest_audit_sha256": manifest_audit_sha,
        "approved_eligibility_sha256": sha256_file(eligibility),
        **{f"a1:{name}": value for name, value in checksums.items()},
        **{f"cache:{name}": value for name, value in cache_hashes.items()},
        **{f"score-or-model:{name}": value for name, value in score_hashes.items()},
    })
    frozen_identity = {
        "study_id": study_id,
        "study_output": str(config["study_output"]),
        "config_sha256": actual_config_sha,
        "a2_code_identity": frozen_a2_code,
        "a2_code_identity_sha256": _digest(frozen_a2_code),
        "source_hashes": source_hashes,
        "input_hash_manifest_sha256": _digest(source_hashes),
        "created_before_feature_materialization": True,
    }
    frozen_identity_path = output_dir / "frozen-study-identity.json"
    _write_json(frozen_identity_path, frozen_identity)
    frozen_identity_sha256 = sha256_file(frozen_identity_path)
    role_digests: list[dict[str, object]] = []
    cache_hash_digest = _digest(cache_hashes)
    for role_id, role in candidate_roles.items():
        score_record = score_provenance[role_id]
        score_name = str(score_record["score_file"])
        score_path = a1_root / score_name
        score_file_hash = sha256_file(score_path)
        expected_global = [index for index, identity in enumerate(global_identity) if str(identity["participant_id"]) in set(role.scored_participants)]
        with np.load(score_path, allow_pickle=False) as content:
            ids = np.asarray(content["ids"], dtype=np.int64)
            rel = np.asarray(content["relative"], dtype=np.float64)
        if not np.array_equal(ids, np.asarray(expected_global, dtype=np.int64)):
            raise InvalidA2Source("candidate role score positions changed after authentication")
        relative_by_global = np.full(len(global_identity), np.nan, dtype=np.float64)
        relative_by_global[ids] = rel
        role_geometry = [geometry[index] for index in expected_global]
        by_record: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
        for item in role_geometry:
            by_record.setdefault((str(item["participant_id"]), str(item["record_id"]), str(item["session_id"])), []).append(item)
        component_by_stable: dict[str, str] = {}
        context_by_component: dict[str, list[ContextWindow]] = {}
        zero_features = np.zeros(111, dtype=np.float32)
        zero_features.setflags(write=False)
        for group_key, group in by_record.items():
            session_start = min(int(item["start_ms"]) for item in group)
            session_end = max(int(item["end_ms"]) for item in group)
            windows = [
                A1Window(
                    identity=item["identity"],
                    start_ms=int(item["start_ms"]),
                    end_ms=int(item["end_ms"]),
                    coverage=float(item["coverage"]),
                    crosses_hard_gap=bool(item["crosses_gap"]),
                    features=zero_features,
                    label=0,
                    session_start_ms=session_start,
                    session_end_ms=session_end,
                    boundary_kind="observed_window_support_component_v1",
                )
                for item in group
            ]
            for component in build_support_components(windows):
                stable_ids = [windows[window_indices].identity.stable_id for window_indices in component.window_indices]
                for stable_id in stable_ids:
                    component_by_stable[stable_id] = component.component_id
                    global_index = global_index_by_stable[stable_id]
                    geometry_row = geometry_by_identity[stable_id]
                    score = relative_by_global[global_index]
                    if not np.isfinite(score):
                        raise InvalidA2Source("approved candidate context score is missing")
                    context_by_component.setdefault(component.component_id, []).append(ContextWindow(
                        role_id=role_id,
                        global_window_index=global_index,
                        stable_id=stable_id,
                        component_id=component.component_id,
                        start_ms=int(geometry_row["start_ms"]),
                        end_ms=int(geometry_row["end_ms"]),
                        relative=float(score),
                    ))
        stable_ids = set(component_by_stable)
        for row in candidates_by_role_raw[role_id]:
            validate_support_identity(
                row,
                role_id=role_id,
                stable_ids=stable_ids,
                component_by_stable_id=component_by_stable,
            )
            candidate_component = str(row["component_id"])
            if candidate_component not in context_by_component:
                raise InvalidA2Source("candidate component has no role-local scored windows")
        role_digests.append(_materialize_role(
            output_dir,
            role,
            candidates_by_role_raw[role_id],
            context_by_component,
            score_hash=score_record["score_file_sha256"],
            cache_hash_digest=cache_hash_digest,
        ))
        del relative_by_global, role_geometry, by_record, windows, component_by_stable, context_by_component, stable_ids

    outer_roles = sorted((role for role in candidate_roles.values() if role.inner_fold is None), key=lambda role: role.outer_fold)
    outer_candidate_counts: list[int] = []
    outer_covered: list[int] = []
    for role in outer_roles:
        rows = candidates_by_role_raw[role.role_id]
        truths = [truth for participant in role.scored_participants for truth in evaluation_truths.get(participant, ())]
        covered = sum(any(str(candidate["participant_id"]) == truth.participant_id and interval_iou(_candidate_interval(candidate), truth.interval) > 0.25 for candidate in rows) for truth in truths)
        outer_candidate_counts.append(len(rows))
        outer_covered.append(covered)
    if outer_candidate_counts != list(config["outer_candidate_counts"]) or outer_covered != list(config["outer_candidate_covered_gt"]):
        raise InvalidA2Source("frozen outer candidate/coverage invariants differ")

    g3_precheck = _all_training_rows(candidates_by_role_raw, roles, training_truths)
    if current_a2_code_identity(root) != frozen_a2_code:
        raise InvalidA2Source("A2 code identity changed during the real-source audit")

    _write_json(materialized / "roles.json", [_role_json(role) for role in roles])
    _write_jsonl(materialized / "truths.jsonl", [
        {"event_id": truth.event_id, "participant_id": truth.participant_id, "interval": {"start_ms": truth.interval.start_ms, "end_ms": truth.interval.end_ms}}
        for participant in participants for truth in evaluation_truths.get(participant, ())
    ])
    _write_json(materialized / "role-digests.json", role_digests)

    matches_rows = _read_json(a1_root / "matches.json")
    if not isinstance(matches_rows, list):
        raise InvalidA2Source("A1 matches artifact is malformed")
    a1_fn_ids: list[str] = []
    for row in matches_rows:
        if isinstance(row, dict):
            a1_fn_ids.extend(str(item) for item in row.get("unmatched_truth_ids", ()))
    if len(a1_fn_ids) != 81 or len(set(a1_fn_ids)) != 81:
        raise InvalidA2Source("A1 unmatched canonical GT list differs from the frozen 81 FN")
    threshold_rows = _read_jsonl(a1_root / "threshold-selection.jsonl")
    thresholds = {str(row.get("outer_fold")): float(row.get("selected")) for row in threshold_rows}
    if len(thresholds) != 5:
        raise InvalidA2Source("A1 threshold selection must contain five outer folds")
    a1_fn_categories: dict[str, str] = {}
    verifier_scores_by_role: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for role in outer_roles:
        verifier_id = f"verifier/{role.outer_fold}/outer"
        score_record = score_provenance[verifier_id]
        path = a1_root / str(score_record["score_file"])
        with np.load(path, allow_pickle=False) as content:
            ids = np.asarray(content["ids"]).astype(str)
            raw = np.asarray(content["raw"], dtype=np.float64)
        verifier_scores_by_role[role.outer_fold] = (ids, raw)
    by_gt = {truth.event_id: truth for values in evaluation_truths.values() for truth in values}
    for gt_id in a1_fn_ids:
        truth = by_gt.get(gt_id)
        if truth is None:
            raise InvalidA2Source("A1 unmatched GT ID is not in approved evaluation truth")
        outer = next(role for role in outer_roles if truth.participant_id in role.scored_participants)
        rows = candidates_by_role_raw[outer.role_id]
        matching = [row for row in rows if str(row["participant_id"]) == truth.participant_id and interval_iou(_candidate_interval(row), truth.interval) > 0.25]
        if not matching:
            category = "no_candidate_iou_over_0_25"
        else:
            ids, raw = verifier_scores_by_role[outer.outer_fold]
            score_map = {candidate_id: float(value) for candidate_id, value in zip(ids, raw)}
            threshold = thresholds.get(outer.outer_fold)
            if threshold is None:
                raise InvalidA2Source("A1 frozen threshold choice is missing")
            passing = [row for row in matching if score_map.get(str(row["candidate_id"]), -1.0) >= threshold]
            if not passing:
                category = "all_matching_candidates_below_threshold"
            elif all(_candidate_interval(row).end_ms - _candidate_interval(row).start_ms < int(config["min_duration_ms"]) for row in passing):
                category = "thresholded_candidate_filtered_by_min_duration"
            else:
                category = "decoder_or_one_to_one_matching"
        a1_fn_categories[gt_id] = category
    _write_json(materialized / "a1-fn-transition-input.json", {"ids": a1_fn_ids, "first_break_categories": a1_fn_categories})

    a2_code = frozen_a2_code
    all_study_files: dict[str, str] = {}
    for path in sorted((output_dir / "materialized").rglob("*")):
        if path.is_file():
            all_study_files[path.relative_to(output_dir).as_posix()] = sha256_file(path)
    for row in role_digests:
        for field in ("candidate_rows_file", "feature_matrix_file", "training_label_file"):
            if row.get(field):
                name = str(row[field])
                all_study_files[name] = sha256_file(output_dir / name)
    report = {
        "status": "AUDIT_READY",
        "study_id": study_id,
        "study_output": str(config["study_output"]),
        "study_id": config["study_id"],
        "a1_run_id": config["a1_run_id"],
        "config_sha256": actual_config_sha,
        "a1_final_checksums_sha256": sha256_file(checksum_path),
        "a2_code_identity": a2_code,
        "a2_code_identity_sha256": _digest(a2_code),
        "frozen_study_identity_sha256": frozen_identity_sha256,
        "source_hashes": source_hashes,
        "input_hash_manifest_sha256": _digest(source_hashes),
        "role_graph_sha256": sha256_file(a1_root / "role-graph.json"),
        "participant_count": len(participants),
        "participants": list(participants),
        "evaluation_gt_count": sum(len(values) for values in evaluation_truths.values()),
        "candidate_row_count": len(raw_candidate_rows),
        "candidate_role_count": len(candidate_roles),
        "verifier_role_count": sum(role.kind == "verifier" for role in roles),
        "score_role_count": len(score_provenance),
        "window_count": len(global_identity),
        "cache_record_count": len(cache_hashes),
        "outer_candidate_counts": outer_candidate_counts,
        "outer_candidate_covered_gt": outer_covered,
        "g3_precheck": g3_precheck,
        "role_digests": role_digests,
        "materialized_file_hashes": all_study_files,
        "resource_readiness": {
            "startup_resources": dict(startup_resources or {}),
            "psutil_available": True,
            "parent_process_tree_monitor_required": True,
            "thread_limit": 4,
        },
        "candidate_fit_attempts": 0,
        "candidate_predict_attempts": 0,
        "verifier_fit_attempts": 0,
        "raw_sensor_io": False,
        "official_test_io": False,
        "external_data_io": False,
        "a1_model_pickle_deserialized": False,
    }
    ready_path = output_dir / "audit-ready.json"
    _write_json(ready_path, report)
    ready_sha = sha256_file(ready_path)
    (output_dir / "audit-ready.sha256").write_text(ready_sha + "  audit-ready.json\n", encoding="ascii")
    return {"status": "AUDIT_READY", "audit_ready_sha256": ready_sha, "report": report}


def _verify_materialized_digests(output: Path, report: Mapping[str, object]) -> None:
    hashes = report.get("materialized_file_hashes")
    if not isinstance(hashes, dict):
        raise InvalidA2Source("AUDIT_READY materialized file hashes are missing")
    for relative, expected in hashes.items():
        path = (output / str(relative)).resolve()
        try:
            path.relative_to(output.resolve())
        except ValueError as exc:
            raise InvalidA2Source("AUDIT_READY artifact path escaped study output") from exc
        if not path.is_file() or sha256_file(path) != expected:
            raise InvalidA2Source(f"AUDIT_READY materialized artifact changed: {relative}")
    digests = report.get("role_digests")
    if not isinstance(digests, list):
        raise InvalidA2Source("AUDIT_READY role digests are missing")
    for row in digests:
        role_id = str(row["role_id"])
        rows = _read_jsonl(output / str(row["candidate_rows_file"]))
        keys = [[role_id, str(item["candidate_id"])] for item in rows]
        if _digest(keys) != row["ordered_candidate_keys_sha256"]:
            raise InvalidA2Source("AUDIT_READY candidate key digest mismatch")
        matrix = np.load(output / str(row["feature_matrix_file"]), allow_pickle=False)
        if matrix.dtype != np.float32 or matrix.shape != (int(row["candidate_count"]), 26) or not np.isfinite(matrix).all():
            raise InvalidA2Source("AUDIT_READY feature matrix shape/type/finiteness mismatch")
        if hashlib.sha256(matrix.tobytes()).hexdigest() != row["feature_matrix_sha256"]:
            raise InvalidA2Source("AUDIT_READY actual fit matrix digest mismatch")
        if row.get("training_label_file"):
            labels = _read_jsonl(output / str(row["training_label_file"]))
            label_rows = [[item["role_id"], item["candidate_id"], int(item["label"])] for item in labels]
            if len(labels) != int(row["candidate_count"]) or _digest(label_rows) != row["training_label_join_sha256"]:
                raise InvalidA2Source("AUDIT_READY separate training label join digest mismatch")


def verify_audit_ready(
    workspace: str | Path,
    output: str | Path,
    *,
    expected_config_sha256: str,
    study_id: str = DEFAULT_STUDY_ID,
) -> dict[str, object]:
    root = Path(workspace).resolve()
    config, output_dir = validate_study_binding(
        root,
        output,
        study_id=study_id,
        config_sha256=expected_config_sha256,
    )
    actual_config = expected_config_sha256
    ready_path = output_dir / "audit-ready.json"
    sidecar = output_dir / "audit-ready.sha256"
    if not ready_path.is_file() or not sidecar.is_file():
        raise InvalidA2Source("hash-bound AUDIT_READY evidence is missing")
    expected = sidecar.read_text(encoding="ascii").strip().split()[0]
    actual = sha256_file(ready_path)
    if actual != expected:
        raise InvalidA2Source("AUDIT_READY report hash mismatch")
    report = _read_json(ready_path)
    if (
        not isinstance(report, dict)
        or report.get("status") != "AUDIT_READY"
        or report.get("study_id") != study_id
        or report.get("study_output") != config["study_output"]
        or report.get("config_sha256") != expected_config_sha256
    ):
        raise InvalidA2Source("AUDIT_READY status/config identity mismatch")
    if report.get("a2_code_identity") != current_a2_code_identity(root):
        raise InvalidA2Source("A2 code changed after AUDIT_READY")
    require_environment(_environment_identity(), _EXPECTED_ENVIRONMENT)
    frozen_identity_path = output_dir / "frozen-study-identity.json"
    if not frozen_identity_path.is_file() or sha256_file(frozen_identity_path) != report.get("frozen_study_identity_sha256"):
        raise InvalidA2Source("pre-materialization A2/source identity manifest changed")
    frozen_identity = _read_json(frozen_identity_path)
    if (
        not isinstance(frozen_identity, dict)
        or frozen_identity.get("study_id") != study_id
        or frozen_identity.get("study_output") != config["study_output"]
        or frozen_identity.get("config_sha256") != actual_config
    ):
        raise InvalidA2Source("pre-materialization A2 identity does not match the frozen config")
    if frozen_identity.get("a2_code_identity") != report.get("a2_code_identity") or frozen_identity.get("source_hashes") != report.get("source_hashes"):
        raise InvalidA2Source("pre-materialization source/code hash binding differs from AUDIT_READY")
    a1_root = root / str(config["a1_artifact_root"])
    checksum_path = a1_root / "final-checksums.json"
    checksums = authenticate_checksum_manifest(checksum_path, a1_root, str(config["source_checksum_sha256"]))
    if len(checksums) != 282:
        raise InvalidA2Source("A1 checksum manifest count changed after audit")
    a1_manifest = _read_json(a1_root / "run-manifest.json")
    if not isinstance(a1_manifest, dict) or not isinstance(a1_manifest.get("code_identity"), dict):
        raise InvalidA2Source("A1 code identity is missing on run revalidation")
    validate_a1_code_identity(a1_manifest["code_identity"], root)
    a1_config_path = root / str(config["a1_config_path"])
    if not a1_config_path.is_file() or sha256_file(a1_config_path) != a1_manifest.get("config_sha256"):
        raise InvalidA2Source("A1 config hash changed after AUDIT_READY")
    a1_config = _read_json(a1_config_path)
    paths = a1_config.get("paths") if isinstance(a1_config, dict) else None
    if not isinstance(paths, dict):
        raise InvalidA2Source("A1 approved path contract is missing during run revalidation")
    cache_root = _assert_workspace_artifact(root, paths.get("cache_root"), name="cache_root", directory=True)
    cache_manifest = _assert_workspace_artifact(root, paths.get("cache_manifest"), name="cache_manifest")
    manifest_audit = _assert_workspace_artifact(root, paths.get("manifest_audit"), name="manifest_audit")
    eligibility = _assert_workspace_artifact(root, paths.get("eligibility"), name="eligibility")
    source_hashes = report.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise InvalidA2Source("AUDIT_READY source hashes are missing")
    for name, path in (("a1_config_sha256", a1_config_path), ("approved_cache_manifest_sha256", cache_manifest), ("approved_manifest_audit_sha256", manifest_audit), ("approved_eligibility_sha256", eligibility)):
        expected_hash = source_hashes.get(name)
        if expected_hash is not None and expected_hash != sha256_file(path):
            raise InvalidA2Source(f"approved source changed after AUDIT_READY: {name}")
    cache_manifest_payload = _read_json(cache_manifest)
    if not isinstance(cache_manifest_payload, dict) or not isinstance(cache_manifest_payload.get("entries"), list):
        raise InvalidA2Source("approved cache manifest is malformed on run revalidation")
    for entry in cache_manifest_payload["entries"]:
        if not isinstance(entry, dict):
            raise InvalidA2Source("approved cache manifest row is malformed on run revalidation")
        cache_path = resolve_approved_path(root, str(entry.get("cache_path", "")), cache_root)
        cache_hash = sha256_file(cache_path)
        if cache_hash != entry.get("cache_sha256") or cache_hash != source_hashes.get(f"cache:{cache_path.relative_to(root).as_posix()}"):
            # A1's original source map is keyed by cache basename; A2's immutable map uses the relative path.
            if cache_hash != entry.get("cache_sha256") or cache_hash != source_hashes.get(f"cache:{cache_path.name}"):
                raise InvalidA2Source("approved cache changed after AUDIT_READY")
    _verify_materialized_digests(output_dir, report)
    return report


def load_audited_corpus(workspace: str | Path, output: str | Path, *, study_id: str = DEFAULT_STUDY_ID):
    """Load only authenticated A2 materialized inputs for the fit process."""

    from eating_event.a2.execution import A2Candidate, FeatureCorpus

    root = Path(workspace).resolve()
    config, config_sha = load_config(root, study_id=study_id)
    config, output_dir = validate_study_binding(root, output, study_id=study_id, config_sha256=config_sha)
    report = verify_audit_ready(root, output_dir, expected_config_sha256=config_sha, study_id=study_id)
    materialized = output_dir / "materialized"
    role_rows = _read_json(materialized / "roles.json")
    if not isinstance(role_rows, list):
        raise InvalidA2Source("materialized A1 role graph is malformed")
    roles = tuple(_role_from_row(row) for row in role_rows)
    participants = tuple(report["participants"])
    validate_role_graph(roles, participants)
    role_digests = report["role_digests"]
    candidates_by_role: dict[str, tuple[A2Candidate, ...]] = {}
    for digest in role_digests:
        role_id = str(digest["role_id"])
        rows = _read_jsonl(output_dir / str(digest["candidate_rows_file"]))
        matrix = np.load(output_dir / str(digest["feature_matrix_file"]), allow_pickle=False)
        label_by_key: dict[tuple[str, str], int] = {}
        if digest.get("training_label_file"):
            for label in _read_jsonl(output_dir / str(digest["training_label_file"])):
                key = (str(label["role_id"]), str(label["candidate_id"]))
                if key in label_by_key:
                    raise InvalidA2Source("duplicate role-scoped training label")
                label_by_key[key] = int(label["label"])
        candidates: list[A2Candidate] = []
        if matrix.shape[0] != len(rows):
            raise InvalidA2Source("materialized candidate row and feature matrix order differ")
        for index, row in enumerate(rows):
            key = (role_id, str(row["candidate_id"]))
            interval_row = row["interval"]
            interval = EventInterval(int(interval_row["start_ms"]), int(interval_row["end_ms"]))
            support = tuple(
                WindowIdentity(str(item["participant_id"]), str(item["record_id"]), str(item["session_id"]), int(item["row_index"]))
                for item in row["support_indices"]
            )
            candidates.append(A2Candidate(
                role_id=role_id,
                candidate_id=key[1],
                participant_id=str(row["participant_id"]),
                record_id=str(row["record_id"]),
                session_id=str(row["session_id"]),
                component_id=str(row["component_id"]),
                interval=interval,
                source_16d=np.asarray(row["source_16d"], dtype=np.float64),
                features_26d=matrix[index],
                support_indices=support,
                label=label_by_key.get(key),
            ))
        if label_by_key and len(label_by_key) != len(candidates):
            raise InvalidA2Source("training label join is incomplete for the candidate role")
        candidates_by_role[role_id] = tuple(candidates)
    truths_by_participant: dict[str, list[TruthRecord]] = {participant: [] for participant in participants}
    for row in _read_jsonl(materialized / "truths.jsonl"):
        interval_row = row["interval"]
        truth = TruthRecord(
            str(row["event_id"]),
            str(row["participant_id"]),
            EventInterval(int(interval_row["start_ms"]), int(interval_row["end_ms"])),
        )
        truths_by_participant[truth.participant_id].append(truth)
    transitions = _read_json(materialized / "a1-fn-transition-input.json")
    return FeatureCorpus(
        participants=participants,
        roles=roles,
        candidates_by_role=candidates_by_role,
        truths_by_participant={p: tuple(rows) for p, rows in truths_by_participant.items()},
        output_dir=output_dir,
        config=config,
        a1_fn_ids=tuple(transitions["ids"]),
        a1_fn_categories=transitions["first_break_categories"],
        source_hashes=report["source_hashes"],
        input_digests={str(row["role_id"]): {
            "ordered_candidate_keys_sha256": str(row["ordered_candidate_keys_sha256"]),
            "feature_matrix_sha256": str(row["feature_matrix_sha256"]),
            "training_label_join_sha256": str(row["training_label_join_sha256"] or ""),
        } for row in role_digests},
    )
