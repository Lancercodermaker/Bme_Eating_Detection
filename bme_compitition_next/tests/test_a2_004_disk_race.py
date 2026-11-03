"""Synthetic disk-accounting races; no A1 data or model calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from eating_event.a2.budget import StudyResourceError, check_disk_budget


def test_atomic_output_rename_is_remeasured_without_losing_final_bytes(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    temporary = output / "labels.jsonl.tmp"
    final = output / "labels.jsonl"
    temporary.write_bytes(b"1234567")
    original_is_file = Path.is_file
    moved = False

    def rename_after_listing(path: Path) -> bool:
        nonlocal moved
        answer = original_is_file(path)
        if path == temporary and answer and not moved:
            temporary.replace(final)
            moved = True
        return answer

    monkeypatch.setattr(Path, "is_file", rename_after_listing)
    measured = check_disk_budget(output, (), max_disk_bytes=7)
    assert moved and final.is_file()
    assert measured == 7


def test_missing_fixed_family_file_does_not_become_zero_bytes(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    fixed = tmp_path / "fixed"
    output.mkdir()
    fixed.mkdir()
    prior = fixed / "ledger.jsonl"
    prior.write_bytes(b"123")
    original_is_file = Path.is_file
    removed = False

    def remove_after_listing(path: Path) -> bool:
        nonlocal removed
        answer = original_is_file(path)
        if path == prior and answer and not removed:
            prior.unlink()
            removed = True
        return answer

    monkeypatch.setattr(Path, "is_file", remove_after_listing)
    with pytest.raises(StudyResourceError, match="missing|unavailable"):
        check_disk_budget(output, (), max_disk_bytes=10, family_paths=(fixed,))
    assert removed


def test_atomic_rename_does_not_waive_disk_ceiling(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    temporary = output / "labels.jsonl.tmp"
    final = output / "labels.jsonl"
    temporary.write_bytes(b"1234567")
    original_is_file = Path.is_file
    moved = False

    def rename_after_listing(path: Path) -> bool:
        nonlocal moved
        answer = original_is_file(path)
        if path == temporary and answer and not moved:
            temporary.replace(final)
            moved = True
        return answer

    monkeypatch.setattr(Path, "is_file", rename_after_listing)
    with pytest.raises(StudyResourceError, match="disk budget exceeded"):
        check_disk_budget(output, (), max_disk_bytes=6)
    assert moved and final.is_file()
