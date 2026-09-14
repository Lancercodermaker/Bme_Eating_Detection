"""Run a bounded, diagnostic-only manifest and raw-file audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from eating_event.audit import audit_tsv_files, write_audit_json, write_dataset_audit_report
from eating_event.config import load_config
from eating_event.data.manifest import discover_raw_files_with_audit
from eating_event.data.raw import RawFileFormatError, read_imu_tsv_with_audit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _diagnostic_config_audit(
    config_path: Path,
    output: Path,
    *,
    limit_files: int | None,
    run_id: str,
    diagnostic_only: bool,
    resource_dry_run: bool,
) -> int:
    started_at = _now()
    started_clock = time.perf_counter()
    try:
        config = load_config(config_path)
        if limit_files is not None and limit_files <= 0:
            raise ValueError("limit-files must be positive")
        if not diagnostic_only and limit_files is not None:
            raise ValueError("file limits are diagnostic-only")

        if resource_dry_run:
            payload = {
                "schema_version": "dataset_audit_v1",
                "run_id": run_id,
                "diagnostic_only": diagnostic_only,
                "telemetry_scope": "diagnostic" if diagnostic_only else "formal",
                "status": "pass",
                "failure_class": None,
                "started_at": started_at,
                "ended_at": _now(),
                "resource_dry_run": True,
                "resource_limits": {
                    "host_memory_fraction": config.host_memory_fraction,
                    "gpu_memory_limit_gb": config.gpu_memory_limit_gb,
                    "audit_timeout_seconds": config.audit_timeout_seconds,
                    "cache_timeout_seconds": config.cache_timeout_seconds,
                    "fit_timeout_seconds": config.fit_timeout_seconds,
                },
                "elapsed_seconds": time.perf_counter() - started_clock,
            }
            write_dataset_audit_report(payload, output)
            return 0

        records, manifest_audit = discover_raw_files_with_audit(config.raw_data_root)
        selected = records[:limit_files] if limit_files is not None else records
        raw_audits: list[dict[str, object]] = []
        malformed_rows = 0
        duplicate_count = 0
        dropped_timestamp_count = 0
        skipped_files = 0
        for record in selected:
            try:
                result = read_imu_tsv_with_audit(record.path, chunk_size=config.raw_chunk_size)
            except RawFileFormatError as exc:
                skipped_files += 1
                raw_audits.append(
                    {
                        "path": str(record.path),
                        "status": "skipped_malformed",
                        "reason": str(exc),
                        "participant_id": record.participant_id,
                        "session_id": record.session_folder,
                    }
                )
                continue
            audit = result.audit
            malformed_rows += audit.malformed_rows
            duplicate_count += audit.duplicate_count
            dropped_timestamp_count += audit.dropped_timestamp_count
            raw_audits.append(
                {
                    "path": audit.path,
                    "status": audit.status,
                    "reason": audit.reason,
                    "participant_id": record.participant_id,
                    "session_id": record.session_folder,
                    "total_rows": audit.total_rows,
                    "valid_rows": audit.valid_rows,
                    "malformed_rows": audit.malformed_rows,
                    "malformed_row_details": list(audit.malformed_row_details),
                    "duplicate_count": audit.duplicate_count,
                    "dropped_timestamp_count": audit.dropped_timestamp_count,
                }
            )
        status_counts = dict(manifest_audit.status_counts)
        status_counts["skipped_malformed"] = status_counts.get("skipped_malformed", 0) + skipped_files
        payload = {
            "schema_version": "dataset_audit_v1",
            "run_id": run_id,
            "diagnostic_only": diagnostic_only,
            "telemetry_scope": "diagnostic" if diagnostic_only else "formal",
            "status": "pass" if not skipped_files else "pass_with_skips",
            "failure_class": "DATA/PIPELINE" if skipped_files else None,
            "started_at": started_at,
            "ended_at": _now(),
            "source_root": str(config.raw_data_root),
            "discovered_file_count": len(records),
            "audited_file_count": len(selected),
            "status_counts": status_counts,
            "invalid_index_rows": manifest_audit.invalid_index_rows,
            "malformed_rows": malformed_rows,
            "duplicate_count": duplicate_count,
            "dropped_timestamp_count": dropped_timestamp_count,
            "manifest_records": manifest_audit.records,
            "files": raw_audits,
            "elapsed_seconds": time.perf_counter() - started_clock,
        }
        write_dataset_audit_report(payload, output)
        return 0
    except (OSError, ValueError, RawFileFormatError) as exc:
        payload = {
            "schema_version": "dataset_audit_v1",
            "run_id": run_id,
            "diagnostic_only": diagnostic_only,
            "telemetry_scope": "diagnostic" if diagnostic_only else "formal",
            "status": "fail",
            "failure_class": "DATA/PIPELINE",
            "reason": str(exc),
            "started_at": started_at,
            "ended_at": _now(),
            "elapsed_seconds": time.perf_counter() - started_clock,
        }
        write_dataset_audit_report(payload, output)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, help="explicit TSV files to audit")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default="dataset-audit")
    parser.add_argument("--diagnostic-only", action="store_true")
    parser.add_argument("--resource-dry-run", action="store_true")
    args = parser.parse_args()

    if args.config is not None:
        raise SystemExit(
            _diagnostic_config_audit(
                args.config,
                args.output,
                limit_files=args.limit_files,
                run_id=args.run_id,
                diagnostic_only=args.diagnostic_only,
                resource_dry_run=args.resource_dry_run,
            )
        )
    if not args.paths:
        parser.error("provide --config or at least one TSV path")
    audits = audit_tsv_files(args.paths, max_rows=args.max_rows)
    write_audit_json(audits, args.output)
    for audit in audits:
        print(
            f"{audit.path}: rows={audit.total_rows} malformed={audit.malformed_rows} "
            f"truncated={audit.truncated}"
        )


if __name__ == "__main__":
    main()
