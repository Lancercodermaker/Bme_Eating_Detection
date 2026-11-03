# Route 2 Evidence Packet and Route 3 Entry Review

Date: 2026-09-27  
Status: Route 2 evidence packet complete; Route 3 terminal prefit status is `INCOMPLETE_RESOURCE`.  
Scope: Route 2 source review, followed by one authorized Route 3 no-fit audit. Route 3 code and config were added in a separate namespace; no verifier fit, candidate model call, or production change occurred.

## 1. Request and controlling scope

The user asked to read `docs/handoffs/2026-09-26-route2-resume-prompt.md` and complete Route 3 execution. The referenced prompt is a Route 2 resume/preflight prompt; the initial review therefore completed the Route 2 evidence packet and recorded the Route 3 pause. The user then said "continue." That instruction was treated as authorization for one bounded Route 3 attempt. A hash-bound config and fresh ledger were created, and the no-fit audit was run once. It stopped before `AUDIT_READY` at the synthetic RSS margin gate, so the nested run was not started.

## 2. Scope and access record

New deliverables:

- `docs/evidence/2026-09-26-route2-source-reaudit.md`
- `docs/superpowers/specs/2026-09-26-route3-matching-aware-target-proposal.md`
- This review decision.
- `configs/route3-matching-aware-v1.json` and its SHA-256 sidecar.
- Route 3 target, workflow, resource-budget, runner, and fixed entry-point code under `src/eating_event/route3/` and `scripts/run_route3_matching_aware.py`.
- `artifacts/route3-matching-aware-v1-001/resource-preflight-failure.json` and the terminal Route 3 status/ledger.

The Route 2 source re-audit records the exact approved artifact members, candidate-row registrations, field boundaries, and carried-forward claims. During Route 3, `load_audited_corpus` read authenticated, materialized A2-004 candidate rows, 26D features, saved labels (authentication only; replaced in memory for non-outer roles), roles, and eligible GT. Outer GT was not used to construct labels. The process computed matching-aware targets and all 25 G3 checks in memory, but persisted neither target counts nor the synthetic size profile after the following RSS gate failed. It did not read raw sensor files, original metadata CSVs, official test data, external data, NPZ score members, cache arrays, or load/fit/call a model.

One path-enumeration deviation occurred before the prompt was read: `Get-ChildItem -Path E:\bme_compitition -Filter AGENTS.md -Recurse -File` was used to look for repository instructions. It returned no matches. It enumerated paths under the project root and could have traversed restricted directories; no returned content was opened and no further investigation was performed. This deviation was disclosed to the user. Consequently, the overall process cannot be described as unqualified path-boundary compliance.

The pre-existing `2026-09-26-route-handoff-review.md` also records a separate earlier `rg --files --hidden` path-enumeration deviation from a route-challenge pass. That historical record was not treated as evidence about this pass; both deviations remain disclosed in their respective reviews.

## 3. Evidence result

- Rechecked 21 no-matchable-candidate FN rows and their best saved candidate IoUs. Four have no positive-length candidate overlap. Three short GT durations (29, 15.372, and 35 seconds) cannot reach strict IoU > 0.25 under the existing minimum 180-second output duration.
- Rechecked all 79 unmatched predictions of at least 600 seconds against the 281 registered annotations: 58 have zero annotation overlap and behavior remains UNKNOWN; 10 overlap an annotation but have max IoU <= 0.25; 11 overlap an eligible GT above 0.25 while a different output is matched to that GT.
- All 79 long intervals already equal their single saved source candidate interval. Final 600-second fusion did not make them long. The 300-second pre-fusion trace is NOT_SAVED, so its causal contribution is unknown.
- The 11 competing output intervals are disjoint, with gaps of 4.089 to 240 seconds. Nine pairs cross record/session and two share a record/session but differ in component. No GT-free group relation is saved; this evidence does not establish a legal inference-time grouping rule.
- Source spelling `hnu21033` is retained as stored. Its identity correspondence to a differently cased participant spelling was not independently checked.

These are local annotation-contract conclusions only. The official matcher, inference scope, submission interface, PPG inputs, and resource rules remain unknown. The evidence does not reopen A1, Formal G1, full training, A2, or production.

## 4. Route 3 proposal and independent review

The proposal changes one mechanism: construct one-to-one positive labels within training roles on fixed saved candidate intervals, train the same pointwise 26D verifier, and score candidates independently at inference. It excludes outer GT from training, threshold choice, features, and prediction. It does not create new boundaries, group candidates by GT, or merge across components.

Independent reviewer result: no P0 and no remaining blocking document issue in the patched documents. The reviewer checked document consistency, not the underlying JSON/JSONL artifacts, and does not claim an independent artifact-level reproduction. The reviewer confirmed that the proposal distinguishes frozen A1/base score inputs from new verifier probabilities; roots and the 58/10/11 source chain are explicit; question-mark punctuation is fixed; and the lowercase participant spelling is preserved with the identity limitation stated. The earlier path-enumeration deviation remains a process limitation.

This independent review predates Route 3 implementation. No independent reviewer checked the Route 3 code, config, or terminal resource artifact.

## 5. Route 3 terminal result

The single Route 3 audit ended with `INCOMPLETE_RESOURCE`. The exact config hash is `f8b5eaf0e3f40f46082bb0e5f41137ff9dca375917da7c6585475bc44305dc7f`. Route 3 caps were 900 active seconds, 600 verifier-fit seconds, two threads, 512 MiB disk, and process-tree RSS `min(3 GiB, 50% of startup available memory)`.

Startup available memory was 3,025,342,464 bytes, so the RSS ceiling was 1,512,671,232 bytes. The A2-004 audit RSS comparator alone (799,109,120 bytes) requires 1,598,218,240 bytes at a 2x margin, exceeding the ceiling by 85,547,008 bytes; measured peak process-tree RSS during this audit was 791,105,536 bytes. The ledger confirms zero verifier fit attempts and no `AUDIT_READY`; no `run` was started. The detailed terminal record is in `resource-preflight-failure.json`.

The G3 precheck returned successfully for all 25 fit compositions before sizing, but its role-level counts were not persisted. No F1 result exists. `A1=CLOSED`, `Formal G1=FAIL`, `full training=BLOCKED`, and `production=UNCHANGED` remain in force. The fixed Route 3 namespace is terminal and cannot be retried or given different caps. A future experiment would require a new reviewed config and namespace with explicit authorization.
