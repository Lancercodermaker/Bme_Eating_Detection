# High-F1 Event Stack Detailed Design

日期：2026-09-14
状态：Design Review 条件通过，架构冻结
工作区：E:/bme_compitition/bme_compitition_next
前置决策：GO WITH RISKS

本文件冻结 2026-09-10 至 2026-09-11 的 Project Preflight、实验记录、外部数据 Preflight 和 constrained design review 结论。它替代旧版“240 s candidate-first”实现计划中的架构假设，但不删除旧文档。

## 1. Goal、指标与约束

### Goal

构建面向官方事件级 F1 的、可复现、可验证、可停止的进食事件检测 pipeline。主目标不是窗口级准确率，也不是单一小 split 的峰值 F1。

### Success metrics

主指标是官方事件级 F1。预测事件与真实事件只有在严格 IoU 大于 0.25 时才算 TP。

每次正式验证必须同时输出：

- TP、FP、FN、Precision、Recall、F1；
- start MAE、end MAE；
- candidate coverage recall；
- long false-positive fraction；
- participant-level mean、standard deviation、worst participant；
- outer split-level mean、median、standard deviation、IQR；
- 推理时间、峰值 host RSS、峰值 GPU memory。

当前没有官方 hidden-test 分数，任何本地结果都不得写成官方结果。

### Constraints

- 正式训练只使用官方 target train。
- 官方 test 不参与训练、阈值选择、模型选择、架构选择或误差分析。
- 原始约 93 GB 数据只读、分块处理，不复制到仓库，不加入 Git。
- 必须按 participant 划分；同一 participant 的全部 session 必须在同一 split。
- ACC、GYRO、PPG 存在重复 timestamp、零 timestamp、覆盖不完整和不可解析文件。
- 主检测轴为 gap-aware 的 10 Hz ACC/GYRO 时间轴。
- GPU 约 8 GB；主 HGB 路线以 CPU 和分块 cache 为主。
- train、validation、test 必须使用完全一致的时间轴、quality mask、feature schema 和 window contract。

## 2. 继承证据

| 证据 | 结论 |
|---|---|
| manifest audit | 1161 个 train session files、43 个 participant、281 个有效餐段、326 个含餐段 session |
| 基础测试 | 官方 IoU、时间轴、raw failure mode 和当前测试共 32 项通过 |
| M0 | event F1 = 0.17284，作为可信本地参照 |
| M1 | event F1 = 0.16867；主要错误是分钟级长 FP；clean-quality F1 = 0.06780 |
| 240 s candidate-only | event F1 = 0.1538，不能作为终点 |
| 15 s/7.5 s local + HGB verifier | 小 participant-frozen split 上 event F1 = 0.7273，TP/FP/FN = 4/0/3；不是稳定结论 |
| best spike candidate coverage | 0.8571，尚未达到正式 0.90 gate |
| TCN candidate-only | coverage 和 FP 不满足接入最终 verifier 的条件 |
| Transformer candidate-only | 当前配置 coverage 不足；保留为受控对照，不接入主路线 |
| full FD-I | F1 = 0.1071，外部预训练 NO-GO |
| FD-I balanced | F1 = 0.1778，未达到 baseline + 0.02 gate |

## 3. Selected Architecture

~~~text
official target-only raw TSV
    -> participant/session manifest
    -> timestamp cleaning and duplicate aggregation
    -> gap-aware 10 Hz ACC/GYRO timebase
    -> quality masks and skipped-file provenance
    -> 15 s / 7.5 s dense local windows
    -> 111-dimensional IMU statistics
    -> high-recall HistGradientBoosting candidate scorer
    -> participant-level OOF candidate scores
    -> event candidate clustering
    -> HistGradientBoosting event verifier
    -> threshold, fusion, duration and boundary constraints
    -> official IoU > 0.25 event evaluation
~~~

架构冻结项：

- target-only；
- 10 Hz IMU 主轴；
- 15 s window、7.5 s stride；
- 不跨真实 gap；
- HGB candidate scorer；
- participant-level OOF verifier；
- event-level verifier 与 constrained decoder；
- official strict IoU/F1；
- submission runner 不读取外部数据和 test truth。

240 s/15 s coarse context 只能作为辅助特征。TCN 只能作为 candidate auxiliary score 或 context representation。Transformer、TCN candidate-only 和外部预训练均不是当前正式主路线。

## 4. 数据契约与接口

### 4.1 Manifest

每个输入文件必须有且只有一个状态：

~~~text
processed
skipped_malformed
skipped_missing_index
skipped_invalid_session
skipped_no_valid_timestamp
skipped_missing_required_imu
skipped_cache_missing
~~~

每条记录至少包含：

~~~text
participant_id: str
session_id: str
path_or_file_id: str
session_start_ms: int
session_end_ms: int
status: str
reason: str | null
row_count: int | null
valid_timestamp_count: int
duplicate_count: int
dropped_timestamp_count: int
~~~

正式验证使用 participant 的全部合格 session。max-files-per-participant 只能用于 smoke test。

### 4.2 Timebase

时间统一为整数毫秒，事件区间为半开区间 [start_ms, end_ms)。

输入：

~~~text
timestamps_ms: [N] int64
values: [N,C] float64
~~~

输出：

~~~text
timestamps_ms: [T] int64
imu_values: [T,6] float32
acc_valid: [T] bool
gyro_valid: [T] bool
imu_valid: [T] bool
ppg_valid: [T] bool
hard_gap: [T] bool
interpolated: [T] bool
~~~

处理规则：

1. 丢弃非有限、零和负 timestamp。
2. timestamp 四舍五入到整数毫秒。
3. 同 timestamp 重复 packet 逐通道 NaN-safe mean。
4. ACC/GYRO 分别清洗并映射到共同 10 Hz grid。
5. 原始相邻有效 timestamp 差值大于 2 s 时建立 hard gap。
6. hard gap 两侧不得插值、不得建立同一窗口、不得聚合为同一事件。
7. PPG 缺失不会使 IMU 主路线失效，但必须记录 quality mask。

### 4.3 Dense windows

主窗口契约：

~~~text
window_seconds = 15
step_seconds = 7.5
grid_hz = 10
window_points = 150
step_points = 75
min_coverage = 0.8
max_gap_seconds = 2.0
~~~

窗口只有在同一 session、同一 continuous segment、IMU coverage 达标且不触及 hard gap 时才生成。

### 4.4 Labels

Window label：

- positive：最大 intersection/window-duration 大于等于 0.5；
- negative：距所有真实事件至少 300 s；
- ignore：其余邻近但边界不确定区域。

ignore 不进入 candidate scorer loss。

Event candidate label：

- positive：至少一个真实事件满足 IoU > 0.25；
- negative：所有真实事件均不满足 IoU > 0.25；
- ignore：候选触及未审计质量区域、hard-gap 边界或标签状态不确定区域。

ignore event candidate 不进入 verifier 训练或评估。

## 5. Participant-level training/evaluation protocol

采用 nested participant validation：

~~~text
outer: 5 participant folds
inner: outer-train participants 上的 4/5 participant folds
~~~

inner fold 负责选择 candidate quantile、verifier threshold、fusion gap、minimum duration、feature variant 和训练预算。outer fold 只做最终比较。

OOF 规则：

1. 每个 outer-train participant 都由不包含该 participant 的 candidate model 打分。
2. OOF fallback 必须为 0。
3. 如果排除某 participant 后训练集无法形成二分类模型，则该 participant 标记 OOF_UNAVAILABLE，不能使用 all-participant model fallback。
4. OOF score 必须保存 fit participant 列表、fold、schema hash 和 threshold reference。
5. verifier 训练至少需要 20 个 positive event candidates，且来自至少 5 个 participant。

当前 source 中的 all-participant fallback 是实现阻塞项，不是可接受协议。

## 6. Candidate scorer、verifier 与 decoder

Candidate table：

~~~text
features: [W,111] float32
labels: [W] int8, values in {1,0,-1}
participant_ids: [W] object/string
windows: tuple[W]
~~~

Event candidate baseline feature：

~~~text
event_features: [E,16] float64
event_labels: [E] int8
~~~

16 维包括 candidate score 的 max/mean/std/p25/p75/min、window count、duration、density、coverage mean/min/max 和 start/end day-phase sin/cos。

HGB candidate scorer 的初始配置：

~~~text
learning_rate = 0.05
max_leaf_nodes = 31
min_samples_leaf = 1
l2_regularization = 1e-3
positive_weight = 3.0
max_iter = 100
~~~

HGB event verifier 的初始配置：

~~~text
learning_rate = 0.05
max_leaf_nodes = 15
l2_regularization = 1e-3
positive_weight = 3.0
max_iter = 100
~~~

候选 threshold 以 inner-selected score quantile 表示。每个 candidate model 使用自己的 fit-participant score distribution 产生 threshold，verifier 使用相对分数，避免 OOF/full-train probability scale 错位。

初始 decoder 参数：

~~~text
candidate_fuse_gap = 300 s
decode_fuse_gap = 600 s
min_duration = 180 s
~~~

事件只能在同一 session、同一 continuous segment 内融合。默认边界为所选窗口的最小 start 与最大 end，之后只裁剪到 session/segment 边界，不使用 GT snapping。

## 7. Artifact、checkpoint 与资源管理

每个 run 使用：

~~~text
artifacts/<run_id>/
    config.resolved.yaml
    split_manifest.json
    data_manifest.jsonl
    timebase_audit.jsonl
    skipped_files.jsonl
    cache/
    candidate_model/
    oof_scores/
    event_candidates.parquet
    verifier_model/
    predictions.parquet
    metrics.json
    participant_metrics.json
    environment.json
    feature_schema.json
    checksums.json
    run.log
~~~

cache key 必须包含 source fingerprint、timebase/window/label config、feature schema version、code/schema version。

资源规则：

- 一次只处理一个 session；
- raw reader 使用 bounded chunk，默认 200000 rows；
- cache feature 使用 float32；
- HGB 运行在 CPU；
- 可选 TCN 的 GPU batch 必须动态受限；
- host RSS 不超过可用内存约 60%；
- 8 GB GPU peak allocation 小于 7 GB；
- audit、cache、fit/eval 都必须有 wall-time budget。

## 8. Risk gates 与 escalation

### Gate criteria

- G0 data contract：所有文件有显式状态；无 silent skip；timebase fixture 与参考结果一致。
- G1 candidate coverage：每个 outer split pooled candidate coverage recall 至少 0.90。
- G2 OOF：OOF fallback 为 0；不存在 participant membership violation。
- G3 verifier data：至少 20 个正 event candidates，来自至少 5 个 participant。
- G4 event quality：median outer F1 至少为可信 baseline + 0.02，至少 3/5 split 不低于 baseline，long FP fraction 不高于 0.25，boundary MAE 不超过 900 s。
- G5 resource：内存、GPU、时间和 cache 恢复均满足资源预算。
- G6 submission：无外部数据、无 test truth、无 GT-neighbor sampling，且 deterministic rerun 一致。

任何 gate failure 必须标记为 IMPLEMENTATION、CONFIGURATION、OPTIMIZATION、DATA/PIPELINE、ASSUMPTION、ARCHITECTURE、REQUIREMENT_INFEASIBLE 或 UNKNOWN 中的一个。

architecture reopen 只有在：

1. candidate coverage 多个 participant-frozen split 持续不足；
2. event F1 多 seed、多 split 持续无法超过可信 baseline；
3. verifier 只在单一小 split 有效；
4. long FP、boundary MAE 或 worst participant F1 在扩大验证后持续恶化；
5. loss/window 指标提升但 event F1 持续不提升；
6. 发现 test、GT 邻域、跨 gap 插值等泄漏；
7. full target scale 无法满足资源约束。

## 9. Design Review

判定：**CONDITIONAL PASS**。

已确认：

- Selected Architecture 与 Preflight 一致；
- 外部数据已排除；
- candidate、OOF verifier、event decoder 和 official evaluator 职责清晰；
- evaluation 和 artifact contract 可执行；
- architecture freeze 与 kill criteria 已明确。

实现前必须先修复：

1. OOF all-participant fallback；
2. silent file/row skip；
3. cross-session merge；
4. formal run 中的文件选择偏差；
5. inner-only threshold selection；
6. cache schema version；
7. participant/split metrics；
8. full-scale resource audit。

当前架构仍可行，当前 limiting factor 是 data/pipeline protocol，而不是模型容量。

## 10. Implementation milestones

### M0 Contract freeze

输入：本文件、现有 source/tests、Preflight evidence。
输出：config、manifest、timebase、window、label、prediction、metrics schema。
验收：所有 shape、类型、状态、冻结参数和禁止项明确。
停止：任何模块仍可读取 test truth、使用 all-participant OOF 或跨 gap 建窗。

### M1 Manifest and timebase audit

输入：synthetic fixtures、少量 train/test parser fixtures。
输出：显式 skipped provenance、duplicate/gap audit、10 Hz regularized series。
验收：无 silent skip；hard gap 不被跨越；无有效 timestamp 文件只被跳过并记录。
停止：timebase 与已有 sentinel 不一致或 parser 丢行不可追踪。

### M2 Dense local cache and coverage

输入：M1 regularized sessions。
输出：15 s/7.5 s candidate cache、labels、quality report。
验收：features 为 [W,111]；无跨 gap window；每 outer split candidate coverage 至少 0.90。
停止：coverage 不达标或 cache schema/hash 不完整。

### M3 HGB and honest OOF

输入：M2 candidate tables、outer-train participants。
输出：full candidate model、participant OOF scores、membership audit。
验收：OOF fallback=0；每个 score 的 fit participant 不含被评分 participant；verifier 正样本 gate 达标。
停止：发生 membership violation 或正样本不足。

### M4 Event verifier and inner decoder selection

输入：M3 OOF scores。
输出：event candidate table、verifier、inner-selected decoder config。
验收：candidate coverage 先过 G1；所有 threshold/fusion/min-duration 只由 inner 选择；long FP 与 boundary metrics 可计算。
停止：verifier 只在单 split 有效或长 FP 持续超过 gate。

### M5 Nested outer evaluation

输入：M4 pipeline、5 outer folds、至少 3 seeds。
输出：overall/macro/worst/split metrics 和稳定性报告。
验收：G4 通过。
停止：只在单 split 提升、loss 与 event F1 脱钩或 architecture kill criteria 被触发。

### M6 Full target-only scale run

输入：全部 target train participant/session、已通过 M5 的 config。
输出：full checkpoints、OOF verifier、resource report、reproducible artifacts。
验收：G5 通过，cache 可恢复，所有输入状态可审计。
停止：OOM、不可控运行时间、cache corruption 或新发现的 leakage。

### M7 Submission isolation

输入：M6 checkpoints、official test raw files。
输出：prediction table、submission serialization、isolation report。
验收：G6 通过；相同 config/seed 两次输出一致；test truth 和 external path 均为零引用。
停止：任何 forbidden input 被读取或 preprocessing contract 不一致。

## 11. 未解决问题

- full target participant/session 上的 candidate coverage 尚未通过 0.90；
- verifier 正样本数在正式 nested split 下未知；
- threshold、fusion 和 boundary 规则的跨 split 稳定性未知；
- full-scale 内存、I/O 和时间尚未测量；
- PPG 是否能改善事件级 F1 尚未证明；
- boundary trim 尚未证明有稳定收益；
- 外部 FD-I bounded cohort 的正向结果不能外推到正式路线。
