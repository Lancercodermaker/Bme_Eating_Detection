"""No-data checks for Route 2's Linux admission accounting."""

import json
import os
import threading
import time

import pytest

from eating_event.route2_candidate_overlap.budget import (
    AppendOnlyLedger,
    BudgetLimits,
    ResourceSnapshot,
    require_stage_filesystem,
    require_precreate_order,
    require_two_layer_startup_free,
)
from eating_event.route2_candidate_overlap.contracts import StudyStage
from eating_event.route2_candidate_overlap.gt_provider import TruthReadScope


def test_terminal_ledger_record_persists_monotonic_event_time(tmp_path) -> None:
    ledger = AppendOnlyLedger(tmp_path / "synthetic.jsonl", tmp_path / "synthetic.lock", tmp_path / "synthetic")
    ledger._fd = os.open(ledger.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    started = time.monotonic_ns()
    ledger.append("invocation_started", {"monotonic_ns": started, "invocation_id": "synthetic"})

    ledger.terminal("INCOMPLETE_RESOURCE", evidence={})
    ledger.close()
    terminal = json.loads(ledger.path.read_bytes().splitlines()[-1])
    terminal_ns = terminal["entry"]["payload"].get("monotonic_ns")

    assert type(terminal_ns) is int
    assert started <= terminal_ns <= time.monotonic_ns()


def _snapshot(guest_free: int, host_free: int) -> ResourceSnapshot:
    return ResourceSnapshot(
        process_tree_rss_bytes=0,
        study_disk_peak_bytes=0,
        compute_workers=1,
        available_ram_bytes=8 * 1024**3,
        study_disk_current_bytes=0,
        guest_backing_free_bytes=guest_free,
        guest_backing_mount_id="80",
        guest_backing_device="/dev/sdd",
        windows_vhdx_path=r"C:\\Users\\synthetic\\ext4.vhdx",
        windows_volume_id="synthetic-volume-guid",
        windows_volume_free_bytes=host_free,
        study_mount_id="scratch-mount-1",
        study_device="/dev/loop999",
        study_fs_capacity_bytes=2 * 1024**3,
        study_fs_uuid="synthetic-fs-uuid",
        study_loop_device="/dev/loop999",
        study_image_path="/var/lib/route2-scratch/synthetic.ext4",
        study_image_dev=42,
        study_image_inode=99,
        study_image_length_bytes=2 * 1024**3,
        study_image_allocated_bytes=0,
    )


@pytest.mark.parametrize("guest_free,host_free", [
    (8 * 1024**3 - 1, 9 * 1024**3),
    (9 * 1024**3, 8 * 1024**3 - 1),
])
def test_both_backing_layers_must_have_eight_gib(guest_free: int, host_free: int) -> None:
    with pytest.raises(RuntimeError, match="free"):
        require_two_layer_startup_free(_snapshot(guest_free, host_free), BudgetLimits())


def test_virtual_free_does_not_substitute_for_host_free() -> None:
    snapshot = _snapshot(1_000 * 1024**3, 9 * 1024**3)
    require_two_layer_startup_free(snapshot, BudgetLimits())


def test_identity_required_for_two_layer_check() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    object.__setattr__(snapshot, "windows_volume_id", "")
    with pytest.raises(PermissionError, match="identity"):
        require_two_layer_startup_free(snapshot, BudgetLimits())


def test_stage_a_filesystem_capacity_is_an_os_gate() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    expected = _snapshot(9 * 1024**3, 9 * 1024**3)
    require_stage_filesystem(snapshot, expected, 2 * 1024**3)
    object.__setattr__(snapshot, "study_fs_capacity_bytes", 2 * 1024**3 + 1)
    with pytest.raises(RuntimeError, match="capacity"):
        require_stage_filesystem(snapshot, expected, 2 * 1024**3)


def test_stage_transition_cannot_switch_devices() -> None:
    snapshot = _snapshot(9 * 1024**3, 9 * 1024**3)
    expected = _snapshot(9 * 1024**3, 9 * 1024**3)
    with pytest.raises(PermissionError, match="mount"):
        object.__setattr__(snapshot, "study_fs_uuid", "another-fs")
        require_stage_filesystem(snapshot, expected, 4 * 1024**3)


def test_two_layer_free_must_precede_image_creation() -> None:
    floor = BudgetLimits().startup_free_disk_bytes
    require_precreate_order(100, 110, 120, floor, floor, floor)
    with pytest.raises(PermissionError, match="pre-create"):
        require_precreate_order(100, 120, 110, floor, floor, floor)
    with pytest.raises(RuntimeError, match="free"):
        require_precreate_order(100, 110, 120, floor, floor - 1, floor)


def test_training_gt_release_requires_durable_unrevoked_event(tmp_path) -> None:
    """A fresh ledger object reconstructs the same gate from scratch bytes."""

    study_root = tmp_path / "synthetic-study"
    ledger_path = tmp_path / "synthetic-budget.jsonl"
    lock_path = tmp_path / "synthetic.lock"
    ledger = AppendOnlyLedger(ledger_path, lock_path, study_root)
    ledger._fd = os.open(ledger_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND, 0o600)
    ledger._owner_thread_id = threading.get_ident()
    scope = TruthReadScope(
        stage=StudyStage.TRAIN_LABELS,
        outer_id="synthetic-outer",
        role_ids=("synthetic-role",),
        participants=("synthetic-participant",),
        eligibility_field="training_eligibility",
        consumer="candidate_labeler",
        role_graph_sha256="a" * 64,
        participant_scope_attestation="b" * 64,
    )
    entry_hash = ledger.mark_stage_b_entry({})
    assert len(entry_hash) == 64
    with pytest.raises(PermissionError, match="Stage B"):
        ledger.record_gt_release(scope)
    ledger.mark_stage_b_volume_expanded(entry_hash, {"study_mount_id": "scratch-mount-1"})
    release_hash = ledger.record_gt_release(scope)
    with pytest.raises(RuntimeError, match="active GT"):
        ledger.terminal("INCOMPLETE_RESOURCE", evidence={})
    ledger.close()
    fresh_reader = AppendOnlyLedger(ledger_path, lock_path, study_root)
    fresh_reader.require_gt_release(scope, release_hash)

    ledger._fd = os.open(ledger_path, os.O_WRONLY | os.O_APPEND)
    ledger.record_gt_revoke(scope, release_hash, "c" * 64)
    ledger.close()
    with pytest.raises(PermissionError, match="revoked"):
        fresh_reader.require_gt_release(scope, release_hash)
