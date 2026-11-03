# A1 端到端可行性结果与停止决定

日期：2026-09-22。运行：`a1-end-to-end-feasibility-v1-005`。

**执行 COMPLETE；最低及理想开发目标均 FAIL；被测 A1 协议 CLOSED。** 这是完整五折性能负结果，不再是身份或机器就绪阻断。按既有 Task 9 规则关闭本协议，不追加 threshold、seed、fit 或其他配置；下一步回到设计与投入讨论。

## A. 文档明确事实与状态演进

用户已批准 A1/D1–D5、D3-Ready-v1 R1–R4，并于本轮明确允许开始。沿用当前工作树及 executing-plans INLINE 执行，没有新增工作树、修改实现、改变配置或重置预算。

最低目标为 pooled F1≥0.66，理想≥0.80；还要求至少3/5折 F1≥0.66，每折 long-FP fraction≤0.25，以及匹配事件 start/end MAE≤900秒。numeric 与 stage 判定分别保存。

此前第二轮 review 和计划中的“audit 004 NOT_READY / fit未启动”是历史停止状态，本记录以新的 audit/run 证据更新当前 A1 状态。原始计划里 session 非空、index bounds 硬包含及旧标签的条款已由获批 D3 覆盖；这里没有默默选择旧契约。RV8 checkpoint resume仍未实现，本次为首次真实冷启动，不依赖恢复。旧 Formal G1/full-training 状态不因本结果改变。

## B. 当前实际执行与新开发结果

Audit 005返回READY，监督父进程状态AUDIT_READY；随后同目录run完成五折。105 candidate +25 verifier拟合全部成功，没有重试或复用旧模型。所有25个verifier通过G3；其中最少120个正候选、21个正participant、103个正canonical GT（这些是训练侧计数）。

41个participant、234个canonical GT，1127缓存、632100窗口；D3 sidecar生效，旧NPZ未回写。6C7保留：TP=0、FP=0、FN=0，F1/recall为NA；它不是性能缺口的来源，也没有因无餐被移除。

| fold | 所选阈值 | TP/FP/FN | F1 | long-FP fraction | start/end MAE（秒） | candidate-covered GT |
|---|---:|---:|---:|---:|---:|---:|
| outer-0 | 0.50 | 36/27/14 | 0.6372 | 85.19% | 305.6/98.2 | 46/50 |
| outer-1 | 0.50 | 26/21/23 | 0.5417 | 80.95% | 318.9/241.3 | 48/49 |
| outer-2 | 0.25 | 38/45/15 | 0.5588 | 57.78% | 361.3/177.6 | 47/53 |
| outer-3 | 0.50 | 25/17/10 | 0.6494 | 70.59% | 317.8/73.3 | 31/35 |
| outer-4 | 0.50 | 28/26/19 | 0.5545 | 65.38% | 438.7/191.5 | 41/47 |

Pooled：TP=153、FP=136、FN=81；precision=0.5294、recall=0.6538、F1=0.585086。289个最终预测。event-bearing participant macro F1=0.5733。Pooled start/end MAE=348.1/155.2秒；95/136个误报时长≥600秒，pooled long-FP fraction=69.85%。JSON quality.long_fp_fraction=85.19%指最差fold，不是pooled比例。

| 验收项 | 结果 |
|---|---|
| pooled F1≥0.66 | FAIL，差0.0749绝对F1 |
| pooled F1≥0.80 | FAIL |
| 至少3/5折F1≥0.66 | FAIL，0/5 |
| 每折long-FP fraction≤25% | FAIL，5/5折超限 |
| 每折start/end MAE≤900秒 | PASS，最差438.7/241.3秒 |
| stage_minimum / stage_ideal | FAIL / FAIL |

4183个outer候选覆盖213/234个GT（91.03%），最终一对一TP为153。覆盖、候选正例数量和最终TP不是同一指标。短GT（≤45秒）合计3个；不能据此把全部81个FN归因为短事件。

## C. 历史结果单独列示

| 历史证据 | 数值/状态 | 本次解释限制 |
|---|---|---|
| Formal A candidate coverage | 207/234 | 历史候选覆盖，不是本次F1 baseline |
| Historical union coverage | 217/234，Formal G1 FAIL | 不解锁union或训练；与本次路径不能视作受控改进比较 |
| audit 004 | RSS超限，fit/predict=0 | 已有资源阻断记录，不能解释为模型负结果 |

本次213/234与历史coverage的差异包含标签、边界及端到端路径变化，没有执行同契约历史baseline对照，不宣称统计显著改进。

## 资源与产物核验

Audit监督耗时18.906秒、peak RSS 1,096,613,888 bytes。真实run监督耗时1069.563秒（约17.83分钟）、peak RSS 2,394,521,600 bytes，低于冻结2,871,572,889 bytes上限。监督统计研究输出724,424,859 bytes，低于2GiB。fit-ledger的627.629秒是累计fit计时，不能当作完整run耗时。

研究预算累计记账2913.016秒（含历史002按1800秒保守扣除；该1800秒不是真实测量）。未扩大6小时额度。剩余额度不构成追加实验授权。

运行后只读核验：final-checksums全条目匹配；130个唯一模型角色、130个score来源、130次成功fit；score文件hash全部一致；fit/scored participant隔离、outer排除成立；41人/234GT、153TP/136FP、289预测计数一致。运行前复核实现/配置/测试hash与180 passed的review快照一致，本轮没有代码改动，未重复执行测试套件。

证据：

- [metrics.json](../../artifacts/a1-end-to-end-feasibility-v1-005/metrics.json)
- [report.md](../../artifacts/a1-end-to-end-feasibility-v1-005/report.md)
- [input-audit.json](../../artifacts/a1-end-to-end-feasibility-v1-005/input-audit.json)
- [run-manifest.json](../../artifacts/a1-end-to-end-feasibility-v1-005/run-manifest.json)
- [final-checksums.json](../../artifacts/a1-end-to-end-feasibility-v1-005/final-checksums.json)
- [resource-segments.jsonl](../../artifacts/a1-end-to-end-feasibility-v1-005/resource-segments.jsonl)
- [study budget](../../artifacts/a1-study-budget.jsonl)

## D. 仍缺失的证据

没有未参与开发决策的participant-level confirmation holdout；单seed五折结果仅为开发证据。没有官方test结果、独立raw时间边界证明、同契约历史baseline对照或误差原因消融。没有可靠monitoring duration，FP/hour保持null。未读取raw sensor、official test或external data；raw路径仍只作为opaque identity。

## E. 基于证据的推断与投入决定

A1已证明技术上可在当前资源内完成真实端到端执行，但没有证明最低性能可行。高候选覆盖与低最终F1同时存在，提示后续设计应优先研究候选筛选、事件边界与解码过程中的精确率/召回损失，尤其长误报；当前证据不足以把责任单独归给verifier、某个阈值或duration规则。

按预先约定关闭被测协议。下一阶段若继续，应先提出新的可证伪设计和有限投入方案，再决定是否实施；不以接近某折目标、修改6C7或利用剩余预算为理由继续本轮局部搜索。这不等价于整个项目永远不可能达到0.66/0.80。

```text
A1_EXECUTION = COMPLETE
A1_NUMERIC_MINIMUM = FAIL
A1_NUMERIC_IDEAL = FAIL
A1_STAGE_MINIMUM = FAIL
A1_STAGE_IDEAL = FAIL
A1_TESTED_PROTOCOL = CLOSED
CHECKPOINT_RESUME = UNSUPPORTED_FAIL_CLOSED
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
