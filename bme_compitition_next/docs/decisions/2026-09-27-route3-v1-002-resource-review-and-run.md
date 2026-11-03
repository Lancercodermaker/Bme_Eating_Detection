# Route 3 v1-002 resource re-review and run result

Date: 2026-09-27  
Workspace: `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`

## Goal

Re-review the frozen Route 3 matching-aware target experiment after terminal resource failure in `route3-matching-aware-v1-001`. If the same resource gates pass, start a fresh, separately namespaced attempt using frozen A2-004 inputs and the same limits.

## Success metrics

The pre-fit audit must reach `AUDIT_READY`; a valid run must pass exact fit-provenance checks, fixed call accounting, and the existing numeric/stage gates. This review adds no performance threshold. The current run did not produce an accepted Route 3 result: the persisted status is `INVALID`, and all four existing A2 numeric/stage minimum and ideal booleans are false in the provisional metrics.

## Constraints

The v1-002 limits equal v1-001: 900 seconds cumulative active wall, 600 seconds verifier-fit wall, RSS ceiling `min(3,221,225,472 B, 50% of startup available memory)`, 512 MiB study disk, 2 threads, 25 verifier fits, 25 verifier scores, zero candidate fits, and zero candidate predicts. No cap was widened. No raw sensor, original metadata CSV, official test, or external data was read.

## Prior art

A2-004 is frozen and complete. v1-001 ended `INCOMPLETE_RESOURCE` before any fit because its startup-derived RSS ceiling did not leave the required 2x margin. The v1-001 terminal record remains unchanged. This attempt used the new `route3-matching-aware-v1-002` namespace.

## Baseline

At review time, available memory was `5,199,306,752 B`, giving a startup-derived RSS ceiling of `2,599,653,376 B`. The A2-004 audit RSS comparator was `799,109,120 B`. For 72,112 candidate rows and 26 float32 features, the conservative projected Route 3 RSS was `860,332,208 B`; its 2x estimate was `1,720,664,416 B`, leaving `878,988,960 B` under the review-time ceiling. A conservative disk estimate including a 1 MiB target audit was `233,418,752 B`; 2x was `466,837,504 B`, below the unchanged 512 MiB limit.

## Candidate approaches

Selected: one fresh v1-002 audit and, only after `AUDIT_READY`, one run under the unchanged limits. Reusing v1-001 or retrying a terminal namespace was excluded. v1-002 itself is terminal and has no retry.

## Critical assumptions

- The frozen role graph contains 105 candidate roles and 72,112 candidate rows across roles; the five outer roles contain 4,183 rows.
- The current environment and completed A2-004 config/audit-ready identities match the frozen Route 3 config.
- The synthetic size estimate is a preflight only; the Route 3 audit independently creates the role-safe target audit and checks measured RSS/disk margins before issuing `AUDIT_READY`.

Evidence: v1-002 config SHA-256 `fee3cb00c6c131fcf9dd40796019802aa9dc62d4deb1f33f1b6a4e9ed3e242f2`; environment and A2-004 identities validated; v1-001/v1-002 resource limits and verifier/target settings compare equal.

## Risks

Memory availability can change between review and invocation. More importantly, run-time provenance validation may reject an otherwise completed fit graph if its record schema does not satisfy the reviewed contract. That implementation risk occurred here.

## Validation experiments

1. Corrected the v1-002 config's trailing literal `\n`, regenerated its SHA-256 sidecar, then loaded and validated the config, environment, A2-004 identity, and fresh namespace. No audit was launched until these checks passed.
2. Resource review passed. Route 3 audit returned `AUDIT_READY` with 105 candidate roles, 25 verifier roles, 234 eligible GT, 41 participants, 0 fit calls, peak process-tree RSS `790,605,824 B`, and study disk `142,383 B`.
3. One v1-002 run executed 25 successful verifier fits, 25 verifier score calls, 65 decodes (60 inner threshold decodes and 5 outer decodes), and 5 outer evaluations. Candidate fits/predicts remained 0/0. Peak process-tree RSS was `796,614,656 B` against a run ceiling of `2,602,833,920 B`; study disk was `7,438,205 B`; no resource failure was recorded.
4. The run ended `INVALID` at `Route 3 actual fit inputs differ from pre-fit audit for verifier/outer-0/inner-0`. Comparing persisted target audit and provisional metrics shows all 25 actual fit records lack `candidate_count`. The exact candidate-key, feature-matrix, and label-join hashes, positive candidate/participant counts, positive canonical-GT counts, verifier role IDs, and training-role compositions otherwise match the audit. `src/eating_event/route3/runner.py::_validate_fit_provenance` requires `candidate_count`, while `src/eating_event/a2/execution.py::_fit` does not put that field in the actual provenance record. This is an implementation/schema mismatch, not an RSS or disk failure.

## Kill criteria

The audit would stop before fitting if the actual 2x RSS/disk margins failed. Any stale identity, data mismatch, or fit-provenance mismatch terminates the attempt. The v1-002 ledger records terminal `INVALID`; do not rerun this namespace. A fresh experiment would require fixing and reviewing the provenance contract and creating a separately authorized namespace.

## Recommendation

SPIKE FIRST

The resource route passed, but the implementation's fit-provenance contract did not. Correct the missing candidate-count provenance field (or revise the validator using an equally strong recorded count), verify the contract against the saved audit/metrics artifacts, then obtain a fresh review before another experiment. The v1-002 provisional scores are not an accepted Route 3 result.

## Confidence

High that memory was not the cause: both invocations stayed well below their measured RSS ceilings and the ledger has no resource failure. High that the INVALID status came from a missing provenance field: all 25 persisted rows were compared and only `candidate_count` was absent among the validator's required fields. The metric outcome remains provisional because the workflow deliberately rejected the run before final Route 3 acceptance.

## Evidence files

- `configs/route3-matching-aware-v1-002.json` and `.sha256`
- `artifacts/route3-matching-aware-v1-002-budget.jsonl`
- `artifacts/route3-matching-aware-v1-002/run-status.json`
- `artifacts/route3-matching-aware-v1-002/resource-summary.json`
- `artifacts/route3-matching-aware-v1-002/target-audit.json`
- `artifacts/route3-matching-aware-v1-002/metrics.json`
- `artifacts/route3-matching-aware-v1-002/synthetic-size-profile.json`
