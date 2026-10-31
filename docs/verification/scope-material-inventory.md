# Scope 活文档解绑前的登记清查

依据：[#126 规格与 S1–S8 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/126)、
[#127 逐条清查口径](https://github.com/MeteoBoy4/PaperRadar/issues/127#issuecomment-6536968672)。
本记录固定实施基线 `78413e6524e0900cb7051a70adcf590fa2e01799` 的迁移准备，
不改变生产登记、不重绑 scope、不产生验收结论。

## 数据与复核口径

逐条数据唯一归属为 [scope-material-inventory.json](scope-material-inventory.json)。
最小键为 `(group, kind, path)`；同一路径跨组分别保留，不提前做中央登记去重。
`bindings` 的每条记录保存旧 SHA、类别、组内用途、分类依据引用和迁移处置。
`classification_authority` 引用 `classification_rules.categories`，回答分类来自何处；
`replacement` 单独回答解绑后由哪些材料承载证明，或者明确说明它仅为非证据上下文。
保留条目的 `replacement.type=original_binding` 表示原绑定继续，不虚构替代材料。

母集来自基线自身的 `./scripts/audit-verification-scope --json`，结果无异常或漂移。
JSON 记录生成命令、基线和审计输出的规范 JSON SHA，测试用本地 Git 对象导出基线副本，
执行副本自己的审计 CLI 后逐条比对，不以未来已解绑的工作树反向改写清单。
复核与 #126 基线一致：11 组、1229 条登记、710 个路径，差异为空。

| 组 | 登记条数 | 拟移除活文档登记 |
| --- | ---: | ---: |
| A1 | 12 | 0 |
| A2-01 | 56 | 0 |
| 完整 A2 | 164 | 0 |
| A3 | 60 | 0 |
| A4 | 87 | 0 |
| A5 | 53 | 0 |
| A6 | 109 | 0 |
| A7 | 146 | 0 |
| A8 | 66 | 3 |
| A9 | 140 | 10 |
| A10 | 336 | 6 |
| 合计 | 1229 | 19 |

## 分类与解绑计划

`classification_rules.live_documents.exact_paths` 是供 #130 消费的唯一活文档分类事实：
当前三份主文档及 25 份现状 Contract，共 28 个规范仓库相对路径。
匹配须精确，不按扩展名、目录前缀或文件名外形推定；新增或改类需要显式审阅。
28 个路径中只有 12 个在本基线被绑定，共形成 19 条逐组登记：

| 组 | 路径 | 后续责任 |
| --- | --- | --- |
| A8 | `README.md`、`docs/contracts/pi-rpc.md`、`docs/contracts/verification-status.md` | #128；原 history、需求与能力材料继续冻结 |
| A9 | `README.md`、`GLOSSARY.md`、`intent/draft.md` | #128；摘要为上下文，Read 需求由 coverage、history 与固定 Schema 承载 |
| A9 | `docs/contracts/read-validation.md` | #128；先迁移 writer、provenance coverage、负例和固定集合断言 |
| A9 | `docs/contracts/frozen-contracts.md`、`runtime-config.md`、`config-projections.md`、`config-snapshots.md`、`verification-status.md`、`backup-restore.md`（后五项沿用同目录） | #128；逐条替代路径见 JSON |
| A10 | `README.md`、`GLOSSARY.md`、`intent/draft.md`、`docs/contracts/fixture-audit.md`、`docs/contracts/backup-restore.md`、`docs/contracts/verification-status.md` | #129；先迁移覆盖指针与静态文档行为，再解绑 |

其余 1210 条保留原绑定：代码、测试及支撑、fixture、依赖身份、版本化示例、
Frozen Contract Schema、ADR、history、需求/覆盖台账与验收基础设施。
其中 42 条 scope→scope 登记在第一步仍保留；第二步另行处理。
`docs/verification/offline-evidence.md` 的三条登记也继续保留。

## 隐藏耦合与具体需求审查

`hidden_couplings` 保存九项逐组迁移任务，记录基线文件和可回放的原文字面指针。
每条拟移除登记通过 `coupling_ids` 关联任务：

- A9 writer 额外核对现状 `read-validation.md` 的哈希；history 解析仍须保留。
- A9 coverage 的 `provenance_replay.materials` 指向该活文档。
- A9/A10 integrity 负例分别含该文档和 `fixture-audit.md`，须等量替换，保留各自 9/10 个参数及受控原因断言。
- A9 固定集合断言仍要求现状 `read-validation.md`。
- A10 `pointer_valid` 只允许固定材料，不能通过放宽校验来迁移。
- A10 三项静态文档行为必须逐项改指或披露处置变化，不能把“文档已记录”自动解释为新文档仍符合旧字节。

A10 的逐需求引用 ID 已全部保存在 `hidden_couplings[a10_coverage_pointers].references`：

| 活文档 | `scope_materials` 引用数 | `public_behavior_pointers` 引用数 |
| --- | ---: | ---: |
| README | 225 | 7 |
| GLOSSARY | 225 | 184 |
| draft | 225 | 184 |
| fixture-audit | 409 | 184 |
| backup-restore | 241 | 7 |
| verification-status | 227 | 0 |

`excerpt_review` 按具体承载者记录七项审查：A8 RPC 需求、A9 Read 需求、
§13.2 六篇历史参考文献样本、A10 获取/类别边界，以及三项静态文档行为。
后三项分别关联 177、1、6 个原始需求 ID，并保存完整基线行为记录供 #129 逐条处理。
693 个 ID 的来源均为原台账内嵌的 37 份 issue 原文；测试重验这些原文 SHA。
历史样本已存在于 `fixtures/a10/historical-v1.json`，类别与声明边界已由 ADR-0032–0034 承载。

本次未发现只在活规格中存在且缺少冻结承载者的既有验收要求，因此
`frozen_excerpts=[]`，不复制规格全文或建立另一份活规范。
三项文档行为中的完成/操作事实，#129 须明确改指或披露状态、计数变化；
本清查不提前决定这些处置。若逐条迁移发现真实缺口，须先按具体 ID 复核，
再新增带基线提交、章节、原文与 SHA 的冻结摘录，不能放宽 `pointer_valid`。

## 未绑定材料与后续汇总

`unbound_materials` 列出基线 `docs/contracts/` 与 `docs/verification/` 中
形似依据但未登记的全部 36 份材料，包括 `a4/a6/a7-requirements.md`、
`a7-history-ledger.json`、`a-narrow-delivery.md`、`issue-114-feed-delivery.md`、
未绑定 history 及 16 份未绑定 Contract。它们仅作披露，不追溯绑定、不授予冻结效力。
本次新增清单与本说明也不加入 scope。

#128/#129 可按 `disposition=remove_after_migration` 导出 19 条旧 SHA 与替代处置，
并按 `coupling_ids` 登记实际迁移、冻结测试修改理由及计数差。
#131 统一解释漂移并按旧规则重绑；本票没有修改任何冻结测试或既有证据。
#130 只消费上述精确分类事实，不另建白名单。

独立测试见 [test_scope_material_inventory.py](../../tests/test_scope_material_inventory.py)：
验证母集无遗漏/重复、审计摘要、分类与替代材料、未绑定披露、原始耦合指针、
A10 需求引用及来源 SHA；若新增冻结摘录，还核对其基线原文与 SHA。
测试依赖本地保留该基线 Git 对象，不访问网络、不运行完整门禁。
这些静态核验不证明 writer 迁移完成、四刊 live、Pi RPC、模型质量、校准或完整阶段 A 通过。
