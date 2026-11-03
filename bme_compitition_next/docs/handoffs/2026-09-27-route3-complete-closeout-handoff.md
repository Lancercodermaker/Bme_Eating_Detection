# 路线三已完成后的证据交接

日期：2026-09-27  
性质：已执行结果的交接；没有待执行的新实验。

## 目标与下一步

在新对话中只读核验和整理 Route 3 的已有终态证据，返回可带回主对话的证据包；随后由用户带回路线 1/2/3 的结果进行整合与架构讨论。本交接不启动新的 Route 3 变体。

用户已明确选择“只读收口 v1-003，返回证据包后整合路线 1/2/3”，不是重新设计或执行新的 Route 3 实验。

工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。路径均相对此工作树；以登记产物支持事实，摘要如与产物矛盾，应报告矛盾，不修复或重跑。

所有命令使用这一精确 workdir；相对路径须先解析为工作树内的绝对路径。PowerShell 读取用 `-LiteralPath`。禁止根目录或父目录搜索、通配符枚举和目录遍历；文件不存在时直接报告精确路径，不扩大搜索。

## 当前状态

| 事项 | 当前证据与状态 |
|---|---|
| 路线 1 | 现有官方资料审查完成；部分合约已核验，官方接口与精确 matcher 仍未知；不是模型实验 |
| 路线 2 | 证据整理、验证设计与独立审阅完成；`NOT_EXPERIMENT_AUTHORIZED`，没有执行验证实验或有效性能结果 |
| Route 3 v1-001 | `INCOMPLETE_RESOURCE`，拟合前余量门停止，真实 fits=0 |
| Route 3 v1-002 | `INVALID`，实际完成 25 fits；缺 `candidate_count` 导致来源拒收，并非 OOM；临时指标不接纳 |
| Route 3 v1-003 | 工程 `COMPLETE`，科学 `CLOSED_STAGE_MINIMUM_FAIL`，一次 audit/一次 run，无重试，真实 fits=25 |

v1-003 TP/FP/FN=150/126/84，Precision=0.5434782609、Recall=0.6410256410、F1=0.5882352941。相对 A2-004 F1=0.6234817814 下降约 0.035246。四项 numeric/stage 门均 FAIL；long FP=89/126，start/end MAE=369.682/162.627 秒。

候选仍为 4,183 个、覆盖213/234 GT；保存的 transition summary 显示原21项无可匹配候选 FN 恢复0项。调用为 candidate fit/predict=0/0、verifier fits/scores=25/25、decodes=60+5、outer evaluations=5。Route 3 累计真实 fits=50，不擦除 v1-002 的消耗。

运行峰值 RSS=796,442,624 B，上限2,526,586,880 B，`resource_failure=null`。已接纳的结果不代表 F1 达标，也不否定 HGB 整个家族。

## 冻结边界

- v1-003 已终态，恢复执行授权已用完。设计/执行清单中的命令是历史记录，不能再次执行；不能自动创建 v1-004 或 A2-005。
- 不训练、predict/predict_proba、重新生成标签/候选、重新解码、调用 matcher/evaluator 或启动 audit/run；不运行测试。
- 不修改代码、配置、旧文档、历史产物或 production，不清理输出。新对话只在回复中交付证据包。
- 不读取、遍历、stat 或重哈希 raw sensor、原 metadata CSV、official test 或 external data，包括 `E:/bme_compitition/official_test_dataset`。这次交接不需要重读官方 PDF、队友 PDF 或公开仓库。
- 不重新加载派生训练缓存或传感器支持；所需结果已有明确登记的终态文件。model 文件仅在 final-checksums 登记的精确路径上重哈希，不反序列化；路径登记不授权执行。
- 41 人均已用于开发；不能称独立 participant 确认。58 段原A2零注释交叠长FP仍为行为 `UNKNOWN`。接受本地标注合约不提供全天行为真值。
- A1 CLOSED；A2固定26D CLOSED_STAGE_MINIMUM_FAIL；Formal G1 FAIL；full training BLOCKED；production UNCHANGED。

## 必读文档

1. `docs/superpowers/specs/2026-09-27-route3-v1-003-provenance-recovery-design.md`
2. `docs/superpowers/plans/2026-09-27-route3-v1-003-provenance-recovery-execution.md`
3. `docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md`
4. `docs/decisions/2026-09-27-route3-v1-002-resource-review-and-run.md`
5. `docs/decisions/2026-09-26-official-annotation-contract-review.md`
6. `docs/decisions/2026-09-27-route2-design-review.md`

前三份终稿已完整独立复审，工程与科学结论、历史消耗、读取范围及审阅限制明确分开。原记录也包含执行前静态审阅和执行后独立终态审阅；均没有未决 P0/P1。

## 精确终态证据

- `configs/route3-matching-aware-v1-003.json`。
- `configs/route3-matching-aware-v1-003.sha256`（不是 `.json.sha256`）。
- `artifacts/route3-matching-aware-v1-003-budget.jsonl`。
- `artifacts/route3-matching-aware-v1-003/` 下：`run-status.json`、`audit-ready.json`、`fit-provenance-precheck.json`、`target-audit.json`、`metrics.json`、`report.md`、`run-manifest.json`、`resource-summary.json`、`verifier-fit-ledger.jsonl`、`verifier-score-provenance.jsonl`、`final-checksums.json`。
- `final-checksums.json` 的63个文件条目及外部预算账本均可按精确登记路径只读重哈希；先检查路径解析后仍在新产物目录内。不要遍历其他目录或从报告链接扩读输入。

绑定摘要：config `a8a48cfe0706d03d133dfaf132f9ff5d1dc25977c79317a0b6c51dd3f01aea25`；READY 文件 `16e07886aac8e593ee6a9f13fab3feac0a0543189c44223e53188c7a2484aaa1`；final-checksums 文件 `1f0ba6768644dabb6c93c2b8d4ab6e8a15e4c22400e208a499d6afbab5f04601`。

## 返回主对话的内容

返回来源路径、工程与科学状态、25条实际来源记录一致性、唯一audit/run与调用/资源账本、保存的pooled/per-fold结果、累计50fits、审阅范围及限制。概述哪些结论可以带入架构讨论，哪些仍缺证据。标明没有执行新实验或形成新实验授权。

路线 2 仍需补齐新16D特征来源、标签语义及单次study预算/范围。未知官方接口、精确匹配算法、PPG场景合规和新增独立参与者等缺口继续保留。不要把路线 1/2 的文档完成混同为三条路线均有模型实验成绩。
