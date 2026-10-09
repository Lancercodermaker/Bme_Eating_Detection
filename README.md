# 智能手表进食事件检测

面向生物医学工程竞赛的智能手表进食事件检测项目。项目从手表 ACC、GYRO 与 PPG 传感器数据中识别进食事件，并以事件级 F1 和边界误差评估结果。当前代码重点是可审计的数据处理、候选事件生成、事件验证和竞赛提交流程。

> 当前阶段：M5 验证范围与随机种子已冻结，正式高分管线仍在实现和验证中。仓库记录的本地实验结果不代表官方隐藏测试成绩。

## 项目结构

```text
.
├── bme_compitition_next/       # Python 项目
│   ├── src/eating_event/       # 数据、特征、模型、指标与验证逻辑
│   ├── scripts/                # 数据审计、候选模型、验证器与提交入口
│   ├── tests/                  # 单元与契约测试
│   ├── configs/                # 配置模板及本地配置
│   └── docs/                   # 实验记录、运行手册、设计与执行计划
├── docs/                       # 项目早期设计与实施记录
├── official_test_dataset/      # 本地竞赛数据（忽略，不应提交）
├── external-dataset/           # 本地外部研究数据（忽略，不应提交）
└── tmp/                        # 本地临时文件（忽略）
```

## 方案概览

主路线以官方训练数据为目标域，按 participant 划分训练与验证，避免同一参与者的 session 跨集合泄漏。处理流程包括数据清单与质量审计、重复和无效时间戳处理、ACC/GYRO 统一到带 gap 检查的 10 Hz 时间轴、15 秒窗口与 7.5 秒步长特征、HGB 候选评分、participant 级 OOF 分数、事件级验证器和受约束的事件解码。评价使用竞赛事件匹配规则（IoU > 0.25），同时关注 Precision、Recall、F1、事件边界 MAE 和误报情况。

仓库也保留 TCN、Transformer 和外部数据预训练对照脚本。它们目前属于实验/对照路线；完整 FD-I 预训练未达到预设收益门槛，FD-II 实验出现负迁移，不属于当前正式提交方案。详细证据见 [`实验日志`](bme_compitition_next/docs/experiment-log-2026-09-10.md)、[`外部数据预检`](bme_compitition_next/docs/external-preflight-2026-09-11.md) 和 [`冻结设计`](bme_compitition_next/docs/superpowers/specs/2026-09-14-high-f1-event-stack-detailed-design.md)。

## 项目进度

- 已建立数据清单、原始文件解析与审计、时间轴、滑窗、特征、事件指标、候选模型/验证器、TCN 与 Transformer 对照，以及提交运行脚本。
- 设计记录的本地数据盘点为 1,161 个训练 session 文件、43 名参与者、281 个有效餐段；竞赛隐藏测试标签不可用于开发评估。
- 小规模 participant-frozen 验证曾得到 event F1 = 0.7273（TP/FP/FN = 4/0/3），但只覆盖有限参与者，不能视为稳定泛化结果或排行榜成绩。
- 最新冻结设计要求 candidate coverage 达到正式门槛，再完成 OOF 验证器、嵌套 participant 验证、全量 target-only 训练和提交隔离检查。当前代码与冻结实施计划仍有差距，提交前需要完成这些阶段并复核结果。
- 本仓库根目录是 Git 根；Python 包与命令需从 `bme_compitition_next/` 目录运行。

## 环境与安装

要求 Python 3.10 或更新版本。建议使用独立虚拟环境；避免污染系统 Python 或 Conda base。

```powershell
cd bme_compitition_next
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

配置依赖包含 NumPy、pandas、PyYAML、SciPy 和 scikit-learn；开发依赖包含 pytest。模型代码中使用 PyTorch 的实验需另行按机器 CUDA/CPU 环境安装匹配版本。

## 配置数据路径

原始数据和元数据必须放在仓库之外。复制模板并编辑成本机路径；本地配置文件由 Git 忽略：

```powershell
Copy-Item configs\example.yaml configs\example.local.yaml
```

然后在 `configs/example.local.yaml` 中设置 `repository_root`、`raw_data_root` 和 `metadata_root`。不要把竞赛原始数据、官方测试标签、外部数据集、模型权重或运行缓存加入版本控制。

## 常用命令

从 `bme_compitition_next/` 执行：

```powershell
# 检查数据目录与文件格式
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/dataset-audit.json

# 运行测试
python -m pytest

# 查看正式提交命令与参数
Get-Content docs/submission-runbook.md
```

提交流程的完整参数、test 标签隔离规则、跳过文件检查和 smoke-test 注意事项见 [`提交运行手册`](bme_compitition_next/docs/submission-runbook.md)。提交 runner 应仅使用官方训练参与者训练，并对官方 test session 输出预测，不读取测试真值。

## 数据与隐私

竞赛数据和外部研究数据不随本仓库分发。部分数据约 93 GB；应按 session 流式或分块处理。外部数据只能按研究设计用于隔离的预训练对照，不能进入官方测试推理路径。请确认竞赛规则、数据许可和参与者隐私要求，再在本地使用数据。不要提交原始数据、个人标识数据、预测产物、缓存、权重或包含本机路径/凭据的配置。

## 文档导航

- [`提交运行手册`](bme_compitition_next/docs/submission-runbook.md)
- [`实验日志`](bme_compitition_next/docs/experiment-log-2026-09-10.md)
- [`数据集审计与模型预检`](bme_compitition_next/docs/preflight-2026-09-10.md)
- [`外部数据预检`](bme_compitition_next/docs/external-preflight-2026-09-11.md)
- [`高 F1 方案详细设计`](bme_compitition_next/docs/superpowers/specs/2026-09-14-high-f1-event-stack-detailed-design.md)
- [`高 F1 实施计划`](bme_compitition_next/docs/superpowers/plans/2026-09-14-high-f1-event-stack-implementation.md)
