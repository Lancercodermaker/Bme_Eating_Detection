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
2. 优先扩大 participant-frozen target-only 实验；外部数据已完成隔离和特征契约验证，只允许作为独立的训练预训练/增强对照，不改变 target-only 基线或官方提交读取路径。
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
- 20 participant、每人最多 4 session 的 local 实验在 40% valid split 上得到 6 个正 train candidate；candidate coverage=`0.857`，candidate event F1=`0.1935`。candidate fuse gap sweep：300 s 得最终 event F1=`0.7273`（TP/FP/FN=`4/0/3`、long FP=`0`），600 s=`0.50`，900 s=`0.29`；300 s 是当前最优后处理尺度。final decode fuse 300/600/900 s 结果相同。
- 在该 best split 加入 candidate 起止时间的日周期 sin/cos 特征后，F1、TP/FP/FN 和 MAE 均无变化；该 prior 暂保留，等待更大训练集验证，不把它宣称为增益。
- event verifier positive sample weight 在 `{1, 3, 5, 10}` 上结果完全相同（F1=`0.7273`、TP/FP/FN=`4/0/3`），说明当前过滤差异不是简单 class-weight 问题。CLI 已保留该参数供后续完整训练对照。
- TCN candidate-only 对照：同一 20×4、40% valid local cache，5 epochs、CUDA、15 s/7.5 s dense sequence、fuse 300 s，得到 F1=`0.2778`（TP/FP/FN=`5/24/2`，Recall=`0.7143`）。它略高于 HGB candidate-only F1≈`0.19`，但 coverage 更低、FP 很多，且明显低于 HGB candidate+event-verifier F1=`0.7273`；按 kill criterion 暂停 TCN 深化，不将其接入最终 verifier。
- 该 local 结果是当前最有希望的 target-only 方向，但 valid 只有 2 个 participant，不能视作排行榜上限；下一步提高训练预算并扩大 participant-frozen 验证覆盖。
- 诊断新增：candidate coverage recall、start/end MAE、长 FP fraction、participant 级指标。后续路线必须先改善 candidate coverage，再比较 verifier/TCN。
- 全 participant first-session broad audit（local、600 s fuse、threshold 0.20）覆盖 32 train/11 valid 或 26 train/17 valid，但 valid 餐段都只有 2 个，candidate recall 约 `0.50`、最终 F1=`0`。这不是模型上限，而是 session-selection bias；后续不能只取 participant 的首 session。
- broad 运行还发现无有效 ACC/GYRO 时间戳的 session；已统一映射为 `RawFileFormatError`，从 skipped provenance 中记录，不再中断整批实验。

## Spike 2 补充：轻量 Transformer 对照

- 新增 `TemporalTransformer` 与 `run_transformer_candidate.py`，先写测试验证窗口级输出、invalid mask、最大序列长度和参数量上限；实现后 focused tests 为 `5 passed`。
- 配置：15 s/7.5 s dense local windows，序列长度 128、stride 64、`d_model=32`、4 heads、2 layers、FFN 64，约 20,705 个参数，5 epochs，CUDA。
- 在当前可复用 cache-only 子集（40% participant-frozen valid split，94 个已缓存 session）上，candidate-only event F1=`0.0645`，TP/FP/FN=`1/25/4`。阈值 `0.1/0.2/0.3` 的 F1 分别为约 `0.054/0.065/0.0`。
- 同一 cache-only 子集重跑 TCN candidate-only 得 F1=`0.1404`，HGB candidate-only 得 F1=`0.1633`，HGB candidate+event-verifier 得 F1=`0.3333`。
- 结论：该轻量 Transformer 候选层的事件覆盖不足，阈值调整不能恢复漏检事件；按 candidate coverage gate 暂停该配置，不接入最终 verifier。这个结果否定的是“当前 15 s 特征序列 Transformer 直接作为候选层”，不是所有 Transformer 结构的理论上限。

### Spike 2b：小样本正则化复验

- 在同一 94-session cache-only、40% participant-frozen validation 子集上，将 Transformer 缩小为 `d_model=16`、1 层、FFN 32，并将 dropout 从 `0.1` 提高到 `0.3`、AdamW weight decay 从 `1e-4` 提高到 `1e-2`。事件 F1 从未正则化配置的 `0.0645` 提升到 `0.1875`，`TP/FP/FN=3/24/2`，Recall=`0.60`。
- 同一正则化配置的阈值 sweep：threshold `0.10/0.20/0.30` 的 F1 分别为 `0.1500/0.1875/0.0000`。因此正则化确实改变了泛化和召回，但并未解决 candidate-only 的误报与事件边界问题。
- 结论：Transformer 不应因首个配置失败而删除；后续保留 dropout、weight decay、较小容量和 early stopping 作为必测正则化轴，但在接入最终 verifier 前仍必须通过更大 participant-frozen split 的 candidate coverage gate。

## Spike 3 外部数据预检与训练适配

- 工作区未发现 FD-I/FD-II/WIMID/FIC 等外部信号文件。
- 已从 KU Leuven RDR 获取 FD-I README 与 7-fold subject-id 列表到工作区外的 `E:\bme_compitition\tmp`，确认 FD 数据为 64 Hz、左右手各 6 DoF、`X_L/X_R/Y_L/Y_R.pkl` 列表格式；标签为 point-wise 0/1/2，不能直接当作本题餐段区间标签。
- 组委会已确认外部数据只能用于训练、不得进入提交包；据此从官方 KU Leuven RDR 下载并校验 FD-I/FD-II 压缩包，MD5 分别为 `e5adb4c6f3caa8f52c215658228917dd` 与 `4c7b2f43560f7f9488643bbe0a9d3dce`。压缩包与解压数据位于工作区外的 `E:\bme_compitition\external-dataset`，并已加入 Git ignore。
- 新增 `eating_event.external` 适配器：按 participant/wrist 流式读取 `X_L/X_R/Y_L/Y_R.pkl`，验证 6 通道与点级标签契约，将 `1=eating` 映射为二值 eating-window 标签，`2=drinking` 保留为非 eating；窗口特征先从 64 Hz 重采样到目标 10 Hz，再复用同一套 111 维统计特征。
- 实际 FD-I 首个左腕样本已验证：`(1,984,366, 6)`、约 `8.61 h`、标签集合 `{0,1,2}`；截取 120 s 后得到 `(15,111)` 窗口特征，全部有限值。该步骤只验证训练数据契约，未改变官方 test/submission 读取路径。
- 独立外部预训练对照已完成：固定 94-session cache-only、40% participant-frozen target split 和正则化 Transformer 配置，target-only baseline F1=`0.1818`（`TP/FP/FN=4/32/4`）。FD-I participant 0–7 双腕预训练 F1=`0.2083`（`5/35/3`），participant 8–15 双腕预训练 F1=`0.2439`（`5/28/3`）；两个不重叠 cohort 的 Recall 均从 `0.50` 提升到 `0.625`。FD-II participant 0–7 预训练 F1=`0.1224`（`3/38/5`），出现负迁移。
- FD-I cohort B checkpoint threshold `0.10/0.15/0.20/0.25/0.30` 的 F1=`0.1509/0.2128/0.2439/0.2500/0.2000`；target-only 对应为 `0.1724/0.2000/0.1818/0.1429/0.0952`。增益不是单一 threshold 的偶然结果，但当前仍只验证了一个 target split。
- 完整 decision record 位于 `docs/external-preflight-2026-09-11.md`。Spike 3 当前状态为 `GO_WITH_RISKS_FD_I_ONLY`：下一步可扩大到全 FD-I 和 event verifier 对照；FD-II 暂不混入，外部 checkpoint 不直接用于提交。
