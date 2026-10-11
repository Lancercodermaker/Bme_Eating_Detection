"""Historical A2-004 final matches, visible only to an outer GT child.

The parent validates five metadata registrations without opening their files.
The child consumes a reviewed physical projection of the saved final matcher
output, never candidate coverage or a replay of the control evaluator. This
reader does not create projections, publish mounts or issue permission.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat

from .contracts import (
    CONTROL_FINAL_MATCH_FIELDS, OUTER_CONTROL_FINAL_MATCHES_PHASE,
    RegisteredFile, RoleSpec, StudyStage, projection_scope_sha256,
    require_frozen_admission,
)
from .gt_provider import TruthReadScope
from .native_failure_capture import NativeFailureCapture
from .path_map import ExactPathMap


MAX_CONTROL_MATCH_BYTES = 1 << 20
MAX_CONTROL_MATCHES = 234


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def control_match_registry_bytes(projections: tuple[RegisteredFile, ...]) -> bytes:
    frozen = require_frozen_admission()
    return _canonical({
        "schema": "route2_a2_004_final_match_registry_v1",
        "source_study_id": "a2-context-verifier-v1-004",
        "source_metrics_sha256": frozen.a2_004_final_metrics_sha256.lower(),
        "role_graph_sha256": frozen.role_graph_sha256.lower(),
        "projections": [asdict(item) for item in projections],
    })


def require_control_match_projections(
    projections: tuple[RegisteredFile, ...], roles: tuple[RoleSpec, ...],
) -> None:
    """Validate only sealed metadata; historical GT identities stay unopened."""
    frozen = require_frozen_admission()
    if (type(projections) is not tuple or len(projections) != 5
            or any(type(item) is not RegisteredFile for item in projections)
            or type(roles) is not tuple or any(type(role) is not RoleSpec for role in roles)):
        raise PermissionError("final control matches require five exact reviewed projections")
    outer = {role.outer_id: role for role in roles if role.kind == "outer"}
    if (len(outer) != 5 or tuple(item.role_id for item in projections) != tuple(sorted(outer))
            or len({item.path for item in projections}) != 5):
        raise PermissionError("final control match projections differ from the five outer folds")
    for item in projections:
        role = outer[item.role_id]
        expected_path = PureWindowsPath(frozen.gt_input_root_path) / "a2-004-final-matches" / (
            hashlib.sha256(item.role_id.encode("utf-8")).hexdigest()[:20] + ".json"
        )
        if (item.path != str(expected_path) or item.fields != CONTROL_FINAL_MATCH_FIELDS
                or type(item.projection_attestation) is not str or not item.projection_attestation.strip()
                or item.scope_sha256 != projection_scope_sha256(
                    "a2_004_final_matches", item.role_id, role.scored_participants,
                    CONTROL_FINAL_MATCH_FIELDS, role_graph_sha256=frozen.role_graph_sha256.lower())):
            raise PermissionError("final control match projection lacks exact source/role/field review")
    if hashlib.sha256(control_match_registry_bytes(projections)).hexdigest() != frozen.control_final_match_registry_sha256.lower():
        raise PermissionError("final control match registry differs from frozen admission")


class HistoricalControlMatchStore:
    """Metadata-only store; it cannot return any historical raw GT identity."""

    def __init__(self, projections: tuple[RegisteredFile, ...], roles: tuple[RoleSpec, ...],
                 path_map: ExactPathMap):
        if type(path_map) is not ExactPathMap:
            raise PermissionError("final control matches require the exact reviewed path map")
        self.projections, self.roles, self.path_map = projections, roles, path_map
        self.require_pinned_registration()

    def require_pinned_registration(self) -> None:
        frozen = require_frozen_admission()
        if self.path_map.manifest_sha256 != frozen.path_map_sha256.lower():
            raise PermissionError("final control match path map differs from frozen admission")
        require_control_match_projections(self.projections, self.roles)
        for item in self.projections:
            self.path_map.require_registered(item.path, item.sha256, role_id=item.role_id,
                                             phase=OUTER_CONTROL_FINAL_MATCHES_PHASE)

    def registered_for(self, scope: TruthReadScope) -> RegisteredFile:
        if type(scope) is not TruthReadScope or scope.stage is not StudyStage.OUTER_EVALUATION:
            raise PermissionError("historical final matches are available only after outer prediction freeze")
        self.require_pinned_registration()
        item = next((item for item in self.projections if item.role_id == scope.outer_id), None)
        if item is None or item.scope_sha256 != projection_scope_sha256(
                "a2_004_final_matches", scope.outer_id, scope.participants,
                CONTROL_FINAL_MATCH_FIELDS, role_graph_sha256=scope.role_graph_sha256):
            raise PermissionError("historical final matches escape the exact outer participant scope")
        return item


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("historical final match projection repeats a JSON field")
        result[key] = value
    return result


def read_control_final_matches(*, scope: TruthReadScope, registered: RegisteredFile,
                               path: Path, source_metrics_sha256: str) -> tuple[str, ...]:
    """Read an already released readonly object, hash and parse the same FD.

    The native phase producer must additionally prove publication, sandbox,
    same-key delivery, exit and revocation for this historical result object.
    No check here substitutes for that still-missing producer.
    """
    if (type(scope) is not TruthReadScope or scope.stage is not StudyStage.OUTER_EVALUATION
            or type(registered) is not RegisteredFile or registered.role_id != scope.outer_id
            or registered.fields != CONTROL_FINAL_MATCH_FIELDS or not registered.projection_attestation
            or registered.scope_sha256 != projection_scope_sha256(
                "a2_004_final_matches", scope.outer_id, scope.participants,
                CONTROL_FINAL_MATCH_FIELDS, role_graph_sha256=scope.role_graph_sha256)
            or type(source_metrics_sha256) is not str or len(source_metrics_sha256) != 64
            or any(char not in "0123456789abcdef" for char in source_metrics_sha256)):
        raise PermissionError("outer child lacks its approved historical final match identity")
    errors = NativeFailureCapture(4)
    descriptor = None
    primary = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(descriptor)
        frame = (before.st_dev, before.st_ino, before.st_mode, before.st_uid, before.st_nlink,
                 before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_CONTROL_MATCH_BYTES
                or not os.fstatvfs(descriptor).f_flag & os.ST_RDONLY):
            raise PermissionError("historical final matches are not a bounded root-owned readonly object")
        body = bytearray()
        while block := os.read(descriptor, min(65536, MAX_CONTROL_MATCH_BYTES + 1 - len(body))):
            body.extend(block)
            if len(body) > MAX_CONTROL_MATCH_BYTES:
                raise ValueError("historical final match projection exceeds its byte bound")
        after = os.fstat(descriptor)
        if (frame != (after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_nlink,
                      after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                or len(body) != before.st_size or hashlib.sha256(body).hexdigest() != registered.sha256.lower()):
            raise PermissionError("historical final match object drifted or differs from its reviewed hash")
        value = json.loads(body, object_pairs_hook=_unique_object)
        fields = {"schema", "source_study_id", "source_metrics_sha256", "role_graph_sha256",
                  "outer_id", "matched_gt"}
        if (type(value) is not dict or set(value) != fields
                or value["schema"] != "route2_a2_004_final_matches_v1"
                or value["source_study_id"] != "a2-context-verifier-v1-004"
                or value["source_metrics_sha256"] != source_metrics_sha256
                or value["role_graph_sha256"] != scope.role_graph_sha256
                or value["outer_id"] != scope.outer_id
                or type(value["matched_gt"]) is not list or len(value["matched_gt"]) > MAX_CONTROL_MATCHES
                or _canonical(value) != body):
            raise PermissionError("historical final matches are not the reviewed canonical A2-004 projection")
        identities = []
        previous = None
        for row in value["matched_gt"]:
            if (type(row) is not dict or set(row) != set(CONTROL_FINAL_MATCH_FIELDS)
                    or type(row["participant_id"]) is not str or row["participant_id"] not in scope.participants
                    or type(row["event_index"]) is not int or row["event_index"] < 0):
                raise PermissionError("historical final match row escapes its physical projection scope")
            key = (row["participant_id"], row["event_index"])
            if previous is not None and key <= previous:
                raise ValueError("historical final match identities repeat or are unsorted")
            previous = key
            identities.append(f"{key[0]}:{key[1]}")
        return tuple(identities)
    except BaseException as exc:
        primary = exc
        errors.failure.primary_error = exc
        raise
    finally:
        if descriptor is not None:
            owned, descriptor = descriptor, None
            try:
                os.close(owned)
            except BaseException as close_error:
                errors.failure.primary_error = primary if primary is not None else close_error
                errors.first_error = close_error
                errors._slots[0].operation = "control_final_matches_close"
                errors._slots[0].error = close_error
                errors._slots[0].descriptor = owned
                raise errors.failure from primary
