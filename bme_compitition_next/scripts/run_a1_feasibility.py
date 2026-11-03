"""Run the approved A1 audit and, only after it, the bounded research path."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any, Sequence

from eating_event.a1.budget import BudgetLedger, BudgetLimits, ResourceNotReady, ensure_disk_budget, sample_process_tree_rss
from eating_event.a1.contracts import A1Config, load_config
from eating_event.a1.inputs import InputBundle, load_inputs
from eating_event.a1.pipeline import build_role_graph, validate_role_graph
from eating_event.a1.anchors import verify_inputs, verify_bundle
from eating_event.a1.execution import write_json
from eating_event.a1.control import launch


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("audit", "run"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=None)
    return parser.parse_args(argv)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def measure_startup_resources() -> dict[str, int]:
    try:
        import psutil

        available = int(psutil.virtual_memory().available)
        if available <= 0:
            raise ResourceNotReady("startup available memory is unavailable")
        current_rss = sample_process_tree_rss()
    except ResourceNotReady:
        raise
    except Exception as exc:  # pragma: no cover - platform dependent
        raise ResourceNotReady("startup resource sampler unavailable") from exc
    return {
        "available_memory_bytes": available,
        "initial_rss_bytes": current_rss,
        "max_rss_bytes": min(8 * 1024**3, int(available * 0.60)),
    }


def _root_for(config_path: Path, root: Path | None) -> Path:
    if root is not None:
        return root.expanduser().resolve()
    return config_path.expanduser().resolve().parents[1]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_fold_manifest(root: Path, config: A1Config) -> dict[str, Any]:
    path = root / config.paths["fold_manifest"]
    payload = _load_json(path)
    if not isinstance(payload, dict) or set(payload) != {f"outer-{index}" for index in range(5)}:
        raise ValueError("approved fold manifest must contain exactly five outer folds")
    for fold_id, fold in payload.items():
        if not isinstance(fold, dict):
            raise ValueError(f"invalid fold manifest entry: {fold_id}")
        train = tuple(sorted(map(str, fold.get("train_participants", []))))
        valid = tuple(sorted(map(str, fold.get("valid_participants", []))))
        if not train or not valid or set(train) & set(valid):
            raise ValueError(f"invalid train/valid partition in {fold_id}")
    return payload


def _validate_outer_manifest(bundle: InputBundle, fold_manifest: dict[str, Any]) -> tuple[str, ...]:
    participants = set(bundle.participants)
    valid_union: set[str] = set()
    valid_counts = {p:0 for p in participants}
    for fold_id, fold in fold_manifest.items():
        train = set(map(str, fold["train_participants"]))
        valid = set(map(str, fold["valid_participants"]))
        if train | valid != participants or train & valid:
            raise ValueError(f"fold {fold_id} does not partition the input participants")
        valid_union.update(valid)
        for p in valid: valid_counts[p] += 1
    if valid_union != participants or any(n != 1 for n in valid_counts.values()):
        raise ValueError("each participant must be outer-valid exactly once")
    if len(participants) != 41:
        raise ValueError(f"A1 requires 41 participants, found {len(participants)}")
    return tuple(sorted(participants))


def _model_inventory(root: Path, config: A1Config) -> dict[str, object]:
    path = root / config.paths["models_manifest"]
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError("models manifest must be a list")
    rows = [row for row in payload if isinstance(row, dict) and row.get("variant") == "A"]
    if len(rows) != 65:
        raise ValueError(f"expected 65 A model roles, found {len(rows)}")
    required = {
        "fit_participants",
        "feature_schema",
        "label_schema",
        "fit_signature",
        "environment",
        "reference_row_hash",
    }
    inventory = []
    for row in rows:
        missing = sorted(required - set(row))
        inventory.append({
            "path": str(row.get("path", "")),
            "declared_sha256": str(row.get("sha256", "")),
            "loadable": bool(row.get("loadable", False)),
            "reuse_eligible": False,
            "reason": "cold start: D3 label signature and original fit environment not independently proven",
        })
    return {
        "manifest_path": str(path),
        "model_role_count": len(rows),
        "reusable_role_count": sum(bool(item["reuse_eligible"]) for item in inventory),
        "cold_start_required_role_count": sum(not bool(item["reuse_eligible"]) for item in inventory),
        "entries": inventory,
    }


def _role_dict(role: object) -> dict[str, object]:
    return {key: list(value) if isinstance(value, tuple) else value for key, value in asdict(role).items()}


def _code_identity(root: Path, config_path: Path) -> dict[str, str]:
    package = root / "src" / "eating_event"
    files = sorted(package.rglob("*.py")) + [root / "scripts" / "run_a1_feasibility.py", config_path]
    return {str(path.relative_to(root)): _sha256_file(path) for path in files if path.is_file()}


def _write_audit_outputs(
    run_dir: Path,
    *,
    config_path: Path,
    config: A1Config,
    bundle: InputBundle,
    fold_manifest: dict[str, Any],
    roles: Sequence[object],
    inventory: dict[str, object],
    resources: dict[str, int],
    root: Path,
) -> dict[str, object]:
    if not run_dir.is_dir():
        raise ValueError("supervisor run directory missing")
    limits = BudgetLimits(
        max_candidate_fits=105,
        max_verifier_fits=25,
        total_wall_seconds=21600,
        audit_wall_seconds=1800,
        fit_wall_seconds=7200,
        max_rss_bytes=resources["max_rss_bytes"],
        max_disk_bytes=2 * 1024**3,
        max_threads=4,
    )
    ensure_disk_budget(run_dir, limits)
    BudgetLedger(run_dir / "fit-ledger.jsonl", limits)
    _write_json(run_dir / "folds.json", fold_manifest)
    _write_json(run_dir / "role-graph.json", [_role_dict(role) for role in roles])
    _write_json(run_dir / "reuse-inventory.json", inventory)
    _write_json(run_dir / "cache-record-identity-audit.json", list(bundle.identity_audit))
    _write_json(run_dir / "label-sidecar.json", list(bundle.label_changes))
    code_identity = _code_identity(root, config_path)
    input_audit = {
        "status": "READY",
        "fit_count": 0,
        "predict_count": 0,
        "participant_count": len(bundle.participants),
        "canonical_event_count": sum(len(values) for values in bundle.truths.values()),
        "source_hashes": dict(bundle.source_hashes),
        "code_identity": code_identity,
        "resources": resources,
        "limits": asdict(limits),
        "role_counts": {
            "candidate": sum(role.kind == "candidate" for role in roles),
            "verifier": sum(role.kind == "verifier" for role in roles),
        },
        "raw_sensor_io": False,
        "test_truth_io": False,
        "external_data_io": False,
        "source_segment_id": None,
        "boundary_kind": "observed_window_support_component_v1",
    }
    _write_json(run_dir / "input-audit.json", input_audit)
    _write_json(
        run_dir / "checksums.json",
        {
            "config_sha256": _sha256_file(config_path),
            "code_identity": code_identity,
            "source_hashes": dict(bundle.source_hashes),
        },
    )
    _write_json(
        run_dir / "run-manifest.json",
        {
            "run_schema": "a1_run_manifest_v1",
            "config_path": str(config_path),
            "config_sha256": _sha256_file(config_path),
            "input_audit_sha256": _sha256_file(run_dir / "input-audit.json"),
            "code_identity": code_identity,
            "environment": environment_identity(),
            "artifact_hashes": {p.name: _sha256_file(p) for p in run_dir.glob("*.json") if p.name in {"input-audit.json","folds.json","role-graph.json","limits.json","cache-record-identity-audit.json","label-sidecar.json"}},
            "status": "AUDIT_READY",
        },
    )
    return input_audit


def _audit_work(config_path: Path, run_dir: Path, *, root: Path | None = None) -> dict[str, object]:
    resources = _load_json(run_dir / "startup-resources.json")
    config_path = config_path.expanduser().resolve()
    config = load_config(config_path)
    base = _root_for(config_path, root)
    verify_inputs(base, config)
    bundle = load_inputs(base, config)
    verify_bundle(bundle)
    fold_manifest = _read_fold_manifest(base, config)
    participants = _validate_outer_manifest(bundle, fold_manifest)
    roles = build_role_graph(participants, outer_folds=5, inner_folds=4, subinner_folds=4, seed=config.seed)
    validate_role_graph(roles, participants)
    for role in roles:
        if role.kind == "candidate" and role.inner_fold is None:
            expected = fold_manifest[role.outer_fold]
            if set(role.fit_participants) != set(expected["train_participants"]) or set(role.scored_participants) != set(expected["valid_participants"]):
                raise ValueError("generated role graph differs from approved folds")
    inventory = _model_inventory(base, config)
    return _write_audit_outputs(
        run_dir,
        config_path=config_path,
        config=config,
        bundle=bundle,
        fold_manifest=fold_manifest,
        roles=roles,
        inventory=inventory,
        resources=resources,
        root=base,
    )


def _execute_work(config_path: Path, run_dir: Path, *, root: Path | None = None) -> dict[str, object]:
    config_path = config_path.expanduser().resolve()
    run_dir = run_dir.expanduser().resolve()
    audit_path = run_dir / "input-audit.json"
    manifest_path = run_dir / "run-manifest.json"
    if not audit_path.is_file() or not manifest_path.is_file():
        raise ValueError("run requires a matching completed audit")
    audit = _load_json(audit_path)
    if not isinstance(audit, dict) or audit.get("status") != "READY":
        raise ValueError("run requires READY audit")
    config = load_config(config_path)
    base = _root_for(config_path, root)
    verify_inputs(base, config)
    bundle = load_inputs(base, config)
    verify_bundle(bundle)
    if audit.get("source_hashes") != dict(bundle.source_hashes):
        raise ValueError("input hashes changed after audit")
    if audit.get("code_identity") != _code_identity(base, config_path):
        raise ValueError("code identity changed after audit")
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("config_sha256") != _sha256_file(config_path):
        raise ValueError("config changed after audit")
    if manifest.get("input_audit_sha256") != _sha256_file(audit_path):
        raise ValueError("audit digest mismatch")
    if manifest.get("environment") != environment_identity():
        raise ValueError("environment changed after audit")
    for name, expected in manifest["artifact_hashes"].items():
        if _sha256_file(run_dir/name) != expected:
            raise ValueError(f"audit artifact changed: {name}")
    from eating_event.a1.pipeline import execute_full_pipeline

    result = execute_full_pipeline(bundle, config, run_dir)
    _write_json(run_dir / "metrics.json", result)
    _write_json(run_dir / "final-checksums.json", {str(p.relative_to(run_dir)): _sha256_file(p) for p in run_dir.rglob("*") if p.is_file() and p.name not in {"worker.log", "run-status.json", "resource-segments.jsonl", "worker-response.json", "final-checksums.json"}})
    return result


def environment_identity():
    import importlib.metadata
    return {"python": sys.version, "platform": platform.platform(),
            "libraries": {name:importlib.metadata.version(name) for name in ("numpy","scikit-learn","scipy","psutil")}}


def audit_run(config_path, run_dir, *, root=None):
    run_dir=Path(run_dir).resolve()
    if run_dir.exists():
        raise ValueError("run directory already exists")
    resources=measure_startup_resources()
    return launch("audit",config_path,run_dir,_root_for(Path(config_path),root),resources)


def execute_run(config_path, run_dir, *, root=None):
    run_dir=Path(run_dir).resolve()
    state=run_dir/"run-status.json"
    if state.exists() and _load_json(state).get("status") != "AUDIT_READY":
        raise ValueError("terminal run state; explicit recovery required")
    if not (run_dir/"input-audit.json").is_file():
        raise ValueError("run requires matching ready audit")
    return launch("run",config_path,run_dir,_root_for(Path(config_path),root),{})


def main(argv=None):
    args=parse_args(argv)
    try:
        function=audit_run if args.mode=="audit" else execute_run
        result=function(args.config,args.run_dir,root=args.root)
        print(json.dumps({"status":result["status"],"reason":result.get("reason")}))
        return 0 if result["status"] in {"READY","COMPLETE"} else 2
    except (ValueError,ResourceNotReady,OSError) as exc:
        print(json.dumps({"status":"NOT_READY","reason":str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
