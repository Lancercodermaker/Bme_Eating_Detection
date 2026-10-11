"""Typed, fail-closed contracts for the isolated Route 2 study."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from math import isfinite
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

STUDY_ID = "route2-candidate-overlap-v1-001"
REFERENCE_GAP_MS = 300_000
GT_FIELDS = (
    "participant_id",
    "event_index",
    "start_ms",
    "end_ms",
    "duration_ms",
    "training_eligibility",
    "evaluation_eligibility",
)
REFERENCE_FIELDS = (
    "role_id",
    "participant_id",
    "record_id",
    "session_id",
    "component_id",
    "start_ms",
    "end_ms",
    "support_indices",
    "boundary_kind",
    "source_segment_id",
)
OUTER_CONTROL_CANDIDATES_PHASE = "outer_control_candidates"
OUTER_CONTROL_FINAL_MATCHES_PHASE = "outer_control_final_matches"
CONTROL_FINAL_MATCH_FIELDS = ("participant_id", "event_index")
REFERENCE_SUPPORT_FIELDS = (
    "participant_id",
    "record_id",
    "session_id",
    "row_index",
)
IDENTITY_FIELDS = (
    "global_index",
    "participant_id",
    "record_id",
    "session_id",
    "row_index",
)
SCORE_MEMBERS = ("ids", "raw", "relative")
CACHE_MEMBERS = ("starts", "ends", "coverage", "crosses_gap")
TREATMENT_CANDIDATE_FIELDS = (
    "role_id",
    "candidate_id",
    "participant_id",
    "record_id",
    "session_id",
    "component_id",
    "start_ms",
    "end_ms",
    "support_indices",
    "source_16d",
    "boundary_kind",
    "source_segment_id",
)
SCORE_PROVENANCE_FIELDS = (
    "role_id",
    "score_path",
    "score_sha256",
    "threshold_reference",
    "ids_member",
    "raw_member",
    "relative_member",
)
CACHE_MANIFEST_FIELDS = (
    "participant_id",
    "record_id",
    "session_id",
    "cache_path",
    "cache_sha256",
)


def projection_scope_sha256(
    scope_kind: str,
    role_id: str,
    participants: tuple[str, ...],
    fields: tuple[str, ...],
    *,
    role_graph_sha256: str = "",
) -> str:
    payload = json.dumps(
        {
            "scope_kind": scope_kind,
            "role_id": role_id,
            "participants": participants,
            "fields": fields,
            "role_graph_sha256": role_graph_sha256,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
QUALITY_ATTESTATION_FIELDS = (
    "role_id",
    "a1_run_sha256",
    "source_a1_input_audit_sha256",
    "invalid_runs_upper_bound",
    "window_feature_dim",
    "window_features_finite",
    "role_identity_view_sha256",
    "role_source_registry_sha256",
)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def stage_a_registry_sha256(
    role_graph_sha256: str,
    role_input_registry_sha256: str,
    reference_registry_sha256: str,
) -> str:
    """Bind the complete A1 and sanitized A2 registrations to one role graph."""

    values = (role_graph_sha256, role_input_registry_sha256, reference_registry_sha256)
    if any(not _is_sha256(value) for value in values):
        raise ValueError("Stage A registry contains a missing or malformed SHA-256")
    payload = json.dumps(
        {
            "study_id": STUDY_ID,
            "role_graph_sha256": role_graph_sha256.lower(),
            "role_input_registry_sha256": role_input_registry_sha256.lower(),
            "reference_registry_sha256": reference_registry_sha256.lower(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenAdmission:
    """Reviewed source pins transcribed only after the concrete A+B decision."""

    role_graph_sha256: str
    role_input_registry_sha256: str
    role_input_registry_path: str
    reference_registry_sha256: str
    reference_registry_path: str
    gt_view_registry_sha256: str
    gt_role_graph_projection_sha256: str
    path_map_sha256: str
    gt_input_root_path: str
    combined_input_registry_sha256: str
    budget_policy_sha256: str
    resource_controller_sha256: str
    phase_runner_sha256: str
    phase_worker_sha256: str
    stage_b_adapter_sha256: str
    approved_write_volumes: tuple[str, ...]
    study_root_path: str
    budget_ledger_path: str
    lock_path: str
    study_image_path: str
    source_registration_path: str
    source_registration_sha256: str
    projection_manifest_path: str
    projection_manifest_sha256: str
    admission_metadata_projection_path: str
    admission_metadata_projection_sha256: str
    a2_004_config_sha256: str
    a2_004_audit_ready_sha256: str
    a2_004_audit_ready_sidecar_sha256: str
    a2_004_role_digests_sha256: str
    a2_004_final_metrics_sha256: str
    control_final_match_registry_sha256: str
    g1_eligibility_sha256: str
    linux_lock_path: str
    linux_lock_sha256: str
    linux_identity_path: str
    linux_identity_sha256: str
    runtime_attestation_path: str
    runtime_attestation_sha256: str
    source_snapshot_root: str
    source_snapshot_manifest_path: str
    source_snapshot_sha256: str
    runtime_snapshot_root: str
    runtime_snapshot_manifest_path: str
    runtime_snapshot_sha256: str
    readiness_sha256: str
    approval_record: str

    def __post_init__(self) -> None:
        values = (
            self.role_graph_sha256,
            self.role_input_registry_sha256,
            self.reference_registry_sha256,
            self.gt_view_registry_sha256,
            self.gt_role_graph_projection_sha256,
            self.path_map_sha256,
            self.combined_input_registry_sha256,
            self.budget_policy_sha256,
            self.resource_controller_sha256,
            self.phase_runner_sha256,
            self.phase_worker_sha256,
            self.stage_b_adapter_sha256,
            self.source_registration_sha256,
            self.projection_manifest_sha256,
            self.admission_metadata_projection_sha256,
            self.a2_004_config_sha256,
            self.a2_004_audit_ready_sha256,
            self.a2_004_audit_ready_sidecar_sha256,
            self.a2_004_role_digests_sha256,
            self.a2_004_final_metrics_sha256,
            self.control_final_match_registry_sha256,
            self.g1_eligibility_sha256,
            self.linux_lock_sha256,
            self.linux_identity_sha256,
            self.runtime_attestation_sha256,
            self.source_snapshot_sha256,
            self.runtime_snapshot_sha256,
            self.readiness_sha256,
        )
        if (
            any(not _is_sha256(value) for value in values)
            or not self.approval_record
            or len(self.approved_write_volumes) != 1
            or any(
                not value or not PurePosixPath(value).is_absolute()
                or ".." in PurePosixPath(value).parts
                for value in self.approved_write_volumes
            )
            or len(set(self.approved_write_volumes)) != len(self.approved_write_volumes)
            or not PureWindowsPath(self.role_input_registry_path).is_absolute()
            or not PureWindowsPath(self.reference_registry_path).is_absolute()
            or not PureWindowsPath(self.gt_input_root_path).is_absolute()
            or any(
                not PureWindowsPath(path).is_absolute()
                or ".." in PureWindowsPath(path).parts
                for path in (
                    self.source_registration_path,
                    self.projection_manifest_path,
                    self.admission_metadata_projection_path,
                    self.linux_lock_path,
                    self.linux_identity_path,
                    self.runtime_attestation_path,
                )
            )
            or not all(PurePosixPath(path).is_absolute() for path in (
                self.study_root_path, self.budget_ledger_path, self.lock_path,
                self.study_image_path, self.source_snapshot_root,
                self.source_snapshot_manifest_path, self.runtime_snapshot_root,
                self.runtime_snapshot_manifest_path,
            ))
            or any(".." in PurePosixPath(path).parts for path in (
                self.source_snapshot_root, self.source_snapshot_manifest_path,
                self.runtime_snapshot_root, self.runtime_snapshot_manifest_path,
            ))
            or self.source_snapshot_root == self.runtime_snapshot_root
            or PurePosixPath(self.source_snapshot_manifest_path).is_relative_to(
                PurePosixPath(self.source_snapshot_root)
            )
            or PurePosixPath(self.runtime_snapshot_manifest_path).is_relative_to(
                PurePosixPath(self.runtime_snapshot_root)
            )
        ):
            raise ValueError("frozen admission needs every reviewed digest, snapshot and approval record")
        root = PurePosixPath(self.study_root_path)
        volume = PurePosixPath(self.approved_write_volumes[0])
        if (
            root.name != STUDY_ID
            or root.parent != volume
            or PurePosixPath(self.budget_ledger_path) != volume / f"{STUDY_ID}-budget.jsonl"
            or PurePosixPath(self.lock_path) != volume / f"{STUDY_ID}.lock"
            or PurePosixPath(self.study_image_path)
            != PurePosixPath("/var/lib/route2/images") / f"{STUDY_ID}.ext4"
            or any(".." in PurePosixPath(path).parts for path in (
                self.study_root_path, self.budget_ledger_path, self.lock_path,
                self.study_image_path,
            ))
        ):
            raise ValueError("frozen output or image paths differ from the single approved study namespace")
        if self.combined_input_registry_sha256.lower() != stage_a_registry_sha256(
            self.role_graph_sha256,
            self.role_input_registry_sha256,
            self.reference_registry_sha256,
        ):
            raise ValueError("combined Stage A input pin differs from its source registrations")


# Intentionally unset. A caller-supplied approval/readiness/registration cannot
# authorize data reads. ``external_admission`` can verify the canonical
# controller-sealed artifact format, but no trusted production supervisor
# bootstraps that verifier, measures the mounted source/runtime, validates the
# approval provenance, or installs its result here. Do not transcribe pins into
# this module: it is inside the hashed source tree, so embedding its own
# manifest digest would be self-referential and invalidate that digest.
FROZEN_ADMISSION: FrozenAdmission | None = None


def require_frozen_admission() -> FrozenAdmission:
    if FROZEN_ADMISSION is None:
        raise PermissionError("real A1/A2 registrations and A+B approval are not frozen")
    return FROZEN_ADMISSION


class StudyStage(str, Enum):
    STAGE_A_REFERENCE = "stage_a_reference"
    STAGE_A_TREATMENT = "stage_a_treatment"
    TRAIN_LABELS = "train_labels"
    INNER_EVALUATION = "inner_evaluation"
    OUTER_EVALUATION = "outer_evaluation"


class StudyStatus(str, Enum):
    REFERENCE_NOT_REPRODUCED = "REFERENCE_NOT_REPRODUCED"
    MECHANISM_NOT_SUPPORTED = "MECHANISM_NOT_SUPPORTED"
    INPUT_NOT_AUTHORIZED = "INPUT_NOT_AUTHORIZED"
    INVALID = "INVALID"
    VERIFIER_DATA_INSUFFICIENT = "VERIFIER_DATA_INSUFFICIENT"
    INCOMPLETE_RESOURCE = "INCOMPLETE_RESOURCE"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class WindowIdentity:
    global_index: int
    participant_id: str
    record_id: str
    session_id: str
    row_index: int

    def __post_init__(self) -> None:
        if self.global_index < 0 or self.row_index < 0:
            raise ValueError("window indices must be nonnegative")
        if not all((self.participant_id, self.record_id, self.session_id)):
            raise ValueError("window identity fields must be nonempty")


@dataclass(frozen=True, slots=True)
class RoleSpec:
    role_id: str
    outer_id: str
    kind: Literal["inner_train", "inner_heldout", "outer"]
    fit_participants: tuple[str, ...]
    scored_participants: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.role_id or not self.outer_id:
            raise ValueError("role and outer identifiers must be nonempty")
        if len(set(self.fit_participants)) != len(self.fit_participants):
            raise ValueError("duplicate fit participant")
        if len(set(self.scored_participants)) != len(self.scored_participants):
            raise ValueError("duplicate scored participant")
        if set(self.fit_participants) & set(self.scored_participants):
            raise ValueError("fit and scored participants must be disjoint")


@dataclass(frozen=True, slots=True)
class RegisteredFile:
    """An exact, separately approved file identity; never discovered by glob."""

    path: str
    sha256: str
    fields: tuple[str, ...]
    role_id: str
    projection_attestation: str = ""
    scope_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.path or not PureWindowsPath(self.path).is_absolute():
            raise ValueError("registered logical Windows input path must be absolute")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("registered input must have a SHA-256 digest")
        if not self.role_id:
            raise ValueError("registered input must bind to one role")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("registered field list contains duplicates")
        if self.scope_sha256 and (
            len(self.scope_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.scope_sha256.lower())
        ):
            raise ValueError("registered projection scope must use a SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CacheFileRegistration:
    participant_id: str
    record_id: str
    session_id: str
    manifest_cache_path: str
    cache_npz: RegisteredFile

    def __post_init__(self) -> None:
        if not all((self.participant_id, self.record_id, self.session_id, self.manifest_cache_path)):
            raise ValueError("cache identity and exact manifest path are required")
        if self.cache_npz.fields != CACHE_MEMBERS:
            raise ValueError("cache member allowlist must be exactly geometry members")
        if self.manifest_cache_path != self.cache_npz.path:
            raise ValueError("cache file path differs from its normalized manifest registration")


@dataclass(frozen=True, slots=True)
class RoleInputRegistration:
    role: RoleSpec
    role_graph_sha256: str
    score_npz: RegisteredFile
    score_provenance: RegisteredFile
    manifest_score_path: str
    cache_files: tuple[CacheFileRegistration, ...]
    cache_manifest_view: RegisteredFile
    identity_view: RegisteredFile
    quality_attestation: RegisteredFile
    a1_run_sha256: str
    a1_input_audit_sha256: str
    threshold_reference: float

    def quality_source_sha256(self) -> str:
        """Bind a quality claim to the exact accepted run, score, and caches."""

        payload = {
            "role_id": self.role.role_id,
            "role_graph_sha256": self.role_graph_sha256.lower(),
            "a1_run_sha256": self.a1_run_sha256.lower(),
            "a1_input_audit_sha256": self.a1_input_audit_sha256.lower(),
            "score_sha256": self.score_npz.sha256.lower(),
            "score_provenance_sha256": self.score_provenance.sha256.lower(),
            "cache_manifest_view_sha256": self.cache_manifest_view.sha256.lower(),
            "identity_view_sha256": self.identity_view.sha256.lower(),
            "threshold_reference": self.threshold_reference,
            "caches": [
                {
                    "participant_id": item.participant_id,
                    "record_id": item.record_id,
                    "session_id": item.session_id,
                    "cache_path": item.cache_npz.path,
                    "cache_sha256": item.cache_npz.sha256.lower(),
                }
                for item in sorted(
                    self.cache_files,
                    key=lambda item: (item.participant_id, item.record_id, item.session_id),
                )
            ],
        }
        return hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

    def __post_init__(self) -> None:
        role_id = self.role.role_id
        if not _is_sha256(self.role_graph_sha256):
            raise ValueError("role input registration requires frozen role-graph identity")
        if not _is_sha256(self.a1_run_sha256):
            raise ValueError("role input registration requires the exact accepted A1 run hash")
        if not _is_sha256(self.a1_input_audit_sha256):
            raise ValueError("role input registration requires the exact accepted A1 input audit hash")
        if any(item.role_id != role_id for item in (
            self.score_npz,
            self.score_provenance,
            self.cache_manifest_view,
            self.identity_view,
            self.quality_attestation,
        )):
            raise ValueError("all role inputs must bind to the same role")
        if self.score_npz.fields != SCORE_MEMBERS:
            raise ValueError("score member allowlist must be exactly ids/raw/relative")
        if self.score_provenance.fields != SCORE_PROVENANCE_FIELDS:
            raise ValueError("score provenance must be an exact role-scoped projection")
        if not self.manifest_score_path:
            raise ValueError("exact score-provenance path binding is required")
        if self.manifest_score_path != self.score_npz.path:
            raise ValueError("score file path differs from the exact provenance registration")
        if not self.score_provenance.projection_attestation:
            raise ValueError("score provenance projection requires independent review")
        role_scope_fields = self.role.scored_participants
        if self.score_provenance.scope_sha256 != projection_scope_sha256(
            "score_provenance",
            role_id,
            role_scope_fields,
            SCORE_PROVENANCE_FIELDS,
            role_graph_sha256=self.role_graph_sha256,
        ):
            raise ValueError("score provenance scope is not bound to this role graph")
        if not self.cache_files:
            raise ValueError("role input must explicitly register its cache files")
        cache_keys = [(item.participant_id, item.record_id, item.session_id) for item in self.cache_files]
        if len(cache_keys) != len(set(cache_keys)):
            raise ValueError("duplicate participant/record/session cache registration")
        if any(item.cache_npz.role_id != role_id for item in self.cache_files):
            raise ValueError("cache registrations must bind to the containing role")
        if any(item.participant_id not in self.role.scored_participants for item in self.cache_files):
            raise ValueError("cache registration contains a non-scored participant")
        if (
            self.cache_manifest_view.fields != CACHE_MANIFEST_FIELDS
            or not self.cache_manifest_view.projection_attestation
            or self.cache_manifest_view.scope_sha256 != projection_scope_sha256(
                "cache_manifest_role",
                role_id,
                self.role.scored_participants,
                CACHE_MANIFEST_FIELDS,
                role_graph_sha256=self.role_graph_sha256,
            )
        ):
            raise ValueError("cache manifest view must be one reviewed, role-scoped projection")
        if self.identity_view.fields != IDENTITY_FIELDS:
            raise ValueError("identity view must be an exact role-scoped projection")
        if not self.identity_view.projection_attestation:
            raise ValueError("identity view projection requires independent review")
        if self.identity_view.scope_sha256 != projection_scope_sha256(
            "role_identity",
            role_id,
            self.role.scored_participants,
            IDENTITY_FIELDS,
            role_graph_sha256=self.role_graph_sha256,
        ):
            raise ValueError("identity projection scope differs from the role participant whitelist")
        if self.quality_attestation.fields != QUALITY_ATTESTATION_FIELDS:
            raise ValueError("quality attestation fields must be exact and role-bound")
        if not self.quality_attestation.projection_attestation:
            raise ValueError("quality attestation projection requires independent review")
        if self.quality_attestation.scope_sha256 != projection_scope_sha256(
            "a1_quality_attestation",
            role_id,
            self.role.scored_participants,
            QUALITY_ATTESTATION_FIELDS,
            role_graph_sha256=self.role_graph_sha256,
        ):
            raise ValueError("quality attestation scope differs from its role registry")
        if not isfinite(self.threshold_reference):
            raise ValueError("frozen threshold reference must be finite")


@dataclass(frozen=True, slots=True)
class ExperimentApproval:
    """Runtime permit shape; a prompt or source edit is not an approval."""

    study_id: str
    scope: Literal["A+B"]
    approved: bool
    role_graph_sha256: str
    input_registry_sha256: str
    budget_policy_sha256: str
    resource_controller_sha256: str
    phase_runner_sha256: str
    phase_worker_sha256: str
    path_map_sha256: str
    approved_write_volumes: tuple[str, ...]
    study_root_path: str
    budget_ledger_path: str
    lock_path: str
    study_image_path: str
    source_registration_sha256: str
    projection_manifest_sha256: str
    admission_metadata_projection_path: str
    admission_metadata_projection_sha256: str
    linux_lock_sha256: str
    linux_identity_sha256: str
    runtime_attestation_sha256: str
    source_snapshot_root: str
    source_snapshot_manifest_path: str
    source_snapshot_sha256: str
    runtime_snapshot_root: str
    runtime_snapshot_manifest_path: str
    runtime_snapshot_sha256: str
    approval_record: str

    def require_full_ab(self) -> None:
        frozen = require_frozen_admission()
        hashes = (
            self.role_graph_sha256,
            self.input_registry_sha256,
            self.budget_policy_sha256,
            self.resource_controller_sha256,
            self.phase_runner_sha256,
            self.phase_worker_sha256,
            self.path_map_sha256,
            self.source_registration_sha256,
            self.projection_manifest_sha256,
            self.admission_metadata_projection_sha256,
            self.linux_lock_sha256,
            self.linux_identity_sha256,
            self.runtime_attestation_sha256,
            self.source_snapshot_sha256,
            self.runtime_snapshot_sha256,
        )
        if (
            self.study_id != STUDY_ID
            or self.scope != "A+B"
            or not self.approved
            or any(not _is_sha256(value) for value in hashes)
            or self.role_graph_sha256.lower() != frozen.role_graph_sha256.lower()
            or self.input_registry_sha256.lower() != frozen.combined_input_registry_sha256.lower()
            or self.budget_policy_sha256.lower() != frozen.budget_policy_sha256.lower()
            or self.resource_controller_sha256.lower() != frozen.resource_controller_sha256.lower()
            or self.phase_runner_sha256.lower() != frozen.phase_runner_sha256.lower()
            or self.phase_worker_sha256.lower() != frozen.phase_worker_sha256.lower()
            or self.path_map_sha256.lower() != frozen.path_map_sha256.lower()
            or self.approved_write_volumes != frozen.approved_write_volumes
            or self.study_root_path != frozen.study_root_path
            or self.budget_ledger_path != frozen.budget_ledger_path
            or self.lock_path != frozen.lock_path
            or self.study_image_path != frozen.study_image_path
            or self.source_registration_sha256.lower() != frozen.source_registration_sha256.lower()
            or self.projection_manifest_sha256.lower() != frozen.projection_manifest_sha256.lower()
            or self.admission_metadata_projection_path != frozen.admission_metadata_projection_path
            or self.admission_metadata_projection_sha256.lower()
            != frozen.admission_metadata_projection_sha256.lower()
            or self.linux_lock_sha256.lower() != frozen.linux_lock_sha256.lower()
            or self.linux_identity_sha256.lower() != frozen.linux_identity_sha256.lower()
            or self.runtime_attestation_sha256.lower() != frozen.runtime_attestation_sha256.lower()
            or self.source_snapshot_root != frozen.source_snapshot_root
            or self.source_snapshot_manifest_path != frozen.source_snapshot_manifest_path
            or self.source_snapshot_sha256.lower() != frozen.source_snapshot_sha256.lower()
            or self.runtime_snapshot_root != frozen.runtime_snapshot_root
            or self.runtime_snapshot_manifest_path != frozen.runtime_snapshot_manifest_path
            or self.runtime_snapshot_sha256.lower() != frozen.runtime_snapshot_sha256.lower()
            or self.approval_record != frozen.approval_record
        ):
            raise PermissionError("a specific, complete A+B authorization is required")
