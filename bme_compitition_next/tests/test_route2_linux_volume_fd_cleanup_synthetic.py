"""Concrete-port FD ownership regressions; every syscall is mocked."""

from collections import Counter
import stat
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap import linux_volume_backend as backend


@pytest.fixture
def syscalls(monkeypatch):
    ports = backend.LinuxVolumeOSPorts()
    trace, active, opened, closed = [], set(), set(), []
    state = SimpleNamespace(next_fd=10, close_failures=set(), stat_failure=None,
                            open_failure=None, sync_failure=None, wrong_file=False)
    for name, value in (("O_DIRECTORY", 0x10000), ("O_NOFOLLOW", 0x20000),
                        ("O_CLOEXEC", 0x80000), ("O_NONBLOCK", 0x800)):
        monkeypatch.setattr(backend.os, name, getattr(backend.os, name, value), raising=False)
    kinds = {}

    def open_fd(path, flags, mode=0o600, *, dir_fd=None):
        trace.append(("open", path, flags, dir_fd))
        if path == state.open_failure:
            raise OSError("synthetic open failure")
        if dir_fd is not None:
            assert dir_fd in active
        fd = state.next_fd
        state.next_fd += 1
        active.add(fd)
        opened.add(fd)
        kinds[fd] = "directory" if flags & backend.os.O_DIRECTORY else "file"
        return fd

    def fstat(fd):
        assert fd in active
        if fd == state.stat_failure:
            raise OSError("synthetic fstat failure")
        mode = stat.S_IFDIR | 0o700 if kinds[fd] == "directory" else stat.S_IFREG | 0o600
        if state.wrong_file and kinds[fd] == "file":
            mode = stat.S_IFIFO | 0o600
        return SimpleNamespace(st_dev=88, st_mode=mode, st_uid=0, st_nlink=1)

    def close(fd):
        trace.append(("close", fd))
        closed.append(fd)
        assert fd in active, "descriptor close was blindly retried after release"
        active.remove(fd)
        if fd in state.close_failures:
            raise OSError(f"synthetic close failed after release: {fd}")

    def fsync(fd):
        assert fd in active
        trace.append(("sync", fd))
        if fd == state.sync_failure:
            raise OSError("synthetic sync failure")

    def write(fd, encoded):
        assert fd in active
        trace.append(("write", fd))
        return len(encoded)

    for name, function in (("open", open_fd), ("fstat", fstat), ("close", close),
                           ("fsync", fsync), ("write", write)):
        monkeypatch.setattr(backend.os, name, function)
    return SimpleNamespace(ports=ports, state=state, trace=trace, active=active,
                           opened=opened, closed=closed)


def no_leak_or_retry(syscalls):
    assert not syscalls.active, "a temporary or unreturned descriptor leaked"
    assert set(syscalls.closed) == syscalls.opened
    assert all(count == 1 for count in Counter(syscalls.closed).values())


@pytest.mark.parametrize("failure", [{10}, {11}, {10, 11}])
def test_directory_transfer_close_failure_closes_new_fd_without_retry(syscalls, failure):
    syscalls.state.close_failures = failure
    with pytest.raises(OSError, match="after release"):
        syscalls.ports._open_directory("/protected/child")
    no_leak_or_retry(syscalls)


def test_directory_stat_failure_closes_current_owned_fd_once(syscalls):
    syscalls.state.stat_failure = 11
    with pytest.raises(OSError, match="fstat"):
        syscalls.ports._open_directory("/protected")
    no_leak_or_retry(syscalls)


def test_directory_success_transfers_only_the_returned_fd(syscalls):
    fd = syscalls.ports._open_directory("/protected/child")
    assert syscalls.active == {fd}
    assert set(syscalls.closed) == syscalls.opened - {fd}
    assert len(syscalls.closed) == len(set(syscalls.closed))
    syscalls.ports.close(fd)
    no_leak_or_retry(syscalls)


@pytest.mark.parametrize("child_also_fails", [False, True])
def test_file_parent_close_failure_closes_unreturned_artifact_fd_once(syscalls, monkeypatch, child_also_fails):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    syscalls.state.close_failures = {parent, 11} if child_also_fails else {parent}
    with pytest.raises(OSError, match="after release"):
        syscalls.ports.open_existing("/protected/candidate.jsonl", kind="file")
    no_leak_or_retry(syscalls)


def test_wrong_type_child_close_failure_still_closes_parent_once(syscalls, monkeypatch):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    syscalls.state.wrong_file = True
    syscalls.state.close_failures = {11}
    with pytest.raises(OSError, match="after release"):
        syscalls.ports.open_existing("/protected/candidate.jsonl", kind="file")
    no_leak_or_retry(syscalls)


def test_file_success_transfers_fd_after_parent_was_closed(syscalls, monkeypatch):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    fd = syscalls.ports.open_existing("/protected/candidate.jsonl", kind="file")
    assert syscalls.active == {fd}
    assert syscalls.closed == [parent]
    syscalls.ports.close(fd)
    no_leak_or_retry(syscalls)


@pytest.mark.parametrize("failure", [{11}, {10}, {10, 11}])
@pytest.mark.parametrize("payload_fails", [False, True])
def test_attempt_close_failures_still_close_every_temporary_fd_once(syscalls, monkeypatch, failure, payload_fails):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    syscalls.state.close_failures = failure
    syscalls.state.sync_failure = 11 if payload_fails else None
    with pytest.raises(OSError, match="after release"):
        syscalls.ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    no_leak_or_retry(syscalls)


def test_attempt_success_closes_marker_and_parent(syscalls, monkeypatch):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    syscalls.ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    assert syscalls.closed == [11, 10]
    no_leak_or_retry(syscalls)


@pytest.mark.parametrize("operation", ["file", "attempt"])
def test_initial_open_failure_closes_only_owned_parent(syscalls, monkeypatch, operation):
    parent = backend.os.open("/", backend.os.O_DIRECTORY)
    monkeypatch.setattr(syscalls.ports, "_open_directory", lambda path: parent)
    syscalls.state.open_failure = "candidate.jsonl" if operation == "file" else backend.STUDY_ID + ".attempt"
    with pytest.raises(OSError, match="open failure"):
        if operation == "file":
            syscalls.ports.open_existing("/protected/candidate.jsonl", kind="file")
        else:
            syscalls.ports.reserve_attempt(b"synthetic", forbidden_device=77)
    no_leak_or_retry(syscalls)
