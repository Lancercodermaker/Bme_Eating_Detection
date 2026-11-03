"""Materialize the immutable preflight M0 trusted-baseline sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

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
    eligibility_contract: Mapping[str, object] | None = None,
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
    if eligibility_contract is not None:
        metrics["eligibility"] = {
            key: eligibility_contract[key]
            for key in (
                "schema_version",
                "manifest_sha256",
                "denominator_sha256",
                "event_denominator_sha256",
                "source_audit_sha256",
                "eligible_participant_count",
                "effective_valid_event_count",
            )
            if key in eligibility_contract
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
    if eligibility_contract is not None:
        manifest["eligibility"] = dict(metrics["eligibility"])
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


def _participants_from_eligibility(eligibility_path: Path) -> tuple[str, ...]:
    payload = json.loads(eligibility_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") not in {
        "participant_eligibility_v1",
        "participant_eligibility_v2",
    }:
        raise ValueError("eligibility artifact has an unsupported schema")
    participant_rows = payload.get("participant_eligibility")
    if not isinstance(participant_rows, Mapping):
        raise ValueError("eligibility artifact lacks participant_eligibility")
    participants = tuple(
        sorted(
            str(participant)
            for participant, details in participant_rows.items()
            if isinstance(details, Mapping) and details.get("participant_status") == "eligible"
        )
    )
    if not participants:
        raise ValueError("eligibility artifact contains no eligible participants")
    return participants


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--eligibility", type=Path, default=None)
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
    eligibility_contract = None
    audited_participants = _participants_from_audit(audit_path)
    if args.eligibility is not None:
        eligibility_path = args.eligibility.expanduser().resolve()
        eligibility_payload = json.loads(eligibility_path.read_text(encoding="utf-8"))
        if not isinstance(eligibility_payload, Mapping):
            raise SystemExit("eligibility artifact must be a JSON object")
        eligible_participants = _participants_from_eligibility(eligibility_path)
        if eligible_participants != audited_participants:
            raise SystemExit("eligibility participant set does not match processed audit participant set")
        eligibility_contract = dict(eligibility_payload)
        eligibility_contract["artifact_sha256"] = _sha256_file(eligibility_path)
    artifact = build_trusted_baseline_artifact(
        output_dir=args.output_dir,
        audited_target_participants=audited_participants,
        baseline_id=args.baseline_id,
        split_seed=args.split_seed,
        valid_fraction=args.valid_fraction,
        expected_event_f1=args.expected_event_f1,
        config_hash=_sha256_file(args.config.expanduser().resolve()),
        audited_manifest_hash=_sha256_file(audit_path),
        eligibility_contract=eligibility_contract,
    )
    manifest_path = args.output_dir.expanduser().resolve() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.strict and manifest.get("result") != "pass":
        raise SystemExit("trusted baseline manifest failed")
    print(json.dumps({"result": manifest["result"], "metric": artifact["metric"]}, sort_keys=True))


if __name__ == "__main__":
    main()
