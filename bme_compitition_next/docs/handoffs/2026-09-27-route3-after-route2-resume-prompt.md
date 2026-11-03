# 路线三新对话 Prompt：接收路线二实际准备结果

日期：2026-09-27  
用途：替代 9 月 26 日入口，启动路线三的文档审查与具体设计准备。不是训练或实验 Prompt。完整复制下文。

~~~text
接续路线三：在已接收路线二准备结果后，完成低容量事件评分模型的可审设计，不执行模型或新实验。

工作树：E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next
所有命令显式指定该 workdir 或精确绝对 LiteralPath。不为找文件搜索 E:/bme_compitition 根目录、父目录、数据目录或邻接产物；相对路径缺失先检查 workdir。

完整阅读，过长分段：
1. docs/handoffs/2026-09-27-route3-after-route2-handoff.md
2. docs/decisions/2026-09-27-route3-after-route2-handoff-review.md
3. docs/evidence/2026-09-27-route2-evidence-tables.md
4. docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md
5. docs/decisions/2026-09-27-route2-design-review.md
6. docs/handoffs/2026-09-27-route2-candidate-interval-validation-authorization-prompt.md
7. docs/decisions/2026-09-26-official-annotation-contract-review.md
8. docs/evidence/2026-09-26-a2-004-postclosure-evidence-review.md
9. docs/handoffs/2026-09-26-route3-event-model.md（以本次接续的依赖/读取边界为准）
10. docs/decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md
11. docs/superpowers/specs/2026-09-22-a2-context-verifier-redesign.md（正式决定优先）
12. docs/superpowers/specs/2026-09-20-a-end-to-end-feasibility-design-review.md
13. docs/decisions/2026-09-22-a1-end-to-end-feasibility-result.md
14. docs/decisions/2026-09-20-a1-end-to-end-feasibility-authorization.md
15. docs/decisions/2026-09-19-formal-g1-local-experimentation-stop.md
16. docs/data-contract-validation-2026-09-17.md

当前事实：路线二已完成21 FN/79长FP/11分离竞争的证据、一个候选区间验证设计及独立审阅。Stage A/B均未执行，gap=0候选/新16D/新26D/新性能均未产生。Stage A提案对105 role各作300秒参考与正时长交叠处理两种生成，比interval多重集，完全不读GT/matches/目标FP。105配对批次是210 role-rule应用，不能仅计105次总调用；存在差异只证明几何变了。路线二25 fits与七字段GT只是待批提案，不属于本对话权限。

冻结：A1 CLOSED；Formal G1 FAIL；full training BLOCKED；production UNCHANGED；固定26D A2 CLOSED_STAGE_MINIMUM_FAIL，不创建005、不重试旧编号。A2-004合法结果F1=.623482、long FP=79/106；全部41人参与开发。官方strict IoU>0.25、event F1与matched起止MAE已核验，exact matcher/scope/eligible、官方接口/未来上下文/资源未知。本地41人/234 GT仍是本地协议，离线目标不假定实时，也不等于无限未来可用。

用户已接受仅以标注合约为开发目标。58段行为UNKNOWN不阻断此目标，不能称行为非进食已确认。HGB家族没有因固定26D失败被否定；不继承队友116D、±20分钟或更复杂模型必然更好的判断。

本对话授权的是文档审查与设计准备，默认先读上述精确文档，新增必要的审查、spec、待授权说明和审核文档。保留已有审核文件不覆盖，不修改代码、配置、历史产物、账本或production；不清理、不训练、不反序列化/调用模型、不做candidate/feature生成、候选计数预演、重解码、audit/run或任何新实验。不要从泛称白名单、七字段实验提案、manifest或待授权Prompt推定新增数据或实验权限。

用户此前明确批准的精确文件/成员、用于保存事实复核的只读权限仍有效，确有必要时定向读取同路径/同成员，不重复请求；精确来源定位见共享证据§1和路线二证据表。只核对已保存身份、区间、support、来源及获准质量/分数，不自动加载source_16d/label、整个cache或未明确数组，不生成新feature或性能结果。既有GT账本审查权限不等于GT可控制未来实验、推理或配置。raw sensor、原metadata、actual official test与external仍禁止读取/遍历/stat/重哈希；无需重读PDF/仓库，可引用路线一结论。此前未批准的新文件/成员才先列精确补充清单并等待扩读授权，继续其他不依赖它的工作。

立即完成：
1. 默认在现有冻结A1/A2候选上选择fixed-candidate keep/drop职责，优先审查一个有限顺序信息增量；不读取实际向量也能先据既有16/26D定义说明信息是否冗余。不把gap=0提案当新候选输入。固定候选scorer不能恢复21个无可匹配候选FN，新边界/直接事件生成不在本次设计范围。
2. 写一个信息增量表：逻辑定义、已有列、未来精确来源候选、推理可得性、time/record/session/component边界、未来依赖、缺失语义、容量、机制支持/反证与最小可证伪条件。实证未取得就写UNVERIFIED，不声称已辨识进食信号；若无增量，交付暂缓模型投入结论。
3. set/ranking只作条件备选；先证明无GT的推理组来源。11对都非交叠，9对跨record/session、2对同record/session不同component，GT共享不是组定义。无合法组证据则暂缓，不能默认跨record、跨缺口或NMS可解决这些病例。
4. 写label-free推理接口、训练标签join、完整角色隔离图，以及inner held-out阈值评价和outer最终评价各自GT资格/访问时点。不假定training_eligibility=evaluation_eligibility，不默认七字段已解决所有角色语义；当前只设计，不实际读GT。
5. 提出一项具体低容量设计和待授权最小验证：单一科学差异、配平对照、同候选/decoder/matcher、TP/FP/FN/F1、long FP、matched GT增失与起止MAE、numeric/stage、本地逐折门槛与停止条件。ranking比较固定相同推理组与选择规则，只变学习目标。给调用/角色图及资源估算缺口，不照搬路线二25次、不编造实测成本、不预承诺.66、不进行family sweep。
6. 明确41人反复开发风险；nested隔离、重划、bootstrap或新seed不产生独立确认。过滤收益看同分母F1及gate，不能简单比较删FP数/丢TP数。保留窗口时间覆盖、存在可匹配候选、可同时一对一匹配上限是不同量。
7. 独立审阅事实、输入权限、GT-free推理、信息增量、对照归因与Prompt，修正重要问题。新增文件用本对话实际日期，标NOT_EXPERIMENT_AUTHORIZED；交付精确方案或暂缓结论、最少新增证据和待授权范围，然后结束准备阶段，不自动训练或回头执行路线二。

不要继承“低覆盖FN必不能恢复”“relative零分就是全负”“58段切分不能变TP所以FP不能下降”等过强断言。三个短GT与180s限制仍保留，不删GT、不改官方IoU。若将来改用gap=0候选，须先接收实际合法产物/来源审核/对照一致性结果，再另行定候选版本和归因，不能同时改候选、表示、目标和decoder。

发现资料不存在/矛盾只记录，不搜索扩大来源、不修复科学产物、不重跑。完成已授权的设计，使下一步真实验证成为具体可审提案；当前NOT_EXPERIMENT_AUTHORIZED不变。
~~~
