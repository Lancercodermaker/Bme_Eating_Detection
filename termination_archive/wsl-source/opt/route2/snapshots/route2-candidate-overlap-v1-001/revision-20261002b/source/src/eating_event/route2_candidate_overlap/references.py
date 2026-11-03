"""Readers for independently approved, physically projected reference views."""

from __future__ import annotations

from collections.abc import Iterator
import hashlib
import json
from typing import Any

from .candidates import ReferenceInterval
from .contracts import (
    OUTER_CONTROL_CANDIDATES_PHASE,
    REFERENCE_FIELDS,
    REFERENCE_SUPPORT_FIELDS,
    RegisteredFile,
    RoleSpec,
    projection_scope_sha256,
    require_frozen_admission,
)
from .inputs import LazyRoleLoader
from .path_map import ExactPathMap

MAX_REFERENCE_LINE_BYTES = 16 * 1024 * 1024


def iter_reference_rows(
    registered: RegisteredFile,
    *,
    path_map: ExactPathMap,
    role_id: str,
    allowed_participants: tuple[str, ...],
    identity_index: dict[tuple[str, str, str, int], int],
    phase: str,
) -> Iterator[ReferenceInterval]:
    """Read only an approved sanitized projection, never mixed legacy rows."""

    if registered.role_id != role_id or registered.fields != REFERENCE_FIELDS:
        raise PermissionError("reference view is not registered for this role/projection")
    if phase not in {"stage_a_reference", OUTER_CONTROL_CANDIDATES_PHASE}:
        raise PermissionError("reference view phase is not an approved role-view purpose")
    if not registered.projection_attestation:
        raise PermissionError("reference projection lacks independent field-isolation review")
    allowed = set(allowed_participants)
    previous: tuple[object, ...] | None = None
    with path_map.open_verified(
        registered.path,
        registered.sha256,
        role_id=role_id,
        phase=phase,
    ) as stream:
        while raw := stream.readline(MAX_REFERENCE_LINE_BYTES + 1):
            if len(raw) > MAX_REFERENCE_LINE_BYTES:
                raise ValueError("reference row exceeds the frozen line bound")
            row = json.loads(raw)
            if not isinstance(row, dict) or set(row) != set(REFERENCE_FIELDS):
                raise PermissionError("reference input is not physically field-projected")
            if (
                row["role_id"] != role_id
                or row["participant_id"] not in allowed
                or not all(isinstance(row[field], str) and row[field] for field in (
                    "participant_id",
                    "record_id",
                    "session_id",
                    "component_id",
                    "boundary_kind",
                ))
                or row["boundary_kind"] != "observed_window_support_component_v1"
                or row["source_segment_id"] is not None
            ):
                raise ValueError("reference row identity/boundary is invalid")
            if not isinstance(row["support_indices"], list):
                raise ValueError("reference support identities must be a list")
            support_indices: list[int] = []
            for support_identity in row["support_indices"]:
                if (
                    not isinstance(support_identity, dict)
                    or set(support_identity) != set(REFERENCE_SUPPORT_FIELDS)
                    or not all(
                        isinstance(support_identity[field], str) and support_identity[field]
                        for field in ("participant_id", "record_id", "session_id")
                    )
                    or isinstance(support_identity["row_index"], bool)
                    or not isinstance(support_identity["row_index"], int)
                    or support_identity["row_index"] < 0
                ):
                    raise ValueError("support identity is outside the frozen identity projection")
                support_identity_key = (
                    support_identity["participant_id"],
                    support_identity["record_id"],
                    support_identity["session_id"],
                    support_identity["row_index"],
                )
                try:
                    global_index = identity_index[support_identity_key]
                except KeyError as exc:
                    raise ValueError("reference support identity is not bound to this role") from exc
                if support_identity_key[:3] != (
                    row["participant_id"],
                    row["record_id"],
                    row["session_id"],
                ):
                    raise ValueError("reference support crosses its participant/record/session")
                support_indices.append(global_index)
            if (
                len(set(support_indices)) != len(support_indices)
                or isinstance(row["start_ms"], bool)
                or not isinstance(row["start_ms"], int)
                or isinstance(row["end_ms"], bool)
                or not isinstance(row["end_ms"], int)
                or row["end_ms"] <= row["start_ms"]
            ):
                raise ValueError("reference interval/support values are invalid")
            key = (
                row["role_id"],
                row["participant_id"],
                row["record_id"],
                row["session_id"],
                row["component_id"],
                int(row["start_ms"]),
                int(row["end_ms"]),
                tuple(support_indices),
                row["boundary_kind"],
                row["source_segment_id"],
            )
            if previous is not None and key < previous:
                raise ValueError("reference projection is not in canonical sorted order")
            previous = key
            yield ReferenceInterval(
                role_id=str(row["role_id"]),
                participant_id=str(row["participant_id"]),
                record_id=str(row["record_id"]),
                session_id=str(row["session_id"]),
                component_id=str(row["component_id"]),
                start_ms=int(row["start_ms"]),
                end_ms=int(row["end_ms"]),
                support_indices=tuple(support_indices),
                boundary_kind=str(row["boundary_kind"]),
                source_segment_id=row["source_segment_id"],
            )


class ApprovedReferenceStore:
    """Exact 105-role map of reviewed physical projection files."""

    def __init__(
        self,
        roles: tuple[RoleSpec, ...],
        projections: dict[str, RegisteredFile],
        identity_loader: LazyRoleLoader,
        path_map: ExactPathMap,
    ):
        if type(identity_loader) is not LazyRoleLoader:
            raise PermissionError("reference views require the exact reviewed role loader")
        if type(path_map) is not ExactPathMap or path_map is not identity_loader.path_map:
            raise PermissionError("reference views require the loader's active exact path map")
        if len(roles) != 105 or len({role.role_id for role in roles}) != 105:
            raise ValueError("reference store requires the frozen 105-role graph")
        if set(projections) != {role.role_id for role in roles}:
            raise PermissionError("reference projection registry must bind every exact role")
        if len({item.path for item in projections.values()}) != 105:
            raise PermissionError("reference projections must have distinct role-scoped physical paths")
        if tuple(identity_loader.role_specs) != roles:
            raise PermissionError("reference and score/cache role registries differ")
        for role in roles:
            projection = projections[role.role_id]
            if (
                projection.role_id != role.role_id
                or projection.fields != REFERENCE_FIELDS
                or not projection.projection_attestation
                or projection.scope_sha256 != projection_scope_sha256(
                    "candidate_reference",
                    role.role_id,
                    role.scored_participants,
                    REFERENCE_FIELDS,
                    role_graph_sha256=identity_loader.role_graph_sha256,
                )
            ):
                raise PermissionError("reference projection lacks exact role/field review")
            path_map.require_registered(
                projection.path, projection.sha256,
                role_id=role.role_id,
                phase="stage_a_reference",
            )
            path_map.require_registered(
                projection.path, projection.sha256,
                role_id=role.role_id,
                phase=OUTER_CONTROL_CANDIDATES_PHASE,
            )
        self._roles = {role.role_id: role for role in roles}
        self._projections = dict(projections)
        self._identity_loader = identity_loader
        self.path_map = path_map
        self.roles = roles
        self.role_graph_sha256 = identity_loader.role_graph_sha256
        registry_payload = [
            {
                "role_id": role_id,
                "path": projection.path,
                "sha256": projection.sha256,
                "fields": projection.fields,
                "projection_attestation": projection.projection_attestation,
                "scope_sha256": projection.scope_sha256,
            }
            for role_id, projection in sorted(self._projections.items())
        ]
        self.registry_sha256 = hashlib.sha256(
            json.dumps(
                {
                    "role_graph_sha256": self.role_graph_sha256,
                    "projections": registry_payload,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @property
    def identity_loader(self) -> LazyRoleLoader:
        return self._identity_loader

    def require_pinned_registration(self) -> None:
        frozen = require_frozen_admission()
        self.path_map.require_registered(
            frozen.reference_registry_path,
            frozen.reference_registry_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        )
        self._identity_loader.require_pinned_registration()
        registry_digest = hashlib.sha256()
        registry_digest = hashlib.sha256()
        with self.path_map.open_verified(
            frozen.reference_registry_path,
            frozen.reference_registry_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        ) as stream:
            while block := stream.read(1024 * 1024):
                registry_digest.update(block)
        if (
            self.role_graph_sha256.lower() != frozen.role_graph_sha256.lower()
            or self.registry_sha256 != frozen.reference_registry_sha256.lower()
            or registry_digest.hexdigest() != self.registry_sha256
        ):
            raise PermissionError("reference store differs from the approved physical-view registry")

    def open_role(
        self,
        role: RoleSpec,
        *,
        phase: str = "stage_a_reference",
    ) -> Iterator[ReferenceInterval]:
        self.require_pinned_registration()
        if phase not in {"stage_a_reference", OUTER_CONTROL_CANDIDATES_PHASE}:
            raise PermissionError("reference view phase is not an approved role-view purpose")
        registered_role = self._roles.get(role.role_id)
        if registered_role != role:
            raise PermissionError("requested role differs from the frozen reference role graph")
        def rows() -> Iterator[ReferenceInterval]:
            with self._identity_loader.open_identity_index(role.role_id) as identity_index:
                yield from iter_reference_rows(
                    self._projections[role.role_id],
                    path_map=self.path_map,
                    role_id=role.role_id,
                    allowed_participants=role.scored_participants,
                    identity_index=identity_index,
                    phase=phase,
                )

        return rows()
