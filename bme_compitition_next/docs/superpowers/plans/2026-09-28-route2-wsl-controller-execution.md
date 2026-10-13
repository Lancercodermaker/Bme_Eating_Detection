# Route 2 WSL Controller Implementation Plan

> **For agentic workers:** Use a task-by-task implementation and independent review workflow. Checkboxes record future work, not work authorized or performed by this document.

**Goal:** 使唯一`route2-candidate-overlap-v1-001`完整A+B申请拥有可审阅的WSL原生硬限控制器、隔离路径和运行期准入，再向负责人提交明确实验授权卡。

**Architecture:** 在Ubuntu-22.04 WSL2内使用只读代码/输入、phase/role限定的文件映射、systemd/cgroup v2父控制组和study专用ext4 loop卷。外层supervisor从invocation入口计时，负责2→4 GiB阶段转换、资源停止和terminal关闭后的回执；实验包只在冻结批准记录与OS实际限额一致时运行。

**Tech Stack:** Ubuntu-22.04 WSL2 Python 3.10.12、已准备的13-wheel哈希锁与隔离venv、systemd/cgroup v2、ext4/loop/resize2fs、现有`src/eating_event/route2_candidate_overlap/`。Linux依赖已能离线导入；可信只读安装快照及历史数值等价仍待复审，`pyproject.toml`下限不构成运行锁。

---

**状态：**`PLAN_PREPARED / INCOMPLETE / NOT_EXPERIMENT_AUTHORIZED`。此计划不授权测试项目流程、读取真实输入、Stage A-only、A+B、fit、评价或重新运行Route3。后端已选择为WSL原生；该选择不代表controller已实现。设计和当前准入证据分别见[路线二设计](../specs/2026-09-27-route2-candidate-interval-validation-design.md)及[既有review整合后修订](../../decisions/2026-09-27-route2-design-review.md)。

## 固定不变的科学合同

- Stage A无GT；先全105个300 s reference复现区间和support，任一失败即停；再全105个strict-overlap处理。只在区间多重集全部相同才以`MECHANISM_NOT_SUPPORTED`于fit前停止。路线二已覆盖**严格正时长重叠**这一机制；旧builder的`fuse_gap_ms=0`仍合并端点相接窗口，不能拿它充当本处理实现，也不另立同机制变体。
- 完整 A+B 一次事前授权；只有 Stage A 机制差异、N/M/S/B/D_A 预冻结式、输入/预算/资源门全部通过才进入 Stage B。固定 5 outer×4 inner；0 candidate scorer fit/predict；最多 25 verifier fit、25 预测批、65 decoder、20 次 GT-backed evaluator 加 1 次 GT-free pooled reduction（合计 21 个 evaluation/reduction 额度）；失败 attempt 计账，不自动重试/续跑。
- 拟议资源上限仍为Stage A/全程/fit wall 1,200/3,600/900 s，RSS `min(4 GiB, floor(3×首次启动可用RAM/5))`，Stage A/全程disk 2/4 GiB，compute workers≤2。负责人已确认镜像前WSL backing filesystem与承载`ext4.vhdx`的Windows实体卷**各自独立**至少8 GiB；60 s提前停止余量、其余预算及RSS/worker的OS强制指标仍**待负责人确认或修订**。
- 完整五折之外不报告性能结果；任何`REFERENCE_NOT_REPRODUCED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`INCOMPLETE_RESOURCE`或`VERIFIER_DATA_INSUFFICIENT`按原设计记录，不用新额度补跑。

## 文件边界

| 责任 | 拟修改/新增文件 | 审阅重点 |
|---|---|---|
| 冻结准入与Linux路径 | `src/eating_event/route2_candidate_overlap/contracts.py`、`inputs.py`、`references.py`、`gt_provider.py`、`execution.py`；新增`path_map.py` | 逻辑Windows登记路径和Linux物理打开路径分离；只认精确hash/role/phase映射；不修改已准备登记/投影字节 |
| OS输出与资源 | `budget.py`；新增`wsl_controller.py`和`scripts/run_route2_candidate_overlap_wsl.py` | 真实mount/cgroup receipt、一次性卷/账本、2→4 GiB门、全写位置约束、外层wall receipt |
| Stage B完整闭环 | `stage_b.py`、`execution.py`及必要的隔离adapter文件 | 原A2-004标签、26D、HGB、nested threshold、decoder/matcher/evaluator等价；不复用旧预载truth路径 |
| 审阅记录 | 既有设计、review、授权Prompt及本计划 | 历史记录保留；所有新增结论标注真实证据层级 |

## Task 1：固定运行合同和依赖身份

- [ ] 对`pyproject.toml`、本机Ubuntu Python/systemd/kernel、A2-004冻结config/代码与历史label-prejoin、`src/eating_event/metrics.py` interval-IoU做**精确范围**静态核对；登记版本/hash及未证明处。先不打开真实score/cache/GT，也不重跑A2/Route3。
- [x] 为Linux准备venv、13个精确包版本和wheel hash，记录安装来源、Python ABI；离线安装、`pip check`与关键import通过。**尚未完成**只读代码/venv安装文件快照和A2-004跨OS数值等价复审；任何不等价仍停在`INCOMPLETE`。
- [ ] 完成并接入机器可读准入记录：study ID、A2 audit-ready/role-digests/config hash、G1/role graph、来源登记、投影manifest、逐文件映射、代码/依赖/controller/Stage B adapter hash、路径、预算、独立review ID与负责人**另行明确**A+B批准ID。`external_admission.py`已实现封套/HMAC/pin格式纯校验并经无数据合成测试；它没有可信supervisor/bootstrap或生产调用者，`FROZEN_ADMISSION`仍为`None`，此验收项未完成。

**验收证据：**冻结清单与既有注册hash一致；历史label/IoU与A2完整等价通过独立审阅。任一身份未知不得进入真实输入准入。

## Task 2：WSL路径适配与阶段输入隔离

- [ ] 在`path_map.py`定义精确文件映射，而非通用`E:`前缀替换：键为原登记逻辑路径、SHA-256、role和phase，值为WSL只读bind别名与mount ID；运行前逐项核对hash、文件类型和授权范围。原登记/投影JSON字节及既有hash保持不变，映射清单单独hash并复审。
- [ ] 改造上表五个现有文件内的`PureWindowsPath`、drive及`Path(registered.path)`直接打开点；`gt_provider.py`从独立只读输入根取phase限定六字段视图，取消“GT输入必须和可写study同级”的假设。代码快照与venv只读；worker的`/mnt/e`及其他未列入输入不可见。
- [ ] 固定Stage A只见score/cache/reference，Stage B训练只见当前训练role资格视图；对每个outer，四个inner held-out角色在三个固定阈值下的**全部12份预测**先冻结，才发布该outer的inner评价视图并选阈值；outer预测冻结后才发布对应outer评价视图。每次phase/role worker退出时撤销其只读bind、关闭文件描述符并释放内存truth，不把上一角色GT留给下一角色。任何越phase、越role、符号链接/路径逃逸、Windows路径未映射均在读取前拒绝。
- [ ] 只用假文件做跨路径/错误hash/未到期GT的无数据反例检查；独立审阅所有文件打开路径和lease生命周期。**不得以一次全量挂载所有GT后由Python过滤来证明隔离。**

**验收证据：**每个已批准逻辑文件恰好映到一个可读对象；worker只能打开该phase/role允许的对象，GT释放有冻结prediction receipt链。若不能做到物理可见性隔离，不启动A+B。

## Task 3：study专用卷和双阶段磁盘硬限

- [ ] `wsl_controller.py`的特权supervisor冻结镜像及挂载点`/var/lib/route2/images/route2-candidate-overlap-v1-001.ext4`、`/var/lib/route2/studies/route2-candidate-overlap-v1-001-volume`。首次真实invocation前只读确认ID、镜像、挂载点、study目录、ledger及lock均未占用；从invocation入口起计后一次性创建，禁止重置或第二次执行。
- [ ] 创建Stage A可写容量≤2,147,483,648 B的ext4 loop；study目录、`-budget.jsonl`、`.lock`同级且同mount ID。把`/tmp`、`/var/tmp`、HOME/XDG缓存、日志、模型与所有临时/原子写导向该卷；禁用core dump、字节码等额外写，禁止worker其他可写挂载。镜像本身只供supervisor访问。
- [ ] 只有全105参考、全105处理、差异、Stage B入场式和账本`fsync`完成后，原地扩同一镜像/loop/ext4至≤4,294,967,296 B；记扩容前后mount ID、block device、`statfs`、已分配块和宿主镜像占盘。扩容失败、mount变化、写逃逸或ENOSPC均为`INCOMPLETE_RESOURCE`，不新建第二卷。
- [ ] 用**独立scratch ID/路径**的无数据合成卷分别验证2 GiB阶段阻断超额写、未满足Stage B门拒绝扩容、获准转换后仍不超过4 GiB，且前后为同一设备/文件系统/mount ID；运行期间Windows默认用户经UNC不能改写候选/ledger或查看未到期视图，terminal后只读审阅可访问。scratch不得创建、占用或重置正式`route2-candidate-overlap-v1-001`命名空间。预检需先确认root/loop/online resize实际可用；既有64 MiB探针不算本项通过。

**验收证据：**Stage A和全study各有实际OS容量收据，所有计费文件位于同一卷；镜像所在WSL backing filesystem与其`ext4.vhdx`所在Windows实体卷的精确设备/路径已冻结、创建前两层free各≥8,589,934,592 B且该预算解释由负责人批准。若无法可靠定位或核验Windows实体余量，保持P1。2 GiB卷自身不可能有8 GiB空闲，不沿用旧`startup_snapshot.free_disk_bytes`的字面检查。

## Task 4：cgroup、RSS、worker及wall的可执行停止

- [ ] 在一个父slice内限制**Linux特权supervisor、worker、hash/resize helper及其全部子进程**，worker service使用非`oneshot`类型，冻结实际`memory.max`、`memory.swap.max`、`pids.max`、`cpu.max`及继承链；异常、OOM和停止时关闭整个进程组。若有辅助进程确实不能纳入父slice，须另设同等强制计费并获负责人批准；仅worker子组收据不算全study RSS证据。记录cgroup峰值和逐进程RSS/线程；`CPUQuota=200%`不得充作worker=2证据。
- [ ] 定义计算worker、库线程、I/O/监控线程及子进程拓扑，冻结OpenMP/BLAS/sklearn并行设置，并在独立审阅中证明原“进程树RSS”和“compute workers≤2”被**硬约束**；若证明不了，提交预算指标修订供负责人确认，状态保持P1。
- [ ] 外层单调计时从invocation进入起，维护Stage A/fit/全程不可重置累计deadline；拟在每个剩余额度末端预留60 s用于杀进程和终态，具体余量经无数据负载/超时探针冻结。`RuntimeMaxSec`只是后备；不能使用对其无效的`Type=oneshot`。
- [ ] 改`budget.py:finalize`的权威计时链：terminal append→fsync→ledger close→外层结束时刻→绑定terminal hash的wall receipt→receipt fsync/close→**外层再次核对单调截止**。后核验缺少可信可审收据，或任一写失败、超时、部分终态、无receipt、试图续跑，均`INCOMPLETE_RESOURCE`；既有提前采样字段仅作过程参考。独立审阅须证明后核验收据的持久化不会留下新的未计时接受窗口。

**验收证据：**外部独立复审的控制器源码hash、OS属性实际值、合成超时/崩溃/线程/内存故障收据、terminal hash与wall receipt闭合。只读/合成检查不能推导出路线二模型效果。

## Task 5：运行期身份绑定与Stage B等价

- [ ] 启动准入先比较A2 audit-ready、role-digests、config、G1/role graph、来源登记`e6f03bb848b6271ebbf2f41f78c9d62d806b2fdd17690487c73265a302821853`、投影manifest`ad85c0190db71cabeca28894e2384b54afef7ec6927c4106bc2d1f735b3fc5ad`的**已独立审阅身份digest与物理隔离的批准元数据**，并核Stage A非GT文件实际hash。若A2/G1原文件混有标签/GT/资格，Stage A只用冻结attestation，不为重哈希而打开这些原文件；也不得提前打开110个GT视图。每个GT物理文件仅在其训练/inner/outer release门通过后，由可信reader在首次语义读取前核实际hash，失败即停。清单/路径/预算/代码/controller/独立review必须与负责人批准记录一一对应。两个现有产物`PREPARED_UNREVIEWED`及manifest null review ID不能靠调用方字符串改成PASS。
- [ ] 完成 stage_b.py 与隔离 adapter 的 25 个 fit/预测、65 decoder 及 21 个 evaluation/reduction 额度闭环；目前分账为 20 次 GT-backed evaluator 调用和 1 次 GT-free pooled reduction，completion 显式记录 evaluator_calls=20、pooled_aggregation_calls=1、pooled_gt_reads=0。训练标签、inner 评价、outer 终评分 phase 放行；逐项审阅 A2-004 的 16D+10D、训练资格/IoU>0.25、HGB、G3、nested 角色、阈值排序、180 s 最短输出、600 s decoder、matcher/evaluator 语义。只有候选连接谓词改变。
- [ ] 用无数据最小合成角色验证入口拒绝自填`ABReadiness`/`EnforcementReceipt`、路径hash漂移、提前GT、超调用额度及Stage A失败后仍想fit；只核协议/控制流，不生成真实候选或性能结果。

**验收证据：**独立审阅覆盖完整runtime绑定和非候选协议等价；没有未审的预载truth map或任意callback绕过。

## Task 6：复审、预算批准与唯一实验授权卡

- [ ] 独立审阅者读取精确实现、代码/依赖/映射/输入hash、无数据合成收据及WSL安装版本，逐项判定P1/P2；审阅范围与未测事项写回既有review。一次探针或文档一致性PASS不升级为controller PASS。
- [ ] 在原budget表上单独列出：2→4 GiB硬卷、WSL backing filesystem和Windows实体卷**两层**free各≥8 GiB、原RSS/worker指标的强制方法或修订、60 s stop cushion、Stage A/全程/fit wall 1,200/3,600/900 s、`N/M/S/B/D_A`式、全部写/读路径、terminal receipt和无续跑政策；由负责人逐项确认或改写。改变数值或指标后重审，不从A2/Route3额度继承。
- [ ] 仅当全部输入、实现、独立复审及预算闭合后，提交**一次完整A+B**具体授权卡，写明研究ID、105+105、25/25/65/21、单一差异、停机分类、审批记录hash。未得到明确A+B批准时保持`FROZEN_ADMISSION=None`和`NOT_EXPERIMENT_AUTHORIZED`，不启动Stage A-only。

## Task 7：仅在另行明确批准后的运行顺序

- [ ] 首次invocation先冻结外层时钟、绝对路径及资源快照，再创建唯一输出卷/ledger/lock；先重验批准清单与Stage A可见文件实际hash、mount和cgroup，任何不符在候选重建前停止。GT视图实际hash按Task 5规定只在对应release之后、首次语义读取之前核验。
- [ ] Stage A先完成并持久化105个reference；全通过才执行105个treatment。相同区间多重集则按获批协议以`MECHANISM_NOT_SUPPORTED`早停，形成合法机制证据而**没有完整五折性能结果**；差异时计算并冻结`N/M/S/B/D_A`，Stage B入场式失败则形成资源终态，不fit。
- [ ] 入场通过后原地扩卷，按预定nested顺序运行Stage B，逐个reservation/attempt/prediction receipt计账；每outer的12份inner阈值预测全冻结后才开放其inner评价GT，outer预测冻结后才开放outer评价GT。phase/role退出即撤销视图并释放truth；达到完整五折才报告原定所有指标和matched GT集合变化。失败即停，无重试/补额度。
- [ ] 无论终态，关闭进程、文件、账本，取得terminal后wall receipt、receipt fsync后核验和OS峰值，挂载转只读；合法早停可报告其预声明机制/资源证据，只有`COMPLETE`且所有收据/协议有效时才接纳路线二**五折性能结果**。把实际合法终态回填既有review；只有用户另行提供合法路线二结果后，才按其要求讨论三个架构方向各自的最小验证，不自动启动任何方向。

**当前停止点：**Task 1–6只有部分只读快照、路径策略与合成能力/解析器验证完成；正式特权controller、OS role/phase mounts、资源与terminal gate、完整独立PASS及剩余预算裁决均未完成。Task 7须另行明确实验授权。Route3 v1-003合法`COMPLETE`、四门`FAIL`，不重跑。

## 2026-09-29 执行台账与修订顺序（覆盖上文旧待办状态）

本节把已完成的**无数据能力取证**与未闭合的**完整控制器准入**分开。实际证据见[WSL scratch探针](../../evidence/2026-09-29-route2-wsl-synthetic-os-probes.md)，最新协议与host信任边界见[设计修订](../specs/2026-09-27-route2-candidate-interval-validation-design.md)。本轮没有Stage A/B、项目数据候选生成、训练或评价。`FROZEN_ADMISSION=None`，`NOT_EXPERIMENT_AUTHORIZED`。

| 门 | 当前证据 | 尚需执行与独立复审 |
|---|---|---|
| 本机WSL与双层free | Ubuntu-22.04 WSL2、systemd/cgroup v2；VHDX确在C:卷，probe前guest/host分别`1,015,001,432,064/38,540,595,200 B`，均≥8GiB；探针后host`34,479,841,280 B` | Linux supervisor取第一单调样本后、正式镜像创建前重新定位guest backing和Windows VHDX所在实体卷，分别实时检查≥`8,589,934,592 B`并绑定mount ID/volume GUID；不能以guest虚拟free替代host；负责人确认预算解释 |
| 2→4 GiB同卷 | scratch ext4在`2,040,373,248 B`及`4,152,066,048 B`两阶段均ENOSPC，扩容前后mount ID 647、device 7:0和UUID相同；scratch清理 | 正式controller只在完整Stage A、机制差异、冻结公式和账本fsync后扩同一卷；拒绝提前扩容、换卷、复用study ID；独立审阅其真实实现 |
| RSS/worker | synthetic cgroup读取`memory.max=268435456`、`swap.max=0`、`pids.max=2`、`cpu.max=200000 100000`，`LimitAS=134217728`；第三task/超额VMS遭拒 | 证明supervisor、helper、worker/库线程拓扑与RLIMIT_AS继承覆盖全研究计算，给原RSS与worker≤2保守数学上界和真实依赖导入收据；否则提交指标修订，不能给硬限PASS |
| 全写路径与阶段GT | 新exact path-map/reader及短寿命phase-worker代码骨架，GT首次hash延后至release，同FD核读 | 特权phase runner实现root-owned逐文件只读bind、精确mount receipt、进程/FD退出和撤销；worker无其他输入或可写挂载；正式镜像内所有临时/缓存/日志/输出/ledger/lock/receipt计费；源文件不变性；110 GT不得提前打开 |
| Windows host边界 | 当前Fancy账号可直接`wsl -u root`进同一发行版；当前账号属于本机Administrators | 负责人已确认Windows host account owner为可信主体，威胁模型选择已关闭；仍需正式controller证明worker可见性/只读边界，并在原A+B卡内绑定此决定 |
| terminal后wall | 过程ledger已有终态hash/close时刻字段草案 | 实现Linux ExecStart入口单调时钟、全部阶段deadline、停止余量、terminal关闭后持久receipt与独立服务退出/时间验收；验证超时、杀进程、崩溃、receipt缺失均fail closed。receipt自写无法自证最后fsync完成时刻，审阅须说明外部可信锚 |
| Linux身份和协议 | 13-wheel哈希锁、离线venv、ABI身份清单和metadata-only运行期校验代码已准备；历史label join/IoU静态复审已覆盖 | 签发独立attestation并核完整只读代码/venv安装文件快照，移除`stage_b.py`活动工作树读取，实际controller精确bind批准的A2/G1/来源/投影及路径；GT实际hash按release；独立复审完整Stage A+B及25/25/65/21、pooled第21项语义/跨OS数值等价 |

### 后续准备工作的强制顺序

1. host信任边界与双层各≥8GiB的解释已由负责人确认。仍须取得剩余RSS/worker强制映射、60s stop cushion及其他预算的具体确认/修订；在正式supervisor实现并复审前，不得把scratch PASS外推。
2. 锁定只读代码快照、Linux venv和`--require-hashes`依赖清单，记录Python ABI、wheel来源、版本/文件hash及A2-004兼容审阅；不得用`pyproject.toml`下限充当锁。
3. 从已审阅来源登记与物理投影**元数据**生成逐文件canonical path-map，保持原JSON字节与hash，独立审阅所有注册键/role/phase/别名；controller生成的mount receipt须由root-owned文件及实际mountinfo核验，调用方伪造对象不算授权。Stage A不得打开原混合label文件或110个GT物理文件。
4. 实现特权Linux supervisor、完整父cgroup、原指标保守限额、同卷写命名空间、2→4 GiB正式门、短寿命phase runner与唯一输入/输出可见性；用不含项目数据的反例验证路径逃逸、提前GT、外部写、线程/内存/磁盘超额、提前扩容、终态崩溃。所有probe使用scratch ID，禁止占用正式study namespace。
5. 实现并核terminal ledger append/fsync/close→外层wall receipt→receipt持久化→外部截止/服务退出验收链；完成A2-004历史label-prejoin、`metrics.py` IoU和Stage B完整代码/身份独立复审，特别验证inner 12预测门、各phase worker退出/GT清空、outer五折及pooled第21次评价精确等价。
6. 只在P1/P2全部关闭、所有代码/manifest/依赖hash与独立审阅ID明确、负责人确认**具体**预算后，制作一张唯一研究ID完整A+B授权卡。审批者另行明确批准之前`FROZEN_ADMISSION=None`，Stage A-only及A+B都不得运行。授权后的运行才按上文Task 7进行；本执行文档及新对话prompt均非实验授权。

- 完整 A+B 一次事前授权；只有 Stage A 机制差异、N/M/S/B/D_A 预冻结式、输入/预算/资源门全部通过才进入 Stage B。固定 5 outer×4 inner；0 candidate scorer fit/predict；最多 25 verifier fit、25 预测批、65 decoder、20 次 GT-backed evaluator 加 1 次 GT-free pooled reduction（合计 21 个 evaluation/reduction 额度）；失败 attempt 计账，不自动重试/续跑。

### 复审反馈后的下一轮实施验收清单

以下列项是**后续准入实施任务**，不是当前可执行许可。独立完整实现复审在既有[review最新修订](../../decisions/2026-09-27-route2-design-review.md)判为FAIL；已完成的scratch与Linux依赖准备只消除对应原语/安装可行性疑问。

- [x] 保存并独立复核2→4 GiB同卷、cgroup及wall合成探针完整JSON和SHA；新scratch已清理，正式study namespace未创建。此项只判**本机能力**PASS。
- [x] 锁定13个Linux wheel及其SHA，隔离venv离线安装、`pip check`和关键import通过；仍待可信只读快照、运行期安装文件验证、ABI绑定和A2-004数值等价审阅。
- [x] 负责人已决定本机WSL威胁模型中的Windows host owner为可信主体。此决策不代替OS只读隔离、controller完整性或来源/审批绑定。
- [ ] controller从Linux supervisor ExecStart第一单调样本开始，在**正式镜像创建前**以同invocation收据核WSL backing和VHDX物理Windows卷身份/空闲分别≥8 GiB；正式stage A镜像path/dev/inode/length、loop源、UUID、mount ID/device与容量冻结，105+105及公式/fsync门通过后只扩原卷到≤4 GiB。
- [ ] 用特权、短寿命的逐role租约使Stage A按105 role顺序轮换精确非GT只读bind；每次旧role worker/FD退出且mount撤销后才开放下一role。Stage B每个训练/inner/outer view同样需controller-signed mount/revoke/退出链；12份inner预测与outer预测的持久ledger门先于GT mount。
- [ ] 建立真实全study父cgroup和每进程RLIMIT_AS保守证明，含supervisor、hash/resize helper、模型进程/线程；实测锁定venv在原RSS上界及worker≤2下可工作。仅有合成`pids.max=2`和`LimitAS`拒绝不足。
- [ ] 用实际OS mount/write-denial证据覆盖研究输出、ledger/lock/receipt、模型、`/tmp`、`/var/tmp`、`/dev/shm`、HOME/XDG、Python字节码、joblib/sklearn缓存、core dump、phase IPC和stdio；系统journal若在study卷外，单列其系统开销合同与审批，禁止笼统“所有写都同卷”。源Windows文件须不可变快照或另有写者隔离。
- [ ] 冻结worker写入只能位于study ext4卷的mount清单；把controller的loop backing image写/扩容、Windows VHDX实体占盘、systemd journal与外层wall锚分别列为可信控制层例外，记录精确路径、卷身份、镜像长度/已分配块、VHDX及例外峰值。负责人明确这些开销是否计入原2/4 GiB study磁盘指标，或批准重定义；不得把承载镜像写入误写成study卷内部写入。
- [ ] phase runner私有生成并封存GT身份HMAC key，只向获准GT child分发、跨outer保持同key、不回传父进程；outer只回传承诺与数值，历史control matched IDs只在获准事后流程用同key承诺化比较。PhaseRunner异常需OS确认child退出、bind撤销，否则无合法terminal；原matched-GT集合诊断未闭合前不能称完整结果。
- [ ] 使用已写的metadata-only校验代码，把A2 audit-ready/role-digests、G1、来源登记、投影manifest、Linux lock/ABI、**完整Route2执行闭包/入口脚本/已安装依赖文件**、controller/phase worker、path-map和批准预算绑定到独立复审的attestation及controller封存的只读快照；`stage_b.py`不再从活动工作树读取配置/源码。启动时只核准许的metadata与Stage A非GT实际文件hash；110 GT视图各自release后首次读取前核hash。核历史`metrics.py`/`a1/metrics.py`运行时身份与跨OS数值等价；没有独立attestation、快照和精确bind时不得把准备代码记为运行期PASS。
- [x] 第 21 项 pooled 操作已明确为不读 GT、不调用 evaluate_participants 的单次 reduction reservation：在 5 个 outer fold 完成后归并五组 participant-disjoint ParticipantMetrics。代码与预算分账分别记录 20 次 evaluator、1 次 pooled reduction、0 次 pooled GT reads；100 组五折合成等价测试通过。完整 A+B 协议独立复审仍未通过。
- [ ] 做terminal ledger append/fsync/close后的外层持久wall receipt及服务退出/单调截止可信锚，覆盖超时/崩溃/缺receipt的反例；复审60s停止余量。独立审阅以上**全部正式实现与收据**，逐项关闭P1/P2。
- [ ] 负责人仍须裁决其余wall/RSS/worker/disk/入场公式/卷外写入预算，并另行批准**唯一完整A+B**具体卡；host信任与双层各≥8GiB解释已确认。此后才可按Task 7运行。当前不得启动Stage A-only或A+B。


## 2026-09-29 负责人决定后的实施验收更新（最新）

本节覆盖上方历史 checklist 中“宿主信任决定未定”及“双层 8 GiB 解释待确认”的当前状态，不代表 controller 实施完成或实验获批。

### 已完成的决策/准备项

- [x] 负责人把 Windows 宿主账号所有者列为可信主体。此为 threat-model 选择；研究 worker 的 OS 隔离、文件只读性与 supervisor 完整性仍须实现并独立复审。
- [x] 负责人确认正式镜像创建前，WSL backing filesystem 与承载 ext4.vhdx 的 Windows 实体卷分别各需 ≥8 GiB 可用，不合并计算。
- [x] 建立 root-owned、mode 0555 的源码与 Linux venv 准备快照。源码树 90 files / 1,210,019 B，manifest SHA-256 03b6cf9d1807bc0520bc00bcf83c27d05e6ed88da615e4895b897a235ffb9e90；venv 11,330 files / 348,519,927 B，manifest SHA-256 e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e。正式只读挂载、runtime admission 和独立审阅尚未完成。
- [x] 做无项目数据双层 free-space readiness sample：WSL /dev/sdd mount ID 80 free 1,014,082,801,664 B；Windows VHDX 所在 C: volume GUID \\?\Volume{5ea83f43-7b10-4ccd-bfad-c0c59dc9cd3b} free 28,729,638,912 B。正式镜像创建前同一 invocation 的实时重测仍未完成，sample 不是正式开门证据。
- [x] 运行期 namespace 精确只读检查显示正式 image、volume、root、ledger、lock 不存在；证据 SHA-256 c5a0876532e00b06e38e362d03d4766b8d240e5807005c3ad3b7c72becf81a40。

### 未关闭验收项（不得运行 Stage A-only 或 A+B）

1. **P1 — 特权 controller 生命周期：**实现 Linux supervisor 从第一 monotonic sample 开始的唯一 invocation；正式镜像创建前同时重测两层 free-space floor 并绑定设备；创建精确 image/loop/ext4；Stage A ≤2 GiB；完成 105+105 和机制差异判断、冻结 N/M/S/B/D_A 且 ledger fsync 后，仅原地扩同一卷至 ≤4 GiB。
2. **P1 — role/phase 输入可见性：**controller 逐 role 原子轮换只读 bind，关闭旧 worker/FD 后撤销再开下一项；Stage A 不见 GT。每个 training/inner/outer GT 通过短寿命 worker 单视图挂载；12 inner prediction receipts/outer prediction receipt 门先持久化，异常也确认 child exit、FD close、bind revoke。任何情况下都不得提前打开 110 个 GT。
3. **P1 — 写路径和承载层账目：**OS 强制 worker 的输出、临时、cache、IPC、stdio 等只写 study volume；controller image/VHDX、systemd journal 和外部 wall receipt 路径单独登记实际 volume/峰值并纳入批准账本。原 2/4 GiB 预算是否覆盖这些控制层写入仍待决定。
4. **P1 — 整个 study 的资源强制：**单一父 cgroup 纳入 supervisor、hash/resize helper 和 workers；记录 memory/swap/task/CPU 属性、逐进程 RSS/线程；用可强制方式实现 RSS ceiling 与 compute worker≤2，或提交明确的新指标给负责人审批。synthetic cgroup probe 不满足此项。
5. **P1 — terminal 后 wall 验收：**terminal ledger append/fsync/close 之后取得并持久化外部 wall receipt，receipt fsync/close 后再核对 cutoff，并由独立 service observer 核 terminal hash、停止时间、退出码、cgroup empty；检验迟到、crash、缺 receipt、无法续跑。60 s cushion 当前仍只是候选值，需 owner 确认并用无数据 probe 支持。
6. **P1 — 运行期 identity 与协议等价：**冻结并只读挂载 source/runtime snapshot；生成独立 review attestation；绑定 A2/G1/registration/projection/role-path-map、Linux ABI、入口及全 execution closure；消除 stage_b.py 活动工作树依赖。独立审阅完整 A+B 的历史 label-prejoin、26D/HGB/G3/nested/threshold/decoder/matcher/evaluator、25/25/65/21、pooled 第21次裁决与 Windows→Linux 全部数值等价；GT 文件只能按 release 后逐文件核 hash。
7. **P1 — 外部独立实现审阅：**对冻结 source/runtime、controller、phase lifecycle、路径映射、预算、合成收据和完整 A+B 执行闭包独立审阅并签发不可伪造 review ID。当前 ID 为 NOT_ISSUED；外部来源登记/投影视图的窄范围审阅引用不替代它。
8. **P2 — 剩余预算逐项裁决：**除了已确认的双层各≥8 GiB之外，负责人仍需确认/改写 Stage A / 全 study / fit wall 1,200/3,600/900 s、60 s stop cushion、RSS 公式、worker≤2定义、Stage A/full disk 2/4 GiB、两个 N/M/S/B/D_A 公式，以及 image/VHDX/journal/wall-anchor 的例外写入计费政策。

A+B 条件卡已写入[既有 decisions 目录](../../decisions/2026-09-29-route2-ab-authorization-card.md)，目前为 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；A+B approval ID NOT_ISSUED，FROZEN_ADMISSION=None。后续独立复审与预算闭合前不请求/记录实验批准。卡获负责人单独明确批准之前，不创建正式研究 namespace、不启动 Stage A-only 或 A+B。

无数据证据及全部 hash 见[条件授权卡](../../decisions/2026-09-29-route2-ab-authorization-card.md)、[既有 review 最新追加段](../../decisions/2026-09-27-route2-design-review.md)和[设计追加段](../specs/2026-09-27-route2-candidate-interval-validation-design.md)。Route3 v1-003 保持合法 COMPLETE、四门 FAIL，不重跑；gap=0 已在路线二覆盖，合法路线二结果前不启动三个架构方向。

## 2026-09-29 实施复审后的最新执行台账

本补充覆盖上方执行状态。当前卡仍为 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`；以下完成项都是准备实现、合成能力或review记录，不构成正式 controller PASS。

### 已落实

- 负责人确认 Windows 宿主账号所有者为可信主体；WSL backing filesystem 与 VHDX 所在 Windows 实体卷创建前分别要求≥8 GiB。
- `ExactPathMap.lease_role_view()` 的 revoke 异常不再泄漏 `_mount_lock`：锁释放移入外层无条件 `finally`。先失败的跨线程回归测试修复后通过，独立复核记录 `route2-path-map-revocation-lock-2026-09-29-CLOSED-001` 确认关闭。最新定向 Route2 synthetic suite：42 passed / 4.60s。
- Worker `/run/route2-worker` alias、`/tmp`、`/var/tmp`、HOME/cache、stdout/stderr 在 scratch ext4 loop 的同卷写入已由 no-data probe 验证；receipt SHA-256 `7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca`。仅关闭这一组具体重定向能力问题。
- Linux identity 修正后重新验证 venv/executable path、Python hash、Python 3.10.12、ABI、13个locked package版本、lock hash和`pip check`。当前 identity SHA-256 `fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f`。
- 当前 source revision `revision-20260929c` 已按既有90文件白名单重新复制、root-owned mode `0555` 并逐文件验证；manifest SHA-256 `9c0bd2c7218a4fbadac6d9254e4ce48aef3586ce84a12e518767a1da14fd90c5`。Linux venv snapshot 11,330 files / manifest SHA-256 `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`。无正式只读mount，不能标 runtime admission PASS。
- Windows 3.10.11 与 pinned Linux 3.10.12 的纯内存合成16D/26D/HGB/decoder/evaluator/pooled reduction outputs hash 相同；receipt `docs/evidence/2026-09-29-route2-cross-os-synthetic-equivalence.json` SHA-256 `6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15`。这是合成数值核验，不是历史A2-004/正式A+B全数值PASS。
- 完整独立静态复审 reference `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 返回 **FAIL / NOT_APPROVAL_READY**；P2 lock leak 的独立关闭记录如上。reviewer 未运行测试或实验，未读项目数据或GT。

### 仍为 P1，正式 privileged controller 未完成

1. 没有一个从第一 Linux monotonic sample、两层≥8 GiB live gate 到 terminal close 的正式 supervisor/`ResourceEnforcer` lifecycle；现有 2→4 GiB 是 scratch capability probe，没有正式105+105/差异/N/M/S/B/D_A/ledger gate。
2. `RoleMountController` 和 `PhaseRunner` 仍是 abstract interfaces；没有正式逐role只读bind轮换、GT阶段发布、旧FD关闭、child退出和异常撤销实现。不得打开110个GT视图。
3. worker全写路径OS拒绝尚无正式receipt；controller image/VHDX、WSL backing增量、journal和外部QPC receipt的卷外写入还没有逐路径与峰值清单并纳入budget决策。
4. 没有包含supervisor、hash/resize helpers与workers的full-study parent cgroup、RSS强制证明或≤2 compute worker的完整证据。当前cgroup proof只是单个合成service。
5. Windows QPC探针证明synthetic terminal close/inactive-service/persistent receipt链，但它没有接到正式Route2 service acceptance；terminal后receipt、60s cushion、deadline/crash/unclean worker和不可续跑尚未形成正式gate。
6. source snapshot pins不能写回包含自己的`contracts.py`而保持同一digest；未来需用source tree之外的controller-sealed admission artifact及可信bootstrap。保持`FROZEN_ADMISSION=None`。
7. 正式source/runtime read-only bind、A2/G1/registration/projection/path-map/ABI和approval运行期绑定仍缺。`stage_b.py`从冻结source root读取历史配置/代码的代码路径已修正；标准库/系统native-library内容闭包未完全pin。
8. 完整A+B历史协议与真实输入等价仍未独立PASS：历史label-prejoin、26D/HGB/G3/nested/阈值/decoder/matcher/evaluator全路径；仅treatment matched-GT commitments，缺control新增/丢失diagnostics；controller生成与销毁HMAC key lifecycle未实现。
9. 完整独立复审当前只有FAIL记录，无`INDEPENDENT_REVIEW_PASS`或不可伪造issuer ID。不能把FAIL记录或synthetic receipt当成review pass。

### 协议/预算申请状态

第21次pooled evaluator reservation 已定为不读GT的 pooled aggregation：总上限仍21（15 inner + 5 outer + 1 aggregate），只有前20个阶段触发GT worker。该精确语义及41合成participant直接评价/五折归并一致的receipt写入申请卡，由负责人审批时绑定。

停止分类仍为 `REFERENCE_NOT_REPRODUCED`、`MECHANISM_NOT_SUPPORTED`、`INPUT_NOT_AUTHORIZED`、`INVALID`、`VERIFIER_DATA_INSUFFICIENT`、`INCOMPLETE_RESOURCE`；只完整五折运行记 `COMPLETE`。仍待负责人确认/改写 1,200/3,600/900 s、60 s stop cushion、RSS/worker 定义、2/4 GiB、`N/M/S/B/D_A`公式及外层image/VHDX/journal/QPC计费范围。负责人两项已决定的信任与双层空间解释不再列为待决定项。

无论本台账项均不得在新卡单独明确批准之前创建正式研究namespace或运行Stage A-only/A+B。Route3 v1-003合法COMPLETE且四门FAIL，不重跑；gap=0继续由路线二覆盖；无合法Route2结果前不启动三个架构方向。

## 2026-09-30 路径策略回归与当前源码身份

- `build_study_access_policy`原先只接受canonical source path，与卡上revision snapshot路径冲突。已改为允许canonical或`revision-YYYYMMDD[a-z0-9]{1,8}`下精确`source`/`venv` leaf；新回归覆盖`revision-20260929c/source`可用和未版本化`revision-current/source`拒绝。versioned-path regression先失败后通过，目标测试2 passed。
- source已刷新为`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930a/source`，90 files / 1,233,457 B，root-owned mode 0555，manifest SHA-256 `d185893bdf5cde2d8d9cdeecfc4e686fe361cd9ca72454ae0783cddb33c64e38`。新prepared identity evidence SHA-256 `a9abd8f2404abd40d1b2b5b3ed2914dac6f6fea71540c0ab8ae35f10f17ed274`；其中再次验证 source manifest、Linux ABI、解释器 identity、venv manifest及`pip check`。本次没有 formal read-only bind。
- 本轮改动只对齐冻结路径与策略，不关闭正式source/runtime mount、admission、ResourceEnforcer、RoleMountController/PhaseRunner、全study cgroup、terminal wall、真实协议等价或独立review FAIL。申请卡必须绑定revision 20260930a；在修订源码获得完整独立 PASS 和负责人批准前，Task 7仍禁止执行。

## 2026-09-30 最新执行台账：revision h、synthetic验收与剩余P1/P2

本节是当前执行态，覆盖此前source revision 20260930a及早期实现状态的“当前”表述；历史条目保留。唯一study ID route2-candidate-overlap-v1-001。当前PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED，正式image/volume/root/ledger/lock均不存在；无项目数据、无GT view、无合法Stage A/B。

### 已验证的准备产物

- 当前完整源快照 /opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20260930h/source，98文件/1,378,752 B，manifest 520423b8bdb1372230140fd162ed8d21991593a071374c3899d27160c7cbc7b7，root:root / 0555，逐文件校验通过。
- 冻结安装环境 /opt/route2/snapshots/route2-candidate-overlap-v1-001/venv，11,330文件/348,519,927 B，manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e，root:root / 0555，逐文件校验通过；Python 3.10.12、x86_64、glibc 2.35、SOABI cpython-310-x86_64-linux-gnu；python SHA a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae；lock c749dcb067a1b18bd53eedf26fb9d2f58589cf0dd55d9860407c949f699bdb76；identity fa195a6a17a21815cff59f4146b807dfb6e0d1dd2aa6f09411ebf3e67270658f；pip check通过。
- 证据：[revision h source/runtime](../../evidence/2026-09-30-route2-prepared-source-runtime-revision-20260930h.json)，SHA 8a9cfb221895e20315ca0f6dc6a6c18d9e29a61ffc27a26ce6a6c75a17079233；正式readonly bind仍false。记录确认study namespace精确路径均absent。
- no-project-data定向套件重跑：完整Route2 command 87 passed / 3.90 s；绑定source revision h与test hashes的[synthetic v2](../../evidence/2026-09-30-route2-admission-controller-synthetic-v2.json)，SHA d92d6aadc4f6397776224ee19ce6c65aaca750e9101532d63eea967d86f50d49。synthetic只验证解析/协议/假系统和fail-closed行为。
- launcher prototype scripts/route2_preimport_launcher.py在导入Route2包前由系统Python -I -S核验受保护config、完整源码/依赖manifest、路径/hash与RO mount record并exec冻结venv；mount controller与path-map绑定canonical manifest bytes及frozen path-map pin，拒绝重复mount及role错序，revocation失败持久化fail closed。launcher尚未安装；无system root config/key/seal/unit/service或可信外部supervisor。
- 限定只读review确认直接pin bypass、重复精确mount、重复revoke mountinfo error evidence/test等源码缺陷已修；follow-up无正式review ID。真实mount namespace、kernel bind syscall、worker child/FD lifespan、GT发布撤销均未验证，不能结项。

旧无数据probe和Linux依赖证据仍作为能力边界证据保留：disk/ENOSPC a5a0923f583a1ac800d05e06bcf6a2a154851551e840950719ca2b4bb4ad5939，cgroup 7c0e0272095e7cd74f2e6ecb7d97ff37a17ab3ea137b57a479e0af84eafab6f9，wall 302c5082a71aea4872e7d65c145b9febfe3200d9e6134f513936018d89ce9d4c，single readonly bind 7a5aadb5039b56a1bd1a5f1fa8bb6110135cb28a343e476a7a1e954bdf51a257，live cgroup c12c590b609e25d8239c0b967ee6d0d6d559bd5585128176724143f91391a096，Windows QPC 55b20cb2f23eade6281034231cd16c0553ebc0395f2a28d78118f9a19d32821c及配对core/seal，worker scratch-write alias 7f175ae5e57353bb736d57db64861626e570517d5e48de4455d098cebadabdca，cross-OS synthetic 6629925e40e1289fd9354d21b5b7e6a0f74dc459fa4a06cd5cda58482f37ce15；精确路径、完整SHA和scope详见唯一授权卡证据表与synthetic v2。Linux锁/identity/wheels/ABI/pip check见2026-09-29-route2-linux-dependency-runtime.md。这些都不是正式研究controller收据。

### 剩余P1：批准前必须完成

1. 安装并钉定source tree外可信pre-import launcher、受保护root config/seal key、systemd unit/service和外部supervisor；独立证明bootstrap导入前信任链。
2. 实现正式privileged ResourceEnforcer/supervisor，从first monotonic sample开始；正式image前同一invocation分别重测两层≥8GiB空间并绑定真实device/volume；Stage A≤2GiB执行完整105+105和差异判断；durably冻结N/M/S/B/D_A与ledger之后仅同一image原地扩到4GiB；terminal close及失败分类不可续跑。
3. 实现真实private mount namespace与逐role只读rotation；先关闭旧worker/FD再撤销并开下一role；training/inner/outer GT按阶段发布，满足12 inner/outer prediction receipt门后才发布evaluation view；异常时回收child、FD、mount并持久化receipt。不得提前打开110个GT view。
4. 对worker全部输出、/tmp、/var/tmp、/dev/shm、HOME/XDG、cache、pyc、core、IPC、stdio等写路径作OS硬限制和逐路径容量计费；controller镜像/backing/VHDX、journal、外部QPC与seal/controller receipts、系统写入列出真实volume和峰值预算。
5. 单一父cgroup涵盖supervisor/hash/resize helper/workers；证明RSS ceiling与≤2 compute workers的可强制约束。
6. terminal ledger append/fsync/close之后持久化外部wall receipt；receipt fsync/close后核cutoff、terminal hash、service exit和cgroup empty；覆盖迟到、crash、missing receipt且禁止续跑。
7. 按revision h及locked runtime独立冻结完整read-only source/runtime与Linux ABI/system library closure；冻结输入身份和path-map、A2-004/G1/source registration/projection/role graph/approval pins；真实RO bind/metadata checks从可信controller进入worker。
8. 完整独立审阅A+B历史协议、105+105、5×4及Windows→Linux完整执行数值等价；裁决并确认第21次pooled aggregation协议语义；补control matched-GT additions/loss诊断与HMAC key lifecycle。当前跨OS证据只限指定合成数组/metrics。
9. 对完整冻结实现、真实system lifecycle及全部预算发正式INDEPENDENT_REVIEW_PASS ID。既有正式review route2-ab-full-implementation-review-2026-09-29-FAIL-001保留FAIL；limited follow-up没有正式ID，不得包装为PASS。

### 条件卡待负责人裁决的P2与预算

- 已确认：Windows host account owner可信；image前WSL backing filesystem与VHDX所在Windows物理卷各自≥8,589,934,592 B。正式同时测量门仍属P1。
- 尚未批准的请求值：Stage A/全study/累计fit wall 1,200/3,600/900 s；stop cushion 60 s；RSS min(4 GiB, floor(3 × first available RAM / 5))；compute workers≤2；Stage A/total disk 2/4 GiB；Stage B disk D_A + 3 × (B + 232N + 8S) + 268,435,456 ≤ 4,294,967,296；Stage B RSS 536,870,912 + 6 × 232M ≤ frozen ceiling。
- N/M/S/B/D_A的实际量定义与冻结时点；image、WSL backing/VHDX allocation、systemd journal、外部QPC、seal/controller receipts和系统写入的volume/peak/是否计入2/4 GiB都需逐路由并裁决。

唯一A+B卡已绑定source/runtime、输入、路径、原始probe、预算候选、完整协议、review refs及停止分类，状态APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；owner approval NOT_ISSUED。协议为105 reference→105 treatment；Stage A零GT/零fit/零predict；同interval multiset fit前MECHANISM_NOT_SUPPORTED；Stage B固定5×4 / 25/25/65/21；第21项pooled不读GT；仅完整五折为COMPLETE，其他六种终态按唯一授权卡。负责人另行明确批准该具体卡以前不讨论首次实验运行，不跑Stage A-only/A+B，不开110 GT。Route3 v1-003合法COMPLETE、四门FAIL不重跑；gap=0由Route2覆盖；无合法Route2结果前不启动三个架构方向。



## 2026-10-01 当前执行台账：revision-q / 159 合成门 / 仍不可运行

唯一 ID `route2-candidate-overlap-v1-001`。owner 决定已录入：Windows host account owner 可信；正式镜像前 WSL backing filesystem 与 Windows VHDX 实体卷分别独立 ≥8 GiB。尚未产生正式 study image/volume/root/ledger/lock；没有 Stage A-only/A+B，GT views opened=0、project data used=false、`FROZEN_ADMISSION=None`。

### 已完成且可复核

- 修复 completion quota 的实际语义、ext4/image 容量合同、迟到 completion 失败证据、outer fold 资源释放及运行前 metadata 隔离；新增 RED→GREEN 合成回归，不触碰项目数据。
- 新增安全 admission projection（原两份完整 manifest 只作为 SHA 绑定），path/hash 贯穿 frozen admission/readiness/approval；合成验证明确拒绝顶层与嵌套额外字段，并捕获 preflight 不打开完整 manifest。projection 状态仍 PREPARED_UNREVIEWED、独立 attestation NOT_ISSUED。
- Route2 合成门 159 passed / 3.30 s。源码 revision-q：`/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261001q/source`，101/101 文件逐项验证，manifest SHA `0bd424e05b4307b39de5f142e7edeeb04a0c949d0ffc256a01d84b543bea7e7d`，root uid 0/mode 0555；配置 `configs/a2-context-verifier-v1-004.json` 已纳入且 hash `233c88d156386dade979301f65a86a189921d77b9330f05594edd48939e00043`。准备 source mode 0555 不是正式只读 mount。
- Linux venv 11,330 files / 348,519,927 B，manifest `e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e`；Python 3.10.12 / Ubuntu 22.04 / x86_64 / glibc 2.35 / SOABI cpython-310-x86_64-linux-gnu；pip check 通过。证据：[revision-q](../../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001q.json)，SHA `45971eb401edec8a2a6ada14a4032fdebdbb4a78b8950f5e6859555e6c108ee2`。
- 保留原始磁盘、cgroup、wall、single RO bind、live cgroup、QPC、worker scratch alias、cross-OS 和 Linux 依赖证据及 SHA，见唯一授权卡证据表；它们仍仅是窄范围能力/准备证据。

### 复审登记

`route2_lifecycle_review` 对 quota/capacity/completion/memory fixes 限定只读复核未发现新缺陷，无正式 review ID。`route2_independent_review` 核验 q 的101个文件、所有 Route2 package / Windows entry scripts / requirements / 11个 Route2 tests 与历史 A2 config，全匹配并确认近期修复；这是有限范围 PASS，不出具正式 ID，也未核验 production lifecycle。`scripts/probe_route2_cross_os_synthetic.py` 不在 q。完整正式 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 仍 FAIL / NOT_APPROVAL_READY。

### 必须继续完成的批准门

1. 安装并审阅受保护系统路径下的 pre-import launcher、root-only config/key、systemd unit/service 与可信外部 supervisor；接通 `ResourceEnforcer`、`SupervisorOps`、`PhaseRunner`。
2. 用同一正式 image/loop/filesystem 完成实时双层 8 GiB gate、≤2 GiB Stage A、持久 ledger gate 后原地扩容；实现从首个 monotonic sample 到 terminal close 的不可续跑生命周期。
3. 对每 role/phase 做真实 private namespace 与 RO mount；GT 分阶段发布，关闭旧 worker/FD 后撤销，异常必须持久化 revoke/failure receipt；禁止提前开 110 GT views。
4. 强制 worker 全部写路径落入已批准硬限并逐路径计费，逐项绑定 image/WSL backing/VHDX/journal/QPC/seal receipts 的真实 volume、峰值和 2/4 GiB计账裁决。
5. 证明 whole-study parent cgroup/RSS ceiling 与 compute workers≤2；terminal close后持久化外部 wall receipt 并检验 service exit/cutoff/cgroup empty/crash/missing receipt。
6. 完成完整历史 A+B/Windows→Linux 数值等价独立审阅；跨 OS receipt 绑定旧 stage_b.py hash，max_iter=40，不是当前完整100迭代闭包。补 control matched-GT additions/loss 与真实 HMAC key 生命周期。
7. 批准全部 wall/RSS/worker/disk/N/M/S/B/D_A/卷外写入预算；更新唯一卡后签发新的完整独立 PASS ID，再由负责人另行明确批准那张绑定 q 和全部路径/hash 的卡。

当前候选额度仍为 Stage A/total/fit 1,200/3,600/900 s、停止余量60 s、RSS min(4 GiB, floor(3×首次可用RAM/5))、worker≤2、2/4 GiB、磁盘式 `D_A+3×(B+232N+8S)+268,435,456≤4,294,967,296`、RSS式 `536,870,912+6×232M≤frozen ceiling`；这些数值和定义均待批准。停止分类及105→105、5×4和25/25/65/21语义保持卡内原值。除非负责人批准最终具体卡，否则保持 `APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED`，不执行任何 Stage A/B。

## 2026-10-01 执行更新：revision-r cgroup backend 与剩余准入门

### 本轮完成

- 新增 cgroup backend：严格读取 systemd unit properties、校验资源 envelope 和 InvocationID；采集前后比较 unit/PID/invocation 与 cgroup2 mount identity，再复用现有 cgroup/process validator。模块 SHA 8c65d7e50ef98eee2fbb296114b9931b277b58013f37db7dcc5b8276bd3cd9fd；synthetic test SHA 4d602a0754059ddda294f8abb59ba55f1c94d53649e2eedd29dd74097ce07b61。
- 首轮 quality review 找到两处身份竞态；回归先失败后通过。窄范围 quality 和 spec re-review 均 PASS、没有正式 ID。定向 suite 29 passed；完整 Route2 synthetic suite 177 passed / 3.58 s。
- transient scratch service 使用准备好的 Linux Python 3.10.12 实测 InvocationID 和 mount identity；memory peak 15,835,136 B、RSS 19,562,496 B、pids 1/2、RLIMIT_AS 2,147,483,648 B。service inactive/not-found，cgroup 已移除。[Scratch receipt](../../evidence/2026-10-01-route2-live-cgroup-backend-scratch-v2.json)，SHA 9897cb6ae717f77b2b41b2c3c4b5e6dd53cef68323e656518bfcf5efd101817a；这不是 study-wide worker/service proof。
- source 冻结为 revision-20261001r，103 files / 1,562,738 B，root uid 0 / mode 0555，manifest deee33c1a187f57cec0d9f5ce44443081db48a784b6252f5eb30ec098a433fdb；[prepared evidence](../../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001r.json) SHA 1bd7dcb8e6d6127e9a60d6b849312262cb8efbcff5693b678a3b0e1803f7bf82。venv 与 Linux ABI 沿用 q；mode 0555 不是只读 bind。

### 继续执行但仍不得运行实验

1. 实现/安装受保护 pre-import trust anchor、root-only config/key、systemd unit 和外部 controller；接通 cgroup adapter 与 SupervisorOps 生命周期。
2. 同一 invocation 实时检查 WSL/VHDX 两个 8 GiB 面；同一 image 做 2→4 GiB gate、105+105 检查和 durable ledger gate。
3. 建真实 private namespace、逐 role RO rotation 和分阶段 GT 发布；旧 child/FD 关闭后才轮换；异常必须持久化撤销结果，禁止提前打开 110 GT views。
4. 对 worker 全写路径实施 OS 硬限制与逐路由预算；计入 image/backing/VHDX/journal/QPC/seal receipts 的实际 volume 和峰值。
5. 证明 supervisor/helpers/workers 共用的全 study parent cgroup、RSS 上限、worker≤2；接通 terminal close 后的 durable external wall receipt 和 service exit/cutoff/crash/missing-receipt 验收。
6. 冻结完整 source/runtime/system ABI/input/path-map/approval 身份；独立复审完整 A+B 历史协议、完整 Windows→Linux 数值等价和 matched-GT/HMAC 生命周期。
7. 负责人裁决所有 wall/RSS/worker/disk/N/M/S/B/D_A/卷外写入候选；完整 independent PASS ID 与 owner approval 仍未签发。

唯一卡状态继续 APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；准备状态 PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / NOT_EXPERIMENT_AUTHORIZED。没有项目数据、score/cache、GT view、正式 image/volume/root/ledger/lock、Stage A/B、Route3 重跑或架构方向运行。

## 2026-10-01 revision-t 进度与复审回填

- [x] 将跨 OS synthetic probe 的 HGB 迭代数从陈旧的 40 固定值改为当前 A2-004 的 `max_iter=100`；增加回归测试校验 probe fit 参数与冻结 config 一致。Windows 3.10.11 与 pinned WSL 3.10.12 均运行了该纯内存合成流程，详细 runtime/source/hash/error 见 [cross-OS revision-t evidence](../../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001t.json)。
- [x] 对当前准备快照 revision-t 做完整 manifest 复验：105/105 文件、1,572,963 B、manifest `b05a2655213ff2e9afba5943b11de99e886c8162bab195c90f2056f6edbde1f0`；pinned Linux dependency venv 11,330/11,330 文件与既有 manifest `e8ee8b0c…` 一致。
- [x] 以 Windows CPython 3.10.11 运行 13 个 no-project-data synthetic test files：**178 passed / 4.75 s**。夹具适配 `GetTickCount64()` 15.625 ms 分辨率；生产 wall/boundary 判定保持原样。
- [ ] 正式 privileged controller、完整 A+B 执行 boundary 和同一 invocation 的 image 2→4 GiB、pre-image 两卷 8 GiB gate 尚未实现/验收；revision-t 仍是只读准备快照，不是安装 controller 或真实 RO bind。
- [ ] 逐 role/phase GT release、worker/file descriptor 退出和 anomaly revoke、所有写路径的 OS 阻断/卷外峰值账本、study-wide RSS/worker hard enforcement，以及 terminal close 后持久外部 wall receipt 验收仍未通过。
- [ ] 同一 outer GT view 下的 reference/control 与 treatment candidates matched-GT additions/losses 尚未实现；历史完整 A+B protocol 与全 numeric equivalence 的独立 PASS、controller HMAC key lifecycle 均未完成。

### 独立静态复审补充

revision-r（manifest `deee33c1…`）的独立只读完整 A+B 复审为 **FAIL / NOT_APPROVAL_READY**，无正式 review ID：执行边界仍依赖 injected protocols；旧 max_iter=40 receipt 不绑定当前 Stage B；outer evaluator 缺少 control matched-GT 候选差分。新 revision-t probe 只将第一项历史证据更新为 max_iter=100 的窄 synthetic 结果，不能关闭后两项，也没有授权实验运行。

负责人已明确 host-account owner 为可信主体，且创建正式镜像前 WSL backing filesystem 与 VHDX 所在 Windows 实体卷分别至少 8 GiB。这两个决定已记录；同一次正式 invocation 中可执行的实时双层检查仍未实现。所有预算上限和外层卷/峰值解释仍待负责人审批。

### revision-u 证据绑定 P2 修复

- [x] 保留存在 scope hash 不匹配的 revision-t，不再拿它作为当前绑定；创建 revision-u，把当前 `snapshot_scope.json` 纳入新 immutable snapshot，manifest 为 `ab898c849e1e22896813bb09866919cd6ed237ceaf8854ed524aef2d3fe1344f`（105 files / 1,573,062 B）。snapshot scope hash `7aecc7db…` 与源码清单一致。
- [x] Windows 经 WSL UNC 与 Linux 均运行同一 `revision-u/source` 上的跨 OS no-data probe，分别记录实际 Stage B 模块导入路径；两端也各自通过完整 manifest 内容验证。
- [x] 13 个 Route 2 no-data synthetic test files 直接从该 UNC 快照运行：178 passed / 5.43 s。
- [ ] revision-u 的窄独立复审仍在进行；即使证据绑定 P2 关闭，也不代表完整 A+B review PASS。

revision-u 收据：[cross-OS probe](../../evidence/2026-10-01-route2-cross-os-synthetic-equivalence-revision-20261001u.json) SHA `73358db47b66d35a9eb663adf69c2d68779515a93398fc8441fad0bb428b7f7c`；[prepared runtime/snapshot](../../evidence/2026-10-01-route2-prepared-source-runtime-revision-20261001u.json) SHA `4441a4a24ea1fe01d1e3a4740ad3942ef0c86577dc595a84cda972e7dc3e525f`。完整执行入口、production resource/mount/wall lifecycle、matched-GT additions/losses、完整 A+B 数值等价、全部 budget approval 与 full independent PASS 均仍未完成。
### 当前 pooled quota 实现与 revision-u 窄复审

第 21 项 pooled 操作已定为一次 GT-free reduction：15 次 inner evaluator + 5 次 outer evaluator + 1 次 pooled reduction。源码、hard call ceilings 与 durable completion payload 均分开记录 event_evaluator=20、pooled_reduction=1；结果收据分列 evaluator_calls=20、pooled_aggregation_calls=1、pooled_gt_reads=0。pool reducer 只归并五个 outer fold 的 participant metrics；100 组五折合成直接评价对照测试通过。该定义保持 25/25/65/21 总配额，同时准确区分读取 GT 的评价与数据归并。

revision-u 的窄 source-binding 复核为 PASS（无正式 ID），确认 manifest/scope hash/Windows 与 Linux import paths，无新增 P1/P2；这不审查之后的 quota 源码改动，亦非完整 A+B PASS。新快照和对应复核仍待完成。其余 controller、mount、budget、全数值等价和 matched-GT 缺口仍按本计划待办。

## 2026-10-02 revision-b 执行记录与剩余准入门

本计划的准备快照更新为 revision-20261002b：/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002b/source，105 files / 1,657,792 B，root-owned 0555；manifest SHA-256 82f563d2cac21a5916f03908e5e7cf404fba64157238b0d28027fc79443407f0；snapshot_scope SHA-256 0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61。Windows 3.10.11 与 pinned Linux 3.10.12 均完整核验；Linux venv manifest e8ee8b0c32415913de7d560cc0a299b424567a688b3471ad0030d135aaf2241e 的 11,330 files / 348,519,927 B 本轮重验通过。

已完成的准入代码修订：全局 call-event interleave replay、frozen 105-role graph/hash binding、25 fit provenance events ↔ StageBResult ↔ durable model bytes SHA 对比，以及 Linux terminal replay 对 frozen outer IDs 和 fit provenance 的交叉核验。13 个 Route2 no-data 测试文件 Windows/Linux 各 194 passed。cross-OS 合成探针非项目数据；200 个概率有 194 个 bitwise 相同，最大绝对差 1.734723475976807e-18；owner tolerance 未批准，因此不得判全流程数值等价。当前 revision-b receipts 链接在本计划的整合修订设计文件与 review 文档中。

执行顺序继续保持：先完成只读 revision-b 审计并修复真实发现；接着确认所有原始能力 probe 和依赖 receipt hash 不变；明确报告所有未闭合 P1/P2；把唯一 A+B 条件授权申请卡补齐路径/hash/额度/审阅ID。用户授权的工作止于这次准备和申请，不包括 Stage A-only、A+B、任何 GT view 打开或 Route3/架构方向运行。

首次运行前仍要先有已安装可信 privileged controller 并通过 synthetic-only OS 验收：同镜像2→4 GiB 持久门、同 invocation 双卷8 GiB live recheck、production role/phase RO mounts 与 GT release/revoke、全部 worker write-path restrictions/卷计量、全 study RSS/worker强制、terminal close 后外部 wall receipt 对 exit/cutoff/crash/missing receipt 的验证、source/dependency/ABI/input/path-map/approval freeze。全部预算候选及 D_A/B/N/S/M 语义与外部写入峰值计费需负责人明确；再完成独立完整 A+B review PASS，最后才提交同一张具体卡给负责人决定。revision-b 窄审阅状态仍 IN_PROGRESS / review ID NOT_ISSUED；formal review 2026-09-29 FAIL 记录有效。

## 2026-10-02 revision-g 执行台账

当前 frozen source 是 `/opt/route2/snapshots/route2-candidate-overlap-v1-001/revision-20261002g/source`，105 files / 1,674,692 B；manifest SHA-256 `40c3efe8664fc0de1c74c8784644e078cb06cf1bb1db1a1e1090e23d61cf76d6`，scope SHA `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`，root-owned 0555、revision parent 0755。d/e/f snapshots 均保留；d 含意外 pycache 无效，e 无法 Windows UNC 校验，f 已 supersede。

| 执行项 | revision-g 证据/状态 |
|---|---|
| 底层准入绕过修补 | f review 找到 `AppendOnlyLedger.create` 与 `BudgetGuard.start` 可接受 duck-typed no-op approval；g 两处现要求精确 `ExperimentApproval`，且先于建路径 / OS enforcer。两项 adversarial regression tests 通过；revision-g narrow static source review 确认关闭（review ID `NOT_ISSUED`）。 |
| Route 2 合成套件 | 固定 g 快照中 13 个测试文件：Windows 203 passed / 10.81 s；WSL Linux 203 passed / 5.63 s、1 个 pytest `pythonpath` warning。禁用 cache/bytecode，双端测试前后均重验 105/105 manifest。 |
| Cross-OS probe | 只用内存合成数据；raw Windows/Linux SHA `1b7d9701689365a75ddd01d6d5a9a4801596fac1b858ecc3e7e98d6c3545a4ff` / `afd240d51d83f332759d384d3a8aa2cac66dfd79e724e6e0f75f304165bf9bbc`。194/200 probability bitwise equal、max abs `1.734723475976807e-18`；owner tolerance 未批准，结论为 PARTIAL_MATCH_ONLY。 |
| Evidence review | [prepared receipt](../../evidence/2026-10-02-route2-prepared-source-runtime-revision-20261002g.json) SHA `9c2a34758988b64d06987db4cf3710caa3afd9047b0b758fbb0b864f5b91ab67`；[aggregate receipt](../../evidence/2026-10-02-route2-cross-os-synthetic-equivalence-revision-20261002g.json) SHA `f74ab7ae43ac81c3772259f35c7afe82bb4300eb4f53dc8c9a5c4d68f4ce8346`。窄 evidence-binding review PASS、无正式 ID；静态 source review 只确认局部源码门。完整 A+B review 仍 FAIL。 |
| owner budget facts | Windows host account owner trusted；WSL backing filesystem 和 VHDX Windows 实体卷建镜前各自 ≥8,589,934,592 B，负责人已确认。其他 wall/RSS/worker/disk/formula/freeze-point/外层卷峰值预算仍未批准。 |

仍开放的任务：生产 privileged controller 与持久 A+B runner/bootstrap admission 连续性；同 image 2→4 GiB durable gate 与双卷同 invocation 实时门；正式逐 role RO mount / GT phased release-revoke / teardown；全 worker 写路径与 controller/外层真实卷峰值计费；whole-study cgroup/RSS/worker 硬限制；terminal close 后外部 wall receipt 对 exit/cutoff/crash/missing receipt 验收；source/dependencies/ABI/inputs/path-map/approval freeze；同一 outer GT additions/losses 算法已静态复核，但生产 PhaseRunner/真实执行仍待证明；完整 5×4 A+B 与 cross-OS numerical equivalence 独立 PASS；所有未批准预算与完整 A+B 审阅。正式完整 review `route2-ab-full-implementation-review-2026-09-29-FAIL-001` 继续 FAIL。

本台账不授权实验。无项目数据/GT、Stage A/B 或正式存储路径已触碰；`FROZEN_ADMISSION=None`、`NOT_EXPERIMENT_AUTHORIZED`。仅在全部 P1/P2 关闭、预算和代码身份 review PASS 且负责人另行明确批准唯一具体卡后，才可讨论首次运行。

## 2026-10-02 整合讨论后的条件验收计划（本轮只修文档）

状态依据为[既有review本轮整合后修订](../../decisions/2026-09-27-route2-design-review.md#2026-10-02-整合后修订四项核对负责人裁决草案与最小-ab-条件卡)，续接2026-09-29整合后修订及revision-g。以下是待决定后的验收顺序，不授权本轮实施、测试、scratch或实验。本轮只读指定文档/无项目数据证据并核其hash，未重新探测WSL、未打开输入/GT、未创建正式namespace。

### 当前事实与身份更正

- [x] 分别核对：准备视图已生成但仍PREPARED_UNREVIEWED；A+B未获授权且FROZEN_ADMISSION=None；Stage A/B未合法运行；没有合法路线二结果。依据g原始收据，GT views opened=0，image/volume/root/ledger/lock/path-map均未创建。
- [x] 核三份9月29日raw disk/cgroup/wall回执及Linux依赖记录的hash，均与既有review一致。2→4 GiB/ENOSPC、13-wheel准备、21项与g双端各203项合成记录只作准备证据。两个g窄复审无正式ID，完整复审FAIL不变。
- [x] 核负责人既定两项解释：宿主账号owner可信；正式建镜像前WSL backing与VHDX Windows实体卷各自独立≥8589934592 B。无需重复确认解释，正式live门仍缺。
- [x] 原始g收据中的scope是64位 `0b27dddc1c252179ff62bccc48b01f68ec72583434101909e260dcf9658f8d61`；上方g段落及旧卡误录额外f6为66位。此处更正当前口径，不改原始证据/source manifest；原卡本轮不修改，正式提交前须同步及独立复核。

### 四项裁决与代价

| 裁决 | 推荐草案 | 备选及代价 | 当前缺口 |
|---|---|---|---|
| 宿主/runner | 延续已确认可信host的WSL2 worker边界；最终卡冻结controller/launcher/key/config/observer主体。 | 若要求host本人也不可见GT/账本，迁独立受控Linux runner；重做输入/设备/依赖/observer绑定与全review。 | worker OS隔离/控制器保护仍P1。 |
| 双层空间/计费 | 研究卷2/4 GiB，image/backing/VHDX/journal/外部锚另列路径/卷/峰值cap，跨层分别报告。 | 全部加到2/4会重复计账并需改D_A/容量/公式；专用承载环境增加迁移成本。 | 控制层具体cap、归因及实时双层门未固定。 |
| RSS/workers | 先审全Linux研究进程两task及exec前每进程RLIMIT_AS≤C/2的保守法，helper串行；通常只剩一个worker槽。 | 逐进程地址额度分配更复杂；改cgroup-memory/worker子组需owner批准指标变化、控制task及投影式。 | 真实依赖可运行、完整继承/防迁出/worker写限制/GT撤销证据缺。 |
| wall/identity/pooled | 独立durable外部wall锚、完整RO闭包与持续admission；20 GT-backed evaluator+1 GT-free reduction。 | 改wall最终写入边界须批准；只读rootfs增加构建/存储成本；直接第21 evaluator增加pooled GT scope/phase审阅。 | 生产链、全5×4/数值审阅、容差及pooled负责人裁决缺。 |

### 决定后仍待完成的独立验收（均未执行）

1. **冻结政策和计费合同。** 负责人确认1200/3600/900s、60s余量在wall内、RSS公式/计费进程范围及compute workers≤2、2/4 GiB、D_A/B/N/S/M与两式、20+1及数值容差政策。控制层逐路径/实际volume/字节cap和observer RAM/tasks必须先填实，不能把8 GiB floor当控制层预算。共享VHDX不明增量需保守全额计或专用环境；清理不抵峰值。
2. **生产trust/admission贯通。** 安装受保护的launcher/config/key/unit/privileged controller与外部observer，核pre-import→sealed admission→同一持久A+B runner→phase worker→terminal的不可替换链。pins在source tree外，不能自哈希或靠exact Python type检查签发批准；owner/review issuer身份须可核。
3. **双层free和同镜像门。** 首monotonic样本后、image前live分别查WSL backing与Windows VHDX卷，绑定device/mount/path/GUID/时序；以同生产controller在独立scratch身份、假输入验证拒绝旧/缺失样本与提前扩容。模拟105 reference全过→105 treatment→区间差异→N/M/S/B/D_A门→ledger fsync→同image/loop/UUID/mount 2→4；失败停机、不换卷。正式真实输入门仅在将来单独授权后运行。
4. **全研究资源与写路径。** 父cgroup覆盖supervisor/hash/resize helper/worker，exec前核soft/hard RLIMIT_AS、initial task数、不可附加/迁出/改限额；冻结库线程和实际依赖拓扑。RLIMIT_RSS、memory.max、CPUQuota与采样不能单独证明原RSS/worker；若保守方案不适用，回到政策选择。输出、ledger/lock、模型、temp/atomic副本、/tmp、/var/tmp、/dev/shm、HOME/XDG/cache/pyc/core、IPC/stdio、继承FD/daemon socket均需系统拒绝或同研究卷映射，内存IPC也须计资源。
5. **逐role/phase实际lease链。** 非GT Stage A role只读轮换；training六字段视图；inner每outer12预测冻结后release，outer预测冻结后release；GT同FD先hash后语义读取。收据绑定namespace/mount/dev/inode、PID/start identity、scope及预测/ledger门；正常与异常都核所有child/后代/FD关闭和mount撤销，之后才下一role。umount不能代替FD teardown。HMAC key创建/仅GT child分发/销毁及同outer control/treatment additions/losses生产链须审，不增加既定调用额度。不得预开110 GT。
6. **terminal后外部wall。** 核terminal append/fsync/close→receipt fsync/close→外部deadline/exit/return-code/cgroup-empty→最终持久锚。Linuxmonotonic和WindowsQPC不混epoch，各自连续绑定boot/invocation；60s不是追加额度。最终seal写入若无计时证据仍P1，不能用更多自报文件解决；迟到/crash/missing/partial/reboot/未净退出拒绝、记录实际消耗、不续跑。
7. **完整RO身份与非候选协议。** 最终source/venv/stdlib/native-loader与动态库/入口/controller/unit/环境/import路径、A2/G1/registration/projection安全attestation、逐文件path-map及owner/review budget pins都绑定真实RO mounts与完整hash。Stage A不为hash打开混合原件/未release GT。独立审历史label/资格、16D+10D、HGB/G3、nested/threshold/180s/600s/IoU/matcher及完整25/25/65/20+1与纯合成5×4；g现有单fit probe和203项测试不能顶替。
8. **pooled和数值裁决验收。** participant五outer互斥/完整、GT分母234；计数求和、F1从总数算、MAE按未舍入误差和/匹配数合并、long-FP按总FP合并且保留空值；缺充分统计量的字段需补并重审。evaluator≤20、reduction≤1、pooled_GT_reads=0分别强制并回放。194/200位级相同仍PARTIAL_MATCH_ONLY；容差应事先冻结并核离散阈值/排序边界，不能事后用舍入一致放行。
9. **正式完整独立review和同一卡最终审批。** 输入/metadata attestation、全生产OS/trust/resource/wall/identity review及完整科学协议/数值/代数归并review均须覆盖最终hash并有正式ID，可合并完整范围审阅。同步原卡scope抄录错误、补全NOT_CREATED/NOT_FIXED字段和控制层数值后，负责人最后另行明确批准原同一张卡。若实现改变g源码，先重冻重审，不沿用g manifest批准新代码。

授权前的完整A+B review是完整生产闭包和纯合成验收，不要求先非法取得真实A+B结果。额外真实输入跨OS验证若被review要求，另列精确读取/调用/预算申请；不自动扩读或执行。未来真实资源/GT/terminal收据由已批准的唯一invocation产生，缺失即合法停机。

### 最小条件卡及终态

唯一ID `route2-candidate-overlap-v1-001`，完整105 reference→至多105严格正时长treatment，candidate scorer fit/predict=0；机制全同fit前MECHANISM_NOT_SUPPORTED，差异且全部门通过才固定5×4、25fit/25predict/65decoder/20evaluator+1reduction。精确input/source/runtime/image/volume/root/ledger/lock及当前准备hash、所有待批预算和缺失项见review的同一卡讨论表；formal path-map、控制层cap、完整review/owner ID缺失时不能进入可批准状态。

六种非COMPLETE分类保持REFERENCE_NOT_REPRODUCED、MECHANISM_NOT_SUPPORTED、INPUT_NOT_AUTHORIZED、INVALID、VERIFIER_DATA_INSUFFICIENT、INCOMPLETE_RESOURCE；仅完整合法五折及全证据有效为COMPLETE。资源/身份失败不当性能负结果、不重试续跑，不降Stage A-only。当前仍APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，FROZEN_ADMISSION=None。

本轮没有执行上述验收。Route3 v1-003合法COMPLETE、四门FAIL，不重跑；gap=0已覆盖。仅用户提供合法路线二结果后才讨论三个架构方向各自的最小验证，不自动启动任何方向。

## 2026-10-02 整合后修订：推进准入组件实现

后续“开始推进”授权实施准入准备及合成测试；没有授权真实 Stage A-only/A+B、项目输入/GT 访问或正式对象创建。原预算、计费、20+1及容差的待批状态保留。

- [x] `admission_bootstrap` 登记同进程/thread 的单次 live proof；拒绝重构 proof、PID/thread/global替换、重复消费，以及清空公开全局后的二次 bootstrap。
- [x] 新 `admitted_execution` 提供固定 A+B runner 接续，核精确绑定类型、fresh guard/ledger、共同 ledger/root、冻结路径及预算/controller/write-volume身份；真实尝试失败后不重试。
- [x] 用无项目数据的夹具验证接续和拒绝路径，追加实际第二 thread 及组合入口顺序检查。窗口内的合成测试结果见下方最终核验记录及 review。
- [ ] pre-import launcher 接入生产完整装配；真实 OS enforcer、role/phase worker 与 terminal 外部 observer贯通。
- [ ] 使用最终生产后端执行单独受限的合成 OS 验收（本轮没有创建/扩容真实 loop 镜像）。
- [ ] 重新冻结变更后的完整 source/controller/runtime身份，并完成独立完整复审与预算/协议确认，再提出同一张卡的最后单独 A+B 批准。

固定 g 快照未修改，新工作树不属于 g manifest。完整 review仍 FAIL / NOT_APPROVAL_READY；准备视图 `PREPARED_UNREVIEWED`，实际源码默认 `FROZEN_ADMISSION=None`。Route3和后续方向的原约束继续适用。

### 本轮最终核验与下一处连接

- [x] 新LinuxLoopVolumeExpander实现既有同image/loop/UUID/mount的2→4GiB syscall扩容，先核受保护seal/真实持久ledger gate，实际fsync后才修改；身份改变、活动view/worker、失效投影、部分失败均拒绝，外部durable attempt禁止跨实例重试。仅组件；真实loop命令本轮未执行。
- [x] 接续窄review发现的P1 fresh状态遗漏及P2大小写误拒均经红→绿回归修复，第二轮静态复核确认限定范围关闭，无正式ID、非完整准入PASS。
- [x] 最后15个Route2合成文件Windows3.10.11与WSL3.10.12各**323项通过**；6个变更代码/测试hash在套件前后相同，准确hash、命令边界和耗时见既有review同日组件推进修订。WSL的1个pytest6.2.5配置warning保留说明。
- [x] 一次真实Linux单进程2GiB RLIMIT_AS、数值库线程=1下的100迭代HGB合成检查完成；peak RSS149606400B。未置于生产study cgroup，不关闭完整RSS/task P1。
- [x] 扩容窄review两轮回执已回填，限定结论与失败边界见本节追加修订及原review。
- [ ] 正式镜像创建及双层live sampler、扩容receipt实际append/fsync、统一startup/lock/ledger所有权与bootstrap/launcher/runner装配仍缺。
- [ ] 安装并核控制层attempt目录；路径 `/var/lib/route2-controller/volume-expansion-attempts/route2-candidate-overlap-v1-001.attempt` 的cap/卷/费用待负责人确认，本轮未创建。

仍无新source冻结、完整生产/科学协议review、预算/20+1/容差确认或A+B批准。正式对象与GT不创建/不打开；资源失败不恢复，不转Stage A-only。

### 扩容窄复审后的追加修订

第一轮扩容静态审阅发现3P1/2P2，修复empty tombstone先持久化、attempt目录实际device分离、完整activity计时回放、实时controller cgroup绑定与FIFO非阻塞拒绝。新增7项直接OS-port mock和50项gate/cgroup回归，最终17文件Windows/WSL各**380项通过**，8文件hash在套件前后一致；准确hash、发现及修复边界见既有review最新修订。第二轮限定静态复核确认五项发现处理完毕、无新的范围内阻断，无正式ID；不能由380项测试或窄复核推断完整准入。

仍需完整105+105 ledger/产物与完整5×4合成证据；四summary-event fixture不替代它们。fsync/ioctl仍可能阻塞，需生产外部wall强制与crash隔离；目录首次同步失败不得宣称已有durable marker。下一步仍是统一startup/lock/ledger所有权、生产OS/phase/observer接线、控制层预算与完整冻结复审；不使用真实项目输入补齐授权前证据。

- [x] 两处组件各两轮独立限定静态复核已回填到原review；未签发正式review ID或实验准入PASS。
- [ ] 外层全局一次性failure ledger/quarantine，尤其首次marker同步失败后的跨崩溃隔离；完整stage ledger/产物绑定及OS外部wall。

状态不变：准备视图PREPARED_UNREVIEWED、实际FROZEN_ADMISSION=None、Stage A/B未合法运行、路线二无合法结果、完整review FAIL。剩余owner预算/计费/20+1/容差未收到新批准，不按沉默视为同意。


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


##### 2026-10-07 环境路线已选择：受控 Windows＋WSL2的实际接入与部署顺序

负责人选择保持全部原约束并提供受控Windows执行实例，继续WSL2；上一节路线待答状态结束，计费边界调整路线不再推进。全权限续行延续，实例接入信息与预算不是权限重申请。目前实例名称／endpoint／provider及实例内存、磁盘上限UNKNOWN；已请求这些信息，未收到前不创建VM、安装平台、重启或猜测付费资源。

后续顺序绑定到同一真实实例，不能把步骤文字当作完成事实：

1. 先接入、只读取得实际Windows／外层provider／账号与token、实例GUID、CPU及nested支持、所有系统与数据卷／VHDX对象的原始身份和可用额度。新实例不是旧共享Ubuntu身份；WSL2运行在VM中时须核对外层nested能力，不依据HypervisorPresent下的CIM false字段判不支持。
2. 在创建正式image之前闭合所有归属写者及native硬cap：系统卷、pagefile、registry/eventlog/temp、carrier、guest、安装／控制／compiler及外部launcher/bridge/observer／provider写入均需实际承载边界。取得guest FS及VHDX所在实际Windows实体卷各至少8GiB的同invocation原始事实；carrier仍没有第三项8GiB要求，独立增长和收尾reserve必须有真实余额。不能把共享free差、固定carrier长度或实例名称当cap。
3. 列明新实例三层actual baseline/capacity/remaining与全部准备费用。先作受预算限制的后端验收范围、失败证据保存与停止条件；20/32/34GiB、64/16MiB等原候选保持，实际对象和完整复审后再最终绑定。未绑定准备边界／预算前不编译、装载helper或启动生产组件。
4. 在可行后端上接通同一可安装runner：原生role/path-map和phase-worker、原始spawn/pidfd/wait/reap/status及UID/namespace/IPC、全部worker写路径和backing创建删除历史、逐role/phase GT grant/revoke；pre-Python/pre-spawn时钟与Windows原始QPC认证transport。现有三个native入口及StageB生产GT phase仍拒绝，不能用caller callback或现有退出子原语代替完整装配。
5. 完成首次constructor/import/dlopen之前的完整readonly解释器／stdlib／PE/ELF/native/helper身份，以及编译／ABI成本；部署terminal后独立签名close/exit join、原始cgroup清场及final durable外部墙钟。安装、失败、OOM／crash、清场和全部外部费用用实际证据验收；随后进行新版完整nested数值等价和完整独立正式复审、完整source/runtime冻结及负责人最终绑定。
6. 仅可消费A+B准入真实闭合后开启一次完整A+B；不以A-only或GT预读绕过。保留预声明早停、20 GT-backed＋第21次GT-free pooled、最终control/treatment matched-GT真实增减；结果分别报告合法COMPLETE／早停状态与质量门。当前尚未进入此步。

本机限定provider发现及官方nested依据、最新条件卡差项统一见[原review本日环境路线追加](../../decisions/2026-09-27-route2-design-review.md)。若实际实例不能满足全写入边界，提交具体对象／provider失败或不支持的证据，不称只缺管理员权限，也不凭VM替换自动PASS。

本次仅环境信息准备及原文档更新，83文件源码工作集不变；未新增／运行测试、未import项目、未启动guest/helper/production或读取GT，未创建正式image/volume/study/ledger/lock。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B均未合法运行、无合法路线二结果及完整FAIL-001保持；条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。原dirty/staged/untracked、授权提示／卡及Route3限制保留。


##### 2026-10-07 本机 E＋WSL／10GiB：部署前停止点

负责人已确认尚未创建，只用本机E盘和WSL，磁盘额度不超过10GiB，并延续全部权限至可交给执行agent。上一节等待实例来源／远程接入状态结束，本轮实际来源为localhost及既有WSL。10GiB=10737418240B按完整归属部署峰值保守处理；旧32GiB carrier／20GiB guest／34GiB实体cap具体方案已不满足新上限，不能调用旧配方创建。原control64/16MiB、数值容差、准备和外部CPU/RAM/task/wall/bytes仍须实际证据及完整复审后绑定。

恢复后只读核对原工作树、注册VHDX、C/E卷和Disk1：唯一Ubuntu22.04/WSL2仍在C，E:/Route2Dedicated与carrier不存在。未export/import/resize/move或shutdown发行版，未分区。Disk1 LargestFreeExtent只是观察，不使用该extent作为平台扩张；旧提升probe PID已被其他进程复用，不复用权限或执行lease。

独立只读复审一次，无正式ID：当前不能准入，10GiB容量UNKNOWN；不是把两个8GiB门相加为16GiB，也不是因旧方案大于10就宣布新minimal环境不可能。创建前guest baseline／FS overhead必须与8GiB free同处真实capacity内；carrier和actual Windows层分别核baseline＋future＋cleanup，内外层不得重复相加。现有共享guest/VHDX数据不是新target的identity或下界。

当前明确的部署前停止点：全部Windows归属写者没有native hard cap。固定carrier或guest容量只能覆盖其内部；NTFS SID quota不计全部metadata且按owner，不能覆盖跨卷／不同owner/system的registry、eventlog、temp、pagefile及WSL／外部执行器效果。完整生产role/path-map、worker原始spawn及隔离／全history／GT撤销、QPC transport、readonly加载闭包、独立最终退出验收也仍未安装。原源码各拒绝入口保留，不用caller callback/schema/HMAC/数字PID制造producer。

因此当前本机配置合法部署preflight=NO-GO（ENVIRONMENT＋IMPLEMENTATION，容量UNKNOWN），维持部署前状态；具体事实、官方来源、三项已核假设及完整条件卡差项见[原review本日10GiB追加](../../decisions/2026-09-27-route2-design-review.md)。取得实际全边界及≤10GiB baseline/峰值/收尾与准备预算之后，才可继续上一节原完整安装／双时钟／readonly／failure-exit／数值／正式复审序列。执行agent当前不能开启A-only或A+B；不向它签发虚假可执行准入。

本轮源码83文件／2096023B保持原mapping；55生产Python仅AST，C/H和历史测试仅hash，无新增／运行测试、项目import、WSL/helper/production或GT读取、正式image/volume/study/ledger/lock创建。原11项staged及dirty/untracked保留，未commit/reset/delete。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001、Stage A/B未合法运行、无合法路线二结果和APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；原授权提示／卡及Route3限制不改。

为当前本机资源形成了一个待负责人决定的具体差异（原review同节末，尚未采用）：将10GiB native cap限于专用载体及其内全部准备／控制／研究文件，卷外Windows系统效果单列计量／预算／拒绝／复审；明确放弃其per-study native硬cap及全部Windows物理增量≤10GiB的native保证。不是重复申请管理员或继续工作权限，而是变更原已确认的资源合同。原两个8GiB／study2→4GiB、时间／资源方法及完整科学／GT／review门不变。未获明确答复时不进行依赖此变更的部署，保持当前NO-GO和冻结None。


##### 2026-10-07 三项证明的执行顺序说明

三项证据及明确验收口径统一追加[原review本日三项证明说明](../../decisions/2026-09-27-route2-design-review.md)。先证明全宿主归属写入有真实可部署native机制、绑定准备预算；再在受限新target作容量/baseline/保留峰值/cleanup实测，同时补齐固定path-map/phase-worker/QPC完整源码；随后同安装版本的实际OS/失败/退出、数值等价及完整独立正式复审、冻结和最终绑定全部闭合后才开启一次A+B。AST/hash、删除拒绝raise、几个成功轨迹或时点free不足代证。容量按同image最大4GiB规划，Stage B实数投影仅来自后续合法Stage A；不预运行Stage A或GT。此节仅答复证明方法，不新增/运行测试或helper/production、创建对象或改变原合同与准入状态。

##### 2026-10-07 按顺序执行的第一项实际止点

已先作本机实际原生机制及系统backing只读盘点，并一次限定独立复审；原始事实/API定义及本轮一次完整A+B条件卡见[原review本日第一项核查](../../decisions/2026-09-27-route2-design-review.md)。本地本日／UTC 2026-10-08：computecore.dll/vmcompute/hcsdiag及wcifs/bindflt确实存在，不等于已配置受限compute system。WSLService/vmcompute为LocalSystem；系统hive/evtx在C、pagefile在D、TEMP涉及C/E，覆盖集合须包含D和SYSTEM作者。quota查询0行、驱动Running、时点free和共享pagefile存量不能证明per-study cap/成本。

新只读RunAs被UAC返回用户取消、exit2，fltmc实例清单UNKNOWN；旧提升事实不作新token/lease。独立核查未关闭第一项，无正式ID：未取得全部归属Windows physical allocated bytes≤10737418240B的actual producer，不普遍否证Windows或10GiB。Job IoWriteBytesLimit为通知超限后仍能写，rate是速率；FSRM目录usage包含metadata，但当前Home没有已取得受支持provider；HCS/wcifs/BindLink局部边界无宿主外部系统作者全cap证据。全准备/控制/外部费用继续UNKNOWN_NOT_ZERO。

执行位置：第一项未关闭；第二项仅定位既有固定producer/部署依赖，没有新增生产实现，原path-map/phase-worker/nested/QPC等拒绝保持；第三项没有新target实装或baseline/容量/保留峰值/cleanup实测。当前合法部署preflight仍NO-GO（ENVIRONMENT＋IMPLEMENTATION，容量UNKNOWN）。原硬边界及准备预算闭合前，不创建正式对象、编译装载helper或启动生产；现有计算/退出消费和快照不能代原始spawn及全创建删除history，不移除raise后返回callback。

carrier-only合同差异未采用；顺序指令不改变全部宿主hard cap。两个8GiB、carrier无第三门但独立reserve、同image最大4GiB和D_A严格上界V2及原科学/隔离门保持；不能派执行agent启动A-only/A+B。83文件hash未变，原限定复核继承而非完整freeze；仅本三文档追加，无新增/运行测试、项目import、WSL/helper/production/Stage/GT或正式对象操作，原dirty/staged/untracked、11项staged及授权卡/提示保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、无合法A/B或Route2结果、完整FAIL-001和APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED维持；续行意图已授权，可消费准入未绑定。Route3及后续架构限制不变。


##### 2026-10-08 本机三项建议已采用：先资源估算，再固定原生child源实现

负责人采用三项建议并开始执行；10GiB改为估计而非hard cap，主要新增资源E，非E合计512MiB含停止清理，任务总RAM16GiB/VRAM8GiB。旧全host≤10GiB native边界NO-GO只保留历史。E专用carrier内完整guest/prep/control/study/失败/cleanup仍须真实原生限额；卷外Windows系统副作用单独计量、预算、超额拒绝和review，不声称已获per-study native cap。

执行顺序现为：
1. 只读资源调查及有条件预算核查已完成。prepared inputs2644303938B、登记unique cache240384603B、scores172155149B，加历史venv/wheels与原source，已知非study子集3.247270GiB；+最大同study4为7.247270GiB，非完整baseline/peak。官方UbuntuWSL压缩archive341130963B及562包只metadata，限定流统计未完整，未提取/安装。真实target和actual容量仍UNKNOWN。
2. 先实施可独立审阅的固定原生child生命周期source：新增linux_child_launch.py、phase_worker_entry.py、native/route2_phase_spawn.c/.h，必要衔接linux_child_exit.py。clone3直接取得原始pidfd、native setup后固定exec、readonly整个child FS与FD白名单/有界IPC、原始wait/reap/status和一次失败清场；不新增通用callback authority。父唯一backing作者、固定role/path-map/broker grant-revoke与installation事实缺时仍拒绝。现阶段仅source/AST/hash及独立静态复审，不新增/运行测试或编译/装载helper。
3. 组件静态复审后，将具体完整准备边界与预算供负责人最终绑定；之后才在受真正边界约束的新E对象取得无GT安装/设施验收事实。完整runner、runtime/加载闭包、双时钟、terminal后签名join/原cgroup清场/final durable外墙、完整等价及正式review/seal未闭合前，不派execution agent到Stage/A-only。

准备提案（尚未最终绑定/部署）：guest nominal20GiB、usable≥19、baseline ceiling8、future6、cleanup1；carrier nominal24、usable≥23、actual baseline≤22，future及cleanup各128MiB。carrier baseline含inner VHDX完整实际AllocationSize/header和所有Winreadonly/control/FS成本，不能仅用nominal20；E新增预留30GiB=carrier nominal24+载体外6GiB，规划约28–30不是实测区间。计整carrier后不在E物理层重复加内部guest/study。非E候选active384MiB+停止清理128MiB=512；真实计量/异步和提前停止producer未闭合。

准备候选RAM4GiB/tasks4/CPU200%/1800秒；显式observer/helper/launcher/bridge合计候选RAM512MiB/tasks4/CPU100%/6000秒覆盖prep1800+study3600+外部观察600，不改变study1200/3600/900含60秒。8.5GiB仅已列process-budget和，不能充whole-task RAM；VM/kernel/service/IPC/cache/Windows开销仍UNKNOWN_NOT_ZERO。原C≤4GiB/AS=C/2/swap0/CPU200%/TasksMax2含controller保持，VRAM预计新增0需真实拒绝dxg。C:/Users/Fancy/.wslconfig不存在未改；任何global设置须列明新文件内容及旧Ubuntu影响，不能替代per-study cgroup/native边界或说全VM/pagefile免费。

限定独立预算核查在上述scope更正后未发现硬算术矛盾，仅有条件准备预算无正式review ID。保留真实guest承载FS与VHDX所在Windows实体卷的同invocation各8GiB门；carrier无第三门但需增长/cleanupreserve。控制64/16MiB、数值容差及新容量/全费用仍候选，不以旧capacity_*全host scope直接解析新计划。

四项状态保持：PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B均未合法运行、无Route2结果；完整route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL，完整条件卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED。继续权限和完整A+B意图已有，不重复申请；可消费准入尚缺。原授权卡/提示不改，不新交接包，保留dirty/staged/untracked，无提交/reset/delete/无关覆盖/正式对象/GT或Stage启动。Route3及后续架构限制不变。


##### 2026-10-08 执行准备容量绑定与唯一获准全局配置

已收到负责人两项明确选择，采用30GiB E准备预留（24 carrier/20 guest/外部6，actual guest baseline≤8）及非E512MiB；采用全局`.wslconfig`的memory8GB/swap0/processors2/guiApplicationsfalse。按不存在检查及CreateNew拒绝覆盖，唯一新建C:/Users/Fancy/.wslconfig，65B，SHA256 a563358aecf354fe25f69fd9778d8b4342b0ae5c8df1c580a1d4263a886643e5；held-file native AllocationSize72/EOF65并非全非E增长。未启动或shutdown WSL、未改既有发行版数据，实际配置应用待验。准备容量绑定已完成，不重复询问；三层actual容量/完整费用、总RAM/VRAM及提前stop链依旧待实际生产者，原study限额保持。

child新增源组件独立规范复审的NPROC零限P2已修复；修订后限定静态规范无剩余P1/P2，独立质量复审继续，无正式ID或完整PASS。库未编译/链接/装载/调用，固定path-map、phase-runner、nested/QPC门仍拒绝。当前源码也没有fresh Windows noGT prep部署调用链；preimport launcher和正式2GiB image creator不能代替。下一步须先完成真实受限prep owner/计量stop与对象安装，再取得新target事实；本轮尚无准备/正式对象、Stage或GT运行。完整FAIL、FROZEN_ADMISSION=None及卡阻断保持。


##### 2026-10-08 后续独立组件：Windows准备Job/进程原生生命周期源码

准备容量和全局配置已获绑定，源码核查确认没有Windows fresh导入部署producer。下一独立源码组件限定新windows_preparation_job.py：真实CreateJobObject、配置/读回Job限额、原始QPC child-birth区间、CreateProcessW挂起且以job-list原子加入、原始process/thread handles、成员资格核对后resume、原始deadline wait/exit、失败terminate/一次关闭及primary/secondary保存。CPU/commit/task限额只约束Job内部进程组；不把commit称whole-task physical RAM，不把杀wsl.exe称WSLService/vmcompute/VM已停。

此组件是private native kernel生命周期，不是完整安装器或准入接口。固定readonly worker/PE依赖及原始bootstrap loader尚不存在，顶层调用在出生前拒绝；不得用caller path/argv/callback/布尔/schema/hash来制造安装权限。module import前的完整Windows interpreter/PE/native加载边界须由原始bootstrap先证明，lazy WinDLL不提供更早constructor证明。当前只实现实际底层OS调用及所有权/失败路径，不执行API或导入module；没有创建Job/进程/VHDX或运行helper。

E carrier/固定guest的真实创建和AllocationSize/history、非E所有作者/在途＋停止清理上界、VM配置应用/外部服务资源与总RAM/VRAM、完整prep部署装配依旧必须提供实际producer。准备scope不消费正式study ledger/lock或FROZEN_ADMISSION。实现后先独立规范、再独立质量静态复审；既有dirty/staged/untracked及其他源文件不动，不新增/运行测试、编译/装载或启动WSL/Stage。

##### 2026-10-08 接续实现：固定 mount helper 适配器（Windows Job复审后执行）

复核当前真实代码：linux_gt_history.py SHA256 5256f4fc0fc9081e162d31e07047575d3650ebba681cad9504aa2c2cc8673883；_libc仍直接从glibc取得open_tree/mount_setattr/move_mount/umount2，未接选定的Ubuntu22.04/glibc2.35 40-byte helper。此处不是新增环境缺口。下一源码实施范围仅替换这个固定loader及其四处内部调用，必要增加原始broker owner的私有helper持有字段；不新建模块，不改C/H、科学操作或GT/journal失败保存方法。

固定装配设计：仅从原始guard/broker/startup/controller取得真实owner和当前完整installation/write-boundary门；该门必须在此helper的任何CDLL/describe调用前通过，当前仍拒绝，不能以hash/ELF inventory/ABI数值或caller object返回成功替代。bootstrap仍须在整个project/ctypes import之前证明完整readonly解释器/stdlib/native闭包，此局部loader不补造早期constructor证据。固定runtime相对路径lib/route2/mount_helper.so，必须是完整冻结runtime manifest的唯一精确成员，读取保持既有readonly/原始FD/有界字节与绝对deadline，ELF inventory只作拒绝不支持格式的后置检查。限定依赖libc.so.6、禁止额外RPATH/RUNPATH并不代实际依赖提供者身份。

原始deadline取controller原始start＋Stage A/total固定额度及60秒stop margin，初次helper加载额外最多10秒且计入原额度，不重新起算整study。首次加载后native describe_v1返回实际40-byte ABI，四个namespaced exports采用原_MountAttr指针及固定LP64签名；errno原样留给既有_call的started/finished记录和失败保存。不猜syscall号，不用直接glibc/shell/legacy fallback。实际库由原始broker生命周期持有，失败不盲目重新dlopen/发起mount，不签发receipt或完整准入。

实现完成后需独立规范及独立质量静态复审，源码改变意味着该loader/owner/四处调用不继承旧hash复核；其余未变方法按实际hash/源码核对继承。仅AST/hash/源码读取，不新增或运行测试，不import项目，不编译/链接/装载/describe/调用helper或启动WSL/Stage/GT；actual部署/原始PE/ELF加载边界、全部费用/冻结与完整正式review继续UNKNOWN，FROZEN_ADMISSION=None及完整FAIL/卡阻断保持。

##### 2026-10-08 已实施组件收尾与下一真实装配依赖（引用原完整卡）

原生child四个新增文件及必要linux_child_exit衔接、Windows Job源组件、固定mount helper适配器已完成独立规范→独立质量静态复审，各最终限定范围无剩余P1/P2，没有正式ID/准入PASS。最终hash/修复及七文件scope详见原review“2026-10-08生产源组件收尾”，同节更新一次完整14项A+B卡；原授权申请卡未改。前三项是真实OS调用和所有权/失败源码，不是安装事实。

本计划前节“helper额外最多10秒”更正为合作式检查窗口：无法中断同步dlopen/constructor/describe；继续使用原armed绝对1200/3600 deadline及60秒stop margin，未新增kernel timer。当前installation/write-boundary门在helper自身CDLL/describe之前仍拒绝；完整解释器/stdlib/project/PE/ELF/native/transitive actual readonly证明须在整个project/ctypes import之前取得。C/H全部未编译/链接/装载/调用，无真实ABI/seccomp/runtime证据。Windows Job4GiB COMMIT/4active PROCESSES/两affinity bit不证明4task或wholeRAM，其60/70秒不是原始pre-Python epoch、准备1800或study3600，fixed prep-worker不存在仍拒绝。

下一完整生产装配的顺序须解决既有依赖：production_runner._load_native_path_map/_load_native_phase_runner/_require_native_nested_producers在guard.start之前，StageB.preflight亦早于原startup；GT broker需要guard.start→phase/terminal注册→原始QPC双记录握手后seq2安装。先实现实际readonly non-GT metadata与固定role/path-map原始producer，再在握手之后安装唯一broker/role publisher；不得早装GT，不以callback/hash/schema替代。真实PhaseRunner须通过原broker唯一release，再绑定只含当前scope GT及outer-only历史match投影的phase-only root，经原始spawn/pidfd/wait/status/reap后revoke；原StageB production分支仍拒绝legacy二次release。父唯一作者提供root/backing完整创建/发布/删除/失败历史，child只读seccomp/namespace不代历史。原始WindowsQPC认证transport、pre-Python clock和terminal后签名close/exit/raw cgroup/durable外墙钟同样待实际接线。

容量已OWNER_BOUND：E新增30GiB无GT准备预留（24GiB carrier含20GiB guest，外E6GiB；actual guest baseline≤8GiB），nonE新增512MiB含停止/清理，whole-taskRAM16GiB/VRAM8GiB；不重复申请。下一部署前须有真实creator/format/import/注册/native上限/三层baseline/余额、完整readonly worker/runtime及非E所有writer/inflight/advance-stop/VM外部退出生产者；控制64/16MiB、准备4GiB/4tasks/200%/1800秒、外部512MiB/4tasks/100%/6000秒、数值容差及完整费用继续实际复审/最终绑定。旧capacity_*20/32/34全host scope不能直接签这套新预算。Windows全局.wslconfig已创建，未启动WSL或将存在当设置已应用。

只作58生产Python AST、88文件hash/原prefix/index/授权文件核对；工作集mapping740afc4263efa095f5e510ba799fe1b608b3b7e9c90f4fa663a584d6a668ff3a非冻结。E:/Route2Dedicated仍不存在，当前非提升、仅原Ubuntu22.04 Stopped。未测试/项目import/helper编译装载/VM/生产/GT/Stage执行，未创建正式对象，全部既有工作保留无提交/reset/delete。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001、StageA/B未合法运行/无合法结果及完整卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持；授权意图已给而可消费准入未形成。Route3 v1-003 COMPLETE/四门FAIL及后续架构约束保持。


### 2026-10-08 固定 nested 装配：规模核查与下一源码实施顺序

本次仅源码和静态准备，未运行测试、项目模块、helper、WSL worker 或 Stage；准备视图 PREPARED_UNREVIEWED、FROZEN_ADMISSION=None，完整复审 route2-ab-full-implementation-review-2026-09-29-FAIL-001 / FAIL 保持。沿用负责人继续实施授权与已绑定 E30GiB / nonE512MiB / RAM16GiB / VRAM8GiB；不重复申请既有决定。

独立只读装配审计按真实 role-input-registry 元数据确认：105 roles 共19,159 cache files，每role119–250；加5项输入metadata及2项reference别名，一遍19,894项文件发布，Stage A三遍至少59,682挂载。逐文件复用GT syscall历史会超过65,536 private facts及8,192 issued mount IDs上界；不能用提高上界掩盖wall、fsync和控制空间费用。当前目录方案的约315次Stage A、130次Stage B租约发布是源码推导次数，不是实测成本。

明确提出需独立复审并刷新冻结身份的生产布局修订：每次只发布一个root-owned readonly role目录，目录仅包含该role已登记opaque aliases和批准的 __study__ 非GT元数据；逐文件logical path/hash/role/phase不变。准备installer可在同一不可变backing内对非GT重复字节作hardlink，须提供实际创建/删除/去重来源历史及没有可写别名的原生证据。生产目录布局须有新的manifest/receipt形式，一个实际目录mount ID与逐文件held FD/inode/hash身份；不沿用v1逐文件独立mount ID声明，不用布尔开关跳过其约束。GT及历史最终match投影保持分开的短寿命scoped file mounts，role目录不得包含它们。旧generic per-file reader可保留。此项为待实现和复审的明确修订，并未证明已安装或放行。

实施顺序：
1. 先补可独立闭合的固定phase-input原生publisher：仅 /run/route2-phase-source/inputs/gt-view.jsonl 与 outer-only /run/route2-phase-source/inputs/control-final-matches.jsonl；必须绑定唯一实际GT broker当前grant、原始guard/startup/controller/PID/thread及冻结historical登记，复用原始已加载helper和真实open_tree/mount_setattr/move_mount，不创建backing。保留所有descriptor/issuance/实际mount身份和durable历史；逐项原生unpublication后才撤销broker的GT alias，禁止每项调用带全局absence检查的_revoke_mount。失败保留primary和close/unmount/history secondary，poison后只允许原始cleanup。quiescence和complete-history须拒绝未关闭publisher/FD/namespace。补入既有outer历史phase的精确translation allowlist，不允许混合GT/nonGT或任意resolver。其闭合不单独撤去总生产拒绝。
2. 再实现固定nested-owner早期metadata构造及目录role publisher：早期loader只认证原_ASSEMBLIES/live bootstrap/installed metadata，不调用尚无StartupBinding的controller._state；真实早期installation gate必须取实际观察，不以unit_observation=None或manifest/hash当成功证据。guard.start → 原始QPC双记录握手 → seq2 GT broker注册 → attach唯一publisher，保持单writer。
3. 扩展现有private child原始outcome持有者，保留实际birth/READY/exit；最终permit前由原始parent读取真实kernel namespace/root clone/input身份，不能由child READY布尔字段代替。原始绝对时限内stop/pidfd wait/reap/close后unpublish两项phase inputs、broker.revoke一次，Stage B跳过legacy release/revoke重复作者，保留全部科学结果验收。
4. 接续pre-Python clock/QPC transport、完整实际readonly安装/依赖/constructor边界、terminal close/exit/cgroup/外部墙钟和实体部署/计量/预算。实际installer创建历史、WSL服务及非E异步增长上界、完整现版数值等价/正式独立复审仍缺；缺事实保持UNKNOWN/拒绝。

每项依原实施工作流采用fresh implementer → 独立SPEC → 独立QUALITY；不执行测试或提交，不把限定静态结果签成完整review ID。当前原授权申请卡与prompt保持不改。

### 2026-10-08 固定生产元数据 v2 的先行容量修订

只读独立容量审计确认既有生产 loader 无法容纳真实元数据：原 role-input-registry 为16,457,999B/hash 5d5f1f59d58a9be265db9467261cf16c4d54bc43e87a2dd33c3b94723191edd3，超过8MiB单文件界限；其base64为21,944,000B，已超过16MiB envelope。仅19,894项非GT role/reference映射的内存内canonical下界为9,131,857B/hash ee2201f4f244e400de4c85c619a33a8b2aee40144668d6fd837a3d5101a8b01b，超过8MiB path-map界限；两者base64合计34,119,812B，还不含其他条目。该map只是下界，未创建文件、未签实际完整map。原role scanner事件1,006,917、语义节点317,354，原同一262,144界限均拒绝；runner另有1,048,576 dataclass节点与16MiB scalar界限，本次未证明其另有失败。

在目录publisher之前实施可独立闭合的真实文件loader：route2_production_ab_metadata_v2与独立HMAC domain，≤1MiB canonical envelope保留全部原bootstrap binding/approval/readiness/limits/config；四个原base64字段替换为精确固定basename token。实际路径仅由loader派生为 /etc/route2/{STUDY_ID}-metadata/ 下的 role-input-registry.json、reference-registry.json、control-final-match-registry.json、path-map.json；拒绝caller路径/resolver/factory。以原_MetadataReads held-nofollow FD、KCMP_FILE、ancestor/frame、actual native private readonly mount核查读取root-owned单link/mode0400文件，raw bytes先绑定原FrozenAdmission hash，再解码。保持原source/config/start重新验证、一次加载与失败消费bootstrap；所有primary和close/consume secondary必须保留。不新增授权issuer，不读GT payload，不调用controller/helper。v1可保留其原内联合同；v2不能伪装为v1扩容。

v2 role/map初始候选解析界限各16MiB，scanner/semantic分别1,048,576/524,288、depth32；保留精确类型、bounded numbers、有限float、canonical UTF8和duplicate rejection。以64KiB有限扫描块与每1,024语义节点合作式deadline检查推进，单文件一次json.loads，保留canonical与dataclass投影相等；后续原始安装对象的完整校验可复用私有已验证map解析结果，不把缓存当mount authority。原10秒仅合作式loader窗口，json.loads/序列化区间仍需要原实际kernel deadline；全量解码RSS和运行时间未测，不能声称可用。48MiB physical-read总界限继续保留并拒绝超额；已知25,652,435B仅roles/references/role-map下界小计，不是完整总量。完整startup另计历史control registry、GT-view-registry/GT-role-scopes、config/seal/key/source/runtime元数据、read buffers、strings/containers/dataclasses/canonical serialization与全部控制/准备成本；GT原4MiB metadata/64MiB payload界限不改。

本项需要独立SPEC→QUALITY及后续完整冻结复审；当前完整installation/native clock/QPC/readonly/runner/deployment/budget门继续拒绝，不能由v2 token/HMAC/hash使其通过。目录path-map v2、真正early owner、原始child成功outcome/pre-permit内核观察与唯一GT release/revoke仍依次实施。nonE512MiB“超额前停止”沿用原约束；负责人尚未明确改变该约束，源码可独立继续，实际部署不据继续消息放行。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001以及APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

### 2026-10-08 原始时钟生产顺序的限定独立审计

独立只读源码审计定位既有依赖，未改源码或执行目标组件：windows_wall.py:176在私有_INVOCATIONS保存实际QPC/PID/thread/nonce/held identity，但没有与其接线的生产CreateProcess/WSL启动调用者；Python preimport launcher:724的首采样晚于Python初始化。linux_start_clock.py:300及live校验强制systemd_exec_main及ExecMainStartTimestampMonotonic*1000相等，而systemd v249上游execute.c:4357 fork之后在:4398才exec_status_start；上游事实不能充当专用Ubuntu patch身份。linux_native_close_handoff.py:353的完整signed launch依赖原seq2 durable journal，不能反向作为pre-bootstrap时钟/QPC来源。原origin拒绝门继续有效，不以HMAC成功绕过。

可行的待实施原生事务须有固定Linux supervisor位于study cgroup之外：已授权准备VM就绪后，原Windows QPC owner开始真实study epoch，在实际study bridge CreateProcess之前武装1200/3600外部deadline；通过实际拥有的bridge传递protected Hello/challenge。Linux supervisor在实际StartTransientUnit请求之前采集真实CLOCK_MONOTONIC t0，仅读一次MemAvailable M0，派生C=min(4GiB,floor(3*M0/5))/AS=floor(C/2)，在启动unit之前武装独立timerfd绝对deadline。固定C unit entry在Python之前暂停，supervisor从实际manager/proc获得InvocationID/MainPID/process start/boot/timeNS/cgroup/native limits，实际受限control backing安装并封存本次context/原始start描述符后才放行；C entry exec系统Python，再exec冻结runtime Python，保持同一PID/进程出生/unit/invocation。绝不预先假造未来manager InvocationID，也不通过减去host elapsed time合成较早Linux epoch。seq2完整signed launch/QPC handshake仍为后置独立步骤。

POSIX timer_t不跨fork/exec保存；timerfd的FD可保留，但必须有独立reader和真实原unit/cgroup终止owner。外部supervisor保留reader和kill ownership，1200/3600原额度及60秒收尾边界不改；Python后置timer如继续使用，只能武装同一t0的原绝对deadline，不能声称跨exec或重新起算。第一RAM样本迁移需要新start record/私有provenance和消费者源码复审：当前prepare_volume:217在StartupBinding后采样，后续须从真实原生registry取得M0，state.available_ram/envelope/ResourceSnapshot均携带同一M0；只重核原生出处和实际kernel上限，不以变化后的MemAvailable相等或第二次C计算代替。当前公式不变，但采样来源/协议不能静默替换。

下一具体原生源码候选为固定prebirth transaction＋same-PID entry＋wire header，包含capture/first RAM/timerfd/实际manager launch/真实identity/sealed FD transfer；依赖实际readonly supervisor/entry/libc/libsystemd闭包、受保护manager socket、真实cgroup kill支持、control tombstone/backing硬限、完整计费与Windows host kill/bridge-loss producer。当前没有这些实际对象；native transaction、v3 consumer、preimport、admission、controller、service argv及Windows transport尚未实现或冻结。不以clock schema或入口占位当生产完成。保持full FAIL-001 / FROZEN_ADMISSION=None，非E512MiB提前停止与实际部署准备仍待真实边界或负责人明确改变验收口径。

原始证据：[systemd v249执行源](https://github.com/systemd/systemd/blob/v249/src/core/execute.c#L4357)、[Linux timer生命周期](https://man7.org/linux/man-pages/man2/timer_create.2.html)、[timerfd语义](https://man7.org/linux/man-pages/man2/timerfd_create.2.html)、[资源限额继承](https://man7.org/linux/man-pages/man2/setrlimit.2.html)。这里只证明设计依赖和上游规则，不证明已安装目标行为。

### 2026-10-09 protected metadata实体别名修补与phase-child下一实施范围

固定metadata v2独立SPEC发现真实实体别名P2：词法路径不同、private readonly file bind与nlink=1并不能证明实体不同；任意32–4096B key可合法JSON，不能靠不同schema排除key与小registry同一inode。已在原_MetadataReads._hold加入真实held FD/anchor fstat frame与KCMP重核，再比较REGULAR的(dev,ino)，读取新payload前拒绝别名；新FD仍归原scope一次清理，DIR祖先不比较，独立mount仍允许。该规则也堵住v1 protected regular文件原漏拒绝拓扑；v1 schema/domain/parser/caps/API保留，不能笼统称全部旧行为未变。最终66441B／1236行，SHA256 5091f93c73d83d1a89d3e2227480c81f2a83e2695d9270b594e494dad27f7a0a；独立SPEC无剩余限定P1/P2，独立QUALITY尚未闭合，不签正式ID或完整PASS。

沿原固定装配顺序，下一可独立实现的生产组件为原始phase child的permit前父进程实际kernel观察与成功outcome保留。当前linux_child_launch.py读取READY后直接写permit，成功返回仅科学result，出生／READY／wait-reap原始记录会丢失。范围限定该文件、必要新private linux_phase_child_observation.py及linux_phase_publication.py的原始active batch/history衔接；C/H、科学算法、通用v1 path-map及三个完整生产拒绝入口不动。

实际生产者必须先绑定同一原始guard/startup/GT owner、当前唯一真实publisher batch/grant/canonical scope/release及由原armed绝对deadline派生的stop/cleanup。父进程从其真实held pidfd与/proc获取waitid WNOWAIT活性、process start/PPid、UID/GID/Groups/Threads、namespace nsfs原始身份、cgroup成员与实际硬上限、root clone及仅当前两个fixed input mount的device/inode/frame/mount身份；只在该实际观察全部成功且已写入原唯一durable历史后发permit。不得用READY、caller expected path/hash/observation/callback制造事实。跨UID/nondumpable的/proc读取必须实际成功；缺CAP_SYS_PTRACE、LSM拒绝或任何不可测事实直接拒绝并原pidfd失败清理，不放宽child身份或假定root权限足够。

私有一次消费outcome须绑定原publisher/batch与owner PID/thread，保留出生descriptor数值快照、原READY字节、实际kernel采样及原wait/reap/status、科学result；对象或公开数据本身不是完整sandbox/exit准入。仅原privately registered owner可取回，成功历史失败同样poison原owner并保留primary/secondary，失败不发permit或重新出生。读取scope只为合作式采样界限，不能重新起算study时钟；原始deadline/60秒收尾仍计原额度。完整phase-root所有backing创建/删除、preconstructor runtime闭包、directory role/map、early nonGT metadata、唯一完整runner和实际部署仍另有缺失，组件闭合不代这些事实。

本次仍只源码/AST/hash及独立静态SPEC→QUALITY，不新增或运行测试、项目import、native编译/链接/装载/调用、WSL/GT payload/生产/Stage或正式对象。原nonE512MiB超额前停止合同未收到明确修改；源码续行不消费部署权限。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001及完整卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

### 2026-10-09 本轮P2修复及限定复审收尾（下一child范围尚未实施）

已优先完成用户要求的metadata问题修复。独立QUALITY发现joint48MiB先超读后拒绝和temporary close入口primary降级，随后freshSPEC发现JSON/serialization报告或_after_blocking入口同类降级；连同此前实体regular别名共四项，本次均已实际修补。三个os.read/pread均在调用前按actual joint remaining裁剪，EOF/proc亦计，返回len先计账；proc原4MiB/file/16MiB累计保留。原raw primary与新secondary先inline留共享预留slots再进任何report/check/cleanup helper，剩余FD只once消费，successfulcleanup和共享failurebuffer健康后才private installation。Pure foreign无新authority，v1原schema/domain/parser/caps/API保留，protected regular旧漏拒绝别名已强化。

Final production_metadata.py 88909B/1693行/SHA15dc4b1c91b48aafbfb53645de8bde89a6298dcb1d35e4e0e69ad4e13ad61ea1；fresh独立SPEC→QUALITY均无剩余限定P1/P2，AST通过；json.loads唯一351行、native读取1045/1236/1246。尚无实际耗时/RAM/完整map/安装/native/故障runtime证据，无正式ID/fullPASS。phase publisher及三个必要owner/closure hooks的最终限定两审亦已干净，精确hash/范围及本次唯一完整14项条件卡见原review2026-10-09整合后续。

原序列继续依赖early fixed nonGT metadata/目录role-map，以及guard.start→原始QPC握手→seq2唯一broker/publisher，再原生phase-worker/scoped撤销。前节child kernel观察/outcome只是下一待实施源范围；本次未创建linux_phase_child_observation.py或移除三个native runner/QPC拒绝入口。prebirth native transaction/单次M0/v3消费者、实际Windows原始QPC/host kill、完整加载闭包、terminal签名退出/真实实体部署/全费用和提前stop、现版完整等价/正式review/冻结仍缺。

准备E30GiB等绑定保持，nonE512MiB提前停止的合同未改变；actual target不存在、自动pagefile和所有系统/在途费用仍UNKNOWN。准备视图PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、Stage A/B未合法运行/Route2无合法结果、fullFAIL-001及卡APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。源码89文件mapping06622d75994ea649c61e9462410f1bad2cb2563a53ec6034f1bbb6c8db430ac2不代source/runtime冻结；59生产AST及26测试仅hash，未运行tests/import/native/WSL/GT/production/Stage/正式对象，无commit/reset/delete，原授权卡/提示/index及全部dirty/staged/untracked保留。

### 2026-10-09 phase-child真实IPC检查的必要装配依赖

沿最新负责人指令继续补齐到合法启动，不放宽既有实验准入或预算。当前phase-child限定源范围新增linux_enforcement.py两处必要装配：原parent RestrictAddressFamilies=AF_UNIX会阻止真实NETLINK_SOCK_DIAG，故仅parent扩为AF_UNIX AF_NETLINK；旧worker service仍精确覆盖为AF_UNIX，ProcSubset=pid及其他限制不变，C native child seccomp拒绝socket syscall不变，PrivateNetwork及AF_INET/INET6拒绝不变。此为真实parent内核IPC peer查询的系统调用依赖，不是新增可授权布尔字段，不证明unit实际应用。C/H不扩ABI，预算和科学算法不变；完整installation及所有生产入口继续拒绝。

observer拟从实际held parent UNIX socket cookie及内核targeted unix_diag PEER属性，对照子进程FD3的真实socket inode；不得使用socketpair创建时SO_PEERCRED冒充child peer。Linux v5.15 primary UAPI unix_diag_req/message/UDIAG_SHOW_PEER、diag.c按实际netns和cookie查找、nsfs ioctl类型以及fdinfo实际flags已经Context7/primary源码核对，仍不是本机专用WSL kernel身份或功能实证。CONFIG_UNIX_DIAG/实际模块及可能autoload、netlink buffer、native libc/nsfs/proc/LSM、临时FD/RAM/CPU/wall和外部服务费用须另列UNKNOWN；不得由文档存在推断目标支持。原namespace/UID/NNP/caps/cgroup/root/input采样及durable-before-permit、一次private成功outcome必须连同必要property修订接受fresh SPEC→QUALITY；本次不执行tests/native/WSL/Stage。

09:42:04.4769911UTC只读宿主：Windows11家庭版中文/26300，当前token非提升，E约1010037497856B可用，E:/Route2Dedicated仍不存在；物理RAM16890322944B，pagefile自动管理，D allocated16GiB。这些元数据不证明实际部署或完整权限能力。nonE512MiB超额前停止的原未答复选择已再次提出，要求明确选择是否改监控预算并接受在途超额；回答之前不改变合同，源码可独立继续。准备E30GiB/RAM16GiB/VRAM8GiB及原所有study额度保持；FROZEN_ADMISSION=None、PREPARED_UNREVIEWED、fullFAIL-001和APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持。

### 2026-10-09 原始phase-child观察／outcome实施收尾及下一装配依赖

前述范围已实际实施到生产源码：linux_child_launch保存原native出生descriptor、READY/status/exit/wait-reap/onceclose，private observer从原held资源实际读内核事实，publisher强留原guard/owner/batch/grant/scope/release与原clock，durable-before-permit及一次outcome消费。最终六cgroup controls/任务集合从同一held anchor复读并强留原raw；inline/fallback排除本buffer自身wrapper，保留原raw primary及真实secondary。parent AF_UNIX AF_NETLINK只满足真实IPC peer内核查询，旧worker/C child socket限制保留，不证明unit属性或UNIX_DIAG/LSM实际支持。限定SPEC→QUALITY：fresh独立LIMITED SPEC及LIMITED QUALITY均未发现剩余受影响范围P1/P2，无正式reviewID；准确4文件hash和完整条件卡见原review同日“phase-child原始内核观察、一次outcome及独立复核”，60生产AST／90文件mapping cdfb4bc3dc9a54adabeb8c21f2f7fef2ace2d880991a7dd7ec8b421286283496仅追踪。

真正后续依赖仍按原执行顺序：early只读nonGT metadata原owner与directory role-map/真实role publisher/reader → native prebirth t0/单次M0及实际manager/entry与原Windows QPC host/bridge认证 → guard/startup/seq2唯一GT broker/publisher → 只由原broker一次release的fixed phase-worker/current phase-root/spawn → actual once outcome及真实reference fence/unpublish后broker.revoke → terminal关闭后签名close/exit join/原cgroup清场/最终durable外墙钟。不能把需要seq2的GT installer放到guard.start前_loader，不能调用legacy ledger release两次，不能用callback或预期hash绕过原拒绝门。_load_native_path_map/_load_native_phase_runner/_require_native_nested_producers/QPC及完整installation门仍拒绝。

全可安装调用链、每一backing创建删除及逐role/phase授权撤销、目录receipt和逐file身份/容量、原once commitment-key issuer、完整readonly解释器/stdlib/PE/ELF/native/preconstructor closure、实际实体硬限/两项8GiB/三层baseline/余额/停止与收尾以及各控制/编译ABI/历史未来准备/外部observer-helper-launcher-bridge费用，仍须真实部署和完整正式复审。当前不能将native adapter/异常缓冲或工作集hash当独立原生权力。Windows宿主E:/Route2Dedicated仍不存在；自动pagefile/WSL服务/日志在途增长上界未知，“少量超额”用语已纠正，当前尚无明确答复，故nonE512MiB超额前停止合同未改，实际部署继续拒绝。

E30GiB/RAM16GiB/VRAM8GiB与既有study约束保持。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整FAIL-001和APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED；无合法Stage A/B或Route2结果。Route3 v1-003合法COMPLETE／四门FAIL不重跑。未新增/运行tests或读测试体、import、native编译链接装载调用、WSL操作、GT/生产/Stage/正式对象；index/auth卡/提示与原dirty/staged/untracked保留，仅原三文档追加，无新交接包。


### 2026-10-09 监控预算已绑定及once science key生产实施步骤

负责人明确答复“采用监控预算并接受上界未知的在途超额，继续工作”。nonE新增512MiB从严格超额前停止改为监控预算：实际observer须提前预警、停止新增工作、计入停止/收尾及可见增长，并记录采样/在途/系统共享作者的遗漏和超额；超额上界仍UNKNOWN，不能保证很小或改称per-study实体硬限。这项是明确资源口径变更，不是重问访问权限。先前384MiB active+128MiB收尾为规划分配，实际计量/阈值/停止执行者仍待实现和复审。既有pagefile分配及共享Ubuntu baseline不能计成任务新增；无法归属的成本保留UNKNOWN_NOT_ZERO。

仅此nonE口径变更，E30GiB准备预留（24carrier含20guest、外E6、guest实际baseline≤8）、whole RAM16GiB/VRAM8GiB、Windows owner可信/WSL2/Ubuntu22.04/glibc2.35、两项8GiB、1200/3600/900含60、C/AS/swap0/CPU200%/Tasks2、D_A2GiB V2及20+1/pooledGTreads0均保留。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、完整route2-ab-full-implementation-review-2026-09-29-FAIL-001/FAIL、APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED，无合法Stage A/B或路线二结果。负责人续行意图已授，实际完整冻结准入尚未形成。

沿原owner-only key设计补真实producer，限定linux_gt_history.py、linux_phase_publication.py及必要private源模块：1核原owner/current scope/grant/batch/parent PID-thread/ledger/绝对clock，预留错误与raw字段；2先consume一次producer调用，getrandom NONBLOCK取32B，返回先强留，校验及原durable history完成后才使用；3后续各phase只复用原key并核现payload，key不成为GT/mount/native authority；4失败保留primary/secondary并poison，不fallback/再发key，安装完整拒绝仍保留；5fresh独立SPEC→QUALITY及root AST/hash，仅源码闭合。现版90文件与原三文档状态、全部未来部署/运行/费用/完整正式review证据分别追踪，完整卡只在原review本unit收尾更新一次。

参照[Python3.10 os.getrandom](https://docs.python.org/3.10/library/os.html#os.getrandom)与[Linux getrandom](https://man7.org/linux/man-pages/man2/getrandom.2.html)；一次Python调用不等于已实证底层syscall次数。未最终绑定全部准备边界/预算前仍不编译/链接/装载/调用helper、启动生产组件；本轮不tests/import/native/WSL/GT/Stage/正式对象。原dirty/staged/untracked和授权卡/提示保留，无commit/reset/delete/new handoff。


### 2026-10-09 once key双审收尾及原fixed phase调用接续步骤

前一实际源码unit已闭合：原Owner系统once32B key、原durable历史、跨phase复用及payload核对，fresh独立SPEC→QUALITY均无剩余限定P1/P2，root60生产AST/90文件hash确认；准确身份见原review同日once key收尾。没有native运行或正式准入；非E512MiB监控及UNKNOWN上界在途超额接受已记入原三文档。

继续原已批准的fixed worker/GT scope事务，不在任务间询问是否继续：
1. 固定native执行器从原bootstrap/guard/controller装配并strong注册；装配不先grant或装载helper，原seq2 broker/publisher仍在guard.start之后。
2. 原healthy active invocation核scope/registered view/原科学输入形状及原绝对clock，预留原事务/返回/错误槽；原broker负责唯一release，publisher只按当前grant实际publish并取得原key。
3. 固定payload交给原C child启动路径；真实私有outcome由原owner一次消费，强留birth/READY/kernel/wait-reap/status/result。
4. actual publisher.close/unpublish及原reference fence先于broker.revoke；release/revoke原durable事件只各一次，不能再由StageB legacy追加。原事务来源核对先于StageB结果接纳。
5. 失败保留primary及所有实际secondary、原buffers和未清场对象；不重试birth/once FD、不给failed正常关闭/撤销或quarantine成功声明。新源private连续性hook不能在原broker revoke尚进行时引入终态中间态递归拒绝。
6. fresh独立SPEC→QUALITY、root AST/hash与变更范围核对；完整14项卡仅最终收尾更新一次。完整directory role/path-map、installation、readonly preconstructor、QPC/native prebirth、实体部署/预算/terminal退出及正式review缺口保持UNKNOWN/拒绝，不能因执行器source存在提前放行。

只源实施，不tests/test-body/import/native/WSL/GT/生产/Stage/正式image-volume-study-ledger-lock，保留原dirty/staged/untracked/index/授权卡提示，无commit/reset/delete/new handoff。PREPARED_UNREVIEWED、FROZEN_ADMISSION=None、fullFAIL-001和APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED不变，Stage及科学结论均无合法运行证据。

### 2026-10-09 固定phase事务限定双审收尾及private监控实施顺序

五文件fixed nativephase源码及StageB原私有事务接纳已完成fresh SPEC→QUALITY，no remaining scoped P1/P2，root fresh61AST/91文件hash核验；准确身份/异常两次修补/实际宿主metadata见原review同日收尾。未实际启动broker/publisher/native child或Stage；完整role/path-map/nested/QPC/installation gate仍拒绝。

接续已绑定nonE512MiB MONITORED及UNKNOWN上界在途超额接受，不重问访问权限：
1. 仅private Windows监控源模块+windows_preparation_job.py，固定C/D physical host卷native GUID/held root identity和free-space实际采样，原raw/owner PID-thread-QPC、预分配有界记录与primary/secondary保存。整盘变化只作monitored signal，归属和真实全费用保持UNKNOWN_NOT_ZERO。
2. 候选384MiB预警/停止新增工作＋128MiB收尾仅规划值；原Job的新Job/child/resume和等待边界接真实采样，触发或actual观察失败停止新增工作、进入原owned-handle清理；不得靠bool/callback/hash制造budget或native authority。
3. 原收尾继续计量/记录可见超额并保存读/报告/关闭错误，独立一次关闭每个原handle；触发不能跳过原cleanup。原60/70秒局部deadline不改称whole1800/3600/6000。killed child/wsl.exe不是VM/service退出。
4. 顶层readonly worker/pre-Python启动owner仍缺并拒绝，source/private sampler不安装全任务原生observer，也不证明RAM/tasks/所有系统作者/allocated bytes；PowerShell只读查询实际28–29线程，不充候选四task。native外部observer/源依赖/编译ABI/实际部署费用仍缺。
5. fresh SPEC→QUALITY、root AST/hash及限定差异核对，随后只在原review更新本轮一次完整14项卡；原授权卡不改、无新交接包。

E30GiB prep/wholeRAM16/VRAM8及原1200/3600/900含60、C/AS/swap0/CPU200%/Tasks2、D_A2GiB严格上界V2、20GT-backed+21GTfree/pooledGTreads0不改。源码可继续，预算/actual准备边界未全绑定前不native编译/链接/装载/调用或启动生产；本轮无tests/test-body/import/WSL/GT/Stage/正式对象/git mutation，保留原工作集。PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL-001/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED保持。

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

### 2026-10-10 adaptive-workflow 接续检查与 producer 任务止损

本轮先核原三文档最新10-10生产计划/限定双审/完整A+B卡、原授权Prompt/申请卡及原disk/cgroup/wall/QPC/Linux依赖证据。两继承源码SHA256与前节完全一致；原限定SOURCE_ONLY结论沿用，不返工。当前准备与安全metadata仍PREPARED_UNREVIEWED，正式independent_review_id=null，contracts.FROZEN_ADMISSION=None；完整FAIL-001未解除。

采用subagent-driven-development：独立工程审阅者READ_ONLY；一个唯一实现者限域追踪role publisher/source backing与原owner装配，分配8分钟软预算/最多两源，未能形成可独立闭合的生产SPEC，返回BLOCKED且未写源码。该限制只界定本次任务，不证明整台机器或所有未来source实施不可行。没有实现delta，因此不虚构新SPEC/QUALITY源码PASS；原两source独立限定结论保留。完整adaptive预检和circuit-breaker判断见原review同日新追加。

SOURCE已定位：production_runner._load_native_path_map只安装early metadata观察器；_load_native_phase_runner只绑定原executor；_require_native_nested_producers与Windows原QPC transport仍直接拒绝。phase publisher只观察已存在immutable root/两个placeholders，其原creator、readonly runtime/project/stdlib/ELF闭包未安装。Linux installation/write-boundary、pre-Python/startup握手拒绝仍存在；真实spawn/pidfd/wait/reap/status/UID/namespace/IPC的已有源码不替代实际部署与终态证据。study/.worker仍可写scratch/log，4096累计identity/256 scan/nlink=1不承接19894 alias或max250+7目录，不扩cap。

执行架构Recommendation=REDESIGN（收敛），模型可行性及本机预算内可行性UNKNOWN。停止没有实际信息增量的局部防御续补。后续任务依次应明确：
1. 专用E实体/三层baseline与全部归属费用、原生硬界及实际准备执行方法；
2. 固定immutable role source的source/creator/创建删除历史/不可写别名与readonly加载闭包，形成可独立实施的真实creator/publisher SPEC；
3. pre-Python/pre-spawn原t0/M0、原Windows QPC transport与Linux startup连续性；
4. 原controller下role轮换和phase worker正常/异常grant/revoke、wait/reap/status及全部写路径；
5. terminal关闭后签名close/exit join、raw cgroup清场、VM服务退出及finaldurable外部QPC；
6. 现版完整nested等价、完整正式独立复审和source/runtime/input/protocol/budget冻结，随后才是唯一合法Stage A/B。
此清单是SOURCE依赖顺序，不是本轮准备或实验执行授权；source布局/对象/费用未知继续拒绝。

后续真实源码单元仍须单实现者停止写入→独立SPEC→fresh QUALITY，所有范围P1/P2修复后报告；最多两轮仍未闭合即重新因果判断。只有AST/hash和静态复审可在当前边界执行，不新增/运行测试、不读test body，不project import/native compile-link-load-call/helper/WSL/GT/生产/Stage，不创建正式对象，不git mutation或覆盖无关工作。

原review本轮收尾将仅追加一次完整14项A+B条件卡，分别记SOURCE进展与actual部署/运行/预算/full review缺项。负责人绑定值/续行意图沿用，不重新询问；原授权卡不改，不新建交接包。Route3 v1-003合法COMPLETE/四门FAIL保持，无合法Route2结果前不启动三个模型架构方向。


### 2026-10-10 QUALITY P2 修订：新 SOURCE 收敛任务记录

原review同日“QUALITY P2 修订：独立预算的 SOURCE 收敛单元”已明确新任务负责人/root、8份准确source读取范围、20分钟新软预算、不同的“creator已存在但未接线”因果假设、区分性验收及UNKNOWN/BLOCKED停止条件；不沿用已结束两源/8分钟额度。该单元只读追踪，不授权部署/测试/生产，不扩cap或伪接线；所有原状态和本轮唯一完整A+B卡保持。


### 2026-10-10 独立预算SOURCE收敛单元关闭

task preparation-creator-to-role-substrate-source-trace由/root单独INLINE追踪，完成于UTC 2026-10-10 15:58:51 UTC；使用上节新20分钟软预算、原8源、一个不同假设，未沿用两源/8分钟旧预算。具体拒绝顺序与有限证据见review最新结果追加：固定prep-worker准备入口、原启动capture、held Windows identity及controller installation门仍拒绝；已有Linux正式study卷creator不是role source部署creator。

结果BLOCKED；没有可在现有已知原owner/布局内独立闭合的生产修改，不修改SOURCE、不延长/重置预算。下一架构判断为收敛实际准备/role substrate/安装/启动/退出的执行链，保留WSL、原预算与科学设计，禁止继续以局部metadata/cap/callback补丁绕过missing producer。本轮限定SPEC及fresh QUALITY随后顺序收尾；不构成完整实现或准入复审。唯一完整A+B卡保持review本轮14项更新，不新增卡或修改原授权卡。


### 2026-10-10 本轮限定独立双审收尾

SPEC第二轮与随后fresh QUALITY第二轮均NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_REVIEW_ONLY；第一轮预算/验收P2由独立新单元记录及有限结果关闭。完整过程见review同名收尾，未扩为新组件SOURCE或正式full-review PASS。本轮只追加原三份文档；原授权prompt/card、两metadata reader、Stage B matched-GT及finalize原修补保持，未tests/import/native/helper/WSL/GT/生产/Stage或Git mutation。两个有界追踪结束，生产补齐仍BLOCKED；下一执行架构收敛在明确实际producer/边界前不继续伪接线，已绑定WSL/预算/科学合同沿用。唯一完整A+B卡与原FAIL/FrozenAdmission=None/未获实验准入状态不变，不自动重跑Route3或启动三个模型方向。


### 2026-10-10 执行架构收敛讨论第1节（尚未进入实施计划）

本轮仅讨论，采用RESEARCH/INLINE、exec_command/Context7/request_user_input_async；新20分钟软预算/八源及停止条件见review同名追加，原预算不重置。生产creator实际body未补齐，未调用实现skill/代理或执行准备。提案顺序：原Windows bootstrap/QPC/native预算所有者→独立受限无GT准备与封存→正式准入及原Linux pre-Python/pre-spawn启动→controller内role publisher/原GT broker→受限worker→撤销/清场/VM退出/durable QPC。runtime/nonGT source与.worker scratch分开，已绑定WSL、预算及科学协议沿用。

下一便宜设计验收为A整体role目录树的非GTmetadata/stat容量与历史核算；若超额才评估B逐role独立封存的全生命周期费用。两个方案未绑定/未验证。独占WSL窗口问题待负责人回答，不自动shutdown/terminate现有发行版。待新设计闭合后再进入writing-plans及原单实现者→SPEC→fresh QUALITY流程；当前不增加测试、项目import/native/WSL/GT/生产或正式对象、Git mutation、新hand-off、新条件卡或PASS。


第1节提案自核补充：静态bank容量验收只针对现有合法nonGT输入/readonly依赖，不提前进行科学物化。原阶段动态产物的创建、冻结和IPC/文件交接仍按原合同核证；新布局费用及原2→4GiB上界需证明，不新增运行步骤或额度。设计仍开放，后续实施计划未启动。


### 2026-10-10 执行架构讨论第2节：独占窗口确认与容量选择依据

未来独占WSL窗口已获负责人“允许”：其他发行版不运行，收尾可关闭整台WSL2 VM。此决定只补host使用约束，不能当成当前独占、配置应用、退出/QPC或准备运行授权。沿用全部WSL/预算/科学协议；原SOURCE/metadata边界保持。

原design review同日第2节记录本次有界容量核算及四份metadata身份：只读登记JSON与nonGT leaf stat，不开payload。完整105 role为19894 alias，含reference的两个phase；唯一基础逻辑数据2.818974GiB，独立逐alias复制数据6.628845GiB，4KiB取整文件数据估算6.669407GiB。原8GiB baseline剩余1.330593GiB不等于实测余量，目标FS、runtime、控制及全归属费用仍UNKNOWN_NOT_ZERO。最大role257 leaf，输入必须独立于.worker，原4096history/256scan/nlink界不扩张。

下一讨论建议优先细化B“基础源一次封存＋逐role独立只读快照”；该方案尚未绑定，A也未证明不可行。下一SOURCE计划前必须确定确切物理backing和唯一creator，逐对象核全部写入口关闭、发布、真实worker spawn/pidfd/wait/reap/status、GT撤销、退出后清除设备/FD并删除generation；在原controller内实施publisher，不新增guest常驻进程。全部复制/封存历史与D_A2→4GiB、原准备及1200/3600/900秒费用必须闭合，未知不计零。静态准备不物化未来候选/26D/模型/预测/评价。

本节route2-static-input-capacity-discussion-2为/root INLINE RESEARCH，新20分钟预算UTC 2026-10-11 01:52:16起，五SOURCE/最多五metadata（实际四）；详见原review。零生产源码delta、零运行。后续组件单实现者停止→独立SPEC→fresh QUALITY；本节未构成组件双审或完整正式复审。完整A+B条件卡仍沿用原review本轮唯一14项卡，不另建授权/交接/冻结。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED不变；Stage A/B仍无合法运行，Route3 v1-003合法COMPLETE/四门FAIL保持。

### 2026-10-10 B已选择：后续组件分解与禁止假接线

原review最新“执行架构收敛第3节”记录B细化：唯一nonGT bank进入原准备/baseline；最多一个current role generation在study/.role-input内创建、磁盘ext4/真实写者关闭/inode保护/readonly验证设备后发布到固定v2 role目录，保持map/alias和三phase完整集合。清场完成后才新generation，无cache/prefetch/daemon，不动.worker4096history/256scan/nlink1。精确子image容量、设备支持、次数R及原2→4GiB/clock余量未证明，不绑定新额或运行。

后续设计依赖顺序：原native准备/加载前/实体执行合同与bank实际封存→拟linux_role_generation.py真实OS create/allocate/format/copy/fsync/seal/loop/dm/cleanup→拟linux_role_publication.py及原path_map/native same-FD role消费→原controller/phase正常与失败cleanup装配。native/route2_mount_helper.c/.h仅列为可能依赖，本轮未读body、不改、无compile/link/load/call。现LinuxInitialVolumeCreator仍是once-only正式study creator，不能改名替代role producer。

必须先解决生产冲突：early metadata实际mount与study namespace门要以同healthy原owner held FD/kernel身份做有限交接；保留拒绝其他/漂移mount，不删门。v2 role消费/lease当前拒绝，真实publisher存在之前不解_require_native_nested_producers。phase failure已经poison，原controller abort仅保留失败；新增独立原cleanup权根，按held pidfd/真实引用清除GT/view/dm/loop/backing，未知保留残留并阻止继续，不走normal revoke或签假删除。

SOURCE范围12项及两readonly advisor、新30分钟预算UTC2026-10-11 03:24:34起见review；/root唯一追加者。新物理细化仅供审阅，尚未进入writing-plans或源码实施；遵守brainstorming，后续单实现者停止→独立SPEC→fresh QUALITY。当前零测试/import/GT/helper/WSL/正式对象/Git操作，原授权卡不改，无新handoff/完整A+B卡。本节两个设计机制替代未假定本机支持：上游5.15未启fs-verity不意味着本机不支持；RAM generation未证明C/AS/峰值所以不默认采用。

所有已绑定科学计数、t0/M0/QPC、预算/收尾/退出、完整正式review及冻结条件保持。PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED不变；Stage A/B未合法运行，Route3终态不变。

#### B设计关口最新收尾（2026-10-10，尚未进入源码实施计划）

原review第3节最后顺序修订及本节收尾为状态依据：data正常关闭写者后完成tree，tree RW引用全部健康关闭后再保护data/tree；实际readonly loop/dm/目录发布在此后。设备清场前先关闭consumer/source mount与dm block/query引用；loop held/query FD在association实际消失验收前关闭，backing O_RDONLY/parent保留到身份核清/clear/unlink。任何未知保留残留及账目、阻止下一generation，不能按较早概述签设备消失。

独立SPEC限定NO_REMAINING_SCOPED_P1_P2 / DESIGN_SOURCE_REVIEW_ONLY已完成；其后fresh独立QUALITY因平台usage limit失败，未完成且无结论。双审关口未闭合；不派发同条件重复重试、不让作者自核或历史QUALITY替代。原review记录本节四次dispatch及额外一次的adaptive checkpoint；恢复核实际05:16:00超过原03:54:34软截止，其后只必要收尾，不重置预算继续设计探索/实现，wall与未知归属费用如实保留。

后续顺序为补齐fresh QUALITY→负责人written物理设计审阅（brainstorming明确关口）→writing-plans→逐组件单实现者停止→独立SPEC→fresh QUALITY。B主线、独占窗口、原WSL/预算/科学协议已绑定，不重问；此关口不是实验授权。无新SOURCE组件、无正式实现review ID、无部署/预算/运行期PASS。12项隔离stdlib AST/hash及404项文件/旧前缀/index保留核只是SOURCE/保留证据，授权prompt/card不变；没有新增测试、test body读取、import、GT/native/helper/WSL/生产调用、正式对象或Git操作。

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED保持，Stage A/B无合法运行和结果，Route3 v1-003合法COMPLETE/四门FAIL保持。沿用原唯一14项完整A+B卡，不新增卡或交接包；真实creator/物理封存/依赖/预算/启动退出/完整正式复审与冻结缺口仍按原卡拒绝。



# B Component SOURCE Implementation Plan — 2026-10-11

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. One implementation agent per component stops writing before a fresh SPEC reviewer and a distinct fresh QUALITY reviewer. Steps use checkbox syntax. The owner has already selected this execution approach; do not ask again.

**Goal:** Author and independently review the concrete SOURCE components for the selected sealed nonGT bank + CURRENT role generation architecture, preserving the original scientific protocol and every original admission rejection until its actual producer exists.

**Architecture:** A trusted native Windows owner and a separate native Linux start parent establish original clocks/identities, caps and readonly execution before Python. The original controller owns bootstrap handoff, unique bank, synchronous current generation, same-FD publication/reader, exact worker surface, original GT sequence and independent poisoned cleanup. Signed terminal/exit observations join actual OS state; whole VM/service enforcement and last Windows-owner exit remain explicit conditional prerequisites until real supported producers prove them.

**Tech Stack:** Existing Python stdlib SOURCE; four existing native C/H with separately guarded Windows seed/Linux native-start/device targets; Win32/Virtual Disk/Job APIs; Linux ext4/loop/device-mapper dm-verity/cgroup v2/pidfd/mount namespace APIs; WSL2 Ubuntu22.04/glibc2.35. No new test files or test commands. User prohibition overrides writing-plans/TDD testing steps; isolated stdlib AST/hash is the only current executable check.

---

This plan accompanies the original review's latest completed B architecture and original spec's latest contract. “NOW_SOURCE” means writing/reviewing source after this new candidate's fresh SPEC and distinct QUALITY, not loading it. No current plan step runs project imports, tests, native compile/link/load/call, helper/WSL/GT/scientific payload/production/Stage, or creates formal image/volume/study/ledger/lock/freeze objects. Existing .worktrees/high-f1-event-stack-execution/bme_compitition_next is the workspace; no new worktree is needed. Unrelated dirty/untracked work and the original eleven A2 staged entries are preserved. Root's feature branch commits/pushes are SOURCE snapshots; full runtime freeze remains in complete.

#### Dependency DAG and component eligibility

~~~text
C00 native enforcement/final-witness primitive audit + exact fail-closed callpoints
 └─ C01 native interfaces + original object/failure state
 ├─ C02 Windows physical/storage/resource scope producer [SOURCE now; actual scope conditional]
 ├─ C03 pre-load execution closure + native dual-clock/transport
 │   └─ C04 retained early metadata -> original initial-volume handoff
 └─ C05 unique nonGT bank creator [depends C02,C03]
      └─ C06 CURRENT generation create/seal/teardown [depends C04,C05]
           └─ C07 whole-directory v2 publisher + same-FD role consumer
                ├─ C08 exact worker namespace/input/GT/write composition
                └─ C09 original GT/phase integration + poisoned cleanup
C02,C03,C04,C06,C07,C08,C09 -> C10 terminal/native close/Linux observer exit
C02,C03,C10 -> C11 independent last-owner/kernel exit/durable join [conditional]
C01..C11 -> C12 complete SOURCE assembly/equivalence/freeze eligibility review
~~~

C00 is the mandatory cheapest first task; no defensive role/publisher implementation precedes its scoped result. C01, C02's fail-closed OS producers, C03, C04, C05, C06, C07, C08, C09 and C10 can be authored as NOW_SOURCE in DAG order. C11's concrete raw-exit/trace consumer and rejection can be authored now; certifying a complete independent last-owner witness is conditionally blocked. C12 may author the complete integration source but cannot claim installability/admission before C02/C11's actual prerequisites, full formal review and full freeze. Actual C/AS/M0/R/thread count/allocated bytes/VM settings/fees are never supplied as default successful data. Passing AST/hash is only parse/hash evidence.

#### Exact static command V and commit protocol G

For each component use the following exact command, replacing ONLY the explicit argument line by that component's listed command line. It reads no test body, imports no target module, writes no file and does not compile native source. Use the actual workspace as cwd.

~~~powershell
@'
import ast, hashlib, json, pathlib, sys
py_count = 0
native_count = 0
for name in sys.argv[1:]:
    path = pathlib.Path(name)
    data = path.read_bytes()
    if path.suffix == ".py":
        ast.parse(data.decode("utf-8"), filename=name)
        py_count += 1
    elif path.suffix in {".c", ".h"}:
        native_count += 1
    else:
        raise SystemExit("SOURCE_SCOPE_REJECT")
    print(json.dumps({"path": name, "bytes": len(data), "lines": data.count(b"\n"),
                      "sha256": hashlib.sha256(data).hexdigest()}, sort_keys=True))
print("SOURCE_ONLY PY_AST_HASH=" + str(py_count) + " NATIVE_HASH=" + str(native_count))
'@ | python -I -S -B - src/eating_event/route2_candidate_overlap/b_source_state.py
~~~

Expected for the shown C01 argument line: file rows with exact path/bytes/lines/SHA256 and terminal SOURCE_ONLY PY_AST_HASH=1 NATIVE_HASH=0. C01 includes native files in its own argument line below, so its expected terminal counts are1/2. A missing file/AST error/non-source suffix aborts; fix SOURCE and repeat only this static command. Never replace V by import all/compileall/pytest or a project CLI. Existing tests may be hashed by root without reading bodies; no task writes or runs them.

G is exact-path staging and exact-path commit AFTER implementation stops, SPEC finds no scoped P1/P2, then distinct QUALITY finds no scoped P1/P2 and neither reports an in complete review. Record review scope/verdict and raw V output in the original plan append; do not create a separate handoff/card. Any P1/P2 produces one scoped fix, author stops, and reviewers re-examine changed scope; historical narrow PASS is not reused. Commit failure preserves the index and original working files; no reset/stash/delete/force/merge/pull/main mutation. Do not amend existing review IDs or pins silently.

Before and after every G, compare the staged raw index rows for these exact eleven entries in memory:

~~~powershell
$route2ProtectedStaged = @(
  'configs/a2-context-verifier-v1-003.json'
  'configs/a2-context-verifier-v1-003.sha256'
  'scripts/run_a2_context_verifier_003.py'
  'src/eating_event/a2/audit.py'
  'src/eating_event/a2/budget.py'
  'src/eating_event/a2/contracts.py'
  'src/eating_event/a2/control.py'
  'src/eating_event/a2/worker.py'
  'tests/test_a2_resource_equivalence.py'
  'tests/test_a2_resource_recovery_namespace.py'
  'tests/test_a2_resource_supervisor.py'
)
$route2StagedBefore = @(git diff --cached --raw -- $route2ProtectedStaged)
# Execute exactly the component's git add -- paths and git commit --only -- paths.
$route2StagedAfter = @(git diff --cached --raw -- $route2ProtectedStaged)
if (Compare-Object $route2StagedBefore $route2StagedAfter) {
  throw 'PROTECTED_STAGED_DRIFT: stop Git work and retain all files'
}
~~~

This is names/modes/blob metadata, not test content. Each component below gives literal G commands. Never bare git commit, git commit -a or git add . . Keep .gitattributes's Route2 -text rules; global core.autocrlf=true must not alter exact native/Python input bytes. Push only codex/high-f1-event-stack-execution after source reviews; no main merge/force.

### C00: Cheapest real native scope and last-witness prerequisite audit

**Files:** Inspect only the existing windows_preparation_job.py:_prepare_fixed_worker/_KernelOwner._create_job/_birth_suspended, windows_non_e_monitor.py:_owner_binding/_resource_drift, windows_wall.py:_require_host_control_boundary, native/route2_mount_helper.c/.h and their official API documentation. Modify only native/route2_mount_helper.c/.h if an exact supported primitive/callpoint is established; otherwise append the exact SOURCE blocking result to the original plan. Do not create a generic proof-provider module or public allow flag. This is a source/API audit, not a machine probe.

- [ ] 1 (2–5min): Build an exact scope-to-native-call table: associated-process commit/CPU/process count from SetInformationJobObject/QueryInformationJobObject; actual thread identities from native thread snapshot enumeration; WSL compute-system/service/kernel association; physical carrier/header/control-volume cap; final original owner's exit and post-exit durable writer timing. Mark process-count != thread-count and committed-memory != RSS/VM. For every missing hard control write its exact pre-birth callpoint and VM_SERVICE_SCOPE_UNPROVEN or E_PHYSICAL_CAP_UNPROVEN outcome. Do not infer that monitoring is enforcement.
- [ ] 2 (2–5min): Audit whether the exact supported OS/kernel primitive can govern original VM/service/task-thread lifetime and independently witness last-owner durable exit inside the fixed scopes. For the final owner, distinguish kernel Process Stop from post-exit durable-flush evidence and identify every live witness/writer. Absence of a concrete callable primitive records OWNER_EXIT_JOIN_UNPROVEN; no substitute callback/schema/self-receipt is selected.
- [ ] 3 (2–5min): If a concrete primitive exists, specify its exact native signature, SDK/header/build requirements, original owner/callpoint, queried effective scope and raw failure/stop/cleanup facts in the original plan before implementing that branch. If it does not, retain the existing refusal and permit only independent lower-level SOURCE authoring; dependent deployment and whole-runner architecture compliance remains blocked. This bounded result is meaningful progress even when it cannot certify runtime feasibility.
- [ ] 4 (2–5min): Run V only for any changed native .c/.h, expected0/2; if no source changed record NO_SOURCE_DELTA and omit G. Fresh SPEC and distinct QUALITY must accept scope/primitive evidence and exact rejection before moving to C01. No retry/reset of budget or broad new platform search follows an unchanged unsupported result.
- [ ] 5 (2–5min): Only if native SOURCE actually changed and both reviews completed, use G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: bind native scope prerequisites to real OS callpoints" -- src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C01: Original B state, failure ownership and separate native targets

**Files:** Create src/eating_event/route2_candidate_overlap/b_source_state.py. Modify src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h and .c. Existing route2_mount_helper_describe_v1 and four mount wrappers keep the 40-byte Linux ABI and their one-syscall errno behavior. Separate Windows seed/Linux-start/device builds use explicit compilation selectors; the SOURCE plan does not execute a build.

- [ ] 1 (2–5min): Add complete common state/error types with no public authority factory. Code contract:

~~~python
from dataclasses import dataclass
from enum import Enum, auto

class GenerationStep(Enum):
    RESERVED = auto()
    DATA_RW = auto()
    DATA_COPIED = auto()
    DATA_CLEAN_UNMOUNTED = auto()
    FORMATTER_REAPED = auto()
    DATA_RW_RELEASED = auto()
    TREE_RW = auto()
    TREE_DURABLE = auto()
    ALL_RW_RELEASED = auto()
    INODES_PROTECTED = auto()
    DEVICES_RO_VERIFIED = auto()
    ROLE_PUBLISHED = auto()
    LEASED = auto()
    CONSUMERS_DRAINED = auto()
    ROLE_UNPUBLISHED = auto()
    DM_REMOVED = auto()
    LOOPS_ABSENT = auto()
    BACKING_DELETED = auto()
    COMPLETE = auto()
    POISONED = auto()
    RESIDUE_RETAINED = auto()

@dataclass(frozen=True, slots=True)
class NativeFault:
    operation: str
    error_number: int
    object_serial: int
    descriptor: int | None

@dataclass(slots=True)
class OwnedDescriptor:
    serial: int
    fd: int
    device: int
    inode: int
    mount_id: int
    consumed: bool = False

class BFailure(Exception):
    def __init__(self, primary: BaseException, secondary: tuple[NativeFault, ...]):
        super().__init__("original B operation failed; retained primary and native secondary facts")
        self.primary = primary
        self.secondary = secondary
~~~

Descriptor identity is actual producer output, never approval. Registry retains original descriptor objects, consumed status and raw preallocated errors before recording/raising. Component owner main-thread/invocation/guard/assembly references remain private; no public constructor accepts paths, callbacks, free-form receipt or a caller success flag.

- [ ] 2 (2–5min): Put platform includes behind explicit native target guards. Reject simultaneous Windows-seed/Linux-start/library selectors at preprocessing; keep glibc2.35/x86_64/UAPI checks for Linux library/start. Declare these concrete new header contracts separately from v1:

~~~c
#include <stdint.h>
#include <stddef.h>
enum r2_scope_result {
    R2_SCOPE_PROVEN = 0,
    R2_VM_SERVICE_SCOPE_UNPROVEN = 1,
    R2_E_PHYSICAL_CAP_UNPROVEN = 2,
    R2_OWNER_EXIT_JOIN_UNPROVEN = 3
};
struct r2_native_error_v2 {
    uint32_t operation;
    int32_t native_error;
    uint64_t object_serial;
    int64_t descriptor;
};
struct r2_birth_v2 {
    uint32_t abi, size;
    uint64_t original_monotonic_ns, original_available_bytes;
    uint64_t external_qpc_ticks, qpc_frequency;
    uint64_t stop_deadline_ns, cleanup_deadline_ns;
    int32_t pid, pidfd, start_memfd, transport_fd;
};
struct r2_verity_spec_v2 {
    uint32_t abi, size, data_block_bytes, hash_block_bytes;
    uint64_t data_blocks, hash_start_block, generation;
    int32_t data_fd, tree_fd, target_dir_fd;
    uint8_t root_sha256[32], salt[32];
};
struct r2_verity_result_v2 {
    uint32_t abi, size, error_count, reserved;
    uint64_t object_serial, data_loop_number, tree_loop_number;
    uint64_t dm_device, mount_id;
    int32_t data_loop_fd, tree_loop_fd, dm_block_fd, dm_control_fd;
    struct r2_native_error_v2 errors[32];
};
int route2_native_seed_main_v2(void);
int route2_native_linux_start_main_v2(void);
int route2_verity_publish_v2(const struct r2_verity_spec_v2 *,
                           struct r2_verity_result_v2 *);
int route2_verity_remove_v2(struct r2_verity_result_v2 *,
                          uint64_t original_cleanup_deadline_ns);
~~~

These are native OS primitive contracts; all FDs/results including partial failure are original caller-owned objects. The v2 provider rechecks actual FD/FS/device/namespace identities and never mints study approval. No guessed syscall numbers, C constructors, automatic dlopen target, or fallback mount. Implement individual bodies in the dependent components below.

- [ ] 3 (2–5min): Define serial consumption before each close, partial-creation result retention and errno/Win32 GetLastError capture before any Python/JSON/report operation. Fail slot exhaustion explicitly while retaining original primary/objects; no swallowing cleanup faults.
- [ ] 4 (2–5min): Run V with arguments b_source_state.py native/route2_mount_helper.h native/route2_mount_helper.c under the full directory prefix. Expected PY_AST_HASH=1 NATIVE_HASH=2. SPEC examines type/ABI/guard/error continuity; QUALITY independently examines no new execution/authority and exact legacy ABI preservation.
- [ ] 5 (2–5min): After both reviews, G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/b_source_state.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c
git commit --only -m "route2: define original B native and lifecycle source contracts" -- src/eating_event/route2_candidate_overlap/b_source_state.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c
~~~

### C02: Native Windows preparation, physical cap and actual resource-scope admission

**Files:** Create src/eating_event/route2_candidate_overlap/windows_b_preparation.py. Modify windows_preparation_job.py:_prepare_fixed_worker/_KernelOwner._kernel_lifecycle; windows_non_e_monitor.py:_install_for_original_owner/_new_work_guard; native/route2_mount_helper.c/.h Windows target. This component consumes no study/GT; physical operations remain dormant SOURCE.

- [ ] 1 (2–5min): Implement fixed native seed first-entry QPC/frequency/host available-RAM sampling, original process/file/volume handles and fixed suspended child creation with exact inherited handle list. Use CreateProcessW absolute ApplicationName, PROC_THREAD_ATTRIBUTE_HANDLE_LIST and job association before ResumeThread; retain raw process/thread creation times, effective QueryInformationJobObject limits, wait/exit and handles. Pre-association allocations are separately accounted.
- [ ] 2 (2–5min): Implement CreateVirtualDisk full-physical-allocation preparation, fixed original E volume GUID/path resolution, GetVirtualDiskPhysicalPath/GetVirtualDiskInformation and FileStandardInfo AllocationSize checks, actual format/attach/import/register state transitions and original cleanup. Each state is NEW→CAP_OWNER_HELD→ALLOCATED→FORMATTED→REGISTERED→BASELINE_RECORDED or FAILURE_RETAINED. Fixed native operation entry points:

~~~c
struct r2_windows_scope_v2 {
    uint32_t abi, size;
    uint64_t original_qpc_ticks, qpc_frequency;
    uint64_t carrier_allocated_bytes, external_e_allocated_bytes;
    uint64_t guest_baseline_bytes, host_control_allocated_bytes;
    uint64_t job_commit_peak_bytes, associated_threads, associated_processes;
    uint64_t vm_system_charge_bytes, service_charge_bytes;
};
int route2_windows_prepare_fixed_v2(struct r2_windows_scope_v2 *);
int route2_windows_observe_original_scope_v2(struct r2_windows_scope_v2 *);
int route2_windows_stop_original_scope_v2(uint64_t original_qpc_deadline);
~~~

All unknown raw values have distinct unproved status, never0. E30/carrier24/guest20/externalE6/control64+16 include headers/FS/history; per-study2→4 remains separate. Hard-cap producer must bind exact filesystem/quota/physical volume and all native/service metadata writers; a MaximumSize or ACL cannot satisfy it.

- [ ] 3 (2–5min): Implement actual supported Job commit/CPU/associated-process enforcement and actual thread/VM/service enumeration: held original process handles, native thread snapshot identities, compute-system/distro identity, original guest cgroup and service attribution. The Windows OS APIs do not promise a Job-wide thread cap or automatic WSLVM association. If no installed native/kernel control proves those precise scopes before birth/new work, emit VM_SERVICE_SCOPE_UNPROVEN and refuse _prepare_fixed_worker. Preserve functioning raw producers; do not manufacture a field/callback to remove rejection. This is the precise prerequisite for future actual supported enforcement, not a claimed platform PASS/NO-GO.
- [ ] 4 (2–5min): Bind the fixed native nonE observer to the same original owner before preparation. Account actual AllocationSize and service/pagefile/registry/eventlog/history. Latch384MiB stop-new; cleanup retains128 nominal and overshootUNKNOWN. Monitor itself counts toward512MiB/100%/4threads/6000. Prep4GiB/200%/4threads/1800 and external scope are distinct, sequential with study; every stop uses original QPC deadline.
- [ ] 5 (2–5min): Implement windows_b_preparation's private consumer using exact native original registry/file/process/epoch references; no API accepts a successful dict. Replace _prepare_fixed_worker refusal only when native producer really returns proven original scope; all unsupported scope branches retain explicit reject before any persistent/new work.
- [ ] 6 (2–5min): Run V with windows_b_preparation.py windows_preparation_job.py windows_non_e_monitor.py native/route2_mount_helper.c native/route2_mount_helper.h (full prefix), expected3/2. SPEC examines physical hierarchy/budget/epoch/all-writer coverage; QUALITY examines Job≠VM/thread/RSS and partial creation/failure/no bypass.
- [ ] 7 (2–5min): G exact files:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/windows_b_preparation.py src/eating_event/route2_candidate_overlap/windows_preparation_job.py src/eating_event/route2_candidate_overlap/windows_non_e_monitor.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: add native preparation and physical scope source producers" -- src/eating_event/route2_candidate_overlap/windows_b_preparation.py src/eating_event/route2_candidate_overlap/windows_preparation_job.py src/eating_event/route2_candidate_overlap/windows_non_e_monitor.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C03: Readonly PRE-LOAD closure, native Linux birth and original authenticated QPC

**Files:** Create src/eating_event/route2_candidate_overlap/linux_b_runtime_closure.py. Modify native/route2_mount_helper.c/.h; scripts/route2_preimport_launcher.py:_require_actual_start_origin/main; linux_start_clock.py:_require_actual_start_origin/_claim_once/consume_preimport_start_clock; windows_control_identity.py:Windows Readonly Execution Lease; production_runner.py:_load_authenticated_outer_qpc. Python validators run after interpreter loading and cannot substitute for this native task.

- [ ] 1 (2–5min): Implement native bounded PE import/delay-import/TLS and ELF PT_INTERP/DT_NEEDED/RPATH/RUNPATH closure parsing before executing/initializing user code. Use fixed installed readonly closure images; reject unresolved/ambient mutable dependency/search path and application constructors/TLS. Enumerate exact interpreter/stdlib/project/helper/crypto/transitive files with full manifests, not69/93 subset. Trust the explicit protected system OS loader boundary while retaining its unknown costs.
- [ ] 2 (2–5min): Implement native Linux parent's fixed CLOCK_MONOTONIC/MemAvailable capture before controller clone, original unit/cgroup effective memory/swap/cpu/pids/AS placement, atomic pidfd parent/child liveness, fixed charged replay claim and sealed original start memfd. Native parent remains charged outside study. Controller birth must not depend on future Python start data. Contract:

~~~c
int route2_capture_original_linux_birth_v2(struct r2_birth_v2 *);
int route2_verify_preload_closure_fixed_v2(void);
int route2_exec_original_controller_fixed_v2(struct r2_birth_v2 *);
~~~

The native source captures original PID/start/boot/time/mount/cgroup identities, original QPC transport frame and deadlines. Memfd seal bytes/FD/OFD and O_EXCL claim are actual facts; HMAC alone is not prebirth proof.
- [ ] 3 (2–5min): Implement fixed bounded pipe framing/nonces/signed canonical domain and original process-handle continuity. No keys/timestamps/paths are accepted through arbitrary argv/env. Close transport/backing/signing FDs before any scientific exec. The actual signer provider gets its separate native readonly runtime closure before import. Authentication failure burns the original attempt.
- [ ] 4 (2–5min): Replace launcher/start-clock/production QPC refusals only with private exact native installation/start consumption. Preserve original _ISSUED_START/claim/boot/time/namespace/guard/bootstrap continuity; never accept ExecMainStartTimestampMonotonic alone or rebase epoch. windows_control_identity revalidates PE/delay/system dependency closure against original held handles.
- [ ] 5 (2–5min): Run V with linux_b_runtime_closure.py linux_start_clock.py windows_control_identity.py production_runner.py scripts/route2_preimport_launcher.py native/route2_mount_helper.c native/route2_mount_helper.h, expected5/2. SPEC checks pre-load ordering, start/M0/deadlines and source type joins; QUALITY checks initializer race/import-before-proof/transport replay/error preservation. Actual ABI/loader support stays UNKNOWN.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_b_runtime_closure.py src/eating_event/route2_candidate_overlap/linux_start_clock.py src/eating_event/route2_candidate_overlap/windows_control_identity.py src/eating_event/route2_candidate_overlap/production_runner.py scripts/route2_preimport_launcher.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: define native preload birth and QPC continuity" -- src/eating_event/route2_candidate_overlap/linux_b_runtime_closure.py src/eating_event/route2_candidate_overlap/linux_start_clock.py src/eating_event/route2_candidate_overlap/windows_control_identity.py src/eating_event/route2_candidate_overlap/production_runner.py scripts/route2_preimport_launcher.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C04: Same original healthy early-metadata handoff to study creation

**Files:** Modify linux_native_path_map.py:_Owner/_install_original_metadata_path_map/_identity/_close_original_path_map; linux_initial_volume.py:LinuxInitialVolumeCreator.create_stage_a_volume, namespace gate around433–435; linux_production_controller.py:prepare_volume/assemble_production_owners.

- [ ] 1 (2–5min): Extend the existing original owner with actual retained metadata O_PATH/readonly source/ancestor descriptors and kernel identity frames; retain same original _Owner object and full map bytes/entry objects. Ensure factory failure owns every acquired FD before cleanup and leaves no public retry.
- [ ] 2 (2–5min): Create private handoff methods with exact existing guard/assembly references. Interface contract:

~~~text
linux_native_path_map._retain_original_bootstrap_mount(guard)
  -> original _Owner's held metadata/ancestor resources
linux_native_path_map._require_original_bootstrap_mount_for_volume(guard, mount_rows)
  -> accepts only exact healthy original metadata mount; rejects all others
linux_native_path_map._close_original_bootstrap_mount(guard, original_cleanup_deadline_ns)
  -> consumes each original FD once; failures retain identities
~~~

These methods resolve private _ORIGINAL/_ASSEMBLIES/_ISSUED_START/_ISSUED_BOOTSTRAP and never accept caller resource objects or allow flags. All105 target directories are created before ancestor-frame capture in preparation; fresh statx mount/device/ns/readonly/frame matches are required at the original initial-volume gate.
- [ ] 3 (2–5min): Refactor only the blanket /run/route2-input namespace gate to the exact held-owner matcher. Continue rejection of all occupied role/worker targets, foreign stacks, changed ancestors and writable metadata. Preserve same-invocation dual8GiB/native backing proof and original physical2GiB creator.
- [ ] 4 (2–5min): Connect prepare_volume and terminal/failure retention to this original handoff; owner resources survive guard.start and close only through original normal/emergency authority. No per-file dummy receipts or a source identity reconstructed from paths.
- [ ] 5 (2–5min): V linux_native_path_map.py linux_initial_volume.py linux_production_controller.py, expected3/0. SPEC checks original handoff/timing/namespace exactness; QUALITY checks open-versus-mounted identity race and single-close/failed factory behavior.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_native_path_map.py src/eating_event/route2_candidate_overlap/linux_initial_volume.py src/eating_event/route2_candidate_overlap/linux_production_controller.py
git commit --only -m "route2: retain original bootstrap mount into study creation" -- src/eating_event/route2_candidate_overlap/linux_native_path_map.py src/eating_event/route2_candidate_overlap/linux_initial_volume.py src/eating_event/route2_candidate_overlap/linux_production_controller.py
~~~

Changing the inherited c6b4c574… linux_native_path_map pin requires new component reviews, new exact hash and complete eventual freeze; old narrow SOURCE PASS does not automatically apply.

### C05: One real noGT bank creator

**Files:** Create src/eating_event/route2_candidate_overlap/linux_bank_creator.py. Modify windows_b_preparation.py and linux_b_runtime_closure.py preparation consumption; native/route2_mount_helper.c/.h device/format support.

- [ ] 1 (2–5min): Install _install_original_bank_creator only from the same charged native preparation/start registry, no arguments for paths/input receipts. Resolve exact registered unique(logical_path,SHA) nonGT objects; reject GT phases/providers/keys/history and differing map identity before copy.
- [ ] 2 (2–5min): Implement held guest carrier openat/O_EXCL/NOFOLLOW/fallocate, pinned formatter(pidfd/wait/reap/status), complete unique byte-copy using fixed buffer and same-FD hashes, file/parent/fs fsync and clean unmount. Preserve actual source bytes and complete creation/deletion/failure history.
- [ ] 3 (2–5min): Implement bank dataRO→treeRW→treefsync/allRWclose→bothinodeprotection→realROloop/dm→clean readonly ext4. Use exact native C01 verity contract; validate authenticatedroot/device/table; privileged aliases belong only to original creator/cleanup. No tree sealing while empty or detached writable data.
- [ ] 4 (2–5min): Account actual bank image/tree/FS/header/history under guest baseline<=8 and original preparation1800. Count formatter actual threads; reject unsupported cap/root/dm/loop/immutable or unknown costs. Bank mount is read-only input for the later generation creator; there is no worker-facing GT surface.
- [ ] 5 (2–5min): V linux_bank_creator.py windows_b_preparation.py linux_b_runtime_closure.py native/route2_mount_helper.c native/route2_mount_helper.h, expected3/2. SPEC checks complete unique input/seal ordering/baseline; QUALITY checks writable raw aliases/formatter failure/copy races/GT separation.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_bank_creator.py src/eating_event/route2_candidate_overlap/windows_b_preparation.py src/eating_event/route2_candidate_overlap/linux_b_runtime_closure.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: add unique sealed nonGT bank source creator" -- src/eating_event/route2_candidate_overlap/linux_bank_creator.py src/eating_event/route2_candidate_overlap/windows_b_preparation.py src/eating_event/route2_candidate_overlap/linux_b_runtime_closure.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C06: Synchronous CURRENT generation OS creator and complete teardown registry

**Files:** Create src/eating_event/route2_candidate_overlap/linux_role_generation.py. Modify native/route2_mount_helper.c/.h and linux_production_controller.py:assemble_production_owners/prepare_volume/current_snapshot. Uses C01 types and C05 original bank; does not reuse initial-volume creator as role creator.

- [ ] 1 (2–5min): Implement private _install_original_role_generation(guard) resolving exact original assembly/early-owner/start/bank/ledger. Reserve uint64 monotonicgeneration before mkdir/open, retain full ordered creation/deletion history and latch overflow/unknown previous deletion. At most one undeletedgeneration and no other-role/cache/prefetch/thread.
- [ ] 2 (2–5min): Implement the exact data/tree paths via held study dir; derive complete role file set from original entry objects/all three phases. Query real allocated headroom before fallocate; preserve max257 leaves as complete input facts, not scratchscan/cap. Builder mount fixed /run/route2-builder/role outside study tree; all writes and formatter are charged to same2→4 image and original clock.
- [ ] 3 (2–5min): Implement C01 GenerationStep transition checks and data copy/clean-unmount/formatter-reap/RW-close/tree-from-dataRO/allRW-close/immutable/readonlyloop/dm/table/ext4 ordering. Interface and ownership contract:

~~~text
linux_role_generation._begin_original_generation(guard, role_id)
  -> original private generation object, including partial failure objects
linux_role_generation._seal_original_generation(guard)
  -> same object after actual RO device/mount proof
linux_role_generation._drain_original_generation(guard)
  -> same object only after all consumer references absent
linux_role_generation._remove_original_generation(guard, original_cleanup_deadline_ns)
  -> actual dm/loop/backing absence or retained residue, never a caller receipt
~~~

Each function resolves the native original registry and consumes original descriptors; no constructor/path/callback is exposed. Actual loop ioctls are configured and queried; actual DM create/load/resume/status/table and authenticatedroot are checked. No ignore_corruption/check_at_most_once.
- [ ] 4 (2–5min): Implement normal teardown consumers/mounts→DMblock/queryclose→DMremove/queryabsence→loopheld/queryclose→associationabsence→identity/protectionclear/unlinkat/parentfsync. Keep DM control FD until actual remove query; retain backingRO/parent as needed before their once-close. Delayed loop removal uses remaining original deadline, never implicitsuccess. Unknown leaves RESIDUE_RETAINED and blocks nextrole.
- [ ] 5 (2–5min): Add actual outermost acquire/generation attempt/publish/delete/copybyte/depth/deadline counters, distinct from retained scientific arrays. Do not prepopulateR from105+105/callsite topology. current_snapshot reports actual inner allocated usage/residue alongside original main imagecapacity, avoiding doublecount.
- [ ] 6 (2–5min): V linux_role_generation.py linux_production_controller.py native/route2_mount_helper.c native/route2_mount_helper.h, expected2/2. SPEC checks states/complete phase set/accounting/registry; QUALITY checks raw writer capabilities, remove-before-close, FD reuse, failure residue and controller+formatterTasks2.
- [ ] 7 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_role_generation.py src/eating_event/route2_candidate_overlap/linux_production_controller.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: add current role generation lifecycle source" -- src/eating_event/route2_candidate_overlap/linux_role_generation.py src/eating_event/route2_candidate_overlap/linux_production_controller.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C07: Whole-directory publication and original same-FD v2 role reader

**Files:** Create src/eating_event/route2_candidate_overlap/linux_role_publication.py. Modify path_map.py:open_verified/lease_role_view/close; linux_native_path_map.py:_require_original_registered/_require_original_registered_batch; production_runner.py:_require_native_nested_producers.

- [ ] 1 (2–5min): Implement private _install_original_role_publication(guard) bound to original healthy early owner/full map and C06 generation. Publish WHOLE directory to exact stable hashedrole target via native open_tree/mount_setattr/move_mount; query publisheddirectory mountID/device/root/readonly/private flags and exact complete aliases/perleafidentities. Do not populate a per-file Mount Receipt collection for one directory mount.
- [ ] 2 (2–5min): Preserve metadata routing only for __study__/preflight_metadata and use real current role owner for nonGTrolefiles. Private interfaces:

~~~text
linux_role_publication._lease_original_role(path_map, role_id)
  -> context sharing one generation only for same original thread and role
linux_role_publication._open_original_role(path_map, logical_path, sha256, role_id, phase)
  -> context yielding stream for one held O_RDONLY FD
linux_role_publication._require_original_role_closed(guard)
  -> verifies original generation history and actual absence
~~~

Open uses heldpublishedparent + exactrelativealias/NOFOLLOW, fstat/statx mount/device/inode/size/nlink regularchecks, sameFDhash,seek0,yield,post frame/map/mount/generationcheck,healthyonceclose. Consumer error primary,post/close errors secondary. Removed/replaced FDnumber neverreused.
- [ ] 3 (2–5min): Wire v2 maplease depth; same-role nesting shares, otherrole/threadrejects. Keep inputs._RoleLease/_enter_lease nestingprohibition unchanged. IncrementrealR on outermost acquire and decrease depth; only actual complete teardown permitsnextgeneration.
- [ ] 4 (2–5min): _require_native_nested_producers validates installed original bank/generation/publisher/reader/controller/phase identities; keep拒绝 ifanyproducerunimplemented/unhealthy. Manifest/hash/boolean does not satisfy gate. Close delegates original normal/emergencyowner withoutresettingmapfailure.
- [ ] 5 (2–5min): V linux_role_publication.py path_map.py linux_native_path_map.py production_runner.py, expected4/0. SPEC checks map/alias identity/all3phases/nesting/dispatch; QUALITY checks sameFD TOCTOU, directoryreceipts, primary/secondary close and faultedlease continuation.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_role_publication.py src/eating_event/route2_candidate_overlap/path_map.py src/eating_event/route2_candidate_overlap/linux_native_path_map.py src/eating_event/route2_candidate_overlap/production_runner.py
git commit --only -m "route2: publish whole role directories and same-FD readers" -- src/eating_event/route2_candidate_overlap/linux_role_publication.py src/eating_event/route2_candidate_overlap/path_map.py src/eating_event/route2_candidate_overlap/linux_native_path_map.py src/eating_event/route2_candidate_overlap/production_runner.py
~~~

### C08: Complete actual worker namespace and write-surface composition

**Files:** Modify native/route2_phase_spawn.c/.h:child_main/route2_phase_spawn; linux_child_launch.py:_native/_run_private_phase/_reap_success; linux_phase_publication.py:_install_original_phase_input_publisher/_tree; phase_worker_entry.py:_main. Scientific execute_phase_operation semantics remain fixed.

- [ ] 1 (2–5min): Materialize exact fixed source tree mount composition through original creator before existing phasepublication/spawn: readonly runtime/source/currentnonGTrole where needed, releasedGTview/optionalhistoricalrow,readonly empty/readonly,minimumprivateproc/dev. Every fixedplaceholder and ancestor is prepared beforeframecapture. Noambient/tmp/home/cache/host/GPU/interop/signing/backingFD.
- [ ] 2 (2–5min): Keep existing UID/GID65534,groups/caps/no_new_privs/private namespaces/parentpidfd/READY-permit/resource/seccomp contract. Add explicit complete composition verification beforeREADY from original parent. Child reopenedrootmountidentity must matchdetached publishedroot, notinherited stalevfsmount. Additional native header contract:

~~~c
struct r2_phase_surface_v2 {
    uint32_t abi, size;
    uint64_t runtime_mount_id, source_mount_id, role_mount_id;
    uint64_t gt_mount_id, historical_mount_id, approved_scratch_mount_id;
    uint64_t original_stop_deadline_ns, original_cleanup_deadline_ns;
};
int route2_phase_surface_verify_v2(const struct r2_phase_surface_v2 *);
~~~

Values come fromoriginalpublisher; native checks actual mount/ns/readonly/source objects. Optionalabsentmounts requireactualabsence, not0treatedassuccess.
- [ ] 3 (2–5min): Explicitly enumerate approved write paths. Preserve phaseworkerRLIMIT_FSIZE0 and readonly environment for currentIPC-only phase. Where existingotherworkerapproval permits scratch/log, allow only exact.worker mount and existing4096history/256scan/nlink1; no capexpansion. Strictno-network/no-device/no-newtask filters, original AS/C/cgroup restrictions remain. Undefinedlibrarysyscall need exact scopedreview before allow.
- [ ] 4 (2–5min): Verify childoriginalpid/start/cgroup/UID/GID/ns/fd/maps/cwd/root/actual threads and original deadline before permit. Capture partialclone/native failure object beforePythonreport; unreapedchildregistry cannotberemoved. Formatter isreapedbeforeworkerbirth.
- [ ] 5 (2–5min): V linux_child_launch.py linux_phase_publication.py phase_worker_entry.py native/route2_phase_spawn.c native/route2_phase_spawn.h, expected3/2. SPEC checks complete surfaces/GT/write counts; QUALITY checks inheritedFD/mount/privilege escape, READYvsPythonbirth and wait/reap/failure. No actual sandbox run.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_child_launch.py src/eating_event/route2_candidate_overlap/linux_phase_publication.py src/eating_event/route2_candidate_overlap/phase_worker_entry.py src/eating_event/route2_candidate_overlap/native/route2_phase_spawn.c src/eating_event/route2_candidate_overlap/native/route2_phase_spawn.h
git commit --only -m "route2: specify complete native worker input and write surface" -- src/eating_event/route2_candidate_overlap/linux_child_launch.py src/eating_event/route2_candidate_overlap/linux_phase_publication.py src/eating_event/route2_candidate_overlap/phase_worker_entry.py src/eating_event/route2_candidate_overlap/native/route2_phase_spawn.c src/eating_event/route2_candidate_overlap/native/route2_phase_spawn.h
~~~

### C09: One GT broker sequence and original poisoned cleanup authority

**Files:** Create src/eating_event/route2_candidate_overlap/linux_failure_cleanup.py. Modify linux_phase_runner.py:_install_original_phase_runner/_execute_original_phase; linux_phase_publication.py:publish/close; linux_gt_history.py:install_original_gt_broker/_revoke_mount; linux_production_controller.py:abort_owned_startup/abort_startup; linux_child_launch.py:_run_private_phase retained registry. Normal revoke still rejects poisonedstate.

- [ ] 1 (2–5min): Install original cleanup owner beforefirstacquisition, with exact original invocation/guard/controller/thread/absolutecleanupdeadline. RegistereveryactualissuedFD/OFD/pidfd/mountID/device/loop/dm/backing/parent serial atissuancebeforefailurecouldoccur. Privateemergencyentry:

~~~text
linux_failure_cleanup._install_original_failure_cleanup(guard)
linux_failure_cleanup._register_original_issued_object(guard, owned_object)
linux_failure_cleanup._cleanup_original_failure(guard, primary_exception)
linux_failure_cleanup._require_original_cleanup_complete(guard)
~~~

owned_object is C01's original registry object, validatedsameissuer; no caller reconstructedpaths/receipts. Last entry rejectsuncertainresidue andneverconvertsfailuretosuccess.
- [ ] 2 (2–5min): Preserve normalgrant→publish→child outcome→drain→phase close→brokernormalrevoke, including20GT-backed/GT-free21st/pooledGT0. No generationcopy uses GT; historicalfinalmatchrow remainsoriginalsourceframe-preserving phaseclone with fivefieldprojection.
- [ ] 3 (2–5min): Replace controller's “preserved without teardown” branch by independent originalemergencyowner entry afterinlineprimarycapture. Failedphase's publisher/broker remainsfailed; do notcallnormalrevoke orclearfailedflags. Freezepermits/newwork first; pidfdkill/wait/reaporiginalchildren then reference/mountdrain, exact phase/roleunpublish, C06devices/backing cleanup.
- [ ] 4 (2–5min): Retainrawprimary+all secondary syscall/wait/unmount/close/remove/delete/ledgerfaults. ConsumedFD ismarkedbeforeclose andneverretried. Anyunknownreap/removal/deletion keeps original registry/residue/cost, blockingnextrole/terminalPASS. EmergencyGTviewremoval is separate failure fact, nothealthygt_phase_view_revoked.
- [ ] 5 (2–5min): V linux_failure_cleanup.py linux_phase_runner.py linux_phase_publication.py linux_gt_history.py linux_production_controller.py linux_child_launch.py, expected6/0. SPEC checks originalgrant/revoke/cleanupownership/scientific counts; QUALITY checks poisonedhealthyinterfaces, unreapedchildretention, signalidentity/closedFDreuse/partialteardown/primaryshadowing.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/linux_failure_cleanup.py src/eating_event/route2_candidate_overlap/linux_phase_runner.py src/eating_event/route2_candidate_overlap/linux_phase_publication.py src/eating_event/route2_candidate_overlap/linux_gt_history.py src/eating_event/route2_candidate_overlap/linux_production_controller.py src/eating_event/route2_candidate_overlap/linux_child_launch.py
git commit --only -m "route2: add original poisoned cleanup without normal revoke" -- src/eating_event/route2_candidate_overlap/linux_failure_cleanup.py src/eating_event/route2_candidate_overlap/linux_phase_runner.py src/eating_event/route2_candidate_overlap/linux_phase_publication.py src/eating_event/route2_candidate_overlap/linux_gt_history.py src/eating_event/route2_candidate_overlap/linux_production_controller.py src/eating_event/route2_candidate_overlap/linux_child_launch.py
~~~

Changing inherited linux_gt_history1ca884d5… requires fresh exact hash/reviews; old SOURCE review doesnotcoverdelta. StageBmatched-GT/execution.finalize repairsareinheritedandnotredone.

### C10: Actual terminal close, signed Linux exit and Windows child/VM join

**Files:** Modify terminal_observation.py:before_owned_terminal_close/after_owned_terminal_close/read_owned_terminal_close; linux_quiescence.py:require_linux_terminal_quiescence; linux_native_close_handoff.py:_require_actual_observer_runtime_closure/issue_native_close/issue_linux_exit; linux_post_exit.py:LinuxPostExitWitness; windows_wall.py:WindowsQpcWallInvocation; windows_native_close_handoff.py:verify_launch/verify_pair; windows_b_preparation.py original stop producer.

- [ ] 1 (2–5min): Bind terminal to C04heldmetadata,C06rolehistory,C09normal/emergencyobjects, original ledger/lockFDclosedfact and actual reference/cgroupquiescence. Terminal status COMPLETE/INCOMPLETE_RESOURCE andqualitygates remainseparate; unknowncleanupcannotclaimCOMPLETE.
- [ ] 2 (2–5min): Sign native close only after actual close andoriginalkernelchannelpeerproof. Observer's ownpreloadclosure fromC03 is required before provider import; replace _require_actual_observer_runtime_closure only with actual original native identity. Join exact closed ledger/OFD/source role/budget/unit/PID/pidfd to signatures.
- [ ] 3 (2–5min): Linuxwitness actualunitinactive/rawcgroupempty/controller exit/backing/FD/mount/history, then signedpostexit; close observer resources/exit. No observer signatureclaimsitsownfinalexit.
- [ ] 4 (2–5min): Different original Windows owner waitsoriginalWSLtransport/observerprocesshandles, retainsrawGetExitCodeProcess/QPC andsignedpair, requestsauthorizedexclusiveWSLshutdown andrequiresactualVM/compute-system/service disappearance plusfinalallocation. No wslexit/no-running-distro substitute. FlushfixedexternalEanchor through held file/volume, recordafterflushnativeQPC andcloseexecutionhandles once.
- [ ] 5 (2–5min): Leave Windows owner remaining work/exit charged and in complete scope untilC11; enforce original external deadline throughout. Anyjoin/flush/exit unknown returns preciseblockedoutcome,residueandprimary/secondary.
- [ ] 6 (2–5min): V terminal_observation.py linux_quiescence.py linux_native_close_handoff.py linux_post_exit.py windows_wall.py windows_native_close_handoff.py windows_b_preparation.py, expected7/0. SPEC checks terminal→sign→postexit→observer exit→VM→durableQPC ordering; QUALITY independently checks selfreceipt/cgroup/OFD/source identity/flush failure.
- [ ] 7 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/terminal_observation.py src/eating_event/route2_candidate_overlap/linux_quiescence.py src/eating_event/route2_candidate_overlap/linux_native_close_handoff.py src/eating_event/route2_candidate_overlap/linux_post_exit.py src/eating_event/route2_candidate_overlap/windows_wall.py src/eating_event/route2_candidate_overlap/windows_native_close_handoff.py src/eating_event/route2_candidate_overlap/windows_b_preparation.py
git commit --only -m "route2: join actual terminal observer VM and durable child exit" -- src/eating_event/route2_candidate_overlap/terminal_observation.py src/eating_event/route2_candidate_overlap/linux_quiescence.py src/eating_event/route2_candidate_overlap/linux_native_close_handoff.py src/eating_event/route2_candidate_overlap/linux_post_exit.py src/eating_event/route2_candidate_overlap/windows_wall.py src/eating_event/route2_candidate_overlap/windows_native_close_handoff.py src/eating_event/route2_candidate_overlap/windows_b_preparation.py
~~~

### C11: Independent last Windows-owner exit and kernel/durable-writer prerequisite

**Files:** Create src/eating_event/route2_candidate_overlap/windows_final_owner_join.py. Modify windows_wall.py and native/route2_mount_helper.c/.h Windows target. Concrete producer SOURCE/rejectcanbeauthorednow; full physicalwitness supportremainsconditional, neveraPASSbydesign.

- [ ] 1 (2–5min): Implement raw original process handle/creationidentity/exit status joinfromadifferentchargedowner, with nativeQPCclockprovenance. Noownexitselfsignature. Exact interface:

~~~c
struct r2_final_owner_join_v2 {
    uint32_t abi, size, result, reserved;
    uint64_t owner_creation_identity, raw_exit_qpc_ticks;
    uint64_t final_durable_qpc_ticks, original_qpc_frequency;
    uint64_t writer_original_identity, writer_exit_qpc_ticks;
};
int route2_final_owner_join_fixed_v2(struct r2_final_owner_join_v2 *);
~~~

Result R2_OWNER_EXIT_JOIN_UNPROVEN preserves unknown raw fields distinctly andblockswholeexternalscopeclosure.
- [ ] 2 (2–5min): Implement original kernel trace identity/evidence consumer for actual Process Stop withpinnedPID/creationtime/startnonce/clock and boundedrecordingbuffers. Source identifiesnativeETWStartTrace/ControlTrace and process-eventprovider pins, actual writer/file/volumehandles andloss/overflow detection. Kernel Process Stop is rawexit evidence only; it cannot byitselfdeclarepost-exit durable flush,complete fees orthreadcap.
- [ ] 3 (2–5min): Require a concrete independently operated native/kernel final flush/timing producer that continues after last owner exit. Identifyitsoriginalwriter/service/process lifetime, all charged external/whole resources and bounded cleanup. If unavailable/unsupported/unaccounted, keep source rejection beforeexperiment admission. Do notaddanunchargedparent,signselfexit orrecursivelyrenameanobserver. This is an exact unproved platform prerequisite; source/static checks cannot prove it.
- [ ] 4 (2–5min): Join C10child/VM durableQPC with raw last owner/writer exit and after flush clock. Only supported actual proof permitsfull external closed status; failuresretainartifacts andoriginalbudget charges. windows_final_owner_join private consumer acceptsnativeoriginalregistry only,not public receipt/path.
- [ ] 5 (2–5min): V windows_final_owner_join.py windows_wall.py native/route2_mount_helper.c native/route2_mount_helper.h, expected2/2. SPEC checks independent producer/complete actorbudget/clock/flush semantics; QUALITY checks circularwitness/newfreeancestor/kerneltraceoverclaim. No actual trace/session/processstarted.
- [ ] 6 (2–5min): G:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/windows_final_owner_join.py src/eating_event/route2_candidate_overlap/windows_wall.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
git commit --only -m "route2: keep final owner exit join tied to native kernel proof" -- src/eating_event/route2_candidate_overlap/windows_final_owner_join.py src/eating_event/route2_candidate_overlap/windows_wall.py src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c src/eating_event/route2_candidate_overlap/native/route2_mount_helper.h
~~~

### C12: Complete SOURCE assembly and future review/freeze admission

**Files:** Modify production_runner.py:assemble_production_bindings/_require_data_bindings_before_preflight/_require_native_nested_producers/main; linux_production_controller.py:assemble_production_owners/prepare_volume; scripts/run_route2_candidate_overlap_wsl.py fixed entry only. Append original three docs for actual component results; no separateauthorization/handoff/freezecreatednow. Existing source_snapshot/runtime_identity/admission_bootstrap are referenced byexactsymbols andlaterexecutionagentmayinspecttheirfullsourcewithinnewscope.

- [ ] 1 (2–5min): Wire fixedproduction entry to originalnativeinstalledcontext,C03start,C04metadata,C05bank,C06generation,C07reader,C08worker,C09cleanup,C10terminal,C11join. Keep all scientific adapters complete, notpartialproducercheck. Native/Windows source cannotbeaccepted merelybecausePythonobjects exist; unsupportedC02/C11conditionalproof remains rejecting.
- [ ] 2 (2–5min): SOURCE trace actual scientific role lease topology withoutreadingpayload: inputs._RoleLease/open_identity_index, references.open_role, Stage A reference/treatment call sites and stage_b._read_candidate_role/innertraining/heldout/outerfit/controlreferences. Retainedmaterializedarraysoutliveleaseswithoutkeepinggenerationalive; only actualoutermostmapacquisitioncountsR. Preserveloadernonnestingandoriginalscientificfunctions.
- [ ] 3 (2–5min): Pin fixed105reference→105treatment,25fitattempts/25predict/65decode/20GT-backed+GT-free21st/pooledGTreads0,strictpositiveoverlap versus300000ms alone,symmetrictolerance/discreteexactandfinalmatchedGTgain/loss; do notrerunRoute3orcreateautomaticmodelbranches. Existingexecution.finalize repairedprimary+secondarylogic remains unchanged.
- [ ] 4 (2–5min): Definefutureactualpreparationevidence gates: C02physical/all-service/thread scopes;C03actualreadonlyclosure/native birth/transport;C05bank<=8baseline;C06actualimage/headroom/R/cost/deletion;C08sandbox/worker facts;C09OOM/crash/quarantine;C10/C11actualterminal/cgroup/service/VM/final durable exit;completecrossOSequivalence. No native build/preparation/experiment commands are executable current SOURCE steps.
- [ ] 5 (2–5min): Full future freeze must use source_snapshot._tree_files/build_source_manifest overthe COMPLETE registered source/runtime tree, includingdirty/untrackedrequireddependencies wherelegitimate; runtime_identity._require_linux_runtime/admission_bootstrap._verify_runtime_execution arepost-load validatorsanddo notreplaceC03. All source/runtime/input/map/launcher-worker-controller/protocol/budgetactualidentitiesnewreviewID andFrozenAdmissionmustbindsamecompleteinstalledrunner. 69/93fileGitevidenceisnotfullfreeze.
- [ ] 6 (2–5min): V production_runner.py linux_production_controller.py scripts/run_route2_candidate_overlap_wsl.py, expected3/0. FreshSPECcheckscoverageall14originalgatesandnohiddenbypass;freshQUALITYcheckscompletecallgraph/stopownership/final unknowns/unchangedscienceandnoTEST/native execution. Record SOURCE_ONLY eligibilityseparatelyfromformalruntimefullreview.
- [ ] 7 (2–5min): Gsourcefilesonly:

~~~powershell
git add -- src/eating_event/route2_candidate_overlap/production_runner.py src/eating_event/route2_candidate_overlap/linux_production_controller.py scripts/run_route2_candidate_overlap_wsl.py
git commit --only -m "route2: assemble complete B source chain with actual admission gates" -- src/eating_event/route2_candidate_overlap/production_runner.py src/eating_event/route2_candidate_overlap/linux_production_controller.py scripts/run_route2_candidate_overlap_wsl.py
~~~

- [ ] 8 (2–5min): Aftercomponentresultsaredurablyappendedandfreshdocumentreviewscomplete,checkpointoriginal3only:

~~~powershell
git add -- docs/decisions/2026-09-27-route2-design-review.md docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md docs/superpowers/plans/2026-09-28-route2-wsl-controller-execution.md
git commit --only -m "docs: record independently reviewed B component source results" -- docs/decisions/2026-09-27-route2-design-review.md docs/superpowers/specs/2026-09-27-route2-candidate-interval-validation-design.md docs/superpowers/plans/2026-09-28-route2-wsl-controller-execution.md
git push origin codex/high-f1-event-stack-execution
~~~

No Git command proves runtime/freeze/experiment permission. The existing upstream branch is used; main remains unchanged.

#### Semantic requirement → component coverage (all fourteen original gates)

| Original gate / requirement | Concrete SOURCE producers/tasks | Future actual acceptance / stop |
|---:|---|---|
|1 complete runner/authorization/FrozenAdmission |C01,C02,C03,C12 exactoriginalassembly |Full independent review/newID/freeze; no publicapprovalflag; untilthenfullFAILunchanged.|
|2 fixedscience/currentnestedcrossOS105+105 |C07sameFD,C08surface,C12scientificcallgraph |Lawfulcurrentfullnestednumeric+discreteequivalence, no oldpartialPASS.|
|3 actualallrolecreator/reader/history |C04heldhandoff,C05bank,C06generation,C07reader |RealOScreator/seal/complete aliases/lifecycle; unknownorresidueblocks.|
|4 ledger25/25/65/20+1/D_A/N/M/S/B/R |C06actualcounters,C09GTsequence,C12integration |Oneenforcingledger,actualStageAcounts/capacity and legalStageBsameimageexpansion.|
|5 matchedGTactualgain/loss/historyprojection |C08exacthistoricalrow,C09sourcepreservingpublisher,C12 |LegalA2-004history/canonicalGT/fivefieldprojection; preservepriorrepairs.|
|6 isolation/scratch4096/256/nlink1 |C08actualnativeworker,C09cleanup |ActualUID/ns/IPC/cgroup/FD/maps/paths/thread facts; noinputmix/capexpand.|
|7 E30/carrier24/guest20/dual8/study hard cap |C02nativephysicalcreator,C04nativefree/handoff,C06inneraccount |Actualphysicalcaps/header/allocation/baseline/reserve; E_PHYSICAL_CAP_UNPROVEN stops.|
|8 nativeM0/t0/C/AS/CPU/tasks/clocks/GPU |C02scope,C03birth,C08worker,C10deadline |Actualeffectiveconfiguration/enforcement/peaks, no environment-onlyPASS.|
|9 prep/external/control/fullVMservicesfees |C02scope/accounting,C03actors,C05bank,C11writer |Actual all writer/service/thread scope; VM_SERVICE_SCOPE_UNPROVEN stops.|
|10 nonE512MONITORED/384stop/128nominal |C02originalnativeobserver,C10finalsampling |Original whole-taskAllocationSize/history/stoplatch; overshootUNKNOWNretained.|
|11 readonlypreload/dualclock/authtransport |C03nativepreloadbeforePythonandobserverprovider |ActualcompletePE/ELF/transitive closure;postloadvalidatorsnotreplacement.|
|12 primary/secondary/poison/terminal/exit |C01errors,C06teardown,C09emergency,C10join,C11lastowner |Actualreap/remove/delete/VM/observer/last owner/durable join; UNKNOWNretainresidue.|
|13 fresh review/full review/full freeze |EveryC'sSPECthenfreshQUALITY,C12fullmanifest |ScopedSOURCEreviews!=formalimplementationID/full freeze/admission.|
|14 legalRoute2terminal/quality/finalF1goal |C12scientificinvariantsandterminalreport |Legalearlystoporfull5foldStageB,qualitygatesseparate;F1>=.66deliveryopen.|

#### Conditional execution evidence — explicit remaining work, no current run

Native compilation/ABI/testing, actual preparation/import/WSL/deployment/runtime/GT/Stage are not currently authorized by this document. Before any such operation the execution agent must read the original actual preparation contract and prove the original budget, enforcement, readonly toolchain and scope; tests are prohibited, including new ones. Whenconditionsareclosedandoriginalauthorizationactuallypermits,actualevidenceproducersmustrecordaboveOSfacts,all historical/future fees and original stop deadline. Missing capability, writer scope or last witness returns the named blocking outcome and retains residue. Do not expand budgets or call the platform infeasible without proof.

Plan SOURCE acceptance is concrete: all component paths, symbols, interfaces, states, OS actions, error owners, dependencies, static counts and Git commands are present. Fresh candidate SPEC and distinct QUALITY are pending until author stop. The execution agent starts C00 after the candidate's scoped dual review. It proceeds to C01 and independent C02/C03 SOURCE parts after the required C00 component reviews; unsupported primitive results block complete enforcement/deployment, rather than silently selecting an abstract factory. This does not remove any actual runtime gate.

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED remain. Route2legalA/B/results0;Route3v1-003legitimateCOMPLETE/fourgatesFAIL. No new handoff, authorization card or freeze object is created. Only the original review's one final14-item table updates this turn's full minimum conditions.


### 2026-10-11 SPEC round 1 errata: authoritative G and C00 eligibility

Fresh /root/b_component_plan_spec_review finished its first pass and stopped reading, finding two scoped P2 issues: abbreviated staged-index comparison and ambiguous continuation after an unsupported C00 result. This append repairs both. Fresh SPEC second pass is required before distinct fresh QUALITY; no clean verdict is claimed. This author changed no SOURCE, ran no Git/tests/native/WSL/GT/formal-object operation and read no additional SOURCE body.

#### G correction: complete original staged identities

This supersedes G's git diff --cached --raw comparison. Cwd is E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next. Retain the selected component's existing literal exact-path git add and git commit --only pair. Insert this complete metadata guard before staging and after EACH commit; never bare commit/add-all.

~~~powershell
$route2ProtectedStaged = @(
  'configs/a2-context-verifier-v1-003.json'
  'configs/a2-context-verifier-v1-003.sha256'
  'scripts/run_a2_context_verifier_003.py'
  'src/eating_event/a2/audit.py'
  'src/eating_event/a2/budget.py'
  'src/eating_event/a2/contracts.py'
  'src/eating_event/a2/control.py'
  'src/eating_event/a2/worker.py'
  'tests/test_a2_resource_equivalence.py'
  'tests/test_a2_resource_recovery_namespace.py'
  'tests/test_a2_resource_supervisor.py'
)
function Read-Route2ProtectedIndex {
  $route2Rows = @(& git ls-files --stage -- $route2ProtectedStaged)
  if ($LASTEXITCODE -ne 0) { throw 'PROTECTED_INDEX_READ_FAILED: preserve state' }
  if ($route2Rows.Count -ne 11) { throw 'PROTECTED_INDEX_COUNT_DRIFT' }
  $route2Seen = @{}
  foreach ($route2Row in $route2Rows) {
    if ($route2Row -notmatch '^([0-7]{6}) ([0-9a-f]{40}|[0-9a-f]{64}) 0\t(.+)$') {
      throw 'PROTECTED_INDEX_IDENTITY_REJECT: full mode/SHA/stage/path required'
    }
    $route2Path = $Matches[3]
    if ($route2Path -cnotin $route2ProtectedStaged -or $route2Seen.ContainsKey($route2Path)) {
      throw 'PROTECTED_INDEX_PATH_DRIFT'
    }
    $route2Seen.Add($route2Path, $route2Row)
  }
  foreach ($route2Path in $route2ProtectedStaged) {
    if (-not $route2Seen.ContainsKey($route2Path)) { throw 'PROTECTED_INDEX_PATH_MISSING' }
  }
  [Array]::Sort($route2Rows, [StringComparer]::Ordinal)
  return $route2Rows
}
function Assert-Route2ProtectedIndexUnchanged {
  param([string[]]$BeforeRows, [string[]]$AfterRows)
  if (-not [String]::Equals(
      ($BeforeRows -join [Environment]::NewLine),
      ($AfterRows -join [Environment]::NewLine),
      [StringComparison]::Ordinal)) {
    throw 'PROTECTED_INDEX_DRIFT: stop; preserve index and working files'
  }
}
$route2StagedBefore = @(Read-Route2ProtectedIndex)
# Run ONLY the selected component's existing literal git add -- exact paths.
# If add fails, compare protected rows and stop; preserve state.
# Run ONLY the component's literal git commit --only -- the same exact paths.
$route2ComponentCommitExit = $LASTEXITCODE
$route2StagedAfter = @(Read-Route2ProtectedIndex)
Assert-Route2ProtectedIndexUnchanged -BeforeRows $route2StagedBefore -AfterRows $route2StagedAfter
if ($route2ComponentCommitExit -ne 0) {
  throw 'COMPONENT_COMMIT_FAILED: preserve index and working files'
}
~~~

Expected: exactly eleven unique original stage0 rows, each full six-digit mode/full40-or64-hex object ID/stage/path. Compare complete rows ordinally before staging and after EACH exact-path commit, including failure. Only Git metadata is read; test bodies remain unopened. Any count/stage/mode/SHA/path/read/compare/commit failure stops and preserves current state.

#### C00 correction: mandatory result → SOURCE eligibility

This table overrides all earlier broad NOW_SOURCE/continuation sentences, including C00 step3 and the final eligibility statement. C00 scoped dual review cannot convert an unsupported/unselected/unproven native prerequisite into a satisfied prerequisite.

| C00 result | Eligible SOURCE work | Mandatory stop |
|---|---|---|
| NOT_AUDITED, incomplete audit, or incomplete C00 review | C00 only. | No C01–C12 implementation. |
| Any required VM_SERVICE_SCOPE, E_PHYSICAL_CAP or OWNER_EXIT primitive unsupported, unselected or unproven | After complete C00 component SPEC and distinct QUALITY, ONLY independent C01 interface/error/rejection declarations without an actual producer claim; C02 already known native Job/raw original identity/observation/named-rejection parts; C03 already known native prebirth capture/bounded preload parsing/transport-rejection SOURCE parts independent of the missing primitive. | STOP dependent C04–C12 bootstrap handoff, bank, generation, publisher/reader, worker, GT, cleanup, terminal/witness and assembly implementation. Do not implement an undefined producer or the full conditional stack even as SOURCE. |
| All required exact native primitives supported and selected with concrete signature, owner, OS callpoint, effective scope and failure/stop semantics; C00 scoped dual review complete | Continue C01–C12 SOURCE in the DAG with component SPEC then distinct QUALITY. | Actual installed/runtime facts remain UNKNOWN until actual producers operate legally; no compile/link/load/call, preparation, WSL/GT/production/Stage or formal-object permission follows. |

Current result is NOT_AUDITED: this document author did not execute C00 or establish the missing native controls/witness. The earlier “completed architecture” title/claims are superseded by **conditional B architecture and SOURCE task plan**; full architecture feasibility is not complete. A complete conditional task description is not a selected or installed complete enforcement mechanism.


### 2026-10-11 最终限定双审收尾
fresh SPEC 第二轮与不同的 fresh QUALITY 均已实际完成、READSTOPPED，结论均为 NO_REMAINING_SCOPED_P1_P2 / DOCUMENT_SOURCE_PLAN_REVIEW_ONLY；仅审最新文档候选及 errata，无 SOURCE body/运行/修改。第一轮两项 P2 经一次 append-only 修订关闭。
当前 C00=NOT_AUDITED，仅 C00 可启动；unsupported/unselected/unproven 时按权威表 STOP C04–C12 even SOURCE，C00 组件双审后也仅允许已枚举独立 C01–C03 部分。完整架构可行性及实际强制/实体/退出证明仍 UNKNOWN，所有原准入拒绝与零合法 A/B 保持；最终 Git 文档提交与远端核由 root 随后完成，本记录不提前宣称推送。


### 2026-10-12 C00 static native scope and last-owner API audit - AUDITED_UNPROVEN

Author=/root/c00_author; baseline HEAD=67311c0d4a7fdda5ffb544074b5508c3c7cf4c40, branch codex/high-f1-event-stack-execution. Result=**AUDITED_UNPROVEN / DONE_WITH_CONCERNS / NO_SOURCE_DELTA**. The factual C00 audit is complete; C00 SPEC and different fresh QUALITY are pending after author stop. A clean scoped review could mean SOURCE_API_AUDIT_ONLY, never runtime PASS or complete architecture feasibility. No supported complete required primitive is selected. Existing refusals remain unchanged; **VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN** are audit blockers, not newly implemented native returns or successful receipts.

#### Routing, preflight and evidence boundary

capability_tags=windows-native/virtualization/resource-accounting/storage/durable-exit; loaded_profiles=generic (science fixed; ML would not change validation); workflow_path=RESEARCH; execution_mode=SUBAGENT; execution_backend=actual collaboration.spawn_agent, sole append author /root/c00_author. Root budget UTC10:38:32-11:38:32; author soft budget UTC10:39:00-11:04:00,25minutes. No runtime experiment. Validation order=bounded official API contracts + five allowed SOURCE paths -> factual result -> author stop -> fresh SPEC -> different fresh QUALITY -> only errata-eligible independent SOURCE parts.

| Fixed preflight field | Record |
| --- | --- |
| Goal | Find an exact supported producer for original VM/service/task-thread/storage enforcement and independent final-owner durable exit before removing any refusal. |
| Success metrics | Exact scope/callpoint/signature/build/query/failure/cleanup evidence and separate public/local ledgers; complete selection requires every required scope. No measured runtime metric is invented. |
| Constraints | Five SOURCE paths below, original-three append only. No tests/add/run/body reads, project imports, native compile/link/load/call, machine probe, helper/WSL/GT/payload/production/Stage, formal image/volume/study/ledger/lock/freeze or Git mutation. Original card/prompt/science fixed. |
| Prior art | Context7 WSL primary docs and official Microsoft Learn Job/Toolhelp/HCS/Virtual Disk/quota/ETW/flush contracts retrieved this turn; public contracts are not host observations. |
| Baseline | Known Job/raw owner-reference code plus unconditional worker/control refusals; original full implementation FAIL and zero lawful Route2 results. Installed/runtime capability UNKNOWN. |
| Candidate approaches | Narrow Job limits, native thread snapshots, generic HCS control, Virtual Disk allocation/query and per-user quotas, process-handle/ETW exit plus file/volume flush. None selects the complete required producer. |
| Critical assumptions | Original WSL system/services/kernel can be bound before births; every thread/writer/metadata charge governed; independent final producer closes its own writer/exit/durable chain without recursive witness substitution. Unproven. |
| Risks | Processes mistaken for threads, commit for RSS; shared services/kernel outside Job; virtual versus physical storage; post-exit trace/receipt writers or final witness lifetime unjoined. |
| Validation experiments | Static read/isolated stdlib AST/hash and official documentation only; no local OS API call or capability probe. |
| Kill criteria | Any required unselected/unproven primitive retains refusal and stops dependent C04-C12 even SOURCE. No broad platform retry or budget reset after this unchanged result. |
| Recommendation | Intake SPIKE FIRST for bounded C00; final REDESIGN for dependent complete SOURCE route with required producers unselected/unproven. This does not establish local/global impossibility or select a replacement platform. |
| Confidence | High for inspected code and retrieved API scope; complete producer feasibility, installed capability and actual costs UNKNOWN_NOT_ZERO. |

Manual telemetry: run_start=2026-10-12 10:39:00 UTC; gate_result=2026-10-12 10:46:37 UTC; author run_end below. Recorder coverage=MISSING: a separate user-selected JSONL conflicts with original-three-only writes; no file/recorder import. Tokens, model/tool/wait/review and historical/future preparation costs UNKNOWN_NOT_ZERO. A stdout encoding failure on a document read was corrected in the isolated stdlib process. An overlength shell append invocation was rejected before process creation (os206), with no write; smaller append calls preserve original prefixes.

Context7 resolve-library-id was first for Windows SDK and WSL. Windows SDK resolution yielded irrelevant Windows App SDK/WinRT matches; no such match selected, official Microsoft Learn used as scoped fallback. WSL selected /microsoftdocs/wsl, High reputation/score80.35, with separate query-docs for global resource/storage configuration and managed VM architecture/lifetime. Public retrieval is not local capability discovery. No broad search/retry follows this bounded unchanged result.

#### Exact scope -> calls -> existing versus missing callpoints

Python names are under src/eating_event/route2_candidate_overlap; lines are unchanged baseline. Missing callpoints below are required positions for a future concrete primitive, not invented functions or implementation permission.

| Required scope | Existing SOURCE / concrete public contract | Missing original boundary and disposition |
| --- | --- | --- |
| Associated-process commit | _cpu_profile:431-434 sets JobMemoryLimit4GiB and active-process/affinity/job-memory/kill-on-close flags. _create_job:458-462 SetInformationJobObject classes9/15; _read_limits:479-494 queries and compares flags/values/byte sizes. | Governs associated-process virtual committed memory, not RSS/whole RAM/VM/kernel/services. Never copy commit values into RSS/VM facts. [Extended limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information). |
| Associated CPU/process count | _cpu_profile picks at most2 affinity bits, ENABLE|HARD_CAP, CpuRate=min(10000,20000//processor_count), ActiveProcessLimit4. Official hard cap budgets associated-thread CPU cycles per scheduling interval; active limit counts associated processes. | Four processes != four threads. Nested CPU-rate quotas are relative to a CPU-controlled parent Job; effective original whole-machine rate cannot be assumed from local readback alone. Original thread/VM/service scope remains VM_SERVICE_SCOPE_UNPROVEN. [Basic limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information), [CPU rate](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_cpu_rate_control_information). |
| Child association before birth | _create_job:464-469 installs PROC_THREAD_ATTRIBUTE_JOB_LIST; _birth_suspended:502-505 CreateProcessW extended/suspended birth, :509-523 verifies original process/thread handles/IDs/membership/limits before ResumeThread:525. | Concrete child SOURCE is not parent/seed/pre-Python/VM association. _prepare_fixed_worker:802-805 refuses production before new work. Complete controls must exist at original native startup before interpreter import and transport/VM/service births; nearer _birth_suspended:497 before CreateProcessW is also required and cannot cover a preexisting VM retroactively. [Job list](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute). |
| Actual native thread identities | Supported observation: CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0), Thread32First/Next, initialized THREADENTRY32.dwSize and th32ThreadID/th32OwnerProcessID. No such producer in inspected native-call inventory; _owner_binding:338-341 gets current PID/TID only. | Snapshot is point-in-time, no birth barrier/lifetime cap or transient-thread coverage. Complete producer needs retained original thread/process handles+creation identity joins and actual hard task-thread control before births. GetThreadTimes gives held-thread creation time; live exit-time output is undefined. No cap selected: VM_SERVICE_SCOPE_UNPROVEN at startup and before _birth_suspended:502. [Snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot), [entry](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/ns-tlhelp32-threadentry32), [times](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes). |
| Original WSL compute-system/services/kernel | Generic HcsEnumerateComputeSystems -> HcsOpenComputeSystem -> HcsGetComputeSystemProperties yields held systems/Id/SystemType; schema has Owner/RuntimeId/HostingSystemId. HcsModifyComputeSystem has particular VM resource paths including memory SizeInMB; HcsTerminateComputeSystem terminates its held system. No HCS producer in five paths. | Generic HCS != supported ownership of original WSL-managed compute system. Owner is a client string, not original process/thread/service/kernel charge identity. WSL2 distros share managed VM CPU/kernel/memory/swap; wslservice starts VM/distros/shares. No exact producer joins original distro/system/service/kernel/thread scopes, installs all required controls before births, queries effective limits and closes every lifetime. VM_SERVICE_SCOPE_UNPROVEN; .wslconfig or wsl.exe kill/wait cannot substitute. [Enumeration](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsenumeratecomputesystems), [properties](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsgetcomputesystemproperties), [modify](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsmodifycomputesystem), [schema](https://learn.microsoft.com/en-us/virtualization/api/hcs/schemareference), [WSL architecture](https://github.com/microsoftdocs/wsl/blob/main/WSL/about.md), [components](https://github.com/microsoftdocs/wsl/blob/main/WSL/opensource.md). |
| E30/carrier24/guest20/externalE6 physical cap | CreateVirtualDisk.MaximumSize is virtual size; FULL_PHYSICAL_ALLOCATION preallocates necessary virtual-disk space. GetVirtualDiskInformation separates VirtualSize/PhysicalSize; FileStandardInfo AllocationSize != EndOfFile. No cap producer here. | These quantities do not govern all physical-E writers, nested backing-chain allocation, VHD headers/logs/BAT, NTFS/ext4/journals, other files, failures or privileged/service metadata growth. Exact overhead included/remaining and cap/query/all-writer control UNKNOWN. Cap owner/volume/storage-chain and effective limit must precede first persistent creation/format/attach/import/register at original startup/preparation gate; _prepare_fixed_worker retains refusal. E_PHYSICAL_CAP_UNPROVEN. [Create](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-createvirtualdisk), [flags](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ne-virtdisk-create_virtual_disk_flag), [sizes](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ns-virtdisk-get_virtual_disk_info), [file allocation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info). |
| Guest64MiB/host16MiB control physical caps within parents | IDiskQuotaControl.Initialize opens NTFS quota volume; SetQuotaState can enforce; IDiskQuotaUser.SetQuotaLimit is a volume-user limit. _require_host_control_boundary:125-131 refuses; _persist_owned:311 calls it before core/seal writes:343/352. | Per-user quota alone does not cover every user/service/privileged/metadata writer or full hierarchy. Cap establishment must precede first control-storage/witness birth; :311 is only its downstream pre-write refusal. Host16 within externalE6, guest64 within guest20, no added allowance. E_PHYSICAL_CAP_UNPROVEN. [Initialize](https://learn.microsoft.com/en-us/windows/win32/api/dskquota/nf-dskquota-idiskquotacontrol-initialize), [state](https://learn.microsoft.com/en-us/windows/win32/api/dskquota/nf-dskquota-idiskquotacontrol-setquotastate), [user limit](https://learn.microsoft.com/en-us/windows/win32/api/dskquota/nf-dskquota-idiskquotauser-setquotalimit). |
| Original continuity/nonE | _owner_binding:303-341 checks original issuance/owner/kernel/epoch/root/reference continuity and current PID/TID; _resource_drift:343-348 checks references, explicitly not native-buffer values or Python sandbox. | No OS enforcement, complete writer provenance or thread count follows. nonE512MiB remains MONITORED, visible384 stop-new/nominal128 cleanup; sampling/inflight/cleanup overshoot UNKNOWN_NOT_ZERO. Registry/pagefile/eventlog/service fees cannot become0. |
| Last original owner exit + durable writers | Original process WaitForSingleObject/GetExitCodeProcess can observe process exit; ETW End gives raw process identity/exit status. FlushFileBuffers works on held write file/admin volume; ControlTrace FLUSH/STOP on trace buffers/session. _persist_owned:379-384 samples/returns while Windows owner is alive. | Process signal/ETW End != post-exit durable flush. Earlier owner QPC/flush cannot certify own later exit. A charged independent producer must be selected before owner/witness births and admission, continue after owner exit, join every remaining writer completion/durable timing and its own final lifetime within original budgets. None selected: OWNER_EXIT_JOIN_UNPROVEN. [Termination](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process), [wait](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject), [ETW process](https://learn.microsoft.com/en-us/windows/win32/etw/process-v2-typegroup1), [flush](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers), [trace](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/nf-evntrace-controltracew). |


#### Supported signature / build / failure and cleanup ledger

These are retrieved public contracts and known narrow SOURCE callpoints. They do not select a complete new producer, installed SDK/ABI/privilege or successful local operation.

| Contract | Exact signature / documented build floor | Effective query, raw failure, stop/wait/cleanup |
| --- | --- | --- |
| Existing Job set/query/stop | BOOL SetInformationJobObject(HANDLE,JOBOBJECTINFOCLASS,LPVOID,DWORD); BOOL QueryInformationJobObject(HANDLE,JOBOBJECTINFOCLASS,LPVOID,DWORD,LPDWORD); BOOL TerminateJobObject(HANDLE,UINT). Windows.h/jobapi2.h, winnt.h; Kernel32.lib/dll; set/query _WIN32_WINNT>=0x0500; CPU-rate Windows8/Server2012; job-list birth Windows10/Server2016. | Rights SET_ATTRIBUTES/QUERY/TERMINATE; zero -> original GetLastError. CPU set may reject DFSS with error50. _query:471-477 checks returned bytes; _read_limits reads9/15 before birth/after membership. _terminate_originals:577-595 stops original Job/held process fallback; _observe_exit:545-562 waits original child and queries class1 ActiveProcesses; _bounded_cleanup_wait:597-616 keeps absolute deadline/UNKNOWN; _cleanup_once:658-712 independently consumes attributes/thread/process/Job/monitor. Stop covers associated processes/child jobs, no arbitrary WSL VM/service. [Set](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-setinformationjobobject), [query](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject), [stop](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject). |
| Missing thread observation | HANDLE CreateToolhelp32Snapshot(DWORD,DWORD); BOOL Thread32First(HANDLE,LPTHREADENTRY32); BOOL Thread32Next(HANDLE,LPTHREADENTRY32). tlhelp32.h, Kernel32.lib/dll; XP/Server2003. | Snapshot INVALID_HANDLE_VALUE -> GetLastError; First/Next FALSE distinguishes ERROR_NO_MORE_FILES from fault; returned dwSize must cover used fields; CloseHandle owns snapshot cleanup. No thread-birth hard control selected. [First](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-thread32first), [next](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-thread32next). |
| Nonselected generic HCS | HRESULT WINAPI HcsEnumerateComputeSystems(PCWSTR,HCS_OPERATION); HRESULT WINAPI HcsOpenComputeSystem(PCWSTR,DWORD,HCS_SYSTEM*); HRESULT WINAPI HcsGetComputeSystemProperties(HCS_SYSTEM,HCS_OPERATION,PCWSTR); HRESULT WINAPI HcsModifyComputeSystem(HCS_SYSTEM,HCS_OPERATION,PCWSTR,HANDLE); HRESULT WINAPI HcsTerminateComputeSystem(HCS_SYSTEM,HCS_OPERATION,PCWSTR). ComputeCore.h/lib/dll, Windows10v1809/Server2019. | Property query returns Id/SystemType/requested data; modify has particular supported resource paths, not arbitrary services/all-thread control. Submission S_OK != completion; retain submission and bounded operation-result HRESULT/document. No original WSL system/access/effective full-scope query selected. [Open](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsopencomputesystem), [terminate](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsterminatecomputesystem). |
| HCS operation ownership, nonselected | HCS_OPERATION WINAPI HcsCreateOperation(void*,HCS_OPERATION_COMPLETION); HRESULT WINAPI HcsWaitForOperationResult(HCS_OPERATION,DWORD,PWSTR*); void WINAPI HcsCloseOperation(HCS_OPERATION); void WINAPI HcsCloseComputeSystem(HCS_SYSTEM). Same ComputeCore requirements. | Create NULL means resource allocation failure. Wait distinguishes S_OK/HCS_E_OPERATION_NOT_STARTED/HCS_E_OPERATION_TIMEOUT/other HRESULT; optional failure document not guaranteed. LocalFree returned string; independently once-close operation/system. Documented optional callback is not a witness selection. Closing system handle is not automatically termination: ShouldTerminateOnLastHandleClosed is conditional; original WSL setting/other handles UNKNOWN. HCS terminate completion != host service exit/backing durable flush. [Create operation](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcscreateoperation), [wait](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcswaitforoperationresult), [close operation](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcscloseoperation), [close system](https://learn.microsoft.com/en-us/virtualization/api/hcs/reference/hcsclosecomputesystem). |
| Nonselected storage calls | DWORD CreateVirtualDisk(PVIRTUAL_STORAGE_TYPE,PCWSTR,VIRTUAL_DISK_ACCESS_MASK,PSECURITY_DESCRIPTOR,CREATE_VIRTUAL_DISK_FLAG,ULONG,PCREATE_VIRTUAL_DISK_PARAMETERS,LPOVERLAPPED,PHANDLE); DWORD GetVirtualDiskInformation(HANDLE,PULONG,PGET_VIRTUAL_DISK_INFO,PULONG). virtdisk.h/VirtDisk.lib/dll, Windows7/Server2008R2. BOOL GetFileInformationByHandleEx(HANDLE,FILE_INFO_BY_HANDLE_CLASS,LPVOID,DWORD), winbase.h/Windows.h, Kernel32.lib/dll, Vista/Server2008. | Virtual Disk returns ERROR_SUCCESS/direct error, not BOOL/GetLastError convention; failed outputs undefined. GET_INFO access/version/size must be valid. File-info FALSE -> GetLastError. No original all-writer cap/chain/effective query/bounded creator/rollback/cleanup producer selected; these observations neither cap metadata writers nor authorize allocation. [Virtual query](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskinformation), [file query](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex). |
| Nonselected NTFS quota | HRESULT IDiskQuotaControl::Initialize(LPCWSTR,BOOL); HRESULT IDiskQuotaControl::SetQuotaState(DWORD); HRESULT IDiskQuotaUser::SetQuotaLimit(LONGLONG,BOOL). dskquota.h/Dskquota.dll, XP/Server2003. | Support/access/path failures preserved; documented ERROR_NOT_SUPPORTED/NOT_READY/ACCESS_DENIED/LOCK_FAILED/E_FAIL as appropriate. Limit -1 is unlimited; TRUE immediately writes quota file, itself metadata work. Actual original volume/user/SID/enforced-state readback and every other writer still missing; no selected all-writer effective-limit query/cleanup. |
| Process wait/flush/trace, no complete final join | DWORD WaitForSingleObject(HANDLE,DWORD); BOOL FlushFileBuffers(HANDLE); ULONG WMIAPI ControlTraceW(CONTROLTRACE_ID,LPCWSTR,PEVENT_TRACE_PROPERTIES,ULONG). synchapi.h/fileapi.h/Windows.h, Kernel32.lib/dll; evntrace.h, modern Sechost.lib/dll, older Advapi32 per docs. | Wait needs SYNCHRONIZE; WAIT_OBJECT_0/TIMEOUT/FAILED distinct; closing pending handle undefined. Flush needs GENERIC_WRITE/admin volume; FALSE -> GetLastError. Trace FLUSH active buffers; STOP invalidates session; return direct system error. ERROR_MORE_DATA after STOP may mean already stopped; ERROR_ACTIVE_CONNECTIONS may mean stopping, so no blind retry/double ownership. Trace query/loss/flush/stop does not certify volume/receipt persistence or later writer exit. No independent full final join/bounded all-writer cleanup selected. |

#### Every witness/writer is charged; actual live inventory UNKNOWN

This is the required actor inventory, not a claim that these actors were started/enumerated. A new parent/callback/logger cannot be free; no witness signs its own final exit.

| Required actor / writer class | Original cost scope and exit ownership |
| --- | --- |
| Windows seed/launcher/wall owner/wsl.exe transport; Linux seed/observer/signer/pipe bridge; any final process/ETW consumer/flush controller | Combined externalRAM512MiB/CPU100%/4 actual tasks or threads/6000s including cleanup60, also whole-taskRAM16GiB/VRAM8GiB and actual E/control/nonE storage. A different charged owner joins originals; adding witness consumes same budget, its final lifetime remains unproven until a concrete independent kernel producer closes it. |
| Preparation worker/compiler/linker/start objects/toolchain/import/register/formatter/ABI-check actors/history | PreparationRAM4GiB/CPU200%/4 actual tasks or threads/1800s including cleanup60 plus whole/storage; no extra compile allowance. Original creator owns stop/wait/once-close/failure residues. Four Job processes != four tasks/threads. |
| WSL VM/guest kernel/init/GCS/daemons/plan9/network/GUI/GPU if present; WSLService/vmcompute/Hyper-V/system helpers | Exact original association, threads/lifetime/fee attribution UNKNOWN. All charge to whole-task and original causal scopes, cannot be omitted or reduced to wsl.exe. Controlled shutdown plus actual VM/workload/service exit and remaining writer flush missing. Service name alone does not prove ownership. |
| Study controller/worker/GT/runtime/ledger/data writers | Fixed C=min(4GiB,floor(3*M0/5)), RLIMIT_AS=C/2, swap.max0, CPU200%, pids.max2 including controller; physical study2->4GiB inside guest20. Actual charge/RSS/thread/child/FD/exit remains future lawful producer fact; none run here. |
| ETW provider/session buffers/kernel logger writes/ETL consumer/controller/file; receipt/seal writer; deferred VHD/NTFS/ext4/journal/cache/device flush work | Original external/whole scopes and actual E/control/nonE bytes/history. Charge domains and durable completion UNKNOWN_NOT_ZERO. Process event production, event arrival, trace-buffer flush, persistent file/volume completion, later work and writer exit are distinct. ETW End alone proves none of the later facts. |
| Registry/.wslconfig/pagefile/swap/eventlog/crash/report/OS-loading/initial service work; deleted/held-open files/retained failures | Complete original nonE baseline/history plus whole-task and backing-chain fees. Missing attribution !=0; user-handle close does not exclude privileged/inflight metadata writers. |

WSL docs establish global .wslconfig settings and shared managed VM CPU/kernel/memory/swap. wsl --shutdown terminates running distros/utility VM, not complete service/kernel writer-fee closure or durable timing. Selected memory8GB/swap0/processors2/guiApplications=false stays text until lawful actual boot/query proves applied settings. [Configuration](https://github.com/microsoftdocs/wsl/blob/main/WSL/wsl-config.md), [shutdown](https://github.com/microsoftdocs/wsl/blob/main/WSL/basic-commands.md). Complete existing mount-helper C/H only supplies Linux open_tree/mount_setattr/move_mount/umount2/ABI wrappers, fixed Linuxx86-64/glibc2.35/UAPI guards and raw errno. It contains no Windows complete control/witness. No new primitive branch or native modification is justified.

#### Public support versus local capability, source identity and eligibility

| Class | Evidence | Unproved |
| --- | --- | --- |
| Public API support | Narrow Job/Toolhelp/generic HCS/Virtual Disk/per-user quota/process wait/ETW/flush contracts retrieved. | Complete original VM/service/task-thread control, all-writer E/control cap and independent last-owner/writer durable-exit producer UNSELECTED/UNPROVEN; no global impossibility claim. |
| Local installed/runtime | No machine probe/native call. | ALL SDK/ABI/build/privilege/WSL/kernel/service/VM/volume/chain/thread/writer/limits/durability facts UNKNOWN; costs/counts UNKNOWN_NOT_ZERO. |
| SOURCE | Exactly five paths read/hash and original3 appended. | NO_SOURCE_DELTA; no V/G, tests/import/native/runtime/formal objects. No new source/provider/card/handoff/freeze. |
| Review | Factual author audit complete. | C00 fresh SPEC and distinct QUALITY pending; no full formal review/runtime PASS/installation/approval. |

Authoritative 2026-10-11 errata remains: incomplete C00 review -> C00 only. After both complete, these blockers still STOP dependent C04-C12 even SOURCE, including C11 witness/full assembly. They do not require a universal stop of the explicitly independent C01-C03 declarations/raw-observation/rejection slices. Concrete next recommendation is **C01_DECLARATIONS_ONLY**: plain value/error/state/named-rejection declarations and dormant v2 native-header/target guards preserving v1, with no registry/provider/success gate or whole C01 PASS. Independent C02 may only use already-known Job/raw-original-identity/observation/named rejection; C03 only already-known prebirth capture/bounded preload parser/transport rejection. No wrapper can advertise missing complete scope. Do not remove _prepare_fixed_worker/_require_host_control_boundary refusals, create an undefined HCS/cap/final witness, add successful callback/schema/allow/receipt, or implement bootstrap handoff/bank/generation/publisher/reader/worker/GT/cleanup/terminal/full stack. This C00 author starts no next component.

PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL / APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED; zero lawful Route2 A/B/results. Route3v1-003 COMPLETE/four-gate FAIL remains closed; no rerun/model direction. Saved scores/model/26D/threshold/decoder/matcher fixed; strict positive overlap versus300s gap only;105-reference work future StageA. Original authorization/card/prompt unchanged.

Exact SOURCE body-read/hash list, five (not an invented sixth), all under src/eating_event/route2_candidate_overlap:

| Path | Unchanged SHA256 |
| --- | --- |
| windows_preparation_job.py | db5313e36fcddfe6914dca4338592a7f40d44d2f1b75093865f7139346f37eb7 |
| windows_non_e_monitor.py | 63bf3e04fa699e5bd7132f089c2c8e845417873e4f0d4c1c39169d734e5cb2eb |
| windows_wall.py | 62009373a895912d6e33916023ebc0f5e449f52469dd2d81652444bc6d68818b |
| native/route2_mount_helper.c | 499b76ddd6275ef5589fdba1c39e9a1a98c55697920bd764d99f9b3123cbdf14 |
| native/route2_mount_helper.h | 6fe3048f48d69c822f59bf7468cb4815015016a7fb84608c81403a10927bf5e6 |

Relevant direct callers/helpers were inspected only inside these five paths, alongside the named C00 functions. All writes are append-only to this plan and original review/spec. Root owns broader preservation/Git/review dispatch. Final author verification/run_end and read/write-stop follow below.

Author verification/run_end=2026-10-12 10:56:37 UTC; elapsed from UTC10:39:00=1057.9s, within25minute soft budget. All five source SHA256 unchanged; all original3 raw prefixes preserved. NO_SOURCE_DELTA; native V/G omitted. C00 reviews pending. READSTOPPED / WRITESTOPPED; no further author reads/writes after this verification.


### 2026-10-12 C00 SPEC round 1 P2 repair - additional exact API contracts

Fresh /root/c00_spec first pass is READSTOPPED/WRITESTOPPED with one P2: the exact API ledger omitted contracts for existing child birth/exit and proposed held-thread timing, plus explicit wait/flush/trace version floors. This append supplies that bounded missing evidence; it does not retry/select missing complete primitives. Second SPEC pass then different fresh QUALITY remain pending. No SOURCE/native/Git mutation or new source-body read/platform search. Fix budget=4minutes from UTC2026-10-12 11:05:33, ending11:09:33; root's original global deadline unchanged.

Normative fixed preflight field: **Recommendation = REDESIGN**. This single final enum supersedes only the earlier combined intake/final wording. It means stopping the dependent complete SOURCE route until its necessary concrete supported producers are selected. It does not change confirmed B/WSL, science or budgets, choose another platform, or declare local/global impossibility. Earlier SPIKE FIRST remains historical intake of the completed bounded audit.

These cards supplement the preceding ledger; exact signatures use SDK parameter types in order. Public minimum versions are API/feature floors, not proof of installed SDK/runtime ABI or support. All local facts UNKNOWN; costs/counts UNKNOWN_NOT_ZERO.

| API and source/original owner | Exact signature; SDK/header/link/DLL/minimum | Access, failure, wait/cleanup contract |
| --- | --- | --- |
| UpdateProcThreadAttribute; existing original _KernelOwner._create_job:464-468, held startup list/job array before birth | BOOL UpdateProcThreadAttribute(LPPROC_THREAD_ATTRIBUTE_LIST,DWORD,DWORD_PTR,PVOID,SIZE_T,PVOID,PSIZE_T). processthreadsapi.h/Windows.h, Kernel32.lib/dll; base function Vista/Server2008. PROC_THREAD_ATTRIBUTE_JOB_LIST specifically Windows10/Server2016. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute). | Operates on initialized attribute list, not a process-open handle. Use valid original Job handles; set/query/termination rights remain specified in preceding Job card. dwFlags0; reserved previous/return-sizeNULL; value storage held until DeleteProcThreadAttributeList. Zero -> GetLastError, no suspended-then-AssignProcess fallback. List deletion and original Job close are separate owned cleanup operations. This establishes child association only. |
| CreateProcessW; existing original _KernelOwner._birth_suspended:502-505; original returned process/thread handles retained at :506 onward | BOOL CreateProcessW(LPCWSTR,LPWSTR,LPSECURITY_ATTRIBUTES,LPSECURITY_ATTRIBUTES,BOOL,DWORD,LPVOID,LPCWSTR,LPSTARTUPINFOW,LPPROCESS_INFORMATION). processthreadsapi.h/Windows.h, Kernel32.lib/dll; XP/Server2003 base function. Extended job-list route retains higher Windows10/Server2016 floor. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw). | Runs under calling process security context; it does not open an arbitrary original owner by PID. Existing absolute application path, writable command buffer, bInheritHandlesFALSE and extended/suspended startup remain distinct requirements. Zero -> GetLastError. Successful creation is not full initialization or final exit. Creator owns returned originals; wait/query/termination require the rights in their respective cards. Close both process and primary-thread handles through existing once-close cleanup; handle close alone is not termination/flush. No parent/seed/pre-Python authority follows. |
| GetThreadTimes; missing held-thread timing producer, not called anywhere in inspected five-file native inventory; proposed different charged owner would retain the original thread | BOOL GetThreadTimes(HANDLE,LPFILETIME,LPFILETIME,LPFILETIME,LPFILETIME), outputs creation/exit/kernel/user in that order. processthreadsapi.h/Windows.h, Kernel32.lib/dll; XP/Server2003. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes). | Needs THREAD_QUERY_INFORMATION or THREAD_QUERY_LIMITED_INFORMATION; XP/Server2003 needs QUERY_INFORMATION. Zero -> GetLastError. Live exit-time output is undefined. Creation/exit FILETIME is wall-clock identity/timing, not raw QPC/durable completion. This neither waits nor caps threads; a future producer must first establish held-handle/creation/owner joins, bounded exit wait and original once-close. No such original owner/callpoint/producer selected. |
| GetExitCodeProcess; existing _KernelOwner._observe_exit:552-554 after WaitForSingleObject(original hProcess)==WAIT_OBJECT_0 | BOOL GetExitCodeProcess(HANDLE,LPDWORD). processthreadsapi.h/Windows.h, Kernel32.lib/dll; XP/Server2003. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess). | Needs PROCESS_QUERY_INFORMATION or PROCESS_QUERY_LIMITED_INFORMATION; XP/Server2003 requires QUERY_INFORMATION. Zero -> GetLastError. Immediate query may return STILL_ACTIVE259 while alive; an application can also exit259, so it is not an independent liveness proof. Existing original handle signal precedes query. Does not wait/flush/close; original process once-close remains _close_process:624-628 and _cleanup_once. No VM/service/last-owner durable join follows. |
| WaitForSingleObject; existing original _KernelOwner._observe_exit:548 and bounded original cleanup wait:597-616 | DWORD WaitForSingleObject(HANDLE,DWORD). synchapi.h/Windows.h, Kernel32.lib/dll; XP/Server2003. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject). | Original handle needs SYNCHRONIZE; WAIT_OBJECT_0/TIMEOUT distinct, WAIT_FAILED0xFFFFFFFF -> GetLastError. Finite wait derives from original deadline; pending-handle close is undefined. Process signal means process exit, no disk durability/VM-service closure. Owner stops/waits before independent once-close; timeout does not remove resources or prove exit. |
| FlushFileBuffers; existing windows_wall._flush:44-48, called by original Windows durable writer for _persist_owned core/seal paths:343/352 after required control-boundary refusal:311 | BOOL FlushFileBuffers(HANDLE). fileapi.h/Windows.h, Kernel32.lib/dll; XP/Server2003. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers). | Open file needs GENERIC_WRITE; all-open-file volume flush needs admin privileges and held original volume handle. Zero -> GetLastError. Synchronous file/volume flush completion is separate from process/trace writer exit; the calling owner is alive. Its file/volume closes and final QPC do not prove its own later exit. No all-writer final bounded cleanup is selected. |
| ControlTraceW; no existing native producer in five paths; proposed charged independent trace controller/writer remains unselected | ULONG WMIAPI ControlTraceW(CONTROLTRACE_ID,LPCWSTR,PEVENT_TRACE_PROPERTIES,ULONG). evntrace.h; base API Windows2000Professional/Server2000. EVENT_TRACE_CONTROL_FLUSH is unsupported on Windows2000, so that feature cannot use the base floor. Current docs link Sechost.lib on Windows8.1/Server2012R2 and Sechost.dll on Windows8.1/Server2012; listed older systems use Advapi32.lib/dll. Actual SDK declaration compatibility remains UNKNOWN. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/nf-evntrace-controltracew). | Control requires elevated admin/Performance Log Users or listed system-service identities; NT Kernel Logger requires admin/LocalSystem. Return ERROR_SUCCESS/direct system error, not BOOL/GetLastError. FLUSH active buffers; STOP invalidates session handle. ERROR_MORE_DATA after STOP may already mean stopped; ERROR_ACTIVE_CONNECTIONS means stopping. Cannot stop/flush from DllMain safely. No original controller/session/budget/exit/volume-durability producer selected; no callback or self-exit receipt closes it. |

VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN, NO_SOURCE_DELTA, existing refusals and authoritative C00-only-until-dual-review / dependent C04-C12 stop remain. This fixes the document omission for review, not the missing complete controls. Author verification/run_end=2026-10-12 11:08:01 UTC; READSTOPPED / WRITESTOPPED after prefix/hash verification. Fresh SPEC second pass is next; no guessed PASS.


#### C00 P2 timing-contract supplement within the same four-minute repair

The original timing scope already includes windows_wall._qpc:31 and _KernelOwner._clock:337/_start_clock:346; these cards add documentation only, without a new timing/owner producer or source read.

| API | Exact signature / SDK requirements | Provenance / failure / ownership |
| --- | --- | --- |
| QueryPerformanceCounter | BOOL QueryPerformanceCounter(LARGE_INTEGER*); profileapi.h/Windows.h, Kernel32.lib/dll; Windows2000Professional/Server2000 minimum. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter). | Writes counter counts to a valid output buffer; no process/thread access handle, wait or close is required by this call. Nonzero success; zero -> GetLastError. Docs guarantee success with valid parameters on XP or later, not correctness of this unprobed installation/ABI/binding. Retain original native binding/epoch/owner and actual successful counter observation. Sampling is elapsed-time evidence, not process exit, pre-Python birth timing or durable flush. |
| QueryPerformanceFrequency | BOOL QueryPerformanceFrequency(LARGE_INTEGER*); profileapi.h/Windows.h, Kernel32.lib/dll; Windows2000Professional/Server2000 minimum. [Official contract](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancefrequency). | Writes counts/second; frequency is fixed at boot and consistent across processors. No process/thread access handle, wait or close. Nonzero success; zero -> GetLastError; older unsupported hardware may output0. XP-or-later valid-parameter guarantee does not prove local binding/epoch provenance. Existing original positive frequency and consistency checks remain; FILETIME is not automatically a QPC join. No counter/frequency sample certifies the owner's future exit or final writer lifetime. |

All three UNPROVEN outcomes/NO_SOURCE_DELTA and pending second SPEC/distinct QUALITY remain. Same repair final author stop=2026-10-12 11:09:06 UTC; READSTOPPED / WRITESTOPPED after prefix verification, within four-minute budget ending11:09:33.


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

### 2026-10-12 三机制证据收敛与执行边界

当前事实及本轮唯一完整14门卡以[原review最新边界](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-boundary-20261012)为准；原计划body不改。
root本轮60分钟UTC11:48:17→12:48:17，RESEARCH/REDESIGN/PARALLEL_SUBAGENT；新具体证据重评为2只读researcher＋1作者＋fresh SPEC＋不同QUALITY共5角色，同预算，不是reset。
两个researcher已结束；root项目body仅windows_wall.py，本作者仅三文档尾部/append；全部token/资源收费UNKNOWN_NOT_ZERO，runtime实验0。
先保留pinned WSL `_CreateVm`→GUID/config/HCS→出生后callback真实顺序，再补原本机version/held身份/全服务线程kernel归属；没有选出complete producer。
physical extent候选必须由原trusted layout owner闭合全raw aliases/resize，三层metadata/headers/overhead内计；L_C literal physical backing与guest hosting FS同invocation各free≥8。
原carrier无第三8GiB门；near20 fixed nested在near24 L_C里可能触发拒绝，是该条件布局冲突，不签本机全局不可能。
finite extent、formatterAPI和依赖查询都仅未来设计；不运行CreateDisk/partition/format/import/register，不因源码出处或owner权限放行。
windows_wall live postflushQPC与owner未来exit分开；允许final trusted coordinator存活需真实负责人答复及acceptance后收费/写入协议，未实施。
三问题PENDING：最后监督者存活/原4线程scope/新物理extent选择；没有答案时不选择推荐，不改原cap/卡/prompt。
作者STOP ALL WRITES后fresh SPEC；实际收敛后不同fresh QUALITY。本轮新限定文档双审PENDING，不能复用C00/C01 verdict代替。
C00 AUDITED_UNPROVEN；C01声明切片已双审、whole C01不完整；C02/C03 NOT_STARTED。下一SOURCE仅原erratum C02 known Job/raw identity/observation/rejection、C03 known prebirth/preload-parser/transport-rejection独立部分。
三UNPROVEN必要机制未闭合前C04–C12 STOP even SOURCE；无provider/wrapper/receipt替代缺失producer，完整架构NOT_COMPLETE/UNPROVEN。
PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/route2-ab-full-implementation-review-2026-09-29-FAIL-001 FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED；合法Route2 A/B/results0，F1≥.66 open，Route3v1-003 COMPLETE/四门FAIL不重跑。
本作者仅三原文档UTF8无BOMappend与raw-prefix核，无SOURCE/Git/额外对象/测试/testbody/projectimport/helper/native/WSL/probe/GT/生产/Stage/正式对象；实际bytes/time单独报告root，不预造full-review或Git收据。

### 2026-10-12 三机制复核与下一合法动作收据

[原 review 限定双审和中断/Git 收据](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-review-receipt-20261012)：独立 SPEC READ_STOPPED UTC 12:23:56；中断恢复后不同 fresh QUALITY UTC 16:15:15→16:16:06，均 NO_REMAINING_SCOPED_P1_P2 / CONDITIONAL_MECHANISM_DOCUMENT_REVIEW_ONLY。
原三文档条件 suffix 已提交 9fb9bb16738df2ea7abe18e17834080299caf1fe，范围仅三文档、原 11 staged 身份保持；收据之后的 push/最终保留核未发生，不冒充结果。
原作者 103 秒及 root 原窗口过期如实记录；恢复只补审与事实/Git 收尾，没有重置生产/实验预算。费用/token/历史未来准备成本 UNKNOWN_NOT_ZERO。root 发现 stdin 编码丢失并仅修复自己的未提交收据，既有 prefix 不改。
三项具体边界答复仍待收到；独立 SOURCE 若另推进，仍仅限既有 erratum 枚举 C02 known Job/raw identity/observation/rejection、C03 known prebirth/preload-parser/transport-rejection，并遵循单作者后独立 SPEC→不同 fresh QUALITY。whole C01 不完整、C02/C03 NOT_STARTED、C04–C12 STOP even SOURCE 保持。
VM_SERVICE_SCOPE_UNPROVEN / E_PHYSICAL_CAP_UNPROVEN / OWNER_EXIT_JOIN_UNPROVEN；PREPARED_UNREVIEWED / FROZEN_ADMISSION=None / 原 full FAIL / 全部准入阻塞保持。没有测试/本机探测/native/WSL/GT/Stage 或正式对象；Route2 无合法结果，科学与 F1≥0.66 目标保持。

### 2026-10-12 负责人三答复与有界下一步

[已绑定三答复](../../decisions/2026-09-27-route2-design-review.md#route2-three-mechanism-owner-decisions-20261012)：最终监督者可存活、应用执行组4tasks-threads、专用实体 extent 设计。仍须补齐监督者后续生命周期/计费、Windows 四 TID 出生硬界、whole RAM16/VRAM8 与全部基础设施计费、真实布局 creator/formatter/加载前及三层实际费用；不执行磁盘变更。
UTC16:31:10→16:37:10 一次只读公共原生资源机制复核，最多 HCS/Job 与物理包络两候选；实际部署不可行尚未证明，不假造 producer，不启动 C04–C12。原16:29:05收尾软目标已过，记录过期，不重置研究/准备/实验预算；当前继续原文档事实收据与版本留存。

<a id="route2-selected-mechanism-source-boundaries-20261012"></a>
### 2026-10-12 Exact next SOURCE slices and conditional later components

[Selected architecture](../../decisions/2026-09-27-route2-design-review.md#route2-selected-mechanism-architecture-20261012) supplies storage/coordinator/hardware callpoints, raw errors and fee boundaries. Plan C00 correction2238-2248 still overrides earlier broad eligibility. Current C00 AUDITED_UNPROVEN and wholeC01 incomplete do not release C04-C12; actual runtime/installed support remains UNKNOWN.
This author wrote DOCUMENT only. A later sole SOURCE author must first inspect only the approved relevant existing native/v2 declaration bodies, reconcile the exact existing signature/target map, and preserve v1 and refusal consumers. Targets below are bounded parts of the existing `native/route2_mount_helper.c/.h` Windows-seed/Linux-start interfaces; any different existing approved C02/C03 mapping must be reconciled before an edit, not guessed or used to create extra files/wiring.

| Eligible independent slice | Concrete source work / permitted native point | Explicit output/stop boundary |
| --- | --- | --- |
| C02-A known Windows Job capsule | Source for already audited CreateJobObjectW/SetInformationJobObject/AssignProcessToJobObject/query operations behind the explicit Windows-seed target; retain original returned Job/process handles and raw Win32 outcomes in existing v2/error declarations. | No call/compile/load now. Supported Job scope is only its actual process/commit/accounting scope. No HCS/service/hardware/physical-extent producer, four-TID claim, scope-success factory or runner wiring. Assignment/breakaway/invalid-handle failures preserve primary/secondary and reject. |
| C02-B raw original exit/observation and named refusal | Original process HANDLE WaitForSingleObject + GetExitCodeProcess and native QPC/frequency observation bodies; bounded raw observation serialization plus named missing-scope rejection. | Wait result/exit code/time are separate raw facts; timeout is not exit, PID/reopened identity not original, object construction not ownership. Never convert a successful child wait/Job query into whole service/owner/cap acceptance. |
| C03-A known prebirth capture only | Existing audited Windows-native QPC point before task Python/spawn and existing audited Linux-start pre-Python/pre-spawn clock/memory/status fields, with exact C01/v2 types and target/OS guards. | No postbirth substitute, inferred cost0, new unidentified creator/provider or native HCS/service call. A missing original owner/epoch/birth field emits its named rejection; no success handoff into bootstrap. |
| C03-B bounded preload parser | Read-only byte parsing of the approved PE/ELF/interpreter/stdlib/native/transitive-provider manifest and existing40-byte ABI contract: fixed version/length, checked sizes/offsets, bounded entries, exact target/architecture and rejection on unknown dependency. | SOURCE parsing only; no import/dlopen/constructor/link/preprocess/loader invocation, provider installation, success-fabricating attestation or guessed allowlist. Full actual closure remains UNPROVEN. |
| C03-C native transport rejection only | Parse bounded raw original-handle/epoch/identity/error transport using existing dormant v2 declarations; reject truncated/duplicate/reordered/unknown status and absent original provenance. | Do not add caller-created authority, registry-consuming state machine, scope receipt, success gate, bootstrap or consumer wiring. This slice cannot publish undefined primitive evidence. |

These are separate bounded components, not whole C02/C03 completion. Each needs sole author STOP ALL WRITES -> fresh scoped SPEC -> different fresh QUALITY; root then owns exact-path Git/preservation. Declaration compatibility and raw-error/once-close obligations are inspected as source, without running tests, reading test bodies, importing project code, compiling/linking/loading/calling, OS/WSL/GT probes or creating formal objects. Unknown exact declaration/path aborts that edit until its existing approved map is read.
Job active-process limit4 cannot implement application four HARD TIDs; process COMMIT cannot implement whole residentRAM16. Missing primitives must remain named refusals. No owner MONITORED answer has arrived; no source slice may reinterpret that cap. Actual source budget/fees and installation facts remain UNKNOWN_NOT_ZERO rather than certified by a source review.

| Conditional later mechanism component (NOT eligible SOURCE now) | Concrete implementation order when all C00 prerequisites are supported/selected | Evidence still required before eligibility/runtime |
| --- | --- | --- |
| Physical-capacity owner/creator/teardown | Held CreateFileW disk -> checked disk length/layout -> CREATE_DISK only separately selected new disk if needed -> approved SET_DRIVE_LAYOUT_EX -> exact MSFT_Volume.Format provider completion -> held actual GUID/extents/NTFS geometry -> dynamic CreateVirtualDisk/known attach/import -> full GetStorageDependencyInformation chain -> same-invocation actual L_C and guest-hosting free floors -> actual writer/service joins, flush/detach/delete/physical flush. | Exact chosen disk/geometry/rights and original layout trust, all raw/resize aliases closed for use interval, formatter/control16MiB feasibility, attach/registration/service signatures, actual overhead/history/fees, finite provider termination/cleanup. Design selection grants no disk action. |
| Final coordinator and service/VM exit join | Original creator GUID/HCS_SYSTEM and closed birth registry -> process/thread waits -> exact subscribed VM exit and operation result -> all original host services/callbacks/cleanup join -> physical cleanup -> q_exit_durable receipt/flush/readback -> all fallible once-close -> live q_accept_live/handoff -> readonly bounded tail/actual own exit. | Exact WSL GUID/handle and exit-event/callback transport, service ownership/join/deregistration signatures, native handoff and deadline enforcer, preload closure, original E control protocol, measured acceptance plus bounded actual tail billing. Disk receipt never masquerades as live postflush sample. |
| Whole-hardware capacity witness/billing composition | Native installed RAM checked KB*1024 -> DXCore factory and four separate hardware-attribute lists -> union original adapter identities -> supported size/property reads -> disjoint linked-member/capacity reconciliation -> stable no-hot-add interval -> bounded raw transport with original phase/actor billing. | Owner actual-host facts still PENDING; exact group/member capacities and required hardware-attribute support, preload/provider closure, trusted immutable topology, complete actor/cost identity. Enumerators witness hardware and cannot enforce memory allocations, thread4, commit or total GPU usage. |

Even after factual source signatures are supplied, all three necessary exact primitives must be supported and selected with concrete owner, OS callpoint, effective scope and failure/stop semantics, and C00 scoped reviews complete, before dependent C04-C12 SOURCE follows the original DAG. Native implementation review then still does not authorize runtime, preparation, disk mutation, WSL/GT, Stage A/B or formal image/volume/study/ledger/lock/freeze objects.
Installed facts, producer operation, original costs and actual scope are established only through a separately lawful bounded execution; this plan records required future evidence, not actual creator/enforcer deployment. NonE MONITORED contract, physical24/20/6 plus both8GiB floors, all elapsed/cleanup limits and scientific settings stay fixed.
Actual existing root Git receipts3709c43/9fb9bb1 were non-force pushed with feature/main/staged preservation verified; this new suffix has no new commit/review receipt. Original expired windows/16:29 close overrun remain recorded and do not reset budget. This component author deadline is UTC17:08:46.
PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED and VM_SERVICE_SCOPE_UNPROVEN/E_PHYSICAL_CAP_UNPROVEN/OWNER_EXIT_JOIN_UNPROVEN remain; C02/C03 NOT_STARTED, no lawful Route2 results, Route3 COMPLETE/fourFAIL no rerun, eventF1>=0.66 still open.
Author original working prefix422533 bytes/SHA256 c3c8be0e8cb0ee95ee34cd06e1efe7d8774ecce7410ecba70c0e833bf71e9fc2 is preserved by append. Actual all-write/all-read stop and suffix byte/hash receipts are measured and delivered to root before fresh SPEC/different QUALITY; both new scoped reviews are PENDING.

### 2026-10-12 Selected DOCUMENT execution-plan review receipt

[Root factual receipt](../../decisions/2026-09-27-route2-design-review.md#route2-selected-mechanism-review-receipt-20261012) binds actual author STOP and fresh independent SPEC -> different fresh QUALITY, both NO_REMAINING_SCOPED_P1_P2 / SELECTED_MECHANISM_DOCUMENT_REVIEW_ONLY. Selected114-line suffix committed29d98ca1b934282c4d745f01ba14e2068ffd9e5e, non-force pushed, remote feature/main and all11 full staged rows verified; this later receipt is not yet committed at writing time.
Next SOURCE eligibility remains exactly the preceding table plus C00 correction2238-2248: C02/C03 are NOT_STARTED; their already-known independent slices only, not whole mechanisms. C04-C12 STOP even SOURCE. Bound owner choices do not supply actual geometry/writer authority, native four-TID enforcement, whole actor billing, preload/creator or exit/deadline/handoff producers. Hardware facts and the NEW thread-policy reply remain PENDING; no default MONITORED selection.
Original17:12 close target elapsed before mandatory scoped review/retention/Git completion; no clock/resource reset. All unmeasured fees UNKNOWN_NOT_ZERO. No source/tests/import/native/WSL/helper/GT/probe/formal objects/disk operations. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/fullFAIL/blocked/notready/notauthorized remain; Route2 no legal results, Route3 COMPLETE/fourFAIL, eventF1>=0.66 still open.

### 2026-10-12：owner 硬件补充
见[硬件自述与策略待决](../../decisions/2026-09-27-route2-design-review.md#route2-owner-hardware-clarification-20261012)：本地 E + WSL 是偏好；RAM 16G、RTX 5060、独立显存 8G 为 OWNER_REPORTED / NOT_NATIVE_VERIFIED，原单位与名称保留。Windows 四 TIDs HARD 维持，用户未选择 MONITORED；policy/native proof 仍待决，原生 inventory/grouping、no-hot-add、prebirth billing、安装事实 UNKNOWN，成本 UNKNOWN_NOT_ZERO，原约束与阻断状态维持，未授权安装、磁盘变更或执行。

Factual closure: fresh independent SPEC then different fresh QUALITY both NO_REMAINING_SCOPED_P1_P2 / OWNER_FACT_DOCUMENT_ONLY, with author/reviewer stop receipts at the linked review anchor. OriginalSOURCE eligibility/blocked states and Windows four HARD TIDs remain; no native operation or installation follows. Root soft-close elapsed during mandatory review/Git preservation; fees UNKNOWN_NOT_ZERO, Git pending at writing time.

### 2026-10-12: Windows MONITORED execution-plan delta
- Owner "同意" approves [MONITORED + fixed-thread policy](../../decisions/2026-09-27-route2-design-review.md#route2-windows-thread-monitored-approved-20261012). Earlier Windows HARD4/PENDING sentences are superseded for BOTH prep/compile/ABI and external observer/helper/launcher/bridge/final-coordinator application groups; no native monitor is implemented by this plan.
- Four application TIDs groupwide includes monitor/loader/callback; infrastructure excluded from agreed application count remains billed. Linux tasks/pids HARD/studyTasksMax=2; prep4GiB/200%/1800, external512MiB/100%/6000/includedcleanup60; whole16GiB/8GiB, E24/20/6+double8, nonE512 MONITORED and science remain unchanged.
- Trusted original owner must retain creator-issued process HANDLE/PID/creation time membership and QPC epoch before birth, and fixed preloaded observer must belong to its counted/billed group. Real membership/phase transitions and bounded before/after identity/liveness snapshots throughout setup/application/drain/seal/tail are required producers, not caller fields or PID reopen.
- >4 or incomplete/failed/stale observation latches STOP_NEW, blocking new births/fit/decode/GT grants; original drain/revoke/wait/cleanup only within original deadlines and costs, retaining primary+cleanup failures. No blind retry/reset/resume/science-complete inference; missing liveness/coverage/deadline/fees refuses.
- User accepts pre-detection overshoot; peak/duration/bound UNKNOWN and observed max only lower evidence, never HARD4 proof. Poll/entry/work bounds, actual loading/membership/stop producer remain UNKNOWN. Use linked raw Toolhelp contract and limitations without new numeric caps, APIs or producer claims.
- After this bounded DOCUMENT delta has fresh independent SPEC then DIFFERENT fresh QUALITY, next action is only independent C02 already-known original native identity/observation/named-rejection SOURCE slice; this is not wholeC02/C03 or all three production primitives.
- BEFORE any SOURCE edit, read/reconcile exact C00/C01 native Windows target/symbol/map against eligibility correction2238-2248. Any newly needed Toolhelp binding requires its narrow SOURCE API audit if not already approved; undefined producers need named refusals, not declarations masquerading as authority or runner wiring.
- C00 AUDITED_UNPROVEN/wholeC01 incomplete/C02C03 NOT_STARTED/dependentC04-C12 STOP even SOURCE persist; physical capacity/complete billing/exact WSL GUID service exit/final durable handoff UNPROVEN. No compile/link/load/call/native/WSL/GT/installation/disk/Stage authorization.
- PREPARED_UNREVIEWED/FrozenNone/fullFAIL/blocked/notready/notauthorized/Stagezero, Route3 COMPLETE/fourFAIL and F1open persist. Original envelopes/charges retained; author UTC/prefix/hash/STOP receipt goes to root before new reviews; no review/Git/runtime PASS is invented.

Scoped P2 override for the approved Windows MONITORED contract:
Active original membership requires live held original identity before and after each snapshot; this does not require all previously admitted actors to remain alive throughout drain/seal/tail.
JOINED_EXITED membership requires retained original creator identity, native exit with approved status, original join/once-close history and final billing; exclude it from the CURRENT active-TID count only after the actual original exit/join producer, retain all historical fees, never reopen closed handles to reconstruct identity, and keep counting surviving monitor/coordinator TIDs in their application group.
An exit racing the snapshot, missing original join/history/final fees or unclassified membership means UNKNOWN/STOP_NEW, never zero/PASS or an assumed normal joined exit; native producers remain UNKNOWN and all prior policy, budget, science, permission and blocked states persist.

Root closure: current policy+P2override passed scoped independent SPEC then different fresh QUALITY, NO_REMAINING_SCOPED_P1_P2 / APPROVED_MONITORED_POLICY_DOCUMENT_ONLY. Actualauthor/review clocks and32s author/outer-soft-close overruns are retained at the linked review anchor, notbudgetPASS/reset. Next onlyC02independent SOURCEafterexactexistingtarget/symbol/APIaudit; no nativeobserver/runtime/completeprimitives proved and C04-C12STOPevenSOURCE/Stageblocked persist. Originalcaps/science and UNKNOWN_NOT_ZERO fees unchanged; Git pending at writing.

### C02-B1 exact existing target and API ledger (SOURCE only)

This narrow ledger precedes C02-B1 native source edits. Actual implementer START is 2026-10-13 02:02:07 UTC; ALL_READ_WRITE_STOP is due no later than 02:22:07 UTC. Earlier root/preparation/research/experiment budgets are not reset; charges remain UNKNOWN_NOT_ZERO. The approved Windows MONITORED4 policy and its P2 override are already selected.

Only existing package-relative `src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c` and `.h` supply this component under existing `R2_TARGET_WINDOWS_SEED`. Exactly-one-target/wrong-OS guards remain; no new source file, target, wrapper, loader, registry or seed/start entry body is introduced. LinuxStart remains dormant; LinuxMountLibrary v1 bodies/40-byte ABI and C01 enum/struct/four future declarations remain byte-preserved. The new Windows body requires explicit SDK target `_WIN32_WINNT >= 0x0600`, SDK `Windows.h`, and C11; actual installed SDK/compiler/architecture/link/loader remains UNKNOWN.

Actual selected source functions are `route2_win_raw_process_observe_v1(uintptr_t, struct r2_win_raw_process_observation_v1 *, size_t)`, `route2_win_refuse_vm_service_scope_v1(void)`, `route2_win_refuse_e_physical_cap_v1(void)`, and `route2_win_refuse_owner_exit_join_v1(void)`. Separate `R2_WIN_RAW_*` statuses describe raw sample outcomes only; the three refusal bodies return existing named `r2_scope_result` UNPROVEN values, never R2_SCOPE_PROVEN. No scope-success factory exists.

| Actual SDK API / exact signature | C02-B1 callpoint and raw failure contract | Primary declaration |
|---|---|---|
| `DWORD GetProcessId(HANDLE)` | Validate borrowed input as a process before any duplication/wait, then query the successful owned duplicate; zero immediately captures all 32 GetLastError bits. Compare both kernel PIDs. No OpenProcess/by-PID reconstruction. | https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessid |
| `HANDLE GetCurrentProcess(void)` | Current-process pseudo container for DuplicateHandle only; do not close it. NULL and INVALID_HANDLE_VALUE/current-process pseudo inputs are explicit argument rejection. Other unsupported pseudo/object inputs reach pre-duplicate GetProcessId failure, preserving its actual error. | https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getcurrentprocess |
| `BOOL DuplicateHandle(HANDLE,HANDLE,HANDLE,LPHANDLE,DWORD,BOOL,DWORD)` | Same-process containers, FALSE inheritance, DUPLICATE_SAME_ACCESS only; never DUPLICATE_CLOSE_SOURCE. Caller keeps borrowed real handle open/stable through successful local duplication. Failed out-parameter is undefined and never owned/closed. | https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle |
| `DWORD WaitForSingleObject(HANDLE,DWORD)` | Two zero-time process polls only after type validation, with SYNCHRONIZE rights. WAIT_TIMEOUT means nonsignaled at that poll; WAIT_OBJECT_0 is actual exit signal. WAIT_FAILED captures immediate GetLastError; any other result is a synthetic invariant fault with no guessed error. | https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject |
| `BOOL GetProcessTimes(HANDLE,LPFILETIME,LPFILETIME,LPFILETIME,LPFILETIME)` | Actual creation/kernel/user raw 100ns units with query information or limited-query rights. Live exit FILETIME is undefined and never read/promoted. Initial nonsignal then signal requires fresh times and consistent creation identity; CPU is this process/all its threads only. | https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes |
| `BOOL GetExitCodeProcess(HANDLE,LPDWORD)` | Only after actual owned-duplicate signal; retain all DWORD values including 259. Signal is the exit witness. No exit approval, original join or whole-group claim. | https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess |
| `BOOL QueryPerformanceFrequency(LARGE_INTEGER *)` | Raw positive signed64 frequency, outside the begin/end sample window; failure immediately captures GetLastError. | https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancefrequency |
| `BOOL QueryPerformanceCounter(LARGE_INTEGER *)` | Raw opaque signed64 begin/end ticks, endpoint after once-close; documented FALSE captures immediate GetLastError. Check endpoint monotonicity only when both calls succeeded. No unsupported conversion/new t0/M0/whole billing. | https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter |
| `BOOL CloseHandle(HANDLE)` | Successful private duplicate receives exactly one local close attempt on every later path. Close failure is retained after primary query fault and poisons result, with no retry; caller original is never closed. | https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle |

Windows.h supplies actual Win32 types/constants and Kernel32.lib/Kernel32.dll bindings; no guessed declarations/types/syscall numbers or POSIX fallback are supplied. Parent's bounded Context7 resolve/two concept queries were partly off target; the exact Microsoft primary pages above supplied this narrow binding audit. No new broad research/API family is opened.

Bounded output is an exact-size native memory record, with explicit UNKNOWN/VALID/FAILED state for each raw value, duplicate/close states, before/after wait codes, borrowed/duplicated PID, creation/CPU/defined exit FILETIME facts, exit code, QPC frequency/endpoints, sample classification and at most three ordered faults (one primary query/invariant, once-close, endpoint). Output parameters are copied only after API success. Failures retain earlier valid facts. LIVE_AT_BOTH_POLLS asserts only two polls; EXITED_BEFORE_FIRST_POLL supplies a raw signaled exit; EXITED_BETWEEN_POLLS remains EXIT_RACED/incomplete/STOP_NEW. None certifies creator membership, continuous or after-return life, native original join/once-close history, final fees or MONITORED4 admission.

This is C02-B1 only, pending actual implementation and fresh scoped SPEC then DIFFERENT fresh QUALITY after sole-author STOP. C00 AUDITED_UNPROVEN, whole C01 incomplete, whole C02 incomplete, C03 NOT_STARTED and C04-C12 STOP even SOURCE persist. Physical extents/all writers/complete billing/exact WSL GUID service exit/final durable handoff remain UNPROVEN. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/full FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stage zero, Route3 COMPLETE/four FAIL and F1 open persist. Original caps/science and UNKNOWN_NOT_ZERO fees remain unchanged. No tests/test-body reads/project imports/preprocess/compile/link/load/call/native/OS/WSL/GT probes/install/disks/formal image/volume/study/ledger/lock/freeze or Git mutation is authorized here.

### C02-B1 sole-author component checkpoint (SOURCE only; fresh reviews pending)

C02-B1 now has actual Windows-only function bodies in the two existing package-relative native files. Sole implementer START: 2026-10-13 02:02:07 UTC. Native edits and first isolated static preservation/hash inspection finished by actual clock 02:12:42 UTC; final ALL_READ_WRITE_STOP and all five final file hashes are returned to root after the final append/hash receipt, with a hard deadline of 02:22:07 UTC. This is DONE_WITH_CONCERNS / IMPLEMENTED_BUT_UNCOMPILED, never fresh SPEC/QUALITY or runtime PASS. Ledger transfer initially rejected an apostrophe in JavaScript before any shell call; that failed transport made zero writes, and the bounded literal transfer then appended successfully.

Actual source functions are `route2_win_raw_process_observe_v1`, `route2_win_refuse_vm_service_scope_v1`, `route2_win_refuse_e_physical_cap_v1` and `route2_win_refuse_owner_exit_join_v1`; the [preceding exact ledger](#c02-b1-exact-existing-target-and-api-ledger-source-only) records their signatures, existing target and SDK API sources. The three refusal bodies return only existing R2_VM_SERVICE_SCOPE_UNPROVEN / R2_E_PHYSICAL_CAP_UNPROVEN / R2_OWNER_EXIT_JOIN_UNPROVEN. Separate R2_WIN_RAW_SAMPLE_COMPLETE is raw observation completeness only, with a distinct enum/namespace; no producer emits R2_SCOPE_PROVEN.

| Actual observer output / path | Source semantics and limitation |
|---|---|
| ABI/size, status, sample_kind; duplicate_state/close_state | Caller must supply exact sizeof native record and real uintptr_t process HANDLE, keep borrowed handle stable/open through local duplication, and exclusively retain output through return. A wrong output pointer/size returns BAD_ARGUMENT without writing; valid output begins UNKNOWN. NULL/current-process/INVALID_HANDLE_VALUE is explicit BAD_ARGUMENT without a native error. Other invalid/unsupported object/pseudo input retains actual pre-duplicate GetProcessId failure. No issuer/creator provenance is inferred. |
| borrowed_pid / duplicate_pid | Actual native GetProcessId on borrowed input precedes DuplicateHandle and any wait; GetProcessId on successful owned duplicate plus equality checks raw process identity. No OpenProcess/reopen-by-PID/type-guess wait, thread/token pseudo API or guessed sentinel range. |
| private duplicate and close | Current-process containers, inheritance FALSE and DUPLICATE_SAME_ACCESS only. Failed DuplicateHandle output is undefined and never owned/closed. Every successful duplicate follows one common once-close attempt on every later path; caller/container is never closed. Close failure remains explicit FAILED/raw fault, poisons completion and may leave a resource unclosed; no retry or manufactured cleanup history. |
| wait_before / wait_after | Exactly two zero-time WaitForSingleObject calls on validated owned process only. Timeout states nonsignal at that poll; signal is the native exit witness. WAIT_FAILED captures immediate DWORD GetLastError; unexpected status/signal regression is synthetic, with no stale/guessed native error. No uninterrupted/after-return or group liveness is inferred. |
| creation_before/after_100ns, kernel_cpu_before/after_100ns, user_cpu_before/after_100ns, exit_filetime_100ns, exit_code | GetProcessTimes outputs are copied only on success. Initial nonsignal never reads/promotes undefined exit FILETIME. Nonsignal then signal obtains fresh defined times and creation equality, then GetExitCodeProcess after actual signal. Exit code 259 retains all DWORD bits and does not revive the process. Live two-poll result leaves exit facts UNKNOWN. Before/after CPU values are separate raw observations; CPU covers this process/all its threads only and is never summed with thread CPU or whole infrastructure fees. |
| qpc_frequency / qpc_begin / qpc_end | Each has UNKNOWN/VALID/FAILED state; raw signed64 positive frequency is queried before begin. End occurs after owned once-close attempt, with monotonic endpoint check when both succeeded. API FALSE uses documented immediate GetLastError. Earlier frequency/startup/all historical fees are outside this window; no FILETIME/QPC unit conversion or new t0/M0/wall-budget witness is asserted. |
| faults[3] / fault_count | A primary query/synthetic failure ends further process queries; common cleanup can add one close fault then one endpoint API/invariant fault. These paths fit exactly three ordered slots and preserve the primary status, all 32 error bits (including raw zero), synthetic/native distinction and all earlier valid facts. No failed API output parameter is promoted. |
| sample_kind and separate raw status | LIVE_AT_BOTH_POLLS means only two polls; EXITED_BEFORE_FIRST_POLL is already signaled raw exit. EXITED_BETWEEN_POLLS returns EXIT_RACED/incomplete/STOP_NEW even when defined exit/code facts were obtained. Query/close/end faults prevent complete status. Original exit approval, native original join/once-close history, historical membership and final fees stay UNKNOWN. |

Static self-review read actual complete C/H, then clarified the shared scope-name comment and separated the exit-code local from PID. Isolated `python -I -S -B` stdlib source/hash inspection exited 0; this was no C preprocess/syntax compiler/build/test/native call. Raw preservation outputs: Linux v1 body exactly 1300 bytes / SHA256 `86b59f0ac8a610b56a47f5ab563e931e88b0fdab8f69c4ee0a52fa38246d53be`; original v1 ABI declaration exactly 313 bytes / `8a48210be5d34d864f63150d1a8272d6e86777e0ea0d1642961a852630199ccf`; C01 enum/struct/four future declarations exactly 1699 bytes / `77ed181ebe412209e4737a82d128b825bd0a8b3f764d8252c9e9013e82301287`. Existing exactly-one-target/OS and Linux SDK/UAPI guards were byte-exact. Public component body/declaration counts were each C=1/H=1. Windows source API-site counts: GetProcessId=2, GetCurrentProcess=1, DuplicateHandle=1, WaitForSingleObject=2, GetProcessTimes=2, GetExitCodeProcess=1, QueryPerformanceFrequency=1, QueryPerformanceCounter=2, CloseHandle=1, immediate GetLastError=12.

Native files at this checkpoint: C 17574 bytes / 392 lines / SHA256 `351eaa16c3394102530c9d2c3d085daaf3e84c1b23cfbd8050a2ed2611e7112b`; H 8584 bytes / 217 lines / `a60683ab57ce9293448d1b6951c903b7bcbad0c3057ed12c1eb5df89692d2e63`. Original three document prefixes remain exact: review 638154 bytes / `32811f21ce386a24c836b73b4ede7f8ef28902ba590d6614bcdd7cac3b7d2754`; spec 361732 / `87c523c5add58f99a721754832d461eb1f29dd201647db44d8c630081996c5e6`; plan 437993 / `05b32743c53867cd5dfa499c90112c3e913f1ceef76634f6ac19b230b70a0d39`. Append-only suffixes preserve mixed/newline raw prefixes.

Next checkpoint is sole-author ALL_READ_WRITE_STOP -> fresh scoped SPEC -> DIFFERENT fresh QUALITY, then root-owned exact-path Git/preservation. Author supplies no review verdict or Git receipt. No other native source/target/file/wrapper/registry/Job caps/Toolhelp loop/seed-start body/future stack or Python consumer changes were made. Existing _prepare_fixed_worker / _require_host_control_boundary and all refusal consumers remain untouched. Complete controllers/seed/full-scope producers and monitor loop/cohort completeness/phase ownership remain NOT_IMPLEMENTED.

Narrow SOURCE card delta only: C02-B1 raw component IMPLEMENTED_BUT_UNCOMPILED; whole C02 incomplete, whole C01 incomplete, C00 AUDITED_UNPROVEN, C03 NOT_STARTED, C04-C12 STOP even SOURCE. VM/service physical extents/all writers/whole billing/exact WSL GUID service exit/final durable handoff remain UNPROVEN. Windows MONITORED4 with P2 exit override and Linux hard semantics/all original caps/budgets/science stay unchanged. PREPARED_UNREVIEWED/FROZEN_ADMISSION=None/full FAIL/APPLICATION_BLOCKED/NOT_APPROVAL_READY/NOT_EXPERIMENT_AUTHORIZED/Stage zero, Route3 COMPLETE/four FAIL and F1 open persist. Installed SDK/architecture/compiler/link/loader/runtime and earlier/all fees remain UNKNOWN / UNKNOWN_NOT_ZERO. No tests/test-body reads/project imports/preprocess/compile/link/load/call/helper/OS/WSL/GT probes/install/disks/formal image/volume/study/ledger/lock/freeze or Git mutation occurred.

### C02-B1 independent SOURCE review closure (UTC 2026-10-13)

Root records this administrative receipt at 2026-10-13 02:33:50 UTC, after the sole author and both reviewers stopped all reads/writes. Author START 02:02:07, STOP 02:16:40 UTC (873 seconds, within its 20-minute component limit). Fresh independent SPEC /root/c02_b1_spec_review: 02:20:55 -> 02:24:41 UTC (226 seconds). DIFFERENT fresh independent QUALITY /root/c02_b1_quality_review: 02:27:02 -> 02:30:43 UTC (221 seconds). Both finished within their six-minute limits and returned NO_REMAINING_SCOPED_P1_P2 / SOURCE_ONLY. No repair was requested. Their verdicts cover the exact two native sources and author checkpoint suffixes; this later factual receipt does not expand that scope or issue a full-review ID.

Reviewed source remains C 17574 bytes/392 lines, SHA256 351eaa16c3394102530c9d2c3d085daaf3e84c1b23cfbd8050a2ed2611e7112b; H 8584 bytes/217 lines, SHA256 a60683ab57ce9293448d1b6951c903b7bcbad0c3057ed12c1eb5df89692d2e63. Both reviewers independently recomputed all five author-checkpoint file hashes. The [preceding exact target/API ledger](#c02-b1-exact-existing-target-and-api-ledger-source-only) records the actual existing Windows target, selected signatures/rights/units/failure semantics; it is a public-document binding audit, not verification of installed SDK or executable ABI.

Root isolated stdlib byte/hash inspections confirmed the same 403 Git-listed project-file set, no additions/deletions, only the exact two native files plus original three append-only documents changed, full original eleven mode/blob/stage/path identities and initial index preserved, unchanged main dd05aa128f8d62a85c20a83f8af72fe13fcfa27b and feature branch. The original authorization prompt/card, GT source pins and all unrelated dirty/staged/untracked bytes remain unchanged. Linux v1 guarded regions are byte-exact (C SHA b402ca4b2f801368e4e2dfc07b3c13be29256867ce3828f91aa6e6df71f58ab7; H SHA 0c742a1cf6da01167e0e8ef9c942563dea78e5d525f2c5aa23187a1f5b3844ed). C01 enum through final future declaration is exactly 1695 bytes/SHA 7112aa7f74704efbdb0567595b6345fa8d5131fd543e318685bef642b20efbca. An initial root fixed-offset comparison reported false because the allowed preceding comment changed its offset; matching the actual block anchors confirmed preservation. This was a static inspection correction, with no source mutation or runtime attempt.

C02-B1 is SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED. It supplies raw process facts through a private duplicate and the three named UNPROVEN bodies; it supplies no creator/cohort authority, active registry, four-thread monitor/interval/stop producer, approved exit/join/history/final billing, full controller or consumer installation. C00 AUDITED_UNPROVEN; whole C01/C02 incomplete; C03 NOT_STARTED; dependent C04-C12 STOP even SOURCE. Further work is limited to the already enumerated independent C01-C03 portions under the C00 eligibility table; there is no automatic dependent-stack continuation.

The existing complete A+B fourteen-item card in [original review section 4.9](../../decisions/2026-09-27-route2-design-review.md) receives only this SOURCE progress delta. Actual physical extent/all-writer capacity boundaries, three-layer baseline/capacity/headroom and complete costs, pre-Python/pre-spawn original t0/M0 and authenticated Windows QPC startup continuity, pre-load readonly PE/ELF/interpreter/stdlib/project/native/transitive closure, GT role grants/revokes and complete nested equivalence, terminal/raw-cgroup/VM/service exit and durable final acceptance, full formal review and complete source/runtime/input/protocol/budget freeze remain unproven. The already approved Windows application-group MONITORED4/fixed-thread policy and accepted UNKNOWN overshoot supersede old Windows HARD4 wording; infrastructure remains completely billed, Linux hard limits and other original caps remain. Dedicated physical extent is selected DESIGN only. The trusted external final coordinator may survive acceptance only under the already bounded/billed tail; this raw sampler does not prove that acceptance. No second card or handoff is created.

PREPARED_UNREVIEWED; FROZEN_ADMISSION=None; route2-ab-full-implementation-review-2026-09-29-FAIL-001 remains FAIL; APPLICATION_BLOCKED / NOT_APPROVAL_READY / NOT_EXPERIMENT_AUTHORIZED. Stage A/B legal runs/results remain zero. Route3 v1-003 remains legitimate COMPLETE/four quality gates FAIL; no rerun/model branches. Fixed scientific protocol, final matched-GT real gain/loss requirement and deep-learning event F1>=0.66 objective remain unchanged/open. Native compiler/SDK/architecture/binary ABI/load/runtime remain UNKNOWN. All historic/current/future charges remain UNKNOWN_NOT_ZERO; component/root source-work clocks do not reset original preparation/experiment deadlines.

Inspection was isolated stdlib raw text/hash, not a test or C syntax check: two native files, zero Python AST targets in this slice. No tests/test-body interpretation/project imports/preprocess/compile/link/load/native/helper/OS/WSL/GT probes or formal objects occurred. Git whitespace inspection exited 0; current hooks contain samples only, text conversion is unset and filters/encoding are unspecified for the exact five paths. Root-owned exact-path commits/non-force push and final preservation/remote receipts follow; none is preclaimed here.

### C02-B1 exact-path Git receipt

At actual 2026-10-13 02:38:44 UTC, root verified component commit bfdee835e23183eefee66c24c5b8fbaf13acb096 (parent 486bde715f0c8f5eecfebe7375e368ba304a2e09), message "feat(route2): add reviewed C02 raw process observation slice". Its complete tree diff contains only the existing native C/H and original three documents. Each committed blob matches its actual reviewed source or later administrative document bytes. Exact-path git add and git commit --only preserved all original eleven complete staged identities and restored the original staged path set; unrelated index entries remained byte-identical. No reset/stash/force/merge/pull/main mutation occurred.

The non-force push to https://github.com/Lancercodermaker/Bme_Eating_Detection.git feature branch codex/high-f1-event-stack-execution exited 0. Subsequent git ls-remote independently returned feature HEAD bfdee835e23183eefee66c24c5b8fbaf13acb096; remote main remains dd05aa128f8d62a85c20a83f8af72fe13fcfa27b. Root then rehashed the same 403 project-file set: no additions/deletions and no unrelated file changes. Original authorization prompt/card, GT pins, dirty/staged/untracked content and source-review hashes are preserved. The source review receipts above remain narrow SOURCE only.

This factual three-document receipt is a separate small commit; its own identity/final remote confirmation is obtained from Git and the final report, rather than self-embedded. No new source behavior, review scope, decisions, authorization card, freeze or handoff is introduced. C02-B1 SOURCE_REVIEWED / IMPLEMENTED_BUT_UNCOMPILED, whole C01/C02 incomplete/C00 AUDITED_UNPROVEN/C03 NOT_STARTED/C04-C12 STOP even SOURCE and all original full FAIL/admission blocks/Stage-zero/F1-open states remain. All fees remain UNKNOWN_NOT_ZERO. Root source-work first clock 2026-10-13 01:44:05 UTC and soft close 02:54:05 UTC remain in force; author/reviewer clocks above describe overlapping SOURCE work, not a new runtime budget or additive wall charge.
