# Smartwatch Eating Detection Baseline

这是一个 participant-grouped、事件级评估的 M0/P0 基线。原始竞赛数据保持只读，代码通过配置文件或 CLI 参数读取；M0 默认只解析 ACC/GYRO，不读取 PPG；每个源文件只在 cache miss 时做一次 CSV/时间轴/重采样处理。`artifacts/`、`cache/`、`checkpoints/` 和 `outputs/` 中的缓存、权重、报告和运行结果不进入 Git。

## Windows 环境

在 PowerShell 中创建并验证环境：

```powershell
conda env create --file environment.yml
conda activate smartwatch-eating
python -m pip install -e ".[dev]"
python scripts/verify_environment.py --require-cuda --steps 2
```

本项目锁定 Python 3.11；`environment-win-64.lock.yml` 记录了本机 Windows 环境。GPU smoke 应报告 CUDA 可见并输出 `SMOKE_PASS device=cuda steps=2`。没有 GPU 时可以去掉 `--require-cuda`，但 CPU 结果不能当作 GPU 验收。

## Sample audit 和 M0 smoke

先只读取少量文件和行数，确认列格式、timestamp 0、重复包和无效 PPG：

```powershell
python -m eating_detection audit `
  --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" `
  --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" `
  --output-dir "artifacts\audit\sample" `
  --limit-files 2 --max-rows 2000
```

生成 participant manifest；其中 `test` 只进入 `excluded_test`，不进入 train/val：

```powershell
python -m eating_detection make-manifest `
  --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" `
  --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" `
  --output "artifacts\splits\m0_manifest.json" `
  --seed 7 --val-fraction 0.2
```

计划中的前 2 个排序文件可能没有正窗口，CLI 会明确输出 `TRAIN_BLOCKED reason=training split has no positive windows`，不会把窗口伪造成负样本。要完成一个最小带标签闭环，可显式指定两个已知覆盖餐段的文件：

```powershell
python -m eating_detection train `
  --config "configs\m0_p0.yaml" `
  --data-root "E:\bme_compitition\official_test_dataset\Data" `
  --index-dir "E:\bme_compitition\official_test_dataset\Data\01_dataset" `
  --train-dir "E:\bme_compitition\official_test_dataset\Data\02_traindataset" `
  --split-manifest "artifacts\splits\m0_manifest.json" `
  --sensor-file "E:\bme_compitition\official_test_dataset\Data\02_traindataset\organized\HNU 21013\sensorData-1784650948547-494d2b5ba270487b8c81c5a11e3d0ebb\collect_data11_1784625955_1784630476.txt" `
  --sensor-file "E:\bme_compitition\official_test_dataset\Data\02_traindataset\organized\HNU21024\sensorData-1784727463904-b9a676da01f94501a4af1d2748321c68\collect_data11_1784713630_1784718323.txt" `
  --max-rows 110000 --epochs 1 --batch-size 4 `
  --output-dir "artifacts\smoke\m0_e2e"

python -m eating_detection evaluate `
  --run-dir "artifacts\smoke\m0_e2e" --split val
```

训练命令会打印 `CONFIG_SAVED`、`SPLIT_SAVED`、`CACHE_SUMMARY`、`TRAIN_EPOCH`、`VAL_EVENTS`、`test_not_used=true` 和 `TRAIN_SMOKE_PASS`。第二次使用相同源文件、行数、采样/预处理/标签配置时应显示 `hits>0`；`evaluate` 只读取已冻结的窗口概率、decoder、truth 和配置，不重新调阈值。

缓存命中和吞吐契约：cache key 包含源文件路径/大小/mtime、目标采样率、`max_gap_ms`、预处理变体、窗口/步长、标签配置和实际区间。缓存写入先落临时 `.npz`，成功后原子改名；按文件构建，因此中断后重跑会复用已经完成的文件。缓存内容是统一时间轴、连续 feature array、quality mask 和 window index；重叠窗口不保存独立 `.clone()` Tensor，DataLoader 在 batch 时切片并在 CUDA 可用时使用 pinned memory 和 non-blocking transfer。full-data 训练使用 lazy cache，只保留索引和当前文件的大数组，避免把 93 GB 对应的连续特征全部驻留内存。解析/时间轴/重采样/cache 构建仍计入 CPU pipeline，不能当作 GPU 训练时间。

## 数据、标签和评估契约

- 先恢复统一时间轴、去除 timestamp 0、稳定排序并合并重复包，再重采样；ACC/GYRO 的质量 mask 保留到模型输入。
- 默认目标频率为 25 Hz，并可比较 15/16 Hz 和 50 Hz。
- `soft` 始终返回窗口与餐段的实际 overlap ratio，范围 `[0, 1]`；`ignore` 只在 `0 < ratio < label_positive_overlap` 时返回 `None`，达到阈值时返回 1。
- `label_positive_overlap` 是训练窗口标签阈值；`event_iou_threshold` 是竞赛事件匹配阈值。两者默认都为 0.25，但语义独立。
- split 按 participant 分组，禁止把相邻窗口随机切到不同集合；test 不参与训练、decoder 调参或模型选择。
- 主指标是事件级 Precision、Recall、F1；事件匹配要求 IoU 严格大于 0.25，同时报告正确匹配事件的 start/end MAE。
- M0 使用 10 个通道：标准化原始 IMU 六轴、标准化 ACC/GYRO 模长，以及 broadcast 到时间轴的 ACC/GYRO quality mask。loss 使用训练集统计的 `pos_weight` 和 `BCEWithLogitsLoss`，输入为 logits，不在 loss 前手动 sigmoid。
- threshold、merge gap、minimum duration 等 decoder 参数只从 validation 调整。

## 运行输出和复现

一次训练目录应包含 `config.yaml`、`split_manifest.json`、`normalization.json`、`checkpoint.pt`、`window_probabilities.jsonl`、`decoder.json`、`events_val.json`、`metrics.json`、`truth_intervals.json` 和 `training_log.json`。checkpoint 记录模型、optimizer、配置、participant manifest、标准化统计、seed、epoch 和验证指标。

完整运行沿用同一个 manifest 和 seed；test 推理只能在 checkpoint/config/decoder 冻结后进行，不能用 test 反调参数。提交前运行：

```powershell
python -m pytest -q
git diff --check
git status --short
```

## Gate 记录

- **2026-09-07 M1 focal-BCE 复验（候选淘汰）：** 原 M1 fusion 结构下只将 loss 改为 focal BCE (`gamma=2`)，保留 global train-only `pos_weight=35.1769`、BCE logits、原 decoder。full frozen run `artifacts/m1_fusion_focal_bce_e1/` 得到 TP/FP/FN=`18/449/33`、P/R/F1=`0.0385439/0.3529412/0.0694981`、participant mean/std/worst=`0.0592277/0.0352845/0`、start/end MAE=`551510/909180 ms`；短暂 FP=`13/449=2.89532%`，Recall=`35.2941%`，且 `neither` predicted-positive rate=`1.0`。M2 gate 仍 false；对应报告为 `artifacts/experiments/m1_fusion_focal_bce_e1/error_analysis.json`。mask-detached、unweighted BCE、focal BCE 三轮 remediation 均淘汰，不创建 M2。

- **2026-09-06 M1 unweighted-BCE 复验（候选淘汰）：** 恢复原 M1 fusion 结构，只将实际训练 `pos_weight` 设为 `1.0`。full frozen run `artifacts/m1_fusion_unweighted_bce_e1/` 的 TP/FP/FN=`8/440/43`、P/R/F1=`0.0178571/0.1568627/0.0320641`、participant mean/std/worst=`0.0370053/0.0515354/0`、start/end MAE=`122452/279977 ms`；短暂 FP=`168/440=38.1818%`，Recall=`15.6863%`，均未满足 M2 gate。对应 error analysis=`artifacts/experiments/m1_fusion_unweighted_bce_e1/error_analysis.json`。下一轮只验证 focal BCE (`gamma=2`) hard-example 方向，不叠加 mask、unweighted prior、decoder 或 M2 context。

- **2026-09-06 M1 mask-detached 复验（候选淘汰）：** systematic debugging 从 e2 checkpoint 确认 raw availability mask 直接进入 fusion gate/head，e2 head mask weights=`+2.2778/+1.3741`，embedding max abs=`0.1401`。单独移除 mask 到 gate/head、保持 global BCE 的 full frozen run `artifacts/m1_fusion_mask_detached_e1/` 得到 TP/FP/FN=`32/710/19`、P/R/F1=`0.0431267/0.6274510/0.0807062`、participant mean/std/worst=`0.0685150/0.0372385/0`、start/end MAE=`462503.5/126226.8 ms`；710 FP 中仅 `26/710=3.66197%` 为短暂。M2 gate 仍 false，且 F1 低于 e2，因此淘汰该候选。下一轮只验证 unweighted-BCE probability-prior 方向，不叠加 mask/loss/decoder 多个高层改动。

- **2026-09-06 M1 remediation 复验（当前最新）：** systematic debugging 确认长 FP 是高分连续输出，且 `both`/`imu_only` availability 与分数强耦合；短暂 FP 不是主因。只选择一个 availability-invariant M1 BCE 方向：train-only 分层 `pos_weight`，并将分层权重上限限制为原 global `pos_weight`；旧 M1 config 未声明该模式时保持 `global_bce`。TDD 先 RED 后 GREEN，专项 M1 测试 `22 passed`。
- 首次未限幅反例 `artifacts/m1_fusion_availability_stratified_e1/` 的 `neither` 权重=`648.2119`，导致其窗口预测正率=`1.0`，validation F1=`0.0777385`，不采用。capped 复验 `artifacts/m1_fusion_availability_stratified_e2/` 使用 1121/1121 IMU/PPG cache hit、3 epoch CUDA、`test_not_used=true`，TP/FP/FN=`24/335/27`，P/R/F1=`0.0668524/0.4705882/0.1170732`，participant F1 mean/std/worst=`0.0981172/0.0612279/0`，start/end MAE=`817518.5/62955.9 ms`。
- 独立报告 `artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`：335 个 FP 的 duration median/p90/max=`297000/8387965.2/24687528 ms`、window count median/p90=`92/2769.4`；短暂定义（`duration≤30000 ms` 且 `window_count≤2`）仅 `10/335=2.9851%`；Recall=`47.0588%`；`both` 窗口预测正率/FPR=`99.7294%/99.7175%`，`neither` 预测正率=`0`。因此 capped loss 改善了 `neither` shortcut，但未解决 `both` 长 FP，且未超过原 M1 F1=`0.1686747`。
- **M2 evidence gate=`false`：** short-FP dominance、positive-event Recall 严格大于 50%、probability/validity/interval context support 均不满足。按原计划不创建 `src/eating_detection/context_model.py`、`configs/experiments/m2_context.yaml`、M2 测试或训练输出；下一步先做单一 M1 层面的 `both` availability/mask prior 证据实验。

- 2026-09-06 M1 full-data compact gate：在不删除既有 `cache/m1_ppg` / artifact、不重建 `cache/m0_full` 的前提下，`max_dense_samples=1,000,000` 将 23,645,128 点 PPG reference 安全保存为 `all_missing_compact`，保留 M0 reference/window/label/hash 对齐；目标条目 `features=[45,0]`、`window_indices=[315264,2]`。修复已提交为 `08d571a`，专项 `48 passed`，全套代码测试 `131 passed`；三个 M1 YAML 已显式记录该阈值。
- 同一 `artifacts/final_m0/split_manifest.json`（34 train / 8 val；SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`）完成 full PPG-only 与 fusion 3 epoch CUDA 运行。M0 参照 F1=`0.1728395`（P=`0.109375`、R=`0.411765`）；PPG-only F1=`0.1792453`（P=`0.118012`、R=`0.372549`，start/end MAE=`839148/74067 ms`）；fusion F1=`0.1686747`（P=`0.106061`、R=`0.411765`，start/end MAE=`637875/79660 ms`）。PPG-only 为诊断，fusion 使用独立 encoder、显式 modality mask 和 `modality_dropout=0.25`。
- 校准/覆盖/资源：PPG-only binary Brier/ECE=`0.167027/0.323197`、soft=`0.166895/0.323553`；fusion binary=`0.239821/0.374105`、soft=`0.239821/0.374461`。fusion val 593,589 windows 中 IMU/PPG/both/neither=`272,759/248,689/248,689/320,830`；PPG-only 故意 IMU-missing，PPG/neither=`248,689/344,900`。PPG-only cache `112 hit/1009 miss`、build=`1162.15 s`；fusion IMU/PPG 均 `1121/1121 hit`。原始 2,378 条 size/mtime 与 preflight 一致，test 未读取/训练，未启动 M2/M3/M4。
- M1 validation error analysis：`python -m eating_detection.error_analysis --run-dir artifacts/m1_fusion_full_e3 --cache-dir cache/m0_full --ppg-cache-dir cache/m1_ppg --comparison-run-dir artifacts/m0_final_q50_group_e3 --ppg-only-run-dir artifacts/m1_ppg_only_full_e3 --output artifacts/experiments/m1_fusion_full_e3/error_analysis.json`。报告仅使用 frozen validation 输出并记录 source run、cache、split hash 和 decoder。177 个 FP 的 duration/window median=`1963878 ms/644`，max-score median=`0.885101`；按≤30 s 且≤2窗口的短暂定义仅 `6/177`，fusion Recall=`0.411765`。M2 gate 不满足，M3/M4 也无证据支持；因此不创建或运行高级模型，保留 M0/M1。

- 2026-09-01 解析/cache gate：两个代表文件各限制到 100,000 行时，旧路径 canonicalization 约 1.50 s/文件；向量化聚合后约 0.007–0.008 s/文件。IMU-only parser 与旧路径的 timestamp、ACC/GYRO、mask 数值一致，并且不含 PPG 列时仍可读取。两个真实文件的 cache miss 约 0.361 s、hit 约 0.022 s；cache-backed M0 sample 已在 RTX 5060 CUDA 上完成 1 epoch，第二遍 hit 不读原始 CSV。
- 2026-09-02 full M0：全量枚举到 1,155 个 train/val sensor 文件，其中 1,121 个成功写入/命中 IMU-only cache，34 个不可解析文件写入 `artifacts/final_m0/run/input_issues.json`（18 个有效 timestamp 不足、16 个二进制/非 UTF-8 内容），没有修改或伪造这些原始文件。有效 cache 产生 3,578,835 个窗口（train 2,985,246、val 593,589），在 RTX 5060 CUDA 上以 batch 64 完成 20 epochs；cache build 97.38 s，训练约 7,110.82 s，平均 epoch 355.48 s。验证集事件指标为 Precision 0.0199637、Recall 0.647059、F1 0.0387324、start/end MAE 289,466/391,033 ms；这是当前 M0/P0 baseline 结果，不是 M1 结论。`evaluate` 只复用冻结概率/decoder/truth，并保留训练 device、batch、cache 和 epoch 遥测。
- M0 低 F1 复核：问题主要表现为验证窗口概率缺乏正负分离，而不是“完全检不出事件”。训练正窗口比例为 2.764%，`pos_weight=35.1769`；在 soft target 均值 0.0273 下，加权 BCE 的常数预测最优概率约为 0.4968。实际验证负窗口概率均值为 0.4568、正窗口为 0.3951，阈值 0.2 时负窗口 FPR 为 89.35%、正窗口 TPR 为 89.20%，产生 1,653 个预测事件但只有 33 个 TP。冻结候选阈值/merge 参数的离线穷举仍以 `0.2/9000/0` 最好，因此不是单独调高阈值即可解决。验证 participant `hnu21042` 有 6 个真事件但没有有效 cache 文件，直接形成 6 个不可预测 FN；同时 P0 质量 mask 约 45.85% 的验证采样点有效，但 soft 模式仍让所有窗口参与 loss 和解码。该结果应视为 IMU-only P0 的低校准/低泛化 baseline，不能据此否定 IMU-only 解析路径的数值等价性。
- M0 诊断报告可从现有 cache 复现，不读取原始 CSV：`python -m eating_detection.error_analysis --run-dir artifacts/final_m0/run --cache-dir cache/m0_full`，输出 `artifacts/final_m0/run/error_analysis.json`。报告包含 quality 分层、binary/soft 两套可靠性分箱与 Brier/ECE、冻结 decoder 参数穷举及 participant 级 TP/FP/FN、边界误差和 cache 覆盖审计。
- 2026-09-03 M0 瓶颈修复：在同一 participant split 和 `cache/m0_full` 上，q50 质量分层 + GroupNorm + 实际筛选窗口的 `pos_weight` + deterministic batch cache fetch 的 full-data 3 epoch run 位于 `artifacts/m0_final_q50_group_e3/`。1121/1121 cache hit、训练窗口 1,306,197、验证窗口 271,724、`device=cuda`、`batch_size=64`；独立 `evaluate` 复现 Precision=`0.109375`、Recall=`0.411765`、F1=`0.1728395`、start/end MAE=`639946/71945 ms`，相对原始 P0 F1=`0.0387324` 明显改善。质量/校准报告的 Brier=`0.157069`、ECE=`0.321964`，优于 baseline 的 `0.248107/0.433362`。q50 训练后的有效 `pos_weight=15.4116`；不再错误沿用未筛选窗口的 `35.1769`。
- 本轮 M0 淘汰证据：P1 lowpass/dynamic=`0.1728395`、P2 axis mirror=`0.1728395`、ignore-boundary=`0.1728395`、avg4 pooling=`0.1728395`，avg+max=`0.1504178`；冻结概率上的平滑 decoder 最高约 `0.195` 仅是同一 validation 的离线后处理，未作为可泛化模型选择。最终保留 q50 + GroupNorm + 默认 avg pooling；没有启动 M1。
- 当前候选仍有边界：验证事件为 TP=`21`、FP=`171`、FN=`30`；`hnu21042` 没有有效 IMU cache，6 个真事件不可预测。因此该结果证明低 F1 瓶颈已显著缓解并形成可复现 M0 候选，但不把它表述为错误已完全消失。

- Task 8 的 sample 消融已完成，但当前数值仅来自 2 个显式文件、1 个 epoch，不能替代 full-data 选择。
- Task 9 M1 暂不启动：M0/P0 已完成 full-data 稳定闭环，但当前事件 F1 很低，且 bounded PPG audit（100,000 行）显示有效 PPG 为 22,005 行（约 22%），其余大部分无效。根据冻结 gate，先保留 IMU-only M0，不把缺失 PPG 当作零信号，也不创建未经数据支持的 M1 结果。
- Task 10 暂不启动：M1 尚未启动，因此还没有满足 Task 10 所需的 `artifacts/experiments/m1*/error_analysis.json` 证据；当前 M0 诊断只用于后续质量/校准和 participant 泛化决策，不创建 M2/M3/M4 模型，避免在事件闭环不稳定时堆叠模型。
- Task 11 full-data 尝试：只枚举到 1,165 个传感器文件（约 93.14 GB），启动了按文件两遍处理的 streaming M0；约 16 分钟后仍在第一遍 CSV 解析、工作集约 957 MB，未产生 checkpoint/epoch。为保护本机资源主动中断，未声称 full-data 指标通过；`artifacts/final/m0/` 中仅保留配置和 manifest。
- full-data 的安全复现入口是无 `--limit-files/--max-rows` 的 `train` 命令；正式运行应先构建 cache，再在 cache hit 的独立运行中训练，并把 `input_issues.json` 作为数据覆盖审计的一部分。不把首遍 CPU cache 构建时间计入 GPU epoch 时间。M0/P0 full-data 已完成；M1、PPG-only 和高级模型仍按冻结 gate 未启动。
