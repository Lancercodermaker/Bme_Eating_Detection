# Route 3 Preflight: Matching-Aware Target on Fixed Candidates

Date: 2026-09-26; execution record added 2026-09-27  
Status: TERMINAL PREFIT STOP - `INCOMPLETE_RESOURCE`; zero verifier fits.  
Scope: One proposed change to training supervision on the frozen A2 candidate intervals and feature roles. One user-authorized no-fit audit was attempted under a new config and namespace, then stopped at the synthetic RSS margin gate. No verifier model was fitted and no production state changed.

## Execution record (2026-09-27)

- Route 3 config SHA-256: `f8b5eaf0e3f40f46082bb0e5f41137ff9dca375917da7c6585475bc44305dc7f`.
- The no-fit audit reached and completed all 25 role-specific G3 checks in memory, then stopped during synthetic RSS sizing because the required 2x cap margin failed. Detailed target counts and the synthetic profile were not persisted.
- Startup available memory was 3,025,342,464 bytes, giving a Route 3 RSS ceiling of 1,512,671,232 bytes. The A2-004 audit RSS comparator alone is 799,109,120 bytes; twice that lower bound is 1,598,218,240 bytes, 85,547,008 bytes above the Route 3 ceiling. Peak sampled process-tree RSS during the audit was 791,105,536 bytes.
- The terminal ledger records zero verifier fit attempts. No score call, candidate fit/predict, audit-ready state, or nested run occurred. The single-attempt namespace is terminal; no retry or cap change is authorized within it.
- Machine-readable record: `artifacts/route3-matching-aware-v1-001/resource-preflight-failure.json`.

## Project preflight

### Goal

Test whether assigning one positive training candidate per eligible GT improves the local event-output benchmark over A2's candidate-level any-IoU-positive target, while keeping candidate intervals fixed.

### Success metrics

Use the existing local 41-participant / 234-eligible-GT contract and strict IoU > 0.25. Report pooled and per-fold TP/FP/FN, precision, recall, event F1, long-FP fraction, matched start/end MAE, matched GT IDs gained/lost, candidate coverage, and resource use.

The existing development gates remain separate:

- Numeric minimum: pooled F1 >= 0.66.
- Numeric ideal: pooled F1 >= 0.80.
- Stage minimum/ideal additionally require at least 3/5 folds at F1 >= 0.66, every fold long-FP fraction <= 0.25, and every fold matched start/end MAE <= 900 seconds.
- These are local development gates, not verified official thresholds.

### Constraints

- Freeze the 4,183 outer candidate intervals, all registered A1/base candidate score outputs (including raw/relative values), the A2 26D role feature values and schema, 41 participants, 234 GT, folds, seed, decoder, interval durations, and evaluator. The new verifier probability scores are outputs of this proposed run, not frozen inputs.
- Keep the 5 outer / 4 inner / 4 subinner role graph and fit labels separate from features.
- Do not use outer GT for label construction, fit, threshold selection, feature creation, or prediction.
- Candidate-model fit/predict remain zero. No new candidate generation or boundary changes.
- Preserve A1 CLOSED, A2 fixed-26D CLOSED_STAGE_MINIMUM_FAIL, Formal G1 FAIL, full training BLOCKED, and production UNCHANGED.
- Official matcher details, inference input scope, non-dominant-hand PPG interface, future context, and resource limits remain unknown.

### Prior art and baseline

Evidence packet: docs/evidence/2026-09-26-route2-source-reaudit.md.

A1 v1-005 is COMPLETE with pooled F1 0.585086 (153 TP, 136 FP, 81 FN). A2 v1-004 is legally COMPLETE with pooled F1 0.623482 (154 TP, 106 FP, 80 FN), but all four numeric/stage gates fail. A2's fixed candidates cover 213/234 GT with at least one matchable candidate; this is not a simultaneously achievable TP count.

The post-closure review found 21 GT with no strict-matchable candidate, 79 long FPs, including 58 with no annotation overlap and behavior UNKNOWN, and 11 long non-overlapping output candidates with eligible-GT IoU > 0.25 whose GT was matched to another prediction. The 79 long outputs already exist as long candidate intervals. The 11 cases motivate a one-to-one supervision hypothesis; they do not prove a deployable inference grouping rule.

### Candidate approach

For each training candidate role, construct a target using only that role's eligible GT and fixed candidate intervals:

1. Apply the existing local strict-IoU, participant-global deterministic one-to-one matcher to the candidate intervals and that role's eligible GT.
2. Mark a candidate positive only if the matching assigns it to a GT; mark every other candidate negative.
3. Keep the existing HGB pointwise verifier family, 26D A2 feature schema, exact A2 fit settings, seed 20260910, inner threshold set {0.10, 0.25, 0.50}, and decoder unchanged. Bind the actual settings by source/config identity before authorization.
4. At inference, score each fixed candidate independently and preserve its interval. Do not construct GT-defined groups, merge across components, or generate new boundaries.

This changes only the training target from "candidate overlaps any eligible GT above threshold" to "candidate is selected by the one-to-one assignment." Matching uses training labels only. Inner held-out GT is used only for the existing inner threshold selection. Outer GT remains unused until final metric evaluation.

The new target is built on the saved post-300-second candidate intervals before verifier thresholding and the final 180-second/600-second decoder. This choice is exact but is not identical to matching final decoded outputs; the difference must stay explicit when interpreting results.

### Critical assumptions

| Assumption | Supporting evidence | Contradiction / uncertainty | Cheapest discriminator and interpretation |
|---|---|---|---|
| One-to-one supervision can reduce duplicate candidate selections | 11 saved outer FP candidates had IoU > 0.25 to a GT already assigned elsewhere; the current any-IoU target can label multiple candidates positive for one GT | These 11 outer cases cannot define training rules; candidate features may not distinguish the assigned and unassigned candidates | One nested development validation with training-fold-only assignments. Improvement in same-denominator F1 and gates supports this target; failure closes this variant |
| Fixed A2 features contain useful ranking signal | A2 has a role-qualified 26D feature schema and 25 verifier fits; current pointwise A2 reaches F1 0.623482 | The feature values were not read in this review; identical feature vectors or weak candidate-level signal cannot be separated by a pointwise scorer | Audit registered feature digests and inspect fold-held-out score distributions only under new authorization |
| Assignment labels are sufficient for all fit roles | Existing role graph separates outer/inner/subinner participants and labels | Selecting one candidate per GT reduces positive counts; some fit may fail the existing G3 minimum | Recompute role-specific positive candidates, positive participants, distinct positive GTs, and class presence before any fit; any failed fit gate stops as data-insufficient |
| Local matching is an acceptable development target | Local strict IoU > 0.25 and one-to-one greedy rules are recorded | Official matcher, eligibility, and scope are not fully known | Obtain official evaluation contract if available; absent that, report only local-contract development evidence |
| This meets the complete competition task | Official text requires targeted solutions for both wearing scenarios and PPG for non-dominant hand | Current approved evidence does not establish a PPG-derived route-3 input or official inference API | Require the exact official interface and approved PPG-derived fields before claiming competition completeness |

### Risks

- This objective cannot create a matchable candidate for the 21 FNs and cannot remove the 180-second short-GT geometry limit.
- The 58 zero-annotation-overlap intervals remain behavior UNKNOWN; suppression means benchmark FP reduction only.
- Outer cases have already influenced development decisions; another five-fold result remains development evidence, not independent confirmation.
- Assigning targets on pre-decoder candidate rows may not align with the final decoded event set.
- The local greedy matcher is not confirmed as the official matcher.
- Changing the positive target may make one or more fits fail G3.
- The official non-dominant-hand / PPG requirement is not demonstrated by this mechanism.

### Proposed validation and exact call plan

This is a proposal, not a run authorization.

- Inputs: exact registered A2 role candidate rows and feature matrices; use candidate identity, fixed interval, and 26D feature matrix. Construct target labels separately from only the training-role canonical GT. Do not fit/predict the A1 candidate model or regenerate its base raw/relative scores. The 25 listed predict_proba calls are new outputs from the fitted verifier.
- Candidate-model fit/predict: 0 / 0.
- New verifier fits: 25 total if every gate passes (20 inner threshold-selection roles plus 5 final outer roles).
- Verifier predict_proba calls: 25 total (one per held-out role; reuse each output for the frozen threshold choices).
- Inner threshold decodes: 20 roles x 3 thresholds = 60; final outer decodes: 5 selected thresholds; proposed total 65.
- Final outer evaluations: 5. Inner threshold evaluation uses only its corresponding held-out inner role.
- The exact software call count and use of persisted matrices must be confirmed in an implementation plan before any run.
- No retry, alternate seed, extra threshold, changed candidate, or outer-specific repair.

Every fit must pass G3: at least 20 positive candidates, at least 5 positive participants, and both classes. Report distinct positive canonical GT count. Target counts are unknown until a separately authorized audit computes them.

### Resource and authorization result

A2-004's saved measurements (active wall 314.266 seconds, fit wall 2.971 seconds, run RSS 238,301,184 bytes, audit RSS 799,109,120 bytes) describe A2-004 only. Route 3 used independent caps: 900 active seconds across audit and run, 600 verifier-fit seconds, two threads, 512 MiB disk, and RSS `min(3 GiB, 50% of startup available memory)`.

The user later said “continue,” which authorized one bounded Route 3 attempt. Its immutable config and fresh ledger were created. The no-fit audit stopped before `AUDIT_READY`: even twice the A2-004 audit RSS comparator exceeds the startup-derived Route 3 ceiling, before adding Route 3 matrix, label, and candidate-row estimates. The terminal status is `INCOMPLETE_RESOURCE`; the full resource record is in `resource-preflight-failure.json` and the budget ledger. No F1 or performance result exists.

### Kill criteria

Stop before fitting if any role identity or feature digest fails, if outer labels are present, if the target matcher cannot be applied without outer GT, if any fit fails G3, if the registered feature/schema contract is unavailable, or if resources cannot be measured under a frozen cap. Record identity/data failures as INVALID, missing positive supervision as DATA_INSUFFICIENT, and resource failures as INCOMPLETE_RESOURCE. Do not retry or change the route.

Evaluate performance only after a complete legal five-fold run. Use the frozen local denominator and gates above. Report matched GT changes alongside MAE. A failure closes this target variant; it does not prove all ranking methods fail. A pass remains development evidence and does not reopen A1, Formal G1, full training, or production.

### Recommendation

The one-to-one supervision target remains a plausible local hypothesis because it addresses the observed multi-positive / single-TP mismatch while leaving candidate geometry fixed. The authorized attempt stopped before fitting, so it provides no performance evidence and does not show whether the target helps. The frozen study ID cannot be retried or given a wider cap. Any future attempt needs a separately reviewed config, fresh study/ledger namespace, and explicit authorization.

### Confidence

Medium-low. The 11 competition cases support the mechanism, while lack of feature separability evidence, development reuse, unknown official matcher/API, and the unresolved PPG requirement limit the conclusion.
