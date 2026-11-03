"""Auditable run artifacts and the sole telemetry writer."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Literal, Mapping, Iterable

from eating_event.telemetry import (
    EventType,
    build_telemetry_event,
    validate_telemetry_payload,
)


def _json_default(value: object) -> object:
    if hasattr(value, "item"):
        return value.item()  # type: ignore[no-any-return]
    if hasattr(value, "tolist"):
        return value.tolist()  # type: ignore[no-any-return]
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"object is not JSON serializable: {type(value)!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RunArtifact:
    """Write a bounded, self-describing artifact directory for one run."""

    def __init__(self, root: str | Path, run_id: str) -> None:
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("run_id must be a non-empty directory name")
        self.root = (Path(root).expanduser().resolve() / run_id).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.context = {
            "run_id": run_id,
            "project_id": "bme_compitition_next",
            "workflow_path": "RESEARCH",
            "execution_mode": "INLINE",
            "execution_backend": "executing-plans",
            "capability_tags": ["machine-learning", "data-contracts"],
            "loaded_profiles": ["Machine Learning"],
        }
        self._event_ids: set[str] = set()
        self._event_types: list[str] = []
        self._finalized = False

    def _safe_path(self, relative_path: str | Path) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("artifact path escapes run directory")
        return target

    def write_json(self, relative_path: str, value: object) -> None:
        if self._finalized:
            raise ValueError("artifact is already finalized")
        target = self._safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )

    def write_jsonl(self, relative_path: str, records: Iterable[Mapping[str, object]]) -> None:
        if self._finalized:
            raise ValueError("artifact is already finalized")
        target = self._safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")

    def record_event(self, event_type: EventType, payload: Mapping[str, object]) -> None:
        if self._finalized:
            raise ValueError("artifact is already finalized")
        validate_telemetry_payload(event_type, payload)
        event = build_telemetry_event(event_type, payload, run_context=self.context)
        if event["event_id"] in self._event_ids:
            raise ValueError("duplicate telemetry event_id")
        self._event_ids.add(event["event_id"])
        self._event_types.append(event_type)
        self.write_jsonl("telemetry.jsonl", [event])

    def _artifact_files(self) -> list[Path]:
        return sorted(
            path
            for path in self.root.rglob("*")
            if path.is_file() and path.name not in {"manifest.json", "checksums.json"}
        )

    def finalize(self) -> dict[str, object]:
        if self._finalized:
            raise ValueError("artifact is already finalized")
        required = {"run_start", "gate_result", "run_end"}
        missing = sorted(required.difference(self._event_types))
        if missing:
            raise ValueError(f"artifact lifecycle missing {', '.join(missing)}")
        files = self._artifact_files()
        checksums = {
            str(path.relative_to(self.root)).replace("\\", "/"): _sha256(path)
            for path in files
        }
        self.write_json("checksums.json", checksums)
        file_names = sorted([*checksums, "checksums.json"])
        try:
            git_revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            git_revision = None
        manifest: dict[str, object] = {
            "schema_version": "artifact_v1",
            "run_id": self.context["run_id"],
            "context": self.context,
            "files": file_names,
            "checksums": checksums,
            "git_revision": git_revision,
            "environment": {"python": platform.python_version()},
            "finalized_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_json("manifest.json", manifest)
        self._finalized = True
        return manifest
