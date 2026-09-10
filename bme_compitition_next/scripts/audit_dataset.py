"""Audit selected raw TSV files without copying or caching raw signals."""

from __future__ import annotations

import argparse
from pathlib import Path

from eating_event.audit import audit_tsv_files, write_audit_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path, help="explicit TSV files to audit")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audits = audit_tsv_files(args.paths, max_rows=args.max_rows)
    write_audit_json(audits, args.output)
    for audit in audits:
        print(
            f"{audit.path}: rows={audit.total_rows} malformed={audit.malformed_rows} "
            f"truncated={audit.truncated}"
        )


if __name__ == "__main__":
    main()

