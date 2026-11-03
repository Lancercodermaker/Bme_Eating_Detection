# A1 有限端到端开发研究：批准记录

日期：2026-09-20  
状态：DESIGN_APPROVED / IMPLEMENTATION_PENDING / EXPERIMENT_NOT_STARTED

## 1. 批准来源与效力

用户原话：**“选择A1，D1-5批准”**。

对应[设计审查稿](../superpowers/specs/2026-09-20-a-end-to-end-feasibility-design-review.md)第 11 节 D1–D5。批准附记加入前，该文件 SHA-256 为：

```text
c982b897e19e0e77dc2b7de72b745d60c50bd5dec90f2d2b8f68bb043b2bbf54
```

这批准了 A1 的有限研究范围及其实施准备，不应再次要求用户重复批准 D1–D5。当前交付是批准归档与实施计划；尚无实现、测试或新实验结果。实际数据执行仍须先完成计划中的来源、边界、隔离、资源检查，不能把批准记录当成检查通过证明。

本决定只为 A1 建立新阶段例外；它与下列旧状态并存：

```text
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED

A1_DESIGN = APPROVED
A1_IMPLEMENTATION = PENDING
A1_EXECUTION_READINESS = NOT_YET_VERIFIED
A1_EXPERIMENT = NOT_STARTED
```

## 2. 文档冲突与覆盖范围

09-14 冻结设计与原计划以正式 G1 通过作为后续路线条件；本决定明确允许准备一条 G1 FAIL 下的有限开发研究路径。因此存在**门禁路径的显式例外**，而不是旧门禁已经通过。原 M5/G4、M6/full training 不恢复，09-19 两份决定及其历史结果不改写。

审查稿中的“尚未批准”与本次批准冲突，由本决定覆盖其当前权限状态；审查稿保留为批准前证据。新边界、relative-score 特征、身份安全的指标聚合与历史 runner 不等价，命名为 `A_contract_safe / A1`，不得直接继承历史 A=207/234。

本决定及[新计划](../superpowers/plans/2026-09-20-a1-end-to-end-feasibility-implementation.md)只管 A1。其余事项继续服从原文档层级；未明确覆盖的冲突应记录并停止相关步骤，不静默选择。

## 3. D1–D3：阶段、配置与边界

**D1：** 采用既有 41 eligible participants、234 个 canonical eligible GT、既有 5 outer folds。6C7 的背景 FP 必须计入。禁止新增排除、重新划分所谓独立 holdout、使用 external/test 或启动 union。新代码与产物独立命名，旧 runner 和历史产物不改写。

**D2：** 选择 A1：candidate q=0.90；仅 verifier threshold `{0.10, 0.25, 0.50}` 在各 outer 的 inner 验证内选择。5 outer × 4 inner；各 inner-train 内再做 4-fold candidate OOF。seed=20260910；candidate/verifier max_iter=100；positive_weight=3；111D 输入、16D relative-score event features；candidate fuse=300s、decoder fuse=600s、min duration=180s。HGB 其余参数沿用审查稿所指冻结配置，并在实现时显式写入配置，禁止依赖不同函数的不同默认值。

reference 是该 scorer 的 fit participants 全部合格缓存窗口（含 IGNORE），stable ID 去重检查、窗口等权、linear quantile；loss 仅用 0/1。OOF/held-out score 的 participant 不在对应 fit/reference 集合；in-sample reference 分数不流入 verifier OOF。阈值选择以 pooled inner F1、较少 FP、较高 threshold 依次打破并列。

**D3 操作性细化：** 采用已批准范围内的保守替代 `observed_window_support_component_v1`，不读取 raw 恢复 source segments。每个 record/session 内按窗口时间排序，重叠或相接窗口形成覆盖并集的连通区间；下一窗口 start 大于当前覆盖 end 即新建区间。仅在同一连通区间内生成候选和融合。所有窗口必须满足原缓存质量字段且 `crosses_hard_gap=false`，否则失败，不静默丢弃。

保存 `source_segment_id=null`、`boundary_kind=observed_window_support_component_v1`、component ID/bounds；不能把缺失 source identity 填成推断出的真实 segment。用 cache manifest 与 manifest audit 的 record/session identity 和 session bounds 关联验证，不 stat/open raw 路径。关联失败、session identity 空缺、越界或窗口 ID 重复均停止。空窗口 record 明确记录，不删除 participant。

该替代证明的是连续合格窗口支持，不证明原始完整 timebase segment；可能拆分历史 A 候选。canonical GT 按 participant 去重，保留 234；同一 GT 跨多个 session 也只计一次。预测生成不跨 record/session/component；匹配按 participant 对唯一 GT 执行一次。第一版不额外跨 record 去重预测；重叠 record 重复预测可能成为 FP，不能事后挑有利记录。

## 4. D4：有限投入与复用

逻辑角色上限为 **105 candidate + 25 verifier**，包括合法复用角色。实际新 fit 上限也不得超过这两个数；失败或中断的 fit attempt 计入，不能重置预算重试。25 个既有 candidate 角色若全部满足来源证明，可能只需 80 个新 candidate fits；这还不是已验证的节约。

以下数值是本次批准后的**保守实施上限**，不是用户逐项指定的数值，也不是历史运行测量：

| 项目 | 上限/规则 |
|---|---|
| 整个真实数据研究累计 wall time | 21,600s（6h），含审计、评分、fit 与报告；续跑继承已耗预算 |
| 来源与缓存预检 | 1,800s，包含在总额内 |
| 单次 fit | 7,200s，且受剩余总预算约束 |
| host 内存 | 本研究进程树合计 RSS ≤ min(8 GiB, 启动时可用内存的 60%)；启动时冻结数值 |
| 新研究磁盘产物 | 2 GiB，含临时文件，不含只读既有输入；先检查可用空间 |
| 并发 | CPU，最多一个 fit worker；每 worker 最多 4 compute threads；不使用 GPU |

无法可靠执行资源监测则不开始真实数据 fit。超限停止，报告 INCOMPLETE_RESOURCE，不自动扩容、减 fold、换 seed、删除 participant 或继续另一配置。有限预算可能不足以完成，不把 6h 写成完成承诺。计量应覆盖子进程，不能只看调度器内存。

复用必须核验模型字节 hash、fit participants、训练窗口/特征/标签、超参数、seed、训练代码及环境兼容性。文件可加载不构成复用证据。缺少复用证明可明确登记为“不复用”，仅在当前输入及完整 fit signature 已验证后按冷启动预算拟合；输入 hash 冲突或来源矛盾必须停止，不能通过重新训练掩盖问题。模型来自既有受信项目路径才可反序列化。

## 5. D5：数值目标、质量条件与解释

每 participant 的 strict IoU>0.25 deterministic greedy one-to-one counts 相加计算 pooled F1。本地 matching 规则固定，并保留“未独立核验官方实现”的限制。

| 判定 | 冻结条件 |
|---|---|
| 最低开发数值目标 | 完整合法五折 pooled F1 ≥ 0.66 |
| 理想开发数值目标 | 完整合法五折 pooled F1 ≥ 0.80 |
| 多数 fold 稳定性 | 至少 3/5 outer folds 的 F1 ≥ 0.66 |
| 输出质量 | 每个 outer fold 的 long-FP fraction ≤0.25，matched start MAE 与 end MAE 各≤900s |
| 最低阶段目标达成 | 最低数值目标、多数 fold、输出质量全部满足 |
| 理想阶段目标达成 | 理想数值目标、多数 fold、输出质量全部满足 |

long 定义为预测 duration≥600s；分子来自同一次匹配的 unmatched predictions。FP=0 时 fraction=0，另报 FP count。MAE 按 matched count 加权，无匹配为 null；null 不视为质量通过。逐 fold 硬门槛是批准后为避免平均掩盖坏 fold 而冻结的操作口径。

须分别报告数值达标与综合阶段达标，不能把 pooled≥0.66 单独写成整体通过。无 GT participant recall=NA；无 GT/无预测 F1=NA；无 GT/有预测 F1=0。短 GT 全部保留：min duration=180s 使 duration≤45s 的 GT 无法 strict-match，此项是结构限制而不是额外排除理由。

每次 verifier fit 仍要求至少 20 个正候选、来自至少 5 个 participant，且有两类；失败为 VERIFIER_DATA_INSUFFICIENT。报告独立正 GT 数量，不能把重复候选当独立事件。

数据/隔离/指标违规为 INVALID；资源中止为 INCOMPLETE_RESOURCE；只有完整合法五折才可评价该协议是否达到 0.66/0.80。outer 结果不反馈到本次配置选择。结果属于反复使用开发 cohort 后的评估，单 seed、缺独立 confirmation，不能宣称官方成绩、部署性能或原正式 G4 通过。

## 6. 下一步与证据记录

按新计划 INLINE 实现、先做合成契约验证，再做不拟合的来源/预算预检，满足就绪条件后才进入 A1 数据执行步骤。任何改变阈值集合、duration、特征、fold、seed、cohort、预算或引入 union 的动作均需显式修订；本次批准不包含自动搜索。

A 文档事实：用户选择与本决定；B 代码行为：仍是审查稿列出的旧实现，尚未修复；C 历史实验：仍是原记录；D 缺失证据：实现正确性、复用证明、资源可行性、新端到端性能及独立确认；E 推断：A1 的有限试验可能提供投入决策信息，不能保证 0.66/0.80。
