# A2-002 Identity Contract Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

本 Codex 环境中的可用 skill 名称为 `subagent-driven-development` 和 `executing-plans`；上行 `superpowers:` 是计划模板惯例。仅在另开的执行对话使用执行 skill。

**Goal:** 在不改变 A2 固定 26D 科学定义和 A1 来源的前提下，修正两处 A2 身份审计误拒，并以独立、继承原预算的 `002` study 完成最多一次开发验证。

**Architecture:** 保留 001 终态与所有字节；002 使用独立的冻结配置、runner、输出、外部账本和锁。两个小范围 audit 校验修订允许已批准的排除行，同时继续严格保护所有被实际使用的 cache entry 和合格 GT；通过合成反例、静态来源契约审查和 hash 冻结后，才调用一次受控 audit，并仅在 `AUDIT_READY` 后调用一次 run。

**Tech Stack:** 现有 Python 3.10.11、NumPy 2.2.6、SciPy 1.15.3、scikit-learn 1.7.2、psutil 7.2.2、pytest；现有 `eating_event.a1`/`eating_event.a2` 源码和获批派生产物。

---

状态：`PLAN_READY / NOT_EXECUTED`。本计划受[002 修订决定](../../decisions/2026-09-23-a2-002-identity-contract-recovery-decision.md)约束；旧[001 执行计划](2026-09-23-a2-context-verifier-validation-implementation.md)中的科学、隔离和评价细节继续适用，旧计划固定 `001` namespace/单次授权和 `NOT_EXECUTED` 状态均为历史。用户明确要求在**另一个对话**执行；本轮只写文档。工作树为 `E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`，已存在大量历史 dirty/untracked 文件，禁止新建 checkout、清理、reset、`git add .` 或顺带提交别的变更。

## 文件地图和不变量

| 文件 | 本次职责 |
|---|---|
| 新建 `configs/a2-context-verifier-v1-002.json`、`.sha256` | 精确复制 001 科学字段，冻结 002 namespace、前序终态/hash 和预算承接。旧 `configs/a2-context-verifier-v1.json`/sidecar 不变。 |
| 修改 `src/eating_event/a2/contracts.py` | 精确 allowlist 的 001/002 config loader；002 配置与 001 科学字段逐字段相同；无任意配置路径。 |
| 修改 `src/eating_event/a2/audit.py` | 两项排除语义修订、002 config 身份传递、代码身份包括 002 runner；其余数据和 26D 特征规则不变。 |
| 修改 `src/eating_event/a2/budget.py`、`control.py`、`worker.py` | 显式固定 001/002 study 路径、独立 002 账本/锁、001 终态/hash 与资源消耗承接、worker 双层校验、动态完成态 provenance。 |
| 新建 `scripts/run_a2_context_verifier_002.py` | 只暴露无参数 `audit`/`run`；硬绑定 002。旧 runner 仍指向终态 001，不能变成 002 入口。 |
| 新建 `tests/test_a2_recovery_identity.py`、`tests/test_a2_recovery_namespace.py` | 合成正反例与跨 study fail-closed 检查。 |
| 只读 `src/eating_event/a2/features.py`、`execution.py`、`inputs.py`、全部 `src/eating_event/a1/`、001 配置/产物/账本 | `git diff 630ab30d8d5a1696b246868ab45a894ba33cb622 --` 对这些源代码/配置必须为空；不要“顺手”修模型或科学接口。 |

002 固定路径：`artifacts/a2-context-verifier-v1-002/`、`artifacts/a2-study-budget-v1-002.jsonl`、`artifacts/a2-study-budget-v1-002.lock`；输出内镜像可用 `a2-study-budget.jsonl`。`001` 终态证据与旧账本 SHA-256 在[002 修订决定 §4](../../decisions/2026-09-23-a2-002-identity-contract-recovery-decision.md)固定。任何入口不得接受另一个 study ID、输出目录、阈值、seed、context width 或数据 root 作为 CLI 参数。

**禁止边界：**不读取或 stat raw sensor、不访问 official test/external data、不加载 A1 模型 pickle、不改 A1 产物/NPZ/标签/sidecar/production。候选模型 fit/predict 为 0；真实 verifier fit 尝试总额 25。001 不可再次 audit/run。所有 41 人已开发暴露，002 即使完成也不是独立确认。

## Task 1：冻结 002 身份，证明科学字段不变

**Files:** 新建 `configs/a2-context-verifier-v1-002.json` 与 `.sha256`、`scripts/run_a2_context_verifier_002.py`；修改 `src/eating_event/a2/contracts.py`；新建 `tests/test_a2_recovery_namespace.py`。

- [ ] **先写失败的合成测试：**002 配置解析必须只允许新 `study_id`、`study_output`、固定 ledger/lock 及 predecessor 元数据与 001 不同。将两个配置除这些允许差异外的 canonical JSON 比较为完全相等；任一 26D 特征名、HGB 参数、角色数、阈值、duration、fusion、seed、预算或 A1 source hash 变化均拒绝。旧配置与 sidecar 的 SHA 必须仍为 `f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5`。
- [ ] 运行 `python -m pytest tests/test_a2_recovery_namespace.py -q`，确认新断言因缺 002 loader/config 而失败；实现显式 `study_id` allowlist 与固定配置文件映射，再运行同一命令至通过。旧 `load_config(root)` 默认行为仍为 001；002 runner 必须显式选择 002。对 002 配置原始字节生成 `.sha256`，每次 audit/run 都先核 sidecar。
- [ ] 002 runner 只接受 `audit` 或 `run` 一个位置参数，确认 cwd 为现有工作树，将固定 `study_id`、配置 SHA 传给控制器；不要复制旧 runner 中硬编码的 `50 passed / 15 passed`，在最终测试通过后记录实际测试输出并再次冻结 runner 代码 hash。旧 runner/配置/001 文件不得改。用临时目录的合成 001 terminal ledger 测拒绝行为，**不可实际调用旧 001 runner**。
- [ ] 复核 `git status --short` 和 001 三个固定 SHA；只暂存本任务文件并确认 `git diff --cached --name-only` 不含历史脏文件。测试绿后才可单独提交本任务文件；若已有无关 staged 文件，跳过提交而不要动它们。

## Task 2：修正两个 A2-only 审计误拒

**Files:** 修改 `src/eating_event/a2/audit.py`；新建/扩充 `tests/test_a2_recovery_identity.py`。

- [ ] **先写失败的 manifest 合成反例：**一个 `processed` 行有非空 ID，与同 participant/session 的 cache entry 唯一关联；另有 `skipped_invalid_session` 行缺字段、`excluded_test_participant` 行 ID 为 `None`，均不产生 cache entry，此例应通过。反例分别包括 `processed` 缺字段及显式 `None` ID、任意两个非空 ID 重复、cache entry 漏配、cache 对应 nonprocessed、participant 或 session 不符，全部应 `INVALID`。不准把 `None` 转为字符串 `"None"`。把索引与 cache-entry 关联提取为一个由 `_load_cache_geometry` **实际调用**的纯 helper，用小 fixture 测该 helper；代码审查再确认真实 loader 没有绕过它，避免为单元测试生成 1,127 个缓存文件。
- [ ] 运行 `python -m pytest tests/test_a2_recovery_identity.py -q`，预期上述正例因旧“每行有 ID”检查失败。修订索引时只允许非 `processed` 行缺 ID；对所有**非空** ID 仍查重，对每个 cache entry 仍要求唯一 `processed`、participant/session 匹配。使用 `record.get("path_or_file_id")` 的实际空值判断，拒绝缺 ID 的 `processed` 行。再次运行该测试文件至通过。
- [ ] **再写失败的资格反例：**资格表含缓存外 participant 的不合格注释，训练/评价标志均 false，且另有 234 个合格评价 GT；缓存成员检查应仅针对合格 GT。分别把一条缓存外注释改成**仅训练资格为 true**、**仅评价资格为 true**，两例都必须失败。全部 281 注释行、原文件 hash、排除理由仍保留；6C7 无餐仍在 41 人。先看到旧集合检查失败，再仅移动/调整 eligible participant 收集位置；不得改 GT 计数、标签或特征输入。
- [ ] 运行 `python -m pytest tests/test_a2_recovery_identity.py -q` 及 `python -m pytest tests/test_a2_audit.py -q`，均需通过。检查本任务 diff 只改变 audit 身份/资格校验和版本传递；不得改变 `_materialize_role` 的 26D 算法或 outer 指标。按 Task 1 的精确暂存规则提交。

## Task 3：独立 002 账本并承接 001 资源消耗

**Files:** 修改 `src/eating_event/a2/budget.py`、`control.py`、`worker.py`、`audit.py` 的 config/代码身份调用；扩充 `tests/test_a2_recovery_namespace.py`。

- [ ] **先写失败的资源/身份测试：**旧 001 的 `INVALID` 无法重启；002 的 config/output/ledger/lock 与 001 互不混用；**首次 audit 建立账本之后**，若新输出目录消失或新外部/镜像账本一侧缺失即 fail-closed。public runner、worker、`run_audit`、`verify_audit_ready` 和 `load_audited_corpus` 各自面对错误 config SHA、study ID 或解析后 output 路径均在读取来源/拟合前拒绝；002 第二次 audit、终态后的 run 或第二次 run 都拒绝。旧 001 产物/账本字节在测试中不变，旧 runner 默认绑定 001 的兼容性用**合成终态**证明。新增 002 runner 必须出现在 `current_a2_code_identity`。
- [ ] **先写失败的预算测试：**002 账本首个 predecessor 记录与 001 状态/旧外部及镜像账本固定 hash 对齐，从旧账本派生 3.5 秒 active wall、0 fit 秒、0 attempts；002 加上自身消耗后仍受合计 7,200/3,600 秒、25 attempts 约束。精确边界例：前序 3.5 s + 002 7,196.5 s 恰达 7,200 s 不可再启动新操作，任何多出的时间必须拒绝；用**仅限合成 fixture**的非零前序 fit 秒/attempts 证明两项也真正累计，而非只在 ledger 留记录。002 RSS ceiling 必须是 `min(8 GiB, 2,127,893,299 bytes, 0.60 × 新启动 available bytes)`；新磁盘计数包括当前 001 目录与旧外部账本以及 002 目录、新外部账本/锁和临时文件。`check_disk_budget` 目前只递归 output，对 `external_paths` 的目录不会递归；用含大文件的合成 001 目录证明确实计入限额，并让 `control.py` 的各次采样、收尾检查和完成态 manifest 使用同一聚合函数。篡改旧终态/hash、单独删除一个账本、丢失资源测量都不得变成新的零预算。
- [ ] 运行 `python -m pytest tests/test_a2_recovery_namespace.py -q` 观察旧硬编码路径导致失败；再实现只有 001/002 两项的固定路径映射，并在 `control.launch`、`StudyLedger`、worker request/response、`audit.run_audit`、`verify_audit_ready`、`load_audited_corpus` 和完成态 manifest 传递/核验同一个 002 study ID、配置 SHA 与固定 output。`audit.py` 当前三处无参 `load_config(root)`（约第 621、1023、1098 行）都必须改为显式 002 选择；各入口自己校验 output 等于配置解析路径。保留 001 终态拒绝语义。预检阶段只读验证前序，不写真实 002 账本；`StudyLedger.assert_can_start_audit()` 目前要求新账本为空，须在**唯一一次** `launch('audit')` 确认空账本后写首个 predecessor 事件，紧接记录启动采样；或明确调整判定只允许该唯一固定 predecessor 事件。测试不触碰真实 002 路径。测试通过后运行 `python -m pytest tests/test_a2_control.py tests/test_a2_recovery_namespace.py -q`。
- [ ] 复核预算快照显示 **前序 + 002** 而非仅 002；`worker.py` 不写旧目录；`control.py` 完成态 manifest、metrics 和账本快照均有 002 study ID、001 前序 hash/继承用量、001+002 合计，外部与镜像路径动态指向 002。按精确暂存规则提交。若必须修改 `features.py`、`execution.py`、A1 或科学配置才能打通，停在设计审查，不扩大本授权。

## Task 4：预拟合静态审查、合成演练和冻结

**Files:** 只读审查上述修改、原 A2 源码及**已冻结的来源报告/审计证据**；测试文件同 Tasks 1–3；本任务不运行真实来源 audit，也不新做全量真实数据核验。

- [ ] 用下表逐项核对**实现谓词、批准来源语义、既有只读证据与合成正反例测试**；任何行缺代码路径或测试，先在第一次真实 audit 前补齐，不凭 001 的 50 个通过数认为来源就绪。表中数量为既有记录的期望值，不授权在 Task 4 重新扫描全部 cache/score 或物化特征；新全量来源核验只能在 Task 5 的唯一 002 audit 内计时进行：

| 门禁 | 批准语义 / 预拟合证据 |
|---|---|
| A1 checksum/code/env | 282 个 listed artifact、45 个注册 A1 路径、冻结 Python/科学库版本，hash 逐项一致；002 代码身份另冻。 |
| manifest/资格 | 1,163 审计行中 1,127 `processed` 唯一关联 cache；两条无 ID 的排除行不作为 cache。281 注释保留，只有合格 GT 进入 41 人，评价 GT=234。 |
| cache/window/role | 1,127 cache、632,100 全局窗口；5/4/4 role=105 candidate+25 verifier；outer 有效人不进入 fit/reference/selection。 |
| score/candidate | 每 candidate role 的全部评分窗口位置有序一致，`relative=raw-threshold`；复合 `(role_id,candidate_id)`；72,112 role-qualified 候选，outer `[946,892,929,653,763]`。 |
| support/feature/G3 | 从全部 scored windows 重建 component，`source_segment_id=null`；label-free 16+10，有限 26D，post 末端门禁；25 个角色在 fit 前各自 G3。 |
| budget/status | 001 仍 INVALID；002 的 audit/run/账本/输出/资源前序绑定，终态拒绝重试。 |

- [ ] 运行 `python -m pytest tests/test_a2_features.py tests/test_a2_audit.py tests/test_a2_pipeline.py tests/test_a2_control.py tests/test_a2_recovery_identity.py tests/test_a2_recovery_namespace.py -q`，再运行 `python -m pytest tests/test_a1_contracts.py tests/test_a1_events.py tests/test_a1_metrics.py -q`；均要求退出码 0，记录**实际**通过数与环境。不要运行会在旧测试中调用 candidate estimator 的 full suite。用 fake verifier backend 演练完整 20+5 角色，确认 0 candidate fit/predict、外层 GT 扰动不改变该折选择/预测、零 GT 的 6C7 保留。
- [ ] 对提交 `630ab30d8d5a1696b246868ab45a894ba33cb622` 做允许路径差异审查；`src/eating_event/a2/features.py`、`execution.py`、`inputs.py` 和旧 001 配置/runner 的 diff 必须为空。全部已登记 A1 代码路径按 A1 `run-manifest.json.code_identity` 的 45 个 hash 核验；不要把当前工作树先前的脏文件与 630ab30 作整树差异后误判为本次改动。检查新增 002 配置除 namespace/predecessor 元数据外与 001 科学字段 canonical 等同；旧 001 状态、输出树、外部和镜像账本 hash 未变。冻结 002 config sidecar、A2 代码哈希和 approved A1 输入 hash；把已知剩余不确定性记录在新 study notes。
- [ ] 若上述任何失败，在**尚未启动真实 002 audit**的实现阶段仅修复本决定明确的两项验证器谓词或 002 namespace/预算承接，并重跑相应合成测试。其他来源契约冲突、科学定义、已批准来源或资源上限需要更改时，停止并另行审查，不开展预算外的“影子 audit”，也不开始真实研究。通过后才进入 Task 5。

## Task 5：一次真实 audit；仅 `AUDIT_READY` 后一次 run

**Files:** 新产物只能写到固定 002 输出和账本/锁；旧 001、A1 和 production 只读。

- [ ] 在指定工作树运行 `python scripts/run_a2_context_verifier_002.py audit` **一次**。它可以读取经 hash 批准的 A1 派生 cache/score/ledger 和构造 26D 特征，不能 fit/predict 任何模型；首个真实 audit 开始计入 002 新消耗并叠加 001 的 3.5 秒。要求 `AUDIT_READY`、完整身份/角色/特征/G3/资源审计、role 顺序及 `float32` 矩阵和独立标签 join 的 hash。若状态为 `INVALID`/`INCOMPLETE_*`，立即终止 002，报告具体门禁；不得同目录重复 audit 或新建 003。
- [ ] **仅当** `AUDIT_READY` 且代码、配置、来源、实际拟合矩阵/标签摘要、账本、001 前序证据全部重新核验一致时，运行 `python scripts/run_a2_context_verifier_002.py run` **一次**。最多 25 个 verifier fit attempt、0 candidate fit/predict；旧 A1 decoder/evaluator、inner 阈值选择和 outer 一次评价规则完全沿用。失败/中断的 fit 计入预算且不重试；无合法 `COMPLETE` 不产出数值性能判定。
- [ ] 只有 `COMPLETE` 才报告 pooled/五折 TP、FP、FN、precision、recall、F1，234 GT/6C7、候选覆盖、long-FP fraction、start/end MAE、四项 numeric/stage 状态、阈值与来源、fit/资源台账、001+002 合计预算及新旧代码/config/input hash。对 75 段历史长 FP 只说明批准标注契约下的变化，真实行为仍未知。保留无独立 participant confirmation、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。
- [ ] 在 002 完成或终止后生成只引用实际产物的结果/停止记录，向用户返回完整路径和下一步架构讨论所需结论。stage minimum FAIL 则关闭固定 26D；stage minimum PASS 也只记开发折支持。任何新门禁失败不能引发 002 再跑、003 自动创建、outer 参数选择或来源修补。

## 自审与交接

- [ ] 逐条映射[002 修订决定](../../decisions/2026-09-23-a2-002-identity-contract-recovery-decision.md)到 Tasks 1–5；核对两项允许校验修订、001 终态、002 namespace、预算承接、科学定义、测试和停止规则没有遗漏。
- [ ] 检查所有本计划路径、状态名、配置键、命令、测试文件及结果字段一致；没有允许 `001` 复活或把 002 当独立确认的措辞。执行者遇到本文与实现/既有产物的未解决冲突，先列证据并停在门禁前，不静默选一边。

本计划不在当前对话执行。用户已授权的是上述**单次 002 恢复验证**，不是一系列新试验；结果返回后再讨论架构级重设计。
