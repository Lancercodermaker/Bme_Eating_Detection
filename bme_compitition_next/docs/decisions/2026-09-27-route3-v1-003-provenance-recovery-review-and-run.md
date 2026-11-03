# Route 3 v1-003 来源契约恢复、审阅与运行记录

日期：2026-09-27  
状态：`COMPLETE / CLOSED_STAGE_MINIMUM_FAIL`；工程恢复完成，四项科学门均未通过。

## 授权与范围

用户明确要求修订设计并重新执行。沿用已经授权的 matching-aware target 科学协议，本轮修复 actual-fit 来源记录契约，审阅新设计，并使用全新 `route3-matching-aware-v1-003` 命名空间进行一次 audit、门通过后一次 run。没有调参、扩展数据范围、重跑 A2 或路线二的授权；不自动启动 v1-004。

设计：`docs/superpowers/specs/2026-09-27-route3-v1-003-provenance-recovery-design.md`。  
执行清单：`docs/superpowers/plans/2026-09-27-route3-v1-003-provenance-recovery-execution.md`。

## 已核实的根因与工程选择

v1-002 实际消耗 25 次成功 verifier 拟合、25 次打分、65 次解码、5 折评价，candidate fit/predict 为 0/0。全部 25 条 actual-fit 记录缺 `candidate_count`；原有角色、组成、正类计数及候选键/矩阵/标签摘要符合预检。实际峰值 RSS `796,614,656 B` 低于运行上限 `2,602,833,920 B`，资源监控无失败。v1-002 保持 `INVALID`，不是内存不足；临时指标不接纳、不用于本轮调参。

直接修改 A2 `_fit` 会改变 A2-004 READY 所要求的共享代码身份。本次保持 A1/A2 文件字节，在 Route 3 范围内适配 `_persist_fit`：从实际训练 rows 构造的实际矩阵行数补 `candidate_count`，核对原实际来源字段，再按唯一 audited role 验证，随后调用原持久化函数。没有从 expected audit 复制候选总数，没有删除或放宽校验。

新增生产来源门在 audit 和 run 首个 `reserve_fit` 前核对全部 25 个实际训练组合，并绑定新 READY；每 fit 持久化前与最终 25 条记录校验继续保留。两个临时适配函数在 `finally` 恢复。失败报告独立于接纳指标，保留已发生调用，错误处理仍关闭终态账本。

## 冻结与静态证据

- 原 READY 登记的 15 个代码文件逐一核对旧摘要后，定向归档到 `docs/evidence/route3-v1-002-code-freeze-2026-09-27.zip`，共 `60,496 B`。
- `docs/evidence/route3-v1-002-recovery-baseline-2026-09-27.json` 固定旧代码身份、归档摘要及 16 个历史配置/终态文件摘要。工程修改后这 16 个文件仍逐一相同，A2 `execution.py` 仍相同。
- 新配置 SHA-256：`a8a48cfe0706d03d133dfaf132f9ff5d1dc25977c79317a0b6c51dd3f01aea25`。除 namespace/attempt 元信息外，新旧配置的全部字段相同，包含 source、target、verifier、thresholds、decoder、evaluator、environment 和 limits。
- 新 output、ledger、lock 在创建配置时定向确认未被使用；不删除历史文件。
- 三个修改源文件已通过静态 AST 语法解析，两份新设计/执行文档通过严格 UTF-8 读取。本轮未新增或运行测试；生产 audit/run 不属于测试替身执行。
- 预审时可用内存 `5,285,724,160 B`，对应预览 RSS 上限 `2,642,862,080 B`。这只是预览，实际 audit/run 各自冻结 startup-derived ceiling，原 2x 余量门与资源监控仍须通过。

科学设置及每 study 的 25 fits、25 scores、900 秒 active wall、600 秒 fit wall、512 MiB disk、2 线程、RSS `min(3 GiB, 50% invocation startup available)` 均不变。历史 v1-001 消耗 0 fits、v1-002 消耗 25；本次最多新增 25，累计最多 50，不擦除旧消耗。

## 独立审阅

独立审阅者 `/root/route_challenge` 完整阅读三个修改源文件、新配置、恢复设计，核对旧冻结副本与当前 A2 `execution.py` 字节。其 pre-run 静态结论未发现 P0/P1 blocker，可进入本轮已授权的 audit；这不表示运行门已通过。训练组合复用原 composer，actual count 取实际矩阵行数，唯一角色查表与顺序校验保留，持久化前验证和最终验证均保留，两个适配函数由 `finally` 恢复，新旧科学配置仅 namespace/attempt 不同。

首轮根因审阅额外指出：只提前保存 calls、仍用成功报告渲染失败会导致二次 KeyError。本次采用独立失败报告；最终失败写出异常也捕获，账本关闭在 `finally`，先写终态 status 后写资源摘要。最新静态复审确认这些问题已处理。

随后审阅者完整阅读正确路径的执行清单及预运行记录，确认其一次 audit、门通过后一次 run、无自动重试的范围。其最终静态复审通过，仍没有调用模型、测试或 audit/run。历史 16 个终态文件全量摘要核对由主执行者完成，独立审阅者只核对其已读范围及 A2 `execution.py` 字节；不能把该限制说成全量独立复算。独立工程审阅不等于独立参与者验证，也不替代真实 audit/run 来源门。

## audit / run 与终态复核

唯一一次 audit 已返回 `AUDIT_READY`：105 candidate roles、25 verifier roles、41 人、234 eligible GT，25 actual-fit 来源预检全部通过，0 次拟合 reservation。audit active wall `12.140 s`，峰值进程树 RSS `791,687,168 B`，audit ceiling `2,516,486,144 B`，study disk `178,694 B`，资源失败为 null。

新 READY 文件 SHA-256 `16e07886aac8e593ee6a9f13fab3feac0a0543189c44223e53188c7a2484aaa1`。主执行者定向核对 config、READY 内容摘要/文件摘要、当前 15 个代码摘要、target audit、25 个唯一有序实际预检记录和 synthetic profile 的绑定。预计 RSS `860,332,208 B`、disk `232,433,875 B`，两个 2x 余量门均通过。audit ledger 恰有一次 invocation、无 fit、无终态失败。

随后唯一一次 run 返回 `COMPLETE`，没有重试。运行期间及 READY 生成后未更改代码或配置。

| 工程证据 | 实际结果 |
|---|---|
| audit / run invocations | 1 / 1 |
| candidate fit / predict | 0 / 0 |
| verifier fit reservations / starts / successful ends / scores | 25 / 25 / 25 / 25 |
| inner / outer decodes；outer evaluations | 60 / 5；5 |
| 实际 fit ledger / metrics / manifest 中含实测候选总数的角色 | 25 / 25 / 25，唯一且有序 |
| audit + run 累计 active wall | 账本 `34.375 s`；关闭后的 resource snapshot `34.390 s`（返回/写出时间差） |
| verifier fit wall | `4.891 s` |
| run peak process-tree RSS / run ceiling | `796,442,624 / 2,526,586,880 B` |
| run resource snapshot study disk / cap | `7,531,662 / 536,870,912 B` |
| resource failure | null |
| Route 3 累计真实 fits | v1-001 0 + v1-002 25 + v1-003 25 = 50 |

主执行者逐一核对全部 25 条实际 fit ledger 与 metrics、manifest、target audit 的角色、训练角色组成、实测候选总数、正类计数、键/矩阵/标签摘要；fit ledger 是 accepted record 的子集，后者另附训练 assigned-GT 摘要。没有用 audit 值填补实测字段。25 个登记 model 文件和 25 个 score 文件按登记路径只重哈希、不加载模型，均与 provenance 中的文件摘要相符。status、config、READY、target、current code、manifest、metrics 和预算终态绑定一致。

`artifacts/route3-matching-aware-v1-003/final-checksums.json` 固定 63 个明确登记的新产物及外部预算账本摘要，自身 SHA-256 为 `1f0ba6768644dabb6c93c2b8d4ab6e8a15e4c22400e208a499d6afbab5f04601`。此文件是终态后只读复核的派生证据，resource-summary 的 disk 是原运行快照，未改写为后续复核文件大小。旧基线的 16 个历史文件及未修改的 12 个登记代码文件仍逐一相同。

终态后，登记文件连同新 checksum 和外部预算账本共 `7,540,296 B`，仍低于 512 MiB，锁已释放。新三份文档通过严格 UTF-8 和损坏文本检查。

### 独立终态审阅

`/root/route_challenge` 完成独立只读终态审阅，结论为可接受工程 `COMPLETE`，无未决 P0/P1。其逐一核对 25 条实际 provenance 在预检、fit ledger、metrics、manifest 中的角色、顺序、候选/正类计数及三个核心摘要；核对唯一 audit/run、25 个成功 fits 与全部调用；核对 config、READY、target、预检及已读源码身份；独立重哈希 63 个登记文件和外部账本，其中 25 个 model 与 25 个 score 文件也与保存的来源记录一致。它没有反序列化模型。

审阅确认 `resource_failure=null`、账本计时与资源快照截点差异合理、保存指标和四门 FAIL 与科学状态一致。其未训练、预测、运行测试、重新匹配或重算指标；工程证据复核不提供独立参与者、独立行为真值或官方未公布测试确认。旧历史文件 16 项全量核对仍是主执行者的单独证据，不扩大独立审阅的历史范围。

## 有效性能结果与路线判断

| 结果 | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| A1 已核验基线 | 153 | 136 | 81 | 0.529412 | 0.653846 | 0.585086 |
| A2-004 已核验基线 | 154 | 106 | 80 | 0.592308 | 0.658120 | 0.623482 |
| Route 3 v1-003 | 150 | 126 | 84 | 0.543478 | 0.641026 | 0.588235 |

| Outer fold | 选定阈值 | TP / FP / FN | F1 | long FP / FP | long-FP fraction | start / end MAE (s) |
|---|---:|---|---:|---|---:|---|
| outer-0 | 0.50 | 33 / 26 / 17 | 0.605505 | 23 / 26 | 0.884615 | 295.584 / 147.957 |
| outer-1 | 0.50 | 27 / 13 / 22 | 0.606742 | 11 / 13 | 0.846154 | 446.184 / 209.499 |
| outer-2 | 0.25 | 36 / 31 / 17 | 0.600000 | 20 / 31 | 0.645161 | 368.279 / 163.078 |
| outer-3 | 0.25 | 21 / 19 / 14 | 0.560000 | 13 / 19 | 0.684211 | 371.085 / 79.062 |
| outer-4 | 0.25 | 33 / 37 / 14 | 0.564103 | 22 / 37 | 0.594595 | 381.827 / 191.632 |

pooled long FP `89/126`（70.6349%），start/end MAE `369.682/162.627 s`。候选仍是 4,183 个，覆盖 `213/234` GT；21 个无可匹配候选的 FN 仍未恢复。五折 F1 均未达 0.66，五折 long-FP fraction 均超过 0.25；numeric minimum/ideal、stage minimum/ideal 四项均 FAIL。

F1 相对 A2-004 降低 `0.035246`；TP 少 4、FP 多 20、FN 多 4。当前证据不支持继续投入这一冻结的 matching-aware pointwise target 变体，状态为 `CLOSED_STAGE_MINIMUM_FAIL`。这不宣告 HGB 家族或全部事件中心架构无效。本轮停止模型投入与执行，优先核验已在路线二讨论的候选区间形成与输出约束；路线二仍为 `NOT_EXPERIMENT_AUTHORIZED`，需要补齐独立授权前提，不能据此自动运行，也不能归因于已证实的 300 秒融合根因。

v1-002 保持 `INVALID`，本次 v1-003 成为有效的 Route 3 开发证据；不追认旧临时指标。

## 结论边界

工程 `COMPLETE` 与 numeric/stage 科学门分别判断。结果仍来自已经参与开发的全部 41 人，只支持本地核验后的标注合约；不确认官方未公布测试性能、官方精确 matcher/API 或全天行为真值。58 段行为仍为 `UNKNOWN`。A1 CLOSED、A2 fixed-26D CLOSED_STAGE_MINIMUM_FAIL、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。
