"""Fail-closed active, disk, RSS, and fit-attempt accounting for Route 3."""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Mapping


class Route3ResourceError(RuntimeError):
    """Raised when the frozen Route 3 resource envelope is exceeded."""


def _process_tree_rss() -> int:
    import psutil

    process = psutil.Process(os.getpid())
    total = process.memory_info().rss
    for child in process.children(recursive=True):
        try:
            total += child.memory_info().rss
        except psutil.Error:
            continue
    return int(total)


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError as exc:
                raise Route3ResourceError("could not measure Route 3 output disk use") from exc
    return total


class Route3Budget:
    """Append-only one-run ledger with a fresh audit/run namespace."""

    study_id = "route3-matching-aware-v1-001"

    def __init__(
        self,
        *,
        output_dir: str | Path,
        ledger_path: str | Path,
        lock_path: str | Path,
        config_sha256: str,
        limits: Mapping[str, object],
        startup_available_bytes: int,
        mode: str,
        study_id: str = "route3-matching-aware-v1-001",
        rss_reader: Callable[[], int] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if mode not in {"audit", "run"}:
            raise ValueError("Route 3 budget mode must be audit or run")
        if len(config_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in config_sha256):
            raise ValueError("Route 3 config hash is malformed")
        self.output_dir = Path(output_dir).resolve()
        self.ledger_path = Path(ledger_path).resolve()
        self.lock_path = Path(lock_path).resolve()
        self.study_id = str(study_id)
        if not self.study_id.startswith("route3-matching-aware-v1-"):
            raise ValueError("Route 3 budget study identity is invalid")
        self.config_sha256 = config_sha256
        self.limits = dict(limits)
        self.rss_ceiling = min(
            int(self.limits["rss_absolute_bytes"]),
            int(startup_available_bytes * float(self.limits["rss_startup_fraction"])),
        )
        self.rss_reader = rss_reader or _process_tree_rss
        self.clock = clock or time.monotonic
        self.mode = mode
        self.started = self.clock()
        self.fit_started: dict[str, float] = {}
        self.prior_active_seconds = 0.0
        self.prior_fit_seconds = 0.0
        self.prior_fit_attempts = 0
        self.current_fit_wall_seconds = 0.0
        self.current_fit_attempts = 0
        self.max_rss = 0
        self._resource_failure: str | None = None
        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._closed = False

        self.output_dir.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            if mode == "audit":
                if self.output_dir.exists() or self.ledger_path.exists():
                    raise ValueError("Route 3 namespace already exists; no reset or retry is allowed")
                self.output_dir.mkdir(parents=True)
                self._append("study_start", {
                    "study_id": self.study_id,
                    "config_sha256": self.config_sha256,
                    "limits": self.limits,
                    "rss_ceiling_bytes": self.rss_ceiling,
                    "startup_available_bytes": int(startup_available_bytes),
                })
            else:
                if not self.output_dir.is_dir() or not self.ledger_path.is_file():
                    raise ValueError("Route 3 run requires the existing audit-ready namespace")
                records = self._read_records()
                if not records or records[0].get("event") != "study_start":
                    raise ValueError("Route 3 budget ledger has no frozen study start")
                if any(row.get("config_sha256") != self.config_sha256 for row in records):
                    raise ValueError("Route 3 config hash differs from its budget ledger")
                statuses = [row.get("status") for row in records if row.get("event") == "status"]
                if not statuses or statuses[-1] != "AUDIT_READY":
                    raise ValueError("Route 3 run requires an AUDIT_READY status")
                if any(row.get("event") == "study_terminal" for row in records):
                    raise ValueError("Route 3 study is already terminal; retries are forbidden")
                if any(
                    row.get("event") == "invocation_start" and row.get("mode") == "run"
                    for row in records
                ):
                    raise ValueError("Route 3 run invocation already exists; retries are forbidden")
                self.prior_active_seconds = sum(
                    float(row.get("duration_seconds", 0.0))
                    for row in records if row.get("event") == "invocation_end"
                )
                self.prior_fit_seconds = sum(
                    float(row.get("duration_seconds", 0.0))
                    for row in records if row.get("event") == "fit_ended"
                )
                self.prior_fit_attempts = sum(row.get("event") == "fit_reserved" for row in records)
            self._append("invocation_start", {"mode": mode, "monotonic": self.started})
            self._monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
            self._monitor_thread.start()
        except Exception:
            self._release_lock()
            raise

    def _acquire_lock(self) -> None:
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ValueError("Route 3 lock exists; refuse concurrent or interrupted rerun") from exc
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(f"{os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _release_lock(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass

    def _read_records(self) -> list[dict[str, object]]:
        records = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or value.get("study_id") != self.study_id:
                raise ValueError("Route 3 budget ledger contains a foreign record")
            records.append(value)
        return records

    def _append(self, event: str, values: Mapping[str, object]) -> None:
        row = {
            "study_id": self.study_id,
            "config_sha256": self.config_sha256,
            "event": event,
            **dict(values),
        }
        with self.ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _active_used(self) -> float:
        current = max(0.0, self.clock() - self.started)
        return self.prior_active_seconds + current

    def _fit_attempts(self) -> int:
        return self.prior_fit_attempts + self.current_fit_attempts

    def _fit_wall_used(self) -> float:
        active_fit_seconds = sum(max(0.0, self.clock() - started) for started in self.fit_started.values())
        return self.prior_fit_seconds + self.current_fit_wall_seconds + active_fit_seconds

    def _check_measurements(self) -> None:
        active = self._active_used()
        if active > float(self.limits["active_wall_seconds"]):
            raise Route3ResourceError("Route 3 active wall limit exceeded")
        try:
            rss = int(self.rss_reader())
            disk = _tree_bytes(self.output_dir)
            disk += self.ledger_path.stat().st_size if self.ledger_path.exists() else 0
            disk += self.lock_path.stat().st_size if self.lock_path.exists() else 0
            max_threads = self.limits.get("threads")
            if max_threads is not None:
                from threadpoolctl import threadpool_info

                counts = [int(item.get("num_threads", 1)) for item in threadpool_info()]
                if not counts:
                    raise RuntimeError("threadpool telemetry returned no pools")
            else:
                counts = []
        except Exception as exc:
            raise Route3ResourceError(f"Route 3 resource telemetry unavailable: {type(exc).__name__}: {exc}") from exc
        self.max_rss = max(self.max_rss, rss)
        if rss > self.rss_ceiling:
            raise Route3ResourceError("Route 3 process-tree RSS limit exceeded")
        if disk > int(self.limits["disk_bytes"]):
            raise Route3ResourceError("Route 3 disk limit exceeded")
        if counts and max(counts) > int(max_threads):
            raise Route3ResourceError("Route 3 thread limit exceeded")
        if self._fit_wall_used() > float(self.limits["fit_wall_seconds"]):
            raise Route3ResourceError("Route 3 cumulative verifier-fit wall limit exceeded")

    def _monitor_resources(self) -> None:
        while not self._monitor_stop.wait(1.0):
            try:
                self._check_measurements()
            except Route3ResourceError as exc:
                self._resource_failure = str(exc)
                self._monitor_stop.set()
                return

    def check(self) -> None:
        if self._resource_failure is not None:
            raise Route3ResourceError(self._resource_failure)
        self._check_measurements()

    def reserve_fit(self, role_id: str) -> None:
        self.check()
        if self._fit_attempts() >= int(self.limits["verifier_fit_attempts"]):
            raise Route3ResourceError("Route 3 verifier fit attempt cap exceeded")
        self._append("fit_reserved", {"role_id": str(role_id), "candidate_fit_attempts": 0})
        self.current_fit_attempts += 1

    def start_fit(self, role_id: str) -> None:
        self.check()
        role_key = str(role_id)
        if role_key in self.fit_started:
            raise ValueError("Route 3 fit role is already active")
        self.fit_started[role_key] = self.clock()
        self._append("fit_started", {"role_id": role_key})

    def end_fit(self, role_id: str, status: str) -> None:
        role_key = str(role_id)
        started = self.fit_started.pop(role_key, None)
        if started is None:
            raise ValueError("Route 3 fit ended without a start record")
        duration = max(0.0, self.clock() - started)
        self._append("fit_ended", {
            "role_id": role_key,
            "status": str(status),
            "duration_seconds": duration,
        })
        self.current_fit_wall_seconds += duration
        if self._fit_wall_used() > float(self.limits["fit_wall_seconds"]):
            raise Route3ResourceError("Route 3 cumulative verifier-fit wall limit exceeded")
        self.check()

    def close(self, status: str) -> None:
        if self._closed:
            return
        self._monitor_stop.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
        duration = max(0.0, self.clock() - self.started)
        self._append("invocation_end", {
            "mode": self.mode,
            "duration_seconds": duration,
            "max_rss_bytes": self.max_rss,
        })
        self._append("status", {"status": str(status)})
        if status != "AUDIT_READY":
            self._append("study_terminal", {"status": str(status)})
        self._release_lock()
        self._closed = True

    def snapshot(self) -> dict[str, object]:
        disk = _tree_bytes(self.output_dir)
        if self.ledger_path.exists():
            disk += self.ledger_path.stat().st_size
        if self.lock_path.exists():
            disk += self.lock_path.stat().st_size
        return {
            "study_id": self.study_id,
            "mode": self.mode,
            "active_wall_seconds_including_prior_invocations": self._active_used(),
            "verifier_fit_attempts": self._fit_attempts(),
            "verifier_fit_wall_seconds": self._fit_wall_used(),
            "max_process_tree_rss_bytes": self.max_rss,
            "rss_ceiling_bytes": self.rss_ceiling,
            "study_disk_bytes": disk,
            "disk_cap_bytes": int(self.limits["disk_bytes"]),
            "resource_failure": self._resource_failure,
        }
