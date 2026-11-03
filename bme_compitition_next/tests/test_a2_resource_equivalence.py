from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from eating_event.a1.contracts import WindowIdentity
from eating_event.a1.inputs import TruthRecord
from eating_event.a1.pipeline import build_role_graph
from eating_event.a2.audit import (
    CacheGeometryRow,
    _LazyRoleCandidates,
    _load_materialized_role_candidates,
    _materialize_role,
    _iter_validate_global_identity,
    _spool_candidate_rows,
)
from eating_event.a2.contracts import ContextWindow, STUDY_002_ID, STUDY_003_ID, expected_study_config
from eating_event.a2.execution import A2Candidate, FeatureCorpus, execute_validation
from eating_event.a2.inputs import validate_outer_label, validate_support_identity
from eating_event.metrics import EventInterval


def _candidate(role_id: str, candidate_id: str, *, label: int | None, start: int = 500) -> dict[str, object]:
    return {
        "role_id": role_id,
        "candidate_id": candidate_id,
        "participant_id": "P0",
        "record_id": "R0",
        "session_id": "S0",
        "component_id": "P0|R0|S0|component-0",
        "interval": {"start_ms": start, "end_ms": 2000},
        "features": [float(index) for index in range(16)],
        "support_indices": [{"participant_id": "P0", "record_id": "R0", "session_id": "S0", "row_index": 0}],
        "boundary_kind": "observed_window_support_component_v1",
        "source_segment_id": None,
        "label": label,
    }


def test_baseline_materialized_role_is_byte_exact_for_the_16d_and_26d_contract(tmp_path: Path) -> None:
    role_id = "candidate/outer-0/inner-0/0/subinner"
    candidate = _candidate(role_id, "same-id", label=1)
    context = [
        ContextWindow(role_id, index, f"P0|R0|S0|{index}", str(candidate["component_id"]), start, end, score)
        for index, (start, end, score) in enumerate(
            [(-1000, -500, 0.25), (0, 1000, 0.5), (1000, 2000, -0.25), (2000, 2500, 0.75)]
        )
    ]
    digest = _materialize_role(
        tmp_path,
        SimpleNamespace(role_id=role_id),
        [candidate],
        {str(candidate["component_id"]): context},
        score_hash="s" * 64,
        cache_hash_digest="c" * 64,
    )
    row_path = tmp_path / str(digest["candidate_rows_file"])
    matrix_path = tmp_path / str(digest["feature_matrix_file"])
    label_path = tmp_path / str(digest["training_label_file"])

    assert digest["ordered_candidate_keys_sha256"] == "0cc0c26927701ec34a58d27f25cbe0f4426d1bb9b0762cf8f65ab2525721382a"
    assert digest["source_16d_sha256"] == "980820d0447609601c21dcd14e6d9bf075a94c4b83419603926ec48d59caeb05"
    assert digest["feature_matrix_sha256"] == "f8263e5f9bc56e7bede4c9c841c4ec763c47a8eb078d3f997d6a59661e92ba02"
    assert digest["training_label_join_sha256"] == "7fc1bf36846a4e7f77fa6c4f3cbc4d84efa5e3a794fb646334fd4a2bcb292ffc"
    assert hashlib.sha256(row_path.read_bytes()).hexdigest() == "dcee0df058fd203e5824b372d88a2c4e8e438a8e20c598fa7a107a07b6615e03"
    assert hashlib.sha256(matrix_path.read_bytes()).hexdigest() == "94ae7139d10000cdc74e0192b702345a61615e8accbbccb1d6c49923d22afff8"
    assert hashlib.sha256(label_path.read_bytes()).hexdigest() == "dba0a020aede0dd2c0d19d886e3565b967db3a916784fbbea7f1e10c28622414"
    matrix = np.load(matrix_path, allow_pickle=False)
    assert matrix.shape == (1, 26) and matrix.dtype == np.float32
    assert np.array_equal(matrix[0, :16], np.arange(16, dtype=np.float32))
    assert matrix.tobytes().hex() == (
        "000000000000803f0000004000004040000080400000a0400000c0400000e0400000004100001041000020410000304100004041"
        "0000504100006041000070410000003e000080bd0000003f0000003f0000803e0000803fcdcccc3c0000403f0000803fcdcccc3c"
    )


def test_global_identity_stream_checks_each_ordered_identity_without_loading_a_second_json_list(tmp_path: Path, monkeypatch) -> None:
    geometry = []
    source = []
    for index, (participant, record, session, row_index, start, end) in enumerate(
        [("P0", "R0", "S0", 0, 0, 100), ("P0", "R1", "S1", 0, 100, 200), ("P1", "R2", "S2", 0, 200, 300)]
    ):
        identity = WindowIdentity(participant, record, session, row_index)
        stable = identity.stable_id
        geometry.append({
            "identity": identity,
            "stable_id": stable,
            "participant_id": participant,
            "record_id": record,
            "session_id": session,
            "row_index": row_index,
            "start_ms": start,
            "end_ms": end,
            "coverage": 1.0,
            "crosses_gap": False,
        })
        source.append({
            "participant_id": participant,
            "record_id": record,
            "session_id": session,
            "row_index": row_index,
        })
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("streaming global identity must not call the eager JSON reader")

    monkeypatch.setattr("eating_event.a2.audit._read_json", forbidden)
    index = _iter_validate_global_identity(path, geometry)

    assert index == {row["stable_id"]: position for position, row in enumerate(geometry)}
    changed = list(source)
    changed[1] = {**changed[1], "record_id": "wrong-record"}
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="identity order"):
        _iter_validate_global_identity(path, geometry)


def test_interleaved_candidate_spool_preserves_role_order_and_rejects_contract_violations(tmp_path: Path) -> None:
    outer_a = "candidate/outer-0/outer"
    inner_a = "candidate/outer-0/inner-0/0/subinner"
    outer_role = SimpleNamespace(role_id=outer_a, inner_fold=None)
    inner_role = SimpleNamespace(role_id=inner_a, inner_fold="inner-0")
    rows = [
        _candidate(outer_a, "same-id", label=None),
        _candidate(inner_a, "same-id", label=1),
        _candidate(outer_a, "outer-second", label=None, start=600),
    ]
    source = tmp_path / "event-candidates.jsonl"
    source.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")

    spool, ids_by_role, counts = _spool_candidate_rows(source, {outer_a: outer_role, inner_a: inner_role}, tmp_path / "spool")

    assert ids_by_role[outer_a] == ["same-id", "outer-second"]
    assert ids_by_role[inner_a] == ["same-id"]
    assert counts == {outer_a: 2, inner_a: 1}
    assert [json.loads(line)["candidate_id"] for line in spool[outer_a].read_text(encoding="utf-8").splitlines()] == ids_by_role[outer_a]
    assert [json.loads(line)["candidate_id"] for line in spool[inner_a].read_text(encoding="utf-8").splitlines()] == ids_by_role[inner_a]

    source.write_text("".join(json.dumps(row) + "\n" for row in rows + [rows[0]]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate composite"):
        _spool_candidate_rows(source, {outer_a: outer_role, inner_a: inner_role}, tmp_path / "duplicate")
    invalid_outer = _candidate(outer_a, "bad-label", label=1)
    source.write_text(json.dumps(invalid_outer) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outer.*label"):
        _spool_candidate_rows(source, {outer_a: outer_role}, tmp_path / "bad-label")


def test_support_identity_rejects_missing_cross_role_and_wrong_component() -> None:
    candidate = _candidate("candidate/o0/outer", "same", label=None)
    role_id = str(candidate["role_id"])
    component = str(candidate["component_id"])
    with pytest.raises(ValueError, match="support/component"):
        validate_support_identity({**candidate, "support_indices": []}, role_id=role_id, stable_ids={"P0|R0|S0|0"}, component_by_stable_id={"P0|R0|S0|0": component})
    with pytest.raises(ValueError, match="outside role/component"):
        validate_support_identity(candidate, role_id=role_id, stable_ids={"P0|R0|S0|1"}, component_by_stable_id={"P0|R0|S0|1": component})
    with pytest.raises(ValueError, match="outer.*label"):
        validate_outer_label({**candidate, "label": 0}, outer_role=True)


class _FakeVerifierBackend:
    def __init__(self) -> None:
        self.fit_rows: list[tuple[str, bytes, bytes, tuple[str, ...]]] = []
        self.score_rows: list[tuple[str, bytes, bytes, tuple[str, ...]]] = []

    def fit(self, features: np.ndarray, labels: np.ndarray, participants, role):
        x = np.asarray(features, dtype=np.float32)
        y = np.asarray(labels, dtype=np.int8)
        people = tuple(map(str, participants))
        self.fit_rows.append((role.role_id, x.tobytes(), y.tobytes(), people))
        return {"role_id": role.role_id, "positive_count": int(y.sum())}

    def score(self, model, features: np.ndarray, participants, role):
        x = np.asarray(features, dtype=np.float32)
        people = tuple(map(str, participants))
        values = np.asarray(x[:, 0], dtype=np.float64)
        self.score_rows.append((role.role_id, x.tobytes(), values.tobytes(), people))
        return values


def _reference_eager_role(output: Path, digest: dict[str, object], role_id: str) -> tuple[A2Candidate, ...]:
    rows = [json.loads(line) for line in (output / str(digest["candidate_rows_file"])).read_text(encoding="utf-8").splitlines()]
    matrix = np.load(output / str(digest["feature_matrix_file"]), allow_pickle=False)
    labels = {}
    if digest.get("training_label_file"):
        labels = {
            (str(row["role_id"]), str(row["candidate_id"])): int(row["label"])
            for row in (json.loads(line) for line in (output / str(digest["training_label_file"])).read_text(encoding="utf-8").splitlines())
        }
    result = []
    for index, row in enumerate(rows):
        key = (role_id, str(row["candidate_id"]))
        result.append(A2Candidate(
            role_id=role_id,
            candidate_id=key[1],
            participant_id=str(row["participant_id"]),
            record_id=str(row["record_id"]),
            session_id=str(row["session_id"]),
            component_id=str(row["component_id"]),
            interval=EventInterval(int(row["interval"]["start_ms"]), int(row["interval"]["end_ms"])),
            source_16d=np.asarray(row["source_16d"], dtype=np.float64),
            features_26d=matrix[index],
            support_indices=tuple(WindowIdentity(str(item["participant_id"]), str(item["record_id"]), str(item["session_id"]), int(item["row_index"])) for item in row["support_indices"]),
            label=labels.get(key),
        ))
    return tuple(result)


def _synthetic_feature_corpora(root: Path, *, perturb_outer_fold: str | None = None):
    participants = ("6C7", *(f"p{index:02d}" for index in range(40)))
    roles = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    role_digests = []
    for role in (row for row in roles if row.kind == "candidate"):
        raw_rows = []
        contexts = {}
        for person_index, person in enumerate(role.scored_participants):
            labels = (None,) if role.inner_fold is None else (1, 1, 0)
            for row_index, label in enumerate(labels):
                candidate_id = f"{role.role_id}:{person}:{row_index}"
                component_id = f"{role.role_id}|{person}|component-{row_index}"
                start = 0
                end = 180000
                stable = f"{person}|record|session|{row_index}"
                contexts[component_id] = [ContextWindow(
                    role_id=role.role_id,
                    global_window_index=person_index * 3 + row_index,
                    stable_id=stable,
                    component_id=component_id,
                    start_ms=0,
                    end_ms=1000,
                    relative=0.5,
                )]
                feature_value = 0.9 if label == 1 or (label is None and person_index % 2 == 0) else 0.1
                raw_rows.append({
                    "role_id": role.role_id,
                    "candidate_id": candidate_id,
                    "participant_id": person,
                    "record_id": "record",
                    "session_id": "session",
                    "component_id": component_id,
                    "interval": {"start_ms": start, "end_ms": end},
                    "features": [feature_value] + [float(index) for index in range(1, 16)],
                    "support_indices": [{"participant_id": person, "record_id": "record", "session_id": "session", "row_index": row_index}],
                    "boundary_kind": "observed_window_support_component_v1",
                    "source_segment_id": None,
                    "label": label,
                })
        digest = _materialize_role(
            root,
            role,
            raw_rows,
            contexts,
            score_hash="f" * 64,
            cache_hash_digest="c" * 64,
        )
        role_digests.append(digest)
    eager_roles = {
        str(row["role_id"]): _reference_eager_role(root, row, str(row["role_id"]))
        for row in role_digests
    }
    lazy_roles = _LazyRoleCandidates(root, role_digests)
    truths = {
        person: (TruthRecord(f"gt-{person}", person, EventInterval(0, 180000)),)
        for person in participants if person != "6C7"
    }
    if perturb_outer_fold is not None:
        outer = next(role for role in roles if role.kind == "candidate" and role.inner_fold is None and role.outer_fold == perturb_outer_fold)
        for person in outer.scored_participants:
            if person != "6C7":
                truths[person] = (TruthRecord(f"gt-{person}", person, EventInterval(1_000_000, 1_180_000)),)
    old_config = expected_study_config(STUDY_002_ID)
    new_config = expected_study_config(STUDY_003_ID)
    eager = FeatureCorpus(participants, roles, eager_roles, truths, root / "eager-run", old_config)
    lazy = FeatureCorpus(participants, roles, lazy_roles, truths, root / "lazy-run", new_config)
    return eager, lazy


def _without_fit_signatures(result: dict[str, object]) -> dict[str, object]:
    normalized = json.loads(json.dumps(result))
    for row in normalized["verifier_fit_provenance"]:
        row.pop("fit_signature", None)
        row.pop("model_path", None)
    return normalized


def test_lazy_loader_matches_eager_20_plus_5_fake_backend_and_outer_truth_is_excluded(tmp_path: Path) -> None:
    eager, lazy = _synthetic_feature_corpora(tmp_path)
    eager_backend = _FakeVerifierBackend()
    lazy_backend = _FakeVerifierBackend()
    eager_result = execute_validation(eager, backend=eager_backend)
    lazy_result = execute_validation(lazy, backend=lazy_backend)

    assert len(eager_backend.fit_rows) == len(lazy_backend.fit_rows) == 25
    assert len(eager_backend.score_rows) == len(lazy_backend.score_rows) == 25
    assert eager_backend.fit_rows == lazy_backend.fit_rows
    assert eager_backend.score_rows == lazy_backend.score_rows
    assert _without_fit_signatures(eager_result) == _without_fit_signatures(lazy_result)
    eager_thresholds = (eager.output_dir / "threshold-selection.jsonl").read_bytes()
    lazy_thresholds = (lazy.output_dir / "threshold-selection.jsonl").read_bytes()
    assert eager_thresholds == lazy_thresholds
    assert (eager.output_dir / "prediction-lineage.json").read_bytes() == (lazy.output_dir / "prediction-lineage.json").read_bytes()
    assert all(row["candidate_fit_attempts"] == 0 for row in (eager_result, lazy_result))
    assert eager_result["formal_g1"] == lazy_result["formal_g1"] == "FAIL"
    assert eager_result["full_training"] == lazy_result["full_training"] == "BLOCKED"
    assert eager_result["production"] == lazy_result["production"] == "UNCHANGED"
    assert eager_result["participant_count"] == lazy_result["participant_count"] == 41
    assert "6C7" in eager_result["participant_ids"] and "6C7" in lazy_result["participant_ids"]
    assert any(
        left["fit_signature"] != right["fit_signature"]
        for left, right in zip(eager_result["verifier_fit_provenance"], lazy_result["verifier_fit_provenance"])
    )

    changed_eager, changed_lazy = _synthetic_feature_corpora(tmp_path / "outer-perturbed", perturb_outer_fold="outer-0")
    changed_result = execute_validation(changed_lazy, backend=_FakeVerifierBackend())
    original_outer = next(row for row in lazy_result["outer_results"] if row["fold_id"] == "outer-0")
    changed_outer = next(row for row in changed_result["outer_results"] if row["fold_id"] == "outer-0")
    assert original_outer["selected_threshold"] == changed_outer["selected_threshold"]
    assert original_outer["prediction_intervals"] == changed_outer["prediction_intervals"]


def test_full_scale_pure_synthetic_memory_and_disk_drill(tmp_path: Path) -> None:
    """Exercise stream/spool/materialize/lazy-load scales without A1 data or a model."""

    import platform

    from eating_event.a1.pipeline import Role
    from eating_event.a2.audit import _iter_validate_global_identity, _load_materialized_role_candidates
    from eating_event.a2.control import sample_process_tree_rss
    from eating_event.a2.inputs import sha256_file

    fixture_root = tmp_path / "synthetic-inputs"
    output = tmp_path / "synthetic-a2-003-output"
    fixture_root.mkdir()
    output.mkdir()
    identity_path = fixture_root / "window-identity.json"
    candidate_path = fixture_root / "event-candidates.jsonl"
    external_ledger = fixture_root / "a2-study-budget-v1-003.jsonl"
    external_ledger.write_bytes(b"synthetic ledger baseline\n" * 16)
    (output / "a2-study-budget.jsonl").write_bytes(external_ledger.read_bytes())
    lock_path = fixture_root / "a2-study-budget-v1-003.lock"
    lock_path.write_bytes(b"")

    participants = tuple(f"p{index:02d}" for index in range(41))
    role_graph = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=20260910)
    candidate_roles = {role.role_id: role for role in role_graph if role.kind == "candidate"}
    record_prefix = "record-" + "r" * 88
    session_prefix = "session-" + "s" * 60

    def identity_fields(index: int) -> dict[str, object]:
        record_block, row_index = divmod(index, 561)
        return {
            "participant_id": f"p{index % 41:02d}",
            "record_id": f"{record_prefix}-{record_block:04d}",
            "session_id": f"{session_prefix}-{record_block:04d}",
            "row_index": row_index,
        }

    fixture_started = time.perf_counter()
    with identity_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("[")
        for index in range(632100):
            if index:
                stream.write(",")
            stream.write(json.dumps(identity_fields(index), separators=(",", ":"), ensure_ascii=False))
        stream.write("]")

    role_ids = list(candidate_roles)
    per_role_counts = {role_id: 0 for role_id in role_ids}
    with candidate_path.open("w", encoding="utf-8", newline="\n") as stream:
        for candidate_index in range(72112):
            role_id = role_ids[candidate_index % len(role_ids)]
            role = candidate_roles[role_id]
            role_index = per_role_counts[role_id]
            per_role_counts[role_id] += 1
            association_count = 150 if candidate_index < 1012 else 149
            component_id = f"{role_id}|component-{role_index}-{association_count}"
            candidate_id = f"{role_id}:candidate-{role_index:05d}:" + "x" * 1400
            start_ms = role_index * 150000
            row = {
                "role_id": role_id,
                "candidate_id": candidate_id,
                "participant_id": participants[(candidate_index * 7) % len(participants)],
                "record_id": "candidate-record-" + "q" * 80,
                "session_id": "candidate-session-" + "z" * 60,
                "component_id": component_id,
                "interval": {"start_ms": start_ms, "end_ms": start_ms + 600000},
                "features": [float(index) for index in range(16)],
                "support_indices": [identity_fields(role_index * 150 + local_index) for local_index in range(8)],
                "boundary_kind": "observed_window_support_component_v1",
                "source_segment_id": None,
                "label": None if role.inner_fold is None else role_index % 2,
            }
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    fixture_generation_seconds = time.perf_counter() - fixture_started
    identity_input_bytes = identity_path.stat().st_size
    candidate_input_bytes = candidate_path.stat().st_size
    assert identity_input_bytes >= 147_814_536
    assert candidate_input_bytes >= 288_130_586

    stage_state = {"current": "fixture_generation", "peak_rss": 0, "by_stage": {}}
    stop_sampling = threading.Event()
    monitor_errors: list[str] = []

    def sampler() -> None:
        while not stop_sampling.wait(0.1):
            try:
                rss = sample_process_tree_rss()
                row = stage_state["by_stage"].setdefault(stage_state["current"], {"peak_rss_bytes": 0})
                row["peak_rss_bytes"] = max(int(row["peak_rss_bytes"]), rss)
                stage_state["peak_rss"] = max(int(stage_state["peak_rss"]), rss)
            except Exception as exc:  # pragma: no cover - hard failure on unsupported telemetry
                monitor_errors.append(f"{type(exc).__name__}: {exc}")
                stop_sampling.set()

    monitor = threading.Thread(target=sampler, daemon=True)
    monitor.start()
    processing_stages: list[dict[str, object]] = []
    family_peak_bytes = 0
    family_projected_peak_bytes = 0
    output_peak_bytes = 0
    predecessor_bytes = 2671 + 634 + 10250 + 2504
    external_ledger_bytes = external_ledger.stat().st_size

    def directory_bytes(path: Path) -> int:
        return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())

    def disk_guard(required_bytes: int) -> None:
        nonlocal family_projected_peak_bytes
        current = directory_bytes(output) + external_ledger_bytes + lock_path.stat().st_size + predecessor_bytes
        family_projected_peak_bytes = max(family_projected_peak_bytes, current + max(0, int(required_bytes)))
        if current + max(0, int(required_bytes)) + 4 * 1024**2 > 1024**3:
            raise AssertionError("synthetic projected family disk would exceed 1 GiB with telemetry reserve")

    def run_stage(name: str, operation):
        nonlocal family_peak_bytes, output_peak_bytes
        stage_state["current"] = name
        started = time.perf_counter()
        result = operation()
        elapsed = time.perf_counter() - started
        output_now = directory_bytes(output)
        family_now = output_now + external_ledger_bytes + lock_path.stat().st_size + predecessor_bytes
        output_peak_bytes = max(output_peak_bytes, output_now)
        family_peak_bytes = max(family_peak_bytes, family_now)
        processing_stages.append({"stage": name, "wall_seconds": elapsed, "family_bytes_after": family_now})
        return result

    processing_started = time.perf_counter()
    try:
        def build_geometry():
            geometry_rows = []
            for index in range(632100):
                identity_row = identity_fields(index)
                identity = WindowIdentity(
                    str(identity_row["participant_id"]),
                    str(identity_row["record_id"]),
                    str(identity_row["session_id"]),
                    int(identity_row["row_index"]),
                )
                geometry_rows.append(CacheGeometryRow(
                    identity=identity,
                    stable_id=identity.stable_id,
                    participant_id=identity.participant_id,
                    record_id=identity.record_id,
                    session_id=identity.session_id,
                    row_index=identity.row_index,
                    start_ms=index * 1000,
                    end_ms=index * 1000 + 500,
                    coverage=1.0,
                    crosses_gap=False,
                ))
            return geometry_rows

        geometry = run_stage("cache_geometry", build_geometry)
        global_index = run_stage("global_identity", lambda: _iter_validate_global_identity(identity_path, geometry))
        assert len(global_index) == 632100
        identity_sha = run_stage("source_identity", lambda: sha256_file(identity_path))
        spool_dir = output / "temporary" / "candidate-role-spools"
        spool_paths, candidate_ids, candidate_counts = run_stage(
            "candidate_spool",
            lambda: _spool_candidate_rows(candidate_path, candidate_roles, spool_dir, disk_guard=disk_guard),
        )
        candidate_sha = run_stage("source_identity", lambda: sha256_file(candidate_path))
        assert sum(candidate_counts.values()) == 72112 and len(candidate_ids) == 105

        def materialize_all_roles():
            digests = []
            total_associations = 0
            for role_id, role in candidate_roles.items():
                raw_rows = [json.loads(line) for line in spool_paths[role_id].read_text(encoding="utf-8").splitlines()]
                contexts = {}
                component_by_id = {}
                allowed_stable_ids = set()
                for row in raw_rows:
                    suffix = str(row["component_id"]).rsplit("|component-", 1)[1]
                    role_index_text, association_text = suffix.split("-")
                    role_index = int(role_index_text)
                    association_count = int(association_text)
                    window_start = role_index * 150
                    component = str(row["component_id"])
                    context = [
                        ContextWindow(
                            role_id,
                            global_index,
                            geometry[global_index].stable_id,
                            component,
                            geometry[global_index].start_ms,
                            geometry[global_index].end_ms,
                            0.25,
                        )
                        for global_index in range(window_start, window_start + association_count)
                    ]
                    contexts[component] = context
                    for window in context:
                        allowed_stable_ids.add(window.stable_id)
                    for support in row["support_indices"]:
                        stable = "|".join(str(support[name]) for name in ("participant_id", "record_id", "session_id", "row_index"))
                        component_by_id[stable] = component
                for row in raw_rows:
                    validate_support_identity(row, role_id=role_id, stable_ids=allowed_stable_ids, component_by_stable_id=component_by_id)
                associations = sum(len(contexts[str(row["component_id"])]) for row in raw_rows)
                total_associations += associations
                digest = _materialize_role(
                    output,
                    role,
                    raw_rows,
                    contexts,
                    score_hash="s" * 64,
                    cache_hash_digest="c" * 64,
                    disk_guard=disk_guard,
                )
                digests.append(digest)
                del raw_rows, contexts, component_by_id, allowed_stable_ids
            return digests, total_associations

        role_digests, association_count = run_stage("role_context_materialization", materialize_all_roles)
        assert association_count == 10_745_700

        def load_one_role_at_a_time():
            lazy = _LazyRoleCandidates(output, role_digests)
            loaded = 0
            keys_hash = hashlib.sha256()
            for role_id in lazy:
                rows = lazy[role_id]
                loaded += len(rows)
                for row in rows:
                    keys_hash.update(role_id.encode("utf-8"))
                    keys_hash.update(b"\0")
                    keys_hash.update(row.candidate_id.encode("utf-8"))
                    keys_hash.update(b"\n")
                del rows
            return loaded, keys_hash.hexdigest()

        loaded_count, loaded_hash = run_stage("run_role_load", load_one_role_at_a_time)
        assert loaded_count == 72112 and len(loaded_hash) == 64
        output_peak_bytes = max(output_peak_bytes, directory_bytes(output))
        family_peak_bytes = max(family_peak_bytes, output_peak_bytes + external_ledger_bytes + lock_path.stat().st_size + predecessor_bytes)
        processing_wall_seconds = time.perf_counter() - processing_started
        assert not monitor_errors
        assert int(stage_state["peak_rss"]) <= int(2.5 * 1024**3)
        assert family_peak_bytes <= 1024**3
        fixture_report = {
            "synthetic_only": True,
            "window_count": len(geometry),
            "candidate_count": sum(candidate_counts.values()),
            "candidate_role_count": len(candidate_counts),
            "role_window_score_associations": association_count,
            "identity_input_bytes": identity_input_bytes,
            "candidate_input_bytes": candidate_input_bytes,
            "input_sha256": {"window_identity": identity_sha, "event_candidates": candidate_sha},
            "support_count_per_candidate": 8,
            "support_identifier_lengths": {"record_id": len(record_prefix) + 5, "session_id": len(session_prefix) + 5},
            "candidate_id_length": 1400 + len("candidate/outer-0/outer:candidate-00000:"),
            "record_assumption": "1127 synthetic record/session blocks, each with up to 561 sequential windows",
            "association_assumption": "each candidate context references 149 scored windows; first 1,012 reference 150, totaling the design scale exactly",
            "process_tree_rss_peak_bytes": int(stage_state["peak_rss"]),
            "stage_peak_rss_bytes": {key: int(value["peak_rss_bytes"]) for key, value in stage_state["by_stage"].items()},
            "output_staging_peak_bytes": output_peak_bytes,
            "family_disk_peak_bytes_including_predecessors": family_peak_bytes,
            "family_projected_temporary_peak_bytes_including_predecessors": family_projected_peak_bytes,
            "fixture_input_total_bytes_excluded_from_family_budget": identity_input_bytes + candidate_input_bytes,
            "processing_wall_seconds": processing_wall_seconds,
            "remaining_active_budget_seconds": 7178.953,
            "fixture_generation_seconds": fixture_generation_seconds,
            "processing_stages": processing_stages,
            "candidate_role_loaded_count": loaded_count,
            "loaded_role_key_digest": loaded_hash,
            "verifier_fit_attempts": 0,
            "candidate_fit_attempts": 0,
            "candidate_predict_attempts": 0,
            "model_fit_or_predict_called": False,
            "official_or_external_data_read": False,
            "raw_sensor_touched": False,
            "predecessor_disk_bytes": predecessor_bytes,
            "output_files_bytes_exclude_fixture_sources": True,
            "screen_pass": True,
            "python_version": platform.python_version(),
        }
        spool_output = (output / "temporary").resolve()
        spool_output.relative_to(output.resolve())
        cleanup_started = time.perf_counter()
        shutil.rmtree(output)
        shutil.rmtree(fixture_root)
        fixture_report["fixture_cleanup_seconds"] = time.perf_counter() - cleanup_started
        print("A2_003_SYNTHETIC_SCALE_DRILL=" + json.dumps(fixture_report, sort_keys=True))
    finally:
        stop_sampling.set()
        monitor.join(timeout=5)
