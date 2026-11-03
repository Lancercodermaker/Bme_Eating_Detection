from __future__ import annotations

import hashlib
import threading

import pytest

from eating_event.route2_candidate_overlap.path_map import (
    ActiveRoleMountSet,
    ExactFileMapping,
    ExactPathMap,
    MountReceipt,
    canonical_manifest_bytes,
    file_mapping,
)


class SyntheticMountController:
    def __init__(
        self, *, omit_last: bool = False, wrong_manifest: bool = False,
        bad_revoke_receipt: bool = False,
    ) -> None:
        self.omit_last = omit_last
        self.wrong_manifest = wrong_manifest
        self.bad_revoke_receipt = bad_revoke_receipt
        self.mounted: list[str] = []
        self.revoked: list[str] = []

    def activate_role_view(self, *, manifest_sha256, role_id, mappings):
        self.mounted.append(role_id)
        selected = mappings[:-1] if self.omit_last else mappings
        mounts = tuple(
            MountReceipt(
                manifest_sha256=("f" * 64 if self.wrong_manifest else manifest_sha256),
                logical_path=item.logical_path,
                sha256=item.sha256,
                role_id=item.role_id,
                phase=item.phase,
                bind_path=item.bind_path,
                mount_id=100 + index,
            )
            for index, item in enumerate(selected)
        )
        return ActiveRoleMountSet(
            controller_run_id="synthetic-run",
            phase_id=f"phase-{len(self.mounted)}",
            receipt_sha256="d" * 64,
            mounts=mounts,
        )

    def revoke_role_view(self, active):
        self.revoked.append(active.phase_id)
        return "bad" if self.bad_revoke_receipt else "e" * 64


def _path_map(controller: SyntheticMountController) -> ExactPathMap:
    entries = tuple(
        file_mapping(
            f"C:\\route2\\{role.replace('/', '-')}-{index}.jsonl",
            hashlib.sha256(f"{role}:{index}".encode()).hexdigest(),
            role_id=role,
            phase=phase,
            bind_root="/run/route2-input",
        )
        for role, phase, index in (
            ("candidate/o1/outer", "stage_a_input", 1),
            ("candidate/o1/outer", "stage_a_reference", 2),
            ("candidate/o2/outer", "stage_a_input", 3),
            ("candidate/o2/outer", "stage_a_reference", 4),
        )
    )
    manifest = canonical_manifest_bytes("/run/route2-input", entries)
    return ExactPathMap(
        manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        bind_root="/run/route2-input",
        entries=entries,
        receipts=(),
        controller_receipt_sha256="c" * 64,
        controller_run_id="synthetic-run",
        phase_id="metadata-only",
        mount_controller=controller,
    )


def test_role_views_rotate_only_after_mount_revocation() -> None:
    controller = SyntheticMountController()
    path_map = _path_map(controller)
    first = path_map._entries
    with path_map.lease_role_view("candidate/o1/outer"):
        assert controller.mounted == ["candidate/o1/outer"]
        active_first = tuple(
            item for item in first
            if item[2] == "candidate/o1/outer"
        )
        assert len(active_first) == 2
        assert path_map.receipt_for(
            active_first[0][0], active_first[0][1], role_id=active_first[0][2], phase=active_first[0][3],
        ).mount_id == 100
        with path_map.lease_role_view("candidate/o1/outer"):
            assert controller.mounted == ["candidate/o1/outer"]
        with pytest.raises(PermissionError, match="another role"):
            with path_map.lease_role_view("candidate/o2/outer"):
                pass
    assert controller.revoked == ["phase-1"]
    assert path_map.controller_receipt_sha256 == "c" * 64
    assert path_map.phase_id == "metadata-only"
    with pytest.raises(PermissionError, match="active controller mount"):
        path_map.receipt_for(
            active_first[0][0], active_first[0][1], role_id=active_first[0][2], phase=active_first[0][3],
        )
    with path_map.lease_role_view("candidate/o2/outer"):
        assert controller.mounted == ["candidate/o1/outer", "candidate/o2/outer"]
    assert controller.revoked == ["phase-1", "phase-2"]
    assert path_map.controller_receipt_sha256 == "c" * 64


def test_role_view_activation_requires_every_exact_registered_file() -> None:
    controller = SyntheticMountController(omit_last=True)
    path_map = _path_map(controller)
    with pytest.raises(PermissionError, match="exact registered mapping set"):
        with path_map.lease_role_view("candidate/o1/outer"):
            pass
    assert controller.revoked == ["phase-1"]
    assert not path_map._receipts


@pytest.mark.parametrize("wrong_manifest", [False, True])
def test_role_view_rejects_partial_or_unbound_controller_receipts(wrong_manifest: bool) -> None:
    controller = SyntheticMountController(omit_last=not wrong_manifest, wrong_manifest=wrong_manifest)
    path_map = _path_map(controller)
    with pytest.raises(PermissionError):
        with path_map.lease_role_view("candidate/o1/outer"):
            pass
    assert controller.revoked == ["phase-1"]
    with pytest.raises(PermissionError, match="faulted"):
        with path_map.lease_role_view("candidate/o2/outer"):
            pass


def test_role_view_revocation_failure_locks_controller_instance() -> None:
    controller = SyntheticMountController(bad_revoke_receipt=True)
    path_map = _path_map(controller)
    with pytest.raises(PermissionError, match="revocation receipt"):
        with path_map.lease_role_view("candidate/o1/outer"):
            pass
    assert not path_map._receipts
    with pytest.raises(PermissionError, match="faulted"):
        with path_map.lease_role_view("candidate/o2/outer"):
            pass
    acquired = threading.Event()

    def acquire_from_another_thread() -> None:
        if path_map._mount_lock.acquire(timeout=1.0):
            acquired.set()
            path_map._mount_lock.release()

    teardown = threading.Thread(target=acquire_from_another_thread)
    teardown.start()
    teardown.join(timeout=2.0)
    assert not teardown.is_alive()
    assert acquired.is_set(), "failed revocation leaked the role-mount lock"
