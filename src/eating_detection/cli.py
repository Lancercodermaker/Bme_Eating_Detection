import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import audit_sensor_files


def _sensor_files(train_dir: Path, limit_files: int | None) -> list[Path]:
    if train_dir.is_file():
        paths = [train_dir]
    else:
        paths = sorted(train_dir.rglob("*.txt"))
    return paths if limit_files is None else paths[:limit_files]


def _run_audit(args: argparse.Namespace) -> int:
    paths = _sensor_files(Path(args.train_dir), args.limit_files)
    report = audit_sensor_files(paths, max_rows=args.max_rows, chunksize=args.chunksize)
    report["index_dir"] = str(Path(args.index_dir))
    report["train_dir"] = str(Path(args.train_dir))
    report["resample_hz"] = args.resample_hz
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "audit_sample.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AUDIT_PASS files={report['files_read']} rows={report['rows_read']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eating-detection")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--index-dir", required=True)
    audit_parser.add_argument("--train-dir", required=True)
    audit_parser.add_argument("--output-dir", required=True)
    audit_parser.add_argument("--limit-files", type=int)
    audit_parser.add_argument("--max-rows", type=int)
    audit_parser.add_argument("--chunksize", type=int, default=50_000)
    audit_parser.add_argument("--resample-hz", type=int, default=25)
    audit_parser.set_defaults(handler=_run_audit)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
