"""In-memory synthetic expansion checks; no images, mounts or study files."""

from __future__ import annotations

from dataclasses import asdict, fields, replace
from functools import lru_cache
import hashlib
import hmac
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap.budget import (
    BudgetLimits, EnforcementReceipt, ResourceSnapshot, StageBProjection,
)
from eating_event.route2_candidate_overlap.contracts import (
    FrozenAdmission, STUDY_ID, stage_a_registry_sha256, RoleSpec, RoleInputRegistration,
    RegisteredFile, CacheFileRegistration, SCORE_MEMBERS, SCORE_PROVENANCE_FIELDS,
    CACHE_MEMBERS, CACHE_MANIFEST_FIELDS, IDENTITY_FIELDS, QUALITY_ATTESTATION_FIELDS,
    projection_scope_sha256,
)
from eating_event.route2_candidate_overlap.linux_supervisor import ImageVolumeReceipt


MODULE = "eating_event.route2_candidate_overlap.linux_volume_backend"
GIB = 1 << 30
KEY = b"synthetic-controller-key-never-used-in-production-123"
UUID = "11111111-2222-3333-4444-555555555555"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


@lru_cache(maxsize=1)
def synthetic_role_registry_bytes():
    """Full metadata schema, constructed in memory without any registered IO."""
    registrations = []
    participants = tuple(f"synthetic-p{i:02d}" for i in range(25))
    for outer in range(1, 6):
        oid = f"o{outer}"
        outer_scored = participants[(outer - 1) * 5:outer * 5]
        outer_fit = tuple(p for p in participants if p not in outer_scored)
        specs = [RoleSpec(f"candidate/{oid}/outer", oid, "outer", outer_fit, outer_scored)]
        for inner in range(1, 5):
            inner_scored = outer_fit[(inner - 1) * 5:inner * 5]
            inner_fit = tuple(p for p in outer_fit if p not in inner_scored)
            specs.append(RoleSpec(f"candidate/{oid}/i{inner}/inner", oid, "inner_heldout", inner_fit, inner_scored))
            for subinner in range(1, 5):
                sub_scored = inner_fit[subinner - 1::4]
                sub_fit = tuple(p for p in inner_fit if p not in sub_scored)
                specs.append(RoleSpec(f"candidate/{oid}/i{inner}/s{subinner}/subinner", oid,
                                      "inner_train", sub_fit, sub_scored))
        for role in specs:
            stem = hashlib.sha256(role.role_id.encode()).hexdigest()[:20]
            base = "C:\\synthetic\\role-registry\\" + stem + "\\"
            def registered(name, members, scope=""):
                return RegisteredFile(base + name, "b" * 64, members, role.role_id,
                    "synthetic-reviewed-projection" if scope else "",
                    projection_scope_sha256(scope, role.role_id, role.scored_participants, members,
                                            role_graph_sha256="a" * 64) if scope else "")
            score = registered("score.npz", SCORE_MEMBERS)
            caches = tuple(CacheFileRegistration(p, "synthetic-r", "synthetic-s", base + p + ".npz",
                             registered(p + ".npz", CACHE_MEMBERS)) for p in role.scored_participants)
            registrations.append(RoleInputRegistration(
                role, "a" * 64, score, registered("provenance.json", SCORE_PROVENANCE_FIELDS, "score_provenance"),
                score.path, caches, registered("cache-manifest.json", CACHE_MANIFEST_FIELDS, "cache_manifest_role"),
                registered("identity.json", IDENTITY_FIELDS, "role_identity"),
                registered("quality.json", QUALITY_ATTESTATION_FIELDS, "a1_quality_attestation"),
                "c" * 64, "d" * 64, 0.5,
            ))
    return canonical([asdict(reg) for reg in sorted(registrations, key=lambda reg: reg.role.role_id)])


def frozen():
    registry_hash = hashlib.sha256(synthetic_role_registry_bytes()).hexdigest()
    values = {field.name: "a" * 64 for field in fields(FrozenAdmission)}
    for name in values:
        if name.endswith("_path"):
            values[name] = "C:\\synthetic\\" + name + ".json"
    volume = "/var/lib/route2/studies/synthetic-volume"
    values.update(
        approved_write_volumes=(volume,),
        study_root_path=f"{volume}/{STUDY_ID}",
        budget_ledger_path=f"{volume}/{STUDY_ID}-budget.jsonl",
        lock_path=f"{volume}/{STUDY_ID}.lock",
        study_image_path=f"/var/lib/route2/images/{STUDY_ID}.ext4",
        budget_policy_sha256=BudgetLimits().digest(),
        source_snapshot_root="/opt/route2/synthetic/source",
        source_snapshot_manifest_path="/opt/route2/synthetic/source.manifest.json",
        runtime_snapshot_root="/opt/route2/synthetic/runtime",
        runtime_snapshot_manifest_path="/opt/route2/synthetic/runtime.manifest.json",
        approval_record="synthetic-owner-approval",
        role_input_registry_sha256=registry_hash,
        combined_input_registry_sha256=stage_a_registry_sha256(
            "a" * 64, registry_hash, "a" * 64),
    )
    return FrozenAdmission(**values)


def projection():
    outer_ids = tuple(f"o{i}" for i in range(1, 6))
    outer = tuple(f"candidate/{oid}/outer" for oid in outer_ids)
    inner = tuple((oid, tuple(f"candidate/{oid}/i{i}/inner" for i in range(1, 5)))
                  for oid in outer_ids)
    training = []
    for oid in outer_ids:
        for i in range(1, 5):
            training.append((f"verifier/{oid}/i{i}", tuple(
                f"candidate/{oid}/i{i}/s{j}/subinner"
                for j in range(1, 5))))
        training.append((f"verifier/{oid}/outer", tuple(
            f"candidate/{oid}/i{i}/inner" for i in range(1, 5))))
    graph = StageBProjection(0, 0, 0, 0, 1 << 20, "a" * 64,
                             outer, inner, tuple(training))
    events = full_stage_a_events(frozen().study_root_path, asdict(graph))
    files = [value for name, value in events if name == "treatment_role_finished"]
    return replace(graph, candidate_rows_n=105, maximum_fit_rows_m=5,
                   prediction_rows_s=25, candidate_file_bytes_b=sum(item["file_bytes"] for item in files))


def synthetic_candidate_bytes(role):
    row = dict(role_id=role, candidate_id="component|candidate-0", participant_id="synthetic-p",
               record_id="synthetic-r", session_id="synthetic-s", component_id="component",
               start_ms=0, end_ms=2, support_indices=[0], source_16d=[0.0] * 16,
               boundary_kind="observed_window_support_component_v1", source_segment_id=None)
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def full_stage_a_events(study_root, graph):
    """Synthetic producer: 105 distinct reference results then treatments.

    Byte hashes and interval fingerprints are derived from in-memory rows;
    no candidate file, image, registered input or formal namespace is opened.
    """
    roles = set(graph["outer_role_ids"])
    roles.update(role for _, values in graph["inner_role_ids_by_outer"] for role in values)
    roles.update(role for _, values in graph["fit_training_roles_by_verifier"] for role in values)
    roles = sorted(roles)
    assert len(roles) == 105
    references, treatments = [], []
    for attempt, role in enumerate(roles, 1):
        encoded = synthetic_candidate_bytes(role)
        interval = [role, "synthetic-p", "synthetic-r", "synthetic-s", "component", 0, 2]
        treatment_fingerprint = hashlib.sha256(canonical(interval) + b"\n").hexdigest()
        reference_interval = [*interval[:-1], 1] if attempt == 1 else interval
        reference_fingerprint = hashlib.sha256(canonical(reference_interval) + b"\n").hexdigest()
        stem = hashlib.sha256(role.encode()).hexdigest()[:20]
        references.extend([
            ("candidate_reconstruction_reserved", {"stage": "reference", "role_id": role, "attempt": attempt}),
            ("reference_role_passed", {"role_id": role, "candidate_count": 1,
                                        "interval_fingerprint": reference_fingerprint}),
        ])
        treatments.extend([
            ("candidate_reconstruction_reserved", {"stage": "treatment", "role_id": role, "attempt": attempt}),
            ("treatment_role_finished", {"role_id": role,
                "path": f"{study_root}/treatment-candidates/{stem}.jsonl",
                "sha256": hashlib.sha256(encoded).hexdigest(), "row_count": 1, "file_bytes": len(encoded),
                "interval_fingerprint": treatment_fingerprint,
                "interval_set_same": treatment_fingerprint == reference_fingerprint}),
        ])
    return references + treatments


def test_expansion_backend_exists():
    assert importlib.util.find_spec(MODULE) is not None, "expansion primitive is missing"


@pytest.fixture
def rig():
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend

    admission = frozen()
    current = ImageVolumeReceipt(
        "synthetic-invocation", STUDY_ID, admission.study_root_path,
        admission.budget_ledger_path, admission.lock_path, admission.study_image_path,
        150, 2049, 99, "/dev/loop7", UUID, "42", "7:7", 2 * GIB - 65536, 2 * GIB,
    )
    limits = BudgetLimits()
    config = {
        "schema": "route2_external_supervisor_config_v1", "study_id": STUDY_ID,
        "controller_key_path": "/etc/route2/synthetic.key",
        "sealed_admission_path": "/etc/route2/synthetic.seal",
        "source_snapshot_root": admission.source_snapshot_root,
        "source_manifest_path": admission.source_snapshot_manifest_path,
        "source_snapshot_sha256": admission.source_snapshot_sha256,
        "source_module_relative_path": "src/eating_event/route2_candidate_overlap/admission_bootstrap.py",
        "runtime_snapshot_root": admission.runtime_snapshot_root,
        "runtime_manifest_path": admission.runtime_snapshot_manifest_path,
        "runtime_snapshot_sha256": admission.runtime_snapshot_sha256,
        "source_mount_path": admission.source_snapshot_root,
        "runtime_mount_path": admission.runtime_snapshot_root,
        "independent_review_id": "synthetic-review", "owner_approval_id": admission.approval_record,
        "authorization_card_sha256": "b" * 64,
    }
    body = {
        "schema": "route2_controller_sealed_admission_v1", "study_id": STUDY_ID,
        "independent_review_id": "synthetic-review", "review_result": "PASS",
        "owner_approval_id": admission.approval_record, "owner_approved": True,
        "approval_scope": "A+B", "authorization_card_sha256": "b" * 64,
        "source_snapshot_sha256": admission.source_snapshot_sha256,
        "runtime_snapshot_sha256": admission.runtime_snapshot_sha256,
        "frozen_admission": asdict(admission),
    }
    snapshot = ResourceSnapshot(
        1000, 1024, 0, 10 * GIB, 1024, 9 * GIB, "5", "8:1",
        "C:\\synthetic\\wsl.vhdx", "synthetic-windows-volume", 9 * GIB,
        current.mount_id, current.filesystem_device, current.filesystem_capacity_bytes,
        UUID, current.loop_device, current.image_path, current.image_device,
        current.image_inode, current.image_length_bytes, 1024,
    )
    enforcement = EnforcementReceipt(
        "synthetic-controller", admission.resource_controller_sha256,
        current.study_root_path, current.ledger_path, current.lock_path,
        admission.approved_write_volumes, True, True, True, True, "c" * 64,
        "/system.slice/route2-synthetic.service", limits.rss_cap_bytes, 0, 2,
        limits.rss_cap_bytes // 2, 2 * GIB, 4 * GIB, "5", "synthetic-windows-volume",
        100, 110, current.created_monotonic_ns, 9 * GIB, 9 * GIB, UUID,
        current.loop_device, current.image_path, current.image_device,
        current.image_inode, current.image_length_bytes,
    )
    events = [
        ("study_created", {"study_id": STUDY_ID, "approval_record": admission.approval_record,
                           "input_registry_sha256": admission.combined_input_registry_sha256,
                           "budget_policy_sha256": limits.digest(), "limits": asdict(limits),
                           "created_wall_ns": 1}),
        ("invocation_started", {"invocation_id": current.invocation_id, "monotonic_ns": 100,
                                "controller_receipt": asdict(enforcement),
                                "startup_snapshot": asdict(snapshot),
                                "frozen_rss_ceiling_bytes": limits.rss_cap_bytes}),
        ("stage_a_finished", {"invocation_id": current.invocation_id, "reference_roles": 105,
                              "treatment_roles": 105, "different_treatment_roles": 1,
                              "stage_a_disk_bytes": 1 << 20, "finished_monotonic_ns": 200}),
        ("stage_b_entry_passed", {"invocation_id": current.invocation_id,
                                  "projection": asdict(projection())}),
    ]
    candidate_events = full_stage_a_events(current.study_root_path, asdict(projection()))
    reference_snapshot = asdict(snapshot)
    treatment_snapshot = asdict(replace(snapshot, study_disk_peak_bytes=1 << 20))
    events[2:2] = [
        ("activity_started", {"name": "stage_a_reference", "monotonic_ns": 151, "fit": False, "stage_a": True}),
        *candidate_events[:210],
        ("activity_finished", {"name": "stage_a_reference", "monotonic_ns": 154, "elapsed_ns": 4,
                               "invocation_wall_ns": 56, "fit_wall_ns": 0, "failed": False,
                               "snapshot": reference_snapshot}),
        ("activity_started", {"name": "stage_a_treatment", "monotonic_ns": 160, "fit": False, "stage_a": True}),
        *candidate_events[210:],
        ("activity_finished", {"name": "stage_a_treatment", "monotonic_ns": 180, "elapsed_ns": 25,
                               "invocation_wall_ns": 90, "fit_wall_ns": 0, "failed": False,
                               "snapshot": treatment_snapshot}),
    ]

    class FakeOS(backend.LinuxVolumeOSPorts):
        def __init__(self):
            self.events = events
            self.body = body
            self.protected = {str(backend.DEFAULT_SUPERVISOR_CONFIG): canonical(config),
                              config["controller_key_path"]: KEY}
            self.trace = []
            self.fds = {}
            self.next_fd = 10
            self.image_length = 2 * GIB
            self.loop_capacity = 2 * GIB
            self.capacity = current.filesystem_capacity_bytes
            self.uuid = UUID
            self.mount_id = "42"
            self.image_inode = 99
            self.loop_inode = 77
            self.loop_backing_inode = 99
            self.offset = self.sizelimit = self.flags = 0
            self.pids = (123,)
            self.live_cgroup = enforcement.parent_cgroup_path
            self.cgroup_inode = 901
            self.cgroup_device = 29
            self.gt_mount = False
            self.attempts = set()
            self.failure = None
            self.after_mutation = None
            self.now = 300
            self.raw_ledger = None
            self.root_denied = False
            self.artifacts = {}
            self.fd_artifacts = {}
            self.offsets = {}
            self.closed = set()
            for index, (name, payload) in enumerate(self.events):
                if name == "treatment_role_finished":
                    self.artifacts[payload["path"]] = SimpleNamespace(
                        data=synthetic_candidate_bytes(payload["role_id"]),
                        info=SimpleNamespace(st_dev=0x707, st_ino=1000 + index, st_mode=stat.S_IFREG | 0o600,
                                             st_uid=0, st_nlink=1, st_mtime_ns=1, st_ctime_ns=1, st_rdev=0))

        def seal(self):
            return canonical({"body": self.body, "controller_hmac_sha256": hmac.new(
                KEY, canonical(self.body), hashlib.sha256).hexdigest()})

        def ledger(self):
            if self.raw_ledger is not None:
                return self.raw_ledger
            tail = "0" * 64
            records = []
            for seq, (event, payload) in enumerate(self.events):
                entry = {"seq": seq, "event": event, "payload": payload,
                         "previous_sha256": tail}
                tail = hashlib.sha256(canonical(entry)).hexdigest()
                records.append(canonical({"entry": entry, "sha256": tail}) + b"\n")
            return b"".join(records)

        @property
        def gate_hash(self):
            return json.loads(self.ledger().splitlines()[-1])["sha256"]

        def require_linux_root(self):
            self.trace.append("root")
            if self.root_denied:
                raise PermissionError("synthetic platform denied")

        def read_protected_file(self, path, *, max_bytes):
            self.trace.append(("protected", str(path)))
            data = self.seal() if str(path) == config["sealed_admission_path"] else self.protected[str(path)]
            if type(data) is bytes and len(data) > max_bytes:
                raise PermissionError("synthetic protected size bound")
            return data

        def open_existing(self, path, *, kind, writable=False):
            self.trace.append(("open", path, kind, writable))
            fd = self.next_fd
            self.next_fd += 1
            self.fds[fd] = (path, kind, self.path_stat(path, kind=kind))
            if path in self.artifacts:
                self.fd_artifacts[fd] = self.artifacts[path]
                self.offsets[fd] = 0
            return fd

        def path_stat(self, path, *, kind):
            if "/treatment-candidates/" in path:
                artifact = self.artifacts[path]
                return SimpleNamespace(**vars(artifact.info), st_size=len(artifact.data))
            if path.startswith("/sys/fs/cgroup/"):
                dev, ino, size = self.cgroup_device, self.cgroup_inode, 0
            elif path == current.image_path:
                dev, ino, size = 2049, self.image_inode, self.image_length
            elif path == current.loop_device:
                dev, ino, size = 6, self.loop_inode, 0
            elif path == current.ledger_path:
                dev, ino, size = 0x707, 81, len(self.ledger())
            elif path == current.lock_path:
                dev, ino, size = 0x707, 82, 2
            else:
                dev, ino, size = 0x707, 83 if path == current.study_root_path else 84, 0
            modes = {"file": stat.S_IFREG | 0o600, "directory": stat.S_IFDIR | 0o700,
                     "block": stat.S_IFBLK | 0o600}
            return SimpleNamespace(st_dev=dev, st_ino=ino, st_size=size, st_mode=modes[kind],
                                   st_uid=0, st_nlink=1, st_mtime_ns=1, st_ctime_ns=1, st_rdev=0x707)

        def fstat(self, fd):
            if fd in self.fd_artifacts:
                artifact = self.fd_artifacts[fd]
                return SimpleNamespace(**vars(artifact.info), st_size=len(artifact.data))
            path, kind, opened = self.fds[fd]
            now_stat = self.path_stat(path, kind=kind)
            return SimpleNamespace(**{**vars(now_stat), "st_ino": opened.st_ino})

        def read_fd(self, fd, *, max_bytes):
            assert self.fds[fd][0] == current.ledger_path
            value = self.ledger()
            if len(value) > max_bytes:
                raise PermissionError("synthetic ledger bound")
            return value

        def lock_exclusive(self, fd):
            self.trace.append(("flock", fd))

        def rewind_fd(self, fd):
            self.offsets[fd] = 0
            self.trace.append(("rewind", fd))

        def read_chunk(self, fd, *, max_bytes):
            assert 0 < max_bytes <= 65536
            self.trace.append(("read_chunk", fd, max_bytes))
            start = self.offsets[fd]
            data = self.fd_artifacts[fd].data[start:start + max_bytes]
            self.offsets[fd] += len(data)
            return data

        def close(self, fd):
            self.trace.append(("close", fd))
            self.closed.add(fd)

        def fsync(self, fd):
            self.trace.append(("fsync", self.fds[fd][0]))
            self.maybe_fail("fsync")

        def fsync_parent(self, path):
            self.trace.append(("directory_fsync", path))

        def mountinfo(self):
            volume = admission.approved_write_volumes[0]
            text = f"{self.mount_id} 1 7:7 / {volume} rw,nosuid,nodev,noexec - ext4 {current.loop_device} rw\n"
            if self.gt_mount:
                text += "55 1 8:1 / /run/route2-input/gt.json ro - ext4 /dev/synthetic ro\n"
            return text

        def filesystem_capacity(self, fd):
            return self.capacity

        def loop_state(self, fd):
            return backend.LoopState(2049, self.loop_backing_inode, 7, self.offset,
                                     self.sizelimit, self.flags, self.loop_capacity)

        def filesystem_uuid(self, fd):
            return self.uuid

        def cgroup_members(self, path):
            assert path == enforcement.parent_cgroup_path
            return self.pids

        def _kernel_text(self, path):
            assert path.as_posix() == "/proc/self/cgroup"
            return "0::" + self.live_cgroup + "\n"

        def pid(self):
            return 123

        def monotonic_ns(self):
            self.now += 1
            return self.now

        def reserve_attempt(self, encoded, *, forbidden_device):
            assert forbidden_device == 0x707
            if STUDY_ID in self.attempts:
                raise FileExistsError("synthetic attempt already reserved")
            self.attempts.add(STUDY_ID)
            self.trace.append(("attempt_fsynced", json.loads(encoded)))
            self.maybe_fail("attempt")

        def maybe_fail(self, phase):
            if self.failure == phase:
                raise OSError("synthetic " + phase + " failure")

        def truncate(self, fd, size):
            self.trace.append(("truncate", fd, size))
            self.image_length = size
            if self.after_mutation:
                self.after_mutation("truncate")
            self.maybe_fail("truncate")

        def refresh_capacity(self, fd):
            self.trace.append(("refresh", fd))
            self.loop_capacity = self.image_length
            if self.after_mutation:
                self.after_mutation("refresh")
            self.maybe_fail("refresh")

        def command(self, argv, *, pass_fds, timeout):
            self.trace.append(("command", argv, pass_fds, timeout))
            assert argv == ("/usr/sbin/resize2fs", f"/proc/self/fd/{pass_fds[0]}", "4G")
            if self.failure == "timeout":
                raise subprocess.TimeoutExpired(argv, timeout)
            self.maybe_fail("resize")
            self.capacity = 4 * GIB - 131072
            if self.after_mutation:
                self.after_mutation("resize")
            return "synthetic resized"

    ports = FakeOS()
    registry_bytes = synthetic_role_registry_bytes()
    return SimpleNamespace(backend=backend, ports=ports, current=current, limits=limits,
                           registry_bytes=registry_bytes,
                           expander=backend.LinuxLoopVolumeExpander(ports=ports, role_registry_bytes=registry_bytes))


def expand(rig, **changes):
    args = dict(invocation_id=rig.current.invocation_id, current=rig.current,
                event_sha256=rig.ports.gate_hash, limits=rig.limits)
    args.update(changes)
    return rig.expander.expand_same_volume(**args)


def mutations(ports):
    return [item for item in ports.trace if isinstance(item, tuple)
            and item[0] in {"attempt_fsynced", "truncate", "refresh", "command"}]


def test_fixed_growth_preserves_identity_and_fsync_precedes_mutation(rig):
    result = expand(rig)
    assert type(result) is ImageVolumeReceipt
    assert replace(result, created_monotonic_ns=rig.current.created_monotonic_ns,
                   filesystem_capacity_bytes=rig.current.filesystem_capacity_bytes,
                   image_length_bytes=rig.current.image_length_bytes) == rig.current
    assert result.image_length_bytes == 4 * GIB
    assert 2 * GIB < result.filesystem_capacity_bytes <= 4 * GIB
    actions = [item[0] for item in mutations(rig.ports)]
    assert actions == ["attempt_fsynced", "truncate", "refresh", "command"]
    gate_sync = rig.ports.trace.index(("fsync", rig.current.ledger_path))
    first_mutation = next(i for i, item in enumerate(rig.ports.trace)
                          if isinstance(item, tuple) and item[0] == "attempt_fsynced")
    assert gate_sync < first_mutation
    assert rig.expander.entry_receipt.event_sha256 == rig.ports.gate_hash
    assert result.created_monotonic_ns > rig.expander.entry_receipt.fsynced_monotonic_ns
    command = next(item for item in mutations(rig.ports) if item[0] == "command")
    assert 0 < command[3] <= 60


@pytest.mark.parametrize("value", [True, {}, SimpleNamespace(approved=True), frozen()])
def test_unverified_approval_shapes_are_denied_before_os_probes(rig, value):
    key = next(path for path in rig.ports.protected if path.endswith("supervisor.json"))
    rig.ports.protected[key] = value
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)
    assert not any(isinstance(item, tuple) and item[0] == "open" for item in rig.ports.trace)


@pytest.mark.parametrize("field,value", [("owner_approved", False), ("owner_approved", 1),
    ("review_result", "FAIL"), ("approval_scope", "Stage A-only"),
    ("owner_approval_id", "other-owner"), ("authorization_card_sha256", "0" * 64)])
def test_valid_hmac_cannot_override_review_or_owner_pins(rig, field, value):
    rig.ports.body[field] = value
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("variant", ["truncated", "digest", "predecessor", "sequence", "noncanonical"])
def test_corrupt_durable_chain_is_denied(rig, variant):
    raw = rig.ports.ledger()
    if variant == "truncated":
        raw = raw[:-1]
    elif variant == "noncanonical":
        raw = b" " + raw
    else:
        records = [json.loads(line) for line in raw.splitlines()]
        if variant == "digest":
            records[1]["sha256"] = "0" * 64
        elif variant == "predecessor":
            records[1]["entry"]["previous_sha256"] = "1" * 64
        else:
            records[1]["entry"]["seq"] = True
        raw = b"".join(canonical(record) + b"\n" for record in records)
    rig.ports.raw_ledger = raw
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("change", ["hash", "invocation", "duplicate", "terminal", "no-boundary",
    "identical", "disk", "rss", "role-graph", "active-gt", "worker", "active-activity", "failed-activity"])
def test_unmet_gate_is_denied_before_attempt_or_volume_write(rig, change):
    kwargs = {}
    if change == "hash":
        kwargs["event_sha256"] = "0" * 64
    elif change == "invocation":
        kwargs["invocation_id"] = "other-invocation"
    elif change == "duplicate":
        rig.ports.events.insert(3, rig.ports.events[-1])
    elif change == "terminal":
        rig.ports.events.append(("terminal", {}))
    elif change == "no-boundary":
        rig.ports.events.pop(next(i for i, (name, _) in enumerate(rig.ports.events) if name == "stage_a_finished"))
    elif change == "identical":
        next(value for name, value in rig.ports.events if name == "stage_a_finished")["different_treatment_roles"] = 0
    elif change in {"disk", "rss", "role-graph"}:
        p = rig.ports.events[-1][1]["projection"]
        p[{"disk": "candidate_file_bytes_b", "rss": "maximum_fit_rows_m",
           "role-graph": "role_graph_sha256"}[change]] = "b" * 64 if change == "role-graph" else 4 * GIB
    elif change == "active-gt":
        rig.ports.gt_mount = True
    elif change == "worker":
        rig.ports.pids = (123, 456)
    else:
        rig.ports.events.insert(2, ("activity_started", {"name": "synthetic", "monotonic_ns": 160,
                                                       "fit": False, "stage_a": True}))
        if change == "failed-activity":
            rig.ports.events.insert(3, ("activity_finished", {"name": "synthetic", "failed": True}))
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig, **kwargs)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("change", ["limits", "capacity", "inode", "backing", "offset",
    "sizelimit", "readonly", "uuid", "mount", "loop-capacity", "image-size", "current-type"])
def test_identity_or_fixed_policy_mismatch_denied_before_mutation(rig, change):
    kwargs = {}
    if change == "limits":
        kwargs["limits"] = replace(rig.limits, total_disk_bytes=5 * GIB)
    elif change == "current-type":
        kwargs["current"] = SimpleNamespace(**asdict(rig.current))
    else:
        field, value = {"capacity": ("capacity", 2 * GIB + 1), "inode": ("image_inode", 98),
            "backing": ("loop_backing_inode", 98), "offset": ("offset", 1024),
            "sizelimit": ("sizelimit", 2 * GIB), "readonly": ("flags", 1),
            "uuid": ("uuid", "aaaaaaaa-2222-3333-4444-555555555555"),
            "mount": ("mount_id", "43"), "loop-capacity": ("loop_capacity", 3 * GIB),
            "image-size": ("image_length", 3 * GIB)}[change]
        setattr(rig.ports, field, value)
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig, **kwargs)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("phase", ["attempt", "truncate", "refresh", "resize", "timeout"])
def test_partial_failure_forbids_retry_even_new_backend_instance(rig, phase):
    rig.ports.failure = phase
    with pytest.raises((OSError, subprocess.TimeoutExpired)):
        expand(rig)
    count = len(mutations(rig.ports))
    rig.ports.failure = None
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig)
    assert len(mutations(rig.ports)) == count
    rig.expander = rig.backend.LinuxLoopVolumeExpander(ports=rig.ports, role_registry_bytes=rig.registry_bytes)
    with pytest.raises((PermissionError, RuntimeError, FileExistsError)):
        expand(rig)
    assert len(mutations(rig.ports)) == count


@pytest.mark.parametrize("phase,attribute,value", [
    ("truncate", "image_inode", 100), ("truncate", "loop_inode", 100),
    ("refresh", "loop_backing_inode", 100), ("refresh", "uuid", "bad-uuid"),
    ("resize", "mount_id", "43"), ("resize", "capacity", 5 * GIB),
    ("resize", "capacity", 2 * GIB), ("resize", "uuid", "bad-uuid"),
])
def test_changed_identity_after_mutation_stops_without_retry(rig, phase, attribute, value):
    rig.ports.after_mutation = lambda actual: setattr(rig.ports, attribute, value) if actual == phase else None
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig)
    count = len(mutations(rig.ports))
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig)
    assert len(mutations(rig.ports)) == count
    if phase != "resize":
        assert not any(item[0] == "command" for item in mutations(rig.ports))


def test_gate_fsync_failure_never_attempts_expansion(rig):
    rig.ports.failure = "fsync"
    with pytest.raises(OSError):
        expand(rig)
    assert not mutations(rig.ports)


def test_expired_entry_denied_before_mutation(rig):
    rig.ports.now = 100 + rig.limits.stage_a_wall_ns
    with pytest.raises((PermissionError, RuntimeError)):
        expand(rig)
    assert not mutations(rig.ports)


def test_production_command_port_uses_argv_no_shell_and_bounded_timeout(monkeypatch):
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "synthetic", "")

    monkeypatch.setattr(backend.subprocess, "run", fake_run)
    backend.LinuxVolumeOSPorts().command(
        ("/usr/sbin/resize2fs", "/proc/self/fd/12", "4G"), pass_fds=(12,), timeout=30)
    argv, options = calls[0]
    assert isinstance(argv, tuple) and options["shell"] is False
    assert options["timeout"] == 30 and options["check"] is True
    assert options["pass_fds"] == (12,) and options["stdin"] == subprocess.DEVNULL
    assert options["env"] == {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}


def test_production_truncate_port_calls_only_fixed_ftruncate(monkeypatch):
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend
    calls = []
    monkeypatch.setattr(backend.os, "ftruncate", lambda fd, size: calls.append((fd, size)))
    ports = backend.LinuxVolumeOSPorts()
    ports.truncate(12, 4 * GIB)
    with pytest.raises((PermissionError, ValueError)):
        ports.truncate(12, 5 * GIB)
    assert calls == [(12, 4 * GIB)]


def test_default_production_backend_denies_non_linux_before_any_file_or_command(monkeypatch):
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend
    monkeypatch.setattr(backend.platform, "system", lambda: "Windows")
    monkeypatch.setattr(backend, "_read_protected_file", lambda *_args, **_kwargs:
                        pytest.fail("production denial must precede protected-file access"))
    monkeypatch.setattr(backend.subprocess, "run", lambda *_args, **_kwargs:
                        pytest.fail("production command must never execute"))
    with pytest.raises(PermissionError, match="Linux root"):
        backend.LinuxLoopVolumeExpander().expand_same_volume("synthetic", None, "a" * 64, BudgetLimits())


def test_forged_seal_with_wrong_key_denied_before_volume_open(rig):
    key_path = next(path for path in rig.ports.protected if path.endswith(".key"))
    rig.ports.protected[key_path] = b"wrong-synthetic-key-xxxxxxxxxxxxxxxxxxxxxxxx"
    with pytest.raises(PermissionError, match="authenticate"):
        expand(rig)
    assert not mutations(rig.ports)
    assert not any(isinstance(item, tuple) and item[0] == "open" for item in rig.ports.trace)


@pytest.mark.parametrize("attribute,value", [("st_uid", 1000), ("st_mode", stat.S_IFLNK | 0o600),
    ("st_mode", stat.S_IFREG | 0o660), ("st_nlink", 2)])
def test_unprotected_or_linked_image_is_denied_before_mutation(rig, attribute, value):
    original = rig.ports.path_stat

    def altered(path, *, kind):
        info = original(path, kind=kind)
        if path == rig.current.image_path:
            setattr(info, attribute, value)
        return info

    rig.ports.path_stat = altered
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_production_loop_ports_decode_kernel_status_and_refresh_exact_open_fd(monkeypatch):
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend
    calls = []

    def ioctl(fd, request, value):
        calls.append((fd, request))
        if request == backend.LOOP_GET_STATUS64:
            return struct.pack("=5Q4I64s64s32s2Q", 2049, 99, 0, 0, 0, 7, 0, 0, 16,
                               b"", b"", b"", 0, 0)
        if request == backend.BLKGETSIZE64:
            return struct.pack("=Q", 2 * GIB)
        assert request == backend.LOOP_SET_CAPACITY and value == 0
        return 0

    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(ioctl=ioctl))
    ports = backend.LinuxVolumeOSPorts()
    assert ports.loop_state(12) == backend.LoopState(2049, 99, 7, 0, 0, 16, 2 * GIB)
    ports.refresh_capacity(12)
    assert calls == [(12, backend.LOOP_GET_STATUS64), (12, backend.BLKGETSIZE64),
                     (12, backend.LOOP_SET_CAPACITY)]


def test_production_uuid_reader_uses_bounded_superblock_pread(monkeypatch):
    from eating_event.route2_candidate_overlap import linux_volume_backend as backend
    import uuid
    superblock = bytearray(1024)
    struct.pack_into("<H", superblock, 56, 0xEF53)
    superblock[104:120] = uuid.UUID(UUID).bytes
    calls = []

    def pread(fd, length, offset):
        calls.append((fd, length, offset))
        return bytes(superblock)

    monkeypatch.setattr(backend.os, "pread", pread, raising=False)
    ports = backend.LinuxVolumeOSPorts()
    assert ports.filesystem_uuid(12) == UUID
    superblock[56] = 0
    with pytest.raises(PermissionError):
        ports.filesystem_uuid(12)
    assert calls == [(12, 1024, 1024), (12, 1024, 1024)]


@pytest.mark.parametrize("change", ["approval", "ledger", "worker"])
def test_gate_change_after_attempt_stops_before_truncate(rig, change):
    reserve = rig.ports.reserve_attempt

    def altered_reservation(encoded, *, forbidden_device):
        reserve(encoded, forbidden_device=forbidden_device)
        if change == "approval":
            rig.ports.body["owner_approved"] = False
        elif change == "ledger":
            rig.ports.events.append(("activity_started", {"name": "late-worker"}))
        else:
            rig.ports.pids = (123, 456)

    rig.ports.reserve_attempt = altered_reservation
    with pytest.raises(PermissionError):
        expand(rig)
    assert [item[0] for item in mutations(rig.ports)] == ["attempt_fsynced"]


def test_authenticated_uppercase_digest_pins_match_the_same_bytes(rig):
    for name in ("budget_policy_sha256", "resource_controller_sha256", "role_graph_sha256", "role_input_registry_sha256",
                 "combined_input_registry_sha256"):
        pins = rig.ports.body["frozen_admission"]
        pins[name] = pins[name].upper()
    result = expand(rig)
    assert result.image_length_bytes == 4 * GIB
