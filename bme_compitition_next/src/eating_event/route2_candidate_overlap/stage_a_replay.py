"""Pure replay of the durable 105-reference/105-treatment Stage A journal.

The role tree comes from a complete canonical input registry pinned outside
the ledger; projection hash labels never define the approved topology.
This verifies metadata, not the candidate artifacts themselves. It
does not open candidate paths, recompute their file/interval hashes from bytes,
or establish their current FD/device/inode identity. Consistent forged metadata
from a compromised ledger writer cannot be detected by this pure replay alone.
The result is never an approval or an artifact-verification capability; live
artifact verification and controller admission remain separate requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, field
import hashlib
import json
from pathlib import PurePosixPath
import re

from .budget import (BudgetLimits, ResourceSnapshot, STAGE_A_CAPACITY_UPPER_BOUND_V2,
                     nested_backing_from_payload, require_nested_backing_sample, require_stage_filesystem,
                     stage_a_projection_disk_bytes, _canonical, _projection_call_role_ids)
from .candidates import CandidateFileReceipt
from .contracts import STUDY_ID, RoleSpec, RoleInputRegistration, RegisteredFile, CacheFileRegistration


MAX_STAGE_A_LEDGER_BYTES = 16 << 20
MAX_ROLE_REGISTRY_BYTES = 16 << 20
_HASH = re.compile(r"[0-9a-fA-F]{64}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_EMPTY_HASH = hashlib.sha256(b"").hexdigest()
_SCHEMAS = {
    "study_created": {"study_id", "approval_record", "input_registry_sha256", "budget_policy_sha256", "limits", "created_wall_ns"},
    "invocation_started": {"invocation_id", "monotonic_ns", "controller_receipt", "startup_snapshot", "frozen_rss_ceiling_bytes"},
    "stage_a_finished": {"invocation_id", "reference_roles", "treatment_roles", "different_treatment_roles", "stage_a_disk_bytes", "finished_monotonic_ns"},
    "stage_b_entry_passed": {"invocation_id", "projection"},
    "candidate_reconstruction_reserved": {"stage", "role_id", "attempt"},
    "reference_role_passed": {"role_id", "candidate_count", "interval_fingerprint"},
    "treatment_role_finished": {"role_id", "path", "sha256", "row_count", "file_bytes", "interval_fingerprint", "interval_set_same"},
    "activity_started": {"name", "monotonic_ns", "fit", "stage_a"},
    "activity_finished": {"name", "monotonic_ns", "elapsed_ns", "invocation_wall_ns", "fit_wall_ns", "failed", "snapshot"},
    "gt_broker_registered": {"manifest_sha256", "gt_registry_sha256", "protected_registry_sha256",
                             "view_count", "kernel", "worker_backing", "issued_worker_identities",
                             "invocation_id", "controller_run_id", "history_sha256"},
}


def _hash(value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise PermissionError("Stage A evidence has an invalid SHA-256")
    return value.lower()


def _integer(value: object, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PermissionError("Stage A counts and clock samples must be exact bounded integers")
    return value


def _text(value: object) -> str:
    if type(value) is not str or not value or any(ord(ch) < 32 for ch in value):
        raise PermissionError("Stage A evidence has an invalid text identity")
    return value


def _path(value: object) -> PurePosixPath:
    value = _text(value)
    parsed = PurePosixPath(value)
    if (not parsed.is_absolute() or parsed.as_posix() != value
            or ".." in parsed.parts or any(ch.isspace() for ch in value)):
        raise PermissionError("Stage A output path is not canonical absolute Linux text")
    return parsed


def _chain(encoded: bytes) -> tuple[dict, ...]:
    if (type(encoded) is not bytes or not encoded or len(encoded) > MAX_STAGE_A_LEDGER_BYTES
            or not encoded.endswith(b"\n")):
        raise PermissionError("Stage A journal is absent, incomplete or outside the byte bound")
    previous = "0" * 64
    entries = []
    try:
        for sequence, raw in enumerate(encoded.splitlines(keepends=True)):
            record = json.loads(raw)
            if (type(record) is not dict or set(record) != {"entry", "sha256"}
                    or _canonical(record) + b"\n" != raw):
                raise ValueError("noncanonical journal envelope")
            body = record["entry"]
            if (type(body) is not dict or set(body) != {"seq", "event", "payload", "previous_sha256"}
                    or type(body["seq"]) is not int or body["seq"] != sequence
                    or type(body["event"]) is not str or not body["event"]
                    or type(body["payload"]) is not dict or body["previous_sha256"] != previous
                    or record["sha256"] != hashlib.sha256(_canonical(body)).hexdigest()):
                raise ValueError("invalid journal sequence or event hash")
            entries.append({**body, "sha256": record["sha256"]})
            previous = record["sha256"]
    except (ValueError, TypeError, UnicodeError, KeyError, RecursionError) as exc:
        raise PermissionError("Stage A durable hash chain cannot be replayed") from exc
    return tuple(entries)


def _snapshot(value: object, *, rss: int, limits: BudgetLimits) -> ResourceSnapshot:
    if type(value) is not dict or set(value) != {item.name for item in fields(ResourceSnapshot)}:
        raise PermissionError("Stage A activity lacks the exact resource snapshot schema")
    try:
        normalized = dict(value)
        normalized["nested_backing"] = nested_backing_from_payload(value["nested_backing"])
        result = ResourceSnapshot(**normalized)
    except (TypeError, ValueError) as exc:
        raise PermissionError("Stage A activity has invalid resource observations") from exc
    if (result.process_tree_rss_bytes > rss or result.compute_workers > limits.worker_limit
            or result.study_disk_peak_bytes > limits.stage_a_disk_bytes
            or result.study_fs_capacity_bytes > limits.stage_a_disk_bytes
            or result.study_image_length_bytes > limits.stage_a_disk_bytes):
        raise PermissionError("Stage A activity resource sample exceeds the fixed phase bounds")
    stage_a_projection_disk_bytes(result, limits)
    if result.nested_backing is not None:
        require_nested_backing_sample(result.nested_backing, windows_vhdx_path=result.windows_vhdx_path,
            windows_volume_id=result.windows_volume_id, windows_free_bytes=result.windows_volume_free_bytes)
    return result


def _registry_object(value, cls):
    if type(value) is not dict or set(value) != {item.name for item in fields(cls)}:
        raise PermissionError("authenticated role registry has an incomplete or unknown object schema")
    return value


def _registry_strings(value, *, allow_empty=False):
    if type(value) is not list or (not value and not allow_empty):
        raise PermissionError("authenticated role registry requires exact text arrays")
    result = tuple(_text(item) for item in value)
    if len(result) != len(set(result)):
        raise PermissionError("authenticated role registry contains duplicate text identities")
    return result


def _registered_file(value):
    value = _registry_object(value, RegisteredFile)
    attestation, scope = value["projection_attestation"], value["scope_sha256"]
    if type(attestation) is not str or type(scope) is not str:
        raise PermissionError("authenticated registry projection bindings must be exact text")
    if attestation:
        _text(attestation)
    if scope:
        _hash(scope)
    return RegisteredFile(
        _text(value["path"]), _hash(value["sha256"]), _registry_strings(value["fields"]),
        _text(value["role_id"]), attestation, scope,
    )


def _authenticated_topology(encoded, *, expected_registry_sha256, expected_graph_sha256):
    """Derive topology exclusively from full bytes pinned outside the ledger.

    No registered input path is opened here. Hash/canonical schema checks and
    the existing registration contracts precede extraction of the role tree.
    """
    registry_hash = _hash(expected_registry_sha256)
    if (type(encoded) is not bytes or not 0 < len(encoded) <= MAX_ROLE_REGISTRY_BYTES
            or hashlib.sha256(encoded).hexdigest() != registry_hash):
        raise PermissionError("role registry bytes differ from their authenticated external SHA-256")
    try:
        rows = json.loads(encoded)
        if type(rows) is not list or len(rows) != 105 or _canonical(rows) != encoded:
            raise PermissionError("role registry must be an exact canonical list of 105 complete registrations")
        roles = []
        for row in rows:
            row = _registry_object(row, RoleInputRegistration)
            spec = _registry_object(row["role"], RoleSpec)
            if type(spec["kind"]) is not str or spec["kind"] not in {"outer", "inner_heldout", "inner_train"}:
                raise PermissionError("role registry contains an unknown role kind")
            role = RoleSpec(_text(spec["role_id"]), _text(spec["outer_id"]), spec["kind"],
                            _registry_strings(spec["fit_participants"]), _registry_strings(spec["scored_participants"]))
            if _hash(row["role_graph_sha256"]) != expected_graph_sha256:
                raise PermissionError("role registration graph SHA differs from the authenticated graph pin")
            if type(row["cache_files"]) is not list or not row["cache_files"]:
                raise PermissionError("role registration lacks its exact cache registrations")
            caches = []
            for item in row["cache_files"]:
                item = _registry_object(item, CacheFileRegistration)
                caches.append(CacheFileRegistration(
                    _text(item["participant_id"]), _text(item["record_id"]), _text(item["session_id"]),
                    _text(item["manifest_cache_path"]), _registered_file(item["cache_npz"])))
            if type(row["threshold_reference"]) not in (int, float):
                raise PermissionError("role registry threshold must be an exact finite number")
            RoleInputRegistration(
                role, row["role_graph_sha256"], _registered_file(row["score_npz"]),
                _registered_file(row["score_provenance"]), _text(row["manifest_score_path"]), tuple(caches),
                _registered_file(row["cache_manifest_view"]), _registered_file(row["identity_view"]),
                _registered_file(row["quality_attestation"]), _hash(row["a1_run_sha256"]),
                _hash(row["a1_input_audit_sha256"]), row["threshold_reference"],
            )
            roles.append(role)
    except (ValueError, TypeError, UnicodeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        raise PermissionError("authenticated role registry cannot be parsed as complete typed metadata") from exc
    role_ids = tuple(role.role_id for role in roles)
    if len(set(role_ids)) != 105 or role_ids != tuple(sorted(role_ids)):
        raise PermissionError("authenticated registry requires 105 unique registrations sorted by exact role ID")
    roots, inners, children = {}, {}, {}
    for role in roles:
        parts = role.role_id.split("/")
        size, suffix = {"outer": (3, "outer"), "inner_heldout": (4, "inner"), "inner_train": (5, "subinner")}[role.kind]
        if (len(parts) != size or parts[0] != "candidate" or parts[-1] != suffix
                or parts[1] != role.outer_id or any(_SEGMENT.fullmatch(part) is None for part in parts[1:-1])):
            raise PermissionError("authenticated role ID, kind, outer ID or parent hierarchy is inconsistent")
        if role.kind == "outer":
            roots[role.outer_id] = role.role_id
        elif role.kind == "inner_heldout":
            inners.setdefault(role.outer_id, []).append(role.role_id)
        else:
            parent = "/".join(parts[:3]) + "/inner"
            children.setdefault(parent, []).append(role.role_id)
    if (len(roots) != 5 or set(inners) != set(roots) or any(len(items) != 4 for items in inners.values())
            or set(children) != {role for items in inners.values() for role in items}
            or any(len(items) != 4 for items in children.values())
            or sum(len(items) for items in children.values()) != 80):
        raise PermissionError("authenticated registry does not define the complete independent 5x4x4 role topology")
    outer_roles = tuple(roots[outer] for outer in sorted(roots))
    inner_graph = tuple((outer, tuple(sorted(inners[outer]))) for outer in sorted(roots))
    training_graph = []
    for outer, inner_roles in inner_graph:
        for inner in inner_roles:
            verifier = "verifier/" + "/".join(inner.split("/")[1:3])
            training_graph.append((verifier, tuple(sorted(children[inner]))))
        training_graph.append((f"verifier/{outer}/outer", inner_roles))
    return registry_hash, set(role_ids), outer_roles, inner_graph, tuple(training_graph)


@dataclass(frozen=True, slots=True)
class StageAReplayReceipt:
    invocation_id: str
    entry_event_sha256: str
    role_graph_sha256: str
    role_input_registry_sha256: str
    reference_role_ids: tuple[str, ...]
    treatment_files: tuple[CandidateFileReceipt, ...]
    different_treatment_role_ids: tuple[str, ...]
    candidate_rows_n: int
    candidate_file_bytes_b: int
    maximum_fit_rows_m: int
    prediction_rows_s: int
    artifact_verification_scope: str = field(default="LEDGER_METADATA_ONLY", init=False)


def replay_stage_a(
    ledger_bytes: bytes, *, invocation_id: str, study_root_path: str,
    expected_role_graph_sha256: str, entry_event_sha256: str,
    role_registry_bytes: bytes, expected_role_input_registry_sha256: str,
    broker_registration_bytes: bytes | None = None,
) -> StageAReplayReceipt:
    """Rebuild reservations/results and projection from canonical durable bytes.

    Expected invocation/root/graph/registry pins must come from the caller's
    separately authenticated admission. The complete registry bytes are
    mandatory and authenticated before the journal is replayed. No approval
    dict or boolean is accepted. All 210 results are paired with unique, exact
    stage ordinals.
    """
    invocation_id = _text(invocation_id)
    root = _path(study_root_path)
    if root.name != STUDY_ID:
        raise PermissionError("Stage A replay root differs from the exact study namespace")
    expected_graph = _hash(expected_role_graph_sha256)
    registry_hash, registered_roles, registered_outer, registered_inner, registered_training = _authenticated_topology(
        role_registry_bytes, expected_registry_sha256=expected_role_input_registry_sha256,
        expected_graph_sha256=expected_graph,
    )
    entry_hash = _hash(entry_event_sha256)
    entries = _chain(ledger_bytes)
    names = [item["event"] for item in entries]
    if broker_registration_bytes is None:
        if "gt_broker_registered" in names:
            raise PermissionError("broker registration needs separately authenticated original-owner bytes")
    else:
        if (type(broker_registration_bytes) is not bytes or not 0 < len(broker_registration_bytes) <= 1 << 20
                or names.count("gt_broker_registered") != 1 or names[2:3] != ["gt_broker_registered"]):
            raise PermissionError("Stage A requires exactly one authenticated registration at pre-worker sequence two")
        registered = entries[2]
        original_record = {"entry": {key: value for key, value in registered.items() if key != "sha256"},
                           "sha256": registered["sha256"]}
        if _canonical(original_record) != broker_registration_bytes:
            raise PermissionError("Stage A registration differs from the original native owner's durable bytes")
        payload = registered["payload"]
        if (payload.get("invocation_id") != invocation_id or type(payload.get("view_count")) is not int
                or payload["view_count"] != 110 or type(payload.get("kernel")) is not dict
                or type(payload.get("worker_backing")) is not dict
                or type(payload.get("issued_worker_identities")) is not list
                or type(payload.get("controller_run_id")) is not str
                or re.fullmatch(r"[0-9a-f]{32}", payload["controller_run_id"]) is None):
            raise PermissionError("Stage A registration has invalid original invocation/registry/kernel/backing metadata")
        for key in ("manifest_sha256", "gt_registry_sha256", "protected_registry_sha256", "history_sha256"):
            _hash(payload.get(key))
    for name in ("study_created", "invocation_started", "stage_a_finished", "stage_b_entry_passed"):
        if names.count(name) != 1:
            raise PermissionError("Stage A replay lacks its unique study/invocation/boundary/entry events")
    if (names[:2] != ["study_created", "invocation_started"]
            or names[-2:] != ["stage_a_finished", "stage_b_entry_passed"]
            or entries[-1]["sha256"] != entry_hash):
        raise PermissionError("Stage A replay is not bound to the exact entry ledger tail")
    for item in entries:
        if item["event"] not in _SCHEMAS or set(item["payload"]) != _SCHEMAS[item["event"]]:
            raise PermissionError("Stage A replay encountered an unknown event or payload schema")
    created, start, boundary, entry = (entries[i]["payload"] for i in (0, 1, -2, -1))
    if (created["study_id"] != STUDY_ID or any(value["invocation_id"] != invocation_id
            for value in (start, boundary, entry))):
        raise PermissionError("Stage A replay study or invocation identity changed")
    _text(created["approval_record"])
    _hash(created["input_registry_sha256"])
    _hash(created["budget_policy_sha256"])
    _integer(created["created_wall_ns"], minimum=1)
    if type(created["limits"]) is not dict or set(created["limits"]) != {item.name for item in fields(BudgetLimits)}:
        raise PermissionError("Stage A replay has an incomplete budget schema")
    try:
        limits = BudgetLimits(**created["limits"])
    except (TypeError, ValueError) as exc:
        raise PermissionError("Stage A replay has invalid exact budget limits") from exc
    if _hash(created["budget_policy_sha256"]) != limits.digest():
        raise PermissionError("Stage A journal budget hash differs from its limits")
    started_ns = _integer(start["monotonic_ns"], minimum=1)
    finished_ns = _integer(boundary["finished_monotonic_ns"], minimum=1)
    rss = _integer(start["frozen_rss_ceiling_bytes"], minimum=1)
    if (type(start["controller_receipt"]) is not dict or not started_ns < finished_ns <= started_ns + limits.stage_a_wall_ns
            or rss > limits.rss_cap_bytes):
        raise PermissionError("Stage A replay startup/boundary resource metadata is invalid")
    startup_snapshot = _snapshot(start["startup_snapshot"], rss=rss, limits=limits)
    projection = entry["projection"]
    if type(projection) is not dict:
        raise PermissionError("Stage A entry lacks an exact projection object")
    try:
        graph_hash, call_roles, training_graph = _projection_call_role_ids(projection)
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as exc:
        raise PermissionError("Stage A entry has an invalid frozen role graph") from exc
    if graph_hash != expected_graph:
        raise PermissionError("Stage A projection differs from the authenticated role graph pin")
    heldout_roles = set(call_roles["verifier_predict"])
    all_roles = heldout_roles | {role for roles in training_graph.values() for role in roles}
    if len(all_roles) != 105 or len(heldout_roles) != 25:
        raise PermissionError("Stage A role graph does not contain exactly 5+20+80 candidate roles")
    if (all_roles != registered_roles or tuple(projection["outer_role_ids"]) != registered_outer
            or tuple((outer, tuple(roles)) for outer, roles in projection["inner_role_ids_by_outer"]) != registered_inner
            or tuple(training_graph.items()) != registered_training):
        raise PermissionError("projection role IDs and training links differ from the independent authenticated registry")

    reservations = {"reference": set(), "treatment": set()}
    references: dict[str, tuple[int, str]] = {}
    treatments: dict[str, CandidateFileReceipt] = {}
    difference_roles: set[str] = set()
    paths: set[str] = set()
    pending: tuple[str, str] | None = None
    active: tuple[str, int] | None = None
    activity_order = ("stage_a_reference", "stage_a_treatment")
    completed_activities = 0
    last_sample = started_ns
    for item in entries[2:-2]:
        name, value = item["event"], item["payload"]
        if name == "gt_broker_registered":
            continue  # Only the separately authenticated unique sequence-two record above.
        if name == "activity_started":
            timestamp = _integer(value["monotonic_ns"], minimum=1)
            if (active is not None or pending is not None or value["fit"] is not False
                    or value["stage_a"] is not True or not last_sample <= timestamp <= finished_ns
                    or completed_activities >= len(activity_order)
                    or value["name"] != activity_order[completed_activities]):
                raise PermissionError("Stage A replay has invalid activity order or stage flags")
            active = (_text(value["name"]), timestamp)
        elif name == "activity_finished":
            if active is None or pending is not None or value["name"] != active[0] or value["failed"] is not False:
                raise PermissionError("Stage A replay has an unmatched, failed or incomplete activity")
            stage = "reference" if active[0] == "stage_a_reference" else "treatment"
            results = references if stage == "reference" else treatments
            if set(results) != all_roles or reservations[stage] != all_roles:
                raise PermissionError("the execution activity cannot finish before all 105 paired stage results")
            end = _integer(value["monotonic_ns"], minimum=1)
            elapsed = _integer(value["elapsed_ns"])
            wall = _integer(value["invocation_wall_ns"])
            fit = _integer(value["fit_wall_ns"])
            if (not active[1] <= end <= active[1] + elapsed <= started_ns + wall <= finished_ns
                    or elapsed > limits.stage_a_wall_ns or wall > min(limits.stage_a_wall_ns, limits.total_wall_ns)
                    or fit != 0):
                raise PermissionError("Stage A replay activity samples exceeded or hid phase wall consumption")
            observed_snapshot = _snapshot(value["snapshot"], rss=rss, limits=limits)
            require_stage_filesystem(observed_snapshot,startup_snapshot,limits.stage_a_disk_bytes)
            last_sample = started_ns + wall
            active = None
            completed_activities += 1
        elif name == "candidate_reconstruction_reserved":
            stage, role = value["stage"], value["role_id"]
            if (type(stage) is not str or stage not in reservations or type(role) is not str or role not in all_roles
                    or pending is not None or role in reservations[stage]
                    or active is None or active[0] != "stage_a_" + stage
                    or _integer(value["attempt"], minimum=1) != len(reservations[stage]) + 1
                    or len(reservations[stage]) >= 105):
                raise PermissionError("Stage A reservation has a duplicate/unpaired role or invalid exact attempt")
            if (stage == "reference" and reservations["treatment"]) or (
                    stage == "treatment" and set(references) != all_roles):
                raise PermissionError("all 105 reference results must precede every treatment reservation")
            reservations[stage].add(role)
            pending = (stage, role)
        elif name == "reference_role_passed":
            role = value["role_id"]
            if (type(role) is not str or role not in all_roles or pending != ("reference", role) or role in references
                    or active is None or active[0] != "stage_a_reference"):
                raise PermissionError("reference result has no exact unique prior reservation")
            count, fingerprint = _integer(value["candidate_count"]), _hash(value["interval_fingerprint"])
            if (count == 0) != (fingerprint == _EMPTY_HASH):
                raise PermissionError("reference count differs from the empty/nonempty interval fingerprint")
            references[role] = (count, fingerprint)
            pending = None
        elif name == "treatment_role_finished":
            role = value["role_id"]
            if (type(role) is not str or role not in all_roles or pending != ("treatment", role)
                    or role in treatments or set(references) != all_roles
                    or active is None or active[0] != "stage_a_treatment"):
                raise PermissionError("treatment result has no unique paired reservation after complete references")
            count, file_bytes = _integer(value["row_count"]), _integer(value["file_bytes"])
            content_hash, fingerprint = _hash(value["sha256"]), _hash(value["interval_fingerprint"])
            path = str(_path(value["path"]))
            expected = root / "treatment-candidates" / (hashlib.sha256(role.encode("utf-8")).hexdigest()[:20] + ".jsonl")
            if path != str(expected) or path in paths:
                raise PermissionError("treatment candidate path differs from the exact unique role output")
            if (count == 0 and (file_bytes != 0 or content_hash != _EMPTY_HASH or fingerprint != _EMPTY_HASH)) or (
                    count > 0 and (content_hash == _EMPTY_HASH or fingerprint == _EMPTY_HASH
                                   or not count <= file_bytes <= count * (1 << 20))):
                raise PermissionError("treatment candidate count/byte/hash evidence is inconsistent")
            same = (count, fingerprint) == references[role]
            if type(value["interval_set_same"]) is not bool or value["interval_set_same"] is not same:
                raise PermissionError("treatment difference claim differs from reference count/interval fingerprint")
            paths.add(path)
            treatments[role] = CandidateFileReceipt(role, path, content_hash, count, file_bytes, fingerprint)
            if not same:
                difference_roles.add(role)
            pending = None
        else:
            raise PermissionError("Stage A replay contains a misplaced summary event")
    if (pending is not None or active is not None or set(references) != all_roles or set(treatments) != all_roles
            or completed_activities != len(activity_order)
            or any(roles != all_roles for roles in reservations.values())):
        raise PermissionError("Stage A replay did not complete every exact 105 reference and 105 treatment role")
    for key, expected in (("reference_roles", 105), ("treatment_roles", 105),
                          ("different_treatment_roles", len(difference_roles))):
        if _integer(boundary[key]) != expected:
            raise PermissionError("Stage A boundary summary differs from its durable result replay")
    if not difference_roles:
        raise PermissionError("identical treatment roles cannot enter the expansion gate")
    rows = {role: receipt.row_count for role, receipt in treatments.items()}
    total_n = sum(rows.values())
    total_b = sum(receipt.file_bytes for receipt in treatments.values())
    maximum_m = max(
        sum(rows[role] for role in training_graph[verifier]) + rows[
            "candidate/" + verifier.removeprefix("verifier/") + ("" if verifier.endswith("/outer") else "/inner")
        ] for verifier in call_roles["verifier_fit"]
    )
    heldout_s = sum(rows[role] for role in heldout_roles)
    disk = _integer(boundary["stage_a_disk_bytes"])
    if limits.stage_a_disk_accounting_mode == STAGE_A_CAPACITY_UPPER_BOUND_V2 and disk != limits.stage_a_disk_bytes:
        raise PermissionError("Stage A V2 boundary must state the strict capacity bound, not current usage")
    if not total_b <= disk <= limits.stage_a_disk_bytes or projection["stage_a_disk_bytes_d_a"] != disk:
        raise PermissionError("Stage A artifact bytes/disk boundary differ from the frozen entry projection")
    for key, expected in (("candidate_rows_n", total_n), ("candidate_file_bytes_b", total_b),
                          ("maximum_fit_rows_m", maximum_m), ("prediction_rows_s", heldout_s)):
        if projection[key] != expected:
            raise PermissionError("Stage B projection differs from replayed candidate counts and fixed fit graph")
    return StageAReplayReceipt(
        invocation_id, entry_hash, expected_graph, registry_hash, tuple(sorted(references)),
        tuple(treatments[role] for role in sorted(treatments)), tuple(sorted(difference_roles)),
        total_n, total_b, maximum_m, heldout_s,
    )
