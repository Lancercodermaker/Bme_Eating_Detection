# Route 3 v1-003 来源记录恢复执行清单

日期：2026-09-27  
状态：`EXECUTED_COMPLETE / CLOSED_STAGE_MINIMUM_FAIL`；一次 audit、一次 run 已终态，无重试。  
工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`

设计依据：`docs/superpowers/specs/2026-09-27-route3-v1-003-provenance-recovery-design.md`。用户已要求修订设计并重新执行；本清单将该授权限定为修复来源记录契约和同一科学协议的一次新 study。它接续 v1-001/v1-002，不改写旧执行记录。

## 1. 冻结输入、命名空间和预算

- Source：`artifacts/a2-context-verifier-v1-004`，config SHA-256 `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`，audit-ready SHA-256 `bf4e9a10a34e5f17b36d3632356cf8e50cdc1cdb60125fe1d78a9b4e4baabeb4`。
- 新配置：`configs/route3-matching-aware-v1-003.json` 及 `.sha256`；只改变 v1-002 的 namespace/attempt 元信息，科学设置、环境与所有 limits 相同。
- 新输出：`artifacts/route3-matching-aware-v1-003`。
- 新外部预算账本/锁：`artifacts/route3-matching-aware-v1-003-budget.jsonl` 与 `artifacts/route3-matching-aware-v1-003-budget.lock`。
- 一次 audit；只有 `AUDIT_READY` 且来源/身份/资源门全部通过时一次 run。没有 retry、参数搜索、alternate seed、额外阈值或后续新命名空间自动执行。
- 最多新增 25 verifier fit attempts / 25 score calls，candidate fit/predict 0/0，60 inner decodes + 5 outer decodes，5 outer evaluations。
- 900 秒累计 active wall、600 秒 fit wall、2 线程、512 MiB 新 study disk、RSS `min(3 GiB, 50% of invocation startup available memory)`，原 2x 余量门不变。
- Route 3 实际拟合：v1-001 为 0，v1-002 为 25，v1-003 已完成 25，总计 50。逐 study 账本独立，累计消耗如实保留。

## 2. 工程修订与预运行审阅

- [x] 只读核实 v1-002 的 status、target-audit、metrics、fit ledger、resource-summary 和 budget ledger；确认 25 条 actual fit 缺 `candidate_count`，资源失败为空，不改写临时指标。
- [x] 对旧 READY 登记的 15 个 code paths 定向归档原字节至 `docs/evidence/route3-v1-002-code-freeze-2026-09-27.zip`；生成 `docs/evidence/route3-v1-002-recovery-baseline-2026-09-27.json` 保存代码、历史配置与终态证据摘要。归档只包含精确已授权文件。
- [x] 保持 A1/A2 代码字节不变；Route 3 实现 actual rows/arrays 来源生成器，以及唯一角色 lookup 和统一单角色校验。
- [x] audit 与 run 的首个 `reserve_fit` 前，对 25 个训练组合完成同一契约的无拟合检查，并把预检结果及摘要绑定新 READY。
- [x] Route 3 scoped `_persist_fit` 适配器在原持久化调用前写入 actual count、核对原 fit_record 与 actual inputs、核对角色审计；最终仍验证全部 25 条记录。正常和异常路径均恢复 `_persist_fit` 与 `_decoded`。
- [x] 失败保存独立的已发生 calls、原因和资源，不依赖完整 result。已经拟合但持久化失败的 attempt 仍消耗预算。
- [x] workflow config registry 与 CLI 加入 v1-003；冻结新配置及 sidecar。精确确认新 output/ledger/lock 不存在；若存在即停止，不删除或覆盖。
- [x] 独立审阅新代码、设计、配置和恢复基线，确认科学字段与 v1-002 相等，读取范围及资源 caps 未扩大，实际计数未从 expected audit 回填，唯一角色和三层来源门完整。
- [x] 在本轮授权边界内进行必要静态语法与文档编码检查。未新增/运行测试，不重跑 A2，不调用任何模型来做预审。

## 3. 唯一 audit

在精确工作树中使用冻结的 Python 3.10 环境：

```powershell
py -3.10 -B scripts/run_route3_matching_aware.py audit route3-matching-aware-v1-003
```

- [x] 启动一次 audit，并保存新 budget invocation。
- [x] 核验环境、A2-004 完成身份和已登记 materialized 输入；构造 role-local matching-aware 标签，outer 标签保持 null。
- [x] 确认 105 candidate roles、25 verifier roles、41 人、234 eligible GT、outer 4,183 行和跨角色 72,112 行未改变；25 个 G3 检查与 actual provenance 检查都通过。
- [x] 确认 2x synthetic RSS/disk 余量及实际资源监控通过，audit 有效产出新 READY，零模型调用。
- [x] 定向复核 READY 的 config/code/environment/source/target/provenance 绑定及资源记录。

若 audit 终态失败，保留账本和原因并结束本次授权；不运行 run、不重试 audit、不自动改 cap 或创建另一 study。

## 4. 唯一 nested run

仅在上一节所有门实际通过后执行一次：

```powershell
py -3.10 -B scripts/run_route3_matching_aware.py run route3-matching-aware-v1-003
```

- [x] 独立重新核验 READY、config/code/environment/source、target 标签和全部 25 actual fit 输入来源；确认首个 reservation 前的预检通过。
- [x] 执行原 20 inner + 5 outer verifier 图。只用 inner held-out 结果选择原三阈值；每个 held-out role 打分一次并复用该分数，不调用 candidate 模型。
- [x] 每次 fit 持久化前核对 actual provenance；真实 fit ledger、返回 fit records 和最终 manifest 均包含实际 `candidate_count`。
- [x] 结束后核对调用计数 0/0、25/25、60+5、5，核对 25 个唯一角色与全部来源字段，保存 metrics/report/manifest/status/resources 和预算终态。
- 异常分支已实现并经静态审阅，本轮没有异常，未注入故障或运行异常测试。正常路径结束时恢复临时适配函数；没有重试。

## 5. 终态只读复核与报告

- [x] 定向比对恢复基线的 16 个旧 v1-001/v1-002 配置/终态文件，确认其未改；A2-004 config/READY/status source 绑定通过，未修改的 12 个登记代码文件字节与基线相同。这不声称全量重哈希历史 A2 所有输出。
- [x] 核实新 status、READY、manifest、fit ledger、预算 ledger、calls 和资源记录相互一致；需要时仅对明确登记的新产物生成校验摘要，不扩大数据范围。
- [x] 独立审阅工程接纳与证据边界。记录审阅范围及限制，不把审阅说成独立 participant 确认。
- [x] 工程 `COMPLETE` 时分别报告 pooled/per-fold TP/FP/FN、F1、long FP、MAE 和四项 numeric/stage 门；科学门失败仍关闭该固定 target 变体。
- [x] 报告 Route 3 累计真实 fits 及新 study 资源，说明 v1-002 仍 `INVALID`；A1/A2 关闭状态、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。

本清单没有授权 raw sensor、原 metadata CSV、official test 或 external data 的读取、遍历、stat 或重哈希。58 个零注释交叠长 FP 仍为行为 `UNKNOWN`，新结果仅支持核验后的本地标注合约开发结论；不能确认进食行为真值、官方未公布测试性能、官方精确 matcher/API 或 PPG 任务完整性。

唯一运行已获得合法 COMPLETE，四项科学门均 FAIL。全部实测结果、资源、摘要及已完成的独立终态审阅见 `docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md`。本轮授权已用完，不会继续新实验。
