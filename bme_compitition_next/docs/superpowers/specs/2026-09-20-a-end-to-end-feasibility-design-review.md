# A 端到端可行性：设计审查草案

> **2026-09-20 批准附记（优先于下文的审查时状态）：** 用户明确回复“选择A1，D1-5批准”。A1 及 D1–D5 的批准、操作性细化与权限边界见[新阶段授权决定](../../decisions/2026-09-20-a1-end-to-end-feasibility-authorization.md)，后续步骤见[实施计划](../plans/2026-09-20-a1-end-to-end-feasibility-implementation.md)。以下正文保留批准前的审查快照；其中“待批准”“NOT_GRANTED”等不再描述当前设计授权状态。批准没有使缺失证据变为已验证，也没有解除旧 G1/full-training 阻断。

日期：2026-09-20  
状态：DRAFT_FOR_DESIGN_REVIEW / NOT_EXECUTION_READY  
工作目录：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`  
范围：需求归档、只读源码审查结论、新研究阶段的设计与投入提案。不是实现计划或实验授权。

## 1. 权限、文档层级与当前状态

用户已确认：最低最终 pooled event F1 为 0.66，理想为 0.80 或更高；主指标由 participant-disjoint 完整 pipeline 的 held-out 预测产生，并另行评价 fold/participant 稳定性；设计顺序先审查 A 的合法下游，再考虑 union 的增量成本。

用户没有授权本阶段训练、推断、实验、修复源码、重开已停止规则搜索或修改 production。本文件中的新配置、数值预算和准入路径均是待审提案。阅读或批准设计方向不自动构成执行授权。

```text
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED

NEW_STUDY_DESIGN = DRAFT_FOR_DESIGN_REVIEW
NEW_STUDY_EXECUTION_AUTHORIZATION = NOT_GRANTED
NEW_MODEL_FITS_THIS_REVIEW = 0
NEW_INFERENCE_THIS_REVIEW = 0
```

文档层级：

1. [09-10 历史设计](2026-09-10-high-f1-event-stack-design.md)为历史背景。
2. [09-14 detailed design](2026-09-14-high-f1-event-stack-detailed-design.md)仍是冻结架构，[implementation plan](../plans/2026-09-14-high-f1-event-stack-implementation.md)仍是原执行路线。
3. [09-19 可行性决定](../../decisions/2026-09-19-candidate-architecture-feasibility-decision.md)与[局部实验停止记录](../../decisions/2026-09-19-formal-g1-local-experimentation-stop.md)规定当前停止状态；后者限制前者对架构不可行性的宽泛表述。
4. 本草案不替换以上文档。未来任何允许 G1 FAIL 下开展有限端到端研究的例外，必须由新决定精确授权，不能称为旧 Task 6+、M5/G4 或 M6 恢复。

数据人口的时序也必须显式区分：09-15 的 267-event / 246-event 文档是历史阶段；[09-17 数据契约记录](../../data-contract-validation-2026-09-17.md)说明最终 v3 为 234 label-eligible events；09-19 决定继续冻结 234 cohort。本草案不恢复旧分母。

## 2. 决策问题与 Preflight

| 字段 | 内容 |
|---|---|
| Goal | 判断是否值得建立可信的 A 端到端开发评估路径，以评价最终 F1≥0.66，并了解向 0.80 提升的空间 |
| Success metrics | 用户确认 pooled event F1≥0.66 为最低目标，≥0.80 为理想目标；具体稳定性验收仍待审 |
| Constraints | target-only、41 eligible participants、234-event cohort、15s/7.5s、111D、strict IoU>0.25、participant 隔离、raw 只读、test/external 不进入本阶段 |
| Prior art | 本地已冻结设计、历史诊断与本轮源码审查；没有新增外部文献有效性主张 |
| Baseline | A candidate coverage 207/234；不是完整端到端 F1 baseline。历史 M0=0.17284 和小 split F1=0.7273 均保留其原适用范围 |
| Candidate approaches | 固定单配置 A；有限 inner verifier-threshold selection 的 A；union 对照暂不纳入第一阶段 |
| Critical assumptions | score/model provenance 可恢复；合法 OOF 能构造；边界元数据足够；16D 下游具备识别能力 |
| Risks | 现有 runner 不符合冻结下游契约；source segment 信息缺失；重复使用开发 folds；短事件与 duration 约束冲突；可复用模型数量不等于新拟合预算为零 |
| Validation experiments | 本轮不执行。仅提出未来单种 A 路线的有限端到端开发评估，见第 7–10 节 |
| Kill criteria | 协议或来源无法证明则停止；预算不足则不启动；性能失败关闭被测配置/协议，不自动宣判所有架构无效，不自动进入 union |
| Recommendation | REDESIGN |
| Confidence | 对现有下游不宜直接执行的判断高；对 0.66/0.80 是否可达未知 |

```text
workflow_path: RESEARCH
execution_mode: REVIEW_ONLY
execution_backend: primary-agent drafting + collaboration.spawn_agent read-only review
capability_tags: machine-learning, data-contracts, evaluation-protocol
loaded_profiles: Machine Learning
scope: one draft document; no source/config/artifact mutation
budget: two bounded read-only review tasks; zero model fits/inference/experiments
fallback: record unresolved evidence and remain NOT_EXECUTION_READY
validation_order: source/lineage -> boundary/metric contract -> design review -> separately authorized implementation/validation
telemetry: no formal ML run; this document is a design record, not run_start/gate_result evidence
```

## 3. 证据分类

| 类别 | 已知内容及限制 |
|---|---|
| A 文档明确事实 | 旧 G1 与 full training 阻断；新业务目标由用户确认；旧 G4 的 0.19284 数值线不能代表新最低项目价值 |
| B 当前代码行为 | OOF fallback、共享绝对 threshold、事件身份丢失、全局重匹配、G3 不完整等；见第 4 节 |
| C 历史实验结果 | A=207/234；union=217/234、4/5 folds 达标、候选规模约6.66倍；没有新增端到端结果 |
| D 缺失证据 | 完整下游性能、独立确认、source segment sidecar、全部模型与运行环境复用证明、资源测量、官方 matching 细节的独立核验 |
| E 推断/提案 | 先完善合法 A 路径可能比先开发 union adapter 更有信息价值；不能据此保证最终 F1 |

用户提供的 source audit 表明 41 eligible participants 全部已用于开发；HNU21018/HNU21042、AC3 和无餐的 6C7 不能组成独立事件确认 cohort。6C7 仍应进入背景误报评价。FD-I/FD-II 不满足当前 confirmation 条件，也不进入本阶段。

即使未来协议严格 participant-disjoint，结果仍是反复使用开发数据后的评估，不能称为独立确认、官方 hidden-test 成绩或已证明的部署性能。更换 seed、重分 folds 或按 session 划新 holdout 均不恢复独立 participant confirmation。

## 4. 当前实现与冻结要求的差距

源码观察基于工作树 `HEAD=b43268d0cb31c3a759f1a7439748f5e9b2681273` 加既有未提交文件；HEAD 本身不能唯一标识本轮观察的源码。未来执行需记录所消费文件的 SHA-256。

| 项目 | 当前行为 | 新路径必须满足的契约 |
|---|---|---|
| OOF | `candidates.py::participant_oof_candidate_scores` 捕获 ValueError 后可拟合 all-participant fallback；runner 只打印后继续 | 不可用显式记录；fallback=0；任何不合法 score 不进入 verifier |
| Score scale | full-train model 分布产生一个 threshold，并用于其他 OOF models；features 使用 raw score | 每个 model 的 threshold 仅来自自身 fit participants；raw/threshold/relative score 均有来源 |
| Event identity | `verifier.EventCandidate` 缺 participant/session/segment/quality 身份 | 明确绑定 record/session/source segment，边界在有效范围内 |
| Gap/session | 窗口生成检查 gap，但事件聚类仅按时间；runner 在 participant 内合并全部 session interval | 候选生成和 decoder fusion 只在同一合法 record/session/segment 内执行 |
| G3 | 只检查存在 0/1 两类 | 每个 verifier fit 至少20个正候选、来自至少5个participant；独立GT数量另报，不把重复候选当独立事件 |
| Evaluation | 汇总全部 participant intervals 后重新匹配 | participant 内合法匹配后汇总整数 TP/FP/FN；禁止跨 participant 配对 |
| Missing MAE | 无 matches 时写0.0 | 写null并报告matched_count；不能表示为完美边界 |
| Nested orchestration | runner一次split；evaluation.py仅有fold构造 | 完整选择/OOF/refit/outer推断边界显式实现，或明确采用无选择的固定配置协议 |

源码位置：`src/eating_event/candidates.py:170`、`scripts/run_event_verifier.py:319`、`:331`、`:381`、`:496`、`:520`、`src/eating_event/verifier.py:19`、`:30`、`:165`、`src/eating_event/metrics.py:106`。

本表不是对历史 G1 runner 的泄漏判决；不同执行路径必须分别审计。本轮未运行任何代码来测量这些问题对历史数值的影响。

## 5. 历史 A 与新路径的身份

本文件用两个名称防止混用：

- `A_legacy`：既有 score lineage、候选规则和历史产物。207/234只属于该记录，不重算、不覆盖。
- `A_contract_safe`：待设计的新端到端研究路径，保留 A scorer 家族、输入特征与目标数据范围，同时补齐 OOF、边界和评价契约。

这两个名称仅是设计标识，当前没有创建第二套模型或产物。

如果加入 source-segment 限制改变了候选区间、relative-score 改变了 verifier features，或 decoder/匹配修正改变了输出，不能称为“历史 A 完全不变、只加了 verifier”。未来需报告这些差异和新版本身份，不强迫新路径复现207/234，否则会把旧实现缺口变成验收要求。

只读检查确认 event-balanced probe 的五个 A outer folds 历史 selected quantile 均为0.90。下文将固定 q=0.90作为新设计建议，明确它来自已有开发历史，不伪称独立选择。若不接受该固定值，应另行设计更深层的candidate选择流程，不能临时改回当前fold的outer-derived选择。

## 6. 身份、边界与指标契约

### 6.1 Input / score / candidate

必须保存：participant_id、record_id、session_id、stable_window_id、source_segment_id及bounds、feature/schema hash、fit_participants、selection_participants、threshold_reference_participants、fold/layer、model hash、raw_score、threshold_reference、relative_score和quality provenance。`OOF=true`单个标记不足以证明隔离。

对要输出为OOF训练分数或held-out验证分数的participant集合H、模型训练集合F，要求F与H不相交。允许模型在自身F上评分，仅用于计算该模型的threshold reference；这些in-sample分数不得冒充OOF verifier训练分数。在outer k中，outer-valid V_k不得出现在任何模型的fit、threshold reference或配置选择集合中；只在冻结后的最终推断与评价中出现。

`threshold_reference = quantile(scores_on_F, q)`，只能用该模型的fit participants分数；`relative_score = raw_score - threshold_reference`。候选support按relative_score≥0选取。数值threshold不能跨model搬用。

reference总体建议延续历史A的实际语义：使用F内全部已批准record cache的合格dense-window rows，包括POSITIVE、NEGATIVE与IGNORE，不按标签或GT邻域抽样；每个stable_window_id恰好一次，重复ID报错。不同record的合法窗口仍是不同ID，不按时间相同自行合并。训练loss仍只使用0/1标签；用于reference评分不等于用于loss。各窗口等权，采用线性插值quantile规则，保存reference row-set hash、count、q和数值threshold；空集合或非有限分数fail-closed，不回退到其他模型threshold。这是新路径待批准的完整定义，不能仅凭q=0.90声称threshold兼容。

现有16维结构可作为起点，但score列改用relative score必须升级schema，不能继续标成完全等价的原feature contract。没有批准增加新特征。GT只用于训练标签和事后评价，不得决定推断时的候选生成、边界或保留/删除。

原计划Task 8将label_uncertain/ignore与inference-quality过滤混写，存在需要澄清的边界：训练标签ignore可使样本不进入loss，但不能根据outer-valid GT给候选打ignore后从预测中删除。推断过滤只能消费预先冻结、推理时可获得的sensor/quality契约。任何评价区域mask也必须是运行前明确批准的协议，不能按模型错误事后设置。

### 6.2 Source segment 不足时的停止行为

WindowRecord和当前cache只保留`crosses_hard_gap`等窗口字段，没有完整source segment id/bounds。窗口通过gap检查，不表示两窗口之间可任意融合。`diagnostic_bounded_proposal`从窗口连续性推导的segment也不自动等价于source segment。

先查是否存在与缓存身份一致的已审计segment sidecar；找不到时，该前提为未满足。本轮artifact文件名检索未发现明确的segment/timebase/gap sidecar，只发现通用audit/cache manifests；这不是对所有文件内容不存在该信息的穷尽证明。不能自动读取raw补建，不能把未知gap当作无gap。未来若采用“仅在连续合格窗口覆盖内聚合”的保守替代，需要单独批准新语义并记录它可能拆分历史A候选；它不是无变化复用。

### 6.3 GT、session 与匹配

既有ledger中存在一个GT与多个session重叠；`events_for_record`返回完整原事件，而不是每session裁剪片段。因此禁止简单逐session重复建立truth denominator。

建议以批准ledger中的canonical event_id建立每participant唯一GT集合，保持234个eligible事件。预测保持session/record/segment身份，生成与融合不能跨界；最终在同一participant中，对唯一GT集合执行一次一对一匹配。GT不按session复制、裁剪或按预测挑选归属。预测间完全重复的去重若需要，必须用预先冻结且不读取GT的规则；不能在评价器中挑选最有利的record。

匹配阶段如需额外限制session关联，应先证明不改变canonical GT归属与分母，再形成显式修订；本草案不静默加入该限制。

当前本地matching是strict IoU>0.25、按IoU降序的deterministic greedy one-to-one。保留为待验证的本地reference，不能声称本轮独立核验了官方实现；也不擅自替换成maximum-cardinality matching。一个GT有任意可匹配候选的coverage，与一对一TP数量分开报告。

每个participant得到TP/FP/FN后再相加：

```text
pooled_F1 = 2 * sum(TP) / (2 * sum(TP) + sum(FP) + sum(FN))
```

无GT participant仍贡献其FP；recall标为不适用。无GT且无预测时participant F1标为不适用，不任意给1以提高macro；无GT但有预测时报告F1=0和FP。macro_event_bearing只对有GT的人计算，并同时输出全participant原始counts。

边界MAE用全部匹配误差与matched_count聚合，无匹配为null。FP/hour仅在有可信监测时长时计算：先按participant合并已批准的有效监测时间区间，不能把重叠窗口或重叠record时长重复求和；分母不可用时报告null与原因。若只有accepted-window support时长，只能作为另名辅助指标，不能冒充全部有效监测时长。

long-FP的分子使用同一次participant-global matching中的未匹配prediction IDs，pooled fraction为总long FP/总FP；不能重新运行身份丢失的全局matcher或平均participant比率。建议沿用当前long定义duration≥600s，FP=0时fraction=0并报告FP_count=0。long-FP与boundary约束不自动取消，其运行前验收口径需在审批表中明确。

### 6.4 Duration / fusion

原设计180s是初始decoder配置，不是官方指标要求。当前实现先过滤短候选，再merge。若最终所有预测至少180s，则duration≤45s的GT不可能满足strict IoU>0.25。

新设计建议第一阶段暂固定candidate fuse=300s、decode fuse=600s、min duration=180s，并在同一合法segment内沿用“verifier threshold -> duration filter -> fusion”的顺序。这是在限制变量，不是宣称该配置最优。短GT仍保留在234分母中，并报告结构性受限情况。需要修改duration或顺序时必须在运行前修订设计，不能因outer结果不佳才扩大搜索。

## 7. 两种可行性协议与建议

以下均未获准执行，且不是原M5/G4。

| 方案 | 配置选择 | 优点 | 结果解释限制 |
|---|---|---|---|
| A0 固定单配置 | candidate q=0.90、verifier threshold=0.50，其他参数固定 | 成本最低，可以检验一个明确完整系统 | 失败只否定该配置，不能据此认定A下游不可学；阈值可能不合适 |
| A1 有限inner选择（建议） | q=0.90固定；仅verifier threshold∈{0.10,0.25,0.50}由inner选择 | 用原计划已有有限阈值集检验下游，避免只测一个任意工作点 | 需要更内层candidate OOF，成本更高；单seed开发结果不是正式稳定性通过 |

共同固定建议：A candidate家族和111D输入；candidate/verifier max_iter=100；HGB verifier使用冻结设计配置与positive_weight=3；event feature维度16但relative-score语义另定schema；上节duration/fusion；seed=20260910；同一既有五个outer folds。不扫描weight、stride、feature、classifier或proposal规则。

A1完整数据流，对每个outer k：

1. T_k为outer-train，V_k为outer-valid；在T_k内部建立4个inner folds。
2. 对inner i，U_ki为inner-train、W_ki为inner-valid。只在U_ki内部再建立4个OOF folds，生成U_ki的候选训练分数，各模型的fit/reference均只来自对应U_ki子集。
3. 只用U_ki的OOF候选拟合一个verifier，满足G3。用U_ki refit的candidate scorer对W_ki评分；用这个inner verifier预测W_ki candidates。
4. 对同一批inner验证分数评价三个冻结threshold，不为threshold重新拟合模型。每个inner评分参与该outer内的选择，不参与其他outer配置选择。
5. 合并T_k中每个participant恰好一次inner-valid预测的counts，选最高pooled inner F1；并列先较少FP，再较高threshold。只选这一个数值，不调整其他参数。
6. 用T_k内4个inner candidate models构造完整T_k OOF候选，拟合最终outer verifier。candidate scorer用完整T_k训练的模型；对V_k应用选定配置一次。
7. 五个outer各自产生配置记录；不先跨outer汇总一个全局配置再回评这五个outer。所有outer指标只进入报告。

任何OOF不可用、G3失败或契约不完整均停止对应协议，不用all-participant模型、不换seed、不减少fold、不静默删除participant。G3按每次fit分别计算，不能使用全数据计数代替。

A0没有步骤2–5的verifier-threshold selection，只需T_k内部OOF构造final verifier；其较低成本与较弱结论必须一起保留。

## 8. 模型复用与拟合预算

已有A manifest记录65个模型路径：5 outer、60 inner。每个outer/inner角色的三个q模型在manifest中SHA-256相同，即20个inner训练角色；q影响threshold而不进入scorer fitting。这里核对的是manifest，不是重新加载全部模型或验证全部文件字节。

五份保存的outer OOF scores不能直接拼成另一outer的verifier训练集，因为其模型可包含当前outer-valid participants。20个inner模型仅可能服务它所属outer的合法训练/验证角色；不提供inner-train内部的更深层OOF。

模型复用必须同时核验fit participant、feature/label/cache hash、hyperparameters、seed、code/environment与threshold来源；缺失项不能用“loadable=true”替代。相同quantile文件不能被当成三份独立证据。

以下是单seed、singleton candidate/verifier训练配置下、尚未跨角色去重的逻辑训练角色预算，不是严格最小拟合次数、计时、性能承诺或拟合授权。设outer F=5，inner I=4，inner-train内部OOF J=4：

| 方案 | candidate训练角色数 | verifier训练角色数 | 完全合法复用现有25个candidate角色后 |
|---|---:|---:|---|
| A0 | F(1+I)=25 | F=5 | 可能0个新candidate fit + 5个verifier fit，仍有新推断 |
| A1 | F(1+I+IJ)=105 | F(1+I)=25 | 可能80个新candidate fit + 25个verifier fit，仍有新推断 |

三个verifier thresholds只增加decode/evaluation，不将fit数乘3。候选quantile若重新搜索、训练配置若改变、增加seed或加入union，均超出以上预算，必须重新计数。

实际新拟合次数=所需角色按完整fit signature去重后的数量减合法已有实例数量。只有fit participants、训练数据/schema/标签/权重、超参数、seed与环境契约均一致时才允许共享；不按相似文件名去重。若更内层角色恰有相同训练集合，实际拟合数可能更少。

实际复用失败不自动批准重新训练。建议把上表未去重角色数量作为冷启动拟合次数上界提案；wall-time、host RSS、disk预算尚无本阶段实测依据，见审批表。沿用旧host memory约60%约束作为资源设计输入，不把它当作已通过的本阶段资源审计。不调用M6 runner，不生成最终提交模型。

## 9. 成功、失败与证据等级

用户已确认主目标；以下稳定性与阶段判定仍是提案：

本阶段0.66/0.80的适用人口是冻结的234-event evaluation-eligible cohort及其全部批准监测背景，不等同281个原始annotations或官方test分母；47个已排除事件及理由继续保留在provenance，不通过新增排除改善指标。

- `MINIMUM_DEVELOPMENT_TARGET_MET`：完整合法五折pooled F1≥0.66。
- `IDEAL_DEVELOPMENT_TARGET_MET`：完整合法五折pooled F1≥0.80。
- 建议附加多数fold条件：至少3/5 folds F1≥0.66；该数字未被单独批准，不写成已冻结要求。
- 每fold P/R/F1、participant counts与分布、无餐FP、long-FP、matched boundary MAE、coverage、candidate规模和资源均必须报告。
- 单seed结果不代表原M5三seed稳定性通过；理想数值线达标不自动代表全部安全/稳定性约束通过。
- G4历史baseline+0.02不再承担新项目成功标准，但不修改历史G4定义。

停止与结果解释：

| 情况 | 结果/行动 |
|---|---|
| 数据身份、OOF、边界、分母或metric契约失败 | INVALID，不作模型可行性结论；本次有限协议停止 |
| G3不满足 | VERIFIER_DATA_INSUFFICIENT；不减少样本门槛或引入fallback |
| 资源预算超出/未完整五折 | INCOMPLETE_RESOURCE；不能称为完整性能负结果 |
| 完整合法结果F1<0.66 | 被测A协议未达到最低目标；不自动否定全部A配置或所有架构，不自动尝试union |
| 完整合法结果≥0.66但未到0.80 | 达到最低开发数值目标；是否追加投入取决于稳定性、成本和错误结构 |
| 完整合法结果≥0.80 | 达到理想开发数值目标；独立确认仍缺失，正式G1/M5/M6不自动放行 |

不能在看过outer误差后追加threshold点、改duration、cap或边界。outer结果只触发新的设计/停止决定。任何oracle分析只可说明所定义候选/decoder约束下的机会，不得当作可部署F1；只有证明是完整可实现输出集合的有效上界，才可用来排除目标，否则不能提前宣布不可达。

## 10. Union 的延后条件

union不在第一阶段A1的配置空间、拟合预算或自动后续动作中。当前已有两个独立问题：

1. 冻结spec写highest-score/earliest-index peak，但`diagnostic_bounded_proposal.py:154`的`max(..., key=(-score,index))`实际选择lowest-score/latest-index；该代码hash与spec记录一致，report所用spec hash也一致。
2. 15s peak和部分短interval无法通过当前180s duration filter；恢复coverage不等于增加最终可输出TP。

保留历史217/234和停止结论；本文件不修复、不重跑，也不宣称修复能提升覆盖。未来若讨论union，必须先选择历史实际实现还是按文字spec修订后的新版本，不能混用身份。

adapter只接收冻结interval和合法score/quality来源，不能改边界或产生新候选。必须区分proposal interval、source support indices和context范围；不能把相同16维数量当作语义兼容。完全相同interval合并后的source provenance、同一GT多正候选权重、重复候选竞争规则均另行设计。

只有在A的结果与接口成本说明额外对照有区分价值时才提出union专项决定；A失败不是自动启动union的理由。

## 11. 执行就绪前必须关闭的决定

这是一份审查草案，不存在隐藏默认值或可直接运行的命令。下列未决项使它保持NOT_EXECUTION_READY：

| 决定 | 本草案建议 | 仍需什么 |
|---|---|---|
| D1 新阶段权限 | 与旧G1停止状态并存的有限A端到端开发研究；非正式M5/G4 | 精确的新决定与实施范围；当前没有该授权 |
| D2 协议/配置 | A1；q固定0.90，仅三个verifier thresholds inner选择；其余上述固定项 | 批准此研究问题和配置范围，接受开发暴露与短事件限制 |
| D3 source segment与GT身份 | 复用可信sidecar；canonical GT每participant一次 | 证明所需sidecar存在或批准恢复/保守替代路径；目前不能宣称cache足够 |
| D4 资源/复用 | 按A1最多105 candidate +25 verifier训练角色核算，优先合法复用 | 审计复用清单；批准wall-time/RSS/disk及新fit上限，不能借用proposal-only 20s作为估算 |
| D5 验收 | pooled0.66/0.80已确认；多数fold、long-FP、boundary口径待审 | 确定稳定性/输出质量的硬门槛与报告项，不事后挑选 |

设计完成不等于实验准备完成。本草案不附运行命令，不创建实验config，不更改旧decision或其hash，不提交production修改。批准全部设计项后仍需形成范围明确的实施/验证方案；测试与实验必须分别授权到相应阶段。

## 12. 审查与交付记录

- 本轮仅新增本设计草案；旧文档、source、config和artifacts保留。
- 采用主代理编写和两个只读独立子任务审查：participant数据流/拟合预算、边界/指标契约。
- 审查重点为隔离、分母、复用边界与结论范围；不是实验复现、测试通过或官方指标认证。
- 本文无需通过运行模型来完成审查；所有未来性能与资源数值均保持未知。
- 两项独立源码审查均已返回。草案复审中，数据流审查者指出OOF隔离与fit-reference评分的措辞冲突，已修正并补齐reference总体定义；后续子代理复审受到用量限制，未宣称完整独立文档复审通过。最终文字一致性检查由主代理完成。
- 文档核验：6个相对文档链接均可解析，代码围栏配对，无占位符标记或UTF-8替换字符；不将这些文档检查写成pipeline测试通过。本文件保留为未提交草案，尚未形成冻结spec/hash。
