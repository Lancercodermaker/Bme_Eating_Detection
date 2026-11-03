# 路线 1 与路线 2/3 交接文档审核记录

日期：2026-09-26  
结果：最终六份内容文档的证据/设计准备阶段审核通过；未决 P0/P1 为零。  
流程状态：有已披露的文件定位范围偏差，不能记为无保留的流程合规 PASS。  
实验状态：NOT_EXPERIMENT_AUTHORIZED；不是 experiment ready。

## 1. 审核对象与权限

用户要求先完成路线 1，编写并审核路线 2/3 相关文档及新对话 Prompt。本轮新增七份文档，包括本审核记录；没有修改历史文档、代码、配置、产物、账本或 production，没有执行模型、训练、新实验、audit/run、测试、安装、提交或发布。

审核的六份内容文档：

- [路线 1 合约核验](2026-09-26-official-annotation-contract-review.md)。
- [A2-004 关闭后证据审查](../evidence/2026-09-26-a2-004-postclosure-evidence-review.md)。
- [路线 2 交接设计](../handoffs/2026-09-26-route2-interval-output-set.md)。
- [路线 3 交接设计](../handoffs/2026-09-26-route3-event-model.md)。
- [路线 2 Prompt](../handoffs/2026-09-26-route2-resume-prompt.md)。
- [路线 3 Prompt](../handoffs/2026-09-26-route3-resume-prompt.md)。

模型执行、扩读数据、独立确认或官方测试的授权没有从文档审核产生。下一对话 Prompt 执行的是证据复核与具体设计准备；真实验证仍需完整、具体、可审方案及明确新授权。

## 2. 实际审核与证据

| 审查者 | 实际工作 | 结论范围 |
|---|---|---|
| 主代理 | 核对来源地位、官方 PDF 三页原文、全套文档、Prompt、冻结状态及最终文档结构 | 确认正文支持 strict IoU >0.25、事件 F1、匹配起止 MAE；不能确认完整 matcher、eligible 或接口 |
| teammate_pdf 子代理（前序资料审查） | 直接读取唯一授权官方 PDF 三页并核对队友报告既有阅读结论 | 官方正文无 one-to-one 措辞；非惯用手 PPG 与场景针对性要求不能忽略；不是对完整官方附件的审查 |
| fn_review 子代理 | 直接读取本轮证据文档；与其前序 21 FN 只读核验对照并核算表内汇总 | 21 行数值/空格身份、4140/580/17、覆盖5/12/4、全负4、短GT3一致；本轮未重做模型/账本审查 |
| route_challenge 子代理 | 完整读六份草稿，提出重要问题；修订后再次直接读取精确工作树文件复核 | 最终准备阶段通过，未决P0/P1无；不授予实验准入，且要求披露§5流程偏差 |

官方/队友资料、公开仓库是合约或机制参考，不作为同协议性能对照。A2 的 COMPLETE 与合法性来自先前已核验保存产物，本轮不以文档审核替代真实 audit。

## 3. 已修正问题

| 问题 | 最终修正 |
|---|---|
| 缓存质量字段名称误写 | 使用实际 crosses_gap=false |
| “无合法候选/无候选”可能误读为完全没有候选 | 统一为“无可匹配候选”，明确14个有保存交叠候选但best IoU不达门槛 |
| 路线3职责可能漂移到序列/新边界生成 | 当前仅fixed-candidate keep/drop或合法set/ranking；生成路线范围外，边界需求交路线2 |
| cache_path可能被理解为全部数组授权 | 只限此前批准geometry/identity/quality成员和登记ids/raw/relative；未明确成员不自行加载 |
| 路线2固定分数筛选与学习集合目标混写 | R2-C固定分数、GT-free集合选择；学习目标归R3-B，配平相同组与选择规则 |
| 停止条件可能简单比较删FP和丢TP | 使用同分母F1、既有逐折门槛与预注册约束，不以计数差替代 |
| 213/234可能误读为同时可实现213TP | 区分时间支持覆盖、可匹配候选覆盖、一对一可实现上限；未新增oracle计算 |
| matched MAE可能受匹配集合筛选影响 | 要求同时报告匹配GT新增/丢失，不据MAE降低独断边界改进 |
| “可部署过滤”超出未知官方I/O | 改为“推理可计算过滤” |
| 官方交付篇幅遗漏 | 补充2/8/12页规则，队友13页PDF不能自动作为合规模板 |
| 定位命令错误工作目录 | 两个Prompt要求显式workdir或精确绝对LiteralPath，禁止根目录/父目录/邻接搜索补救 |

## 4. 最终版本与结构核查

下面只对本轮新增六份文档做 SHA-256 绑定，未重哈希 sensor、metadata、official test 或历史实验产物。这些哈希绑定独立审查者最后一次读取后的内容版本；本审核记录本身不作自指哈希。

| 文档（相对工作树） | SHA-256 |
|---|---|
| docs/decisions/2026-09-26-official-annotation-contract-review.md | 11aa97a469309f7bdaf554b090ee977d6c3d012732b69945d2e5caa3cc358e3c |
| docs/evidence/2026-09-26-a2-004-postclosure-evidence-review.md | 9c255fc5711a51b1a8c94471f52cf5bf241a6bac3b252c6391b475e688317bf5 |
| docs/handoffs/2026-09-26-route2-interval-output-set.md | e9b1de707257c88e8c2c6d50fbc683475ac145d5137be262df7b32acaf558c69 |
| docs/handoffs/2026-09-26-route3-event-model.md | 2aa6d12b2ff3e632e1d8fbc6e0f1ef9b72aa293d591af293fff8035f651e823a |
| docs/handoffs/2026-09-26-route2-resume-prompt.md | 47f5bdd73bfa42d96ac64a2c7b71ee0e1c12adadacc72592126a153063d0b394 |
| docs/handoffs/2026-09-26-route3-resume-prompt.md | e7e8b8caf3274acfa465756c0a8acf815b6ec4ab93c21d87d02ac92f93b811f0 |

主代理用标准库逐个读取上述精确文件，核对UTF-8、内部docs链接、Prompt围栏、歧义术语与最终版本。最后一次完整结构核查覆盖本记录在内的7份文档、6份版本绑定，缺失链接/围栏/版本错误为0，退出码0。未搜索数据目录；对PDF/产物/manifest中的原始路径不做链接目标stat。结构核查不是科学测试或新实验，不能据此声称新方案性能/资源门禁通过。

## 5. 已披露的定位范围偏差

route_challenge 首轮定位时使用了错误工作目录 E:/bme_compitition，而不是指定 worktree。它先按六个相对docs路径读取，文件不存在；随后执行一次 rg --files --hidden，附六个本轮精确文件名的 -g 过滤，输出为空、exit=1。

这些文件名过滤只限制返回结果，没有限定目录或明确排除 raw/metadata/official_test。该命令可能枚举了项目根目录下不允许遍历的目录，现有输出不能排除这一点，不能宣称本轮从未越界遍历。未返回或读取任何匹配文件内容，也没有运行模型或实验。没有进一步探查命令究竟经过哪些数据目录，以免再次扩大访问。

主代理已向用户说明，停止这类搜索并改为精确工作树绝对LiteralPath。之后的子代理复核和主代理结构核查均限定已列文件。根代理早期任务转述没有重新写明绝对工作目录，应承担定位边界说明不够精确的责任；改进已写入两个新对话Prompt。此次偏差不改写A1/A2已有指标，但使本轮流程不能获得无保留合规PASS。

## 6. 未决事项与交接结论

未决P0/P1文档问题：无。仍未取得的科学/运行证据：

- 官方精确matcher、scope、eligibility、时间轴及接口附件。
- 全记录、未来上下文、跨record联合推断许可和官方CPU/RAM/超时限制。
- 候选300秒融合前的完整保存轨迹及其因果证据。
- 可用于推理的非交叠候选竞争分组、事件信息增量和新方案资源测量。
- 非惯用手场景/PPG的已授权派生输入与针对性方案实现证据。
- 独立新participant/官方反馈；58段独立同期行为记录仍未取得，行为UNKNOWN。

路线1的现有资料审查与用户标注目标决定已完成；不是完整官方可执行合约已确认。路线2、3可以在新对话执行各自证据/设计准备。推荐先路线2，再让路线3读取其实际产出；若没有产出，路线3只做不依赖它的信息增量核验与条件设计。

A1 CLOSED；Formal G1 FAIL；full training BLOCKED；production UNCHANGED；A2固定26D CLOSED_STAGE_MINIMUM_FAIL全部保持。没有A2-005、新实验、自动重试、模型家族全盘否定或独立泛化确认。
