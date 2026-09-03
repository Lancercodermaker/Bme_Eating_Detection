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

- 2026-09-01 解析/cache gate：两个代表文件各限制到 100,000 行时，旧路径 canonicalization 约 1.50 s/文件；向量化聚合后约 0.007–0.008 s/文件。IMU-only parser 与旧路径的 timestamp、ACC/GYRO、mask 数值一致，并且不含 PPG 列时仍可读取。两个真实文件的 cache miss 约 0.361 s、hit 约 0.022 s；cache-backed M0 sample 已在 RTX 5060 CUDA 上完成 1 epoch，第二遍 hit 不读原始 CSV。
- 2026-09-02 full M0：全量枚举到 1,155 个 train/val sensor 文件，其中 1,121 个成功写入/命中 IMU-only cache，34 个不可解析文件写入 `artifacts/final_m0/run/input_issues.json`（18 个有效 timestamp 不足、16 个二进制/非 UTF-8 内容），没有修改或伪造这些原始文件。有效 cache 产生 3,578,835 个窗口（train 2,985,246、val 593,589），在 RTX 5060 CUDA 上以 batch 64 完成 20 epochs；cache build 97.38 s，训练约 7,110.82 s，平均 epoch 355.48 s。验证集事件指标为 Precision 0.0199637、Recall 0.647059、F1 0.0387324、start/end MAE 289,466/391,033 ms；这是当前 M0/P0 baseline 结果，不是 M1 结论。`evaluate` 只复用冻结概率/decoder/truth，并保留训练 device、batch、cache 和 epoch 遥测。
- M0 低 F1 复核：问题主要表现为验证窗口概率缺乏正负分离，而不是“完全检不出事件”。训练正窗口比例为 2.764%，`pos_weight=35.1769`；在 soft target 均值 0.0273 下，加权 BCE 的常数预测最优概率约为 0.4968。实际验证负窗口概率均值为 0.4568、正窗口为 0.3951，阈值 0.2 时负窗口 FPR 为 89.35%、正窗口 TPR 为 89.20%，产生 1,653 个预测事件但只有 33 个 TP。冻结候选阈值/merge 参数的离线穷举仍以 `0.2/9000/0` 最好，因此不是单独调高阈值即可解决。验证 participant `hnu21042` 有 6 个真事件但没有有效 cache 文件，直接形成 6 个不可预测 FN；同时 P0 质量 mask 约 45.85% 的验证采样点有效，但 soft 模式仍让所有窗口参与 loss 和解码。该结果应视为 IMU-only P0 的低校准/低泛化 baseline，不能据此否定 IMU-only 解析路径的数值等价性。

- Task 8 的 sample 消融已完成，但当前数值仅来自 2 个显式文件、1 个 epoch，不能替代 full-data 选择。
- Task 9 M1 暂不启动：M0/P0 已完成 full-data 稳定闭环，但当前事件 F1 很低，且 bounded PPG audit（100,000 行）显示有效 PPG 为 22,005 行（约 22%），其余大部分无效。根据冻结 gate，先保留 IMU-only M0，不把缺失 PPG 当作零信号，也不创建未经数据支持的 M1 结果。
- Task 10 暂不启动：没有满足 Task 9 的 M1 或 `error_analysis.json` 证据，因此不创建 M2/M3/M4 模型，避免在事件闭环不稳定时堆叠模型。
- Task 11 full-data 尝试：只枚举到 1,165 个传感器文件（约 93.14 GB），启动了按文件两遍处理的 streaming M0；约 16 分钟后仍在第一遍 CSV 解析、工作集约 957 MB，未产生 checkpoint/epoch。为保护本机资源主动中断，未声称 full-data 指标通过；`artifacts/final/m0/` 中仅保留配置和 manifest。
- full-data 的安全复现入口是无 `--limit-files/--max-rows` 的 `train` 命令；正式运行应先构建 cache，再在 cache hit 的独立运行中训练，并把 `input_issues.json` 作为数据覆盖审计的一部分。不把首遍 CPU cache 构建时间计入 GPU epoch 时间。M0/P0 full-data 已完成；M1、PPG-only 和高级模型仍按冻结 gate 未启动。
