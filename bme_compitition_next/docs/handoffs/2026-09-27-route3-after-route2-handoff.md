# 路线三接续：已接收路线二准备结果

日期：2026-09-27  
状态：ROUTE2_PREPARATION_RECEIVED / ROUTE3_HANDOFF_PREPARED / NOT_EXPERIMENT_AUTHORIZED。  
工作树：E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next。

本文件更新路线三的依赖与新对话入口，不启动路线二验证或路线三研究。9 月 26 日已审核文档及本轮接收的路线二文件均保留原样；新的入口为[接续 Prompt](2026-09-27-route3-after-route2-resume-prompt.md)，审核见[接续审核记录](../decisions/2026-09-27-route3-after-route2-handoff-review.md)。

## 1. 已接收并完整阅读的路线二产出

| 文件 | 接收到什么 | 不代表什么 |
|---|---|---|
| [证据表](../evidence/2026-09-27-route2-evidence-tables.md) | 21 FN、79 长 FP、11 组分离竞争的定位与分层 | 不是新候选或新性能结果 |
| [候选区间验证设计](../superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md) | 固定保存分数，只改变候选间隙融合的待验证假设 | 不证明 300 秒规则是原因，也不表示 gap=0 已执行 |
| [独立审阅决定](../decisions/2026-09-27-route2-design-review.md) | Stage A 无 GT 门、七字段/分阶段 GT 提案的修订及复审限制 | 审阅没有重算全部 79 条 lineage 或 11 组 IoU/匹配归属 |
| [待授权验证 Prompt](2026-09-27-route2-candidate-interval-validation-authorization-prompt.md) | 需要另外批准的输入、科学定义、调用、资源与执行范围 | 文件自身不授候选生成、模型、代码、GT 或预算权限 |

本次接收只读了上述文档及 9 月 26 日路线三入口，没有读取科学产物或数据、重新核验完整 lineage、生成候选、运行模型、重解码或 audit/run。路线二文件记录的产物核对仍按其实际来源和审阅限制表述，不能升级为本轮独立性能确认。

## 2. 当前科学状态与合约

用户已接受仅以核验后的官方标注要求为开发目标；独立行为记录缺失不阻断此 benchmark 目标，58 个零注释交叠长 FP 的行为仍 UNKNOWN。官方正文明确 strict IoU >0.25、事件 F1、匹配起始/结束 MAE；精确 matching、scope、eligible、完整接口、未来上下文与资源限制仍未核验。

本地参考仍为 41 人/234 canonical eligible GT、participant-global greedy one-to-one。全部 41 人已参与开发，重新划分不能产生独立确认。A1 CLOSED；Formal G1 FAIL；full training BLOCKED；production UNCHANGED；固定 26D A2 CLOSED_STAGE_MINIMUM_FAIL；不创建 A2-005、不复活任何已关闭编号。

A2-004 的合法保存结果仍是 TP/FP/FN=154/106/80、F1=0.623482、long FP=79/106。现有 4,183 个 outer 候选覆盖 213/234 个 GT，是“至少有一个可匹配候选”的计数，不等于能同时实现 213 个一对一 TP。

## 3. 路线二的 Stage A/B 都未执行

| 阶段 | 拟议操作与门槛 | 当前状态及解释 |
|---|---|---|
| Stage A | 每个预声明 role 对同一分数分别应用 300 秒参考规则与唯一处理规则，比较区间多重集；完全不读 GT、匹配或目标 FP 名单 | 待授权；105 个配对 role batch 包含 210 次 role-rule 应用，不是已执行的 105 次总生成调用 |
| 处理规则 | 同 participant/record/session/observed-support component；positive 为 relative ≥0，半开区间仅在 next.start_ms < current_end_ms 时合并，端点相接也断开 | “gap=0”只是简称，不能改写成允许端点相接的 gap≤0，也不证明物理连续 |
| Stage A 停止 | 105 个 role 的参考/处理 interval 多重集全相同则不进入 verifier fit | 差异存在仅证明候选几何变了，不证明 F1、覆盖、long FP 或最终 decoder 输出改善 |
| Stage B | 105 个处理候选批次重建同 schema 特征/训练标签，再按原 nested 图拟合与评价 | 没有处理候选产物；新 16D 来源、label 语义、26D 重算与新资源账本尚未批准 |
| GT 提案 | 精确 eligibility 文件中七字段，分训练标签与冻结预测后的评价阶段 | 这是路线二未来提案，不是当前路线三读 GT 的授权；inner 阈值评价资格与 join 时点尚需明确 |
| 模型与成本 | 提案有 25 verifier attempts、25 held-out prediction batches、65 decoder calls | 全为待批准计数；不是 A2 剩余额度，不是路线三预算，也没有新实测成本 |

未来 Stage A 的参考规则重建也须计入调用、wall、RAM、disk 和账本。不能只记 105 个处理批次而遗漏参考生成。若未来处理候选被批准，原候选的 16D、标签或 verifier 分数不能直接复制给新边界。

## 4. 路线三现在可继续什么

推荐先做 R3-A：**基于现有冻结候选的有限顺序信息增量设计**。这是设计优先级，不是模型选择或实验授权。现有 16/26D 的均值、分位数、正窗比例、longest-run 等摘要是否遗漏与标注相关的顺序信息，需要先给出具体定义、非冗余理由和可证伪条件，不能以“加维度”或换家族为理由。

R3-B 的合法组内 ranking/set 作为条件备选。路线二已明确 11 对都不发生正长度交叠、9 对跨 record/session、2 对同 record/session 不同 component，且没有已核验的 GT-free 推理组。不能以这 11 个 GT 共享关系直接建推理组，也不能先设计跨 record selector 再假定官方输入允许。无合法组证据时建议暂缓这一目标变化。

两类职责都只对现有候选评分/选择，不能恢复当前 21 个无可匹配候选 FN。它们不需要等待 gap=0 实验即可开展书面设计；但不能宣称已恢复候选缺口。新边界或直接事件生成仍在本次路线三范围外。

如果以后考虑在 gap=0 候选上做路线三，先接收**实际合法运行产物、角色/schema/来源审核与对照一致性记录**，另定候选版本及归因设计。不要直接把路线二提案当作路线三默认候选接口，也不要同时改候选、表示、学习目标和 decoder。

## 5. 不能继承的绝对效果断言

- 覆盖 <50% 不足以证明 strict IoU >0.25 必不可达；不得把“低覆盖 FN 不保证恢复”写成“低覆盖 FN 必不能恢复”。保留输入不足的证据，但实际可匹配性仍取决于区间几何、score 和输出约束。
- relative=0 按提案属于 positive；“零分”不能替代“GT 交叠窗口 relative 全负”。只复用四个全负案例的精确已保存状态，不外推模型家族无效。
- 58 个零注释交叠候选的纯子区间不能产生 TP；这不等于其 FP 数量不可能下降。若新规则使片段被过滤或选择删除，FP 仍可能变化；是否值得以 TP 代价换取 FP 减少需完整同分母 F1 和 gate 判断，本轮不计算这一反事实。
- Stage A 有几何差异不等于 300 秒规则被证明是错误原因；无标签门通过也不授训练权限。
- 保持 final minimum=180 秒仍保留三个短 GT 的数学冲突；路线三 fixed-candidate scorer 不能解决此限制。不得删 GT 或改变官方 IoU。

## 6. 本次接续及下一对话的读取边界

**本次接续实际只读精确列出的文档，写必要的新文档。**下一对话默认先据文档完成设计；这不撤销用户此前明确授予的精确路径/成员的保存事实只读权限。确需定向复核时，在先前已批准的相同文件、相同成员和相同只读用途内可以继续，不重复请求授权。不得从旧入口的泛称、manifest路径或路线二七字段实验提案推定新增权限，不能自动加载 source_16d/label、整包缓存或未明确成员。

既有权限的定位以共享证据文档§1及路线二证据表的精确登记来源为依据：只核对已经保存的身份、区间、support、来源和质量/分数事实，不生成新feature、候选或新性能结果；科学产物成员不明确时保留缺口。先前GT账本只读审查权限不等于允许GT控制未来实验门槛、推理或配置选择。路线二七字段/阶段提案仍不能自行授予路线三监督、评价或实验权限。

不读取、遍历、stat 或重哈希 raw sensor、原始 metadata CSV、actual official test、external data。当前接续无须重读官方 PDF 或仓库；既有审查结论可从路线一文档引用。所有命令明确 workdir 或精确绝对 LiteralPath，不搜索项目根目录、父目录或邻接产物。

若需要此前未批准的产物或成员，先交付“哪个精确文件/成员、用于哪项证据、为什么文档不足、能改变什么决定”的补充清单，等待明确扩读授权；不停止其他不依赖它的准备工作。原始数据及官方 test 不作为默认补证手段。

## 7. 下一对话交付与停止条件

1. 明确职责和候选版本：默认现有冻结 A1/A2 候选，不假定 gap=0 运行。
2. 一个信息增量或目标增量表，列既有列、未来来源候选、推理可得性、时间/身份/缺失边界、容量、支持与反证；无增量可交付暂缓结论。
3. label-free 推理接口、训练监督/inner selection/outer evaluation 角色隔离图；候选标签资格和评价资格不自行假定相等。GT 只在未来获准的监督/评价角色使用，不做推理分组、mask 或边界。
4. 一项具体低容量方案及待授权最小可证伪验证；单一科学差异、配平对照、同候选/decoder/matcher、同分母 F1、逐折 gate、long FP、matched GT 集合及起止 MAE。若选 ranking，固定相同推理组和选择规则，只改学习目标。
5. 角色/调用图、资源估算缺口、预算和不可重试条件，全部标拟议；不照搬路线二25次、不填假实测值、不预承诺0.66。
6. 独立审核与精确待授权说明。身份/来源不足、GT-free组不成立、信息冗余或成本无法约束时停止进入模型验证；继续交付已能证明的设计结论。

以上交付可以在新对话完成，当前只是准备好入口。真实 candidate/feature 生成、fit/predict、重解码、audit/run 和性能试验仍需另行具体授权。路线三准备完成也不解锁 Formal G1、full training 或 production。

## 8. 接收时发现的文档级待澄清事项

不改写路线二已审核文件，记录供其未来实施决定处理：

- Stage A 的105配对批次/210 role-rule应用与后续105处理批次须分别计账；当前文案局部只列处理重建数，不能继承为总预算。
- 原 nested inner 阈值选择需要 held-out inner 的 GT 评价；须明确其资格集合、字段访问时点及冻结要求，不能因“outer 预测冻结后读 evaluation_eligibility”就推定 inner 语义已完整。
- 21 FN 表共有21数据行且头/数据9列，Markdown分隔行8列；这是呈现问题，行数核对不等于表格列格式通过，不改变已保存科学计数。

这些项不把路线二已完成的准备阶段改称实验失败，也不否定其标签隔离修订；它们说明实施授权尚未完成。
