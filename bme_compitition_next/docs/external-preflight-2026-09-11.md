# 外部数据独立 Preflight：2026-09-11

## Goal

判断外部 FD 数据的训练-only 预训练是否值得进入下一阶段，以提高官方目标集的 event-level F1；外部数据不能进入官方 test、提交文件或提交推理路径。

## Success metrics

- 主指标：固定 participant-frozen target validation split 上的 event-level F1。
- 辅指标：event TP/FP/FN、Recall、start/end MAE、最差 participant F1。
- 接受条件：相同 target split、相同 Transformer 配置下，外部预训练相对 target-only baseline 的 F1 有稳定正增益，且不是依靠明显增加 FP 换取；外部数据不被 submission runner 读取。
- 当前结果只代表 participant-frozen target validation，不代表官方测试集分数或排行榜上限。

## Constraints

- 外部数据只能用于训练；所有 target validation 指标只在赛题官方训练数据的 participant-frozen 验证集上计算。
- 固定 15 s window、7.5 s stride、10 Hz feature grid、111 维特征、Transformer `d_model=16`、1 layer、FFN 32、dropout 0.3、AdamW weight decay 0.01。
- target-only 与外部预训练实验使用相同 target split、seed、微调 epoch、decode 参数；外部预训练为 2 epoch，target 微调为 5 epoch。

## Prior art

- 官方 FD 数据说明：64 Hz、左右腕 6 DoF、点级标签 `0=other/1=eating/2=drinking`；FD-I 是 free-living 标注，FD-II 只在 meal session 标注。来源：[KU Leuven RDR FD dataset](https://rdr.kuleuven.be/dataset.xhtml?persistentId=doi%3A10.48804%2FCN8VBB)。
- 目标项目已有 HGB candidate + event verifier 路线；此前同一类 cache-only 子集上，HGB verifier 优于 candidate-only Transformer，因此本次结果首先回答“外部预训练是否改善候选覆盖”，不是直接替换最终 verifier。

## Baseline

当前 target-only baseline：94 个缓存 session、40% participant-frozen valid split、正则化轻量 Transformer，threshold 0.20。

- `TP/FP/FN=4/32/4`
- event F1=`0.1818`
- Recall=`0.5000`
- start/end MAE=`773772/131512 ms`

## Candidate approaches

| 方案 | 外部训练数据 | target event F1 | TP/FP/FN | Recall | 结论 |
|---|---|---:|---:|---:|---|
| target-only | 无 | 0.1818 | 4/32/4 | 0.500 | 基线 |
| FD-I cohort A | participant 0–7，双腕，16 tables | 0.2083 | 5/35/3 | 0.625 | 正向，但 FP +3 |
| FD-I cohort B | participant 8–15，双腕，16 tables | 0.2439 | 5/28/3 | 0.625 | 正向，FP -4 |
| FD-II cohort A | participant 0–7，双腕，16 tables | 0.1224 | 3/38/5 | 0.375 | 负向，暂不采用 |
| FD-I full | participant 0–33，双腕，68 tables | 0.1071 | 3/45/5 | 0.375 | 负向，触发 kill gate |
| FD-I full balanced | participant 0–33，双腕，68 tables，每序列最多 512 windows | 0.1778 | 4/33/4 | 0.500 | 接近但未超过 baseline gate |

FD-I 两个不重叠 bounded cohort 的 F1 都高于 target-only，且 Recall 都从 0.50 提升到 0.625；但 full FD-I 不成立。full FD-I 不限采样的 threshold `0.10/0.15/0.20/0.25/0.30/0.35` 对应 F1=`0.1176/0.1017/0.1071/0.1111/0.1154/0.1224`，没有恢复 baseline。full FD-I balanced-512 的 threshold sweep 最好为 `0.2174`（threshold=`0.15`），而 target-only 同一 threshold 为 `0.2000`，增益小于预设 `+0.02` gate。bounded cohort B 的 threshold sweep 为 `0.10/0.15/0.20/0.25/0.30` 对应 F1=`0.1509/0.2128/0.2439/0.2500/0.2000`；因此 bounded 正向现象存在，但不能外推为 full-data route 成功。

## Critical assumptions

1. FD-I 的 eating gesture 点标签映射为“窗口内出现 label 1 即 positive”在小 cohort 上有迁移信号，但 full FD-I 失败，说明该假设不足以支撑全量预训练。置信度：低到中等。
2. 外部特征必须与 target 特征契约一致。已通过 64 Hz → 10 Hz 重采样后复用同一 111 维特征提取器；适配器测试和真实样本有限值检查通过。置信度：较高。
3. FD-II 的 0 标签可直接当作 target negative。证据相反：FD-II 预训练 F1=`0.1224`，低于 baseline；其“只标注 meal session”的语义会产生 label/domain mismatch。置信度：低，因此当前不采用该假设。

## Risks

- 当前只覆盖一个 target split 和两个 FD-I cohort，仍可能存在 split 偶然性。
- 外部预训练改善 candidate recall，但 event 边界 MAE 没有一致改善；最终高分路线仍需要 OOF event verifier/decoder。
- full FD-I 特征化有较高 I/O、内存和时间成本；本次全量两种采样策略均未通过收益 gate。
- FD-II 的未标注区域不能安全地作为普通 negative；混入会制造负迁移。
- 只比较了一个轻量 Transformer 容量/正则化配置；不得把该结果外推为所有 Transformer 架构结论。

## Validation experiments

- 数据契约：通过；外部目录为 `E:\bme_compitition\external-dataset`，未被 Git 跟踪。
- target-only baseline：通过；固定 split 上 F1=`0.1818`。
- FD-I cohort A pretrain → target fine-tune：通过；F1=`0.2083`。
- FD-I cohort B pretrain → target fine-tune：通过；F1=`0.2439`。
- FD-II cohort A pretrain → target fine-tune：失败 gate；F1=`0.1224`。
- full FD-I pretrain → target fine-tune：失败 gate；F1=`0.1071`。
- full FD-I balanced-512：失败收益 gate；F1=`0.1778`，threshold sweep 最好 `0.2174`，仍未达到 baseline + 0.02。
- threshold sensitivity：bounded FD-I cohort B 有正向差异，但 full FD-I 的 threshold sweep 不能恢复 baseline。
- submission isolation：通过；submission runner 无 external/FD-I/FD-II 引用。

## Kill criteria

- 完整 FD-I 训练后，在同一 target split F1 不高于 baseline 至少 0.02，或 Recall 下降超过 0.05：停止外部预训练路线。
- F1 没有正增益且 FP 增加超过 20%：停止该配置，转向 candidate/verifier 或标签重映射。
- 任何提交推理路径读取外部数据：立即回退到 target-only checkpoint。
- FD-II 继续以当前“窗口内 label 1 为正、其余为负”的映射训练且没有解决未标注语义：不进入正式训练。

## Recommendation

**NO-GO**：当前“FD-I 全量窗口预训练 → target Transformer 微调”的路线不进入正式高分管线；full FD-I 和 balanced-512 都未通过收益 gate，FD-II 还出现负迁移。bounded FD-I 的正向结果保留为重设计线索，后续若继续，只能改变采样/标签映射/模型训练策略并重新建立独立验证证据；当前官方提交继续使用 target-only/已有 verifier 路线。

## Confidence

较高（约 0.85）。full FD-I、balanced-512、FD-II 和多个 threshold 已覆盖主要当前路线；剩余不确定性是更换标签/采样/模型结构后的新路线，不属于本次已验证路线。
