# A2-004 单次磁盘竞态恢复实施计划

日期：2026-09-24  
状态：`PARTIAL_IMPLEMENTATION / DISK_RACE_UNIT_FIX_VERIFIED / A2_004_NAMESPACE_NOT_IMPLEMENTED / REAL_AUDIT_NOT_STARTED`

**目标：**在不改变 A2 固定 26D 科学定义的前提下，先用合成反例排除 003 的监督磁盘扫描竞态与结果打印问题，再仅于完整门禁通过后，使用全新 004 namespace 取得一次合法开发折性能结果或如实终止。依据[004 决定](../../decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md)、[004 设计](../specs/2026-09-24-a2-004-disk-race-recovery-design.md)及原[A2 科学授权](../../decisions/2026-09-23-a2-context-verifier-design-review-and-authorization.md)。本计划不允许运行 003 audit/run。

## 工作树、文件和起跑条件

工作树：`E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next`。现有大量既有 staged/dirty/untracked 文件；先保存 `git status --short`，精确检查本任务差异，不 `reset`/`clean`、整树暂存、删除部分 003 产物或另开目录伪装同一编号。新对话须使用**这个现有工作树**，因为 003 实现及文档尚未作为完整干净提交存在。修改共享代码前，003 冻结身份的 21 个文件已逐字核验，连同配置/sidecar 保存在 `docs/evidence/a2-003-frozen-code-2026-09-24.tar`（23 项、399,360 B、SHA `336ce6bc7c008feb89ef4643f28f5ce61369369c8506a2439c8030b59739b670`）；新 agent 须只读重验该档案及 003 输出。后续 004 当前 digest 变化是合法新研究，不回填 003 身份。

| 文件 | 004 允许工作 |
|---|---|
| `configs/a2-context-verifier-v1-004.json`、`.sha256`；`scripts/run_a2_context_verifier_004.py` | 固定新身份、三前序、1.5 GiB 磁盘额度及编码安全入口；不接收任意参数 |
| `src/eating_event/a2/contracts.py`、`budget.py`、`control.py`、`worker.py`、`audit.py` | 004 三前序绑定/累计计量、短寿命文件重命名时有界重采样、失败遥测与新编号路由；003 终态路径仍拒绝重启 |
| `tests/test_a2_recovery_namespace.py`、`test_a2_resource_recovery_namespace.py` | 仅把“未知编号”断言改为稳定未注册 ID；保留 002/003 固定科学和输出绑定断言 |
| 新 `tests/test_a2_004_*.py` 及既有 `tests/test_a2_resource_supervisor.py`、`test_a2_resource_equivalence.py` | 竞态注入、前序损坏、假 worker/编码回归、全图科学等价及资源筛查 |

`features.py`、`execution.py` 的 fit/score/selection、A1、原 decoder/metrics、001/002/003 配置/sidecar/runner/产物/账本、production 均不可改。若 004 必须改 `execution.py` 的 role 装载生命周期，先停在设计复核，不把这份文档当作默认许可。禁止读取或 stat raw sensor、official test/external data；A1 模型 pickle 仅按现有 audit 核 hash，不能反序列化或调用。Tasks 1–4 全用纯合成数据和只读前序记录，不拟合/预测真实模型。

## Task 1：锁定 003 终态及三前序身份

- [ ] 只读重验 001/002 的固定 hash、终态、外部/镜像账本和树；003 `run-status`、停止记录、配置、冻结身份、外部/镜像账本与 164 文件输出树的 SHA/字节数按 004 决定 §2 逐项重算。证明 audit=1、run=0、fit=0、无 READY/sidecar/锁；保留 003 `temporary` 与 `materialized`。若任一前序不符，`NOT_STARTED_GATE_FAILED`，不得创建 004 路径。
- [ ] 从三份实际账本重算家族 active=144.688 秒（具体浮点值以账本为准）、fit wall=0、attempts=0，而不只信新配置。新配置科学 canonical 投影与 003 相同，只更改固定 004 身份、三前序元数据和事前 1.5 GiB 家族磁盘 cap。建立 004 runner/config/sidecar 的 ID/config SHA/output 三向绑定；未知 ID/path、篡改前序/科学字段或旧 003 runner 再调用须在真实来源前拒绝。新旧代码身份分别保存，不用当前代码 digest 否定 003 的历史冻结摘要。
- [ ] 在纯合成临时工作区验证上述正反例，实际记录命令、退出码、通过数、配置 SHA 与当前代码身份；任何报错不触发真实 audit。

## Task 2：先复现并修复监督磁盘竞态

- [x] 先写确定性**失败**测试：合成输出中的 `.jsonl.tmp` 被磁盘扫描纳入 `is_file()` 快照，随后在 `stat()` 前原子改名为最终 `.jsonl`；旧实现已复现 `FileNotFoundError`。共享 `budget.py::check_disk_budget` 已作最小有界重扫，`tests/test_a2_004_disk_race.py` 的改名重计数、固定文件消失、超 cap 三个合成测试由 3 failed 转为 3 passed。新 agent 仍须确认 004 路由只把**可变的当前输出树**当作可重扫对象，最终计入真实存在的文件、检查硬 cap；不能把消失路径记 0 或无界重试。若有限重采样后仍不可证明，以可持久化的 `INCOMPLETE_RESOURCE` 失败，带操作阶段与路径；固定前序输出、外部/镜像账本、004 固定根真正缺失立即 fail-closed。
- [ ] 反例包括：改名后仍超 1.5 GiB 必失败；001/002/003 任一固定文件消失、外部/镜像账本不一致、004 固定账本缺失、持续竞态或采样异常不得误放行。用高频原子写的**假 worker**跑监督器，核对最终文件计量、先 fsync 的 RSS/磁盘证据、锁释放、外部/镜像账本一致及失败阶段。003 的历史输出不可拿来当合成可写 fixture。
- [ ] 新 runner 用 ASCII 安全 JSON 输出；在 cp1252 文本流写含中文失败原因的纯合成案例中仍返回原持久状态。此打印修复与磁盘计量分别测试，不能借终端编码失败掩盖真实 worker 终态。

## Task 3：科学等价、全规模工程筛查及冻结

- [ ] 复跑原 003 20+5 fake-backend 对照：每个 verifier fit 的 role、26D `float32`/label/participant 字节、G3、每折阈值选择、预测、lineage、TP/FP/FN、长 FP、MAE、四项判定与 003 设计一致；扰动 outer GT 不改选择/预测。只允许 study ID/config 身份签名不同。candidate fit/predict=0，真实 HGB fit/predict=0。
- [ ] 纯合成规模演练覆盖 632,100 窗口、72,112 候选、105 candidate role 和 10,745,700 个经过 score 解析的关联，身份≥147,814,536 B、候选≥288,130,586 B，记录 support/字符串长度、处理 wall、process-tree RSS、暂存/物化/遥测/运行投影。家族磁盘必须加入**原样保留的 001/002/003**输出、外部账本、004 估计产物与锁，离 1,610,612,736 B cap 至少 256 MiB，并另留关键终态遥测空间；RSS 工程筛查仍≤2.5 GiB。不能用先前 709,711,113 B 单新研究估计代替四编号家族投影，也不能声称这保证真实 HGB 峰值。
- [ ] 运行实施计划指定的完整 A2 回归组和 A1 合同/事件/指标组，两组退出码均 0，记录实际通过数；不得仅沿用 003 的 136/15 报告。只读重验 A1 checksum manifest SHA `0543791e90df9e1bcf93111dc45e80678089898409e6888b90584fd18c469025`、282 entries、45 注册 A1 代码身份及批准来源清单本身；**不**在此阶段重哈希清单列出的全部真实来源。核 diff 仅限允许路径，冻结 004 config raw SHA、完整 A2 code identity、Python/科学库版本。代码/测试再变更后重新冻结；真实 audit 后不得再改。
- [ ] 在创建 004 输出前只读运行 `preflight`，检查 004 目录/账本/锁全部不存在、家族磁盘与预算余量、启动 available≥5 GiB。`preflight` shell 退出码为 0 也不能代表准入，必须检查 JSON status=`PREFLIGHT_READY`；不足可改善机器环境后重做只读检查。任一合成、身份、来源、预算或环境门禁不通过，保持 004 `NOT_STARTED`，不要用真实 audit 排查。

## Task 4：唯一真实 audit，合法 READY 后唯一 run

- [ ] 仅在 Tasks 1–3 均验收且 004 固定 namespace 空置时，从指定工作树执行 `python scripts/run_a2_context_verifier_004.py audit` **一次**。audit 首次完整认证 A1 282 listed artifact、45 代码身份及 1,127 approved cache，构造原 26D/role 摘要；不拟合/预测。要求哈希绑定 `AUDIT_READY`、完整来源/标签/G3/资源台账。任何已开始的 audit 失败，终态停止 004；不得同目录重试、改名、删除旧产物或开 005。
- [ ] 仅在 READY 后，先轻量重验配置/代码、三前序小账本、READY hash、预算和当前 available≥`max(5 GiB, ceil(冻结 ceiling/0.60))`。不足只返回 `RUN_NOT_STARTED_INSUFFICIENT_HEADROOM`，READY 不变、run interval/fit=0，可改善环境后重复只读准入；不得提升 ceiling。通过后执行 `python scripts/run_a2_context_verifier_004.py run` **一次**。run 的受监督 active interval 内、首个 fit 前重新哈希 A1 来源、role 与实际 fit 输入；重哈希失败仍算唯一 run。之后才运行固定 20+5 图，家族 verifier attempts≤25、candidate fit/predict=0。
- [ ] `COMPLETE` 才报告 pooled/五折 TP/FP/FN、precision/recall/F1、长 FP、matched start/end MAE、阈值与来源、A1 FN transition、四项 numeric/stage；不只看 pooled F1。若未完成，四项一律 `NOT_EVALUATED`，明确工程/数据门禁与性能的区别。无论终态，都重新只读验证 001/002/003 固定哈希、004 外部/镜像账本、唯一 audit/run 次数及 active/fit/RSS/disk；保持 A1 CLOSED、Formal G1 FAIL、full training BLOCKED、production UNCHANGED。汇报后停止，不自动启动架构级实验。

**不能保证 `COMPLETE`：**本计划只能在真实研究前排除已知且可合成复现的阻断，并规定未知失败的合法终态；任何“为了拿到 F1”而重复已开始尝试或放宽边界的做法都使结果无效。

交接时的部分验证：新磁盘竞态测试先红后绿为 3 passed；`test_a2_004_disk_race.py`、A2 control/002/003 namespace 与 003 supervisor 定向组为 88 passed。由于真实 003 输出已存在，旧低内存 preflight 测试改在隔离纯合成工作区，不再要求真实 003 路径不存在。随后运行了当前允许的完整 A2+A1 指定回归合集，**154 passed，退出码 0**（耗时 194.11 秒）。这些是在 004 namespace/config/runner 实现**之前**的结果；Task 3 仍须在最后一次 004 代码修改后重新执行并冻结身份。
