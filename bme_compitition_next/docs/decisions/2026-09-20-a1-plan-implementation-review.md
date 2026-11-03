# A1 执行计划与实现复核

> 后续修订及第二轮review已完成，见[复核后续记录](2026-09-20-a1-revision-review-followup.md)。下文保留首轮发现快照，行号对应修订前源码。冷启动路径已修复并通过180项测试；当前NOT_READY的最新阻断为audit 004资源超限，checkpoint resume仍明确不支持。

日期：2026-09-20。状态：`DONE_WITH_CONCERNS / ISSUES_FOUND / A1_NOT_READY`。

用户已批准[D3-Ready-v1 R1–R4](2026-09-20-a1-d3-combined-readiness-revision-proposal.md)。本轮记录批准，并使用 `E:/Codex/Home/skills/gstack-review/SKILL.md` 及实际位于 `E:/Codex/Home/skills/gstack/review/checklist.md` 的检查表执行本地计划—实现复核。适配用户范围：没有PR、远程评论、merge或部署，不执行遥测/安装/自动提交；不派发子代理。采用两轮检查、具体行证据与置信度校准，不将此记录声称为完整PR落地流程认证。

范围：A1当前计划、配置、独立包、runner及针对性测试；以批准契约对比当前文件，而不是用主分支全量diff混入既有无关工作。所有A1文件目前为本地未提交实现。审查没有修复模型/执行代码，没有调用fit/predict或读取raw。文档批准状态与计划门禁已更新；以下8项代码问题仍待修复。

## F1 [P1] 资源约束没有接入实际执行（confidence 10/10）

证据：`pipeline.py:190` 直接 `estimator = fit_candidate_estimator(`，在当前进程调用；`:197` 调用 `ledger.record_fit_result(role.role_id, "success")` 没有传elapsed/RSS；`:307` 重新硬编码 `max_rss_bytes=8 * 1024**3`；总wall仅在`:464` 完成一个outer后检查。`budget.py:135/140` 的check_wall/check_output_size没有生产路径调用，RSS仅在runner启动时采样。

影响：实际fit没有单次7200s终止、≤1s内存监控或线程限制；audit耗时/峰值、predict与写盘未受控，run也不继承audit冻结的60%可用内存上限。配置存在不表示限制有效。

修复/验收：RV1。监控包围完整研究执行，累计预算必须包含audit且可续接；使用合成worker验证终止和子进程统计，禁止真实模型做资源护栏试验。

## F2 [P1] MAE按participant等权而非按匹配事件加权（confidence 10/10）

证据：`metrics.py:234` 为 `start_mae_ms=sum(start_values) / len(start_values) if start_values else None`，`:235` end同样处理。

合成反例：participant a有1个match，边界误差1000ms；b有9个match，误差全0。当前返回500ms，批准契约要求100ms。会改变fold和pooled质量判断，不只是展示格式。

修复/验收：RV2，累加所有matched errors或将participant MAE乘matched_count，再除总count；零matches保留null。

## F3 [P1] 冻结配置与批准输入没有形成强校验（confidence 10/10）

证据：`contracts.py:187` 仅检查 `if not 0 < self.strict_iou < 1`；duration/fusion只要求非负。实测 `A1Config(strict_iou=.5,min_duration_ms=0)` 被接受。`:265` 等load_config合并允许任意HGB覆盖，但fit函数仅消费max_iter/weight，其余由scoring硬编码，可能出现记录配置和实际模型不一致。

`inputs.py:158` 只检查ledger hash字段存在；`:278` 将声明值抄入source_hashes，没有验证冻结ledger常量；config也没有批准manifest内容hash。当前流程能证明audit前后文件未变化，不能证明audit首次读到的就是批准输入。

修复/验收：RV3。严格值域/等值检查及完整模型参数signature；批准输入hash独立于待审输入声明。旧输入hash保持锚定，D3新增sidecar单独冻结。测试改变GT时间但保持234计数、改manifest+cache声明、改IoU/duration均被拒绝。

## F4 [P1] 真实pipeline缺完整来源和可复核产物（confidence 10/10）

证据：`pipeline.py:359` 仅为subinner写role/participant/threshold/count；reference.row_hash在`:270` 返回时被丢弃（只返回threshold），不绑定model hash、fit signature或逐row score；`ScoreProvenance`只定义在contracts而未接入pipeline。inner/outer及verifier没有同等级来源记录。

预测落盘仅含ID/participant/time，未保存匹配pairs与unmatched IDs；metrics函数中的逐participant结果未写出。`metrics.py:208` 只从truth或prediction出现的人构造人口，无GT且无预测的6C7会从明细消失（pooled计数不受这一点影响）。

影响：即使返回F1，也不能按批准契约重建模型/OOF/threshold lineage、解释FP及完整41人结果；不能用静态角色图替代实际评分来源。

修复/验收：RV4，实际角色输入集合与signature校验、全部层级来源、match与participant产物、无事件/预测人口显式NA。复用清单不得仅按字段存在就称reuse_eligible。

## F5 [P1] 完整质量验收未接入runner（confidence 10/10）

证据：`metrics.py:243` 定义evaluate_quality，但pipeline未调用；`pipeline.py:482` 直接返回 `"status": "COMPLETE"` 和pooled/fold指标，没有numeric_minimum/ideal、majority_folds、quality_per_fold、stage判定。runner只写metrics.json和run-status.json，没有计划要求的完整report和最终产物hash清单。

影响：计算结束状态无法表达已批准业务目标和质量门槛是否满足。这里不指控现代码将低F1标成PASS；问题是验收及交付缺失。

修复/验收：RV5。明确COMPLETE只代表五折完成，达标由独立字段给出；aggregate函数必须接收准确的五fold结果与pooled结果，不能依赖含糊的results[-1]约定。

## F6 [P2] 运行没有绑定审计fold/代码依赖快照（confidence 9/10）

证据：runner读取并保存fold_manifest，但 `pipeline.py:316` 用 `build_outer_folds(participants, n_folds=5, seed=config.seed)` 重新生成；inner也重新生成。runner `_code_identity` 在`:141` 只hash a1包、runner与config，不含实际导入的evaluation.py/metrics.py。`_validate_outer_manifest` 检查valid_union，未按每participant计数验证恰好一次。

重要反证：本轮逐fold比较当前生成的outer-valid集合与冻结manifest，**5/5一致**。故本审查不声称当前发生重新分配、泄漏或历史结果无效；指出依赖代码变化/异常manifest不能被完整就绪门禁发现。

修复/验收：RV6。使用冻结fold/role graph作为执行输入，完整快照hash与participant multiplicity核验；环境记录至少覆盖影响模型行为的实际库版本。

## F7 [P1] 静态测试被当作完整执行路径验证（confidence 10/10）

证据：`tests/test_a1_pipeline.py` 的3个测试均只调用build_role_graph，没有执行execute_full_pipeline；`tests/test_a1_budget.py` 的3个测试只验证ledger计数及空采样异常，没有worker或超时终止；全A1测试检索未发现execute_full_pipeline集成调用。

本轮重跑contracts/metrics/budget/pipeline四个测试文件：16 passed。与此同时F2合成反例明确失败于业务期望。测试通过是真实的，覆盖计划要求不完整也是真实的；不能将用户报告157 passed或36项合成测试等同Task1–8完成。

修复/验收：RV7。以fake estimator执行真实orchestrator/runner路径，记录实际集合和调用次数；测试GT扰动不改变heldout预测、三threshold不增加fit、G3中断、预算终止和产物完整性。不要只增加镜像实现的断言。

## F8 [P2] 失败/重复运行状态可能掩盖真实原因或覆盖结果（confidence 10/10）

证据：`pipeline.py:472` 的 `except Exception as exc` 将未知错误归为INCOMPLETE_RESOURCE；runner `:284` 无论run返回INVALID/G3失败/资源中止均return0。execute_run不先拒绝已完成run，也不验证manifest记录的input_audit_sha256；重复run会在保留fit-ledger下重新开始，撞已预留角色后写新的metrics/run-status，可能覆盖原完成结果。audit失败分支也会在已有run-dir写audit-failure.json。

修复/验收：RV8，run状态机、目录写保护、显式resume及累计预算、审计摘要验证；未知错误归INVALID/明确程序故障，非成功停止退出非零，不复写已完成产物。

## 计划层面的修正与下一步

8项中多数是原计划已经要求但实现未完成，不需要重新发明架构或降低门槛。计划本身的不足是Task9就绪入口只写“前面完成”，没有可执行的逐项证据清单；现已追加RV1–RV8，并挂接已批准R1–R4覆盖条款。

执行顺序建议：R1–R3数据适配 + RV3输入冻结 → RV2指标 → RV6/RV4执行来源 → RV1预算 → RV5/RV8状态与报告 → RV7全路径合成回归 → 完整不拟合audit。存在依赖时不得提前宣告READY。

本轮未修上述source：用户请求是计划审查，修复涉及执行协议关键路径且不是机械文本修改；将问题具体化为可验收的计划项后交回，保留批准范围。无需再次批准D3-Ready-v1；后续修复若严格恢复已批准契约，也不应重新请求这些设计批准。

验证范围：只读来源/代码审查、冻结outer集合比较、MAE/配置合成反例、16项现有纯契约测试、文档检查。没有重跑全量157项，没有独立子代理复核、真实fit/predict或原始数据验证。不能保证没有其他问题。

```text
D3_READY_V1 = APPROVED
A1_EXECUTION_READINESS = NOT_READY
REVIEW = ISSUES_FOUND (6 P1, 2 P2)
LOCAL_G1_EXPERIMENTATION = STOPPED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
