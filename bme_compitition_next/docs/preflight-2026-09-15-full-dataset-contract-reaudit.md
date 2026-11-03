# Full Dataset Contract Re-audit Preflight

日期：2026-09-15  
状态：Preflight revision-2 完成；`GO WITH RISKS`  
前置 revision：`docs/preflight-2026-09-15-participant-eligibility-exclusion.md`  
本 revision：替代此前的 `267` event denominator 方案；模型架构仍冻结。

## Goal

对 target-train 的 raw audit、sensor 原始索引、meal metadata 和 user profile 做一次完整 source-contract reconciliation，显式排除所有无法在 `processed` sensor session 上形成可评估输入的事件，并为 participant/event denominator 建立可复现 hash。

本次将 `AC3` 明确跳过，并同时处理其他同类不可用事件；不物理删除 raw，不修复或合成 sensor，不把无法生成输入的 label 计入 G1 recall。

## Success metrics

全量 contract audit 必须固定以下结果：

| 指标 | 结果 |
|---|---:|
| full raw records discovered/audited | 1161 / 1161 |
| processed raw records | 1127 |
| explicit raw skips | 34 |
| raw skip reasons | undecodable=16；missing_valid_gyro_timestamp=18 |
| organized raw participant count | 43 |
| meal metadata participant count | 43 |
| source union participant count | 44 |
| raw/meal participant intersection | 42 |
| participant-level eligible sensor cohort | 41 |
| valid meal events | 281 |
| usable processed-session overlap | 246 |
| excluded events | 35 |

35 个 excluded events 必须按以下原因精确分布：

```text
metadata_only_no_session: 3
overlap_only_invalid_sensor: 20
no_index_session_overlap: 12
```

新的 sensor-backed event denominator 为 `246`，event denominator SHA256：

```text
1d98c9472a2904ec4c6507fd8792472ade84062f395f4fb4928656c1bd00d687
```

raw manifest SHA256 和 processed-file denominator SHA256 保持：

```text
manifest_sha256: dbc178582d1868758afb4241206e0c79011e666119b9814a4d81f9307f4942f5
denominator_sha256: 147ed5d46f16ef0f4dbcab200322914b320d41766a5b91c1d8a07ffaba50d469
```

## Constraints

- raw files、raw index 和 source CSV 只读；不复制、不移动、不重写。
- 所有 raw file failure 必须保留 canonical status；unexpected failure 继续 fail-closed。
- participant-level exclusion：`AC3`、`HNU21018`、`HNU21042` 不进入 formal sensor cohort。
- event-level exclusion：任何非 `usable_processed_overlap` 的 meal event 不进入 G1 event denominator。
- `6C7` 有 raw sensor 但无 meal label，保留为 eligible participant audit record，不制造事件。
- user profile-only IDs 不属于当前 sensor/meal source union，不进入训练或事件分母，但保留 source reconciliation。
- 不改变模型架构、timebase、window、feature、split seed、threshold grid、OOF、verifier、decoder 或 official metric。
- test truth、external data、GT-neighbor sampling、cross-gap interpolation 和 file cap formal validation 仍禁止。

## Prior art and current evidence

原始 full raw audit 已审计全部 `1161` records，确认 `1127` processed 与 `34` raw-invalid。新的 re-audit artifact 为：

`artifacts/g1-participant-exclusion-eligibility-v2.json`

四层 source reconciliation：

- `sensororiginaldata_system` participant set 与 organized raw audit 完全一致：43 个；没有 sensor-index-only 或 raw-without-sensor-index participant。
- meal metadata 有 43 个 participant；唯一 `meal_metadata_only` participant 是 `AC3`，有 3 个事件但没有 sensor session。
- organized raw-only participant 是 `6C7`，有 6 个 processed session 但没有 meal event。
- user profile 表有 55 个非-test ID，其中 11 个只存在于 profile 表，不进入 target sensor/meal union。

事件级完整分类显示：246 个事件可由 processed session 覆盖；20 个只重叠 raw-invalid session；12 个完全不重叠任何 indexed session；3 个属于 AC3 metadata-only。此前只排除 HNU21018/HNU21042 的 14 个事件是不完整的。

## Baseline

旧的 incomplete G1 fold metrics 继续作废。旧 M0 q50 + GroupNorm 的 event F1=`0.17284` 仍是历史 sentinel，不是 246-event denominator 下已重验证的 baseline。

V1 必须使用 41 个 eligible sensor participant、new eligibility artifact 和固定 `20260910` split contract 重建 trusted-baseline contract；不能修改 expected metric、metric implementation 或 seed。

## Candidate approaches

### A. 推荐：participant + event 双层 eligibility

participant 层只允许有 processed session 的 participant 进入 folds；event 层只允许与 processed indexed session overlap 的事件进入 coverage denominator。保留所有 excluded provenance 和 hashes。

### B. 只排除 AC3/HNU21018/HNU21042

拒绝。它仍会把 12 个无 index overlap 事件和其他 6 个只落在 invalid session 的事件混入或不透明丢失。

### C. 保留全部 281 个事件，用 zero coverage 表示不可用

拒绝。无 sensor input 的事件不能区分模型漏检与数据缺失，会污染 G1 gate。

### D. 尝试根据 metadata 时间修复 session 或合成输入

本轮拒绝。没有独立证据支持修复，且会改变 raw/label contract。

## Critical assumptions

1. indexed session bounds 是 event-to-sensor 对齐的正式 contract；没有 overlap 的事件不能纳入 sensor-backed evaluation。置信度：高；验证：V0 event-level audit。
2. `usable_processed_overlap` 足以作为 G1 event denominator 的准入条件；置信度：中高；验证：V2 G1 artifact isolation。
3. 41 个 eligible participant 足以形成既定 5-fold participant split；置信度：高；验证：V1/V2 split contract。
4. raw-invalid session 中的 20 个事件不应通过 participant 内其他 session 的存在被挽救；若事件本身只落在 invalid session，仍无可用输入。置信度：高。
5. user profile-only IDs 不属于当前 target-train sensor/meal union；置信度：中；保留为 provenance，不进入模型分母。

## Risks

- 246 是 sensor-backed research denominator，不是官方测试集分数或稳定泛化结论。
- 35 个事件的排除可能产生 label-selection bias，尤其是 raw-invalid participant 的事件全部被排除。
- 12 个无 indexed-session overlap 事件可能反映时间轴/索引质量问题，不能当作随机缺失。
- 事件级排除会使某些 participant 的 valid-event 数下降；必须输出 participant event status counts，不能只报 pooled F1。
- source CSV 与 organized raw 的导出关系没有官方 provenance 文档；当前结论基于文件内容和一致性对账。

## Validation experiments

### V0：full source-contract audit（已完成）

读取 immutable full raw audit 和四层 source tables，生成 `participant_eligibility_v2` artifact。验收：counts、source sets、event status counts、三份 hash 一致。

### V1：trusted baseline contract revalidation

从 eligibility artifact 读取 41 个 eligible sensor participant；固定 baseline ID、seed、valid fraction、expected metric；验证 participant set、split manifest 和 hashes。

### V2：processed-only formal G1

正式 G1 必须读取 eligibility artifact：cache/fold 只允许 1127 processed records 中的 41 participant；event coverage 只允许 246 个 `usable_processed_overlap` events；无 file cap、无 verifier。

### V3：isolation and denominator audit

扫描 cache、fold、OOF、prediction、metric：AC3/HNU21018/HNU21042 不得出现；35 个 excluded event 不得进入 formal event denominator；event hash 必须贯穿 artifact。

## Kill criteria

- 发现新的 meal participant 没有 raw/sensor source，或 source set/hash 漂移：停止并重新做 contract review。
- 任一非 `usable_processed_overlap` event 进入 G1 denominator：结果作废。
- excluded participant/event 出现在 cache、fold、model、OOF 或 metric：结果作废。
- baseline contract 无法在 41 participant 下重建：停止，不改 seed/metric 规避。
- 任一 G1 fold pooled coverage recall `<0.90`：G1 fail，不进入 Task 6。
- 发现 index bounds 不能作为 event alignment contract：`REDESIGN`，不继续调模型。

## Recommendation

`GO WITH RISKS`，但只允许执行 V1 → V2 → V3。此前 `267` denominator 方案作废，新的 formal event denominator 固定为 `246`，participant exclusion 固定包含 `AC3`、`HNU21018`、`HNU21042`。模型架构不 reopen。

## Confidence

中等偏高。四层 participant 对账和 281 个事件的逐事件分类已经完成；剩余风险主要是 source export 的外部 provenance 与 exclusion 后 cohort 的科学代表性，而不是当前审计计算本身。

## Routing record

```text
workflow_path: RESEARCH
execution_mode: INLINE
execution_backend: inline Codex
scope: full source-contract re-audit and participant/event eligibility only
budget: one full immutable audit reconciliation; no model training in this review
fallback: Root Cause Review if source sets, event mapping, or hash contract changes
review/escalation: any new unusable class, membership leakage, baseline mismatch, or G1 fold < 0.90
architecture: frozen; no model reopen
```
