# 路线二一次完整 A+B 条件授权卡

日期：2026-10-02（当前绑定 revision-20261002g；此前版本作为历史准备快照保留）

## 提交状态

**APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**

研究ID固定为 route2-candidate-overlap-v1-001。本卡把完整实验范围、预算候选值、路径和当前身份收据列成可审材料；当前仍不能批准执行：正式 ResourceEnforcer、PhaseRunner、逐 role / phase OS 挂载撤销、完整资源包络、terminal 后外部墙钟验收、正式运行期输入身份绑定及若干预算裁决尚未闭合。本版独立全实现复审已返回 FAIL；不是独立 PASS。

本卡不是批准记录。A+B 批准ID：NOT_ISSUED；FROZEN_ADMISSION=None。当前没有合法 Stage A-only 或 A+B 运行，也没有合法路线二结果。不能以本卡、代码接口、probe 或先前准备视图替代负责人之后对这张具体卡的单独明确批准。

## 负责人已明确的两项决定

- Windows 宿主账号所有者列为可信主体。该项解除“宿主所有者本身不可信”的政策缺口；它不证明运行 worker 的物理隔离、输入文件不可变、特权 controller 已可信或账本不能被宿主所有者修改。负责人选择的威胁模型须在正式独立复审中与实际 worker 边界绑定。
- 创建正式镜像前，WSL 承载文件系统与 ext4.vhdx 所在 Windows 实体卷分别需要至少 8 GiB 可用空间，即各自 ≥8,589,934,592 B，不合并、不互相抵扣。

截至新鲜准备取样，WSL backing filesystem 可用 1,014,082,801,664 B（/dev/sdd，ext4，mount ID 80）；承载 VHDX 的 Windows C: volume GUID 为 \\?\Volume{5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b}\，当时可用 28,729,638,912 B。VHDX 位于 C:\Users\Fancy\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc\LocalState\ext4.vhdx。该次读数是 PREPARATION_ONLY 样本；正式创建前仍须由同一 supervisor invocation 重新取样并绑定设备、volume GUID 与单调时序。

## 请求覆盖的唯一科学协议

- 先对冻结的 105 个 role 各运行一次 300 秒 reference 复现，区间和 support 身份按冻结登记核对；所有 105 个 reference 全通过后，才对同一 105 个 role 应用严格正时长 overlap treatment。任一 reference 失败时，立刻停止且 treatment 调用数为零。完整路径上限为 105 reference → 至多 105 treatment，即最多 210 次规则应用。
- Stage A 不读取 GT、资格、match 或 target 名单；candidate scorer fit/predict 均为 0。处理与参考区间多重集全部相同，则在首次 verifier fit 前以 MECHANISM_NOT_SUPPORTED 停止；support 差异只用于完整性核对。
- 仅在区间机制发生变化、Stage A 通过、输入身份/预算/资源/隔离门齐备且本卡另获明确批准时，才进入固定 5 outer × 4 inner Stage B。最多 25 verifier fit attempts、25 prediction batches、65 decoder calls、21 evaluator reservations。失败 attempt 计费；不重试、不续跑、不补额度。inner 每个 outer 的 12 份阈值预测全部冻结后才发布该 outer 的评价视图；outer 预测冻结后才发布 outer 评价视图。
- 六种非完成终态：REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE。只有完整且所有协议/收据有效的五折运行才记 COMPLETE。Stage A-only 不在本卡范围。
- 第 21 次 evaluator reservation 定义为**不读取 GT 的 pooled metric aggregation**：共21次 evaluator reservations = 15次 inner threshold phases + 5次 outer phases + 1次 pooled aggregation；只有前20次打开阶段限定的 GT worker view。最后一项仅归并五个 participant-disjoint outer fold 已接受的 participant metrics，不再打开 pooled GT view。跨 OS 的41个合成 participant 直接历史 evaluator 与五折归并对象相同；见合成证据。此语义是本卡请求批准的组成部分，不是已批准或真实输入等价证据。

路线 3 v1-003 保持合法 COMPLETE、四门 FAIL，不重跑；gap=0 严格重叠已由路线二覆盖。收到合法路线二结果前，不启动三个架构方向。

## 预算表

| 项目 | 当前拟议上限/公式 | 决定状态与强制证据 |
|---|---|---|
| Stage A wall | ≤1,200 s | 数值仍待负责人逐项确认；真实 supervisor deadline 未实现 |
| 全 study wall | ≤3,600 s | 数值仍待负责人逐项确认；须从 invocation 第一单调样本计时 |
| 累计 fit wall | ≤900 s | 数值仍待负责人逐项确认；必须不可重置 |
| 停止余量 | 提议 60 s | 尚未确认；需证明覆盖进程终止和 terminal 写入 |
| RSS | ≤min(4,294,967,296 B, floor(3 × 首次启动可用 RAM / 5)) | 上限及“RSS”的原指标尚未获批强制映射；必须覆盖 supervisor、helper、worker 全部研究进程 |
| 计算 workers | ≤2 | 尚未有整个 study 可核的 OS 强制证据；CPUQuota 不能代替 worker 数 |
| Stage A study filesystem | ≤2,147,483,648 B | 正式 controller 尚未创建/冻结；只能由同一正式 ext4 loop 硬限证明 |
| 完整 study filesystem | ≤4,294,967,296 B | 仅在 Stage A 完成、机制差异、N/M/S/B/D_A 门冻结并通过且 ledger fsync 后，原地扩同一 image/loop/filesystem；该正式 gate 尚未实现 |
| 镜像创建前 WSL backing free | ≥8,589,934,592 B | 负责人确认；正式启动时必须实时重测并绑定 backing device/mount |
| 镜像创建前 Windows VHDX 实体卷 free | ≥8,589,934,592 B | 负责人确认；正式启动时必须实时重测并绑定 volume GUID |
| Stage B 磁盘准入 | D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296 | 拟议公式仍待负责人确认；N/M/S/B/D_A 必须在 Stage A 后、fit 前冻结并持久记账 |
| Stage B RSS 准入 | 536,870,912 + 6 × 232M ≤ 冻结 RSS ceiling | 拟议公式仍待负责人确认；M 包含每折拟合及 held-out 行数 |

study 磁盘预算只描述专用 study 文件系统；controller 镜像/VHDX 分配与扩容、WSL backing 增量、systemd journal、外部 wall/receipt 锚点目前尚未按路径、卷身份和峰值纳入可信控制层例外清单，是否计入 2/4 GiB 指标也未获负责人裁定。所有 worker 写入（包括 /tmp、/var/tmp、/dev/shm、HOME/XDG、字节码、joblib/sklearn cache、core dump、phase IPC、stdout/stderr、模型、候选、ledger、lock）仍须由实际 OS mount/写拒绝证据证明受控。

## 冻结路径及当前身份

| 对象 | 本卡精确路径/身份 | 当前状态 |
|---|---|---|
| 来源登记 | 工作树下 artifacts/route2-candidate-overlap-v1-001-source-registration.json；SHA-256 e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853 | PREPARED_UNREVIEWED；外部只读审阅引用见审阅ID表；没有写入正式批准产物 |
| 投影视图根与 manifest | 工作树下 artifacts/route2-candidate-overlap-v1-001-inputs/；manifest 为 projection-manifest.json；SHA-256 ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad | PREPARED_UNREVIEWED；manifest 的 independent_review_id 为 null；本卡未列出或打开 110 个 GT 内容 |
| G1 与 role graph | G1 digest 68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30；role-graph digest 3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a | 只列冻结身份；正式 controller 的 metadata-only admission binding 未完成 |
| A2-004 config | configs/a2-context-verifier-v1-004.json；SHA-256 233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043 | 身份可列；完整 runtime 来源/代码绑定与跨 OS 数值等价仍未审结 |
| 精确逐文件输入映射 | 拟议 alias 形式 /run/route2-input/<sha256>；映射文件、各 role bind alias 和 mount receipt | NOT_CREATED；当前没有可批准的逐文件 path-map hash，不能视作输入路径冻结 |
| 正式 study image | /var/lib/route2/images/route2-candidate-overlap-v1-001.ext4 | 不存在，尚未创建 |
| 正式 study volume | /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume | 不存在，尚未挂载 |
| 唯一 study root | /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001 | 不存在 |
| append-only budget ledger | /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001-budget.jsonl | 不存在 |
| one-shot lock | /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001.lock | 不存在 |
| 冻结源码快照 | /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930h/source；manifest /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930h/source-manifest.json | 当前准备快照，98 files / 1,378,752 B；manifest SHA-256 520423b8bdb1372230140fd162ed8d21991593a071374c3899d27160c7cbc7b7；root-owned、mode 0555、逐文件验证；尚未由正式 controller 只读挂载；全实现正式复审仍为 FAIL |
| 冻结 Linux runtime snapshot | /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv；manifest /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv-manifest.json | 准备快照，11,330 files / 348,519,927 B；manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e；尚未由正式 controller 只读绑定/独立复审 |

源码树和关键闭包身份（当前 revision-20260930h，完整98个文件以manifest为准）：preimport launcher a50f1c2141fe3bf6ff57b9417c131db7b23276d463f9785de75b225872c13140；admission_bootstrap.py 1429f5cd55e20bcde3acc465e323738d756054c7baf8478abdab76613fdad6cc；linux_mount_controller.py b07bccd0d4c1a55c71cbb7a29db1bdc17ee014fbb66fa5c895dc60bad14152b4；path_map.py 69347620995da1d5ac22a2565b03a2af8b840869efd95c85e2b9bd135316d73c；linux_enforcement.py 22db48d59848d19928199a0eb4511b861a7d7ccd3ac0f21ac7d675567005af47；wsl_controller.py 4fe04e8c4ff333e40eca0d696f30f27e2dbfc99a35d78c85c88d6f0cdcccf0ef；phase_worker.py 9f1c09700a4bcd33733fe9ab6695192c91e12569f6be7bcf480115d53aa61831；stage_b.py a4173593346a2f63e32633274663a6b154cbe62b653292000692f8c5b2387e6e；external_admission.py 847ecb01ac2da0e169ca47c7fcfa44c29abdc43bfe6f9979559143521eca54a7；Windows entry scripts/run_route2_candidate_overlap_wsl.py e3af61cc3bad9d97f761e9a311f6b68644600f3f25dad766cbbca51ea36b2d81。这些关键hash与98文件整体manifest共同绑定源码准备身份，不构成独立冻结签名或批准收据。

Linux 依赖身份：requirements/route2-linux-cp310.lock SHA-256 `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`；requirements/route2-linux-cp310.identity.json SHA-256 `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`；ABI identity SHA-256 `ec35a5dbf14eb3ac020f35a5e6f44819059f1f9d405cfb1f5764344cb5651960`。环境为 Ubuntu 22.04 / WSL2、Python 3.10.12、CPython cpython-310-x86_64-linux-gnu、x86_64、glibc 2.35、kernel 6.6.87.2-microsoft-standard-WSL2；13-wheel离线安装与 `pip check` 通过。venv/代码快照仅为准备态；不能证明历史Windows 3.10.11与Linux整个真实A+B Stage B协议数值等价。

## 无项目数据证据与引用

| 证据 | 文件 SHA-256 | 能证明的范围 |
|---|---|---|
| 同卷 ext4 2→4 GiB + ENOSPC raw probe | docs/evidence/2026-09-29-route2-wsl-disk-probe-raw.json — a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939 | scratch 卷原语能力；不是正式 ledger-gated 扩容 |
| cgroup raw probe | docs/evidence/2026-09-29-route2-wsl-cgroup-probe-raw.json — 7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9 | 合成第三 task / 超额资源拒绝能力 |
| 旧 Linux synthetic wall probe | docs/evidence/2026-09-29-route2-wsl-wall-probe-raw.json — 302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c | fake receipt 缺失/迟到拒绝；不含可信 terminal 后持久外部锚 |
| 单文件只读 bind probe | docs/evidence/2026-09-29-route2-wsl-readonly-bind-probe.json — 7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257 | 一个合成文件在 worker 内只读且写入被拒；无 role rotation / GT 生命周期 |
| live cgroup observation | docs/evidence/2026-09-29-route2-wsl-cgroup-live-observation.json — c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096 | 合成 service 的 2 task、RLIMIT_AS 与拒绝第三 task；无全 study controller |
| Windows QPC 外部合成回执 | docs/evidence/2026-09-29-route2-windows-qpc-wall-probe-55aa8d5ee51a4902.json — 55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c | Windows QPC 测得 terminal/service/receipt 次序并持久化；synthetic terminal service，不是正式运行器集成 |
| QPC core / seal | core bf2b83546f8236682506b5a873ff81308792630fb91635abf55d1f3876f29bcb；seal 4975ce4b21e2365aa846bbfead2d1c81a812fbcb304ee2b0be3dbba780fdd6c0 | synthetic external receipt 的配对文件身份 |
| 源码快照 + 双层 preflight | docs/evidence/2026-09-29-route2-source-runtime-snapshot-and-two-layer-preflight.json — 506e23659875e4520a1cbff4b1eb8fbe9e38d83f0dbd93d9fa2b6d71262c061b | 快照 hash、ABI、准备时两层 free、宿主决定记录；不是正式建镜像时收据 |
| 更新后的source/runtime身份与namespace检查 | docs/evidence/2026-09-29-route2-prepared-source-runtime-revision-20260929c.json — ed13f420b610f1eeb30759d962d15eea4b736b42a623ba367dd6e1cecff2715d | 新90文件源码manifest、11,330文件venv manifest、ABI/解释器路径校验；formal readonly mount 未证明；正式namespace精确路径仍不存在 |
| source revision 20260930a + versioned-path runtime check | docs/evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930a.json — a9abd8f2404abd40d1b2b5b3ed2914dac6f6fea71540c0ab8ae35f10f17ed274 | 新90文件/1,233,457 B源码manifest逐文件校验，Linux ABI/解释器与venv manifest、pip check复核；正式namespace仍不存在；controller-owned RO mount仍未证明 |
| worker写路径scratch-loop probe | docs/evidence/2026-09-29-route2-wsl-worker-write-path-probe-route2-write-probe-21c0a063faf94ea6bf11d32f27096006.json — 7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca | `/tmp`、`/var/tmp`、HOME/cache、stdout/stderr 在该无数据探针中落同一scratch loop；不是全study controller/write-volume记账 |
| Windows↔Linux no-data numeric probe | docs/evidence/2026-09-29-route2-cross-os-synthetic-equivalence.json — 6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15 | Windows 3.10.11与Linux 3.10.12的指定合成16D/26D/HGB/decoder/metrics/pooled reduction输出hash相同；不含真实A+B输入或完整历史协议证明 |
| 正式 namespace 只读检查 | docs/evidence/2026-09-29-route2-formal-study-namespace-readonly-check.json — c5a0876532e00b06e38e362d03d4766b8d240e5807005c3ad3b7c72becf81a40 | exact image / volume / root / ledger / lock 在检查时均不存在 |
| revision-20260930h source/runtime 与 ABI 快照 | docs/evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930h.json — 8a9cfb221895e20315ca0f6dc6a6c18d9e29a61ffc27a26ce6a6c75a17079233 | 98文件源码与11,330文件venv逐项验证、ABI、pip check、准备态namespace absent；不证明正式只读挂载或准入 |
| controller/bootstrap synthetic v2 | docs/evidence/2026-09-30-route2-admission-controller-synthetic-v2.json — d92d6aadc4f6397776224ee19ce6c65aaca750e9101532d63eea967d86f50d49 | 当前源码绑定的无数据合成测试87 passed及能力边界；不证明真实OS生命周期 |
| Linux dependency runtime 记录 | docs/evidence/2026-09-29-route2-linux-dependency-runtime.md | offline wheel install、pip check、imports 与 ABI；不是安装态可信 bind 或 Stage B 数值等价 |

## 审阅ID与未关闭项

| 范围 | 审阅/批准标识 | 状态 |
|---|---|---|
| 来源登记只读审阅 | review_g1_projection:source-registration:e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853 | 外部引用；来源产物仍 PREPARED_UNREVIEWED |
| 物理 projection 只读审阅 | review_g1_projection:physical-views:ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad | 外部引用；manifest 的正式 independent_review_id=null，projection 仍 PREPARED_UNREVIEWED |
| 完整 Route2 controller + A+B 实现独立复审 | route2-ab-full-implementation-review-2026-09-29-FAIL-001 | 正式独立review为FAIL / NOT_APPROVAL_READY，早于revision 20260930a/h；后续窄范围review无正式review ID，不覆盖全实现且不是PASS；无 INDEPENDENT_REVIEW_PASS ID |
| role-mount lock leak 独立复核 | route2-path-map-revocation-lock-2026-09-29-CLOSED-001 | P2 Python `RLock`泄漏已关闭；真实OS撤销和异常worker teardown仍是P1 |
| 负责人 A+B 批准 | NOT_ISSUED | 无批准记录 hash；不得构造 FROZEN_ADMISSION |

当前仍阻止批准的 P1：

1. **正式特权controller/ResourceEnforcer缺失。** 无从首个Linux monotonic sample、双层pre-image检查、镜像创建、Stage A≤2 GiB到terminal close的唯一supervisor lifecycle。scratch 2→4 GiB probe未验证正式105+105、机制差异、`N/M/S/B/D_A`与ledger fsync gate。
2. **RoleMountController/PhaseRunner仍是抽象接口。** 没有真实逐role RO bind轮换、GT phase view发布、旧worker/FD关闭和异常revoke。不得提前打开110个GT视图。
3. **写路径与承载层预算未闭合。** worker全部写入尚未由正式OS controller强制落同一study卷；controller image/VHDX、WSL backing、systemd journal与外部QPC receipt尚无逐路径/卷身份/峰值清单和负责人预算裁决。
4. **全study资源限制未证明。** 合成cgroup probe没有把supervisor、hash/resize helper与worker纳入正式父cgroup；没有RSS ceiling和计算worker≤2完整强制回执。
5. **正式terminal后wall acceptance缺失。** QPC probe是合成能力证据；尚未与正式runner结合terminal append/fsync/close、receipt持久化、service exit/截止检查及crash/缺回执拒绝。60 s stop cushion仍待确认与验证。
6. **Frozen admission尚无无循环可信引导。** `contracts.py` 位于所哈希source tree内，不能把source digest及readiness pin编辑进它自身并维持该digest。保持 `FROZEN_ADMISSION=None`；待设计并独立审查source tree外的controller-sealed admission artifact/bootstrap。
7. **运行期source/data/runtime binding不完整。** Source revision 20260930a 和 venv 为逐文件校验的root-owned mode 0555准备快照；已修正`build_study_access_policy`仅接受旧canonical源码路径、会拒绝本卡revision路径的问题，并用 versioned-path 回归覆盖。无formal controller-owned read-only mount、canonical attestation、运行期path-map与metadata binding，Linux system library/标准库闭包尚未完全pin。`stage_b.py` 现已从冻结source root读取历史配置/代码；“仍读活动工作树”的旧说法已修正。
8. **真实A+B等价与GT control诊断未通过。** 跨OS synthetic数值一致性不等价于真实输入/完整历史协议PASS；label-prejoin、26D/HGB/G3/nested/threshold/decoder/matcher/evaluator全执行闭包仍待独立复审。当前只有treatment matched-GT commitments，缺control集合新增/丢失诊断；controller HMAC key创建、封存、仅child分发及销毁未实现。
9. **无独立PASS issuer/负责人批准。** 完整独立静态复审已返回 FAIL（记录ID见下）；没有 `INDEPENDENT_REVIEW_PASS` attestation，也没有负责人A+B批准hash。

**已关闭的 P2：**`path_map.py` revoke异常不再泄漏Python `_mount_lock`。独立复核ID `route2-path-map-revocation-lock-2026-09-29-CLOSED-001`；跨线程回归测试先按预期失败，修复后通过。真实OS bind撤销与异常worker teardown不在该P2关闭范围内。

**仍待负责人裁决的预算：**1,200/3,600/900 s、60 s停止余量、RSS公式与worker定义、2/4 GiB study额度、`N/M/S/B/D_A`准入式、controller image/VHDX、systemd journal、外部QPC receipt等卷外可信控制写入的计费政策。已确认的宿主信任与两处各≥8 GiB不再列为待决；正式创建前同次invocation的live复测仍未实现。

验证记录：锁回归先失败后通过；versioned-source-path回归先失败后通过；本版定向 Route2 synthetic suite 为 **43 passed（4.29 s）**。无项目数据cross-OS probe的指定数字输出SHA相同；不包含真实Route2/A2输入。详细独立review、P1/P2与能力边界见既有[2026-09-27 Route2 review的最新“整合后修订”](2026-09-27-route2-design-review.md)和[执行计划最新台账](../superpowers/plans/2026-09-28-route2-wsl-controller-execution.md)。

## 当前申请处置

本卡作为唯一研究ID的一次完整 A+B 条件授权申请资料提交，但标记为不可批准状态。申请内容完整列出，条件证据未闭合；当前不请求实验运行审批。负责人另行明确批准本卡的最终绑定版本之前，继续保持 FROZEN_ADMISSION=None、NOT_EXPERIMENT_AUTHORIZED；不启动 Stage A-only 或 A+B，不打开 GT，不重跑 Route3，不启动三个架构方向。

## 2026-09-30 整合后修订：h 快照、controller 修补与当前准入判断

本节是本卡当前执行视图，优先于此前20260930a–e的当前快照表述；旧快照与其证据保留为历史。唯一研究ID仍为 route2-candidate-overlap-v1-001。本次没有项目数据、score/cache内容或GT读取，没有创建image/volume/root/ledger/lock。

当前source准备快照 /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930h/source，98 files / 1,378,752 B，manifest SHA-256 520423b8bdb1372230140fd162ed8d21991593a071374c3899d27160c7cbc7b7，root uid 0、mode 0555；逐项完整校验通过。Linux venv /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv，11,330 files / 348,519,927 B，manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e，root uid 0、mode 0555；逐项校验通过。ABI为Ubuntu 22.04 WSL2、Python 3.10.12、x86_64、glibc 2.35、SOABI cpython-310-x86_64-linux-gnu；python SHA-256 a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；identity JSON fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；ABI identity ec35a5dbf14eb3ac020f35a5e6f44819059f1f9d405cfb1f5764344cb5651960；pip check输出 No broken requirements found. 逐文件验证和mode 0555不是只读bind，readonly_mount_proven=false。

当前关键源码hash：preimport launcher a50f1c2141fe3bf6ff57b9417c131db7b23276d463f9785de75b225872c13140；admission_bootstrap.py 1429f5cd55e20bcde3acc465e323738d756054c7baf8478abdab76613fdad6cc；linux_mount_controller.py b07bccd0d4c1a55c71cbb7a29db1bdc17ee014fbb66fa5c895dc60bad14152b4；path_map.py 69347620995da1d5ac22a2565b03a2af8b840869efd95c85e2b9bd135316d73c；linux_enforcement.py 22db48d59848d19928199a0eb4511b861a7d7ccd3ac0f21ac7d675567005af47；wsl_controller.py 4fe04e8c4ff333e40eca0d696f30f27e2dbfc99a35d78c85c88d6f0cdcccf0ef；phase_worker.py 9f1c09700a4bcd33733fe9ab6695192c91e12569f6be7bcf480115d53aa61831；stage_b.py a4173593346a2f63e32633274663a6b154cbe62b653292000692f8c5b2387e6e；external_admission.py 847ecb01ac2da0e169ca47c7fcfa44c29abdc43bfe6f9979559143521eca54a7；Windows entry e3af61cc3bad9d97f761e9a311f6b68644600f3f25dad766cbbca51ea36b2d81。完整98文件manifest为source tree最终身份，不构成独立签名或批准。

输入和业务身份沿用上表：source registration e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853，projection manifest ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad，G1 68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30，role graph 3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a，A2-004 config 233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043。登记和projection仍PREPARED_UNREVIEWED，projection independent_review_id=null；正式逐文件输入path-map仍NOT_CREATED。正式image、volume、root、ledger、lock仍absent；卡中不列或打开110个GT视图。

证据为 [revision h source/runtime](../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930h.json)，SHA-256 8a9cfb221895e20315ca0f6dc6a6c18d9e29a61ffc27a26ce6a6c75a17079233；及 [admission/controller synthetic v2](../evidence/2026-09-30-route2-admission-controller-synthetic-v2.json)，SHA-256 d92d6aadc4f6397776224ee19ce6c65aaca750e9101532d63eea967d86f50d49。当前完整Route2定向命令结果87 passed / 3.90 s；仅无项目数据合成测试，不证明真实Linux mount、worker/service lifecycle或正式准入。既有磁盘、cgroup、wall、只读bind、QPC、worker-write alias、跨OS合成与Linux依赖探针均保留在前述证据表及synthetic v2中，只作为它们各自范围内的能力或准备证据。

本轮repo-side pre-import launcher在Route2 bootstrap导入前核验root-only配置、完整source/runtime manifest、hash/path和只读mount记录，再exec冻结venv；但它没有安装到受保护系统路径，root-owned config、seal key、unit/service、外部可信supervisor均不存在。role mount controller/path-map现验证canonical manifest bytes/hash与FROZEN_ADMISSION path-map pin，拒绝绕过直接调用、重复精确挂载、role错序；revoke尝试清理所有alias、写失败收据并fail closed，mountinfo读取异常有专项synthetic回归。限定范围复核确认这些源码修补及覆盖缺口关闭，但无正式review ID；未验证真实namespace、kernel mount syscall、GT发布、worker子进程或FD生命周期，不能关闭生产P1。

完整协议维持105 reference全部通过后才105 treatment；Stage A不读GT、不fit/predict；interval multiset相同时在fit前以MECHANISM_NOT_SUPPORTED停止。之后固定Stage B 5×4，额度25/25/65/21。第21次是15 inner + 5 outer + 1 pooled aggregation reservation中的不读GT聚合项；只有前20次启动阶段GT worker。停止分类固定为 REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE；只有完整五折运行是COMPLETE。

预算候选值仍待负责人裁决：Stage A/总wall/累计fit wall 1,200/3,600/900 s；stop cushion 60 s；RSS min(4 GiB, floor(3 × 首次可用RAM / 5))；compute worker≤2；Stage A/全study disk 2/4 GiB；Stage B disk D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296；Stage B RSS 536,870,912 + 6 × 232M ≤ 冻结RSS上限。负责人已确认宿主账号所有者可信，以及镜像前WSL backing filesystem与VHDX实体卷各自至少8,589,934,592 B。image/backing/VHDX、systemd journal、QPC外部wall receipt、seal/controller receipts与系统写入路径需逐项绑定实际卷和峰值字节；清单及是否计入2/4 GiB均未闭合。

未关闭P1：正式特权supervisor/ResourceEnforcer及双层实时建镜像前gate；同一image的2→4 GiB及durable ledger门；真实private namespace、逐role只读轮换、阶段GT发布、child/FD退出与异常撤销；worker全部写路径OS拒绝和controller承载层实际卷/峰值账目；study级parent cgroup、RSS和worker≤2强制；terminal close后持久外部wall receipt、service exit/cutoff/crash/missing-receipt验收；source/runtime/system library/stdlib/input/path-map/A2/G1/registration/projection/approval精确运行期冻结和只读挂载；完整A+B历史协议与Windows→Linux真实数值等价独立PASS、control matched-GT差异诊断与HMAC key lifecycle；正式完整review PASS及owner approval ID。P2仍有除已确认两项外的wall/RSS/worker/disk公式和卷外写入范围裁决。原始probe不替代production lifecycle。

正式全实现review route2-ab-full-implementation-review-2026-09-29-FAIL-001仍是FAIL / NOT_APPROVAL_READY；最新limited follow-up无正式ID，INDEPENDENT_REVIEW_PASS NOT_ISSUED；A+B owner approval NOT_ISSUED。当前状态PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED，卡仍APPLICATION_BLOCKED。Route3 v1-003合法COMPLETE、四门FAIL、不重跑；gap=0由路线二覆盖；无合法路线二结果前不启动三个架构方向。负责人另行明确批准这张具体卡之前不讨论首次实验运行，不运行Stage A-only或A+B，不提前打开110个GT视图。



## 2026-10-01 唯一卡当前绑定：revision-q 与具体剩余门

本节更新本卡当前视图，不创建第二张卡、不改变唯一研究 ID，也不表示获批。ID：`route2-candidate-overlap-v1-001`；申请状态 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**；A+B owner approval ID `NOT_ISSUED`；`FROZEN_ADMISSION=None`。负责人已明确 Windows host-account owner 为可信，且 image 前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别独立 ≥8,589,934,592 B。

### 当前绑定路径和 hash

- 准备源码：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001q/source`；manifest `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001q/source-manifest.json`；101 files / 1,537,167 B，SHA-256 `0bd424e05b4307b39de5f142e7edeeb04a0c949d0ffc256a01d84b543bea7e7d`，root:root / 0555，101/101核验。必需配置 `configs/a2-context-verifier-v1-004.json` SHA `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043` 已纳入。
- Linux runtime：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv`；11,330 files / 348,519,927 B，manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`；Ubuntu 22.04 / Python 3.10.12 / x86_64 / glibc 2.35 / SOABI cpython-310-x86_64-linux-gnu；python `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`，lock `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`，identity `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`，pip check通过。尚无可信 controller-owned RO mount。
- 新安全 admission metadata projection：工作树 `docs/evidence/2026-10-01-route2-admission-metadata-projection.json`，逻辑 Windows path `E:\\bme_compitition\\.worktrees\\high-f1-event-stack-execution\\bme_compitition_next\\docs\\evidence\\2026-10-01-route2-admission-metadata-projection.json`，SHA `a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c`；仅含 source registration `e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`、projection manifest `ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad` 两个 digest及10个身份 pin，不含逐GT行数/census/records。metadata projection 及原登记/manifest均 `PREPARED_UNREVIEWED`，projection independent review/attestation均未签发。正式逐文件 role path-map `NOT_CREATED`。
- 完整准备证据 [revision-q JSON](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001q.json) SHA `45971eb401edec8a2a6ada14a4032fdebdbb4a78b8950f5e6859555e6c108ee2`。正式路径精确为 image `/var/lib/route2/images/route2-candidate-overlap-v1-001.ext4`；volume `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume`；root `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001`；ledger `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001-budget.jsonl`；lock `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001.lock`。五处均核为 ABSENT。

### 唯一申请协议与预算

申请协议不变：先做105个300 s reference且全部通过后，才对同105 role做最多105 treatment（105→105）；Stage A 零 GT、零 scorer fit/predict；candidate interval multiset 全同则 fit 前 `MECHANISM_NOT_SUPPORTED`。仅机制变化且所有 gates 通过后运行固定5 outer×4 inner，额度25 fits / 25 prediction batches / 65 decoder / 21 evaluator reservations；第21项明确为不读GT pooled aggregation。无重试、无续跑、无 Stage A-only 降级。六个非完成终态仍为 `REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`；仅完整五折可 COMPLETE。

待负责人裁决的额度继续完整列入本卡：Stage A/全 study/累计 fit wall 1,200/3,600/900 s；stop cushion 60 s；RSS≤min(4 GiB, floor(3×首次可用RAM/5))；compute workers≤2；Stage A/全 study disk 2/4 GiB；Stage B disk `D_A+3×(B+232N+8S)+268,435,456≤4,294,967,296`；Stage B RSS `536,870,912+6×232M≤冻结RSS上限`；N/M/S/B/D_A的精确定义、冻结时点与卷峰值记账未批。image/VHDX/backing、journal、QPC/seal/controller receipt和系统写入的真实volume/峰值、是否计入2/4 GiB也未批。host owner trust和两个各自≥8 GiB floor已决；正式 image 前实时重测仍必须由受审 controller 实现。

### 复审与未关闭项

| 复审/证据 | 当前状态 |
|---|---|
| `route2-ab-full-implementation-review-2026-09-29-FAIL-001` | 正式完整审阅仍 FAIL / NOT_APPROVAL_READY |
| revision-q 文件清单与近期源码有限只读复核 | 101/101及配置、近期修复范围 PASS；无正式 review ID，不等于完整 PASS |
| lifecycle fixes 限定只读复核 | 未发现范围内新缺陷；无正式 ID |
| `route2-path-map-revocation-lock-2026-09-29-CLOSED-001` | 保留为已关闭历史 P2 |
| 新完整 `INDEPENDENT_REVIEW_PASS` / A+B owner approval | NOT_ISSUED / NOT_ISSUED |

未闭 P1：受保护 privileged supervisor/ResourceEnforcer 与安装信任根；正式同一image 2→4 GiB durable gate；真实逐role/phase mount、GT发布、worker/FD退出及异常revoke；全部worker写路径OS硬限和controller承载卷峰值计费；study-wide RSS/worker≤2；terminal close后 durable 外部 wall/QPC、service exit/cutoff/crash/missing receipt验收；完整运行期source/runtime/ABI/input/path-map/approval冻结及metadata投影正式复核；完整历史A+B与Windows→Linux等价PASS；control matched-GT additions/loss与HMAC key lifecycle。

原始probe hash沿用本卡前表且不扩大其意义：磁盘 `a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939`；cgroup `7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9`；wall `302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c`；readonly bind `7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257`；live cgroup `c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096`；QPC `55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c`；worker-write alias `7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca`；cross-OS synthetic `6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15`；Linux原始依赖细节见既有 `2026-09-29-route2-linux-dependency-runtime.md`。跨OS JSON来自旧 stage_b hash `a4173593…`、仅 max_iter=40 的局部合成样例，不覆盖当前 `stage_b.py` hash `fe6a45eb…` 或完整A+B。

准备 suite 159 passed；没有项目数据、GT views、Stage A/B 或路线二科学结果。Route3 v1-003保持合法 COMPLETE、四门 FAIL、不重跑；gap=0已纳入路线二；没有合法路线二结果前不启动三个架构方向。负责人另行明确批准这张具备全部最终path/hash和复审ID的卡前，不讨论首次实验运行。

## 2026-10-01 唯一卡 revision-r 更新：申请仍 blocked

### 研究 ID、审批状态与固定科学合同

唯一 ID：route2-candidate-overlap-v1-001。负责人已确认 Windows 宿主账号 owner 为可信主体；正式 image 创建前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别独立至少 8,589,934,592 B。申请状态 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；准备状态 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED；owner A+B approval NOT_ISSUED。

先运行 105 个 300 s reference，全部合法通过后才运行相同 105 roles 的 treatment。Stage A 零 GT、零 fit、零 predict；candidate interval multiset 相同则 fit 前 MECHANISM_NOT_SUPPORTED。只有机制改变且所有准入门通过才执行固定 Stage B 5 outer × 4 inner：25 fits / 25 prediction batches / 65 decoder calls / 21 evaluator reservations。前20次按阶段发布 GT view；第21次只聚合五折已接受的 ParticipantMetrics，GT reads=0。无 retry、resume 或 Stage A-only。六个非完整终态为 REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE；只有完整五折可以 COMPLETE。

### 全部预算申请值（尚未批准）

| 预算 | 候选值 | 状态 |
|---|---|---|
| Stage A / total / cumulative fit wall | 1,200 / 3,600 / 900 s | 待批准 |
| stop cushion | 60 s | 待批准 |
| RSS | min(4 GiB, floor(3 × first available RAM / 5)) | 待批准 |
| compute workers | ≤2 | 定义和限制待批准 |
| Stage A / total study disk | 2 / 4 GiB | 待批准 |
| Stage B disk | D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296 | N/M/S/B/D_A 与计账面待批准 |
| Stage B RSS | 536,870,912 + 6 × 232M ≤ frozen RSS ceiling | N/M/S/B/D_A 与计账面待批准 |

image、WSL backing/VHDX、systemd journal、外部 QPC receipt、seal/controller receipt 和系统写入的 volume、峰值、是否计入2/4 GiB均未裁决。两项已定的信任/空间策略不再作为待问项；同一 invocation 实时 gate 仍未实现。

### 当前绑定的完整路径与 hash

- source root /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001r/source；manifest /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001r/source-manifest.json；103 files / 1,562,738 B；manifest SHA deee33c1a187f57cec0d9f5ce44443081db48a784b6252f5eb30ec098a433fdb；root uid 0 / mode 0555；证据 [revision-r](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001r.json) SHA 1bd7dcb8e6d6127e9a60d6b849312262cb8efbcff5693b678a3b0e1803f7bf82。真实 RO bind 未证明。
- cgroup backend SHA 8c65d7e50ef98eee2fbb296114b9931b277b58013f37db7dcc5b8276bd3cd9fd；test SHA 4d602a0754059ddda294f8abb59ba55f1c94d53649e2eedd29dd74097ce07b61；linux_enforcement SHA b36e317d3841246ef21a4b41cb122975ab59ba5d04cdb4b33e761898fd1b08c5；budget SHA 113084f5836ac91f73e4db25330eeced9b79392b55d6d9269710f26a3ef8a0a3；snapshot_scope SHA 8c46b34f5486f85f81b6789b126eb91cfff9bff642dadc9665e2a7edf31245e8。
- Linux runtime root /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv；11,330 files / 348,519,927 B；manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e；Python executable a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；identity JSON fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；ABI Ubuntu 22.04 WSL2 / Python 3.10.12 / x86_64 / glibc 2.35 / SOABI cpython-310-x86_64-linux-gnu，pip check PASS；ABI identity ec35a5dbf14eb3ac020f35a5e6f44819059f1f9d405cfb1f5764344cb5651960。
- 正式路径均当前 ABSENT：image /var/lib/route2/images/route2-candidate-overlap-v1-001.ext4；volume /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume；root /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001；ledger /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001-budget.jsonl；lock /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001.lock。正式 role path map NOT_CREATED。
- 安全 metadata projection：source registration e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853；projection manifest ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad；projection [JSON](../evidence/2026-10-01-route2-admission-metadata-projection.json) SHA a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c；status PREPARED_UNREVIEWED，10 identity pins、无 GT census。pins：A1 role graph 3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a；A2-004 audit-ready bf4e9a10a34e5f17b36d3632356cf8e50cdc1cdb60125fe1d78a9b4e4baabeb4；A2-004 config 233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043；A2 role digests 634ffeea5d877ff65f6f1f77d73c581ea2e1367d146bef971be4f9c6123702df；A2 audit-ready sidecar 9c45fcc8abe597fcf1d6b740d4a2d6b5384e2c01961d753eb17d2ec2f49ad723；G1 eligibility 68c5cd8ec6fe12813f8b39c9d31000d4e18bd6ea732840b67428db643aef3a30；GT role scopes 628d75042fd3e38e3dad01bc4df3d31f483b968d4f46b2d0eac002e08a3017e7；GT view registry 09055b4d2829a9d2d144fafd8409eea9ceb3a0e4446328b027620829305f5bb0；reference registry 7f790671ef2884943e41be2be3036c7611c6c0412f36a116686c61b3d23df21a；role input registry 5d5f1f59d58a9be265db9467261cf16c4d54bc43e87a2dd33c3b94723191edd3。
- 当前 live scratch [receipt v2](../evidence/2026-10-01-route2-live-cgroup-backend-scratch-v2.json) SHA 9897cb6ae717f77b2b41b2c3c4b5e6dd53cef68323e656518bfcf5efd101817a：单进程验证 service/cgroup 和退出清理，不证明生产 lifecycle。

原始 no-data probes 与 Linux dependency evidence 完整沿用：disk/ENOSPC a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939；cgroup 7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9；wall 302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c；single RO bind 7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257；live cgroup c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096；Windows QPC 55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c；worker scratch alias 7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca；cross-OS synthetic 6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15；Linux dependency note [path](../evidence/2026-09-29-route2-linux-dependency-runtime.md), SHA d0f352f70b5721d58cef37eae97c7a20e16212531c262f43c1a1e8f6fd8b83b0。Cross-OS receipt is bound to old stage_b.py a4173593… / max_iter=40 and does not prove current stage_b.py fe6a45eb5ef3409c12de895c5ae6656284730eb59667526987b4b301561240e5 or full A+B equivalence.

### 复审ID与未关闭状态

- 完整 review route2-ab-full-implementation-review-2026-09-29-FAIL-001：FAIL / NOT_APPROVAL_READY，继续有效。
- 历史关闭项 route2-path-map-revocation-lock-2026-09-29-CLOSED-001：只关闭 Python lock leak。
- revision-r cgroup backend quality review PASS 与 spec review PASS：局部、无正式 ID；完整 INDEPENDENT_REVIEW_PASS NOT_ISSUED；A+B owner approval NOT_ISSUED。
- 未关闭 P1：可信安装controller / SupervisorOps lifecycle；建镜前双层实时8 GiB与同一 image 2→4 GiB durable gate；逐 role/phase RO mount、GT release/revoke 和 child/FD teardown；全部 worker 写路径 OS 限制与controller承载卷峰值；study-wide RSS/worker≤2；terminal后 durable external wall/cutoff/exit/crash/missing receipt；完整 source/runtime/ABI/input/path-map/approval 运行期冻结；完整历史A+B/Windows→Linux等价、control matched-GT/HMAC；完整独立 PASS 和 owner approval。
- 未批准 P2：所有表内预算值，N/M/S/B/D_A 精确定义、冻结时点、外层卷和峰值账目。
- 全部准备和合成结果不代表实验结果。GT views opened=0；没有项目数据、score/cache、Stage A-only/A+B、正式 image/volume/root/ledger/lock、Route3 v1-003重跑或架构方向启动。

## 2026-10-01 revision-t：同一张申请卡的当前状态

本节更新现有唯一卡 `route2-candidate-overlap-v1-001`，不是第二张授权卡。申请状态继续 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**；准备继续 **PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED**。105 reference → 105 treatment、Stage A 零 GT、候选 interval multiset 全同则 fit 前 `MECHANISM_NOT_SUPPORTED`、固定 Stage B 5×4 与 25/25/65/21 额度、pooled 第21次 evaluator 不读 GT、无 retry/resume/Stage A-only 的科学合同不变。

### 当前源码、runtime 与合成收据

- 当前只读准备源码：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001t/source`；manifest `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001t/source-manifest.json`；105 files / 1,572,963 B；manifest SHA `b05a2655213ff2e9afba5943b11de99e886c8162bab195c90f2056f6edbde1f0`；root uid 0 / mode 0555。准备证据 [revision-t](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001t.json)。
- Linux dependency venv 仍为 `/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv`，11,330 files / 348,519,927 B，manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`，Python 3.10.12 / Ubuntu 22.04 WSL2 / x86_64 / glibc 2.35 / SOABI `cpython-310-x86_64-linux-gnu`；pip check 通过。模式 0555 仍不等于正式 controller-owned RO bind。
- 当前 probe [跨 OS revision-t 收据](../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001t.json)，SHA `6bf04a9e1128f0e3178c0ae32db14a95480245d62e21c5a4757626a23164102a`，绑定当前 Stage B SHA `fe6a45ebe5f3409c12de895c5ae6656284730eb59667526987b4b301561240e5`、A2-004 config SHA `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`、`max_iter=100`。features / decode / event metrics / pooled reduction hash 两端一致；score 有 194/200 bitwise equality，最大绝对差 `1.734723475976807e-18`，14 位小数舍入一致。没有已批准的 numerical tolerance，完整 Windows→Linux A+B equivalence 仍为 P1。
- Windows 3.10.11 完整 no-data Route 2 synthetic suite：**178 passed / 4.75 s**。启动参数和产物均未读取任何项目输入；这只是能力与实现测试，不是路线二结果。

### 独立审阅与仍阻断审批的事项

完整只读静态复审核验 revision-r 的 103/103 文件后判 **FAIL / NOT_APPROVAL_READY**，无正式 review ID。当前正式 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL。三项新增明确 P1：

1. Windows entry 仍只支持 preflight/OS probes；完整 `PhaseRunner` / `SupervisorOps` / `ResourceEnforcer` 仍为依赖注入协议，没有安装且受保护的完整 A+B execution boundary。
2. 旧 `max_iter=40` 收据作废为当前等价证据。revision-t 新 probe 仅是当前参数下的小型合成调用链，概率字节 hash 不同且无负责人批准的数值容差，不能替代完整 A+B 复审。
3. outer evaluator 未在同一 outer GT 上同时比较 reference/control 与 treatment candidate coverage，因此缺少 matched-GT additions/losses。

跨 OS probe 的窄 review 请求尚未返回；没有 `INDEPENDENT_REVIEW_PASS`，没有 owner A+B approval ID。所有预算仍待负责人审批：wall 1200/3600/900 s，60 s cushion，RSS 公式，workers≤2，Stage A/全程 disk 2/4 GiB，Stage B disk/RSS 公式及 N/M/S/B/D_A 定义、冻结点、承载层写入 volume/peak accounting。负责人已确认宿主账号 owner 可信；WSL backing filesystem 与 VHDX 实体卷创建前各自至少 8 GiB。正式路径均未创建，实时创建前复核尚未接入 controller。

未关闭项还包括真实逐 role/phase RO mount 与 GT 发布/revoke、worker 所有写路径 OS 限制、全 study RSS/worker 强制、terminal 后外部 durable wall receipt、runtime identity freeze、HMAC key lifecycle，以及完整五折实现和独立 PASS。不得提前打开 110 个 GT views。

**负责人当前没有可批准的完整卡。** 在以上 P1/P2 关闭、完整独立 PASS 和负责人另行明确批准这张带齐 hash/路径/预算/review ID 的同一卡之前，不启动 Stage A-only 或 A+B；Route3 v1-003 不重跑；不启动三个架构方向。当前 GT views opened=0，`NOT_EXPERIMENT_AUTHORIZED`。

## 2026-10-01 revision-u 当前绑定：同一张卡，仍不可批准

revision-t 收据中 `snapshot_scope.json` 的 hash 与所指快照 manifest 不同；窄独立复审核实后已将其标记 superseded。当前唯一卡绑定 revision-u，而不是另建一张卡：源码根 `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001u/source`，manifest SHA `ab898c849e1e22896813bb09866919cd6ed237ceaf8854ed524aef2d3fe1344f`，105 files / 1,573,062 B，scope hash `7aecc7db19975be35fc25c7789e7ad2000b05a5ca3e7d17209f7f1898cbdf6e6`。Windows UNC 与 Linux `/opt` runtime 均校验完整 manifest 并从同一个快照实际导入 Stage B；证据 [revision-u cross-OS](../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001u.json) SHA `73358db47b66d35a9eb663adf69c2d68779515a93398fc8441fad0bb428b7f7c`，prepared evidence [revision-u](../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001u.json) SHA `4441a4a24ea1fe01d1e3a4740ad3942ef0c86577dc595a84cda972e7dc3e525f`。

从 revision-u UNC 快照运行的 no-data synthetic suite 为 178 passed / 5.43 s。probe 用当前 A2-004 `max_iter=100`，两 OS 的合成 feature/decode/metrics/pooled reduction hash 一致；probability byte hash 不同，200 values 中 194 个 bitwise 相同，最大绝对差 `1.734723475976807e-18`、14 位小数舍入后一致。没有负责人批准的数值容差，因此 full A+B equivalence 未通过审阅。

### revision-u 之后仍待关闭的 P1/P2

- P1：缺少已安装、受保护的完整 A+B 执行入口；现有 Windows CLI 仍仅 preflight/OS probes，`PhaseRunner` / `SupervisorOps` / `ResourceEnforcer` 仍是注入协议。
- P1：同一镜像 2→4 GiB durable gate、创建前两处各独立 ≥8 GiB 的同次实时检查、逐 role/phase GT 发布撤销、worker 所有写路径与 controller 卷外计费、study-wide RSS/worker 硬限制、terminal 关闭后的外部 wall receipt 均未完整实现。
- P1：同一 outer GT view 上 control/reference 和 treatment candidates 的 additions/losses matched-GT 对照仍缺失；完整历史 A+B 与全数值跨 OS review PASS 也未签发。
- P1：controller HMAC key lifecycle、runtime source/dependency/ABI/input/path-map/approval 冻结、full independent review PASS 未完成。
- P2：负责人尚未批准所有 wall/RSS/worker/disk 上限、N/M/S/B/D_A 精确定义、候选式冻结时点，以及镜像/VHDX/backing/journal/QPC/seal/controller 写入对应卷及峰值是否计入。宿主 owner 可信与两处独立 8 GiB floor 已确认，但执行 gate 未实现。

当前完整 formal review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL；revision-u 独立窄复审已 PASS（source binding only，无正式 ID），不是 full A+B review。完整申请仍 105 reference→105 treatment、固定5×4与25/25/65/21、单次 A+B、预算候选值未获批；owner approval ID / `INDEPENDENT_REVIEW_PASS` / `FROZEN_ADMISSION` 均 NOT_ISSUED/None。状态 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**。不得启动 Stage A-only/A+B，不提前打开110个GT views，不重跑 Route3 v1-003，也不启动三个架构方向。
### pooled quota 语义更新与 revision-u 复审范围

Stage B 第四个配额现在定义为 21 个 evaluator/reduction 操作：20 次 GT-backed evaluator（15 inner + 5 outer）和 1 次不读 GT 的 pooled reduction。pool reducer 只合并五个互斥 outer fold 的 participant metrics；ledger/result 分别记录 evaluator 20、pooled reduction 1、pooled GT reads 0。合成测试对 100 组五折样本验证其与直接 pooled evaluator 等价；总配额仍为 25/25/65/21。该语义写入唯一申请卡，但 full A+B review 与负责人整卡批准仍必要。

revision-u narrow source-binding review 为 PASS（无正式 ID），范围限于 u 的 manifest/scope hash/路径绑定。当前 quota 代码改动发生在该 review 之后，新的 immutable snapshot/review 尚待完成。完整 formal review 仍 FAIL；P1/P2、INDEPENDENT_REVIEW_PASS、owner approval ID 均未关闭。唯一研究 ID route2-candidate-overlap-v1-001 仍 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，FROZEN_ADMISSION=None；不得运行 Stage A-only 或 A+B，GT views opened=0。

## 2026-10-02 revision-b：唯一完整 A+B 条件授权申请卡

**研究 ID：** route2-candidate-overlap-v1-001  
**申请状态：** APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED  
**正式批准 ID：** NOT_ISSUED；FROZEN_ADMISSION=None。此卡是完整条件申请，负责人尚未批准；不得以此启动实验。

### 一次运行的科学合同

- 先处理同一冻结角色图中的 105 reference roles。只有 105/105 reference 全部合格后，才处理对应 105 treatment roles；reference 任一失败时 treatment role 数为 0。每个 role 应用一次冻结 300 秒规则，禁止补跑/重试/恢复或挑选子集。
- Stage A 不读取 GT、不 fit/predict。A 必须生成完整 treatment candidate 行及精确 interval multiset；若与 reference 完全相同，在任何 fit reservation 前以 MECHANISM_NOT_SUPPORTED 停止。
- 只有完整 Stage A、机制差异、特征/标签/资源/准入门全部通过时，才进入固定 Stage B：5 outer × 4 inner。quota 固定为 25 fit、25 predict、65 decoder、20 GT-backed evaluator 与 1 GT-free pooled reduction；第21次 operation 是对五个 disjoint outer-fold metrics 的 pooled reduction，pooled_gt_reads=0。
- 仅六个终态：REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE；只有完整合法五折可为 COMPLETE。禁止 Stage A-only、局部 Stage B、重试、恢复或余量追加。

### 预算请求（均为待负责人批准的 proposed hard limits）

- Stage A wall 1200 s；whole-study wall 3600 s；单次 fit wall 900 s；到期前 60 s 开始 stop cushion。
- RSS ceiling = min(4 GiB, floor(3 × 首次读取的 available RAM / 5))；compute workers <=2。
- Stage A disk <=2 GiB；whole-study disk <=4 GiB。
- Stage B disk：D_A + 3 × (B + 232N + 8S) + 268,435,456 <= 4,294,967,296 bytes。
- Stage B RSS：536,870,912 + 6 × 232M <= 已冻结 RSS ceiling。
- D_A 是 Stage A 结束时 allocated bytes；B 是完整 treatment-candidate UTF-8 bytes；N 是 treatment candidate 总数；S 是 25 个 held-out predictions 总行数；M 是每个 verifier cycle 的四个 OOF training-role 行数与对应 held-out 行数之和的最大值。需按预注册语义冻结候选数量和模型数据；不得一次性预载 105 role matrices。
- 预算批准还须逐项给出 controller image、VHDX、WSL backing filesystem、systemd journal、外部 QPC receipt、seal/controller receipts 和任何 worker 临时文件的实际卷、峰值及其是否计入 2/4 GiB 限额。预算与这些定义目前均未获 owner approval。

### 固定路径与身份哈希

- immutable source：/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002b/source；manifest 82f563d2cac21a5916f03908e5e7cf404fba64157238b0d28027fc79443407f0；105 files / 1,657,792 B；scope 0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61；root uid 0 / mode 0555。
- Linux runtime：/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv；manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e；Python executable a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；Ubuntu 22.04 WSL2 / CPython 3.10.12 / x86_64 / glibc 2.35 / SOABI cpython-310-x86_64-linux-gnu；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；identity fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f。
- Windows parity runtime：CPython 3.10.11，interpreter SHA-256 3cce33d75d6fdae4e004d0bdf149320b3147482a9caf370079dcb9c191a1b260。该合成验证 runtime 并不代替正式 worker 的 Linux ABI freeze。
- A2-004 config 233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043；A1 frozen role graph 3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a；A2 role digests 634ffeea5d877ff65f6f1f77d73c581ea2e1367d146bef971be4f9c6123702df；source registration e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853；metadata projection manifest ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad；projection JSON a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c。该 projection 只有10项身份哈希，不含资格人数/GT census；它未获独立 attestation，不能设置 FROZEN_ADMISSION。
- 唯一正式输出位置拟为：image /var/lib/route2/images/route2-candidate-overlap-v1-001.ext4；volume /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume；root /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001；ledger /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001-budget.jsonl；lock /var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001.lock。所有正式对象目前 ABSENT；正式 role input path map 尚 NOT_CREATED；提议的输入 alias 为 /run/route2-input/<sha256>，但角色与阶段 bind receipt 尚不存在。
- 负责人已确认 Windows host account owner 为可信主体；WSL backing filesystem 与 VHDX 所在 Windows physical volume 在镜像创建前分别独立至少 8,589,934,592 B。运行时同 invocation 双卷重测尚未实现。

### 当前证据与审阅 ID

- [revision-b prepared source/runtime receipt](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002b.json)，SHA-256 c2e85d16ddd3fab1ef00b0bab536bcd8cd3a92dd900b4f7093fcaea2b9c2e301。
- [revision-b cross-OS synthetic receipt](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002b.json)，SHA-256 394ef837276c3693f18ff7eb1bc88c981e005eb74fc4927323797dc0170edc00；raw Windows/Linus outputs SHA-256 ea99e21601db369fa579acecb66117a20474a6e8815feb617f9cc36194cc1b52 / afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc。
- Windows / Linux revision-b Route2-only no-data suites 各 194 passed。Probe 的非概率哈希相同；概率 194/200 bitwise equal，最大绝对差 1.734723475976807e-18，负责人容差未批准。因此这是部分合成证据，不是完整 A+B 等价。
- 正式完整实现 review route2-ab-full-implementation-review-2026-09-29-FAIL-001 仍 FAIL / NOT_APPROVAL_READY。revision-b 全部实现只读复审 ID 与证据窄复审 ID 当前均 NOT_ISSUED，复审状态 IN_PROGRESS；不得称完整 A+B PASS。
- 原始能力探针和 Linux依赖证据哈希均留存于 review 的 revision-b 整合后修订中，包括 ENOSPC、cgroup、wall、read-only bind、live cgroup、Windows QPC、worker scratch alias 与 Linux dependency runtime note。

### 批准前必须关闭的项目

1. 安装并保护可信 privileged controller，实际接通 SupervisorOps、PhaseRunner、ResourceEnforcer；证明启动仅能由完整、哈希绑定的 A+B approval seal 解封。
2. 实现并 synthetic-verify 同一 image 的持久 2→4 GiB 门、同 invocation 两处独立 >=8 GiB gate；正式 private namespace role/phase RO mount、分阶段 GT 发布与异常撤销、子进程与 FD teardown、controller HMAC key lifecycle。
3. 限制 worker 所有可能写入路径并对 controller/image/VHDX/backing/journal/external receipt 的实际 volume 和峰值完整计账；全 study parent cgroup、RSS ceiling 与 worker<=2 强制；terminal close 后独立 durable wall receipt 并验证正常退出、超时、崩溃及缺失 receipt。
4. 正式冻结 source/dependencies/ABI、输入内容和路径身份、所有 approval/hash；完善同一 outer GT 中 reference 与 treatment additions/losses 的生产对照；取得完整 nested 5x4 A+B 静态复审 PASS 与完整数值等价审阅结论。
5. 负责人明确批准所有预算、公式语义和卷外/峰值计费，并在全部阻断关闭后另行明确批准本卡的确切 source/path/budget/review hashes。

负责人对这张卡的批准是后续运行讨论的必要条件，不是本次申请的预先授权。当前不得运行 Stage A-only/A+B，不得打开110个GT views，不得创建 image、volume、study root、ledger、lock；保持 NOT_EXPERIMENT_AUTHORIZED。

## 2026-10-02 revision-g：同一张卡的当前完整申请绑定

本节更新上述唯一研究 ID `route2-candidate-overlap-v1-001`，不是新卡。申请状态仍 **APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED**；本卡只提交条件申请，不是预算批准或运行授权。A+B owner approval ID `NOT_ISSUED`；`FROZEN_ADMISSION=None`。

### 科学范围与固定停止分类

- 105 个 reference roles 必须全部合格后才处理同一 105 roles 的 treatment：`105 reference → 至多 105 treatment`，每 role 一次冻结 300 s 规则应用。reference 任一失败时 treatment 数为 0。Stage A 零 GT、零 candidate scorer fit/predict；reference/treatment candidate interval multiset 完全相同则在首次 verifier fit 前停止为 `MECHANISM_NOT_SUPPORTED`。
- Stage B 仅在机制差异、完整输入身份/预算/资源隔离门通过并且此卡另获负责人明确批准后开始；固定 **5 outer × 4 inner**。固定额度为 **25 verifier fit / 25 prediction batches / 65 decoder calls / 21 evaluation-reduction reservations**，其中 20 个 GT-backed evaluator + 1 个 GT-free pooled reduction，最后一项归并五个 disjoint outer-fold participant metrics 且 `pooled_gt_reads=0`。失败 attempt 计账；不得 retry、resume、追加额度、运行局部 Stage B 或 Stage A-only。
- 仅允许以下终态：`REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`。仅所有五折和证据门完整有效才能标 `COMPLETE`。Route3 v1-003 不重跑；取得合法 Route2 结果前不启动三个架构方向。

### 预算请求及裁决状态

| 项目 | 申请数值/公式 | 当前状态 |
|---|---|---|
| Stage A / whole-study / cumulative fit wall | 1,200 / 3,600 / 900 s | 未批准，生产 deadline 未接通 |
| stop cushion | 60 s | 未批准，尚未证明覆盖终止与 terminal write |
| RSS ceiling | `min(4,294,967,296 B, floor(3 × first available RAM / 5))` | 未批准，全进程指标和硬强制未证明 |
| compute workers | ≤2 | 未批准，全 study OS 证据缺失 |
| Stage A / whole-study study volume | 2 / 4 GiB | 未批准，同一 image durable 2→4 GiB gate 未生产接线 |
| 建镜前 WSL backing filesystem free | ≥8,589,934,592 B | **负责人已确认**，同次实时 gate 未接线 |
| 建镜前 VHDX 所在 Windows physical volume free | ≥8,589,934,592 B | **负责人已确认**，与 WSL floor 独立、不合并；同次实时 gate 未接线 |
| Stage B disk | `D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296 B` | 未批准；需冻结 D_A/B/N/S |
| Stage B RSS | `536,870,912 + 6 × 232M ≤ frozen RSS ceiling` | 未批准；需冻结 M 定义和 ceiling |
| controller/volume peak writes | image、VHDX、WSL backing、journal、QPC wall receipt、seal/controller receipts、worker 临时文件 | 未批准；所有路径、实际 volume、峰值与是否计入 2/4 GiB 未定 |

宿主信任决定：负责人已确认 Windows host account owner 是可信主体。此项不证明 worker 隔离、只读输入、账本防篡改或 controller 安装可信。

### 当前冻结身份、路径和证据 hash

- 源码快照：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002g/source`；manifest SHA-256 `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`；105 files / 1,674,692 B；scope SHA-256 `0b27dddc1c252179ff62f6bccc48b01f68ec72583434101909e260dcf9658f8d61`；root uid 0 / mode 0555，revision parent mode 0755。revision-d 无效、revision-e UNC 无法验证、revision-f 已 supersede；这些历史快照均保留。
- Linux runtime：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/venv`；manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`；Python 3.10.12 / Ubuntu 22.04 WSL2 / x86_64 / glibc 2.35 / SOABI `cpython-310-x86_64-linux-gnu`；interpreter SHA `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`；lock SHA `c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76`；identity SHA `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`；ABI identity SHA `ec35a5dbf14eb3ac020f35a5e6f44819059f1f9d405cfb1f5764344cb5651960`。该环境仍是 prepared snapshot，未由可信 controller 只读绑定。
- Windows parity runtime：CPython 3.10.11，interpreter SHA `3cce33d75d6fdae4e004d0bdf149320b3147482a9caf370079dcb9c191a1b260`。它只供合成对照，不能替代正式 Linux worker ABI freeze。
- 输入/设计身份仍为：A2-004 config `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`；A1 role graph `3185f9bfa93e8b5cd4b1e549d96ab4da4d2b399119deb616129504a42a304f4a`；A2 role digests `634ffeea5d877ff65f6f1f77d73c581ea2e1367d146bef971be4f9c6123702df`；source registration `e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`；projection manifest `ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`；projection JSON `a1aeda0659cac64e519401c95b77e7904f4a8426002d8e355b7cf8224f8b063c`。现有 projection 未获独立 attestation，不可设置 `FROZEN_ADMISSION`。
- 正式拟议位置：image `/var/lib/route2/images/route2-candidate-overlap-v1-001.ext4`；volume `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume`；study root `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001`；ledger `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001-budget.jsonl`；lock `/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume/route2-candidate-overlap-v1-001.lock`。截至 revision-g 核验全部 `ABSENT`；per-role GT/input path map `NOT_CREATED`，不得提前打开 110 个 GT views。
- [Prepared source/runtime receipt](../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002g.json) SHA-256 `9c2a34758988b64d06987db4cf3710caa3afd9047b0b758fbb0b864f5b91ab67`；[cross-OS aggregate receipt](../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002g.json) SHA-256 `f74ab7ae43ac81c3772259f35c7afe82bb4300eb4f53dc8c9a5c4d68f4ce8346`；raw Windows/Linux output SHA-256 `1b7d9701689365a75ddd01d6d5a9a4801596fac1b858ecc3e7e98d6c3545a4ff` / `afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc`。
- revision-g 13-file Route 2 synthetic suite：Windows **203 passed / 10.81 s**；Linux **203 passed / 5.63 s**, one pytest `pythonpath` warning。Probe 非项目数据；跨 OS 非概率 hashes 一致、probability 194/200 bitwise equal、max abs `1.734723475976807e-18`，未获 tolerance，结论 `PARTIAL_MATCH_ONLY`。

### 审阅、P1/P2 与决定门

- 正式完整实现 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001`：`FAIL / NOT_APPROVAL_READY`，继续有效。revision-f 与 revision-g evidence-binding narrow review 均 PASS、无正式 review ID，范围限 receipt/hash/vector binding。revision-g narrow static source review 确认 exact-type approval guards、第21项语义和 same-outer-GT additions/losses 算法；无正式 ID，也不是完整 A+B PASS。owner approval ID 未签发。
- revision-g 修复 `AppendOnlyLedger.create` 和 `BudgetGuard.start` 的 duck-typed approval 绕过：两处要求 exact `ExperimentApproval`，并经合成回归测试和窄静态复核确认在创建任何 study path 或触发 OS 操作前拒绝伪造对象，该 P2 已关闭。
- P1 仍包括：安装可信 privileged controller 并把 `SupervisorOps`/`PhaseRunner`/`ResourceEnforcer` 接入完整 A+B runner；bootstrap frozen admission 持续绑定到 runner；production image/live free gates；role/phase RO mount rotation、GT 发布/撤销与 child/FD teardown；全部 worker 写路径限制和 controller/外层 volume 峰值账；study-wide cgroup/hard RSS/worker≤2；terminal close 后 outer wall receipt 对 exit/cutoff/crash/missing receipt 的持久验证；完整源码/依赖/ABI/输入/path-map/approval freeze；same-outer-GT 算法的生产 PhaseRunner 与真实执行证据；完整 5×4 A+B 及全数值等价独立 PASS。
- P2 仍包括预算数值、公式与 `D_A/B/N/S/M` 冻结语义、controller 与外部写入实际卷/峰值成本。第21项和 matched-GT additions/losses 的实现逻辑有窄源码 PASS，但完整 A+B review 仍 FAIL。

本卡还不是实验授权。负责人另行明确批准这张绑定确切源码、路径、预算和 review ID 的同一卡以前，不启动 Stage A-only/A+B，不创建正式对象，不打开 GT。保持 `FROZEN_ADMISSION=None` / `NOT_EXPERIMENT_AUTHORIZED`。
