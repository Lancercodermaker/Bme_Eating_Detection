"""Exact-path, one-role-at-a-time input loading.

This module accepts only an externally reviewed registration object. It never
discovers files or loads a role-wide/global feature matrix.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from dataclasses import asdict
import gc
import hashlib
import json
from math import isfinite
import sys
import threading
from typing import Any, BinaryIO, Iterator, Mapping

from . import path_map as path_mappings
from .contracts import (
    CACHE_MEMBERS,
    CACHE_MANIFEST_FIELDS,
    IDENTITY_FIELDS,
    SCORE_PROVENANCE_FIELDS,
    SCORE_MEMBERS,
    RegisteredFile,
    RoleInputRegistration,
    require_frozen_admission,
)
from .candidates import SupportWindow, WindowGeometry, build_support_component_ids
from .path_map import ExactPathMap


def _load_npz_members(stream: BinaryIO, members: tuple[str, ...]) -> dict[str, Any]:
    import numpy as np

    loaded: dict[str, Any] = {}
    with np.load(stream, allow_pickle=False) as archive:
        for member in members:
            try:
                loaded[member] = archive[member]
            except KeyError as exc:
                raise ValueError(f"approved member is missing from exact artifact: {member}") from exc
    return loaded


def _read_projection(
    stream: BinaryIO,
    registered: Any,
    expected_fields: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    if not registered.projection_attestation:
        raise PermissionError("projection lacks independent field-isolation review")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(stream, 1):
        if not line.strip():
            raise ValueError(f"blank identity row at {line_number}")
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != set(expected_fields):
            raise ValueError("projection contains fields outside its approved allowlist")
        rows.append(row)
    return tuple(rows)


def _validate_role_identity_rows(
    rows: tuple[dict[str, Any], ...], registration: RoleInputRegistration
) -> None:
    """The physical identity view must contain only this role's scored windows."""

    if not rows:
        raise ValueError("role identity projection is empty")
    allowed = set(registration.role.scored_participants)
    previous_global = -1
    seen_local: set[tuple[str, str, str, int]] = set()
    for row in rows:
        global_index = row["global_index"]
        row_index = row["row_index"]
        if (
            isinstance(global_index, bool)
            or not isinstance(global_index, int)
            or global_index <= previous_global
            or isinstance(row_index, bool)
            or not isinstance(row_index, int)
            or row_index < 0
            or not all(
                isinstance(row[field], str) and row[field]
                for field in ("participant_id", "record_id", "session_id")
            )
            or row["participant_id"] not in allowed
        ):
            raise ValueError("identity projection escapes the scored role or global order")
        key = (row["participant_id"], row["record_id"], row["session_id"], row_index)
        if key in seen_local:
            raise ValueError("duplicate local window identity in the role projection")
        seen_local.add(key)
        previous_global = global_index


@dataclass(slots=True)
class LoadedRole:
    role_id: str
    identities: tuple[dict[str, Any], ...]
    scores: Mapping[str, Any]
    geometry: Mapping[str, Any]
    threshold_reference: float

    def validate(self, registration: RoleInputRegistration) -> None:
        import numpy as np

        ids = np.asarray(self.scores["ids"])
        raw_original = np.asarray(self.scores["raw"])
        relative_original = np.asarray(self.scores["relative"])
        raw = np.asarray(self.scores["raw"], dtype=np.float64)
        relative = np.asarray(self.scores["relative"], dtype=np.float64)
        starts = np.asarray(self.geometry["starts"])
        ends = np.asarray(self.geometry["ends"])
        coverage = np.asarray(self.geometry["coverage"], dtype=np.float64)
        crosses_gap = np.asarray(self.geometry["crosses_gap"], dtype=np.bool_)
        count = len(self.identities)
        if ids.ndim != 1 or raw.shape != ids.shape or relative.shape != ids.shape:
            raise ValueError("score members must have aligned one-dimensional rows")
        if raw_original.shape != ids.shape or relative_original.shape != ids.shape:
            raise ValueError("raw and relative score arrays must align with ids")
        if any(array.shape != (count,) for array in (starts, ends, coverage, crosses_gap)):
            raise ValueError("geometry and role-scoped identity view are misaligned")
        if not np.issubdtype(ids.dtype, np.integer):
            raise ValueError("score ids must be integer global window indices")
        if np.any(ids < 0) or np.any(ids > np.iinfo(np.int64).max):
            raise ValueError("score global ids are outside the supported index range")
        if len(set(map(int, ids.tolist()))) != len(ids):
            raise ValueError("duplicate global score id within role")
        if not np.isfinite(raw).all() or not np.isfinite(relative).all():
            raise ValueError("score members contain non-finite values")
        if not isfinite(registration.threshold_reference):
            raise ValueError("frozen threshold reference must be finite")
        expected_relative = raw_original - float(registration.threshold_reference)
        if not np.array_equal(expected_relative, relative_original):
            raise ValueError("relative score member differs from raw minus frozen threshold")
        if not np.isfinite(coverage).all():
            raise ValueError("coverage contains non-finite values")
        if (
            not np.issubdtype(starts.dtype, np.integer)
            or not np.issubdtype(ends.dtype, np.integer)
            or np.any(ends <= starts)
        ):
            raise ValueError("window bounds must be valid integer intervals")
        if np.any(coverage < 0.8) or np.any(coverage > 1.0) or np.any(crosses_gap):
            raise ValueError("window fails the frozen A1 validity conditions")
        identity_by_global = {int(row["global_index"]): row for row in self.identities}
        if len(identity_by_global) != count:
            raise ValueError("duplicate global identity")
        if not set(map(int, ids.tolist())) <= set(identity_by_global):
            raise ValueError("score id is not bound to a role window identity")
        _validate_role_identity_rows(self.identities, registration)
        expected_ids = [int(row["global_index"]) for row in self.identities]
        if ids.astype(np.int64, copy=False).tolist() != expected_ids:
            raise ValueError("score ids do not match the frozen scored-participant global order")
        previous_by_session: dict[tuple[str, str, str], int] = {}
        for index, identity in enumerate(self.identities):
            key = (
                str(identity["participant_id"]),
                str(identity["record_id"]),
                str(identity["session_id"]),
            )
            start = int(starts[index])
            if key in previous_by_session and start < previous_by_session[key]:
                raise ValueError("window starts are out of order within a session")
            previous_by_session[key] = start
        if self.role_id != registration.role.role_id:
            raise ValueError("loaded role differs from registration")
        if self.threshold_reference != registration.threshold_reference:
            raise ValueError("threshold differs from frozen score provenance")
        if registration.quality_attestation.role_id != self.role_id:
            raise ValueError("quality attestation role mismatch")

    def support_windows(self, registration: RoleInputRegistration) -> tuple[SupportWindow, ...]:
        """Join only the authorized role geometry and score members."""

        import numpy as np

        self.validate(registration)
        starts = np.asarray(self.geometry["starts"], dtype=np.int64)
        ends = np.asarray(self.geometry["ends"], dtype=np.int64)
        coverage = np.asarray(self.geometry["coverage"], dtype=np.float64)
        crosses_gap = np.asarray(self.geometry["crosses_gap"], dtype=np.bool_)
        geometry = tuple(
            WindowGeometry(
                role_id=self.role_id,
                participant_id=str(identity["participant_id"]),
                record_id=str(identity["record_id"]),
                session_id=str(identity["session_id"]),
                global_index=int(identity["global_index"]),
                row_index=int(identity["row_index"]),
                start_ms=int(starts[index]),
                end_ms=int(ends[index]),
                coverage=float(coverage[index]),
                crosses_gap=bool(crosses_gap[index]),
            )
            for index, identity in enumerate(self.identities)
        )
        components = build_support_component_ids(self.role_id, geometry)
        by_global = {item.global_index: item for item in geometry}
        score_ids = np.asarray(self.scores["ids"], dtype=np.int64)
        relative = np.asarray(self.scores["relative"], dtype=np.float64)
        result: list[SupportWindow] = []
        for global_index, relative_score in zip(score_ids.tolist(), relative.tolist(), strict=True):
            item = by_global[global_index]
            result.append(
                SupportWindow(
                    role_id=self.role_id,
                    participant_id=item.participant_id,
                    record_id=item.record_id,
                    session_id=item.session_id,
                    component_id=components[global_index],
                    global_index=global_index,
                    row_index=item.row_index,
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    relative=float(relative_score),
                    coverage=item.coverage,
                )
            )
        return tuple(result)


class _RoleLease(AbstractContextManager[LoadedRole]):
    def __init__(self, owner: "LazyRoleLoader", registration: RoleInputRegistration):
        self.owner = owner
        self.registration = registration
        self.value: LoadedRole | None = None
        self._mount_lease: Any = None
        self._mount_lease_entered = False

    def __enter__(self) -> LoadedRole:
        self.owner.require_pinned_registration()
        self.owner._enter_lease()
        reg = self.registration
        try:
            self._mount_lease = self.owner.path_map.lease_role_view(reg.role.role_id)
            self._mount_lease.__enter__()
            self._mount_lease_entered = True
            identities = self.owner._projection(reg.identity_view, IDENTITY_FIELDS)
            provenance = self.owner._projection(reg.score_provenance, SCORE_PROVENANCE_FIELDS)
            if len(provenance) != 1:
                raise ValueError("score provenance projection must contain one role record")
            score_entry = provenance[0]
            threshold = score_entry["threshold_reference"]
            if (
                score_entry["role_id"] != reg.role.role_id
                or score_entry["score_path"] != reg.manifest_score_path
                or score_entry["score_sha256"] != reg.score_npz.sha256
                or isinstance(threshold, bool)
                or not isinstance(threshold, (int, float))
                or not isfinite(threshold)
                or float(threshold) != reg.threshold_reference
                or score_entry["ids_member"] != "ids"
                or score_entry["raw_member"] != "raw"
                or score_entry["relative_member"] != "relative"
            ):
                raise ValueError("score file, threshold, members and role are not provenance-bound")
            _validate_role_identity_rows(identities, reg)

            identity_groups: dict[tuple[str, str, str], list[tuple[int, dict[str, Any]]]] = {}
            for position, identity in enumerate(identities):
                key = (
                    str(identity["participant_id"]),
                    str(identity["record_id"]),
                    str(identity["session_id"]),
                )
                identity_groups.setdefault(key, []).append((position, identity))
            cache_keys = {
                (item.participant_id, item.record_id, item.session_id)
                for item in reg.cache_files
            }
            if cache_keys != set(identity_groups):
                raise ValueError("cache registry and role identity view do not cover the same records")
            manifest_rows = self.owner._projection(reg.cache_manifest_view, CACHE_MANIFEST_FIELDS)
            if len(manifest_rows) != len(reg.cache_files):
                raise ValueError("role cache manifest view has the wrong number of records")
            registered_caches = {
                (item.participant_id, item.record_id, item.session_id): item
                for item in reg.cache_files
            }
            seen_manifest_keys: set[tuple[str, str, str]] = set()
            for manifest_row in manifest_rows:
                key = (
                    manifest_row["participant_id"],
                    manifest_row["record_id"],
                    manifest_row["session_id"],
                )
                if (
                    not all(isinstance(value, str) and value for value in key)
                    or key in seen_manifest_keys
                    or key not in registered_caches
                ):
                    raise ValueError("cache manifest view contains an extra or duplicate record")
                cache_file = registered_caches[key]
                if (
                    manifest_row["cache_path"] != cache_file.manifest_cache_path
                    or manifest_row["cache_sha256"] != cache_file.cache_npz.sha256
                ):
                    raise ValueError("cache path/hash differs from its exact role registration")
                seen_manifest_keys.add(key)
            if seen_manifest_keys != cache_keys:
                raise ValueError("role cache manifest view is incomplete")

            import numpy as np

            geometry: dict[str, Any] = {
                "starts": np.empty(len(identities), dtype=np.int64),
                "ends": np.empty(len(identities), dtype=np.int64),
                "coverage": np.empty(len(identities), dtype=np.float64),
                "crosses_gap": np.empty(len(identities), dtype=np.bool_),
            }
            for cache_file in reg.cache_files:
                cache = self.owner._npz(cache_file.cache_npz, CACHE_MEMBERS)
                rows = sorted(
                    identity_groups[(cache_file.participant_id, cache_file.record_id, cache_file.session_id)],
                    key=lambda pair: int(pair[1]["row_index"]),
                )
                row_indices = [int(identity["row_index"]) for _, identity in rows]
                if row_indices != list(range(len(rows))):
                    raise ValueError("cache rows do not match the frozen row-index order")
                arrays = {name: np.asarray(cache[name]) for name in CACHE_MEMBERS}
                if any(array.ndim != 1 or array.size != len(rows) for array in arrays.values()):
                    raise ValueError("cache geometry arrays do not align with role identities")
                if (
                    not np.issubdtype(arrays["starts"].dtype, np.integer)
                    or not np.issubdtype(arrays["ends"].dtype, np.integer)
                    or not np.issubdtype(arrays["crosses_gap"].dtype, np.bool_)
                    or np.any(arrays["starts"] > np.iinfo(np.int64).max)
                    or np.any(arrays["ends"] > np.iinfo(np.int64).max)
                ):
                    raise ValueError("cache geometry has an unexpected member dtype")
                for local_index, (role_position, _) in enumerate(rows):
                    for name in CACHE_MEMBERS:
                        geometry[name][role_position] = arrays[name][local_index]

            score = self.owner._npz(reg.score_npz, SCORE_MEMBERS)
            attestation = self.owner._projection(
                reg.quality_attestation, reg.quality_attestation.fields
            )
            if len(attestation) != 1:
                raise ValueError("quality attestation view must contain exactly one role record")
            quality = attestation[0]
            if (
                quality["role_id"] != reg.role.role_id
                or quality["source_a1_input_audit_sha256"] != reg.a1_input_audit_sha256
                or isinstance(quality["invalid_runs_upper_bound"], bool)
                or not isinstance(quality["invalid_runs_upper_bound"], int)
                or quality["invalid_runs_upper_bound"] != 20
                or isinstance(quality["window_feature_dim"], bool)
                or not isinstance(quality["window_feature_dim"], int)
                or quality["window_feature_dim"] != 111
                or quality["window_features_finite"] is not True
                or quality["a1_run_sha256"] != reg.a1_run_sha256
                or quality["role_identity_view_sha256"] != reg.identity_view.sha256
                or quality["role_source_registry_sha256"] != reg.quality_source_sha256()
            ):
                raise ValueError("role lacks the frozen A1 accepted-window quality proof")
            self.value = LoadedRole(
                role_id=reg.role.role_id,
                identities=identities,
                scores=score,
                geometry=geometry,
                threshold_reference=reg.threshold_reference,
            )
            self.value.validate(reg)
            return self.value
        except BaseException:
            try:
                if self._mount_lease_entered:
                    self._mount_lease_entered = False
                    self._mount_lease.__exit__(*sys.exc_info())
            finally:
                self.owner._leave_lease()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.value is not None:
            self.value.scores = {}
            self.value.geometry = {}
            self.value.identities = ()
            self.value = None
        try:
            gc.collect()
        finally:
            try:
                if self._mount_lease_entered:
                    self._mount_lease_entered = False
                    self._mount_lease.__exit__(exc_type, exc, traceback)
            finally:
                self.owner._leave_lease()


class LazyRoleLoader:
    """Stores metadata registrations only; role payloads live inside a lease."""

    def __init__(
        self,
        registrations: tuple[RoleInputRegistration, ...],
        *,
        role_graph_sha256: str,
        path_map: ExactPathMap,
    ):
        if type(path_map) is not ExactPathMap:
            raise PermissionError("role loader requires the reviewed exact Linux path map")
        ids = [item.role.role_id for item in registrations]
        if len(registrations) != 105 or len(ids) != len(set(ids)):
            raise ValueError("the frozen input registry must bind exactly 105 unique roles")
        if len(role_graph_sha256) != 64:
            raise ValueError("loader requires the exact frozen role-graph hash")
        self._registrations = {item.role.role_id: item for item in registrations}
        self.role_specs = tuple(item.role for item in registrations)
        self.role_graph_sha256 = role_graph_sha256.lower()
        if any(item.role_graph_sha256.lower() != self.role_graph_sha256 for item in registrations):
            raise ValueError("role input registrations do not share the frozen role graph")
        registration_bytes = json.dumps(
            [asdict(item) for item in sorted(registrations, key=lambda item: item.role.role_id)],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        self.registry_sha256 = hashlib.sha256(registration_bytes).hexdigest()
        self.path_map = path_map
        if self.path_map is path_mappings._NATIVE_CONTEXT:
            self.path_map.require_registered_batch(tuple(
                (item.path, item.sha256, registration.role.role_id, "stage_a_input")
                for registration in registrations
                for item in (
                    registration.score_npz,
                    registration.score_provenance,
                    registration.cache_manifest_view,
                    registration.identity_view,
                    registration.quality_attestation,
                    *(cache.cache_npz for cache in registration.cache_files),
                )
            ))
        else:
            for registration in registrations:
                for item in (
                    registration.score_npz,
                    registration.score_provenance,
                    registration.cache_manifest_view,
                    registration.identity_view,
                    registration.quality_attestation,
                    *(cache.cache_npz for cache in registration.cache_files),
                ):
                    self.path_map.require_registered(
                        item.path, item.sha256,
                        role_id=registration.role.role_id,
                        phase="stage_a_input",
                    )
        self._active = False
        self._lease_lock = threading.Lock()

    def require_pinned_registration(self) -> None:
        frozen = require_frozen_admission()
        self.path_map.require_registered(
            frozen.role_input_registry_path,
            self.registry_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        )
        if (
            self.role_graph_sha256 != frozen.role_graph_sha256.lower()
            or self.registry_sha256 != frozen.role_input_registry_sha256.lower()
            or self.path_map.manifest_sha256 != frozen.path_map_sha256.lower()
        ):
            raise PermissionError("role loader differs from the independently reviewed source pins")
        with self.path_map.open_verified(
            frozen.role_input_registry_path,
            self.registry_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        ):
            pass

    def _projection(
        self, registered: RegisteredFile, fields: tuple[str, ...]
    ) -> tuple[dict[str, Any], ...]:
        with self.path_map.open_verified(
            registered.path, registered.sha256,
            role_id=registered.role_id, phase="stage_a_input",
        ) as stream:
            return _read_projection(stream, registered, fields)

    def _npz(self, registered: RegisteredFile, members: tuple[str, ...]) -> dict[str, Any]:
        with self.path_map.open_verified(
            registered.path, registered.sha256,
            role_id=registered.role_id, phase="stage_a_input",
        ) as stream:
            return _load_npz_members(stream, members)

    def _enter_lease(self) -> None:
        with self._lease_lock:
            if self._active:
                raise RuntimeError("only one role-scoped input lease may be active")
            self._active = True

    def _leave_lease(self) -> None:
        with self._lease_lock:
            if not self._active:
                raise RuntimeError("role-scoped lease was not active")
            self._active = False

    def open_role(self, role_id: str) -> AbstractContextManager[LoadedRole]:
        self.require_pinned_registration()
        try:
            registration = self._registrations[role_id]
        except KeyError as exc:
            raise KeyError(f"unregistered role: {role_id}") from exc
        return _RoleLease(self, registration)

    @contextmanager
    def open_identity_index(self, role_id: str) -> Iterator[dict[tuple[str, str, str, int], int]]:
        """Open one role's reviewed identity projection without loading arrays."""

        self.require_pinned_registration()
        try:
            registration = self._registrations[role_id]
        except KeyError as exc:
            raise KeyError(f"unregistered role: {role_id}") from exc
        self._enter_lease()
        identity_index: dict[tuple[str, str, str, int], int] = {}
        try:
            with self.path_map.lease_role_view(role_id):
                try:
                    rows = self._projection(registration.identity_view, IDENTITY_FIELDS)
                    _validate_role_identity_rows(rows, registration)
                    for row in rows:
                        key = (
                            str(row["participant_id"]),
                            str(row["record_id"]),
                            str(row["session_id"]),
                            int(row["row_index"]),
                        )
                        identity_index[key] = int(row["global_index"])
                    yield identity_index
                finally:
                    identity_index.clear()
                    gc.collect()
        finally:
            self._leave_lease()
