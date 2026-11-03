from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


def test_source_snapshot_manifest_binds_complete_file_tree(tmp_path) -> None:
    from eating_event.route2_candidate_overlap.source_snapshot import (
        build_source_manifest,
        verify_source_snapshot,
    )

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "worker.py").write_bytes(b"synthetic source\n")
    (tmp_path / "config.json").write_bytes(b"{}\n")
    manifest = build_source_manifest(tmp_path)
    proof = verify_source_snapshot(
        tmp_path,
        manifest,
        expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
    )
    assert proof.file_count == 2
    assert proof.total_bytes == len(b"synthetic source\n{}\n")
    assert proof.manifest_sha256 == hashlib.sha256(manifest).hexdigest()


def test_snapshot_rejects_changed_or_unlisted_source_files(tmp_path) -> None:
    from eating_event.route2_candidate_overlap.source_snapshot import (
        build_source_manifest,
        verify_source_snapshot,
    )

    source = tmp_path / "worker.py"
    source.write_bytes(b"before")
    manifest = build_source_manifest(tmp_path)
    digest = hashlib.sha256(manifest).hexdigest()
    source.write_bytes(b"after")
    with pytest.raises(PermissionError, match="file bytes"):
        verify_source_snapshot(tmp_path, manifest, expected_manifest_sha256=digest)

    source.write_bytes(b"before")
    (tmp_path / "unlisted.py").write_bytes(b"extra")
    with pytest.raises(PermissionError, match="file set"):
        verify_source_snapshot(tmp_path, manifest, expected_manifest_sha256=digest)


def test_snapshot_rejects_noncanonical_manifest_and_symlinks(tmp_path, monkeypatch) -> None:
    from eating_event.route2_candidate_overlap.source_snapshot import (
        build_source_manifest,
        verify_source_snapshot,
    )

    (tmp_path / "source.py").write_bytes(b"fixed")
    manifest = build_source_manifest(tmp_path)
    digest = hashlib.sha256(manifest).hexdigest()
    with pytest.raises(PermissionError, match="canonical"):
        verify_source_snapshot(tmp_path, manifest + b" ", expected_manifest_sha256=hashlib.sha256(manifest + b" ").hexdigest())

    alias = tmp_path / "alias.py"
    alias.write_bytes(b"link target bytes")
    actual_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == alias or actual_is_symlink(path),
    )
    with pytest.raises(PermissionError, match="link"):
        build_source_manifest(tmp_path)


def test_readonly_mount_resolution_uses_most_specific_covering_mount() -> None:
    from eating_event.route2_candidate_overlap.source_snapshot import (
        require_readonly_mount,
    )

    mountinfo = (
        "36 25 0:32 / / rw,relatime - ext4 /dev/root rw\n"
        "41 36 7:1 / /opt/route2 ro,nosuid,nodev - ext4 /dev/loop4 ro\n"
        "42 41 7:1 / /opt/route2/source rw,relatime - ext4 /dev/loop4 rw\n"
    )
    with pytest.raises(PermissionError, match="read-only"):
        require_readonly_mount("/opt/route2/source/pkg.py", mountinfo)
    proof = require_readonly_mount("/opt/route2/venv/bin/python", mountinfo)
    assert (proof.mount_id, proof.mount_point, proof.filesystem) == (41, "/opt/route2", "ext4")


def test_imported_module_must_come_from_the_pinned_readonly_tree(tmp_path) -> None:
    from eating_event.route2_candidate_overlap.source_snapshot import (
        build_source_manifest,
        verify_snapshot_module,
    )

    module = tmp_path / "src" / "eating_event" / "route2_candidate_overlap" / "stage_b.py"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"synthetic module")
    manifest = build_source_manifest(tmp_path)
    mountinfo = "41 36 7:1 / /opt/route2/source ro,nosuid - ext4 /dev/loop4 ro\n"
    proof = verify_snapshot_module(
        tmp_path,
        module,
        manifest,
        expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        expected_module_relative_path="src/eating_event/route2_candidate_overlap/stage_b.py",
        mount_path="/opt/route2/source",
        mountinfo_text=mountinfo,
    )
    assert proof.module_relative_path == "src/eating_event/route2_candidate_overlap/stage_b.py"
    assert proof.mount.mount_id == 41

    other_module = tmp_path.parent / "active-worktree-stage-b.py"
    other_module.write_bytes(b"different active source")
    with pytest.raises(PermissionError, match="outside"):
        verify_snapshot_module(
            tmp_path,
            other_module,
            manifest,
            expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
            expected_module_relative_path="src/eating_event/route2_candidate_overlap/stage_b.py",
            mount_path="/opt/route2/source",
            mountinfo_text=mountinfo,
        )
