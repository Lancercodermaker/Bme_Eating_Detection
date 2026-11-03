# 路线 2：新对话执行 Prompt

用途：执行候选区间/输出集合的证据与设计准备。已经审核的是该准备阶段的入口与边界；不是已经批准训练或真实数据实验的计划。完整复制下面文本即可。

~~~text
接续 A2-004 关闭后的路线 2：候选区间与输出集合。使用工作树：
E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next

所有本地读取命令显式指定这个workdir或使用精确绝对LiteralPath。不得为定位文件搜索E:/bme_compitition根目录或递归搜索数据目录；相对路径不存在时先检查命令workdir，不以全盘/根目录搜索补救。

先完整阅读，过长分段，不只读摘要：
1. docs/decisions/2026-09-26-official-annotation-contract-review.md
2. docs/evidence/2026-09-26-a2-004-postclosure-evidence-review.md
3. docs/handoffs/2026-09-26-route2-interval-output-set.md
4. docs/decisions/2026-09-26-route-handoff-review.md
5. docs/decisions/2026-09-22-a1-end-to-end-feasibility-result.md
6. docs/decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md
7. docs/decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md
8. docs/decisions/2026-09-20-a1-end-to-end-feasibility-authorization.md
9. docs/decisions/2026-09-19-formal-g1-local-experimentation-stop.md
10. docs/data-contract-validation-2026-09-17.md
11. docs/superpowers/specs/2026-09-20-a-end-to-end-feasibility-design-review.md

已决定：接受仅以核验后的官方标注要求为开发目标；不再把无法取得独立行为记录作为这一benchmark目标的前置门禁。官方正文确认strict IoU>0.25、event F1及matched起止MAE；one-to-one算法、scope、eligible、完整输入/输出接口、未来上下文与运行资源仍未知。本地41人/234GT及greedy one-to-one只能标为本地开发协议。离线任务不预设实时，也不假定无限未来或跨record联合输入。

冻结：A1 CLOSED；Formal G1 FAIL；full training BLOCKED；production UNCHANGED；A2固定26D CLOSED_STAGE_MINIMUM_FAIL。004合法COMPLETE但四项numeric/stage均FAIL；不复活001/002/003、不重试004、不启动005。全部41人参与过开发，重新划分不能称独立确认。

本对话执行的是证据复核与可审设计准备。我授权新增本路线所需的审查、设计、待授权验证说明与审核文档；不修改旧文档、代码、配置、历史产物或production，不清理输出，不训练、不调用模型predict/predict_proba、不反序列化模型、不运行audit/run或任何新实验（含改阈值生成新候选、重解码与反事实性能试验）。文档不能自行扩大授权。

读取白名单：上述文档及共享证据文档§1明确登记的A1/A2保存产物、标签/representability文件；派生缓存仅批准cache-manifest的精确cache_path，保存分数仅score-provenance精确注册路径，A2物化候选仅role-digests精确注册路径。只核对保存事实、身份与简单几何，不重新执行科学流程。禁止读取、遍历、stat或重哈希raw sensor、原始metadata CSV、actual official test及external data；manifest中的path字符串不是读取授权。

缓存成员只限此前批准的窗口时间区间、身份和质量成员；登记分数只限ids/raw/relative。cache_path不是文件内全部数组授权，feature/label或未明确成员不自行加载。文件/字段缺失只报告，不搜索根目录、父目录或邻接产物。区分保留窗口时间覆盖、GT存在可匹配候选、一对一可实现匹配上限；213/234不等于已证明可同时获得213TP。

可复用路线1已审官方/队友来源结论。如确需回看，仅这两个精确PDF有例外读取权限：
E:/bme_compitition/official_test_dataset/Data/01_dataset/03_papers/赛题二-进食检测_V1.1 (1).pdf
C:/Users/Fancy/Documents/xwechat_files/wxid_j17l6d344xmo22_9a97/msg/file/2026-09/作品报告_基于智能手表传感器的进食检测算法.pdf
不得遍历其父目录或读取邻接文件。公开参考只用NormanAC/Eating-Detaction提交b134aba6c8cae82abc43da66014122f99ab4c20c与quarkes1/BMEcontest-2提交2a53cf8abbf7d280e8cd563c25fd545bad3f7cc0的源代码/文档静态参考，不下载数据、不执行或安装仓库。不得继承其eligible、≥.25 matcher、全局GT先验或未严格隔离的内层特征。

立即完成：
1. 定向复核并保存21 FN多因素表、79长FP区间来源表、11个分离竞争案例表，每项附文件/字段位置，区分已证、相关和NOT_SAVED。保持58段行为UNKNOWN。复核3个短GT与180s约束的数学冲突，不能删除/重标GT或改IoU。
2. 列推理输入边界表。component不是物理source segment；9对跨record/session竞争不能默认允许联合处理。GT竞争关系不能作为推理组；NMS没有解决非交叠11对的直接机制。
3. 根据证据选一个主要机制，明确是改候选区间还是在固定分数上作不消费GT的输出集合选择；学习ranking/集合目标交路线3。给出具体输入/输出、合法组/边界、缺口和空值语义、标签与角色隔离、支持/反证、无法解释的错误。相同候选selector不能恢复21 FN；子区间切分不能把58个零交叠FP变成TP。
4. 为这个机制写待授权的最小可证伪验证说明：单一科学差异、固定其余变量、比较对象、调用/角色计数、资源估算缺口、numeric/stage及停止条件、开发过拟合风险。不要编造实测成本或把A2额度当新授权；不复活已关闭bounded proposal/outer个案搜索。
5. 由独立审查者审核事实、推理GT泄漏、输入权限、归因与Prompt；修正重要问题。新增文件使用本对话实际日期，建议分别放docs/evidence、docs/superpowers/specs、docs/decisions，清楚标NOT_EXPERIMENT_AUTHORIZED，保留这组已审核交接文件不覆盖。

停止判定使用同一GT分母下的F1、既有逐折门槛和预注册约束，不能简单比较删FP数与丢TP数。matched MAE同时报告匹配GT集合变化，不借删除难例声称边界更准。

缺少轨迹或接口时，完成不依赖它们的证据和条件设计，列“需要哪项新证据、为什么会改变选择”，不猜测、不扩读、不修复、不重跑。交付后给出是否值得进入一个具体验证的判断和完整待批准方案；若真实执行仍需要新授权，说明当前限制来自以上任务边界。完成本阶段后结束，不自动进入训练、路线3或production。路线3需显式接收本阶段真实产出，不能假定已经通过。
~~~
