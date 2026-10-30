# 论文事实 Contract 历史实施与验收约定

本文件迁存基线 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 的
`docs/contracts/paper-facts.md` §11 原文，保留其中 #69、#74、#75 及 #111 的历史时点。
以下“当前”“后续”“尚未注册”“未验证”均是原记录的措辞，不表示迁存时的实现状态，
也不构成本轮验收结论。历史通过不证明当前工作树、真实来源、模型、实验或 live 就绪。
现状见[论文事实 Contract](../contracts/paper-facts.md)，承接责任见[路线图](../roadmap.md)。

## 11. 实施与验收约定

以下历史目录/验收记录按基线原字节保留；其中逐票状态不作为当前实施前沿，当前责任见[路线图](../roadmap.md#模块承接索引)。

本组图为 #68→#69→#70→#71→(#72,#73)→#74→#75。与 N8 建议不同，不交付独立空表票：#69 连同最小 migration、首条 DOI 登记、查询和测试纵向落地。首个 revision 为 `a601_paper_facts`；后续扩表追加顺序 migration，不改已合入 revision，最后验收绑定实际末端 head，不能永久以 a601 代替。

A6 只在 #75 注册，ISSUE=75，PARENT_ISSUE=67，前置同次 A1、完整 A2、A3、A5，A4 仍控制完整门禁。中间票均须完整离线入口 0，新测试独立模块，不改旧用例分母、不更新历史证据、不提前注册 A6。旧源码/head/help/backup 绑定先按 a2_scope wrapper、完整 A2、A3、A4、A5 拓扑重审复验，再冻结 A6 哈希；台账列旧哈希/新哈希/原因/run_id，不参与自身最终 run_id 哈希以免循环。

最终 run_id 必须来自全部功能和验收集成后的最终工作树，严格绑定代码、工作树、lockfile、真实 revision、材料及实际回执；中间通过不能冒充最终通过。长门禁前 `./scripts/dev-environment check`，单次先留 30 分钟观察预算并回填实际耗时，超时先诊断、不删测。#65 若已合入沿用其回执协议，未合入不自行领取测试并行优化。

本票不改 README 或其他公共 Contract 的已交付能力声明；各后续票随真实实现同步。A5 旧 NOT_ASSESSED 的 paper_fact_mapping 是当次历史结论，不回改 a5_scope.py；由最终 A6 明确新增覆盖。文档落地提交由 #68 完成记录引用，主方案处置映射见 ADR；不修改 #67 正文/状态或其历史固定提交链接。

### #69 重解析裁决的跨票验证归属

| 用户要求 | #69 已覆盖 | 后续必须覆盖 |
| --- | --- | --- |
| v1 有摘要、同材料 v2 无摘要 | 当前查询缺摘要，旧修订文本/依据不变；从公开查询读出的旧文本调用既有 A5 builder 得到原输入指纹 | #73 经公共历史版本/修订/快照映射重建完整输入链 |
| v2 无摘要、另一来源有摘要 | 当前跨来源仍受控拒绝，不宣称 fallback 通过 | #71 仲裁与 #74 集成验证 fallback 获选来源、provenance 变化与新修订 |
| v2 改摘要文本 | 当前公开事实经既有 A5 builder 产生不同指纹 | #73 正式映射及历史重建指纹链组合验证 |
| v2 候选全空 | not_retained、原字段/修订不变、取得原结果与版本门禁保留 | 后续消费者继续保持同一保护，不推断清空或撤销 |

该表不替代各后续票的验收，特别不能把 #69 的测试内 builder 组合当作已交付公共历史映射。


### #74 组合恢复证明（尚未注册 A6）

公共事实服务构造的同一库覆盖四来源冲突/未选候选、人工修订、无 DOI 及后补登记、跨 Feed、
多 DOI/版本、正式有/无摘要升级、同级歧义、三态关系及两端尚未出现的 relation-only。
活跃 WAL 备份在完整副本上解析论文语义；恢复再搬迁后的全新进程仅接收受控引用与独立散列，
从候选引用重建旧/新快照的 boundary/value payload 和 fingerprint。历史证据比较保留完整字段、
候选/取得引用、版本与选择；后补 DOI 是当前身份登记，不将原来未知 DOI 强装成历史冻结字段。
从未获选版本的历史 selection=null，正式缺摘要当前仍 missing_abstract，不跨版本补文本。
完整重解析缺摘要后由注册机构补缺会追加 provenance 修订；全空更高解释继续 not_retained 且不清空。
独立关系不随字段解释撤销。

`trace --verify-source-bytes` 默认关闭，普通查询/映射无 blob I/O；显式核验包括无字段观察的
仅关系来源材料。缺/坏关系材料返回 corrupt_reference，不输出原始 item/响应正文，不改历史。
副本中 FK 合法且重哈希的 item/payload、provenance、DOI 归属、错获选候选、完整修订、选择与关系
证据矛盾由备份/恢复受控拒绝；合法未齐端点和 requires_merge 不报损坏。详见备份恢复 Contract。

新增独立测试不改变旧固定分母，不登记 A6；仅证明离线历史重建，未验证完整阶段 A、live、
真实来源、RPC、Docling/NAS 或任务续跑。首次真实导入前（B 起、C 扩展）的 parser 固定样本门禁和强冲突材料门禁保持。


### #75 最终独立验收

A6 scope 的 ISSUE=75、PARENT_ISSUE=67，固定实际末端 a604_version_relations；不新增 migration
或 backup 格式。Feed 指纹权威为 `paper_radar.papers.feed.FEED_ITEM_FINGERPRINT_VERSION=1`，
`item_fingerprint` 对原始 item 字节计算 SHA-256，独立固定 abc 向量验证原算法未变。
同次 A1、完整 A2、A3、A5 前置、完整执行回执、固定源码/材料、真实迁移与运行身份逐项核对。
12 项能力与正文/评论归属见[最终 A6 规格对照](../verification/a6-requirements.md)。A4 继续决定总门禁。
A5 当时 `paper_fact_mapping` NOT_ASSESSED 原样保留；正式映射与 #74 历史重建由新增 A6 覆盖。
不将历史切片说明中的“尚未注册”当成当前注册状态，也不改写历史运行 JSON。

本结论仅证明离线事实闭环，所有第 10 节来源假设和首次真实导入前的强冲突材料/parser 固定样本门禁
继续未验证。stage_a_verified/live_verified/rpc_verified 固定 false，不授予任务资格或模型预算。

A7-02 任务层已持久化 boundary/value 规范输入与请求依据，见[任务 Contract](../contracts/screening-tasks.md)。
论文事实包只公开既有连接级 `resolve_revision` 供调用方在 BEGIN 后复核一致性，
不反向依赖任务服务，不新增语言事实、预算或执行资格。

#111 将首次真实写入责任前移到 B，C 扩展；实验根也是真实写入，不豁免强冲突观察、最终接口或隔离恢复，见 [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。历史 A6 结论不因此获得 live 证明。
