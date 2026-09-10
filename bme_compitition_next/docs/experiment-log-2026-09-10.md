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
- 全套当前测试：32 个测试通过。

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

## OOF verifier 与候选诊断

- candidate verifier 已改为 participant-level OOF score：每个 train participant 的 candidate 分数由未包含该 participant 的模型产生；验证 participant 使用全训练 participant 模型。小样本 fold 无法形成正负两类时会显式记录 `oof_fallback_participants`。
- OOF 分数只用于训练 event verifier；candidate threshold 的分位数改为从 full-train model 的 train score 计算，避免 OOF 与 full-train 概率尺度错位。
- 240 s/15 s、4 participant 小 split、低预算 OOF：candidate coverage recall 仍为 0.25，最终 event F1 为 0；15 s 小 split 最终 F1 也为 0。该结果不足以否定 local-tree，但否定了继续在该小 split 上调参的价值。
- 扩大 target-only 240 s 实验：10 participant、每人最多 2 session，8 train/2 valid，3 个 malformed session 被跳过并保留 provenance。candidate coverage recall=`0.50`、candidate event F1=`0.2222`、最终 event F1=`0`；HNU21011 candidate recall=1、HNU21037=0，显示 participant shift 仍是主要风险。
- 同一 10 participant split 的 15 s/7.5 s local-tree：固定阈值 0.35 时最终 event F1=`0.3333`；降低 candidate threshold 到 0.20 后为 `TP/FP/FN=1/0/1`、event F1=`0.6667`，start MAE=`122.9 s`、end MAE=`60.9 s`、long FP fraction=`0`。raw candidate coverage recall=`0.50`，HNU21011 被 verifier 正确保留，HNU21037 仍漏检。
- 同一 local cache 提高 candidate/verifier 预算到 100 iter 后最终 F1 降为 `0`，虽然 candidate coverage 仍为 `0.50`；verifier 过滤掉了低预算下的唯一 TP。这是 participant-frozen 过拟合/校准 failure mode，当前不继续提高 HGB 迭代次数。
- 同一 local cache 改用 40% participant-frozen split（4 valid participants）时，120 s fuse 在 threshold 0.20/0.35 下产生 0 个正 train candidate，verifier 无法训练；record-level 诊断显示 600 s fuse 才产生正候选。600 s fuse 下 candidate coverage recall=`0.75`、candidate event F1=`0.30`、最终 F1=`0.40`（TP/FP/FN=`1/0/3`），但 start/end MAE 约 1101/1129 s，说明长 fuse 带来边界风险。
- 该 40% split 的 verifier threshold 0.10/0.25/0.50 结果相同，训练正候选只有 1 个；因此当前瓶颈是正候选数量和 participant shift，不是 decoder threshold。
- 扩展到 20 participant、每人最多 2 session 的 local target-only 实验（15 train/5 valid）后，600 s fuse、candidate threshold 0.20 产生 5 个正 train candidate；candidate coverage recall=`1.0`、candidate event F1=`0.375`、最终 event F1=`0.3333`（TP/FP/FN=`1/2/2`）。5 个 valid participant 中 4 个有真餐段，3 个 candidate coverage=1 但 verifier 只保留 1 个 TP；verifier threshold 0.10/0.25/0.50 无差异。结论仍是 verifier 正样本不足，下一轮扩大 participant/session 覆盖。
- 该 local 结果是当前最有希望的 target-only 方向，但 valid 只有 2 个 participant，不能视作排行榜上限；下一步提高训练预算并扩大 participant-frozen 验证覆盖。
- 诊断新增：candidate coverage recall、start/end MAE、长 FP fraction、participant 级指标。后续路线必须先改善 candidate coverage，再比较 verifier/TCN。
- 全 participant first-session broad audit（local、600 s fuse、threshold 0.20）覆盖 32 train/11 valid 或 26 train/17 valid，但 valid 餐段都只有 2 个，candidate recall 约 `0.50`、最终 F1=`0`。这不是模型上限，而是 session-selection bias；后续不能只取 participant 的首 session。
- broad 运行还发现无有效 ACC/GYRO 时间戳的 session；已统一映射为 `RawFileFormatError`，从 skipped provenance 中记录，不再中断整批实验。
