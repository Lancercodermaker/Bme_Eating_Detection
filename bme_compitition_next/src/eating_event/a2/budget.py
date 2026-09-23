"""Durable single-study attempt, wall-time and resource accounting."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Mapping, Sequence


TERMINAL_STATUSES = {
    "COMPLETE",
    "INVALID",
    "VERIFIER_DATA_INSUFFICIENT",
    "INCOMPLETE_RESOURCE",
    "INCOMPLETE_INTERRUPTED",
}


class StudyResourceError(RuntimeError):
    pass


class StudyInterrupted(RuntimeError):
    pass


class StudyLedgerIntegrityError(StudyResourceError, ValueError):
    """A missing or inconsistent durable ledger invalidates resource proof."""


def _append_fsynced(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(record), sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


class StudyLedger:
    """External append-only A2 budget ledger mirrored inside the one output."""

    def __init__(self, artifacts_root: str | Path, output_dir: str | Path, limits: Mapping[str, object] | None = None) -> None:
        self.artifacts_root = Path(artifacts_root).resolve()
        self.output_dir = Path(output_dir).resolve()
        if self.output_dir.parent != self.artifacts_root or self.output_dir.name != "a2-context-verifier-v1-001":
            raise ValueError("A2 study output must use its one fixed directory")
        self.external_path = self.artifacts_root / "a2-study-budget.jsonl"
        self.mirror_path = self.output_dir / "a2-study-budget.jsonl"
        self.lock_path = self.artifacts_root / "a2-study-budget.lock"
        self.limits = dict(limits or {
            "verifier_fit_attempts": 25,
            "active_wall_seconds": 7200,
            "fit_wall_seconds": 3600,
            "threads": 4,
            "disk_bytes": 1024**3,
        })
        if (self.external_path.exists() or self.mirror_path.exists()) and not self.output_dir.is_dir():
            raise StudyLedgerIntegrityError("study output is missing while the external ledger remains")
        self.records()

    def records(self) -> list[dict[str, object]]:
        external_exists = self.external_path.is_file()
        mirror_exists = self.mirror_path.is_file()
        if external_exists != mirror_exists:
            raise StudyLedgerIntegrityError("study ledger mirror is missing")
        if not external_exists:
            return []
        external = b""
        mirror = b""
        for attempt in range(5):
            external = self.external_path.read_bytes()
            mirror = self.mirror_path.read_bytes()
            if external == mirror:
                break
            if attempt < 4:
                time.sleep(0.02)
        else:
            raise StudyLedgerIntegrityError("study ledger mirror differs from external ledger")
        records: list[dict[str, object]] = []
        for line in external.decode("utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StudyLedgerIntegrityError("study ledger is corrupt") from exc
            if not isinstance(row, dict) or not isinstance(row.get("event"), str):
                raise StudyLedgerIntegrityError("study ledger contains an invalid record")
            records.append(row)
        return records

    def append(self, event: str, fields: Mapping[str, object] | None = None) -> dict[str, object]:
        record = {"event": event, **dict(fields or {}), "recorded_epoch": time.time()}
        _append_fsynced(self.external_path, record)
        _append_fsynced(self.mirror_path, record)
        return record

    def assert_no_unclosed_intervals(self) -> None:
        records = self.records()
        starts: dict[str, dict[str, object]] = {}
        for record in records:
            if record["event"] == "invocation_start":
                starts[str(record["id"])] = record
            elif record["event"] == "invocation_end":
                starts.pop(str(record["id"]), None)
        if starts:
            raise StudyResourceError("unclosed audit/run wall interval cannot be measured")
        reserved = {str(r["role_id"]) for r in records if r["event"] == "fit_reserve"}
        starts_fit = {str(r["role_id"]) for r in records if r["event"] == "fit_start"}
        ends_fit = {str(r["role_id"]) for r in records if r["event"] == "fit_end"}
        if starts_fit - ends_fit or reserved - starts_fit:
            raise StudyResourceError("unclosed verifier fit attempt cannot be measured")

    def active_wall_seconds(self, *, now: float | None = None) -> float:
        current = time.monotonic() if now is None else float(now)
        starts: dict[str, float] = {}
        completed = 0.0
        for record in self.records():
            if record["event"] == "invocation_start":
                starts[str(record["id"])] = float(record["monotonic"])
            elif record["event"] == "invocation_end":
                completed += float(record["duration_seconds"])
                starts.pop(str(record["id"]), None)
        return completed + sum(max(0.0, current - started) for started in starts.values())

    def assert_wall_budget(self, *, now: float | None = None) -> float:
        used = self.active_wall_seconds(now=now)
        if used > float(self.limits["active_wall_seconds"]):
            raise StudyResourceError("total A2 active wall budget exceeded")
        return used

    def mark_status(self, status: str, **fields: object) -> None:
        if status not in {"AUDITING", "AUDIT_READY", "RUNNING", *TERMINAL_STATUSES}:
            raise ValueError("invalid A2 study status")
        self.append("study_status", {"status": status, **fields})

    def current_status(self) -> str | None:
        rows = [row for row in self.records() if row["event"] == "study_status"]
        return str(rows[-1]["status"]) if rows else None

    def assert_can_start_audit(self) -> None:
        records = self.records()
        if records or self.external_path.exists() or self.mirror_path.exists():
            raise ValueError("A2 audit was already started; study retry is forbidden")

    def assert_can_start_run(self) -> None:
        status = self.current_status()
        if status in TERMINAL_STATUSES:
            raise ValueError("A2 study has a terminal status")
        if status != "AUDIT_READY":
            raise ValueError("run requires a hash-matched AUDIT_READY study")
        if any(row["event"] == "invocation_start" and row.get("mode") == "run" for row in self.records()):
            raise ValueError("A2 run already started; restart is forbidden")


class FitAttemptLedger:
    def __init__(self, ledger: StudyLedger) -> None:
        self.ledger = ledger

    def attempt_count(self) -> int:
        return sum(row["event"] == "fit_reserve" for row in self.ledger.records())

    def reserve_fit(self, role_id: str) -> None:
        if not role_id:
            raise ValueError("verifier role is required")
        rows = self.ledger.records()
        if any(row["event"] == "fit_reserve" and row.get("role_id") == role_id for row in rows):
            raise ValueError(f"verifier role already reserved: {role_id}")
        if self.attempt_count() >= int(self.ledger.limits["verifier_fit_attempts"]):
            raise StudyResourceError("A2 verifier fit-attempt budget exhausted")
        self.ledger.append("fit_reserve", {"role_id": role_id, "attempt": self.attempt_count() + 1})

    def start_fit(self, role_id: str, *, now: float | None = None) -> None:
        rows = self.ledger.records()
        if not any(row["event"] == "fit_reserve" and row.get("role_id") == role_id for row in rows):
            raise ValueError("verifier fit was not reserved")
        if any(row["event"] == "fit_start" and row.get("role_id") == role_id for row in rows):
            raise ValueError("verifier fit attempt already started")
        self.ledger.append("fit_start", {"role_id": role_id, "monotonic": time.monotonic() if now is None else float(now)})

    def end_fit(self, role_id: str, status: str, *, now: float | None = None) -> float:
        current = time.monotonic() if now is None else float(now)
        rows = self.ledger.records()
        starts = [row for row in rows if row["event"] == "fit_start" and row.get("role_id") == role_id]
        if not starts or any(row["event"] == "fit_end" and row.get("role_id") == role_id for row in rows):
            raise ValueError("verifier fit interval is missing or already closed")
        elapsed = max(0.0, current - float(starts[-1]["monotonic"]))
        self.ledger.append("fit_end", {"role_id": role_id, "status": status, "duration_seconds": elapsed})
        if self.fit_wall_seconds(now=current) > float(self.ledger.limits["fit_wall_seconds"]):
            raise StudyResourceError("cumulative verifier fit wall budget exceeded")
        return elapsed

    def fit_wall_seconds(self, *, now: float | None = None) -> float:
        current = time.monotonic() if now is None else float(now)
        starts: dict[str, float] = {}
        completed = 0.0
        for row in self.ledger.records():
            if row["event"] == "fit_start":
                starts[str(row["role_id"])] = float(row["monotonic"])
            elif row["event"] == "fit_end":
                completed += float(row["duration_seconds"])
                starts.pop(str(row["role_id"]), None)
        return completed + sum(max(0.0, current - started) for started in starts.values())

    def assert_fit_wall_budget(self, *, now: float | None = None) -> float:
        used = self.fit_wall_seconds(now=now)
        if used > float(self.ledger.limits["fit_wall_seconds"]):
            raise StudyResourceError("cumulative verifier fit wall budget exceeded")
        return used


def check_rss_ceiling(value: int | None, *, max_rss_bytes: int) -> int:
    if value is None or int(value) <= 0:
        raise StudyResourceError("process-tree RSS measurement unavailable")
    if int(value) > int(max_rss_bytes):
        raise StudyResourceError("process-tree RSS ceiling exceeded")
    return int(value)


def check_disk_budget(output_dir: str | Path, external_paths: Sequence[str | Path], *, max_disk_bytes: int) -> int:
    root = Path(output_dir)
    if not root.is_dir():
        raise StudyResourceError("A2 study output is missing during disk measurement")
    total = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    for item in external_paths:
        path = Path(item)
        if path.is_file():
            total += path.stat().st_size
    if total > int(max_disk_bytes):
        raise StudyResourceError("A2 study disk budget exceeded")
    return total


def require_environment(actual: Mapping[str, object], expected: Mapping[str, object]) -> None:
    actual_libraries = actual.get("libraries")
    expected_libraries = expected.get("libraries")
    if not isinstance(actual_libraries, Mapping) or not isinstance(expected_libraries, Mapping):
        raise ValueError("environment version manifest is incomplete")
    if str(actual.get("python", "")).split()[0] != str(expected.get("python", "")):
        raise ValueError("environment version mismatch for Python")
    for name, version in expected_libraries.items():
        if actual_libraries.get(name) != version:
            raise ValueError(f"environment version mismatch for {name}")
