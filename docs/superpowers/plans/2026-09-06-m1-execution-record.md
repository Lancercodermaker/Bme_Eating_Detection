# M1 执行与门禁记录

用户于 2026-09-06 明确授权启动 M1；旧文档的“等待授权”状态由此覆盖。
仅使用现有 `codex/smartwatch-eating-baseline` worktree，不合并、不 push、不启动 M2/M3/M4。

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
实验：9 项 RED（缺少函数）→ 13 项 IO GREEN → 全套 81 passed，compileall/diff check 通过；提交 `d05665f`。独立审查进行中。

## PPG cache 契约（待 TDD 实现与验证）

- 独立 `cache/m1_ppg/`，独立 schema/modality 指纹；绝不修改既有 IMU cache。
- 每文件连续 `(45,T)` float32：44 波形 + 1 row quality；另存 `(1,T)` bool quality、int64 时间轴/窗口索引/窗口边界、float32 soft label、bool loss mask。
- 保留 44 通道定义和既有 all-finite/nonzero 行 mask；额外平坦质量检查必须显式记录，不能伪装成原 parser 等价语义。
- 先对 PPG timestamp 稳定去重聚合，再恢复统一网格，再抗混叠重采样。无效波形置零且质量为 false。
- 通过显式目标时间轴契约对齐 M0 窗口；对齐信息纳入 key，不能按窗口序号盲拼。
- 原始波形 cache 与训练集拟合的标准化统计分离；统计只用 train 有效样本，val 复用。
- key 包括源路径/size/mtime、采样率/max_gap、预处理变体、窗口/标签配置和区间、modality/channel/schema、显式对齐范围；hit 只 stat 源文件，不打开 CSV。
- 临时文件写入成功后原子改名；逐文件恢复；batch 切片，不保存重叠窗口 clone。

## 待完成

- [ ] PPG parser 独立审查与缺失模态覆盖。
- [ ] PPG cache 严格 TDD、数值/窗口/label 等价、原子写入和中断恢复验证、阶段提交。
- [ ] 独立 IMU/PPG encoder、显式 mask、安全 modality dropout，严格 TDD 与 CUDA 样例、阶段提交。
- [ ] cache/train CLI 集成与 test 排除验证，PPG-only sample，full-data gate。
- [ ] 同 split train/val 全量 cache、PPG-only 诊断、复用 M0 reference、M1 联合训练与缺失模态实验。
- [ ] 事件指标、MAE、calibration、coverage 和 CPU/GPU 分开遥测。
- [ ] 全套最终验证、README/handoff/实施计划更新与提交，保留现有分支/worktree。
