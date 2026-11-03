"""Synthetic checks for the Route 2 Linux hard-limit and post-exit contracts."""

from __future__ import annotations

from importlib import import_module, util
from pathlib import Path

from eating_event.route2_candidate_overlap.budget import BudgetLimits


def _module():
    name = "eating_event.route2_candidate_overlap.linux_enforcement"
    assert util.find_spec(name) is not None, "Linux enforcement contract module must exist"
    return import_module(name)


def test_resource_envelope_binds_rss_tasks_address_space_and_stop_margin() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
        stop_margin_ns=60_000_000_000,
    )

    assert envelope.rss_cap_bytes == 4 * 1024**3
    assert envelope.memory_swap_max_bytes == 0
    assert envelope.pids_max == 2
    assert envelope.rlimit_as_per_process_bytes == 2 * 1024**3
    assert envelope.runtime_max_ns == 3_540_000_000_000
    assert envelope.stage_a_stop_ns == 1_140_000_000_000
    assert envelope.fit_stop_ns == 840_000_000_000


def test_resource_envelope_uses_ram_fraction_and_rejects_unprovable_budget() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=4 * 1024**3,
        stop_margin_ns=60_000_000_000,
    )
    assert envelope.rss_cap_bytes == (3 * 4 * 1024**3) // 5
    assert envelope.rlimit_as_per_process_bytes == envelope.rss_cap_bytes // 2

    try:
        module.derive_resource_envelope(
            BudgetLimits(), available_ram_bytes=1024,
            stop_margin_ns=1_200_000_000_000,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a budget with no enforceable shutdown margin must be rejected")


def test_transient_unit_properties_encode_hard_limits_and_kill_all() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
        stop_margin_ns=60_000_000_000,
    )
    properties = dict(module.systemd_unit_properties(envelope))

    assert properties["Type"] == "exec"
    assert properties["MemoryMax"] == str(4 * 1024**3)
    assert properties["MemorySwapMax"] == "0"
    assert properties["TasksMax"] == "2"
    assert properties["LimitAS"] == str(2 * 1024**3)
    assert properties["CPUQuota"] == "200%"
    assert properties["RuntimeMaxSec"] == "3540s"
    assert properties["TimeoutStopSec"] == "60s"
    assert properties["KillMode"] == "control-group"
    assert properties["Restart"] == "no"
    assert properties["ProtectControlGroups"] == "yes"
    assert properties["PrivateMounts"] == "yes"
    assert properties["PrivateIPC"] == "yes"
    assert properties["LockPersonality"] == "yes"


def test_study_service_policy_confines_persistent_writes_and_one_role_view() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
    )
    study_root = "/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001"
    ledger = study_root[:-len("route2-candidate-overlap-v1-001")] + "route2-candidate-overlap-v1-001-budget.jsonl"
    lock = study_root[:-len("route2-candidate-overlap-v1-001")] + "route2-candidate-overlap-v1-001.lock"
    aliases = (
        ("candidate/o1/outer", "stage_a_input", "/run/route2-input/score"),
        ("candidate/o1/outer", "stage_a_reference", "/run/route2-input/reference"),
    )
    policy = module.build_study_access_policy(
        study_root=study_root,
        ledger_path=ledger,
        lock_path=lock,
        source_snapshot_root="/opt/route2/snapshots/route2-candidate-overlap-v1-001/source",
        runtime_snapshot_root="/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv",
        active_mounts=aliases,
    )
    binds = tuple(
        module.ReadonlyFileBind(role, phase, f"/mnt/e/data/{index}.jsonl", alias)
        for index, (role, phase, alias) in enumerate(aliases)
    )
    properties = dict(module.study_service_properties(envelope, policy, input_binds=binds))
    assert set(properties["ReadWritePaths"].split()) == {study_root, ledger, lock}
    assert set(properties["ReadOnlyPaths"].split()) == {
        policy.source_snapshot_root, policy.runtime_snapshot_root,
        "/run/route2-input/score", "/run/route2-input/reference",
    }
    assert "/mnt" in properties["InaccessiblePaths"]
    assert properties["PrivateNetwork"] == "yes"
    assert set(properties["BindReadOnlyPaths"].split()) == {
        "/mnt/e/data/0.jsonl:/run/route2-input/score",
        "/mnt/e/data/1.jsonl:/run/route2-input/reference",
    }

    try:
        module.build_study_access_policy(
            study_root=study_root,
            ledger_path=ledger,
            lock_path=lock,
            source_snapshot_root=policy.source_snapshot_root,
            runtime_snapshot_root=policy.runtime_snapshot_root,
            active_mounts=aliases + (("candidate/o2/outer", "stage_a_input", "/run/route2-input/other"),),
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("simultaneous role mounts must be refused")


def test_systemd_argv_never_uses_a_shell_or_collects_cgroup_evidence() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
    )
    study_root = "/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001"
    ledger = study_root[:-len("route2-candidate-overlap-v1-001")] + "route2-candidate-overlap-v1-001-budget.jsonl"
    lock = study_root[:-len("route2-candidate-overlap-v1-001")] + "route2-candidate-overlap-v1-001.lock"
    policy = module.build_study_access_policy(
        study_root=study_root,
        ledger_path=ledger,
        lock_path=lock,
        source_snapshot_root="/opt/route2/snapshots/route2-candidate-overlap-v1-001/source",
        runtime_snapshot_root="/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv",
        active_mounts=(),
    )
    argv = module.systemd_run_argv(
        "route2-synthetic-001",
        envelope,
        policy,
        ("/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv/bin/python", "-B", "-m", "synthetic_probe"),
    )
    assert "--collect" not in argv
    assert "--wait" in argv and "--pipe" in argv
    assert "--" in argv
    assert "-B" in argv
    assert "--setenv=PYTHONDONTWRITEBYTECODE=1" in argv
    assert "--setenv=PYTHONPATH=" + policy.source_snapshot_root + "/src" in argv
    assert "--setenv=XDG_CACHE_HOME=" + policy.study_root + "/.cache" in argv


def test_registered_windows_file_maps_to_one_exact_readonly_wsl_bind() -> None:
    module = _module()
    from eating_event.route2_candidate_overlap.path_map import file_mapping

    mapping = file_mapping(
        "E:\\study\\cache.npz", "a" * 64,
        role_id="candidate/o1/outer", phase="stage_a_input",
        bind_root="/run/route2-input",
    )
    binds = module.registered_file_binds((mapping,))
    assert len(binds) == 1
    assert binds[0].source_path == "/mnt/e/study/cache.npz"
    assert binds[0].alias_path == mapping.bind_path

    try:
        module.registered_file_binds((
            file_mapping(
                "E:\\study\\a.npz", "b" * 64,
                role_id="candidate/o1/outer", phase="stage_a_input",
                bind_root="/run/route2-input",
            ),
            file_mapping(
                "E:\\study\\gt.jsonl", "c" * 64,
                role_id="candidate/o2/outer", phase="stage_a_reference",
                bind_root="/run/route2-input",
            ),
        ))
    except PermissionError:
        pass
    else:
        raise AssertionError("registered binds for multiple roles must be refused")


def test_cgroup_receipt_requires_actual_v2_values_and_all_task_rlimits() -> None:
    module = _module()
    envelope = module.derive_resource_envelope(
        BudgetLimits(), available_ram_bytes=8 * 1024**3,
        stop_margin_ns=60_000_000_000,
    )
    observation = {
        "version": 2,
        "cgroup_path": "/system.slice/route2-synthetic.service",
        "memory.max": str(envelope.rss_cap_bytes),
        "memory.current": str(envelope.rss_cap_bytes // 2),
        "memory.peak": str(envelope.rss_cap_bytes),
        "memory.swap.max": "0",
        "memory.events": {"max": 0, "oom": 0, "oom_kill": 0},
        "pids.max": "2",
        "pids.current": "1",
        "pids.events.max": "0",
        "cpu.max": "200000 100000",
        "rlimit_as_bytes_by_pid": {"101": envelope.rlimit_as_per_process_bytes},
        "rss_bytes_by_pid": {"101": envelope.rlimit_as_per_process_bytes // 2},
        "thread_count_by_pid": {"101": 1},
    }

    receipt = module.validate_cgroup_enforcement(observation, envelope)
    assert receipt.hard_rss is True
    assert receipt.hard_worker_threads is True
    assert receipt.memory_peak_bytes == envelope.rss_cap_bytes
    assert receipt.task_count == 1
    assert receipt.process_tree_rss_bytes == envelope.rlimit_as_per_process_bytes // 2

    observation["rlimit_as_bytes_by_pid"] = {
        "101": envelope.rlimit_as_per_process_bytes,
        "102": envelope.rlimit_as_per_process_bytes + 1,
    }
    try:
        module.validate_cgroup_enforcement(observation, envelope)
    except PermissionError:
        pass
    else:
        raise AssertionError("one process outside the inherited RLIMIT_AS bound must fail closed")

    altered = {**observation, "memory.peak": str(envelope.rss_cap_bytes + 1)}
    try:
        module.validate_cgroup_enforcement(altered, envelope)
    except PermissionError:
        pass
    else:
        raise AssertionError("a full-study cgroup peak above the RSS hard line must fail closed")

    for field, value in (("pids.events.max", "1"), ("memory.events", {"max": 1, "oom": 0, "oom_kill": 0})):
        altered = {**observation, field: value}
        try:
            module.validate_cgroup_enforcement(altered, envelope)
        except PermissionError:
            pass
        else:
            raise AssertionError(f"a previously hit hard cgroup limit was accepted: {field}")


def test_live_cgroup_capture_walks_all_child_groups_and_processes(tmp_path: Path) -> None:
    module = _module()
    proc = tmp_path / "proc"
    cgroups = tmp_path / "cgroup"
    service = cgroups / "system.slice" / "route2-synthetic.service"
    child = service / "worker.slice"
    for path in (proc / "self", proc / "123", proc / "124", service, child):
        path.mkdir(parents=True)
    (proc / "self" / "cgroup").write_text("0::/system.slice/route2-synthetic.service\n")
    (service / "cgroup.procs").write_text("123\n")
    (child / "cgroup.procs").write_text("124\n")
    for group in (service, child):
        (group / "memory.max").write_text("4294967296\n")
        (group / "memory.current").write_text("1048576\n")
        (group / "memory.peak").write_text("2097152\n")
        (group / "memory.swap.max").write_text("0\n")
        (group / "memory.events").write_text("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n")
        (group / "pids.max").write_text("2\n")
        (group / "pids.current").write_text("2\n")
        (group / "pids.events").write_text("max 0\n")
        (group / "cpu.max").write_text("200000 100000\n")
    for pid, rss in (("123", 128), ("124", 256)):
        (proc / pid / "status").write_text(f"Name:\tworker\nVmRSS:\t{rss} kB\nThreads:\t1\n")
        (proc / pid / "limits").write_text(
            "Limit                     Soft Limit           Hard Limit           Units\n"
            "Max address space         2147483648           2147483648           bytes\n"
        )

    observation = module.capture_cgroup_v2_observation(proc_root=proc, cgroup_root=cgroups)
    assert observation["cgroup_path"] == "/system.slice/route2-synthetic.service"
    assert observation["rlimit_as_bytes_by_pid"] == {"123": 2147483648, "124": 2147483648}
    assert observation["thread_count_by_pid"] == {"123": 1, "124": 1}
    assert observation["rss_bytes_by_pid"] == {"123": 128 * 1024, "124": 256 * 1024}


def test_post_exit_receipt_requires_closed_ledger_inactive_unit_and_durable_observer() -> None:
    module = _module()
    receipt = {
        "schema": "route2_post_exit_receipt_v1",
        "invocation_id": "synthetic-invocation",
        "unit_name": "route2-synthetic.service",
        "terminal_sha256": "a" * 64,
        "unit_result": "success",
        "exit_status": 0,
        "active_state": "inactive",
        "durable_external_event": True,
        "invocation_started_ns": 100,
        "terminal_closed_ns": 150,
        "deadline_ns": 3_600_000_000_100,
        "external_clock": "windows_qpc",
        "qpc_frequency": 10_000_000,
        "external_started_ticks": 1_000,
        "external_terminal_detected_ticks": 1_500,
        "external_unit_inactive_ticks": 1_800,
        "external_receipt_fsynced_ticks": 2_000,
        "external_deadline_ticks": 36_000_001_000,
    }

    assert module.verify_post_exit_receipt(
        receipt,
        invocation_id="synthetic-invocation",
        unit_name="route2-synthetic.service",
        terminal_sha256="a" * 64,
        observed_monotonic_ns=250,
        observed_external_ticks=2_500,
        total_wall_ns=3_600_000_000_000,
        expected_qpc_frequency=10_000_000,
        expected_external_started_ticks=1_000,
    ) is True

    for mutation in (
        {"active_state": "active"},
        {"durable_external_event": False},
        {"external_unit_inactive_ticks": 25_000_000_000_000},
        {"external_receipt_fsynced_ticks": 1_400},
        {"terminal_sha256": "b" * 64},
    ):
        altered = {**receipt, **mutation}
        try:
            module.verify_post_exit_receipt(
                altered,
                invocation_id="synthetic-invocation",
                unit_name="route2-synthetic.service",
                terminal_sha256="a" * 64,
                observed_monotonic_ns=250,
                observed_external_ticks=2_500,
                total_wall_ns=3_600_000_000_000,
                expected_qpc_frequency=10_000_000,
                expected_external_started_ticks=1_000,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError(f"invalid post-exit evidence was accepted: {mutation}")
