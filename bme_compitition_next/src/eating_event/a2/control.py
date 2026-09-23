"""Parent supervisor for the one hash-bound A2 audit and run."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence

from eating_event.a2.budget import (
    FitAttemptLedger,
    StudyInterrupted,
    StudyLedger,
    StudyResourceError,
    check_disk_budget,
    check_rss_ceiling,
)


def sample_process_tree_rss(pid: int | None = None) -> int:
    try:
        import psutil
    except ImportError as exc:
        raise StudyResourceError("psutil is required for process-tree RSS monitoring") from exc
    try:
        root = psutil.Process(pid or os.getpid())
        members = [root, *root.children(recursive=True)]
        return sum(int(process.memory_info().rss) for process in members)
    except (psutil.Error, OSError) as exc:
        raise StudyResourceError("process-tree RSS sample failed") from exc


def supervise_worker(
    command: Sequence[str],
    output_dir: str | Path,
    ledger: StudyLedger,
    *,
    response_path: str | Path,
    max_rss_bytes: int,
    max_disk_bytes: int,
    wall_deadline_seconds: float,
    fit_wall_seconds: float | None = None,
) -> dict[str, object]:
    """Run one worker and kill its process tree on any unprovable ceiling."""

    import psutil

    output = Path(output_dir)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([str(output.parents[1] / "src"), str(output.parents[1])])
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        environment[name] = "4"
    worker: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    peak_rss = 0
    output_bytes = 0
    process_error: Exception | None = None
    with (output / "worker.log").open("ab") as log:
        try:
            worker = subprocess.Popen(list(command), stdout=log, stderr=subprocess.STDOUT, env=environment)
            while True:
                elapsed = time.monotonic() - started
                if elapsed > wall_deadline_seconds:
                    raise StudyResourceError("A2 invocation wall deadline exceeded")
                rss = check_rss_ceiling(sample_process_tree_rss(), max_rss_bytes=max_rss_bytes)
                peak_rss = max(peak_rss, rss)
                output_bytes = check_disk_budget(
                    output,
                    (ledger.external_path, ledger.lock_path),
                    max_disk_bytes=max_disk_bytes,
                )
                if fit_wall_seconds is not None:
                    used = FitAttemptLedger(ledger).assert_fit_wall_budget()
                    if used > fit_wall_seconds:
                        raise StudyResourceError("cumulative verifier fit wall deadline exceeded")
                if worker.poll() is not None:
                    break
                time.sleep(0.2)
            response = Path(response_path)
            if not response.is_file():
                raise StudyInterrupted(f"A2 worker disappeared without a response (exit {worker.returncode})")
            return {
                "elapsed_seconds": time.monotonic() - started,
                "peak_rss_bytes": peak_rss,
                "study_bytes": output_bytes,
                "returncode": worker.returncode,
            }
        except BaseException as exc:
            process_error = exc
            if worker is not None and worker.poll() is None:
                try:
                    parent = psutil.Process(worker.pid)
                    children = parent.children(recursive=True)
                    for child in reversed(children):
                        child.kill()
                    parent.kill()
                    psutil.wait_procs(children + [parent], timeout=5)
                except psutil.Error:
                    pass
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            raise
        finally:
            telemetry = {
                "elapsed_seconds": time.monotonic() - started,
                "peak_rss_bytes": peak_rss,
                "study_bytes": output_bytes,
                "returncode": worker.returncode if worker is not None else None,
                "cause": None if process_error is None else f"{type(process_error).__name__}: {process_error}",
            }
            with (output / "resource-segments.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(telemetry, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            check_disk_budget(output, (ledger.external_path, ledger.lock_path), max_disk_bytes=max_disk_bytes)


def _environment_identity() -> dict[str, object]:
    import importlib.metadata
    import platform

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "libraries": {
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "scikit-learn": importlib.metadata.version("scikit-learn"),
            "psutil": importlib.metadata.version("psutil"),
        },
    }


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _startup_resources() -> dict[str, int]:
    import psutil

    available = int(psutil.virtual_memory().available)
    if available <= 0:
        raise StudyResourceError("startup available-memory sample failed")
    ceiling = min(8 * 1024**3, int(available * 0.60))
    if ceiling <= 0:
        raise StudyResourceError("startup RSS ceiling is invalid")
    return {"startup_available_bytes": available, "rss_ceiling_bytes": ceiling}


def launch(mode: str, workspace: str | Path, *, config_digest: str, study_notes: str) -> dict[str, object]:
    if mode not in {"audit", "run"}:
        raise ValueError("A2 exposes only audit and run modes")
    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    output = root / "artifacts" / "a2-context-verifier-v1-001"
    artifacts.mkdir(exist_ok=True)
    lock_path = artifacts / "a2-study-budget.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("A2 study lock exists; an interrupted study is fail-closed") from exc
    os.write(fd, f"pid={os.getpid()} mode={mode}\n".encode("ascii"))
    os.fsync(fd)
    os.close(fd)
    ledger: StudyLedger | None = None
    invocation_id = f"{mode}-{time.time_ns()}"
    invocation_started: float | None = None
    resources: dict[str, int] | None = None
    status = "INVALID"
    cause: str | None = None
    try:
        if mode == "audit":
            if output.exists() or (artifacts / "a2-study-budget.jsonl").exists():
                raise ValueError("A2 audit has already started; no reset or alternate directory is allowed")
            output.mkdir()
        elif not output.is_dir():
            raise ValueError("A2 run requires the existing single study output")
        ledger = StudyLedger(artifacts, output)
        ledger.assert_no_unclosed_intervals()
        if mode == "audit":
            ledger.assert_can_start_audit()
            resources = _startup_resources()
            ledger.append("startup_resources", resources)
            (output / "study-notes.md").write_text(study_notes.rstrip() + "\n", encoding="utf-8")
        else:
            ledger.assert_can_start_run()
            resources_row = next((row for row in ledger.records() if row["event"] == "startup_resources"), None)
            if resources_row is None:
                raise StudyResourceError("persisted startup RSS ceiling is missing")
            resources = {
                "startup_available_bytes": int(resources_row["startup_available_bytes"]),
                "rss_ceiling_bytes": int(resources_row["rss_ceiling_bytes"]),
            }
        limits = {
            "verifier_fit_attempts": 25,
            "active_wall_seconds": 7200,
            "fit_wall_seconds": 3600,
            "threads": 4,
            "disk_bytes": 1024**3,
        }
        ledger.limits = limits
        active_used = ledger.active_wall_seconds()
        if active_used >= 7200:
            raise StudyResourceError("A2 cumulative active wall budget is exhausted")
        invocation_started = time.monotonic()
        ledger.append("invocation_start", {"id": invocation_id, "mode": mode, "monotonic": invocation_started})
        ledger.mark_status("RUNNING" if mode == "run" else "AUDITING", invocation_id=invocation_id)
        _write_json(output / "run-status.json", {"status": "RUNNING" if mode == "run" else "AUDITING", "config_sha256": config_digest})
        request = {
            "mode": mode,
            "workspace": str(root),
            "output": str(output),
            "config_sha256": config_digest,
            "startup_resources": resources,
            "response": str(output / f"worker-response-{mode}.json"),
            "request": str(output / f"worker-request-{mode}.json"),
        }
        _write_json(Path(request["request"]), request)
        command = [sys.executable, "-m", "eating_event.a2.worker", str(request["request"])]
        try:
            telemetry = supervise_worker(
                command,
                output,
                ledger,
                response_path=request["response"],
                max_rss_bytes=int(resources["rss_ceiling_bytes"]),
                max_disk_bytes=int(limits["disk_bytes"]),
                wall_deadline_seconds=7200.0 - active_used,
                fit_wall_seconds=3600.0 if mode == "run" else None,
            )
            response = json.loads(Path(request["response"]).read_text(encoding="utf-8"))
            if not isinstance(response, dict):
                raise ValueError("A2 worker response must be an object")
            status = str(response.get("status", "INVALID"))
            if mode == "audit" and status == "AUDIT_READY":
                status = "AUDIT_READY"
            elif mode == "run" and status != "COMPLETE":
                status = status if status in {"INVALID", "VERIFIER_DATA_INSUFFICIENT", "INCOMPLETE_RESOURCE", "INCOMPLETE_INTERRUPTED"} else "INVALID"
            _write_json(output / "resource-summary.json", telemetry)
            if telemetry.get("returncode") != 0 and status in {"AUDIT_READY", "COMPLETE"}:
                raise ValueError("A2 worker exit/status mismatch")
            ledger.append("invocation_end", {"id": invocation_id, "duration_seconds": telemetry["elapsed_seconds"]})
            ledger.mark_status(status, invocation_id=invocation_id)
            if status == "AUDIT_READY":
                _write_json(output / "run-status.json", {"status": status, "config_sha256": config_digest})
            else:
                _write_json(output / "run-status.json", {"status": status, "config_sha256": config_digest, "reason": response.get("reason")})
            response["resource_summary"] = telemetry
            response["fit_ledger"] = _ledger_snapshot(ledger)
            if status == "COMPLETE":
                _finalize_complete_output(root, output, ledger, response, telemetry)
            return response
        except StudyResourceError as exc:
            status, cause = "INCOMPLETE_RESOURCE", str(exc)
        except StudyInterrupted as exc:
            status, cause = "INCOMPLETE_INTERRUPTED", str(exc)
        except KeyboardInterrupt:
            status, cause = "INCOMPLETE_INTERRUPTED", "A2 supervisor was interrupted by the operator"
        except Exception as exc:
            cause = f"{type(exc).__name__}: {exc}"
            status = "VERIFIER_DATA_INSUFFICIENT" if cause.startswith("ValueError: G3:") else "INVALID"
        finally:
            if invocation_started is not None:
                try:
                    elapsed = time.monotonic() - invocation_started
                    if not any(row["event"] == "invocation_end" and row.get("id") == invocation_id for row in ledger.records()):
                        ledger.append("invocation_end", {"id": invocation_id, "duration_seconds": elapsed})
                except Exception:
                    status, cause = "INCOMPLETE_RESOURCE", "A2 ledger could not close the active wall interval"
        ledger.mark_status(status, invocation_id=invocation_id, cause=cause)
        _write_json(output / "run-status.json", {"status": status, "config_sha256": config_digest, "cause": cause})
        return {"status": status, "reason": cause, "ledger_snapshot": _ledger_snapshot(ledger)}
    except Exception as exc:
        cause = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, StudyResourceError):
            status = "INCOMPLETE_RESOURCE"
        if ledger is not None and output.is_dir():
            try:
                ledger.mark_status(status, cause=cause)
                _write_json(output / "run-status.json", {"status": status, "cause": cause})
            except Exception:
                pass
        return {"status": status, "reason": cause, "ledger_snapshot": _ledger_snapshot(ledger) if ledger else None}
    finally:
        # An orderly invocation releases the inter-command lock. A hard crash
        # leaves it behind and prevents any implicit retry.
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _ledger_snapshot(ledger: StudyLedger) -> dict[str, object]:
    records = ledger.records()
    return {
        "status": ledger.current_status(),
        "verifier_fit_attempts": sum(row["event"] == "fit_reserve" for row in records),
        "active_wall_seconds": ledger.active_wall_seconds(),
        "fit_wall_seconds": FitAttemptLedger(ledger).fit_wall_seconds(),
        "ledger_record_count": len(records),
    }


def _finalize_complete_output(
    workspace: Path,
    output: Path,
    ledger: StudyLedger,
    response: dict[str, object],
    telemetry: dict[str, object],
) -> None:
    """Publish a final, checksummed report after parent-side resource accounting."""

    metrics_path = output / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    snapshot = _ledger_snapshot(ledger)
    final_bytes = check_disk_budget(output, (ledger.external_path, ledger.lock_path), max_disk_bytes=1024**3)
    resources = {
        **telemetry,
        "final_study_bytes": final_bytes,
        "rss_ceiling_bytes": next(
            int(row["rss_ceiling_bytes"]) for row in ledger.records() if row["event"] == "startup_resources"
        ),
        "active_wall_seconds_total": snapshot["active_wall_seconds"],
        "fit_wall_seconds_total": snapshot["fit_wall_seconds"],
        "verifier_fit_attempts": snapshot["verifier_fit_attempts"],
        "thread_limit": 4,
    }
    metrics["unknown_behavior_note"] = (
        "The historical 75 long false positives without recorded overlap with the 281 annotations have unknown actual behavior. "
        "Suppressing them is an annotation-contract FP reduction, not independent behavior adjudication."
    )
    response["resource_accounting"] = resources
    response["fit_ledger"] = snapshot

    report_path = output / "report.md"
    report_base = report_path.read_text(encoding="utf-8")

    manifest_path = output / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fit_ledger"] = snapshot
    manifest["budget_ledger"] = {
        "external_path": "artifacts/a2-study-budget.jsonl",
        "output_mirror_path": "artifacts/a2-context-verifier-v1-001/a2-study-budget.jsonl",
        "external_sha256": __import__("hashlib").sha256(ledger.external_path.read_bytes()).hexdigest(),
        "mirror_sha256": __import__("hashlib").sha256(ledger.mirror_path.read_bytes()).hexdigest(),
    }
    for _ in range(4):
        metrics["resource_accounting"] = resources
        metrics["fit_ledger"] = snapshot
        metrics_path.write_text(json.dumps(metrics, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "resource-summary.json").write_text(json.dumps(resources, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = report_base + "\n## Resource and fit accounting\n\n"
        report += f"- Total audit plus run active wall: {resources['active_wall_seconds_total']:.3f} s (limit 7,200 s).\n"
        report += f"- Cumulative verifier fit wall: {resources['fit_wall_seconds_total']:.3f} s (limit 3,600 s).\n"
        report += f"- Verifier fit attempts: {resources['verifier_fit_attempts']} / 25; candidate fit/predict: 0 / 0.\n"
        report += f"- Peak process-tree RSS: {resources['peak_rss_bytes']} bytes; ceiling {resources['rss_ceiling_bytes']} bytes.\n"
        report += f"- A2 study artifacts including external ledger and lock: {resources['final_study_bytes']} / 1,073,741,824 bytes.\n"
        report += "- The historical 75 long FP without recorded overlap with the 281 annotations have unknown actual behavior; suppression is an annotation-contract FP reduction, not behavior adjudication.\n"
        report_path.write_text(report, encoding="utf-8")
        manifest["resource_accounting"] = resources
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checksums: dict[str, str] = {}
        for path in sorted(output.rglob("*")):
            if not path.is_file() or path.name in {"run-manifest.json", "final-checksums.json", "run-status.json", "worker.log"}:
                continue
            checksums[path.relative_to(output).as_posix()] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        (output / "final-checksums.json").write_text(json.dumps(checksums, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        measured = check_disk_budget(output, (ledger.external_path, ledger.lock_path), max_disk_bytes=1024**3)
        if measured == resources["final_study_bytes"]:
            break
        resources["final_study_bytes"] = measured
    else:
        raise StudyResourceError("final A2 disk accounting did not stabilize")
