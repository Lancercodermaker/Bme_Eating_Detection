# A2-004 单次监督磁盘竞态恢复决定

日期：2026-09-24  
状态：`A2_004_CONDITIONALLY_AUTHORIZED / NOT_STARTED / PERFORMANCE_NOT_EVALUATED`

## 1. 授权范围与证据界限

用户在获知 [A2-003 真实 audit 终态](2026-09-24-a2-003-single-resource-recovery-decision.md) 为 `INVALID` 后，要求解决阻断并准备下一次完整 A2。该新指令仅批准**一个新编号 A2-004**的工程恢复及其门禁通过后的单次真实验证；它明确覆盖 003 决定中“不得自动创建 004”的**未来编号禁止**，不重开 001/002/003，也不把 003 的部分物化当作 `AUDIT_READY` 或可继续的 run。004 的实现仍须先满足本决定、[设计](../superpowers/specs/2026-09-24-a2-004-disk-race-recovery-design.md)及[执行计划](../superpowers/plans/2026-09-24-a2-004-disk-race-recovery-implementation.md)；本次文档准备不调用真实 audit/run、模型 fit/predict 或新架构实验。

003 是**工程/监督门禁失败**，没有 A2 性能证据。错误消息中的 `.jsonl.tmp` 缺失不证明 `training-labels` 目录未创建：`_write_jsonl` 先建父目录，失败角色的最终 `.jsonl` 已在终态前写成。高置信机制是 worker 将 `.tmp` 原子改名期间，监督器的磁盘计量已枚举旧路径、随后对旧路径 `stat()`，抛出 `FileNotFoundError`；资源日志显示监督器终止 worker、worker response 缺失。持久化记录没有 traceback 行号，故必须在 004 的纯合成测试中确定性复现和排除此竞态，不能把推断写成已证实的单行调用栈。cp1252 终端 `UnicodeEncodeError` 是用户报告的终态打印问题，不能改写 003 持久终态。

## 2. 冻结前序与累计用量

001=`INVALID`，002=`INCOMPLETE_RESOURCE`，003=`INVALID`；三个编号各有一次真实 audit、零 run、零 fit，四项性能均 `NOT_EVALUATED`。004 preflight 在任何持久写入前须按 [003 决定 §2](2026-09-24-a2-003-single-resource-recovery-decision.md)逐字重验 001/002 的配置、终态、外部/镜像账本、输出树和锁，并新增下列 003 固定证据：

| 003 证据 | 固定值 |
|---|---|
| 配置 SHA-256 | `dca4d895f5d65bf7df6583ddd935338fa614f91952103508bed5189dd1fbc993` |
| 冻结 A2 code identity 摘要 | `b60e9cd5dd9138210af665b6f0124d76fd99ba7fe7e27fe169237287aeeec918` |
| `frozen-study-identity.json` SHA-256 | `d39aa40d4207668a89db34f6de5f8c9f3d24ac3267cab9bc120cf7e4d0328f5c` |
| `run-status.json` SHA-256 | `4039ef151dd47f48ab11436d1c7e583b7f592c72eb2617db27d07e39630b3315` |
| `validation-stop-record.json` SHA-256 | `a6f17a77b652e9bf95c43083e7c0f1b27becbdc4450ea81b1d0e2b2d73466b74` |
| 003 外部与镜像账本 SHA-256 | `eae9f876cf0cf3c58a49e3fe6da5bbc74ced55d7791074227eafccae6191cbae`，字节相等 |
| 003 输出树 | 164 文件、339,692,500 B、SHA-256 `fa999f999b99ef783249d607e53eadd88359232afe5c93100c7d545c4264e7ec`，沿用 003 决定 §2 算法 |

003 不能有残留锁、`AUDIT_READY`/sidecar 或 run/fit 事件。其临时 spool 与部分物化**必须保留并计入**新家族磁盘，不能清理以腾空间。001+002+003 家族 active wall 从账本重算为 144.688 秒，剩余约 7,055.312/7,200 秒；fit wall 0/3,600 秒，verifier attempts 0/25。当前 004 代码身份会因合法新文件/修复而不同，不能拿它与 003 历史 code digest 作相等比较；必须保留 003 冻结身份记录和可复原的代码差异证据。

修复共享代码前，已按 003 `frozen-study-identity.json` 的 21 条逐文件 SHA 核对原字节，另保存 003 配置/sidecar 共 23 项于 `docs/evidence/a2-003-frozen-code-2026-09-24.tar`（399,360 B，SHA-256 `336ce6bc7c008feb89ef4643f28f5ce61369369c8506a2439c8030b59739b670`）。该档案只保存代码与配置，不含 A1 数据；004 执行 agent 须先重验档案成员及 hash，不因共享代码现已改变而改写 003 历史身份。

## 3. 固定 004 差异与禁止边界

固定 namespace 为 `a2-context-verifier-v1-004`：`configs/a2-context-verifier-v1-004.json` 及 `.sha256`、`scripts/run_a2_context_verifier_004.py`、`artifacts/a2-context-verifier-v1-004/`、`artifacts/a2-study-budget-v1-004.jsonl` 和同名 `.lock`。配置科学投影须与 003 逐字段 canonical 相同；只允许编号/output/ledger/lock、001+002+003 前序摘要、下述家族磁盘资源条款变化。A1 来源 checksum、41 人/234 GT/6C7、5/4/4 角色、16+10→26D `float32`、HGB 参数及 seed、阈值 `{0.10,0.25,0.50}`、180 秒 duration、600 秒 fusion、strict IoU `>0.25`、一对一事件评价、G3 和四项 numeric/stage 规则全部不变。candidate fit/predict=0，outer GT 不进入特征、拟合或选择。

工程变更仅限：004 固定身份/三前序累计账本；磁盘计量对原子写入的并发快照与失败遥测；004 runner 的编码安全结果打印；必要的合成反例和等价/规模测试。不得修改 `features.py`、A1、原 decoder/metrics、001/002/003 配置、sidecar、runner、产物或账本，不得因真实 outer 结果改阈值、特征、模型或资源 cap。只读 hash 核验 A1 pickle，不能反序列化/调用；raw sensor 不读取也不 stat，official test/external data 不访问。若需要触及科学计算、来源资格或本决定以外资源条款，真实 audit 前停下复审。

## 4. 资源门禁及唯一尝试

004 沿用 003 的 CPU process-tree RSS：启动可用主内存至少 `5×2^30 B`；冻结 ceiling=`min(4×2^30 B, floor(0.60×启动 available B))`。READY 后 run 前可用内存仍至少 `max(5×2^30 B, ceil(冻结 ceiling/0.60))`，不足仅返回 run 未启动并保留 READY；不得重新冻结更高 ceiling。线程≤4，家族 active≤7,200 秒、fit wall≤3,600 秒、verifier attempts≤25。

由于不可删除的 003 部分产物使原 1 GiB 家族上限仅余约 24 MB，004 在**首次真实 audit 前**一次性将家族磁盘硬上限定为 `1.5×2^30 B`（1,610,612,736 B），覆盖 001/002/003/004 全部输出、四份外部及镜像账本、锁、暂存和遥测。新的纯合成规模演练必须把不可变的 003 产物加入实测/投影，预计峰值距硬上限至少保留 256 MiB，并另保留终态关键遥测空间；磁盘无法证实时不启动。此上限和余量不得在真实 audit 后提高，不允许清理前序。003 的真实 RSS 峰值远低于冻结 ceiling，故不提高 RSS cap。

磁盘计量须以确定性故障注入证明：短寿命 `.tmp` 在枚举后、`stat` 前变为最终文件时，重新扫描能计入最终文件且不中断；真正缺失的固定前序、账本、输出或持续不可测的磁盘状态仍 fail-closed；预算超限仍按资源失败记录。合成假 worker 高频原子写和 004 runner 的 cp1252 输出回归、完整 20+5 fake backend 科学等价、全规模纯合成 score/role 资源演练、计划两组回归退出码 0 均须在真实 audit 前通过。测试不可调用真实模型 predict；不能用 004 真实 audit 诊断已知竞态。

已在新 004 合成测试中先复现旧 `check_disk_budget` 的三个失败案例，再对共享 `budget.py` 作最小有界重扫修复：输出 `.tmp` 改名后重新计入最终文件；固定 family 文件缺失和超 cap 仍失败。此修复**不是** 004 的真实 audit 授权已满足：新 namespace/三前序、假 worker、cp1252 与全部回归仍须由执行 agent 验收后才能启动。

满足上述全部门禁且 004 固定输出/账本/锁均不存在，才准**一次真实 audit**；只有哈希绑定 `AUDIT_READY` 后准**一次真实 run**。audit 首次完整认证 A1 批准来源；run 在已计时和 RSS 监督的 active interval 内、首个 fit 前重哈希来源、全部 role 和实际 fit 输入。已开始 audit/run 的任何 `INVALID`、`INCOMPLETE_RESOURCE`、`INCOMPLETE_INTERRUPTED`、`VERIFIER_DATA_INSUFFICIENT` 或身份不明都关闭 004；不重试、不改目录、不自动 005。只读 preflight/headroom 检查可在未开始相应 interval 时重复。

## 5. 结果解释

只有 `COMPLETE` 才比较 A1 pooled F1 `0.585086` 与 A2 pooled/五折事件指标，并分别报告 numeric minimum≥0.66、numeric ideal≥0.80、stage minimum/ideal。stage 还须相应 numeric gate、至少 3/5 折 F1≥0.66、每折长 FP≤25%、每折 matched start/end MAE≤900 秒。未 `COMPLETE` 时四项都是 `NOT_EVALUATED`，工程/数据失败不能称为性能失败。即使通过，41 人全部参与过开发决策，没有独立 participant 确认；无现场视频，长 FP 只按标注契约表述。A1 仍 `CLOSED`、Formal G1=`FAIL`、full training=`BLOCKED`、production=`UNCHANGED`。004 后只汇报并讨论路线，不自动进行架构实验。
