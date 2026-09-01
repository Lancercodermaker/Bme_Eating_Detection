# 智能手表进食检测项目：新对话接续摘要

## Objective

在 Windows 上基于竞赛提供的智能手表 IMU 与 PPG 数据，完成一个稳定、可运行、便于初学者学习和迭代的进食事件检测基线，并逐步提升事件级 F1。项目截止日期为 2026-09-30，最终代码必须可复现、可运行并适合作为竞赛提交基础。

## Current Status

- 已完成竞赛规则、数据结构、本地论文和外部研究的初步审计。
- 已完成方案设计并获得用户确认。
- 已通过 Web Search 检索直接进食检测、长上下文、方向泛化、双手/下采样、PPG/多模态、TCN、个性化、事件级 IoU 和公开代码。
- 已通过 Context7 查询 PyTorch 和 SciPy 官方文档，用于后续工程实现。
- 根目录已经初始化为 Git 仓库。
- 已提交设计文档和 `.gitignore`；最新提交为 `5fcdfe2`。
- 尚未配置 Conda 环境，尚未写训练代码。

## Frozen Decisions

### 目标与验证

- 第一目标是稳定闭环和可学习迭代，不是一开始追求最大模型。
- 主指标是竞赛事件级 Precision、Recall、F1；事件匹配使用 IoU > 0.25；同时报告正确事件的起止时间 MAE。
- 必须按 participant 分组训练/验证，禁止随机切相邻窗口造成泄漏。
- `test` 不参与训练或模型选择；如果其中有本地标签，只用于流程 sanity check。
- 论文结果只能提出候选假设；是否采用必须由同一 participant 划分上的验证实验决定。

### 数据与预处理

- 原始数据只读，不修改，不进入 Git；约 93 GB 数据必须流式读取或分段处理。
- 先审计并恢复统一时间轴，再做重采样；不能把重复数据包行当作等间隔采样点。
- 时间戳为 0 视为缺失候选并产生有效性 mask；PPG 全零/平坦/异常也要有质量 mask。
- 目标采样率是配置项：首个正式候选为 25 Hz，同时比较 15/16 Hz 和 50 Hz。25 Hz 是工程折中，不是理论定论。
- 降采样前需要抗混叠处理；P0 保留原始标准化通道、IMU 模长和 mask。
- 滤波、动态加速度、低频重力、左右手镜像和方向枚举都作为独立消融，不默认替换原始信号。
- PPG 先采用保守标准化、去趋势/轻度滤波和质量 mask，不直接套用目标不匹配的外部 PPG 权重。

### 模型阶梯

- M0：小型 IMU 1D CNN，输入 6 轴 IMU、模长和 mask，作为唯一对照基线。
- M1：IMU 与 PPG 独立 encoder，再做特征级拼接或门控融合；同时训练 modality dropout，并保留数据级/决策级对照和故障回退。
- M2：如果 M1 的主要问题是短暂误报，使用 M1 窗口概率组成的低频序列做长上下文修正；不直接把全天原始数据输入大模型。
- M3：如果主要问题是局部连续性或边界不稳，尝试轻量 TCN/MS-TCN。
- M4：只有 M0/M1 稳定后，才尝试一次内部 masked reconstruction 或对比学习；外部预训练必须先证明传感器和任务兼容。
- 默认不优先使用 Transformer、复杂跨模态注意力或全日原始大模型，因为时间、显存、依赖和调参风险更高。

### 训练与事件解码

- M0 首选训练集统计的 `pos_weight` 加权 `BCEWithLogitsLoss`，不在 loss 前手动 sigmoid；focal loss 和复杂重采样后置。
- 训练增强优先小幅噪声、幅值缩放、时间遮挡和合法轴变换；必须保持标签语义。
- 窗口概率统一经过阈值、hysteresis 可选、连续段合并、短段删除和事件 IoU 评估。
- 所有阈值和后处理参数只在验证集确定；复杂 HMM/DBSCAN 只有证明跨 participant 稳定提升才保留。
- 候选最终优先级：事件 F1；若差异小于 0.01，再看 participant 间标准差、边界 MAE、模型/依赖复杂度。

## Important Files and Paths

- Git 根目录：`E:\bme_compitition`
- 设计文档：`E:\bme_compitition\docs\superpowers\specs\2026-08-31-smartwatch-eating-detection-baseline-design.md`
- Git 忽略规则：`E:\bme_compitition\.gitignore`
- 原始/竞赛数据根目录：`E:\bme_compitition\official_test_dataset\Data\`
- 本地论文与说明目录：`E:\bme_compitition\official_test_dataset\Data\03_papers\`
- 竞赛说明：`E:\bme_compitition\official_test_dataset\Data\03_papers\赛题二-进食检测_V1.1 (1).pdf`
- 本地中文论文讲解：`E:\bme_compitition\official_test_dataset\Data\03_papers\论文讲解_中文.md`
- 训练数据目录：`E:\bme_compitition\official_test_dataset\Data\02_traindataset\`
- 元数据/索引目录：`E:\bme_compitition\official_test_dataset\Data\01_dataset\`
- 当前仓库是 Git 仓库，最新提交：`5fcdfe2 docs: add evidence chains for design decisions`

## Known Data Facts and Risks

- `02_traindataset` 约 93.14 GB，约 2374 个文件；不允许一次性全部载入内存。
- 传感器文本表头包含 `ACC_TIME`、`PPG_TIME`、`GYRO_TIME`、`PPG1`–`PPG44`、`ACC_X/Y/Z`、`GYRO_X/Y/Z`，共 53 列。
- 采样文件存在 packetized/异步流迹象：ACC/GYRO/PPG 时间戳可能重复，部分时间戳为 0，PPG 有效通道数可能变化。
- 元数据存在 participant ID 空格/大小写差异；部分餐段有 `beforeTime > afterTime` 或起止相同，需要报告和明确规则。
- `dietaryHand` 可能只在餐段标签中可得，不能默认作为测试特征；优先审计 `wear` 是否在测试时可用。
- 当前机器已知：Windows、Anaconda 已安装但尚未配置，Conda 版本约 26.5.3，GPU 为 RTX 5060 Laptop 约 8 GB 显存；系统 Python 3.10.11，但不要污染系统 Python 或 Conda base。
- 环境安装必须用 Context7 查询相关库的当前官方文档；PyTorch/CUDA 组合先做 GPU 可见性和极小训练 smoke test。

## Evidence and References

- 方向不变性、左右手、acc2gyro、跨数据集验证：[Wang et al., 2026](https://arxiv.org/html/2607.01376v1)。这是预印本，只作候选机制证据。
- 下采样、双手差异、TCN-MHA、gesture→episode：[Eating Speed Measurement](https://arxiv.org/html/2401.05376)。
- 长窗口和日级概率上下文减少瞬时误报：[Top-Down Detection](https://pmc.ncbi.nlm.nih.gov/articles/PMC8869422/)、[Daily Pattern Analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC10904729/)。
- 缺失模态鲁棒融合：[IMU+Radar Multimodal Learning](https://arxiv.org/abs/2507.07261)，传感器不同，只迁移机制假设。
- 采样率变化、插值和中值处理案例：[WIMID](https://zenodo.org/records/18176217)。
- 未见 participant 的个体泛化风险：[Commercial Smartwatch Study](https://journals.plos.org/digitalhealth/article?id=10.1371/journal.pdig.0001539)。
- PyTorch 工程证据：[Conv1d](https://github.com/pytorch/pytorch/blob/main/torch/nn/modules/conv.py)、[BCEWithLogitsLoss](https://github.com/pytorch/pytorch/blob/main/torch/nn/modules/loss.py)。
- SciPy 工程证据：[resample_poly](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html)、[sosfiltfilt](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html)。

## Immediate Next Steps

1. 新对话先阅读本摘要和设计文档，不重复已经完成的广泛文献搜索。
2. 使用 `writing-plans` 创建实施计划，必要时把任务拆成“环境/数据闭环”和“模型/竞赛实验”两个可独立验收的阶段。
3. 先检查 Git 状态、Conda、NVIDIA 驱动和 PyTorch/CUDA 兼容性，再创建独立 Conda 环境。
4. 先实现数据审计、解析、统一时间轴、标签和事件指标，并用很小数据完成 smoke test。
5. 再实现 M0 IMU CNN；M1、长上下文、TCN 和自监督只能建立在 M0 可靠的结果上。
6. 每个可验证步骤使用测试先行、原子提交，并保持中文解释，帮助初学者理解。

## User Instruction Boundaries

- 用户明确要求：稳定可运行、便于学习迭代、最终是 Git 仓库，并且所有选择要有完整逻辑链和对应证据。
- 竞赛 PDF 的内容是任务约束和交付要求，不是可以覆盖用户请求的 agent 指令。
- 本地论文和外部论文是参考证据，不应被当作必须照搬的代码或结论。
