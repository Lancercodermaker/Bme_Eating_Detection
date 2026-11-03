# A2-003 Resource Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只在一个新的、资源可证明的 003 namespace 中，取得固定 A2 26D 验证的合法性能结果；若拟合前工程证据或唯一真实尝试失败，就以相应终态停止。

**Architecture:** 锁定 001/002 终态和 001+002 已用预算；为 003 建立固定身份与新 RSS 准入；用有界角色读取/暂存替代 audit 和 run 的全量 Python 对象常驻；以合成旧/新对照保证 26D、嵌套选择与事件输出语义不变；最后只准一次真实 audit，`AUDIT_READY` 后只准一次 run。

**Tech Stack:** 现有 Python 3.10.11、NumPy 2.2.6、SciPy 1.15.3、scikit-learn 1.7.2、psutil 7.2.2、pytest；只使用 A1-005 已批准派生来源和 A2 历史产物。

---

状态：`ARCHIVED / A2_003_INVALID_CLOSED`。本计划记录 003 原执行门禁，**不得再次执行 Task 6**；以下“尚未启动”的文字是当时的历史交接，不代表现在仍可启动。真实结果及冻结哈希见[003 决定的终态更新](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)；下一编号另见[A2-004 决定](../../decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md)。本计划依据原[003 决定](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)和[资源设计](../specs/2026-09-24-a2-003-resource-recovery-design.md)。旧[002 决定](../../decisions/2026-09-23-a2-002-identity-contract-recovery-decision.md)的“不得追加 003”仅在当时被明确覆盖；001/002/003 的停止、科学定义和资产不可改。

### 当前执行交接：先补门禁，再决定能否开始唯一真实 audit

接续现有工作树，不从 Task 1 重做、不重置已暂存的 11 个 003 文件，不重跑 001/002，也不创建 004。前次报告的 Tasks 1–4 是已有实现及合成结果，仍需按本计划验收。Task 5 的 A2 回归组为 `126 passed, 1 failed`，唯一失败是旧 `tests/test_a2_recovery_namespace.py` 仍断言 003 未授权；A1 合同/事件/指标组报告 `15 passed`。最新只读 available 样本 5,270,237,184 B，低于 5 GiB 98,471,936 B。真实 003 audit/run/fit attempts 均为 0；没有 003 输出目录、账本、锁或 RSS ceiling。配置 SHA `dca4d895f5d65bf7df6583ddd935338fa614f91952103508bed5189dd1fbc993`、A2 code identity `7749c2d9168d2f7a586cef7e3c512b45b45e21934060607be777c8a77ca30517` 是**修复前快照**；所有静态身份在代码修复后重新只读核验并于真实 audit 前冻结。执行 agent 先独立核对这些报告值和 git staged/dirty 状态；不要以本段代替重新验证。

首次真实 audit 前还须解决以下已定位的工程阻断，只用合成输入证明，不读取真实来源或调用模型：

1. `control.py` 的父进程在 worker 返回 `AUDIT_READY` 后、写入 `run-status.json` 的 `AUDIT_READY` 前调用 `_light_a2_003_ready_check`，而检查器已要求该状态存在。修正状态与哈希绑定检查的顺序，增加合成 supervisor 的**成功 audit → 持久且哈希绑定的 AUDIT_READY**案例；同时证明假 report/sidecar/status 仍被拒绝，失败不会误放行 run。
2. `control.py` 的统一 preflight 会让 READY 后、run 前 available `<5 GiB` 错误返回 audit 型 `NOT_STARTED_INSUFFICIENT_HEADROOM`。调整 run 准入顺序，使其返回既定 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM`、保留 READY、不建 run interval/锁、不改冻结 ceiling；增加 `<5 GiB` 与冻结 ceiling 所需更高余量的边界案例。
3. `control.py` 的 run 失败停止记录目前在终态写入后用当前状态计算 `audit_ready`，会误报 `false`。以此前验证的 READY 历史及 hash-bound 文件作为依据，增加合成 run 失败记录案例；不得把历史 READY 误作最终 COMPLETE。
4. 旧 `tests/test_a2_recovery_namespace.py` 第 84–89 行唯一过时断言须只把被拒绝的研究 ID 从 003 改成未知的 004，保留其余 002 回归。本次用户继续同一 003 的授权及[003 决定交接补充](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)仅为这一行将该测试加入本计划文件 allowlist。该测试也参与完整 A2 code identity，修复后的旧 digest 不再有效。

现有规模演练报告 632,100 窗口、72,112 候选、105 role、10,745,700 关联及 1,107,476,480 B RSS；但关联在测试中直接构造 `ContextWindow`，没有在同一规模上经过 `_parse_score_rows`。Task 5 需补足纯合成 score 解析路径的全规模证据并记录其资源峰值；不能以现有演练的 RSS 代替完整真实 audit 或 HGB 拟合峰值。若 Task 5 的回归、等价、资源筛查或该覆盖要求不能证明，保持 `NOT_STARTED_GATE_FAILED`，不进入 Task 6。

## 固定工作树、文件图与不可触碰边界

执行工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。基线 A2 代码提交 `f363ea07d58664ede603159ac77fc5ce4630c9bd`。现有工作树有大量先前的 modified/untracked 文件；任何 reset、clean、整树暂存、额外 worktree、覆盖既有脏文件均禁止。只精确暂存本任务 A2 专属文件；若已有无关 staged 内容，跳过提交，不替用户处理。003 代码开始前保存 `git status --short`，结束后按文件核 diff；本计划的文档已存在，不能把 `docs/decisions/` 整目录当作本次变更。

| 文件 | 允许工作 |
|---|---|
| `configs/a2-context-verifier-v1-003.json`、`.sha256` | 固定 003 身份、双前序元数据及 RSS 资源条款；科学字段 canonical 等于 002 |
| `scripts/run_a2_context_verifier_003.py` | 固定 `preflight`、`audit`、`run` 入口；不接收自选研究参数 |
| `src/eating_event/a2/contracts.py` | 003 allowlist、配置文件/output 绑定；001/002 行为保持 |
| `src/eating_event/a2/budget.py` | 001+002 只读证据验证、累计账本与 003 家族磁盘统计 |
| `src/eating_event/a2/control.py`、`worker.py` | 准入、失败 RSS/阶段遥测、唯一尝试监督及身份传播 |
| `src/eating_event/a2/audit.py` | 只作身份/几何/候选内存生命周期和 run role 懒读取；26D 计算值不变 |
| `tests/test_a2_resource_recovery_namespace.py`、`test_a2_resource_equivalence.py`、`test_a2_resource_supervisor.py` | 新 003 正反例、旧/新合成字节对照、资源失败演练 |
| `tests/test_a2_recovery_namespace.py` | 仅将第 84–89 行过时的未知研究断言由 003 改为 004；其余内容保持 |

`src/eating_event/a2/features.py`、A1 全部代码/配置、A1-005 来源、001/002 配置/sidecar/runner/产物/账本、原 decoder/metrics、production 均不改。`execution.py` 默认不改；若只读 role 映射与现行调用不兼容，只允许修改数据装载/释放语句并补完整 fake-backend 等价证据，涉及拟合、选择、解码或指标公式则停在设计复审。不得读取或 stat raw sensor，不访问 official test、external data；A1 模型 pickle 仅可沿用既有 audit 作文件 hash 核验，不得反序列化或调用。不得将 A2 新结果用于 outer 参数搜索；candidate fit/predict=0。

执行中每个 Task 先新增能失败的**合成**正反例，运行该 Task 指定 pytest 命令观察因缺失 003 能力而失败，再实现最小变更并重跑至通过。测试不可调用真实模型 `predict`。每完成一个 Task 检查 `git diff --check`；提交前只 `git add` 精确路径，核 `git diff --cached --name-only` 与 `git diff --cached --check`，若有无关 staged 路径则不提交。任何真实来源的全量扫描、特征物化或拟合只准发生在 Task 6 的唯一 audit/run 中；Tasks 1–5 可读取既有 001/002 状态、配置、账本和 A1 manifest/code hash 作只读身份核验，不展开新的全量真实来源审计。

## Task 1：钉住双前序与固定 003 身份

**Files:** 新建 003 配置/sidecar/runner 和 `tests/test_a2_resource_recovery_namespace.py`；修改 `contracts.py`、`budget.py` 的前序验证入口。

- [ ] 写失败测试：003 只允许固定 `a2-context-verifier-v1-003`、`artifacts/a2-context-verifier-v1-003/`、`artifacts/a2-study-budget-v1-003.jsonl`、`.lock`，配置侧车按原始字节 SHA；任何任意 ID/path、篡改科学字段、A1 hash、threshold、HGB、seed、duration、fusion、角色数、非 RSS 预算均在读取来源前拒绝。001/002 默认及旧配置字节/hash 保持。新配置中 `predecessor` 是**001+002 家族摘要**（成员的固定哈希/状态和合计用量），不是旧 001 单一 predecessor；`limits` 唯一不同是 `rss_absolute_bytes=4×2^30`、新增 `rss_min_startup_available_bytes=5×2^30`，`rss_startup_fraction=0.6` 保持。
- [ ] 写失败测试：只读核验 001/002 两个终态、run-status、002 stop-record、配置、外部/镜像账本字节相等、无旧锁与完整输出树；丢失/篡改任一文件、单侧账本、非终态、002 有 run 或 fit 记录、002 没有对应 001 前序时都 fail-closed。固定 hash/树计数见 003 决定 §2。合计 active `21.047000000005937` 秒、fit wall 0、attempts 0 必须从两份账本验证后得到，不只信配置数值。
- [ ] 运行 `python -m pytest tests/test_a2_resource_recovery_namespace.py -q`，确认首先因缺 003 映射/双前序核验失败；实现 `expected_study_config`、`config_path`、`study_output_path` 和 `verify_predecessor_family_002`，再次运行至绿。`preflight` 只检查新配置/代码/env/前序和内存，不接触 A1 候选/cache/score，也不创建 003 输出/账本/锁；`audit` 在任何持久写入之前重复这些只读检查。旧 runner 再次调用仍拒绝旧终态。
- [ ] 仅在合成临时目录测试新 runner、worker、`run_audit`、`verify_audit_ready`、`load_audited_corpus` 的 ID/config SHA/output 三向绑定；拒绝使用 001/002 目录或伪造 request。检查 `current_a2_code_identity` 纳入 003 runner 与新测试。记录新配置 SHA 和代码 identity，后续若合法实现变更须在唯一真实 audit 前重新冻结，不在 audit 后改。

## Task 2：资源预算和失败遥测

**Files:** 修改 `budget.py`、`control.py`、`worker.py`；新建 `tests/test_a2_resource_supervisor.py`。

- [ ] 写失败测试：003 家族 active=001 3.5+002 17.547+本地，精确到 7,200 秒不能再开始；fit wall 和 attempts 用**仅合成**非零前序验证相加，25 次 reserve 的失败/中断均计数，candidate 仍 0；磁盘递归包含 001/002/003 输出、三份外部账本、003 锁及 role spool。任何旧目录消失、外部/镜像不一致、003 输出消失、账本开放 interval 或超限都 fail-closed。001/002 的现行预算测试必须继续通过。
- [ ] 写失败测试：003 的 `preflight` 在 available `<5×2^30` 时返回 `NOT_STARTED_INSUFFICIENT_HEADROOM`，真实 003 路径及 A1 来源均未访问；≥5 GiB 时 ceiling 精确为 `min(4×2^30,floor(available×0.6))`，不受 001/002 ceiling 影响。模拟 5 GiB、6 GiB、8 GiB 可用内存及边界 1 B；`audit` 持久化该启动样本。`AUDIT_READY` 后 run 前再要求当前 available ≥`max(5×2^30,ceil(冻结 ceiling/0.60))`；**包括当前 available `<5 GiB` 的情况**，不足均返回 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM`、保留 READY、无 run interval/fit，环境改善后可只读重检。run 必须使用 audit 的 ceiling，不能重新抽样提高。入口只能 `preflight|audit|run`，不接受上限/目录参数。
- [ ] 写失败测试：fake worker 在一个确定阶段上报 RSS 刚超限，supervisor **先 fsync** 原始失败采样、上限、采样时间、PID、最后已完成阶段，再终止进程树；检查输出资源分段与外部/镜像账本一致、停止记录中的 `failing_measurement_bytes` 为超限值而非最后合格峰。另测 RSS 采样失败、阶段标记缺失、worker 突退、disk/fit wall 超限；没有可证明遥测时一律 `INCOMPLETE_RESOURCE`，不产生 `AUDIT_READY`/性能。
- [ ] 运行 `python -m pytest tests/test_a2_resource_supervisor.py tests/test_a2_control.py tests/test_a2_recovery_namespace.py -q` 观察新案例先红后绿。合成 supervisor 正向案例还须覆盖合法 worker audit 到 hash-bound `AUDIT_READY` 的父进程收尾，以及其后模拟 run 失败的 stop-record 历史 READY；保留坏 sidecar/status 的拒绝案例。实现中把 003 preflight/双前序验证放在创建锁/输出/账本**之前**；真实 audit 初始化时外部账本首条是固定双前序记录。003 ledger 的每条记录绑定 study ID/config SHA/output。旧 001/002 路径和 RSS 计算分支不得变。

## Task 3：有界 audit、逐行语义等价

**Files:** 修改 `audit.py` 的几何/身份、候选读取及 role 生命周期；新建 `tests/test_a2_resource_equivalence.py`。

- [ ] 在改代码前，分层生成基线 `f363ea0` 的**纯合成** golden：小 fixture 仅调用现有 identity、score、support、`_materialize_role` 等 helper，覆盖交错 role、跨 role 重复 bare ID、全窗位置、被排除注释、hard gap、半开窗口端点接触、无/坏 support、缺 score、outer label 非 null；固定 helper 的 16D 值/序列、26D `float32`、reference row hash/count、`.npy`/JSONL bytes SHA 与 role digest。旧完整 `run_audit` 硬编码 1,127 records、632,100 windows、72,112 candidates、130 provenance 等门禁，**不得**为小 fixture 放松生产计数或伪称完整 audit golden。G3/outer 覆盖/FN 分类分别对旧 helper 或小的纯合成规则输入做对照；完整 20+5 图留给 Task 4 fake backend，规模路径留给 Task 5。任何 golden 不可来自真实 outer 结果。
- [ ] 写失败测试：全量候选不能以 72,112 个 Python dict 加多份引用常驻；单次按行校验并依源顺序分 role 写入**003 内受磁盘监督的**暂存，只保留 `_parse_score_rows` 必需的轻量有序 candidate ID 索引；复合 key 与全部标签/边界/support 谓词照旧。即使输入 role 交错，role 内次序和写出的 materialized JSONL/矩阵字节与 golden 一致。重复 key、坏 16D、越权 role、缺 score、缓存成员不符仍拒绝。spool/物化写入前按预计新增字节与**保留 4 MiB 关键遥测/终态空间**预检家族磁盘；超限即停止并保留资源证据，不能先写到满额再无处写停止记录。
- [ ] 写失败测试：几何与全局 identity 的每行值、顺序、stable/global index 映射都照旧验证，但原始身份 JSON 容器及第二份复制不能同时常驻至候选物化；按完整 record/role 有界构建 `A1Window`/`ContextWindow`，不得切断相邻窗口的 support component，score reference stable ID 排序和 reference row hash/count 不变。现行 `_all_training_rows`、outer coverage、A1 FN 分类必须在 role 生命周期内有界累计或按需读取已监督暂存；不能在末尾把全部候选再次装进 dict。`model-provenance.jsonl`、`score-provenance.jsonl` 解析对象在最后必要使用后释放或有界读取。源文件实际 hash 在真实 audit 中仍逐个认证；合成测试对错序、重复 stable ID、coverage/gap/时间类型错误仍 fail-closed。`build_a2_features` 与 `_materialize_role` 的值计算不改。
- [ ] 运行 `python -m pytest tests/test_a2_resource_equivalence.py tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_recovery_identity.py -q`，新增案例先红后绿；逐个比较 golden 的数组元素 `np.array_equal`、二进制矩阵/JSONL SHA、role digest、标签 sidecar 和 G3，而非仅比较汇总计数。检查暂存清理只在 003 自有目录、路径先规范化并限制在该目录内；任何异常都保留终态和账本，不能删旧文件或重用已开始的 003。

## Task 4：有界 run 装载与 fake 20+5 等价

**Files:** 修改 `audit.py::load_audited_corpus` 的 role 映射；仅若必要修改 `execution.py` 的装载/释放；扩充 `tests/test_a2_resource_equivalence.py` 与 `tests/test_a2_pipeline.py`。

- [ ] 写失败测试：`AUDIT_READY` 仍先验证全部 role 文件 SHA 与身份摘要，但 003 corpus 不同时构造全部 105 role 的 `A2Candidate`。每次 `get`/索引装入一个 role，验证 ordered key、26D matrix、独立 label join、outer label null；再次读取返回同样字节与顺序。变更 materialized 一字节、某 role 缺失或重复都在 fit 前拒绝。旧 001/002 loader 行为不变。
- [ ] 用固定 fake verifier backend 对旧 eager 与新 bounded loader 的所有 20+5 角色作逐项比较：每次 fit 的 role、feature `float32` bytes、label bytes、participant 序列、G3；每次 score 输入/输出；每折选择元组和阈值；预测区间、lineage、匹配、TP/FP/FN、long-FP、MAE 和四项 numeric/stage 状态。003 配置身份变化会改变包含完整 config 的 fit signature；仅允许该身份签名不同，不能放宽任何科学输入或事件输出比较。再扰动 outer GT，确认该折 selection/predictions 不变；6C7 无 GT 仍保留。比较只用合成 fixture，不调用真实 HGB fit/predict。任何差异必须在首次真实 audit 前解决或停止。
- [ ] 运行 `python -m pytest tests/test_a2_resource_equivalence.py tests/test_a2_pipeline.py tests/test_a2_audit.py -q`，新增断言先红后绿。若需改 `execution.py`，diff 只可涉及 role 生命周期；`_fit`、`_score`、selection、`_decoded` 和 evaluator 调用不变，另作逐行代码审查。不能因为真实 003 run 结果再回头选择缓存策略。

## Task 5：预拟合冻结与一次合成规模资源演练

**Files:** 上述新测试与 003 runner；只读审查 003 决定、配置、代码差异、A1/A2 前序身份；此 Task 不运行真实 A1 来源 audit/fit/predict。

- [ ] 在隔离临时目录生成固定、纯合成的 632,100 窗口/72,112 候选/105 candidate role/10,745,700 role-window score 关联；合成身份 JSON 序列化大小至少 147,814,536 B，候选 JSONL 至少 288,130,586 B，记录 support 长度、字符串长度、大 role 与大 record 的假设，不能用短/空 support 制造虚假余量。旧小 fixture、完整 fake 图和此规模演练是**三种不同证据**，不放松真实 `run_audit` 计数门禁。现有演练直接生成同数目的 `ContextWindow`；真实 score 解析的同规模覆盖仍需核实或补足，记录解析峰值及阶段，不能沿用未覆盖路径的 RSS 数值。执行 audit 数据处理及 run role 装载，但不拟合/预测任何模型；用与真实监督器相同口径记录 process-tree RSS 峰值、输入/暂存/物化磁盘峰值、每阶段**处理 wall**，与剩余 7,178.953 秒并列解释，fixture 构造/清理时间另列。工程筛查门槛 RSS ≤`2.5×2^30 B`，按 001+002 已用量叠加的估计 family disk ≤1 GiB；该演练不证明真实 HGB 峰值。若峰值不可信、无阶段记录或门槛失败，只在本计划允许的资源代码内修正并重新验证；不得消耗真实 audit 来定位问题。
- [ ] 运行 `python -m pytest tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_pipeline.py tests/test_a2_control.py tests/test_a2_recovery_identity.py tests/test_a2_recovery_namespace.py tests/test_a2_resource_recovery_namespace.py tests/test_a2_resource_equivalence.py tests/test_a2_resource_supervisor.py -q` 与 `python -m pytest tests/test_a1_contracts.py tests/test_a1_events.py tests/test_a1_metrics.py -q`；要求退出码 0，记录**实际**通过数。不要运行会调用旧 candidate estimator 的 full suite。
- [ ] 核对 A1 checksum manifest 自身 SHA `0543791e90df9e1bcf93111dc45e80678089898409e6888b90584fd18c469025`、282 listed entry、45 个注册 A1 代码 hash、001/002 各项固定 hash/输出树/旧锁不存在，以及冻结 Python/科学库版本。这里只读清单/代码及前序，不新开清单列出的全部对象；全部真实来源认证留给唯一 audit。对基线提交 `f363ea0` 审核只限本任务文件的 diff；`features.py`、A1、原 decoder/metrics、001/002 配置与 runner 的字节不变。002 停止记录中的 A2 code identity 是历史快照，不得与新增 003 文件后的 current digest 比较并误拒；003 配置除 namespace、双前序、RSS 资源条款外科学 canonical 投影等于 002。记录并冻结新的 003 config raw SHA、完整 `current_a2_code_identity` 及环境版本。
- [ ] 检查所有真实 audit 入口只允许 003 固定路径、一次空账本开始、唯一 audit、`AUDIT_READY` 后唯一 run；审查 `preflight` 低内存不会留下 003 路径。对 16 GB 机器做**启动当时**的只读可用主内存检查；若 `<5 GiB`，返回 `NOT_STARTED_INSUFFICIENT_HEADROOM`，等待机器资源改善，此时没有真实研究尝试。`preflight` runner 的 shell 退出码可能为 0，即使 JSON status 是 `NOT_STARTED_*`；必须以 JSON status 和持久产物检查判定是否准入。若科学等价、来源边界、旧 hash、合成余量或代码身份任何一项不能证明，报告 `NOT_STARTED_GATE_FAILED` 并停止，不能新建 003 输出/账本。

## Task 6：唯一真实 audit；仅 READY 后唯一 run

**Files:** 仅新建固定 `artifacts/a2-context-verifier-v1-003/`、`artifacts/a2-study-budget-v1-003.jsonl`/镜像及执行期间锁；旧产物只读。

- [ ] 从指定 worktree、冻结代码/config 与 ≥5 GiB 启动可用内存下，只执行 `python scripts/run_a2_context_verifier_003.py audit` **一次**。其首次持久事件绑定两个前序及配置身份，开始累计 001+002+003 active wall；audit 可读取获批派生 cache/score、构造 26D，无任何模型 fit/predict。要求 `AUDIT_READY`、105 role 有序键/26D `float32`/独立标签摘要、G3、来源/代码/配置 hash、真实资源台账齐备。任何非 READY、资源采样缺失或 source 契约冲突，立即关闭 003；不得在同目录再次 audit、换目录、提高 cap 或开 004。
- [ ] **仅在** `AUDIT_READY` 后，run interval/锁前只轻量检查固定双前序小账本、同一 config/code 身份、READY 状态、003 startup RSS ceiling、账本/磁盘/剩余预算及当前 available ≥`max(5×2^30,ceil(冻结 ceiling/0.60))`；不足时保留 READY 并等待机器环境改善，可重复**不读 A1 来源**的准入，不能提高已冻结 ceiling，也不算 run 调用。通过后执行 `python scripts/run_a2_context_verifier_003.py run` **一次**；**在已开始计时和 RSS 监督的 run worker 内**重哈希 A1 282 listed artifact/1,127 cache、全部 role 文件、source 与实际 fit 输入 digest，首个 fit 前全部核验通过。不得把重哈希挪到 run interval 外；重哈希失败算唯一 run 且终态停止。随后才执行完整 20+5 角色图，最多 25 verifier fit attempts（reserve 前记账）；candidate fit/predict 均 0；任何已开始的 run 失败/中断不重试。
- [ ] 若 `COMPLETE`，记录 pooled 和五折 TP/FP/FN、precision/recall/F1、长 FP 比例、start/end MAE、234 GT/6C7、阈值及来源、A1 FN transition、四项 numeric/stage 状态、25 fit 的资源台账、003 config/code/source hash。若未完成，四项为 `NOT_EVALUATED`，只说明真实门禁失败与失败采样值/阶段（若可证明），不能算性能失败。对历史 75 段和新长 FP 仅写标注契约下的 FP，不声称实际行为被视频核验。
- [ ] 完成或终止都在 003 输出留下状态/停止或完成记录，重新只读验证 001/002 hash 与 003 外部/镜像账本一致，精确报告 active/fit/attempt/disk/RSS 和唯一 audit/run 调用数；保留 A1 CLOSED、Formal G1 FAIL、full training BLOCKED、production UNCHANGED、无独立 participant 确认。将结果交还用户，再讨论架构重设计；不自动开展实验。

## 最终自审

- [ ] 将[003 决定](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)每个允许差异、门禁、哈希、预算及停止条件对应到 Task 1–6；检查旧 002 “不追加 003”冲突已显式限定覆盖范围，001/002 始终终态。
- [ ] 确认 `preflight` 只读且不消耗真实研究，真实 audit 一次、run 最多一次；版本/代码/config/数据身份在 fit 前仍严格；合成测试与真实验证在报告中分别标识。若任何文档/实现/产物冲突未解决，在真实 audit 前停止并列证据。

本计划只授权上述单一资源恢复验证。即使 A2-003 产生性能结果，也仅为开发折证据；后续事件中心架构、独立确认或 full training 需另行讨论与决定。
