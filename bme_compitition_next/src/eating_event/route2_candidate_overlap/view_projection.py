"""Privileged, one-time projection of frozen derived Route 2 inputs.

This preparation tool is separate from the study.  It may read the explicitly
registered mixed A2 candidate rows and G1 eligibility source; the study must
receive only the physical views written here after independent review.  A
completed projection is identified by a manifest written last.  Failure leaves
an incomplete, non-reusable directory and never deletes or replaces a file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from eating_event.a1.pipeline import Role, build_role_graph, validate_role_graph

from .contracts import (
    CACHE_MANIFEST_FIELDS,
    CACHE_MEMBERS,
    CacheFileRegistration,
    GT_FIELDS,
    IDENTITY_FIELDS,
    OUTER_CONTROL_CANDIDATES_PHASE,
    QUALITY_ATTESTATION_FIELDS,
    REFERENCE_FIELDS,
    REFERENCE_SUPPORT_FIELDS,
    RegisteredFile,
    RoleInputRegistration,
    RoleSpec,
    SCORE_MEMBERS,
    SCORE_PROVENANCE_FIELDS,
    StudyStage,
    projection_scope_sha256,
)
from .gt_provider import stage_gt_fields


A1_ROOT = "artifacts/a1-end-to-end-feasibility-v1-005"
A2_ROOT = "artifacts/a2-context-verifier-v1-004"
OUTPUT_RELATIVE = "artifacts/route2-candidate-overlap-v1-001-inputs"
REGISTRATION_RELATIVE = "artifacts/route2-candidate-overlap-v1-001-source-registration.json"
GT_RELATIVE = "artifacts/g1-participant-exclusion-eligibility-v3-final.json"
MAX_REFERENCE_LINE_BYTES = 16 * 1024 * 1024
A1_INPUTS_CODE_SHA256 = "4f0cf752e6cf970a27c177733b539d30a3fbceb165d3e920a749c3e8c0576766"
A1_RUNNER_CODE_SHA256 = "b3d30bf103698153429f53dc6cbab23a55ae7d89155ed99bf0d8148a265a9bdb"
_ROLE_TUPLE_FIELDS = (
    "fit_participants",
    "reference_participants",
    "scored_participants",
    "selection_participants",
    "outer_valid",
)


@dataclass(frozen=True, slots=True)
class PinnedSource:
    """A caller supplied exact source path and previously registered digest."""

    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("source path must be absolute")
        _digest_value(self.sha256)


@dataclass(frozen=True, slots=True)
class ProjectionSources:
    a2_config: PinnedSource
    a2_config_sidecar: PinnedSource
    a2_audit_ready: PinnedSource
    a1_config: PinnedSource
    a1_run_manifest: PinnedSource
    a1_final_checksums: PinnedSource
    a1_input_audit: PinnedSource
    a1_role_graph: PinnedSource
    a1_window_identity: PinnedSource
    a1_score_provenance: PinnedSource
    a1_cache_manifest: PinnedSource
    a1_manifest_audit: PinnedSource
    a2_role_digests: PinnedSource
    g1_eligibility: PinnedSource
    a1_eligibility_alias: PinnedSource
    score_files_by_role: Mapping[str, PinnedSource]
    cache_files_by_record: Mapping[tuple[str, str, str], PinnedSource]
    candidate_rows_by_role: Mapping[str, PinnedSource]


def _source_dict(source: PinnedSource) -> dict[str, str]:
    return {"path": str(source.path), "sha256": source.sha256.lower()}


def _sources_dict(sources: ProjectionSources) -> dict[str, object]:
    return {
        field: _source_dict(getattr(sources, field))
        for field in (
            "a2_config", "a2_config_sidecar", "a2_audit_ready",
            "a1_config", "a1_run_manifest", "a1_final_checksums",
            "a1_input_audit", "a1_role_graph", "a1_window_identity",
            "a1_score_provenance", "a1_cache_manifest", "a1_manifest_audit",
            "a2_role_digests", "g1_eligibility", "a1_eligibility_alias",
        )
    } | {
        "score_files_by_role": {
            role_id: _source_dict(source) for role_id, source in sorted(sources.score_files_by_role.items())
        },
        "cache_files_by_record": [
            {"participant_id": key[0], "record_id": key[1], "session_id": key[2], **_source_dict(source)}
            for key, source in sorted(sources.cache_files_by_record.items())
        ],
        "candidate_rows_by_role": {
            role_id: _source_dict(source) for role_id, source in sorted(sources.candidate_rows_by_role.items())
        },
    }


def _sources_from_dict(value: object) -> ProjectionSources:
    if not isinstance(value, dict):
        raise ValueError("source registration must contain a source object")
    scalar_fields = (
        "a2_config", "a2_config_sidecar", "a2_audit_ready",
        "a1_config", "a1_run_manifest", "a1_final_checksums",
        "a1_input_audit", "a1_role_graph", "a1_window_identity",
        "a1_score_provenance", "a1_cache_manifest", "a1_manifest_audit",
        "a2_role_digests", "g1_eligibility", "a1_eligibility_alias",
    )
    if set(value) != set(scalar_fields) | {
        "score_files_by_role", "cache_files_by_record", "candidate_rows_by_role"
    }:
        raise ValueError("source registration fields differ from the frozen projection schema")

    def parse_source(item: object) -> PinnedSource:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"} or (
            type(item["path"]) is not str or type(item["sha256"]) is not str
        ):
            raise ValueError("source registration entry lacks exact path/hash")
        return PinnedSource(Path(item["path"]), item["sha256"])

    cache_rows = value["cache_files_by_record"]
    score_rows = value["score_files_by_role"]
    candidate_rows = value["candidate_rows_by_role"]
    if not isinstance(cache_rows, list) or not isinstance(score_rows, dict) or not isinstance(candidate_rows, dict):
        raise ValueError("source registration role/cache collections are malformed")
    caches: dict[tuple[str, str, str], PinnedSource] = {}
    for item in cache_rows:
        if not isinstance(item, dict) or set(item) != {
            "participant_id", "record_id", "session_id", "path", "sha256"
        }:
            raise ValueError("cache source registration row is malformed")
        key = (item["participant_id"], item["record_id"], item["session_id"])
        if any(type(part) is not str or not part for part in key) or key in caches:
            raise ValueError("cache source registration identity repeats or is invalid")
        caches[key] = parse_source({"path": item["path"], "sha256": item["sha256"]})
    kwargs = {field: parse_source(value[field]) for field in scalar_fields}
    sources = ProjectionSources(
        **kwargs,
        score_files_by_role={role_id: parse_source(source) for role_id, source in score_rows.items()},
        cache_files_by_record=caches,
        candidate_rows_by_role={role_id: parse_source(source) for role_id, source in candidate_rows.items()},
    )
    if _sources_dict(sources) != value:
        raise ValueError("source registration is not canonical or contains duplicate role keys")
    return sources


def _digest_value(value: str) -> str:
    lowered = value.lower()
    if len(lowered) != 64 or any(char not in "0123456789abcdef" for char in lowered):
        raise ValueError("a frozen SHA-256 digest is required")
    return lowered


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _normalized_relative_hashes(value: object) -> dict[str, str]:
    """Normalize historical Windows separators without discarding hash identity."""

    if not isinstance(value, dict):
        raise ValueError("historical path/hash registry must be an object")
    result: dict[str, str] = {}
    for original, digest in value.items():
        if type(original) is not str or type(digest) is not str:
            raise ValueError("historical path/hash registry entry is malformed")
        name = original.replace("\\", "/")
        if not name or name.startswith("/") or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
            raise ValueError("historical path/hash registry escaped its root")
        if name in result:
            raise ValueError("historical path/hash registry has separator-aliased duplicates")
        result[name] = _digest_value(digest)
    return result


def _fixed_path(workspace: Path, source: PinnedSource, relative: str) -> Path:
    expected = (workspace / relative).resolve()
    actual = source.path.resolve()
    if actual != expected:
        raise PermissionError(f"registered source differs from fixed derived path: {relative}")
    return actual


def _read_json(source: PinnedSource) -> object:
    raw = source.path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.sha256.lower():
        raise ValueError(f"registered source SHA-256 mismatch: {source.path.name}")
    return json.loads(raw)


def _verify_file(source: PinnedSource) -> None:
    digest = hashlib.sha256()
    with source.path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != source.sha256.lower():
        raise ValueError(f"registered source SHA-256 mismatch: {source.path.name}")


def _read_jsonl(source: PinnedSource) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    digest = hashlib.sha256()
    with source.path.open("rb") as stream:
        while raw := stream.readline(MAX_REFERENCE_LINE_BYTES + 1):
            if len(raw) > MAX_REFERENCE_LINE_BYTES:
                raise ValueError(f"registered JSONL row exceeds line bound: {source.path.name}")
            digest.update(raw)
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise ValueError(f"registered JSONL row is not an object: {source.path.name}")
            rows.append(row)
    if digest.hexdigest() != source.sha256.lower():
        raise ValueError(f"registered JSONL SHA-256 mismatch: {source.path.name}")
    return tuple(rows)


def _derived_path(workspace: Path, value: object, *, allowed_root: Path) -> Path:
    if type(value) is not str or not value:
        raise ValueError("derived source path is missing")
    candidate = Path(value.replace("\\", "/"))
    path = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
    try:
        path.relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise PermissionError("derived source path escapes its approved artifact root") from exc
    return path


def _roles(payload: object) -> tuple[Role, ...]:
    if not isinstance(payload, list) or len(payload) != 130:
        raise ValueError("frozen A1 role graph must contain 130 rows")
    roles: list[Role] = []
    expected_keys = set(Role.__dataclass_fields__)
    for row in payload:
        if not isinstance(row, dict) or set(row) != expected_keys:
            raise ValueError("A1 role graph row differs from the frozen Role schema")
        values = dict(row)
        for key in _ROLE_TUPLE_FIELDS:
            if not isinstance(values[key], list) or any(type(item) is not str for item in values[key]):
                raise ValueError(f"role graph {key} must be a string array")
            values[key] = tuple(values[key])
        thresholds = values["thresholds"]
        if not isinstance(thresholds, list) or any(
            type(item) not in (int, float) or not math.isfinite(float(item))
            for item in thresholds
        ):
            raise ValueError("role graph thresholds must be a finite numeric array")
        values["thresholds"] = tuple(float(item) for item in thresholds)
        roles.append(Role(**values))
    outer = [role for role in roles if role.kind == "candidate" and role.inner_fold is None]
    if len(outer) != 5:
        raise ValueError("frozen role graph lacks five outer candidate roles")
    participants = tuple(sorted({person for role in outer for person in role.scored_participants}))
    validate_role_graph(roles, participants)
    if tuple(roles) != build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910):
        raise ValueError("stored role graph differs from the frozen 5/4/4 construction")
    return tuple(roles)


def _global_ids_sha256(global_ids: Sequence[int]) -> str:
    if any(type(value) is not int or value < 0 for value in global_ids):
        raise ValueError("global ID binding must contain exact nonnegative integers")
    return hashlib.sha256(_canonical_json(list(global_ids))).hexdigest()


def _score_global_id_binding(
    source: PinnedSource,
    expected_global_ids: Sequence[int],
) -> dict[str, object]:
    """Read only the approved `ids` member and bind it to role identities."""

    import numpy as np

    _verify_file(source)
    with np.load(source.path, allow_pickle=False) as archive:
        ids = np.asarray(archive["ids"])
        if (
            ids.ndim != 1
            or not np.issubdtype(ids.dtype, np.integer)
            or np.issubdtype(ids.dtype, np.bool_)
            or np.any(ids < 0)
            or np.any(ids > np.iinfo(np.int64).max)
        ):
            raise ValueError("score ids must be one-dimensional nonnegative int64 global IDs")
        actual = [int(value) for value in ids.tolist()]
    expected = list(expected_global_ids)
    if actual != expected:
        raise ValueError("score ids do not match the exact role-scoped A1 global identity order")
    _verify_file(source)
    return {"row_count": len(actual), "global_ids_sha256": _global_ids_sha256(actual)}


def _cache_global_id_binding(
    source: PinnedSource,
    expected_global_ids: Sequence[int],
) -> dict[str, object]:
    """Check approved geometry row counts against the cache's exact global-ID order."""

    import numpy as np

    _verify_file(source)
    expected = list(expected_global_ids)
    if not expected:
        raise ValueError("registered cache has no A1 global window identities")
    with np.load(source.path, allow_pickle=False) as archive:
        for member in CACHE_MEMBERS:
            values = np.asarray(archive[member])
            if values.ndim != 1 or values.size != len(expected):
                raise ValueError(f"cache geometry row count differs from global identities: {member}")
    _verify_file(source)
    return {"row_count": len(expected), "global_ids_sha256": _global_ids_sha256(expected)}


def _prepare_a1_sources(
    workspace: Path,
    sources: ProjectionSources,
    a2_config: Mapping[str, object],
    a2_audit: Mapping[str, object],
    roles: tuple[Role, ...],
) -> dict[str, Any]:
    """Authenticate the accepted A1 run and bind only approved IDs/geometry members."""

    _fixed_path(workspace, sources.a1_config, "configs/a1-end-to-end-feasibility-v1.json")
    _fixed_path(workspace, sources.a1_run_manifest, f"{A1_ROOT}/run-manifest.json")
    _fixed_path(workspace, sources.a1_final_checksums, f"{A1_ROOT}/final-checksums.json")
    _fixed_path(workspace, sources.a1_input_audit, f"{A1_ROOT}/input-audit.json")
    _fixed_path(workspace, sources.a1_window_identity, f"{A1_ROOT}/window-identity.json")
    _fixed_path(workspace, sources.a1_score_provenance, f"{A1_ROOT}/score-provenance.jsonl")
    source_hashes = a2_audit.get("source_hashes")
    if not isinstance(source_hashes, dict):
        raise ValueError("A2-004 audit has no source hash registration")
    expected_source_hashes = {
        "a1_config_sha256": sources.a1_config.sha256,
        "a1_run_manifest_sha256": sources.a1_run_manifest.sha256,
        "a1_window_identity_sha256": sources.a1_window_identity.sha256,
        "a1_score_provenance_sha256": sources.a1_score_provenance.sha256,
        "approved_cache_manifest_sha256": sources.a1_cache_manifest.sha256,
        "approved_manifest_audit_sha256": sources.a1_manifest_audit.sha256,
    }
    if any(source_hashes.get(key) != value.lower() for key, value in expected_source_hashes.items()):
        raise ValueError("A2-004 audit does not bind the registered A1 inputs")
    if sources.a1_final_checksums.sha256.lower() != a2_config.get("source_checksum_sha256"):
        raise ValueError("A1 final checksum manifest differs from A2-004 config")

    a1_config = _read_json(sources.a1_config)
    run = _read_json(sources.a1_run_manifest)
    checksums_payload = _read_json(sources.a1_final_checksums)
    input_audit = _read_json(sources.a1_input_audit)
    identities = _read_json(sources.a1_window_identity)
    score_rows = _read_jsonl(sources.a1_score_provenance)
    cache_manifest = _read_json(sources.a1_cache_manifest)
    manifest_audit = _read_json(sources.a1_manifest_audit)
    if not isinstance(a1_config, dict) or not isinstance(a1_config.get("paths"), dict):
        raise ValueError("A1 frozen config lacks a path contract")
    if not isinstance(run, dict) or run.get("run_schema") != "a1_run_manifest_v1" or (
        run.get("config_sha256") != sources.a1_config.sha256.lower()
        or run.get("input_audit_sha256") != sources.a1_input_audit.sha256.lower()
        or run.get("status") != "AUDIT_READY"
    ):
        raise ValueError("A1 accepted run manifest/config identity differs")
    code_identity = _normalized_relative_hashes(run.get("code_identity"))
    if (
        code_identity.get("src/eating_event/a1/inputs.py") != A1_INPUTS_CODE_SHA256
        or code_identity.get("scripts/run_a1_feasibility.py") != A1_RUNNER_CODE_SHA256
    ):
        raise ValueError("A1 accepted-window code identity is not the reviewed validator")
    if not isinstance(input_audit, dict) or input_audit.get("status") != "READY" or (
        not isinstance(input_audit.get("source_hashes"), dict)
    ):
        raise ValueError("A1 accepted input audit is not READY")
    checksum_source = checksums_payload.get("files", checksums_payload) if isinstance(checksums_payload, dict) else None
    checksum_entries = _normalized_relative_hashes(checksum_source)
    if (
        checksum_entries.get("input-audit.json") != sources.a1_input_audit.sha256.lower()
        or checksum_entries.get("window-identity.json") != sources.a1_window_identity.sha256.lower()
        or checksum_entries.get("score-provenance.jsonl") != sources.a1_score_provenance.sha256.lower()
        or checksum_entries.get("role-graph.json") != sources.a1_role_graph.sha256.lower()
    ):
        raise ValueError("A1 final checksum manifest lacks the registered accepted input chain")
    paths = a1_config["paths"]
    artifact_root = (workspace / "artifacts").resolve()
    cache_root = _derived_path(workspace, paths.get("cache_root"), allowed_root=artifact_root)
    cache_manifest_path = _derived_path(workspace, paths.get("cache_manifest"), allowed_root=artifact_root)
    manifest_audit_path = _derived_path(workspace, paths.get("manifest_audit"), allowed_root=artifact_root)
    eligibility_path = _derived_path(workspace, paths.get("eligibility"), allowed_root=artifact_root)
    _verify_file(sources.a1_eligibility_alias)
    if (
        sources.a1_cache_manifest.path.resolve() != cache_manifest_path
        or sources.a1_manifest_audit.path.resolve() != manifest_audit_path
        or sources.a1_eligibility_alias.path.resolve() != eligibility_path
        or sources.a1_eligibility_alias.sha256.lower() != sources.g1_eligibility.sha256.lower()
    ):
        raise ValueError("A1 approved config paths differ from the registered derived sources")
    if not isinstance(cache_manifest, dict) or not isinstance(cache_manifest.get("entries"), list) or (
        len(cache_manifest["entries"]) != 1127
    ):
        raise ValueError("A1 cache manifest does not contain 1127 approved records")
    if not isinstance(manifest_audit, dict) or not isinstance(manifest_audit.get("records"), list):
        raise ValueError("A1 record audit has no record registration")
    if not isinstance(identities, list) or len(identities) != 632100:
        raise ValueError("A1 global window identity has an unexpected row count")
    if len(score_rows) != 130:
        raise ValueError("A1 score provenance does not contain 130 roles")

    accepted_hashes = input_audit["source_hashes"]
    if any(accepted_hashes.get(key) != source.sha256.lower() for key, source in (
        ("cache_manifest", sources.a1_cache_manifest),
        ("manifest_audit", sources.a1_manifest_audit),
        ("eligibility", sources.a1_eligibility_alias),
    )):
        raise ValueError("A1 accepted input audit differs from registered derived inputs")
    records_by_opaque: dict[str, dict[str, object]] = {}
    for record in manifest_audit["records"]:
        if not isinstance(record, dict):
            raise ValueError("A1 record audit contains a malformed row")
        opaque = record.get("path_or_file_id")
        if opaque is not None and opaque != "":
            if type(opaque) is not str or opaque in records_by_opaque:
                raise ValueError("A1 record audit has a malformed or duplicate opaque key")
            records_by_opaque[opaque] = record
    caches: dict[tuple[str, str, str], dict[str, object]] = {}
    for entry in cache_manifest["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("A1 cache manifest contains a malformed row")
        participant, session = entry.get("participant_id"), entry.get("session_id")
        opaque = entry.get("path", entry.get("path_or_file_id"))
        if any(type(value) is not str or not value for value in (participant, session, opaque)):
            raise ValueError("A1 cache manifest lacks participant/session/opaque identity")
        audit_record = records_by_opaque.get(opaque)
        if not isinstance(audit_record, dict) or (
            audit_record.get("status") != "processed"
            or audit_record.get("participant_id") != participant
            or audit_record.get("session_id") != session
        ):
            raise ValueError("A1 cache record is not bound to a processed record audit")
        path = _derived_path(workspace, entry.get("cache_path"), allowed_root=cache_root)
        record_id = entry.get("record_id") or path.stem
        if type(record_id) is not str or not record_id:
            raise ValueError("A1 cache record ID is invalid")
        key = (participant, record_id, session)
        if key in caches:
            raise ValueError("A1 cache record identity repeats")
        source = sources.cache_files_by_record.get(key)
        if source is None or source.path.resolve() != path or (
            source.sha256.lower() != entry.get("cache_sha256")
            or accepted_hashes.get(f"cache:{path.name}") != source.sha256.lower()
        ):
            raise ValueError("A1 cache registration path/hash differs from approved manifests")
        _verify_file(source)
        caches[key] = {
            "participant_id": participant,
            "record_id": record_id,
            "session_id": session,
            "cache_path": str(path),
            "cache_sha256": source.sha256.lower(),
        }
    if set(sources.cache_files_by_record) != set(caches):
        raise ValueError("A1 cache file registration has missing or extra records")

    global_identity: list[dict[str, object]] = []
    identity_index: dict[tuple[str, str, str, int], int] = {}
    participants = {person for role in roles if role.kind == "candidate" and role.inner_fold is None for person in role.scored_participants}
    identity_rows_by_cache: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for global_index, identity in enumerate(identities):
        if not isinstance(identity, dict) or not {"participant_id", "record_id", "session_id", "row_index"} <= set(identity):
            raise ValueError("A1 global identity row is malformed")
        if any(type(identity[field]) is not str or not identity[field] for field in (
            "participant_id", "record_id", "session_id"
        )) or type(identity["row_index"]) is not int or identity["row_index"] < 0:
            raise ValueError("A1 global identity field is invalid")
        key = (identity["participant_id"], identity["record_id"], identity["session_id"], identity["row_index"])
        if key in identity_index or key[:3] not in caches or key[0] not in participants:
            raise ValueError("A1 global identity duplicates or escapes the approved cache registry")
        identity_index[key] = global_index
        projected_identity = {
            "global_index": global_index,
            "participant_id": key[0],
            "record_id": key[1],
            "session_id": key[2],
            "row_index": key[3],
        }
        global_identity.append(projected_identity)
        identity_rows_by_cache.setdefault(key[:3], []).append(projected_identity)

    cache_global_id_bindings: list[dict[str, object]] = []
    cache_global_id_bindings_by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    for key, row in sorted(caches.items()):
        identity_rows = sorted(
            identity_rows_by_cache.get(key, ()), key=lambda item: int(item["row_index"])
        )
        expected_global_ids = [int(item["global_index"]) for item in identity_rows]
        if [int(item["row_index"]) for item in identity_rows] != list(range(len(identity_rows))):
            raise ValueError("A1 cache row indices are not a complete local sequence")
        source = sources.cache_files_by_record[key]
        binding = _cache_global_id_binding(source, expected_global_ids)
        cache_global_id_bindings_by_key[key] = binding
        cache_global_id_bindings.append({
            "participant_id": key[0],
            "record_id": key[1],
            "session_id": key[2],
            **binding,
        })

    by_role: dict[str, dict[str, object]] = {}
    for row in score_rows:
        role_id = row.get("role_id")
        if type(role_id) is not str or role_id in by_role:
            raise ValueError("A1 score provenance has duplicate or invalid role")
        by_role[role_id] = row
    if set(by_role) != {role.role_id for role in roles}:
        raise ValueError("A1 score provenance role set differs from the frozen role graph")
    candidate_roles = {role.role_id: role for role in roles if role.kind == "candidate"}
    if set(sources.score_files_by_role) != set(candidate_roles):
        raise ValueError("registered score files must cover exactly 105 candidate roles")
    scores: dict[str, dict[str, object]] = {}
    score_global_id_bindings_by_role: dict[str, dict[str, object]] = {}
    for role_id, role in candidate_roles.items():
        row = by_role[role_id]
        if row.get("kind") != "candidate" or tuple(row.get("scored_participants", ())) != role.scored_participants or (
            tuple(row.get("fit_participants", ())) != role.fit_participants
            or tuple(row.get("threshold_reference_participants", ())) != role.reference_participants
            or row.get("input_hashes") != accepted_hashes
            or row.get("run_identity") != run
        ):
            raise ValueError(f"A1 candidate score provenance differs from accepted run/role: {role_id}")
        score_relative = row.get("score_file")
        path = _derived_path(workspace / A1_ROOT, score_relative, allowed_root=workspace / A1_ROOT / "scores")
        source = sources.score_files_by_role[role_id]
        threshold = row.get("threshold")
        if source.path.resolve() != path or source.sha256.lower() != row.get("score_file_sha256") or (
            isinstance(threshold, bool) or not isinstance(threshold, (int, float))
            or not math.isfinite(float(threshold))
            or checksum_entries.get(str(path.relative_to(workspace / A1_ROOT)).replace("\\", "/")) != source.sha256.lower()
        ):
            raise ValueError(f"A1 score path/hash/threshold differs from frozen registration: {role_id}")
        _verify_file(source)
        role_global_ids = [
            int(identity["global_index"])
            for identity in global_identity
            if identity["participant_id"] in set(role.scored_participants)
        ]
        score_binding = _score_global_id_binding(source, role_global_ids)
        score_global_id_bindings_by_role[role_id] = score_binding
        scores[role_id] = {
            "role_id": role_id,
            "score_path": str(path),
            "score_sha256": source.sha256.lower(),
            "threshold_reference": float(threshold),
            "ids_member": "ids",
            "raw_member": "raw",
            "relative_member": "relative",
        }
    return {
        "run_sha256": sources.a1_run_manifest.sha256.lower(),
        "input_audit_sha256": sources.a1_input_audit.sha256.lower(),
        "global_identity": tuple(global_identity),
        "identity_index": identity_index,
        "scores": scores,
        "score_global_id_bindings_by_role": score_global_id_bindings_by_role,
        "caches": caches,
        "cache_global_id_bindings": tuple(cache_global_id_bindings),
        "cache_global_id_bindings_by_key": cache_global_id_bindings_by_key,
    }


def _source_gt_rows(payload: object, participants: set[str]) -> tuple[dict[str, object], ...]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "participant_eligibility_v3":
        raise ValueError("G1 eligibility source has an unexpected schema")
    rows = payload.get("event_eligibility")
    if not isinstance(rows, list) or len(rows) != 281:
        raise ValueError("G1 source does not contain the frozen 281 event rows")
    projected: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for row in rows:
        if not isinstance(row, dict) or not set(GT_FIELDS) <= set(row):
            raise ValueError("G1 source lacks an approved event eligibility field")
        item = {field: row[field] for field in GT_FIELDS}
        participant = item["participant_id"]
        if type(participant) is not str or not participant:
            raise ValueError("G1 participant identity must be a nonempty string")
        for field in ("event_index", "start_ms", "end_ms", "duration_ms"):
            if type(item[field]) is not int:
                raise ValueError(f"G1 {field} must be an exact JSON integer")
        for field in ("training_eligibility", "evaluation_eligibility"):
            if type(item[field]) is not bool:
                raise ValueError(f"G1 {field} must be a JSON boolean")
        # G1 preserves all annotated events, including participants excluded
        # from the frozen model role graph.  Those source rows are valid only
        # when neither stage may use them; keep them in this source projection
        # so the 281-row annotation contract is not silently rewritten.
        if participant not in participants and (
            item["training_eligibility"] or item["evaluation_eligibility"]
        ):
            raise ValueError("eligible G1 event participant is outside the frozen role graph")
        if item["event_index"] < 0 or item["end_ms"] <= item["start_ms"]:
            raise ValueError("G1 event identity or interval is invalid")
        if item["duration_ms"] != item["end_ms"] - item["start_ms"]:
            raise ValueError("G1 duration differs from its interval")
        identity = (participant, item["event_index"])
        if identity in seen:
            raise ValueError("duplicate G1 participant/event index")
        seen.add(identity)
        projected.append(item)
    if sum(bool(row["evaluation_eligibility"]) for row in projected) != 234:
        raise ValueError("G1 evaluation denominator differs from 234")
    return tuple(sorted(projected, key=lambda row: (str(row["participant_id"]), int(row["event_index"]))))


def _source_gt_census(
    rows: Sequence[Mapping[str, object]],
    role_graph_participants: set[str],
) -> dict[str, int | bool]:
    """Record the preserved source/evaluation relationship without filtering rows."""

    if len(rows) != 281:
        raise ValueError("G1 source census requires all 281 event rows")
    source_participants = {str(row["participant_id"]) for row in rows}
    inside = [row for row in rows if str(row["participant_id"]) in role_graph_participants]
    outside = [row for row in rows if str(row["participant_id"]) not in role_graph_participants]
    training_ids = {
        (str(row["participant_id"]), int(row["event_index"]))
        for row in rows if row["training_eligibility"] is True
    }
    evaluation_ids = {
        (str(row["participant_id"]), int(row["event_index"]))
        for row in rows if row["evaluation_eligibility"] is True
    }
    training_only = training_ids - evaluation_ids
    evaluation_only = evaluation_ids - training_ids
    if len(evaluation_ids) != 234:
        raise ValueError("G1 evaluation denominator differs from 234")
    if any(
        str(row["participant_id"]) not in role_graph_participants
        for row in rows
        if row["training_eligibility"] is True or row["evaluation_eligibility"] is True
    ):
        raise ValueError("eligible G1 source rows escape the frozen role graph")
    return {
        "source_event_rows": len(rows),
        "source_participants": len(source_participants),
        "role_graph_participants": len(role_graph_participants),
        "role_graph_participants_with_source_events": len(
            source_participants & role_graph_participants
        ),
        "role_graph_participants_without_source_events": len(
            role_graph_participants - source_participants
        ),
        "source_events_in_role_graph": len(inside),
        "source_events_outside_role_graph": len(outside),
        "outside_role_graph_events_eligible_for_either_phase": sum(
            row["training_eligibility"] is True or row["evaluation_eligibility"] is True
            for row in outside
        ),
        "training_eligible_events": len(training_ids),
        "evaluation_eligible_events": len(evaluation_ids),
        "events_eligible_for_both_phases": len(training_ids & evaluation_ids),
        "training_only_eligible_events": len(training_only),
        "evaluation_only_eligible_events": len(evaluation_only),
        "events_ineligible_for_both_phases": len(rows) - len(training_ids | evaluation_ids),
        "training_and_evaluation_identity_sets_equal": not training_only and not evaluation_only,
    }


def _reference_rows(
    source: PinnedSource,
    role: Role,
    expected_count: int,
    identity_index: Mapping[tuple[str, str, str, int], int],
) -> tuple[dict[str, object], ...]:
    """Parse privileged mixed rows; return only the ten permitted view fields."""

    digest = hashlib.sha256()
    projected: list[dict[str, object]] = []
    seen_candidate_ids: set[str] = set()
    allowed = set(role.scored_participants)
    with source.path.open("rb") as stream:
        while raw := stream.readline(MAX_REFERENCE_LINE_BYTES + 1):
            if len(raw) > MAX_REFERENCE_LINE_BYTES:
                raise ValueError(f"reference source row exceeds line bound: {role.role_id}")
            digest.update(raw)
            row = json.loads(raw)
            if not isinstance(row, dict):
                raise ValueError(f"mixed reference row is not an object: {role.role_id}")
            required = set(REFERENCE_FIELDS) - {"start_ms", "end_ms"}
            if not required <= set(row) or "interval" not in row or "candidate_id" not in row:
                raise ValueError(f"mixed reference row lacks identity/interval/support: {role.role_id}")
            candidate_id = row["candidate_id"]
            if type(candidate_id) is not str or not candidate_id or candidate_id in seen_candidate_ids:
                raise ValueError(f"mixed reference candidate ID is missing or repeated: {role.role_id}")
            seen_candidate_ids.add(candidate_id)
            interval = row["interval"]
            if not isinstance(interval, dict) or not {"start_ms", "end_ms"} <= set(interval):
                raise ValueError(f"mixed reference interval is malformed: {role.role_id}")
            result = {field: row[field] for field in REFERENCE_FIELDS if field not in {"start_ms", "end_ms"}}
            result["start_ms"] = interval["start_ms"]
            result["end_ms"] = interval["end_ms"]
            if set(result) != set(REFERENCE_FIELDS):
                raise ValueError("reference projection has an unexpected field")
            if result["role_id"] != role.role_id or result["participant_id"] not in allowed:
                raise ValueError(f"mixed reference role/participant differs: {role.role_id}")
            if any(type(result[field]) is not str or not result[field] for field in (
                "participant_id", "record_id", "session_id", "component_id", "boundary_kind"
            )):
                raise ValueError(f"reference identity is malformed: {role.role_id}")
            if result["boundary_kind"] != "observed_window_support_component_v1" or result["source_segment_id"] is not None:
                raise ValueError(f"reference boundary/source segment differs: {role.role_id}")
            if type(result["start_ms"]) is not int or type(result["end_ms"]) is not int or result["end_ms"] <= result["start_ms"]:
                raise ValueError(f"reference interval is invalid: {role.role_id}")
            support = result["support_indices"]
            if not isinstance(support, list) or not support:
                raise ValueError(f"reference support is absent: {role.role_id}")
            support_seen: set[tuple[str, str, str, int]] = set()
            clean_support: list[dict[str, object]] = []
            for identity in support:
                if not isinstance(identity, dict) or not set(REFERENCE_SUPPORT_FIELDS) <= set(identity):
                    raise ValueError(f"reference support identity is incomplete: {role.role_id}")
                item = {field: identity[field] for field in REFERENCE_SUPPORT_FIELDS}
                if any(type(item[field]) is not str or not item[field] for field in ("participant_id", "record_id", "session_id")):
                    raise ValueError(f"reference support identity is invalid: {role.role_id}")
                if type(item["row_index"]) is not int or item["row_index"] < 0:
                    raise ValueError(f"reference support row index is invalid: {role.role_id}")
                key = (item["participant_id"], item["record_id"], item["session_id"], item["row_index"])
                if key in support_seen or key not in identity_index or key[:3] != (
                    result["participant_id"], result["record_id"], result["session_id"]
                ):
                    raise ValueError(f"reference support repeats or escapes role identity: {role.role_id}")
                support_seen.add(key)
                clean_support.append(item)
            result["support_indices"] = clean_support
            projected.append(result)
    if digest.hexdigest() != source.sha256.lower() or len(projected) != expected_count:
        raise ValueError(f"reference source hash/count changed: {role.role_id}")
    def sort_key(row: dict[str, object]) -> tuple[object, ...]:
        support_key = tuple(
            identity_index[(item["participant_id"], item["record_id"], item["session_id"], item["row_index"])]
            for item in row["support_indices"]
        )
        return (
            row["role_id"], row["participant_id"], row["record_id"], row["session_id"],
            row["component_id"], row["start_ms"], row["end_ms"], support_key,
            row["boundary_kind"],
        )
    return tuple(sorted(projected, key=sort_key))


def _write_jsonl_exclusive(path: Path, rows: Sequence[dict[str, object]]) -> tuple[str, int]:
    digest = hashlib.sha256()
    with path.open("xb") as stream:
        for row in rows:
            raw = _canonical_json(row) + b"\n"
            stream.write(raw)
            digest.update(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest.hexdigest(), len(rows)


def _write_manifest_exclusive(path: Path, value: dict[str, object]) -> str:
    raw = _canonical_json(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def _write_registry_exclusive(path: Path, value: object) -> str:
    """Write the exact canonical bytes used by the runtime registry digests."""

    raw = _canonical_json(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def _hashed_name(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20] + ".jsonl"


def _pinned_from_declared(path: Path, digest: object) -> PinnedSource:
    if type(digest) is not str:
        raise ValueError("frozen source registry lacks a file SHA-256")
    source = PinnedSource(path.resolve(), digest)
    _verify_file(source)
    return source


def prepare_source_registration(
    *,
    workspace_root: Path,
    registration_path: Path,
) -> tuple[Path, str]:
    """Derive exact input registration from frozen A2/A1 manifests, then stop.

    The result is PREPARED_UNREVIEWED.  An independent reviewer must inspect
    and pin its SHA-256 before ``project_review_views`` can be called.  All
    reads use the fixed derived paths or paths named by their frozen manifests.
    """

    workspace = workspace_root.resolve()
    target = registration_path.resolve()
    if target != (workspace / REGISTRATION_RELATIVE).resolve() or target.exists():
        raise PermissionError("source registration must use its new fixed output path")
    a2_config_path = workspace / "configs/a2-context-verifier-v1-004.json"
    a2_sidecar_path = workspace / "configs/a2-context-verifier-v1-004.sha256"
    audit_path = workspace / A2_ROOT / "audit-ready.json"
    audit_sidecar_path = workspace / A2_ROOT / "audit-ready.sha256"
    config_sidecar = a2_sidecar_path.read_bytes()
    audit_sidecar = audit_sidecar_path.read_bytes()
    config_sha = config_sidecar.decode("ascii").strip().split()[0]
    audit_sha = audit_sidecar.decode("ascii").strip().split()[0]
    a2_config = _pinned_from_declared(a2_config_path, config_sha)
    a2_audit_ready = _pinned_from_declared(audit_path, audit_sha)
    config = _read_json(a2_config)
    audit = _read_json(a2_audit_ready)
    if not isinstance(config, dict) or not isinstance(audit, dict) or (
        config.get("study_id") != "a2-context-verifier-v1-004"
        or config.get("study_output") != A2_ROOT
        or config.get("a1_artifact_root") != A1_ROOT
        or audit.get("status") != "AUDIT_READY"
        or audit.get("study_id") != config["study_id"]
        or audit.get("config_sha256") != a2_config.sha256.lower()
        or config.get("verifier_thresholds") != [0.1, 0.25, 0.5]
        or config.get("candidate_fuse_ms") != 300000
    ):
        raise ValueError("A2-004 config/audit source anchor differs from the frozen study")
    audit_hashes = audit.get("source_hashes")
    materialized_hashes = audit.get("materialized_file_hashes")
    if not isinstance(audit_hashes, dict) or not isinstance(materialized_hashes, dict):
        raise ValueError("A2-004 audit lacks exact source/materialized hashes")
    root = workspace / A1_ROOT
    a1_config = _pinned_from_declared(
        workspace / "configs/a1-end-to-end-feasibility-v1.json", audit_hashes.get("a1_config_sha256")
    )
    a1_run = _pinned_from_declared(root / "run-manifest.json", audit_hashes.get("a1_run_manifest_sha256"))
    a1_final = _pinned_from_declared(root / "final-checksums.json", config.get("source_checksum_sha256"))
    checksums_payload = _read_json(a1_final)
    checksum_source = checksums_payload.get("files", checksums_payload) if isinstance(checksums_payload, dict) else None
    checksum_entries = _normalized_relative_hashes(checksum_source)
    a1_input_audit = _pinned_from_declared(root / "input-audit.json", checksum_entries.get("input-audit.json"))
    a1_roles = _pinned_from_declared(root / "role-graph.json", audit_hashes.get("a1_role_graph_sha256"))
    a1_identity = _pinned_from_declared(root / "window-identity.json", audit_hashes.get("a1_window_identity_sha256"))
    a1_scores = _pinned_from_declared(root / "score-provenance.jsonl", audit_hashes.get("a1_score_provenance_sha256"))
    a2_digests = _pinned_from_declared(
        workspace / A2_ROOT / "materialized/role-digests.json",
        materialized_hashes.get("materialized/role-digests.json"),
    )
    gt = _pinned_from_declared(workspace / GT_RELATIVE, config.get("eligibility_sha256"))
    a1_config_payload = _read_json(a1_config)
    if not isinstance(a1_config_payload, dict) or not isinstance(a1_config_payload.get("paths"), dict):
        raise ValueError("A1 config lacks exact derived manifest paths")
    paths = a1_config_payload["paths"]
    artifacts = workspace / "artifacts"
    cache_manifest_path = _derived_path(workspace, paths.get("cache_manifest"), allowed_root=artifacts)
    manifest_audit_path = _derived_path(workspace, paths.get("manifest_audit"), allowed_root=artifacts)
    a1_eligibility_path = _derived_path(workspace, paths.get("eligibility"), allowed_root=artifacts)
    cache_manifest = _pinned_from_declared(cache_manifest_path, audit_hashes.get("approved_cache_manifest_sha256"))
    manifest_audit = _pinned_from_declared(manifest_audit_path, audit_hashes.get("approved_manifest_audit_sha256"))
    a1_eligibility_alias = _pinned_from_declared(a1_eligibility_path, config.get("eligibility_sha256"))

    roles = _roles(_read_json(a1_roles))
    candidate_roles = {role.role_id: role for role in roles if role.kind == "candidate"}
    score_rows = _read_jsonl(a1_scores)
    score_by_role = {row.get("role_id"): row for row in score_rows if row.get("role_id") in candidate_roles}
    if len(score_by_role) != 105:
        raise ValueError("A1 candidate score provenance cannot register 105 unique roles")
    score_files = {
        role_id: _pinned_from_declared(
            _derived_path(root, row.get("score_file"), allowed_root=root / "scores"),
            row.get("score_file_sha256"),
        )
        for role_id, row in score_by_role.items()
    }
    cache_payload = _read_json(cache_manifest)
    if not isinstance(cache_payload, dict) or not isinstance(cache_payload.get("entries"), list):
        raise ValueError("A1 approved cache manifest lacks record entries")
    cache_root = _derived_path(workspace, paths.get("cache_root"), allowed_root=artifacts)
    cache_files: dict[tuple[str, str, str], PinnedSource] = {}
    for row in cache_payload["entries"]:
        if not isinstance(row, dict):
            raise ValueError("A1 cache manifest has a malformed record")
        path = _derived_path(workspace, row.get("cache_path"), allowed_root=cache_root)
        key = (row.get("participant_id"), row.get("record_id") or path.stem, row.get("session_id"))
        if any(type(part) is not str or not part for part in key) or key in cache_files:
            raise ValueError("A1 cache manifest record identity is missing or repeated")
        cache_files[key] = _pinned_from_declared(path, row.get("cache_sha256"))

    role_digest_rows = _read_json(a2_digests)
    if not isinstance(role_digest_rows, list) or len(role_digest_rows) != 105:
        raise ValueError("A2-004 role digests do not register 105 reference files")
    candidate_files: dict[str, PinnedSource] = {}
    for row in role_digest_rows:
        if not isinstance(row, dict) or type(row.get("role_id")) is not str:
            raise ValueError("A2-004 role digest identity is malformed")
        role_id = row["role_id"]
        relative = row.get("candidate_rows_file")
        if role_id not in candidate_roles or role_id in candidate_files or (
            relative != f"materialized/candidate-rows/{_hashed_name(role_id)}"
        ):
            raise ValueError("A2-004 reference file is missing, duplicated, or outside its role")
        candidate_files[role_id] = _pinned_from_declared(
            workspace / A2_ROOT / relative, materialized_hashes.get(relative)
        )
    sources = ProjectionSources(
        a2_config=a2_config,
        a2_config_sidecar=_pinned_from_declared(
            a2_sidecar_path, hashlib.sha256(config_sidecar).hexdigest()
        ),
        a2_audit_ready=a2_audit_ready,
        a1_config=a1_config,
        a1_run_manifest=a1_run,
        a1_final_checksums=a1_final,
        a1_input_audit=a1_input_audit,
        a1_role_graph=a1_roles,
        a1_window_identity=a1_identity,
        a1_score_provenance=a1_scores,
        a1_cache_manifest=cache_manifest,
        a1_manifest_audit=manifest_audit,
        a2_role_digests=a2_digests,
        g1_eligibility=gt,
        a1_eligibility_alias=a1_eligibility_alias,
        score_files_by_role=score_files,
        cache_files_by_record=cache_files,
        candidate_rows_by_role=candidate_files,
    )
    a1 = _prepare_a1_sources(workspace, sources, config, audit, roles)
    gt_rows = _source_gt_rows(
        _read_json(gt),
        {person for role in roles if role.kind == "candidate" and role.inner_fold is None for person in role.scored_participants},
    )
    role_graph_participants = {
        person for role in roles
        if role.kind == "candidate" and role.inner_fold is None
        for person in role.scored_participants
    }
    registration = {
        "schema": "route2_source_registration_v1",
        "status": "PREPARED_UNREVIEWED",
        "study_id": "route2-candidate-overlap-v1-001",
        "a2_audit_ready_sidecar_path": str(audit_sidecar_path),
        "a2_audit_ready_sidecar_sha256": hashlib.sha256(audit_sidecar).hexdigest(),
        "sources": _sources_dict(sources),
        "score_global_id_bindings_by_role": {
            role_id: binding
            for role_id, binding in sorted(a1["score_global_id_bindings_by_role"].items())
        },
        "cache_global_id_bindings_by_record": list(a1["cache_global_id_bindings"]),
        "g1_event_eligibility_census": _source_gt_census(gt_rows, role_graph_participants),
        "independent_review_id": None,
        "experiment_authorization": None,
    }
    registration_sha = _write_manifest_exclusive(target, registration)
    return target, registration_sha


def project_review_views(
    *,
    workspace_root: Path,
    output_dir: Path,
    source_registration: PinnedSource,
    independent_source_review_id: str,
) -> tuple[Path, str]:
    """Create new, unreviewed physical views from an exact derived-source registry.

    The caller must independently register every path and SHA-256 before this
    function runs.  This function never grants experiment permission or opens
    raw sensor, original metadata, official test, or external data paths.
    """

    workspace = workspace_root.resolve()
    if not independent_source_review_id.strip():
        raise PermissionError("physical view generation requires an independent source-registration review ID")
    _fixed_path(workspace, source_registration, REGISTRATION_RELATIVE)
    registration = _read_json(source_registration)
    if not isinstance(registration, dict) or set(registration) != {
        "schema", "status", "study_id", "a2_audit_ready_sidecar_path",
        "a2_audit_ready_sidecar_sha256", "sources", "g1_event_eligibility_census",
        "score_global_id_bindings_by_role", "cache_global_id_bindings_by_record",
        "independent_review_id", "experiment_authorization",
    } or (
        registration.get("schema") != "route2_source_registration_v1"
        or registration.get("status") != "PREPARED_UNREVIEWED"
        or registration.get("study_id") != "route2-candidate-overlap-v1-001"
    ):
        raise ValueError("source registration has not been prepared for independent review")
    sources = _sources_from_dict(registration.get("sources"))
    if not workspace.is_absolute():
        raise ValueError("workspace root must be absolute")
    destination = output_dir.resolve()
    expected_destination = (workspace / OUTPUT_RELATIVE).resolve()
    if destination != expected_destination or destination.exists():
        raise PermissionError("projection destination must be the new fixed input namespace")
    _fixed_path(workspace, sources.a2_config, "configs/a2-context-verifier-v1-004.json")
    _fixed_path(workspace, sources.a2_config_sidecar, "configs/a2-context-verifier-v1-004.sha256")
    _fixed_path(workspace, sources.a2_audit_ready, f"{A2_ROOT}/audit-ready.json")
    _fixed_path(workspace, sources.a1_role_graph, f"{A1_ROOT}/role-graph.json")
    _fixed_path(workspace, sources.a2_role_digests, f"{A2_ROOT}/materialized/role-digests.json")
    _fixed_path(workspace, sources.g1_eligibility, GT_RELATIVE)

    config = _read_json(sources.a2_config)
    sidecar = sources.a2_config_sidecar.path.read_bytes()
    if hashlib.sha256(sidecar).hexdigest() != sources.a2_config_sidecar.sha256.lower():
        raise ValueError("A2-004 config sidecar hash differs from registration")
    if not isinstance(config, dict) or (
        config.get("study_id") != "a2-context-verifier-v1-004"
        or config.get("study_output") != A2_ROOT
        or config.get("a1_artifact_root") != A1_ROOT
        or config.get("eligibility_sha256") != sources.g1_eligibility.sha256.lower()
        or config.get("verifier_thresholds") != [0.1, 0.25, 0.5]
        or config.get("candidate_fuse_ms") != 300000
    ):
        raise ValueError("A2-004 config differs from the frozen Route 2 source contract")
    if not sidecar.decode("ascii").strip().split() or sidecar.decode("ascii").strip().split()[0].lower() != sources.a2_config.sha256.lower():
        raise ValueError("A2-004 config sidecar does not name the registered config hash")

    audit = _read_json(sources.a2_audit_ready)
    role_graph_payload = _read_json(sources.a1_role_graph)
    digest_rows = _read_json(sources.a2_role_digests)
    eligibility_payload = _read_json(sources.g1_eligibility)
    if not isinstance(audit, dict) or (
        audit.get("status") != "AUDIT_READY"
        or audit.get("study_id") != "a2-context-verifier-v1-004"
        or audit.get("study_output") != A2_ROOT
        or audit.get("config_sha256") != sources.a2_config.sha256.lower()
        or audit.get("role_graph_sha256") != sources.a1_role_graph.sha256.lower()
        or audit.get("candidate_role_count") != 105
        or audit.get("evaluation_gt_count") != 234
    ):
        raise ValueError("A2-004 audit identity differs from the frozen registration")
    source_hashes = audit.get("source_hashes")
    file_hashes = audit.get("materialized_file_hashes")
    if not isinstance(source_hashes, dict) or not isinstance(file_hashes, dict) or (
        source_hashes.get("a1_role_graph_sha256") != sources.a1_role_graph.sha256.lower()
        or source_hashes.get("approved_eligibility_sha256") != sources.g1_eligibility.sha256.lower()
        or file_hashes.get("materialized/role-digests.json") != sources.a2_role_digests.sha256.lower()
    ):
        raise ValueError("A2-004 source/materialized hashes differ from registration")
    if not isinstance(digest_rows, list) or len(digest_rows) != 105 or audit.get("role_digests") != digest_rows:
        raise ValueError("A2-004 role digests differ from AUDIT_READY")
    if not isinstance(eligibility_payload, dict) or (
        eligibility_payload.get("label_eligible_event_denominator_sha256") != config.get("denominator_sha256")
    ):
        raise ValueError("G1 denominator identity differs from A2-004 config")

    roles = _roles(role_graph_payload)
    a1 = _prepare_a1_sources(workspace, sources, config, audit, roles)
    expected_score_global_ids = {
        role_id: binding
        for role_id, binding in sorted(a1["score_global_id_bindings_by_role"].items())
    }
    if registration.get("score_global_id_bindings_by_role") != expected_score_global_ids or (
        registration.get("cache_global_id_bindings_by_record")
        != list(a1["cache_global_id_bindings"])
    ):
        raise ValueError("registered score/cache global-ID bindings differ from the exact derived sources")
    candidate_roles = {role.role_id: role for role in roles if role.kind == "candidate"}
    if set(sources.candidate_rows_by_role) != set(candidate_roles):
        raise ValueError("registered mixed candidate files must cover exactly 105 roles")
    digest_by_role: dict[str, dict[str, object]] = {}
    for item in digest_rows:
        if not isinstance(item, dict) or type(item.get("role_id")) is not str or item["role_id"] in digest_by_role:
            raise ValueError("A2-004 candidate role digest is missing or duplicated")
        digest_by_role[item["role_id"]] = item
    if set(digest_by_role) != set(candidate_roles):
        raise ValueError("A2-004 role digests differ from the A1 candidate graph")
    if sum(item.get("candidate_count", -1) for item in digest_rows) != audit.get("candidate_row_count"):
        raise ValueError("A2-004 candidate counts differ from AUDIT_READY")
    for role_id, role in candidate_roles.items():
        item = digest_by_role[role_id]
        relative = item.get("candidate_rows_file")
        if type(relative) is not str or not relative.startswith("materialized/candidate-rows/"):
            raise ValueError(f"A2-004 candidate file is outside the approved row namespace: {role_id}")
        if relative != f"materialized/candidate-rows/{_hashed_name(role_id)}":
            raise ValueError(f"A2-004 candidate filename differs from role identity: {role_id}")
        source = sources.candidate_rows_by_role[role_id]
        _fixed_path(workspace, source, f"{A2_ROOT}/{relative}")
        if source.sha256.lower() != file_hashes.get(relative):
            raise ValueError(f"A2-004 candidate source hash differs from audit: {role_id}")
        if type(item.get("candidate_count")) is not int or item["candidate_count"] < 0:
            raise ValueError(f"A2-004 candidate count is malformed: {role_id}")
        if not role.scored_participants:
            raise ValueError(f"A1 candidate role has no scored participants: {role_id}")
        _verify_file(source)

    outer_roles = sorted(
        (role for role in candidate_roles.values() if role.inner_fold is None),
        key=lambda role: role.outer_fold,
    )
    training_roles = sorted(
        (role for role in candidate_roles.values() if role.inner_fold is not None),
        key=lambda role: role.role_id,
    )
    inner_by_outer = {
        outer.outer_fold: tuple(sorted(
            (role for role in training_roles if role.outer_fold == outer.outer_fold and role.subinner_fold is None),
            key=lambda role: role.inner_fold or "",
        ))
        for outer in outer_roles
    }
    if len(training_roles) != 100 or any(len(inner) != 4 for inner in inner_by_outer.values()):
        raise ValueError("A1 nested candidate roles differ from the frozen 100/20/5 graph")
    participants = {person for outer in outer_roles for person in outer.scored_participants}
    gt_rows = _source_gt_rows(eligibility_payload, participants)
    gt_census = _source_gt_census(gt_rows, participants)
    if registration.get("g1_event_eligibility_census") != gt_census:
        raise ValueError("G1 source census differs from the reviewed registration")

    # Finish predictable source/schema failures before claiming the one-use
    # output namespace.  Output generation reads each source a second time and
    # rechecks its digest, so a source changed between passes still fails shut.
    for role_id, role in sorted(candidate_roles.items()):
        _reference_rows(
            sources.candidate_rows_by_role[role_id], role,
            digest_by_role[role_id]["candidate_count"], a1["identity_index"],
        )
    if len({_hashed_name(role_id) for role_id in candidate_roles}) != 105:
        raise ValueError("role-scoped output names collide")
    identity_participants = {row["participant_id"] for row in a1["global_identity"]}
    cache_participants = {row["participant_id"] for row in a1["caches"].values()}
    for role_id, role in candidate_roles.items():
        scored = set(role.scored_participants)
        if not scored or not scored <= identity_participants or not scored <= cache_participants:
            raise ValueError(f"A1 role identity/cache projection is incomplete: {role_id}")

    destination.mkdir(parents=False, exist_ok=False)
    reference_dir = destination / "reference"
    identity_dir = destination / "role-identity"
    score_provenance_dir = destination / "score-provenance"
    cache_manifest_dir = destination / "cache-manifest"
    quality_dir = destination / "quality"
    training_dir = destination / "gt-training"
    inner_dir = destination / "gt-inner"
    outer_dir = destination / "gt-outer"
    for directory in (
        reference_dir, identity_dir, score_provenance_dir, cache_manifest_dir,
        quality_dir, training_dir, inner_dir, outer_dir,
    ):
        directory.mkdir(exist_ok=False)
    records: list[dict[str, object]] = []
    role_input_registrations: list[dict[str, object]] = []
    runtime_role_registrations: list[RoleInputRegistration] = []
    reference_projections: dict[str, RegisteredFile] = {}

    for role_id, role in sorted(candidate_roles.items()):
        role_name = _hashed_name(role_id)
        scored = set(role.scored_participants)
        identity_rows = tuple(row for row in a1["global_identity"] if row["participant_id"] in scored)
        cache_rows = tuple(sorted(
            (row for row in a1["caches"].values() if row["participant_id"] in scored),
            key=lambda row: (row["participant_id"], row["record_id"], row["session_id"]),
        ))
        if not identity_rows or not cache_rows or (
            {row["participant_id"] for row in identity_rows} != scored
            or {row["participant_id"] for row in cache_rows} != scored
        ):
            raise ValueError(f"A1 role identity/cache projection is incomplete: {role_id}")
        identity_path = identity_dir / role_name
        score_view_path = score_provenance_dir / role_name
        cache_view_path = cache_manifest_dir / role_name
        quality_path = quality_dir / role_name
        identity_hash, identity_count = _write_jsonl_exclusive(identity_path, identity_rows)
        score_hash, _ = _write_jsonl_exclusive(score_view_path, (a1["scores"][role_id],))
        cache_hash, cache_count = _write_jsonl_exclusive(cache_view_path, cache_rows)
        scored_tuple = role.scored_participants
        views = (
            ("role_identity", identity_path, identity_hash, IDENTITY_FIELDS, identity_count),
            ("score_provenance", score_view_path, score_hash, SCORE_PROVENANCE_FIELDS, 1),
            ("cache_manifest_role", cache_view_path, cache_hash, CACHE_MANIFEST_FIELDS, cache_count),
        )
        for kind, path, file_hash, fields, count in views:
            records.append({
                "kind": kind,
                "phase": "stage_a_input",
                "role_id": role_id,
                "outer_id": role.outer_fold,
                "role_ids": [role_id],
                "participants": list(scored_tuple),
                "fields": list(fields),
                "scope_sha256": projection_scope_sha256(
                    kind, role_id, scored_tuple, fields,
                    role_graph_sha256=sources.a1_role_graph.sha256.lower(),
                ),
                "path": str(path),
                "sha256": file_hash,
                "row_count": count,
            })
        source_score = sources.score_files_by_role[role_id]
        quality_digest_payload = {
            "role_id": role_id,
            "role_graph_sha256": sources.a1_role_graph.sha256.lower(),
            "a1_run_sha256": a1["run_sha256"],
            "a1_input_audit_sha256": a1["input_audit_sha256"],
            "score_sha256": source_score.sha256.lower(),
            "score_provenance_sha256": score_hash,
            "cache_manifest_view_sha256": cache_hash,
            "identity_view_sha256": identity_hash,
            "threshold_reference": a1["scores"][role_id]["threshold_reference"],
            "caches": [
                {
                    "participant_id": row["participant_id"],
                    "record_id": row["record_id"],
                    "session_id": row["session_id"],
                    "cache_path": row["cache_path"],
                    "cache_sha256": row["cache_sha256"],
                }
                for row in cache_rows
            ],
        }
        quality_row = {
            "role_id": role_id,
            "a1_run_sha256": a1["run_sha256"],
            "source_a1_input_audit_sha256": a1["input_audit_sha256"],
            "invalid_runs_upper_bound": 20,
            "window_feature_dim": 111,
            "window_features_finite": True,
            "role_identity_view_sha256": identity_hash,
            "role_source_registry_sha256": hashlib.sha256(_canonical_json(quality_digest_payload)).hexdigest(),
        }
        if tuple(quality_row) != QUALITY_ATTESTATION_FIELDS:
            raise ValueError("quality attestation schema changed during projection")
        quality_hash, _ = _write_jsonl_exclusive(quality_path, (quality_row,))
        records.append({
            "kind": "a1_quality_attestation",
            "phase": "stage_a_input",
            "role_id": role_id,
            "outer_id": role.outer_fold,
            "role_ids": [role_id],
            "participants": list(scored_tuple),
            "fields": list(QUALITY_ATTESTATION_FIELDS),
            "scope_sha256": projection_scope_sha256(
                "a1_quality_attestation", role_id, scored_tuple,
                QUALITY_ATTESTATION_FIELDS,
                role_graph_sha256=sources.a1_role_graph.sha256.lower(),
            ),
            "path": str(quality_path),
            "sha256": quality_hash,
            "row_count": 1,
            "source_path": str(sources.a1_input_audit.path),
            "source_sha256": a1["input_audit_sha256"],
            "evidence": "A1 READY input audit, registered run and reviewed A1 input validator; invalid_runs is a certified upper bound",
        })
        role_spec = RoleSpec(
            role_id=role_id,
            outer_id=role.outer_fold,
            kind=(
                "outer" if role.inner_fold is None else
                "inner_heldout" if role.subinner_fold is None else "inner_train"
            ),
            fit_participants=role.fit_participants,
            scored_participants=role.scored_participants,
        )
        projection_attestation = "PREPARED_UNREVIEWED"
        def projected_file(
            path: Path, digest: str, fields: tuple[str, ...], kind: str,
        ) -> RegisteredFile:
            return RegisteredFile(
                path=str(path), sha256=digest, fields=fields, role_id=role_id,
                projection_attestation=projection_attestation,
                scope_sha256=projection_scope_sha256(
                    kind, role_id, scored_tuple, fields,
                    role_graph_sha256=sources.a1_role_graph.sha256.lower(),
                ),
            )

        runtime_registration = RoleInputRegistration(
            role=role_spec,
            role_graph_sha256=sources.a1_role_graph.sha256.lower(),
            score_npz=RegisteredFile(
                path=str(source_score.path), sha256=source_score.sha256.lower(),
                fields=SCORE_MEMBERS, role_id=role_id,
            ),
            score_provenance=projected_file(
                score_view_path, score_hash, SCORE_PROVENANCE_FIELDS, "score_provenance"
            ),
            manifest_score_path=str(source_score.path),
            cache_files=tuple(
                CacheFileRegistration(
                    participant_id=row["participant_id"],
                    record_id=row["record_id"],
                    session_id=row["session_id"],
                    manifest_cache_path=row["cache_path"],
                    cache_npz=RegisteredFile(
                        path=row["cache_path"], sha256=row["cache_sha256"],
                        fields=CACHE_MEMBERS, role_id=role_id,
                    ),
                )
                for row in cache_rows
            ),
            cache_manifest_view=projected_file(
                cache_view_path, cache_hash, CACHE_MANIFEST_FIELDS, "cache_manifest_role"
            ),
            identity_view=projected_file(identity_path, identity_hash, IDENTITY_FIELDS, "role_identity"),
            quality_attestation=projected_file(
                quality_path, quality_hash, QUALITY_ATTESTATION_FIELDS, "a1_quality_attestation"
            ),
            a1_run_sha256=a1["run_sha256"],
            a1_input_audit_sha256=a1["input_audit_sha256"],
            threshold_reference=a1["scores"][role_id]["threshold_reference"],
        )
        if runtime_registration.quality_source_sha256() != quality_row["role_source_registry_sha256"]:
            raise ValueError(f"A1 quality source digest differs from runtime registration: {role_id}")
        runtime_role_registrations.append(runtime_registration)
        role_input_registrations.append({
            "role_id": role_id,
            "role_graph_sha256": sources.a1_role_graph.sha256.lower(),
            "scored_participants": list(scored_tuple),
            "score_npz": {"path": str(source_score.path), "sha256": source_score.sha256.lower(), "fields": ["ids", "raw", "relative"]},
            "score_global_id_binding": {
                **a1["score_global_id_bindings_by_role"][role_id],
            },
            "score_provenance_view": {"path": str(score_view_path), "sha256": score_hash},
            "cache_manifest_view": {"path": str(cache_view_path), "sha256": cache_hash},
            "identity_view": {"path": str(identity_path), "sha256": identity_hash},
            "quality_attestation": {"path": str(quality_path), "sha256": quality_hash},
            "a1_run_sha256": a1["run_sha256"],
            "a1_input_audit_sha256": a1["input_audit_sha256"],
            "threshold_reference": a1["scores"][role_id]["threshold_reference"],
            "cache_files": [
                {"participant_id": row["participant_id"], "record_id": row["record_id"],
                 "session_id": row["session_id"], "path": row["cache_path"],
                 "sha256": row["cache_sha256"], "fields": ["starts", "ends", "coverage", "crosses_gap"],
                 **a1["cache_global_id_bindings_by_key"][
                     (row["participant_id"], row["record_id"], row["session_id"])
                 ]}
                for row in cache_rows
            ],
        })

    for role_id, role in sorted(candidate_roles.items()):
        rows = _reference_rows(
            sources.candidate_rows_by_role[role_id], role,
            digest_by_role[role_id]["candidate_count"], a1["identity_index"],
        )
        path = reference_dir / _hashed_name(role_id)
        view_hash, row_count = _write_jsonl_exclusive(path, rows)
        records.append({
            "kind": "reference",
            "phase": "stage_a_reference",
            "additional_role_view_phases": [OUTER_CONTROL_CANDIDATES_PHASE],
            "role_id": role_id,
            "outer_id": role.outer_fold,
            "role_ids": [role_id],
            "participants": list(role.scored_participants),
            "fields": list(REFERENCE_FIELDS),
            "scope_sha256": projection_scope_sha256(
                "candidate_reference", role_id, role.scored_participants, REFERENCE_FIELDS,
                role_graph_sha256=sources.a1_role_graph.sha256.lower(),
            ),
            "path": str(path),
            "sha256": view_hash,
            "row_count": row_count,
            "source_path": str(sources.candidate_rows_by_role[role_id].path),
            "source_sha256": sources.candidate_rows_by_role[role_id].sha256.lower(),
        })
        reference_projections[role_id] = RegisteredFile(
            path=str(path), sha256=view_hash, fields=REFERENCE_FIELDS, role_id=role_id,
            projection_attestation="PREPARED_UNREVIEWED",
            scope_sha256=projection_scope_sha256(
                "candidate_reference", role_id, role.scored_participants, REFERENCE_FIELDS,
                role_graph_sha256=sources.a1_role_graph.sha256.lower(),
            ),
        )

    if (
        len(runtime_role_registrations) != 105
        or set(reference_projections) != set(candidate_roles)
        or len({item.role.role_id for item in runtime_role_registrations}) != 105
    ):
        raise ValueError("runtime input and reference registries do not cover the frozen roles")
    role_registry_path = destination / "role-input-registry.json"
    role_registry_sha256 = _write_registry_exclusive(
        role_registry_path,
        [asdict(item) for item in sorted(runtime_role_registrations, key=lambda item: item.role.role_id)],
    )
    reference_registry_path = destination / "reference-registry.json"
    reference_registry_sha256 = _write_registry_exclusive(
        reference_registry_path,
        {
            "role_graph_sha256": sources.a1_role_graph.sha256.lower(),
            "projections": [
                asdict(projection) for _, projection in sorted(reference_projections.items())
            ],
        },
    )

    def write_gt_view(
        stage: StudyStage,
        scope_id: str,
        outer_id: str,
        role_ids: tuple[str, ...],
        whitelist: tuple[str, ...],
        directory: Path,
    ) -> None:
        field_names = stage_gt_fields(stage)
        eligibility_field = field_names[-1]
        allowed = set(whitelist)
        rows = tuple(
            {field: event[field] for field in field_names}
            for event in gt_rows if event["participant_id"] in allowed
        )
        path = directory / _hashed_name(scope_id)
        view_hash, row_count = _write_jsonl_exclusive(path, rows)
        records.append({
            "kind": "gt",
            "phase": stage.value,
            "role_id": scope_id,
            "outer_id": outer_id,
            "role_ids": list(role_ids),
            "participants": list(whitelist),
            "fields": list(field_names),
            "eligibility_field": eligibility_field,
            "eligible_row_count": sum(bool(row[eligibility_field]) for row in rows),
            "scope_sha256": projection_scope_sha256(
                f"gt:{stage.value}:{outer_id}:{','.join(role_ids)}",
                outer_id, whitelist, field_names,
                role_graph_sha256=sources.a1_role_graph.sha256.lower(),
            ),
            "path": str(path),
            "sha256": view_hash,
            "row_count": row_count,
            "source_path": str(sources.g1_eligibility.path),
            "source_sha256": sources.g1_eligibility.sha256.lower(),
            "release_rule": "training_role_only" if stage == StudyStage.TRAIN_LABELS else "after_matching_frozen_prediction_receipt",
        })

    for role in training_roles:
        write_gt_view(
            StudyStage.TRAIN_LABELS, role.role_id, role.outer_fold, (role.role_id,),
            role.scored_participants, training_dir,
        )
    for outer in outer_roles:
        inner_role_ids = tuple(role.role_id for role in inner_by_outer[outer.outer_fold])
        write_gt_view(
            StudyStage.INNER_EVALUATION, outer.outer_fold, outer.outer_fold,
            inner_role_ids, outer.fit_participants, inner_dir,
        )
        write_gt_view(
            StudyStage.OUTER_EVALUATION, outer.outer_fold, outer.outer_fold,
            (outer.role_id,), outer.scored_participants, outer_dir,
        )

    role_scope_projection = {
        "schema": "route2_gt_role_scopes_v1",
        "role_graph_sha256": sources.a1_role_graph.sha256.lower(),
        "training_label_participants": {
            role.role_id: list(role.scored_participants) for role in training_roles
        },
        "training_outer_ids": {
            role.role_id: role.outer_fold for role in training_roles
        },
        "inner_evaluation_roles_by_outer": {
            outer.outer_fold: [role.role_id for role in inner_by_outer[outer.outer_fold]]
            for outer in outer_roles
        },
        "outer_fit_participants": {
            outer.outer_fold: list(outer.fit_participants) for outer in outer_roles
        },
        "outer_role_ids": {
            outer.outer_fold: outer.role_id for outer in outer_roles
        },
        "outer_evaluation_participants": {
            outer.outer_fold: list(outer.scored_participants) for outer in outer_roles
        },
    }
    role_scopes_path = destination / "gt-role-scopes.json"
    role_scopes_sha256 = _write_manifest_exclusive(role_scopes_path, role_scope_projection)
    # The runtime registry contains only view capabilities.  Source paths and
    # GT counts stay in the separate preparation manifest for review and must
    # never enter Stage B before the matching prediction receipt is frozen.
    runtime_gt_keys = (
        "kind", "phase", "role_id", "outer_id", "role_ids", "participants",
        "fields", "scope_sha256", "path", "sha256", "release_rule",
    )
    gt_records = [
        {key: record[key] for key in runtime_gt_keys}
        for record in records if record["kind"] == "gt"
    ]
    if len(gt_records) != 110:
        raise ValueError("GT projection registry lacks 100 training and ten evaluation views")
    gt_view_registry = {
        "schema": "route2_gt_view_registry_v1",
        "role_graph_sha256": sources.a1_role_graph.sha256.lower(),
        "gt_role_scopes_path": str(role_scopes_path),
        "gt_role_scopes_sha256": role_scopes_sha256,
        "views": gt_records,
        "status": "PREPARED_UNREVIEWED",
    }
    gt_registry_path = destination / "gt-view-registry.json"
    gt_registry_sha256 = _write_manifest_exclusive(gt_registry_path, gt_view_registry)

    manifest = {
        "schema": "route2_projection_manifest_v1",
        "status": "PREPARED_UNREVIEWED",
        "study_id": "route2-candidate-overlap-v1-001",
        "source_registration_path": str(source_registration.path),
        "source_registration_sha256": source_registration.sha256.lower(),
        "independent_source_review_id": independent_source_review_id.strip(),
        "a1_role_graph_sha256": sources.a1_role_graph.sha256.lower(),
        "a2_004_audit_ready_sha256": sources.a2_audit_ready.sha256.lower(),
        "a2_004_role_digests_sha256": sources.a2_role_digests.sha256.lower(),
        "a2_004_config_sha256": sources.a2_config.sha256.lower(),
        "g1_eligibility_sha256": sources.g1_eligibility.sha256.lower(),
        "g1_event_eligibility_census": gt_census,
        "reference_view_count": 105,
        "role_input_registration_count": len(role_input_registrations),
        "training_gt_view_count": 100,
        "inner_gt_view_count": 5,
        "outer_gt_view_count": 5,
        "gt_role_scopes_path": str(role_scopes_path),
        "gt_role_scopes_sha256": role_scopes_sha256,
        "gt_view_registry_path": str(gt_registry_path),
        "gt_view_registry_sha256": gt_registry_sha256,
        "role_input_registry_path": str(role_registry_path),
        "role_input_registry_sha256": role_registry_sha256,
        "reference_registry_path": str(reference_registry_path),
        "reference_registry_sha256": reference_registry_sha256,
        "role_input_registrations": role_input_registrations,
        "records": records,
        "independent_review_id": None,
        "experiment_authorization": None,
    }
    if len(records) != 635 or len(role_input_registrations) != 105:
        raise ValueError("projection did not create the complete role/reference/GT view set")
    manifest_path = destination / "projection-manifest.json"
    manifest_hash = _write_manifest_exclusive(manifest_path, manifest)
    return manifest_path, manifest_hash
