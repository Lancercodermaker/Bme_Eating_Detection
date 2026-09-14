# High-F1 Event Stack Execution Log

## Worktree preflight

- plan revision: `7ff07afe189f3e493f62a18a710d08c75d2321c6`
- frozen baseline: `6d906ce`
- branch: `codex/high-f1-event-stack-execution`
- worktree: `E:/bme_compitition/.worktrees/high-f1-event-stack-execution`
- project: `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`
- repository policy: `E:/bme_compitition/.worktrees/` is ignored by `.gitignore`
- ancestry check: `6d906ce` is an ancestor of `7ff07af`
- initial worktree status: clean
- project command directory: the nested `bme_compitition_next` directory above
- raw data policy: no raw data copied or modified

## Baseline verification

- first baseline attempt: classified `ENVIRONMENT`; Python 3.10 lacked `torch` and the existing Transformer tests failed during collection
- remediation: installed project dependencies from `pyproject.toml` and CPU `torch`; no repository files were changed by setup
- fresh baseline result: `python -m pytest -q` -> `47 passed in 11.78s`

## Execution record

This log is updated at each task and milestone. Formal gate failures must record their failure classification, next action, continuation decision and architecture-reopen decision before the next formal command is started.

## Task 1 / M0

- input: reviewed design and plan contracts for config, schemas, artifacts and telemetry
- output: local-window config defaults, resource/schema fields, typed data rows, lifecycle telemetry and checksummed run artifacts
- acceptance: focused tests `13 passed`; full suite `57 passed`
- failure classification: `NONE`
- next action: proceed to Task 2 manifest/raw audit
- continue local optimization: no
- architecture reopen: no

## Task 2 / M1

- input: target-train manifest indexes and bounded raw sensor TSV reads
- output: explicit manifest status records, malformed-row audit with source row numbers, and diagnostic audit CLI
- acceptance: focused tests `11 passed`; full suite `59 passed`; `artifacts/m1-audit.json` reports `1161` discovered files and `2` bounded raw files audited
- observed evidence: `malformed_rows=0`, `duplicate_count=1672486`, `dropped_timestamp_count=145485`; diagnostic metadata includes `run_id=m1-audit`, `diagnostic_only=true`, `telemetry_scope=diagnostic`
- failure classification: `NONE`
- next action: proceed to Task 2b trusted baseline sentinel
- continue local optimization: no
- architecture reopen: no

## Task 2b / trusted baseline sentinel

- input: M1 diagnostic manifest audit and the reviewed preflight M0 reference
- output: `artifacts/m0-trusted-baseline/split-manifest.json`, `metrics.json` and `manifest.json`
- acceptance: focused test `1 passed`; full suite `60 passed`; strict CLI result `pass`
- frozen evidence: event F1 `0.17284`, strict IoU `> 0.25` one-to-one matching, `target_only_train`, participant-frozen seed `20260910`, valid fraction `0.20`
- failure classification: `NONE`
- next action: proceed to Task 3 hard-gap-aware timebase
- continue local optimization: no
- architecture reopen: no

## Task 3 / hard-gap-aware timebase

- input: synthetic duplicate/gap timestamp series and dense-window fixtures
- output: `hard_gap_mask`, `interpolated_mask`, `segment_id`, and segment-safe window filtering
- acceptance: focused tests `9 passed`; full suite `62 passed`
- failure classification: `NONE`
- next action: proceed to Task 4 feature and cache contracts
- continue local optimization: no
- architecture reopen: no

## Task 4 / versioned local cache

- input: hard-gap-aware regularized sessions, 15 s / 7.5 s window contract, IMU feature extractor
- output: finite `[W,111]` feature contract, schema-versioned candidate cache, local-window candidate runner
- acceptance: focused tests `11 passed`; full suite `67 passed`; cache round-trip preserves float32 features, int8 labels, interval arrays and metadata validation
- diagnostic smoke: `artifacts/m2-smoke.json` was written with `run_id=m2-smoke`, `diagnostic_only=true`, `telemetry_scope=diagnostic`; the 4-file/2-participant bounded subset had single-class train labels and was classified `DATA/PIPELINE`
- minimal deviation: diagnostic-only `--max-files-per-participant 2` uses a total bounded sample across two participants so the smoke cannot expand to all large raw files; formal runs do not use this cap
- failure classification: `DATA/PIPELINE` for diagnostic smoke only; formal M2 contract tests pass
- next action: proceed to formal G1 candidate coverage; do not treat smoke metrics as formal evidence
- continue local optimization: no
- architecture reopen: no
