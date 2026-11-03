# 新对话 Prompt：路线三终态收口与证据包

适用范围：只读整理已经完成的 v1-003，供返回主对话整合路线1/2/3。它不授权新的 Route 3 实验。以下内容可直接复制到新对话：

```text
进入路线三已完成后的终态证据收口，整理结果后由我带回主对话，最后整合路线1/2/3并开启下一轮架构讨论。

工作树：
E:/bme_compitition/.worktrees/high-f1-event-stack-execution/bme_compitition_next

所有读取和命令必须使用上述精确workdir，不使用环境默认cwd。把登记相对路径先解析为工作树内绝对路径；PowerShell读取用-LiteralPath。禁止根目录/父目录搜索、通配符枚举或目录遍历。精确文件不存在时报告该路径，不扩大搜索。config sidecar的精确路径是configs/route3-matching-aware-v1-003.sha256，不是.json.sha256。

先完整阅读：
docs/handoffs/2026-09-27-route3-complete-closeout-handoff.md
以及该交接列出的六份必读文档。过长文档分段读取，不只看摘要。交接用于状态导航；事实如与登记产物矛盾，说明矛盾并停止依赖该项，不猜测、不修复、不重跑。

当前事实：
- v1-003已经合法COMPLETE，科学状态CLOSED_STAGE_MINIMUM_FAIL。它不是待执行实验。
- 保存TP/FP/FN=150/126/84，F1=0.5882352941；四项numeric/stage门均FAIL，long FP=89/126。
- 一次audit、一次run；candidate fit/predict=0/0，verifier fits/scores=25/25，decodes=60+5，outer evaluations=5；资源无失败。
- v1-001真实fits=0，v1-002真实fits=25且仍INVALID，v1-003真实fits=25，Route3累计50。不能追认002临时指标或说其未拟合。
- 路线1是官方合约资料审查；路线2仍NOT_EXPERIMENT_AUTHORIZED。不能把三条路线说成均完成了模型实验。

本轮仅授权只读核验和在回复中整理证据：
1. 用交接中精确登记的config、status、READY、预检、target audit、metrics、manifest、fit/score ledger、resource和外部budget ledger核对绑定与实际记录。核对25个唯一有序role的candidate_count、正类计数及键/矩阵/标签摘要；不复制expected值冒充actual。
2. 可按final-checksums.json的精确条目只读重哈希63个登记产物和外部账本；先检查条目解析后仍在指定目录范围内。model pickle只重哈希，不反序列化、不执行。禁止目录遍历扩读。
3. 引用保存的pooled与五折指标，不运行matcher/evaluator、重新匹配、重新解码或重算实验指标。区分工程COMPLETE、四门FAIL与路线关闭。
4. 明确你实际核对的范围及未核对部分；独立工程审阅不是独立参与者或官方测试确认。
5. 在最终回复提供可复制回主对话的路线三证据包，包含来源文件、状态/指标/调用/资源/累计消耗、审阅结论、限制以及仍会改变架构路线的证据缺口。不要在本对话启动整合后的新实验。

严禁：
- 不执行设计/执行清单里的历史命令；不重跑v1-003，不自动创建v1-004或A2-005。
- 不训练、predict/predict_proba、生成标签或候选、重新解码、audit/run、新实验或测试。
- 不修改代码、配置、文档、历史产物或production，不清理输出。本轮不写文件。
- 不读取、遍历、stat或重哈希raw sensor、原metadata CSV、official test或external data，尤其E:/bme_compitition/official_test_dataset。manifest路径不是扩大输入权限；不重读官方/队友PDF或远程仓库，不加载训练缓存或传感器支持。

保持：全部41人已有开发暴露，没有独立participant确认；58段原A2零注释交叠长FP行为仍UNKNOWN。A1 CLOSED，A2固定26D CLOSED_STAGE_MINIMUM_FAIL，Formal G1 FAIL，full training BLOCKED，production UNCHANGED。不能假定无限未来上下文或声称官方精确matcher/API已确认；该固定目标变体失败不否定HGB家族。

完成后停止，等我把证据包带回主对话。若我想研究新的Route3变体，应在整合讨论后另行明确新机制、输入/标签、执行设计、预算与授权；不能继承已耗尽的003授权。
```
