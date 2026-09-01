# Smartwatch Eating Detection Baseline

这是一个 participant-grouped、事件级评估的 M0/P0 基线。原始竞赛数据保持只读，代码通过配置文件或 CLI 参数读取；`artifacts/`、`cache/`、`checkpoints/` 和 `outputs/` 中的缓存、权重、报告和运行结果不进入 Git。

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

训练命令会打印 `CONFIG_SAVED`、`SPLIT_SAVED`、`TRAIN_EPOCH`、`VAL_EVENTS`、`test_not_used=true` 和 `TRAIN_SMOKE_PASS`。`evaluate` 只读取已冻结的窗口概率、decoder、truth 和配置，不重新调阈值。

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
