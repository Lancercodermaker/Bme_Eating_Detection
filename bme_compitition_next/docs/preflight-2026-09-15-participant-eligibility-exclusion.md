# Participant Eligibility Exclusion Preflight

日期：2026-09-15  
状态：Preflight 完成；`GO WITH RISKS`，等待 bounded implementation 重新验证  
范围：仅处理 raw-invalid participant 的临时 eligibility/denominator 决策；模型架构保持冻结。

## Goal

在不删除或修复不可用原始数据的前提下，建立一个可审计、可回滚的 participant-level eligibility contract，使正式 G1 只使用有至少一个 `processed` session 的 participant，同时明确记录被排除 participant、受影响事件和新的指标分母。

这不是对 HNU21018 或 HNU21042 的数据修复，也不是为了提高分数而选择 participant。它是对已确认的 acquisition/data-contract failure 的临时研究范围定义：这些 participant 仍保留在 raw manifest、skip audit 和 provenance 中，但不进入本轮 formal G1、cache、fold、训练、阈值选择、OOF、verifier 或指标。

## Success metrics

Preflight/设计验收必须满足：

- 全量 raw audit 仍发现并审计 `1161` 个 target-train sensor records；其中 `1127` 个 `processed`，`34` 个显式 skipped。
- skip reason 保持为 `undecodable=16` 和 `missing_valid_gyro_timestamp=18`，没有新的未分类 failure。
- participant-level denominator 从审计得到 `43` 个 target-train participant，其中 `41` 个 eligible、`2` 个 ineligible：`HNU21018`、`HNU21042`。
- metadata 中的 `281` 个有效事件中，两个 ineligible participant 的 `14` 个事件被显式标注为 excluded，临时有效事件分母为 `267`；不把 `267` 称为官方或稳定结果。
- participant/session eligibility、manifest SHA256 和 denominator SHA256 写入新的不可变 artifact；当前审计 hash 为：
  - manifest：`dbc178582d1868758afb4241206e0c79011e666119b9814a4d81f9307f4942f5`
  - denominator：`147ed5d46f16ef0f4dbcab200322914b320d41766a5b91c1d8a07ffaba50d469`
- 后续 bounded G1 使用全部 eligible processed sessions、无 file cap，并要求 5 个 outer fold 的 pooled candidate coverage recall 均达到 `>= 0.90`。
- 新 route 不读取 test truth、不引入 external data、不跨 gap 插值、不修补或合成 GYRO，不改变 frozen model/window/feature/split/OOF/verifier/decoder/metric contract。

## Constraints

- raw data 只读；不物理删除、移动、复制或改写原始文件。
- `skipped_malformed` 与 `skipped_missing_required_imu` 必须保留在 manifest；unexpected parser/runtime failure 继续 fail-closed。
- HNU21018/HNU21042 的 participant identity 不能从 manifest 中静默移除，必须有 `participant_status=ineligible_no_processed_session` 和 exclusion reason。
- exclusion 只对本轮 target-train research denominator 生效；不得据此修改官方 test/submission 输入契约，也不得把 test participant 当作训练 participant。
- 旧的失败 G1 artifact 和不完整 fold metrics 保持 immutable，新的 audit/G1 使用新的 run id 和输出路径。
- 当前 frozen architecture、G1 quantile grid、participant split strategy、trusted baseline metric 和后续 M5 seed 不因本次 denominator amendment 改写。

## Prior art and current evidence

全量 processed-only manifest audit 已完成：`artifacts/g1-processed-only-manifest-audit.json`。关键事实是：

| 项目 | 结果 |
|---|---:|
| discovered/audited records | 1161 / 1161 |
| processed records | 1127 |
| explicit skipped records | 34 |
| undecodable | 16 |
| missing valid GYRO timestamp | 18 |
| target-train participants | 43 |
| eligible participants | 41 |
| ineligible participants | 2 |
| metadata valid events | 281 |
| excluded participant events | 14 |
| temporary valid event denominator | 267 |

Root Cause Review `artifacts/g1-processed-only-root-cause-review-20260915/review.json` 已确认：两个 participant 的全部 session 都 raw-invalid；HNU21018 的 9 个有效事件、HNU21042 的 5 个有效事件均落在这些无有效 IMU 输入的 session ranges 中。这是系统性 acquisition/data-contract failure，不是可以通过本地 parser/threshold 优化恢复的信号。

可信旧参照仍为 M0 q50 + GroupNorm，event F1=`0.17284`。它只能作为新 denominator 下的可比性 sentinel，不能自动当成新分母上的已复现 baseline。

## Baseline

当前 formal G1 的五个 fold metrics 因使用 incomplete population 而作废，不得用于模型、threshold、verifier 或 nested evaluation 选择。

新的 baseline 处理顺序：

1. 先从 canonical eligibility manifest 重新导出 41 个 eligible participant；
2. 用既有 participant-frozen seed `20260910`、valid fraction `0.20` 和既有 baseline ID 做 trusted-baseline contract revalidation；
3. 不修改既有预期 metric `0.17284`、split rule 或 metric implementation；
4. 如果 baseline 无法在新 denominator 下以相同协议复现，则停止正式 G1，归类为 `DATA/PIPELINE` 或 `ASSUMPTION`，不得用新分数强行替换旧参照。

## Candidate approaches

### A. 推荐：temporary participant-level exclusion

将两位 participant 保留为 provenance，但设置 `ineligible_no_processed_session`。只有 participant eligible 且 record status 为 `processed` 的数据进入 formal pipeline。该方案与当前已完成的 file-level raw failure audit 一致，最小化对冻结架构的改动，并可明确计算 denominator/hash。

### B. 保留 participant、用空输入或零填充继续训练

拒绝。没有可用 GYRO/IMU session 时，空输入、零填充或 artificial session 会让输入和标签关系失真，并把 acquisition failure 伪装成模型可学习样本。

### C. 原始数据 repair、插值或 binary recovery

本轮拒绝。它们会改变 raw data contract，且当前证据不足以证明恢复后的信号科学有效；如未来获得独立的原始数据修复依据，应另开 data-recovery review。

### D. 继续沿用全量 participant denominator，并把无输入 participant 当作 zero-coverage

仅保留为敏感性分析，不作为本轮 G1 的训练/选择分母。它会把“模型没有数据可用”与“模型漏检”混在同一 recall 中，无法支持当前 candidate coverage gate。

## Critical assumptions

1. `no processed session` 是足以阻断该 participant 进入 IMU-based formal G1 的 data-contract 条件，而不是一次偶然的 parser bug。当前证据：19 个 session 全部 raw-invalid，且失败类别跨 participant 一致；置信度：高。
2. exclusion 仅作用于 formal research denominator，不代表这些 participant 在真实竞赛总体中的标签无效；置信度：高。
3. 41 个 eligible participant 仍足以形成 5-fold participant-frozen G1；置信度：高，但需实际 split/audit 验证。
4. 14 个被排除事件不会让剩余 267 个事件成为系统性偏斜、不可代表的 denominator；置信度：中低，必须通过 participant/event coverage 报告确认。
5. 旧 M0 metric 可以作为可比性 sentinel，而不是未经重跑就作为新 denominator baseline；置信度：中。

## Risks

- 这是有效分母变化，不可把排除后的 F1 与未排除全量分母的 F1 直接比较。
- 两位 participant 的全部事件被排除，可能引入 participant/domain selection bias；本轮结果最多称为 `temporary eligible-cohort result`。
- 如果无效数据不是随机缺失而是某种设备/采集条件的代表，41 人 cohort 可能高估泛化能力。
- participant 数量减少可能改变 outer fold composition；必须记录新的 split manifest/hash，不能复用失败 G1 fold metrics。
- 后续若发现还有 participant 无 processed session、skip class 增加或 manifest hash 漂移，本设计立即失效并重新进入 Root Cause Review。

## Validation experiments

### V0：eligibility materialization

从现有 canonical audit 重新生成新的 participant eligibility artifact，验收 `1161/1127/34`、`43/41/2`、`281/14/267` 和两份 hash 均一致。所有 34 个 skip 都必须落入已批准的两个 canonical class。

### V1：trusted baseline contract revalidation

在不改 seed、split rule、metric 或 expected metric 的前提下，用 41 个 eligible participant 验证 baseline 输入清单、participant split 和 hash contract。任何 membership violation、test leakage 或 baseline 不可比都停止后续 route。

### V2：processed-only formal G1

仅使用 `processed` records 且按 participant eligibility 过滤；不使用 `max-files-per-participant`。运行既有 5 outer folds 和 frozen quantile grid `(0.70, 0.80, 0.90)`，只做 candidate coverage，不启动 verifier。新 artifact 必须写入 eligible participant list、excluded participant list、fold membership、cache/manifest hash 和 skip summary。

### V3：denominator isolation audit

扫描 cache、fold、model、prediction 和 metric artifacts：`HNU21018`、`HNU21042` 以及它们的 14 个事件不得出现于任何 formal input/metric；但必须存在于 audit/provenance/exclusion report。任何反例都使 G1 结果作废。

## Kill criteria

- 任何 expected skip 之外的 parser/runtime failure 被归入 skip：停止并归类 `IMPLEMENTATION`/`DATA_PIPELINE`。
- 任何 excluded participant/session/event 进入 cache、fold、model、OOF、prediction 或 metric：结果作废，回到 eligibility interface。
- participant/session、manifest hash、denominator hash 或 split membership 不完整：停止，不生成可选模型结果。
- trusted baseline 无法在新 denominator 下完成可比性 revalidation：停止并重开 baseline/data-contract review。
- 任一 G1 outer fold pooled coverage recall `<0.90`：G1 fail，不进入 Task 6。
- 发现除 HNU21018/HNU21042 外还有无 processed session participant，或出现新的 skip class：停止并重新做 Preflight/Root Cause Review。
- 14 个事件的排除造成明显非代表性且无法通过敏感性分析解释：本临时 route `NO-GO/RENEGOTIATE`，不能继续用 267-event 结果做正式选择。
- 任何结果使用 test truth、external data、GT-neighbor sampling、cross-gap interpolation 或改动 frozen architecture：结果作废。

## Recommendation

`GO WITH RISKS`，仅限于一个 bounded participant-eligibility amendment：先完成 V0/V1，再运行一次新的 processed-only formal G1。该决定允许继续验证，不宣称数据问题已被修复，也不允许直接进入 verifier、nested evaluation 或 full-scale training。

如果 V0/V1 或 V2 失败，应停止实现路线；如果 V2 通过，才允许按原计划进入后续 gate。模型架构仍保持 frozen，当前 reopen 仅限 Preflight/Detailed Design 的 denominator/data contract。

## Confidence

中等偏高。raw-invalid 证据和 participant eligibility 事实明确，temporary exclusion 的工程边界可执行；但科学代表性和排除后分数的外部有效性仍未知，因此不能给出 `GO` 或稳定 F1 承诺。

## Routing record

```text
workflow_path: RESEARCH
execution_mode: REVIEW_ONLY for this turn; bounded implementation after review artifact
execution_backend: inline Codex
scope: participant eligibility / denominator amendment only
architecture: frozen; no model reopen
next_action: V0 eligibility materialization -> V1 trusted baseline revalidation -> V2 formal G1
fallback: Root Cause Review if any eligibility, hash, baseline, or representativeness assumption fails
circuit_breaker: no random seed/threshold/budget changes after a failed gate
```
