"""Fixed entry point for the single A2-002 recovery validation."""

from __future__ import annotations

import os
import sys
from pathlib import Path


STUDY_ID = "a2-context-verifier-v1-002"


for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[_variable] = "4"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"audit", "run"}:
        print("usage: python scripts/run_a2_context_verifier_002.py {audit|run}", file=sys.stderr)
        return 2
    workspace = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != workspace:
        print("A2-002 command must run from the authorized existing worktree", file=sys.stderr)
        return 2
    from eating_event.a2.contracts import load_config
    from eating_event.a2.control import launch

    config, config_sha256 = load_config(workspace, study_id=STUDY_ID)
    notes = """# A2-002 study notes

Pre-audit test commands and actual results, the frozen source/config identity, and the known remaining uncertainties are recorded here before the sole real-source audit. The predecessor resource use is fixed by the 002 config; no candidate-model fit or predict is allowed.
"""
    result = launch(
        args[0],
        workspace,
        config_digest=config_sha256,
        study_notes=notes,
        study_id=STUDY_ID,
    )
    print(result)
    return 0 if result.get("status") in {"AUDIT_READY", "COMPLETE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
