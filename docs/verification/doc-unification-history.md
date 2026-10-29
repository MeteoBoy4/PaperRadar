# 文档统一迁入的历史证明范围

本文件保存 #113 整理时从路线图移出的既有历史证明/状态摘要，来源基线为 `e642d83`；不替代原始运行证据，不扩大任何通过范围。当前计划与责任仍见[路线图](../roadmap.md)。

## Read 恢复证据范围


#98 已以两份历史配置和中/英文、single/reduce 四份候选原字节验证[规格 §9.1](../../intent/draft.md#91-本机一致性快照)所述隔离恢复与
再次搬迁。消费上下文由固定测试常量重建，不属于恢复产物，也不证明真实 PDF、
evidence-map 或正文选择；范围见 [Read 恢复说明](../contracts/read-validation.md#恢复范围98)。

## 阶段 A 收口与 B 前置（#111，目标规格）


[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111) 的文档更新没有交付或验收新增能力，A4 1.3.0 历史材料、A2 示例和历史结论保持不变；A1–A10 通过不等于完整 A 通过。历史范围见[A 收口清单](../verification/stage-a-closure.md)。

A 窄收口、B 前置的当前承接责任见[模块表](../roadmap.md#模块)和[承接索引](../roadmap.md#模块承接索引)。安装探测与离线工程可并行，首次真实消费须先满足相应入口。

B 实验隔离、摘要入口、PDF 最低路径、质量与材料保管要求见[规格 §11 B](../../intent/draft.md#阶段-bjgr-feed-第一条真实纵向闭环)及[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)；未来 Pi 升级要求见[规格 §7.8](../../intent/draft.md#78-pi-固定版本供给)。

## 文首记录的状态与出处


以下仅索引基线文首的历史切片边界，已完成模块见[路线图 A1–A10 表](../roadmap.md#已完成)；早期“后续”由后来的证据收口，不作为当前待办。目标要求以各链接正文为准。

| 原记录日期 | 出处 | 规则/证据归属 | 历史证明边界与承接 |
| --- | --- | --- | --- |
| 2026-10-11 | Pi 适配边界 | [docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md) | §5、“我的决策”及有界 RPC；当次仅文档，代码/配置/登记版本/Frozen Contract 不变。 |
| 2026-10-12 | #26 供给方案 | [intent/draft.md#78-pi-固定版本供给](../../intent/draft.md#78-pi-固定版本供给) | 固定版本供给、执行核对与恢复要求；当次不证明安装/RPC/校准通过。 |
| 2026-10-18 | 供给与升级裁决 | [intent/draft.md#78-pi-固定版本供给](../../intent/draft.md#78-pi-固定版本供给) | D1–D5：新声明版本、无脱网重建承诺、三段正式版本、当前与最近三个旧安装、行为影响判定必填；当次不证明验收。 |
| 2026-10-22 | #67、#68、#69–#75 | [docs/adr/0030-paper-version-identity-and-source-observations.md](../adr/0030-paper-version-identity-and-source-observations.md) | D1–D4/N1/N2、身份/Feed 回摆/冲突；A6 离线底座已注册，真实来源/parser/live/完整 A 未验。旧固定正文不覆盖后续裁决。 |
| 2026-10-23 | #76、#77–#80、#81、#82、#83、#84 | [docs/contracts/screening-tasks.md](../contracts/screening-tasks.md) | 预算/派生三值适用性及 boundary/value、retry、查询、历史恢复/独立 A7；仅离线 test，screening CLI/paper trace 组合未交付；真实模型/完整 A 未验。语言来源后由 ADR-0035 裁决。 |
| 2026-10-24 | #85 D1–D4/P3 | [docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md) | 首次 snapshot 语义/回执 snapshot 审计、A7 最终模型裁决、零 token 未知及 cwd 外发例外；真实 Pi/模型未验。 |
| 2026-10-25 | 获取方式裁决 | [docs/adr/0032-relax-paper-acquisition-without-evading-access-controls.md](../adr/0032-relax-paper-acquisition-without-evading-access-controls.md) | §4.3/§4.8/§11 F/§13/§15；合法自动化与访问规避边界。策略可按真实审计另票调整；当次只改文档与两份 A9 文档哈希，业务代码/配置/Frozen Contract 不变。 |
| 未标日期 | #103 | [docs/contracts/fixture-audit.md#103-已交付的取得边界](../contracts/fixture-audit.md#103-已交付的取得边界) | 计划/有界 HTTP/未安装通道/原子结算/只读查询/基本恢复；当时四刊选样/矩阵/resume/replay/独立验收待续，后由 #104–#108 收口；不证明 live/完整 A。 |
| 2026-10-26 | #102 | [docs/contracts/fixture-audit.md#pdf-字节事实与-backend-期望102](../contracts/fixture-audit.md#pdf-字节事实与-backend-期望102) | 本机 PDF 字节/backend 期望与显式替换，旧字节/期望保留，新 SHA 不继承结果；不下载/不运行 Docling，不证明四刊正文/完整 A。 |
| 2026-10-26 | #104 | [docs/contracts/fixture-audit.md](../contracts/fixture-audit.md) | 四刊固定选样/原位继续、整份 Feed/显式身份/类别、不按成败换样；当时后续矩阵/回放/独立门禁待续，后由 #105–#108 收口；真实审计未验。 |
| 2026-10-26 | #105 | [docs/contracts/fixture-audit.md](../contracts/fixture-audit.md) | audit run、适用矩阵/主区块/截断/A6仲裁/真实分母、复用材料及原时间；complete 仅终态、查询不输出原摘要；当时回放/混合闭包/门禁待续，后由 #106–#108 收口。 |
| 2026-10-26 | #106 | [docs/contracts/fixture-audit.md](../contracts/fixture-audit.md) | audit resume、冻结 v1 replay、服务 API 新 parser/差异；两类真实进程/事务故障/基本恢复离线验证，无运行时不宣称重解析；当时完整混合闭包/门禁待续，后由 #107/#108 收口。 |
| 2026-10-26 | #107 | [docs/contracts/fixture-audit.md](../contracts/fixture-audit.md) | 单刊 Feed/整计划 abstract_audit、不可变汇总、真实 a704 五类非空升级/活跃 WAL 恢复；不联网/不自动继续，source_missing 单列、未引用制品合法；当时完整门禁由 #108 收口。 |
| 2026-10-26 | #107、#108 | [docs/verification/a10-requirements.md](../verification/a10-requirements.md) | A10 完整需求台账/真实回执/十四份同次证据，直接前置 A1/完整 A2/A3/A6；其他必需组仍决定总门禁。仅 HTTP 离线，未验范围见路线图继承缺口。 |
| 2026-10-27 | 原题名语言裁决 | [docs/adr/0035-feed-derived-original-title-language-fact.md](../adr/0035-feed-derived-original-title-language-fact.md) | 首发 Feed 归属 v1，只有《大气科学》中文；不做语言检测、false 仅非中文、无归属不得 value；当次只改文档/scope，自动派生/生产接线未交付。 |
| 2026-10-28 | #111 | [docs/adr/0036-isolate-stage-b-read-experiment.md](../adr/0036-isolate-stage-b-read-experiment.md) | 七项初始确认与后续评论；实验根不复用不提升、JGR入口、Pi1.4.0、/srv/pi-cwd、Docling extra及CLI归属；当次只改目标文档/scope，历史A1–A10证明不变。 |
| 2026-10-24 | #92、#93、#94/#95、#96、#97、#98、#99 | [docs/contracts/read-validation.md](../contracts/read-validation.md) | Read自有词汇/身份三元组/窄矩阵/阿拉伯数字/三种警告视图、配置/恢复/独立 A9；不证明真实Read/完整A。 |

### A10 继承缺口

[#108](https://github.com/MeteoBoy4/PaperRadar/issues/108) 的未验范围仍由 Audit/Source、C/F/Abstract、Feed/Body、I 承接：四刊实际审计、稳定性及 B 入口真实达标证据（JGR 判据已由 #111 固定）、完整摘要优先/额外区块的Screening语义、A6来源假设、AMS403策略、渲染/授权/正文/PDF/Docling/生产导入/NAS与完整阶段A；合法未来通道按新策略补跑。依据为[A10 未验台账](../verification/a10-requirements.md)和[收口责任](../verification/stage-a-closure.md#收口责任与未决项)。

#111 的[固定提交讨论文件](https://github.com/MeteoBoy4/PaperRadar/blob/212e312/intent/discussions/阶段A剩余工作.md)仅作非规范背景，七项初始确认来自该票 Further Notes。

D 承接配置投影边界未提供的完整校准变更审计、minor/major 分级与门禁；I 承接自动运行（见[规格 §11 I](../../intent/draft.md#阶段-i无人值守nas-恢复与最终验收)）；依据[配置投影 Contract](../contracts/config-projections.md#diff-结果与-cli)与[规格 §11 D](../../intent/draft.md#阶段-d完整-screening-与盲评校准)。

## 配置切片与底座验收范围


A2-01 覆盖 Profile；A2-02 覆盖 models/boundary；A2-03 覆盖 topics/value；A2-04 覆盖 escalation/reuse；A2-05 覆盖 extraction；A2-06（#21）覆盖 Read 配置；该历史拆分的目标规则保留在[规格 §6](../../intent/draft.md#六制品与目录契约)。

A2-07–A2-09 已交付期刊配置冻结、六投影/基线只读比较和配置事务并发中断恢复；
#26 的 adapter 配置及 #27 的历史快照发现也纳入完整配置验收。#25 在同一次完整
离线执行中追加独立 A2 结论，与 #12、A1、A2-01 共用 run_id 和证据哈希；迁移
revision 来自真实临时验收库，格式版本与固定合成材料逐项记录，正文与凭据不进入
验收摘要。固定覆盖和未验收项见 [离线证据](../verification/offline-evidence.md)（`docs/verification/offline-evidence.md`）。
此结论只证明配置切片，不代表完整阶段 A、正式校准、阶段 B 或 live 验收通过。
#29/#35 在同次固定计划中另追加 A3 存储/恢复结论，绑定同次基础证据、A1、完整 A2、
实际执行回执、运行身份、真实临时库 revision、版本和固定材料哈希；缺失、少执行、
skip/deselect/collect-only、漂移或中断不能借历史成功通过。#36/#45 同次另追加必需 A4
供给生命周期结论，绑定 A1、完整 A2、A3、真实格式和固定执行范围。六份主要文件共享 run_id，
pytest 回执另行绑定；A2-01 仍为可选历史组。A3 不声明论文事实、指纹、任务/可见性、
报告重建、Pi/Docling、真实来源或 NAS 已验收，stage_a_verified/live_verified 恒 false。

### A7 历史验收绑定

2026-10-23：#82/#83 完成唯一 retry 父链、版本化安全查询及非空完整历史隔离恢复；
#84 以独立必需 A7 组绑定同次 A1、完整 A2、A3、A5、A6，A4 仍决定总门禁。
依据：[ADR-0031 补充裁决](../adr/0031-screening-budget-and-derived-applicability.md#补充裁决)。

## 阶段输入历史证明范围


书目与供给身份仅通过封闭输入类型严格拒绝证明隔离，A5 当时没有论文事实模型，不宣称
“卷期页码更新到任务不重跑”已端到端验收；不为此创建 A4 安装记录。A2 的组件矩阵仍是
[配置投影契约](../contracts/config-projections.md)权威，该历史切片只核对各阶段一个代表传播及 Read、
期刊 tier、adapter 审计版本和 screening thinking_level 的少量交叉变化。
#73 的[论文事实映射服务](../contracts/paper-facts.md#8-当前查询历史重建与只读-cli)已在其独立测试中
覆盖真实登记、来源仲裁、人工修正和历史 revision/snapshot 的 boundary/value 输入重建。
该服务只读，规范载荷持久化已由 A7 任务层承担，完整任务资格和校准门禁仍未交付；A5 原固定范围及
当时的 NOT_ASSESSED 历史结论保持，最终 A6 已由 #75 登记，覆盖范围与单次判据见[离线 A6 结论](../verification/offline-evidence.md#a6-独立结论6775)。
独立复现命令与验收边界见[离线证据说明](../verification/offline-evidence.md)。
#53 单独交付时没有登记 A5 验收组；#54 追加独立 A5 结论后的历史 check-offline 输出七份
主要文件，另有实际 pytest 回执与终态；A6 注册时输出八份主要文件、总十份 JSON。
A7 登记时输出九份主要文件、总十一份 JSON，见
[离线证据入口](../verification/offline-evidence.md)。固定范围及规格映射见
[独立 A5 结论](../verification/offline-evidence.md#a5-独立结论4754)。
A5 通过仅声明四阶段输入计算、回放、比较和隔离恢复，不代表阶段 A、真实来源、RPC、
NAS 或自动精读通过。

<a id="整理中待确认的既有冲突"></a>

## 历史证据定位与审计入口


以下是证据的定位信息，不替代原记录，也不作为当前树通过结论：

- [阶段 A 收口台账原基线 `cdf5c1f4f18c19eead77d78cab0e9fafe668ebf1`](../verification/stage-a-closure.md)。
- [E0：5274 passed 的历史证据索引，源码 `a8a8ad87efb65bdf79719b6f093efe2a3c54f138`](../verification/stage-a-closure.md#证据索引与范围)。本机记录定位为 `verification-runs/ab9a89500053400db1c07d40e180a064{,.terminal,.pytest,.a1,.a2,.a2-full,.a3,.a4,.a5,.a6,.a7,.a8,.a9,.a10}.json`；未持有原文件的环境只能查看索引，不能声称已重跑。历史 `stage_a_verified=false` 不变。
- [A1 scope](../../scripts/a1_scope.py)、[完整 A2 scope](../../scripts/a2_full_scope.py)、[A3 scope](../../scripts/a3_scope.py)、[A5 scope](../../scripts/a5_scope.py)、[A9 scope](../../scripts/a9_scope.py)；其他范围由[冻结收口证据索引](../verification/stage-a-closure.md#证据索引与范围)导航。
- scope 默认审计不收集测试；需要独立核对分母时使用 `--collect --json`，该操作不执行测试体或发布结论。依据：[原审计口径](../verification/stage-a-closure.md#本票验证口径)。
