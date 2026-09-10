# 智能手表进食检测第二版 Preflight

日期：2026-09-10  
状态：Preflight 完成，等待高分架构 spike 验收  
工作区：`E:\bme_compitition\bme_compitition_next`

## Goal

从第一天起围绕官方测试集的事件级 F1 做高分路线。稳定性、可复现性和学习性仍然是硬约束，但不再把“先做一个容易学习的 1D CNN 基线”作为主要产品目标。

## Success metrics

主指标：官方测试集事件级 F1。竞赛定义为预测事件与真实事件 IoU 严格大于 0.25 才算 TP，并据此计算 Precision、Recall 和 F1；起止时间 MAE 为辅助指标。

本地选择指标：同一 participant-frozen split 上的事件级 F1，辅以 Precision、Recall、participant 均值/标准差/最差值、长时间连续 FP 比例、start/end MAE 和推理成本。当前没有官方测试集分数，不能把本地分数称为官方结果。

## Constraints

- 原始数据约 93 GB，只读、流式或缓存处理，不复制进本工作区，不加入 Git。
- 必须按 participant 划分，test 不参与训练、阈值选择、架构选择或误差分析。
- 数据包含 ACC、GYRO、44 路 PPG，存在重复时间戳、时间戳为 0、模态覆盖不完整和部分不可解析文件。
- 训练和推理必须使用相同的时间轴、质量掩码、归一化和窗口/序列契约。
- GPU 约 8 GB；模型必须采用分块或多分辨率长上下文，不能把全天原始信号一次放入显存。
- 截止日期和竞赛评审要求使得实验必须可复现、可比较、可停止。

## Prior art and current evidence

本地论文说明支持 IMU、PPG、较长窗口和数据选择作为候选方向，但不证明它们适合本数据集。上一版真实实验是更强的本地证据：

| 结果 | 证据 |
|---|---:|
| M0 q50 + GroupNorm | event F1 = 0.17284 |
| M1 原始 IMU/PPG fusion | event F1 = 0.16867 |
| M1 validation 事件 | TP/FP/FN = 21/177/30 |
| M1 起始时间 MAE | 约 637875 ms |
| M1 FP 形态 | 主要是分钟级长连续误检，不是短暂抖动 |
| clean-quality M1 | F1 = 0.06780，质量过滤没有解决长 FP |

旧 worktree 中没有真正训练过 `M2 context model`。已完成的是 M1 的 threshold/decoder、fusion、pooling、loss、模态可用性和质量过滤实验，以及用于决定是否启动 M2 的 gate。因此本轮应将结论表述为：

> 局部窗口独立打分再依赖 threshold/merge 后处理的路线已被证据否定；不是所有 1D CNN 编码器都被否定。

### Spike 0 抽样审计结果

对一个训练文件和一个 `test` 文件各读取前 2000 行，没有扫描全量数据：

- 表头为 53 列：3 个时间列、44 个 PPG 列、3 个 ACC 列和 3 个 GYRO 列。
- 训练样本中 ACC/GYRO 只有 186 个唯一时间戳，1814 行重复；PPG 只有 31 个唯一时间戳，1969 行重复。
- test 样本中 ACC/GYRO 只有 187 个唯一时间戳，1813 行重复；PPG 只有 30 个唯一时间戳，1970 行重复。
- 两个样本都出现时间戳为 0；训练样本 PPG 时间戳为 0 的行约 1550/2000，test 约 1565/2000。
- PPG 非零通道在抽样中呈现 0 或 20 路，而不是稳定的 44 路有效波形。
- 餐段表共有 288 行、44 个 external ID，其中 7 条记录反序或零时长；`test` 有餐段记录，不能因为它出现在元数据中就把它当训练/验证数据。

这些数字是抽样审计，不是全量统计；它们已经足以阻止“把每一行当成一个等间隔采样点”的实现。

## Baseline

当前可信本地参照为 M0 q50 + GroupNorm，event F1=0.17284。M1 没有超过它。旧实验的分数只用于架构判断，不作为新工作区的最终 baseline，直到新工作区能够复现数据、split、指标和关键产物。

## Additional team evidence

两份队友仓库提供了比旧 M0/M1 更接近高分目标的证据，但分数必须按各自协议复核，不能直接当作官方测试分数：

1. `BMEcontest-2` 使用真实时间戳、240 秒全覆盖滑窗、15 秒步长、候选密度聚合和事件级复核器；TCN 主要作为候选窗口的辅助深度分。其 README 报告干净 participant-disjoint 协议下 TCN 方案均值约 0.505、全局聚合约 0.512，并明确废弃过泄漏协议下的 0.617。该仓库还记录了时间轴漂移和事件右端膨胀 bug，说明评估协议本身就是高风险变量。
2. `Eating-Detaction` 使用 15 秒密集网格、ACC/GYRO 手工特征、LightGBM 窗级分数、事件级二审和嵌套 participant 验证，README 报告诚实 nested F1=0.652，且废弃了稀疏网格产生的 0.922 假象。其最大收益来自事件化参数和二阶事件过滤，而不是继续堆叠模型容量。

因此主路线更新为：

```text
真实时间戳恢复
→ 密集、无缺口跨越的全覆盖 chunk/window
→ 高召回候选层
→ TCN/统计特征/轻量上下文模型作为候选评分
→ 事件级复核与序列约束
→ 官方 IoU/F1
```

TCN 仍然保留，但作为候选评分或事件级复核的一部分，而不是让一个局部 TCN 单独承担全天事件检测。

## External data policy and plan

外部数据值得尝试，但只允许通过受控实验进入：

### 首选：FD-I/FD-II

KU Leuven 的 FD 数据包含约 513 小时、61 名参与者的自由生活 IMU 数据，公开提供 FD-I、FD-II 和 MO 文件，许可证为 CC-BY-NC-ND-4.0。它与本题在 IMU、自由生活进食和事件检测方面最接近，但采样率约 64 Hz、设备为 Shimmer3、标签更细，仍存在域差异。

第一用途是外部预训练局部 encoder/TCN，再只用赛题 participant 微调；不要直接把 FD 的标签当作本题餐段标签。

### 次选：WIMID

WIMID 约 528 小时、11 名参与者、159 顿餐，约 100 Hz，主要是惯用手 IMU。它和本题采样率更接近，但只有单侧 IMU，且 Zenodo 页面标明版权归 Jožef Stefan Institute，不能把“可下载”自动等同于“可用于竞赛提交”。

### 后置：FIC/OREBA/MO 等餐内手势数据

这些数据的标签更细，适合训练 bite/gesture encoder；但它们通常是餐内或半受控场景，与本题全天自报餐段的任务不同。只能作为辅助表征预训练，不能直接当作 episode 监督数据。

### 外部数据实验顺序

1. `target_only`：赛题数据从头训练，作为严格对照。
2. `external_pretrain → target_finetune`：外部数据只用于预训练，验证和阈值只使用赛题 train/inner split。
3. `joint_train`：外部与赛题数据按固定比例联合训练，只在前两步证明外部表征有效后运行。
4. `self_supervised`：如果监督标签映射始终不稳定，再考虑跨数据集无标签重构/对比预训练。

接受条件：外部预训练必须在相同 participant-frozen split 上提高赛题事件 F1，且不能明显增加 participant 波动、边界 MAE 或长 FP；否则只保留为负结果。每个外部数据集、预训练任务和混合比例都必须单独记录。

竞赛提供的 PDF 没有明确写出“外部数据允许”或“外部数据禁止”。因此在获得组委会书面确认前，外部数据只能作为本地研究/预训练实验；最终提交应披露数据集、许可证、预训练方式，并确保提交包不违反数据再分发条款。

## Candidate approaches

### A. 推荐：全覆盖候选层 + 事件级复核

先按真实时间戳生成不跨缺口的密集长窗口，候选层只追求高 Recall；再用候选内部形态、前后上下文、会话状态和 TCN/统计特征进行事件级复核，最后用事件序列约束和官方 IoU/F1 解码。它直接针对旧版“局部窗口高分长 FP”和候选覆盖不足两个问题。

### B. 备选：层级式长上下文神经分割

局部 encoder 只提取 chunk 表示，不直接决定最终事件；在 chunk 序列上使用 dilated TCN、轻量 Transformer 或混合上下文模块，输出 eventness 与 start/end boundary。它作为 A 的神经候选评分器或独立对照，而不是一开始替换整个事件管线。

### C. 后置：anchor-free temporal event proposal

模型直接预测 eventness、startness、endness 或 duration，再通过 proposal matching 产生事件，减少对单一 threshold 的依赖。它更贴近官方事件级目标，但标签转换、损失和匹配复杂度最高，只有 A/B 的证据不足时才进入。

### C. 备选：anchor-free temporal event proposal

模型直接预测 eventness、startness、endness 或 duration，再通过 proposal matching 产生事件，减少对单一 threshold 的依赖。它更贴近官方事件级目标，但标签转换、损失和匹配复杂度最高，只有 A/B 的证据不足时才进入。

暂不优先：直接把全天原始序列输入 Transformer、复杂跨模态注意力、外部预训练或继续在 M1 上反复调 threshold/loss。这些方向无法先回答长 FP 的根因，且容易把数据问题和架构问题混在一起。

## Critical assumptions

1. 长 FP 的主要原因是局部窗口模型缺少事件级上下文，而不是所有可学习信号都不存在。支持证据：M0 概率正负窗口仍有分离；多轮 threshold、loss、质量和 pooling 变化无法消除分钟级 FP。置信度：中等。
2. 已有时间轴、标签和 IoU 代码足以作为新架构的输入契约，但必须在新工作区重新做小样本等价性验证。置信度：中等。
3. chunk 表示序列可以在 8 GB GPU 上训练，并且不会因 participant 边界、文件边界或缺失模态产生新的 shortcut。置信度：中低。
4. 训练 participant 的事件数量足以支持上下文模型；若不够，需要强正则、跨文件序列构造或事件级增强，而不是盲目增加模型容量。置信度：未知。

## Risks

- 长上下文模型可能只是学到一天中的时间段、文件边界或模态覆盖模式。
- 事件标签是区间级标签，内部可能含有非进食间隔；过强的 dense loss 会把标签噪声放大。
- 长序列采样会产生严重类别不平衡，局部 batch loss 可能与事件 F1 不一致。
- chunk overlap、序列截断和文件边界处理不正确会造成事件重复或边界偏移。
- 本地 split 与官方隐藏测试分布仍可能不同。

## Validation experiments

### Spike 0：新工作区闭环复现

只读取少量 participant 和 test 目录，确认文件索引、时间戳、质量 mask、标签区间、窗口/chunk 边界和 IoU/F1 与旧版参考产物一致。验收前不进行全量训练。

### Spike 1：全覆盖候选层闭环

先不训练复杂模型，使用真实时间戳构造 240 秒左右的密集滑窗，验证不跨缺口、候选覆盖率、短餐覆盖率、正负比例和事件 IoU 可达性。候选层的验收指标是“漏掉多少真实事件”，不是最终 Precision。

### Spike 2：事件级复核对照

在同一候选集合上比较简单统计复核器、TCN 深度分和轻量上下文模型。所有模型使用严格 nested participant split；阈值只在 inner OOF 选择。记录候选 Recall、最终 event F1、长 FP、短餐 Recall、非惯用手 Recall 和边界 MAE。

### Spike 3：外部预训练消融

在 Spike 2 的固定 target pipeline 上只比较 `target_only` 与 `FD_pretrain → target_finetune`。若外部预训练不能在目标事件级 F1 上带来稳定收益，就不进行 joint training，也不再投入更多外部数据下载和映射成本。

## Kill criteria

- 新工作区无法复现数据/标签/IoU 参考结果：停止模型实验，归类为 `PIPELINE` 问题。
- 小数据无法让模型明显降低训练损失并区分正负事件：停止长训练，归类为 `PIPELINE` 或 `ASSUMPTION`。
- 长上下文模型只提高窗口指标、不提高事件 F1：停止该方向，归类为 `OBJECTIVE_MISMATCH`。
- 三个因果不同的长上下文假设都不能超过 M0/M1 参照：停止局部修补，执行架构/可行性复审。
- 任何方案使用 test 调阈值、选模型或选特征：该结果作废。

## Recommendation

SPIKE FIRST。新目标不再是“先实现 M0 再逐步加复杂度”，而是“先验证长上下文事件分割路线是否能在正确数据闭环上超过旧版参照”。M0/M1 只保留为数据和评估 sentinel，不作为本轮主架构终点。

## Confidence

中等。旧版实验对“局部窗口独立打分”的否定证据较强，但对最佳长上下文架构尚无本地测量，因此不能提前承诺 F1 提升幅度。

## Routing record

```text
workflow_path: RESEARCH
execution_mode: INLINE
execution_backend: null
scope: preflight and bounded architecture spike; no full implementation yet
budget: one bounded spike at a time; reassess after three materially different hypotheses
fallback: return to data/label/metric root-cause investigation
review/escalation: plateau, leakage, or three failed causal hypotheses triggers architecture review
```
