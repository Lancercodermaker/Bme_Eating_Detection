# A1 修订实现与第二轮 review

> **2026-09-22 状态更新：** audit 005已通过，Task 9真实五折运行COMPLETE（105 candidate +25 verifier fits）。pooled F1=0.5851，最低/理想及综合门槛均FAIL；按既定规则关闭被测A1协议。见[结果决定](2026-09-22-a1-end-to-end-feasibility-result.md)。下文audit 004/fit=0描述保留为历史状态；checkpoint恢复仍不支持，旧G1/full-training/production冻结状态不变。

日期：2026-09-20。状态：`IMPLEMENTATION_REVISED / REVIEW_COMPLETED_WITH_LIMITATIONS / A1_NOT_READY_RESOURCE`。

范围：用户“修订并继续review”及后续“继续”授权下，落实已批准D3-Ready-v1并修复首轮review发现。没有执行target数据fit/predict，没有读取raw或official test/external data，没有提交或改写历史NPZ/G1产物。

## 1. 已完成的修订

| 门禁 | 实际修改及验证 |
|---|---|
| D3 R1–R3 | approved manifest/hash派生身份；保留index边界，使用窗口支持组件；participant training GT派生训练标签；sidecar记录196行0→-1，不回写NPZ |
| RV1 | 专用worker由父进程监控完整audit/run，覆盖加载、fit、predict、写盘；0.2s采样，fit phase计时；线程环境上限4；冻结启动RSS；研究级wall ledger；跨run磁盘统计 |
| RV2 | MAE按matched_count加权；1匹配1000ms + 9匹配0ms的反例返回100ms；无matches为null |
| RV3 | 独立批准输入hash锚点、ledger固定值、1127/41/632100/234人口校验；IoU/duration/fusion/HGB/资源值严格冻结；D3标签差异和965越界窗口计数核验 |
| RV4 | 实际fit/score集合检查；model bytes/hash、训练行/特征/标签hash与完整fit signature；130角色score来源；candidate/support、prediction、matched/unmatched IDs；无GT无预测participant保留；报告candidate coverage、独立正GT数及macro_event_bearing |
| RV5 | 五fold与pooled分别传入质量判定；numeric/stage最低与理想结果分开；report、metrics及最终checksum产物接入runner |
| RV6 | 审计生成并冻结role snapshot；实际执行消费该snapshot；outer/inner/subinner逐层人口与验证唯一性检查；代码身份覆盖整个eating_event包、runner、config；记录相关库环境版本 |
| RV7 | fake estimator经过真实execute_full_pipeline和runner工作函数；验证130 fits、三threshold无额外fit、outer-GT扰动不改变对应fold选择/预测、G3失败停止、产物完整、审计摘要篡改拒绝；合成worker验证超时/RSS终止 |
| RV8 | study单owner锁；已完成/失败run不能隐式再执行，已有目录不落盘覆盖；非成功退出非零；未知错误归INVALID、资源错误单独分类；已有任意fit reservation时拒绝新run重置预算 |

为了职责分离新增 `anchors.py`、`execution.py`、`control.py`、`worker.py`；均属于独立A1包，未把修改扩散至历史模型/runner。

模型复用采用明确冷启动策略：旧模型训练环境和新标签signature不能完整证明一致，因此不复用、不反序列化。实际角色仍最多105 candidate +25 verifier，未额外增加fit预算。65个历史路径的清单不再被误称为已合法复用的模型。

## 2. 第二轮复核中新发现并关闭的问题

- subinner角色图原来仅检查outer排除，未直接拒绝fit/scored重叠；新增失败反例并强化层级集合检查。
- run目录级fit ledger不足以保护全研究预算；新增跨run reservation检查，禁止换目录重置fit次数。
- 磁盘超限原来抛普通RuntimeError，可能被归INVALID；现为明确ResourceNotReady。
- 资源配置允许负线程数等无效值；现与批准固定值精确比对。
- 完整报告缺少candidate_count、candidate-covered GT与macro；已补齐并验证。

以上均先以失败测试或已复现反例确认，再修复。当前复核未发现新的、可具体复现的冷启动执行路径阻断错误；这不是无漏洞保证，也不是独立第三方审查。

## 3. 验证证据

- 最终全量测试：`python -m pytest -q` → **180 passed in 20.66s**。
- `python -m compileall -q src/eating_event/a1 scripts/run_a1_feasibility.py` 通过；之后contracts修订也经pytest导入/执行验证。
- 实现/配置/测试身份：[code-test-hashes.json](../../artifacts/a1-revision-review-v2/code-test-hashes.json)。用于本轮复核归档，不替代未来audit重新计算代码身份。
- unit tests可能拟合小型合成HGB；完整编排测试使用FakeBackend。上述数值均不是target研究fit/predict次数或性能结果。

### 不拟合audit 003

[input-audit.json](../../artifacts/a1-end-to-end-feasibility-v1-003/input-audit.json)曾返回READY，完成1127缓存、41人、234GT、196标签sidecar与身份检查，fit_count=0、predict_count=0。监督采样约11.578s，peak RSS 1,065,684,992 bytes。

此后代码继续修订，003的code identity已过期；严禁把该READY作为最终代码运行许可。

### 不拟合audit 004

[audit-failure.json](../../artifacts/a1-end-to-end-feasibility-v1-004/audit-failure.json)最终状态为NOT_READY，reason=`RSS budget exceeded`，fit_count=0、predict_count=0。

| 项目 | 实测 |
|---|---:|
| 启动可用内存 | 1,272,868,864 bytes |
| 按60%冻结RSS上限 | 763,721,318 bytes |
| 监督采样峰值 | 768,344,064 bytes |
| worker被终止前耗时 | 约12.953s |

这证明真实监督路径能终止超限worker。不得因worker内部可能已经写出input-audit READY便忽略父进程NOT_READY；父进程run-status是最终状态。004后还有资源异常分类和配置检查修订，因此它也不是最终代码READY快照。

既有002失败audit没有可靠耗时，研究级预算一次性按批准audit上限1800s保守扣除，标记`historical_audit_upper_bound`，不声称这是真实耗时。加003/004实测后的记账约1824.547s。未重置或扩容预算，未进行第005次audit。

## 4. 保留的限制与下一步

1. **当前机器就绪仍未通过。** 最新真实审计在当时的冻结内存上限内失败。后续应在可用资源发生明确变化，或有经验证的内存使用优化后，再创建新审计；不得循环重试或擅自调大60%/8GiB上限。
2. **没有自动checkpoint resume。** 中断/失败执行和已有fit reservation均fail-closed；新目录不能绕过。若将来需要恢复，必须先设计能复核模型/score/artifact、角色进度和累计预算的显式恢复方案。当前修复完成的是防重跑、防预算清零，不将“拒绝resume”声称为已实现恢复功能。
3. **首次真实fit的性能与资源成本未知。** FakeBackend验证编排及来源，不证明真实HGB的G3可用性、耗时、峰值或F1达标。
4. 仍没有raw时间边界独立证明或未参与开发决策的confirmation cohort；D3的已批准证据范围不变。

计划中RV8关于显式恢复的功能部分保留未完成；它不允许通过隐式重跑替代。此次范围内已关闭首轮8项发现的冷启动安全/正确性缺口，研究级READY仍取决于最终代码重新audit通过。

```text
D3_READY_V1 = APPROVED_AND_IMPLEMENTED
TARGET_A1_FIT_COUNT = 0
TARGET_A1_PREDICT_COUNT = 0
A1_EXECUTION_READINESS = NOT_READY_RESOURCE
CHECKPOINT_RESUME = UNSUPPORTED_FAIL_CLOSED
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
