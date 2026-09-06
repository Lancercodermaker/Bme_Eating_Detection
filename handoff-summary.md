# 智能手表进食检测项目：新对话接续摘要

## 2026-09-06 M1 remediation 交接（最新权威状态：capped availability loss 后仍不启动 M2）

本节覆盖下方旧版 M1 error-analysis gate；它是当前关于 remediation 和高级方向选择的唯一权威节。严格只使用 frozen train/validation artifacts，未读取竞赛 test participant/data，未重训 M0、未重建 `cache/m0_full`，未创建或运行 M2。

### 事实

- 起始 HEAD=`920ca23b91e082c1192968234471553342410030`，worktree=`E:\bme_compitition\.worktrees\smartwatch-baseline`，分支=`codex/smartwatch-eating-baseline`；项目解释器固定为 `C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe`。frozen split SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6`。
- 根因复核确认：M1 的长期 FP 是高分连续输出，不是 decoder 短抖动；`both`/`imu_only` availability 与分数耦合，`neither` 的稀有正例在直接分层 `neg/pos` 权重下会被夸大；Recall 不足还包含 `hnu21042` 的 6 个不可观测事件。
- 只选择一个 M1 remediation 方向：availability-invariant BCE。先完成 TDD RED→GREEN，再用 train-only availability 分层 `pos_weight`，并将每个分层权重上限设为原 global `pos_weight`，仍使用 BCE logits、原 decoder 契约、participant split 和 train-only statistics。未叠加 M2/M3/M4。
- 首次未限幅实验 `artifacts/m1_fusion_availability_stratified_e1/` 的 `neither` 权重=`648.2119`，造成 `neither` 预测正率=`1.0`，validation F1=`0.0777385`；该变体作为反例保留，不作为最终候选。
- 最终 capped 实验 `artifacts/m1_fusion_availability_stratified_e2/`：train/val windows=`2,985,246/593,589`，IMU/PPG cache=`1121/1121 hit`，训练=`3041.14 s`，3 epoch 均约=`1011.88/1013.40/1014.60 s`，CUDA max allocated=`94.15 MB`。capped weights=`both 15.4561`、`imu_only 14.9599`、`ppg_only 0`、`neither 35.1769`。
- e2 validation TP/FP/FN=`24/335/27`，Precision/Recall/F1=`0.0668524/0.4705882/0.1170732`，participant F1 mean/std/worst=`0.0981172/0.0612279/0`，start/end MAE=`817518.5/62955.9 ms`。相对原 frozen M1 F1=`0.1686747`，该候选未改善主指标。
- e2 FP 仍不是短暂噪声：335 个 FP 的 duration median/p90/max=`297000/8387965.2/24687528 ms`，window count median/p90=`92/2769.4`，max-score median=`0.5374218`；按 duration≤`30000 ms` 且 window count≤2，仅 `10/335=2.9851%` 短暂 FP。`both` predicted-positive rate=`0.9972938`、FPR=`0.9971748`；`neither` 已降至概率=`0.0864576`、预测正率=`0`，但双模态长 FP 耦合仍在。
- 独立报告为 `artifacts/experiments/m1_fusion_availability_stratified_e2/error_analysis.json`，且记录 source/cache、split hash、decoder=`threshold 0.1 / merge_gap 9000 / min_duration 0`、`test_data_read=false`。M2 gate=`false`：short-FP dominance=`false`、Recall>50%=`false`（观察值=`47.0588%`）、probability/validity/interval context support=`false`。

### 风险、候选与验收标准

- 风险：capped loss 修正了 `neither` 的全正 shortcut，却没有解决 `both` 的长时间高分 FP；F1 低于原 M1，不能为了启动 M2 解释为成功。test 仍完全不在选择环路内。
- 候选只保留一个高级方向决策：M2 仅在短暂 FP≥50%、positive-event Recall 严格>50%、且 error analysis 支持 context 三项同时满足时启动；M3/M4 没有本轮证据。
- 操作化标准保持不变：短暂 FP 为 duration≤`2×window_sec=30000 ms` 且 window count≤2；gate 三项全部满足才通过。

### 选择与交付

- 选择：`do_not_start_advanced_models`。不创建 `src/eating_detection/context_model.py`、`configs/experiments/m2_context.yaml`、M2 测试或 M2 训练输出。下一步建议是先针对 `both` 的 availability/mask prior 做单一 M1 方向的独立证据实验，再重新 gate；当前不进入 M2。
- 已完成代码范围：`training.py` 支持显式 `m1_loss_mode=availability_stratified_bce`，旧 M1 config 默认保持 `global_bce`；新增 capped-stratum TDD 覆盖。README、执行记录和本交接节均记录 e1 反例、e2 结果及 no-M2 结论。

## 2026-09-06 M1 交接（最新权威状态：validation error-analysis gate）

本节覆盖下方旧版“全量结果与最终验证”状态，是当前关于高级方向选择的唯一权威节。已在不读取原始 CSV/test、不重训 M0/M1 的条件下，对 frozen M1 fusion validation 输出完成 error analysis；M2 evidence gate 不满足，因此不创建或运行 M2/M3/M4。

### 事实

- 分析来源为 `artifacts/m1_fusion_full_e3/` 的 frozen validation 输出、`cache/m0_full` 与 `cache/m1_ppg` 的窗口/quality/cache metadata；结果写入 `artifacts/experiments/m1_fusion_full_e3/error_analysis.json`。来源 run-dir、两个 cache 目录、decoder=`threshold=0.15, merge_gap_ms=6000, min_duration_ms=0`、`event_iou_threshold=0.25`、`label_positive_overlap=0.25`、split manifest SHA-256=`18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6` 均已记录；reference hash 逐 validation cache 校验通过。
- M1 fusion validation：windows=`593589`，TP/FP/FN=`21/177/30`，Precision/Recall/F1=`0.1060606/0.4117647/0.1686747`，participant F1 mean/std/worst=`0.1481688/0.1077214/0`，start/end MAE=`637874.6/79659.7 ms`。独立复算与 `artifacts/m1_fusion_full_e3/metrics.json` 逐项相等。
- FP 不是短暂噪声：177 个 FP 的 duration 中位数=`1963878 ms`（约32.7分钟）、p90=`12265790.4 ms`、max=`24915528 ms`；窗口数中位数=`644`、p90=`4071`；最大分数中位数=`0.8851013`、事件平均分数中位数=`0.7146850`；前/后相邻预测事件间隔中位数均=`117000 ms`。按本报告固定的“短暂”操作定义（duration≤`30000 ms` 且≤`2`个窗口），仅 `6/177`=`3.39%` FP 属于短暂。
- Calibration：binary Brier/ECE=`0.2398206/0.3741050`，soft overlap Brier/ECE=`0.2398207/0.3744612`。modality 分层为 `imu_only=24070`、`ppg_only=0`、`both=248689`、`neither=320830`；decoder threshold=`0.15` 下 imu-only 与 both 的窗口预测阳性率均为1且窗口 FPR均为1，neither 的预测阳性率为0。PPG-only 诊断为 F1=`0.1792453`、Recall=`0.3725490`，不能替代 fusion 主结果。
- 同 split M0 `artifacts/m0_final_q50_group_e3/`：F1=`0.1728395`、P/R=`0.109375/0.4117647`、start/end MAE=`639946.0/71945.5 ms`、participant F1 std=`0.1137248`。M1 fusion 相对 M0 的 F1 delta=`-0.0041648`，Recall 无提升，end MAE 增加约`7714.3 ms`；split JSON 三份完全相同。

### 风险、候选与验收标准

- 风险：M1 是同一 frozen participant split、3 epoch、单次 full run；validation 仍有长时间高分 FP、Recall 仅`41.18%`，且 modality availability 与分数强耦合。任何基于 test 的再选择都仍被禁止。
- 候选：M2（短暂 FP + 足够正事件 Recall）；M3（局部连续性/边界抖动）；M4（M1 稳定后的自监督）；不启动高级模型（信号、coverage 或 Recall 不足）。
- 验收标准：M2 需同时满足短暂 FP 占主导、正事件 Recall 超过半数，并且 error analysis 明确支持概率/有效性/间隔 context；若主要错误是长时间连续误报或整体 Recall/coverage 不足，则不启动高级模型。报告将短暂 FP 明确操作化为 duration≤`2×window_sec` 且窗口数≤2，dominance≥50%，正事件 Recall>50%。

### 选择与实验结果

- 选择：`do_not_start_advanced_models`。M2 gate=`false`（short FP dominance=`false`、positive-event recall sufficient=`false`、context support=`false`）；M3/M4 也未获证据支持。只保留 M0/M1 frozen artifacts，不创建 `context_model.py`、M2 config 或 M2 训练输出。
- 工具增强为 `src/eating_detection/error_analysis.py` 的 M1 双 cache validation 分析路径；新增合成 cache TDD 回归为 `tests/test_m1_error_analysis.py`。新增路径只读 cache/JSON/YAML，不触碰源 CSV；原有 M0 error analysis CLI 兼容保留。
- 本节基于起始 HEAD=`3e5e38e`；最终提交后仍保留当前分支/worktree，不合并、不 push。

## 2026-09-06 M1 交接（最新权威状态：全量结果与最终验证）

本节覆盖下方旧版“全量运行资源门禁”状态；它是当前唯一权威状态。代码修复已完成并提交，full-data PPG-only 与 fusion 已完成；最终新鲜验证已全绿，当前只需提交本节记录。

### 事实

- worktree 为 `E:\bme_compitition\.worktrees\smartwatch-baseline`，分支为 `codex/smartwatch-eating-baseline`；仅使用项目解释器 `C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe`。紧凑 PPG cache 修复与测试/config 修改已原子提交为 `08d571a fix: guard oversized PPG cache allocation`；不合并、不 push。
- 严格 TDD 已覆盖：compact miss；lazy compact cache-hit 在 PPG reader 抛错时仍不读 CSV；batch 只生成局部 `(45, window_length)` 零 PPG 与 `(IMU,PPG)=(1,0)` mask；未显式 M0 reference 时，`max_dense_samples` 也进入 cache key，避免阈值变化错误命中旧 dense cache。专项最终 `48 passed`，全套最终代码测试 `131 passed`；独立审查未发现 P0/P1。
- 三份 M1 YAML 已显式记录 `ppg_max_dense_samples: 1000000`。超限 reference 使用 `storage=all_missing_compact`，保留 M0 reference/window/label/hash 对齐，不分配 `45×T` dense 数组。
- 完整 PPG-only：`artifacts/m1_ppg_only_full_e3/`，3,578,835 windows（train 2,985,246 / val 593,589），F1=`0.1792453`，P=`0.1180124`，R=`0.3725490`，start/end MAE=`839148.2/74066.6 ms`；binary calibration Brier/ECE=`0.1670272/0.3231965`，soft=`0.1668948/0.3235527`。PPG cache 为 112 hit/1009 miss，build=`1162.15 s`，load=`0.983 s`；训练=`2953.12 s`，epoch 均值约=`982.15 s`。
- 完整 fusion：`artifacts/m1_fusion_full_e3/`，同一 3,578,835 windows，`modality_dropout=0.25`，F1=`0.1686747`，P=`0.1060606`，R=`0.4117647`，start/end MAE=`637874.6/79659.7 ms`；binary calibration Brier/ECE=`0.2398206/0.3741050`，soft=`0.2398207/0.3744612`。IMU/PPG cache 均 1121/1121 hit；训练=`3097.80 s`，epoch 均值约=`1029.65 s`。
- fusion 验证覆盖为 593,589 windows：IMU available=`272,759`，PPG available=`248,689`，both=`248,689`，neither=`320,830`；PPG-only 诊断显式将 IMU 全部置缺，验证 PPG available=`248,689`、neither=`344,900`。这些是 coverage 与 mask 证据，不是额外的 test 或独立反事实重训。
- 冻结 M0 参照 `artifacts/m0_final_q50_group_e3/`：F1=`0.1728395`，P=`0.109375`，R=`0.4117647`，start/end MAE=`639946.0/71945.5 ms`。三套 split manifest SHA-256 均为 `18caba0864331037df66745668d56cabb0499af4c9f2799e2e7b4114394feef6` 且 JSON 相等；test 未读取/训练，CLI 输出 `test_not_used=true`。
- `cache/m1_ppg` 与 `artifacts/m1_ppg_only_full_e3` 未删除。PPG cache 当前共有 1,136 个 `.npz`；本次新 compact 记录 87 个。目标 HNU21004 reference 长度 23,645,128 的记录为 `all_missing_compact`，`features=[45,0]`、window indices=`[315264,2]`；既有旧 cache 记录均保留。
- 原始数据只读复核：`artifacts/m1_preflight/source_metadata_before.json` 的 2,378 条 size/mtime 全部未变化；没有原始数据路径进入 Git。CUDA full runs 均使用 RTX 5060 Laptop，未启动 M2/M3/M4。

### 风险、选择与验收

- 风险：PPG-only 是诊断且 compact PPG 是显式缺失模态，不是从稀疏点外推；全量结果为冻结 split、3 epoch、单次 run，不能据此宣称 M1 已优于 M0。fusion 的缺失模态报告目前以真实 coverage、显式 mask 和训练 dropout 为主，未另造 test-like 反事实训练。
- 选择：保留 full fusion 作为 M1 主结果，PPG-only 作为诊断，M0 作为只读参照；不重训 M0、不删除 cache/artifact、不追加 M1 超参搜索。
- 最终验收已通过：全套 `131 passed`，PPG cache/M1 专项 `48 passed`，compileall、diff check、CUDA smoke、cache-hit/lazy 回归、split equality、原始 metadata、Git raw/ignore 检查均通过。下一步仅提交文档结果，保留本分支/worktree，不合并、不 push。

## 2026-09-06 M1 交接（最新权威状态：全量运行资源门禁）

本节覆盖紧随其后的旧版“2026-09-06 M1 交接”及所有更早历史材料。用户要求交接而非暂停或放弃 M1；新对话须保留以下未提交修改，并从其严格 TDD 验证继续。

### Objective

在既有 worktree 中完成 M1 的全量 PPG-only、冻结 M0 参照和融合训练；先让 PPG cache 在异常超长 IMU reference 上以安全、可验证的紧凑缺失模态表示恢复运行。不要重搜文献、重训 M0、创建 worktree、合并或 push。

### Current Status

- worktree：`E:\bme_compitition\.worktrees\smartwatch-baseline`；分支：`codex/smartwatch-eating-baseline`；HEAD：`174b82c docs: record M1 full-data gate`。当前修改**未提交**：本交接的 `handoff-summary.md` / `resume-prompt.txt`，以及 `src/eating_detection/{ppg_cache,dataset,training,cli}.py` 和 `tests/test_m1_data.py`；必须保留。
- 已提交的 M1 链条：PPG parser/cache（`d05665f`、`47f2f41`、`d93f9e3`）、M1 core（`3d970f1`）、配对 cache（`b2bfdbc`）、缓存训练（`4d76501`）、CLI（`986e8d4`）、calibration（`5bedd93`）和 gate/documentation（`174b82c`）。此前全套测试 **127 passed**；这是紧凑修复之前的结果。
- 两个真实 bounded CUDA 样例、M0-cache 参数/原始数据/ignore/CUDA 检查已经通过，但它们未覆盖异常长 reference。因此“输入/隔离门禁通过”不等于“全量 M1 可跑”。完整 PPG-only 首次运行在 PPG cache 构建期被系统终止，尚未产生训练 metrics/checkpoint；没有可报告的全量 M1 结果。
- 失败文件为 `E:\bme_compitition\official_test_dataset\Data\02_traindataset\organized\HNU21004\sensorData-1784555315601-539a8c024e96427a98597987cd3ca1e6\collect_data0_1783594392_1784540197.txt`。对应 M0 cache `cache/m0_full\bc\bc2d886f22330793a591da026202dad502ec6b47de75c92ed2a3b26394bac65f.npz` 的 reference 长度为 23,645,128（约 262.7 小时）；原始文件仅有 109,380 个有效 PPG 行。既有 PPG builder 为此分配 44×T dense float32 waveform（峰值远超可用内存），进程无 Python traceback 地被终止。
- 当前未提交的 TDD 修复新增 `PPGCacheConfig.max_dense_samples=1_000_000`：超限 reference 将保存完整 M0 window/label 契约与 reference SHA-256 metadata，但不写多 GB dense PPG；`storage='all_missing_compact'` 表示 PPG 显式不可用，paired dataset 以局部 `(45, window_length)` 零数组和 `(IMU, PPG)=(1,0)` mask 提供 batch。配对验证以 reference hash 而非空 timestamps 保持严格对齐；PPG train-only standardizer 跳过 compact cache；CLI 已传入此配置。
- 该修复的首个 RED 已记录：新增 `test_paired_dataset_uses_compact_all_missing_ppg_cache_for_an_excessive_reference` 起初因缺少 `max_dense_samples` 失败。实现已写入但**尚未重新运行 GREEN、未独立审查、未提交**。配置 YAML 也尚未显式写入该新阈值（CLI 当前默认值可用）；应在验证后补齐以保证可复现。

### Frozen Decisions

- 原始数据只读且不进 Git；只使用 `artifacts/final_m0/split_manifest.json` 的 34 train / 8 val participant split；test 不参与训练、选择或缓存输入。
- 复用 `cache/m0_full` 的 1,121 个冻结 IMU cache 和 M0 reference；PPG 仅写 `cache/m1_ppg`。不得重训/重建 M0，也不得修改 M0 parser/cache。
- M1 为从头训练的独立 IMU/PPG GroupNorm encoder、embedding fusion、45-channel PPG（44 waveform + point quality）、显式 `(B,2)` modality mask 与安全 modality dropout；PPG-only 仅为诊断。保持 BCE logits、train-only statistics、soft/ignore 标签和严格 IoU>0.25 event metrics。
- 紧凑 cache 是保守缺失模态，不从稀疏 PPG 猜测/外推数据；普通 reference 的既有 dense cache key 必须保持命中兼容。只有经 TDD、专项/全套测试、审查和原子提交后才能当作已验收实现。
- 不 destructive Git、不新建/嵌套 worktree、不合并、不 push、不启动 M2/M3/M4；保留现有未提交内容。

### Important Files

- `E:\bme_compitition\.worktrees\smartwatch-baseline\resume-prompt.txt`：可粘贴的新对话 prompt。
- `E:\bme_compitition\.worktrees\smartwatch-baseline\docs\superpowers\plans\2026-09-06-m1-execution-record.md`：已提交阶段和 bounded gate 的详细证据。
- `E:\Codex\Home\attachments\17106c1a-dc79-42bc-b3e9-33b5b804fb95\pasted-text-1.txt`：原始完整任务和验收门禁。
- `src/eating_detection/ppg_cache.py`、`dataset.py`、`training.py`、`cli.py`、`tests/test_m1_data.py`：当前未提交紧凑 cache TDD 的唯一工作面。
- `configs/m1_imu_ppg.yaml`、`configs/experiments/m1_ppg_only.yaml`、`configs/experiments/m1_fusion_no_dropout.yaml`：验证后应显式记录 `ppg_max_dense_samples`。

### Open Risks

- 必须证明 lazy compact cache hit 不会读 CSV、不会加载/分配全量 45×T 数组，并且 reference hash、window/label 与 M0 cache 仍严格匹配；仅有当前 single-item miss 测试还不够。
- compact files应只影响异常长 reference；普通缓存 key/hit 与既有 127-test 行为不能回归。若所有 train PPG 都 compact，standardizer 必须 fail closed 而不是悄悄拟合 placeholder zeros。
- 完整运行已在第一个超长文件处终止，修复后必须用原 full 命令恢复现有 `cache/m1_ppg` / `artifacts/m1_ppg_only_full_e3`，先取得真正完整 PPG-only，再运行 fusion；不要删除已生成 cache/artifact 以“重来”。

### Next Step

先只读检查 status/HEAD/diff，然后用项目解释器运行新增 compact 单测；从该 RED→GREEN 链条继续。补一个强制 lazy cache-hit（reader 抛错）和 batch 取数不分配 dense 全轴的回归，再执行 PPG cache/M1 data/训练相关测试、全套 pytest、compileall、diff 检查与 CUDA smoke，审查后原子提交。通过后，恢复下列完整 PPG-only 命令并监控 memory/cache 进度：

```powershell
$taskPython='C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe'
$dataRoot='E:\bme_compitition\official_test_dataset\Data'
& $taskPython -m eating_detection.cli train `
  --config configs/experiments/m1_ppg_only.yaml `
  --data-root $dataRoot `
  --index-dir (Join-Path $dataRoot '01_dataset') `
  --train-dir (Join-Path $dataRoot '02_traindataset') `
  --output-dir artifacts/m1_ppg_only_full_e3 `
  --split-manifest artifacts/final_m0/split_manifest.json `
  --epochs 3 --batch-size 64 --device cuda
```

预期交付物是：已提交、可恢复的紧凑 cache 修复；完整 PPG-only 的真实输出；随后 cache-hit fusion 完整输出与同 split M0/PPG-only/fusion 的明确比较。若发现具体矛盾，简述后采用最小安全假设继续，不重新开展广泛探索。

## 2026-09-06 M1 交接（当前权威状态）

本节覆盖下方所有“未授权 M1 / M1 尚未开始”的历史描述。用户已明确授权完整推进 M1；本次在用户要求交接后暂停，不代表 M1 完成。

### Objective

在现有隔离 worktree 完成 M1：独立 PPG cache、独立 IMU/PPG encoder 特征融合、从头联合训练、同 split 的 PPG-only 诊断及缺失模态验证。不要重新搜文献、重训 M0 或启动 M2/M3/M4。

### Current status

- worktree：`E:\bme_compitition\.worktrees\smartwatch-baseline`；分支 `codex/smartwatch-eating-baseline`。
- HEAD：`3d970f1`；本轮已提交 `d05665f feat: add isolated PPG-only chunk parser`、`47f2f41 fix: preserve explicit missing PPG stream semantics`、`d93f9e3 feat: add verified isolated PPG cache` 和 `3d970f1 feat: add robust M1 fusion model core`。起点是 `7c7d2ee`。
- 已完整读取旧 handoff、设计文档、实施计划和 README；已完成只读 preflight。
- PPG parser 已完成 TDD 和独立规格/质量审查：`iter_ppg_chunks` 只投影 PPG_TIME/PPG1–44；M0 原路径未改。行质量仍是正 timestamp、44 通道全 finite、非全零。缺列显式 invalid；缺整条 PPG 返回空无效流，由 cache 的参考时间轴补齐。
- 两个真实文件各 2,000 行：PPG 新旧时间戳/波形/mask 完全一致，有效行 450/435。
- **PPG cache 已完成独立规格/质量审查与阶段验收**：`src/eating_detection/ppg_cache.py` 与 `tests/test_ppg_cache.py` 保持独立 `ppg/` namespace，不改 IMU cache。新增回归固定“精确平坦流默认无效（显式 `keep` 可回退）”以及“无效输入经抗混叠影响的输出必须为零/无效”。专项 **27 passed**，全套 **110 passed**，compileall/diff check 成功；这不代表 full-data gate 通过。
- 两个真实文件各 2,000 行：在 soft/ignore 下 PPG 与 M0 25 Hz reference 的 timestamps、window index/boundary、labels 与 loss mask 完全相等；hnu21013/hnu21024 的 PPG quality coverage 分别为 0.65158/0.31050。cache miss 后将 PPG reader 置为抛错函数的 lazy hit 仍成功，证明确实未读 CSV。
- PPG cache 阶段已提交；不要丢弃或回退这些修改。
- **M1 模型核心已提交**：`IMUPPGFusion` 有独立 GroupNorm IMU/PPG encoder、45 channel PPG（含逐点 quality）、显式 `(B,2)` modality mask、训练期安全单模态 dropout、eval 确定性以及 strict M0 compatibility refusal。`train_m1_one_batch` 直接使用 `BCEWithLogitsLoss` logits。专项8 passed、全套118 passed，CUDA forward/backward 和 environment smoke 成功。
- **paired cache Dataset 与 PPG train-only 标准化已完成待阶段提交**：以 source、participant、全逐点 timestamps、window index/boundary、soft label 和 loss mask 强制逐文件匹配；即使两个 cache 是 lazy，也只读取 timestamps array 来验证 reference grid。窗口质量被显式派生为 IMU/PPG `(2,)` modality mask，PPG 缺失不丢弃窗口。44 个 PPG waveform channel 仅按训练 participant 的有效采样点拟合统计，缩放后无效点重新置零并原样保留 point quality。专项6 passed；全套124 passed。尚未接入 CLI 或执行 M1/PPG-only 训练。
- **cache-hit M1 batch training 已完成待阶段提交**：`fit_m1_cached` 只接受配对 cache，拒绝 train/val 之外的 cache participant 或任何 excluded test participant；它按 train participant 拟合 IMU/PPG 统计与 `pos_weight`，用参与者/文件分组 batch 做 BCE logits 训练、批量验证、严格 IoU decoder/事件指标、checkpoint 与概率输出。`ppg_only` 诊断仅将 IMU modality mask 置零；`fusion` 保持双分支。其输出记录两个 cache 的命中/CPU 时间、设备/GPU/epoch 时间、train/val modality coverage，以及验证窗口的二元/soft calibration（Brier/ECE/reliability bins）。专项2 passed、全套127 passed。
- **M1 CLI/config 已完成待阶段提交**：`model: m1_imu_ppg` 保持 M0 默认分支不变，并为每个成功 IMU cache 单独读取 reference timestamps 来构建独立 PPG cache；PPG build failure 单列报告，只有同 source 的 cache pair 会被传到训练。新增 `configs/m1_imu_ppg.yaml`（fusion）和 `configs/experiments/m1_ppg_only.yaml`（诊断）。端到端 CLI TDD 通过：2 个 toy participant 完成 PPG-only 训练、产出 PPG cache 和嵌套 IMU/PPG normalization；全套127 passed，并已完成真实 bounded PPG-only/fusion CUDA sample。
- **full-data gate 已通过，完整训练尚未启动**：真实受限样例（hnu21013 train/hnu21024 val、各30,000行、1 epoch）完成 PPG-only、fusion(dropout=.25) 与 fusion(dropout=0) CUDA，均为 cache hit；全套127 passed/compileall/diff check/CUDA smoke 通过；原始 2,378 项 size/mtime 在既有统一5小时记录偏移后零变化，raw零跟踪，cache/artifact忽略确认。将复用 `cache/m0_full` 的1121个 M0 IMU caches（metadata 参数与冻结P0完全一致），不会重建 IMU cache；PPG 独立写 `cache/m1_ppg`。

### Frozen decisions

- 原始数据只读、不得加入 Git；不 destructive git、不新建/嵌套 worktree、不合并、不 push。原始/cache/权重/输出忽略已验证。
- 使用 `artifacts/final_m0/split_manifest.json`；与 `artifacts/m0_final_q50_group_e3/split_manifest.json` 内容完全相同。train 34 participants/954 sensor txt，val 8/201，共 1155；excluded_test=ac3,test（仅清点文件名，0/2 txt）。完整 participant 列表见 manifest/执行记录，不重新划分。
- 现有 IMU cache 为 train 929 + val 192=1121 文件，3,578,835 windows、268,791,286 时间点；PPG 预计约51GB，交接前磁盘空闲约1.17TB。
- M1 使用独立 IMU/PPG encoder，embedding 级融合，从头联合训练。PPG-only 仅诊断；外部 PPG 饮食权重禁止；M0 迁移仅结构/state_dict 全兼容时可作单独消融，不静默加载。
- 固定 preprocessing/cache 与可学习 encoder、train-only 标准化统计分离。输入44 PPG波形+显式质量，modality mask 至少(B,2)，训练安全 modality dropout，缺模态不能仅靠普通零值。
- soft 返回实际 overlap ratio；ignore：0→0，低于训练阈值→None，达到→1。训练 label_positive_overlap 与评估 event_iou_threshold 不混用；participant 分组；test 不参与训练/阈值/decoder/模型选择。
- 事件 Precision/Recall/F1、严格 IoU>0.25、start/end MAE 为主报告；同时 calibration/coverage/participant 波动。
- CPU负责CSV/时间轴/重采样/cache；CUDA负责模型前向/反向/BCEWithLogitsLoss。训练和验证必须batch，不混淆CPU预处理与GPU时间。

### Important files and environment

- 原始完整任务：`E:\Codex\Home\attachments\17106c1a-dc79-42bc-b3e9-33b5b804fb95\pasted-text-1.txt`，新对话必须读取，含逐阶段完整测试与验收要求。
- 执行记录：`E:\bme_compitition\.worktrees\smartwatch-baseline\docs\superpowers\plans\2026-09-06-m1-execution-record.md`。
- 设计：同 worktree 的 `docs/superpowers/specs/2026-08-31-smartwatch-eating-detection-baseline-design.md`；原计划：`docs/superpowers/plans/2026-09-01-smartwatch-eating-detection-implementation-plan.md`。
- 项目解释器：`C:\Users\Fancy\anaconda3\envs\smartwatch-eating\python.exe`，Python3.11.16，PyTorch2.11.0+cu128/CUDA12.8，RTX5060Laptop。默认 PATH 的 Python 是系统3.10，不要用错。`scripts/verify_environment.py --require-cuda --steps 2` 已通过。
- M0最终artifact：`artifacts/m0_final_q50_group_e3/`。只读复评与原指标相等：TP/FP/FN=21/171/30，P=.109375，R=.4117647058823529，F1=.17283950617283952，start/end MAE=639946.0238095239/71945.45238095238ms；q50/GroupNorm/avg/batch64，pos_weight=15.411571805503204。不重训。
- 忽略的 preflight证据：`artifacts/m1_preflight/summary.json`、`imu_cache_inventory.json`、`source_metadata_before.json`（2378个原始文件size/mtime基线，最终用来复核未改数据）。

### Open risks / immediate next steps

1. PPG cache 阶段已完成：现 API 为 `PPGCacheConfig` 与 `build_ppg_cache(source_path, intervals, cache_root, config, reference_timestamps_ms=None, lazy=False)`；45×T float32 feature、1×T bool quality、连续 array+window index、reference grid hash、lazy/atomic/recovery 均已验收。默认 `reject_constant_stream`，显式 `keep` 仅供回退；无效重复包也会通过抗混叠质量支持传播为输出屏障。
2. full-data gate 已通过。下一步严格顺序启动完整 PPG-only→复用冻结 M0 reference→完整 fusion；PPG cache 单独逐文件恢复，M0 IMU cache 只读命中。随后报告 fusion/PPG-only/M0/dropout 的可比指标与缺失模态结果。
3. 全量 M1 必须等原附件所有 full-data gate 通过。最终全套 pytest/compileall/diff/Git/忽略/CUDA/缓存 hit/样例复现，更新 README/handoff/原实施计划，原子提交。finishing-a-development-branch 仅报告集成选项，默认保留分支/worktree。

每阶段用中文“事实→风险→候选→验收标准→选择→实验结果”；每个实现阶段RED→GREEN→阶段验证→原子提交。使用 executing-plans、using-git-worktrees、test-driven-development、systematic-debugging、verification-before-completion；需要子代理时遵循已加载的subagent-driven-development。库API用Context7先resolve再query；本轮已查pandas `/websites/pandas_pydata`、PyTorch `/pytorch/pytorch/v2.11.0`，SciPy查到内容较浅，主要复用现有resample_uniform。

## 2026-09-03 权威更新

更新时间：2026-09-03T13:48:19-04:00（America/New_York）。本节覆盖下方早期历史状态；设计文档和实施计划中的冻结时间戳仍为 2026-09-01T09:51:58-04:00。

- 当前实现位于隔离 worktree：`E:\bme_compitition\.worktrees\smartwatch-baseline`。
- 当前分支为 `codex/smartwatch-eating-baseline`；本轮最新代码提交为 `1f2088a fix: keep local pooling deterministic`（文档提交后 HEAD 会更新）。不要直接在 `master` 上实现，不要合并或 push，除非用户另行明确授权。
- 环境、数据审计、时间轴恢复、标签、participant split、M0、事件评估、消融、缓存流水线、full M0 复现检查以及 quality/calibration/participant error analysis 已完成；当前全套测试为 `72 passed`，文档提交后的最终验证需再次确认。
- RTX 5060 CUDA 已验证可用；full M0 实际使用 `device=cuda`。全量 train/val 枚举 1,155 个 sensor 文件，1,121 个有效 cache 完成 20 epoch；34 个不可解析文件保存在 `input_issues.json`，未修改原始数据。
- M0 当前采用 q50 质量分层 + GroupNorm + 筛选后 `pos_weight` + batch cache fetch；`artifacts/m0_final_q50_group_e3/` 的 full-data 3 epoch F1=`0.1728395`，独立 evaluate 一致，原始 P0 F1=`0.0387324`。M1 使用独立 IMU/PPG encoder 的特征级融合，仍需用户明确授权后按冻结 gate 启动；M0 默认不读取 PPG。
- PPG 冻结契约：固定预处理和 PPG cache 不等于 PPG 模型；M1 使用独立 IMU/PPG encoder 做特征级融合并在本竞赛事件标签上联合训练；PPG-only 只做诊断对照；M1 默认从头联合训练；M0 权重仅在结构兼容时作为迁移消融；不直接使用外部 PPG 饮食任务权重；无效 PPG 必须配合 quality/modality mask 和 modality dropout。
- 93 GB 的 CSV 解析、时间轴恢复、插值、重采样和 cache 构建属于 CPU；M0/M1 的 PyTorch batch 前向、反向和损失计算在 CUDA 可用时使用 RTX 5060。缓存命中后训练不得重复扫描原始 CSV。

### 2026-09-03 M0 瓶颈修复结果

- 质量/校准/participant error analysis 已用于选择 q50：full cache-hit 训练窗口为 1,306,197，验证窗口为 271,724，有效 `pos_weight=15.4116`；Brier=`0.157069`、ECE=`0.321964`。
- 当前最终候选：`device=cuda`、batch 64、GroupNorm、默认 avg pooling、q50 quality gate；Precision=`0.109375`、Recall=`0.411765`、F1=`0.1728395`、start/end MAE=`639946/71945 ms`，TP/FP/FN=`21/171/30`。
- P1、P2、ignore-boundary、avg4 均为 F1=`0.1728395`；avg+max 为 `0.1504178`；不采纳。当前仍有 171 个 FP，且 `hnu21042` 因无有效 cache 有 6 个不可预测 FN；M0 的低 F1 已显著改善但不是零错误。
- 训练读取已增加 deterministic participant/per-file batch shuffle、batched continuous-array fetch；full cache-hit 不读取原始 CSV。P1 派生 cache 和 ignore-label cache 均在 Git 忽略目录，未修改原始数据。
- M1、PPG-only 和任何外部 PPG 权重仍未启动；默认保留当前 M0 分支/worktree，不合并、不 push。

### 2026-09-01 本轮吞吐续作状态

- 已完成两个代表文件的有界基准，并定位到高重复 timestamp 聚合的逐组布尔筛选和 M0 不必要的 PPG 全列物化；现已改为向量化聚合和明确的 `include_ppg=False` IMU-only 路径。
- 已实现带源文件 metadata/config/标签指纹的 per-file feature cache：保存统一时间轴、连续 feature array、quality mask、window index、窗口边界和 label；临时文件成功后原子改名，按文件构建可中断恢复。
- CLI 的 M0 训练现统一从 cache-backed DataLoader batch 读取；cache hit 不读取原始 CSV，CUDA 时使用 pinned memory/non-blocking transfer，验证使用批量 inference，并记录 device、batch size、GPU memory/utilization 和 epoch 时间。
- 本轮验证：全套测试从 46 增至 61 项并通过；两个真实文件的 cache miss/hit、断点恢复、lazy cache 内存边界、重复表头兼容和 bounded/full RTX 5060 CUDA sample 均通过。sample 指标不替代 full-data 指标。
- full M0 结果：1,121 个有效 cache、3,578,835 个窗口、20 epochs、batch 64；验证集 F1=`0.0387324`、Precision=`0.0199637`、Recall=`0.647059`，start/end MAE=`289466/391033 ms`。独立 evaluate 保持训练元数据并输出相同事件指标。M1 仍未启动。
- M0 诊断报告：`artifacts/final_m0/run/error_analysis.json` 由现有 cache 和冻结验证概率生成，不读取原始 CSV；包含 quality 分层、binary/soft 校准、decoder 阈值穷举和 participant 级错误。主要结论是验证概率正负分离失败、低质量窗口显著放大 FP，`hnu21042` 无有效 cache 导致 6 个不可预测 FN；暂不启动新的 IMU 消融或 M1，等待用户决策。

下方较早的 Current Status、Important Files、Known Data Facts 和 Immediate Next Steps 保留为历史接续材料；其中关于“尚未配置环境/尚未写训练代码”、旧提交号和旧文件数量的描述不再代表当前状态。

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
