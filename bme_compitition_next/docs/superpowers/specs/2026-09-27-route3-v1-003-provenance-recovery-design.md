# Route 3 v1-003 拟合来源记录恢复设计

日期：2026-09-27  
状态：`ENGINEERING_RECOVERY_VALIDATED`；v1-003 已合法 `COMPLETE`，科学状态为 `CLOSED_STAGE_MINIMUM_FAIL`。  
工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`

## 1. 本次授权与目标

用户在收到 v1-002 的终态记录后要求“需要改设计文档并重新执行”。本次授权覆盖修复来源记录契约、审阅修订和在新 `route3-matching-aware-v1-003` 命名空间中进行一次 `audit`，仅在所有门通过后进行一次 `run`。这是同一科学协议的工程恢复，不授权调整模型、目标、阈值、候选区间、评价规则或资源上限，也不启动路线二。

工程成功定义：实际拟合输入的来源记录与冻结审计相符；所有调用、资源和身份门通过后，运行可以获得合法 `COMPLETE`。科学成功仍由原 numeric/stage 门判断；工程 `COMPLETE` 不等于 F1 达标。

本设计接续以下完整来源：

- `docs/superpowers/specs/2026-09-26-route3-matching-aware-target-proposal.md`
- `docs/superpowers/plans/2026-09-27-route3-matching-aware-execution.md`
- `docs/decisions/2026-09-27-route3-v1-002-resource-review-and-run.md`
- `src/eating_event/route3/runner.py`、`workflow.py` 与 `src/eating_event/a2/execution.py`

## 2. 已核实的失败原因与历史消耗

v1-002 实际完成了 25 次 verifier 拟合、25 次打分、65 次解码和 5 折 outer 评价，candidate fit/predict 为 0/0。运行峰值进程树 RSS 为 `796,614,656 B`，低于其运行上限 `2,602,833,920 B`，资源记录没有失败。因此不能再描述为“首个拟合前失败”或内存不足。

写入端 `a2.execution._fit` 的实际拟合记录没有 `candidate_count`；读取端 `route3.runner._validate_fit_provenance` 要求该字段。25 条实际记录均缺这个字段；其角色、训练角色组合、键/矩阵/标签摘要与其他已比较计数相符。校验发生在整个执行图之后，因而已经消耗的 25 次拟合不能当作零消耗。v1-002 保持终态 `INVALID`，临时指标不追认为有效性能证据，也不用于本次调参。

| 命名空间 | 已登记结果 | 已消耗 verifier 拟合 | 本次处理 |
|---|---|---:|---|
| v1-001 | `INCOMPLETE_RESOURCE`，预拟合停止 | 0 | 保留原账本与产物 |
| v1-002 | `INVALID`，拟合图已执行 | 25 | 保留原账本与产物 |
| v1-003 | `COMPLETE / CLOSED_STAGE_MINIMUM_FAIL` | 25（原预算上界也是 25） | audit/run 各一次，已终态，无重试 |

v1-003 已完成 25 次拟合，Route 3 累计真实拟合为 50 次。新 study 的预算独立，并未擦除 v1-002 的消耗。旧配置、文档、产物和终态不改写。恢复前 15 个登记代码文件由执行者归档到 `docs/evidence/route3-v1-002-code-freeze-2026-09-27.zip`，对应恢复基线位于 `docs/evidence/route3-v1-002-recovery-baseline-2026-09-27.json`；这些新证据保存旧运行代码身份，不替代旧 READY。

## 3. 保持不变的科学合约

机制仍为 matching-aware 的逐候选监督：对每个非 outer candidate role，使用该角色参与者的训练 GT 和原本的本地严格 `IoU > 0.25`、participant-global deterministic greedy one-to-one matcher，仅把被指派的候选标为正例。标签建在冻结的 300 秒候选融合之后、verifier 阈值与最终 decoder 之前；它不是对最终解码事件做目标匹配。

- 读取冻结 A2-004 已认证 materialized corpus；105 个 candidate roles、25 个 verifier roles，跨角色 72,112 行，outer 4,183 行。
- 26D 特征值、schema、原 16D decode view、A1/base 保存分数、候选身份与区间均不变。原 A2 any-IoU 标签不作为新训练目标。
- 41 人、234 eligible GT、5/4/4 nested roles、seed `20260910`、HGB 设置、positive weight `3.0`、`max_iter=100` 不变。
- 阈值仍为 `{0.10, 0.25, 0.50}`；候选融合 300 秒、最终融合 600 秒、最短输出 180 秒、long FP 定义 600 秒不变。
- outer 标签在训练目标构造时保持 null；outer GT 只能用于冻结后的最终评价。原 inner 评价仅用于原阈值选择。
- 调用预算仍为 candidate fit/predict 0/0、verifier fit attempts 25、scores 25、inner decodes 60、outer decodes 5、outer evaluations 5。失败拟合也消耗其 attempt。

Numeric minimum/ideal 仍为 pooled F1 至少 0.66/0.80。Stage 门还要求至少 3/5 折 F1 至少 0.66，每折 long-FP fraction 不超过 0.25、每折 matched start/end MAE 不超过 900 秒。这是本地开发合约，官方精确 matcher 与运行接口尚未确认。

本次不改变候选区间，未提供直接恢复 21 个无可匹配候选 FN 的候选形成机制；不能仅凭候选覆盖数推导所有最终融合情形的数学不可恢复性。180 秒输出约束与短 GT 的数学冲突仍存在。58 个与已登记注释零交叠的长 FP 行为真值仍为 `UNKNOWN`。所有 41 人已用于开发，新的五折结果不能称为独立参与者验证。A1 CLOSED、A2 fixed-26D CLOSED_STAGE_MINIMUM_FAIL、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。

## 4. 来源契约恢复机制

### 4.1 保留 A2 实现的文件字节

A2-004 READY 的代码身份包含共享 `a2/execution.py`。直接在该文件补字段会改变被冻结输入加载所要求的代码身份。本次只在 Route 3 侧实现来源适配器，保留 A1/A2 登记代码字节与科学执行路径。

Route 3 在本次单进程执行范围内临时适配 `a2.execution._persist_fit`，执行结束或异常时通过 `finally` 恢复原函数；已有 `_decoded` 调用计数适配也必须恢复。适配器不得影响其他命名空间，不得再次调用 estimator 或 score。

### 4.2 实际输入生成实际记录

实际来源记录生成器接收实际训练 `rows` 与 verifier role，复用 A2 的 `_candidate_arrays`、`_role_hash`、`_labels_hash`，生成角色身份、训练角色组合、候选计数、正例候选/参与者计数、键摘要、26D float32 矩阵摘要及标签 join 摘要。`candidate_count` 从实际矩阵行数取得，并检查与标签、参与者、rows 长度一致，不能从 expected audit 复制。

审核时保留 assigned distinct positive GT 与 A2 actual positive canonical GT 的原有语义区别：前者来自训练角色指派账本，后者来自 A2 的实际正候选与 GT 严格交叠集合。补候选总数不能用 feature_dim、positive_count 或 GT_count 代替，也不能通过降低校验强度来接受缺字段记录。

统一的单角色契约必须比较角色 ID、完整训练角色组合、`candidate_count`、positive candidate/participant counts，以及三个输入摘要。expected 和 actual 均必须具有唯一 role ID；不得依赖 `zip` 顺序来掩盖缺角色、重复角色或错角色。全部 25 个登记角色集合必须精确相等。

### 4.3 三层门

1. **audit 与 run 的无拟合来源门：** 对全部 25 个实际训练组合，按冻结 A2 executor 的行序组成数组和记录，使用与持久化路径相同的字段生成器和同一角色契约比较 target audit。该检查在首个 `reserve_fit` 前完成，不调用 fit/predict/predict_proba。结果及摘要绑定新 READY；run 独立重建并与 READY 比较。
2. **每次拟合持久化门：** Route 3 的 `_persist_fit` 适配器从传入的实际 rows/arrays 生成候选总数，核对 A2 本次实际 fit_record 的输入字段，再按唯一角色查找 audited expected 记录并校验，最后调用原 `_persist_fit`。字段在写入 `verifier-fit-ledger.jsonl` 之前补齐，返回的记录也含同一字段。如果拟合后持久化门失败，该次 attempt 已消耗，不能重试。
3. **最终 25 条记录门：** 执行结束仍验证全部实际 fit records、唯一角色集合、输入来源与固定调用计数。metrics、fit ledger 和最终 manifest 的实际记录须一致；不得只修改 metrics 中的副本。

这样，缺失来源字段应首先在无拟合门发现，运行中的漂移在该角色持久化时发现，末尾门继续保护最终接纳。每一层都失败即停，不把 expected 值回填为“实际值”。

## 5. 资源、读取范围与失败保存

资源上限与 v1-002 完全相同：audit/run 累计 active wall 900 秒，verifier fit wall 600 秒，最多 2 线程，新 study disk `536,870,912 B`（512 MiB），RSS `min(3,221,225,472 B, 50% of invocation startup available memory)`。原 2x RSS/disk 合成余量门保留；audit 与 run 按原预算实现分别冻结其 invocation 的 startup-derived RSS 上限。不放宽 caps，不更换机器状态来静默重试终态。

读取范围限于本次精确登记的 docs/source/config、冻结 A2-004 manifest 登记的派生 materialized 输入，以及用于恢复基线的已登记历史终态产物。不得读取、遍历、stat 或重哈希 raw sensor、原 metadata CSV、official test 或 external data；manifest 中的路径不是扩大读取范围的授权。

失败时独立保存原因、已经发生的调用计数、fit ledger、资源记录和终态，不要求完整 `result` 才能记录失败。没有发生的后续调用不能写为完成；存在的临时分数与指标继续标为不可接纳。身份/来源/调用漂移为 `INVALID`，G3 数据不足为 `DATA_INSUFFICIENT`，资源门失败为 `INCOMPLETE_RESOURCE`。终态之后不得在 v1-003 重跑，也不得自动创建 v1-004。

## 6. 审阅与接纳证据

本轮未新增或运行测试；不采用旧执行计划中的测试步骤作为新授权。实际 audit 的来源预检是生产接纳门，不是用替身后端运行的测试。

独立审阅应检查：A2 字节未改；实际计数来自实际数组；25 角色唯一且集合完整；数组/键/标签顺序与 A2 executor 一致；来源门位于首个 fit reservation 前；适配器在写账本前运行并在异常路径恢复；旧 namespace/config/产物未改；新配置只有 namespace/attempt 元信息改变；失败调用记录不依赖完整评价结果；资源 caps 与数据读取边界未扩大。

只在一次合法新运行终态后报告 accepted metrics。即使 `COMPLETE`，也要分别报告四项科学门及路线状态；失败只关闭这一冻结 target 变体，不推断 HGB 家族或全部事件中心架构无效。

## 7. 本轮实际结果

一次 audit、一次 run 已完成，无重试；v1-003 来源、身份、调用及资源门通过，25 次实际拟合均有实测 `candidate_count`。TP/FP/FN 为 150/126/84，F1 `0.5882352941`，四项 numeric/stage 门均 FAIL。原 21 个无可匹配候选的 FN 在本次保存的 transition summary 中恢复数为 0；这是一项实际结果。Route 3 累计真实 fits 为 50，v1-002 仍 `INVALID`。完整来源、资源、独立审阅及结论见 `docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md`。本轮授权已用完，不自动继续新实验。
