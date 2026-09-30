# AIHOT 对 PaperRadar V1 的可借鉴经验

调研日期：2026-09-30。研究对象：[KKKKhazix/AIHOT](https://github.com/KKKKhazix/AIHOT) 的固定提交 [`885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38`](https://github.com/KKKKhazix/AIHOT/tree/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38)（下文简称 `885b736`）。依据是该提交的仓库文档、源码、迁移和测试文件；没有运行 AIHOT 的服务、数据库、模型或真实信源验收。因此“实现了”只表示源码具有对应路径，不表示生产表现已由本次调研验证。PaperRadar 的对照依据是本仓库 `CONTEXT.md`、`intent/draft.md`、相关 ADR 和当前 `src/paper_radar/`；下文明确区分**已规定的目标行为**与**现有实现**。

## 执行摘要

AIHOT 最值得借鉴的是把“采集、昂贵分析、呈现”分开，并为每一步留下可诊断的输入、结果、成本及失败事实。尤其适合 PaperRadar V1 的增量是：**来源健康与空日报解释、同一事实的分层呈现、错例分层评测、付费请求去重与未知结果处理、报告窗口和补刊的边界测试**。其中大部分方向已经写在 PaperRadar 规格里，价值在于把验收做得更具体，而不是新加一套产品能力。

AIHOT 的核心排名和归组逻辑服务于行业新闻热度；PaperRadar 的对象是有版本、证据和人工决定的论文。**不要移植**网址或语义相似度自动合并、来源等级决定入选门槛、两次 0–100 分取平均、事件热度排名、网页/API/向量检索或由模型撰写日报导语。这些会破坏 V1 已定的身份、并列评价、盲评和只读报告边界。

## 1. 采集：统一入口、进度游标和可诊断的来源健康

**AIHOT 事实。** `collectSource()` 按来源读取、过滤、入库并排后续任务；同一批次先用 identity key 排重，只有新增或内容修订才入队。RSS 的 HTTP validator 在存储成功后才写入来源 cursor；失败保留上次成功进度，记录 `fetch_runs`、失败次数、最近错误及退避时间。列表详情页失败被当作 best effort，主采集仍可继续。源码：[collect.ts §64–112](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/sources/collect.ts#L64-L112)、[§160–207](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/sources/collect.ts#L160-L207)。它还根据近 7 天产出调采集间隔；该策略为其大量混合信源服务：[collect.ts §321–363](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/sources/collect.ts#L321-L363)。

**对 PaperRadar：借鉴机制，缩小范围。** V1 仅有四刊 Feed，`intent/draft.md` 阶段 C 已要求重复抓取幂等、元数据来源可追溯、单个 Feed 失败隔离、按周记录摘要可得性。实现时可为每个 Feed 保存 `last_attempt`、`last_success`、`validator`、连续失败数和简短错误码；只有解析及入库成功才推进 validator。对单篇详情补全失败形成观察或失败事实，不阻断其他论文。离线 fixture 覆盖 `200→304`、重复条目、写入失败后不得推进 cursor。**不建议**直接加 AIHOT 的多来源插件、动态抓取频率或关键词噪声过滤；PaperRadar 的四刊范围和“全部 journal-article 进入 Screening”已由 [ADR 0011](../docs/adr/0011-admit-all-journal-article-records-to-screening.md) 固定。

## 2. 去重：可借鉴“发现事实独立保存”，不能借鉴身份规则

**AIHOT 事实。** 不同来源的同一 identity key 会增加 `article_discoveries`，但不会让后来的聚合源覆盖主来源的标题与正文；原来源内容哈希变化生成 `article_revisions`，已经见过的旧哈希和乱码往返不会反复触发付费分析。其身份主要是规范化 URL，也对 X 帖子使用帖子 ID：[materials.ts §150–205](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/content/materials.ts#L150-L205)、[url.ts §5–63](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/lib/url.ts#L5-L63)、[核心表迁移](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/database/migrations/0001_core.sql#L60-L110)。

**对 PaperRadar：需改造。** 同一次 Feed 条目的重放去重、重复发现只增加 `Feed 发现记录` 以及外部 Adapter 不覆盖 Paper 事实，已经是本项目不变量；AIHOT 提供了具体的幂等验收样例。但 URL 规范化只能用于**同源条目或抓取地址级别**的幂等，不能据此自动合并 Paper。预印本与期刊版、重定向、不同 DOI 的同题论文，均需本项目的强标识与权威版本关系规则；见 [ADR 0005](../docs/adr/0005-only-merge-papers-automatically-on-strong-identifiers.md)、[ADR 0001](../docs/adr/0001-collapse-publication-versions-into-one-paper.md)。内容哈希可帮助识别重复观察，但不得把源文本哈希当作论文身份或覆盖版本历史。建议测试一条 DOI 被两个 Feed 发现时仅增加发现事实，以及相似标题但无强标识时仅生成候选。

**不借鉴语义自动归组。** AIHOT 将标题摘要向量召回的新闻报道交给模型判 `SAME_OCCURRENCE` / `SAME_STORY`，必要时二次复核；归组决策会落库。源码：[group.ts §1–40、§197–237、§287–337](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/events/group.ts)、[relate.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/events/relate.ts)、[grouping_decisions 迁移](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/database/migrations/0006_embeddings.sql#L1-L25)。新闻“同一事件”与论文“同一项学术工作”不是同一种身份关系；二次模型复核也达不到 PaperRadar 的自动合并条件。

## 3. 分层呈现：先有持久化事实，再有读者视图

**AIHOT 事实。** 它以 `articles`/`analyses`/人工覆盖为输入，构建 `publications` 读取层，网页、RSS、API、MCP 和报告读同一层；重建该层不再调模型，用户打开页面也不调模型：[architecture.md](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/docs/architecture.md)、[publish.ts §1–15、§144–160](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/publication/publish.ts#L1-L15)。AIHOT 的日报先选结构化候选，并按事实去重及栏目组织，再由模型写导语：[compose.ts §49–117、§136–177](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/reports/compose.ts#L49-L177)。

**对 PaperRadar：借鉴投影边界。** 本项目已规定 SQLite 为唯一业务事实源、Markdown 为只读投影、生成报告不调用模型；见 [ADR 0018](../docs/adr/0018-keep-v1-markdown-reports-read-only.md) 和 `intent/draft.md` 阶段 H。实际增量是在实现报告时设计一个**校准可见性过滤后的读取接口**，由日报、`paper show`、`trace`、复核队列共用。先在数据库固定 report run/entry、稳定编号、首次发布键与等待队列，再渲染 Markdown。用固定数据测试五项总上限、三项分析上限、已发布 pending 不重现、后来完成分析可重现、空日报区别健康与故障。不要为此引入 AIHOT 的 Web/API/MCP 或持久化 `publications` 副本；V1 一个轻量读取服务或查询层即可。

**分层内容可借鉴的呈现方式。** AIHOT 对近门槛资料输出较完整中文说明，对其余资料输出短摘要，并在报告中设栏目与简讯：[selection.md §1](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/docs/selection.md)、[analyze.ts §339–355](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/analyze.ts#L339-L355)。PaperRadar 已定义待评、揭晓、普通日报，以及摘要速览、全文受阻、精读分析层次。实现时应让一条报告占位与用户下一步动作匹配：`pending` 显示需判断什么，受阻项说明障碍和补救，精读项只展示证据支持的结论。AIHOT 的分栏数量和“差一点入选也写”的门槛不适用；V1 保持五项注意力上限。

## 4. LLM 分析与校准：借鉴错例分析，遵守本项目硬门槛

**AIHOT 事实。** 宽召回预筛只阻断明确无关的 `BLOCK`，`UNKNOWN` 继续评分；对于进入的资料，同一评分提示词独立调用两次，按来源等级门槛和两次分数之和决定精选。模型输出经 Zod Schema 解析，后续由代码计算入选；评分、结构抽取、写作有各自的步骤：[prefilter.md](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/industry/prompts/prefilter.md)、[analyze.ts §45–71、§194–240、§339–402](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/analyze.ts)、[selection.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/industry/selection.ts)。提示词按所引用文件内容生成哈希版本：[prompts.ts §27–55](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/prompts.ts#L27-L55)。

**对 PaperRadar：借鉴步骤拆分，不移植评分制。** 本项目已有研究边界判断、摘要层价值预测、条件式复用升级和确定性建议规则；只有结构化 artifact 合法且业务规则通过才可使用。AIHOT 的 `UNKNOWN` 宽放思路适合检查误杀，但 PaperRadar 不能让缺题名或摘要的记录进入 Screening；`metadata_unobtainable` 和疑似截断摘要各有既定路径。也不要将 AIHOT 的 0–100 注意力分数、来源等级门槛、重复评分平均或自由标签移入本项目。PaperRadar 保持研究价值与复用可行性两项并列评价，Screening 不读期刊信誉；见 [ADR 0013](../docs/adr/0013-do-not-compute-a-composite-paper-rank.md)。

**AIHOT 的校准工具很有启发。** `eval-selection.ts` 从带 `caseId`、`benchmarkSplit`、`samplingStratum` 和人工 gold 的 JSONL 读取样本；用固定 seed 抽样，逐条计算 TP/FP/FN/TN、precision、recall、门槛扫描、错误原因、token 和耗时，再把结果导入 SelectBench：[selection.md §校准](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/docs/selection.md)、[eval-selection.ts §31–165](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/scripts/eval-selection.ts#L31-L165)、[SelectBench 数据表](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/database/migrations/0009_selectbench.sql)。尤其值得借鉴的是按来源或错误类型看 false negative，而不是只盯总准确率；选用留出集可帮助发现对已揭晓标签的过拟合。

**对 PaperRadar：需严格改造。** 本项目已有 10–20 篇预热、32 篇真实 Feed 正式校准、四刊最低数、最多五篇的冻结盲评批次、用户先于系统的揭晓顺序，以及精确率/防漏判/最小分母门禁。错例面板或离线评测可以展示按期刊、摘要截断、`pending` 原因、模型失败、复用升级触发等切片，但正式盲评样本不得按“难例”手挑；AIHOT 文档建议加入难例仅适合 PaperRadar 的**预热或额外诊断集**。正式揭晓前所有查询都须经统一可见性接口。对已揭晓标签调参后重算要标注非独立验证与可能的 `human_input_drift`；留出集若用于独立评价，必须独立于调参且不能暗中替代本项目门禁。见 [ADR 0002](../docs/adr/0002-calibrate-before-automatic-fulltext-reading.md)、[ADR 0019](../docs/adr/0019-allow-calibration-recalculation-on-revealed-labels.md)、`intent/draft.md` §4.6 与“十六、校准失败、重算与变更纪律”。

**必须保留版本与变更纪律。** AIHOT 文档写明“提示词变更只影响之后新资料，已判过的不重算”，模型后台切换也只影响新任务：[selection.md §一条资料怎么变成精选、§换模型](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/docs/selection.md)、[models.ts §1–52](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/models.ts#L1-L52)。PaperRadar 可以借鉴“内容哈希可追溯”，但版本化 Profile/Prompt/Topic/Contract 不可原地修改，阶段指纹只含语义输入；影响校准的变化先由用户附理由分级，`minor` 有限重算、`major` 关门禁。见 [ADR 0008](../docs/adr/0008-invalidate-artifacts-with-stage-specific-fingerprints.md)、[ADR 0020](../docs/adr/0020-let-the-user-classify-calibration-impacting-changes.md)。同样不能照搬 `models.ts` 中无效模型选择回退 `default` 的逻辑；V1 禁止未校准的 Provider fallback：[ADR 0004](../docs/adr/0004-do-not-fallback-to-an-uncalibrated-screening-model.md)。

## 5. 总结与证据：重用已验证的结构化事实

**AIHOT 事实。** 它在选入资料后分别生成读者摘要、推荐理由、结构化事实；反幻觉提示词禁止加入原文没有的数字、版本、功能和排他词：[analyze.ts §349–402](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/analyze.ts#L349-L402)、[rules-anti-hallucination.md](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/industry/prompts/rules-anti-hallucination.md)。日报的候选、栏目和去重由代码决定，但导语由另一次 LLM 调用生成：[compose.ts §99–177](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/reports/compose.ts#L99-L177)。

**对 PaperRadar：只借鉴写作约束，不借鉴报告时新生成结论。** Screening 的中文速览、Read 的中文分析可以采用“先说明对用户研究的实际意义，再列出依据与限制”的简洁结构，但原始论文题名、作者、摘要、evidence 仍保留来源语言。尤其需要确定性检验引用的 evidence ID 有效、位置可回溯、模型不得把不可用的表格/公式/图片当成证据。AIHOT 的提示词级反幻觉不能替代这个校验。普通 Markdown 日报应只读取已持久化的 Screening、Read 和运行事实；模型写导语会制造未入库的新判断，不符合本项目报告只读投影。AIHOT 的文章和事件页不提供论文级 evidence ID 链，不能直接作为精读证据设计。

## 6. 可靠性、成本和可观测性：可复制“事实账”，不要复制基础设施

**AIHOT 事实。** 付费请求先以稳定逻辑键建立 receipt 和 attempt，再发请求；结果先入库后供业务写入复用。并发预算按服务串行检查，限制每分钟/小时/天请求。发送后超时可能已计费，因此标为 `unknown`，不会由普通调用立即重发；运维恢复逻辑可自动放行一次，之后仍未知则等待人工处理，故这不是“恰好一次付费”保证。接收成功而输出不可用可以标记失败再试：[receipts.ts §1–8、§69–184、§199–215](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/providers/receipts.ts)。文章分析以输入 revision 为检查条件；旧输入算完后保留分析历史，但不覆盖当前状态：[analyze.ts §415–454](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/analyze.ts#L415-L454)。

**对 PaperRadar：借鉴抽象，但遵守数据保留限制。** V1 已规定阶段输入指纹、有限两次模型尝试、单篇失败隔离、用量/成本摘要。可在 SQLite 保存 provider attempt 的任务 ID、阶段、指纹摘要、模型与配置版本、请求状态、token、耗时、错误类别和必要回执，复用已持久化的成功结果以减少重复付费；超时后的“结果未知”与“明确拒绝”要分开，未知结果可能需要受控重发。**模型原始成功响应须永久保留**，这是 [ADR 0017](../docs/adr/0017-retain-only-source-and-analysis-bearing-artifacts.md) 与 `intent/draft.md` §4.5 的既定要求；模型失败响应只保存足够诊断的结构化执行事实，不把秘密或正文写进日志。另据 [ADR 0009](../docs/adr/0009-retain-only-material-provider-responses.md)，普通外部 HTTP 来源响应只有贡献元数据、参考文献或冲突证据时才形成不可变来源快照，304、限流和失败页面不永久复制响应体。AIHOT 对所有付费请求先存完整原始响应的统一做法，需要按这三类数据分别适配。成本安全阀可先用 V1 已定的次数和工作量限制；在真实用量取得后再按规格配置月度金额上限，不引入独立预算后台。

**AIHOT 事实。** 运维告警区分当前读者受影响、当天需所有者处理、每日摘要；检测“很久没有新内容”、处理积压、日报未生成、未知回执、任务排队和备份超时，并给出影响及下一步：[alerts.ts §1–83、§136–174](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/operations/alerts.ts#L1-L174)。它还生成一周来源健康摘要，列失败或长期无产出的来源：[operations/reports.ts §9–43](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/operations/reports.ts#L9-L43)。日报固定取稿时间窗，保存窗口与生成版本；漏掉定时点后补刊，重新生成时保存旧修订：[compose.ts §120–177、§258–299](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/reports/compose.ts#L120-L299)。

**对 PaperRadar：高价值的具体增量。** V1 已有“运行摘要”、每周注意力可持续性指标和 NAS 恢复验收的目标。实现时可把“今日确实无新结果”“某刊 Feed 失败”“Screening/Read 积压”“报告未生成”做成互斥或并列的明确事实，让空日报不误导。每周按四刊列发现数、摘要成功/疑似截断/不可得数、最近成功抓取、失败次数，并连同 pending 净积压、accepted 未精读最老等待时间和决定覆盖率呈现。测试日界线、补刊、重复运行和写报告失败回滚；但本项目历史报告不可改写，新事实通过 supersede，不能照搬 AIHOT 更新当前 `reports` 行并存修订的模式。也无须 pg-boss、PostgreSQL、飞书告警和网站监控。

## 7. 实施建议：按 PaperRadar 现有阶段落地

以下是对已定规格的**执行与验收细化**，不是新增 V1 产品范围。当前仓库的可执行代码主要在配置/契约、SQLite 存储底座与 Screening 验证层；Feed 采集、真实模型流水线、校准、全文 Read 和日报仍以 `intent/draft.md` 作为待实现目标，不应把本文建议写成已上线能力。

| 优先级与阶段 | 可行动作 | 验收信号 | 与 AIHOT 的关系 |
| --- | --- | --- | --- |
| P0 · C，Feed 发现 | 为四刊保存每次抓取运行、成功 cursor、失败类别与来源观察；详情补全失败隔离。 | 冻结 RSS `200/304` 重放幂等；一刊失败时其余刊继续；失败不推进 cursor。 | [collect.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/sources/collect.ts#L64-L207) 的可恢复采集思路。 |
| P0 · D，预热与校准 | 保留每例输入版本、人工决定、系统建议及错误切片；按刊和摘要质量看 FP/FN、弃权、失败；正式批次维持机械选样与盲评隔离。 | 揭晓前任何报告/CLI 不泄漏结果；揭晓后能按切片解释失败；重算标明标签复用及输入漂移。 | 借 [eval-selection.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/scripts/eval-selection.ts#L84-L165) 的诊断形式，保留 PaperRadar 门禁。 |
| P1 · B/D/G，模型调用 | 建立有限必要的请求 attempt/结果账与 `unknown` 状态；业务提交前校验输入指纹，防过期写入。 | 已收到的相同请求结果可复用以减少重复付费；超时与明确拒绝可区分，未知结果有受控恢复路径；旧指纹结果不覆盖新事实。 | 改造 [receipts.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/providers/receipts.ts#L105-L184) 和 [analyze.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/editorial/analyze.ts#L415-L454)；模型成功响应按 ADR 0017 保留，外部来源响应按 ADR 0009 限缩保留。 |
| P1 · H/I，报告与运维 | 统一只读查询和校准可见性；固定报告成员；空日报附简短健康解释；每周来源及注意力摘要。 | 报告无需模型可重建；五项/三项上限；健康空与故障空不同；补刊不重复首次展示。 | 借 [publication](https://github.com/KKKKhazix/AIHOT/tree/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/publication)、[alerts.ts](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/packages/backend/src/operations/alerts.ts#L19-L83) 的边界与可诊断性。 |
| 不纳入 V1 | Web/API/MCP、向量归组、热点排序、社交信源、动态 Provider fallback、全文翻译、模型写日报导语。 | 不新增相应依赖、Schema 和处理路径。 | AIHOT 用于新闻站的能力与 PaperRadar V1 范围或不变量冲突。 |

## 查证局限与出处说明

本次克隆并阅读固定提交 `885b736` 的一手文件，使用源码行号而非依赖仓库 `main` 的浮动状态。重点核对了 `docs/selection.md`、`docs/architecture.md`、`docs/sources.md`，以及 `sources/collect.ts`、`content/materials.ts`、`editorial/analyze.ts`、`providers/receipts.ts`、`reports/compose.ts`、`publication/publish.ts`、事件归组、评测脚本、相关迁移和运维告警；未完整审计 UI、所有信源 Adapter 或全部测试，也未测量 AIHOT 文档宣称的线上延迟、精选效果或成本。AIHOT 自己称公开仓库是线上代码的快照，示范信源与真实运营信源不同：[README.md §说在前面](https://github.com/KKKKhazix/AIHOT/blob/885b736dc0fd3ef3d4c9c70af2bc3a981a99ff38/README.md)。因此本文只把可读源码与文档支持的机制当作参考，不把线上效果当成对 PaperRadar 的预测。
