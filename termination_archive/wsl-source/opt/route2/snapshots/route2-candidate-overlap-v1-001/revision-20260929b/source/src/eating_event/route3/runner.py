"""No-retry audit and single nested run for Route 3 matching-aware targets."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Mapping

from eating_event.route3.budget import Route3Budget, Route3ResourceError
from eating_event.route3.workflow import (
    _file_sha256,
    build_fit_compositions,
    load_a2_004_corpus,
    load_route3_config,
    make_route3_audit_ready,
    prepare_matching_aware_corpus,
    route3_environment_identity,
    route3_size_profile,
    verify_a2_004_complete,
    verify_route3_audit_ready,
    verify_route3_environment,
    write_json,
)


def _canonical_sha256(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _same_json(left: object, right: object) -> bool:
    return _canonical_sha256(left) == _canonical_sha256(right)


def _budget(workspace: Path, config: Mapping[str, object], config_sha256: str, mode: str) -> Route3Budget:
    import psutil

    return Route3Budget(
        output_dir=workspace / str(config["study_output"]),
        ledger_path=workspace / str(config["ledger_path"]),
        lock_path=workspace / str(config["lock_path"]),
        config_sha256=config_sha256,
        limits=config["limits"],
        startup_available_bytes=int(psutil.virtual_memory().available),
        mode=mode,
        study_id=str(config["study_id"]),
    )


def _write_status(
    output: Path,
    *,
    status: str,
    config: Mapping[str, object],
    config_sha256: str,
    reason: str | None = None,
    audit_ready_sha256: str | None = None,
) -> None:
    write_json(output / "run-status.json", {
        "status": status,
        "study_id": config["study_id"],
        "study_output": config["study_output"],
        "config_sha256": config_sha256,
        "audit_ready_sha256": audit_ready_sha256,
        "reason": reason,
    })


def _population_summary(corpus, config: Mapping[str, object]) -> dict[str, object]:
    candidates = [role for role in corpus.roles if role.kind == "candidate"]
    verifiers = [role for role in corpus.roles if role.kind == "verifier"]
    summary = {
        "participants": len(corpus.participants),
        "eligible_gt": sum(len(corpus.truths_by_participant.get(p, ())) for p in corpus.participants),
        "candidate_roles": len(candidates),
        "verifier_roles": len(verifiers),
    }
    expected = config["evaluator"]
    for actual_key, config_key in (
        ("participants", "participants"),
        ("eligible_gt", "eligible_ground_truth"),
        ("candidate_roles", "candidate_roles"),
        ("verifier_roles", "verifier_roles"),
    ):
        if summary[actual_key] != expected[config_key]:
            raise ValueError(f"Route 3 population mismatch for {actual_key}")
    return summary


def _budget_summary(budget: Route3Budget, score_calls: int | None = None) -> dict[str, object]:
    summary = budget.snapshot()
    if score_calls is not None:
        summary["verifier_score_calls"] = score_calls
    return summary


def run_audit(
    workspace: str | Path,
    *,
    study_id: str = "route3-matching-aware-v1-001",
) -> dict[str, object]:
    root = Path(workspace).resolve()
    config, config_sha = load_route3_config(root, study_id=study_id)
    verify_route3_environment(config)
    budget: Route3Budget | None = None
    output = root / str(config["study_output"])
    ready_file_sha: str | None = None
    try:
        budget = _budget(root, config, config_sha, "audit")
        budget.check()
        source_status = verify_a2_004_complete(root, config)
        corpus = load_a2_004_corpus(root, progress_callback=lambda _: budget.check())
        population = _population_summary(corpus, config)
        prepared, target_audit = prepare_matching_aware_corpus(
            corpus,
            iou_threshold=float(config["target"]["iou_threshold"]),
            expected_fit_count=int(config["verifier"]["fit_attempts"]),
        )
        del corpus
        budget.check()
        provenance_precheck = _precheck_actual_fit_records(prepared, target_audit, budget)
        size_profile = route3_size_profile(
            target_audit,
            config,
            rss_ceiling_bytes=budget.rss_ceiling,
        )
        ready = make_route3_audit_ready(root, config, config_sha, prepared, target_audit)
        ready["source_a2_status"] = source_status
        ready["population"] = population
        ready["synthetic_size_profile_sha256"] = _canonical_sha256(size_profile)
        ready["actual_fit_provenance_precheck_sha256"] = _canonical_sha256(provenance_precheck)
        ready["audit_ready_sha256"] = _canonical_sha256({key: value for key, value in ready.items() if key != "audit_ready_sha256"})
        write_json(output / "target-audit.json", target_audit)
        write_json(output / "fit-provenance-precheck.json", provenance_precheck)
        write_json(output / "synthetic-size-profile.json", size_profile)
        write_json(output / "audit-ready.json", ready)
        ready_file_sha = _file_sha256(output / "audit-ready.json")
        _write_status(
            output,
            status="AUDIT_READY",
            config=config,
            config_sha256=config_sha,
            audit_ready_sha256=ready_file_sha,
        )
        budget.check()
        budget.close("AUDIT_READY")
        write_json(output / "resource-summary.json", _budget_summary(budget))
        return {
            "status": "AUDIT_READY",
            "study_id": config["study_id"],
            "audit_ready_sha256": ready_file_sha,
            "population": population,
            "verifier_fit_count": len(target_audit["verifier_fits"]),
            "resource_summary": _budget_summary(budget),
        }
    except Route3ResourceError as exc:
        status, reason = "INCOMPLETE_RESOURCE", str(exc)
    except ValueError as exc:
        message = str(exc)
        status = "DATA_INSUFFICIENT" if "G3" in message else "INVALID"
        reason = message
    except Exception as exc:
        status, reason = "INVALID", f"{type(exc).__name__}: {exc}"
    if budget is not None:
        _write_status(output, status=status, config=config, config_sha256=config_sha, reason=reason)
        budget.close(status)
        summary = _budget_summary(budget)
        write_json(output / "resource-summary.json", summary)
    return {"status": status, "study_id": config["study_id"], "reason": reason}


class _BudgetedVerifierBackend:
    def __init__(self, config: Mapping[str, object], budget: Route3Budget) -> None:
        from eating_event.a2.execution import DefaultVerifierBackend

        self.delegate = DefaultVerifierBackend(config)
        self.budget = budget
        self.score_calls = 0

    def fit(self, features, labels, participants, role):
        self.budget.check()
        model = self.delegate.fit(features, labels, participants, role)
        self.budget.check()
        return model

    def score(self, model, features, participants, role):
        self.budget.check()
        self.score_calls += 1
        if self.score_calls > 25:
            raise Route3ResourceError("Route 3 verifier score-call cap exceeded")
        scores = self.delegate.score(model, features, participants, role)
        self.budget.check()
        return scores


def _render_route3_report(result: Mapping[str, object]) -> str:
    pooled = result["pooled"]
    status = result.get("status", "COMPLETE")
    lines = [
        "# Route 3 matching-aware target validation",
        "",
        f"Status: `{status}` (local development folds; no independent participant confirmation).",
        "",
        "Training labels mark only candidates selected by the local participant-level strict-IoU one-to-one matcher. Candidate intervals, 26D features, role graph, HGB settings, thresholds, decoder, and evaluator were frozen.",
        "",
        "| Fold | TP | FP | FN | F1 | Long FP | Long-FP fraction | Start MAE (s) | End MAE (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["outer_results"]:
        f1 = "NA" if row["f1"] is None else f"{row['f1']:.6f}"
        lines.append(
            f"| {row['fold_id']} | {row['tp']} | {row['fp']} | {row['fn']} | {f1} | {row['long_fp_count']} | {row['long_fp_fraction']:.6f} | {row['start_mae_s'] if row['start_mae_s'] is not None else 'NA'} | {row['end_mae_s'] if row['end_mae_s'] is not None else 'NA'} |"
        )
    pooled_f1 = "NA" if pooled["f1"] is None else f"{pooled['f1']:.6f}"
    lines.extend([
        f"| pooled | {pooled['tp']} | {pooled['fp']} | {pooled['fn']} | {pooled_f1} | {pooled['long_fp_count']} | {pooled['long_fp_fraction']:.6f} | {pooled['start_mae_ms'] / 1000 if pooled['start_mae_ms'] is not None else 'NA'} | {pooled['end_mae_ms'] / 1000 if pooled['end_mae_ms'] is not None else 'NA'} |",
        "",
        f"- Numeric minimum / ideal: {result['route3_numeric_minimum']} / {result['route3_numeric_ideal']}",
        f"- Stage minimum / ideal: {result['route3_stage_minimum']} / {result['route3_stage_ideal']}",
        f"- Candidate fit / predict: {result['candidate_fit_attempts']} / {result['candidate_predict_attempts']}",
        f"- Verifier fits / scores / decodes / outer evaluations: {result['call_accounting']['verifier_fit_attempts']} / {result['call_accounting']['verifier_score_calls']} / {result['call_accounting']['total_decodes']} / {result['call_accounting']['outer_evaluations']}",
        "- A1 remains closed; Formal G1=FAIL; full training=BLOCKED; production=UNCHANGED.",
        "- The result is development evidence over previously exposed participants and does not verify the official matcher, inference interface, or PPG requirement.",
        "",
    ])
    return "\n".join(lines)


def _expected_fit_rows(target_audit: Mapping[str, object]) -> dict[str, dict[str, object]]:
    expected_rows = target_audit.get("verifier_fits")
    if not isinstance(expected_rows, list) or len(expected_rows) != 25:
        raise ValueError("Route 3 fit provenance count differs from the audited plan")
    by_role: dict[str, dict[str, object]] = {}
    for row in expected_rows:
        if not isinstance(row, dict) or not isinstance(row.get("verifier_role_id"), str):
            raise ValueError("Route 3 fit provenance row is malformed")
        role_id = row["verifier_role_id"]
        if role_id in by_role:
            raise ValueError("Route 3 audited fit role is duplicated")
        by_role[role_id] = row
    return by_role


def _validate_fit_record(actual: Mapping[str, object], expected: Mapping[str, object]) -> None:
    fields = {
        "verifier_role_id": "role_id",
        "candidate_count": "candidate_count",
        "positive_candidate_count": "positive_candidate_count",
        "positive_participant_count": "positive_participant_count",
        "ordered_candidate_keys_sha256": "ordered_candidate_keys_sha256",
        "feature_matrix_sha256": "feature_matrix_sha256",
        "training_label_join_sha256": "training_label_join_sha256",
    }
    if any(key not in expected or value not in actual or expected[key] != actual[value] for key, value in fields.items()):
        raise ValueError(f"Route 3 actual fit inputs differ from pre-fit audit for {expected.get('verifier_role_id')}")
    if "training_candidate_role_ids" not in expected or sorted(expected["training_candidate_role_ids"]) != actual.get("training_candidate_roles"):
        raise ValueError(f"Route 3 candidate role composition differs for {expected.get('verifier_role_id')}")


def _actual_fit_record(rows, role) -> dict[str, object]:
    """Measure actual executor inputs; never substitute expected audit values."""
    import numpy as np
    from eating_event.a2 import execution as a2_execution

    features, labels, participants = a2_execution._candidate_arrays(rows)
    if set(participants) - set(role.fit_participants) or set(role.outer_valid) & set(participants):
        raise ValueError("Route 3 actual fit participants violate the frozen role")
    return {
        "role_id": role.role_id,
        "training_candidate_roles": sorted({row.role_id for row in rows}),
        "fit_participants": sorted(set(participants)),
        "candidate_count": int(features.shape[0]),
        "candidate_count_source": "actual_feature_matrix_rows",
        "positive_candidate_count": int(np.count_nonzero(labels == 1)),
        "positive_participant_count": len({p for p, label in zip(participants, labels) if label == 1}),
        "ordered_candidate_keys_sha256": a2_execution._role_hash(rows),
        "feature_matrix_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "training_label_join_sha256": a2_execution._labels_hash(rows),
    }


def _precheck_actual_fit_records(corpus, target_audit, budget) -> dict[str, object]:
    """Check all actual row compositions before any fit reservation."""
    expected_by_role = _expected_fit_rows(target_audit)
    role_by_id = {role.role_id: role for role in corpus.roles}
    # This is the existing composer whose ordering mirrors execute_validation.
    compositions = build_fit_compositions(corpus.roles, corpus.candidates_by_role, {})
    records = []
    for composition in compositions:
        budget.check()
        record = _actual_fit_record(composition.rows, role_by_id[composition.verifier_role_id])
        expected = expected_by_role.get(str(record["role_id"]))
        if expected is None:
            raise ValueError("Route 3 actual precheck fit role was not audited")
        _validate_fit_record(record, expected)
        records.append(record)
    _validate_fit_provenance({"verifier_fit_provenance": records}, target_audit)
    return {"schema": "route3_actual_fit_provenance_precheck_v1", "status": "PASS", "fit_calls": 0, "records": records}


def _validate_fit_provenance(result: dict[str, object], target_audit: Mapping[str, object]) -> None:
    expected_by_role = _expected_fit_rows(target_audit)
    actual_rows = result.get("verifier_fit_provenance")
    if not isinstance(actual_rows, list) or len(actual_rows) != len(expected_by_role):
        raise ValueError("Route 3 fit provenance count differs from the audited plan")
    seen = []
    for actual in actual_rows:
        if not isinstance(actual, dict):
            raise ValueError("Route 3 actual fit provenance row is malformed")
        role_id = actual.get("role_id")
        if not isinstance(role_id, str) or role_id in seen or role_id not in expected_by_role:
            raise ValueError("Route 3 actual fit role is duplicated or unaudited")
        seen.append(role_id)
        expected = expected_by_role[role_id]
        _validate_fit_record(actual, expected)
        actual["route3_distinct_positive_gt_count"] = expected.get("distinct_positive_gt_count")
    if seen != list(expected_by_role):
        raise ValueError("Route 3 actual fit order differs from the audited plan")


def run_experiment(
    workspace: str | Path,
    *,
    study_id: str = "route3-matching-aware-v1-001",
) -> dict[str, object]:
    root = Path(workspace).resolve()
    config, config_sha = load_route3_config(root, study_id=study_id)
    output = root / str(config["study_output"])
    budget: Route3Budget | None = None
    backend: _BudgetedVerifierBackend | None = None
    decode_counter = [0]
    original_decoded = None
    original_persist_fit = None
    call_accounting: dict[str, object] | None = None
    status = "INVALID"
    reason: str | None = None
    result: dict[str, object] | None = None
    try:
        budget = _budget(root, config, config_sha, "run")
        budget.check()
        verify_route3_environment(config)
        ready = verify_route3_audit_ready(root, config, config_sha)
        _write_status(
            output,
            status="RUNNING",
            config=config,
            config_sha256=config_sha,
            audit_ready_sha256=_file_sha256(output / "audit-ready.json"),
        )
        source_corpus = load_a2_004_corpus(root, progress_callback=lambda _: budget.check())
        population = _population_summary(source_corpus, config)
        prepared, target_audit = prepare_matching_aware_corpus(
            source_corpus,
            iou_threshold=float(config["target"]["iou_threshold"]),
            expected_fit_count=int(config["verifier"]["fit_attempts"]),
        )
        del source_corpus
        provenance_precheck = _precheck_actual_fit_records(prepared, target_audit, budget)
        actual_ready = make_route3_audit_ready(root, config, config_sha, prepared, target_audit)
        actual_ready["source_a2_status"] = ready["source_a2_status"]
        actual_ready["population"] = population
        actual_ready["synthetic_size_profile_sha256"] = ready["synthetic_size_profile_sha256"]
        actual_ready["actual_fit_provenance_precheck_sha256"] = _canonical_sha256(provenance_precheck)
        actual_ready["audit_ready_sha256"] = _canonical_sha256({
            key: value for key, value in actual_ready.items() if key != "audit_ready_sha256"
        })
        if not _same_json(actual_ready, ready):
            raise ValueError("Route 3 source, role, target, environment, or code digest changed after audit")
        budget.check()

        prepared = replace(prepared, output_dir=output)
        from eating_event.a2 import execution as a2_execution

        original_decoded = a2_execution._decoded
        original_persist_fit = a2_execution._persist_fit
        expected_by_role = _expected_fit_rows(target_audit)
        persisted_roles: set[str] = set()

        def persist_actual_fit(corpus, role, rows, model, fit_record):
            actual = _actual_fit_record(rows, role)
            # Existing fields must agree with measured inputs. Only the missing
            # total row count and its source are added to the shared record.
            for key, value in actual.items():
                if key not in {"candidate_count", "candidate_count_source"} and fit_record.get(key) != value:
                    raise ValueError(f"Route 3 actual fit record is inconsistent for {role.role_id}: {key}")
            if "candidate_count" in fit_record and fit_record["candidate_count"] != actual["candidate_count"]:
                raise ValueError("Route 3 actual candidate_count conflicts with measured inputs")
            fit_record["candidate_count"] = actual["candidate_count"]
            fit_record["candidate_count_source"] = actual["candidate_count_source"]
            expected = expected_by_role.get(role.role_id)
            if expected is None or role.role_id in persisted_roles:
                raise ValueError("Route 3 persist fit role is duplicated or unaudited")
            _validate_fit_record(fit_record, expected)
            original_persist_fit(corpus, role, rows, model, fit_record)
            persisted_roles.add(role.role_id)

        def counted_decoded(*args, **kwargs):
            decode_counter[0] += 1
            return original_decoded(*args, **kwargs)

        a2_execution._decoded = counted_decoded
        a2_execution._persist_fit = persist_actual_fit
        backend = _BudgetedVerifierBackend(prepared.config or {}, budget)
        result = a2_execution.execute_validation(prepared, backend=backend, budget=budget)
        call_accounting = {
            "candidate_fit_attempts": int(result["candidate_fit_attempts"]),
            "candidate_predict_attempts": int(result["candidate_predict_attempts"]),
            "verifier_fit_attempts": int(result["verifier_fit_attempts"]),
            "verifier_score_calls": backend.score_calls,
            "inner_threshold_decodes": decode_counter[0] - 5,
            "outer_decodes": 5,
            "total_decodes": decode_counter[0],
            "outer_evaluations": len(result["outer_results"]),
        }
        expected_calls = {
            "candidate_fit_attempts": 0,
            "candidate_predict_attempts": 0,
            "verifier_fit_attempts": 25,
            "verifier_score_calls": 25,
            "inner_threshold_decodes": 60,
            "outer_decodes": 5,
            "total_decodes": 65,
            "outer_evaluations": 5,
        }
        result["call_accounting"] = call_accounting
        if call_accounting != expected_calls or budget._fit_attempts() != 25:
            raise ValueError(f"Route 3 call accounting mismatch: {call_accounting}")
        _validate_fit_provenance(result, target_audit)
        if persisted_roles != set(expected_by_role):
            raise ValueError("Route 3 actual persisted fit role set differs from the audit")
        result.update({
            "study_id": config["study_id"],
            "route3_target_method": config["target"]["method"],
            "route3_target_iou_threshold": config["target"]["iou_threshold"],
            "route3_predecoder_target": True,
            "route3_target_audit_sha256": target_audit["audit_sha256"],
            "route3_audit_ready_sha256": _file_sha256(output / "audit-ready.json"),
            "route3_numeric_minimum": bool(result["a2_numeric_minimum"]),
            "route3_numeric_ideal": bool(result["a2_numeric_ideal"]),
            "route3_stage_minimum": bool(result["a2_stage_minimum"]),
            "route3_stage_ideal": bool(result["a2_stage_ideal"]),
            "route3_protocol_status": "SUPPORTED_ON_DEVELOPMENT_FOLDS" if result["a2_stage_minimum"] else "CLOSED_STAGE_MINIMUM_FAIL",
            "call_accounting": call_accounting,
            "resource_limits": config["limits"],
        })
        result["status"] = "COMPLETE"
        write_json(output / "metrics.json", result)
        (output / "report.md").write_text(_render_route3_report(result), encoding="utf-8")
        write_json(output / "run-manifest.json", {
            "schema": "route3_matching_aware_run_manifest_v1",
            "study_id": config["study_id"],
            "config_sha256": config_sha,
            "audit_ready_sha256": result["route3_audit_ready_sha256"],
            "target_audit_sha256": target_audit["audit_sha256"],
            "source_a2": verify_a2_004_complete(root, config),
            "route3_code_identity": ready["route3_code_identity"],
            "environment": route3_environment_identity(),
            "call_accounting": call_accounting,
            "verifier_fit_provenance": result["verifier_fit_provenance"],
            "route3_protocol_status": result["route3_protocol_status"],
        })
        budget.check()
        status = "COMPLETE"
    except Route3ResourceError as exc:
        status, reason = "INCOMPLETE_RESOURCE", str(exc)
    except ValueError as exc:
        message = str(exc)
        status = "DATA_INSUFFICIENT" if "G3" in message else "INVALID"
        reason = message
    except Exception as exc:
        status, reason = "INVALID", f"{type(exc).__name__}: {exc}"
    finally:
        if original_decoded is not None or original_persist_fit is not None:
            from eating_event.a2 import execution as a2_execution

            if original_decoded is not None:
                a2_execution._decoded = original_decoded
            if original_persist_fit is not None:
                a2_execution._persist_fit = original_persist_fit

    if budget is not None:
        try:
            if status != "COMPLETE":
                observed_calls = call_accounting or {
                    "candidate_fit_attempts": 0,
                    "candidate_predict_attempts": 0,
                    "verifier_fit_attempts": budget._fit_attempts(),
                    "verifier_score_calls": 0 if backend is None else backend.score_calls,
                    "total_decodes": decode_counter[0],
                    "outer_evaluations": None,
                }
                if result is not None:
                    result["status"] = status
                    result["route3_failure_reason"] = reason
                    result["call_accounting"] = observed_calls
                    write_json(output / "metrics.json", result)
                # Failure rendering has no dependency on accepted metrics.
                (output / "report.md").write_text(
                    f"# Route 3 matching-aware target validation\n\nStatus: `{status}`.\n\nReason: {reason}\n\nObserved calls: `{json.dumps(observed_calls, sort_keys=True)}`.\n\nProvisional metrics are not accepted performance evidence.\n",
                    encoding="utf-8",
                )
                manifest_path = output / "run-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
                manifest.update({"study_id": config["study_id"], "config_sha256": config_sha, "run_status": status, "failure_reason": reason, "call_accounting": observed_calls})
                write_json(manifest_path, manifest)
        except Exception as exc:
            status = "INVALID"
            reason = f"{reason or 'Route 3 failure'}; failure artifact finalization: {type(exc).__name__}: {exc}"
        finally:
            budget.close(status)
        summary = _budget_summary(budget, None if backend is None else backend.score_calls)
        ready_path = output / "audit-ready.json"
        _write_status(
            output,
            status=status,
            config=config,
            config_sha256=config_sha,
            reason=reason,
            audit_ready_sha256=_file_sha256(ready_path) if ready_path.is_file() else None,
        )
        write_json(output / "resource-summary.json", summary)
    if status == "COMPLETE":
        return {
            "status": status,
            "study_id": config["study_id"],
            "metrics": result,
            "resource_summary": _budget_summary(budget, None if backend is None else backend.score_calls),
        }
    return {"status": status, "study_id": config["study_id"], "reason": reason}
