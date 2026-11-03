"""Parent supervisor for the one hash-bound A2 audit and run."""

from __future__ import annotations

import json
import hashlib
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
    compute_003_rss_ceiling,
    minimum_run_available_bytes,
    require_environment,
    verify_predecessor_001,
    verify_predecessor_family_002,
)
from eating_event.a2.contracts import DEFAULT_STUDY_ID, PREDECESSOR_001, STUDY_001_ID, STUDY_002_ID, STUDY_003_ID, load_config, study_output_path, validate_study_binding
from eating_event.a2.audit import current_a2_code_identity


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
    sample_interval_seconds: float = 0.2,
) -> dict[str, object]:
    """Run one worker and kill its process tree on any unprovable ceiling."""

    if ledger.study_id == STUDY_003_ID:
        return _supervise_worker_003(
            command,
            output_dir,
            ledger,
            response_path=response_path,
            max_rss_bytes=max_rss_bytes,
            max_disk_bytes=max_disk_bytes,
            wall_deadline_seconds=wall_deadline_seconds,
            fit_wall_seconds=fit_wall_seconds,
            sample_interval_seconds=sample_interval_seconds,
        )

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


_A2_003_STAGES = {
    "source_identity",
    "cache_geometry",
    "global_identity",
    "candidate_spool",
    "score_provenance",
    "role_context_materialization",
    "audit_complete",
    "run_role_load",
    "fit",
}
_A2_003_TELEMETRY_RESERVE_BYTES = 4 * 1024**2


def _sample_worker_process_tree(pid: int) -> dict[str, object]:
    import psutil

    try:
        root = psutil.Process(pid)
        members = [root, *root.children(recursive=True)]
        processes = []
        for process in members:
            try:
                rss = int(process.memory_info().rss)
            except psutil.Error:
                raise StudyResourceError("process-tree RSS sample failed")
            processes.append({"pid": int(process.pid), "rss_bytes": rss})
        return {
            "root_pid": int(pid),
            "processes": processes,
            "rss_bytes": sum(int(row["rss_bytes"]) for row in processes),
        }
    except (psutil.Error, OSError) as exc:
        raise StudyResourceError("process-tree RSS sample failed") from exc


def _read_last_completed_stage(output: Path) -> tuple[str | None, str | None]:
    path = output / "worker-progress.json"
    if not path.is_file():
        return None, None
    try:
        progress = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"worker stage telemetry could not be read: {type(exc).__name__}"
    if not isinstance(progress, dict):
        return None, "worker stage telemetry is malformed"
    stage = progress.get("last_completed_stage")
    if not isinstance(stage, str) or stage not in _A2_003_STAGES:
        return None, "worker stage marker is missing or unknown"
    return stage, None


def _append_jsonl_fsynced(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _terminate_worker_tree(worker: subprocess.Popen[bytes], process_error: Exception) -> None:
    import psutil

    del process_error
    if worker.poll() is not None:
        return
    try:
        parent = psutil.Process(worker.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            child.kill()
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=5)
    except psutil.Error:
        try:
            worker.kill()
        except OSError:
            pass
    try:
        worker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _supervise_worker_003(
    command: Sequence[str],
    output_dir: str | Path,
    ledger: StudyLedger,
    *,
    response_path: str | Path,
    max_rss_bytes: int,
    max_disk_bytes: int,
    wall_deadline_seconds: float,
    fit_wall_seconds: float | None,
    sample_interval_seconds: float,
) -> dict[str, object]:
    output = Path(output_dir)
    environment = dict(os.environ)
    workspace = output.parents[1]
    environment["PYTHONPATH"] = os.pathsep.join([str(workspace / "src"), str(workspace)])
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        environment[name] = "4"
    worker: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    peak_rss = 0
    last_stage: str | None = None
    failing_measurement: int | None = None
    process_error: Exception | None = None
    try:
        with (output / "worker.log").open("ab") as log:
            worker = subprocess.Popen(list(command), stdout=log, stderr=subprocess.STDOUT, env=environment)
            while True:
                elapsed = time.monotonic() - started
                stage, stage_error = _read_last_completed_stage(output)
                if stage is not None:
                    last_stage = stage
                process_sample: dict[str, object] | None = None
                sample_error: str | None = None
                try:
                    process_sample = _sample_worker_process_tree(worker.pid)
                except StudyResourceError as exc:
                    sample_error = str(exc)
                rss = None if process_sample is None else int(process_sample["rss_bytes"])
                measurement = {
                    "event": "rss_sample",
                    "sampled_epoch": time.time(),
                    "elapsed_seconds": elapsed,
                    "worker_pid": int(worker.pid),
                    "process_tree": None if process_sample is None else process_sample["processes"],
                    "rss_bytes": rss,
                    "rss_ceiling_bytes": int(max_rss_bytes),
                    "last_completed_stage": last_stage,
                    "sample_error": sample_error,
                    "stage_error": stage_error,
                }
                # Both the local segment and mirrored ledger are durable before
                # the supervisor evaluates the ceiling or terminates the worker.
                _append_jsonl_fsynced(output / "resource-segments.jsonl", measurement)
                ledger.append("resource_sample", {key: value for key, value in measurement.items() if key != "event"})
                if rss is not None:
                    peak_rss = max(peak_rss, rss)
                disk_limit = int(max_disk_bytes) - _A2_003_TELEMETRY_RESERVE_BYTES
                if disk_limit <= 0:
                    raise StudyResourceError("A2-003 disk ceiling cannot preserve the 4 MiB telemetry reserve")
                try:
                    ledger.measure_disk(max_disk_bytes=disk_limit)
                except StudyResourceError as exc:
                    raise StudyResourceError(f"A2-003 family disk ceiling exceeded: {exc}") from exc
                if sample_error is not None:
                    raise StudyResourceError("A2-003 process-tree RSS telemetry unavailable")
                if rss is None:
                    raise StudyResourceError("A2-003 process-tree RSS measurement unavailable")
                if rss > int(max_rss_bytes):
                    failing_measurement = rss
                    error = StudyResourceError("A2-003 process-tree RSS ceiling exceeded")
                    error.failing_measurement_bytes = rss
                    error.last_completed_stage = last_stage
                    error.worker_pid = int(worker.pid)
                    error.process_tree = process_sample["processes"] if process_sample else None
                    raise error
                if stage_error is not None and elapsed > 30.0:
                    raise StudyResourceError(stage_error)
                if time.monotonic() - started > wall_deadline_seconds:
                    raise StudyResourceError("A2-003 invocation wall deadline exceeded")
                if fit_wall_seconds is not None:
                    used = FitAttemptLedger(ledger).assert_fit_wall_budget()
                    if used > fit_wall_seconds:
                        raise StudyResourceError("A2-003 cumulative verifier fit wall deadline exceeded")
                if worker.poll() is not None:
                    break
                time.sleep(max(0.01, float(sample_interval_seconds)))

        response = Path(response_path)
        if not response.is_file():
            raise StudyInterrupted(f"A2-003 worker disappeared without a response (exit {worker.returncode if worker else None})")
        final_stage, stage_error = _read_last_completed_stage(output)
        if final_stage is None:
            raise StudyResourceError(stage_error or "A2-003 worker completed without stage telemetry")
        last_stage = final_stage
        return {
            "elapsed_seconds": time.monotonic() - started,
            "peak_rss_bytes": peak_rss,
            "study_bytes": ledger.measure_disk(max_disk_bytes=max_disk_bytes),
            "returncode": worker.returncode,
            "last_completed_stage": last_stage,
            "failing_measurement_bytes": None,
        }
    except BaseException as exc:
        process_error = exc
        if isinstance(exc, StudyResourceError):
            if not hasattr(exc, "failing_measurement_bytes"):
                exc.failing_measurement_bytes = failing_measurement
            if not hasattr(exc, "last_completed_stage"):
                exc.last_completed_stage = last_stage
        if worker is not None:
            _terminate_worker_tree(worker, exc)
        raise
    finally:
        summary = {
            "event": "invocation_summary",
            "elapsed_seconds": time.monotonic() - started,
            "peak_rss_bytes": peak_rss,
            "failing_measurement_bytes": failing_measurement,
            "last_completed_stage": last_stage,
            "returncode": worker.returncode if worker is not None else None,
            "cause": None if process_error is None else f"{type(process_error).__name__}: {process_error}",
        }
        _append_jsonl_fsynced(output / "resource-segments.jsonl", summary)


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
    if study_id == STUDY_003_ID:
        return _launch_003(
            mode,
            workspace,
            config_digest=config_digest,
            study_notes=study_notes,
        )
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


def available_memory_bytes() -> int:
    import psutil

    try:
        value = int(psutil.virtual_memory().available)
    except (psutil.Error, OSError) as exc:
        raise StudyResourceError("available main-memory sample failed") from exc
    if value <= 0:
        raise StudyResourceError("available main-memory sample failed")
    return value


def _a2_003_read_only_preflight(root: Path, config_digest: str) -> tuple[dict[str, object], dict[str, object], Path, dict[str, str]]:
    config, actual_digest = load_config(root, study_id=STUDY_003_ID)
    if actual_digest != config_digest:
        raise ValueError("A2-003 config SHA does not match the fixed invocation")
    output = study_output_path(root, config, study_id=STUDY_003_ID)
    code_identity = current_a2_code_identity(root)
    from eating_event.a2.audit import _EXPECTED_ENVIRONMENT, _environment_identity

    require_environment(_environment_identity(), _EXPECTED_ENVIRONMENT)
    predecessor = verify_predecessor_family_002(root)
    if predecessor != config.get("predecessor"):
        raise StudyResourceError("A2-003 predecessor family differs from the frozen config")
    limits = config["limits"]
    if float(predecessor["active_wall_seconds"]) >= float(limits["active_wall_seconds"]):
        raise StudyResourceError("A2-003 cumulative active wall budget is exhausted before startup")
    if float(predecessor["fit_wall_seconds"]) >= float(limits["fit_wall_seconds"]):
        raise StudyResourceError("A2-003 cumulative verifier fit wall budget is exhausted before startup")
    if int(predecessor["verifier_fit_attempts"]) >= int(limits["verifier_fit_attempts"]):
        raise StudyResourceError("A2-003 cumulative verifier fit-attempt budget is exhausted before startup")
    known_disk = sum(
        int(row["output_tree_bytes"]) + int(row["external_ledger_bytes"])
        for row in predecessor["members"]
    )
    if known_disk >= int(limits["disk_bytes"]):
        raise StudyResourceError("A2-003 family disk budget is exhausted before startup")
    available = available_memory_bytes()
    if available < 5 * 1024**3:
        result = {
            "status": "NOT_STARTED_INSUFFICIENT_HEADROOM",
            "study_id": STUDY_003_ID,
            "config_sha256": actual_digest,
            "startup_available_bytes": available,
            "required_startup_available_bytes": 5 * 1024**3,
            "predecessor": predecessor,
            "a2_code_identity": code_identity,
        }
        return result, config, output, code_identity
    ceiling = compute_003_rss_ceiling(available)
    return {
        "status": "PREFLIGHT_READY",
        "study_id": STUDY_003_ID,
        "config_sha256": actual_digest,
        "startup_available_bytes": available,
        "rss_ceiling_bytes": ceiling,
        "predecessor": predecessor,
        "a2_code_identity": code_identity,
    }, config, output, code_identity


def _light_a2_003_ready_check(
    output: Path,
    *,
    config: dict[str, object],
    config_digest: str,
    code_identity: dict[str, str],
) -> dict[str, object]:
    report_path = output / "audit-ready.json"
    sidecar = output / "audit-ready.sha256"
    status_path = output / "run-status.json"
    if not all(path.is_file() for path in (report_path, sidecar, status_path)):
        raise StudyResourceError("A2-003 hash-bound AUDIT_READY evidence is missing")
    expected_hash = sidecar.read_text(encoding="ascii").strip().split()[0]
    actual_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise StudyResourceError("A2-003 AUDIT_READY hash mismatch")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if (
        not isinstance(report, dict)
        or report.get("status") != "AUDIT_READY"
        or report.get("study_id") != STUDY_003_ID
        or report.get("study_output") != config["study_output"]
        or report.get("config_sha256") != config_digest
        or report.get("a2_code_identity") != code_identity
        or not isinstance(status, dict)
        or status.get("status") != "AUDIT_READY"
        or status.get("study_id") != STUDY_003_ID
        or status.get("config_sha256") != config_digest
    ):
        raise StudyResourceError("A2-003 AUDIT_READY identity/status binding mismatch")
    return report


def _create_003_lock(lock_path: Path, mode: str) -> None:
    lock_path.parent.mkdir(exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise StudyLedgerIntegrityError("A2-003 lock exists; this study cannot be resumed or retried") from exc
    try:
        os.write(fd, f"pid={os.getpid()} mode={mode}\n".encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _launch_003(
    mode: str,
    workspace: str | Path,
    *,
    config_digest: str,
    study_notes: str,
) -> dict[str, object]:
    if mode not in {"preflight", "audit", "run"}:
        raise ValueError("A2-003 exposes only preflight, audit and run modes")
    root = Path(workspace).resolve()
    try:
        preflight, config, output, code_identity = _a2_003_read_only_preflight(root, config_digest)
    except Exception as exc:
        return {
            "status": "NOT_STARTED_GATE_FAILED",
            "study_id": STUDY_003_ID,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if mode == "preflight" or preflight["status"] == "NOT_STARTED_INSUFFICIENT_HEADROOM":
        return preflight

    artifacts = root / "artifacts"
    external = root / str(config["ledger_path"])
    lock_path = root / str(config["lock_path"])
    if mode == "audit":
        mirror = output / "a2-study-budget.jsonl"
        if output.exists() or external.exists() or mirror.exists() or lock_path.exists():
            return {
                "status": "NOT_STARTED_GATE_FAILED",
                "study_id": STUDY_003_ID,
                "reason": "A2-003 fixed namespace is already present; retry is forbidden",
            }
        try:
            _create_003_lock(lock_path, mode)
            output.mkdir()
        except Exception as exc:
            try:
                lock_path.unlink()
            except OSError:
                pass
            return {"status": "NOT_STARTED_GATE_FAILED", "study_id": STUDY_003_ID, "reason": f"{type(exc).__name__}: {exc}"}
        predecessor = preflight["predecessor"]
        resources = {
            "startup_available_bytes": int(preflight["startup_available_bytes"]),
            "rss_ceiling_bytes": int(preflight["rss_ceiling_bytes"]),
        }
    else:
        if not output.is_dir():
            return {"status": "NOT_STARTED_GATE_FAILED", "study_id": STUDY_003_ID, "reason": "run requires existing A2-003 output"}
        predecessor = preflight["predecessor"]
        try:
            ledger = StudyLedger(artifacts, output, limits=config["limits"], study_id=STUDY_003_ID, predecessor=predecessor, config_sha256=config_digest)
            ledger.assert_no_unclosed_intervals()
            ledger.assert_can_start_run()
            startup = next((row for row in ledger.records() if row.get("event") == "startup_resources"), None)
            if not isinstance(startup, dict):
                raise StudyResourceError("A2-003 persisted startup RSS ceiling is missing")
            _light_a2_003_ready_check(output, config=config, config_digest=config_digest, code_identity=code_identity)
            current_available = available_memory_bytes()
            required = minimum_run_available_bytes(int(startup["rss_ceiling_bytes"]))
            if current_available < required:
                return {
                    "status": "RUN_NOT_STARTED_INSUFFICIENT_HEADROOM",
                    "study_id": STUDY_003_ID,
                    "startup_rss_ceiling_bytes": int(startup["rss_ceiling_bytes"]),
                    "current_available_bytes": current_available,
                    "required_available_bytes": required,
                    "audit_ready_sha256": hashlib.sha256((output / "audit-ready.json").read_bytes()).hexdigest(),
                }
            active_used = ledger.assert_can_start_invocation()
            ledger.assert_fit_wall_budget()
            ledger.measure_disk(max_disk_bytes=int(config["limits"]["disk_bytes"]))
        except Exception as exc:
            return {"status": "NOT_STARTED_GATE_FAILED", "study_id": STUDY_003_ID, "reason": f"{type(exc).__name__}: {exc}"}
        try:
            _create_003_lock(lock_path, mode)
        except Exception as exc:
            return {"status": "NOT_STARTED_GATE_FAILED", "study_id": STUDY_003_ID, "reason": f"{type(exc).__name__}: {exc}"}
        resources = {
            "startup_available_bytes": int(startup["startup_available_bytes"]),
            "rss_ceiling_bytes": int(startup["rss_ceiling_bytes"]),
            "current_available_bytes": current_available,
            "required_run_available_bytes": required,
        }

    ledger: StudyLedger | None = None
    invocation_id = f"{mode}-{time.time_ns()}"
    invocation_started: float | None = None
    telemetry: dict[str, object] = {}
    status = "INVALID"
    cause: str | None = None
    failure: Exception | None = None
    finalized = False
    try:
        ledger = StudyLedger(
            artifacts,
            output,
            limits=config["limits"],
            study_id=STUDY_003_ID,
            predecessor=predecessor,
            config_sha256=config_digest,
        )
        ledger.assert_no_unclosed_intervals()
        if mode == "audit":
            ledger.assert_can_start_audit()
            # The first durable 003 record is the complete, hash-bound family
            # predecessor snapshot, before startup resources or worker files.
            ledger.append("predecessor", {"predecessor": predecessor})
            ledger.append("startup_resources", resources)
            (output / "study-notes.md").write_text(study_notes.rstrip() + "\n", encoding="utf-8")
        else:
            ledger.assert_can_start_run()
        invocation_started = time.monotonic()
        ledger.append("invocation_start", {"id": invocation_id, "mode": mode, "monotonic": invocation_started})
        active_used = ledger.assert_can_start_invocation()
        ledger.mark_status("AUDITING" if mode == "audit" else "RUNNING", invocation_id=invocation_id)
        _write_json(output / "run-status.json", {
            "status": "AUDITING" if mode == "audit" else "RUNNING",
            "study_id": STUDY_003_ID,
            "study_output": str(config["study_output"]),
            "config_sha256": config_digest,
        })
        request = {
            "mode": mode,
            "study_id": STUDY_003_ID,
            "workspace": str(root),
            "output": str(output),
            "config_sha256": config_digest,
            "startup_resources": resources,
            "response": str(output / f"worker-response-{mode}.json"),
            "request": str(output / f"worker-request-{mode}.json"),
        }
        _write_json(Path(request["request"]), request)
        command = [sys.executable, "-m", "eating_event.a2.worker", str(request["request"])]
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
        if not isinstance(response, dict) or (
            response.get("study_id") != STUDY_003_ID
            or response.get("config_sha256") != config_digest
            or Path(str(response.get("study_output", ""))).resolve() != output
        ):
            raise StudyResourceError("A2-003 worker response identity mismatch")
        status = str(response.get("status", "INVALID"))
        allowed_statuses = {"AUDIT_READY"} if mode == "audit" else {"COMPLETE"}
        if status in allowed_statuses and telemetry.get("returncode") != 0:
            raise StudyResourceError("A2-003 worker exit/status mismatch")
        if status not in allowed_statuses | {"INVALID", "VERIFIER_DATA_INSUFFICIENT", "INCOMPLETE_RESOURCE", "INCOMPLETE_INTERRUPTED"}:
            status = "INVALID"
        if mode == "audit" and status == "AUDIT_READY":
            _light_a2_003_ready_check(output, config=config, config_digest=config_digest, code_identity=code_identity)
        telemetry["invocation_elapsed_seconds"] = time.monotonic() - invocation_started
        _write_json(output / "resource-summary.json", telemetry)
        ledger.append("invocation_end", {"id": invocation_id, "duration_seconds": telemetry["invocation_elapsed_seconds"]})
        ledger.mark_status(status, invocation_id=invocation_id)
        _write_json(output / "run-status.json", {
            "status": status,
            "study_id": STUDY_003_ID,
            "study_output": str(config["study_output"]),
            "config_sha256": config_digest,
            "audit_ready_sha256": response.get("audit_ready_sha256") if status == "AUDIT_READY" else None,
            "reason": response.get("reason"),
        })
        response["resource_summary"] = telemetry
        response["budget_ledger"] = _ledger_snapshot(ledger)
        if status == "COMPLETE":
            _finalize_003_complete_output(root, output, ledger, response, telemetry)
        elif status not in {"AUDIT_READY"}:
            _write_003_stop_record(output, ledger, status=status, cause=response.get("reason"), telemetry=telemetry, failure=None)
        finalized = True
        return response
    except StudyResourceError as exc:
        failure = exc
        status, cause = "INCOMPLETE_RESOURCE", str(exc)
    except StudyInterrupted as exc:
        failure = exc
        status, cause = "INCOMPLETE_INTERRUPTED", str(exc)
    except KeyboardInterrupt as exc:
        failure = exc
        status, cause = "INCOMPLETE_INTERRUPTED", "A2-003 supervisor was interrupted by the operator"
    except Exception as exc:
        failure = exc
        cause = f"{type(exc).__name__}: {exc}"
        status = "VERIFIER_DATA_INSUFFICIENT" if cause.startswith("ValueError: G3:") else "INVALID"
    finally:
        if finalized:
            pass
        elif ledger is not None and invocation_started is not None:
            try:
                duration = max(0.0, time.monotonic() - invocation_started)
                if not any(row.get("event") == "invocation_end" and row.get("id") == invocation_id for row in ledger.records()):
                    ledger.append("invocation_end", {"id": invocation_id, "duration_seconds": duration})
                ledger.mark_status(status, invocation_id=invocation_id, cause=cause)
                _write_json(output / "run-status.json", {
                    "status": status,
                    "study_id": STUDY_003_ID,
                    "study_output": str(config["study_output"]),
                    "config_sha256": config_digest,
                    "cause": cause,
                })
                _write_003_stop_record(output, ledger, status=status, cause=cause, telemetry=telemetry, failure=failure)
            except Exception:
                status, cause = "INCOMPLETE_RESOURCE", "A2-003 could not persist its terminal resource evidence"
        elif ledger is not None and output.is_dir():
            try:
                ledger.mark_status(status, cause=cause)
                _write_json(output / "run-status.json", {
                    "status": status,
                    "study_id": STUDY_003_ID,
                    "study_output": str(config["study_output"]),
                    "config_sha256": config_digest,
                    "cause": cause,
                })
                _write_003_stop_record(output, ledger, status=status, cause=cause, telemetry=telemetry, failure=failure)
            except Exception:
                status, cause = "INCOMPLETE_RESOURCE", "A2-003 could not persist terminal evidence"
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
    return {"status": status, "reason": cause, "budget_ledger": _ledger_snapshot(ledger) if ledger is not None else None}


def _write_003_stop_record(
    output: Path,
    ledger: StudyLedger,
    *,
    status: str,
    cause: object,
    telemetry: dict[str, object],
    failure: Exception | None,
) -> None:
    from eating_event.a2.budget import FitAttemptLedger

    records = ledger.records()
    startup = next((row for row in records if row.get("event") == "startup_resources"), {})
    samples = [row for row in records if row.get("event") == "resource_sample"]
    last_sample = samples[-1] if samples else {}
    rss_values = [int(row["rss_bytes"]) for row in samples if isinstance(row.get("rss_bytes"), int)]
    failure_value = getattr(failure, "failing_measurement_bytes", None) if failure is not None else None
    stop = {
        "schema": "a2_003_validation_stop_record_v1",
        "study_id": STUDY_003_ID,
        "study_output": "artifacts/a2-context-verifier-v1-003",
        "status": status,
        "cause": cause,
        "audit_calls": sum(row.get("event") == "invocation_start" and row.get("mode") == "audit" for row in records),
        "run_calls": sum(row.get("event") == "invocation_start" and row.get("mode") == "run" for row in records),
        "audit_ready": ledger.current_status() == "AUDIT_READY",
        "rss_accounting": {
            "startup_available_bytes": startup.get("startup_available_bytes"),
            "ceiling_bytes": startup.get("rss_ceiling_bytes"),
            "peak_rss_bytes": max(rss_values, default=telemetry.get("peak_rss_bytes")),
            "failing_measurement_bytes": failure_value,
            "last_completed_stage": getattr(failure, "last_completed_stage", last_sample.get("last_completed_stage")),
            "worker_pid": getattr(failure, "worker_pid", last_sample.get("worker_pid")),
            "process_tree": getattr(failure, "process_tree", last_sample.get("process_tree")),
        },
        "active_wall_seconds": ledger.active_wall_seconds(),
        "fit_accounting": {
            "combined_fit_wall_seconds": FitAttemptLedger(ledger).fit_wall_seconds(),
            "combined_verifier_fit_attempts": FitAttemptLedger(ledger).attempt_count(),
            "candidate_fit_attempts": 0,
            "candidate_predict_attempts": 0,
        },
        "family_disk_bytes": ledger.measure_disk(max_disk_bytes=int(ledger.limits["disk_bytes"])),
        "resource_samples": len(samples),
        "four_numeric_stage_states": {
            "a2_numeric_minimum": "NOT_EVALUATED",
            "a2_numeric_ideal": "NOT_EVALUATED",
            "a2_stage_minimum": "NOT_EVALUATED",
            "a2_stage_ideal": "NOT_EVALUATED",
        },
        "study_conclusions": {
            "a1": "CLOSED",
            "formal_g1": "FAIL",
            "full_training": "BLOCKED",
            "independent_participant_confirmation": False,
            "production": "UNCHANGED",
        },
    }
    _write_json(output / "validation-stop-record.json", stop)


def _finalize_003_complete_output(
    workspace: Path,
    output: Path,
    ledger: StudyLedger,
    response: dict[str, object],
    telemetry: dict[str, object],
) -> None:
    from eating_event.a2.budget import FitAttemptLedger

    metrics_path = output / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    family_bytes = ledger.measure_disk(max_disk_bytes=int(ledger.limits["disk_bytes"]))
    snapshot = _ledger_snapshot(ledger)
    startup = next(row for row in ledger.records() if row.get("event") == "startup_resources")
    resources = {
        **telemetry,
        "family_disk_bytes_total": family_bytes,
        "rss_ceiling_bytes": int(startup["rss_ceiling_bytes"]),
        "startup_available_bytes": int(startup["startup_available_bytes"]),
        "active_wall_seconds_total": ledger.active_wall_seconds(),
        "a2_003_active_wall_seconds": ledger.local_active_wall_seconds(),
        "inherited_001_002_active_wall_seconds": ledger.predecessor_usage()["active_wall_seconds"],
        "fit_wall_seconds_total": FitAttemptLedger(ledger).fit_wall_seconds(),
        "a2_003_fit_wall_seconds": FitAttemptLedger(ledger).local_fit_wall_seconds(),
        "verifier_fit_attempts_total": FitAttemptLedger(ledger).attempt_count(),
        "candidate_fit_attempts": 0,
        "candidate_predict_attempts": 0,
        "thread_limit": 4,
    }
    metrics["resource_accounting"] = resources
    metrics["budget_ledger"] = snapshot
    metrics["study_id"] = STUDY_003_ID
    metrics["unknown_behavior_note"] = (
        "No independent participant confirmation or on-site video is available. "
        "Long false positives are described under the approved annotation contract only."
    )
    _write_json(metrics_path, metrics)
    summary_path = output / "resource-summary.json"
    _write_json(summary_path, resources)
    report_path = output / "report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else "# A2-003 validation\n"
    report += "\n## Resource and evidence accounting\n\n"
    report += f"- A2 family active wall: {resources['active_wall_seconds_total']:.3f} / 7,200 seconds.\n"
    report += f"- Verifier fit wall: {resources['fit_wall_seconds_total']:.3f} / 3,600 seconds; attempts {resources['verifier_fit_attempts_total']} / 25.\n"
    report += f"- Candidate fit/predict: 0 / 0.\n- Process-tree RSS peak: {resources.get('peak_rss_bytes')} bytes; frozen ceiling {resources['rss_ceiling_bytes']} bytes.\n"
    report += f"- Family disk: {family_bytes} / 1,073,741,824 bytes.\n"
    report += "- No independent participant confirmation or on-site video exists; long false positives remain annotation-contract findings.\n"
    report += "- A1=CLOSED; Formal G1=FAIL; full training=BLOCKED; production=UNCHANGED.\n"
    report_path.write_text(report, encoding="utf-8")
    manifest_path = output / "run-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["resource_accounting"] = resources
        manifest["budget_ledger"] = snapshot
        manifest["predecessor_family"] = ledger.predecessor
        _write_json(manifest_path, manifest)
    checksums: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"final-checksums.json", "run-status.json", "worker.log", "resource-segments.jsonl", "a2-study-budget.jsonl"}:
            checksums[path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(output / "final-checksums.json", checksums)


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
