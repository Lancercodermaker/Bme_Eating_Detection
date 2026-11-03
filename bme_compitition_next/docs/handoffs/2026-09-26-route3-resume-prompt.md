# 路线 3：新对话执行 Prompt

用途：执行低容量事件模型的信息/目标增量核验与设计准备。真实模型执行尚需具体设计、资源和新的明确授权。完整复制下面文本即可；路线 2 的实际产出若已存在，在新对话中追加其精确文档路径。

~~~text
接续 A2-004 关闭后的路线 3：低容量事件评分/集合模型设计。使用工作树：
E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next

所有本地读取命令显式指定这个workdir或使用精确绝对LiteralPath。不得为定位文件搜索E:/bme_compitition根目录或递归搜索数据目录；相对路径不存在时先检查命令workdir，不以全盘/根目录搜索补救。

先完整阅读，过长分段，不只读摘要：
1. docs/decisions/2026-09-26-official-annotation-contract-review.md
2. docs/evidence/2026-09-26-a2-004-postclosure-evidence-review.md
3. docs/handoffs/2026-09-26-route2-interval-output-set.md
4. docs/handoffs/2026-09-26-route3-event-model.md
5. docs/decisions/2026-09-26-route-handoff-review.md
6. docs/decisions/2026-09-22-a1-end-to-end-feasibility-result.md
7. docs/decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md
8. docs/decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md
9. docs/decisions/2026-09-20-a1-end-to-end-feasibility-authorization.md
10. docs/decisions/2026-09-19-formal-g1-local-experimentation-stop.md
11. docs/data-contract-validation-2026-09-17.md
12. docs/superpowers/specs/2026-09-20-a-end-to-end-feasibility-design-review.md
13. docs/superpowers/specs/2026-09-22-a2-context-verifier-redesign.md（正式决定优先于草案）
如我在本对话提供路线2实际产出的精确文档路径，再完整阅读它们；未提供时写明未接收，完成不依赖它们的信息增量审查，不搜索未授权产物或假定路线2成功。

已决定：仅以核验后的官方标注要求为开发目标；58段无注释交叠长FP仍行为UNKNOWN，独立行为证据缺失不阻断该benchmark目标。官方strict IoU>0.25、event F1、matched起止MAE已确认；exact matcher/scope/eligible、官方接口、可用未来上下文和资源未知。本地41人/234GT的参考结果不能称官方等价。离线定位不按实时架构设计，也不假定无限未来可读。

冻结：A1 CLOSED；Formal G1 FAIL；full training BLOCKED；production UNCHANGED；A2固定26D CLOSED_STAGE_MINIMUM_FAIL。004合法COMPLETE、F1=.623482、long FP=79/106、21个GT无可匹配候选；不复活或重试A2，不启动005。HGB整个家族没有被否定。全部41人参与过开发，nested隔离不能清除历史路线选择的过拟合，重划不能称独立确认。

本对话执行的是信息/目标增量核验与可审设计准备。我授权新增本路线所需的审查、设计、待授权验证说明与审核文档；不修改旧文档、代码、配置、历史产物或production，不清理输出，不训练、不调用模型predict/predict_proba、不反序列化模型、不运行audit/run或任何新实验（含新特征性能试验、改阈值生成候选、重解码）。文档不能自行扩大授权。

读取白名单：上述文档及共享证据文档§1明确登记的A1/A2保存产物、标签/representability文件；派生缓存只按已批准cache-manifest精确cache_path，保存分数只按score-provenance精确路径，物化候选只按role-digests精确路径。定向核对身份、几何/质量与保存分数，不默认加载所有feature数组或未注册PPG派生文件。禁止读取、遍历、stat或重哈希raw sensor、原始metadata CSV、actual official test与external data。manifest路径字符串不是授权。

缓存成员只限此前批准的窗口时间区间、身份和质量成员；登记分数只限ids/raw/relative。cache_path不是文件内全部数组授权，feature/label或未明确成员不自行加载。文件/字段缺失只报告，不搜索根目录、父目录或邻接产物。区分保留窗口时间覆盖、GT存在可匹配候选、一对一可实现匹配上限；213/234不等于已证明可同时获得213TP。

可复用路线1已审外部来源。如确需回看，仅两个精确PDF为例外：
E:/bme_compitition/official_test_dataset/Data/01_dataset/03_papers/赛题二-进食检测_V1.1 (1).pdf
C:/Users/Fancy/Documents/xwechat_files/wxid_j17l6d344xmo22_9a97/msg/file/2026-09/作品报告_基于智能手表传感器的进食检测算法.pdf
不遍历父目录。公开参考仅NormanAC/Eating-Detaction提交b134aba6c8cae82abc43da66014122f99ab4c20c与quarkes1/BMEcontest-2提交2a53cf8abbf7d280e8cd563c25fd545bad3f7cc0的代码/文档，不下载数据、不安装/执行仓库。其153/276GT成绩、≥.25 matcher、全局先验和±20分钟未来信息不能自动继承。官方非惯用手需结合PPG及针对性算法；队友HRV分支失败不能证明所有PPG无效，本对话不扩大PPG/raw读取授权。

立即完成：
1. 本阶段模型职责只选固定候选keep/drop或合法组内set/ranking，提出其中一个可证伪机制。相同候选评分/集合模型不能恢复21 FN；新边界需求交路线2并记录依赖，直接时序/新边界生成路线不在本次设计授权内，不自动转入其设计。
2. 给出一个已有16/26D遗漏的信息，或一个独立候选分类与一对一集合目标之间的具体差异。列信息增量表：现有列、所需精确来源、部署可得性、time/record/session/component边界、未来依赖、缺失语义、容量。不以加维度/换家族本身为理由；证据不足可推荐暂缓。
3. 写label-free推理接口、训练标签/关系join、(role_id,candidate_id)身份和完整角色隔离图。GT关系只在训练折监督/诊断，不能给held-out推理分组、边界、mask或阈值。时间先验、上游分数和内层选择都在相应训练层隔离，不拼5个outer OOF当另一outer训练集。
4. 写单一机制的具体低容量设计及待授权最小验证说明：配平对照、冻结其余变量、TP/FP/FN与long FP/起止MAE、numeric/stage、角色/调用计数、预算和测量缺口、失败及停止条件、41人开发过拟合风险。R3-B对照固定相同推理组和选择规则，仅改变学习目标。不要编造fit预算、实测成本、预期F1或独立确认资格；不同时改候选、representation、loss和decoder，不启动family sweep或更大序列模型。
5. 独立审查事实、输入权限、GT泄漏、信息增量、资源可审性和Prompt，修正重要问题。新增文档用本对话实际日期，建议放docs/evidence、docs/superpowers/specs、docs/decisions，标NOT_EXPERIMENT_AUTHORIZED；保留已审核交接文件不覆盖。

停止判定使用同一GT分母下的F1、既有逐折门槛和预注册约束，不能简单比较删FP数与丢TP数。matched MAE同时报告匹配GT集合变化，不借删除难例声称边界更准。

发现文件不存在、身份矛盾、轨迹/接口缺失时，明确指出，不猜测、不修复、不扩读数据、不重跑。完成可做的准备，交付一项具体可审方案或“暂缓模型投入”的证据结论及会改变选择的最少新证据。若真实执行仍需新授权，说明限制来自以上任务边界。完成本阶段后结束，不自动训练、不解锁full training、不进入production。
~~~
