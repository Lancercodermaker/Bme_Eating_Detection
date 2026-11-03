"""Full Stage A metadata replay regressions, with no data/artifact access."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json

import pytest

from test_route2_linux_volume_backend_synthetic import canonical, expand, mutations, rig  # noqa: F401


MODULE = "eating_event.route2_candidate_overlap.stage_a_replay"
SUMMARY_NAMES = {"study_created", "invocation_started", "stage_a_finished", "stage_b_entry_passed"}


def test_stage_a_replay_module_exists():
    assert importlib.util.find_spec(MODULE) is not None, "full Stage A replay is missing"


def test_four_summary_events_cannot_authorize_expansion(rig):
    rig.ports.events = [item for item in rig.ports.events if item[0] in SUMMARY_NAMES]
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def replay(rig, **overrides):
    from eating_event.route2_candidate_overlap.stage_a_replay import replay_stage_a
    args = dict(invocation_id=rig.current.invocation_id,
                study_root_path=rig.current.study_root_path,
                expected_role_graph_sha256="a" * 64,
                role_registry_bytes=rig.registry_bytes,
                expected_role_input_registry_sha256=rig.ports.body["frozen_admission"]["role_input_registry_sha256"],
                entry_event_sha256=rig.ports.gate_hash)
    args.update(overrides)
    return replay_stage_a(rig.ports.ledger(), **args)


def positions(rig, name):
    return [i for i, (event, _) in enumerate(rig.ports.events) if event == name]


def payload(rig, name, index=0):
    return rig.ports.events[positions(rig, name)[index]][1]


def test_complete_105_reference_then_treatment_replays_exact_projection(rig):
    result = replay(rig)
    expected = payload(rig, "stage_b_entry_passed")["projection"]
    assert len(result.reference_role_ids) == len(result.treatment_files) == 105
    assert len(result.different_treatment_role_ids) == 1
    for field in ("candidate_rows_n", "candidate_file_bytes_b", "maximum_fit_rows_m", "prediction_rows_s"):
        assert getattr(result, field) == expected[field]
    assert result.entry_event_sha256 == rig.ports.gate_hash
    assert result.role_input_registry_sha256 == hashlib.sha256(rig.registry_bytes).hexdigest()
    assert result.artifact_verification_scope == "LEDGER_METADATA_ONLY"


@pytest.mark.parametrize("name", ["candidate_reconstruction_reserved", "reference_role_passed", "treatment_role_finished"])
def test_omitted_stage_a_event_is_denied(rig, name):
    del rig.ports.events[positions(rig, name)[0]]
    with pytest.raises(PermissionError):
        replay(rig)

@pytest.mark.parametrize("name", ["candidate_reconstruction_reserved", "reference_role_passed", "treatment_role_finished"])
def test_duplicate_stage_a_event_is_denied(rig, name):
    index = positions(rig, name)[0]
    rig.ports.events.insert(index + 1, deepcopy(rig.ports.events[index]))
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("name", ["unknown_event", "reference_passed", "candidate_reconstruction_failed",
                                   "terminal", "gt_phase_released", "call_reserved"])
def test_unknown_or_forged_stage_a_event_is_denied(rig, name):
    rig.ports.events.insert(2, (name, {}))
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("name", ["candidate_reconstruction_reserved", "reference_role_passed", "treatment_role_finished"])
def test_roles_must_be_in_exact_105_role_graph(rig, name):
    payload(rig, name)["role_id"] = "candidate/rogue/outer"
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("value", [True, 1.0, 0, 2, 106, "1"])
def test_reference_reservation_attempt_is_exact_stage_ordinal(rig, value):
    payload(rig, "candidate_reconstruction_reserved")["attempt"] = value
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("value", [True, 1.0, 0, 2, 106, "1"])
def test_treatment_reservation_attempt_restarts_at_one(rig, value):
    reservations = positions(rig, "candidate_reconstruction_reserved")
    rig.ports.events[reservations[105]][1]["attempt"] = value
    with pytest.raises(PermissionError):
        replay(rig)


def test_reference_result_cannot_precede_reservation(rig):
    left = positions(rig, "candidate_reconstruction_reserved")[0]
    right = positions(rig, "reference_role_passed")[0]
    rig.ports.events[left], rig.ports.events[right] = rig.ports.events[right], rig.ports.events[left]
    with pytest.raises(PermissionError):
        replay(rig)


def test_treatment_cannot_begin_until_all_references_have_passed(rig):
    index = positions(rig, "candidate_reconstruction_reserved")[105]
    reservation = rig.ports.events.pop(index)
    rig.ports.events.insert(2, reservation)
    with pytest.raises(PermissionError):
        replay(rig)


def test_result_must_match_the_reserved_role(rig):
    payload(rig, "reference_role_passed")["role_id"] = payload(rig, "reference_role_passed", 1)["role_id"]
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("name,field,value", [
    ("reference_role_passed", "candidate_count", True),
    ("reference_role_passed", "candidate_count", -1),
    ("reference_role_passed", "interval_fingerprint", "x" * 64),
    ("treatment_role_finished", "row_count", True),
    ("treatment_role_finished", "file_bytes", -1),
    ("treatment_role_finished", "file_bytes", 0),
    ("treatment_role_finished", "sha256", "x" * 64),
    ("treatment_role_finished", "interval_fingerprint", "x" * 64),
    ("treatment_role_finished", "interval_set_same", 1),
])
def test_candidate_evidence_fields_are_exact(rig, name, field, value):
    payload(rig, name)[field] = value
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("name", ["candidate_reconstruction_reserved", "reference_role_passed", "treatment_role_finished"])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_stage_a_payload_schema_is_exact(rig, name, change):
    value = payload(rig, name)
    if change == "missing":
        del value["role_id"]
    else:
        value["approved"] = True
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("path", ["/tmp/forged.jsonl", "relative.jsonl", "C:\\synthetic\\candidate.jsonl",
    "/var/lib/route2/studies/synthetic-volume/../forged.jsonl"])
def test_treatment_path_must_match_exact_role_output_under_study(rig, path):
    payload(rig, "treatment_role_finished")["path"] = path
    with pytest.raises(PermissionError):
        replay(rig)


def test_different_role_file_path_cannot_be_reused(rig):
    payload(rig, "treatment_role_finished")["path"] = payload(rig, "treatment_role_finished", 1)["path"]
    with pytest.raises(PermissionError):
        replay(rig)


def test_difference_boolean_is_rederived_from_count_and_interval_fingerprint(rig):
    value = payload(rig, "treatment_role_finished")
    value["interval_set_same"] = not value["interval_set_same"]
    with pytest.raises(PermissionError):
        replay(rig)


def test_same_interval_fingerprint_cannot_hide_count_difference(rig):
    payload(rig, "reference_role_passed", 1)["candidate_count"] += 1
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("field,value", [("reference_roles", 104), ("reference_roles", 105.0),
    ("treatment_roles", 104), ("different_treatment_roles", 2), ("different_treatment_roles", True)])
def test_boundary_counts_are_rebuilt_from_events(rig, field, value):
    payload(rig, "stage_a_finished")[field] = value
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("field", ["candidate_rows_n", "candidate_file_bytes_b", "maximum_fit_rows_m", "prediction_rows_s"])
def test_projection_counts_must_equal_replayed_receipts_and_fixed_graph(rig, field):
    projection = payload(rig, "stage_b_entry_passed")["projection"]
    projection[field] += 1
    with pytest.raises(PermissionError):
        replay(rig)


def test_varied_role_counts_derive_m_with_heldout_and_s_without_subinner(rig):
    treatments = [item[1] for item in rig.ports.events if item[0] == "treatment_role_finished"]
    references = {item[1]["role_id"]: item[1] for item in rig.ports.events if item[0] == "reference_role_passed"}
    counts = {}
    for ordinal, value in enumerate(treatments):
        value["row_count"] = ordinal % 7 + 1
        references[value["role_id"]]["candidate_count"] = value["row_count"]
        counts[value["role_id"]] = value["row_count"]
    projection = payload(rig, "stage_b_entry_passed")["projection"]
    graph = projection["fit_training_roles_by_verifier"]
    projection["candidate_rows_n"] = sum(counts.values())
    projection["maximum_fit_rows_m"] = max(sum(counts[role] for role in children) +
        counts["candidate/" + verifier.removeprefix("verifier/") +
               ("" if verifier.endswith("/outer") else "/inner")] for verifier, children in graph)
    heldout = set(projection["outer_role_ids"]) | {role for _, roles in projection["inner_role_ids_by_outer"] for role in roles}
    projection["prediction_rows_s"] = sum(counts[role] for role in heldout)
    result = replay(rig)
    assert result.maximum_fit_rows_m == projection["maximum_fit_rows_m"]
    assert result.prediction_rows_s == projection["prediction_rows_s"]


@pytest.mark.parametrize("change", ["tail", "invocation", "graph", "chain", "partial", "noncanonical"])
def test_replay_is_bound_to_authentic_canonical_chain_and_invocation(rig, change):
    kwargs = {}
    if change == "tail":
        kwargs["entry_event_sha256"] = "0" * 64
    elif change == "invocation":
        kwargs["invocation_id"] = "different-invocation"
    elif change == "graph":
        kwargs["expected_role_graph_sha256"] = "b" * 64
    else:
        raw = rig.ports.ledger()
        if change == "chain":
            values = [json.loads(line) for line in raw.splitlines()]
            values[2]["sha256"] = "0" * 64
            raw = b"".join(canonical(item) + b"\n" for item in values)
        elif change == "partial":
            raw = raw[:-1]
        else:
            raw = b" " + raw
        rig.ports.raw_ledger = raw
    with pytest.raises(PermissionError):
        replay(rig, **kwargs)


def test_extension_gate_actually_calls_stage_a_replay(rig, monkeypatch):
    def reject(*_args, **_kwargs):
        raise PermissionError("synthetic full replay denied")
    monkeypatch.setattr(rig.backend, "replay_stage_a", reject, raising=False)
    with pytest.raises(PermissionError, match="full replay denied"):
        expand(rig)
    assert not mutations(rig.ports)


def activity_position(rig, event, stage):
    return next(i for i, (name, value) in enumerate(rig.ports.events)
                if name == event and value["name"] == "stage_a_" + stage)


def test_complete_roles_without_execution_activities_are_denied(rig):
    rig.ports.events = [item for item in rig.ports.events if not item[0].startswith("activity_")]
    with pytest.raises(PermissionError):
        replay(rig)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
def test_each_stage_requires_its_unique_full_activity_frame(rig, stage):
    rig.ports.events = [item for item in rig.ports.events
                        if not (item[0].startswith("activity_") and item[1]["name"] == "stage_a_" + stage)]
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
def test_unknown_activity_name_cannot_cover_reconstruction(rig, stage):
    for name, value in rig.ports.events:
        if name.startswith("activity_") and value["name"] == "stage_a_" + stage:
            value["name"] = "synthetic_approval"
    with pytest.raises(PermissionError):
        replay(rig)


def test_reference_and_treatment_activity_names_cannot_be_swapped(rig):
    for name, value in rig.ports.events:
        if name.startswith("activity_"):
            value["name"] = ("stage_a_treatment" if value["name"] == "stage_a_reference"
                              else "stage_a_reference")
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
def test_reservation_and_result_before_activity_start_are_denied(rig, stage):
    start = activity_position(rig, "activity_started", stage)
    event = rig.ports.events.pop(start)
    rig.ports.events.insert(start + 2, event)
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
def test_activity_cannot_finish_before_105th_result(rig, stage):
    finish = activity_position(rig, "activity_finished", stage)
    event = rig.ports.events.pop(finish)
    rig.ports.events.insert(finish - 2, event)
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
def test_empty_activity_cannot_be_followed_by_unprotected_stage_roles(rig, stage):
    start = activity_position(rig, "activity_started", stage)
    finish = activity_position(rig, "activity_finished", stage)
    event = rig.ports.events.pop(finish)
    rig.ports.events.insert(start + 1, event)
    with pytest.raises(PermissionError):
        replay(rig)


def test_treatment_activity_cannot_also_cover_all_reference_roles(rig):
    rig.ports.events = [item for item in rig.ports.events
                        if not (item[0].startswith("activity_") and item[1]["name"] == "stage_a_reference")]
    start = activity_position(rig, "activity_started", "treatment")
    event = rig.ports.events.pop(start)
    rig.ports.events.insert(2, event)
    with pytest.raises(PermissionError):
        replay(rig)


def test_two_partial_activities_cannot_replace_the_single_full_reference_activity(rig):
    start = activity_position(rig, "activity_started", "reference")
    finish = activity_position(rig, "activity_finished", "reference")
    early_end = deepcopy(rig.ports.events[finish])
    early_end[1].update(monotonic_ns=152, elapsed_ns=1, invocation_wall_ns=53)
    second_start = deepcopy(rig.ports.events[start])
    second_start[1]["monotonic_ns"] = 153
    rig.ports.events[finish][1]["elapsed_ns"] = 2
    rig.ports.events[start + 3:start + 3] = [early_end, second_start]
    with pytest.raises(PermissionError):
        replay(rig)


def test_third_activity_after_both_complete_is_denied(rig):
    begin = deepcopy(rig.ports.events[activity_position(rig, "activity_started", "treatment")])
    end = deepcopy(rig.ports.events[activity_position(rig, "activity_finished", "treatment")])
    begin[1].update(name="extra", monotonic_ns=191)
    end[1].update(name="extra", monotonic_ns=194, elapsed_ns=4, invocation_wall_ns=96)
    rig.ports.events[-2:-2] = [begin, end]
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("stage", ["reference", "treatment"])
@pytest.mark.parametrize("change", ["missing", "extra", "wrong_type"])
def test_required_activity_snapshot_schema_remains_exact(rig, stage, change):
    snapshot = rig.ports.events[activity_position(rig, "activity_finished", stage)][1]["snapshot"]
    if change == "missing":
        del snapshot["compute_workers"]
    elif change == "extra":
        snapshot["approved"] = True
    else:
        snapshot["compute_workers"] = True
    with pytest.raises(PermissionError):
        replay(rig)


@pytest.mark.parametrize("name,field", [
    ("reference_role_passed", "interval_fingerprint"),
    ("treatment_role_finished", "interval_fingerprint"),
    ("treatment_role_finished", "sha256"),
])
def test_positive_candidate_count_cannot_claim_empty_content_or_interval_hash(rig, name, field):
    empty = hashlib.sha256(b"").hexdigest()
    # Alter a matching role's reference and treatment fingerprints together so
    # the legacy same/difference check alone cannot reject the forged pair.
    if name == "reference_role_passed":
        payload(rig, "reference_role_passed", 1)[field] = empty
        payload(rig, "treatment_role_finished", 1)[field] = empty
    else:
        payload(rig, name, 1)[field] = empty
        if field == "interval_fingerprint":
            payload(rig, "treatment_role_finished", 1)["interval_set_same"] = False
            payload(rig, "stage_a_finished")["different_treatment_roles"] = 2
    with pytest.raises(PermissionError):
        replay(rig)


def test_projection_m_uses_independent_hand_calculated_counts(rig):
    # Hand calculation over a fixed, named graph (no production graph walk):
    # o1 outer fit: 11+13+19+23+17 = 83.
    # o1/i1 inner fit: 7+9+15+21+11 = 63.
    # o2/i4 inner fit: 29+31+37+41+1 = 139 (the maximum).
    # Other fits have four unit children plus at most a 23-row heldout.
    counts = {
        "candidate/o1/outer": 17,
        "candidate/o1/i1/inner": 11, "candidate/o1/i2/inner": 13,
        "candidate/o1/i3/inner": 19, "candidate/o1/i4/inner": 23,
        "candidate/o1/i1/s1/subinner": 7, "candidate/o1/i1/s2/subinner": 9,
        "candidate/o1/i1/s3/subinner": 15, "candidate/o1/i1/s4/subinner": 21,
        "candidate/o2/i4/s1/subinner": 29, "candidate/o2/i4/s2/subinner": 31,
        "candidate/o2/i4/s3/subinner": 37, "candidate/o2/i4/s4/subinner": 41,
    }
    for event, value in rig.ports.events:
        if event == "reference_role_passed":
            value["candidate_count"] = counts.get(value["role_id"], 1)
        elif event == "treatment_role_finished":
            value["row_count"] = counts.get(value["role_id"], 1)
    projection = payload(rig, "stage_b_entry_passed")["projection"]
    # Unit baseline N=105 plus 78 heldout, 48 o1/i1 and 134 o2/i4 increments.
    # Unit baseline S=25 plus only the 78 heldout increments.
    projection.update(candidate_rows_n=365, maximum_fit_rows_m=139, prediction_rows_s=103)
    result = replay(rig)
    assert (result.candidate_rows_n, result.maximum_fit_rows_m, result.prediction_rows_s) == (365, 139, 103)


def test_missing_authenticated_role_registry_denies_before_expansion(rig):
    rig.expander = rig.backend.LinuxLoopVolumeExpander(ports=rig.ports)
    with pytest.raises(PermissionError, match="registry"):
        expand(rig)
    assert not mutations(rig.ports)


def test_projection_cannot_relabel_all_roles_while_retaining_original_graph_hash(rig):
    for event, value in rig.ports.events:
        if "role_id" in value:
            value["role_id"] = value["role_id"].replace("/o5/", "/o6/")
        if event == "treatment_role_finished":
            stem = hashlib.sha256(value["role_id"].encode()).hexdigest()[:20]
            value["path"] = f"{rig.current.study_root_path}/treatment-candidates/{stem}.jsonl"
    projection = payload(rig, "stage_b_entry_passed")["projection"]
    projection["outer_role_ids"] = [role.replace("/o5/", "/o6/") for role in projection["outer_role_ids"]]
    projection["inner_role_ids_by_outer"] = [("o6" if outer == "o5" else outer,
        [role.replace("/o5/", "/o6/") for role in roles]) for outer, roles in projection["inner_role_ids_by_outer"]]
    projection["fit_training_roles_by_verifier"] = [(verifier.replace("/o5/", "/o6/"),
        [role.replace("/o5/", "/o6/") for role in roles]) for verifier, roles in projection["fit_training_roles_by_verifier"]]
    with pytest.raises(PermissionError):
        replay(rig)
    # The production gate must compare the same independent evidence before
    # artifact opening or attempt reservation, not just the pure replay helper.
    with pytest.raises(PermissionError):
        rig.expander._gate(rig.ports.ledger(), rig.ports.gate_hash, rig.current,
                           rig.limits, rig.expander._admission()[0])
    assert not mutations(rig.ports)


def supply_registry(rig, encoded, *, repin=False):
    rig.expander._role_registry_bytes = encoded
    if repin:
        from eating_event.route2_candidate_overlap.contracts import stage_a_registry_sha256
        pins = rig.ports.body["frozen_admission"]
        pins["role_input_registry_sha256"] = hashlib.sha256(encoded).hexdigest()
        pins["combined_input_registry_sha256"] = stage_a_registry_sha256(
            pins["role_graph_sha256"], pins["role_input_registry_sha256"], pins["reference_registry_sha256"])
        payload(rig, "study_created")["input_registry_sha256"] = pins["combined_input_registry_sha256"]


@pytest.mark.parametrize("value", [None, True, {}, b"", "approved", bytearray(b"metadata")])
def test_registry_byte_evidence_cannot_be_a_flag_dict_or_mutable_buffer(rig, value):
    supply_registry(rig, value)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_arbitrary_registry_byte_tamper_is_rejected_against_sealed_pin(rig):
    supply_registry(rig, rig.registry_bytes + b" ")
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("change", ["whitespace", "newline", "unsorted", "not_list", "duplicate_key"])
def test_registry_requires_exact_canonical_sorted_serialization_even_when_repinned(rig, change):
    rows = json.loads(rig.registry_bytes)
    if change == "whitespace":
        encoded = b" " + rig.registry_bytes
    elif change == "newline":
        encoded = rig.registry_bytes + b"\n"
    elif change == "unsorted":
        encoded = canonical(list(reversed(rows)))
    elif change == "not_list":
        encoded = canonical({"registrations": rows})
    else:
        encoded = rig.registry_bytes.replace(b'"role_graph_sha256":"' + b"a" * 64 + b'"',
            b'"role_graph_sha256":"' + b"a" * 64 + b'","role_graph_sha256":"' + b"a" * 64 + b'"', 1)
    supply_registry(rig, encoded, repin=True)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("change", [
    "missing_role", "duplicate_role", "wrong_outer", "wrong_kind", "row_graph_hash",
    "missing_role_field", "extra_role_field", "fit_is_text", "nontext_participant", "overlap",
    "missing_registration_field", "extra_registration_field", "nested_file_field", "wrong_file_role",
    "threshold_boolean", "missing_cache", "wrong_parent",
])
def test_authenticated_registry_full_schema_and_topology_are_validated(rig, change):
    rows = json.loads(rig.registry_bytes)
    row = rows[0]
    if change == "missing_role":
        rows.pop()
    elif change == "duplicate_role":
        rows[1] = deepcopy(rows[0])
    elif change == "wrong_outer":
        row["role"]["outer_id"] = "o2"
    elif change == "wrong_kind":
        row["role"]["kind"] = "outer"
    elif change == "row_graph_hash":
        row["role_graph_sha256"] = "e" * 64
    elif change == "missing_role_field":
        del row["role"]["fit_participants"]
    elif change == "extra_role_field":
        row["role"]["approved"] = True
    elif change == "fit_is_text":
        row["role"]["fit_participants"] = "fit"
    elif change == "nontext_participant":
        row["role"]["fit_participants"] = [True]
    elif change == "overlap":
        row["role"]["fit_participants"] = row["role"]["scored_participants"]
    elif change == "missing_registration_field":
        del row["identity_view"]
    elif change == "extra_registration_field":
        row["approved"] = True
    elif change == "nested_file_field":
        row["score_npz"]["approved"] = True
    elif change == "wrong_file_role":
        row["score_npz"]["role_id"] = "candidate/other/outer"
    elif change == "threshold_boolean":
        row["threshold_reference"] = True
    elif change == "missing_cache":
        row["cache_files"] = []
    else:
        row["role"]["role_id"] = row["role"]["role_id"].replace("/i1/", "/i5/")
    supply_registry(rig, canonical(rows), repin=True)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("overrides", [
    {"role_registry_bytes": None}, {"role_registry_bytes": True},
    {"role_registry_bytes": {}}, {"expected_role_input_registry_sha256": True},
    {"expected_role_input_registry_sha256": "e" * 64},
])
def test_pure_replay_requires_full_registry_bytes_and_exact_external_hash(rig, overrides):
    with pytest.raises(PermissionError):
        replay(rig, **overrides)


def test_pure_replay_registry_arguments_have_no_optional_default(rig):
    from eating_event.route2_candidate_overlap.stage_a_replay import replay_stage_a
    with pytest.raises(TypeError):
        replay_stage_a(rig.ports.ledger(), invocation_id=rig.current.invocation_id,
            study_root_path=rig.current.study_root_path, expected_role_graph_sha256="a" * 64,
            entry_event_sha256=rig.ports.gate_hash)


def test_registry_evidence_never_opens_any_registered_input_or_metadata_path(rig):
    open_existing = rig.ports.open_existing
    def output_only(path, *, kind, writable=False):
        assert not path.startswith("C:"), "byte-only registry verification opened a registered logical input"
        return open_existing(path, kind=kind, writable=writable)
    rig.ports.open_existing = output_only
    expand(rig)
