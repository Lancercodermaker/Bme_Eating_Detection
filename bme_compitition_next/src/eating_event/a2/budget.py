"""Durable single-study attempt, wall-time and resource accounting."""

from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import time
from typing import Callable, Mapping, Sequence

from eating_event.a2.contracts import (
    DEFAULT_STUDY_ID,
    PREDECESSOR_001,
    PREDECESSOR_002,
    PREDECESSOR_FAMILY_001_002,
    STUDY_001_ID,
    STUDY_002_ID,
    STUDY_003_ID,
    expected_study_config,
)


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


def validate_predecessor_summary(actual: Mapping[str, object], expected: Mapping[str, object] = PREDECESSOR_001) -> dict[str, object]:
    if not isinstance(actual, Mapping) or any(actual.get(key) != value for key, value in expected.items()):
        raise StudyLedgerIntegrityError("A2-001 predecessor identity or resource summary mismatch")
    return dict(expected)


def validate_predecessor_family_summary(
    actual: Mapping[str, object],
    expected: Mapping[str, object] = PREDECESSOR_FAMILY_001_002,
) -> dict[str, object]:
    if not isinstance(actual, Mapping) or dict(actual) != dict(expected):
        raise StudyLedgerIntegrityError("A2-001+002 predecessor family identity or cumulative use mismatch")
    return dict(expected)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _output_tree_identity(path: Path) -> tuple[str, int, int]:
    rows = []
    total = 0
    for item in sorted((entry for entry in path.rglob("*") if entry.is_file()), key=lambda entry: entry.relative_to(path).as_posix()):
        size = item.stat().st_size
        total += size
        rows.append([item.relative_to(path).as_posix(), _sha256_file(item), size])
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), total, len(rows)


def verify_predecessor_001(
    workspace: str | Path,
    expected: Mapping[str, object] = PREDECESSOR_001,
) -> dict[str, object]:
    """Read and re-authenticate only the fixed A2-001 status/output/ledger evidence."""

    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    output = artifacts / "a2-context-verifier-v1-001"
    status_path = output / "run-status.json"
    external = artifacts / "a2-study-budget.jsonl"
    mirror = output / "a2-study-budget.jsonl"
    predecessor_lock = artifacts / "a2-study-budget.lock"
    config = root / "configs" / "a2-context-verifier-v1.json"
    if predecessor_lock.exists():
        raise StudyLedgerIntegrityError("A2-001 predecessor lock remains present")
    for path in (status_path, external, mirror, config):
        if not path.is_file():
            raise StudyLedgerIntegrityError(f"A2-001 predecessor evidence is missing: {path.name}")
    status_bytes = status_path.read_bytes()
    external_bytes = external.read_bytes()
    mirror_bytes = mirror.read_bytes()
    if external_bytes != mirror_bytes:
        raise StudyLedgerIntegrityError("A2-001 predecessor external/mirror ledgers differ")
    status = json.loads(status_bytes.decode("utf-8"))
    if not isinstance(status, dict) or status.get("status") != "INVALID":
        raise StudyLedgerIntegrityError("A2-001 predecessor is not terminal INVALID")
    config_sha = _sha256_file(config)
    if status.get("config_sha256") != config_sha:
        raise StudyLedgerIntegrityError("A2-001 predecessor status/config identity differs")
    records = []
    for line in external_bytes.decode("utf-8").splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or not isinstance(row.get("event"), str):
            raise StudyLedgerIntegrityError("A2-001 predecessor ledger is malformed")
        records.append(row)
    if not records or records[-1].get("event") != "study_status" or records[-1].get("status") != "INVALID":
        raise StudyLedgerIntegrityError("A2-001 predecessor ledger lacks terminal INVALID")
    starts: set[str] = set()
    active = 0.0
    fit_starts: set[str] = set()
    fit_wall = 0.0
    attempts = 0
    resource_rows = []
    for row in records:
        event = row["event"]
        if event == "invocation_start":
            starts.add(str(row["id"]))
        elif event == "invocation_end":
            starts.discard(str(row["id"]))
            active += float(row["duration_seconds"])
        elif event == "fit_reserve":
            attempts += 1
        elif event == "fit_start":
            fit_starts.add(str(row["role_id"]))
        elif event == "fit_end":
            fit_starts.discard(str(row["role_id"]))
            fit_wall += float(row["duration_seconds"])
        elif event == "startup_resources":
            resource_rows.append(row)
    if starts or fit_starts or len(resource_rows) != 1:
        raise StudyLedgerIntegrityError("A2-001 predecessor ledger has incomplete resource evidence")
    tree_sha, tree_bytes, tree_files = _output_tree_identity(output)
    actual = {
        "study_id": "a2-context-verifier-v1-001",
        "status": "INVALID",
        "run_status_sha256": hashlib.sha256(status_bytes).hexdigest(),
        "external_ledger_sha256": hashlib.sha256(external_bytes).hexdigest(),
        "mirror_ledger_sha256": hashlib.sha256(mirror_bytes).hexdigest(),
        "config_sha256": config_sha,
        "output_tree_sha256": tree_sha,
        "active_wall_seconds": active,
        "fit_wall_seconds": fit_wall,
        "verifier_fit_attempts": attempts,
        "rss_ceiling_bytes": int(resource_rows[0].get("rss_ceiling_bytes", 0)),
        "output_tree_bytes": tree_bytes,
        "external_ledger_bytes": len(external_bytes),
    }
    if tree_files != 8:
        raise StudyLedgerIntegrityError("A2-001 predecessor output tree file count changed")
    return validate_predecessor_summary(actual, expected)


def verify_predecessor_002(
    workspace: str | Path,
    expected: Mapping[str, object] = PREDECESSOR_002,
) -> dict[str, object]:
    """Re-authenticate the fixed, terminal A2-002 evidence without opening A1 sources."""

    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    output = artifacts / "a2-context-verifier-v1-002"
    status_path = output / "run-status.json"
    stop_path = output / "validation-stop-record.json"
    external = artifacts / "a2-study-budget-v1-002.jsonl"
    mirror = output / "a2-study-budget.jsonl"
    predecessor_lock = artifacts / "a2-study-budget-v1-002.lock"
    config_path = root / "configs" / "a2-context-verifier-v1-002.json"
    if predecessor_lock.exists():
        raise StudyLedgerIntegrityError("A2-002 predecessor lock remains present")
    for path in (status_path, stop_path, external, mirror, config_path):
        if not path.is_file():
            raise StudyLedgerIntegrityError(f"A2-002 predecessor evidence is missing: {path.name}")

    status_bytes = status_path.read_bytes()
    stop_bytes = stop_path.read_bytes()
    external_bytes = external.read_bytes()
    mirror_bytes = mirror.read_bytes()
    if external_bytes != mirror_bytes:
        raise StudyLedgerIntegrityError("A2-002 predecessor external/mirror ledgers differ")
    status = json.loads(status_bytes.decode("utf-8"))
    stop = json.loads(stop_bytes.decode("utf-8"))
    if not isinstance(status, dict) or status.get("status") != "INCOMPLETE_RESOURCE":
        raise StudyLedgerIntegrityError("A2-002 predecessor is not terminal INCOMPLETE_RESOURCE")
    if not isinstance(stop, dict) or stop.get("schema") != "a2_validation_stop_record_v1":
        raise StudyLedgerIntegrityError("A2-002 stop record is malformed")
    config_sha = _sha256_file(config_path)
    if status.get("config_sha256") != config_sha or stop.get("config_sha256") != config_sha:
        raise StudyLedgerIntegrityError("A2-002 predecessor status/config identity differs")
    # The historical compact run-status predates explicit study_id binding;
    # its fixed-path SHA plus the stop record and ledger provide that binding.
    if stop.get("study_id") != STUDY_002_ID:
        raise StudyLedgerIntegrityError("A2-002 predecessor study identity differs")
    if stop.get("audit_calls") != 1 or stop.get("run_calls") != 0 or stop.get("audit_ready") is not False:
        raise StudyLedgerIntegrityError("A2-002 predecessor call counts or READY state changed")
    if stop.get("audit_status") != "INCOMPLETE_RESOURCE" or stop.get("performance_state") != "NOT_EVALUATED":
        raise StudyLedgerIntegrityError("A2-002 predecessor terminal/performance state changed")

    rss = stop.get("rss_accounting")
    fit = stop.get("fit_accounting")
    active = stop.get("active_wall_accounting")
    disk = stop.get("disk_accounting")
    ledger_report = stop.get("ledger")
    if not all(isinstance(item, dict) for item in (rss, fit, active, disk, ledger_report)):
        raise StudyLedgerIntegrityError("A2-002 stop record resource accounting is incomplete")
    assert isinstance(rss, dict) and isinstance(fit, dict) and isinstance(active, dict)
    assert isinstance(disk, dict) and isinstance(ledger_report, dict)
    if (
        rss.get("ceiling_bytes") != PREDECESSOR_002["rss_ceiling_bytes"]
        or rss.get("last_recorded_accepted_peak_bytes") != PREDECESSOR_002["last_recorded_accepted_rss_bytes"]
        or rss.get("failing_measurement_bytes") is not None
        or fit.get("combined_fit_wall_seconds") != 0.0
        or fit.get("combined_verifier_fit_attempts") != 0
        or fit.get("candidate_fit_attempts") != 0
        or fit.get("candidate_predict_attempts") != 0
        or active.get("a2_audit_seconds") != PREDECESSOR_002["active_wall_seconds"]
        or active.get("combined_seconds") != PREDECESSOR_FAMILY_001_002["active_wall_seconds"]
        or ledger_report.get("terminal_status") != "INCOMPLETE_RESOURCE"
        or ledger_report.get("external_and_mirror_byte_equal") is not True
        or ledger_report.get("external_sha256") != hashlib.sha256(external_bytes).hexdigest()
        or ledger_report.get("mirror_sha256") != hashlib.sha256(mirror_bytes).hexdigest()
        or disk.get("family_bytes_at_stop_record") is None
    ):
        raise StudyLedgerIntegrityError("A2-002 stop record cumulative resource evidence changed")

    records: list[dict[str, object]] = []
    for line in external_bytes.decode("utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StudyLedgerIntegrityError("A2-002 predecessor ledger is malformed") from exc
        if not isinstance(row, dict) or not isinstance(row.get("event"), str):
            raise StudyLedgerIntegrityError("A2-002 predecessor ledger has an invalid record")
        records.append(row)
    if len(records) != int(ledger_report.get("record_count", -1)) or not records:
        raise StudyLedgerIntegrityError("A2-002 predecessor ledger record count changed")
    if records[0].get("event") != "predecessor" or records[0].get("predecessor") != PREDECESSOR_001:
        raise StudyLedgerIntegrityError("A2-002 predecessor ledger lacks its fixed A2-001 record")
    for row in records:
        if (
            row.get("study_id") != STUDY_002_ID
            or row.get("study_output") != "artifacts/a2-context-verifier-v1-002"
            or row.get("config_sha256") != config_sha
        ):
            raise StudyLedgerIntegrityError("A2-002 predecessor ledger identity binding changed")
    starts: dict[str, dict[str, object]] = {}
    active_seconds = 0.0
    fit_starts: set[str] = set()
    fit_seconds = 0.0
    attempts = 0
    audit_calls = 0
    run_calls = 0
    startup_rows: list[dict[str, object]] = []
    for row in records:
        event = row["event"]
        if event == "invocation_start":
            invocation_id = str(row["id"])
            starts[invocation_id] = row
            if row.get("mode") == "audit":
                audit_calls += 1
            elif row.get("mode") == "run":
                run_calls += 1
        elif event == "invocation_end":
            invocation_id = str(row["id"])
            if invocation_id not in starts:
                raise StudyLedgerIntegrityError("A2-002 predecessor ledger closes an unknown interval")
            starts.pop(invocation_id)
            active_seconds += float(row["duration_seconds"])
        elif event == "fit_reserve":
            attempts += 1
        elif event == "fit_start":
            fit_starts.add(str(row.get("role_id", "")))
        elif event == "fit_end":
            role_id = str(row.get("role_id", ""))
            if role_id not in fit_starts:
                raise StudyLedgerIntegrityError("A2-002 predecessor fit interval is malformed")
            fit_starts.remove(role_id)
            fit_seconds += float(row["duration_seconds"])
        elif event == "startup_resources":
            startup_rows.append(row)
    if starts or fit_starts or attempts != 0 or fit_seconds != 0.0:
        raise StudyLedgerIntegrityError("A2-002 predecessor ledger has open work or fit use")
    if audit_calls != 1 or run_calls != 0 or active_seconds != float(PREDECESSOR_002["active_wall_seconds"]):
        raise StudyLedgerIntegrityError("A2-002 predecessor ledger call count or active use changed")
    if len(startup_rows) != 1 or startup_rows[0].get("rss_ceiling_bytes") != PREDECESSOR_002["rss_ceiling_bytes"]:
        raise StudyLedgerIntegrityError("A2-002 predecessor startup resource record changed")

    tree_sha, tree_bytes, tree_files = _output_tree_identity(output)
    actual = {
        "study_id": STUDY_002_ID,
        "status": "INCOMPLETE_RESOURCE",
        "run_status_sha256": hashlib.sha256(status_bytes).hexdigest(),
        "stop_record_sha256": hashlib.sha256(stop_bytes).hexdigest(),
        "external_ledger_sha256": hashlib.sha256(external_bytes).hexdigest(),
        "mirror_ledger_sha256": hashlib.sha256(mirror_bytes).hexdigest(),
        "config_sha256": config_sha,
        "output_tree_sha256": tree_sha,
        "active_wall_seconds": active_seconds,
        "fit_wall_seconds": fit_seconds,
        "verifier_fit_attempts": attempts,
        "candidate_fit_attempts": int(fit.get("candidate_fit_attempts", -1)),
        "candidate_predict_attempts": int(fit.get("candidate_predict_attempts", -1)),
        "audit_calls": audit_calls,
        "run_calls": run_calls,
        "rss_ceiling_bytes": int(startup_rows[0].get("rss_ceiling_bytes", 0)),
        "startup_available_bytes": int(startup_rows[0].get("startup_available_bytes", 0)),
        "last_recorded_accepted_rss_bytes": int(rss.get("last_recorded_accepted_peak_bytes", 0)),
        "failing_measurement_bytes": rss.get("failing_measurement_bytes"),
        "output_tree_bytes": tree_bytes,
        "external_ledger_bytes": len(external_bytes),
    }
    if tree_files != 7:
        raise StudyLedgerIntegrityError("A2-002 predecessor output tree file count changed")
    return validate_predecessor_summary(actual, expected)


def verify_predecessor_family_002(
    workspace: str | Path,
    expected: Mapping[str, object] = PREDECESSOR_FAMILY_001_002,
) -> dict[str, object]:
    """Verify both terminal predecessors and derive their cumulative family use."""

    member_001 = verify_predecessor_001(workspace)
    member_002 = verify_predecessor_002(workspace)
    actual = {
        "schema": "a2_predecessor_family_v1",
        "members": [member_001, member_002],
        "active_wall_seconds": float(member_001["active_wall_seconds"]) + float(member_002["active_wall_seconds"]),
        "fit_wall_seconds": float(member_001["fit_wall_seconds"]) + float(member_002["fit_wall_seconds"]),
        "verifier_fit_attempts": int(member_001["verifier_fit_attempts"]) + int(member_002["verifier_fit_attempts"]),
        "candidate_fit_attempts": int(member_001.get("candidate_fit_attempts", 0)) + int(member_002["candidate_fit_attempts"]),
        "candidate_predict_attempts": int(member_001.get("candidate_predict_attempts", 0)) + int(member_002["candidate_predict_attempts"]),
    }
    return validate_predecessor_family_summary(actual, expected)


def _append_fsynced(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(record), sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


class StudyLedger:
    """External append-only A2 budget ledger mirrored inside the one output."""

    def __init__(
        self,
        artifacts_root: str | Path,
        output_dir: str | Path,
        limits: Mapping[str, object] | None = None,
        *,
        study_id: str = DEFAULT_STUDY_ID,
        predecessor: Mapping[str, object] | None = None,
        config_sha256: str | None = None,
    ) -> None:
        self.artifacts_root = Path(artifacts_root).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.workspace = self.artifacts_root.parent
        self.study_id = study_id
        expected = expected_study_config(study_id)
        fixed_output = (self.workspace / str(expected["study_output"])).resolve()
        if self.output_dir != fixed_output or self.output_dir.parent != self.artifacts_root:
            raise ValueError("A2 study output must use its fixed study namespace")
        if study_id == STUDY_001_ID:
            self.external_path = self.artifacts_root / "a2-study-budget.jsonl"
            self.lock_path = self.artifacts_root / "a2-study-budget.lock"
            self.predecessor = None
        else:
            self.external_path = self.workspace / str(expected["ledger_path"])
            self.lock_path = self.workspace / str(expected["lock_path"])
            self.predecessor = dict(predecessor or (PREDECESSOR_001 if study_id == STUDY_002_ID else PREDECESSOR_FAMILY_001_002))
        self.study_output_identity = str(expected["study_output"])
        self.config_sha256 = config_sha256
        if study_id in {STUDY_002_ID, STUDY_003_ID}:
            if (
                not isinstance(config_sha256, str)
                or len(config_sha256) != 64
                or any(character not in "0123456789abcdef" for character in config_sha256)
            ):
                raise ValueError(f"{study_id} ledger requires the fixed config SHA-256")
        self.mirror_path = self.output_dir / "a2-study-budget.jsonl"
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
        if self.study_id in {STUDY_002_ID, STUDY_003_ID} and records and records[0].get("event") != "predecessor":
            raise StudyLedgerIntegrityError(f"{self.study_id} ledger does not begin with its predecessor record")
        if self.study_id in {STUDY_002_ID, STUDY_003_ID} and records:
            for row in records:
                if (
                    row.get("study_id") != self.study_id
                    or row.get("study_output") != self.study_output_identity
                    or row.get("config_sha256") != self.config_sha256
                ):
                    raise StudyLedgerIntegrityError(f"{self.study_id} ledger study identity binding mismatch")
            predecessor_rows = [row for row in records if row.get("event") == "predecessor"]
            if (
                len(predecessor_rows) != 1
                or not isinstance(predecessor_rows[0].get("predecessor"), dict)
                or predecessor_rows[0]["predecessor"] != self.predecessor
            ):
                raise StudyLedgerIntegrityError(f"{self.study_id} ledger predecessor identity binding mismatch")
        return records

    def append(self, event: str, fields: Mapping[str, object] | None = None) -> dict[str, object]:
        record = {"event": event, **dict(fields or {})}
        if self.study_id in {STUDY_002_ID, STUDY_003_ID}:
            record.update({
                "study_id": self.study_id,
                "study_output": self.study_output_identity,
                "config_sha256": self.config_sha256,
            })
        record["recorded_epoch"] = time.time()
        _append_fsynced(self.external_path, record)
        _append_fsynced(self.mirror_path, record)
        return record

    def measure_disk(self, *, max_disk_bytes: int) -> int:
        if self.study_id == STUDY_001_ID:
            return check_disk_budget(
                self.output_dir,
                (self.external_path, self.lock_path),
                max_disk_bytes=max_disk_bytes,
            )
        if self.study_id == STUDY_002_ID:
            return check_study_family_disk_budget(
                self.workspace,
                self.output_dir,
                (self.external_path, self.lock_path),
                max_disk_bytes=max_disk_bytes,
            )
        return check_study_family_disk_budget_003(
            self.workspace,
            self.output_dir,
            (
                self.workspace / "artifacts" / "a2-study-budget.jsonl",
                self.workspace / "artifacts" / "a2-study-budget-v1-002.jsonl",
                self.external_path,
                self.lock_path,
            ),
            max_disk_bytes=max_disk_bytes,
        )

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

    def predecessor_usage(self) -> dict[str, float | int]:
        if self.study_id == STUDY_001_ID:
            return {"active_wall_seconds": 0.0, "fit_wall_seconds": 0.0, "verifier_fit_attempts": 0}
        rows = [row for row in self.records() if row.get("event") == "predecessor"]
        if len(rows) > 1:
            raise StudyLedgerIntegrityError(f"{self.study_id} ledger contains multiple predecessor records")
        source = rows[0].get("predecessor") if rows else (self.predecessor or {})
        if not isinstance(source, Mapping):
            raise StudyLedgerIntegrityError(f"{self.study_id} predecessor record is malformed")
        if rows and self.predecessor and dict(source) != self.predecessor:
            raise StudyLedgerIntegrityError(f"{self.study_id} predecessor record differs from its frozen identity")
        return {
            "active_wall_seconds": float(source.get("active_wall_seconds", 0.0)),
            "fit_wall_seconds": float(source.get("fit_wall_seconds", 0.0)),
            "verifier_fit_attempts": int(source.get("verifier_fit_attempts", 0)),
        }

    def local_active_wall_seconds(self, *, now: float | None = None) -> float:
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

    def active_wall_seconds(self, *, now: float | None = None) -> float:
        return float(self.predecessor_usage()["active_wall_seconds"]) + self.local_active_wall_seconds(now=now)

    def assert_wall_budget(self, *, now: float | None = None) -> float:
        used = self.active_wall_seconds(now=now)
        if used > float(self.limits["active_wall_seconds"]):
            raise StudyResourceError("total A2 active wall budget exceeded")
        return used

    def assert_can_start_invocation(self) -> float:
        used = self.active_wall_seconds()
        if used >= float(self.limits["active_wall_seconds"]):
            raise StudyResourceError("total A2 active wall budget leaves no time for another invocation")
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
        if self.study_id in {STUDY_002_ID, STUDY_003_ID}:
            self.predecessor_usage()


class FitAttemptLedger:
    def __init__(self, ledger: StudyLedger, *, on_fit_end: Callable[[str, str], None] | None = None) -> None:
        self.ledger = ledger
        self.on_fit_end = on_fit_end

    def attempt_count(self) -> int:
        inherited = int(self.ledger.predecessor_usage()["verifier_fit_attempts"])
        return inherited + sum(row["event"] == "fit_reserve" for row in self.ledger.records())

    def local_attempt_count(self) -> int:
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
        if status == "success" and self.on_fit_end is not None:
            self.on_fit_end(role_id, status)
        if self.fit_wall_seconds(now=current) > float(self.ledger.limits["fit_wall_seconds"]):
            raise StudyResourceError("cumulative verifier fit wall budget exceeded")
        return elapsed

    def local_fit_wall_seconds(self, *, now: float | None = None) -> float:
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

    def fit_wall_seconds(self, *, now: float | None = None) -> float:
        inherited = float(self.ledger.predecessor_usage()["fit_wall_seconds"])
        return inherited + self.local_fit_wall_seconds(now=now)

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


def check_disk_budget(
    output_dir: str | Path,
    external_paths: Sequence[str | Path],
    *,
    max_disk_bytes: int,
    family_paths: Sequence[str | Path] = (),
) -> int:
    root = Path(output_dir)
    if not root.is_dir():
        raise StudyResourceError("A2 study output is missing during disk measurement")
    total = 0
    counted: set[Path] = set()
    for item in (root, *(Path(path) for path in family_paths)):
        path = Path(item).resolve()
        if not path.exists():
            raise StudyResourceError(f"A2 family disk-accounting path is missing: {path.name}")
        files = (path,) if path.is_file() else tuple(child for child in path.rglob("*") if child.is_file())
        for file_path in files:
            resolved = file_path.resolve()
            if resolved not in counted:
                total += resolved.stat().st_size
                counted.add(resolved)
    for item in external_paths:
        path = Path(item).resolve()
        if path.is_file() and path not in counted:
            total += path.stat().st_size
            counted.add(path)
    if total > int(max_disk_bytes):
        raise StudyResourceError("A2 study disk budget exceeded")
    return total


def check_study_family_disk_budget(
    workspace: str | Path,
    output_002: str | Path,
    external_paths: Sequence[str | Path],
    *,
    max_disk_bytes: int,
) -> int:
    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    predecessor_output = artifacts / "a2-context-verifier-v1-001"
    predecessor_ledger = artifacts / "a2-study-budget.jsonl"
    predecessor_lock = artifacts / "a2-study-budget.lock"
    if not predecessor_output.is_dir() or not predecessor_ledger.is_file():
        raise StudyResourceError("A2-001 predecessor artifacts are missing from family disk accounting")
    if predecessor_lock.exists():
        raise StudyResourceError("A2-001 predecessor lock is present during A2-002 resource accounting")
    return check_disk_budget(
        output_002,
        external_paths,
        max_disk_bytes=max_disk_bytes,
        family_paths=(predecessor_output, predecessor_ledger),
    )


def check_study_family_disk_budget_003(
    workspace: str | Path,
    output_003: str | Path,
    external_paths: Sequence[str | Path],
    *,
    max_disk_bytes: int,
) -> int:
    """Count the complete 001+002+003 family, including both ledger mirrors."""

    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    outputs = (
        artifacts / "a2-context-verifier-v1-001",
        artifacts / "a2-context-verifier-v1-002",
    )
    external_001 = artifacts / "a2-study-budget.jsonl"
    external_002 = artifacts / "a2-study-budget-v1-002.jsonl"
    lock_001 = artifacts / "a2-study-budget.lock"
    lock_002 = artifacts / "a2-study-budget-v1-002.lock"
    if lock_001.exists() or lock_002.exists():
        raise StudyLedgerIntegrityError("A2-001/002 predecessor lock is present during A2-003 accounting")
    for old_output, old_external in zip(outputs, (external_001, external_002)):
        old_mirror = old_output / "a2-study-budget.jsonl"
        if not old_output.is_dir() or not old_external.is_file() or not old_mirror.is_file():
            raise StudyLedgerIntegrityError("A2-001/002 predecessor output or ledger is missing from family accounting")
        if old_external.read_bytes() != old_mirror.read_bytes():
            raise StudyLedgerIntegrityError("A2-001/002 predecessor external/mirror ledgers differ")
    output = Path(output_003).resolve()
    expected_output = (root / "artifacts" / "a2-context-verifier-v1-003").resolve()
    if output != expected_output:
        raise StudyLedgerIntegrityError("A2-003 disk accounting output path is not fixed")
    paths = tuple(Path(path).resolve() for path in external_paths)
    expected_003_external = (artifacts / "a2-study-budget-v1-003.jsonl").resolve()
    expected_003_lock = (artifacts / "a2-study-budget-v1-003.lock").resolve()
    if expected_003_external not in paths or expected_003_lock not in paths:
        raise StudyLedgerIntegrityError("A2-003 disk accounting omitted its external ledger or lock")
    mirror_003 = output / "a2-study-budget.jsonl"
    if expected_003_external.exists() != mirror_003.exists():
        raise StudyLedgerIntegrityError("A2-003 external/mirror ledger is missing")
    if expected_003_external.exists() and expected_003_external.read_bytes() != mirror_003.read_bytes():
        raise StudyLedgerIntegrityError("A2-003 external/mirror ledgers differ")
    return check_disk_budget(
        output,
        paths,
        max_disk_bytes=max_disk_bytes,
        family_paths=(*outputs, external_001, external_002),
    )


def compute_rss_ceiling(
    startup_available_bytes: int,
    predecessor_ceiling_bytes: int = int(PREDECESSOR_001["rss_ceiling_bytes"]),
) -> int:
    available = int(startup_available_bytes)
    prior = int(predecessor_ceiling_bytes)
    if available <= 0 or prior <= 0:
        raise StudyResourceError("startup or predecessor RSS ceiling is invalid")
    ceiling = min(8 * 1024**3, prior, int(available * 0.60))
    if ceiling <= 0:
        raise StudyResourceError("A2-002 RSS ceiling is invalid")
    return ceiling


def compute_003_rss_ceiling(startup_available_bytes: int) -> int:
    available = int(startup_available_bytes)
    if available < 5 * 1024**3:
        raise StudyResourceError("A2-003 startup available memory is below the 5 GiB admission floor")
    ceiling = min(4 * 1024**3, (available * 60) // 100)
    if ceiling <= 0:
        raise StudyResourceError("A2-003 RSS ceiling is invalid")
    return ceiling


def minimum_run_available_bytes(rss_ceiling_bytes: int) -> int:
    ceiling = int(rss_ceiling_bytes)
    if ceiling <= 0 or ceiling > 4 * 1024**3:
        raise StudyResourceError("A2-003 run headroom cannot be derived from a ceiling outside the approved 4 GiB limit")
    return max(5 * 1024**3, (ceiling * 100 + 59) // 60)


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
