# 外部数据独立 Preflight：2026-09-11

## Goal

判断外部 FD 数据的训练-only 预训练是否值得进入下一阶段，以提高官方目标集的 event-level F1；外部数据不能进入官方 test、提交文件或提交推理路径。

## Success metrics

- 主指标：固定 participant-frozen target validation split 上的 event-level F1。
- 辅指标：event TP/FP/FN、Recall、start/end MAE、最差 participant F1。
- 接受条件：相同 target split、相同 Transformer 配置下，外部预训练相对 target-only baseline 的 F1 有稳定正增益，且不是依靠明显增加 FP 换取；外部数据不被 submission runner 读取。
- 当前结果只代表 bounded spike，不代表官方测试集分数或排行榜上限。

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

FD-I 两个不重叠 cohort 的 F1 都高于 target-only，且 Recall 都从 0.50 提升到 0.625。threshold sweep 在 FD-I cohort B 上的结果为：`0.10/0.15/0.20/0.25/0.30` 对应 F1=`0.1509/0.2128/0.2439/0.2500/0.2000`；target-only 同一 checkpoint 对应 `0.1724/0.2000/0.1818/0.1429/0.0952`。这支持 FD-I 的增益不只是某一个固定 threshold 的偶然结果。

## Critical assumptions

1. FD-I 的 eating gesture 点标签映射为“窗口内出现 label 1 即 positive”是可迁移的。证据：两个不重叠 FD-I cohort 都提升 Recall 和 F1。仍需在完整 FD-I 和更大 target split 上复验。置信度：中等。
2. 外部特征必须与 target 特征契约一致。已通过 64 Hz → 10 Hz 重采样后复用同一 111 维特征提取器；适配器测试和真实样本有限值检查通过。置信度：较高。
3. FD-II 的 0 标签可直接当作 target negative。证据相反：FD-II 预训练 F1=`0.1224`，低于 baseline；其“只标注 meal session”的语义会产生 label/domain mismatch。置信度：低，因此当前不采用该假设。

## Risks

- 当前只覆盖一个 target split 和两个 FD-I cohort，仍可能存在 split 偶然性。
- 外部预训练改善 candidate recall，但 event 边界 MAE 没有一致改善；最终高分路线仍需要 OOF event verifier/decoder。
- full FD-I 特征化有较高 I/O、内存和时间成本；bounded 8-participant cohort 已可运行，但尚未宣称全量训练收益。
- FD-II 的未标注区域不能安全地作为普通 negative；混入会制造负迁移。
- 只比较了一个轻量 Transformer 容量/正则化配置；不得把该结果外推为所有 Transformer 架构结论。

## Validation experiments

- 数据契约：通过；外部目录为 `E:\bme_compitition\external-dataset`，未被 Git 跟踪。
- target-only baseline：通过；固定 split 上 F1=`0.1818`。
- FD-I cohort A pretrain → target fine-tune：通过；F1=`0.2083`。
- FD-I cohort B pretrain → target fine-tune：通过；F1=`0.2439`。
- FD-II cohort A pretrain → target fine-tune：失败 gate；F1=`0.1224`。
- threshold sensitivity：通过；FD-I cohort B 在 `0.20–0.25` 都高于 target-only 对应 checkpoint。
- submission isolation：通过；submission runner 无 external/FD-I/FD-II 引用。

## Kill criteria

- 完整 FD-I 训练后，在同一 target split F1 不高于 baseline 至少 0.02，或 Recall 下降超过 0.05：停止外部预训练路线。
- F1 没有正增益且 FP 增加超过 20%：停止该配置，转向 candidate/verifier 或标签重映射。
- 任何提交推理路径读取外部数据：立即回退到 target-only checkpoint。
- FD-II 继续以当前“窗口内 label 1 为正、其余为负”的映射训练且没有解决未标注语义：不进入正式训练。

## Recommendation

**GO WITH RISKS**：只保留 FD-I 作为训练-only 预训练候选，进入下一阶段的全量 FD-I / target verifier 对照；暂时排除 FD-II，不把外部 Transformer checkpoint 直接当作最终提交模型。

## Confidence

中等（约 0.70）。两个不重叠 FD-I cohort 给出一致正向信号，但 target split 数量和 candidate-only 结构仍限制了结论强度。
