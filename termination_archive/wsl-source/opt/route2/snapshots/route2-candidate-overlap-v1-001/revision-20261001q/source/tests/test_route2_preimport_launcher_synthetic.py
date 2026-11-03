"""Synthetic no-project-data tests for the external pre-import launcher."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


def _load_launcher():
    path = Path(__file__).parents[1] / "scripts" / "route2_preimport_launcher.py"
    spec = importlib.util.spec_from_file_location("route2_preimport_launcher", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest(root: Path) -> bytes:
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        data = path.read_bytes()
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return json.dumps(
        {"schema": "route2_immutable_source_snapshot_v1", "files": entries},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _mountinfo(path: str, *, flags: str = "ro,relatime") -> str:
    return f"41 25 7:1 / {path} {flags} - ext4 /dev/loop-test ro\n"


def test_preimport_verifier_accepts_only_exact_ro_mounted_complete_tree(tmp_path: Path) -> None:
    launcher = _load_launcher()
    root = tmp_path / "source"
    module = root / "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"synthetic bootstrap source; never imported by this test")
    manifest = _manifest(root)

    handed_off: list[str] = []
    proof, result = launcher.verify_then_handoff(
        root,
        manifest,
        expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        expected_module_relative_path=(
            "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
        ),
        mount_path="/tmp/synthetic-route2-source",
        mountinfo_text=_mountinfo("/tmp/synthetic-route2-source"),
        handoff=lambda: (handed_off.append("exec") or "handoff-result"),
        require_linux_root=False,
    )

    assert result == "handoff-result"
    assert handed_off == ["exec"]
    assert proof.file_count == 1
    assert proof.total_bytes == len(module.read_bytes())
    assert proof.manifest_sha256 == hashlib.sha256(manifest).hexdigest()


@pytest.mark.parametrize(
    "failure", ["bytes", "manifest", "mount", "parent_mount", "duplicate_mount", "module"]
)
def test_preimport_verifier_rejects_before_any_import_or_exec(
    tmp_path: Path, failure: str,
) -> None:
    launcher = _load_launcher()
    root = tmp_path / "source"
    module = root / "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"verified synthetic source")
    manifest = _manifest(root)
    expected_manifest_sha = hashlib.sha256(manifest).hexdigest()
    expected_module = "src/eating_event/route2_candidate_overlap/admission_bootstrap.py"
    mount_path = "/tmp/synthetic-route2-source"
    mountinfo = _mountinfo(mount_path)
    if failure == "bytes":
        module.write_bytes(b"changed after manifest creation")
    elif failure == "manifest":
        expected_manifest_sha = "0" * 64
    elif failure == "mount":
        mountinfo = _mountinfo(mount_path, flags="rw,relatime")
    elif failure == "parent_mount":
        mountinfo = _mountinfo("/tmp", flags="ro,relatime")
    elif failure == "duplicate_mount":
        mountinfo = _mountinfo(mount_path) + _mountinfo(mount_path, flags="rw,relatime").replace(
            "41 ", "42 ", 1,
        )
    elif failure == "module":
        expected_module = "src/eating_event/route2_candidate_overlap/not_bootstrap.py"

    imported_or_executed: list[str] = []

    def after_verification() -> None:
        imported_or_executed.append("exec")

    with pytest.raises(PermissionError):
        launcher.verify_then_handoff(
            root,
            manifest,
            expected_manifest_sha256=expected_manifest_sha,
            expected_module_relative_path=expected_module,
            mount_path=mount_path,
            mountinfo_text=mountinfo,
            handoff=after_verification,
            require_linux_root=False,
        )
    assert imported_or_executed == []
