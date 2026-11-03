"""Synthetic checks for live Route 2 systemd/cgroup identity binding."""

from __future__ import annotations

from importlib import import_module, util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap.budget import BudgetLimits


def _backend():
    name = "eating_event.route2_candidate_overlap.linux_cgroup_backend"
    assert util.find_spec(name) is not None, "live Linux cgroup backend must exist"
    return import_module(name)


def _device_major_minor(device: int) -> str:
    if hasattr(os, "major") and hasattr(os, "minor"):
        return f"{os.major(device)}:{os.minor(device)}"
    major = ((device >> 8) & 0xFFF) | ((device >> 32) & 0xFFFFF000)
    minor = (device & 0xFF) | ((device >> 12) & 0xFFFFFF00)
    return f"{major}:{minor}"


def _mountinfo_path(path: Path) -> str:
    resolved = path.resolve().as_posix()
    return resolved if resolved.startswith("/") else f"/{resolved.lstrip('/')}"


def _fixture(tmp_path: Path):
    enforcement = import_module("eating_event.route2_candidate_overlap.linux_enforcement")
    envelope = enforcement.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
        stop_margin_ns=60_000_000_000,
    )
    unit = "route2-synthetic.service"
    cgroup_path = f"/system.slice/{unit}"
    proc = tmp_path / "proc"
    root = tmp_path / "cgroup"
    service = root / "system.slice" / unit
    child = service / "worker.slice"
    for path in (proc / "self", proc / "123", proc / "124", service, child):
        path.mkdir(parents=True)

    (proc / "self" / "cgroup").write_text(f"0::{cgroup_path}\n", encoding="ascii")
    (service / "cgroup.procs").write_text("123\n", encoding="ascii")
    (child / "cgroup.procs").write_text("124\n", encoding="ascii")
    for group in (service, child):
        (group / "memory.max").write_text(f"{envelope.memory_max_bytes}\n", encoding="ascii")
        (group / "memory.current").write_text("1048576\n", encoding="ascii")
        (group / "memory.peak").write_text("2097152\n", encoding="ascii")
        (group / "memory.swap.max").write_text("0\n", encoding="ascii")
        (group / "memory.events").write_text(
            "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n", encoding="ascii",
        )
        (group / "pids.max").write_text("2\n", encoding="ascii")
        (group / "pids.current").write_text("2\n", encoding="ascii")
        (group / "pids.events").write_text("max 0\n", encoding="ascii")
        (group / "cpu.max").write_text("200000 100000\n", encoding="ascii")
    for pid, rss in (("123", 128), ("124", 256)):
        (proc / pid / "status").write_text(
            f"Name:\tworker\nVmRSS:\t{rss} kB\nThreads:\t1\n", encoding="ascii",
        )
        (proc / pid / "limits").write_text(
            "Limit                     Soft Limit           Hard Limit           Units\n"
            f"Max address space         {envelope.rlimit_as_per_process_bytes}"
            f"           {envelope.rlimit_as_per_process_bytes}           bytes\n",
            encoding="ascii",
        )

    device = os.stat(root).st_dev
    mount_id = 37
    mount_point = _mountinfo_path(root)
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        f"{mount_id} 25 {_device_major_minor(device)} / {mount_point} "
        "rw,nosuid,nodev,noexec,relatime - cgroup2 cgroup rw\n",
        encoding="ascii",
    )
    properties = {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "Type": "exec",
        "Restart": "no",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "RemainAfterExit": "no",
        "ControlGroup": cgroup_path,
        "MainPID": "123",
        "InvocationID": "0123456789abcdef0123456789abcdef",
        "MemoryAccounting": "yes",
        "MemoryMax": str(envelope.memory_max_bytes),
        "MemorySwapMax": str(envelope.memory_swap_max_bytes),
        "TasksAccounting": "yes",
        "TasksMax": str(envelope.pids_max),
        "CPUQuotaPerSecUSec": "2s",
        "RuntimeMaxUSec": "59min",
        "TimeoutStopUSec": "1min",
    }
    return {
        "enforcement": enforcement,
        "envelope": envelope,
        "unit": unit,
        "proc": proc,
        "root": root,
        "mountinfo": mountinfo,
        "mount_point": mount_point,
        "properties": properties,
        "mount_id": mount_id,
    }


def _observe(backend, fixture, **overrides):
    return backend.capture_active_study_service_observation(
        fixture["unit"], fixture["envelope"],
        proc_root=fixture["proc"],
        cgroup_root=fixture["root"],
        mountinfo_path=fixture["mountinfo"],
        **overrides,
    )


def test_capture_binds_exact_live_service_mount_and_existing_cgroup_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(
        backend, "read_systemd_unit_properties",
        lambda unit: fixture["properties"] if unit == fixture["unit"] else {},
    )

    observation = _observe(backend, fixture)
    proof = fixture["enforcement"].validate_cgroup_enforcement(
        observation, fixture["envelope"],
    )

    assert proof.process_count == 2
    assert proof.task_count == 2
    assert observation["cgroup_path"] == fixture["properties"]["ControlGroup"]
    assert observation["systemd_unit"]["main_pid"] == 123
    assert observation["systemd_unit"]["invocation_id"] == fixture["properties"]["InvocationID"]
    assert observation["cgroup2_mount"]["mount_id"] == fixture["mount_id"]
    assert observation["rlimit_as_bytes_by_pid"] == {
        "123": fixture["envelope"].rlimit_as_per_process_bytes,
        "124": fixture["envelope"].rlimit_as_per_process_bytes,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Type", "simple"),
        ("Restart", "on-failure"),
        ("KillMode", "process"),
        ("MemoryMax", "max"),
        ("TasksMax", "3"),
        ("CPUQuotaPerSecUSec", "3s"),
        ("RuntimeMaxUSec", "60min"),
        ("ControlGroup", "/system.slice/other.service"),
        ("ActiveState", "inactive"),
    ],
)
def test_capture_rejects_mismatched_service_semantics_or_hard_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    properties = dict(fixture["properties"])
    properties[field] = value
    monkeypatch.setattr(backend, "read_systemd_unit_properties", lambda _unit: properties)

    with pytest.raises(PermissionError):
        _observe(backend, fixture)


@pytest.mark.parametrize(
    "variant", ["device", "root", "path", "duplicate"],
)
def test_capture_rejects_ambiguous_or_unbound_cgroup2_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    fields = fixture["mountinfo"].read_text(encoding="ascii").split()
    if variant == "device":
        fields[2] = "999999:999999"
    elif variant == "root":
        fields[3] = "/slice"
    elif variant == "path":
        fields[4] = "/wrong/path"
    else:
        duplicate = list(fields)
        duplicate[0] = "38"
        duplicate[4] = "/another/cgroup"
        fixture["mountinfo"].write_text(
            " ".join(fields) + "\n" + " ".join(duplicate) + "\n", encoding="ascii",
        )
    if variant != "duplicate":
        fixture["mountinfo"].write_text(" ".join(fields) + "\n", encoding="ascii")
    monkeypatch.setattr(
        backend, "read_systemd_unit_properties", lambda _unit: fixture["properties"],
    )

    with pytest.raises(PermissionError):
        _observe(backend, fixture)


def test_capture_rejects_a_different_cgroup_root_on_the_same_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    other_root = tmp_path / "other-cgroup-root"
    import shutil

    shutil.copytree(fixture["root"], other_root)
    assert os.stat(other_root).st_dev == os.stat(fixture["root"]).st_dev
    monkeypatch.setattr(
        backend, "read_systemd_unit_properties", lambda _unit: fixture["properties"],
    )

    with pytest.raises(PermissionError, match="mount point"):
        backend.capture_active_study_service_observation(
            fixture["unit"], fixture["envelope"],
            proc_root=fixture["proc"],
            cgroup_root=other_root,
            mountinfo_path=fixture["mountinfo"],
        )


def test_capture_rejects_changed_systemd_invocation_id_during_cgroup_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    before = dict(fixture["properties"])
    after = {**before, "InvocationID": "fedcba9876543210fedcba9876543210"}
    snapshots = [before, after]
    monkeypatch.setattr(
        backend, "read_systemd_unit_properties", lambda _unit: snapshots.pop(0),
    )

    with pytest.raises(PermissionError, match="changed during"):
        _observe(backend, fixture)
    assert snapshots == []


def test_capture_rejects_changed_cgroup_mount_identity_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _backend()
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(
        backend, "read_systemd_unit_properties", lambda _unit: fixture["properties"],
    )
    capture = backend.capture_cgroup_v2_observation

    def capture_then_remount(**kwargs):
        observation = capture(**kwargs)
        fields = fixture["mountinfo"].read_text(encoding="ascii").split()
        fields[0] = str(fixture["mount_id"] + 1)
        fixture["mountinfo"].write_text(" ".join(fields) + "\n", encoding="ascii")
        return observation

    monkeypatch.setattr(backend, "capture_cgroup_v2_observation", capture_then_remount)
    with pytest.raises(PermissionError, match="mount identity changed"):
        _observe(backend, fixture)


def test_systemctl_reader_uses_direct_argv_and_requires_complete_unique_properties() -> None:
    backend = _backend()
    values = {
        "Type": "exec",
        "Restart": "no",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "RemainAfterExit": "no",
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "ControlGroup": "/system.slice/route2-synthetic.service",
        "MainPID": "123",
        "InvocationID": "0123456789abcdef0123456789abcdef",
        "MemoryAccounting": "yes",
        "MemoryMax": "4294967296",
        "MemorySwapMax": "0",
        "TasksAccounting": "yes",
        "TasksMax": "2",
        "CPUQuotaPerSecUSec": "2s",
        "RuntimeMaxUSec": "59min",
        "TimeoutStopUSec": "1min",
    }
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="".join(f"{name}={value}\n" for name, value in values.items()),
        )

    actual = backend.read_systemd_unit_properties(
        "route2-synthetic.service", run=fake_run,
    )
    assert actual == values
    argv, kwargs = calls[0]
    assert isinstance(argv, list)
    assert argv[0] == "/usr/bin/systemctl"
    assert argv[1] == "show"
    assert argv[-1] == "route2-synthetic.service"
    assert kwargs["shell"] is False

    def duplicate_run(_argv, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="Type=exec\nType=exec\n")

    with pytest.raises(PermissionError):
        backend.read_systemd_unit_properties(
            "route2-synthetic.service", run=duplicate_run,
        )
