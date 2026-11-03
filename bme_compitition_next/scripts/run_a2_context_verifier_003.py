"""Fixed entry point for the single A2-003 resource-recovery validation."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


STUDY_ID = "a2-context-verifier-v1-003"

for _variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[_variable] = "4"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"preflight", "audit", "run"}:
        print("usage: python scripts/run_a2_context_verifier_003.py {preflight|audit|run}", file=sys.stderr)
        return 2
    workspace = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve() != workspace:
        print("A2-003 command must run from the authorized existing worktree", file=sys.stderr)
        return 2

    from eating_event.a2.audit import current_a2_code_identity
    from eating_event.a2.contracts import canonical_json, load_config
    from eating_event.a2.control import launch

    config, config_sha256 = load_config(workspace, study_id=STUDY_ID)
    code_identity = current_a2_code_identity(workspace)
    code_identity_sha256 = hashlib.sha256(canonical_json(code_identity)).hexdigest()
    notes = f"""# A2-003 study notes

## Fixed identity

- Study: `{STUDY_ID}`
- Config SHA-256: `{config_sha256}`
- Canonical A2 code-identity SHA-256: `{code_identity_sha256}` ({len(code_identity)} files; includes this 003 runner and the 003 synthetic tests)
- A1 source checksum SHA-256: `{config['source_checksum_sha256']}`
- Inherited active wall: `{config['predecessor']['active_wall_seconds']}` seconds; inherited verifier fit wall and attempts: 0 / 0.
- RSS ceiling rule: `min(4 GiB, floor(0.60 * startup available bytes))`, with startup available memory at least 5 GiB.
- Candidate fit and predict counts are fixed at zero; verifier fit attempts are capped at 25 for the full family.

## Evidence limits

- This run uses only the fixed A1-005 derived artifacts and approved A2 predecessors.
- No independent participant-level confirmation or on-site video exists. Long false positives are interpreted under the approved annotation contract only.
- A1 remains CLOSED; Formal G1=FAIL; full training=BLOCKED; production=UNCHANGED.
"""
    result = launch(args[0], workspace, config_digest=config_sha256, study_notes=notes, study_id=STUDY_ID)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    if args[0] == "preflight" and result.get("status") in {
        "PREFLIGHT_READY",
        "NOT_STARTED_INSUFFICIENT_HEADROOM",
        "NOT_STARTED_GATE_FAILED",
    }:
        return 0
    return 0 if result.get("status") in {"AUDIT_READY", "COMPLETE", "RUN_NOT_STARTED_INSUFFICIENT_HEADROOM"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
