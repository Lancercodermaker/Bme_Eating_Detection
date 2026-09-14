# High-F1 Event Stack Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将冻结的 target-only 15 s/7.5 s dense-window、HGB candidate scorer、participant-level OOF event verifier 和 constrained decoder 实现为可审计的正式 ML pipeline。

**Architecture:** 先修复 manifest、timebase、cache 和 OOF 数据契约，再执行 candidate coverage gate，随后训练 event verifier 并用 nested participant validation 选择 decoder 参数。外部数据、test truth、GT 邻域采样、跨 gap 插值和 all-participant OOF fallback 永远不属于本计划。

**Tech Stack:** Python 3.10+、NumPy、pandas、PyYAML、SciPy、scikit-learn、pytest；HGB 在 CPU 上运行；PyTorch/TCN 只保留为后续受控 candidate auxiliary，不是本计划的主实现。

---

## 执行边界

- 项目工作目录固定为 E:/bme_compitition/bme_compitition_next；Git 仓库根目录固定为 E:/bme_compitition。
- 原始数据目录只读，不能复制到工作区或加入 Git。
- 实现开始前必须从冻结提交 6d906ce 创建独立 worktree 和 codex/ 分支；master 只保存已冻结文档，不直接承载实现改动。
- 每个 task 先写 focused failing test，再实现最小改动，再运行 focused test 和全套测试。
- 每个 gate failure 必须写入 artifact 并停止当前 milestone；不得用随机换 seed 或手工改 threshold 掩盖失败。
- 正式验证禁止 max-files-per-participant；该参数只允许 smoke test。
- 当前旧计划 E:/bme_compitition/bme_compitition_next/docs/superpowers/plans/2026-09-10-high-f1-event-stack.md 保留为历史记录，本计划是当前冻结设计的执行计划。
- 本计划执行过程中不得调用外部数据适配器，不得读取 test truth，不得重新做开放式架构搜索。

Worktree preflight must verify that the existing repository policy ignores the worktree path, then verify that the plan revision descends from 6d906ce. The implementation worktree is a Git checkout at a path below the ignored directory, while every Python, pytest and project-relative Git command runs from its nested project directory:

~~~powershell
$repo = "E:\bme_compitition"
$project = "E:\bme_compitition\bme_compitition_next"
$worktree = "E:\bme_compitition\.worktrees\high-f1-event-stack-execution"
$worktreeProject = Join-Path $worktree "bme_compitition_next"
$ignoreProbe = ".worktrees/high-f1-event-stack-execution"
git -C $repo check-ignore -q $ignoreProbe
if ($LASTEXITCODE -ne 0) { throw "worktree path is not ignored by repository policy" }
$planRevision = git -C $project rev-parse HEAD
git -C $project merge-base --is-ancestor 6d906ce $planRevision
if ($LASTEXITCODE -ne 0) { throw "plan revision is not descended from 6d906ce" }
git -C $repo worktree add $worktree -b codex/high-f1-event-stack-execution $planRevision
if (-not (Test-Path (Join-Path $worktreeProject "pyproject.toml"))) { throw "nested project directory is missing" }
Set-Location $worktreeProject
if ((git rev-parse --show-toplevel) -ne ($worktree -replace '\\','/')) { throw "unexpected worktree root" }
if ((Get-Location).Path -ne (Resolve-Path $worktreeProject).Path) { throw "commands are not running from the project directory" }
~~~

After this command, all implementation commands run from `$worktreeProject`; worktree management alone uses `git -C $repo`. The original project checkout remains unchanged during implementation. Before Task 1, record the verified values of `planRevision`, `$worktree`, `$worktreeProject` and the clean status in the execution log.

## Adaptive Workflow execution contract

本计划采用以下固定路由：

~~~text
workflow_path: RESEARCH
execution_mode: INLINE
execution_backend: executing-plans
scope: target-only data-contract repair, formal coverage gate, OOF verifier and nested evaluation
budget: one bounded gate at a time; at most three materially different hypotheses for one unresolved failure
fallback: return to data/label/metric root-cause investigation
escalation: three causal hypotheses, five major experiments, leakage, plateau or hard resource limit
~~~

验证顺序固定为：

~~~text
dataset sanity
-> trusted baseline sentinel
-> pipeline sanity
-> small-set overfit
-> formal candidate coverage
-> OOF verifier
-> nested event evaluation
-> full target-only scale
-> submission isolation
~~~

Telemetry 的范围必须明确区分正式 run 和诊断 run。正式 G1 以及 M3–M7 的 formal run 必须使用统一的 `RunArtifact.record_event`，并记录 `run_start`、`gate_result` 和 `run_end`；只有实际触发 adaptive-workflow circuit breaker 时才记录 `escalation`。Task 2 的 dataset audit、Task 4 的 bounded smoke cache 和 Task 7 的 verifier smoke 都是 `diagnostic_only`，不属于 formal telemetry 生命周期；它们只在各自的 audit/smoke JSON 中写入 `run_id`、`diagnostic_only=true`、命令、状态、失败分类和开始/结束时间，不得被误当成正式 gate 结果。正式 run 的 host 若没有独立 telemetry recorder，则由 run artifact 写入这些事件，不能伪称已有外部 telemetry。

## 文件结构

| 文件 | 责任 |
|---|---|
| src/eating_event/config.py | resolved config、资源预算和 schema version |
| src/eating_event/schemas.py | manifest、candidate、prediction 和 artifact 类型 |
| src/eating_event/data/manifest.py | participant/session/file discovery 和显式状态 |
| src/eating_event/data/raw.py | bounded raw TSV reader、坏行统计、ACC/GYRO 解析 |
| src/eating_event/data/timebase.py | 去重、10 Hz regularization、hard-gap metadata |
| src/eating_event/data/windows.py | segment-aware dense window generation |
| src/eating_event/data/labels.py | window label 和 ignore policy |
| src/eating_event/features.py | 111 维 IMU feature contract |
| src/eating_event/cache.py | versioned candidate-table serialization |
| src/eating_event/candidates.py | candidate table、HGB candidate scorer、OOF scores |
| src/eating_event/verifier.py | event candidate features、HGB verifier、decoder |
| src/eating_event/metrics.py | strict IoU、one-to-one match 和 metric aggregation |
| src/eating_event/evaluation.py | nested split、inner selection、outer reporting |
| src/eating_event/coverage.py | formal G1 candidate coverage and frozen quantile selection |
| src/eating_event/artifacts.py | run directory、checksums、resource logging |
| src/eating_event/telemetry.py | run_start、gate_result、escalation、run_end schema and validation helpers; writes are owned by RunArtifact |
| src/eating_event/full_run.py | full target-only scale orchestration and cache recovery |
| scripts/audit_dataset.py | manifest/timebase audit CLI |
| scripts/run_trusted_baseline.py | materialize and validate the frozen M0 trusted-baseline sentinel |
| scripts/run_candidate_baseline.py | dense cache 和 candidate coverage CLI |
| scripts/run_candidate_coverage.py | formal outer-fold G1 coverage CLI |
| scripts/run_event_verifier.py | OOF verifier 和 nested validation CLI |
| scripts/run_full_target_only.py | M6 full target-only checkpoints, OOF verifier and resource report |
| scripts/run_submission.py | load M6 target-only checkpoints and serialize test predictions |
| tests/test_trusted_baseline.py | frozen M0 baseline value/split/source contract |
| tests/test_*.py | contract、leakage、metric、resource 和 runner regression tests |

### Task 1: Freeze public config and data schemas

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/config.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/schemas.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/telemetry.py
- Modify: E:/bme_compitition/bme_compitition_next/configs/example.local.yaml
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_config.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_schemas.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_artifacts.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_telemetry.py

- [ ] **Step 1: Write failing schema tests**

~~~python
def test_config_rejects_raw_root_inside_repository(tmp_path):
    repo = tmp_path / "repo"
    raw = repo / "raw"
    metadata = tmp_path / "metadata"
    repo.mkdir()
    raw.mkdir()
    metadata.mkdir()
    path = tmp_path / "config.yaml"
    path.write_text(
        f"repository_root: {repo}\nraw_data_root: {raw}\nmetadata_root: {metadata}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inside repository"):
        load_config(path)


def test_prediction_row_rejects_bounds_outside_session():
    with pytest.raises(ValueError, match="session"):
        PredictionRow(
            participant_id="p",
            session_id="s",
            start_ms=0,
            end_ms=1000,
            session_start_ms=100,
            session_end_ms=900,
        )


def test_formal_run_artifact_requires_core_lifecycle_events(tmp_path):
    run = RunArtifact(tmp_path, "g1")
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G1", "result": "pass", "failure_class": None})
    with pytest.raises(ValueError, match="run_end"):
        run.finalize()
~~~

- [ ] **Step 2: Run focused tests and confirm failure**

~~~text
python -m pytest tests/test_config.py tests/test_schemas.py tests/test_artifacts.py tests/test_telemetry.py -q
~~~

Expected: FAIL because the resource fields, schema dataclasses, formal-run artifact and telemetry lifecycle do not exist.

- [ ] **Step 3: Add the typed contracts**

Extend ProjectConfig with:

~~~python
feature_schema_version: str = "imu_stats_v1"
label_schema_version: str = "window_event_labels_v1"
raw_chunk_size: int = 200000
host_memory_fraction: float = 0.60
gpu_memory_limit_gb: float = 7.0
audit_timeout_seconds: int = 1800
cache_timeout_seconds: int = 21600
fit_timeout_seconds: int = 7200
~~~

Define frozen dataclasses ManifestRow, GapSummary, CandidateRow, EventCandidateRow and PredictionRow. PredictionRow validates end_ms > start_ms and session_start_ms <= start_ms < end_ms <= session_end_ms. Candidate labels use int8 values 1, 0 and -1.

Create the initial `RunArtifact`/`TelemetryEvent` foundation here, before any formal G1 command can run. `RunArtifact.record_event(event_type, payload)` is the only writer; it injects the resolved run context and writes `telemetry.jsonl`. `finalize()` must require `run_start`, `gate_result` and `run_end`, allow `escalation` only when `circuit_breaker_fired=true`, and include the telemetry checksum in the manifest. Task 8 extends this foundation with the complete artifact payload and checkpoint rules; it must modify these files rather than recreate them.

Change configs/example.local.yaml so the formal defaults are window_seconds=15 and step_seconds=7.5. Add explicit coarse_window_seconds=240, coarse_step_seconds=15 and use_coarse_context=false fields; coarse context is disabled unless an inner-validation experiment enables it.

- [ ] **Step 4: Run focused and full tests**

~~~text
python -m pytest tests/test_config.py tests/test_schemas.py tests/test_artifacts.py tests/test_telemetry.py -q
python -m pytest -q
~~~

Expected: all focused tests and all existing tests pass.

- [ ] **Step 5: Commit M0**

~~~text
git add src/eating_event/config.py src/eating_event/schemas.py src/eating_event/artifacts.py src/eating_event/telemetry.py configs/example.local.yaml tests/test_config.py tests/test_schemas.py tests/test_artifacts.py tests/test_telemetry.py
git commit -m "feat: freeze pipeline data schemas and resource config"
~~~

Gate: M0 passes only when interval semantics, array dtypes, resource limits and schema versions are explicit.

### Task 2: Make manifest discovery and raw parsing auditable

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/manifest.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/raw.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/audit.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/audit_dataset.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_manifest.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_raw.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_audit.py

- [ ] **Step 1: Write failing provenance tests**

~~~python
def test_bad_index_row_is_reported(tmp_path):
    raw_root = make_raw_root_with_index_row(tmp_path, start_time="bad")
    records, audit = discover_raw_files_with_audit(raw_root)
    assert records == []
    assert audit.invalid_index_rows == 1
    assert audit.status_counts["skipped_invalid_session"] == 1


def test_malformed_sensor_row_is_counted(tmp_path):
    path = write_sensor_file_with_one_malformed_data_row(tmp_path)
    result = read_imu_tsv_with_audit(path)
    assert result.audit.malformed_rows == 1
    assert result.audit.valid_rows > 0
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_manifest.py tests/test_raw.py tests/test_audit.py -q
~~~

Expected: FAIL because discovery has no audit return value and raw parsing silently skips malformed lines.

- [ ] **Step 3: Return explicit manifest audit records**

Change discovery to return:

~~~python
tuple[list[RawFileRecord], ManifestAudit]
~~~

Record missing index files, malformed index rows, missing session folders, invalid time ranges, and skipped sensor files. Keep participant test excluded unless include_test=True. Every former bare continue must produce one status record.

- [ ] **Step 4: Replace silent bad-line handling**

Keep bounded chunks of raw rows and count malformed rows with their source row number and parser reason. Valid rows remain usable. Raise RawFileFormatError only for invalid headers, undecodable files, or files with no valid required ACC/GYRO timestamps.

- [ ] **Step 5: Run focused tests and the parser sentinel**

~~~text
python -m pytest tests/test_manifest.py tests/test_raw.py tests/test_audit.py -q
python scripts/audit_dataset.py --config configs/example.local.yaml --limit-files 2 --output artifacts/m1-audit.json --run-id m1-audit --diagnostic-only
~~~

Expected: focused tests pass; audit JSON contains `status_counts`, `malformed_rows`, `duplicate_count`, `dropped_timestamp_count`, `run_id="m1-audit"`, `diagnostic_only=true`, `telemetry_scope="diagnostic"`, `status`, `failure_class`, `started_at` and `ended_at`. This artifact is dataset evidence only and is not a formal telemetry run.

- [ ] **Step 6: Commit M1 parser changes**

~~~text
git add src/eating_event/data/manifest.py src/eating_event/data/raw.py src/eating_event/audit.py scripts/audit_dataset.py tests/test_manifest.py tests/test_raw.py tests/test_audit.py
git commit -m "feat: make manifest and raw parsing auditable"
~~~

Gate: stop M1 if any file or malformed row lacks an explicit status.

### Task 2b: Materialize the trusted baseline sentinel before pipeline work

This is the required bridge between dataset sanity and the pipeline-sanity/timebase tasks. It does not tune a new model and does not read test truth; it turns the preflight M0 reference into a self-contained, hashable artifact that G4 must consume.

**Files:**

- Create: E:/bme_compitition/bme_compitition_next/scripts/run_trusted_baseline.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_trusted_baseline.py

- [ ] **Step 1: Write the failing baseline-contract test**

~~~python
def test_trusted_baseline_artifact_freezes_value_split_and_metric_source(tmp_path):
    artifact = build_trusted_baseline_artifact(
        output_dir=tmp_path,
        audited_target_participants=("p-01", "p-02", "p-03", "p-04", "p-05"),
        baseline_id="m0-q50-groupnorm",
        split_seed=20260910,
        valid_fraction=0.20,
        expected_event_f1=0.17284,
    )
    assert artifact["schema_version"] == "trusted_baseline_v1"
    assert artifact["baseline_id"] == "m0-q50-groupnorm"
    assert artifact["metric"]["name"] == "event_f1"
    assert artifact["metric"]["value"] == pytest.approx(0.17284, abs=1e-5)
    assert artifact["metric"]["matching"] == "strict_iou_gt_0.25_one_to_one"
    assert artifact["metric"]["source_document"] == "docs/preflight-2026-09-10.md"
    assert artifact["split"] == {
        "strategy": "participant_frozen",
        "seed": 20260910,
        "valid_fraction": 0.20,
        "participant_order": "sorted_unique_target_train",
        "manifest": "split-manifest.json",
    }
~~~

- [ ] **Step 2: Run the focused sentinel test and confirm failure**

~~~text
python -m pytest tests/test_trusted_baseline.py -q
~~~

Expected: FAIL because the baseline artifact builder and its frozen split/metric schema do not exist.

- [ ] **Step 3: Implement the frozen baseline sentinel**

Implement `build_trusted_baseline_artifact(output_dir, audited_target_participants, baseline_id, split_seed, valid_fraction, expected_event_f1)` and the CLI with these exact rules:

1. Resolve only eligible target-train participants from the audited manifest, sort their IDs lexicographically, and call the existing deterministic `split_participants(..., valid_fraction=0.20, seed=20260910)` exactly once. Write `artifacts/m0-trusted-baseline/split-manifest.json` with `schema_version="participant_split_v1"`, `strategy="participant_frozen"`, `seed=20260910`, `valid_fraction=0.20`, the exact sorted `participant_ids`, `train_participant_ids`, `valid_participant_ids`, `participant_order_sha256` and `split_sha256`; that file is the authoritative split, not an implicit random split.
2. Write `artifacts/m0-trusted-baseline/metrics.json` with `schema_version="trusted_baseline_v1"`, `baseline_id="m0-q50-groupnorm"`, `data_scope="target_only_train"`, `split_manifest="split-manifest.json"`, `split_manifest_sha256` equal to the sibling split artifact, and this exact nested metric object: `{"name":"event_f1","value":0.17284,"matching":"strict_iou_gt_0.25_one_to_one","source_document":"docs/preflight-2026-09-10.md","source_locator":"Baseline / M0 q50 + GroupNorm"}`. The runner must reject a different value, split seed, valid fraction, metric rule, or data scope; it must never substitute an M5 result or a newly sampled split.
3. Write `artifacts/m0-trusted-baseline/manifest.json` containing the config hash, audited target manifest hash, split-manifest hash, metrics hash, `data_scope="target_only_train"`, `test_truth_references=[]`, `external_data_references=[]` and `result="pass"`. A missing source/contract field produces `result="fail"` and blocks Task 3 and all later model work.

- [ ] **Step 4: Run the sentinel and the full existing suite**

~~~text
python -m pytest tests/test_trusted_baseline.py -q
python -m pytest -q
python scripts/run_trusted_baseline.py --config configs/example.local.yaml --audit artifacts/m1-audit.json --baseline-id m0-q50-groupnorm --split-seed 20260910 --valid-fraction 0.20 --expected-event-f1 0.17284 --output-dir artifacts/m0-trusted-baseline --strict
~~~

Expected: the artifact contains `split-manifest.json`, `metrics.json` and `manifest.json`, with `result="pass"` and `metric.value=0.17284`. Do not start Task 3 if the sentinel cannot prove the exact participant-frozen split, the official strict IoU rule or the preflight metric source.

- [ ] **Step 5: Commit M1 baseline sentinel**

~~~text
git add scripts/run_trusted_baseline.py tests/test_trusted_baseline.py
git commit -m "test: freeze trusted baseline sentinel"
~~~

Gate: the trusted baseline consumed by G4 is exactly `artifacts/m0-trusted-baseline/metrics.json:$.metric.value`, with value `0.17284`; its split is exactly the sibling `split-manifest.json` generated by seed `20260910` and valid fraction `0.20`. No G4 command may use a hard-coded scalar or any outer metric as a replacement.

### Task 3: Add hard-gap metadata and segment-aware timebase

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/timebase.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/raw.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/windows.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/labels.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_timebase.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_windows.py

- [ ] **Step 1: Write failing hard-gap tests**

~~~python
def test_regularized_series_keeps_large_gap_invalid():
    series = aggregate_timestamp_rows(
        [1000, 1100, 5000, 5100],
        [[1.0], [2.0], [3.0], [4.0]],
    )
    result = regularize_series(series, grid_hz=10, max_gap_seconds=2.0)
    assert result.hard_gap_mask.any()
    assert not result.valid_mask[20:40].any()


def test_window_generation_rejects_hard_gap():
    timestamps = np.arange(0, 10000, 100, dtype=np.int64)
    valid = np.ones(timestamps.size, dtype=bool)
    hard_gap = np.zeros(timestamps.size, dtype=bool)
    hard_gap[40] = True
    records = generate_dense_windows(
        timestamps,
        valid,
        hard_gap_mask=hard_gap,
        grid_hz=10,
        window_seconds=3,
        step_seconds=1,
        min_coverage=0.8,
        max_gap_seconds=2.0,
    )
    assert all(not record.crosses_hard_gap for record in records)
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_timebase.py tests/test_windows.py -q
~~~

Expected: FAIL because RegularizedSeries has no hard-gap metadata and window generation has no hard-gap argument.

- [ ] **Step 3: Extend RegularizedSeries**

Add exact fields:

~~~python
hard_gap_mask: np.ndarray
interpolated_mask: np.ndarray
segment_id: np.ndarray
~~~

Build segment_id from raw adjacent timestamp differences greater than max_gap_seconds. Leave the intervening grid invalid. Combine ACC and GYRO hard-gap masks with logical OR for the IMU contract.

- [ ] **Step 4: Enforce segment-aware windows**

Add hard_gap_mask and segment_id to generate_dense_windows. Reject a window containing a hard-gap marker, more than one segment_id, coverage below min_coverage, or an invalid run longer than max_gap_seconds times grid_hz. Preserve the existing positive, negative and ignore label rules.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_timebase.py tests/test_windows.py -q
python -m pytest -q
~~~

Expected: all tests pass and no synthetic window crosses a hard gap.

- [ ] **Step 6: Commit M1 timebase changes**

~~~text
git add src/eating_event/data/timebase.py src/eating_event/data/raw.py src/eating_event/data/windows.py src/eating_event/data/labels.py tests/test_timebase.py tests/test_windows.py
git commit -m "feat: enforce hard-gap-aware timebase and windows"
~~~

Gate: no feature extraction starts until the hard-gap regression tests pass.

### Task 4: Version feature/cache contracts and switch the formal grid to local windows

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/features.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/candidates.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/cache.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_candidate_baseline.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_candidates.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_cache.py

- [ ] **Step 1: Write failing feature/cache tests**

~~~python
def test_imu_feature_schema_has_111_finite_values():
    values = np.ones((150, 6), dtype=np.float32)
    vector = extract_imu_features(values, np.ones(150, dtype=bool))
    assert len(vector.names) == 111
    assert vector.values.shape == (111,)
    assert np.isfinite(vector.values).all()


def test_cache_key_changes_with_feature_schema_version():
    first = build_cache_key("abc", 15.0, 7.5, "imu_stats_v1", "labels_v1")
    second = build_cache_key("abc", 15.0, 7.5, "imu_stats_v2", "labels_v1")
    assert first != second
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_candidates.py tests/test_cache.py -q
~~~

Expected: FAIL because cache.py and schema-versioned cache keys do not exist.

- [ ] **Step 3: Implement the versioned cache API**

Add these functions with concrete behavior:

~~~python
def build_cache_key(
    source_fingerprint: str,
    window_seconds: float,
    step_seconds: float,
    feature_schema_version: str,
    label_schema_version: str,
) -> str:
    return sha256(
        "|".join(
            [
                source_fingerprint,
                str(window_seconds),
                str(step_seconds),
                feature_schema_version,
                label_schema_version,
            ]
        ).encode("utf-8")
    ).hexdigest()
~~~

Add save_candidate_table and load_candidate_table. Persist float32 features, int8 labels, int64 starts/ends, float32 coverage, int32 invalid runs, participant/session identifiers, feature names and metadata. Reject a cache when expected metadata differs.

- [ ] **Step 4: Make local windows the formal default**

Set formal config and configs/example.local.yaml to window_seconds=15 and step_seconds=7.5. Pass hard_gap_mask and segment_id into window generation. Keep coarse_window_seconds=240 and coarse_step_seconds=15 only behind use_coarse_context=false. Process one session at a time.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_candidates.py tests/test_cache.py -q
python -m pytest -q
~~~

Expected: all tests pass; cache round-trip preserves schema, shape and labels exactly.

- [ ] **Step 6: Run the bounded smoke cache**

~~~text
python scripts/run_candidate_baseline.py --config configs/example.local.yaml --cache-dir artifacts/m2-smoke-cache --output artifacts/m2-smoke.json --max-files-per-participant 2 --run-id m2-smoke --diagnostic-only
~~~

The command must write `run_id="m2-smoke"`, `diagnostic_only=true`, `telemetry_scope="diagnostic"`, `status`, `failure_class`, `started_at` and `ended_at` in `artifacts/m2-smoke.json`. It must label the run smoke-only and must not treat its metrics as formal evaluation or as a formal telemetry lifecycle.

- [ ] **Step 7: Commit M2 cache changes**

~~~text
git add src/eating_event/features.py src/eating_event/candidates.py src/eating_event/cache.py scripts/run_candidate_baseline.py tests/test_candidates.py tests/test_cache.py
git commit -m "feat: version dense local candidate cache"
~~~

Gate: M2 cannot proceed unless feature width is 111, cache metadata validates, and candidate coverage is emitted.

### Task 5: Execute the formal G1 candidate-coverage gate before verifier work

**Files:**

- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/coverage.py
- Create: E:/bme_compitition/bme_compitition_next/scripts/run_candidate_coverage.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_coverage.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/evaluation.py

- [ ] **Step 1: Write failing formal coverage tests**

~~~python
def test_formal_coverage_rejects_file_limits():
    with pytest.raises(ValueError, match="formal"):
        CoverageRunConfig(
            formal=True,
            max_files_per_participant=2,
        )


def test_coverage_report_contains_fold_and_participant_results():
    report = CandidateCoverageReport(
        gate_id="G1",
        fold_results=(
            FoldCoverageResult(
                fold_id="outer-0",
                pooled_recall=0.95,
                participant_recall={"p1": 1.0},
            ),
        ),
    )
    assert report.gate_id == "G1"
    assert report.fold_results[0].pooled_recall == pytest.approx(0.95)
    assert report.fold_results[0].participant_recall["p1"] == pytest.approx(1.0)


def test_candidate_quantile_selection_is_frozen_and_deterministic():
    results = (
        QuantileResult(quantile=0.70, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=30),
        QuantileResult(quantile=0.80, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=20),
        QuantileResult(quantile=0.90, pooled_recall=0.95, worst_participant_recall=0.80, candidate_count=20),
    )
    assert select_candidate_quantile(results).quantile == pytest.approx(0.90)
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_coverage.py -q
~~~

Expected: FAIL because CoverageRunConfig, CandidateCoverageReport and the formal coverage runner do not exist.

- [ ] **Step 3: Implement deterministic outer/inner participant fold creation**

Add ParticipantFold, build_outer_folds and build_inner_folds to evaluation.py. Sort participant identifiers, apply the supplied seed, assign every participant to exactly one outer validation fold, and keep all sessions of a participant together. No test participant or test metadata is accepted by these functions.

Freeze the G1 candidate-quantile protocol in code and in the formal report:

~~~python
G1_CANDIDATE_QUANTILE_GRID = (0.70, 0.80, 0.90)
G1_CANDIDATE_FUSE_GAP_MS = 300_000
G1_COVERAGE_THRESHOLD = 0.90
~~~

For each outer fold, run the following nested sequence for every quantile in the frozen grid: fit the candidate scorer on inner-train participants only; derive that fit's score threshold from the inner-train participant score distribution only; score inner-valid participants only; and evaluate candidate coverage on inner-valid sessions only. Aggregate the inner-fold results and select by this exact lexicographic key, in descending/ascending order as shown: highest pooled candidate coverage recall, highest worst event-bearing-participant recall, lowest total candidate interval count, highest quantile. The final key is `(pooled_recall, worst_participant_recall, -candidate_count, quantile)`, and ties are resolved by the fixed grid order. Only after this selection, refit the candidate scorer on the complete outer-train participants and derive its threshold from the complete outer-train score distribution. Use that refit exactly once to score outer-valid sessions for the G1 report; outer-valid sessions never affect fitting, threshold derivation, quantile selection or any other decision. A change to the grid, metric order, fuse gap or threshold requires a new design review.

- [ ] **Step 4: Implement formal coverage evaluation**

Implement CandidateCoverageReport, FoldCoverageResult and run_candidate_coverage. The command must:

1. discover all eligible target train sessions;
2. reject max-files-per-participant when formal=True;
3. build outer participant folds;
4. for every inner fold, fit HGB candidate scorer only on inner-train participants and derive its threshold only from inner-train scores;
5. score inner-valid participants, evaluate the frozen quantile grid there, and select the quantile using only aggregated inner-valid results;
6. refit HGB candidate scorer once on complete outer-train participants after selection and derive its threshold only from complete outer-train scores;
7. use that refit to score every eligible outer-valid session exactly once;
8. build candidate event intervals with candidate_fuse_gap=300 seconds and calculate pooled and per-participant candidate coverage;
9. write fold and participant reports even when the gate fails;
10. never fit an event verifier.

Use these output files:

~~~text
artifacts/g1-candidate-coverage.json
artifacts/g1-candidate-coverage-by-fold.json
artifacts/g1-candidate-coverage-by-participant.json
artifacts/g1-candidate-coverage-telemetry.jsonl
~~~

The formal runner writes `run_start` before discovery, a `gate_result` after coverage is computed, an `escalation` only when the adaptive-workflow circuit breaker is reached, and `run_end` on pass or classified failure. The three coverage reports and the telemetry file must be written before a nonzero G1 exit.

- [ ] **Step 5: Re-run coverage tests after implementation**

~~~text
python -m pytest tests/test_coverage.py -q
python -m pytest -q
~~~

Expected: all coverage contract tests and the complete pre-G1 test suite pass. Do not start the formal G1 command when either command fails.

- [ ] **Step 6: Enforce the G1 gate**

The command exits nonzero after writing the report when any outer fold has pooled candidate coverage recall below 0.90. A first failure is classified as DATA/PIPELINE, CONFIGURATION or UNKNOWN according to the audit evidence. ARCHITECTURE is allowed only after three materially different causal hypotheses fail across multiple clean participant-frozen folds.

- [ ] **Step 7: Run the formal coverage command**

~~~text
python scripts/run_candidate_coverage.py --config configs/example.local.yaml --output artifacts/g1-candidate-coverage.json --cache-dir artifacts/g1-formal-cache --outer-folds 5 --formal
~~~

Expected: the command uses all eligible sessions, writes participant/fold coverage, and stops before any verifier training if G1 fails. The command is reached only after the Task 5 focused and full test rerun passes.

- [ ] **Step 8: Commit M2/G1 formal coverage gate**

~~~text
git add src/eating_event/coverage.py src/eating_event/evaluation.py scripts/run_candidate_coverage.py tests/test_coverage.py
git commit -m "feat: add formal candidate coverage gate"
~~~

Gate: Task 6 and all verifier tasks are blocked until every outer fold satisfies pooled candidate coverage recall >= 0.90 or an explicit architecture-level kill decision is recorded.

### Task 6: Reuse nested participant folds and complete official metrics

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/candidates.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/metrics.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/evaluation.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_metrics.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_evaluation.py

- [ ] **Step 1: Write failing fold and metric tests**

~~~python
def test_outer_folds_assign_each_participant_once():
    participants = [f"p{i:02d}" for i in range(10)]
    folds = build_outer_folds(participants, n_folds=5, seed=20260910)
    assigned = [
        participant
        for fold in folds
        for participant in fold.valid_participants
    ]
    assert sorted(assigned) == sorted(participants)
    assert len(assigned) == len(set(assigned))


def test_iou_equal_to_point_two_five_is_not_a_match():
    prediction = EventInterval(0, 1000)
    truth = EventInterval(600, 1600)
    assert interval_iou(prediction, truth) == pytest.approx(0.25)
    assert evaluate_events([prediction], [truth]).tp == 0


def test_unmatched_boundary_mae_is_none():
    metrics = evaluate_events(
        [EventInterval(0, 1000)],
        [EventInterval(5000, 6000)],
    )
    assert metrics.matched_count == 0
    assert metrics.start_mae_ms is None
    assert metrics.end_mae_ms is None


def test_boundary_mae_none_is_sorted_after_finite_value():
    assert boundary_mae_sort_key(900) < boundary_mae_sort_key(None)
    assert boundary_mae_sort_key(None) != boundary_mae_sort_key(0)
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_metrics.py tests/test_evaluation.py -q
~~~

Expected: FAIL because nested metric aggregation and missing-match boundary semantics do not exist; the participant-fold API is already created by the preceding G1 task and is reused here.

- [ ] **Step 3: Implement deterministic fold objects**

Reuse the `ParticipantFold`, `build_outer_folds` and `build_inner_folds` contracts created in Task 5. Extend them only if the focused tests expose a contract gap; do not create a second fold implementation. Define:

~~~python
@dataclass(frozen=True)
class ParticipantFold:
    fold_id: str
    train_participants: tuple[str, ...]
    valid_participants: tuple[str, ...]
~~~

Implement build_outer_folds and build_inner_folds by sorting participant IDs, applying the supplied NumPy seed, assigning each participant to exactly one validation fold, and deriving the complementary train set. Never read test metadata.

- [ ] **Step 4: Complete metric semantics**

Keep strict IoU > threshold and deterministic one-to-one matching. Add matched_count, truth_count and prediction_count. Use `None` for unmatched boundary MAE and never serialize or substitute it as numeric zero. Define `boundary_mae_sort_key(value)` so every finite value sorts before `None`, finite values sort ascending, and `None` sorts last; if all candidates have `None`, continue to the later deterministic tie-break without inventing a value. Add aggregate functions for micro, macro_all, macro_event_bearing and worst participant.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_metrics.py tests/test_evaluation.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 6: Commit M3 evaluation contracts**

~~~text
git add src/eating_event/candidates.py src/eating_event/metrics.py src/eating_event/evaluation.py tests/test_metrics.py tests/test_evaluation.py
git commit -m "feat: add nested participant evaluation contracts"
~~~

Gate: M3 is invalid if a participant appears in multiple outer validation folds or missing-match MAE is encoded as zero. This task may only run after the formal G1 coverage report has passed. Candidate quantile selection remains the frozen Task 5 inner-only protocol; Task 6 must not broaden its candidate set.

### Task 7: Remove OOF leakage and enforce verifier sample gates

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/candidates.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_event_verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_verifier.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_oof_leakage.py

- [ ] **Step 1: Write failing leakage tests**

~~~python
def test_oof_fit_participants_never_include_scored_participant():
    tables = make_two_class_tables_for_four_participants()
    result = participant_oof_candidate_scores_with_audit(
        tables,
        random_state=7,
        n_folds=4,
        max_iter=10,
    )
    for participant, rows in result.audit_by_participant.items():
        for row in rows:
            assert participant not in row.fit_participants
    assert result.fallback_participants == ()


def test_unavailable_oof_is_not_replaced_by_all_participant_model():
    tables = make_single_class_holdout_tables()
    result = participant_oof_candidate_scores_with_audit(
        tables,
        random_state=7,
        n_folds=2,
        max_iter=10,
    )
    assert result.unavailable_participants
    assert result.fallback_participants == ()
~~~

- [ ] **Step 2: Run focused tests and expose the current failure**

~~~text
python -m pytest tests/test_verifier.py tests/test_oof_leakage.py -q
~~~

Expected: the new tests fail against the current all-participant fallback.

- [ ] **Step 3: Replace fallback with explicit OOF status**

Define:

~~~python
@dataclass(frozen=True)
class OOFScoreAudit:
    scored_participant: str
    fit_participants: tuple[str, ...]
    fold_id: str
    threshold_reference: float
    status: str


@dataclass(frozen=True)
class OOFScoreResult:
    scores_by_participant: dict[str, tuple[np.ndarray, ...]]
    audit_by_participant: dict[str, tuple[OOFScoreAudit, ...]]
    unavailable_participants: tuple[str, ...]
    fallback_participants: tuple[str, ...]
~~~

For every held-out participant, fit only on the other outer-train participants. If the remaining labels are not binary, return OOF_UNAVAILABLE and no score. Never fit a model containing the scored participant as a fallback.

- [ ] **Step 4: Normalize score thresholds by fit distribution**

For each fitted candidate model, compute:

~~~python
threshold_reference = float(
    np.quantile(fit_participant_scores, candidate_quantile)
)
relative_score = raw_score - threshold_reference
~~~

Persist raw_score, threshold_reference, relative_score, fold_id, fit_participants and schema hash. Event verifier features use relative_score.

- [ ] **Step 5: Enforce verifier positive-sample gate**

Before fitting the verifier, require:

~~~python
if positive_count < 20 or positive_participant_count < 5:
    raise VerifierTrainingGateError(
        "verifier positive sample gate failed"
    )
~~~

Write the counts and the gate result to the run artifact.

- [ ] **Step 6: Run focused tests and verifier smoke**

~~~text
python -m pytest tests/test_verifier.py tests/test_oof_leakage.py -q
python scripts/run_event_verifier.py --config configs/example.local.yaml --cache-dir artifacts/m2-smoke-cache --cache-only --output artifacts/m3-smoke.json --run-id m3-smoke --diagnostic-only
~~~

Expected: focused tests pass. A smoke dataset that cannot meet the positive-sample gate exits with VerifierTrainingGateError and writes diagnostic-only `run_id`, `status`, `failure_class`, `started_at` and `ended_at`; it does not emit or stand in for the formal M3/M4 telemetry lifecycle.

- [ ] **Step 7: Commit M4 OOF changes**

~~~text
git add src/eating_event/candidates.py src/eating_event/verifier.py scripts/run_event_verifier.py tests/test_verifier.py tests/test_oof_leakage.py
git commit -m "fix: remove participant leakage from verifier OOF scores"
~~~

Gate: M4 fails closed when fallback_participants is non-empty or verifier positive samples are insufficient.

### Task 8: Make event decoding session-safe and persist artifacts

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/schemas.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/telemetry.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_event_verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_telemetry.py

- [ ] **Step 1: Write failing decoder and artifact tests**

~~~python
def test_decoder_does_not_merge_different_sessions():
    candidates = [
        EventCandidate(
            session_id="s1",
            segment_id=0,
            interval=EventInterval(0, 180000),
            session_start_ms=0,
            session_end_ms=180000,
            segment_start_ms=0,
            segment_end_ms=180000,
            features=np.zeros(16),
            label=0,
            candidate_status="negative",
            quality_status="audited",
            quality_flags=(),
            window_indices=(0,),
        ),
        EventCandidate(
            session_id="s2",
            segment_id=0,
            interval=EventInterval(200000, 380000),
            session_start_ms=200000,
            session_end_ms=380000,
            segment_start_ms=200000,
            segment_end_ms=380000,
            features=np.zeros(16),
            label=0,
            candidate_status="negative",
            quality_status="audited",
            quality_flags=(),
            window_indices=(1,),
        ),
    ]
    predictions = decode_event_candidates(
        candidates,
        np.array([0.9, 0.9]),
        threshold=0.5,
        min_duration_ms=180000,
        decode_fuse_gap_ms=600000,
    )
    assert len(predictions) == 2


def test_artifact_finalize_writes_manifest(tmp_path):
    run = RunArtifact(tmp_path, "m4")
    run.write_json("feature_schema.json", {"version": "imu_stats_v1", "width": 111})
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G1", "result": "pass", "failure_class": None})
    run.record_event("run_end", {"final_status": "pass"})
    manifest = run.finalize()
    assert manifest["schema_version"] == "artifact_v1"
    assert "feature_schema.json" in manifest["files"]


def test_event_candidate_may_start_at_segment_boundary():
    candidate = EventCandidate(
        session_id="s1",
        segment_id=0,
        interval=EventInterval(0, 1000),
        session_start_ms=0,
        session_end_ms=2000,
        segment_start_ms=0,
        segment_end_ms=2000,
        features=np.zeros(16),
        label=1,
        candidate_status="positive",
        quality_status="audited",
        quality_flags=(),
        window_indices=(0,),
    )
    assert candidate.interval.start_ms == candidate.segment_start_ms


def test_ignored_event_candidate_is_excluded_from_verifier_data():
    candidate = EventCandidate(
        session_id="s1",
        segment_id=0,
        interval=EventInterval(1000, 2000),
        session_start_ms=0,
        session_end_ms=3000,
        segment_start_ms=0,
        segment_end_ms=3000,
        features=np.zeros(16),
        label=-1,
        candidate_status="ignore",
        quality_status="hard_gap_boundary",
        quality_flags=("hard_gap_boundary",),
        window_indices=(0,),
    )
    assert candidate.is_ignored
    assert filter_verifier_candidates([candidate]) == []


@pytest.mark.parametrize(
    ("quality_status", "quality_flag"),
    [
        ("un_audited", "un_audited_quality"),
        ("audited", "label_uncertain"),
        ("hard_gap_boundary", "hard_gap_boundary"),
    ],
)
def test_each_ignore_source_is_excluded_from_verifier_data(quality_status, quality_flag):
    candidate = make_event_candidate(
        label=-1,
        candidate_status="ignore",
        quality_status=quality_status,
        quality_flags=(quality_flag,),
    )
    assert filter_verifier_candidates([candidate]) == []


def test_run_artifact_records_all_required_telemetry_events(tmp_path):
    run = RunArtifact(tmp_path, "m5")
    run.record_event("run_start", {"workflow_path": "RESEARCH"})
    run.record_event("gate_result", {"gate_id": "G1", "result": "pass", "failure_class": None})
    run.record_event(
        "escalation",
        {"reason": "resource threshold", "hypothesis_count": 3, "circuit_breaker_fired": True},
    )
    run.record_event("run_end", {"final_status": "failed"})
    run.finalize()
    events = [
        json.loads(line)
        for line in (run.root / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event_type"] for event in events] == [
        "run_start", "gate_result", "escalation", "run_end"
    ]


def test_escalation_requires_circuit_breaker_flag(tmp_path):
    run = RunArtifact(tmp_path, "m5-no-escalation")
    with pytest.raises(ValueError, match="circuit_breaker_fired"):
        run.record_event(
            "escalation",
            {"reason": "ordinary retry", "hypothesis_count": 1, "circuit_breaker_fired": False},
        )
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_verifier.py tests/test_artifacts.py tests/test_telemetry.py -q
~~~

Expected: FAIL because EventCandidate has no session/quality contract and the existing formal-run artifact foundation lacks the complete decoder, checkpoint and telemetry payload contract.

- [ ] **Step 3: Implement the complete EventCandidate boundary contract**

Extend EventCandidate with these exact fields:

~~~python
session_id: str
segment_id: int
interval: EventInterval
session_start_ms: int
session_end_ms: int
segment_start_ms: int
segment_end_ms: int
features: np.ndarray
label: int  # 1 positive, 0 negative, -1 ignore
candidate_status: Literal["positive", "negative", "ignore"]
quality_status: Literal["audited", "un_audited", "hard_gap_boundary"]
quality_flags: tuple[str, ...]
window_indices: tuple[int, ...]
~~~

Validate session_start_ms <= segment_start_ms <= interval.start_ms < interval.end_ms <= segment_end_ms <= session_end_ms. For a clean positive/negative candidate require `label` to be 1/0, `candidate_status` to agree with it, `quality_status="audited"` and `quality_flags=()`. For an ignored candidate require `label=-1`, `candidate_status="ignore"`, and at least one source flag from `un_audited_quality`, `hard_gap_boundary` or `label_uncertain`; `quality_status` identifies whether the boundary or quality region caused the ignore state. `quality_flags` is the bounded tuple of ignore-source flags, not a replacement for the upstream IMU/PPG quality mask. Group, sort and fuse only within the same session_id and segment_id. Apply candidate_fuse_gap before verifier scoring, apply verifier threshold and min_duration after scoring, then clip intervals to segment bounds. Decoder receives no truths. The inclusive `segment_start_ms <= interval.start_ms` boundary is intentional and must have a regression test.

Construct the status from the audited quality mask, segment/hard-gap metadata and label state. Retain ignored candidates in the audit artifact with their source fields, but make `filter_verifier_candidates` remove every candidate with `candidate_status="ignore"`, `label=-1`, `quality_status != "audited"` or non-empty `quality_flags` before verifier fitting, OOF scoring, metric evaluation or decoder input. Ignored candidates must not contribute to verifier positive/negative counts.

- [ ] **Step 4: Implement RunArtifact**

Define:

~~~python
class RunArtifact:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = (root / run_id).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.context = {
            "run_id": run_id,
            "project_id": "bme_compitition_next",
            "workflow_path": "RESEARCH",
            "execution_mode": "INLINE",
            "execution_backend": "executing-plans",
            "capability_tags": ["machine-learning", "data-contracts"],
            "loaded_profiles": ["Machine Learning"],
        }

    def write_json(self, relative_path: str, value: object) -> None:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("artifact path escapes run directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2), encoding="utf-8")
~~~

Add write_jsonl and finalize. `finalize()` writes checksums, git revision, environment versions and the artifact manifest; it rejects paths outside the run directory and rejects a run that lacks `run_start`, `gate_result` or `run_end`.

Extend the telemetry schema in `telemetry.py` and expose it through the existing `RunArtifact.record_event` API:

~~~python
class TelemetryEvent(TypedDict):
    schema_version: Literal["telemetry_v1"]
    event_id: str
    event_type: Literal["run_start", "gate_result", "escalation", "run_end"]
    timestamp: str
    run_id: str
    project_id: str
    workflow_path: str
    execution_mode: str
    execution_backend: str
    capability_tags: list[str]
    loaded_profiles: list[str]
    payload: dict[str, object]


class RunArtifact:
    def record_event(
        self,
        event_type: Literal["run_start", "gate_result", "escalation", "run_end"],
        payload: Mapping[str, object],
    ) -> None:
        validate_telemetry_payload(event_type, payload)
        event = build_telemetry_event(event_type, payload, run_context=self.context)
        self.write_jsonl("telemetry.jsonl", [event])
~~~

`RunArtifact.record_event` is the only telemetry-writing API. There is no module-level writer without an artifact root and run context. Every JSONL record contains `schema_version="telemetry_v1"`, an opaque unique `event_id`, a UTC ISO-8601 `timestamp`, `run_id`, `project_id`, `workflow_path="RESEARCH"`, `execution_mode="INLINE"`, `execution_backend="executing-plans"`, `capability_tags`, `loaded_profiles` and the bounded `payload`. `gate_result` requires `gate_id`, `result` and `failure_class` (use `None` when passing); `escalation` requires `reason`, `hypothesis_count` and `circuit_breaker_fired=true`, and is rejected when that flag is false; `run_end` requires `final_status`; `run_start` requires the resolved workflow and execution context. Reject duplicate event IDs. Payloads must not contain secrets, raw prompts, test truth, source data or unbounded command output. `RunArtifact.record_event` injects the run context so callers cannot omit it. The artifact manifest must include `telemetry.jsonl` and its checksum.

Add tests in `tests/test_telemetry.py` for the four event types, required-field validation, duplicate IDs, forbidden payload fields, and the finalize requirement. The artifact test must also verify that `telemetry.jsonl` is listed in the manifest.

- [ ] **Step 5: Emit complete metrics**

Update run_event_verifier.py to write micro, macro_all, macro_event_bearing, worst_participant, candidate coverage, long_fp_fraction, matched_count and split metadata. Write participant_metrics.json separately. Emit `run_start` before data work, one `gate_result` after each gate, `escalation` only when the adaptive-workflow circuit breaker is reached, and `run_end` on every normal or classified failure path. An unavailable external recorder is not an excuse to omit these events; the local artifact is the recorder.

- [ ] **Step 6: Run focused and full tests**

~~~text
python -m pytest tests/test_verifier.py tests/test_artifacts.py tests/test_telemetry.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 7: Commit M4 decoder/artifacts**

~~~text
git add src/eating_event/verifier.py src/eating_event/schemas.py src/eating_event/artifacts.py src/eating_event/telemetry.py scripts/run_event_verifier.py tests/test_verifier.py tests/test_artifacts.py tests/test_telemetry.py
git commit -m "feat: add session-safe decoder and complete run artifacts"
~~~

Gate: no inner parameter selection begins until candidate coverage, event metrics and artifact manifests are emitted.

### Task 9: Implement inner-only parameter selection and outer evaluation

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/evaluation.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_event_verifier.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_nested_evaluation.py

- [ ] **Step 1: Write failing inner-selection test**

~~~python
def test_outer_metrics_cannot_select_decoder_parameters():
    selected = select_inner_parameters(
        inner_results=[
            {"candidate_quantile": 0.80, "inner_event_f1": 0.40},
            {"candidate_quantile": 0.90, "inner_event_f1": 0.35},
        ]
    )
    assert selected.candidate_quantile == 0.80
    assert selected.selection_source == "inner"


def test_m5_selected_config_is_hashed_and_inner_only(tmp_path):
    artifact = write_selected_config_fixture(tmp_path)
    assert artifact["schema_version"] == "decoder_config_v1"
    assert artifact["selection_source"] == "inner"
    assert artifact["outer_metrics_used"] is False
    assert verify_config_hash(artifact)


def test_inner_selection_prefers_finite_boundary_mae_over_none():
    selected = select_inner_parameters(
        inner_results=[
            {"candidate_quantile": 0.80, "inner_event_f1": 0.40, "candidate_coverage": 0.90, "long_fp_fraction": 0.10, "boundary_mae_ms": None},
            {"candidate_quantile": 0.90, "inner_event_f1": 0.40, "candidate_coverage": 0.90, "long_fp_fraction": 0.10, "boundary_mae_ms": 900},
        ]
    )
    assert selected.candidate_quantile == 0.90


def test_final_config_aggregates_inner_results_without_outer_metrics(tmp_path):
    inner_results = write_complete_inner_results_fixture(tmp_path)
    selected = aggregate_inner_results(inner_results)
    assert selected["selection_source"] == "inner"
    assert selected["outer_metrics_used"] is False
    assert selected["inner_results_artifact"] == "inner-results.jsonl"
    assert selected["aggregate_inner_metrics"]["inner_result_count"] == 20
    assert "mean_inner_event_f1" in selected["aggregate_inner_metrics"]
    assert "mean_candidate_coverage" in selected["aggregate_inner_metrics"]
    assert "mean_long_fp_fraction" in selected["aggregate_inner_metrics"]
    assert "boundary_mae_missing_count" in selected["aggregate_inner_metrics"]
    assert "finite_boundary_mae_mean_ms" in selected["aggregate_inner_metrics"]


def test_m5_decoder_grid_is_finite_and_schema_complete():
    assert M5_DECODER_GRID == {
        "candidate_quantile": (0.70, 0.80, 0.90),
        "verifier_threshold": (0.10, 0.25, 0.50),
        "candidate_fuse_gap_ms": (300_000,),
        "decode_fuse_gap_ms": (300_000, 600_000, 900_000),
        "min_duration_ms": (120_000, 180_000, 240_000),
        "feature_variant": ("event_stats_v1",),
        "training_budget": ("budget_v1",),
    }
    assert M5_TRAINING_BUDGETS == {
        "budget_v1": {"candidate_max_iter": 100, "verifier_max_iter": 100}
    }
    assert len(expand_decoder_grid(M5_DECODER_GRID, M5_TRAINING_BUDGETS)) == 81


def test_g4_uses_three_seed_outer_metrics_and_trusted_baseline(tmp_path):
    baseline_path = tmp_path / "artifacts" / "m0-trusted-baseline" / "metrics.json"
    baseline_path.parent.mkdir(parents=True)
    split_path = baseline_path.parent / "split-manifest.json"
    split_path.write_text(
        json.dumps(
            {
                "schema_version": "participant_split_v1",
                "strategy": "participant_frozen",
                "seed": 20260910,
                "valid_fraction": 0.20,
                "participant_ids": ["p-01", "p-02", "p-03", "p-04", "p-05"],
                "train_participant_ids": ["p-01", "p-02", "p-03", "p-04"],
                "valid_participant_ids": ["p-05"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    split_hash = hashlib.sha256(split_path.read_bytes()).hexdigest()
    baseline_path.write_text(
        json.dumps(
            {
                "schema_version": "trusted_baseline_v1",
                "baseline_id": "m0-q50-groupnorm",
                "data_scope": "target_only_train",
                "split_manifest": "split-manifest.json",
                "split_manifest_sha256": split_hash,
                "split": {
                    "strategy": "participant_frozen",
                    "seed": 20260910,
                    "valid_fraction": 0.20,
                    "participant_order": "sorted_unique_target_train",
                    "manifest": "split-manifest.json",
                },
                "metric": {
                    "name": "event_f1",
                    "value": 0.17284,
                    "matching": "strict_iou_gt_0.25_one_to_one",
                    "source_document": "docs/preflight-2026-09-10.md",
                    "source_locator": "Baseline / M0 q50 + GroupNorm",
                },
            }
        ),
        encoding="utf-8",
    )
    outer_metrics = [
        {
            "seed": seed,
            "outer_fold_id": f"outer-{fold}",
            "event_f1": 0.20,
            "long_fp_fraction": 0.10,
            "boundary_mae_ms": 800_000,
        }
        for seed in (20260910, 20260911, 20260912)
        for fold in range(5)
    ]
    report = build_g4_report(
        outer_metrics=outer_metrics,
        trusted_baseline_path=baseline_path,
    )
    assert report["seed_ids"] == [20260910, 20260911, 20260912]
    assert report["trusted_baseline_artifact"] == "artifacts/m0-trusted-baseline/metrics.json"
    assert report["g4"]["median_outer_f1_pass"] is True
    assert report["g4"]["outer_splits_at_or_above_baseline"] >= 3
    assert report["g4"]["long_fp_fraction_max_pass"] is True
    assert report["g4"]["boundary_mae_ms_max_pass"] is True
~~~

- [ ] **Step 2: Run focused test**

~~~text
python -m pytest tests/test_nested_evaluation.py -q
~~~

Expected: FAIL because inner-only parameter selection is not implemented.

- [ ] **Step 3: Implement DecoderConfig and selection**

Define:

~~~python
@dataclass(frozen=True)
class DecoderConfig:
    candidate_quantile: float
    verifier_threshold: float
    candidate_fuse_gap_ms: int
    decode_fuse_gap_ms: int
    min_duration_ms: int
    feature_variant: str
    training_budget: str
    selection_source: str
~~~

Freeze the complete M5 search space before any inner result is written. There is no implicit range, CLI override or unregistered value:

~~~python
M5_DECODER_GRID = {
    "candidate_quantile": (0.70, 0.80, 0.90),
    "verifier_threshold": (0.10, 0.25, 0.50),
    "candidate_fuse_gap_ms": (300_000,),
    "decode_fuse_gap_ms": (300_000, 600_000, 900_000),
    "min_duration_ms": (120_000, 180_000, 240_000),
    "feature_variant": ("event_stats_v1",),
    "training_budget": ("budget_v1",),
}
M5_TRAINING_BUDGETS = {
    "budget_v1": {"candidate_max_iter": 100, "verifier_max_iter": 100},
}
M5_SEEDS = (20260910, 20260911, 20260912)
~~~

Implement `expand_decoder_grid(grid, training_budgets)` as a deterministic sorted Cartesian-product helper; it must validate that every `training_budget` key exists in `training_budgets`, attach the corresponding `candidate_max_iter` and `verifier_max_iter`, and return exactly 81 `DecoderConfig` values for the constants above.

The three quantiles reuse the frozen G1 grid; verifier thresholds are the preflight-tested `{0.10, 0.25, 0.50}` set; candidate fusion remains fixed at the preflight-supported 300 s; decode fusion is the finite `{300, 600, 900}` s set; minimum duration is the pre-registered `{120, 180, 240}` s set centered on the design default. The feature variant is the singleton `event_stats_v1` (the exact `[E,16]` event feature contract built from the Task 4 `imu_stats_v1` `[W,111]` cache); no coarse-context, TCN or Transformer feature enters M5. The training budget is the singleton design budget `budget_v1` (candidate/verifier `max_iter=100`); the field remains in the schema so a future approved plan can add a budget, but this plan has no open budget search. Inner code must enumerate exactly 81 configurations (`3×3×1×3×3×1×1`) and reject any configuration outside it; with 5 outer folds and 4 inner folds, `inner-results.jsonl` therefore contains exactly 1,620 passing config/fold rows.

Implement `select_inner_parameters` using inner event F1 as the primary key, then higher candidate coverage, lower long_fp_fraction, lower count of `boundary_mae_ms=None` rows, lower finite boundary MAE, and lexicographic configuration order. The function accepts inner results only. Use `boundary_mae_sort_key`: every finite boundary MAE precedes `None`, finite values sort ascending, and `None` is never converted to zero. If all remaining candidates have `None`, proceed to the lexicographic configuration tie-break. The lexicographic configuration ID includes all seven fields, including `feature_variant` and `training_budget`.

- [ ] **Step 4: Implement the complete nested outer evaluation sequence**

For each outer fold, execute this order and enforce the participant boundary at every function call:

1. Build inner participant folds from that outer fold's `outer-train` participants only; no outer-valid participant or metadata is available to the inner runner.
2. For every inner fold and every decoder configuration in the frozen candidate grid, fit the candidate scorer on `inner-train` participants only and derive its score threshold from the `inner-train` score distribution only.
3. Within the same inner fold, generate participant-frozen OOF candidate scores using only `inner-train` participants, then fit the verifier with the existing `fit_event_verifier` contract using only those inner-train OOF scores. OOF-unavailable participants are recorded and never replaced by an all-participant fallback.
4. Apply the inner-train candidate and verifier to `inner-valid` sessions only. Compute candidate coverage, event F1, long-fp fraction and boundary MAE on inner-valid only; use no outer-valid value for selection.
5. Select the decoder configuration from aggregated inner-valid results using `select_inner_parameters` and the frozen key. Do not refit any model or inspect outer-valid metrics before this selection is serialized.
6. After selection, refit the candidate scorer on complete `outer-train` participants and derive its threshold from complete `outer-train` scores only. Generate participant-frozen OOF scores within complete outer-train and fit the verifier only from those OOF scores.
7. Apply the selected, outer-train-refit pipeline exactly once to `outer-valid`, persist its metrics as evaluation-only output, and prohibit those metrics from changing the selected configuration or any threshold.

Persist one per-fold selection record and the final M5 config under:

~~~text
artifacts/m5-nested-evaluation/inner-results.jsonl
artifacts/m5-nested-evaluation/outer-fold-selected-configs.json
artifacts/m5-nested-evaluation/selected-config.json
artifacts/m5-nested-evaluation/outer-metrics.json
artifacts/m5-nested-evaluation/manifest.json
~~~

`inner-results.jsonl` contains exactly one `inner_result_v1` record for each `(outer_fold_id, inner_fold_id, decoder_config)` evaluation. Every record has `outer_fold_id`, `inner_fold_id`, `config_id`, all seven frozen configuration fields (`candidate_quantile`, `verifier_threshold`, `candidate_fuse_gap_ms`, `decode_fuse_gap_ms`, `min_duration_ms`, `feature_variant`, `training_budget`), the resolved `candidate_max_iter` and `verifier_max_iter`, `inner_event_f1`, `candidate_coverage`, `long_fp_fraction`, `boundary_mae_ms` (finite number or `None`), `candidate_count` and `status`. Records are sorted by `outer_fold_id`, `inner_fold_id` and `config_id`; incomplete or failed inner results cannot be silently omitted from aggregation.

The unique final config is aggregated from all `status="pass"` rows in this `inner-results.jsonl` across all five outer folds and all four inner folds per outer fold. Selection is permitted only when every expected `(outer_fold_id, inner_fold_id, config_id)` row from the exact `M5_DECODER_GRID` Cartesian product is present and has `status="pass"`; a missing or failed row invalidates M5 and prevents `selected-config.json` from being written. For each `config_id`, compute arithmetic means of `inner_event_f1`, `candidate_coverage`, `long_fp_fraction` and all finite `boundary_mae_ms` values, plus `boundary_mae_missing_count`. Select with this exact key: highest mean inner event F1, highest mean candidate coverage, lowest mean long-fp fraction, lowest boundary-MAE missing count, lowest finite boundary-MAE mean with `None` after every finite value, then lexicographically smallest `config_id`. Write the aggregate and the contributing row IDs into `selected-config.json` under the exact `aggregate_inner_metrics` object below. `outer-metrics.json` is written only after this selection and is never read by the selector or used in the final-config key.

The implementation API for this step is `aggregate_inner_results(inner_results_path)`; it reads only `inner-results.jsonl`, validates the complete 5×4 row matrix for every decoder config, computes the aggregate key above, and returns the selected config payload. `write_selected_config` then writes and hashes that payload. Neither function accepts `outer-metrics.json` as an input.

`selected-config.json` is the only config that M6 may consume. Its exact schema is:

~~~json
{
  "schema_version": "decoder_config_v1",
  "config_hash": "64 lowercase hexadecimal characters",
  "base_config_hash": "64 lowercase hexadecimal characters",
  "selection_source": "inner",
  "selection_metric": "mean_inner_event_f1",
  "selection_key": ["mean_inner_event_f1", "mean_candidate_coverage", "mean_long_fp_fraction", "boundary_mae_missing_count", "finite_boundary_mae_mean_ms", "config_lexicographic"],
  "candidate_quantile": 0.80,
  "verifier_threshold": 0.50,
  "candidate_fuse_gap_ms": 300000,
  "decode_fuse_gap_ms": 600000,
  "min_duration_ms": 180000,
  "feature_variant": "event_stats_v1",
  "training_budget": "budget_v1",
  "candidate_max_iter": 100,
  "verifier_max_iter": 100,
  "outer_metrics_used": false,
  "source_run_id": "m5-nested-evaluation",
  "outer_fold_ids": ["outer-0", "outer-1", "outer-2", "outer-3", "outer-4"],
  "inner_results_artifact": "inner-results.jsonl",
  "contributing_inner_result_ids": ["outer-0/inner-0/q0.80-v0.50-f300000-d600000-min180000-fv-event_stats_v1-b-budget_v1"],
  "aggregate_inner_metrics": {
    "inner_result_count": 20,
    "mean_inner_event_f1": 0.40,
    "mean_candidate_coverage": 0.90,
    "mean_long_fp_fraction": 0.10,
    "boundary_mae_missing_count": 0,
    "finite_boundary_mae_mean_ms": 900.0
  }
}
~~~

The example numeric values are schema examples; the implementation writes the actual aggregate from the selected config's 20 contributing inner rows. If all 20 boundary MAE values are `None`, `finite_boundary_mae_mean_ms` is JSON `null` and the selection key places it after every finite mean; it is never encoded as zero. `aggregate_inner_metrics` is required and is part of the canonical hash. The canonical hash is computed after sorting keys and using compact UTF-8 JSON, with only `config_hash` omitted during hashing. `outer_metrics_used` must remain false; `selection_source` must remain `inner`. The final config is selected from the complete inner-result row set only, using the fixed aggregate key and deterministic configuration order. A missing field, hash mismatch, non-inner source, incomplete inner-result set or any outer metric dependency invalidates M5/G4.

M5 must run exactly the three seeds `M5_SEEDS=(20260910, 20260911, 20260912)` and write `artifacts/m5-nested-evaluation/stability-report.json`. The stability report contains one row for every seed and outer fold, per-seed median/mean/standard deviation, the exact seed list, the split-manifest hash and the resolved selected-config hash. `outer-metrics.json` contains one aggregate row per outer fold, where each metric is the median of that fold's three seed results, plus the raw 15 seed×fold rows. Define `median_outer_f1` as the median of all 15 raw outer-fold F1 values; define `outer_splits_at_or_above_baseline` as the count of the five outer-fold medians whose F1 is at least the trusted baseline; define `long_fp_fraction_max` and `boundary_mae_ms_max` as the maxima of the five outer-fold medians. A missing/non-finite boundary MAE is a G4 failure, not zero.

G4 consumes exactly `artifacts/m0-trusted-baseline/metrics.json` and its sibling `split-manifest.json`, and reads `$.metric.value` only after verifying `schema_version="trusted_baseline_v1"`, `baseline_id="m0-q50-groupnorm"`, `data_scope="target_only_train"`, `split_manifest_sha256`, split `strategy="participant_frozen"`, split `seed=20260910`, split `valid_fraction=0.20`, `metric.name="event_f1"`, `metric.matching="strict_iou_gt_0.25_one_to_one"`, `metric.source_document="docs/preflight-2026-09-10.md"` and `metric.value=0.17284` within `1e-5`. The final `outer-metrics.json` must contain this source path, its SHA256 and the resolved baseline value. G4 passes only when all of the following are true: `median_outer_f1 >= trusted_baseline_event_f1 + 0.02`; `outer_splits_at_or_above_baseline >= 3`; `long_fp_fraction_max <= 0.25`; and `boundary_mae_ms_max <= 900_000`. The stability report must contain all three seeds and no failed/missing seed-fold row. Any failed condition writes `gate_result=fail`, classifies the failure and prevents M6.

Implement `build_g4_report(outer_metrics, trusted_baseline_path)` with the following deterministic calculation; do not replace it with a single-seed or mean-only check:

~~~python
baseline = read_json(trusted_baseline_path)
baseline_f1 = baseline["metric"]["value"]
rows = sorted(outer_metrics, key=lambda row: (row["outer_fold_id"], row["seed"]))
assert sorted({row["seed"] for row in rows}) == [20260910, 20260911, 20260912]
assert all(sum(row["seed"] == seed for row in rows) == 5 for seed in (20260910, 20260911, 20260912))
assert all(is_finite(row["event_f1"]) for row in rows)
fold_medians = {
    fold_id: median([row["event_f1"] for row in rows if row["outer_fold_id"] == fold_id])
    for fold_id in ("outer-0", "outer-1", "outer-2", "outer-3", "outer-4")
}
long_fp_max = max_fold_median("long_fp_fraction", rows)
boundary_mae_max = max_finite_fold_median("boundary_mae_ms", rows)
g4 = {
    "median_outer_f1_pass": median([row["event_f1"] for row in rows]) >= baseline_f1 + 0.02,
    "outer_splits_at_or_above_baseline": sum(value >= baseline_f1 for value in fold_medians.values()),
    "long_fp_fraction_max": long_fp_max,
    "long_fp_fraction_max_pass": long_fp_max is not None and long_fp_max <= 0.25,
    "boundary_mae_ms_max": boundary_mae_max,
    "boundary_mae_ms_max_pass": boundary_mae_max is not None and boundary_mae_max <= 900_000,
}
g4["result"] = "pass" if (
    g4["median_outer_f1_pass"]
    and g4["outer_splits_at_or_above_baseline"] >= 3
    and g4["long_fp_fraction_max_pass"]
    and g4["boundary_mae_ms_max_pass"]
) else "fail"
~~~

`max_fold_median` and `max_finite_fold_median` return `None` when required values are missing/non-finite; they may not coerce `None` to zero. The serialized `outer-metrics.json` stores numeric-or-null `median_outer_f1`, `outer_splits_at_or_above_baseline`, `long_fp_fraction_max`, `boundary_mae_ms_max`, the four boolean checks above, `g4.result`, `trusted_baseline_artifact`, `trusted_baseline_sha256`, `trusted_baseline_event_f1`, `seed_ids`, `outer_fold_ids` and the raw 15 rows. `stability-report.json` stores the same raw rows plus per-seed median/mean/std and the selected-config hash.

- [ ] **Step 5: Run focused and full tests after the M5 implementation**

~~~text
python -m pytest tests/test_nested_evaluation.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 6: Run M5 nested evaluation and the three-seed stability report after tests pass**

~~~text
python scripts/run_event_verifier.py --config configs/example.local.yaml --cache-dir artifacts/g1-formal-cache --output-dir artifacts/m5-nested-evaluation --formal --outer-folds 5 --seeds 20260910,20260911,20260912 --trusted-baseline artifacts/m0-trusted-baseline/metrics.json
~~~

Expected: `inner-results.jsonl`, `outer-fold-selected-configs.json`, `selected-config.json`, `outer-metrics.json`, `stability-report.json`, `manifest.json` and `telemetry.jsonl` exist. The command must stop before M6 if the complete frozen Cartesian grid, all 5×4 inner rows per config, three seeds, trusted-baseline validation or any G4 condition fails.

- [ ] **Step 7: Commit M5 nested evaluation**

~~~text
git add src/eating_event/evaluation.py scripts/run_event_verifier.py tests/test_nested_evaluation.py
git commit -m "feat: enforce nested inner-only decoder selection"
~~~

Gate: G4 evaluation is invalid if any outer metric reaches parameter selection. After inner-only selection, G4 passes only if the three-seed stability report is complete, `median_outer_f1 >= 0.17284 + 0.02`, at least 3 of the 5 outer-fold medians are at least `0.17284`, the maximum outer-fold-median `long_fp_fraction <= 0.25`, and the maximum outer-fold-median `boundary_mae_ms <= 900000`. A missing or non-finite metric is a failed gate, not an imputed value.

### Task 10: Execute the independent M6 full target-only scale run and resource gate

This is a separate milestone from nested evaluation and submission serialization. It is the only task allowed to produce the final target-only candidate and verifier checkpoints. It must run only after G4 nested evaluation passes and after the resource dry-run succeeds.

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/config.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/full_run.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/audit_dataset.py
- Create: E:/bme_compitition/bme_compitition_next/scripts/run_full_target_only.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_full_target_run.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_resources.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_reproducibility.py

- [ ] **Step 1: Write failing M6 and resource tests**

~~~python
def test_full_target_run_rejects_bounded_file_limit(tmp_path):
    config = make_full_target_config(tmp_path, max_files_per_participant=2)
    with pytest.raises(ValueError, match="formal full target-only"):
        validate_full_target_run(config, formal=True)


def test_full_target_run_writes_candidate_verifier_and_oof_artifacts(tmp_path):
    result = run_fixture_full_target_only(
        tmp_path,
        selected_config=make_m5_selected_config(tmp_path),
    )
    assert (result.output_dir / "candidate_model.joblib").exists()
    assert (result.output_dir / "verifier_model.joblib").exists()
    assert (result.output_dir / "oof_scores").is_dir()
    assert (result.output_dir / "cache_manifest.json").exists()
    assert (result.output_dir / "resource_report.json").exists()


def test_cache_only_recovery_does_not_fit_again(tmp_path, monkeypatch):
    selected_config = make_m5_selected_config(tmp_path)
    first = run_fixture_full_target_only(tmp_path, selected_config=selected_config)
    monkeypatch.setattr("eating_event.full_run.fit_candidate_model", fail_if_called)
    monkeypatch.setattr("eating_event.full_run.fit_event_verifier", fail_if_called)
    recovered = run_fixture_full_target_only(
        tmp_path,
        selected_config=selected_config,
        cache_only=True,
        resume=True,
    )
    assert sha256_file(recovered.output_dir / "candidate_model.joblib") == sha256_file(first.output_dir / "candidate_model.joblib")
    assert sha256_file(recovered.output_dir / "verifier_model.joblib") == sha256_file(first.output_dir / "verifier_model.joblib")


def test_m6_requires_m5_selected_config(tmp_path):
    with pytest.raises(ValueError, match="selected-config"):
        run_full_target_only(
            make_full_target_config(tmp_path),
            selected_config_path=None,
            cache_dir=tmp_path / "cache",
            output_dir=tmp_path / "output",
            run_id="m6",
            formal=True,
        )


def test_m6_rejects_selected_config_hash_mismatch(tmp_path):
    config, selected_config = make_formal_m5_fixture(tmp_path, config_hash="f" * 64)
    assert selected_config == config.repository_root / "artifacts" / "m5-nested-evaluation" / "selected-config.json"
    with pytest.raises(ValueError, match="config_hash"):
        run_full_target_only(
            config,
            selected_config_path=selected_config,
            cache_dir=tmp_path / "cache",
            output_dir=tmp_path / "output",
            run_id="m6",
            formal=True,
        )


def test_m6_does_not_reselect_parameters(tmp_path, monkeypatch):
    monkeypatch.setattr("eating_event.full_run.select_inner_parameters", fail_if_called, raising=False)
    monkeypatch.setattr("eating_event.full_run.select_candidate_quantile", fail_if_called, raising=False)
    run_fixture_full_target_only(tmp_path, selected_config=make_m5_selected_config(tmp_path))


def test_resource_budget_rejects_gpu_limit_above_seven_gb():
    with pytest.raises(ValueError, match="gpu_memory_limit_gb"):
        ResourceBudget(gpu_memory_limit_gb=7.5)
~~~

`make_formal_m5_fixture` must create a temporary repository root, write `artifacts/m5-nested-evaluation/selected-config.json` and its sibling `manifest.json` under that root, include every exact selected-config field (including `feature_variant`, `training_budget`, resolved max-iteration values and `aggregate_inner_metrics`), set a passing G4 result and a correct `base_config_hash`, compute a correct canonical hash first, then replace only `config_hash` with the valid but incorrect value `"f" * 64`. The test therefore reaches canonical hash validation after the formal path, schema, grid and aggregate checks.

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_full_target_run.py tests/test_resources.py tests/test_reproducibility.py -q
~~~

Expected: FAIL because the independent full-run orchestrator, checkpoint contract, cache recovery and resource budget do not exist.

- [ ] **Step 3: Implement the full target-only orchestrator**

Implement `run_full_target_only(config, selected_config_path, cache_dir, output_dir, run_id, formal, cache_only, resume)` with these non-negotiable boundaries:

1. Require `selected_config_path` in formal mode and require it to resolve exactly to `artifacts/m5-nested-evaluation/selected-config.json` relative to the configured repository root. Load that file, its sibling M5 `manifest.json` and the resolved base config before model fitting. Require `schema_version="decoder_config_v1"`, `selection_source="inner"`, `outer_metrics_used=false`, `source_run_id="m5-nested-evaluation"`, the seven frozen decoder fields, the `aggregate_inner_metrics` object, and `manifest["gate_results"]["G4"]["result"]="pass"`.
2. Recompute the canonical JSON hash excluding `config_hash` and compare it with `selected-config.json.config_hash`; the aggregate object is included in this hash. Recompute the resolved ProjectConfig hash and compare it with `base_config_hash`. Reject missing fields, any hash mismatch, a non-inner selection source, a failed/missing G4 result, a selected value outside `M5_DECODER_GRID`, or a `training_budget` whose `candidate_max_iter`/`verifier_max_iter` do not exactly equal `M5_TRAINING_BUDGETS[training_budget]`.
3. Discover every eligible target train participant and session from the manifest; reject test participants, test metadata and external data references before any feature or label parsing. In `formal=True`, reject `max_files_per_participant`, process all eligible target train sessions, and write an explicit per-session status for every discovered session.
4. Load or build the versioned dense candidate cache. Fit the final HGB candidate model on all eligible target train rows using the values in the validated selected config, including `feature_variant`, `training_budget`, `candidate_max_iter`, `verifier_max_iter`, threshold and decoder values; no outer-valid or test row may enter fitting. M6 must not call `select_inner_parameters` or `select_candidate_quantile`, and the CLI must provide no candidate-quantile, verifier-threshold or decoder-parameter override.
5. Generate participant-frozen OOF candidate scores for all target train participants, then call the existing public `fit_event_verifier` function only with those OOF scores. `fit_event_verifier` is the sole canonical verifier-fit name for this plan. Fail closed if OOF fallback is non-empty or the positive-sample gate fails.
6. Write these exact outputs under `artifacts/m6-full-target-only/`: `candidate_model.joblib`, `verifier_model.joblib`, `oof_scores/`, `cache_manifest.json`, `metrics.json`, `resource_report.json`, `resolved_config.json`, `selected-config.json`, `run.log`, `telemetry.jsonl` and `manifest.json`. Copy the validated M5 selected config into the M6 artifact. Checkpoints must contain the contract hash, feature schema hash, git revision and training participant digest.

- [ ] **Step 4: Implement bounded resource monitoring and reproducibility**

Record process RSS before and after each session, peak RSS, stage elapsed time, GPU allocated/reserved memory when CUDA is present, and timeout status. Abort the current stage when the configured host fraction, GPU limit or stage timeout is exceeded. Derive module seeds from master seed, run ID, fold ID and module name; seed NumPy and Python; if PyTorch is used, enable deterministic algorithms and record the CUDA device. Record `run_start`, each `gate_result`, any adaptive-workflow `escalation` and `run_end` in the M6 artifact.

- [ ] **Step 5: Re-run M6 focused and full tests after implementation**

~~~text
python -m pytest tests/test_full_target_run.py tests/test_resources.py tests/test_reproducibility.py -q
python -m pytest -q
~~~

Expected: all M6 checkpoint, selected-config, cache-recovery, resource and reproducibility tests pass. Do not start the resource dry-run or any model fitting when either command fails.

- [ ] **Step 6: Run the resource dry-run before full training**

~~~text
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/m6-resource-audit.json --resource-dry-run --run-id m6-resource-audit --diagnostic-only
~~~

Expected: tests pass; the diagnostic audit completes inside its configured timeout and writes resource limits, peak measurements, `run_id`, `diagnostic_only=true` and a classified result. A resource failure stops M6 before model fitting.

- [ ] **Step 7: Run the complete M6 target-only scale command**

~~~text
python scripts/run_full_target_only.py --config configs/example.local.yaml --selected-config artifacts/m5-nested-evaluation/selected-config.json --cache-dir artifacts/m6-full-cache --output-dir artifacts/m6-full-target-only --run-id m6-full-target-only --formal
~~~

The command must not receive `--max-files-per-participant` or any decoder-parameter override. Acceptance requires the M5 selected config to pass schema/hash/G4 validation, all eligible target train sessions to be processed or explicitly classified, both full checkpoints to exist, OOF verifier scores to cover every eligible target participant without fallback, resource limits to pass, and the artifact manifest plus telemetry to be complete. No official test score is computed or written.

- [ ] **Step 8: Run M6 cache recovery and compare outputs**

~~~text
python scripts/run_full_target_only.py --config configs/example.local.yaml --selected-config artifacts/m5-nested-evaluation/selected-config.json --cache-dir artifacts/m6-full-cache --output-dir artifacts/m6-full-target-only --run-id m6-full-target-only --formal --cache-only --resume
~~~

Acceptance requires cache-only recovery to avoid raw reads and model fitting, preserve the cache manifest and contract hashes, and reproduce the candidate/verifier checkpoint checksums and saved target-train predictions. A recovery mismatch is a `PIPELINE` failure and blocks submission.

- [ ] **Step 9: Commit M6 full-scale artifacts and controls**

~~~text
git add src/eating_event/artifacts.py src/eating_event/config.py src/eating_event/full_run.py scripts/audit_dataset.py scripts/run_full_target_only.py tests/test_full_target_run.py tests/test_resources.py tests/test_reproducibility.py
git commit -m "feat: add full target-only scale run and resource gates"
~~~

Gate: M6/G5 passes only when the full target-only candidate checkpoint, participant-OOF verifier checkpoint, cache-recovery comparison and resource report all pass. Any leakage, OOF fallback, missing session status, checkpoint mismatch or resource violation records `gate_result=fail`, writes `run_end` and stops before Task 11.

### Task 11: Execute M7 target-only submission isolation

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/data/manifest.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_submission.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_manifest.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_submission_isolation.py

- [ ] **Step 1: Write failing isolation tests**

~~~python
def test_submission_rejects_external_data_path(tmp_path):
    config = make_submission_config(
        tmp_path,
        external_data_root=tmp_path / "external-dataset",
    )
    with pytest.raises(ValueError, match="external"):
        validate_submission_inputs(config)


def test_train_event_loader_skips_test_row_before_parsing_timestamps(tmp_path):
    path = tmp_path / "mealinfo.csv"
    path.write_text(
        "externalid,beforeTime,afterTime\n"
        "p1,100,200\n"
        "test,not-a-time,also-not-a-time\n",
        encoding="utf-8",
    )
    events = load_train_meal_events(path, allowed_participants={"p1"})
    assert set(events) == {"p1"}
    assert events["p1"][0].start_ms == 100


def test_submission_event_loader_never_receives_test_participant(tmp_path, monkeypatch):
    observed = []

    def spy(path, allowed_participants):
        observed.append(set(allowed_participants))
        assert "test" not in {value.lower() for value in allowed_participants}
        return {}

    monkeypatch.setattr("scripts.run_submission.load_train_meal_events", spy)
    run_submission_with_test_fixture(tmp_path)
    assert observed


def test_submission_requires_the_passed_m6_checkpoints(tmp_path):
    with pytest.raises(ValueError, match="M6"):
        validate_submission_model_dir(tmp_path / "missing-m6")
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_submission_isolation.py -q
~~~

Expected: FAIL because submission input validation and test-truth isolation are not enforced.

- [ ] **Step 3: Implement a train-only event loader**

Add load_train_meal_events(path, allowed_participants). The loader must inspect externalid first and skip any row not in allowed_participants before reading or converting beforeTime and afterTime. It must reject allowed_participants containing test. Refactor run_submission.py to discover train records first, derive the train participant set, call this loader once for train labels, and pass an empty truth tuple for every test record.

The runner consumes, rather than recreates, the artifacts from `artifacts/m6-full-target-only/`. Validate that the directory contains `candidate_model.joblib`, `verifier_model.joblib`, `manifest.json`, `resolved_config.json`, `telemetry.jsonl` and the M6 contract/feature hashes. Reject a missing or failed M6 manifest and never retrain either model in the submission task.

Before reading test files, validate that external_data_references and test_truth_references are empty and that the submission contract hash equals the trained contract hash. The runner must not call load_meal_events on the mixed metadata file.

- [ ] **Step 4: Implement deterministic serialization from the M6 checkpoints**

Serialize participant_id, session_id, start_ms and end_ms. Sort by participant_id, session_id, start_ms and end_ms. Write the isolation report, skipped-file provenance, `telemetry.jsonl` and manifest beside the submission artifact; record `run_start`, the G6 `gate_result` and `run_end` for the submission run.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_submission_isolation.py -q
python scripts/run_submission.py --config configs/example.local.yaml --model-dir artifacts/m6-full-target-only --cache-dir artifacts/m7-submission-cache --output artifacts/m7-submission.json
python -m pytest -q
~~~

Expected: all tests pass; the runner loads the M6 checkpoints, reads only official test raw files for inference, never parses test truth, and writes an isolation report beside the submission artifact.

- [ ] **Step 6: Commit M7/G6 isolation**

~~~text
git add src/eating_event/data/manifest.py scripts/run_submission.py src/eating_event/artifacts.py tests/test_manifest.py tests/test_submission_isolation.py
git commit -m "fix: enforce target-only submission isolation"
~~~

Gate: M7/G6 passes only when the runner consumes a passing M6 artifact, any external or test-truth reference fails closed, a test metadata row with invalid timestamps does not make the train-only loader fail, and a deterministic rerun produces the same serialized output and isolation report.

### Task 12: Execute gates and record the final implementation state

**Files:**

- Create: E:/bme_compitition/bme_compitition_next/docs/gates/2026-09-14-gate-results.md
- Modify: E:/bme_compitition/bme_compitition_next/docs/experiment-log-2026-09-10.md
- Create: E:/bme_compitition/bme_compitition_next/tests/test_gate_reporting.py

- [ ] **Step 1: Write failing gate-report test**

~~~python
def test_gate_report_has_required_fields():
    report = build_gate_report(
        gate_id="G2",
        acceptance="OOF fallback equals zero",
        current_evidence={"fallback_count": 0},
        experiment="participant membership audit",
        result="pass",
        failure_class=None,
        next_action="continue",
        continue_local_optimization=False,
        architecture_reopen=False,
    )
    assert report["gate_id"] == "G2"
    assert report["current_evidence"]["fallback_count"] == 0
    assert report["architecture_reopen"] is False
~~~

- [ ] **Step 2: Run focused test**

~~~text
python -m pytest tests/test_gate_reporting.py -q
~~~

Expected: FAIL because the gate report schema does not exist.

- [ ] **Step 3: Implement gate report serialization**

Every gate result must contain gate_id, acceptance, current_evidence, experiment, result, failure_class, next_action, continue_local_optimization, architecture_reopen, run_id and config_hash. Use UNKNOWN when evidence is insufficient and never encode missing metrics as zero.

- [ ] **Step 4: Run the gate sequence in order**

~~~text
python -m pytest -q
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/g0-audit.json --run-id g0-audit --diagnostic-only
python scripts/run_trusted_baseline.py --config configs/example.local.yaml --audit artifacts/g0-audit.json --baseline-id m0-q50-groupnorm --split-seed 20260910 --valid-fraction 0.20 --expected-event-f1 0.17284 --output-dir artifacts/m0-trusted-baseline --strict
python scripts/run_candidate_coverage.py --config configs/example.local.yaml --output artifacts/g1-candidate-coverage.json --cache-dir artifacts/g1-formal-cache --outer-folds 5 --formal
python scripts/run_event_verifier.py --config configs/example.local.yaml --cache-dir artifacts/g1-formal-cache --output-dir artifacts/m5-nested-evaluation --formal --outer-folds 5 --seeds 20260910,20260911,20260912 --trusted-baseline artifacts/m0-trusted-baseline/metrics.json
python scripts/run_full_target_only.py --config configs/example.local.yaml --selected-config artifacts/m5-nested-evaluation/selected-config.json --cache-dir artifacts/m6-full-cache --output-dir artifacts/m6-full-target-only --run-id m6-full-target-only --formal
python scripts/run_submission.py --config configs/example.local.yaml --model-dir artifacts/m6-full-target-only --cache-dir artifacts/m7-submission-cache --output artifacts/m7-submission.json
~~~

Do not start the next command when the previous gate fails. Record the failure classification and next action before continuing.

- [ ] **Step 5: Perform plan self-review**

Check that every Detailed Design section maps to a task, every task has exact files and tests, all public names agree with Task 1, and no step introduces external data, test truth, GT-neighbor sampling, cross-gap interpolation or all-participant fallback.
Check that the worktree path is `E:/bme_compitition/.worktrees/high-f1-event-stack-execution`, `/.worktrees/` is verified by `git check-ignore`, and all project commands run from its nested `bme_compitition_next` directory.
Check that the formal G1 command precedes every verifier or complex-model command and writes fold, participant and failure-class artifacts before stopping on failure.
Check that Task 5 reruns `tests/test_coverage.py` and `python -m pytest -q` after implementation and before the formal G1 command.
Check that the G1 quantile grid, M5 `verifier_threshold`/`decode_fuse_gap_ms`/`min_duration_ms` values, singleton `feature_variant`/`training_budget`, inner-only selection metric, tie-break and fuse gap are frozen and that Task 6 reuses rather than recreates `evaluation.py`.
Check that every G1 inner fold fits and thresholds on inner-train only, selects on inner-valid only, refits on complete outer-train only, and evaluates outer-valid only after selection.
Check that Task 9 repeats this full inner-train/inner-valid/complete-outer-train/outer-valid order for candidate and verifier models, not only for the G1 scorer.
Check that EventCandidate carries candidate status, quality status and ignore-source flags, and that every ignored source is excluded from verifier training, OOF scoring, metrics and decoder input.
Check that Task 8 exposes the `RunArtifact.record_event` telemetry API and tests `run_start`, `gate_result`, `escalation` and `run_end` plus manifest checksums.
Check that formal G1 and M3–M7 runs always have `run_start`, `gate_result` and `run_end`, while `escalation` exists only with `circuit_breaker_fired=true`, and that no module-level telemetry writer remains. Check that Task 1 creates the artifact/telemetry foundation before G1 and that Task 2/4/7 bounded commands are explicitly `diagnostic_only` with audit/smoke JSON metadata rather than formal lifecycle events.
Check that the Task 8 focused command includes `tests/test_telemetry.py` and that M6 recovery patches the canonical `fit_event_verifier` name.
Check that M6 is an independent full target-only run with full candidate/verifier checkpoints, participant OOF scores, cache-only recovery comparison and resource report before M7/G6 submission.
Check that Task 9 writes the exact M5 selected-config schema and that Task 10 validates its path, schema, canonical hash, base-config hash and G4 status without reselecting parameters.
Check that `inner-results.jsonl` contains all 5×4 inner-fold rows per decoder config, final config aggregation uses only those rows, and `outer-metrics.json` is excluded from selection.
Check that `selected-config.json` contains `feature_variant`, `training_budget`, resolved budget values and `aggregate_inner_metrics`, and that the aggregate object is included in the canonical hash.
Check that finite boundary MAE sorts before `None`, `None` is never encoded as zero, and the selection test covers the rule.
Check that the trusted baseline sentinel writes `artifacts/m0-trusted-baseline/metrics.json` and `split-manifest.json`, fixes the M0 value at `0.17284` under the strict IoU rule, and that M5 consumes that artifact rather than a hard-coded or outer-derived baseline.
Check that M5 runs exactly three seeds, writes the stability report, defines the outer-fold/seed aggregation, and explicitly enforces all four G4 acceptance conditions including the 3/5 split condition, long-FP limit and 900000 ms boundary limit.
Check that the M6 hash-mismatch test uses the formal relative selected-config path and a valid 64-character hexadecimal wrong hash.
Check that Task 10 reruns `tests/test_full_target_run.py`, resource/reproducibility tests and `python -m pytest -q` before the resource dry-run and full target-only training.
Check that EventCandidate allows `segment_start_ms == interval.start_ms` and that submission tests prove test rows are skipped before timestamp parsing.

- [ ] **Step 6: Commit only the executed gate record**

~~~text
git add docs/gates/2026-09-14-gate-results.md docs/experiment-log-2026-09-10.md tests/test_gate_reporting.py
git commit -m "docs: record high-f1 pipeline gate results"
~~~

Gate: if G1, G2, G3, G4, G5 or G6 fails, stop the formal route and classify the failure before local optimization. Architecture reopen is allowed only by the frozen kill criteria.

## Completion criteria

The implementation is complete only when:

- G0 through G6 have recorded results;
- full target-only artifacts are reproducible;
- outer evaluation is nested and participant-disjoint;
- OOF fallback is zero;
- candidate coverage, event F1, long FP, boundary MAE and worst participant are reported;
- submission runner has no external-data or test-truth references;
- no architecture reopen occurred without a recorded kill criterion.
