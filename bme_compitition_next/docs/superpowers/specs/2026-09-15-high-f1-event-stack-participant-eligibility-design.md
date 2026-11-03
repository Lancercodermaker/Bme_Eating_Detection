# High-F1 Event Stack Participant Eligibility Amendment — Detailed Design

日期：2026-09-15  
状态：Conditional design approval；`GO WITH RISKS`
前置文档：`docs/preflight-2026-09-15-participant-eligibility-exclusion.md`  
适用范围：target-train formal G1 的临时 eligible cohort；不修改模型架构。

## 1. Design decision

当前 dataset contract 允许 file-level expected skip，但要求每个 participant 至少有一个 processed session。全量 audit 证明该 participant-level 假设不成立：`HNU21018` 与 `HNU21042` 的全部 session 都无 usable processed output。

本 amendment 采用 participant-level temporary exclusion：

- raw file 仍只读、仍保留在 discovered manifest 和 audit provenance；
- 34 个 raw-invalid file 继续使用 canonical file status；
- 两个 participant 追加 participant-level status `ineligible_no_processed_session`；
- 只有 participant status 为 eligible 且 file status 为 `processed` 的 records 进入 formal G1/cache/fold/model/OOF/verifier/metric；
- 两个 participant 的 14 个 valid event labels 不进入本轮 effective denominator，但必须进入 exclusion report；
- 这不是 raw repair、imputation、label deletion 或 architecture change。

## 2. Population and denominator contract

基于 `artifacts/g1-processed-only-manifest-audit.json`：

| 层级 | 数量 | 说明 |
|---|---:|---|
| discovered target-train sensor records | 1161 | full audit，无 file cap |
| processed records | 1127 | 可进入 processed-only pipeline 的 file records |
| skipped records | 34 | 16 undecodable + 18 missing valid GYRO timestamp |
| target-train participants | 43 | participant session eligibility keys |
| eligible participants | 41 | 至少一个 processed session |
| ineligible participants | 2 | HNU21018、HNU21042 |
| metadata valid events | 281 | 43 个 target participant metadata keys 的有效事件 |
| excluded participant events | 14 | HNU21018: 9；HNU21042: 5 |
| effective temporary event denominator | 267 | 只用于本轮 eligible-cohort research |

Manifest hash：`dbc178582d1868758afb4241206e0c79011e666119b9814a4d81f9307f4942f5`。  
Denominator hash：`147ed5d46f16ef0f4dbcab200322914b320d41766a5b91c1d8a07ffaba50d469`。

两个 hash 必须作为 eligibility input 的身份，而不是仅作为日志字符串。任何新 audit、cache 或 fold 如果 hash 不匹配，必须停止并生成新的 run artifact。

## 3. Data and status schema

### 3.1 File status

沿用当前 canonical statuses：

```text
processed
skipped_malformed
skipped_missing_required_imu
skipped_missing_index
skipped_invalid_session
skipped_no_valid_timestamp
skipped_cache_missing
```

本 amendment 仅批准当前已证实的：

```text
skipped_malformed / undecodable
skipped_missing_required_imu / missing_valid_gyro_timestamp
```

任何未列出的错误必须 fail-closed，不得被映射为 expected skip。

### 3.2 Participant status

每个 target-train participant 必须有一条 eligibility record：

```text
participant_id: string
participant_status: eligible | ineligible_no_processed_session
discovered_session_count: int
processed_session_count: int
skipped_session_count: int
excluded_event_count: int
eligibility_reason: string
manifest_sha256: string
denominator_sha256: string
```

对于 HNU21018/HNU21042：`processed_session_count=0`、`participant_status=ineligible_no_processed_session`，不能简单从 participant list 中删除。

### 3.3 Effective input predicate

formal target-train record 的唯一准入条件为：

```text
record.status == "processed"
and participant_status == "eligible"
and participant_id not in excluded_test_or_unknown_ids
```

有效事件的唯一准入条件为：

```text
event.participant_id belongs to an eligible participant
and event is valid under the existing meal metadata contract
```

不得按 event 数量、模型表现、fold 结果或窗口覆盖率再做第二次人工选择。

## 4. Processing flow

```text
full raw/index discovery
    -> canonical file audit (read-only)
    -> file status + raw failure provenance
    -> participant/session eligibility
    -> eligible participant/event denominator artifact
    -> trusted baseline contract revalidation
    -> processed-only cache materialization
    -> participant folds
    -> formal G1 candidate coverage
```

关键顺序：participant eligibility 必须在 cache/fold 之前确定；cache 不能通过“先生成再过滤”绕过 eligibility；fold membership 必须从同一个 eligibility artifact 导出。

## 5. Baseline and split contract

- G1 仍使用 5 outer participant folds。
- G1 quantile grid 仍为 `(0.70, 0.80, 0.90)`。
- trusted baseline 仍使用 baseline ID `m0-q50-groupnorm`、participant-frozen split seed `20260910`、valid fraction `0.20` 和既有 expected event F1 `0.17284` 作为 sentinel contract。
- M5 的 `M5_SELECTION_SEED=20260910` 与 evaluation seeds `(20260910, 20260911, 20260912)` 不在本 amendment 中修改。
- 旧的 incomplete G1 fold metrics 不可复用；所有新 fold/output 使用新 run ID 和新 hash。

如果 41 participant 无法形成 5 个有效 outer fold，或者 split artifact 无法证明 participant disjoint，则 formal G1 停止，不通过减少 fold、改 seed 或放宽 split 来规避。

## 6. Artifact contract

建议新 run 使用独立路径，避免覆盖失败证据：

```text
artifacts/g1-participant-exclusion-manifest-audit.json
artifacts/g1-participant-exclusion-eligibility.json
artifacts/g1-participant-exclusion-coverage.json
artifacts/g1-participant-exclusion-cache/
artifacts/g1-participant-exclusion-folds/
```

至少写入：

- `discovered_file_count`, `audited_file_count`, `processed_file_count`, `skipped_file_count`；
- `skipped_reason_counts`；
- full participant eligibility map；
- excluded participant IDs and event counts；
- manifest/denominator/cache schema hashes；
- participant fold membership and split seed；
- excluded IDs absence audit；
- command/config/code revision and run timestamps；
- G1 gate result and failure classification。

任何 formal metrics artifact 如果缺少 eligibility/hash references，都只能是 diagnostic output，不能用于模型选择。

## 7. Validation gates

### V0 — eligibility artifact

Acceptance：counts/hash/IDs 与本设计一致，所有 discovered record 恰有一个 file status，所有 participant 恰有一个 participant status。

### V1 — trusted baseline revalidation

Acceptance：新 participant set、split、metric implementation 和 data contract 可追溯；无 test truth、无 hidden fallback、无 hash mismatch。

### V2 — formal G1

Acceptance：

- all `1127` processed records are considered unless an explicit, audited cache failure occurs；
- no `max-files-per-participant`；
- 5 outer folds are participant-disjoint；
- every fold pooled candidate coverage recall `>=0.90`；
- expected skips do not fail the gate；
- unexpected failure does fail closed；
- no verifier or Task 6+ work starts before this gate passes。

### V3 — isolation audit

Acceptance：HNU21018/HNU21042 and their 14 events are absent from formal cache/fold/model/metric inputs, and present in audit/provenance/exclusion outputs。

## 8. Failure classification and escalation

| Failure | Classification | Action |
|---|---|---|
| new unclassified parser/runtime error | IMPLEMENTATION / DATA_PIPELINE | stop; debug earliest affected gate |
| excluded ID enters formal artifact | IMPLEMENTATION | invalidate run; repair eligibility boundary |
| hash or membership missing | DATA/PIPELINE | stop; rebuild artifact contract |
| baseline not comparable | ASSUMPTION | Root Cause Review; no G1 |
| fold coverage `<0.90` | DATA/PIPELINE or ARCHITECTURE after evidence | G1 fail; no verifier |
| additional no-processed participant | ASSUMPTION | reopen Preflight/Detailed Design |
| cohort appears materially nonrepresentative | REQUIREMENT_INFEASIBLE / ASSUMPTION | NO-GO/RENEGOTIATE temporary exclusion |

The model architecture is not reopened by this amendment. Architecture reopen is allowed only by the pre-existing gates after a valid eligible-cohort G1 and subsequent evidence, not as a shortcut around denominator failure.

## 9. Implementation boundary

The next implementation may modify only:

- participant eligibility materialization;
- formal G1 input filtering and artifact references;
- test coverage for participant exclusion and isolation;
- audit/report output paths.

It may not modify:

- raw parser semantics beyond the already-approved canonical failure mapping;
- timebase, windows, features, model, threshold grid, decoder or official metric;
- raw data contents or external data policy;
- formal file cap rules;
- OOF fallback policy or downstream Task 6+ code.

## 10. Decision

Decision：`GO WITH RISKS` for the bounded amendment.  
Allowed next action：implement V0/V1 eligibility boundary, then rerun formal G1.  
Not allowed：把 267-event result称为官方/稳定结果，或在 G1 之前启动 verifier、nested evaluation、full-scale training。
