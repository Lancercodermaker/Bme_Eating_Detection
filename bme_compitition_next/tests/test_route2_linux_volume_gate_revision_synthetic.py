"""Review regressions using synthetic ledger and kernel evidence only."""

from __future__ import annotations

from copy import deepcopy
import stat

import pytest

from test_route2_linux_volume_backend_synthetic import rig, mutations  # noqa: F401


@pytest.fixture
def revised(rig):
    ports = rig.ports
    ports.live_cgroup = "/system.slice/route2-synthetic.service"
    ports.cgroup_inode = 901
    ports.cgroup_device = 29
    ports.kernel_reads = []
    original_stat = ports.path_stat

    def kernel_text(path):
        assert path.as_posix() == "/proc/self/cgroup", "synthetic test cannot read other kernel paths"
        ports.kernel_reads.append(path.as_posix())
        return "0::" + ports.live_cgroup + "\n"

    def path_stat(path, *, kind):
        info = original_stat(path, kind=kind)
        if path.startswith("/sys/fs/cgroup/"):
            assert kind == "directory"
            info.st_dev = ports.cgroup_device
            info.st_ino = ports.cgroup_inode
            info.st_rdev = 0
            info.st_mode = stat.S_IFDIR | 0o755
        return info

    ports._kernel_text = kernel_text
    ports.path_stat = path_stat
    return rig


def gate(revised):
    approved, _ = revised.expander._admission()
    return revised.expander._gate(revised.ports.ledger(), revised.ports.gate_hash,
                                 revised.current, revised.limits, approved)[:3]


def mount(revised):
    approved, _ = revised.expander._admission()
    return revised.expander._mount(revised.current, approved,
                                   "/system.slice/route2-synthetic.service")


def add_activity(revised, *, name="stage_a_treatment", started=160, ended=180, elapsed=25, wall=90):
    existing_start = next(value for event, value in revised.ports.events
                          if event == "activity_started" and value["name"] == name)
    existing_end = next(value for event, value in revised.ports.events
                        if event == "activity_finished" and value["name"] == name)
    snapshot = deepcopy(existing_end["snapshot"])
    beginning = {"name": name, "monotonic_ns": started, "fit": False, "stage_a": True}
    ending = {"name": name, "monotonic_ns": ended, "elapsed_ns": elapsed,
              "invocation_wall_ns": wall, "fit_wall_ns": 0,
              "failed": False, "snapshot": snapshot}
    existing_start.clear()
    existing_start.update(beginning)
    existing_end.clear()
    existing_end.update(ending)
    return existing_start, existing_end


def test_budgetguard_activity_distinct_end_and_later_samples_are_valid(revised):
    add_activity(revised)
    assert gate(revised) == (100, 200, "/system.slice/route2-synthetic.service")
    assert not mutations(revised.ports)


@pytest.mark.parametrize("field,value", [
    ("monotonic_ns", 99), ("monotonic_ns", 149), ("monotonic_ns", 201),
    ("monotonic_ns", True), ("monotonic_ns", 160.0),
])
def test_activity_start_time_must_be_exact_and_inside_invocation_boundary(revised, field, value):
    beginning, _ = add_activity(revised)
    beginning[field] = value
    with pytest.raises(PermissionError):
        gate(revised)
    assert not mutations(revised.ports)


@pytest.mark.parametrize("field,value", [
    ("monotonic_ns", 159), ("monotonic_ns", 201), ("monotonic_ns", True),
    ("elapsed_ns", -1), ("elapsed_ns", 19), ("elapsed_ns", 41), ("elapsed_ns", 25.0),
    ("invocation_wall_ns", -1), ("invocation_wall_ns", 84), ("invocation_wall_ns", 101),
    ("invocation_wall_ns", True), ("fit_wall_ns", -1), ("fit_wall_ns", 1),
    ("fit_wall_ns", True),
])
def test_activity_finish_and_sample_times_cannot_hide_wall_consumption(revised, field, value):
    _, ending = add_activity(revised)
    ending[field] = value
    with pytest.raises(PermissionError):
        gate(revised)
    assert not mutations(revised.ports)


@pytest.mark.parametrize("which,field", [
    (0, "monotonic_ns"), (1, "monotonic_ns"), (1, "elapsed_ns"),
    (1, "invocation_wall_ns"), (1, "fit_wall_ns"), (1, "snapshot"),
])
def test_activity_gate_requires_actual_budgetguard_schema(revised, which, field):
    events = add_activity(revised)
    del events[which][field]
    with pytest.raises(PermissionError):
        gate(revised)


def test_late_overshoot_cannot_be_hidden_by_short_monotonic_finish(revised):
    _, ending = add_activity(revised)
    ending["elapsed_ns"] = revised.limits.stage_a_wall_ns + 1
    ending["invocation_wall_ns"] = revised.limits.total_wall_ns + 1
    with pytest.raises(PermissionError):
        gate(revised)


def test_stage_a_fit_time_cannot_be_hidden_inside_finished_activity(revised):
    _, ending = add_activity(revised)
    ending["fit_wall_ns"] = revised.limits.fit_wall_ns + 1
    with pytest.raises(PermissionError):
        gate(revised)


def test_next_activity_cannot_start_before_previous_completion_sample(revised):
    add_activity(revised, name="stage_a_reference", started=151, ended=180, elapsed=34, wall=90)
    add_activity(revised, started=185, ended=195, elapsed=10, wall=96)
    with pytest.raises(PermissionError):
        gate(revised)


def test_ordered_multiple_activities_are_valid(revised):
    add_activity(revised, name="stage_a_reference", started=151, ended=180, elapsed=34, wall=90)
    add_activity(revised, started=191, ended=196, elapsed=6, wall=98)
    assert gate(revised) == (100, 200, "/system.slice/route2-synthetic.service")


@pytest.mark.parametrize("field,value", [
    ("process_tree_rss_bytes", 5 * (1 << 30)), ("compute_workers", 3),
    ("study_disk_peak_bytes", 3 * (1 << 30)), ("study_image_inode", 100),
    ("study_fs_capacity_bytes", 3 * (1 << 30)),
])
def test_finished_activity_snapshot_is_bound_to_fixed_identity_and_limits(revised, field, value):
    _, ending = add_activity(revised)
    ending["snapshot"][field] = value
    with pytest.raises(PermissionError):
        gate(revised)


@pytest.mark.parametrize("members", [(), (456,), (123, 456), (123, 123), (True,)])
def test_cgroup_must_contain_exactly_controller_pid(revised, members):
    revised.ports.pids = members
    with pytest.raises(PermissionError):
        mount(revised)
    assert not mutations(revised.ports)


def test_cgroup_is_bound_to_live_unified_membership_before_and_after_sample(revised):
    mount(revised)
    assert revised.ports.kernel_reads == ["/proc/self/cgroup", "/proc/self/cgroup"]


def test_wrong_live_cgroup_rejected_even_with_controller_pid_in_supplied_members(revised):
    revised.ports.live_cgroup = "/system.slice/unrelated.service"
    with pytest.raises(PermissionError):
        mount(revised)


@pytest.mark.parametrize("text", ["", "0::/system.slice/route2-synthetic.service\n0::/other\n",
    "1:name=systemd:/system.slice/route2-synthetic.service\n", "0::relative\n"])
def test_missing_duplicate_or_noncanonical_live_unified_cgroup_is_denied(revised, text):
    revised.ports._kernel_text = lambda _path: text
    with pytest.raises(PermissionError):
        mount(revised)


def test_controller_migration_during_membership_sampling_is_denied(revised):
    sample = revised.ports.cgroup_members

    def migrated(path):
        result = sample(path)
        revised.ports.live_cgroup = "/system.slice/unrelated.service"
        return result

    revised.ports.cgroup_members = migrated
    with pytest.raises(PermissionError):
        mount(revised)


def test_cgroup_recreation_during_sample_is_denied(revised):
    sample = revised.ports.cgroup_members

    def recreated(path):
        result = sample(path)
        revised.ports.cgroup_inode += 1
        return result

    revised.ports.cgroup_members = recreated
    with pytest.raises(PermissionError):
        mount(revised)


@pytest.mark.parametrize("field", ["cgroup_inode", "cgroup_device"])
def test_cgroup_identity_cannot_change_between_expansion_checkpoints(revised, field):
    mount(revised)
    setattr(revised.ports, field, getattr(revised.ports, field) + 1)
    with pytest.raises(PermissionError):
        mount(revised)
