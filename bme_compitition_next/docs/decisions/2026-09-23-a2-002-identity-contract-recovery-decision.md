# A2-002 身份契约修订与单次恢复验证决定

日期：2026-09-23  
状态：`DESIGN_REVIEWED / A2_002_CONDITIONALLY_AUTHORIZED / NOT_STARTED`

## 1. 权限、历史状态和结论

用户在收到 A2-001 的 `INVALID` 结果后，明确允许继续完成 A2，并要求先审查文档、写执行计划和提供另开对话的执行 prompt。该指令授权**一个新的、受本决定和[002 执行计划](../superpowers/plans/2026-09-23-a2-002-identity-contract-recovery-implementation.md)约束的 A2-002 恢复验证**；本轮只写文档，不运行 audit、fit、predict 或实验。002 不是对终态 001 的同目录重试；它是用户另行授权、科学定义相同的新 study，也不是 Formal G1、本项目 full training 或 production 的授权。

[A2-001 状态](../../artifacts/a2-context-verifier-v1-001/run-status.json)保持终态 `INVALID`。旧[设计审查与授权](2026-09-23-a2-context-verifier-design-review-and-authorization.md)及[001 执行计划](../superpowers/plans/2026-09-23-a2-context-verifier-validation-implementation.md)中“唯一 001 目录、唯一旧账本、未运行”的文字是 001 执行前的历史状态；本决定仅为**另一个明确编号的 002** 覆盖这些 namespace/授权文字，不修改 001 记录，也不放宽其科学定义和停止门槛。旧 001 配置、sidecar、产物、外部/镜像账本及提交 `630ab30d8d5a1696b246868ab45a894ba33cb622` 保留供审计。

预检决定：`SPIKE FIRST`，只检验原固定 26D 上下文机制。置信度：对已发现的两处实现过严与其修订边界为高；对 002 后续所有门禁能否通过、F1 是否改善以及未见 participant 泛化为未知。若不接受开发折证据的限制，暂停模型投入仍是合理选项。

## 2. A2-001 的证据分层

| 层级 | 已核事实与解释 |
|---|---|
| A. 已批准契约 | [D3 身份审计](2026-09-20-a1-d3-identity-audit-and-revision-proposal.md)要求 **1,127 个 cache entry 各自**唯一关联一条 `processed` manifest-audit 记录；[A1 读取实现](../../src/eating_event/a1/inputs.py)只对非空 opaque ID 建索引并检查重复，再逐 cache entry 验证 participant/session/status。[资格契约](../data-contract-validation-2026-09-17.md)保留全部注释，同时用训练/评价资格标志决定 GT。 |
| B. A2-001 实现 | [A2 audit.py](../../src/eating_event/a2/audit.py)第 203–210 行要求审计表**每行**非空 ID；第 155–188、675–676 行把全部注释参与者要求纳入 41 人缓存。这两项都比 A1 获批契约更宽泛地拒绝已排除行。 |
| C. 实际执行 | A2-001 在首个来源门禁以 `approved record audit identity is missing or duplicated` 停止，3.5 秒、0/25 verifier fit、0 candidate fit/predict、无 `AUDIT_READY`、无特征物化或性能结果；[外部账本](../../artifacts/a2-study-budget.jsonl)和[worker 响应](../../artifacts/a2-context-verifier-v1-001/worker-response-audit.json)一致。该错误由**缺失**引起，不是已使用记录重复。 |
| D. 只读核验 | `manifest-audit.json` 有 1,163 行，全部 1,161 个非空 opaque ID 无重复；两条无 ID 的行分别是 `skipped_invalid_session` 和 `excluded_test_participant`。1,127 条 `processed` 均有 ID，与 1,127 个 cache entry 的身份、participant、session、status 一一匹配。资格表的 281 条注释涉及 43 人；缓存外 3 人的 17 条均为训练和评价资格 false，234 个评价 GT 不受影响。 |
| E. 推断与缺口 | 第一处是已触发的 A2 校验器误拒；第二处是依据代码与批准元数据可确定的下一处误拒，**尚未在 001 运行中触发**。001 在读取 cache NPZ 与物化特征之前停止，后续真实来源门禁、26D、G3、F1 均未验证；不能承诺 002 必然完成。没有独立 participant 确认，也没有那 75 段长 FP 的独立行为真值。 |

旧执行计划一处允许拟合前实现更正后重复 audit，另一处规定来源身份失败即 `INVALID` 且终态不可重启。对已经终止的 001，以终态和用户“不重试、不修补来源”的指令为准；不能借前一句在 001 目录再次调用 audit。002 的第一轮真实 audit 一旦失败也终止，不能预授权连续补丁。

## 3. 只批准两项校验语义修订

1. **Manifest audit：**对非空 `path_or_file_id`（包括 nonprocessed 行）保持全表唯一性；`processed` 行缺 ID 必须 `INVALID`；非 `processed` 的 skipped/excluded 行可以没有 ID。每个批准 cache entry 仍必须唯一指向 `status=processed`、participant/session 匹配的记录，不能跳过或模糊匹配任何实际使用的 record。禁止以 `str(None) == "None"` 把缺值当作真实 ID。不得改写批准 manifest、cache 或 A1 产物。
2. **Eligibility：**保留并校验资格表的全部 281 行及固定 hash；只把 `evaluation_eligibility=true` 或 `training_eligibility=true` 的 canonical GT participant 纳入 41 人缓存成员检查。不合格注释不得进入训练、OOF、预测或 234-GT 评价；合格 GT 若不在缓存人群内仍为 `INVALID`。不得更改资格标志、分母、sidecar 或事件边界。

修订仅限验证器对**已批准排除语义**的解释，不从 outer 结果选择特征/阈值，不产生额外模型数据。`a2_event_context_v1` 的 16+10 特征、±300 秒中点区域、原候选与 4,183 个 outer interval、41 人/234 GT、5/4/4 角色、HGB、seed、`{0.10,0.25,0.50}` 阈值集合、180 秒 duration、600 秒 fusion、strict IoU `>0.25`、G3 与四项 numeric/stage 门槛均与 001 完全相同。[原 A2 审查决定](2026-09-23-a2-context-verifier-design-review-and-authorization.md)其余科学及解释条款继续有效。`features.py`、`execution.py`、A1 代码和评价实现不因本修订改变。

## 4. 新 study 身份和资源连续性

002 仅使用新 `configs/a2-context-verifier-v1-002.json` 及 SHA sidecar、`artifacts/a2-context-verifier-v1-002/`、外部 `artifacts/a2-study-budget-v1-002.jsonl` 和 `artifacts/a2-study-budget-v1-002.lock`；无任意路径/编号 CLI 覆盖。002 配置与 001 配置逐字段相同，允许差异仅为 study ID、输出/账本/锁路径和固定 predecessor 元数据。旧 `configs/a2-context-verifier-v1.json` 及其 sidecar 不改。002 runner、worker、`run_audit`、`verify_audit_ready`、`load_audited_corpus`、ledger 与完成态 manifest 都须逐次双向绑定同一个 study ID/config hash/解析后的固定 output 路径；不能只在 public runner 核一次。完成态 manifest、metrics 和台账快照均记录 001 前序 hash/继承用量及 001+002 合计。001 runner 继续 fail-closed，不能把旧账本或目录当作 002。

冻结前序证据：001 `run-status.json` SHA-256 `321ff020f82e3a81172959c86a7f44b7cf801234b6dc4ed210bdc34c65dfcb60`，旧外部与镜像账本 SHA-256 `1f8698d4957b468f0dc67fd4dfb9a42483c8b71334d8fb5808ec03999a576453`；旧配置 SHA-256 `f34e05939745a081a8ab4878a2e94f30e0cc4879980d1d32d761664c722ed6f5`。001 输出树固定摘要 `e58935ebfcac05a22481e14835b80e00f213304940834527116789bfb2acb4a0`：对输出目录全部文件按相对 POSIX 路径排序，构造 `[相对路径, 文件 SHA-256, 文件字节数]` 列表，使用无空白分隔的 UTF-8 JSON 后取 SHA-256。002 在首次真实 audit 前及结果交接时重验这些值和旧终态，记录旧账本已用 active wall **3.5 秒**、fit wall **0 秒**、verifier fit attempt **0**；旧文件一律只读。新累计上限仍为 A2 全家族 audit+run **7,200 秒**、fit **3,600 秒**、verifier fit attempt **25**、candidate fit/predict **0**、线程 **4**，并计入 001 使用量。RSS 上限取 `min(8 GiB, 001 已冻结的 2,127,893,299 bytes, 002 启动可用内存的 60%)`，不能因换目录升高。1 GiB 的新研究磁盘上限计入 001 现有产物/旧账本和 002 产物/新账本/锁/临时文件；目录须递归计数，且过程采样、收尾检查和完成态 manifest 使用同一口径。当前 001 目录 8 个文件共 2,671 bytes，外部账本 634 bytes，执行前须再核身份与实际字节数。缺少或不一致的账本、遥测或前序证据均 fail-closed。预检只读核验前序，不预先创建真实 002 账本；首次持久 predecessor 记录须在唯一一次 002 audit 启动、确认新账本为空后写入。

## 5. 准入、停止和结果解释

真实 audit 前必须完成：相对于 `630ab30` 的允许路径/科学常量差异审查；覆盖两项排除语义正反例的合成测试；完整预拟合来源契约矩阵审查；环境、来源与前序终态/hash 固定。原先的 50 项 A2 合成测试及 15 项 A1 测试只证明当时所覆盖的情况，不能代替新反例与完整来源审计。此阶段不得调用真实模型或 001 runner。

002 仅准许**一次**真实来源 audit。`AUDIT_READY` 必须绑定实际 role 顺序、26D `float32` 矩阵、独立标签 join、代码/配置/来源 hash 与资源台账；仅在通过后运行**一次**完整嵌套验证，≤25 verifier fit attempts。任何新身份、资格、隔离、G3、资源或实现门禁失败即报告对应 `INVALID`、`VERIFIER_DATA_INSUFFICIENT` 或 `INCOMPLETE_*`；不重开 002、不追加 003、不据此评价 A2 性能。完成态才按旧决定分别判定 numeric minimum/ideal 与 stage minimum/ideal。若 stage minimum 失败，关闭此固定 26D 变体；若通过，也只记 `SUPPORTED_ON_DEVELOPMENT_FOLDS`，不能宣称独立确认或 Formal G1 通过。长 FP 的减少只能称为批准标注契约下的 FP 减少，不能代替真实行为核验。之后再回到架构级重设计讨论。

```text
A2_001 = INVALID_CLOSED
A2_001_PERFORMANCE = NOT_EVALUATED
A2_002 = CONDITIONALLY_AUTHORIZED_NOT_STARTED
A2_002_SCIENTIFIC_DEFINITION = SAME_FIXED_26D
A1_TESTED_PROTOCOL = CLOSED
LOCAL_G1_EXPERIMENTATION = STOPPED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
