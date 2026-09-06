# M1 执行与门禁记录

用户于 2026-09-06 明确授权启动 M1；旧文档的“等待授权”状态由此覆盖。
仅使用现有 `codex/smartwatch-eating-baseline` worktree，不合并、不 push、不启动 M2/M3/M4。

## M1 remediation 与复验 gate（2026-09-06，当前最新）

### 事实

- 起始 HEAD=`920ca23b91e082c1192968234471553342410030`；仍使用 `E:\bme_compitition\.worktrees\smartwatch-baseline`、分支 `codex/smartwatch-eating-baseline`、项目解释器 `C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe` 和 `artifacts/final_m0/split_manifest.json`。未读取 test、未重训 M0、未重建 `cache/m0_full`。
- systematic debugging 将问题分为四类并确认：长期连续 FP、高分输出与 modality availability 耦合、校准/threshold 不是唯一根因、以及真实 Recall 不足/不可观测 FN。有限候选中只选 availability-invariant M1 BCE；M2/M3/M4 不并行。
- TDD 先 RED：新增 capped weight 断言时 `compute_m1_stratum_pos_weights` 不接受 `max_pos_weight`；最小实现后 GREEN。随后增加 legacy config RED→GREEN，确保只有显式 `m1_loss_mode=availability_stratified_bce` 才启用新 loss，旧 M1 config 仍为 `global_bce`。专项 M1 测试=`22 passed`。
- e1 直接分层权重实验把 `neither` 的 train-only `neg/pos` 比设为 `648.2119`，validation `neither` predicted-positive rate=`1.0`，TP/FP/FN=`11/221/40`，F1=`0.0777385`；作为明确反例淘汰。
- 选定方向内的 e2 capped 复验使用 `min(stratum_ratio, global_pos_weight)`，只用 train participant 统计；run=`artifacts/m1_fusion_availability_stratified_e2/`，1121/1121 IMU/PPG cache hit，windows=`3,578,835`，3 epoch CUDA training=`3041.14 s`，`test_not_used=true`。
- e2 frozen validation：TP/FP/FN=`24/335/27`，P/R/F1=`0.0668524/0.4705882/0.1170732`，participant F1 mean/std/worst=`0.0981172/0.0612279/0`，start/end MAE=`817518.5/62955.9 ms`。FP duration median/p90/max=`297000/8387965.2/24687528 ms`，window count median/p90=`92/2769.4`，short FP=`10/335=2.9851%`；`both` predicted-positive rate/FPR=`0.9972938/0.9971748`，`neither` predicted-positive rate=`0`。
- 对应报告为 `artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`；其 gate observed Recall=`0.4705882`，short FP fraction=`0.0298507`，context support=`false`，M2=`false`。未创建 `context_model.py`、`m2_context.yaml` 或 M2 输出。

### 风险、候选、验收标准、选择

- 风险：capped loss 修正了 `neither` 的分数塌缩，但 `both` 长 FP 仍占主导，且 F1 低于原 M1 `0.1686747`；不能将 e2 解读为成功，更不能用它强行启动 M2。
- 候选：只保留该单一 M1 availability-invariant loss 方向的已验证 capped 变体；M2 仍需短 FP≥50%、Recall严格>50%、context evidence 三项全满足，M3/M4 本轮不满足。
- 选择：`do_not_start_advanced_models`。下一步仅建议在 M1 层面针对 `both` mask/availability prior 做新的独立证据实验，当前不实现、不配置、不训练 M2。

### 交付物

- 代码：`src/eating_detection/training.py`、`tests/test_m1_fusion.py`、`tests/test_m1_cached_training.py`、`configs/experiments/m1_availability_stratified.yaml`。
- 证据：`artifacts/m1_fusion_availability_stratified_e1/`（反例）、`artifacts/m1_fusion_availability_stratified_e2/`（最终 capped 复验）、`artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`。

## M1 validation error analysis 与高级方向 gate（2026-09-06，当前最新）

### 事实

- 使用 `artifacts/m1_fusion_full_e3/` 的 frozen validation 输出，配对读取 `cache/m0_full` 与 `cache/m1_ppg` 的 metadata、window arrays 和 quality mask；未读取原始 CSV、test participant 或 checkpoint 做推理。结果保存于计划要求的 `artifacts/experiments/m1_fusion_full_e3/error_analysis.json`。
- provenance 已记录 source run-dir、两个 cache 目录、split manifest SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`、decoder=`0.15/6000/0`、`event_iou_threshold=0.25`、`label_positive_overlap=0.25` 和 `ppg_max_dense_samples=1000000`；192 个 validation M0/PPG pair 的 reference SHA-256 均匹配，window start/end/label/loss mask 均匹配。
- fusion validation 总体为 windows=`593589`、TP/FP/FN=`21/177/30`、Precision/Recall/F1=`0.1060606/0.4117647/0.1686747`、participant F1 mean/std/worst=`0.1481688/0.1077214/0`、start/end MAE=`637874.6/79659.7 ms`。独立复算与 frozen `metrics.json` 相等。
- FP 分布显示持续误报而非短暂误报：duration median/p90/max=`1963878/12265790.4/24915528 ms`，window count median/p90=`644/4071`，max-score median=`0.8851013`，event-mean-score median=`0.7146850`，前后相邻预测事件 gap median 均=`117000 ms`。按 duration≤`30000 ms` 且 window count≤2 的固定短暂定义，仅`6/177`=`3.39%` FP。
- calibration 为 binary Brier/ECE=`0.2398206/0.3741050`、soft=`0.2398207/0.3744612`。实际 validation modality strata 为 imu-only=`24070`、PPG-only=`0`、both=`248689`、neither=`320830`；threshold=`0.15` 时 imu-only/both 窗口阳性率与窗口 FPR均为1，neither 阳性率为0，显示分数强烈依赖 modality availability。
- 同 split M0 `artifacts/m0_final_q50_group_e3/` 为 F1=`0.1728395`、P/R=`0.109375/0.4117647`、start/end MAE=`639946.0/71945.5 ms`、participant F1 std=`0.1137248`。M1 fusion delta：F1=`-0.0041648`、Precision=`-0.0033144`、Recall=`0`、start MAE=`-2071.4 ms`、end MAE=`+7714.3 ms`。PPG-only 诊断 F1=`0.1792453` 但 Recall=`0.3725490`，不能替代 fusion 主结果。

### 风险

- M1 full run 仍是 frozen split、3 epoch、单次实验；整体 Recall 仅`41.18%`，且 177 个 FP 主要是高分长连续段。此证据不支持把错误归因于窗口概率的短暂抖动，也不支持直接堆叠更高容量模型。
- modality coverage 中没有 PPG-only windows；PPG available 全部落在 both，neither 占`320830/593589`。因此不能把 PPG 分支的可用性误写成独立模态已提升泛化。

### 候选

- M2：仅在短暂 FP 主导、正事件 Recall 足够，且 error analysis 支持 probability/validity/interval context 时启动。
- M3：仅在局部连续性或边界抖动是主问题时启动。
- M4：仅在 M1 稳定且未被前两类错误解释时启动。
- 不启动高级模型：M1 信号、coverage 或 Recall 不足，或证据不支持上述归因。

### 验收标准

- 本轮报告采用可复核的保守操作化：短暂 FP 为 duration≤`2×window_sec=30000 ms` 且窗口数≤2；主导要求短暂 FP 占比≥50%；“检出大部分正事件”要求 Recall>50%。三项需同时满足才算 M2 gate passed。M3 需有局部连续性/边界抖动主导证据；否则不启动。
- 必须维持 strict IoU>`0.25`、participant 级 metrics、宏平均 start/end MAE、binary/soft calibration、modality coverage、同 split M0 对比，且 artifact 明确 source run、split hash 和 decoder。

### 选择

- 选择 `do_not_start_advanced_models`。M2 gate=`false`：short FP dominance=`false`、positive-event recall sufficient=`false`、context support=`false`；M3/M4 亦为 false。只保留 M0/M1，不创建 `context_model.py`、M2 config 或 M2 训练产物。

### 实验结果

- `src/eating_detection/error_analysis.py` 新增 M1 双 cache、FP event duration/window/gap/score、participant metrics、calibration、modality strata、同 split comparison 和 gate 输出；M0 CLI 分支保持兼容。reference hash mismatch 回归也已加入。
- TDD 已完成 RED→GREEN：合成 cache/error-analysis 专项当前 `2 passed`；真实分析命令输出 `ERROR_ANALYSIS windows=593589 f1=0.168674698795 fp=177 participants=8`。full M1 artifacts、cache 与 raw 均未删除或重建。

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
