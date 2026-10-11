"""Append-only budget accounting; execution requires a reviewed Linux enforcer.

Snapshots are observations, never a substitute for the independently reviewed
OS limits and the post-terminal wall receipt.  Without that controller the study
fails before output creation.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import threading
import time
from typing import TYPE_CHECKING, Callable, Iterable, Iterator, Literal, Mapping, Protocol, TypeVar
import uuid
import weakref

from .contracts import ExperimentApproval, STUDY_ID, StudyStatus
from .candidates import CandidateFileReceipt

if TYPE_CHECKING:
    from .gt_provider import TruthReadScope

ZERO_HASH = "0" * 64
_BINARY = getattr(os, "O_BINARY", 0)
T = TypeVar("T")


@dataclass(slots=True)
class _LedgerCloseState:
    descriptor: int
    identity: tuple[int, int]
    pid: int
    thread_id: int
    attempted: bool = False
    succeeded: bool = False
    closed_ns: int | None = None


_LEDGER_CLOSE_STATES = weakref.WeakKeyDictionary()


def _discard_owned_ledger_writer(ledger) -> None:
    """Failure cleanup consumes the original writer once, without a success fact."""
    state = _LEDGER_CLOSE_STATES.get(ledger)
    if state is not None and state.attempted:
        ledger._fd = None
        return
    descriptor = state.descriptor if state is not None else ledger._fd
    ledger._fd = None
    if state is not None:
        state.attempted = True
    if descriptor is not None:
        if state is not None:
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != state.identity:
                raise PermissionError("original writer descriptor changed before failure cleanup")
        os.close(descriptor)


def require_owned_ledger_close_success(ledger, expected_descriptor: int) -> int:
    """Query the native close success fact; public field resets cannot mint it."""
    state = _LEDGER_CLOSE_STATES.get(ledger)
    if (state is None or type(expected_descriptor) is not int or state.descriptor != expected_descriptor
            or state.pid != os.getpid() or state.thread_id != threading.get_ident()
            or state.attempted is not True or state.succeeded is not True
            or type(state.closed_ns) is not int or state.closed_ns <= 0
            or ledger._fd is not None or ledger._poisoned is not False
            or ledger._closed_at_monotonic_ns != state.closed_ns):
        raise PermissionError("original ledger close has no private native success fact")
    return state.closed_ns
# The fourth protocol dimension is 20 GT-backed evaluator calls plus one
# GT-free pooled reduction over the five disjoint outer-fold summaries.
CALL_CEILINGS = {
    "verifier_fit": 25,
    "verifier_predict": 25,
    "decoder": 65,
    "event_evaluator": 20,
    "pooled_reduction": 1,
}
CALL_THRESHOLDS = ("0.10", "0.25", "0.50")
_ROLE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_FIT_PROVENANCE_FIELDS = frozenset({
    "verifier_role_id", "training_candidate_roles", "fit_participants",
    "candidate_count", "positive_candidate_count", "positive_participant_count",
    "distinct_positive_canonical_gt_count", "ordered_candidate_keys_sha256",
    "feature_matrix_sha256", "training_label_join_sha256", "model_path",
    "model_sha256", "fit_attempt",
})


def _call_role_ids_from_graph(
    outer_role_ids: Iterable[str],
    inner_role_ids_by_outer: Iterable[tuple[str, Iterable[str]]],
    fit_training_roles_by_verifier: Iterable[tuple[str, Iterable[str]]],
) -> dict[str, tuple[str, ...]]:
    """Derive the only valid call labels from the frozen 5x4 role graph."""

    outer_roles = tuple(outer_role_ids)
    inner_graph = tuple((outer_id, tuple(role_ids)) for outer_id, role_ids in inner_role_ids_by_outer)
    outer_ids = tuple(sorted(role_id.split("/")[1] for role_id in outer_roles if type(role_id) is str and role_id.count("/") == 2))
    if (
        len(outer_roles) != 5
        or len(outer_ids) != 5
        or len(set(outer_ids)) != 5
        or len(inner_graph) != 5
        or len({outer_id for outer_id, _ in inner_graph}) != 5
        or {outer_id for outer_id, _ in inner_graph} != set(outer_ids)
        or any(not _ROLE_SEGMENT.fullmatch(outer_id) for outer_id in outer_ids)
    ):
        raise PermissionError("frozen role graph does not contain five unique outer roles")
    if any(role_id != f"candidate/{outer_id}/outer" for role_id in outer_roles for outer_id in outer_ids if role_id.split("/")[1] == outer_id):
        raise PermissionError("frozen role graph outer role IDs are inconsistent")

    ordered_inner: dict[str, tuple[str, ...]] = {}
    for outer_id, role_ids in inner_graph:
        if not _ROLE_SEGMENT.fullmatch(outer_id) or len(role_ids) != 4 or len(set(role_ids)) != 4:
            raise PermissionError("frozen role graph does not contain four unique inner roles per outer")
        for role_id in role_ids:
            parts = role_id.split("/") if type(role_id) is str else ()
            if (
                len(parts) != 4 or parts[0] != "candidate" or parts[1] != outer_id
                or parts[3] != "inner" or not _ROLE_SEGMENT.fullmatch(parts[2])
            ):
                raise PermissionError("frozen role graph contains an invalid inner role ID")
        ordered_inner[outer_id] = tuple(sorted(role_ids))

    actual_fit_training = tuple(
        (verifier_id, tuple(training_roles))
        for verifier_id, training_roles in fit_training_roles_by_verifier
    )
    expected_fit_training: list[tuple[str, tuple[str, ...]]] = []
    seen_training_roles: set[str] = set()
    for outer_id in outer_ids:
        for inner_role_id in ordered_inner[outer_id]:
            inner_name = inner_role_id.split("/")[2]
            verifier_id = f"verifier/{outer_id}/{inner_name}"
            matches = [
                roles for role, roles in actual_fit_training if role == verifier_id
            ]
            if len(matches) != 1 or len(matches[0]) != 4 or len(set(matches[0])) != 4:
                raise PermissionError("frozen role graph lacks four subinner fit roles per verifier")
            children = tuple(sorted(matches[0]))
            for child_id in children:
                parts = child_id.split("/") if type(child_id) is str else ()
                if (
                    len(parts) != 5 or parts[:3] != ["candidate", outer_id, inner_name]
                    or parts[4] != "subinner" or not _ROLE_SEGMENT.fullmatch(parts[3])
                    or child_id in seen_training_roles
                ):
                    raise PermissionError("frozen role graph contains an invalid subinner training role")
                seen_training_roles.add(child_id)
            expected_fit_training.append((verifier_id, children))
        outer_verifier_id = f"verifier/{outer_id}/outer"
        expected_fit_training.append((outer_verifier_id, ordered_inner[outer_id]))
    complete_role_ids = (
        set(outer_roles)
        | {role_id for roles in ordered_inner.values() for role_id in roles}
        | seen_training_roles
    )
    if (
        actual_fit_training != tuple(expected_fit_training)
        or len(seen_training_roles) != 80
        or seen_training_roles & {role for roles in ordered_inner.values() for role in roles}
        or len(complete_role_ids) != 105
    ):
        raise PermissionError("frozen fit roles do not bind the complete 105-role candidate graph")

    fits: list[str] = []
    predictions: list[str] = []
    decoders: list[str] = []
    evaluators: list[str] = []
    for outer_id in outer_ids:
        inner = ordered_inner[outer_id]
        fits.extend(f"verifier/{outer_id}/{role_id.split('/')[2]}" for role_id in inner)
        fits.append(f"verifier/{outer_id}/outer")
        predictions.extend(inner)
        predictions.append(f"candidate/{outer_id}/outer")
        for role_id in inner:
            decoders.extend((role_id,) * len(CALL_THRESHOLDS))
        decoders.append(f"candidate/{outer_id}/outer")
        evaluators.extend(f"threshold/{outer_id}/{threshold}" for threshold in CALL_THRESHOLDS)
        evaluators.append(f"outer/{outer_id}")
    return {
        "verifier_fit": tuple(fits),
        "verifier_predict": tuple(predictions),
        "decoder": tuple(decoders),
        "event_evaluator": tuple(evaluators),
        "pooled_reduction": ("pooled/outer",),
    }


def _projection_call_role_ids(
    projection_payload: Mapping[str, object],
) -> tuple[str, dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    expected_fields = {
        "candidate_rows_n", "maximum_fit_rows_m", "prediction_rows_s",
            "candidate_file_bytes_b", "stage_a_disk_bytes_d_a", "role_graph_sha256",
            "outer_role_ids", "inner_role_ids_by_outer", "fit_training_roles_by_verifier",
    }
    if set(projection_payload) != expected_fields:
        raise PermissionError("Stage B entry projection lacks the frozen role graph schedule")
    role_graph_sha256 = projection_payload["role_graph_sha256"]
    outer_role_ids = projection_payload["outer_role_ids"]
    inner_graph = projection_payload["inner_role_ids_by_outer"]
    fit_training_graph = projection_payload["fit_training_roles_by_verifier"]
    if (
        type(role_graph_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", role_graph_sha256)
        or not isinstance(outer_role_ids, (tuple, list))
        or not isinstance(inner_graph, (tuple, list))
        or any(not isinstance(item, (tuple, list)) or len(item) != 2 for item in inner_graph)
        or not isinstance(fit_training_graph, (tuple, list))
        or any(not isinstance(item, (tuple, list)) or len(item) != 2 for item in fit_training_graph)
    ):
        raise PermissionError("Stage B entry projection has an invalid frozen role graph identity")
    numeric_fields = (
        "candidate_rows_n", "maximum_fit_rows_m", "prediction_rows_s",
        "candidate_file_bytes_b", "stage_a_disk_bytes_d_a",
    )
    if any(
        type(projection_payload[name]) is not int or projection_payload[name] < 0
        for name in numeric_fields
    ):
        raise PermissionError("Stage B entry projection has invalid exact integer values")
    schedule = _call_role_ids_from_graph(
        outer_role_ids,
        ((item[0], item[1]) for item in inner_graph),
        ((item[0], item[1]) for item in fit_training_graph),
    )
    fit_training = {item[0]: tuple(item[1]) for item in fit_training_graph}
    return role_graph_sha256, schedule, fit_training


def _expected_global_call_order(role_ids_by_kind: Mapping[str, tuple[str, ...]]) -> tuple[tuple[str, str], ...]:
    predictions = role_ids_by_kind["verifier_predict"]
    outer_roles = {
        role_id.split("/")[1]: role_id
        for role_id in predictions
        if len(role_id.split("/")) == 3 and role_id.endswith("/outer")
    }
    inner_roles: dict[str, list[str]] = {}
    for role_id in predictions:
        parts = role_id.split("/")
        if len(parts) == 4 and parts[3] == "inner":
            inner_roles.setdefault(parts[1], []).append(role_id)
    calls: list[tuple[str, str]] = []
    for outer_id in sorted(outer_roles):
        inner = tuple(sorted(inner_roles[outer_id]))
        for role_id in inner:
            calls.extend((
                ("verifier_fit", f"verifier/{outer_id}/{role_id.split('/')[2]}"),
                ("verifier_predict", role_id),
                *(("decoder", role_id),) * len(CALL_THRESHOLDS),
            ))
        calls.extend(
            ("event_evaluator", f"threshold/{outer_id}/{threshold}")
            for threshold in CALL_THRESHOLDS
        )
        calls.extend((
            ("verifier_fit", f"verifier/{outer_id}/outer"),
            ("verifier_predict", outer_roles[outer_id]),
            ("decoder", outer_roles[outer_id]),
            ("event_evaluator", f"outer/{outer_id}"),
        ))
    calls.append(("pooled_reduction", "pooled/outer"))
    return tuple(calls)


def _validate_fit_provenance_payload(payload: Mapping[str, object], *, expected_role_id: str, expected_attempt: int) -> None:
    if set(payload) != _FIT_PROVENANCE_FIELDS:
        raise PermissionError("fit provenance event has an unknown or incomplete schema")
    string_fields = (
        "verifier_role_id", "ordered_candidate_keys_sha256", "feature_matrix_sha256",
        "training_label_join_sha256", "model_path", "model_sha256",
    )
    integer_fields = (
        "candidate_count", "positive_candidate_count", "positive_participant_count",
        "distinct_positive_canonical_gt_count", "fit_attempt",
    )
    if (
        any(type(payload[name]) is not str for name in string_fields)
        or payload["verifier_role_id"] != expected_role_id
        or any(type(payload[name]) is not int or payload[name] < 0 for name in integer_fields)
        or payload["fit_attempt"] != expected_attempt
        or payload["positive_candidate_count"] > payload["candidate_count"]
        or payload["distinct_positive_canonical_gt_count"] > payload["positive_candidate_count"]
        or any(not re.fullmatch(r"[0-9a-f]{64}", payload[name]) for name in (
            "ordered_candidate_keys_sha256", "feature_matrix_sha256",
            "training_label_join_sha256", "model_sha256",
        ))
    ):
        raise PermissionError("fit provenance event differs from the fixed fit identity or metrics")
    roles, participants = payload["training_candidate_roles"], payload["fit_participants"]
    if (
        not isinstance(roles, (tuple, list))
        or any(type(item) is not str or not item.startswith("candidate/") for item in roles)
        or len(set(roles)) != len(roles)
        or not isinstance(participants, (tuple, list))
        or any(type(item) is not str or not item for item in participants)
        or tuple(participants) != tuple(sorted(set(participants)))
        or payload["positive_participant_count"] > len(participants)
    ):
        raise PermissionError("fit provenance event has invalid training role or participant identities")
    model_path_text = payload["model_path"]
    expected_filename = hashlib.sha256(expected_role_id.encode("utf-8")).hexdigest() + ".pickle"
    if not any(
        candidate.is_absolute()
        and len(candidate.parts) >= 2
        and candidate.parts[-2] == "verifier-models"
        and candidate.name == expected_filename
        for candidate in (Path(model_path_text), PurePosixPath(model_path_text), PureWindowsPath(model_path_text))
    ):
        raise PermissionError("fit provenance event has a noncanonical model path")


def _fixed_call_role_schedule(
    states: Mapping[tuple[str, int], tuple[str, str]],
) -> tuple[dict[str, tuple[str, ...]], str]:
    """Require call roles to form the protocol's exact 5x4 nested schedule."""

    actual = {
        kind: tuple(states[(kind, attempt)][0] for attempt in range(1, ceiling + 1))
        for kind, ceiling in CALL_CEILINGS.items()
    }
    outer_roles: dict[str, str] = {}
    inner_roles: dict[str, list[str]] = {}
    all_prediction_roles: set[str] = set()

    for role_id in actual["verifier_predict"]:
        parts = role_id.split("/")
        if not all(_ROLE_SEGMENT.fullmatch(part) for part in parts):
            raise PermissionError("call role schedule contains a malformed candidate role ID")
        if len(parts) == 3 and parts[0] == "candidate" and parts[2] == "outer":
            outer_id = parts[1]
            if outer_id in outer_roles:
                raise PermissionError("call role schedule repeats an outer candidate role")
            outer_roles[outer_id] = role_id
        elif len(parts) == 4 and parts[0] == "candidate" and parts[3] == "inner":
            outer_id = parts[1]
            inner_roles.setdefault(outer_id, []).append(role_id)
        else:
            raise PermissionError("call role schedule contains a non-protocol candidate role")
        if role_id in all_prediction_roles:
            raise PermissionError("call role schedule repeats a prediction role")
        all_prediction_roles.add(role_id)

    outer_ids = tuple(sorted(outer_roles))
    if (
        len(outer_ids) != 5
        or set(inner_roles) != set(outer_ids)
        or any(len(items) != 4 or len(set(items)) != 4 for items in inner_roles.values())
    ):
        raise PermissionError("call role schedule is not the frozen five-outer by four-inner graph")

    expected_fits: list[str] = []
    expected_predictions: list[str] = []
    expected_decoders: list[str] = []
    expected_evaluators: list[str] = []
    for outer_id in outer_ids:
        ordered_inner = tuple(sorted(inner_roles[outer_id]))
        if any(role_id.split("/")[1] != outer_id for role_id in ordered_inner):
            raise PermissionError("call role schedule crosses outer-fold boundaries")
        expected_fits.extend(
            f"verifier/{outer_id}/{role_id.split('/')[2]}"
            for role_id in ordered_inner
        )
        expected_fits.append(f"verifier/{outer_id}/outer")
        expected_predictions.extend(ordered_inner)
        expected_predictions.append(outer_roles[outer_id])
        for role_id in ordered_inner:
            expected_decoders.extend((role_id,) * len(CALL_THRESHOLDS))
        expected_decoders.append(outer_roles[outer_id])
        expected_evaluators.extend(
            f"threshold/{outer_id}/{threshold}" for threshold in CALL_THRESHOLDS
        )
        expected_evaluators.append(f"outer/{outer_id}")

    expected = {
        "verifier_fit": tuple(expected_fits),
        "verifier_predict": tuple(expected_predictions),
        "decoder": tuple(expected_decoders),
        "event_evaluator": tuple(expected_evaluators),
        "pooled_reduction": ("pooled/outer",),
    }
    if actual != expected:
        raise PermissionError("call role schedule does not match the fixed five-by-four Stage B plan")
    schedule_sha256 = hashlib.sha256(_canonical({
        kind: list(role_ids) for kind, role_ids in expected.items()
    })).hexdigest()
    return expected, schedule_sha256


def _replay_call_event_accounting(
    event_payloads: Iterable[tuple[str, Mapping[str, object]]],
    *,
    ledger_tail_sha256: str,
    expected_role_ids_by_kind: Mapping[str, Iterable[str]] | None = None,
    expected_role_graph_sha256: str | None = None,
    expected_fit_training_roles_by_verifier: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, object]:
    """Replay the exact global call schedule and any durable fit summaries."""

    counts = dict.fromkeys(CALL_CEILINGS, 0)
    event_payloads = tuple(event_payloads)
    require_fit_provenance = expected_role_ids_by_kind is not None or any(
        event == "verifier_fit_provenance" for event, _ in event_payloads
    )
    states: dict[tuple[str, int], tuple[str, str]] = {}
    reserved_order: list[tuple[str, str]] = []
    started_order: list[tuple[str, str, int]] = []
    finished_order: list[tuple[str, str, int]] = []
    lifecycle_order: list[tuple[str, str, str, int]] = []
    fit_provenance: list[dict[str, object]] = []
    pending_fit: tuple[str, int] | None = None
    call_event_count = 0
    try:
        for event, payload in event_payloads:
            if type(event) is not str or not isinstance(payload, Mapping):
                raise ValueError("ledger event has an invalid type")
            if require_fit_provenance and pending_fit is not None and event != "verifier_fit_provenance":
                raise ValueError("fit provenance is missing or not adjacent to its completed fit")
            if event == "verifier_fit_provenance":
                if pending_fit is None:
                    raise ValueError("fit provenance has no immediately preceding completed fit")
                role_id, attempt = pending_fit
                _validate_fit_provenance_payload(
                    payload, expected_role_id=role_id, expected_attempt=attempt,
                )
                fit_provenance.append(dict(payload))
                lifecycle_order.append((event, "verifier_fit", role_id, attempt))
                pending_fit = None
                continue
            if event not in {"call_reserved", "call_started", "call_finished"}:
                if event.startswith("call_"):
                    raise ValueError("unknown call event")
                continue
            if event == "call_reserved":
                if set(payload) != {"kind", "role_id", "attempt", "ceiling"}:
                    raise ValueError("call reservation has an unknown schema")
                kind, role_id = payload["kind"], payload["role_id"]
                attempt, ceiling = payload["attempt"], payload["ceiling"]
                if (
                    type(kind) is not str or kind not in CALL_CEILINGS
                    or type(role_id) is not str or not role_id
                    or type(attempt) is not int or type(ceiling) is not int
                    or ceiling != CALL_CEILINGS[kind]
                    or attempt != counts[kind] + 1
                ):
                    raise ValueError("call reservation differs from its fixed ceiling or sequence")
                counts[kind] += 1
                states[(kind, attempt)] = (role_id, "reserved")
                reserved_order.append((kind, role_id))
                lifecycle_order.append((event, kind, role_id, attempt))
            elif event == "call_started":
                if set(payload) != {"kind", "role_id", "attempt"}:
                    raise ValueError("call start has an unknown schema")
                kind, role_id, attempt = payload["kind"], payload["role_id"], payload["attempt"]
                if (
                    type(kind) is not str or kind not in CALL_CEILINGS
                    or type(role_id) is not str or type(attempt) is not int
                    or states.get((kind, attempt)) != (role_id, "reserved")
                ):
                    raise ValueError("call start has no unique durable reservation")
                states[(kind, attempt)] = (role_id, "started")
                started_order.append((kind, role_id, attempt))
                lifecycle_order.append((event, kind, role_id, attempt))
            else:
                if set(payload) != {"kind", "role_id", "attempt", "outcome"}:
                    raise ValueError("call finish has an unknown schema")
                kind, role_id, attempt, outcome = (
                    payload["kind"], payload["role_id"], payload["attempt"], payload["outcome"],
                )
                if (
                    type(kind) is not str or kind not in CALL_CEILINGS
                    or type(role_id) is not str or type(attempt) is not int
                    or type(outcome) is not str or outcome not in {"succeeded", "failed"}
                    or states.get((kind, attempt)) != (role_id, "started")
                ):
                    raise ValueError("call finish has no unique durable start")
                states[(kind, attempt)] = (role_id, outcome)
                finished_order.append((kind, role_id, attempt))
                lifecycle_order.append((event, kind, role_id, attempt))
                if kind == "verifier_fit" and require_fit_provenance:
                    if outcome != "succeeded":
                        raise ValueError("failed fit cannot publish fit provenance")
                    pending_fit = (role_id, attempt)
            call_event_count += 1
    except (KeyError, TypeError, ValueError) as exc:
        raise PermissionError("durable call-event accounting cannot replay the ledger") from exc

    if (
        type(ledger_tail_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", ledger_tail_sha256)
        or counts != CALL_CEILINGS
        or len(states) != sum(CALL_CEILINGS.values())
        or any(state != "succeeded" for _, state in states.values())
        or call_event_count != 3 * sum(CALL_CEILINGS.values())
    ):
        raise PermissionError("durable call-event accounting does not prove every fixed call succeeded")
    state_payload = [
        [kind, attempt, role_id, state]
        for (kind, attempt), (role_id, state) in sorted(states.items())
    ]
    role_ids_by_kind, role_schedule_sha256 = _fixed_call_role_schedule(states)
    expected_order = _expected_global_call_order(role_ids_by_kind)
    if tuple(reserved_order) != expected_order:
        raise PermissionError("durable calls do not follow the fixed global call order")
    expected_transition_order: list[tuple[str, str, int]] = []
    attempts_by_kind = dict.fromkeys(CALL_CEILINGS, 0)
    for kind, role_id in expected_order:
        attempts_by_kind[kind] += 1
        expected_transition_order.append((kind, role_id, attempts_by_kind[kind]))
    if (
        tuple(started_order) != tuple(expected_transition_order)
        or tuple(finished_order) != tuple(expected_transition_order)
    ):
        raise PermissionError("durable call lifecycle does not follow the fixed global call event order")
    if expected_role_ids_by_kind is not None:
        try:
            frozen_schedule = {
                kind: tuple(role_ids)
                for kind, role_ids in expected_role_ids_by_kind.items()
            }
        except (AttributeError, TypeError) as exc:
            raise PermissionError("frozen role graph call schedule is malformed") from exc
        if set(frozen_schedule) != set(CALL_CEILINGS) or frozen_schedule != role_ids_by_kind:
            raise PermissionError("durable call role IDs differ from the frozen role graph schedule")
        if (
            type(expected_role_graph_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_role_graph_sha256)
            or expected_fit_training_roles_by_verifier is None
        ):
            raise PermissionError("durable call accounting lacks the frozen role graph hash")
    elif expected_role_graph_sha256 is not None or expected_fit_training_roles_by_verifier is not None:
        raise PermissionError("frozen role graph identity is present without its role schedule")
    if expected_role_ids_by_kind is not None or fit_provenance:
        fit_role_ids = role_ids_by_kind["verifier_fit"]
        if expected_fit_training_roles_by_verifier is not None:
            try:
                expected_training = {
                    verifier_id: tuple(role_ids)
                    for verifier_id, role_ids in expected_fit_training_roles_by_verifier.items()
                }
            except (AttributeError, TypeError) as exc:
                raise PermissionError("frozen fit role graph is malformed") from exc
            if (
                set(expected_training) != set(fit_role_ids)
                or any(
                    tuple(item.get("training_candidate_roles", ())) != expected_training.get(item.get("verifier_role_id"))
                    for item in fit_provenance
                )
            ):
                raise PermissionError("durable fit provenance training roles differ from the frozen candidate graph")
        if (
            len(fit_provenance) != CALL_CEILINGS["verifier_fit"]
            or tuple(item.get("verifier_role_id") for item in fit_provenance) != fit_role_ids
            or tuple(item.get("fit_attempt") for item in fit_provenance)
            != tuple(range(1, CALL_CEILINGS["verifier_fit"] + 1))
        ):
            raise PermissionError("durable fit provenance does not match all 25 frozen fit calls")
    call_sequence_sha256 = hashlib.sha256(
        _canonical([list(item) for item in lifecycle_order])
    ).hexdigest()
    fit_provenance_sha256 = hashlib.sha256(_canonical(fit_provenance)).hexdigest()
    audit = {
        "schema": "route2_fixed_call_event_accounting_v4",
        "counts": counts,
        "call_event_count": call_event_count,
        "ledger_tail_sha256": ledger_tail_sha256,
        "call_states_sha256": hashlib.sha256(_canonical(state_payload)).hexdigest(),
        "call_role_schedule_sha256": role_schedule_sha256,
        "call_sequence_sha256": call_sequence_sha256,
        "fit_provenance_sha256": fit_provenance_sha256,
        "role_graph_sha256": expected_role_graph_sha256,
    }
    return {
        "call_event_count": call_event_count,
        "call_event_accounting_sha256": hashlib.sha256(_canonical(audit)).hexdigest(),
        "call_role_schedule_sha256": role_schedule_sha256,
        "call_sequence_sha256": call_sequence_sha256,
        "fit_provenance_sha256": fit_provenance_sha256,
        "role_graph_sha256": expected_role_graph_sha256,
        "fit_provenance": tuple(fit_provenance),
        "role_ids_by_kind": role_ids_by_kind,
    }


STAGE_A_CURRENT_DISK_V1 = "stage_a_current_v1"
STAGE_A_CAPACITY_UPPER_BOUND_V2 = "stage_a_capacity_upper_bound_v2"


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    stage_a_wall_ns: int = 1_200_000_000_000
    total_wall_ns: int = 3_600_000_000_000
    fit_wall_ns: int = 900_000_000_000
    rss_cap_bytes: int = 4_294_967_296
    stage_a_disk_bytes: int = 2_147_483_648
    total_disk_bytes: int = 4_294_967_296
    startup_free_disk_bytes: int = 8_589_934_592
    worker_limit: int = 2
    stage_b_disk_slack_bytes: int = 268_435_456
    stage_b_rss_slack_bytes: int = 536_870_912
    # The default retains the historical generic/synthetic protocol. The new
    # production assembly requires V2 explicitly, with a new frozen digest.
    stage_a_disk_accounting_mode: str = STAGE_A_CURRENT_DISK_V1

    def __post_init__(self) -> None:
        values = tuple(value for name, value in asdict(self).items()
                       if name != "stage_a_disk_accounting_mode")
        if any(type(value) is not int for value in values):
            raise ValueError("every budget limit must be an exact integer")
        if any(value <= 0 for value in values):
            raise ValueError("every budget limit must be positive")
        if self.stage_a_wall_ns > self.total_wall_ns:
            raise ValueError("Stage A wall ceiling exceeds the study ceiling")
        if self.fit_wall_ns > self.total_wall_ns:
            raise ValueError("fit wall ceiling exceeds the study ceiling")
        if self.stage_a_disk_bytes > self.total_disk_bytes:
            raise ValueError("Stage A disk ceiling exceeds the study ceiling")
        if (type(self.stage_a_disk_accounting_mode) is not str
                or self.stage_a_disk_accounting_mode not in
                    (STAGE_A_CURRENT_DISK_V1, STAGE_A_CAPACITY_UPPER_BOUND_V2)):
            raise ValueError("explicit supported Stage A disk accounting protocol is required")

    def digest(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


@dataclass(frozen=True, slots=True)
class NestedBackingSample:
    """Observed carrier topology, not a disk cap or execution authority.

    The outer Windows GUID is carried by the surrounding receipt/snapshot.
    The original canonical host response retains both held-file identities.
    Candidate reserve values are never supplied by defaults in this type.
    """

    carrier_vhdx_path: str
    carrier_volume_id: str
    carrier_free_bytes: int
    carrier_min_free_bytes: int
    carrier_disk_number: int
    physical_disk_number: int
    host_response_json: str


def nested_backing_from_payload(value):
    """Decode fixed JSON metadata; this does not register a native producer."""
    if value is None:
        return None
    if type(value) is not dict or set(value) != {item.name for item in fields(NestedBackingSample)}:
        raise PermissionError("nested backing JSON has missing or unknown fields")
    return NestedBackingSample(**value)


def require_nested_backing_sample(sample, *, windows_vhdx_path, windows_volume_id,
                                  windows_free_bytes) -> None:
    """Validate the V2 observation shape; only native ports produce authority."""
    guid = r"\\\\\?\\Volume\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}\\"
    if (type(sample) is not NestedBackingSample
            or type(sample.carrier_vhdx_path) is not str
            or type(sample.carrier_volume_id) is not str
            or type(windows_volume_id) is not str
            or not re.fullmatch(guid, sample.carrier_volume_id)
            or not re.fullmatch(guid, windows_volume_id)
            or sample.carrier_volume_id == windows_volume_id
            or any(type(value) is not int or value < 0 for value in (
                sample.carrier_free_bytes, sample.carrier_min_free_bytes,
                sample.carrier_disk_number, sample.physical_disk_number, windows_free_bytes))
            or sample.carrier_min_free_bytes <= 0
            or sample.carrier_disk_number == sample.physical_disk_number
            or type(sample.host_response_json) is not str
            or not 0 < len(sample.host_response_json.encode("utf-8")) <= 4096):
        raise PermissionError("nested carrier/physical backing observation is incomplete")
    for value, name in ((sample.carrier_vhdx_path, None), (windows_vhdx_path, "ext4.vhdx")):
        if type(value) is not str:
            raise PermissionError("nested backing requires exact Windows paths")
        path = PureWindowsPath(value)
        if (not path.is_absolute() or not re.fullmatch(r"[A-Z]:", path.drive)
                or str(path) != value or ".." in path.parts
                or (name is not None and path.name != name)
                or (name is None and path.suffix != ".vhdx")):
            raise PermissionError("nested backing path is not canonical and local")
    if sample.carrier_vhdx_path == windows_vhdx_path:
        raise PermissionError("carrier and guest VHDX are the same file path")
    try:
        body = json.loads(sample.host_response_json)
        expected = {"schema", "distro", "distro_registry_id", "windows_vhdx_path",
                    "carrier_vhdx_path", "carrier_volume_id", "windows_volume_id", "nonce",
                    "carrier_available_bytes", "carrier_total_free_bytes", "available_bytes",
                    "total_free_bytes", "carrier_file_identity", "guest_vhdx_file_identity",
                    "carrier_disk_number", "physical_disk_number"}
        if (type(body) is not dict or set(body) != expected
                or _canonical(body).decode("utf-8") != sample.host_response_json
                or body["schema"] != "route2_host_backing_sample_v2"
                or any(type(body[key]) is not str for key in
                       ("distro", "distro_registry_id", "nonce"))
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", body["distro"])
                or not re.fullmatch(r"\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}",
                                    body["distro_registry_id"])
                or not re.fullmatch(r"[0-9a-f]{32}", body["nonce"])):
            raise ValueError("canonical topology response fields")
        bindings = {"windows_vhdx_path": windows_vhdx_path, "windows_volume_id": windows_volume_id,
                    "carrier_vhdx_path": sample.carrier_vhdx_path,
                    "carrier_volume_id": sample.carrier_volume_id,
                    "carrier_disk_number": sample.carrier_disk_number,
                    "physical_disk_number": sample.physical_disk_number}
        if any(type(body[key]) is not type(value) or body[key] != value
               for key, value in bindings.items()):
            raise ValueError("carrier/physical response binding")
        for key in ("available_bytes", "total_free_bytes", "carrier_available_bytes",
                    "carrier_total_free_bytes"):
            if type(body[key]) is not int or body[key] < 0:
                raise ValueError("native free bytes")
        if (min(body["available_bytes"], body["total_free_bytes"]) != windows_free_bytes
                or min(body["carrier_available_bytes"], body["carrier_total_free_bytes"])
                    != sample.carrier_free_bytes):
            raise ValueError("native layer free byte reduction")
        for key in ("carrier_file_identity", "guest_vhdx_file_identity"):
            identity = body[key]
            if (type(identity) is not dict or set(identity) != {"volume_serial_number", "file_id_hex"}
                    or type(identity["volume_serial_number"]) is not int
                    or not 0 <= identity["volume_serial_number"] < 1 << 64
                    or type(identity["file_id_hex"]) is not str
                    or not re.fullmatch(r"[0-9a-f]{32}", identity["file_id_hex"])):
                raise ValueError("held native file identity")
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise PermissionError("nested host response is malformed or unbound") from exc


def nested_backing_identity(sample, *, windows_vhdx_path, windows_volume_id, windows_free_bytes):
    """Return identity fields only, excluding changing balances and nonces."""
    require_nested_backing_sample(sample, windows_vhdx_path=windows_vhdx_path,
        windows_volume_id=windows_volume_id, windows_free_bytes=windows_free_bytes)
    response = json.loads(sample.host_response_json)
    return (windows_vhdx_path, windows_volume_id, sample.carrier_vhdx_path,
            sample.carrier_volume_id, sample.carrier_min_free_bytes, sample.carrier_disk_number,
            sample.physical_disk_number, response["carrier_file_identity"],
            response["guest_vhdx_file_identity"], response["distro"], response["distro_registry_id"])


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    """Live usage plus a disk peak value interpreted by the frozen protocol.

    In capacity-upper-bound V2, study_disk_peak_bytes is a conservative hard
    capacity bound, not a measured peak. study_disk_current_bytes remains live
    inner filesystem usage; image allocated bytes are separate physical data.
    """
    process_tree_rss_bytes: int
    study_disk_peak_bytes: int
    compute_workers: int
    available_ram_bytes: int
    study_disk_current_bytes: int
    guest_backing_free_bytes: int
    guest_backing_mount_id: str
    guest_backing_device: str
    windows_vhdx_path: str
    windows_volume_id: str
    windows_volume_free_bytes: int
    study_mount_id: str
    study_device: str
    study_fs_capacity_bytes: int
    study_fs_uuid: str
    study_loop_device: str
    study_image_path: str
    study_image_dev: int
    study_image_inode: int
    study_image_length_bytes: int
    study_image_allocated_bytes: int
    # None retains the historical generic receipt shape. Concrete production
    # requires V2 explicitly; it never converts None into measured topology.
    nested_backing: NestedBackingSample | None = None

    def __post_init__(self) -> None:
        values = (
            self.process_tree_rss_bytes,
            self.study_disk_peak_bytes,
            self.compute_workers,
            self.available_ram_bytes,
            self.study_disk_current_bytes,
            self.guest_backing_free_bytes,
            self.windows_volume_free_bytes,
            self.study_fs_capacity_bytes,
            self.study_image_dev,
            self.study_image_inode,
            self.study_image_length_bytes,
            self.study_image_allocated_bytes,
        )
        if any(type(value) is not int for value in values):
            raise ValueError("resource snapshot values must be exact integers")
        if min(values) < 0:
            raise ValueError("resource snapshot contains a negative observation")
        if self.study_disk_current_bytes > self.study_disk_peak_bytes:
            raise ValueError("current disk usage exceeds the stated peak")
        if self.nested_backing is not None and type(self.nested_backing) is not NestedBackingSample:
            raise ValueError("resource snapshot has an undecoded nested backing sample")


def stage_a_projection_disk_bytes(snapshot: ResourceSnapshot, limits: BudgetLimits) -> int:
    """Return D_A under the explicit frozen accounting mode, never infer it."""
    if type(snapshot) is not ResourceSnapshot or type(limits) is not BudgetLimits:
        raise PermissionError("Stage A accounting requires exact snapshot and budget types")
    if limits.stage_a_disk_accounting_mode == STAGE_A_CURRENT_DISK_V1:
        return snapshot.study_disk_current_bytes
    if (limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or snapshot.study_image_length_bytes != limits.stage_a_disk_bytes
            or not 0 < snapshot.study_fs_capacity_bytes <= limits.stage_a_disk_bytes
            or not 0 <= snapshot.study_disk_current_bytes <= snapshot.study_fs_capacity_bytes
            or snapshot.study_disk_peak_bytes != limits.stage_a_disk_bytes):
        raise PermissionError("Stage A strict capacity upper bound lacks its fixed volume evidence")
    return limits.stage_a_disk_bytes


def require_fixed_native_budget(limits: BudgetLimits) -> None:
    """Native 2->4 GiB primitives retain fixed amounts for either named mode."""
    if (type(limits) is not BudgetLimits
            or limits != BudgetLimits(stage_a_disk_accounting_mode=limits.stage_a_disk_accounting_mode)):
        raise PermissionError("native volume requires the fixed amounts and an explicit accounting mode")


def require_two_layer_startup_free(snapshot: ResourceSnapshot, limits: BudgetLimits) -> None:
    """The VHD's virtual `df` space cannot stand in for host physical free space."""

    if not all((
        snapshot.guest_backing_mount_id,
        snapshot.guest_backing_device,
        snapshot.windows_vhdx_path,
        snapshot.windows_volume_id,
    )):
        raise PermissionError("WSL backing and Windows VHDX volume identity is incomplete")
    if (
        snapshot.guest_backing_free_bytes < limits.startup_free_disk_bytes
        or snapshot.windows_volume_free_bytes < limits.startup_free_disk_bytes
    ):
        raise RuntimeError("two-layer startup free-disk hard line is not met")
    if snapshot.nested_backing is not None:
        require_nested_backing_sample(snapshot.nested_backing,
            windows_vhdx_path=snapshot.windows_vhdx_path, windows_volume_id=snapshot.windows_volume_id,
            windows_free_bytes=snapshot.windows_volume_free_bytes)
        if snapshot.nested_backing.carrier_free_bytes < snapshot.nested_backing.carrier_min_free_bytes:
            raise RuntimeError("separately sealed carrier growth/cleanup reserve is not met")


def require_stage_filesystem(
    snapshot: ResourceSnapshot, expected: ResourceSnapshot, capacity_ceiling_bytes: int,
) -> None:
    """Check the same mounted filesystem still enforces the phase capacity."""

    frozen = (
        expected.study_mount_id,
        expected.study_device,
        expected.study_fs_uuid,
        expected.study_loop_device,
        expected.study_image_path,
        expected.study_image_dev,
        expected.study_image_inode,
    )
    observed = (
        snapshot.study_mount_id,
        snapshot.study_device,
        snapshot.study_fs_uuid,
        snapshot.study_loop_device,
        snapshot.study_image_path,
        snapshot.study_image_dev,
        snapshot.study_image_inode,
    )
    if not all(frozen):
        raise PermissionError("study mount identity was not frozen")
    if observed != frozen:
        raise PermissionError("study mount, loop, image or filesystem identity changed during the invocation")
    if expected.nested_backing is not None or snapshot.nested_backing is not None:
        def backing_identity(value):
            return (value.guest_backing_mount_id, value.guest_backing_device,
                    nested_backing_identity(value.nested_backing, windows_vhdx_path=value.windows_vhdx_path,
                        windows_volume_id=value.windows_volume_id, windows_free_bytes=value.windows_volume_free_bytes))
        if backing_identity(snapshot) != backing_identity(expected):
            raise PermissionError("original nested guest/carrier/physical backing identity changed")
    if snapshot.study_fs_capacity_bytes > capacity_ceiling_bytes:
        raise RuntimeError("study filesystem capacity exceeds the phase hard limit")
    if snapshot.study_image_length_bytes > capacity_ceiling_bytes:
        raise RuntimeError("study image length exceeds the phase hard limit")


def require_precreate_order(
    invocation_started_ns: int,
    free_checked_ns: int,
    image_created_ns: int,
    guest_free_bytes: int,
    host_free_bytes: int,
    required_free_bytes: int,
) -> None:
    """Reject a quota receipt sampled only after the formal image existed."""

    if any(type(value) is not int for value in (
        invocation_started_ns, free_checked_ns, image_created_ns,
        guest_free_bytes, host_free_bytes, required_free_bytes,
    )) or not (0 < invocation_started_ns <= free_checked_ns < image_created_ns):
        raise PermissionError("pre-create two-layer free sampling order is not proven")
    if min(guest_free_bytes, host_free_bytes) < required_free_bytes:
        raise RuntimeError("pre-create two-layer free-disk hard line is not met")


@dataclass(frozen=True, slots=True)
class EnforcementReceipt:
    """Evidence from a separately reviewed external hard-limit controller.

    An in-process assertion is insufficient: review must bind ``controller_id``
    to the installed OS controller, its implementation hash, covered volumes,
    and the exact approved study invocation before use.
    """

    controller_id: str
    controller_sha256: str
    study_root: str
    ledger_path: str
    lock_path: str
    covered_write_volumes: tuple[str, ...]
    hard_rss: bool
    hard_worker_threads: bool
    hard_disk_peak: bool
    hard_wall: bool
    evidence_sha256: str
    parent_cgroup_path: str
    memory_max_bytes: int
    memory_swap_max_bytes: int
    pids_max: int
    rlimit_as_per_process_bytes: int
    stage_a_capacity_bytes: int
    total_capacity_bytes: int
    guest_backing_mount_id: str
    windows_volume_id: str
    invocation_started_monotonic_ns: int
    precreate_free_checked_monotonic_ns: int
    image_created_monotonic_ns: int
    precreate_guest_free_bytes: int
    precreate_windows_volume_free_bytes: int
    study_fs_uuid: str
    study_loop_device: str
    study_image_path: str
    study_image_dev: int
    study_image_inode: int
    study_image_length_bytes: int
    precreate_nested_backing: NestedBackingSample | None = None

    def require_complete(self) -> None:
        if (self.precreate_nested_backing is not None
                and type(self.precreate_nested_backing) is not NestedBackingSample):
            raise PermissionError("controller receipt has an undecoded nested backing sample")
        if (
            not self.controller_id
            or len(self.controller_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.controller_sha256.lower())
            or not self.covered_write_volumes
            or not all((self.hard_rss, self.hard_worker_threads, self.hard_disk_peak, self.hard_wall))
            or len(self.evidence_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.evidence_sha256.lower())
            or not self.parent_cgroup_path
            or not self.guest_backing_mount_id
            or not self.windows_volume_id
            or not self.study_fs_uuid
            or not self.study_loop_device
            or not self.study_image_path
            or any(
                type(value) is not int or value < 0
                for value in (
                    self.memory_max_bytes,
                    self.memory_swap_max_bytes,
                    self.pids_max,
                    self.rlimit_as_per_process_bytes,
                    self.stage_a_capacity_bytes,
                    self.total_capacity_bytes,
                    self.invocation_started_monotonic_ns,
                    self.precreate_free_checked_monotonic_ns,
                    self.image_created_monotonic_ns,
                    self.precreate_guest_free_bytes,
                    self.precreate_windows_volume_free_bytes,
                    self.study_image_dev,
                    self.study_image_inode,
                    self.study_image_length_bytes,
                )
            )
        ):
            raise PermissionError("audited OS hard-limit coverage is incomplete")


class ResourceEnforcer(Protocol):
    """External platform controller; sampled monitoring alone is inadequate.

    prepare_volume owns the image and OS envelope, plus an external durable
    pre-image one-shot attempt. It must leave the inner study root/lock/ledger
    absent; AppendOnlyLedger is their only creator. A bound lifecycle uses the
    same concrete controller for ResourceEnforcer and SupervisorOps, including
    durable abort_startup cleanup/quarantine. That production adapter is still
    required; this protocol does not provide it.
    """

    def prepare_volume(
        self,
        study_root: Path,
        ledger_path: Path,
        lock_path: Path,
        limits: BudgetLimits,
        invocation_started_monotonic_ns: int,
    ) -> tuple[EnforcementReceipt, ResourceSnapshot]: ...
    def current_snapshot(self, study_root: Path) -> ResourceSnapshot: ...
    def enforce_during_activity(
        self,
        study_root: Path,
        limits: BudgetLimits,
        activity: str,
        *,
        remaining_total_wall_ns: int,
        remaining_stage_a_wall_ns: int | None,
        remaining_fit_wall_ns: int | None,
        frozen_rss_ceiling_bytes: int,
    ) -> object: ...
    def stop_activity(self, handle: object) -> ResourceSnapshot: ...
    def expand_after_stage_b_entry(
        self, study_root: Path, limits: BudgetLimits, entry_event_sha256: str,
    ) -> ResourceSnapshot: ...


class UnavailableResourceEnforcer:
    """Safe default while no independently reviewed OS controller exists."""

    def prepare_volume(self, *args: object, **kwargs: object) -> tuple[EnforcementReceipt, ResourceSnapshot]:
        raise PermissionError("no independently reviewed OS hard-limit controller is installed")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sync_directory(path: Path) -> None:
    """Persist namespace changes; failure never permits startup continuation."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise PermissionError("startup parent is not a directory")
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True, slots=True)
class PredictionFreezeReceipt:
    phase: Literal["inner", "outer"]
    role_id: str
    outer_id: str
    threshold: str
    prediction_path: str
    prediction_sha256: str
    predict_attempt: int
    decoder_attempt: int
    ledger_event_sha256: str


@dataclass(frozen=True, slots=True)
class DurableEventReceipt:
    event_sha256: str
    fsynced_monotonic_ns: int


class AppendOnlyLedger:
    """A hash-chained journal that is created once and never resumed."""

    def __init__(self, path: Path, lock_path: Path, study_root: Path):
        self.path = path
        self.lock_path = lock_path
        self.study_root = study_root
        self._fd: int | None = None
        self._seq = 0
        self._tail = ZERO_HASH
        self._guard = threading.RLock()
        self._poisoned = False
        self._terminal = False
        self._owner_thread_id: int | None = None
        self._reference_roles: set[str] = set()
        self._reference_passed: set[str] = set()
        self._treatment_roles: set[str] = set()
        self._treatment_finished: dict[str, CandidateFileReceipt] = {}
        self._different_treatment_roles: set[str] = set()
        self._call_counts = dict.fromkeys(CALL_CEILINGS, 0)
        self._call_state: dict[tuple[str, int], tuple[str, str]] = {}
        self._frozen_predictions: dict[tuple[str, str, str, str], PredictionFreezeReceipt] = {}
        self._stage_b_entry_passed = False
        self._stage_b_entry_event_hash: str | None = None
        self._stage_b_volume_expanded = False
        self._active_gt_release: str | None = None
        self._terminal_sha256: str | None = None
        self._closed_at_monotonic_ns: int | None = None
        self._invocation_id: str | None = None
        self._invocation_started_monotonic_ns: int | None = None
        self._stage_a_finished = False
        self._stage_b_complete = False
        self._create_entered = False
        self._created_monotonic_ns: int | None = None
        self._lock_identity: tuple[int, ...] | None = None
        self._lock_sha256: str | None = None

    def _require_exact_paths(self) -> None:
        expected_root = self.study_root.parent / STUDY_ID
        expected_ledger = self.study_root.parent / f"{STUDY_ID}-budget.jsonl"
        expected_lock = self.study_root.parent / f"{STUDY_ID}.lock"
        if not all(path.is_absolute() for path in (self.study_root, self.path, self.lock_path)):
            raise ValueError("study paths must be absolute")
        if (self.study_root, self.path, self.lock_path) != (expected_root, expected_ledger, expected_lock):
            raise ValueError("study output, ledger, and lock must be exact approved sibling paths")
        if any(path.parent.is_symlink() for path in (self.study_root, self.path, self.lock_path)):
            raise PermissionError("study parent must not be a symlink")

    def create(self, approval: ExperimentApproval, limits: BudgetLimits) -> None:
        if type(approval) is not ExperimentApproval:
            raise PermissionError("ledger creation requires an exact ExperimentApproval")
        approval.require_full_ab()
        self._require_exact_paths()
        if (
            str(self.study_root) != approval.study_root_path
            or str(self.path) != approval.budget_ledger_path
            or str(self.lock_path) != approval.lock_path
        ):
            raise PermissionError("ledger paths differ from the frozen A+B approval")
        if approval.study_id != STUDY_ID or approval.budget_policy_sha256.lower() != limits.digest():
            raise PermissionError("authorization does not bind this study and budget policy")
        if self._fd is not None:
            raise RuntimeError("ledger is already open")
        if self._create_entered:
            raise RuntimeError("ledger creation may be attempted only once")
        if not self.study_root.parent.is_dir():
            raise FileNotFoundError("approved study parent directory is missing")
        if self.path.exists() or self.lock_path.exists() or self.study_root.exists():
            raise FileExistsError("study output, ledger, or lock is already occupied")
        self._create_entered = True
        self._owner_thread_id = threading.get_ident()
        try:
            self._create_storage(approval, limits)
        except BaseException:
            self._poisoned = True
            _discard_owned_ledger_writer(self)
            raise

    def _create_storage(self, approval: ExperimentApproval, limits: BudgetLimits) -> None:
        # Exclusive creation is intentionally nonrecoverable.  If a crash occurs
        # after any one object is created, a second invocation may not reuse it.
        lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY
                          | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o600)
        try:
            # Occupy the ID durably before payload/root/ledger work. A partial
            # payload is still a tombstone. Initial fsync failure requires the
            # outer controller's quarantine; it is not proof of durability.
            os.fsync(lock_fd)
            _sync_directory(self.lock_path.parent)
            payload = _canonical({"study_id": STUDY_ID, "lock_id": str(uuid.uuid4())})
            if os.write(lock_fd, payload) != len(payload):
                raise OSError("partial lock-file write")
            os.fsync(lock_fd)
            info = os.fstat(lock_fd)
            self._lock_identity = (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                                   info.st_uid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            self._lock_sha256 = hashlib.sha256(payload).hexdigest()
        finally:
            os.close(lock_fd)
        self.study_root.mkdir(mode=0o700)
        _sync_directory(self.study_root.parent)
        self._fd = os.open(
            self.path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY
            | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        info = os.fstat(self._fd)
        _LEDGER_CLOSE_STATES[self] = _LedgerCloseState(
            self._fd, (info.st_dev, info.st_ino), os.getpid(), threading.get_ident(),
        )
        self.append(
            "study_created",
            {
                "study_id": STUDY_ID,
                "approval_record": approval.approval_record,
                "input_registry_sha256": approval.input_registry_sha256,
                "budget_policy_sha256": limits.digest(),
                "limits": asdict(limits),
                "created_wall_ns": time.time_ns(),
            },
        )
        _sync_directory(self.path.parent)
        self._created_monotonic_ns = time.monotonic_ns()

    def append(self, event: str, payload: dict[str, object]) -> str:
        if self._fd is None:
            raise RuntimeError("ledger has not been created under an A+B approval")
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("budget ledger has a single owner thread; concurrent mutation is forbidden")
        with self._guard:
            if self._poisoned or self._terminal:
                raise RuntimeError("ledger is poisoned or already terminal; no continuation is allowed")
            if self._stage_b_complete and event != "terminal":
                raise RuntimeError("ledger cannot continue after the durable Stage B completion event")
            if event == "invocation_started":
                invocation_id = payload.get("invocation_id")
                started_ns = payload.get("monotonic_ns")
                if (
                    self._invocation_id is not None
                    or not isinstance(invocation_id, str)
                    or not invocation_id
                    or type(started_ns) is not int
                    or started_ns <= 0
                ):
                    raise PermissionError("invocation start must be bound exactly once to a valid id and monotonic time")
            elif self._invocation_id is not None and payload.get("invocation_id") not in (None, self._invocation_id):
                raise PermissionError("ledger event invocation identity differs from its frozen start")
            body = {
                "seq": self._seq,
                "event": event,
                "payload": payload,
                "previous_sha256": self._tail,
            }
            encoded_body = _canonical(body)
            digest = hashlib.sha256(encoded_body).hexdigest()
            line = _canonical({"entry": body, "sha256": digest}) + b"\n"
            try:
                written = os.write(self._fd, line)
                if written != len(line):
                    raise OSError("partial ledger append")
                os.fsync(self._fd)
            except BaseException:
                self._poisoned = True
                raise
            self._tail = digest
            self._seq += 1
            if event == "invocation_started":
                self._invocation_id = invocation_id
                self._invocation_started_monotonic_ns = started_ns
            return digest

    def _append_durable(self, event: str, payload: dict[str, object]) -> DurableEventReceipt:
        digest = self.append(event, payload)
        return DurableEventReceipt(digest, time.monotonic_ns())

    def _require_invocation(self, invocation_id: str) -> None:
        if (
            not isinstance(invocation_id, str)
            or not invocation_id
            or self._invocation_id is None
            or invocation_id != self._invocation_id
        ):
            raise PermissionError("stage event is not bound to the started ledger invocation")

    def mark_stage_a_finished(self, payload: dict[str, object]) -> DurableEventReceipt:
        expected = {
            "invocation_id", "reference_roles", "treatment_roles",
            "different_treatment_roles", "stage_a_disk_bytes", "finished_monotonic_ns",
        }
        if self._stage_a_finished or set(payload) != expected:
            raise RuntimeError("Stage A boundary event is incomplete or already recorded")
        self._require_invocation(payload["invocation_id"])
        if (
            type(payload["reference_roles"]) is not int
            or payload["reference_roles"] != 105
            or type(payload["treatment_roles"]) is not int
            or payload["treatment_roles"] != 105
            or type(payload["different_treatment_roles"]) is not int
            or not 0 <= payload["different_treatment_roles"] <= 105
            or type(payload["stage_a_disk_bytes"]) is not int
            or payload["stage_a_disk_bytes"] < 0
            or type(payload["finished_monotonic_ns"]) is not int
            or payload["finished_monotonic_ns"] <= (self._invocation_started_monotonic_ns or 0)
        ):
            raise PermissionError("Stage A boundary event does not meet the frozen role and time contract")
        receipt = self._append_durable("stage_a_finished", payload)
        self._stage_a_finished = True
        return receipt

    def reserve_candidate_reconstruction(self, stage: str, role_id: str) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("candidate reservations must use the ledger owner thread")
        if stage == "reference":
            if self._treatment_roles:
                raise RuntimeError("all reference roles must precede every treatment role")
            if role_id in self._reference_roles or len(self._reference_roles) >= 105:
                raise RuntimeError("candidate reference role reservation is duplicated/exhausted")
        elif stage == "treatment":
            if len(self._reference_passed) != 105:
                raise RuntimeError("treatment is blocked until all 105 references pass")
            if role_id not in self._reference_roles or role_id in self._treatment_roles:
                raise RuntimeError("treatment role is unregistered or already reserved")
            if len(self._treatment_roles) >= 105:
                raise RuntimeError("candidate treatment role reservation is exhausted")
        else:
            raise ValueError("candidate reconstruction stage must be reference or treatment")
        attempt = 1 + (len(self._reference_roles) if stage == "reference" else len(self._treatment_roles))
        self.append(
            "candidate_reconstruction_reserved",
            {"stage": stage, "role_id": role_id, "attempt": attempt},
        )
        (self._reference_roles if stage == "reference" else self._treatment_roles).add(role_id)

    def mark_reference_passed(self, role_id: str, *, candidate_count: int, fingerprint: str) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("reference result must use the ledger owner thread")
        if role_id not in self._reference_roles or role_id in self._reference_passed:
            raise RuntimeError("reference pass has no unique prior reservation")
        if candidate_count < 0 or len(fingerprint) != 64:
            raise ValueError("reference pass evidence is incomplete")
        self.append(
            "reference_role_passed",
            {"role_id": role_id, "candidate_count": candidate_count, "interval_fingerprint": fingerprint},
        )
        self._reference_passed.add(role_id)

    def mark_treatment_finished(
        self,
        receipt: CandidateFileReceipt,
        *,
        interval_set_same: bool,
    ) -> None:
        """Persist one completed treatment and its exact Stage B input file."""

        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("treatment result must use the ledger owner thread")
        if type(receipt) is not CandidateFileReceipt or type(interval_set_same) is not bool:
            raise TypeError("treatment completion requires an exact candidate receipt and comparison")
        if receipt.role_id not in self._treatment_roles or receipt.role_id in self._treatment_finished:
            raise RuntimeError("treatment completion has no unique prior reservation")
        file_path = self._study_output(Path(receipt.path))
        if (
            file_path.stat().st_size != receipt.file_bytes
            or self._hash_file(file_path) != receipt.sha256.lower()
        ):
            raise ValueError("persisted treatment candidate file differs from its receipt")
        self.append(
            "treatment_role_finished",
            {**asdict(receipt), "interval_set_same": interval_set_same},
        )
        self._treatment_finished[receipt.role_id] = receipt
        if not interval_set_same:
            self._different_treatment_roles.add(receipt.role_id)

    def require_frozen_candidate(self, receipt: CandidateFileReceipt) -> None:
        """Bind Stage B to the live treatment ledger and detect mutation."""

        if type(receipt) is not CandidateFileReceipt or self._treatment_finished.get(receipt.role_id) != receipt:
            raise PermissionError("candidate receipt is absent from the live treatment ledger")
        file_path = self._study_output(Path(receipt.path))
        if (
            file_path.stat().st_size != receipt.file_bytes
            or self._hash_file(file_path) != receipt.sha256.lower()
        ):
            raise PermissionError("treatment candidate file changed after freezing")

    def _verified_call_event_accounting(self) -> dict[str, object]:
        """Replay the durable hash chain and derive fixed call counts from its events."""

        if self._fd is None:
            raise PermissionError("durable call-event accounting requires an open ledger")
        previous = ZERO_HASH
        sequence = 0
        event_payloads: list[tuple[str, Mapping[str, object]]] = []
        try:
            with self.path.open("rb") as source:
                for raw in source:
                    if not raw.endswith(b"\n") or raw == b"\n":
                        raise ValueError("call ledger has a partial record")
                    record = json.loads(raw[:-1].decode("utf-8"))
                    if (
                        not isinstance(record, dict)
                        or set(record) != {"entry", "sha256"}
                        or _canonical(record) + b"\n" != raw
                    ):
                        raise ValueError("call ledger record is not canonical")
                    body = record["entry"]
                    digest = record["sha256"]
                    if (
                        not isinstance(body, dict)
                        or set(body) != {"seq", "event", "payload", "previous_sha256"}
                        or type(body["seq"]) is not int
                        or body["seq"] != sequence
                        or body["previous_sha256"] != previous
                        or not isinstance(body["event"], str)
                        or not isinstance(body["payload"], dict)
                        or type(digest) is not str
                        or hashlib.sha256(_canonical(body)).hexdigest() != digest
                    ):
                        raise ValueError("call ledger hash chain is invalid")
                    event = body["event"]
                    payload = body["payload"]
                    event_payloads.append((event, payload))
                    previous = digest
                    sequence += 1
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise PermissionError("durable call-event accounting cannot replay the ledger") from exc
        if previous != self._tail or sequence != self._seq:
            raise PermissionError("durable call-event accounting cannot replay the ledger")
        stage_b_entries = [
            payload for event, payload in event_payloads if event == "stage_b_entry_passed"
        ]
        call_positions = [
            index for index, (event, _) in enumerate(event_payloads) if event == "call_reserved"
        ]
        entry_positions = [
            index for index, (event, _) in enumerate(event_payloads) if event == "stage_b_entry_passed"
        ]
        if len(stage_b_entries) != 1 or not call_positions or entry_positions[0] >= call_positions[0]:
            raise PermissionError("durable call-event accounting lacks its unique prior Stage B role graph entry")
        entry_payload = stage_b_entries[0]
        if set(entry_payload) != {"invocation_id", "projection"} or not isinstance(entry_payload["projection"], Mapping):
            raise PermissionError("durable Stage B entry does not contain its frozen role projection")
        _role_graph_sha256, frozen_role_ids_by_kind, frozen_fit_training_roles = _projection_call_role_ids(
            entry_payload["projection"],
        )
        replayed = _replay_call_event_accounting(
            event_payloads,
            ledger_tail_sha256=previous,
            expected_role_ids_by_kind=frozen_role_ids_by_kind,
            expected_role_graph_sha256=_role_graph_sha256,
            expected_fit_training_roles_by_verifier=frozen_fit_training_roles,
        )
        if (
            replayed["call_event_count"] != sum(1 for event, _ in event_payloads if event in {
                "call_reserved", "call_started", "call_finished",
            })
            or {kind: sum(
                1 for event, payload in event_payloads
                if event == "call_reserved" and payload.get("kind") == kind
            ) for kind in CALL_CEILINGS} != self._call_counts
        ):
            raise PermissionError("durable call-event accounting differs from the in-memory call state")
        # The replay helper establishes the event transitions; compare a state
        # digest against the in-memory ledger state to detect local drift too.
        state_payload = [
            [kind, attempt, role_id, state]
            for (kind, attempt), (role_id, state) in sorted(self._call_state.items())
        ]
        audit = {
            "schema": "route2_fixed_call_event_accounting_v4",
            "counts": self._call_counts,
            "call_event_count": replayed["call_event_count"],
            "ledger_tail_sha256": previous,
            "call_states_sha256": hashlib.sha256(_canonical(state_payload)).hexdigest(),
            "call_role_schedule_sha256": replayed["call_role_schedule_sha256"],
            "call_sequence_sha256": replayed["call_sequence_sha256"],
            "fit_provenance_sha256": replayed["fit_provenance_sha256"],
            "role_graph_sha256": replayed["role_graph_sha256"],
        }
        expected = hashlib.sha256(_canonical(audit)).hexdigest()
        if expected != replayed["call_event_accounting_sha256"]:
            raise PermissionError("durable call-event accounting differs from the in-memory call state")
        return {
            "call_event_count": replayed["call_event_count"],
            "call_event_accounting_sha256": replayed["call_event_accounting_sha256"],
            "call_sequence_sha256": replayed["call_sequence_sha256"],
            "fit_provenance_sha256": replayed["fit_provenance_sha256"],
            "fit_provenance": replayed["fit_provenance"],
            "role_graph_sha256": _role_graph_sha256,
            "role_ids_by_kind": replayed["role_ids_by_kind"],
        }

    def reserve_call(self, kind: str, role_id: str) -> int:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call reservations must use the ledger owner thread")
        if kind not in CALL_CEILINGS:
            if kind in {"candidate_fit", "candidate_predict"}:
                raise PermissionError("candidate models are forbidden in this study")
            raise ValueError(f"unknown budgeted call: {kind}")
        if not role_id:
            raise ValueError("call must be bound to a nonempty role")
        with self._guard:
            count = self._call_counts[kind]
            if count >= CALL_CEILINGS[kind]:
                raise RuntimeError(f"{kind} call ceiling is exhausted")
            self.append(
                "call_reserved",
                {"kind": kind, "role_id": role_id, "attempt": count + 1, "ceiling": CALL_CEILINGS[kind]},
            )
            self._call_counts[kind] = count + 1
            self._call_state[(kind, count + 1)] = (role_id, "reserved")
            return count + 1

    def start_call(self, kind: str, role_id: str, attempt: int) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call start must use the ledger owner thread")
        if self._call_state.get((kind, attempt)) != (role_id, "reserved"):
            raise RuntimeError("call start has no unique, matching reservation")
        self.append("call_started", {"kind": kind, "role_id": role_id, "attempt": attempt})
        self._call_state[(kind, attempt)] = (role_id, "started")

    def finish_call(self, kind: str, role_id: str, attempt: int, *, succeeded: bool) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call finish must use the ledger owner thread")
        if self._call_state.get((kind, attempt)) != (role_id, "started"):
            raise RuntimeError("call finish has no matching started attempt")
        outcome = "succeeded" if succeeded else "failed"
        self.append("call_finished", {"kind": kind, "role_id": role_id, "attempt": attempt, "outcome": outcome})
        self._call_state[(kind, attempt)] = (role_id, outcome)

    def _study_output(self, path: Path) -> Path:
        if not path.is_absolute() or path.is_symlink():
            raise PermissionError("prediction output must be an absolute, non-symlink study file")
        root = self.study_root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise PermissionError("prediction output is outside the exact study root")
        return resolved

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
        return digest.hexdigest()

    def freeze_prediction(
        self,
        *,
        phase: Literal["inner", "outer"],
        role_id: str,
        outer_id: str,
        threshold: str,
        prediction_path: Path,
        predict_attempt: int,
        decoder_attempt: int,
    ) -> PredictionFreezeReceipt:
        """Hash a persisted prediction and bind it to a successful predict call."""

        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("prediction freeze must use the ledger owner thread")
        if phase not in {"inner", "outer"} or threshold not in {"0.10", "0.25", "0.50"}:
            raise ValueError("prediction phase or frozen threshold is invalid")
        if not role_id or not outer_id:
            raise ValueError("prediction role and outer id are required")
        if self._call_state.get(("verifier_predict", predict_attempt)) != (role_id, "succeeded"):
            raise PermissionError("prediction has no completed verifier predict batch")
        if self._call_state.get(("decoder", decoder_attempt)) != (role_id, "succeeded"):
            raise PermissionError("prediction has no completed decoder call")
        key = (phase, role_id, outer_id, threshold)
        if key in self._frozen_predictions:
            raise RuntimeError("prediction receipt is already frozen")
        exact_path = self._study_output(prediction_path)
        file_hash = self._hash_file(exact_path)
        payload: dict[str, object] = {
            "phase": phase,
            "role_id": role_id,
            "outer_id": outer_id,
            "threshold": threshold,
            "prediction_path": str(exact_path),
            "prediction_sha256": file_hash,
            "predict_attempt": predict_attempt,
            "decoder_attempt": decoder_attempt,
        }
        event_hash = self.append("prediction_frozen", payload)
        receipt = PredictionFreezeReceipt(
            phase=phase,
            role_id=role_id,
            outer_id=outer_id,
            threshold=threshold,
            prediction_path=str(exact_path),
            prediction_sha256=file_hash,
            predict_attempt=predict_attempt,
            decoder_attempt=decoder_attempt,
            ledger_event_sha256=event_hash,
        )
        self._frozen_predictions[key] = receipt
        return receipt

    def require_frozen_prediction(
        self,
        receipt: PredictionFreezeReceipt,
        *,
        phase: Literal["inner", "outer"],
        role_id: str,
        outer_id: str,
        threshold: str,
    ) -> None:
        """Check the live ledger binding and detect output mutation before GT opens."""

        key = (phase, role_id, outer_id, threshold)
        if self._frozen_predictions.get(key) != receipt:
            raise PermissionError("prediction receipt does not match the live append-only ledger")
        if receipt.ledger_event_sha256 == ZERO_HASH or not receipt.ledger_event_sha256:
            raise PermissionError("prediction receipt has no persisted ledger event")
        exact_path = self._study_output(Path(receipt.prediction_path))
        if self._hash_file(exact_path) != receipt.prediction_sha256:
            raise PermissionError("frozen prediction output changed before evaluation GT opened")

    def mark_stage_b_entry(
        self, projection: dict[str, int], *, invocation_id: str,
    ) -> DurableEventReceipt:
        if not self._stage_a_finished or self._stage_b_entry_passed:
            raise RuntimeError("Stage B entry can only be recorded once")
        self._require_invocation(invocation_id)
        receipt = self._append_durable("stage_b_entry_passed", {
            "invocation_id": invocation_id,
            "projection": projection,
        })
        self._stage_b_entry_passed = True
        self._stage_b_entry_event_hash = receipt.event_sha256
        return receipt

    def mark_stage_b_volume_expanded(
        self,
        entry_event_sha256: str,
        volume: dict[str, object],
        *,
        invocation_id: str,
    ) -> DurableEventReceipt:
        if (
            not self._stage_b_entry_passed
            or self._stage_b_entry_event_hash != entry_event_sha256
            or self._stage_b_volume_expanded
            or self._active_gt_release is not None
        ):
            raise PermissionError("Stage B volume expansion lacks its unique entry gate")
        self._require_invocation(invocation_id)
        receipt = self._append_durable("stage_b_volume_expanded", {
            "invocation_id": invocation_id,
            "entry_event_sha256": entry_event_sha256,
            "volume": volume,
        })
        self._stage_b_volume_expanded = True
        return receipt

    def mark_stage_b_complete(self, payload: dict[str, object]) -> DurableEventReceipt:
        expected = {
            "invocation_id", "inner_roles_completed", "outer_roles_completed",
            "verifier_fit_calls", "verifier_predict_calls", "decoder_calls",
            "evaluator_calls", "pooled_aggregation_calls",
            "pooled_aggregation_completed", "pooled_gt_reads",
            "call_event_count", "call_event_accounting_sha256",
            "finished_monotonic_ns", "result_sha256",
        }
        if not self._stage_b_volume_expanded or self._stage_b_complete or self._active_gt_release is not None:
            raise PermissionError("Stage B completion requires the expanded volume and no active GT view")
        if set(payload) != expected:
            raise ValueError("Stage B completion event schema is incomplete or unknown")
        self._require_invocation(payload["invocation_id"])
        quota_fields = (
            "inner_roles_completed", "outer_roles_completed", "verifier_fit_calls",
            "verifier_predict_calls", "decoder_calls", "evaluator_calls",
            "pooled_aggregation_calls", "pooled_gt_reads",
        )
        if (
            any(type(payload[name]) is not int for name in quota_fields)
            or (payload["inner_roles_completed"], payload["outer_roles_completed"],
                payload["verifier_fit_calls"], payload["verifier_predict_calls"],
                payload["decoder_calls"], payload["evaluator_calls"],
                payload["pooled_aggregation_calls"], payload["pooled_gt_reads"])
            != (20, 5, 25, 25, 65, 20, 1, 0)
            or payload["pooled_aggregation_completed"] is not True
            or type(payload["finished_monotonic_ns"]) is not int
            or payload["finished_monotonic_ns"] <= (self._invocation_started_monotonic_ns or 0)
            or type(payload["call_event_count"]) is not int
            or type(payload["call_event_accounting_sha256"]) is not str
            or not isinstance(payload["result_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", payload["result_sha256"])
        ):
            raise PermissionError("Stage B completion does not meet the fixed quota and pooled no-GT contract")
        durable_call_accounting = self._verified_call_event_accounting()
        if any(
            payload[name] != durable_call_accounting[name]
            for name in ("call_event_count", "call_event_accounting_sha256")
        ):
            raise PermissionError("Stage B completion lacks matching durable call-event accounting")
        receipt = self._append_durable("stage_b_complete", payload)
        self._stage_b_complete = True
        return receipt

    @staticmethod
    def _truth_scope_digest(scope: "TruthReadScope") -> str:
        from .gt_provider import TruthReadScope

        if type(scope) is not TruthReadScope:
            raise PermissionError("GT release requires the exact reviewed truth scope")
        return hashlib.sha256(_canonical(asdict(scope))).hexdigest()

    def record_gt_release(self, scope: "TruthReadScope") -> str:
        """Persist a one-view release after the exact prediction freeze barrier."""

        from .contracts import StudyStage

        if not self._stage_b_volume_expanded or self._active_gt_release is not None:
            raise PermissionError("GT release requires Stage B expansion and no prior active view")
        scope_digest = self._truth_scope_digest(scope)
        prediction_hashes: list[str] = []
        if scope.stage == StudyStage.TRAIN_LABELS:
            if scope.prediction_receipt is not None or len(scope.role_ids) != 1:
                raise PermissionError("training GT release is not role scoped")
        elif scope.stage in (StudyStage.INNER_EVALUATION, StudyStage.OUTER_EVALUATION):
            prediction = scope.prediction_receipt
            if prediction is None:
                raise PermissionError("evaluation GT release lacks frozen predictions")
            expected = 12 if scope.stage == StudyStage.INNER_EVALUATION else 1
            if len(prediction.predictions) != expected:
                raise PermissionError("evaluation GT release lacks the full prediction barrier")
            phase = "inner" if expected == 12 else "outer"
            for item in prediction.predictions:
                self.require_frozen_prediction(
                    item, phase=phase, role_id=item.role_id,
                    outer_id=scope.outer_id, threshold=item.threshold,
                )
                prediction_hashes.append(item.ledger_event_sha256)
        else:
            raise PermissionError("Stage A has no GT release")
        digest = self.append("gt_phase_released", {
            "scope_sha256": scope_digest,
            "stage": scope.stage.value,
            "outer_id": scope.outer_id,
            "role_ids": list(scope.role_ids),
            "prediction_event_sha256": prediction_hashes,
        })
        self._active_gt_release = digest
        return digest

    def record_gt_revoke(
        self, scope: "TruthReadScope", release_event_sha256: str, os_revoke_receipt_sha256: str,
    ) -> str:
        """Record OS-observed teardown; the controller must attest it independently."""

        if self._active_gt_release != release_event_sha256:
            raise PermissionError("GT revoke differs from the sole active view")
        if len(os_revoke_receipt_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in os_revoke_receipt_sha256.lower()
        ):
            raise PermissionError("OS GT mount teardown receipt is missing")
        digest = self.append("gt_phase_view_revoked", {
            "scope_sha256": self._truth_scope_digest(scope),
            "release_event_sha256": release_event_sha256,
            "os_revoke_receipt_sha256": os_revoke_receipt_sha256.lower(),
        })
        self._active_gt_release = None
        return digest

    def require_gt_release(self, scope: "TruthReadScope", release_event_sha256: str) -> None:
        """Rebuild the durable ledger chain, including in a fresh phase child."""

        expected_scope = self._truth_scope_digest(scope)
        if len(release_event_sha256) != 64:
            raise PermissionError("GT release hash is missing")
        previous = ZERO_HASH
        entry_passed = False
        entry_event_sha256: str | None = None
        volume_expanded = False
        prediction_events: dict[str, dict[str, object]] = {}
        completed_calls: set[tuple[str, str, int]] = set()
        release_found = False
        release_revoked = False
        with self.path.open("rb") as source:
            for line in source:
                record = json.loads(line)
                body = record["entry"]
                digest = record["sha256"]
                if body["previous_sha256"] != previous or hashlib.sha256(_canonical(body)).hexdigest() != digest:
                    raise PermissionError("GT release ledger chain is invalid")
                previous = digest
                event = body["event"]
                payload = body["payload"]
                if event == "stage_b_entry_passed":
                    entry_passed = True
                    entry_event_sha256 = digest
                elif event == "stage_b_volume_expanded":
                    if not entry_passed or payload.get("entry_event_sha256") != entry_event_sha256:
                        raise PermissionError("GT release lacks its Stage B volume transition")
                    volume_expanded = True
                elif event == "call_finished" and payload.get("outcome") == "succeeded":
                    completed_calls.add((payload["kind"], payload["role_id"], payload["attempt"]))
                elif event == "prediction_frozen":
                    if (
                        ("verifier_predict", payload["role_id"], payload["predict_attempt"]) not in completed_calls
                        or ("decoder", payload["role_id"], payload["decoder_attempt"]) not in completed_calls
                    ):
                        raise PermissionError("frozen prediction lacks completed predict/decoder calls")
                    prediction_events[digest] = payload
                elif event == "gt_phase_released" and digest == release_event_sha256:
                    expected_predictions = (
                        set() if scope.prediction_receipt is None
                        else {item.ledger_event_sha256 for item in scope.prediction_receipt.predictions}
                    )
                    if (
                        not entry_passed
                        or not volume_expanded
                        or payload["scope_sha256"] != expected_scope
                        or payload["stage"] != scope.stage.value
                        or payload["outer_id"] != scope.outer_id
                        or payload["role_ids"] != list(scope.role_ids)
                        or set(payload["prediction_event_sha256"]) != expected_predictions
                        or len(payload["prediction_event_sha256"]) != len(expected_predictions)
                        or not expected_predictions <= prediction_events.keys()
                    ):
                        raise PermissionError("GT release lacks the frozen phase barrier")
                    release_found = True
                elif event == "gt_phase_view_revoked" and payload.get("release_event_sha256") == release_event_sha256:
                    release_revoked = True
        if not release_found or release_revoked:
            raise PermissionError("GT release is absent or already revoked")
        if scope.prediction_receipt is not None:
            for item in scope.prediction_receipt.predictions:
                expected_payload = asdict(item)
                expected_payload.pop("ledger_event_sha256")
                if prediction_events.get(item.ledger_event_sha256) != expected_payload:
                    raise PermissionError("frozen prediction receipt differs from the durable ledger")
                exact_path = self._study_output(Path(item.prediction_path))
                if self._hash_file(exact_path) != item.prediction_sha256.lower():
                    raise PermissionError("frozen prediction changed after GT release")

    def terminal(
        self,
        status: str,
        *,
        evidence: dict[str, object],
        invocation_started_monotonic_ns: int,
    ) -> str:
        """Persist one terminal event; any missing event after a crash is incomplete."""

        if status not in {item.value for item in StudyStatus}:
            raise ValueError("unknown Route 2 terminal status")
        if self._active_gt_release is not None:
            raise RuntimeError("active GT view must have an OS-confirmed revoke before terminal")
        if any(state in {"reserved", "started"} for _, state in self._call_state.values()):
            if status != "INCOMPLETE_RESOURCE":
                raise RuntimeError("unfinished call attempts require INCOMPLETE_RESOURCE")
        if status == StudyStatus.COMPLETE.value:
            if (
                not self._stage_a_finished
                or not self._stage_b_complete
                or len(self._reference_passed) != 105
                or len(self._treatment_roles) != 105
                or any(self._call_counts[kind] != ceiling for kind, ceiling in CALL_CEILINGS.items())
                or any(state != "succeeded" for _, state in self._call_state.values())
            ):
                raise RuntimeError("COMPLETE requires all paired roles and frozen call ceilings")
        if type(invocation_started_monotonic_ns) is not int or invocation_started_monotonic_ns <= 0:
            raise ValueError("terminal event requires the frozen invocation monotonic start")
        terminal_monotonic_ns = time.monotonic_ns()
        if terminal_monotonic_ns < invocation_started_monotonic_ns:
            raise RuntimeError("terminal monotonic time precedes invocation start")
        digest = self.append(
            "terminal",
            {
                "status": status,
                "evidence": evidence,
                "wall_ns": terminal_monotonic_ns - invocation_started_monotonic_ns,
                "monotonic_ns": terminal_monotonic_ns,
                "epoch_ns": time.time_ns(),
            },
        )
        self._terminal = True
        self._terminal_sha256 = digest
        return digest

    def close(self) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("ledger close must use the owner thread")
        if self._fd is not None:
            state = _LEDGER_CLOSE_STATES.get(self)
            if (state is None or state.attempted or self._fd != state.descriptor
                    or state.pid != os.getpid() or state.thread_id != threading.get_ident()):
                self._poisoned = True
                raise PermissionError("ledger close lost its original private writer ownership")
            descriptor = state.descriptor
            state.attempted = True
            # Consume FD ownership before either syscall. A failed close may
            # already have released and reused the descriptor number.
            self._fd = None
            try:
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino) != state.identity:
                    raise PermissionError("original close descriptor now refers to a different file")
            except BaseException:
                self._poisoned = True
                raise
            failure = None
            try:
                os.fsync(descriptor)
            except BaseException as error:
                failure = error
            try:
                os.close(descriptor)
            except BaseException as error:
                failure = failure or error
            if failure is not None:
                self._poisoned = True
                raise failure
            self._closed_at_monotonic_ns = time.monotonic_ns()
            state.closed_ns = self._closed_at_monotonic_ns
            state.succeeded = True

    @property
    def terminal_sha256(self) -> str:
        if self._fd is not None or not self._terminal_sha256:
            raise RuntimeError("terminal hash is unavailable before ledger close")
        return self._terminal_sha256

    @property
    def closed_at_monotonic_ns(self) -> int:
        if self._fd is not None or self._closed_at_monotonic_ns is None:
            raise RuntimeError("terminal close time is unavailable before ledger close")
        return self._closed_at_monotonic_ns


class BudgetGuard:
    def __init__(
        self,
        limits: BudgetLimits,
        ledger: AppendOnlyLedger,
        enforcer: ResourceEnforcer,
        study_root: Path,
        *,
        approved_controller_sha256: str,
        approved_write_volumes: tuple[str, ...],
        invocation_started_monotonic_ns: int,
        invocation_id: str,
    ):
        if enforcer is None:
            raise RuntimeError("no independent OS-level resource enforcer is installed")
        if ledger.study_root != study_root:
            raise ValueError("resource guard and budget ledger must bind the same exact study root")
        if (
            len(approved_controller_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in approved_controller_sha256.lower())
            or len(approved_write_volumes) != 1
            or not isinstance(invocation_id, str)
            or not invocation_id
        ):
            raise PermissionError("the reviewed controller and covered volumes must be frozen")
        self.limits = limits
        self.ledger = ledger
        self.enforcer = enforcer
        self.study_root = study_root
        self.approved_controller_sha256 = approved_controller_sha256.lower()
        self.approved_write_volumes = tuple(approved_write_volumes)
        self.invocation_id = invocation_id
        # Conservatively count all preflight work after guard construction.
        if (
            type(invocation_started_monotonic_ns) is not int
            or invocation_started_monotonic_ns <= 0
            or invocation_started_monotonic_ns > time.monotonic_ns()
        ):
            raise ValueError("outer invocation clock must start before guard construction")
        self._invocation_started_ns: int | None = invocation_started_monotonic_ns
        self._start_entered = False
        self._stage_a_finished_ns: int | None = None
        self._fit_wall_ns = 0
        self._rss_ceiling_bytes: int | None = None
        self._started = False
        self._activity_open = False
        self._finished = False
        self._stage_a_snapshot: ResourceSnapshot | None = None
        self._stage_b_admitted = False
        self._volume_identity_snapshot: ResourceSnapshot | None = None
        self._stage_a_event_receipt: DurableEventReceipt | None = None
        self._stage_b_entry_event_receipt: DurableEventReceipt | None = None
        self._stage_b_expansion_event_receipt: DurableEventReceipt | None = None
        self._stage_b_completion_event_receipt: DurableEventReceipt | None = None
        self._stage_b_result_evidence: dict[str, object] | None = None
        self._boundary_failure: str | None = None
        self._startup_receipt: EnforcementReceipt | None = None
        self._startup_snapshot: ResourceSnapshot | None = None
        self._lifecycle_supervisor = None
        self._volume_prepare_entered = False
        self._startup_failure: str | None = None
        self._startup_close_failure: str | None = None
        self._startup_phase = "approval"

    def start(self, approval: ExperimentApproval) -> None:
        """Count from entry, verify the OS controller, then create the study once."""

        if type(approval) is not ExperimentApproval:
            raise PermissionError("budget start requires an exact ExperimentApproval")
        if self._start_entered:
            raise RuntimeError("startup measurement may occur only once")
        self._start_entered = True
        from .startup_ownership import registered_startup, require_startup_binding
        binding = registered_startup(self)
        owner = binding.owner() if binding is not None else None
        original_ledger = binding.ledger if binding is not None else self.ledger
        try:
            require_startup_binding(self, approval)
            self._start_once(approval)
        except BaseException as original_error:
            self._start_entered = True
            self._startup_failure = type(original_error).__name__
            self._started = False
            self._finished = True
            # No terminal can be invented for an incomplete startup. Preserve
            # occupied objects and close the writer even when a flush fails.
            close_error = None
            if type(original_ledger) is AppendOnlyLedger:
                original_ledger._poisoned = True
                if original_ledger._fd is not None:
                    try:
                        _discard_owned_ledger_writer(original_ledger)
                    except BaseException as error:
                        close_error = error
                        self._startup_close_failure = type(error).__name__
            # A failed close must never bypass external detach/quarantine.
            abort_error = None
            if owner is not None:
                try:
                    owner.fail_budget_start(self, self._startup_phase, original_error)
                except BaseException as error:
                    abort_error = error
            if close_error is not None or abort_error is not None:
                error = PermissionError("startup failed; original, writer-close and abort errors retained")
                error.primary_error = original_error
                error.writer_close_error = close_error
                error.abort_error = abort_error
                error.secondary_errors = tuple(item for item in (close_error, abort_error) if item is not None)
                raise error from original_error
            raise

    def _start_once(self, approval: ExperimentApproval) -> None:
        from .startup_ownership import require_startup_binding, mark_volume_preparing
        approval.require_full_ab()
        if (
            approval.resource_controller_sha256.lower() != self.approved_controller_sha256
            or tuple(approval.approved_write_volumes) != self.approved_write_volumes
        ):
            raise PermissionError("controller and write-volume coverage differ from the frozen A+B approval")
        self.ledger._require_exact_paths()
        if (
            str(self.study_root) != approval.study_root_path
            or str(self.ledger.path) != approval.budget_ledger_path
            or str(self.ledger.lock_path) != approval.lock_path
        ):
            raise PermissionError("resource guard paths differ from the frozen A+B approval")
        # Reject occupied IDs before asking the controller to create an image.
        # lstat also detects dangling links; post-prepare O_EXCL remains the
        # authoritative atomic gate in the protected mounted namespace.
        for path in (self.study_root, self.ledger.path, self.ledger.lock_path):
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            raise FileExistsError("study output, ledger, or lock is already occupied")
        self._startup_phase = "prepare_volume"
        require_startup_binding(self, approval)
        mark_volume_preparing(self)
        self._volume_prepare_entered = True
        receipt, snapshot = self.enforcer.prepare_volume(
            self.study_root, self.ledger.path, self.ledger.lock_path, self.limits,
            self._invocation_started_ns or 0,
        )
        require_startup_binding(self, approval)
        if type(receipt) is not EnforcementReceipt or type(snapshot) is not ResourceSnapshot:
            raise PermissionError("startup requires exact enforcement and resource snapshot records")
        receipt.require_complete()
        require_precreate_order(
            self._invocation_started_ns or 0,
            receipt.precreate_free_checked_monotonic_ns,
            receipt.image_created_monotonic_ns,
            receipt.precreate_guest_free_bytes,
            receipt.precreate_windows_volume_free_bytes,
            self.limits.startup_free_disk_bytes,
        )
        if receipt.controller_sha256.lower() != self.approved_controller_sha256:
            raise PermissionError("OS controller implementation differs from the approved digest")
        if receipt.invocation_started_monotonic_ns != self._invocation_started_ns:
            raise PermissionError("OS controller receipt differs from the outer invocation clock")
        if (
            receipt.study_root != str(self.study_root)
            or receipt.study_image_path != approval.study_image_path
            or receipt.ledger_path != str(self.ledger.path)
            or receipt.lock_path != str(self.ledger.lock_path)
            or tuple(receipt.covered_write_volumes) != self.approved_write_volumes
        ):
            raise PermissionError("OS controller receipt does not cover the exact approved paths/volumes")
        study_volume = str(self.study_root.parent.resolve(strict=True))
        if study_volume not in self.approved_write_volumes:
            raise PermissionError("study output volume is absent from OS controller coverage")
        # The receipt is a capability claim, not independent proof.  Its provider
        # must be reviewed and bound to the separate human approval record.
        # The >=8 GiB floor belongs to the actual pre-image receipt, checked
        # above. A current post-allocation snapshot may legitimately have less
        # free space after paying for the initial image. Never impose a second
        # unapproved post-create floor or relabel old balances as current.
        if not all((snapshot.guest_backing_mount_id, snapshot.guest_backing_device,
                    snapshot.windows_vhdx_path, snapshot.windows_volume_id)):
            raise PermissionError("current backing identity is incomplete after pre-image free checking")
        if (
            snapshot.guest_backing_mount_id != receipt.guest_backing_mount_id
            or snapshot.windows_volume_id != receipt.windows_volume_id
            or snapshot.study_fs_capacity_bytes > self.limits.stage_a_disk_bytes
            or receipt.stage_a_capacity_bytes > self.limits.stage_a_disk_bytes
            or receipt.total_capacity_bytes > self.limits.total_disk_bytes
            or not snapshot.study_mount_id
            or not snapshot.study_device
            or snapshot.study_fs_uuid != receipt.study_fs_uuid
            or snapshot.study_loop_device != receipt.study_loop_device
            or snapshot.study_image_path != receipt.study_image_path
            or snapshot.study_image_dev != receipt.study_image_dev
            or snapshot.study_image_inode != receipt.study_image_inode
            or snapshot.study_image_length_bytes != receipt.study_image_length_bytes
        ):
            raise PermissionError("backing identity or Stage A filesystem hard limit differs from approval")
        if receipt.precreate_nested_backing is not None or snapshot.nested_backing is not None:
            before = nested_backing_identity(receipt.precreate_nested_backing,
                windows_vhdx_path=snapshot.windows_vhdx_path,windows_volume_id=receipt.windows_volume_id,
                windows_free_bytes=receipt.precreate_windows_volume_free_bytes)
            after = nested_backing_identity(snapshot.nested_backing,
                windows_vhdx_path=snapshot.windows_vhdx_path,windows_volume_id=snapshot.windows_volume_id,
                windows_free_bytes=snapshot.windows_volume_free_bytes)
            if before != after:
                raise PermissionError("precreate nested backing differs from the original current topology")
            if (receipt.precreate_nested_backing.carrier_free_bytes
                    < receipt.precreate_nested_backing.carrier_min_free_bytes):
                raise RuntimeError("precreate carrier growth/cleanup reserve is not met")
        require_stage_filesystem(snapshot, snapshot, self.limits.stage_a_disk_bytes)
        self._volume_identity_snapshot = snapshot
        if snapshot.available_ram_bytes <= 0:
            raise RuntimeError("startup available-RAM sample is invalid")
        self._rss_ceiling_bytes = min(
            self.limits.rss_cap_bytes,
            (3 * snapshot.available_ram_bytes) // 5,
        )
        if (
            receipt.pids_max > self.limits.worker_limit
            or receipt.pids_max < 1
            or receipt.rlimit_as_per_process_bytes < 1
            or receipt.rlimit_as_per_process_bytes * receipt.pids_max > self._rss_ceiling_bytes
            or receipt.memory_max_bytes > self._rss_ceiling_bytes
            or receipt.memory_swap_max_bytes != 0
        ):
            raise PermissionError("reviewed RSS/task hard limits do not imply the frozen study ceiling")
        if snapshot.process_tree_rss_bytes > self._rss_ceiling_bytes:
            raise RuntimeError("startup process-tree RSS already exceeds the frozen ceiling")
        if snapshot.compute_workers > self.limits.worker_limit:
            raise RuntimeError("worker ceiling is already exceeded")
        if snapshot.study_disk_peak_bytes > self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage A disk ceiling is already exceeded at startup")
        self._startup_phase = "ledger_create"
        self.ledger.create(approval, self.limits)
        self.ledger.append(
            "invocation_started",
            {
                "invocation_id": self.invocation_id,
                "monotonic_ns": self._invocation_started_ns,
                "controller_receipt": asdict(receipt),
                "startup_snapshot": asdict(snapshot),
                "frozen_rss_ceiling_bytes": self._rss_ceiling_bytes,
            },
        )
        self._started = True
        require_startup_binding(self, approval)
        self._check(self.enforcer.current_snapshot(self.study_root))
        require_startup_binding(self, approval)
        self._startup_receipt = receipt
        self._startup_snapshot = snapshot
        if self._lifecycle_supervisor is not None:
            self._startup_phase = "startup_observation"
            self._lifecycle_supervisor.observe_budget_start(self)

    def _elapsed_ns(self) -> int:
        if self._invocation_started_ns is None:
            raise RuntimeError("study invocation has not started")
        return time.monotonic_ns() - self._invocation_started_ns

    def _remaining(self, ceiling: int, spent: int, kind: str) -> int:
        remaining = ceiling - spent
        if remaining <= 0:
            raise RuntimeError(f"{kind} hard line is exhausted")
        return remaining

    @contextmanager
    def activity(self, name: str, *, stage_a: bool = False, fit: bool = False) -> Iterator[None]:
        if not self._started or self._finished:
            raise RuntimeError("budget guard must be started before activity")
        self._observe_owned_phase(work=(stage_a, fit))
        if self._boundary_failure is not None:
            raise PermissionError("activity is forbidden after a durable stage boundary failure")
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("activity is forbidden after the Stage B completion receipt")
        if self._activity_open:
            raise RuntimeError("nested activities can hide fit or stage wall consumption")
        if stage_a != (self._stage_a_finished_ns is None):
            raise RuntimeError("activity stage does not match the persisted Stage A boundary")
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling is not frozen")
        elapsed = self._elapsed_ns()
        remaining_total = self._remaining(self.limits.total_wall_ns, elapsed, "total wall")
        remaining_stage = (
            self._remaining(self.limits.stage_a_wall_ns, elapsed, "Stage A wall")
            if stage_a else None
        )
        remaining_fit = (
            self._remaining(self.limits.fit_wall_ns, self._fit_wall_ns, "fit wall")
            if fit else None
        )
        handle = self.enforcer.enforce_during_activity(
            self.study_root,
            self.limits,
            name,
            remaining_total_wall_ns=remaining_total,
            remaining_stage_a_wall_ns=remaining_stage,
            remaining_fit_wall_ns=remaining_fit,
            frozen_rss_ceiling_bytes=self._rss_ceiling_bytes,
        )
        self._activity_open = True
        started_ns = time.monotonic_ns()
        try:
            self.ledger.append("activity_started", {"name": name, "monotonic_ns": started_ns, "fit": fit, "stage_a": stage_a})
        except BaseException:
            self._activity_open = False
            self.enforcer.stop_activity(handle)
            raise
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            ended_ns = time.monotonic_ns()
            try:
                snapshot = self.enforcer.stop_activity(handle)
            finally:
                self._activity_open = False
            if fit:
                self._fit_wall_ns += time.monotonic_ns() - started_ns
            self.ledger.append(
                "activity_finished",
                {
                    "name": name,
                    "monotonic_ns": ended_ns,
                    "elapsed_ns": time.monotonic_ns() - started_ns,
                    "invocation_wall_ns": self._elapsed_ns(),
                    "fit_wall_ns": self._fit_wall_ns,
                    "failed": failed,
                    "snapshot": asdict(snapshot),
                },
            )
            self._check(snapshot)

    def invoke_call(self, kind: str, role_id: str, operation: Callable[[], T]) -> tuple[int, T]:
        """Reserve, invoke exactly once, and persist the actual call outcome."""

        self._observe_owned_phase(work=(False, kind == "verifier_fit"))
        if self._boundary_failure is not None:
            raise PermissionError("calls are forbidden after a durable stage boundary failure")
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("calls are forbidden after the Stage B completion receipt")
        if not self._stage_b_admitted:
            raise PermissionError("no verifier, decoder, or evaluator call before Stage B admission")
        attempt = self.ledger.reserve_call(kind, role_id)
        self.ledger.start_call(kind, role_id, attempt)
        try:
            with self.activity(
                f"{kind}:{role_id}:{attempt}",
                stage_a=False,
                fit=(kind == "verifier_fit"),
            ):
                result = operation()
        except BaseException:
            self.ledger.finish_call(kind, role_id, attempt, succeeded=False)
            raise
        self.ledger.finish_call(kind, role_id, attempt, succeeded=True)
        return attempt, result

    def _observe_owned_phase(self, method: str | None = None, *args: object,
                             work: tuple[bool, bool] | None = None) -> None:
        """Use only the registered original lifecycle owner at phase boundaries."""
        from .startup_ownership import registered_startup, require_startup_binding
        binding = registered_startup(self)
        try:
            require_startup_binding(self)
            if binding is not None:
                if work is None:
                    from .phase_observation import require_phase_role_graph
                    require_phase_role_graph(self)
                else:
                    from .phase_observation import require_owned_work
                    require_owned_work(self, stage_a=work[0], fit=work[1])
            if binding is not None and method is not None:
                getattr(binding.owner(), method)(self, *args)
        except BaseException as error:
            self._boundary_failure = f"owned phase observation failed: {type(error).__name__}"
            if binding is not None and binding.owner() is not None:
                binding.owner().fail_budget_phase(self, error)
            raise

    def finish_stage_a(self) -> ResourceSnapshot:
        if self._boundary_failure is not None:
            raise PermissionError("Stage A boundary is forbidden after a durable boundary failure")
        self._observe_owned_phase()
        if not self._started or self._stage_a_finished_ns is not None or self._activity_open:
            raise RuntimeError("Stage A may finish only once with no open activity")
        if (
            len(self.ledger._reference_passed) != 105
            or len(self.ledger._treatment_roles) != 105
            or set(self.ledger._treatment_finished) != self.ledger._treatment_roles
        ):
            raise RuntimeError("Stage A boundary requires 105 passed references and 105 frozen treatments")
        snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(snapshot)
        final_snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(final_snapshot)
        finished_ns = time.monotonic_ns()
        if not self.ledger._different_treatment_roles.issubset(self.ledger._treatment_roles):
            raise PermissionError("Stage A difference count is not bound to treatment roles")
        self._stage_a_event_receipt = self.ledger.mark_stage_a_finished({
            "invocation_id": self.invocation_id,
            "reference_roles": len(self.ledger._reference_passed),
            "treatment_roles": len(self.ledger._treatment_finished),
            "different_treatment_roles": len(self.ledger._different_treatment_roles),
            "stage_a_disk_bytes": stage_a_projection_disk_bytes(final_snapshot, self.limits),
            "finished_monotonic_ns": finished_ns,
        })
        self._stage_a_finished_ns = self._stage_a_event_receipt.fsynced_monotonic_ns
        self._stage_a_snapshot = final_snapshot
        if (
            self._invocation_started_ns is None
            or finished_ns > self._invocation_started_ns + self.limits.stage_a_wall_ns
            or self._stage_a_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.stage_a_wall_ns
        ):
            self._boundary_failure = "Stage A boundary append/fsync exceeded the Stage A wall deadline"
            raise RuntimeError(self._boundary_failure)
        self._observe_owned_phase("observe_budget_stage_a")
        return final_snapshot

    def require_stage_b_entry(
        self,
        projection: StageBProjection,
    ) -> None:
        require_exact_stage_b_projection(projection)
        projection.call_role_ids_by_kind()
        if self._boundary_failure is not None:
            raise PermissionError("Stage B entry is forbidden after a durable stage boundary failure")
        self._observe_owned_phase()
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("Stage B entry is forbidden after the Stage B completion receipt")
        if not self._started or self._stage_a_snapshot is None or self._finished or self._stage_b_admitted:
            raise RuntimeError("Stage B projection requires persisted, complete Stage A")
        if projection.stage_a_disk_bytes_d_a != stage_a_projection_disk_bytes(self._stage_a_snapshot, self.limits):
            raise RuntimeError("D_A differs from the frozen Stage A accounting protocol")
        if (
            self._stage_a_event_receipt is None
            or self._invocation_started_ns is None
            or self._stage_a_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.stage_a_wall_ns
        ):
            raise RuntimeError("Stage B entry requires an on-time durable Stage A boundary")
        self._check(self.enforcer.current_snapshot(self.study_root))
        require_stage_b_entry(
            projection,
            limits=self.limits,
            frozen_rss_ceiling_bytes=self.frozen_rss_ceiling_bytes,
            stage_a_hard_lines_met=True,
        )
        self._stage_b_entry_event_receipt = self.ledger.mark_stage_b_entry(
            asdict(projection), invocation_id=self.invocation_id,
        )
        stage_a_deadline = self._invocation_started_ns + self.limits.stage_a_wall_ns
        if (
            self._stage_b_entry_event_receipt.fsynced_monotonic_ns
            < self._stage_a_event_receipt.fsynced_monotonic_ns
            or self._stage_b_entry_event_receipt.fsynced_monotonic_ns > stage_a_deadline
        ):
            self._boundary_failure = "Stage B entry append/fsync exceeded the Stage A wall deadline"
            raise RuntimeError(self._boundary_failure)
        entry_hash = self._stage_b_entry_event_receipt.event_sha256
        self._observe_owned_phase("observe_budget_stage_b_entry", projection)
        expanded = self.enforcer.expand_after_stage_b_entry(
            self.study_root, self.limits, entry_hash,
        )
        if self._volume_identity_snapshot is None:
            raise RuntimeError("study volume identity was not frozen before expansion")
        require_stage_filesystem(
            expanded, self._volume_identity_snapshot,
            self.limits.total_disk_bytes,
        )
        if expanded.study_fs_capacity_bytes <= self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage B filesystem did not expand after its entry gate")
        volume = {
            "invocation_id": self.invocation_id,
            "study_id": STUDY_ID,
            "study_root_path": str(self.study_root),
            "ledger_path": str(self.ledger.path),
            "lock_path": str(self.ledger.lock_path),
            "image_path": expanded.study_image_path,
            "created_monotonic_ns": time.monotonic_ns(),
            "image_device": expanded.study_image_dev,
            "image_inode": expanded.study_image_inode,
            "loop_device": expanded.study_loop_device,
            "filesystem_uuid": expanded.study_fs_uuid,
            "mount_id": expanded.study_mount_id,
            "filesystem_device": expanded.study_device,
            "filesystem_capacity_bytes": expanded.study_fs_capacity_bytes,
            "image_length_bytes": expanded.study_image_length_bytes,
        }
        self._stage_b_expansion_event_receipt = self.ledger.mark_stage_b_volume_expanded(
            entry_hash, volume, invocation_id=self.invocation_id,
        )
        created_ns = volume["created_monotonic_ns"]
        entry_fsynced_ns = self._stage_b_entry_event_receipt.fsynced_monotonic_ns
        expansion_fsynced_ns = self._stage_b_expansion_event_receipt.fsynced_monotonic_ns
        total_deadline = self._invocation_started_ns + self.limits.total_wall_ns
        if (
            type(created_ns) is not int
            or type(entry_fsynced_ns) is not int
            or type(expansion_fsynced_ns) is not int
            or created_ns < entry_fsynced_ns
            or expansion_fsynced_ns < created_ns
            or expansion_fsynced_ns > total_deadline
        ):
            self._boundary_failure = "Stage B expansion append/fsync is outside its durable wall boundary"
            raise RuntimeError(self._boundary_failure)
        self._observe_owned_phase("observe_budget_expansion")
        self._stage_b_admitted = True
        self._check(expanded)

    def finish_stage_b(self, result: object) -> None:
        """Persist the unique COMPLETE payload after the fixed Stage B protocol succeeds."""

        from .stage_b import FitSummary, StageBResult

        if (
            not self._started or not self._stage_b_admitted or self._finished
            or self._activity_open or self._stage_b_completion_event_receipt is not None
        ):
            raise RuntimeError("Stage B completion requires one admitted, inactive invocation")
        if self._boundary_failure is not None:
            raise PermissionError("Stage B completion is forbidden after a durable stage boundary failure")
        self._observe_owned_phase()
        if type(result) is not StageBResult or result.status is not StudyStatus.COMPLETE:
            raise ValueError("Stage B completion requires the exact successful result type")
        call_event_accounting = self.ledger._verified_call_event_accounting()
        role_ids_by_kind = call_event_accounting.pop("role_ids_by_kind")
        fit_role_ids = role_ids_by_kind["verifier_fit"]
        if (
            type(result.fit_provenance) is not tuple
            or len(result.fit_provenance) != CALL_CEILINGS["verifier_fit"]
            or any(type(item) is not FitSummary for item in result.fit_provenance)
            or tuple(item.verifier_role_id for item in result.fit_provenance) != fit_role_ids
            or tuple(item.fit_attempt for item in result.fit_provenance)
            != tuple(range(1, CALL_CEILINGS["verifier_fit"] + 1))
        ):
            raise PermissionError("Stage B fit provenance does not match the replayed five-by-four role schedule")
        if _canonical([asdict(item) for item in result.fit_provenance]) != _canonical(
            call_event_accounting["fit_provenance"]
        ):
            raise PermissionError("Stage B fit provenance differs from the 25 durable verifier fit events")
        for summary in result.fit_provenance:
            model_path = self.ledger._study_output(Path(summary.model_path))
            if (
                model_path.parent.name != "verifier-models"
                or model_path.name != hashlib.sha256(summary.verifier_role_id.encode("utf-8")).hexdigest() + ".pickle"
                or self.ledger._hash_file(model_path) != summary.model_sha256
            ):
                raise PermissionError("Stage B fit provenance model path or content hash differs from its persisted model")
        snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(snapshot)
        integer_fields = (
            result.pooled_gt_count,
            result.verifier_fit_attempts,
            result.verifier_prediction_batches,
            result.decoder_calls,
            result.evaluator_calls,
            result.pooled_aggregation_calls,
            result.pooled_gt_reads,
        )
        if (
            len(result.selected_thresholds) != 5
            or len(result.fold_metrics) != 5
            or len(result.outer_candidate_counts) != 5
            or len(result.outer_candidate_covered_gt) != 5
            or len(result.outer_reference_candidate_covered_gt) != 5
            or len(result.outer_candidate_added_gt_commitments) != 5
            or len(result.outer_candidate_lost_gt_commitments) != 5
            or any(type(value) is not int for value in integer_fields)
            or result.pooled_gt_count != 234
            or result.verifier_fit_attempts != 25
            or result.verifier_prediction_batches != 25
            or result.decoder_calls != 65
            or result.evaluator_calls != 20
            or result.pooled_aggregation_calls != 1
            or result.pooled_aggregation_completed is not True
            or result.pooled_gt_reads != 0
        ):
            raise PermissionError("Stage B result differs from the fixed role, call, or pooled no-GT protocol")
        outer_ids = tuple(outer_id for outer_id, _ in result.selected_thresholds)
        frozen_outer_ids = tuple(
            role_id.split("/")[1]
            for role_id in role_ids_by_kind["verifier_predict"]
            if len(role_id.split("/")) == 3 and role_id.endswith("/outer")
        )
        if (
            outer_ids != frozen_outer_ids
            or tuple(outer_id for outer_id, _ in result.outer_candidate_counts) != outer_ids
            or tuple(outer_id for outer_id, _ in result.outer_candidate_covered_gt) != outer_ids
            or tuple(outer_id for outer_id, _ in result.outer_reference_candidate_covered_gt) != outer_ids
            or tuple(outer_id for outer_id, _ in result.outer_candidate_added_gt_commitments) != outer_ids
            or tuple(outer_id for outer_id, _ in result.outer_candidate_lost_gt_commitments) != outer_ids
        ):
            raise PermissionError("Stage B matched-GT diagnostics do not cover the five exact outer folds")
        seen_commitments: set[str] = set()
        for (_, covered), (_, reference_covered), (_, additions), (_, losses) in zip(
            result.outer_candidate_covered_gt,
            result.outer_reference_candidate_covered_gt,
            result.outer_candidate_added_gt_commitments,
            result.outer_candidate_lost_gt_commitments,
            strict=True,
        ):
            if (
                type(covered) is not int or type(reference_covered) is not int
                or type(additions) is not tuple or type(losses) is not tuple
                or tuple(sorted(set(additions))) != additions
                or tuple(sorted(set(losses))) != losses
                or set(additions) & set(losses)
                or covered - reference_covered != len(additions) - len(losses)
                or any(
                    type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in (*additions, *losses)
                )
                or seen_commitments & (set(additions) | set(losses))
            ):
                raise PermissionError("Stage B matched-GT additions or losses are inconsistent")
            seen_commitments.update((*additions, *losses))
        result_sha256 = hashlib.sha256(_canonical(asdict(result))).hexdigest()
        finished_ns = time.monotonic_ns()
        if (
            self._invocation_started_ns is None
            or finished_ns > self._invocation_started_ns + self.limits.total_wall_ns
        ):
            raise RuntimeError("Stage B computation exceeded the total active-wall deadline")
        payload = {
            "invocation_id": self.invocation_id,
            # Five outer decisions each complete four nested inner roles.
            # selected_thresholds has one item per outer fold, not one per
            # inner held-out role.
            "inner_roles_completed": 20,
            "outer_roles_completed": len(result.fold_metrics),
            "verifier_fit_calls": result.verifier_fit_attempts,
            "verifier_predict_calls": result.verifier_prediction_batches,
            "decoder_calls": result.decoder_calls,
            "evaluator_calls": result.evaluator_calls,
            "pooled_aggregation_calls": result.pooled_aggregation_calls,
            "pooled_aggregation_completed": result.pooled_aggregation_completed,
            "pooled_gt_reads": result.pooled_gt_reads,
            "call_event_count": call_event_accounting["call_event_count"],
            "call_event_accounting_sha256": call_event_accounting["call_event_accounting_sha256"],
            "finished_monotonic_ns": finished_ns,
            "result_sha256": result_sha256,
        }
        self._stage_b_result_evidence = asdict(result)
        self._stage_b_completion_event_receipt = self.ledger.mark_stage_b_complete(payload)
        if (
            self._stage_b_completion_event_receipt.fsynced_monotonic_ns < finished_ns
            or self._stage_b_completion_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.total_wall_ns
        ):
            self._boundary_failure = "Stage B completion append/fsync exceeded the total active-wall deadline"
            raise RuntimeError(self._boundary_failure)
        self._observe_owned_phase("observe_budget_stage_b_completion")

    def _check(self, snapshot: ResourceSnapshot) -> None:
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling was not frozen at startup")
        if self._volume_identity_snapshot is None:
            raise RuntimeError("study volume identity was not frozen at startup")
        require_stage_filesystem(
            snapshot, self._volume_identity_snapshot,
            self.limits.total_disk_bytes if self._stage_b_admitted else self.limits.stage_a_disk_bytes,
        )
        if snapshot.process_tree_rss_bytes > self._rss_ceiling_bytes:
            raise RuntimeError("process-tree RSS hard line exceeded")
        if snapshot.study_disk_peak_bytes > self.limits.total_disk_bytes:
            raise RuntimeError("study disk hard line exceeded")
        if self._stage_a_finished_ns is None and snapshot.study_disk_peak_bytes > self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage A disk hard line exceeded")
        if snapshot.compute_workers > self.limits.worker_limit:
            raise RuntimeError("compute worker hard line exceeded")
        if self._elapsed_ns() > self.limits.total_wall_ns:
            raise RuntimeError("total active-wall hard line exceeded")
        if self._stage_a_finished_ns is None and self._elapsed_ns() > self.limits.stage_a_wall_ns:
            raise RuntimeError("Stage A active-wall hard line exceeded")
        if self._fit_wall_ns > self.limits.fit_wall_ns:
            raise RuntimeError("fit active-wall hard line exceeded")

    def finalize(self, status: str, *, evidence: dict[str, object]) -> str:
        """Persist one terminal.  Missing/partial finalization is an incomplete run."""

        if not self._started or self._finished or self._activity_open:
            raise RuntimeError("study may finalize once after all activities close")
        from .startup_ownership import registered_startup, require_startup_binding
        original_binding = registered_startup(self)
        try:
            require_startup_binding(self)
            snapshot = self.enforcer.current_snapshot(self.study_root)
            try:
                self._check(snapshot)
            except BaseException as error:
                status = "INCOMPLETE_RESOURCE"
                evidence = {**evidence, "resource_error": repr(error)}
            if self._boundary_failure is not None:
                status = "INCOMPLETE_RESOURCE"
                evidence = {**evidence, "boundary_failure": self._boundary_failure}
            if self._stage_b_completion_event_receipt is not None:
                if self._stage_b_result_evidence is None:
                    raise RuntimeError("durable Stage B completion lacks its result evidence")
                existing_result = evidence.get("stage_b_result")
                if existing_result is not None and existing_result != self._stage_b_result_evidence:
                    raise PermissionError("terminal Stage B result differs from the durable completion result")
                evidence = {**evidence, "stage_b_result": self._stage_b_result_evidence}
            started = self._invocation_started_ns
            if started is None:
                raise RuntimeError("invocation monotonic start is absent at terminal close")
            if original_binding is not None:
                from .terminal_observation import prepare_owned_terminal
                evidence = {**evidence, **prepare_owned_terminal(self)}
            self.ledger.terminal(
                status,
                evidence={
                    **evidence,
                    "snapshot": asdict(snapshot),
                    "invocation_wall_ns": self._elapsed_ns(),
                    "fit_wall_ns": self._fit_wall_ns,
                    "stage_a_wall_ns": (
                        self._stage_a_finished_ns - self._invocation_started_ns
                        if self._stage_a_finished_ns is not None and self._invocation_started_ns is not None
                        else self._elapsed_ns()
                    ),
                },
                invocation_started_monotonic_ns=started,
            )
            self._finished = True
            if original_binding is not None:
                from .terminal_observation import before_owned_terminal_close
                before_owned_terminal_close(self)
            self.ledger.close()
            if original_binding is not None:
                from .terminal_observation import after_owned_terminal_close
                after_owned_terminal_close(self)
            return status
        except BaseException:
            if original_binding is not None:
                from .terminal_observation import fail_owned_terminal
                try:
                    fail_owned_terminal(self)
                except BaseException:
                    # Preserve the original failure; cleanup consumed its FD
                    # before close, so no descriptor number is retried.
                    pass
                original_ledger = original_binding.ledger
                original_ledger._poisoned = True
                try:
                    _discard_owned_ledger_writer(original_ledger)
                except BaseException:
                    pass
            raise

    @property
    def frozen_rss_ceiling_bytes(self) -> int:
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling is not frozen before startup")
        return self._rss_ceiling_bytes


@dataclass(frozen=True, slots=True)
class StageBProjection:
    candidate_rows_n: int
    maximum_fit_rows_m: int
    prediction_rows_s: int
    candidate_file_bytes_b: int
    stage_a_disk_bytes_d_a: int
    role_graph_sha256: str = ""
    outer_role_ids: tuple[str, ...] = ()
    inner_role_ids_by_outer: tuple[tuple[str, tuple[str, ...]], ...] = ()
    fit_training_roles_by_verifier: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.candidate_rows_n,
            self.maximum_fit_rows_m,
            self.prediction_rows_s,
            self.candidate_file_bytes_b,
            self.stage_a_disk_bytes_d_a,
        )
        if any(type(value) is not int for value in values):
            raise ValueError("Stage B projection values must be exact integers")
        if any(value < 0 for value in values):
            raise ValueError("Stage B projection values must be nonnegative")
        if self.role_graph_sha256 or self.outer_role_ids or self.inner_role_ids_by_outer or self.fit_training_roles_by_verifier:
            if (
                type(self.role_graph_sha256) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", self.role_graph_sha256)
                or type(self.outer_role_ids) is not tuple
                or type(self.inner_role_ids_by_outer) is not tuple
                or type(self.fit_training_roles_by_verifier) is not tuple
                or any(
                    type(item) is not tuple or len(item) != 2
                    or type(item[0]) is not str or type(item[1]) is not tuple
                    for item in self.inner_role_ids_by_outer
                )
                or any(
                    type(item) is not tuple or len(item) != 2
                    or type(item[0]) is not str or type(item[1]) is not tuple
                    for item in self.fit_training_roles_by_verifier
                )
            ):
                raise ValueError("Stage B role graph schedule has an invalid frozen identity")
            _call_role_ids_from_graph(
                self.outer_role_ids, self.inner_role_ids_by_outer,
                self.fit_training_roles_by_verifier,
            )

    def call_role_ids_by_kind(self) -> dict[str, tuple[str, ...]]:
        if not self.role_graph_sha256:
            raise PermissionError("Stage B projection has no frozen role graph identity")
        if not re.fullmatch(r"[0-9a-f]{64}", self.role_graph_sha256):
            raise PermissionError("Stage B projection has an invalid frozen role graph identity")
        return _call_role_ids_from_graph(
            self.outer_role_ids, self.inner_role_ids_by_outer,
            self.fit_training_roles_by_verifier,
        )


def require_stage_b_entry(
    projection: StageBProjection,
    *,
    limits: BudgetLimits,
    frozen_rss_ceiling_bytes: int,
    stage_a_hard_lines_met: bool,
) -> None:
    """Apply the predeclared Stage B formula without loading GT or fitting."""

    require_exact_stage_b_projection(projection)
    if type(frozen_rss_ceiling_bytes) is not int or frozen_rss_ceiling_bytes <= 0:
        raise ValueError("frozen RSS ceiling must be a positive exact integer")
    if type(stage_a_hard_lines_met) is not bool:
        raise ValueError("Stage A hard-line result must be an exact boolean")
    disk_projection = (
        projection.stage_a_disk_bytes_d_a
        + 3 * (
            projection.candidate_file_bytes_b
            + 232 * projection.candidate_rows_n
            + 8 * projection.prediction_rows_s
        )
        + limits.stage_b_disk_slack_bytes
    )
    rss_projection = (
        limits.stage_b_rss_slack_bytes
        + 6 * 232 * projection.maximum_fit_rows_m
    )
    if not stage_a_hard_lines_met:
        raise RuntimeError("Stage A hard-line evidence is missing")
    if disk_projection > limits.total_disk_bytes:
        raise RuntimeError("Stage B disk entry formula fails")
    if rss_projection > frozen_rss_ceiling_bytes:
        raise RuntimeError("Stage B RSS entry formula fails")


def require_exact_stage_b_projection(projection: StageBProjection) -> None:
    """Reject subclasses and mutated field values at every public admission boundary."""

    if type(projection) is not StageBProjection:
        raise ValueError("Stage B projection must use the exact reviewed type")
    values = (
        projection.candidate_rows_n,
        projection.maximum_fit_rows_m,
        projection.prediction_rows_s,
        projection.candidate_file_bytes_b,
        projection.stage_a_disk_bytes_d_a,
    )
    if any(type(value) is not int for value in values):
        raise ValueError("Stage B projection values must be exact integers")
    if any(value < 0 for value in values):
        raise ValueError("Stage B projection values must be nonnegative")
    if (
        type(projection.role_graph_sha256) is not str
        or type(projection.outer_role_ids) is not tuple
        or type(projection.inner_role_ids_by_outer) is not tuple
        or type(projection.fit_training_roles_by_verifier) is not tuple
    ):
        raise ValueError("Stage B frozen role graph fields must use exact immutable types")
    if (
        projection.role_graph_sha256 or projection.outer_role_ids
        or projection.inner_role_ids_by_outer or projection.fit_training_roles_by_verifier
    ):
        projection.call_role_ids_by_kind()
