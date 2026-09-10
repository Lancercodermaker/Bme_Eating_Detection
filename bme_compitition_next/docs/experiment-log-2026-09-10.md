# 实验日志：2026-09-10

## 数据与环境

- 目标工作区：`E:\bme_compitition\bme_compitition_next`
- raw root 与 metadata root 通过 `configs/example.local.yaml` 显式传入。
- `smartwatch-eating` 环境：Python 3.11.16、NumPy 2.4.6、pandas 2.3.3、SciPy 1.17.1、PyTorch 2.11.0+cu128、CUDA 可用、scikit-learn 1.9.0。
- manifest 只读统计：1161 个训练 session 文件、43 个 participant、281 个有效餐段、326 个含餐段 session；官方 test 目录 2 个 session，未进入训练。

## 已通过的基础验证

- 官方事件指标：严格 `IoU > 0.25`、一对一匹配、空集合和边界 MAE 测试通过。
- 时间轴：重复 packet 聚合、零/非正时间戳缺失化、长 gap 不插值、ACC/GYRO 公共网格对齐测试通过。
- 原始数据 failure mode：二进制伪 `.txt`、重复 header/非数值行被识别为 `RawFileFormatError` 并可加入 skipped provenance。
- 全套当前测试：28 个测试通过；之后加入 verifier/候选测试后为 30 个通过。

## Spike A：240 s coarse candidate-only

命令核心：`run_candidate_baseline.py --window-seconds 240 --step-seconds 15`，4 个 participant、每个最多 10 个 session、1 个 frozen validation participant。

结果：`TP/FP/FN=1/8/3`，event F1=`0.1538`，start MAE 约 352 s，end MAE 约 1709 s。

解释：没有超过旧版可信 M0 的 0.1728；长 FP 和边界过宽仍然存在。这个结果否决“240 s 统计特征直接 eventize”作为终点，但不是对 240 s context 的最终否决。

## Spike B：15 s/7.5 s local candidate-only

命令核心：`run_candidate_baseline.py --window-seconds 15 --step-seconds 7.5`，同 participant 子集和 frozen split。

结果：`TP/FP/FN=0/3/1`，event F1=`0.0`。同一 cache 上 event verifier 因训练 candidate 正样本太少/分数极端而无法可靠泛化；扩大到 q75 后可训练，但验证 F1 仍为 0。

解释：该 spike 的主要 failure mode 是小样本 participant split 和 in-sample candidate score 极端化，不足以否定队友报告的 local-tree 路线。下一轮必须扩大 participant 覆盖，并使用 train-only quantile/OOF score 训练复核器。

## 当前决策

1. 保留 15 s/7.5 s local-tree 与 240 s coarse-context 两条候选尺度。
2. 优先扩大 participant-frozen target-only 实验；暂不引入外部数据或 TCN，避免混淆数据契约与模型收益。
3. verifier 正式训练必须改为 train participant 内 OOF candidate score；固定绝对概率阈值暂不可信。
4. 任何正式候选路线仍需同时报告 candidate Recall、event F1、长 FP 比例、participant 最差 F1 和边界 MAE。

