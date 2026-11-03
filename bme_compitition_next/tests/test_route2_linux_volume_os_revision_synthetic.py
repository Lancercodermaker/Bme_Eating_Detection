"""Direct syscall-port regressions using mocks, without creating any OS objects."""

import os
import stat
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap import linux_volume_backend as backend


def _reservation(monkeypatch, *, same_device=False, failure=None):
    ports = backend.LinuxVolumeOSPorts()
    trace = []
    for name, value in (("O_NOFOLLOW", 0x20000), ("O_CLOEXEC", 0x80000)):
        monkeypatch.setattr(backend.os, name, getattr(backend.os, name, value), raising=False)
    monkeypatch.setattr(ports, "_open_directory", lambda path: 10)
    monkeypatch.setattr(backend.os, "fstat", lambda fd: SimpleNamespace(st_dev=77 if same_device else 88))
    def open_marker(*args, **kwargs):
        trace.append("create")
        return 11
    def sync(fd):
        trace.append(("sync", fd))
        if failure == "directory" and fd == 10:
            raise OSError("synthetic directory sync failure")
        if failure == "payload_sync" and fd == 11 and trace.count(("sync", 11)) == 2:
            raise OSError("synthetic payload sync failure")
    def write(fd, body):
        trace.append("payload_write")
        return len(body)-1 if failure == "short_write" else len(body)
    monkeypatch.setattr(backend.os, "open", open_marker)
    monkeypatch.setattr(backend.os, "fsync", sync)
    monkeypatch.setattr(backend.os, "write", write)
    monkeypatch.setattr(backend.os, "close", lambda fd: trace.append(("close", fd)))
    return ports, trace


def test_attempt_tombstone_is_durable_before_payload_write(monkeypatch):
    ports, trace = _reservation(monkeypatch)
    ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    assert trace[:5] == ["create", ("sync", 11), ("sync", 10), "payload_write", ("sync", 11)]


@pytest.mark.parametrize("failure", ["short_write", "payload_sync"])
def test_payload_failure_retains_the_prior_durable_tombstone(monkeypatch, failure):
    ports, trace = _reservation(monkeypatch, failure=failure)
    with pytest.raises(OSError):
        ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    assert trace.index(("sync", 10)) < trace.index("payload_write")
    assert trace.count("create") == 1


def test_directory_sync_failure_cannot_write_payload_or_report_durability(monkeypatch):
    ports, trace = _reservation(monkeypatch, failure="directory")
    with pytest.raises(OSError, match="directory sync"):
        ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    assert "payload_write" not in trace


def test_attempt_bind_alias_on_study_device_is_rejected_before_create(monkeypatch):
    ports, trace = _reservation(monkeypatch, same_device=True)
    with pytest.raises(PermissionError, match="study filesystem"):
        ports.reserve_attempt(b"synthetic payload", forbidden_device=77)
    assert "create" not in trace


@pytest.mark.parametrize("writable", [False, True])
def test_wrong_type_initial_open_is_nonblocking_and_rejected(monkeypatch, writable):
    ports = backend.LinuxVolumeOSPorts()
    trace = []
    # Flag constants are supplied in Windows solely for the mocked Linux call.
    for name, value in (("O_NOFOLLOW", 0x20000), ("O_CLOEXEC", 0x80000), ("O_NONBLOCK", 0x800)):
        monkeypatch.setattr(backend.os, name, getattr(backend.os, name, value), raising=False)
    monkeypatch.setattr(ports, "_open_directory", lambda path: 10)
    def open_fifo(path, flags, **kw):
        trace.append(flags)
        assert flags & backend.os.O_NONBLOCK, "wrong-type open can block before fstat"
        return 11
    monkeypatch.setattr(backend.os, "open", open_fifo)
    monkeypatch.setattr(backend.os, "fstat", lambda fd: SimpleNamespace(
        st_mode=stat.S_IFIFO | 0o600, st_uid=0, st_nlink=1,
    ))
    closed = []
    monkeypatch.setattr(backend.os, "close", lambda fd: closed.append(fd))
    with pytest.raises(PermissionError):
        ports.open_existing("/protected/synthetic-fifo", kind="file", writable=writable)
    assert closed == [11, 10]
