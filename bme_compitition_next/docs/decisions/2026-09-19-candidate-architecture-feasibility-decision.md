# Candidate Architecture Feasibility Decision

日期：2026-09-19  
范围：只读证据审查与设计决定；不训练、不推断、不调参、不修改 production 或正式 gate。

## 结论

当前候选层的局部 objective、representation、decision-function、stride 和已记录的 aggregation 方向均没有把 Formal G1 candidate coverage 稳定推进到要求线。问题最具体地落在现有接口假设：

```text
每个窗口给一个 score
    -> 一个数值 threshold
    -> 一条 thresholded interval stream
    -> verifier 只能筛选这条 stream
```

本决定推荐重开的是“candidate proposal interface”，不是继续搜索 HGB 参数、weight、threshold、stride 或 aggregation 参数。推荐方向是一个 coverage-preserving、bounded multi-hypothesis interval proposal layer；保留现有 `imu_stats_v1`、A scorer、participant-disjoint protocol、verifier 和 official evaluator，先把候选集合从单一 thresholded interval stream 改成受控的 proposal set。

这只是设计批准请求，不是 architecture implementation authorization。

```text
DESIGN_REVIEW_ELIGIBILITY = ELIGIBLE
RECOMMENDED_DESIGN_DECISION = REOPEN_CANDIDATE_PROPOSAL_INTERFACE
ARCHITECTURE_CHANGE_AUTHORIZATION = NOT_GRANTED
ARCHITECTURE_KILL_EVIDENCE = SUFFICIENT_FOR_INTERFACE_REOPEN_ONLY
DECISION_FUNCTION_EFFECT = UNSUPPORTED
PRODUCTION = UNCHANGED
FULL_TRAINING = BLOCKED
ARCHITECTURE_CHANGE = NOT_EXECUTED
```

## 1. 架构重开条款与条件映射

原始 detailed design 的 architecture reopen 条款是：

> architecture reopen 只有在：
>
> 1. candidate coverage 多个 participant-frozen split 持续不足；
> 2. event F1 多 seed、多 split 持续无法超过可信 baseline；
> 3. verifier 只在单一小 split 有效；
> 4. long FP、boundary MAE 或 worst participant F1 在扩大验证后持续恶化；
> 5. loss/window 指标提升但 event F1 持续不提升；
> 6. 发现 test、GT 邻域、跨 gap 插值等泄漏；
> 7. full target scale 无法满足资源约束。

来源：[detailed design §8](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/docs/superpowers/specs/2026-09-14-high-f1-event-stack-detailed-design.md:319)。原文没有写“必须同时满足全部条件”，也没有另定义“重复随机重划分”的要求，因此这是一个条件列表：满足任一条即可使 design review 有依据；它不等于自动授权 architecture replacement。

当前证据映射：

| 条款 | 当前证据 | 判定 |
|---|---|---|
| 1. candidate coverage 在多个 participant-frozen split 持续不足 | 当前 Formal G1 A 为 207/234；outer-2/3/4 为 0.8491/0.8571/0.8511。event-balanced E 为 206/234，outer-2/3/4 仍低于 0.90。相同 participant-disjoint outer protocol 上，失败不是单一 participant 或单一 fold。 | 满足现有 5-fold 解释；没有额外随机 split 的独立确认 |
| 2. event F1 多 seed、多 split 持续低于 baseline | 没有本轮新增 G4/M5 结果；G1 阻断后未运行正式 verifier/M5。 | 未证明 |
| 3. verifier 只在单一小 split 有效 | 不能在 G1 未通过时启动正式 verifier；旧小 split 结果不是当前 234-event formal 证据。 | 未证明 |
| 4. long FP/boundary/worst participant F1 扩大验证后恶化 | 当前 candidate 结果报告了大量未匹配候选，但这不是正式 G4 的 long-FP/boundary 结论。 | 未证明 |
| 5. window/loss 改善而 event F1 不改善 | event-balanced E 的五折 AUROC 全改善，但 event coverage 为 206/234，低于 A 的 207/234；这是 event-level transfer failure 的直接候选证据，但不是完整 G4 F1 结果。 | 作为支持性证据；不把它扩大为已证明的 G4 条款 |
| 6. 泄漏 | 已有报告没有把当前失败归因于 test、GT-neighbor 或 cross-gap leakage。 | 未满足 |
| 7. 资源 | event-balanced probe 在冻结预算内完成；没有资源阻断。 | 未满足 |

因此，`DESIGN_REVIEW_ELIGIBILITY` 可以由条款 1 独立成立，不需要 M5/G4 结果来“解锁”该审查；但它只证明可以讨论候选架构，不证明现有 architecture 已被 kill，也不授权 production 替换。

实现计划还有更高的 architecture-level 门槛：只有“三个 materially different causal hypotheses”在多个 clean participant-frozen folds 失败时，才允许把失败分类为 ARCHITECTURE；同时 G1 通过或有明确 architecture-level kill decision 之前，verifier/Task 6+ 仍阻断。[implementation plan §Task 5](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/docs/superpowers/plans/2026-09-14-high-f1-event-stack-implementation.md:627)–[§646](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/docs/superpowers/plans/2026-09-14-high-f1-event-stack-implementation.md:646)。本决定把现有证据解释为“足以重开 candidate proposal interface”，而不是宣布整个 high-F1 stack 已被证明不可行。

## 2. 已有干预的因果证据表

实验数量不作为独立证据数量；每项按改变的因果因素和评价层级区分。

| 干预 | 改变的因素 | participant/fold 协议 | 评价层级 | 已报告结果 | 与其他干预的独立性与限制 |
|---|---|---|---|---|---|
| Temporal Representation Probe | `imu_stats_v1` 对 bounded temporal representation 的替换；不是 candidate interface | 5 个 participant-disjoint outer folds；报告已冻结 | window score/ranking、hard-negative controls | `BOUNDED_TEMPORAL_REPRESENTATION_HYPOTHESIS=UNSUPPORTED`；representation 未强化；architecture 仍 frozen | 与 decision function 相同数据协议但改变 representation，因果因素独立；不检验 proposal interface |
| Decision-function Probe | A 与 preregistered nonlinear N；representation 固定 | 5 个 participant-disjoint outer folds | window-level AUROC/AUPRC 与 participant 分布 | 当前冻结状态按项目记录为 `DECISION_FUNCTION_EFFECT=UNSUPPORTED`；正式 event-level transfer 未建立，报告标记 `NOT_RUN_WINDOW_EFFECT_NOT_REPRODUCED` | 改变 scorer decision function，不改变 proposal contract；不能证明 scorer→interval interface 可用 |
| Aggregation Tournament | preregistered hysteresis、score-supported island fusion、bounded smoothing 等 eventization family | 配置规定 5 outer/inner protocol | eventization/coverage/false-event safety | 历史结论保留，但本工作树当前未找到对应 result report；只可核验 preregistered scope，不能把缺失 report 当新结果 | 与 representation/weighting 不同，但 source limitation 阻止本轮独立重算或强结论 |
| Window Geometry Diagnostic | 15 s/7.5 s 与 15 s/3 s 的采样网格 | 234 cohort；232 exact-complete 单独汇总；原始报告标记 2 个 approved raw skips | temporal support/coverage geometry | 232 exact-complete 上支持变化；234 汇总中 coverage improved=107, unchanged=117, worsened=10；不是模型 score rescue | 改变 inference sampling/support，不训练；没有授权 production stride 变化 |
| Frozen-A 3 s Transfer | 同一冻结 A、同一 threshold/eventizer，改推断网格 | 5 个 outer folds；完整 recording context | window score evidence 与 event outcome | `BOUNDED_SCORE_CHANGE_OBSERVED`；event-level `UNSUPPORTED`；`NO_CLEAR_EVENT_BENEFIT`；production stride unchanged | 与 geometry 的 density/support 方向相关但不等同；不改变模型目标或 proposal interface |
| Event-balanced A/E | 固定 A 与单一 event-balanced objective | 5 个 participant-disjoint outer folds；234 events | window AUROC/AUPRC、candidate event coverage、candidate FP | A=207/234；E=206/234；E recovered=2、newly lost=3；E AUROC 五折改善但 event coverage 无收益 | 改变 fit objective，不改变 feature/scorer class、threshold protocol 或 eventizer；本分支已关闭 |

直接结果来源：

- [Formal G1 v4 coverage](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-candidate-coverage-v4/coverage.json)
- [Temporal representation report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-temporal-representation-probe-v1/report.json)
- [Decision-function report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-decision-function-probe-v1/report.json)
- [Window geometry report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-window-geometry-diagnostic-v1/report.json)
- [Frozen-A 3 s report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-frozen-a-3s-stride-transfer-diagnostic-v1/report.json)
- [Event-balanced report](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/g1-event-balanced-candidate-objective-probe-v1/report.json)
- [Aggregation preregistration](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/configs/formal-g1-aggregation-tournament-v1.json)；当前未找到对应 result report，本决定不重跑。

## 3. 当前接口实际保证什么

### 3.1 Scorer 到 proposal

`src/eating_event/candidates.py::CandidateModel.predict_scores` 输出每个窗口一个 `predict_proba(features)[:,1]` score。[candidates.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/src/eating_event/candidates.py:127)–[132]

当前 `eventize_windows` 先保留 `score >= threshold` 的窗口，再按固定 fuse gap 合并成 interval；没有选中的窗口不会进入 proposal。[candidates.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/src/eating_event/candidates.py:27)–[61]

### 3.2 Proposal 到 verifier

`build_event_candidates` 接收已经选中的 window scores，构造一个 `EventCandidate`，其 16 个特征包括 score summary、window count、duration、density、coverage 和 day phase；verifier 接收这些 candidate features。[verifier.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/src/eating_event/verifier.py:29)–[121]

### 3.3 Verifier/decoder 能否改变候选集合

`decode_event_candidates` 只返回已有 `candidate.interval`，并按 verifier score 和 minimum duration 过滤；它不能新增一个不存在的 candidate，也不能改变单个 candidate 的 start/end。[verifier.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/src/eating_event/verifier.py:165)–[179]

runner 随后可以对被选 interval 做 `_merge_intervals`；这能合并邻近已有 interval，并扩大合并后的外边界，但仍不能从没有 proposal 的区域创造证据。[run_candidate_baseline.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/scripts/run_candidate_baseline.py:146)–[159]；调用位置见 [run_event_verifier.py](E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/scripts/run_event_verifier.py:497)–[503]。

因此：

- G1 candidate coverage 是当前项目契约规定的 verifier 前可行性门槛；
- 它不是按当前实现自动得到的最终 event recall 数学上限，因为下游 merge 可能改变已有 interval 的边界；
- 但下游不能恢复一个完全没有进入 candidate set 的事件证据，所以反复在 threshold/weight/representation 层局部试错而不改变 proposal interface，理论上有明确的瓶颈风险。

## 4. 设计选项

### 选项 A（推荐）：Coverage-Preserving Multi-Hypothesis Proposal Layer

改变的假设：候选层不再把“单一 threshold 后的一条 interval stream”当作唯一 proposal；它输出一个有上限、可审计的 proposal set，保留同一 continuous segment 内多个 score-support / boundary hypotheses，交给 verifier 选择。

保留：

- `imu_stats_v1` 111D；
- 当前 A HGB 作为第一版 scorer；
- 15 s/7.5 s production grid；
- participant-disjoint outer/inner protocol、234 cohort、IoU>0.25、test isolation；
- 现有 16D event candidate features 的主体；
- verifier、decoder 和 official evaluator 的职责。

需要改变的接口草案：

```text
WindowScoreStream
  {window_interval, raw_score, quality, session_id, segment_id, fold_id}
        -> BoundedProposalSet
  {proposal_interval, source_window_indices, score_support_summary,
   boundary_variant, session_id, segment_id, provenance}
        -> EventVerifier
        -> decoder
        -> official evaluator
```

proposal layer 的核心约束是“保留证据、限制数量、禁止 GT 参与”：它可以在固定规则下保留低于单一 start threshold 但属于连续 score-support 的 interval hypothesis，也可以给同一 support region 生成有限的 boundary variants；不能读取 GT、不能按 outer 失败事件定制、不能跨 gap/session 合并。G1 仍要求每个 outer fold proposal coverage recall ≥0.90，不放宽 234 cohort 或 IoU 门槛。

为什么它不同于已经失败的方案：

- 不是另一个 HGB/classifier 或 weight 公式；
- 不是 temporal feature expansion；
- 不是把 7.5 s 换成 3 s；
- 不是在已有 thresholded interval stream 上再做 hysteresis/smoothing/fusion；
- 它改变的是 scorer→candidate 的信息保留接口，使 verifier 实际能看到原先被单一 threshold 丢弃的 score evidence。

已有证据支持：geometry/3 s 诊断显示 dense support 可以增加，但 fixed A 的 event transfer 仍 unsupported；event-balanced E 显示 window AUROC 可以改善而 event coverage 不改善；这两项共同指向“窗口 evidence 到 candidate interval 的转换”仍是未解决假设。该证据支持重开接口假设，但不证明选项 A 必然成功。

代价与最可能失败点：

- proposal 数量、内存、verifier training rows 和 OOF artifact 会增加；
- proposal 去重、同一 segment 的多候选竞争和 decoder merge 规则会更复杂；
- 如果低分 support 只是 hard-negative signal，candidate recall 可能增加但 verifier FP/long-FP 会恶化；
- 如果真正问题是 participant domain shift 或 label/data support，proposal set 仍不会恢复真实 evidence。

### 选项 B：Event-Boundary Proposal Head

改变的假设：用一个 event-centric proposal module 直接预测 segment 内的 start/end/confidence，取代“window score threshold 后 eventize”作为 candidate producer。

保留同一 data contract、234 cohort、participant-disjoint split、IoU gate、verifier/decoder/evaluator；改变 scorer→proposal 的输出，从 window score stream 变为 interval proposals。

它可能直接改善低支持事件的 interval coverage 和边界，但需要新的 event-boundary training target、proposal matching、训练预算和更严格的 OOF artifact。当前证据没有直接证明 boundary head 能解决问题；geometry 只证明 support 变化，decision/objective 结果也没有建立 event-level transfer。因此 B 的失败风险和验证成本高于 A。

## 5. 推荐决定与必须批准的事项

推荐选项 A，但只批准“设计方向和接口重开”，不批准 implementation、full training 或 production replacement。

需要用户明确批准的具体事项：

1. 将 candidate contract 从“单一 thresholded interval stream”改为“bounded multi-hypothesis `BoundedProposalSet`”；
2. 保持 234-event cohort、participant-disjoint、IoU>0.25、每 fold coverage ≥0.90、test isolation 不变；
3. 允许 proposal layer 在不读取 GT 的前提下保留有限的 score-support/boundary hypotheses；
4. 在新 proposal G1 通过前继续阻断 verifier、M5、G4、M6 和 full training；
5. 接受 candidate 数量、verifier 计算和 artifact 存储作为需要预先冻结的资源预算，而不是偷偷放宽 G1；
6. 允许一次 proposal-only feasibility validation；不批准 weight sweep、threshold compensation、stride scan、feature expansion 或 M6 runner 开发。

如果不批准第 1–3 项，则当前证据不足以支持任何继续的 candidate redesign，应记录 `NO_JUSTIFIED_REDESIGN`，保留 G1/full-training 阻断。

## 6. 唯一后续验证草案（暂不执行）

这是设计草案，不是本轮实验命令。

固定比较：

- baseline：当前 A 的已保存 15 s/7.5 s participant-disjoint score source 和当前 `eventize_windows` candidate stream；
- proposal：只实现一次冻结的 `BoundedProposalSet` 规则；不训练新 scorer，第一阶段直接复用现有 A score source，以隔离 proposal-interface 效应；
- 数据：234-event cohort、相同 5 outer folds、完整 recording context、背景窗口、test 隔离；不重新划分 participant，不访问 test；
- 参数：proposal count cap、support/boundary rule、session/segment boundary 和 resource budget 在运行前写入新 spec/hash；不得根据 outer 结果修改；
- 评价：G1 proposal coverage、每 fold/participant coverage、proposal count、candidate label balance、hard-negative/false-event、资源；不把 oracle/GT-driven proposal 当性能结果。

通过：5/5 outer folds proposal coverage recall ≥0.90，且在冻结资源预算内完成；这只使 verifier 阶段“可考虑”，不自动启动 verifier。  
失败：任一 fold <0.90、proposal 数量超过预算、或只靠 GT/outer 失败事件才能达到覆盖；立即关闭选项 A，不继续调 proposal cap、threshold 或 aggregation。  
无论结果如何：因为 outer folds 已反复用于开发诊断，结果只能作为 diagnostic feasibility evidence；后续确认需另行批准的独立 participant-labeled confirmation protocol，不能通过重划分或 test 追求通过。

## 7. 路线影响

当前路线：

```text
G1 FAIL
  -> verifier/M4 BLOCKED
  -> M5/G4 BLOCKED
  -> M6/full training BLOCKED
```

若用户批准选项 A：

```text
proposal interface spec/hash
  -> one proposal-only G1 validation
  -> only if G1 passes: formal verifier/M4 design
  -> nested M5
  -> G4
  -> only after M5/G4: M6/full target-only training
```

若 proposal-only G1 失败，不能用 verifier、M5、G4 或 full training 把 candidate coverage 缺口隐藏起来；应记录 candidate architecture infeasible，并由用户决定是否接受更高成本的选项 B 或停止项目。

## 8. 保持状态与来源限制

- production 未修改；
- Formal G1 未放宽；
- full training 仍 blocked；
- architecture change 未执行；
- event-balanced weighting branch 已关闭；
- 未找到 aggregation tournament result report，因此该历史结论只按既有记录保留，未在本轮重新解释或重跑；
- 未实现 M6 runner，也没有用它代替 candidate coverage 决策；
- 当前 worktree 上未发现适用 `AGENTS.md`。
