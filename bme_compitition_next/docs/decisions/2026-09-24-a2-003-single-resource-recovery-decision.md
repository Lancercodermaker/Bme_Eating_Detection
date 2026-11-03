# A2-003 单次资源恢复验证决定

日期：2026-09-24  
状态：`A2_003_INVALID_CLOSED / PERFORMANCE_NOT_EVALUATED`。下文原授权与交接段落保留为执行前历史记录，不再允许按其启动 003。

## 2026-09-24 真实 audit 终态（覆盖下文执行前状态）

003 唯一真实 audit 已启动并终止为 `INVALID`；audit=1、run=0、verifier fit attempts=0、candidate fit/predict=0，未生成 `AUDIT_READY` 或 sidecar。四项 A2 numeric/stage 均为 `NOT_EVALUATED`，不能据此计算或推断 A2 F1。`run-status.json` SHA-256 `4039ef151dd47f48ab11436d1c7e583b7f592c72eb2617db27d07e39630b3315`；停止记录 SHA-256 `a6f17a77b652e9bf95c43083e7c0f1b27becbdc4450ea81b1d0e2b2d73466b74`；003 外部/镜像账本逐字相等，SHA-256 `eae9f876cf0cf3c58a49e3fe6da5bbc74ced55d7791074227eafccae6191cbae`；输出树按本决定 §2 算法为 164 文件、339,692,500 B、SHA-256 `fa999f999b99ef783249d607e53eadd88359232afe5c93100c7d545c4264e7ec`。003 冻结的 A2 code identity 是 `b60e9cd5dd9138210af665b6f0124d76fd99ba7fe7e27fe169237287aeeec918`，配置 SHA 仍为 `dca4d895f5d65bf7df6583ddd935338fa614f91952103508bed5189dd1fbc993`；`frozen-study-identity.json` SHA-256 `d39aa40d4207668a89db34f6de5f8c9f3d24ac3267cab9bc120cf7e4d0328f5c`。再次核验前序 001/002 与当前 003 输出须只读，任何产物和账本不可清理、改写或迁移后伪作同一次验证。

003 audit 用时 123.641 秒；001+002+003 家族累计 active wall 144.688 秒，fit wall 0，verifier attempts 0。process-tree RSS 峰值 767,606,784 B，冻结 ceiling 3,612,401,664 B；停止记录 family disk 339,947,030 B。失败记录只指出 `materialized/training-labels/d660fffa1ac2e96ba1bd.jsonl.tmp` 的 `FileNotFoundError`；该目录和同名最终 `.jsonl` 在终态产物中存在，最终文件早于终态约 70 ms，因此**不能**把“目录没创建”定为根因。代码中 `_write_jsonl` 写前创建父目录并将 `.tmp` 原子替换；监督器在 worker 写文件期间高频扫描磁盘，`check_disk_budget` 先枚举短寿命 `.tmp` 再延后 `stat()`，与 rename 竞态可产生完全相同的异常。没有持久化 traceback，故这是高置信机制推断，仍需下一编号的确定性合成故障注入来证伪。资源摘要显示 worker 被监督器终止且无 worker response，支持异常来自监督计量。用户另报告 runner 在持久化终态后向 cp1252 终端打印中文错误时发生 `UnicodeEncodeError`；该显示故障不改变持久终态，但下一 runner 须做编码安全回归。

真实 audit 前报告的 A2 回归为 136 passed、A1 合同/事件/指标为 15 passed。纯合成规模演练覆盖 10,745,700 个经 score 解析的关联，解析 wall 86.75 秒/RSS 峰值 1,214,140,416 B；整段 RSS 峰值 1,237,483,520 B，估计家族磁盘峰值 709,711,113 B。这些证明当时的拟合前工程门禁通过，不证明真实 audit 必能完成或真实 HGB 资源上界。

已开始 audit 的失败按本决定 §4 消耗唯一机会，003 永久关闭，不得修复代码后复用、清理目录再试或把失败称作性能不达标。用户随后要求下一次 A2；新的单次编号与资源决定见 [A2-004 决定](2026-09-24-a2-004-single-disk-race-recovery-decision.md)，不追认 003 的科学结果。

## 2026-09-24 执行交接补充（不改变科学定义）

用户在获知 003 的第一次执行停在真实 audit 之前后，明确同意继续完成**同一个 A2-003**。已报告 Tasks 1–4 的实现和合成验证；003 的真实 audit/run/fit attempts 均为 0，没有 003 输出目录、账本、锁或冻结的 RSS ceiling。最近一次只读内存样本为 5,270,237,184 B，比 5 GiB 准入值少 98,471,936 B；这是当时的样本，不代替下次启动时的重新采样。四项 A2 numeric/stage 状态仍为 `NOT_EVALUATED`。

本次交接在原计划文件范围内，允许在首次真实 audit 前完成现有 003 的工程门禁修复：将 `tests/test_a2_recovery_namespace.py` 中唯一过时的“003 未获批准”断言改为拒绝未知的 004，保留该文件其他 002 断言；在已允许的 `src/eating_event/a2/control.py` 与 `tests/test_a2_resource_supervisor.py` 内修复并合成验证（1）合法 worker `AUDIT_READY` 的父进程状态写入/哈希绑定检查顺序，（2）`AUDIT_READY` 后 run 可用内存低于 5 GiB 时仍须返回 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM` 且不消耗 run，（3）run 失败停止记录的 `audit_ready` 须反映此前经过验证的 READY 证据，而非写入终态后的当前状态；并在原已允许的合成测试文件内补足 Task 5 的全规模 score 解析证据。修复只限状态、监督、证据记录和合成覆盖，不改来源资格、26D、拟合/选择、阈值、解码或指标。旧测试属于 A2 code identity；修改后必须在真实 audit 前重算并冻结完整代码身份，旧摘要仅为修复前快照。计划的全组回归退出码 0、合成规模覆盖与其余门禁仍须通过。若不能证明，保持 `NOT_STARTED`，不得用真实 audit 排查。

这不是 004 授权，也不扩大 003 的一次真实 audit 与一次真实 run 额度。唯一 audit 对真实 A1 来源首次完整认证；唯一 run 在已计时且受 RSS 监督的 active interval 内重新哈希，且在首个 fit 前完成。低内存只读预检可重做；真实 audit 或 run 一旦开始而失败，其次数即已消耗。

## 1. 新授权与旧停止记录的关系

用户已在获知 A2-002 的 `INCOMPLETE_RESOURCE`、旧资源上限和没有性能结果后，明确要求写好设计及执行文档，并提供另开对话执行 A2 的 prompt；用户澄清电脑有 16 GB 主内存、8 GB 显存，旧上限仅是 001/002 的冻结额度。本决定据此**仅批准一个新编号的 A2-003 资源恢复研究**，条件是先满足本决定与[设计](../superpowers/specs/2026-09-24-a2-003-resource-recovery-design.md)、[执行计划](../superpowers/plans/2026-09-24-a2-003-resource-recovery-implementation.md)的所有拟合前门禁。形成本决定的对话只写/审核文档、未启动研究；其后 003 实现与合成验证的状态见上方交接补充。

[A2-002 决定 §5](2026-09-23-a2-002-identity-contract-recovery-decision.md)与其执行计划 Task 5 曾规定“不得追加 003”。这在 002 授权与终止时成立；本次用户的新指令仅覆盖该条的**未来研究编号禁止**，不把 002 终态变成可重试，也不追认 002 的结果为性能结论。001=`INVALID`、002=`INCOMPLETE_RESOURCE`，两个 namespace、配置、sidecar、账本和输出都不可改、复活或重跑。除本文列出的资源生命周期/遥测/003 namespace 例外，原[A2 科学授权](2026-09-23-a2-context-verifier-design-review-and-authorization.md)及 002 两项已批准的身份/资格语义修订继续约束 003。若文档、实现或前序证据仍冲突，必须在真实 audit 前列出并停止，不能静默选一方。

本决定不是连续尝试 003、004 的许可，不是调整 26D 特征、模型、阈值、duration、fusion 或评价的许可，也不更改 [A1 关闭决定](2026-09-22-a1-end-to-end-feasibility-result.md)与 Formal G1 停止状态。

## 2. 固定前序与缺口

| 研究 | 终态 | 唯一真实 audit / run | fit | 性能 |
|---|---|---:|---:|---|
| A2-001 | `INVALID`，来源身份门禁 | 1 / 0 | 0 | `NOT_EVALUATED` |
| A2-002 | `INCOMPLETE_RESOURCE`，RSS 监督门禁 | 1 / 0 | 0 | `NOT_EVALUATED` |

003 前必须只读重验：001 `run-status` SHA `321ff020f82e3a81172959c86a7f44b7cf801234b6dc4ed210bdc34c65dfcb60`、外部/镜像账本 SHA `1f8698d4957b468f0dc67fd4dfb9a42483c8b71334d8fb5808ec03999a576453`、配置 SHA `f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5`、输出树 SHA `e58935ebfcac05a22481e14835b80e00f213304940834527116789bfb2acb4a0`（8 文件、2,671 B）；002 `run-status` SHA `f96ee4eff5d56e80c5793fd3522069396f2505872019cfce43c1df711e355e7c`、[停止记录](../../artifacts/a2-context-verifier-v1-002/validation-stop-record.json) SHA `62d40008488b4577f0549c1483dde5ce9b527bfeed810572abe8284bc1745d94`、外部/镜像账本 SHA `804287e46a7513aa7b916988d07775a98e477a02989cfe5480978867ec5db5a9`、配置 SHA `89d1a7697dadf3a92f1a2249a68d186ca3ffb48ad8b06697bf142f5952e78949`、输出树 SHA `bdcb14f362c735429473b0d4678e175e2d5cdfc09c2f2628935d97d848b9179f`（7 文件、10,250 B）。输出树算法沿用 002 决定：相对 POSIX 路径排序后的 `[path,SHA-256,size]` 数组作无空白 UTF-8 JSON SHA-256。001/002 不得有残留锁；新 003 不能把前序账本缺失解释为零使用量。

002 最后合格 RSS 为 2,116,214,784 B；失败采样值**未保存**。来源审核尚未写 `frozen-study-identity.json`，没有 `AUDIT_READY`；具体分配阶段未知。16 GB 物理内存与 8 GB 显存不代表启动时可用主内存，002 启动可用只有 4,113,694,720 B；A2 CPU 路径不借显存增加 RSS。`INCOMPLETE_RESOURCE` 不能写成 F1 失败。A1 有 0.585086 的既有开发折 F1，003 之前不能推断 A2 能达 0.66/0.80。

## 3. 准许的实现差异

003 唯一固定 namespace：`configs/a2-context-verifier-v1-003.json` 及 `.sha256`、`artifacts/a2-context-verifier-v1-003/`、`artifacts/a2-study-budget-v1-003.jsonl`、`artifacts/a2-study-budget-v1-003.lock`，配独立 `scripts/run_a2_context_verifier_003.py`。配置相对 002 只准改变 study/output/ledger/lock 身份、001+002 前序哈希与合计使用量的元数据，以及本决定的新 RSS 资源条款；其他科学字段和非 RSS 预算逐字段 canonical 相同。public runner、worker、audit、run loader、ledger、完成态 manifest/metrics 都必须绑定同一固定 ID/config SHA/解析后 output。旧 001/002 调用行为保持 fail-closed。

资源实现仅限：减少 audit 的几何/全局身份/候选同时常驻；有序的 role 暂存与释放；run 按 role 有界读取；保留失败 RSS 数值与阶段的监督遥测；003 的双前序 hash、累计预算和资源准入。`features.py` 的 26D 计算、A1、原 decoder/metrics、真实模型参数与阈值选择公式不得改。若确需改 `execution.py`，只限角色装载/释放调度，且须在真实 audit 前用 fake backend 证明完整 20+5 图、fit 输入、选择、预测、匹配和指标完全等价。不能靠 003 outer 结果决定是否再改实现。

来源仅为 hash 批准的 A1-005 派生 cache、score、候选与前序 A2 记录；raw sensor 不读取也不 stat，official test/external data 不访问。A1 pickle 仅按现行 audit 核文件 hash，不能反序列化或调用；candidate fit/predict=0。没有现场视频，不把 75 段历史长 FP 当作已核实的非进食。

## 4. 003 固定资源与预先停止条件

003 RSS ceiling=`min(4 × 2^30 B, floor(0.60 × 启动可用主内存 B))`，只在**启动可用主内存 ≥5 × 2^30 B**时允许创建 003 输出/账本/锁并开始真实来源 audit。低于该门槛仅返回 `NOT_STARTED_INSUFFICIENT_HEADROOM`；调整机器环境后可重复不读取 A1 来源的只读预检，不能把这种预检算成真实 audit。通过后的启动采样及 ceiling 写入持久账本。`AUDIT_READY` 后、建立 run interval/锁之前，要求当前 available ≥`max(5 × 2^30 B, ceil(已冻结 ceiling / 0.60))`；不足时返回 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM`，保持 `AUDIT_READY`，不消耗 fit 或唯一 run 次数，可等待环境改善后重做只读准入。run 沿用 audit 的 ceiling，不能从新采样提高。001/002 的 2,127,893,299 B 保留为历史证据，**不**参与 003 的 `min`；4 GiB ceiling 与 5 GiB 准入值都不得在看到 003 结果后上调。

001+002 已使用 active wall 21.047 秒，003 可用合计余额 7,178.953 秒；fit wall 已用 0/3,600 秒，verifier attempts 0/25。1 GiB 磁盘包含全部 001/002/003 研究产物、外部及镜像账本、锁和临时文件；线程≤4。必须先做分层纯合成语义等价测试及**一次纯合成规模资源演练**，形状覆盖 632,100 窗口、72,112 候选、105 candidate role、10,745,700 role/window 评分关联；身份 JSON≥147,814,536 B、候选 JSONL≥288,130,586 B，support/字符串长度假设明记。以 ≤2.5 GiB 的演练 RSS 峰值和 ≤1 GiB 家族磁盘估计作为工程风险筛查；该演练不使用 A1 真实来源、不训练/预测模型、不读 outer 性能，不能保证真实峰值。失败可在首次真实 audit 前修复本决定范围内的资源代码并重新验证；未获等价/余量筛查则不启动 003。

真正的 003 只准一次真实 audit；仅当其状态是哈希绑定的 `AUDIT_READY`，且 run 前轻量配置/代码/前序账本/headroom 准入通过，才准建立一次 run interval。A1 282 listed artifact、1,127 cache 与全部 role digest 的完整重哈希属于**受监督 run 的 active interval**，必须在首个 fit 前完成；不能把它挪到预算外。完整复核失败仍算这唯一 run，并终态停止；通过后最多 25 verifier fit attempts。任何已开始的 003 audit/run 遇到 `INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`、`INCOMPLETE_INTERRUPTED` 或身份/遥测不明，立即终止此编号；不重试、不改阈值或资源上限、不自动创建 004。前序、准入、合成等价未通过时记 `NOT_STARTED`，不得生成虚假的 A2 性能状态。`COMPLETE` 才计算 A2 numeric minimum/ideal 与 stage minimum/ideal；其他情况四项均 `NOT_EVALUATED`。

## 5. 结果权限

即使 `COMPLETE`，仍无未参与开发的 participant-level 确认；五折 F1 仅支持开发证据。不得通过重划 41 人声称独立确认；FD-I/FD-II 不得未经新的契约/权限决定充当确认集。Formal G1 仍 `FAIL`，full training 仍 `BLOCKED`，production 仍 `UNCHANGED`。003 结束后再根据真实结果与用户讨论架构级重新设计；本决定不预授权该设计的实验。

```text
A2_001 = INVALID_CLOSED
A2_002 = INCOMPLETE_RESOURCE_CLOSED
A2_003 = INVALID_CLOSED
A2_003_PERFORMANCE = NOT_EVALUATED
A1_TESTED_PROTOCOL = CLOSED
LOCAL_G1_EXPERIMENTATION = STOPPED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
