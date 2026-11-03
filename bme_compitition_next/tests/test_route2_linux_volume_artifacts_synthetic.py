"""Candidate-byte verification using in-memory FDs only; no project inputs."""

from copy import deepcopy
import hashlib
import importlib.util
import stat
from dataclasses import replace
from types import SimpleNamespace

import pytest

from test_route2_linux_volume_backend_synthetic import rig, expand, mutations  # noqa: F401


MODULE = "eating_event.route2_candidate_overlap.linux_volume_artifacts"


def first(rig):
    path = next(iter(rig.ports.artifacts))
    return path, rig.ports.artifacts[path]


def bind_new_hash(rig, path):
    payload = next(value for name, value in rig.ports.events
                   if name == "treatment_role_finished" and value["path"] == path)
    payload["sha256"] = hashlib.sha256(rig.ports.artifacts[path].data).hexdigest()


def flip(artifact):
    artifact.data = b"x" + artifact.data[1:]


def replaced(rig, path):
    artifact = deepcopy(rig.ports.artifacts[path])
    artifact.info.st_ino += 5000
    rig.ports.artifacts[path] = artifact


def test_specific_artifact_verifier_exists():
    assert importlib.util.find_spec(MODULE) is not None


def test_changed_candidate_bytes_deny_before_attempt_or_growth(rig):
    _, artifact = first(rig)
    flip(artifact)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_missing_candidate_denies_before_attempt(rig):
    path, _ = first(rig)
    del rig.ports.artifacts[path]
    with pytest.raises((PermissionError, KeyError, FileNotFoundError)):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("field,value", [
    ("st_uid", 1000), ("st_nlink", 2), ("st_dev", 999),
    ("st_mode", stat.S_IFIFO | 0o600), ("st_mode", stat.S_IFREG | 0o660),
    ("st_mode", stat.S_IFREG | 0o644), ("st_ino", 0),
    ("st_mtime_ns", True), ("st_ctime_ns", 1.0),
])
def test_artifact_stat_is_exact_protected_and_on_volume(rig, field, value):
    _, artifact = first(rig)
    setattr(artifact.info, field, value)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("variant", ["short", "long", "partial", "rows"])
def test_size_line_count_and_final_newline_are_independent_of_hash(rig, variant):
    path, artifact = first(rig)
    if variant == "short":
        artifact.data = artifact.data[:-1]
    elif variant == "long":
        artifact.data += b"\n"
    elif variant == "partial":
        artifact.data = artifact.data[:-1] + b"x"
        bind_new_hash(rig, path)
    else:
        artifact.data = b"\n" + artifact.data[1:]
        bind_new_hash(rig, path)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_all_105_descriptors_locked_and_held_through_growth(rig):
    reserve = rig.ports.reserve_attempt

    def held(encoded, *, forbidden_device):
        artifact_fds = set(rig.ports.fd_artifacts)
        assert len(artifact_fds) == 105
        assert not artifact_fds & rig.ports.closed
        assert artifact_fds <= {item[1] for item in rig.ports.trace
                                if isinstance(item, tuple) and item[0] == "flock"}
        reserve(encoded, forbidden_device=forbidden_device)
    rig.ports.reserve_attempt = held
    expand(rig)
    assert len(rig.ports.fd_artifacts) == 105
    assert set(rig.ports.fd_artifacts) <= rig.ports.closed
    for fd in rig.ports.fd_artifacts:
        # Initial verification plus every volume checkpoint rehashes from byte 0.
        assert rig.ports.trace.count(("rewind", fd)) >= 8


@pytest.mark.parametrize("phase,expected", [
    ("attempt", ["attempt_fsynced"]),
    ("truncate", ["attempt_fsynced", "truncate"]),
    ("refresh", ["attempt_fsynced", "truncate", "refresh"]),
    ("resize", ["attempt_fsynced", "truncate", "refresh", "command"]),
])
@pytest.mark.parametrize("change", ["bytes", "replace", "mtime", "ctime", "size"])
def test_artifact_change_at_every_mutation_checkpoint_fails_closed(rig, phase, expected, change):
    path, artifact = first(rig)

    def alter(at):
        if at != phase:
            return
        if change == "bytes":
            flip(artifact)  # Stat remains identical: every checkpoint must rehash.
        elif change == "replace":
            replaced(rig, path)
        elif change == "size":
            artifact.data += b"x"
        else:
            setattr(artifact.info, "st_" + change + "_ns", 2)
    rig.ports.after_mutation = alter
    reserve = rig.ports.reserve_attempt

    def reserved(encoded, *, forbidden_device):
        reserve(encoded, forbidden_device=forbidden_device)
        alter("attempt")
    rig.ports.reserve_attempt = reserved
    with pytest.raises(PermissionError):
        expand(rig)
    assert [item[0] for item in mutations(rig.ports)] == expected
    assert set(rig.ports.fd_artifacts) <= rig.ports.closed
    with pytest.raises(PermissionError, match="one-shot"):
        expand(rig)


@pytest.mark.parametrize("change", ["bytes", "replace"])
def test_changed_artifact_during_gate_fsync_prevents_attempt(rig, change):
    path, artifact = first(rig)
    sync = rig.ports.fsync

    def changed(fd):
        sync(fd)
        if rig.ports.fds[fd][0] == rig.current.ledger_path:
            flip(artifact) if change == "bytes" else replaced(rig, path)
    rig.ports.fsync = changed
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("change", ["replace", "mtime", "ctime"])
def test_change_during_same_fd_stream_is_detected(rig, change):
    path, artifact = first(rig)
    read = rig.ports.read_chunk
    changed = False

    def unstable(fd, *, max_bytes):
        nonlocal changed
        data = read(fd, max_bytes=max_bytes)
        if rig.ports.fds[fd][0] == path and not changed:
            changed = True
            if change == "replace":
                replaced(rig, path)
            else:
                setattr(artifact.info, "st_" + change + "_ns", 2)
        return data
    rig.ports.read_chunk = unstable
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_failed_open_closes_every_previously_held_artifact(rig):
    opening = rig.ports.open_existing
    count = 0

    def failed(path, *, kind, writable=False):
        nonlocal count
        if "/treatment-candidates/" in path:
            count += 1
            if count == 30:
                raise PermissionError("synthetic protected walk failure")
        return opening(path, kind=kind, writable=writable)
    rig.ports.open_existing = failed
    with pytest.raises(PermissionError):
        expand(rig)
    assert len(rig.ports.fd_artifacts) == 29
    assert set(rig.ports.fd_artifacts) <= rig.ports.closed
    assert not mutations(rig.ports)


def test_all_candidate_opens_are_readonly_and_exact_receipt_paths(rig):
    expand(rig)
    paths = {value["path"] for name, value in rig.ports.events if name == "treatment_role_finished"}
    opens = [item for item in rig.ports.trace if isinstance(item, tuple)
             and item[0] == "open" and "/treatment-candidates/" in item[1]]
    assert {item[1] for item in opens} == paths
    assert all(item[2:] == ("file", False) for item in opens)


def test_stream_overread_is_rejected_without_reservation(rig):
    read = rig.ports.read_chunk
    rig.ports.read_chunk = lambda fd, *, max_bytes: read(fd, max_bytes=max_bytes) + b"x" * (max_bytes + 1)
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_worker_start_during_last_pre_attempt_hash_denies_before_reservation(rig):
    path, _ = first(rig)
    read = rig.ports.read_chunk

    def worker_started(fd, *, max_bytes):
        data = read(fd, max_bytes=max_bytes)
        if rig.ports.fds[fd][0] == path and rig.ports.trace.count(("rewind", fd)) == 4:
            rig.ports.pids = (123, 456)
        return data
    rig.ports.read_chunk = worker_started
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_large_file_streams_in_bounded_blocks_across_newline_boundary(rig):
    path, artifact = first(rig)
    original_size = len(artifact.data)
    artifact.data = b"x" * (65536 * 2 + 13) + b"\n"
    payload = next(value for name, value in rig.ports.events
                   if name == "treatment_role_finished" and value["path"] == path)
    payload["file_bytes"] = len(artifact.data)
    bind_new_hash(rig, path)
    rig.ports.events[-1][1]["projection"]["candidate_file_bytes_b"] += len(artifact.data) - original_size
    expand(rig)
    fd = next(fd for fd, item in rig.ports.fds.items() if item[0] == path)
    reads = [item[2] for item in rig.ports.trace if isinstance(item, tuple)
             and item[:2] == ("read_chunk", fd)]
    assert reads[:4] == [65536, 65536, 14, 1]


def test_zero_byte_output_requires_empty_hash_and_zero_lines(rig):
    from eating_event.route2_candidate_overlap.linux_volume_artifacts import HeldTreatmentArtifacts
    _, _, _, replay = rig.expander._gate(rig.ports.ledger(), rig.ports.gate_hash,
                                        rig.current, rig.limits, rig.expander._admission()[0])
    original = replay.treatment_files[0]
    empty = replace(original, file_bytes=0, row_count=0, sha256=hashlib.sha256(b"").hexdigest())
    replay = replace(replay, treatment_files=(empty, *replay.treatment_files[1:]),
                     candidate_file_bytes_b=replay.candidate_file_bytes_b - original.file_bytes)
    rig.ports.artifacts[empty.path].data = b""
    held = HeldTreatmentArtifacts(rig.ports, replay, volume_device=0x707,
                                  deadline_ns=10**12, not_before_ns=200)
    try:
        held.open_and_verify()
        held.checkpoint()
    finally:
        held.close()
    assert set(rig.ports.fd_artifacts) <= rig.ports.closed


def test_stream_short_reads_can_split_every_newline(rig):
    read = rig.ports.read_chunk
    rig.ports.read_chunk = lambda fd, *, max_bytes: read(fd, max_bytes=min(17, max_bytes))
    expand(rig)


@pytest.mark.parametrize("variant", ["early_eof", "extra_eof", "wrong_type"])
def test_bounded_stream_protocol_errors_stop_before_attempt(rig, variant):
    read = rig.ports.read_chunk

    def bad_read(fd, *, max_bytes):
        data = read(fd, max_bytes=max_bytes)
        if variant == "early_eof":
            return b""
        if variant == "extra_eof" and not data:
            return b"x"
        return bytearray(data) if variant == "wrong_type" else data
    rig.ports.read_chunk = bad_read
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("phase", ["initial", "checkpoint"])
def test_whole_set_fence_detects_earlier_file_change_during_later_read(rig, phase):
    first_path, artifact = first(rig)
    last_path = list(rig.ports.artifacts)[-1]
    read = rig.ports.read_chunk
    target = 1 if phase == "initial" else 2

    def earlier_changed(fd, *, max_bytes):
        data = read(fd, max_bytes=max_bytes)
        if rig.ports.fds[fd][0] == last_path and rig.ports.trace.count(("rewind", fd)) == target:
            artifact.info.st_ctime_ns += 1
        return data
    rig.ports.read_chunk = earlier_changed
    with pytest.raises(PermissionError):
        expand(rig)
    assert not mutations(rig.ports)


def test_deadline_overshoot_inside_artifact_stream_prevents_reservation(rig):
    read = rig.ports.read_chunk

    def expired(fd, *, max_bytes):
        data = read(fd, max_bytes=max_bytes)
        rig.ports.now = 100 + rig.limits.total_wall_ns
        return data
    rig.ports.read_chunk = expired
    with pytest.raises(PermissionError, match="deadline"):
        expand(rig)
    assert not mutations(rig.ports)


@pytest.mark.parametrize("limit", [0, -1, True, 1.0, 65537])
def test_concrete_stream_port_rejects_unbounded_reads_before_syscall(rig, monkeypatch, limit):
    def forbidden(*args):
        pytest.fail("invalid streaming size reached a syscall")
    monkeypatch.setattr(rig.backend.os, "read", forbidden)
    with pytest.raises(PermissionError):
        rig.backend.LinuxVolumeOSPorts().read_chunk(999, max_bytes=limit)


def test_concrete_stream_port_uses_only_bounded_read_and_rewind_syscalls(rig, monkeypatch):
    trace = []
    monkeypatch.setattr(rig.backend.os, "read", lambda fd, size: trace.append(("read", fd, size)) or b"bytes")
    monkeypatch.setattr(rig.backend.os, "lseek", lambda fd, offset, whence:
                        trace.append(("rewind", fd, offset, whence)) or 0)
    ports = rig.backend.LinuxVolumeOSPorts()
    ports.rewind_fd(999)
    assert ports.read_chunk(999, max_bytes=65536) == b"bytes"
    assert trace == [("rewind", 999, 0, rig.backend.os.SEEK_SET), ("read", 999, 65536)]


@pytest.mark.parametrize("target", ["loop", "image", "ledger"])
def test_close_error_after_release_still_closes_all_remaining_fds_once(rig, target):
    paths = {"loop": rig.current.loop_device, "image": rig.current.image_path,
             "ledger": rig.current.ledger_path}
    close = rig.ports.close
    failed = []

    def released_then_failed(fd):
        close(fd)
        matching = [number for number, (path, _, _) in rig.ports.fds.items() if path == paths[target]]
        if fd == max(matching) and not failed:
            failed.append(fd)
            raise OSError("synthetic close failed after FD release")
    rig.ports.close = released_then_failed
    with pytest.raises(OSError, match="after FD release"):
        expand(rig)
    assert failed
    assert set(rig.ports.fds) <= rig.ports.closed
    assert all(rig.ports.trace.count(("close", fd)) == 1 for fd in rig.ports.fds)
    with pytest.raises(PermissionError, match="one-shot"):
        expand(rig)
