"""Fail-closed cumulative budget and process-resource primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import time
from typing import Callable, Iterable, Mapping


class ResourceNotReady(RuntimeError):
    """Resource measurement is unavailable or cannot prove the ceiling."""


@dataclass(frozen=True)
class BudgetLimits:
    max_candidate_fits: int = 105
    max_verifier_fits: int = 25
    total_wall_seconds: float = 21_600.0
    audit_wall_seconds: float = 1_800.0
    fit_wall_seconds: float = 7_200.0
    max_rss_bytes: int = 8 * 1024**3
    max_disk_bytes: int = 2 * 1024**3
    max_threads: int = 4


@dataclass(frozen=True)
class BudgetState:
    candidate_fit_attempts: int
    verifier_fit_attempts: int
    failed_fit_attempts: int
    elapsed_wall_seconds: float = 0.0
    peak_rss_bytes: int | None = None
    output_bytes: int | None = None

    @classmethod
    def from_samples(cls, samples: Iterable[Mapping[str, object]], *, max_rss_bytes: int) -> "BudgetState":
        peak: int | None = 0
        for sample in samples:
            value = sample.get("rss_bytes")
            if value is None:
                raise ResourceNotReady("RSS sampler returned no measurement")
            peak = max(peak or 0, int(value))
        if peak is None or peak > max_rss_bytes:
            raise ResourceNotReady("RSS resource ceiling is not satisfied")
        return cls(0, 0, 0, peak_rss_bytes=peak)


class BudgetLedger:
    """Append-only JSONL ledger; reserved attempts are never reusable."""

    def __init__(self, path: str | Path, limits: BudgetLimits) -> None:
        self.path = Path(path)
        self.limits = limits
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("fit ledger contains a non-object record")
                records.append(record)
        return records

    def _append(self, record: Mapping[str, object]) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(dict(record), sort_keys=True) + "\n")

    def state(self) -> BudgetState:
        records = self._records()
        candidate = sum(record.get("kind") == "candidate" and record.get("event") == "reserve" for record in records)
        verifier = sum(record.get("kind") == "verifier" and record.get("event") == "reserve" for record in records)
        failed = sum(record.get("event") == "result" and record.get("status") != "success" for record in records)
        elapsed = sum(float(record.get("elapsed_seconds", 0.0)) for record in records)
        rss_values = [int(record["rss_bytes"]) for record in records if record.get("rss_bytes") is not None]
        output_values = [int(record["output_bytes"]) for record in records if record.get("output_bytes") is not None]
        return BudgetState(
            candidate_fit_attempts=int(candidate),
            verifier_fit_attempts=int(verifier),
            failed_fit_attempts=int(failed),
            elapsed_wall_seconds=elapsed,
            peak_rss_bytes=max(rss_values) if rss_values else None,
            output_bytes=sum(output_values) if output_values else None,
        )

    def reserve_fit(self, kind: str, role_id: str) -> None:
        if kind not in {"candidate", "verifier"}:
            raise ValueError("fit kind must be candidate or verifier")
        records = self._records()
        if any(record.get("event") == "reserve" and record.get("role_id") == role_id for record in records):
            raise RuntimeError(f"fit role already reserved: {role_id}")
        state = self.state()
        if kind == "candidate" and state.candidate_fit_attempts >= self.limits.max_candidate_fits:
            raise RuntimeError("candidate fit budget exhausted")
        if kind == "verifier" and state.verifier_fit_attempts >= self.limits.max_verifier_fits:
            raise RuntimeError("verifier fit budget exhausted")
        self._append({
            "event": "reserve",
            "kind": kind,
            "role_id": role_id,
            "timestamp": time.time(),
        })

    def record_fit_result(
        self,
        role_id: str,
        status: str,
        *,
        elapsed_seconds: float = 0.0,
        rss_bytes: int | None = None,
        output_bytes: int | None = None,
        error: str | None = None,
    ) -> None:
        if status not in {"success", "failed", "timeout", "resource_exceeded"}:
            raise ValueError("invalid fit result status")
        if not any(record.get("event") == "reserve" and record.get("role_id") == role_id for record in self._records()):
            raise RuntimeError(f"fit role was not reserved: {role_id}")
        self._append({
            "event": "result",
            "role_id": role_id,
            "status": status,
            "elapsed_seconds": float(elapsed_seconds),
            "rss_bytes": rss_bytes,
            "output_bytes": output_bytes,
            "error": error,
            "timestamp": time.time(),
        })

    def check_wall(self, started_at: float) -> None:
        elapsed = time.monotonic() - started_at
        if elapsed > self.limits.total_wall_seconds:
            raise ResourceNotReady("A1 total wall-time budget exhausted")

    def check_output_size(self, output_dir: str | Path) -> int:
        root = Path(output_dir)
        total = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        if total > self.limits.max_disk_bytes:
            raise ResourceNotReady("A1 output disk budget exhausted")
        return total


def sample_process_tree_rss(pid: int | None = None) -> int:
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ResourceNotReady("psutil is required for process-tree RSS monitoring") from exc
    root = psutil.Process(pid or __import__("os").getpid())
    processes = [root]
    processes.extend(root.children(recursive=True))
    try:
        return int(sum(process.memory_info().rss for process in processes))
    except psutil.Error as exc:  # pragma: no cover - process-race dependent
        raise ResourceNotReady("process tree changed during RSS sampling") from exc


def ensure_disk_budget(output_dir: str | Path, limits: BudgetLimits) -> int:
    root = Path(output_dir)
    usage = shutil.disk_usage(root.anchor or root)
    if usage.free < limits.max_disk_bytes:
        raise ResourceNotReady("insufficient free disk for A1 output budget")
    return usage.free


def run_supervised(command: list[str], output_dir: Path, limits: BudgetLimits, *,
                   prior_seconds: float, audit: bool = False) -> dict[str, object]:
    """Monitor the entire worker, including loading, fitting, scoring and writes.

    A worker publishes the start of a fit in phase.json. The parent does not
    depend on that worker yielding control to enforce any deadline.
    """
    import os
    import subprocess
    import psutil

    output_dir = Path(output_dir)
    ensure_disk_budget(output_dir, limits)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(__import__("sys").path)
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        environment[name] = str(limits.max_threads)
    started = time.monotonic()
    peak, output_bytes = 0, 0
    process = None
    error = None
    try:
        with (output_dir / 'worker.log').open('ab') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
            while True:
                elapsed = time.monotonic() - started
                if prior_seconds + elapsed > limits.total_wall_seconds or (audit and elapsed > limits.audit_wall_seconds):
                    raise ResourceNotReady('wall-time budget exceeded')
                # Include parent and its worker descendants; no silent zero on failure.
                peak = max(peak, sample_process_tree_rss())
                if peak > limits.max_rss_bytes:
                    raise ResourceNotReady('RSS budget exceeded')
                roots = list(output_dir.parent.glob('a1-end-to-end-feasibility-v1-*')) if output_dir.name.startswith('a1-end-to-end-feasibility-v1-') else [output_dir]
                output_bytes = sum(p.stat().st_size for root in roots if root.is_dir() for p in root.rglob('*') if p.is_file())
                if output_bytes > limits.max_disk_bytes:
                    raise ResourceNotReady('disk budget exceeded')
                phase_path = output_dir / 'phase.json'
                if phase_path.exists():
                    phase = json.loads(phase_path.read_text(encoding='utf-8'))
                    if phase.get('kind') == 'fit' and time.time() - float(phase['started_at']) > limits.fit_wall_seconds:
                        raise ResourceNotReady('fit wall-time budget exceeded')
                if process.poll() is not None:
                    break
                time.sleep(.2)
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        if process is not None and process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in reversed(children):
                    child.kill()
                parent.kill()
                psutil.wait_procs(children + [parent], timeout=5)
            except psutil.NoSuchProcess:
                pass
            process.wait(timeout=5)
        telemetry = dict(elapsed_seconds=time.monotonic()-started, peak_rss_bytes=peak,
                         output_bytes=output_bytes, error=error,
                         returncode=process.returncode if process else None)
        # Retain failure/timeout cost, including unsuccessful attempts.
        with (output_dir / 'resource-segments.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(telemetry) + '\n')
    return telemetry
