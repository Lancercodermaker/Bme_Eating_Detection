# High-F1 Event Stack Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将冻结的 target-only 15 s/7.5 s dense-window、HGB candidate scorer、participant-level OOF event verifier 和 constrained decoder 实现为可审计的正式 ML pipeline。

**Architecture:** 先修复 manifest、timebase、cache 和 OOF 数据契约，再执行 candidate coverage gate，随后训练 event verifier 并用 nested participant validation 选择 decoder 参数。外部数据、test truth、GT 邻域采样、跨 gap 插值和 all-participant OOF fallback 永远不属于本计划。

**Tech Stack:** Python 3.10+、NumPy、pandas、PyYAML、SciPy、scikit-learn、pytest；HGB 在 CPU 上运行；PyTorch/TCN 只保留为后续受控 candidate auxiliary，不是本计划的主实现。

---

## 执行边界

- 工作区固定为 E:/bme_compitition/bme_compitition_next。
- 原始数据目录只读，不能复制到工作区或加入 Git。
- 实现开始前必须从冻结提交 6d906ce 创建独立 worktree 和 codex/ 分支；master 只保存已冻结文档，不直接承载实现改动。
- 每个 task 先写 focused failing test，再实现最小改动，再运行 focused test 和全套测试。
- 每个 gate failure 必须写入 artifact 并停止当前 milestone；不得用随机换 seed 或手工改 threshold 掩盖失败。
- 正式验证禁止 max-files-per-participant；该参数只允许 smoke test。
- 当前旧计划 E:/bme_compitition/bme_compitition_next/docs/superpowers/plans/2026-09-10-high-f1-event-stack.md 保留为历史记录，本计划是当前冻结设计的执行计划。
- 本计划执行过程中不得调用外部数据适配器，不得读取 test truth，不得重新做开放式架构搜索。

Worktree preflight must verify that the plan revision descends from 6d906ce, then create the implementation worktree from that plan revision:

~~~powershell
$repo = "E:\bme_compitition"
$project = "E:\bme_compitition\bme_compitition_next"
$worktree = "E:\bme_compitition\bme_compitition_next-high-f1-execution"
$planRevision = git -C $project rev-parse HEAD
git -C $project merge-base --is-ancestor 6d906ce $planRevision
if ($LASTEXITCODE -ne 0) { throw "plan revision is not descended from 6d906ce" }
git -C $repo worktree add $worktree -b codex/high-f1-event-stack-execution $planRevision
~~~

After this command, all implementation commands run from $worktree. The original project checkout remains unchanged during implementation.

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

每个 run 必须记录 run_start、gate_result、escalation 和 run_end。若当前 host 没有独立 telemetry recorder，则在 run artifact 中写入相同字段，不能伪称已有外部 telemetry。

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
| src/eating_event/artifacts.py | run directory、checksums、resource logging |
| scripts/audit_dataset.py | manifest/timebase audit CLI |
| scripts/run_candidate_baseline.py | dense cache 和 candidate coverage CLI |
| scripts/run_event_verifier.py | OOF verifier 和 nested validation CLI |
| scripts/run_submission.py | target-only final fit 和 test prediction serialization |
| tests/test_*.py | contract、leakage、metric、resource 和 runner regression tests |

### Task 1: Freeze public config and data schemas

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/config.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/schemas.py
- Modify: E:/bme_compitition/bme_compitition_next/configs/example.local.yaml
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_config.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_schemas.py

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
~~~

- [ ] **Step 2: Run focused tests and confirm failure**

~~~text
python -m pytest tests/test_config.py tests/test_schemas.py -q
~~~

Expected: FAIL because the resource fields, schema dataclasses and bounds validation do not exist.

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

Change configs/example.local.yaml so the formal defaults are window_seconds=15 and step_seconds=7.5. Add explicit coarse_window_seconds=240, coarse_step_seconds=15 and use_coarse_context=false fields; coarse context is disabled unless an inner-validation experiment enables it.

- [ ] **Step 4: Run focused and full tests**

~~~text
python -m pytest tests/test_config.py tests/test_schemas.py -q
python -m pytest -q
~~~

Expected: all focused tests and all existing tests pass.

- [ ] **Step 5: Commit M0**

~~~text
git add src/eating_event/config.py src/eating_event/schemas.py configs/example.local.yaml tests/test_config.py tests/test_schemas.py
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
python scripts/audit_dataset.py --config configs/example.local.yaml --limit-files 2 --output artifacts/m1-audit.json
~~~

Expected: focused tests pass; audit JSON contains status_counts, malformed_rows, duplicate_count and dropped_timestamp_count.

- [ ] **Step 6: Commit M1 parser changes**

~~~text
git add src/eating_event/data/manifest.py src/eating_event/data/raw.py src/eating_event/audit.py scripts/audit_dataset.py tests/test_manifest.py tests/test_raw.py tests/test_audit.py
git commit -m "feat: make manifest and raw parsing auditable"
~~~

Gate: stop M1 if any file or malformed row lacks an explicit status.

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
python scripts/run_candidate_baseline.py --config configs/example.local.yaml --cache-dir artifacts/m2-smoke-cache --output artifacts/m2-smoke.json --max-files-per-participant 2
~~~

The command must label this run smoke-only and must not treat its metrics as formal evaluation.

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
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_coverage.py -q
~~~

Expected: FAIL because CoverageRunConfig, CandidateCoverageReport and the formal coverage runner do not exist.

- [ ] **Step 3: Implement deterministic outer/inner participant fold creation**

Add ParticipantFold, build_outer_folds and build_inner_folds to evaluation.py. Sort participant identifiers, apply the supplied seed, assign every participant to exactly one outer validation fold, and keep all sessions of a participant together. No test participant or test metadata is accepted by these functions.

- [ ] **Step 4: Implement formal coverage evaluation**

Implement CandidateCoverageReport, FoldCoverageResult and run_candidate_coverage. The command must:

1. discover all eligible target train sessions;
2. reject max-files-per-participant when formal=True;
3. build outer participant folds;
4. select candidate quantile only inside outer-train inner folds;
5. fit HGB candidate scorer only on outer-train;
6. score every eligible outer-valid session;
7. build candidate event intervals with candidate_fuse_gap=300 seconds;
8. calculate pooled and per-participant candidate coverage;
9. write fold and participant reports even when the gate fails;
10. never fit an event verifier.

Use these output files:

~~~text
artifacts/g1-candidate-coverage.json
artifacts/g1-candidate-coverage-by-fold.json
artifacts/g1-candidate-coverage-by-participant.json
~~~

- [ ] **Step 5: Enforce the G1 gate**

The command exits nonzero after writing the report when any outer fold has pooled candidate coverage recall below 0.90. A first failure is classified as DATA/PIPELINE, CONFIGURATION or UNKNOWN according to the audit evidence. ARCHITECTURE is allowed only after three materially different causal hypotheses fail across multiple clean participant-frozen folds.

- [ ] **Step 6: Run the formal coverage command**

~~~text
python scripts/run_candidate_coverage.py --config configs/example.local.yaml --output artifacts/g1-candidate-coverage.json --cache-dir artifacts/g1-formal-cache --outer-folds 5 --formal
~~~

Expected: the command uses all eligible sessions, writes participant/fold coverage, and stops before any verifier training if G1 fails.

- [ ] **Step 7: Commit G1 coverage gate**

~~~text
git add src/eating_event/coverage.py src/eating_event/evaluation.py scripts/run_candidate_coverage.py tests/test_coverage.py
git commit -m "feat: add formal candidate coverage gate"
~~~

Gate: Task 6 and all verifier tasks are blocked until every outer fold satisfies pooled candidate coverage recall >= 0.90 or an explicit architecture-level kill decision is recorded.

### Task 6: Add nested participant folds and complete official metrics

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/candidates.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/metrics.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/evaluation.py
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
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_metrics.py tests/test_evaluation.py -q
~~~

Expected: FAIL because nested folds, matched_count and missing-match boundary semantics do not exist.

- [ ] **Step 3: Implement deterministic fold objects**

Define:

~~~python
@dataclass(frozen=True)
class ParticipantFold:
    fold_id: str
    train_participants: tuple[str, ...]
    valid_participants: tuple[str, ...]
~~~

Implement build_outer_folds and build_inner_folds by sorting participant IDs, applying the supplied NumPy seed, assigning each participant to exactly one validation fold, and deriving the complementary train set. Never read test metadata.

- [ ] **Step 4: Complete metric semantics**

Keep strict IoU > threshold and deterministic one-to-one matching. Add matched_count, truth_count and prediction_count. Use None for unmatched boundary MAE. Add aggregate functions for micro, macro_all, macro_event_bearing and worst participant.

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

Gate: M3 is invalid if a participant appears in multiple outer validation folds or missing-match MAE is encoded as zero. This task may only run after the formal G1 coverage report has passed.

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
python scripts/run_event_verifier.py --config configs/example.local.yaml --cache-dir artifacts/m2-smoke-cache --cache-only --output artifacts/m3-smoke.json
~~~

Expected: focused tests pass. A smoke dataset that cannot meet the positive-sample gate exits with VerifierTrainingGateError and a recorded gate result.

- [ ] **Step 7: Commit M4 OOF changes**

~~~text
git add src/eating_event/candidates.py src/eating_event/verifier.py scripts/run_event_verifier.py tests/test_verifier.py tests/test_oof_leakage.py
git commit -m "fix: remove participant leakage from verifier OOF scores"
~~~

Gate: M4 fails closed when fallback_participants is non-empty or verifier positive samples are insufficient.

### Task 8: Make event decoding session-safe and persist artifacts

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/verifier.py
- Create: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_event_verifier.py
- Modify: E:/bme_compitition/bme_compitition_next/tests/test_verifier.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_artifacts.py

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
    manifest = run.finalize()
    assert manifest["schema_version"] == "artifact_v1"
    assert "feature_schema.json" in manifest["files"]
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_verifier.py tests/test_artifacts.py -q
~~~

Expected: FAIL because EventCandidate has no session contract and RunArtifact does not exist.

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
label: int
window_indices: tuple[int, ...]
~~~

Validate session_start_ms <= segment_start_ms < interval.start_ms < interval.end_ms <= segment_end_ms <= session_end_ms. Group, sort and fuse only within the same session_id and segment_id. Apply candidate_fuse_gap before verifier scoring, apply verifier threshold and min_duration after scoring, then clip intervals to segment bounds. Decoder receives no truths.

- [ ] **Step 4: Implement RunArtifact**

Define:

~~~python
class RunArtifact:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = (root / run_id).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, value: object) -> None:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("artifact path escapes run directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2), encoding="utf-8")
~~~

Add write_jsonl and finalize. finalize writes checksums, git revision, environment versions and the artifact manifest; it rejects paths outside the run directory.

- [ ] **Step 5: Emit complete metrics**

Update run_event_verifier.py to write micro, macro_all, macro_event_bearing, worst_participant, candidate coverage, long_fp_fraction, matched_count and split metadata. Write participant_metrics.json separately.

- [ ] **Step 6: Run focused and full tests**

~~~text
python -m pytest tests/test_verifier.py tests/test_artifacts.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 7: Commit M5 decoder/artifacts**

~~~text
git add src/eating_event/verifier.py src/eating_event/artifacts.py scripts/run_event_verifier.py tests/test_verifier.py tests/test_artifacts.py
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
            {"candidate_quantile": 0.80, "f1": 0.40},
            {"candidate_quantile": 0.90, "f1": 0.35},
        ]
    )
    assert selected.candidate_quantile == 0.80
    assert selected.selection_source == "inner"
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
    selection_source: str
~~~

Implement select_inner_parameters using inner event F1 as the primary key, then higher candidate coverage, lower long_fp_fraction, lower boundary MAE and lexicographic configuration order. The function accepts inner results only.

- [ ] **Step 4: Implement nested outer evaluation**

For each outer fold, fit candidate models on outer-train, generate honest OOF verifier data within outer-train, select parameters only from inner folds, refit on outer-train and evaluate once on outer-valid. Persist the selected config and outer participant lists.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_nested_evaluation.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 6: Commit M6 nested evaluation**

~~~text
git add src/eating_event/evaluation.py scripts/run_event_verifier.py tests/test_nested_evaluation.py
git commit -m "feat: enforce nested inner-only decoder selection"
~~~

Gate: G4 evaluation is invalid if any outer metric reaches parameter selection.

### Task 10: Add resource governor and deterministic run controls

**Files:**

- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/artifacts.py
- Modify: E:/bme_compitition/bme_compitition_next/src/eating_event/config.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/audit_dataset.py
- Modify: E:/bme_compitition/bme_compitition_next/scripts/run_event_verifier.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_resources.py
- Create: E:/bme_compitition/bme_compitition_next/tests/test_reproducibility.py

- [ ] **Step 1: Write failing resource/reproducibility tests**

~~~python
def test_resource_budget_rejects_gpu_limit_above_seven_gb():
    with pytest.raises(ValueError, match="gpu_memory_limit_gb"):
        ResourceBudget(gpu_memory_limit_gb=7.5)


def test_saved_prediction_evaluation_is_deterministic(tmp_path):
    config = make_deterministic_config(tmp_path)
    predictions = make_prediction_table()
    first = evaluate_saved_predictions(config, predictions)
    second = evaluate_saved_predictions(config, predictions)
    assert first == second
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_resources.py tests/test_reproducibility.py -q
~~~

Expected: FAIL because ResourceBudget and deterministic saved-prediction evaluation do not exist.

- [ ] **Step 3: Implement bounded monitoring**

Record process RSS before and after each session, peak RSS, stage elapsed time, GPU allocated/reserved memory when CUDA is present, and timeout status. Abort the current stage when configured host fraction, GPU limit or stage timeout is exceeded.

- [ ] **Step 4: Implement deterministic seeds**

Derive module seeds from master seed, run ID, fold ID and module name. Seed NumPy and Python; if PyTorch is used, enable deterministic algorithms and record CUDA device. Write resolved config, git revision, environment and checksums before final metrics.

- [ ] **Step 5: Run resource dry-run**

~~~text
python -m pytest tests/test_resources.py tests/test_reproducibility.py -q
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/m6-resource-audit.json
~~~

Expected: tests pass; the audit either completes inside its configured timeout or exits with an explicit resource failure classification.

- [ ] **Step 6: Commit M7 resource controls**

~~~text
git add src/eating_event/artifacts.py src/eating_event/config.py scripts/audit_dataset.py scripts/run_event_verifier.py tests/test_resources.py tests/test_reproducibility.py
git commit -m "feat: add reproducibility and resource gates"
~~~

Gate: no full target-scale training starts before the resource dry-run and cache recovery pass.

### Task 11: Enforce target-only submission isolation

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
~~~

- [ ] **Step 2: Run focused tests**

~~~text
python -m pytest tests/test_submission_isolation.py -q
~~~

Expected: FAIL because submission input validation and test-truth isolation are not enforced.

- [ ] **Step 3: Implement a train-only event loader**

Add load_train_meal_events(path, allowed_participants). The loader must inspect externalid first and skip any row not in allowed_participants before reading or converting beforeTime and afterTime. It must reject allowed_participants containing test. Refactor run_submission.py to discover train records first, derive the train participant set, call this loader once for train labels, and pass an empty truth tuple for every test record.

Before reading test files, validate that external_data_references and test_truth_references are empty and that the submission contract hash equals the trained contract hash. The runner must not call load_meal_events on the mixed metadata file.

- [ ] **Step 4: Implement deterministic serialization**

Serialize participant_id, session_id, start_ms and end_ms. Sort by participant_id, session_id, start_ms and end_ms. Write the isolation report and skipped-file provenance beside the submission artifact.

- [ ] **Step 5: Run focused and full tests**

~~~text
python -m pytest tests/test_submission_isolation.py -q
python -m pytest -q
~~~

Expected: all tests pass.

- [ ] **Step 6: Commit G6 isolation**

~~~text
git add src/eating_event/data/manifest.py scripts/run_submission.py src/eating_event/artifacts.py tests/test_manifest.py tests/test_submission_isolation.py
git commit -m "fix: enforce target-only submission isolation"
~~~

Gate: G6 passes only when any external or test-truth reference fails closed and a test metadata row with invalid timestamps does not make the train-only loader fail.

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
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/g0-g1-audit.json
python scripts/run_event_verifier.py --config configs/example.local.yaml --cache-dir artifacts/formal-cache --output artifacts/g2-g4-verifier.json
python scripts/run_submission.py --config configs/example.local.yaml --cache-dir artifacts/formal-cache --output artifacts/g6-submission.json
~~~

Do not start the next command when the previous gate fails. Record the failure classification and next action before continuing.

- [ ] **Step 5: Perform plan self-review**

Check that every Detailed Design section maps to a task, every task has exact files and tests, all public names agree with Task 1, and no step introduces external data, test truth, GT-neighbor sampling, cross-gap interpolation or all-participant fallback.

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
