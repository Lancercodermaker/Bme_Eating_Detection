# 路线二候选区间验证：待批准 Prompt 草案

日期：2026-09-27  
状态：`DRAFT / NOT_EXPERIMENT_AUTHORIZED`  
工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`

> 本文件是供负责人审阅的验证提案，不自带执行授权。直接粘贴本Prompt也不构成训练、候选生成、模型调用或真实数据实验授权。只有负责人另行明确批准全部范围、字段和预算后，才能进入执行；缺一项就停在准备状态。

## 新对话讨论入口：先补齐路线二，再决定架构最小验证

用户已提出顺序偏好：若现有证据不足，优先准备并在前置条件和单独授权齐备后完成路线二受控验证，再依据证据决定三个架构方向各自是否值得做最小验证。当前只授权文档更新与继续讨论，不是立即执行路线二或全部后续模型的授权。候选几何方向的gap=0机制已包含在路线二中，不能换名再重复同一实验。

以下为可复制的下一轮**讨论**Prompt；其后的段落仍是待批准实验提案，不可直接执行：

```text
接续路线1/2/3整合后的架构讨论，优先补齐路线二候选区间验证的准入条件。本对话先讨论与修订已有文档，不启动实验。

工作树：E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next
所有命令显式使用该workdir；相对路径先解析为工作树内绝对路径，PowerShell读取用-LiteralPath。禁止根目录/父目录搜索、通配符枚举和目录遍历；缺文件直接报告精确路径，不扩大搜索。

完整阅读以下已有文件，不新增独立交接包：
1. docs/decisions/2026-09-26-official-annotation-contract-review.md
2. docs/evidence/2026-09-27-route2-evidence-tables.md
3. docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md
4. docs/decisions/2026-09-27-route2-design-review.md
5. docs/handoffs/2026-09-27-route2-candidate-interval-validation-authorization-prompt.md
6. docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md
过长文件分段完整阅读；本文件的新“讨论入口”和review最后的“本轮静态定义补充与准入复审”（保留其中的“整合后修订”历史事实）是最新说明，历史审批范围不能扩展为当前执行许可。

冻结事实：
- 路线1是官方资料审查，允许以核验后的标注合约作为开发目标；官方精确matcher/API、未来上下文、跨record输入与资源仍未知，非惯用手结合PPG要求未被IMU成绩代替。
- A2-004合法COMPLETE：TP/FP/FN=154/106/80，F1=0.623482；固定26D路线CLOSED_STAGE_MINIMUM_FAIL。
- Route3 v1-003合法COMPLETE：150/126/84，F1=0.5882352941，四门FAIL。它只关闭固定候选/26D下的matching-aware逐候选目标变体，不否定HGB或联合事件架构。v1-002仍INVALID且已耗25fits，Route3累计50fits，不重跑003，不创建004或A2-005。
- 路线二尚未执行，仍NOT_EXPERIMENT_AUTHORIZED；“完整执行”指获批协议达到其预定终态，若参考/输入/资源失败或机制无差异，应合法停止，不能强行耗完25fits。

先讨论并使方案具体可审阅：
1. 新候选16D公式现已在A1静态代码定位：来自同role保存relative、support窗coverage和新边界；仍需补精确派生cache/score/身份文件、成员、role绑定、固定10D实现及A1原标签调用链。冻结原A1/A2 candidate-label语义，不继承Route3标签或复制旧候选向量/标签/模型分数。
2. Stage A先保证300秒参考在全部105个role复现保存候选的区间及support身份多重集，随后比较唯一gap=0规则。旧300秒规则含等号；处理必须严格正时长相交，不能仅调用旧构建器并设gap=0。完整通过路径上限为105组配对=210次规则应用，复用参考结果，不额外重建；参考早停按实际消耗记账，处理调用数为0，不执行剩余role凑数。整个Stage A不读GT、资格标记、match或目标FP名单；重建候选是未来新实验，不是现在可偷跑的只读检查。
3. 分清训练标签的training_eligibility、全部inner held-out三阈值预测冻结后的evaluation_eligibility、outer预测冻结后的evaluation_eligibility；分别明确participant白名单、读取时点及消费者。现有A2 audit/run提前整份加载GT，不能原样用来证明分阶段读取；单JSON事后过滤不等于先限制可见数据。不能假定两种资格标记相同或提前全量物化outer GT。
4. 冻结参考复现标准、全部相同的早停、Stage B标签/来源/隔离/G3和资源门、独立新study/账本及具体数值预算。design §5已列待确认的数值硬停止线和Stage B入场式；它们是支出政策而非wall/RSS/disk预计成本，不继承A2/Route3额度。当前提案要求A+B一并准入：全部输入和两阶段上限均在首次重建前获批；实际数量只代入事先冻结的Stage B规则，资源不满足就停止，不能运行后补预算。若完整前提仍不可得，可以讨论是否另提Stage A-only，但须另行具体化、审阅与授权，不自行拆分执行。
5. 说明需要额外读取哪些精确输入/字段、为什么已有证据不足。若需扩大数据权限，等待明确批准；只有全部输入、语义、范围和预算具体化并经独立审阅后，才给单独实验授权请求。不得把本讨论Prompt当作批准。

若文档不足，可仅静态读取以下精确代码定义：src/eating_event/a1/events.py、src/eating_event/a1/pipeline.py、src/eating_event/a1/scoring.py、src/eating_event/a2/audit.py、src/eating_event/a2/execution.py。不运行其中函数、不扩大搜索；文件不存在即报告，不猜其他路径。本轮不加载cache数组、新16D/label成员或GT数据；它们的读取须列入后续精确授权。其余component、A1原标签调用及A2固定10D源码不在本轮静态白名单内，若需补证须另列精确路径与用途，不能顺手扩读。

根据路线二未来实际证据决定：候选几何/输出约束、低容量边界与联合事件输出、连续时序表示的信息增量。不是无条件把三个方向都跑一遍；无合法信息增量或运行时分组就不进入模型验证。gap=0和180秒最短输出是两个变量，不同时修改。

允许修订上述路线二design、review和已有authorization-prompt三个文档以形成可审核提案；保留历史事实并标明修订，不新建交接文件。不修改代码、配置、历史产物或production，不清理输出；不运行测试、训练、predict/predict_proba、候选生成、解码、matcher/evaluator、audit/run或新实验。
不读取/遍历/stat/重哈希raw sensor、原metadata CSV、official test或external data，尤其E:/bme_compitition/official_test_dataset；manifest路径不授权扩读。不重读官方/队友PDF或远程仓库。

41人均已开发暴露，没有独立participant确认；58个原A2零注释交叠长FP行为仍UNKNOWN。A1 CLOSED、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。
先给证据支撑的建议、尚缺条件与取舍，再继续讨论；没有执行授权时停在NOT_EXPERIMENT_AUTHORIZED。
```

## 新对话执行准备入口（条件式，仍非实验授权）

以下Prompt用于本轮文档复审后的新对话，取代上节仅供讨论的入口。粘贴它只授权其中写明的静态补证和隔离实现准备；**不批准读取尚未列明的实验数据、生成候选或运行Stage A/B**。新对话须先形成可审阅的准入卡并取得负责人对完整A+B的单独明确授权，才可按冻结协议执行。若准入无法补齐，交付具体阻断和待授权请求；不得自行降为Stage A-only。

```text
接续路线1/2/3整合后的讨论，目标是把路线二route2-candidate-overlap-v1-001准备到可执行状态；只有我对完整准入卡另行明确授权后，才执行一次A+B受控验证。单纯粘贴本Prompt不构成实验授权。当前状态为NOT_EXPERIMENT_AUTHORIZED。

工作树：E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next。所有命令显式指定workdir；精确路径用PowerShell -LiteralPath。不得根目录/父目录搜索、通配枚举或遍历数据目录；缺路径先报告，不猜测。不得读取、遍历、stat或重哈希raw sensor、原metadata CSV、official test、external data；不得改历史产物、旧账本、旧配置或production。Route3 v1-003已合法COMPLETE且四门FAIL，不重跑。

先完整阅读这六份现有文档，长文件分段：
1. docs/decisions/2026-09-26-official-annotation-contract-review.md
2. docs/evidence/2026-09-27-route2-evidence-tables.md
3. docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md
4. docs/decisions/2026-09-27-route2-design-review.md
5. docs/handoffs/2026-09-27-route2-candidate-interval-validation-authorization-prompt.md
6. docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md
以review最后的“新对话执行入口前的文档复审”及其中保留的“整合后修订”为当前状态；不新建交接包。本消息额外授权对src/eating_event/a1/boundaries.py、src/eating_event/a1/inputs.py、src/eating_event/a1/execution.py、src/eating_event/a2/features.py四个精确源码进行静态只读，用于核实component/有效窗、原逐role标签调用链及固定10D；不运行函数、不扩读其他源码。既有讨论入口列出的五个精确源码仍可静态只读。

先完成准入补证并给出逐项证据：A1根目录与105 role的score/identity/cache/参考candidate登记路径、hash、字段及role/global-ID绑定；新16D和固定10D的确切来源；原candidate label与训练/inner/outer评价语义；300s参考的有效窗/component/排序/区间及support复现定义。未获得精确数据读取授权前，只能从已获准文档和上述源码提取路径或提出所需的精确路径/字段，不打开、stat或重哈希那些artifact。GT单JSON的可申请来源字段上限为七项；消费者须使用读取前已按phase/role/participant物理限定、只含共同五字段加该阶段唯一资格的六字段视图或预先获批的等价provider；先全量解析再过滤不合格。Stage A参考candidate row也须字段级隔离，不能整行物化旧label/source_16d/分数后再过滤；若需脱敏reference视图，另列生成权限、时间、路径/hash与独立审阅。

GT字段口径：原eligibility的七字段只是来源上限。每个phase/role/participant预限定视图只向消费者暴露共同五字段（participant_id,event_index,start_ms,end_ms,duration_ms）加该阶段唯一资格字段，共六字段；训练阶段不暴露evaluation_eligibility，inner/outer评价阶段不暴露training_eligibility。评价视图只在对应预测冻结后开放。任何已返回完整七字段的provider均不合格。

可以仅为新route2 study准备隔离实现和修订现有三份路线二文档；先列明新增代码/输出路径及权限边界。不得触碰旧A1/A2/Route3运行身份、配置、产物或production；准备阶段不得实际读取实验数组、GT或生成候选。独立审阅新实现的role惰性装载、GT/reference字段隔离、进程树RSS/worker、峰值磁盘、单调active/fit wall、崩溃和不可重置账本；有缺口就列为阻断，不用低频监控冒称硬上限。

形成一张具体A+B准入卡供我审阅：逐文件路径/hash/字段/role权限、分阶段GT读取和独立实现审阅证据、旧A2与新Stage B在训练标签/26D/HGB/nested role/阈值选择/decoder/matcher-evaluator上的逐项静态等价审阅、唯一新study命名空间与空闲检查方法、Stage A+B资源硬线及入场公式、105参考+105处理/25 fit attempts/25预测/65解码/最多21评价上限、合法早停和终态。参考interval/support复现不能替代非候选协议等价审阅；缺一项不把F1差异归因于gap规则。资源提案见design §5，需由我明确确认或改写；A+B全部输入与预算须在首次重建前一并获批。未取得我对该准入卡的具体实验授权前，不运行测试、候选重建/计数、训练、预测、解码、评价或audit/run，也不创建study输出/账本/锁。

只有收到我对完整A+B准入卡的单独明确授权，才依冻结协议执行一次；先全105参考复现，再全105严格重叠处理。Stage A零GT；参考失败即停且处理调用为0，全相同则fit前停。Stage B按训练标签、四inner角色全部三阈值预测冻结后的inner评价、outer预测冻结后的终评顺序读取GT。资源/输入/G3等合法早停要保留证据，不强行耗满25 fits、不自动重试或追加预算。最终给出study终态、实际调用/资源账本、来源与隔离审阅证据、预声明指标与限制；不要自动启动后三个架构方向。若准入不可得，只提交阻断与具体待授权请求；Stage A-only必须另提、另审、另授权。
```

## 建议批准的唯一问题

判断对保存的role-specific窗口分数只改变候选融合规则，能否改善本地事件输出：从当前300,000ms gap fusion改为**仅合并正时长相交的positive windows**。按participant/record/session/observed-support component分组，所有区间半开 `[start_ms,end_ms)`；排序后仅当 `next.start_ms < current_end_ms` 时延续候选，端点相接、任何正间隙、质量无效或身份/component改变都切开。positive固定为已保存role-specific `relative >= 0`。不搜索gap，不生成额外候选网格或cap。

唯一对照为保存的A2-004 300s候选流程及结果。固定分数、fold/role、A2 26D schema、HGB参数、inner threshold集合 `{0.10,0.25,0.50}`、final minimum 180s、decoder fusion 600s、GT denominator与本地matcher。原参考规则为`next.start_ms <= current_end_ms + 300000`；处理为严格`next.start_ms < current_end_ms`，不能将旧构建器的gap参数直接设零。新候选的16D和26D必须按同一冻结定义重算，不能复制父候选向量或标签。A2-004结果和预算不能重开或继承。

完整设计及证据表：

- `docs/evidence/2026-09-27-route2-evidence-tables.md`
- `docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md`
- `docs/decisions/2026-09-27-route2-design-review.md`（包含既往审阅与整合后修订记录）

## 执行前必须取得的新决定

负责人必须明确批准：

1. 候选生成、独立新study输出/append-only ledger及新实验代码允许的精确范围。拟用全新`route2-candidate-overlap-v1-001`、输出`artifacts/route2-candidate-overlap-v1-001/`、外置不可重置账本`artifacts/route2-candidate-overlap-v1-001-budget.jsonl`及锁`artifacts/route2-candidate-overlap-v1-001.lock`，未来启动前须精确确认未占用并冻结身份；本轮不创建。账本累计参考/处理应用、fit attempt、预测、解码、资源与终态，失败/中断不重置、不自动重试。不得改旧配置、代码身份、账本、产物或production。
2. 新candidate 16D的公式已由`src/eating_event/a1/events.py:54-91`定位：同role已保存`relative`的六个统计量、support数/时长/密度、support窗`coverage`三统计量、起止毫秒模一天的sin/cos。仍须批准精确派生文件/成员与role绑定，并核实A2固定10D实现及原A1/A2 candidate-label调用链；不能把“公式已知”当成数据权限已齐。未来GT读取上限为 `artifacts/g1-participant-exclusion-eligibility-v3-final.json.event_eligibility` 的 `participant_id,event_index,start_ms,end_ms,duration_ms,training_eligibility,evaluation_eligibility` 七字段；分别冻结训练标签、inner阈值评价、outer终评的role/participant白名单、读取时点和消费者。训练标签拟用同participant、同训练role的 `training_eligibility` 与任一IoU严格>0.25，outer候选标签null；inner四角色全部三阈值预测冻结后才用该outer训练participant的 `evaluation_eligibility`，outer预测冻结后才读其held-out评价资格。不能用整份JSON预载后过滤冒充分阶段读取；旧A2 audit/run不能原样复用。不授权 `event-representability-v3-final.json`、其他成员或旧candidate标签；当前也不允许读cache feature/label成员。字段、路径、阶段读取实现或历史语义未明确时停止`INPUT_NOT_AUTHORIZED`。
3. 冻结A1 artifact root、`role-graph.json`、`window-identity.json`、`score-provenance.jsonl`、cache-manifest与record身份审核的精确路径/注册hash；score-provenance中精确score路径只读 `ids/raw/relative`及登记阈值，cache-manifest中精确cache_path只读 `starts/ends/coverage/crosses_gap`，并核对global ID顺序。A2 `role-digests.json`登记candidate行仅取身份、区间和`support_indices`用于参考门，不读旧16D/label/分数；如旧candidate行是混合记录，须先证明字段级隔离，整行物化后再过滤不合格。若要预生成只含允许字段的reference视图，另列并批准生成权限、时间、路径/hash和独立审阅。raw sensor、原始metadata、official test和external仍不在范围；此处是未来拟议输入，不是本轮读取许可。
4. 新研究Stage A及全局资源数值提案：Stage A active wall≤1,200s、全study active wall≤3,600s、累计fit wall≤900s、进程树RSS≤`min(4GiB, floor(3×首次启动可用RAM字节/5))`、Stage A disk≤2GiB、全study disk≤4GiB且首次启动同卷可用磁盘≥8GiB、并发计算worker线程≤2；单调时钟累计从invocation入口至终态写出的active wall，进程树RSS与含临时/原子副本的峰值磁盘均不因中断重置。Stage B在无标签Stage A后以处理候选总数`N`、25个周期训练四OOF角色加对应held-out角色的最大行数`M`、25预测批次总行数`S`、含身份/support/16D的完整处理候选UTF-8文件字节和`B`、当时占盘`D_A`检验：`D_A+3×(B+232N+8S)+268435456≤4294967296 B`且`536870912+6×232M≤冻结RSS ceiling`；系数只是预声明入场余量，实际资源仍受硬线监控，详见design §5。新study须按role惰性载入/释放、同卷计费并证明硬限可执行；崩溃导致最后耗时不可核算时不可续跑。整表和式子须在首次重建前确认或改写并一并批准；实测数量仅代入批准的式子，资源不满足就停止，不运行后补预算。这些数字是支出硬停止线，不是预计成本或A2/Route3额度。当前提案要求A+B一并准入；不自行改为Stage A-only，另提分阶段申请须先具体化与审阅。无法先定义账本和数值边界时不启动。
5. 批准105个role的两遍候选处理：第一遍105个300s参考全部复现，第二遍105个严格重叠处理；任一参考失败即停，第二遍调用数为0。两遍构成无标签interval-multiset gate，只有处理候选进入后续verifier。批准0 candidate-model fit/predict、25 verifier fit attempts、25 verifier预测批次、65 decoder调用和最多21次event evaluator调用（15次inner合并阈值、5次outer、1次pooled）。失败/中断attempt按批准账本累计，不自动重试。

这些事项未齐全之前，不执行candidate reconstruction、候选计数预演、阈值生成、模型fit/predict/proba、重解码、audit/run或性能试验。要先批准候选重建作为本次实验的Stage A，因为它会产生新候选；不得把它称为纯只读预检。

## 精确输入与角色隔离

未来获批后仅使用：已登记A1 role score的`ids/raw/relative`与阈值；冻结global window identity/role图；cache-manifest精确derived `cache_path`的`starts/ends/coverage/crosses_gap`及所需身份审核字段；A2 `role-digests.json`精确登记candidate row的身份、区间、support；以及在上述eligibility七字段来源上限内获批的、仅含阶段六字段的role-scoped物理视图。Stage A不读取GT/资格标记，也不调用旧A2整份GT hash/audit路径；Stage B训练标签、四inner角色所有阈值预测冻结后的阈值评价、outer冻结预测后的终评分别按其角色白名单读取，outer held-out GT不能参与inner阈值选择。内层评价不能使用训练资格替代评价资格。不得读取 `event-representability-v3-final.json`、其他字段、旧candidate `source_16d`/标签或未批准feature成员；outer GT不用于边界、group、mask或过滤。本段是未来拟议范围，不授权本讨论对话加载数据。

保留participant-disjoint的五外折及原nested role图。每个训练role仅按原A1/A2训练资格与标签语义使用该role所需GT，不把234条评价集合替作训练集合；inner与outer GT按上述阶段分别在其预测冻结后评价。outer held-out数据仅按冻结协议构造推理特征，不进入训练role。每个fit重验G3（至少20个正候选、至少5名正participant、正负两类；另报distinct positive GT，不能称独立验证）。缺分数不是负例，空窗口集只有在ID/质量完整且无positive score时才视为合法空集。

推理候选不能跨record/session/component。`component_id`不是物理source segment；`source_segment_id`保持null。9个跨record/session的竞争案例不授权联合推理；GT共享关系不可作为selector或candidate boundary输入。未知官方接口、全record/未来上下文、CPU/RAM/time限制都要记录为限制，不猜测。

## 调用、评价与停止

- Candidate scorer fit=0、predict=0；复用105个role已保存scores，核验错即`INVALID`并停止。
- Candidate reconstruction完整通过路径上限=先105参考role、后105处理role，共105组配对/210次规则应用；参考结果复用于复现门和差异门，不再重建。参考早停按实际消耗记账，处理调用数为0，不执行剩余role凑数。
- 新verifier最多25次fit attempt、25个heldout prediction batches；不得继承A2的model或quota。
- decoder 65次：20个inner role×3阈值，5个outer role×选定阈值；按新冻结ledger和输入规模计资源。
- event evaluator最多21次：每outer合并四个inner角色预测后在其训练participant上评价3阈值，共15次；5次outer held-out及1次pooled终评。五次阈值选择使用这15次结果，不额外评价。
- 完整五折按同一234 GT分母报pooled/fold TP/FP/FN/F1、long-FP比例、matched起止MAE、候选coverage与规模。matched MAE同时列matched GT的新增/丢失集合。
- Numeric minimum/ideal为pooled F1≥0.66/≥0.80。Stage还要求至少3/5 fold F1≥0.66、每fold long-FP fraction≤0.25、每fold matched start/end MAE≤900s。保留A2已有F1<0.66开发负结果，不称独立确认。
- 身份/角色/特征源或GT泄漏为`INVALID`；G3失败为`VERIFIER_DATA_INSUFFICIENT`；资源中止为`INCOMPLETE_RESOURCE`；完整合法结果不达门槛关闭这个精确变体，不调gap或按outer逐例修补。

Stage A必须完全无标签。先以冻结的原窗口筛选、身份/component分组及300s规则，在全部105个role复现A2-004登记候选区间多重集；同键下还核对规范排序的support身份多重集，以免区间相同而16D输入不同。任一不一致即`REFERENCE_NOT_REPRODUCED`停止，不将其当gap效应；在全105参考通过前，处理规则调用数为0。随后比较同分数下300s与严格正时长相交处理按`(role_id,participant_id,record_id,session_id,component_id,start_ms,end_ms)`及重数计数的区间多重集，不依赖candidate_id，不读GT、资格标记、match或目标FP。105组配对共210次规则应用，参考结果复用；全部相同则`MECHANISM_NOT_SUPPORTED`并在fit前停止。有差异只证明候选变化，最终decoder仍可能重新合并。Stage B只在所有来源/标签/隔离/预算门齐备并获批后进入；训练标签、inner阈值评价与outer终评分阶段读取。任何`NOT_SAVED`、schema缺口或成本数据写入记录，不扩大搜索解决。

## 结束边界

即使完整实验获批并完成，结果也只是已重复使用41人开发群体上的开发证据，不改变Formal G1、full-training、production或A2关闭状态。此提案不启动路线3、full training或production。
 
## 2026-09-27 静态源码补证后的当前准入状态

本轮获准的四个新增源码及讨论入口既有五个源码均已静态只读核对；当前工作树SHA-256、有效窗口/component规则、原逐role标签调用链、固定10D/nested执行语义见design §8。它们仅是当前源码指纹，不能证明A2-004历史运行时绑定。Stage A须继续使用独立的字段隔离reader；不能复用会整份加载features/labels/eligibility的旧loader或audit。

拟新增代码路径（未创建）：src/eating_event/route2_candidate_overlap/contracts.py、inputs.py、gt_provider.py、candidates.py、features.py、execution.py、budget.py。study输出路径仍为artifacts/route2-candidate-overlap-v1-001/、artifacts/route2-candidate-overlap-v1-001-budget.jsonl、artifacts/route2-candidate-overlap-v1-001.lock；本轮未创建、未核验占用，也未生成候选。

目前不能形成可批准执行的完整A+B准入卡：A1冻结root与105个score/identity/cache的精确登记路径、文件hash、字段与role/global-ID绑定未从artifact核对；A2 role-digests登记的105个candidate rows及混合字段隔离方式未核对；七字段GT的阶段限定provider/派生视图不存在或未审；A2-004历史config/代码绑定及matcher/evaluator实现级等价未证；资源监控/崩溃账本实现未审；design §5数值仍待负责人确认或改写。未授权任何artifact读取；不执行Stage A-only。

更正（同日后续只读核验）：本段写入时尚未检查占用；随后仅对上述三个study输出精确路径执行Test-Path -LiteralPath，目录、账本和锁均不存在。未读取输入artifact，也未创建study输出。
 
更正（同日后续只读核验）：本节写入时尚未检查输出路径占用；随后对study目录、budget账本、lock三个精确路径执行Test-Path -LiteralPath，均不存在，且均未创建。当前终态为 INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED。
 
## 2026-09-27 完整 A+B 卡复审补充：仍不构成授权

状态：NOT_EXPERIMENT_AUTHORIZED。本 prompt 的任何文字或代码准备都不是运行许可。现已建立的隔离源码只用于后续审阅，不具备完整可执行 A+B Stage B，也未通过最新补丁的独立复审。九个源文件的逐文件 SHA-256 及允许的精确源文件范围记在 design §8 与本次新增卡片中。

Study 输出空闲检查仅检查了三个具体 -LiteralPath，目录、JSONL 账本、lock 均不存在；没有创建任何一项。没有读取、stat 或哈希实验 artifact。完整 A+B 入场仍缺：真实 A1 score/identity/cache 和 A2 reference 的 105-role 路径/hash/字段/role/global-ID 注册；旧 reference 行隔离 label/旧 16D/分数的受审视图；在原来源七字段上限内预先物理限定phase/role/participant及阶段单一资格的六字段GT视图与生成审阅；A2-004 历史配置/标签/模型/matcher/evaluator 精确来源及与新 Stage B 等价审阅；完整 Stage B adapter；OS 级资源/计时/崩溃账本硬限实现和独立复审。

待负责人确认/改写 design §5 的所有资源数字和 Stage B 入场公式，并在首次候选重建之前一次批准全部输入与 A+B 两阶段预算。计划硬额度仍是 reference 105 roles → treatment 105 roles；candidate fit/predict 0；最多 25 verifier fit attempts、25 prediction batches、65 decoder calls、21 event-evaluator calls。reference 一处失败即停且 treatment 调用为 0；处理区间多重集全相同则 fit 前以 MECHANISM_NOT_SUPPORTED 停止，support 差异只作输入完整性检查，不能成为继续 fit 的理由。任何 P1/资源/崩溃边界均不得靠自动重试或补预算绕过。Stage A-only 需另提、另审、另授权。

当前具体所需的分阶段只读/视图生成授权与完整输入清单格式见 design 文档新增 A+B 入场表。收到精确授权材料并完成独立 review 后，仍须另行提交完整卡供负责人明确批准；此前不运行测试、候选重建或计数、训练、预测、解码、评价、audit/run，也不创建 study 输出、ledger 或 lock。
 
## 2026-09-28 独立复审追加阻断

另一份独立只读审阅另外确认下列问题；均未通过实现补丁解除，且即便 Stage A 的资源预算获批也不可入场：

1. A1 完整输入校验还依赖 invalid_runs 与 finite 111D window-feature quality。四个 geometry cache 字段不能证明历史 score 来自有效 A1 run；每个 role 的质量声明须绑定真实 A1 run hash、role、identity view hash 和完整性检查，且目前未从获准登记材料核实。
2. 105 个 score global IDs 与 window identity、role graph 的精确映射/顺序尚未证明。不能把数组行序当作 identity 证据。
3. 旧 A2 candidate spool 含 label、旧 16D 和 score 等混合字段；整行 JSON 解析后再筛字段不是 Stage A 字段隔离。必须使用另行批准并审阅的预投影 reference view。
4. A2 的局部 role 数据读取仍会全局预载 truth map，不能复用到 Stage B；新实现须维持按阶段/role 惰性读取与局部保留，且独立审阅其对象生命周期。

该审阅把几何、标签、固定 10D 与 nested 语义核对为静态结论，但 Stage B 仅在代码形状上与冻结设计相符；A2-004 历史 config/代码身份、matcher/evaluator 实现及协议等价没有核实。它明确认为资源监控、崩溃边界和新 study 惰性隔离尚未实现/审阅，因此不能开始 Stage A。此结论优先于历史草稿里任何较弱的就绪描述。
 
## 2026-09-28 最新隔离源码复审结果

更早章节称“补丁尚未复核”是当时状态。独立审阅者已对当前九个 package 文件及三份最新 Route2 文档做完第二轮静态检查。仍未运行测试、导入/编译、实验函数，也未访问 artifact/data。最新结论为 INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED。

已解决/实质改善的静态点：inputs.py 校验 relative == raw - frozen threshold；references.py 已将 WindowIdentity support 精确映射到 role global index；execution.py 限定具体 reference store 与 role reconstructor 类型，关闭任意 callback 注入路径。它们仍不代表真实 registry 或批准已绑定。

未解除的 P1：
1. registry/approval/readiness 仍可自我声明。实际 score/cache/reference registrations、冻结 role graph、输入 registry hash 没有和 ExperimentApproval、ABReadiness、run_stage_a 入场对象逐一比较。score A1 run hash 只校验长度；identity/cache 还未在运行时拒绝全部非 scored participant。
2. GT scope 有阶段角色/participant 检查，但 scope digest、review ID、冻结预测 receipt 未绑定批准登记和真实冻结预测；iter_truth 仍返回完整七字段，因此训练阶段可见 evaluation_eligibility，评价阶段也可见 training_eligibility。需落实严格阶段字段暴露和真实预审视图绑定。
3. Stage A 存在 lease 交错：reference store 逐行读取时持有 identity loader lease，随后 run_stage_a 对同 role 调 candidate reconstructor；同 loader 会拒绝第二个 lease。换两个 loader 也未比较其 registry 完全一致。需修 lease 生命周期或校验统一注册表。
4. Stage B adapter 不存在，执行在处理候选变化后仍返回 INPUT_NOT_AUTHORIZED。16D/26D helper 存在不等于标签、HGB、nested fit/predict、inner threshold、decoder、matcher/evaluator 被集成或证明与 A2-004 等价。
5. ResourceEnforcer 仍是 Protocol；active wall 不含从 invocation 到终态持久化的完整墙钟；ledger/lock 路径未限制在受监控 study 卷。异常或资源超限缺统一终态关闭，reservation 也未绑定真实 Stage B 调用。
6. loader 的 active lease 布尔状态无并发同步；GT 对时间/index 的 int 转换接受过宽。这两项为 P2，也须在实现审阅中处理。

此前另一份独立静态审阅关于 A1 invalid_runs/finite 111D 质量证明、score global IDs 到 window identity 的精确绑定、reference 混合行必须预先投影、A2 局部 role 读取仍可能全局预载 truth map 等发现仍有效；本轮没有相应 artifact 证据或逐项解除审阅。Stage B 与 A2-004 只核过源码形状/设计方向，matcher/evaluator 历史身份和协议等价仍未证明。

最新复审者未检查输出路径占用；负责人代理随后只对三个精确 study 输出路径用 Test-Path -LiteralPath 检查，均为 False。未创建输出/账本/锁。以上代码审阅不改变 NOT_EXPERIMENT_AUTHORIZED，也不允许降级运行 Stage A-only。

## 2026-09-28 当前实证更新与待授权A+B提案

本节覆盖较早入口里“未登记、未生成物理视图”的旧状态；历史内容不删除。G1源事件语义已查清：281条源事件、43名源参与者、41名role graph参与者（40名有源事件、1名无源事件）；264条事件位于role graph内，图外17条全部training/evaluation不eligible。training和evaluation eligible identities完全相同，各234条。保留完整源事件 census、原标签与资格语义；角色物理视图只按冻结role participant scope取行，保留图内不eligible行，外层评价denominator为234。

精确来源登记 SHA-256：`e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`；独立来源审阅PASS，覆盖105 score、1,127 cache、105 reference路径/hash/role/global-ID绑定。物理视图manifest SHA-256：`ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`；独立只读复审PASS，635/635 hash、10,842,725行、105 reference支持身份、110份六字段GT scope/release无错误。对应审阅引用和逐文件源码SHA-256见设计文档本日附录。两个产物状态仍是`PREPARED_UNREVIEWED`；物理manifest的正式`independent_review_id`仍为null，外部复审PASS没有写回产物，也不代表实验批准。study目录、budget ledger、lock精确检查均为空。

当前隔离源码复审：G1/GT阶段门、role lease、Stage A参考先于处理、Stage B预算算术和已审阅A2-004部件PASS；正整数门已收紧并独立复审PASS。仍有P1阻断：没有具体OS hard-limit controller；记录的墙钟在terminal append/fsync/close之前采样；A2 audit/role-digest/登记/投影准入身份的运行期绑定未完成。历史A2 label prejoin和`metrics.py` IoU内核尚未在允许范围内独立审阅。故当前维持`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`，不得运行Stage A/B，也不自动改为Stage A-only。

**可在新对话讨论并提交的一次性完整A+B方案：**

1. 研究ID为`route2-candidate-overlap-v1-001`。完整A+B输入、独立复审和两阶段预算须在任何候选重建前一起获批；本段及复制本Prompt都不是实验授权。
2. Stage A对105 roles先全部执行`reference_300s`，全部成功后再执行105个`strict_overlap`；任一参考失败即停，全体候选interval multisets均无变化时以`MECHANISM_NOT_SUPPORTED`在verifier前停。support用于完整性检查。Stage A不读GT，candidate-model fit/predict为0。
3. 仅当interval机制发生变化且输入、身份、资源及独立实现审阅全通过时进入固定5 outer×4 inner Stage B。training GT按训练role开放；inner/outer evaluation GT须各自在对应冻结prediction receipt后开放。最多25 verifier fits、25 prediction batches、65 decoder calls、21 event-evaluator calls；失败attempt计入账本，不重试、不续跑。
4. 待确认预算：Stage A wall≤1,200s；全study wall≤3,600s；fit wall≤900s；RSS≤`min(4GiB, floor(3×首次启动可用RAM/5))`；Stage A disk≤2GiB；全study disk≤4GiB；启动同卷free disk≥8GiB；workers≤2。Stage B按Stage A末当前占盘`D_A`、候选总行数`N`、每周期最大拟合包络`M`、25个held-out批次总行数`S`及完整候选文件字节`B`执行：`D_A+3×(B+232N+8S)+268435456≤4294967296`且`536870912+6×232M≤冻结RSS ceiling`。这仍是待负责人确认/改写的支出提案。
5. 实验前必须补齐并审阅真实OS硬限、覆盖terminal持久化的墙钟计量、不可伪造的来源/A2审计/projection/准入绑定，以及历史label-prejoin和IoU内核等未审阅协议项。缺任一项不进入A+B；不自行降级Stage A-only。Route3 v1-003保持合法`COMPLETE`、四门`FAIL`，不重跑。

因此可以另开对话继续准备并提交上述完整A+B授权申请；目前还不能将现有材料作为可执行准入卡直接批准或开跑。

## 2026-09-28 执行后端与授权申请状态

Windows-native硬限路径未通过预检：主机为Windows 11 Home、非管理员，无Docker/FSRM；Job Object与NTFS用户quota不覆盖本研究要求的全部进程/线程/目录限制。WSL2 Ubuntu-22.04已有systemd/cgroup v2。无数据能力探针证实可设置`MemoryMax`/`TasksMax`/`CPUQuota`，ext4 loopback可以在镜像容量处拒绝追加写；500ms systemd `RuntimeMaxSec`探针实际在750ms终止，故还需外层单调时钟和保守停止余量。当前WSL Python缺scikit-learn，Route2 package未集成WSL runner或POSIX路径适配。没有安装软件、改全局WSL配置、运行项目测试或实验；探针临时文件/服务已清理。

本Prompt包含完整科学协议和待批预算，但由于硬限控制器未集成、A2审计/投影hash尚未绑定到runtime admission、terminal后墙钟回执缺失，当前只能作为`NOT_READY_FOR_EXECUTION`的条件申请。继续前需由负责人确认执行环境与产物访问合同：选择WSL-native隔离volume并接受WSL路径适配，或提供已委派cgroup v2和study级硬quota的Linux runner。确认平台不等于实验授权；完整A+B仍须另行明确批准，随后才可进入Stage A/B。

继续保持`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`。Route3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑。

## 2026-09-28 后端选择后的申请入口（覆盖上节二选一问题）

负责人已要求**重新设计方案与执行方案**。当前选择WSL2 Ubuntu-22.04原生runner、systemd/cgroup v2及study专用ext4 loop输出卷作为待实施路线；不是A+B实验授权。新[设计节](../superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md)、既有[review的整合后修订](../decisions/2026-09-27-route2-design-review.md)和[执行计划](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md)为后续审阅入口，不新建交接包。旧Windows `artifacts/route2-candidate-overlap-v1-001*`路径只作此前空闲检查记录，**不再是拟批准的运行输出路径**；Linux拟议绝对路径及Windows只读审阅入口须在最终卡中冻结并复核。

提交完整A+B执行授权申请前，必须先有：①同一隔离卷在Stage A硬限2 GiB、预冻结Stage B入场并fsync后才在线增至全程4 GiB的无数据原语证明、正式gate实现与独立审阅；②worker的输出、ledger、lock、临时、日志同卷写限制，controller镜像/VHDX、系统journal和外部wall锚写入例外逐项计费，且每phase只读精确输入映射；原“运行中Windows登录用户不能改写/读取GT”是**尚未关闭的host边界P1**，不能由WSL同账号UNC限制推定PASS；Stage A零GT，每outer的12份inner阈值预测全冻结后才放inner评价GT，outer预测冻结后才放outer评价GT，phase退出撤销可见性；③原RSS与worker指标的可强制对应证明，覆盖supervisor/helper/worker，或经负责人批准的资源指标修订；④外层invocation至terminal fsync/close后的wall receipt、receipt fsync后截止核验、停止余量与崩溃不可续跑证据；⑤Linux依赖/路径适配、A2/G1/登记/投影manifest的启动元数据绑定、GT物理文件在对应release后才核实际hash、历史label-prejoin/IoU及完整Stage B等价独立复审；⑥负责人逐项确认包括“WSL backing filesystem与其VHDX所在Windows实体卷两层free各≥8 GiB”解释在内的两阶段预算。任何一项未齐，状态仍是`NOT_READY_FOR_EXECUTION`，不使用已准备视图运行Stage A-only或A+B。

届时最小待批准卡只覆盖原研究ID一次完整A+B及既定105参考→105处理、25/25/65/21上限和预声明停机分类。负责人须在**具体代码/配置hash、WSL绝对输入输出路径、预算与独立审阅收据全部可查后**另行明确批准；本Prompt、后端选择和无数据控制器验证均不能代替该批准。只有用户提供合法路线二结果后才讨论三个架构方向的最小验证；严格重叠机制不重复，Route3 v1-003不重跑。

## 2026-09-29 新对话执行提示（准入实施，非实验启动）

以下文本可直接复制到新对话。它要求先完成可审阅的正式控制器/隔离实施与独立复审；即便新对话完成这些工作，也须另有绑定具体hash/预算的**明确A+B实验批准**才可首次运行。最新状态以既有review的[2026-09-29整合后修订](../decisions/2026-09-27-route2-design-review.md)为准，不新建交接包。

> 接续路线1/2/3整合讨论。工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。先读路线二现有设计`docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md`、执行计划`docs/superpowers/plans/2026-09-28-route2-wsl-controller-execution.md`、既有review`docs/decisions/2026-09-27-route2-design-review.md`的**2026-09-29最新修订**，以及`docs/evidence/2026-09-29-route2-wsl-synthetic-os-probes.md`、三份raw JSON、`docs/evidence/2026-09-29-route2-linux-dependency-runtime.md`和当前源码/测试。保留已有工作树改动，不重建交接包。
>
> 当前仅有准备视图及无数据能力证据：来源登记/物理投影仍`PREPARED_UNREVIEWED`，A+B未获授权，Stage A/B未合法运行，路线二没有合法结果；`FROZEN_ADMISSION=None`。本对话授权的是**补齐准入实现、合成验证、独立复审和提交具体申请**，不包含运行Stage A-only或A+B，不访问受禁raw sensor、原始metadata、official test、external data，不提前打开110个GT物理视图。Route3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑；gap=0严格重叠已由路线二覆盖，不换名重复；合法路线二结果到来前不启动三个架构方向。
>
> 先处理host信任边界：本机Fancy账号可`wsl -u root`进入Ubuntu-22.04且可提升本地管理员，现有WSL worker隔离不能约束该Windows宿主操作者。若负责人明确确认Windows host owner可信，可继续WSL2 worker/phase隔离并把该边界写进预算和review；若要求宿主登录用户运行中也不可看GT/改ledger，改用独立受控Linux runner。未确认时保留P1，不能声明GT物理隔离PASS。
>
> 然后按执行计划逐项实现并取证：Linux supervisor入口先取单调时钟；正式镜像创建前同时核WSL backing filesystem及`ext4.vhdx`所在Windows实体卷各≥8 GiB，绑定实际设备/卷；Stage A≤2 GiB，同一image/loop/ext4只在105+105、机制差异、`N/M/S/B/D_A`门及账本fsync后扩至≤4 GiB；冻结image path/dev/inode/length、loop、UUID、mount ID/device。worker研究写路径含临时/缓存/IPC/stdio必须同study卷硬限制；controller镜像/VHDX分配、system journal和外部wall锚为待批准的可信控制层例外，逐路径/占盘峰值单列。父cgroup覆盖supervisor/helper/worker，给原进程树RSS公式和worker≤2真实强制证据，不能拿CPUQuota或采样代替。
>
> 实现controller拥有的Stage A逐role精确只读bind租约及旧FD/挂载撤销轮换；Stage A零GT。Stage B每个训练/inner/outer GT在对应持久发布门后进入短寿命单视图worker，12份inner阈值预测全冻结才开放inner评价，outer预测冻结才开放outer评价；异常也要OS确认退出/撤销。GT只在release后通过同FD核hash并读取。controller私有HMAC key只交GT child；历史control matched GT IDs仅在获准事后流程用同key承诺化，完成matched集合变化诊断。terminal账本append/fsync/close后取得并持久化wall receipt，再由可信外部服务退出/单调截止锚判定；缺失/迟到/崩溃都fail closed。
>
> 把来源登记、投影manifest、A2 audit-ready/role-digests、G1、13-wheel Linux锁/ABI、路径map、完整Route2代码执行闭包/入口脚本/已安装venv文件、controller/phase worker、预算和独立审阅ID绑定为不可变只读且不可由调用者伪造的运行期准入；移除`stage_b.py`对活动工作树源码/config的依赖。Stage A只核非GT可见文件，混合G1/A2原件不为hash而打开，GT实际文件按phase release核。独立复审完整A2-004标签/26D/HGB/G3/nested/阈值/decoder/IoU/matcher/evaluator、25/25/65/21及Linux相对历史Windows的数值等价；第21项当前是pooled代数归并而非直接`evaluate_participants`，须先裁决。只用无项目数据的合成反例验证。新结果写回**既有review的整合后修订**、原设计和执行计划。
>
> 最后给出逐项P1/P2证据和最小可审阅的**一次完整A+B**待授权卡：研究ID`route2-candidate-overlap-v1-001`，105个300s reference全过后105个strict positive-duration overlap treatment，0 candidate scorer fit/predict；机制全同在fit前`MECHANISM_NOT_SUPPORTED`，差异且全部门通过才做固定5×4 Stage B，最多25 fit、25预测、65 decoder、21 evaluator额度，无重试/续跑。卡上精确列出六种非`COMPLETE`停机分类及`COMPLETE`、输入根/study mount/image/ledger/lock及宿主卷身份、controller写例外与计费、完整代码/依赖hash及独立review ID、terminal后wall锚和GT lease收据。负责人须逐项确认双层8GiB解释、1200/3600/900s与60s停止余量、RSS、2/4GiB、worker、pooled第21项语义及host边界，再另行明确批准具体hash卡。未获该批准前维持`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`，不启动任何路线二实验。
