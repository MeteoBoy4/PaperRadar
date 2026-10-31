# Verification Scope 活文档解绑：第一步迁移台账

本次冻结记录的规范数据是 [scope-document-migration.json](scope-document-migration.json)。
基线为 `78413e6524e0900cb7051a70adcf590fa2e01799`，归并输入为 `ca0e551`；
本记录由包含它的最终提交与工作树身份覆盖，不进入任何 scope，避免自引用或新增级联。
候选准备不表示 #131 已完成；独立审阅、最终提交上的完整门禁及 main 收口仍须完成。
最终 run_id 只记外部收口报告，不写回本台账。

## 分类与冻结依据

[#127 分类清查](scope-material-inventory.json)以基线 11 组／1,229 条登记／710 条路径为母集，
每条保留类别、用途、权威来源与处置。其 `bindings` 是旧母集，
`classification_rules.live_documents.exact_paths` 是唯一精确活文档分类清单（28 路径），
`unbound_materials` 的 36 份披露不构成追溯登记。未知文档没有自动豁免。

本次移除 19 条活文档绑定（A8=3、A9=10、A10=6），规范数据 `removed_bindings`
逐条原样保留组、路径、旧 SHA、类别和替代依据；新增 A10 最小冻结摘录后为 1,211 条。
history、需求/覆盖台账、ADR、Schema、代码、测试、fixture 和依赖身份继续固定；
42 条旧 scope 引用边保留，尚未集中登记。既有 `docs/verification/`、`intent/review/`、
`contracts/` 原字节清单与 SHA 在 `preserved_baseline_materials` 中供复核。

## 隐藏耦合与 A10 去向

[A8/A9 迁移数据](a8-a9-document-migration.json)保存 writer 与 coverage 的具体变更；
本台账 `a8_a9` 归并其迁移事实。A9 writer 以冻结 read-validation history 为依据，
`provenance_replay` 指向同一冻结材料。
A10 保留原 693 个需求 ID、顺序、需求来源定位/原文，以及 37 份完整来源元数据、原文和 SHA；
`format_version=1` 不变、`ledger_revision=2` 明确升级覆盖口径。
活文档只作上下文，covered 必须有真正的 covered 行为与固定集合内材料，操作记录不算产品覆盖。

[完整 A10 迁移数据](a10-scope-document-migration.json)的 `pointer_migrations`
逐项列出全部 2,237 个旧活文档指针 occurrence 的 owner、字段、需求/行为、理由及新去向；
本台账 `a10` 同步其三项文档行为、methodology 前后语义和处置差。
`documented_decisions` 由 ADR-0033/0034 与
[最小冻结摘录](a10-documentation-excerpts.json)承载具体文档义务；
`sampling_operational_docs`、`documents_and_operational_boundary` 的操作部分转为 operational，
逐字引用 #104–106 完成/补修原文；文档内容义务由独立冻结材料证明，产品部分继续由 covered 行为证明。
A10-104/105/106-BODY-001 三个父票导航条目 covered→operational；另有上述真实缺口 covered→not_assessed：
covered 550→546、operational 108→111，not_assessed 28→29、superseded=7 不变，合计 693。
独立review后发现 A10-100-C6405695568-CLAUSE-037 的三处原因登记义务缺少规格 §8.4，单独 covered→not_assessed；Contract/GLOSSARY 两处交付内容保持。固定集合外指针约束未放宽。

## 冻结测试与受控重绑

三处允许修改逐条保存在 `frozen_test_changes`：

| 模块 | 修改 | 固定数量 |
| --- | --- | ---: |
| `test_a9_integrity.py` | read-validation Contract 负例换为本组原参数未列的 a9-scope-review | 参数9→9，模块92 |
| `test_a10_integrity.py` | fixture-audit Contract 负例换为本组原参数未列的 ADR-0032 | 参数10→10，模块108 |
| `test_a9_scope.py` | 固定成员断言改指 a9-scope-review | 模块4 |

其他冻结测试和四个公开审计模块字节未变。`frozen_test_bytes` 记录基线/第一步 SHA，
`stage2_scope_test_bytes` 专列第二步必须保持的冻结 scope 测试字节。
`fixed_group_counts` 逐组逐模块保存完整固定分母：

| 组 | 模块 | 用例 |
| --- | ---: | ---: |
| 完整 A2 | 69 | 1401 |
| A3 | 17 | 268 |
| A4 | 30 | 375 |
| A5 | 14 | 529 |
| A6 | 48 | 543 |
| A7 | 39 | 564 |
| A8 | 20 | 630 |
| A9 | 15 | 560 |
| A10 | 37 | 450 |

A1/A2-01 原审计无固定计数行，不解释为零。共享测试跨组出现，各组分母分别保留。

格式与静态检查稳定后，按旧规则拓扑审阅 14 条重绑；`rebindings` 每条记录组、scope、
成员路径、旧/新 SHA 和理由。实际修改为 #128 writer/coverage/两测试、#129 validator/coverage/一测试、
#130 共享审计实现；其余为 A8→A9/A10、A9→A10 的旧 scope 传播。
不是接受所有候选哈希，也未增减任何组的测试成员或分母。

独立review修复另在 `review_rebindings` 记录两条实际 fixture 更新：A10 覆盖台账和最小冻结摘录；A10 无下游，不产生额外 scope 传播。原 14 条基线→最终重绑的台账同步最终 SHA，新增摘录绑定也同步实际 SHA。`a10.semantic_review` 指向完整复核记录：原 635 个操作／上下文 occurrence 的 302 个 owner 全部核对，16 个文档义务逐项去向见 [A10迁移说明](a10-scope-document-migration.md#操作与上下文的完整语义复核)。新增 11 段最小原文，加已有 4 段共 15 段，均有基线提交、全文 SHA、章节行号和原文 SHA；其中 §8.4 摘录证明缺口边界。先前候选的审计／测试结果不能代表修复后树。

## D1 新能力覆盖

四票新增能力与本票review修复均由独立未绑定模块承载，当前总计 93 项。
它们不进入历史固定分母或回执，最终同次全量 pytest 仍须全部通过。

| 票 | 独立模块 | 用例 | 证明 |
| --- | --- | ---: | --- |
| #127 | `tests/test_scope_material_inventory.py` | 4 | 基线母集、分类、隐藏耦合、摘录审查 |
| #128 | `tests/test_a8_a9_document_scope.py` | 23 | A8/A9 解绑、writer 与固定材料负例 |
| #129 | `tests/test_a10_scope_migration.py` | 18 | 693/37 保真、2237 指针、处置差、摘录与拒绝 |
| #130 | `tests/test_scope_document_guards.py` | 27 | 防回绑、受控分类、副本文档与冻结材料、历史适用性因果 |
| #130 | `tests/test_live_document_links.py` | 4 | 活文档到冻结证据的相对链接存在性 |
| #131 review修复 | `tests/test_a10_document_obligations.py` | 17 | 15 项文档交付内容、§8.4 真实缺口、302 owner／635指针穷尽复核 |

`tests/scope_document_support.py` 只共享隔离副本重绑与 writer 子进程协议；A8/A9 与防护测试模块各自维护独立白名单、组选择和预期断言。原 18 项 A10 迁移测试仍为18项，仅同步真实处置差；没有修改其他冻结测试。

相关静态/功能验证和 audit/collect 的具体命令与结果由外部 `131-result.md` 交接；
正式验收只认最终提交上的同次门禁与可信终态。历史 run 样本留在根原目录，root 再按固定样本复核，
不搬迁、不改写历史 JSON。任何候选事实均不代表四刊 live、Pi RPC、模型质量、正式校准、Docling、NAS 或完整阶段 A。
