# A2-004 监督磁盘竞态恢复设计

日期：2026-09-24  
状态：`DESIGN_REVIEWED / DOCUMENT_ONLY / REAL_AUDIT_NOT_STARTED`

本设计从[003 终态](../../decisions/2026-09-24-a2-003-single-resource-recovery-decision.md)恢复一次**相同科学定义**的验证；是否可运行由[004 单次决定](../../decisions/2026-09-24-a2-004-single-disk-race-recovery-decision.md)及[004 实施计划](../plans/2026-09-24-a2-004-disk-race-recovery-implementation.md)约束。这里不提供 003 重试或 005 授权。

## 1. 失败机制与需区分的证据

003 的持久终态是 `INVALID`、audit=1、run=0、fit=0、A2 四项 `NOT_EVALUATED`。失败 `.jsonl.tmp` 同名最终文件存在；`audit.py::_write_jsonl` 创建父目录、写临时文件并原子重命名；`control.py::_supervise_worker_003` 每约 0.2 秒执行 `ledger.measure_disk`；`budget.py::check_disk_budget` 先列出 `is_file()` 路径，随后逐个 `stat()`。如果 worker 在两步间把 `.tmp` 改名，监督器的旧路径 `stat()` 会抛出 `FileNotFoundError`，终止 worker。worker response 缺失、资源摘要 returncode=15 与此一致。缺少 traceback，故先以纯合成注入确认该机制，不把“父目录缺失”写成事实。

修复不得简单吞掉所有 `FileNotFoundError` 或忽略 `.tmp`：这会漏计临时峰值，也会掩盖前序丢失。监督器对**正在变化的 004 输出树**遇到短寿命路径消失时须有界地重列并重测整个快照；成功采样必须包含最终文件或仍存在的临时文件，仍按固定 cap 检查。有限次重采样后若不能形成可证明的计量，按 `INCOMPLETE_RESOURCE` 持久化失败阶段/样本并停止。001/002/003 的固定输出树、外部/镜像账本或 004 固定根/账本缺失，应立即 fail-closed，不能用重试或零字节代替。预写入磁盘 guard 与监督采样共同保证短暂增量受控；4 MiB 关键遥测空间仍预留。

下一 runner 以 ASCII 安全 JSON 输出或等价编码无关方式呈现结果，测试在 cp1252 文本流写含中文的失败原因仍能打印；该显示修复不改变持久化终态。失败路径应保留完整异常类别、操作阶段、路径和监督阶段，以便区分扫描竞态、真实来源文件缺失及资源上限。

## 2. 004 身份与有界资源

配置只变固定 004 namespace、三前序身份/累计用量和一次性 1.5 GiB 家族磁盘额度；A1 source SHA、26D、角色图、HGB、阈值、duration、fusion、匹配和四项判定保持 003 canonical 相同。004 的新代码身份在修复与回归后冻结；003 历史 `b60e9cd5...` 是前序产物的冻结记录，不能拿当前可变代码直接与它比。新 preflight 只读验证 001/002/003 完整终态和账本/树，测当前主内存；不读取或 stat raw sensor，不访问真实 A1 cache/score/candidate 内容，也不建 004 输出。001/002/003 输出与暂存永不清理。

新家族磁盘投影须以现存 003 输出 339,692,500 B 和全部前序账本为底，叠加 004 纯合成的输入暂存、物化、运行输出和遥测，留至少 256 MiB 与硬 cap 的距离。旧 003 合成 709,711,113 B 是 001+002+单次新研究的估计；加上保留的 003 产物约 1.05 GB，距旧 1 GiB 仅约 24 MB，不能沿用旧 cap 或把 003 文件清空。004 RSS 仍采用 5 GiB 启动门槛及最高 4 GiB ceiling，run 复检沿用冻结值；真实 003 RSS 峰值 767,606,784 B 不能证明 004 run/HGB 峰值。

## 3. 验证层次与停止

1. **纯合成确定性竞态**：在 `is_file()` 后、`stat()` 前原子改名 `.tmp`，证明新计量重扫后准确计入且超 cap 仍拒绝；固定前序/账本缺失、持续竞态及采样失败仍按规定终止。独立假 worker 在监督器下高频写 `.tmp`/rename，最终状态、RSS/磁盘样本、锁与外部/镜像账本一致。cp1252 打印回归单独验证。
2. **科学等价和规模**：沿用 003 已通过的 20+5 fake-backend 输入、输出和 outer 隔离比较；新增 004 身份后重新运行，不把 config/ID 差异当成科学输入差异。纯合成全规模 score 解析覆盖 632,100 窗口、72,112 候选、105 role、10,745,700 关联及真实长度/support 假设，计入 001/002/003 保留资产的磁盘和监控开销；不调用模型 fit/predict。完整 A2、A1 指定回归均退出 0。任何科学差异或资源筛查不过，不启动真实 audit。
3. **唯一真实研究**：先只读 preflight 与 namespace 空置，再一次 audit。只有合法 `AUDIT_READY` 且 run 轻量准入通过，才一次 run；run worker 的来源重哈希在监督 active interval 内、首个 fit 前。无 `COMPLETE` 则只报告真实终态和资源/阶段，不推算 F1。不得因 outer 结果修补、静默重试或启动 005。

这套门禁只能排除已经识别且可合成验证的失败机制，不能保证真实来源、HGB、操作系统或新未知故障一定允许 `COMPLETE`。用户所要的“完整执行”只能解释为：门禁通过才进入唯一真实尝试；若中途失败，按证据终止并报告，而非绕过规则以取得性能数字。
