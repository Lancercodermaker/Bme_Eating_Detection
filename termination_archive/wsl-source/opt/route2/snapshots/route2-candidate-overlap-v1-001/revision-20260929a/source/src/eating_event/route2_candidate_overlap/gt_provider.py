"""Role- and phase-scoped provider over separately approved six-field views."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Any, Literal

from .budget import AppendOnlyLedger, PredictionFreezeReceipt
from .contracts import (
    GT_FIELDS,
    STUDY_ID,
    RegisteredFile,
    StudyStage,
    projection_scope_sha256,
    require_frozen_admission,
)
from .path_map import ExactPathMap

GT_COMMON_FIELDS = GT_FIELDS[:5]


def stage_gt_fields(stage: StudyStage) -> tuple[str, ...]:
    if stage == StudyStage.TRAIN_LABELS:
        return GT_COMMON_FIELDS + ("training_eligibility",)
    if stage in (StudyStage.INNER_EVALUATION, StudyStage.OUTER_EVALUATION):
        return GT_COMMON_FIELDS + ("evaluation_eligibility",)
    raise PermissionError("Stage A has no GT fields")


@dataclass(frozen=True, slots=True)
class FrozenPredictionReceipt:
    outer_id: str
    role_ids: tuple[str, ...]
    thresholds: tuple[float, ...]
    predictions: tuple[PredictionFreezeReceipt, ...]

    def __post_init__(self) -> None:
        if not self.outer_id or not self.role_ids:
            raise ValueError("prediction receipt is incomplete")
        if len(set(self.role_ids)) != len(self.role_ids):
            raise ValueError("prediction receipt repeats a role")
        if self.thresholds not in ((0.10, 0.25, 0.50), (0.10,), (0.25,), (0.50,)):
            raise ValueError("prediction receipt has an unknown threshold set")
        phase = "inner" if len(self.role_ids) == 4 else "outer" if len(self.role_ids) == 1 else ""
        if not phase or (phase == "inner" and self.thresholds != (0.10, 0.25, 0.50)):
            raise ValueError("prediction receipt has an invalid phase shape")
        expected = {
            (role_id, f"{threshold:.2f}")
            for role_id in self.role_ids for threshold in self.thresholds
        }
        actual = {(item.role_id, item.threshold) for item in self.predictions}
        if len(self.predictions) != len(expected) or actual != expected:
            raise ValueError("prediction receipt does not cover each role and threshold exactly once")
        if any(item.phase != phase or item.outer_id != self.outer_id for item in self.predictions):
            raise ValueError("prediction receipt phase or outer fold differs")


@dataclass(frozen=True, slots=True)
class TruthReadScope:
    stage: StudyStage
    outer_id: str
    role_ids: tuple[str, ...]
    participants: tuple[str, ...]
    eligibility_field: Literal["training_eligibility", "evaluation_eligibility"]
    consumer: Literal["candidate_labeler", "threshold_selector", "outer_evaluator"]
    prediction_receipt: FrozenPredictionReceipt | None = None
    role_graph_sha256: str = ""
    participant_scope_attestation: str = ""

    def __post_init__(self) -> None:
        if not self.role_ids or not self.participants:
            raise ValueError("truth scope must name exact roles and participants")
        if len(set(self.role_ids)) != len(self.role_ids):
            raise ValueError("truth scope repeats roles")
        if len(set(self.participants)) != len(self.participants):
            raise ValueError("truth scope repeats participants")
        if not self.role_graph_sha256 or not self.participant_scope_attestation:
            raise PermissionError("truth role/participant whitelist must be attested")
        if self.stage == StudyStage.TRAIN_LABELS:
            if self.eligibility_field != "training_eligibility" or self.consumer != "candidate_labeler":
                raise PermissionError("training labels require training eligibility and labeler")
            if self.prediction_receipt is not None:
                raise PermissionError("training label reads precede prediction receipts")
            if len(self.role_ids) != 1:
                raise PermissionError("training labels are loaded for one candidate role at a time")
        elif self.stage == StudyStage.INNER_EVALUATION:
            self._require_frozen_predictions("threshold_selector")
            if self.eligibility_field != "evaluation_eligibility":
                raise PermissionError("inner evaluation requires evaluation eligibility")
            if len(self.role_ids) != 4 or self.prediction_receipt is None:
                raise PermissionError("inner GT opens only after all four inner roles freeze")
            if len(self.prediction_receipt.thresholds) != 3:
                raise PermissionError("all three frozen thresholds must be represented")
        elif self.stage == StudyStage.OUTER_EVALUATION:
            self._require_frozen_predictions("outer_evaluator")
            if self.eligibility_field != "evaluation_eligibility" or len(self.role_ids) != 1:
                raise PermissionError("outer GT requires one frozen outer prediction role")
            if self.prediction_receipt is None or self.prediction_receipt.thresholds not in (
                (0.10,),
                (0.25,),
                (0.50,),
            ):
                raise PermissionError("outer GT requires a receipt for the selected frozen threshold")
        else:
            raise PermissionError("Stage A cannot construct a GT read scope")

    def _require_frozen_predictions(self, consumer: str) -> None:
        if (
            self.consumer != consumer
            or self.prediction_receipt is None
            or self.prediction_receipt.outer_id != self.outer_id
            or set(self.prediction_receipt.role_ids) != set(self.role_ids)
        ):
            raise PermissionError("GT access requires a matching frozen-prediction receipt")


@dataclass(frozen=True, slots=True)
class FrozenRoleGraph:
    """Minimal reviewed role/participant projection used before GT view access."""

    sha256: str
    projection_sha256: str
    training_label_participants: dict[str, tuple[str, ...]]
    training_outer_ids: dict[str, str]
    inner_evaluation_roles_by_outer: dict[str, tuple[str, ...]]
    outer_fit_participants: dict[str, tuple[str, ...]]
    outer_role_ids: dict[str, str]
    outer_evaluation_participants: dict[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        if any(
            len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower())
            for value in (self.sha256, self.projection_sha256)
        ):
            raise ValueError("frozen role graph requires its exact SHA-256")
        fields = (
            "training_label_participants",
            "training_outer_ids",
            "inner_evaluation_roles_by_outer",
            "outer_fit_participants",
            "outer_role_ids",
            "outer_evaluation_participants",
        )
        for field_name in fields:
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                MappingProxyType({key: tuple(items) if not isinstance(items, str) else items
                                  for key, items in value.items()}),
            )
        outer_ids = set(self.inner_evaluation_roles_by_outer)
        if (
            len(self.training_label_participants) != 100
            or len(self.training_outer_ids) != 100
            or set(self.training_outer_ids) != set(self.training_label_participants)
            or len(outer_ids) != 5
            or set(self.outer_fit_participants) != outer_ids
            or set(self.outer_role_ids) != outer_ids
            or set(self.outer_evaluation_participants) != outer_ids
            or any(len(roles) != 4 for roles in self.inner_evaluation_roles_by_outer.values())
        ):
            raise ValueError("role graph is not the frozen 100/20/5 nested shape")
        for role_id, outer_id in self.training_outer_ids.items():
            if outer_id not in outer_ids:
                raise ValueError("training role maps to an unknown outer fold")
            if not set(self.training_label_participants[role_id]) <= set(
                self.outer_fit_participants[outer_id]
            ):
                raise ValueError("training-label participants escape the outer training set")
        heldout_sets = [set(values) for values in self.outer_evaluation_participants.values()]
        for index, first in enumerate(heldout_sets):
            for second in heldout_sets[index + 1:]:
                if first & second:
                    raise ValueError("outer held-out participant sets overlap")
        for outer_id in outer_ids:
            if set(self.outer_fit_participants[outer_id]) & set(
                self.outer_evaluation_participants[outer_id]
            ):
                raise ValueError("outer training and held-out participant sets overlap")

    @staticmethod
    def _scope_attestation(
        stage: StudyStage,
        outer_id: str,
        role_ids: tuple[str, ...],
        participants: tuple[str, ...],
        eligibility_field: str,
        role_graph_sha256: str,
    ) -> str:
        return projection_scope_sha256(
            f"gt:{stage.value}:{outer_id}:{','.join(role_ids)}",
            outer_id,
            participants,
            GT_COMMON_FIELDS + (eligibility_field,),
            role_graph_sha256=role_graph_sha256,
        )

    def validate_scope(self, scope: TruthReadScope) -> None:
        if scope.role_graph_sha256 != self.sha256:
            raise PermissionError("truth scope uses a different frozen role graph")
        if scope.stage == StudyStage.TRAIN_LABELS:
            role_id = scope.role_ids[0]
            expected = self.training_label_participants.get(role_id)
            if (
                expected is None
                or self.training_outer_ids.get(role_id) != scope.outer_id
                or set(scope.participants) != set(expected)
            ):
                raise PermissionError("training GT participants differ from the role whitelist")
        elif scope.stage == StudyStage.INNER_EVALUATION:
            roles = self.inner_evaluation_roles_by_outer.get(scope.outer_id)
            expected = self.outer_fit_participants.get(scope.outer_id)
            if roles is None or expected is None:
                raise PermissionError("inner evaluation references an unknown outer fold")
            if scope.role_ids != roles or set(scope.participants) != set(expected):
                raise PermissionError("inner GT scope differs from the frozen outer-training whitelist")
        elif scope.stage == StudyStage.OUTER_EVALUATION:
            role = self.outer_role_ids.get(scope.outer_id)
            expected = self.outer_evaluation_participants.get(scope.outer_id)
            if role is None or expected is None:
                raise PermissionError("outer evaluation references an unknown outer fold")
            if scope.role_ids != (role,) or set(scope.participants) != set(expected):
                raise PermissionError("outer GT scope differs from the frozen held-out whitelist")
        attestation = self._scope_attestation(
            scope.stage,
            scope.outer_id,
            scope.role_ids,
            scope.participants,
            scope.eligibility_field,
            self.sha256,
        )
        if scope.participant_scope_attestation != attestation:
            raise PermissionError("participant scope was not derived from the frozen role graph")

    def training_scope(self, role_id: str) -> TruthReadScope:
        participants = self.training_label_participants[role_id]
        outer_id = self.training_outer_ids[role_id]
        fields = "training_eligibility"
        return TruthReadScope(
            stage=StudyStage.TRAIN_LABELS,
            outer_id=outer_id,
            role_ids=(role_id,),
            participants=participants,
            eligibility_field=fields,
            consumer="candidate_labeler",
            role_graph_sha256=self.sha256,
            participant_scope_attestation=self._scope_attestation(
                StudyStage.TRAIN_LABELS,
                outer_id,
                (role_id,),
                participants,
                fields,
                self.sha256,
            ),
        )

    def inner_evaluation_scope(
        self,
        outer_id: str,
        receipt: FrozenPredictionReceipt,
    ) -> TruthReadScope:
        roles = self.inner_evaluation_roles_by_outer[outer_id]
        participants = self.outer_fit_participants[outer_id]
        fields = "evaluation_eligibility"
        return TruthReadScope(
            stage=StudyStage.INNER_EVALUATION,
            outer_id=outer_id,
            role_ids=roles,
            participants=participants,
            eligibility_field=fields,
            consumer="threshold_selector",
            prediction_receipt=receipt,
            role_graph_sha256=self.sha256,
            participant_scope_attestation=self._scope_attestation(
                StudyStage.INNER_EVALUATION,
                outer_id,
                roles,
                participants,
                fields,
                self.sha256,
            ),
        )

    def outer_evaluation_scope(
        self,
        outer_id: str,
        receipt: FrozenPredictionReceipt,
    ) -> TruthReadScope:
        role = self.outer_role_ids[outer_id]
        participants = self.outer_evaluation_participants[outer_id]
        fields = "evaluation_eligibility"
        return TruthReadScope(
            stage=StudyStage.OUTER_EVALUATION,
            outer_id=outer_id,
            role_ids=(role,),
            participants=participants,
            eligibility_field=fields,
            consumer="outer_evaluator",
            prediction_receipt=receipt,
            role_graph_sha256=self.sha256,
            participant_scope_attestation=self._scope_attestation(
                StudyStage.OUTER_EVALUATION,
                outer_id,
                (role,),
                participants,
                fields,
                self.sha256,
            ),
        )


class ScopedTruthProvider:
    """Opens one physically scoped derivative; never accepts the source JSON."""

    def __init__(
        self,
        registry_path: str | Path,
        role_scopes_path: str | Path,
        ledger: AppendOnlyLedger,
        path_map: ExactPathMap,
    ):
        if type(ledger) is not AppendOnlyLedger:
            raise PermissionError("GT provider requires the exact durable study ledger reader")
        if type(path_map) is not ExactPathMap:
            raise PermissionError("GT provider requires the reviewed Linux path map")
        frozen = require_frozen_admission()
        if path_map.manifest_sha256 != frozen.path_map_sha256.lower():
            raise PermissionError("GT provider path map differs from frozen admission")
        inputs_root = PureWindowsPath(frozen.gt_input_root_path)
        expected_registry = inputs_root / "gt-view-registry.json"
        expected_scopes = inputs_root / "gt-role-scopes.json"
        if (
            str(registry_path) != str(expected_registry)
            or str(role_scopes_path) != str(expected_scopes)
        ):
            raise PermissionError("GT provider accepts only the frozen logical projection registries")
        self.path_map = path_map
        self._registry_logical_path = str(expected_registry)
        self._role_scopes_logical_path = str(expected_scopes)
        self._registry_path = path_map.require_file(
            self._registry_logical_path,
            frozen.gt_view_registry_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        )
        self._role_scopes_path = path_map.require_file(
            self._role_scopes_logical_path,
            frozen.gt_role_graph_projection_sha256,
            role_id="__study__",
            phase="preflight_metadata",
        )
        self.require_pinned_registration()
        registry = json.loads(self._metadata_bytes(
            self._registry_logical_path, frozen.gt_view_registry_sha256
        ))
        scopes = json.loads(self._metadata_bytes(
            self._role_scopes_logical_path, frozen.gt_role_graph_projection_sha256
        ))
        if not isinstance(scopes, dict) or set(scopes) != {
            "schema", "role_graph_sha256", "training_label_participants",
            "training_outer_ids", "inner_evaluation_roles_by_outer",
            "outer_fit_participants", "outer_role_ids", "outer_evaluation_participants",
        } or scopes["schema"] != "route2_gt_role_scopes_v1" or (
            scopes["role_graph_sha256"] != frozen.role_graph_sha256.lower()
        ):
            raise PermissionError("GT role/participant whitelist differs from its approved projection")
        scope_names = (
            "training_label_participants", "training_outer_ids",
            "inner_evaluation_roles_by_outer", "outer_fit_participants",
            "outer_role_ids", "outer_evaluation_participants",
        )
        if any(not isinstance(scopes[name], dict) for name in scope_names):
            raise ValueError("GT role scope projection has malformed maps")
        self._role_graph = FrozenRoleGraph(
            sha256=frozen.role_graph_sha256.lower(),
            projection_sha256=frozen.gt_role_graph_projection_sha256.lower(),
            training_label_participants={
                key: tuple(value) for key, value in scopes["training_label_participants"].items()
            },
            training_outer_ids=dict(scopes["training_outer_ids"]),
            inner_evaluation_roles_by_outer={
                key: tuple(value) for key, value in scopes["inner_evaluation_roles_by_outer"].items()
            },
            outer_fit_participants={
                key: tuple(value) for key, value in scopes["outer_fit_participants"].items()
            },
            outer_role_ids=dict(scopes["outer_role_ids"]),
            outer_evaluation_participants={
                key: tuple(value) for key, value in scopes["outer_evaluation_participants"].items()
            },
        )
        if not isinstance(registry, dict) or set(registry) != {
            "schema", "role_graph_sha256", "gt_role_scopes_path",
            "gt_role_scopes_sha256", "views", "status",
        } or registry["schema"] != "route2_gt_view_registry_v1" or (
            registry["status"] != "PREPARED_UNREVIEWED"
            or registry["role_graph_sha256"] != frozen.role_graph_sha256.lower()
            or registry["gt_role_scopes_path"] != self._role_scopes_logical_path
            or registry["gt_role_scopes_sha256"] != frozen.gt_role_graph_projection_sha256.lower()
            or not isinstance(registry["views"], list)
            or len(registry["views"]) != 110
        ):
            raise PermissionError("GT view registry differs from the frozen reviewed projection")
        self._views: dict[tuple[StudyStage, str], RegisteredFile] = {}
        view_keys = {
            "kind", "phase", "role_id", "outer_id", "role_ids", "participants",
            "fields", "scope_sha256", "path", "sha256", "release_rule",
        }
        phase_counts = dict.fromkeys(
            (StudyStage.TRAIN_LABELS, StudyStage.INNER_EVALUATION, StudyStage.OUTER_EVALUATION), 0
        )
        for record in registry["views"]:
            if not isinstance(record, dict) or set(record) != view_keys or record["kind"] != "gt":
                raise PermissionError("GT execution registry contains a source or unapproved field")
            stage = StudyStage(record["phase"])
            if stage not in phase_counts:
                raise PermissionError("GT registry includes a Stage A or unknown phase")
            role_scope = record["role_id"]
            outer_id = record["outer_id"]
            role_ids = tuple(record["role_ids"])
            participants = tuple(record["participants"])
            fields = tuple(record["fields"])
            if (
                type(role_scope) is not str or type(outer_id) is not str
                or not all(type(item) is str for item in role_ids + participants + fields)
                or fields != stage_gt_fields(stage)
                or role_scope != (role_ids[0] if stage == StudyStage.TRAIN_LABELS else outer_id)
            ):
                raise PermissionError("GT registry role, scope, or six-field schema differs")
            if stage == StudyStage.TRAIN_LABELS:
                expected_roles = (role_scope,)
                expected_participants = self._role_graph.training_label_participants.get(role_scope)
                expected_outer = self._role_graph.training_outer_ids.get(role_scope)
                directory = "gt-training"
                release = "training_role_only"
            elif stage == StudyStage.INNER_EVALUATION:
                expected_roles = self._role_graph.inner_evaluation_roles_by_outer.get(outer_id)
                expected_participants = self._role_graph.outer_fit_participants.get(outer_id)
                expected_outer = outer_id
                directory = "gt-inner"
                release = "after_matching_frozen_prediction_receipt"
            else:
                expected_role = self._role_graph.outer_role_ids.get(outer_id)
                expected_roles = (expected_role,) if expected_role else None
                expected_participants = self._role_graph.outer_evaluation_participants.get(outer_id)
                expected_outer = outer_id
                directory = "gt-outer"
                release = "after_matching_frozen_prediction_receipt"
            expected_path = inputs_root / directory / (
                hashlib.sha256(role_scope.encode("utf-8")).hexdigest()[:20] + ".jsonl"
            )
            scope_digest = projection_scope_sha256(
                f"gt:{stage.value}:{outer_id}:{','.join(role_ids)}",
                outer_id, participants, fields, role_graph_sha256=frozen.role_graph_sha256.lower(),
            )
            if (
                expected_roles is None or expected_participants is None
                or role_ids != expected_roles or participants != expected_participants
                or outer_id != expected_outer or record["release_rule"] != release
                or record["scope_sha256"] != scope_digest
                or record["path"] != str(expected_path)
            ):
                raise PermissionError("GT registry escapes the frozen role/participant whitelist")
            key = (stage, role_scope)
            if key in self._views:
                raise ValueError("GT registry repeats a stage/role scope")
            self._views[key] = RegisteredFile(
                path=record["path"], sha256=record["sha256"], fields=fields,
                role_id=role_scope, projection_attestation=frozen.approval_record,
                scope_sha256=scope_digest,
            )
            path_map.require_registered(
                record["path"], record["sha256"],
                role_id=role_scope,
                phase=stage.value,
            )
            phase_counts[stage] += 1
        if tuple(phase_counts.values()) != (100, 5, 5):
            raise ValueError("GT registry does not contain the exact 100/5/5 phase views")
        self._ledger = ledger

    def _metadata_bytes(self, logical_path: str, sha256: str) -> bytes:
        with self.path_map.open_verified(
            logical_path, sha256,
            role_id="__study__", phase="preflight_metadata",
        ) as stream:
            return stream.read()

    def require_pinned_registration(self) -> None:
        """Recheck metadata-only physical registries without opening any GT view."""

        frozen = require_frozen_admission()
        for logical, expected in (
            (self._registry_logical_path, frozen.gt_view_registry_sha256),
            (self._role_scopes_logical_path, frozen.gt_role_graph_projection_sha256),
        ):
            digest = hashlib.sha256(self._metadata_bytes(logical, expected)).hexdigest()
            if digest != expected.lower():
                raise PermissionError("GT physical registry changed after independent review")

    def iter_truth(
        self,
        scope: TruthReadScope,
    ) -> Iterator[dict[str, Any]]:
        if scope.stage == StudyStage.STAGE_A_REFERENCE or scope.stage == StudyStage.STAGE_A_TREATMENT:
            raise PermissionError("Stage A has no GT provider")
        self.require_pinned_registration()
        self._role_graph.validate_scope(scope)
        scope_id = scope.role_ids[0] if scope.stage == StudyStage.TRAIN_LABELS else scope.outer_id
        view_key = (scope.stage, scope_id)
        try:
            registered = self._views[view_key]
        except KeyError as exc:
            raise PermissionError("no registered GT projection for this phase/outer fold") from exc
        expected_fields = stage_gt_fields(scope.stage)
        if registered.fields != expected_fields:
            raise PermissionError("GT projection fields differ from the approved phase-six-field view")
        if registered.role_id != scope_id:
            raise PermissionError("GT projection does not bind to the requested role/scope")
        if registered.scope_sha256 != scope.participant_scope_attestation:
            raise PermissionError("GT projection was not registered for this exact role/participant scope")

        release = self.path_map.receipt_for(
            registered.path,
            registered.sha256,
            role_id=scope_id,
            phase=scope.stage.value,
        )
        self._ledger.require_gt_release(scope, release.release_ledger_event_sha256)
        with self.path_map.open_verified(
            registered.path,
            registered.sha256,
            role_id=scope_id,
            phase=scope.stage.value,
        ) as stream:
            allowed = set(scope.participants)
            seen: set[tuple[str, int]] = set()
            while raw := stream.readline(1024 * 1024 + 1):
                if len(raw) > 1024 * 1024:
                    raise ValueError("GT row exceeds the frozen row bound")
                row = json.loads(raw)
                if not isinstance(row, dict) or set(row) != set(expected_fields):
                    raise PermissionError("GT view contains fields outside the approved projection")
                participant = row["participant_id"]
                if type(participant) is not str or participant not in allowed:
                    raise PermissionError("scoped GT view contains an out-of-scope participant")
                eligible = row[scope.eligibility_field]
                if type(eligible) is not bool:
                    raise ValueError("eligibility field must be boolean")
                if any(type(row[field]) is not int for field in ("event_index", "start_ms", "end_ms", "duration_ms")):
                    raise ValueError("truth indices and times must be exact JSON integers")
                event_index = row["event_index"]
                if event_index < 0:
                    raise ValueError("truth event index must be nonnegative")
                identity = (participant, event_index)
                if identity in seen:
                    raise ValueError("duplicate participant/event truth identity")
                seen.add(identity)
                if row["end_ms"] <= row["start_ms"]:
                    raise ValueError("truth interval must be nonempty")
                if row["duration_ms"] != row["end_ms"] - row["start_ms"]:
                    raise ValueError("truth duration differs from its frozen interval")
                if not eligible:
                    continue
                yield row
