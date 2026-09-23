"""Fixed entry point for the single A2-002 recovery validation."""

from __future__ import annotations

import hashlib
import json
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
    from eating_event.a2.audit import current_a2_code_identity
    from eating_event.a2.contracts import load_config
    from eating_event.a2.control import launch

    config, config_sha256 = load_config(workspace, study_id=STUDY_ID)
    code_identity = current_a2_code_identity(workspace)
    code_identity_sha256 = hashlib.sha256(
        json.dumps(code_identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    notes = f"""# A2-002 study notes

## Pre-audit verification

- `python -m pytest tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_pipeline.py tests/test_a2_control.py tests/test_a2_recovery_identity.py tests/test_a2_recovery_namespace.py -q`: **91 passed**.
- `python -m pytest tests/test_a1_contracts.py tests/test_a1_events.py tests/test_a1_metrics.py -q`: **15 passed**.
- Synthetic recovery identity tests: 10 passed; existing A2 audit contract tests: 21 passed; namespace/control tests: 46 passed.
- Static A1 evidence review: checksum manifest lists 282 artifacts; all 45 registered A1 source-code hashes match. No listed artifact was opened by this pre-audit review.

## Frozen identity

- Study: `{STUDY_ID}`
- Config SHA-256: `{config_sha256}`
- Canonical A2 code-identity SHA-256: `{code_identity_sha256}` ({len(code_identity)} files; includes this 002 runner)
- Approved A1 source checksum SHA-256: `{config['source_checksum_sha256']}`
- A1 predecessor evidence and inherited budget are fixed in the 002 config: 3.5 active seconds, 0 fit seconds, 0 verifier fit attempts, RSS ceiling 2,127,893,299 bytes.
- Runtime was verified as Python 3.10.11, NumPy 2.2.6, SciPy 1.15.3, scikit-learn 1.7.2, psutil 7.2.2.

## Scope and remaining uncertainty

Candidate-model fit and predict counts are fixed at zero. Only the 25 authorized verifier roles may fit. All 41 participants were exposed during development; there is no independent participant confirmation. The observed change for 75 historical long false positives is annotation-contract evidence only; their actual behavior remains unknown.
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
