# A2-003 固定 26D 验证的资源恢复设计

日期：2026-09-24  
状态：`ARCHIVED / A2_003_INVALID_CLOSED`。这是 003 的历史设计，不能再用它启动真实 audit/run；终态见[003 决定](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)，下一编号见[A2-004 决定](../../decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md)。

## 1. 决策问题与证据

本设计回答一个有限问题：在不改变 [A2 已批准科学定义](../../decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md)的前提下，能否解除 A2-002 的资源阻断，使固定 26D 验证产生一次合法性能结果？是否启动新编号研究、具体预算及旧停止语句的覆盖，见[单次授权决定](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)。本设计和[执行计划](../plans/2026-09-24-a2-003-resource-recovery-implementation.md)不构成本对话运行真实研究的指令。

| 证据层 | 已知内容 | 解释界限 |
|---|---|---|
| A. 批准文档 | A1-005、41 人、234 GT、5/4/4 角色、26D、HGB、阈值及 decoder 已冻结；001/002 各自一次尝试。 | 002 的“不得追加 003”是其当时授权范围，需新的明确决定覆盖；不能改写旧记录。 |
| B. 现行代码 | [audit.py](../../../src/eating_event/a2/audit.py)先构造 632,100 个窗口的 Python 几何与身份对象，再全量解析 147.8 MB 身份 JSON 和 288.1 MB 候选 JSONL；[control.py](../../../src/eating_event/a2/control.py)在保存失败采样前先检查上限；[run loader](../../../src/eating_event/a2/audit.py)一次装入 105 个角色。 | 同时常驻是可审查的峰值风险；尚不能确定 002 在哪一步超限，也不能由 audit 的改进保证 run 通过。 |
| C. 已有结果 | [002 停止记录](../../../artifacts/a2-context-verifier-v1-002/validation-stop-record.json)：`INCOMPLETE_RESOURCE`，audit 一次、run 零次、fit 零次；最后合格 RSS 2,116,214,784 B，旧上限 2,127,893,299 B，失败采样值未持久化。001+002 active wall 21.047 秒。 | 四项 A2 性能判定均 `NOT_EVALUATED`，不是性能失败。A1 run 峰值 2,394,521,600 B 只提供量级参考，不是 A2 上界。 |
| D. 缺失证据 | 无 002 的 `AUDIT_READY`、真实 26D 物化摘要、失败采样值或精确阶段；无独立 participant 确认，也无现场视频可核实长 FP 实际行为。 | 不能用 002 与 003 的真实输出做字节对照，不能把 annotation-contract FP 改善当作行为真值。 |
| E. 推断 | 旧 2.13 GB 是 001/002 的冻结研究上限，不是 16 GB 机器的硬上限；8 GB 显存不扩充 CPU process-tree RSS。 | 提高可用资源与减少对象常驻有合理机制，但成功和 F1 改善均未知。 |

## 2. 固定科学定义与禁止边界

003 使用 A1-005 的 105 个 candidate score roles 和保存的候选；outer 4,183 个候选覆盖 213/234 GT。41 人、234 个评价 GT、6C7、5/4/4 嵌套角色、训练侧 G3、16+10 特征顺序与 `float32` 转换、±300 秒 midpoint context、HGB 全参数、seed `20260910`、阈值集合 `{0.10,0.25,0.50}`、180 秒最短时长、600 秒 fusion、strict IoU `>0.25`、一对一匹配和四项 numeric/stage 判定均不得变。outer 标签不得进入特征、拟合或选择。保留复合 `(role_id,candidate_id)` 身份、全窗 score 位置验证、component 非 source segment、post window 末端门禁、独立标签 join 及实际 fit 输入摘要验证。

只读取经 A1 checksum、代码身份和数据契约批准的派生 cache/score/候选及 A2 前序记录。不得读取或 stat raw sensor；不得访问 official test、external data；A1 模型 pickle 仅允许沿用既有 audit 的文件哈希核验，不得反序列化或调用；不得回写 NPZ、标签、A1 产物或 production。candidate fit/predict 为 0；只有合法嵌套图中的 verifier 可 fit，家族累计最多 25 次。模型配置、阈值、duration、fusion、目标函数、outer 角色或评价规则不是本次资源修复的可编辑项。

## 3. 资源方案：先改常驻方式，再执行一次

### 3.1 Audit 的有界数据生命周期

1. 从现行 `f363ea07d58664ede603159ac77fc5ce4630c9bd` 代码生成只含合成小 fixture 的基线输出与哈希，保留原功能计算路径作为等价参照。先补能复现多 role 交错、重复 bare candidate ID、半开区间接触、hard gap、缺 score、资格排除与 outer 标签泄漏的反例。
2. `audit.py` 对窗口几何/全局身份只保留完成后续验证所需的一份有序表示；验证时保留 A1 全局索引顺序、stable ID、participant/record/session/row、开始结束毫秒、coverage 与 gap 的逐项语义。消除 `_load_global_identity` 的原始 JSON 行和复制身份行同时常驻；不得用只检查计数或哈希代替逐行身份/几何核验。`_parse_score_rows` 对 reference stable ID 的排序、reference row hash/count 仍须逐 role 完全一致；按 record 有界构造时不能拆断 `build_support_components` 的相邻窗口连通关系。具体容器可用紧凑列或有界 record 结构，但适配器向现有 component/context/feature 函数传递完全相同的值与顺序。
3. 将 72,112 条候选 JSONL 单次顺序读取并校验，按原输入顺序写入固定 role 暂存文件；暂存目录位于 **003 输出**，从创建起计入 1 GiB 家族磁盘上限。保持所有 role 的复合 key 唯一性、16D JSON 数值、label-null、boundary 与 support 契约。`_parse_score_rows` 所需的 candidate ID 只保留每 role 的轻量有序索引，不保留候选 dict。每次只将一个 role 的原始候选及所需 scored windows/context 装入内存，调用现有 `build_a2_features` 和 `_materialize_role`；不可通过重复扫描 outer 结果决定处理方式。现行 `_all_training_rows`、outer coverage 和 A1 FN 分类仍依赖全量 `candidates_by_role_raw`，必须改为 role 生命周期内有界累计，或从受监督暂存按需重读 outer role，保留原输出值、键与次序；不能在末尾重新全量装入 72,112 行。`model-provenance.jsonl` 与 `score-provenance.jsonl` 的已认证对象也须在最后一次必要使用后释放/有界读取，不与全部物化角色长期常驻。完成这些只读计算后清除暂存；`AUDIT_READY` 前不存在未计数的临时文件。任何新增暂存格式必须在产物/预算账本中可追溯。
4. 保留原 26D 特征函数、HGB、decoder、匹配和评价实现的计算语义。若为资源生命周期不得不编辑 `execution.py`，只允许装载/释放调度，禁止改选择元组、fit/score 调用次序、解码或指标公式；执行前用 fake backend 的完整 20+5 角色结果证明等价。证明不了就停止，不调用真实 audit。

### 3.2 Run 的有界读取

`load_audited_corpus` 不再把 105 个 role 的 `A2Candidate` 同时常驻；返回受 `AUDIT_READY` 和 role digest 约束的只读 role 映射，按请求装入该 role 并验证 ordered key、26D `float32` 矩阵、标签 join 及文件哈希。访问顺序仍由 `execute_validation` 的原 20+5 图决定；同一 role 的重复访问返回同样内容，不将 outer GT 用于选择。保持最多当前 outer fold 必需的 role 在内存，fold 后释放。此变动只影响内存驻留，不允许放宽“实际 fit 输入与 audit 摘要一致”的门禁。合成基线/新实现对每个 verifier 的有序特征矩阵、标签、participant 序列、评分输入、阈值选择、预测、匹配和 metrics 作逐项比较；不调用真实模型。若做不到等价，不启动 003 真实 audit。

### 3.3 一次性资源门禁

003 的 host CPU process-tree RSS 规则在真实 audit 前固定为：`min(4 × 2^30 bytes, floor(0.60 × startup_available_bytes))`。`startup_available_bytes` 必须至少 `5 × 2^30 bytes`；否则只返回 `NOT_STARTED_INSUFFICIENT_HEADROOM`，在创建 003 输出/账本/锁和访问 A1 派生来源之前停止。内存环境改善后可重新做**只读资源预检**，这不构成新的真实 audit；首次实际 audit 一旦建立 003 账本即消耗唯一尝试。一次启动采样与算出的 ceiling 写入 003 外部/镜像账本。`AUDIT_READY` 后、**建立 run invocation/锁之前**再做只读可用内存采样，要求 `available >= max(5 × 2^30 B, ceil(已冻结 ceiling / 0.60))`；低于门槛返回 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM`，保持 `AUDIT_READY`，可等待环境改善后再次只读准入，且没有 run 调用/fit 消耗。run 始终沿用 audit 冻结的 ceiling，绝不因新采样而升高，也不继承 001/002 的 2,127,893,299 B 上限。4 GiB 是新的研究硬上限，5 GiB 是最低准入条件，不是对完成率的保证；显存不计入。

家族累计 active wall ≤7,200 秒，含 001 的 3.5 秒和 002 的 17.547 秒；003 起始剩余 **7,178.953 秒**。家族累计 verifier fit wall ≤3,600 秒、fit attempts ≤25（前两轮均为 0）；candidate fit/predict 恒为 0；线程≤4。家族磁盘 ≤1,073,741,824 B，递归计入 001/002/003 输出、三份外部账本、003 锁及所有暂存，镜像文件由输出目录计入。旧研究峰值 RSS 是独立运行的历史记录，不累加到 003 的 RSS ceiling。

监督器每次 RSS 采样先记录数值、时间、worker PID/进程树摘要及**最后一个已完成的阶段标记**，再检查上限；超限采样也须在杀进程前尽力 fsync 到资源分段及外部/镜像账本，停止记录明确 `failing_measurement_bytes`，不能再把最后合格峰误写为失败值。阶段标记只反映处理步骤，不含 outer 性能：来源身份、cache geometry、global identity、candidate spool、score provenance、各 role context/物化、audit 完成、run role load、fit。遥测丢失、账本单侧缺失或无法证明超限值时按 `INCOMPLETE_RESOURCE` fail-closed，不推测数字。超限后不在同一 003 目录重试，也不临时调高上限。

## 4. 真实 audit 前的等价与资源证明

合成等价分层进行：旧 helper 的小 fixture 逐行比较旧/新 16D 输入、26D `float32` 数组（包括 NaN 拒绝）、ordered role keys、label sidecar、score reference hash/count、G3 相关 helper、`.npy`/JSONL 字节 SHA 与 role digest；测试不以浮点近似相等代替字节相等。旧完整 `run_audit` 硬编码来源规模，**不能**用小 fixture 跑通，也不得为小 fixture 放松生产计数门禁。用相同 fake backend 对完整 20+5 验证图比较 fit 输入字节、评分输入、阈值、decoder lineage、一对一匹配与科学判定；扰动 outer GT 不得改变该折选择或预测。003 新代码/测试使 A2 code identity 与 002 历史 digest 自然不同，必须冻结新的 003 digest；fit signature 包含完整 config，可因 003 namespace/资源元数据不同而变化，但科学输入、模型参数、选择和事件结果必须等价。确认 A1 45 个代码路径、旧 001/002 配置与产物、`features.py` 的特征计算函数、A1 decoder/metrics 的 hash 不受改动。新 003 代码身份、配置 sidecar 和允许路径 diff 需在真实 audit 前冻结。

另用**纯合成规模数据**运行一次资源演练，覆盖 632,100 个唯一窗口、72,112 候选、105 个 candidate role 和已批准设计记录的 **10,745,700 个 role/window 评分关联**；合成身份 JSON 不少于 147,814,536 B、候选 JSONL 不少于 288,130,586 B，support 长度和字符串长度采用明确记录的保守假设，而不能用极短/空 support 使解析负载虚低。合成来源文件与被测 003 输出分开计量；只测处理/装载内存和暂存磁盘，不调用模型，也不读取真实 A1 派生内容。演练须报告输入大小、假设、同监督器定义的 process-tree RSS 峰值、暂存峰值、每阶段驻留及**处理 wall**，并将处理 wall 与 7,178.953 秒剩余研究预算并列解释；fixture 生成/清理时间另列。峰值 RSS ≤`2.5 × 2^30 B`、家族口径估计磁盘 ≤1 GiB，才进入真实 audit。2.5 GiB 是事前工程**风险筛查**门槛，不是可据 outer 结果调整的参数；真实 support 分布、Python 对象膨胀与 HGB 拟合峰值没有独立上界证明，即使通过也不能承诺真实完成。失败时只允许在首次真实 audit 前修复本设计指定的资源生命周期/遥测实现并重测；无法满足则关闭 003 为未启动。

## 5. 研究顺序、停止与解释

前序身份、测试、合成内存演练、环境及只读内存准入全通过后，在固定 `a2-context-verifier-v1-003` namespace 调用真实 audit **一次**。仅当它产生哈希绑定的 `AUDIT_READY`，run 前才做**轻量** 003 配置/代码、001/002 前序小账本、READY 状态和当前 headroom 检查；不得在 run interval 外重新哈希 A1 282 listed artifact、1,127 cache 或全部物化 role。通过轻量准入后建立唯一 run 的锁与 active interval，在受监督 worker **第一项 fit 前**完整复核同一代码/config/A1 来源、role digest 与账本，然后运行完整 25 verifier role 验证。重哈希所耗时间和 RSS 属于这次 run 预算；若失败，run 已消耗并终态停止。任何身份/科学等价/G3/资源/实现门禁失败都终止该编号；不得再次调用 audit/run、另建 004 或按 outer 结果修改参数。完整结果才报告 pooled/五折事件指标及四项判定；失败只报告门禁与资源原因，性能仍 `NOT_EVALUATED`。

即使 003 `COMPLETE` 且 stage minimum 通过，也仅是已参与开发的 41 人五折证据；不成为独立确认、Formal G1 通过、full training 或 production 授权。无现场视频时，历史 75 段及新长 FP 的实际行为仍未知；对标签契约的 FP 改善只按该契约表述。完成或终止后再与用户讨论事件中心时序输出等架构路线，不自动展开新实验。
