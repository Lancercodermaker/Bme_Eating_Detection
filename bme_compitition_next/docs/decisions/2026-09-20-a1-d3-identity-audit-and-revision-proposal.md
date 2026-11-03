# A1 D3 身份来源全量审计与修订提案

> 后续边界复核已完成，见[联合就绪修订提案](2026-09-20-a1-d3-combined-readiness-revision-proposal.md)。本文件保留身份专项审计；其“仅等待身份批准”不表示A1可以立即运行。新的边界及训练标签口径差异须按联合提案一并处理，目前仍为NOT_READY。

状态：`PROPOSED / NOT_APPROVED`。本文件只处理 A1 D3 的缓存身份来源例外，不改变 A1 或 D1–D5 的总体批准，也不恢复旧 M5/G4/M6、full training 或 production。

## 1. 审计范围与方法

审计只读取已批准的缓存、cache manifest、manifest audit、cache provenance、checksums、eligibility 和仓库代码；manifest 中的 raw sensor 路径只作为不透明字符串键使用，没有对其执行 `stat`、存在性检查或打开。没有读取官方 test、external data，也没有执行 fit/predict。

输入范围：

- `cache-manifest.json`：1127 entries；`manifest-audit.json`：1163 records，其中 processed 为 1127。
- `g1-formal-cache-v3-final`：1127 个 NPZ，全部被 manifest 引用。
- 41 participants、234 canonical eligible GT；6C7 保留在 participants 中，作为背景 FP 来源。
- cache 总窗口数：632100。

逐 entry 检查了文件存在性、声明/实际 SHA-256、NPZ schema、数组长度、participant/session 字段、metadata、缓存 basename/stem、manifest audit 关联和窗口边界。所有 v4 coverage checksums 均与文件实际 SHA-256 相符。

## 2. 审计事实与根因

### 2.1 实际身份缺失

| 检查 | 结果 |
|---|---:|
| cache 文件存在且被引用 | 1127 / 1127 |
| cache 声明 hash 与实际 hash 相符 | 1127 / 1127 |
| NPZ 缺少必需数组 | 0 |
| NPZ participant 数组完全匹配 manifest participant | 1127 / 1127 |
| NPZ `session_ids` 全行为空字符串 | 1127 / 1127 |
| 空 `session_ids` 行数 | 632100 / 632100 |
| 含任意非空 `session_ids` 的 entry | 0 |
| NPZ metadata 含可识别 session/record 字段 | 0 |

根因是现有序列化链路：`build_candidate_table` 没有向 `CandidateTable.session_ids` 写入 session，`save_candidate_table` 在该字段为 `None` 时按设计写入空字符串；coverage runner 另行把 `record.session_folder` 写入 cache manifest。因此，空数组是历史缓存 serialization omission，不是一个可从 NPZ 内容自行恢复的 source segment identity。

### 2.2 可用的非 raw 唯一关联

| 候选关联来源 | 覆盖 | 碰撞/歧义 | 结论 |
|---|---:|---:|---|
| manifest entry 的 `cache_path` | 1127 / 1127 | 0 | 可用，但必须连同 hash 和 manifest identity 验证 |
| cache basename/stem | 1127 / 1127 | 0 | 可作 record key；不单独宣称 session 来源 |
| manifest `cache_sha256`，且与实际 hash 比对 | 1127 / 1127 | 0 | 可作强完整性键 |
| NPZ metadata `cache_key` = basename stem | 1127 / 1127 | 0 | 可交叉核验 record key |
| cache entry `path` → manifest audit | 1127 / 1127 | 0 | 每个 path 恰好一个 processed audit record，participant/session 一致 |
| participant + manifest session | 1127 / 1127 | 0 | manifest 内唯一 |
| NPZ `source_fingerprint` | 1127 / 1127 非重复 | 无 | 仅为 opaque hash；manifest audit 没有同一字段，不能单独推出 session |
| participant + 窗口时间范围 → audit bounds | 188 / 1127 | 939 无候选，0 歧义 | 不能作为恢复来源 |

缓存文件、basename/stem、声明 hash、实际 hash、metadata cache key、manifest path、participant+session 均为 1127 个不同值/组合；没有未引用 NPZ。当前数据支持的结论是：**通过批准 cache manifest 与 manifest audit 的一对一 entry 关联，可以确定性地派生 record/session identity；不能把 NPZ 的空 `session_ids` 当成证据，也不能只靠窗口时间推断 identity。**

### 2.3 边界审计的独立缺口

这不是本提案用来放宽的条件，但必须记录：按现有 D3 的“所有窗口必须落在 manifest session bounds 内”原文检查，只有 188 / 1127 entries 全部窗口在边界内；930 entries 的最早窗口早于 audit start，12 entries 的最晚窗口晚于 audit end，其中 3 entries 两者同时发生。最大 start-underflow 为 9837 ms，最大 end-overflow 为 880 ms。

因此，identity mapping 可行不等于 A1 已 ready。时间边界缺口仍按现有 D3 fail-closed，不能由本身份修订静默放宽、裁剪或丢弃窗口；它是后续就绪审计的独立证据缺口。

## 3. 建议的 D3 修订（仅身份来源例外）

在获得单独的 D3 修订批准前，以下文字只是提案，当前状态保持 `NOT_READY`。

### D3-Identity-v1：批准缓存 entry 的确定性身份派生

1. 定义 `cache_record_identity_v1`：对每个 approved cache entry，以 `(cache_path, declared_cache_sha256)` 定位唯一 cache 文件；以该 entry 中的 `participant_id`、`session_id`、opaque `path` 关联 `manifest-audit` 中恰好一个 `status=processed` 记录。要求 participant、session、audit path 一致。
2. `record_id` 使用已校验 cache basename/stem；`session_id` 和 participant 使用 manifest/audit 的值。显式保存：
   - `session_identity_source = approved_cache_manifest_v1`
   - `session_identity_derivation = one_to_one_cache_entry`
   - `source_segment_id = null`
   - `boundary_kind = observed_window_support_component_v1`
3. NPZ 内空的 `session_ids` 视为“字段缺失”，不得原地回写、不得用空字符串作为身份、不得声称 NPZ 自带 session identity。派生身份只存在于本次 A1 输入审计/运行的只读 sidecar 或内存对象中。
4. 通过以下 fail-closed 条件后才允许把派生身份提供给 D3 support-component 逻辑：
   - 1127 entries 的 cache 文件存在、hash 全部相符、均位于 approved cache root；
   - cache path、basename/stem、metadata cache key 和实际文件之间无重复/冲突；
   - 每个 cache entry 对应恰好一个 manifest audit path，且 audit status 为 processed；
   - participant/session 对应关系一对一，NPZ participant 数组全行一致；
   - 每个 `(participant, record_id, session_id, row_index)` stable window identity 唯一；
   - 原有 `crosses_hard_gap=false`、质量字段、session bounds 和空 record 规则继续执行；任一失败均停止，不静默丢弃、裁剪或改写身份。
5. D3 的语义不变：只在同一 record/session 的 `observed_window_support_component_v1` 内生成和融合，`source_segment_id` 保持 `null`；该修订不把 cache entry、窗口覆盖组件或 manifest session 冒充原始 source segment。
6. 实现获批后，先生成 `cache-record-identity-audit.json`，包含逐 entry 的 cache path/hash、record stem、participant/session、audit row identity、映射来源和校验结果，并把该 sidecar hash 纳入 A1 provenance。未生成并核验该 sidecar 前不得进入真实 A1 run。

## 4. 不在本修订范围内的事项

- 不重写历史 NPZ、历史 runner、历史模型、历史实验产物或旧决定。
- 不读取 raw 以恢复 source segment，不使用 official test/external data。
- 不放宽当前发现的 939 条 session-bound 越界，不按时间猜测 session，不重试或扩展参数空间。
- 不启动 union、full training、production，也不执行 A1 fit/predict。
- 不改变以下冻结状态：

```text
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```

## 5. 决定请求与当前判定

本审计支持“唯一 manifest association 可作为身份来源”的**条件性可行**结论，但不支持直接修补空 `session_ids` 或仅靠时间边界恢复。当前 A1 仍为 `NOT_READY`：身份修订尚未批准，且 session-bound 独立缺口仍未满足现行 D3 门禁。

后续只需对本文件第 3 节的 D3-Identity-v1 作出批准/拒绝决定；不需要重新讨论 A1 或 D1–D5 的整体批准。
