# B 工程收口范围与最终门禁条件

本台账汇总 [#185](https://github.com/MeteoBoy4/PaperRadar/issues/185) 的独立 D1 工程覆盖，
`stage_a_verified=false`。不新增验收组，不扩张 A1–A10 的 required 集合、回执或固定分母。
工程测试、所有者真实链签收与现场隔离恢复分别保留，任何一项不替代其余项。

## 结论生效条件

本文件是最终待验候选的工程范围说明，不是完整离线门禁通过记录。
工程结论只在独立审阅／修复、最终树 scope 敏感确认与白名单重绑完成后，
对最终冻结 SHA 实际执行完整 `./scripts/check-offline` 返回 **0**，并查询**同一 run**
得到 **passed / verified / same** 时生效。完整门禁须所有者明确要求，由唯一执行者运行。
HEAD、merge commit 或任意身份约束材料变化后重新取得最终树结论。
最终 run_id 与具体树身份留树外交付报告，不预填本台账或回写既有证据。
路线图中的 B 完成项按此条件生效；工程候选和定向测试均不授权提前关闭 #206／#185。

## 工程范围与方法

- 显式实验根与实际 `data/` 布局：JGR Feed v2、完整主摘要／语言与冻结候选、选样接受授权、外发范围、只读预检和无 prompt 映射探测。
- 显式两阶段 Screening、失败查询／reclaim／retry／继续、代执行 accepted、PDF 确认、受限提取、正文显式选择、六项核查、单篇 Read 与恢复。
- 固定 report run/entry、最小日报／单篇、暴露并集导出、标准备份与隔离脱网回放；报告原字节、历史依据、evidence 和预算独立核验。
- CLI 为主要接缝；公开服务 API 仅作故障／并发注入，恢复用真实产品子进程。HTTP transport、Pi 合成 RPC、Docling parser／SDK、PDF renderer 和注入 clock 为外部替身边界；不替换内部准入成功、领取、预算或接收权威。
- 全部材料在本票独占 `/tmp` 合成根；不执行真实／live 命令，不访问真实实验根、运行 checkout、研究数据或凭据，不下载模型。
- 本票不新增 Alembic migration、表、Schema 字段、业务 Prompt 或 Stage fingerprint 语义；已接受 ADR 正文与既有逐票工程台账保持冻结。

## 独立 D1 当前收集并集

以下按**最终模块的实际 pytest collect**列数量，参数化按完整 node ID 去重；
不是各票历史运行数相加，也不表示这些节点已在本票单条命令中全部执行。
独立新增模块不进入历史组，测试支撑／恢复 worker 不另计节点。

| 独立模块 | 当前节点数 |
| --- | ---: |
| `tests/test_body_selection_cli.py` | 3 |
| `tests/test_body_selection_facts.py` | 11 |
| `tests/test_body_selection_integrity.py` | 2 |
| `tests/test_body_selection_migrations.py` | 4 |
| `tests/test_body_selection_read.py` | 1 |
| `tests/test_body_selection_recovery.py` | 1 |
| `tests/test_experiment_accept_cli.py` | 27 |
| `tests/test_experiment_accept_migrations.py` | 6 |
| `tests/test_experiment_candidates_cli.py` | 18 |
| `tests/test_experiment_exposure_cli.py` | 2 |
| `tests/test_experiment_exposure_entry.py` | 5 |
| `tests/test_experiment_exposure_faults.py` | 14 |
| `tests/test_experiment_exposure_history.py` | 4 |
| `tests/test_experiment_exposure_identity.py` | 9 |
| `tests/test_experiment_exposure_migrations.py` | 4 |
| `tests/test_experiment_exposure_recovery.py` | 1 |
| `tests/test_experiment_extract_cli.py` | 35 |
| `tests/test_experiment_extract_migrations.py` | 5 |
| `tests/test_experiment_feed_cli.py` | 21 |
| `tests/test_experiment_layout_cli.py` | 35 |
| `tests/test_experiment_layout_migrations.py` | 6 |
| `tests/test_experiment_pdf_cli.py` | 30 |
| `tests/test_experiment_pdf_migrations.py` | 6 |
| `tests/test_experiment_read_cli.py` | 24 |
| `tests/test_experiment_read_logging.py` | 3 |
| `tests/test_experiment_read_owner_basis.py` | 1 |
| `tests/test_experiment_read_retry_cli.py` | 9 |
| `tests/test_experiment_reports_capacity.py` | 1 |
| `tests/test_experiment_reports_cli.py` | 14 |
| `tests/test_experiment_reports_decision_order.py` | 4 |
| `tests/test_experiment_reports_disclosure.py` | 4 |
| `tests/test_experiment_reports_faults.py` | 4 |
| `tests/test_experiment_reports_late_results.py` | 2 |
| `tests/test_experiment_reports_logging.py` | 2 |
| `tests/test_experiment_reports_migrations.py` | 5 |
| `tests/test_experiment_reports_publication.py` | 2 |
| `tests/test_experiment_reports_recovery.py` | 1 |
| `tests/test_experiment_reports_sections.py` | 1 |
| `tests/test_experiment_screen_cli.py` | 22 |
| `tests/test_experiment_selection_cli.py` | 29 |
| `tests/test_experiment_selection_migrations.py` | 4 |
| `tests/test_experiment_supply_layout.py` | 10 |
| `tests/test_extraction_normalization_cli.py` | 5 |
| `tests/test_extraction_normalization_repair.py` | 34 |
| `tests/test_extraction_normalization_selection.py` | 1 |
| `tests/test_model_mapping_rpc.py` | 10 |
| `tests/test_replay_business.py` | 1 |
| `tests/test_replay_container.py` | 1 |
| `tests/test_replay_deadline.py` | 16 |
| `tests/test_replay_descendant_deadline.py` | 4 |
| `tests/test_replay_entry.py` | 2 |
| `tests/test_replay_faults.py` | 24 |
| `tests/test_replay_os.py` | 1 |
| `tests/test_replay_process.py` | 2 |
| `tests/test_report_replay_projection.py` | 3 |
| `tests/test_screening_recovery_trace_cli.py` | 23 |
| `tests/test_stage_b_admission_source_closure.py` | 12 |
| `tests/test_stage_b_egress_preflight.py` | 41 |
| `tests/test_stage_b_model_mapping.py` | 11 |
| `tests/test_stage_b_production_prompts.py` | 10 |
| `tests/test_stage_b_trace_restore_cli.py` | 2 |
| 唯一并集 | **595**（61 个模块） |

收集原始日志、完整 node ID、逐模块 JSON、精确命令及源码 `__file__` 核验在本票树外交付报告。
各票同名模块曾随补丁扩展，以上当前数量覆盖旧稿数量；不把同一模块计入多票多次。

## 组合回归与冻结材料

本票先重现三份旧恢复 trace 全对象比较和 D7 守卫：5 failed、25 passed。
逐字段核对三份 trace 的全部原 13 个字段一致，只有新增 `workflow`。
经逐份具体审阅，在备份前以公共 `query_paper_trace(...).safe_payload()` 固定工作流 JSON；
恢复后仍完整 `json == expected`，不删除 workflow 或旧字段。原三个模块 18／9／5 个节点、
WAL、幂等、恢复和语义损坏拒绝保持；新增 D1 另以 literal 验证 unknown／experiment 用途、
空业务与非空 B 的选样、两次 PDF 历史、正文、核查和 Read，自动队列始终拒绝。
快照是跨备份的差分 oracle，不代替独立语义断言。

D7 使用新的 `pi-admission-v26` 策略键与显式准入源码闭包；v1–v25 的原向量、摘要锚、
同 key 重绑拒绝、源码修改拒绝及解释器含义保持。新增权威链涵盖产品入口、模型配置／
Contract／输出校验、外发授权、当前样本／正文和事务内领取预算；不依赖运行时目录扫描。
可选封印构建对这些源码改动受控拒绝。D7 工程绿不授予可选严格 Live 资格，
所有者豁免仍是独立决定，原能力状态保留 unknown／not_assessed。

实际消费者组合按风险选择根／候选／Screening、Read retry／核查、冻结报告／暴露、
新正文选择与 normalization、备份恢复、完整合成隔离回放及超时后代清理。
本票另运行受影响守卫、strict mypy、Ruff／format、非空提交差分检查和触发的入口兼容组合。
各次失败、恢复后通过、耗时和节点并集在树外逐项记录，开发期检查不写正式验收回执。

固定范围只读审计以稳定本地 main 为显式 base／target，分别核对 current_change、
baseline_drift 与下游组。敏感确认和必要白名单重绑绑定最终合入树身份，由最终集成者执行；
子票旧确认、历史哈希和已有门禁不能直接沿用。未知新台账仍为固定材料，不借此改变分类。

### 新增的旧组消费闭包

三份旧 trace 测试新增使用 `tests/stage_b_trace_support.py`，它只在备份前调用
`src/paper_radar/paper_trace.py` 的公共安全工作流投影并做 JSON 模式序列化。
最终集成者将前者作为 A6 support/source、后者作为 A6 source 显式登记，
沿 A6→A10 的证明依赖覆盖下游；不增加 required 测试模块、回执或固定分母，
不重复制造 scope 哈希边。两文件最终 SHA 与用途在树外交接中列明。

## 已冻结工程索引

- [公开生产 Prompt](issue-186-production-prompts.md)。
- [根与 Feed](issue-187-experiment-feed.md)、[实际供给布局跟进](issue-187-supply-layout-followup.md)。
- [候选快照](issue-188-candidate-views.md)、[类型跟进](issue-188-candidate-types-followup.md)。
- [外发／预检](issue-189-egress-preflight.md)、[内存仅披露](issue-189-memory-disclosure-followup.md)、[选样授权](issue-190-selection-authorization.md)、[映射探测](issue-191-model-mapping.md)。
- [Screening](issue-192-screen-command.md)、[失败恢复与 trace](issue-193-recovery-trace.md)、[代接受](issue-194-delegated-acceptance.md)、[PDF](issue-195-pdf-confirmation.md)。
- [受限提取](issue-196-bounded-extraction.md)、[六项版式核查](issue-197-layout-review.md)、[显式正文选择](body-selection-delivery.md)、[normalization v2](extraction-normalization-v2-repair.md)。
- [显式 Read](issue-198-explicit-read.md)、[规范 paper retry 跟进](issue-198-paper-retry.md)。
- [实验报告](issue-199-experiment-reports.md)、[决定顺序](issue-199-report-decision-order.md)、[披露精度](issue-199-report-disclosure-followup.md)。
- [暴露导出](issue-200-exposure-export.md)、[隔离回放](issue-201-offline-replay.md)、[时限与后代清理](replay-deadline-repair.md)。

旧台账反映各自时点，不修改其历史计数或把旧稿当作最终树的执行结果。
公共现状分别由[B 工作流](../contracts/stage-b-workflow.md)、[报告](../contracts/reports.md)、
[暴露导出](../contracts/exposure-export.md)、[备份恢复](../contracts/backup-restore.md)拥有；
组件规则链接回自己的权威。README／GLOSSARY／规格／ADR 复核不新增产品决策。

## 所有者签收索引

这里只索引既有脱敏结论，不重述、补证或扩大任何真实运行主张：

- [#204 版式验收](issue-204-live-layout-acceptance.md)。
- [#205 真实链验收](issue-205-live-chain-acceptance.md)。
- [#205 隔离恢复验收](issue-205-recovery-acceptance.md)。

三份签收原字节保持，各自冻结 SHA、样本范围、保留的失败与未验证项以原文为准。
本票没有读取其私有底稿或重跑真实链。

## 下游义务与未验证范围

| 下一模块 | 独立义务 |
| --- | --- |
| C | 新的长期生产根；保留器启用前导入冻结暴露清单，沿 DOI 与双向权威关系永久排除，覆盖重复发现、版本变化、未来合并；实验结果不提升、不复用 |
| D | 完整建议、reuse 与正式盲评校准；B 的公开 Prompt／建议／代接受不是正式校准基线或标签 |
| F | 四刊、中文、复杂正文和摘录 fixture、正式质量与通用资源阈值；单样本和主机内存披露均不替代 |
| G | 通用长文 chunk／reduce 与正常队列，禁止截断全文绕预算；延续两次和显式 retry |
| H | 完整日报与复核，五／三容量、冻结成员／依据、受限内容警告与 unknown／not_assessed 继续独立成立 |
| I | NAS／无人值守／最终恢复，原根与恢复副本并行的授权、预算、租约和重复执行风险；本机回放不提供跨副本协调 |

完整阶段 A、正式生产 Read、四刊及通用质量／资源、模型参数实际效力、科学结论人工复核、
可选严格 Live 证据链、NAS 与跨副本执行协调均未由本工程台账验证。
