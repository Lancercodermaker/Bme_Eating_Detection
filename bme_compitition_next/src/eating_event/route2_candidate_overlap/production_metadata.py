"""Fixed protected A+B metadata decoder; never an input or execution owner.

Installation requires canonical v1 inline or ``route2_production_ab_metadata_v2`` bytes at
INSTALLED_METADATA_PATH, on a native private read-only mount, owned by root
with mode 0400 and one link. The envelope has only ``body`` and
``controller_hmac_sha256``. Its signature is HMAC-SHA256 over HMAC_DOMAIN plus
the canonical body, using the original bootstrap controller key. The body
contains the exact bootstrap identities in _BINDING_FIELDS and ``metadata``.
V1 retains its original domain, caps and four canonical base64 fields. V2 has
its own HMAC domain and a <=1 MiB envelope naming four exact fixed files under
/etc/route2/{STUDY_ID}-metadata/. Authenticate every original binding before
reading those files; pin each raw file before its single JSON decode.

No installation/approval is issued here. Missing protected bytes, original
native start authority, kernel OFD comparison, or frozen identities refuse.
Only controller metadata, pinned source records, and the actual config are read;
no role/reference payload, GT, provider, Stage B, ledger or volume is opened.
The ten-second load bound is cooperative. Read/decode/dataclass/serialization
allocation and actual elapsed time remain unmeasured; this source is not an
installation, budget receipt, or native runtime proof.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass, fields
import hashlib
import hmac
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import threading
import time

from . import admission_bootstrap, contracts, linux_start_clock
from .control_matches import control_match_registry_bytes, require_control_match_projections
from .admission_bootstrap import SupervisorBootstrapProof
from .budget import BudgetLimits, STAGE_A_CAPACITY_UPPER_BOUND_V2, require_fixed_native_budget
from .contracts import (
    CacheFileRegistration, ExperimentApproval, RegisteredFile, RoleInputRegistration,
    RoleSpec, REFERENCE_FIELDS, STUDY_ID, projection_scope_sha256,
)
from .execution import ABReadiness, StageBEquivalenceReceipt
from .external_admission import load_controller_sealed_admission
from .linux_quiescence import (
    _ReadScope, _filesystem, _frame, _mounts, _PROC_SUPER_MAGIC,
    _MAX_FILE_BYTES as _PROC_MAX_FILE_BYTES, _MAX_TOTAL_BYTES as _PROC_MAX_TOTAL_BYTES,
)
from .linux_start_clock import LinuxStartClockProof, require_preimport_start_clock
from .native_failure_capture import NativeFailureCapture
from .path_map import (
    ExactFileMapping, canonical_manifest_bytes, directory_file_mapping,
    _MANIFEST_V1, _MANIFEST_V2,
)
from .phase_observation import _same_open_description
from .source_snapshot import _relative_name


INSTALLED_METADATA_PATH = f"/etc/route2/{STUDY_ID}-ab-metadata.json"
HMAC_DOMAIN = b"route2.production.ab-metadata.v1\x00"
HMAC_DOMAIN_V2 = b"route2.production.ab-metadata.v2\x00"
MAX_METADATA_BYTES = 1 << 24
MAX_METADATA_V2_BYTES = 1 << 20
MAX_REGISTRY_BYTES = 1 << 23
MAX_REGISTRY_V2_BYTES = 1 << 24
MAX_REFERENCE_BYTES = 1 << 20
MAX_PATH_MAP_BYTES = 1 << 23
MAX_PATH_MAP_V2_BYTES = 1 << 24
MAX_CONFIG_BYTES = 1 << 20
MAX_TOTAL_READ_BYTES = 48 << 20
MAX_METADATA_FDS = 64
MAX_LOAD_NS = 10_000_000_000
MAX_JSON_NODES = 1 << 18
MAX_JSON_V2_EVENTS = 1 << 20
MAX_JSON_V2_VALUES = 1 << 19
MAX_JSON_DEPTH = 32
_JSON_CHUNK_BYTES = 1 << 16
_JSON_BOUNDARY = re.compile(rb'["\[\]{}:,\t\n\r ]')
_JSON_STRING_BOUNDARY = re.compile(rb'["\\]')
_CONFIG_RELATIVE = "configs/a2-context-verifier-v1-004.json"
_SCHEMA = "route2_production_ab_metadata_v1"
_SCHEMA_V2 = "route2_production_ab_metadata_v2"
_METADATA_DIRECTORY = f"/etc/route2/{STUDY_ID}-metadata"
_FIXED_METADATA_FILES = (
    ("role_registry_file", "role-input-registry.json"),
    ("reference_registry_file", "reference-registry.json"),
    ("control_final_match_registry_file", "control-final-match-registry.json"),
    ("path_map_manifest_file", "path-map.json"),
)
_LOADER_RELATIVE = "src/eating_event/route2_candidate_overlap/production_metadata.py"
_RUNNER_RELATIVE = "src/eating_event/route2_candidate_overlap/production_runner.py"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_BINDING_FIELDS = frozenset({
    "schema", "study_id", "config_sha256", "seal_sha256",
    "source_snapshot_sha256", "runtime_snapshot_sha256", "independent_review_id",
    "owner_approval_id", "authorization_card_sha256", "frozen_admission_sha256",
})
_METADATA_FIELDS = frozenset({
    "approval", "readiness", "limits", "role_registry_bytes",
    "reference_registry_bytes", "control_final_match_registry_bytes", "path_map_manifest_bytes", "config_path",
})
_METADATA_V2_FIELDS = frozenset({
    "approval", "readiness", "limits", "config_path",
    *(name for name, _ in _FIXED_METADATA_FILES),
})
_LOAD_ENTERED = False
_INSTALLED_METADATA: _InstalledMetadata | None = None


@dataclass(frozen=True, slots=True)
class ProductionABMetadata:
    """Approved records only; fresh data/execution owners are assembled later."""

    approval: ExperimentApproval
    readiness: ABReadiness
    limits: BudgetLimits
    role_registrations: tuple[RoleInputRegistration, ...]
    reference_projections: tuple[RegisteredFile, ...]
    control_final_match_projections: tuple[RegisteredFile, ...]
    role_registry_bytes: bytes
    path_map_manifest_bytes: bytes
    config_path: str


@dataclass(frozen=True, slots=True)
class _ValidatedPathMap:
    """Retained data validation only; no file, mount or installation authority."""

    raw: bytes
    schema: str
    bind_root: str
    mappings: tuple[ExactFileMapping, ...]
    keys: frozenset[tuple[str, str, str, str]]


@dataclass(frozen=True, slots=True)
class _InstalledMetadata:
    proof: SupervisorBootstrapProof
    start: LinuxStartClockProof
    metadata: ProductionABMetadata
    pid: int
    thread: threading.Thread
    frozen: contracts.FrozenAdmission
    role_registry_bytes: bytes
    bindings_bytes: bytes
    record_bytes: bytes
    path_map: _ValidatedPathMap


def _original_error(error: BaseException) -> BaseException:
    report = getattr(error, "failure_capture", None)
    if type(report) is NativeFailureCapture and report.failure is error:
        return report.failure.primary_error if report.failure.primary_error is not None else error
    return error


def _retain_failure(errors: NativeFailureCapture, operation: str, error: BaseException,
                    descriptor: int | None = None) -> BaseException:
    """Keep raw errors in reserved slots before cleanup/report construction."""
    try:
        errors.record(operation, error, descriptor)
    except BaseException as aggregation_error:
        errors.aggregation_error = aggregation_error
        slot = next(errors._cursor, None)
        if slot is None:
            errors.overflowed = True
        else:
            slot.operation = operation
            slot.error = error
            slot.descriptor = descriptor
        slot = next(errors._cursor, None)
        if slot is None:
            errors.overflowed = True
        else:
            slot.operation = "metadata_capture_entry"
            slot.error = aggregation_error
            slot.descriptor = None
    return _original_error(error)


def _checkpoint(reads: _MetadataReads | None) -> None:
    if reads is not None:
        if type(reads) is not _MetadataReads:
            raise PermissionError("metadata checkpoints require the original concrete read owner")
        reads.checkpoint()


def _after_blocking(reads: _MetadataReads | None, primary: BaseException | None) -> None:
    try:
        _checkpoint(reads)
    except BaseException as checkpoint_error:
        if reads is None:
            raise
        # Both raw facts precede any report or further Python helper entry.
        if primary is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = primary
            if primary is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = primary
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_blocking_primary"
                    slot.error = primary
                    slot.descriptor = None
        errors = reads.failures
        if errors.failure.primary_error is None:
            errors.failure.primary_error = checkpoint_error
        if checkpoint_error is not errors.failure:
            if errors.first_error is None:
                errors.first_error = checkpoint_error
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
                errors.aggregation_error = errors._overflow
            else:
                slot.operation = "metadata_blocking_checkpoint"
                slot.error = checkpoint_error
                slot.descriptor = None
        errors.failure.secondary_errors = errors._slots
        errors.failure.aggregation_error = errors.aggregation_error
        raise errors.failure from errors.failure.primary_error


def _canonical(value: object, reads: _MetadataReads | None = None) -> bytes:
    _checkpoint(reads)
    primary = None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except BaseException as exc:
        primary = exc
        if reads is not None:
            # Lock the raw cause before the post-operation checkpoint frame.
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_canonical_serialization"
                    slot.error = exc
                    slot.descriptor = None
        raise
    finally:
        try:
            _after_blocking(reads, primary)
        except BaseException as after_error:
            if reads is None:
                raise
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = after_error
            if after_error is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = after_error
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_after_blocking_dispatch"
                    slot.error = after_error
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error


def _pin(encoded: bytes, digest: str, name: str) -> None:
    if type(encoded) is not bytes or type(digest) is not str or not _SHA.fullmatch(digest.lower()):
        raise PermissionError(f"{name} has no exact frozen SHA-256")
    if hashlib.sha256(encoded).hexdigest() != digest.lower():
        raise PermissionError(f"{name} bytes differ from frozen admission")


def _json(encoded: bytes, maximum: int, *, large: bool = False,
          reads: _MetadataReads | None = None) -> object:
    """Bound allocation before decoding; canonical equality rejects duplicates.

    There are no object hooks, constant hooks, type tags, or caller decoders.
    Duplicate members cannot survive byte equality with the canonical result.
    """
    if type(encoded) is not bytes or not 0 < len(encoded) <= maximum:
        raise PermissionError("production metadata JSON is empty or exceeds its byte bound")
    event_limit = MAX_JSON_V2_EVENTS if large else MAX_JSON_NODES
    value_limit = MAX_JSON_V2_VALUES if large else MAX_JSON_NODES
    depth = nodes = token = 0
    quoted = escaped = False
    # C-backed searches skip ordinary string/token bytes. All state survives
    # chunk boundaries, including a trailing escape or partial number token.
    for start in range(0, len(encoded), _JSON_CHUNK_BYTES):
        _checkpoint(reads)
        chunk = encoded[start:start + _JSON_CHUNK_BYTES]
        offset = 0
        while offset < len(chunk):
            if quoted:
                if escaped:
                    escaped = False
                    offset += 1
                    continue
                match = _JSON_STRING_BOUNDARY.search(chunk, offset)
                if match is None:
                    break
                byte = chunk[match.start()]
                offset = match.end()
                if byte == 92:
                    escaped = True
                else:
                    quoted = False
                continue
            match = _JSON_BOUNDARY.search(chunk, offset)
            end = len(chunk) if match is None else match.start()
            token += end - offset
            if token > 128:
                raise PermissionError("production JSON exceeds its depth/node/number envelope")
            if match is None:
                break
            byte = chunk[end]
            offset = match.end()
            token = 0
            if byte == 34:
                quoted = True
                nodes += 1
            elif byte in (91, 123):
                depth += 1
                nodes += 1
            elif byte in (93, 125):
                depth -= 1
            elif byte in (44, 58):
                nodes += 1
            if depth < 0 or depth > MAX_JSON_DEPTH or nodes > event_limit:
                raise PermissionError("production JSON exceeds its depth/node/number envelope")
        _checkpoint(reads)
    if depth or quoted:
        raise PermissionError("production metadata JSON frame is incomplete")
    try:
        _checkpoint(reads)
        primary = None
        try:
            value = json.loads(encoded.decode("utf-8", errors="strict"))
        except BaseException as exc:
            primary = exc
            if reads is not None:
                errors = reads.failures
                if errors.failure.primary_error is None:
                    errors.failure.primary_error = exc
                if exc is not errors.failure:
                    if errors.first_error is None:
                        errors.first_error = exc
                    slot = next(errors._cursor, None)
                    if slot is None:
                        errors.overflowed = True
                        errors.aggregation_error = errors._overflow
                    else:
                        slot.operation = "metadata_json_load"
                        slot.error = exc
                        slot.descriptor = None
            raise
        finally:
            try:
                _after_blocking(reads, primary)
            except BaseException as after_error:
                if reads is None:
                    raise
                errors = reads.failures
                if errors.failure.primary_error is None:
                    errors.failure.primary_error = after_error
                if after_error is not errors.failure:
                    if errors.first_error is None:
                        errors.first_error = after_error
                    slot = next(errors._cursor, None)
                    if slot is None:
                        errors.overflowed = True
                        errors.aggregation_error = errors._overflow
                    else:
                        slot.operation = "metadata_after_blocking_dispatch"
                        slot.error = after_error
                        slot.descriptor = None
                errors.failure.secondary_errors = errors._slots
                errors.failure.aggregation_error = errors.aggregation_error
                raise errors.failure from errors.failure.primary_error
        # A depth-sized iterator stack avoids allocating one pending tuple for
        # every child of a large list/dict. Count semantic values, not keys.
        pending = [iter((value,))]
        observed = 0
        while pending:
            try:
                item = next(pending[-1])
            except StopIteration:
                pending.pop()
                continue
            level = len(pending) - 1
            observed += 1
            if observed % 1024 == 0:
                _checkpoint(reads)
            kind = type(item)
            if observed > value_limit or level > MAX_JSON_DEPTH:
                raise ValueError("JSON node bound")
            if kind is dict:
                pending.append(iter(item.values()))
            elif kind is list:
                pending.append(iter(item))
            elif kind is float:
                if not math.isfinite(item):
                    raise ValueError("nonfinite JSON number")
            elif kind is int:
                if not -(1 << 63) < item < 1 << 63:
                    raise ValueError("JSON integer bound")
            elif kind is str:
                item.encode("utf-8", errors="strict")
            elif kind not in (bool, type(None)):
                raise ValueError("non-JSON value")
        _checkpoint(reads)
        if _canonical(value, reads) != encoded:
            raise ValueError("noncanonical/duplicate JSON")
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        if reads is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_json_validation"
                    slot.error = exc
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error
        raise PermissionError("production metadata requires strict canonical UTF-8 JSON") from exc
    return value


def _record(value: object, names: frozenset[str]) -> dict:
    if type(value) is not dict or set(value) != names:
        raise PermissionError("production metadata record has unknown or missing fields")
    return value


def _text(value: object, *, empty: bool = False) -> str:
    if (type(value) is not str or len(value) > 4096 or (not value and not empty)
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise PermissionError("production metadata string has the wrong type or bound")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if type(value) is not list or len(value) > 1 << 16:
        raise PermissionError("production metadata string tuple has the wrong type or bound")
    return tuple(_text(item) for item in value)


def _scalar_fields(value: object, names: frozenset[str], *, tuples: frozenset[str] = frozenset(),
                   booleans: frozenset[str] = frozenset()) -> dict:
    record = _record(value, names)
    result = {}
    for name, item in record.items():
        if name in tuples:
            result[name] = _strings(item)
        elif name in booleans:
            if type(item) is not bool:
                raise PermissionError("production approval/readiness flags must be exact JSON booleans")
            result[name] = item
        else:
            result[name] = _text(item, empty=name in {"scope_sha256", "projection_attestation"})
            if name.endswith("sha256") and item and not _SHA.fullmatch(item):
                raise PermissionError("production metadata digest must be lowercase SHA-256")
            if name.endswith("review_id") and not _ID.fullmatch(item):
                raise PermissionError("production metadata review identity is malformed")
    return result


def _file(value: object) -> RegisteredFile:
    return RegisteredFile(**_scalar_fields(value, frozenset(field.name for field in fields(RegisteredFile)),
                                          tuples=frozenset({"fields"})))


def _role(value: object) -> RoleSpec:
    record = _scalar_fields(value, frozenset(field.name for field in fields(RoleSpec)),
                            tuples=frozenset({"fit_participants", "scored_participants"}))
    if record["kind"] not in {"inner_train", "inner_heldout", "outer"}:
        raise PermissionError("production role has an unknown kind")
    if not record["fit_participants"] or not record["scored_participants"]:
        raise PermissionError("production roles require their exact participant scopes")
    return RoleSpec(**record)


def _registration(value: object, reads: _MetadataReads | None = None) -> RoleInputRegistration:
    record = _record(value, frozenset(field.name for field in fields(RoleInputRegistration)))
    scalar_names = frozenset({"role_graph_sha256", "manifest_score_path", "a1_run_sha256", "a1_input_audit_sha256"})
    scalars = _scalar_fields({name: record[name] for name in scalar_names}, scalar_names)
    threshold = record["threshold_reference"]
    if type(threshold) is not float or not math.isfinite(threshold):
        raise PermissionError("production reference threshold must be an exact finite JSON float")
    caches = record["cache_files"]
    if type(caches) is not list or not 0 < len(caches) <= 1 << 16:
        raise PermissionError("production role requires bounded explicit cache registrations")
    decoded = []
    for index, value in enumerate(caches):
        if index % 64 == 0:
            _checkpoint(reads)
        cache = _record(value, frozenset(field.name for field in fields(CacheFileRegistration)))
        decoded.append(CacheFileRegistration(
            participant_id=_text(cache["participant_id"]), record_id=_text(cache["record_id"]),
            session_id=_text(cache["session_id"]), manifest_cache_path=_text(cache["manifest_cache_path"]),
            cache_npz=_file(cache["cache_npz"])))
    return RoleInputRegistration(
        role=_role(record["role"]), score_npz=_file(record["score_npz"]),
        score_provenance=_file(record["score_provenance"]), cache_files=tuple(decoded),
        cache_manifest_view=_file(record["cache_manifest_view"]), identity_view=_file(record["identity_view"]),
        quality_attestation=_file(record["quality_attestation"]), threshold_reference=threshold, **scalars)


def _approval(value: object) -> ExperimentApproval:
    return ExperimentApproval(**_scalar_fields(value, frozenset(field.name for field in fields(ExperimentApproval)),
        tuples=frozenset({"approved_write_volumes"}), booleans=frozenset({"approved"})))


def _readiness(value: object) -> ABReadiness:
    record = _record(value, frozenset(field.name for field in fields(ABReadiness)))
    equivalence = StageBEquivalenceReceipt(**_scalar_fields(record["equivalence"],
        frozenset(field.name for field in fields(StageBEquivalenceReceipt))))
    names = frozenset(record) - {"equivalence"}
    return ABReadiness(equivalence=equivalence, **_scalar_fields(
        {name: record[name] for name in names}, names,
        booleans=frozenset({"all_inputs_explicitly_approved", "stage_b_resources_preapproved"})))


def _limits(value: object) -> BudgetLimits:
    record = _record(value, frozenset(field.name for field in fields(BudgetLimits)))
    if (any(type(item) is not int or not 0 < item < 1 << 63 for name, item in record.items()
            if name != "stage_a_disk_accounting_mode")
            or type(record["stage_a_disk_accounting_mode"]) is not str
            or record["stage_a_disk_accounting_mode"] != STAGE_A_CAPACITY_UPPER_BOUND_V2):
        raise PermissionError("production metadata requires exact integer budgets and explicit V2 accounting")
    return BudgetLimits(**record)


def _raw(value: object, maximum: int, reads: _MetadataReads | None = None) -> bytes:
    if type(value) is not str or not 0 < len(value) <= 4 * ((maximum + 2) // 3):
        raise PermissionError("production raw metadata has no bounded base64 byte frame")
    _checkpoint(reads)
    primary = None
    try:
        encoded = value.encode("ascii", errors="strict")
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= maximum or base64.b64encode(raw) != encoded:
            raise ValueError("noncanonical base64")
    except (UnicodeError, ValueError, binascii.Error) as exc:
        primary = exc
        if reads is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_base64_decode"
                    slot.error = exc
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error
        raise PermissionError("production raw metadata must use canonical base64") from exc
    except BaseException as exc:
        primary = exc
        if reads is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_base64_decode"
                    slot.error = exc
                    slot.descriptor = None
        raise
    finally:
        try:
            _after_blocking(reads, primary)
        except BaseException as after_error:
            if reads is None:
                raise
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = after_error
            if after_error is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = after_error
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_after_blocking_dispatch"
                    slot.error = after_error
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error
    return raw


def _reference_bytes(metadata: ProductionABMetadata, reads: _MetadataReads | None = None) -> bytes:
    return _canonical({"role_graph_sha256": contracts.require_frozen_admission().role_graph_sha256.lower(),
        "projections": [asdict(item) for item in sorted(metadata.reference_projections, key=lambda item: item.role_id)]}, reads)


_CONCRETE_FIELD_TYPES = {
    RegisteredFile: {"fields": (tuple, str)},
    RoleSpec: {"fit_participants": (tuple, str), "scored_participants": (tuple, str)},
    CacheFileRegistration: {"cache_npz": RegisteredFile},
    RoleInputRegistration: {
        "role": RoleSpec, "score_npz": RegisteredFile, "score_provenance": RegisteredFile,
        "cache_files": (tuple, CacheFileRegistration), "cache_manifest_view": RegisteredFile,
        "identity_view": RegisteredFile, "quality_attestation": RegisteredFile, "threshold_reference": float,
    },
    ExperimentApproval: {"approved_write_volumes": (tuple, str), "approved": bool},
    ABReadiness: {"equivalence": StageBEquivalenceReceipt, "all_inputs_explicitly_approved": bool,
                  "stage_b_resources_preapproved": bool},
    StageBEquivalenceReceipt: {},
    BudgetLimits: {field.name: int for field in fields(BudgetLimits)
                  if field.name != "stage_a_disk_accounting_mode"},
}


def _metadata_types(metadata: ProductionABMetadata, reads: _MetadataReads | None = None) -> None:
    """Reject field-type drift that canonical JSON alone could conceal."""
    if (type(metadata) is not ProductionABMetadata
            or type(metadata.role_registry_bytes) is not bytes
            or not 0 < len(metadata.role_registry_bytes) <= MAX_REGISTRY_V2_BYTES
            or type(metadata.path_map_manifest_bytes) is not bytes
            or not 0 < len(metadata.path_map_manifest_bytes) <= MAX_PATH_MAP_V2_BYTES
            or type(metadata.config_path) is not str):
        raise PermissionError("production requires bounded exact concrete metadata fields")
    observed = 0

    def check(item, expected):
        nonlocal observed
        observed += 1
        if observed % 1024 == 0:
            _checkpoint(reads)
        if type(expected) is tuple:
            if type(item) is not tuple or len(item) > 1 << 16:
                raise PermissionError("production metadata tuple type or bound changed")
            for child in item:
                check(child, expected[1])
        elif type(item) is not expected:
            raise PermissionError("production metadata concrete record or scalar type changed")
        elif expected in _CONCRETE_FIELD_TYPES:
            overrides = _CONCRETE_FIELD_TYPES[expected]
            for field in fields(expected):
                check(getattr(item, field.name), overrides.get(field.name, str))
        elif expected is str:
            _text(item, empty=True)
        elif expected is float and not math.isfinite(item):
            raise PermissionError("production metadata finite scalar changed")
        elif expected is int and not 0 < item < 1 << 63:
            raise PermissionError("production metadata integer budget changed")

    check(metadata.approval, ExperimentApproval)
    check(metadata.readiness, ABReadiness)
    check(metadata.limits, BudgetLimits)
    check(metadata.role_registrations, (tuple, RoleInputRegistration))
    check(metadata.reference_projections, (tuple, RegisteredFile))
    check(metadata.control_final_match_projections, (tuple, RegisteredFile))
    _checkpoint(reads)


def _record_bytes(metadata: ProductionABMetadata, reads: _MetadataReads | None = None) -> bytes:
    return _canonical({"approval": asdict(metadata.approval), "readiness": asdict(metadata.readiness),
                       "limits": asdict(metadata.limits), "config_path": metadata.config_path}, reads)


def _retained_map(metadata: ProductionABMetadata) -> _ValidatedPathMap | None:
    original = _INSTALLED_METADATA
    if type(original) is not _InstalledMetadata or original.metadata is not metadata:
        return None
    if (original.pid != os.getpid() or original.thread is not threading.current_thread()
            or original.start is not original.proof.start_clock
            or original.frozen is not contracts.require_frozen_admission()
            or original.proof.frozen_admission is not original.frozen
            or original.role_registry_bytes is not metadata.role_registry_bytes
            or type(original.path_map) is not _ValidatedPathMap
            or original.path_map.raw is not metadata.path_map_manifest_bytes
            or _canonical(asdict(original.proof)) != original.bindings_bytes
            or _record_bytes(metadata) != original.record_bytes):
        raise PermissionError("original installed metadata/bootstrap/data identity changed")
    return original.path_map


def _require_retained_path_map(proof: SupervisorBootstrapProof,
                               metadata: ProductionABMetadata) -> _ValidatedPathMap:
    """Original protected decoded data only; this cannot issue mount authority."""
    with admission_bootstrap._INSTALL_LOCK:
        original = _INSTALLED_METADATA
        if (type(original) is not _InstalledMetadata or original.proof is not proof
                or original.metadata is not metadata or _bound_start(proof) is not original.start):
            raise PermissionError("early path-map assembly requires original retained protected metadata")
        retained = _retained_map(metadata)
        if retained is None:
            raise PermissionError("protected metadata has no original validated path-map data")
        return _verify_path_map(metadata, retained=retained)


def verify_metadata_pins(metadata: ProductionABMetadata) -> tuple[RoleSpec, ...]:
    """Pure record/pin validation, including the bytes used by the real adapters."""
    roles, _ = _verify_metadata_records(metadata)
    return roles


def _verify_metadata_records(metadata: ProductionABMetadata, *, reads: _MetadataReads | None = None,
                             large: bool = True) -> tuple[tuple[RoleSpec, ...], _ValidatedPathMap]:
    _metadata_types(metadata, reads)
    retained = _retained_map(metadata)
    frozen = contracts.require_frozen_admission()
    roles = tuple(item.role for item in metadata.role_registrations)
    ids = tuple(role.role_id for role in roles)
    references = metadata.reference_projections
    if (len(ids) != 105 or len(set(ids)) != 105 or ids != tuple(sorted(ids))
            or len(references) != 105 or tuple(item.role_id for item in references) != ids
            or len({item.path for item in references}) != 105
            or any(item.role_graph_sha256.lower() != frozen.role_graph_sha256.lower()
                   for item in metadata.role_registrations)):
        raise PermissionError("production role/reference records differ from the canonical 105-role graph")
    _checkpoint(reads)
    canonical_roles = _canonical([asdict(item) for item in metadata.role_registrations], reads)
    if canonical_roles != metadata.role_registry_bytes:
        raise PermissionError("decoded role registrations differ from their raw canonical sorted registry")
    _pin(canonical_roles, frozen.role_input_registry_sha256, "role input registry")
    _pin(_reference_bytes(metadata, reads), frozen.reference_registry_sha256, "reference registry")
    _checkpoint(reads)
    require_control_match_projections(metadata.control_final_match_projections, roles)
    _checkpoint(reads)
    for role, reference in zip(roles, references):
        if (reference.fields != REFERENCE_FIELDS or not reference.projection_attestation
                or reference.scope_sha256 != projection_scope_sha256("candidate_reference", role.role_id,
                    role.scored_participants, REFERENCE_FIELDS, role_graph_sha256=frozen.role_graph_sha256.lower())):
            raise PermissionError("production reference lacks the exact reviewed role/field/participant identity")
    metadata.approval.require_full_ab()
    metadata.readiness.require_complete()
    if (metadata.approval.approved is not True
            or metadata.readiness.all_inputs_explicitly_approved is not True
            or metadata.readiness.stage_b_resources_preapproved is not True
            or metadata.readiness.role_input_registry_sha256.lower() != frozen.role_input_registry_sha256.lower()
            or metadata.readiness.reference_registry_sha256.lower() != frozen.reference_registry_sha256.lower()):
        raise PermissionError("production approval/readiness differ from the frozen registry identities")
    require_fixed_native_budget(metadata.limits)
    if (metadata.limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or metadata.limits.digest() != frozen.budget_policy_sha256.lower()):
        raise PermissionError("production budget is not the frozen fixed native V2 policy")
    expected_config = str(PurePosixPath(frozen.source_snapshot_root) / _CONFIG_RELATIVE)
    if type(metadata.config_path) is not str or metadata.config_path != expected_config:
        raise PermissionError("production configPath must identify the actual A2-004 source snapshot config")
    path_map = _verify_path_map(metadata, retained=retained, large=large, reads=reads)
    _checkpoint(reads)
    return roles, path_map


def _verify_path_map(metadata: ProductionABMetadata, *, retained: _ValidatedPathMap | None = None,
                     large: bool = True, reads: _MetadataReads | None = None) -> _ValidatedPathMap:
    frozen = contracts.require_frozen_admission()
    raw = metadata.path_map_manifest_bytes
    _pin(raw, frozen.path_map_sha256, "full path-map manifest")
    if retained is None:
        retained = _retained_map(metadata)
    if retained is None:
        maximum = MAX_PATH_MAP_V2_BYTES if large else MAX_PATH_MAP_BYTES
        record = _record(_json(raw, maximum, large=large, reads=reads),
                         frozenset({"schema", "study_id", "bind_root", "entries"}))
        if (type(record["schema"]) is not str or record["schema"] not in {_MANIFEST_V1, _MANIFEST_V2}
                or type(record["study_id"]) is not str or record["study_id"] != STUDY_ID):
            raise PermissionError("production path-map schema/study identity differs")
        entries = record["entries"]
        if type(entries) is not list or not 0 < len(entries) <= 1 << 16:
            raise PermissionError("production requires bounded complete path-map entries")
        decoded, decoded_keys = [], set()
        for index, value in enumerate(entries):
            if index % 64 == 0:
                _checkpoint(reads)
            # Envelope size/node policy and path-map encoding are independent.
            # Both encodings retain the authenticated envelope's original caps.
            names = frozenset({"logical_path", "sha256", "role_id", "phase"})
            if record["schema"] == _MANIFEST_V1:
                names |= {"bind_path"}
            decoded_item = _scalar_fields(value, names)
            item = (ExactFileMapping(**decoded_item) if record["schema"] == _MANIFEST_V1
                    else directory_file_mapping(**decoded_item))
            decoded.append(item)
            decoded_keys.add(item.key)
        mappings = tuple(decoded)
        bind_root = _text(record["bind_root"])
        retained = _ValidatedPathMap(raw, record["schema"], bind_root, mappings, frozenset(decoded_keys))
    if (type(retained) is not _ValidatedPathMap or retained.raw is not raw
            or retained.schema not in {_MANIFEST_V1, _MANIFEST_V2}
            or type(retained.bind_root) is not str or type(retained.mappings) is not tuple
            or not 0 < len(retained.mappings) <= 1 << 16 or type(retained.keys) is not frozenset):
        raise PermissionError("retained path-map concrete data identity changed")
    mappings = retained.mappings
    root = PurePosixPath(_text(retained.bind_root))
    key_values, bind_paths = set(), set()
    mapping_fields = frozenset(field.name for field in fields(ExactFileMapping))
    for index, item in enumerate(mappings):
        if index % 64 == 0:
            _checkpoint(reads)
        if type(item) is not ExactFileMapping:
            raise PermissionError("retained map contains a foreign concrete mapping")
        _scalar_fields({field: getattr(item, field) for field in mapping_fields}, mapping_fields)
        if root not in PurePosixPath(item.bind_path).parents:
            raise PermissionError("production full path-map lost its original confinement")
        key_values.add(item.key)
        bind_paths.add(item.bind_path)
    keys = frozenset(key_values)
    _checkpoint(reads)
    primary = None
    try:
        canonical_map = canonical_manifest_bytes(str(root), mappings, schema=retained.schema)
    except BaseException as exc:
        primary = exc
        if reads is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_map_serialization"
                    slot.error = exc
                    slot.descriptor = None
        raise
    finally:
        try:
            _after_blocking(reads, primary)
        except BaseException as after_error:
            if reads is None:
                raise
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = after_error
            if after_error is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = after_error
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_after_blocking_dispatch"
                    slot.error = after_error
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error
    if (canonical_map != raw or keys != retained.keys or len(keys) != len(mappings)
            or len(bind_paths) != len(mappings)):
        raise PermissionError("production full path-map is not canonical, unique and confined")
    expected = {(frozen.role_input_registry_path, frozen.role_input_registry_sha256.lower(), "__study__", "preflight_metadata"),
                (frozen.reference_registry_path, frozen.reference_registry_sha256.lower(), "__study__", "preflight_metadata")}
    for registration in metadata.role_registrations:
        _checkpoint(reads)
        for item in (registration.score_npz, registration.score_provenance, registration.cache_manifest_view,
                     registration.identity_view, registration.quality_attestation):
            expected.add((item.path, item.sha256.lower(), registration.role.role_id, "stage_a_input"))
        for index, cache in enumerate(registration.cache_files):
            if index % 64 == 0:
                _checkpoint(reads)
            item = cache.cache_npz
            expected.add((item.path, item.sha256.lower(), registration.role.role_id, "stage_a_input"))
    for item in metadata.reference_projections:
        for phase in ("stage_a_reference", contracts.OUTER_CONTROL_CANDIDATES_PHASE):
            expected.add((item.path, item.sha256.lower(), item.role_id, phase))
    for item in metadata.control_final_match_projections:
        expected.add((item.path, item.sha256.lower(), item.role_id, contracts.OUTER_CONTROL_FINAL_MATCHES_PHASE))
    if not expected <= keys:
        raise PermissionError("production full path-map omits a frozen role/reference/registry identity")
    _checkpoint(reads)
    return retained


def _deadline(start: LinuxStartClockProof, limits: BudgetLimits) -> int:
    require_fixed_native_budget(limits)
    if (limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or limits.digest() != contracts.require_frozen_admission().budget_policy_sha256.lower()):
        raise PermissionError("metadata reads require the original frozen V2 budget")
    deadline = start.invocation_started_monotonic_ns + min(limits.stage_a_wall_ns, limits.total_wall_ns) - 60_000_000_000
    now = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    if now < start.invocation_started_monotonic_ns or now >= deadline:
        raise PermissionError("metadata verification exhausted the original native invocation deadline")
    return deadline


def _bound_start(proof: SupervisorBootstrapProof) -> LinuxStartClockProof:
    """Pure original-object binding; callers hold the bootstrap install lock."""
    issued = admission_bootstrap._ISSUED_BOOTSTRAP
    if (type(proof) is not SupervisorBootstrapProof or issued is None or issued.proof is not proof
            or issued.consumed or issued.pid != os.getpid() or issued.thread is not threading.current_thread()
            or contracts.FROZEN_ADMISSION is not proof.frozen_admission
            or type(proof.frozen_admission) is not contracts.FrozenAdmission
            or type(proof.start_clock) is not LinuxStartClockProof):
        raise PermissionError("metadata loader requires the original live unclaimed bootstrap registry entry")
    return proof.start_clock


def _original_start(proof: SupervisorBootstrapProof) -> LinuxStartClockProof:
    with admission_bootstrap._INSTALL_LOCK:
        start = _bound_start(proof)
        limits = BudgetLimits(stage_a_disk_accounting_mode=STAGE_A_CAPACITY_UPPER_BOUND_V2)
        _deadline(start, limits)  # Before the existing native verifier reads its protected files.
        start = require_preimport_start_clock(start,
            config_sha256=proof.config_sha256, seal_sha256=proof.seal_sha256)
        _deadline(start, limits)
        return start


class _MetadataReads:
    """Held nofollow ancestor/file frames and private KCMP_FILE anchors."""

    def __init__(self, start: LinuxStartClockProof, failures: NativeFailureCapture, entered_ns: int):
        if type(start) is not LinuxStartClockProof or type(failures) is not NativeFailureCapture:
            raise PermissionError("metadata reads require original concrete start and failure ownership")
        self.start = start
        self.pid = os.getpid()
        self.thread = threading.current_thread()
        self.failures = failures
        self.closed = False
        self.limits = BudgetLimits(stage_a_disk_accounting_mode=STAGE_A_CAPACITY_UPPER_BOUND_V2)
        self.scope = _ReadScope()
        self.scope.failures = failures
        self.scope.deadline = min(entered_ns + MAX_LOAD_NS, _deadline(start, self.limits))
        self.held = {}
        self.file_mounts = {}
        self.total = 0

    def checkpoint(self) -> None:
        if self.pid != os.getpid() or self.thread is not threading.current_thread():
            raise PermissionError("metadata read owner changed process or thread")
        if self.total + self.scope.total > MAX_TOTAL_READ_BYTES:
            raise PermissionError("installed metadata/proc reads exceeded their total physical byte bound")
        self.scope.checkpoint()
        _deadline(self.start, self.limits)

    def _fd_slots(self, additional: int) -> None:
        if self.closed or len(self.scope.owned) + additional > MAX_METADATA_FDS:
            raise PermissionError("metadata reads exceeded their once-owned 64-descriptor bound")

    def _read_request(self, maximum: int) -> int:
        """Bound the next real read before its syscall, including EOF probes."""
        self.checkpoint()
        remaining = MAX_TOTAL_READ_BYTES - self.total - self.scope.total
        if maximum <= 0 or remaining <= 0:
            raise PermissionError("metadata/proc read has no remaining physical byte budget")
        return min(maximum, remaining)

    def _hold(self, path: str, descriptor: int, parent: int | None, name: str) -> int:
        if path in self.held:
            raise PermissionError("metadata must retain each original bounded descriptor exactly once")
        before = _frame(os.fstat(descriptor))
        if stat.S_ISREG(before[2]):
            # Distinct private RO bind paths can name one single-link inode.
            # Compare only original held REGULAR files, before any payload
            # read; ancestors are directories and never enter this comparison.
            for held_descriptor, held_anchor, _, _, held_frame in self.held.values():
                if not stat.S_ISREG(held_frame[2]):
                    continue
                self.checkpoint()
                if (_frame(os.fstat(held_descriptor)) != held_frame
                        or _frame(os.fstat(held_anchor)) != held_frame):
                    raise PermissionError("original held metadata file frame changed before alias validation")
                _same_open_description(held_descriptor, held_anchor)
                if before[:2] == held_frame[:2]:
                    raise PermissionError("protected metadata files must have distinct actual device/inode identities")
        self._fd_slots(1)
        # Reserve publication before dup; a returned anchor cannot escape the
        # original once-only scope if list allocation fails.
        self.scope.owned.append(None)
        try:
            anchor = os.dup(descriptor)
        except BaseException:
            self.scope.owned.pop()
            raise
        self.scope.owned[-1] = anchor
        if os.get_inheritable(descriptor) or os.get_inheritable(anchor):
            raise PermissionError("metadata descriptors must not be inherited by workers")
        _same_open_description(descriptor, anchor)  # Native equality; no inode/bool fallback.
        self.held[path] = (descriptor, anchor, parent, name, before)
        return descriptor

    def directory(self, path: str) -> int:
        self.checkpoint()
        admission_bootstrap._canonical_absolute_path(path, "metadata parent")
        if "/" not in self.held:
            self._fd_slots(2)
            self._hold("/", self.scope.directory("/"), None, "/")
        parent = self.held["/"][0]
        current = PurePosixPath("/")
        for name in PurePosixPath(path).parts[1:]:
            current /= name
            key = str(current)
            if key not in self.held:
                self._fd_slots(2)
                self._hold(key, self.scope.open_at(parent, name, directory=True), parent, name)
            parent = self.held[key][0]
        return parent

    def verify(self) -> None:
        self.checkpoint()
        for descriptor, anchor, parent, name, before in self.held.values():
            self.checkpoint()
            if (_frame(os.fstat(descriptor)) != before or _frame(os.fstat(anchor)) != before
                    or _frame(os.stat(name, dir_fd=parent, follow_symlinks=False)) != before):
                raise PermissionError("held metadata ancestor/file frame changed")
            _same_open_description(descriptor, anchor)
        if self.file_mounts:
            mounts = self.mounts()
            for path, mount in self.file_mounts.items():
                self.checkpoint()
                if self.readonly(self.held[path][0], path, mounts) != mount:
                    raise PermissionError("held original metadata file lost its native read-only mount identity")

    def _proc_text(self, parent: int, name: str) -> bytes:
        """Original protected proc FD/frame checks with one joint read budget."""
        self._fd_slots(1)
        descriptor = self.scope.open_at(parent, name)
        primary = None
        try:
            _filesystem(descriptor, _PROC_SUPER_MAGIC)
            before = _frame(os.fstat(descriptor))
            chunks, count = [], 0
            while True:
                # Preserve the original per-file EOF-detection allowance and
                # independent proc sum, while clipping every request to the
                # actual remaining joint budget before entering os.read.
                request = self._read_request(min(_JSON_CHUNK_BYTES,
                    _PROC_MAX_FILE_BYTES - count + 1, _PROC_MAX_TOTAL_BYTES - self.scope.total))
                chunk = os.read(descriptor, request)
                received = len(chunk)
                self.scope.total += received  # Before checkpoint/append/join can fail.
                count += received
                self.checkpoint()
                if count > _PROC_MAX_FILE_BYTES:
                    raise PermissionError("protected proc text exceeded its original per-file byte bound")
                if not chunk:
                    break
                chunks.append(chunk)
            if (before != _frame(os.fstat(descriptor))
                    or before != _frame(os.stat(name, dir_fd=parent, follow_symlinks=False))):
                raise PermissionError("protected proc text identity changed during its bounded read")
            self.checkpoint()
            raw = b"".join(chunks)
            self.checkpoint()
            return raw
        except BaseException as exc:
            primary = exc
            if self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = exc
            else:
                primary = self.failures.failure.primary_error
            if exc is not self.failures.failure:
                if self.failures.first_error is None:
                    self.failures.first_error = exc
                slot = next(self.failures._cursor, None)
                if slot is None:
                    self.failures.overflowed = True
                    self.failures.aggregation_error = self.failures._overflow
                else:
                    slot.operation = "metadata_proc_text"
                    slot.error = exc
                    slot.descriptor = descriptor
            raise
        finally:
            # Lock the original raw error before the close_one Python frame
            # can fail to enter. A dispatch failure leaves this FD in owned
            # for the original scope's final once-only cleanup.
            if primary is not None and self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = primary
            try:
                self.scope.close_one(descriptor, primary_error=primary)
            except BaseException as close_error:
                if self.failures.failure.primary_error is None:
                    self.failures.failure.primary_error = close_error
                if close_error is not self.failures.failure:
                    if self.failures.first_error is None:
                        self.failures.first_error = close_error
                    slot = next(self.failures._cursor, None)
                    if slot is None:
                        self.failures.overflowed = True
                        self.failures.aggregation_error = self.failures._overflow
                    else:
                        slot.operation = "metadata_proc_text_close_dispatch"
                        slot.error = close_error
                        slot.descriptor = descriptor
                self.failures.failure.secondary_errors = self.failures._slots
                self.failures.failure.aggregation_error = self.failures.aggregation_error
                raise self.failures.failure from self.failures.failure.primary_error

    def mounts(self):
        self._fd_slots(2)  # The protected proc walk holds at most two temporary FDs.
        parent = self.scope.directory(f"/proc/{os.getpid()}")
        primary = None
        try:
            self._fd_slots(1)
            return _mounts(self._proc_text(parent, "mountinfo"))
        except BaseException as exc:
            primary = exc
            if self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = exc
            else:
                primary = self.failures.failure.primary_error
            if exc is not self.failures.failure:
                if self.failures.first_error is None:
                    self.failures.first_error = exc
                slot = next(self.failures._cursor, None)
                if slot is None:
                    self.failures.overflowed = True
                    self.failures.aggregation_error = self.failures._overflow
                else:
                    slot.operation = "metadata_mountinfo"
                    slot.error = exc
                    slot.descriptor = parent
            raise
        finally:
            if primary is not None and self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = primary
            try:
                self.scope.close_one(parent, primary_error=primary)
            except BaseException as close_error:
                if self.failures.failure.primary_error is None:
                    self.failures.failure.primary_error = close_error
                if close_error is not self.failures.failure:
                    if self.failures.first_error is None:
                        self.failures.first_error = close_error
                    slot = next(self.failures._cursor, None)
                    if slot is None:
                        self.failures.overflowed = True
                        self.failures.aggregation_error = self.failures._overflow
                    else:
                        slot.operation = "metadata_mountinfo_close_dispatch"
                        slot.error = close_error
                        slot.descriptor = parent
                self.failures.failure.secondary_errors = self.failures._slots
                self.failures.failure.aggregation_error = self.failures.aggregation_error
                raise self.failures.failure from self.failures.failure.primary_error

    def readonly(self, descriptor: int, path: str, mounts):
        self._fd_slots(2)
        parent = self.scope.directory(f"/proc/{os.getpid()}/fdinfo")
        primary = None
        try:
            self._fd_slots(1)
            encoded = self._proc_text(parent, str(descriptor))
        except BaseException as exc:
            primary = exc
            if self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = exc
            else:
                primary = self.failures.failure.primary_error
            if exc is not self.failures.failure:
                if self.failures.first_error is None:
                    self.failures.first_error = exc
                slot = next(self.failures._cursor, None)
                if slot is None:
                    self.failures.overflowed = True
                    self.failures.aggregation_error = self.failures._overflow
                else:
                    slot.operation = "metadata_fdinfo"
                    slot.error = exc
                    slot.descriptor = parent
            raise
        finally:
            if primary is not None and self.failures.failure.primary_error is None:
                self.failures.failure.primary_error = primary
            try:
                self.scope.close_one(parent, primary_error=primary)
            except BaseException as close_error:
                if self.failures.failure.primary_error is None:
                    self.failures.failure.primary_error = close_error
                if close_error is not self.failures.failure:
                    if self.failures.first_error is None:
                        self.failures.first_error = close_error
                    slot = next(self.failures._cursor, None)
                    if slot is None:
                        self.failures.overflowed = True
                        self.failures.aggregation_error = self.failures._overflow
                    else:
                        slot.operation = "metadata_fdinfo_close_dispatch"
                        slot.error = close_error
                        slot.descriptor = parent
                self.failures.failure.secondary_errors = self.failures._slots
                self.failures.failure.aggregation_error = self.failures.aggregation_error
                raise self.failures.failure from self.failures.failure.primary_error
        ids = [line.split(b":", 1)[1].strip() for line in encoded.splitlines() if line.startswith(b"mnt_id:")]
        if len(ids) != 1 or re.fullmatch(rb"[1-9][0-9]*", ids[0]) is None:
            raise PermissionError("metadata descriptor lacks its native kernel mount identity")
        matching = [item for item in mounts if item.mount_id == int(ids[0])]
        covering = [item for item in mounts if PurePosixPath(path).is_relative_to(item.point)]
        if len(matching) != 1 or not covering:
            raise PermissionError("metadata native mount is absent or hidden")
        mount = matching[0]
        info = os.fstat(descriptor)
        if (mount != max(covering, key=lambda item: (len(PurePosixPath(item.point).parts), item.mount_id))
                or "ro" not in mount.options or "rw" in mount.options or mount.optional
                or mount.device != f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
                or not os.fstatvfs(descriptor).f_flag & os.ST_RDONLY):
            raise PermissionError("metadata file requires its visible private native read-only mount")
        return mount

    def read(self, path: str, *, maximum: int, secret: bool = False) -> bytes:
        self.checkpoint()
        admission_bootstrap._canonical_absolute_path(path, "metadata file")
        self.verify()
        parent = self.directory(str(PurePosixPath(path).parent))
        name = PurePosixPath(path).name
        self._fd_slots(2)
        descriptor = self.scope.open_at(parent, name)
        self._hold(path, descriptor, parent, name)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or info.st_mode & 0o222 or not 0 < info.st_size <= maximum
                or (secret and stat.S_IMODE(info.st_mode) != 0o400)):
            raise PermissionError("installed metadata/controller file must be immutable, bounded and single-link")
        mount = self.readonly(descriptor, path, self.mounts())
        self.file_mounts[path] = mount
        chunks, offset = [], 0
        while offset < info.st_size:
            request = self._read_request(min(_JSON_CHUNK_BYTES, info.st_size - offset))
            chunk = os.pread(descriptor, request, offset)
            received = len(chunk)
            self.total += received  # Physical bytes precede any append/checkpoint allocation.
            offset += received
            self.checkpoint()
            if not chunk:
                raise PermissionError("installed metadata read ended before its pinned frame")
            chunks.append(chunk)
            self.checkpoint()
        request = self._read_request(1)
        extra = os.pread(descriptor, request, offset)
        self.total += len(extra)
        self.checkpoint()
        if extra:
            raise PermissionError("installed metadata grew beyond its original frame")
        self.verify()
        if self.readonly(descriptor, path, self.mounts()) != mount:
            raise PermissionError("installed metadata native mount changed during its bounded read")
        self.checkpoint()
        raw = b"".join(chunks)
        self.checkpoint()
        return raw


def _bindings(proof: SupervisorBootstrapProof, schema: str = _SCHEMA,
              reads: _MetadataReads | None = None) -> dict:
    return {"schema": schema, "study_id": STUDY_ID, "config_sha256": proof.config_sha256,
        "seal_sha256": proof.seal_sha256, "source_snapshot_sha256": proof.source_snapshot_sha256,
        "runtime_snapshot_sha256": proof.runtime_snapshot_sha256, "independent_review_id": proof.independent_review_id,
        "owner_approval_id": proof.owner_approval_id, "authorization_card_sha256": proof.authorization_card_sha256,
        "frozen_admission_sha256": hashlib.sha256(_canonical(asdict(proof.frozen_admission), reads)).hexdigest()}


def _fixed_metadata_paths() -> tuple[str, ...]:
    # There is no caller path, resolver, source-root rebasing or factory here.
    return tuple(str(PurePosixPath(_METADATA_DIRECTORY) / basename)
                 for _, basename in _FIXED_METADATA_FILES)


def _refuse_metadata_overlaps(proof: SupervisorBootstrapProof, start: LinuxStartClockProof,
                              config) -> None:
    frozen = proof.frozen_admission
    protected = {
        INSTALLED_METADATA_PATH, start.config_path, config.controller_key_path, config.sealed_admission_path,
        config.source_manifest_path, config.runtime_manifest_path, frozen.source_snapshot_manifest_path,
        frozen.runtime_snapshot_manifest_path, frozen.linux_lock_path, frozen.linux_identity_path,
        frozen.runtime_attestation_path, str(linux_start_clock.PRODUCTION_POLICY_PATH),
        str(PurePosixPath(frozen.source_snapshot_root) / _CONFIG_RELATIVE),
        str(PurePosixPath(frozen.source_snapshot_root) / _LOADER_RELATIVE),
        str(PurePosixPath(frozen.source_snapshot_root) / _RUNNER_RELATIVE),
    }
    with linux_start_clock._START_LOCK:
        issued = linux_start_clock._ISSUED_START
        if issued is None or issued.proof is not start or issued.consumed:
            raise PermissionError("fixed metadata paths lost their original start owner")
        protected.add(str(issued.claim_path))
    protected_paths = tuple(PurePosixPath(value) for value in protected
                            if type(value) is str and value.startswith("/"))
    roots = (PurePosixPath(frozen.source_snapshot_root), PurePosixPath(frozen.runtime_snapshot_root),
             PurePosixPath(config.source_mount_path), PurePosixPath(config.runtime_mount_path))
    for value in _fixed_metadata_paths():
        path = PurePosixPath(value)
        if (any(path == other or path in other.parents or other in path.parents for other in protected_paths)
                or any(path == root or root in path.parents or path in root.parents for root in roots)):
            raise PermissionError("fixed metadata file overlaps protected config/key/seal/source/runtime/envelope")


def _decode_material(encoded: bytes, proof: SupervisorBootstrapProof, key: bytes,
                     reads: _MetadataReads | None, config=None) -> tuple[ProductionABMetadata, _ValidatedPathMap]:
    envelope = _record(_json(encoded, MAX_METADATA_BYTES, reads=reads),
                       frozenset({"body", "controller_hmac_sha256"}))
    body = _record(envelope["body"], _BINDING_FIELDS | {"metadata"})
    schema = body["schema"]
    if type(schema) is not str or schema not in {_SCHEMA, _SCHEMA_V2}:
        raise PermissionError("installed metadata uses an unknown exact envelope schema")
    large = schema == _SCHEMA_V2
    if large and len(encoded) > MAX_METADATA_V2_BYTES:
        raise PermissionError("v2 installed metadata exceeds its one-MiB slim envelope")
    domain = HMAC_DOMAIN_V2 if large else HMAC_DOMAIN
    signature = envelope["controller_hmac_sha256"]
    if (type(signature) is not str or not _SHA.fullmatch(signature)
            or not hmac.compare_digest(signature,
                hmac.new(key, domain + _canonical(body, reads), hashlib.sha256).hexdigest())):
        raise PermissionError("installed metadata does not authenticate with the original root controller key")
    expected_bindings = _bindings(proof, schema, reads)
    if (any(type(body[name]) is not str for name in _BINDING_FIELDS)
            or {name: body[name] for name in _BINDING_FIELDS} != expected_bindings):
        raise PermissionError("installed metadata differs from the original config/seal/review/owner/authorization")
    record = _record(body["metadata"], _METADATA_V2_FIELDS if large else _METADATA_FIELDS)
    frozen = proof.frozen_admission
    if frozen is not contracts.require_frozen_admission():
        raise PermissionError("installed metadata lost its original frozen admission object")
    # Validate all fixed tokens and scalar records before the first external
    # metadata-file read. No caller-supplied paths or callback can replace them.
    approval = _approval(record["approval"])
    readiness = _readiness(record["readiness"])
    limits = _limits(record["limits"])
    config_path = _text(record["config_path"])
    bounds = (MAX_REGISTRY_V2_BYTES if large else MAX_REGISTRY_BYTES, MAX_REFERENCE_BYTES,
              MAX_REFERENCE_BYTES, MAX_PATH_MAP_V2_BYTES if large else MAX_PATH_MAP_BYTES)
    digests = (frozen.role_input_registry_sha256, frozen.reference_registry_sha256,
               frozen.control_final_match_registry_sha256, frozen.path_map_sha256)
    labels = ("raw role registry", "raw reference registry", "raw historical final match registry",
              "raw full path-map manifest")
    if large:
        if type(reads) is not _MetadataReads or reads.start is not proof.start_clock or reads.closed:
            raise PermissionError("v2 metadata requires the original held-file read owner")
        for field, basename in _FIXED_METADATA_FILES:
            if type(record[field]) is not str or record[field] != basename:
                raise PermissionError("v2 metadata requires its exact fixed basename tokens")
        if type(config) is not admission_bootstrap.SupervisorConfig:
            raise PermissionError("fixed v2 paths require the original verified supervisor records")
        _refuse_metadata_overlaps(proof, reads.start, config)
        raw_files = []
        for path, maximum, digest, label in zip(_fixed_metadata_paths(), bounds, digests, labels):
            raw = reads.read(path, maximum=maximum, secret=True)
            _pin(raw, digest, label)  # Frozen raw identity precedes that file's sole decode.
            raw_files.append(raw)
    else:
        raw_files = [_raw(record[name], maximum, reads) for name, maximum in zip(
            ("role_registry_bytes", "reference_registry_bytes", "control_final_match_registry_bytes",
             "path_map_manifest_bytes"), bounds)]
        for raw, digest, label in zip(raw_files, digests, labels):
            _pin(raw, digest, label)
    role_bytes, reference_bytes, control_bytes, map_bytes = raw_files
    roles = _json(role_bytes, bounds[0], large=large, reads=reads)
    if type(roles) is not list or len(roles) != 105:
        raise PermissionError("installed role registry must contain exactly 105 records")
    refs = _record(_json(reference_bytes, MAX_REFERENCE_BYTES, large=large, reads=reads),
                   frozenset({"role_graph_sha256", "projections"}))
    if (refs["role_graph_sha256"] != frozen.role_graph_sha256.lower()
            or type(refs["projections"]) is not list or len(refs["projections"]) != 105):
        raise PermissionError("installed reference registry differs from the frozen 105-role graph")
    controls = _record(_json(control_bytes, MAX_REFERENCE_BYTES, large=large, reads=reads), frozenset({
        "schema", "source_study_id", "source_metrics_sha256", "role_graph_sha256", "projections",
    }))
    if (controls["schema"] != "route2_a2_004_final_match_registry_v1"
            or controls["source_study_id"] != "a2-context-verifier-v1-004"
            or controls["source_metrics_sha256"] != frozen.a2_004_final_metrics_sha256.lower()
            or controls["role_graph_sha256"] != frozen.role_graph_sha256.lower()
            or type(controls["projections"]) is not list or len(controls["projections"]) != 5):
        raise PermissionError("installed historical final match registry differs from reviewed A2-004 identity")
    try:
        decoded_roles = []
        for value in roles:
            _checkpoint(reads)
            decoded_roles.append(_registration(value, reads))
        metadata = ProductionABMetadata(approval=approval, readiness=readiness,
            limits=limits, role_registrations=tuple(decoded_roles),
            reference_projections=tuple(_file(value) for value in refs["projections"]), role_registry_bytes=role_bytes,
            control_final_match_projections=tuple(_file(value) for value in controls["projections"]),
            path_map_manifest_bytes=map_bytes, config_path=config_path)
        _, validated_map = _verify_metadata_records(metadata, reads=reads, large=large)
    except (ValueError, TypeError, RecursionError) as exc:
        if reads is not None:
            errors = reads.failures
            if errors.failure.primary_error is None:
                errors.failure.primary_error = exc
            if exc is not errors.failure:
                if errors.first_error is None:
                    errors.first_error = exc
                slot = next(errors._cursor, None)
                if slot is None:
                    errors.overflowed = True
                    errors.aggregation_error = errors._overflow
                else:
                    slot.operation = "metadata_dataclass_decode"
                    slot.error = exc
                    slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error
        raise PermissionError("installed metadata does not match the exact concrete dataclass contracts") from exc
    if _reference_bytes(metadata, reads) != reference_bytes:
        raise PermissionError("decoded references differ from their raw canonical sorted registry")
    _checkpoint(reads)
    if control_match_registry_bytes(metadata.control_final_match_projections) != control_bytes:
        raise PermissionError("decoded final control matches differ from their raw canonical registry")
    _checkpoint(reads)
    return metadata, validated_map


def _decode(encoded: bytes, proof: SupervisorBootstrapProof, key: bytes) -> ProductionABMetadata:
    """Preserve the original pure inline decoder; fixed v2 reads use the loader."""
    metadata, _ = _decode_material(encoded, proof, key, None)
    return metadata


def _snapshot_config(reads: _MetadataReads, proof: SupervisorBootstrapProof, metadata: ProductionABMetadata) -> None:
    frozen = proof.frozen_admission
    raw = reads.read(frozen.source_snapshot_manifest_path, maximum=admission_bootstrap.MAX_SOURCE_MANIFEST_BYTES)
    _pin(raw, frozen.source_snapshot_sha256, "original source snapshot manifest")
    manifest = _record(_json(raw, admission_bootstrap.MAX_SOURCE_MANIFEST_BYTES, reads=reads),
                       frozenset({"schema", "files"}))
    if manifest["schema"] != "route2_immutable_source_snapshot_v1" or type(manifest["files"]) is not list:
        raise PermissionError("source snapshot manifest does not use the original frozen schema")
    identities = {}
    for index, value in enumerate(manifest["files"]):
        if index % 256 == 0:
            reads.checkpoint()
        record = _record(value, frozenset({"path", "bytes", "sha256"}))
        name = _relative_name(record["path"])
        if (name in identities or type(record["bytes"]) is not int or record["bytes"] < 0
                or type(record["sha256"]) is not str or not _SHA.fullmatch(record["sha256"])):
            raise PermissionError("source snapshot manifest has a repeated or malformed identity")
        identities[name] = (record["bytes"], record["sha256"])
    source = proof.snapshots.source
    if (source.manifest_sha256 != frozen.source_snapshot_sha256.lower()
            or source.file_count != len(identities) or source.total_bytes != sum(size for size, _ in identities.values())
            or _CONFIG_RELATIVE not in identities or identities[_CONFIG_RELATIVE][1] != frozen.a2_004_config_sha256.lower()):
        raise PermissionError("actualconfig lacks its original complete source snapshot pin")
    if (Path(__file__).as_posix() != str(PurePosixPath(frozen.source_snapshot_root) / _LOADER_RELATIVE)
            or _LOADER_RELATIVE not in identities or _RUNNER_RELATIVE not in identities):
        raise PermissionError("concrete metadata loader/runner must be installed in the original pinned source snapshot")
    encoded = reads.read(metadata.config_path, maximum=MAX_CONFIG_BYTES)
    mount = reads.file_mounts[metadata.config_path]
    original_mount = proof.snapshots.source_mount
    if (mount.mount_id != original_mount.mount_id or mount.point != frozen.source_snapshot_root
            or mount.point != original_mount.mount_point or mount.device != original_mount.major_minor
            or mount.filesystem != original_mount.filesystem):
        raise PermissionError("actualconfig is not on the original source snapshot's native read-only mount")
    if len(encoded) != identities[_CONFIG_RELATIVE][0]:
        raise PermissionError("actualconfig size differs from the original source manifest")
    _pin(encoded, frozen.a2_004_config_sha256, "actual A2-004 config")


def _read_installed_metadata(proof: SupervisorBootstrapProof, errors: NativeFailureCapture) -> ProductionABMetadata:
    """Read only the fixed installation in the original unclaimed interpreter.

    The public loader owns the preallocated raw-error buffer and consumes its
    genuine bootstrap on every failure. No caller read/decoder callback exists.
    """
    global _LOAD_ENTERED, _INSTALLED_METADATA
    reads = None
    primary = None
    try:
        with admission_bootstrap._INSTALL_LOCK:
            _bound_start(proof)  # A foreign proof cannot start or consume a loader attempt.
            if _LOAD_ENTERED:
                raise PermissionError("fixed production metadata installation has already been attempted")
            _LOAD_ENTERED = True
            entered_ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        start = _original_start(proof)
        admission_bootstrap._require_linux_root()
        reads = _MetadataReads(start, errors, entered_ns)
        bindings_bytes = _canonical(asdict(proof), reads)
        config_bytes = reads.read(start.config_path, maximum=admission_bootstrap.MAX_SUPERVISOR_CONFIG_BYTES, secret=True)
        _pin(config_bytes, proof.config_sha256, "original supervisor config")
        config = admission_bootstrap.parse_supervisor_config(config_bytes)
        admission_bootstrap._require_frozen_bindings(config, proof.frozen_admission)
        if (config.independent_review_id != proof.independent_review_id or config.owner_approval_id != proof.owner_approval_id
                or config.authorization_card_sha256 != proof.authorization_card_sha256
                or proof.study_id != STUDY_ID or proof.source_snapshot_sha256 != config.source_snapshot_sha256
                or proof.runtime_snapshot_sha256 != config.runtime_snapshot_sha256):
            raise PermissionError("metadata installation differs from original supervisor identities")
        key = reads.read(config.controller_key_path, maximum=admission_bootstrap.MAX_CONTROLLER_KEY_BYTES, secret=True)
        with linux_start_clock._START_LOCK:
            original = linux_start_clock._ISSUED_START
            if (original is None or original.proof is not start or original.consumed
                    or original.thread is not threading.current_thread() or len(key) < 32
                    or hashlib.sha256(key).hexdigest() != original.controller_key_sha256):
                raise PermissionError("metadata HMAC key lost its original unclaimed start registry binding")
        seal = reads.read(config.sealed_admission_path, maximum=admission_bootstrap.MAX_SEALED_ADMISSION_BYTES, secret=True)
        _pin(seal, proof.seal_sha256, "original admission seal")
        frozen = load_controller_sealed_admission(seal, controller_key=key,
            expected_source_snapshot_sha256=proof.source_snapshot_sha256,
            expected_runtime_snapshot_sha256=proof.runtime_snapshot_sha256,
            expected_review_id=proof.independent_review_id, expected_owner_approval_id=proof.owner_approval_id,
            expected_authorization_card_sha256=proof.authorization_card_sha256)
        if frozen != proof.frozen_admission:
            raise PermissionError("original admission seal changed its frozen metadata identities")
        if INSTALLED_METADATA_PATH in {start.config_path, config.controller_key_path, config.sealed_admission_path,
                                      config.source_manifest_path, config.runtime_manifest_path}:
            raise PermissionError("fixed metadata installation overlaps another protected controller file")
        installed = reads.read(INSTALLED_METADATA_PATH, maximum=MAX_METADATA_BYTES, secret=True)
        reads.checkpoint()
        metadata, validated_map = _decode_material(installed, proof, key, reads, config)
        reads.checkpoint()
        _snapshot_config(reads, proof, metadata)
        reads.verify()
        if _original_start(proof) is not start:
            raise PermissionError("metadata verification lost its original live native start")
        if _canonical(asdict(proof), reads) != bindings_bytes:
            raise PermissionError("original bootstrap/source records changed during metadata verification")
        reads.checkpoint()
        candidate = _InstalledMetadata(proof, start, metadata, os.getpid(), threading.current_thread(),
            proof.frozen_admission, metadata.role_registry_bytes, bindings_bytes,
            _record_bytes(metadata, reads), validated_map)
        reads.verify()
        reads.checkpoint()
    except BaseException as exc:
        primary = exc
        if errors.failure.primary_error is None:
            errors.failure.primary_error = exc
        else:
            primary = errors.failure.primary_error
        if exc is not errors.failure:
            if errors.first_error is None:
                errors.first_error = exc
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
                errors.aggregation_error = errors._overflow
            else:
                slot.operation = "metadata_load_primary"
                slot.error = exc
                slot.descriptor = None
        raise
    finally:
        if reads is not None:
            reads.closed = True  # Consume this cleanup attempt before entering close.
            if primary is not None and errors.failure.primary_error is None:
                errors.failure.primary_error = primary
            try:
                reads.scope.close(primary_error=primary)
            except BaseException as close_error:
                if errors.failure.primary_error is None:
                    errors.failure.primary_error = close_error
                if primary is None:
                    primary = errors.failure.primary_error
                if close_error is not errors.failure:
                    if errors.first_error is None:
                        errors.first_error = close_error
                    slot = next(errors._cursor, None)
                    if slot is None:
                        errors.overflowed = True
                        errors.aggregation_error = errors._overflow
                    else:
                        slot.operation = "metadata_scope_close_dispatch"
                        slot.error = close_error
                        slot.descriptor = None
                # A close-dispatch failure can leave unconsumed slots. Attempt
                # only those slots; consumed descriptor integers are not retried.
                while reads.scope.owned:
                    descriptor = reads.scope.owned.pop()
                    try:
                        os.close(descriptor)
                    except BaseException as remaining_error:
                        if errors.first_error is None:
                            errors.first_error = remaining_error
                        slot = next(errors._cursor, None)
                        if slot is None:
                            errors.overflowed = True
                            errors.aggregation_error = errors._overflow
                        else:
                            slot.operation = "metadata_remaining_close"
                            slot.error = remaining_error
                            slot.descriptor = descriptor
                errors.failure.secondary_errors = errors._slots
                errors.failure.aggregation_error = errors.aggregation_error
                raise errors.failure from errors.failure.primary_error
    reads.checkpoint()
    if reads.scope.failures is not errors:
        raise PermissionError("metadata cleanup lost its original shared failure buffer")
    if (errors.failure.primary_error is not None or errors.first_error is not None
            or errors.aggregation_error is not None or errors.overflowed):
        if errors.failure.primary_error is None:
            errors.failure.primary_error = (errors.first_error if errors.first_error is not None
                else errors.aggregation_error if errors.aggregation_error is not None else errors._overflow)
        errors.raise_failure(errors.failure.primary_error)
    # Registration follows complete config/source/start/held-FD revalidation
    # and successful once-only cleanup; the map cache never grants mount proof.
    _INSTALLED_METADATA = candidate
    return metadata


def _burn_genuine_bootstrap(proof: SupervisorBootstrapProof) -> None:
    """Consume this caller's original handoff; a foreign proof cannot burn it."""
    with admission_bootstrap._INSTALL_LOCK:
        issued = admission_bootstrap._ISSUED_BOOTSTRAP
        owned = (type(proof) is SupervisorBootstrapProof and issued is not None
                 and issued.proof is proof and not issued.consumed
                 and issued.pid == os.getpid() and issued.thread is threading.current_thread())
    if not owned:
        return
    # Claim consumes this original handoff before native clock validation.
    # Its raw error remains a secondary fact even when consumption succeeded.
    admission_bootstrap.claim_bootstrap_for_ab(proof)


def load_installed_metadata(proof: SupervisorBootstrapProof) -> ProductionABMetadata:
    """Load once; every refusal, including early/cleanup failures, burns ownership."""
    try:
        errors = NativeFailureCapture(1024)  # Before original-start checks or any FD/read.
    except BaseException as allocation_error:
        # No loader resource exists yet. Preserve both raw errors by chaining
        # if even the reserved buffer could not be allocated; still consume
        # this original handoff once, never a foreign proof's handoff.
        try:
            _burn_genuine_bootstrap(proof)
        except BaseException as burn_error:
            raise allocation_error from burn_error
        raise
    try:
        return _read_installed_metadata(proof, errors)
    except BaseException as exc:
        if errors.failure.primary_error is None:
            errors.failure.primary_error = exc
        primary = errors.failure.primary_error
        # Keep recording inline here: failure to enter a record helper must
        # neither replace the locked primary nor skip bootstrap consumption.
        if exc is not errors.failure:
            if errors.first_error is None:
                errors.first_error = exc
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
                errors.aggregation_error = errors._overflow
            else:
                slot.operation = "metadata_loader_refusal"
                slot.error = exc
                slot.descriptor = None
        try:
            _burn_genuine_bootstrap(proof)
        except BaseException as burn_error:
            if errors.first_error is None:
                errors.first_error = burn_error
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
                errors.aggregation_error = errors._overflow
            else:
                slot.operation = "metadata_bootstrap_consumption"
                slot.error = burn_error
                slot.descriptor = None
        try:
            errors.raise_failure(primary)
        except BaseException as report_error:
            if report_error is errors.failure:
                raise
            errors.aggregation_error = report_error
            slot = next(errors._cursor, None)
            if slot is None:
                errors.overflowed = True
            else:
                slot.operation = "metadata_report_dispatch"
                slot.error = report_error
                slot.descriptor = None
            errors.failure.secondary_errors = errors._slots
            errors.failure.aggregation_error = errors.aggregation_error
            raise errors.failure from errors.failure.primary_error


def require_installed_metadata(proof: SupervisorBootstrapProof, metadata: ProductionABMetadata) -> None:
    """Copied/caller-constructed records cannot replace the protected installation."""
    original = _INSTALLED_METADATA
    if (type(original) is not _InstalledMetadata or original.proof is not proof
            or original.metadata is not metadata or original.pid != os.getpid()
            or original.thread is not threading.current_thread() or original.start is not proof.start_clock):
        raise PermissionError("production assembly requires the original authenticated installed metadata object")
    if _original_start(proof) is not original.start:
        raise PermissionError("installed metadata lost its original unclaimed bootstrap/start binding")
    # This remains data validation plus the original native-start check. It
    # reuses no closed FD or cached mount as installation/runtime authority.
    verify_metadata_pins(metadata)


__all__ = ["ProductionABMetadata", "load_installed_metadata", "require_installed_metadata", "verify_metadata_pins"]
