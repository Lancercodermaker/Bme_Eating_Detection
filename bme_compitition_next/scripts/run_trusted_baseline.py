"""Materialize the immutable preflight M0 trusted-baseline sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from eating_event.candidates import split_participants
from eating_event.config import load_config


BASELINE_ID = "m0-q50-groupnorm"
BASELINE_F1 = 0.17284
BASELINE_SEED = 20260910
BASELINE_VALID_FRACTION = 0.20
BASELINE_MATCHING = "strict_iou_gt_0.25_one_to_one"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def build_trusted_baseline_artifact(
    *,
    output_dir: str | Path,
    audited_target_participants: Iterable[str],
    baseline_id: str,
    split_seed: int,
    valid_fraction: float,
    expected_event_f1: float,
    config_hash: str | None = None,
    audited_manifest_hash: str | None = None,
) -> dict[str, object]:
    """Write and return the fixed target-only M0 contract."""

    if baseline_id != BASELINE_ID:
        raise ValueError(f"baseline_id must be {BASELINE_ID}")
    if split_seed != BASELINE_SEED:
        raise ValueError(f"split_seed must be {BASELINE_SEED}")
    if valid_fraction != BASELINE_VALID_FRACTION:
        raise ValueError("valid_fraction must be 0.20")
    if abs(float(expected_event_f1) - BASELINE_F1) > 1e-5:
        raise ValueError("expected_event_f1 must equal the trusted M0 value")

    participants = tuple(sorted({str(value) for value in audited_target_participants if str(value)}))
    if len(participants) < 2:
        raise ValueError("trusted baseline needs at least two target participants")
    train_participants, valid_participants = split_participants(
        participants,
        valid_fraction=BASELINE_VALID_FRACTION,
        seed=BASELINE_SEED,
    )
    participant_order_sha256 = _sha256_bytes(_canonical_bytes(list(participants)))
    split_core: dict[str, object] = {
        "schema_version": "participant_split_v1",
        "strategy": "participant_frozen",
        "seed": BASELINE_SEED,
        "valid_fraction": BASELINE_VALID_FRACTION,
        "participant_ids": list(participants),
        "train_participant_ids": list(train_participants),
        "valid_participant_ids": list(valid_participants),
        "participant_order_sha256": participant_order_sha256,
    }
    split_core["split_sha256"] = _sha256_bytes(_canonical_bytes(split_core))
    output = Path(output_dir).expanduser().resolve()
    split_path = output / "split-manifest.json"
    _write_json(split_path, split_core)
    split_file_hash = _sha256_file(split_path)

    metric = {
        "name": "event_f1",
        "value": BASELINE_F1,
        "matching": BASELINE_MATCHING,
        "source_document": "docs/preflight-2026-09-10.md",
        "source_locator": "Baseline / M0 q50 + GroupNorm",
    }
    split_summary = {
        "strategy": "participant_frozen",
        "seed": BASELINE_SEED,
        "valid_fraction": BASELINE_VALID_FRACTION,
        "participant_order": "sorted_unique_target_train",
        "manifest": "split-manifest.json",
    }
    metrics: dict[str, object] = {
        "schema_version": "trusted_baseline_v1",
        "baseline_id": BASELINE_ID,
        "data_scope": "target_only_train",
        "split_manifest": "split-manifest.json",
        "split_manifest_sha256": split_file_hash,
        "split": split_summary,
        "metric": metric,
    }
    metrics_path = output / "metrics.json"
    _write_json(metrics_path, metrics)
    manifest = {
        "schema_version": "trusted_baseline_manifest_v1",
        "baseline_id": BASELINE_ID,
        "config_hash": config_hash or _sha256_bytes(_canonical_bytes({"baseline_id": BASELINE_ID})),
        "audited_target_manifest_hash": audited_manifest_hash or _sha256_bytes(_canonical_bytes(list(participants))),
        "split_manifest_sha256": split_file_hash,
        "metrics_sha256": _sha256_file(metrics_path),
        "data_scope": "target_only_train",
        "test_truth_references": [],
        "external_data_references": [],
        "result": "pass",
    }
    _write_json(output / "manifest.json", manifest)
    return metrics


def _participants_from_audit(audit_path: Path) -> tuple[str, ...]:
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    records = payload.get("manifest_records")
    if not isinstance(records, list):
        raise ValueError("audit artifact lacks manifest_records")
    participants = {
        str(record["participant_id"])
        for record in records
        if isinstance(record, dict)
        and record.get("status") == "processed"
        and str(record.get("participant_id", "")).lower() != "test"
    }
    if not participants:
        raise ValueError("audit artifact contains no eligible target participants")
    return tuple(sorted(participants))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--baseline-id", required=True)
    parser.add_argument("--split-seed", type=int, required=True)
    parser.add_argument("--valid-fraction", type=float, required=True)
    parser.add_argument("--expected-event-f1", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    audit_path = args.audit.expanduser().resolve()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    if args.strict and audit_payload.get("diagnostic_only") is not True:
        raise SystemExit("strict trusted baseline requires a diagnostic audit artifact")
    artifact = build_trusted_baseline_artifact(
        output_dir=args.output_dir,
        audited_target_participants=_participants_from_audit(audit_path),
        baseline_id=args.baseline_id,
        split_seed=args.split_seed,
        valid_fraction=args.valid_fraction,
        expected_event_f1=args.expected_event_f1,
        config_hash=_sha256_file(args.config.expanduser().resolve()),
        audited_manifest_hash=_sha256_file(audit_path),
    )
    manifest_path = args.output_dir.expanduser().resolve() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.strict and manifest.get("result") != "pass":
        raise SystemExit("trusted baseline manifest failed")
    print(json.dumps({"result": manifest["result"], "metric": artifact["metric"]}, sort_keys=True))


if __name__ == "__main__":
    main()
