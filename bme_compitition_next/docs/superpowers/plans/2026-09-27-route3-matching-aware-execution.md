# Route 3 Matching-Aware Supervision Execution Plan

> **Execution record (2026-09-27):** One authorized `audit` invocation ended `INCOMPLETE_RESOURCE` during synthetic RSS sizing. All 25 G3 prechecks returned successfully in memory, but the 2x RSS margin failed before `AUDIT_READY`; the ledger records zero fits. The `run` command was not started and this study namespace cannot be retried. See `artifacts/route3-matching-aware-v1-001/resource-preflight-failure.json`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one bounded local nested validation of one-to-one training targets on the frozen A2-004 candidate intervals and 26D features.

**Architecture:** Keep A2-004 closed and read its authenticated materialized corpus as immutable input. In a new `route3-matching-aware-v1-001` namespace, assign labels only to non-outer candidate roles using the existing participant-level strict-IoU deterministic matcher, then call the existing fixed A2 nested verifier/evaluator with the new labels. The outer roles stay label-free until final evaluation; the new run gets its own config, ledger, output directory, and tighter resource caps.

**Tech Stack:** Existing Python 3.10 / NumPy / scikit-learn HGB / psutil environment; existing A2-004 role graph and A1 event matcher; no candidate model call.

---

## Fixed experiment definition

- Input source: `artifacts/a2-context-verifier-v1-004`, config SHA-256 `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`, audit-ready SHA-256 `bf4e9a10a34e5f17b36d3632356cf8e50cdc1cdb60125fe1d78a9b4e4baabeb4`.
- Output namespace: `artifacts/route3-matching-aware-v1-001`; external ledger `artifacts/route3-matching-aware-v1-budget.jsonl`; exclusive lock `artifacts/route3-matching-aware-v1-budget.lock`.
- Target: for each non-outer candidate role, run the existing participant-level matcher on that role's saved candidate intervals and only that role's eligible GT. A candidate is positive iff the local strict `IoU > 0.25` greedy one-to-one assignment selects it. Every other candidate is negative. Outer candidate rows remain `label=None` during target construction.
- Matcher tie order: existing `evaluate_participants` contract, whose per-participant candidate order is `candidate_id`, truth order is `event_id`, possible edges sort by descending IoU then candidate and truth indices, and accepted pairs are one-to-one.
- Verifier: unchanged HGB family and A2-004 fit settings, seed `20260910`, positive weight `3.0`, `max_iter=100`; fixed thresholds `{0.10, 0.25, 0.50}`; unchanged A2-004 decoder, duration, fusion, participant roles, and local evaluator.
- Planned calls: 0 candidate fit/predict, 25 verifier fit attempts, 25 verifier score calls, 60 inner threshold decodes plus 5 outer decodes, and 5 outer evaluations. A failed fit consumes its attempt. No retry, threshold extension, candidate change, or outer-specific repair.
- Independent Route 3 limits: 900 seconds total active wall across audit and run, 600 seconds cumulative verifier-fit wall, at most 2 threads, 512 MiB new-study disk, and process-tree RSS capped at `min(3 GiB, 50% of startup available memory)`. These are new Route 3 limits; A2-004 limits are not inherited. If any limit cannot be measured or is exceeded, stop `INCOMPLETE_RESOURCE`.
- Before the first fit, audit and persist role-specific positive-candidate counts, positive-participant counts, positive-GT counts, class presence, row-key digests, and target-label digests for all 25 fit compositions. Any G3 failure stops `DATA_INSUFFICIENT` with zero fits.

## File map

- Create `src/eating_event/route3/targets.py`: pure role-local target construction and a lazy mapping over A2 candidates.
- Create `src/eating_event/route3/budget.py`: exclusive fresh namespace, append-only fsynced attempt ledger, fit accounting, active wall/RSS/disk/thread checks.
- Create `src/eating_event/route3/workflow.py`: A2-004 authenticated load, role-local matching-aware corpus preparation, all-fit G3 precheck, audit-ready hash, and result/status persistence.
- Create `scripts/run_route3_matching_aware.py`: exact-worktree `audit` and `run` commands, with thread limits set before scientific imports.
- Create `configs/route3-matching-aware-v1.json` and `.sha256`: fixed input identities, target, verifier, decoder, call plan, and limits.
- Create `tests/test_route3_targets.py`: synthetic deterministic assignment, strict threshold, per-participant separation, and outer-label-isolation tests.
- Create `tests/test_route3_workflow.py`: synthetic nested fit composition and all-role G3 precheck tests. The fake backend must make zero estimator calls.
- Update `docs/superpowers/specs/2026-09-26-route3-matching-aware-target-proposal.md` and `docs/decisions/2026-09-26-route2-preflight-review.md` only after a terminal run status exists.

## Execution tasks

### Task 1: Target assignment

- [x] Write the synthetic tests first. Assert strict thresholding, one-to-one selection, per-participant matching, and outer-label isolation.
- [x] Run the target test first and confirm the expected initial `ImportError` for the new target module.
- [x] Implement `assign_role_targets(role, rows, truths_by_participant, *, iou_threshold)` using `evaluate_participants`; the outer branch returns rows unchanged only after asserting every label is null.
- [x] Run `tests/test_route3_targets.py`; the four target tests passed during initial implementation. Later integrity changes were syntax-checked, not retested.

### Task 2: Immutable config, resource ledger, and audit-ready gate

- [x] Write synthetic ledger/workflow tests before implementation; cover namespace rejection, fit-attempt accounting, resource stops, null outer labels, and per-composition G3.
- [x] Run the workflow test first and confirm the expected missing-module failure.
- [x] Create the fixed Route 3 config and sidecar, fresh namespace, `Route3Budget`, A2-004 loader, and target audit/precheck code. The audit did not produce `AUDIT_READY` because the following resource gate failed.
- [x] Run the target/workflow/budget tests during initial implementation; nine passed. Later integrity changes were syntax-checked, not retested.
- [x] Run the synthetic sizing gate with the configured 4,183 outer-candidate counts and 26D `float32` arrays. It stopped because the required 2x RSS margin exceeded the startup-derived ceiling; see the machine-readable failure record. No size profile was persisted.
- [x] Freeze the config and code identities and run the no-fit `audit` once. G3 returned for all 25 compositions, then the audit terminated `INCOMPLETE_RESOURCE`; do not continue or retry.

### Task 3: Single nested execution

- [ ] Write the fake-backend integration test and exercise the nested A2 execution graph. Not started because no `AUDIT_READY` state was produced.
- [x] Implement the fixed runner integration, thread limits, audit-ready verification, and pre-fit key/feature/label hash comparison. The execution path was not entered.
- [ ] Run integration tests against the final implementation. No tests were rerun after the final integrity edits.
- [ ] Invoke the `run` command. Not started because the audit gate failed; no verifier fit or score occurred.
- [x] Persist the terminal `INCOMPLETE_RESOURCE` status and ledger. No performance metrics are inferred.

## Review gates

- [ ] Independent reviewer checks Route 3 code/config/result consistency. The prior independent review covered Route 2 documents only.
- [ ] Report this as local development evidence over previously exposed folds. Keep `A1=CLOSED`, `Formal G1=FAIL`, `full training=BLOCKED`, `production=UNCHANGED`; a pass does not establish official matcher, PPG integration, or independent participant confirmation.
