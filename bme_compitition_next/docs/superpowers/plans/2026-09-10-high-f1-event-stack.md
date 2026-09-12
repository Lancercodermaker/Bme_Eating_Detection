# High-F1 Event Stack Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Build a reproducible, event-centric eating detector whose local selection metric is participant-frozen event-level F1 under the official strict `IoU > 0.25` rule.

**Architecture:** Read-only raw-data adapter -> timestamp de-duplication and regular IMU timebase -> dense 240-second candidate windows -> high-recall candidate model -> event-level verifier -> constrained eventizer -> official event evaluator. The first spike implements and validates the data/metric contract before any neural architecture search.

**Tech Stack:** Python 3.10, NumPy, pandas, SciPy, pytest, PyTorch for later neural components, and a tree-based verifier for the first strong baseline. Raw data remains outside the repository and is referenced through an explicit configuration file.

## Execution rules

- Use TDD for production Python: write the failing test, run it and record the failure, then implement the smallest change, then run the focused and full tests.
- Do not read official `test` labels for model selection or error analysis.
- Do not treat raw TSV rows as equally spaced samples; all windows must be derived from de-duplicated timestamps and explicit quality masks.
- Every experiment writes a config, split manifest, prediction event table, and metrics JSON.
- Work only under `E:\bme_compitition\bme_compitition_next`; the original 93 GB data stays read-only.

## Task 1: Lock repository and configuration contracts

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\pyproject.toml`
- Create: `E:\bme_compitition\bme_compitition_next\configs\example.local.yaml`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\__init__.py`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\config.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_config.py`

1. Write tests that load an explicit raw-data root, reject a missing root, reject a path inside the repository, and preserve numeric window/coverage parameters.
2. Run `python -m pytest tests/test_config.py -q`; it must fail because the package/config loader does not exist.
3. Implement a small typed configuration loader without importing model code.
4. Run the focused test again; expected result is all config tests pass.

## Task 2: Implement the official event metric before modeling

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\metrics.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_metrics.py`

1. Add tests for exact boundary behavior: IoU `0.25` is not a match, IoU just above `0.25` is a match, one prediction cannot match two truths, and empty prediction/ground-truth sets produce correct counts.
2. Run `python -m pytest tests/test_metrics.py -q`; it must fail before implementation.
3. Implement interval IoU, deterministic one-to-one matching, event precision/recall/F1, and boundary MAE. Keep timestamps in integer milliseconds to avoid float boundary ambiguity.
4. Run the focused test and then `python -m pytest -q`; expected result is all current tests pass.

## Task 3: Reconstruct the sensor timebase with synthetic packet fixtures

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\data\__init__.py`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\data\timebase.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_timebase.py`

1. Create a fixture with repeated packet rows, zero PPG timestamps, unsorted rows, and a real IMU gap. Test that duplicate timestamps aggregate deterministically, zero timestamps become unavailable rather than time zero, and the gap is preserved.
2. Run `python -m pytest tests/test_timebase.py -q`; it must fail before implementation.
3. Implement a streaming-friendly parser boundary: packet aggregation is separate from regular-grid resampling; IMU and PPG have independent timestamp masks; no interpolation crosses a gap larger than the configured tolerance.
4. Run focused tests and inspect the fixture summary (unique timestamps, duplicate count, gaps, coverage).

## Task 4: Build labels and dense non-crossing candidate windows

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\data\labels.py`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\data\windows.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_windows.py`

1. Test interval-overlap labels, positive-window policy, strict negative-distance policy, minimum coverage, and rejection of windows crossing a gap.
2. Run `python -m pytest tests/test_windows.py -q`; it must fail before implementation.
3. Implement a configurable dense grid with default window `240 s`, step `15 s`, and coverage `0.8`; expose both overlap fraction and distance to the nearest ground-truth event.
4. Run focused tests and a synthetic candidate audit; expected output is deterministic window count and zero cross-gap windows.

## Task 5: Add raw-file audit and train-only manifest generation

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\audit.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\audit_dataset.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_audit.py`

1. Test that the audit reports duplicate timestamps, zero timestamps, modality coverage, gap distribution, and malformed-file counts without loading the full 93 GB dataset.
2. Run the focused test and make it fail before implementation.
3. Implement bounded sampling and file-level streaming using explicit paths. The command must accept a raw-data root and metadata paths; it must never infer paths from the current working directory.
4. Run the audit on one known train file and one known test file only for parser sanity. Run the full train manifest audit without consuming test labels.
5. Save JSON/CSV summaries under ignored `artifacts/` and compare against the preflight facts.

## Task 6: Establish the first high-recall candidate baseline

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\features.py`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\candidates.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\run_candidate_baseline.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_candidates.py`

1. Test feature extraction on a synthetic regular IMU signal and ensure it is invariant to duplicate packet rows after timebase reconstruction.
2. Run the focused test and observe the expected failure.
3. Implement IMU-only features and compare the default 240 s/15 s candidate grid with the controlled 15 s/7.5 s local grid. Keep all windows dense and valid; do not use GT-neighbor sampling.
4. Run both grids on the frozen development split and write candidate Recall, event-level metrics after a transparent eventizer, long-FP ratio, and participant distribution.
5. Kill this route if candidate Recall is below `0.90` or if the eventizer only works when GT-adjacent windows are used.

## Task 7: Add event-level verifier before neural architecture search

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\verifier.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\run_event_verifier.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_verifier.py`

1. Test candidate-context feature construction and no-leakage participant grouping.
2. Run the focused test and observe the expected failure.
3. Implement a tree-based event verifier using candidate shape, neighboring density, coverage, quality, and optional local sequence score. Keep threshold tuning inside the training fold.
4. Compare against the candidate-only baseline using the same frozen predictions and official metric. The verifier must reduce long FP without dropping candidate Recall below the gate.

## Task 8: Introduce TCN/long-context modeling as a controlled replacement

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\models\tcn.py`
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\models\dataset.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\train_tcn.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_tcn.py`

1. Test tensor shapes, causal/dilated receptive-field calculation, mask handling, and deterministic DataLoader seeding.
2. Run the focused test and observe the expected failure.
3. Implement a small TCN that scores the same dense 240-second candidates or produces candidate embeddings; do not make it the only detector.
4. Compare `candidate-only`, `candidate+tree-verifier`, and `candidate+TCN+tree-verifier` on the exact same split and candidate table.
5. Stop increasing TCN depth if validation event F1 or long-FP ratio does not improve for two bounded architecture changes.

## Task 8b: Validate a bounded lightweight Transformer context model

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\models\transformer.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\run_transformer_candidate.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_transformer.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_transformer_runner.py`

1. Use the same cached dense candidate tables and participant split as the TCN comparison.
2. Bound the model at `d_model=32`, two encoder layers, four heads, and sequence chunks of at most 128 windows.
3. Compare candidate-only event F1, candidate coverage, long FP, boundary MAE, and participant-level worst cases at the same eventizer settings.
4. Kill the route if candidate coverage is below the gate and threshold sensitivity cannot recover it; do not add the Transformer to the final verifier merely because training loss decreases.

## Task 9: Evaluate external pretraining as an isolated experiment

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\src\eating_event\external.py`
- Create: `E:\bme_compitition\bme_compitition_next\scripts\pretrain_external.py`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_external.py`

1. Add a test that external samples and target samples map to the same feature/timebase contract without mixing participant IDs.
2. Run the focused test and observe the expected failure.
3. Implement an opt-in FD-I/FD-II pretraining adapter; keep external data out of the target-only baseline and final submission until license/organizer confirmation is recorded.
4. Compare `target_only`, `external_pretrain -> target_finetune`, and only then `joint_train`; accept external data only if frozen event F1 improves without worsening participant worst-case F1, boundary MAE, or long FP.

**Current gate:** FD-I/FD-II signal archives are not present locally. The official archive is approximately 5.5 GB and carries CC-BY-NC-ND-4.0; full execution remains blocked until the organizer's external-data rule and the data-to-target contract are confirmed.

## Task 10: Reproducible report and final submission gate

**Files:**
- Create: `E:\bme_compitition\bme_compitition_next\scripts\evaluate.py`
- Create: `E:\bme_compitition\bme_compitition_next\docs\experiment-log.md`
- Test: `E:\bme_compitition\bme_compitition_next\tests\test_reproducibility.py`

1. Test that a saved config and prediction table reproduce the same metrics JSON.
2. Run the focused test and observe the expected failure.
3. Implement one-command evaluation that emits the complete metric bundle, split IDs, software versions, and data audit hash.
4. Run the full suite, a clean-room smoke run on synthetic data, and the final train-only audit.
5. Before any official submission, verify no test labels, GT-adjacent sampling, forbidden external data, or untracked large artifacts enter the package.
