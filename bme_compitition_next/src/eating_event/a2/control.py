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
    check_rss_ceiling,
    compute_rss_ceiling,
    verify_predecessor_001,
)
from eating_event.a2.contracts import DEFAULT_STUDY_ID, PREDECESSOR_001, STUDY_001_ID, STUDY_002_ID, load_config, study_output_path, validate_study_binding


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
                output_bytes = ledger.measure_disk(max_disk_bytes=max_disk_bytes)
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
            ledger.measure_disk(max_disk_bytes=max_disk_bytes)


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


def _startup_resources(study_id: str, config: dict[str, object]) -> dict[str, int]:
    import psutil

    available = int(psutil.virtual_memory().available)
    if available <= 0:
        raise StudyResourceError("startup available-memory sample failed")
    if study_id == STUDY_002_ID:
        predecessor = config["predecessor"]
        if not isinstance(predecessor, dict):
            raise StudyResourceError("A2-001 predecessor RSS ceiling is missing")
        ceiling = compute_rss_ceiling(available, int(predecessor["rss_ceiling_bytes"]))
    else:
        ceiling = min(8 * 1024**3, int(available * 0.60))
    if ceiling <= 0:
        raise StudyResourceError("startup RSS ceiling is invalid")
    return {"startup_available_bytes": available, "rss_ceiling_bytes": ceiling}


def launch(
    mode: str,
    workspace: str | Path,
    *,
    config_digest: str,
    study_notes: str,
    study_id: str = DEFAULT_STUDY_ID,
) -> dict[str, object]:
    if mode not in {"audit", "run"}:
        raise ValueError("A2 exposes only audit and run modes")
    root = Path(workspace).resolve()
    artifacts = root / "artifacts"
    config, expected_output = validate_study_binding(
        root,
        study_output_path(root, load_config(root, study_id=study_id)[0], study_id=study_id),
        study_id=study_id,
        config_sha256=config_digest,
    )
    output = expected_output
    artifacts.mkdir(exist_ok=True)
    lock_name = str(config.get("lock_path", "artifacts/a2-study-budget.lock"))
    lock_path = (root / lock_name).resolve()
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("A2 study lock exists; an interrupted study is fail-closed") from exc
    os.write(fd, f"pid={os.getpid()} mode={mode}\n".encode("ascii"))
    os.fsync(fd)
    os.close(fd)
    ledger: StudyLedger | None = None
    invocation_id = f"{mode}-{time.time_ns()}"
    invocation_started: float | None = time.monotonic()
    resources: dict[str, int] | None = None
    status = "INVALID"
    cause: str | None = None
    try:
        if study_id == STUDY_002_ID:
            expected_predecessor = config.get("predecessor")
            if not isinstance(expected_predecessor, dict):
                raise StudyResourceError("A2-002 predecessor configuration is missing")
        else:
            expected_predecessor = None
        if mode == "audit":
            external_path = (root / str(config.get("ledger_path", "artifacts/a2-study-budget.jsonl"))).resolve()
            if output.exists() or external_path.exists():
                raise ValueError("A2 audit has already started; no reset or alternate directory is allowed")
            output.mkdir()
        elif not output.is_dir():
            raise ValueError("A2 run requires the existing fixed study output")
        ledger = StudyLedger(
            artifacts,
            output,
            limits=config["limits"],
            study_id=study_id,
            predecessor=expected_predecessor,
            config_sha256=config_digest,
        )
        ledger.assert_no_unclosed_intervals()
        if mode == "audit":
            ledger.assert_can_start_audit()
            if study_id == STUDY_002_ID:
                predecessor = verify_predecessor_001(root, expected_predecessor)
                ledger.append("predecessor", {"predecessor": predecessor})
            resources = _startup_resources(study_id, config)
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
        ledger.append("invocation_start", {"id": invocation_id, "mode": mode, "monotonic": invocation_started})
        active_used = ledger.assert_can_start_invocation()
        ledger.mark_status("RUNNING" if mode == "run" else "AUDITING", invocation_id=invocation_id)
        _write_json(output / "run-status.json", {
            "status": "RUNNING" if mode == "run" else "AUDITING",
            "study_id": study_id,
            "study_output": str(config["study_output"]),
            "config_sha256": config_digest,
        })
        request = {
            "mode": mode,
            "study_id": study_id,
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
                max_disk_bytes=int(config["limits"]["disk_bytes"]),
                wall_deadline_seconds=max(0.0, float(config["limits"]["active_wall_seconds"]) - active_used),
                fit_wall_seconds=float(config["limits"]["fit_wall_seconds"]) if mode == "run" else None,
            )
            response = json.loads(Path(request["response"]).read_text(encoding="utf-8"))
            if not isinstance(response, dict):
                raise ValueError("A2 worker response must be an object")
            if (
                response.get("study_id") != study_id
                or response.get("config_sha256") != config_digest
                or Path(str(response.get("study_output", ""))).resolve() != output
            ):
                raise ValueError("A2 worker response study identity mismatch")
            status = str(response.get("status", "INVALID"))
            if mode == "audit" and status == "AUDIT_READY":
                status = "AUDIT_READY"
            elif mode == "run" and status != "COMPLETE":
                status = status if status in {"INVALID", "VERIFIER_DATA_INSUFFICIENT", "INCOMPLETE_RESOURCE", "INCOMPLETE_INTERRUPTED"} else "INVALID"
            telemetry["invocation_elapsed_seconds"] = time.monotonic() - invocation_started
            _write_json(output / "resource-summary.json", telemetry)
            if telemetry.get("returncode") != 0 and status in {"AUDIT_READY", "COMPLETE"}:
                raise ValueError("A2 worker exit/status mismatch")
            ledger.append("invocation_end", {"id": invocation_id, "duration_seconds": telemetry["invocation_elapsed_seconds"]})
            ledger.mark_status(status, invocation_id=invocation_id)
            if status == "AUDIT_READY":
                _write_json(output / "run-status.json", {
                    "status": status,
                    "study_id": study_id,
                    "study_output": str(config["study_output"]),
                    "config_sha256": config_digest,
                })
            else:
                _write_json(output / "run-status.json", {
                    "status": status,
                    "study_id": study_id,
                    "study_output": str(config["study_output"]),
                    "config_sha256": config_digest,
                    "reason": response.get("reason"),
                })
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
                records = ledger.records()
                open_rows = {
                    str(row["id"])
                    for row in records
                    if row["event"] == "invocation_start"
                } - {
                    str(row["id"])
                    for row in records
                    if row["event"] == "invocation_end"
                }
                if invocation_id in open_rows and invocation_started is not None:
                    ledger.append("invocation_end", {
                        "id": invocation_id,
                        "duration_seconds": max(0.0, time.monotonic() - invocation_started),
                    })
                ledger.mark_status(status, cause=cause)
                _write_json(output / "run-status.json", {
                    "status": status,
                    "study_id": study_id,
                    "study_output": str(config["study_output"]),
                    "config_sha256": config_digest,
                    "cause": cause,
                })
            except Exception:
                pass
        elif output.is_dir():
            _write_json(output / "run-status.json", {
                "status": status,
                "study_id": study_id,
                "study_output": str(config["study_output"]),
                "config_sha256": config_digest,
                "cause": cause,
            })
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
    fits = FitAttemptLedger(ledger)
    predecessor = ledger.predecessor_usage()
    return {
        "study_id": ledger.study_id,
        "study_output": ledger.study_output_identity,
        "config_sha256": ledger.config_sha256,
        "predecessor": None if ledger.study_id == STUDY_001_ID else dict(ledger.predecessor or {}),
        "a2_active_wall_seconds": ledger.local_active_wall_seconds(),
        "predecessor_active_wall_seconds": predecessor["active_wall_seconds"],
        "combined_active_wall_seconds": ledger.active_wall_seconds(),
        "a2_fit_wall_seconds": fits.local_fit_wall_seconds(),
        "predecessor_fit_wall_seconds": predecessor["fit_wall_seconds"],
        "combined_fit_wall_seconds": fits.fit_wall_seconds(),
        "a2_verifier_fit_attempts": fits.local_attempt_count(),
        "predecessor_verifier_fit_attempts": predecessor["verifier_fit_attempts"],
        "combined_verifier_fit_attempts": fits.attempt_count(),
        "external_ledger_path": ledger.external_path.relative_to(ledger.workspace).as_posix(),
        "mirror_ledger_path": ledger.mirror_path.relative_to(ledger.workspace).as_posix(),
        "lock_path": ledger.lock_path.relative_to(ledger.workspace).as_posix(),
        "status": ledger.current_status(),
        "verifier_fit_attempts": fits.attempt_count(),
        "active_wall_seconds": ledger.active_wall_seconds(),
        "fit_wall_seconds": fits.fit_wall_seconds(),
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
    final_bytes = ledger.measure_disk(max_disk_bytes=1024**3)
    snapshot = _ledger_snapshot(ledger)
    resources = {
        **telemetry,
        "final_study_bytes": final_bytes,
        "family_disk_bytes_total": final_bytes,
        "rss_ceiling_bytes": next(
            int(row["rss_ceiling_bytes"]) for row in ledger.records() if row["event"] == "startup_resources"
        ),
        "active_wall_seconds_total": snapshot["combined_active_wall_seconds"],
        "a2_active_wall_seconds": snapshot["a2_active_wall_seconds"],
        "predecessor_active_wall_seconds": snapshot["predecessor_active_wall_seconds"],
        "fit_wall_seconds_total": snapshot["combined_fit_wall_seconds"],
        "a2_fit_wall_seconds": snapshot["a2_fit_wall_seconds"],
        "predecessor_fit_wall_seconds": snapshot["predecessor_fit_wall_seconds"],
        "verifier_fit_attempts": snapshot["combined_verifier_fit_attempts"],
        "a2_verifier_fit_attempts": snapshot["a2_verifier_fit_attempts"],
        "predecessor_verifier_fit_attempts": snapshot["predecessor_verifier_fit_attempts"],
        "thread_limit": 4,
    }
    metrics["unknown_behavior_note"] = (
        "The historical 75 long false positives without recorded overlap with the 281 annotations have unknown actual behavior. "
        "Suppressing them is an annotation-contract FP reduction, not independent behavior adjudication."
    )
    response["resource_accounting"] = resources
    response["fit_ledger"] = snapshot
    metrics["study_id"] = ledger.study_id
    metrics["budget_ledger"] = snapshot

    report_path = output / "report.md"
    report_base = report_path.read_text(encoding="utf-8")

    manifest_path = output / "run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fit_ledger"] = snapshot
    manifest["budget_ledger"] = {
        "study_id": ledger.study_id,
        "predecessor": None if ledger.study_id == STUDY_001_ID else dict(ledger.predecessor or {}),
        "external_path": ledger.external_path.relative_to(workspace).as_posix(),
        "output_mirror_path": ledger.mirror_path.relative_to(workspace).as_posix(),
        "lock_path": ledger.lock_path.relative_to(workspace).as_posix(),
        "external_sha256": __import__("hashlib").sha256(ledger.external_path.read_bytes()).hexdigest(),
        "mirror_sha256": __import__("hashlib").sha256(ledger.mirror_path.read_bytes()).hexdigest(),
        "combined_active_wall_seconds": snapshot["combined_active_wall_seconds"],
        "combined_fit_wall_seconds": snapshot["combined_fit_wall_seconds"],
        "combined_verifier_fit_attempts": snapshot["combined_verifier_fit_attempts"],
    }
    for _ in range(4):
        metrics["resource_accounting"] = resources
        metrics["fit_ledger"] = snapshot
        metrics_path.write_text(json.dumps(metrics, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "resource-summary.json").write_text(json.dumps(resources, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = report_base + "\n## Resource and fit accounting\n\n"
        report += f"- Total audit plus run active wall: {resources['active_wall_seconds_total']:.3f} s (limit 7,200 s).\n"
        report += f"- Inherited A2-001 active wall: {resources['predecessor_active_wall_seconds']:.3f} s; A2-002 active wall: {resources['a2_active_wall_seconds']:.3f} s.\n"
        report += f"- Cumulative verifier fit wall: {resources['fit_wall_seconds_total']:.3f} s (limit 3,600 s; inherited {resources['predecessor_fit_wall_seconds']:.3f} s).\n"
        report += f"- Verifier fit attempts: {resources['verifier_fit_attempts']} / 25 (inherited {resources['predecessor_verifier_fit_attempts']}); candidate fit/predict: 0 / 0.\n"
        report += f"- Peak process-tree RSS: {resources['peak_rss_bytes']} bytes; ceiling {resources['rss_ceiling_bytes']} bytes.\n"
        report += f"- A1-001 plus A2-002 artifacts, ledgers, lock and temporary output: {resources['family_disk_bytes_total']} / 1,073,741,824 bytes.\n"
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
        measured = ledger.measure_disk(max_disk_bytes=1024**3)
        if measured == resources["final_study_bytes"]:
            break
        resources["final_study_bytes"] = measured
    else:
        raise StudyResourceError("final A2 disk accounting did not stabilize")
