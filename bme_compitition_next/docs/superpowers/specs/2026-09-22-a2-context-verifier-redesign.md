# A2 事件上下文验证器 redesign

日期：2026-09-22
状态：`DESIGN_DRAFT / NOT_EXECUTION_AUTHORIZED`
前置决定：A1 完整五折运行已关闭被测协议；本文件仅定义下一种可证伪设计，不重开 A1 参数搜索。

## 1. 目标与证据边界

目标是在保持 A1 候选集合、participant 划分、234 个 canonical GT 和官方 strict IoU > 0.25 评价不变的条件下，检验**事件验证器缺少候选内外的时间证据**是否造成已覆盖事件漏报及背景长误报。A2 是新的开发协议，不能把它的结果写成独立确认或官方 test 成绩。

依据 [A1 结果决定](../../decisions/2026-09-22-a1-end-to-end-feasibility-result.md)及对已保存 `matches.json`、`predictions.jsonl`、`event-candidates.jsonl`、五个 outer verifier score 文件与批准的 eligibility ledger 的只读关联：

| A1 现象 | 数量 | 解释界限 |
|---|---:|---|
| 最终 TP / FP / FN | 153 / 136 / 81 | pooled F1 = 0.585086；5/5 折低于 0.66 |
| FN：无 IoU > 0.25 的候选 | 21 | 验证器无法恢复；A2 不改变这一数量 |
| FN：有候选但所有匹配候选低于本折 verifier threshold | 59 | 指向验证/排序环节，但不证明改阈值有益 |
| FN：候选过阈值后被 180 s 最短时长规则过滤 | 1 | A2 不改时长规则 |
| FP：与任何同 participant GT 无时间交叠 | 103 | 需要识别背景活动；不能简单解释为边界误差 |
| FP：有交叠但 IoU ≤ 0.25 / 可匹配却未被一对一匹配选中 | 17 / 16 | 后者不等于独立真实事件 |
| 长 FP（≥600 s） | 95 / 136 | 5/5 折 long-FP 门槛失败 |

这是一种基于**已暴露开发五折**的事后误差分类，不是新模型效果或独立因果证明。A1 的 outer 候选共 4183 个，213/234 个 GT 有候选覆盖，最终只匹配 153 个。候选覆盖与最终 TP 的差距支持先检查下游表达，但原 Formal G1 仍为 FAIL。

## 2. Project preflight

| 字段 | 本阶段决定 |
|---|---|
| Goal | 检验固定候选之上的事件上下文能否改善最终事件级 F1 与长误报 |
| Success metrics | 冻结的最低开发目标：pooled F1 ≥ 0.66、至少 3/5 折 F1 ≥ 0.66、每折 long-FP fraction ≤ 0.25、每折 matched start/end MAE ≤ 900 s；理想 pooled F1 ≥ 0.80 单独报告 |
| Constraints | target train only；41 eligible participants / 234 GT；participant-disjoint 5 outer / 4 inner / 4 subinner；现有 candidate、q=0.90、duration/fusion、IoU、D3 身份与边界不变；不读取 raw、official test 或 external data |
| Prior art | 本地 A1 五折结果、09-14 冻结架构、09-19 G1 停止决定；本文件不借用外部论文数值证明效果 |
| Baseline | A1 在同一批候选上 pooled F1=0.585086、TP/FP/FN=153/136/81；这是开发基线，不是独立确认 |
| Candidate approaches | V：固定候选的上下文 verifier；T：仅调整阈值或时长；P：扩充 proposal set。选择 V，理由见第 3 节 |
| Critical assumptions | 已保存候选角色的逐窗口 relative scores 能与批准缓存窗口、候选 support 和 role graph 唯一关联；候选周边分数含额外判别信息；离线事件输出允许观察候选之后最多 300 s |
| Risks | 同一开发五折已用于设计；新增特征可能放大参与者差异或记录边缘效应；A2 不解决 21 个无候选 FN 或 Formal G1；score/candidate artifact 可能缺少可靠关联 |
| Validation experiments | 本文件不执行。未来先做不拟合身份/特征 audit，再做一个冻结配置的嵌套五折 verifier 对照；不作 feature、threshold 或 seed sweep |
| Kill criteria | 身份/hash/OOF 关联不完整、特征需 GT 或跨 component、资源门槛超限即停止；完整结果未过既有 stage minimum 则关闭此 V 变体，不追加局部搜索 |
| Recommendation | REDESIGN |
| Confidence | 对 A1 计数分解为高；对“上下文特征会提升 F1”为低；对开发五折向未见 participant 泛化为未知 |

路由：`workflow_path=RESEARCH`，`execution_mode=INLINE`，执行后端为当前 Codex 的只读文件/命令工具。当前范围是设计文档；模型 fit、predict、production 修改预算均为 0。下一阶段只有在设计、实施计划和资源预算单独冻结后才可执行。

## 3. 方案比较与选择

| 方案 | 改动 | 价值 | 主要代价/限制 |
|---|---|---|---|
| **V：事件上下文 verifier（选择）** | 保留 16 个 A1 事件特征，增加固定的同组件时间分数特征；HGB 配置不变 | 直接检验 59 个已覆盖 FN 与 103 个纯背景 FP 的共同判别假设；可复用候选拟合/评分产物 | 不恢复无候选 GT；仍需处理 G1；新增特征可能无效 |
| T：阈值或时长再搜索 | 不改特征，仅追加解码工作点 | 实施成本低 | A1 已按 inner 选择三个阈值；59 个 FN 与 136 个 FP 同时存在，单向放宽阈值缺少正面证据；事后追加搜索违反 A1 停止决定 |
| P：先扩充 proposal set | 新候选接口、adapter、重复候选竞争 | 有机会覆盖 21 个无候选 GT | 历史冻结 union 约为 A 候选数 6.66 倍，仍只有 4/5 folds 过 G1；可能进一步加重 FP；因果变量更多 |

V 只改变事件表达。现有 A1 16D 特征包括候选已选中窗口的分数汇总、时长、密度、coverage 和 day phase；它不描述**候选内未选中的窗口**以及候选前后的分数轨迹。该缺口是可检验假设，不是已证明的根因。P 保留为独立的后续架构问题，不能因 V 的结果自动启动。

## 4. 数据流与接口

```text
A1 approved cache + 105 candidate-role score files + role graph
  -> hash、identity、participant/record/session/component 对齐 audit
  -> A1 冻结候选与 16D 特征
  -> 同一 score role、同一 observed-window-support component 的上下文提取
  -> a2_event_context_v1 26D 事件特征
  -> 原 HGB verifier 配置、原 nested role graph
  -> 原 inner threshold 集 {0.10, 0.25, 0.50}
  -> 原 duration/fusion 和 participant-safe strict-IoU evaluator
```

输入只取 [A1 产物](../../../artifacts/a1-end-to-end-feasibility-v1-005/)和它已批准的 cache/ledger。`window-identity.json` 只有身份，没有时间；时间必须由经 hash 校验的批准 cache 中 `starts/ends` 取得，禁止由文件名、GT 或预测结果补造。每个候选用自己的 `role_id` 关联同角色 candidate score 文件；`relative = raw - 该角色的 fit-participant threshold reference`，不能跨模型搬用绝对阈值。重复、缺失、冲突的 stable window ID 或 candidate ID 一律使 audit 失败。

对每个候选，先按 A1 的 `build_support_components` 恢复相同 participant、record、session 的组件并核对 `component_id`。只允许同组件窗口进入上下文；`source_segment_id` 仍为 null，不能把推断组件冒充真实 source segment。候选 interval、support、顺序、标签及所有 A1 分数文件均只读、不回写。

## 5. `a2_event_context_v1` 的十个新增特征

以窗口半开区间的中点 `floor((start_ms + end_ms)/2)` 决定区域。设候选为 `[s,e)`：inside 为 `[s,e)`；pre 为 `[s-300000,s)`；post 为 `[e,e+300000)`。每个区域仅接纳**同一组件**且该角色实际有 relative score 的窗口，按 `(start_ms,end_ms,row_index)` 排序。`positive` 定义为 relative score ≥ 0，与 GT 标签无关。已有 16D 特征按原顺序原值保留，以下十维依次追加：

| 序号 | 特征 | 精确定义 |
|---:|---|---|
| 17 | `inside_mean_relative` | inside 全部窗口 relative score 算术平均 |
| 18 | `inside_p25_relative` | inside 全部窗口 relative score 的线性插值第 25 百分位 |
| 19 | `inside_positive_fraction` | inside 中 positive 窗口数 / inside 窗口数 |
| 20 | `inside_longest_positive_run_fraction` | inside 按时间排序、相邻窗口区间相交时连续的最长 positive run 窗口数 / inside 窗口数 |
| 21 | `pre_mean_relative` | pre 窗口 relative score 均值；无窗口为 0 |
| 22 | `pre_positive_fraction` | pre 中 positive 比例；无窗口为 0 |
| 23 | `pre_observed_fraction` | `min(pre窗口数/40, 1)`；记录边缘/组件边缘缺失由此显式表达 |
| 24 | `post_mean_relative` | post 窗口 relative score 均值；无窗口为 0 |
| 25 | `post_positive_fraction` | post 中 positive 比例；无窗口为 0 |
| 26 | `post_observed_fraction` | `min(post窗口数/40, 1)` |

inside 必须至少有一个窗口，否则候选/score 关联无效并停止；所有特征必须为有限数。`40` 是 300 s / 7.5 s 的冻结参考窗口数，不用 GT 或当前 participant 统计估计。post-context 意味离线输出最多等待候选结束后 300 s；本设计不声称满足实时报警延迟。若未来出现实时要求，应另立设计，不静默删掉 post 特征。

## 6. 隔离、复用与验证协议

1. 在任何 fit 前，audit 重新验证 A1 `final-checksums.json`、配置/代码身份、105 个 candidate score 文件、`event-candidates.jsonl`、批准 cache hash、role graph 与 41/234 人口。验证 candidate role 的 fit/reference/scored participant 集合和 A1 原有 outer/inner/subinner 隔离；不得仅凭文件名认定可复用。
2. 从 A1 产物按 role 流式生成 26D 候选表。所有 role 的 candidate ID、interval、label、outer-valid 成员和候选数与 A1 精确一致。特征抽取函数不接收 GT；GT 只进入训练标签审计与事后评价。
3. 保留 A1 的 5 outer / 4 inner / 4 subinner role graph、HGB verifier 全部显式参数和 `seed=20260910`。只为新 26D 特征拟合 verifier：上限 25 个逻辑 verifier role；**候选模型 fit 上限为 0**。旧 16D verifier 不复用为新 schema 模型。
4. 每个 inner 只在其合法训练参与者的 OOF 候选上拟合 verifier；三个阈值只用 inner-valid 预测选择，按原 A1 的 pooled F1、较少 FP、较高阈值顺序打破平局。outer-valid 不参与任何 fit、reference 或配置选择；每折 outer 只评估一次。
5. 运行前冻结新配置及 SHA-256、输入/代码/hash 清单、角色拟合签名和资源上限。报告同一候选下 A1 与 A2 的 fold/participant TP、FP、FN、F1、long FP、boundary MAE、candidate coverage，以及 81 个 A1 FN 的阶段转移；后者只是解释，不能反过来调规则。

测试应覆盖：候选和原16D逐字节/逐值不变、同组件上下文、边缘缺失、相邻窗口 run 定义、score 身份错配、hash 篡改、outer GT 扰动不改变选择、participant 隔离、无 GT 的 6C7 仍参与背景 FP、完整 synthetic runner。只有 audit/test 通过才考虑真实 fit。

## 7. 资源与停止决定

拟议单次研究上限：0 candidate fits、最多 25 verifier fits、完整运行 wall ≤ 2 h、其中 fit wall ≤ 1 h、线程 ≤ 4、额外研究产物 ≤ 1 GiB；host RSS ≤ `min(8 GiB, 启动可用内存的 60%)`。这些是**下一阶段待冻结的预算提案**，不是现有 A1 剩余额度的自动授权。任何中断不得换目录重置预算；无可核验 checkpoint 时保持 fail-closed。

完整合法结果只有同时满足第 2 节的 pooled、fold、long-FP 和 MAE 最低门槛，才记 `A2_DEVELOPMENT_MINIMUM=PASS`；0.80 理想门槛单独记录。若未达标，关闭此 26D 变体，不追加上下文宽度、特征、阈值、duration、seed 或 classifier 搜索。资源或 provenance 失败只记 `INCOMPLETE/INVALID`，不能作性能负结论。

即使 A2 达到 0.66，固定候选的 Formal G1 状态仍为 FAIL，full training 和 production 不会自动放行；需要另立 candidate-interface 决定。所有 41 个 participant 已用于开发诊断，本阶段五折仍是开发证据，缺少独立 participant confirmation cohort；不通过重分已有 participant 或读取 official test 建立虚假确认。

```text
A1_TESTED_PROTOCOL = CLOSED
A2_DESIGN = DRAFT_FOR_REVIEW
A2_EXECUTION_AUTHORIZATION = NOT_GRANTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
