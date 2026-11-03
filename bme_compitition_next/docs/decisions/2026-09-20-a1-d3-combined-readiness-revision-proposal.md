# A1 D3 身份、边界与标签口径：联合就绪修订提案

> **批准附记：** 用户于2026-09-20明确回复“批准修订，同时给我用review的skill重新审查一下当前计划有无其他漏洞”。因此本文 `D3-Ready-v1` 的R1–R4已批准；下文PROPOSED/NOT_APPROVED为批准前快照。批准前文件SHA-256：`82c844fdb099102ab3d3dee3a29749cc0ba6252684b6532dcc0755b7b815f39b`。实现和完整就绪核验尚未完成，A1仍NOT_READY。追加审查见[计划与实现复核](2026-09-20-a1-plan-implementation-review.md)；不得重复请求本次R1–R4批准。

日期：2026-09-20。状态：`PROPOSED / NOT_APPROVED / A1_NOT_READY`。

用户本轮“可以”授权边界复核及完整修订提案的形成；不解释为批准尚未形成的协议改动。本轮完成只读缓存审计和确定性标签复核，没有应用修订、执行 fit/predict 或重跑 A1 run。

## 1. 结论与文档层级

仅批准 [D3-Identity-v1](2026-09-20-a1-d3-identity-audit-and-revision-proposal.md) 不足以恢复运行。本提案将三个需要明确决定的事项一次呈现：身份来源、窗口支持边界，以及本次新发现的训练标签口径差异。它不是再次请求 A1 或 D1–D5 整体批准。

建议采用下文 `D3-Ready-v1` 联合修订，先实现和测试，再通过完整不拟合审计。即使联合修订获批，也不等于代码正确、所有就绪门禁通过或模型性能达标。

现行 [A1 授权](2026-09-20-a1-end-to-end-feasibility-authorization.md) 要求 session bounds 严格包含所有窗口；现行 A1 loader 因此停止是正确行为。本提案若获批，会明确替换这项要求，绝非宣布旧要求已满足。09-14 设计对同 session/segment 融合与边界裁剪的要求也须按本提案明确限定为新的开发协议；历史运行和原正式门禁不重写。

## 2. 新审计证据

复现脚本：[audit_a1_boundary_contract.py](../../scripts/audit_a1_boundary_contract.py)。输出：[boundary-audit.json](../../artifacts/a1-d3-boundary-contract-audit-v1/boundary-audit.json)、[hash](../../artifacts/a1-d3-boundary-contract-audit-v1/boundary-audit.sha256)、[标签独立交叉核验](../../artifacts/a1-d3-boundary-contract-audit-v1/label-crosscheck.json)。脚本拒绝覆盖已有审计输出；本次输入文件和脚本 hashes 已写入报告。

本审计读取批准的 cache manifest/audit/eligibility、1127 个 NPZ 和源码；每个 NPZ 都核验实际 SHA-256 与声明一致。raw 路径仅作为 manifest 关联字符串，不 stat/open，不访问 official test 或 external data。只载入身份、时间、标签与质量数组，不载入模型，不执行拟合或预测。

| 检查 | 结果 |
|---|---:|
| records / participants / windows | 1127 / 41 / 632100 |
| 存在 index-bound 越界的 records | 939 |
| 实际越界窗口 | 965（约0.152666%） |
| start 早于 index start 的窗口 | 953 |
| end 晚于 index end 的窗口 | 12 |
| 最大 start underflow / end overflow | 9837ms / 880ms |
| 越界窗口旧标签 positive / negative / ignore | 64 / 892 / 9 |
| 越界窗口与 training-eligible GT 相交 | 65 个窗口，涉及60个唯一GT |
| 越界窗口距 training-eligible GT 小于300s | 75 |
| crosses_gap=true / coverage<0.8 / invalid_run>20 | 0 / 0 / 0 |
| 按历史 session GT 筛选规则重算与缓存标签差异 | 0 / 632100 |
| 按 participant 全部 training-eligible GT 重算与缓存差异 | 196 / 632100 |
| 差异类型 | 全部 negative(0) → ignore(-1) |
| 差异影响 records / participants | 11 / 8 |
| 差异窗口中越界 / 不越界 | 2 / 194 |

6C7 有6个records、3443个窗口，其中3个records各有1个越界窗口，均为negative；两种GT口径的标签差异为0。不能将整个缺口归因于6C7，也不能通过删除6C7解决。

独立 vectorized 重算采用 intersection/window-duration≥0.5 判正、最近GT距离≥300000ms判负，否则ignore；它完整复现632100个历史标签。随后用现有纯函数 `label_window` 对全部越界或标签差异窗口的并集1159行交叉验证，结果一致。该检查是标签计算验证，不是模型实验，也不是完整 pipeline 测试通过。

## 3. 来源语义与未解决的物理原因

已查代码链：

1. `data/manifest.py::discover_raw_files_with_audit` 从历史 `index.csv` 的 startTime/endTime 赋值 audit session bounds。
2. `data/raw.py::regularize_imu` 用 ACC/GYRO 时间戳的首末值建立网格；`_build_table` 没有传入 index bounds 用于裁剪该网格。
3. `data/windows.py::generate_dense_windows` 从网格生成15s窗口，end=start+15000ms；按 coverage、invalid run 和 gap/segment 检查窗口质量。
4. `data/manifest.py::events_for_record` 仅保留与 index interval 相交的 GT，不裁剪GT本身。
5. `regenerate_label_cache.py` 沿用旧几何/特征，并使用该 session-filtered GT 重建标签。当前完整重算一致支持这一标签生成链解释。

因此，index bounds 与缓存窗口支持不是同一来源。它们在历史实现中分别影响 GT 选择和采样几何。09-14 设计写“negative：距所有真实事件至少300s”，现行实现实际是“距经session筛选后留下的事件至少300s”；196行差异证明此处有实质区别。不能再将 index bounds 简称为“纯描述信息”而忽略它对历史标签的作用。

仍缺失：没有重新读取 raw 证明时钟差异的物理成因、index end 的精确端点约定或原始完整连续segment。缓存hash保证字节身份，质量字段与现有生成代码提供项目内来源证据，但不构成重新审计raw的独立证明。偏差小不能证明它合理；本提案不增加10s容差，不把观察到的最大偏差变成通用合法阈值。

## 4. 建议批准的 D3-Ready-v1

### R1：身份来源

采用此前 D3-Identity-v1 的一对一 cache entry/hash → manifest audit 关联和 sidecar 要求。空 NPZ session字段只是缺失，派生 session 保存来源，非空冲突仍停止。旧NPZ不回写。`record_id` 使用核验过的cache stem，原participant/folds不变。

### R2：有限开发协议的有效支持范围

仅对本次冻结输入 hashes 所标识的1127个缓存，采用 `approved_cached_window_support_v1`：保留全部632100个历史合格窗口，在每个确定性 record/session 内用全部窗口覆盖并集形成连续component。候选生成与融合只能位于同record/session/component内，不能跨空白支持区间。

index_start/end 单独保留为历史元数据并报告偏差，不再作为拒绝已批准窗口的硬包含条件；不得将支持区间冒充真实source segment或完整监测时间。保留 `source_segment_id=null` 与 `boundary_kind=observed_window_support_component_v1`。这明确接受项目内缓存来源作为本次开发研究的边界证据，不声称raw边界已核验。

不裁剪、不删除965个窗口，不移动时间、不改变特征或cohort。窗口质量、时间单调/正duration、hash、记录身份和数组对齐仍为硬检查；未来新增缓存或输入hash变化不能自动套用此例外。若发现身份冲突或质量异常，停止，不以新边界规则覆盖。

### R3：显式的训练标签修订

建议建立 `participant_training_truth_labels_v1`：对每个窗口，使用其participant在冻结ledger中全部 `training_eligibility=true` 的canonical GT，按现有0.5 overlap/300s距离规则计算训练标签，不先按 index interval 筛掉GT。

这是超出纯身份映射的明确数据语义修订，必须连同R1/R2审阅，不能偷偷算作loader修复。当前具体影响为196行0→-1：positive总数35948不变，negative由583145变为582949，ignore由13007变为13203，总窗口数仍为632100。保存逐行 old/new label、stable ID、依据与sidecar hash；历史NPZ及结果不改写。

训练loss使用新的0/1标签；q reference仍包含同一fit participants全部合格rows（含IGNORE），所以reference行人口不改变，但重新拟合模型后reference数值可能改变。只允许训练侧GT参与该训练侧标签；验证预测生成/过滤不读取验证GT。全量审计已接触开发标签这一事实保留，不把此过程称为独立确认。

模型复用必须重新判断：任何训练行标签或loss行集合受影响的旧模型不可作为新signature直接复用；即使不受影响也仍须通过原完整provenance核验。不得承诺仍能复用25个模型或只新增80 fits；总105 candidate/25 verifier attempts预算不增加。评估GT仍为234，candidate/event标签仍按participant canonical GT的已批准规则。

### R4：实现与就绪门禁

批准后的实施范围限 A1 loader/contracts/config、对应测试、新sidecars及新run provenance，不改旧cache/runner。需一次完成R1–R3，再审计；不先只补session并重跑一个已知会失败的run。

必须增加以下反例验证：重复manifest key不得字典覆盖；非空session冲突失败；record间时间相接不能融合；index外但在已批准support内窗口按新契约接受；空白support不桥接；GT变化不能改变验证预测生成；196行标签差异逐一可解释；改变训练标签必须改变fit signature；只有同一冻结输入身份才适用边界例外。

数据侧审计要求：1127/41/632100/234计数一致，身份映射完整，原数组hash不变，965越界窗口记录完整，196标签差异与sidecar一致，质量字段硬检查通过，角色图隔离/复用/资源就绪核验全部通过。任何额外差异停止调查，不更新预期值掩盖问题。

完整不拟合audit通过后，才按原A1授权进入有限run。新run继承已有研究预算消耗，不更换run ID清零。此次复核是未运行模型的设计审计，耗时/产物应记录并在后续研究总投入核算中明确列出，不能声称成本为零。

## 5. 替代方案与投入判断

- 仅批准身份：不足以解除已知边界阻断，不建议作为下一次运行尝试。
- 丢弃越界窗口或participant：会删除正窗口、改变参考分布与背景范围，不推荐。
- 全局增加时间容差：缺乏物理依据，也不解决194个不越界窗口的标签口径差异，不推荐。
- 坚持index硬边界：需要另行设计几何/特征/标签处理和来源重建，不能直接裁剪时间后保留旧特征；成本更高，不在本提案实施范围。
- 坚持必须独立证明raw边界：需另行授权最小target-train raw/index来源核验。在现有“只读缓存、不读raw”范围内无法给出该证明；不能伪造为已完成。

推荐R1–R4是对有限开发研究明确接受何种证据的选择，不是保证端到端可行。它解决目前已知的三个数据契约问题；完整audit仍可能发现其他失败，不能预先宣称READY。

## 6. 证据分类、当前状态和待决定内容

A 文档事实：原G1停止、A1已批准、严格index包含是现行D3要求。B 当前代码行为：上述不同边界来源及session-filtered训练GT；A1 loader仍按旧条件失败。C 历史实验：无变化。D 缺失证据：raw物理边界、修订实现正确性、全部就绪条件、新性能与独立confirmation。E 推断/建议：以冻结cache支持范围加明确标签口径修订，比删数据或无依据容差更适合本次有限开发研究。

待决定：是否整体批准 `D3-Ready-v1（R1身份 + R2缓存支持边界 + R3训练标签 + R4验证要求）`。在批准前不应用、不fit/predict。旧身份提案继续作为审计背景，其“仅等待Identity批准”不再表示完整就绪路径。

```text
A1_D3_COMBINED_REVISION = PROPOSED_NOT_APPROVED
A1_EXECUTION_READINESS = NOT_READY
LOCAL_G1_EXPERIMENTATION = STOPPED
PROPOSAL_INTERFACE_EFFECT = SUPPORTED_ON_DEVELOPMENT_FOLDS
FROZEN_PROPOSAL_RULE_AS_G1_REMEDY = UNSUPPORTED
FORMAL_G1 = FAIL
FULL_TRAINING = BLOCKED
PRODUCTION = UNCHANGED
```
