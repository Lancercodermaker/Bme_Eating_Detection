# M1 执行与门禁记录

用户于 2026-09-06 明确授权启动 M1；旧文档的“等待授权”状态由此覆盖。
仅使用现有 `codex/smartwatch-eating-baseline` worktree，不合并、不 push、不启动 M2/M3/M4。

## Preflight

- 起点 HEAD：`7c7d2ee5123cce9173474a1da1fec3eefb6b089a`；工作区干净，已确认 linked worktree。
- 完整读取 handoff、冻结设计、原实施计划和 README。
- `artifacts/final_m0/split_manifest.json` 与最终 q50 artifact 的 split 内容一致。
- train 34 participant / 954 sensor txt；val 8 participant / 201 sensor txt。
- train：hnu21001, hnu21002, hnu21003, hnu21004, hnu21005, hnu21007, hnu21008, hnu21009, hnu21010, hnu21012, hnu21013, hnu21014, hnu21018, hnu21019, hnu21021, hnu21022, hnu21023, hnu21025, hnu21026, hnu21026j, hnu21027, hnu21028, hnu21029, hnu21031, hnu21032, hnu21033, hnu21034, hnu21035, hnu21036, hnu21037, hnu21038, hnu21039, hnu21040, hnu21041。
- val：hnu21006, hnu21011, hnu21015, hnu21016, hnu21017, hnu21024, hnu21042, hnu212020。
- excluded_test：ac3 / test；只枚举文件名，分别 0 / 2 sensor txt，不读取标签。
- 原始数据 Git 跟踪为空；cache/artifacts/checkpoints/outputs 的具体文件探针均被忽略。
- 环境：`C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe`，Python 3.11.16，PyTorch 2.11.0+cu128，CUDA 12.8，RTX 5060 Laptop。
- 既有 CUDA 两步训练验证通过；基线 pytest 72 passed。
- M0 artifact `artifacts/m0_final_q50_group_e3/` 存在；不重训 M0。

## 解析子阶段

事实：M0 已有显式 IMU-only 投影，原始 PPG 行质量语义为正 timestamp、44 通道全部 finite、非全零。
风险：复用全模态 parser 会不必要转换 IMU；缺列可能报错或被误认为有效零值。
候选：扩展 M0 parser，或独立 PPG-only parser。
验收：只读取 PPG，保留旧行 mask 等价性，缺列显式无效，重复表头与 bounded rows 可测试。
选择：独立 `iter_ppg_chunks`；M0 路径保持原实现。
实验：9 项 RED（缺少函数）→ 13 项 IO GREEN → 全套 81 passed，compileall/diff check 通过；提交 `d05665f`。独立审查发现缺少整条 PPG stream 时抛错；追加 2 项 RED 后改为显式空/无效流。全套 83 passed，规格与质量审查通过；提交 `47f2f41`。两个真实文件各 2,000 行与旧 parser 时间戳/波形/mask 完全等价，有效行分别为 450 和 435。

M0 只读复评重新计算 TP/FP/FN=21/171/30，Precision=0.109375，Recall=0.4117647058823529，F1=0.17283950617283952，start/end MAE=639946.0238095239/71945.45238095238 ms；与保存指标逐项相等。原始文件 metadata 基线共 2,378 项，保存于忽略的 `artifacts/m1_preflight/`。M0 cache 清点为 train 929、val 192，合计 3,578,835 windows、268,791,286 time samples。PPG 数组磁盘估计约 51 GB，可用空间约 1.17 TB。

## PPG cache 契约（待 TDD 实现与验证）

- 独立 `cache/m1_ppg/`，独立 schema/modality 指纹；绝不修改既有 IMU cache。
- 每文件连续 `(45,T)` float32：44 波形 + 1 row quality；另存 `(1,T)` bool quality、int64 时间轴/窗口索引/窗口边界、float32 soft label、bool loss mask。
- 保留 44 通道定义和既有 all-finite/nonzero 行 mask；额外平坦质量检查必须显式记录，不能伪装成原 parser 等价语义。
- 先对 PPG timestamp 稳定去重聚合，再恢复统一网格，再抗混叠重采样。无效波形置零且质量为 false。
- 通过显式目标时间轴契约对齐 M0 窗口；对齐信息纳入 key，不能按窗口序号盲拼。
- 原始波形 cache 与训练集拟合的标准化统计分离；统计只用 train 有效样本，val 复用。
- key 包括源路径/size/mtime、采样率/max_gap、预处理变体、窗口/标签配置和区间、modality/channel/schema、显式对齐范围；hit 只 stat 源文件，不打开 CSV。
- 临时文件写入成功后原子改名；逐文件恢复；batch 切片，不保存重叠窗口 clone。
- `flat_policy` 默认 `reject_constant_stream`：至少两条有效 canonical row 在 44 个通道均精确恒定时，整条流质量为 false；仅显式传入 `keep` 才保留非零常量流。没有推断幅度阈值。
- 降采样质量同时追踪抗混叠滤波的输入支持；若无效行会改变输出样本，则该样本质量为 false 且 44 个波形通道置零，不能被点位质量检查误标为有效。

## PPG cache 审查与验收（2026-09-06）

事实：独立规格审查确认 `ppg/` 命名空间、45×T float32（44 波形 + 质量）和独立 bool quality array；reference grid hash、源 path/size/mtime、采样率、窗口/标签、schema 与预处理均进入 key。初始实现的非零常量流默认保留，且 100 Hz 的单个无效点在 25 Hz 抗混叠后会改变相邻波形但仍被标为有效。

风险：前者与冻结的“平坦 PPG 必须有质量 mask”不一致；后者会把由无效包污染的输入交给 M1 encoder。候选是保留旧默认，或以无阈值的精确常量规则默认拒绝，并把滤波支持传播进 quality。

验收标准：新回归测试须先失败；默认平坦流无效但显式 `keep` 可回退；所有受无效点影响的降采样输出为零/无效，同时远离该点的输出保留有效。现有 timestamp/window/label/ignore、partial(43列)、key、atomic/recovery、lazy 与 cache-hit 禁止 CSV 测试不得回归。

选择：默认 `reject_constant_stream`，保留显式 `keep`；以 resample 后 availability 对 all-valid support 的数值比较传播滤波影响，不改 IMU cache 或 M0 的 `resample_uniform` 默认行为。

实验：两项新增测试 RED（默认平坦流仍有效；无效点影响的输出仍为有效）→ 最小实现 GREEN。PPG cache 专项 27 passed；全套 110 passed；compileall 与 diff check 通过。两个真实文件各 2,000 行，在 soft/ignore 下都与 M0 25 Hz reference 的 timestamps/window indices/window boundaries/labels/loss mask 完全相等；hnu21013 quality coverage=0.65158、hnu21024=0.31050。每个 cache miss 后，替换 PPG reader 为抛错函数的 lazy hit 仍成功，未打开原始 CSV。M0 冻结概率只读复评保持 TP/FP/FN=21/171/30、F1=0.17283950617283952。

## M1 模型核心（2026-09-06）

事实：M0 的 `IMUCNN` 与新的独立 M1 temporal encoder 不具有完全相同的 module/state_dict 结构，不能静默迁移。M1 PPG 输入固定为 45 channels（44 波形 + 逐点 quality），但逐点 quality 不能替代窗口级模态可观测性。

风险：仅以零值表示缺失会让 Conv bias/normalization 产生看似有效的 embedding；独立地随机丢弃两个模态会出现双模态都不可用的训练样本；把 sigmoid 放在 loss 前会违背数值稳定的 BCE 契约。

选择：`IMUPPGFusion` 使用独立 GroupNorm temporal encoder，embedding 级 gated fusion，并把 `(B,2)` modality mask 同时用于分支输入、embedding 和分类 head。训练 dropout 只在两个模态都可用时随机屏蔽其中一个；eval 不随机屏蔽。`load_compatible_imu_encoder_from_m0` 仅在完整 key/shape 相等时加载，否则 fail closed；默认不调用它。`train_m1_one_batch` 直接将 logits 和 `[0,1]` target 传给 `BCEWithLogitsLoss`。

实验：8 项 RED（缺少 fusion/model batch 接口）→ GREEN：独立分支 shape、无效 PPG 的不同数值在 modality mask=false 时输出一致、单/双缺模态 finite、训练期安全 dropout、eval 确定性、M0 不兼容拒绝、CPU logits BCE backward 与 CUDA forward/backward。专项 8 passed；全套 118 passed；compileall/diff check 通过；`verify_environment.py --require-cuda --steps 2` 新鲜通过（PyTorch 2.11.0+cu128、CUDA 12.8、RTX 5060 Laptop）。尚未创建 paired cache Dataset/CLI 或进行 M1/PPG-only 训练。

## M1 配对 cache 与 PPG 标准化（2026-09-06）

事实：IMU 与 PPG cache 即使使用同一文件名，也可能因不同的 reference grid、窗口边界或 soft label 而错位；lazy cache 为节省内存不把 timestamps 常驻。PPG 的 44 个波形 channel 与最后一个 point-quality channel 也不能一并标准化。

风险：按 cache/window 序号盲拼会静默训练到错误标签；只在 non-lazy cache 验证 timestamps 会让真实训练路径绕过 M0 reference grid 约束；把验证 participant 或 invalid PPG 值加入统计会泄漏并把 placeholder 零值变成伪信号。

选择：`PairedCachedWindowDataset` 以解析后的 source path 一一配对并强制 participant、timestamps、window index/start/end、window label、loss mask 相等；lazy 时仅从各 `.npz` 读出 timestamps array 作一次性验证，不加载 feature arrays。每窗根据各 cache point-quality 的非零覆盖派生 `(IMU, PPG)` modality mask，窗口仍保留。`fit_m1_ppg_standardizer` 仅扫描训练 participant 的 44-channel 有效 PPG 点；`standardize_m1_ppg_batch` 保留第45个 quality channel，并在缩放后把所有 invalid waveform 值复位为零。

实验：5 项 RED（缺少 paired Dataset/PPG standardizer 接口）→ GREEN；再以延迟加载 cache 的篡改 timestamps 回归测试确认实际训练路径也拒绝错 reference grid。专项 6 passed；全套 124 passed；compileall/diff check 通过。尚未运行 PPG-only 或融合训练、也尚未接入 CLI。

## M1 cache-hit batch training（2026-09-06）

事实：M1 必须在同一 participant split 的配对 cache 上训练；PPG-only 是诊断，不应另造隐式拼接模型，也不得通过遗漏 PPG 窗口改变 label 分布。test cache 若意外传入训练函数会破坏冻结 split。

风险：训练期重读 CSV、将 validation 统计带入 PPG 标准化、或仅在调用 CLI 时过滤 test 都会造成不可复现或泄漏。单独的 PPG-only 训练若仍留下 IMU mask=true，会不再是诊断性对照。

选择：新增 `fit_m1_cached`，接受已配对 IMU/PPG caches，先拒绝 train/val 外 cache participant 及 split manifest 中 excluded test participant，再构造 participant/file batch。IMU/PPG 统计和 `pos_weight` 均只来自训练 participant。`ppg_only` 只把 IMU modality mask 置零；`fusion` 传递原始 mask。两个模式都复用 batch BCE logits、验证集 decoder、严格 IoU 事件评价、checkpoint/probability 输出，并分别记录 IMU/PPG cache 命中/CPU 时间、GPU 与 epoch 时间、train/val modality coverage。验证概率按唯一 `(participant,start,end)` 与 cache label 回配，输出二元 membership 与 soft overlap target 的 Brier/ECE/reliability bins。

实验：两项 RED（训练入口不存在）→ GREEN：lazy cache 的 PPG-only end-to-end CPU batch 在 reader 被替换为抛错函数时仍完成，写出 checkpoint、双模态 normalization、概率和事件输出；额外回归确认 train/val 之外的 cache participant 被拒绝。补一项 calibration RED（metrics 缺少该字段）→ GREEN。专项 2 passed；全套 127 passed；compileall/diff check 通过。CLI 与真实 bounded sample 尚未运行。

## M1 CLI/config（2026-09-06）

事实：M1 需要每个 IMU cache 的 M0 reference timestamps 才能构建 PPG cache，但训练时应保持 cache lazy，且 M0 命令行为不能回归。不同 source 的 PPG build failure 不能让未配对 IMU 悄悄进入训练。

风险：传入 lazy cache 的 `timestamps_ms=None` 会导致 PPG 自建 grid；把 PPG build failures 混进 IMU issues 会掩盖故障；把 M1 默认行为覆盖到 M0 会破坏既有可复现命令。

选择：CLI 仅在 `model: m1_imu_ppg` 时，从每个 lazy IMU `.npz` 单独读取 timestamps array 来调用 `build_ppg_cache(..., reference_timestamps_ms=...)`，并仅传入成功的同-source cache pairs；PPG issues 写入独立 JSON。无 `model` 的 YAML 仍走 M0。提交 `configs/m1_imu_ppg.yaml`（feature fusion）和 `configs/experiments/m1_ppg_only.yaml`（诊断），明确 PPG cache/preprocess/flat policy 与 model parameters。

实验：CLI TDD 先在 M0 路径运行并缺少 `model_mode` 输出（RED），实现后 2 个 toy participant 的 PPG-only CLI 完成独立 PPG cache 与 paired cache training，保存 nested IMU/PPG normalization（GREEN）。专项 1 passed、全套 127 passed；compileall/diff check 通过。真实 bounded PPG-only/fusion CUDA sample 尚未运行。

## Bounded CUDA 与 full-data gate（2026-09-06）

事实：用 frozen manifest 中 hnu21013(train) 和 hnu21024(val) 各最多30,000行、1 epoch/batch64/CUDA 完成真实 PPG-only、feature fusion(dropout=.25) 和 no-dropout fusion；首次 PPG-only 两种 cache 均2 miss，后两次均 IMU/PPG 2/2 hit。三次在此受限范围的事件 F1 都为0.0384615（P=1、R=0.0196078、start/end MAE=34506/259494ms），不能推断全量优劣。PPG-only/fusion/dropout fusion 的 binary Brier/ECE 分别为0.165814/0.407198、0.081846/0.286045、0.085418/0.292211；fusion 在该 tiny sample 的 calibration 较好，但不是选择依据。

风险：若完整 M1 重建 IMU cache，就不再是复用冻结M0 reference；若把 bounded event 结果写作全量结论，会误导下一步模型选择。

选择：检查 `cache/m0_full` 的1121个 cache 元数据后，确认其采样率、max gap、P0、window、label配置都与M1配置完全相同。因此三个 M1 YAML 的 `cache_dir` 均改为该只读 IMU cache；PPG 保持独立 `cache/m1_ppg`。完整运行前复核全套127 passed、compileall、diff check、CUDA2-step smoke、raw零跟踪、artifact/cache忽略，并以原始2378文件的size/mtime基线复核为零变化（基线记录有统一5小时偏移，校正后比较）。

验收：full-data gate 通过；接下来可按既定顺序全量构建/命中 PPG cache，运行 PPG-only，再重用既有 M0 reference，最后运行 fusion。未启动M2/M3/M4。

## 待完成

- [x] PPG parser 独立审查与缺失模态覆盖。
- [x] PPG cache 严格 TDD、数值/窗口/label 等价、原子写入和中断恢复验证、阶段提交。
- [x] 独立 IMU/PPG encoder、显式 mask、安全 modality dropout，严格 TDD 与 CUDA 样例、阶段提交。
- [x] 真实 PPG-only/fusion bounded sample、M0 reference、dropout 对照与 full-data gate。
- [x] 全量 PPG-only 与 fusion、缺失模态 coverage、完整指标报告。
- [x] 同 split train/val 全量 cache、PPG-only 诊断、复用 M0 reference、M1 联合训练与训练期 modality dropout。
- [x] 事件指标、MAE、calibration、coverage 和 CPU/GPU 分开遥测。
- [x] 全套最终验证、README/handoff/实施计划更新与提交，保留现有分支/worktree。

## Full-data compact PPG continuation（2026-09-06）

事实：紧凑 PPG cache 修复在严格 TDD 下完成并提交为 `08d571a fix: guard oversized PPG cache allocation`。新增 compact miss、lazy hit reader-throw、batch 局部零数组回归；另修复无显式 M0 reference 时 `max_dense_samples` 未进入 cache key 的边界问题。专项 `48 passed`，全套代码测试 `131 passed`；三份 M1 YAML 均显式记录 `ppg_max_dense_samples: 1000000`。独立审查无 P0/P1。

风险：超长 reference 的 compact 表示是保守的显式缺失 PPG，不是插值或外推；PPG-only 只是诊断；所有结果为同一冻结 split 的 3 epoch 单次 run，不能作为超参选择的稳健证明。

选择：不删除已有 `cache/m1_ppg` 或 `artifacts/m1_ppg_only_full_e3`，在原 cache 上恢复完整 PPG-only，再用全 hit cache 运行 fusion；M0 保持只读，不读取/训练 test，不启动 M2/M3/M4。

实验：

- 目标 HNU21004 reference 长度 `23,645,128`，最终 `.npz` 为 `storage=all_missing_compact`，`timestamps_ms=[0]`、`features=[45,0]`、`quality_mask=[1,0]`、`window_indices=[315264,2]`，保留 reference SHA-256 `108929f8c6534c2afb69d22170dd1380cc58da61ffc52d1ec6106386a5fad1f4`。`cache/m1_ppg` 共 1,136 个文件；本次新增 compact 记录 87 个，旧记录保留。
- PPG-only artifact `artifacts/m1_ppg_only_full_e3/`：3,578,835 windows（train/val=`2,985,246/593,589`），F1/P/R=`0.1792453/0.1180124/0.3725490`，start/end MAE=`839148.2/74066.6 ms`；binary Brier/ECE=`0.1670272/0.3231965`，soft=`0.1668948/0.3235527`；PPG cache `112 hit/1009 miss`、build/load=`1162.15/0.983 s`，training=`2953.12 s`。
- Fusion artifact `artifacts/m1_fusion_full_e3/`：`modality_dropout=0.25`，F1/P/R=`0.1686747/0.1060606/0.4117647`，start/end MAE=`637874.6/79659.7 ms`；binary Brier/ECE=`0.2398206/0.3741050`，soft=`0.2398207/0.3744612`；IMU/PPG cache 均 `1121/1121 hit`，training=`3097.80 s`。
- fusion val coverage：IMU=`272,759`、PPG=`248,689`、both=`248,689`、neither=`320,830` / `593,589` windows；PPG-only intentional IMU-missing val coverage：PPG=`248,689`、neither=`344,900`。M0 frozen reference F1=`0.1728395`，三份 split manifest SHA-256 均 `18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。
- 资源/隔离：两次 full run 使用 CUDA；full fusion 训练 epoch 均值约 `1029.65 s`、峰值已分配显存约 `94.15 MB`；PPG-only epoch 均值约 `982.15 s`、峰值约 `89.07 MB`。原始数据 2,378 条 size/mtime 与 preflight 一致，test 未读取/训练，cache/artifact 保留。

验收：full-data 运行已通过 CLI `TRAIN_SMOKE_PASS`；新鲜全套 `131 passed`、PPG cache/M1 专项 `48 passed`、compileall、diff check、CUDA smoke、lazy cache-hit、split equality、原始 metadata 2,378/2,378 未变、raw 未跟踪与 ignore 检查均通过。README、handoff、resume prompt 与本执行记录已更新，待文档原子提交。
