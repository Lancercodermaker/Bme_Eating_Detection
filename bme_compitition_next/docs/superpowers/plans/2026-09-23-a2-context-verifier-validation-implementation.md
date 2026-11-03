# A2 Context Verifier Validation Implementation Plan

> **2026-09-23 执行后状态：**本 `001` 计划在真实来源审计门禁以 `INVALID` 关闭，0 fits、无 `AUDIT_READY`、无性能结果；下文 `PLAN_READY / NOT_EXECUTED` 是历史起点。只按新[002 修订决定](../../decisions/2026-09-23-a2-002-identity-contract-recovery-decision.md)与[002 执行计划](2026-09-23-a2-002-identity-contract-recovery-implementation.md)进入另一个编号的恢复验证；禁止再次执行本文 `001` audit/run 命令。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

In this Codex installation the callable skill names are `subagent-driven-development` and `executing-plans`; the `superpowers:` wording above is the required plan-header convention. Apply a skill only in the later execution conversation, not during this documentation turn.

**Goal:** Test once whether fixed A1 candidates gain event-level discrimination from ten frozen same-component score-trajectory features, while retaining the approved participant-disjoint and event-evaluation contracts.

**Architecture:** Read and authenticate A1 run `005` artifacts without loading its models or raw sensor; join each candidate role's complete scored-window stream to approved cache geometry, preserve the original 16D candidate rows, and create a separate 26D feature matrix. Refit only the 25 nested verifier roles under a fail-closed A2 study ledger, then decode and evaluate exactly once using A1's frozen rules.

**Tech Stack:** Python 3.10, NumPy, scikit-learn HGB through existing `eating_event.a1.scoring`, approved A1 cache/JSON/NPZ artifacts, pytest, psutil for process-tree supervision.

---

Status: `PLAN_READY / NOT_EXECUTED` (2026-09-23). The [A2 review and conditional authorization](../../decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md) supersedes conflicting wording in the [2026-09-22 A2 draft](../specs/2026-09-22-a2-context-verifier-redesign.md) for this validation. The user's authorization applies to **one later-conversation development validation after readiness gates**, not to this documentation turn. A1 is closed; Formal G1 is FAIL; full training and production remain blocked.

## Fixed boundaries and file map

- Work only in `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`. Keep all A1 code, configuration, source artifacts, canonical labels and production unchanged. Do not read or stat raw sensor, official test or external data. Do not load an A1 model pickle or call a candidate model's `predict`/`predict_proba`.
- Source A1 directory: `artifacts/a1-end-to-end-feasibility-v1-005`. Its `final-checksums.json` SHA-256 is `0543791e90df9e1bcf93111dc45e80678089898409e6888b90584fd18c469025`; all 282 listed entries and the 45 registered A1 code paths currently hash correctly. A2 must verify them again at run time.
- A2 study output: `artifacts/a2-context-verifier-v1-001` only. The durable append-only ledger and lock live at `artifacts/a2-study-budget.jsonl` and `artifacts/a2-study-budget.lock`, outside that output directory; the output holds a mirror. No alternate attempt directory, hidden rerun, or fit-budget reset. The executor may iterate code and synthetic tests before the real study begins; the study clock starts at the **first real-source audit**, including failed or repeated audits. After a fit is reserved, no automatic retry.
- Frozen outer candidate counts `[946, 892, 929, 653, 763]`, covered GT `[46, 48, 47, 31, 41]`, pooled 4,183/213, 41 participants and 234 evaluation GT are input invariants. A2 may change final predictions only through the new verifier scores.

| File | Responsibility |
|---|---|
| `configs/a2-context-verifier-v1.json` and `.sha256` | Exact study constants, source hash root, limits and frozen verifier schema |
| `src/eating_event/a2/contracts.py` | A2 config, role-qualified keys, label-free feature-row types and validators |
| `src/eating_event/a2/features.py` | Pure 16D→26D transformation from already-scored, same-component windows |
| `src/eating_event/a2/inputs.py` | Safe A1 manifest/cache geometry and score loading; no raw/model pickle I/O |
| `src/eating_event/a2/audit.py` | Fail-closed source hashes, role/score/candidate/component/label and isolation audit |
| `src/eating_event/a2/execution.py` | 25 verifier roles, inner selection, outer decode/evaluation and lineage output |
| `src/eating_event/a2/budget.py`, `control.py`, `worker.py` | Durable one-study fit-attempt ledger, supervisor, lock, resource telemetry and status |
| `scripts/run_a2_context_verifier.py` | `audit` and `run` entry points; `run` requires saved `AUDIT_READY` identity |
| `tests/test_a2_features.py`, `test_a2_audit.py`, `test_a2_pipeline.py`, `test_a2_control.py` | Synthetic behavior, tamper, isolation and resource-gate tests |

Do not change `src/eating_event/a1/contracts.py::EVENT_FEATURE_DIM`, `A1Candidate`, A1 configs or A1 runner. Reuse A1's fit primitive, decoder and participant-safe evaluator through imports; keep the A2 matrix/lineage separate. If an import requires an A1 source edit, stop and review that proposed edit before proceeding.

## Implementation cadence and exact commands

Tasks 1–5 are implementation work; Task 6 alone reaches real A1-derived inputs. Within each task, implement one named counterexample at a time: add its synthetic test, run that task's exact `python -m pytest` file command below and observe a failure for the intended missing behavior, add the minimum A2-only code, rerun the same command to green, then move to the next case. Do not mark a task complete from a single happy-path test. Preserve the existing dirty worktree: use `git status --short` before staging, stage only the A2 paths named in that task, run `git diff --cached --check` and verify `git diff --cached --name-only` contains **only** intended A2 files before committing them after green tests. If unrelated changes were already staged, leave them untouched and skip the commit checkpoint. Never run a cleanup/reset or `git add .`. Record executed commands and observed results in the A2 study notes. Synthetic test activity does not start the real-source study or consume model-fit attempts, but synthetic tests in this plan must not invoke a candidate estimator.

The runner exposes exactly two study commands from the specified worktree, with no CLI switches for thresholds, data roots, seeds, feature choices or alternate output directories:

```powershell
python scripts/run_a2_context_verifier.py audit
python scripts/run_a2_context_verifier.py run
```

`audit` is a no-fit/no-predict real-source check and begins the durable 7,200-second active-wall accounting. `run` is unavailable until a hash-matched `AUDIT_READY` exists; it consumes at most 25 reserved verifier fit attempts. Both commands must return nonzero on `INVALID`, `VERIFIER_DATA_INSUFFICIENT`, `INCOMPLETE_RESOURCE` or interruption and write an explicit status. A successful `audit` is readiness evidence, not a performance result.

## Task 1: Freeze A2 constants and typed contracts

**Files:** Create `configs/a2-context-verifier-v1.json`, `configs/a2-context-verifier-v1.sha256`, `src/eating_event/a2/__init__.py`, `src/eating_event/a2/contracts.py`; test `tests/test_a2_audit.py`.

- [ ] Define schema `a2_event_context_v1`, base schema `a1_relative_event_features_v1`, 16+10 dimensions, seed `20260910`, read-only candidate reference quantile `q=0.90`, fixed lookaround `300000` ms, observed-fraction divisor `40`, thresholds `[0.10,0.25,0.50]`, candidate fuse `300000` ms, decode fuse `600000` ms, min duration `180000` ms, long FP `600000` ms, strict IoU `>0.25`, frozen A1 verifier HGB parameters, and the A1 `005` checksum root above. Configuration loading must reject any different value, extra research option or unapproved source path. `q` is audited against saved candidate score provenance; it never triggers candidate recalibration.
- [ ] Freeze limits: 0 candidate fits/predicts, ≤25 verifier fit **attempts**, total audit-plus-run wall ≤7,200 s, cumulative verifier-fit wall ≤3,600 s, ≤4 threads, **all new study artifacts including external ledger and temporary files** ≤1 GiB, RSS ≤`min(8 GiB, 0.60 × startup available bytes)`. This is one study across interruption and restart. Store the config SHA-256 in its sidecar using canonical file bytes; validate the sidecar before `audit` or `run`.
- [ ] Make the feature row identity a pair, never a bare candidate ID. Its feature input has no `label` field:

```python
CandidateKey = tuple[str, str]  # (role_id, candidate_id)
# A2FeatureRow holds key, participant/record/session/component, interval,
# source_16d (float64 values in JSON order), features_26d (float32 for fit),
# support stable IDs and source hashes. Labels live in a separate mapping.
```

- [ ] Test that changing any frozen constant, source hash, feature width or role-qualified key rule fails before file loading or fit. Run `python -m pytest tests/test_a2_audit.py -q`; expected exit code 0.

## Task 2: Implement the exact pure 26D feature function

**Files:** Create `src/eating_event/a2/features.py`; test `tests/test_a2_features.py`.

- [ ] Write synthetic tests **before** the function: midpoint equal to `s` belongs inside, midpoint equal to `e` belongs post, positive-length half-open overlap joins a positive run, endpoint touch breaks it, any negative relative-score window breaks it, an empty pre/post region yields three zeros, an empty inside region is `INVALID`, and a window from another component or role is rejected. Include overlapping boundary windows so pre/post are not incorrectly treated as disjoint outside evidence.
- [ ] Implement the draft's ten features in exactly this order. For `inside=[s,e)`, `pre=[s-300000,s)`, and `post=[e,e+300000)`, assign a same-component scored window by `mid=(start_ms+end_ms)//2`. Use the saved `relative` score. Define `positive` as `relative>=0`; sort by `(start_ms,end_ms,global_window_index)`. Count a positive run across successive positive windows only when `next.start_ms < run_end_ms`, update `run_end_ms=max(run_end_ms,next.end_ms)`, and reset on nonpositive/touch/gap. Divide the largest run's window count by all inside-window count. The feature vector is:

```text
1–16  saved A1 candidate JSON feature numbers in original order
17    inside mean(relative)
18    inside linear-interpolated p25(relative)
19    inside positive count / inside count
20    inside longest positive run window count / inside count
21    pre mean(relative), or 0 if empty
22    pre positive count / pre count, or 0 if empty
23    min(pre count / 40, 1)
24    post mean(relative), or 0 if empty
25    post positive count / post count, or 0 if empty
26    min(post count / 40, 1)
```

- [ ] Require all 26 values finite; preserve the original 16 JSON numeric values and order before the final A1-compatible `float32` matrix cast. Require every selected post window's `end_ms <= candidate.end_ms+300000`; a violation fails source audit. Do **not** claim the final decoded output has 300-second latency: 600-second-gap fusion is offline.
- [ ] Run `python -m pytest tests/test_a2_features.py -q`; expected exit code 0. No trained model is called by these tests.

## Task 3: Authenticate and join every frozen input before any fit

**Files:** Create `src/eating_event/a2/inputs.py`, `src/eating_event/a2/audit.py`; extend `tests/test_a2_audit.py`.

- [ ] Test failure cases first: altered `final-checksums.json`, a listed-file hash mismatch, an A1 registered code path drift, score provenance/model signature conflict, score path escape, global score ID out of range/duplicate/missing, reordered or partial scored-window IDs, nonfinite score, `relative` mismatch, cross-role candidate-ID collision incorrectly treated as global duplicate, within-role duplicate, support outside its role/component, a non-null outer candidate label in a real artifact, and outer-valid participant leaking into fit/reference/selection.
- [ ] Authenticate the pinned `final-checksums.json` hash, then verify every listed A1 artifact. Verify only the **registered** A1 `run-manifest.json.code_identity` paths against their hashes; the new A2 source files get their own code manifest. Verify eligibility SHA-256 `68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30`, canonical denominator SHA-256 `6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d`, approved cache manifest/record hashes and all 130 role/provenance records. Reject missing/extra/conflicting role entries.
- [ ] Load `window-identity.json` as the 632,100-item **global** ordered table. Read only approved cache numeric `starts`, `ends`, `coverage` and `crosses_gap` with `np.load(..., allow_pickle=False)` after each cache file hash and approved-root check; reconstruct record ID exactly as A1 does (`entry.record_id` or cache filename stem). Never open the opaque raw path recorded in a manifest. Match each global identity row to one numeric cache row, with original record-local `row_index` and time bounds.
- [ ] For each candidate role, load its score NPZ with `allow_pickle=False`, require `ids` exactly equal the ordered global indices of **all** approved windows whose participant is in `role.scored_participants`, and require `np.array_equal(relative, raw - role_threshold)` after finite/type/shape checks. Validate score-file hash, model hash/signature, reference q/count/row hash, fit/reference/scored/selection/outer-valid participant sets, and source hash lineage against the A1 role graph. Candidate score roles have a real threshold reference; the 25 A1 verifier provenance roles record `reference_participants=[]` and `threshold=None`, so audit those with their **verifier** provenance semantics rather than demanding a candidate reference from them. The saved candidate `relative` array is the only A2 feature score source; never recompute a candidate model score.
- [ ] Rebuild `build_support_components` from every scored window of each `(participant,record,session)` role group. Audit each saved candidate under `(role_id,candidate_id)` for order, 16D values, interval, support stable IDs, component and label semantics; explicitly require `boundary_kind=observed_window_support_component_v1` and `source_segment_id=null`. Training/inner rows may carry frozen labels, outer rows must have `label=null`. The 26D function receives a projection without that label. Assert the five outer candidate and covered-GT invariants specified above; only the existing approved GT may be used for the latter audit, never for feature construction.
- [ ] Save a no-fit `AUDIT_READY` report with input hashes, role counts, score completeness, per-role candidate counts, G3 precheck, context empty-region counts and feature finiteness, without using any outer metric to revise features. Persist per-role ordered `(role_id,candidate_id)` keys, the actual 26D `float32` matrix digest and a **separate** training-label join digest; bind all three to source/config/code hashes. Run `python -m pytest tests/test_a2_audit.py -q`; expected exit code 0. A real-source failure is `INVALID`, not an invitation to adapt rules to failed events.

## Task 4: Preserve nested OOF selection with a fake backend first

**Files:** Create `src/eating_event/a2/execution.py`; test `tests/test_a2_pipeline.py`.

- [ ] Write a fake-backend full-run test that records each verifier fit/scored participant set, feature schema and labels. It must show 20 inner verifier roles trained from four subinner candidate roles each, five outer verifier roles trained from four inner candidate roles each, **zero** candidate fits/predicts, and no outer-valid participant in any fit/reference/selection. Test the **pure feature function** ignores an injected label and evaluation GT; separately, test the real-source audit rejects a non-null outer label as `INVALID`. Perturb **one selected fold's outer-valid evaluation GT** and verify that same fold's inner threshold choice and outer prediction intervals remain unchanged; other folds may legally use that participant for training.
- [ ] Fit each inner verifier only on the four subinner OOF candidate sets of its parent inner train; score only its held-out inner candidate role. Choose among the three frozen thresholds with A1's exact tuple rule `(pooled_inner_F1_or_minus_one, -pooled_inner_FP, threshold)` on inner-valid participants. Fit each outer verifier only on the four inner OOF candidate sets of outer train; score its held-out outer candidate role **once**. Keep role-qualified score, fit signature, model hash, features hash, labels hash and selected-threshold lineage.
- [ ] Before **each** verifier fit, recheck G3: ≥20 positive candidates, ≥5 distinct positive participants, both binary classes. Save independent positive canonical GT count. Reserve the attempt before fit; failure stops `VERIFIER_DATA_INSUFFICIENT` or `INVALID`, not numeric FAIL. Use frozen A1 HGB parameters, `seed=20260910` and 26D `float32` matrix. Do not reuse the A1 16D verifier pickle.
- [ ] Use the unchanged A1 `decode_candidates` ordering (score threshold, 180-second minimum, same-component 600-second-gap fusion), then the unchanged participant-safe evaluator with strict IoU `>0.25`. Pass a 16D A1-compatible decode view containing the saved original candidates plus the new verifier scores; the 26D matrix exists only for A2 verifier fit/scoring and never enters `A1Candidate`. Retain decoded `source_candidate_ids` in a separate role-qualified lineage file **before** converting to `PredictionRecord`; do not infer ancestry from final intervals. Include participant `6C7` and all 234 GT. The 81 A1 FN stage-transition report uses stable GT IDs and fixed first-break categories only after the run is complete.
- [ ] Test zero-GT/zero-prediction, zero-GT/FP, FP=0 long fraction=0, no-match MAE=null and null quality failure, one-to-one match competition, fold and pooled aggregation. Run `python -m pytest tests/test_a2_pipeline.py -q`; expected exit code 0.

## Task 5: Build one-study supervision and fail-closed outputs

**Files:** Create `src/eating_event/a2/budget.py`, `control.py`, `worker.py`, `scripts/run_a2_context_verifier.py`; test `tests/test_a2_control.py`.

- [ ] Test before implementation: a reserved interrupted fit still consumes one of 25 attempts; a duplicate role fit is rejected; no candidate fit/predict path exists in the real-study runner; total active wall includes **every** real-source audit invocation plus execution across restarts; cumulative fit wall includes completed fit durations and the active fit; a process-tree RSS sample failure, total study-disk overage or worker disappearance terminates without success. Test that deleting/renaming the study output while the external ledger remains is fail-closed, that a missing/corrupt external ledger when its output mirror exists is fail-closed, and that `run` after `COMPLETE` or any terminal failure cannot restart the study. An A1 scientific-library version mismatch must reject the run before fit.
- [ ] Implement a single study lock and append-only, fsynced attempt/resource ledger at `artifacts/a2-study-budget.jsonl`, mirrored into `artifacts/a2-context-verifier-v1-001`. Pin the available-memory sample and RSS ceiling on the first real-source audit and reuse that ceiling across audit/run invocations; never resample to raise it. Persist cumulative active audit/run wall, active fit wall and all fit reservations across restarts. If a process dies with an unclosed audit/fit interval whose elapsed time cannot be proved, stop `INCOMPLETE_RESOURCE`; never reconstruct a favorable remaining budget. Supervise the worker process tree through audit, fit, scoring and artifact writes; force ≤4 BLAS/OpenMP threads. Preserve the A2 study ledger on failure. Do not reuse A1's study-name-specific directory glob or treat A1's per-fit timeout as the A2 cumulative one-hour limit.
- [ ] Write status values `AUDIT_READY`, `COMPLETE`, `INVALID`, `VERIFIER_DATA_INSUFFICIENT`, `INCOMPLETE_RESOURCE` and `INCOMPLETE_INTERRUPTED`, with a cause and ledger snapshot. Require and record A1 run-manifest versions Python 3.10.11, NumPy 2.2.6, SciPy 1.15.3, scikit-learn 1.7.2 and psutil 7.2.2 before fit; record the platform as well. Store a run manifest with frozen A1 checksum root, A2 config/code hashes, environment and role graph; score/model provenance and source-candidate lineage; fold/participant metrics, threshold choices, budget telemetry and final checksums. Keep A1 input paths as references, not copied 724-MB source artifacts. A `run` command rejects a missing or stale `AUDIT_READY` identity.
- [ ] Run `python -m pytest tests/test_a2_control.py -q`; expected exit code 0. Then run `python -m pytest tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_pipeline.py tests/test_a2_control.py -q`; expected exit code 0. Do not run a real fit during test development.

## Task 6: Freeze, audit, then run the sole real validation

**Files:** Freeze `configs/a2-context-verifier-v1.json` and its sidecar; create only A2 output under `artifacts/a2-context-verifier-v1-001`.

- [ ] Review the [binding design decision](../../decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md) line by line against Tasks 1–5. Run the four targeted A2 synthetic test files plus `python -m pytest tests/test_a1_contracts.py tests/test_a1_events.py tests/test_a1_metrics.py -q`; record actual test counts and environment. `tests/test_a1_scoring.py` and some full-suite fake-pipeline tests invoke candidate-model fit/predict, so do not run the full existing suite under this zero-candidate-call authorization. Freeze A2 source/config hashes **before** real-source feature materialization. If a pre-fit implementation correction changes any hash, repeat tests and no-fit audit under the same frozen scientific definition; every repeated real-source audit consumes the same study wall budget. Any scientific-definition change needs a new reviewed version before a real run.
- [ ] Invoke the new runner's `audit` mode once the tests pass. It may inspect approved A1 scores/cache and materialize fixed 26D features, but must perform zero model fits/predicts. Require every source/role/feature/G3/monitor check to pass and save `AUDIT_READY` with hash-bound inputs. If approved source identity fails, stop `INVALID`; do not fetch raw/test/external data or silently substitute a cache.
- [ ] Invoke `run` only after `AUDIT_READY` is verified. Before its **first fit**, and on any restart, rehash the actual ordered role-qualified candidate keys, 26D `float32` matrices and separate label joins against the saved audit digests; fail `INVALID` if any differ. It may fit at most 25 verifier roles, score only their legal held-out candidate rows, and evaluate each outer fold once. A failed or interrupted fit consumes its attempt; no retry, alternate directory, feature/threshold/seed change or same-run compensation. If the run is incomplete/invalid, report that state without treating it as negative performance evidence.
- [ ] For a complete run, record pooled and each fold's TP/FP/FN, precision, recall, F1, candidate count/coverage, long-FP count/fraction, matched start/end MAE/count, all-participant counts including `6C7`, event-bearing macro F1, participant mean/SD/worst and outer mean/median/SD/IQR, provenance, resource use and the fixed-stage transitions. Compute and report four distinct statuses: numeric minimum ≥0.66, numeric ideal ≥0.80, stage minimum and stage ideal. Stage additionally needs ≥3/5 folds F1≥0.66, every fold long-FP fraction≤0.25, and non-null matched start/end MAE≤900 s. FP=0 yields long fraction 0 with FP count 0; no-match MAE is null and fails its gate. State that A1's fixed 75 long FP without any approved annotation overlap have unknown actual behavior; A2 suppression of them is an annotation-contract FP reduction, not independent behavior adjudication. Retain the approved 234-GT metric and do not use this subgroup to revise features or thresholds.
- [ ] Close this 26D protocol after the single complete result. If stage minimum fails, do not search context width/features, verifier thresholds, duration, fusion, seed or model. If it passes, call it `SUPPORTED_ON_DEVELOPMENT_FOLDS` only. In either case keep `FORMAL_G1=FAIL`, `FULL_TRAINING=BLOCKED`, `PRODUCTION=UNCHANGED`, and note that no independent participant confirmation exists. Give the user a result handoff with complete report, status, hashes, fit ledger and any unresolved document/implementation conflict for the original design discussion before considering architecture redesign.

## Self-review and handoff checks

- [ ] **Spec coverage:** Map every section of the A2 draft and every correction in the binding 2026-09-23 decision to a task above. In particular verify the composite key, all-window score completeness, label-free features, G3, nested OOF, resource accounting, stage semantics and no-confirmation statement.
- [ ] **Placeholder/type scan:** Reject unresolved placeholders and mismatched field/function names in implementation or artifacts. The plan's named schemas, paths and status values are fixed; implementation-specific helper names may differ only if the documented outputs/invariants remain identical.
- [ ] **Safety scan:** Confirm no task edits A1/production, opens raw/official/external data, deserializes old models, reruns a candidate model, uses outer outcomes to change a parameter, or creates a second A2 study directory.

The next conversation may execute this plan under the user's 2026-09-23 authorization **only within these bounds**. A successful A2 development result is not an independent confirmation or Formal G1 remedy.
