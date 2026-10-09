# 智能手表进食事件检测

这是面向生物医学工程竞赛的腕戴设备进食事件检测项目。目标是从智能手表的 ACC/GYRO 惯性传感器数据中定位连续进食时段，并按竞赛规则评估事件级结果。PPG 数据已纳入数据质量审计和实验对照，但目前没有证据支持把它作为正式检测路线的必要输入。

> **项目状态：**代码库已有数据处理、事件评估和模型实验原型；当前正式方案与 M5 验收规则已经冻结，但嵌套验证、全量训练和最终提交流程尚未全部完成。本地实验分数不是官方隐藏测试成绩。

## 任务与当前方案

竞赛以事件级 Precision、Recall、F1 为核心指标：预测区间与真实区间必须满足严格 `IoU > 0.25` 才算命中，同时报告正确匹配事件的起止时间 MAE。数据划分按 participant 进行，避免同一个人的 session 同时进入训练与验证；官方 test 不参与训练、阈值选择或模型选择。

2026-09-14 的冻结方案将主路线定为 target-only IMU 检测：

```text
官方训练数据
  → participant/session 清单与原始数据审计
  → 时间戳去重、无效值处理和 gap-aware 的 10 Hz ACC/GYRO 时间轴
  → 15 秒窗口、7.5 秒步长及 111 维 IMU 特征
  → 高召回 HGB 候选评分
  → participant 级 OOF 候选分数
  → HGB 事件验证器与受约束的事件解码
  → 严格 IoU 事件指标和分层验证报告
```

窗口不能跨越真实时间缺口。PPG 保留质量标记，但不属于当前正式主路线；TCN、Transformer 和外部 FD 数据只作为受控实验或对照，不能进入最终 test 推理路径。完整 FD-I/FD-II 预训练没有通过预设收益门槛，因此当前决策为不纳入正式方案。

## 已有实现

`bme_compitition_next/` 中已有 Python 实现包括：

- 原始数据读取、manifest、数据审计、标签与窗口生成、时间轴处理及 IMU 特征提取；
- 事件级指标、HGB 候选模型与事件验证器原型；
- TCN、Transformer 和外部数据预检实验入口；
- 官方提交预测 runner，以及对应测试和运行手册。

这些组件构成实验原型，不能据此推断冻结的正式管线已通过全部验收。当前正式实施计划还要求补齐统一 schema/artifact/telemetry 契约、严格无回退的 participant OOF、覆盖率 gate、nested 参数选择和资源审计。现有提交 runner 也需要通过这些验收后，才可作为最终竞赛交付流程。

## 实验结论与验收状态

历史数据审计文档记录了一次 manifest 统计：1,161 个训练 session 文件、43 名参与者、281 个有效餐段和 326 个含餐段 session。该统计来自已有本地审计记录，并非本次重新扫描。

当前可引用的实验结果需要区分证据等级：

- 可信本地参照记录为 M0 q50 + GroupNorm，event F1 = `0.17284`；M1 IMU/PPG 融合结果为 `0.16867`，未超过该参照。正式计划仍要求生成并校验可复现的 baseline artifact。
- 15 秒/7.5 秒候选加 HGB 事件验证器曾在一个有限的 participant-frozen split 上达到 event F1 = `0.7273`（TP/FP/FN = `4/0/3`）。这是探索性结果，样本与验证覆盖有限，不代表稳定泛化水平。
- 同一阶段记录的最佳 candidate coverage recall 为 `0.8571`，低于正式要求的 `0.90`，因此候选覆盖 gate 尚未通过。
- 外部预训练的完整 FD-I、平衡采样 FD-I 和 FD-II 结果分别未超过正式收益门槛或出现负迁移；bounded FD-I cohort 的局部正向结果不能外推为全量方案有效。

当前冻结计划规定：M5 只在 inner participant folds 上选择参数，selection seed 为 `20260910`；随后用 evaluation seeds `20260910`、`20260911`、`20260912` 做稳定性评估。种子和搜索范围已冻结，不表示该评估已经执行或通过。G1 至 G4 的正式门槛为：

- 每个 outer split 的 candidate coverage recall 至少 `0.90`；
- participant OOF 无 all-participant fallback，且不存在 participant 交叉；
- 验证器至少有 20 个正候选，来自至少 5 名参与者；
- 五个 outer fold 的 median event F1 至少比可信 baseline 高 `0.02`，且至少 3/5 fold 不低于 baseline；
- outer fold 的最大 long-FP fraction 不超过 `0.25`，最大边界 MAE 不超过 900 秒。

只有这些门槛和资源检查通过后，计划才进入全量 target-only 训练及 test 推理隔离检查。竞赛隐藏测试标签和官方最终成绩目前均不可用于本地报告。

## 项目结构

```text
.
├── bme_compitition_next/       # Python 项目
│   ├── src/eating_event/       # 数据、特征、模型、指标与验证逻辑
│   ├── scripts/                # 审计、候选模型、验证器与提交入口
│   ├── tests/                  # 单元与数据契约测试
│   ├── configs/                # 可提交模板与本地配置
│   └── docs/                   # 实验、运行、设计和当前实施计划
├── docs/                       # 第一版基线设计与历史实施计划
├── official_test_dataset/      # 本地竞赛资料和数据，不提交
├── external-dataset/           # 本地外部研究数据，不提交
└── tmp/                        # 临时文件，不提交
```

## 环境与安装

要求 Python 3.10 或更新版本。建议使用独立虚拟环境，避免污染系统 Python 或 Conda base。以下命令从仓库根目录执行：

```powershell
cd bme_compitition_next
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

基础依赖包括 NumPy、pandas、PyYAML、SciPy 和 scikit-learn，开发依赖包括 pytest。TCN/Transformer 实验所需 PyTorch 应根据本机 CPU 或 CUDA 环境另行安装匹配版本。

## 配置数据路径

原始数据和元数据必须保留在仓库之外。将示例配置复制为本地配置并编辑路径；`*.local.yaml` 会被 Git 忽略：

```powershell
Copy-Item configs\example.yaml configs\example.local.yaml
```

在 `configs/example.local.yaml` 中设置 `repository_root`、`raw_data_root` 和 `metadata_root`。不要将竞赛数据、外部数据、官方测试标签、模型权重、缓存或本机配置加入版本控制。原始数据规模约 93 GB，应按 session 流式或分块处理。

## 常用入口

从 `bme_compitition_next/` 目录执行：

```powershell
# 检查数据目录和文件格式
python scripts/audit_dataset.py --config configs/example.local.yaml --output artifacts/dataset-audit.json

# 运行现有测试
python -m pytest

# 查看提交 runner 的受控参数和数据隔离约束
Get-Content docs/submission-runbook.md
```

提交 runner 的完整命令、smoke-test 限制和 skipped-file 检查说明见 [`提交运行手册`](bme_compitition_next/docs/submission-runbook.md)。

## 文档导航

以下 2026-09-14 设计与实施计划是当前正式路线的权威文档；更早的设计保留为决策历史，不能与最新方案混用：

- [`当前方案详细设计`](bme_compitition_next/docs/superpowers/specs/2026-09-14-high-f1-event-stack-detailed-design.md)
- [`当前冻结实施计划`](bme_compitition_next/docs/superpowers/plans/2026-09-14-high-f1-event-stack-implementation.md)
- [`实验日志`](bme_compitition_next/docs/experiment-log-2026-09-10.md)
- [`数据与模型预检`](bme_compitition_next/docs/preflight-2026-09-10.md)
- [`外部数据预检及 NO-GO 结论`](bme_compitition_next/docs/external-preflight-2026-09-11.md)
- [`提交运行手册`](bme_compitition_next/docs/submission-runbook.md)
- [`旧版高 F1 方案设计`](bme_compitition_next/docs/superpowers/specs/2026-09-10-high-f1-event-stack-design.md) 与 [`旧版实施计划`](bme_compitition_next/docs/superpowers/plans/2026-09-10-high-f1-event-stack.md)
- [`第一版基线设计`](docs/superpowers/specs/2026-08-31-smartwatch-eating-detection-baseline-design.md) 与 [`第一版实施计划`](docs/superpowers/plans/2026-09-01-smartwatch-eating-detection-implementation-plan.md)

仓库根目录的 [`旧版接续摘要`](handoff-summary.md) 和 [`旧版接续提示`](resume-prompt.txt) 记录的是早期阶段，其中的代码进度、模型路线和路径信息已过时；当前项目状态以本 README 和上面的 2026-09-14 冻结设计/计划为准。

## 数据与合规

竞赛数据和外部研究数据不随仓库分发。使用前请核对竞赛规则、数据许可和参与者隐私要求。外部数据只用于隔离的训练预检；正式提交路径不得读取外部数据或 test 真值。请勿提交原始数据、个人标识信息、预测产物、缓存、权重，或含本机路径/凭据的配置。
