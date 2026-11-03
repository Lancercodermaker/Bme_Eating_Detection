# Formal G1 Local Experimentation Stop Decision

日期：2026-09-19  
范围：结束当前 Formal G1 局部实验阶段；不启动新实验、不训练、不修改 production 或正式 gate。

## 最终阶段状态

```text
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```

本记录直接复用 [Bounded Proposal Set probe report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-bounded-proposal-set-feasibility-probe-v1/report.json)，不重算历史结果。

## 1. Formal G1 当前状态

正式候选基线 A 仍为 207/234，Formal G1 要求保持不变：234-event cohort、IoU > 0.25、participant-disjoint、5/5 outer folds coverage recall >= 0.90。

| Outer fold | A baseline | Frozen proposal union | G1 状态 | 缺口 |
|---|---:|---:|---|---:|
| outer-0 | 46/50 = 0.920 | 47/50 = 0.940 | pass | 0 |
| outer-1 | 46/49 = 0.939 | 47/49 = 0.959 | pass | 0 |
| outer-2 | 45/53 = 0.849 | 47/53 = 0.887 | fail | 1 event；需 48/53 才达到 0.90 |
| outer-3 | 30/35 = 0.857 | 32/35 = 0.914 | pass | 0 |
| outer-4 | 40/47 = 0.851 | 44/47 = 0.936 | pass | 0 |

因此，proposal union 的诊断结果为 217/234，但仍只有 4/5 folds 达标。它不改变正式 Formal G1 状态，也不构成 full training 授权。

## 2. Proposal 接口的两个独立结论

### 正面机制证据

在已经反复用于开发诊断的 participant-disjoint folds 上，固定的 `P_new = P_A ∪ P_extra` 恢复了 10 个原始 missing events，且没有 newly lost event。恢复事件来自多个 fold 和多个 participant，说明 proposal-set 接口确实能保留单一 thresholded interval stream 之前丢失的 score-support/boundary hypotheses。

### 预注册负结论

该冻结规则仍未达到 5/5 fold G1，按预注册停止。不得修补 outer-2 特定事件，不得按事件定制边界、cap 或 threshold，不得继续参数搜索，也不得把该规则扩大解释为整个候选架构均不可行。

## 3. Candidate 规模与代价

| 项目 | 数量 |
|---|---:|
| A baseline proposals | 3,903 |
| P_extra proposals | 22,149 |
| 与 A 完全相同的 extra intervals | 77 |
| 新增非重复 intervals | 22,072 |
| P_new union | 25,975 |

因此 proposal 集合从 3,903 增加到 25,975，规模为约 6.66 倍。资源审计通过：运行约 20.1 s，峰值 RSS 约 1.02 GiB，诊断产物约 13.4 MB，未发生模型 fit。

candidate-level one-to-one precision 仅是 proposal 级诊断指标，不是最终系统 precision：本轮没有 ProposalSet→16D candidate feature adapter、verifier、decoder 或最终 event pipeline。union 的候选 FP 负担明显增加，但不能将其直接命名为最终系统误报率。

## 4. 阻断面分离

### Coverage 阻断

outer-2 union 仍为 47/53，低于 0.90；因此 Formal G1 仍 FAIL，full training 继续 BLOCKED。

### 下游接口缺口

当前 `build_event_candidates` 接受 thresholded selected-window stream，不接受任意 `BoundedProposalSet` interval。`boundary_expanded` 和部分 proposal hypotheses 不能直接进入现有 16D candidate-feature contract。本轮不自动实现 adapter、不训练 verifier、不进入 M5/G4/M6。

### 资源状态

资源不是当前阻断：冻结预算内完成，`RESOURCE_STATUS = PASS`。candidate 数量和下游 verifier 负担属于后续设计投入决策，不被伪装成新的 G1 门槛。

## 5. 已关闭方案及适用范围

以下分支按各自预注册或冻结结论关闭；关闭范围只针对对应假设，不外推为所有未来设计均无效：

- temporal representation expansion：`BOUNDED_TEMPORAL_REPRESENTATION_HYPOTHESIS = UNSUPPORTED`；不再增加 temporal features。
- decision-function probe：当前冻结状态 `DECISION_FUNCTION_EFFECT = UNSUPPORTED`；不重开 classifier search。
- event-balanced positive weighting：E=206/234，低于 A=207/234；关闭 weight sweep、clipping 和 threshold compensation。
- frozen A 3 s transfer：有 score/support 变化，但 event-level transfer unsupported；production stride 保持 7.5 s。
- aggregation tournament：历史 preregistration 保留，当前工作树未找到对应 result report；本记录不把来源缺失转化为新结果，也不重跑 aggregation。
- 本轮 bounded proposal rule：恢复 10 个事件但仍未达到 G1；关闭该固定规则的后续 cap、boundary、threshold 搜索。

这些结果共同保留两类证据：局部机制证据支持 proposal interface 值得被视为设计变量；正式 G1 证据仍不足以放行下游或 full training。

## 6. 保存的模型、scores、provenance 与入口

本轮未覆盖 production artifacts。保留：

- [冻结 spec](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/configs/formal-g1-bounded-proposal-set-feasibility-probe-v1.json)
- [spec SHA-256 sidecar](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/configs/formal-g1-bounded-proposal-set-feasibility-probe-v1.sha256)
- [逐事件结果](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-bounded-proposal-set-feasibility-probe-v1/event-results.jsonl)
- [proposal provenance](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-bounded-proposal-set-feasibility-probe-v1/proposal-provenance.jsonl)
- [fold results](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-bounded-proposal-set-feasibility-probe-v1/fold-results.json)
- [既有 A OOF scores、thresholds、fold manifest 与 models](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-event-balanced-candidate-objective-probe-v1)
- [可复现入口](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/scripts/run_bounded_proposal_set_probe.py)

入口仅作为已冻结诊断的可复现记录；再次运行或建立确认性证据需要新的明确授权。

## 7. 阶段决策

当前项目不再继续 Formal G1 局部参数/规则实验。下一步不是修补 outer-2，也不是继续现有规则搜索，而是由项目负责人明确新的设计与投入决定：是否批准一个实质不同的候选接口/adapter 设计、接受其 candidate 与 verifier 成本，并另行定义符合数据治理的确认方案。

在该决定之前，保留 Formal G1 阻断、full training 阻断和 production 不变。
