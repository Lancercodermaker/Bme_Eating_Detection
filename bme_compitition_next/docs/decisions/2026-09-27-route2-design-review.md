# 路线二设计独立审阅与修订决定

日期：2026-09-27  
状态：`DESIGN_REVIEW_COMPLETE / NOT_EXPERIMENT_AUTHORIZED`  
工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`

## 原始审阅结论

本节记录原始审阅范围；当前准入条件以本文最后的“新对话执行入口前的文档复审”为准，并结合其保留的“本轮静态定义补充与准入复审”和“整合后修订与下一轮讨论”。原始审阅通过不代表后续新增输入、阶段或预算已经获批。

独立审阅未发现证据表中的已核对事实与指定来源冲突，也未发现审阅过程越过读取白名单。审阅者核对了五个已登记 outer candidate 文件的路径和行数、选中候选行的身份/区间/support/source-segment/boundary 字段、11组竞争区间间隔算术，并确认文档保留了 `NOT_SAVED`、58个零注释交叠长FP的 `UNKNOWN` 状态及A1/G1/A2既有关闭边界。

审阅者没有重新计算全部79条 lineage，也没有从原始匹配输入重算11组 IoU 和匹配归属；这些结论仍依赖已批准的A2证据复核及本文列出的来源。此限制不改变本轮审阅的只读结论。

## 修订的问题与处理

**高优先级：outer GT可能控制是否继续实验。** 原设计曾允许用由 outer GT/matcher 确定的“目标长候选”变化，在首次 verifier fit 前决定继续或停止。这会让 held-out 标签影响流程。现已删除该门槛。修订后的 Stage A 在每个预声明 role batch 内，对同一组已批准 score streams 分别应用冻结的300秒参考规则和唯一的 gap=0 处理规则，只比较 candidate interval 多重集；不得读取 GT、匹配结果或目标 FP 名单。若105个role的区间多重集全部相同，则在任何 verifier fit 前以 `MECHANISM_NOT_SUPPORTED` 停止。训练标签只在此无标签门通过后，按冻结的 nested role 语义构造；outer GT 只在对应预测完全冻结后评价。

**权限范围不够精确：GT 输入曾泛称 eligibility/representability 文件。** 初次修订将输入锁定到 `artifacts/g1-participant-exclusion-eligibility-v3-final.json` 的 `event_eligibility`，但独立复审指出，若缺少资格标记，五个身份/区间字段不足以从281条注释中重建训练和234条评价集合。原始修订将拟议白名单明确为 `participant_id,event_index,start_ms,end_ms,duration_ms,training_eligibility,evaluation_eligibility`，并区分训练标签与outer评价。此处是历史记录，不是当前新增读取授权；整合后进一步补齐inner评价阶段，见下文。`event-representability-v3-final.json`、eligibility 文件其他字段及旧 candidate 标签均不在提案授权范围内；如确有需要，必须另列精确路径和字段并单独批准。

对应修订已同步到验证设计和待授权 Prompt。独立复审确认资格标记白名单和分阶段读取已补齐，Stage A仍不读取GT/匹配/目标FP名单，修订段落没有遗留问题。复审未读取其他文件或执行实验；在新的明确授权前不启动后续操作。

## 路线判断与未决条件

现有证据支持把**候选区间形成**作为下一项待验证机制：对 `relative >= 0` 的窗口，只在同一 participant/record/session/observed-support component 内合并正时长重叠的半开区间（`next.start_ms < current_end_ms`），端点相接即断开。它是一个受控假设，并未证明300秒规则导致相关错误；现有保存材料没有连接前 positive-run 轨迹，因此该因果归因仍为 `NOT_SAVED`。固定分数下此机制不会新增交叠窗口的正分信号，但低覆盖不足以单独证明不可恢复。仅在58个原零注释交叠预测区间内裁切或切分不能创造GT交叠；过滤可能改善标注合约FP，碎片也可能增加FP，不能据此解释其行为真值。

建议为 `SPIKE FIRST`，但当前仍为 `NOT_EXPERIMENT_AUTHORIZED`。首次执行前还需负责人单独冻结新16D特征的精确合法来源、A1/A2 candidate-label 语义、单次study输出和不可重置账本、全局wall/RSS/disk/thread预算与启动测量方式，并批准规定的105个paired role candidate batches、25次verifier fit attempts、25个预测批次和65次decoder调用。A2-004的预算和结果不得继承。缺少任一精确输入、语义或资源边界时，按Prompt停止，不猜测或扩大搜索。

41名参与者全部具有开发集暴露；任何新结果都只是重复使用开发群体的开发证据。A1仍关闭、Formal G1仍为FAIL、full training仍为BLOCKED、production保持UNCHANGED，固定26D A2仍是 `CLOSED_STAGE_MINIMUM_FAIL`。本决定不启动实验、训练、路线三或production。

## 整合后修订与下一轮讨论（2026-09-27）

本节保留当时的整合修订记录；其中逐role配对和仅核对区间的措辞，已由本文最后一节的“先全105参考、再全105处理”和附加support身份门细化。其余历史事实保留。

### 路线1/2/3当前状态

| 路线 | 已有证据与状态 | 可支持的决定 |
|---|---|---|
| 路线1 | 官方标注合约资料审查；用户接受以核验后的标注合约作为开发目标 | 可以继续讨论本地标注合约优化；精确官方matcher、评价范围、接口、未来上下文和资源仍未知。IMU成绩不代替非惯用手结合PPG要求 |
| 路线2 | 证据表与验证设计已存在；尚未生成新候选或运行验证，仍为 `NOT_EXPERIMENT_AUTHORIZED` | 优先补齐准入条件，取得候选形成机制证据；不能称为重跑，也不能将300s融合认作已证实根因 |
| 路线3 | v1-003合法 `COMPLETE / CLOSED_STAGE_MINIMUM_FAIL`；TP/FP/FN=150/126/84、F1=0.5882352941，四门FAIL；A2-004为154/106/80、F1=0.623482 | 关闭固定候选/26D下的matching-aware逐候选训练目标变体，不否定HGB家族、边界模型或联合事件输出架构 |

路线3 v1-002完成25次真实拟合后因实际来源记录缺少 `candidate_count` 而为INVALID，不是OOM，临时指标不接纳；v1-003另耗25次，累计50次真实拟合。v1-003已只读收口，不重跑、不创建v1-004或A2-005。路线3完整来源审查及资源证据见 `docs/decisions/2026-09-27-route3-v1-003-provenance-recovery-review-and-run.md`；本次文档更新引用该已收口记录，没有重新运行或重读模型。

### 当前设计修正

1. **先复现300s参考。** Stage A必须在全部105个role复现已登记参考候选区间多重集，再比较唯一gap=0处理。任一role不一致即 `REFERENCE_NOT_REPRODUCED` 停止，不调窗口筛选或component规则来取得差异。比较使用participant/record/session/component/起止及重数，不依赖新candidate ID。
2. **无标签阶段与GT阶段分开。** Stage A不读取GT、资格标记、match或目标FP。Stage B分别冻结训练标签、inner held-out阈值评价、outer终评的role/participant白名单、资格标记、读取时点及消费者。训练标签使用原A1/A2语义及 `training_eligibility`；inner所有固定阈值预测冻结后才读取其held-out的 `evaluation_eligibility`，仅限outer训练participant；outer预测冻结后才读outer held-out的评价资格。两种资格标记不能假定相同，不提前物化全部outer GT。七字段仍是未来拟议范围，当前讨论不读GT数据。
3. **重建调用不重复。** 完整通过路径上限为105组配对共210次规则应用，每role的300s参考与gap=0各一次；参考结果复用于复现门和差异门，参考早停按实际消耗记账，不执行剩余role凑数。全部相同则在首次fit前以 `MECHANISM_NOT_SUPPORTED` 停止。有差异只证明候选机制改变，最终600s decoder仍可能重新合并，并不保证F1改善。
4. **修正归因强度。** 14个FN提供边界问题线索，不是预期恢复数；低覆盖不是不可恢复的证明。58个零注释交叠长FP行为仍UNKNOWN；仅在原区间内裁切不会产生GT交叠，不排除过滤对标注合约FP的作用。
5. **A+B一并准入，先定两阶段资源边界。** 当前提案要求独立study、不可重置账本、全部合法特征/标签输入及Stage A/B数值上限在首次重建前齐备并一并获批。Stage A保存的实际数量仅判断是否满足事先冻结的Stage B投影规则和上限；资源条件不满足就停止并返回证据，不能运行后补预算。当前数值预算仍未补齐；Stage A-only不在当前提案内，若完整前提仍不可得，可在下一轮另行讨论、具体化和审阅，不自行分段执行。

这些修正已同步到现有design和authorization-prompt，保留原始审阅的范围与限制。本次修订的文档一致性独立审阅记录在本节末补充；原始审阅不会自动覆盖本次修订或尚缺的输入/执行实现。

### 用户顺序偏好与合法终态

用户希望：路线二证据不足时，先完成路线二受控验证，再根据结果决定三个架构方向各自的最小验证。本轮只落实讨论入口和文档说明；不启动路线二，不把这个顺序偏好扩展为已批准全部输入、预算或后三个方向的实验。

“完整执行”指获批协议到达预声明的合法终态。参考无法复现、机制无差异、输入/隔离/G3或资源不满足都应按协议停止并保留证据，不强行完成25次拟合。输入与资源中止不等于模型性能失败；合法完整五折失败只关闭这一精确gap=0变体；即使过门也不自动改变production或独立确认状态。

后续三个方向应有条件进入讨论：

- **候选几何与输出约束：**gap=0候选机制已由路线二覆盖，不换名重复；180秒最短输出是另一个变量，不能与gap=0一起修改。
- **低容量边界与联合事件输出：**只有路线二留下的误差证据、合法特征和GT-free运行时分组支持时，才讨论最小可证伪验证；11组事后GT竞争关系不构成推理组。
- **连续时序表示的信息增量：**先证明合法现有信息或新输入能补充固定26D缺失的信息，再讨论更高容量模型；不因现有变体失败推定复杂模型更好。

41人重复开发的过拟合风险贯穿全部方向。后续结果只能支持本地标注合约下的开发性能，不能确认官方测试集性能、全天行为真值、58段真实未进食或PPG场景合规。

### 下一轮尚缺条件与入口

仍缺新候选16D精确来源/role绑定与固定10D实现身份、原A1/A2 candidate-label与inner/outer评价集合语义、各阶段可执行的role-scoped读取方法、参考窗口/component实现身份、独立study资源数值上限。16D公式已由本轮准许静态代码定位，详见本文最后一节；不得运行函数、读取数据数组、扩大输入范围或先生成候选计数。

下一轮完整阅读六份既有文档，并使用 `docs/handoffs/2026-09-27-route2-candidate-interval-validation-authorization-prompt.md` 的“新对话讨论入口”。不新增独立交接包；若需要更多输入，先列精确证据、用途和为何现有材料不足，等待范围授权。准入条件具体化并完成独立审阅后，才提供单独、具体的实验授权请求。

### 本次修订复审状态

第一轮独立复审发现一项P1：Stage A/B分段授权口径不一致；另有P2：210次规则应用需明确为完整路径上限。现已统一为当前A+B一并准入提案，首次候选重建前须全部输入和两阶段预算获批；Stage A-only仅可下一轮另行提出，不允许自行拆分。105配对/210应用已明确上限，参考早停只记实际消耗。

第二轮由独立审阅代理 `route_challenge` 完整读取三份最新文档，确认上轮P1/P2已解决、三文档口径一致，无新增P0/P1。结论为**文档一致性准备复审通过，不是执行准备完成**。仍为 `NOT_EXPERIMENT_AUTHORIZED`；新16D来源、标签/评价实现、角色读取方法和数值预算缺口继续保留。审阅者仅只读三份指定文档，未检查数据或执行实现。

复审范围仅为三份文档的一致性、权限边界与论证强度，不是尚缺来源/数值预算/执行实现的通过证明。本轮仅修改上述三份现有路线二文档；未运行测试、训练、预测、候选生成、解码、评价、audit/run或新实验，未访问raw、原metadata、official test或external data。

三份文档已完成严格UTF-8解码与表格列数检查：design两表分别7/6个数据行，review整合表3个数据行，Prompt代码块成对闭合；未发现替换字符或连续问号乱码。此为文档检查，不是模型测试或实验验证。

## 本轮静态定义补充与准入复审（2026-09-27，晚于上节）

本轮按既有讨论入口完整阅读六份指定文档；仅在文档不足处静态读取入口允许的五个精确代码文件，未访问cache/score/GT数组或扩搜其他源码。上节“文档一致性复审通过”仅覆盖当时版本，不能当作本轮新增来源/预算的准入结论。路线二仍是 `NOT_EXPERIMENT_AUTHORIZED`。

| 准入项 | 本轮静态证据 | 结论与剩余条件 |
|---|---|---|
| 新候选16D | `src/eating_event/a1/events.py:54-91` 给出16维顺序和公式；`src/eating_event/a2/audit.py:430-457` 指出派生cache `starts/ends/coverage/crosses_gap`，score为登记`ids/raw/relative` | **公式已定位**，无需raw或旧候选向量；精确A1根目录、cache_path/成员读取、全局ID顺序、role绑定和A2固定10D定义仍需批准/冻结 |
| 原candidate标签 | `a1/events.py:166-171` 为对传入truth的任一严格IoU>0.25；`a2/audit.py:269-320` 分出training/evaluation资格；`a2/execution.py:325-329` 要求outer标签null | 拟按同participant且属于训练role的`training_eligibility`真值重算100个inner/subinner role标签；允许代码没有A1原调用点，历史逐role传入集合尚未独立核实，不能称标签合同已完整冻结 |
| GT阶段读取 | 旧A2 audit在`1027`整份读取资格、`1293-1308`提前使用/物化评价GT，run再预载；旧fit来源计数还从评价truth map取值 | 新study必须有经审阅的role-scoped provider：Stage A零GT；训练标签按训练资格；四个inner角色三阈值预测全冻结后才读该outer训练participant的评价资格；outer预测冻结后才读其held-out评价资格。对单JSON先全量解析后过滤不满足时序；训练GT诊断须按训练资格另计 |
| 300s参考与gap=0 | `a1/events.py:153-154` 的300s条件为 `next.start<=current_end+300000`，旧函数传`gap=0`仍合并端点相接；处理要求严格`next.start<current_end` | 未来Stage A先完成105个参考role；参考区间及support身份多重集均与A2登记行一致后，再做105个处理role。任一参考不一致即停，不把它当机制效果；全部处理区间相同则fit前停 |
| 独立预算 | 105参考+105处理、25 fit attempts、25预测批次、65解码、最多21次event evaluator是调用上限；10,745,700窗/1,117,552,800B单26D矩阵只是宽泛数学上界 | design现已给独立study拟议硬停止线和Stage B固定入场式，数值仍待负责人确认；它们是支出政策，不是实际wall/RSS/disk预测，不能借A2/Route3额度 |

**需要的精确补证/权限：**先由负责人指定冻结A1 artifact root及`role-graph.json`、`window-identity.json`、`score-provenance.jsonl`、登记score NPZ、cache-manifest/record身份审核、逐条登记的derived cache_path与A2 role-digests/candidate row的完整路径和hash，只批准设计表列出的字段。现有文档只提供部分相对文件名和代码推导字段，不能据此读取数据。若需核验component、A1Window、历史标签调用和固定10D公式，另提对 `src/eating_event/a1/boundaries.py`、`src/eating_event/a1/inputs.py`、`src/eating_event/a1/execution.py`、`src/eating_event/a2/features.py` 四个精确源码的**静态只读**范围，或提供等价冻结定义；本轮未读取它们。GT来源仍限已指明eligibility七字段的未来role-scoped视图，不授权当前读数或整份预载。

**独立研究决定卡：**设计已拟唯一`route2-candidate-overlap-v1-001` namespace、对应输出目录、外置append-only且不可重置的budget账本/lock；本轮未创建，未来启动前还需精确确认空闲。数值提案为Stage A active wall≤1,200s、全study active wall≤3,600s、累计fit wall≤900s、进程树RSS≤`min(4GiB, floor(3×首次启动可用RAM字节/5))`、Stage A disk≤2GiB、全study disk≤4GiB且首次启动同卷可用磁盘≥8GiB、并发计算worker线程≤2。Stage B入场式使用Stage A无标签自产的`N/M/S/B/D_A`，其中`M`包含每周期训练与held-out行，`B`包含完整候选support/16D；详见design §5。安全系数只是预声明的支出筛选，不能证明五折能在预算内完成。未来新study仍需证明按role惰性加载/释放与硬资源限额可执行，并经独立实现审阅。上述数字与测量法须由负责人确认或改写，连同全部输入在首次重建前一并批准；不能从旧A2/Route3耗时或磁盘线性外推。若未获批准，不提出A+B执行授权，也不自行降为Stage A-only。

**复审判断：**建议保持`SPIKE FIRST`的研究优先级，先完成上述精确准入定义，再做A+B一次受控验证。当前静态补证解决了“16D计算式未知”的部分问题，却暴露旧A2执行流与分阶段GT合同不兼容；不能把已有文档一致性审阅扩展成执行实现审阅。未来路线二结果到达合法终态后，再分别决定三个架构方向的最小验证；gap=0已经属于本提案，180秒最短输出另列变量，不自动启动后三方向。Route3 v1-003保持合法COMPLETE、四门FAIL，不重跑。

### 本轮独立复审终态

独立只读审阅先指出16D计算式可从准许源码恢复、旧A2提前全量加载GT、旧构建器`gap=0`仍合并端点相接，以及参考support和角色/身份来源缺口；据此修订三份现有路线二文档。资源专项复审又指出初稿RSS入场式漏计held-out行、`B`口径不清、active wall/峰值磁盘/崩溃计账和硬资源限额实现未定；现已将`M`定义为同一verifier周期的训练加held-out行，`B`限定完整候选UTF-8文件字节，并把惰性加载、同卷、峰值计账与强制监控列为执行前审阅门。

最终独立审阅者重新完整阅读三份最新文档，核对105参考后105处理、support复现门、GT三阶段、最多21次event evaluator、`N/M/S/B/D_A`定义及三文档资源数字/公式，未发现剩余P0/P1/P2。其结论仅为**待授权文档的一致性和论证边界通过**：没有核验未准许的源码、cache/score/GT数据、role-scoped provider或未来资源监控实现；没有运行测试、候选重建、模型、评价或audit/run。因此输入权限与实现审阅门仍未过，`NOT_EXPERIMENT_AUTHORIZED`不变。

## 新对话执行入口前的文档复审（2026-09-27）

本次仅重新完整审阅上述三份路线二文档，未扩大代码或数据读取。初轮一致性复审没有新P0/P1；权限复审发现一项P2准入措辞缺口：Stage A需取旧candidate row的interval/support，若行内还含旧label、`source_16d`或分数，整行物化后再过滤违反Stage A无标签与字段白名单。追加科学复审发现一项P1准入缺口：参考候选复现不足以证明新Stage B其他环节与A2-004同协议。design和待授权Prompt现已分别补充reference字段隔离门和非候选协议等价门；均须在首次重建前提供实现及独立审阅证据。此文档修订不代表这些实现已存在或获批。

三文档的A+B一并准入、105参考全通过后才进行105处理、GT三阶段、21次评价上限和`N/M/S/B/D_A`预算式保持一致。另明确：参考区间/support复现只证明候选输入，不能证明新Stage B与A2-004在训练标签、26D、HGB、nested role、阈值选择、decoder及matcher/evaluator上同协议；这些非候选环节须逐项冻结代码/配置身份并独立审阅，缺一项不能把F1差异归因于gap规则。仍缺精确登记路径/hash与role绑定、原A1逐role标签及固定10D/component/有效窗实现身份、GT role-scoped provider、reference字段隔离实现、惰性装载与硬资源监控的独立实现审阅，以及负责人的预算确认和具体实验授权。新增的“新对话执行准备入口”只允许按其范围补齐这些前提；复制它不等于批准A+B，状态继续为`NOT_EXPERIMENT_AUTHORIZED`。Route3 v1-003维持合法COMPLETE、四门FAIL，不重跑。
 
## 新对话静态源码补证与独立复审（2026-09-27）

本轮在六份指定文档之后，按新增白名单静态核对四个源码，并复核讨论入口原列五个源码。九个当前工作树源码SHA-256及逐文件范围见现有design §8。没有打开、stat或重哈希任何输入artifact；没有运行源码函数、测试、候选计数/重建、训练、预测、解码、评价或audit/run。Route3 v1-003仍是合法COMPLETE、四门FAIL，不重跑。

静态核实结果：A1有效窗校验包括end>start、start顺序、无hard gap、coverage≥0.8、invalid_runs≤20；observed-support component按(start,end,row_index)建立，端点相接会连接。A1 candidate规则保留relative≥0并用300s的<=条件融合，support保留完整窗口身份；旧A1 label调用用同participant training truth和任一IoU>0.25，outer candidate标签为空。A2固定10D、26D float32组合、nested 5/4/4角色、inner阈值选择和outer终评顺序均已定位。准确含义、hash及实现边界见design §8。

第二审阅者独立只读六份指定文档和九个白名单源码，未读artifact、数组、GT或其他源码，未运行函数/测试/实验，未修改文件。其复审确认上述几何、标签、10D及nested语义结论；另指出四个准入风险：A1 loader另验证invalid_runs和feature有限值，当前允许的四个geometry成员不能单独证明历史分数来自通过完整A1输入校验的run；score global IDs必须与window identity及105个role精确绑定；A2 candidate spool整行解析混合row，不能作为Stage A字段隔离器；A2局部role lazy读取仍全局预载truth map。复审结论是静态合同核对完成，执行准入仍未通过。

Stage B只在代码形状上与冻结设计相符，不能称为A2-004等价通过。A2-004历史config/代码身份尚未核验，A2-004所用matcher/evaluator的实现文件不在批准静态白名单内；协议等价门仍须取得精确历史身份及独立审阅。新study role惰性加载、GT/reference字段隔离、进程树RSS/worker、峰值磁盘、单调wall、崩溃账本实现尚不存在或未审，因此不能开始Stage A。

只读namespace占用检查对以下三个精确路径返回不存在：artifacts/route2-candidate-overlap-v1-001/、artifacts/route2-candidate-overlap-v1-001-budget.jsonl、artifacts/route2-candidate-overlap-v1-001.lock。没有创建目录、账本或锁。

当前仍需负责人或数据源提供A1冻结root及精确注册文件；逐role score/cache与105 candidate reference行的路径/hash/字段/role/global-ID清单；GT阶段限定provider或经单独批准的派生视图；Stage A混合reference字段投影及审阅方式；A2-004 config/code和matcher/evaluator实现身份；新执行实现及其独立资源审阅。design §5资源数字也须确认或改写，并和全部输入在首次重建前一并批准。状态保持 INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED；不降级为Stage A-only。
 
## 2026-09-27 新对话执行入口前的实现复审

当前状态仍为 INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED。上一节所列“拟新增代码尚未创建”的记录是历史状态；之后只在新 study 包 src/eating_event/route2_candidate_overlap/ 建立了九个隔离源文件。每个文件的当前 SHA-256 和准确路径见设计文档新增的“实现快照与未闭合门禁”表；没有触碰旧配置、历史产物或 production。

独立静态审阅在随后局部补丁前发现 7 类 P1：真实 artifact/role/global-ID registry 未绑定；approval/readiness 自我声明；Stage A reader/callback 可绕过且 treatment 路径仍不可执行；GT participant/role/字段隔离没有真实预读视图与来源证明；reference support 对象格式最初不匹配；没有 OS 级资源硬限/完整 wall-time 及崩溃审计；Stage B 等价实现完全缺失。局部补丁新增了 raw-relative 校验、role/cache identity 注册、support identity 映射和 GT pre-open scope hash 校验，但这些补丁尚未独立复审，不能标作问题已解除。

因此当前准入结论不是“可批 Stage A”或“可批 A+B”，而是完整 A+B 卡不可签发。准确的逐项输入权限/哈希、读取范围、实现复审、stage 顺序、资源门及调用上限见设计文档新增表。本轮既没有实验 artifact 的读取许可，也没有任何实验执行许可；三个精确输出路径经 Test-Path -LiteralPath 检查均为空，study 输出、账本和锁均未创建。

优先待用户提供/批准的材料：
1. 只读检查精确的 A1/A2 registry 和 105 role 输入登记投影的路径/hash/字段/role/global-ID 绑定；授权仍须排除 raw sensor、原始 metadata、official test 和 external data。
2. 分别批准生成隔离的A2 reference视图和按阶段、role、participant预限定的GT视图；原来源七字段只是上限，训练或评价消费者各只能见共同五字段加该阶段唯一资格，共六字段。给出view路径/hash/生成方法与许可，并先独立审阅视图。不得由study读取完整旧candidate行或完整GT后再过滤。
3. 提供并授权静态检查 A2-004 历史配置、标签、模型、matcher/evaluator 的精确身份/路径/hash；对新 Stage B adapter 与 OS 资源及崩溃处理补实现并独立复审。
4. 确认或改写 design §5 全部资源数字和公式，并在首次重建前对 A+B 全部输入与两阶段预算一并授权。

未完成以上各项前，不运行测试、候选重建/计数、fit/predict、decode/evaluate、audit/run，也不创建 study 输出/账本/锁。Route3 v1-003 保持既有合法 COMPLETE、四门 FAIL，本次不重跑。
 
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

## 2026-09-28 准入语义漂移修订

本次在既有三份路线二文档中核对原§4/§5与新增准入卡，发现并修正三处会改变入场判定的P1口径漂移：`D_A`沿用Stage A末**当前**占盘，Stage A峰值另受2GiB硬线；`S`仅为25个held-out预测批次的总行数，四个OOF训练role加held-out的每周期最大行数属于`M`；`MECHANISM_NOT_SUPPORTED`只按处理与参考**区间多重集**全同判定，support差异仅作完整性检查。原eligibility的七字段是来源读取上限，阶段消费者视图为共同五字段加单一训练或评价资格的六字段，评价视图仍须在相应预测冻结后开放。上述更正不改预算数字、调用上限或已列P1实现阻断；这些文字更正已通过独立只读文档复审；资源数字仍待负责人确认，执行实现与实验授权仍未闭合，路线二保持`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`。

## 2026-09-28 整合后的当前证据与准入结论

下述结果取代本审阅中更早的“来源/投影尚未生成”及旧源码阻断描述；历史记录保留。只使用获准的派生G1 eligibility、冻结role graph、已登记A1/A2派生源。G1共有281条源事件、43名源参与者；41名role-graph参与者中40名有源事件、1名无源事件；264条事件位于role graph内，17条位于图外且全部两阶段不eligible。training和evaluation eligible identity集合相等，各234条。修订后的投影语义保留源 census、原标签和图内不eligible行，仅按冻结role participant scope生成物理GT；外层评价denominator为234。

新登记 `artifacts/route2-candidate-overlap-v1-001-source-registration.json` SHA-256=`e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`，105 score、1,127 cache、105 reference路径/hash/role/global-ID来源审阅PASS，0个绑定或hash错误；审阅ID记录为`review_g1_projection:source-registration:e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`。物理视图manifest SHA-256=`ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`，635/635文件hash、10,842,725行通过，候选support/global-ID及110份六字段GT scope/release检查通过；外部审阅引用为`review_g1_projection:physical-views:ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`。但两个artifact仍保持`PREPARED_UNREVIEWED`，projection manifest的`independent_review_id`为null，登记审阅不等于授权。精确study目录、budget ledger、lock目前均不存在。

当前源码的独立静态复审通过G1/GT阶段隔离、role lease、Stage A顺序和Stage B预算算术。A2-004已审阅的配置/代码部件、特征、标签规则、HGB、nested选择/解码/评价及25/25/65/21调用数静态一致；完整运行期A2 audit/role-digests/source-registration/projection绑定仍未验证，历史label prejoin与`metrics.py` IoU内核未在本次范围内审阅。`budget.py`的正整数/布尔门及候选收据类型校验已加严并复审PASS。

未闭合P1：隔离包没有具体OS hard-limit controller；`BudgetGuard.finalize`在terminal append/fsync/close前记录elapsed，墙钟证据漏掉终态持久化。执行准入身份仍需不可伪造地绑定登记、projection、A2审计身份和独立审阅。Stage B估算式检查PASS但资源限额实际强制未验证。因此不能签发Stage A或A+B授权，也不能自动退为Stage A-only。

待另行提交的完整A+B提案保持：105个`reference_300s`全部成功后，执行105个`strict_overlap`；参考失败即停，全体interval multiset无变化则`MECHANISM_NOT_SUPPORTED`并在verifier前停；仅在候选区间变化及全部门通过时进入一次固定5×4 nested Stage B。预算提案为Stage A/全程/fit wall `1,200/3,600/900s`，RSS `min(4GiB, 3/5初始可用RAM)`，Stage A/全程disk `2/4GiB`、同卷启动free disk≥8GiB、workers≤2；Stage B使用`D_A + 3×(B+232N+8S)+268435456 ≤ 4294967296`及`536870912+6×232M ≤ frozen RSS ceiling`。最多25 fit、25 predict、65 decode、21 evaluator；无重试、续跑或Stage A-only降级。数值须负责人确认或改写，全部输入与A+B两阶段额度须首次重建前一并批准。

结论仍为 **INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED**。可以在新对话提交这份A+B提案并继续关闭阻断；当前证据不能直接申请执行/开始实验。Route3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑。

## 2026-09-28 OS控制器预检：需要重设计执行后端

主机是Windows 11 Home build 26200，当前进程非管理员，无Docker、FSRM或Hyper-V管理命令。Microsoft Job Object限制的是job commit memory和active processes；NTFS quota按volume/user配置，均不能直接覆盖现有Route2进程树RSS、worker task和study目录配额。WSL2 Ubuntu-22.04具systemd/cgroup v2，但Windows native包当前没有WSL执行桥。

为区分环境能力与Route2实验，本轮仅运行无数据系统探针：WSL transient service的cgroup实际显示memory 64MiB、pids 4、CPU quota 200%；500ms `RuntimeMaxSec`使sleep进程终止，但报告service runtime为750ms；64MiB ext4 loopback在写超容量时返回`ENOSPC`。探针无Route2输入，临时镜像已卸载/删除、unit inactive。WSL Python 3.10.12缺scikit-learn。没有更改`.wslconfig`、安装软件包、运行项目测试或模型。

结果足以确认WSL提供可组合的资源控制原语，不足以认证一个Route2 controller。主要残项为：将预算覆盖与输出、ledger、lock硬quota集成到同一OS隔离运行；从外层invocation起计并在terminal fsync/close后出具wall receipt；为A1/A2/物理视图与runtime approval绑定精确hash；完成WSL路径/依赖适配并独立复审。runtime超时探针还显示timer与进程终止存在调度延迟，实际wall硬线须使用保守stop cushion并由外层单调时钟收尾核验。

**Preflight recommendation: REDESIGN。** 完整A+B协议和输入申请草案已写入设计文档，但当前只达到`NOT_READY_FOR_EXECUTION`。下一步需要确认执行后端/输出路径合同：采用WSL-native隔离volume（其数据以WSL路径访问，并适配Route2路径代码），或提供外部已配置的Linux硬限runner。不得把现有Windows native静态审阅当作真实controller通过；不启动Stage A-only或A+B。Route3 v1-003状态保持不变。

## 2026-09-28 整合后修订：WSL后端及路线二执行方案

本节是**当前最新决定**，取代上一节“后端待二选一”的下一步描述；保留旧预检记录作为历史。选用**WSL2 Ubuntu-22.04原生runner + systemd/cgroup v2 + study专用ext4 loop隔离输出卷**作为后续实现路线；输出、外置账本、锁、日志、临时及原子写文件共用一卷。Windows仅在终态关闭并只读后经`\\wsl.localhost\Ubuntu-22.04\...`审阅，不在运行中同步到原工作树`artifacts/`。外部硬限Linux runner是WSL不能证明准入条件时另行提交的后备方案，不是自动执行分支。具体路径、阶段扩容、只读输入映射和阻断见[设计文档最新节](../superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md)与[执行计划](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md)。

| 层级 | 当前证据允许的判定 | 明确不成立的判定 |
|---|---|---|
| 准备视图 | 来源登记105 score/1,127 cache/105 reference、物理视图635/635 hash及10,842,725行获外部只读PASS；准备工作完成 | 两产物自身仍`PREPARED_UNREVIEWED`、manifest `independent_review_id=null`，外部PASS不是批准 |
| A+B授权 | 只有科学协议和条件申请草案；本节选择后端/路径设计 | 没有负责人确认完整资源预算、路径合同及明确A+B实验授权 |
| Stage A/B运行 | 只有无数据WSL原语探针；study输出/ledger/lock尚未创建 | Stage A和Stage B均未合法启动、未消费任何调用额度 |
| 路线二结果 | A2-004保存结果仅作历史对照 | 没有路线二合法候选/模型/评价结果，不能把Route3结果或准备视图充作路线二结果 |

**资源与实现仍为P1阻断。** 64 MiB loop写满仅证明单容量原语；Stage A 2 GiB与全程4 GiB须在**同一卷**先以2 GiB文件系统硬限运行，且只有无标签Stage A及预冻结入场式通过并持久化后才在线扩容至4 GiB。本机扩容/失败回滚、全部写位置及运行中Windows UNC不能改写证据尚未验证。2 GiB卷不可能同时满足原字面“同卷启动free≥8 GiB”；拟改为创建前WSL backing filesystem及其`ext4.vhdx`所在Windows实体卷**两层**free各≥8 GiB，需负责人将此预算解释一并批准。`MemoryMax`、`TasksMax`、`CPUQuota`与原RSS/计算worker指标并不等价，特权supervisor、hash/resize helper和worker须纳入同一计费范围，或另行批准同等强制计费。`RuntimeMaxSec`在500 ms探针晚于边界终止，且不适用于`Type=oneshot`；外层单调计时、提前停止余量、terminal fsync/close后wall receipt及receipt fsync后的截止核验仍未实现。

**输入与等价仍为P1阻断。** 现有Windows路径登记字节/hash保留，新增经独立复审的逐精确文件只读映射，stage/role/phase限制输入可见性；不能把Windows路径简单替换成`/mnt/e`，也不能在Stage A暴露GT。每outer四个inner held-out角色×三阈值的12份预测全部冻结后才开放inner评价GT，outer预测冻结后才开放其评价GT，phase退出撤销视图并释放truth。当前包中的`PureWindowsPath`/drive断言及`gt_provider`的study同级输入断言须适配。A2 audit-ready/role-digests、来源登记、投影manifest元数据、G1及预算/runner/依赖/Stage B adapter须在启动绑定**已审阅身份digest与隔离元数据**；若A2/G1原文件混有GT/标签/资格，Stage A不得为重算hash打开它们。Stage A可见非GT文件实际hash启动核，GT物理文件实际hash只在各自release后、首次语义读取前核，不能启动时预读110份GT。历史label-prejoin和`metrics.py` IoU内核尚需独立审阅。Linux依赖只有下限，WSL缺scikit-learn。所有这些完成并经独立实现复审前，`FrozenAdmission=None`的拒绝态不得解除。

**最小可审阅但尚不可执行的完整A+B卡：**研究ID仍为`route2-candidate-overlap-v1-001`；首次候选重建前一次批准原§4科学协议、精确输入/映射、阶段GT、完整Stage A+B、controller与预算。先105个300 s参考全部复现，再105个严格重叠处理；interval multiset全同则`MECHANISM_NOT_SUPPORTED`在fit前停。差异且所有门通过后才进入固定5×4 nested Stage B，0 candidate scorer fit/predict，至多25 verifier fit、25预测、65 decoder、21 evaluator；无自动重试、续跑或Stage A-only降级。原1,200/3,600/900 s、RSS、2/4 GiB、free≥8 GiB、worker≤2及`N/M/S/B/D_A`式仅是待负责人逐项确认的支出政策。当前`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`，后端选择不等于A+B授权、合法运行或合法结果。

路线1仍是标注/接口合约资料审查。路线3 v1-003合法`COMPLETE`且四门`FAIL`，不重跑，也不将该精确逐候选目标的失败外推到整个事件中心架构。只有用户提供合法路线二结果后，再依据其误差证据讨论候选几何/输出约束、低容量边界/联合事件输出、连续时序信息增量各自的**一个**最小验证；严格重叠机制已在路线二，不换名重复，三个方向均不自动启动。

## 2026-09-29 整合后修订：本机取证与独立实现复审（最新状态）

本节取代上文“本机2→4 GiB尚未验证”“Linux依赖缺少”及“原始probe仅有转录字段”的过时状态，保留其历史文字供审计。工作树仍为`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。独立审阅者检查了当前Route2代码、历史A1/A2对应实现、三组**无项目数据**定向合成测试、WSL三份完整原始OS探针回执和Linux依赖锁；没有读取真实score/cache/GT，没有运行Stage A/B或A2/Route3重跑，没有对项目数据fit或评价。合成测试确曾调用历史评价函数，不能把它称为合法路线二评价。源码仍在修订，任何hash须以最终冻结版本重算。复审结论为**部分准备证据可核，完整协议与执行准入FAIL**，不能签发`EnforcementReceipt`或`FrozenAdmission`。

| 必须分开的状态 | 当前事实 |
|---|---|
| 准备视图 | 来源登记`e6f03b...1853`、投影manifest`ad85c0...fc5ad`已物理生成并由此前独立只读复核，但两产物仍`PREPARED_UNREVIEWED`、manifest正式review ID为null；外部PASS没有写入正式批准清单 |
| A+B授权 | 未有绑定完整输入、预算、代码/依赖、路径、controller及独立复审ID的负责人批准；`FROZEN_ADMISSION=None` |
| Stage A/B合法运行 | 未创建正式WSL study镜像、mount、ledger或lock；105参考/105处理、25/25/65/21额度均未消费；Stage A-only也未获授权 |
| 合法路线二结果 | 无。scratch卷写满、合成标签/指标测试和Linux依赖安装均不是路线二科学结果 |

**已验证的准备证据：**本机Ubuntu-22.04 WSL2的同一scratch ext4卷在≤2 GiB与在线扩至≤4 GiB后分别以`ENOSPC`拒绝超额写入，前后同mount ID、设备和UUID；三份重复探针原始JSON见[磁盘](../evidence/2026-09-29-route2-wsl-disk-probe-raw.json)、[cgroup](../evidence/2026-09-29-route2-wsl-cgroup-probe-raw.json)、[墙钟](../evidence/2026-09-29-route2-wsl-wall-probe-raw.json)，SHA-256分别为`a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939`、`7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9`、`302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c`；独立复核了JSON hash/字段，scratch已清理，原“仅转录”P2已关闭。两层preflight证实WSL backing和VHDX所在C:实体卷当时均≥8 GiB，不能替代正式创建前实时检查。cgroup合成第三task及超额VMS被拒；wall合成缺失/迟到receipt被拒，但持久外部完成事件未证明。Linux[13-wheel锁](../../requirements/route2-linux-cp310.lock)和[身份清单](../../requirements/route2-linux-cp310.identity.json)已产生，13/13 wheel hash、离线安装、`pip check`和关键import通过；证据见[Linux依赖记录](../evidence/2026-09-29-route2-linux-dependency-runtime.md)。这些都是**能力/准备**证据，不是正式controller或跨平台数值等价PASS。

**独立复审仍列P1：**

1. `wsl_controller.py`/Windows脚本只暴露preflight和scratch probe，没有真实特权`ResourceEnforcer`或`PhaseRunner`。`budget.py`虽新增pre-create双层free时序、正式镜像path/dev/inode、loop设备、ext4 UUID、mount ID/device/容量和2→4门字段，但不存在能从Linux supervisor入口到terminal/receipt结束持续执行它们的可信控制器。
2. Stage A固定一个`ExactPathMap`对象却需要顺序打开105个role；当前active receipt只允许一个role且没有controller证明的旧FD/挂载撤销及下一role原子轮换。Stage B的短寿命phase接口还没有真实只读单GT bind、进程退出/FD关闭/撤销收据；Python receipt和代码路径检查不能代替OS物理隔离。源Windows文件读取期间的不变性也未证明。
3. worker在`study_root`之外的`/tmp`、`/var/tmp`、`/dev/shm`、HOME/XDG、字节码、joblib/sklearn缓存、core dump、phase IPC和stdout/stderr等写去向未受正式同卷硬限审计。controller的loop image/VHDX分配、systemd journal和外层wall锚本来位于study卷外，须以可信控制层例外逐路径/峰值计费并由负责人批准，不能笼统称“所有写同卷”。全study父cgroup/`RLIMIT_AS`继承、supervisor/helper/worker拓扑和原进程树RSS/compute worker≤2的强制对应没有真实依赖运行证明；`CPUQuota=200%`不可代替worker数。
4. 没有从Linux supervisor第一单调时钟样本至terminal ledger关闭**以后**的持久外部墙钟验收链。fake receipt的实时正反例并未证明最后fsync完成及服务退出的可信持久锚点、60s停止余量或崩溃不可续跑。`terminal()`现拒绝仍活动GT release，故PhaseRunner异常无撤销收据时会fail closed、不会接纳终态，但异常teardown本身仍未实现。
5. HMAC修订让inner仅返阈值标量，training/outer跨进程GT ID只返承诺；但真实controller尚未生成、封存、只向GT child分发并销毁同一私钥。原要求的matched GT集合变化还需用同key把获准历史control ID变成承诺后比较，不能只交treatment承诺。21个evaluator reservation中仅前20次直接调用历史`evaluate_participants`，第21项为逐participant五折代数归并；100组合成全字段等价只证明测试范围，负责人须接受经审阅的等价替代或改为真实第21次调用，也不证明Linux历史A2数值完全一致。
6. 新`runtime_identity.py`已将来源登记、投影manifest、A2 audit-ready/role-digests、G1、Linux lock/ABI与**拟议的**canonical独立审阅attestation及允许的metadata-only bind关联，`run_ab`在Stage A/B适配器读输入前检查；当前没有该attestation、controller只读bind和不可变安装文件。完整Route2执行闭包、入口脚本及venv实际文件没有只读快照/hash收据，`stage_b.py`仍从活动工作树核A2 config/源码和GT registry，在WSL隔离方案下不能作为运行期身份。Stage A不得为了哈希原混合G1/A2文件而读GT；110个GT文件仍须各自release后、首次语义读取前核实际hash。历史A2 AUDIT_READY绑定了A2 audit源码和role-digests；`metrics.py`/`a1/metrics.py`的历史运行时字节身份与Linux Python 3.10.12相对Windows 3.10.11的数值等价仍需补证。
7. 当前Windows账号能直接以WSL root进入该发行版，且可提升为本机管理员；原“运行中Windows默认用户不能看未到期GT/改写ledger”的host边界不能在同用户WSL证明。需负责人明确把Windows host owner列为可信并重审worker边界，或改用独立受控Linux宿主；普通本机新账号本身不消除此项。

**已修的代码闸与验证范围：**持久账本要求Stage B入场及同卷扩容事件先于GT release，fresh child可重建ledger hash链、12/1预测receipt及预测文件hash；活跃GT release阻止terminal。outer GT ID以控制器私钥HMAC的接口替代原始ID，空训练候选归为`VERIFIER_DATA_INSUFFICIENT`。三组定向无数据合成测试（budget、phase protocol、runtime identity）在最终静态复审版共**21项PASS**；它们不模拟完整OS runner。独立复审还覆盖历史A1 `label_candidates`同participant严格`IoU>0.25`、`metrics.py` IoU/匹配严格`>`及A2按`(role_id,candidate_id)`预分离标签后join；这项**源码规则静态审阅可关闭**，真实历史artifact/label身份和跨OS数值等价仍未证明。完整实现复审结论仍为**FAIL**，不能把合成PASS当作正式通过收据。

**最小可审阅待授权提案仍只有一张：**`route2-candidate-overlap-v1-001`一次完整A+B，105个300s reference全部通过后105个strict positive-duration overlap treatment，Stage A零GT和零candidate-model fit/predict；全同以`MECHANISM_NOT_SUPPORTED`在fit前停。仅在机制变化且全部输入/身份/资源门通过时入固定5×4 Stage B，最多25 fit、25预测、65 decoder、21 evaluator额度；其中第21项的直接调用或等价归并须先裁决，无重试/续跑。具体卡还须冻结六种非`COMPLETE`停机分类及`COMPLETE`、`1200/3600/900s`与60s停止余量、RSS公式/worker≤2、2/4 GiB及承载镜像/系统写例外是否计费、`N/M/S/B/D_A`式、创建前**WSL backing与VHDX所在Windows实体卷分别≥8 GiB**、terminal关闭后外部wall锚、host信任边界、精确输入根/study mount/image/ledger/lock路径与卷身份、Linux 13-wheel/Python ABI、完整源码/依赖/controller hash和独立复审ID。上述均需负责人逐项确认，完整独立实现复审PASS后另行明确批准。当前`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`。路线3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑；gap=0已由路线二覆盖，合法路线二结果到来前不讨论并启动三个方向。


## 2026-09-29 整合后修订：负责人决定、准备快照与授权卡（追加最新状态）

本节追加在既有整合审阅后；不改写历史判断。唯一可审的授权材料为[一次完整 A+B 条件授权卡](2026-09-29-route2-ab-authorization-card.md)，状态为 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。

### 已关闭的负责人解释与准备证据

- 负责人明确 Windows 宿主账号所有者列为可信主体。该项关闭威胁模型的“宿主所有者是否可信”政策选择；不等于研究 worker OS 隔离或 controller 收据通过。
- 负责人明确正式镜像创建前，两项 8 GiB 下限分别适用于 WSL backing filesystem 与 ext4.vhdx 所在 Windows 实体卷，不合并。新增准备样本分别为 1,014,082,801,664 B（/dev/sdd、mount ID 80）与 28,729,638,912 B（C:，volume GUID \\?\Volume{5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b}）。这不是未来同一 invocation 的正式建镜像前收据。
- 源码/venv 的 root-owned 准备快照和 ABI 身份已经生成。完整摘要及 hash 见[快照与双层预检记录](../evidence/2026-09-29-route2-source-runtime-snapshot-and-two-layer-preflight.json)，SHA-256 为 506e23659875e4520a1cbff4b1eb8fbe9e38d83f0dbd93d9fa2b6d71262c061b。源码 90 files / 1,210,019 B，manifest SHA-256 03b6cf9d1807bc0520bc00bcf83c27d05e6ed88da615e4895b897a235ffb9e90；runtime 11,330 files / 348,519,927 B，manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e。准备快照还没有经正式 controller 只读挂载或独立全实现复审。
- 新 namespace 检查记录 SHA-256 c5a0876532e00b06e38e362d03d4766b8d240e5807005c3ad3b7c72becf81a40；正式 image、study volume、study root、ledger 和 lock 均不存在。准备 evidence 与历史 2→4 GiB、cgroup、wall、readonly bind 和 QPC raw hash 与能力边界逐项列在授权卡及[原始 probe 目录](../evidence/2026-09-29-route2-wsl-synthetic-os-probes.md)。所有这些都没有用项目数据或 GT。
- 精确 Route2 定向合成测试为 41 passed / 2.96 s。曾有一次 PowerShell glob 误匹配触发整库测试：382 passed、2 failed（test_004_supervisor_survives_high_frequency_atomic_worker_writes、test_fit_compositions_match_the_nested_role_graph）；tests/test_route3_workflow.py 单元测试也被该次收集包含。这不是 Route3 v1-003 实验运行；Route3 未重跑。该整库测试结果不升级 Route2 准入。

### 独立复审状态与剩余阻断

当前完整实现/跨 OS 数值等价独立复审 ID 为 NOT_ISSUED；此前可用独立 reviewer task 没有产生审阅结果，Claude CLI 因未登录不能执行审阅。来源登记和物理投影的既有窄范围外部引用仍仅为：
- review_g1_projection:source-registration:e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853；
- review_g1_projection:physical-views:ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad。

对应来源与投影仍标 PREPARED_UNREVIEWED；projection manifest 的正式 independent_review_id 仍为 null。这些ID不构成完整 Route2 实现审阅或 A+B 批准。

**仍阻止申请获批的 P1：**
1. 没有正式特权 supervisor / ResourceEnforcer / PhaseRunner，未从 invocation 第一个 monotonic sample 执行正式双层磁盘门、镜像创建、全程限额到 terminal close。
2. 没有正式 2 GiB Stage A 镜像与 ledger 门控的同一卷 2→4 GiB 转换。
3. 没有 Stage A 逐 role 只读挂载原子轮换，也没有每个 Stage B training/inner/outer GT view 的实际发布、phase worker 退出、FD 关闭、异常撤销和 mount receipt。
4. worker 完整写路径未受 OS 同卷硬限；镜像/VHDX、journal、wall receipt 等可信控制层卷外写入缺路径身份与峰值计费。
5. 没有全 study 父 cgroup/RLIMIT_AS 的 RSS 强制证明或 worker≤2 的强制收据。
6. 没有 terminal ledger append/fsync/close 之后的持久外部 wall receipt、receipt fsync 后截止核验、service exit 观察和崩溃不可续跑验收。
7. path-map、A2 audit-ready/role-digests、G1、registration、projection、运行快照和批准元数据没有绑到不可伪造的只读运行期准入；role path-map 文件/hash 尚不存在，stage_b.py 仍关联活动工作树。
8. 完整 A+B 历史协议和 Linux/Windows 数值等价未由独立 reviewer PASS；第21 evaluator pooled reduction 的等价语义未裁决；HMAC key 生命周期与 matched GT-set change 诊断未闭合。
9. 只读源码/依赖 snapshot 不是 formal read-only runtime mount，也无 independent attestation。
10. 完整实现独立复审没有审阅ID，不能用文档自审或无数据测试替代。

**仍待负责人的 P2/预算裁决：**除已确认的宿主所有者信任与双层各≥8 GiB外，1,200/3,600/900 s、60 s stop cushion、RSS/worker 指标及 2/4 GiB 预算、N/M/S/B/D_A 公式，以及承载 image、VHDX、system journal、外部 wall 锚的计费范围尚未逐项批准。正式创建前两层 free-space 实时检查本身仍是实现 P1。

四个状态继续分开：准备产物 PREPARED_UNREVIEWED；FROZEN_ADMISSION=None；无合法 Stage A/B；无合法路线二结果。当前不运行 Stage A-only/A+B，不打开 110 个 GT 视图，不重跑 Route3 v1-003，不启动架构方向。

## 2026-09-29 整合后修订：独立全实现复审、快照校正与申请复核（最新）

本段覆盖本日新增的无项目数据取证及一次独立静态复审；保留以上历史记录，不扩大读取或运行授权。唯一研究ID仍为 `route2-candidate-overlap-v1-001`。负责人已确认 Windows 宿主账号所有者为可信主体，并确认正式镜像创建前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷各自至少有 8 GiB；两项解释已关闭，但正式启动时的同次 invocation 实时检查仍未执行。

### 独立复审结论

独立只读复审记录号 `route2-ab-full-implementation-review-2026-09-29-FAIL-001`：**FAIL / NOT_APPROVAL_READY**。审阅者读取了 Route2 实现、wrapper、测试、设计、执行计划、授权卡、既有review、授权Prompt及指定无数据证据；未运行测试或实验，未读取项目输入、历史分数/cache内容、项目数据或任何 GT 字节/视图。该编号是本次 FAIL 记录的引用，不是 `INDEPENDENT_REVIEW_PASS` attestation，不授予运行权限。

复审发现的未关闭 P1：

1. **没有正式特权 supervisor / `ResourceEnforcer`。** 当前接口仍是 `Protocol`，WSL 模块目前提供原语探针。2→4 GiB 探针没有执行正式105+105、差异判断、`N/M/S/B/D_A`投影及持久 ledger gate；controller image、VHDX、journal、外部 wall receipt 的卷外写入尚未按实际卷、长度/峰值和预算裁决纳入可信账本。
2. **没有 OS 级逐 role / phase 控制器。** `RoleMountController` 和 `PhaseRunner` 仍是抽象接口。单文件只读 bind 和 Python lease sequencing 不能证明真实逐 role 轮换、旧 worker/FD 关闭、GT release 只在相应预测冻结后发生，或异常时 child 退出与只读 mount 撤销。不得提前打开110个 GT 视图。
3. **全 study RSS / worker 约束未证明。** live cgroup receipt 只覆盖合成 service；现无 supervisor、hash/resize helper 与 workers 共用的正式父 cgroup，也没有 `hard_rss` / `hard_worker_threads` 的全 study 收据。
4. **terminal 后 QPC 接受流程未接入正式 runner。** Windows QPC 合成探针证明 terminal close、service inactive、terminal hash 核对与持久 receipt 的顺序能力；`BudgetGuard.finalize()` 仍未通过正式外层 observer 复核并接受 receipt。60秒停止余量仍是未确认候选值，crash / deadline / 缺 receipt 的正式拒绝与不可续跑流程尚未实现。
5. **冻结 admission 的源码自哈希问题未解决。** `FrozenAdmission` pins 若被写回其自身 source snapshot 中的 `contracts.py`，会改变其所声明的 source manifest digest。保持 `FROZEN_ADMISSION=None` 是当前正确拒绝态；未来必须由 source tree 之外的 controller-sealed admission artifact 和独立的 bootstrap/trust binding 承载批准 pins，不能用编辑后再重算同一 manifest 的循环路径。
6. **只读执行闭包仍不完整。** 本日修正了 Linux identity 的 venv 路径及 CPython executable path，准备 source 与 venv 快照逐文件 manifest 校验通过；`stage_b.py` 已从冻结 source root 读取历史配置/代码，旧review中“仍从活动工作树读配置/代码”的说法已过期。正式 controller-owned read-only mount 仍未建立；Linux system library / 标准库的内容闭包也未钉定，运行期投影、身份和 approval 尚未由可信 controller 绑定。
7. **完整 A+B / 跨 OS 数值等价仍未通过。** 新增的 Windows 3.10.11 与 Linux 3.10.12 纯内存合成探针在 16D、26D、HGB probability、decoder、event metrics 和 pooled reduction 上得到相同 SHA；见下节。它不读取真实 A2-004/Route2 输入，不能证明完整真实数据协议数值等价、所有数值边界或执行闭包。
8. **control matched-GT 诊断和 HMAC key lifecycle 缺失。** 当前 Stage B 只回传 treatment 的 matched-GT commitments；没有历史 control commitments 与新增/丢失集合比较。生产 controller 尚未创建、封存、仅分发给 GT child 并销毁同一 HMAC key。
9. **没有可信 PASS issuer 或负责人批准。** 精确 approval/readiness checks 是 fail-closed，不应描述为任意字符串可绕过；但正式 issuer、canonical attestation 和完整 controller receipt 尚不存在。完整实现 `INDEPENDENT_REVIEW_PASS` ID 与负责人 A+B approval ID 均为 `NOT_ISSUED`。

### 本日关闭项与新增无数据证据

- **P2 role-mount lock leak 已关闭。** 独立复核记录号 `route2-path-map-revocation-lock-2026-09-29-CLOSED-001` 检查了 `path_map.py` 外层无条件 `finally` 和跨线程锁回归。回归测试曾以预期错误“failed revocation leaked the role-mount lock”失败；修复后通过。最新定向 Route2 synthetic suite 为 **42 passed in 4.60s**。这只关闭 Python `RLock` 泄漏；OS 级撤销及异常 worker teardown 仍是上项 P1。
- **Linux prepared identity 和 ABI 已重新核对。** 当前 identity JSON SHA-256 `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`，Linux executable path `/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv/bin/python`，binary SHA-256 `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`，Python `3.10.12`，ABI `cpython-310-x86_64-linux-gnu`，glibc `2.35`，lock `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`。`pip check` 为 `No broken requirements found.`
- **准备 source revision 已新建且逐文件验证。** `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260929c/source` 为 root-owned、mode `0555`，90 files / 1,232,085 B，manifest SHA-256 `9c0bd2c7218a4fbadac6d9254e4ce48aef3586ce84a12e518767a1da14fd90c5`。安装 venv 快照仍为 11,330 files / 348,519,927 B，manifest SHA-256 `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`。准备树可验证；正式只读 mount 未证明。证据：[prepared source/runtime revision](../evidence/2026-09-29-route2-prepared-source-runtime-revision-20260929c.json)，SHA-256 `ed13f420b610f1eeb30759d962d15eea4b736b42a623ba367dd6e1cecff2715d`。
- **worker 写路径 alias 的 scratch-loop 能力已取证。** SHA-256 `7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca` 的无项目数据 receipt 证明 probe 中 `/tmp`、`/var/tmp`、HOME/cache 与 stdout/stderr 指向同一 scratch ext4 loop。它没有证明正式 study controller 的所有写路径，或计入 image/VHDX/journal/QPC 外部写入。
- **合成跨 OS 输出一致。** [cross-OS synthetic receipt](../evidence/2026-09-29-route2-cross-os-synthetic-equivalence.json)，SHA-256 `6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15`；所有指定数字输出摘要完全相同。能力范围止于该内存合成用例。
- **正式 study namespace 仍不存在。** 新鲜检查中的 image、volume、root、ledger、lock 均 absent；`FROZEN_ADMISSION=None`、GT views opened=0。此对现状的检查不等于 future approved controller gate。

### pooled 第21次 reservation 的协议裁决

本申请将“第21次 pooled evaluator”明确定义为**一次不再读取 GT 的 pooled aggregation reservation**：15次 inner threshold evaluator phases + 5次 outer evaluator phases + 1次 pooled metric aggregation，共21次 evaluator reservations；其中只有前20次打开阶段限定的GT worker view。第21项仅聚合五个 participant-disjoint outer fold 已接受的 `ParticipantMetrics`，不得再打开新 pooled GT 视图。这样保留全体 held-out participant 上 pooled TP/FP/FN/F1 的科学量，同时避免在5个 outer GT view已逐次撤销后引入新的全量评价视图。

源码将每participant matcher结果作为可加总单元；participant不跨outer fold，因此 pooled计数由五折结果归并。新合成探针对41个合成participant直接调用历史 evaluator 后与五折归并结果比较，dataclass相等且跨OS hash一致。该裁决现在写进唯一 A+B 卡，供负责人批准时一并审阅；它不是真实A+B等价或现有运行授权。停止分类继续固定为 `REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`，仅完整五折为 `COMPLETE`。

### 当前申请状态

当前唯一申请卡仍为 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`；负责人 A+B approval ID `NOT_ISSUED`，`FROZEN_ADMISSION=None`。虽已解决两项负责人解释、修复 P2 lock leak、记录 pooled reservation 定义及纯合成数值一致性，正式 privileged controller、stage-gated input mount、全 study硬限、terminal 后QPC集成、controller-sealed admission、control matched-GT诊断、完整真实协议等价与其独立 PASS 仍缺。其他资源支出数字及卷外写入预算仍为待裁决提案。

本轮没有创建正式研究namespace、没有 Stage A-only 或 A+B 运行、没有提前打开110个GT视图，没有重跑 Route3 v1-003，也没有启动三个架构方向。负责人另行明确批准该具体卡之前维持 `NOT_EXPERIMENT_AUTHORIZED`。

## 2026-09-30 source revision 与 snapshot-path 修订

本节只记录本轮实现与准备身份变化；**不撤销**`route2-ab-full-implementation-review-2026-09-29-FAIL-001`。完整正式 controller、phase worker 与 GT 隔离仍没有 PASS。

- 更新了`build_study_access_policy`：其 immutable source/runtime root 校验此前只允许`/opt/route2/snapshots/<study-id>/source`，会拒绝已冻结申请拟用的版本化source路径。现在允许 canonical leaf 或严格格式`revision-YYYYMMDD[a-z0-9]{1,8}`下的对应`source`/`venv` leaf；study、leaf、snapshot parent 和 revision 格式仍必须精确匹配。新增回归先因旧策略失败，再通过；当前 linux_enforcement.py SHA-256 为`22db48d59848d19928199a0eb4511b861a7d7ccd3ac0f21ac7d675567005af47`。定向 suite 43 passed in 4.29s。
- 依既有90文件manifest白名单，从active worktree重新生成 root-owned、mode 0555 的 source revision `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930a/source`；90 files / 1,233,457 B，manifest SHA-256 `d185893bdf5cde2d8d9cdeecfc4e686fe361cd9ca72454ae0783cddb33c64e38`。完整逐文件验证、版本路径策略、Linux ABI、Python identity、venv manifest和`pip check`复核见[2026-09-30 source/runtime evidence](../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930a.json)，SHA-256 `a9abd8f2404abd40d1b2b5b3ed2914dac6f6fea71540c0ab8ae35f10f17ed274`。
- 本次 source revision 变化尚未被完整独立复审；原独立 reviewer 后续复查未形成结果，因此不能声称 revision 20260930a 已通过独立复审。policy path fix 也没有建立 controller-owned read-only mount、RoleMountController/PhaseRunner、正式资源 enforcement 或 Stage A/B 运行身份绑定。
- 仍保持 project data used=false、GT views opened=0、formal study namespace absent、`FROZEN_ADMISSION=None`、`NOT_EXPERIMENT_AUTHORIZED`。P1/P2 清单、预算候选和唯一申请状态以条件卡及执行计划当前状态为准。

## 2026-09-30 准入 seal 合成复核与全实现只读审计

本段记录当前 conversation 对准入 parser 的窄范围复核与一次只读全源码审计。两项都不替代正式完整 review，也没有签发 `INDEPENDENT_REVIEW_PASS` ID。负责人确认 Windows host account owner 属可信主体，且镜像创建前 WSL backing filesystem、VHDX 所在 Windows 实体卷分别独立要求至少 8 GiB；这关闭了两项预算解释歧义，但不关闭实时 gate 或其余预算裁决。

### P2 parser 修订及其证据范围

- 新增 `src/eating_event/route2_candidate_overlap/external_admission.py`：仅解析并验证 canonical、controller-sealed artifact 格式、HMAC与调用方预期 pins；不会建立 issuer/owner/reviewer provenance，不会自行测量 source/runtime，也不写入 `FROZEN_ADMISSION`。`contracts.py` 已改为准确说明 parser 存在但没有可信 production caller/bootstrap；全局继续是 `None`。
- 无项目数据证据见[external admission synthetic evidence](../evidence/2026-09-30-route2-external-admission-seal-synthetic.json)，SHA-256 `00550c19060cfd16c731dfda7aecb6927f37a21127b47f4999498281f2980c64`。该记录绑定 parser SHA-256 `847ecb01ac2da0e169ca47c7fcfa44c29abdc43bfe6f9979559143521eca54a7`、测试 SHA-256 `a6bbe05365f6527a6a242b12225c9ddf2f7f372be3a87e52f4ccedfe9957169b`、prepared source revision `revision-20260930e` / manifest `9234f5cbb186999e4af2f1dcbe4e26269a3ed009effb9c87ab0b8560dfb85cfd`；parser 测试 **10 passed**，当轮定向 Route2 suite **53 passed**。Linux venv 内另行验证 source manifest、Python 3.10.12 / x86_64 / glibc 2.35 / CPython ABI 与 `pip check`；该 venv 未安装 pytest，因此 suite 在当前工作树 Python 环境运行，没有写入冻结 venv。
- `/root/route2_admission_bootstrap_review` 对 parser 和测试作了窄范围独立复核，确认 canonical 序列化 `RecursionError` 被拒绝并关闭该 parser P2；没有正式 review ID。它不是 production admission 或全实现 PASS。

### 当前独立审计和未关闭项

- `/root/route2_ab_full_static_audit` 对完整 A+B 源码、路径/预算/阶段协议及既有合成跨 OS 证据作只读审计；未运行脚本/测试/服务，未读 project input、score/cache/GT，未运行 Route3。该审计没有正式 review ID，也不构成 PASS。A+B 源码的 105 reference 后 105 treatment、reference 失败时 treatment=0、相同 interval multiset 时 fit 前 `MECHANISM_NOT_SUPPORTED`，以及固定 5×4 / 25/25/65/21 计数与第21项 pooled aggregation 语义，与申请卡一致；这些只是源码核对，不是执行证据。
- 既有正式完整 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍为 **FAIL / NOT_APPROVAL_READY**。当前 P1 仍包括：可信 supervisor/bootstrap 与生产准入调用；正式 `ResourceEnforcer` 生命周期和同一 image 的 2→4 GiB ledger gate；真实逐 role 与 GT phase bind/revoke/child-exit 链；所有 worker 写路径及 image/VHDX/journal/wall-anchor 例外账目；全 study parent-cgroup、RSS 与 worker 强制；terminal close 后外部 wall receipt / deadline / crash 验收；A2/G1/registration/projection/runtime/source/path-map/approval 运行期身份绑定；完整 A+B 历史协议及 Windows→Linux 等价的独立 PASS；control matched-GT 诊断和 HMAC key 生命周期。
- 跨 OS 收据只证明指定合成 16D/26D、HGB、decoder、metrics 和 pooled reduction 输出摘要相同；不证明完整历史协议闭包或真实 A+B 等价。 pooled 第21项仍是申请卡中的待批准语义：15 inner + 5 outer + 1 不读 GT 的聚合 reservation。
- P2 文档矛盾：本计划旧清单曾把 host trust 和双层 8 GiB 解释列为待决，现已改为已确认；60 s stop cushion、1,200/3,600/900 s、RSS/worker 定义、2/4 GiB、`N/M/S/B/D_A` 公式和卷外控制写入预算仍未确认。复核中另有一个 Stage A mount-controller 原型正在单独实现与合成测试；在实现、两轮独立审阅与快照刷新完成前不把它列为已关闭 P1。

当前状态仍为 `PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED`。正式研究 namespace 不存在；GT views opened=0；不运行 Stage A-only/A+B，不重跑 Route3 v1-003，不在取得合法 Route2 结果前启动三个架构方向。

## 2026-09-30 整合后修订：h 快照、准入链补强与当前 P1/P2

此节续接本review原有“整合后修订”，旧日期章节保留历史。唯一研究ID route2-candidate-overlap-v1-001。负责人已把Windows宿主账号所有者列为可信主体，并明确正式镜像前WSL backing filesystem与VHDX所在Windows实体卷各自独立至少8,589,934,592 B；解释歧义已关闭，但正式invocation双层实时gate未实现。

当前source准备快照revision-20260930h为98 files / 1,378,752 B，manifest SHA-256 520423b8bdb1372230140fd162ed8d21991593a071374c3899d27160c7cbc7b7，root uid 0、mode 0555；逐项完整校验通过。Linux venv为11,330 files / 348,519,927 B，manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e，root uid 0、mode 0555、完整校验通过；Python 3.10.12、x86_64、glibc 2.35、SOABI cpython-310-x86_64-linux-gnu；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；identity fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f；pip check无broken requirements。完整记录见[revision h source/runtime](../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930h.json)，SHA-256 8a9cfb221895e20315ca0f6dc6a6c18d9e29a61ffc27a26ce6a6c75a17079233。mode 0555与逐文件hash不是kernel只读bind，readonly_mount_proven=false。

新的repo-side pre-import launcher在Route2 bootstrap导入前以系统Python核验受保护配置、source/runtime manifest、路径与hash、mount记录后再exec冻结venv；源码及fail-closed synthetic cases纳入revision h。尚未安装到系统保护路径；root-only config/seal key/systemd unit/service/可信external supervisor不存在。故它没有建立production trust anchor，FROZEN_ADMISSION继续None。

Stage A Linux role mount controller/path-map源码修订绑定canonical manifest bytes/hash与frozen path-map pin，也在直接controller入口强制检查；完整role映射、不同role错序拒绝、duplicate exact mount拒绝、private namespace传播校验、receipt目录fsync、alias尽力revoke与持久failure receipt，以及重复revoke的mountinfo异常都增加合成覆盖。最新定向Route2 synthetic suite 87 passed / 3.90 s，收据为[admission/controller synthetic v2](../evidence/2026-09-30-route2-admission-controller-synthetic-v2.json)，SHA-256 d92d6aadc4f6397776224ee19ce6c65aaca750e9101532d63eea967d86f50d49。限定范围只读复核确认对应源码缺陷和测试缺口已关闭；无正式review ID，不是完整A+B PASS。没有运行真实mount namespace/kernel syscall/service/worker/GT phase。

正式完整review route2-ab-full-implementation-review-2026-09-29-FAIL-001继续FAIL / NOT_APPROVAL_READY。当前未关闭P1：repo launcher无系统安装或外部信任config/key/seal/service；无first-monotonic-sample起始的特权ResourceEnforcer、双层实时≥8GiB门、正式image与同image 2→4GiB ledger门；无真实逐role只读mount/GT phase release/worker child和FD close/revoke；worker全写路径未OS强制、image/backing/VHDX/journal/QPC/receipt例外缺卷身份和峰值账；无full-study cgroup/RSS/worker≤2；无terminal close后的external wall receipt/service exit/cutoff/crash acceptance；无source/runtime/system library/stdlib/input/path-map/A2/G1/registration/projection/approval身份端到端只读绑定；完整A+B真实协议和Windows→Linux数值等价无PASS、control matched-GT diagnostics/HMAC key lifecycle缺失；无完整独立PASS ID或owner approval。正式image/volume/root/ledger/lock均absent，project data=false，GT=0，Stage A/B=false。

P2预算仍需裁决：wall 1,200/3,600/900 s、60 s cushion、RSS min(4GiB,floor(3×首次可用RAM/5))及RSS定义、worker≤2的定义、2/4GiB、D_A + 3×(B+232N+8S)+268,435,456≤4,294,967,296、536,870,912+6×232M≤冻结RSS ceiling、N/M/S/B/D_A冻结语义以及controller/system例外路径卷归属与峰值写入范围。宿主信任和双层各≥8GiB解释已由负责人决定，不再作为待决项；正式创建时同时live测量仍未完成。

原始探针和Linux依赖证据仍只证明各自准备/合成范围：磁盘ENOSPC、cgroup、wall、single readonly bind、live cgroup、Windows QPC、worker alias scratch loop、cross-OS synthetic原始文件及SHA和限制见唯一[授权卡证据表](2026-09-29-route2-ab-authorization-card.md)与[synthetic v2](../evidence/2026-09-30-route2-admission-controller-synthetic-v2.json)；wheel lock、ABI和pip check上下文见[Linux dependency runtime](../evidence/2026-09-29-route2-linux-dependency-runtime.md)。没有一项是正式研究controller receipt。

唯一授权卡已补绑定revision h、输入与路径身份、全部预算候选、探针hash、review refs和停止分类，但状态仍APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；PREPARED_UNREVIEWED，FROZEN_ADMISSION=None。Route3 v1-003合法COMPLETE、四门FAIL且不重跑；gap=0由路线二覆盖；取得合法路线二结果前不启动三个架构方向。不跑Stage A-only/A+B，不提前打开110个GT视图。



## 2026-10-01 整合后修订：revision-q、脱敏准入投影与当前阻断项

本节是当前执行视图，保留此前协议和审阅历史。唯一 study ID 仍为 `route2-candidate-overlap-v1-001`。负责人已确认 Windows 宿主账号所有者是可信主体；正式镜像创建前，WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别至少 8,589,934,592 B。正式 image、volume、root、ledger、lock 均未创建；`FROZEN_ADMISSION=None`。本次只运行无项目数据合成测试，没有读 score/cache、项目数据或 GT，没有 Stage A/B、Route3 重跑或 GT 视图打开。

### 当前可核准备证据

- 当前源码为 `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001q/source`，101 files / 1,537,167 B，manifest SHA-256 `0bd424e05b4307b39de5f142e7edeeb04a0c949d0ffc256a01d84b543bea7e7d`，root uid 0、mode 0555，101/101 文件逐项 hash/size 验证通过。快照纳入 Stage B 要求的 `configs/a2-context-verifier-v1-004.json`，SHA-256 `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`。快照独立核对不包含 `scripts/probe_route2_cross_os_synthetic.py`；跨 OS probe 仍须单独按其旧代码身份解释。
- Linux venv `/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv` 保持 11,330 files / 348,519,927 B，manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`；Ubuntu 22.04 WSL2、Python 3.10.12、x86_64、glibc 2.35、SOABI `cpython-310-x86_64-linux-gnu`，解释器 SHA `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`，lock `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`，identity `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`，`pip check` 通过。准备目录只读权限不是正式 controller-owned RO mount，`readonly_mount_proven=false`。
- [revision-q 准备证据](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001q.json) SHA-256 `45971eb401edec8a2a6ada14a4032fdebdbb4a78b8950f5e6859555e6c108ee2`；[安全准入元数据投影](../evidence/2026-10-01-route2-admission-metadata-projection.json) SHA-256 `a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c`。投影仅含原 registration/projection 的 SHA 与10项身份 hash，不含 eligible-row/GT census/count/record；仍 `PREPARED_UNREVIEWED`，没有独立 metadata attestation 或批准。
- Route2 无项目数据定向 suite：**159 passed / 3.30 s**；不证明任何真实 Linux namespace、worker/service、项目数据处理或科学结果。q 快照有限只读复核核对 101/101、必需 config 与近期修复；没有正式 review ID，也不覆盖完整 controller/A+B。
- 原始能力探针和 Linux 依赖证据保留：磁盘/ENOSPC `a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939`；cgroup `7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9`；wall `302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c`；single RO bind `7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257`；live cgroup `c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096`；Windows QPC `55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c`；worker scratch alias `7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca`；cross-OS synthetic `6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15`。Linux 依赖记录见[2026-09-29-route2-linux-dependency-runtime.md](../evidence/2026-09-29-route2-linux-dependency-runtime.md)。它们是各自窄范围的能力/准备证据，不是 production lifecycle 或完整 A+B PASS。

### 本版关闭的代码缺陷与独立复核边界

源码现在将 Stage B 外层选择阈值数检查为5，并将固定5×4协议的20个 inner role 写入完成回执；同一 4 GiB 镜像允许 ext4 实际容量位于 (2 GiB, 4 GiB]；迟到 completion fsync 的 `INCOMPLETE_RESOURCE` terminal 会保留并绑定已提交 `stage_b_result`；每个 outer fold 记录后释放候选矩阵、scores、预测与 scope 对象；运行前只读安全 metadata projection，不再读取含 GT 派生计数的完整 registration/projection manifest。精确 schema/10个 pin 拒绝其他顶层或嵌套字段，并由 readiness/approval 绑定 path 与 hash。

独立 lifecycle 窄审阅对上述代码缺陷未发现新问题，但无正式 ID。`route2_independent_review` 有限只读核对 revision-q 的完整 manifest 与上述修复，范围内 PASS；没有正式 review ID，不是完整实现 PASS。完整正式复审 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍为 FAIL / NOT_APPROVAL_READY。

### 尚未关闭的 P1

1. 没有安装在受保护系统路径的可信 pre-import launcher、root-only config/seal key、systemd service/unit 与外部 supervisor；`ResourceEnforcer`、`SupervisorOps`、`PhaseRunner` 仍有待接通的 protocol/interface。
2. 没有正式同一 image 的 2→4 GiB resize + durable-ledger gate，也没有从 first monotonic sample 到 terminal close 的特权全链路。
3. Repo mount-controller/path-map 原型不证明真实 private namespace、逐 role RO bind 轮换、单阶段 GT 发布、旧 child/FD 关闭、异常撤销与持久失败回执。不得提前打开 110 个 GT 视图。
4. Worker 的 /tmp、/var/tmp、/dev/shm、HOME/XDG、cache、pyc、core、IPC、stdio 等全部写路径还没有正式 OS 拒绝与计费；controller/image/VHDX、WSL backing、journal、QPC receipt 等卷外路径/卷身份/峰值也未锁定。
5. 没有覆盖 supervisor/helper/worker 的 study-wide parent cgroup、强制 RSS ceiling 与 compute workers≤2。
6. 没有 terminal append/fsync/close 后的持久外部墙钟验收、service exit/cutoff/cgroup-empty 检查或 crash/迟到/missing-receipt 正式闭环。
7. 当前 safe metadata projection 仍未独立复核为 PASS、无 runtime attestation；正式 path-map 仍 `NOT_CREATED`，source/runtime/ABI/system library closure/输入/approval pins 未经可信 controller 在真实只读 mount 中冻结。
8. 完整历史 A+B 与 Windows→Linux 数值等价尚无独立 PASS；cross-OS receipt 仅覆盖窄合成样本，绑定旧 `stage_b.py=a4173593…`，当前 q `stage_b.py=fe6a45eb…`，并非当前完整 5×4 闭包实测。probe 脚本不在 q。control matched-GT additions/loss 诊断与 HMAC key 生命周期仍缺。
9. 没有新的完整实现 `INDEPENDENT_REVIEW_PASS` ID，也没有负责人对具体卡的 A+B approval ID。

### P2 / 预算裁决

负责人尚未批准 Stage A/total/cumulative-fit wall 1,200/3,600/900 s、60 s stop cushion、RSS `min(4 GiB, floor(3×first available RAM/5))`、compute workers≤2、Stage A/total disk 2/4 GiB、Stage B disk `D_A + 3×(B+232N+8S)+268,435,456 ≤ 4,294,967,296`、RSS `536,870,912+6×232M ≤ frozen ceiling`，以及 N/M/S/B/D_A 的实际定义、冻结时点和峰值记账口径。controller/image/VHDX、journal、外部 QPC/seal receipts 的写入 volume 与是否计入 2/4 GiB 均待裁决。已解决且不再重复提问：宿主账号 owner 可信；WSL backing 与 Windows VHDX 实体卷分别独立 ≥8 GiB。正式建镜像前同一 invocation 实时复测仍是 P1。

唯一申请仍是 105 reference 全部成功后才 105 treatment；Stage A 零 GT/零 fit/零 predict；相同 interval multiset 在 fit 前以 `MECHANISM_NOT_SUPPORTED` 停止；Stage B 固定 5×4、25/25/65/21，第21次是无 GT pooled aggregation；停止分类为 `REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`，仅完整五折可 `COMPLETE`。状态维持 `PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED`。Route3 v1-003 合法 COMPLETE、四门 FAIL、不重跑；gap=0 由路线二覆盖；合法路线二结果前不启动三个架构方向。

## 2026-10-01 整合后修订：revision-r 与 live systemd/cgroup backend

本节更新唯一研究ID route2-candidate-overlap-v1-001 的 cgroup 后端修补、无项目数据证据和当前阻断状态，保留既有 review、A+B 科学合同与探针证据。负责人已确认 Windows 宿主账号 owner 为可信主体；正式 image 创建前，WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别独立至少 8,589,934,592 B。正式双层实时检查仍未实现。

### 本轮修复和可复核证据

- 新增 linux_cgroup_backend.py：以固定 argv / shell=False 读取 systemd 精确属性；要求活动 Type=exec、Restart=no、KillMode=control-group 与预算内 memory/swap/tasks/CPU/runtime/stop 限制；严格校验 32 位十六进制 InvocationID，并在 cgroup/process 采集前后比较 unit 属性、invocation 和 PID。cgroup2 mount identity 前后也重新读取并比较 mount ID、device、resolved mount point、root device 和 inode，再调用既有完整 cgroup/process validator。模块 SHA-256 8c65d7e50ef98eee2fbb296114b9931b277b58013f37db7dcc5b8276bd3cd9fd；合成测试 SHA-256 4d602a0754059ddda294f8abb59ba55f1c94d53649e2eedd29dd74097ce07b61。
- 首轮独立质量检查发现 mount identity 可能在采集时更换、unit invocation 未固定；两项均加失败回归后修复。新的窄范围 quality review 与 spec review 均 PASS，未签发正式 review ID。定向 cgroup/enforcement suite 29 passed；完整无项目数据 Route2 suite 177 passed / 3.58 s。全套 pytest 在 Windows Python 3.14.6 执行；live capture 用准备好的 Linux Python 3.10.12 venv。
- 一次性 transient unit route2-scratch-live-cgroup-verifier-20261001f.service 捕获 InvocationID 654e1b4475154ee28631d18b9a8feb70、cgroup2 mount ID 685 / device 0:23、memory peak 15,835,136 B、pids current/max 1/2、单进程 RSS 19,562,496 B、RLIMIT_AS=2,147,483,648 B；退出后 unit 为 inactive/not-found，cgroup 已清除。见 [scratch v2](../evidence/2026-10-01-route2-live-cgroup-backend-scratch-v2.json)，SHA-256 9897cb6ae717f77b2b41b2c3c4b5e6dd53cef68323e656518bfcf5efd101817a。它只证明单惰性进程的一次 service/cgroup 捕获；8 GiB 是传入的合成值，不是实时 RAM 样本。
- 新 source snapshot revision-20261001r：/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001r/source，103 files / 1,562,738 B，manifest SHA-256 deee33c1a187f57cec0d9f5ce44443081db48a784b6252f5eb30ec098a433fdb，root uid 0 / mode 0555，103/103 复验。见 [revision-r evidence](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001r.json)，SHA-256 1bd7dcb8e6d6127e9a60d6b849312262cb8efbcff5693b678a3b0e1803f7bf82。依赖快照仍为 11,330 files / 348,519,927 B，manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e；Ubuntu 22.04 WSL2 / Python 3.10.12 / x86_64 / glibc 2.35 / SOABI cpython-310-x86_64-linux-gnu，pip check 通过。mode 0555 不等于正式只读 bind，readonly_mount_proven=false。

### 复审边界与未关闭门

新 PASS 仅覆盖 cgroup adapter 属性解析、unit invocation 绑定、mount identity 前后比较及相应 synthetic regressions；不覆盖完整 103-file A+B 闭包。完整 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍为 **FAIL / NOT_APPROVAL_READY**；INDEPENDENT_REVIEW_PASS 与 A+B owner approval 均为 NOT_ISSUED。

仍未关闭的 P1：未安装受保护 privileged controller / SupervisorOps，本后端尚未接入完整 Route2Supervisor 生命周期；同一 image 2→4 GiB durable gate 与建镜前双层实时空间检查未完成；逐 role/phase 私有 RO mount、GT 分段发布、旧 worker/FD 关闭和异常撤销未形成正式生命周期；worker 全写路径 OS 限制及 controller image、VHDX/backing、journal、QPC/seal receipt 的 volume 峰值计费未完成；全 study parent cgroup、RSS 与 worker≤2 无全流程强制收据；terminal close 后外部 wall receipt、service exit/cutoff/crash/missing receipt 未接入正式 runner；运行期 source/runtime/ABI/input/path-map/approval 冻结、完整历史 A+B 与 Windows→Linux 等价、control matched-GT additions/loss 与 HMAC key lifecycle 未完成；完整独立 PASS 与 owner approval 缺失。

P2/预算仍待裁决：wall 1200/3600/900 s、stop cushion 60 s、RSS min(4 GiB, floor(3×first available RAM/5))、worker≤2、disk 2/4 GiB、Stage B disk D_A+3×(B+232N+8S)+268,435,456≤4,294,967,296、Stage B RSS 536,870,912+6×232M≤frozen ceiling，以及 N/M/S/B/D_A 定义、volume 峰值与 image/VHDX/journal/QPC/seal receipts 是否计入 2/4 GiB。宿主信任和两个独立 8 GiB 下限已解决。

准备状态继续为 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED，唯一申请卡继续 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。原始探针 hashes 和 Linux 依赖说明仍保留在下方授权卡当前版本中；没有项目数据、GT、Stage A/B、正式研究 namespace 或 Route3 重跑。

## 2026-10-01 revision-t 更新：完整静态复审仍 FAIL

### 当前合成证据与范围

- 新准备源码快照 [revision-t](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001t.json)：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001t/source`，105 files / 1,572,963 B，manifest SHA-256 `b05a2655213ff2e9afba5943b11de99e886c8162bab195c90f2056f6edbde1f0`，root uid 0 / mode 0555；venv 11,330 files / 348,519,927 B，manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`。这是准备快照，不代表 controller-owned RO mount。
- 新跨 OS 收据 [revision-t probe](../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001t.json)，SHA-256 `6bf04a9e1128f0e3178c0ae32db14a95480245d62e21c5a4757626a23164102a`，已绑定当前 `stage_b.py` `fe6a45ebe5f3409c12de895c5ae6656284730eb59667526987b4b301561240e5`、冻结 A2-004 config `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043` 和 `max_iter=100`。合成输入、26D 特征、decoded output、event metric 和 pooled reduction 两端 hash 一致；200 个 verifier score 中 194 个位级一致，最大绝对差 `1.734723475976807e-18`，14 位小数舍入后一致。负责人尚未批准数值容差；这不是完整 A+B 等价 PASS。
- 当前无项目数据 Route 2 synthetic suite：Windows CPython 3.10.11 **178 passed / 4.75 s**。第一次在该解释器下运行时 4 个时间边界夹具因 `GetTickCount64()` 15.625 ms 分辨率相同刻度而失败；夹具现在等到下一时钟刻度，生产限时逻辑未放宽。GT views opened=0；未运行 Stage A/B。

### revision-r 的独立完整静态复审结论

只读审阅核验 revision-r manifest 及 103/103 文件，没有运行测试、service、Stage A/B 或读取项目数据；无正式 review ID。结论 **FAIL / NOT_APPROVAL_READY**，发现三项 P1：

1. Windows 入口仅开放 preflight/OS probes；完整 A+B 的 `PhaseRunner`、`SupervisorOps` 和 `ResourceEnforcer` 仍是注入接口，未形成可审阅、可信、安装的端到端执行边界。
2. 历史跨 OS 收据绑定旧 `stage_b.py` `a4173593…` 与 `max_iter=40`，不能证明当前配置。revision-t 新探针修复了这项陈旧绑定，但只验证一个合成 fit/vector、decoder、metrics 和 pooled reduction，且概率输出存在上述极小差值；完整数值语义仍未复审。
3. 外层评价只接收 treatment candidates；没有在同一个 outer GT view 上评价 control reference candidates，无法报告 matched-GT 候选 additions/losses。

原正式 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 继续有效且为 FAIL。revision-t 的新窄复审请求尚未返回；任何局部复审都不能替代完整 PASS。

预算候选、固定 105→105 / Stage B 5×4 / 25/25/65/21 协议及唯一 study ID 不变。申请仍为 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**；准备仍为 **PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED**。未创建正式研究资源，未打开 GT，未启动 Stage A-only 或 A+B，Route3 v1-003 未重跑。

## 2026-10-01 revision-u 更正：当前跨 OS 收据绑定一致

revision-t 窄复审发现其 `snapshot_scope.json` 收据 hash 来自工作树（`7aecc7db…`），而旧快照仍含 `8c46b34f…`。该版保留作审计历史并标记 superseded；不再作为当前源码绑定证据。

当前 revision-u 使用 manifest `ab898c849e1e22896813bb09866919cd6ed237ceaf8854ed524aef2d3fe1344f`，105 files / 1,573,062 B；其 `snapshot_scope.json` SHA 为 `7aecc7db19975be35fc25c7789e7ad2000b05a5ca3e7d17209f7f1898cbdf6e6`，与工作树一致。Windows CPython 与 Linux pinned CPython 都在同一份 WSL `/opt/.../revision-20261001u/source` 快照上独立验证全部 105 个文件；Windows 实际从 UNC probe/Stage B 路径导入，Linux 从相同 `/opt` 路径导入。详见 [revision-u cross-OS 收据](../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001u.json)，SHA-256 `73358db47b66d35a9eb663adf69c2d68779515a93398fc8441fad0bb428b7f7c`；准备状态记录见 [revision-u snapshot/runtime evidence](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001u.json)，SHA-256 `4441a4a24ea1fe01d1e3a4740ad3942ef0c86577dc595a84cda972e7dc3e525f`。

178 个无项目数据 Route 2 synthetic tests 也直接从 revision-u UNC 快照运行，178 passed / 5.43 s。此前的 3 个完整静态审阅 P1 不受这次证据绑定修正影响；revision-u 窄复审已对 source binding 给出有限范围 PASS（无正式 ID），正式 full-review ID `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL。该修正不创建正式 study image/volume/root/ledger/lock，不打开 GT，不启动 Stage A/B；状态仍 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED。
## 2026-10-01 revision-u 窄复审结论与额度语义修订

revision-u 的源码/收据绑定窄复核为 PASS（无正式 review ID）：105/105 文件与 manifest、snapshot_scope.json hash、Windows UNC/Linux /opt 源码及 probe/Stage B import 路径均核验通过；未发现新 P1/P2。revision-t 的 scope-hash P2 已在 revision-u 修复。reviewer 没有重跑 178 项测试，也没有审查完整 A+B、生产只读挂载或完整数值等价。此结论仅适用于 revision-u。

第 21 项 pooled 操作现在在源码和额度台账中拆分为 20 次 GT-backed evaluator（15 inner + 5 outer）+ 1 次 GT-free pooled reduction。reduction 只归并五个 participant-disjoint outer fold 的 participant metrics，不重新读取 pooled GT；completion 字段分列 evaluator_calls=20、pooled_aggregation_calls=1、pooled_gt_reads=0，总额度仍为 21。无数据 Route2 合成套件本轮为 178 passed / 4.63 s。此代码改动已在工作树中，但新的 immutable snapshot 与独立窄复审仍待完成。

完整正式 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 继续 FAIL / NOT_APPROVAL_READY。原有 P1、预算 P2、完整 A+B 独立 PASS 和 owner approval 均未关闭；FROZEN_ADMISSION=None，状态保持 PREPARED_UNREVIEWED / APPLICATION_BLOCKED / NOT_EXPERIMENT_AUTHORIZED。未读项目数据、score/cache 或 GT，未创建正式 study image/volume/root/ledger/lock，未运行 Stage A/B。

## 2026-10-02 整合后修订：revision-a 固定角色回放与当前准入证据

以下内容更新本 review 中的当前证据视图；revision-t/u/v/x 的旧收据与窄复审结论保留为历史记录。研究 ID 仍唯一为 `route2-candidate-overlap-v1-001`。

### 当前源码、依赖和输入身份

- 当前准备快照为 `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002a/source`，105 files / 1,616,440 B，manifest SHA-256 `4a53e5a86b4f64ba18cdedac267b71ead1a8f79441ee19a9bc06c217a13bd21f`，`snapshot_scope.json` SHA-256 `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`。Root-owned、mode 0555 的准备副本已由 Windows CPython 3.10.11 UNC 与 pinned Linux CPython 3.10.12 各验证完整 105/105 文件；这是内容身份验证，不表示 controller-owned read-only bind。
- Linux venv 绑定 manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`，11,330 files / 348,519,927 B；CPython 3.10.12、Ubuntu-22.04 WSL2、x86_64、glibc 2.35、SOABI `cpython-310-x86_64-linux-gnu`；lock `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`、identity `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`、pip check 通过。Windows 测试实际使用 CPython 3.10.11；默认 `python` 命令指向 3.14.6，未用于冻结版本验收。
- 输入身份沿用安全 projection：source registration SHA `e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`，projection manifest SHA `ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`，projection receipt SHA `a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c`，10 个 identity pins。G1/role graph/A2-004 config 及 GT/reference/role-input registry pins 见 prepared receipt。Registration 和 projection 仍 `PREPARED_UNREVIEWED`；正式逐文件 path-map `NOT_CREATED`，不能称为运行期输入路径冻结。
- 新收据：[revision-a prepared source/runtime](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002a.json)，SHA `7573ac37ac2c1222792edc66b8d16a5d0442abef57c0b9686b21c34d70cea356`；[revision-a cross-OS synthetic](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002a.json)，SHA `4522591f27fcf3a480ae7c46823c3df56ede4e77645e730d1ada44e45659c359`。两端均从同一只读快照运行 13 个 Route2 no-data synthetic test files：Windows 184 passed / 6.92 s；Linux 184 passed / 3.04 s。Linux 使用 pinned venv 数值依赖和后置系统 pytest 6.2.5 harness，出现一个旧 pytest 对 `pythonpath` 配置的 warning。
- 原 revision-x prepared receipt SHA `6247b1501ded892179cebadc50355a0ab1ddfabb9d94fc3910160c4bf64a9550` 顶层 source 绑定正确，但 `source_runtime_reverification` 仍引用 revision-v，`lifecycle_slice` 仍把 revision-u/v 写作当前。[更正记录](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261001x-binding-correction.json) SHA `fa4be183d960d421962e1ef62d31105bbadc6fa514ebc1b151680ab10d741fe3` 列明这两个历史字段；revision-a 收据是当前 source/runtime 证据。更正仍待独立复核。

### 固定 Stage B 角色回放修订

旧事件回放确认 25/25/65/21 总额度，却没有从 ledger 独立证明精确 5×4 role graph。revision-a 将 accounting 更新为 schema `route2_fixed_call_event_accounting_v2`：从有序 durable reservation/start/finish 事件重建五个 outer 及各四个 inner role，核对 25 fit、25 predict、65 decoder、20 GT-backed evaluator、1 GT-free pooled-reduction 的精确角色序列；`StageBResult.fit_provenance` 的 25 个 role ID 和 attempt 序号再绑定重放所得 fit 序列。新增 `test_call_event_replay_rejects_generic_role_ids_even_when_quotas_match`，全套 184 项合成测试通过。该代码修复关闭先前发现的 generic role IDs 配额攻击缺口，独立 review 仍 pending。

### 跨 OS 数值证据边界

revision-a probe 在两个系统均导入相同 Stage B hash `78c14d552314ed99262294381324401320fdd12d61301419353164cd2184e109`；synthetic features、decode、event metrics 与 pooled reduction hash 相同。200 个 synthetic probability 中 194 个逐位相同，最大绝对差 `1.734723475976807e-18`、最大相对差 `1.598084348556363e-16`、RMS 差 `2.6020852139652105e-19`。没有负责人批准的数值容差；probe 只有一个 HGB synthetic fit、40 个合成候选与 41 个合成 participants 的 pooled reduction，不等于完整 5×4 A+B 等价。

### 当前未关闭 P1/P2

- P1：没有受保护并已安装、把 `SupervisorOps`、`PhaseRunner`、`ResourceEnforcer` 接为完整 A+B boundary 的可信 controller；没有 `FROZEN_ADMISSION`。正式同一 image 的 2→4 GiB durable ledger gate 和同次 invocation 建镜前两处独立 ≥8 GiB 实测仍未接入 lifecycle。
- P1：生产 private mount namespace、逐 role/phase RO mount rotation、GT 分阶段发布、旧 worker/FD teardown、异常撤销与 controller HMAC key 生命周期没有正式 receipts。
- P1：worker 全写路径 OS 限制、controller/image/VHDX/WSL backing/journal/QPC 等承载卷和峰值计费、study-wide parent cgroup/RSS ceiling/compute worker≤2、terminal close 后外部 wall receipt 的 exit/cutoff/crash/missing-receipt 验收未完成。
- P1：source/runtime/ABI/输入/path-map/approval 尚未由安装 controller 运行期绑定到 RO mounts；完整 A+B 与全流程数值等价、完整 independent PASS 均缺失。正式 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL。
- P2：负责人尚未裁决 wall 1200/3600/900 s、60 s cushion、RSS 公式、worker 定义、2/4 GiB 口径与 Stage B 公式。`D_A` 为 Stage A 结束计费占盘；`B` 为完整处理候选 UTF-8 字节；`N` 为处理候选总数；`S` 为 25 个 held-out 预测 role 总行数；`M` 为 verifier 周期中四个 OOF 训练 role 与对应 held-out 行数之和的最大值。拟议 disk `D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296` B；拟议 RSS `536,870,912 + 6 × 232M ≤ frozen RSS ceiling`。
- 已明确决定：Windows 宿主账号所有者为可信主体；WSL backing filesystem 与 VHDX 所在 Windows 实体卷的建镜前可用空间分别各 ≥8,589,934,592 B。正式实时 gate 尚未实现。
- image、volume、root、ledger、lock 当前均 `ABSENT`；GT views opened=0；未用项目输入、score/cache；Stage A/B 未运行。当前 `PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED`。Route3 v1-003 维持合法 COMPLETE、四门 FAIL，不重跑；gap=0 由 Route2 覆盖；无合法 Route2 结果前不启动三个架构方向。

revision-a source/receipt 与 role schedule 的窄独立复核已请求，尚无 review ID。当前唯一研究 ID 的 A+B 条件申请仍 `APPLICATION_BLOCKED / NOT_APPROVAL_READY`；负责人另行明确批准完整、review 完成的具体卡之前，不启动 Stage A-only 或 A+B，也不讨论首次实验运行。

## 2026-10-02 整合后修订：revision-b 回放/provenance 修补与准入申请

唯一研究 ID 仍为 route2-candidate-overlap-v1-001。本次只做准入实现修补、无项目数据合成核验和审阅准备；状态保持 PREPARED_UNREVIEWED / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，FROZEN_ADMISSION=None。Stage A、Stage B、Stage A-only 均未启动，GT views opened=0；未读取项目数据、scores 或 cache；Route3 v1-003 不重跑，三个架构方向不启动。

### 当前源码、依赖与源文件身份

- revision-b immutable source root：/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002b/source；Windows 访问路径为 \\wsl.localhost\Ubuntu-22.04\opt\route2\snapshots\route2-candidate-overlap-v1-001\revision-20261002b\source。root uid=0、mode=0555；105 个文件 / 1,657,792 B；canonical manifest SHA-256 82f563d2cac21a5916f03908e5e7cf404fba64157238b0d28027fc79443407f0；snapshot_scope.json SHA-256 0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61。Windows CPython 3.10.11 与 pinned Linux CPython 3.10.12 分别从 revision-b 使用 frozen source_snapshot.verify_source_snapshot 核验完整 105/105 文件。
- Linux dependency snapshot 保持 /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv；11,330 files / 348,519,927 B；manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e；Python executable SHA-256 a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；Ubuntu 22.04 WSL2、Python 3.10.12、x86_64、glibc 2.35、SOABI cpython-310-x86_64-linux-gnu；numpy 2.2.6、pandas 2.3.3、psutil 7.2.2、PyYAML 6.0.3、scipy 1.15.3、scikit-learn 1.7.2；pip check 通过。完整 venv manifest 本轮重新核验。
- Windows probe interpreter 为 CPython 3.10.11，python.exe SHA-256 3cce33d75d6fdae4e004d0bdf149320b3147482a9caf370079dcb9c191a1b260；probe numeric package versions 与 Linux pinned runtime 相同。
- 两个新证据：[revision-b prepared source/runtime](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002b.json)，SHA-256 c2e85d16ddd3fab1ef00b0bab536bcd8cd3a92dd900b4f7093fcaea2b9c2e301；[revision-b cross-OS synthetic](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002b.json)，SHA-256 394ef837276c3693f18ff7eb1bc88c981e005eb74fc4927323797dc0170edc00。保留的原始合成 probe outputs：Windows [JSON](../evidence/2026-10-02-route2-cross-os-synthetic-revision-20261002b-windows-output.json) SHA-256 ea99e21601db369fa579acecb66117a20474a6e8815feb617f9cc36194cc1b52；Linux [JSON](../evidence/2026-10-02-route2-cross-os-synthetic-revision-20261002b-linux-output.json) SHA-256 afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc。

### revision-b 修补、回归与窄审阅

- 修补 durable replay 的全局调用次序，拒绝各 kind 单独排序正确但跨 kind 分组错序；accounting v3 把 global call sequence hash 和 frozen role graph SHA纳入。
- StageB projection、BudgetGuard 和 terminal replay 绑定完整 frozen role graph SHA、105 个冻结 role IDs 与 5 outer / 20 inner / 80 subinner fit-training role schedule；完成结果所选 outer IDs 必须精确来自 frozen graph。
- 25 个 verifier fit provenance 现在要求逐条、按顺序与 durable verifier_fit_provenance events 对应，核验 event schema、role/attempt、metrics、参与者和训练 role graph、model SHA、canonical verifier-models/<sha256(role)>.pickle 路径及 study-root 中的模型文件 SHA；terminal replay 再将 durable events 与 StageBResult 逐项比较。
- 关键源码 SHA-256：budget.py 0ff5609fc9120afb2a089f8a747bc894c665455e919025e195221e73e62c2ed8；stage_b.py c755a8d11e210a626a17a3e4ddd3af031d0985e4e057d0ff743164fcf52353a9；linux_supervisor.py 81a24c0f128b279bdde275567faf0ab30b32b53b972838eba48e5e96b64af8a2；test_route2_budget_wsl_synthetic.py 5385545e13a46573c55c1e109a46d843f71382271f1532e4cd8b87416a81d107；test_route2_supervisor_lifecycle_synthetic.py 9b4ad747370f9ccc1e083b5eba7d219c6c90990267a40896edba5f43660c9a36。
- revision-b immutable tree 的 13 个 Route2 no-data synthetic test files：Windows CPython 3.10.11 / pytest 9.1.0 为 194 passed / 8.51 s；Linux pinned CPython 3.10.12 / system pytest 6.2.5 为 194 passed / 4.41 s，附一条 pytest 6.2.5 不识别 pyproject pythonpath 选项的 warning。两边均禁用 cacheprovider 与 bytecode；没有使用项目数据或 GT。
- 当前只读审阅仍在进行：route2_ab_full_static_audit 核 revision-b 全局调用、105-role graph 与 fit provenance links；cgroup_backend_quality_review 核 revision-b receipt/output/hash binding。两者当前 review ID 均 NOT_ISSUED；不得写作完整 A+B PASS。正式完整实现 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍为 FAIL / NOT_APPROVAL_READY。

### 跨 OS 合成探针的解释

revision-b script SHA-256 5b69c406d4205d3fc72bfb190ed6fffb6fc3f1ed35382076146a2003cbf1b8be；两边均绑定 StageBAdapter SHA-256 c755a8d11e210a626a17a3e4ddd3af031d0985e4e057d0ff743164fcf52353a9。输入为内存合成数据：一次确定性 HGB fit（200 行）、40 个 synthetic candidates 输入 decoder、31 个输出、synthetic event metrics 和 41 个 synthetic participants 的五折 pooled reduction。source16D、feature26D、decoder、event metric 与 pooled reduction hashes 完全相同。200 个 probability 值中 194 个 bitwise 相同；最大绝对差 1.734723475976807e-18，最大相对差 1.598084348556363e-16，RMS 差 2.6020852139652105e-19；6 至 14 位小数舍入结果相同，但 binary hashes 不同且没有负责人批准的 tolerance。该结果是 PARTIAL_MATCH_ONLY，不是完整 5x4 A+B 等价证明。

### 当前仍阻断的 P1/P2 与申请卡状态

- P1：缺少已安装、受保护且可信的完整 privileged controller，将 SupervisorOps / PhaseRunner / ResourceEnforcer 接入唯一 A+B 执行边界；同一 image 2→4 GiB durable gate 与镜像前同 invocation 双层实时 8 GiB gate 尚未连入执行；生产 private namespace 逐 role RO mounts、分阶段 GT publish/revoke、worker/FD teardown 和 controller HMAC key lifecycle 未证明。
- P1：worker 全写路径 OS 限制，以及 controller image、VHDX、WSL backing、journal、QPC、seal/controller receipts 的实际卷身份与峰值/卷外计账未闭合；whole-study parent cgroup、全 study hard RSS 与 worker<=2 尚无全程强制证据；terminal close 后外部 wall receipt 对 service exit、cutoff、crash、missing receipt 的持久验收未闭合。
- P1：正式 controller-owned read-only freeze 对 source/dependencies/ABI/inputs/path map/approval 尚未安装或验证；正式 role input/GT path map 仍 NOT_CREATED。完整历史 nested 5x4 A+B 跨 OS 数值等价、正式独立 PASS 和 owner approval 均未签发。
- P2：负责人尚未批准提出的 wall 1200/3600/900 s、60 s stop cushion、RSS min(4 GiB,floor(3*first available RAM/5))、worker<=2、Stage A/whole-study disk 2/4 GiB、Stage B disk D_A+3*(B+232N+8S)+268435456<=4294967296 B、RSS 536870912+6*232M<=frozen RSS ceiling，以及 D_A/B/N/S/M freeze semantics 和 controller/external writes 的真实 volume/peak accounting。
- 负责人已经确认 Windows host account owner 是可信主体，并确认 WSL backing filesystem 与 VHDX 所在 Windows physical volume 在建镜前各自独立至少 8,589,934,592 B；此答复没有代替同 invocation 实时 gate。
- 唯一授权卡状态仍 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。card 保持 route2-candidate-overlap-v1-001 的一次完整 A+B 条件申请，列明 105 reference→105 treatment、固定 5x4、25/25/65/21 与各停止分类；待关闭所有 P1/P2、完成独立 review 和预算明确批准，并由负责人对同一张具体卡另行明确批准后，才可讨论首次运行。

原始能力探针与 Linux dependency evidence 保留其原哈希及历史范围：disk/ENOSPC a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939；cgroup 7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9；wall 302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c；single RO bind 7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257；live cgroup c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096；Windows QPC 55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c；worker scratch alias 7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca；Linux dependency runtime note d0f352f70b5721d58cef37eae97c7a20e16212531c262f43c1a1e8f6fd8b83b0。它们仍是能力/依赖证据，不是完整 study lifecycle 证明。

## 2026-10-02 整合后修订：revision-g 当前证据及准入复审

本节将 revision-g 设为当前只读准备基线，supersede revision-b/c/f 的当前身份引用；唯一研究 ID 仍为 `route2-candidate-overlap-v1-001`。本次只进行准入修补、无项目数据合成核验、独立复审和卡片更新。`FROZEN_ADMISSION=None`，`NOT_EXPERIMENT_AUTHORIZED`；未运行 Stage A-only、Stage A、Stage B；未打开 GT view、项目输入、scores 或 cache。image/volume/study root/ledger/lock/path map 均未创建。Route3 v1-003 保持合法 `COMPLETE` 与四门 `FAIL`，不重跑；gap=0 已由路线二覆盖；合法 Route2 结果前不启动三个架构方向。

- 当前只读源码：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002g/source`；105 files / 1,674,692 B；manifest SHA-256 `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`；scope SHA-256 `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`；root uid 0 / mode 0555，revision parent mode 0755。Windows 和 Linux 各在测试前后独立核验全部 105 files，revision-d 留存但因 3 个意外 `__pycache__` 文件无效，revision-e 留存但其 parent mode 0700 无法经 Windows UNC 验证，revision-f 已被 g supersede。
- 固定快照的 13 个 Route 2 no-data test files 在 Windows CPython 3.10.11 / pytest 9.1.0 **203 passed / 10.81 s**；Ubuntu 22.04 WSL2 CPython 3.10.12 / pytest 6.2.5 + pinned numeric venv **203 passed / 5.63 s**，另有 pytest 不识别 `pythonpath` 配置的 warning。禁用 cacheprovider 和 bytecode。无项目数据、GT、Stage A/B。
- 当前证据：[prepared source/runtime revision-g](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002g.json)，SHA-256 `9c2a34758988b64d06987db4cf3710caa3afd9047b0b758fbb0b864f5b91ab67`；[cross-OS aggregate revision-g](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002g.json)，SHA-256 `f74ab7ae43ac81c3772259f35c7afe82bb4300eb4f53dc8c9a5c4d68f4ce8346`。Raw Windows / Linux vectors SHA-256 分别为 `1b7d9701689365a75ddd01d6d5a9a4801596fac1b858ecc3e7e98d6c3545a4ff` / `afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc`。指定非概率哈希一致；200 probability 值中 194 个 bitwise equal，最大绝对差 `1.734723475976807e-18`、最大相对差 `1.5980843485563632e-16`、RMS `2.6020852139652105e-19`，6–14 位小数舍入一致。负责人未批准容差，判定仍是 `PARTIAL_MATCH_ONLY`，不是完整 A+B 数值等价。revision-g evidence-binding narrow review 已 PASS（review ID `NOT_ISSUED`），仅确认 aggregate、raw vectors、source manifest/scope 与统计量绑定；不覆盖完整 A+B。
- revision-g narrow static source review 已确认 `AppendOnlyLedger.create` 与 `BudgetGuard.start` 在任何文件或 OS 操作前拒绝 duck-typed approval，关闭该 P2（review ID `NOT_ISSUED`）。审阅还确认 21 项配额源码语义与同一 outer GT 上 keyed reference/treatment additions/losses 算法；均为源码范围局部 PASS，无真实 GT 执行或生产 PhaseRunner 证明。完整 A+B 执行边界仍 FAIL；不把窄 review 写成完整 PASS。
- 第 21 项额度协议为 20 次 GT-backed evaluator（15 inner + 5 outer）和 1 次 GT-free pooled reduction，归并五个不相交 outer-fold participant metrics，`pooled_gt_reads=0`。本次静态源码复核确认语义，203 项合成测试通过；正式完整 A+B 审阅 ID 仍为 `NOT_ISSUED` 且既有完整 review 仍 FAIL。
- 负责人已确认 Windows host account owner 为可信主体，并确认正式镜像创建前 WSL backing filesystem 与承载 `ext4.vhdx` 的 Windows 实体卷各自独立至少 `8,589,934,592 B`，两层不合并。其余 wall/RSS/workers/disk/公式/冻结时点/卷外写入峰值预算未批准；镜像创建前同 invocation 的双卷实时门未接入生产执行。

**仍未关闭的 P1/P2：**没有安装且受保护的完整 privileged controller，也没有生产 `SupervisorOps` / `PhaseRunner` / `ResourceEnforcer` A+B 执行边界；bootstrap 安装的 admission 对象没有贯穿持久 A+B runner，`FROZEN_ADMISSION=None`；同一镜像 2→4 GiB durable gate 和双卷同 invocation ≥8 GiB gate 未连接；production per-role read-only mount rotation、分阶段 GT publish/revoke 与 child/FD teardown 未证明；worker 全写路径和 controller image/VHDX/backing/journal/QPC/seal/controller receipt 卷身份及峰值记账未闭合；全 study parent cgroup、hard RSS 与 worker≤2 enforcement 未安装；terminal close 后外部 wall receipt 尚未验收正常退出/cutoff/crash/missing receipt；同 outer GT additions/losses 算法已做窄静态复核，但真实 GT phase runner 与 production execution 仍无证据；完整 5×4 A+B 独立 PASS 未完成；跨 OS probability 仍有差异且 tolerance 未批准。P2 仍有所有未批准的预算与 `D_A/B/N/S/M` freeze semantics。

正式完整实现 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 继续 `FAIL / NOT_APPROVAL_READY`。唯一授权卡继续 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`；只有全部阻断关闭、准确 source/input/runtime/controller hash 获独立 PASS、预算明确批准，并由负责人另行批准同一具体卡后，才能讨论首次运行。

## 2026-10-02 整合后修订：四项核对、负责人裁决草案与最小 A+B 条件卡

本节续接 **2026-09-29 整合后修订**及其 revision-g 更新，是本轮讨论的当前依据。只核阅既有文档和无项目数据回执，重新计算指定证据文件的 SHA-256；没有重跑探针、测试或任何实验，也没有重新测量 WSL 实时状态。下述建议均为待裁决政策与验收要求，不是新执行许可。原授权卡仍是同一张卡；本轮按写入范围只更新原设计、执行计划和本 review，不修改授权卡或新建交接包。

### 四项状态分别核对

| 核对项 | 最新 review 与 revision-g 原始收据 | 本轮结论 |
|---|---|---|
| 准备视图 | 来源登记与物理投影已生成，仍 `PREPARED_UNREVIEWED`；projection 的正式 `independent_review_id=null`。安全 metadata projection 也没有正式 attestation。 | 已生成不等于正式准入审阅通过；保留准备状态。 |
| 完整 A+B 授权 | `experiment_authorized=false`、owner approval `NOT_ISSUED`、`FROZEN_ADMISSION=None`。 | 尚未获授权。 |
| Stage A/B 合法运行 | `stage_a_or_b_started=false`、`gt_views_opened=0`；收据记录 image/volume/root/ledger/lock 均不存在，path-map 未创建。 | 两阶段均未合法运行；这些是既有收据状态，本轮没有以新 invocation 验证或创建正式对象。 |
| 路线二合法结果 | 只有准备、scratch 和合成回执，没有合法 Stage A/B 结果。 | 没有合法路线二结果。 |

完整实现复审 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 **FAIL / NOT_APPROVAL_READY**。9月29日的21项合成测试和 revision-g 双端各203项合成测试均只是各自范围的准备证据。revision-g 证据绑定、approval guard、21项额度及 matched-GT 算法的窄复审没有正式 review ID，也没有签发完整实验准入 PASS。

本轮重算以下原始文件 hash，与既有记录一致：

| 原始证据 | SHA-256 | 可支持的结论 |
|---|---|---|
| [同卷 scratch disk raw](../evidence/2026-09-29-route2-wsl-disk-probe-raw.json) | `a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939` | 实际容量 `2,040,373,248→4,152,066,048 B`，两次 ENOSPC，同 mount/device/UUID；synthetic gate 只是布尔值，不是正式 Stage B 门。 |
| [cgroup raw](../evidence/2026-09-29-route2-wsl-cgroup-probe-raw.json) | `7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9` | 合成第三 task 和超额 VMS 被拒；收据明确 `hard_rss_or_worker_receipt_issued=false`、依赖/supervisor拓扑未证明。 |
| [wall raw](../evidence/2026-09-29-route2-wsl-wall-probe-raw.json) | `302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c` | fake receipt 缺失/迟到拒绝；`post_close_result_durable=false`、`durable_external_completion_event_proven=false`。 |
| [Linux dependency evidence](../evidence/2026-09-29-route2-linux-dependency-runtime.md) | `d0f352f70b5721d58cef37eae97c7a20e16212531c262f43c1a1e8f6fd8b83b0` | 13-wheel hash、离线安装、import、pip check 与 ABI 的准备事实；不证明生产只读运行期或全协议等价。 |
| [revision-g prepared receipt](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002g.json) | `9c2a34758988b64d06987db4cf3710caa3afd9047b0b758fbb0b864f5b91ab67` | 105文件源码准备身份、依赖身份、既有203项合成记录及上述拒绝态。 |
| [revision-g cross-OS receipt](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002g.json) | `f74ab7ae43ac81c3772259f35c7afe82bb4300eb4f53dc8c9a5c4d68f4ce8346` | 非概率摘要相同，概率194/200逐位相同；无批准容差，仍 `PARTIAL_MATCH_ONLY`。 |

**身份抄录更正（P2）：**两份 revision-g 原始收据都记录 `snapshot_scope.json` 的64位 SHA-256 为 `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`。上方 revision-g 文字、设计、计划及原授权卡误录为含额外 `f6` 的66位串；本轮在三份允许写入的文档更正当前口径，旧卡仍须在正式提交前同步并独立复核。本更正不改 source manifest `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`，不声称重新验证了 Linux 源码树，也不新增正式 review ID。

### 1. 宿主信任与执行后端

**已有证据：**本机账号能以 WSL root 进入发行版、VHDX ACL 给账号/管理员控制权；负责人已明确宿主账号所有者可信。WSL root 入口能力也符合 [Microsoft WSL 命令说明](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)。这项政策选择已经确认，不再次当作未决问题。

**缺失证据：**可信主体名单尚须随最终卡冻结到实际 launcher、root config/key、controller、外部 observer 与 reviewer issuer；worker 不能提升权限、改控制配置或绕过 phase namespace 的生产证据仍缺。可信宿主的诚实执行是前提，现方案没有限制宿主本人读取 GT 或改账本的技术保证。

| 方案 | 代价与边界 | 建议状态 |
|---|---|---|
| 延续已确认的可信宿主 + WSL2 worker 隔离 | 复用准备依赖和路径；需要安装受保护 controller、移除 worker 控制权限、重审输入/GT与账本边界。宿主仍有 root 能力。 | 推荐延续既有决定；OS隔离 P1 保留。 |
| 改为独立受控 Linux runner | 若负责人要求连 Windows 登录用户也不能读 GT/改账本，必须移出其控制的宿主；增加数据受控迁移、Linux设备/磁盘与输入映射重绑定、observer/依赖重新审阅的成本。 | 仅在信任要求改变时选择，不能用普通本机新账号代替。 |

### 2. 双层空间门与控制层计费

**已有证据：**raw disk 回执分别记录 WSL backing ext4 与实际 VHDX 的 Windows volume GUID/free bytes。WSL 虚拟可用空间不能代表实体卷余量；[Microsoft WSL 磁盘说明](https://learn.microsoft.com/en-us/windows/wsl/disk-space)明确虚拟容量可以大于实体盘。负责人已确认正式建镜像前两层**各自**至少 `8,589,934,592 B`，不能相加或互相抵扣。历史写压导致 VHDX 增长，删除 scratch 未立即返还其分配。

**缺失证据：**同一 invocation、首个 Linux monotonic 样本之后且建镜像之前，两次 live 测量与真实 backing mount/device、VHDX路径及Windows volume GUID 的绑定；无效/过期样本拒绝和测量到创建之间的身份复核；控制层逐路径、占盘峰值与硬额度。8 GiB 是启动余量门，不是授权花费8 GiB，也不保证其他宿主写者不会耗尽磁盘。

| 计费方案 | 代价 | 建议 |
|---|---|---|
| 研究卷仍受2/4 GiB；控制层另列有界预算 | 不改 N/M/S/B/D_A 的研究卷口径；增加镜像、WSL backing/VHDX、journal、外部锚与seal收据的独立清单、限制和归因。 | 推荐，具体控制层字节额度尚未提出可批准的完整数值。 |
| 将各层占用加总到原2/4 GiB | 同一数据的研究文件、镜像、VHDX会重复计账，原4 GiB文件系统不再代表4 GiB总成本；必须重定义 D_A、容量和入场式，提前重新审阅。 | 更保守但影响可用容量，不能默默套用旧公式。 |
| 迁至专用 runner/专用承载卷 | 更容易做 quota、预留和归因；增加迁移与全绑定复审费用。 | 共享VHDX增量无法可靠限制或计账时的备选。 |

推荐方案应把下表填成精确数值合同；任一 `NOT_FIXED` 项不能进入可批准卡：

| 层/写入 | 计费口径与必须记录的身份 | 当前缺口 |
|---|---|---|
| 研究 ext4 卷 | 输出、候选、模型、临时/原子副本、日志、ledger/lock、卷内ext4元数据/journal均受2/4 GiB硬容量；记整个文件系统占用峰值，不能只加可见文件大小或删除后净值。 | 全写路径系统限制与正式容量收据缺。 |
| loop image / WSL backing | 镜像逻辑长度分别≤2/4 GiB；另记image dev/inode、已分配块与backing增量。它位于研究卷外。 | 物理分配/控制额外开销的字节cap与计费政策 `NOT_FIXED`。 |
| Windows VHDX实体分配 | 从同次批准invocation基线记实际实体占用增量峰值，不能仅用逻辑文件长度；同一层不把image再相加，跨层分别报告。共享发行版不能分辨的增量保守全额记或改用专用承载环境。 | 分配测量接口、归因、峰值cap与超限停止 `NOT_FIXED`；不得以清理后缩小抵扣历史峰值。 |
| systemd/system journal | 优先把worker stdio直接写研究卷；残余service/kernel journal须列准确路径/namespace/卷，按约定增量或保守全额记账。不能通过允许worker写journal socket来逃逸额度。 | 实际路由、隔离与增量cap `NOT_FIXED`。 |
| 外部wall锚、seal/controller receipts | 精确路径、Linux device或Windows volume GUID、最多记录数、最大字节、durable写入与保留期；只能由可信控制层写。 | 路径/hash/峰值cap `NOT_FIXED`。 |

准备的 source/venv/wheelhouse 属既有准备成本，须披露基线；未来invocation产生的副本、新安装或额外写入不能借“准备”名称免计。外部Windows observer的RAM/tasks也须单列预算；若负责人要求它属于原全进程RSS范围，则须提供跨OS强制加总，不能悄悄排除。

### 3. RSS、worker、正式扩容和 GT 撤销

**已有证据：**`memory.max`、`swap.max=0`、`pids.max=2`、`RLIMIT_AS`的局部拒绝；single RO bind、部分worker写alias、live cgroup身份与Python role/revoke sequencing原型；durable call replay和固定角色/调用顺序的合成证据。原始能力回执没有覆盖整个 study。

**缺失证据：**supervisor/hash/resize helper/worker 的完整进程与线程拓扑、设置限额到exec的连续性、禁止迁出或改限额、真实依赖在此拓扑下可运行；正式扩容门和逐role/phase挂载/FD回收链；所有写路径的系统拒绝。

| 可选强制方法 | 代价与必须证明的条件 |
|---|---|
| 保留原 RSS，先审保守两task方法（推荐先评估） | 全Linux研究进程纳入同一父cgroup，启动时task≤2，之后禁止额外附加/迁出；所有进程exec前 soft/hard `RLIMIT_AS≤floor(C/2)`，其中 `C=min(4GiB,floor(3×首次可用RAM/5))`。在普通用户地址空间及既定RSS定义下，至多两进程、每进程RSS≤VMS≤C/2给出总RSS≤C的保守证明。两task含supervisor本身，因此通常只剩一个worker/helper槽，必须串行且库线程受限；不能宣称能同时跑两个worker。较小可用RAM或native库地址映射可能使依赖无法启动。 |
| 保留原 RSS，分配更多受限控制task | 逐进程地址空间预算之和≤C，worker子组task≤2，控制进程另设有限task/地址额度；需要防止fork复制地址预算并核全部进程类型，证明明显更复杂。不得只设总pids=k、每进程C/2。 |
| 改为cgroup charged-memory指标 + 分离控制task与worker额度 | 可用 `memory.max`、swap禁用及worker子组task硬限，拓扑更宽松；必须负责人明确批准指标改变、控制开销和短时越限语义，重新审阅Stage B投影式。不能称它证明了原进程树RSS硬上限。 |

上述第一种仍只是待审方案。Linux [cgroup v2文档](https://docs.kernel.org/admin-guide/cgroup-v2.html)说明pids计线程，附加进程/降低限额可能令current大于max；memory.max在特定情形也可暂时越限。[Linux resource-limit文档](https://man7.org/linux/man-pages/man2/getrlimit.2.html)说明RLIMIT_AS限制虚拟地址空间，现代Linux的RLIMIT_RSS不能提供所需RSS硬限。故需exec前核验、固定成员和能力限制；采样RSS、线程环境变量、CPUQuota都只能补充证据。当前查到的是机制语义，最终审阅仍须冻结本机实际kernel/systemd功能，不能假定具有最新版功能。

**正式2→4 GiB门：**在一次已批准 A+B 内，105 reference全通过 → 同105 treatment完成 → interval multiset有差异 → 以无标签产物冻结 `N/M/S/B/D_A` → 通过预批disk/RSS两式及A全部硬线 → 入场事件与账本fsync → 才扩原image/loop/ext4。扩前后核image path/dev/inode、length/allocated blocks、loop backing、UUID、mount ID/device及实际容量；不换卷、不提前扩、不接受caller布尔值作证据。任何失败停 `INCOMPLETE_RESOURCE` 或相应输入终态。正式namespace的真实收据只能在另获实验授权后生成；授权前需由同生产controller在独立scratch身份、纯合成输入上验证这条门，当前缺失。

**全部worker写路径：**输出/模型/ledger/lock、临时及原子副本、`/tmp`、`/var/tmp`、`/dev/shm`、HOME/XDG、NumPy/joblib/sklearn缓存、pyc、core、IPC、stdout/stderr及继承FD/daemon socket均要有明确拒绝或同研究卷映射。环境变量重定向不能代替只读root/允许写mount、去权限与实际写拒绝。匿名IPC内存纳入RSS/task；文件或shared-memory落盘纳入磁盘，不能另开未计tmpfs。

**逐role/phase证据合同：**每项绑定study/invocation、role/phase、participant白名单、输入logical path/hash、实际文件dev/inode、只读mount ID/device和namespace、worker PID/start identity、调用/预测receipt、release/revoke事件与时序。Stage A只见当前非GT role；训练仅六字段training视图；每outer全部12份inner阈值预测持久冻结后才挂inner evaluation GT，outer预测冻结后才挂outer GT。GT release后先核同一FD的实际hash再读语义，退出需证child及其后代已退出、无继承/传递FD残留、bind撤销、truth对象释放；随后才开下一role。单次umount不证明旧FD已失效。异常撤销证据缺失时不能接受 `COMPLETE` 或续跑。110个GT文件不得预挂/预读。

matched-GT additions/losses 算法在 revision-g 已获窄静态核对，不再称“算法未实现”；仍缺同outer GT scope下的生产PhaseRunner、control来源与同key承诺绑定、密钥创建/仅GT child分发/销毁及实际执行收据。该诊断不得增加fit、predict、decoder或额外GT-backed evaluator，若最终实现需要增调用，须先重审额度。

### 4. terminal后墙钟、完整运行期身份与 pooled 裁决

| 子项 | 已有证据 | 缺失证据 | 选项与代价 |
|---|---|---|---|
| 外部wall验收 | raw wall拒绝缺失/迟到；后续QPC合成core/seal记录terminal/service/receipt次序。 | 正式runner集成；terminal append/fsync/close、receipt fsync/close后独立observer的截止/exit/cgroup-empty核验；最终持久接受锚、crash/no-resume与60s余量。 | 推荐可信外部observer及可审durable完成事件；需额外控制进程、持久存储与计费。若把最后seal持久化移出wall范围以简化，属于预算语义变更，须负责人明确批准，当前不采用。仅增加一个自报时间文件不解决最后一次fsync自证问题。 |
| 完整只读运行身份 | g source105文件manifest、venv11,330文件manifest、13-wheel锁/ABI、safe metadata、pre-import及approval parser原型。 | root保护安装与issuer；stdlib、dynamic loader/实际native-library闭包、入口/worker/controller/systemd unit、环境/import路径、正式path-map及RO mount完整身份；同一个approved admission贯穿bootstrap→持久runner→worker→终态。 | 推荐受保护安装加只读snapshot/逐文件manifest与外部封存admission；代码改动需重冻重审。更完整的只读rootfs可降低系统库漂移，但需要重建环境、增加存储和部署审阅成本。0555权限、版本号与HMAC parser不能独自产生可信批准。 |
| 数值与全5×4协议 | 非概率摘要相同；194/200概率逐位相同，max abs `1.734723475976807e-18`，未批容差。 | 当前生产闭包下完整纯合成5×4、数值边界/阈值平局与排序、历史label/26D/HGB/G3/decoder/matcher全协议独立复审；负责人容差政策。 | 维持逐位标准则现概率证据不通过，可能需统一运行环境；允许预声明容差需审边界决策不变，不能据6–14位舍入一致自行批准。容差通过也不能替代完整执行审阅。 |
| 第21项pooled | 源码及合成支持20次GT-backed evaluator + 1次GT-free reduction；五outer participant互斥。 | 负责人接受该替代；完整独立review及durable计数/participant覆盖、234分母和全字段结果验证。 | 推荐20+1，少开一次全量GT视图；若坚持第21次直接evaluator，须新增只读pooled GT scope/release/revoke、字段权限与phase资源审阅，不能自动切换。 |

wall合同需冻结一个连续的时钟/boot/invocation身份。Linux首个monotonic样本先于正式资源创建；Windows QPC如用于包住外层调用，须在其自身时钟内测duration，不能跨OS相减epoch。清理余量计入1200/3600s之内，不是再加60s；累计fit≤900s仍单独计成功/失败/中断。外部observer必须核已关闭ledger的terminal hash、完整收据hash、service exit/return code和cgroup空状态，并在最后计费持久化之后验deadline。未能为最终外部锚提供独立可审证据，就保持P1；迟到、重启换epoch、partial terminal、missing receipt、未净退出或清理超预算均不能接受结果，也不能重开额度。截止接受与实际超限消耗必须分别如实报告。

pooled归并必须先核五fold及participant集合互斥、完整、每participant matcher scope相同和outer评价eligible GT总数234。TP/FP/FN及long-FP计数求和；F1从总计数重算；MAE按未舍入的误差和/匹配数合并，long-FP fraction按总FP分母合并，不能平均fold F1/MAE/rate。零GT/零FP/无match语义沿冻结协议。对不能从现有participant指标充分恢复的字段，不能宣称全字段等价，须补冻结统计量并重审。分别硬限并回放 `evaluator_calls≤20`、`pooled_aggregation_calls≤1`、`pooled_gt_reads=0`，不得把第21个直接evaluator藏在合计21内。

**避免首次授权的循环前提：**授权前“完整A+B审阅”是完整生产执行闭包、历史科学协议及无项目数据全5×4验收的独立审阅；它不能要求先偷跑真实A+B取得结果。真实105参考复现、候选数量投影、phase GT/资源/terminal收据，是另获授权后本次唯一invocation里的门。若独立review要求额外真实输入跨OS核验，应另列精确数据权限/次数/预算供负责人决定，当前禁止自动执行，也不得重跑A2/Route3。

### 最小可审阅的一次完整 A+B 条件授权卡（同一研究ID的讨论视图）

**状态：`APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`。** 下表形成原卡待修订内容，不产生第二张研究卡，也不是附条件即时放行。现有准备hash不代表将来controller实现后仍可沿用；任何执行闭包变化必须刷新快照、收据和review。

| 卡字段 | 精确范围/候选值 | 尚缺项 |
|---|---|---|
| 唯一invocation | `route2-candidate-overlap-v1-001`，一次完整A+B，不重试/续跑、无Stage A-only；不得继承A2/Route3额度。 | owner A+B approval ID及批准记录hash `NOT_ISSUED`。 |
| 单一科学差异 | 原300s `<=end+300000`改严格正时长overlap `<end`；相同保存score/role/26D/HGB/threshold/180s/600s/matcher。 | 完整历史协议独立review。 |
| Stage A | 全105 reference interval/support复现后至多105 treatment；reference失败treatment=0；零GT、candidate-model fit/predict=0；interval multiset全同在fit前停止。 | 真实数据门仅在未来已授权invocation内执行，不能提前做候选计数。 |
| Stage B/调用 | 机制有差异且全部门通过后固定5×4；25 fit attempts、25 predict、65 decoder、20 GT-backed evaluator + 1 GT-free pooled reduction；失败attempt计费。 | 完整生产闭包及20+1正式协议裁决。 |
| 输入 | 工作树精确准备根 `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next/artifacts/route2-candidate-overlap-v1-001-inputs`；registration `e6f03b…1853`、manifest `ad85c0…fc5ad`；运行只打开冻结role/phase allowlist，非GT在Stage A核hash，GT release后逐文件核hash。 | Linux逐文件RO alias/path-map hash `NOT_CREATED`；安全metadata attestation及来源/projection正式批准绑定未签发。不得打开混合G1/A2原件补hash。 |
| source/runtime | g source `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002g/source`，manifest `40c3efe8…cf76d6`、正确scope见上；venv `/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv`，manifest `e8ee8b0c…2241e`；13-wheel lock `c749dcb0…db76`、identity `fa195a6a…658f`。完整hash沿原始收据，不以缩写做机器比较。 | 生产controller/入口/完整OS库闭包/RO mounts/环境与连续admission绑定；后续源码改动须重新冻结。 |
| 正式路径 | image `/var/lib/route2/images/route2-candidate-overlap-v1-001.ext4`；volume `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume`；root为volume下 `/route2-candidate-overlap-v1-001`，ledger为volume下 `/route2-candidate-overlap-v1-001-budget.jsonl`，lock为volume下 `/route2-candidate-overlap-v1-001.lock`。 | invocation前未占用核验及创建后dev/inode/UUID/mount/loop身份；本轮均不创建。 |
| wall/RSS/worker | A/total/fit≤1200/3600/900s；60s stop cushion计入wall；RSS≤`min(4294967296,floor(3×首次可用RAM/5))`；compute workers≤2。 | 除宿主可信外均未批；须选定上述强制方案、外部observer费用及最终durable墙钟锚。 |
| disk/free/扩容 | A≤2147483648 B，full≤4294967296 B，同image持久门后2→4；建镜前WSL backing与VHDX Windows实体卷各≥8589934592 B。 | 两层floor已确认，正式live gate缺；2/4预算和控制层cap/路径/计费仍未批。 |
| Stage B式与冻结量 | `D_A+3×(B+232N+8S)+268435456≤4294967296`；`536870912+6×232M≤C`。D_A=A末研究卷当前占盘；B=完整处理候选UTF-8字节；N=总处理候选数；S=25 held-out预测role总行数；M=25周期中四OOF训练role+对应held-out行数和的最大值。 | 数值/口径/冻结时点未批；量由未来Stage A无标签产物得到，fit/resize前写入并fsync，禁止观察后调系数。 |
| GT/terminal证据 | training/inner/outer六字段单阶段view、逐role撤销、12/1预测门、同outer GT诊断及HMAC key生命周期；terminal关闭后external wall/exit/cgroup-empty证据。 | 全生产OS收据缺；纯合成验收也尚未覆盖完整闭包。 |
| 停机/结果 | `REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`；仅完整合法五折及全部证据有效才`COMPLETE`。 | 资源/隔离失败不得记性能负结果或补跑。 |
| 报告量 | 同234 GT分母，pooled/fold TP/FP/FN/F1、long-FP、matched起止MAE及新增/丢失GT承诺、candidate coverage/规模；numeric minimum/ideal=0.66/0.80，stage另需≥3/5 fold F1≥0.66、每fold long-FP≤0.25、起止MAE≤900s。 | 保存冻结完整指标及原空值语义；41人已开发暴露，仍只作本地开发证据。 |

### 还缺的独立复审与负责人确认

1. **独立输入/元数据与身份复审：**把既有source-registration/physical-view窄引用绑定到正式外部attestation；核safe metadata、完整64位hash、逐文件映射及六字段消费者合同。原产物仍为准备态，不由文档自行写PASS。
2. **独立完整生产实现复审：**受保护安装/可信issuer、bootstrap→runner连续admission、双层live门、正式扩容逻辑、role/phase mount/FD teardown、全写路径、全study资源与外部wall/crash终态。需绑定最终source/runtime/controller/unit/path-map hash及纯合成OS生命周期证据，签发完整正式review ID；现在只有FAIL记录。
3. **独立完整科学协议/数值复审：**历史label-prejoin、训练资格、16D+10D、HGB/G3、nested/阈值/decoder/IoU/matcher、精确25/25/65/20+1与同outer GT诊断；核完整合成5×4和数值边界，并审20+1代数等价。两项g窄复审无法替代。
4. **负责人预算裁决：**1200/3600/900s、60s余量/接受边界、RSS与worker定义及强制路线、2/4 GiB、D_A/B/N/S/M和两式；逐控制路径及Windows observer的具体磁盘/RAM/task cap、共享VHDX增量政策、numeric tolerance及20+1语义。宿主可信与两个独立8 GiB解释已经确认，无需再批准一次。
5. **最后单独A+B批准：**所有P1和预算先闭合、旧卡scope笔误同步、最终hash卡获完整独立PASS后，负责人再明确批准同一具体卡。当前不请求以“待补证条件”提前放行，不构造 `FROZEN_ADMISSION`。

Route3 v1-003保持合法 `COMPLETE`、四门 `FAIL`，不重跑；gap=0由路线二覆盖。只有用户提供合法路线二结果后，才讨论三个架构方向各自的最小验证；任何路线二终态都不自动授权后续方向。本轮止于这份可审讨论稿，仍无实验准入PASS。

## 2026-10-02 整合后修订：负责人要求推进后的组件实现

“开始推进”用于落实准入准备代码和纯合成测试；不构成完整 A+B 条件卡批准。准备视图仍 `PREPARED_UNREVIEWED`，A+B未授权、`FROZEN_ADMISSION=None`，Stage A/B均未合法运行，没有路线二合法结果。完整 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL；此节不是新正式 review，不新建交接包。

已实现 bootstrap 单次 live proof登记及 [admitted_execution.py](../../src/eating_event/route2_candidate_overlap/admitted_execution.py) 的同 PID/thread 固定 runner 接续。真实尝试消费后，后续校验/runner异常也不允许重试；重构proof、全局身份替换、已启动guard/ledger、ledger分离、路径或预算/controller/write-volume错配均拒绝。授权由原受保护配置/密封件/review/owner/snapshot验证提供，live proof不是独立授权签发者。

这条接续 API 没有接入现有 launcher 的生产装配。实际 `ResourceEnforcer` /完整 `SupervisorOps`、全部worker写路径、GT真实phase lease/FD teardown、terminal后外部wall和完整RO运行闭包仍有P1；不能因组件测试通过而关闭整体验收。

Windows CPython3.10.11 与 WSL CPython3.10.12 已在**未冻结工作树**执行最初14个Route2合成文件（215项，各自通过）。随后新增接续补充检查，最终完整计数/范围待下方核验记录。WSL使用既有锁定venv的数值包及系统pytest6.2.5，`pythonpath`配置warning由显式测试import路径处理；Windows pytest9.1.0。命令禁用bytecode/cache；未重跑4GiB scratch或墙钟探针，未打开项目数据/GT，未创建正式image/volume/root/ledger/lock。

一次 `pytest tests -k route2` 尝试仍收集到其他路线文件，因缺少torch在收集期失败；随后改用明确的 `test_route2*_synthetic.py` 文件集合。该失败不是路线二实验或准入结论，也没有为此安装依赖或运行其他路线。

revision-g 原始证据/快照保持原身份；新代码尚无新冻结manifest和正式review ID。控制层cap/计费、原budget强制路线、20+1与数值容差仍待负责人裁决；Windows宿主owner可信和两层各8GiB已有确认，不重复请求。Route3不重跑、gap=0覆盖和合法路线二结果之后才讨论后续三方向的限制保持。

### 扩容组件、独立窄复核与最终合成核验

[linux_volume_backend.py](../../src/eating_event/route2_candidate_overlap/linux_volume_backend.py) 实现**既有卷**的固定2→4GiB扩容，不创建卷或签发准入。它重新验证受保护config/key/seal中的review/owner/card pins，读取root-only账本并回放链、Stage A完成和Stage B投影门；核image inode/device、loop backing/容量、ext4 UUID/mount、cgroup独占及无活动view，账本与parent实际fsync后才触碰镜像。通过已打开descriptor执行ftruncate、loop容量ioctl及限定argv的resize2fs，重复核同一身份；外部O_EXCL持久attempt marker阻止部分失败后的新实例重试。返回receipt仍需controller实际落账并fsync。

控制层新增路径 `/var/lib/route2-controller/volume-expansion-attempts/route2-candidate-overlap-v1-001.attempt` **未创建**；其目录安装、字节cap、卷归属与计费必须补入原条件卡的控制层预算，不默认为免费，也不把8GiB floor当成费用上限。正式双层live采样、首次建镜、统一startup/lock/ledger所有权、完整ResourceEnforcer/SupervisorOps及接线仍缺；本组件不能单独关闭这些P1。

接续组件的独立窄静态审阅先发现P1（负fit累计和未检查的残留账本/阶段状态）与P2（controller摘要大小写误拒）。新增33项回归先复现失败，再修复完整fresh状态检查及budget/controller digest规范化；相关53项Windows合成检查通过。第二轮静态复核确认这两项关闭、限定范围未发现新正确性问题；没有正式review ID，不构成A+B准入PASS。扩容组件的独立窄审阅结论见本节末尾两轮修订。

| 第一轮未冻结工作树核验（下述五处修复前） | 结果与范围 |
|---|---|
| Windows CPython3.10.11 / pytest9.1.0 | 明确选择15个 `test_route2*_synthetic.py` 文件：**323 passed / 9.03s**；`-B`、`-p no:cacheprovider`。 |
| WSL CPython3.10.12 / pytest6.2.5 | 同15个文件：**323 passed / 6.53s**，1个既有`pythonpath` warning；`-I -B`，显式worktree src/root与锁定venv数值包测试路径，禁用pytest cache。不是正式生产import或RO运行身份验收。 |
| 变更绑定 | 下表6个代码/测试文件在最后两端套件前后SHA-256一致；这不是完整source/runtime manifest。 |
| 单进程Linux依赖可行性 | 使用真实soft/hard `RLIMIT_AS=2147483648 B`、五种数值库线程环境=1，30s外部timeout；200行概率/100迭代的现有HGB合成函数完成，elapsed=1254496502ns、Threads=1、VmSize=325404KiB、VmRSS=146100KiB、peak RSS=149606400B。仅支持这一合成负载的依赖可运行性；没有study cgroup、controller/helper拓扑或全study强制证明。 |
| 默认拒绝态 | 新解释器只import contracts/bootstrap，确认 `FROZEN_ADMISSION=None`、live proof登记=None；未调用bootstrap或实验入口。 |

| 第一轮代码/测试文件（下述修复前，保留历史绑定） | SHA-256 |
|---|---|
| `src/eating_event/route2_candidate_overlap/admission_bootstrap.py` | `38cce6d193ae59191d7bb33ed2f76a5503b2b4051c3d58f43acbcb782be48e6e` |
| `src/eating_event/route2_candidate_overlap/admitted_execution.py` | `1ebff25304024879f200bde33b18bc04fdbe09951c2877f5ca39e073f5738778` |
| `src/eating_event/route2_candidate_overlap/linux_volume_backend.py` | `66e44dab8fafe643d5b6143ddcfad10a090d188f84b9a36fcf6fe433c8157fa3` |
| `tests/test_route2_admitted_execution_synthetic.py` | `2f7b6790672c700f5d0cd86ae9aabb2998a2a51f86929c4faf82d5fffbe826f3` |
| `tests/test_route2_admission_bootstrap_synthetic.py` | `d0f652a5ba4bf8583eb51971db867c4d50bdd79b814ef43717e2688209fdcbcd` |
| `tests/test_route2_linux_volume_backend_synthetic.py` | `6d39d6bf0512c9775eb36d9046200af7de11754fa737d7d8cd7bba50dafe1d7c` |

这些测试与新依赖可行性检查均只用合成输入，GT/project inputs=0；没有执行真实loop操作、Stage A-only/A+B或Route3。本轮代码未提交，现有工作树改动保留。后续优先推进统一startup所有权与生产OS/phase/observer装配，再做受限合成OS全生命周期；最终冻结、完整独立review和预算/协议确认完成后，负责人单独批准同一具体hash卡才能运行。

### 扩容第一轮窄审阅发现及第二轮修订

扩容独立窄审阅在上述323项合成通过的版本仍发现3个P1和2个P2，初版原语不可接受。修订如下，第二轮限定回执结论见本节末尾，不由测试自行宣布关闭：

| 问题 | 当前修订与拒绝证据 |
|---|---|
| P1 attempt payload部分写/fsync失败时，目录项未先持久化 | 先创建empty tombstone，file fsync与parent fsync都成功后才写payload；后续payload短写/同步失败保留已持久占位。首次同步失败仍是未证明持久化的失败，禁止触碰镜像；整invocation不可重试/外部隔离仍依赖待实现controller。文件同步不能代替目录同步，依据[Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)。 |
| P1 outside-study路径可能是同研究卷的bind alias | 在已打开的attempt目录FD上比较st_dev，等于实际study卷device则在O_EXCL创建前拒绝；不能仅依据路径前缀或root权限判断计费卷。 |
| P1 activity时间未参与gate回放 | 核真实BudgetGuard字段集、exact-int start/end/elapsed/invocation-wall/fit-wall，校验多次monotonic采样次序、stage边界及ceilings；Stage A累计fit必须0。 |
| P2 错误/空cgroup能作无worker证明 | 对照 `/proc/self/cgroup` 中当前controller的确切统一cgroup路径；成员必须恰为当前PID，目录FD与可见路径身份重复核对并跨checkpoint比较，迁出/重建/空组/额外线程均拒绝。 |
| P2 FIFO在type检查前可阻塞open | 初次object open增加O_NONBLOCK，再对FD核真实类型；wrong-type拒绝时关闭FD。该flag不能使fsync/ioctl或普通文件IO变成有硬wall保证，依据[Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html)。 |

新增直接OS-port mock回归7项及gate/cgroup回归50项；旧成功fixture修为合成实时cgroup绑定，单独扩容检查128项通过。**最终17个Route2合成文件：Windows CPython3.10.11 380 passed / 9.04s；WSL CPython3.10.12 380 passed / 6.61s、1个既有pytest warning。**测试入口和no-cache/no-bytecode边界同上；下列8文件在最后双端套件前后hash一致。

| 当前修订后的变更绑定 | SHA-256 |
|---|---|
| `linux_volume_backend.py` | `e7a01819920aa6ae6fae7a747e7f0df2c403e8ea9139652bfe5fac507d7ce2a2` |
| `test_route2_linux_volume_backend_synthetic.py` | `52551716471557bab64b34c93b33df29ed52df90cd336c5892b14c31bc4c3896` |
| `test_route2_linux_volume_os_revision_synthetic.py` | `3706e4a5456706806971e6d72e5fb491ee154393a3f2e5a19dba87d9a41428f8` |
| `test_route2_linux_volume_gate_revision_synthetic.py` | `855d294d7053e9a1ff506f39055a3753154c8c9049f0813dce4e2a5c744027b8` |
| bootstrap、admitted_execution及其两个测试（上表其余4文件） | 各自hash保持上表值；8文件的前后比较全部相同。 |

**仍不可提升为完整准入：**扩容fixture的四个summary事件不是完整105 reference与105 treatment事件回放，不是完整5×4或全GT lifecycle验收；原语没有为阻塞fsync/ioctl提供外部wall强制。必须由最终controller绑定完整合法Stage A账本/产物与单次startup所有权，并在受限合成OS全生命周期验证全resource/GT/write/terminal/RO身份。第一轮目录同步失败的跨崩溃隔离、完整外部stop/验收和控制层cap/计费均仍须闭合。当前完整review **FAIL / NOT_APPROVAL_READY**，视图 `PREPARED_UNREVIEWED`，`FROZEN_ADMISSION=None`，没有真实合法Stage A/B或路线二结果。

**第二轮扩容独立窄静态复核回执：**核对本节修订hash，五项发现均已在原语限定范围处理，未发现新的范围内阻断。attempt持久性只在empty tombstone的file/parent同步都成功后成立；首次同步失败保持未证明持久化、镜像修改前中止。复核未独立重跑380项测试，未提供正式review ID，没有实验准入PASS。外层全局一次性failure ledger/quarantine及生产完整链仍MISSING；完整review结论仍FAIL。

执行记录：本轮在用户指定既有worktree本地实现接续组件，单一implementer处理扩容组件；两个独立只读审阅分别执行两轮限定复核，发现后先补合成拒绝回归再修复。未并行改同一方法，未新建分支/交接包或提交；预算和协议的未答裁决不按沉默视为批准。


## 2026-10-03 整合后修订：统一启动所有权与完整 Stage A 回放（准入准备）

用户后续“继续补齐缺口”继续授权准入代码及无项目数据的合成验收，不构成真实 Stage A-only/A+B、输入/GT 读取或正式对象创建批准。四项状态分别保持：准备视图 PREPARED_UNREVIEWED；A+B 未获授权且 FROZEN_ADMISSION=None；Stage A/B 均未合法运行；路线二没有合法结果。完整独立 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL。

### 本轮实现的责任边界

1. **单一启动创建者。** `BudgetGuard.start` 通过同一具体控制器准备 image/OS envelope，`AppendOnlyLedger.create` 独占创建研究卷内 root/lock/ledger。`admitted_execution` 必须绑定同一个 fresh `Route2Supervisor`、approval 对象、guard、controller、invocation、clock、预算及路径；Supervisor 从 owner 的实际 FD 和磁盘上两条 canonical/hash-chained 启动记录核验，只读接收启动。绑定后旧 Supervisor 建镜像/建锁及 phase/terminal 写入口拒绝，防止两条生命周期重复创建或追加。未绑定的旧 port-ordering model 仅保留组件用途，不能作为 admitted runner 的第二创建者。
2. **占位与失败处理。** 研究锁先 O_EXCL 创建空 tombstone、file fsync、parent fsync，再写 payload 和创建 root/ledger；账本首次 append/fsync 后同步其 parent，最后记录完成 clock。同步/写入失败 poison、关闭 writer FD、禁止相同对象重试。bound guard 的 prepare/create/observe 失败消费启动、调用同一外部 controller 的 `abort_startup`，核 detach/quarantine/durable-failure/no-retry 收据；缺收据继续拒绝。首次 parent/file 同步失败仍不证明跨崩溃持久化，外部 pre-image attempt/failure ledger/quarantine 的真实实现仍缺，不能由本组件承诺全局一次性。
3. **扩容不再只认四条汇总。** `stage_a_replay` 从 canonical 持久账本重建 105 reference 完整通过后 105 treatment 的 reservation/result，核固定 5+20+80 role 集合、exact attempt、唯一产物路径、count/hash/schema、按 reference/treatment count+interval fingerprint 推导差异，并从角色候选数及固定训练图重算 N/B/M/S，交叉核 D_A 与 entry projection。四 summary-only、缺/多/重/错序角色、未知事件或虚报差异/投影均拒绝。它的结果明确为 LEDGER_METADATA_ONLY，不能证明当前产物 FD/bytes 或为 compromised writer 签发能力。实际产物核验正在接入，最终范围与回归回执追加在本节后。

上述目录持久性依据 [Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html) 的文件与目录分别同步要求；O_NOFOLLOW/O_CLOEXEC/O_NONBLOCK 的边界依据 [Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html)。O_NONBLOCK 不为普通文件读写/fsync/ioctl 提供墙钟强制，生产外部截止仍必需。

### 仍需补齐及负责人的待裁决

- 真实 `ResourceEnforcer + SupervisorOps` 单一生产 adapter：image 创建、建镜像前同 invocation 双层 live free sampler（guest backing 与 VHDX Windows 实体卷分别至少 8,589,934,592 B）、pre-image durable attempt、启动失败隔离、controller 保护及 launcher/bootstrap/完整 runner 装配。宿主账号 owner 可信与双层 8 GiB 已确认，不重复申请；其他控制层路径/cap/实际卷/峰值归因仍未批准。
- 后续 phase/terminal 对既有 guard 持久事件的只读适配与实际 append/fsync 扩容 receipt，完整研究进程 RSS/tasks 与所有写路径强制，GT 逐 role/phase live mount、同 FD hash 后读取、worker/后代/FD teardown 及撤销证据。当前统一的是 startup；bound Supervisor 的后续外部观察接线仍缺。
- terminal close 后独立 Linux monotonic/Windows QPC 退出与 cgroup-empty 验收、最终外部 anchor 持久化计时；stdlib/native loader/动态库/helper/unit/controller/observer 等完整只读运行期闭包；纯合成完整 5×4 及科学协议/调用额度/数值等价独立复审。COMPLETE 不能由 runner 内部返回值或本轮测试产生。
- 原 1200/3600/900s、wall 内 60s 余量、保守全研究 RSS/task 方法、2/4 GiB、D_A/B/N/S/M 两式，20 GT evaluator+1 GT-free pooled algebraic reduction，跨 OS 数值容差及所有外层写入预算仍待明确。未答问题不视为批准。控制层 cap 不能用双层 8 GiB floor 替代。
- 最终源码须重新冻结并独立完整复审；revision-g snapshot/manifest 不改，本轮工作树代码不属于 g manifest。当前唯一条件卡仍 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；补齐 controller/完整身份/输入 attestation/预算与正式 review ID 后，才由负责人最后单独批准同一具体完整 A+B 卡。

本轮未启动 Stage A-only/A+B、未读取项目输入或 GT、未创建正式 image/volume/root/ledger/lock。合成测试的临时 journal 与 fake volume receipts 仅属于临时夹具；没有执行真实 loop 操作。未提交，新旧工作树改动保留。Route3 v1-003 已合法 COMPLETE、四门 FAIL，不重跑；gap=0 已覆盖；只在用户提供合法路线二结果后讨论三个架构方向最小验证，不自动启动。


### 启动窄复审修订与最终双端合成记录

启动第一轮独立窄审阅找到 2P1/2P2：FD close 再抛错跳过 abort；绑定后的 controller/clock/invocation 漂移；同值大写 budget digest 误拒；actual lock 删除/替换未检查。先补拒绝回归再修复：新 live `startup_ownership` registry 独立冻结原 owner/controller/ledger/预算/路径/clock/invocation/PID/thread，prepare 前后及启动观察边界对照；失败使用原绑定清理，关闭 FD 异常仍走 abort；锁 payload fsync 后记录实际 stat/hash，观察时核 held/visible 及内容；digest 大小写归一。第二轮又指出清理依赖可变 `_budget_guard`，收尾改为仅查 registry 的原 owner，prepare 实际进入记录在独立 WeakSet，进度字段清空不影响 abort，失败强制消费 start。独立限定收尾复核确认该 P1 关闭；当前四项发现均在指定启动范围内处理，无正式 review ID，未独立复跑测试，不是完整 A+B 或实验准入 PASS。

扩容本轮已实际接入三个准备层：① 105+105 及两个唯一活动的持久回放；② 外部 seal 中 `role_input_registry_sha256` 认证的完整 canonical safe registry bytes，独立重建 5+20+80 role topology 后比较投影；缺 bytes、SHA 不符、只换 graph hash 标签或角色关系均拒绝；③ 同研究卷 105 个受保护普通文件的 held FD/advisory locks，64 KiB streaming SHA/精确字节/换行行数/EOF及前后、whole-set身份围栏，每个扩容 checkpoint 重哈希并在之后复核 quiescence。所有 FD 在失败时均尝试关闭，close 失败不 blind retry 同一 descriptor。

metadata registry bytes 的未来真实供应必须由已批准的 preflight_metadata RO path-map/classifier/controller 实现，本轮只构造完整合成注册列表，未读取真实注册/输入。Byte verifier 不解析候选 JSON 语义、不重算 interval fingerprint、不证明 reference/input provenance；其 advisory locks 只保障可信控制器是唯一授权 writer 的边界，不能限制另一个特权 root writer。原全局 startup attempt/quarantine、外部 wall、真实 controller/GT 生命周期、全只读闭包和科学协议仍 P1，完整 review 仍 FAIL。

**最终测试：20 个 `test_route2*_synthetic.py` 文件，Windows CPython3.10.11 656 passed /30.10s；WSL CPython3.10.12 656 passed /25.88s、1个既有 pytest6.2.5 unknown-pythonpath 配置 warning。**固定显式文件列表，以 `-B -m pytest ... -q --tb=short -p no:cacheprovider`；Linux 使用 `/usr/bin/python3 -I -B`、仅将当前 source/root 与既有 pinned venv site-packages 加入解释器路径。不运行全 tests collection、不安装新依赖、不重复 cross-OS 模型探针或真实磁盘/cgroup/wall 探针。这不是数值等价验收；原 194/200 位级相同仍 PARTIAL_MATCH_ONLY，容差待确认。

50 个当前 Route2 package源码/上述合成测试/三个既有脚本的内容 SHA 在最后双端套件前后相同；按相对 POSIX path→lower SHA 映射、sorted-key compact JSON 编码，聚合 SHA `2780cb395e270813ed04b68069853841d109ad094530aaf43abde52220013a59`。此映射只绑定本次准备回归，不是新的完整 source snapshot manifest，不覆盖输入/runtime/stdlib/native/controller安装，不签发批准。revision-g 保持原样。

| 本轮源码 | 最后回归绑定 SHA-256 |
|---|---|
| `budget.py` | `8427ad2ecb85e4e26fea194f6001d28a09efa456584824117d44a775ae7cb6af` |
| `linux_supervisor.py` | `c75e31c3ccac7a8c88e69a6ef9f0544ea1e6a63b1cde96f10153b31aaf5eccba` |
| `startup_ownership.py` | `640cb5f4f5bf6ea2332fb69fa988c874282c1f0ea0c5173004560600f0d01341` |
| `admitted_execution.py` | `24e956dfbae2066ec054cbddd8a89e9226ce96e24e0f6ac156a4fb3194e37853` |
| `stage_a_replay.py` | `e8f74c1f3b08254375228546b8bea13c7044875215ec04a3dd9a1b5abdea24fc` |
| `linux_volume_artifacts.py` | `92e6741588b4c7c48b635af20456da8dd30a310790a655a3b6850a0c16d83481` |
| `linux_volume_backend.py` | `517ad8b87e3605c517077bc693e1df56a0f822b00e0026b650c3b537cbe7b100` |

新源码默认 fresh Python import 检查 `FROZEN_ADMISSION is None`、bootstrap live issuance is None；未创建正式对象、未读取项目输入或 GT、未运行合法 Stage A/B，无合法路线二结果。上述准备回归不能改变 PREPARED_UNREVIEWED / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，所有待批预算/20+1/容差继续待批。上述656项与50文件绑定是后续FD修复前的历史准备记录；最终限定回执与最新回归见下节，不由测试自行关闭审阅。

### 扩容限定复核收尾与最新674项准备回归

扩容第二轮独立静态复核确认：未独立认证role topology的P1、正候选数配空流hash的P2以及两个完整活动边界缺失，均已在本组件范围处理；固定合成注册图的独立手算核得 N=365、M=139、S=103。该结论只核metadata回放与产物bytes保护，不证明候选JSON语义、interval fingerprint重算或reference/input provenance，也没有正式review ID。

该轮另发现 concrete OS-port 的临时FD清理P2：逐级打开目录时old FD close报错可能泄漏新FD；目标FD已打开但parent close报错时可能无法交接也未关闭目标；attempt FD close报错可能跳过parent清理。现改为显式持有列表，先移除/转移所有权再close，失败仍尝试其余FD，成功仅交接仍持有的FD，不盲目重复关闭旧编号。新增18个mocked-syscall用例；先9项RED，再18项GREEN，覆盖原三条路径、关闭后报错、多个close同时失败及成功交接。Linux close报错后descriptor可能已释放，重复关闭可能影响重用编号，依据[Linux close(2)](https://man7.org/linux/man-pages/man2/close.2.html)；这不替代fsync或外部墙钟强制。

**最后独立限定静态复核确认剩余FD清理P2关闭，未发现新增范围内P1/P2；审阅前后下表两文件SHA一致。**审阅者未修改代码、未独立运行测试或真实探针、未签发正式review ID。启动与扩容这两个窄范围的发现关闭不改变完整独立review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 的FAIL结论，不构成实验准入PASS。

| 最新准备回归 | 结果与边界 |
|---|---|
| Windows CPython3.10.11 | 显式21个 `test_route2*_synthetic.py`：674 passed /33.54s；禁用bytecode和pytest cache。 |
| WSL CPython3.10.12 | 同21个文件：674 passed /27.98s；1个既有pytest6.2.5 unknown-pythonpath配置warning；入口与上节相同。 |
| 当前文件绑定 | 51个Route2 package源码/上述合成测试/三个既有脚本，测试前后内容SHA全部一致；sorted-key compact JSON的相对POSIX path→lower SHA映射聚合SHA为 `b045636bbf94d96c8d71ceda8d8f2020eec1e59248d5891b9c5e616d4303c670`。 |
| 范围 | 仅合成输入和临时夹具；没有真实loop、项目输入/GT、正式对象或合法Stage A/B。此映射只绑定回归，不是完整source/runtime冻结manifest或跨OS数值等价证据。 |

| FD修复后的当前绑定 | SHA-256 |
|---|---|
| `linux_volume_backend.py` | `1bb2698f0a34cbf8b0a2811adb24266571d73a6001a96346a9a41cdd8029a328` |
| `test_route2_linux_volume_fd_cleanup_synthetic.py` | `fbaabcd0143f0ebca22c6ed9f87dcf56e3c4ecb44fa872662bef85ccaf82f518` |

上节656项/50文件聚合SHA及 `517ad8…` backend SHA保留为修复前历史绑定；本节674项/51文件及 `1bb269…` 是当前准备回归依据。其余上表源码SHA不变，revision-g受保护snapshot及manifest未更新，本轮代码尚未正式冻结、未提交。

**下一处实现断点仍是完整生产装配。**需将同一个生产ResourceEnforcer/SupervisorOps、建镜前双层live检查与持久attempt/quarantine、bound phase/terminal只读观察、扩容receipt落账、真实RSS/task/全部写路径与逐role/phase GT撤销，以及terminal后外部墙钟验收接成一条完整链；随后补完整只读运行身份、输入attestation、纯合成5×4和科学协议/数值等价独立复审。已确认的宿主账号可信与两层各≥8GiB不重复申请；其余预算、控制层cap/计费、20+1归并及数值容差仍待负责人裁决。独立完整复审和同一具体hash卡的单独负责人批准仍缺。

四项状态分别保持：①准备视图 `PREPARED_UNREVIEWED`；②A+B未获授权、`FROZEN_ADMISSION=None`；③Stage A/B均未合法运行；④路线二没有合法结果。没有新建交接包或改授权卡，本轮结论只写回原设计、执行计划与本review的整合后修订。Route3 v1-003合法COMPLETE、四门FAIL、不重跑；gap=0已由路线二覆盖；三个架构方向只在用户提供合法路线二结果后讨论，不自动启动。

### 同轮追加：phase单写者只读接续与811项最终准备记录

继续补齐后续phase接线。BudgetGuard仍是唯一账本写者；Stage A结束、Stage B入场、同卷扩容及Stage B完成各自在owner append/fsync成功、原deadline检查后，由同一bound Supervisor只读观察。entry观察在调用物理扩容前，expansion观察在设置admitted及启动工作前；没有调用旧Supervisor的第二套append/expand入口。原终止后的外部验收接线仍缺，内部返回不能作为合法COMPLETE。

新 `phase_observation` 在真实startup序号2冻结两条record digest、原writer FD的device/inode/mode/nlink/uid、独立原approval角色图pin及startup payload。每次观察通过真实只读FD按64KiB读取至多16MiB，核EOF、canonical完整hashchain、held/visible/owner身份与size/mtime/ctime前后围栏、live seq/tail及唯一末尾phase。私有顺序固定 A-boundary→B-entry→expansion→B-complete；pending proof只允许原对象一次accept，复制/改写/跨thread/PID/FD替换及复原公开进度均拒绝。后续clock/RSS/volume/Stage A/entry/projection/expansion对照独立保存的startup与accepted payload，失败消费私有observer且阻断后续work。

初版phase的23文件双端764项通过时，独立窄审阅仍发现1个P1：健康observer只接受Stage A后，伪造公开 `_stage_b_admitted=True` 可进入operation，finally资源拒绝太晚。补两个healthy invoke/activity用例先复现RED，再增加私有 `require_owned_work`：无pending且尚未接受任何phase时只准Stage A非fit；仅接受前三个phase、确已接受expansion后准Stage B；中间阶段、完成、失败及非exact-bool均拒绝并poison。activity在backend调用前、invoke_call在reserve/started追加前检查。新增43项helper拒绝回归；公开admitted伪造、completion字段复原和poison进度复原均要求operation/backend调用及journal增量为零。最后137项阶段组件测试通过，独立限定静态收尾确认此P1关闭、未发现新的范围内明确P1/P2，五文件SHA审前审后一致；审阅者未独立跑测试、未签正式review ID。

一次联合验收曾有两个fake即时扩容与entry fsync同刻的失败；Windows CPython3.10.11实测monotonic为GetTickCount64、resolution=0.015625s。只把零工作量fake controller改为等待下一tick，生产严格after比较、门及预算未改。真实Linux扩容、阻塞syscall的外部wall保证仍没有新增验收证据。

| 当前最终准备回归 | 结果 |
|---|---|
| Windows CPython3.10.11 | 23个显式Route2合成文件，811 passed /38.49s；无bytecode/pytest cache。 |
| WSL CPython3.10.12 | 同23文件，811 passed /29.79s；1个既有pytest6.2.5 unknown-pythonpath配置warning；隔离入口、显式当前source/root与既有venv测试路径同前。 |
| 文件内容绑定 | 54个package源码/合成测试/三个既有脚本在最终双端套件前后SHA全部一致；相对POSIX path→lower SHA映射的sorted-key compact JSON聚合SHA：`4e5ca85ac49fb28edea884dddf168589c90e741c66fd3b60be627a52997f286c`。 |

| phase修补后的当前绑定 | SHA-256 |
|---|---|
| `budget.py` | `a03b2f2349f367bc9cc751a74ea5cd5ce6bca4a7ff8e571b96be9fe5b4ccc646` |
| `linux_supervisor.py` | `27c038a2b0798a448bb8156a0be98b8bc324566e51f793a0839b3492261f0756` |
| `phase_observation.py` | `2fff54c7671cd683fc9a2bc85f278c662b884b237894693e7b95e79be9d12189` |
| `test_route2_phase_owner_synthetic.py` | `81f7d243dce955edb2e2ed0fffdd240ed05253f2597e4c0e75acfe7fb1aab4d2` |
| `test_route2_phase_reader_synthetic.py` | `8b4b58f71872fd60e9e625afa974c456675ac3d1ace30a10f4d9d2b05d695164` |

656/674项记录继续保留为此前组件版本的历史绑定；中间764项聚合SHA `54a6fa4407fb26306287fac0710c477ef5daa60685b13999bca20bbf965687b2` 属于私有work门修补前版本，不能替代本节811项依据。FD扩容backend的 `1bb269…` 绑定保持不变。54文件映射只绑定准备回归，不是完整source/runtime冻结manifest；revision-g快照未更新，当前工作树尚未正式冻结、未提交。

**证据边界：**这里只核trusted owner/event provenance及私有工作阶段。两个测试文件共137项包含fake snapshot、人工role计数/COMPLETE metadata和纯合成408条固定调用事件与假model bytes；没有真实Stage A/B、项目输入/GT或科学结果。它不证明实际105重建来源、候选JSON语义/interval重算、真实资源/GT/挂载撤销或完整A+B等价。原完整独立review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍FAIL，窄范围关闭与811项测试均不得称为实验准入PASS。

**剩余准入缺口：**单一生产ResourceEnforcer/SupervisorOps与launcher/bootstrap/完整runner装配；pre-image全局一次性attempt及跨崩溃quarantine；建镜前两层live ≥8GiB检查；真实全研究RSS/task/全部worker写路径与控制层cap/计费；逐role/phase GT和worker/后代/FD退出撤销；terminal close后外部clock/退出/cgroup-empty/最终durable anchor验收；完整只读运行闭包和输入attestation；纯合成完整5×4及科学协议/数值等价独立完整复审。原预算、20+1代数归并、数值容差和外部写入费用继续待负责人裁决；宿主owner可信与两层各≥8GiB的既有确认保持。最终重冻、覆盖最终hash的正式完整review ID与同一卡单独负责人批准仍缺。

最终四项状态分别核定不变：准备视图 `PREPARED_UNREVIEWED`；A+B未授权且 `FROZEN_ADMISSION=None`；Stage A/B均未合法运行；路线二没有合法结果。fresh import未签发bootstrap live proof。没有创建正式image/volume/study root/ledger/lock、打开GT view、安装正式unit/config/key、执行真实loop或重跑Route3；未改授权卡、新建交接包或提交。Route3 v1-003合法COMPLETE、四门FAIL，gap=0已覆盖；架构方向讨论仍只在用户提供合法路线二结果后进行，不自动启动。

### 2026-10-03 续补：初始建镜原语与 terminal 只读交接（准入准备）

本节续接既有“2026-09-29整合后修订”及同轮811项记录，作为当前追加状态；不新建交接包，不改原授权卡。负责人“继续补齐缺失／继续工作”只推进实现与纯合成验证，未构成一次正式A+B授权。四项状态分别保持：①准备视图 `PREPARED_UNREVIEWED`；②A+B未授权、`FROZEN_ADMISSION=None`；③Stage A/B均未合法运行；④路线二没有合法结果。完整独立实现复审 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍为 **FAIL**。2→4GiB同卷scratch、13-wheel依赖、原21项/203项以及后续合成套件均只是准备证据，不得称为实验准入PASS。

| 本轮补齐的代码与证据 | 仍缺的生产证据、选择及代价 |
|---|---|
| `linux_initial_volume.py` 新增初始2GiB原语：验证root保护的完整A+B seal；单独initial policy绑定整个fullAB seal SHA；核本进程已消费的只读bootstrap；先O_EXCL空attempt、file/parent fsync、再有界payload同步；任何后续失败保留占位。同一held parent FD经过双层采样直到exclusive image create；posix_fallocate预分配2GiB、固定loop ioctl/mkfs/mount、格式化前与之后核actual backing inode/flags/capacity/UUID/mount。 | 这不是完整ResourceEnforcer或SupervisorOps，未装配、未物理调用。缺保护目录/控制卷安装边界、系统崩溃与跨进程失败quarantine/持久失败账本、真实OS后果与原guard装配。initial attempt与既有expansion attempt分别保留；不能把空tombstone当作初始化fsync失败后的跨断电持久证明。预分配会增加建镜写入和时间，计入从invocation开始的Stage A墙钟；仍需outer强制停止。 |
| 双层各≥8GiB代码门：held ext4 parent/statvfs与actual covering mount；新增只读Windows sampler精确HKCU Lxss GUID/distro/BasePath/VHDX映射，held VHDX HANDLE取volume GUID，对同一GUID查询available与total-free，分别取保守下界；nonce绑定同步响应，Linux clock包含整个采样，不混用QPC epoch。创建前再次核covering mount ID/dev、freshness与Stage A deadline。 | Windows账号owner可信与两层各≥8GiB已由负责人确认，无需重问。尚缺正式launcher把实际WSL实例与注册VHDX连续绑定、held Windows可执行文件/脚本的实际运行身份及worker不可写安装证明。`require_host_execution_boundary` **默认拒绝**，前后hash不证明中间执行bytes。继续WSL需补此生产边界；若改为限制可信host登录用户，则需独立受控Linux runner及其部署成本，不自动切换。 |
| `terminal_observation.py` 注册原owner/ledger/controller/clock与私有accepted phase锚；原BudgetGuard仅写一个terminal；关闭前持有readonly anchor，actual canonical完整链/lock/tail/result SHA/时间与原FD身份有界核验；私有native close事实记录真实attempt与成功，不能由公开字段重置或EBADF单独制造。关闭/读取/绑定失败消费机会，释放anchor并对原writer一次清理，不盲重试同号FD。`observe_budget_terminal_close`只交接到`TERMINAL_PENDING`。 | `_require_controller_quiescence` **默认拒绝**。真实逐role/phase GT、全部worker及后代/遗留FD撤销源仍缺，不能据helper自述签发生产close receipt。还缺退出后的独立observer、inactive service/cgroup-empty、terminal再次核验、Windows QPC最终durable anchor及完整外部墙钟验收；本进程close metadata不是ACCEPTED，也不是合法路线二结果。 |
| 原扩容门继续使用完整105+105元数据回放、105个artifact held FD/hash与正式2→4GiB gate原语；terminal现在固定私有阶段前缀、COMPLETE要求健康accepted四阶段、result摘要匹配。 | 整study RSS/task强制、全worker写路径、真实role/phase mount轮换与撤销、完整输入/只读执行闭包和完整5×4合成科学等价仍待补齐。现有artifact字节核验不代替候选JSON/interval语义、来源及重建独立复审。20个GT-backed评价+第21次GT-free代数归并已是当前代码提案，协议裁决与跨OS容差尚未批准；不把合成COMPLETE metadata当实验COMPLETE。 |

**控制层预算仍待决定：**单独sealed initial policy的 `attempt_cap_bytes` 与 `max_free_sample_age_ns` 显式必填，无负责人默认值；前者只是该marker的逻辑payload写入上限，**不是**控制卷实际allocated blocks的OS硬cap，也不包含其parent metadata、失败账本、扩容attempt、loop/VHDX增量、mkfs/systemd journal或外部墙钟锚。正式卡必须逐项选择“纳入4GiB研究预算”或“另列有硬cap的控制预算”，说明loop镜像与内层文件占用如何避免重复计费，并分别列VHDX实体增量、journal与外部锚的控制费用。预分配不是免费准备证据。原RSS/worker方法、1200/3600/900s与60s收尾占墙钟、所有外部写入/准备探针费用、pooled20+1和数值容差继续待负责人裁决，未推断沉默为批准。

**最小一次完整A+B条件授权卡（仍为草案）：**唯一研究ID `route2-candidate-overlap-v1-001`；状态 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`。同一卡固定当前完整source/runtime/input/view/role graph/controller/launcher/worker/backend及协议SHA；附独立完整实现复审与安装边界/OS控制验收的正式ID；填全部研究与控制层cap/计费、采样freshness、RSS/task方法和墙钟规则；裁决20+1及数值容差；持久once/quarantine、双层live free、全写路径与逐role/phase撤销、post-exit外部验收任一缺证即拒绝。同一份明确负责人批准与root保护seal最后才可使单次A+B申请生效。没有Stage A-only、失败续跑或追加study ID。原授权卡尚未同步本轮hash，不可凭旧卡执行；后续需在批准前按允许范围同步，当前未改卡或制造批准对象。

**本轮限定审阅：**Poincare静态复核关闭mount ID类型、fullAB seal完整绑定、held parent/device与covering mount复查、held VHDX→GUID free查询、mkfs前loop核验、即时deadline/freshness及stdout有界读取/清理问题；保留Windows执行身份P1及全部生产装配/计费/quarantine/outer-wall缺口。Meitner静态复核关闭mutable linkage跳hooks、supervisor前置拒绝未消费handoff、异常close公开字段伪造成功、before-close hook异常遗留writer及同号FD误关闭问题。两者未执行真实OS/科学实验、未签正式review ID；只是限定问题关闭，不替代独立完整实现复审。旧手工创建临时journal测试仅在合成fixture显式seed私有close state，生产没有宽松fallback。

| 最终准备回归 | 本轮实际结果 |
|---|---|
| Windows CPython3.10.11 | 显式26个Route2 synthetic文件；`-B`、无pytest cache；**948 passed /45.02s**。 |
| WSL CPython3.10.12 | 同26文件，从当前工作树加载源码、只用既有pinned venv测试依赖；**947 passed /1 skipped /32.24s**；skip只针对Windows默认port平台拒绝检查；1个既有pytest6.2.5 unknown-pythonpath配置warning。 |
| 新组件范围 | initial volume 61项；terminal reader 66项；native owner接线10项。均为临时合成journal、fake资源/role/COMPLETE counters和mock syscall/Win32/kernel数据；未物理建镜、mount/loop/GT或运行Stage A/B。 |
| 内容绑定 | 60个package源码/合成测试/四个脚本，排序相对POSIX path→lowercase SHA的compact JSON聚合：`0e7432d0d2658dac0b8f049b07c953fdafce2c265be611e07777845f7ea92b06`；最终双端回归前后每个文件内容一致。仅准备回归绑定，不是完整冻结manifest。 |
| 默认拒绝与只读absence | Windows/WSL fresh import均为`FROZEN_ADMISSION=None`、issued bootstrap=None、terminal observers=0；WSL stat-only核formal image/volume/root/ledger/lock、两个attempt、initial-loop lock及supervisor/initial-policy配置均不存在。 |

| 当前关键实现 | SHA-256 |
|---|---|
| `budget.py` | `92e9bab1a66f22357c2c52da852a43060a916609de279f29b46b1cfd77261b6d` |
| `linux_supervisor.py` | `3d51767e654ccb10836d93164721a26cd9ee5a3a1dfe0258f62ab960e5d6c77f` |
| `linux_initial_volume.py` | `43350180585ee29af088b53d178f1bba08ef12eefb1ac4e305f6c598308894ab` |
| `route2_host_volume_sample.py` | `2dfa48e04ee3f254d6bd05448f99c73ed366a4f252dfbd63418d66e97d5941ee` |
| `terminal_observation.py` | `413fceefeb75c116460e188e9c84a75ac6926ffc54d4e831c93a78ab599f26ea` |

**仍须完成：**单一生产ResourceEnforcer/SupervisorOps与launcher/bootstrap/完整runner装配；Windows真实执行身份、pre-image once与跨崩溃quarantine及双层实时free的生产验收；整study资源/全部写路径/控制预算；真实逐role/phase GT+worker/后代/FD撤销；terminal后外部退出/双时钟/durable-anchor验收；完整只读运行闭包与输入attestation；完整5×4合成、科学语义与跨OS数值等价的独立完整复审；最终完整重冻与全部正式review ID；同一卡预算/协议/容差与明确负责人批准。revision-g准备快照、13-wheel依赖和原cross-OS `PARTIAL_MATCH_ONLY`未重新冻结或升级结论。

没有创建正式image/volume/study root/ledger/lock/config/key/unit，没有打开项目输入或GT view、启动Stage A/B、重跑Route3或任何架构方向；未提交。Route3 v1-003仍合法COMPLETE、四门FAIL；gap=0已由路线二覆盖。只有用户提供合法路线二结果后才讨论三个架构方向各自最小验证，不自动启动。

实现接口参考：Linux固定loop配置及容量核验依据[loop(4)](https://man7.org/linux/man-pages/man4/loop.4.html)，固定mkfs参数依据[mke2fs(8)](https://man7.org/linux/man-pages/man8/mke2fs.8.html)；Windows held-handle卷GUID和同卷free查询依据[GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)、[GetDiskFreeSpaceExW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getdiskfreespaceexw)。这些接口文档不构成本机正式控制层验收。

### 2026-10-03 续补：生产装配、真实身份与外部验收（待负责人裁决）

**状态依据仍为既有 review 最新整合修订，四项分别不变：**准备视图 `PREPARED_UNREVIEWED`；一次完整 A+B 尚未授权且 `FROZEN_ADMISSION=None`；Stage A/B 均未合法运行；路线二没有合法结果。完整独立实现复审 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍为 **FAIL**。2→4 GiB scratch、13 wheels、既有合成回归、窄静态审阅均只属准备证据。上一小节的 948/947+1skip 是上一批代码的历史回归，不能覆盖本节新增实现。

#### 最小预算裁决草案（预算确认不等于实验授权）

已确认且沿用：Windows 宿主账号所有者为可信主体；正式 image 创建前，WSL 承载文件系统与 VHDX 所在 Windows 实体卷分别 live ≥8 GiB。以下选择仍待负责人明确答复，未填默认批准：

| 项目 | 推荐确认内容 | 代价、缺证与替代方案 |
|---|---|---|
| 整研究 wall | Stage A 1200s、总 3600s、累计 fit 900s；60s 收尾预留在原 wall 内。外部 QPC 在身份核验和 WSL 启动之前开始；Linux 首样本在 bootstrap 之前。建镜、预分配、mkfs、哈希、全部清理与最后 anchor/handle 关闭均计入。Stage A 到 durable entry gate；2→4 扩容受总 wall。 | 实际可计算时间缩短；fit 为总 wall 子集，不另加 900s。生产 pre-bootstrap 首样本/launcher 连续性尚缺；独立外部观察者的 RAM/tasks 另列，不免预算。 |
| RSS/tasks | C=min(4 GiB, floor(3×启动 available RAM/5))；memory.max=C、swap=0、CPU200%；继承 LimitAS=floor(C/2)，TasksMax=2 **包含 controller**，因此通常只有一个计算 worker 槽。 | 这是对原 workers≤2、监控/I/O 另记口径的保守实施变更，须明确批准；可能地址空间不足。另一方案保持两个计算 workers，并另补整树 RSS 的真实强制方法，增加实现和独立复审成本。活跃 worker 时不能再 fork systemctl/采样助手。 |
| 研究磁盘与正式扩容 | 保留同一 image 的 2→4 GiB、原 N/M/S/B/D_A 两式及余量。逻辑 image、实际 allocated blocks、内层 FS 含 metadata 的占用分别报告；image backing 与内层文件不跨层重复相加。D_A 已含 B 时，原公式中的保守重复预留继续保留。 | image 外层 extent/inode/VHDX metadata 不能凭文件长度免费排除。预分配及失败后保留 image 均占账；删除不抵既有峰值，复制 quarantine 另收费。确切计量与硬 cap 边界待 owner 裁决及 OS 证据。 |
| 控制预算候选 | 独立 guest64 MiB（67,108,864B）和 host16 MiB（16,777,216B）仅作为容量候选，先固定最坏持久化内容和失败收尾空间，再确认额度。包括 attempt、失败账本、quarantine metadata、role receipts、systemd journal、host core/seal/临时副本。 | 80 MiB 名义容量不是 host 实体总 cap。guest 控制卷不能装研究 image；journal 写在其他卷即未覆盖；host 若复制完整 16 MiB ledger，加编码/副本/anchor 可超候选容量。本轮不复制完整 ledger 到 host，也不把 marker 的 payload cap 当 OS allocated hard cap。 |
| VHDX 实体费用 | 若坚持物理硬上限，推荐专用、可真实强制上限的承载边界，部署与最坏增量测量之后再定 cap；共享 distro 仅能保守记录全局 VHDX allocated delta。 | 共享 VHDX 的采样不能证明 per-study hardcap。专用边界增加部署、迁移、基线空间、身份重冻与安装复审；当前不安装、不迁移、不自行给增量填零或硬 cap。也可选择独立受控 Linux runner，需重新核安装/预算边界；不自动切换。 |
| 采样与准备费用 | 候选 freshness 5s、单 marker payload≤64 KiB；只是待批方法值。依赖安装、快照、既有 scratch/probes、控制卷部署分别列已发生/未来一次性准备成本；未知记“待核”，不可填零。 | 5s 若不足覆盖完整同步 host sample 则拒绝，不能延长后补批准；逻辑 payload 限额不覆盖目录及 allocated metadata。需汇总原始回执和容量证据，不重跑探针。 |
| 第21项与数值 | 推荐裁决 20 GT-backed evaluator + 1 GT-free pooled reduction，pooled GT reads=0；TP/FP/FN 与误差和/匹配数代数归并，不平均各折 MAE/F1。 | 20+1 协议仍未批准。原 194/200 概率逐位一致、最大差 1.734723475976807e-18 仅 PARTIAL_MATCH_ONLY；概率/特征/指标容差、阈值/排序边界处理需事先确定并独立复审，不从已观察误差反推授权容差。 |

**一次完整 A+B 条件卡的最小必填集仍为同一研究 ID `route2-candidate-overlap-v1-001`：**完整 source/runtime/输入/视图/role graph/controller/launcher/worker/backend/protocol SHA；独立完整实现和安装/OS 控制复审正式 ID；上述预算及计量、控制卷/外部观察者额度、准备费用、freshness、20+1 与数值等价裁决；persistent once/quarantine、实际全写路径及逐 role/phase revoke、真实运行身份、post-exit 双时钟/最后 durable anchor 的验收证据；最后另有同一卡明确负责人实验批准和 root 保护 seal。预算确认或静态问题关闭均不使该卡生效；当前仍 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`。原授权卡未修改，也不能用其旧 hash 执行。无 Stage A-only、失败续跑或新 study ID。

#### 本轮负责人已确认与专用边界部署草案

本轮三项异步答复已收到，优先于上面的待批草案行：**已确认** A1200s/总3600s/累计fit900s、60s计入原wall，C=min(4 GiB, floor(3×启动available RAM/5))、LimitAS=floor(C/2)、TasksMax=2含controller（通常一个计算worker）；**已选择**专用可强制上限的承载边界，先补部署与容量方案；**已确认**20个GT-backed评价+1个GT-free代数归并、pooled GT reads=0。**数值容差继续待定**。这些答复不批准实验、安装、新探针或具体控制/实体磁盘额度，也不签发预算decision ID、正式review ID、seal或FrozenAdmission。

专用边界首选草案：新增专用WSL发行版与专用**实际NTFS卷/固定物理分区**，原共享Ubuntu与现有输入保持作为既有准备来源。volume GUID、物理device/partition身份、distro注册GUID和ext4.vhdx inode绑定同一卡；不选择、格式化或移动用户现有卷。若没有合适专用物理卷，备选是预分配完整固定容量host carrier，但须增加carrier→实际宿主物理卷拓扑证据与第三层检查，并将整个carrier一次性allocated容量计为准备成本；虚拟carrier free不能冒充实体卷free。两种方案都先形成安装清单/容量回执方案，当前不执行。

普通NTFS per-SID quota只能辅助限制被计入的数据流，不能单独替代本任务要求的物理总cap：官方定义按数据流长度收费，部分metadata不收费，压缩不改变quota账。因此不把“专用账号+quota”直接写成物理硬上限PASS；如采用quota，仍需独立容器/卷硬边界和SID/文件owner/全路径证明。[Microsoft Disk Quota Limits](https://learn.microsoft.com/en-us/windows/win32/fileio/disk-quota-limits)。

| 安装前必须形成的可审阅项 | 容量/一次性执行条件 |
|---|---|
| 存储拓扑及全部身份 | 指定实际物理NTFS卷或固定分区及其只读拓扑证据；冻结注册distro/BasePath/VHDX路径与Windows caller身份；专用边界不承载无关任务。没有指定设备，不生成格式化/分区命令。 |
| 先列准备成本 | B_base单列发行版OS、Python/13-wheel运行树、完整只读source/runtime快照、输入/视图准备副本、guest控制卷、host执行快照与控制区、FS/VHDX metadata和失败保留；未知值“待核”，不估成0。已有scratch/依赖/快照费用分别追溯，不复制整共享distro作为无费baseline。 |
| 确定容量Q | 先核格式化后可用容量与B_base实配占用；正式建镜前guest及实际Windows实体卷各仍≥8 GiB（必要时还核carrier）。因此不能只按“4 GiB研究image+80 MiB候选控制区”定Q。Q需包含baseline、live8 GiB门、最坏2→4/VHDX增长、控制/失败收尾、metadata余量；具体Q与guest64/host16尚待容量证据和负责人确认。 |
| 写路径及控制层 | 研究loop上限2/4 GiB单计；guest64/host16仅候选、分别真实硬cap。journald/runtime/tmp/stdout/stderr/cache/HOME、attempt/quarantine、role receipts、外部core/seal全部有固定落点；其他写入路径无证明即拒绝。host仅持久化必要摘要与anchor，不复制完整16 MiB ledger。系统基础写入若超出专用边界，必须另列费用/硬限，不能免责省略。 |
| 安装与恢复 | 专用环境的一次性安装、volume/controller/worker权限、boot/service/startup连续性、核定失败空间和原地quarantine先独立复审；不得搬运或重用正式study ID下部分账本，也不能删除释放空间后宣称未触峰值。现阶段不创建正式image/volume/study/ledger/lock/unit/config/key或distro。 |
| 安装后验收的前置预算 | 安装/容量/OS验收属于准备工作，需另有明确额度、对象、只合成数据范围与一次性操作清单。预算方法确认不自动批准任何真实探针。实际production安装验收、完整实现独立review及最终identity重冻未完成之前，一次完整A+B卡仍阻断。 |

WSL导入仅作为部署能力参考，尚无执行命令或注册动作；官方支持VHDX导入/原地注册，但是否满足固定边界与本机安装身份须另核。[WSL基本命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)。

另有**D_A计量裁决待确认**：方案A保留原“内层实际峰值”口径，补原生峰值来源（不能靠稀疏采样证明已删除文件的峰值）；方案B将正式gate中的D_A明确改为Stage A的2 GiB严格容量上界，用作保守投影，可能因高估而更早拒绝Stage B，但不能由此声称已测得真实峰值。若选择B，须重冻计量协议/预算SHA并独立复审，镜像实体收费仍另报告；当前没有自动选择B，生产适配器仍在原D_A来源缺失处拒绝。

#### D_A负责人裁决与本轮实现范围

负责人已明确选择**方案B：采用2 GiB严格上界，按新计量协议复审**。以上“待确认”段落保留为历史申请，当前决定以本段为准。生产预算必须显式填写 `stage_a_disk_accounting_mode=stage_a_capacity_upper_bound_v2`；生产controller policy升级为v2，固定该模式且绑定新预算摘要。通用合成/旧实现接口的默认 `stage_a_current_v1` 仅保留历史语义，**生产装配拒绝该模式**。新增字段改变预算摘要及账本schema内容；须重冻源码、协议/预算SHA与授权卡，并完成独立复审，不能沿用revision-g或原授权卡的旧hash。

V2中D_A固定为2,147,483,648B，通过同一实际2 GiB image、内层FS容量≤2 GiB及当前占用≤容量核验后用于正式gate；不是“已测得峰值”。`study_disk_current_bytes`继续报告实时内层FS占用；生产snapshot旧字段名`study_disk_peak_bytes`在V2中承载容量上界（Stage A=2 GiB，扩容后=4 GiB），不能用其生成真实峰值结论。原disk/RSS投影两式及slack数额继续保留，只改变D_A输入的计量语义；B已在D_A上界内的保守重复预留仍保留。image `st_blocks*512`为另行报告的实体分配采样，不能证明VHDX物理峰值或替代整卷硬cap。

已贯通：预算摘要/账本创建、Stage A durable边界、guard与supervisor边界一致性、Stage B投影、105+105元数据回放和扩容入口。初建/扩容原语保留固定数额并识别显式计量模式，仍要求外部冻结预算摘要完全一致。2→4正式扩容仍必须先有同一guard/supervisor接受的唯一durable entry、完整回放与当前artifact核验，不能以scratch成功替代。**本段是源码与协议准备，没有合法Stage A/B、没有准入PASS。**

| 补齐项 | 已有实现/证据 | 缺失证据、可选方案及代价 |
|---|---|---|
| 单一生产装配 | `assemble_production_owners`装配同一个controller作为ResourceEnforcer和bound SupervisorOps；固定原guard/ledger/supervisor私有归属，冻结role registry；禁止legacy第二账本writer和同进程wall验收。 | 完整ABExecutionBindings科学数据适配器、pre-bootstrap Linux首样本与host launch连续性仍缺；不能靠传入时间戳/对象名称补证。源码装配不等于已安装runner。 |
| RSS/tasks/wall真实原语 | 固定cgroup2与实际systemd主PID、memory/swap/tasks/LimitAS核验；新增绝对MONOTONIC内核SIGKILL timer，活动timer不增加辅助task；Stage A gate之前受A timer，扩容受总timer。 | timer只杀原controller，全部workers须由已安装KillMode=control-group及真实stop/reap闭环覆盖；真实安装/超限/失败收尾/整study验收未执行。生产写边界、worker清场、abort/quarantine生产端口继续拒绝。 |
| 真实身份与GT清场 | 只读Linux内核collector核对原PID/start/nativeTID、procfs/nsfs/cgroup2、递归procs/threads、mountinfo与FD/device/inode，包括deleted GT引用；terminal接入此检查。 | 原始GT inode全集、全部issued/revoked角色历史、逐role/phase权限与startup锚必须由实际root broker持有；现LinuxRoleMountController仅覆盖non-GT，不能用mutable_active/revoked或空列表补齐。此处仍拒绝，未开GT。 |
| post-exit Linux验收 | 独立外部witness在unit仍active时持有原cgroup内核FD；退出后核对原InvocationID、inactive/dead/success、原PID退出、cgroup及子树empty、完整ledger/terminal再验；最后Linuxclock在FD清理之后。 | observer必须持续在unit cgroup和mntns之外；systemd收集后的offline/消失内核证据不当作empty。原cgroup持久可读witness策略、签名native-close跨进程传输和实际host桥接尚未安装/验收。observer RAM/tasks/所有helper另计，额度未定。 |
| Windows全只读运行身份与外部QPC | QPC先于全树身份构建；manifest绑定exe、Python模块和代码文件的全量held handle；实际readonly卷/完整文件集/stream hash/路径与reparse核验，拒绝`..`及未映射zip模块；core/seal文件与volume flush、readback、验证及handle关闭后再取最后QPC。 | 必须安装完整只读Windows执行快照与受保护manifest/policy；当前可写Python不是替代品。host完整native DLL/WSL桥接运行身份、签名Linuxhandoff、独立硬cap host-control卷真实拓扑仍缺；两个生产gate在任何写入之前拒绝。 |
| 一次性与失败保存 | 原私有归属下独立消费abort、活动失败污染、descriptor/handle逐个释放、禁止重试和覆写；初建/扩容attempt保留。 | durable abort/quarantine生产实现、容量与实际权限仍缺；不能把catch/GC清理当作磁盘隔离或可恢复授权。 |
| 20+1 | owner已确认20 GT-backed评价+1 GT-free代数归并，pooled GT reads=0；旧算法/额度窄审阅仅覆盖限定源码。 | 最终production role图与全部21调用的真实GT revoke/FD证据仍缺；正式协议/源身份重冻与完整独立review ID缺；数值容差仍未确认，跨OS结论继续PARTIAL_MATCH_ONLY。 |

实施接口参考：[Linux timer_create](https://man7.org/linux/man-pages/man2/timer_create.2.html)、[timer_settime](https://man7.org/linux/man-pages/man2/timer_settime.2.html)、[cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)、[Windows FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)、[GetVolumeInformationW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw)。这些原生接口定义不构成本机部署、完整实现复审或实验准入证据。

#### 专用边界容量核算表（安装前填写，不代替实测）

每层分别填写baseline实际allocated bytes与峰值增量。承载容量的最低规划关系为 `可用总容量 >= baseline + max(8 GiB, 预计后续峰值增量 + 已批准收尾余量)`；8 GiB是建镜前的余额门，不无条件再与4 GiB image相加收费。Windows实体卷、guest FS及可选carrier分别计算并核对真实拓扑；VHDX虚拟最大容量不是Windows物理余额或已占字节。具体数值需部署对象与容量证据，不能用本表推定已满足。

| 成本项 | 现有可用信息 | 计量与缺口 |
|---|---|---|
| revision-g source准备快照 | 105文件，逻辑1,674,692B；当前生产源码已改变，原manifest只保留历史准备身份。 | 不是当前完整代码闭包，也不是allocated收费；最终source/runtime/controller/launcher/worker全树须重冻。 |
| 既有Linux runtime准备树 | 11,330文件，逻辑348,519,927B；已有13-wheel依赖证据。 | inode/extent、目录及VHDX metadata、安装缓存/wheel副本和新专用distro副本待核；逻辑字节不能直接当physical cap。 |
| distro OS、Windows只读执行树、输入/准备视图与控制层安装 | 已有准备来源；尚无选定专用卷部署的baseline。 | 每一实际副本单列；OS/native libraries/WSL桥接完整身份及allocated量待核，不填0。 |
| 正式image与控制区峰值增量 | image固定2→4 GiB；guest64 MiB/host16 MiB仅候选。 | 研究image和内层数据不跨层双计；VHDX与外层metadata、journald、失败保留、core/seal等均归属已批准hardcap；候选payload/卷大小不能代替实际FS可用容量。 |
| 观察者与准备工作 | post-exit独立observer及其systemctl helper与host launcher在study cgroup之外。 | RAM/tasks/CPU/wall与一次性安装、身份重冻、容量/OS验收/失败收尾预算另填；未获准则不安装、不运行真实验收。 |

预算确认尚缺：专用实体边界对象及容量Q、guest/host实际控制额度、baseline/峰值增量与准备费用；外部observer/launcher/helpers RAM/tasks等额度；free-sample freshness与marker payload数额；跨OS数值容差及阈值/排序边界。已确认的wall/RSS/tasks、20+1与D_A V2无需重复询问，但仍须进入最终预算/协议内容摘要及正式独立复审。

#### 一次完整A+B条件授权卡：最小可审阅填写稿

| 字段 | 当前填写值／待填内容 |
|---|---|
| 研究／请求范围 | `route2-candidate-overlap-v1-001`；仅一次完整Stage A+B；同一image 2→4 GiB，失败不续跑，不另起ID。 |
| 当前状态 | `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`；准备视图`PREPARED_UNREVIEWED`；`FROZEN_ADMISSION=None`；Stage A/B均未合法运行；合法结果无。 |
| 信任与建镜门 | Windows宿主账号owner可信；实际WSL承载FS与VHDX所在Windows实体卷在建镜前各live≥8 GiB；新增专用硬cap边界部署方案已选，具体对象/容量待填。 |
| 已确认预算方法 | A1200s/总3600s/累计fit900s；60s收尾计入原wall；C=min(4 GiB,floor(3×启动available RAM/5))，LimitAS=floor(C/2)，TasksMax=2含controller。 |
| 已确认协议方法 | 20 GT-backed+1 GT-free pooled代数归并、pooled GT reads=0；D_A V2=2 GiB严格上界，不能报告为测得真实峰值。 |
| 尚待预算裁决 | 专用实体cap/Q与baseline/准备费用、guest/host control硬cap、observer/launcher/helpers资源、freshness/marker payload、跨OS数值容差与阈值/排序边界；未知不填0或默认批准。 |
| 最终身份闭包 | source/runtime/原始注册输入/准备视图/path-map/role graph/controller/launcher/worker/backend/科学协议/预算全文SHA：**待最终重冻**；本轮working-set摘要不是完整生产closure，原revision-g/card hash不能沿用。 |
| 独立审阅 | 原完整实现`route2-ab-full-implementation-review-2026-09-29-FAIL-001`仍FAIL；最终完整实现、安装与OS控制、计量/数值协议独立复审的正式ID：**NOT_ISSUED**。窄静态审阅不填此栏。 |
| 必需OS与持久证据 | 一次性attempt/lock/失败原地quarantine；全部worker写路径；完整role/phase GT只读bind、权限、revoke、child退出及FD清场；真实源/runtime身份；pre-bootstrap→exit双墙钟及最后durable anchor，均**待生产闭环证据**。 |
| 最终负责人授权／保护seal | 正式review通过并绑定最终全部身份与预算后，由负责人另行明确一次完整A+B实验批准；当前**NOT_ISSUED**，不创建config/key/unit/seal或正式研究对象。 |

该填写稿只存在于原设计、执行计划和既有review最新整合修订内。原授权申请卡保持原样且不能用于当前源码；没有新交接包或可执行授权。Route3 v1-003合法COMPLETE、四门FAIL保持；gap=0由路线二覆盖。仅在负责人提供合法路线二结果后讨论三个架构方向的最小验证，不自动启动方向。

#### 本轮限定静态复审与最终源码记账

独立规格复审发现的1×P1、2×P2已按限定范围修订并再审确认：Stage B普通candidate preflight移到同一guard接受entry及expansion之后，未放宽private work gate；扩容验证后的重复fsync保留total deadline，不再追加Stage A deadline（原durable entry的及时接受仍由原guard/supervisor私有记录要求）；生产policy固定已确认的exact60,000,000,000ns margin。

随后独立质量审阅在最终13个源码上逐一确认原12项静态修订已存在：protected policy四元组、冻结registry传递、preimage8 GiB与建镜后余额分离、Windows实际路径/manifest、QPC先于lease构建、完整mount/loop核验、observer持续隔离、活动失败消费、timer删除后超时强制退出、一次性全部FD清理/取消、最终QPC覆盖验收与lease关闭、systemctl stdout边读边限额。质量审阅新增1×P2已修订并再审确认：quiescence在全部FD清理后再次检查同一一秒elapsed deadline，再返回原实际采样时间。两项审阅均为**限定只读静态结论，无正式review ID**；不代表穷尽全部实现问题、不签发完整实现或实验准入PASS。原完整FAIL仍有效。

post-exit新增private dup/OFD锚及原生KCMP_FILE比较，避免以inode相同代替原open-file-description；内核缺支持/权限不足或FD归属含糊即拒绝，清理失败仍尝试其他明确归属FD，含糊FD不盲目关闭。实际WSL kcmp兼容性、原cgroup退出后可读性与必要observer进程退出兜底尚未验收，也不能据此签发实际quiescence/exit receipt。[kcmp(2)](https://man7.org/linux/man-pages/man2/kcmp.2.html)。

本轮**未新增/运行测试，未导入或调用实现，未运行Windows/WSL原生探针**。仅用Python3.10 AST解析36个Route2模块、逐行检查13个变更源码与三份新增文档段落，以及只读hash核算。上文948/947+1skip和revision-g203/OS仍仅是旧批次准备证据，不覆盖本轮新增代码；也没有新的跨OS数值等价结论。工作树原有改动保留，未提交；未创建正式image/volume/study/ledger/lock/unit/config/key/distro，未开GT，未启动Stage A-only或A+B。

最终只读working-set记账为36个package源码+26个既有synthetic测试文件+4个既有相关scripts，共66文件。逐文件raw-byte SHA256的repo相对POSIX路径映射按key排序，以UTF-8 canonical JSON（ensure_ascii=false、separators=(',',':')）再次SHA256，得到 `023b0d1cfcbca62843fea3a248c1247c2f16834e3cbb1feb3fd85e8e79f2e54d`。这是本轮可复现静态记账，**不是完整source/runtime生产快照或FrozenAdmission**。质量审阅确认13个源码在其首轮审阅前后与提交值一致；最后只改quiescence的cleanup后deadline检查，独立再审确认该文件前后hash一致。以下为最终13个源码：

| 源码 | 最终SHA256 |
|---|---|
| `budget.py` | `a5fdb1d1126b2885599c7e664d77cb978dbdd8cc19a411d463b48019d991c8f3` |
| `linux_deadline.py` | `fda5c51a792b72459569aa1bb1c190ad64d9b84f10ffa909df3ccd1e13c5cbdc` |
| `linux_initial_volume.py` | `d00ea0b899c4b8a3175d277a5897e1568292d9d919b64a3ea7ffb347a7abd02a` |
| `linux_post_exit.py` | `7054dd5ce85602a169837ec8548d6d254e191e8378162bf56c6d42a13241625c` |
| `linux_production_controller.py` | `b4935cd2070e200c445af1190640140f6d1abb73573ddccabf1a6e6f05e6e697` |
| `linux_quiescence.py` | `041518fbe189f851f05b342fb0013d10736a0033d5a085ed1e8157e0ce061f34` |
| `linux_supervisor.py` | `f8ccdbc503f9c56b1584a04424d0493ac651d7f807ef0e46c5027f311e97a412` |
| `linux_volume_backend.py` | `642a6b01fbdb41f3e096d775dab91d34bcc590ab6b0a5d8fec1c833bab165835` |
| `stage_a_replay.py` | `50acc858422dd9c03bd480d26162567c88ecdc4d66f38088b8b3e4bada5d48f3` |
| `stage_b.py` | `416f13e2a72b97d89b0321b06f2ede693b4f44136111669abd8c0757874de308` |
| `terminal_observation.py` | `eb4fab831f62c220822959a33cc6e2d18a2eb9fd1a73861d661d51e646c95ffc` |
| `windows_control_identity.py` | `5c6ce7ae572c98865febd148450edd835133b6fa43326edd595810948caffe2f` |
| `windows_wall.py` | `2dce7d85b3eee1545579cb012b0eaa5ef6fee5dea5ad6b6cd9e2a68e883e6f78` |

仍需的独立复审与批准顺序：先补实际原始GT broker/phase worker私有完整历史、全写路径与生产abort/quarantine、pre-bootstrap时钟和完整AB科学适配器、签名native-close与外部transport；再在选定专用边界及获准准备额度下形成独立安装/OS控制与失败收尾证据，核全readonly代码/runtime/native依赖身份；完成D_A V2/20+1及数值等价协议与全预算独立复审；最终完整A+B实现review正式ID与全部身份/预算重冻后，负责人另行签发同一研究的一次完整A+B授权。目前预算目标实体/准备空间问询尚未收到答复；没有据此自动选择设备、容量、数值容差或准许部署。

### 2026-10-04 整合后续补：负责人授权继续实现与部署准备

本节接续既有整合后修订。负责人已授权继续完成 GT 授权／撤销历史、全写路径和失败保存、完整 runner、启动时钟连续性和签名外部交接，以及专用实体边界、容量／剩余预算、数值容差和独立复审。本授权推进实现、部署准备和复审，不等同于原条件卡绑定的一次完整 A+B 实验授权。不新建交接包，不修改原授权申请卡，不启动 Stage A-only 或 A+B。

四项状态分别保持：准备视图 `PREPARED_UNREVIEWED`；A+B 未获正式准入且 `FROZEN_ADMISSION=None`；Stage A/B 均未合法运行；路线二没有合法结果。原完整实现复审 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 保持 **FAIL / NOT_APPROVAL_READY**。三份原始 WSL 探针、13-wheel 依赖准备和历史合成测试只属准备证据；本轮没有新增或运行测试，没有打开真实 GT，也不以历史回归覆盖新增代码。Route3 v1-003 合法 COMPLETE、四门 FAIL，不重跑；gap=0 已覆盖；架构方向验证仍等用户提供合法路线二结果。

#### 已确认裁决

- Windows 宿主账号所有者可信，继续 WSL2 worker 隔离；若以后改变该信任假设，改用独立受控 Linux runner 并重新复审。
- 正式 image 创建前，guest 承载 FS 与 VHDX 所在 Windows 实体卷分别现场核验 ≥8 GiB。固定外层 carrier 方案另加 carrier 层身份和余量，不能以 carrier free 代替实体卷 free。
- Stage A／total／累计 fit 为 1200／3600／900 秒，60 秒收尾计入原 wall。RSS `C=min(4 GiB,floor(3×启动可用RAM/5))`，LimitAS=floor(C/2)，swap=0，CPU=200%，TasksMax=2 包含控制器。
- D_A 采用 Stage A 的 2 GiB 严格容量上界 V2，不能称为实测真实峰值；2→4 GiB 扩容仍要求全部正式阶段门、计量协议独立复审和新冻结预算。
- 第21项采用 20 次 GT-backed 评价 + 1 次 GT-free 代数归并，pooled GT reads=0。新数值容差草案仍须协议复审和最终绑定，不能由旧残差或本轮实现授权冒充既有容差批准。

#### 实际只读部署盘点

2026-10-04 Windows Get-Volume/Get-Partition 只读结果：E 为 NTFS，实体卷 GUID `dbd01263-98ac-43a9-a44c-5dcc3d2e02d1`，Disk 1 / Partition 2，卷容量 1,897,546,117,120 bytes、剩余 1,018,094,968,832 bytes；C 剩余 28,526,243,840 bytes，D 剩余 114,173,882,368 bytes。未盘点到现成专用空闲分区，不能格式化或占用已有 C/D/E 分区。这是时点空间盘点，不是 per-study 实体硬上限，也不能代替创建前 freshness 检查。

当前进程 `ElevatedAdministrator=false`，`New-VHD`／`Get-VHD` 不可用，`diskpart.exe` 存在。未创建 carrier、VHDX、新发行版或正式实验对象。可继续形成固定预分配 carrier 的部署配置和拒绝条件；实际 attach、安装、身份和容量证据需要具备管理能力的执行环境，不能以未执行脚本、规划容量或 SID quota 代替。

#### 可审阅容量和数值草案

| 层 | 拟议上限 GiB | 基线天花板 | 未来峰值增量 | 收尾保留 | 名义预算余额 | 格式化可用容量最低值下的条件余额 |
|---|---:|---:|---:|---:|---:|---:|
| guest | 20 | 8 | 6 | 1 | 5 | 4（可用容量至少19） |
| carrier | 32 | 23 | 1 | 1 | 7 | 6（可用容量至少31） |
| Windows实体归属 | 34 | 33 | 0.75 | 0.25 | 0 | 实际 UNKNOWN |

以上均为未批准的规划天花板，各层分别计费，不能把20/32/34相加当作一次循环镜像费用。固定32 GiB carrier 不自动强制34 GiB实体总归属上限；carrier外的元数据、C卷上的可归属系统写入等仍要真实上限和全写路径证据。基线必须原生计量，未来增量须可复审的保守上界；实际容量、实际剩余预算和真实部署身份仍为 UNKNOWN。guest64 MiB／host16 MiB仍是控制容量候选。控制写根统一为 `/var/lib/route2-controller`，loop镜像、VHDX、journald、replay/startup/failure标记和外部anchor均在写清单中，包含临时副本和失败保留，不因删除而退回历史峰值。

数值政策拟议连续值 `atol=1e-12、rtol=1e-10`，公式 `abs(a-b)<=atol+rtol*max(abs(a),abs(b))`。阈值、排序、tie、区间、匹配、计数、null mask与质量门的离散决定必须完全一致；指标质量门和阈值选择须从实际输入重算，不能只比较调用者声明的门值或空聚合记录。现有194/200逐位一致仍是 PARTIAL_MATCH_ONLY，不能自动改判完整等价。

#### 本轮实现与审阅状态

已形成原始 GT broker／完整110-view登记与不可删减的失败历史、启动时钟跨exec交接、生产runner装配框架、失败保存、Ed25519外部交接，以及容量／数值政策源码。仍在修复本轮独立静态审阅发现的原生边界和身份连续性缺口。失败标记只证明尝试保存原artifact；worker清场／GT撤销未证明时必须记录 NOT_ATTESTED，不能形成成功StartupAbortReceipt、terminal接纳或重试资格。

完整实现状态仍为 FAIL。最终完整实现、实际安装和 OS 控制、计量／数值协议复审的正式ID均 NOT_ISSUED。外部observer的真实解释器／stdlib／原生依赖和Windows DLL完整只读闭包、实际QPC启动transport、完整phase worker／adapter装配、专用实体硬边界与实测预算仍缺。Ed25519所需cryptography和传递原生依赖未安装或冻结，既有13 wheels不覆盖它；签名producer在运行期身份闭合前拒绝。

本轮只做源码实现、AST／文本／hash核对和独立静态审阅，不执行生产源码或合成测试。原申请卡继续 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，旧source/runtime hash不得用于本轮源码。讨论和状态只回写原设计、执行计划和既有review的整合后修订，工作树保留未提交。

#### 一次完整 A+B 最小条件授权卡（更新草案，仍不可执行）

| 项 | 本轮绑定内容／尚缺条件 |
|---|---|
| 研究／次数 | `route2-candidate-overlap-v1-001`，一次完整 A+B；不拆 Stage A-only，不重跑 Route3，不自动开展架构方向验证。 |
| 当前准入 | APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；FROZEN_ADMISSION=None。 |
| 科学协议 | D_A=2 GiB严格上界V2；105-role输入与参考身份；25 fit／25 predict／65 decode／20 GT-backed eval +1 GT-free pooled；pooled GT reads=0。全部计数和算法身份须冻结核对。 |
| 原已确认额度 | Stage A1200秒、total3600秒、累计fit900秒；60秒收尾计入原wall；C=min(4GiB,3/5启动可用RAM)，LimitAS=C/2，TasksMax=2包含控制器。 |
| 尚待预算绑定 | 专用guest/carrier/实体归属对象和原生hard cap；20/32/34GiB及guest64MiB／host16MiB控制容量均为草案；实际baseline、格式化损耗、剩余额度、外部observer／launcher／helper资源和全部控制写入费用。 |
| 全身份冻结 | 新source闭包、Linux／Windows／observer解释器、stdlib、wheel、原生库及DLL闭包、launcher、controller、broker、worker、外部验收代码、完整配置和镜像／卷／发行版原生身份。旧revision-g和旧申请卡hash不可复用。 |
| GT／worker | 全110-view登记、完整真实授权／失败／撤销历史，原始worker发行和退出证据，全部写路径强制，controller遗留FD／mapping／OFD清场；实际证据尚未产生。 |
| 双时钟／terminal | Linux从原始进程启动开始连续计费，外部QPC涵盖启动和terminal关闭后的全部检查、持久化及清理；真正unit/PID退出、原始cgroup状态和签名交接。安装／真实验收证据尚缺。 |
| 数值／签名政策 | 拟议atol1e-12、rtol1e-10，全部离散决定严格一致；Ed25519交接和Linux策略HMAC进入最终协议与依赖复审后统一冻结。 |
| 独立复审 | 完整实现、实际安装／OS控制／失败收尾、磁盘计量与全预算、数值协议和完整运行期身份复审正式ID均 NOT_ISSUED。静态窄审阅没有签发实验准入PASS。 |
| 最终签发 | 负责人批准上述实际对象／预算／身份和正式review ID绑定的同一卡后，才签一次完整A+B owner approval与seal。当前不得据草案创建正式image／volume／study／ledger／lock或打开GT。 |

部署准备可继续使用已有授权推进，但目前不能凭本会话未提升的Windows进程生成实际受控边界证明；没有把这项环境限制转化为新的实验授权，也没有降低实体计量标准。完整生产phase worker与适配器、QPC启动交接和外部运行期身份producer仍属实现／安装缺口，不得只凭框架或接口存在称为已完成。


#### 负责人补答与实际权限复核（2026-10-04）

负责人补答“授权当前对话完全访问权限”。这延续准备实现与文件访问授权，不签发一次完整 A+B，也不能代替 Windows 实际管理员令牌或专用实体边界对象。补答后只读复核仍为 `ElevatedAdministrator=false`、`New-VHD=false`、`Get-VHD=false`、`diskpart.exe=true`。E 实体卷 GUID 不变，现场余额为 1,017,121,017,856 bytes；该余额仍只属时点盘点，不是 per-study hard cap 或正式创建前检查。未尝试格式化现有分区、创建正式 image/volume/study/ledger/lock，未安装发行版。

负责人明确选择“保留候选，复审后再最终绑定”：guest/carrier/实体归属 20/32/34 GiB、guest/host 控制 64/16 MiB、连续值 atol=1e-12 与 rtol=1e-10、离散决定完全一致继续作为候选。此答复确认候选进入复审，不是这些实际容量、外部控制资源、安装支出或数值容差的最终预算／协议签发。原已确认的 1200/3600/900 秒、60 秒在原 wall 内、RSS／TasksMax 方法、D_A V2 与20+1协议继续有效。实际专用对象、原生上限、完整基线和剩余额度仍待具备管理能力的环境取得。

#### 后续源码修订与真实 worker 撤销前检查（2026-10-04）

已修订 GT 登记历史的 native tuple／JSON list 比较：先要求精确键、数组及整数形状，再按 canonical JSON 比较原始 backing anchor；保留全部已发行对象历史，不以空列表替代。容量计量的 native accounting 分支仅在 `_valid_ceiling` 成立时比较上界，非法候选字段继续进入 BLOCKED 问题报告。两项限定范围的独立静态规范复核未发现剩余 P1/P2；该结论没有签发正式 review ID，不覆盖运行期或完整 A+B。

launcher 与跨 exec start-clock 复核加入参数为空、当前必拒绝的原生 origin 门。在实际已安装 manager 的 pre-fork 时间戳语义与身份绑定，或可信 pre-Python 原生起点 producer 完成前，`ExecMainStartTimestampMonotonic` 不得被接受；版本字符串、HMAC、review 字段及时间戳早于首个 Python sample 都不能单独证明完整启动计费。原生 capped／billed／deadline replay-claim producer 也仍未完成。

原始 GT broker 在正常卸载前增加双次原始 cgroup／控制器 FD／mapping 核验与不回收子进程的 `waitid(P_ALL, WEXITED|WNOWAIT|WNOHANG|__WALL)` 检查。只有 native ECHILD 可接受；活跃、已退出未回收或不支持的状态均拒绝。相同子进程检查进入 activity／terminal quiescence 双次采样。该门在 GT bind 尚有效时不读取 GT 内容，不代替原始 worker 发行、逐个 pidfd／wait／退出状态、完整 sandbox 与全写路径证明；描述性账本事件仍标注 `individual_worker_exit_history=NOT_ATTESTED`。新门正在独立静态规范／质量审阅，本轮未调用这些 native APIs。

采用这一补充检查的依据是：僵尸进程不会列在 cgroup.procs；proc children 在子进程退出期间也可能遗漏，故未把该列表作为回收证明。依据：[Linux cgroup v2 官方文档](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)、[Linux waitid 手册](https://man7.org/linux/man-pages/man2/waitid.2.html)、[proc children 手册](https://man7.org/linux/man-pages/man5/proc_tid_children.5.html)、[Linux UAPI wait.h](https://raw.githubusercontent.com/torvalds/linux/master/include/uapi/linux/wait.h)。这些语义资料不替代所选安装环境的原生验收证据。

#### 固定生产元数据装载器（源码已形成，安装和复审仍待闭合）

`production_metadata.py` 已形成固定装载入口，`production_runner` 不再停在“metadata loader is missing”。唯一安装位置为 `/etc/route2/route2-candidate-overlap-v1-001-ab-metadata.json`，schema 为 `route2_production_ab_metadata_v1`。原始 supervisor config／seal／source／runtime／FrozenAdmission／review／owner／授权卡身份进入精确 body，采用原始 controller key 的域分隔 HMAC-SHA256；原始未消费 bootstrap、start-clock 和装载结果在私有 registry 中绑定。审批、readiness、预算、canonical sorted 105-role 与 reference 登记、完整 raw path-map bytes，以及实际 A2 config 的 source manifest／冻结 hash 必须一致。复制 dataclass、传入 callback 或拼装 hash 不能替代该装载结果。

装载只读取有固定边界的控制／登记元数据和配置；原生读取保持 nofollow 父目录和文件 FD，核对 frame、KCMP_FILE/OFD、mount ID／device／private readonly／fstatvfs，并在原始 invocation deadline 内使用额外 10 秒上界，关闭临时 FD 后再次检查。loader 不构造 provider、Stage B、ledger、guard、volume 或 GT worker；main 的既有失败路径消费 bootstrap。源码的完整规范／质量复审尚在进行。

真实只读安装 bundle、新源码／runtime 冻结、所选环境的 root／KCMP／mount 支持及启动 origin producer 仍缺。真实 role/path-map、phase-worker、nested producer 和原始 QPC transport 门继续拒绝。因此这项源码进展既不是完整 runner 已完成，也不是正式 A+B 准入。新签名依赖 cryptography／原生传递闭包仍不属于既有13-wheel证据。


#### 完整静态复审与三层采样协议修订（2026-10-04，接续）

负责人最新答复继续有效：20/32/34 GiB、64/16 MiB及连续值 atol/rtol 保留为候选，独立复审后才最终绑定；完全访问权限不等于实际 Windows 管理员令牌，不是实验 owner approval。

本轮新的完整 A+B 静态源码复审仍返回 **FAIL**，没有签发正式 review ID，不替代原 `route2-ab-full-implementation-review-2026-09-29-FAIL-001`。复审分别发现源码装配缺口、实际安装／原生证明缺口和预算待决项，不能概括成“只缺管理员权限”。其中 GT 登记进入账本后与 Stage A 回放／正式扩容不兼容，expander 未使用原控制器持有的 OS ports，launcher 跨 exec 丢失六项线程限制，以及嵌套 carrier 后现有二层采样错误地将 carrier 当作 Windows 实体卷，均属源码问题。

已修订的源码范围：

- 原始 GT broker 只从原 guard／私有 registry／真实原始账本持有 FD 中导出唯一 seq=2 登记的 canonical 完整记录。回放和扩容只接纳这些原始字节绑定的唯一登记，不接纳调用者补造记录或放开其他未知 GT 事件。实际逐 worker 发行、sandbox、退出和所有 backing 对象历史仍未完成。
- controller、creator、expander 共用同一原始 `LinuxProductionOSPorts`。bootstrap 后账本仍为 `study_created/invocation_started` 两条时先停在 QPC／签名 Linux-unit 原始握手门；该门现仍拒绝，未以回调、epoch 或 receipt 冒充 transport。握手完成前不得安装 GT broker 或运行 worker。
- pinned bootstrap 的实际 exec 环境明确包含六项线程限制，各为1：OMP、OPENBLAS、MKL、NUMEXPR、VECLIB、BLIS；保持隔离启动参数和原生时钟起点拒绝条件。未据此声称实际 TasksMax 或完整运行期身份已验收。
- 固定 metadata loader 的导出入口也在所有失败路径消费原始 genuine bootstrap，覆盖早期验证、读取、parse、FD 关闭和 registry 发布；复制／外来 proof 不能消费另一原始 owner。该修订与 runner 的独立规范及质量窄审阅未发现剩余限定范围 P1/P2，没有正式 ID 或实验准入 PASS。
- GT 撤销前及 activity／terminal 的无活跃／未回收子进程检查，独立规范窄审阅未发现剩余限定范围 P1/P2；仍不构成逐 worker 退出历史或完整清场证明。

三层采样协议必须重冻：初始镜像策略改为 `route2_initial_volume_policy_v2`，host 请求／响应改为 `route2_host_backing_sample_v2`。`windows_volume_id` 明确指承载 carrier 文件的外层 Windows 实体卷；新增 carrier 文件路径、carrier GUID、独立批准的增长／收尾 free reserve。原生 Windows producer 必须分别持有 registered guest VHDX 和 carrier backing 文件，核对真实 file ID、实际 carrier 的虚拟磁盘设备与承载 guest 文件卷的 disk extents 关联，并分别现场取 carrier free 与实体卷 free；nonce、单一 GUID、规划路径或旧自由空间回执不能替代。

Linux 侧 `InitialFreeSample`、`EnforcementReceipt`、`ResourceSnapshot`、supervisor startup 及 Stage A／扩容回放增加固定 `NestedBackingSample`，保留完整 canonical host 响应与原生两文件身份／两 disk number。正式 creator 强制 V2，前后身份及 registry／carrier／physical 绑定一致。原 guest 与实际实体卷各 ≥8 GiB 门保持；carrier 只另查明确签发的增长／收尾预留，不自动批准第三个8 GiB门。generic 历史模式的 None 只保留旧通用协议，不能作为正式生产采样。采样与回放是观察和身份核对，不能证明实际执行的 Windows 解释器／脚本、实体 allocated-byte hard cap 或全部写路径强制。

本轮正在独立复审 V2 传播及原生 sampler；未执行其中的 native APIs、没有创建任何部署或实验对象。旧合成测试仅覆盖旧协议，不覆盖这些新修订；在另行获准验证前不新增或运行测试。三层采样的 API 语义依据：[OpenVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-openvirtualdisk)、[GetVirtualDiskPhysicalPath](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskphysicalpath)、[IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents)。这些 API 文档及源码本身不构成所选原生安装验收。

完整实现仍缺的具体 producer／交接：原生 pre-Python／pre-spawn 起点及 capped/billed/deadline replay-claim；原始 QPC 到 Linux 的已认证启动 transport；真实 role/path-map 轮换 owner 与 phase-worker spawn／sandbox／IPC／pidfd／wait／reap／status；全部已创建又删除的 backing 对象发行历史；整 study/controller/worker 写路径封锁；host sampler 的实际执行身份；observer 和 Windows DLL/PE/ELF/stdlib/ABI 完整只读闭包；Linux/Windows 控制写入原生 cap 与外部 deadline；真正 unit 退出、原始 cgroup 清场、最终 durable QPC 接纳；完整 bounded teardown/quarantine/no-retry owner。失败保存不等于撤销／清场成功，相关 NOT_ATTESTED 不得改成成功回执。

最小完整 A+B 条件卡继续 APPLICATION_BLOCKED：除前述源码闭合，尚需实际专用对象、原生 allocated-byte hard cap、格式化容量／真实 allocation baseline／所有失败保留及收尾峰值、每层实际余额、历史及未来准备支出、Linux observer/helper 和 Windows launcher/QPC/bridge 在 TasksMax=2 外的 RAM/task/CPU/wall 额度，及数值容差最终裁决。固定32 GiB carrier 不强制34 GiB全部实体归属，E/C卷逃逸系统写入和 NTFS 元数据不得记0。候选算术及窄静态复审不能签发预算或准入。

最终仍按同一研究的一次完整 A+B 顺序：完整实现与实际安装／原生控制／失败收尾独立复审；V2计量、全预算、数值协议及完整运行期身份独立复审；全部正式 review ID 与全新 source/runtime/role/config/native对象/预算身份冻结；负责人另行绑定一次完整 A+B owner approval 和 seal。目前准备视图 PREPARED_UNREVIEWED，FROZEN_ADMISSION=None，Stage A/B 均未合法运行，路线二仍无合法结果。


#### 2026-10-05 整合后续补：中断复审恢复及候选预算纠错

接续上一节的同一工作，不新建交接包、授权卡或研究 ID。2026-10-04 独立审阅额度中断时，三层协议质量审阅、原生 Windows sampler 规范／质量审阅及 carrier floor 修订复审未完成，不能将中断标记为通过。2026-10-05 已重新安排独立静态审阅；本节先记录实际完成源码及待审范围，后续结果继续在本节追加。

GT pre-revoke fence 的独立质量复审发现 P2：descendant cgroup 可能被额外挂载遮住扫描对象。已在每次原始 kernel identity 检查拒绝 `/sys/fs/cgroup/` 下的任何 overmount；双次 tree/FD/maps/no-children 扫描前后要求原始 proc mountinfo 字节一致。质量复审未发现剩余限定范围 P1/P2。只属源码复审，实际原始 worker 发行、pidfd/wait/reap/status、完整 sandbox、逐role／逐phase授权及撤销历史仍缺；相关 NOT_ATTESTED 不变。

原生 sampler 源码已形成：读取真实 Lxss registry，持有 guest/carrier 文件及无 delete-sharing 的父目录链，按 actual FileIdInfo 和 final GUID path 核对；采用 GET_INFO-only、RWDepth=0 的 OpenVirtualDisk query，GetVirtualDiskPhysicalPath 返回 mounted carrier disk，再与实际承载 guest 文件的 carrier volume disk extents 关联。外层 Windows 实体 GUID/free 从持有的 carrier backing 文件单独核对。前后复核 registry、namespace path、原始文件身份及两卷映射；多extent、differencing、unsupported ABI/共享模式／query 或漂移均拒绝。不进行 attach/detach，不申请提升权限，不写文件。永久 attach 若需额外 DETACH access，当前 GET_INFO-only query 会拒绝，安装方案须证明兼容，不能以重试 attach 或增加权限绕过。sampler 尚待本次完整限定范围的独立规范／质量审阅；本轮未调用它。

容量／数值候选的独立源码审阅发现 P2：`ProposedCeiling.balances` 和三个容量计算使用了所有层统一8 GiB，隐含新增 carrier floor，虽然当前31 GiB格式化候选仍满足旧算术。已集中修订为 `confirmed_preimage_floor_bytes`：guest 与 actual Windows physical 为8 GiB；carrier为0，再单独计 growth+cleanup。live free、规划derived minimum、native balance及 proposal check采用同一规则。carrier 推导最低容量由 `23+max(8,1+1)=31` 改为 `23+1+1=25 GiB`；另行保留的格式化容量候选31 GiB不变，20/32/34 GiB及64/16 MiB、数值容差候选均未调整、未最终批准。修订后规范／质量复审待闭合。

独立容量／数值审阅除此未发现剩余限定范围 P1/P2，但只认可条件算术和当前纯 metadata 政策范围：nominal guest/carrier/physical峰值及收尾后余额仍为5/7/0 GiB，actual baseline、formatted capacity、remaining budget 和 native hard cap 为 UNKNOWN。外部observer/helper/launcher/bridge资源及历史／未来准备支出、NTFS metadata、C/E可归属系统写入继续待计量和批准，不能缺省0。候选数值政策的全离散一致、真实输入重算和已认证冻结条件未改变；historical PARTIAL_MATCH_ONLY 未升级。

本轮继续仅源码、AST／文本／hash和独立静态复审，不新增或运行测试，不执行生产代码或 native sampler，不打开 GT，不创建正式对象。完整 A+B 实现复审仍 FAIL、正式复审ID未签发；准备视图 PREPARED_UNREVIEWED，A+B未获正式授权且FROZEN_ADMISSION=None，Stage A/B均未合法运行，路线二无合法结果。Route3及后续架构验证约束继续有效。


2026-10-05T10:37:02.4863418Z 只读重新盘点：当前 Windows token 仍 `ElevatedAdministrator=false`，New-VHD/Get-VHD 不可用；E实体GUID `dbd01263-98ac-43a9-a44c-5dcc3d2e02d1`、NTFS、Disk1/Partition2及容量1,897,546,117,120 bytes未变，现场剩余1,015,561,474,048 bytes。该全卷余额和相对旧盘点的变化不能归属为本研究支出，也不是实际 per-study cap 或正式 preimage sample。未尝试提升权限、部署 carrier、attach/detach、创建发行版或正式实验对象。


本次独立复审新增发现与修订：sampler 仅 FILE_READ_ATTRIBUTES 的句柄不能据称持续阻止删除／改名，已增加实际 FILE_READ_DATA／FILE_LIST_DIRECTORY 加属性访问并保留无 delete-sharing；拒绝权限或共享不兼容，不降为属性-only重试。依据：[Microsoft CreateFileW 访问／共享语义](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)。此外每次 `current_snapshot` 在返回前核对 live sample 与私有 state.initial_sample 的 guest mount/device、两文件原始ID、两GUID、disk number、carrier reserve和distro/registry身份；不能在观察到替换后仍进入 activity，也不能由后来恢复身份抹去先前观察。两处分别正在独立规范／质量复审。carrier floor 纠错的独立规范与质量审阅均未发现剩余限定范围P1/P2，无正式ID或实验准入PASS。

额外部署兼容缺口：原Linux依赖identity和证据记录 Ubuntu22.04、CPython3.10.12、glibc2.35。当前GT broker要求libc直接导出 open_tree/move_mount/mount_setattr；上游glibc2.36发布记录才加入这些wrapper（[GNU glibc2.36官方发布记录](https://sourceware.org/pipermail/glibc-cvs/2022q3/079946.html)）。由此推断：现有上游2.35环境不能直接满足该实现；实际发行版是否回移这些符号尚无本轮原生导出证据，不能只用版本号断言实际加载库已兼容或已验收。kernel支持与科学13-wheel可导入不证明libc wrapper存在，本轮没有调用GT/mount APIs或改动系统libc。

兼容可选方案及代价：专用环境采用实际导出所需wrapper的glibc并保持经批准的CPython/科学版本，代价为新发行版／完整ELF运行期和科学数值身份重新冻结及准备空间；或保留Ubuntu22.04，新增由实际kernel headers生成、独立复审和冻结的native helper，代价为compiler/headers/helper/ABI/所有原生传递依赖及额外准备／失败额度。不得硬编码猜测syscall号、使用调用者callback或放宽GT挂载证明；当前未自动选择新发行版、安装compiler或实现未经冻结的helper。此缺口进入完整安装／依赖复审及同一条件卡，不把13-wheel准备改判为可运行完整生产控制器。


##### 本次限定范围复审矩阵与工作集记账

| 源码范围 | 独立规范复审 | 独立质量复审 | 实际证据边界 |
|---|---|---|---|
| 固定 metadata 装载／导出失败消费 bootstrap | 未发现剩余限定范围P1/P2 | 未发现剩余限定范围P1/P2 | 未安装新bundle；不覆盖完整runner／原生启动。 |
| 原 GT backing canonical 比较及 pre-revoke/no-children/overmount fence | 未发现剩余限定范围P1/P2 | overmount P2修订后未发现剩余限定范围P1/P2 | 逐worker发行／退出／全部对象完整历史仍缺，NOT_ATTESTED有效。 |
| 原 broker seq2登记回放、shared ports、二记录握手顺序、六线程env | 未发现剩余限定范围P1/P2 | 未发现剩余限定范围P1/P2 | 原始QPC/signed-unit transport尚缺，握手门仍拒绝。 |
| V2三层Linux策略／receipt／snapshot／回放与每次live原始身份对比 | 未发现剩余限定范围P1/P2 | live backing替换 P2修订后未发现剩余限定范围P1/P2 | 生产写边界／host实际执行身份／native hard cap仍缺。 |
| Windows原生sampler V2全模块 | share-counted句柄及两项registry P1修订后未发现剩余限定范围P1/P2 | 两项registry P1修订后未发现剩余限定范围P1/P2 | 未调用native sampler；实际WSL语义／host运行期／硬上限仍缺。 |
| runner成功启动后的一次原始owner失败保存及startup异常聚合 | P2修订后未发现剩余限定范围P1/P2 | P2修订后未发现剩余限定范围P1/P2 | 仅已有installed/armed边界可尝试；实际保存、清场与GT撤销未发生。 |
| Windows外部wall／lease／trust失败清理及owner生命周期 | 原清理及init／abandonment／Thread引用P2修订后未发现剩余限定范围P1/P2 | 限额恢复后生命周期质量复核完成，未发现剩余限定范围P1/P2 | 真实host-control cap／deadline与签名外部验收仍缺。 |
| carrier无第三8GiB floor的统一计算 | 未发现剩余限定范围P1/P2 | 未发现剩余限定范围P1/P2 | 25GiB仅derived minimum；31GiB formatted及全部额度仍候选。 |
| glibc2.35 native mount helper C/H及broker ABI对应 | 未发现剩余限定范围P1/P2 | 未发现剩余限定范围P1/P2 | 未编译、未接入、未冻结；不是实际加载身份或可运行性证据。 |
| 完整A+B及原生安装／全部预算／运行期／数值 | FAIL | 正式完整review ID尚未签发 | 不可用窄范围审阅升级准入。 |

上述均为独立静态源码审阅，未签发正式 review ID，不是实验准入PASS；动态验证和原生安装验收尚未发生。本次不以旧合成测试证明修订正确。

工作集记账当前为81文件、2,064,551逻辑bytes，canonical path→raw-byte SHA-256 map 的 digest为 `f5ad68da431a21b29a3733f89fa9385991f8bbd3ae81c2a2100f213d253ff31b`。范围仅49个 Route2 package .py、4个既有相关script、26个既有synthetic测试文件及helper C/H两个源码文件；26个测试只hash，未修改／未解析／未执行。53个Python源码仅AST解析，未import目标模块；2个C/H文件仅文本／静态审阅，未编译／链接／加载。逻辑bytes不是实际allocated-byte支出或峰值。此摘要不是完整生产source/runtime闭包，不是immutable freeze或FrozenAdmission；旧revision-g/11330-file runtime身份不可复用作新增代码／helper／完整stdlib/ELF/DLL证明。

| 当前关键源码 | SHA-256 |
|---|---|
| `production_metadata.py` | `37040329c3741e6623495b7c9b8c301abb21103bbc4291bebe1d1972849722e9` |
| `production_runner.py` | `77c2df5ffa23f9c6559c47769235643ef7c21dc49cf28cd31d3ffbca99bcca97` |
| `budget.py` | `f42f3cfbbdf424fc5ba327c8aba5161bc039649775ad588923dcca4ac331e89b` |
| `native/route2_mount_helper.c` | `499b76ddd6275ef5589fdba1c39e9a1a98c55697920bd764d99f9b3123cbdf14` |
| `native/route2_mount_helper.h` | `6fe3048f48d69c822f59bf7468cb4815015016a7fb84608c81403a10927bf5e6` |
| `mount_helper_inspection.py` | `b222a2aa93b37ad453ee63b2e24284bf2e391b2cde2199d0eb1501696ae88beb` |
| `phase_observation.py` | `047877749ff563578599bdcfc3c7649b6868384b1af0352e0503641a3115aca9` |
| `native_failure_capture.py` | `710944c666182b2fe9a1fc2ecf2718248a78c63791c3721e1107411e1b444944` |
| `linux_quiescence.py` | `3cd0de584f77f58bdea437a9543abe6efb9d8bb16813c902fb05ea1eab35bc05` |
| `linux_gt_history.py` | `5256f4fc0fc9081e162d31e07047575d3650ebba681cad9504aa2c2cc8673883` |
| `linux_production_controller.py` | `e12a9a86d6cb0ca05f6c6b2f548eec3d13200b301211482513c0155402b9d1e9` |
| `scripts/route2_preimport_launcher.py` | `9052f08153bd6212e17da54c7c437768f743d3b4268440565463077310175c1b` |
| `scripts/route2_host_volume_sample.py` | `69399abdb851f43e7dcb0167641f3b151d54ffa8583c68f09e8ee072a4f5902d` |
| `windows_wall.py` | `62009373a895912d6e33916023ebc0f5e449f52469dd2d81652444bc6d68818b` |
| `windows_control_identity.py` | `5b347987ad976a35d0aed071fb642284938ea5e2817f9c35223acd92e387523a` |
| `windows_native_close_handoff.py` | `f787ae85fb8c74b7659a30d1df701f2388118d7b3bed2d84bf5dc6d96556f58b` |
| `capacity_plan.py` | `a815704f4ee70fc86974ae297ff87b52e53ddea902a04f0f1f9651955c9fba37` |
| `capacity_validation.py` | `3a2cc572c560abbac6dc49e272b806ba6d5e440239a8cac84c81634b9ec7135a` |
| `numerical_equivalence_policy.py` | `0876114b0bde408f33699fd4c6deffc3928f86d6a75235d2eb1d997a6d67426a` |

最小一次完整A+B条件卡新增必填项：实际选定的libc/headers/native-helper兼容路线及全部实际加载身份、V2三层实际对象/策略/原始采样回执、全写路径和外部控制资源及准备费用；以上与数值／计量协议的最终绑定及完整正式review IDs共同重冻。负责人已选Ubuntu22.04／glibc2.35原生helper；实际部署／构建／原生身份仍待补齐，代码仍不得将候选或本节hash装入正式FROZEN_ADMISSION。原授权申请卡SHA仍 `88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf`，本次保持未修改、未提交。


##### 原始注册表绑定及外部墙钟失败保存的继续修补

Windows sampler 的独立质量复审新增两个P1：`REG_SZ BasePath` 被 `expandvars` 错误展开；未读取实际 `VhdFileName`，注册表文件名改变仍可能得到原快照。已修补为仅接受字面 REG_SZ，拒绝未绑定展开语义的 REG_EXPAND_SZ；读取实际 VhdFileName，显式值仅接受 REG_SZ/ext4.vhdx。只有原生 `FileNotFoundError.winerror=2` 才采用可选值的上游 ext4.vhdx 默认，其余读取错误仍拒绝。每次注册表快照包含存在性、原始值、类型和有效文件名，显式值与缺省值之间的变化也必须拒绝。依据：[WSL实际路径组合](https://github.com/microsoft/WSL/blob/master/src/windows/service/exe/DistributionRegistration.cpp)、[可选文件名默认值](https://github.com/microsoft/WSL/blob/master/src/windows/service/exe/DistributionRegistration.h)、[ext4.vhdx常量](https://github.com/microsoft/WSL/blob/master/src/windows/service/inc/wslservice.idl)。该上游源码关系不能替代实际安装版本的语义绑定。修补后整个sampler的独立规范与质量复审均未发现剩余限定范围P1/P2，旧hash 8d0b22…8826被新源码69399a…02d替代，不能沿用旧审阅对象。

外部 Windows QPC 失败路径新增源码修补：handoff challenge 的验证、真实lease身份检查或编码失败，必须消费该原始invocation并关闭原lease；重复绑定或其他绑定失败也遵循同一规则。anchor文件、control目录／卷、完整execution lease关闭异常保留原操作异常和全部cleanup异常，不能用最后一次CloseHandle失败覆盖此前写入／readback／身份验证错误。每个finally显式记录本次操作的primary异常，避免误取调用者正在处理的外层异常。以上源码仍在独立规范复审；host control hard cap、原生deadline、原始启动transport和签名observer完整运行期producer仍缺，本轮未写anchor或签发外部验收。

失败保存／runner的独立静态审查继续核对原始owner、bootstrap消费和失败标记路径；发现项及修订须在当前章节继续记录。失败保存仍不等于真实worker终止、GT撤销、detach/quarantine或合法terminal。四项状态和完整FAIL保持不变。


runner／外部验收继续审查又发现三个P2，已修补源码并进入复核：成功启动后的runner故障未进入保存路径；execution lease constructor/close仅保留第一项关闭错误且可能覆盖primary；trust reader使用ambient `sys.exc_info()`，在调用者正处理其他异常时可能吞掉关闭失败。runner现在仅在原始private owner完整验证后捕获controller/assembly，失败后按原私有invocation/approval和原armed timer尝试一次保存，跳过已有startup abort，不依赖故障后可变的public链接。bootstrap消费与保存异常均与primary合并保留；成功保存的有限回执仍为 StartupPreservedWithoutTeardown，NOT_ATTESTED不变。三个Windows模块共享primary/全部cleanup异常聚合器，原始lease在关闭前消费并转移全部handles，关闭失败不能重试；trust reader显式捕获本次读取的primary，每个owned handle消费一次。尚需本轮独立规范及质量复核闭合；未实际写marker、触及GT或运行runner。

##### 仍须实现／安装的具体生产入口

以下是当前源码的实际缺口，增加Windows管理权限也不会自动填补。每项先形成完整实现及安装方案，再按已授权的准备范围取得证据；本节不授权创建正式研究对象。

| 入口／对象 | 尚缺的生产事实 | 尚待预算／独立复审绑定 |
|---|---|---|
| `production_runner._load_native_path_map`、`_load_native_phase_runner`、`_require_native_nested_producers` | 固定role输入装配、真实phase worker sandbox／IPC、原始spawn/pidfd/wait/reap/status，以及全部backing对象的创建／删除历史；逐role/phase GT授权撤销，含失败清场。 | 全写路径与worker强制方法、TasksMax=2内的完整owner归属；完整实现／安装／失败复审。 |
| `LinuxProductionOSPorts.require_installation_and_write_boundary` | 实际controller/worker安装、全部可写FD/挂载路径限制和整study资源强制，不能接受policy布尔字段。 | guest/carrier/实体分层原生上限、系统写入／元数据、journal及临时和失败保留峰值。 |
| `linux_start_clock._require_actual_start_origin` 与原始startup握手 | 安装目标的pre-Python/pre-spawn时钟语义及原始PID/boot/timens/unit/invocation；原生限时且计费的claim/tombstone；原始QPC与signed Linux-unit双向transport。 | 启动/准备支出及外部observer/helper/launcher/bridge资源；完整原生启动与安装复审。 |
| `LinuxInitialVolumeOSPorts.require_host_execution_boundary` | 实际Windows sampler解释器、held PE/DLL及原生ABI完整身份；已修补的sampler源码尚未运行。 | 新source/runtime及Windows运行期闭包、V2实体对象身份/新鲜原始采样、数值跨OS协议。 |
| `linux_native_close_handoff._require_actual_observer_runtime_closure` | 外部Linux signer/observer自己的pre-import、解释器、stdlib、cryptography及全部ELF/native ABI闭包；不接受study PID的快照代证。 | 新依赖及其准备空间/失败保留，observer在TasksMax=2之外的真实RAM/task/CPU/wall额度。 |
| `windows_wall._require_host_control_boundary` 和最终外部验收 | 真实受保护control目录/卷、原生容量及写deadline；真正unit/PID退出、原始cgroup清场、签名close/exit join和最终durable QPC观察。 | host控制16MiB仍候选，完整控制层计费；实际安装／外部验收及失败收尾复审。 |
| 专用实体边界与容量native verifier | 实际对象位置／具备原生管理能力的执行方式、原生allocated-byte上限、格式化容量/基线/剩余额度及全部可归属写入边界。 | 20/32/34GiB、64/16MiB、历史/未来准备费用及容差继续候选，完整预算与协议复审后由负责人最终绑定。 |

下一步准备顺序保持：先绑定真实部署／ABI基线并完成原生worker与全写路径实现；补原始双时钟transport、observer运行期及独立验收实现；再取得专用对象的实际容量／上限／余额及控制费用，统一冻结新计量／数值／身份后提交完整独立复审。缺少实际位置、原生管理执行能力或预算决定时保持UNKNOWN，禁止把静态算术、既有scratch/13-wheel/合成测试称为实验准入PASS。完整正式review IDs与一次完整A+B owner approval仍未签发。


外部wall依赖复核继续发现两个P2并已修补：native open校验失败后的CloseHandle异常可能遮盖原校验错误；open成功到owned列表append之间的MemoryError可能遗漏新handle。`_Win32.open_readonly`现在显式保留校验primary，并消费一次关闭；`open_owned_readonly`只接受plain list，在append失败时消费一次关闭尚未登记的handle并保留registration/cleanup错误。lease和trust全部acquisition使用同一入口，旧owned handles仍由各自finally处理，不以重开/重试掩盖失败。当前三模块的规范复核及质量审阅未完成前不得声称其清理调用链已全面闭合。


runner质量复审在原有startup abort调用链发现额外P2：账本writer关闭失败已经捕获，但owner.fail_budget_start抛出abort/保存异常时会跳过后面的close_error处理。`BudgetGuard.start`现分别捕获原始startup异常、writer-close异常、abort异常，在结构化primary_error／writer_close_error／abort_error／secondary_errors中完整保留；writer discard与owner abort均只尝试一次，不引入新的Linux依赖，也不把保存异常改为成功terminal。此补充修订正在独立规范与质量复核。新post-start保存入口本身暂未发现剩余限定范围P1/P2，完整A+B复审仍FAIL。


##### 负责人已选Ubuntu22.04／glibc2.35原生helper路线

负责人最新答复明确保留Ubuntu22.04／glibc2.35，增加经独立复审与冻结的native helper，另计编译与ABI准备成本。此项部署ABI基线选择覆盖此前“路线尚待答复”，不授权实验；20/32/34GiB、64/16MiB和数值容差继续候选。实际专用环境的位置、管理执行能力及完整原生对象仍未绑定，原科学13-wheel只能保留为历史准备证据。

已新增 `native/route2_mount_helper.c` 与 `.h` 源码：Linux x86-64 LP64、glibc2.35编译目标门；全部syscall号只由实际工具链的 `SYS_*` 头文件提供，缺少定义编译即拒绝，无猜测号、重试、shell或legacy mount fallback。四个namespaced入口覆盖open_tree/mount_setattr/move_mount/umount2，每个最多一次native syscall并保留errno；mount_attr大小/offset和40-byte版本化ABI描述进入编译约束。源依据为[Linux5.15 mount UAPI](https://raw.githubusercontent.com/torvalds/linux/v5.15/include/uapi/linux/mount.h)和[Linux syscall接口](https://man7.org/linux/man-pages/man2/syscall.2.html)，这两份上游资料不能代替实际目标headers的身份。native源码正在独立规范静态审阅；本轮未编译、链接、加载或调用它。

接入次序：先对实际compiler/linker／glibc／UAPI/asm headers、全部include闭包和预处理宏、完整flags/link map、symbols/build-id/ELF依赖及失败输出进行身份与预算复审；在批准的准备边界内形成实际helper及ABI回执，再与新的完整source/runtime闭包一起冻结；固定只读helper装载器必须在任何CDLL/dlopen及constructor之前证明实际ELF与传递native身份，实际加载后核对ABI；随后才能由原始broker记录原生调用历史。当前 `_libc` 仍要求libc直接exports，没有把新C源码接为生产权限，也没有用schema、HMAC或安装布尔字段绕过loader的原生身份缺口。不能称当前Ubuntu22.04完整broker已可运行。

另计的准备支出至少包括compiler/linker/header工具链、include/预处理输出、object/shared-library/debug/symbol/link-map、所有临时和失败保留、cache/core/log以及readonly安装／新manifest和复审；bytes/wall/RAM/task/CPU与各层峰值／余额均尚未实测和最终绑定，不能缺省0。该helper只补ABI接口，不能补pre-Python启动origin、原始QPC transport、worker/GT历史或原生hard cap。

Windows质量复审另外发现两个P2并进入修订：重复调用lease/invocation `__init__` 会覆盖旧原始状态或孤立旧handles；丢弃weak owner会在存活进程中丢失raw handle的关闭入口。现以私有WeakSet拒绝同一exact-type对象的重复初始化，constructor只处理本次published state；增加捕获私有state而非self的cleanup-only finalizer，仅在原始PID内消费一次关闭，abandonment不会创建／签署任何验收或重试。normal close后的finalizer跳过已消费state，错误留在私有process记录中；相关规范／质量复核尚未闭合。runner＋startup异常聚合的独立规范与质量复审则均未发现剩余限定范围P1/P2，未签正式review ID。四项状态和完整FAIL继续有效。


owner生命周期的规范复核另定位并修补两个P2：init WeakSet的check+insert在私有Lock内原子完成且在native acquisition前释放；lease/invocation state只弱引用原Thread，全部正常lease/wall/trust检查均按referent对象身份核对，避免finalizer参数通过Thread属性间接强引用owner。限定三模块调用链规范复核未发现剩余P1/P2；质量复核尚在进行。C/H helper及broker对应ABI的规范、质量静态审阅均未发现限定范围P1/P2，无正式ID，不证明可编译、实际ELF/native运行期、原始装载身份或实验准入。


##### 2026-10-05 共享WSL构建条件盘点与装载前检查实现范围

截至本节，Windows owner生命周期质量复核因审阅执行器用量限额中断，尚未完成；这不是自动审批拒绝，也没有签发正式review ID。矩阵中的“复核中”由此更新为“中断／未完成”。此前规范范围未发现剩余P1/P2的结论不能代替这项质量复核或完整A+B复审。

Windows只读盘点时间2026-10-05T17:11:08.4935272Z：WSL2 2.6.3.0、kernel版本6.6.87.2-1、Windows10.0.26300.9457；唯一现有Ubuntu-22.04当时Stopped、WSL VERSION2。随后于下列时间在这个共享发行版启动一个 `python3 -I -B -` 标准库元数据盘点进程，仅读取os-release、dpkg状态、四份headers和gcc/ld/readelf文件身份及root全局空闲。未调用compiler/linker/readelf、未编译／装载helper，未导入项目或科学依赖，未读取GT、运行测试或生产控制器。启动现有发行版产生的普通init/journal/VHDX及系统控制写入和完整启动CPU/RAM/task/wall/bytes均为UNKNOWN_NOT_ZERO；下列进程内wall仅覆盖元数据脚本，不是外部QPC验收，也不能归属全局空间变化为本研究成本。此共享环境不是已绑定的专用runner，空闲量不是正式创建前双层检查。

原始工具输出的结构化ASCII JSON段如下（工具输出前的WSL本地化诊断未作语义或身份依据）。文件hash与路径仅为该时点元数据，非不可变运行期或完整include/ELF闭包：

```json
{
  "kind": "READ_ONLY_SHARED_DISTRO_BUILD_METADATA_INVENTORY_NOT_ADMISSION",
  "utc": "2026-10-05T17:18:37.260126+00:00",
  "machine": "x86_64",
  "kernel": "6.6.87.2-microsoft-standard-WSL2",
  "uid": 1000,
  "python": "3.10.12 (main, Aug 31 2026, 10:18:17) [GCC 11.4.0]",
  "os_release": {
    "path": "/etc/os-release",
    "resolved_path": "/usr/lib/os-release",
    "bytes": 386,
    "sha256": "594d5ddd35aedb47f00d9c34d140017907a5b9f93c975aba125fc924daac5c07",
    "device": 2096,
    "inode": 2671,
    "mode": "0o100644",
    "uid": 0,
    "text": "PRETTY_NAME=\"Ubuntu 22.04.5 LTS\"\nNAME=\"Ubuntu\"\nVERSION_ID=\"22.04\"\nVERSION=\"22.04.5 LTS (Jammy Jellyfish)\"\nVERSION_CODENAME=jammy\nID=ubuntu\nID_LIKE=debian\nHOME_URL=\"https://www.ubuntu.com/\"\nSUPPORT_URL=\"https://help.ubuntu.com/\"\nBUG_REPORT_URL=\"https://bugs.launchpad.net/ubuntu/\"\nPRIVACY_POLICY_URL=\"https://www.ubuntu.com/legal/terms-and-policies/privacy-policy\"\nUBUNTU_CODENAME=jammy\n"
  },
  "package_status_identity": {
    "path": "/var/lib/dpkg/status",
    "resolved_path": "/var/lib/dpkg/status",
    "bytes": 1084129,
    "sha256": "f473e0d091187899bb3633e305344e674768d7bc1f5041e7e85ec296d260aaa0",
    "device": 2096,
    "inode": 18107,
    "mode": "0o100644",
    "uid": 0
  },
  "packages": {
    "binutils": {
      "Version": "2.38-4ubuntu2.12",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "cpp-11": {
      "Version": "11.4.0-1ubuntu1~22.04.3",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "gcc": {
      "Version": "4:11.2.0-1ubuntu1",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "gcc-11": {
      "Version": "11.4.0-1ubuntu1~22.04.3",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "libc-bin": {
      "Version": "2.35-0ubuntu3.15",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "libc6": {
      "Version": "2.35-0ubuntu3.15",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "libc6-dev": {
      "Version": "2.35-0ubuntu3.15",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "libgcc-11-dev": {
      "Version": "11.4.0-1ubuntu1~22.04.3",
      "Architecture": "amd64",
      "Status": "install ok installed"
    },
    "linux-libc-dev": {
      "Version": "5.15.0-194.204",
      "Architecture": "amd64",
      "Status": "install ok installed"
    }
  },
  "headers": [
    {
      "path": "/usr/include/features.h",
      "resolved_path": "/usr/include/features.h",
      "bytes": 17860,
      "sha256": "dcd1855804e2c64d528adb4c9c36f1567c67472a47654d4302d61b32eacd294b",
      "device": 2096,
      "inode": 1735,
      "mode": "0o100644",
      "uid": 0,
      "selected_macro_lines": []
    },
    {
      "path": "/usr/include/linux/mount.h",
      "resolved_path": "/usr/include/linux/mount.h",
      "bytes": 5092,
      "sha256": "5bfcc55e59c446ea9fd945a42184d2782547ac92c59e8898310f316f18ad2dab",
      "device": 2096,
      "inode": 239530,
      "mode": "0o100644",
      "uid": 0,
      "selected_macro_lines": [
        "#define MOUNT_ATTR_SIZE_VER0\t32 /* sizeof first published struct */"
      ]
    },
    {
      "path": "/usr/include/x86_64-linux-gnu/bits/syscall.h",
      "resolved_path": "/usr/include/x86_64-linux-gnu/bits/syscall.h",
      "bytes": 45553,
      "sha256": "4f14dc07155d99c63b6a014abd86145df425d2bf741dab1bdd2858cc021a4de5",
      "device": 2096,
      "inode": 120685,
      "mode": "0o100644",
      "uid": 0,
      "selected_macro_lines": [
        "# define SYS_mount_setattr __NR_mount_setattr",
        "# define SYS_move_mount __NR_move_mount",
        "# define SYS_open_tree __NR_open_tree",
        "# define SYS_umount2 __NR_umount2"
      ]
    },
    {
      "path": "/usr/include/x86_64-linux-gnu/asm/unistd_64.h",
      "resolved_path": "/usr/include/x86_64-linux-gnu/asm/unistd_64.h",
      "bytes": 9687,
      "sha256": "9f1c975001d7cd39af3a2c14d518d80b0aaaab8bec3ad12b5e56419bdc8cafbe",
      "device": 2096,
      "inode": 240114,
      "mode": "0o100644",
      "uid": 0,
      "selected_macro_lines": [
        "#define __NR_umount2 166",
        "#define __NR_open_tree 428",
        "#define __NR_move_mount 429",
        "#define __NR_mount_setattr 442"
      ]
    }
  ],
  "tools": {
    "gcc": {
      "path": "/usr/bin/gcc",
      "resolved_path": "/usr/bin/x86_64-linux-gnu-gcc-11",
      "bytes": 928584,
      "sha256": "821af3c74506283c179ca413bb33e6b528805a4dd8a5c09df125e5ad560a9e89",
      "device": 2096,
      "inode": 53248,
      "mode": "0o100755",
      "uid": 0
    },
    "ld": {
      "path": "/usr/bin/ld",
      "resolved_path": "/usr/bin/x86_64-linux-gnu-ld.bfd",
      "bytes": 1736184,
      "sha256": "58937fc20c21e147883b4fdaa0fc7438a8e8f2bb886cfcaa4896100ca91139e7",
      "device": 2096,
      "inode": 50803,
      "mode": "0o100755",
      "uid": 0
    },
    "readelf": {
      "path": "/usr/bin/readelf",
      "resolved_path": "/usr/bin/x86_64-linux-gnu-readelf",
      "bytes": 776640,
      "sha256": "04db0000749aff89e4af21429340b00b536fc6f80e811c872c006507881a5560",
      "device": 2096,
      "inode": 50809,
      "mode": "0o100755",
      "uid": 0
    }
  },
  "root_filesystem_available_bytes": 1013998739456,
  "dedicated_boundary_bound": false,
  "inventory_process_wall_ns_only": 19432601,
  "startup_control_writes_and_resource_cost": "UNKNOWN_NOT_ZERO",
  "include_closure_or_effective_compiler_abi_proved": false
}
```

本次源码任务先补一个仅接收有界bytes的helper产物检查器：解析实际ELF header、program headers、PT_DYNAMIC、GNU build-id及动态依赖／搜索路径／初始化标签，并校对40-byte ABI描述。它不读取磁盘、不运行readelf/ldd、不调用CDLL/dlopen/describe/syscall，不产生安装权限、receipt或准入。输出必须明确为准备元数据；ELF导出与重定位、符号提供者、完整传递依赖、readonly原始FD/挂载、实际已加载原生对象、pre-import连续性和计费边界仍须由生产loader证明。原broker的直接libc入口目前保持未接入；不以这个检查器绕过尚缺的原生producer。

预算保留：实际compiler主文件3项和headers4项已经有时点身份，仍缺compiler helper/as/collect2、启动文件与include完整闭包、effective macros/flags、link map/symbols、实际helper/ABI、临时与失败保留、readonly安装费用和逐层峰值／余额。这些费用另计但尚无最终额度，不能因现有安装而记0。四项状态、完整FAIL、候选容量／容差以及无正式研究对象的限制继续有效。


##### 本次实现增量、实体边界交付顺序及条件卡补项

新增 `mount_helper_inspection.py` 只进行plain bytes内的受限ELF64/动态表/strings/build-id检查和40-byte ABI描述校对；未执行检查器、未获得真实helper产物。当前范围不覆盖符号表、重定位／版本／提供者、constructor内容或传递加载身份。依据为[ELF动态链接格式](https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.dynamic.html)与[ELF程序表](https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.pheader.html)。生产接入必须在第一次加载之前绑定传递依赖和原始readonly对象，因为动态加载可能递归加载依赖并执行初始化代码（[Linux dlopen说明](https://man7.org/linux/man-pages/man3/dlopen.3.html)）；设置RTLD_LOCAL／RTLD_NOW或use_errno不能代替身份。产物检查器不接入原broker，不使当前glibc2.35直接exports变为可用。

GT失败保存的本次源码修订：原grant吞掉read-scope/owned-FD/cleanup/history/ledger异常，owned-FD与kernel ReadScope仅保留第一次关闭失败；原finally还可能用关闭异常覆盖读取／原生观察故障。现在grant/revoke/install保留原始primary和全部secondary，poisoned private owner另保留process-local failure_errors；全部FD先消费、每个最多一次close，无重试。原生FD返回后或普通kernel FD打开后登记失败时，未登记FD的关闭也消费一次；GT读取／mount观察和quiescence范围明确传递本次primary。history或fsync失败仍为失败证据，不能称为durable成功；mount撤销或worker退出仍可能NOT_ATTESTED，不能用异常保存升级为清场回执。修订对象必须重新做独立规范及质量复核，旧hash的窄结论不能继承。

容量源码现强制独立列出 `native_mount_helper_build_and_abi_freeze` 准备分类，PreparationCost增加显式CPU额度，验证／owner预算绑定包括bytes/wall/RAM/task/CPU全部字段；缺项维持拒绝。负责人选择的Ubuntu22.04/glibc2.35只作为部署ABI基线，实际目标和helper产物继续None；未填任何新预算数值。科学13-wheel、readonly源码拷贝、实际native安装以及编译／失败输出等支出需按实际对象拆分，禁止把既有安装当免费或在同一层重复叠加父容器和内层数据。20/32/34GiB、64/16MiB与数值容差仍候选。

实体部署与费用的具体交付顺序仍属于准备计划，未执行：

| 顺序 | 必须交付的可审阅对象／证据 | 缺失时的处理及代价 |
|---|---|---|
| 1 | 专用目标位置、管理执行身份；现候选E:/Route2Dedicated/route2-fixed-carrier.vhdx及Route2Dedicated注册对象，实际GUID/file ID/allocated extents仍None。 | 本会话访问授权不能提升Windows token；目前不得建立正式对象。若实际执行环境不同，重新绑定OS/依赖与数值身份。 |
| 2 | 准备预算ID及原生资源／全部输出边界：toolchain、helper build、ABI、staging/cache/core/log/失败保留和readonly安装，历史与未来费用分开。 | 现有共享WSL盘点和历史准备不能提供per-study cap；费用UNKNOWN_NOT_ZERO。还需明确外部observer/launcher/helper/bridge的CPU/RAM/task/wall。 |
| 3 | 实际固定预分配carrier、guest VHDX、格式化容量与原始held文件/卷/注册身份，以及外层NTFS和宿主系统写入的可强制归属上限。 | 固定carrier32GiB只限制容器，不能单独证明“含外层元数据／C/E系统效果”的实体34GiB硬上限。全部归属写入必须可计量并受限；不能以共享卷空闲替代。 |
| 4 | 实际readonly helper/完整ELF依赖与pre-import装载身份、GT broker/worker全写路径和逐role/phase发行／退出／撤销历史；原始双时钟交接与外部签名验收。 | 候选ELF/ABI元数据、HMAC文件或政策布尔字段均不能生成原生事实；真实kernel/host失败行为、关闭后墙钟和清场仍缺。 |
| 5 | 实际三层baseline／峰值保留／cleanup／余额。准备费用、控制层和扩容归属决定；正式创建前同一invocation内guest FS及实际实体卷各≥8GiB。 | carrier没有第三项负责人确认的8GiB floor；仍须独立满足经批准的增长与收尾reserve。2GiB D_A严格上界不是实测峰值。 |
| 6 | 新完整source/runtime/role/计量/数值冻结，完整实现、安装、预算、失败、外部验收及跨OS数值的独立正式复审。 | 当前81文件的源码工作集hash只作追踪；实际ELF/helper/observer及全运行期闭包未冻结，review IDs尚未签发。之后仍需一次完整A+B负责人授权。 |

一次完整A+B最小条件卡在原章节草案基础上补齐以下字段，当前状态继续 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED：

| 条件卡字段 | 当前已确认／已有证据 | 仍须最终绑定 |
|---|---|---|
| 唯一研究及范围 | route2-candidate-overlap-v1-001；一次完整A+B，Stage A失败按协议终止；无A-only申请。 | 独立正式review ID、owner approval ID、完整seal均未签发；FROZEN_ADMISSION=None。 |
| 信任／部署对象 | Windows owner可信，WSL2 worker隔离；Ubuntu22.04/glibc2.35 helper路线已选。 | 实际管理执行方式／专用对象／全写边界、readonly完整代码和原生依赖身份。 |
| 已确认实验预算方法 | 1200/3600/900秒，60秒在原额度内；C=min(4GiB,3/5启动可用RAM)、AS=C/2、TasksMax=2含controller，通常1 worker；D_A=2GiB严格上界V2。 | 真实启动RAM与原生强制、正式2→4GiB门；实际三层上限/容量/余额，全部控制与准备和外部资源额度。 |
| GT／评价协议 | 20次GT-backed＋第21次GT-free代数pooled，pooled GT reads=0。 | 全role/phase授权、原始worker身份/退出和全backing对象历史、GT/FD/maps撤销含失败；真实生产runner尚未完整。 |
| 墙钟／完成条件 | 两个原始时钟和terminal后外部验收要求保留，源码失败消费／异常聚合已有修补。 | pre-Python origin与原始QPC transport，observer运行期、签名close/exit join、原始cgroup清场和final durable QPC实际证据。 |
| 数值／复审 | atol1e-12、rtol1e-10及离散完全一致仍候选；历史PARTIAL_MATCH_ONLY不升级。 | 完整跨OS特征/概率/指标/排序与阈值边界证据，负责人最终协议裁决，以及完整实现／安装／预算正式复审。 |

上述卡是待负责人最终确认的条件汇总，不是授权或准入PASS。准备视图仍PREPARED_UNREVIEWED；A+B尚未获授权且FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二没有合法结果。独立完整实现结论仍FAIL。Route3 v1-003保持合法COMPLETE／四门FAIL，不重跑；gap=0由路线二覆盖。只有负责人提供合法路线二结果后才讨论三个架构方向的最小验证，本次不自动启动任何方向。


##### 本轮追加P2修订与限定复审状态（此前“复核中”由本节更新）

Windows owner生命周期的质量审阅已在限额恢复后完成，三模块清理／init／finalizer调用链的规范与质量静态复核均未发现剩余限定范围P1/P2，没有签正式ID。helper产物检查器的规范复审发现并修补两个P2：glibc2.35支持的FILTER/AUXILIARY等字符串不得遗漏；不支持的五类标签现显式拒绝。PT_NOTE必须按实际4/8对齐解析descriptor和下一note，不能丢弃p_align后固定4。修订后的完整检查器规范与质量静态审阅均未发现剩余范围P1/P2，实际helper仍未编译／装载。预算两模块的质量复审另发现并修补两个P2：preparation scope须plain非空白str，receipt必须显式包含每个claim键；confirmed methods在两入口均逐字段精确type和值锁定，不能用bool/float替代0/1。修订后规范和质量静态复核均未发现剩余范围P1/P2，无正式ID。

GT失败保存还在追加规范复核，不能继承旧源码的静态结论：新增NativeFailureCapture，在GT owner及kernel ReadScope获取自身FD前预分配1024／544错误槽与wrapper，普通kernel opens先预约owned槽再os.open，native返回FD登记失败先close一次。所有record调用的入口也由调用方保护：frame分配失败写入预留槽及aggregation_error，不能阻止剩余关闭。原native负返回的errno故障在后续history/ledger之前固定保存；共享wrapper的primary只锁一次，grant/revoke/install在清理前固定原始primary，关闭或format故障只能追加。tuple化在close循环后尝试，失败保留预留槽；overflow／process death／OOM-kill均不能称完整历史或clean teardown，外部quarantine仍缺。新增buffer内存、exception/traceback保留、源码写入及全部准备费用待真实预算绑定，不能按槽数量推断实际RAM支出或记0。源码检查不是故障注入或运行期证明，GT/worker的NOT_ATTESTED不变。

| 本轮追加范围 | 规范静态复核 | 质量静态复核 | 可下结论的边界 |
|---|---|---|---|
| Windows owner生命周期／完整三模块清理调用链 | 已完成，未发现剩余范围P1/P2 | 已完成，未发现剩余范围P1/P2 | 无实际host cap/签名验收；无正式ID。 |
| ELF／40-byte ABI候选产物检查器 | 两P2修订后未发现剩余范围P1/P2 | 未发现剩余范围P1/P2 | 纯bytes元数据；未执行、未取得实际产物或原生装载身份。 |
| helper准备CPU/scope／方法类型及预算claims绑定 | 两P2修订后未发现剩余范围P1/P2 | 两P2修订后未发现剩余范围P1/P2 | 金额／额度与实际对象仍UNKNOWN，全部候选保持。 |
| GT/root ReadScope预留错误槽、原始primary及调用入口保护 | 多轮P2修订后未发现剩余限定范围P1/P2 | journal追加P2修订后未发现剩余限定范围P1/P2 | 真实发行／退出／撤销与失败清场、全写路径未证明。 |

本节最新源码追踪如下；不是冻结manifest、完整运行期闭包或正式复审对象：

```json
{
  "scope": "working source tracking; NOT frozen/runtime/admission",
  "files": 81,
  "logical_bytes": 2064551,
  "mapping_sha256": "f5ad68da431a21b29a3733f89fa9385991f8bbd3ae81c2a2100f213d253ff31b",
  "python_ast_only": 53,
  "native_source_text_only": 2,
  "historical_test_hash_only": 26,
  "no_import_test_native_or_helper_execution": true,
  "hashes": {
    "native_failure_capture.py": "710944c666182b2fe9a1fc2ecf2718248a78c63791c3721e1107411e1b444944",
    "linux_gt_history.py": "5256f4fc0fc9081e162d31e07047575d3650ebba681cad9504aa2c2cc8673883",
    "linux_quiescence.py": "3cd0de584f77f58bdea437a9543abe6efb9d8bb16813c902fb05ea1eab35bc05",
    "phase_observation.py": "047877749ff563578599bdcfc3c7649b6868384b1af0352e0503641a3115aca9",
    "mount_helper_inspection.py": "b222a2aa93b37ad453ee63b2e24284bf2e391b2cde2199d0eb1501696ae88beb",
    "capacity_plan.py": "a815704f4ee70fc86974ae297ff87b52e53ddea902a04f0f1f9651955c9fba37",
    "capacity_validation.py": "3a2cc572c560abbac6dc49e272b806ba6d5e440239a8cac84c81634b9ec7135a"
  }
}
```

四件事再次分别核对：①准备视图已生成，仍PREPARED_UNREVIEWED；②一次完整A+B尚未获授权，FROZEN_ADMISSION=None；③Stage A/B均未合法运行；④路线二没有合法结果。完整独立实现复审仍 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` / FAIL；本节窄复核与scratch/13-wheel/合成测试均不构成实验准入PASS。原授权卡不修改；新增条件卡内容仍在原三份文档整合修订内。实际专用对象／原生容量与余额、完整生产runner和worker写边界、启动双时钟、实际readonly native loader／observer、terminal后签名外部验收、最终预算／容差和完整独立review IDs继续缺失。


GT／journal质量复核发现最后一个直接调用链P2并已追加修补：phase._journal读／校验／解析先失败N、finally close失败M时不能由M替代N。该reader现于临时fd打开前预留generic 4槽，直接锁N并一次close；M放入secondary槽，直接传播预分配wrapper，不引入Linux依赖、record/report helper或关闭重试。GT原owner仅接受exact NativeFailureCapture及其原failure对象的报告，直接锁raw N，保留wrapper/M。该追加两函数的规范与最终质量静态复核均未发现剩余范围P1/P2，未签正式ID；本轮限定源码范围复核闭合，实际运行期及完整A+B准入仍未闭合。

所有cleanup/report dispatch前的原始primary锁定、close/close_one调用方剩余FD消费、每次aggregation/format失败独立槽保留已纳入规范复核。它们是进程内源码失败保存；实际durability、真实GT撤销、individual worker exit、全写路径、整study强制、原始双时钟、外部签名验收和OOM-kill/crash quarantine仍缺。新source/raw-byte工作集只追踪当前修订，未执行其中任何新代码。完整A+B review FAIL及四项未准入状态继续有效。


##### 本轮收尾：限定源码复核闭合，完整准入继续阻塞

追加journal直接调用链的独立规范与质量静态复核均未发现剩余具体P1/P2；与此前GT／ReadScope／NativeFailureCapture三模块范围的结果一起，闭合本轮已报源码失败保存项。ELF／ABI产物检查器、helper准备预算／CPU／scope／方法类型及Windows生命周期也已完成各自规范与质量静态复核。均未签发正式review ID，均不是完整A+B实现／安装或实验准入PASS。本轮未运行或新增测试、未import项目、未编译／链接／装载helper或调用其ABI／syscalls；唯一WSL执行为上节共享发行版的标准库只读构建元数据盘点，正常启动控制写入费用仍UNKNOWN_NOT_ZERO。

实际仍缺：专用对象位置及具备原生管理能力的执行方式、可强制含全部外层／宿主归属写入的实体上限与三层实际容量／baseline／余额；完整runner、真实worker身份及所有backing对象创建／退出／删除历史、逐role/phase GT撤销和全写路径强制；pre-Python start与原始QPC的认证transport、完整readonly code/stdlib/PE/ELF/native ABI身份、独立observer/signature及terminal后外部墙钟验收。编译／ABI、控制层、历史／未来准备和外部资源费用、数值容差仍待负责人在实际证据及完整复审后最终绑定；20/32/34GiB、64/16MiB等继续候选，不能填成已批准。完整实现、安装／依赖、资源／失败／退出验收、跨OS数值及预算正式复审IDs仍未签发。

四项状态最终核对不变：准备视图PREPARED_UNREVIEWED；A+B未授权且FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二无合法结果。最小一次完整A+B条件卡继续APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，完整复审仍FAIL。原授权申请卡SHA-256仍88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf；未创建正式image/volume/study/ledger/lock、未打开GT view、未重跑Route3或启动任何架构方向。本轮讨论与状态仅更新原三份文档的整合后修订，无新交接包；全部工作树改动保留未提交。


##### 2026-10-07 整合后续补：最终匹配集合对照与原生退出消费（限定源码准备）

本节接续“2026-09-29整合后修订”及其最新追加修订，是本轮状态依据；历史局部收尾不代表完整生产实现或实验获准。已恢复原设计、WSL执行计划、原review、原授权提示和申请卡，并读原始disk/cgroup/wall探针及Linux依赖证据；没有新建交接包，也没有改原授权提示／申请卡。

四项分别核对：①准备登记／投影视图仍PREPARED_UNREVIEWED；②一次完整A+B未获授权，contracts.FROZEN_ADMISSION=None；③Stage A/B均未合法运行；④路线二没有合法结果。完整独立实现复审仍为 route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL。原scratch 2→4GiB、13-wheel、历史合成测试、PARTIAL_MATCH_ONLY和窄静态复核均只作准备证据，不构成实验准入PASS。

恢复时先核对原81文件工作集：2,064,551逻辑字节、mapping SHA256 f5ad68da431a21b29a3733f89fa9385991f8bbd3ae81c2a2100f213d253ff31b，与上一轮最新记录相同。Windows wall/lease/trust、ELF/40-byte ABI准备检查、helper准备分类与CPU/scope/claims/精确方法类型、GT／quiescence／journal失败保存结论仅在相同hash的原限定范围内继承。native_failure_capture.py、linux_gt_history.py、linux_quiescence.py、phase_observation.py、mount_helper_inspection.py、capacity_plan.py、capacity_validation.py的当前hash仍与上一节逐项相同；本轮改变的九文件另做限定独立复审。

| 重新核对的原始准备证据 | SHA256 | 仍可下的结论 |
|---|---|---|
| 2026-09-29-route2-wsl-disk-probe-raw.json | a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939 | 同mount/dev/FS UUID的2→4GiB及ENOSPC准备证据；不是正式实体部署或新study准入。 |
| 2026-09-29-route2-wsl-cgroup-probe-raw.json | 7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9 | 第三task/VMS拒绝不证明实际RSS硬边界和完整worker准入。 |
| 2026-09-29-route2-wsl-wall-probe-raw.json | 302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c | 外部durable完成验收未闭合。 |
| route2-linux-cp310.lock／identity.json | c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76 / fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f | Ubuntu22.04/glibc2.35/Python3.10.12的13-wheel准备身份；不是专用目标或stdlib/native readonly加载闭包。 |
| 2026-09-29-route2-linux-dependency-runtime.md | d0f352f70b5721d58cef37eae97c7a20e16212531c262f43c1a1e8f6fd8b83b0 | 历史依赖准备记录，后续源码和完整nested数值仍未闭合。 |

本轮只读Windows核对：当前账号 LAPTOP-339GMS1N\Fancy，实际token无提升管理员权限；E:/Route2Dedicated及候选route2-fixed-carrier.vhdx均不存在，注册表只有既有共享Ubuntu-22.04（Version2，位于C盘用户LocalState）。没有启动WSL，也没有取得本轮新的Linux正式对象stat；正式namespace缺对象结论仍须区分既有只读证据与新的部署事实。完全访问权限继续表示准备授权，不能产生提升token或实验授权；缺口还包括执行后端、原生producer、实体cap、加载边界、预算和验收，不能归纳为“只缺管理员权限”。

实际源码增量如下。

1. 最终matched-GT对照P2：新增control_matches.py，不再以候选覆盖的新增／丢失替代最终命中集合。它提供五个历史A2-004 outer最终匹配集合的严格元数据登记和子进程物理reader：原始readonly FD、root-owned单链接普通文件、大小界限、前后身份／hash一致、规范JSON及重复键／重复GT拒绝；字段仅participant_id/event_index，限定到对应outer evaluation participant集合。读取／解析primary及一次close的secondary均保存。未生成、打开或核验任何真实历史GT投影；原A2-004最终metrics身份、逐文件授权／来源对应关系、五个真实readonly投影、原生发布／撤销和冻结值仍缺。
2. contracts.py／path_map.py／production_metadata.py／production_runner.py把这五个投影及来源metrics hash显式纳入登记；新增冻结字段a2_004_final_metrics_sha256、control_final_match_registry_sha256。旧准备schema/seal不能覆盖新形状，后续必须重新复审／冻结，当前不填任何批准值。新outer_control_final_matches phase只允许与同一outer_evaluation scope配对；训练／inner不得使用。字段、digest和投影attestation只是待原生证明的绑定条件，不能制造grant或readonly事实。
3. phase_worker.py／stage_b.py在获准outer终评子进程内用同一GT commitment key比较合法历史control最终集合与treatment匹配对，父进程只接收commitments。逐fold及pooled分别保存control_matched_gt_commitments、matched_gt_added_commitments、matched_gt_lost_commitments，并独立保留原candidate覆盖差值；校验与同outer eligible集合的关系、canonical集合及逐fold／pooled差值一致，合法历史control的pooled TP必须为154。没有增加control evaluator：仍20次GT-backed评价＋第21次GT-free代数归并，pooled_gt_reads=0。Stage A预flight只核登记，不读最终match投影；新物理投影的实际合法生成和native scope发布仍阻塞。
4. execution.py终态失败P2：Stage A与Stage B各在开始前预分配TerminalFinalizationFailure。原stage异常与guard.finalize()第二异常均以raw对象保留（primary_error／terminal_error／secondary_errors），wrapper沿原异常链传播，状态仍INCOMPLETE_RESOURCE。terminal尝试只消费一次，不以重试掩盖失败；代码异常保留不证明终态durability或清场。
5. 优先级1中选取可独立审阅的原生退出消费子原语：新增linux_child_exit.py，真实调用P_PIDFD waitid／pidfd_send_signal／poll，先WNOWAIT观察，再最多一次实际reap，保留原生pid/uid/signo/code/status和单调时钟；只有P_PIDFD wait成功证明当前父进程可wait后才允许通过held pidfd收尾kill，没有numeric-PID回退。借入pidfd不关闭，dup和fdinfo两个owned FD各最多一次close；timeout／signal／nonzero／原生等待／close均失败并保存primary和各secondary。独立静态初审提出的两个P2已修补：cleanup deadline检查覆盖失败kill和reap开始；失败及close直接写预留槽，去除失败路径聚合闭包和收尾动态tuple分派。

退出子原语尚无生产调用者：没有实现或证明原始spawn／pidfd_open／birth持有、deadline预算来源、UID/namespace/IPC隔离、逐role授权、全worker写路径、全部backing对象创建／删除历史或最终清场。它不签退出receipt、不给权限，不得以caller传入PID/deadline升级为原生事实；child_exit_attestation=NOT_ATTESTED、history_complete=False。完整phase-worker生产组件尚未闭合，本轮只是补了其中实际内核wait/reap/status的源码子组件；没有绕过任何生产入口拒绝。

| 本轮限定独立复审 | 规范／质量静态结果 | 结论边界 |
|---|---|---|
| execution.py、control_matches.py、contracts.py、path_map.py、production_metadata.py、production_runner.py、phase_worker.py、stage_b.py | 独立只读复审未发现剩余范围P1/P2 | 对照集合合同及失败保存源码；未签正式review ID，不覆盖真实投影、producer、OS、数值或完整A+B。 |
| linux_child_exit.py | 上述两P2修补后最终独立只读复审未发现剩余范围P1/P2，核对下表hash | wait/reap/status与一次消费源码；未签正式review ID，没有实际内核、spawn、权限或退出验收证明。 |

本轮修改文件及限定复审版本：

| src/eating_event/route2_candidate_overlap/ 下文件 | 字节 | SHA256 |
|---|---:|---|
| execution.py | 28394 | 4e195dfd4812ee964124ec8b8d2f3be10e9fe388cc8c0fb6c629fe934ef4d62e |
| control_matches.py | 10698 | 28b5c11c0ffb8ec1c9dc137a43c1642cab2a31a69f0d0ca3187581e739aac112 |
| contracts.py | 25477 | 8b449806780ec87be2210f8cf069b3143ba74c3187d07e0bf089fc2ef8866840 |
| path_map.py | 30276 | fcc35210a77855d5175a9f51ce05175e0319f38eae697d6e544b987a8023221e |
| production_metadata.py | 41705 | 4b42eac0b4e1868cd9f0d9ed6f5d25e1810ec69d7806eb7fd4dff57d4af3c4b3 |
| production_runner.py | 23025 | bb785d22c6a83b3d9bdd1eef1baf83df9d540cd85136a04130aa21dd83e703c5 |
| phase_worker.py | 13085 | 20e52e548b8c356fda311a699b3c157f1e4421271e0d3eb3f04d342f72081ced |
| stage_b.py | 76124 | 41a58c2ad7c56fa9d4bb17bd37ecd4fc3a6396680c843f23a62b9181293ae09e |
| linux_child_exit.py | 8849 | 2ab1db487b7f523b31d4af7cf7b8a2e8cd89c0b2086ebf617c42dfa4ebad13a8 |

当前工作集包括51个Route2 Python模块、4个相关scripts、2个native C/H文本、26个历史测试。55个生产Python文件只做AST；26个历史测试只算hash，未修改／新增／运行；C/H只读文本hash，未编译、链接、装载或调用。下面是源码追踪，不是完整source/runtime冻结：

```json
{
  "scope": "working source tracking; NOT frozen/runtime/admission",
  "files": 83,
  "logical_bytes": 2096023,
  "mapping_sha256": "6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93",
  "python_ast_only": 55,
  "native_source_text_only": 2,
  "historical_test_hash_only": 26,
  "historical_test_mapping_sha256": "469312e5c5ef487681d4bf5ec25c0cc4cf6957ad891912ccc638b34c9cca1b70",
  "no_import_test_native_or_helper_execution": true
}
```

固定生产链及真实事实仍按五项优先级列明：

| 优先级／具体代码入口 | 本轮推进 | 尚缺的真实producer／对象／依赖 |
|---|---|---|
| 1：production_runner._load_native_path_map、_load_native_phase_runner、_require_native_nested_producers；stage_b.execute_phase生产controller分支 | 最终match物理reader／传递合同及原生退出消费源码 | 三入口仍直接拒绝，StageB生产GT phase也仍拒绝。固定安装role/path-map发布与worker入口、原始spawn/pidfd/birth owner、UID/mount+PID等namespace/IPC、全部worker写路径、全部backing创建／删除（含两次扫描间短命对象）、逐role/phase GT grant/revoke及失败历史均未闭合。linux_mount_controller回调／命令runner和linux_gt_history时点快照不能替代。 |
| 2：linux_start_clock._require_actual_start_origin／_claim_once、production_runner._load_authenticated_outer_qpc、linux_production_controller.startup_ports | 原既有拒绝保持 | pre-Python/pre-spawn原始clock、原WindowsQPCWallInvocation authenticated transport、原始unit/PID/invocation和连续准入／计费；新pidfd函数传入期限不是时钟producer。 |
| 3：linux_gt_history._libc、mount_helper_inspection、runtime_identity及host execution边界 | 原helper准备检查结论按未变hash继承 | Ubuntu22.04/glibc2.35下旧直接libc exports路线未接通；真实reviewed readonly helper尚未编译／安装。首次dlopen/constructor/import之前完整解释器、stdlib、PE/ELF/native/transitive dependencies、原始held对象及实际加载边界未证明，共享toolchain盘点不能代替专用身份。 |
| 4：native close/exit handoff、linux_post_exit及Windows wall owner | 原异常生命周期结论按未变hash继承；Stage终态第二异常源码已保存 | terminal关闭后的独立签名close/exit join、observer运行期readonly身份与单独secret／通道、原始cgroup清场及最终durable外部QPC墙钟尚无实际证据。wait/reap不能代替整study退出或cgroup清场。 |
| 5：linux_production_controller.require_installation_and_write_boundary、linux_initial_volume.require_host_execution_boundary、capacity_plan/validation | 真实Windows对象／权限核对，原预算规则保留 | 专用carrier/guest/宿主实体对象、原生per-study硬cap（含宿主归属写入）、三层actual baseline/capacity/remaining/cleanup、同invocation创建前8GiB事实；控制层／compiler+ABI／历史与未来准备／observer/helper/launcher/bridge全部CPU/RAM/task/wall/bytes额度。缺值继续UNKNOWN_NOT_ZERO／拒绝。 |

下面更新一次完整A+B最小条件卡；spec和WSL计划引用本卡，原授权申请卡不修改。状态：APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。

| 完整A+B条件项 | 已确认的边界或本轮源码 | 仍缺、不得虚填的绑定／证据 |
|---|---|---|
| 唯一研究／授权范围 | route2-candidate-overlap-v1-001；一次完整A+B及协议早停；不申请A-only，不复用A2-004 ledger/余额。 | owner具体A+B approval ID/seal未签；FROZEN_ADMISSION=None，源码准备不是实验授权。 |
| 科学协议／非候选等价 | 仅300s candidate gap连接改严格时间交叠；保存role分数、模型／阈值0.10/0.25/0.50、600s decoder、180s minimum、matcher与固定五折均保留。 | 同一完整source/config/runtime身份、26D/标签/排序/阈值边界/decoder/matcher的独立完整等价证据；不能只以105参考复现证明。 |
| 输入／参考和角色图 | 固定5 outer×4 inner×4 subinner；105参考全部通过后才105处理；Stage A无GT或match读取。 | exact input/reference/cache/score路径、字段投影、105role来源、readonly授权／实际原生发布／revoke、632100窗口/1127记录及global顺序等当前身份。 |
| 调用额度／Stage B前门 | candidate scorer fit/predict=0；至多105+105重建；25 fit attempts（含失败）、25 predict、65 decoder；20 GT-backed评价＋1 GT-free pooled，pooled GT reads=0。 | 真实唯一ledger、native连续强制、Stage A实际N/M/S/B及2GiB D_A严格上界V2入场投影；仅合成计数不准入。 |
| 最终matched-GT新增项 | 本轮已实现五fold／pooled control/treatment最终集合增减报告，候选覆盖另报；历史control TP=154校验。 | 合法A2-004最终metrics exact hash／matched_pairs源权限，五个field-isolated readonly投影及精确路径/hash/participant scope；同canonical GT含义、同commitment key的native子进程发布、撤销／历史；新增两个冻结hash和schema复审。缺任一拒绝，不新开控制评价或StageA GT。 |
| 信任／隔离和实际部署 | Windows owner可信；WSL2 worker隔离；Ubuntu22.04/glibc2.35＋独立review/frozen helper。 | 实际执行身份（当前非提升）、专用target GUID/file ID/extents与完整安装runner；UID/namespace/IPC／全写路径／backing历史／worker原始spawn-exit-reap均缺。 |
| 创建前可用空间／实体硬边界 | guest承载FS与VHDX所在实际Windows实体卷各≥8GiB；carrier没有第三项8GiB要求，仍独立满足增长＋收尾reserve。 | 同一真实invocation的两项native事实、三层baseline/容量/余额与可强制实体cap；共享WSL全局增量不能代替per-study硬上限。 |
| 时间／内存／CPU／任务方法 | Stage A/总/累计fit=1200/3600/900秒；60秒收尾计入原额度；C=min(4GiB,floor(3×启动可用RAM/5))，AS=C/2，swap=0，CPU=200%，TasksMax=2含controller，通常只剩1计算worker。 | 原始启动RAM、真实cgroup/AS/CPU/task强制、原始deadline来源、外部资源计费及durable结束在原预算内的实际证据。 |
| 容量及数值候选 | D_A=Stage A 2GiB严格容量上界V2，不称实测峰值；20/32/34GiB、guest/host控制64/16MiB、atol=1e-12/rtol=1e-10与离散完全一致仍候选。 | 全部实际资源／数值证据及完整独立复审后由负责人最终绑定；不在源码或卡中偷偷改为批准值。 |
| 准备／控制／外部资源 | helper编译及ABI准备成本独立列项；历史／未来准备分开，控制写入不可计零。 | toolchain helper/as/collect2/headers/start files/include closure/flags/link map、ABI/readonly安装、失败保留／临时/core/log/cache；新match投影／IPC／preallocated异常及traceback／pidfd poll／source写入，以及observer/helper/launcher/bridge的bytes/wall/RAM/task/CPU预算均UNKNOWN_NOT_ZERO。 |
| 实际加载和原始双时钟 | 原始时钟／QPC身份及第一次constructor之前的边界要求保留。 | pre-Python/pre-spawn、认证QPC transport／连续准入、全解释器/stdlib/PE/ELF/native/helper加载身份和readonly原始held对象。hash清单/HMAC/callback/schema不提供权限或原生证据。 |
| terminal／exit／失败验收 | primary与secondary源码保全、一次终态尝试和一次FD/reap消费；NOT_ATTESTED保持。 | 真实故障、OOM-kill/crash quarantine、逐role GT清场、签名close/exit join、原始cgroup空／退出、最终durable外部墙钟验收；不能把exception保存称durability。 |
| 跨OS数值／完整正式复审 | 旧证据仅PARTIAL_MATCH_ONLY；本轮九文件限定静态无剩余范围P1/P2，无正式ID。 | 新版完整nested数值等价、完整source/runtime/role/计量冻结，完整实现／安装／依赖／预算／失败／退出验收的独立正式review IDs；FAIL-001尚未替换。 |
| 实验终点／成功门 | 参考失败或机制无差异等预声明合法早停，或一次完整五折Stage B；COMPLETE与质量门通过分开。 | 尚无合法结果。成功仍pooled F1≥0.66、至少3/5fold≥0.66、每fold long-FP≤0.25且起止MAE各≤900秒，并报告最终match真实新增／丢失。没有候选/decoder/F1/泛化实证可报告。 |

本轮边界执行：只作源码修改、静态只读审阅、AST/hash及只读Windows对象核对；未新增／运行测试、未import项目、未启动WSL、未编译／链接／装载／运行helper或生产组件，未打开GT view，未创建正式image/volume/study/ledger/lock。新九文件不能继承旧源码完整或数值结论，实际安装、运行期、预算和正式复审仍待闭合。全部原dirty/staged/untracked保留，未commit/reset或删除无关工作；原授权卡hash仍88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf，原授权提示hash仍c6e85abcbfb0fd9ae64afe2716bae12b21f0ad391e27b30762528c07298357cd。

最终状态不变：PREPARED_UNREVIEWED；A+B未授权、FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二无合法结果；完整复审FAIL-001 / FAIL，条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。Route3 v1-003合法COMPLETE／四门FAIL保持，不重跑；gap=0由路线二覆盖。负责人提供合法路线二结果前，不启动或自动讨论三个架构方向的验证。

##### 2026-10-07 全权限续行：提升能力实测与实体边界可行性门

负责人现已明确授权“给予全部权限，补齐剩下缺口直到能够合法开启stageA/B并得到路线二的最终结论”。本节记录继续准备、实施、部署复审及条件闭合后合法执行的授权意图；后续不重复申请已有继续工作权限。该授权没有提供缺失的native事实，也没有把此前要求复审后最终绑定的20/32/34GiB、64/16MiB、准备／外部资源预算与数值容差绑定到实际目标。可消费的完整A+B准入尚未形成，FROZEN_ADMISSION=None；NOT_EXPERIMENT_AUTHORIZED表示冻结准入绑定未完成，不表示负责人没有授权继续推进。原授权提示／申请卡不改。

本轮先核验执行后端，避免物理边界未成立时继续堆积局部guard。新实测如下，均为准备观察，非安装、权限或准入receipt：

| 项目 | 实测事实 | 证据边界 |
|---|---|---|
| 主会话 | Windows11家庭版build26300，WSL2.6.3.0/kernel6.6.87.2-1；管理员组deny-only，token非提升，whoami /priv未列SeManageVolumePrivilege。 | 管理员组成员不等于该进程有管理特权；Home／缺VHD cmdlet不能证明WSL原则上不可行。 |
| 实际提升 | 用户已授权后，以Start-Process -Verb RunAs -WindowStyle Hidden启动一次只读PowerShell探针，经同用户ACL named pipe返回；2026-10-07T09:34:08.5649578Z，PID33896，同账号／SID，ElevatedAdmin=true，SeManageVolumePrivilege存在、State=Disabled。 | 未调用特权启用／CreateVirtualDisk／AttachVirtualDisk；报告为只读token观察，非signed native producer。 |
| 提升生命周期／费用 | probe过程内Stopwatch wall=7128ms，含UAC和IPC；09:41:24.7722043Z复核probe PID已不在，主token仍非提升。 | 临时提升没有改变主会话，未建立已安装broker或held执行lease。完整CPU/RAM/task/bytes费用UNKNOWN_NOT_ZERO；7128ms不是实验或项目wall。 |
| 对象／卷 | E:/Route2Dedicated及候选carrier仍不存在；唯一共享Ubuntu22.04 Stopped。C容量/free=322123591680/28063293440B，E=1897546117120/1021840699392B，NTFS；VirtDisk.dll存在、FileVersion10.0.26100.9278。 | 未启动WSL，未取得新的guest正式对象stat；整卷free不是per-study cap或正式same-invocation preimage；DLL文件不是完整held加载身份或provider操作成功证明。 |

Context7及Microsoft原始文档核对：[WSL配置](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)的.wslconfig作用于全部WSL2发行版，不能代per-study硬上限；[WSL挂载](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk)需要管理员，[AttachVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-attachvirtualdisk)要求SE_MANAGE_VOLUME_PRIVILEGE。[固定VHD预分配](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ne-virtdisk-create_virtual_disk_flag)不强制carrier之外的归属写入总额。

独立只读后端可行性复审完成（一个review round，无正式ID）：当前尚不能开启A+B，但证据不足以认定WSL原理上不可行。提升执行方式已取得实际新证据；仍缺包含外层NTFS metadata及C/E registry/eventlog/temp等全部宿主归属写入的native per-study实体硬上限。固定32GiB carrier只限制内部容器；file length、SID quota、共享free变化、HMAC或sampler时点快照均不提供lifetime cap。sampler还不能证明其解释器执行边界。缺New-VHD/Get-VHD/Mount-VHD不排除原生Virtual Disk API通道，但本机provider成功尚UNKNOWN。

预检与执行路由：workflow_path=RESEARCH，capability_tags=deployment,isolation,resource-accounting,data-contracts,ml-evaluation，loaded_profiles=Machine Learning；先INLINE只读盘点和一次UAC probe，再通过collaboration.spawn_agent独立只读复审。Goal=一次合法完整A+B及科学结论；Success metrics=原F1／五折／long-FP／MAE／最终matched-GT门；Constraints=原隔离、全部归属实体硬边界、三层余额、两个8GiB、计时及资源／GT隔离／正式复审；Prior art=原scratch／13-wheel／局部复核；Baseline=83文件工作集、FAIL-001、无合法实验结果；Candidate approaches=受控Windows实例保留原约束，或负责人允许提出计费边界调整再复审；Critical assumptions=所有归属写者能否进入native hard boundary及实际对象／预算／加载身份能否闭合；Risks=误把提升或carrier当全边界、漏计系统副作用；Validation experiments=一次只读UAC成功，无数据／存储创建／Stage；Kill criteria=边界或准备预算未绑定时不创建正式对象、不编译装载生产helper或启动Stage；Recommendation=SPIKE FIRST；Confidence=提升报告明确，整体cap／部署可行性UNKNOWN。下一动作在环境边界处ESCALATE、等待证据；不生成额外JSONL或交接包，状态仅记原三文档。

完整A+B最小条件卡本轮更新差项（上一节全表其他缺项延续）：

| 条件项 | 更新状态 | 仍须真实闭合 |
|---|---|---|
| 负责人续行授权 | 全权限续行及条件闭合后合法执行的授权意图已收到，不再重复申请。 | 完整对象、预算、身份及正式复审后绑定可消费seal；FROZEN_ADMISSION=None。 |
| 原生管理执行方式 | 同账号一次提升只读probe成功，SeManageVolumePrivilege存在但未启用，不再写成无法提升。 | 持续受控部署执行器、实际provider／权限／held运行期及费用；不能复用已退出的PID。 |
| 全归属实体硬边界 | UNKNOWN／未具备，不是仅管理员权限问题。 | 原约束下的真实执行器，或负责人明确选择并复审计费边界调整；已发出环境路线选择，回答未到前不进行依赖该答案的部署。 |

原生产链、所有worker写路径／backing创建删除／GT撤销、原始clock/QPC、pre-constructor readonly解释器／stdlib／PE/ELF/native、signed close/exit join和durable外部墙钟、三层actual baseline/容量/余额、全部历史／未来准备／控制／外部费用、新版完整跨OS数值及正式复审缺项继续存在。提升成功不关闭这些缺口。

本轮源码未修改：83文件、2096023逻辑B、mapping SHA256 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93；55生产Python仅AST，2 C/H和26历史测试只hash。未新增或运行测试、未import项目、未启动WSL、未创建正式image/volume/study/ledger/lock、未读取GT、未编译装载helper或运行生产；原dirty/staged/untracked保留未提交。准备视图仍PREPARED_UNREVIEWED；授权意图已收到但可消费A+B准入未形成、FROZEN_ADMISSION=None；Stage A/B均未合法运行；无合法路线二结果。完整review仍route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL，条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；Route3及后续架构限制不变。


##### 2026-10-07 环境路线已选择：保留全部硬边界的受控 Windows 实例

负责人已答复选择“保持原约束，提供具备完整硬边界的受控 Windows 执行实例（继续 WSL2）”。上一节环境路线待答状态由本节替代：不再考虑调整计费边界；原全部归属写入硬上限、WSL2、两个创建前8GiB事实和carrier独立reserve继续适用。全权限续行已收到，无须重复申请。

实际实例尚未标识或接入。已请求现有实例的名称／远程接入方式与地址；若未创建，则需可用虚拟化平台及实例内存／磁盘上限。这是缺少执行资源信息，非权限重申请；未收到前不猜测provider、端点、付费账户或预算，不启动依赖这些信息的部署。

本机补充只读盘点：Get-Command未找到Get-VM/New-VM、VBoxManage、vmrun/vmware、qemu-system-x86_64或virsh；四个常见安装位置及对应卸载登记没有发现VirtualBox/VMware/QEMU。该发现仅覆盖实际检查的命令／路径／登记，不能写成不存在任何虚拟化软件。CPU报告i7-14650HX、16core/24thread；HypervisorPresent=true下CIM virtualization/SLAT字段为false，不能据此判定BIOS关闭或硬件不支持。尚无可识别的本地受控Windows实例，现有共享Ubuntu不是该实例。

Context7核对[Microsoft WSL原始说明](https://github.com/microsoftdocs/wsl/blob/main/WSL/troubleshooting.md)：Windows VM内部使用WSL2需要外层提供nested virtualization；[Hyper-V Set-VMProcessor](https://learn.microsoft.com/en-us/powershell/module/hyper-v/set-vmprocessor)的ExposeVirtualizationExtensions是一个provider配置方法。本轮没有执行该配置、安装虚拟化软件、修改启动设置、重启、创建VM或访问远程实例；文档可用不证明实际provider支持。

受控Windows名称或独立VM本身不闭合实体边界。实际核对必须覆盖该Windows的系统卷、pagefile、registry/eventlog/temp、WSL与carrier，以及外部launcher/bridge/observer和外层provider的归属写入与资源；任何超出本研究硬边界的写者仍须真实计入并受可强制上限约束。原20/32/34GiB及控制64/16MiB继续是候选，不能直接套用到尚未取得baseline的新实例，也不能默默提高额度。

完整A+B条件卡最新差项：环境路线已经确定，执行实例／nested能力／全写入native cap仍UNKNOWN，实际三层对象和剩余预算未闭合；管理提升已有只读成功事实，不再列为“无法提升”。原14项完整卡及其他实现、runtime、准备与外部费用、数值、完整正式复审缺口全部延续。下一次有实例信息后按原WSL计划本日追加顺序先只读核对，再形成具体部署与预算绑定结果；失败则记录实际后端不可行的证据，不继续用字段或局部guard代替生产实现。

本次环境选择及盘点没有实现新的生产producer，没有新增测试、项目import、guest/helper/production运行或GT读取，没有正式对象创建。83文件工作集及已完成源码修补保持；准备视图PREPARED_UNREVIEWED，FROZEN_ADMISSION=None，Stage A/B均未合法运行，路线二无合法结果，完整复审仍FAIL-001 / FAIL。条件卡仍APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；后者指可消费冻结准入尚未绑定。Route3及后续架构限制不变。


##### 2026-10-07 本机 E＋WSL／10GiB：实际后端预检及独立复审

负责人最新答复：实例尚未创建，可用平台仅本机E盘和WSL，磁盘额度不超过10GiB，给予全部权限，继续至执行agent可开始路线二。资源来源问题已有答复，本轮不再等待或申请远程Windows实例，也不重复询问权限。按保守全归属部署峰值上限处理10GiB=10737418240B（baseline、增长、失败保留、准备／控制与收尾须同口径核算；历史准备另记，不抹为零），不是只给study输出设限。旧20/32/34GiB具体方案与本轮上限不相容，仅保留历史候选记录；不得用其默认值创建对象。10GiB是负责人给出的约束，不是已经形成安装receipt或可消费的完整预算seal。

恢复后先只读核对，未重复任何创建。2026-10-07T17:08:53.5222948Z：仅既有Ubuntu22.04/WSL2，注册GUID {851afdaf-bf1a-4b7e-85b5-47ec86716f54}，VHDX仍在C:/Users/Fancy/AppData/Local/Packages/CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc/LocalState/ext4.vhdx，logical length18464374784B、Attributes=Archive。它不是新的E专用对象，logical length不是per-study物理allocated cap。E卷GUID dbd01263-98ac-43a9-a44c-5dcc3d2e02d1，NTFS容量1897546117120B、free1018579828736B；C容量322123591680B、free28520214528B。E:/Route2Dedicated及carrier均不存在。Disk1报告LargestFreeExtent102835945472B，仅记录原始元数据；未分区、移动或缩减任何现有卷，不能将这项观察升级为专用边界。当前主token仍非提升，原RunAs成功事实保留；旧probe PID33896此刻被QQ进程占用，不是旧probe或可复用held lease，未操作该进程。

一次独立只读复审（local_10gib_admission_feasibility_review，无正式review ID）：当前不能准入，10GiB整体可行性UNKNOWN，无普遍算术否证；源码无改动。两个8GiB是guest承载FS及实际Windows实体卷创建前free门，不是两项研究分配，不得相加成16GiB；carrier没有第三8GiB门。2→4GiB是同一study image的阶段容量，不是2+4；三层父容器与内层对象不得重复计费。每层仍须分别满足 usable_capacity≥baseline+max(free门,future_peak+cleanup) 和 allocated_cap≥baseline+future_peak+cleanup。若guest总格式化容量也≤10GiB，则创建前baseline至多2GiB，实际FS/容器/host overhead会进一步收紧；新minimal Ubuntu22.04＋完整运行期／输入投影／控制／构建峰值尚UNKNOWN。历史shared guest allocated11639623680B不是新minimal部署的下界，旧32/20/34具体方案的静态拒绝也不是10GiB原理不可能。

三个已核假设及判读：
- 使用旧32GiB carrier／20GiB guest：源码capacity_plan.PROPOSED_CEILINGS和validate_proposed_capacity绑定旧方案，明显不满足本轮10GiB；只能否决旧方案，不能伪造更小baseline或说全部新方案都不可行。
- 移现有共享Ubuntu到E或只设置defaultVhdSize：前者不产生新的专用身份／全归属边界，后者只定义发行版VHD容量；不提供全部Windows宿主副作用硬上限。未export/import/move/resize/shutdown任何发行版。
- 建≤10GiB固定carrier或按SID设quota：只限内部容器或该卷某owner的数据。Microsoft [Disk Quota Limits](https://learn.microsoft.com/en-us/windows/win32/fileio/disk-quota-limits)明确按owner SID及streams长度计费，文件相关metadata不计；不能覆盖原合同要求的外层NTFS及不同owner/system的registry/eventlog/temp/pagefile等归属写入。[WSL配置](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)的全局VM设置也不能代per-study边界。没有更改quota、全局WSL配置或创建carrier。

当前实际限因分两类：ENVIRONMENT——本机共享Windows／E＋WSL仍未提供覆盖全部宿主归属写者的native实体硬上限；IMPLEMENTATION——production_runner三个native装配入口及QPC transport、controller完整安装／写边界、initial host执行身份和wall control边界仍明确拒绝。新10GiB容量分类UNKNOWN；不是“只缺管理员权限”，也不认定WSL原理不可行。preflight=RESEARCH/INLINE只读事实＋REVIEW_ONLY一次collaboration独立复审，Recommendation=NO-GO（仅当前本机配置的合法部署／启动，不是10GiB全部方案或科学假设NO-GO）。三项核对没有给出可强制全边界，停止在部署之前，不做盲目存储或helper实验；下一动作是取得满足原合同的真实边界／预算证据，当前可用平台尚未提供该事实。未把环境缺口包装成源码回归。

完整A+B最小条件卡更新差项：资源来源已明确为本机E＋WSL，实例不存在；磁盘上限≤10GiB替代当前部署的旧具体候选，原guest/host control64/16MiB和数值容差仍未绑定。全归属硬cap、三层actual baseline/峰值/remaining/cleanup、准备与外部完整费用仍缺。完整生产phase-worker原始spawn→UID/namespace/cgroup/FD/写路径→受限IPC→逐role/phase授权→计算→pidfd wait/reap/status→撤销及backing创建删除／失败清场仍未接通；已有退出消费不能代替。双时钟、首次constructor前readonly闭包、terminal后签名close/exit join／cgroup清场／durable外部墙钟、新版完整数值等价与完整正式独立review均继续缺。原14项全卡其余内容延续，不能把执行agent派到真实Stage或用A-only绕过。

本轮没有新增生产实现或测试，没有import项目、启动WSL／生产、读取GT、创建正式image/volume/study/ledger/lock、编译／链接／装载／调用helper。83文件／2096023B源码mapping SHA256 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93保持，55生产Python仅AST，2 C/H文本和26历史测试仅hash，原11项staged及全部dirty/untracked保留未提交。原授权卡／提示保持原hash。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B未合法运行、无合法路线二结果保持，完整route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL及APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED不变（负责人续行权限已授，可消费准入尚未形成）。Route3及后续架构限制不变。

本机继续路径的待决合同变更（未采用、非准入）：若负责人明确允许，将10GiB原生硬上限限定于E专用载体及其内完整guest／研究／准备／控制／失败保留和收尾文件；载体外的Windows NTFS/registry/eventlog/temp/pagefile等系统副作用改为单独计量、预算、超额拒绝及独立复审，不再声称其具备per-study native硬上限。这样改变了此前全部宿主归属实体硬边界，也不再提供全部Windows物理增量≤10GiB的native保证；不能由“全部权限”推定同意。原两个8GiB、2→4GiB、时限／C/AS/swap/CPU/tasks、科学协议／GT隔离与完整review要求保留。即使同意，10GiB的实际baseline/peak/cleanup和完整生产链仍须实证闭合，不立即授权Stage。已形成此具体差异供负责人决定；未答复前原合同及所有拒绝维持，不把讨论当新证据或审批。


##### 2026-10-07 三项阻断的证明口径（说明，未执行验收）

负责人询问三点如何证明，本节给出可接受证据；不是解除原边界或回答上一节待决变更，不构成新准入。证明工作来自实际实现、OS机制／对象和独立复审，口头确认、hash清单或HMAC不能代证。

1. 全部宿主归属硬上限：先穷举worker/controller/helper/launcher/bridge/observer/WSL/Windows系统的可达写路径和backing，逐项绑定writer、held对象/卷身份、原生拒绝机制和allocated额度；载体外NTFS metadata/registry/eventlog/temp/pagefile等也须落入真实强制边界或被真实禁止，不能只跟踪观察。机制与可达路径完整性由独立复审核对；准备预算绑定后以受限无GT设施验收核实写满/越界/失败/终态行为，OS在额度边界拒绝，保留原始返回及完整失败历史。轨迹用于查漏，成功的几次运行或时点free/peak不能证明所有路径和生命周期。SID quota不计相关metadata，发行版VHD限额只约束内部；目前没有找到闭合全部宿主副作用的已安装原生机制，不能宣称Windows/WSL原理上不能实现。[微软quota定义](https://learn.microsoft.com/en-us/windows/win32/fileio/disk-quota-limits)。

2. 生产调用链：首先补齐production_runner._load_native_path_map、_load_native_phase_runner、_require_native_nested_producers、_load_authenticated_outer_qpc及相邻实际producer，再提供同一已安装版本的运行证据。固定role/path-map发布、原始spawn/pidfd/birth、UID/namespace/IPC/cgroup/FD/全写路径、逐role/phase grant/revoke与全部backing创建删除、真实wait/reap/status及失败保存必须接通；不能删除raise后返回caller callback。原始Windows QPC tick/frequency与pre-Python/pre-spawn Linux单调clock由原生启动者产生，认证transport绑定同invocation，持续计费至durable结束；完整readonly执行闭包在首次import/dlopen/constructor前已证明。terminal后的独立签名close/exit join和原始cgroup清场也属同链。准备边界/预算绑定后才作无GT实际设施验收；这不会证明科学数值等价，后续还须新版完整nested数值、完整正式独立review及source/runtime冻结。AST/hash与窄复核只能证明对应源码范围，不关闭实装运行门。

3. 10GiB容量：先以精确拟安装清单和保守保留峰值绑定准备预算，再在受真实硬边界约束的新target中实际部署/测量。分别记录guest/carrier/实际Windows层capacity、allocated baseline、增长保守上界、失败保留、cleanup与remaining；Windows held文件的AllocationSize与EndOfFile分开，FS/外层metadata另计，单文件allocation值也不是全部物理成本。[FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info)。总物理baseline＋物理未来峰值增量＋收尾reserve≤10737418240B；固定carrier整体先计入物理baseline，内部guest/study不再向同一物理层重复相加。每层usable_capacity≥baseline+max(该层free门,future_peak+cleanup)，allocated_cap≥baseline+future_peak+cleanup。正式image创建前同invocation guest FS与VHDX实际Windows实体卷各≥8GiB，carrier无第三项门但独立增长/收尾余额成立；若guest formatted usable≤10GiB，创建前guest baseline≤2GiB，其他overhead进一步收紧。先按同一study image最大4GiB上界作准备容量规划，不需偷跑Stage A；合法Stage A后才用真实N/M/S/B执行Stage B投影，D_A仍2GiB严格上界V2，不称实测峰值。

推进顺序：先确定第一项有可部署原生机制并绑定准备预算，再作第三项新target实际测量，同时补第二项源码；随后同一完整安装身份的OS/失败/退出/数值及完整独立正式复审闭合，才冻结可消费准入并开始一次A+B。当前本机全硬边界机制未闭合；第二项还欠实施；第三项无新target实测。此节仅说明，未创建对象、运行测试、编译装载helper、启动生产或读取GT；状态和全部既有工作不变。

##### 2026-10-07 按执行顺序推进：第一项本机机制核查（未闭合）

负责人要求按上一节顺序补完三项。本轮先作受限只读机制盘点，再限定核对第二项既有装配依赖；未把“全部权限”或顺序指令解释为采纳carrier-only合同差异。原全部宿主归属实体硬边界与≤10737418240B保持。查询只读、不创建正式对象/改配置/启动guest或项目，不是生产attestation；完整准备与异步系统成本仍UNKNOWN_NOT_ZERO。

本地2026-10-07／UTC 2026-10-08T03:20:33.3243536Z实际CIM事实：Windows11家庭版中文版10.0.26300、SKU99。Win32_OptionalFeature匹配Hyper-V/Containers/VirtualMachinePlatform/Subsystem-Linux等名称，仅返回VirtualMachinePlatform、Microsoft-Windows-Subsystem-Linux且InstallState=1；不是全部provider不存在的证明。Win32_QuotaSetting查询成功但0行，不能证明quota全无。WSLService Running、vmcompute Stopped/Manual，StartName均LocalSystem，程序分别C:/Program Files/WSL/wslservice.exe和C:/Windows/system32/vmcompute.exe。Win32_SystemDriver报告bindflt/CldFlt/FileInfo/wcifs/WdFilter/Wof Running，不证明本study已配置filter实例、silo/scratch或quota。

hivelist的SOFTWARE/SYSTEM backing为\Device\HarddiskVolume3\Windows\System32\config\SOFTWARE及SYSTEM；CIM日志文件名包括C:/Windows/System32/Winevt/Logs/{System,Application,Windows PowerShell}.evtx。Win32_PageFileUsage为D:/pagefile.sys、AllocatedBaseSize=16384、CurrentUsage=525、PeakUsage=824（CIM原值，不是本study物理增量）；TEMP为E:/Codex/Temp和C:/Windows/Temp。随后Get-Volume：C/D/E均NTFS，GUID分别5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b／7eba0331-891d-4eac-a4cc-9c993f4d50bd／dbd01263-98ac-43a9-a44c-5dcc3d2e02d1，free为28367396864／116296581120／1015734886400B，仅共享时点值。覆盖集合须包含真实D盘pagefile及SYSTEM作者；不能假定只涉及C/E。共享pagefile存量不全部计为study，不据16GiB原值直接否证10GiB；归属增长和physical allocation仍UNKNOWN。

新只读提升盘点使用RunAs/Hidden及current-owner＋SYSTEM限定临时named pipe，最终原始错误“The operation was canceled by the user.”、exec exit_code=2。未收到新提升child inventory，fltmc filters/instances无结果、UNKNOWN；父端finally释放临时IPC。原09:34Z提升成功记录仍保留，但无可复用token/lease。UAC取消与全归属cap能力缺口分开，不概括为只缺管理员；未调整驱动/service/quota/注册表，系统隐含准备写入不计零。

独立reviewer03:25:33Z发现HCS组件，主agent03:28:43.9468099Z逐路径复核：computecore.dll=1017336B、vmcompute.exe=4359664B、hcsdiag.exe=366056B、bindflt.sys=198112B、wcifs.sys=259584B实际存在，进程/OS均64位；已查System32路径无bindlink.dll/SrmSvc.dll，仅为限定路径事实。首次主agentRegistry provider查询错用斜线报路径错误、不作证；03:29:06.3258352Z正确路径重查：无SrmSvc服务键，vmcompute DependOnService为rpcss/wcifs/hvsocketcontrol/condrv。未运行hcsdiag/调用HCS/BindLink/核验exports或创建compute system。无Hyper-V管理cmdlet不能推导“HCS不存在”，DLL存在也不证明可部署受限WSL。

一次限定独立复审：collaboration.followup_task→local_10gib_admission_feasibility_review，只读现有provider/API及本机事实，无写文件/测试/项目/helper/guest/GT执行，无正式review ID；第一项未关闭。Context7先核对文档，再以Microsoft一手定义区分实际能力：

| 核查机制 | 实际能力与第一项缺口 |
|---|---|
| 固定carrier/guest/study | 只能限制其内部增长；载体外C/D/E metadata、SYSTEM service、hive/evtx/temp/pagefile未因此进入同一cap。 |
| NTFS SID quota | 按file owner和data streams长度计费，相关metadata排除；缺跨SYSTEM作者/卷的allocated-byte producer。[定义](https://learn.microsoft.com/en-us/windows/win32/fileio/disk-quota-limits)。 |
| wcifs/bindflt/HCS | 已有组件；layer/COW、路径重定向和VM/container控制不等于全宿主cap。没有原始受限compute-system/scratch绑定，也无外部WSLService/vmcompute及系统作者全部覆盖。[wcifs](https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/anti-virus-optimization-for-windows-containers)、[BindLink](https://learn.microsoft.com/en-us/windows/win32/bindlink/bindlink-overview)、[HCS](https://learn.microsoft.com/en-us/virtualization/api/hcs/overview)。 |
| Job API | IoWriteBytesLimit是通知阈值，超出仍能写；写入bytes不是physical allocation，launcher job不自动包括外部SYSTEM服务。IO-rate是IOPS/bytes-per-second，公开结构文档注明Windows10 1607及更新不支持。[通知](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_notification_limit_information_2)、[rate](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/ns-jobapi2-jobobject_io_rate_control_information)。 |
| FSRM | Server目录hard quota可拒绝超限，目录usage包含metadata，不能套用NTFS SID quota的排除项。本Home限定服务/DLL检查缺失，未取得受支持provider；即使有目录quota，仍须证明全部跨卷系统归属作者进入覆盖集合。[平台](https://learn.microsoft.com/en-us/windows-server/storage/fsrm/fsrm-overview)、[usage](https://learn.microsoft.com/en-us/windows/win32/api/fsrmquota/nf-fsrmquota-ifsrmquota-get_quotaused)。 |

仍缺actual producer：从首次准备/启动至最终清理，真实绑定每个归属系统/服务/launcher/observer作者及承载对象，在首次分配前强制跨C/D/E≤10GiB并保存完整超限、失败及清场历史。过滤器实例、异步归属、全成本仍UNKNOWN；限定核查不是全系统provider穷举，不把未知当不存在，不普遍否证Windows/WSL或10GiB。当前严格合同下合法部署仍NO-GO（ENVIRONMENT＋IMPLEMENTATION，容量UNKNOWN）。

第二项仅定位已有源码和部署依赖：production_runner原三个native装配入口及QPC仍拒绝；phase计算及pidfd退出消费可继承，但LinuxRoleMountController允许平台/root/命令/namespace/readiness/source-resolver等回调，不能由默认参数提供生产权限。linux_gt_history仍缺原始worker spawn/UID/namespace/IPC/全写路径、全部backing创建删除及逐role/phase GT授权撤销；快照不能代全历史。首次加载readonly、双时钟、close/exit及费用也未闭合。这些是既有缺口，不是新源码回归。本轮没有新增生产实现或改源码；第一项未闭合，未创建target或执行第二、三项部署验收。

更新一次完整A+B最小条件卡缺项；原授权申请卡不改。状态 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**：

| 完整A+B条件项 | 本轮证据与仍缺闭合 |
|---|---|
| 1. 唯一研究／授权 | 一次route2-candidate-overlap-v1-001完整A+B及预声明早停续行意图已获授权；不是缺继续权限。可消费approval/seal与FROZEN_ADMISSION未绑定，不启A-only。 |
| 2. 完整独立复审 | route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL；本次provider限定核查未关闭第一项，无正式ID，不代完整复审。 |
| 3. source/runtime冻结 | 83文件hash仅源码追踪；同一完整可安装runner、target runtime/native/observer/launcher/bridge闭包及正式freeze仍缺。 |
| 4. 输入／角色／GT／历史对照 | 105 role、20 GT-backed＋第21次GT-free pooled保留。实际readonly注册/输入、合法五份A2-004最终matched-GT投影及逐phase释放撤销未部署；不预读GT。 |
| 5. 全宿主硬边界／专用对象 | 来源本机E＋WSL，HCS组件确认；专用对象未创建。C/D/E及SYSTEM作者/卷外NTFS效果缺per-study native allocated-byte cap，第一项未关闭。 |
| 6. 三层≤10GiB容量 | 新target guest/carrier/actual Windows的baseline/capacity/remaining/保留峰值/cleanup均缺；共享free非准入，旧20/32/34GiB配方禁用，新10GiB可行性UNKNOWN。 |
| 7. 8GiB门／stage disk | image前guest FS与VHDX实际Windows实体卷各≥8GiB；carrier无第三门但需增长/收尾reserve。D_A=2GiB严格上界V2，同image最大4GiB、非2+4；新target同invocation事实缺。 |
| 8. 完整生产worker链 | path-map/phase-worker/nested入口拒绝；原始spawn/pidfd/birth、UID/namespace/cgroup/FD/IPC/写路径、全创建删除history、grant/revoke与失败清场未接通。 |
| 9. 时间与强制资源 | 1200/3600/900秒含60秒收尾；C=min(4GiB,floor(3×启动可用RAM/5))、AS=C/2、swap0、CPU200%、TasksMax2含controller保留；startup RAM/真实强制及original deadline证据缺。 |
| 10. 双时钟／连续准入 | pre-Python/pre-spawn Linux clock、原始Windows QPC tick/frequency、认证transport及同invocation至durable结束计费未安装。 |
| 11. readonly加载/helper | 首次import/dlopen/constructor前完整解释器/stdlib/PE/ELF/native边界缺；Ubuntu22.04/glibc2.35及独立review/frozen helper要求保留，C/H未编译/链接/装载/调用。 |
| 12. terminal／exit／实际失败 | primary/secondary保存及退出消费源码按未变hash继承；真实故障/OOM/crash、GT清场、签名close/exit join、原始cgroup清场及final durable外部墙钟缺。 |
| 13. 全准备／控制／外部预算 | 历史/未来安装、compiler/ABI、startup control、observer/helper/launcher/bridge与系统隐含成本UNKNOWN_NOT_ZERO；64/16MiB及全部预算未最终绑定。 |
| 14. 完整数值／科学结论 | 旧PARTIAL_MATCH_ONLY不覆盖新版nested链；atol1e-12/rtol1e-10及离散完全一致待review/绑定。无合法A/B或Route2结果，质量门及最终control/treatment matched-GT真实增减待合法结果。 |

原carrier-only合同差异未采用；顺序指令不等于放弃卷外Windows per-study native硬cap或全部Windows物理增量≤10GiB的native保证。当前本机E＋WSL原合同的部署前止点保持；不以字段/HMAC/hash/schema/callback虚填机制或签发执行agent可用准入。改变范围须明确合同决定，再绑定预算与完整复审，不自动放行。

本轮只原三文档追加和系统/源码只读核对，无新增/运行测试、项目import、WSL/production/Stage/GT、正式image/volume/study/ledger/lock或helper编译/链接/装载/调用。83文件／2096023B mapping SHA256 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93未变（不是freeze），原限定源码结论继承、无新正式源码review ID。原dirty/staged/untracked、11项staged及授权提示/卡保留，未提交/reset/delete。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B均未合法运行、无Route2结果、完整FAIL-001保持。Route3 v1-003合法COMPLETE／四门FAIL、不重跑及合法Route2结果前不启动后续架构方向限制保持。


##### 2026-10-08 负责人采用本机三项推进建议：资源调查与原生 child 源码实施入口

负责人最新明确接受三项建议并开始执行：10GiB仅为估计资源用量，不再是硬上限；主要任务资源在E，其他盘只能少数；任务总RAM上限16GiB、VRAM上限8GiB。后续明确选定非E盘新增预算合计512MiB，含停止与清理空间。此前“卷外全部Windows per-study native cap、全部宿主物理增量≤10GiB”的当前NO-GO只保留为旧合同历史，不再作为未答复或现行硬条件。

现行边界为：E专用carrier内部完整guest、研究、准备、控制、失败保留和收尾文件仍受真正原生实体边界约束；载体外Windows NTFS、registry、eventlog、temp、pagefile及SYSTEM/service作者副作用单独计量、预算、超额拒绝和独立复审，不宣称它们已有per-study原生硬限。这项合同调整不填充native producer或安装事实，不授予可消费的冻结实验准入。既定两项8GiB门、同study image 2→4GiB、1200/3600/900秒含60秒、C≤4GiB与AS=C/2/swap0/CPU200%/TasksMax2、GT和科学协议保持；16GiB是任务总上限，不是study额度扩大。

只读资源调查：640个prepared-input文件共2644303938B；按原role-input registry元数据去重，1127个cache NPZ共240384603B、105个score NPZ共172155149B，均位于E且文件存在。本轮只stat文件元数据、读取登记元数据，没有打开GT payload或cache/score数组。加历史科学venv348519927B、13-wheel 79270066B和原83文件源码追踪2096023B，已知非study内容子集3486729706B（3.247270GiB）；加同一study最大4GiB为7.247270GiB，均非安装baseline或实测峰值。旧共享Ubuntu的C盘18.464GB VHDX不充新目标最小OS基线。

2026-10-08T07:48:29Z只读Windows样本：E free1014769180672B；物理RAM16890322944B、Windows free3056592KiB（约2.915GiB），不替代首次Linux MemAvailable。nvidia-smi原生只读query得到NVIDIA RTX5060 Laptop GPU总8151MiB、used2587MiB、free5313MiB；共享used不全归本study、总量不等于可用额度。当前CPU HGB/phase源码新增VRAM先估计0，实际禁用dxg及完整运行证据仍缺。C:/Users/Fancy/.wslconfig不存在，未创建；cgroup swap0不能推出WSL VM swap/pagefile费用为0。

官方Ubuntu WSL jammy目录的rootfs HEAD为341130963B压缩，包manifest17419B/562包，列明glibc2.35、Python3.10.12、systemd249。限定只读archive流统计在45秒research deadline停止，仅见8829条、178990762B普通文件逻辑内容、63324160B压缩流；未提取或安装，不能当完整OS baseline。来源：[Ubuntu WSL jammy](https://cloud-images.ubuntu.com/wsl/jammy/current/)、[包清单](https://cloud-images.ubuntu.com/wsl/jammy/current/ubuntu-jammy-wsl-amd64-wsl.manifest)。

具体待最终绑定的准备提案：guest nominal20GiB、usable≥19、baseline ceiling8、future6（含同image最大4）、cleanup1；carrier nominal24GiB、usable≥23、实际baseline≤22（必须含inner VHDX完整AllocationSize/header及Windows readonly/control/FS成本）、future128MiB、cleanup128MiB；E新增预留30GiB（carrier nominal24加外部6，header/外NTFS/归档临时/失败/Windows E副作用均计入），规划约28–30GiB，非已证区间。内部guest/study不向已计整carrier的同一E物理层再相加。非E候选active384MiB+stop/cleanup128MiB合计512MiB；实际完整计量、采样延迟/异步写入覆盖及提前stop producer仍缺，不宣称保证不超额。

一次非study准备候选RAM4GiB/tasks4/CPU200%/wall1800秒；显式observer/helper/launcher/bridge合计候选RAM512MiB/tasks4/CPU100%/wall6000秒，后者覆盖prep1800+study3600+外部观察600，不扩展原study时限。8.5GiB仅已列process-envelope的保守和；WSL VM/kernel/service/IPC/cache/Windows等开销仍UNKNOWN_NOT_ZERO，不能说任务总RAM已闭合。科学study原C方法和全部时限不变。

独立资源/源码设计核查在更正inner VHDX实际完整分配、observer wall6000及RAM scope后，未发现上述限定条件算术的硬矛盾；仅有条件准备预算，无正式review ID或准入PASS。20/24/30、控制64/16MiB、准备/外部预算及数值容差仍待实际事实、独立复审和负责人最终绑定；现有capacity_*旧32/34与全host scope不可直接解析或批准这套新提案。

实际源码工作已选择固定原生child启动生命周期：新C/H clone3原始pidfd与native sandbox/setup→固定exec child、有界IPC→原始wait/reap/失败cleanup；GT child全部FS只读，父原所有者独占backing创建删除。文件范围为linux_child_launch.py、phase_worker_entry.py、native/route2_phase_spawn.c/.h及必要linux_child_exit.py衔接。此节为实施入口，未宣称实现/复审已经完成；固定role/path-map与broker的真实发布/撤销、原始时钟/QPC transport、首次constructor前完整readonly闭包和terminal后外部验收仍需分别闭合。没有创建正式image/volume/study/ledger/lock，没有WSL/Stage/GT执行或helper编译/链接/装载/调用。

准备视图仍PREPARED_UNREVIEWED，FROZEN_ADMISSION=None，Stage A/B均未合法运行、无路线二合法结果；完整route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL。完整A+B续行意图已获授权，不重复请求“全部权限”；可消费的具体冻结准入缺项须闭合。原授权提示/申请卡不改，Route3 v1-003合法COMPLETE／四门FAIL不重跑，合法Route2结果前不自动启动后续架构方向。


##### 2026-10-08 负责人最终绑定准备容量与全局WSL配置

负责人已明确采用30GiB无GT准备预留：E专用carrier nominal24GiB，含guest nominal20GiB，载体外预留6GiB；guest actual baseline须≤8GiB，否则拒绝进入study。非E新增预算合计512MiB（包含提前停止及清理空间）保持。10GiB仍仅历史估计，任务总RAM≤16GiB、VRAM≤8GiB及原study资源/科学约束不变。准备容量的负责人绑定已闭合，不重复申请；actual baseline、完整费用及资源生产者尚未闭合，不能由绑定当实际安装证据。

负责人同时明确采用列明的全局配置。按CreateNew、拒绝覆盖，唯一新建C:/Users/Fancy/.wslconfig：`[wsl2]`、`memory=8GB`、`swap=0`、`processors=2`、`guiApplications=false`，CRLF/UTF-8无BOM，共65B，SHA256 a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5。随后held-file原生FileStandardInfo只读得到AllocationSize=72、EndOfFile=65、NumberOfLinks=1、非目录/非删除pending；72不是C盘全部metadata/journal/系统副作用物理成本，仍另计非E预算。配置影响本机全部WSL2发行版；本轮未启动VM或shutdown/移动/删除发行版，未把文件存在当已应用的VM强制证据。

原生child新增源组件已完成初次独立规范复审；确认WSL6.6 ambient UID65534与NPROC零限的P2并已去除该冗余零限，保留原cgroup两task与seccomp禁止创建task。修订后限定静态规范范围无剩余P1/P2，无正式review ID/PASS；独立质量复审进行中。实际无GTWindows prep部署producer仍未安装，既有preimport launcher不是fresh distro导入器，正式image creator也不能代准备部署。准备对象/完整计量及提前停止链、root/GT/native装配仍须真实实现与复审，当前未创建对象或编译/装载helper，Stage不放行。


##### 2026-10-08 生产源组件收尾：原生 child、Windows Job 与固定 mount helper（限定静态复审）

沿用本节已有执行授权、原设计和整合修订，不新建交接包。负责人已最终绑定 E 新增30GiB无GT准备预留：carrier nominal24GiB，包含guest nominal20GiB，载体外6GiB；actual guest baseline≤8GiB，否则拒绝进入study。非E新增合计512MiB包含停止和清理，任务总RAM≤16GiB、VRAM≤8GiB。10GiB仅历史估计，旧全宿主归属native≤10GiB要求已由负责人接受的载体内硬边界＋载体外独立计量/预算/提前停止方法替代，不重新引入。准备容量和列明全局WSL配置无需再次询问；实际生产事实、其他候选费用额度、完整复审及可消费冻结准入尚未闭合。

实际源码实施与限定独立复审如下。每项均先独立规范、后独立质量，针对下表最终hash重新确认；无剩余限定范围P1/P2，无正式review ID，不是实验准入PASS或完整实现通过：

| 生产源组件 | 实际实现、修复与复审结论 | 没有证明的事实 |
|---|---|---|
| Linux phase-child原始生命周期 | 新C/H以clone3同时取得原始pidfd，C-only child setup→固定新解释器exec；私有mount/IPC/net/PID/UTS/cgroup namespaces、只读root、UID/GID65534、cap/groups drop、seccomp和FD白名单；私有READY/FAILED/final permit、有界JSON/GT commitment结果、原始wait/status/reap和逐FD一次关闭，保留primary/secondary。移除会受WSL6.6共享UID65534影响的冗余NPROC=0，保留cgroup两task/seccomp禁止新task；关闭标签在消费FD前预置，避免报告路径遗失未消费FD。独立规范及质量修订后均无剩余范围P1/P2。 | C/H未编译/链接/装载/调用，未证明实际ABI/runtime/seccomp兼容或child出生。固定phase-only root的创建/发布/删除、cgroup出生边界、GT broker装配和全部实际费用仍缺；本单元不是生产PhaseRunner或完整清场receipt。 |
| Windows无GT准备Job生命周期 | 新windows_preparation_job.py实际声明并调用Job配置/读回、PROC_THREAD_ATTRIBUTE_JOB_LIST原子出生关联、suspended CreateProcessW、原始process/thread handle/ID/成员身份/ResumeThread、accounting/wait/status、原handle终止和独立一次关闭。修正NULL stdio仍设置STARTF_USESTDHANDLES的合同问题；错误聚合/报告失败也使状态FAILED，原primary和secondary及不完整捕获原因保留。独立规范及质量最终无剩余范围P1/P2。 | 4GiB是Job COMMIT、4是active PROCESSES，不是physical RAM/RSS或四个task/线程；两affinity bit/CPU rate也不是WSL VM whole-task证明。60/70秒只覆盖该private生命周期，不是原始pre-Python epoch或准备1800/study3600。无readonly prep-worker.exe/安装owner，固定顶层准备调用仍拒绝；未创建Job或进程，杀wsl.exe不代表WSL VM/服务退出，fatal HANDLE转换/owner death quarantine仍UNKNOWN。 |
| Ubuntu22.04/glibc2.35固定mount helper适配器 | 只改linux_gt_history.py的header/固定constants/三个private owner cache字段/40-byte ABI结构/_libc及恰好四个内部调用。从原始guard/broker/startup/controller取得owner；原complete installation/write-boundary gate在helper CDLL/describe前，随后完整canonical runtime manifest的唯一固定lib/route2/mount_helper.so成员、有界readonly bytes/hash、reject-only ELF inventory；实际describe_v1核十个uint32的40-byte ABI，绑定四个namespaced exports，errno立即保存。首次加载仅startup seq2、无worker/grant；库成功加载后原owner持有，不重试dlopen；失败revoke只用原cached库，不需要healthy journal，不新加载。独立规范和质量最终均无剩余范围P1/P2。 | installation gate仍无条件拒绝，没有实际helper安装或native调用。完整解释器/stdlib/project/PE/ELF/native/transitive readonly闭包须在任何project/ctypes import/constructor之前由实际bootstrap证明；本loader在自身CDLL之前的门不能补造此前证明。ELF/hash/ABI只是后置拒绝检查。 |

上一WSL计划“加载额外最多10秒”表述由此更正：10秒是合作式读取/调用前后检查窗口，计入原Stage A/总额度；不能中断同步dlopen、constructor或describe，不能声称独立原生10秒硬上限。原始已武装kernel绝对deadline、60秒原额度内stop margin及实际安装/外部quarantine仍必需。没有新增timer、放宽1200/3600/900或把检查窗口当clock origin。

最终源码身份（仅工作集追踪，非完整source/runtime冻结）：

| src/eating_event/route2_candidate_overlap/ 下文件 | 逻辑B／行 | SHA256 |
|---|---:|---|
| linux_child_launch.py | 19028／327 | e221c4b2c55899c68ac9eda5607a5770878c3d6f8560058d79e5aeb33905cb91 |
| phase_worker_entry.py | 18515／333 | 84d4628985fd8c32914a61de611149f080255ba3e842494f38508defdd148ff8 |
| native/route2_phase_spawn.c | 22305／385 | e8179f30ea45107164248e04881b2e43cad26f5b93eb3f5b02f3580f7af7786b |
| native/route2_phase_spawn.h | 2420／55 | cbb647b8537873c35b77e8fe52c639cb6fffa73406fc3f5e98ace08f113aa9ad |
| linux_child_exit.py | 10281／205 | fdfc029fa3a253d4a99e81979c8538ce9bd443f205262cbf368462324f9e2c0c |
| windows_preparation_job.py | 30076／600 | 82f76b8caef0da786f5354a8f70767f74be1bb130e6ab040a8d600860f95da3d |
| linux_gt_history.py | 131356／2369 | 830ec1164eb7b43b4a9edabc6de1c6fc05c88760d4958e4d703466ffbcc4c011 |

限定独立审阅者为native_phase_launch_quality_review（对应先行独立规范）、windows_preparation_job_spec_review／windows_preparation_job_quality_review、mount_helper_adapter_spec_review／mount_helper_adapter_quality_review；后两组规范/质量均fresh且只读，未把实现者自查当独立结论。首次Win规范提出的三项P2及native child修订均已返工并重新审阅；本节只记录最终限定结论，不签正式ID。旧Windows wall/lease/trust、ELF准备检查/费用分类/confirmed methods、native_failure_capture/linux_quiescence、phase._journal和GT原failure保存结论按未变实际hash及源码范围继承。GT模块新增loader/calls单独重新审阅；其余原AST在剔除且仅剔除批准的header/constants/cache/ABI/loader/四处调用后与实施前完全一致。科学Stage A/B、最终matched-GT与execution.finalize双异常修补文件未再改变。

最终只作AST/hash/文本核对：88文件、2202343逻辑B、58个生产Python AST成功、4个native源文本、26个历史测试仅hash；工作集mapping SHA256 740afc4263efa095f5e510ba799fe1b608b3b7e9c90f4fa663a584d6a668ff3a。历史测试mapping仍469312e5c5ef487681d4bf5ec25c0cc4cf6957ad891912ccc638b34c9cca1b70。去除五个新文件并还原本轮两个既有文件原hash后，精确重构此前83文件mapping 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93；所有其他原工作集文件保留。git ls-files --stage原始95行bytes SHA256仍2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e，既有index未改。三原文档以追加方式保留全部既有prefix；原授权卡仍88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf，原授权提示仍c6e85abcbfb0fd9ae64afe2716bae12b21f0ad391e27b30762528c07298357cd。

真实对象核对：2026-10-08T15:47:55.7110687Z主账号LAPTOP-339GMS1N\Fancy，当前token ElevatedAdmin=false；旧提升只读probe成功事实保留，不当可复用token。E:/Route2Dedicated仍不存在；wsl --list --verbose只列既有Ubuntu-22.04 Stopped/Version2，没有新专用target或VM启动。C:/Users/Fancy/.wslconfig hash仍a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5，唯一实际新增host配置仍65B/已授权内容；原held-file AllocationSize72不代表全部Windows副作用或配置已经应用。15:19:56.8174356Z C/D/E共享free分别27626876928／116277129216／1012088463360B，Windows free RAM3153256KiB，仅整卷/宿主时点观察。Win32_PageFileSetting查询成功0行，不能推定pagefile固定无增长；历史D pagefile、C注册表/日志及服务写者继续纳入非E归属范围。共享free净变化不能作本任务allocation、增量或512MiB验收。

本轮更新一次完整A+B最小条件卡，替代此前卡中已被负责人新决定替代的资源/授权待答项。APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；负责人续行及条件闭合后执行意图已授权，后者只说明可消费冻结准入尚未形成，不是再次索取泛化权限：

| 完整A+B条件项 | 已确认／实际完成 | 仍缺真实生产者、事实和冻结绑定 |
|---|---|---|
| 1 唯一研究／授权范围 | route2-candidate-overlap-v1-001；一次完整A+B或预声明早停，不A-only、不复用旧ledger/余额；负责人全权限续行意图已给。 | 同一真实安装/资源/科学身份、完整正式review、最终预算与具体可消费approval/seal；FROZEN_ADMISSION=None。 |
| 2 科学协议／非候选等价 | 仅保存role scores的300s gap连接改严格时间交叠；模型、26D、阈值0.10/0.25/0.50、600s decoder、180s minimum、matcher及五折方法不变。 | 当前完整nested版本的标签/特征/排序/阈值边界/decoder/matcher数值与离散等价；105参考复现不单独证明非候选部分。 |
| 3 输入／参考／角色图／path-map | 原105 role、5 outer×4 inner×4 subinner及先105control再105treatment保留；Stage A无GT/match。已完成child原始生命周期源码。 | production_runner._load_native_path_map/_load_native_phase_runner/_require_native_nested_producers仍拒绝；真实固定non-GT metadata/role发布与撤销、105路径/投影/来源/hash、632100窗口/1127记录/global顺序身份、全部backing创建/删除与失败历史。 |
| 4 调用额度／Stage B前门 | scorer fit/predict=0；105+105重建；25 fit attempts含失败、25 predict、65 decoder、20 GT-backed评价＋21st GT-free代数归并，pooled GT reads=0；D_A为2GiB严格上界V2。 | 唯一实际ledger与持续原生强制；合法Stage A实得N/M/S/B、完整入场投影和同study2→4GiB；准备/scratch/合成计数不替代。 |
| 5 最终matched-GT对照 | 先前P2修补按未变hash继承：每fold及pooled实际control/treatment最终集合新增/丢失，candidate coverage另报；合法历史control TP=154校验。 | A2-004合法最终metrics/matched_pairs exact hash与源权限、五个field-isolated readonly投影及当前路径/hash/scope；同canonical GT与commitment key，真实outer-only子进程发布/撤销与历史；未创建/打开这些GT关联投影，不追加控制评价。 |
| 6 信任／隔离／实际部署 | Windows owner可信；WSL2隔离、Ubuntu22.04/glibc2.35＋独立review/frozen helper；当前有Linux child与Windows Job实际API源组件。 | 完整可安装runner、专用target注册GUID/held file IDs/extents/native控制；readonly prep-worker/phase root、UID/namespace/IPC/cgroup原始出生与exit/reap/status和全部写路径运行事实；非提升不是完整缺口。 |
| 7 两项8GiB／实体硬边界 | 正式image创建前guest承载FS与guest VHDX所在实际Windows实体卷分别≥8GiB；carrier无第三8GiB但独立增长/收尾reserve。E carrier内native硬边界、载体外独立预算方法已采纳。 | 原生部署creator/format/import/注册、同invocation两项现场free、实际三层usable/AllocationSize baseline与全部费用/余额/cleanup，carrier实际可强制边界；共享WSL增量或wholevolume free不证明。 |
| 8 时限／RAM／CPU／task／VRAM | 1200/3600/900秒含60秒；C=min(4GiB,floor(3×首次Linux可用RAM/5))、AS=C/2、swap0、CPU200%、TasksMax2含controller；任务总RAM16GiB/VRAM8GiB；授权.wslconfig内容已创建。 | 实际应用VM8GB/swap0/2processor、原始Linux MemAvailable/cgroup/AS/task/CPU/dxg拒绝及全任务峰值；Job4GiB commit/4process不是task或wholeRAM。原始hard clocks及外部费用/停止/结束事实。 |
| 9 准备容量／其他候选预算／数值 | E30GiB无GT准备预留、24GiB carrier含20GiB guest、外部E6GiB及baseline≤8GiB前门，nonE512MiB含停止清理已OWNER_BOUND；10GiB非硬cap。 | 28–30GiB仅保守规划而非实测peak；actual guest/carrier/E baseline、header/full allocation、未来峰值及reserve。64/16MiB控制、准备4GiB/4tasks/200%/1800s、外部512MiB/4tasks/100%/6000s及atol1e-12/rtol1e-10/离散完全一致仍待真实证据、复审与负责人最终绑定；旧20/32/34全host-scope源码不能直接消费新scope。 |
| 10 全部准备／控制／外部费用与非E停止 | helper编译/ABI另计，历史与未来准备分开，启动控制写入不可零；E是主要增长位置，非E全task512MiB。 | 实际部署producer；C/D/System/registry/eventlog/temp/pagefile/WSL services/VM及所有作者/在途增长/采样遗漏/stop/cleanup完整计量和提前停止上界；compiler/linker/headers/include/start files/objects/lib/debug/link map、安装/失败保留/core/cache/log/source/IPC/异常slots/traceback/observer/helper/launcher/bridge的bytes/wall/RAM/task/CPU费用。缺值UNKNOWN_NOT_ZERO。 |
| 11 实际加载边界／原始双时钟 | 固定40-byte mount helper source adapter已接线；原始owner/canonical pinned成员/ABI与errno检查；合作式10s诚实说明。 | native helper C/H均未编译/链接/安装/加载/实际调用；首次任何constructor/import/dlopen前完整readonly解释器/stdlib/PE/ELF/native/transitive actual held身份；pre-Python/pre-spawn原始clock、原WindowsQpcWallInvocation认证transport、原unit/PID/invocation/准入连续性。hash/HMAC/caller callback/schema不造事实。 |
| 12 terminal／exit／故障验收 | 原primary/secondary、一次消费/关闭源修补继承；新child/Job/helper失败保存限定静态闭合。 | 实际失败/超限/OOM/crash quarantine与完整durable历史、逐role/phase GT grant/revoke、签名terminal关闭后close/exit join、原始cgroup清场、外部WSL VM/服务确实退出和最终durable外部QPC墙钟。异常保存或pidfd wait不是完整study退出验收。 |
| 13 跨OS／完整正式review与最终冻结 | 当前三个组件限定静态规范＋质量无剩余范围P1/P2；AST/hash核对通过；原完整FAIL-001仍有效，旧数值证据仅PARTIAL_MATCH_ONLY。 | 新版完整nested科学等价、可安装全调用链、独立installation/OS/native/readonly/费用/故障/exit/full implementation正式review IDs；source/runtime/输入/准备视图/path-map/role/launcher/worker/controller/全部协议及预算最终完整冻结。当前88文件map不提供冻结。 |
| 14 实验终点／成功门 | 合法预声明早停，或一次完整五折Stage B；COMPLETE与质量门通过分开。pooled F1≥0.66、至少3/5fold≥0.66、每fold long-FP≤0.25、起止MAE各≤900秒及最终match增减仍固定。 | Stage A/B未合法运行，105参考是否复现、candidate差异/decoder保留/F1/泛化/最终MAE集合增减均无合法科学结果，不能据源码或局部review推断。 |

下一生产装配的真实调用顺序依赖已定位，属于既有缺口：production_runner构造path-map/PhaseRunner以及StageB.preflight在guard.start之前；原GT broker却必须在guard.start、phase/terminal注册和原始QPC双记录握手之后的seq2安装。不能把GT installer直接放进早期_loader，不能用回调型LinuxRoleMountController默认参数当新authority。实际固定装配须先证明readonly non-GT preflight metadata的原始发布边界，再于原始startup握手后安装唯一broker/role publisher；StageB当前production分支仍拒绝legacy ledger release，后续真实runner必须只由该broker发一次release，join scoped phase-only root、原始spawn/exit/reap后再实际revoke，不双写release/second writer。phase-only root须只含同一已释放GT及outer-only历史match投影，不暴露其他GT/宿主write路径，并提供父唯一作者完整创建/删除历史。这些以及实际prep部署对象、512MiB计量/停止链、原始clock/readonly/terminal生产者仍缺，不能包装为仅需提升或把局部源码闭合写成完整runner。

本轮未新增/运行测试、未project import、未WSL启动、未helper编译/链接/装载/调用或生产执行、未GT读取、未创建正式image/volume/study/ledger/lock；唯一额外host文件为已明确授权.wslconfig。全部既有dirty/staged/untracked及授权卡/提示保留，未提交/reset/delete。四项状态分别是：准备视图PREPARED_UNREVIEWED；可消费A+B准入未形成/FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二没有合法结果。完整route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL；scratch2→4GiB、13-wheel、历史合成和本节窄复审均非准入PASS。Route3 v1-003合法COMPLETE／四门FAIL不重跑，gap=0由路线二覆盖；合法Route2结果前不自动启动三个架构验证。


### 2026-10-09 整合后续：固定phase publisher、metadata v2与本轮P2收尾

本节接续原整合修订，依负责人“继续工作”及“先修复问题”推进；讨论、决定和状态仍只在原三文档追加，授权提示／申请卡不改，不新建交接包。Windows owner可信、WSL2/Ubuntu22.04/glibc2.35、E30GiB准备预留及nonE512MiB超额前停止、总RAM16GiB/VRAM8GiB等既有绑定保持，不重复申请。负责人续行意图已授；可消费完整A+B冻结准入仍未形成。

#### 实际源码实施及限定复审

固定phase-input publisher已在linux_phase_publication.py实施，必要连接linux_gt_history.py、linux_enforcement.py和linux_quiescence.py。它只依原唯一已安装GT broker、原guard/startup/controller/PID/thread、当前实际grant/canonical scope/durable release及原armed绝对stop/cleanup；仅发布 /run/route2-phase-source/inputs/gt-view.jsonl 与outer-only control-final-matches.jsonl。复用原owner已持有固定native helper的真实open_tree(CLONE/CLOEXEC/AT_EMPTY_PATH)、mount_setattr(readonly/nosuid/nodev/noexec/private)、move_mount；先保存原FD/原生mount ID，再记录history。历史match来源从原已安装metadata的五个登记推导，无resolver。关闭前实际child/reference fence，正常umount一次，核目标及原issued ID缺席，完成后才允许broker.revoke；失败保存primary/secondary并poison原owner，cleanup只用原cached库。未创建、复制、链接或删除任何backing。原完整installation门及GT broker安装仍拒绝，所以没有publisher实际安装/调用证据。

该publisher独立SPEC曾发现并已修复3个P2：重复/无active close也须保存失败并poison；目标编码必须在消费umount尝试前固定；native负返回失败记录的操作标签不能在立即保存errno前动态拼接。最终限定SPEC→QUALITY均无剩余范围P1/P2，无正式review ID。_tree仅核固定input substrate/空immutable targets；完整runtime/source/phase树所有创建删除及加载闭包不由它证明。

固定production_metadata v2实施了真实受保护文件读取路径，解决真实role registry 16,457,999B和role/reference map下界9,131,857B无法装入旧8MiB文件/16MiB inline envelope的问题。独立schema/domain，≤1MiB canonical envelope中的四个精确basename token仅派生 /etc/route2/{STUDY_ID}-metadata/ 下固定role/reference/control-final/path-map文件；HMAC及全部原bootstrap bindings先于外部读取，实际held nofollow FD/KCMP/native frame/private visible readonly mount核查，raw frozen hash先于JSON。v2 role/map各16MiB、ref/control各1MiB；64KiB扫描块、scanner/semantic 1,048,576/524,288、depth32、有界数值/duplicate/canonical拒绝，单文件一次json.loads；已验证map只保留data/projections与原raw对象身份，后续校验不重parse，不提供mount authority。原v1 schema/domain/parser/caps/dataclass/API保留；当前directory path-map v2尚未实施，不能把现存exact-map v1当目录版本。

本unit四个具体P2均已修复并完成fresh独立SPEC→QUALITY，无剩余限定P1/P2：
1. protected REGULAR文件经不同readonly bind paths别名到同一inode：读取payload前重核原held FD/anchor frames和KCMP，再拒绝相同(dev,ino)；不比较DIR祖先，独立mount仍合法。此项也加强v1原漏拒绝的protected regular拓扑，不能称全部旧行为未变。
2. shared48MiB physical-read limit后置拒绝：三个实际os.read/pread调用均先按self.total+scope.total的真实remaining裁剪，含proc和EOF探针；remaining≤0在syscall前拒绝，返回len先计账再append/join。proc原4MiB每文件和16MiB累计边界保留，q模块未改。
3. temporary close_one入口错误把原读/parse异常降为secondary：cleanup前inline锁原raw primary，close/dispatch/未消费FD fallback以及report-entry失败均保留；不重试已消费FD。
4. JSON/validation、canonical/map serialization、两个base64和dataclass路径同类报告/checkpoint入口覆盖：有reads/shared buffer时在任何helper前inline保存raw primary及reserved slots；_after_blocking保留原异常和checkpoint secondary，其入口失败由caller保存。pure foreign validator未增加安装权限。

private installation在成功一次cleanup、原proof/source/config连续性及exact shared failure-buffer健康后才登记。64 FD/48MiB界限及原10秒合作式window保留；不能中断同步loads/serialization或称kernel硬10秒。原1200/3600/900及60秒收尾计原额度不变。实际完整map容量、运行耗时、RSS/AS、native/installation/故障注入与durability均未测，完整正式review仍FAIL-001。

最终工作集身份，仅追踪源码而非完整source/runtime冻结：

| 文件（src/eating_event/route2_candidate_overlap/） | B／行 | SHA256 |
|---|---:|---|
| linux_phase_publication.py | 43656／802 | cf5f2d2e4971f135ab4c78e564974b7e110c13d15bea36d33066ee5a041d646c |
| linux_gt_history.py | 132393／2386 | d5d8ba1652ac4e6d40d3edf9e26c43dc910de0b15aa3c5ba52dc1e45d5c61395 |
| linux_enforcement.py | 41538／953 | f88b0925dea9e2bd1b5117d489efdda11a806f3ec29da3e7f24ebaf9c0000a56 |
| linux_quiescence.py | 43714／825 | b50e149e81cf8dff161cdbb27dbb5c1d06f475f5c410092ccbf5ea5db18d5ef7 |
| production_metadata.py | 88909／1693 | 15dc4b1c91b48aafbfb53645de8bde89a6298dcb1d35e4e0e69ad4e13ad61ea1 |

Fresh isolated AST：59个生产Python成功；89文件2,294,790逻辑B、4个native文本、26个历史测试仅hash，mapping 06622d75994ea649c61e9462410f1bad2cb2563a53ec6034f1bbb6c8db430ac2；历史测试map仍469312e5c5ef487681d4bf5ec25c0cc4cf6957ad891912ccc638b34c9cca1b70。git ls-files --stage原95行bytes SHA仍2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e。stage_b/execution/contracts等科学修补按未变hash继承，没有改模型、阈值、decoder、matcher或额外GT评价。授权卡仍88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf，原提示仍c6e85abcbfb0fd9ae64afe2716bae12b21f0ad391e27b30762528c07298357cd。逻辑bytes不是allocated peak或冻结证据。

07:57:01.944 UTC只读宿主实证：Fancy/current token未提升、物理RAM16890322944B；AutomaticManagedPagefile=True，D:/pagefile.sys AllocatedBaseSize16384MiB/CurrentUsage1525/Peak2098，PageFileSetting成功空集不证明fixed/no-growth。E:/Route2Dedicated仍不存在；.wslconfig仍65B/SHA a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5，存在不证明VM应用。未启动/关闭WSL或改变pagefile/global设置。旧RunAs只读成功不是当前可复用提升token，非提升也不是完整缺口。nonE512MiB提前停止仍缺所有作者/未观测/在途最大增长及stop/writeback上界；先前提出改monitor/验收阈值并接受in-flight overshoot的选择没有明确答复，不据“继续”或“先修复”修改原合同。

#### 本轮一次完整A+B最小条件卡更新

状态：APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；完整 route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL，FROZEN_ADMISSION=None。源组件限定闭合不授予完整review或实验准入。

| 项 | 已保留或本轮实际源码进展 | 仍缺真实条件 |
|---|---|---|
| 1 准备／授权／冻结 | 既有PREPARED_UNREVIEWED及负责人续行/无GT准备授权；原卡不改。 | 同一完整可安装runner、全部review和真实预算/身份、负责人最终绑定及可消费FrozenAdmission；无合法Stage A/B结果。 |
| 2 科学唯一变量／105参考 | 固定saved scores、26D、.10/.25/.50、strict overlap对300gap、600秒decoder/180秒minimum及matcher/五折保持，Stage A无GT。 | 105参考实际复现、全窗口/记录/global顺序/来源hash和完整现版等价；源码不推断科学结果。 |
| 3 固定生产调用链／规模 | 已有native child生命周期及固定phase publisher；metadata v2实际FD reader已实现并静态复审。 | _load_native_path_map/_load_native_phase_runner/_require_native_nested_producers仍拒绝；真实early nonGT owner、directory map/role publisher和reader、一套完整runner。19,894文件一遍/Stage A59,682逐文件挂载超过现有history/ID容量，须明确新目录receipt+逐file身份，不能扩cap冒充闭合。 |
| 4 Stage A/B额度／ledger | 105+105、scorer fit/predict0、25 fit attempts含失败/25predict/65decoder、20 GT-backed＋21stGT-free pooled/pooledGTreads0；D_A=2GiB严格容量上界V2。 | 唯一实际ledger/持续强制、合法Stage A实得N/M/S/B及Stage B入场投影、同image2→4GiB；历史scratch/合成不是准入。 |
| 5 最终matched-GT对照 | 既有science P2修补保持，control/treatment最终集合新增/丢失与candidate覆盖分报；publisher有outer-only固定历史路径。 | A2-004合法final metrics/matched-pairs实际来源、五个field-isolated readonly投影及同canonicalGT/commitment授权；未创建或读取GT关联投影，不增加control评价。 |
| 6 信任／隔离／部署 | Windows owner可信，继续WSL2、Ubuntu22.04/glibc2.35；原C child/API与publisher源组件。 | 专用target/注册GUID/held IDs/native上下层对象、实际UID/namespace/IPC/root/全部写路径。READY后父实际kernel观察及成功birth/READY/exit outcome留存尚未实施，现成功路径仍仅返科学result。 |
| 7 两项8GiB／硬实体 | guest承载FS与guest VHDX实际Windows实体卷各≥8GiB，carrier无第三8GiB，独立增长/cleanup reserve。 | 原生creator/format/import/注册和carrier真硬边界；同invocation两项free、三层actual usable/AllocationSize baseline/余额/完整历史，wholevolume free或共享WSL增量不替代。 |
| 8 原时限／CPU/task/RAM/VRAM | 1200/3600/900秒含60；C=min(4GiB,floor3*M0/5)、AS=C/2、swap0、CPU200%、TasksMax2含controller；whole RAM16/VRAM8及已授权.wslconfig保持。 | 实际VM8GB/swap0/2processor应用、first prebirth M0/provenance/native cgroup/AS/CPU/tasks/dxg拒绝、全部任务峰值；Job4GiB commit/4process不代RSS/tasks；原hard clocks/stop/cleanup。 |
| 9 已绑定容量／其余候选 | E30GiB noGT准备：24carrier含20guest、external E6、guest baseline≤8；nonE512MiB含stop/cleanup，10GiB为估计。 | actual三层baseline/retained growth/future峰值/header/余额；64/16MiB控制、prep4GiB/4tasks/200%/1800s、external512MiB/4tasks/100%/6000s、atol1e-12/rtol1e-10/discreteexact仍待实际证据/复审/负责人绑定；旧20/32/34 whole-host scope不能直接签新预算。 |
| 10 全部费用／nonE advance-stop | helper编译/ABI另计，历史/未来准备分开，startup写入不可零；实际系统pagefile自动管理尚在。 | 全C/D/System/registry/eventlog/temp/pagefile/WSL服务/VM/writer/inflight/漏采/最大不可截断分配/stop+writeback计量与提前停止上界；compiler/linker/includes/start files/objects/lib/debug/core/cache/log/source/IPC/errors/tracebacks及observer/helper/launcher/bridge bytes/wall/RAM/task/CPU，缺值UNKNOWN_NOT_ZERO。 |
| 11 readonly/native／原双时钟 | cached40-byte mount helper适配器及publisher source；前birth native clock顺序已独立审计。 | C/H均未编译/链接/装载/实际调用；任何constructor/import/dlopen前完整readonly解释器/stdlib/project/PE/ELF/native/transitive held身份；实际Windows原QPC认证transport和host kill owner、Linux pre-unit/pre-Python真实t0/单次M0原生supervisor/entry及消费者，现QPC loader仍拒绝。 |
| 12 生命周期／terminal退出 | scoped publisher正常unpublication-before-broker-revoke及primary/secondary失败源码；原finalize双异常修补保持。 | 全backing创建/删除/history、唯一逐role/phase GT release/revoke完整装配；真实故障/OOM/crash/quarantine、terminal关闭后签名close/exit join、原cgroup清场、WSL VM/服务真实退出与final durable外部QPC墙钟。fd/umount源码或异常槽不证明clean exit。 |
| 13 独立正式review／等价／冻结 | 两组件最终限定SPEC＋QUALITY无剩余范围P1/P2；59AST/89工作集hash仅追踪。 | 完整可安装production/installation/OS/native/readonly/预算/失败/退出正式review IDs、完整nested现版跨OS等价；旧PARTIAL_MATCH_ONLY不覆盖新源码；完整source/runtime/input/role/map/launcher/worker/controller/协议和预算冻结。 |
| 14 实验及成功终点 | 预声明早停或一次五折Stage B；COMPLETE与质量门分开；pooledF1≥.66、至少3/5fold≥.66、各fold longFP≤.25、起止MAE≤900秒及最终match增减保持。 | Stage A/B未合法运行，105参考/候选差异/decoder是否保留/F1/MAE/泛化均无合法结论；只在负责人提供合法Route2结果后再讨论三架构最小验证。 |

四项状态分别确认：准备视图PREPARED_UNREVIEWED；可消费A+B准入未形成/FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二没有合法结果。完整FAIL-001保持，scratch2→4GiB/13-wheel/历史合成/窄静态审阅都不是实验准入PASS。Route3 v1-003合法COMPLETE／四门FAIL不重跑，gap0已由Route2覆盖。

本次只源码实施/AST/hash/独立静态复审及宿主只读元数据；未新增/运行测试、读测试体或project import，未native编译/链接/装载/调用、WSL/GT payload/生产/Stage或正式image/volume/study/ledger/lock。保留全部原dirty/staged/untracked，无commit/reset/delete或无关覆盖。下一phase-child实际观察/outcome只是原计划的待实施范围，本次没有新增其文件或移除完整生产拒绝。

### 2026-10-09 整合后续：phase-child原始内核观察、一次outcome及独立复核

本节接续原整合后修订。负责人继续补齐到合法Stage A/B的意图与准备授权已给出；当前可消费的完整冻结准入仍未形成。保留Windows owner可信、WSL2/Ubuntu22.04/glibc2.35、E30GiB无GT准备预留（24GiB carrier含20GiB guest、外部E6GiB、guest actual baseline≤8GiB）、nonE新增512MiB含停止收尾且超额前停止、whole RAM16GiB/VRAM8GiB与全部原study限制，不重复申请权限。本节不能把来源代码的局部闭合改写为完整路线二或实验放行。

实际新增private linux_phase_child_observation.py，并改linux_child_launch.py、linux_phase_publication.py及linux_enforcement.py两处必要属性。原始C spawn/pidfd/READY/status/wait/reap适配器衔接同一原guard/startup、GT owner/current grant/canonical scope/durable release、publisher active batch及原armed绝对stop/cleanup。native出生返回立即强留原PID/pidfd/IPC/status/permit FD与errno数值，再进入校验/报告。父进程在permit前从原held pidfd、/proc、nsfs和cgroup anchor取得真实内核样本：WNOWAIT活性、process start/PPid、UID/GID/Groups/Threads/caps/NNP/seccomp、各namespace类型及身份、实际cgroup成员/任务及四硬上限、原child root/input clone/mount frame、全部preexec FD与readonly runtime ELF。输入仅原当前GT和outer-only历史control投影，不读GT payload。

实际IPC peer查询以held UNIX socket cookie和原NETLINK_SOCK_DIAG目标请求双向比对内核peer inode；SO_PEERCRED仅作为socketpair创建时身份，不冒充child peer。父unit的RestrictAddressFamilies改为AF_UNIX AF_NETLINK，旧worker仍AF_UNIX、C child仍拒绝socket syscall；其他限制不扩大。[Linux v5.15 unix_diag UAPI](https://github.com/torvalds/linux/blob/v5.15/include/uapi/linux/unix_diag.h)与[内核peer查询实现](https://github.com/torvalds/linux/blob/v5.15/net/unix/diag.c)仅支持上述接口语义，不提供目标实证。netlink/nsfs/ptrace/LSM/CONFIG_UNIX_DIAG、模块autoload及费用都须实际目标证明，当前没有实际调用证据。runtime FD核同一真实readonly ELF和UID65534的DAC访问条件，不替代任何constructor/import/dlopen前完整readonly解释器/stdlib/project/native/transitive闭包。

原观察写入唯一durable历史后，再核原owner/live/deadline并发一次permit。成功路径保留原READY字节、实际birth/观察、native状态、WNOWAIT/wait/reap/once-FD-close及科学result，先完成durable finished再登记私有once outcome；只有同一owner PID/thread/current batch可消费，durable consumed成功后移除私有登记，batch仍强留原事实。失败只用原pidfd杀停/真实wait-reap及消费后一次close；不可回收的原state继续强留，报告/关闭失败保留primary及secondary并poison原owner。失败后尝试unpublish仍受真实reference fence与failed状态约束；失败缓冲并不制造clean receipt。完整生产caller尚未装配，本轮没有启动child/observer/publisher。

独立规范复审发现的失败保存/cleanup入口及原生错误报告缺项已修补，包含安装read强留、报告失败先锁原raw primary、剩余owned FD先消费再close且不重试号码、native负返回先留errno/error、安装成功登记放在finally及原buffer健康之后。它们是既有控制流缺口，不把所有修补称为新回归。fresh QUALITY另确认两项P2：最终fence须从同一held cgroup anchor再次重读memory.max/memory.swap.max/pids.max/cpu.max/cgroup.procs/cgroup.threads并保存final raw，四limit与规范化任务集合变化即失败；inline/fallback不得将本buffer.failure写回自身primary/first/secondary，foreign wrapper仅由实际origins/captures还原原raw及真实secondary，原buffers仍强留。这两项修补后的限定SPEC→QUALITY结果为 fresh独立LIMITED SPEC及LIMITED QUALITY均未发现剩余受影响范围P1/P2。没有正式review ID；不签完整implementation或准入PASS。

| 文件（src/eating_event/route2_candidate_overlap/） | B／行 | SHA256 |
|---|---:|---|
| linux_child_launch.py | 47517／881 | 18db36acc9e3d2b322a381bf33f9ffe203c7011fe3d6871485826ddd35febb7f |
| linux_enforcement.py | 41782／956 | 5c893f24cf287804a68d26734a2cd2d20f7bd9d405515bdf04906ec1664b81ba |
| linux_phase_child_observation.py | 54500／933 | dd52d6d07182574838e5a5cdad382390f6f52916836255e6177270e4e2c486eb |
| linux_phase_publication.py | 100107／1833 | 891277a7a95e458ff603c8f316f26a320e5e65361abe04ca49ffdca275f5ebda |

root fresh stdlib isolated核对：60个生产Python AST成功，90文件2,434,474逻辑B／4 native文本／26测试仅hash，mapping cdfb4bc3dc9a54adabeb8c21f2f7fef2ace2d880991a7dd7ec8b421286283496。26历史测试只hash、不读取测试体或运行；测试map仍469312e5c5ef487681d4bf5ec25c0cc4cf6957ad891912ccc638b34c9cca1b70。原git index95行bytes SHA仍2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e；原授权卡SHA仍88fb568136da88451b5a6be0d2cb7452d3340c8e9855945ee1d82b52ef904ddf、提示仍c6e85abcbfb0fd9ae64afe2716bae12b21f0ad391e27b30762528c07298357cd。原89文件仅本4文件变化/新增，无源码删除；production_metadata、native C/H、stage_b/execution/contracts及其他既有源码按未变hash继承原限定结论。工作集hash是追踪，不是完整source/runtime冻结，logical bytes不是allocated baseline或峰值。

14:29:28.5995319 UTC只读宿主：Windows11家庭版中文/26300、当前Fancy token非提升、物理RAM16890322944B；AutomaticManagedPagefile=True，D:/pagefile.sys AllocatedBaseSize16384MiB/CurrentUsage1814/Peak3247。现有pagefile分配不是本任务新增成本，usage不是AllocationSize增长；自动管理仍不能给出本任务可用的未来增长上界。E free1009242656768B、C free28223995904B、D free116280750080B，仅为全卷样本。E:/Route2Dedicated不存在，.wslconfig仍65B/SHA a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5，存在不证明WSL VM已应用。HKCU登记元数据仅列出共享Ubuntu-22.04/WSL2，BasePath在C:/Users/Fancy/AppData/Local/Packages/CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc/LocalState；没有探测或改变实际运行状态。旧RunAs只读成功不能替代当前提升token；现状也不是只缺管理员权限。

此前预算选择中的“少量在途超额”已明确纠正：pagefile/WSL服务/系统日志超额上界未知，不能保证很小。已请求负责人决定是否将nonE512MiB改为监控预算、提前预警和停止但如实接受上界未知的在途超额；当前尚无明确答复。答复前保持原严格超额前停止合同，不能据“继续工作”、宽泛权限或时间流逝替换。即使改变口径，实际专用对象、原生边界、全部费用和完整runner仍须闭合，不等于自动批准Stage。

#### 本轮一次完整A+B最小条件卡更新

APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。完整route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL，FROZEN_ADMISSION=None。

| 项 | 已保留或实际源码进展 | 仍缺真实条件 |
|---|---|---|
| 1 准备／续行意图／准入 | PREPARED_UNREVIEWED，负责人续行和准备授权保留；原授权卡不改。 | 同一完整可安装runner、真实对象/费用/预算、完整正式reviews与最终绑定形成可消费FrozenAdmission；没有合法Stage结果。 |
| 2 科学变量／105参考 | saved scores/26D/.10/.25/.50/strict overlap对300gap/600秒decoder/180秒minimum/matcher/五折保持，Stage A无GT。 | 105参考真实复现、完整记录/窗口/global顺序/来源身份及现版科学等价；不能据局部源码推断F1。 |
| 3 固定生产装配／规模 | metadata v2真实受保护FD reader、固定phase publisher及原child观察/outcome源码已推进。 | _load_native_path_map/_load_native_phase_runner/_require_native_nested_producers仍拒绝；early nonGT原owner、目录role-map/reader/publisher及完整caller未实施。19,894文件一遍/Stage A59,682逐file挂载超过旧ID/history容量，须新目录receipt与逐file真实身份，不能直接扩cap。 |
| 4 额度／ledger／D_A | 105+105、scorer fit/predict0、25fit attempts含失败/25predict/65decoder、20GT-backed+21stGT-free pooled/pooledGTreads0；D_A2GiB严格容量上界V2。 | 唯一实际ledger与持续强制、合法Stage A取得N/M/S/B及Stage B投影、同image2→4GiB；历史scratch、13wheel、合成不代准入。 |
| 5 最终matched-GT对照 | 既有control/treatment最终match新增/丢失与candidate coverage分报修补保持，outer-only固定历史input。 | 合法A2-004最终matched-pairs实际来源、五个field-isolated readonly投影及canonical GT/commitment授权；不增加control评价，原once GT commitment-key issuer仍缺。 |
| 6 信任／WSL／child隔离 | trusted Windows owner、Ubuntu22.04/glibc2.35；实际内核观察生产源码及一次outcome，父netlink必需属性。 | 专用target/注册GUID/原对象ID、真实UID/ns/IPC/root/FD/mount/cgroup和属性应用；ptrace/LSM/UNIX_DIAG功能与实际运行未测，READY/schema不是事实。 |
| 7 两项8GiB／per-study实体 | guest FS与VHDX实际Windows实体卷各≥8GiB；carrier无第三8GiB而有增长/收尾reserve。 | 原生creator/format/import/注册、专用实体硬限、同invocation两项free、三层actual usable/AllocationSize baseline/余额及完整backing历史，wholevolume free/共享WSL增量无效。 |
| 8 时限／RAM/AS/CPU/tasks/VRAM | 1200/3600/900含60；C=min(4GiB,floor3*M0/5)、AS=C/2、swap0、CPU200%、TasksMax2含controller；whole RAM16/VRAM8保持。 | FIRST prebirth M0与原clock出处、VM8GB/swap0/2processor实际应用、原cgroup/AS/CPU/tasks/全部峰值及dxg拒绝；Job commit/process不代RSS/tasks。 |
| 9 准备容量／候选预算 | E30GiB：24carrier含20guest+外E6，guest baseline≤8；nonE512MiB含stop/cleanup，10GiB只是估计。 | actual三层baseline/未来峰值/header/余额；64/16MiB控制、prep4GiB/4tasks/200%/1800s、external512MiB/4tasks/100%/6000s与atol1e-12/rtol1e-10/discreteexact仍待实证/复审/最终绑定。 |
| 10 全费用／nonE停止 | helper编译/ABI另计、startup控制写入不可零；严格512MiB未获修改。 | C/D/System/registry/eventlog/temp/pagefile/WSL VM/服务所有作者、漏采/在途/不可截断分配与stop/writeback上界；控制、compiler/linker/includes/objects/libs/cache/core/errors/history/future准备及observer/helper/launcher/bridge资源，UNKNOWN_NOT_ZERO。 |
| 11 readonly加载／原双时钟 | mount adapter及spawn/observer源码；prebirth native事务顺序已定位。 | native C/H未编译/链接/装载/调用，完整preconstructor readonly解释器/stdlib/project/PE/ELF/native/transitive实际closure；pre-Python/pre-spawn Linux t0/单次M0 supervisor/entry/v3消费者、原Windows QPC认证transport与host kill owner，loader仍拒绝。 |
| 12 生命周期／terminal退出 | durable-before-permit、出生/READY/status/真实wait-reap/onceclose强留及private once consume源码，primary/secondary保持。 | 完整phase/runtime/backing创建删除、唯一逐role/phase GT release/revoke实际装配；真实故障/OOM/crash/quarantine、terminal关闭后签名close/exit join、原cgroup清场、VM/服务实际退出和最终durable外部QPC验收。 |
| 13 完整review／现版等价／冻结 | 本4文件限定两审与AST/hash仅覆盖其源码；此前未变组件结论继承。 | 全可安装production/installation/OS/native/readonly/预算/故障/退出独立正式review IDs、现版完整nested跨OS等价及全部source/runtime/input/role/map/launcher/worker/controller/协议预算冻结；旧PARTIAL_MATCH_ONLY不足。 |
| 14 实验／质量终点 | 合法预声明早停或一次五折Stage B；COMPLETE与质量门区分；pooledF1≥.66、≥3/5fold F1≥.66、各fold longFP≤.25、起止MAE各≤900秒及最终match集合增减保持。 | Stage A/B未合法运行，参考复现/机制差异/decoder保留/F1/MAE/泛化没有合法结果。仅合法Route2结果后再讨论三架构最小验证。 |

四项状态仍分别确认：PREPARED_UNREVIEWED；FROZEN_ADMISSION=None且可消费A+B未形成；Stage A/B均未合法运行；路线二没有合法结果。scratch2→4GiB、13-wheel、历史合成和窄静态复审均非实验准入PASS。Route3 v1-003合法COMPLETE／四门FAIL保持、不重跑，gap=0由Route2覆盖。

本轮仅源码/AST/hash/独立静态复审及只读宿主元数据。未新增/运行测试、读取测试体或project import，未native编译/链接/装载/调用、WSL操作、GT payload/生产/Stage或创建正式image/volume/study/ledger/lock；无commit/stage/reset/delete或无关覆盖，原dirty/staged/untracked、index、原授权卡/提示保留。讨论/决定/状态仅追加原三文档，无新交接包。


### 2026-10-09 负责人绑定nonE监控预算及下一生产源码范围

负责人明确答复“采用监控预算并接受上界未知的在途超额，继续工作”。nonE新增512MiB从严格超额前停止改为监控预算：实际observer须提前预警、停止新增工作、计入停止/收尾及可见增长，并记录采样/在途/系统共享作者的遗漏和超额；超额上界仍UNKNOWN，不能保证很小或改称per-study实体硬限。这项是明确资源口径变更，不是重问访问权限。先前384MiB active+128MiB收尾为规划分配，实际计量/阈值/停止执行者仍待实现和复审。既有pagefile分配及共享Ubuntu baseline不能计成任务新增；无法归属的成本保留UNKNOWN_NOT_ZERO。

仅此nonE口径变更，E30GiB准备预留（24carrier含20guest、外E6、guest实际baseline≤8）、whole RAM16GiB/VRAM8GiB、Windows owner可信/WSL2/Ubuntu22.04/glibc2.35、两项8GiB、1200/3600/900含60、C/AS/swap0/CPU200%/Tasks2、D_A2GiB V2及20+1/pooledGTreads0均保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整route2-ab-full-implementation-review-2026-09-29-FAIL-001/FAIL、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。负责人续行意图已授，实际完整冻结准入尚未形成。

按已批准的controller-only science key/固定phase-worker设计，下一独立生产源码范围是补齐原owner的once GT commitment key生产者及原payload绑定。当前linux_phase_publication._phase_launch_payload明确记录issuer缺失，codec的32–64B caller key只是科学数据。由同一健康的原GT owner/current grant/publisher batch/parent PID与thread、原startup/ledger/绝对clock下调用系统getrandom取得32B；一轮producer invocation先消费再调用，raw返回先强留后校验/历史/格式化，短返回、EAGAIN/ENOSYS及任何原事实缺失直接拒绝并保留primary/secondary，不fallback、不重新发key。相同invocation后续phase沿同一原对象复用并核payload key；科学key不授GT或native权限，不承诺完整payload freeze。先前helper C/H和科学操作/算法不改，完整runner/installation拒绝门保留。Python wrapper内部可能处理EINTR，不能把一次Python producer调用宣传为单次底层syscall实测。接口语义来自[Python3.10 os](https://docs.python.org/3.10/library/os.html#os.getrandom)及[Linux getrandom](https://man7.org/linux/man-pages/man2/getrandom.2.html)，不是本机目标功能/费用证据。

工作集恢复核对仍90文件mapping cdfb4bc3dc9a54adabeb8c21f2f7fef2ace2d880991a7dd7ec8b421286283496、60生产AST、4native文本、26测试仅hash，原index95行及授权卡/提示hash不变。该map只追踪，非完整source/runtime冻结。当前只源码/AST/hash/独立SPEC→QUALITY及只读元数据，未新增/运行tests或读测试体、project import/native编译链接装载调用/WSL/GT/生产/Stage/正式image-volume-study-ledger-lock，不改无关工作。完整14项条件卡在本unit收尾后仅在本review更新一次；原授权卡不改，无新交接包。


### 2026-10-09 once science key源码闭合及固定native phase事务接续

本unit实际只改linux_gt_history.py和linux_phase_publication.py：原Owner预分配private key record；首合法active batch在原guard/startup/GT grant/ledger/PID-thread/绝对clock下，消费一次Python调用尝试后执行cached exact posix.getrandom(32, GRND_NONBLOCK)。raw直接强留再校验32B与fingerprint，原durable started先于call、finished后才usable；后续phase复用，当前payload核原bytes。失败先保留raw primary/真实secondary及原buffers，poison并不重发；snapshot/history/closure保留实际once记录。key只为科学GT身份，不授原生权限，不承诺完整payload freeze或immutable bytes清零。实际producer尚未运行，Linux支持、费用及底层syscall次数保留UNKNOWN_NOT_ZERO。

fresh独立LIMITED SPEC→LIMITED QUALITY均no remaining scoped P1/P2，无正式review ID/fullPASS。root fresh stdlib AST/hash：两文件134921B/2448行/SHA1309117fc2ef99fb078856c7a62606d71408344e7d418459ccc2214385fbb0a7，以及118155B/2120行/SHAc11beb752ffc4ebbdbe05ba47cd77fe7b12a653a0c3b4bdc90f36c327ce7fd24；90文件2455050逻辑B、60生产AST成功、4native文本和26测试仅hash不变，mapping9ea22c374f1572a477b2bfb368d9dd761860a0719e370696e5793aac561950db。index95行、原授权卡/提示保持。map是追踪而非完整冻结。

16:02:34.2272992UTC宿主只读：当前Fancy token未提升；E:/Route2Dedicated不存在，E free1008907411456B；.wslconfig仍65B/原hash，仅共享Ubuntu22.04注册元数据，未操作WSL。自动pagefile仍True，D页文件AllocatedBaseSize18456MiB，较14:29的16384增加2072MiB；这是共享系统分配变化，不能全归本任务或计零。当前nonE512MiB已由负责人改为监控预算并接受上界未知在途超额，实际计量/预警/停止新工作/收尾observer仍缺；384+128只是规划。E30GiB/wholeRAM16GiB/VRAM8GiB及全部原study限制不变。

按已批准的固定phase-worker/逐scope撤销设计继续下一个实际生产源码组件，不在unit间重复申请权限：绑定原bootstrap/guard/controller的固定native phase执行器，只有原GT owner/current registry/armed clock可进入；preallocate强留原事务，再由原broker一次grant、publisher实际挂载、原key getter、C spawn/真实once outcome消费、publisher.close后broker一次revoke。StageB生产分支使用原事务实得release/revoke/outcome，禁止legacy ledger再次记账；普通caller receipt/布尔/hash/callback不能代替原对象。source/runtime/role-map缺口仍须拒绝，完整nested producer/路径/installation/QPC gate不得伪闭合。失败保留primary/全部secondary及实际未清场对象，不把失败正常closed、正常revoke或quarantine写成成功。

范围限定必要private native phase源模块、stage_b.py、production_runner.py，以及gt/publisher必要原事务连续性hook；不得变科学codec/模型/阈值/decoder/matcher/折、C/H和额度。实际spawn/helper仍不得运行。fresh SPEC→QUALITY后root AST/hash；本轮完整14项卡只在最终收尾更新一次。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、fullFAIL-001、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage或Route2结果；没有tests/import/native/WSL/GT/生产/Stage/正式对象/commit/reset/delete/new handoff。

### 2026-10-09 固定native phase事务限定双审收尾及监控组件接续

实际新增linux_phase_runner.py，并修改stage_b.py、production_runner.py、linux_gt_history.py、linux_phase_publication.py。原bootstrap/guard/controller在start前只作source/私有归属装配，不发GT或加载helper；执行时重核原已安装owner/registry/armed绝对clock和完整安装门，再由原broker唯一grant/release、原publisher实际publish、原系统once32B科学key、原native child/outcome一次消费、原children/reference fence及close/unpublish、原broker一次revoke。StageB native分支取原私有事务结果，保留common科学和最终control/treatment matched-GT校验，再一次durable接纳；legacy release/revoke只留非native分支，避免double writer。原Windows logical control RegisteredFile保持，child固定/inputs读取，不能误改成Linux alias。

fresh独立SPEC先修take/accept/scientific reject的raw primary预存与helper入口secondary，再补报告函数和随后保存入口双失败的独立strong holder/raw secondary；所有失败保留实际原primary/secondary与真实buffers，不重试consumed birth/FD/outcome/close/revoke、不将failed正常closed/quarantine。最终LIMITED_SPEC_NO_REMAINING_SCOPED_P1_P2、后续fresh LIMITED_QUALITY_NO_REMAINING_SCOPED_P1_P2，均SOURCE_ONLY、无正式review ID/fullPASS。GT owner强留事务，private snapshots包括原返回/错误/attempt，完整事务hook只在真正GT-free completehistory，不在broker.revoke内publisher fence递归判半关闭。无GT/no事务早停保持合法。

准确最终source身份：linux_phase_runner.py 69866B/1275行/SHA dc31fac7d3521578086acaaeb0c2f98a2d5db3dfe2ec07c870dc61dae474a54f；stage_b.py 78604B/SHA 1f23761b896766dea965f4367c65a075a68ff3de7364493dc36282e7a9e7c845；production_runner.py 23298B/SHA 9ccc0b4985c09d51e8c43b48c3543c9260ce51007547e80f39acf293a8d2f8f1；linux_gt_history.py 135442B/SHA aa260514cca017fe06ed2d502b4712b029c7a79992eed63ee078b97f88eba043；linux_phase_publication.py 118297B/SHA 1d68296ebd96fea8846bb7f2a19370a14169f2be5cf84ddc2bcad91bb812443a。root fresh 61生产AST全OK、91文件2528332逻辑B、4native文本/26tests仅hash、mapping b388388a5e0b1ebd37433feff45f9b4d10d9c3a19d9a06345a5555bd8c3018d6；原index/test/native/auth卡提示不变。map仅源码追踪。完整_load_native_path_map/_require_native_nested_producers/QPC/installation仍拒绝；fixedphase factory的条件源码接通不等于生产runner可装或可跑。

17:14:57UTC只读Get-Command在当前PATH未见cl/clang/gcc/link/lld-link；见diskpart/wsl.exe；不据此断言全部工具链未安装。E:/Route2Dedicated和固定prep-worker.exe仍不存在。17:29:31–17:29:36UTC一次只读CIM元数据探索，局部测量5239ms，不是生产monitor/原invocation epoch：C free28128903168→28128829440（全卷可见减少73728B），D/E该短窗未变，D pagefile AllocatedBaseSize回到16384MiB；原16:02的2072MiB增长不能因回落改计零，所有共享变化归属UNKNOWN_NOT_ZERO。查询进程workingSet96321536→98512896B、private72269824→74100736B、CPU0.515625秒、threads29→28。只有两次样本，没有峰值/完整费用/全系统作者覆盖；PowerShell线程数超候选外部4任务，不能由Job四process等同四task。

接续负责人已接受nonE监控预算的实际源组件：原Windows private Job owner的固定C/D host卷实际native GUID/held root identity/free-space采样、raw强留、原owner/pid/thread/QPC continuity、固定容量有界记录和monitored positive high-water/可见超额记录；整盘free变化只为信号，不等于task AllocationSize或所有系统作者成本。候选384MiB预警/停止新增工作、128MiB收尾仍仅规划，实际最终绑定/全成本/全任务外部observer待闭合；不由本private组件签准入。原Job在每个新Job/child/resume边界及等待中核当前实际样本，触发时停止新工作并进入原owned-handle cleanup；收尾继续读并保留错误，不用预算触发跳过原关闭，不宣称杀wsl.exe即VM/service退出。该源码范围只新增必要private Windows监控模块和windows_preparation_job.py接线，保留现有readonly/pre-Python/worker缺失顶层拒绝，原60/70秒局部生命周期不得改称1800/3600/6000或原总clock。实际全任务原生外部observer与4task/RSS/WSL服务证据另缺，不用PowerShell查询进程充当它。

本轮只源码/AST/hash/独立静态复审和只读metadata，未tests/test-body/import/native编译链接装载调用/WSL/GT/production/Stage/正式image-volume-study-ledger-lock，无git mutation/commit/reset/delete/new handoff。nonE512MiB MONITORED及上界未知在途超额接受、E30GiB/RAM16GiB/VRAM8GiB绑定保持。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED，无合法Stage/Route2结果；完整14项卡只在本轮最终收尾更新一次。

### 2026-10-09 剩余候选预算限定复审及负责人最终绑定提案

负责人已绑定E新增30GiB无GT准备预留（24GiB carrier内含20GiB guest、载体外E6GiB，guest实际入场baseline≤8GiB）、nonE新增512MiB MONITORED并接受上界UNKNOWN的在途超额、whole-task RAM16GiB／VRAM8GiB及已批准.wslconfig。以下只提交原候选限制供负责人最终绑定，不重问既有决定，不代表实测费用、可部署证明或完整A+B准入。

| 候选项 | 本次具体绑定提案与计费范围 |
|---|---|
| guest控制 | 64MiB，内计于guest20GiB；config/key/seal/ledger/lock/receipt/startup/原始失败/日志/traceback/IPC backing及相应临时、header和清理均计入实际guest归属。 |
| host控制 | 16MiB，明确仅指实际位于外部E的控制对象，内计于external E6GiB；C上的.wslconfig、registry/eventlog/pagefile/WSL service等仍属nonE监控及未知费用，不迁入E账或计零。 |
| 无GT准备及native编译／ABI | 合计RAM4GiB、CPU200%、TasksMax4（线程／任务含controller）、总wall1800s且60s收尾计入原额度；准备不与study并行。compiler/linker/includes/start files/objects/lib/debug/core/cache/log/source/历史与未来准备分类分账，编译／ABI单列不获得第二份额度。 |
| 外部observer/helper/launcher/bridge | 原scope合计RAM512MiB、CPU100%、TasksMax4（线程／任务）、总wall6000s且60s收尾计入；归属的VM/kernel/service及未知成本保留，不默认排除或零。Job四process/commit、PS查询28–29线程均不能证明此上限；必须有实际满足限制的固定原生实现，否则拒绝。 |
| nonE提前停止规划 | 在已绑定512MiB MONITORED下，以384MiB可见增长作为停止新增工作候选阈值，128MiB只作名义收尾规划；不是硬reserve、全部作者/AllocationSize归属证明或超额上界，不保证超额很小。 |
| 完整现版数值等价判据 | 对称abs(a-b)≤1e-12+1e-10×max(abs(a),abs(b))，阈值/排序与tie/区间/匹配/计数/质量门等离散决定完全一致；用于未来完整nested验证，旧PARTIAL_MATCH_ONLY不能通过。 |

fresh独立限定静态提案复审：适合提交负责人作具体CAP／配置绑定，未发现提案自身新增P1/P2算术矛盾；无正式review ID、full PASS或compile/run/Stage授权。条件算术30=24+6，guest20已内含；64/16MiB不另加到30。沿原规划guest 8+max(8,6+1)=16GiB≤19GiB usable，carrier 22+0.125+0.125=22.25GiB≤23GiB usable；均是条件算术，actual usable、AllocationSize/header、增长和余额未取得，不能称实测baseline/peak。future6已含同一study最大4GiB，不另加2+4。两项8GiB须正式镜像创建前同一invocation实测guest承载FS及VHDX所在实际Windows实体卷，不是新增16GiB支出，carrier无第三项8GiB门。

1800+3600=5400s，6000中的600s只是外部scope规划余额，不重开时钟；原1200/3600/累计fit900及60收尾均不变。非并行准备与study的已列RAM算式max(4,C)+0.5≤4.5GiB不覆盖VM/kernel/service，不能据此证明whole-task16GiB；配置文件存在不证明VM实际应用。已知旧subset3.247270GiB+同study max4=7.247270GiB排除OS/工具链/控制/历史未来费用，不是actual baseline/peak。共享pagefile增长2072MiB后回落归属仍UNKNOWN_NOT_ZERO，不能全归本任务或计零。

尚待负责人明确最终绑定以上候选数字；这一步源于原负责人“候选，复审后再由负责人最终绑定”的要求，全访问权限或“继续工作”不替代数值选择。未回答前仅源码、AST/hash、独立静态复审和只读metadata，不编译/链接/装载/实际调用helper或启动生产。即使回答采用，实际原生CAP、全费用、专用对象/readonly加载/QPC/退出及完整正式review仍须闭合；不自动开启Stage。状态PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。讨论只追加原三文档，原授权卡/提示保持不改，不新增交接包。

### 2026-10-09 监控源双审收尾及early nonGT目录读取实际组件接续

Windows private监控源最终52829B/902行/SHA63bf3e04fa699e5bd7132f089c2c8e845417873e4f0d4c1c39169d734e5cb2eb；windows_preparation_job.py41979B/805行/db5313e36fcddfe6914dca4338592a7f40d44d2f1b75093865f7139346f37eb7未改。fresh限定SPEC→QUALITY重核均无剩余范围P1/P2，无正式ID/fullPASS。修补独立原资源子引用、原baseline/highwater/slot消费连续性，以及合法whole baseline后有效单卷即使peer失败也累计原private完成事实的可见下界；初始baseline仍须全部native/topology/finalQPC提交，整体UNKNOWN及raw primary/全部secondary、实际PID/thread-before-consume/onceclose保留。actual部署/全部作者和AllocationSize归属/whole任务时限及费用仍未证，不能用局部监控源解除顶层readonly/pre-Python拒绝。root62生产AST/92文件2593064 logical B，hash map只源码追踪；完整卡本轮最终仅更新一次。

接续原优先一中可独立闭合的真实生产组件：启动前early nonGT metadata目录原owner、固定exact path-map v2装配及同FD读取源码。当前production_runner._load_native_path_map仍直接拒绝；生产.metadata v2 envelope已保留原受保护FD取得的validated map，不能用caller控制器/receipt/schema/hash重新制造native权限。此unit只闭合early metadata目录producer/reader及factory，不把尚缺的逐role directory publication、nested/readonly runtime/QPC/native时钟/部署/退出写成已完成。

1. v1 canonical manifest、parser、receipt语义和API保留；增加显式compact目录map v2，wire entry只保留logical_path/sha256/role_id/phase，bind_path由固定规则派生，禁止wire传入自选path。metadata在/run/route2-input/metadata；nonGT role在/run/route2-input/roles/<SHA256(role_id)>；GT和outer historical仍用既有flat opaque alias。同一ExactFileMapping仍保存完整派生alias。目录receipt必须与逐file实际FD/mount/frame身份分开，不能把共享目录mount ID包装成多个唯一file mount ID。当前单遍19894文件/Stage A59682逐file挂载问题不靠扩cap解决；新compact encoding不扩16MiB map、48MiB joint、node/FD/history等既有边界。
2. 仅原bootstrap、原protected metadata、原guard/controller可由固定private factory装配；从retained validated map取得plain数据，不再无界JSON重解析，不接caller路径/clock/budget/resolver/callback或声明式receipt。early装配在guard.start前，不把seq2 GT installer移到前面，不装载helper或开启GT。
3. 真正原OS directory/file FD、fstat/fstatvfs、fdinfo/mountinfo、readonly/protected ancestor/flags/stat事实必须在原PID/thread和原绝对clock下取得；只核当前metadata目录及合法metadata files，逐file hash与consumer用同一readonly FD，不触GT/historical O_PATH/hash/content。没有实际对象/原身份/原生事实即UNKNOWN/拒绝。新reader使用既有stdlib OS入口，不新增ctypes/libc/helper装载来绕过preconstructor要求；完整加载闭包仍是缺失门。
4. acquisition结果、原FD数值、原raw/errors及primary/所有actualsecondary先于type/hash/report/helper保留，实际消费前核原PID/thread，消费后一次close、不重试号码，各独立close互不跳过；失败强留未知原对象和原错误，不生成成功close/quarantine。factory成功前完成其临时scope全部close并核failure buffer健康，避免增加未装配terminal-close的长寿FD。原公开holder漂移拒绝新读而清理原refs；不扩为任意private-global Python sandbox。
5. _load_native_path_map改接固定actual early factory；_require_native_nested_producers及完整installation/readonly/QPC/逐role producer拒绝继续保留，普通v2 metadata或同类对象不成为IO authority。原GT installer只增加mode-specific静态alias一致性检查，GT实际grant/revoke及40-byte helper ABI/额度/科学逻辑不变。没有实际role publisher时不允许以legacy caller controller开启native role lease。
6. 源范围仅path_map.py、production_metadata.py、production_runner.py、linux_gt_history.py及必要新private linux_native_path_map.py；讨论由root仅追加原三文档。单implementation→fresh独立SPEC→fresh独立QUALITY→root AST/hash/实际范围核对，失败交同一实现者修补，不先开始下一implementation。完整source/runtime冻结、实际helper/部署、全费用/预算方法及完整正式review仍须另外闭合。

原预算候选提案已复核并写回，当前负责人最终绑定问题待回答；源码不依赖回答继续，helper编译/装载/调用及生产仍不启动。只SOURCE、AST/hash、独立静态复审和原metadata readonly核对，无tests/test-body/projectimport/native/WSL/GT/Stage/正式image-volume-study-ledger-lock，无commit/stage/reset/delete/无关覆盖或新handoff。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED及无合法Route2结果保持；Route3 COMPLETE/四门FAIL不重跑。

### 2026-10-09 负责人最终绑定剩余限制

负责人对上述具体候选问题回复“采用列明的候选限制（建议）”。该明确选择取代前文“待负责人最终绑定”的数值待定状态，原访问权限及监控在途超额决定继续有效；不是实际原生方法、部署事实或实验准入的替代。

最终绑定：guest控制64MiB内计guest20GiB；host控制16MiB只计实际外部E对象、内计external E6GiB，C上的.wslconfig及registry/eventlog/pagefile/WSL服务成本仍归nonE。无GT准备及native编译/ABI合计RAM4GiB、CPU200%、TasksMax4（线程/任务含controller）、总wall1800s，准备不与study并行，编译/ABI单列计费但无第二份额度。外部observer/helper/launcher/bridge原scope合计RAM512MiB、CPU100%、TasksMax4（线程/任务）、总wall6000s。两项wall均将60s收尾计入原额度，不重开原绝对时钟；原Stage A/总/累计fit1200/3600/900s、study C=min(4GiB,floor(3×启动可用RAM/5))、LimitAS=C/2、swap=0、CPU200%、TasksMax2含controller保持。

nonE已绑定512MiB MONITORED，以384MiB可见增长停止新增工作、128MiB仅作名义收尾规划；负责人接受上界UNKNOWN的在途超额。128MiB不是实体reserve或超额上界，不能保证超额很小，全部写入者/AllocationSize归属与VM/kernel/service成本仍须保留UNKNOWN_NOT_ZERO。whole-task RAM16GiB/VRAM8GiB、E准备30GiB=24GiB carrier（含guest20GiB）+external E6GiB及实际guest baseline≤8GiB保持。完整现版数值等价使用对称abs(a-b)≤1e-12+1e-10×max(abs(a),abs(b))；阈值、排序/tie、区间、匹配、计数及质量门等离散决定完全一致。旧PARTIAL_MATCH_ONLY不满足该完整判据。

数值绑定已闭合，实际费用/原scope的RAM、CPU、线程/task及总clock执行方法、专用目标/三层baseline与剩余预算、完整readonly加载/原QPC/退出及独立正式review仍未闭合。当前仅继续已限定源码、AST/hash和独立静态复审，不因这一回复编译/装载/helper调用或启动生产/Stage；完整A+B最小条件卡在本轮源码复审最终收尾更新一次。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL，APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。

### 2026-10-09 early metadata 目录实现与限定复审收尾

本轮实际源码工作接通固定 `_load_native_path_map` factory，增加 compact directory map-v2 与独立 early metadata owner/同 FD reader。map-v1 保留；v2 wire 只保存逻辑身份，metadata、非 GT role 与历史 GT 的实际 alias 分别由固定规则导出。元数据 envelope-v2 与 map-v2 明确配对，并继承原受限 FD 解析、16MiB map/48MiB 联合容量、节点/FD/history 上界；没有扩大额度。

factory 只接受原 bootstrap、protected metadata、guard/controller，以实际 PID/thread、原绝对 clock、nofollow FD、fstat/fstatvfs/fdinfo/mountinfo 与 namespace/只读保护事实观测已存在目录。hash 和 consumer 使用同一只读 FD，读取前后核目录、leaf 与 epoch；仅可读 `_METADATA/__study__`。覆盖登记核对不打开 GT、历史 final matches 或 role payload；没有凭 caller callback、布尔值、schema/hash/HMAC 制造部署权限。role publisher 未安装时继续拒绝，实际目录对象的创建、挂载和逐 role 发布不属于此单元的完成事实。

本轮独立 SPEC 先发现公开 schema/hash/closed/receipts 缺 exact-type/reference 先行的 P2，已补统一 gate。独立 QUALITY 再发现 retained mapping 与公开 entry 共用对象导致 plain 字段和 key 同步漂移的 P2，已补公开前独立原五标量快照、完整原 key-set 与固定 derived alias 核对；读取前、consumer 后和 native require_registered 使用同一连续性检查。两次修补均保留独立原清理引用和原 raw primary/secondary 失败保存，不恢复漂移公开字段、不扩大 private-global 篡改模型。

原始资源引用在第一次 acquisition 前固定；每次原返回/异常先保存再做类型、hash、报告。安装返回前所有临时 scope 必须关闭且失败 buffer 健康，失败时不注册 owner，不留下需虚构 terminal 回执的常驻 FD。原 consumer primary 与关闭 secondary、runner 装配 map-close 与 bootstrap-burn 的各次实际失败继续独立尝试与保存。新 reader 不引入 CDLL(None)/helper 装载；这只避免该新路径引入加载，不证明整个解释器/stdlib/PE/ELF/transitive readonly 边界。

最终独立 SPEC / QUALITY 结果、五文件 pins 与主审工作集核对见下；这些均限定 SOURCE_ONLY，不签完整 review ID、runtime authority 或实验 PASS。

静态调用链另确认：完整注册逐项调用 whole-map 连续性 gate，复杂度为 O(K×M)，本次还逐 entry 导出固定 alias。上一版已逐次扫整个 map，此处不包装为新回归；实际时间、峰值和费用未执行取得，不能计零或据局部源码复审宣称预算内可完成。原绝对 clock、容量上界和失败拒绝保持，真实生产装配仍需关闭这一费用缺口。

最终独立 SPEC：NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY；最终独立 QUALITY：LIMITED_QUALITY_NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY。复审者均只读核实实际五文件 pins 与隔离 stdlib AST，不运行功能、测试体、project import、native/helper/WSL/GT/Stage，不写源码、文档或 Git。两项均没有正式 full-review ID；完整 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 保持 FAIL。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| `linux_gt_history.py` | 135672 / 2461 | `ff347728f96ecca83000b41ad0080ee20531472a0585b2dacc8709b158a2b781` |
| `linux_native_path_map.py` | 41431 / 749 | `d6238ac9d094c41df5201afefcd0787135d45526f97e7f769851cd45d688684e` |
| `path_map.py` | 34251 / 775 | `325df812111f88f78ea79cf3438bf553c1ea20194701df4e2f20a8fed41704ea` |
| `production_metadata.py` | 90339 / 1718 | `bbf83c9ba1c5da7451b86cfd1d13ca8357023503703ce7d9dacff64060859a48` |
| `production_runner.py` | 24343 / 421 | `bfe984b7014467b6ab805734b364efe94cae58fcf7c7c2fc026fc8aa9eb97a68` |

主审限定核对：93 文件 / 2,641,175 logical bytes；63 份生产 Python AST 可解析、4 份 native C/H 仅文本/hash、26 份测试仅 hash。相对本轮恢复基线，只改上述五份生产源码及 `windows_non_e_monitor.py`（52829B，SHA256 `63bf3e04fa699e5bd7132f089c2c8e845417873e4f0d4c1c39169d734e5cb2eb`）；没有删除工作集文件。最终第二个 P2 修补只改 private reader，其余92项不变。原 staged/untracked/dirty 工作保留，index95行 SHA256 `2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e` 不变；source trace mapping `aec946187451f8372e879e5c6b8e3684586eb6fb36a9a9da3295e8b966b7ce6c`（UTF8 compact JSON sorted keys，records[path,bytes,sha256,role]按relative path排序）；test hash mapping `03276135ecde7218157839fb6d9973ac15bb095654eee44a8f984b5aab1618c5`。这是源码追踪，不能称完整 source/runtime 冻结或测试通过。

本轮不创建正式 image/volume/study/ledger/lock，不编译、链接、装载或调用 native helper，不启动 WSL/生产组件/Stage，也不读取 GT payload。native C/H、历史 matched-GT/异常修补、原授权卡/prompt 和 Route3 状态保留。

### 2026-10-09 完整 A+B 最小条件卡（本轮收尾更新一次）

**APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。** 当前准备视图仍 PREPARED_UNREVIEWED，`FROZEN_ADMISSION=None`，Stage A/B 均未合法运行，路线二无合法结果。负责人完整续行意图与具体资源数值绑定已记录，不能替代可消费的合法准入。

| 项 | 已确认或已实现（区分源码与实际事实） | 仍缺的真实条件 |
|---:|---|---|
| 1 | 原准备 metadata 已核为 PREPARED_UNREVIEWED；负责人已授权继续补齐并表达完成后执行的意图，原授权卡保持不改。 | 仍须同一套完整可安装 runner、实际部署/身份/费用、完整正式复审和可消费的 FrozenAdmission。FAIL-001 仍为 FAIL，A+B 准入尚未闭合。 |
| 2 | 科学变量保持：固定 saved scores、26D、阈值 .10/.25/.50，仅比较严格交叠与 300 秒候选间隙；decoder 600 秒/min180、matcher 和五折不变。 | 105 个 reference role 的真实复现、完整记录/窗口/来源身份，以及现版完整 nested 跨 OS 等价仍未取得。旧 PARTIAL_MATCH_ONLY 不覆盖现版。 |
| 3 | protected metadata-v2 FD、固定 native phase 事务，以及此次 early metadata 目录 owner、同 FD reader、compact map-v2 与固定 factory 为 SOURCE 实现；最终独立限定 SPEC/QUALITY 均无剩余范围 P1/P2，SOURCE_ONLY，不签正式 full-review ID 或实验准入。 | 实际逐 role 目录 publisher/reader、全部 backing 创建/删除、完整 nested 生产者和 runtime 安装仍缺。此次 early factory 仅观察并读取已存在 metadata，不能创建部署对象。 完整注册逐项覆盖检查的 whole-map 扫描费用尚无实际证据，不可计零。 |
| 4 | 105+105、25 次 fit 尝试/25 次 predict/65 次 decode、20 次 GT-backed 加第 21 次 GT-free 归并、pooled GT reads=0 合同保持；D_A=2GiB 为 strict capacity V2。 | 唯一实际 ledger 和强制执行、Stage A 实得 N/M/S/B、合法 Stage B 投影、同一 image 2→4GiB 的部署事实未取得。scratch、13-wheel、历史合成均非准入 PASS。 |
| 5 | Stage B 已分别报告 control/treatment 最终 matched-GT 的新增/丢失与候选覆盖变化；once key 和 fixed phase 为源码进展。 | 历史 A2-004 合法 final matched-pairs 来源、五个只读字段隔离投影、实际 canonical GT/commitment 及逐 role/phase 授权撤销尚未闭合；本轮未读取 GT payload。 |
| 6 | Windows 宿主所有者可信，继续 WSL2/Ubuntu22.04/glibc2.35；spawn/pidfd/wait/reap/status、UID/namespace/IPC 的已有源码结论保留。 | 专用目标实际 GUID/SID/UID/namespace/IPC、全部 worker 写路径、原生支持和正常/异常情况下的内核事实尚未证明。源码不替代部署身份。 |
| 7 | E 准备预留30GiB，以及创建正式 image 前同一 invocation 核 guest FS 与 VHDX 实际实体 Windows 卷分别至少8GiB的决定保持；carrier 仅另须增长和收尾 reserve。 | 专用 creator/format/import/register/native实体硬上限，三层 actual usable/allocated baseline/header/headroom/余额和 backing 创建删除历史仍缺。01:37:55Z只读盘点时专用目标与 prep worker 不存在。 |
| 8 | Stage A/总/累计 fit=1200/3600/900秒均含60秒收尾；C=min(4GiB,floor(3×首次原生启动可用RAM/5))、LimitAS=C/2、swap0、CPU200%、TasksMax2含controller；整任务RAM16GiB/VRAM8GiB保持。 | 实际 VM 应用8GB配置、pre-birth M0/原时钟、cgroup/AS/CPU/线程-task限制、GPU边界、整任务峰值/费用未证。Job commit/process count不能代替RSS/tasks或VM退出。 |
| 9 | 负责人已绑定E30=24GiB carrier含20GiB guest+external E6GiB，guest入场baseline≤8GiB；guest控制64MiB/外部E host控制16MiB内计；准备+编译ABI合计4GiB/200%/4tasks/1800秒，外部scope512MiB/100%/4tasks/6000秒，两者均含60秒收尾；现版对称atol1e-12/rtol1e-10和离散exact。 | 这些原 scope 的实际执行方法、VM/kernel/services全部归属、控制/编译ABI/历史及未来准备/外部费用、峰值以及三层实际 baseline/headroom/余额仍为 UNKNOWN。数值绑定不等于实测或实验准入。 |
| 10 | nonE=512MiB监控预算；384MiB可见增长停止新增工作，128MiB仅为名义收尾规划；负责人接受上界未知的在途超额。C/D原生监控源码限定SPEC/QUALITY无剩余范围P1/P2。 | 全任务固定 observer、全部 Windows 写入者、allocated bytes归属与费用未闭合。共享 pagefile 曾增2072MiB后回落不代表费用为零；PS observer实见28–29线程，不满足4tasks；128MiB不是实体reserve或超额上界。 |
| 11 | 受限 ELF/40-byte ABI 准备检查和4个native C/H源保留；此次 early reader 用stdlib FD/proc事实，不新增 CDLL/helper 装载。 | 4个C/H尚未compile/link/load/call；实际readonly解释器/stdlib/project/PE/ELF/transitive依赖边界须在任何constructor/import/dlopen前证明。Linux pre-Python/pre-spawn t0/M0、原Windows QPC认证transport与host kill仍缺。 |
| 12 | 异常保存及原owned FD/pidfd/READY/status/wait/reap/once-close等局部源码结论保留；新单元失败清理使用独立原资源引用。 | 全部 backing 创建删除、唯一逐role/phase GT授权撤销、实际 OOM/crash/quarantine，terminal后签名close/exit join、原始cgroup清场/VM服务退出、最终durable外部QPC验收仍缺。 |
| 13 | 本轮仅限组件独立SPEC/QUALITY及AST/hash；工作集用于源码追踪，原index/auth/native/test内容保持。 | 完整可安装OS/native/readonly/预算/失败/退出/现版nested等价的正式review ID，以及source-runtime-input-rolemap-launcher/worker/controller-protocol-budget完整冻结未闭合。完整FAIL-001维持。 |
| 14 | 准备终点、实验终点、质量成功终点分开；pooledF1≥.66、至少3/5折F1≥.66、每折long-FP≤.25、start/end MAE≤900秒并报告真实matched-GT增减。Route3 v1-003仍合法COMPLETE/四门FAIL。 | Stage A/B均未合法运行，无路线二合法科学结果。须按预声明早停或完成一次五折Stage B；不得重跑Route3或在合法Route2结果前自动启动三个架构方向验证。 |

准备终点要求同一套完整可安装 runner、实际资源与身份证据、完整独立复审及具体可消费 A+B 授权全部闭合；实验终点为预声明合法早停或一次五折 Stage B；`COMPLETE` 与质量门通过分别判断。不能把局部复核闭合描述为路线二完整实现或实验获准；也不能把完整缺口概括成“只缺管理员权限”。

### 2026-10-09 接续完整输入注册的受限批量覆盖实现

上一单元 five-source early metadata owner/reader 的独立 SPEC/QUALITY 已限定 SOURCE_ONLY 无剩余范围P1/P2，完整A+B卡已在原review本轮收尾更新一次，完整FAIL及运行拒绝仍保持。接续选择一个实际启动链组件：`RoleRegisteredPreparedInputs.__init__` 目前对全部role/cache逐项调用whole-map连续性gate，源码可确认O(K×M)；不得以未知实测费用关闭预算缺口。

实施仅限定 `path_map.py`、`linux_native_path_map.py`、`inputs.py`：加入只核metadata覆盖的固定受限batch入口，把输入注册已存在的同一身份序列一次提交；native批量前后仍核完整原keys/独立字段快照/固定derivedalias，以原retained不可变keys检查每项，先exact tuple/string类型，继承原map大小上界、不扩大原预算。每段检查原绝对clock/PID/thread/bootstrap/controller连续性，不返回中间权限、不授予IO、不触及GT或角色发布；legacy单项API和v1原语义保留。不能把该复杂度收敛称实际时间/峰值/费用已测或全生产可执行。保持注册顺序、重复项含义、savedscore科学变量及GT门。

一个实现者完成并停止写入后，独立SPEC再QUALITY静态复审；只有stdlib AST/hash，不新增/运行测试、project import、native编译/装载/helper/WSL/GT/生产/Stage，不创建正式image/volume/study/ledger/lock，不操作Git或无关文件。讨论/结果仅追加原三文档，原授权卡/prompt不改。最终SOURCE_ONLY结论和实际pins另追加；既有完整14项卡仍是当前准入缺项依据，数值已绑定、真实部署/运行/费用/完整正式review未知。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、FAIL-001/ APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

### 2026-10-09 完整输入注册批量覆盖源码与限定复审收尾

启动注册原逐项require_registered会每项重扫整个map；此单元在 `inputs.py` 保留原registration/file顺序和重复项，仅原issued native map将同一四字段身份序列一次交给受限batch；legacy/v1仍使用原逐项检查。`path_map.py`保持原单项API，增加metadata-only batch dispatch；`linux_native_path_map.py`在原 owner 内完成全部 plain tuple/string、继承原map条目数的批大小、原不可变key-set查找与分段原clock/PID/thread/bootstrap/controller核对。批量前后仍执行完整key-set、独立五标量原快照、固定alias连续性检查，任何不一致继续拒绝；不返回中间结果或授予IO/role/GT权限，不引入callback或可执行generator。SHA小写规范化、记录顺序与重复项含义、legacy单项/v1路径保持。

原native覆盖路径的SOURCE复杂度收敛为O(K+M)，并增加O(K)批量行存储；分段_identity不重扫map。实际耗时、内存峰值、费用和预算内可执行性均未测，保持UNKNOWN，不计零。原clock/额度/cap以及生产部署/readonly/QPC/terminal等拒绝门不改变，不能由batch核对制造权限或合法结果。

最终独立SPEC/QUALITY状态与当前三文件pins在实际复审结束后填写；只允许stdlibAST/hash，无测试、project import、native/helper/WSL/GT/Stage或正式对象。本单元原14项条件卡不重复新建/更新另一整卡，仅追加其第3/9/13项的源码进展，实际费用与完整准入缺项维持。

独立SPEC首轮确认1个P2：用总行数限制为unique map key数，会让legacy/v1拒绝原逐项能通过的合法重复文件身份；cache record key唯一不等于文件四字段身份唯一。已仅修 `inputs.py`，读取path_mappings模块当前 `_NATIVE_CONTEXT` 以is选择native优化路径，legacy/plain恢复原逐项loop，不缓存初始None或用schema/布尔值替代原native身份。native批量仍继承M行界、不去重；重复项只在该界内接受，完整实际v2输入是否满足该界仍须准备/冻结实证，不以此补丁自动保证。

原单项API、IO、rolelease、rawfailure/cleanup/onceclose函数的before/current AST摘要由实现者保存的dirty pre-batch全文计算（不是HEAD/main）；独立复审者重算当前对应摘要比对报告值。源段摘要只作源码追踪，不是原生事实或完整runtime冻结。

最终独立SPEC复核：NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY；新独立QUALITY：NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY。两者均核实际三源pins与隔离stdlibAST；QUALITY另以AST比较native身份收集与legacy循环的角色、文件顺序一致。legacy原outerFor当前摘要独立重算为 `5b3f42c7e303099b7025dbfe6e225dc0b77fe183cb4bd8343be512fbd5382e89`，匹配saved-dirty before报告。原11个函数current摘要重算匹配报告before，不夸大独立baseline可见性。无正式full-review ID/full PASS/运行authority。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| `inputs.py` | 25365 / 545 | `ad0d5947e476975e5feaedbd2743088de07386c5eb74c1019d48b3129c96dc7c` |
| `linux_native_path_map.py` | 42629 / 773 | `a27ab491c278f021e0a5929b3dd6df12458911791b3a8abea48a6f168fd4360d` |
| `path_map.py` | 35528 / 796 | `db5661ef50af59d44b0cf3acc58daceca44da71bb93a7ebf9842982e397d5620` |

主审当前工作集93文件 / 2,644,404 logical bytes，63生产AST可解析、4native C/H仅文本/hash、26测试仅hash；SOURCE trace mapping `b7e36fce4e368dc87019d9641bb277023502708f7015fc212238521b51a9bb04`，序列化同前UTF8 compact JSON sorted keys/relative paths。测试hash mapping `03276135ecde7218157839fb6d9973ac15bb095654eee44a8f984b5aab1618c5`，index95行hash `2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e`不变。相对本轮恢复基线仅7份生产源码改变（inputs、linux_gt_history、linux_native_path_map、path_map、production_metadata、production_runner、windows_non_e_monitor），不存在删除或native/test/source科学核心改动；原dirty/staged/untracked保留，无commit/stage/reset。源码追踪不称完整source/runtime冻结。

原完整14项 A+B 最小条件卡仍见本review“2026-10-09 完整 A+B 最小条件卡（本轮收尾更新一次）”；本追加仅补该卡第3/9/13项的源码进展。前节O(K×M)的完整输入注册路径已由原native受限batch收敛为SOURCE O(K+M)，实际费用/峰值/耗时/数据K≤M仍UNKNOWN，真实部署、全部role/backing历史/授权撤销、原QPC/prePythonclock、readonly加载前闭包、完整runtime/三层baseline及预算执行方法、终态关闭后签名join/清场/finaldurable外墙钟和完整正式复审未闭合。原 source/runtime/input/rolemap/launcher-worker-controller/protocol/budget完整冻结仍缺。

PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、`route2-ab-full-implementation-review-2026-09-29-FAIL-001`仍FAIL；APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。Stage A/B未合法运行，路线二无合法结论。本轮无测试、project import、native/helper/WSL/GT/生产/Stage/正式对象；原授权卡/prompt、StageB matched-GT与execution双异常修補的原源hash、Route3 v1-003合法COMPLETE/四门FAIL保留，不重跑或启动三架构方向。全部绑定数值仍按负责人前节回复，不重新询问。

### 2026-10-10 原 native GT broker 接续 directory-v2 metadata 的生产源码计划

负责人要求继续补齐原六类启动缺口；已有续行授权、资源数值及 nonE 监控在途超额决定沿用，不重复申请。实际只读盘点仍未见 E:/Route2Dedicated，当前主 token 未提升；这不是完整缺口总结，也不据此停止可独立推进的源码工作。当前原三份文档最新状态及 source pins 已核，原 disk/cgroup/wall JSON 与 Linux 依赖证据的 hash 和准备范围保留。

逐 role directory publisher 的 target 已固定，但 source substrate、creator、完整创建删除历史尚缺；现 study/.worker 是 worker scratch/log，不是不可变 role input。其累计 4096 inode/path 历史界、单链接要求及 256 目录扫描界不能直接承接单遍 19894 alias 或最大 250+7 文件目录，不能改字段或扩 cap 冒充部署闭合。这个已有实现缺口维持，后续 publisher 必须沿完整预算和原生对象另行闭合。

本次先闭合一条真实启动调用断点：linux_gt_history._registry 的两份非 GT payload 登记 metadata 仍走 _read_metadata/_source/registered_file_binds 的 flat leaf resolver，不能消费 compact map-v2；installer 另建 plain map 也不具有原 early owner 的 issued-map 身份。范围仅 linux_native_path_map.py 与 linux_gt_history.py。

1. 原 fixed hook 仅从 healthy original early owner 取得同 guard/controller/startup binding/ledger/PID-thread/绝对 clock/原 protected manifest 的 issued map；同 guard 原 owner 漂移、failed、closed、active 或原 manifest 不一致直接拒绝，不 fallback。原 owner 缺失时仅保留原 v1 from_bytes，plain v2 继续拒绝。不接 caller map/path resolver/callback、HMAC/schema/布尔 authority。
2. 仅固定 gt-view-registry.json、gt-role-scopes.json 的 preflight_metadata/__study__ 走原 native directory 同 FD reader。原 4MiB GT registration metadata cap 在 resource.before.st_size 后、任何 payload pread/hash 前检查；普通 metadata 原 cap 保持，不增加 caller 可选 max。duplicate-key 与原 JSON/schema 解析须在 owned context 内，成功结果只在后核、全部 once-close 和 failure buffer 健康后返回。
3. raw read/parse primary 与 postconsumer/stream/FD/外层 scope close 的实际 secondary 独立强留；原 PID/thread before-consume、once-close、失败不重试/不重发保持。110 GT O_PATH 登记、GT grant/revoke、helper、ledger、worker history、registered_file_binds 和科学合同不改。
4. 单实现者停止写入后 fresh 独立 SPEC，再 fresh QUALITY；主审隔离 stdlib AST/hash 及实际修改范围核对。无新增/运行 tests、test body、project import、native compile/link/load/call、WSL、GT payload、生产/Stage 或正式 image/volume/study/ledger/lock；无 Git mutation、删除或无关覆盖。讨论只追加原三份文档，原授权卡/prompt 不改，不新建交接包。
5. SOURCE 断点闭合不宣称 actual broker 已安装或运行；native role publisher、完整 nested/readonly/QPC/prebirth/terminal、专用实体与三层实际 baseline/预算方法和完整正式 review 仍缺。完整 A+B 最小条件卡在本轮最终收尾仅更新一次。

PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍 FAIL；APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法 Stage A/B 或路线二结果。Route3 v1-003 合法 COMPLETE/四门 FAIL，不重跑，三架构方向不启动。

### 2026-10-10 原 native GT broker 接续 directory-v2 metadata 的实现与限定复审收尾

本单元实际修改 linux_native_path_map.py 和 linux_gt_history.py，接续原 execution.install_original_gt_broker 调用中的两份登记 metadata 消费断点。原 installer 不再为 directory-v2 另建 plain map；固定 getter 从原 healthy early owner 取得同一 issued map，核同 guard/controller/startup binding/ledger/PID-thread、原绝对 clock、bootstrap/start/frozen/protected metadata 和原 manifest bytes 对象。原 owner 失败、未完、漂移、active 或 closed 直接拒绝；只有原 owner 缺失时保留原 legacy-v1 from_bytes，plain-v2 继续拒绝。未接 caller map、resolver、callback 或新 authority 字段。

固定 reader 仅消费 gt-view-registry.json 与 gt-role-scopes.json 的 preflight_metadata/__study__ 身份。共享 SAME-FD engine 在同一 acquired resource.before.st_size 后、任何该 payload pread/hash 前检查原 4MiB 严格上限；普通 metadata 的原公开参数与 16MiB 上限、joint 48MiB read 上界保持。duplicate-key JSON、顶层及嵌套 graph/view schema 检查均在 owned context 内；cross-record、110 项 GT O_PATH 登记和实际 GT 权力检查仍留在原 broker。结果仅在后核实际 frame/kernel/mount/原身份及全部 once-close/failure buffer 健康后返回。

两份原 resource/scope 由 installing broker 独立强持有。raw read/parse primary 在后续检查前保存；postconsumer、stream、FD 和外层 qscope cleanup 的实际 secondary 分别保留。外层 normal/failed cleanup 及 fallback 在消费 FD 前核原 PID/thread，先 pop 再 close，不重新发号、不重试或以布尔值宣称清场。原 _live、_source、_read_metadata、_record_worker_backing、_libc、grant、revoke 和 _registry 下游检查保持原 AST。

fresh 独立 SPEC 首轮发现 1 个 scoped P2：nested graph/view schema 原仍在 reader 退出后检查。已补入同一 FD consumer context，不删除原 downstream 检查。最终同一 SPEC 重核与 fresh 独立 QUALITY 均为 NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY；无正式 full-review ID、full PASS 或实验准入。SPEC 通过内存反向重构核此次修补仅固定 reader AST 改变；QUALITY 和主审独立重算当前七个 protected AST、公开 reader args 和 downstream 摘要，与实现者 saved-dirty before 报告一致，不夸大其访问了修改前全文。downstream 摘要为 e0592fc0687d5bc33dd2b88231543e7af1ca98df45943457b2457e0ee533fde1；公开 args 摘要为 822d3bef5f4cfefd23c82923af507dffd93238606bc439e4c1eabfc79c5963e9。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| linux_native_path_map.py | 57790 / 1015 | c6b4c57437f87b5e8b695a747467100df2094d49240e6a1da1ecf4e104994bd2 |
| linux_gt_history.py | 138428 / 2496 | 1ca884d50b7e700c0fde4d30b82b755b26539f0b0008d832d6c982bd6988b143 |

主审隔离 Python3.14.6 -I -S -B stdlib AST/hash 核 101 个跟踪项；其中工作集93文件 / 2,662,321 logical bytes：63份生产Python AST可解析、4份native C/H仅text/hash、26份测试仅hash。相对本轮恢复基线，仅两份上述源码和原三文档追加发生变化；工作集无新增或删除，原 staged/untracked/dirty 保留。native、tests、requirements、原授权卡/prompt、stage_b.py matched-GT 和 execution.py 双异常修补的 hash 均不变；原 git index raw bytes SHA256 b2ef45b682ab16128e1effc27fcce7180028919967ced9b43e07c37dd7003bea 保持。这是源码追踪，不是完整 source/runtime 冻结或测试通过。

本轮只读部署盘点未见 E:/Route2Dedicated，当前主 token 未提升，.wslconfig 存在不等于 VM 实际应用配置。原 disk/cgroup/wall 和 Linux 依赖准备证据及 PREPARED_UNREVIEWED metadata 已复核；均不能代替实际专用目标、三层 baseline/headroom 或启动时费用。4个native C/H未 compile/link/load/call；没有测试、project import、WSL/helper/生产/GT payload/Stage或正式image-volume-study-ledger-lock，无Git mutation、删除、原授权卡改写或新交接包。

### 2026-10-10 完整 A+B 最小条件卡（本轮收尾更新一次）

**APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。** 准备视图仍 PREPARED_UNREVIEWED，FROZEN_ADMISSION=None；完整 route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍 FAIL。负责人续行与最终执行意图、具体数值绑定及 nonE 在途超额决定沿用，不重复申请；完整实际条件未闭合，Stage A/B 未合法运行，路线二无合法结果。

| 项 | 已确认或已实现（区分 SOURCE 与实际事实） | 仍缺的真实条件 |
|---:|---|---|
| 1 | 原准备视图核为 PREPARED_UNREVIEWED；负责人已授权继续补齐并表达条件满足后执行意图，原授权申请卡保持不改。 | 同一完整可安装 runner、真实部署/身份/费用、完整正式独立复审及可消费 FrozenAdmission 尚未闭合；不能以宽泛访问权限或局部复审制造实验准入。 |
| 2 | 固定 saved scores、26D、阈值 .10/.25/.50；仅严格正时间交叠对比300秒候选间隙；decoder600秒/min180、matcher及五折不变。 | 105 reference role真实复现、完整记录/窗口/来源身份与現版完整 nested 跨 OS 等价未取得；旧 PARTIAL_MATCH_ONLY 不覆盖现版。参考复现是合法 Stage A 的工作，不以无授权运行提前取得。 |
| 3 | early metadata owner/reader、compact-v2 factory、metadata-only batch及本次原GT broker两leaf消费接续已为 SOURCE；此次最终限定 SPEC/QUALITY 均无剩余范围P1/P2。 | 逐role目录 publisher/source backing布局与creator、完整创建删除历史、实际readonly role reader、完整nested生产者及runtime安装仍缺；本组件仅消费已存在metadata，不创建原生对象。 |
| 4 | 105+105、25次fit尝试/25次predict/65次decode、20次GT-backed加第21次GT-free归并、pooled GT reads=0合同保持；D_A=2GiB strict capacity V2。 | 唯一实际ledger与强制执行、Stage A实得N/M/S/B、合法Stage B投影及同一image2→4GiB的实际部署尚缺；历史scratch、13-wheel、合成和局部静态复核不算准入PASS。 |
| 5 | Stage B源码分别报告control/treatment最终matched-GT新增/丢失与候选覆盖增减；相关原hash保持。 | 历史A2-004合法final matched-pairs来源、五个只读字段隔离投影、实际canonical GT/commitment与逐role/phase授权撤销尚未闭合；本轮未读取GT payload。 |
| 6 | Windows宿主所有者可信，继续WSL2/Ubuntu22.04/glibc2.35；已有spawn/pidfd/wait/reap/status、UID/namespace/IPC局部源码结论继承。 | 专用目标实际GUID/SID/UID/namespace/IPC、所有worker写路径、原生支持及正常/异常内核事实仍缺。现study/.worker是可写scratch/log；4096累计身份界、256目录界和nlink=1规则不能直接承接19894 alias/max250+7的immutable role substrate。 |
| 7 | E准备预留30GiB；正式image前同一invocation核guest FS与VHDX实际Windows实体卷分别至少8GiB；carrier无第三项8GiB要求，但须独立增长与收尾reserve。 | E专用creator/format/import/register和原生实体硬上限、三层actual usable/allocated baseline/header/headroom/余额、backing创建删除证据仍缺；本轮只读未见专用目标，不可用共享WSL全局增量代替per-study硬边界。 |
| 8 | Stage A/总/累计fit=1200/3600/900秒均含60秒收尾；C=min(4GiB,floor(3×首次原生启动可用RAM/5))、LimitAS=C/2、swap0、CPU200%、TasksMax2含controller；整任务RAM16GiB/VRAM8GiB。 | pre-birth原M0/t0、实际VM8GB配置、cgroup/AS/CPU/thread-task/GPU边界、全部归属费用与峰值未证明；Job commit/process count不等于RSS/tasks或VM退出。 |
| 9 | E30=carrier24GiB含guest20GiB+external E6GiB，guest入场baseline≤8GiB；guest控制64MiB/仅external E host控制16MiB内计；准备+compile/ABI合计4GiB/200%/4tasks/1800秒，external512MiB/100%/4tasks/6000秒，均含60秒收尾；现版对称atol1e-12/rtol1e-10及离散exact已绑定。 | 各原scope实际执行方法、VM/kernel/services全部归属、控制/compile-ABI/历史及未来准备/observer-helper-launcher-bridge成本、峰值及三层实际baseline/headroom/余额均UNKNOWN；本次FD/hash/parse/后核存储与耗时亦不可计零。 |
| 10 | nonE512MiB监控预算；384MiB可见增长停止新增工作、128MiB仅名义收尾规划；负责人接受上界UNKNOWN的在途超额，原监控SOURCE结论保留。 | 全任务固定observer、全部Windows写入者、allocated bytes归属与费用尚缺；旧PS observer28–29线程不能满足4tasks；共享pagefile增长后回落非零费用，128MiB非实体reserve或超额上界。 |
| 11 | 受限ELF/40-byte ABI准备检查与4个native C/H源保留；本单元仅原stdlib/proc/FD读取，不新增helper/CDLL装载。 | native仍未compile/link/load/call；须在任何constructor/import/dlopen前证明实际readonly解释器/stdlib/project/PE/ELF/transitive依赖边界；Linux pre-Python/pre-spawn原clock、Windows原QPC认证transport/启动连续性/host kill仍缺。 |
| 12 | 原失败保存、owned FD/pidfd/READY/status/wait/reap/once-close源码结论继承；本次新增metadata原primary与实际secondary及outer cleanup身份检查。 | 全部backing创建删除、唯一逐role/phase GT撤销、真实OOM/crash/quarantine、terminal关闭后签名close/exit join、raw cgroup清场/VM服务退出与最终durable外部QPC验收仍缺；关闭布尔值/hash/HMAC不能替代原生事实。 |
| 13 | 本轮独立限定SPEC/QUALITY及主审AST/hash闭合，只限两份源码；旧scope源码未改变则继承其结论，无正式full ID。 | 完整可安装OS/native/readonly/预算/失败/退出/现版nested等价正式review ID与source-runtime-input-rolemap-launcher-worker-controller-protocol-budget完整冻结仍缺；FAIL-001维持。 |
| 14 | 准备、实验、质量成功终点分开：pooledF1≥.66、至少3/5折F1≥.66、每折long-FP≤.25、start/end MAE≤900秒且报告真实matched-GT增减。Route3 v1-003合法COMPLETE/四门FAIL，gap0覆盖保留。 | 无合法路线二结果；须合法预声明早停或完成一次五折Stage B，COMPLETE不等于质量门通过。Route3不重跑，合法Route2结果前不自动启动三架构方向。 |

下一优先组件是拥有固定source substrate、原生create/delete历史及不可写别名事实的逐role publisher，不能复用.worker或仅补schema/回调绕过缺口。现 production_runner nested/QPC、path_map role、Linux installation/startup和Windows readonly preworker等原拒绝入口保持；缺失actual producer、实际部署对象或预算事实继续UNKNOWN/拒绝。本单元不等于完整路线二实现或获准实验，完整缺口不能概括成只缺管理员权限。

### 2026-10-10 adaptive-workflow 工程审阅与逐 role producer 止损判断

本追加继承前节最新状态，不改原授权 Prompt、原授权申请卡及任何已绑定决定。负责人已授权继续补齐，并表达实际条件满足后执行的意图；当前障碍是完整实际准入未闭合，不重复申请已作出的决定。

#### 路由、预检与证据层级

- capability_tags: machine-learning, data-contracts, evaluation, operating-system-isolation。
- loaded_profiles: Machine Learning；OS 部分使用 generic fallback，未加载 Embedded。
- critical_unknowns: immutable role source 的来源/creator/完整创建删除历史与不可写别名；专用部署/三层 baseline 与全部归属费用；pre-Python/pre-spawn 原时钟、QPC transport、加载前依赖闭包、最终退出与 full review。
- validation_order: 既有科学合同与合法基线 → SOURCE 调用链和 actual producer 可闭合性 → 完整部署/预算/加载/退出设计 → 未来获准的无科学数据取证及正式独立复审/冻结 → 合法 Stage A → 合法 Stage B 或预声明早停。本轮停在 SOURCE。
- workflow_path: RESEARCH。
- execution_mode: SUBAGENT；本轮实际 backend 为 collaboration.spawn_agent 加 exec_command。一个独立工程审阅者；一个唯一实现者做限定 producer 追踪，未获可独立闭合 SPEC，返回 BLOCKED 且零源码修改。没有伪造新的实现 SPEC/QUALITY PASS。
- budget/fallback: producer 追踪限定一个单元、最多两源、分配 8 分钟软预算，缺 source/creator 或须跨层设计即停止；工程审阅单独限域。历史 retry/hypothesis/review 总计 UNKNOWN，不因换 agent 重置；本轮新合法实验、运行测试、fit、GT payload 读取均为 0。后续 source 实施须一个实现者停止写入，再独立 SPEC、fresh QUALITY；两轮仍有范围 P1/P2 则重新因果审阅。
- telemetry: 未调用 skill 的 JSONL recorder；本轮只允许原三文档追加，未另选 telemetry 文件。以下人工 gate/escalation 记录不冒称 recorder 产物；token usage、历史总耗时及完整费用 UNKNOWN。

| Preflight 固定字段 | 当前判断 |
|---|---|
| Goal | 保持事件级 F1≥0.66 的最终深度学习目标，先取得唯一候选融合机制的合法证据。 |
| Success metrics | pooled F1≥0.66、至少3/5折F1≥0.66、每折long-FP≤0.25、start/end MAE≤900秒及真实最终matched-GT增减；合法COMPLETE与质量门通过分别判断。 |
| Constraints | 全部既有数据/角色/GT时序、WSL/Ubuntu/glibc、硬限/监控预算与调用上限沿用；当前仅源码、隔离stdlib AST/hash、静态复审及准许只读metadata。 |
| Prior art | 原09-10设计先树模型基线、后比较TCN/Transformer表示；原路线1标注合约审查及路线3既有结果是本地开发证据。Context7核对Python3.10 OS FD API和scikit-learn HGB/nested CV；未据文档推定本机能力。 |
| Baseline | 已保存合法A1 F1=0.585086、A2-004=0.623482、Route3 v1-003=0.5882352941；仅引用既有报告，不重新评价。Route2 UNKNOWN。 |
| Candidate approaches | 科学处理仍唯一严格正时长交叠，对照300秒间隙；执行层应先收敛实际部署和对象生命周期，再续组件实现。 |
| Critical assumptions | 完整runner能在既定预算内安装、启动、隔离、退出；真实role/phase substrate及加载闭包可合法提供。当前未证。 |
| Risks | 工程投入继续增长而未产生新的合法机制证据；41人重复开发；固定26D与保存分数不足以证明深度表示信息增量或官方泛化。 |
| Validation experiments | 本轮为SOURCE依赖追踪，合法Route2实验为0；未来105 reference复现是合法Stage A任务，不提前偷跑。 |
| Kill criteria | 不能在明确原owner/对象布局内选出真实生产组件时停止局部扩写；部署/预算/加载/退出闭环不能形成则继续阻塞并重审执行架构。未来科学早停仍按原声明。 |
| Recommendation | REDESIGN，仅针对实验执行架构的收敛；不撤回已绑定WSL/预算/科学协议，也不启动三个模型方向。 |
| Confidence | 对源码拒绝与缺实际producer判断高；对本机不可行、F1目标可达及模型架构优劣均不足，保持UNKNOWN。 |

#### 是否符合 best practice、是否偏离目标

单变量候选比较、participant隔离、Stage A零GT、nested内层选择、预声明早停、不可重用旧额度及COMPLETE/质量门分开，应保留。整体工程节奏不符合当前目标所需的有界验证：93文件/2,662,321 logical B 是上一单元SOURCE工作集，不是完整冻结或部署证据；多轮窄范围 SOURCE_ONLY 复审不能替代可安装的端到端执行链，更不能增加Route2性能证据。

当前科学目标未被改写，但交付路径已有偏移风险。Route2固定saved scores，重拟固定26D HGB verifier，只验证候选几何。HGB是梯度提升树，不能交付为深度学习模型。早期树基线是原设计的合理阶段，若长期停留在控制系统与固定树模型，仍未完成用户的深度学习目标。A2-004与0.66的距离及Route3负结果不构成深度模型不可行证明；未运行Route2也不能称该候选机制失败。

官方参考仅支持方法分类与评价原则：[HGB模型定义](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)、[nested CV选择偏差说明](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)、[Python3.10 OS FD能力](https://docs.python.org/3.10/library/os.html)。当前stable网页并非项目锁定1.7.2版本证明，本轮不迁移依赖。项目版本/ABI仍以原Linux lock/identity为准。

#### 为什么前 agent 一直停在 Stage A/B 前

| 实际调用断点 | 已有SOURCE事实 | 尚缺的生产者/事实 |
|---|---|---|
| production_runner.py:149–172，path_map.py:659–660 | fixed early metadata map和phase executor已有；native/v2 role lease与完整nested门仍直接拒绝。 | 原role backing来源、creator/create-delete历史、只读目录发布和同FD role reader；完整phase/runtime部署。 |
| linux_native_path_map.py:232–236、340–344、606–613、660–706 | 原owner只观察/读取已存在metadata目录；完整map登记不授予role IO。 | 观察器没有role对象创建/挂载/删除权限和历史，不能把目标路径当作已经存在的substrate。 |
| linux_phase_publication.py:1007–1039；native/route2_phase_spawn.c:316–323 | phase publisher检查既有immutable输入root/两个空placeholder；child固定chroot、UID/GID65534、单IPC及/runtime、/source入口。 | 固定phase树/解释器/stdlib/project/ELF/transitive加载闭包的原creator与加载前只读安装；已有spawn/pidfd/READY/wait/reap/status源码不能替代此事实。 |
| production_runner.py:175–178、223–224；linux_production_controller.py:54–55、57–85；route2_preimport_launcher.py:527 | 原QPC、installation/write-boundary与pre-Python起点仍明确拒绝；握手在原两记录journal边界。 | 原Windows QPC认证transport、pre-Python/pre-spawn t0/M0、原Linux启动连续性、全写路径和预算归属。 |
| 原完整条件卡第7–13项 | 预算值已绑定，synthetic原语/依赖准备及局部失败保存已有。 | 专用实体/三层actual baseline/硬界、全任务费用、terminal关闭后签名close/exit join、raw cgroup清场、VM服务退出、finaldurable外部QPC、完整正式review与冻结。 |

最新两份继承源码实测hash一致，沿用限定结论：linux_native_path_map.py=c6b4c57437f87b5e8b695a747467100df2094d49240e6a1da1ecf4e104994bd2；linux_gt_history.py=1ca884d50b7e700c0fde4d30b82b755b26539f0b0008d832d6c982bd6988b143。本轮没有对该已收尾组件返工。

原disk/cgroup/wall/QPC raw JSON和Linux依赖证据已只读重核hash，与原卡对应项一致。disk为scratch同FS 2→4 GiB/ENOSPC；cgroup明确hard_rss_or_worker_receipt_issued=false、supervisor_and_dependency_import_proven=false；旧wall明确durable_external_completion_event_proven=false。Windows QPC证据是合成服务的持久外锚，非正式runner transport。13-wheel lock/ABI/venv准备可行不等于完整readonly加载或现版nested数值等价。没有重跑这些探针。

当前只读Windows事实：E可见空闲1,003,427,061,760 B；E:/Route2Dedicated不存在，主token未提升；注册Ubuntu-22.04 WSL2 BasePath仍在C:。.wslconfig文本为memory=8GB/swap=0/processors=2/guiApplications=false，未调用WSL，实际VM配置UNKNOWN。这不能证明E+WSL不可行，也不能以历史RunAs成功替代当前身份；现共享C:发行版不证明E专用per-study部署。未知actual baseline/AllocationSize/VM-kernel-service费用不计零。

#### Circuit breaker 与唯一下一动作

- current goal: 合法Route2机制证据及最终高F1深度学习交付。
- evidence: 既有A1/A2/Route3合法结果、前节完整卡、上述源码拒绝与仅准备对象；本轮实现者限定追踪BLOCKED/零源码修改。
- failed hypotheses: 已关闭的固定候选/26D matching-aware目标变体；“局部metadata消费闭合即可启动”被现版直接拒绝否定；.worker作为immutable输入与现有历史/目录界冲突。未把这些SOURCE观察算作新的性能实验。
- experiments: 本轮合法Stage A/B=0；历史全部实验/同门假设/retry总数UNKNOWN。
- ruled-out causes: 当前不再缺预算数值决定；单独提权不解除missing producer；Route3旧INVALID不是OOM。
- remaining uncertainty: 真正部署/全部费用/完整nested等价/平台预算内可执行性及深度表示信息增量。
- current limiting factor: 实际对象creator、部署和全生命周期闭合。
- failure classification: 执行层ARCHITECTURE + IMPLEMENTATION；ENVIRONMENT及REQUIREMENT_INFEASIBLE未证。
- architecture still viable?: 科学机制尚待合法验证，WSL平台未被否定；现版完整执行路径不能运行。
- requirement still feasible?: UNKNOWN，未证明F1≥0.66或深度学习目标不可达。
- next action: redesign architecture。先收敛执行架构和真实substrate生命周期，暂停无独立可闭合SPEC的局部扩写；不回滚dirty源码、不重开模型方向。

下一可交付是完整部署/对象依赖表及一个可独立实施的真实creator/publisher SPEC：每个backing的精确source、创建者、承载FS/额度、创建/发布/撤销/删除的原owner与OS事实、失败时保留/清场、加载前readonly依赖及原始clock关联。source backing布局与费用当前UNKNOWN，本轮不凭猜测指定新目录或宣布该SPEC完成。仅有target、map、hash、schema或receipt不能关闭此门。

部署顺序应是：专用实体与全部费用/原硬限 → pre-Python准备/编译/ABI及readonly依赖闭包 → 原Windows/Linux时钟与startup join → 原controller下真实逐role source/publication及phase树/worker → 同invocation正常/失败撤销、reap、terminal/VM退出验收 → 完整正式独立复审和全冻结 → 唯一合法A+B。该顺序是SOURCE收敛要求，不授权本轮创建、编译或运行；没有证明存在不可消解的源码循环，也没有宣称所有后续源码都不能写。

路线1资料结论和路线3既有负证据沿用；路线3v1-003合法COMPLETE/四门FAIL不重跑。Route2合法早停或一次完整五折结论后，再依误差与合法信息讨论三个模型方向。现在不以工程BLOCKED推翻科学假设，不自动启动架构实验。

### 2026-10-10 完整 A+B 最小条件卡（adaptive 工程审阅本轮收尾仅更新一次）

**APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。** PREPARED_UNREVIEWED；FROZEN_ADMISSION=None；route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL。负责人续行和条件满足后执行的意图、全部绑定数值沿用；完整实际准入未闭合。Stage A/B均未合法运行，Route2无合法结果。本轮只有依赖追踪与审阅文档，没有新的源码组件完成事实。

| 项 | 已确认 / SOURCE / 本轮核对 | 仍缺的实际最小条件 |
|---:|---|---|
| 1 | source-registration及safe projection仍PREPARED_UNREVIEWED，正式review null；已有负责人续行意图，原授权申请卡/prompt不改。 | 同一完整可安装runner、真实身份/费用、完整正式独立复审与可消费FrozenAdmission；full FAIL未解除。 |
| 2 | 固定saved scores、模型、26D、threshold .10/.25/.50、decoder600秒/min180及matcher；唯一严格正时长交叠对比300秒间隙。 | 原105 reference合法Stage A复现、完整来源/窗口/记录身份与现版完整nested跨OS等价；旧PARTIAL_MATCH_ONLY不足。现版对称atol=1e-12、rtol=1e-10及离散完全一致，不提前运行取证。 |
| 3 | 原early metadata/batch/GT两leaf消费SOURCE及继承限定SPEC/QUALITY结论保留；两source hash一致，本轮零源码修改。 | 逐role publisher/source backing/creator/完整create-delete/不可写别名、同FD role reader、phase/runtime部署和完整nested生产者；本轮限定实现者BLOCKED，不以target/map/receipt替代producer。 |
| 4 | 105+105、25 fit attempts/25 predict/65 decode、20 GT-backed评价+第21次GT-free归并、pooled GT reads=0；D_A=2GiB strict capacity V2。 | 唯一actual ledger强制执行、Stage A实得N/M/S/B、合法Stage B投影与同image2→4GiB实际部署；非2+4累计。scratch/合成不算准入PASS。 |
| 5 | Stage B原control/treatment最终matched-GT新增/丢失源码保持，候选覆盖变化另列。 | 历史A2-004合法final matched-pairs来源、五个字段隔离投影、actual canonical GT/commitment及逐role/phase授权撤销；本轮不读GT payload。 |
| 6 | WSL2/Ubuntu22.04/glibc2.35、可信Windows owner及已有spawn/pidfd/READY/wait/reap/status/UID/namespace/IPC源码沿用。 | 专用actual GUID/SID/UID/namespace/IPC、worker全部写路径及正常/异常内核事实；.worker为可写scratch/log，4096历史/256scan/nlink=1不能承接19894 alias/max250+7不可变输入。 |
| 7 | E准备30GiB；formal image前同一invocation证明guest承载FS及VHDX实际Windows实体卷分别至少8GiB；carrier只须独立增长/收尾reserve，无第三8GiB要求。 | 专用creator/format/import/register、per-study实体硬界、三层actual usable/allocated baseline/header/headroom/余额与backing历史。当前E专用目标不存在，已注册发行版在C:；E可见free充足不代替专用闭合，也不证明本机不可行。 |
| 8 | Stage A/总/累计fit=1200/3600/900秒，60秒收尾内计；C=min(4GiB,floor(3×首次原生启动可用RAM/5))、LimitAS=C/2、swap0、CPU200%、TasksMax2含controller；whole RAM16GiB/VRAM8GiB；.wslconfig文本8GB/swap0/2CPU/gui=false。 | pre-birth原t0/M0、VM实际应用配置、cgroup/AS/CPU/tasks-threads/GPU硬界及全部费用/峰值；本轮未启动VM，实际配置UNKNOWN。 |
| 9 | E30=carrier24GiB含guest20GiB+external E6GiB，guest实际baseline≤8GiB；guest控制64MiB/仅external E的host控制16MiB内计。准备+compile/ABI合计RAM4GiB/CPU200%/4tasks-threads/1800秒；external observer/helper/launcher/bridge合计512MiB/100%/4tasks-threads/6000秒；均含60秒收尾。 | 原scope实际执行方法、VM/kernel/services、控制/编译ABI/历史未来准备/全部外部归属费用、峰值及三层actual baseline/余额；本轮SOURCE追踪/审阅费用未取得完整账目，不计零。 |
| 10 | nonE新增512MiB为MONITORED；384MiB可见增长停止新增工作、128MiB仅名义收尾规划；负责人接受在途超额上界UNKNOWN。 | fixed whole-task observer、全部Windows写入者与AllocationSize归属/费用；旧PS28–29线程不满足4tasks，pagefile增长回落非零，128MiB不是实体reserve或超额上界。 |
| 11 | 原13-wheel lock/ABI/venv准备及4个native C/H源、受限ELF/40-byte ABI SOURCE保持；原证据hash只读核对。 | 任何constructor/import/dlopen之前的实际readonly helper/解释器/stdlib/project/PE/ELF/native/transitive加载边界；原Windows QPC认证transport、Linux pre-Python/pre-spawn连续性与host kill。本轮不compile/link/load/call。 |
| 12 | 原失败primary/secondary、owned FD/pidfd/READY/status/wait/reap/once-close SOURCE继承；本轮无新backing或运行。 | 全backing create-delete、唯一逐role/phase GT撤销、真实OOM/crash/quarantine、terminal关闭后签名close/exit join、raw cgroup清场/VM服务退出与finaldurable外部QPC；假布尔/hash/HMAC不替代OS事实。 |
| 13 | 本轮独立工程审阅+唯一实现者限定SOURCE追踪；无源码delta，继承原限定双审；所有当前生产Python仅AST解析，测试只hash。 | 完整可安装OS/native/readonly/预算/失败/退出/现版nested等价正式独立review ID、source/runtime/input/rolemap/launcher-worker-controller/protocol/budget完整冻结；不把工程建议或doc审阅签成full PASS。 |
| 14 | 科学四门和matched-GT报告保持；Route3v1-003合法COMPLETE/四门FAIL，不重跑。原树基线是诊断阶段，最终深度学习目标保持。 | Route2须合法预声明早停或一次完整五折Stage B；COMPLETE与质量门通过分别报告。无合法Route2结果前不自动启动三个模型方向，也不把本轮工程BLOCKED当模型失败。 |

本轮执行架构收敛判断为REDESIGN；平台与模型可行性仍UNKNOWN。下一SOURCE交付是有明确actual source/creator/原owner/额度/创建删除/readonly加载/失败退出边界的部署与publisher SPEC，未形成该SPEC前停止局部防御扩写；不自动创建部署对象，不重新询问已绑定决定或变造授权。完整停止理由来自adaptive-workflow的circuit breaker（无信息增量/架构不确定先作新因果判断），并服从本轮仅源码/静态的用户边界。


### 2026-10-10 QUALITY P2 修订：独立预算的 SOURCE 收敛单元

fresh QUALITY 初审发现一个范围P2：前节“下一可交付”未绑定新的负责人、读取范围、预算与区分性验收；已结束的两源/8分钟预算不能沿用。本追加补齐该执行记录，不修改前文或本轮唯一完整A+B卡，也不签新的实现PASS。

- task: preparation-creator-to-role-substrate-source-trace；不同于已结束的early metadata两源追踪。
- causal hypothesis: 实际role/phase substrate creator可能已经存在于准备/部署实现，只是未接到原metadata/runner；若成立可选真实接线单元，若不存在则记录具体missing producer，停止伪接线。
- owner: /root 为本轮唯一追加作者和SOURCE追踪者（INLINE）；原实现者停止写入。全局主路线仍RESEARCH/SUBAGENT，本收敛单元执行backend为exec_command。
- bounded read scope: 仅以下8份生产source：windows_preparation_job.py、windows_control_identity.py、scripts/run_route2_candidate_overlap_wsl.py、scripts/route2_preimport_launcher.py、linux_initial_volume.py、linux_production_controller.py、linux_phase_publication.py、linux_native_path_map.py。可读取src/scripts文件名目录清单寻找对应原creator源文件；不读其他文件body、test body或科学payload。此前证据只引用不扩大独立核验范围。
- fresh budget: 从本轮实际UTC 2026-10-10 15:52:32时点开始，最多20分钟软预算、上述8份source、一个因果假设；不继承旧任务额度，不新增实验/运行测试。首次读取后的本记录继续约束剩余工作，实际完整费用/历史耗时仍UNKNOWN。
- distinguishing acceptance: 给出真实creator定义及生产调用链（若存在）、逐对象source/承载FS/原owner、创建/readonly发布/撤销/删除是否由实际OS操作形成，分别标SOURCE与actual runtime未知；若可在已明确原owner/布局内独立接线，应形成精确实施SPEC再由单实现者实施；否则记录具体行号、未实现入口和原拒绝顺序，报告BLOCKED，不把观察器/Job生命周期/正式study卷creator等同于role source creator。
- stop condition/fallback: 原creator实现未找到、exact role backing/费用未知或必须跨层设计才能接线即停止该单元；结果不能证明本机不可行。scope不足不扩大搜索、预算到期不重置假设；保持所有准入拒绝，不加cap/callback/hash/schema/布尔authority。
- prohibitions: 仍仅SOURCE/隔离stdlib AST/hash；不测试/project import/native/helper/WSL/GT/生产/Stage，不创建正式对象或改Git；讨论与结果只追加原三文档。source实施目标仍未完成，未来运行条件仍须真实取证。


### 2026-10-10 独立预算 SOURCE 收敛结果：实际准备 creator 未在限定范围找到

上节单元在UTC 2026-10-10 15:58:51 UTC收尾，早于原20分钟软预算终点；未重置预算、未增加假设、未扩大8源读取范围。一次因果假设的SOURCE追踪结果为BLOCKED，零实验、零SOURCE修改。本记录是人工填写的执行事实，不是JSONL recorder输出；工具/token费用和历史/未来准备费用仍UNKNOWN。

1. windows_preparation_job.py:250–256的原KernelOwner描述原生Job/process生命周期，不是已安装的worker binding或role/phase creator；固定命令在:293指向E:/Route2Dedicated/control/prep-worker.exe。_kernel_lifecycle（:743起）形成Job、clock/monitor、suspended birth、wait/exit的SOURCE路径，但_prepare_fixed_worker（:802–805）因readonly Windows worker/PE closure及pre-import installation/startup owner缺失无条件拒绝。src/scripts文件名目录清单未发现prep-worker实现文件；此名称清单不是对全机二进制或其他未读body的不存在证明。
2. windows_control_identity.py:181起的WindowsReadonlyExecutionLease持有并校验既有安装身份、readonly carrier及manifest/file身份，不创建不可变输入backing。scripts/run_route2_candidate_overlap_wsl.py现有command入口为preflight及synthetic probes，不能当作正式准备部署creator；route2_preimport_launcher.py:514–526明确原pre-Python/pre-spawn启动producer未实现，继续拒绝。
3. linux_initial_volume.py确实已有LinuxInitialVolumeCreator及OS操作SOURCE：create_image（:135起）以O_EXCL/O_NOFOLLOW创建并预分配image，后续loop/format/mount形成正式study容量卷路径。不能把它误写为“所有creator都不存在”。但create_stage_a_volume（:397起）在:403先要求held Windows execution boundary；该边界在:95–104仍无条件拒绝。linux_production_controller.py:234–245在调用它前还先核installation及host boundary。这是正式Stage A的2GiB study卷creator，不是E carrier/guest准备creator，更不是逐role/phase readonly source creator。
4. linux_native_path_map.py的原healthy early owner与linux_phase_publication.py的树核验继续观察既有metadata/source substrate；此限定范围没有发现可直接接线的实际role/phase原creator。既定目标/run/route2-input/roles/<SHA256(role_id)>的exact source backing布局、creator、创建/readonly发布/不可写别名/撤销/删除历史及其费用仍UNKNOWN。不得以Job生命周期、study卷creator、cap扩张或metadata authority替代。
5. 八源均经隔离stdlib AST解析和SHA256检查；没有project import或执行。本轮不得把SOURCE操作的存在写成actual runtime创建/安装/预算/退出证据。Linux既有study卷SOURCE有实现与其目前不能合法调用这两点同时成立。

验收的区分性结果：未支持“准备creator已有、只差接线”这一限定假设；继续补role publisher需要先明确跨层实际source/deployment authority，不能在本轮原owner与布局未知时独立实施。故未选出可合法独立闭合的生产修改单元，生产实施请求仍BLOCKED。该结论不是全repo/全机creator不存在、E+WSL不可行或F1目标不可行的证明。

本收敛单元已停止；下一判断仍是执行架构REDESIGN，保留原科学协议、WSL和已绑定额度。完整A+B最小条件卡只沿用本轮前节唯一14项更新，本追加没有第二张卡、正式full-review ID、实现PASS、冻结或实验放行；PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL及全部BLOCKED状态保持。后续独立SPEC与fresh QUALITY只审本轮文档事实和执行记录，不代替新组件实现双审。


### 2026-10-10 本轮限定静态双审收尾（文档与SOURCE事实）

- 顺序完成独立SPEC第二轮（/root/adaptive_spec_review）后，再完成fresh独立QUALITY第二轮（/root/adaptive_quality_review）；两者最终均为NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_REVIEW_ONLY。QUALITY初审的一个范围P2（下一任务无新预算/范围/验收）已由上节新单元记录及实际有限结果关闭。原单实现者已停止写入；本轮没有生产源码delta，故没有新组件SOURCE双审PASS或正式full-review ID。
- 继承两metadata reader hash完全一致；Stage B matched-GT与execution.finalize原修补hash不变。原授权prompt/card hash不变。隔离stdlib AST仅解析59个route2生产Python及4个相关script，共63项；没有测试、project import、native/WSL/helper/GT/Stage或部署对象创建。
- 收尾前404个既有监测文件（src/scripts/configs/requirements/docs/tests，测试仅hash）仅原三份文档变化，无增删，Git index SHA未变；三文档原始bytes前缀均保持。最终追加后再核同一集合和前缀。该有限元数据检查不是完整source/runtime/input/protocol/budget冻结。
- UTC 2026-10-10 16:04:09 UTC：工程审阅和两个有界追踪已结束；生产补齐请求仍BLOCKED。下一行动为执行架构REDESIGN，先收敛真实准备creator、role/phase不可变source、安装/原启动/退出及完整归属预算的可实施边界，保留已确认WSL、科学设计和资源决定；本机可行性及最终深度学习F1目标仍UNKNOWN。不是重新授权或自动启动任何模型方向。
- 唯一完整A+B最小条件卡沿用本轮前节14项更新；不生成第二卡。PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；Route2零合法运行/结果，Route3 v1-003合法COMPLETE/四门FAIL保持。


### 2026-10-10 执行架构收敛讨论，第1节：准备所有者、输入封存与生命周期（提案，未绑定）

负责人本轮授权进入架构讨论，继续沿用已确认WSL、预算及科学协议。此节记录讨论提案，不表示已同意新增布局、已部署或实验获准；不覆盖前节事实、原授权卡或完整A+B条件卡。PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

#### 新单元与固定preflight

- task: route2-execution-architecture-discussion-1；owner /root；workflow_path=RESEARCH，execution_mode=INLINE，actual backend=exec_command、Context7 resolve/query及request_user_input_async。当前边界高度耦合且待负责人给出host使用事实，不启动实现代理。本阶段仍保留后续单实现者停止写入→独立SPEC→fresh QUALITY的实施顺序。
- 新软预算从本轮实际UTC 2026-10-10 16:59:58起20分钟，只讨论两个输入载体方案与一条准备/运行/退出所有者链；此前首批文档/skill读取发生在该时间记录之前，不夸大为全会话计时。文档限原三份及skill；生产source body限linux_native_path_map.py、linux_phase_publication.py、linux_phase_runner.py、production_runner.py、linux_gt_history.py、linux_initial_volume.py、linux_production_controller.py、scripts/route2_preimport_launcher.py。其他src/scripts/configs/requirements/docs/tests只作文件hash元数据保留检查，tests不读body。无科学payload/测试/import/native/WSL/正式对象/Git操作。
- acceptance: 给出实际应由哪个OS所有者创建/封存/发布/撤销的因果顺序，指出bootstrap种子及source bank容量/不可写别名/共享VM退出仍缺哪些事实，提出两个物理方案及区分性便宜验收；不把架构字段当成producer。budget到期或关键物理条件未知即停止本节扩展，保留提案/UNKNOWN，不自动实施或升级运行权限。
- Goal: 收敛可安装的真实creator→不可变输入→worker→原启动/退出链，服务合法Route2机制验证及最终高event F1深度学习目标。
- Success metrics: 准备合同与正式实验准入的依赖有明确先后，所有生产对象/写者/实际时钟与费用有唯一归属；完整科学判定仍沿用原A/B及质量门，不用设计完成替代实验完成。
- Constraints: 全部已确认WSL、30GiB E分配、baseline、RAM/CPU/tasks/wall/收尾、nonE监控及原GT/ledger/nested科学合同沿用前节完整14项卡。
- Prior art: 当前early metadata consumer、GT broker/phase publication、study image creator、native phase生命周期源码及本节官方OS文档；都是已有部分或文档语义，非本机实际producer部署。
- Baseline: Route2零合法结果，完整实现FAIL；两metadata reader SOURCE_ONLY结论保持。
- Candidate approaches: A预制并整体封存nonGT role目录树；B按role分批生成独立封存输入。见下文，均不复用.worker作为输入。
- Critical assumptions: 原trusted host能提供受审native bootstrap种子；封存真正消除其他写入口；所需input/runtime物理费用满足原额；是否能安排独占WSL时间窗口UNKNOWN。
- Risks: A重复payload占用/准备耗时超出baseline或额度；B额外创建删除/封存历史与原clock、cap冲突；全VM退出涉及同账号其他发行版；native种子与加载前依赖仍未交付。
- Validation experiments: 当前只做静态设计及未来便宜metadata容量核算的说明，不运行实验。任何准备/ABI/OS部署证据仍须先有闭合的实际准备执行方法与原额度；正式A/B仍需完整准入。
- Kill criteria: 任一方案无法在原容量/身份/history/clock内形成真实不可写载体则弃该方案；不能关闭所要求VM/服务退出边界则记录平台使用约束冲突，不签终态PASS。未知不填零、不扩cap、不重置预算继续补消费者。
- Recommendation: REDESIGN进入讨论；先明确原native准备所有者，再优先评估A的真实容量可行性，无法满足时才评估B；不是已选定/已验证A。
- Confidence: 对现拒绝入口和官方OS语义高；对本机载体/容量/完整生命周期可行性仍UNKNOWN。记录为原三文档人工telemetry，不调用会产生额外文件的recorder，工具/token/全归属费用仍UNKNOWN。

#### 建议的因果顺序与唯一责任

1. **原trusted Windows native host owner与bootstrap种子。** 在任何项目Python或准备worker出生之前建立原QPC、native资源scope和固定安装身份；该种子的PE/native/transitive加载闭包、取得/编译安装历史和费用必须先明确。它是缺少的实际producer，不能由尚未启动的Python验证器倒推其存在。
2. **独立受限无GT准备creator。** 依原准备scope创建专用carrier/guest/external控制载体，形成同invocation三层baseline与实际容量/余额；随后创建readonly runtime/project/helper/nonGT输入及phase-source空placeholder。prepare有独立的受审执行合同，其所产部署事实供正式实验准入消费；不能让prepare反过来要求其尚未产生的FrozenAdmission来证明已部署。当前实际prepare合同未闭合，数值绑定不解除禁止运行。
3. **封存边界。** 写入结束、文件/目录持久化、关闭创建者可写FD、撤出临时写挂载并禁止其他写者/别名后，才发布只读source。只读入口、文件mode或manifest/hash不单独证明不可变；需实际backing设备/FS/挂载/写者事实。runtime加载闭包先于任何Python import/native load。GT及historical final-match payload不进入nonGT准备树，继续沿原broker合法grant/revoke处理；GT原backing部署缺项单列，不以nonGT镜像替代。
4. **原启动所有者与controller。** Windows原QPC认证transport与Linux native pre-Python/pre-spawn原t0/M0先形成，再启动原controller。controller持有original metadata/role publisher/broker/ledger及OS句柄；publisher在controller原进程内工作，避免新增Linux常驻进程占用TasksMax2。正式study 2→4GiB卷creator在正式准入后消费准备事实，沿现once-only顺序调用，不充当准备creator。
5. **逐role/phase worker。** 对现版directory-v2的/run/route2-input/roles/<SHA256(role_id)>发布精确的只读角色目录，沿现版权限传递与native spawn、UID/namespace/IPC/pidfd/READY/wait/reap/status装配。worker仅见本role输入与批准的短期GT视图，输出/scratch继续落study/.worker；原4096累计历史、256scan、nlink=1及map/joint/history界保持。不得把目录mount receipt包装成逐file mount事实。
6. **撤销与最终提交。** 每phase先确认真实worker退出并完成FD/pidfd清理，再撤销grant及输入发布；所有正常/失败secondary保留。最终terminal关闭后还需签名close/exit join、raw cgroup清场、scope内服务退出、实际VM退出及最终durable外部QPC。外部原host owner持有宿主进程句柄，完成退出验收和backing清理记录；其自身close/exit见证路径也须在实施SPEC明确，当前不签自证明终态。

#### 两个输入载体方案，先做容量选择

| 方案 | 物理设计提案 | 优点 | 进入实施前的区别验收 |
|---|---|---|---|
| A：一次准备后整体封存 | 独立于.worker的nonGT role目录树，含精确role leaf；发布目录v2视图，不靠硬链接或大批逐file新挂载冒充目录发布。准备完成后整个source载体只读，运行期间不改写。具体backing FS/布局尚未绑定。 | 运行期无复制/回写输入，创建者与消费者边界易核；最少运行期状态。 | 仅nonGT登记metadata/实际stat先核重复物理字节、inode/目录布局、封存历史和全费用是否满足guest baseline≤8GiB及原准备额度；未取得这些事实不得假设去重或免费共享。 |
| B：逐role独立生成并封存 | 基础原输入已封存；另一个受审creator在原scope内创建当前role专用输入，封存后publisher交给worker，退出后撤销并销毁。输入不是可写scratch，已经封存的同一对象不回写复用。 | 有机会降低峰值物理空间。 | 证明每次copy/create/delete、原history/cap及原1200/3600秒clock、收尾/剩余预算完整；不能仅凭低峰值承诺选B。 |

建议先审A的容量；这是候选排序，非A可行或已批准。若A复制上界超过原额度，则停止A，比较B的生命周期代价；没有一种方案能闭合时给出具体NO-GO证据，不无限转回局部policy补丁。105 reference合法复现仍只在获准Stage A执行。

#### 新的host使用事实问题与官方依据

Context7已先resolve并选High来源/websites/man7_linux_man-pages及/microsoftdocs/wsl，分概念query。官方文档说明：
- [Linux mount](https://man7.org/linux/man-pages/man8/mount.8.html)：只读bind入口可保留可写的原superblock；因此本节提出核整个backing及其他写入口，不采用仅ro标记封存。最新文档的新增CLI语法不作为Ubuntu22.04上可用性的证明，本节未执行任何命令。
- [WSL basic commands](https://github.com/MicrosoftDocs/WSL/blob/main/WSL/basic-commands.md)：terminate仅针对指定发行版；shutdown关闭所有运行发行版及WSL2 utility VM。独立发行版不能单独证明VM已退出。
- [WSL disk space](https://github.com/MicrosoftDocs/WSL/blob/main/WSL/disk-space.md)：分发VHDX及安装位置不等同于原per-study实体硬界；仍须原专用carrier与实际预算方法，不能借默认自动扩容当额度。

已通过request_user_input_async仅询问一个新增事实：能否提供期间其他发行版不运行、收尾可关闭整台WSL2 VM的独占窗口。本节UTC 2026-10-10 17:11:47 UTC记为回答待定/UNKNOWN；不把工具默认选项或等待时间当批准，不停止现有发行版、不启动WSL。如果不能独占，先评估已确认VM退出合同能否满足；不擅自降低退出要求。

brainstorming任务顺序：context已恢复；本节为逻辑所有者/容量选择，不调用浏览器visual companion；新事实问题待答；两个approach与第1节设计已提出；正式设计绑定/负责人审阅、后续writing-plans和SOURCE实施尚未开始。本轮只追加原三文档的“讨论提案”，不commit、不新建spec/交接包、不重开已确认决定，不新增完整A+B卡或任何review PASS。


#### 第1节提案自核补充：静态source bank与阶段产物不可混同

前节A/B的“nonGT role输入树”仅讨论**已登记、已合法分离的nonGT基础输入及readonly运行依赖**，不是在准备期生成全部未来科学输入。prepare不得提前物化候选、26D衍生特征、训练模型、预测、解码或评价结果，不读混合原件来替代合法nonGT投影。105 reference及其后105 treatment生成/复现、fit/predict/decode/evaluate及GT时序仍按原Stage合同。

阶段产生的模型/预测/衍生输入是否经文件或既有IPC交接，继续沿各阶段原合同核对；本节未选择新传输方式、未批准新增copy/image步骤。其真实producer、冻结时点、scratch可写别名/FD关闭与consumer交接仍必须闭合，不能因静态source bank封存就声明完整不可变输入完成。任何新静态复制、阶段物化或封存所占物理/内存/控制费用都须进入原额度；D_A=2GiB V2及同image2→4GiB界不能默认已经覆盖改变后的布局，需逐项证明仍满足原界，不修改上限。这一补充只明确讨论范围，未选择A/B或放行准备。


### 2026-10-10 执行架构收敛讨论，第2节：独占窗口已确认与静态输入容量证据

负责人回复“允许”，确认未来可安排独占WSL窗口：期间其他发行版不运行，收尾允许关闭整台WSL2 utility VM。本项host使用决定已绑定，不重复询问。它只解决允许独占的使用约束；当前是否真正独占、原配置是否已应用、实际VM/服务退出、最终durable外部QPC及其费用仍UNKNOWN。本次回复没有授权调用WSL、实际准备、正式对象创建或Stage A/B，原SOURCE/metadata只读边界保持。

#### 本节独立有界工作记录

- task=route2-static-input-capacity-discussion-2；owner=/root；workflow_path=RESEARCH；execution_mode=INLINE；actual backend=exec_command、隔离stdlib metadata/stat。新软预算为实际UTC 2026-10-11 01:52:16起20分钟，终点02:12:16 UTC；此前首批文档/名称读取不计作已覆盖的整会话计时。本节是America/Denver本地2026-10-10记录。
- SOURCE body固定限production_runner.py、contracts.py、linux_native_path_map.py、production_metadata.py、path_map.py五项。metadata固定上界五项，实际读取下列四项；只读登记结构、路径、状态及nonGT文件stat，不打开科学payload、不核payload hash。其他既有src/scripts/configs/requirements/docs/tests只作hash保留核，tests不读body。
- acceptance：区分唯一基础源与完整directory-v2逐role/phase复制量，包含reference的两phase别名，提出有数值依据的物理方案排序；不把stat当内容冻结、FS实体分配或baseline实测。未知容量/写者/原clock费用停止本节扩展，不加cap或以policy替代producer。本节零生产源码修改、零实验、零WSL/部署对象操作；工具及全归属费用仍UNKNOWN_NOT_ZERO。

#### 实际读取的登记metadata与保留身份

| metadata | bytes | SHA256 |
|---|---:|---|
| artifacts/route2-candidate-overlap-v1-001-source-registration.json | 927264 | e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853 |
| artifacts/route2-candidate-overlap-v1-001-inputs/role-input-registry.json | 16457999 | 5d5f1f59d58a9be265db9467261cf16c4d54bc43e87a2dd33c3b94723191edd3 |
| artifacts/route2-candidate-overlap-v1-001-inputs/reference-registry.json | 62579 | 7f790671ef2884943e41be2be3036c7611c6c0412f36a116686c61b3d23df21a |
| artifacts/route2-candidate-overlap-v1-001-inputs/projection-manifest.json | 12570808 | ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad |

source-registration及projection-manifest仍为PREPARED_UNREVIEWED。role-input-registry登记105 role；本核算仅选score_npz、score_provenance、cache_manifest_view、identity_view、quality_attestation及cache_files.cache_npz，再加入已登记nonGT reference projection。没有读取GT census值、GT payload、混合原件、候选/模型/预测/评价内容。metadata中的source SHA本节未按payload验证。

#### 容量核算：必须计入两phase reference alias

production_metadata.py:892–906要求每个reference在stage_a_reference与OUTER_CONTROL_CANDIDATES_PHASE分别登记；path_map.py:110–127的alias名包含logical_path、SHA、role_id、phase，因此同一reference的两个phase形成不同leaf。role目标根继续是/run/route2-input/roles/<SHA256(role_id)>。

- role输入19684个登记出现，加105 reference×2，完整静态nonGT alias共19894。只计一次reference得到的19789及6873003807 bytes是不完整中间量，不用于最终方案选择。
- 对1757个不同登记路径执行non-following leaf stat：观察到1757个(dev,ino)对象，均普通文件、nlink=1；missing/unusable/metadata-hash冲突及本脚本前后stat漂移均为0。该结果不证明parent、全部别名、可写FD/挂载或内容身份；未持有运行期source FD。
- 不同基础源逻辑数据共3026850159 bytes（2.818974 GiB）。按每role/phase独立复制19894 leaf，数据共7117668304 bytes（6.628845 GiB）；按每文件4KiB向上取整的规划估算共7161221120 bytes（6.669407 GiB）。这不是目标FS allocation实测，未包含目录/inode/journal、封存载体、runtime、控制、reserve及其他baseline费用。
- 原8GiB入场baseline减上述4KiB文件数据估算，仅余1428713472 bytes（1.330593 GiB）。实际Ubuntu/runtime及完整三层baseline仍UNKNOWN，不填零。故A目前容量紧张，但没有证明A或E+WSL不可行，不签NO-GO。
- 最大单role leaf数为257（250 cache+5输入+2 reference），不能放入.worker的256扫描界。当前stat给出的保守单role逻辑数据上界为93797305 bytes（89.452081 MiB）；不含FS开销、后续科学阶段产物及其封存费用。

#### 方案排序与下一设计单元

本节建议将B“基础源一次封存＋逐role独立只读快照”作为下一讨论主线；这是根据容量更新的提案，尚未由负责人选择、实施或验证。A仍保留为低运行期复杂度的候选；若其实际全baseline能满足原界，可再比较。不得把2.82GiB唯一逻辑数据称作已安装source bank或实际磁盘峰值。

B需按原所有者链闭合以下物理责任后，才形成可审SOURCE实施计划：
1. 无GT准备creator在原准备scope内创建静态基础载体；关闭可写FD与临时写入口，证明整个backing无可写别名后发布。基础载体须与.worker及动态科学产物分离，runtime/helper加载前闭包单列。
2. 原controller内的creator/publisher创建当前role的独立generation，完成持久化及真实只读封存后映射到现版directory-v2目标根；不新增常驻guest进程，不改变TasksMax2、nlink、累计history及扫描上界。不回写复用已封存对象，不用共享可写原文件或hardlink节省量冒充不可变性。
3. 真实spawn、pidfd、READY、wait/reap/status确认和逐role/phase GT grant/revoke沿原合同装配。先确认退出及必要FD释放，再撤销视图、清除挂载/设备引用并删除generation；失败路径保留primary与cleanup secondary，不凭callback回执宣布成功。
4. 新copy/create/delete/封存步骤须分别证明原4096历史、输入与scratch分离、D_A=2GiB及同image2→4GiB容量合同仍满足；1200/3600/900秒、原准备/外部scope、所有历史及未来费用不扩额。105 reference复现、treatment、26D/fit/predict/decode/evaluate仍只在合法Stage运行，不能在prepare提前物化。
5. 原host native种子及pre-Python/pre-spawn t0/M0/QPC、安装依赖、三层实体硬界/actual baseline/剩余预算、terminal签名join/raw cgroup/服务与VM退出仍是独立缺项。独占窗口的许可不产生这些事实。

下一单元应先选定确切backing FS/实体布局及creator API，逐对象列出创建者、可写入口消除时点、发布/撤销/删除、原scope和费用，形成有限的可实施设计；若无法证明原界，停止该方案并给出具体冲突。当前不新增占位接口/政策字段或另一个条件卡；完整A+B卡沿用本轮前节唯一14项卡。后续SOURCE组件仍按单实现者停止写入→独立SPEC→fresh独立QUALITY执行，不用本节文档自核替代双审。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。路线二零合法A/B及结果；Route3 v1-003合法COMPLETE/四门FAIL不变；本节没有source/runtime/input/protocol/budget冻结或full-review PASS。

本节收尾保留核（实际UTC 2026-10-11 02:10:23）：404项既有监测文件仅原三文档变化，无增删，三文档旧bytes前缀均完整，Git index SHA不变；源码及原授权prompt/card因此保持原hash。这是有限hash元数据自核，不是独立双审、完整冻结或runtime证据。新的问题只询问下一讨论优先细化B还是继续证明A baseline；未收到选择前不把推荐写成已绑定方案。本节容量任务已结束，不延长原20分钟预算继续实施。

### 2026-10-10 执行架构收敛第3节：B已选择，真实物理载体与失败所有权细化提案

负责人本轮明确“选择并开始细化与优化B方案”。B主线和前节独占WSL窗口现为已绑定决定，不重新讨论A/B或既有WSL/预算/科学协议。本节物理机制、生产组件和安装顺序是供审阅的细化提案；不是生产源码实现、实际准备或实验放行。

#### 新单元、preflight与证据边界

- task=route2-B-physical-design-3；owner=/root；workflow_path=RESEARCH；execution_mode=PARALLEL_SUBAGENT；实际backend=collaboration.spawn_agent、exec_command、Context7及官方文档读取。新30分钟软预算自实际UTC 2026-10-11 03:24:34起，终点03:54:34；首次恢复文档/skill读取发生在此前，不夸大为全会话计时。
- 两个只读advisor分别限定4源input与5源worker/lifecycle，8分钟软预算，已结束、零修改；/root为原三文档唯一追加者。总SOURCE body范围固定12项：production_runner.py、production_metadata.py、linux_initial_volume.py、linux_native_path_map.py、linux_phase_publication.py、path_map.py、contracts.py、linux_phase_runner.py、linux_production_controller.py、linux_child_launch.py、linux_child_exit.py、linux_gt_history.py。native C/H仅名称清单，不读body；科学payload、tests body、project import、helper/native/WSL/生产及正式对象操作均未进行。404项既有文件hash/index保留核不是完整冻结。
- capability_tags=linux-execution-isolation, immutable-input-publication, scientific-protocol-preservation, resource-budget；loaded_profiles=generic（不改变模型/数据/评价选择）；critical_unknowns=bank/role真实backing与原creator、原owner与动态视图兼容、全部写者/FD/设备引用、history/clock费用、原启动及最终退出。validation_order=SOURCE因果与OS语义→具体设计/独立静态双审→未来依法准备证据→完整冻结准入→合法A/B。
- Goal：真实creator→不可变输入→worker→启动/退出链，支持Route2机制比较并服务最终深度学习event F1≥0.66。
- Success metrics：每个物理对象有唯一创建/封存/发布/撤销/删除者、先后和原额度归属；冲突给出拒绝入口，不以文档完成替代实验完成。
- Constraints：原14项完整A+B条件卡全部保持；本节仅静态/文档，不增额度/cap/测试/Git操作、新卡或交接包。
- Prior art：原early metadata owner、directory-v2、GT/phase/child、study image源码；前节metadata/stat容量；本节官方kernel/man-pages语义。
- Baseline：零合法Route2结果，完整实现FAIL；SOURCE inherited pin不变。B仅主线已选，bank/generation无本机创建证据。
- Candidate approaches：磁盘ext4独立generation+真实backing写者关闭/封存；fs-verity文件封存；sealed-memfd RAM generation。以下仅优先细化第一项，不把后两项假定免费或本机支持。
- Critical assumptions：原受审native creator/加载前边界能按原scope实施；本机实际dm/loop/immutable支持、guest baseline、整个生命周期费用仍UNKNOWN。
- Risks：启动metadata与study mount门冲突；输入读取仍误路由到metadata owner；phase失败后没有可承诺的完整清场；复制次数/累计历史及2GiB余量未知。
- Validation experiments：当前零实验，仅12源静态追踪及官方文档。后续本机部署/运行期证据仍受原实际准备合同约束，不因数值/设计选择直接运行。
- Kill criteria：机械封存/完整写者集合、所有权连续性、原cap/资源余量或原clock不能证明即保留UNKNOWN并停止相应实施；不靠新字段/回执/扩大cap放行。
- Recommendation=REDESIGN；Confidence：SOURCE拒绝和原OS语义高，完整本机/预算可行性UNKNOWN。人工telemetry只写原三文档；不调用另建日志文件的recorder，token及全归属费用UNKNOWN_NOT_ZERO。

#### 独立追踪发现的四个必须解决的生产断点

1. **原early owner不要求全部role文件已存在，也不授予其I/O。** linux_native_path_map.py:686–700只对__study__/preflight_metadata核实际目录/挂载；:529–575保留全map对象/scalar/覆盖，不替代role authority。由此动态generation可以保留原full-map，不必为了启动预制19894 alias。但path_map.py:576–579将现版v2读取送到metadata owner，该owner:606拒绝role请求；:659–660又明确拒绝native role lease。需要真实role producer和same-FD consumer分支，不是改manifest或复制一张receipt。
2. **启动挂载门真实冲突。** early owner在linux_native_path_map.py:318–344、:505–518核实际/run/route2-input/metadata mount，并要求pre-guard.start原bootstrap状态（:182–186、:681）。production_runner.py:403–409先load metadata再assemble owners；linux_production_controller.py:206–245随后prepare study。linux_initial_volume.py:433–435却拒绝任何/run/route2-input mount。新设计须仅识别同一healthy原early owner持有的确切readonly bootstrap metadata mount及其FD/device/ancestor/kernel身份；未知、漂移、其他role/worker mount全部拒绝。不能删掉整项namespace检查或只增加allow布尔值；该重构须与原owner交接连续性一同独立复审。
3. **已有phase publisher不是nonGT generation creator。** linux_phase_publication.py:1548–1579克隆原broker释放的GT/可选historical row；:1067–1070、:1150–1163要求保留source frame/device/FS root且观察fresh mount ID。不得把新copy generation的不同inode当作原GT source，也不能以directory mount生成逐file mount receipts。
4. **失败不是正常revoke后删除。** linux_phase_runner.py:704–757正常grant→publish→child outcome→close phase inputs→revoke；:799–841失败poison后禁止normal revoke，至多一次未尝试的publisher close。linux_production_controller.py:96–99保留失败后抛StartupPreservedWithoutTeardown。linux_child_launch.py:670–679对未reap原child保留registry并阻止移除。B必须提供独立的原cleanup权限，使用原对象/原deadline处理失败，不借健康normal接口或“close_complete”attempt标志签删除成功。

#### B的物理布局提案与资源归属

| 对象 | 物理提案 / 原唯一责任 | 生命周期与费用 |
|---|---|---|
| 静态nonGT bank | guest专用carrier内独立ext4数据image及完整性tree；只保存现有合法nonGT登记输入，按(logical_path, expected SHA)去重，不按role/phase重复。由无GT准备creator形成。bank内部对象路径与role alias分离，受保护目录分层以保持各扫描范围的原界。 | 从准备开始到整个任务退出保持封存；实际data/tree/FS/control/制作历史进入guest≤8GiB baseline及原prepare账目。2.82GiB仅逻辑数据，不能放入初始2GiB study或称实测allocation。bank不包含GT、历史matched-GT或未来科学产物。 |
| 稳定发布骨架 | prepare预建/run/route2-input/metadata及roles下105个原role hash mountpoint、私有builder mountpoint；身份记录前完成目录变化。 | 后续只在已存在mountpoint发布/撤销，不改original metadata祖先目录来绕过frame后核。publisher不额外起daemon。 |
| 当前role generation | controller原进程同步创建study/.role-input/<原invocation内单调generation>/data.img及tree.img，O_EXCL/O_NOFOLLOW、held parent FD；与.worker分离。构建mount在独立私有/run/route2-builder/role，正式consumer只见/run/route2-input/roles/<SHA256(role_id)>。 | 始终最多一个未销毁generation；旧对象真实清场前不创建新对象。data/tree/FS/目录与失败残留全部内计原2→4GiB study容量和原clock；不在study mount树内新增submount、不在其他guest路径另借容量。精确image子容量尚须原容量余量证明，不绑定任意128MiB等新额。 |
| role视图 / reader | 新原role owner在同一map对象和guard下发布整个readonly目录；consumer用exact key索引、O_RDONLY/O_NOFOLLOW、同FD hash→消费→后核。 | 不改固定alias，不加入generation到bind_path，不替换healthy early map。__study__ metadata继续原owner；GT继续原broker；其他未授权phase拒绝。 |
| scientific worker | 现原phase runner/child owner装配native spawn/pidfd/READY/UID/namespace/IPC、wait/reap/status；bank、builder、raw image/device不暴露给worker。 | creator/formatter与scientific worker互斥。controller+一个临时受限formatter或一个scientific worker，均须实际满足TasksMax2；任何内部线程/额外服务亦计入，命令名不能证明任务数。输出仅既有批准写路径，不把.roIe-input加入.worker registry。 |

generation不是底层FS的便宜copy-on-write snapshot；这里“快照”明确为新独立payload副本完成后封存。plain-v2 metadata仍拒绝fallback；原healthy early owner失效/漂移/closed/active不得重建map或重新发号。

#### 封存机制首选提案：实际原生写者关闭 + inode保护 + readonly验证设备

为解决“ro入口仍有可写backing”的漏洞，本节提出以下真实OS步骤，不能简化成mode/hash/policy字段：

1. builder在唯一原scope内独占创建data/tree文件；记录初始inode/parent、所有RW FD、loop、mount及formatter真实pidfd/退出。从已封存bank同FD逐源串行复制，固定小buffer、实时扣原clock/内存；hash与bank登记的payload SHA一致。普通leaf保持nlink=1，拒绝symlink/hardlink；role ext4 root清除格式化自带lost+found等非登记条目并保留其创建删除历史。
2. 复制完成后fsync各leaf/目录/FS及backing，正常卸载构建FS，观察其写引用全部终结；所有formatter已wait/reap，旧RW loop真正解除，原RW image FD一次关闭并健康。关闭记录之外的writer/可写mapping、另一个mount、raw device授权或同inode别名未知时不封存。
3. 在原owned O_RDONLY backing FD上设置并核FS_IMMUTABLE_FL，禁止常规write/truncate/reopen/rename/unlink；data和tree均受保护。唯一原trusted native控制/cleanup所有者的clear权限不得交给worker或其他un审调用方；active期间不可执行clear/rewrite，cleanup仅在实际quiescence后一次清除该保护再删除。此能力、全部特权写者/FD集合和实际执行权限必须有部署事实，单次GETFLAGS不能证明闭合；若无法排除未归属特权写者，则该物理方案拒绝。
4. 构建完整Merkle tree并由原producer认证root/长度/算法/参数；data/tree readonly loop→只读dm-verity device→clean ext4 ro,noload/nosuid/nodev/noexec/private mount。dm producer须实际进行原生device create/table load/resume与内核query，绑定真实dev、table、root和generation，不能只签一张HMAC回执。kernel摘要和原payload SHA是不同身份，不互相替换；不接受ignore_corruption、check_at_most_once等降低校验的选项。完整性设备补数据读校验，不单独证明没有可写backing别名。
5. 新role owner在该source FS上核完整原role mapping集合与真实leaf/frame/mount；发布固定role目录。原lease包含stage_a_input、stage_a_reference、outer_control_candidates三集合（path_map.py:35–37、:683–694），因此本提案不偷偷改成phase子集来降低copy计费。消费者成功只在同FD后核和全部once-close健康后返回；任何损坏/读失败或cleanup失败poison并阻止下一role。

机械能力、本机内核与helper实施均未观察；以上是可审的OS因果提案，不是已安装producer。只读dm-verity不能替代第2/3步；原Windows可信owner假设不免除guest全部特权写者与加载闭包证明。新协议不得接受任意caller backend、factory、路径、policy callback作为真实issuer。

#### 正常与失败退出：先身份/引用闭合，后删除

正常：停止新的role读/phase申请→消费真实child outcome和bounded IPC EOF→pidfd WNOWAIT/reap一次，核UID65534/CLD_EXITED/status0及原raw statuses→原phase输入关闭、GT broker完成正常revoke→role consumer同FD后核和引用释放→撤出role view并核各namespace mount absence→释放source FS held refs/正常unmount→实际移除dm并核不存在→readonly loop实际detach/association消失→一次关闭owned data/tree/query FD→在原cleanup权限下clear确切inode保护、以held parent核身份后unlink data/tree和generation目录、fsync删除历史→才允许下一个generation。

正常路径顺序必须与实际consumer拓扑匹配；纯controller非GT lease没有worker时仍须确认不存在任何worker/phase/FD引用，不能制造虚拟child exit。若metadata/frame检查需要的借用FD仍活跃，不得先关或先删。

失败：在原异常捕获点保留raw primary，停止新增工作；原cleanup使用原pidfd及原收尾deadline执行kill/wait/reap（linux_child_exit.py:106–174），随后按已真实发行的grant/mount/device/FD清除，禁止走poison后normal revoke。close/unmount/remove/detach/unlink有任一未知或secondary均保留原身份、残留及费用，不能写REVOKED/DELETED或终态PASS，也不重试已消费FD/attempt。清场失败保留backing，后续raw cgroup与宿主/VM退出owner继续处理原残留；不能用VM退出声明此前删除已发生。

terminal关闭后仍需原签名close/exit join、raw cgroup清场、全部服务及VM实际退出、finaldurable外部原QPC和外部owner自身exit见证，独占窗口仅解决使用许可。真实kill/namespace/revoke/raw devices/VM费用和加载前边界仍在原完整准入缺项中。

#### 优化与可行性判据：只减少已证明的成本

- unique bank一次准备＋一个current generation；不缓存已完成role、不异步prefetch、不新增guest daemon；全目录一次发布，不制造19894 per-file新mount或hardlink。
- Exact map按role建立固定索引，SOURCE处理目标O(K+M)，不做每alias×所有角色扫描；同线程同role嵌套lease共享同generation和深度，跨role拒绝。银行复制按单源串行held FD进行，RW阶段结束才开consumer；buffer、FD和所有中间账目都必须进入原额度。
- 原.worker仍累计4096 inode/path、256scan/nlink1（linux_gt_history.py:63、:781–846、:951–986）；删除不reset history。独立input并不免去完整创建/封存/发布/撤销/删除历史。新输入扫描按原full-map确切集合核257 leaf，不能复用scratch256后扩cap。generation生命周期次数R与全部history所占空间/记录数须从实际consumer调用拓扑推导；科学105+105是逻辑任务数，不能直接冒充R或便宜copy次数。
- baseline式：actual(bank data+tree+FS + OS/runtime/project/dependencies + 控制/历史 + 原其他baseline)≤8GiB。stage式：current generation实际分配+tree/FS/history+原scratch/模型/输出/ledger/控制/残留/收尾≤原2GiB，Stage B在同一study image扩至4GiB。嵌套image字节消耗study内部容量；guest实体层按原outer image分配核，不以2+inner逻辑长度重复计算或称新增免费空间。三层actual usable/allocated/remaining均须原同invocation证据。
- total copy/格式化/树构建/核验/关闭/删除工作=按真实每次lease求和，包含重复role和失败；不能用89.45MiB单role逻辑上界推出全任务wall PASS。全部步骤消耗原Stage A1200/总3600秒；fit计时沿原科学合同且累计900秒不变，额外输入工作不得归零或延后原t0。预先证明原cleanup余量，不借128MiB nonE名义reserve作实体保证。
- 目前actual R、目标FS allocation、封存设备/权限、2GiB余量和耗时均UNKNOWN_NOT_ZERO，不能签B可部署或E+WSL不可行。若原资源式失败，停止具体载体方案并报告冲突，不扩大绑定值。

#### 官方依据与替代机制取舍（非本机证据）

Context7先resolve Linux man-pages，高来源/websites/man7_linux_man-pages，按loop/readonly ext4/teardown/immutable分概念读取；随后补官方kernel资料。未执行文档中的OS命令。
- [Linux mount](https://man7.org/linux/man-pages/man8/mount.8.html)及[Linux 5.15 ext4](https://www.kernel.org/doc/html/v5.15/admin-guide/ext4.html)：readonly入口不足以证明写者不存在；dirty ext4可能journal replay，ro,noload须以clean filesystem为前提。不能用noload掩盖不一致。
- [Linux inode flags](https://man7.org/linux/man-pages/man2/FS_IOC_SETFLAGS.2const.html)：immutable由特权设置/清除；本方案额外要求关原RW引用、控制clear权限及元数据身份，不把该flag单独当生产闭合。
- [Linux 5.15 dm-verity](https://www.kernel.org/doc/html/v5.15/admin-guide/device-mapper/verity.html)：verity target为只读块校验设备，root须来自可信原creator；本提案要求实际设备及参数核对，禁止降低校验选项。新增设备/tree和原生helper成本并非零。
- [Microsoft 5.15参考config](https://github.com/microsoft/WSL2-Linux-Kernel/blob/linux-msft-wsl-5.15.y/arch/x86/configs/config-wsl)：只读HTTP取得109806 bytes，见CONFIG_DM_VERITY=y、CONFIG_BLK_DEV_LOOP=y、CONFIG_EXT4_FS=y、CONFIG_MEMFD_CREATE=y而CONFIG_FS_VERITY未设置。原Microsoft/config-wsl是指向该文件的30-byte路径。本机当前kernel/config尚未查询，不能用上游config当本机能力PASS。
- [Linux 5.15 fs-verity](https://www.kernel.org/doc/html/v5.15/filesystems/fsverity.html)：文件verity可约束内容写入，但要求kernel/FS feature且不保护rename/delete/所有metadata；本节不默认增加custom kernel或用其替代原owner身份。sealed-memfd暂不作主线，因为image/pagecache/复制共存的C/AS/RAM费用尚未证明，不能把disk困难转成未计RAM。
- [Linux unmount](https://man7.org/linux/man-pages/man2/umount.2.html)和[loop teardown](https://man7.org/linux/man-pages/man8/losetup.8.html)：lazy unmount/detach请求成功可仍有活引用；必须实际核namespace/device/association消失，不能以成功返回作删除证据。

#### 后续生产组件边界（设计候选，不是本轮已启动的实施计划）

1. 原受限prepare/native种子与bank creator：确定E实体/guest承载/readonly加载前所有者、实际bank data/tree/保护/设备，原准备执行合同独立于尚未产生的FrozenAdmission；不让prepare消费自身未来产出的FrozenAdmission来证明已部署。无GT非科学字节复制仅在该实际准备方法闭合后执行。
2. 拟linux_role_generation.py：单一creator/cleanup对象负责原held parent、OS create/allocate/format/copy/flush/seal/loop/dm/FS、原失败保留和实际删除；不得只提供ports接口而无生产OS调用。原linux_initial_volume不是role creator，不复用它的once-only study身份。native helper可能涉及native/route2_mount_helper.c/.h，必须先单列新的readonly ABI/加载/资源边界，本轮未读其body或改动。
3. 拟linux_role_publication.py与原path_map.py/native owner调用点：发行/持有唯一原role owner，保留原map/manifest object和exact alias，分别路由metadata、nonGT role及拒绝其他phase；same-FD消费者全后核/once-close及失败撤销。metadata mount与study gate的原owner实物交接一并定SPEC，不能删除gate当修复。
4. 原phase/controller failure assembly：装配creator、role reader/publisher、现GT/phase/worker及原失败cleanup authority；之后才处理_require_native_nested_producers真实拒绝，保留QPC/完整安装/readonly/native/full-review等独立gate。

这些组件都仍需实际原producer/对象/费用证据；当前没有可声称已SOURCE闭合的新组件。本节文档写入停止后做独立SPEC，再fresh独立QUALITY，仅审本设计及SOURCE事实；不是正式full-review。按brainstorming，新物理细化须负责人审阅后进入writing-plans及单实现者源码任务；已选B不再询问，SOURCE双审不代替完整实验准入。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。Stage A/B零合法运行与结果，Route3 v1-003合法COMPLETE/四门FAIL不变；原四门、matched-GT实际增减、固定saved scores/模型/26D/threshold/decoder/matcher及只比较严格时间交叠与300秒间隙保持。无合法Route2结果前不启动三个模型方向。本节不新增完整A+B卡，继续引用前节唯一14项卡。

#### 第3节细化自核修订：tree先完成，引用先关，真实能力不冒充

封存第2–4步以此精确顺序为准：data复制/flush、构建FS clean unmount、formatter与RW loop/FD真实终结→持data O_RDONLY逐块构建tree（此时tree仍由唯一builder持RW FD、没有consumer）→tree flush及所有tree RW引用健康一次关闭→设置并核data/tree inode保护→原readonly loop/dm实际发行和consumer发布。不得先保护空tree再写Merkle；全部leaf源SHA已在复制时按同FD核，Merkle root由该原producer认证，两种摘要不混用。

正常退出先关各consumer/phase/source mount FD并核真实namespace引用释放；dm block/query FD须健康一次关闭后，才尝试移除dm（原mapper-control FD可保留用来查询）；readonly loop的持有/query FD及全部关联引用须在association消失验收前按原一次关闭语义释放。loop clear/remove请求可延迟，必须在原deadline内以剩余控制/内核观察核实际结果。data/tree O_RDONLY backing与held parent可保留至身份核清/clear保护/unlink，不把已关FD号重新用作原句柄。任何关闭/引用/移除未知即保留残留，不能按第3节概括顺序先宣告device absence。上述只是顺序修订，不授权OS调用。

第3节表格中的私有backing路径统一为study/.role-input（字母role）；不是.worker，不将该树混入其registry。磁盘机制仍为优先细化提案；本机kernel/ioctl/权限未观察，无能力PASS。独立静态双审仅对本节设计/修订及SOURCE事实，后续不能把该结论写作新生产组件或完整full-review通过。

#### 第3节收尾：SPEC完成、fresh QUALITY未完成，设计与运行准入分别保留

负责人最新“继续工作”沿用已选择B及原工作边界。本次只继续细化设计的审阅和保留核；没有重问B、独占WSL窗口或任何既有预算/科学决定，没有开始生产源码、实际准备或Stage。

- /root/b_design_spec_review已返回正式限定结论：NO_REMAINING_SCOPED_P1_P2 / DESIGN_SOURCE_REVIEW_ONLY。审阅对象为第3节、其最后自核修订及spec/plan相应最新追加；未读SOURCE body、未修改、未运行。该结论只说明此设计范围未发现剩余P1/P2，不说明新的role producer已实现或物理预算已证明。
- 在SPEC结论后尝试派发fresh独立/root/b_design_quality_review；平台返回usage limit，未完成审阅、没有QUALITY verdict。记为NOT_COMPLETED_USAGE_LIMIT / NO_QUALITY_VERDICT；因此本节双审尚未完成，不能记录双审NO_REMAINING_SCOPED_P1_P2，也不能以/root自核或历史源码QUALITY替代此轮fresh结论。当前不继续派发同条件重复尝试。
- 第四次子代理派发前已于UTC 2026-10-11 03:48:30做adaptive软阈值checkpoint：原两个只读advisor识别新启动/消费/失败冲突，作者停止后SPEC和fresh QUALITY是不同的限定评价关口；增加第四个agent不扩充运行期假说，原总预算截止03:54:34不变。实际dispatch=4（advisor2、SPEC1、QUALITY失败1）；已返回内容3；生产实施attempt=0、major experiments=0、implementation retry=0、同一运行失败新假说=0。QUALITY未完成次数1；没有产生实现review ID或full-review PASS。
- 恢复核时实际UTC已为2026-10-11 05:16:00，超过本节03:54:34软截止。整个03:24:34起的wall超过30分钟；其中工具/模型工作、等待、中断各自比例及全归属费用UNKNOWN_NOT_ZERO，不能扣掉未知间隔后宣称按预算完成。此后仅做必要收尾保留核和如实记录，不重置设计探索预算、不拓宽SOURCE或继续实现。
- 四个生产断点和本机creator/封存/权限/FD/设备/worker写路径/actual预算UNKNOWN均保持。设计的“data完成→tree完成→RW全部健康关闭→inode保护→实际RO loop/dm→role发布”和“引用先关→核设备/association实际消失→清保护并按held parent删除”以最后自核修订为准。最新spec/plan共同引用这一修订；第3节较早的概述不能覆盖它。
- 本轮已有12项生产Python的隔离stdlib AST/hash核，没有新增测试、测试body读取、project import、helper/native/WSL/GT payload/生产调用或正式对象创建。收尾404项文件hash核只解释为有限工作保留证据；第一次将全404项旧hash嵌入Windows命令参数超过系统命令长度而未创建进程，随后改为只传三文档旧前缀记录成功，metadata核retry=1，与实现/运行retry无关。
- 在本收尾追加前，404项既有监测文件仅原三文档变化，无增删；三文档旧bytes前缀均完整，Git index SHA b2ef45b682ab16128e1effc27fcce7180028919967ced9b43e07c37dd7003bea不变；两份继承生产源码和原授权prompt/card均保持原hash。最终追加后再次作同范围hash/前缀/index核；该核不等于完整冻结或独立QUALITY。

下一步仍是补齐本设计的fresh独立QUALITY，并由负责人审阅这份新增的具体物理设计；brainstorming的written-spec review关口要求这一审阅后才进入writing-plans。已选B与独占窗口不重问；SDD要求完成独立SPEC/QUALITY，资源失败不应绕过关口。上述是SOURCE计划前的设计关口，不是部署、实验或扩额申请。准备方法与实际执行边界、完整正式复审和全部冻结仍须分别闭合。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；Stage A/B零合法运行、路线二零合法结果，Route3 v1-003合法COMPLETE/四门FAIL保持。原唯一14项完整A+B条件卡继续有效，本节不新增卡、交接包或授权文件。



### 2026-10-11 B architecture completion and component SOURCE plan — candidate for fresh review

This is the latest B design and supersedes only the earlier sequencing statement that writing-plans had not been commissioned. The owner now commissions architecture completion, design review and a component execution plan; the execution agent implements later. B and the exclusive future WSL window are fixed. This session authors documentation only. Previous B SPEC was DESIGN_SOURCE_REVIEW_ONLY; its subsequent QUALITY had no verdict because of usage quota. Those results do not review this new candidate. A fresh SPEC and a distinct fresh QUALITY must examine this candidate after its author stops writing.

Author=/root/b_architecture_plan_author, single append author of the original three documents; actual start UTC 2026-10-11 12:17:14, 25-minute author budget ending 12:42:14 within root's 60-minute budget 12:09:47–13:09:47. Source body scope is exactly the 30 paths recorded below; root's separate ten bring the combined scope to 40, with no 41st body. No SOURCE mutation, test creation/execution/body reads, project imports, native compile/link/load/call, helper/WSL/GT/scientific payload/production/Stage operations, formal object creation or Git mutation by this author. Token, review, waiting and historical/future preparation costs remain UNKNOWN_NOT_ZERO. This is not a new authorization card, handoff package or source/runtime freeze.

#### 4.1 Decision, readiness and the two real unresolved platform prerequisites

The selected mechanism is one unique sealed nonGT bank followed by independently created CURRENT role generations. The bank is preparation/baseline storage, never the 2GiB study. Every role generation is charged inside study/.role-input and the original clocks. No cache, prefetch, daemon, altered role subset, enlarged scratch registry or new capacity is introduced. The entire original map, aliases and scientific identities remain unchanged.

The plan is ready for bounded SOURCE implementation of the independent components specified as NOW_SOURCE, starting with C00's native enforcement and final-witness primitive audit. Complete architecture feasibility and selection of a compliant VM/service/thread/last-owner enforcement mechanism remain conditional. It is not a physical deployment or runtime feasibility PASS. Two prerequisites explicitly stay unproved: (a) exact enforcement and attribution of the original whole VM/kernel/services/Windows thread scopes, beyond associated-process Job limits; (b) a genuinely independent final witness for the last original Windows owner's exit and final durable timing, with every witness/writer charged. No confirmed platform impossibility is asserted. The source plan gives concrete observation, enforcement-boundary and rejection tasks for both. Until they produce actual supported OS evidence, the complete runner cannot be installed/admitted as compliant. OWNER_EXIT_JOIN_UNPROVEN and VM_SERVICE_SCOPE_UNPROVEN are precise blocking outcomes, not success receipt fields.

Trusted Windows owner and the existing protected OS loader are the initial trust roots. Files, policy, signed metadata and callbacks do not create this trust. The design does not pretend a newly spawned parent is free. Every task-created actor, including a seed, WSL transport, observer, compiler, formatter, launcher and bridge, belongs to an original resource scope. System/kernel services and initial OS loading that cannot yet be fully attributed are UNKNOWN_NOT_ZERO and prohibit resource PASS. SOURCE authoring can resolve interfaces without running those actors.

#### 4.2 Original native birth, dual clocks and authenticated continuity

**Windows native seed.** The four existing native C/H files remain the native source boundary. The future Windows executable is a separate, conditionally compiled target of native/route2_mount_helper.c/.h; Linux mount-library ABI v1 stays exactly 40 bytes. The same source has a distinct Linux native-start executable target. No Windows code is compiled into the Linux mount library and no constructor or automatic startup runs in a loaded helper. Separate explicit entry targets and ABI identifiers prevent accidental dlopen of a launcher. Compile/link/ABI/load remain blocked until the actual preparation budget and readonly toolchain closure are established.

The trusted owner launches only the fixed installed seed by held file identity on the protected execution carrier. Native first-entry QueryPerformanceCounter/QueryPerformanceFrequency and available host RAM are captured before Python, WSL launch or preparation child creation. PE TLS callbacks, application DLL initializers, mutable delay-load/search paths and automatic dependency discovery are rejected. System PE loading before the first seed entry is an explicit trusted OS boundary with costs retained; it is not retroactively billed by a Python timestamp. The original native parent captures its child's creation identity before granting execution. Dynamic file handles use FILE_FLAG_OPEN_REPARSE_POINT, no writable sharing, FileIdInfo/volume GUID and observed readonly carrier identity. ApplicationName is absolute; no PATH or caller command is accepted. CreateProcessW uses suspended birth plus a restricted inherited handle list; Job association, effective queried limits and original process/thread identities are checked before ResumeThread. The existing Python _prepare_fixed_worker refusal is replaced only by consumption of that held native installation/start state, never by constructing _KernelOwner after an import.

The external owner's original QPC epoch is captured once before its work; 6000 seconds includes preparation observation, transport, signing, verification, all its cleanup and its remaining exit work. Preparation and study are sequential: original preparation/compile/ABI epoch is bounded by 1800 seconds including 60 cleanup; the original study epoch is captured at its actual native birth before Python/creation work and remains bounded by 1200 Stage A/3600 total/900 cumulative fit, each with its existing cleanup accounting. No epoch is rebased after hashing, registration, mount creation, Python startup, failure or a retry. Host QPC and Linux CLOCK_MONOTONIC remain distinct clocks, joined by authenticated invocation identity rather than numerical equality. The native Linux M0 used for C is its one original first native available-RAM sample before controller birth, not a later sample; host RAM observations also remain charged.

**Transport.** The original Windows seed owns anonymous, bounded binary pipe endpoints inherited only by its fixed pinned wsl.exe transport child; the original Linux seed receives the matching standard channels and closes them before any scientific worker exec. The frame contains schema/domain, fresh host nonce, original QPC ticks/frequency, deadlines, preparation/study invocation identities and exact installed source/runtime/protocol/budget pins. No timestamp or key comes from argv/environment. Linux returns the current boot ID, native process start identity, time/mount namespace identities, unit/cgroup identity and original Linux start. Existing native-close signature envelopes remain canonical; the protected signer and verifier runtime must be established before their crypto/provider import. Exact original process handles/pipe identities and the signed nonce/pins are joined; a pipe or HMAC alone does not prove Linux origin. EOF, replay, duplicate fields, oversized frames, peer/boot/namespace drift or deadline expiration latches failure. An unproved transport origin keeps the production _load_authenticated_outer_qpc refusal.

**Linux native seed and controller.** The root native parent captures CLOCK_MONOTONIC and parses its first MemAvailable sample in a fixed buffer before clone/fork of the controller. It holds its parent/child pidfds and original absolute deadlines. It creates the replay claim on the already hard-capped guest control filesystem with O_EXCL and fsync; the claim's allocated file plus directory/FS overhead is charged, not just JSON length. It configures the already existing unit/cgroup before releasing the child, rather than accepting ExecMainStartTimestampMonotonic as pre-fork authority. The child records birth/start ticks and boot/time namespace, receives the original start in a sealed memfd (WRITE/GROW/SHRINK/SEAL), makes the descriptor non-inheritable after consumption and execs the pinned interpreter with -I -S -B. Parent and observer stay outside the scientific cgroup, inside the original external scope. The native seed is synchronous and does not add a guest role daemon. At most controller + formatter OR controller + scientific worker occupy TasksMax=2; every formatter thread is counted and wait/reap precedes worker birth. Actual support, formatter thread count, available RAM, cgroup placement and absolute deadline producer must be measured later; absence rejects before new work.

**Continuity.** scripts/route2_preimport_launcher._require_actual_start_origin and linux_start_clock._require_actual_start_origin consume the same installed native issuance and held original identities. linux_start_clock._claim_once consumes the already issued replay claim, without reopening a public origin factory. The original native PID/boot/time namespace, memfd OFD, deadlines, QPC challenge and source/runtime pins stay continuous through exec, bootstrap, production_metadata, original controller and terminal. Healthy same-owner state is required at each transition; failure burns the attempt and retains its objects. Neither systemd property snapshots nor a new approval flag removes the native-origin gate.

#### 4.3 Actual storage deployment, caps and complete fee scopes

The future dedicated Windows E layout is the sealed physical carrier plus external E area: E30GiB = carrier24GiB containing guest20GiB + external E6GiB. A native preparation creator resolves E by original volume GUID and held directory/file identity, creates the bounded carrier/VHDX through actual Virtual Disk APIs, partitions/formats/attaches it, creates the bounded guest image and imports/registers only the dedicated WSL2 Ubuntu22.04/glibc2.35 instance. Actual VHD headers, host FS allocation/metadata, nested images and journals are included. Maximum virtual size is not a physical allocation proof. CreateVirtualDisk/GetVirtualDiskInformation and FileStandardInfo.AllocationSize must report their separate quantities; sparse/preallocated status is not a zero-cost statement. Any physical hard-cap method must constrain all relevant writers, including privileged/service and metadata writers, or stop with E_PHYSICAL_CAP_UNPROVEN. The SOURCE task produces the exact cap owner, quota/volume identity, observed allocation and underlying writer scope; it does not guess a header overhead or claim a directory ACL is a hard cap.

Guest logical usable/actual allocation/physical Windows allocation are three separate accounts. The guest filesystem has a physical 20GiB boundary; before admission its actual baseline (OS, runtime/dependencies, bank, guest control, preparation history/residues) is at most 8GiB. The 64MiB guest control filesystem is independently bounded within guest20. The 16MiB host control filesystem is independently bounded only inside external E6. Whole carrier24 and external E6 include their control caps, filesystems, headers, retained failures and cleanup; they are not extra allowances. A fixed-size virtual disk filesystem with actual queried usable blocks and all writer scope under the original owner is the preferred control mechanism. Failure of that proof rejects; a logical marker length does not satisfy it.

Before formal study image creation, the same original invocation obtains fresh native guest backing-FS free and the actual Windows physical volume carrying its VHDX free, each >=8GiB. Actual source VHDX/GUID/guest device/mount/held parent are joined in that sample. GetStorageDependencyInformation plus held virtual disk, file, volume and storage device identities must resolve the entire guest.vhdx -> carrier NTFS virtual volume -> carrier.vhdx -> original actual Windows physical E chain. GetDiskFreeSpaceEx on the carrier virtual volume is only its reserve observation, not the physical E 8GiB floor. Logical virtual sizes are selected below physical caps as necessary to include proven header/FS/metadata allocation, without adding allowance. The carrier has its separately proven growth/cleanup reserve; there is no third 8GiB floor. LinuxInitialVolumeCreator continues to create the one physical 2GiB Stage A image and LinuxLoopVolumeExpander grows that same image to 4GiB after the legal Stage B entry gate. It does not allocate a second 4GiB image. Generation data/tree images live as allocated files inside that mounted study image, so their storage is included once in the study physical capacity and explicitly itemized as inner use; they are not charged as a second independent outer image. Exact inner free/metadata/headroom and failed residues still determine whether a generation can be attempted.

.wslconfig remains memory8GB/swap0/processors2/guiApplications=false text until actual VM boot proves those settings. The future exclusive window allows complete WSL shutdown, disallows another distro, and does not prove shutdown/config application by itself. Root-owned service state, actual VM ID, distro registration, guest cgroup/kernel features, physical backing and GUID must be recorded from OS producers before formal image creation. Interop/DrvFs automount/network/GUI/GPU devices are absent from scientific worker namespaces. A GPU prohibition is a real device/FD/module exposure check; fixed VRAM8GiB remains part of the whole-task account, with prior/shared GPU fees UNKNOWN_NOT_ZERO until proven.

Resource accounting/enforcement is split precisely:
- Preparation plus compile/ABI: RAM4GiB, CPU200%, 4 actual tasks/threads, 1800s including cleanup60. Toolchain/includes/start objects/linker/intermediate/venv/formatters/import/register/history are classified here; no second compile allowance.
- External observer/helper/launcher/bridge: combined RAM512MiB, CPU100%, 4 actual tasks/threads, 6000s including cleanup60. Windows seed, Linux seed/observer, wsl.exe, signing/pipe bridge and any final exit witness are counted here.
- Study: C=min(4GiB,floor(3*M0/5)); RLIMIT_AS=C/2; memory.swap.max=0, CPU200%, pids.max=2 including controller; actual memory charge/RSS/threads/child placement and peaks are observed, not inferred from environment limits.
- Whole task: RAM16GiB, VRAM8GiB and all VM/kernel/services costs remain a separate complete account. A process Job's committed-memory/process-count limit does not prove RSS/thread limits or capture vmmemWSL/kernel/service costs. No concrete Windows native primitive has yet been shown to enforce the full original WSLVM/kernel/service/thread scope. The cheapest first C00 task audits actual native callpoints and supported primitives, records the exact missing control and retains rejection before new work; this is not an implemented or selected complete enforcement provider. The source prerequisite must enumerate actual WSL/HCS compute-system identity, associated native processes/services, guest root cgroups and kernel charge domains, install supported limits before relevant births, query effective limits and retain raw limit/kill/exit evidence. If those APIs cannot give the required original scope, it returns VM_SERVICE_SCOPE_UNPROVEN before allocation/new work. Neither an arithmetic max(4,C)+0.5 nor .wslconfig is substituted for this proof.
- nonE growth: fixed whole-task native observer tracks all relevant Windows writer scopes and actual AllocationSize/volume changes from original baseline, with 512MiB MONITORED, visible384MiB latching stop-new-work and nominal128MiB cleanup. Accepted in-flight overshoot upper bound remains UNKNOWN; this is not a hard cap. Registry/.wslconfig/eventlog/pagefile/service and deleted-file history cannot be assigned zero or erased when current allocation falls.

Every sample includes original epoch/identity and pre/post allocation/cleanup history. The native observer's own sampling, logs, buffers and loaded closure are charged. Incomplete fee attribution or an unbounded writer scope prevents PASS; it does not establish platform infeasibility.

#### 4.4 Readonly PRE-LOAD closure, bank and bootstrap handoff

**Execution closure before load.** Preparation enumerates PE imports/delay imports and ELF PT_INTERP/DT_NEEDED/RPATH/RUNPATH recursively using bounded byte parsing; it pins the interpreter, stdlib, project tree, native helpers, crypto/provider and transitive OS/user libraries. User closure images are cleanly built, all RW references closed, protected and published through actual readonly verified devices before CreateProcess/execveat/dlopen/import or an initializer. Python isolated startup uses only these frozen trees; interpreter ELF loader and dependency resolution must resolve into them or the explicitly trusted system boundary. No LD_PRELOAD, ambient PATH/site packages, writable DLL search, pycache/core/cache/log path or constructor is allowed. The signer observer has its own full closure, not the study's bootstrap receipt. Actual mapped files, loader path, dependency devices/FDs and provider before-import continuity are checked against the same held creator identities; runtime closure remains unproved until future actual evidence. Cryptography added beyond the old 13-wheel installation requires a newly reviewed full runtime closure, not a silent extra wheel.

**Bank creator.** The noGT preparation creator reads only registered nonGT sources, uniquely indexed by (logical path, expected SHA256); 1757 logical sources total 2.818974GiB is a static logical estimate. It creates a bank data image and integrity tree on the guest carrier, copies by held verified source FD with a fixed buffer, fsyncs each actual object/parent and the FS, closes/unmounts all RW writers, builds the tree with data O_RDONLY, fsyncs/closes tree RW, protects both inodes, and only then creates real readonly loops + dm-verity and a clean ro,noload,nosuid,nodev,noexec/private ext4 mount. The creator-authenticated Merkle root is distinct from each scientific payload SHA256. No GT file/provider/key/history enters the bank. 19894 aliases and their original complete map remain metadata for later role copy; they are not multiplied into the bank. Actual bank FS/image/tree overhead, failed builds and prior preparation are included in <=8GiB baseline and 1800s.

**Bootstrap metadata and fixed role targets.** During preparation create all 105 stable empty /run/route2-input/roles/<SHA256(role_id)> targets, metadata parents and root placeholders before capturing immutable ancestor frames. Early metadata is a real readonly mount. linux_native_path_map._install_original_metadata_path_map gains persistent O_PATH/O_RDONLY directory/ancestor/source-device/namespace/mount references owned by its existing original healthy owner; it currently closes all temporaries. That exact owner supplies a private bootstrap handoff to LinuxInitialVolumeCreator.create_stage_a_volume. The initial mount scan permits only the exact retained metadata mount with its unchanged full identity/flags and the original 105 empty unmounted targets. Every other role/worker mount, stack, drifted inode, writable ancestor or foreign namespace remains rejected. This is a held-owner identity transfer, not deleting the namespace gate or adding an allow boolean. References live through actual study startup and are closed once at terminal or original failure cleanup.

The original full map object, bytes, entry objects, aliases, three nonGT phase sets (stage_a_input, stage_a_reference, outer_control_candidates), and early metadata identity are retained. A directory publication gets one directory mount/device/root identity plus per-file inode/size/hash facts. It does not manufacture per-file mount receipts for a single directory mount, and the GT publisher's old source-frame-preserving semantics are not reinterpreted as byte-copy generation creation.

#### 4.5 CURRENT generation, same-FD consumer and actual R

Only the original controller main thread creates generations. Its monotonically increasing invocation generation number is reserved and durably recorded before the first mkdir/open attempt; attempts, failed creations and actual deletion outcomes are never removed from history. At most one undeleted generation can exist. Backing is study/.role-input/<generation>/data.img + tree.img. Construction mount is /run/route2-builder/role, outside the study mount tree and private; consumer mount is the original fixed whole role directory. No scratch path becomes an input source. Exact allocation size is determined from complete role files plus ext4/tree/metadata overhead and current proven study headroom before create; 89.452081MiB max role logical size and 257 leaves (250+7) do not prove an allocation fit.

Normal state sequence:
RESERVED -> DATA_RW -> DATA_COPIED -> DATA_CLEAN_UNMOUNTED -> FORMATTER_REAPED -> DATA_RW_RELEASED -> TREE_RW -> TREE_DURABLE -> ALL_RW_RELEASED -> INODES_PROTECTED -> DEVICES_RO_VERIFIED -> ROLE_PUBLISHED -> LEASED -> CONSUMERS_DRAINED -> ROLE_UNPUBLISHED -> DM_REMOVED -> LOOPS_ABSENT -> BACKING_DELETED -> COMPLETE.
Each transition requires the actual syscall, held object identity and original deadline; failure becomes POISONED/RESIDUE_RETAINED and cannot start another generation.

Create uses held study directory + openat O_EXCL/O_NOFOLLOW/O_CLOEXEC, fallocate and fstat allocation/device/owner/nlink checks. Formatter is the pinned executable under the same cgroup with original pidfd/wait/reap/status; it cannot overlap a scientific worker. Complete role aliases are copied from the bank by same-FD validated reads, with no GT and no phase subset. After data fsync/syncfs, normal FS unmount, formatter wait/reap and all RW loop/FD healthy once-close, data O_RDONLY is used to build tree while tree remains RW. Only after tree fsync and all RW references are healthy closed are both data/tree inode immutable flags set and checked. All privileged clear/overwrite/raw-device/alias capabilities must belong exclusively to the held trusted creator/cleanup owner; flags by themselves are insufficient. Real readonly loop configuration must be queried, then DM_DEV_CREATE/TABLE_LOAD/DEV_SUSPEND resume/STATUS/TABLE_STATUS must show the exact creator-authenticated root, devices, block sizes, capacity and readonly active table. No ignore_corruption/check_at_most_once; EIO/integrity failure poisons the generation. The ext4 mount must be clean and ro,noload,nosuid,nodev,noexec/private, not merely a ro bind of a writable backing.

linux_role_publication installs only from the same early owner/controller/guard and original bank. path_map.open_verified uses metadata branch only for __study__/preflight_metadata; current nonGT roles go to the original role owner. The role reader opens by held published directory and no-symlink relative alias, checks mount/device/inode/length/regular-file/nlink and original mapping, hashes the SAME O_RDONLY FD, seeks that FD to zero, yields its stream, then rechecks consumed FD/frame/map/mount/active generation and closes once. Read failure is primary; post-check and close failure are preserved as secondaries. A consumed FD integer is never retried or reused as an identity. Nested path-map leases of the same role and original main thread share depth and one generation; a different role or thread rejects. The loader's existing prohibition on nested loader leases is retained; only original path-map sharing is extended.

R is not 105+105. Root SOURCE evidence establishes loader.open_role and open_identity_index both acquire map leases; references.open_role holds its identity-index lease across yielded reference consumption; Stage B revisits inner/outer role inputs and outer-control identity/reference views. The future native/controller history increments R_create_attempt at an actual outermost map acquire, R_published only after real publication, depth separately for same-role nested acquisitions, and R_deleted only after actual complete teardown. Ordered (generation, role_id, first acquire, nested depth transitions, original deadlines, created bytes, copied bytes, formatter status, publish/unpublish/remove/delete outcome) is durable. Role revisits after release create new generations. Stage A N/M/S/B and Stage B topology remain produced only by lawful runtime. Static parsing or READY cannot set an unknown R/cost to zero. Exact complete SOURCE topology can be inspected by the execution agent within its new scope, but actual R is still an OS/runtime counter.

#### 4.6 Worker, GT and poisoned cleanup

The controller's writable study paths are only ledger/lock, scientific artifact paths already fixed by approval, .role-input and .worker scratch/log. .worker keeps 4096 cumulative creation/deletion history, 256 scan, regular nlink1; input history is separate and complete, not a cap increase or reset after deletion. Worker root is an explicit actual mount composition: readonly runtime + source; exact current nonGT role directory where needed; current released GT view and optional historical final-match row; fixed readonly empty /readonly; minimum private /proc and /dev without writable devices/network/interop. Scratch/log writable mount is supplied only to a worker whose existing approval explicitly permits its exact paths; the phase worker's current RLIMIT_FSIZE=0/readonly environment stays unchanged unless that exact existing write contract requires a separately reviewed alteration. No generic /tmp, HOME, cache, arbitrary host path, inherited backing/loop/dm/cgroup/signing FD or unrestricted proc access appears.

native route2_phase_spawn.child_main retains UID/GID65534, empty groups/capabilities, no_new_privs, private mount/IPC/network/UTS namespace, pidfd parent liveness, READY→permit, RLIMIT_AS=C/2, original task limits, seccomp no new task/socket/privileged mount/device operations, and exit-driven IPC close. Before READY the native parent verifies complete mount composition, backing identity, child /proc fd/maps/cwd/root/cgroup/namespace/credentials and actual task count. CPU/RAM limits are effective queried OS state, not BLAS environment variables alone. NonGT materialization and the GT science phase keep their existing scientific functions and fixed candidates/models/scores/26D/matcher. If a workload needs a library syscall denied by seccomp, the source task identifies the exact call and readonly/scratch impact before a new reviewed allow entry; no blanket permissive fallback.

Normal GT lifecycle remains the one original broker grant -> current phase publisher (source-preserving GT/historical mounts) -> original worker outcome/wait/reap -> consumer/reference drain -> phase unpublish -> broker revoke. Exactly 20 GT-backed evaluations and GT-free pooled21st aggregation; pooled GT reads remain zero. Metadata, GT payload and commitment/signing keys have separate consumers and namespaces. The generation copier never calls GT. Stage B retains final matched-GT gains/losses and five-field historical isolation; candidate coverage is reported separately.

A new original cleanup authority is installed before first OS acquisition, with a private registry of every actual issued pidfd, FD/OFD, mount ID/device, loop association, dm UUID/table and backing/parent identity. It is tied to the original invocation/controller main thread and original absolute cleanup deadline. Its emergency entry accepts the original primary exception object, freezes new work and operates on that registry even after guard/broker/publisher healthy state is poisoned. It does not call normal revoke, reconstruct authority from path/receipt, reset the failed owner or retry a consumed close.

Emergency sequence: retain primary inline -> stop permits/new work -> pidfd_send_signal(SIGKILL) only for original owned live children -> bounded waitid/pidfd wait + reap -> drain consumer FD/maps/cwd/root/mount references -> actual phase and role unpublish -> close DM block/query FDs -> issue actual DM removal and query absence via original control fd -> close loop holding/query FDs before requiring association absence -> close retained RO backing references as owned -> verify original backing/parent identity, clear protection only under trusted cleanup capability, unlinkat and fsync held parent. DM control FD may remain until table removal is proved; no consumed dm/loop FD is reopened as the old object. Loop removal may be delayed, but absence must be observed before deadline. No lazy unmount is accepted as destruction proof. Unknown unmount/remove/close/reap/delete retains residue, costs and original registry and blocks next role and terminal PASS. VM exit is never evidence that the earlier file was deleted. Emergency cleanup facts are distinct from a successful GT revoke event.

#### 4.7 Terminal join, final durable QPC and the final owner gap

Controller normal terminal first proves role/GT/worker closure and actual ledger+lock close; only then the original external Linux signer consumes the authenticated native-close channel and signs the closed original identity. The Linux witness checks the original systemd unit inactive, original pidfd/process exit, raw cgroup empty, exact backing/FD/mount histories and retained ledger identity, then issues its signed post-exit observation. It closes its own resources and exits. It cannot sign proof of its own final exit.

A different original Windows native owner, already charged, holds the original wsl.exe/observer transport process handles and raw exit/timing observations. It verifies the signed native-close/Linux-exit pair, waits the Linux observer/transport exit, observes the dedicated unit/raw cgroups/services stop, and in the authorized exclusive window requests full WSL shutdown. It requires actual VM/compute-system disappearance, relevant service/workload termination and final backing allocation/history observations. Merely waiting for wsl.exe exit or seeing no running distro is insufficient. It flushes the fixed external-E anchor through held file/volume identity, records native final-durable QPC after successful flush/verification and closes its consumed execution handles under the same original external deadline.

That durable QPC proves only work completed before that sample. The Windows owner is still alive and charged. A separate final native/kernel witness task must join its original process handle/kernel creation identity, actual exit and any remaining trace/writer buffers and durable final timing. Proposed implementation must use actual independent kernel process-exit production (e.g. a pinned kernel ETW ProcessStop identity with raw QPC clock provenance), not the owner's signed self-report; ETW recording alone does not prove a post-exit file flush or a thread/resource cap. Any native consumer/trace writer/service is identified, bounded and charged inside original external/whole-task scopes. Until supported native/kernel producer, final-flush semantics and the complete writer/exit join are demonstrated, source returns OWNER_EXIT_JOIN_UNPROVEN, retains external residue and cannot assert whole external scope closed. No new uncharged ancestor, recursive “observer of observer” or automatically accepted ETW file is introduced. This is the exact final conditional prerequisite, not a disguised completed architecture fact.

#### 4.8 SOURCE boundaries, API evidence and semantic coverage

Official semantics used for these choices were fetched with Context7 resolve-library-id first, followed by separate Job, virtual-disk, dm-verity and cgroup queries. Unmatched Virtual Disk/ETW queries were not treated as evidence; exact Microsoft pages were read as fallback. Job limits concern associated processes and committed memory, while its ActiveProcessLimit is a process count; the architecture therefore requires separate actual thread/VM scope proof. [Microsoft Job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information). .wslconfig applies at VM startup and complete shutdown is a distinct action. [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config). Virtual maximum size and physical disk path are distinct native properties. [CreateVirtualDisk parameters](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-create_virtual_disk_parameters), [GetVirtualDiskPhysicalPath](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskphysicalpath). dm-verity is configured with an authenticated root and actual readonly table; cgroup swap/thread domains need real queried state. [Kernel dm-verity](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/verity.html), [Kernel cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html). These references establish API semantics, not this machine's installed features or PASS.

The authoritative per-component checkbox steps, native signatures, exact isolated AST/hash and path-specific Git commands are in the original plan's new “B component SOURCE implementation plan”. Coverage of the original fourteen gates is explicit there; the final updated fourteen-item minimal-condition table below is the only complete A+B card update in this author turn.

Exact author SOURCE body-read list (30; symbol scans count as bodies): windows_preparation_job.py; windows_control_identity.py; windows_wall.py; windows_non_e_monitor.py; windows_native_close_handoff.py; linux_initial_volume.py; linux_production_controller.py; production_runner.py; linux_native_path_map.py; path_map.py; linux_phase_publication.py; linux_phase_runner.py; linux_child_launch.py; linux_gt_history.py; linux_cgroup_backend.py; linux_start_clock.py; startup_ownership.py; terminal_observation.py; linux_native_close_handoff.py; linux_post_exit.py; linux_quiescence.py; phase_worker_entry.py; phase_worker.py; linux_volume_backend.py; native/route2_mount_helper.c; native/route2_mount_helper.h; native/route2_phase_spawn.c; native/route2_phase_spawn.h (all under src/eating_event/route2_candidate_overlap); scripts/route2_preimport_launcher.py; scripts/run_route2_candidate_overlap_wsl.py. Root independently reads stage_a_replay.py, stage_b.py, inputs.py, references.py, features.py, gt_provider.py, control_matches.py, source_snapshot.py, runtime_identity.py, admission_bootstrap.py. execution.py is not a 41st body; prior finalize repair is inherited, not redone.

#### 4.9 Complete A+B minimal conditions — this turn's single final update

**PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED.** This candidate adds completed component design/steps, with fresh SPEC and fresh QUALITY still pending after author stop. No new production component or runtime PASS is claimed. Root has preserved exact bytes with .gitattributes and checkpointed/pushed existing SOURCE groups to the feature branch; those Git snapshots are unreviewed SOURCE, not a standalone installation/freeze. Original eleven A2 staged entries and unrelated dirty/untracked work remain preserved. Remote main is unchanged.

| Gate | Confirmed / SOURCE / new document result | Remaining actual minimum condition |
|---:|---|---|
| 1 | Existing source-registration/safe projection stay PREPARED_UNREVIEWED; owner commissioned this architecture/plan. | Same complete installable runner, actual identity/cost, full independent review and consumable FrozenAdmission; full FAIL remains. |
| 2 | Fixed saved scores/models/26D/.10,.25,.50/decoder600s,min180/matcher; only strict positive overlap vs300000ms gap. | Lawful 105 reference then105 treatment, full current nested cross-OS equivalence, symmetric atol1e-12/rtol1e-10 and exact discrete outcomes; no premature run. |
| 3 | Inherited two source pins/limited SOURCE reviews retained; bank/current-generation/same-FD/handoff source tasks specified. | Real bank creator, complete role creator/publisher/input history, no writable aliases, same-FD actual consumer and complete nested data adapters installed and reviewed. |
| 4 | Fixed25 fit attempts/25 predict/65 decode/20GT+GT-free21st/pooledGTreads0; same2→4GiB design retained. | One actual enforcing ledger, actual Stage A N/M/S/B/R and legal Stage B projection/physical expansion; capacity and lifecycle fees proven. |
| 5 | Prior final matched-GT gain/loss and finalize repairs retained. | Legal A2-004 final matched-pair origin, five-field projection, actual canonical GT/commitment and phase release/revoke; candidate coverage remains separate. |
| 6 | WSL2/Ubuntu22.04/glibc2.35 and original worker mechanisms retained; complete input/GT/write surface and independent cleanup specified. | Actual SID/GUID/UID/namespace/IPC/FD/mount/cgroup/thread facts and complete scratch/input history; 4096/256/nlink1 unchanged. |
| 7 | E30=carrier24 inclguest20+externalE6; dual8GiB plus carrier reserve preserved; physical creation/cap task specified. | Dedicated actual import/register/volume identity, per-study hard cap, header/FS/allocation/baseline/headroom/history and fresh original dual free sample. |
| 8 | C from original M0, AS=C/2/swap0/200%/Tasks2,1200/3600/900+included cleanup60 retained. | Native prebirth origin, actual .wslconfig application, effective hard resource/thread/GPU bounds and complete peaks/charges. |
| 9 | Guestcontrol64/hostcontrol16 included; prep4GiB/200%/4tasks/1800, external512MiB/100%/4tasks/6000 fixed. | Actual whole VM/kernel/service enforcement/accounting scope and all historic/future costs; VM_SERVICE_SCOPE_UNPROVEN blocks. |
| 10 | nonE512MONITORED,384 stop-new,128 nominalcleanup, accepted overshoot UNKNOWN retained. | Original native whole-task writer/AllocationSize/history observer and charged scope/stop evidence; deleted/current fall-back never resets cost. |
| 11 | Native conditional seed, original dual clocks/transport and pre-load closure source tasks specified; no native call this turn. | Actual readonly PE/ELF/interpreter/stdlib/project/native/transitive/provider closure before loading and continuous original startup/host kill producer. |
| 12 | Primary/secondary, original pidfds/OFDs/once-close and poison cleanup/terminal sequence specified. | Actual OOM/crash/quarantine/remove/delete/cgroup/service/VM/observer exit and last owner kernel witness/final durable external join; OWNER_EXIT_JOIN_UNPROVEN blocks. |
| 13 | This is the fresh candidate's architecture and concrete checkbox SOURCE plan; Git exact bytes are preserved. | New candidate fresh SPEC + distinct QUALITY, per-component SOURCE reviews, then full installable formal review ID and complete source/runtime/input/map/protocol/budget freeze. |
| 14 | Route2 remains mechanism diagnostic; Route3v1-003 legitimate COMPLETE/four gates FAIL; no automatic rerun/model branches. | Legal predeclared early stop or complete five-fold Stage B, COMPLETE separately from four quality gates and actual matched-GT report; final deep-learning event F1>=0.66 delivery still open. |

The scientific and engineering outcomes remain separate. Stage A/B legal runs/results=0. This design does not classify engineering UNKNOWN as model failure or fulfilled F1>=0.66 delivery. No authorization prompt/card is changed; no new authorization/freeze/handoff object is created. Author must stop all three-document writes before the new independent reviews.


### 2026-10-11 Fresh SPEC round 1 receipt and append-only repair

/root/b_component_plan_spec_review finished first pass READSTOPPED with two P2 findings: abbreviated staged-index comparison and ambiguous unsupported-C00 SOURCE continuation. Author appended authoritative G/eligibility errata to the original plan and matching spec clarification. No SOURCE/Git/tests/additional SOURCE-body/native/WSL/GT/formal-object operation occurred. Root confirmed original3-only raw changes, preserved prefixes and unchanged eleven staged entries; this is preservation evidence, not freeze/review PASS.

The earlier “architecture completion/completed architecture” and broad NOW_SOURCE wording are superseded by **conditional B architecture and SOURCE task plan**. Full architecture feasibility is not complete. Current C00 NOT_AUDITED allows C00 only. Unsupported/unselected/unproven VM_SERVICE_SCOPE, E_PHYSICAL_CAP or OWNER_EXIT primitive stops dependent C04–C12 SOURCE. After complete C00 component dual review, only enumerated independent C01 declarations/rejections, C02 known Job/raw-identity/observation/rejection and C03 known prebirth/preload-parser/transport-rejection SOURCE parts may continue. No undefined producer/full conditional stack under an unsupported result. Review does not satisfy a missing prerequisite. A fully supported/selected exact-primitive result permits DAG SOURCE continuation; actual runtime/installation/budget facts stay UNKNOWN.

G now uses full git ls-files --stage rows: exactly eleven unique stage0 originals, full mode/full40-or64-hex SHA/stage/path, ordinal comparison before and after EACH exact-path commit, retaining state on failure. Executable metadata guard is in plan errata; no test body is read.

Fresh SPEC second pass is required before distinct fresh QUALITY; no final clean verdict claimed. Author stops all original3 writes after repair. No new full fourteen-item table/card. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED, legal Route2 A/B/results0 and Route3v1-003 COMPLETE/four-gatesFAIL remain.


### 2026-10-11 最终限定双审与保留核收尾
- fresh SPEC /root/b_component_plan_spec_review 第二/最终轮已完成、READSTOPPED：NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_PLAN_REVIEW_ONLY。
- 不同的 fresh QUALITY /root/b_component_plan_quality_review 已实际完成、READSTOPPED（约12:57 UTC），同一限定结论；两者只审最新候选+errata 文档，无 SOURCE body、运行或修改。第一轮两项 P2 经一次 append-only 修订关闭。
- 当前 C00=NOT_AUDITED，仅 C00 可启动。unsupported/unselected/unproven VM_SERVICE_SCOPE/E_PHYSICAL_CAP/OWNER_EXIT 时 STOP C04–C12 even SOURCE；C00 组件双审后也仅允许已枚举独立 C01 接口/错误/拒绝声明、C02 已知 Job/raw identity/observation/rejection、C03 已知 native prebirth/preload parse/transport rejection 部分。
- 完整架构可行性、VM/service/thread 实际硬控制、physical E cap、最后 Windows owner 独立 durable-exit witness 仍 NOT_COMPLETE/UNKNOWN；无正式 full implementation ID、runtime/budget/freeze/admission PASS，文档双审不满足缺失的 native primitive。
- root 实际静态核：63份 Python 仅隔离 AST；69份既有 Route2 working-file hashes 与 Git blobs 原字节一致；404项保留范围仅原三文档 append 变化、旧前缀完整、无增删；原11项完整 stage/mode/fullSHA/path 不变、两份授权文档原字节不变。这些样本不是完整 runtime freeze。
- Git 由 root 执行：当前8个限定提交、HEAD=80f9f6a；现有 origin feature branch 已创建且已推至 d848d6b。最终文档提交/推送及 remote HEAD 验证尚由 root 随后完成；本记录不提前宣称完成，main 不改。
- 本轮3个不同 agent 为 author、SPEC、QUALITY（follow-up 不另算 agent）；作者 SOURCE body30+root10=40，不增加第41份；无 SOURCE mutation、测试/GT/native/WSL/正式对象操作。
- telemetry：root 全局60分钟 UTC12:09:47–13:09:47；作者初轮实际12:17:14–12:41:17（25分钟内），修订实际12:47:47–12:51:26，最终本次仅2分钟收尾。全部未知历史/等待/归属费用仍 UNKNOWN_NOT_ZERO。
- PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED 保持；合法 Route2 A/B/results=0，Route3v1-003 合法 COMPLETE/四门FAIL。Route2仍机制诊断，最终深度学习 event F1≥.66目标未交付。
- 作者完成本收尾后停止原三文档全部写入；不新增第二张14项卡、handoff、授权或冻结对象。


### 2026-10-11 Git 实际完成收据（核至 UTC13:01:47）

root 已实际提交 7c96c1b941e29ad41156154c6d055ca1005d2991（conditional architecture/spec＋限定双审两文档）及 8d92ebd77b4af34e58b36a9ef83ab5bfad9b5858（617行 component SOURCE plan）；截至此核共10个新限定提交，non-force push SUCCESS。
UTC13:01:47 git ls-remote 实核 origin/codex/high-f1-event-stack-execution=8d92ebd77b4af34e58b36a9ef83ab5bfad9b5858；main 仍 dd05aa128f8d62a85c20a83f8af72fe13fcfa27b。本事实在该已核时点取代前收据“最终 Git pending”。
提交后75份已查 Git blobs 与 working bytes 完全一致（69份 SOURCE/launcher/requirements＋原三文档＋两授权文档＋.gitattributes）；原11项完整 staged mode/fullSHA/stage/path 不变。此样本不是 runtime freeze 或实现/预算/实验 PASS。
C00-only、完整架构可行性 UNKNOWN、原 full FAIL/FrozenAdmission=None/NOT_EXPERIMENT_AUTHORIZED 与零合法 Route2 A/B/results 保持。root 随后才提交本 Git 收据并推送/核新的 final HEAD，本条不预造该 hash 或宣称后续推送已发生。
作者仅追加本 review 后停止写入，无 SOURCE/Git/新对象操作，不新增14项卡、handoff 或授权。


### 2026-10-12 C00 API audit receipt - author stopped, component reviews pending

/root/c00_author completed C00 only against HEAD67311c0d4a7fdda5ffb544074b5508c3c7cf4c40. The original execution plan's latest C00 audit contains exact scope/callpoint/native-signature/build/query/failure/cleanup tables, the complete required witness/writer cost inventory, separate public/local ledgers and five unchanged SOURCE hashes. Context7 WSL and official Microsoft Learn were retrieved; no machine probe/test/project/native/runtime operation occurred.

Result=**AUDITED_UNPROVEN / DONE_WITH_CONCERNS / NO_SOURCE_DELTA**. Known Job set/query/job-list birth covers associated-process commit/CPU/active processes, not RSS/four actual threads/VM/services/kernel. Toolhelp snapshots observe native identities, without lifetime hard control. Generic HCS operations do not select supported ownership/complete charging of the original WSL-managed system. Virtual Disk allocation/query and per-user quotas do not select an all-writer physical E/control cap including FS/VHD metadata. Process signal/ETW End and post-exit persistent flush/writer exit are separate. No complete independently operated final-owner producer is selected; a witness cannot sign its own final exit.

Existing refusals stay unchanged; named audit blockers=**VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN**. ALL local installed/runtime facts UNKNOWN; costs/counts UNKNOWN_NOT_ZERO. No universal/local impossibility is inferred. C00 fresh SPEC then different fresh QUALITY are pending; a future clean scoped verdict is SOURCE_API_AUDIT_ONLY, not full architecture/runtime PASS.

Until both C00 reviews finish, C00 only. Thereafter these blockers STOP dependent C04-C12 even SOURCE. Only errata-enumerated independent C01 declarations/rejections, C02 known Job/raw identity/observation/rejection and C03 known prebirth/preload-parser/transport-rejection slices can proceed. Recommended next slice=C01_DECLARATIONS_ONLY: plain value/error/state/named rejection + dormant v2 header/target guards preserving v1, no registry/provider/new success gate and no whole C01 PASS. No wrapper can supply an undefined missing producer.

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / original full FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED and zero lawful Route2 results remain. Original card/prompt/science unchanged. Original3 append only, no native/source delta/V/G; author stop=2026-10-12 10:56:37 UTC, READSTOPPED / WRITESTOPPED. Root dispatches fresh SPEC then distinct fresh QUALITY.


### 2026-10-12 C00 SPEC first-pass P2 contract repair

Fresh /root/c00_spec first pass stopped with one P2, no P1/otherP2. Sole author appended the original plan's "C00 SPEC round 1 P2 repair" with UpdateProcThreadAttribute/CreateProcessW/GetThreadTimes/GetExitCodeProcess exact signatures, requirements/access/failure/owned callpoints/cleanup and explicit wait/flush/trace minimum-version floors. These targeted official docs complete the missing contract evidence; no new platform selection or source/native/Git/runtime operation occurred.

Normative fixed final preflight field is **Recommendation = REDESIGN**: stop dependent complete SOURCE until necessary concrete producers are selected; confirmed B/WSL/science/budgets unchanged, no local/global impossibility claim. VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN and NO_SOURCE_DELTA remain. Original admission refusals/zero lawful results remain. Second SPEC then different fresh QUALITY pending, no guessed PASS. Author stop=2026-10-12 11:08:01 UTC; READSTOPPED / WRITESTOPPED.


C00 first-pass P2 repair also appends the original plan's QPC timing-contract supplement: exact QueryPerformanceCounter/QueryPerformanceFrequency signature/header/lib/DLL/minimum/failure/provenance, no new producer. Recommendation=REDESIGN and all three UNPROVEN blockers/NO_SOURCE_DELTA unchanged. Final repair author stop=2026-10-12 11:09:06 UTC; READSTOPPED / WRITESTOPPED; second SPEC and distinct QUALITY pending.


### 2026-10-12 C00 actual scoped dual-review and preservation receipt

Fresh SPEC /root/c00_spec second/final pass completed READSTOPPED with NO_REMAINING_SCOPED_P1_P2 / C00_SOURCE_API_AUDIT_ONLY; its first-pass single P2 contract omission was repaired. Different fresh QUALITY /root/c00_quality actually completed READSTOPPED/WRITESTOPPED at UTC11:17:36 (5m36s), with the same scoped verdict. C00 factual SOURCE/API audit scoped dual review is complete; result remains AUDITED_UNPROVEN / DONE_WITH_CONCERNS / NO_SOURCE_DELTA. VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN persist. Reviews establish scoped audit completeness, not selected complete controls, architecture feasibility or runtime PASS.

Root verified current preservation:402 Git-listed project files, only original3 append changes with no additions/deletions and old raw prefixes intact;69 Route2 source/launcher/requirements working bytes exactly match HEAD; protected11 full mode/blob/stage/path entries unchanged. Baseline origin feature HEAD67311c0d4a7fdda5ffb544074b5508c3c7cf4c40 and main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b were verified read-only. Exact original3 Git checkpoint is still pending root action after this author stops; no new commit/push hash or success is invented.

C01_DECLARATIONS_ONLY is next eligible independent SOURCE slice, not whole C01 completion: plain value/error/state/named rejection and dormant v2 header/target declarations preserving v1; no registry/provider/success gate or wrapper claiming missing scope. STOP dependent C04-C12 even SOURCE. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED and zero lawful Route2 A/B/results remain. Original B/WSL/science/budgets/card/prompt unchanged; no runtime authorization. This receipt does not start another component, reset C00's gate/root budget, or claim original budget completion. Root's original soft deadline remains UTC11:38:32.

Sole author appended original3 only, with no SOURCE read/mutation, search, tests, Git or runtime operation. Receipt author stop=2026-10-12 11:18:53 UTC; READSTOPPED / WRITESTOPPED after prefix verification.

### 2026-10-12 C01_DECLARATIONS_ONLY author checkpoint (fresh reviews pending)

C00 is closed as AUDITED_UNPROVEN / NO_SOURCE_DELTA after actual freshSPEC and different freshQUALITY found NO_REMAINING_SCOPED_P1_P2 / C00_SOURCE_API_AUDIT_ONLY. Its actual documentation Git receipt is `4abba28c5cf86982de1e64929ec5cf0dad267e6c`, pushed and remote-verified at UTC 11:20:22; remote main remains `dd05aa128f8d62a85c20a83f8af72fe13fcfa27b`. The three necessary C00 primitives remain UNPROVEN. C04-C12 remain STOP even for SOURCE.

The explicit erratum permits this independent C01 interface/error/rejection declaration objective only. The sole author started at UTC 11:21:47 with a seven-minute budget; source writing/checks ended at UTC 11:24:37 (170 seconds). The C01 component soft budget is UTC 11:20:22-11:40:22, while the original root 60-minute soft deadline remains UTC 11:38:32. Meaningful checkpoint reason: the C00 P2 documentation repair and sequential fresh reviews consumed time; this next C01 objective is an independent declaration slice permitted by closed C00, with no native gate reset, budget reset, or new platform search.

Actual source delta: new `src/eating_event/route2_candidate_overlap/b_source_state.py` declares only the 21 GenerationStep Enum(auto) values, frozen/slotted NativeFault, slotted OwnedDescriptor, and BFailure retaining the exact primary and secondary objects with the approved stable message. Ordinary constructors are values and do not establish original ownership, approval, scope proof, or a rejection receipt. No registry, state machine, consumption/close, consumer/wiring import, or authority factory was added.

The existing `src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c` and `.h` now require exactly one explicit `R2_TARGET_WINDOWS_SEED`, `R2_TARGET_LINUX_START`, or `R2_TARGET_MOUNT_LIBRARY`, rejecting simultaneous/missing/wrong-OS selection. There is no default target. Platform includes sit behind their targets; _GNU_SOURCE precedes Linux system headers. Reviewed Linux x86-64/glibc 2.35/SYS_UAPI guards apply to both Linux source targets. Only the mount-library branch retains existing v1 bodies. The header adds dormant SOURCE_ONLY / NOT_IMPLEMENTED v2 scope-result, error, birth, verity-spec/result, and four function declarations. No new function body, stub, provider, seed/start operation, publisher/remover, constructor, loader, or automatic entry exists.

Context7 resolved `/websites/python_3_10` and queried the single dataclass-record topic (frozen/slots/typed fields); the official Python 3.10 documentation supports the declaration syntax: <https://docs.python.org/3.10/library/dataclasses.html>. No broad SDK or production API search occurred. User no-tests/source-only restrictions take precedence over TDD. Execution routing is sole author followed by freshSPEC and a different freshQUALITY, then root-owned Git; author stops before either review. Scoped author status is DONE_WITH_CONCERNS / C01_DECLARATIONS_ONLY, not whole C01 PASS. C01 consumption/error continuity/provider parts remain unimplemented and blocked/deferred. Source Git and both fresh reviews remain pending; do not infer review approval or complete C01 admission from this checkpoint.

Actual isolated `python -I -S -B` stdlib validation exit 0: PY_AST_HASH=1, NATIVE_HASH=2. Source paths, bytes, lines, SHA-256:

- `src/eating_event/route2_candidate_overlap/b_source_state.py`: 1737 bytes, 65 lines, `a9df70bad715bf645317f4abf3b95ad285494feab87773c31633f7b3d4d9628f`.
- `src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c`: 3678 bytes, 89 lines, `bd9a2b0504c8e14523432f5a498de0aeeba4d8db59bb1bc548951616b2e38a4e`.
- `src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h`: 3897 bytes, 105 lines, `5c357486315470206635a245d0ac7c7ef006eb37db21918abf942746e2efc142`.

Legacy function text before/after is exactly 1300 bytes / `86b59f0ac8a610b56a47f5ab563e931e88b0fdab8f69c4ee0a52fa38246d53be`; legacy v1 struct text before/after is exactly 313 bytes / `8a48210be5d34d864f63150d1a8272d6e86777e0ea0d1642961a852630199ccf`. No compile/preprocess/link/load/call, tests or test-body reads, project import, helper/WSL/OS API probe, GT payload access, production execution, Stage A, formal image-volume-study-ledger-lock-freeze, or Git mutation occurred. No extra source/document/handoff file was added. Original document byte prefixes are retained; only this suffix is appended. Installed runtime remains UNKNOWN; costs remain UNKNOWN_NOT_ZERO; mechanisms remain missing. Existing refusal consumers were not touched.

Preserved states: PREPARED_UNREVIEWED; FROZEN_ADMISSION=None; full FAIL001FAIL; APPLICATION_BLOCKED; NOT_APPROVAL_READY; NOT_EXPERIMENT_AUTHORIZED; zero lawful Route 2A/B/results. Route 3 v1-003 COMPLETE / four-gate FAIL is not rerun. Saved scores/model26D threshold, decoder, matcher, strict-overlap versus 300-second policy, and 105-reference future Stage A remain fixed; F1>=0.66 remains open.

### 2026-10-12 C01 scoped dual-review and source Git receipt

Actual freshSPEC `/root/c01_declarations_spec` completed `NO_REMAINING_SCOPED_P1_P2 / C01_DECLARATIONS_SOURCE_ONLY`, READSTOPPED UTC 11:29:34; different freshQUALITY `/root/c01_declarations_quality` completed the same scoped verdict, start UTC 11:31:18 / READSTOPPED 11:34:09.
Quality had two initial text-hash extraction-boundary assertion failures; corrected verification exited 0, with no source failure/change. Root corrected its combined file-read parameter error, then isolated AST/hash verification exited 0 (`PY_AST_HASH=1`, `NATIVE_HASH=2`), without writes.
Actual source commit is `c228bdf2086174cd3af2e1ba6519c7e910119321`, exactly the three permitted source paths; non-force push and ls-remote verification completed UTC 11:36:53, origin feature at that exact commit and main unchanged `dd05aa128f8d62a85c20a83f8af72fe13fcfa27b`. C00 documentation receipt remains `4abba28c5cf86982de1e64929ec5cf0dad267e6c`.
Root's default diff whitespace check misclassified protected CRLF; it stopped before staging. Corrected per-command `core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol` passed exit 0; no byte/config mutation occurred, and all 11 protected full rows matched before/after the source commit.
Root's 403-file preservation check found only the original three documents plus two native files changed and one new b_source_state.py, with no other additions/deletions; all original document prefixes since 4abba28 remained intact. GT broker/native path map/Stage B matched-GT/execution-finalize/auth-card prompt original hashes remained unchanged.
C00 bounded API audit plus dual reviews is complete as AUDITED_UNPROVEN; the C01_DECLARATIONS_SOURCE_ONLY slice plus dual reviews is complete, while whole C01 remains incomplete. C02/C03 are NOT_STARTED; only their independent erratum slices are next legal. STOP C04-C12 even SOURCE; no further source beyond this slice was authorized or written here.
Three real mechanisms remain missing/unselected, with no local impossibility proof or native-control/provider support claim. Installed runtime UNKNOWN; costs UNKNOWN_NOT_ZERO; runtime experiments/tests/compile/link/load/native calls/WSL/OS probes/GT payload access remain zero.
Manual coverage totals six agents: C00 SPEC two rounds plus QUALITY one; C01 SPEC one plus different QUALITY one. No separate recorder or handoff file was created; this append is the sole final-record writer, with root owning the subsequent documentation Git checkpoint; that future receipt is not invented here.
Root's original soft deadline UTC 11:38:32 is near; if final receipt/Git close crosses it, that is the necessary fact-preserving close within C01 component budget end UTC 11:40:22, with no budget reset or implementation continuation.
All states remain PREPARED_UNREVIEWED, FROZEN_ADMISSION=None, full FAIL001FAIL, APPLICATION_BLOCKED, NOT_APPROVAL_READY, NOT_EXPERIMENT_AUTHORIZED; lawful Route 2A/B/results and payload accesses remain zero. Route 3 v1-003 COMPLETE/four-gate FAIL is not rerun; saved scores/model26D threshold/decoder/matcher, strict overlap versus 300 seconds, 105-reference future Stage A, and open F1>=0.66 remain unchanged.

<a id="route2-three-mechanism-boundary-20261012"></a>
### 2026-10-12 三机制边界细化：具体证据、条件方案与负责人待决项

本节回应补齐三机制的目标；结果是可审阅的条件方案，完整生产机制仍 NOT_COMPLETE / UNPROVEN。新的公开创建链和有限几何证据允许缩小缺项，没有证明本机部署可行或不可行。已选 B、独占 WSL 窗口、科学协议及原数值预算保持；以下新增边界未选择、未实施。

#### 本轮有界工作与复核顺序

- root 本轮起止软预算为 UTC 2026-10-12 11:48:17→12:48:17（60分钟）；workflow_path=RESEARCH，Recommendation=REDESIGN，execution_mode=PARALLEL_SUBAGENT，loaded_profiles=generic。目标仍是完整可执行 Route2 机制诊断及最终深度学习 event F1≥0.66。
- 新证据具体涉及 WSL VM 创建身份、物理 extent 与最后写者边界；因此明确重评为两个只读 researcher＋唯一文档作者＋fresh SPEC＋不同 fresh QUALITY 共五个角色，超过默认三个角色的软指引但仍在同一原预算内。不是 C00 重试、研究门或预算重置；无运行期实验。
- 实际两个 researcher 已结束；root 本轮只读一个项目 body windows_wall.py。本作者只读原三文档尾部并追加其 suffix；SOURCE delta=0。新证据由 researcher 提供，本作者没有另读项目/API body 或本机探测。
- 成功标准是把 producer、全写者、有限额度和最后验收边界逐项说明；缺项保留拒绝。安装版本、实际几何、基线、全部历史/未来费用和 token 账目均 UNKNOWN_NOT_ZERO，不能填零。
- 作者停止全部写入后才开始 fresh SPEC；SPEC 收敛后再由不同 fresh QUALITY 复核。当前两项均 PENDING，只有本节限定文档复核资格，没有完整实现 review ID 或 PASS。

#### 机制一：WSL 创建身份与整任务资源边界

公开源码固定为 Microsoft/WSL commit `449a7eb5c98638bb35cd4d9b4717d090b15ba271`（2026-10-03）。它是外部版本证据，已安装本机版本 UNKNOWN。

- [LxssUserSession.cpp](https://raw.githubusercontent.com/microsoft/WSL/449a7eb5c98638bb35cd4d9b4717d090b15ba271/src/windows/service/exe/LxssUserSession.cpp) 的 `_CreateVm` 先 `CoCreateGuid(vmId)`，再 `WslCoreVm::Create`，之后才 `OnVmStarted`；这给出确切 creator 顺序，插件不是出生前限额者。
- [WslCoreVm.cpp](https://raw.githubusercontent.com/microsoft/WSL/449a7eb5c98638bb35cd4d9b4717d090b15ba271/src/windows/service/exe/WslCoreVm.cpp) 将 GUID 存为 `m_machineId`，生成 `Memory.SizeInMB`、`Processor.Count` 与 terminate-on-last-handle 配置，并核 HCS `RuntimeId` 相等；VM guest 配置机制真实存在。
- 同一路径创建 host collector/init/callback 线程及 wslhost/wslrelay Job；VM destruction 后还有 host threads join 与 helper/file/access cleanup。VM 退出不能代表全部 Windows 工作已经退出或收费结束。
- [common/hcs.cpp](https://raw.githubusercontent.com/microsoft/WSL/449a7eb5c98638bb35cd4d9b4717d090b15ba271/src/windows/common/hcs.cpp) 的 `CreateComputeSystem` 调用 `HcsCreateComputeSystem` 后 `HcsWaitForOperationResult(INFINITE)`；调用方有限等待不能推出 service 内部有限终止。公共 [HcsCreateComputeSystem](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcscreatecomputesystem) 也不自动提供原 WSL 全服务归属。
- WslService 为 SYSTEM/session0，用户会话按 Windows account 建立；[内部 COM IDL](https://raw.githubusercontent.com/microsoft/WSL/449a7eb5c98638bb35cd4d9b4717d090b15ba271/src/windows/service/inc/wslservice.idl) 明示 internal/non-stable。[WslPluginApi.h](https://raw.githubusercontent.com/microsoft/WSL/449a7eb5c98638bb35cd4d9b4717d090b15ba271/src/windows/inc/WslPluginApi.h) / [官方插件文档](https://learn.microsoft.com/en-us/windows/wsl/wsl-plugins) 的出生后 callback 得到 DWORD SessionId/token/SID，运行在 service 地址空间；没有 HCS GUID/held handle 或出生前全 service/thread 硬界。

条件方案只能继续匹配实际 pinned 本机 creator、原 GUID/handle、host service/thread/kernel charge 与清场所有者；尚未选出支持原整任务 scope 的 producer。即使负责人将 4tasks-threads 明确为应用线程，Windows 应用的四 TID 出生硬界、whole RAM16GiB/VRAM8GiB 和服务全部计费仍须另外证明。Job 四进程不等于四线程，commit 不等于 RSS。结果保持 VM_SERVICE_SCOPE_UNPROVEN；不作全局或本机 WSL 不可能的结论。

#### 机制二：有限物理 extent 包含所有文件系统写者

E30GiB 是任务预留，不是现有 E 卷总长30GiB。新增候选是可信 Windows layout owner 在任务专用物理 extent 上持有有限几何，并排除未归属 raw alias/resize 权限；有限 backing FS 使所有正常数据/FS metadata 写入共享同一真实容量边界。布局、实际介质和 owner 均未选择，没有创建分区。

- 物理 carrier backing FS 的 extent `L_C<24GiB`，剩余 carrier 额度扣除任务 disk/partition metadata；物理 external extent `L_X<6GiB`，FS 与 host control≤16MiB 全部内计。dynamic carrier VHDX 放在 L_C 内；其中有限 guest-backing NTFS FS 承载 dynamic guest VHDX，guest VHDX/该层 FS metadata 合计内计 guest20GiB，虚拟 guest size 须扣 overhead 后小于20；guest control≤64MiB 内计20。全部 overhead/格式支持与实际 cohort 仍 UNKNOWN，尤其 host16MiB 格式可行性未证明。
- 若选此新布局，literal physical backing volume GUID/free floor 必须指实际承载 carrier VHDX 的 L_C，不能采原较大的 E 根或虚拟 carrier NTFS。formal study image 前同一 invocation 核 guest hosting FS 与该实际物理 backing volume 分别 free≥8GiB；carrier 只保留增长/清场 reserve，不加第三个8GiB门。
- 因此 L_C 接近24时，当前 carrier allocation＋host FS 必须≤L_C−8（约16GiB）。dynamic guest baseline≤8 可能容纳但仍 UNKNOWN；近20GiB fixed nested guest 会拒绝这个新几何方案，不代表原较大 E 布局一概失败。
- 未来原 Windows owner 用 held `CreateFileW` device/volume 与 `DeviceIoControl` 核 [VOLUME_GET_VOLUME_DISK_EXTENTS](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents)、[GET_DRIVE_LAYOUT_EX](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_get_drive_layout_ex)、DISK_GET_LENGTH_INFO；[SET_DRIVE_LAYOUT_EX](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_set_drive_layout_ex) 只写已选任务 layout。CREATE_DISK 只可初始化任务所有的新 disk，不能初始化现有 E。
- [MSFT_Volume.Format](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/format-msft-volume) 的未来 `IWbemServices::ExecMethod` transport HRESULT 与 formatter ReturnValue/ExtendedStatus 分开验证；formatter/service 费用 UNKNOWN。FSCTL_GET_NTFS_VOLUME_DATA 是几何/计数查询，不是 hard cap。[GROW_PARTITION](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_grow_partition) 可在线增长；[LOCK_VOLUME](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_lock_volume) 有 open files 时失败，不提供使用期几何封锁。必须由原可信 layout owner 保持几何并排除所有越界写入口。
- [GetStorageDependencyInformation](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getstoragedependencyinformation) 核全 held backing chain；GetVirtualDiskPhysicalPath 返回 attached device，不代替实际物理卷 free；GetDiskFreeSpaceEx 必须采确切物理卷。未来清场依次 inner writers stop/join→inner flush/quiesce/close/detach→carrier flush/lock/dismount/close/detach→physical backing/external flush。

所有查询和写者闭合尚未实现；提交异步请求、timeout 或 attempt 标志不证明 rollback/delete/durable exit。原文件 carrier 仍保留未闭合状态，新 physical extent 候选需负责人选择且单独完成 creator/formatter/加载前与预算 producer。E_PHYSICAL_CAP_UNPROVEN 保持。

#### 机制三：最终 durable QPC 的最后验收边界

root 本轮实际读到 `windows_wall._persist_owned`：core/seal 写入、flush/readback→held volume/root close→identity verify→execution lease close→final QPC→返回 ExternalExitObservation，此刻 Windows writer owner 仍活着。

[WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) 等原 process handle signal 可证明对应 process 真退出；[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers) 对 held writable file/admin volume 的完成是 durability 事实。两者都不能证明调用者自己的未来退出；seal 写入前的 QPC 与最后 postflush QPC 也不能混作磁盘里的同一采样。

若逐字要求每个最终 durable writer 都有退出之后的另一个 durable writer，有限 process-writer 链没有最后边界；这是对该要求的条件推理，不是硬件/kernel 全局不可能性证明。尚未选择独立 kernel/hardware final producer。

条件替代是允许一个最终可信外部 coordinator 在 acceptance 后继续存活：它用原 held 身份观察 task controller/worker/observer/VM/service 全部退出，flush 固定 E control receipt，再采 native QPC，给出 live acceptance fact，不声明自己的退出。直到 acceptance 的所有成本进入原预算；acceptance 后寿命、后续任务写入与计费边界必须明确，不能写零。协议、加载前边界、预算与实际 producer 仍未选择/实现，OWNER_EXIT_JOIN_UNPROVEN 保持。

#### 三个已发出的负责人问题仍 PENDING

1. 是否允许最终可信监督者在验收后继续存活，且运行期费用全部计入原 scope；验收后寿命/计费/剩余写入如何明确？
2. 原4tasks-threads 是否仅限制任务应用线程，还是包含全部基础设施 actor；整任务 RAM16GiB/VRAM8GiB 与全部费用仍保持？
3. 是否选择任务专用物理 extent 方案，还是保留原文件 carrier 方案；当前选择只涉及设计，不授权磁盘变更？

推荐选项不是答复；未收到负责人答案/授权，不能绑定任何新边界、重解释 cap、修改原申请卡或启动实施。

#### 本轮唯一完整14门卡更新（旧卡原字节保留）

| 门 | 已知/固定事实 | 仍须闭合的缺项 |
| --- | --- | --- |
| 1 | 原 registration/safe projection PREPARED_UNREVIEWED；负责人委托补齐，原申请卡/prompt保持。 | 同一完整可安装 runner、实际身份/费用、完整独立审与可消费 FrozenAdmission；full FAIL 保持。 |
| 2 | saved scores/model26D/阈值.10,.25,.50、decoder600秒/min180、matcher/五折、strict positive overlap vs300秒固定；对称atol1e-12/rtol1e-10及离散exact。 | 合法105 reference＋105 treatment、完整记录/窗口/来源与当前完整nested跨OS等价；旧 PARTIAL_MATCH_ONLY 不足，不能提前运行。 |
| 3 | early metadata/batch/GT两leaf SOURCE继承；C00公开创建链事实新增但 AUDITED_UNPROVEN；C01声明切片双审完成，whole C01不完整。 | 实际 bank/role creator/publisher、全create-delete/history/无可写别名、same-FD consumer/完整nested与部署；三必要producer尚缺。 |
| 4 | 25 fit attempts/25 predict/65 decode/20GT评价＋第21次GT-free归并、pooledGTreads0；D_A=2GiB strict V2，同image2→4GiB。 | 唯一实际 enforcing ledger、Stage A N/M/S/B/R、合法Stage B投影/实体扩容及全部容量生命周期费用；非2+4累计。 |
| 5 | 原 control/treatment final matched-GT新增/丢失与finalize修复SOURCE继承，candidate coverage另列。 | A2-004合法final matched-pair来源、五字段隔离投影、actual canonical GT/commitment与逐role/phase release/revoke；本轮GT payload零读取。 |
| 6 | WSL2/Ubuntu22.04/glibc2.35、可信Windows owner、原spawn/pidfd/READY/wait/reap/status/UID/namespace/IPC继承；B和独占窗口已选。 | actual GUID/SID/UID/namespace/IPC/FD/mount/cgroup/thread与全部写路径/清场；4096历史/256scan/nlink1不能承接19894 alias/max257输入。 |
| 7 | E预留30=carrier24含guest20＋external6；guest实际baseline≤8；同invocation guest hosting FS/实际物理 backing各free≥8，无第三8门。 | physical extent仅条件候选；owner/全writers/finite geometry、creator/format/import/register、三层actual usable/allocated/header/headroom/history/余额与fresh floor均未闭合。 |
| 8 | 1200/3600/900秒均内计60收尾；C=min(4GiB,floor(3×首次原M0/5))、LimitAS=C/2、swap0、CPU200%、TasksMax2含controller；whole RAM16/VRAM8GiB。 | prebirth t0/M0、实际VM8GB/swap0/2CPU/gui=false应用、cgroup/AS/CPU/thread/GPU硬界及全部峰值/费用；4线程范围问题PENDING。 |
| 9 | guestcontrol64MiB内计20，hostcontrol16MiB只内计external6；prep＋compile/ABI=4GiB/200%/4tasks-threads/1800秒；external全部observer/helper/launcher/bridge=512MiB/100%/4tasks-threads/6000秒，均内计60收尾。 | VM/kernel/services全归属、全部历史/未来/准备/控制/ABI/observer费用和三层baseline/余额UNKNOWN_NOT_ZERO；应用范围答复也不能自动证明整任务cap。 |
| 10 | nonE新增512MiB MONITORED；384MiB停新增，128MiB名义收尾，负责人接受在途超额UNKNOWN。 | fixed whole-task observer、全部Windows writers/AllocationSize/history/收费/stop；旧PS28–29线程不满足4tasks，pagefile回落/删除不归零，128不是实体reserve或超额上界。 |
| 11 | 原13-wheel lock/ABI/venv、4 native C/H、受限ELF/40-byte ABI与conditional seed/dual clock/transport SOURCE任务继承。 | 任何constructor/import/dlopen前 readonly PE/ELF/interpreter/stdlib/project/native/transitive/provider闭包、原Windows QPC认证/Linux prePython-prespawn连续性/host kill；本轮零compile/link/load/call。 |
| 12 | 原primary/secondary、pidfd/OFD/READY/status/wait/reap/once-close/poison清场SOURCE继承；live postflush样本因果澄清。 | 全backing delete/GT revoke、OOM/crash/quarantine、terminal签名join/raw cgroup/VM/service/observer真实退出、最终durable external QPC及最后writer边界；监督者存活问题PENDING。 |
| 13 | C00 SOURCE_API_AUDIT_ONLY及C01_DECLARATIONS_SOURCE_ONLY实际双审仅限原scope；本轮唯一作者文档追加后fresh SPEC→不同QUALITY待做。 | 本轮限定文档双审、完整可安装正式review ID、source/runtime/input/rolemap/launcher/worker/controller/protocol/budget全部冻结；无新full PASS。 |
| 14 | Route3v1-003合法COMPLETE/四门FAIL不重跑；科学四门pooledF1≥.66、≥3/5折F1≥.66、每折longFP≤.25、start/endMAE≤900秒及实际matched-GT报告保持。 | 零合法Route2 A/B/results；须合法预声明早停或完整五折Stage B，COMPLETE与质量门分别报告。深度学习event F1≥.66仍未交付，不自动启动三模型方向。 |

C00仍 AUDITED_UNPROVEN；C01声明SOURCE切片已闭合但whole C01不完整；C02/C03 NOT_STARTED，仅原erratum枚举的独立 C02 known Job/raw identity/observation/rejection 与 C03 known prebirth/preload-parser/transport-rejection 下一步合法。C04–C12继续 STOP even SOURCE；本节不是解除研究门或生产授权。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。无新source/native/runtime/input/protocol/budget冻结，无实现/准入PASS。本作者仅原三文档append、UTF8无BOM保留旧prefix；无额外对象、测试/test body、project import、helper/native/WSL/API probe、GT、生产/Stage/正式对象或Git操作。完成append与prefix核后停止全部写入，root负责实际fresh SPEC→不同QUALITY与后续收据；未知收费不计零。

<a id="route2-three-mechanism-review-receipt-20261012"></a>
### 2026-10-12 三机制限定文档双审收据与中断恢复

原设计作者追加的 +79/+13/+17 行已按原字节保留；三机制仍是条件方案，SOURCE delta=0。先前独立 SPEC 实际结果为 NO_REMAINING_SCOPED_P1_P2 / CONDITIONAL_MECHANISM_DOCUMENT_REVIEW_ONLY，READ_STOPPED UTC 12:23:56；此为恢复既有报告，没有重新执行 SPEC 的声称。
原 QUALITY 调用未取得可恢复结果；root 于 UTC 16:13:14 恢复时没有存活子 agent，实际派发不同 fresh QUALITY。其 UTC 16:15:15→16:16:06，51 秒内只读 review 2753–2831、spec 1842–1854、plan 2434–2450 与限定 numstat；结果同为 NO_REMAINING_SCOPED_P1_P2 / CONDITIONAL_MECHANISM_DOCUMENT_REVIEW_ONLY。P3 仅要求本事实收据纠正作者时点的 PENDING 快照。二者不是完整实现、三机制、运行期、冻结或准入 PASS；旧正文不改。
恢复记录中的原作者软截止 UTC 12:18:00，实际全部写入停止 12:19:43，超出 103 秒，仅 append/prefix 收尾，不能称软截止通过。root 原 11:48:17→12:48:17 窗口在恢复时已过；中断期间活动/资源账目未完整观测，不填零，不称预算通过。用户“继续工作”只使必要复核及版本留存继续，没有回答三项边界选择，也没有重置三机制研究/准备/实验预算。
恢复为 REVIEW_ONLY / 实际 collaboration.spawn_agent，generic；一次 fresh QUALITY，新增实验/因果假说零。UTC 16:19:05 为剩余事实收据及限定 Git 收尾设置 10 分钟软目标 16:29:05；这不是生产授权或重开研究循环。没有独立 telemetry recorder；沿用原三文档人工记录，费用/token 及全部历史/未来准备成本仍 UNKNOWN_NOT_ZERO。
root 只读恢复基线为 403 个 Git-listed 文件原字节 hash、三文档对 HEAD 045b2ea 的完整原 prefix、11 项完整 mode/blob/stage/path。原 GT 两文件 SHA256 仍为 c6b4c57437f87b5e8b695a747467100df2094d49240e6a1da1ecf4e104994bd2、1ca884d50b7e700c0fde4d30b82b755b26539f0b0008d832d6c982bd6988b143；原申请卡及授权 prompt hash 保持。raw hash 不解释 test body，也不是 runtime/source 冻结。
实际文档提交 9fb9bb16738df2ea7abe18e17834080299caf1fe 仅原三文档条件方案 suffix，109 行增加、无删除；exact-path add 与 commit --only 前后逐次核对 11 项完整 staged 身份一致，提交后仍只余原 11 staged。限定 diff --check（cr-at-eol）退出 0，三文档 text=unset，现有 hooks 无活动文件；没有运行测试。只读远程核对原分支 045b2ea0c8b159d31601fea2339b0ca6295fdab7、main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b；收据提交/非 force push/最终保留核尚未发生，不预填。
本收据首次写入时 PowerShell stdin 将非 ASCII 转为问号；root 读回发现，仅修复自身未提交的收据 suffix，核原 9fb9bb1 prefix 字节及当前坏 suffix 的准确 hash 后，用 ASCII JSON Unicode escape 向隔离 stdlib 传参并编码 UTF8。既有文档、设计 suffix、其他 dirty/staged 内容未覆盖；这是本次事实收据的编码修复，不重开组件实现或复审结论。
三项负责人问题仍 PENDING：最终监督者验收后存活/后续费用边界，4tasks-threads 的应用/基础设施范围，真实有限 physical extent 设计。数值预算、WSL2/Ubuntu22.04/glibc2.35、B 与科学合同保持；C00 AUDITED_UNPROVEN，whole C01 不完整，C02/C03 NOT_STARTED 且只允许既有独立切片，C04–C12 STOP even SOURCE。VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN 保持；本机可行或不可行未证明。
PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / full FAIL001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED 保持；合法 Stage A/B/Route2 结果零，F1≥0.66 开放，Route3 v1-003 COMPLETE/四门 FAIL 不重跑。本收据 root 唯一写入，仅记录实际事实，未增加设计/组件实现或再造完整14门卡；无测试/test body、project import、native/helper/WSL/机器探测/GT/生产/Stage、正式对象或其他工作树改写。

<a id="route2-three-mechanism-owner-decisions-20261012"></a>
### 2026-10-12 三项负责人答复：绑定设计边界

负责人逐项明确选择：①“采用外部监督者作为最终验收者（推荐）”；②“约束任务应用执行组，基础设施另行完整计费（推荐）”；③“采用专用实体卷/extent 设计（推荐）”。此前 PENDING 是答复到达前的事实快照，现由本追加绑定以上三项；“继续工作”没有代替具体答复。
最终可信监督者可在验收后继续存活，先观察实验进程及 WSL/VM 服务全部真实退出、持久化 E 回执后验收；截至验收费用全进原 scope，验收后禁止实验写入，其后生命周期/收费边界仍须具体闭合。无需再以另一进程证明最终验收者自己的退出。原 4tasks-threads 约束准备及外部控制的任务应用执行组，基础设施全计费，whole RAM16GiB/VRAM8GiB 不变；Windows 四 TID 出生硬界仍缺，不改称四进程。真实有限实体 extent 选为设计，24/20/6 与全部元数据内计、actual physical backing GUID 与双8GiB门保持；没有授权分区/格式化/磁盘修改。
三答复使条件分支被选择，没有证明实际 producer、部署、预算或准入。C00 AUDITED_UNPROVEN、whole C01 未完、C02/C03 NOT_STARTED、C04–C12 STOP even SOURCE 保持；原三机制 UNPROVEN、全部冻结/准入阻塞和完整 FAIL 保持。先前限定双审只覆盖原条件文本；本追加记录直接答复，不冒充新的完整设计审或实现审。
UTC 16:31:10 明确重评：workflow_path=RESEARCH / Recommendation=REDESIGN / execution_mode=SUBAGENT / generic；三项明确新答复降低原 scope 歧义，选一次 6 分钟有界原生整任务资源可行性复核，截止16:37:10。最多两条因果候选：原 HCS/Job 组合，或真实物理 RAM/VRAM 包络（另区分 OS boot trim/outer VM 父层费用）；不扩大范围、不运行实验，缺实际整基础设施 hard producer 即停止源码实施并给具体残余。新增源码/准备/实验预算均未发号。
原收尾目标16:29:05已过；16:31:10重评时仍未完成收据 Git 收尾，不能称软目标通过或用新证据抹去该事实。本收据只续记实际事实；所有费用仍 UNKNOWN_NOT_ZERO。新只读研究不得写文件，root 暂只完成原文档收据/版本留存，不启动受阻组件。

<a id="route2-selected-mechanism-architecture-20261012"></a>
### 2026-10-12 Selected mechanism architecture: native callpoints and remaining stops

This is a bounded DOCUMENT refinement of the three explicit owner choices already bound above. The external final coordinator may survive acceptance; prep/external four tasks-threads apply to the application execution groups with infrastructure fully billed; actual finite physical extents are selected for DESIGN. No disk operation is authorized. B, exclusive WSL2/Ubuntu22.04/glibc2.35 and every scientific/numeric contract remain fixed. The actual hardware facts and a possible Windows-thread MONITORED change are still PENDING; four original application TIDs remain HARD.
Author start UTC 2026-10-12 16:48:46; component stop deadline 17:08:46 (20 minutes, earlier than root 17:12). This does not reset the expired original root window, the 16:29:05 close target, any preparation/research/experiment envelope, or historical charges. Researcher actual public-resource interval was 16:32:15-16:36:28 before 16:37:10. Author read only original3 latest <=130 lines and plan C00 eligibility 2238-2248, plus applicable skills/public contract references; no source/test-body/project import or local native/runtime probe.
API documentation use: Context7 resolved official Win32 `/websites/learn_microsoft_en-us_windows_win32_api`, then three scoped geometry, exit/flush, and hardware queries. Narrow primary-page fallback clarified signatures/enumeration only; inaccessible or absent exact contracts stay UNKNOWN. These are documentation facts, not installed support, successful calls, fee evidence, or an enforcer. The previous complete 14-gate card remains the sole card; this suffix supplies mechanism deltas.

#### A. Actual physical extents, creation order, and all storage writers

1. Keep actual carrier backing extent L_C <24GiB and actual external extent L_X <6GiB; disk/partition structures, alignment slack and filesystem metadata consume the margins inside 24/6 and the total 30GiB reservation. Shared disk metadata is charged once with an explicit allocation; unknown overhead cannot be omitted. The finite carrier guest-hosting NTFS region is <=20GiB including dynamic guest.vhdx and its filesystem metadata; guest control <=64MiB stays inside 20, host control <=16MiB stays inside external6. A virtual MaximumSize, free counter, quota or requested reservation is not the physical extent.
2. Before creator/formatter/import/registration or task Python, the trusted Windows layout owner must authenticate its pinned native executable, loader/interpreter/provider closure and original account/token, own the whole selected task disk/extent layout, and establish the original budget/time/handle registry. Actual owner, disk, closure and permissions remain UNKNOWN. Privileged SYSTEM/admin/kernel writers must be trusted and billed; a volume ACL does not exclude their raw-device or resize access. Absence of a supported way to close these write entrances rejects this selected layout.
3. The future creator first holds the original disk HANDLE, validates existing disk identity/length and approved dedicated layout, then initializes ONLY a separately selected new task-owned disk if initialization is required, sets its finite nonoverlapping layout, formats the exact resulting volume objects, reopens/holds their volume/root identities, and re-queries disk layout and extents. Never initialize/repartition the existing E root. No disk number, GUID, device path or permission has been supplied as an actual selection here.

| Native callpoint | Exact documented signature / use | Rejection and ownership rule |
| --- | --- | --- |
| Original disk/volume/root open | `HANDLE CreateFileW(LPCWSTR,DWORD,DWORD,LPSECURITY_ATTRIBUTES,DWORD,DWORD,HANDLE)`; `OPEN_EXISTING` for approved existing disk/volume handles, directory semantics for held roots. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew). | `INVALID_HANDLE_VALUE` captures GetLastError before another call; access/share/reparse policy must be selected per handle. A pathname or reopened PID/device alone is not an original identity. |
| Layout creator and held geometry queries | `BOOL DeviceIoControl(HANDLE,DWORD,LPVOID,DWORD,LPVOID,DWORD,LPDWORD,LPOVERLAPPED)`; IOCTL_DISK_CREATE_DISK on the selected NEW disk only, IOCTL_DISK_SET_DRIVE_LAYOUT_EX on its approved dedicated layout, then IOCTL_DISK_GET_DRIVE_LAYOUT_EX, IOCTL_DISK_GET_LENGTH_INFO and IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS on their proper held disk/volume handles. [DeviceIoControl](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-deviceiocontrol). | Check BOOL, immediate Win32 error, returned byte lengths, sector alignment, bounded entry counts, checked offset+length, disjoint extents and whole-disk identity. Bounded size retries require a fresh complete result; a truncated/changed layout never authorizes a writer. These queries do not lock live geometry. |
| Exact formatter object, before publishing a writer | `HRESULT IWbemServices::ExecMethod(const BSTR,const BSTR,long,IWbemContext*,IWbemClassObject*,IWbemClassObject**,IWbemCallResult**)`; use the identity-matched MSFT_Volume object and Format method. [ExecMethod](https://learn.microsoft.com/en-us/windows/win32/api/wbemcli/nf-wbemcli-iwbemservices-execmethod), [MSFT_Volume.Format](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/format-msft-volume). | COM HRESULT and formatter ReturnValue/ExtendedStatus are independent outcomes. A synchronous call can block; semisynchronous completion still needs its exact provider join, finite deadline and billed service cohort. Timeout is not cancel/rollback/exit. Provider schema/binding and format feasibility remain UNKNOWN. |
| Nested image creator within the held parent | `DWORD CreateVirtualDisk(PVIRTUAL_STORAGE_TYPE,PCWSTR,VIRTUAL_DISK_ACCESS_MASK,PSECURITY_DESCRIPTOR,CREATE_VIRTUAL_DISK_FLAG,ULONG,PCREATE_VIRTUAL_DISK_PARAMETERS,LPOVERLAPPED,PHANDLE)`; VHDX type, no parent/source copy, dynamic allocation and selected aligned MaximumSize. Version2 requires VIRTUAL_DISK_ACCESS_NONE. [CreateVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-createvirtualdisk). | ERROR_SUCCESS is distinct from BOOL/HRESULT; failed out-HANDLE is undefined. Exact attach/open rights, parameters and service completion producer are still UNKNOWN, not guessed. Full-physical-allocation near20 is not substituted for the selected dynamic baseline. |
| Actual backing chain, before every formal admission | `DWORD GetStorageDependencyInformation(HANDLE,GET_STORAGE_DEPENDENCY_FLAG,ULONG,PSTORAGE_DEPENDENCY_INFO,PULONG)`; validate the complete versioned dependency chain with bounded buffers. [Storage dependency](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getstoragedependencyinformation). | ERROR_SUCCESS only; failed output is undefined. GetVirtualDiskPhysicalPath identifies an attached virtual disk device, not the final physical-volume free floor. Any unexpected parent, multiple unapproved disks, alias or changed original object rejects. |

4. Hold disk/volume/parent-root/image handles across use and record raw disk identity, partition offset/length, volume GUID, file identity, VHD identifier and every dependency edge. Resolve names to these held objects; deny publication through junction/reparse/hard-link/raw-device/resize aliases outside the approved writer map. Compare observed layout at each handoff against the original registry. IOCTL_DISK_GROW_PARTITION can grow a live partition and FSCTL_LOCK_VOLUME fails with open files, so repeat queries/locks alone cannot make the use interval HARD; the trusted layout owner must actually exclude every competing geometry/write authority throughout it. That authority is still UNPROVEN.
5. Create dynamic carrier.vhdx inside L_C; attach/format its finite guest-hosting region, then create/import the dynamic guest.vhdx inside that region with virtual size reduced for all guest-image headers/logs/metadata. Each mounted-image/format/import/WSL service is a registered writer and billed actor. Carrier/image creation request or successful format does not publish a complete runner. FSCTL_GET_NTFS_VOLUME_DATA supplies filesystem geometry/counters, not a capacity enforcer; physical extent plus the closed writer/resize authority is the proposed enforcer.
6. Before a formal study image, ONE invocation with unchanged held identities and quiescent admitted writers measures guest-hosting filesystem and the ACTUAL L_C physical backing volume GUID, using `BOOL GetDiskFreeSpaceExW(LPCWSTR,PULARGE_INTEGER,PULARGE_INTEGER,PULARGE_INTEGER)` with the exact volume roots. Both actual available/physical free floors must meet 8GiB after all preceding fees. The historical larger E root and the virtual carrier volume cannot replace L_C. Carrier growth/cleanup reserve is not a third 8GiB gate.
7. Thus carrier allocation plus L_C filesystem overhead must be <=L_C-8GiB at that gate; guest-hosting allocation/metadata must leave its own 8GiB. A dynamic baseline <=8GiB may fit but is not measured; near20GiB fixed nested allocation fails the near24GiB L_C geometry with this floor. This is a rejection of that particular selected geometry, not proof that the earlier larger-E design or all machines are impossible.
8. Ordinary host-control filesystem/reader/writer semantics and its <=16MiB bound are retained. Whether the selected formatter can produce the required small control filesystem/region, with its metadata inside that bound, remains UNKNOWN. This suffix does not replace it with raw sectors, a larger control allocation, or a different receipt protocol. Failure to establish that feasibility keeps E_PHYSICAL_CAP_UNPROVEN.
9. Teardown order is revoke creation/publication and join guest/application writers -> flush guest data/control, quiesce guest filesystem, close/detach inner image after its actual service join -> flush/quiesce carrier filesystem, close/detach carrier after actual service join -> remove only original task-owned image artifacts, witness actual unlink/allocation outcome and flush actual L_C -> retain/flush external control for the final coordinator. Each close/detach/delete is its own observed result; request, timeout, deleted name, zero link count or free-space increase does not prove every writer exited or every allocation was reclaimed.
10. Charge physical/virtual creation, format metadata, headers, baseline, dynamic growth, logs, mount/import/register, provider/helper/kernel/service activity, failed requests, retries, historical create-delete, cleanup and the final receipt to their original phases and original 24/20/6 ledger. nonE remains MONITORED 512MiB with stop-new at384MiB and nominal128MiB cleanup, including provider spills/pagefile; the accepted in-flight overshoot remains UNKNOWN. Failed partial creation is quarantined with original handles retained for bounded cleanup, original primary error and secondary cleanup errors preserved; no retry receives a fresh allocation/budget.

#### B. Final external coordinator: original exits, durable sample, live acceptance

The final coordinator is a selected trust boundary with unchanged accounting and loading controls. Before task/native/Python births, its authenticated native owner must retain the original process/thread HANDLEs, creator-issued exact HCS GUID/held HCS_SYSTEM, service/helper callback cohort and original QPC frequency/epoch. The closed birth registry must prohibit further task/cohort births during drain; PID reuse, job count zero, `wsl --shutdown`, service-name lookup or reopening an unproven GUID cannot manufacture this registry. Exact WSL creator transport and complete service/thread/kernel attribution remain UNPROVEN.

| Final-stage native callpoint | Exact signature / interpretation | Failure/stop rule |
| --- | --- | --- |
| Original process/thread exit wait | `DWORD WaitForSingleObject(HANDLE,DWORD)`; wait the original SYNCHRONIZE-capable process or thread handle with remaining original deadline. [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject). | Only WAIT_OBJECT_0 on that original process/thread proves its signaled termination. WAIT_TIMEOUT is failure with actor still unjoined; WAIT_FAILED preserves GetLastError; unexpected result poisons the attempt. Never wait on a handle another actor can close/reuse. |
| Original process result | `BOOL GetExitCodeProcess(HANDLE,LPDWORD)` after its signaled exit; exit status is separately checked. [GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess). | No polling STILL_ACTIVE as the exit witness. Nonapproved exit status, crash or missing original identity rejects normal acceptance and retains raw status/primary error. |
| Exact HCS system and operation | `HRESULT HcsOpenComputeSystem(PCWSTR,DWORD,HCS_SYSTEM*)` with creator-certified ID and GENERIC_ALL; `HRESULT HcsWaitForOperationResult(HCS_OPERATION,DWORD,PWSTR*)` with finite remaining deadline. [HCS open](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsopencomputesystem), [HCS operation wait](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcswaitforoperationresult). | Opening by ID alone is insufficient provenance. S_OK proves that particular operation completed; shutdown operation completion is not all host-service exit. Preserve HCS HRESULT/result JSON; free the returned document with its documented allocator. Timeout/not-started is not VM/service join. |
| Durable fixed E control receipt | `BOOL FlushFileBuffers(HANDLE)` on held writable receipt and required volume handles, after exact bounded writes/readback and all other actor joins. [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers). | Any write/short write/readback/flush failure prevents live acceptance; capture Win32 error immediately. File flush alone does not join an image service or prove its writer exit. |
| Last close and live native timing | `BOOL CloseHandle(HANDLE)` once per original Win32 handle; `BOOL QueryPerformanceCounter(LARGE_INTEGER*)` and original positive `BOOL QueryPerformanceFrequency(LARGE_INTEGER*)`. [CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle), [QPC](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter). | Type-specific HCS/COM/provider resources use their own release, not CloseHandle. A close failure poisons normal acceptance; never blindly retry a possibly recycled value. QPC is native elapsed-time evidence and cannot certify the sampler own future exit. |

Protocol ordering is concrete but NOT_IMPLEMENTED: DRAIN (freeze births/new writes, revoke task/GT authority) -> original application/controller/observer/helper process joins and approved statuses -> exact VM exit -> its host service/callback/thread/cleanup joins -> inner/carrier/backing cleanup and flush joins -> other Windows writer owners release/exit -> COORDINATOR_SEALS -> ACCEPTED_LIVE -> bounded readonly tail/own exit. Every arrow requires its original producer; a data class or caller assertion is not a transition receipt.
The exact HCS exit-event subscription/callback signature, original VM-ID handoff, callback deregistration/drain and WSL service cohort join must be pinned before implementation; they are UNKNOWN here. Subscription must be established before shutdown to avoid missing exit. The original VM exit event and any HCS shutdown result are checked separately; then original service processes/threads are actually joined. Shared WslService activity or an unowned provider cannot be silently excluded or forcibly stopped as if task-owned. No original all-services producer means OWNER_EXIT_JOIN_UNPROVEN and VM_SERVICE_SCOPE_UNPROVEN.
After those joins, sample q_exit_durable in the coordinator with native QPC. Native filesystem/kernel I/O needed solely for this final coordinator seal remains inside its selected final-writer boundary and original billing; it is not relabeled as an already-exited WSL/task service. If seal requires another unowned live helper/provider service, the required cohort closure is absent and acceptance refuses. Write a fixed-size versioned receipt bound to attempt/cohort/held physical backing and external control identities, original QPC frequency/epoch, exit/status records, raw error chain, accounting-through-seal and its own q_exit_durable. Perform complete write, content/seal validation, readback and required file/volume FlushFileBuffers; retain the external control identity through verification. q_exit_durable is ON DISK and is sampled after every required other actor exit, but BEFORE its own receipt flush.
Next finish all fallible receipt/identity/once-close and lease-release work; then sample q_accept_live after the successful final flush/close barrier and hand off the same authenticated live result with the same receipt digest/cohort/frequency. q_accept_live is NOT ON DISK. Rewriting the receipt with it creates a later flush and therefore a different live endpoint; this protocol does not do so. A disk-only reader may consume the stored joined-exit receipt but cannot claim the final postflush live acceptance sample or recreate it from a later disk timestamp.
Normal acceptance requires both a durable joined-exit receipt and the live q_accept_live handoff, delivered while the coordinator is alive through the already authenticated bounded channel. The exact handoff completion/deadline accounting producer is still UNKNOWN; a raw return object or pre-send timestamp does not prove successful delivery. If delivery incurs later work, its native completion/time and charges must be included in the readonly tail, without rewriting q_accept_live as an on-disk time or claiming it is the final process exit.
Crash before join/seal/flush, torn or replayed receipt, identity mismatch, unjoined actor, stale/duplicate attempt, failed close/QPC, rejected exit status or lost live handoff produces no normal acceptance. Retain the original primary fault and ordered secondary cleanup faults; terminate/reap/quarantine only through original ownership. A durable receipt after coordinator crash is evidence of its stored joins, never sufficient to synthesize the missing live acceptance. The coordinator is the sole final experiment writer; once its receipt is sealed it writes no further experiment/E artifact, including late success/failure patches.
Its survival tail is bounded readonly result handoff, original once-close and own exit with deadline=min(original external t0+6000 seconds, original cleanup t0+60 seconds), evaluated in the original authenticated native QPC epoch with checked arithmetic. Cleanup t0 precedes the drain/receipt work; acceptance cannot restart either clock or reserve a fresh60 seconds. Acceptance at/after that deadline refuses normal completion. The existing trusted Windows deadline owner must hold its original process handle, enforce the absolute deadline and observe actual termination if it stalls. That enforcer/termination join is not deployed/proven. Receipt reporting separates measured charges through acceptance from reserved/actual later infrastructure charges; tail fees never become zero or vanish because acceptance occurred. Missing bounded lifetime or tail accounting remains failure. No new final experiment writer is needed to prove this selected coordinator own exit for acceptance.
All coordinator/preloader/writer/observer/helper/launcher/bridge application actors share original external512MiB/100%/four HARD TIDs/6000 seconds; setup/compile/ABI retain4GiB/200%/four HARD TIDs/1800 seconds, both including cleanup60. All VM/kernel/service/formatter/infrastructure activity is fully billed, with wholeRAM16GiB/VRAM8GiB unchanged. Individual billing, provider spill, native deadline completion and every historical/future cost remain UNKNOWN_NOT_ZERO; selected trust is not a budget PASS.

#### C. Conditional whole-hardware envelope and native witness

Research found a conditional physical enclosure: installed DRAM <=17179869184 bytes and the aggregate actual dedicated physical accelerator memory <=8589934592 bytes can bound actual resident RAM/dedicated VRAM even for guest/kernel/services/hypervisor/coordinator. Finite hardware is the enforcer; enumeration is its witness. This is NOT a selected/verified actual-host fact, per-actor billing proof, committed-memory cap, additive shared-RSS proof, or total GPU-allocation cap. The owner hardware answer is still PENDING.
Raw native producer proposal: first establish that the selected Windows machine is the actual physical host under the original trusted topology owner, rather than a virtual SMBIOS/adapter view that omits a parent host; owner assertion alone is not proof. The original authenticated Windows owner calls before any task Python/native/DXCore/provider load has escaped its approved preload closure; records API binding/OS/native binary/provider identities and original boot/cohort/QPC epoch; holds DXCore factory/list/adapter objects; transports bounded raw bytes/statuses through the original parser. An owner-provided hardware description is useful corroboration but cannot replace the actual raw producer. No implementation/probe or preload authorization is supplied here.
RAM callpoint is `BOOL GetPhysicallyInstalledSystemMemory(PULONGLONG)`; initialize an output, require native TRUE and nonzero KB, and checked KB*1024 <=17179869184. Failure leaves the output unusable, not zero. This uses SMBIOS installed RAM; GlobalMemoryStatusEx ullTotalPhys is OS-visible memory and may be lower. [Installed memory](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getphysicallyinstalledsystemmemory). Historical 2026-10-08 OS-visible16890322944 bytes therefore does not prove installedDRAM16GiB.

| Hardware producer step | Concrete native signature / scope | Reject instead of infer |
| --- | --- | --- |
| Factory and all hardware-type lists | `HRESULT DXCoreCreateAdapterFactory(REFIID,void**)`; `HRESULT IDXCoreAdapterFactory::CreateAdapterList(uint32_t,const GUID*,REFIID,void**)` separately with ONE hardware attribute each: DXCORE_HARDWARE_TYPE_ATTRIBUTE_GPU, COMPUTE_ACCELERATOR, NPU, MEDIA_ACCELERATOR. Union all four lists. [Factory](https://learn.microsoft.com/en-us/windows/win32/api/dxcore/nf-dxcore-dxcorecreateadapterfactory), [List](https://learn.microsoft.com/en-us/windows/win32/dxcore/dxcore_interface/nf-dxcore_interface-idxcoreadapterfactory-createadapterlist). | Multiple attributes mean intersection, not union. D3D-only/workload lists miss devices without a Direct3D user-mode driver; a successful empty list is only that list result. Required hardware-attribute support and actual complete host coverage are UNKNOWN. |
| Every adapter, no first-NVIDIA shortcut | `uint32_t IDXCoreAdapterList::GetAdapterCount()`; `HRESULT IDXCoreAdapterList::GetAdapter(uint32_t,REFIID,void**)`; retain every hardware adapter and deduplicate the same native adapter object/InstanceLuid across attribute lists. [Enumeration](https://learn.microsoft.com/en-us/windows/win32/dxcore/dxcore-enum-adapters). | Software/remote/virtual/linked adapters need explicit classification, not missing records. Historical single NVIDIA8151MiB is not proof of every physical accelerator. Failed/missing index or invalid/stale adapter rejects the inventory. |
| Property bytes and capacity | `HRESULT IDXCoreAdapter::GetProperty(DXCoreAdapterProperty,size_t,void*)`, preceded by supported-property/size checks; capture IsHardware, InstanceLuid, HardwareID/HardwareIDParts, DedicatedAdapterMemory, DedicatedSystemMemory and PhysicalAdapterCount. [Property](https://learn.microsoft.com/en-us/windows/win32/dxcore/dxcore_interface/nf-dxcore_interface-idxcoreadapter-getproperty), [Property definitions](https://learn.microsoft.com/en-us/windows/win32/api/dxcore_interface/ne-dxcore_interface-dxcoreadapterproperty). | Missing support/property, unsupported grouping, wrong size/HRESULT, overflow or changed topology is UNKNOWN/rejection, never0. GetProperty can still return for an invalid adapter, so success alone is not a valid inventory. |

Linked physical adapters require exact group/member reconciliation: map each native logical adapter and PhysicalAdapterCount to all disjoint physical members, establish whether each capacity property is per-member or group aggregate, and count each physical memory region once. Record DedicatedSystemMemory and reconcile its system-DRAM/dedicated classification without silently dropping it; conservatively include unreconciled extra dedicated regions or reject. Exact member-capacity API/signature and installed support are UNKNOWN. Node memory Budget/CurrentUsage/AvailableForReservation, DXGI_QUERY_VIDEO_MEMORY_INFO and reservation setters are changing usage/budget values, not physical capacity.
The HARD inference also needs a trusted actual topology invariant for the whole interval including coordinator tail: no memory/GPU/accelerator hot-add or capacity-increasing device replacement can occur. DXCore stale/invalid notifications and re-enumeration are rejection detectors; they do not prevent the first instant of a hot-add overshoot. Original host/topology authority and full hardware grouping remain UNPROVEN. If the selected host exceeds either installed envelope, reject this candidate without declaring all WSL deployments impossible or silently using boot truncation/another machine.
HCS guest8GiB and Job process COMMIT do not enclose every parent/host actor or actual resident RSS; OS boot memory truncation bounds OS use rather than installed DRAM, and an outer VM adds parent/hypervisor costs. Neither is a selected substitute. Even a proved finite hardware enclosure leaves phase C/LimitAS, guest swap0/2CPU/200%/TasksMax2, whole task CPU/time and actual application-thread prebirth controls needing their own original enforcers and billing producers.
Four HARD Windows application TIDs remain the unresolved source/runtime blocker: Job active-process limit4 is four processes, never four threads; after-birth polling or an observed peak4 cannot prove the birth bound. No owner MONITORED answer has arrived. Hardware witness, coordinator privilege or source-only wrapper cannot manufacture a four-thread primitive or omit loader/formatter/helper application threads from their groups.
For composition, preserve one original ledger: preparation including every current/historical research/source/preload/format/import cost -> application phase and all infrastructure charges -> cleanup -> acceptance -> bounded readonly coordinator tail. Physical capacity can enclose aggregate resident/dedicated bytes; it cannot itemize actors, certify budgets/deadlines or clear nonE spill. Missing raw scope/fees remains UNKNOWN_NOT_ZERO and a refusal, even if owner later reports a 16GiB/8GiB machine.

#### Exact remaining eligibility and author receipt boundary

Authoritative plan C00 correction 2238-2248 still governs: C00 AUDITED_UNPROVEN after its scoped dual review permits ONLY independent C01 declarations (already completed in scope), C02 known Job/raw original identity/observation/named rejection, and C03 known prebirth/bounded preload parsing/transport rejection parts. Whole C01 remains incomplete; C02/C03 are NOT_STARTED. Storage creators, HCS/coordinator/hardware providers, dependent bootstrap/bank/generation/publisher/reader/worker/GT/cleanup/terminal/assembly C04-C12 remain STOP even SOURCE until ALL required exact primitives are supported and selected with concrete signature, owner, OS callpoint, effective scope and failure/stop semantics. Installed runtime UNKNOWN alone never authorizes runtime.
VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN and full architecture NOT_COMPLETE/UNPROVEN persist. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED persist. No new freezing/approval/results, formal objects, Stage A/B, preparation, disk change, helper/native/WSL/GT operation, source or Git mutation by this author. Route3 v1-003 remains COMPLETE/four-gate FAIL without rerun; saved model26D/threshold/decoder/matcher and scientific four gates remain; event F1>=0.66 is open.
Actual existing Git receipts supplied by root: 9fb9bb16738df2ea7abe18e17834080299caf1fe and 3709c43ff1e7d1c28258c01d009757efaf0cfb82 were non-force pushed; root ls-remote verified feature3709c43 and main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b, and all11 full staged identities matched. This suffix has no new commit/push or fresh review result. Author stops all original3 writes before root fresh SPEC then a different fresh QUALITY; both new scoped reviews are PENDING.
Author original working-prefix receipt: review592674 bytes/SHA256 b52b9da939872e2de0ee47975444428e435306fbc5aa2a0f3f68ccfcee33a850; spec353874 bytes/4aea0b29fab0c0ef9c3d700b00a9ca4adbb9cd97cd0193b10a7d92c42ba47d46; plan422533 bytes/c3c8be0e8cb0ee95ee34cd06e1efe7d8774ecce7410ecba70c0e833bf71e9fc2. UTF8 append only, no old bytes overwritten. Actual final WRITESTOPPED/READSTOPPED times, suffix counts and prefix verification are measured in the author tool receipt for root to record; they are not invented here.

<a id="route2-selected-mechanism-review-receipt-20261012"></a>
### 2026-10-12 Root receipt: selected DOCUMENT dual review and exact-path Git

Receipt time 2026-10-12 17:24:17 UTC. This factual suffix supersedes only the author-time PENDING review/Git snapshots, not the original full FAIL.
- Sole author start16:48:46, WRITESTOPPED17:06:43.608148, READSTOPPED17:06:43.618129 UTC, before17:08:46. The selected suffix is review2854-2928 +75 lines, spec1864-1873 +10, plan2464-2492 +29. Original HEAD3709 prefixes were byte-identical. Initial cp1252 stdout and OS206 process-creation failures wrote nothing; bounded ASCII JSON chunks completed the append.
- Fresh independent SPEC actual17:13:53-17:16:33 UTC (deadline17:17:53) and different fresh QUALITY actual17:18:15-17:20:13.5009727 UTC (deadline17:22:15) both returned NO_REMAINING_SCOPED_P1_P2 / SELECTED_MECHANISM_DOCUMENT_REVIEW_ONLY. Neither proved SOURCE/runtime, all three mechanisms, budget compliance, freeze, full review or admission. QUALITY reported no actionable P3.
- The extra deadline-owner cohort/lifetime and complete service/VM/HCS handoff remain UNPROVEN: the surviving coordinator choice does not authorize an unjoined additional actor. Stored q_exit_durable and live postflush q_accept_live remain distinct; missing producer, bounded tail or accounting refuses acceptance.
- Actual original owner answers are bound in the preceding owner-decision receipt. Only the NEW hardware facts and Windows four-TID HARD-versus-MONITORED question remain PENDING. Four original application TIDs remain HARD. A recommended option and elapsed time are not an answer.
- [The one complete14-gate card](#route2-three-mechanism-boundary-20261012) remains with the selected delta above: rows7/8/12 have DESIGN/scope/final-boundary choices, while physical objects, prebirth enforcers, full actor billing and runtime joins remain UNKNOWN. Row13 now has the scoped selected-DOCUMENT dual review; no full PASS.
- Root fresh isolated-stdlib raw preservation covered all403 Git-listed project files: only original3 changed, no added/deleted file; all unrelated bytes, original auth card/prompt and both inherited GT source hashes were unchanged. All11 original full staged mode/blob/stage/path rows and main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b matched before/after exact-doc staging/commit/push. This is preservation evidence, not a runtime/source freeze.
- Exact original3 only committed as 29d98ca1b934282c4d745f01ba14e2068ffd9e5e (+114/-0), non-force pushed to codex/high-f1-event-stack-execution; fresh ls-remote confirmed that feature HEAD and unchanged remote main. This later factual receipt has not yet been committed/pushed at writing time. No active Git hooks; static diff whitespace check exit0. One root JSON control-character rejection occurred before any Git command/write, then the literal transport was corrected and the commit completed.
- Root outer17:12 close target had elapsed before the fresh selected reviews/retention/Git close. This is a soft-target overrun for mandatory independent review and fact-preserving completion, not a passed deadline or reset. Original expired root/research/preparation envelopes and all historical charges persist. Model/token/resource telemetry remains UNKNOWN_NOT_ZERO; manual original3 receipts cover actions/times, not missing native billing.
- Final routing remains RESEARCH / REVIEW_ONLY through actual collaboration author -> SPEC -> different QUALITY plus root isolated-stdlib/Git. Preflight remains UNKNOWN/ARCHITECTURE with conditional REDESIGN, not a proven local NO-GO. No further speculative defensive SOURCE work was added.
- PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED remain. C00 AUDITED_UNPROVEN; wholeC01 incomplete; C02/C03 NOT_STARTED with only enumerated independent SOURCE slices eligible; C04-C12 STOP even SOURCE. Route2 Stage A/B/results remain zero; eventF1>=0.66 open; Route3 COMPLETE/fourFAIL preserved. No test/test-body/import/native/helper/WSL/GT/probe or formal object/disk operation.

<a id="route2-owner-hardware-clarification-20261012"></a>
### 2026-10-12：owner 硬件自述与策略待决
- 偏好本地 E 盘 + WSL；OWNER_REPORTED：RAM 16G、RTX 5060、独立显存 8G；NOT_NATIVE_VERIFIED。保留原单位和名称，不推定精确 GiB/字节、Laptop/Desktop SKU、唯一适配器/无 iGPU、物理主机或拓扑。
- 自述仅部分回答硬件问题；原生 inventory/grouping、no-hot-add、prebirth billing、已安装事实仍 UNKNOWN；所有成本 UNKNOWN_NOT_ZERO。
- Windows 应用四 TIDs：HARD 保持原有强制上限及证明要求；MONITORED 接受观测与记录，缺少同等防越限保证。两者仍依赖原有计数、归属和记账边界；用户只问区别与联系，未选择 MONITORED，HARD 维持。
- 安装偏好未授权正式安装、磁盘变更或执行，也不替代 physical 24/20/6 与同次 invocation double-8 下限；CPU、RAM 16GiB、VRAM 8GiB、时间、E 盘上限、Linux TasksMax=2 与 prep、外部任务上限、科学判据均维持。
- C00 AUDITED_UNPROVEN；整个 C01 未完成；C02/C03 NOT_STARTED，仅独立切片；C04-C12 STOP（含 SOURCE）；PREPARED_UNREVIEWED；Frozen=None；full FAIL / blocked / not ready / not authorized / Stage zero。
- Route3 COMPLETE、四项 FAIL、F1 open 均维持；policy 选择与 native proof 仍待决，本追加不构成安装证明或审阅成功。

Root factual receipt: sole author FIRSTCLOCK23:47:56 / STOP_ALL_READS_AND_WRITES23:49:20 UTC (84s within90; separate last-write/read not instrumented). Fresh independent SPEC FIRSTCLOCK23:50:42 / ALLREADSTOP23:51:39 (deadline23:51:42); its initial no-read deadline misunderstanding was clarified within that same60s, not a reset. Different fresh QUALITY FIRSTCLOCK23:52:41 / ALLREADSTOP23:53:07 (deadline23:53:41; exact last-read unavailable). Both NO_REMAINING_SCOPED_P1_P2 / OWNER_FACT_DOCUMENT_ONLY. Root403-file raw preservation: only original3 appended, original prefixes/all unrelated files/auth artifacts/main/full11 staged rows unchanged; static whitespace exit0 and no active hooks. FAST/SUBAGENT factual clarification only; actual collaboration author -> SPEC -> different QUALITY. Root23:52:37 soft close elapsed during mandatory independent review/Git retention close, not a passed deadline or renewed preparation/runtime budget. Manual receipts lack native resource telemetry; costs UNKNOWN_NOT_ZERO. This receipt has not yet been committed/pushed at writing time; no SOURCE/native/runtime/installation/GT/Stage or policy change follows.

<a id="route2-windows-thread-monitored-approved-20261012"></a>
### 2026-10-12: approved Windows application-thread MONITORED policy

- Owner reply "同意" approves the immediately preceding Windows MONITORED + fixed-thread recommendation. This is APPROVED policy, not a PENDING choice; author FIRSTCLOCK is 2026-10-13 00:06:09 UTC (session/local day 2026-10-12).
- Apply only the Windows thread-policy delta to rows 8/9 of the [existing complete14-gate card](#route2-three-mechanism-boundary-20261012); that card and all other gates retain their original requirements.
- Supersede Windows HARD4 / MONITORED-PENDING for BOTH prep/compile/ABI application group and external observer/helper/launcher/bridge/final-coordinator application group. Linux existing tasks/pids HARD limits, including study TasksMax=2, remain.
- The threshold remains four application TIDs groupwide, including application monitor/loader/callback TIDs. Fixed-thread design must cover all births; infrastructure threads stay outside this agreed application count but are fully charged to original budgets.
- Owner accepts in-flight overshoot before detection. Actual peak and overshoot duration/bound remain UNKNOWN; MONITORED is not HARD4 proof, observed four is not actual four.
- All science, CPU/RAM/VRAM/disk/wall limits remain: whole16GiB/8GiB, E24/20/6 and same-invocation double8 floors, nonE512 MONITORED; no installation, disk, WSL, native execution or Stage authorization follows.
- Original prep4GiB/CPU200%/1800 and external512MiB/CPU100%/6000 caps remain, with cleanup60 included. All observer/infrastructure/tail costs remain charged; missing costs UNKNOWN_NOT_ZERO.
- Required producer CONTRACT: trusted original Windows native owner retains creator-issued original process HANDLE, PID, creation-time membership registry and original QPC epoch before births. Caller fields, an empty supplied PID list and PID reopen do not establish identity or complete membership.
- A fixed native observer is itself in its counted and billed application group and in the preloaded closure. Prove membership/birth/detach/escape and phase transitions; declarations are not producers.
- Throughout setup/application/drain/seal/tail, take raw bounded snapshots with q_begin/q_end and checked original process identity/liveness before and after each sample.
- Observed crossing above four OR incomplete, failed or stale observation sets irrevocable STOP_NEW for that invocation: no further workload births, fit, decode or new GT grants. Empty/partial samples cannot be a group-zero PASS.
- Only original actors may drain/revoke/wait/cleanup under original deadlines; preserve the primary failure and cleanup secondary failure. No blind retry, budget reset, resume, or inference of full scientific completion.
- Missing monitor liveness, coverage, original native deadline ownership or fees refuses acceptance. Owner accepted overshoot, not omitted costs or silent monitor failure.
- Poll interval, enumeration-entry/work limits, actual loading/membership and the native STOP_NEW producer remain UNKNOWN until concretely bounded; do not invent numeric configuration or widen existing caps.
- Narrow raw route: HANDLE CreateToolhelp32Snapshot(DWORD,DWORD), TH32CS_SNAPTHREAD only, no inheritance/module/heap flags; it snapshots all system threads and ignores the PID argument. INVALID_HANDLE_VALUE requires immediate GetLastError. [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot).
- Enumerators are BOOL Thread32First(HANDLE,LPTHREADENTRY32) and BOOL Thread32Next(HANDLE,LPTHREADENTRY32). Initialize/reset each appropriate input; false requires immediate error capture. [First](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-thread32first), [Next](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-thread32next).
- Set dwSize=sizeof(THREADENTRY32); validate returned dwSize covers every used field before reading owner PID/TID, and reset the input size as required. Snapshot TID has no creation-time identity. [Structure](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-threadentry32).
- FALSE + ERROR_NO_MORE_FILES establishes enumerator end/empty only. Other errors, truncation, exceeded scan bounds or deadline mean UNKNOWN/STOP_NEW. Only bounded retry is admissible; do not import module ERROR_BAD_LENGTH infinite-retry advice.
- Close each owned snapshot HANDLE once via CloseHandle; failed close poisons raw status and must be preserved, not treated as successful disposal.
- Match enumerated owner PID to the ORIGINAL held-process registry using DWORD GetProcessId(HANDLE), where 0 is error, and BOOL GetProcessTimes(HANDLE,LPFILETIME,LPFILETIME,LPFILETIME,LPFILETIME). [PID](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessid), [Times](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).
- Require stable original creation time and live held identity before/after sampling; original WaitForSingleObject(HANDLE,0) must distinguish exit/error states. FILETIME wall values are not QPC; exitTime is undefined for a live process.
- Process kernel+user accumulators include its threads but omit complete kernel/service/other-actor billing. Do not double-count process CPU plus its thread CPU; these counters cannot certify complete whole-group fees.
- Optional OpenThread(DWORD rights,BOOL inherit,DWORD TID) returns NULL, not INVALID_HANDLE_VALUE. GetThreadTimes BOOL offers supplementary CURRENT held-object facts only; a later open cannot authenticate the original snapshot thread or recover missing history.
- Observed maximum is only lower evidence: short-lived missed threads, scheduling delay and API blocking latency leave actual peak/overshoot UNKNOWN. A thread HANDLE acquired later is not prebirth identity proof.
- No native monitor, bounded stop producer, physical capacity, complete billing, exact WSL GUID/service exit or final durable handoff is newly proven. Owner hardware report remains OWNER_REPORTED / NOT_NATIVE_VERIFIED with original units/name.
- C00 AUDITED_UNPROVEN; whole C01 incomplete; C02/C03 NOT_STARTED; dependent C04-C12 STOP even SOURCE. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / full FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED persist.
- Route2 Stage A/B/results remain zero; Route3 COMPLETE/fourFAIL and eventF1>=0.66 open persist. Prior expired envelopes/charges are retained; this approval does not reset any preparation or runtime budget.
- Original3 DOCUMENT append only; fresh SPEC then DIFFERENT fresh QUALITY follows author STOP. No review/Git/runtime PASS claimed.

Scoped P2 override for the approved Windows MONITORED contract:
Active original membership requires live held original identity before and after each snapshot; this does not require all previously admitted actors to remain alive throughout drain/seal/tail.
JOINED_EXITED membership requires retained original creator identity, native exit with approved status, original join/once-close history and final billing; exclude it from the CURRENT active-TID count only after the actual original exit/join producer, retain all historical fees, never reopen closed handles to reconstruct identity, and keep counting surviving monitor/coordinator TIDs in their application group.
An exit racing the snapshot, missing original join/history/final fees or unclassified membership means UNKNOWN/STOP_NEW, never zero/PASS or an assumed normal joined exit; native producers remain UNKNOWN and all prior policy, budget, science, permission and blocked states persist.

Root factual review receipt (UTC2026-10-13): first author00:06:09/deadline00:09:09/STOP00:09:41,32s overrun retained; initial quote transport and command-size guards made no mutations. Initial fresh SPEC00:11:37->00:12:49 found scopedP2 active-vs-joined-exited ambiguity. Sameauthor exact repair00:14:18->00:14:39 within60s; original budget not reset. SPEC repair verification00:15:48->00:15:56 (deadline00:17:18) and DIFFERENT fresh QUALITY00:17:51->00:18:24 (deadline00:19:51) both NO_REMAINING_SCOPED_P1_P2 / APPROVED_MONITORED_POLICY_DOCUMENT_ONLY; no actionable QUALITY P3. Separate exact last-read/write times unavailable where not instrumented. Root outer00:14:31 elapsed during mandatoryP2repair/reviews/retention/Gitclose, not a deadlinePASS or renewed preparation/runtime envelope. User WindowsMONITORED choice now bound, allothercaps/science/permissions unchanged; nativeobserver and other actualmechanisms remain UNPROVEN, C04-C12STOPevenSOURCE and Stageblocked. Root isolatedstdlib403-file preservation found onlyoriginal3 changes, oldprefixes/allunrelatedbytes/authartifacts/main/full11stagedrows unchanged; noSource/testbody/probes/native/helper/WSL/GT/install/Stage activity. Manual actual-action/time receipts cover this RESEARCH/SUBAGENT author->SPEC->repair->SPEC->differentQUALITY route; native/model/resource telemetry andfees UNKNOWN_NOT_ZERO. This factual receipt is uncommitted/unpushed at writing; it is not SOURCE/runtime/fullreview/freeze/admission evidence.

### C02-B1 exact target and API ledger link (SOURCE only)

Before native edits, the narrow existing-target/function/API ledger is appended to the [original execution plan](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-existing-target-and-api-ledger-source-only). Sole implementer START 2026-10-13 02:02:07 UTC, due ALL_READ_WRITE_STOP 02:22:07 UTC. This permits the independent raw Windows process observer and three existing-name refusals only, pending implementation/reviews; whole C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE and all original blocked/budget/science/UNKNOWN_NOT_ZERO states persist.

### C02-B1 actual raw component author checkpoint (fresh reviews pending)

The [original plan component checkpoint](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-sole-author-component-checkpoint-source-only-fresh-reviews-pending) records actual Windows-only raw process observer and three named UNPROVEN refusal bodies, exact fields, same-access private duplicate/once-close paths, raw native/synthetic error ordering, live versus signaled versus racing-exit semantics, limits and source/prefix hashes. The [preceding target/API ledger](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-existing-target-and-api-ledger-source-only) was appended before any native edit.

Sole author START 2026-10-13 02:02:07 UTC; native edits/first static hash inspection ended by actual 02:12:42 UTC; final ALL_READ_WRITE_STOP and five-file hashes are sent to root before the 02:22:07 UTC hard stop. Author status DONE_WITH_CONCERNS / IMPLEMENTED_BUT_UNCOMPILED. Actual original Linux v1 body/40-byte ABI and C01 declarations/target guards are byte-preserved. Isolated stdlib static source/hash inspection exited 0; no build/test/native operation/Git or fresh SPEC/QUALITY PASS is claimed.

This is the independent C02-B1 raw observation/refusal component only. Separate raw SAMPLE_COMPLETE is no admission; EXIT_RACED remains incomplete/STOP_NEW. Complete native controllers/seed/cohort/phase ownership/scope producers stay NOT_IMPLEMENTED. C00 AUDITED_UNPROVEN/whole C01 and C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE persist. Physical scope/all writers/whole billing/service exit/final durable handoff remain UNPROVEN; Windows MONITORED4/P2 override/Linux hard/original caps/science/UNKNOWN_NOT_ZERO budgets and all blocked/Stage-zero/Route3-four-FAIL/F1-open states persist. Root must obtain fresh scoped SPEC then DIFFERENT fresh QUALITY after author STOP; review/Git/runtime receipts remain pending.

### C02-B1 scoped dual review receipt (UTC 2026-10-13)

The [original plan review closure](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-independent-source-review-closure-utc-2026-10-13) records the exact API ledger/source hashes, actual author STOP 02:16:40 UTC after 873 seconds, fresh SPEC /root/c02_b1_spec_review 02:20:55 -> 02:24:41 UTC, and different fresh QUALITY /root/c02_b1_quality_review 02:27:02 -> 02:30:43 UTC. Both return NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY on the identical two native files and author-checkpoint document suffixes. C02-B1 is SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED; it is a raw observation/refusal component, not complete C02 or installed production.

Root independently confirmed 403 file identities/no additions or deletions, exact five-path changes, byte-preserved original-three prefixes/v1/C01 declarations, full original eleven staged identities, original authorization documents/GT pins, unrelated work and main. Current SOURCE review does not replace full formal review, installation, real budget/scope mechanisms or admission. This later administrative append records the receipts without expanding review scope.

The existing section 4.9 complete fourteen-item A+B card retains its actual conditions, with this sole SOURCE delta. Subsequent bound choices remain authoritative: Windows application4TIDs MONITORED/fixed-thread and UNKNOWN overshoot, complete infrastructure billing, dedicated physical extent DESIGN, and bounded/billed external final coordinator survival; Linux hard limits/other original caps/science are unchanged. Physical/all-writer capacity, whole charges, original birth/transport, pre-load closure, complete GT/input/phase ownership, terminal/VM/service exit and final durable acceptance, full equivalence/formal review/freeze are still unproven. No second card, handoff or authorization object is created.

C00 AUDITED_UNPROVEN; whole C01/C02 incomplete; C03 NOT_STARTED; C04-C12 STOP even SOURCE. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / original full FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED and zero lawful Route2 runs/results persist. Route3 legitimate COMPLETE/four FAIL and the open F1>=0.66 objective persist. SOURCE/API/static review only; no tests/build/native/WSL/GT/probes/formal objects. SDK/compiler/runtime and all costs remain UNKNOWN / UNKNOWN_NOT_ZERO. Git receipts follow separately.

### C02-B1 exact-path Git receipt link

The [original plan Git receipt](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-path-git-receipt) records actual five-path commit bfdee835e23183eefee66c24c5b8fbaf13acb096, non-force push/remote feature HEAD verification, unchanged main, exact original eleven staged identities and the same 403-file set with no unrelated changes. This later three-document receipt is a separate small commit; its own final HEAD is read from Git/final report, not preclaimed here. Reviewed native source bytes remain unchanged. SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED only; full C02 and all deployment/runtime/admission/science-result conditions remain incomplete/blocked, with UNKNOWN_NOT_ZERO fees. No tests/build/native/WSL/GT probes/formal objects or new card/handoff.

<a id="c00-mechanism-reaudit-candidate-20261013"></a>
### 2026-10-13 C00 mechanism re-audit: candidate conclusion, not a formal PASS

This is an incremental state update to the existing unique complete fourteen-gate A+B card (section 4.9 and its preserved later deltas). It creates no second application, authorization prompt, handoff, freeze or approval object. Author FIRSTCLOCK 04:49:42 UTC; eight-minute recording target 04:57:42 UTC. Fresh independent SPEC followed by DIFFERENT fresh QUALITY and their actual review IDs remain pending; root must record their returned verdicts after author STOP. No review ID or PASS is invented here.

**Authorization delta is effective.** The owner's new preparation-validation permission is real; the former SOURCE-only permission shortage is no longer the reason to refuse preparation. It does not waive the original clock, execution-group, resource, complete-fee, STOP_NEW or cleanup contract. A preparation invocation may run only when that complete contract exists before its first birth/import/API call. It is presently missing. Physical extent remains the selected DESIGN; actual format/partition/import/registration or other concrete entity changes require their concrete authorized scope. Existing Windows MONITORED4/fixed-thread application groups, complete infrastructure billing and the bounded, billed surviving external final coordinator are binding choices; do not reopen them. Preparation permission does not authorize GT, Stage A/B or a scientific run.

C00 remains AUDITED_UNPROVEN. Whole C01/C02 remain incomplete; C02-B1 remains SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED, with C SHA256 351eaa16c3394102530c9d2c3d085daaf3e84c1b23cfbd8050a2ed2611e7112b and H a60683ab57ce9293448d1b6951c903b7bcbad0c3057ed12c1eb5df89692d2e63 unchanged. C03 has not started. Dependent C04-C12 remain STOP even SOURCE; no extra partial refusal, dependent source repair or new recorder is justified by this re-audit.

#### Evidence boundary and preflight

Recovery has a formal final report for all 1922 spec lines, the original 362-line card, 233-line authorization prompt and six cited evidence classes. Plan/review full-document restoration by the other read-only auditors has not yet received a final confirmation at author time; their concrete messages are evidence, not an invented complete restoration/review. They encountered an external platform usage-limit error; subsequent final reports confirmed plan1-2237 and the complete review had not been fully restored without truncation. Root assigned the same auditors one five-minute necessary text-restoration window each, without reopening API research, hypotheses or runtime budgets. Their actual final completion or external blockage must be recorded when known.

| Required preflight field | Current recorded result |
|---|---|
| Goal | Close complete A+B pre-admission, including actual producers and all fourteen gates. |
| Success metrics | Complete fourteen-gate closure, installable production and runtime proof, full formal review, complete freeze, and the existing unique complete approval application. |
| Constraints | All original numerical/scientific limits; no GT or Stage in preparation; concrete entity changes only within concrete approval; no budget reset. |
| Prior art | Public pinned WSL/HCS creation/lifecycle contracts and historical bounded probes; SOURCE observations do not prove local runtime. |
| Baseline | C00 AUDITED_UNPROVEN; partial SOURCE components; full FAIL; no FrozenAdmission; zero lawful Route2 A/B/results. |
| Candidate approaches | Only the three already bound approaches: Windows application MONITORED4/fixed-thread, dedicated physical extent DESIGN, and bounded/billed surviving external final coordinator. No B/platform/policy replacement. |
| Critical assumptions | Creator-certified original identities/cohorts, original complete fee/deadline ledger, current approved geometry/exclusive ownership, and a readonly pre-load native closure. All remain unproven. |
| Risks | No selected all-service join producer; HcsCancelOperation is unimplemented; physical metadata/writers remain unbounded by actual evidence; historical fees/remaining budgets are UNKNOWN_NOT_ZERO. |
| Validation experiments | This invocation: recovered SOURCE/static evidence and public documentation only; zero actual native, WSL, preload, GT or Stage invocation. |
| Kill criteria | Any required producer unsupported, unselected or unproven, or an incomplete preparation contract, prevents running and dependent implementation. Do not spend a missing budget by guessing. |
| Recommendation | REDESIGN the presently unclosed production route. Preserve bound design choices; do not declare this machine infeasible or replace B, policy or platform. |
| Confidence | High confidence in the documented gaps; actual local feasibility remains UNKNOWN. |

Routing is RESEARCH / PARALLEL_SUBAGENT using actual collaboration: three read-only restoration/audit workers and this sole original3 author, then fresh SPEC -> DIFFERENT fresh QUALITY. loaded_profiles=generic; capability tags=native-lifecycle, resource-accounting, physical-storage. This is manual telemetry in the original3 only; no separate recorder/new file. Validation order remains restoration -> public API contract -> complete preparation contract -> lawful native/no-GT subset -> runtime freeze -> full formal review -> final approval. Independent SOURCE wall windows overlap and must not be added as elapsed task wall.

#### New SOURCE facts and what they do not produce

- Existing windows_preparation_job.py:802-805 _prepare_fixed_worker explicitly refuses a missing readonly Windows worker/PE closure and pre-import owner. Its implemented body is child Job commit/process-count control plus private 60/70-second QPC windows; it does not produce whole RAM/thread/service accounting or original 1800/6000-second admission.
- Existing windows_wall.py:125-131 _require_host_control_boundary refuses missing actual hard-capped host control and installed policy. An owner-supplied declaration does not install that boundary.
- Existing capacity_plan/validation retain historical fixed 32-GiB carrier/34-GiB physical and old shared-E assumptions. They cannot consume the current L_C<24 / L_X<6 dynamic design. No actual CreateVirtualDisk/layout/formatter producer is present. These dependent sources are untouched.
- Public WSL source pinned at 449a7eb5c98638bb35cd4d9b4717d090b15ba271 contains _CreateVm -> CoCreateGuid -> WslCoreVm::Create -> OnVmStarted. This does not expose a creator-certified original local WSL cohort. common/hcs.cpp uses internal INFINITE waits; a local finite wait cannot establish finite underlying service completion. Local version/creator bridge remains UNKNOWN. Newly retrieved WSLc session-termination documentation also does not certify the original complete WSL service cohort; no route switch follows.
- HCS can observe VM exit on the creator-certified original HCS_SYSTEM when a callback is registered before shutdown. HcsEventSystemExited JSON exit status is a VM event, not all host-service join. Original callback context, cohort, callback TIDs, pre-load closure and all costs must be owned before loading; deregistration/drain guarantees remain UNKNOWN. The [exact HCS owner/API ledger](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c00-reaudit-owner-api-ledger-20261013) records async final-result waiting, E_NOTIMPL cancellation and close-only semantics.
- Historical 09-29 same-image 2->4-GiB scratch ENOSPC observations are local capacity failures. Actual C backing was not current L_C; deleting VHDX/cleanup does not refund historical growth. The 10-07 Disk1 LargestFreeExtent=102835945472 bytes lacks current offset/sector/GUID/exclusive-owner evidence; never default to formatting E, Disk1 or Partition2.
- Original prep1800/external6000 cumulative time/fees and remaining original-t0 balances are incomplete: UNKNOWN_NOT_ZERO. There is no proof they are exhausted, and no zero/free allowance. Historical Linux thirteen wheels/venv 348519927 logical bytes/pip-import snapshot do not certify a new native/preload closure.

#### Incremental status of the existing unique fourteen-gate card

SOURCE and historical actual evidence are kept separate. FUTURE_AUTHORIZED_INVOCATION_ONLY means the owner's permission exists, while the actual evidence may be produced only by an invocation whose original complete preparation contract already passes; it is not a gate PASS or an automatic permission to start now. Same-invocation floors cannot be replaced by an old measurement.

| Original gate | SOURCE evidence / fixed requirement | Actual evidence now | Before-run vs same-invocation gate | Current conclusion |
|---|---|---|---|---|
| 1 readiness/freeze | Registration/safe projection PREPARED_UNREVIEWED; original card/prompt preserved. | No complete installable runner, runtime identity/fees, full review or consumable FrozenAdmission. | Complete contract/producer closure before preparation; full freeze/review before A+B. | NOT_CLOSED; preparation permission effective, APPLICATION_BLOCKED. |
| 2 scientific equivalence | Saved 26D scores/model, thresholds .10/.25/.50, decoder600s/min180s, matcher/five folds and strict positive overlap vs300s; symmetric atol1e-12/rtol1e-10, discrete exact. | Historical PARTIAL_MATCH_ONLY; no lawful complete nested cross-OS 105 reference+105 treatment across five folds x four configurations. | Science fixed beforehand; equivalent actual complete records/windows/source before A+B. | HISTORICAL_PARTIAL / NOT_CLOSED; no GT/Stage permission here. |
| 3 creator/bank/input history | Metadata/batch/GT leaves and C01 declaration slice are SOURCE; public creation chain newly clarified. | Original bank/role creator/publisher, complete create/delete/history, no writable alias, same-FD consumption and nested deployment unproven. | Creator/authority/pre-load contract beforehand; complete original history by actual invocation. | NOT_CLOSED; C00 AUDITED_UNPROVEN and whole C01 incomplete. |
| 4 calls/capacity projection 2->4 | 25 fit/25 predict/65 decode/20 GT evaluations+one GT-free pooled merge, pooled GT reads0; D_A=2GiB strict V2, same image2->4, not2+4. | Only historical local ENOSPC/capacity attempts; no complete enforcing N/M/S/B/R ledger or lawful Stage B projection. | Enforcing ledger/projection producer beforehand; actual capacity history/expansion only under concrete scope. | HISTORICAL_PARTIAL / NOT_CLOSED. |
| 5 matched-GT/source/releases | Final matched-GT gain/loss/finalize SOURCE retained; candidate coverage separate. | No lawful A2-004 final matched-pair provenance, five-field isolation, actual canonical commitment and all role/phase grants/revokes. | Role/source contract beforehand; actual releases/revokes only in a later authorized scientific invocation. | NOT_CLOSED; current GT payload reads0. |
| 6 WSL worker/isolation | Bound WSL2/Ubuntu22.04/glibc2.35/B/exclusive window; spawn/pidfd/READY/wait/reap/status SOURCE. | GUID/SID/UID/namespace/IPC/FD/mount/cgroup/thread/write-path/cleanup unproven; historical4096/scan256/nlink1 does not support19894aliases/max257. | Original owner/isolation contract beforehand; actual original identities/history under authorized preparation. | HISTORICAL_PARTIAL / FUTURE_AUTHORIZED_INVOCATION_ONLY. |
| 7 E physical24/20/6/metadata/floors | E30=carrier24 including guest20 + external6; controls64MiB within20 /16MiB within6; guest baseline<=8; same invocation guest hosting FS and actual L_C backing each free>=8GiB, independent carrier reserve, no third8. | Physical extent DESIGN only; no current finite geometry/all-writer producer/three-layer usable, allocated, header, headroom, history or remaining-balance proof. | Approved current geometry/exclusive ownership and capacity producer beforehand; fresh double8 and actual baseline in the same invocation. | NOT_CLOSED / FUTURE_AUTHORIZED_INVOCATION_ONLY; no default disk format. |
| 8 t0/M0/RAM/CPU/VM/Linux hard | Whole16GiB RAM/8GiB VRAM; study1200/3600/cumulative fit900 include cleanup60; C=min(4GiB,floor(3M0/5)), AS=C/2, swap0, CPU200%, TasksMax2 including controller; Windows MONITORED4 bound. | Original prebirth t0/M0, VM8GB/swap0/CPU2/gui=false application, cgroup/AS/CPU/GPU hard boundaries/whole peaks unproven. | Hard/billed owners before birth; first original M0 and continuous actual usage in the same invocation. | NOT_CLOSED; MONITORED is not HARD4 and actual overshoot UNKNOWN. |
| 9 prep/external full historical billing | Prep4GiB/200%/MON4/1800; external512MiB/100%/MON4/6000; all helper/launcher/bridge/coordinator/infrastructure costs and cleanup60 included. | Private Job/QPC paths only; original whole-history t0 balances/VM/kernel/service/observer/ABI fees unproven. | Original complete fee/deadline ledger before any preparation; continuous future costs under the same original ledger. | NOT_CLOSED / UNKNOWN_NOT_ZERO, neither exhausted nor zero proven. |
| 10 non-E512 MONITORED | Stop new growth at384MiB; nominal128MiB tail; accepted in-flight overshoot remains UNKNOWN. | No fixed whole-task writer/AllocationSize/history/billing/stop producer; old PS28-29threads do not satisfy application4. | Fixed observer/stop/owner contract beforehand; all growth through tail actually billed. | HISTORICAL_PARTIAL / NOT_CLOSED; deletion/pagefile fallback is not refund;128 is not physical reserve/bound. |
| 11 pre-load/dependency ABI | Thirteen-wheel lock/old ABI/venv and native C/H/40-byte ABI/conditional seed/transport SOURCE retained; C02-B1 uncompiled. | No current readonly PE/ELF/interpreter/stdlib/project/native/transitive/provider closure before constructor/import/dlopen; no original QPC/prePython continuity. | Closure/owner/hard kill/accounting before any import or load; native ABI facts only in lawful preparation. | HISTORICAL_PARTIAL / FUTURE_AUTHORIZED_INVOCATION_ONLY; prepare worker explicitly refuses missing closure. |
| 12 cleanup/VM/service/original join/durable QPC | Existing pidfd/OFD/READY/status/wait/reap/once-close/poison SOURCE; live final coordinator selected with bounded billed tail. | No complete backing-delete/GT-revoke/OOM/crash/quarantine/raw-cgroup/VM/all-service original join or durable live acceptance producer; HCS VM exit alone insufficient. | Original stop/deadline/tail owner beforehand; terminal joins, flush and subsequent live native QPC in the same invocation. | NOT_CLOSED; VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN. |
| 13 complete formal review | Existing narrow C00/C01/C02 SOURCE reviews do not cover whole installable production. | This candidate suffix awaits fresh SPEC->different QUALITY; no new full-review ID, runtime or source/input/role/protocol/budget freeze. | Candidate scoped reviews after author STOP; complete formal review/freeze before the unique final A+B application. | NOT_CLOSED; no scoped/full PASS preclaimed. |
| 14 lawful COMPLETE/quality | Route3v1-003 lawful COMPLETE/fourFAIL preserved without rerun; pooledF1>=.66, >=3/5 foldF1>=.66, each longFP<=.25, start/endMAE<=900s; actual matched-GT report required. | Zero lawful Route2 A/B/results; no lawful early stop or complete five-fold Stage B. | Later scientific authorization required; COMPLETE and all four quality gates reported independently. | NOT_CLOSED; deep-learning eventF1>=.66 remains open. |

The preparation contract and same-invocation evidence distinction prevent a circular blanket ban: new authorized preparation can produce its permitted runtime facts once its already-required pre-execution safety, identity, clock, fee and cleanup producers exist. Current absence of those producers prevents that invocation now; it does not rescind permission or prove local impossibility.

Root source FIRSTCLOCK03:07:55 / soft target03:37:55 has elapsed; root confirmed at04:49:49 and a later capacity-source grep occurred after that target. This overrun is retained; earlier SOURCE reads were not fully instrumented. This author window and auditor/reviewer windows are bounded recording/review windows, not renewed original C00 research/preparation/runtime budgets. No additional research/native loop follows. Public web retrieval had one429 failure; Context7 resolve then concept-scoped queries yielded the first-party HCS contracts, without a retry loop. Exact complete token/resource/fee telemetry remains UNKNOWN_NOT_ZERO.

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED remain. These last states describe the scientific A+B application; the new conditional preparation permission above is effective. No SOURCE/native/runtime freeze, actual installation, native execution or legal Stage result was produced. After author append/prefix hashes and STOP_ALL_WRITES_AND_READS, root owns actual fresh SPEC->different QUALITY, exact-path retention/Git and final factual receipts.

<a id="c00-reaudit-science-gate-erratum-20261013"></a>
### C00 re-audit scoped P2 erratum and actual full-restoration receipt

Fresh independent SPEC actually stopped reads at05:01:17 UTC and reported two scoped P2 issues, no P1; this same-author append repairs those issues without changing the preceding candidate/prefix. It is not a completed dual-review verdict. SPEC repair verification followed by DIFFERENT fresh QUALITY and actual IDs remain pending. Mandatory repair FIRSTCLOCK05:01:53 UTC/three-minute target05:04:53 is document recording only; original elapsed SOURCE target, historical/runtime budgets and UNKNOWN_NOT_ZERO costs are not reset.

Normative update of row2 of the existing unique complete fourteen-gate card: supersede review's preceding row2 at original line3068 and plan's scientific-isolation row at original line2634. There is one fixed scientific setting: nested5 outer folds x4 inner folds, with4 sub-inner folds per inner fold, not four configurations. The105 candidate roles derive from the whole nested graph. The25 verifier fits are20 inner+5 outer; original upper bounds25fit/25predict/65decode/20GT evaluations+oneGT-free pooled merge and pooledGTreads0 remain.

BEFORE the scientific run, protocol/source identity and non-GT source/input checks must close. Complete nested cross-OS equivalence is a separate prior verification on synthetic inputs, no real GT/no Stage, covering the original5x4 call graph and numerical boundaries, symmetric atol1e-12/rtol1e-10 and discrete exactness, with independent review. Current historical PARTIAL_MATCH_ONLY is insufficient. This append does not execute verification or manufacture a PASS.

Formal StageA may occur only after binding concrete complete A+B final approval, inside the same lawful invocation:105 reference cases all pass ->105 treatment cases. These formal cases are not prior admission evidence or a substitute for the synthetic verification. Original M0, fresh same-invocation double8, formal105, N/M/S/B/R, actual GT releases/revokes and terminal facts are SAME INVOCATION only. Their before-run producer/contract requirements must close without running an early Stage. Row2 remains HISTORICAL_PARTIAL / NOT_CLOSED; all other card rows/limits and the effective conditional preparation permission are preserved.

Actual restoration is now complete: the read-only spec restorer confirmed all1922 spec lines, original362-line card,233-line prompt and six referenced evidence classes. The plan auditor confirmed all2596 plan lines without gaps after completing1-2237 (truncated361-540 reread); supplementary read window04:53:37->READSTOP04:57:11 UTC,214s. The review auditor confirmed all3019 lines without gaps, including1-2753 supplementary reads and2754-3019 narrow reads; READSTOP04:59:00 UTC against target04:58:39,21s overrun retained, exact last-read time uninstrumented. These are actual text-restoration receipts, not implementation/runtime/full-review PASS. Root's previously elapsed03:37:55 SOURCE target and later-source overrun remain.

Root preservation receipt before repair:403 project files, only original3 append changes, no additions/deletions, all171 full index entries unchanged including all eleven protected staged identities, and original-prefix checks matched. This is preservation evidence, not an approval or runtime freeze. No source/config/test/prompt/card bytes are changed by this repair. VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN and C00 AUDITED_UNPROVEN/wholeC01C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE persist. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/oldfullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED for A+B, Stagezero/Route3 COMPLETE-fourFAIL/F1open and all UNKNOWN_NOT_ZERO fees persist.

<a id="c00-reaudit-actual-scoped-review-receipt-20261013"></a>
### C00 re-audit actual scoped review and final condition-status receipt

Root records actual completed review ID route2-c00-permission-aware-document-api-review-2026-10-13-001, scope C00_PERMISSION_AWARE_DOCUMENT_API_AUDIT_ONLY. It is not a full implementation/runtime review ID. The original route2-ab-full-implementation-review-2026-09-29-FAIL-001 remains FAIL.

- Sole author /root/c00_reaudit_author: 04:49:42 -> STOP_ALL_WRITES_AND_READS04:56:28 UTC,406s within8min. Initial candidate hashes are preserved in the later repair prefix.
- Fresh independent SPEC /root/c00_reaudit_spec: 04:58:30 -> READSTOP05:01:17,167s within5min; two scoped P2 and no P1. Same author repaired only by append05:01:53 -> STOP05:03:25,92s within3min. SPEC repair verification05:04:27 -> READSTOP05:04:51,24s within2min, NO_REMAINING_SCOPED_P1_P2.
- DIFFERENT fresh independent QUALITY /root/c00_reaudit_quality: 05:06:07 -> READSTOP05:08:51,164s within5min, NO_REMAINING_SCOPED_P1_P2 / C00_PERMISSION_AWARE_DOCUMENT_API_AUDIT_ONLY. QUALITY independently used Context7 resolve then three separate primary-document queries and checked actual source facts. No runtime/full-admission verdict is inferred.
- Both final reviewers inspected repaired spec1946/plan2649/review3101 lines. Reviewed SHA256: spec afe786cfa9814d8dd37147b2f7846eb9168e7b934bba4abadb80de01aa66fc85; plan41b37394588f159b6b1c76558ea2fca68725a8e212d3fc8c3a13722b7f3e2e3b; review6b584407df6983fdf9c990bfb2a668cd894f9b47d0f52d697722f11ec3f2f0fb. This administrative suffix does not extend their reviewed byte scope.
- Full original3 restoration is actually complete as recorded by the preceding repair receipt. Original root SOURCE soft deadline03:37:55 and review-restoration21s overrun remain, not budget PASS/reset. Platform usage interruptions and uninstrumented intervals remain explicit; independent SOURCE windows are not additive elapsed runtime.
- Fresh root preservation checked all403 project files: only original3 append changes, no additions/deletions, all171 complete index rows unchanged including the original eleven full staged identities, and all original raw prefixes matched. C02-B1 C/H/GT/path-map/Stage B/finalize/auth-card/prompt and unrelated bytes remain unchanged. Exact-three-path whitespace check exited0. Git checkpoint/non-force push and final remote verification follow; no future Git success is invented here.

The existing unique fourteen-gate card's complete status update and latest row2 erratum remain authoritative. All fourteen gates are NOT_CLOSED or historical/future-invocation partial; no gate advances to admission PASS. BEFORE requirements include actual installed production/ownership/pre-load/resource/billing/cleanup paths and full reviewed synthetic nested equivalence. Original M0/fresh double8/formal105/N-M-S-B-R/GT release and terminal facts belong only to the later authorized same invocation, via implemented fail-closed paths; none was manufactured by an early Stage.

Effective preparation-validation permission is retained. Actual preparation cannot start with missing original histories/1800-6000 balances, controlled pre-load entry and complete actor identity/fees; these remain UNKNOWN_NOT_ZERO, neither proven exhausted nor free. Current task-dedicated disk/extent identity, exact geometry/exclusive writer authority and complete original VM/service/callback exit/deadline/handoff producers remain absent. The centralized facts request for existing original receipts/history/entry and a specific task-owned physical target remains unanswered; no repeated policy approval is requested and no concrete disk action is submitted without a verified target/impact plan.

Final status: C00 AUDITED_UNPROVEN; C02-B1 SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED; wholeC01/C02 incomplete; C03 NOT_STARTED; dependent C04-C12 STOP even SOURCE. VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN persist. Production installation, actual no-GT budget/failure-cleanup proof, complete freeze and full formal review remain undelivered. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED for A+B persist. No compile/link/load/native/OS/WSL/installation/physical-disk/GT/Stage invocation occurred. No approvable complete A+B object or final approval request is issued. Route2 lawful results0; Route3v1-003 lawful COMPLETE/fourFAIL preserved; eventF1>=0.66 remains open.

<a id="c00-reaudit-exact-path-git-receipt-20261013"></a>
### C00 re-audit exact-path Git receipt

Root verified actual commit 8fc7aadb969af63f3e4102b67e91f25176d83e2d, parent f0ba61a1bb8b022b8aa06b023469aaba862a4cbb, exact original3 document paths only,185 insertions/zero deletions. Exact-path add plus commit --only preserved all other complete index entries and the original eleven full staged identities/path set. The non-force push to codex/high-f1-event-stack-execution exited0; subsequent completed ls-remote returned that exact feature HEAD and unchanged main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b. The initial remote query yielded a running session; root's completion guard treated pending as failure too early, then resumed the same session and actual exit0 output verified both refs. No re-push/reset/force or data mutation followed that guard error.

This final administrative receipt is a separate small original3 checkpoint; its own hash and final remote status are obtained from Git and the final response, not self-embedded or preclaimed. Scoped document/API review ID route2-c00-permission-aware-document-api-review-2026-10-13-001 remains limited; no full implementation/runtime review, source/runtime/input/budget freeze, APPROVAL_READY or experiment authority follows. Current physical objects, original controlled preparation entry/history/balances and complete VM/service original join producers remain unproven. All fourteen condition conclusions, effective conditional preparation permission, three UNPROVEN names, C04-C12 stop, original full FAIL/FROZEN_ADMISSION=None/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero/Route3-fourFAIL/F1open/UNKNOWN_NOT_ZERO states remain. No further implementation, probe or budget reset is introduced.


### C02-A sole-author review handoff (2026-10-13; reviews pending)

Only the independent C02-A component is COMPONENT_SOURCE_IMPLEMENTED_UNCOMPILED, awaiting fresh scoped SPEC then DIFFERENT fresh QUALITY after author STOP. [Pre-edit exact API/cleanup ledger and source checkpoint](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md#c02-a-exact-existing-target--pre-edit-api-and-cleanup-ledger-2026-10-13) binds actual W/SDK signatures/headers/Kernel32/rights/out/error floors; public docs are not installed SDK/ABI proof. Sole author START08:11:46 UTC/deadline08:31:46; final actual STOP/hash receipt goes to root, not preclaimed here.

Existing native C/H contain five independent raw-status create_fixed/assign_borrowed/query/close_once/copy_report_v1 functions behind separate Windows-seed/x64/C11/Win8 guards, plus native C11 atomic_flag guard for consistent lifecycle/report copies. Anonymous noninheritable original Job is retained directly in private native state before return conversion; fixed commit4GiB/active4/lowest <=2 allowed bits/interval CPU200% conversion/KILL/no breakaway configuration receives strict exact-size readback. One real borrowed process type/PID checked before private SAME_ACCESS/FALSE duplicate; pseudo/NULL/INVALID and real self PID rejected; PID/creation/liveness and Job membership surround actual assignment. Association is existing-process only, not atomic prebirth/permission, and failure can terminate it. Primary remains sticky; only report/once-cleanup remain after poison. Both successful private handles are consumed before either independent one-time close; all three bounded primary+close faults retain full DWORD values. Failed duplicate output never owned, borrowed never closed, close failure not retried; KILL request not exit/join.

Report version/native size, per-field UNKNOWN/VALID/FAILED, fixed configured snapshot/latest query attempt and acquisition/consume/close history distinguish raw native facts from initialized zero. Latest Job counters/commit peaks describe this Job only; commit not RSS/wholeRAM/VM, active4 not TIDs, CPU scheduling interval/nested-parent relative not instantaneous wallclock. No complete membership/history/fees, approval, MONITORED4, VM/service/physical/final join or successful scope producer. Existing C/H baseline bytes and all old B1/refusals/Linux v1/C01 pins match isolated stdlib hash checks; original3 append-only. No C syntax/ABI/build/preprocess/link/load/native/runtime/test/import/probe/WSL/GT/formal objects or Git mutation.

C00 AUDITED_UNPROVEN/wholeC01C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE/three UNPROVEN/PREPARED_UNREVIEWED/FROZENNone/oldfullFAIL/APPLICATION_BLOCKED/notapprovalready/notexperimentauthorized/Stagezero/Route3 COMPLETE-fourFAIL/F1open persist. Effective prep/compile/noGT permission remains, but original actual clock/group/resources/full fees/preload/stop/cleanup contract is missing; no invocation/new E directory. Source budget does not reset runtime budgets or make fee0; UNKNOWN_NOT_ZERO persists.


### C02-A scoped dual review, historical-budget recovery and full-card delta (2026-10-13)

This is one final incremental update to the existing unique fourteen-condition A+B card, not a second application/authorization/handoff. The user's conditional preparation/compile/no-GT permission is effective; general preparation permission is not missing. The user reports no known trusted preparation entry/full historical ledger and asks for workspace recovery. The E-directory reply authorizes the proposed task namespace E:\Route2AdmissionPrep_20261013; no directory or preparation object has been created. That reply does not identify or authorize repartitioning/formatting/shrinking an existing disk, nor replace the selected finite physical extent design.

C02-A review ID route2-c02-a-native-job-source-review-2026-10-13-001 is exclusively C02_A_NATIVE_JOB_SOURCE_ONLY / IMPLEMENTED_BUT_UNCOMPILED. Sole author /root/c02_a_native_job_author START08:11:46, source/doc read-write STOP08:30:35, final five-file receipt08:31:21 UTC, all before08:31:46. Independent fresh SPEC /root/c02_a_fresh_spec START08:36:11/ALL_SOURCE_READ_STOP08:42:42 (391s, deadline08:44:11), then DIFFERENT fresh QUALITY /root/c02_a_fresh_quality START08:45:08/ALL_SOURCE_DOC_READ_STOP08:50:59 (351s, deadline08:53:08), both NO_REMAINING_SCOPED_P1_P2. Neither author self-review nor root hashing substitutes for those reviews. Native C41410 bytes SHA2560982f899b883ff3fb2268d42473c9bea951dbed0ce569a359e15a8e4b392e3f4 and H14779 bytes SHA256d94ce542b9ab2ec3ee7ed8bd634b216a2696f17b856a20c0108648bd5079cd95 bind reviewed source, not an installed runtime or freeze. Entire old C17574-byte prefix and old H8584-byte reconstruction match historical pins; C02-B1 bodies/refusals remain byte-exact although the whole files now have new hashes.

Root independently confirmed403 project-file identities: only native C/H and original3 docs changed; no additions/deletions; full171-entry index unchanged before commit, including all original eleven complete mode/blob/stage/path identities. Historical document prefixes374539/478654/671144 bytes (spec/plan/review) match baseline c0e2f6a8bdb21cc22a0d411415dd54ba0fe9faeb. Exact-path whitespace check exited0. Root's first line-count command had a PowerShell parse error before execution/zero mutation; corrected read-only command exited0. Git checkpoint and actual remote receipt are pending at this append, not preclaimed.

Workspace recovery: /root/historical_budget_recovery read-only windows07:37:20->07:45:45 and07:51:43->07:55:41 UTC. The expanded search used18487 filenames across E:/bme_compitition, including main checkout, both worktrees and hidden/ignored paths; root separately checked reachable Git object-name inventory. Six archives were inspected by directory/header metadata only; A1/A2/Route3 ledger names and scientific/external/official-test filenames were not read as payloads. No additional original Route2 preparation/launch full-ledger candidate was found. This establishes a search result in this scope, not that no historical record exists anywhere. No transcript containing GT payload was opened.

| Recovered historical fragment | Exact evidence | Remaining limit on use |
| --- | --- | --- |
| First09-29 scratch C VHDX length13,974,372,352->18,034,458,624B; delta4,060,086,272B (3872MiB); C free38,540,595,200->34,479,841,280B | [original no-GT evidence:41](../evidence/2026-09-29-route2-wsl-synthetic-os-probes.md) and its later-repeat distinction | Logical VHDX lengths/volume free are not whole-task AllocationSize attribution or a full peak/history. Cleanup did not immediately reclaim growth; deletion never refunds historical fees. |
| Separate repeat VHDX length18,028,167,168->18,464,374,784B; delta436,207,616B (416MiB); image allocated4,203,593,728B | [disk raw no-GT repeat](../evidence/2026-09-29-route2-wsl-disk-probe-raw.json) | Do not count only416MiB as history or double-add child image and parent VHDX at the same physical layer. Neither cap violation nor positive remaining budget follows from these fragments. |
| Historical apt/venv/pip/download/offline install/import; venv11330 files/348,519,927 logicalB;13 pinned wheels | [Linux dependency history](../evidence/2026-09-29-route2-linux-dependency-runtime.md) | Does not recover full loading/installation time, CPU, RAM, threads, allocated metadata, VM/service fees or immutable actual closure. |
| Three local scratch peaks11,149,312B /335,872B /15,835,136B | [09-29 local observation](../evidence/2026-09-29-route2-wsl-cgroup-live-observation.json), [10-01 inert unit](../evidence/2026-10-01-route2-scratch-systemd-cgroup-live.json), [10-01 backend scratch](../evidence/2026-10-01-route2-live-cgroup-backend-scratch-v2.json) | Unit-only samples are not prep/external/VM/kernel/service lifetime peaks, billing or whole original joins. |
|10-07 RunAs/Hidden narrow probe7128ms incl UAC/IPC;10-09 local CIM5239ms/CPU0.515625s, threads29->28; shared D pagefile relative growth2072MiB | Preserved earlier review1624/1962/1976; local samples and later PID reuse | No held original-cohort lease, full time/peak chain or task-only pagefile attribution; neither full charge0 nor deletion/refund follows. |

Missing ledger dimensions remain original pre-load/pre-birth epoch and boot/QPC continuity; all creator/cohort births/detach/escape; every start/stop/cleanup/acceptance interval; cumulative prep1800/external6000 consumption; CPU and RAM/thread/VRAM peaks; VM/kernel/service/system-writer attribution; per-layer AllocationSize/metadata/failed and deleted-held objects; bounded billed tails; trustworthy complete historical upper bounds and derived remaining balances. Existing PreparationCost/cap-only types and private post-Python60/70-second clocks do not produce them. The recovered table preserves known history; it is not a complete budget ledger. UNKNOWN_NOT_ZERO means neither proved exhaustion nor proved positive余额.

Read-only storage/contract audit /root/c03_preload_contract_reader STOP08:26:44 after08:22:53 (231s), supplementary START08:37:43/ALL_SOURCE_READ_STOP08:41:25 (222s). Historical10-07 E volume GUID dbd01263-98ac-43a9-a44c-5dcc3d2e02d1, Disk1/Partition2, NTFS volume capacity1,897,546,117,120B/free1,018,579,828,736B and LargestFreeExtent102,835,945,472B are old samples. Disk uniqueID/whole-disk size/logical-physical sectors/current extent offset-length/layout/exclusive writer owner are missing; volume capacity is not whole-disk size. Historical RunAs success/Disabled SeManageVolumePrivilege is not a current controlled deployment executor. There is no specific irreversible storage command plan eligible for approval yet. The designated directory is only a namespace.

C03 remains NOT_STARTED: the existing candidate helper ELF metadata parser (8MiB/128 program headers/4096 dynamic entries/128 notes/4096-byte strings) and exact40-byte ABI parser are inherited narrow byte parsers. They do not cover complete PE import/delay-import/TLS, interpreter/stdlib/project/native/transitive-provider preload grammar. Complete native preload input API/grammar/entries/depth/aggregate bounds and actual readonly provider identities are not fixed; do not guess new allowlists or repurpose existing4096-history/256-scan/nlink1. Known independent C01-C03 SOURCE eligibility remains; it does not authorize undefined whole providers/seed/glue. C04-C12 remain STOP even SOURCE.

| Existing condition | SOURCE and inherited contract | Actual evidence recovered this turn | Remaining lawful production gate | Conclusion |
| --- | --- | --- | --- | --- |
|1 readiness/freeze | Conditional prep permission effective; fixed B/WSL/science and unique original application preserved | Scoped C02-A source review and exact preservation only | Complete production installation/no-GT evidence/source-runtime-input-protocol-budget freeze and full formal review BEFORE final approval | NOT_CLOSED / APPLICATION_BLOCKED |
|2 scientific equivalence | Saved scores/model26D/thresholds/decoder/matcher fixed; only strict overlap vs300s; symmetric tolerances/discrete exact | Historical partial synthetic evidence only; no new execution | Complete independently reviewed no-GT nested equivalence BEFORE A+B application;105 ALL_PASS reference then105 treatment only in later authorized same invocation | HISTORICAL_PARTIAL / NOT_CLOSED |
|3 creator/bank/input history | C01 declarations and C02-A/B1 raw native components scoped-reviewed; whole C01/C02 incomplete | C02-A source bodies, not actual creator or complete history | Original creator identities/immutable backing/all create-delete history/no writable aliases/same-FD consumption and revoke; C04+ currently STOP | NOT_CLOSED |
|4 calls/capacity projection2->4 |25fit/25predict/65decode/20GT-backed evaluations plus21st GT-free merge; pooled GT reads0; sameimage2->4 | Only distinct historical no-GT scratch observations | Reviewed production path BEFORE approval; actual N/M/S/B/R/exact counts/strict D_A2GiB and legal expansion in same authorized invocation | HISTORICAL_PARTIAL / NOT_CLOSED |
|5 matched-GT/source/releases | Original directory-v2 broker/110O_PATH history/revocations and matched-GT/finalize repairs inherited | This turn GT payload reads0 | Installed role/phase grant/revoke/FD-history producer beforehand; actual releases/matched-GT facts only authorized Stage | NOT_CLOSED |
|6 WSL worker/isolation | WSL2 Ubuntu22.04/glibc2.35; fixed worker/spawn-pidfd-wait-reap/status/UID/namespace/IPC contract | Historical local observations only | Complete reviewed worker/isolation/write-path/cleanup production implementation BEFORE approval; live identities in same invocation | HISTORICAL_PARTIAL / FUTURE_AUTHORIZED_INVOCATION_ONLY |
|7 E physical24/20/6/metadata/floors | Selected finite physical L_C<24/L_X<6, guest20/baseline<=8, control64/16MiB all internal; carrier reserve distinct | Directory permission and old shared E sample, no current extents | Current physical target/geometry/exclusive owners/full metadata and authorized concrete change plan BEFORE deployment; actual guest-hosting FS and actual L_C double8 before image in same invocation | NOT_CLOSED / FUTURE_AUTHORIZED_INVOCATION_ONLY |
|8 t0/M0/RAM/CPU/VM/Linux hard | Windows MONITORED4/fixed thread approved; Linux hard unchanged; whole16GiB/8GiB; original C=min(4GiB,floor3M0/5),AS=C/2,swap0,CPU200%,TasksMax2 | C02-A raw Job source COMMIT/process/intervalCPU facts only; no actual boundaries | Trusted before-birth owners/continuous full fees/WSL8GB,swap0,CPU2,GUI false actual application; original first M0 in same invocation | NOT_CLOSED; MONITORED overshoot UNKNOWN |
|9 prep/external full historical billing | Original4GiB/200%/MON4/1800s; external512MiB/100%/MON4/6000s;60-tail internal, infrastructure fully billed | Partial history table above; no complete original epoch/remaining balance | Recover trustworthy complete historical upper bounds; original controlled pre-load groups/time/resource/billing/STOP/cleanup entry BEFORE any new actual run | NOT_CLOSED / UNKNOWN_NOT_ZERO |
|10 non-E512 MONITORED | Stop-new384MiB/nominal128-tail and accepted unknown in-flight overshoot unchanged | Narrow historical pagefile/working-set/thread samples only | Complete writer/AllocationSize/history/billing/observer/STOP production mechanism BEFORE run; all growth through acceptance tail charged | HISTORICAL_PARTIAL / NOT_CLOSED |
|11 pre-load/dependency ABI | Existing40-byte ABI and ELF inventory inherited; C02-A guard requires actual C11 atomics/Win64/Win8 SDK | No installed compiler/toolset/SDK/helper/load/closure verification | Exact bounded preload contract/immutable whole dependency closure BEFORE load; controlled compile/link/ABI/load validation only after complete prep contract | HISTORICAL_PARTIAL / FUTURE_AUTHORIZED_INVOCATION_ONLY |
|12 cleanup/VM/service/original join/durable QPC | Surviving trusted external final coordinator selected; full fees/tail/no postacceptance experiment writes | Job once-close SOURCE is no process/VM/service join or durable acceptance | Exact creator-issued VM/service actors, independent deadline/original exit-join/writer flush/QPC/bounded billed tail production paths BEFORE approval; live acceptance same invocation | NOT_CLOSED; three UNPROVEN remain |
|13 complete formal review | C00 scoped document/API and C01/B1 reviews inherited; new C02-A scoped review ID above | Actual independent SPEC then DIFFERENT fresh QUALITY source-only verdict | Complete installable implementation/execution-closure formal independent review/new full ID/freeze BEFORE unique final A+B application | NOT_CLOSED; old full FAIL retained |
|14 lawful COMPLETE/quality | Route3v1-003 lawful COMPLETE/fourFAIL preserved; F1>=0.66 open | New Route2 scientific/GT/Stage executions0 | Binding concrete complete A+B owner final approval, then authorized same-invocation stages and actual result; no advance Stage | NOT_CLOSED / NOT_EXPERIMENT_AUTHORIZED |

Fact-generation timing is not a loophole: pre-admission installation, complete mechanisms/fee bounds, synthetic nested equivalence and formal full review are still required. Original first M0, fresh double8, stage counts105+105/N/M/S/B/R, real grant/revoke and live exit/flush/QPC can only be generated by the legally authorized same invocation, whose fail-closed nonbypassable production paths must already exist and be fully reviewed. None are supplied by source hashes or old snapshots.

Actual blockers are missing complete original historical fee evidence/controlled preparation entry, current physical target/geometry/exclusive write scope, exact original VM-service ownership/join and final durable producer, and unfinished dependent production closure. Source adds cannot reconstruct an unobserved old epoch or physical object. No approval-ready complete A+B object exists; no final approval request is issued. Only additional concrete historical receipts/current target facts or a supported exact mechanism can change these blockers; no re-request of already effective general prep permission is needed. The full three-mechanism result remains AUDITED_UNPROVEN, not proof this machine is impossible.

C02-A now SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED; C02-B1 inherited same scoped status; whole C01/C02 incomplete; C03 NOT_STARTED; C04-C12 STOP even SOURCE. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero remain. No compile/preprocess/link/load/native/OS/WSL/installation/disk-change/GT/Stage or preparation object occurred. SOURCE windows overlap and are not additive runtime wall. Earlier elapsed research/source envelopes and all costs remain UNKNOWN_NOT_ZERO; this recovery/review/retention is no original-clock reset. Only subsequent administrative review/Git receipts may append after this final full-card update.


Final condition-document verification receipt: independent SPEC /root/c02_a_fresh_spec START08:57:45/ALL_DOCUMENT_READ_STOP08:58:49 UTC (64s within4min), followed by DIFFERENT QUALITY /root/c02_a_fresh_quality START08:59:50/STOP_ALL_DOCUMENT_READS09:00:54 (64s within4min), both NO_REMAINING_SCOPED_P1_P2 / C02_A_FINAL_CONDITION_DOCUMENT_ONLY. They read only the final original3 delta; no implementation/API/runtime/Git operation. This administrative receipt adds no scope, full formal review, freeze, budget PASS or approval; exact-path Git/remote receipt remains pending.


### C02-A exact-path Git preservation receipt (2026-10-13)

Root verified actual source checkpoint017c372fc148484c9a0927d3fd2bb66b53d5b18d, parentc0e2f6a8bdb21cc22a0d411415dd54ba0fe9faeb: exact native C/H plus original3 paths only,777 insertions/zero deletions. All five committed blobs equal raw worktree bytes; all other complete index rows and the original eleven full staged identities remain unchanged, and postcommit porcelain status exactly matches the turn baseline. Non-force push exited0; completed remote query verified feature017c372fc148484c9a0927d3fd2bb66b53d5b18d and main stilldd05aa128f8d62a85c20a83f8af72fe13fcfa27b at09:04:53 UTC. No reset/stash/force or unrelated mutation.

This is a later administrative original3-only checkpoint. Its own hash/final remote confirmation is obtained from Git/final response, not self-embedded or preclaimed. Source C02-A and final-document scoped double reviews establish only their stated scope. C00 AUDITED_UNPROVEN/threeUNPROVEN/wholeC01C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE/fullFAIL/PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero/Route3fourFAIL/F1open/UNKNOWN_NOT_ZERO remain. No complete original historical ledger or controlled preparation contract/current physical extent/final join has been supplied; no compile/ABI/native/no-GT runtime or scientific invocation was started. The designated E directory remains uncreated. Earlier elapsed source/research/preparation envelopes remain; necessary restoration/review/Git close is not a budget reset. Only retention and final reporting follow.


### Historical session receipt recovery and C03-A contract audit (2026-10-13)

This is a narrow evidence increment to the existing unique14-condition card, not a new application, preparation epoch, source component or whole-admission review. Owner “继续工作” resumes necessary recovery; no original prep/external/study/storage/scientific budget is reset. Current feature HEAD at restoration is ddea3ca97e2389e5b7bae16cf7988da344589c96; reviewed native C/H remain0982f899b883ff3fb2268d42473c9bea951dbed0ce569a359e15a8e4b392e3f4 /d94ce542b9ab2ec3ee7ed8bd634b216a2696f17b856a20c0108648bd5079cd95, still uncompiled. The preceding turn is concrete scoped-source progress; this turn recovers historical record locators and two actual call/output pairings. Neither completes any original admission condition.

The earlier18487-workspace-name search did not cover the following external archives. Header-only inspection establishes these exact sources, not native clocks, fees or a complete ledger:

| Session/archive under E:/Codex/Home/sessions | Header timestamp / bytes / scope |
| --- | --- |
|2026/09/28/rollout-2026-09-28T21-41-04-01a0ead2-9452-7043-88de-bdd5bd1eed7e.jsonl |2026-09-29T01:44:01.186Z;8,364,821B; root source vscode, cwd E:\bme_compitition |
|2026/09/29/rollout-2026-09-29T02-00-22-01a0ebbf-f7a2-7cf3-bc0e-ddade43327ca.jsonl |2026-09-29T06:00:23.111Z;1,253,207B; /root/linux_deps, parent01a0ead2, cwd same |
|2026/09/29/rollout-2026-09-29T08-12-15-01a0ed14-602e-7240-bbc8-a2074864eab7.jsonl |2026-09-29T12:12:29.385Z;119,593,018B; root source vscode, cwd same |
|2026/10/07/rollout-2026-10-07T02-25-26-01a11577-ab1e-7b42-adfa-26dde75b81b9.jsonl |2026-10-07T08:27:03.758Z;54,642,294B; header only, body not inspected |

Only tool-call metadata and exact whitelisted no-GT call outputs were projected. User/analysis/event message bodies and unselected output payloads were not decoded or returned; no GT file/payload or scientific run was consumed. Source-candidate verification showed real archived commands use the Windows launcher py -3.10 -B, whereas the original no-GT evidence's example command uses python. Actual tool framing contains both function_call and custom_tool_call; selected outputs contain input_text records. An unsupported function-only / python-only / text-only selector's zero counts do not establish absence. The30-second bounded metadata projector recognized5666 tool frames across its allowed sources, skipped one oversized record and returned no exact matches under its then-restricted grammar; that result is not comprehensive coverage or ledger absence. After locating and reading only the two relevant pure exec_command call-source records, root used exact call IDs and byte offsets to pair outputs, retaining unknown fields.

Both commands are the documented no-GT CLI modes in the preserved [original probe evidence](../evidence/2026-09-29-route2-wsl-synthetic-os-probes.md). Each verified source contains one tools.exec_command call, the exact task workdir and PowerShell shell, with no GT/scientific operation:

| Exact historical call | Authoritative locator in01a0ed14 archive | Observed returned metadata | Limit |
| --- | --- | --- | --- |
|py -3.10 -B scripts/run_route2_candidate_overlap_wsl.py preflight; call_Rld2AUo95RdsGnQLksVUvEVl | call line934/byte6,266,971 at2026-09-29T13:43:52.279Z; output line937/byte6,275,817 at13:43:56.377Z | call/output client-record interval4.098s; explicit text exit=0. | Native QPC/original epoch/cohort/full CPU-RAM-thread-VM-service/storage fees and billed tail remain unproved. The interval is not whole runtime or an admissible original budget balance. |
|py -3.10 -B scripts/run_route2_candidate_overlap_wsl.py probe-cgroup; call_ExR4DpWLZd2MZFHmvh2K2sRa | call line1665/byte9,866,349 at2026-09-29T14:47:32.122Z; output line1668/byte9,884,960 at14:47:42.793Z | call/output client-record interval10.671s; no explicit child-exit scalar was projected. | Do not infer child exit0 from a returned tool record. A local synthetic cgroup observation is no complete preparation/group/VM-service join or history. |

These two client intervals must not be summed into or deducted from native1800/6000 limits. They do not establish either complete charge0, exhaustion or a positive remaining balance. All prior3872MiB first/416MiB repeat logical VHDX growth, local unit peaks, dependency installations and narrow Windows samples remain separate inherited partial records; no deletion refunds/history reset or per-layer double charging. This recovery does not locate a complete original historical ledger or supply the before-load/prebirth controlled preparation entry.

Bounded SOURCE receipts: C03-A read-only audit /root/c03_a_source_eligibility_audit START09:13:00/ALL_READ_STOP09:16:25 UTC (205s within8min). Historical locator /root/historical_session_receipt_locator START09:17:07/header STOP09:18:56 (109s); subsequent selector STOP at the retained09:23:07 hard deadline, with no verified call receipt then. The first unsupported selector recognized zero supported frames; its later follow-up reached the deadline before body inspection. On resumed recovery, its follow-up received the task11:45:52 with23s left before retained11:46:15 stop and inspected zero body records; these zero counts are explicitly not absence. Root independently confirmed both framing tags; source-reader errors included native quote loss, non-JSON JavaScript string escapes, a generated-source syntax error and output-type mismatch. These affected isolated recovery utilities only, not repository/production code. The failed generated-source parser opened no archive. Later root selectors used exact identifiers/offsets and recognized input_text; final selected-scalar projection stopped12:13:29 UTC with both known pairs verified and all handles closed. Root's09:21:32 and11:46:15 source targets have elapsed; subsequent necessary recovery/retention is an explicit source overrun, not a passed deadline, renewed C00 mechanism research or original execution-clock reset. Uninstrumented clock gaps and all resource/model/fee telemetry remain UNKNOWN_NOT_ZERO. No further archive research follows this checkpoint.

C03-A audit found no complete already-fixed independent native capture body to implement. Existing r2_birth_v2 fields and target guards do not fix capture status/error/output-size/per-field validity, private once-burn/close, signed QPC transport, exact bounded first MemAvailable grammar or original pre-Python/pre-spawn owner and consumer continuity. The prose capture_original_linux_birth_v2 signature is absent from native declarations; the existing Python envelope requires systemd_exec_main and has no M0/QPC/deadlines. This is a precise source-contract gap, not proof native capture or this machine is impossible; no new refusal-only/schema-only code is added. User policy choices and independent SOURCE eligibility stay bound; dependent C04-C12 remain STOP even SOURCE.

Condition9 receives additional historical call/output locators only: NOT_CLOSED / UNKNOWN_NOT_ZERO. Condition11 retains the concrete C03/preload contract and actual deployment gaps. Condition13 may receive only a new scoped evidence-recording review after independent SPEC then DIFFERENT fresh QUALITY; full implementation/execution closure review and old full FAIL remain unchanged. All other original14 conclusions and BEFORE versus same-invocation facts are inherited from the preceding full-card delta; there is no second full card or final A+B request.

Actual continued-work prerequisites remain trustworthy original full historical fee/clock/cohort upper bounds and resulting balances, a reviewed installed controlled preparation entry, current task-owned physical disk/extent identities/geometry/exclusive writer scope, and exact original VM/service/final durable exit-join producers. Permission already given does not create these facts; the E:\Route2AdmissionPrep_20261013 namespace remains uncreated and is no physical-cap proof. C00 AUDITED_UNPROVEN / three UNPROVEN / wholeC01C02 incomplete / C03 NOT_STARTED / C04-C12 STOP even SOURCE / PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / oldfullFAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED / Stagezero / Route3fourFAIL / F1open persist. No compile, link, ABI/native load, actual mechanism test, OS/WSL probe, installation, disk change, GT or Stage occurred. Source recovery utilities are not controlled production validation. Fresh scoped record reviews and exact-path Git retention remain pending at append time.


Scoped recording-review receipt: route2-historical-session-metadata-record-review-2026-10-13-001 covers HISTORICAL_SESSION_METADATA_RECORD_ONLY. Fresh SPEC /root/historical_receipt_fresh_spec START12:22:20/ALL_READ_STOP12:25:13 UTC (173s within6min), followed by DIFFERENT fresh QUALITY /root/historical_receipt_fresh_quality START12:27:16/ALL_READ_STOP12:27:35/final STOP12:28:30 (74s within6min), both NO_REMAINING_SCOPED_P1_P2. They read only the original3 recovery suffixes against supplied facts, not archives/implementation/API/runtime. Optional P3 precision is recorded here by append: the two projectors had configured30-second maxima, with reported inner-loop elapsed0.01579s and0.25848s respectively, not actual30-second runs or complete source/loader fees. No interval or process duration becomes native original budget evidence. Root confirmed all403 original identities/full171 index/original11 complete staged rows unchanged before append; old original3 prefixes match baseline ddea3ca. Exact-path retention and actual remote receipt remain pending; no complete formal review, budget/freeze/admission PASS or new run follows.


### Historical receipt recovery Git preservation receipt (2026-10-13)

Actual checkpoint d72b15f3d57598cf08548ab817626cca66781ddf, parent ddea3ca97e2389e5b7bae16cf7988da344589c96, contains only the original3 document paths with52 insertions/zero deletions. Exact committed blobs match raw worktree bytes; full unaffected index rows/original11 mode-blob-stage-path identities and baseline porcelain status are preserved. Non-force push returned a live session25904; root resumed that same session to actual exit0, without restart. Completed remote query at12:42:01 UTC verified feature d72b15f3d57598cf08548ab817626cca66781ddf and unchanged main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b. Native C/H and all400 other file bytes remain unchanged.

This later administrative original3-only receipt receives its own HEAD/final remote confirmation from Git/final reporting, not a self-embedded or preclaimed hash. Two historical client records and the scoped recording-review ID do not create native original budgets, trusted preparation entry, actual dedicated extents, VM-service joins, complete production freeze or full formal review. All14 conclusions/UNPROVEN/STOP/oldfullFAIL/FROZEN_ADMISSION=None/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero remain. No actual experiment/preparation component/native/helper/WSL/GT execution or directory creation follows. Earlier source overruns and fees UNKNOWN_NOT_ZERO remain; only retention/final reporting follows.


### Preparation bootstrap contract clarification and evidence impasse (2026-10-13)

The owner's “继续完成目标” keeps the full admission objective and previous preparation permission in effect. This records a substantive contract clarification; it does not narrow success to another SOURCE component, add an application/epoch, alter the original14 card or change a status field to PASS. Current restored HEAD416856672df48fd2c36fc50b636b037cdb7708e5 is inherited, not reset.

Independent read-only /root/admission_unblock_contract_audit START13:40:19/ALL_READS_STOP13:43:47 UTC (208s within8min) read original3 documents and the gated preparation source. It made no files/Git/native/API/WSL/compiler/test/import/GT operation. Its conclusion distinguishes implementable internal design from genuine evidence prerequisites.

**C03 precision:** earlier “no complete already-fixed capture contract” remains an accurate implementation inventory, but MUST NOT be interpreted as an external permission/fact blocker for its status, output-size, field-validity, once semantics or bounded MemAvailable grammar. Those are internal design choices which may be specified autonomously within the existing independent C03 allowance, then independently reviewed. Their absence alone cannot justify asking the owner to supply a software contract. The SOURCE target/guards and fixed numerical/resource/scientific rules remain bound. This clarification does not implement a capture, fabricate prebirth ownership or authorize dependent handoff.

A COMPLETE preparatory invocation is larger: original-history admission, immutable pre-load ownership, creator/actor accounting, storage/writer controls, STOP_NEW, VM/service drainage and surviving final coordinator acceptance. Plan2238–2248, specifically2245, and2473–2488 retain dependent C04–C12 STOP even SOURCE when any required exact primitive is unproven. The latest preparation permission authorizes a contractual actual invocation when its prerequisites exist; it does not select an unknown producer, provide historical balances or permit a successful bootstrap assembled from caller fields. Independent C03 source completion would not by itself make that complete invocation legal.

The actual source windows_preparation_job.py:802–805 remains refusal-only for missing fixed worker/PE closure/pre-import owner. Its private _kernel_lifecycle at743–796 starts a local post-Python clock, imports observer code and births one worker. Replacing the refusal with that lifecycle cannot establish original pre-load ownership, whole actor fees, original1800/6000 balances or native VM-service joins. No such replacement is made.

| Requirement timing | Concrete prerequisite/fact | Consequence under unchanged contract |
| --- | --- | --- |
| BEFORE any new actual preparation | Authenticated original historical coverage and native clock continuity; complete charge upper bounds and original remaining1800/6000 balances, including60s internal cleanup; original owning startup/deadline/STOP/cleanup mechanisms, immutable loading closure and selected supported producer contracts | A future producer cannot reconstruct an unobserved old epoch/cohort/peak/service/deleted-allocation/tail. UNKNOWN remains unusable as a positive balance. |
| DURING a legally admitted preparation invocation | Its new original raw identities, current geometry/usage, legal compile/link/ABI/load outcomes, continuous fees, failure cleanup and persistent results | These may be generated by the new preparation permission after the enclosing BEFORE contract exists; they need not all be supplied in advance by the owner. Current disk geometry is not a demand to run a Stage. |
| DURING later concretely approved science | First original study M0, fresh double8 before image, formal105+105/counts/GT grants and revocations/live terminal acceptance | Production paths must already be implemented/reviewed and fail closed; no advance Stage or historical sample substitutes for same-invocation facts. |

The recovered historical preflight exit0/client4.098s and local cgroup client10.671s remain truthful partial evidence. They are not native QPC, complete consumed wall, cohort membership, resource peaks, VM/kernel/service fees, per-layer AllocationSize/metadata or original billed tails. Their client intervals are not added to/deducted from native caps. Source hashes/AST/scoped review markers and prospective instrumentation cannot supply the missing retrospective quantities. This is an evidence impasse under the contract, not a finding this host is physically incapable.

The minimum evidence capable of changing the decisive history gate is an original-owner ledger or trustworthy COMPLETE historical upper-bound certificate, with authenticated original epoch/cohort coverage, all preparation/external actors and infrastructure, durations/resource/storage histories/tails and derived original balances. Such evidence could prove prior failure/exhaustion rather than permit continuation. A certificate must not be merely a caller assertion or manufactured history_complete field. Root has recovered partial records and external locators, but no such complete certificate.

The selected WSL mechanism separately still needs an EXACT supported creator/service-scope contract: creator-issued original VM identity, complete billed actor membership and finite original service/callback drainage. HCS VM-exit callbacks, closing operation tracking and a later PID/GUID reopen do not provide that scope. Public API capability is not local deployment/runtime proof. After an enclosing preparation contract is satisfied, bounded current physical disk/extent identity/geometry/exclusive writer facts may be obtained under the granted permission; a concrete irreversible layout/format/shrink plan then needs its separate specific owner approval. E:\Route2AdmissionPrep_20261013 remains a permitted namespace, uncreated and not a physical capacity mechanism.

If the required retrospective evidence was never retained and no trustworthy full historical upper bound can be proven, the fixed combined-history/no-reset requirement leaves no valid route to admission. Further general permission or a newly recording observer does not supply that lost evidence. No request to waive/reset historical limits, move a gate, relax a bound or retroactively legalize work is made. The next meaningful change must provide the missing authoritative evidence or a genuinely supported exact primitive; no new refusal-only code, unwired sampler, status-only PASS or approval card is substituted.

Current inventory remains C00 AUDITED_UNPROVEN, threeUNPROVEN, wholeC01/C02 incomplete, C03 NOT_STARTED, dependent C04–C12 STOP even SOURCE, PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/oldfullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero/Route3fourFAIL/F1open. The complete production installation, necessary no-GT actual mechanism/failure cleanup/budget evidence, full freeze/full formal review and concrete unique final A+B object remain undelivered. These are missing deliverables, not completed by this clarification. Native C/H/source/GT pins are inherited unchanged; no actual preparation/compile/load/probe/installation/disk/GT/Stage operation occurs. All earlier SOURCE overruns and historical fees UNKNOWN_NOT_ZERO persist. Fresh scoped recording SPEC then DIFFERENT fresh QUALITY and exact-path Git receipt follow after root append STOP; they do not count as full implementation/admission review.


#### Original14 conditions: complete closing status increment (2026-10-13)

This is the original14 inventory updated in place by append, not a new card, application, admission seal or narrowed success criterion. SOURCE observations below remain separate from actual evidence. BEFORE means before a newly admitted preparation/experiment as applicable; SAME means a fact produced only by the corresponding legally admitted invocation through already implemented, independently reviewed, non-bypassable production paths. No early Stage is used to manufacture a SAME fact.

| Original condition | SOURCE and actual evidence now | Remaining BEFORE / SAME gates and conclusion |
| --- | --- | --- |
| 1 — One complete A+B object | Existing registration/safe projection remains PREPARED_UNREVIEWED. No complete installed runner, actual executing identity or full-review PASS. | BEFORE: complete production installation, evidence closure, full freeze and full independent review, then one concrete final A+B owner approval and consumable seal. BLOCKED; FROZEN_ADMISSION=None. |
| 2 — Fixed science and equivalence | Saved scores, fixed model/26D/thresholds/decoder/matcher, strict positive overlap versus300-second gap, 5x4, symmetric atol1e-12/rtol1e-10 and discrete exactness unchanged. Historical partial equivalence is insufficient. | BEFORE: complete nested production/equivalence path and frozen legal input protocol. SAME science:105 reference+105 treatment with full provenance and required records; reference reproduction is not authorized preparation. UNPROVEN. |
| 3 — Input bank/generation/publisher | Inherited metadata/batch/GT directory-v2 source and original O_PATH history retained; C01 declaration slice, C02-B1 raw observation and C02-A native Job slice have scoped SOURCE review only. | BEFORE: real creator/complete create-delete history, immutable role backing/no writable aliases, same-FD consumption/revocation and full nested installation. All three exact C00 mechanisms UNPROVEN; dependent C04–C12 STOP even SOURCE. UNPROVEN. |
| 4 — Ledger, counts and image capacity | Protocol keeps25fit/25predict/65decode/20GT-backed evaluations plus21st GT-free algebraic merge, pooledGTreads0. D_A=2GiB strict V2, same image2→4GiB is not2+4. | BEFORE: unique enforcing ledger and finite physical image lifecycle/expansion implementation. SAME science: actual Stage A N/M/S/B/R and authorized Stage B projection/counts, with all lifecycle charges. UNPROVEN. |
| 5 — GT and matched-GT reports | Inherited Stage B final matched-GT additions/losses and execution.finalize double-exception SOURCE fixes retained; no GT payload read this turn. | BEFORE: legal matched-pair provenance, isolated five-field projection and actual broker-backed per-role/phase grant/revoke production. SAME science: canonical GT commitment/consumption and actual report. UNPROVEN. |
| 6 — Worker isolation and identities | WSL2/Ubuntu22.04/glibc2.35/trusted Windows owner, selected B route and exclusive window remain bound. Existing spawn/pidfd/READY/wait/reap/status/UID/namespace/IPC pieces are inherited SOURCE. | BEFORE: supported original creator/worker/IPC/write-path/cleanup implementation. SAME legal preparation/science: original GUID/SID/UID/cohort/FD/mount/cgroup/TID identities and native results. Roles use /run/route2-input/roles/<SHA256(role_id)>; study/.worker is writable scratch/log.4096history/256scan/nlink1 cannot directly cover19894alias/max257role. UNPROVEN. |
| 7 — Physical E capacity | Selected dedicated finite physical extent design; E30GiB=carrier24 including guest20+external6, guest baseline<=8GiB. Only old E geometry and partial logical growth evidence recovered. Permitted preparation directory remains uncreated. | BEFORE: supported full-writer physical extent mechanism and, after valid bounded inspection, exact irreversible target/commands/impact review and approval. SAME legal preparation: current backing identity/geometry/capacity/baselines/metadata/reserve/history. SAME science: guest-hosting FS and actual physical backing each freshfree>=8GiB before image; carrier reserve independent, no third8GiB requirement. UNPROVEN. |
| 8 — RAM/CPU/tasks/original clocks | WholeRAM16GiB/VRAM8GiB; .wslconfig8GB/swap0/processors2/gui=false; StageA1200/study3600/cumulativefit900 seconds incl60cleanup. C=min(4GiB,floor(3*M0/5)), AS=C/2, swap0, CPU200%, TasksMax2 inclcontroller unchanged. Windows approved MONITORED4 application TIDs/fixed-thread design does not replace Linux hard limits or full fees. | BEFORE: original prebirth clock/memory capture, authenticated QPC transport, complete resources/deadline/STOP production. SAME legal invocation: actual configuration/hard-limit application, original M0 and continuous peaks/fees; no post-Python local clock substitution. UNPROVEN. |
| 9 — Preparation/external/history/control fees | Prep+compile/ABI4GiB/200%/MONITORED4/1800s; external512MiB/100%/MONITORED4/6000s, incl60cleanup. Guestcontrol64MiB inside20; hostcontrol16MiB insideexternal6. Infrastructure VM/kernel/service/loader/monitor costs all count. Recovered client4.098/10.671s and storage/dependency fragments remain partial. | BEFORE any new actual preparation: authenticated complete past accounting/native-clock continuity or trustworthy full historical upper-bound certificate, establishing original remaining balances. New observer cannot recreate missing past quantities; UNKNOWN_NOT_ZERO. SAME legal preparation: all new fees and tails continuously merged. DECISIVE EVIDENCE BLOCK. |
| 10 — nonE growth | nonE512MiB MONITORED; STOP_NEW384 and nominal128tail, accepted UNKNOWN in-flight overshoot unchanged. Old PS28–29threads/pagefile observations are partial, not compliant new application evidence or refunds. | BEFORE: complete writer/AllocationSize/history/monitor/STOP implementation with fixed thread design. SAME legal invocation: actual whole scope growth and billed cleanup; deletion/pagefile decrease does not erase history,128 is not physical reserve/overshoot bound. UNPROVEN. |
| 11 — Installation and pre-load closure | Original13-wheel lock/venv/ABI and inherited native/helper interfaces remain historical partial evidence. C02-B1/C02-A C/H are SOURCE-reviewed, still IMPLEMENTED_BUT_UNCOMPILED; unchanged pins inherited. | BEFORE loads: immutable interpreter/stdlib/project/PE/ELF/native/transitive/provider closure, original startup/load boundary and accounting. SAME legal preparation: controlled build/link/ABI/native load/call and dependency installation evidence; no such new actual run admitted. UNPROVEN. |
| 12 — Cleanup and external acceptance | Inherited primary/secondary, once-close/poison, pidfd/OFD/READY/wait/reap source retained. Approved trusted final coordinator may survive acceptance, with all original-scope costs through acceptance and contract tails counted and no later experiment writes. | BEFORE: complete producer/worker/backing-delete/GT-revoke/OOM/crash/quarantine/raw-cgroup/VM/service original-exit/join and independent deadline/durable-QPC/bounded-tail production. SAME legal invocation: native exit/drain/durable E receipt/live acceptance evidence. No unbilled or unjoined witness. UNPROVEN. |
| 13 — Full freeze and formal review | Existing narrow SOURCE reviews and historical metadata recording review are inherited only in their scope. This clarification's valid SPEC then different fresh QUALITY remain pending at writing. Old route2-ab-full-implementation-review-2026-09-29-FAIL-001 remains FAIL. | BEFORE: complete source/runtime/input/rolemap/launcher/worker/controller/protocol/budget freeze with actual identities; truly complete independent execution-closure review and NEW formal full ID. Scoped clarification review cannot close this condition. UNPROVEN. |
| 14 — Separate scientific success | Route3v1-003 legitimate COMPLETE/four-gate FAIL retained, not rerun. Route2 StageA/B has no legal run/results. Fixed quality gates pooledF1>=.66, >=3/5 foldsF1>=.66, per-foldlongFP<=.25, start/endMAE<=900seconds and realmatchedGT report remain. | SAME authorized science only: declared lawful early stop or complete five-fold Stage B, reporting COMPLETE separately from quality success. F1>=.66 objective open; no automatic model branches. NOT_EXPERIMENT_AUTHORIZED. |

The documentary SPEC attempt /root/bootstrap_contract_fresh_spec is INVALID: START14:12:25/read-stop14:20:37 UTC492s exceeded its360s SOURCE limit; it also exposed older suffix text. Its no-scoped-finding statement is not a passed receipt. /root/bootstrap_clarification_fresh_spec2 is also INVALID: START15:06:13/STOP15:09:12 UTC179s, unauthorized skill-file read before any of the three frozen suffixes, no SPEC verdict. Both failures remain historical; no actual preparation clock is reset and all historical charges/UNKNOWN_NOT_ZERO remain. Root has made only this documentation increment. A new bounded independent SPEC, followed only after valid completion by a different fresh QUALITY, must review the final frozen clarification and this complete status table; neither is full admission review.


#### Preparation contract clarification: scoped dual-review receipt (2026-10-13)

Scoped record ID `route2-preparation-contract-clarification-review-2026-10-13-001` covers ONLY this frozen documentary clarification and original14 status increment, not production implementation, runtime closure or admission. Fresh SPEC /root/bootstrap_clarification_final_spec retained original START15:13:51 and deadline15:19:51 UTC: initial pre-content hash-label stop15:13:54, corrected suffix hashes then ALL_READ_STOP15:18:48/FINAL_STOP15:19:04, total313s within360; no clock reset. Root had supplied whole-file hashes without identifying their scope; the correction changed no file bytes. Different fresh QUALITY /root/bootstrap_clarification_final_quality START15:21:24/ALL_READ_STOP15:21:28/FINAL_STOP15:21:45,21s within360. Both concluded NO_REMAINING_SCOPED_P1_P2 / PREPARATION_CONTRACT_CLARIFICATION_ONLY. Earlier two INVALID attempts remain INVALID.

The reviewed suffixes at offsets383834/499532/702517 had lengths2023/2023/16641 bytes and SHA256 2ff4631add8d858278e509c2d23848573a6513fd14f47b7903299c17d905375f / same / 5376e91bee5e47206be8ad85ef0f271fe8b1a83b06bf2974e0397ceaa043b15a. Root preservation check before this administrative receipt confirmed403 file identities,400 unrelated bytes unchanged, all171 complete index rows identical including original11 staged mode/blob/stage/path identities, all three entire4168566 HEAD prefixes identical and diff --check exit0. Only original3 doc suffixes changed. No actual preparation/native/compile/load/install/disk/GT/Stage run occurred; costs remain UNKNOWN_NOT_ZERO and original clocks/balances unproven. Git exact-path commit/push/remote receipt follows. Full FAIL/FROZEN_ADMISSION=None/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED and all original14 gaps persist.


#### Preparation clarification Git receipt (2026-10-13)

Exact-path commit e762f973f15f85cddd298d7c615ad697ab801581, parent416856672df48fd2c36fc50b636b037cdb7708e5, changed only original3 documents with90 insertions/zero deletions (review60,plan15,spec15). Committed raw blobs were review30672c018102ef356dc6040f36fa961d5e333993, plan ddf95c3ac3fbb41192eb75d66972c214fd2b9209 and spec d86d1addb46d7057fbe888741b00f23466476900, matching precommit bytes. Postcommit verification preserved403 identities/400 unrelated bytes, complete unaffected index rows including original11 staged mode/blob/stage/path and exact original porcelain-v2 dirty/untracked status. A precommit status comparison using v1 versus the baseline's v2 stopped before mutation; same-format v2 verification corrected that false alarm. No unrelated content was changed.

Non-force push completed exit0; git ls-remote verified at15:30:54 UTC feature=e762f973f15f85cddd298d7c615ad697ab801581 and main=dd05aa128f8d62a85c20a83f8af72fe13fcfa27b. This administrative receipt is appended only to original3 and will receive its own exact-path commit/non-force push; its final hash is reported after verification. Scoped documentary review route2-preparation-contract-clarification-review-2026-10-13-001 remains ONLY clarification/status recording. Full admission objective is unmet: authenticated full original historical accounting/balances and exact supported creator/service scope remain decisive; allthreeC00 mechanisms UNPROVEN, dependentC04–C12 STOP, fullFAIL and unready/unauthorized states retained. No actual preparation, disk alteration, GT or Stage occurred. UNKNOWN_NOT_ZERO and all original14 obligations remain.


### Resumed C00 engineering/history investigation and C03 parser implementation (2026-10-13)

The owner accepted the responsibility correction: engineering, bounded historical recovery and independent lawful source work remain root's work; no new general permission is requested. Goal was explicitly restored active during this work, verified by get_goal at16:33:56 UTC; no completed objective or budget reset is inferred. Full original14 admission objective, B/WSL/science/selected mechanisms/caps and prior actual authorizations remain unchanged. C04–C12 STOP even SOURCE still applies while any exact C00 prerequisite is UNPROVEN. Root remains original3 document author; native parser has one separate author.

**Routing/evidence boundary.** RESEARCH / PARALLEL_SUBAGENT, actual collaboration backend, disjoint readonly WSL-source and history investigations plus one independent C03 designer/implementer. WSL research720s, history720s, C03 design600s, parser implementation720s; acceptance requires exact evidence/contract fit, never UNKNOWN-as-zero or a source marker as admission. Independent SOURCE clocks are not original preparation/external clocks. No compile/link/ABI/load/install/helper/native/WSL/hardware/GT/Stage run or preparation directory/physical layout was created. All historical/current/future charges remain UNKNOWN_NOT_ZERO; source manual clock/hash evidence is not a complete actual-resource ledger.

**C00: concrete WSL mechanisms investigated.** /root/c00_wsl_exact_scope_research START15:52:34/read-tool STOP16:03:40 UTC666s within720. Three paths were examined: supported stock plugin hooks; creator-level WSL source integration; exclusive session plus conservative complete-host/infrastructure charging. No path was established as a complete selected deployment/accounting/drain producer. Public API capability and SOURCE creator callpoints must remain separate from local runtime proof.

Root closed the moving-master/source-version gap with one read-only git ls-remote and two immutable source retrievals: microsoft/WSL master observed at commit f0d348baffc2c0ee96bdca20f56cd974ef03f50b. The pinned [WslCoreVm.cpp](https://github.com/microsoft/WSL/blob/f0d348baffc2c0ee96bdca20f56cd974ef03f50b/src/windows/service/exe/WslCoreVm.cpp) text SHA256 was06e4ff2a29dca8474ca0a84f4205bb6375eb8a74fe150ba13fc30102a9b0b189; pinned [WslPluginApi.h](https://github.com/microsoft/WSL/blob/f0d348baffc2c0ee96bdca20f56cd974ef03f50b/src/windows/inc/WslPluginApi.h) text SHA2560c0f6a0ec47581af95e9dde12e80a77546bcb996e1eeece9f898008f4683eb07. These are decoded downloaded SOURCE text hashes, not an installed binary/dependency freeze. No package was installed or service modified.

At this pin, WslCoreVm::Create(UserToken,Config&&,VmId,InitializeDrvFs) receives the creator GUID (108–109); Initialize assigns machine ID (171–184), retains original CreateComputeSystem result (354), queries runtime ID and checks creator equality (356–357), then registers callback/starts VM (374/381). This is a concrete original-owner integration callpoint, not late PID/GUID discovery. It does not expose a ready complete stock frontend producer. Pinned plugin synchronous OnVMStarted/OnVMStopping (218/222) receives session ID/token/SID (67–71) and configuration flags (60–62), without original VM GUID/HCS owner; it shares WslService's address space.

Pinned VM teardown has detached initialization (495) and detached termination callback work (2552); destructor waits on a future (743). Its close comments (816–817 and2390–2392) describe waiting for outstanding compute-system callbacks. That SOURCE observation corrects any overly broad inference that handle close has no callback behavior; it still does not establish finite deadline, all detached work, original WslService/HCS/kernel shutdown or complete accounting. [HcsCloseComputeSystem](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsclosecomputesystem) is a void handle-close API, not an independently returned whole-service drain/cost receipt. No unbounded wait may become a normal complete result merely because a local VM exit callback fired. Conservative whole-infrastructure charging is a legitimate candidate only if complete upper bounds fit the unchanged scopes; no such fit is proven. VM_SERVICE_SCOPE_UNPROVEN persists. WSL source integration remains an engineering prospect, not a request that the owner supply API design and not a selected installed fork.

**Physical capacity/final coordinator.** Context7 resolve-library-id then one scoped query used official Win32 API library; official [volume disk extents](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents) and [disk layout](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_get_drive_layout_ex) support held volume/disk geometry queries via DeviceIoControl. These do not lock current geometry, establish current privileges/exclusive writers, supply all allocation metadata or prove the selected16MiB ordinary host-control filesystem/region. Existing exact extent/formatter/reserve/stop contract and bounded surviving coordinator contract remain bound. Root made no local physical queries or changes: original full-history/owned-preparation BEFORE gate is still missing. A concrete irreversible target/commands/impact approval cannot be responsibly requested from old Disk1/Part2 geometry alone. E_PHYSICAL_CAP_UNPROVEN and OWNER_EXIT_JOIN_UNPROVEN persist; this is not local physical impossibility. Approved coordinator survives acceptance with original deadline/billed bounded readonly tail/no experiment writes unchanged.

**Historical recovery: stronger coverage, still no original balances.** /root/historical_upper_bound_reconstruction started15:53:34 with16:05:34 hard stop. Four previously identified archives yielded38,266 line envelopes and3,212 recognized exec invocations (176/39/2258/739);772 other-tool frames counted separately (92/9/259/412), zero selected-frame parse errors. Each selected invocation had one return envelope, zero missing/duplicate/negative interval pairs. Client sums507.540/501.142/9134.444/3215.894s are NOT original consumed wall: overlap, source actions, async children and47 write_stdin/10 October Start-Process source mentions prevent that deduction. A sum above a cap is not exhaustion proof.

The exact existing no-GT Windows QPC wall receipt contains frequency10,000,000; started6083251378366, fsynced6083259049235, observed6083259137962; local start-to-fsync0.7670869s/start-to-observation0.7759596s and local10s deadline. It has no original epoch/boot/cohort/preload/full-consumption/balance linkage. This adds a raw local clock fragment, not original t0 continuity, complete actor history or available1800/6000 balances. Existing storage/dependency/peak fragments retain their prior limitations and cannot be refunded/double-counted.

History scope/timing exceptions are explicit: the reader opened using-superpowers instruction outside its dispatched source whitelist; last source inspection time16:03:44 was approximate, while authenticated later clock16:06:18 gives total764s,44s beyond720. No scope-clean formal review/PASS is claimed. No output bodies/GT/scientific records/project code execution/new files were used. Findings are factual metadata/whitelisted OS-receipt recovery, not proof that every possible historical record is absent. These archives remain compatible with different unrecorded background/service lifetimes, peaks/deleted allocations and tails. No trustworthy full upper bound below original caps was recovered. Further generic filename/envelope scanning is not a useful substitute for an exact original-owner ledger/controller receipt binding original epoch/cohort/all actors/native costs/storage/tails. Native bootstrap capture and prospective monitoring cannot repair an unobserved past. This decisive history gate remains an external evidence requirement under the current contract, not a proven cap exhaustion or host failure.

**C03 independent implementation.** Designer START15:57:36/read STOP16:06:03 UTC507s within600; author implementation START16:09:41/read-write STOP16:15:45 UTC364s within720. Only existing native C/H were appended. Public route2_linux_parse_memavailable_v1 parses complete caller-provided bounded guest meminfo bytes; it does not sample /proc, create/claim original M0/t0/once owner, authenticate transport or authorize anything. Fixed status/size/validity/grammar choices are internal, not owner fact/permission demands. Future complete capture remains original native guest parent before controller birth/Python, with CLOCK_MONOTONIC, once-owned open/read/EOF/close/failure semantics as the fixed design; no such producer/entry/consumer is added.

Parser: native recordABI1/size32/alignment8/offsets0,4,8,12,16,24; statuses0–9; max16,384 input/512 per LF-inclusive line/64 key/20 digits. Grammar DECIMAL [ HSPACE+ "kB" ] HSPACE* LF within complete keyed lines; exact MemAvailable requireskB, one match, checkeduint64 accumulation/1024 conversion; every unrelated/trailing line is checked. Zero is valid raw parsed data. Bad output/range/alignment/overlap leaves output unchanged; recognized-output ordinary failures publish ABI/size/status with zero numeric/validity fields; only full success setsvalid1. Caller supplies accessible bytes/exclusive valid output. No OS/heap/errno/global/once/capture/producer/consumer or admission fields. No TDD runtime cycle/test/compile/ABI/run result is claimed; meaningful synthetic boundary/failure cases are queued for legal preparation.

Fresh SPEC START16:18:11/read STOP16:19:13/final STOP16:20:43 UTC152s within480 found no scopedP1/P2. Different fresh QUALITY START16:22:18/read STOP16:23:36/final STOP16:25:22 UTC184s found oneP2 header grammar wording. Same sole author repaired only that new comment START16:26:11/STOP16:27:32 UTC81s within300; C behavior/bytes unchanged. SPEC re-review START16:31:45/read STOP16:31:48/final STOP16:32:04 UTC19s within240 passed; different QUALITY re-review START16:33:25/read STOP16:33:48/final STOP16:33:55 UTC30s within240 passed. Final scoped ID route2-c03-memavailable-parser-source-review-2026-10-13-001 = NO_REMAINING_SCOPED_P1_P2 / C03_MEMAVAILABLE_PARSER_SOURCE_ONLY, IMPLEMENTED_BUT_UNCOMPILED. It is not wholeC03 or full admission review.

Final native C50,735 bytes SHA9405332714cb146ce59c9db0289a00043ab0eb01ea922af4ef7177eca9f25691; H17,363 SHA541ec7516757f907f430a80f6ec7ef7f29066610591da5eafc485fde17545b42. Entire preexisting41,410 C/14,779 H prefixes retain0982f899b883ff3fb2268d42473c9bea951dbed0ce569a359e15a8e4b392e3f4 / d94ce542b9ab2ec3ee7ed8bd634b216a2696f17b856a20c0108648bd5079cd95. New suffix9325/2584 hashes3fcc845b11a16f5d796ca30717d7aa73d1f16e64ed972db383709362eacc7e29 /272097d2bf2665f9d60ec754dfaebd1bf3babc49660b0ef285a63bf3489c26dc.

**Inherited header pin precision:** original f0ba H is8,584 bytes SHAa60683ab57ce9293448d1b6951c903b7bcbad0c3057ed12c1eb5df89692d2e63. Earlier C02-A inserted before its final8-byte endif, so current first8,584 bytes are not that complete old file. Reconstructing unchanged first8,576 bytes plus original final8 now at14771–14778 yields exacta60683... . The earlier raw-prefix assertion was imprecise; original B1 declarations/bytes are retained around the already-reviewed insertion, and C03 preserves the entire current14,779-byte header. No old bytes are rewritten to force a historical hash. Original C17,574 prefix still exact351eaa16c3394102530c9d2c3d085daaf3e84c1b23cfbd8050a2ed2611e7112b.

#### Original14 closing condition update for this resumed work

This is the existing14 inventory's single closing increment, not a new application/card. All numerical/scientific/identity/same-invocation rules retain their full previous rows. SOURCE and actual evidence are separated below; SAME facts require already implemented, reviewed, non-bypassable legal production paths.

| Original gate | SOURCE / actual evidence now | Remaining BEFORE / SAME conclusion |
| --- | --- | --- |
| 1 completeA+B | No complete installed runner or consumable admission seal; PREPARED_UNREVIEWED. | BEFORE complete production/evidence/fullreview/freeze then concrete ownerA+Bapproval; BLOCKED,FROZEN_ADMISSION=None. |
| 2 science/equivalence | Saved scores/model26D/threshold/decoder/matcher/strict-overlap-vs300s/5x4/tolerances unchanged; only historical partial evidence. | BEFORE full nested/frozen legal protocol; SAME approvedscience105+105/source provenance/equivalence. UNPROVEN. |
| 3 immutable inputs/creator | Prior broker/batch/O_PATH/source fixes retained; C03 parser does not create or freeze a role. | BEFORE realbank/generation/rolecreator/history/immutablebacking/noalias/sameFD/revoke/nested; C04–C12STOP. UNPROVEN. |
| 4 ledger/counts/image |25fit/25predict/65decode/20GT+21stGTfree/pooledGTreads0/D_A2GiBstrictV2/sameimage2→4 unchanged. | BEFORE enforcing ledger/finite complete capacity lifecycle; SAME legalAcounts/Bprojection/expansion withallfees. UNPROVEN. |
| 5 GT/matchedreports | Directory-v2,finalmatchedGT增减/finalize fixes retained; no GTpayload access. | BEFORE actualprovenance/isolatedprojection/broker grants/revokes; SAME legalGTcommitment/consumption/report. UNPROVEN. |
| 6 isolation/identities | WSL2Ubuntu22.04glibc2.35/B/exclusivewindow fixed; pinned creator source is prospect, not installed identity. | BEFORE completephaseworker/writepaths/cleanup; SAME originalGUID/SID/UID/cohort/FD/namespace/IPC/cgroup/TID identities. Role path/hash and4096/256/nlink1 limits unchanged. UNPROVEN. |
| 7 Ephysicalcap |30=24carrierincl20guest+6external; baseline<=8; selectedextent/publicgeometry APIs only; no currentphysicalproof or diskchanges. | BEFORE exactmechanism/approvedirreversibleplan; SAME legalpreparationgeometry/allmetadata/history/reserve andsciencefreshguestFS+actualphysicalbackingdouble8; no third8. UNPROVEN. |
| 8 originalM0/t0/resources | PureMemAvailable parser SOURCEdualpassed only; no M0/t0 producer. Whole16/8GiB,wslconfig8GB/swap0/2CPU/gui=false,C=min4GiBfloor3M0/5,AS=C/2,LinuxCPU200%/Tasks2,1200/3600/900incl60 retained. | BEFORE originalcapture/QPCtransport/hardowners; SAME actualconfiguration, firstoriginalguestM0/clocks/continuouspeaks. WindowsMON4 doesnotreplaceLinuxhard. UNPROVEN. |
| 9 fullhistoricalbudgets | Prep4GiB/200%/MON4/1800,external512MiB/100%/MON4/6000incl60;controls64/16MiB内计; infrastructure全计. NativeQPCfragment andcomplete selectedexec-envelope pairing are partial. | BEFORE trustworthyfullpasthistory/nativeepoch/originalremainingbalances; SAME allnewcosts/tails merged. DECISIVEUNKNOWN_NOT_ZERO; neitherzero norexhaustionproven. |
| 10 nonEspill |512MiBMONITORED/STOP_NEW384/nominal128tail/acceptedUNKNOWNinflightovershoot unchanged; no current completewriterobserver. | BEFORE fixedmonitor/fullwriters/AllocationSize/history/STOP; SAME entiregrowth/billedtail/no deletionrefund. UNPROVEN. |
| 11 load/installclosure | Oldwheel/native evidence partial; C02-B1/A andnewC03parser SOURCEreviewedUNCOMPILED. | BEFORE immutablePE/ELF/interpreter/stdlib/project/transitive/providerpreloadowner; SAME legalbuild/link/ABI/load/install receipts. Noactualnewrun. UNPROVEN. |
| 12 exit/cleanup/durable | PinnedWSLclosecallbackbehavior adds source precision, not wholejoin; approved surviving finalcoordinator/tail unchanged. | BEFORE completeoriginalheldidentity/deadline/GTrevoke/backingdelete/rawcgroup/VMservice/asyncdrain/durableQPC; SAME actualfailurecleanup/exit/receipt/acceptance. UNPROVEN. |
| 13 fullfreeze/formalreview | NewC03scopedsourceID only; this resumedrecord freshSPEC/differentQUALITY pendingatwriting. OldfullFAIL-001 remainsFAIL. | BEFORE actualcomplete source/runtime/input/rolemap/launcher/worker/controller/protocol/budget freeze andNEWtrulyfullindependentreviewID. UNPROVEN. |
| 14 sciencequality | Route3v1-003合法COMPLETE/fourFAIL retained; Route2zero legalStage/results; fourqualitygates andactualmatchedGTreport unchanged. | SAME laterapproved lawfulstop/fullfivefoldB; COMPLETEseparatefromquality. F1>=.66 open,NOT_EXPERIMENT_AUTHORIZED. |

Current C00 AUDITED_UNPROVEN/allthreeexactprimitives UNPROVEN, wholeC01/C02 incomplete, C03 independentparser SOURCE_REVIEWED/IMPLEMENTED_BUT_UNCOMPILED withwholeC03incomplete, C04–C12STOPevenSOURCE. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED persist. Originalapprovalprompt/card, all unrelated dirty/staged/untracked and original11 complete index identities are protected. Root stops writing for scoped documentary SPEC then DIFFERENT freshQUALITY; these and exact-path Git receipts cannot close the full objective. No generic permission shortage or local impossibility is claimed; no historical/clock waiver or new approval object is introduced.


Source Git receipt: exact-path native commit91e500517c3ea2a2be1ba0312a8330e1bebaf572 parentd70f684cf1938752db73d1da0894b08be9090961 changed only C/H with226/54 insertions,zero deletions. Raw committed blobs4375dd3fad97cb4d9593e3ba241ea391d8e87999 /b838fd427f5725791c29a55be71a0b1456d74d59 match reviewed bytes. Postcommit403-file set/401 unrelated bytes, original dirty/untracked and all unaffected index rows including11 complete staged identities preserved. Non-force push exit0; remote check16:42:18 UTC feature91e500517c3ea2a2be1ba0312a8330e1bebaf572/main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b. It is a SOURCE parser commit, not runtime/admission success. Subsequent original3 record review/Git facts follow separately.


#### Resumed C00/C03 record: scoped independent review receipt (2026-10-13)

Only the final frozen resumed investigation/source/Git/original14 recording suffixes were reviewed. Fresh SPEC /root/resumed_c00_record_fresh_spec START16:44:32/read STOP16:45:05/final STOP16:45:27 UTC55s within480; DIFFERENT fresh QUALITY /root/resumed_c00_record_fresh_quality START16:46:58/read STOP16:47:25/final STOP16:47:52 UTC54s within480. Both verified exact3 slices and concluded NO_REMAINING_SCOPED_P1_P2 / RESUMED_C00_C03_RECORD_ONLY. Scoped recording ID route2-c00-resumed-mechanism-history-record-review-2026-10-13-001 is not full implementation/runtime/admission review. C03's separate parser source review remains SOURCE_ONLY/UNCOMPILED; oldfullFAIL and alloriginal14 BEFORE/SAME gaps persist.

Frozen original3 slices: specoffset389386/plan505084 length2169 each SHA f1c4efb52645cef35a80008971fc9ff567ed9f677b663435ba720272fbf84c87; reviewoffset722687 length17676 SHA c3f2a47305036b2835b6e92d59510c1c22bdbc3a704ba45332124c4c39ac0ac6. These identify only reviewed documentary increments, not complete freeze. Root appends this administrative receipt, then exact-path original3 commit/non-force push with preservation and remote receipts. No actual preparation/compile/install/native/WSL/disk/GT/Stage, no historical-zero/reset/waiver and no additional application object. Goal remains active at writing; the original historical evidence gate still prevents actual work and the full objective is unmet.


#### Resumed investigation documentation Git receipt (2026-10-13)

Exact-path original3 commit3d9742f6807446c502d5a4358589dd65cad2aeab parent91e500517c3ea2a2be1ba0312a8330e1bebaf572 changed96 inserted/zero deleted lines (review66/plan15/spec15). Raw doc blobs review790c86680725c1851b633db3b03ae54d0344dd38, plan3ee655b7a4375843ff395825b00f245d56f80284, spec9a062ed4e7d7d0b41d251759f6aafa5b092bcce2 matched precommit bytes. Original3 whole prefixes,403-file identity set,400 other bytes including reviewed nativeC/H, unaffected full index including11 staged identities and exact original dirty/untracked status were preserved. Non-force push exit0; remote check16:55:44 UTC feature3d9742f6807446c502d5a4358589dd65cad2aeab/main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b.

This administrative receipt follows valid scoped record review; it receives its own exact-path original3 commit/push, with final remote hash reported after verification. Source parser commit91e5005 remains SOURCE_REVIEWED/UNCOMPILED. Goal active is not completion: original full history/remaining-budget evidence is unavailable in recovered records, allthreeexactmechanisms remainUNPROVEN, dependentC04–C12STOP and all14/fullFAIL/unready/unauthorized states remain. No generic permission request or guessed history certificate can change that. Any future owner decision about opening a history-accounting contract redesign/review would authorize only drafting that concrete proposal; no original-clock/budget change, actual run, disk alteration or Stage may be inferred. Such redesign is not authorized by this receipt and original no-reset/full-history rules remain in force. No new objects, actual preparation, GT or science occurred; UNKNOWN_NOT_ZERO remains.


### C00 follow-up: formatter containment and typed exit evidence (2026-10-13)

Previous resumed goal turn is PROGRESS: authoritative native parser commit91e5005 and record commits3d9742f/d78364e changed source/evidence while retaining the complete objective. This automatic continuation restores actual HEADd78364e2764d1109578c944d60139bbde7387da3/feature branch; it does not treat a pending conversation question as a live-process verified wait or as approval. The owner's history-accounting proposal scope decision remains unanswered at writing, so original full-history/no-reset/1800+6000-before-preparation rules remain effective. No actual preparation, object creation, disk query/alteration, helper/compile/ABI/load/installation, GT or Stage is performed.

RESEARCH / PARALLEL_SUBAGENT uses two disjoint bounded public-SOURCE questions; no production implementation is added. Physical-control source START17:14:47/STOP17:23:20 UTC513s within600. Termination source START17:15:16/READ_TOOL_STOP17:21:05 UTC349s within480. Termination reader disclosed an initial using-superpowers instruction-file read outside its no-file dispatch; this is retained as a scope exception, not a scope-clean formal review. Context7 resolution preceded concept queries; transport failures were replaced only with official primary documentation. Root made one immutable-source recheck, matching previous decoded-text SHA; tool-rendered line indices are not raw GitHub-file line numbers and need not imply a different revision. All SOURCE fees/actual historical budgets remain UNKNOWN_NOT_ZERO, not inferred from these clocks.

**Exact host-control capacity consequence.** [CreateVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-createvirtualdisk) and [parameters](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-create_virtual_disk_parameters) permit a legacy fixed VHD candidate >=3MB with512-byte sector alignment and default block0. Microsoft explains that a [fixed VHD file](https://learn.microsoft.com/en-us/archive/msdn-magazine/2009/april/windows-with-c-the-virtual-disk-api-in-windows-7) includes a512-byte footer beyond virtual size. Therefore a16MiB MaximumSize already exceeds the complete16MiB physical control-file budget before host allocation/metadata; virtual size cannot be used as that physical bound.

A conditional arithmetic candidate uses15MiB virtual bytes15,728,640, footer-inclusive file length15,729,152; IF host allocation units are4096, rounded allocation15,732,736 leaves1,044,480 of16,777,216. These are derived envelopes, not queried actual sizes/cluster geometry/baselines or formatter outcomes. Host filesystem metadata/writers still need physical containment and complete charges. Simply placing this file on the larger external E6 filesystem does not prove the independent control cap. No backing-type substitution is selected or created; the preferred physical control subextent remains the first conditional preparation case.

[MSFT_Volume.Format](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/format-msft-volume) advertises NTFS and allocation options, but gives no numeric NTFS minimum or complete16MiB metadata guarantee. [IVdsVolumeMF2::FormatEx](https://learn.microsoft.com/en-us/windows/win32/api/vds/nf-vds-ivdsvolumemf2-formatex) exposes VDS_E_VOLUME_TOO_SMALL and filesystem-dependent cluster constraints. NTFS “8MB minimum” folklore is not current-provider proof; no successful fitting filesystem is inferred. [CreatePartition](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/createpartition-msft-disk) can round unspecified-alignment offsets, so requested size/offset must not replace actual held layout.

**Formatter stop is separate from wrapper stop.** MSFT Format returns FormattedVolume/ExtendedStatus but provides no cancellation/job handle or absolute deadline parameter. [IVdsAsync::Cancel](https://learn.microsoft.com/en-us/windows/win32/api/vds/nf-vds-ivdsasync-cancel) is not implemented by dynamic providers; basic providers check cancellation only for disk cleaning, not formatting. [QueryStatus](https://learn.microsoft.com/en-us/windows/win32/api/vds/nf-vds-ivdsasync-querystatus) is nonblocking and requires the operation HRESULT: its own S_OK can coexist with pending work. The [legacy WMI Format contract](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/vdswmi/format-method-in-class-win32-volume) explicitly says canceling the client call leaves the provider formatting. No wrapper exit/timeout/cancel flag proves all writer quiescence, rollback or deletion safety. Any helper/provider actor remains within original billed scope/exit obligations.

**Pinned WSL exit semantics are more precise.** Root re-downloaded only WslCoreVm.cpp at microsoft/WSL f0d348baffc2c0ee96bdca20f56cd974ef03f50b; decoded text hash06e4ff2a29dca8474ca0a84f4205bb6375eb8a74fe150ba13fc30102a9b0b189 matches the earlier source. Actual raw file [line1477](https://github.com/microsoft/WSL/blob/f0d348baffc2c0ee96bdca20f56cd974ef03f50b/src/windows/service/exe/WslCoreVm.cpp#L1477) enables ShouldTerminateOnLastHandleClosed. The generic HCS default VM-survives-client example therefore cannot establish this pin's behavior. The option causes termination on last close; it still does not provide a finite completion/whole-service drain/accounting receipt, and another retained handle changes which close is last.

At raw [line2885](https://github.com/microsoft/WSL/blob/f0d348baffc2c0ee96bdca20f56cd974ef03f50b/src/windows/service/exe/WslCoreVm.cpp#L2885), BOTH HcsEventSystemExited and HcsEventServiceDisconnect enter OnExit. The merged m_vmExitEvent/OnExit signal alone is not actual VM-exit proof. The [HCS event contract](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcs_event_type) distinguishes service connection loss from system exit. A future source-integrated owner must preserve original typed event/identity or completed original termination operation; no dependent terminal implementation is added now.

[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess) starts asynchronous termination and requests I/O cancellation; physical exit waits for that process's pending I/O. A signaled original process handle establishes actual process death and eliminates its user callbacks, including detached threads. It does not terminate child processes or prove VM/HCS/sibling/kernel drain. Microsoft provides no finite physical-exit bound. [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) timeout on modern Windows excludes low-power periods, so a local wait duration cannot replace the original absolute native-clock predicate. Early service self DuplicateHandle can yield a real same-object process handle, but authenticated creator/recipient/prebirth scope remains an unimplemented integration requirement; opaque HCS_SYSTEM cross-process duplication is not assumed.

**Conditional qualified acceptance sequence, not deployed producer:** original creator/cohort/HCS identity and independent deadline owner BEFORE work -> STOP_NEW/freeze experiment writes and capture original cleanup t0 -> D=min(original external t0+6000s, original cleanup t0+60s) -> completed original [HcsTerminateComputeSystem](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsterminatecomputesystem) operation/typed genuine exit (initiating S_OK is not completion) -> actual original process-handle joins for every service/helper/actor -> separate complete residual infrastructure drain/final billing -> durable E receipt/verification then acceptance QPC<D -> bounded billed readonly coordinator tail. Finite deadline bounds normal acceptance, not a promise every stalled kernel/provider must physically exit by D. Timeout/unknown residual/late durability fails normal completion, retains identities/charges and never becomes JOINED_EXITED. [HcsWaitForOperationResult](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcswaitforoperationresult) and [HcsWaitForComputeSystemExit](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcswaitforcomputesystemexit) distinguish original completion/exit observations from close/cancel requests. Stock service status/PID polling is not creator-issued process joining.

**Next meaningful validation, still gated:** after original historical balances and complete owned preparation contract are proven, resolve actual physical disk/extent/metadata/alias identities; review any specific irreversible commands and obtain their explicit approval; then test exact <=16MiB NTFS control layout with supported cluster options, ordinary FileId/AllocationSize/core-seal durability, provider terminal/quiescence and billed cleanup. A smaller fixed-VHD case is conditional on separately proven all-host-metadata physical confinement, not a substitute. In the original pinned VM/service cohort test SystemExited versus ServiceDisconnect, outstanding formatter/callback/I/O/child failure cases, absolute-deadline rejection, durable receipt ordering and residual billing. No test has run, and existing permission supplies no missing history or selected complete owner.

This evidence changes required test/acceptance predicates for original14 gates7/9/12/13; all other complete rows remain at the preceding original14 update. C00 allthreeUNPROVEN, C03 parser SOURCE_REVIEWED/IMPLEMENTED_BUT_UNCOMPILED/wholeC01-C03 incomplete, C04–C12STOPevenSOURCE, PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/oldfullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/zero legalRoute2/Route3fourFAIL/F1open persist. No source/manifest/approval/card bytes changed, no new handoff. Source findings do not prove16MiB NTFS failure or local impossibility. More generic API research cannot substitute for these legally admitted native tests. After root append stop, independent SPEC and DIFFERENT fresh QUALITY review ONLY this record; no full admission review is claimed.


#### C00 formatter/exit precision: scoped review receipt (2026-10-13)

Fresh SPEC /root/c00_precision_record_spec original START17:34:04/read STOP17:35:25/final STOP17:35:47 UTC103s within360. Its initial pre-content stop confused root's AUTHOR freeze17:30:47 with the review deadline; root clarified and the SAME original17:40:04 deadline remained, without resetting its clock. DIFFERENT fresh QUALITY /root/c00_precision_record_quality START17:37:48/read STOP17:38:22/final STOP17:38:39 UTC51s within360. Both verified exact3 slices and concluded NO_REMAINING_SCOPED_P1_P2 / C00_FORMATTER_EXIT_RECORD_ONLY. Scoped record ID route2-c00-formatter-typed-exit-record-review-2026-10-13-001 is a factual source/contract recording review, not full implementation/runtime/admission PASS.

Reviewed specoffset394789/plan510487 length1199 each SHA f6f42bfcc39104c21d105124f340135ad8f4c6c68bd8fb8f856d2d7208392cfd; reviewoffset743597 length10141 SHA292f535c357026db4add3e708537b829ad84a484ecb91ecc863f61b7bd612217. No existing SOURCE was changed or tested; pureC03 remains uncompiled and allthreeC00/fulladmission failures remain. Root appends only this actual administrative receipt, then exact-path original3 Git verification. Pending owner scope question stays unanswered/notapproval; no actual budget/clock/contract amendment or experiment is inferred.


#### C00 precision Git receipt (2026-10-13)

Exact-path original3 commit411e890e3a160b7b6eff285b6b55e48dac179bbf parentd78364e2764d1109578c944d60139bbde7387da3 inserted58/removed0 lines (review34,plan12,spec12). Committed raw blobs review76414fda929e18ac7375f77da0fcec4c72c6d78c, plan7ad766254aad2e47470728198065bff8815fd8c4, specf33590fe633cce88515ccad76ebc26e223a7976f equal reviewed precommit bytes. Full original3 prefixes,403-file set/400 other bytes including nativeC/H, original dirty/untracked and unaffected index including11 original staged mode/blob/stage/path rows preserved. Non-force push with per-command HTTP/1.1 completedexit0; ls-remote17:46:05 UTC feature411e890e3a160b7b6eff285b6b55e48dac179bbf/main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b.

This administrative receipt is appended only to original3 and receives a final exact-path commit/non-force push; its final hash is reported after verification. Scoped formatter/typed-exit recording dualreview doesnotclose fulladmission. Goal remainsactive atwriting, pending scope answer isnotapproval, originalhistorybudgetblock/allthreeUNPROVEN/wholeimplementation-runtime-freeze-fullreview failures remain. Noactualprep/object/disk/native/compile/GT/Stage ornewrequestcard. Alloriginal14 conditions andUNKNOWN_NOT_ZERO preserved.


#### Third resumed goal-turn blocked audit (2026-10-13)

The full admission objective is unchanged and NOT achieved. Fresh resumed-turn1 produced reviewed nativeC03source and stronger history/WSL evidence; turn2 produced formatter/typed-exit evidence and commits411e890/bd9ae05; these were progress, not full closure. In this third resumed turn root revalidated authoritative HEADbd9ae051131b41e15f82c63737dbaf77f8b1812c/feature, complete171 index rows, original dirty/untracked and all5 owned source/document SHA values against the last verified receipt: unchanged. The same original-history/native-epoch/full-fee/originalremaining1800/6000 evidence gate persisted across all3. No reply authorizing history-accounting proposal design/review has arrived; an automatic Goal continuation is not that reply or a budget/clock waiver. No actual preparation was started and no live owned native process/session is confirmed to poll; the completed SOURCE research/review agents do not constitute a verified runtime wait.

Independent /root/third_blocked_gate_audit evaluated supplied verified facts only, without new file/API/runtime actions, and returned BLOCKED_AUDIT_PASSED: same condition/three-turn threshold/genuine impasse hold. This is a conversation/evidence gate assessment, not a source/runtime/fullimplementation review. Original plan2245 retains dependentC04–C12 STOP evenSOURCE; plan2625 requires complete original past charges/native-clock continuity/positive originalbalances BEFORE actualpreparation. Reviewed known independent rawJob/observation/parser source has reached its bounded component checkpoints; more unwired helpers/refusalfields or genericSDKresearch cannot substitute for the necessary legally admitted nativevalidation. WholeC01-C03 incomplete and allthreeC00UNPROVEN remain; no unimplemented producer is claimed ready.

Root will mark the Goal blocked after this administrative exact-path original3 commit/push/remote-preservation audit, and report the actual tool return. It will not mark complete or pause. The needed external change is authoritative original complete historical evidence, or the owner's explicit scope decision permitting a concrete history-accounting handling proposal to be designed and independently reviewed. Proposal permission alone would not amend any existing contract/budget, authorize newactualrun/diskchanges/GT/Stage, or makeFROZEN_ADMISSION valid. Missing evidence remains UNKNOWN_NOT_ZERO, not zero, exhaustion, ledger-global-absence or local physical impossibility. Original14/fullFAIL/PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/zeroRoute2science/Route3fourFAIL/F1open remain. This receipt adds no new application/handoff or production code; all unrelated/staged identities are protected.


<a id="c00-history-gap-concrete-proposal-20261013"></a>
### Concrete historical-accounting gap handling proposal (2026-10-13, PENDING)

**Authority correction and actual scope.** Designing and independently reviewing this proposal is already authorized by the admission objective and the requirement to finish reviewable work before requesting approval. The unanswered earlier question asking permission merely to draft it is not a valid external blocker. Independent conversation-only /root/history_proposal_authorization_audit confirmed that distinction. The preceding third-turn receipt correctly identifies the actual historical-evidence gate, but its implication that no further authorized proposal work exists is superseded here. Goal has not been marked blocked at this writing. This append changes no operative contract or approval field; no actual preparation, compilation, provider call, directory/disk change, GT or Stage is started. Root is the only documentary author. Original3-only documentary drafting/review has a separate source-session checkpoint, not a new preparation epoch or credit against actual-runtime budgets.

**Evidence and exact problem.** The bounded recovery found 3,212 selected execution-source records with paired client envelopes and a local native-QPC durability fragment; it did not recover complete creator/cohort/native-epoch continuity, all infrastructure charges, historical allocation/deletion/tail costs, or authoritative remaining1800/6000 balances. Client duration sums are not consumed native budget or proof of exhaustion. Complete original history is not proved globally absent; host feasibility is UNKNOWN. Plan2621/2625 requires these BEFORE actual preparation, and original14 gate9 remains decisive UNKNOWN_NOT_ZERO. A future logger cannot backfill the missing past.

**H0: original contract unchanged (current operative path).** Recover an authoritative original receipt chain, not a caller-authored statement or a reconstruction that assigns zero to missing intervals. The reviewable acceptance object must bind:
- The original study/lineage, original owner and original epoch/deadline identities, boot/QPC provenance and original continuity rules. Archive filenames, fresh ticks and reconstructed HANDLE numbers are not native continuity or live held-handle evidence.
- Every historical preparation/control interval and original group/cohort membership, including monitor/loader/compiler/helper, WSL VM/kernel/service/infrastructure, detached work and bounded tails. Reconcile overlaps under the original accounting rules; do not infer native charges from client-call pairing or add overlapping waits as separate wall usage.
- Original RAM/VRAM/CPU/thread observations and storage baselines, allocations, metadata, growth/deletion history, all original owners/writers and original residual charges. Missing actors/intervals/metadata stay UNKNOWN_NOT_ZERO; deletion is not an invented historical refund.
- Authoritative finite upper bounds on the charges and native deadline continuity for each original budget, with a positive balance sufficient for the proposed bounded action and its60s cleanup under the original1800/6000 contracts. A signed hash or owner attestation proves provenance only, not missing quantitative facts.

A single reconciled certificate must reference the raw evidence and executable verification rules, include discrepancies/unknowns, be independently SPEC/QUALITY reviewed, and fail closed on any missing decisive item. Its receipt/verified balances become BEFORE evidence only after successful validation; no empty ledger, new ID, new t0, estimated zero or retroactive success declaration is accepted. No such certificate is currently available. Further generic metadata scanning without a new authoritative source has no justified recovery target.

**H1: concrete owner exception proposal, NOT in force.** If H0 cannot be supplied, the only proposed alternative is an explicit, recorded change to the preparation/control historical-accounting contract. This is a requested exception to the user's instruction "不清零历史、不重置原时钟" and original historical cumulative ceilings; it is not compliance with the unchanged original contract. The original study ID, original records/epochs/unknown charges and old failures remain permanently visible. No owner signature can transform those unknowns into measured history. The owner would acknowledge that original preparation/control historical budget compliance remains unproved and accept that audit exception.

The exact proposed authority is ONE prospective supplemental no-GT preparation/control attempt, within the same study and with NO retry/renewal credit. Before any action it must have an independently reviewed trusted supervisor, immutable preload/dependency boundary, actual identity/resource owners and complete prospective accounting. The supervisor creates and seals its actual original native attempt epoch before the first relevant load/spawn. This new attempt clock is permitted only by the explicitly approved exception, never substituted for or represented as the recovered old clock. Its global preparation/control time domains run continuously through all designated operations/waits/drainage/receipts/tails; suspended periods are handled by the original absolute native-deadline rules. No process restart, subgroup, helper or resumed conversation restarts either domain.

| Proposed supplemental domain | Exact maximum for this ONE attempt, cleanup included |
| --- | --- |
| Preparation/build/ABI/load/no-GT validation |1800s total, RAM4GiB, CPU200%, application MONITORED4 with the approved fixed-thread design; the final60s are inside1800. |
| External supervisor/control/monitor/coordinator |6000s total from its own original attempt birth, RAM512MiB, CPU100%, application MONITORED4; final60s inside6000, including acceptance and the bounded billed coordinator tail. |
| Whole task and infrastructure |RAM16GiB/VRAM8GiB; all VM/kernel/service/loader/monitor/provider and other infrastructure charged. They are outside the application-TID number only where the already approved design says so, never outside accounting. |
| Physical storage and spill |E30GiB=carrier24 inclguest20+external6, guest baseline<=8GiB, control64MiB/16MiB internal; nonE512MiB MONITORED, STOP_NEW384MiB, nominal128MiB tail and accepted unknown in-flight overshoot unchanged for prospective operations. |

The supplemental bounds limit FUTURE admitted exposure only; the total historical-plus-future ceiling and historical peak/growth compliance remain unproved and are the explicit exception. This applies to irrecoverable historical preparation/control accounting ONLY, including its old resource/storage/spill charges, not a waiver of current live allocations or ongoing costs. Any remaining original task actor, writer, VM/service, allocation or asynchronous provider obligation must be identified, owned, conservatively charged inside the prospective scope and contained before its dependent action; an unknown residual does not become "historical" merely because a new attempt starts. Existing live storage is not erased from physical occupancy or granted a refund. Where no valid BEFORE owner/containment/identity proof can be established, STOP remains. No pre-existing object is killed, detached, deleted, partitioned or formatted by this permission.

STOP_NEW prevents new work at a missing/stale/failed observation, budget/identity violation or the original remaining-tail threshold. Absolute native deadlines govern acceptance; OS termination requests do not guarantee physical completion by deadline. Failure preserves primary and cleanup errors and all identities/charges. The attempt ends on its first failure/expiry, original join/drainage/durable-E acceptance or known legal stop; no silent retry/credit renewal. A stuck owned actor/provider remains unresolved and billed, with no normal success and no invented finite residual charge. A separate object-specific owner decision is required where lawful cleanup cannot finish. The exception does not authorize unowned infrastructure to run after accounting stops.

**Retained BEFORE gates and limits of this proposal.** H1 approval removes ONLY the original-history proof prerequisite for this specifically approved supplemental envelope, by an explicit exception. It does not magically provide the missing trusted preparation entry/preload closure/actual resource enforcement, original held identities/current residual containment, the selected exact C00 VM/service/E-extent/final-coordinator producers, or their actual mechanism proofs. All must be implemented, concretely reviewed and satisfy their own BEFORE gates before the dependent operation. Known preparatory source remains within the original eligibility DAG; C04-C12 remain STOP even SOURCE until the C00 continuation predicate and independent dual review genuinely pass. Startup facts are obtained only in an authorized SAME INVOCATION with implemented, reviewed, non-bypassable failure refusal. If those owners cannot be made valid under the unchanged resources, report the actual gap and STOP; this exception promises no feasibility.

No task preparation directory is created now. The previously named namespace E:\Route2AdmissionPrep_20261013 may be used only after its actual storage/current-writer/metadata scope is reviewed and admitted; a directory is not a physical cap. Partition/format/shrink/existing-disk changes/deletion of existing objects still require exact actual disk/volume identity, geometry, commands, effects and separate approval. WSL2/Ubuntu22.04/glibc2.35, memory8GB/swap0/processors2/gui=false actually applied, Linux native hard limits, original first guestM0/C/AS and both SAME-INVOCATION free>=8GiB checks remain unchanged. No third8GiB is introduced.

Science is excluded: no GT payload/reference reproduction/scientific evaluation or StageA/B; no scientific fit/predict/decode charges are created. Original StageA1200/study3600/cumulativefit900 incl60 and their original SAME-INVOCATION clocks are untouched. Saved scores/model26D/threshold/decoder/matcher, strict-overlap vs300s, the complete nested5 outer x4 inner x4 sub-inner role graph,105+105,25fit/25predict/65decode/20GT plus21stGT-free merge/pooledGTreads0, symmetric tolerances and D_A2GiB strictV2 remain unchanged. An approved exception must be pinned as a contract amendment in source/runtime/protocol/budget freeze and the NEW full independent implementation review; no gate can be declared compliant with the unchanged old historical requirement. Original unique A+B card/prompt stay unchanged; only a later complete, actually review-ready concrete A+B application may request final scientific authority.

**Concrete pending owner decision.** Approve or decline H1 in exactly the above scope: accept the explicitly unproved historical preparation/control accounting, permit this ONE supplemental prospective1800/6000 envelope/new sealed attempt epoch under the same study, and retain all listed current-resource/identity/physical/scientific gates. Nothing in a generic "continue" or this proposal's scoped SOURCE reviews grants that exception. If declined, H0 is the only path under the current contract and actual preparation remains blocked until its authoritative certificate exists. Approval alone is not APPROVAL_READY, not an A+B authorization, and not disk approval.

**Current condition conclusion.** No operative state changes: C00=AUDITED_UNPROVEN/allthreeUNPROVEN; wholeC01/C02/C03 incomplete, independentC03parser SOURCE_REVIEWED/IMPLEMENTED_BUT_UNCOMPILED; C04-C12STOPevenSOURCE. Original14 rows remain as previously fully updated, with gate9 now additionally linked to this PENDING proposal (not PASS); PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED. Route2 legal Stage/results zero; Route3v1-003 COMPLETE/fourFAIL unchanged; F1>=0.66 open. This proposal requires fresh independent SPEC then DIFFERENT fresh QUALITY after author freeze, repairs/re-review of all scopedP1/P2, exact-path original3 commits and nonforce feature push with remote/main and original171-index/11-staged/403-file preservation verification. Those are proposal reviews, not a full admission review.


#### Pending-proposal lifecycle clarification after scoped QUALITY P2

This is a normative correction to the PENDING proposal ONLY, not to the operative contract. The initial SPEC found no scopedP1/P2; the DIFFERENT fresh QUALITY found one lifecycleP2 and did not pass the initial proposal. Supersede the earlier sentence "The attempt ends on its first failure/expiry, original join/drainage/durable-E acceptance or known legal stop" with the following rule:

First failure, expiry or legal STOP immediately ends workload authorization and latches STOP_NEW. It does not end, reset, erase or renew the original attempt native time domains, accounting liability or ledger. All attributable actor/VM/service/provider/observer/coordinator costs remain in that SAME supplemental attempt and the original study lineage through actual termination, drainage, final charges and receipt persistence. Failure, refusal, budget expiry or the end of a60s nominal cleanup tail cannot be used as an accounting cutoff. Crossing1800/6000 is an envelope FAIL, not supplemental permission, a new clock or a finite historical-charge certificate.

Finalization of a FAILED accounting record requires authoritative proof that all applicable owned obligations terminated/drained, complete final charges, and the durable original failure receipt. Normal COMPLETE additionally requires every original normal-acceptance condition and timely durable QPC; successful accounting of failure never implies successful normal acceptance. A surviving or unobserved obligation remains an open residual with UNKNOWN_NOT_ZERO liability. Ending observation does not prove termination or assign zero/finite cost afterward. Continuing to owe/account for those costs grants no indefinite runtime or new monitor budget. Before dependent work, the same independently reviewed bounded-stop/join/residual-containment owners must still exist; if they cannot exist under the proposed bounds, the action stays STOP. No H1 approval, refusal or new attempt authorizes cancellation/deletion/killing of a pre-existing unowned object or hides its still-live obligations.

Root now freezes the corrected full proposal for fresh independent SPEC then DIFFERENT fresh QUALITY. The initial QUALITY P2 remains historical and is closed only by those actual re-review results. All original14/current operating states and original card/prompt remain unchanged.


#### Concrete history-gap proposal: independent re-review and closing condition receipt

Scoped review ID route2-c00-history-gap-proposal-source-review-2026-10-13-001 covers ONLY the PENDING proposal and its lifecycle correction, not full implementation/runtime/admission. Initial SPEC /root/history_gap_concrete_spec START18:23:38/readSTOP18:24:11/finalSTOP18:24:46 UTC found no scopedP1/P2. DIFFERENT initial QUALITY /root/history_gap_concrete_quality START18:26:20/readSTOP18:26:52/finalSTOP18:29:03 found one lifecycleP2; that initial QUALITY did not PASS. Root alone appended the normative correction and froze18:30:22. Fresh independent SPEC /root/history_gap_corrected_spec START18:31:14/readSTOP18:31:45/finalSTOP18:33:04, then DIFFERENT fresh QUALITY /root/history_gap_corrected_quality START18:34:10/readSTOP18:34:37/finalSTOP18:35:57 both verified corrected bytes and returned NO_REMAINING_SCOPED_P1_P2 / HISTORY_GAP_PENDING_PROPOSAL_ONLY. All reviewer durations stayed within their original360s windows; none reset its clock. Initial P2 is retained in history and closed by these actual re-reviews.

Corrected reviewoffset759205/specoffset401455/planoffset517153, each14781 bytes SHA256 abbcb551cd7bc35da10cb49334494e80636a410431e4eab132f82ef7ad137b87. Source design/review clocks are separate from actual preparation budgets; they establish no native clock/balance or runtime fee certificate. Source-only preservation audit verified403-file identity set,400 other bytes, original171 index rows and unrelated dirty/untracked before this administrative receipt. The previous administrative exact3 commitfabc72da90fb401f4dc406f0912f8b2322f0cd3d was nonforce pushed and remotely verified18:16:52 UTC; main remaineddd05aa128f8d62a85c20a83f8af72fe13fcfa27b. Root appends this factual receipt, then exact3 commit/nonforce push and verifies the resulting bytes, preserved11 staged identities and remote feature/main. The final new commit is reported after verification, not preclaimed here.

| Original14 condition | SOURCE / actual evidence at closing | Remaining legal gate and conclusion |
| --- | --- | --- |
| 1 complete A+B production | Partial source; complete installed/connected production runner and admission seal absent. | BEFORE full production/runtime evidence/freeze/full independent review/concrete A+B approval. BLOCKED. |
| 2 science and equivalence | Fixed scientific contract retained; no new scientific run/equivalence evidence. | BEFORE complete nested frozen protocol; SAME lawful105+105/equivalence. UNPROVEN. |
| 3 immutable role inputs | Old broker/O_PATH fixes retained; no real complete creator/publisher/immutable backing/revocation chain. | BEFORE complete production chain; SAME original identity/sameFD/history. UNPROVEN; dependentSOURCE STOP. |
| 4 counts and finite images | Original25fit/25predict/65decode/20GT+21stGT-free and D_A2GiB strictV2 retained. | BEFORE enforcing ledger/capacity lifecycle; SAME legal counts/image2->4/accounting. UNPROVEN. |
| 5 GT and reports | Old directory-v2/final matched-GT/finalize source fixes retained; no GT payload access. | BEFORE true projection/grant/revoke/provenance; SAME lawfully authorized GT consumption/report. UNPROVEN. |
| 6 isolation and creator identities | Raw Job/process source and pinned WSL creator source only; no complete installed original cohort/isolation proof. | BEFORE worker/write/namespace/cleanup owners; SAME original held identities and complete history. UNPROVEN. |
| 7 E physical capacity | Selected finite physical extent and public API evidence only; named directory not created/not a cap. | BEFORE exact mechanism/current identity/any required disk approval; SAME all metadata/writers/reserves/double8. UNPROVEN. |
| 8 first M0/t0 and resource owners | C03 MemAvailable parser SOURCE_REVIEWED/UNCOMPILED; no original native capture/transport/current-policy evidence. | BEFORE real producers/hard owners; SAME originalM0/QPC/Linux limits/current WSL/RAM/VRAM. UNPROVEN. |
| 9 historical and full fees | Bounded archive/QPC evidence remains partial; H0 certificate absent. H1 scoped proposal dual-reviewed, PENDING owner exception. | BEFORE original proof under current contract, or explicitly approved H1 plus every retained BEFORE gate. UNKNOWN_NOT_ZERO; no old-cap PASS. |
| 10 non-E spill | Original512/384/nominal128 MONITORED rule retained; no complete actual writer/allocation/history observer proof. | BEFORE fixed complete observer/STOP owner; SAME all growth/tail/unknown overshoot charges. UNPROVEN. |
| 11 install and preload closure | Old pinned Linux dependency evidence partial; C02/nativeC03 remain uncompiled; no new build/ABI/load/install. | BEFORE immutable loaded closure/launcher owners; SAME legally admitted build/load/installation evidence. UNPROVEN. |
| 12 termination and durable acceptance | Pinned formatter/typed-exit API evidence and corrected accounting semantics only; no actual whole join/drain/durable QPC proof. | BEFORE original held deadline/cleanup owners; SAME failed and normal whole termination/residual billing/durable acceptance. UNPROVEN. |
| 13 full freeze and independent review | New ID is PENDING-PROPOSAL SOURCE review only; old full FAIL-001 retained. | BEFORE actual complete source/runtime/input/role/protocol/budget freeze and NEW full independent review. UNPROVEN; FROZEN_ADMISSION=None. |
| 14 scientific quality | Route3v1-003 legalCOMPLETE/fourFAIL retained; Route2 lawfulStage/results zero. | SAME later owner-authorized scientific run/four gates/actual report. F1>=0.66 OPEN. |

Original operative contract remains unchanged; C00 AUDITED_UNPROVEN/allthreeUNPROVEN, wholeC01-C03 incomplete, C04-C12STOP evenSOURCE, PREPARED_UNREVIEWED/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED remain. No new card/handoff or altered original application prompt/card. After Git verification root presents ONE concrete H1 decision, rather than asking permission to draft; generic continuation is not this contract exception. The repeated original historical evidence gate still persists across the third resumed turn. With all authorized concrete proposal work now finished and no authoritative H0 evidence or H1 scope decision, root will mark Goal blocked and report the actual returned status, not complete/pause. That stops dependent work until an explicit external change; it does not assert budget exhaustion, global ledger absence or local infeasibility.


<a id="h1-owner-approval-bound-20261014"></a>
### H1 owner approval bound to the reviewed object (2026-10-14)

The owner explicitly answered "批准" twice after the concrete H1 request and resumed the Goal active. This is ONE approval of the same H1 object, not two supplemental attempts or renewal credit. Authority is bound to commit66dfa1b938b56a60db700078a7d335ed1b1da6a0, scoped review route2-c00-history-gap-proposal-source-review-2026-10-13-001, corrected reviewoffset759205/specoffset401455/planoffset517153 each14781bytes SHA256 abbcb551cd7bc35da10cb49334494e80636a410431e4eab132f82ef7ad137b87, including the appended lifecycle correction. This later decision supersedes ONLY prior H1 PENDING/not-in-force and pending-history-decision statements. Approval of designing the proposal was already inherent; no new approval of drafting is requested.

H1 is now APPROVED_UNSTARTED: original study/old epochs/records/unknown historical preparation/control charges remain visible; original historical cumulative time/resource/storage/spill compliance remains unproved. The owner authorizes the exactly reviewed ONE prospective no-GT preparation1800/external6000 envelope/new actual native sealed attempt epoch under the same study; their original4GiB/512MiB/200%/100%/MONITORED4/fixed-thread/60s-inside, whole16GiB/VRAM8GiB, current allocations/all infrastructure costs and every retained BEFORE/physical/identity/preload/deadline/STOP/join/durable receipt condition still apply. Clock/ledger liability does not end at FAIL/expiry/tail end; no retries/renewals. No native attempt epoch was generated, no workload/build/ABI/load/probe or preparation object/directory was started by this receipt, and no positive remaining balance is invented from absence of a new run.

The historical H0 certificate is no longer the decisive BEFORE prerequisite for this specifically approved supplemental attempt; it remains unavailable for proving unchanged old-contract compliance. The next concrete prerequisite is an actual trusted external first-load owner/immutable preload closure and the real C00 full resources, physical scope and exit/drain producers. H1 itself supplies none of those facts. C00=AUDITED_UNPROVEN/allthreeUNPROVEN, wholeC01-C03 incomplete, C04-C12STOP evenSOURCE, PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/oldfullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED remain. Original14 gate9 gains this explicit exception approval only; its prospective full billing proof is incomplete, and the other13 rows retain their preceding complete status. Original unique A+B prompt/card stay unchanged. No disk mutation/deletion of existing object, GT payload/reference reproduction/scientific evaluation or StageA/B is authorized; Route2 lawfulsciencezero/Route3COMPLETE-fourFAIL/F1open remain.

Current resumption FIRSTCLOCK05:49:02 UTC and actual task/interface/file reads are SOURCE-session evidence only, not the new native attempt t0 or runtime-budget certificates. The authoritative initial HEAD/branch/doc bytes matched the approved object; complete171 index rows, original11 staged paths and403-file identity set were captured for preservation. The following native owner/closure mechanism analysis is a new bounded SOURCE reassessment driven by this actual owner decision; no earlier physical/runtime hypothesis or source counter is erased.


<a id="c00-post-h1-support-gap-20261014"></a>
### Post-H1 C00 mechanism decision: source support is distinct from deployment (2026-10-14)

H1 APPROVED_UNSTARTED is inherited from ad4cb334097b5004b554fa62da96be778bb8429b and the preceding owner-approval receipt. The original-history H0 certificate is no longer the decisive prerequisite for that one supplemental attempt. This decision does not reopen H1, reset its clocks or grant a second attempt. No actual native attempt epoch, compilation, ABI/load/call, WSL invocation, hardware/storage provider probe, preparation object/directory or Stage was started in this reassessment. That action inventory is not a zero-cost certificate: historical and SOURCE-session costs remain UNKNOWN_NOT_ZERO where unmeasured.

**Authoritative SOURCE predicate.** Plan2238–2248, specifically2245–2246, separates exact native mechanism support/selection from installed SAME-INVOCATION facts. Actual deployment UNKNOWN alone does not forbid the complete SOURCE DAG. To continue that DAG, however, every required native primitive must actually be supported and selected with signature, owner, callpoint, effective scope and failure/stop semantics, followed by independent C00 SPEC and DIFFERENT fresh QUALITY. A conditional producer declaration is insufficient. The present gap includes missing SOURCE mechanisms, not merely deployment evidence. Existing independent C02 raw Job/identity/observation and C03 bounded prebirth/parser/transport-rejection source remain eligible within their original narrow scope; this decision does not expand it. Full seed, cohort registry, preload/bootstrap, scope gate, cleanup or assembly cannot be renamed C00 to bypass dependent C04–C12 STOP.

**Mechanism findings and ownership.** The table records public capability separately from local facts. These are mechanisms inspected, not newly selected complete producers or local success receipts.

| Mechanism / exact contract | Required owner and production callpoint | Supported scope and remaining decisive gap / failure semantics |
| --- | --- | --- |
| BOOL SetProcessWorkingSetSizeEx(HANDLE,SIZE_T,SIZE_T,DWORD); BOOL GetProcessWorkingSetSizeEx(HANDLE,PSIZE_T,PSIZE_T,PDWORD) | Original creator-held process owner; policy before resume/load and raw verification under the original external epoch. Set requires PROCESS_SET_QUOTA; query needs its documented process query access. | QUOTA_LIMITS_HARDWS_MAX_ENABLE=0x4 bounds the process working set, not complete RAM. AWE and large-page allocations are outside the working set; removed pages can remain resident. No Set/Get was called here. Missing/failed policy or scope proof must STOP_NEW, not fall back to commit/process-count evidence. This API pair is NOT selected as the complete RAM producer. |
| HRESULT WINAPI HcsGetComputeSystemProperties(HCS_SYSTEM,HCS_OPERATION,PCWSTR); HcsSetComputeSystemCallback(HCS_SYSTEM,HCS_EVENT_OPTIONS,const void*,HCS_EVENT_CALLBACK) | Original WSL VM creator bridge owns the original HCS_SYSTEM/operation/context; register before dependent VM work and retain callback/context lifetime. | Property start S_OK is asynchronous initiation; VM exit callback covers VM exit only. Neither supplies complete service/kernel/provider membership, fees or all original joins. Current WSL creator bridge build/install/signing and callback drainage remain unproved. Failed/stale/incomplete observation stops new work and retains pending charges. |
| HcsWaitForOperationResult(HCS_OPERATION,DWORD,PWSTR*), HcsCancelOperation(HCS_OPERATION), HcsCloseOperation(HCS_OPERATION), HcsCloseComputeSystem(HCS_SYSTEM) | Original operation/compute owner under checked remaining absolute QPC deadline; live external coordinator retains all applicable obligations. | Finite wait bounds the caller only. Cancel is documented E_NOTIMPL for this selected API. Closing tracking/compute handles is not cancellation, VM/service termination or callback drain. Result strings require LocalFree. Timeout/close cannot certify JOINED_EXITED; unresolved work remains billed and normal acceptance fails. |
| Selected finite physical carrier/external extents and surviving bounded billed final coordinator | Native physical creator before format/import/allocation; original external final coordinator after experiment/VM/service joins, durable E receipt and subsequent QPC. | Exact current backing GUID/disk/offset/length/geometry, bounded formatter/all-writer metadata scope, original service/provider join and bounded-tail producers are still absent. No concrete disk identity or mutation command is approved by the directory permission. A directory or fixed-size VHD does not alone establish the physical24/20/6 bounds. No local infeasibility is inferred from UNKNOWN. |

Primary evidence: [SetProcessWorkingSetSizeEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setprocessworkingsetsizeex), [GetProcessWorkingSetSizeEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-getprocessworkingsetsizeex), [working set coverage](https://learn.microsoft.com/en-us/windows/win32/memory/working-set), and the pinned HCS official ledger at plan2608–2617. The Get API page lists a BOOL signature but an inconsistent “None” Return value entry; no void ABI or invented success interpretation is adopted. Root first resolved Microsoft Win32 in Context7, queried the single working-set scope concept, then checked these official pages. Those public facts establish no local API invocation, current object, permission or runtime proof.

**First build and load boundary.** Repository inspection found no installed trusted native outer entry that can lawfully establish the first compiler/loader boundary. Existing windows_preparation_job._prepare_fixed_worker refuses absent immutable worker/pre-import authority; Python/ctypes QPC is acquired after those loaders. windows_control_identity consumes a manifest but does not create its trusted native origin. scripts/route2_preimport_launcher.py refuses absent pre-Python origin; admission_bootstrap consumes downstream tokens. The native v2 seed/start entries are declarations without executable producer bodies. This is a repository finding, not an exhaustive claim that no suitable platform entry exists on this machine.

A real entry must own its original epoch before relevant loads/births, immutable executable/transitive closure, original creator HANDLE/cohort, born-in-Job preparation/control boundaries, fixed MONITORED4 application observers, complete RAM/VRAM and infrastructure charging, independent absolute deadlines, STOP_NEW, original join/drain/residual containment and durable E receipts. CreateJobObject/SetInformationJobObject/QueryInformationJobObject followed by PROC_THREAD_ATTRIBUTE_JOB_LIST and CreateProcessW with retained PROCESS_INFORMATION can form an application birth chain; those APIs do not themselves create the missing complete RAM, service or physical scope. An executable built by an unsupervised compiler cannot retroactively supervise its own first build. A current intrinsic process handle or post-load clock cannot manufacture prebirth/preload history. Source-only hooks and historical RunAs success are not current deployed ownership evidence.

**Bounded reassessment and independent audit inventory.** Root FIRSTCLOCK05:49:02 UTC; the900s SOURCE checkpoint at06:04:02 elapsed without closure. That overrun is retained, not replaced by a new clock. The root decision freeze is recorded below from the actual clock. These SOURCE clocks are separate from the unstarted H1 native1800/6000 domains and certify neither their remaining balance nor resource compliance.
- /root/h1_bootstrap_chain_audit START05:51:44/readSTOP05:57:09/finalSTOP05:57:54,370s within480s: source/refusal/first-load chain.
- /root/h1_vm_resource_mechanism_audit START05:52:42/readSTOP05:57:20/finalSTOP05:58:43,361s within480s: HCS/full RAM/service scope. Its initial Context7 resolve returned mismatched results and no query was used; official primary pages were used. It additionally ran one read-only search for an authorization-card path outside the assigned original3/source scope before correction. That scope exception is retained; this research audit is NOT a scope-clean formal SPEC/QUALITY pass.
- /root/h1_source_continuation_predicate_audit START06:23:39/readSTOP06:27:32/finalSTOP06:28:19,280s within320s: SOURCE support versus actual deployment and narrow C00 eligibility.

The three materially different checks added the first-load gap, actual working-set exclusions/service scope and authoritative SOURCE-predicate correction. Blind repetitions, generic SDK research and more unwired refusal helpers are stopped. Mandatory record SPEC then DIFFERENT fresh QUALITY are distinct acceptance checks, each separately bounded360s, not a reset of these research counters. No SOURCE code was changed. Existing C02-B1 and C03 source bytes/reviews are inherited; compilation and runtime remain unproved.

**Adaptive preflight / root-cause decision.** Goal: complete real A+B admission before requesting final scientific authority. Success metrics: supported/selected exact C00 mechanisms, lawful installed no-GT production validation and full freeze/review/14-condition closure. Constraints: original physical/resource/identity/deadline/science contracts plus approved H1 only. Prior art: official Win32/HCS and pinned WSL/formatter evidence. Baseline: partial source, no current installed first-load owner/full RAM/all-service/physical producer proof. Candidate approaches: existing trusted platform entry or an actually supported native entry with complete scope, lawfully built/deployed under reviewed preparation authority. Critical assumptions: full group RAM/whole-task coverage, complete creator membership and residual join, lawful first build, exact physical metadata/writer bounds. Risks: post-load self-certification, missing service/cache/nonpageable costs, caller timeout mistaken for exit, infinite unbilled tail. Validation experiments: only a targeted reviewed entry/scope proof and then legally admitted no-GT checks; no runtime spike before its BEFORE contract. Kill criteria: unsupported/unselected decisive primitive, absent original ownership/loading boundary or incomplete stop/accounting scope. Recommendation: REDESIGN. Confidence: high in the current support/evidence gap, unknown in eventual local feasibility.

Failure classification is ARCHITECTURE/UNKNOWN, not REQUIREMENT_INFEASIBLE. Ruled out as sufficient: H1 approval alone, hard working-set/commit/process count alone, VM exit or HCS close alone, plain E directory, raw hashes/AST or historical privilege success. Architecture and requirement viability remain unproved. Exactly one next action is redesign architecture at the trusted first-load/full-scope mechanism boundary, retaining the selected MONITORED4/physical extent/live-coordinator decisions and original budgets. The agent owns this engineering work; the owner is not asked to invent APIs or repeat existing permissions. If no complete supported route can be established, dependency work stays STOP and the minimum external change is an actual trusted native platform entry satisfying these retained gates, or a separately concrete reviewed bootstrap contract amendment. No such amendment is proposed or authorized by this record, and no generic approval would satisfy it.

**Full14 closing delta.** This is a mechanism-gap decision record, not full implementation/runtime/admission PASS.

| Original condition | SOURCE / actual evidence now | Remaining legal gate / conclusion |
| --- | --- | --- |
| 1 complete A+B production | Partial source; no connected installed complete runner/seal. | BEFORE full production/runtime freeze/review and concrete A+B approval. BLOCKED. |
| 2 science/equivalence | Fixed nested5x4x4 scientific contract retained; no new validation. | BEFORE complete no-GT synthetic cross-OS equivalence; SAME later lawful105+105. UNPROVEN. |
| 3 immutable role inputs | Existing broker/O_PATH fixes retained; complete publisher/backing/revoke absent. | BEFORE complete reviewed production path; SAME original identities/same FD/history. UNPROVEN. |
| 4 counts/images |25fit/25predict/65decode/20GT+21stGT-free, D_A2GiB strictV2 retained. | BEFORE ledger/physical lifecycle; SAME legal counts and sameimage2->4 billing. UNPROVEN. |
| 5 GT/report | Existing directory-v2/matched-GT/finalize fixes retained; no GT reads. | BEFORE production projection/grant/revoke; SAME authorized GT/report. UNPROVEN. |
| 6 isolation/identities | Raw original Job/process source only; no complete native birth/worker/isolation owners. | BEFORE creators/namespace/write/cleanup; SAME original held identities and complete history. UNPROVEN. |
| 7 E physical capacity | Finite extent design retained; directory uncreated and insufficient as a cap. | BEFORE supported exact scope, actual target/geometry and any separate disk approval; SAME metadata/writers/reserves/double8. UNPROVEN. |
| 8 first t0/M0/resources | C03 parser SOURCE_REVIEWED/UNCOMPILED; working-set-only proof ruled insufficient. | BEFORE full native producers/resource owners; SAME original epoch/M0/QPC/WSL/Linux/RAM/VRAM. UNPROVEN. |
| 9 history/full fees | H1 APPROVED_UNSTARTED; old history permanently UNKNOWN_NOT_ZERO. | BEFORE retained prospective owners; SAME complete H1 accounting. Approved exception only, no old compliance PASS. |
| 10 non-E spill |512/384/nominal128 MONITORED unchanged; complete writer/allocation observer absent. | BEFORE whole fixed observer/STOP owner; SAME full growth/tail/unknown overshoot fees. UNPROVEN. |
| 11 install/preload | Existing pins retained; no legal first-build entry/complete immutable dependency closure. | BEFORE trusted entry/closure; SAME legal build/ABI/load/install. UNPROVEN. |
| 12 termination/acceptance | Public HCS limits and bounded live-coordinator design only. | BEFORE full original owner/deadline/drain/tail path; SAME all joins/final billing/durable E/QPC. UNPROVEN. |
| 13 freeze/full review | This scoped decision still awaits its own dual review; old full FAIL-001 preserved. | BEFORE actual complete source/runtime/input/protocol/budget freeze and NEW full independent review. UNPROVEN. |
| 14 scientific quality | Route2 legal Stage/results zero; Route3v1-003 COMPLETE/fourFAIL retained. | SAME later final-authorized science/four gates/report. F1>=0.66 OPEN. |

C00=AUDITED_UNPROVEN/allthreeUNPROVEN; wholeC01–C03 incomplete, C04–C12 STOP even SOURCE, PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED persist. Original unique A+B card/prompt are untouched. Root freezes this append for independent SPEC then DIFFERENT fresh QUALITY, fixing all scopedP1/P2 before an exact-path original3 commit/nonforce feature push. A scoped record review will not satisfy the missing mechanism continuation predicate or the full formal admission review.

Actual root decision freeze clock: 2026-10-14 08:32:51 UTC. Earlier SOURCE overrun and native-budget unknowns remain as recorded above.


#### Post-H1 C00 decision: actual independent dual review receipt

Scoped review ID route2-c00-post-h1-mechanism-gap-decision-review-2026-10-14-001 covers ONLY the frozen gap/REDESIGN record, not supported C00 continuation or complete implementation/runtime/admission. Fresh SPEC /root/post_h1_c00_gap_spec FIRSTCLOCK08:35:39/readSTOP08:37:46/finalSTOP08:38:26 UTC (167s), followed by DIFFERENT fresh QUALITY /root/post_h1_c00_gap_quality FIRSTCLOCK08:39:59/readSTOP08:42:11/finalSTOP08:42:52 (173s), both actually returned NO_REMAINING_SCOPED_P1_P2 / C00_GAP_DECISION_ONLY inside their original360s bounds. Each independently verified equal original3 slices: offsets spec426049/plan541747/review783799,15183 UTF8 bytes SHA2561b503e20beabcfa4a4e00428510548669ba3bef8a625a356037f6496967e1804. Root-supplied audit clocks/scope exception/SOURCE overrun were assessed as recorded, not independently remeasured. Author was WRITESTOPPED throughout both reviews. No scoped repair was required.

This factual receipt supersedes ONLY the record's pending-review wording and condition13's pending scoped-decision review. The full14 conclusions remain unchanged: H1 APPROVED_UNSTARTED; gate9 approved historical exception but prospective complete fees unproved; all required C00 mechanisms still UNPROVEN; full freeze/review and A+B authorization absent. New scoped ID does not replace the old full FAIL-001. Complete SOURCE DAG remains stopped for missing exact support/selection, not simply because current installation facts are UNKNOWN.

Root's fresh preservation check08:41:19 UTC verified403 original paths,400 other working-file byte identities, all171 pre-stage index rows including original11 staged identities, unrelated statusV2 and all frozen decision bytes unchanged. Root now appends this administrative receipt only to original3, verifies prefixes/diff/exact paths, commits and nonforce-pushes the feature, then verifies remote feature/main. No Git success/hash is preclaimed here. No task directory/object/native epoch/build/ABI/load/WSL/GT/Stage is created by these reviews or this receipt. Goal objective is unachieved; this is the first resumed turn after effective H1, so the old history blocker is not reused as a new three-turn blocked audit. All fee unknowns and SOURCE overrun remain recorded. Receipt author clock: 2026-10-14 08:44:27 UTC.
