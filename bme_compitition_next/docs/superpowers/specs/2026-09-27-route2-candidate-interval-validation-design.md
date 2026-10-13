# 路线二：候选区间最小验证设计

日期：2026-09-27  
状态：`DESIGN_PREPARED / NOT_EXPERIMENT_AUTHORIZED`  
本轮文档复审范围：仅修订本设计、既有审阅决定和待授权Prompt；不修改代码、配置、历史产物或production，不产生新候选，不训练或调用模型。下述实验仍待单独授权。

## 1. 项目预检

- **Goal：**判断固定保存分数下，取消候选生成阶段的 300 s 正时间间隔融合，是否能改善最终进食事件输出。
- **Success metrics：**本地同一 234 canonical eligible GT 分母、strict IoU>0.25、participant-global greedy one-to-one；报告 pooled event F1、五折 F1、long-FP fraction、matched start/end MAE 及匹配 GT 集合变化。官方尚未公布 exact matcher/scope/eligibility，结果仍是本地开发协议。
- **Constraints：**41人均已参与开发；A1 CLOSED、A2固定26D CLOSED_STAGE_MINIMUM_FAIL、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。禁止重开任何已终态的A1/A2/Route3命名空间，不能沿用其额度；未来路线二需独立study。不能读 raw sensor、metadata CSV、official test、external data；不能把 GT 竞争关系用作推理输入。
- **Prior art：**A2-004最终260个预测均各自来自一个role-qualified candidate且区间一致；79长FP在最终600s融合之前已经是长候选。21个FN没有IoU>0.25的现有候选。候选阶段300s融合前的运行轨迹未保存。既往bounded proposal规则已关闭，本方案不重开其cap/peak/outer逐例搜索。
- **Baseline：**A2-004保存结果 TP=154、FP=106、FN=80、F1=0.623482；A1保存 F1=0.585086。A2不是新运行预算或此方案的独立确认集。
- **Candidate approaches：**R2-A降低final minimum只能解除3个短GT的几何限制，现有best candidate IoU仍未过0.25；R2-C固定分数集合选择有11个事后竞争案例，但没有合法的GT-free运行时组，且9对跨record/session；本设计选R2-B范围内的单一候选融合差异，不训练ranking模型。
- **Critical assumptions：**role-specific `ids/raw/relative`分数可在完整核对后合法复用；候选生成可逐role从分数窗重建；新候选能得到同schema的16D来源特征和固定10D上下文特征；单record/session输入在官方接口内有边界。16D计算式已从准许静态代码恢复，精确派生文件、字段、role映射及10D实现身份尚未获准或冻结；官方输入契约仍未知。
- **Risks：**取消间隙融合可能显著增加候选数；重算candidate labels/26D向量不能复用旧候选值；全41人已多轮开发，外层成绩只作开发证据；58个零注释交叠长FP行为仍UNKNOWN；此IMU分数实验不证明非惯用手PPG要求已满足。
- **Validation experiments：**仅提出一个待授权的A2式五折验证：同一role-specific score streams，以候选融合规则为唯一科学变量，完整重建候选并使用相同26D verifier协议评估一次。当前不执行。
- **Kill criteria：**候选身份/分数/隔离无效、训练/外层标签混用、缺少合法16D特征来源、G3不满足或资源监控失败，均在性能结论前fail-closed；单一设置完整失败后关闭该变体，不扫间隙、不调阈值、不修outer案例。
- **Recommendation：**`SPIKE FIRST`，但只有精确特征来源、Stage A参考门、唯一资源上限及新授权齐备后才可进入运行。连接前轨迹未保存，未来重建属于获批Stage A，不是本轮预检。
- **Confidence：**中低。已保存证据支持“候选几何值得验证”，没有证明300s融合导致错误，且关键训练特征来源和实际规模未知。

能力路由：`machine-learning, data-contracts, evaluation`；加载Machine Learning profile。未来获批后的验证次序为：全部输入/语义与Stage A+B数值预算、启动测量方式事先冻结并获批 → 身份/角色与分数来源 → 全105 role的300s参考复现 → 唯一gap=0候选重建与无标签差异门 → 把Stage A实际数量代入预冻结的Stage B资源投影 → nested verifier与事件评价。未知官方接口和资源作为critical unknowns。

## 2. 选择的唯一机制

把历史候选融合的最大可跨时间间隔从300,000ms改为**只合并正时长时间交叠的相邻正分窗口**。这项变化只改变候选区间形成。它不新增分数阈值、不搜索cap、不生成边界备选集合、不使用GT做推理分组，也不改变final decoder 600s融合、180s最短输出、matcher、fold或模型家族。

对每个role内的每个 `(participant_id, record_id, session_id, observed-support component)` 独立处理：

1. 仅采用分数ID与获准窗口身份、时间、质量字段完整对齐且质量有效的窗口。来源核对需按冻结A1 score契约确认同role已保存`relative`与`raw - threshold_reference`一致；参考和处理都使用同一经核验的已保存`relative`，不一方重算、一方直接读取。positive 定义固定为 `relative >= 0`。
2. 按冻结A1传入窗口序列的 `(start_ms, end_ms, index)` 排序，区间为半开 `[start_ms,end_ms)`；`stable_window_id`只用于身份核验和support比较，不能替换旧构建器的排序平局键。
3. 下一个positive窗口仅在与当前支持区间并集正时长相交时延续当前候选，即 `next.start_ms < current_end_ms`。仅端点相接或存在任何正间隙时开始新候选；组件/身份改变必然切开。
4. 每个最大连通run输出一个候选，区间为其支持窗并集，保留完整role-qualified support身份。所有候选保持 `source_segment_id=null`，`boundary_kind=observed_window_support_component_v1`。

**原规则与处理规则的精确区别：**`src/eating_event/a1/events.py:154` 的300s参考条件为 `next.start_ms <= current_end_ms + 300000`。同一函数传入 `fuse_gap_ms=0` 仍会合并端点相接窗口；处理规则要求严格 `< current_end_ms`，未来独立study须显式实现并冻结该比较，不能把调用旧函数的gap参数置零当作处理。参考使用原条件与原窗口筛选/component定义；处理只改连接谓词。

**新候选16D的静态计算定义：**`src/eating_event/a1/events.py:54-91` 对该候选完整support的role-specific `relative` 和逐窗 `coverage`，按顺序计算：`max(relative), mean(relative), std(relative, ddof=0), percentile(relative,25), percentile(relative,75), min(relative), support_count, (end_ms-start_ms)/1000, support_count/duration_seconds, mean(coverage), min(coverage), max(coverage), sin(start_ms日相位), cos(start_ms日相位), sin(end_ms日相位), cos(end_ms日相位)`；日相位为 `2π×((time_ms mod 86400000)/86400000)`，保留该代码的NumPy percentile/default float64语义。`src/eating_event/a2/audit.py:430-457` 指向已登记派生cache的 `starts/ends/coverage/crosses_gap` 四个成员，role score只取登记NPZ的`ids/raw/relative`及score-provenance的`threshold`。这证明公式可恢复，**不授予本轮读取cache或score数组**，也未核实精确cache_path/role绑定或固定10D实现。新候选必须按自己的support和边界重算16D，再按冻结的A2 10D定义构成26D；旧候选 `source_16d`、标签和verifier分数均不得继承。

边界、positive窗集合和候选数都不得按GT调整；同一候选生成规则用于所有角色。候选每行的训练标签与A2 26D输入值必须使用已冻结的角色内规则重新生成，不能复制旧融合候选的16D向量或标签。若精确训练标签规则或新run的16D输入来源不能在授权资料中确认，停止，不推定。

## 3. 推理边界和空值语义

| 字段/对象 | 已保存来源与当前事实 | 设计用法与边界 |
|---|---|---|
| participant / record / session | 登记的outer candidate rows有三种身份；cache-manifest登记participant/session及精确cache_path，record关联来自此前身份审核 | 候选生成组必须同record/session；不得把9个跨record/session竞争对当联合输入许可 |
| 窗口时间区间、稳定身份、质量 | 未来拟议为冻结A1 `window-identity.json` 的 `participant_id,record_id,session_id,row_index` 与登记cache-manifest的 `participant_id,session_id,record_id,cache_path,cache_sha256`，精确derived cache仅 `starts,ends,coverage,crosses_gap`；score `ids`按冻结global window顺序绑定 | 需先列出A1根目录、manifest/identity精确路径和已登记hash，并核对632100窗口、1127记录及ID顺序；不得借manifest路径扩读raw/原metadata。缺字段、重复/越界ID、非有限score或身份冲突为`INVALID`；有效且无positive窗是合法空候选集 |
| `raw/relative`分数 | 仅score-provenance精确注册文件的`ids/raw/relative` | 不重算分数、不调用candidate模型、不改threshold；相对分数沿用各role已保存的reference |
| observed-support component | outer candidate row保存component ID；`source_segment_id=null` | 只能在同component内生成；component不代表物理source segment |
| 26D verifier特征 | 16D公式已从A1静态代码恢复；现有role-digests只绑定旧candidate的source 16D与26D摘要；新run的16D数组尚未产生 | 需批准上一行精确来源成员和score成员，并冻结A2固定10D实现身份/输入契约；不得把旧16D赋给新边界。当前不得加载cache数组或搜索邻接文件 |
| GT与candidate label | 精确文件 `artifacts/g1-participant-exclusion-eligibility-v3-final.json` 的 `event_eligibility` 保存281注释/234 eligible GT | 拟议字段上限为 `participant_id,event_index,start_ms,end_ms,duration_ms,training_eligibility,evaluation_eligibility`，不是当前新增读取授权。训练标签按当前训练candidate role所需participant使用 `training_eligibility`；inner阈值评价只在该inner held-out角色的全部固定阈值预测冻结后，使用其held-out participant的 `evaluation_eligibility`，这些participant必须属于outer训练集；outer评价只在对应outer预测冻结后读取outer held-out participant的 `evaluation_eligibility`。不得假定两个资格标记相同、读其他字段或读取 `event-representability-v3-final.json`；须先冻结合法的分阶段role-scoped读取方式 |
| 未来输入/组范围 | 官方完整输入接口、record/session可用范围、未来上下文和资源限制未知 | 本方案只定义单record/session批次内的区间生成；不宣称实时、不假设无限未来、不跨record/session联合处理 |

缓存或score缺失不能当负分；缺少时间/质量字段不能静默过滤。组件边界不能被候选或输出融合跨越。candidate label规则必须与原A1/A2规则完全相同；若本地冻结语义无法从批准决定中恢复，先补齐决策再运行。

**GT阶段隔离：**Stage A完全不读取GT或任一资格标记。Stage B必须分别冻结训练标签、inner阈值评价和outer终评的participant白名单、资格标记、读取时点与消费者；内层评价必须复用原A1/A2评价集合定义，不能以训练资格代替评价资格。若当前实现无法按角色和阶段隔离读取，或不能恢复原标签/评价语义，先停止补充输入/实现决定，不通过预先物化全部outer GT再过滤来规避权限边界。新旧标签规则不得同时引入Route3 matching-aware目标，否则失去单差异比较。

**静态已证与待核实的标签合同：**`src/eating_event/a1/events.py:166-171` 的候选标签函数为 `int(any(IoU(candidate.interval, truth)>0.25))`，没有一对一指派或matching-aware重标。`src/eating_event/a2/audit.py:269-320` 分开构造 `training_eligibility` 和 `evaluation_eligibility` truth 集；`src/eating_event/a2/execution.py:350-395` 显示每outer有四个inner验证角色、三阈值解码，合并这些冻结预测后在outer训练participant上选择阈值，再预测outer held-out。本轮新增获准静态只读范围已覆盖原A1逐role标签传入链、A2固定10D、`metrics.py`的严格IoU及A2按`(role_id,candidate_id)`预分离标签后join；这是**源码规则静态审阅**，真实历史artifact/label身份、完整26D运行期代码冻结和跨OS数值等价仍须在准入前核实。新study拟按同participant、同训练role的训练资格truth应用原函数规则，不能把静态审阅当作A+B授权。

**拟议分阶段读取合同：**训练标签消费者仅为该verifier的四个OOF训练candidate角色；每个candidate角色只看自身`scored_participants`中、且属于当前outer训练集的`training_eligibility=true`事件，构造标签前还要先按候选`participant_id`过滤truth，避免相同时间戳的跨人误标；outer candidate标签始终为null。对每个outer，先冻结四个inner held-out角色在全部三个阈值下的预测及摘要，再让阈值选择器只读该outer `fit_participants`的`evaluation_eligibility=true`事件；选定阈值后冻结outer预测及来源，再让终评器只读该outer `scored_participants`的`evaluation_eligibility=true`事件。pooled终评在五outer预测全部冻结后只汇总五个outer终评视图。每次读取须记录role、participant白名单、阶段六字段物理视图（共同五字段加唯一资格）、时间点和消费者，不保留跨role可查询的全量GT映射。来源是单个JSON；仅在全量解析后过滤输出不算分阶段读取。需先冻结能执行此时序的精确role-scoped provider/派生视图及其生成权限、访问日志和独立审阅，若做不到则`INPUT_NOT_AUTHORIZED`。旧A2 audit在`1027`提前整份加载eligibility，并于`1293-1308`在运行前使用/物化outer GT；旧A2执行也预载truth map，因此未来新study不能原样调用旧audit/run来证明合规。

**GT字段口径更正：**此前“七字段投影”的提法仅指原eligibility来源可申请的字段上限，不是任一消费者可同时看到两种资格。每个获批物理视图先限定phase、role、participant，再只含共同五字段`participant_id,event_index,start_ms,end_ms,duration_ms`及该阶段唯一的`training_eligibility`或`evaluation_eligibility`，共六字段；训练消费者不得见评价资格，inner/outer评价消费者不得见训练资格。视图须在相应预测冻结后才对评价消费者开放；来源视图的生成另行授权与审阅。

**参考行的字段隔离门：**Stage A要读取旧candidate row的身份、区间和`support_indices`，但不得物化同一记录里可能存在的旧label、`source_16d`或verifier分数。首次重建前须确认保存格式及字段级读取能力：优先使用物理上仅含准许字段的冻结reference视图；若需从混合记录生成该视图，应另列生成者所需的精确读取权限、生成时间、输出路径与hash，并独立审阅。仅在整行解析后丢弃禁读字段不算Stage A字段隔离。缺少可证明的隔离方式时为`INPUT_NOT_AUTHORIZED`，不得以参考复现为由读取混合整行。

## 4. 最小可证伪验证协议

**单一科学差异：**候选融合仅由原300s gap rule改成positive windows之间正时长交叠。所有其余量固定：A1的role-specific窗口分数与participant划分、41人/234 GT、候选特征schema、A2的26D构造定义和HGB设置、内层threshold集合 `{0.10,0.25,0.50}`、final minimum=180s、decoder fusion=600s、strict IoU>0.25和既有five-fold gates。

**非候选协议等价门：**105个参考role的interval/support复现只核候选输入，不能证明新Stage B与A2-004同协议。首次候选重建前，须把原训练标签及资格、16D/固定10D至26D构造、HGB参数、nested role图、阈值选择、decoder和matcher/evaluator逐项列出冻结代码/配置身份，由独立审阅确认除候选融合外的协议等价；缺任一证据就停`INPUT_NOT_AUTHORIZED`，不能将后续F1差异归因于gap规则。无需重跑A2-004。

**对照与处理：**对照为保存的A2-004 300s candidate输入及其一次合法完整结果；处理为用相同105 role score streams重建上述单一新candidate集合，并按相同nested图重拟26D verifier。对照只作同protocol历史参照，不能复制模型分数到新候选。Treatment只有在特征/label输入齐全且身份审计通过后才能比较F1。Stage A先完成105个300s参考role的复现门，全部通过后才对同105个role应用严格重叠处理；不得逐role交错执行处理以绕过全局参考门。

**角色隔离：**每outer fold保持原5/4/4嵌套角色。GT仅用于各训练角色的原定义candidate labels、inner冻结预测后的阈值评价及outer冻结预测后的终评；outer held-out标签不得参与特征构造、训练candidate label、阈值选择、关系分组或预测。outer held-out数据仅按冻结协议构造其推理特征，不进入训练role。全部participant各自只属一个outer role；跨role相同window由role-qualified ID区分。每个fit重验G3：至少20个positive candidates、至少5名positive participants、两类，并另报distinct positive canonical GT，后者按该训练role的`training_eligibility`事件计算。旧A2 fit来源记录会从预载评价truth map计算一个同名GT计数（`a2/execution.py:221-225`）；新study不能将它当训练GT计数或替代G3。

**调用上限（拟议，不是授权）：**本提案申请Stage A+B一并准入；所有输入、标签/评价语义及两阶段数值预算须在首次候选重建前具体化、审阅并单独获批。当前不提出Stage A-only申请。以下为完整通过路径上限，早停记录实际消耗，不执行剩余role来凑数。

| 调用 | 数量 | 说明 |
|---|---:|---|
| candidate scorer fit / predict | 0 / 0 | 只复用105个已登记role的保存分数；身份核验失败就停止，不重跑模型 |
| candidate interval reconstruction | 至多105参考role + 105处理role，210次规则应用 | 先完成全部105个300s参考复现，再处理同105个role；参考早停仅记实际参考应用数，处理应用数为0，不执行剩余role凑数。只有处理候选进入后续verifier；重建本身是待授权实验步骤 |
| verifier fit attempts | 25 | 20个inner + 5个outer；failed/interrupted attempt也计数，独立新study账本 |
| verifier predict batches | 25 | 每个拟合模型对其单个heldout inner/outer role调用一次 |
| decoder calls | 65 | 20 inner batches各按3个冻结阈值解码（60），5 outer batches各按已选阈值一次（5） |
| evaluator/reduction 额度 | 合计 21 项 | 20 次读取受限 GT view 的 evaluate_participants 调用（15 次 inner threshold + 5 次 outer held-out）及 1 次无 GT 的 pooled reduction。pooled 只归并五个互斥 outer fold 的 ParticipantMetrics，不重开 GT、不执行第 21 次直接 evaluator。完成收据分列 evaluator_calls=20、pooled_aggregation_calls=1、pooled_gt_reads=0，两类额度分别强制限制；pooled 分母仍为冻结的 234 个 eligible evaluation GT。合成等价测试不能代替完整协议独立复审或负责人对整张 A+B 卡的批准。 |

`candidate interval reconstruction`不是本轮可以偷跑的静态读取，它会形成新候选，当前明确未授权。A2-004的25 fits已耗尽；上述25是全新的待批次数，不可沿用004 ledger/output、资源余量或关闭编号。

**数值与stage门槛：**完整五折才报告结果。numeric minimum=`pooled F1>=0.66`；numeric ideal=`>=0.80`。stage minimum还需numeric minimum、至少3/5 fold F1>=0.66、每fold long-FP fraction<=0.25、每fold matched start/end MAE均<=900s；stage ideal将numeric改为0.80，其余不变。FP=0、无match和无GT participant语义沿用冻结本地规则。匹配MAE比较必须报告control/treatment各自matched GT集合新增/丢失；不能因删难例声称边界更准。不得只比较删除FP数与丢失TP数。

**阈值选择语义：**每个outer的四个inner held-out角色、三个固定阈值的全部预测先冻结，再分别在该outer训练participant的评价资格集合上算合并指标；沿用`src/eating_event/a2/execution.py:366-375` 的排序键 `(F1, -FP, threshold)` 取最大，平局偏较高阈值。这个评价集合与训练标签资格分开；不得使用outer held-out评价GT调阈值。

**停止与分类：**

- score/role/schema/label泄漏或任何GT进入推理为`INVALID`；不输出性能结论。
- G3失败为`VERIFIER_DATA_INSUFFICIENT`；不减门槛或删participant。
- 监控、磁盘或时限超过新批准上限为`INCOMPLETE_RESOURCE`；不当作性能负结果、不重试。
- 保存来源缺少精确16D候选特征或无法一致计算新候选的26D输入时，在首次verifier fit前停止`INPUT_NOT_AUTHORIZED`。
- Stage A先复现参考：对105个role中的每个role，使用相同已批准score streams、score-provenance阈值与冻结的原窗口筛选、身份/component分组、排序及300s `<=` 规则，重建参考候选。逐role同A2-004 `role-digests.json`登记行比较区间多重集，键为`(role_id,participant_id,record_id,session_id,component_id,start_ms,end_ms)`及重数；另以规范排序的`support_indices`构成同键下的support身份多重集，保证相同区间没有换掉用于16D的窗。不读旧 `source_16d`/label，不依赖candidate_id。任一role任一多重集不一致即`REFERENCE_NOT_REPRODUCED`并停止；参考通过前处理规则调用数必须为0，不修规则迎合GT，也不报告gap效应。
- 全105参考复现通过后，Stage A才在同一批role上各应用一次严格 `<` 处理规则，比较参考与处理的上述区间多重集。全过程不读取GT、资格标记、match结果或目标FP名单。完整路径总计105组配对、210次规则应用；参考结果直接复用于差异门，不再重建。区间多重集全部相同则`MECHANISM_NOT_SUPPORTED`并在首次fit前停止；support差异只作输入完整性检查，不能单独称几何机制生效。有区间差异仅证明候选机制改变，不证明最终600s decoder仍保留差异或改善F1。后续只有在特征/标签/资源全部齐备并获批时进入Stage B，按上述三种GT阶段隔离评价。
- 完整合法五折未达任一门槛即关闭这一精确gap=0变体；不试gap点、不调feature/minimum/decoder、不做outer个案修补。

## 5. 资源估算和需补新证据

已保存A2-004实际值仅供背景：25个verifier fit、fit wall 2.971s、run RSS 238,301,184B、家族磁盘663,216,129B；它们不预测新候选规模，也不是新限制或授权。105个保存score roles共10,745,700个window score；no-gap run数最多只能以窗口数作极宽的理论上界。若达到该上界，26D float32矩阵本身为 `10,745,700 × 26 × 4 = 1,117,552,800B`（约1.04GiB），不含候选行、support、labels、账本、临时文件或模型。该值是输入行数导出的数学上界，不是预期值或实测成本。A2-004的663MB产物不能线性外推。

当前不能给出可信的新wall/RSS/disk**消耗预测**：候选数尚未生成；现有A2 verifier耗时对应72,112个不同角色候选；新16D派生来源也未获批读取。下表是为一次新study提出的**支出硬停止线**，表示最多愿意消耗多少，既不是预测值，也未获得执行批准；数值与A2/Route3账本独立。首次候选重建前须由负责人确认或改写整表、启动测量方式及投影规则，并连同全部输入一并批准。

| 资源 | 新study拟议硬停止线 | 计账方式 |
|---|---:|---|
| Stage A累计active wall | 1,200 s | 单调时钟从study invocation入口到Stage A终态持久化，含来源核验/重建/序列化；每次invocation写入不可重置账本并累计 |
| 全study累计active wall | 3,600 s | 含Stage A/B全部输入核验、训练、预测、解码、评价、报告与终态写出；不因中断/新invocation重置 |
| 全study累计verifier fit wall | 900 s | active wall的子集；成功、失败及中断fit实际耗时均累计 |
| process-tree peak RSS | `min(4,294,967,296 B, floor(3 × 首次启动可用RAM字节 / 5))` | 首次启动取一次OS可用RAM样本并冻结ceiling；各阶段同一ceiling，须事前审阅可强制执行的进程树限额与监测方法，缺样本/监控即停 |
| Stage A study disk | 2,147,483,648 B | 新输出、所有临时/原子写副本、外置账本与锁的**峰值占用**，不删证据来腾额度 |
| 全study disk | 4,294,967,296 B | 同一计费范围的峰值占用，不按阶段重置；首次启动同卷可用磁盘须≥8,589,934,592 B |
| compute worker threads | 2 | 进程树同时运行的计算worker合计≤2；监控/I/O线程另记，任何库线程池不得绕过此上限 |

**事先冻结的Stage B入场规则（拟议）：**仅在全105参考复现、全105处理完成且区间多重集有差异后，从Stage A自身的无标签候选产物记录各role数量，记处理候选总数`N`、25个预定verifier周期各自“四个OOF训练role行数之和 + 对应held-out角色行数”的最大值`M`、25个held-out预测role总行数`S`、Stage A登记的**完整处理候选行**（role/身份/区间/support/新16D，冻结UTF-8编码）的文件字节和`B`、同一计费范围在Stage A末当前占盘`D_A`。`D_A`已包含`B`，公式重复预留属故意保守。这些量不读取GT。只有`D_A + 3×(B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296 B`且`536,870,912 + 6×232M ≤ 冻结RSS ceiling`、Stage A所有硬线未触及、feature/role/GT阶段门已就绪，才允许首次fit；否则在fit前`INCOMPLETE_RESOURCE`或相应输入终态。`232=16D float64 128B + 26D float32 104B`，`8S`是float64分数数值部分；3倍、6倍及256/512MiB固定余量是事先选择的**入场安全系数，不是RSS/磁盘预测**，也不保证覆盖support、模型、JSON和临时副本的实际开销。新study Stage B须冻结并经独立审阅按verifier周期惰性载入/释放训练与held-out角色的实现，禁止一次预载全105 role矩阵；做不到则该入场式无效、不得fit。通过只表示允许在监控下尝试Stage B，任一硬线超限仍立即停。N/M/S/B/D_A只能代入此事先批准的式子，不得据实测值调整系数、上限或输出范围。本段仍是待负责人批准的成本政策，不是本轮运行许可。

全部显式临时/原子写文件拟放在新study输出同卷，外置账本/锁亦在该卷；若任一隐式临时文件使用别卷，须在首次启动前把该卷纳入同一峰值计费及独立空闲检查，否则停止。资源监控不得以低频抽样冒称严格上限；未来执行实现须证明进程树RSS/线程/磁盘硬线如何强制或在大分配前保守拦截，并由独立审阅确认。若崩溃造成最后active/fit片段无法从持久账本核算，终态为`INCOMPLETE_RESOURCE`且不可续跑，不以新invocation归零。

**本轮补证后的区分：**16D公式已经定位，仍没有获批的精确派生cache成员路径、A1根目录和role到窗口的绑定；固定10D公式尚未在本轮允许的代码范围内审阅。上述10,745,700和1,117,552,800B是数学上界；即便另存所有16D float64行，追加的数学上界为`10,745,700×16×8=1,375,449,600B`，仍未计对象、support、重复矩阵、JSON、模型和临时文件。它们不能充当RSS、磁盘或wall估计。

| 首次候选重建前必须冻结的决策 | 当前可核对的精确证据或尚缺内容 | 未满足时 |
|---|---|---|
| A1身份和分数输入 | 指明冻结A1 artifact root、`role-graph.json`、`window-identity.json`、`score-provenance.jsonl`及105个登记score文件的精确路径、hash、所需身份/role/阈值字段；只读score NPZ `ids/raw/relative`，按原score契约核对来源/顺序 | `INPUT_NOT_AUTHORIZED` |
| 派生窗口和16D | 指明cache-manifest与已批准record身份审核的精确路径/hash及登记cache_path；逐cache只读`starts,ends,coverage,crosses_gap`，复用原有效窗条件，禁止读其他数组、raw和原metadata；明确新16D按上式重算 | `INPUT_NOT_AUTHORIZED` |
| 参考分组与固定26D | 此行原为2026-09-27静态读取范围记录；四个精确源码随后获准只读并已核原逐role标签/固定10D定义。该源码静态核验不能代替真实历史artifact身份、26D运行期代码冻结或跨OS数值等价 | `REFERENCE_NOT_REPRODUCED`或`INPUT_NOT_AUTHORIZED`，按失败位置记录 |
| 保存参考核对 | 只批准A2 `role-digests.json`登记105个candidate row文件的`role_id,participant_id,record_id,session_id,component_id,interval,support_indices,boundary_kind,source_segment_id`及必要candidate行定位；不读旧`source_16d`、标签、模型分数。须证明字段级隔离，混合整行后过滤不合格；若需预生成脱敏reference视图，另批其精确来源权限、路径/hash及生成步骤并独立审阅 | `INPUT_NOT_AUTHORIZED` |
| 原标签与三阶段GT | 核实原A1逐role标签调用链；定义100个inner/subinner标签role、20个inner评价role、5个outer终评role的participant白名单；原来源七字段只是上限，消费者的阶段视图只暴露共同五字段加该阶段一种资格，须证明读取前即限制可见数据，单JSON全量解析后过滤不合格 | `INPUT_NOT_AUTHORIZED` |
| 独立study与资源 | **本行为2026-09-27旧Windows输出草案，已由下文WSL绝对路径方案取代，不得作为批准路径。**唯一研究ID仍为`route2-candidate-overlap-v1-001`；正式Linux image/study mount/ledger/lock须在具体卡中冻结并证明首次未占用。账本记录每次参考/处理应用、fit reservation/start/end、预测、解码、资源快照和终态，失败/中断同样计入，禁止重置或自动重试。上表数值硬线和Stage B入场式、所有写入及承载层例外须与全部输入同时单独获批 | `INCOMPLETE_RESOURCE`或尚未授权启动 |

上表给出可审阅的数值预算提案，但硬停止线仍需负责人确认/改写，并不证明该额度足以完成五折。即使获批，超过即停，不因已有消耗而补额度。Stage A+B保持同一次事前准入，不能因特征/GT/静态定义仍有缺口而自行先做Stage A。若另提Stage A-only，须另写范围、预算、审阅和授权决定，不能沿用本提案的部分许可。

改变决定的精确新证据：

1. **300s连接前轨迹或固定分数上的精确重建差异：**判断是否有多个正run被300s规则连接，决定所选机制是否有真实处理差异。当前轨迹`NOT_SAVED`；重建它会生成新候选，须纳入未来明确授权。
2. **新候选的16D合法输入来源：**公式与派生cache成员名已静态定位，但精确登记路径、hash、role/全局ID绑定尚未批准，A2附加10D计算定义也未在本轮静态白名单内核实。现有旧candidate向量不能映射给新边界；路径/绑定/定义不明时不得猜测或搜索。
3. **官方/正式推理接口范围：**决定单record/session完整批次与分数数组是否可用，是否存在未来/跨文件约束；缺失会阻止部署结论，也可能令候选run定义不适用。
4. **候选数量与资源先验：**本提案要求Stage A+B全部准入条件及两阶段预算在生成数量前一并获批；Stage A得到的实际数量只用于判断是否满足事先冻结的Stage B资源投影规则和上限。投影不满足就停止并返回证据，不能运行后补预算。候选计数本身属于受控验证，不在本轮执行。若完整前提仍无法补齐，是否另提Stage A-only几何证据验证须在下一轮单独讨论、具体化并审阅，当前提案不允许自行改为分段执行。
5. **官方非惯用手PPG可用输入/场景标识：**决定现有IMU score streams能否代表完整竞赛方案。本验证不能填补PPG要求的实施证据。

## 6. 当前决定

证据支持优先验证**候选区间融合**，不支持立即设计fixed-score selector：11个竞争pair虽真实，但推理组定义、同component语义和跨record输入权均缺失；重叠NMS对它们没有直接作用。对候选融合机制的支持是结构性线索，不是300s因果证明；14个FN提供边界问题线索，不是预期可恢复TP数。固定分数下此机制不会新增交叠窗口的正分信号；低覆盖不足以单独证明不可恢复。仅在58个原零注释交叠预测区间内裁切/切分不能创造GT交叠，但过滤可能改善标注合约FP、碎片也可能增加FP；行为仍UNKNOWN。

建议结果为`SPIKE FIRST`：若新的有限授权能覆盖一次candidate重建、精确新候选特征来源、25 verifier attempts及唯一资源预算，值得跑这一种严格固定变体。现阶段未满足feature source、规模投影和新授权条件；本文件及后续Prompt均为`NOT_EXPERIMENT_AUTHORIZED`。本阶段结束后不自动进入训练、selector优化、路线3或production。

## 7. 整合后的讨论顺序

用户希望在路线二证据不足时，先补齐并完成这一受控验证，再决定三个架构方向各自是否值得进行最小验证。路线二尚未执行，因此不是历史运行的重试。协议的完整执行包括预声明的合法早停，不要求门槛失败后继续25次拟合；Stage A产生新候选，仍须先获单独授权。

路线1是官方资料审查，用户接受核验后的标注合约目标；官方精确接口/matcher及PPG要求的完整实施证据仍缺。路线3 v1-003已合法COMPLETE但四门FAIL，F1=0.5882352941低于A2-004；只关闭固定候选/26D下的matching-aware逐候选目标变体，不否定HGB家族或事件中心架构。

候选几何的gap=0方向已由本设计覆盖，不以新名字重复。180秒最短输出是另一个变量；低容量边界/联合事件输出需合法特征与GT-free运行时组；连续时序表示需信息增量证据。不得无条件将三个方向各跑一遍，路线二结果也不自动授权后续验证。

当前仍需冻结新16D精确来源/role绑定、固定10D、原标签与评价集合语义、分阶段GT读取实现、原窗口/component实现身份、非候选协议等价审阅及独立study资源数值预算。参考复现的比较标准已在本设计明确，但尚未由合法重建实证通过。新对话条件式执行准备入口保存在既有 `docs/handoffs/2026-09-27-route2-candidate-interval-validation-authorization-prompt.md`；修订与独立复审状态见既有 `docs/decisions/2026-09-27-route2-design-review.md`。不新增交接文件，本轮不启动实验。
 
## 8. 本轮静态源码补证与准入卡（2026-09-27）

本轮只读核对以下九个精确源码；表中SHA-256是当前工作树文件内容指纹，不证明这些字节就是A2-004历史运行时绑定的版本。

| 源码 | 当前工作树SHA-256 | 静态核实内容 |
|---|---|---|
| src/eating_event/a1/boundaries.py | B0502AFB300AE6B6EF143619E987F7E4AC9148B60B3EDF9AA9ABE02E2D694394 | component先按start_ms、end_ms、row_index排序；只接受同participant/record/session，拒绝跨hard gap；support window以start_ms <= 当前end_ms连成observed-support component，source_segment_id为null。 |
| src/eating_event/a1/inputs.py | 4F0CF752E6CF970A27C177733B539D30A3FBCEB165D3E920A749C3E8C0576766 | 有效输入要求end>start、start非降序、crosses_gap全false、coverage至少0.8、invalid_runs不高于20，按历史revision检查session边界。旧load_inputs会先载入整份eligibility，并读features、labels、invalid_runs等成员；新Stage A不得复用。 |
| src/eating_event/a1/execution.py | 437EFCAA832811131F80303FC1C86BFBDF2BFA52CB09E2FE9472769BB7866FCD | subinner训练角色与inner held-out角色的candidate均按participant的training_truths标注；outer held-out candidate调用label=false，标签保持空。inner阈值选择在outer.fit_participants上，outer终评在outer.scored_participants上。 |
| src/eating_event/a2/features.py | 30EAFFC5E3CD39455B1D3D429B82CBDF873755169343E67E4EC9DB0E11E53581 | 固定10D顺序为inside mean、inside线性25百分位、inside positive fraction、inside最长重叠positive-run fraction、pre三项均值/positive/observed、post三项均值/positive/observed。lookaround为300000ms，observed fraction除数40；与source16D拼接后转float32，要求26D有限值。 |
| src/eating_event/a1/events.py | 294FCD6B2BB4AF787209A99D57A66131347556A0F33D761D6A3102AE69E26A4F | positive为raw-threshold_reference >= 0；candidate内部按(start_ms,end_ms,index)排序；旧融合条件为next.start_ms <= current_end + fuse_gap_ms；support保存完整WindowIdentity。fuse_gap_ms=0仍会合并端点相接。16D计算来源和顺序见§2。 |
| src/eating_event/a1/pipeline.py | EADA692E5FF3C46C3B9F880F11E85D800F4F9E7447E5DDFCE97E4A7324730E00 | role graph为5 outer、每outer 4 inner、每inner 4 subinner；总计105 candidate roles及25 verifier roles，participant划分逐层互斥。 |
| src/eating_event/a1/scoring.py | 244A34D02AA60BB58463B8848A09FEFCEDF6F49D4959A11D2A09137AE5C60F16 | verifier为HistGradientBoostingClassifier；静态默认positive_weight=3、seed=20260910、max_iter=100，G3门为至少20正candidate、至少5名正participant及两类齐备。具体A2-004配置值仍需历史config身份核对。 |
| src/eating_event/a2/audit.py | 3DA72CC775AAA2381A9F2D1FCD86801DB425015E97F1BB4DA4FB9D8A325D9BED | 当前代码先完整解析eligibility；candidate materialization读取旧row的features并保存旧source_16d，再拼接10D。outer coverage及后续GT诊断在预测前访问evaluation truth。不得将该audit直接用作分阶段GT provider。 |
| src/eating_event/a2/execution.py | 6CA6CDFF4C3ADF4C1CBA50DD72229DCF80EE2FF4AAAD4C9C8BB6FDB6F9465E33 | 当前执行结构为20 inner fit/predict、5 outer fit/predict；每outer先聚合四个inner角色的三阈值预测，再在outer训练participant评价选阈值，之后拟合outer verifier、预测并终评held-out。当前代码默认阈值0.10/0.25/0.50，decoder经A1 decode_candidates，outer后做pooled评价。 |

### 静态结论与仍未通过的门

参考候选规则可按原实现精确表达：已核验role scores经登记threshold转换为relative；只保留relative>=0；使用A1有效窗口及observed-support component；positive支持按(start_ms,end_ms,index)排序；300s参考只在next.start_ms <= current_end_ms + 300000时延续。区间多重集键和support身份多重集定义仍按§4执行。处理谓词必须独立写成严格next.start_ms < current_end_ms。

训练标签调用链已定位为同participant的training_truths加任一严格IoU>0.25；100个inner/subinner candidate roles有训练标签，五个outer candidate roles保持null。A2 nested执行顺序和固定10D公式均已从白名单源码定位；这解决了“公式与历史逐role调用点未知”的静态问题。

以下仍是实质阻断：当前工作树源码摘要没有证明A2-004历史运行绑定；A2-004精确config与fold/source identity尚未获准读取；matcher/evaluator实现位于本轮静态白名单以外，因此只能从已有文档确认约定，不能完成实现级等价审阅。当前A1 loader与A2 audit均不能作为新study输入器：前者读取宽于允许范围的cache成员和整份GT，后者预载全部资格数据并提前使用outer GT。新实现的role惰性加载、GT/reference读取隔离、进程树RSS/worker、峰值磁盘、单调wall、崩溃账本均尚未存在或审阅。

### 代码与输出路径清单（均未创建）

拟新增代码限定在src/eating_event/route2_candidate_overlap/：contracts.py（输入与role契约）、inputs.py（登记文件验证和role惰性读取）、gt_provider.py（阶段限定的GT接口）、candidates.py（300s参考、严格重叠处理及16D）、features.py（固定10D整合）、execution.py（nested Stage B）、budget.py（不可重置账本与硬资源监督）。这是供准入卡审阅的拟议路径，不构成实现完成或运行授权。

拟用输出路径仍为artifacts/route2-candidate-overlap-v1-001/、artifacts/route2-candidate-overlap-v1-001-budget.jsonl、artifacts/route2-candidate-overlap-v1-001.lock。本轮未创建、未检查占用状态。

精确artifact路径/hash/role绑定尚未获数据读取授权；105 role的score/cache/reference登记、GT role-scoped provider或派生视图、candidate混合行字段隔离、A2-004配置与matcher/evaluator实现身份、资源监督实现和独立审阅均未通过。故此卡仍为INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED；不进入Stage A-only，也不创建运行产物。

更正（同日后续只读核验）：§8写入时尚未检查占用；随后仅对上述三个study输出精确路径执行Test-Path -LiteralPath，目录、账本和锁均不存在。未读取输入artifact，也未创建study输出。

A1 scoring静态参数补充：HistGradientBoostingClassifier verifier使用learning_rate=0.05、max_leaf_nodes=15、max_depth=None、min_samples_leaf=1、l2_regularization=1e-3、max_features=1.0、max_bins=255、early_stopping=False、tol=1e-7、warm_start=False、class_weight=None；positive样本weight、random_state与max_iter由调用参数提供。此为当前白名单源码定义，不代替核对A2-004所绑定的实际config及源码身份。
 
独立静态复核补充：A1 score ids是stable window identity对应的global index；A2 audit验证window-identity.json与按cache manifest顺序构造的stable identity逐行一致，并要求role score ids精确等于该role scored participant的global-index序列。此映射仍需在获批artifact中核实。A1旧输入校验还含cache级invalid_runs<=20及111D features有限值；Stage A拟读几何四成员无法重演全部A1输入审计，因此准入资料必须证明保存score ids来自已通过原A1窗口接纳检查的冻结run，不能静默省略质量条件，也不能为此读取features/labels/raw。A2 audit的candidate-row spool会整行JSON解析后检查label/features/source_16d；它不能充当Stage A字段隔离reader。A2 fit阶段局部按role延迟candidate rows，但truth map仍全局预载，不能证明GT隔离。
 
## 2026-09-27 准入卡复核：实现快照与未闭合门禁

状态：INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED。本节记录准备工作；不授权数据读取、候选重建或实验。

隔离实现只新增在 src/eating_event/route2_candidate_overlap/。逐文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| __init__.py | 630C4829E499D53040C136D9EF9722721023EF55825F1E1AA843DC9DA97C9BC8 |
| contracts.py | DC07ED531DE308EF459FEAAFFD954A65BB1BA5D7658F96492D0AE7ED212DE072 |
| inputs.py | A9A93FBCB6974E310F0ABAD204CDA85786E5A0F3B4E9DAD7B11DFB49BFCA1E66 |
| gt_provider.py | 5D87CF91BA72E268179A14AE6AD901C1DCCAB45AA6789B45C31804F0D8831233 |
| candidates.py | D61E213FC6E56E8FB9AAD4E4E5A047945703B63A6F81A592D4723B82409E0E05 |
| features.py | C88B025E9C0AC2BD12548C68713E02FE88F84CEAB8F2829FFE8CEF82E2BA687A |
| references.py | F3CEA03ED7D017E7FFC87FABF865781F676F21E0B7BD1CEA90AC1F10949A55CF |
| execution.py | 17B250D7EAF2E31DCB6D52F886F3D02364900CD55B65F3567151BA97FB3DE96E |
| budget.py | A101DD3D1BC757C56E6AC18E5B3EDB9CEDE32829024830DEAD91684EF2E45380 |

这些是本次准备代码的当前指纹；没有运行测试、导入/编译代码或调用函数。允许静态读取的既有源码九文件及其哈希在 §8；未扩大到其他源码。没有读取、stat 或哈希实验 artifact、GT、raw sensor、原始 metadata、official test 或 external data。

只对以下精确新输出路径执行了 Test-Path -LiteralPath，结果均为 False；没有创建目录、账本或锁：

- artifacts/route2-candidate-overlap-v1-001/
- artifacts/route2-candidate-overlap-v1-001-budget.jsonl
- artifacts/route2-candidate-overlap-v1-001.lock

独立静态审阅查出以下 P1 阻断。审阅范围是隔离实现和 Route2 文档；审阅者没有运行测试、导入/编译、调用函数或读取 artifact。之后对 score raw-relative、多 cache identity 映射、reference WindowIdentity support 映射、以及 GT pre-open scope 检查所做的修改尚未由审阅者复核：

1. 完整输入登记仍未由真实 role graph、A1/A2 registry、role/global-ID 映射和登记文件 hash 证明；approval/readiness 仍能由调用方构造，不能作为实验批准或输入完整性证明。
2. Stage A 仍存在可注入 reader/callback 绕过隔离的风险，且执行路径遇到处理候选变化后返回 INPUT_NOT_AUTHORIZED；当前不是可运行的 A+B 路径。
3. GT provider 在打开文件前校验 scope hash 的代码已补，但尚无经批准的精确七字段、role/participant-scoped 派生视图、派生来源/生成权限/hash 或独立审阅。运行时代码对行的 participant 检查发生在解析该行后，不能替代预先物理隔离及绑定到真实冻结 role graph 的证据。
4. 旧 A2 reference 输入的 support_indices 实为 WindowIdentity 对象。实现已改为按精确 identity 投影映射 global index，但修改未复审，且未获准读取或生成脱敏 reference 视图；旧混合行中的 label、旧 16D、分数不得被 Stage A reader 看到。
5. 无 Stage B adapter：训练标签语义、全新 16D + 固定 10D、HGB 配置、nested role 运行、inner 三阈值选择、decoder、matcher/evaluator 调用链未落成，也未逐项证明与 A2-004 等价。105 个参考 interval/support 复现本身不能证明等价。
6. ResourceEnforcer 目前只是协议接口，不是可执行的进程树 RSS、磁盘峰值、worker 数和 wall-time 硬限实现；当前计时与异常/崩溃终态也未证明覆盖完整 invocation 到终态的 active wall 及跨中断不可重置账本。
7. ledger 的本地排他创建/哈希链思路不能证明调用计数与实际 Stage B 调用原子绑定、跨卷临时文件/ledger/lock 磁盘合计、进程树监测或抗崩溃审计完整性。不得据此宣称资源线可执行。

### 完整 A+B 入场卡待补证据

| 门 | 必须绑定的精确证据 | 当前状态 / 所需授权 |
|---|---|---|
| A1 score、identity、cache | 冻结 A1 root/manifest、role graph、window identity、score provenance、105 个 role 的 score NPZ、每个 participant/record/session 的 cache manifest record 与 cache 文件；逐项 exact path/SHA-256/字段/role/global ID 顺序绑定。score 只开 ids/raw/relative 和阈值；cache 只开 starts/ends/coverage/crosses_gap。 | 尚未打开、stat、重哈希；请另行给出并授权精确登记清单及只读字段投影。 |
| A2 reference | role-digests.json 与 105 role reference 行的精确路径/hash/role；由 WindowIdentity 支持绑定到 global ID。Stage A 允许字段仅为 role、identity、区间、support、boundary kind、source segment；必须隔离旧 label、旧 16D、分数。 | 尚未读取。若需派生脱敏视图，请分别授权生成，给出生成代码/权限、目标路径/hash，并独立审阅后再登记。 |
| GT | 原来源七字段为上限；按phase、role、participant预先生成物理隔离的六字段视图（共同五字段加该阶段唯一资格）。训练只暴露training_eligibility，inner/outer只在各自预测冻结后暴露evaluation_eligibility。视图要绑定真实冻结role graph、participants、phase、role和exact hash。 | 尚无获批视图或读取权限。原GT不得全量解析后过滤。 |
| A2-004 历史对照 | exact A2-004 config/run provenance、训练标签和模型配置、nested role/阈值选择、decoder、matcher、evaluator 的实现与 hashes。 | 现有允许静态源码范围不含已证明的历史实现身份；请提供精确路径并另行授权静态审阅。 |
| Stage B 与硬限 | 新 Stage B adapter、实际调用与不可重置账本关联、可执行 OS resource enforcement、异常/崩溃测试证据及独立代码审阅。 | 未实现/未审。不得开始 Stage B。 |
| 资源数字 | 负责人确认或改写本节 §5 的全部硬限，并一次性批准 A+B 两阶段预算。 | 待确认；不得在 Stage A 后再补 Stage B 预算。 |

§5 当前提案，全部数值须由负责人确认或改写后才可成为硬线：Stage A active wall ≤1,200 s；全 study active wall ≤3,600 s；累计 fit wall ≤900 s；进程树 RSS ≤min(4,294,967,296, floor(3 × 首次启动可用 RAM 字节 / 5))；Stage A 峰值磁盘 ≤2,147,483,648 bytes；全 study 峰值磁盘 ≤4,294,967,296 bytes；首次启动同卷可用空间 ≥8,589,934,592 bytes；并发计算 worker ≤2。active wall 需涵盖启动至终态写入；峰值磁盘需含输出、临时文件、账本/锁及其卷上的副本，并且任何崩溃不得重置额度。当前代码尚未实现/证明这些强制条件。

Stage B 入场式沿用§5原定义：`D_A`为Stage A结束时同一计费范围的当前占盘（Stage A峰值另受2GiB硬线约束）；`B`为完整处理候选UTF-8文件字节数；`N`为处理候选总数；`S`仅为25个held-out预测role的总行数；`M`为25个verifier周期中四个OOF训练role行数与对应held-out role行数之和的最大值。不得在看到Stage A数量后改写这些口径：

- D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296 bytes
- 536,870,912 + 6 × 232M ≤ 冻结 RSS ceiling

全部候选与两阶段预算必须在首次重建前一并获批。计划调用上限：参考 role 105 个之后处理 role 105 个；candidate model fit/predict 为 0；verifier 最多 25 次 fit attempts、25 个预测批次；decoder 65 次；event evaluator 最多 21 次。任何参考失败立即停止、处理调用为 0；处理候选 interval multiset 全相同则在 fit 前停止。不得自动重试、加预算或启动后三个架构方向。

终态保持：参考失败 REFERENCE_NOT_REPRODUCED；处理与参考完全相同 MECHANISM_NOT_SUPPORTED；身份/来源/标签隔离/协议违规 INVALID；G3 不足 VERIFIER_DATA_INSUFFICIENT；资源或崩溃未完成 INCOMPLETE_RESOURCE；只有完整合法执行才按预声明指标判 COMPLETE。Stage A-only 不属于本卡，必须另提、另审、另授权。
 
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

## 2026-09-28 来源登记、物理视图及当前源码复审

本节更新并取代更早“未能登记/未能投影”及过时隔离源码审阅条目的当前状态；更早内容保留为历史记录。工作树为 `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。本轮没有运行测试、训练、预测、候选生成、解码、评价、Route 2 Stage A/B 或旧 audit/run；没有读取、遍历、stat 或重哈希 raw sensor、原始 metadata、official test 或 external data。

### G1 源事件与 denominator

只依据获准的派生 `event_eligibility` 与冻结 role graph，登记 census 为：281 条源事件、43 名源参与者；role graph 有41名参与者（其中40名在源事件中出现、1名无源事件）；264条源事件在图内、17条在图外。17条图外事件的 training/evaluation eligibility 均为 false。training 与 evaluation 的 eligible identity 集合完全相同，各234条；无单阶段 eligible 事件；图内另有30条两阶段均不 eligible，全部不 eligible 共47条。

因此保留281条源事件的原标签与资格 census；不因越图直接删源事件。物理 GT 视图只按冻结 role 的参与者集合取其源行，并保留图内不 eligible 行及原资格字段；训练/评价消费者再按各自资格字段取值。外层评价 denominator 仍是234，不将281改作评价分母。G1 SHA-256 为 `68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30`；role graph SHA-256 为 `3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a`。

### 精确来源登记和物理视图

| 产物 | SHA-256 | 状态与审阅 |
|---|---|---|
| `artifacts/route2-candidate-overlap-v1-001-source-registration.json` | `e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853` | `PREPARED_UNREVIEWED`；独立来源审阅 PASS，ID `review_g1_projection:source-registration:e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853` |
| `artifacts/route2-candidate-overlap-v1-001-inputs/projection-manifest.json` | `ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad` | `PREPARED_UNREVIEWED`；物理视图独立只读审阅 PASS，外部引用 ID `review_g1_projection:physical-views:ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`；manifest 自身 `independent_review_id` 仍为 null |

来源登记审阅核对15个标量来源、105个score NPZ、1,127个cache NPZ和105个reference文件的路径/hash/role/global-ID绑定，文件hash与绑定错误均为0。105/105 score ID 序列与冻结role身份顺序匹配；1,127/1,127 cache记录的局部行序连续，4,508/4,508 geometry NPY成员维度和长度正确，global-ID digest匹配。reference源hash与A2 role digests匹配；source registration阶段候选行内容解析数为0。A2-004 config SHA-256 为 `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`。

来源登记审阅通过后才生成物理视图。独立视图复核核对635/635文件hash、10,842,725行，错误为0；105份reference视图的候选/支持身份与role/global-ID绑定通过，含72,112条候选及1,039,040个support identity；110份GT视图为严格六字段，按100 training、5 inner、5 outer scope登记，outer denominator 234。视图只暴露共同字段加当前消费者唯一资格字段；training为role-only，inner/outer评价视图只在匹配的冻结prediction receipt后开放。两份新产物均保留 `PREPARED_UNREVIEWED`，审阅结果只记录于文档；不得将外部PASS解释成artifact里的正式审阅状态或实验授权。

study目录 `artifacts/route2-candidate-overlap-v1-001`、账本 `artifacts/route2-candidate-overlap-v1-001-budget.jsonl` 和锁 `artifacts/route2-candidate-overlap-v1-001.lock` 已分别按精确路径检查，当前均不存在。

### 当前隔离实现静态复审

独立审阅针对下表所列当前精确源码hash进行；没有导入/编译或运行代码。11个package文件的SHA-256为：

| 文件 | SHA-256 |
|---|---|
| `view_projection.py` | `00278e0b626784d01adb884e3e30e8725321b5617166ee63991be4fef1de0ce4` |
| `gt_provider.py` | `2585830c0b50436027875f4199b7e2f9fc9fd90a89c3851c9001288ca2a9b1c4` |
| `execution.py` | `cd9d90e583cd574f1f2c90cc640e2a8f42785872f289af702653e305737d884e` |
| `stage_b.py` | `66ec9839b772097dc55718104000b02a0bd02d29ae1dd5514f7467d579c5b822` |
| `budget.py` | `c7eef85006f353422321634c2d19a7e5c812889bdce10aa809f4aee1fcbcb0a8` |
| `inputs.py` | `f1251d17314fda838b24aae4c385f94e8b6d8b89aab9bd4d8fde32c3304d3342` |
| `references.py` | `1062a8022c1bcc2f571dea4ae7e7b139a0be4e83a93294e4831e9ba24649774f` |
| `candidates.py` | `e4fa61c88b12fa4b1bae1404801146887d6e573fc46df6199be582225d307ff2` |
| `features.py` | `c88b025e9c0ac2bd12548c68713e02fe88f84ceab8f2829ffe8cef82e2ba687a` |
| `contracts.py` | `75bca1dee6925448624596fc12acc8dd1976929a16f1fbdd87b82b367d9b0415` |
| `__init__.py` | `630c4829e499d53040c136d9ef9722721023ef55825f1e1aa843dc9da97c9bc8` |

**PASS：**G1保留/role投影语义；GT运行期共同五字段加单一资格字段，评价需匹配冻结prediction receipt；输入loader按role串行并关闭lease；Stage A先完成全部reference核对、再处理105个treatment role；严格 interval-multiset 同一时才判机制不支持。Stage B的N/M/S/B/D_A推导和数值算式与设计一致：`D_A + 3 × (B + 232N + 8S) + 268435456 ≤ 4294967296`，以及`536870912 + 6 × 232M ≤ frozen RSS ceiling`。A2-004已审阅部件的配置/代码identity、特征、IoU>0.25标签规则、G3/HGB、nested阈值选择、decoder/evaluator及25/25/65/21调用数一致。

**P1 FAIL：**没有真实OS hard-limit controller；`ResourceEnforcer`只是Protocol，安全默认实现拒绝启动，caller receipt中的coverage布尔值和digest不能证明进程树RSS、线程、磁盘峰值或wall硬限。`BudgetGuard.finalize`在terminal append/fsync和ledger close之前记录wall elapsed，终态持久化时间未计入记录墙钟。二者都阻止实验入场。

**P1 UNVERIFIED：**运行期尚未把A2 audit-ready/role-digests、来源登记和projection manifest重新绑定到不可伪造的冻结准入；`ABReadiness`审阅ID是调用方提供，当前`FrozenAdmission`仍为None。A2历史label prejoin实现与`src/eating_event/metrics.py`中的interval-IoU实现没有在本次准许范围内独立审阅。因此A2协议核对是“已审阅代码部件一致”，不是完整端到端批准绑定。

**P2已修复并独立复审PASS：**`BudgetLimits`、`ResourceSnapshot`、`StageBProjection`、`CandidateFileReceipt`及Stage B预算helper现对整数字段拒绝bool/float，对布尔门拒绝非bool。`budget.py`最终SHA见表；该修改不补足P1硬限或终态计时。

### 下一步唯一实验提案（待另行授权）

仅提一次完整A+B：新study `route2-candidate-overlap-v1-001`，先对105 roles全部运行`reference_300s`，全部参考成功后再对105 roles运行`strict_overlap`；任一参考失败立即停止，参考与处理的interval multisets全同则以`MECHANISM_NOT_SUPPORTED`在verifier前停止。support仅作完整性核对，不改变机制门。Stage A不读GT且candidate-model fit/predict为0。仅在候选区间发生变化、A与资源/输入门通过并取得完整授权后进入固定5 outer/4 inner Stage B；training GT只对训练role开放，inner和outer评价GT分别在冻结对应预测后开放。预期硬调用上限为25 verifier fits、25 prediction batches、65 decoder calls、21 event-evaluator calls；不得自动重试、续跑或降为Stage A-only。

资源仍是待负责人确认/改写的支出上限提案：Stage A wall≤1,200s，全study wall≤3,600s，累计fit wall≤900s，RSS≤`min(4GiB, floor(3/5 × 首次启动可用RAM))`，Stage A disk≤2GiB，全study disk≤4GiB，启动同卷free disk≥8GiB，workers≤2。Stage B仅在Stage A末当前占盘`D_A`、总候选行数`N`、每周期最大拟合包络`M`、held-out预测批次总行数`S`、完整候选文件字节`B`代入上式并通过后入场。实际执行还必须先实现并独立审阅OS硬限、覆盖终态持久化的wall计量、准入身份绑定；本提案不代表这些数字或实验已获批。

最新状态仍为 **INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED**。Route3 v1-003仍为合法`COMPLETE`、四门`FAIL`，不重跑。

## 2026-09-28 OS资源控制器可行性预检

### Preflight记录

- **Goal:** 为完整A+B提供真实硬限及终态计时，再提交用户审批卡。
- **Success metrics:** 进程树内存、计算task/worker、study disk和从invocation入口到terminal持久化的wall均受操作系统控制；来源、视图和A2身份在运行期按冻结hash重验。
- **Constraints:** 当前明确禁止Route 2 Stage A/B、训练、预测、候选生成、解码、评价和旧audit/run；继续遵守raw sensor、原始metadata、official test、external data禁读；不更改历史产物、配置或production。
- **Prior art:** Microsoft Job Object仅提供job-wide committed-memory及active-process等资源限制；NTFS disk quota按volume user计费。WSL `.wslconfig`资源配置作用于所有WSL2发行版。systemd transient service可设置`MemoryMax`、`TasksMax`、`CPUQuota`及`RuntimeMaxSec`。
- **Baseline:** 主机Windows 11 Home build 26200，当前进程非管理员；没有Docker、FSRM或Hyper-V `vmconnect`命令。已有Ubuntu-22.04 WSL2（kernel 6.6.87.2）、systemd、cgroup v2；root通过WSL发行版入口可用，但默认用户没有passwordless sudo。WSL Python为3.10.12，缺少scikit-learn。
- **Candidate approaches:** 原生Windows Job Object不足以覆盖RSS/线程/directory quota；WSL systemd+cgroup和study专用loopback文件系统具备可用资源原语；另一个可行选项是负责人提供有cgroup v2委派及每study硬quota的Linux runner。
- **Critical assumptions:** WSL runner仍需适配Windows绝对路径和FrozenAdmission；输出/ledger/lock必须落在同一隔离文件系统或获得分别硬限；WSL service的wall supervisor必须从外层invocation入口起计时并在terminal fsync/close后持久化结束回执；G1/A1/A2已登记输入需以只读allowlist挂载。
- **Risks:** 原生Windows package当前没有WSL runner；WSL的500ms runtime超限探针实际在750ms终止；WSL模型依赖未安装；loopback可用容量小于镜像标称大小。当前不得宣称真实Route2 controller已完成或其wall边界已证明。
- **Validation spikes:** 仅做无数据OS能力探针，没有读取Route2数据、运行项目测试或模型。systemd cgroup文件实际显示`memory.max=67108864`、`pids.max=4`、`cpu.max=200000 100000`，transient service可启动；`RuntimeMaxSec=500ms`杀死sleep服务但其报告runtime为750ms。64MiB ext4 loopback镜像的文件系统容量为58,675,200 bytes，80MiB写入以`ENOSPC`失败；临时镜像已卸载并删除，transient unit inactive。
- **Kill criteria:** 若不能在冻结预算下将输出、ledger、lock和所有临时写入统一限制于OS硬quota，或外层wall receipt不能完整绑定ledger terminal hash，则停止当前执行路线；不得以采样监控替代硬限。
- **Recommendation: REDESIGN.** 当前Windows-native执行路径不满足硬限要求。先完成WSL-native运行器/隔离文件系统集成与独立审阅，或转交满足相同硬限的Linux runner；这两条路径都未完成，也没有运行实验。

参考文档：[Job Object limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)、[extended job memory fields](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)、[NTFS per-user quota](https://learn.microsoft.com/en-us/windows/win32/api/dskquota/ns-dskquota-diskquota_user_information)、[WSL global configuration](https://github.com/microsoftdocs/wsl/blob/main/WSL/wsl-config.md)、[systemd transient-unit resource controls](https://github.com/systemd/systemd/blob/main/docs/TRANSIENT-SETTINGS.md)。这些API能力证据不等于Route2隔离运行器已实现。

### A+B授权申请状态

上节定义的实验科学协议、输入hash、105+105 Stage A顺序、Stage B调用上限与数值预算组成唯一A+B申请草案。当前只能提交为**条件申请**：需先完成WSL-native controller与path adapter、启动前A2 audit/role-digests/registration/projection重验、terminal-close外部wall receipt、临时/候选输出统一硬quota，以及依赖锁定和独立复审。WSL loopback实验使用的是`/tmp`，尚未验证把批准输出路径映射到该loopback volume后Windows侧的访问方式；不在未明确路径合同前自行迁移产物。条件未满足前，申请状态为`NOT_READY_FOR_EXECUTION`，没有Stage A/B授权。

Route3 v1-003继续保持合法`COMPLETE`、四门`FAIL`，不重跑。

## 2026-09-28 WSL-native controller 与隔离输出重设计（待实施、待独立审阅）

本节是后端与路径的**设计选择**，取代上节尚待二选一的后端问题及§5表内旧Windows `artifacts/`“唯一输出”路径记录；旧路径只保留为当时的空闲检查历史，不作为新运行许可。不改变§2–§5的单一科学变量、调用上限或停止规则。选定 Ubuntu-22.04 WSL2 的 systemd/cgroup v2、study 专用 ext4 loop 文件系统和 Linux 原生 Python 运行器。外部 Linux runner 仅在此路径无法证明硬限时作为另行设计的后备，不自动切换。当前仍是 `INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`：准备视图已生成并获外部只读复核，A+B 未获执行授权，Stage A/B 均未运行，路线二没有合法结果。

### 路径与权限合同

| 用途 | 拟冻结的 Linux 路径/规则 | 准入证据 |
|---|---|---|
| study 卷挂载点 | `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume`，专用 ext4 loop，底层镜像拟放 `/var/lib/route2/images/route2-candidate-overlap-v1-001.ext4`；镜像、挂载设备、mount ID和宿主卷须在授权卡中冻结 | 新study ID首次启动前均空闲；镜像、挂载点和源目录无符号链接/复用；由独立审阅的特权supervisor创建一次 |
| 唯一可写study树 | 挂载点下 `route2-candidate-overlap-v1-001/`，同级 `route2-candidate-overlap-v1-001-budget.jsonl` 与 `route2-candidate-overlap-v1-001.lock`；日志、terminal、wall receipt、模型、候选、原子写副本和临时目录都在同一卷 | 实际mount ID一致；worker只有此挂载的写权限；`/tmp`、`/var/tmp`、`HOME`、XDG/NumPy/sklearn缓存与日志显式落在卷内；禁用core dump及额外可写目录 |
| 已准备输入 | 原Windows登记和投影字节及hash保持不变；新增一个逐**精确文件**的只读路径映射清单，把登记的逻辑Windows路径+SHA-256+role/phase映到WSL只读bind入口 | 映射清单另有hash和独立审阅；worker看不到整个`/mnt/e`、原始源、未到期GT或其他role文件。Stage A只暴露获批score/cache/reference视图；训练role才开放训练视图；每outer的四个inner held-out角色×三个阈值全部12份预测冻结后才开放其inner评价视图，outer预测冻结后才开放其outer评价视图。每phase/role退出撤销bind、关闭FD和清空内存truth |
| 源码与依赖 | 无数据的代码快照及Linux venv放只读目录；Linux依赖版本、wheel hash、Python/systemd/kernel版本和与A2-004协议等价证据写入准入卡 | `pyproject.toml`目前仅给版本下限且WSL缺scikit-learn；安装/冻结不得被误记为已有实验结果 |
| Windows审阅入口 | 只在终态关闭、卷只读后，经 `\\wsl.localhost\Ubuntu-22.04\var\lib\route2\studies\route2-candidate-overlap-v1-001-volume\` 查看 | 专用service UID/目录权限须用无数据文件证明**运行中**Windows默认用户不能读取未到期视图或改写卷内候选/ledger，终态卷转只读后才允许审阅读取；不在执行中向Windows `artifacts/` 复制或同步输出，不形成第二个未计费写位置 |

当前`FrozenAdmission`、`AppendOnlyLedger`、`BudgetGuard`及`run_stage_a`分别使用`PureWindowsPath`/盘符比较；登记与视图内的绝对路径也被`inputs.py`、`references.py`、`gt_provider.py`直接打开。仅替换三个输出字符串无法执行本方案。改造须把**原登记逻辑身份**与**Linux物理打开路径**分开，并使所有读取经过同一冻结映射；原登记/投影hash不得静默重写。`gt_provider.py`当前把GT输入固定为study同级`...-inputs`，新方案须改为独立只读输入根并保持phase/role/receipt核验，不能把GT输入复制进可写study卷来满足旧断言。任何精确文件不能映射、hash/role不符、mount逃逸或提前可见评价GT，均为`INPUT_NOT_AUTHORIZED`/`INVALID`并在读取前停止。

### 双阶段磁盘硬线与墙钟

首次获批invocation从外层单调时钟起计，再创建2,147,483,648 B上限的loop backing及ext4文件系统。Stage A期间**文件系统自身**可写容量不得超过2 GiB；仅在105个参考全部通过、105个处理完成、区间多重集存在差异、`N/M/S/B/D_A`按§5冻结并通过Stage B入场式、相应账本事件已fsync后，特权supervisor才可把**同一卷**在线扩至不超过4,294,967,296 B，并在首次fit前记录扩容前后设备/文件系统容量与mount ID。扩容失败即`INCOMPLETE_RESOURCE`，不换卷、不重置账本。单个从开始就可写4 GiB的loop卷不能证明Stage A 2 GiB硬线。当前仅64 MiB写满探针，**未验证本机2→4 GiB在线扩容**；此项是P1准入阻断。卷容量保守限制可用字节，另需记录文件已分配块、ext4元数据、宿主镜像实际占盘与峰值；不得删证据腾空间。`D_A`仍指Stage A末本study计费文件的**当前**占盘，Stage A峰值另由2 GiB硬线约束，不改§5公式。

原§5“首次启动同卷free disk≥8 GiB”在2 GiB隔离卷上不可能按字面成立。拟议修订为：创建镜像前**同时**检查镜像所在WSL发行版backing filesystem和承载其`ext4.vhdx`的Windows物理卷可用空间均≥8,589,934,592 B，并冻结两个实际路径/设备及容量来源；另验证study文件系统阶段容量和余量。WSL内`df`可报告VHD虚拟最大空闲，不能单独证明Windows实体卷有空间；若无法可靠定位VHDX/实体卷和取得物理余量，仍是P1阻断。此为资源合同解释变更，必须与2/4 GiB、wall/RSS/worker数字一并由负责人确认或改写，不能由实现者自行认定已获批。

外层supervisor从invocation入口记单调时钟；Stage A 1,200 s、累计fit 900 s、全study 3,600 s均有独立不可重置deadline。用非`oneshot`服务和进程组kill作OS后备，提前留**拟议60 s停止/终态余量**；该数值须经无数据超时、崩溃和负载探针证明足以覆盖终态写入，再写入预算批准。`RuntimeMaxSec`不能单独覆盖启动、阶段累计或终态，500 ms探针已见750 ms终止；对`Type=oneshot`它还无效。权威wall receipt由外层在terminal ledger append、fsync、close**之后**取结束时刻，绑定terminal hash及invocation ID后另行持久化；receipt fsync/close返回后还须由外层再次核对单调截止，缺少可信的后核验收据则不接纳结果。若晚于任一硬线、receipt缺失、杀进程未收敛或终态不完整，结果为`INCOMPLETE_RESOURCE`且不可续跑。`BudgetGuard.finalize`当前提前采样的wall值仅作过程记录，不可充当权威回执。

`MemoryMax`限制cgroup记账内存，`TasksMax`计所有进程/线程，`CPUQuota=200%`限制CPU时间；三者不自动证明§5的进程树峰值RSS或“同时计算worker≤2”。设计保持原数值提案，但把**精确指标映射与强制证明**列为P1：冻结supervisor、worker、hash/resize helper及库线程池的进程拓扑和compute worker定义；父cgroup须覆盖所有Linux study活动，或对不可纳入者另设同等强制计费并获批准，不能只用worker子组收据声称覆盖全study。记录实际`memory.max`、`memory.peak`、`pids.max`、`cpu.max`和逐进程RSS/线程证据。若无法证明原RSS/worker硬线，必须向负责人提交改成cgroup内存/总task或其他可强制指标的**预算修订**，重新审阅批准；不能把原语探针标成原硬线PASS。

### 准入、验证与最小待授权范围

在首次候选重建前，运行期准入须把A2-004 config、audit-ready/role-digests、G1/role graph、来源登记`e6f03b...1853`和投影manifest`ad85c0...fc5ad`的**经独立审阅批准的身份digest/元数据**与路径映射、代码/依赖、controller、Stage B adapter、预算和负责人**明确的A+B批准记录**绑定，并只核Stage A可见非GT输入的实际文件hash。启动时只读物理隔离的准入元数据；若A2/G1源文件混有标签、GT或资格内容，不为重算其hash在Stage A打开原文件，而复用已审阅的冻结digest和物理投影收据。不能为了启动时“全量重验”打开110个GT视图；训练、inner、outer各视图仅在对应release门后、首次语义读取前由可信reader核其实际文件hash，核错即停，且不得在跨phase对象中保留GT。两个准备产物现在仍为`PREPARED_UNREVIEWED`，manifest `independent_review_id=null`；外部只读PASS不能由调用者的review字符串自行升级。历史label-prejoin与`metrics.py` IoU内核、完整A2协议等价、真实OS controller和上述路径/硬限仍需独立复审。`FrozenAdmission=None`在这些条件闭合前保持拒绝；不得用调用方自填receipt越过。

执行方案见[WSL controller 执行计划](../plans/2026-09-28-route2-wsl-controller-execution.md)。计划中的无数据合成验证只检控制器能力；它不产生候选、fit、评价或路线二科学结果。最小可审阅授权卡仍只申请`route2-candidate-overlap-v1-001`一次完整A+B：105个300 s参考全通过后105个严格正时长重叠处理，Stage A无GT；全同则fit前停；若差异及全部门通过，最多25 fit、25预测、65 decoder、20 次 GT evaluator + 1 次 pooled reduction（21 项合计），0 candidate scorer fit/predict；§5预算和上述WSL资源合同由负责人逐项确认。此卡**尚未可签发**，更不允许自动降为Stage A-only。只有收到用户提供的合法路线二结果后才按既有review讨论三个架构方向；严格重叠机制已包含在本路线，不换名重复。Route3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑。

系统能力依据：[systemd resource controls](https://man7.org/linux/man-pages/man5/systemd.resource-control.5.html)、[systemd service runtime](https://man7.org/linux/man-pages/man5/systemd.service.5.html)、[Linux cgroup v2](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)、[ext4在线扩容](https://man7.org/linux/man-pages/man8/resize2fs.8.html)、[WSL文件系统路径](https://learn.microsoft.com/en-us/windows/wsl/filesystems)、[WSL VHD虚拟与实体空闲区别](https://learn.microsoft.com/en-us/windows/wsl/disk-space)。这些文档只支持设计可行性判断；下文无数据探针已证明部分本机原语，正式controller组合与独立完整实现复审仍未通过。

## 2026-09-29 本机硬限证据与隔离边界修订（当前有效）

本节更新上节“2→4 GiB尚未验证”的状态；它不改变科学协议，也不将无数据探针升级为实验准入。准备视图已经生成并获外部只读复核，但artifact仍为`PREPARED_UNREVIEWED`；A+B没有具体执行授权，Stage A/B没有合法运行，路线二没有合法结果。`FROZEN_ADMISSION=None`必须保持。完整命令、数值及清理收据见[无数据OS探针证据](../../evidence/2026-09-29-route2-wsl-synthetic-os-probes.md)。

### 两层空闲与同卷2→4 GiB

第一次本机Ubuntu-22.04 WSL2样本中，`/var/lib` 位于ext4 `/dev/sdd`、当时mount ID 80；后续独立预检的mount ID为226，**历史ID不能当作正式冻结身份**。探针前WSL层可用`1,015,001,432,064 B`，承载该发行版`ext4.vhdx`的Windows C: NTFS实体卷GUID为`{5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b}`、可用`38,540,595,200 B`，各自高于`8,589,934,592 B`。写盘探针后实体卷可用`34,479,841,280 B`，说明只看WSL虚拟`df`数值会误判实际余量；Microsoft明确说明WSL所示VHD可用空间可能大于实体Windows设备空间：[WSL disk space](https://learn.microsoft.com/en-us/windows/wsl/disk-space)。**正式创建前必须重新定位VHDX、核对两个设备身份并分别实时取样，两层各≥8 GiB；上述历史读数不是入场收据。** 用户授权了本机取证和准备实施；双层解释仍按其要求列为负责人待确认的预算修订。

独立scratch ID `route2-os-probe-139db8f4856949e99fe7410134cf2181`的ext4 loop先显示容量`2,040,373,248 B`，写`2,023,567,360 B`后被`ENOSPC`拒绝；在线扩容前后mount ID 647、`st_dev=1792`、设备`7:0`、UUID`e4812c4c-6f93-4709-949b-2e38b63cfc92`均相同；扩后容量`4,152,066,048 B`，再写`2,111,692,800 B`后再次`ENOSPC`。两阶段实际容量分别不超过2/4 GiB。探针卷已卸载、loop已detach、scratch已删除，正式study镜像、挂载、目录、ledger、lock均未创建。此结果证明本机ext4原语可用，**没有证明**正式Stage B必须在105+105和`N/M/S/B/D_A`门持久化后才扩卷，也没有证明所有应用写入同卷。

### 进程、GT与host信任边界

另一无数据systemd service实际读到`memory.max=268435456`、`memory.swap.max=0`、`pids.max=2`、`cpu.max=200000 100000`，子进程继承`LimitAS=134217728`；第三task与256 MiB虚拟地址分配被拒。这只证明可用的OS原语。拟证明原**进程树RSS≤C、计算worker≤2**时，必须使所有研究进程、线程、supervisor与helper均进入同一`pids.max≤2`父组，并在任何可计算代码之前继承每进程`RLIMIT_AS≤floor(C/2)`：每个进程`RSS≤VMS≤RLIMIT_AS`，因此同时两task的RSS和≤C；另冻结BLAS/OpenMP/sklearn线程、外部Windows helper职责及实际运行拓扑。任何一项不成立就不能标`hard_rss/hard_worker_threads=true`，需修订预算指标或后端后重审。当前完整controller尚未签发这两个强制收据。

代码方向已改为逻辑Windows登记路径与Linux只读bind别名分离，映射键绑定文件hash、role、phase；Stage A只用非GT输入，GT实际文件hash只在release后通过同一个已核hash的FD读取。Stage B改为训练role、inner、outer短寿命phase worker；12份inner预测全部冻结才可释放对应inner视图，outer预测冻结才可释放其视图，worker退出并撤销bind后父进程只接收最小指标/承诺。**映射对象或Python receipt本身不能证明物理隔离**：特权controller必须给出root-owned mount namespace、逐文件只读mount ID、worker退出/FD关闭/撤销的可核收据；源文件还需不可变快照或独占写阻止，避免hash后被别的写者修改。所有临时、日志、HOME/XDG缓存、字节码、core dump、模型、候选、账本和墙钟收据的写去向需按mount ID审计并强制仅落同一study卷。

本机存在更根本的host边界：当前Windows登录账号可执行`wsl -d Ubuntu-22.04 -u root -- id`进入同一发行版root，绕过研究worker的mount namespace，访问原始GT或改写卷。该账号还属于本地Administrators，提升后可接管其他本机Windows账号的VHDX ACL。因此当前单用户WSL方案**不能满足原设计“运行中Windows默认用户不能看未到期GT或改写ledger”这一条件**；新建普通Windows账号不能自动消除此P1。后续只能①负责人明确把Windows宿主账号所有者/管理员列为可信操作者，并将强制隔离对象限定为受控研究worker与其进程树，更新威胁模型和独立复审；或②使用隔离宿主/受控Linux runner并保留原host隔离要求。未经此项明确决定，不给GT物理隔离PASS。Microsoft的[WSL按用户安装说明](https://learn.microsoft.com/en-us/windows/wsl/setup/environment)和[Windows访问WSL文件权限](https://learn.microsoft.com/en-us/windows/wsl/file-permissions)作为边界依据。

### 墙钟、依赖与准入状态

Linux supervisor的ExecStart入口必须先取`CLOCK_MONOTONIC`样本，再建镜像/挂载/账本；Windows预检时钟不得直接与Linux monotonic epoch相减。terminal事件append/fsync/close后，由外层取得terminal hash和关闭时刻、持久化wall receipt，再由独立观察的服务退出时间/返回码判定截止。receipt自身无法在最后一次fsync后再自证“fsync已完成时刻”而不引入新的写入循环；故需独立实现复审明确最终可信锚点和fail-closed验收规则。当前`BudgetGuard`过程elapsed和已编写的ledger close字段均**不是**完整终态wall强制证据。Linux版本和wheel hash已完成准备锁，ABI校验代码已写；但可信只读venv/代码快照、A2-004跨OS数值等价和A2/G1/来源/投影到正式controller运行期的绑定仍未闭合。新的代码和探针均只属准备实现，未完成独立全协议实现复审。

因此现阶段仅本机**原语能力探针PASS**，完整A+B准入仍`INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`。最小待授权卡须先列明host信任边界选择、双层8 GiB实时检查、原RSS/worker的证明或预算修订、2→4 GiB正式门、全读写路径、terminal后wall验收、Linux依赖和所有源码/数据身份及独立审阅ID；随后负责人另行明确批准一次完整A+B。此之前不运行Stage A-only、A+B或Route3。

### 独立实现复审后的设计补充

三份探针的完整机器可读重复回执现已保存于[磁盘](../../evidence/2026-09-29-route2-wsl-disk-probe-raw.json)、[cgroup](../../evidence/2026-09-29-route2-wsl-cgroup-probe-raw.json)和[墙钟](../../evidence/2026-09-29-route2-wsl-wall-probe-raw.json)；磁盘重复探针仍在同一scratch卷两次`ENOSPC`且已清理。Linux CPython 3.10.12的[13-wheel哈希锁](../../../requirements/route2-linux-cp310.lock)和[身份清单](../../../requirements/route2-linux-cp310.identity.json)已完成离线安装、wheel逐字节hash、`pip check`及关键import；具体见[依赖证据](../../evidence/2026-09-29-route2-linux-dependency-runtime.md)。这些产物仍为准备材料，用户可变venv不能直接作为可信运行期根，Linux/Windows及Python patch差异仍须协议数值等价裁决。

最新静态/合成复审还要求正式方案补上：①同一个`ExactPathMap`不能持有105个Stage A role的所有active receipt，必须由controller逐role轮换租约，在下一role可见前取得旧FD关闭与mount撤销证据；②正式卷收据冻结镜像路径、`dev/inode/length`、loop源、ext4 UUID、mount ID/device和2/4 GiB容量，创建前两层free样本与镜像创建的单调顺序可审；③所有研究写入包括`/dev/shm`、`/tmp`、`/var/tmp`、HOME/XDG、字节码、缓存、core dump、phase IPC、stdout/stderr，系统journal的边界须单列，不能由`systemd-run --pipe`合成探针推断；④PhaseRunner异常也须确保子进程退出/只读GT bind撤销，否则没有合法终态；⑤outer GT IDs只可在当前outer冻结预测并评价后以controller私有HMAC key的不可反查承诺出child，key不得给Stage A或Stage B父进程，历史control的matched GT IDs须由可信事后流程用同key承诺化后才能比较集合新增/丢失。代码已有相关fail-closed接口与21项无数据定向测试，但**没有**真实controller、key封存/分发、逐role轮换或独立完整PASS。

运行期元数据校验代码现在要求冻结的来源登记、投影manifest、13-wheel Linux锁/身份和独立`INDEPENDENT_REVIEW_PASS` attestation，经controller封存的`preflight_metadata`只读精确bind进入；启动时不为重算hash而打开混合A2/G1原件或提前打开110个GT视图。但该attestation尚不存在，`FROZEN_ADMISSION=None`；`stage_b.py`仍从活动工作树读取A2 config/源码，且整个Route2执行闭包、venv已安装文件、入口脚本和精确bind都没有不可变快照收据。正式controller还须核验完整只读代码镜像及依赖安装文件，消除活动工作树路径依赖；否则上述Python身份校验不能签准入。历史`label_candidates`逐candidate按同participant的`IoU>0.25`标注、A2按role预分离标签后join和IoU内核已做静态独立复核，边界0.25/0.26有合成反例；真实历史artifact身份、完整运行期及跨OS数值等价仍待复核。

若选择继续本机WSL，须先明确Windows宿主账号所有者为可信操作者，OS强制对象是研究worker及其子进程；这项修改不能由实施者默许。若保留原host用户不可读取/改写要求，应换独立受控Linux宿主并重审输出路径。两种方案都要保持一次性完整A+B批准门，不自动运行任何实验。

**写路径预算边界：**“所有研究写入同卷”精确指worker可写的候选、模型、临时文件、缓存、IPC和stdio均只能在study ext4卷，其他worker可写mount必须拒绝。特权controller创建/扩容的loop backing image位于外层WSL ext4，WSL `ext4.vhdx`在Windows实体卷上分配；它们是同一研究卷的承载层写入，不能假称也位于study卷内。systemd journal、外层wall验收锚以及不可避免的系统写入须逐路径列为可信控制层例外，记录镜像逻辑长度/已分配块、VHDX占盘峰值和例外字节，分别绑定宿主层空间身份与预算审批。若原“2/4 GiB study磁盘”要求连这些承载/系统开销一并计入，则需负责人明确修订指标后再批准；实施者不得自行排除。


## 2026-09-29 负责人决定与准入卡补充（当前有效）

负责人已明确 Windows 宿主账号所有者为可信主体，并确认镜像创建前 WSL backing filesystem 与承载 ext4.vhdx 的 Windows 实体卷分别各需 ≥8,589,934,592 B。见[本轮准备快照与双层预检](../../evidence/2026-09-29-route2-source-runtime-snapshot-and-two-layer-preflight.json)（SHA-256 506e23659875e4520a1cbff4b1eb8fbe9e38d83f0dbd93d9fa2b6d71262c061b）。样本中 WSL backing free 为 1,014,082,801,664 B，C: volume GUID 为 \\?\Volume{5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b}，Windows free 为 28,729,638,912 B。它只是准备样本；正式 supervisor 仍须在正式 image 创建前从同一 invocation 重新核两层空间、设备身份与时间先后。

原始 registration/projection 仍 PREPARED_UNREVIEWED；正式 projection independent_review_id=null。新的完整源码快照 manifest SHA-256 为 03b6cf9d1807bc0520bc00bcf83c27d05e6ed88da615e4895b897a235ffb9e90，venv 安装快照 manifest SHA-256 为 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e，完整准备记录包含 ABI 和依赖身份。没有正式 controller 只读 bind、canonical review attestation 或 frozen admission，因此它们不构成 runtime PASS。

唯一 A+B 申请与所有已知绝对路径、预算候选值、source/runtime hash、合成探针 hash、外部 review refs 和未关闭 P1/P2 集中在[路线二条件授权卡](../../decisions/2026-09-29-route2-ab-authorization-card.md)。申请状态为 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；A+B approval ID 为 NOT_ISSUED，FROZEN_ADMISSION=None。已确认的两项 policy 选择关闭，但其余拟议预算仍需负责人确认；路径映射、OS enforcement、GT 逐阶段视图生命周期与完整 A+B 独立复审仍为阻断条件。不得把历史外部只读 PASS 写成产物自身的批准状态。

## 2026-09-29 follow-up：完整实现复审、跨 OS 合成核验与 pooled 协议裁决

本节为本日实现准备后的更新，不改变本设计的 `NOT_EXPERIMENT_AUTHORIZED` 状态。负责人已确认 Windows 宿主账号所有者可信，且正式镜像前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别各≥8 GiB；正式启动同次 invocation 的实时重测仍须实现。当前准确状态、逐项 P1/P2 和申请路径以[最新整合 review](../../decisions/2026-09-27-route2-design-review.md)及[唯一完整 A+B 条件卡](../../decisions/2026-09-29-route2-ab-authorization-card.md)为准。

Linux prepared identity 中的 `venv_path` 与 `python_realpath` 已分别改为冻结 venv root 和实际 `realpath(sys.executable)` `/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv/bin/python`；identity SHA-256 为 `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`。完整90文件 source 准备快照最新revision `revision-20260929c` 的 manifest SHA-256 为 `9c0bd2c7218a4fbadac6d9254e4ce48aef3586ce84a12e518767a1da14fd90c5`；11,330文件 Linux venv manifest SHA-256 为 `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`。它们是逐文件验证、root-owned mode 0555 的准备树，没有 controller-owned read-only mount、可信 attestation、系统库/标准库完整内容 pin 或 frozen admission。

[无数据 cross-OS synthetic receipt](../../evidence/2026-09-29-route2-cross-os-synthetic-equivalence.json) SHA-256 `6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15` 比较 Windows CPython 3.10.11 与 pinned Linux CPython 3.10.12：纯内存合成 16D、26D、HGB probability、decoder、event metrics 与 pooled reduction 输出的 SHA-256 完全相同。该证据不包含真实 Route2/A2 输入、GT或任何 Stage A/B run，不能替代真实输入的完整协议/数值独立复审。

**pooled 第21次 evaluator reservation 定义已在申请中明确：**15次inner阈值评价 + 5次outer评价 + 1次不读取GT的 pooled aggregation reservation，总计21次预算reservation；只有前20次可启动阶段限定的GT evaluator worker。第21项仅从五个participant-disjoint outer folds已接受的 participant metrics 作归并，不新增pooled GT view。合成探针比较了41个合成participant上的直接历史 evaluator 输出与五折归并，结果对象相等。该语义是本卡中供负责人审核/批准的一部分，不表示已经获得批准，也不代表真实A+B输入已被等价验证。

独立实现复审记录 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 的结论为 FAIL / NOT_APPROVAL_READY。正式特权 supervisor/`ResourceEnforcer`、同卷2→4 GiB ledger门、真实逐role及GT phase mount/revoke、完整写路径与承载层预算、全study RSS/worker强制、terminal后QPC acceptance、controller-sealed admission、control matched-GT commitments/HMAC key lifecycle均未闭合。`FROZEN_ADMISSION=None`；正式 image/volume/root/ledger/lock不存在。Route3 v1-003不重跑，gap=0继续仅由路线二覆盖，合法路线二结果前不启动三个架构方向。

最新 namespace 只读检查 SHA-256 c5a0876532e00b06e38e362d03d4766b8d240e5807005c3ad3b7c72becf81a40，显示正式 image、volume、root、ledger、lock 均不存在。本轮仍没有 Stage A-only、A+B、candidate fit、模型预测、Route3 实验或 110 个 GT 视图读取。Route3 v1-003 维持合法 COMPLETE、四门 FAIL、不重跑；gap=0 覆盖在既有路线二协议内，取得合法路线二结果前不启动三个架构方向。

执行实现的逐项验收以[WSL controller 执行计划](../plans/2026-09-28-route2-wsl-controller-execution.md)的最新补充为准；下面早先章节中“待负责人确认宿主信任与两层8GiB解释”的历史句子由本段更新，余下数值预算及实际运行期证据仍保持未关闭。

## 2026-09-30 frozen source path 对齐

当前 source revision 更新为`revision-20260930a`，manifest SHA-256 `d185893bdf5cde2d8d9cdeecfc4e686fe361cd9ca72454ae0783cddb33c64e38`；90 files / 1,233,457 B，逐文件验证、root-owned、mode 0555。发现并修正`build_study_access_policy`只接受旧 canonical source root、拒绝版本化冻结路径的问题；回归先失败后通过。新证据见[prepared source/runtime revision 20260930a](../../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930a.json)，SHA-256 `a9abd8f2404abd40d1b2b5b3ed2914dac6f6fea71540c0ab8ae35f10f17ed274`。

这只使路径策略与本卡路径一致；它不构成 controller-owned RO mount、完整运行期 source/runtime admission、独立复审或实验授权。原完整实现复审仍为 FAIL，修订后的 source/controller 尚无新的独立 PASS。

## 2026-09-30 整合后修订：预导入信任锚与Stage A role mount原型

本节是设计最新状态，保留此前科学协议，不授予Stage A-only或A+B运行许可。负责人已确认Windows host account owner属可信主体，且建正式镜像前WSL backing filesystem与装载VHDX的Windows实体卷分别独立至少8,589,934,592 B；这是threat-model和预算下限决定，正式invocation live gate仍待实现。

正式controller必须在可信Route2 bootstrap之前建立source tree外信任根。新增repo-side launcher设计为由系统Python -I -S启动，在导入任何Route2包之前核实受保护config/key、root-owned完整source/runtime清单、精确路径/hash、实际只读mount records及bootstrap文件，再exec固定Linux venv。准备代码和fail-closed synthetic tests已进入revision-20260930h，但尚未安装到受保护系统位置，也无root-only config、key/seal、systemd unit/service、可信supervisor或正式launch receipt。代码原型没有形成production anchor，FROZEN_ADMISSION=None是必须保持的拒绝态。

当前准备source h为98 files / 1,378,752 B，manifest 520423b8bdb1372230140fd162ed8d21991593a071374c3899d27160c7cbc7b7；venv 11,330 files / 348,519,927 B，manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e。ABI Python 3.10.12 / x86_64 / glibc 2.35 / CPython cpython-310-x86_64-linux-gnu；解释器hash a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；identity fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f；pip check通过。见[revision h snapshot evidence](../../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930h.json)。逐文件验证和mode 0555不等于只读mount，readonly_mount_proven=false。

Linux mount controller现在要求manifest bytes/hash与frozen admission path_map_sha256一致，包括公开controller方法直接调用；核完整role Stage A input/reference映射；下一role在读取来源前拒绝；拒绝重复精确mount；检查private mount namespace/shared propagation；receipt创建父链fsync；撤销尽力清理全部alias并写durable failure receipt；重复撤销出现alias或mountinfo读取失败时fail closed。path_map.py SHA 69347620995da1d5ac22a2565b03a2af8b840869efd95c85e2b9bd135316d73c；linux_mount_controller.py SHA b07bccd0d4c1a55c71cbb7a29db1bdc17ee014fbb66fa5c895dc60bad14152b4。限定范围只读复核确认直接pin bypass、重复mount与revoke failure evidence/test缺口在source层已修复；无正式审阅ID。这未证明kernel mount、真正private namespace、role lifecycle、worker child/FD生命周期、GT phase release或systemd异常退出。

唯一条件卡仍请求105 reference全通过后才105 treatment；Stage A不读GT、不fit/predict，相同interval multiset在fit前以MECHANISM_NOT_SUPPORTED终止。Stage B固定5×4，25/25/65/21；第21项是15 inner + 5 outer + 1不读GT的pooled aggregation reservation，前20项才打开阶段GT worker。停止分类为REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE；仅完整五折为COMPLETE。

预算请求仍待负责人逐项批准：1,200/3,600/900 s，60 s stop cushion，RSS min(4 GiB, floor(3×首次可用RAM/5))，worker≤2，Stage A/total disk 2/4 GiB，Stage B disk D_A + 3(B + 232N + 8S) + 268435456 ≤ 4294967296，Stage B RSS 536870912 + 6×232M ≤ frozen ceiling。controller image、WSL backing/VHDX、systemd journal、外部QPC receipt、seal/controller receipts还需实际路径、卷身份、峰值字节预算。负责人已确认host owner可信和两个独立≥8GiB floor，但正式建镜像同次invocation live重测未完成。

正式privileged supervisor/ResourceEnforcer、same-image 2→4 GiB ledger gate、逐role和GT phase真实mount/revoke、worker全部写路径与承载层记账、study-wide RSS/worker限制、terminal close后外部wall receipt、可信launcher配置/key/service、运行期source/runtime/input/path-map identity绑定、完整A+B及跨OS数值等价独立PASS仍是申请阻断项。revision h定向合成suite为87 passed；见[synthetic v2](../../evidence/2026-09-30-route2-admission-controller-synthetic-v2.json)，不是production evidence。正式review route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL；limited follow-up无正式ID、无INDEPENDENT_REVIEW_PASS。

状态仍PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED，正式image/volume/root/ledger/lock不存在。Route3 v1-003合法COMPLETE、四门FAIL、不重跑；gap=0由路线二覆盖；合法路线二结果前不启动三个架构方向。负责人另行明确批准本卡前不运行Stage A-only/A+B，不提前打开110个GT视图。



## 2026-10-01 整合后修订：安全 metadata projection 与 q 冻结

保留本设计的科学范围和 GT 三阶段语义。负责人已明确宿主账号所有者可信，以及正式 image 前 WSL backing filesystem 和 Windows VHDX 实体卷各自至少 8,589,934,592 B；同一 invocation 实时 gate 尚未实现。执行状态仍为 `PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED`。

运行期 metadata 改为精确 `route2_admission_metadata_projection_v1`：仅绑定原 source-registration/projection manifest SHA、A1/A2/G1/registry/GT-scope 十项身份 hash、PREPARED 状态与 null authorization；没有 row count、eligibility census、GT records 或开放字段。投影文件为 [2026-10-01-route2-admission-metadata-projection.json](../../evidence/2026-10-01-route2-admission-metadata-projection.json)，SHA-256 `a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c`。`runtime_identity` 只通过 controller-sealed map 读取该投影、attestation、Linux lock 与 identity；不再在 Stage A 前打开完整 registration/projection manifest。`FrozenAdmission`、`ABReadiness`、`ExperimentApproval` 均绑定投影 path/hash。文件仍 `PREPARED_UNREVIEWED`，独立 attestation 未签发；原两份输入产物仍 `PREPARED_UNREVIEWED`，GT 文件完全未打开。

本轮修正五个代码缺口：5个 outer threshold decisions 与20个 inner roles 分离计数；4 GiB 镜像长度与 ext4 可用容量分开校验（扩容样例 4,152,066,048 B）；迟到 Stage B completion 的资源失败 terminal 保留相同结果证据；outer candidate/scores/prediction 对象在下一 outer 开始前释放；metadata projection 顶层与嵌套均拒绝额外 GT 派生字段，并测试实际 preflight 只打开安全 projection 与依赖元数据。无项目数据 Route2 suite 159 passed。

当前冻结 source 为 revision-q，101 files / 1,537,167 B，manifest `0bd424e05b4307b39de5f142e7edeeb04a0c949d0ffc256a01d84b543bea7e7d`，包含唯一需要的历史 A2-004 配置 hash `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`。有限只读 review 确认 q manifest 与这些修复一致，无正式 review ID；整体 review 仍 `route2-ab-full-implementation-review-2026-09-29-FAIL-001`。

设计中的科学卡不变：105 reference → 105 treatment；Stage A 不读 GT；相同 interval multiset 在 fit 前停止；仅机制有差异并且准入通过后运行固定 5×4 Stage B、25/25/65/21，第21项是无 GT pooled aggregation。六个停止状态与原卡一致。阻断项仍包括受保护特权 supervisor/ResourceEnforcer、真实同 image 扩容、物理逐 role/阶段 GT mount 与 revoke、所有 worker 写路径和卷外计账、全 study RSS/worker hard limit、terminal 后外部 wall receipt、完整历史协议与跨 OS 全流程等价、control matched-GT/HMAC 诊断、预算审批及正式独立 PASS。未经负责人另行批准完整具体卡，不得运行 Stage A-only 或 A+B，也不得启动三个架构方向。

## 2026-10-01 整合后修订：revision-r 的 cgroup service 身份证据

负责人已确认 Windows 宿主账号 owner 可信，正式建 image 前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷各自独立至少 8,589,934,592 B；同一 invocation 的实时门仍未实现。revision-r 新增 systemd/cgroup2 后端：固定属性快照、严格 InvocationID 与 capture 前后 unit/PID 比较，及 cgroup2 mount ID/device/mount point/root inode 前后比较。模块 SHA 8c65d7e50ef98eee2fbb296114b9931b277b58013f37db7dcc5b8276bd3cd9fd，测试 SHA 4d602a0754059ddda294f8abb59ba55f1c94d53649e2eedd29dd74097ce07b61。两次局部 review 均 PASS，无正式 ID；[live scratch v2](../../evidence/2026-10-01-route2-live-cgroup-backend-scratch-v2.json) SHA 9897cb6ae717f77b2b41b2c3c4b5e6dd53cef68323e656518bfcf5efd101817a 只覆盖单个惰性进程。

本轮无项目数据 Route2 suite 177 passed / 3.58 s。当前准备快照 [revision-r](../../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001r.json) SHA 1bd7dcb8e6d6127e9a60d6b849312262cb8efbcff5693b678a3b0e1803f7bf82，source manifest deee33c1a187f57cec0d9f5ce44443081db48a784b6252f5eb30ec098a433fdb，103 files / 1,562,738 B，root-owned mode 0555；venv/ABI 沿用 q，prepared mode 不能证明真实 RO mount。

本次仅关闭 adapter 的两个代码缺口。正式 SupervisorOps / privileged service 未安装或接入；2→4 GiB 和双层 disk gate、role/phase GT mount/revoke、worker 全写路径及承载层计账、study-wide RSS/worker、terminal 后 wall receipt、运行期身份冻结、完整历史 A+B 和跨 OS 等价、matched-GT/HMAC 与预算裁决仍阻断。完整 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍 FAIL，准备状态仍 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED。

## 2026-10-01 revision-t：合成数值证据及复审边界

旧跨 OS 收据固定 `max_iter=40` 且绑定旧 Stage B hash，现只作为历史证据保留。新收据 [revision-t synthetic probe](../../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001t.json) 绑定源码快照 manifest `b05a2655213ff2e9afba5943b11de99e886c8162bab195c90f2056f6edbde1f0`、当前 Stage B hash `fe6a45ebe5f3409c12de895c5ae6656284730eb59667526987b4b301561240e5`、A2-004 config hash `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`，并使用 `max_iter=100`。

在 Windows CPython 3.10.11 与 pinned WSL CPython 3.10.12 上，合成 16D/26D 特征、31 个 decoded prediction、event metrics 和 pooled fold reduction 完全 hash 相同。verifier score 原始 `float64` 字节 hash 不同：194/200 个值位级相同，最大绝对差约 `1.73e-18`，最大相对差约 `1.60e-16`，全部分数四舍五入至 14 位小数后一致。没有负责人批准的比较容差，因此这只说明该合成样例上的接近程度，不能宣称完整数值等价。

独立完整静态复审核验 revision-r（103/103）后仍判 **FAIL / NOT_APPROVAL_READY**，无正式 review ID：Windows 入口没有完整可信 A+B 执行边界；新的小型合成 probe 不能覆盖完整 A+B；outer evaluation 缺少同一 held-out GT 下 control reference candidates 与 treatment candidates 的 additions/losses 差分。保留这些为 P1。要关闭 matched-GT 项，设计和实现必须让两类候选在同一 outer role 的同一 GT lease 中做对照，并将差分纳入冻结结果；这不授权提前打开 GT。

revision-t no-data Route 2 suite 在 Windows CPython 3.10.11 为 **178 passed / 4.75 s**。四个此前失败用例的根因为该运行时 monotonic clock 分辨率 15.625 ms；只修改 synthetic fixture 等待下一刻度，生产 budget check 未放宽。准备状态仍 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED；Stage A/B 未运行。

### revision-u 源快照路径复核

revision-t 的跨 OS receipt 曾把工作树 `snapshot_scope.json` hash 写入收据，但快照中仍是上一版 hash。revision-t 记录为 superseded。revision-u manifest `ab898c849e1e22896813bb09866919cd6ed237ceaf8854ed524aef2d3fe1344f` 现包含正确 `snapshot_scope.json` hash `7aecc7db19975be35fc25c7789e7ad2000b05a5ca3e7d17209f7f1898cbdf6e6`；Windows 和 Linux 均独立校验相同的 105-file/1,573,062-byte tree，并从该同一 tree 运行 max_iter=100 合成探针。新的绑定记录在 [revision-u probe evidence](../../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001u.json)，SHA `73358db47b66d35a9eb663adf69c2d68779515a93398fc8441fad0bb428b7f7c`。

独立窄复审确认旧 P2 已通过重建快照与双端导入路径记录修复的范围仍待最终复核。无论如何，这只关闭证据绑定缺陷，不关闭完整 A+B 执行入口、完整跨 OS equivalence 或 matched-GT control-vs-treatment 差分三个 P1；准备仍 PREPARED_UNREVIEWED，A+B 仍 NOT_EXPERIMENT_AUTHORIZED。
### pooled quota 语义与 revision-u 窄复审结果

第 21 项在实现上精确计为 20 次 GT-backed evaluator（15 次 inner 阈值选择 + 5 次 outer 终评）和 1 次不读取 GT 的 pooled reduction。该 reduction 归并五个互斥 outer fold 的 participant metrics，pooled denominator 仍由 5 个 outer receipts 合计并校验为 234；它不重新打开一个全量 pooled GT view。Stage B 结果和预算 ledger 分别记录 20 evaluator、1 pooled reduction、0 pooled GT reads，总调用/归并额度为 21。100 组五折合成等价测试及 no-data suite 已通过；完整 A+B 协议独立审查仍待完成。

revision-u 的 exact source/receipt binding 独立窄复核为 PASS（无正式 ID），确认 105/105 manifest、scope hash 和双 OS 源码/import path；没有新 P1/P2。该复核不覆盖之后的 pooled quota 源码改动、完整 A+B、生产 RO mount 或完整数值等价。当前新 source revision 与 review 仍待建立；实验授权状态不变。

## 2026-10-02 整合后修订：revision-b 准入回放与条件申请

本轮 immutable source revision-b 的 manifest SHA-256 为 82f563d2cac21a5916f03908e5e7cf404fba64157238b0d28027fc79443407f0，105 文件 / 1,657,792 B，scope SHA-256 0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61；Windows CPython 3.10.11 与 Ubuntu 22.04 WSL2 pinned CPython 3.10.12 均使用快照内验证器逐文件复核。Linux pinned dependency venv 为 11,330 文件 / 348,519,927 B，manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e，Python 3.10.12 / x86_64 / glibc 2.35；pip check 通过。

本轮代码修补使 durable replay 检查跨 operation kinds 的全局 interleave，并把 105 frozen roles、role graph SHA 与 StageB completion / terminal replay 连结；25 项 fit provenance 逐项对比事件载荷及模型文件 SHA。revision-b Windows/Linux no-data Route2 suites 各 194 passed。合成 cross-OS probe 中 source/feature/decode/metrics/pooled hashes 相同，probability vectors 194/200 bitwise equal，max abs diff 1.734723475976807e-18；没有批准的数值容差，所以完整 A+B 跨 OS 数值等价仍开放。证据详见 [revision-b prepared source/runtime](../../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002b.json) 与 [cross-OS probe receipt](../../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002b.json)。

科学协议和申请范围未改变：先 105 reference 全通过，再处理相同 105 roles；Stage A 不读取 GT、不 fit/predict；完整候选 interval multiset 相同即在首次 fit 前以 MECHANISM_NOT_SUPPORTED 停止；若通过且资源 gate 合格才允许固定 5x4 Stage B。Stage B quota 为 25 fit / 25 predict / 65 decoder / 20 GT-backed evaluator / 1 GT-free pooled reduction；第21项不读取 pooled GT。路线2取得合法结果前，不重跑 Route3 v1-003，也不开始三个架构方向。

执行 P1 仍开放：可信已安装 privileged controller 与 SupervisorOps/PhaseRunner/ResourceEnforcer wiring；image 2→4 GiB durable gate 与镜像前两处各自 >=8 GiB 同次实时 gate；production per-role RO mount / phased GT publish-revoke / child-FD teardown / HMAC key lifecycle；worker 全写路径系统限制与 controller/volume 峰值 accounting；全 study cgroup/RSS/worker hard limits；terminal 关闭后外部墙钟收据和 crash/cutoff/missing-proof 验收；正式 source/runtime/ABI/input/path-map/approval freeze；完整 5x4 A+B 跨 OS equivalence 与独立 PASS。开放 P2 为所有提出预算及 D_A/B/N/S/M 与卷外写入计费的 owner approval。负责人已确认 host account owner trusted，且 WSL backing 与 VHDX Windows 实体卷分别至少 8 GiB；实时 gate 尚未实现。

完整 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 继续 FAIL。revision-b 两项只读窄复审进行中，均无 review ID；不得记为 complete A+B PASS。source/runtime 和结果状态依旧 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED。

## 2026-10-02 revision-g：当前准入实现与设计边界

revision-g 为当前只读源码身份，manifest `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`，105 files / 1,674,692 B，scope SHA `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`。固定快照的 13 个 Route 2 合成测试在 Windows CPython 3.10.11 为 203 passed / 10.81 s，在 Ubuntu 22.04 WSL2 CPython 3.10.12 为 203 passed / 5.63 s，Linux 有一个 pytest `pythonpath` 配置 warning；两端测试前后都验证了完整 105-file manifest。

新增精确 approval type 门覆盖 `AppendOnlyLedger.create` 与 `BudgetGuard.start`，并在建目录/ledger/lock或调用 OS enforcer 前拒绝 duck-typed approval。revision-g narrow static source review 确认该 P2 已关闭（review ID `NOT_ISSUED`）；此前的 supervisor exact-type 门、终端 replay 显式 role-graph pin 和合法 interleave hash 测试也保留。这些局部源码结论不提供生产 controller 或合法 A+B 执行入口。

跨 OS 合成探针仅含内存数据，raw vectors 为 Windows SHA `1b7d9701689365a75ddd01d6d5a9a4801596fac1b858ecc3e7e98d6c3545a4ff`、Linux SHA `afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc`；指定非概率 hashes 相同，probability 194/200 bitwise same，max absolute difference `1.734723475976807e-18`。容差没有负责人批准，所以结论 `PARTIAL_MATCH_ONLY`。完整 5×4 A+B 数值等价仍未证明。

第 21 项保留 20 次读取阶段 GT 的 evaluator 加 1 次不读 GT 的 pooled reduction；后者只汇总五个互斥 outer-fold metrics，`pooled_gt_reads=0`。revision-g narrow static review 确认其源码语义；完整 A+B independent PASS 仍缺。该复审还确认同一 outer GT 上 reference/treatment keyed additions/losses 算法已在源码实现，但真实 worker/mount/runtime 与合法 A+B 证据仍缺。正式完整实现 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 继续 FAIL；production privileged controller、双层实时 8 GiB 与 2→4 GiB 门、逐 role/phase OS 挂载、全路径写限制、study-wide RSS/worker/cgroup 强制、terminal 后外部 wall 收据、source/dependency/ABI/input/path-map/approval freeze 均未完成。预算只获批宿主 owner 信任和两处独立 8 GiB pre-image floor，其余值与公式均待负责人裁决。保持 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED，不启动 Stage A-only 或 A+B。

## 2026-10-02 整合讨论修订：待负责人确认的执行合同

当前状态：`PREPARED_UNREVIEWED / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`；`FROZEN_ADMISSION=None`。本轮讨论没有形成预算批准或实验授权。

本轮只讨论并回填文档；逐项证据、方案代价和唯一A+B条件卡见[既有review本轮整合后修订](../../decisions/2026-09-27-route2-design-review.md#2026-10-02-整合后修订四项核对负责人裁决草案与最小-ab-条件卡)。以该review续接2026-09-29的最新修订为状态依据，不另建交接包或新研究卡。

| 必须分开的状态 | 本轮核对 |
|---|---|
| 准备视图 | 已生成，仍 `PREPARED_UNREVIEWED`；正式projection review ID为null。 |
| A+B授权 | 未签发；`FROZEN_ADMISSION=None`。 |
| Stage A/B | 均未合法运行；本轮不创建image/volume/root/ledger/lock，不打开GT、不运行测试/探针。 |
| 合法路线二结果 | 没有；scratch、13-wheel准备及21项/203项合成记录均不构成结果或准入PASS。 |

完整独立实现复审仍 `route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL`。g窄审阅无正式ID，只覆盖证据绑定或局部源码；`PARTIAL_MATCH_ONLY`不改为数值等价通过。

**准备身份更正：**本轮核hash的[g原始prepared收据](../../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002g.json)与[cross-OS收据](../../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002g.json)给出的scope是64位 `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`；上方g文字与旧授权卡误录额外`f6`形成66位串。本节纠正当前口径，原卡需正式提交前同步、独立复核；不改原始证据或source manifest，不声称重新验证了Linux source。g source manifest仍 `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`，不是已批准runtime。

### 决定1：信任范围

负责人已明确Windows宿主账号所有者可信，继续WSL2 worker隔离为推荐路径；该决定不再待问。最终卡须列controller/launcher/root key/config/外部observer等可信主体，worker不得控制它们。若新要求是宿主登录用户本人也不能读GT/改账本，则必须改用其不能控制的独立Linux runner，付出输入映射、依赖、设备身份与全控制器复审成本；同机普通新账号不足以证明这个边界。真实worker隔离P1仍开放。

### 决定2：空间与计费

两个独立floor已确定：正式建image前同次invocation内，WSL backing filesystem及VHDX所在Windows实体卷分别≥8589934592 B。supervisor首个Linux monotonic样本在前，绑定backing mount/device、实际VHDX路径/Windows volume GUID、live读数及创建时序；旧sample只作准备证据。两层free不相加，8 GiB不是新增花费额度。

推荐保留研究卷A/full≤2/4 GiB，再单列有界控制层预算：image逻辑长度与已分配块、WSL backing增量、VHDX实体分配增量峰值、systemd/system journal、外部wall/seal/controller receipts。研究卷内ext4 journal及所有worker临时/副本计入2/4；控制层须精确路径/卷/cap/峰值与超限策略，不以删除后净值抵扣。image与VHDX分层报告，同一层避免重复加总；若负责人希望跨层全部相加到2/4，则必须改D_A/容量/入场式后重审。无法隔离共享VHDX增量时保守全额归因或迁专用承载环境。控制层字节cap及observer RAM/tasks尚未固定，卡仍blocked。

### 决定3：原资源指标和物理phase门

优先审保守两task方案：全Linux研究supervisor/helper/worker在同一受控父cgroup，初始task≤2、禁止额外附加或迁出，每进程exec前soft/hard RLIMIT_AS≤floor(C/2)，C为原RSS公式；依赖线程池与helper串行。在已冻结普通地址空间/RSS口径下，RSS≤VMS使总RSS≤C。这会让supervisor占一个task，通常只留一个worker槽；依赖导入/映射能否适用尚无全程证据。若不适用，备选是逐进程地址额度分配并独立证明，或负责人批准改为cgroup charged-memory/worker子组指标；后者必须重审预算和Stage B投影式。memory.max、CPUQuota、采样RSS或环境变量不能代替原指标证明。实际kernel/systemd、继承链及防改限额仍待审。

正式扩容必须在未来一次已批准invocation中完成105 reference全过、105 treatment完成、区间有差异、无标签N/M/S/B/D_A冻结、两式及A资源门通过、账本fsync后，才把同一image/loop/ext4从≤2 GiB扩至≤4 GiB；核前后path/dev/inode、loop、UUID、mount ID/device、逻辑长度和容量。授权前只能以独立scratch身份和假输入验同生产controller门，不得生成真实候选数量。

worker所有输出、临时/副本、模型、ledger/lock、/tmp、/var/tmp、/dev/shm、HOME/XDG、cache、pyc/core、IPC/stdio及继承FD/daemon socket必须系统拒绝或落同研究卷。Stage A零GT；training仅六字段训练资格；每outer12份inner预测全部冻结后开inner GT，outer预测冻结后开outer GT。逐role/phase收据须包含namespace/mount/file身份、hash、participant scope、PID/start identity及release/revoke时序。GT release后同FD先hash再读；退出确认全部child/后代与FD关闭、撤销后才能开下一项。umount本身不使旧FD失效；异常无收据不得COMPLETE/续跑。

### 决定4：wall、运行身份与第21项

推荐可信外部observer验terminal append/fsync/close、receipt fsync/close、service exit/cgroup-empty和最终durable墙钟锚。Linuxmonotonic与WindowsQPC各自测duration并绑定boot/invocation，不能相减不同epoch。60s余量计入1200/3600s，fit900s另计；wall最后写入/验收边界与observer费用仍需裁决。若外部锚末次fsync不能独立证明在deadline内，P1保持；把seal持久化移出wall范围属于另一次预算政策改变，当前未采用。

运行身份需受保护pre-import安装、源码/venv/stdlib/native loader及库闭包/入口/controller/unit/环境/import路径的内容身份与真实RO mount，绑定safe metadata、role path-map、输入和owner/review pins。外部controller-sealed admission在源码树外，避免自哈希循环，并持续贯穿bootstrap→runner→worker→terminal。Stage A不得打开混合G1/A2原件或未release的GT来核hash。0555、wheel版本和parser正确性均不构成完整准入。

推荐负责人接受第21项为GT-free代数归并：20次GT-backed evaluator（15inner+5outer）+1次pooled reduction，pooled_gt_reads=0。独立审阅需核participant互斥/完整、234分母、TP/FP/FN/long-FP相加、F1由总计数算、MAE由未舍入误差和与匹配数加权，保留空值语义，不能平均fold指标。无法从现有统计量恢复的字段须补充分量后重审；如果坚持第21次直接评价，需另审pooled GT scope/release/revoke与预算，不能自行切换。

跨OS概率194/200逐位相同不满足当前未修改的标准。允许预声明数值容差与阈值/排序等离散决定一致，或统一环境争取逐位相同，是负责人待裁决的两个选择；小样本舍入一致不能替代完整5×4及边界审阅。matched-GT additions/losses算法已有窄静态证据，生产同scope/control/HMAC生命周期仍缺。

### 同一张完整A+B卡的批准前提

沿用唯一ID、105 reference→至多105 strict-overlap treatment、0 candidate fit/predict、固定5×4与25/25/65/20+1；六种非COMPLETE停机分类及五折完整COMPLETE见review最小卡。保留原1200/3600/900s、60s、RSS/workers、2/4 GiB和两个Stage B式作为**待批支出线**，不是预计成本。准确路径、当前准备hash、未创建path-map、缺review/owner ID及控制层未固定cap均在该卡列明，不能附条件即刻放行。

还需独立输入/metadata attestation、最终生产控制器全生命周期/资源/wall/只读身份完整review，以及全历史科学协议/数值/20+1等价review；可以由同一完整正式review覆盖，但需明确范围、最终hash与ID。授权前完整A+B验收只能用纯合成闭包，真实运行收据是批准后一次invocation的门，不能要求偷跑取得授权前结果。所有预算/计费/容差/pooled选择确认、旧卡scope同步并独立PASS后，再由负责人单独批准该具体hash卡。

本轮没有执行这些待办。Route3 v1-003合法COMPLETE、四门FAIL且不重跑；gap=0已由路线二覆盖。只有用户提供合法路线二结果后才讨论三个架构方向各自最小验证，不自动启动任何方向。

## 2026-10-02 整合后修订：准入实现推进，工作树尚未冻结

负责人随后指示“开始推进”，据此推进生产准入组件实现及无项目数据的合成验收。该指示没有签发 Stage A-only/A+B 批准，也没有确认其余预算、控制层计费、数值容差或20+1协议裁决。上节“只讨论”是此前轮次的范围，保留其历史记录。

新增连续性合同：受保护 bootstrap 的全部验证完成后，在同一解释器登记真实 proof 对象、PID 与 thread 对象。A+B 入口只能单次消费该登记，不能用重构/序列化 proof、fork 后 PID、不同 thread 或替换后的 FrozenAdmission 接续。真实接续尝试在后续检查失败时也被消费，禁止恢复/重试。

[admitted_execution.py](../../../src/eating_event/route2_candidate_overlap/admitted_execution.py) 只接收固定类型的完整 A+B 绑定，核新 guard/ledger 的共同身份、未启动状态、冻结路径、预算摘要、controller 和 write-volume pins，再直接调用既有 `execution.run_ab`。完整 readiness/metadata/Stage B preflight 仍由原 runner 在 `guard.start` 前核验；没有任意 callback、插件 factory 或第二解释器。返回值是内部结果，尚不能替代 terminal 后外部验收。

**仍缺的生产连接：**pre-import launcher 仍只执行 bootstrap；完整 privileged controller 的装配、真实 OS 后端及外部 observer 尚未接入这条新 API。新增 API 只推进接续组件，不关闭完整实现 P1，不签发实验准入 PASS。

revision-g 源码/依赖快照及原始回执保持原身份；新增工作树源码尚未重新冻结，不能拿 g manifest 批准新代码。准备视图仍 `PREPARED_UNREVIEWED`，`FROZEN_ADMISSION=None`，Stage A/B 未合法运行，路线二没有合法结果。新增合成验收和窄审阅的准确范围及最终计数写回既有 review 与执行计划。

新增扩容合同实现为 [linux_volume_backend.py](../../../src/eating_event/route2_candidate_overlap/linux_volume_backend.py)：仅操作已经创建的精确2GiB卷，验证受保护seal和root-only ledger中的持久Stage B门，核无活动view/worker与image/loop/mount/UUID绑定；真实fsync后固定扩至4GiB，持久外部attempt使部分失败不可重试。首次建镜、双层live采样、外部attempt安装/费用、receipt落账及完整OS接线仍需实现/审阅。

接续窄审阅所发现fresh状态遗漏和摘要大小写问题已修复并获第二轮限定静态复核，非正式review ID。最终15个文件Windows/WSL各323项合成通过；一次真实2GiB RLIMIT_AS/单线程HGB合成检查支持该依赖负载可运行性，不证明全study RSS/task强制。6个新代码/测试hash与范围记录在既有review，未签发新冻结manifest或完整准入PASS。下一处生产断点是统一startup/lock/ledger所有权及launcher→controller→phase worker→外部observer装配；其余原P1和负责人裁决仍保留。

扩容第一轮窄审阅在323项通过时仍发现3P1/2P2。之后增加empty tombstone file+parent先同步、attempt目录实际study-device拒绝、activity计时/边界回放、当前PID实时cgroup与目录身份绑定及wrong-type非阻塞open；最终17个文件Windows/WSL各380项合成通过，8个文件hash前后相同。第二轮独立静态复核确认五项发现在组件范围处理完毕，无新的范围内阻断，无正式ID。原128项扩容组件检查只使用mock，不证明真实loop、完整105+105/5×4、跨崩溃隔离或阻塞syscall外部wall；首次同步失败保持未证明持久化并在镜像修改前中止，外层failure ledger/quarantine仍缺。不得写成完整实验准入PASS。完整review仍FAIL且各预算/协议裁决未获新批准。


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

本轮先恢复原设计、WSL执行计划、review“2026-09-29整合后修订”及最新追加、原授权提示／申请卡，并核对所引用的原始disk/cgroup/wall与Linux依赖证据。原81文件工作集mapping SHA256 f5ad68da431a21b29a3733f89fa9385991f8bbd3ae81c2a2100f213d253ff31b吻合；未变源码的上一轮限定结论继承，本轮改变范围另作限定独立复审。最新详细证据、九文件hash、五项生产缺口及唯一更新的完整A+B最小条件卡，统一见[原design review同名2026-10-07整合后续补](../../decisions/2026-09-27-route2-design-review.md)。

四项分别保持：准备视图PREPARED_UNREVIEWED；A+B未授权且FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二没有合法结果。完整独立实现复审仍route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL；scratch 2→4GiB、13-wheel、历史合成及本轮限定源码复核不是准入PASS。原授权提示／申请卡不改，无新交接包。

实际修改：control_matches.py增加五个历史A2-004 outer最终匹配GT登记和子进程readonly-FD读取；contracts/path_map/production_metadata/production_runner绑定其来源与登记，phase_worker/stage_b按同一GT commitment key输出逐fold／pooled的control最终集合及新增／丢失，候选覆盖另报。新增冻结hash字段a2_004_final_metrics_sha256、control_final_match_registry_sha256尚无合法绑定；实际投影来源权限、五个真实对象、native grant/revoke和新schema完整复审仍缺，未创建或读取投影。outer终评仍只调用一次treatment评价，总合同保持20 GT-backed＋第21次GT-free代数归并、pooled_gt_reads=0；Stage A无GT/match读取。

execution.py修复Stage A/B原异常后finalize第二异常被吞掉的问题：预分配TerminalFinalizationFailure保留raw primary/terminal secondary，沿原异常传播，状态INCOMPLETE_RESOURCE且一次终态尝试，不称durable成功。新增linux_child_exit.py是优先级1中的原生pidfd wait/reap/status消费子原语，包含一次reap/owned-FD close和限时失败处理；没有numeric-PID fallback，不签receipt。独立静态复核提出的cleanup deadline及失败分派两个P2已修补。

九文件限定独立规范／质量静态复审未发现剩余范围P1/P2，均未签正式review ID。退出子原语没有生产调用者、原始spawn/pidfd_open/birth/deadline来源；UID/namespace/IPC、全部backing创建删除、逐role GT撤销和全写路径仍缺，child_exit_attestation=NOT_ATTESTED/history_complete=False。production_runner三个native装配入口及StageB生产GT phase继续拒绝；没有把caller PID/deadline、schema/HMAC或hash清单当原生授权。不能称完整phase-worker或路线二生产链已实现。

当前工作集83文件、2096023逻辑字节、mapping SHA256 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93；55个生产Python文件仅AST，2个native C/H文本hash，26个历史测试仅hash。它是源码追踪，非source/runtime冻结；本轮未新增／运行测试、未import项目、未启动WSL、未编译／链接／装载／调用helper或启动生产组件，未打开GT view，未创建正式image/volume/study/ledger/lock。原dirty/staged/untracked保留未提交。

只读Windows核对显示当前token无提升权限，候选E:/Route2Dedicated及carrier不存在、只有既有共享Ubuntu22.04注册；本轮未取得新的Linux正式对象stat。缺口不是仅管理员权限：固定安装path-map/phase-worker及全写路径、pre-Python/pre-spawn原始clock与认证QPC transport、第一次dlopen/constructor前完整readonly解释器/stdlib/PE/ELF/native/helper身份、terminal后的签名close/exit join/原始cgroup清场/durable外部墙钟、专用三层实体cap/baseline/容量/余额和全部准备／控制／外部资源预算、完整新版跨OS数值／独立正式复审仍未闭合。

保留原负责人决定：Windows owner可信、WSL2隔离；创建前guest FS及VHDX所在实际Windows实体卷各≥8GiB，carrier没有第三项8GiB floor但须独立增长／收尾reserve；1200/3600/900秒和原额度内60秒收尾，C=min(4GiB,floor(3×启动可用RAM/5))、AS=C/2、swap=0、CPU=200%、TasksMax=2含controller；专用可强制实体边界，D_A=2GiB严格上界V2。Ubuntu22.04/glibc2.35＋独立复审冻结helper保留，编译／ABI及启动控制费用UNKNOWN_NOT_ZERO；20/32/34GiB、控制64/16MiB和atol/rtol候选仍待完整证据及复审后负责人最终绑定。新增投影／IPC／pidfd消费／异常保存也需真实预算，不能计零。

完整A+B最小条件卡仅在上述原review更新一次，状态继续APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。无合法科学结果，COMPLETE与质量门通过仍分开；Route3 v1-003合法COMPLETE／四门FAIL保持，不重跑，gap=0仍由路线二覆盖。负责人提供合法路线二结果前不启动任何架构方向。

##### 2026-10-07 全权限续行：提升能力实测与实体边界可行性门

负责人已明确给予全权限，要求补齐缺口至合法A+B及最终科学结论；已记录继续准备／实施／部署复审和条件闭合后合法执行的授权意图，不重复申请已有继续工作权限。实际完整身份、预算、正式复审及可消费准入绑定仍须闭合，候选额度不因此变成最终绑定，原授权提示／申请卡不改。

本轮实测管理执行方式取得进展：原主token非提升、管理员组deny-only；一次RunAs/Hidden只读UAC probe经同用户ACL named pipe返回，2026-10-07T09:34:08.5649578Z PID33896报告ElevatedAdmin=true，SeManageVolumePrivilege存在但Disabled。未启用特权或调用存储创建／attach API；probe wall=7128ms仅为该准备过程，完整CPU/RAM/task/bytes费用UNKNOWN_NOT_ZERO。09:41:24Z复核probe已退出、主token仍非提升；不是已安装broker或held执行lease。

独立只读后端复审无正式ID：Windows11 Home／缺VHD cmdlet不证明WSL原则上不可行；当前专用目录／carrier仍缺，唯一共享Ubuntu22.04 Stopped，本轮未启动WSL。尚未证明包含外层NTFS及C/E registry/eventlog/temp等全部宿主归属写入的per-study native hard cap；固定32GiB carrier、整卷free、SID quota、HMAC、时点sampler不代证。已发出保持原约束提供受控执行实例／允许提出计费边界调整后复审的环境路线选择；回答和实际证据未到前不执行依赖它的正式部署。

SPIKE FIRST预检、官方来源、实际提升／费用及完整条件卡差项统一记[原review同名最新修订](../../decisions/2026-09-27-route2-design-review.md)。生产装配与全写路径／GT历史、原始双时钟、readonly加载身份、terminal后独立外部验收、三层actual容量余额、全部费用、新数值／完整正式复审缺项延续；原科学协议、两个8GiB及carrier独立reserve、20 GT-backed＋GT-free pooled和最终matched-GT报告保持。

源码工作集未变：83文件／2096023B，mapping SHA256 6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93；55生产Python仅AST，2 C/H与26历史测试只hash。未新增／运行测试、未import项目、未启动WSL或生产、未创建正式image/volume/study/ledger/lock、未读取GT、未编译装载helper，原改动与staged项保留未提交。

准备视图仍PREPARED_UNREVIEWED；负责人续行授权意图已收到，但可消费A+B准入未形成、FROZEN_ADMISSION=None；Stage A/B均未合法运行；路线二无合法结果。完整review仍route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL，条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED（表示冻结准入未绑定，不表示负责人未授权继续推进）。Route3 v1-003 COMPLETE／四门FAIL及后续架构限制保持。


##### 2026-10-07 环境路线已选择：保留原约束的受控 Windows＋WSL2

负责人选择“保持原约束，提供具备完整硬边界的受控 Windows 执行实例（继续 WSL2）”，替代上一节待答状态；不调整计费边界，不重复申请全权限续行。实例名称／端点／provider及内存、磁盘上限尚未提供，已请求实际资源信息，不能由授权或候选额度推定。

本机常见虚拟化命令／安装位置盘点未发现可用provider或现有受控实例；这是限定发现，不证明WSL原则上不可行。Windows VM内的WSL2还须实际nested virtualization支持。独立VM不自动覆盖系统卷、registry/eventlog/temp/pagefile或外层provider／observer归属写入，仍需原生可强制边界及完整费用事实。具体盘点、官方来源、条件卡差项见[原review本日环境路线最新追加](../../decisions/2026-09-27-route2-design-review.md)，部署顺序见原WSL计划本日追加。

本次没有新增生产实现、测试、项目import、guest/helper/production运行、GT读取或正式对象创建。83文件源码工作集不变；PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B未合法运行、路线二无合法结果及完整FAIL-001保持，条件卡仍APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。原科学变量、成功门、资源／准入要求及Route3限制不变，原授权提示／卡保持不改。


##### 2026-10-07 本机 E＋WSL／10GiB上限的最新边界

负责人已说明实例未创建、只用本机E盘及WSL、磁盘额度不超过10GiB，继续全权限推进至执行agent可启动路线二。资源来源已有答复，不再等待远程实例或重复权限申请。10GiB=10737418240B按本次全归属部署峰值上限保守处理；旧20/32/34GiB具体方案不能用于本轮创建，只保留历史记录，不把新上限当作完整预算seal。

实际只读对象核对及一次独立复审详见[原review本日10GiB最新追加](../../decisions/2026-09-27-route2-design-review.md)。当前唯一Ubuntu的VHDX仍在C，E专用对象未创建；本机全宿主归属写入native硬cap尚未提供，生产装配／QPC等入口仍拒绝。两个创建前8GiB free门不重复相加，carrier无第三项门，study image仍同一2→4GiB；新minimal部署是否能在10GiB内满足全部baseline／增长／收尾UNKNOWN，未证明普遍算术不可行。不能用VHD长度、SID quota、共享free或布尔／seal字段代证全部边界。

当前本机配置合法部署预检NO-GO，非科学结论。原所有隔离、计量、20 GT-backed＋GT-free pooled、最终matched-GT、数值／完整review和失败验收要求保留。83文件源码不变，本轮仅原文档状态及只读静态核对，无测试、project import、WSL/helper/production运行或GT读取、正式对象创建。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001、Stage A/B未合法运行和无合法结果保持；条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED不变。原授权提示／卡、所有既有改动及Route3限制保留。

原review同节末列出未采用的具体合同变更供负责人决定：10GiB native cap仅限完整专用载体；卷外Windows系统副作用单独计量／预算／复审，失去原全部宿主归属native cap与全物理增量≤10GiB保证。此前“全权限”不自动允许该变更；未答复前继续原合同，所有准入拒绝保持。即使负责人同意，也须重新完整复审及实际容量／生产证据闭合后才可开启A+B。


##### 2026-10-07 三项证明口径补充

负责人询问的三点分别要求：完整可达写路径受实际OS硬边界约束的结构与运行证据；固定生产path-map/worker/QPC及完整退出调用链的真实安装/运行/独立正式复审；新target在≤10GiB下的三层capacity/allocated baseline/峰值/收尾/余额事实。具体方法、计费不重复、guest若≤10GiB则创建前baseline≤2GiB及两个8GiB门，见[原review本日三项证明口径](../../decisions/2026-09-27-route2-design-review.md)。须先绑定准备边界与预算再实施设施验收；无需偷跑Stage A取得容量证明。此询问不等于同意原资源合同变更，本轮无验收执行、准入或状态改变。

##### 2026-10-07 顺序执行的第一项机制核查（未闭合）

按负责人要求先作本机实际provider/系统backing只读盘点与一次限定独立复审；原始查询事实、官方语义和本轮一次完整A+B条件卡缺项见[原review本日第一项机制核查](../../decisions/2026-09-27-route2-design-review.md)。本地本日／UTC 2026-10-08：HCS组件确实存在，wcifs/bindflt等驱动Running，不应由无Hyper-V管理cmdlet推导HCS不存在。WSLService/vmcompute属LocalSystem；hive/evtx在C、pagefile在D、TEMP涉及C/E；固定E载体不能单凭容量覆盖这些作者。共享pagefile原值不是study物理增量，不全部计入也不直接否证10GiB。

新RunAs只读盘点返回用户取消、exit2，未取得新提升或fltmc实例清单；原提升成功记录保持，但不复用旧token/PID。quota查询0行不是全部quota关闭证明；组件/驱动状态也不是已配置受限compute system。独立复审第一项未关闭，无正式ID：缺从准备至清理覆盖全部归属系统作者和承载对象、在首次分配前强制跨C/D/E≤10737418240B的actual producer。Job写入通知/rate和局部HCS/重定向边界不能代全-host allocated cap；FSRM目录usage包括metadata，须与NTFS SID quota定义区分，当前Home未取得可消费FSRM provider。

当前严格合同下合法部署仍NO-GO（ENVIRONMENT＋IMPLEMENTATION，10GiB容量UNKNOWN），不普遍否证Windows/WSL或10GiB；既有源码缺口不是新回归。第二项固定path-map/worker/QPC及全history、pre-constructor readonly闭包、独立close/exit等未实施；第三项新target actual baseline/容量/保留峰值/cleanup及全准备/控制/外部费用缺。第一项未闭合，未创建target或执行第二、三项部署验收，本轮无新的生产源码实现。

carrier-only合同差异未采用；顺序指令不改变原全部宿主hard cap。原两个8GiB、carrier独立reserve、同image2→4GiB、时限/C/AS/swap/CPU/tasks、Ubuntu22.04/glibc2.35/helper及20 GT-backed＋GT-free pooled/最终matched-GT科学门保持。83文件mapping未变，原限定静态结论仅继承，不构成完整freeze/PASS。本轮仅原三文档追加，无新增/运行测试、项目import、WSL/helper/production/Stage/GT或正式对象操作；原dirty/staged/untracked、11项staged及授权卡/提示保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、无合法A/B或Route2结果、完整FAIL-001及APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；负责人续行意图已授权，可消费准入尚未形成。Route3及后续架构限制不变。


##### 2026-10-08 接受本机三项建议后的现行范围与资源预估

负责人明确采用三项建议并开始执行：10GiB是估计，不是磁盘硬上限；主要新增资源在E，其他盘少数；任务总RAM≤16GiB、VRAM≤8GiB，随后选定非E新增合计512MiB（含停止清理）。因此旧“全Windows可归属物理增量≤10GiB且全部作者受per-study native cap”的NO-GO为历史，不再把carrier-only差异写成未答复。E专用carrier内完整guest/准备/控制/研究/失败/收尾仍须真实原生硬边界；卷外Windows系统副作用改为独立计量、预算、超额拒绝和独立复审，不虚构原生保证。

原科学变量、两项8GiB、同study2→4GiB、1200/3600/900含60秒、C=min(4GiB,floor(3×首次Linux可用RAM/5))、AS=C/2、swap0、CPU200%、TasksMax2含controller与GT合同全部保持。16GiB不扩大study C；CPU verifier预计新增VRAM0，但实际dxg拒绝及峰值需验收。Windows只读样本物理RAM16890322944B/free3056592KiB不代Linux首次样本；nvidia-smi总8151MiB/used2587/free5313为共享时点值。

只stat和读取登记元数据：prepared inputs2644303938B、登记unique cache240384603B、scores172155149B；加历史venv348519927B/13wheel79270066B/原83文件source2096023B，已知非study子集3486729706B=3.247270GiB，加同study最大4为7.247270GiB，不是OS/runtime完整baseline或peak。均来自E已有对象，不读GT payload、NPZ数组或跑Stage。官方WSL jammy压缩rootfs341130963B/562包不是安装体积；45秒限定archive流统计未完整、未提取。完整原始事实与来源及限定独立资源核查见原review“2026-10-08负责人采用本机三项推进建议”。

待最终绑定的保守准备建议：20GiB guest（usable≥19、baseline≤8、future6、cleanup1）、24GiB carrier（usable≥23、实际完整baseline≤22、future/cleanup各128MiB）、E新增预留30GiB，规划约28–30GiB；不是实际峰值保证。inner VHDX AllocationSize/header必须实际计入，carrier已计整物理容器后不重复叠加内部guest/study。非E active384+stop/cleanup128MiB；真实完整计量、异步及采样余量和提前stop仍缺。guest前门另取同invocation8GiB，carrier无第三8GiB但独立增长/cleanup成立。

非study准备候选4GiB RAM/4 tasks/200% CPU/1800秒；显式外部observer/helper/launcher/bridge候选512MiB RAM/4 tasks/100% CPU/6000秒（1800+3600+600），不得延长原study门。已列进程保守和8.5GiB不是whole-task证据；WSL VM/kernel/service/IPC/cache等仍UNKNOWN_NOT_ZERO。C:/Users/Fancy/.wslconfig不存在未改，guest swap0不能外推VM swap/pagefile=0。上述条件算术经限定独立核查无硬矛盾，无正式ID；新具体数值、64/16MiB控制、完整预算和数值容差仍待实际证据及负责人最终绑定。

本轮先实施真实原生child lifecycle源组件，范围linux_child_launch.py、phase_worker_entry.py、native/route2_phase_spawn.c/.h与必要linux_child_exit.py衔接；child FS只读、有界IPC、原始pidfd/UID/namespace/FD/exec/exit，backing唯一父作者history需真实生产者，不能用扫目录或caller callback/receipt/HMAC替代。实施及限定独立复审结果另在原三文档追加，不据此解除production_runner装配/双时钟/readonly/close-exit等缺口。

PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001、无合法A/B或Route2结果保持。授权卡/提示不改、不新交接包；无正式对象/GT/Stage/helper运行或新增/运行测试。Route3 v1-003 COMPLETE/四门FAIL与合法Route2结果前不启动后续架构方向保持。


##### 2026-10-08 准备容量与全局WSL配置已获负责人绑定

负责人明确采用E新增30GiB无GT准备预留（24GiB carrier含20GiB guest、载体外6GiB；actual guest baseline≤8GiB否则拒绝study）及非E新增512MiB含停止清理。30GiB准备容量绑定已闭合；任务总RAM16GiB/VRAM8GiB、原study C/AS/swap/CPU/tasks/时限及科学协议保持。实际完整baseline/增长/费用/advance-stop生产者未形成，准备绑定不是实验准入。

按负责人精确答复，只以CreateNew新建C:/Users/Fancy/.wslconfig：`[wsl2]`、`memory=8GB`、`swap=0`、`processors=2`、`guiApplications=false`。65B/无BOM/CRLF，SHA256 a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5；held-file AllocationSize72/EOF65只代表该文件，不含全C卷系统副作用。未启动WSL VM或改发行版数据，尚非实际VM应用证据。原生child限定规范复审发现并修复NPROC零限与ambient UID65534的P2，修订后无范围P1/P2；质量复审尚在进行，无正式ID、完整review PASS或准入。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B未合法运行、无合法结果及完整FAIL-001保持；详见原review同日追加。


##### 2026-10-08 原生生产源组件限定复审收尾及完整A+B条件卡更新

三个源组件已按最终hash完成独立规范及独立质量静态复审，无剩余限定范围P1/P2，无正式review ID/完整review PASS：linux_child_launch.py／phase_worker_entry.py／native/route2_phase_spawn.c/.h及linux_child_exit.py原始clone3/pidfd、readonly namespace/UID/IPC/exec与wait/reap/失败关闭；windows_preparation_job.py原子Job出生关联、原handle wait/终止/一次关闭及primary/secondary；linux_gt_history.py固定lib/route2/mount_helper.so loader及恰好四处调用，真实40-byte ABI/namespaced exports、原owner缓存与失败revoke。原科学StageA/B、最终matched-GT和finalize双异常修补未改变。详见原review“2026-10-08生产源组件收尾”最终七文件hash和14项完整卡。

重要更正：helper10秒是合作式读取/调用前后检查，计入原1200/3600额度；不能中断同步dlopen/constructor/describe，原armed kernel deadlines、60秒margin和全安装/外部quarantine要求不变。完整readonly解释器/stdlib/project/native/transitive加载边界必须先于整个project/ctypes import；局部loader只在自身CDLL前调用现有安装门，门仍拒绝。未编译、链接、装载、describe或调用任一C/H，未证明ABI或sandbox实际运行。

负责人已绑定E30GiB准备预留（24 carrier含20 guest、E外部6、guest actual baseline≤8否则拒绝study）及nonE新增512MiB含停止清理；16GiB总RAM/8GiB VRAM、原study预算方法保持。仅.wslconfig已按授权创建并hash复核，不是VM实际应用证据。旧全宿主native≤10GiB不再是当前要求；E载体内仍须真实硬边界，载体外真实计量/预算/提前停止。其他控制/准备/外部额度及数值容差继续候选，完整actual baseline/peak/history/费用仍UNKNOWN_NOT_ZERO。

最终88文件/2202343逻辑B、58生产Python仅AST/4native文本/26历史测试仅hash，工作集mapping740afc4263efa095f5e510ba799fe1b608b3b7e9c90f4fa663a584d6a668ff3a，仅源码追踪不freeze。重构原83文件map6917f020ad3ee5895b8717de0db2ec8e0a3e2bde2df917e99f1c07b44b735b93精确一致、原index及三文档prefix/授权卡/提示保留。2026-10-08T15:47:55Z E:/Route2Dedicated仍不存在，当前token非提升、仅既有Ubuntu22.04 Stopped/WSL2。完整prep部署creator、三层实际baseline/native cap、非E在途/stop全计量、固定role/path-map/phase-root历史与runner、原始QPC transport、pre-Python加载闭包、terminal后签名退出/清场/durable外部墙钟及全正式review/冻结仍缺；不能说只缺管理员权限。

完整A+B条件卡本轮已在原review更新一次：APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。负责人续行意图已授，FROZEN_ADMISSION=None/准备视图PREPARED_UNREVIEWED/Stage A/B未合法运行/无合法Route2结果及完整FAIL-001均保持。未新增/运行测试、项目import、guest/helper/生产/GT执行或创建正式image/volume/study/ledger/lock；未提交/reset/delete/改原授权卡，新交接包没有。Route3及合法Route2结果前不启动后续架构约束保持。


##### 2026-10-09 固定phase publisher与metadata v2限定源码修复收尾

沿负责人续行及“先修复问题”指示，原phase publisher已形成真实cached helper的open_tree/mount_setattr/move_mount/正常umount源码，只发布当前唯一grant的GT及outer-only历史match两个固定inputs；连接原owner/history/closure/quiescence，失败poison并保留primary/secondary。没有创建/复制/删除backing，没有实际安装、helper加载或GT读取。完成独立SPEC→QUALITY，3个publisher P2修订后无剩余限定P1/P2，无正式ID；完整phase树/所有backing history/readonly runtime不由这个input substrate检查证明。

metadata v2固定四文件native FD/KCMP/read-only mount/raw-pin-before-JSON加载器已完成；保留v1 schema/domain/parser/caps/API，新增v2独立domain/≤1MiB envelope/fixed basename、role/map各16MiB和单次bounded解析/retained data-only map。四个限定P2闭合：protected regular实体别名；每实际read/pread含proc/EOF必须在调用前按joint48MiB remaining裁剪并先计账；临时close入口错误不降级原primary；JSON/serialization/base64/dataclass及_after_blocking报告/检查入口同类primary/secondary保存。DIR aliases/独立mount合法，pure foreign validator不增加权限。成功cleanup＋原source/config/start/native连续性及共享failure buffer健康后才private installation。Final production_metadata.py 88909B/1693行/SHA15dc4b1c91b48aafbfb53645de8bde89a6298dcb1d35e4e0e69ad4e13ad61ea1；fresh独立SPEC和QUALITY均无剩余限定P1/P2，无正式review或准入PASS。原10秒仅合作式window，实际耗时/RSS/完整map/inst/native都未测。

本次完整14项A+B条件卡只在原review“2026-10-09整合后续”更新一次，状态APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。E30GiB、nonE512MiB超额前停止、RAM16/VRAM8、原study时限/C/AS/swap/CPU/tasks及所有科学门保持；nonE改monitor并接受在途overshoot的旧选择没有明确答复，不据继续消息改变合同。07:57UTC实际target仍不存在、当前非提升、pagefile自动管理、.wslconfig未变，不是实际部署/VM应用证据。

仍缺directory map/role publisher、guard.start前early nonGT owner、固定runner三入口、READY后父实际kernel观察与成功原始outcome、完整原始clock/QPC/readonly构造前闭包、terminal后签名exit/清场/外墙钟，以及专用实体三层实际容量/余额/全费用/提前停止、完整正式review/现版nested等价/冻结。前birth supervisor/entry只为已审待实施顺序，不是现成组件。既有Stage B/execution科学修补hash保持；无合法Stage A/B/Route2结果，Route3 COMPLETE四FAIL和后续架构限制保持。

Fresh 89文件2294790逻辑B、59生产AST、4native文本、26历史测试仅hash；mapping06622d75994ea649c61e9462410f1bad2cb2563a53ec6034f1bbb6c8db430ac2仅源码追踪，非完整freeze。原index/授权卡/提示hash保持，原三文档仅追加。未新增或运行测试/project import/nativecompile/load/call/WSL/GTpayload/production/Stage/正式对象，未commit/reset/delete。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None及完整reviewFAIL-001保持。

### 2026-10-09 整合后续：phase-child内核观察与一次outcome源码收尾

沿原计划实际新增linux_phase_child_observation.py并接入linux_child_launch.py和原fixed publisher；必要parent AF_NETLINK属性加入linux_enforcement.py，旧worker仍AF_UNIX及原C seccomp限制。父在permit前从原held pidfd/proc/nsfs/cgroup/root/input/FD/kernel UNIX_DIAG读取真实identity/隔离/成员/上限/IPC peer，先完成原durable history再permit；原出生/READY/native状态/wait-reap/onceclose/scientific result强留，原owner/current batch仅一次消费成功outcome。当前均是生产者源码，没有actual调用或完整runner装配。

独立审查修补了失败保存/cleanup入口及安装成功登记顺序；QUALITY确认的最终六cgroup control再读和自身wrapper循环存槽亦已修补。限定SPEC→QUALITY：fresh独立LIMITED SPEC及LIMITED QUALITY均未发现剩余受影响范围P1/P2，无正式ID。准确4文件hash、60生产AST／90文件mapping cdfb4bc3dc9a54adabeb8c21f2f7fef2ace2d880991a7dd7ec8b421286283496及本轮唯一完整14项A+B最小条件卡见原review“2026-10-09 整合后续：phase-child原始内核观察、一次outcome及独立复核”。其他科学源码和C/H未变，native未编译/链接/装载/调用；AST/hash不是runtime冻结或数值等价。

当前仍缺目录role/path-map/完整PhaseRunner与调用链、原once GT commitment-key issuer、全部backing生命周期及逐role/phase撤销、真实专用Windows/WSL实体与三层baseline/余额/全费用、原始Windows QPC及Linux prebirth t0/单次M0、preconstructor完整readonly依赖、terminal签名exit/cgroup/最终外墙钟、完整现版nested等价与正式review。不是“只缺提升权限”，不靠HMAC/callback/schema/hash赋予事实。nonE512MiB严格超额前停止仍保留；此前“少量在途超额”已纠正为上界未知，待负责人明确选择监控口径才可改变，当前尚无明确答复。

准备E30GiB/RAM16GiB/VRAM8GiB、1200/3600/900含60、C/AS/swap/CPU/Tasks2、两项8GiB、D_A2GiB V2和20+1/pooled GT reads0不变。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED及无合法Stage A/B/路线二结果保持；Route3合法COMPLETE／四门FAIL不重跑。仅原三文档追加，授权提示/卡不改；未tests/import/native/WSL/GT/生产/Stage/正式对象/Git mutation。


### 2026-10-09 nonE监控预算负责人答复与原science key生产范围

负责人明确答复“采用监控预算并接受上界未知的在途超额，继续工作”。nonE新增512MiB从严格超额前停止改为监控预算：实际observer须提前预警、停止新增工作、计入停止/收尾及可见增长，并记录采样/在途/系统共享作者的遗漏和超额；超额上界仍UNKNOWN，不能保证很小或改称per-study实体硬限。这项是明确资源口径变更，不是重问访问权限。先前384MiB active+128MiB收尾为规划分配，实际计量/阈值/停止执行者仍待实现和复审。既有pagefile分配及共享Ubuntu baseline不能计成任务新增；无法归属的成本保留UNKNOWN_NOT_ZERO。

仅此nonE口径变更，E30GiB准备预留（24carrier含20guest、外E6、guest实际baseline≤8）、whole RAM16GiB/VRAM8GiB、Windows owner可信/WSL2/Ubuntu22.04/glibc2.35、两项8GiB、1200/3600/900含60、C/AS/swap0/CPU200%/Tasks2、D_A2GiB V2及20+1/pooledGTreads0均保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整route2-ab-full-implementation-review-2026-09-29-FAIL-001/FAIL、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。负责人续行意图已授，实际完整冻结准入尚未形成。

按已批准的controller-only science key/固定phase-worker设计，下一独立生产源码范围是补齐原owner的once GT commitment key生产者及原payload绑定。当前linux_phase_publication._phase_launch_payload明确记录issuer缺失，codec的32–64B caller key只是科学数据。由同一健康的原GT owner/current grant/publisher batch/parent PID与thread、原startup/ledger/绝对clock下调用系统getrandom取得32B；一轮producer invocation先消费再调用，raw返回先强留后校验/历史/格式化，短返回、EAGAIN/ENOSYS及任何原事实缺失直接拒绝并保留primary/secondary，不fallback、不重新发key。相同invocation后续phase沿同一原对象复用并核payload key；科学key不授GT或native权限，不承诺完整payload freeze。先前helper C/H和科学操作/算法不改，完整runner/installation拒绝门保留。Python wrapper内部可能处理EINTR，不能把一次Python producer调用宣传为单次底层syscall实测。接口语义来自[Python3.10 os](https://docs.python.org/3.10/library/os.html#os.getrandom)及[Linux getrandom](https://man7.org/linux/man-pages/man2/getrandom.2.html)，不是本机目标功能/费用证据。

仅在原三文档追加；本unit实施linux_gt_history/linux_phase_publication及必要private源模块，先原owner/clock/作用域核对→一次实际producer→strong raw→原durable历史→原payload精确science key绑定。费用未知不能计零，实际专用对象/三层baseline/全部费用、原始双时钟/readonly闭包、role/path-map/完整runner/退出/全review等仍缺；本轮不执行helper/生产/测试或Stage。


### 2026-10-09 原once key限定源码复审及下一固定phase执行器

原GT owner的实际系统once key producer已写入两文件并经fresh独立LIMITED SPEC→QUALITY，无剩余限定P1/P2；原payload核同一32B key，失败强留raw primary/secondary、poison/no reissue，后续phase复用。原durable started-before-call/finished-before-use、原clock/额度和private snapshot/closure连续性保持。原GT/mount/native权力不来自key或fingerprint，实际producer未调用；完整source/runtime freeze和费用仍缺。准确hash、90文件/60AST和宿主共享pagefile变化见原review本日“once science key源码闭合及固定native phase事务接续”。

下一组件是原已批准的fixed native phase-worker事务及StageB调用：固定执行器绑定原bootstrap/guard/controller，同PID-thread；真正运行时必须有健康的原GT broker/publisher/registry/绝对clock。一次grant→实际publish→原key→原spawn及真实once outcome消费→unpublish→原broker revoke；StageB只接受该原事务中的实得结果/授权/撤销，不能再legacy record_gt_release/revoke。保留完整path-map/nested/installation/QPC拒绝；实例、hash、callback、布尔不制造missing部署事实。原private事务必须强留各实际返回、原primary/secondary和未退出/未撤销状态，失败不生成成功close/quarantine。科学算法/输出字段/额度、20+1与pooledGTreads0不变。

nonE512MiB监控预算/接受UNKNOWN上界在途超额已绑定；E30GiB/RAM16GiB/VRAM8GiB保持，其他候选及真实监控/部署/费用仍未最终闭合。只源码/AST/hash及fresh独立静态双审，不tests/import/native编译链接装载调用/WSL/GT/生产/Stage/正式对象。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001/完整卡BLOCKED NOT_APPROVAL_READY NOT_EXPERIMENT_AUTHORIZED，无合法Stage或Route2结果。仅原三文档追加，不改原授权卡或无关dirty/index，不提交或新交接包。

### 2026-10-09 固定phase事务SOURCE_ONLY双审及nonE监控源组件

原fixed-worker设计的五文件接续已完成：原bootstrap/controller/guard私有装配→真实installed原owner/clock/gate核验→broker唯一grant/release→publisher与原once科学key→原native launch/outcome一次消费→原ref fence及close/unpublish→broker一次revoke→StageB common科学/最终matched-GT检查→原事务一次durable接受。GT owner/snapshot/真正GT-free completehistory强留连续性；失败保留raw primary及所有实际secondary，无GT早停保留。fresh限定SPEC修两类异常入口P2后clean，fresh QUALITY也no remaining scoped P1/P2，均无正式ID/fullPASS；最终五文件准确hash及91文件/61AST map见原review本日固定事务收尾。完整role/path-map、nested/QPC/installation拒绝仍在。

nonE512MiB监控及上界未知在途超额接受是负责人已绑定决定。下一源码组件只实现原private Windows Job owner的固定C/D native采样/held实际GUID和原owner-QPC/raw/errors连续性、可见positive high-water/超额记录与原stop-new-work/owned cleanup接线；全卷free差值不是任务物理allocated bytes，系统/服务/pagefile漏采/抵消/在途成本保留UNKNOWN_NOT_ZERO。384MiB active/128MiB收尾只是规划、不是新增绑定或硬cap。新Job/child/resume及等待每次实际查验；收尾继续观察并保留异常，不跳过原once close，不宣称全WSL VM退出。仅private监控源模块+windows_preparation_job.py，完整readonly/pre-Python/worker gate继续拒绝，60/70秒只属旧private生命周期；全任务原生外部observer和whole资源仍须另外闭合。

只读metadata实际见C短窗free减少73728B、pagefile历史增长后回落及查询进程28–29线程；无法按任务归属或当峰值，不能用PowerShell observer对齐候选四task。当前PATH未见Windows C compiler/linker不等于工具链全不存在，专用目录/worker仍不存在。原E30GiB/RAM16GiB/VRAM8GiB和全部study科学/时限/GT协议不改。本轮无tests/import/native/WSL/GT/生产/Stage/正式对象/git变更；原授权卡提示与dirty/staged/untracked保留，完整14项卡最终仅原review更新，无新交接包。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001与三项BLOCKED状态保持，无合法路线二结果。

### 2026-10-09 剩余准备预算限定复审及最终绑定待决

原review同日“剩余候选预算限定复审及负责人最终绑定提案”已给具体六项提案：guest控制64MiB内计guest20、仅外部E的host控制16MiB内计E6；无GT准备及native编译/ABI统一RAM4GiB/CPU200%/TasksMax4/总wall1800s；外部observer/helper/launcher/bridge原scope统一RAM512MiB/CPU100%/TasksMax4/总wall6000s；上述时间均含60收尾、准备与study不并行，编译/ABI分类另计不新增额度；已绑定nonE512MiB MONITORED下384MiB stop-new-work+128MiB名义收尾；未来完整nested对称abs(a-b)≤1e-12+1e-10×max(abs(a),abs(b))及全部离散决定一致。fresh独立限定静态复审认为可提交负责人绑定，未发现提案自身新增P1/P2算术矛盾，无正式ID/fullPASS或运行授权。

这些是CAP/配置候选，不是实测费用/部署事实。64/16MiB不另加E30，.wslconfig/registry/eventlog/pagefile/WSL服务不迁入E账或计零；实际三层usable/AllocationSize/header/增长/余额及全费用须实证。原规划guest16≤19GiB usable、carrier22.25≤23GiB usable只为条件算术；两项8GiB不重复加支出，carrier无第三门。已列非并行RAM max(4,C)+0.5≤4.5不覆盖VM/kernel/service，不能证明whole16；PS28–29线程与Job四process/commit不能证明外部四task/RSS，方法不满足则拒绝。

负责人原先要求候选经复审后由负责人最终绑定，本提案仍待明确回答；不重问已绑定E30GiB/nonE512MiB MONITORED及UNKNOWN超额接受/wholeRAM16/VRAM8/WSL2等决定。未绑定完整准备边界/预算前仍不helper编译链接装载调用或生产启动；当前只SOURCE/AST/hash及独立静态复审、readonly元数据，原三文档追加/原卡提示与dirty/index保留。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED及无合法Stage/结论保持。完整14项卡只在本轮最终收尾更新一次。

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

### 2026-10-09 early metadata 目录实现、限定复审与 A+B 卡收尾

负责人已最终绑定前节列明的剩余数值限制。源码实际补上固定 `_load_native_path_map` factory、compact directory map-v2、protected metadata envelope-v2 与 early nonGT metadata 目录 owner/同 FD reader；v1保留，v2目录与leaf身份分开，不扩大16MiB map/48MiB联合、节点/FD/history或原clock额度。仅实际观测读取已存在的 `_METADATA/__study__`；不创建部署对象、不打开role/GT/historical payload，不接受caller controller或callback授予权限，未安装role publisher仍拒绝。

本轮独立 SPEC/QUALITY 分别找出的两个 P2 已修补：先核 exact type/original reference再比较公开schema/hash/closed/receipts；public map创建前固定独立原五标量快照，核完整原keys、字段值及固定derived alias，读取前/postconsumer/require_registered共享gate，失败清理仍持独立原资源和rawprimary/secondary。最终两项限定独立复审均无剩余范围P1/P2，SOURCE_ONLY，无正式full-review ID。逐注册whole-map gate的静态O(K×M)及alias导出实际费用/预算可执行性仍UNKNOWN；不得据此声称全生产可执行。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| `linux_gt_history.py` | 135672 / 2461 | `ff347728f96ecca83000b41ad0080ee20531472a0585b2dacc8709b158a2b781` |
| `linux_native_path_map.py` | 41431 / 749 | `d6238ac9d094c41df5201afefcd0787135d45526f97e7f769851cd45d688684e` |
| `path_map.py` | 34251 / 775 | `325df812111f88f78ea79cf3438bf553c1ea20194701df4e2f20a8fed41704ea` |
| `production_metadata.py` | 90339 / 1718 | `bbf83c9ba1c5da7451b86cfd1d13ca8357023503703ce7d9dacff64060859a48` |
| `production_runner.py` | 24343 / 421 | `bfe984b7014467b6ab805734b364efe94cae58fcf7c7c2fc026fc8aa9eb97a68` |

完整细节与本轮唯一更新的14项 A+B 最小条件卡见原 `docs/decisions/2026-09-27-route2-design-review.md` 的“2026-10-09 完整 A+B 最小条件卡（本轮收尾更新一次）”。六份源码修改/93文件追踪/63生产AST/4native文本/26测试仅hash/原index及授权文件保留均已核；没有新增/运行测试、project import、native编译/装载/helper、WSL、GT或Stage，没有创建正式image/volume/study/ledger/lock。工作集是源码追踪，非完整source/runtime冻结。

实际逐role目录发布器、全部backing创建删除及授权撤销、pre-Python/pre-spawn原Linux时钟与原WindowsQPC认证transport、完整readonly解释器/stdlib/PE/ELF/native/transitive加载前身份、terminal后签名close/exitjoin/rawcgroup清场与finaldurable外墙钟、专用实体部署/原生硬边界/三层actualbaseline及余额/全部原scope费用与执行方法、完整现版nested等价及正式复审均未闭合。原 `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍FAIL，准备PREPARED_UNREVIEWED、FROZEN_ADMISSION=None，APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；无合法Stage A/B及路线二结果。Route3 v1-003仍合法COMPLETE/四门FAIL，不重跑；只有负责人提供合法路线二结果后才讨论三架构最小验证。

### 2026-10-09 接续完整输入注册的受限批量覆盖实现

上一单元 five-source early metadata owner/reader 的独立 SPEC/QUALITY 已限定 SOURCE_ONLY 无剩余范围P1/P2，完整A+B卡已在原review本轮收尾更新一次，完整FAIL及运行拒绝仍保持。接续选择一个实际启动链组件：`RoleRegisteredPreparedInputs.__init__` 目前对全部role/cache逐项调用whole-map连续性gate，源码可确认O(K×M)；不得以未知实测费用关闭预算缺口。

实施仅限定 `path_map.py`、`linux_native_path_map.py`、`inputs.py`：加入只核metadata覆盖的固定受限batch入口，把输入注册已存在的同一身份序列一次提交；native批量前后仍核完整原keys/独立字段快照/固定derivedalias，以原retained不可变keys检查每项，先exact tuple/string类型，继承原map大小上界、不扩大原预算。每段检查原绝对clock/PID/thread/bootstrap/controller连续性，不返回中间权限、不授予IO、不触及GT或角色发布；legacy单项API和v1原语义保留。不能把该复杂度收敛称实际时间/峰值/费用已测或全生产可执行。保持注册顺序、重复项含义、savedscore科学变量及GT门。

一个实现者完成并停止写入后，独立SPEC再QUALITY静态复审；只有stdlib AST/hash，不新增/运行测试、project import、native编译/装载/helper/WSL/GT/生产/Stage，不创建正式image/volume/study/ledger/lock，不操作Git或无关文件。讨论/结果仅追加原三文档，原授权卡/prompt不改。最终SOURCE_ONLY结论和实际pins另追加；既有完整14项卡仍是当前准入缺项依据，数值已绑定、真实部署/运行/费用/完整正式review未知。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、FAIL-001/ APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

### 2026-10-09 输入注册受限批量覆盖限定双审收尾

继承前节三源计划，已实际实现原issued native map的metadata-only受限batch，启动输入注册同一原序身份一次提交，以原immutable keys覆盖、批量前后wholemap独立字段/keys/alias核对和每64项/整图段原clock连续性检查，将native源码扫描由O(K×M)收敛为O(K+M)。新行存储O(K)，真实峰值、耗时、费用仍UNKNOWN。

独立SPEC先确认legacy/v1重复身份回归，已仅修inputs当前模块 `_NATIVE_CONTEXT` 的is身份选择：native batch，legacy/plain原逐项循环；不凭schema/bool授权、不缓存初始None、不去重。native仍只在继承原M行界内接受重复项，实际完整v2注册K≤M须证，未扩大原caps。最终独立SPEC及新独立QUALITY均NO_REMAINING_SCOPED_P1_P2/SOURCE_ONLY，三源实际pins/AST匹配；原11函数current摘要独立重算匹配实现者saved-dirty before报告（非HEAD/main），不称独立访问before全文或runtime事实。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| `inputs.py` | 25365 / 545 | `ad0d5947e476975e5feaedbd2743088de07386c5eb74c1019d48b3129c96dc7c` |
| `linux_native_path_map.py` | 42629 / 773 | `a27ab491c278f021e0a5929b3dd6df12458911791b3a8abea48a6f168fd4360d` |
| `path_map.py` | 35528 / 796 | `db5661ef50af59d44b0cf3acc58daceca44da71bb93a7ebf9842982e397d5620` |

主审当前工作集93文件 / 2,644,404 logical bytes，63生产AST可解析、4native C/H仅文本/hash、26测试仅hash；SOURCE trace mapping `b7e36fce4e368dc87019d9641bb277023502708f7015fc212238521b51a9bb04`，序列化同前UTF8 compact JSON sorted keys/relative paths。测试hash mapping `03276135ecde7218157839fb6d9973ac15bb095654eee44a8f984b5aab1618c5`，index95行hash `2790745c981ce8dc419b08d133e9751549b8e300542aff1ddfdc717505f3ee7e`不变。相对本轮恢复基线仅7份生产源码改变（inputs、linux_gt_history、linux_native_path_map、path_map、production_metadata、production_runner、windows_non_e_monitor），不存在删除或native/test/source科学核心改动；原dirty/staged/untracked保留，无commit/stage/reset。源码追踪不称完整source/runtime冻结。

完整实现与限定复审细节追加在原review的“2026-10-09 完整输入注册批量覆盖源码与限定复审收尾”；本轮完整14项卡仍只有review中一次整卡更新，本追加补第3/9/13项source进展，真实部署/运行/费用/完整正式review缺项不关闭。无tests/project import/native编译链接装载/helper/WSL/GT/Stage/正式image-volume-study-ledger-lock，原授权卡/prompt与全部dirty/staged/untracked/index保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、FAIL-001仍FAIL，APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法路线二结果；Route3不重跑，三架构不启动。

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

### 2026-10-10 原 native GT broker directory-v2 metadata 限定双审收尾

按前节两源计划，已接续原 execution.install_original_gt_broker 到登记metadata的实际SOURCE调用断点：installer仅从同一healthy原early owner取得issued map/原manifest bytes对象；无owner仅legacy-v1 fallback，plain-v2及原owner失败/漂移/未完/active/closed继续拒绝。固定两leaf GT登记metadata以SAME FD hash/read/parse消费，4MiB在payload pread/hash前检查；普通metadata原公开参数/16MiB、joint48MiB、110 GT O_PATH及grant/revoke合同不变。

raw read/parse primary与postconsumer/stream/FD/outer qscope close secondary独立保留；实际PID/thread在consume/cleanup前核，先pop后close、失败不重试发号。SPEC首轮nested schema移出owned context的1个P2已补齐；最终同一独立SPEC与fresh独立QUALITY均NO_REMAINING_SCOPED_P1_P2/SOURCE_ONLY，无正式full-review ID或准入PASS。七protected函数及原_registry downstream/公开reader args的current AST独立重算匹配实现者saved-dirty-before摘要，不声称独立访问before全文。

| 文件 | bytes / 行 | SHA256 |
|---|---:|---|
| linux_native_path_map.py | 57790 / 1015 | c6b4c57437f87b5e8b695a747467100df2094d49240e6a1da1ecf4e104994bd2 |
| linux_gt_history.py | 138428 / 2496 | 1ca884d50b7e700c0fde4d30b82b755b26539f0b0008d832d6c982bd6988b143 |

主审101跟踪项中工作集93文件/2,662,321 logical bytes，63生产AST可解析、4native仅text/hash、26tests仅hash；相对本轮恢复仅两源码和原三文档追加改变，无新增/删除，native/test/requirements/auth/index/StageB matched-GT与execution双异常源码hash保持。原dirty/staged/untracked保留，无tests/test body/project import/native compile-link-load-call/WSL/GT payload/生产/Stage/正式image-volume-study-ledger-lock或Git mutation；这是SOURCE追踪而非完整冻结或runtime验证，实际成本不可计零。

完整实现细节及本轮唯一完整14项A+B条件卡见原review的2026-10-10同名收尾与条件卡。下一实际组件须提供独立immutable role source的creator/create-delete history，现.worker可写scratch的4096/256/nlink规则不能直接承接完整role输入；逐role publisher、nested、原QPC/prebirth、readonly加载前闭包、专用实体/三层baseline/预算执行方法、终态签名join/清场/finaldurable外墙钟及完整正式review继续缺失/UNKNOWN。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL；APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。负责人已绑定数值和续行决定沿用不重复询问；Route3合法COMPLETE/四门FAIL，不重跑、不启动三架构方向。

### 2026-10-10 adaptive-workflow 工程止损审阅（接续原最新修订）

科学机制和全部已绑定决定保持：Route2仍固定saved scores、模型/26D/阈值/decoder/matcher，仅严格正时间交叠对比300秒候选间隙；105 reference复现仅为未来合法Stage A任务。

本轮RESEARCH预检对实验执行架构给出REDESIGN收敛判断：当前原owner只拥有metadata读取，完整native role publisher/source creator/create-delete/不可写别名及phase/runtime加载闭包未闭合。唯一实现者限定追踪返回BLOCKED，零源码修改；不把新增schema/receipt/callback或.worker扩cap当实际producer，不制造新的SOURCE实现PASS。前两source pins一致，原限定SPEC/QUALITY SOURCE_ONLY结论继承。完整预检固定字段、因果分类和证据见原review同日“adaptive-workflow 工程审阅与逐role producer止损判断”。

最终目标仍是event F1≥0.66的深度学习模型；原设计先HGB基线、后比较时序表示。当前Route2仅候选几何与固定26D HGB验证，不能当作完成深度学习交付。引用既有合法报告：A1=.585086、A2-004=.623482、Route3v1-003=.5882352941；无新评价/Route2结果。41人重复开发的确认限制沿用。

下一可交付须明确完整实际部署/对象/预算/启动/失败/退出依赖，并形成一个真实creator/publisher的可独立实施SPEC；exact source backing和费用仍UNKNOWN，不凭target路径推定对象，不自动执行。WSL/Ubuntu22.04/glibc2.35、全部资源数值和负责人续行意图不重新讨论；本机E+WSL不可行尚未证实。当前只读专用E目标不存在、主token未提升，已注册WSL2仍在C:；.wslconfig文本不等于实际VM配置。

PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、route2-ab-full-implementation-review-2026-09-29-FAIL-001仍FAIL；APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，Stage A/B均未合法运行。原授权卡/提示不改，Route3不重跑，合法Route2结果前不自动启动三个模型架构方向；全部讨论只追加原三文档，不新建handoff。


### 2026-10-10 QUALITY P2 修订：新 SOURCE 收敛任务记录

原review同日“QUALITY P2 修订：独立预算的 SOURCE 收敛单元”已明确新任务负责人/root、8份准确source读取范围、20分钟新软预算、不同的“creator已存在但未接线”因果假设、区分性验收及UNKNOWN/BLOCKED停止条件；不沿用已结束两源/8分钟额度。该单元只读追踪，不授权部署/测试/生产，不扩cap或伪接线；所有原状态和本轮唯一完整A+B卡保持。


### 2026-10-10 独立预算准备creator追踪结果（SOURCE_ONLY）

review最新“独立预算 SOURCE 收敛结果”记录一次8源/20分钟内的追踪：Windows Job与readonly identity lease已有消费/生命周期SOURCE；LinuxInitialVolumeCreator确有正式study image OS操作SOURCE，但host/installation拒绝入口在其前，不能替代准备或role source creator。限定范围未找到既有可直接接线的role/phase creator；exact backing/创建删除/readonly别名/原authority及费用仍UNKNOWN。零源码修改、零实验，生产实施仍BLOCKED；不扩大为全机或WSL不可行。继承两metadata reader的原SOURCE_ONLY双审，不产生新组件或full-review PASS。唯一完整A+B卡沿用review本轮14项卡，所有状态与科学合同不变。


### 2026-10-10 本轮限定独立双审收尾

独立SPEC第二轮之后完成fresh独立QUALITY第二轮，均NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_REVIEW_ONLY；初审任务记录P2已关闭。事实与范围见review本轮“限定静态双审收尾”。本轮零生产源码修改，两metadata reader及原Stage B/finalize修补继承；只有原三文档追加，原授权卡不变。生产组件仍未补齐，完整实现review仍FAIL，SOURCE事实审阅不签完整实现或准入PASS；PREPARED_UNREVIEWED、FROZEN_ADMISSION=None及所有原阻塞状态保持。唯一完整A+B卡仍为本轮前节14项更新。


### 2026-10-10 执行架构收敛讨论第1节（未绑定提案）

负责人已要求进入creator→不可变输入→worker→原启动与退出的讨论；原review同名追加记录本轮新20分钟/八源静态范围、固定preflight、所有者链、两个输入物理方案及官方OS依据。建议先受限无GTprepare形成runtime/nonGT/phase-source实际部署，再由正式FrozenAdmission消费；runtime加载前边界、原Windows/Linux时钟及最终退出均有独立原OS所有者。publisher拟在原controller进程内，worker scratch保持原界，GT授权合同不变。

A为一次准备并整体封存nonGT role目录树，B为按role独立创建/封存/撤销；均仍是候选，需先凭非GTmetadata/stat核实际复制容量及原预算，具体backing尚未绑定。只读bind不等于整个source不可改；独立WSL发行版不等于VM退出。是否可提供独占WSL窗口已询问，回答待定/UNKNOWN。本节不签已同意的新布局、SOURCE/实现/实验PASS；原14项卡、PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL及全部阻塞状态保持，原科学合同与Route3终态不变。


第1节提案自核补充：A/B仅覆盖已合法分离、已登记的nonGT基础输入与readonly依赖；准备期不生成候选/26D衍生/模型/预测或评价。动态产物保持原Stage时序与既有交接合同，实际producer/冻结/别名/FD和全费用另核；静态bank封存不等于完整输入闭合，不默认新布局满足原D_A=2GiB及同image2→4GiB界，须在原界内证明。详见review第1节自核补充。


### 2026-10-10 架构讨论第2节追加：独占WSL已绑定，静态载体选择仍为提案

负责人回复“允许”，确认未来期间其他发行版不运行、收尾允许关闭整台WSL2 VM的独占窗口。该使用决定无需再问；实际独占/config应用/VM退出/QPC证据仍UNKNOWN。SOURCE/metadata只读限制没有解除，不能据此执行WSL、实际准备或Stage。

详见原design review同日“执行架构收敛讨论，第2节”。隔离stdlib仅登记metadata和nonGT leaf stat，未读取科学payload或验证其hash：105 role完整directory-v2需19894 alias（19684输入+105 reference×2 phase），不同基础路径1757、逻辑数据3026850159 bytes（2.82GiB）。逐alias复制文件数据7117668304 bytes；4KiB取整估算7161221120 bytes（6.67GiB），原8GiB baseline仅余1428713472 bytes（1.33GiB）用于其余费用。估算不含目标FS/runtime/control/reserve，actual baseline和全费用仍UNKNOWN_NOT_ZERO；A未证明NO-GO。

最大role为257 leaf，不能沿用.worker的256scan作为输入目录容器。B“基础源一次封存＋逐role独立只读快照”现为建议主线，尚未选择或获实施PASS。下一设计必须明确实际backing/creator、关闭全部写入口、原controller内publisher、worker真实退出后撤销/删除及history/clock归属；不新增常驻guest进程、不扩大cap。静态输入封存不代替未来科学产物producer；准备不提前做reference复现、候选/26D/模型/预测或GT评价。

本节task=route2-static-input-capacity-discussion-2，/root INLINE RESEARCH；新20分钟预算自UTC 2026-10-11 01:52:16，SOURCE读取限五项、metadata上界五项实读四项，具体hash/范围在原review。不新增源码、测试、正式对象、授权卡、交接包或完整A+B条件卡；后续组件保持单实现者停止→独立SPEC→fresh QUALITY。

PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、FAIL-001 FAIL及APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。无合法路线二结果，无完整冻结或正式复审PASS。

### 2026-10-10 B主线已选择：物理载体与原owner链细化提案

负责人选择并要求细化B；未来独占WSL窗口也已绑定。原design review最新“执行架构收敛第3节”给出/root单写的完整物理/正常失败生命周期提案及两advisor的12源事实，不重新讨论已有预算/科学/WSL决定。该细化仍供审阅，不是已安装或SOURCE组件PASS。

提案：独立封存唯一nonGT bank（约2.82GiB仅逻辑数据，进入原guest≤8GiB actual baseline）；controller内同步创建最多一个当前role磁盘ext4 generation，backing在study/.role-input，builder mount在study树外私有路径，固定consumer根/run/route2-input/roles/<SHA256(role_id)>不改alias/map对象。每generation保持原三个nonGT role phase的完整mapping集合；不默改phase子集。完整输入257leaf与.worker4096累计/256scan/nlink1分离，scratch cap不扩。generation data/tree/FS/历史/残留均内计原study2→4GiB及原clock，无新增容量或驻留daemon。

封存须真实create/allocate/copy/fsync/clean unmount/formatter wait-reap/RW引用关闭、全部写者和别名核清；首选细化inode immutable保护及readonly loop/dm-verity设备，root由原creator认证、actual table/dev/mount核对。保护flag或Merkle/hash回执各自都不足，未归属特权clear/writer/raw device能力即拒绝。角色reader必须same-FD hash→消费→后核→健康once-close，GT继续原broker。源文件SHA与设备Merkle root分开，不变科学内容。

SOURCE指出四断点：early native只核__study__ metadata而非全部role；v2 role open/lease仍拒绝；GT phase publisher不是nonGT byte-copy creator；early metadata实际mount与initial study拒绝所有/run/route2-input mount冲突。须以原healthy owner实际FD/identity交接收敛namespace门，不能删门或布尔放行。失败phase已poison不能normal revoke，必须原cleanup authority用真实pidfd/原deadline清场；任何引用、close/unmount/dm/loop/delete未知则保留残留及费用，阻止下一role和终态PASS。

优化只采用bank一次、单current generation、同role嵌套共享、完整map索引、固定小buffer、目录一次发布；生命周期次数R、全部copy/history/FS/RAM/原1200/3600/900秒费用仍UNKNOWN_NOT_ZERO。上游Microsoft5.15参考config启dm-verity/loop/ext4而未启fs-verity，不是本机config；不默认custom kernel或RAM快照可行。native种子、prepare合同、加载前边界、三层actual预算、原t0/M0/QPC、terminal/raw cgroup/服务与VM/finaldurable外QPC仍为独立真实缺项。

本节新30分钟预算UTC2026-10-11 03:24:34起，source限12项、两readonly advisor；本轮只原三文档append、不源码/测试/import/helper/WSL/GT/正式对象/Git操作。新细化设计按brainstorming供负责人审阅，后续才writing-plans及单实现者→SPEC→fresh QUALITY。完整A+B卡沿用原review唯一14项卡，不另建授权/交接/冻结。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL及APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；Route2零合法A/B，Route3v1-003合法COMPLETE/四门FAIL保持。

#### B细化最新收尾与顺序修订（2026-10-10）

原design review第3节最后自核修订为共同依据：data复制/持久化、构建FS正常卸载、formatter wait/reap及RW loop/FD真实终结后，持data O_RDONLY构建tree；tree持久化及RW引用全部健康一次关闭后才保护data/tree inode，再发行真实readonly loop/dm和role目录。清场先释放consumer/source mount及dm block/query FD，再核实际dm消失；loop held/query引用在association消失验收前释放，backing O_RDONLY及held parent可留至身份核清/clear/unlink。不能先封存空tree、先签设备消失或重用已消费FD。

独立SPEC已返回NO_REMAINING_SCOPED_P1_P2 / DESIGN_SOURCE_REVIEW_ONLY；随后fresh QUALITY因平台usage limit未完成，NOT_COMPLETED_USAGE_LIMIT / NO_QUALITY_VERDICT。此轮尚无完整双审结论，不用历史源码QUALITY或作者自核代替，也没有新生产组件PASS。原review收尾记录四次dispatch、03:48:30软阈值checkpoint、实际恢复05:16:00已超过03:54:34设计软截止；其后仅必要收尾，未知等待/工作/全归属费用不扣除或计零。12源码已有隔离AST/hash；404项保留核仅原三文档append、旧前缀/index保留，不是冻结。

下一步补齐fresh QUALITY并由负责人审阅本次具体written物理设计；按brainstorming关口后才writing-plans及SDD单实现者→SPEC→fresh QUALITY。B/独占WSL窗口及既有预算/科学协议不重问。bank/generation/全部writer与引用、actual预算/R/clock、启动退出和完整冻结仍UNKNOWN_NOT_ZERO；本机能力和E+WSL可行性均未签PASS/NO-GO。SOURCE源码、授权prompt/card保持原hash，无测试/import/GT/helper/WSL/生产/正式对象/Git操作。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED及零合法路线二A/B/结果不变。原唯一14项完整条件卡沿用，不新建卡或交接包。



### 2026-10-11 B completed architecture contract and SOURCE execution boundary

The latest original design review section “B architecture completion and component SOURCE plan” is the normative architecture for this candidate, including its native birth, physical accounting, pre-load closure, bank/generation, original owner handoff, worker/GT, failure and terminal requirements. The owner explicitly commissions this architecture and component plan now. Earlier statements postponing writing-plans are superseded only for this newly authorized document work; they do not waive fresh independent review or authorize execution.

**Selected B:** one sealed unique nonGT bank in original guest preparation/baseline; synchronous original-controller creation of at most one undeleted current role generation in study/.role-input/<monotonic-generation>/data.img + tree.img; private builder outside study mount tree; publish the whole clean readonly verified directory at the unchanged /run/route2-input/roles/<SHA256(role_id)>. Preserve original full-map bytes and objects, aliases and all stage_a_input/stage_a_reference/outer_control_candidates mappings. 1757 unique sources/2.818974GiB,19894 aliases/6.669407GiB4KiB data estimate,max257 leaves/max89.452081MiB logical role size remain static estimates, never allocation/cost PASS. .worker's4096 cumulative/256scan/nlink1 is separate and unchanged.

**Normal generation contract:** reserve/history before creation; actual allocated data, pinned formatter under Tasks2, copy/hash same FD, fsync/syncfs, clean unmount, formatter wait/reap, healthy RW loop/FD release, tree construction from data O_RDONLY while treeRW, tree fsync and all RW release, protect/check both inodes, actual readonly loop + dm create/load/resume/table verification with original authenticated Merkle root, clean ext4ro,noload,nosuid,nodev,noexec/private, whole-directory publication. No privileged clear/overwrite/raw alias escapes original trusted creator/cleanup ownership. Individual payload SHA is distinct from device root. Consumer hashes/seeks/reads/post-checks/closes the same O_RDONLY FD. Directory publication supplies actual directory mount and per-leaf file facts, not fabricated per-file mount receipts.

**Owner continuity contract:** native Windows owner originalQPC before Python/WSL/children and Linux native pre-controller/pre-Python original CLOCK_MONOTONIC/M0; bounded authenticated transport joining original nonce/QPC/boot/PID/start/ns/unit/cgroup/installed pins; sealed memfd plus charged O_EXCL replay claim; deadlines never reset. Every user execution dependency (PE/ELF loader/interpreter/stdlib/project/native/provider/transitive) is physically readonly before CreateProcess/exec/import/dlopen/initializer. Both study and observer closures are complete. Four existing native C/H receive separately guarded Windows seed/Linux native-start/device bridge targets; existing mount40-byte ABI remains unchanged. Compilation/ABI/load is not a SOURCE command.

Early metadata owner retains actual directory/ancestor/source/OFD/mount/namespace identities and privately hands them to the original study creator. The initial namespace gate admits only that same healthy original readonly metadata mount and 105 precreated unmounted role targets; rejects every foreign/drifted/role/worker mount. v2 open/lease dispatch routes only study metadata to metadata owner and current nonGT roles to actual original role publisher. It never accepts a caller controller/boolean factory. _require_native_nested_producers remains rejecting until all concrete creators/readers are installed and their original identities joined.

**Storage and resource contract:** E30=carrier24 inclguest20+externalE6; actualguestbaseline<=8; guestcontrol64 and hostcontrol16 are included (host onlyexternalE). Same-invocation guest backing FS and actual Windows physical volume carryingVHDX each>=8GiB before formal image; carrier only has its own reserve, no third8GiB floor. Main study2GiB strictcapacityV2 grows same image2→4GiB, not2+4. Role data/tree/FS/history/residue use that study physical capacity. Actual virtual size, FS usable blocks, allocated blocks, VHD headers, baseline/growth/cleanup and all writer scopes are separate proofs.

Preparation+compile/ABI remain4GiB/200%/4tasks-threads/1800s; external observer/helper/launcher/bridge512MiB/100%/4tasks-threads/6000s; both includecleanup60 and preparation does not overlap study. StudyC=min4GiB,floor3*M0/5),AS=C/2,swap0,200%,Tasks2 includingcontroller,1200/3600/900 includeexistingcleanup60. WholeRAM16/VRAM8 and allVM/kernel/services costs remainUNKNOWN_NOT_ZERO until fully attributable/enforced. A Windows Job only bounds its associated-process properties; process-count/committed-memory is not thread/RSS/VM proof. No exact complete VM/service/thread native hard-control primitive or last-owner post-exit durable kernel producer has yet been established. C00 is the first bounded source/official-API callpoint audit and preserves named rejection until concrete supported primitives exist; this is not a selected abstract complete-proof factory. Concrete native scope task must produce effective actual limits/association/accounting/stop evidence or VM_SERVICE_SCOPE_UNPROVEN before new work. .wslconfig8GB/swap0/2CPU/guiFalse text is not actual application. nonE512MONITORED/384visiblegrowth stop-new/128nominalcleanup/acceptedovershootupperUNKNOWN remain fixed.

**Worker/GT/cleanup contract:** exact readonly runtime/source/current role/released GT and historical row composition; only already approved scratch/log paths writable; no ambient tmp/cache/host/device/GPU/signing/backing FD. Native UID/GID65534, emptygroups/capabilities/private namespaces/IPC,originalpidfd/READY-permit/wait-reap/seccomp/resource facts are preserved. Phase grant/publish/outcome/drain/unpublish/revoke stays the one original broker sequence. Poisoned failures use an independent original cleanup authority installed before acquisition with original object registry/primary/deadline, not healthy normal revoke. It kills/waits/reaps original children, drains references, actually unpublishes, closes DM block/query references then removes/queries DM absence, closes loop holding/query references before association absence, verifies original backing/parent, clears only owned protection, unlinks/fsyncs. Consumed close numbers are never retried. Unknown retains residue/charges, blocks next generation/terminal PASS; VM exit is not file deletion.

**Terminal contract:** actual ledger/lock close -> original Linux signer native-close -> inactive unit/raw empty cgroup + controller exit witness -> Linux observer resource close/exit -> a different original charged Windows owner raw process-handle wait/exit and signed pair verification -> actual services/VM shutdown/backing observations -> fixed external-E durable anchor and final native QPC. Owner still alive after that QPC remains charged. Final original-owner exit/durable timing requires an independent native/kernel witness whose actual writer/resources are also in original scopes; kernel ETW ProcessStop alone is not flush/complete-scope proof. Absence returns OWNER_EXIT_JOIN_UNPROVEN and prevents external scope closure/admission. No uncharged new ancestor or signed self-exit receipt.

**R contract:** realoutermost path-map acquisition increments generation attempt counter; same-role/same-thread map nested depth is separate; loader nesting prohibition remains. Role revisits after release create new generations. Record all issued/failed/copied/published/unpublished/deleted generations and original deadlines. R is UNKNOWN_NOT_ZERO until its actual producer runs lawfully; neither105+105, lease callsite counts, static estimate norREADY is actual R. Root verified input.open_role/open_identity_index/reference generator and StageB revisits; exact topology completion is a separate later SOURCE inspection, not permission for scientific payload reads.

**Scientific invariant:** original105reference then105treatment;25fit attempts,25predict,65decode;20GT-backed eval +GT-free21st pooledaggregation;pooledGTreads0; fixedsaved scores/models/26D/.10,.25,.50/decoder600sec,min180/matcher; strict positive overlap alone versus300000msgap; numerical comparisonabs(a-b)<=1e-12+1e-10*max(abs(a),abs(b)), discrete exact. Preserve finalmatched-GT actual gains/losses and already repaired execution.finalize double-error behavior. Route2 diagnostic is not completed deep-learning eventF1>=.66 delivery.

The original plan now contains exact component paths/call sites/native interfaces/checkbox SOURCE steps/dependency DAG/static commands/Git path commits/review acceptance and conditional physical prerequisites. Initial independent source components may be authored after fresh candidate SPEC and distinct QUALITY approve their scoped plan. Native compile/link/load/call, actual installation/preparation, helper/WSL/GT/production/Stage/formal image-volume-ledger-lock objects remain blocked by actual prerequisite evidence and original authorization boundaries.

Status remains PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED; new candidate dual review is pending, not inherited. Route2legalA/B/results0;Route3v1-003legitimateCOMPLETE/four-gatesFAIL unchanged. Only the original review's single final fourteen-item table is the complete A+B update; this section is a contract, not another authorization card or handoff.


### 2026-10-11 SPEC round 1 clarification: conditional architecture and C00 stop

Fresh SPEC first pass finished READSTOPPED with two P2 findings. The original plan's “SPEC round1 errata” repairs full-index G and C00 eligibility; second-pass SPEC must finish before distinct fresh QUALITY. No clean review verdict is claimed.

Earlier “completed architecture” title/claims and broad SOURCE continuation are superseded by **conditional B architecture and SOURCE task plan**. Full architecture feasibility/native VM-service-thread/physical-cap/final-owner mechanisms are not complete. Current C00 result is NOT_AUDITED: C00 only. Unsupported/unselected/unproven VM_SERVICE_SCOPE, E_PHYSICAL_CAP or OWNER_EXIT primitive stops dependent C04–C12 SOURCE, including bank/generation/publisher/worker/GT/terminal/assembly. After complete C00 component dual review, only enumerated independent C01 interface/error/rejection declarations, C02 known Job/raw-identity/observation/rejection and C03 known native prebirth/preload-parser/transport-rejection SOURCE parts may continue. No undefined producer or full conditional stack is implemented even as SOURCE under that result. Review cannot make an unsupported prerequisite satisfied.

All required exact primitives must be supported and selected with concrete signature/owner/OS callpoint/scope/stop semantics, plus complete C00 dual review, before DAG SOURCE continuation. Installed/runtime facts remain UNKNOWN and execution permission remains unchanged.

Corrected G reads git ls-files --stage for exactly eleven unique original stage0 paths, full modes/full40-or64-hex object IDs, comparing complete rows before/after EACH exact-path component commit. Metadata only; no test bodies or Git operation by this author. No second full A+B card, authorization or handoff. All original scientific/budget/status invariants remain.


### 2026-10-11 最终限定双审收尾
/root/b_component_plan_spec_review 第二/最终轮及不同的 /root/b_component_plan_quality_review 均实际返回 NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_PLAN_REVIEW_ONLY、READSTOPPED；审查仅最新文档候选+errata，非实现/运行/完整架构 PASS。
C00=NOT_AUDITED，仅 C00 可执行 SOURCE 审查；unsupported/unselected/unproven 则依原 plan 权威表停止 C04–C12 even SOURCE，仅经 C00 组件双审后的已枚举独立 C01–C03 部分可续行。VM/service/thread hard control、physical E cap、final-owner durable witness 未闭合；原 full FAIL/FrozenAdmission=None/NOT_EXPERIMENT_AUTHORIZED 与零合法 A/B 不变，F1≥.66目标仍未交付。


### 2026-10-12 C00 clarification - factual audit complete, prerequisites unproven

C00=**AUDITED_UNPROVEN / DONE_WITH_CONCERNS / NO_SOURCE_DELTA**, with its fresh SPEC and distinct fresh QUALITY pending after author stop. The original plan's latest C00 audit supplies exact five-file SOURCE facts/hashes, API signatures/build requirements/raw failures/stop semantics, existing-versus-missing pre-birth callpoints and all required witness/writer cost scopes.

Job process count != actual thread count; committed memory != RSS/whole VM. Thread snapshots are observations. Generic HCS APIs do not select original WSL/service/kernel/thread ownership enforcement. Virtual size/full allocation/file allocation queries/per-user quotas do not select an all-writer physical cap. Process signal/ETW End is not post-exit durable flush. A final witness cannot sign its own final exit. Required complete primitives remain **VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN**. _prepare_fixed_worker and _require_host_control_boundary refusals remain unchanged. No producer/callback/schema/allow/success receipt is selected or implemented. Public support and local capability remain separate; all installed/runtime facts UNKNOWN, costs/counts UNKNOWN_NOT_ZERO, no global impossibility claim.

Authoritative eligibility is unchanged: incomplete C00 reviews -> C00 only; both complete with current blockers -> independent C01 interface/error/named rejection, C02 known Job/raw-original-identity/observation/rejection and C03 known prebirth/bounded preload parsing/transport rejection only. Recommended C01_DECLARATIONS_ONLY contains plain value/error/state/named-rejection and dormant v2 header/target declarations preserving v1, no registry/provider/success gate or whole C01 PASS. STOP dependent C04-C12 even SOURCE, including C11 witness and full assembly; no wrapper advertising an absent complete producer.

A future clean review is SOURCE_API_AUDIT_ONLY; no native execution/machine probe/preparation/WSL/GT/Stage/formal-object/experiment permission follows. PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / original full FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED, zero lawful Route2 results and fixed science remain. Original card/prompt unchanged. Only original3 appended; author stop=2026-10-12 10:56:37 UTC, READSTOPPED / WRITESTOPPED. Fresh SPEC then different fresh QUALITY remain root's next steps.


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

### 2026-10-12 三机制最新边界（限定文档复核待做）

规范性细化见[原review本轮唯一14门卡与三机制证据](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-boundary-20261012)。
新增 pinned WSL creator/GUID/config 顺序只证明公开 VM 部分；whole service/kernel/thread/费用 producer仍缺，installed version UNKNOWN。
新增 finite physical extent 仅条件设计；E30是预留，L_C实际物理backing/guest hosting FS双8GiB门与carrier reserve分开，所有metadata/overhead/control内计原24/20/6。
未选择layout/creator/formatter/全raw写者闭合；无磁盘操作，E_PHYSICAL_CAP_UNPROVEN保持。
windows_wall最后postflush QPC由活着的owner采样；它不是own-exit证明，也不是seal里已经落盘的最后采样。
final coordinator可继续存活、4tasks-threads范围、physical extent选择三个问题均PENDING；推荐不能作答复，acceptance后收费/写入边界不能填零。
VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN，完整机制NOT_COMPLETE/UNPROVEN，数值/科学/B/独占WSL决定不变。
C00 AUDITED_UNPROVEN；C01仅声明切片SOURCE双审完成，whole C01不完整；C02/C03 NOT_STARTED，仅原独立切片下一步合法，C04–C12 STOP even SOURCE。
PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/full FAIL001FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED；合法Route2结果0，F1≥.66仍open，Route3v1-003 COMPLETE/四门FAIL不重跑。
本轮SOURCE delta/运行期实验0；唯一原三文档append完成即STOP ALL WRITES，再fresh SPEC→不同fresh QUALITY；限定复核PENDING，不是full review/freeze/PASS。

### 2026-10-12 三机制限定文档复核收据

[原 review 实际双审与中断恢复收据](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-review-receipt-20261012)记录 SPEC UTC 12:23:56、不同 fresh QUALITY UTC 16:16:06 停止；二者均 NO_REMAINING_SCOPED_P1_P2 / CONDITIONAL_MECHANISM_DOCUMENT_REVIEW_ONLY，作者时点的 PENDING 仅在限定文档范围内收敛。
三项负责人选择仍 PENDING；真实机制仍 UNPROVEN，无完整实现/运行期/冻结/准入 PASS。root 只追加实际收据，并修复自身未提交收据的 stdin 编码问题；原数值/科学协议、全部拒绝状态及旧 prefix 保持。未启动 C02/C03 或任何受阻组件。

### 2026-10-12 三项负责人答复已绑定

[原 review 直接答复及边界](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-owner-decisions-20261012)：最终外部验收者可存活；4tasks-threads 约束应用执行组、基础设施完整计费；专用真实实体 extent 设计已选择。此前 PENDING 快照保留，答复只绑定设计，不是磁盘操作授权或 producer/部署/预算/准入 PASS。原数值/科学、三机制 UNPROVEN 和所有阻塞保持。

### 2026-10-12 Selected mechanism protocol delta (DOCUMENT ONLY)

Normative concrete ordering/callpoints and refusal rules are in [selected architecture](../../decisions/2026-09-27-route2-design-review.md#route2-selected-mechanism-architecture-20261012); the existing scientific protocol and complete14-gate card remain unchanged.
Physical storage retains actual L_C<24/L_X<6 with all metadata inside30, guest-hosting region<=20 and controls64/16MiB inside20/6; new actual backing GUID plus guest-hosting filesystem each pass8GiB in one quiescent invocation. Layout/formatter/alias trust and16MiB control-format feasibility are UNPROVEN; no disk action is authorized.
Final coordinator uses original process/thread HANDLE exits, exact creator-owned HCS VM exit and service/callback joins before q_exit_durable is written/flushed to fixed E receipt. q_accept_live is sampled after final flush/close and is live only; durable receipt alone cannot synthesize it. Failure/crash/replay/poison or missing joins/handoff refuses normal acceptance.
Coordinator survival is readonly handoff/once-close/exit within original external6000 and includedcleanup60, with all measured/reserved/actual tail charges under original caps; no postseal experiment/E writes or zero-cost tail. Deadline owner, complete exit/billing producer and native installed support remain missing.
Physical installedDRAM16GiB plus complete disjoint dedicated physical accelerator8GiB inventory is a conditional hardware enclosure, not actual selected-host proof or a total-allocation/commit/billing cap. Owner hardware facts and Windows MONITORED answer are PENDING; four original application TIDs remain HARD and Job4processes is insufficient.
C00 AUDITED_UNPROVEN; only independent C02 known Job/identity/observation/rejection and C03 known prebirth/preload-parser/transport-rejection SOURCE slices are eligible next. C04-C12 STOP even SOURCE; all three mechanisms, architecture/admission/fullFAIL/refusal states persist; F1>=0.66 open and Route3 COMPLETE/fourFAIL unchanged.
SOURCE/runtime/GT/disk delta0; sole author appends original3 and stops before new fresh SPEC -> different fresh QUALITY, currently PENDING. Actual prefix/hash/time receipt is reported to root, with no new Git or review success invented.

### 2026-10-12 Selected DOCUMENT review receipt

[Root factual receipt](../../decisions/2026-09-27-route2-design-review.md#route2-selected-mechanism-review-receipt-20261012) records actual author STOP, fresh SPEC then different QUALITY: both NO_REMAINING_SCOPED_P1_P2 / SELECTED_MECHANISM_DOCUMENT_REVIEW_ONLY. Selected suffix committed29d98ca1b934282c4d745f01ba14e2068ffd9e5e and non-force pushed with feature/main/full11 staged verification. This later receipt is uncommitted at writing time.
The three original owner choices are bound; hardware facts and the NEW Windows thread policy answer remain PENDING, so four application TIDs remain HARD. Physical-capacity/VM-service/final-exit mechanisms are UNPROVEN; scoped review is not source/runtime/budget/admission proof. No scientific change or execution. Original fullFAIL/FrozenNone/blocked states and C04-C12 STOP even SOURCE persist. Original outer17:12 was exceeded by mandatory review/retention/Git close; no budget reset and all missing costs UNKNOWN_NOT_ZERO.

### 2026-10-12：owner 硬件补充
见[硬件自述与策略待决](../../decisions/2026-09-27-route2-design-review.md#route2-owner-hardware-clarification-20261012)：偏好本地 E + WSL，RAM 16G、RTX 5060、独立显存 8G 仅 OWNER_REPORTED / NOT_NATIVE_VERIFIED，原单位与名称保留。用户未选择 MONITORED，Windows 四 TIDs HARD 维持；policy/native proof 仍待决，原生 inventory/grouping、no-hot-add、prebirth billing、安装事实 UNKNOWN，成本 UNKNOWN_NOT_ZERO，原约束与阻断状态维持，未授权安装、磁盘变更或执行。

Factual closure: original3 owner-report suffix now has fresh SPEC then different fresh QUALITY, both NO_REMAINING_SCOPED_P1_P2 / OWNER_FACT_DOCUMENT_ONLY; actual times and retention are recorded at the linked review anchor. No native/installed/runtime/admission proof or thread-policy change; original root soft-close overrun and UNKNOWN_NOT_ZERO fees retained. Git pending at writing time.

### 2026-10-12: Windows MONITORED policy approved
- The owner "同意" approves [the Windows thread-policy delta](../../decisions/2026-09-27-route2-design-review.md#route2-windows-thread-monitored-approved-20261012), superseding all earlier Windows HARD4/MONITORED-PENDING sentences for BOTH prep/compile/ABI and external observer/helper/launcher/bridge/final-coordinator application groups.
- Four remains the groupwide application-TID threshold, including monitor/loader/callback, with fixed-thread design; infrastructure is excluded only from this agreed application count and fully billed. Linux tasks/pids HARD including studyTasksMax=2 and every RAM/VRAM/CPU/disk/wall/science cap remain.
- Accept pre-detection overshoot with actual peak/duration UNKNOWN, never HARD4 proof. Required original native owner HANDLE/PID/creation-time membership/QPC epoch and counted preloaded native observer must produce bounded identity-checked observations through setup/application/drain/seal/tail; caller fields/empty lists/PID reopen cannot supply proof.
- Observed >4 or incomplete/failed/stale observation latches STOP_NEW; no workload birth/fit/decode/new GT grants. Only original drain/revoke/wait/cleanup under original deadlines; missing liveness/coverage/deadline/fees refuses, primary+cleanup failures retained, no retry/reset/resume/completion inference. Poll/work bounds, loading/membership/stop producer remain UNKNOWN; no invented caps.
- Raw Toolhelp signatures, return/error/dwSize/once-close rules and PID-reuse/current-thread/CPU-billing limitations are bound by the linked contract; observed max is lower evidence only. Native monitor/physical capacity/full billing/WSL service exit/durable handoff remain UNPROVEN; no execution/installation/disk/Stage permission.
- C00 AUDITED_UNPROVEN, wholeC01 incomplete, C02/C03 NOT_STARTED and dependentC04-C12 STOP even SOURCE; PREPARED_UNREVIEWED/FrozenNone/fullFAIL/blocked/notready/notauthorized, Stagezero, Route3 COMPLETE/fourFAIL and F1open remain. This DOCUMENT suffix awaits fresh SPEC then different QUALITY after author STOP.

Scoped P2 override for the approved Windows MONITORED contract:
Active original membership requires live held original identity before and after each snapshot; this does not require all previously admitted actors to remain alive throughout drain/seal/tail.
JOINED_EXITED membership requires retained original creator identity, native exit with approved status, original join/once-close history and final billing; exclude it from the CURRENT active-TID count only after the actual original exit/join producer, retain all historical fees, never reopen closed handles to reconstruct identity, and keep counting surviving monitor/coordinator TIDs in their application group.
An exit racing the snapshot, missing original join/history/final fees or unclassified membership means UNKNOWN/STOP_NEW, never zero/PASS or an assumed normal joined exit; native producers remain UNKNOWN and all prior policy, budget, science, permission and blocked states persist.

Root closure: owner MONITORED approval and active/JOINED_EXITED scopedP2 repair now have independent SPEC then different fresh QUALITY, both NO_REMAINING_SCOPED_P1_P2 / APPROVED_MONITORED_POLICY_DOCUMENT_ONLY, with exact actual UTCs and retained32s author/outer-soft-close overruns at the linked review anchor. No nativeobserver/budget/fullreview/admission PASS or originalclock reset. FourTIDs MONITORED is binding for Windowsapplicationgroups; Linuxandotheroriginalcaps/science unchanged; allmissingfees UNKNOWN_NOT_ZERO. Git pending at writing.

### C02-B1 exact target and API ledger link (SOURCE only)

The [original execution plan ledger](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-existing-target-and-api-ledger-source-only) reconciles the existing package-relative native C/H Windows target, exact four new component functions, Microsoft API declarations, raw validity/once-close/failure semantics and explicit SDK/C11 requirements before implementation. Sole implementer START 2026-10-13 02:02:07 UTC; due ALL_READ_WRITE_STOP 02:22:07 UTC. This component grants no issuer provenance/scope success/original join or runtime/Stage authorization; whole C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE and original caps/science/fees remain unchanged.

### C02-B1 actual raw component author checkpoint (fresh reviews pending)

Actual implementation is limited to Windows-guarded route2_win_raw_process_observe_v1 and route2_win_refuse_vm_service_scope_v1 / route2_win_refuse_e_physical_cap_v1 / route2_win_refuse_owner_exit_join_v1 in the existing native C/H. The [original plan checkpoint](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-sole-author-component-checkpoint-source-only-fresh-reviews-pending) specifies exact raw fields/status/size, API output validity, process-type validation before waits, same-access private duplication, one close attempt, ordered 32-bit Win32 and synthetic faults, fresh raced-exit times/identity, signal-witness code259 and QPC/FILETIME units. The [exact ledger](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-existing-target-and-api-ledger-source-only) preceded all source edits.

Sole author START 2026-10-13 02:02:07 UTC; native edits/first isolated static source/hash inspection ended by 02:12:42 UTC. Final ALL_READ_WRITE_STOP/five-file hash receipt goes to root before 02:22:07 UTC. Source is IMPLEMENTED_BUT_UNCOMPILED / DONE_WITH_CONCERNS, pending fresh scoped SPEC then DIFFERENT fresh QUALITY. Old Linux v1/C01 declarations and original three document prefixes are preserved; no tests/preprocessing/build/load/call/native/OS/WSL/GT probe or Git mutation occurred.

Successful raw completion asserts facts for this borrowed native process only; it creates no original membership/exit approval/join/final billing/whole scope/epoch/handoff/admission receipt. Raced exit is incomplete/STOP_NEW. Complete seed/controllers/cohort/phase owner/full-scope producers remain NOT_IMPLEMENTED. C00 AUDITED_UNPROVEN, whole C01/C02 incomplete, C03 NOT_STARTED, C04-C12 STOP even SOURCE; physical extent/all-writer/whole-billing/service-exit/final-durable proofs remain UNPROVEN. Original Windows MONITORED4/P2 override/Linux hard/caps/science/UNKNOWN_NOT_ZERO budgets and blocked/Stage-zero/Route3-four-FAIL/F1-open states persist.

### C02-B1 scoped SOURCE review boundary (UTC 2026-10-13)

The [original plan closure](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-independent-source-review-closure-utc-2026-10-13) records author STOP followed by fresh independent SPEC and different fresh QUALITY, both NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY on identical C/H bytes and author-checkpoint suffixes. C02-B1 is SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED. Native source hashes are C351eaa16c3394102530c9d2c3d085daaf3e84c1b23cfbd8050a2ed2611e7112b and H a60683ab57ce9293448d1b6951c903b7bcbad0c3057ed12c1eb5df89692d2e63. Root verified original-three raw prefixes, old v1/C01 declarations, exact five-path scope and all unrelated/index/main preservation. This administrative receipt issues no full-review ID or wider review claim.

Actual raw API facts, field validity, private same-access duplicate/once-close, ordered query/close/QPC faults, signaled exit-code259 and raced-exit incompleteness are implemented. Creator/cohort certification, active identity registry, monitored-thread loop/interval/stop action, exit approval/join/history/final costs, seed/full controllers and consumer wiring remain absent/unproven. Three native refusals never emit R2_SCOPE_PROVEN. A successful raw sample is no admission.

Existing complete A+B card receives only the C02-B1 SOURCE delta. All actual deployment/capacity/cost, original clocks/transport, readonly loading closure, complete input/GT/phase and nested equivalence, teardown/durable external acceptance, full formal review/freeze conditions remain. Approved Windows MONITORED4/infrastructure billing/physical extent DESIGN/external coordinator tail decisions persist; Linux hard and original caps/science remain. C00 AUDITED_UNPROVEN, whole C01/C02 incomplete, C03 NOT_STARTED, C04-C12 STOP even SOURCE; PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/full FAIL/all admission blocks/Stage zero/Route3 COMPLETE-fourFAIL/F1-open persist. No tests/imports/build/native/OS/WSL/GT probes/formal objects; actual SDK/compiler/runtime/charges stay UNKNOWN / UNKNOWN_NOT_ZERO. Root exact-path Git receipts follow.

### C02-B1 exact-path Git receipt link

The [original plan receipt](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-b1-exact-path-git-receipt) records component commit bfdee835e23183eefee66c24c5b8fbaf13acb096, actual non-force push/remote HEAD and preservation of main/original eleven staged identities/all unrelated bytes. This administrative append changes no reviewed source behavior or scope; its own small-commit hash/final remote confirmation is obtained from Git/final report. C02-B1 remains SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED, whole C02 incomplete and all original FAIL/blocked/Stage-zero/freeze-none states remain. UNKNOWN_NOT_ZERO costs, original caps/science/confirmed policy choices and C04-C12 SOURCE stop persist; no new tests/native/WSL/GT/formal objects/card/handoff.

<a id="c00-reaudit-authorization-delta-20261013"></a>
### C00 re-audit: effective preparation permission and current admission gap

The [candidate C00 re-audit](../../decisions/2026-09-27-route2-design-review.md#c00-mechanism-reaudit-candidate-20261013) is the main decision record. Its fourteen rows are an incremental full-state update to the existing unique complete A+B card, not another card/application. The [execution owner/API and preparation-contract ledger](../plans/2026-09-28-route2-wsl-controller-execution.md#c00-reaudit-owner-api-ledger-20261013) distinguishes BEFORE requirements from facts produced by the same authorized invocation.

The owner's new preparation-validation permission is effective; old SOURCE-only authorization shortage no longer blocks preparation. Before any birth/import/load/native/WSL/API call, the original clock/execution groups/resource/complete fee/STOP_NEW/cleanup contract must exist. Original budget/history balances, readonly pre-load owner/closure, current finite geometry/all-writer producer and complete VM/service original join remain unproven; no actual preparation invocation occurred. Permission is retained, not withdrawn, and actual machine feasibility remains UNKNOWN. Concrete physical changes still need their concrete authorized scope; GT/Stage/scientific A+B remain unauthorized.

Already bound Windows MONITORED4/fixed-thread application groups, full infrastructure billing, dedicated physical extent DESIGN and bounded billed surviving external final coordinator remain authoritative. All other limits/science, E30=24 including20+6/control metadata/guest baseline<=8 and same-invocation guest-hosting-FS+actual-L_C-backing free>=8GiB each remain; independent carrier reserve, no third8. Prep4GiB/200%/1800, external512MiB/100%/6000, cleanup60, whole16GiB RAM/8GiB VRAM, nonE512/stop384/nominal128 with UNKNOWN overshoot, actual VM8GB/swap0/CPU2/gui=false, study1200/3600/cumulative fit900 and original Linux hard C/AS/TasksMax2 are unchanged. Full historical fees/remaining balances are UNKNOWN_NOT_ZERO, neither proven exhausted nor zero.

SOURCE findings: _prepare_fixed_worker refuses missing readonly Windows worker/PE/pre-import owner; _require_host_control_boundary refuses missing actual hard-capped hostcontrol/installed policy; old capacity code32/34/sharedE cannot consume current L_C<24/L_X<6 design and has no actual layout/formatter producer. No dependent source was repaired. Official HCS contracts distinguish VM exit from all-service join, async start from final result, finite local timeout from service completion, and operation/compute close from rollback. HcsCancelOperation is specifically documented NOT IMPLEMENTED/E_NOTIMPL; no global cancellation-impossibility claim follows. Original local WSL creator bridge/cohort/preload/billing/tail remains UNKNOWN.

C00 AUDITED_UNPROVEN; wholeC01/C02 incomplete; C02-B1 SOURCE_REVIEWED/IMPLEMENTED_BUT_UNCOMPILED source pins unchanged; C03 NOT_STARTED; C04-C12 STOP even SOURCE. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/old fullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED describe the scientific A+B application. StageA/B/results0; Route3 lawful COMPLETE/fourFAIL is preserved without rerun; eventF1>=.66 remains open. No formal review ID/PASS/freeze or runtime evidence is invented.

Author FIRSTCLOCK2026-10-13 04:49:42 UTC/recording target04:57:42 is separate from the elapsed root SOURCE03:07:55->03:37:55 soft target and original execution budgets. Root's later capacity-source grep/earlier uninstrumented reading and all fees remain recorded, without a reset or budget PASS. Spec/card/prompt/referenced-evidence restoration has a final report; full plan/review restoration confirmation is still pending at author time. Only original3 append/prefix hash inspection occurs here. After author STOP, root obtains fresh SPEC->DIFFERENT fresh QUALITY and actual IDs/retention/Git receipts; these are pending, not preclaimed.

<a id="c00-reaudit-science-gate-erratum-20261013"></a>
### C00 re-audit scoped P2 erratum: original science and evidence timing

This normative increment supersedes the scientific interpretation in the preceding candidate and linked plan/review, preserving all their bytes. The unique scientific setting is nested five outer folds x four inner folds, with four sub-inner folds per inner fold; it is not four configurations. The complete nested graph supplies the105 candidate roles;25 verifier fits are20 inner+5 outer. The original limits remain25fit/25predict/65decode/20GT evaluations+oneGT-free pooled merge, pooledGTreads0.

BEFORE scientific approval, complete nested cross-OS equivalence uses synthetic inputs with no real GT and no Stage, covering the original5x4 call graph, numerical boundaries, symmetric atol1e-12/rtol1e-10 and discrete exactness, followed by independent review. Fixed protocol/source identity and non-GT source/input checks are prior requirements. This erratum performs no such validation and asserts no equivalence PASS.

Only after the binding concrete complete A+B final approval may the same lawful invocation perform formal StageA105 reference cases, all pass, then105 treatment cases. Formal105 is not prior evidence or a substitute for synthetic verification. Original M0/fresh double8/formal105/N-M-S-B-R/GT releases/terminal facts are SAME INVOCATION only, never permission to run Stage early. The [main erratum and restored-evidence receipt](../../decisions/2026-09-27-route2-design-review.md#c00-reaudit-science-gate-erratum-20261013) updates row2 of the existing unique card; no new card. Fresh SPEC repair verification and DIFFERENT fresh QUALITY are pending. Three UNPROVEN/current blocked states and UNKNOWN_NOT_ZERO budgets persist; this mandatory document repair does not reset elapsed SOURCE or execution budgets.

### C00 re-audit actual scoped dual-review receipt

[Actual SPEC repair verification and DIFFERENT fresh QUALITY](../../decisions/2026-09-27-route2-design-review.md#c00-reaudit-actual-scoped-review-receipt-20261013) completed NO_REMAINING_SCOPED_P1_P2 / C00_PERMISSION_AWARE_DOCUMENT_API_AUDIT_ONLY. Full original3 restoration is complete. The scoped ID is not full implementation/runtime review; all original three UNPROVEN mechanisms, NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/FROZEN_ADMISSION=None, fourteen-gate incompleteness and original UNKNOWN_NOT_ZERO budgets remain. Effective preparation permission is retained, but actual original clock/group/fees/pre-load/cleanup contract is missing. No runtime/GT/Stage or new production SOURCE occurred; Git receipts follow separately.

### C00 re-audit Git preservation receipt

[Actual exact-three-document commit/non-force push/remote preservation](../../decisions/2026-09-27-route2-design-review.md#c00-reaudit-exact-path-git-receipt-20261013) records the scoped audit checkpoint. This later administrative receipt is a separate small commit; its own HEAD is read from Git/final report. Mechanism/runtime/full-review/admission gaps and all original budgets/states remain unchanged.


### C02-A native known-Job capsule source checkpoint (2026-10-13)

Only the independent C02-A component is COMPONENT_SOURCE_IMPLEMENTED_UNCOMPILED, awaiting fresh scoped SPEC then DIFFERENT fresh QUALITY after author STOP. [Pre-edit exact API/cleanup ledger and source checkpoint](../plans/2026-09-28-route2-wsl-controller-execution.md#c02-a-exact-existing-target--pre-edit-api-and-cleanup-ledger-2026-10-13) binds actual W/SDK signatures/headers/Kernel32/rights/out/error floors; public docs are not installed SDK/ABI proof. Sole author START08:11:46 UTC/deadline08:31:46; final actual STOP/hash receipt goes to root, not preclaimed here.

Existing native C/H contain five independent raw-status create_fixed/assign_borrowed/query/close_once/copy_report_v1 functions behind separate Windows-seed/x64/C11/Win8 guards, plus native C11 atomic_flag guard for consistent lifecycle/report copies. Anonymous noninheritable original Job is retained directly in private native state before return conversion; fixed commit4GiB/active4/lowest <=2 allowed bits/interval CPU200% conversion/KILL/no breakaway configuration receives strict exact-size readback. One real borrowed process type/PID checked before private SAME_ACCESS/FALSE duplicate; pseudo/NULL/INVALID and real self PID rejected; PID/creation/liveness and Job membership surround actual assignment. Association is existing-process only, not atomic prebirth/permission, and failure can terminate it. Primary remains sticky; only report/once-cleanup remain after poison. Both successful private handles are consumed before either independent one-time close; all three bounded primary+close faults retain full DWORD values. Failed duplicate output never owned, borrowed never closed, close failure not retried; KILL request not exit/join.

Report version/native size, per-field UNKNOWN/VALID/FAILED, fixed configured snapshot/latest query attempt and acquisition/consume/close history distinguish raw native facts from initialized zero. Latest Job counters/commit peaks describe this Job only; commit not RSS/wholeRAM/VM, active4 not TIDs, CPU scheduling interval/nested-parent relative not instantaneous wallclock. No complete membership/history/fees, approval, MONITORED4, VM/service/physical/final join or successful scope producer. Existing C/H baseline bytes and all old B1/refusals/Linux v1/C01 pins match isolated stdlib hash checks; original3 append-only. No C syntax/ABI/build/preprocess/link/load/native/runtime/test/import/probe/WSL/GT/formal objects or Git mutation.

C00 AUDITED_UNPROVEN/wholeC01C02 incomplete/C03 NOT_STARTED/C04-C12 STOP even SOURCE/three UNPROVEN/PREPARED_UNREVIEWED/FROZENNone/oldfullFAIL/APPLICATION_BLOCKED/notapprovalready/notexperimentauthorized/Stagezero/Route3 COMPLETE-fourFAIL/F1open persist. Effective prep/compile/noGT permission remains, but original actual clock/group/resources/full fees/preload/stop/cleanup contract is missing; no invocation/new E directory. Source budget does not reset runtime budgets or make fee0; UNKNOWN_NOT_ZERO persists.


### C02-A reviewed source and final fourteen-condition delta (2026-10-13)

[The original review's final incremental fourteen-condition card, partial historical-budget recovery, directory authorization and exact remaining production gates](../../decisions/2026-09-27-route2-design-review.md#c02-a-scoped-dual-review-historical-budget-recovery-and-full-card-delta-2026-10-13) preserves the unique application and all historical entries. Review ID route2-c02-a-native-job-source-review-2026-10-13-001 covers SOURCE only: sole author stopped08:30:35, fresh SPEC stopped08:42:42, DIFFERENT fresh QUALITY stopped08:50:59 UTC; both NO_REMAINING_SCOPED_P1_P2 / IMPLEMENTED_BUT_UNCOMPILED. C/H reviewed hashes0982f899b883ff3fb2268d42473c9bea951dbed0ce569a359e15a8e4b392e3f4 /d94ce542b9ab2ec3ee7ed8bd634b216a2696f17b856a20c0108648bd5079cd95, old C/H/B1 bytes and original3 prefixes preserved. This is no full C02/runtime/freeze/admission proof.

The user's E-directory permission binds E:\Route2AdmissionPrep_20261013 as proposed namespace only; it is not created or a physical cap. Workspace18487-name and six archive-directory searches found no additional complete original Route2 ledger. Recovered first3872MiB and distinct repeat416MiB VHDX logical growth/local cgroup/install/Windows samples do not establish original fee upper bounds/positive余额/AllocationSize attribution. No original budget or clock is reset, history is not zeroed, and no physical or compile/native/WSL/GT/Stage action is taken. Current full original preparation contract/physical geometry/exclusive owner/VM-service final join/dependency closure remain missing; C03 bounded complete grammar is still unspecified. Complete14 conclusions stay NOT_CLOSED; C00 AUDITED_UNPROVEN, wholeC01/C02 incomplete, C03 NOT_STARTED, C04-C12 STOP even SOURCE, PREPARED_UNREVIEWED/FROZENNone/fullFAIL/APPLICATION_BLOCKED/notapprovalready/notexperimentauthorized/Route2zero/Route3fourFAIL/F1open/UNKNOWN_NOT_ZERO persist. Git retention remains pending at append time.


Final condition-document verification receipt: independent SPEC /root/c02_a_fresh_spec START08:57:45/ALL_DOCUMENT_READ_STOP08:58:49 UTC (64s within4min), followed by DIFFERENT QUALITY /root/c02_a_fresh_quality START08:59:50/STOP_ALL_DOCUMENT_READS09:00:54 (64s within4min), both NO_REMAINING_SCOPED_P1_P2 / C02_A_FINAL_CONDITION_DOCUMENT_ONLY. They read only the final original3 delta; no implementation/API/runtime/Git operation. This administrative receipt adds no scope, full formal review, freeze, budget PASS or approval; exact-path Git/remote receipt remains pending.


### C02-A exact-path Git preservation receipt (2026-10-13)

[Actual source checkpoint017c372 and remote/main/full-index preservation receipt](../../decisions/2026-09-27-route2-design-review.md#c02-a-exact-path-git-preservation-receipt-2026-10-13) records the scoped source/document checkpoint. This later administrative original3-only commit gets its own HEAD/final remote confirmation from Git/final reporting. No full mechanism/runtime/budget/freeze/admission closure follows; the final fourteen-condition delta and all UNPROVEN/blocked states remain unchanged.


### Historical no-GT session receipt recovery (2026-10-13)

[The original review's historical-session recovery and precise C03-A source-contract audit](../../decisions/2026-09-27-route2-design-review.md#historical-session-receipt-recovery-and-c03-a-contract-audit-2026-10-13) adds external archive locators and two exact call/output pairs, without a new14-card/application/epoch or production change. Historical preflight at13:43:52.279->13:43:56.377 UTC and probe-cgroup14:47:32.122->14:47:42.793 on2026-09-29 yield only client-record intervals4.098s/10.671s; preflight explicitly emitted exit0, cgroup exit scalar remains unknown. The real archived commands use py -3.10 -B; unsupported older selectors' zero matches are not proof of absence. Native QPC/original fee bounds/positive1800-6000 balances/cohort/service/physical attribution remain UNKNOWN_NOT_ZERO. C03-A has no complete fixed capture/once/first-MemAvailable/transport/consumer contract; no partial refusal-only code is added. Native C/H hashes/bytes and all original budgets/science/bound policy are inherited unchanged; source overrun is retained, not actual-clock reset. Conditions9/11/13 remain NOT_CLOSED, all other14 conclusions and C04-C12 SOURCE stop/fullFAIL/FROZENNone/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stagezero remain. Actual scoped recording SPEC->different QUALITY/Git receipts are pending at append time; no current native/OS/WSL/prep/GT/Stage action follows.


Scoped recording-review receipt: route2-historical-session-metadata-record-review-2026-10-13-001 covers HISTORICAL_SESSION_METADATA_RECORD_ONLY. Fresh SPEC /root/historical_receipt_fresh_spec START12:22:20/ALL_READ_STOP12:25:13 UTC (173s within6min), followed by DIFFERENT fresh QUALITY /root/historical_receipt_fresh_quality START12:27:16/ALL_READ_STOP12:27:35/final STOP12:28:30 (74s within6min), both NO_REMAINING_SCOPED_P1_P2. They read only the original3 recovery suffixes against supplied facts, not archives/implementation/API/runtime. Optional P3 precision is recorded here by append: the two projectors had configured30-second maxima, with reported inner-loop elapsed0.01579s and0.25848s respectively, not actual30-second runs or complete source/loader fees. No interval or process duration becomes native original budget evidence. Root confirmed all403 original identities/full171 index/original11 complete staged rows unchanged before append; old original3 prefixes match baseline ddea3ca. Exact-path retention and actual remote receipt remain pending; no complete formal review, budget/freeze/admission PASS or new run follows.


### Historical receipt recovery Git preservation receipt (2026-10-13)

[Actual historical-record checkpoint d72b15f and exact-path/index/remote/main receipt](../../decisions/2026-09-27-route2-design-review.md#historical-receipt-recovery-git-preservation-receipt-2026-10-13) records source-only evidence retention. This later administrative original3 checkpoint receives its own HEAD from Git/final report; no whole budget/mechanism/freeze/review/admission closure or invocation is implied.


### Preparation bootstrap contract clarification (2026-10-13)

[The original review's independent contract clarification and decisive evidence impasse](../../decisions/2026-09-27-route2-design-review.md#preparation-bootstrap-contract-clarification-and-evidence-impasse-2026-10-13) corrects the interpretation of C03: its output/status/validity/once/parser details are autonomously implementable internal choices, not an external permission/fact requirement. Complete preparatory bootstrap remains dependent C04–C12 STOP under the unproven exact mechanisms. Original authenticated historical charges/clock continuity and resulting1800/6000 balances are BEFORE new actual execution; future instrumentation cannot recreate those past facts. New preparation identities/current geometry/ABI/load/usage/cleanup may be generated during a legally admitted preparation invocation; original study M0/double8/formal105+105/GT/live acceptance remain later authorized same-invocation facts. General permission is already effective; it supplies neither a missing ledger nor exact WSL original creator/service drainage. No reset/waiver/new sampler/refusal/PASS/application/Stage is introduced. Original14 conditions, all source/runtime/fullreview/admission failures and UNKNOWN_NOT_ZERO remain; scoped clarification dual review/Git receipt are pending at writing.


The original review additionally appends [the complete original14 closing status increment](../../decisions/2026-09-27-route2-design-review.md#original14-conditions-complete-closing-status-increment-2026-10-13), separating SOURCE/actual proof, BEFORE requirements and SAME legal-invocation facts for all14 conditions. It retains the decisive full-history/original-budget evidence block and all three exact mechanisms UNPROVEN; no completed installation/freeze/full review/approval is claimed. Two invalid scoped SPEC attempts are preserved there, not counted as PASS. A valid fresh SPEC then different fresh QUALITY is still required for this final documentary scope.


#### Preparation contract clarification: scoped dual-review receipt (2026-10-13)

Scoped record ID `route2-preparation-contract-clarification-review-2026-10-13-001` covers ONLY this frozen documentary clarification and original14 status increment, not production implementation, runtime closure or admission. Fresh SPEC /root/bootstrap_clarification_final_spec retained original START15:13:51 and deadline15:19:51 UTC: initial pre-content hash-label stop15:13:54, corrected suffix hashes then ALL_READ_STOP15:18:48/FINAL_STOP15:19:04, total313s within360; no clock reset. Root had supplied whole-file hashes without identifying their scope; the correction changed no file bytes. Different fresh QUALITY /root/bootstrap_clarification_final_quality START15:21:24/ALL_READ_STOP15:21:28/FINAL_STOP15:21:45,21s within360. Both concluded NO_REMAINING_SCOPED_P1_P2 / PREPARATION_CONTRACT_CLARIFICATION_ONLY. Earlier two INVALID attempts remain INVALID.

The reviewed suffixes at offsets383834/499532/702517 had lengths2023/2023/16641 bytes and SHA256 2ff4631add8d858278e509c2d23848573a6513fd14f47b7903299c17d905375f / same / 5376e91bee5e47206be8ad85ef0f271fe8b1a83b06bf2974e0397ceaa043b15a. Root preservation check before this administrative receipt confirmed403 file identities,400 unrelated bytes unchanged, all171 complete index rows identical including original11 staged mode/blob/stage/path identities, all three entire4168566 HEAD prefixes identical and diff --check exit0. Only original3 doc suffixes changed. No actual preparation/native/compile/load/install/disk/GT/Stage run occurred; costs remain UNKNOWN_NOT_ZERO and original clocks/balances unproven. Git exact-path commit/push/remote receipt follows. Full FAIL/FROZEN_ADMISSION=None/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED and all original14 gaps persist.
