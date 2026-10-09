# 智能手表进食事件检测

这是面向生物医学工程竞赛的腕戴设备进食事件检测项目。目标是从智能手表的 ACC/GYRO 惯性传感器数据中定位连续进食时段，并按竞赛规则评估事件级结果。PPG 数据已纳入数据质量审计和实验对照，但目前没有证据支持把它作为正式检测路线的必要输入。

> **项目状态（README 更新于 2026-10-09）：**9 月 14 日的高 F1 方案只是后续开发的起点。此后完成了 A1 五折端到端可行性、A2 上下文验证器和 Route 3 目标改造等实验，也继续推进 Route 2 的执行隔离工程。可追溯的最佳完整 pooled event F1 为 A2-004 的 `0.623482`，但相关开发验收未通过；Route 2 截至最新记录（2026-10-02）仍未获实验授权。全量训练与生产提交保持阻塞，且没有官方隐藏测试成绩。

## 任务与当前方案

竞赛以事件级 Precision、Recall、F1 为核心指标：预测区间与真实区间必须满足严格 `IoU > 0.25` 才算命中，同时报告正确匹配事件的起止时间 MAE。数据划分按 participant 进行，避免同一个人的 session 同时进入训练与验证；官方 test 不参与训练、阈值选择或模型选择。

2026-09-14 设计记录中的初始高 F1 方案将主线设为 target-only IMU 检测：

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

窗口不能跨越真实时间缺口。PPG 保留质量标记，但不属于已验证的检测输入；TCN、Transformer 和外部 FD 数据只作为受控实验或对照，不能据此进入最终 test 推理路径。完整 FD-I/FD-II 预训练没有通过预设收益门槛。

9 月 14 日之后，开发从方案设计继续进入数据资格复核、完整五折端到端验证、事件上下文验证器和候选区间匹配改造。9 月底起，重点转向 Route 2：验证候选区间融合规则，并补齐受控跨平台执行、输入隔离和资源记账。Route 2 的工程预检和合成测试不等于真实数据实验；当前完整 A+B 申请仍为 `NOT_EXPERIMENT_AUTHORIZED`。因此，9 月 14 日计划应作为路线历史阅读，不能再描述为最新冻结的已验收方案。

## 已有实现

`bme_compitition_next/` 中已有 Python 实现包括：

- 原始数据读取、manifest、数据审计、标签与窗口生成、时间轴处理及 IMU 特征提取；
- 事件级指标、HGB 候选模型与事件验证器原型；
- TCN、Transformer 和外部数据预检实验入口；
- 官方提交预测 runner，以及对应测试和运行手册。

这些组件构成实验原型，不能据此推断冻结的正式管线已通过全部验收。当前正式实施计划还要求补齐统一 schema/artifact/telemetry 契约、严格无回退的 participant OOF、覆盖率 gate、nested 参数选择和资源审计。现有提交 runner 也需要通过这些验收后，才可作为最终竞赛交付流程。

## 实验结论与验收状态

历史数据审计记录包括 1,161 个训练 session 文件、43 名参与者、281 个标注餐段和 326 个含餐 session。后续资格审查将开发评价限定为 41 名参与者和 234 个 canonical eligible ground-truth 事件；两组统计的口径不同，不能直接互换。

早期模型结果仍有参考价值，但代表不同证据阶段：

- 本地可信参照为 M0 q50 + GroupNorm，event F1=`0.17284`；M1 IMU/PPG 融合为 `0.16867`，没有超过该参照。
- 15 秒窗口、7.5 秒步长的候选模型曾在一个样本很小的 participant-frozen split 上达到 F1=`0.7273`（TP/FP/FN=`4/0/3`）。该探索结果和之后完整五折 pooled 指标的验证范围不同，不能作为整体泛化成绩。
- 此前候选覆盖率最高记录为 `0.8571`；后续 A1/A2 的候选覆盖是 `213/234`，但“存在可匹配候选”不等于最终一对一匹配的 TP 数。
- 完整 FD-I、平衡采样 FD-I 和 FD-II 预训练没有通过预设收益门槛或出现负迁移；bounded FD-I cohort 的局部结果不支持把外部预训练纳入正式检测路线。

### 2026-09-14 之后的完整事件级结果

下表为当前工作区检出的完整五折本地开发结果，均按 41 名开发参与者、234 个 eligible GT 和 participant-level one-to-one 匹配评估。它们是开发证据，不是独立参与者确认集，也不是官方测试成绩。

| 实验 | pooled TP / FP / FN | pooled event F1 | 状态与解释 |
|---|---:|---:|---|
| A1 端到端可行性 v1-005（2026-09-22） | 153 / 136 / 81 | `0.585086` | 五折执行完成；最低及理想开发门槛均未通过，协议关闭 |
| A2 上下文验证器 v1-004（2026-09-24） | 154 / 106 / 80 | `0.623482` | 相对 A1 提高 `0.038396`；仍未达到最低 pooled F1 或其他 stage 门槛，固定 26D 变体关闭 |
| Route 3 matching-aware v1-003（2026-09-27） | 150 / 126 / 84 | `0.588235` | 较 A2 低 `0.035246`；四项 numeric/stage 门槛均未通过，该变体关闭 |

在这些有完整指标文件对应的结果中，A2-004 是可追溯的最高 pooled event F1。A1 的 `outer-3` 单折 F1 为 `0.6494`，它不是 pooled F1。项目记录者提到另有一次约 `0.64` 的 pooled 探索结果；本次检查工作区内的完整结果报告与上述各次 `metrics.json` 后，没有找到可对应的 run ID 和指标产物，因此先保留为未归档的探索记录，不与可复核结果混记。找到该次运行的结果文件后，可再补齐其配置、分折和数据口径。

后续实验沿用的本地最低/理想目标为 pooled F1 `0.66 / 0.80`；stage 最低门槛还要求至少 3/5 折 F1≥`0.66`、每折 long-FP fraction≤`0.25`，且匹配事件 start/end MAE 各≤`900` 秒。A1、A2-004 和 Route 3 v1-003 均未满足最低门槛。该门槛是本地开发合约，不应表述为已经满足竞赛官方评估协议。

### 当前工程与实验准入状态

- 数据资格和边界合约在 9 月中旬重新审查后，完整 A1、A2 与 Route 3 试验均已留下独立结果记录；A1、固定 26D A2 和 Route 3 v1-003 已关闭，不应把早期待执行方案写成当前仍在等待首次验证。
- Route 2 的候选区间方案持续进行了 WSL/Linux 受控执行、隔离和资源控制开发。最新记录日期为 `2026-10-02`：跨平台 no-data 合成测试各有 203 项通过，但概率结果仍仅为部分数值匹配；完整实现复审仍为 `FAIL / NOT_APPROVAL_READY`，负责人批准尚未签发，故 Stage A/B 均未运行。
- 当前整体状态仍为 Formal G1 `FAIL`、full training `BLOCKED`、production `UNCHANGED`。41 名参与者均已用于开发决策，现有五折结果不能当作独立参与者验证。
- 没有可报告的官方隐藏测试成绩。全量训练、最终 test 推理及提交 runner 的生产验收均未完成；本地 F1 不能代替官方成绩。

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

本 README 于 `2026-10-09` 更新；本次复核到的最新项目决策/证据记录日期为 `2026-10-02`。以下链接指向当前 `main` 中已跟踪的文档，其中 2026-09-14 设计和实施计划是路线历史基线，不代表当前实验已验收：

- [`当前方案详细设计`](bme_compitition_next/docs/superpowers/specs/2026-09-14-high-f1-event-stack-detailed-design.md)
- [`2026-09-14 高 F1 实施计划`](bme_compitition_next/docs/superpowers/plans/2026-09-14-high-f1-event-stack-implementation.md)
- [`实验日志`](bme_compitition_next/docs/experiment-log-2026-09-10.md)
- [`数据与模型预检`](bme_compitition_next/docs/preflight-2026-09-10.md)
- [`外部数据预检及 NO-GO 结论`](bme_compitition_next/docs/external-preflight-2026-09-11.md)
- [`提交运行手册`](bme_compitition_next/docs/submission-runbook.md)
- [`旧版高 F1 方案设计`](bme_compitition_next/docs/superpowers/specs/2026-09-10-high-f1-event-stack-design.md) 与 [`旧版实施计划`](bme_compitition_next/docs/superpowers/plans/2026-09-10-high-f1-event-stack.md)
- [`第一版基线设计`](docs/superpowers/specs/2026-08-31-smartwatch-eating-detection-baseline-design.md) 与 [`第一版实施计划`](docs/superpowers/plans/2026-09-01-smartwatch-eating-detection-implementation-plan.md)

9 月 15 日至 10 月 2 日的详细 A1/A2/Route 3 结果、Route 2 决策与执行证据目前保存在本地 `codex/high-f1-event-stack-execution` 开发工作树的 `bme_compitition_next/docs/` 和 `artifacts/` 中，尚未纳入当前 `main` 分支，因此 GitHub `main` 上不能直接打开这些后续文档或指标产物。本 README 已按该工作区记录更新摘要；后续如需在 GitHub 上审阅完整来源，应将相应文档与代码一起发布，不能只依赖此摘要。仓库根目录的 [`旧版接续摘要`](handoff-summary.md) 和 [`旧版接续提示`](resume-prompt.txt) 记录更早阶段，不能作为当前状态来源。

## 数据与合规

竞赛数据和外部研究数据不随仓库分发。使用前请核对竞赛规则、数据许可和参与者隐私要求。外部数据只用于隔离的训练预检；正式提交路径不得读取外部数据或 test 真值。请勿提交原始数据、个人标识信息、预测产物、缓存、权重，或含本机路径/凭据的配置。
