"""Private worker process for the supervised A2 audit and run commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def main() -> int:
    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    workspace = Path(request["workspace"]).resolve()
    output = Path(request["output"]).resolve()
    response_path = Path(request["response"]).resolve()
    mode = request["mode"]
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        if os.environ.get(variable) != "4":
            response = {"status": "INVALID", "reason": f"thread limit environment missing: {variable}"}
            response_path.write_text(json.dumps(response, sort_keys=True) + "\n", encoding="utf-8")
            return 2
    try:
        if mode == "audit":
            from eating_event.a2.audit import run_audit

            result = run_audit(
                workspace,
                output,
                config_sha256=request["config_sha256"],
                startup_resources=request.get("startup_resources"),
            )
        elif mode == "run":
            from eating_event.a2.audit import load_audited_corpus
            from eating_event.a2.budget import FitAttemptLedger, StudyLedger
            from eating_event.a2.execution import execute_validation

            corpus = load_audited_corpus(workspace, output)
            ledger = StudyLedger(workspace / "artifacts", output)
            result = execute_validation(corpus, budget=FitAttemptLedger(ledger))
            result["status"] = "COMPLETE"
            result["environment"] = _environment_identity()
            result["fit_budget"] = {
                "attempts": FitAttemptLedger(ledger).attempt_count(),
                "fit_wall_seconds": FitAttemptLedger(ledger).fit_wall_seconds(),
            }
            _write_run_manifest(workspace, output, corpus, result, request["config_sha256"])
        else:
            result = {"status": "INVALID", "reason": "unknown private worker mode"}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        from eating_event.a2.budget import StudyResourceError
        from eating_event.a2.audit import VerifierDataInsufficient

        if isinstance(exc, StudyResourceError):
            status = "INCOMPLETE_RESOURCE"
        elif isinstance(exc, VerifierDataInsufficient) or message.startswith("ValueError: G3:"):
            status = "VERIFIER_DATA_INSUFFICIENT"
        else:
            status = "INVALID"
        result = {"status": status, "reason": message}
    response_path.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result.get("status") in {"AUDIT_READY", "COMPLETE"} else 2


def _environment_identity() -> dict[str, object]:
    import importlib.metadata
    import platform

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "libraries": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "psutil")},
    }


def _write_run_manifest(workspace: Path, output: Path, corpus: object, result: object, config_sha256: str) -> None:
    from eating_event.a2.audit import current_a2_code_identity
    from eating_event.a2.inputs import sha256_file

    manifest = {
        "schema": "a2_run_manifest_v1",
        "status": "COMPLETE",
        "a1_run_id": "a1-end-to-end-feasibility-v1-005",
        "a1_final_checksums_sha256": "0543791e90df9e1bcf93111dc45e80678089898409e6888b90584fd18c469025",
        "a2_config_sha256": config_sha256,
        "a2_code_identity": current_a2_code_identity(workspace),
        "environment": _environment_identity(),
        "source_hashes": dict(getattr(corpus, "source_hashes", {}) or {}),
        "input_digests": dict(getattr(corpus, "input_digests", {}) or {}),
        "verifier_fit_attempts": result.get("verifier_fit_attempts"),
        "fit_budget": result.get("fit_budget"),
        "fold_results": result.get("outer_results"),
        "statuses": {
            "a2_numeric_minimum": result.get("a2_numeric_minimum"),
            "a2_numeric_ideal": result.get("a2_numeric_ideal"),
            "a2_stage_minimum": result.get("a2_stage_minimum"),
            "a2_stage_ideal": result.get("a2_stage_ideal"),
        },
    }
    target = output / "run-manifest.json"
    target.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _checksums: dict[str, str] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != target and path.name not in {"worker.log", "resource-segments.jsonl", "a2-study-budget.jsonl", "run-status.json"}:
            _checksums[str(path.relative_to(output)).replace("\\", "/")] = sha256_file(path)
    (output / "final-checksums.json").write_text(json.dumps(_checksums, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
