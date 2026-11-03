from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eating_event.route2_candidate_overlap.path_map import (
    ActiveRoleMountSet,
    ExactFileMapping,
    canonical_manifest_bytes,
    file_mapping,
)


def _synthetic_controller(
    tmp_path: Path,
    mappings: tuple[ExactFileMapping, ...],
    *,
    effective_uid: int = 0,
    readonly_after_remount: bool = True,
    receipt_root: Path | None = None,
    source_resolution_log: list[str] | None = None,
    unmount_fail_aliases: frozenset[str] = frozenset(),
    namespace_check=None,
    worker_prepublication_check=None,
    directory_sync_hook=None,
):
    from eating_event.route2_candidate_overlap.linux_mount_controller import (
        LinuxRoleMountController,
    )

    tmp_path.mkdir(parents=True, exist_ok=True)
    source_paths: dict[str, Path] = {}
    alias_paths: dict[str, Path] = {}
    mounted: dict[str, tuple[str, int, bool]] = {}
    commands: list[tuple[str, ...]] = []
    next_mount_id = 40

    for index, mapping in enumerate(mappings):
        source = tmp_path / f"source-{index}.jsonl"
        source.write_bytes(f"synthetic source {index}\n".encode())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == mapping.sha256
        source_paths[mapping.bind_path] = source
        alias = tmp_path / "aliases" / Path(mapping.bind_path).name
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.write_bytes(b"")
        alias_paths[mapping.bind_path] = alias

    def run_command(argv: tuple[str, ...]) -> None:
        nonlocal next_mount_id
        commands.append(argv)
        if argv[0] == "mount" and argv[1] == "--bind":
            source, alias = argv[2], argv[3]
            mounted[alias] = (source, next_mount_id, False)
            next_mount_id += 1
        elif argv[0] == "mount" and argv[1] == "-o":
            alias = argv[4]
            source, mount_id, _ = mounted[alias]
            mounted[alias] = (source, mount_id, readonly_after_remount)
        elif argv[0] == "umount":
            if argv[1] in unmount_fail_aliases:
                raise RuntimeError("synthetic umount failure")
            mounted.pop(argv[1], None)
        else:  # pragma: no cover - unexpected command must fail the test
            raise AssertionError(f"unexpected synthetic command: {argv!r}")

    def mountinfo() -> str:
        rows = []
        for alias, (source, mount_id, readonly) in sorted(mounted.items()):
            options = "ro,relatime" if readonly else "rw,relatime"
            rows.append(
                f"{mount_id} 1 0:77 / {alias} {options} - ext4 /dev/synthetic rw\n"
            )
        return "".join(rows)

    def file_identity(path: Path) -> tuple[int, int]:
        logical_alias = next(
            (alias for alias, physical in alias_paths.items() if physical == path), None
        )
        if logical_alias is not None and logical_alias in mounted:
            bound_source = Path(mounted[logical_alias][0])
            info = bound_source.stat()
        else:
            info = path.stat()
        return info.st_dev, info.st_ino

    manifest_bytes = canonical_manifest_bytes("/run/route2-input", mappings)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    import eating_event.route2_candidate_overlap.contracts as contracts

    contracts.FROZEN_ADMISSION = SimpleNamespace(path_map_sha256=manifest_sha256)

    def resolve_source(bind):
        if source_resolution_log is not None:
            source_resolution_log.append(bind.alias_path)
        return source_paths[bind.alias_path]

    controller = LinuxRoleMountController(
        reviewed_manifest_bytes=manifest_bytes,
        expected_manifest_sha256=manifest_sha256,
        receipt_root=receipt_root or tmp_path / "receipts",
        source_resolver=resolve_source,
        alias_path_resolver=lambda alias: alias_paths[alias],
        command_runner=run_command,
        mountinfo_reader=mountinfo,
        platform_name=lambda: "Linux",
        effective_uid=lambda: effective_uid,
        root_path_validator=lambda _path: None,
        file_identity_reader=file_identity,
        directory_sync=directory_sync_hook or (lambda _path: None),
        mount_namespace_validator=namespace_check or (lambda: None),
        worker_prepublication_check=worker_prepublication_check or (
            lambda _role, _mappings: True
        ),
        controller_run_id="synthetic-run",
    )
    controller._synthetic_manifest_bytes = manifest_bytes
    return controller, source_paths, alias_paths, mounted, commands, mountinfo


@pytest.fixture(autouse=True)
def _reset_frozen_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    import eating_event.route2_candidate_overlap.contracts as contracts

    monkeypatch.setattr(contracts, "FROZEN_ADMISSION", None)


def _mappings(
    role: str = "candidate/o1/outer",
    *,
    source_offset: int = 0,
) -> tuple[ExactFileMapping, ...]:
    return tuple(
        file_mapping(
            f"C:\\route2\\{phase}.jsonl",
            hashlib.sha256(f"synthetic source {index + source_offset}\n".encode()).hexdigest(),
            role_id=role,
            phase=phase,
            bind_root="/run/route2-input",
        )
        for index, phase in enumerate(("stage_a_input", "stage_a_reference"))
    )


def _manifest_sha256(mappings: tuple[ExactFileMapping, ...]) -> str:
    encoded = canonical_manifest_bytes("/run/route2-input", mappings)
    return hashlib.sha256(encoded).hexdigest()


def _activate(
    controller,
    mappings: tuple[ExactFileMapping, ...],
    role_id: str,
    *,
    manifest_sha256: str | None = None,
) -> ActiveRoleMountSet:
    manifest_bytes = controller._synthetic_manifest_bytes
    return controller.activate_role_view(
        manifest_sha256=manifest_sha256 or hashlib.sha256(manifest_bytes).hexdigest(),
        manifest_bytes=manifest_bytes,
        role_id=role_id,
        mappings=mappings,
    )


def test_production_receipts_default_to_persistent_controller_storage() -> None:
    from eating_event.route2_candidate_overlap.linux_mount_controller import (
        LinuxRoleMountController,
    )

    manifest_bytes = canonical_manifest_bytes("/run/route2-input", _mappings())
    controller = LinuxRoleMountController(
        reviewed_manifest_bytes=manifest_bytes,
        expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        worker_prepublication_check=lambda _role, _mappings: True,
        mount_namespace_validator=lambda: None,
    )

    assert controller._receipt_root == Path(
        "/var/lib/route2-controller/role-mount-receipts"
    )


def test_linux_controller_activates_exact_stage_a_bind_set_and_revoke_is_durable(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    controller, _sources, _aliases, mounted, commands, mountinfo = _synthetic_controller(
        tmp_path, mappings
    )

    active = _activate(controller, mappings, "candidate/o1/outer")

    assert type(active) is ActiveRoleMountSet
    assert active.controller_run_id == "synthetic-run"
    assert {receipt.phase for receipt in active.mounts} == {
        "stage_a_input",
        "stage_a_reference",
    }
    assert {receipt.bind_path for receipt in active.mounts} == {
        item.bind_path for item in mappings
    }
    assert all(receipt.mount_id > 0 for receipt in active.mounts)
    assert all("ro" in line.split(" - ", 1)[0].split()[5].split(",") for line in mountinfo().splitlines())
    assert len(mounted) == len(mappings)
    assert sum(command[0] == "mount" and command[1] == "--bind" for command in commands) == 2
    assert sum(command[0] == "mount" and command[1] == "-o" for command in commands) == 2

    receipt_file = tmp_path / "receipts" / f"activation-{active.controller_run_id}-{active.phase_id}.json"
    receipt_bytes = receipt_file.read_bytes()
    receipt_value = json.loads(receipt_bytes)
    assert receipt_value["schema"] == "route2_mount_receipt_v1"
    assert receipt_value["manifest_sha256"] == _manifest_sha256(mappings)
    assert receipt_value["controller_run_id"] == active.controller_run_id
    assert receipt_value["phase_id"] == active.phase_id
    assert len(receipt_value["mounts"]) == 2
    assert hashlib.sha256(receipt_bytes).hexdigest() == active.receipt_sha256

    revocation_sha256 = controller.revoke_role_view(active)

    assert len(revocation_sha256) == 64
    assert not mounted
    assert sum(command[0] == "umount" for command in commands) == 2
    revocation_file = tmp_path / "receipts" / f"revocation-{active.controller_run_id}-{active.phase_id}.json"
    revocation_bytes = revocation_file.read_bytes()
    assert hashlib.sha256(revocation_bytes).hexdigest() == revocation_sha256
    assert json.loads(revocation_bytes)["activation_receipt_sha256"] == active.receipt_sha256
    assert controller.revoke_role_view(active) == revocation_sha256


def test_repeating_same_activation_is_idempotent_while_view_is_active(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    controller, _sources, _aliases, _mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path, mappings
    )
    first = _activate(controller, mappings, "candidate/o1/outer")
    command_count = len(commands)

    second = _activate(controller, mappings, "candidate/o1/outer")

    assert second is first
    assert len(commands) == command_count


def test_controller_requires_linux_root_before_any_mount_command(tmp_path: Path) -> None:
    mappings = _mappings()
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        effective_uid=1234,
    )

    with pytest.raises(PermissionError, match="Linux and effective UID 0"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not commands
    assert not mounted


def test_source_digest_mismatch_rejects_activation_without_mounting(tmp_path: Path) -> None:
    mappings = _mappings()
    controller, sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path, mappings
    )
    next(iter(sources.values())).write_bytes(b"changed after path-map review")

    with pytest.raises(PermissionError, match="SHA-256 changed"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not commands
    assert not mounted


def test_wrong_alias_root_and_mixed_roles_are_rejected_before_mounting(
    tmp_path: Path,
) -> None:
    correct = _mappings()
    wrong_root = ExactFileMapping(
        logical_path=correct[0].logical_path,
        sha256=correct[0].sha256,
        role_id=correct[0].role_id,
        phase=correct[0].phase,
        bind_path=correct[0].bind_path.replace(
            "/run/route2-input/", "/run/route2-other/", 1
        ),
    )
    wrong_root_mappings = (wrong_root, correct[1])
    wrong_root_bytes = canonical_manifest_bytes(
        "/run/route2-input", wrong_root_mappings
    )
    from eating_event.route2_candidate_overlap.linux_mount_controller import (
        LinuxRoleMountController,
    )

    with pytest.raises(PermissionError, match="canonical reviewed manifest"):
        LinuxRoleMountController(
            reviewed_manifest_bytes=wrong_root_bytes,
            expected_manifest_sha256=hashlib.sha256(wrong_root_bytes).hexdigest(),
            worker_prepublication_check=lambda _role, _mappings: True,
            mount_namespace_validator=lambda: None,
        )

    other_role = file_mapping(
        correct[1].logical_path,
        correct[1].sha256,
        role_id="candidate/o2/outer",
        phase=correct[1].phase,
        bind_root="/run/route2-input",
    )
    mixed_role_mappings = (correct[0], other_role)
    other_controller, _sources, _aliases, other_mounted, other_commands, _mountinfo = (
        _synthetic_controller(tmp_path / "role", mixed_role_mappings)
    )

    with pytest.raises(PermissionError, match="this role's Stage A"):
        _activate(other_controller, mixed_role_mappings, "candidate/o1/outer")

    assert not other_commands and not other_mounted


def test_read_write_mountinfo_triggers_rollback_and_faults_controller(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        readonly_after_remount=False,
    )

    with pytest.raises(PermissionError, match="not read-only"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not mounted
    assert sum(command[0] == "umount" for command in commands) == 1
    assert controller.faulted
    with pytest.raises(PermissionError, match="faulted"):
        _activate(controller, mappings, "candidate/o1/outer")


def test_canonical_manifest_pins_every_stage_a_mapping_for_the_role(
    tmp_path: Path,
) -> None:
    role_mappings = _mappings()
    extra_input = file_mapping(
        "C:\\route2\\extra-input.jsonl",
        hashlib.sha256(b"synthetic source 2\n").hexdigest(),
        role_id="candidate/o1/outer",
        phase="stage_a_input",
        bind_root="/run/route2-input",
    )
    complete_manifest_mappings = role_mappings + (extra_input,)
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        complete_manifest_mappings,
        source_resolution_log=source_resolution_log,
    )

    with pytest.raises(PermissionError, match="canonical manifest's complete role set"):
        _activate(controller, role_mappings, "candidate/o1/outer")

    assert not source_resolution_log
    assert not mounted and not commands


def test_caller_cannot_select_a_manifest_digest(tmp_path: Path) -> None:
    mappings = _mappings()
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        source_resolution_log=source_resolution_log,
    )

    with pytest.raises(PermissionError, match="frozen admission path-map pin"):
        _activate(
            controller,
            mappings,
            "candidate/o1/outer",
            manifest_sha256="b" * 64,
        )

    assert not source_resolution_log
    assert not mounted and not commands


def test_direct_controller_call_requires_matching_frozen_path_map_pin(
    tmp_path: Path,
) -> None:
    import eating_event.route2_candidate_overlap.contracts as contracts

    mappings = _mappings()
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        source_resolution_log=source_resolution_log,
    )
    contracts.FROZEN_ADMISSION = SimpleNamespace(path_map_sha256="f" * 64)

    with pytest.raises(PermissionError, match="frozen admission path-map pin"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not source_resolution_log
    assert not mounted and not commands


def test_direct_controller_call_fails_closed_when_admission_is_unset(
    tmp_path: Path,
) -> None:
    import eating_event.route2_candidate_overlap.contracts as contracts

    mappings = _mappings()
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        source_resolution_log=source_resolution_log,
    )
    contracts.FROZEN_ADMISSION = None

    with pytest.raises(PermissionError, match=r"registrations and A\+B approval are not frozen"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not source_resolution_log
    assert not mounted and not commands


def test_different_active_role_is_rejected_before_source_resolution(
    tmp_path: Path,
) -> None:
    first_role = _mappings("candidate/o1/outer")
    second_role = _mappings("candidate/o2/outer", source_offset=2)
    complete_manifest_mappings = first_role + second_role
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        complete_manifest_mappings,
        source_resolution_log=source_resolution_log,
    )
    manifest_sha256 = _manifest_sha256(complete_manifest_mappings)
    _activate(controller, first_role, "candidate/o1/outer")
    source_count_before_rejection = len(source_resolution_log)

    with pytest.raises(PermissionError, match="another exact role view"):
        _activate(controller, second_role, "candidate/o2/outer")

    assert len(source_resolution_log) == source_count_before_rejection
    assert len(mounted) == 2
    assert sum(command[0] == "mount" for command in commands) == 4


def test_receipt_root_creation_fsyncs_each_new_directory_parent(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    manifest_bytes = canonical_manifest_bytes("/run/route2-input", mappings)
    sync_calls: list[Path] = []
    root = tmp_path / "persistent" / "controller" / "receipts"
    from eating_event.route2_candidate_overlap.linux_mount_controller import (
        LinuxRoleMountController,
    )
    controller = LinuxRoleMountController(
        reviewed_manifest_bytes=manifest_bytes,
        expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        receipt_root=root,
        root_path_validator=lambda _path: None,
        directory_sync=sync_calls.append,
        mount_namespace_validator=lambda: None,
        worker_prepublication_check=lambda _role, _mappings: True,
    )

    controller._ensure_receipt_root()

    assert root.is_dir()
    assert {tmp_path, tmp_path / "persistent", tmp_path / "persistent" / "controller"} <= set(sync_calls)


def test_namespace_and_worker_publication_preconditions_fail_before_mounts(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    source_resolution_log: list[str] = []
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path / "namespace",
        mappings,
        source_resolution_log=source_resolution_log,
        namespace_check=lambda: (_ for _ in ()).throw(
            PermissionError("private mount namespace required")
        ),
    )

    with pytest.raises(PermissionError, match="private mount namespace"):
        _activate(controller, mappings, "candidate/o1/outer")

    assert not source_resolution_log and not commands and not mounted

    other_log: list[str] = []
    other, _sources, _aliases, other_mounted, other_commands, _mountinfo = (
        _synthetic_controller(
            tmp_path / "worker",
            mappings,
            source_resolution_log=other_log,
            worker_prepublication_check=lambda _role, _mappings: False,
        )
    )
    with pytest.raises(PermissionError, match="worker publication precondition"):
        _activate(other, mappings, "candidate/o1/outer")
    assert not other_log and not other_commands and not other_mounted


def test_namespace_guard_rejects_shared_mount_propagation() -> None:
    import eating_event.route2_candidate_overlap.linux_mount_controller as module

    mountinfo = "1 0 8:1 / / rw shared:1 - ext4 /dev/root rw\n"

    with pytest.raises(PermissionError, match="shared mount propagation"):
        module._require_alias_root_not_shared(mountinfo)

    module._require_alias_root_not_shared(
        "1 0 8:1 / / rw master:1 - ext4 /dev/root rw\n"
    )


def test_default_namespace_guard_applies_propagation_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import eating_event.route2_candidate_overlap.linux_mount_controller as module

    monkeypatch.setattr(module, "platform", SimpleNamespace(system=lambda: "Linux"))
    stat_result = module.os.stat_result
    monkeypatch.setattr(
        module.os,
        "stat",
        lambda path: stat_result((
            0, 2 if path == "/proc/self/ns/mnt" else 1, 1,
            1, 0, 0, 0, 0, 0, 0,
        )),
    )
    monkeypatch.setattr(
        module,
        "_default_mountinfo_reader",
        lambda: "1 0 8:1 / / rw shared:1 - ext4 /dev/root rw\n",
    )

    with pytest.raises(PermissionError, match="shared mount propagation"):
        module._require_private_mount_namespace()


def test_failed_revoke_processes_every_alias_persists_failure_and_faults(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    failing_alias = mappings[-1].bind_path
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
        unmount_fail_aliases=frozenset({failing_alias}),
    )
    active = _activate(controller, mappings, "candidate/o1/outer")

    with pytest.raises(PermissionError, match="revocation failed"):
        controller.revoke_role_view(active)

    attempted_aliases = {
        command[1] for command in commands if command[0] == "umount"
    }
    assert attempted_aliases == {item.bind_path for item in mappings}
    assert controller.faulted
    assert set(mounted) == {failing_alias}
    failure_path = tmp_path / "receipts" / (
        f"revocation-failure-{active.controller_run_id}-{active.phase_id}.json"
    )
    failure_bytes = failure_path.read_bytes()
    failure = json.loads(failure_bytes)
    assert failure["schema"] == "route2_mount_revocation_failure_v1"
    assert failure["residual_aliases"] == [failing_alias]
    assert len(hashlib.sha256(failure_bytes).hexdigest()) == 64
    with pytest.raises(PermissionError, match="faulted"):
        _activate(controller, mappings, "candidate/o1/outer")


def test_repeated_revoke_persists_evidence_if_an_alias_reappears(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    controller, sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
    )
    active = _activate(controller, mappings, "candidate/o1/outer")
    controller.revoke_role_view(active)
    commands_before_repeated_revoke = len(commands)
    reappeared = mappings[0].bind_path
    mounted[reappeared] = (str(sources[reappeared]), 999, True)

    with pytest.raises(PermissionError, match="durable failure evidence"):
        controller.revoke_role_view(active)

    assert controller.faulted
    assert len(commands) == commands_before_repeated_revoke
    failure_path = tmp_path / "receipts" / (
        f"revocation-failure-{active.controller_run_id}-{active.phase_id}.json"
    )
    failure = json.loads(failure_path.read_bytes())
    assert failure["schema"] == "route2_mount_revocation_failure_v1"
    assert failure["residual_aliases"] == [reappeared]
    assert controller._revocation_failures[active.phase_id] == hashlib.sha256(
        failure_path.read_bytes()
    ).hexdigest()


def test_source_and_receipt_file_descriptors_are_closed_after_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import eating_event.route2_candidate_overlap.linux_mount_controller as module

    opened: set[int] = set()
    original_open = module.os.open
    original_close = module.os.close

    def tracking_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened.add(descriptor)
        return descriptor

    def tracking_close(descriptor: int) -> None:
        original_close(descriptor)
        opened.discard(descriptor)

    monkeypatch.setattr(module.os, "open", tracking_open)
    monkeypatch.setattr(module.os, "close", tracking_close)
    mappings = _mappings()
    controller, _sources, _aliases, _mounted, _commands, _mountinfo = (
        _synthetic_controller(tmp_path, mappings)
    )
    active = _activate(controller, mappings, "candidate/o1/outer")
    assert not opened

    controller.revoke_role_view(active)

    assert not opened


def test_receipt_root_failure_during_revoke_still_attempts_every_unmount(
    tmp_path: Path,
) -> None:
    mappings = _mappings()
    controller, _sources, _aliases, mounted, commands, _mountinfo = _synthetic_controller(
        tmp_path,
        mappings,
    )
    active = _activate(controller, mappings, "candidate/o1/outer")
    controller._root_path_validator = lambda _path: (_ for _ in ()).throw(
        PermissionError("synthetic receipt root validation failure")
    )

    with pytest.raises(PermissionError, match="failure evidence could not be persisted"):
        controller.revoke_role_view(active)

    attempted_aliases = {
        command[1] for command in commands if command[0] == "umount"
    }
    assert attempted_aliases == {item.bind_path for item in mappings}
    assert not mounted
    assert controller.faulted
