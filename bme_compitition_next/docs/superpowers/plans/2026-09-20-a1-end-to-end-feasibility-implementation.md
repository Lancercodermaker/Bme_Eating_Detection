# A1 End-to-End Feasibility Implementation Plan

> **2026-09-22 状态更新：** audit 005已通过，Task 9真实五折运行COMPLETE（105 candidate +25 verifier fits）。pooled F1=0.5851，最低/理想及综合门槛均FAIL；按既定规则关闭被测A1协议。见[结果决定](../../decisions/2026-09-22-a1-end-to-end-feasibility-result.md)。下文audit 004/fit=0描述保留为历史状态；checkpoint恢复仍不支持，旧G1/full-training/production冻结状态不变。

> **2026-09-20 有效补充：** [D3-Ready-v1](../../decisions/2026-09-20-a1-d3-combined-readiness-revision-proposal.md)的R1–R4已获用户明确批准，覆盖本计划中空session直接拒绝、index bounds硬包含及旧训练标签口径的相应条款。实施必须使用可审计身份/标签sidecar，不改旧NPZ。[review复核](../../decisions/2026-09-20-a1-plan-implementation-review.md)发现8项差距，Task 9真实run前必须关闭下列RV门禁；已有测试通过不能代替这些证据。

## Review 追加执行与验收门禁

修订进度见[第二轮review记录](../../decisions/2026-09-20-a1-revision-review-followup.md)：D3与RV冷启动安全/正确性修订已实现，180项全量测试通过。RV8的checkpoint恢复功能尚未实现，当前采用拒绝恢复/拒绝换目录重跑的fail-closed行为；不能把下面旧步骤整体勾选当作恢复已可用。最新真实audit 004因RSS超限停止，Task9 fit/predict尚未启动，旧audit 003的READY代码快照已过期。

- [ ] RV1 / Tasks6、8：把资源监控接入实际audit/fit/predict/写盘路径；独立worker、≤1s采样、超时终止、四线程上限、审计冻结RSS与累计预算。用合成worker证明超限会停止，不能只测试BudgetLedger计数。
- [ ] RV2 / Task4：按matched_count加权聚合start/end MAE；增加1对9匹配数量反例（1000ms与0ms → pooled100ms），并验证逐fold质量判定。
- [ ] RV3 / Tasks1、2、8：配置严格冻结IoU、duration/fusion、HGB和所有预算；配置记录并核验批准输入hash、ledger、D3sidecar版本与内容，不能仅记录本次读到的hash。保持训练/评价eligibility语义分离。
- [ ] RV4 / Tasks5、7、8：真实数据流绑定完整fit signature/model hash/reference row hash/raw与relative score，覆盖所有候选与verifier角色；持久化匹配IDs、逐participant统计及无GT无预测participant的显式NA行。缺来源禁止READY/COMPLETE。
- [ ] RV5 / Tasks4、8、9：在真实runner内调用完整五fold质量验收，输出numeric/stage最小与理想判定、完整report及hashes；禁止只保存pooled F1便认为交付齐全。
- [ ] RV6 / Tasks7、8：生成一次完整冻结fold/role快照并由运行消费；核验每人outer-valid恰好一次、已批准outer/inner集合一致；将evaluation/metrics等实际依赖代码及环境版本纳入身份。当前outer集合核对一致，此项修复审计绑定缺口。
- [ ] RV7 / Tasks7、8：新增无真实模型的execute_full_pipeline与runner集成测试，fake estimator记录实际fit/reference/scored集合；验证外层GT扰动不改变该fold选择及预测，threshold不增加fit，G3失败即停止，artifact齐全，资源超限可终止。静态role graph测试不算完成这些步骤。
- [ ] RV8 / Tasks8、9：完整run状态机，已完成/失败run不能隐式重跑；resume必须显式且继承预算。验证input-audit hash，已有目录不得落盘覆盖；非成功停止返回非零退出码，未知程序错误归INVALID而非INCOMPLETE_RESOURCE。

以上恢复已批准契约，不增加研究配置、预算、人口或模型实验。R1–R4实现与RV1–RV8全部通过后，才可重新申请机器就绪判定并按既有授权进入有限run；不需再次请求用户批准A1/D1–D5/R1–R4。

> **For agentic workers:** 使用 `executing-plans`，按任务 INLINE 执行；不主动派发子代理。复用当前隔离工作树，逐项核验后勾选。

**Goal:** 建立并验证已批准 A1 的隔离、边界、预算与事件指标路径，随后在有限投入内评价 0.66/0.80 开发目标。

**Architecture:** 新建独立 `eating_event.a1` 包及专用 runner，消费冻结缓存、ledger 与 fold manifests。模型拟合、阈值 reference、选择与最终评价分别保存来源；任何不可证明的隔离或身份失败均停止。历史 runner、G1 产物和 production 不改写。

**Tech Stack:** 当前 Python / NumPy / scikit-learn / pytest 环境；依赖版本在执行前记录和锁定到 run manifest，不在本阶段顺便升级依赖。

---

## 权威输入与权限

工作目录：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。以下文件路径均相对此目录。

- [A1 授权决定](../../decisions/2026-09-20-a1-end-to-end-feasibility-authorization.md)是本阶段配置、上限和验收规则的权威来源。
- [设计审查稿](../specs/2026-09-20-a-end-to-end-feasibility-design-review.md)第 4–10 节提供理由、数据流和历史差异。
- 旧路线继续冻结：G1 FAIL、局部实验 STOPPED、full training BLOCKED、production UNCHANGED。
- 本计划创建时未实现以下文件、未运行测试、未启动新推断/fit。下面命令是未来执行说明，不是完成记录。
- 当前工作树含大量先前未提交变更；禁止 `git add .`、整体回滚或清理。只处理本计划明确列出的新文件；提交时逐个指定本阶段文件，不能顺带提交既有改动。

## 文件职责

| 新文件 | 唯一职责 |
|---|---|
| `configs/a1-end-to-end-feasibility-v1.json` | 固定配置、来源文件及输入 hash、资源上限 |
| `src/eating_event/a1/__init__.py` | 包声明，不做读取/训练 |
| `src/eating_event/a1/contracts.py` | 身份、集合隔离、schema、fit signature |
| `src/eating_event/a1/inputs.py` | manifest/ledger/cache 验证、只读输入加载 |
| `src/eating_event/a1/boundaries.py` | accepted-window support 连通区间 |
| `src/eating_event/a1/events.py` | relative-score 候选、16D 特征、训练标签、decoder |
| `src/eating_event/a1/metrics.py` | participant 匹配、整数计数、质量指标与判定 |
| `src/eating_event/a1/scoring.py` | 显式 HGB 参数、合法复用、reference 与 OOF score |
| `src/eating_event/a1/budget.py` | 进程树监控、累计预算、fit attempt ledger |
| `src/eating_event/a1/pipeline.py` | 5×4×4 角色图、inner 选择、outer 冻结评价 |
| `scripts/run_a1_feasibility.py` | audit/run 两种显式模式与独立输出目录 |
| `tests/test_a1_contracts.py` / `test_a1_inputs.py` / `test_a1_boundaries.py` | 来源与边界反例 |
| `tests/test_a1_events.py` / `test_a1_metrics.py` | 特征语义、解码顺序、指标反例 |
| `tests/test_a1_scoring.py` / `test_a1_budget.py` / `test_a1_pipeline.py` | 拟合来源、上限与完整流程隔离 |

不修改 `run_event_verifier.py`、`diagnostic_bounded_proposal.py`、旧 configs 或旧 model/artifact 文件。可读取已有纯函数实现作为参考；不得调用带 all-participant fallback 或 raw stat/read 副作用的旧 orchestrator。

## Task 1：冻结配置与来源类型

- [ ] 在 `contracts.py` 定义不可变窗口身份 `(participant_id, record_id, session_id, row_index)`；time 不是唯一 ID。candidate 另带 component ID、bounds、ordered support IDs；prediction 有独立稳定 ID。所有集合/hash 均采用排序后的确定性序列化。
- [ ] 建立 `ScoreProvenance`，字段为 role、fit_participants、scored_participants、selection_participants、threshold_reference_participants、model_hash、fit_signature、reference_row_hash、reference_count、q、threshold、feature_schema。reference role 允许 fit-row scoring，OOF/heldout role 不允许交集；外层 valid 不得进入 fit/reference/selection。
- [ ] 首先写真实泄漏反例，而非只检查字段存在。例如 `tests/test_a1_contracts.py`：

```python
import pytest
from eating_event.a1.contracts import require_disjoint

def test_heldout_participant_cannot_be_in_fit_set():
    with pytest.raises(ValueError, match="participant overlap"):
        require_disjoint({"p1", "p2"}, {"p2"})

def test_legal_score_partition():
    require_disjoint({"p1", "p2"}, {"p3"})
```

对应最小集合检查，不捕获后降级：

```python
def require_disjoint(fit_participants, scored_participants):
    overlap = set(fit_participants) & set(scored_participants)
    if overlap:
        raise ValueError(f"participant overlap: {sorted(overlap)}")
```

- [ ] 冻结 JSON：q=.9、thresholds=[.1,.25,.5]、seed=20260910、outer=5/inner=4/subinner=4、candidate_fuse_ms=300000、decode_fuse_ms=600000、min_duration_ms=180000、long_fp_ms=600000、strict_iou=.25、16D schema=`a1_relative_event_features_v1`，资源值采用授权决定第 4 节。
- [ ] 显式写 HGB：candidate learning_rate=.05、max_iter=100、max_leaf_nodes=31、min_samples_leaf=1、l2_regularization=.001；verifier 同值但 max_leaf_nodes=15；两者 positive_weight=3、random_state=20260910。其余会影响 fit 的库默认项须核查实际安装版本并显式记录，不通过遗漏参数伪造与旧模型一致的 signature。
- [ ] 运行 `python -m pytest tests/test_a1_contracts.py -q`；先观察反例失败，再实现使其通过。配置验证拒绝额外 threshold/seed、非有限参数、越界预算，不接受隐式搜索扩展。

## Task 2：只读输入与模型复用清单

- [ ] `inputs.py` 只消费 `artifacts/g1-candidate-coverage-v4/cache-manifest.json`、`manifest-audit.json`、`eligibility.json` 及它们指向的批准 ledger；缓存路径必须落在 `artifacts/g1-formal-cache-v3-final`。raw 路径只当 opaque identity，不执行存在性检查或 stat。
- [ ] 从 `artifacts/g1-event-balanced-candidate-objective-probe-v1/fold-manifest.json` 和 `models-manifest.json` 获取 outer folds/模型角色；完整读取实际 schema 后建立显式字段适配，拒绝缺字段，不猜路径。ledger SHA-256 必须为 `6e7580a6dc4562ced645361b086a08143a2051516a0804d7031c964174438c6d`，其余输入逐文件核验声明 hash 并写入新配置。
- [ ] 核验 41 participants、每人恰好一次 outer-valid、canonical GT=234。已记录缓存总数 1127 records / 632100 windows（35948 positive、583145 negative、13007 ignore）用于核对；不匹配立即查明，不能自动改预期常数。无餐 participant 与空 record 保留。
- [ ] 按 manifest entry 对 cache 全文件 hash、数组长度、时间次序、111D、finite values、label 集合、稳定身份和 session bounds 核验。canonical event ID 用原 ledger ID；跨 session 重叠不复制 GT，不从 outer labels 决定推断保留区域。
- [ ] `test_a1_inputs.py` 注入临时小缓存：hash 篡改必须失败；GT 跨两 record 仍计一个；缺 session 必须失败；raw I/O spy 一旦调用就抛错；6C7 无 GT 仍在 folds。运行 `python -m pytest tests/test_a1_inputs.py -q`。
- [ ] 写 reusable-model inventory：manifest 的 65 路径先按完整 signature/字节 hash 归并，不先假定 25 全可复用。缺证明标记 non-reusable；冲突标记 INVALID。库/代码/hash 核验完成前不反序列化。

## Task 3：保守边界与候选语义

- [ ] `boundaries.py` 实现授权决定的覆盖并集组件；先写以下回归例：同 record `[0,15000]`、`[7500,22500]` 属同组件，`[30000,45000]` 属另一组件；不同 session 即使时间相接也不能同组件。窗口 crosses_hard_gap=true 或超 session bounds 必须报错。
- [ ] `events.py` 先按 relative_score≥0 选择支持窗口，再在同一组件内按冻结 candidate fuse 生成事件；完整记录 support，而非只保留时间。不可跨不连续支持区间填洞，q reference 仍消费全体 fit rows。
- [ ] 16D 顺序固定：relative max/mean/std/p25/p75/min，支持窗口数、duration_seconds、count/duration_seconds，coverage mean/min/max，start day phase sin/cos、end day phase sin/cos。时间相位沿用历史实现的定义并写 schema；std 与 quantile 约定显式记录。所有结果 finite，duration>0；无支持不构造候选。
- [ ] 标签函数与推断函数分离：训练 candidate 与其 participant canonical GT 任一 strict IoU>.25 即为正。验证 candidate 生成与特征 API 不接收 GT；只在评价阶段访问 truth。
- [ ] decoder 按 verifier threshold、min duration、同 component fusion 的顺序。没有跨 record 预测去重或 GT 驱动的质量过滤。
- [ ] `test_a1_events.py` 必测：两个相同 relative-score 分布但不同 raw/reference 偏移得到相同特征；两个各短于180s的高分候选不能先合并绕过 duration；组件间不能靠600s fuse桥接；改变验证GT不改变预测。运行 `python -m pytest tests/test_a1_boundaries.py tests/test_a1_events.py -q`。

## Task 4：身份安全的事件指标

- [ ] `metrics.py` 按 participant 分组，对 canonical GT 与稳定排序 prediction 运行 strict IoU>.25 greedy 降序匹配；相同 IoU 按冻结 truth/prediction index 顺序打破并列。先核对本地 `metrics.py` tie ordering，保留其规则，不改成 maximum-cardinality。
- [ ] 为每 participant 保存 matched ID pairs、unmatched prediction IDs、unmatched GT IDs；TP/FP/FN 均从这些集合生成。先汇总 counts 再计算 F1；不能把不带 participant 的 intervals 全局重匹配。
- [ ] `test_a1_metrics.py` 包含以下可手算例：p1 有一个GT `[0,100000]` 无预测，p2 无GT但预测同区间，合计 TP=0/FP=1/FN=1。另测 IoU 恰为 .25 不匹配、一个GT两个相同预测只有一个TP、跨session共享GT只计一次、空GT/空预测F1为None、零matches MAE为None。
- [ ] 边界误差累加后除 matched_count；long-FP只消费同一匹配的 unmatched IDs；0FP fraction=0。无可靠监测时长，FP/hour=null，原因明确；可选辅助时长只能命名 accepted-window-support-hour，并先按participant合并覆盖区间。
- [ ] 分开实现 numeric_minimum、numeric_ideal、majority_folds、quality_per_fold、stage_minimum、stage_ideal，完全按授权决定判定；任何缺失 outer fold 不能生成 complete=true。运行 `python -m pytest tests/test_a1_metrics.py -q`。

## Task 5：scorer、reference 和逐 fit 的 G3

- [ ] `scoring.py` 根据完整 signature 决定合法复用或新的唯一 fit；fit 输入仅相应 participants 的 0/1 rows。拟合完成产生 model SHA 与 fit-row/label/schema/environment hashes。任何 ValueError 记录失败并向上传递，不调用 fallback。
- [ ] 在该模型自身 fit participants 的全部批准缓存 rows 上计算 reference；stable IDs 每个恰好一次，窗口等权，linear quantile。保存 threshold/reference row hash/count，不缓存成可混入 OOF 的训练 score 表。
- [ ] 对目标 heldout participants 评分前先执行隔离检查。每条 score 绑定 model/reference provenance。三个 q 历史文件只可能是同一模型的别名；本阶段不运行 .7/.8。
- [ ] verifier fit 前独立计算正候选数、正 participant 数、正 canonical GT 数以及两类是否存在；不足20/5或单类即停止，不把 outer/其他 fit 的计数补入。
- [ ] `test_a1_scoring.py` 使用带 fit participant 记录的 fake estimator：证明 reference 含 IGNORE 但 loss 不含，heldout 不进入reference；reference空/非finite失败；model signature不同不复用；19正候选/4正participant/单类均失败；G3通过例满足20正候选、5人且有负类。运行 `python -m pytest tests/test_a1_scoring.py -q`。

## Task 6：资源护栏先于真实数据运行

- [ ] `budget.py` 把 wall/RSS/disk/fit attempts 记录到 append-only run ledger；续跑先读已耗预算。fit尝试先预留计数再启动worker，中断仍消耗一次。任何失败不自动重试。
- [ ] 在专用子进程运行单个fit，限制CPU线程数；父进程监控本研究进程树与输出目录。只终止本run创建的worker。Windows进程与内存采集实现须经当前平台验证；若不可用则返回 NOT_READY，不用静默空读数代替。
- [ ] 预算检查在worker启动前、运行中、产物落盘前后执行；监控周期≤1s，报告可能的采样超调，不能宣称操作系统级零超调。模型/score大文件分块写临时文件，预留空间后原子完成；异常保留失败manifest，不发布完整结果。
- [ ] `test_a1_budget.py` 使用fake clock/RSS/disk sampler验证所有边界、worker失败仍计数、resume不能清零；用短命合成worker验证超时终止和子进程内存计入。不得用真实模型来测资源护栏。运行 `python -m pytest tests/test_a1_budget.py -q`。

## Task 7：nested orchestration 与无模型隔离演练

- [ ] `pipeline.py` 在任何 fit 前输出完整角色 DAG：每 outer 的1 outer scorer、4 inner scorers、16 subinner scorers，以及4 inner verifiers和1 outer verifier。共105/25个逻辑角色。角色按完整signature去重，不按fold名字猜测相同。
- [ ] 既有outer/inner集合优先从批准manifest恢复；为每个inner-train生成4个participant folds时沿用已冻结participant分层算法，seed固定20260910。先保存完整 fold manifest/hash，再评分；不能从outer性能选择partition。需读取label统计来构造训练侧fold时仅限当前训练侧人口。
- [ ] 对每inner U/W：subinner模型生成U的OOF候选，fit inner verifier；scorer refit U评分W；在相同W verifier分数上评价三个threshold，不重新训练。每个T participant恰好作为一次W。所有inner验证计数按threshold汇总，依次按F1/少FP/高threshold选择。
- [ ] final outer verifier只能用四个inner scorer对各W得到的T OOF候选；不能用inner verifier分数代替训练特征，也不能拼接全局outer OOF文件。outer candidate fit T后对V评分，已选threshold执行一次；所有outer指标仅进report。
- [ ] `test_a1_pipeline.py` 使用41个synthetic participant及fake fit/predict回调检查：105/25角色上界、outer V不进入任何fit/reference/selection、U verifier每条训练score来自不含该人的fit、三个threshold不增加fit、篡改V标签不改变该outer已选threshold和预测、G3失败不继续final fit、相同timestamp跨人不匹配。
- [ ] fake callback测试不访问真实缓存、不训练模型。运行 `python -m pytest tests/test_a1_pipeline.py -q`；失败就停在实现阶段，不进入真实数据排查。

## Task 8：runner、输出契约与就绪检查

- [ ] `scripts/run_a1_feasibility.py` 提供 `--mode audit` 与 `--mode run`；无mode即报错。两者要求显式 `--config` 与新 `--run-dir`，禁止目录覆盖或写入旧artifacts；resume须显式检查run ID/config/input hashes及剩余预算。
- [ ] audit模式执行只读输入核验、角色DAG、复用清单与资源可用性检查；不调用模型predict/fit。run模式仅在同一配置/输入/代码hash对应的审计通过后执行，不接受人为编辑 passed 字段；重验关键摘要并保留证据。
- [ ] 保存 `run-manifest.json`、`input-audit.json`、`folds.json`、`role-graph.json`、`reuse-inventory.json`、`fit-ledger.jsonl`、score provenance、candidate/prediction/match身份表、各fold所选threshold、`metrics.json`、`report.md`、文件 hashes。报告含候选规模、coverage与一对一TP的区别、6C7 FP、短事件结构限制、legacy差异、资源/失败状态与独立确认缺失。
- [ ] 在隔离合成输入上跑runner全流程，证明输出完整性、失败不伪造complete、不会改旧文件。使用glob只选新测试：

```powershell
$a1Tests = Get-ChildItem -LiteralPath tests -Filter 'test_a1_*.py' | ForEach-Object { $_.FullName }
python -m pytest @a1Tests -q
```

预期全部通过；此时只可宣称合成契约测试通过。若需要改动任何既有source，先说明必要性并对受影响模块追加针对性回归；不得借机修 union。

- [ ] 完成代码/协议自审、生成schema/config/source hashes；复核D1–D5全部映射到上述任务。文档与实现不一致时先修正实现或显式修订决定，不以性能结果为理由放宽。

## Task 9：已批准研究的受控执行与投入结论

只有 Task 1–8 完成并记录就绪证据后执行。当前计划交付不执行这些命令。

- [ ] 启动不拟合审计；新run目录使用唯一ID，例名 `a1-end-to-end-feasibility-v1-001` 若存在即失败：

```powershell
python scripts/run_a1_feasibility.py --mode audit --config configs/a1-end-to-end-feasibility-v1.json --run-dir artifacts/a1-end-to-end-feasibility-v1-001
```

预期 READY、输入hash/角色/预算核验通过且fit_count=0；audit时间计入6h总额。缺证据即输出原因，不把审计失败解释为模型无效。

- [ ] 使用同一run目录中的有效审计开始run，不能覆盖既有完成结果：

```powershell
python scripts/run_a1_feasibility.py --mode run --config configs/a1-end-to-end-feasibility-v1.json --run-dir artifacts/a1-end-to-end-feasibility-v1-001
```

预期是完整五fold结果或明确停止状态；不预设F1成功。不得看outer结果后修改本run阈值、duration、特征、预算或seed。

- [ ] 报告 A事实/B实现/C历史/D缺证据/E推断；将新开发结果与历史结果分表，逐项展示numeric与stage门槛。正式G1、full training、production旧状态原样附录。
- [ ] 完整合法F1<.66：关闭被测协议并形成新的设计/投入讨论；.66–.80且质量稳定性通过：达到最低开发阶段目标，讨论是否值得提升；≥.80且其余通过：达到理想开发阶段目标，仍不宣称独立确认。资源/协议中止不构成完整性能负结果。
- [ ] 新增 `docs/decisions/2026-09-20-a1-end-to-end-feasibility-result.md` 仅在实际结果存在时填写；若实际日期改变则使用实际日期。不能现在创建空的成功记录。union/full training绝不自动接续。

## 计划自审记录

设计第4–6节对应Tasks1–5；第7节对应Task7；第8节对应Tasks2/6；第9节对应Tasks4/9；第10节union保持范围外。D3采用窗口支持替代的语义变更已明确记录，D4预算不是性能估计，D5数值与综合门槛分开。所有任务目前未勾选；未把文档检查当作代码或模型验证。
