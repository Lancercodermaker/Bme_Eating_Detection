"""Only supported entry point for the one frozen A2 development validation."""

from __future__ import annotations

import os
import sys
from pathlib import Path


for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[_variable] = "4"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"audit", "run"}:
        print("usage: python scripts/run_a2_context_verifier.py {audit|run}", file=sys.stderr)
        return 2
    workspace = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != workspace:
        print("A2 command must run from the authorized existing worktree", file=sys.stderr)
        return 2
    from eating_event.a2.contracts import load_config
    from eating_event.a2.control import launch

    config, config_sha256 = load_config(workspace)
    notes = """# A2 study notes

## Pre-audit verification

- `python -m pytest tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_pipeline.py tests/test_a2_control.py -q` — 50 passed.
- `python -m pytest tests/test_a1_contracts.py tests/test_a1_events.py tests/test_a1_metrics.py -q` — 15 passed.
- Environment: Python 3.10.11, NumPy 2.2.6, SciPy 1.15.3, scikit-learn 1.7.2, psutil 7.2.2.
- Synthetic pipeline uses a fake verifier backend; no candidate estimator fit/predict and no A1 model pickle deserialization.

The study clock starts at this first real-source audit invocation. Candidate-model fit/predict budget: 0/0. No outer result may change the frozen study definition.
"""
    result = launch(args[0], workspace, config_digest=config_sha256, study_notes=notes)
    print(result)
    return 0 if result.get("status") in {"AUDIT_READY", "COMPLETE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
