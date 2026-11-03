# 智能手表进食检测项目阶段性进度报告

**日期：** 2026-09-10  
**分支：** `codex/smartwatch-eating-baseline`  
**当前阶段：** M1 诊断与证据收敛，M2 尚未启动

## 1. 执行摘要

当前结论不是“官方数据不可学”，而是：

> 数据覆盖和质量管线存在真实问题，但当前 M1 的局部窗口建模和多模态融合方式是主要性能瓶颈。

M0 已经形成可复现的 q50 + GroupNorm 基线。M1 完成了 full frozen split 训练和多轮受控消融，但所有候选都没有满足 M2 evidence gate。最近的 clean-quality 对照实验进一步证明，单独过滤低质量窗口不能解决长时间连续误检，反而暴露出模型对模态可用性分层的依赖。

## 2. 目标与门禁

项目当前遵守 M1-first 约束：在 M2 证据门禁通过前，不创建、不配置、不训练 M2。

M2 gate 要求同时满足：

1. 事件 Recall 严格大于 50%；
2. 至少 50% 的误检是短暂 FP，当前定义为持续时间不超过 30 秒且不超过 2 个窗口；
3. 有概率、有效性或区间上下文证据支持进入更高级模型。

截至本报告，最新 clean-quality 实验的 gate 状态仍为 `false`：Recall=`7.84%`，短暂 FP 占比=`6.35%`，没有上下文证据。

## 3. 数据、标签和预处理状态

### 已确认的事实

- 原始竞赛数据保持只读。preflight 记录的 2,378 个源文件全部未发生 size/mtime 变化。
- test 数据没有参与训练、阈值选择或误差分析。
- frozen participant split 未变化，SHA-256 为 `18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。
- train/validation 中枚举到 1,155 个传感器文件，1,121 个成功建立或命中 IMU cache，34 个文件无法正常使用：16 个为二进制或非 UTF-8 内容，18 个有效 timestamp 不足。
- `HNU21042` 的部分源文件 ACC/GYRO timestamp 为 0，导致该参与者 validation 中 6 个真实事件没有可用 IMU 输入。这是确定的数据覆盖问题。
- 原始 M1 paired dataset 之前没有使用和 M0 一致的 `quality >= 0.5` 窗口门槛。原 M1 validation 有 `320,830 / 593,589` 个 `neither` 窗口，约占 54.1%。

### 目前对数据可学性的判断

数据不能被判定为“不可学”：

- M0 验证概率的正负窗口均值分别约为 `0.5039` 和 `0.3586`，存在虽然有限但可观测的分离；
- M0 离线阈值扫描在阈值 `0.2` 时窗口 Recall 达到约 `70.6%`，但 Precision 只有约 `1.88%`，说明信号存在，问题在于区分度和校准不足；
- 标签审计得到 281 个正常标签、4 个反向或交换标签、3 个零时长标签被排除，没有发现大规模端点缺失。

因此，当前更准确的表述是：数据有缺失覆盖、参与者差异和标签/窗口粒度带来的困难，但不是完全没有可学习信号。

## 4. 基线和实验结果

| 实验 | 主要变量 | Precision | Recall | F1 | 结论 |
|---|---|---:|---:|---:|---|
| 原始 M0/P0 | 初始 IMU-only pipeline | 0.01996 | 0.64706 | 0.03873 | 低校准 baseline |
| M0 q50 + GroupNorm | 质量筛选、实际窗口 `pos_weight` | 0.10938 | 0.41176 | 0.17284 | 当前 M0 参照 |
| M1 原始 fusion | concat、global BCE、avg pooling | 0.10606 | 0.41176 | 0.16867 | 177 个 FP，主要为长连续误检 |
| M1 availability-stratified BCE | 分层 prior | 0.06685 | 0.47059 | 0.11707 | 改善 neither shortcut，但未解决 both 长 FP |
| M1 avgmax pooling | temporal pooling 变体 | 0.04583 | 0.54902 | 0.08459 | Recall 超过 50%，但短 FP 仅 4.97% |
| M1 logit-mean + 分层 BCE | logit-level fusion | 0.03469 | 0.66667 | 0.06596 | Recall 提升，长 FP 仍占主导 |
| M1 clean-quality | 唯一新增 `quality >= 0.5` 过滤 | 0.05970 | 0.07843 | 0.06780 | 清洗本身不能解决问题，候选淘汰 |

此前还验证过 shared-mean、normalized-mean、固定 prior、focal BCE、unweighted BCE、modality dropout、temporal bins、negative-run penalty 和 logit-min 等方向。它们分别出现 Recall 崩塌、observed-modality 高正率、长 FP 未消除或短 FP 不占主导等问题，均未满足 M2 gate。

## 5. 最近一轮 clean-quality 诊断

本轮只增加了 `PairedCachedWindowDataset.min_quality_fraction`，默认值仍为 `0.0`，专项配置使用 `0.5`。其余模型、loss、decoder、cache、seed 和 frozen split 保持不变。

结果：

- train/validation windows=`1,306,197 / 271,724`；相比原 M1 validation 少 `321,865` 个窗口，质量门槛确实生效；
- IMU/PPG cache 均为 `1121/1121 hit`；
- TP/FP/FN=`4/63/47`；
- F1=`0.06780`，Recall=`0.07843`；
- `both` 窗口 predicted-positive rate=`0.039%`，FPR=`0.041%`；
- `imu_only` 窗口 predicted-positive rate/FPR 均为 `100%`；
- FP 中只有 `4/63=6.35%` 为短暂 FP，绝大多数仍不是局部抖动。

这说明质量问题真实存在，但不是长 FP 的充分解释。模型在不同模态覆盖层上的输出完全失衡，更像是在利用“哪些模态存在”这一 shortcut，而不是稳定识别进食事件。

## 6. 根因判断

### 已确认的数据问题

1. M1 原先没有严格复用 M0 的质量窗口契约；
2. 部分 participant/file 缺失有效 IMU 时间戳；
3. 大量窗口处于模态不可用或不完整状态；
4. 15 秒局部窗口与事件级目标之间存在天然粒度差异。

### 目前更可能的主要瓶颈

当前 M1 使用局部窗口 encoder、全局池化和多模态 concat fusion。该结构对模态缺失和质量分层很敏感，也没有足够的事件级长时序上下文。多个受控实验都显示，误检通常是数十分钟级的连续段，而不是短暂窗口噪声。

所以当前判断为：

> 数据集是“有噪声且覆盖不完整，但存在信号”；当前 M1 是“能训练，但学到的主要是模态/覆盖先验，无法稳定完成事件级检测”。

这还不能证明某个新架构一定能达到 M2，只能证明继续在当前 fusion 上盲目调 loss、阈值或 pooling 的收益很低。

## 7. 已完成的工程工作

- 完成 M0 full-data cache、质量筛选、GroupNorm 和 frozen split 复现闭环；
- 完成 M1 paired cache、PPG cache、fusion 训练和独立 error analysis；
- 为 M1 增加质量门槛参数，并补充 CLI 配置转发；
- 按 TDD 先写 RED 测试，再完成实现，专项 M1 测试 `5 passed`；
- 全套测试 `150 passed`；
- `compileall`、`git diff --check` 通过；
- CUDA smoke 通过：RTX 5060 Laptop GPU，`SMOKE_PASS device=cuda steps=2`；
- README、handoff 和 M1 execution record 已更新；
- M2 相关源码、配置、测试和训练产物仍未创建。

## 8. 当前保留状态

- 当前最佳可复现实验参照仍是 M0 q50 + GroupNorm，F1=`0.17284`；
- 当前 M1 原始 fusion 的 F1=`0.16867`，但未通过 M2 gate；
- clean-quality run 只作为诊断证据，不作为最终性能方向；
- 外部开源数据暂不引入。此时引入会同时改变数据分布、设备域和标签协议，无法先回答“架构还是预处理”的问题；
- 工作树仍包含前几轮实验代码、配置和文档修改，尚未做最终整合提交或推送。

## 9. 下一步建议

下一步应继续停留在 M1，按以下顺序收敛：

1. 在同一 clean-quality frozen split 上做 IMU-only、PPG-only 和简单线性 probe，确认信号是否在不经过当前 fusion 的情况下可分；
2. 检查窗口标签、时间对齐和特征统计，特别关注正事件附近与长时间负段的分布；
3. 若线性 probe 能学到而当前 M1 学不到，再只改变 M1 的事件级时序建模，不叠加新数据和新 loss；
4. 只有当 Recall、短 FP 主导和上下文证据三项同时满足，才允许创建 M2。

## 10. 主要复现入口

```powershell
conda activate smartwatch-eating
python -m pytest -q
python scripts/verify_environment.py --require-cuda --steps 2
python -m eating_detection.error_analysis `
  --run-dir artifacts/m1_fusion_clean_quality_e1 `
  --cache-dir cache/m0_full `
  --ppg-cache-dir cache/m1_ppg `
  --comparison-run-dir artifacts/m0_final_q50_group_e3 `
  --output artifacts/experiments/m1_fusion_clean_quality_e1/error_analysis.json
```

相关产物：

- [clean-quality 配置](../configs/experiments/m1_clean_quality_e1.yaml)
- [clean-quality metrics](../artifacts/m1_fusion_clean_quality_e1/metrics.json)
- [clean-quality error analysis](../artifacts/experiments/m1_fusion_clean_quality_e1/error_analysis.json)
- [handoff 摘要](../handoff-summary.md)
- [M1 执行与门禁记录](superpowers/plans/2026-09-06-m1-execution-record.md)
