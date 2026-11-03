# M1 执行与门禁记录

## M1 clean-quality diagnostic（2026-09-09，数据管线假设未证实；M2 gate 仍 false）

### 事实

- 为区分数据质量/覆盖与架构根因，只新增 paired M1 dataset 的 `min_quality_fraction` 参数，使其可以复用 M0 的 IMU `quality >= 0.5` 窗口标准；未引入外部数据、未重训 M0、未读取 test、未创建或运行 M2。
- TDD：先加入 paired dataset 过滤测试并确认现状 RED（缺少参数），再实现最小过滤；CLI 配置转发也先通过 RED 验证。M1 专项=`5 passed`，全套=`150 passed`，`compileall`、`git diff --check`、CUDA smoke 通过。
- 配置=`configs/experiments/m1_clean_quality_e1.yaml`，full run=`artifacts/m1_fusion_clean_quality_e1/`；原始 `concat`、global BCE、avg pooling、dropout、decoder、seed、cache 和 frozen split 保持不变，唯一变量是 `m1_min_quality_fraction=0.5`。CUDA batch=`16`，训练=`3918.25 s`，epoch=`1303.15/1308.60/1305.79 s`，IMU/PPG cache=`1121/1121 hit`，test 未读取。
- clean run train/val windows=`1,306,197/271,724`；独立 error analysis=`artifacts/experiments/m1_fusion_clean_quality_e1/error_analysis.json`，validation probability 与 cache unmatched=`0`，cache rows unused=`321,865`。
- 独立报告 TP/FP/FN=`4/63/47`，P/R/F1=`0.0597015/0.0784314/0.0677966`，participant mean/std/worst=`0.0689078/0.0714318/0`，start/end MAE=`694011/144528 ms`；短暂 FP=`4/63=6.34921%`，`both` predicted-positive rate/FPR=`0.0390493%/0.0407640%`，`imu_only`=`100%/100%`。
- frozen M0 对照仍为 TP/FP/FN=`21/171/30`、P/R/F1=`0.109375/0.4117647/0.1728395`。原始 M1 fusion 为 TP/FP/FN=`21/177/30`、P/R/F1=`0.1060606/0.4117647/0.1686747`。

### 风险、假设与选择

- quality gate 生效并移除了 M1 原 validation 中约 54.1% 的低质量/不可用窗口，但没有改善 event F1 或 long-FP gate；clean run 中 `both` 几乎全被压为负、`imu_only` 全为正，说明原始 M1 的模态分层/融合行为对窗口覆盖分布高度敏感。
- 因此 `neither` 窗口和 `hnu21042` 的无 IMU 覆盖是确定的数据问题，但不是长 FP 的充分解释；M0 在合格 IMU 窗口上仍有可学习信号，官方数据不能判为“不可学”。
- 本轮只作为诊断证据，不把 clean-quality 过滤单独选为最终 M1 性能方向；后续应先保持该质量契约，再单独验证具有事件级长时序上下文的架构。M2 仍不创建、不配置、不训练。

### 实验结果

- M2 gate=`false`：Recall=`0.0784314` 未超过 50%，短暂 FP 占比=`6.34921%` 未达到 50%，且没有 probability/validity/interval context 证据。
- 结论：官方数据可学，但当前 M1 架构/融合不能把局部信号稳定转换为事件级预测；数据覆盖问题先修，时序架构是主要性能瓶颈。

## M1 logit-mean + availability-stratified BCE remediation 复验（2026-09-08，候选淘汰）

### 事实

- 在 frozen split 上完成 `logit_mean` fusion + train-only availability-stratified BCE 的 3-epoch CUDA run，保持 batch=`16`、avg pooling、dropout、decoder、双 cache 和 seed；未读取 test、未重训 M0、未创建/运行 M2。
- full run=`artifacts/m1_fusion_logit_mean_availability_e1/`，训练=`8509.22 s`，epoch=`2837.09/2831.45/2839.46 s`，windows=`3,578,835`（train=`2,985,246`、val=`593,589`），cache=`1121/1121 hit`，stderr 为空。
- 独立 error analysis=`artifacts/experiments/m1_fusion_logit_mean_availability_e1/error_analysis.json`：TP/FP/FN=`34/946/17`，P/R/F1=`0.0346939/0.666667/0.0659554`，participant mean/std/worst=`0.0578241/0.0315472/0`，start/end MAE=`492860.1/104338.2 ms`；FP duration median/p90/max=`162000/2178074/12011694 ms`，window median/p90=`45/717`，short FP=`62/946=6.55391%`。
- `both` predicted-positive rate/FPR=`89.2959%/88.9624%`、`imu_only`=`88.9489%/88.3845%`、`neither`=`0%`；split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`，source CSV/test 均未读取。

### 风险、候选、验收标准、选择

- Recall 严格超过 50%，但 short-FP dominance=`false`，probability/validity/interval context support=`false`，M2 gate=`false`。分层 prior 只能降低 observed-modality 平均概率，不能消除长 FP。
- 下一候选只改变 fusion 为 conservative `logit_min`：both 窗口取 IMU/PPG 两个 logit 的最小值，single-modality 使用唯一可用 logit，neither 使用缺失先验；不叠加新 loss、decoder 或 M2 context。

## M1 logit-mean fusion remediation 复验（2026-09-08，候选淘汰）

- `artifacts/m1_fusion_logit_mean_e1/`：global BCE、3 epoch CUDA、训练=`8127.87 s`，epoch=`2706.26/2710.42/2709.94 s`。
- 独立 error analysis：TP/FP/FN=`31/882/20`，P/R/F1=`0.033954/0.607843/0.0643154`，short FP=`63/882=7.14286%`；`both` predicted-positive rate/FPR=`92.9309%/92.6775%`，`imu_only`=`82.9497%/82.1583%`。
- Recall 虽为=`60.7843%`，但 decoder sweep 在 Recall>50% 时 short-FP fraction 最高仅=`13.6914%`；M2 gate=`false`，下一轮验证 availability-stratified BCE 组合。

## M1 avgmax pooling remediation 复验（2026-09-08，候选淘汰）

- `artifacts/m1_fusion_avgmax_pooling_e1/`：只改变 pooling 为 `avgmax`，训练=`8518.02 s`，epoch=`2817.10/2841.92/2857.74 s`。
- 独立 error analysis：TP/FP/FN=`28/583/23`，P/R/F1=`0.0458265/0.549020/0.0845921`，short FP=`29/583=4.97427%`，Recall=`54.9020%`；`both` FPR=`94.7949%`、`imu_only` FPR=`81.3872%`，长 FP 仍主导，M2=`false`。
- decoder sweep 无 gate 候选；下一轮验证 logit-level conservative fusion。

## M1 negative-run BCE e2 remediation 复验（2026-09-07，候选淘汰）

- `artifacts/m1_fusion_negative_run_bce_e2/`：train-only negative-run cap=`16.0`，训练=`8684.75 s`，epoch=`2906.57/2916.91/2860.02 s`。
- 独立 error analysis：TP/FP/FN=`19/142/32`，P/R/F1=`0.118012/0.372549/0.179245`，short FP=`0/142=0%`，long FP median=`3318113.5 ms`；压低长 FP 但 Recall 不足，M2=`false`。

## M1 no-modality-dropout remediation 复验（2026-09-07，候选淘汰）

### 事实

- 只改变训练期 `m1_modality_dropout=0.0`，保持原 concat fusion、global train-only BCE、avg pooling、decoder、双 cache、seed 和 frozen split；未读取 test、未重训 M0、未创建/运行 M2。
- full run=`artifacts/m1_fusion_no_modality_dropout_e1/`，3 epoch CUDA、batch=`16`、`test_not_used=true`，windows=`3,578,835`（train=`2,985,246`、val=`593,589`），IMU/PPG cache=`1121/1121 hit`；训练=`7862.23 s`，epoch=`2630.11/2618.98/2611.87 s`，GPU max allocated=`38.60 MB`。
- 独立 error analysis=`artifacts/experiments/m1_fusion_no_modality_dropout_e1/error_analysis.json`：TP/FP/FN=`25/418/26`，P/R/F1=`0.0564334/0.4901961/0.1012146`，participant mean/std/worst=`0.0933466/0.0661283/0`，start/end MAE=`674733.8/86950.4 ms`；FP duration median/p90/max=`289500/5910860.2/23359557 ms`，window median/p90=`87.5/1939.3`，short FP=`19/418=4.54545%`。
- calibration binary/soft Brier/ECE=`0.2757563/0.3258336`、`0.2758124/0.3261898`；`both` predicted-positive rate/FPR=`97.1390%/97.0148%`，`imu_only`=`88.8824%/88.2881%`，`neither`=`0%`。报告 provenance split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`，source CSV/test 均未读取。

### 风险、候选、验收标准、选择

- no-dropout 没有消除 observed-modality 长连续 FP；short-FP dominance=`false`（`4.54545% < 50%`）、positive-event Recall=`49.0196%`（未严格大于 50%）、context support=`false`，M2 gate=`false`。
- 下一候选只考虑 train-only negative-run weighted BCE：以每个 train 文件内的连续负窗口 run 计算额外负样本权重，显式在文件/ignored-label 边界截断并设上限；不读取 validation/test，不叠加 decoder、M2 context 或新模型容量。
- 进入实现前必须完成 systematic debugging 与 TDD RED→GREEN：run segmentation 的边界/忽略标签、只使用 train metadata、权重上限、legacy `global_bce` 默认兼容和 batch loss 数值契约都要有测试；通过后才做 frozen full run 和独立 error analysis。M2 仍要求 short-FP≥50%、Recall严格>50%、context evidence 三项同时满足。

### 实验结果

- no-modality-dropout artifact 与独立报告作为失败证据保留；继续 M1，不创建或配置 M2。

## M1 normalized-mean remediation 复验（2026-09-07，候选淘汰）

### 事实

- TDD 专项=`15 passed`、全套=`140 passed`。只改变 fusion 为 modality-specific L2-normalized mean，保持 global BCE、avg pooling、`modality_dropout=0.25`、decoder、双 cache 和 frozen split；未读取 test、未重训 M0、未创建/运行 M2。
- full run=`artifacts/m1_fusion_normalized_mean_e2/`，3 epoch CUDA、batch=`16`、`test_not_used=true`，windows=`3,578,835`，IMU/PPG cache=`1121/1121 hit`；epoch loss=`0.6721980/0.6787165/0.7075065`，训练=`8194.78 s`，epoch=`2733.04/2730.38/2730.04 s`，GPU max allocated=`39.32 MB`。
- 独立 error analysis=`artifacts/experiments/m1_fusion_normalized_mean_e2/error_analysis.json`：TP/FP/FN=`21/179/30`，P/R/F1=`0.1050000/0.4117647/0.1673307`，participant mean/std/worst=`0.1461368/0.1056068/0`，start/end MAE=`615517.5/79659.7 ms`；FP duration median/p90/max=`1914000/12250816.2/24915528 ms`，window median/p90=`631/4066`，short FP=`6/179=3.35196%`。
- `both` predicted-positive rate/FPR=`100%/100%`，`imu_only`=`99.7133%/99.6977%`，`neither`=`0%`；binary/soft Brier/ECE=`0.2519498/0.3199287`、`0.2520053/0.3202849`。provenance split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`，未读取 source CSV/test。
- 只读 threshold sweep 仍不满足 gate：threshold=`0.20` 时 Recall=`51.1111%`、short-FP=`2.96053%`；threshold=`0.90` 时 short-FP fraction=`18.6579%`。

### 风险、候选、验收标准、选择

- normalized-mean 未满足 short-FP dominance、Recall 严格大于 50% 和 context support，M2 gate=`false`；不启动 M2。
- 下一轮只验证 `m1_modality_dropout=0.0`，恢复真实联合 modality 分布；保留原 concat、global BCE、avg pooling、decoder、cache 与 frozen split，不叠加 normalized/shared mean、fixed prior、avg4、强 dropout 或 M2 context。配置=`configs/experiments/m1_no_modality_dropout.yaml`，输出=`artifacts/m1_fusion_no_modality_dropout_e1/`。

### 实验结果

- normalized-mean artifact 与独立报告保留为失败证据；继续 M1。

## M1 shared-mean + both-prior BCE remediation 复验（2026-09-07，候选淘汰）

### 事实

- 在 shared-mean global BCE Recall=`52.9412%` 但长 FP 主导后，只选择 train `both` stratum prior calibration：`pos_weight=15.4561`，保留 shared-mean、global avg pooling、dropout、decoder、双 cache 与 frozen split。
- 专项 M1=`14 passed`、全套=`139 passed`。full run=`artifacts/m1_fusion_shared_mean_both_prior_e1/`，1121/1121 cache hit，3 epoch CUDA，batch=`16`，`test_not_used=true`；epoch loss=`0.3338849/0.3511153/0.3584828`，训练=`7635.24 s`。
- 独立 error analysis=`artifacts/experiments/m1_fusion_shared_mean_both_prior_e1/error_analysis.json`：TP/FP/FN=`37/1381/14`，P/R/F1=`0.0260931/0.7254902/0.0503744`，participant mean/std/worst=`0.0461866/0.0267140/0`，start/end MAE=`418557.2/115420.5 ms`；FP duration median/p90/max=`99000/1266000/12904228 ms`，short FP=`123/1381=8.90659%`。
- calibration binary/soft Brier/ECE=`0.1162751/0.1575266`、`0.1161367/0.1578828`；`both` predicted-positive rate=`84.3407%`、`imu_only`=`98.1678%`、`neither`=`0%`。

### 风险、候选、验收标准、选择

- prior shrink 改善 calibration 但造成大量碎片化 FP；Recall=`72.5490%` 通过，short dominance=`false`（`8.90659% < 50%`），context=`false`，M2 gate=`false`。
- 下一轮只选择 modality-specific normalized mean：两个 embedding 分别 L2 normalize 后再按 availability 求均值；恢复 global BCE，不叠加 fixed prior、avg4、dropout、decoder 或 M2 context。配置=`configs/experiments/m1_normalized_mean_fusion.yaml`。

### 实验结果

- both-prior artifact 作为失败证据保留；不创建或配置 M2，继续 M1。

## M1 shared-mean fusion remediation 复验（2026-09-07，候选淘汰）

### 事实

- systematic debugging 已确认 mask-detached、强 dropout 和 shared-mean 均不能消除 `both` 长连续 FP；本轮只验证 availability-invariant shared-mean：可用 modality embedding 求均值后接单一 head，不把 raw mask 或 zero-filled concat 送入 classifier/gate。
- TDD RED→GREEN 后专项 M1=`14 passed`、全套=`139 passed`。batch 64 首次 full run 在 epoch 2 因 host-side `numpy ArrayMemoryError` 中止，未使用该半成品；代码、数据、seed、split、cache、3 epoch 均保持不变，batch 16 重跑完整成功。
- full run=`artifacts/m1_fusion_shared_mean_e1/`，IMU/PPG cache=`1121/1121 hit`，windows=`3,578,835`，device=`cuda`，`test_not_used=true`；epoch loss=`0.5768392/0.6230866/0.6320540`，训练=`7530.31 s`，epoch=`2538.07/2480.00/2510.68 s`。
- 独立 error analysis=`artifacts/experiments/m1_fusion_shared_mean_e1/error_analysis.json`：TP/FP/FN=`27/342/24`，P/R/F1=`0.0731707/0.5294118/0.1285714`，participant mean/std/worst=`0.1074696/0.0613915/0`，start/end MAE=`420034.7/72489.3 ms`；FP duration median/p90/max=`375000/6992894.9/23399919 ms`，window median/p90=`121/2316.8`，short FP=`12/342=3.50877%`。
- calibration binary/soft Brier/ECE=`0.2679920/0.3252369`、`0.2680491/0.3255931`；`both` predicted-positive rate=`99.0136%`、`imu_only`=`90.1994%`、`neither`=`0%`。质量接近完整的窗口仍以长 FP 为主。

### 风险、候选、验收标准、选择

- shared-mean 使 positive-event Recall 严格超过 50%，但没有把错误变成短暂 FP：short dominance=`false`，只有 `3.50877% < 50%`；M2 context support=`false`，所以 M2 gate=`false`。
- 首次 batch 64 失败是 host-memory 运行问题，已通过同一候选 batch 16 完成闭环；不把 epoch-2 checkpoint 用作结果，也不改变 frozen evidence。
- 下一轮只选择 modality-specific normalized mean：保留 availability-invariant shared-mean 结构，对 IMU/PPG embedding 分别 L2 normalize 后再平均，恢复 global train-only BCE；配置=`configs/experiments/m1_normalized_mean_fusion.yaml`；不叠加 fixed prior、avg4、dropout、decoder 或 M2 context。

### 实验结果

- shared-mean global BCE artifact 作为失败证据保留；不创建或配置 M2，继续 M1。

## M1 strong modality-dropout remediation 复验（2026-09-07，候选淘汰）

### 事实

- 针对 raw availability mask shortcut，只选择 `m1_modality_dropout=1.0`，保留原 avg pooling、global BCE、raw mask、decoder、frozen cache 和 split。
- fresh 专项 M1=`27 passed`、全套=`138 passed`。full run=`artifacts/m1_fusion_strong_dropout_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- error analysis=`artifacts/experiments/m1_fusion_strong_dropout_e1/error_analysis.json`：TP/FP/FN=`19/142/32`，P/R/F1=`0.1180124/0.3725490/0.1792453`，participant mean/std/worst=`0.1531839/0.1095215/0`，start/end MAE=`839148.2/74066.6 ms`；short FP=`0/142=0%`。

### 风险、候选、验收标准、选择

- 强 dropout 后 `both` predicted-positive rate=`1.0`、`imu_only`=`0`，FP 全为长段，候选淘汰。
- M2 gate=`false`：short dominance=`false`、Recall=`37.2549%`、context=`false`；M3/M4=`false`。
- 下一轮只选择 availability-invariant shared-mean fusion：不将 raw mask 或零填充 concat 送入 classifier/gate，改为可用 embedding 的共享均值 head；不叠加 avg4、fixed prior、strong dropout、decoder 或 M2 context。

### 实验结果

- strong-dropout artifact 作为失败证据保留；不创建或配置 M2。

## M1 temporal-bin pooling remediation 复验（2026-09-07，候选淘汰）

### 事实

- 在 fixed-prior 淘汰后，针对全局平均池化丢失窗口内时序形状，只选择 `m1_pooling=avg4`；保持 global BCE、raw mask、`modality_dropout=0.25`、原 decoder、frozen cache 和 split。
- TDD RED→GREEN 后专项 M1=`13 passed`、全套=`138 passed`。full run=`artifacts/m1_fusion_temporal_pooling_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- error analysis=`artifacts/experiments/m1_fusion_temporal_pooling_e1/error_analysis.json`：TP/FP/FN=`22/255/29`，P/R/F1=`0.0794224/0.4313725/0.1341463`，participant mean/std/worst=`0.1175802/0.0839017/0`，start/end MAE=`851102.8/74506.0 ms`；short FP=`9/255=3.52941%`。

### 风险、候选、验收标准、选择

- avg4 后 `both` predicted-positive rate 仍=`1.0`，FP duration median/p90/max=`525000/9223489/24744528 ms`，且 calibration/F1 恶化，候选淘汰。
- M2 gate=`false`：short dominance=`false`、Recall=`43.1373%`、context=`false`；M3/M4=`false`。
- 下一轮只选择强 modality-dropout `p=1.0`，训练时每个 both 窗口随机保留一个 modality，针对 raw mask/availability prior；不叠加 avg4、fixed prior、decoder 或 M2 context。

### 实验结果

- avg4 artifact 作为失败证据保留；不创建或配置 M2。

## M1 fixed-prior BCE remediation 复验（2026-09-07，候选淘汰）

### 事实

- 在 focal-BCE 淘汰后，基于 train/validation `both` 正窗口率 `6.0768%/4.2129%` 的 prior shift，只选择 fixed prior `pos_weight=4.0`；原 fusion、BCE logits、decoder、frozen cache 和 split 均不变。
- TDD RED→GREEN 后专项 M1=`12 passed`、全套=`137 passed`。full run=`artifacts/m1_fusion_fixed_prior_bce_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- error analysis=`artifacts/experiments/m1_fusion_fixed_prior_bce_e1/error_analysis.json`：TP/FP/FN=`21/220/30`，P/R/F1=`0.0871369/0.4117647/0.1438356`，participant mean/std/worst=`0.1215559/0.0838309/0`，start/end MAE=`496446.0/79659.7 ms`；short FP=`8/220=3.63636%`。

### 风险、候选、验收标准、选择

- fixed prior 改善 calibration，但 `both` predicted-positive rate 仍=`1.0`，FP duration median/p90/max=`805500/11371933.5/24741528 ms`，候选淘汰。
- M2 gate=`false`：short dominance=`false`、Recall=`41.1765%`、context=`false`；M3/M4=`false`。
- 下一轮只选择 temporal-bin pooling `avg4`，针对全局平均池化丢失窗口内时序形状的根因；不叠加新的 loss、mask、decoder 或 M2 context。

### 实验结果

- fixed-prior artifact 作为失败证据保留；不创建或配置 M2。

## M1 focal-BCE remediation 复验（2026-09-07，候选淘汰）

### 事实

- 起始 HEAD=`ca25dd8d0d1cd5215511ba9e8177f5e75dc09fa2`；固定 worktree/branch/interpreter/split 与前轮一致，未读取 test、未重训 M0、未创建或运行 M2。
- 只选择 focal BCE（`gamma=2`）hard-example 方向：原 M1 fusion 结构、global train-only `pos_weight`、BCE logits、原 decoder 均保持不变。
- TDD RED→GREEN 后专项 M1=`25 passed`、全套=`136 passed`。full run=`artifacts/m1_fusion_focal_bce_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- error analysis=`artifacts/experiments/m1_fusion_focal_bce_e1/error_analysis.json`：TP/FP/FN=`18/449/33`，P/R/F1=`0.0385439/0.3529412/0.0694981`，participant mean/std/worst=`0.0592277/0.0352845/0`，start/end MAE=`551510.5/909179.6 ms`；short FP=`13/449=2.89532%`。

### 风险、候选、验收标准、选择

- focal BCE 未解决 long FP，并使 `neither` predicted-positive rate=`1.0`；候选淘汰。
- M2 gate=`false`：short dominance=`false`、Recall=`35.2941%`、context=`false`；M3/M4=`false`。
- mask-detached、unweighted BCE、focal BCE 三轮 M1 remediation 均未通过 gate；不再以失败候选强行创建 M2，保留 evidence 并回到用户可审阅的 no-M2 状态。

### 实验结果

- focal artifact 作为失败证据保留；最终验证完成后原子提交一次，不合并、不 push。

## M1 probability-prior remediation 复验（2026-09-06，unweighted BCE 淘汰）

### 事实

- 起始 HEAD=`ca25dd8d0d1cd5215511ba9e8177f5e75dc09fa2`；固定 worktree/branch/interpreter/split 与前轮一致，未读取 test、未重训 M0、未创建或运行 M2。
- 恢复原 M1 fusion 结构，只选择 `unweighted_bce` 概率先验候选；实际训练 `pos_weight=1.0`，保留 frozen cache、BCE logits、原 decoder。
- TDD RED→GREEN 后专项 M1=`24 passed`、全套=`135 passed`。full run=`artifacts/m1_fusion_unweighted_bce_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- error analysis=`artifacts/experiments/m1_fusion_unweighted_bce_e1/error_analysis.json`：TP/FP/FN=`8/440/43`，P/R/F1=`0.0178571/0.1568627/0.0320641`，participant mean/std/worst=`0.0370053/0.0515354/0`，start/end MAE=`122452.4/279976.8 ms`；short FP=`168/440=38.1818%`。

### 风险、候选、验收标准、选择

- unweighted BCE 的 calibration 改善不能弥补 Recall 崩溃；候选淘汰，M2 gate=`false`（short dominance=`false`、Recall=`false`、context=`false`）。
- 下一轮只选择 focal BCE（固定 `gamma=2`，保留 global train-only `pos_weight` 和原 M1 fusion/decoder），针对长连续 FP 的 hard-example 证据；不叠加 mask、unweighted prior 或 M2。

### 实验结果

- unweighted artifact 作为失败证据保留；仍不创建或配置 M2。

## M1 mask-detached remediation 复验（2026-09-06，候选淘汰）

### 事实

- 起始 HEAD=`ca25dd8d0d1cd5215511ba9e8177f5e75dc09fa2`；固定 worktree/branch/interpreter/split 与上一轮一致，未读取 test、未重训 M0、未创建或运行 M2。
- systematic debugging 从 e2 checkpoint 追踪到 raw availability mask 直接进入 `IMUPPGFusion.gate` 与 `head`：e2 head mask weights=`+2.2778/+1.3741`，embedding weight max abs=`0.1401`；因此只选择 mask-detached 这一 M1 方向，保持 global BCE、原 decoder 和 frozen cache 不变。
- TDD RED→GREEN 后专项 M1=`24 passed`、全套=`135 passed`。full run=`artifacts/m1_fusion_mask_detached_e1/`，IMU/PPG cache=`1121/1121 hit`，3 epoch CUDA，`test_not_used=true`。
- independent error analysis=`artifacts/experiments/m1_fusion_mask_detached_e1/error_analysis.json`：TP/FP/FN=`32/710/19`，P/R/F1=`0.0431267/0.6274510/0.0807062`，participant mean/std/worst=`0.0685150/0.0372385/0`，start/end MAE=`462503.5/126226.8 ms`；FP duration median/p90/max=`289500/2795702.9/13966995 ms`，window median/p90=`88/919`，short FP=`26/710=3.66197%`。

### 风险、候选、验收标准、选择

- mask-detached 后 both predicted-positive rate 仍=`92.3583%`、neither=`0%`，且 F1 低于 e2=`0.1170732`；说明仅移除 raw mask 输入不足，候选淘汰。
- M2 gate=`false`：short-FP dominance=`false`，Recall=`62.7451%` 虽超过 50%，context support=`false`；M3/M4=`false`。
- 下一轮只选择 unweighted BCE probability-prior 候选（恢复原 M1 fusion 结构，`pos_weight=1`），不与 mask-detached、availability-stratified loss 或 decoder 改动叠加。

### 实验结果

- 新增代码/测试在下一轮前不视为验收；本候选 artifact 作为失败证据保留。仍不创建或配置 M2。

用户于 2026-09-06 明确授权启动 M1；旧文档的“等待授权”状态由此覆盖。
仅使用现有 `codex/smartwatch-eating-baseline` worktree，不合并、不 push、不启动 M2/M3/M4。

## M1 remediation 与复验 gate（2026-09-06，当前最新）

### 事实

- 起始 HEAD=`920ca23b91e082c1192968234471553342410030`；仍使用 `E:\bme_compitition\.worktrees\smartwatch-baseline`、分支 `codex/smartwatch-eating-baseline`、项目解释器 `C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe` 和 `artifacts/final_m0/split_manifest.json`。未读取 test、未重训 M0、未重建 `cache/m0_full`。
- systematic debugging 将问题分为四类并确认：长期连续 FP、高分输出与 modality availability 耦合、校准/threshold 不是唯一根因、以及真实 Recall 不足/不可观测 FN。有限候选中只选 availability-invariant M1 BCE；M2/M3/M4 不并行。
- TDD 先 RED：新增 capped weight 断言时 `compute_m1_stratum_pos_weights` 不接受 `max_pos_weight`；最小实现后 GREEN。随后增加 legacy config RED→GREEN，确保只有显式 `m1_loss_mode=availability_stratified_bce` 才启用新 loss，旧 M1 config 仍为 `global_bce`。专项 M1 测试=`22 passed`。
- e1 直接分层权重实验把 `neither` 的 train-only `neg/pos` 比设为 `648.2119`，validation `neither` predicted-positive rate=`1.0`，TP/FP/FN=`11/221/40`，F1=`0.0777385`；作为明确反例淘汰。
- 选定方向内的 e2 capped 复验使用 `min(stratum_ratio, global_pos_weight)`，只用 train participant 统计；run=`artifacts/m1_fusion_availability_stratified_e2/`，1121/1121 IMU/PPG cache hit，windows=`3,578,835`，3 epoch CUDA training=`3041.14 s`，`test_not_used=true`。
- e2 frozen validation：TP/FP/FN=`24/335/27`，P/R/F1=`0.0668524/0.4705882/0.1170732`，participant F1 mean/std/worst=`0.0981172/0.0612279/0`，start/end MAE=`817518.5/62955.9 ms`。FP duration median/p90/max=`297000/8387965.2/24687528 ms`，window count median/p90=`92/2769.4`，short FP=`10/335=2.9851%`；`both` predicted-positive rate/FPR=`0.9972938/0.9971748`，`neither` predicted-positive rate=`0`。
- 对应报告为 `artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`；其 gate observed Recall=`0.4705882`，short FP fraction=`0.0298507`，context support=`false`，M2=`false`。未创建 `context_model.py`、`m2_context.yaml` 或 M2 输出。

### 风险、候选、验收标准、选择

- 风险：capped loss 修正了 `neither` 的分数塌缩，但 `both` 长 FP 仍占主导，且 F1 低于原 M1 `0.1686747`；不能将 e2 解读为成功，更不能用它强行启动 M2。
- 候选：只保留该单一 M1 availability-invariant loss 方向的已验证 capped 变体；M2 仍需短 FP≥50%、Recall严格>50%、context evidence 三项全满足，M3/M4 本轮不满足。
- 选择：`do_not_start_advanced_models`。下一步仅建议在 M1 层面针对 `both` mask/availability prior 做新的独立证据实验，当前不实现、不配置、不训练 M2。

### 交付物

- 代码：`src/eating_detection/training.py`、`tests/test_m1_fusion.py`、`tests/test_m1_cached_training.py`、`configs/experiments/m1_availability_stratified.yaml`。
- 证据：`artifacts/m1_fusion_availability_stratified_e1/`（反例）、`artifacts/m1_fusion_availability_stratified_e2/`（最终 capped 复验）、`artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`。

## M1 validation error analysis 与高级方向 gate（2026-09-06，当前最新）

### 事实

- 使用 `artifacts/m1_fusion_full_e3/` 的 frozen validation 输出，配对读取 `cache/m0_full` 与 `cache/m1_ppg` 的 metadata、window arrays 和 quality mask；未读取原始 CSV、test participant 或 checkpoint 做推理。结果保存于计划要求的 `artifacts/experiments/m1_fusion_full_e3/error_analysis.json`。
- provenance 已记录 source run-dir、两个 cache 目录、split manifest SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`、decoder=`0.15/6000/0`、`event_iou_threshold=0.25`、`label_positive_overlap=0.25` 和 `ppg_max_dense_samples=1000000`；192 个 validation M0/PPG pair 的 reference SHA-256 均匹配，window start/end/label/loss mask 均匹配。
- fusion validation 总体为 windows=`593589`、TP/FP/FN=`21/177/30`、Precision/Recall/F1=`0.1060606/0.4117647/0.1686747`、participant F1 mean/std/worst=`0.1481688/0.1077214/0`、start/end MAE=`637874.6/79659.7 ms`。独立复算与 frozen `metrics.json` 相等。
- FP 分布显示持续误报而非短暂误报：duration median/p90/max=`1963878/12265790.4/24915528 ms`，window count median/p90=`644/4071`，max-score median=`0.8851013`，event-mean-score median=`0.7146850`，前后相邻预测事件 gap median 均=`117000 ms`。按 duration≤`30000 ms` 且 window count≤2 的固定短暂定义，仅`6/177`=`3.39%` FP。
- calibration 为 binary Brier/ECE=`0.2398206/0.3741050`、soft=`0.2398207/0.3744612`。实际 validation modality strata 为 imu-only=`24070`、PPG-only=`0`、both=`248689`、neither=`320830`；threshold=`0.15` 时 imu-only/both 窗口阳性率与窗口 FPR均为1，neither 阳性率为0，显示分数强烈依赖 modality availability。
- 同 split M0 `artifacts/m0_final_q50_group_e3/` 为 F1=`0.1728395`、P/R=`0.109375/0.4117647`、start/end MAE=`639946.0/71945.5 ms`、participant F1 std=`0.1137248`。M1 fusion delta：F1=`-0.0041648`、Precision=`-0.0033144`、Recall=`0`、start MAE=`-2071.4 ms`、end MAE=`+7714.3 ms`。PPG-only 诊断 F1=`0.1792453` 但 Recall=`0.3725490`，不能替代 fusion 主结果。

### 风险

- M1 full run 仍是 frozen split、3 epoch、单次实验；整体 Recall 仅`41.18%`，且 177 个 FP 主要是高分长连续段。此证据不支持把错误归因于窗口概率的短暂抖动，也不支持直接堆叠更高容量模型。
- modality coverage 中没有 PPG-only windows；PPG available 全部落在 both，neither 占`320830/593589`。因此不能把 PPG 分支的可用性误写成独立模态已提升泛化。

### 候选

- M2：仅在短暂 FP 主导、正事件 Recall 足够，且 error analysis 支持 probability/validity/interval context 时启动。
- M3：仅在局部连续性或边界抖动是主问题时启动。
- M4：仅在 M1 稳定且未被前两类错误解释时启动。
- 不启动高级模型：M1 信号、coverage 或 Recall 不足，或证据不支持上述归因。

### 验收标准

- 本轮报告采用可复核的保守操作化：短暂 FP 为 duration≤`2×window_sec=30000 ms` 且窗口数≤2；主导要求短暂 FP 占比≥50%；“检出大部分正事件”要求 Recall>50%。三项需同时满足才算 M2 gate passed。M3 需有局部连续性/边界抖动主导证据；否则不启动。
- 必须维持 strict IoU>`0.25`、participant 级 metrics、宏平均 start/end MAE、binary/soft calibration、modality coverage、同 split M0 对比，且 artifact 明确 source run、split hash 和 decoder。

### 选择

- 选择 `do_not_start_advanced_models`。M2 gate=`false`：short FP dominance=`false`、positive-event recall sufficient=`false`、context support=`false`；M3/M4 亦为 false。只保留 M0/M1，不创建 `context_model.py`、M2 config 或 M2 训练产物。

### 实验结果

- `src/eating_detection/error_analysis.py` 新增 M1 双 cache、FP event duration/window/gap/score、participant metrics、calibration、modality strata、同 split comparison 和 gate 输出；M0 CLI 分支保持兼容。reference hash mismatch 回归也已加入。
- TDD 已完成 RED→GREEN：合成 cache/error-analysis 专项当前 `2 passed`；真实分析命令输出 `ERROR_ANALYSIS windows=593589 f1=0.168674698795 fp=177 participants=8`。full M1 artifacts、cache 与 raw 均未删除或重建。

## Preflight

- 起点 HEAD：`7c7d2ee5123cce9173474a1da1fec3eefb6b089a`；工作区干净，已确认 linked worktree。
- 完整读取 handoff、冻结设计、原实施计划和 README。
- `artifacts/final_m0/split_manifest.json` 与最终 q50 artifact 的 split 内容一致。
- train 34 participant / 954 sensor txt；val 8 participant / 201 sensor txt。
- train：hnu21001, hnu21002, hnu21003, hnu21004, hnu21005, hnu21007, hnu21008, hnu21009, hnu21010, hnu21012, hnu21013, hnu21014, hnu21018, hnu21019, hnu21021, hnu21022, hnu21023, hnu21025, hnu21026, hnu21026j, hnu21027, hnu21028, hnu21029, hnu21031, hnu21032, hnu21033, hnu21034, hnu21035, hnu21036, hnu21037, hnu21038, hnu21039, hnu21040, hnu21041。
- val：hnu21006, hnu21011, hnu21015, hnu21016, hnu21017, hnu21024, hnu21042, hnu212020。
- excluded_test：ac3 / test；只枚举文件名，分别 0 / 2 sensor txt，不读取标签。
- 原始数据 Git 跟踪为空；cache/artifacts/checkpoints/outputs 的具体文件探针均被忽略。
- 环境：`C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe`，Python 3.11.16，PyTorch 2.11.0+cu128，CUDA 12.8，RTX 5060 Laptop。
- 既有 CUDA 两步训练验证通过；基线 pytest 72 passed。
- M0 artifact `artifacts/m0_final_q50_group_e3/` 存在；不重训 M0。

## 解析子阶段

事实：M0 已有显式 IMU-only 投影，原始 PPG 行质量语义为正 timestamp、44 通道全部 finite、非全零。
风险：复用全模态 parser 会不必要转换 IMU；缺列可能报错或被误认为有效零值。
候选：扩展 M0 parser，或独立 PPG-only parser。
验收：只读取 PPG，保留旧行 mask 等价性，缺列显式无效，重复表头与 bounded rows 可测试。
选择：独立 `iter_ppg_chunks`；M0 路径保持原实现。
实验：9 项 RED（缺少函数）→ 13 项 IO GREEN → 全套 81 passed，compileall/diff check 通过；提交 `d05665f`。独立审查发现缺少整条 PPG stream 时抛错；追加 2 项 RED 后改为显式空/无效流。全套 83 passed，规格与质量审查通过；提交 `47f2f41`。两个真实文件各 2,000 行与旧 parser 时间戳/波形/mask 完全等价，有效行分别为 450 和 435。

M0 只读复评重新计算 TP/FP/FN=21/171/30，Precision=0.109375，Recall=0.4117647058823529，F1=0.17283950617283952，start/end MAE=639946.0238095239/71945.45238095238 ms；与保存指标逐项相等。原始文件 metadata 基线共 2,378 项，保存于忽略的 `artifacts/m1_preflight/`。M0 cache 清点为 train 929、val 192，合计 3,578,835 windows、268,791,286 time samples。PPG 数组磁盘估计约 51 GB，可用空间约 1.17 TB。

## PPG cache 契约（待 TDD 实现与验证）

- 独立 `cache/m1_ppg/`，独立 schema/modality 指纹；绝不修改既有 IMU cache。
- 每文件连续 `(45,T)` float32：44 波形 + 1 row quality；另存 `(1,T)` bool quality、int64 时间轴/窗口索引/窗口边界、float32 soft label、bool loss mask。
- 保留 44 通道定义和既有 all-finite/nonzero 行 mask；额外平坦质量检查必须显式记录，不能伪装成原 parser 等价语义。
- 先对 PPG timestamp 稳定去重聚合，再恢复统一网格，再抗混叠重采样。无效波形置零且质量为 false。
- 通过显式目标时间轴契约对齐 M0 窗口；对齐信息纳入 key，不能按窗口序号盲拼。
- 原始波形 cache 与训练集拟合的标准化统计分离；统计只用 train 有效样本，val 复用。
- key 包括源路径/size/mtime、采样率/max_gap、预处理变体、窗口/标签配置和区间、modality/channel/schema、显式对齐范围；hit 只 stat 源文件，不打开 CSV。
- 临时文件写入成功后原子改名；逐文件恢复；batch 切片，不保存重叠窗口 clone。
- `flat_policy` 默认 `reject_constant_stream`：至少两条有效 canonical row 在 44 个通道均精确恒定时，整条流质量为 false；仅显式传入 `keep` 才保留非零常量流。没有推断幅度阈值。
- 降采样质量同时追踪抗混叠滤波的输入支持；若无效行会改变输出样本，则该样本质量为 false 且 44 个波形通道置零，不能被点位质量检查误标为有效。

## PPG cache 审查与验收（2026-09-06）

事实：独立规格审查确认 `ppg/` 命名空间、45×T float32（44 波形 + 质量）和独立 bool quality array；reference grid hash、源 path/size/mtime、采样率、窗口/标签、schema 与预处理均进入 key。初始实现的非零常量流默认保留，且 100 Hz 的单个无效点在 25 Hz 抗混叠后会改变相邻波形但仍被标为有效。

风险：前者与冻结的“平坦 PPG 必须有质量 mask”不一致；后者会把由无效包污染的输入交给 M1 encoder。候选是保留旧默认，或以无阈值的精确常量规则默认拒绝，并把滤波支持传播进 quality。

验收标准：新回归测试须先失败；默认平坦流无效但显式 `keep` 可回退；所有受无效点影响的降采样输出为零/无效，同时远离该点的输出保留有效。现有 timestamp/window/label/ignore、partial(43列)、key、atomic/recovery、lazy 与 cache-hit 禁止 CSV 测试不得回归。

选择：默认 `reject_constant_stream`，保留显式 `keep`；以 resample 后 availability 对 all-valid support 的数值比较传播滤波影响，不改 IMU cache 或 M0 的 `resample_uniform` 默认行为。

实验：两项新增测试 RED（默认平坦流仍有效；无效点影响的输出仍为有效）→ 最小实现 GREEN。PPG cache 专项 27 passed；全套 110 passed；compileall 与 diff check 通过。两个真实文件各 2,000 行，在 soft/ignore 下都与 M0 25 Hz reference 的 timestamps/window indices/window boundaries/labels/loss mask 完全相等；hnu21013 quality coverage=0.65158、hnu21024=0.31050。每个 cache miss 后，替换 PPG reader 为抛错函数的 lazy hit 仍成功，未打开原始 CSV。M0 冻结概率只读复评保持 TP/FP/FN=21/171/30、F1=0.17283950617283952。

## M1 模型核心（2026-09-06）

事实：M0 的 `IMUCNN` 与新的独立 M1 temporal encoder 不具有完全相同的 module/state_dict 结构，不能静默迁移。M1 PPG 输入固定为 45 channels（44 波形 + 逐点 quality），但逐点 quality 不能替代窗口级模态可观测性。

风险：仅以零值表示缺失会让 Conv bias/normalization 产生看似有效的 embedding；独立地随机丢弃两个模态会出现双模态都不可用的训练样本；把 sigmoid 放在 loss 前会违背数值稳定的 BCE 契约。

选择：`IMUPPGFusion` 使用独立 GroupNorm temporal encoder，embedding 级 gated fusion，并把 `(B,2)` modality mask 同时用于分支输入、embedding 和分类 head。训练 dropout 只在两个模态都可用时随机屏蔽其中一个；eval 不随机屏蔽。`load_compatible_imu_encoder_from_m0` 仅在完整 key/shape 相等时加载，否则 fail closed；默认不调用它。`train_m1_one_batch` 直接将 logits 和 `[0,1]` target 传给 `BCEWithLogitsLoss`。

实验：8 项 RED（缺少 fusion/model batch 接口）→ GREEN：独立分支 shape、无效 PPG 的不同数值在 modality mask=false 时输出一致、单/双缺模态 finite、训练期安全 dropout、eval 确定性、M0 不兼容拒绝、CPU logits BCE backward 与 CUDA forward/backward。专项 8 passed；全套 118 passed；compileall/diff check 通过；`verify_environment.py --require-cuda --steps 2` 新鲜通过（PyTorch 2.11.0+cu128、CUDA 12.8、RTX 5060 Laptop）。尚未创建 paired cache Dataset/CLI 或进行 M1/PPG-only 训练。

## M1 配对 cache 与 PPG 标准化（2026-09-06）

事实：IMU 与 PPG cache 即使使用同一文件名，也可能因不同的 reference grid、窗口边界或 soft label 而错位；lazy cache 为节省内存不把 timestamps 常驻。PPG 的 44 个波形 channel 与最后一个 point-quality channel 也不能一并标准化。

风险：按 cache/window 序号盲拼会静默训练到错误标签；只在 non-lazy cache 验证 timestamps 会让真实训练路径绕过 M0 reference grid 约束；把验证 participant 或 invalid PPG 值加入统计会泄漏并把 placeholder 零值变成伪信号。

选择：`PairedCachedWindowDataset` 以解析后的 source path 一一配对并强制 participant、timestamps、window index/start/end、window label、loss mask 相等；lazy 时仅从各 `.npz` 读出 timestamps array 作一次性验证，不加载 feature arrays。每窗根据各 cache point-quality 的非零覆盖派生 `(IMU, PPG)` modality mask，窗口仍保留。`fit_m1_ppg_standardizer` 仅扫描训练 participant 的 44-channel 有效 PPG 点；`standardize_m1_ppg_batch` 保留第45个 quality channel，并在缩放后把所有 invalid waveform 值复位为零。

实验：5 项 RED（缺少 paired Dataset/PPG standardizer 接口）→ GREEN；再以延迟加载 cache 的篡改 timestamps 回归测试确认实际训练路径也拒绝错 reference grid。专项 6 passed；全套 124 passed；compileall/diff check 通过。尚未运行 PPG-only 或融合训练、也尚未接入 CLI。

## M1 cache-hit batch training（2026-09-06）

事实：M1 必须在同一 participant split 的配对 cache 上训练；PPG-only 是诊断，不应另造隐式拼接模型，也不得通过遗漏 PPG 窗口改变 label 分布。test cache 若意外传入训练函数会破坏冻结 split。

风险：训练期重读 CSV、将 validation 统计带入 PPG 标准化、或仅在调用 CLI 时过滤 test 都会造成不可复现或泄漏。单独的 PPG-only 训练若仍留下 IMU mask=true，会不再是诊断性对照。

选择：新增 `fit_m1_cached`，接受已配对 IMU/PPG caches，先拒绝 train/val 外 cache participant 及 split manifest 中 excluded test participant，再构造 participant/file batch。IMU/PPG 统计和 `pos_weight` 均只来自训练 participant。`ppg_only` 只把 IMU modality mask 置零；`fusion` 传递原始 mask。两个模式都复用 batch BCE logits、验证集 decoder、严格 IoU 事件评价、checkpoint/probability 输出，并分别记录 IMU/PPG cache 命中/CPU 时间、GPU 与 epoch 时间、train/val modality coverage。验证概率按唯一 `(participant,start,end)` 与 cache label 回配，输出二元 membership 与 soft overlap target 的 Brier/ECE/reliability bins。

实验：两项 RED（训练入口不存在）→ GREEN：lazy cache 的 PPG-only end-to-end CPU batch 在 reader 被替换为抛错函数时仍完成，写出 checkpoint、双模态 normalization、概率和事件输出；额外回归确认 train/val 之外的 cache participant 被拒绝。补一项 calibration RED（metrics 缺少该字段）→ GREEN。专项 2 passed；全套 127 passed；compileall/diff check 通过。CLI 与真实 bounded sample 尚未运行。

## M1 CLI/config（2026-09-06）

事实：M1 需要每个 IMU cache 的 M0 reference timestamps 才能构建 PPG cache，但训练时应保持 cache lazy，且 M0 命令行为不能回归。不同 source 的 PPG build failure 不能让未配对 IMU 悄悄进入训练。

风险：传入 lazy cache 的 `timestamps_ms=None` 会导致 PPG 自建 grid；把 PPG build failures 混进 IMU issues 会掩盖故障；把 M1 默认行为覆盖到 M0 会破坏既有可复现命令。

选择：CLI 仅在 `model: m1_imu_ppg` 时，从每个 lazy IMU `.npz` 单独读取 timestamps array 来调用 `build_ppg_cache(..., reference_timestamps_ms=...)`，并仅传入成功的同-source cache pairs；PPG issues 写入独立 JSON。无 `model` 的 YAML 仍走 M0。提交 `configs/m1_imu_ppg.yaml`（feature fusion）和 `configs/experiments/m1_ppg_only.yaml`（诊断），明确 PPG cache/preprocess/flat policy 与 model parameters。

实验：CLI TDD 先在 M0 路径运行并缺少 `model_mode` 输出（RED），实现后 2 个 toy participant 的 PPG-only CLI 完成独立 PPG cache 与 paired cache training，保存 nested IMU/PPG normalization（GREEN）。专项 1 passed、全套 127 passed；compileall/diff check 通过。真实 bounded PPG-only/fusion CUDA sample 尚未运行。

## Bounded CUDA 与 full-data gate（2026-09-06）

事实：用 frozen manifest 中 hnu21013(train) 和 hnu21024(val) 各最多30,000行、1 epoch/batch64/CUDA 完成真实 PPG-only、feature fusion(dropout=.25) 和 no-dropout fusion；首次 PPG-only 两种 cache 均2 miss，后两次均 IMU/PPG 2/2 hit。三次在此受限范围的事件 F1 都为0.0384615（P=1、R=0.0196078、start/end MAE=34506/259494ms），不能推断全量优劣。PPG-only/fusion/dropout fusion 的 binary Brier/ECE 分别为0.165814/0.407198、0.081846/0.286045、0.085418/0.292211；fusion 在该 tiny sample 的 calibration 较好，但不是选择依据。

风险：若完整 M1 重建 IMU cache，就不再是复用冻结M0 reference；若把 bounded event 结果写作全量结论，会误导下一步模型选择。

选择：检查 `cache/m0_full` 的1121个 cache 元数据后，确认其采样率、max gap、P0、window、label配置都与M1配置完全相同。因此三个 M1 YAML 的 `cache_dir` 均改为该只读 IMU cache；PPG 保持独立 `cache/m1_ppg`。完整运行前复核全套127 passed、compileall、diff check、CUDA2-step smoke、raw零跟踪、artifact/cache忽略，并以原始2378文件的size/mtime基线复核为零变化（基线记录有统一5小时偏移，校正后比较）。

验收：full-data gate 通过；接下来可按既定顺序全量构建/命中 PPG cache，运行 PPG-only，再重用既有 M0 reference，最后运行 fusion。未启动M2/M3/M4。

## 待完成

- [x] PPG parser 独立审查与缺失模态覆盖。
- [x] PPG cache 严格 TDD、数值/窗口/label 等价、原子写入和中断恢复验证、阶段提交。
- [x] 独立 IMU/PPG encoder、显式 mask、安全 modality dropout，严格 TDD 与 CUDA 样例、阶段提交。
- [x] 真实 PPG-only/fusion bounded sample、M0 reference、dropout 对照与 full-data gate。
- [x] 全量 PPG-only 与 fusion、缺失模态 coverage、完整指标报告。
- [x] 同 split train/val 全量 cache、PPG-only 诊断、复用 M0 reference、M1 联合训练与训练期 modality dropout。
- [x] 事件指标、MAE、calibration、coverage 和 CPU/GPU 分开遥测。
- [x] 全套最终验证、README/handoff/实施计划更新与提交，保留现有分支/worktree。

## Temporal-run penalty remediation (2026-09-08)

系统性调试确认已有 negative-run sample weighting 没有改变 observed-modality 长 FP 的连续输出，因此新增一个保持窗口顺序的 contiguous-negative-run penalty 作为单一 M1 方向。TDD 先验证：只标记长度至少 3 的连续负 run；penalty 会增加对应 logits 的负 BCE；原 `pos_weight` 保持不变。专项 temporal 测试 `2 passed`，全套测试 `149 passed`，compileall、diff check 和 CUDA smoke 均通过。

首个 full frozen run 使用 `m1_temporal_run_logit_min_e1.yaml`、penalty weight=`8.0`，仍复用 `cache/m0_full`、`cache/m1_ppg`、原 frozen split 和默认 decoder。`artifacts/m1_temporal_run_logit_min_e1/` 得到 TP/FP/FN=`1/244/50`、P/R/F1=`0.00408163/0.0196078/0.00675676`，short FP=`73/244=29.9180%`，event Recall=`1.96078%`。`both` predicted-positive rate=`0%`、mean probability=`0.00001564`，说明 weight=`8.0` 使双模态输出塌缩；不是 decoder-only 修复，M2 gate 仍 false。独立报告为 `artifacts/experiments/m1_temporal_run_logit_min_e1/error_analysis.json`，split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。下一步只降低 penalty 到 `0.5`，不创建或运行 M2。

第二个 full frozen run 只将该 penalty 降为`0.5`，配置为`m1_temporal_run_logit_min_e2.yaml`。`artifacts/m1_temporal_run_logit_min_e2/` 得到 TP/FP/FN=`5/437/46`、P/R/F1=`0.0113122/0.0980392/0.0202840`，short FP=`189/437=43.2494%`，event Recall=`9.80392%`。`both` predicted-positive rate=`0%`、mean probability=`0.00235831`，而 `imu_only` FPR=`46.2253%`；较小 penalty 提高短 FP 占比但仍令双模态分支低于 decoder threshold，M2 gate 仍 false。独立报告为 `artifacts/experiments/m1_temporal_run_logit_min_e2/error_analysis.json`，仍使用 split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。下一步只将 penalty 降至`0.05`，不创建或运行 M2。

第三个 full frozen run 使用 `m1_temporal_run_logit_min_e3.yaml`，只将 penalty 降至`0.05`。训练在 epoch 2 checkpoint 后被 Windows 主机重启中断：System 日志记录 18:01:43 开始 reboot、18:03:16 恢复；stdout/stderr 均为空，未生成最终 `metrics.json`、`events_val.json` 或 error analysis，故不计为实验结果，也不作 M2 gate 判定。未完成目录已归档为 `artifacts/m1_temporal_run_logit_min_e3_launch_failed/`，其中 checkpoint 的 `epoch=2`；待主机稳定后仅重跑同一 e3 配置，继续保持不创建或运行 M2。

同一 e3 配置在主机更新后于 22:47:04 第二次启动；epoch 2 checkpoint 于 00:29:29 写入。Windows Update 随后于 02:37:43–02:37:44 安装 `9PLM9XGG6VKS-OpenAI.Codex`，训练进程随 Codex 更新中断；没有 Python/CUDA traceback，stdout/stderr 为空，未产生最终 metrics、events 或 error analysis，故不计为实验结果，也不作 M2 gate 判定。目录已归档为 `artifacts/m1_temporal_run_logit_min_e3_launch_failed_codex_update/`，待更新完成后仅重跑同一 e3 配置。

## Full-data compact PPG continuation（2026-09-06）

事实：紧凑 PPG cache 修复在严格 TDD 下完成并提交为 `08d571a fix: guard oversized PPG cache allocation`。新增 compact miss、lazy hit reader-throw、batch 局部零数组回归；另修复无显式 M0 reference 时 `max_dense_samples` 未进入 cache key 的边界问题。专项 `48 passed`，全套代码测试 `131 passed`；三份 M1 YAML 均显式记录 `ppg_max_dense_samples: 1000000`。独立审查无 P0/P1。

风险：超长 reference 的 compact 表示是保守的显式缺失 PPG，不是插值或外推；PPG-only 只是诊断；所有结果为同一冻结 split 的 3 epoch 单次 run，不能作为超参选择的稳健证明。

选择：不删除已有 `cache/m1_ppg` 或 `artifacts/m1_ppg_only_full_e3`，在原 cache 上恢复完整 PPG-only，再用全 hit cache 运行 fusion；M0 保持只读，不读取/训练 test，不启动 M2/M3/M4。

实验：

- 目标 HNU21004 reference 长度 `23,645,128`，最终 `.npz` 为 `storage=all_missing_compact`，`timestamps_ms=[0]`、`features=[45,0]`、`quality_mask=[1,0]`、`window_indices=[315264,2]`，保留 reference SHA-256 `108929f8c6534c2afb69d22170dd1380cc58da61ffc52d1ec6106386a5fad1f4`。`cache/m1_ppg` 共 1,136 个文件；本次新增 compact 记录 87 个，旧记录保留。
- PPG-only artifact `artifacts/m1_ppg_only_full_e3/`：3,578,835 windows（train/val=`2,985,246/593,589`），F1/P/R=`0.1792453/0.1180124/0.3725490`，start/end MAE=`839148.2/74066.6 ms`；binary Brier/ECE=`0.1670272/0.3231965`，soft=`0.1668948/0.3235527`；PPG cache `112 hit/1009 miss`、build/load=`1162.15/0.983 s`，training=`2953.12 s`。
- Fusion artifact `artifacts/m1_fusion_full_e3/`：`modality_dropout=0.25`，F1/P/R=`0.1686747/0.1060606/0.4117647`，start/end MAE=`637874.6/79659.7 ms`；binary Brier/ECE=`0.2398206/0.3741050`，soft=`0.2398207/0.3744612`；IMU/PPG cache 均 `1121/1121 hit`，training=`3097.80 s`。
- fusion val coverage：IMU=`272,759`、PPG=`248,689`、both=`248,689`、neither=`320,830` / `593,589` windows；PPG-only intentional IMU-missing val coverage：PPG=`248,689`、neither=`344,900`。M0 frozen reference F1=`0.1728395`，三份 split manifest SHA-256 均 `18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。
- 资源/隔离：两次 full run 使用 CUDA；full fusion 训练 epoch 均值约 `1029.65 s`、峰值已分配显存约 `94.15 MB`；PPG-only epoch 均值约 `982.15 s`、峰值约 `89.07 MB`。原始数据 2,378 条 size/mtime 与 preflight 一致，test 未读取/训练，cache/artifact 保留。

验收：full-data 运行已通过 CLI `TRAIN_SMOKE_PASS`；新鲜全套 `131 passed`、PPG cache/M1 专项 `48 passed`、compileall、diff check、CUDA smoke、lazy cache-hit、split equality、原始 metadata 2,378/2,378 未变、raw 未跟踪与 ignore 检查均通过。README、handoff、resume prompt 与本执行记录已更新，待文档原子提交。
