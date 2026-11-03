"""Fixed entry point for the single Route 3 matching-aware validation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[_variable] = "2"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in {1, 2} or args[0] not in {"audit", "run"}:
        print("usage: py -3.10 scripts/run_route3_matching_aware.py {audit|run} [study-id]", file=sys.stderr)
        return 2
    study_id = args[1] if len(args) == 2 else "route3-matching-aware-v1-001"
    if study_id not in {"route3-matching-aware-v1-001", "route3-matching-aware-v1-002", "route3-matching-aware-v1-003"}:
        print("unknown Route 3 study id", file=sys.stderr)
        return 2
    workspace = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != workspace:
        print("Route 3 command must run from the authorized existing worktree", file=sys.stderr)
        return 2
    sys.path.insert(0, str(workspace / "src"))

    from threadpoolctl import threadpool_limits

    from eating_event.route3.runner import run_audit, run_experiment

    with threadpool_limits(limits=2):
        result = (
            run_audit(workspace, study_id=study_id)
            if args[0] == "audit"
            else run_experiment(workspace, study_id=study_id)
        )
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    expected_status = "AUDIT_READY" if args[0] == "audit" else "COMPLETE"
    return 0 if result.get("status") == expected_status else 2


if __name__ == "__main__":
    raise SystemExit(main())
