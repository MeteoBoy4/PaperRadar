# Feed 生产服务组合

## 用途与范围

`paper_radar.feed_pipeline.FeedPipeline(database, data_root, http=...)` 组合
JGR Feed 取得、当前版本最低元数据结果、语言依据及 value 任务登记。网络执行复用
`SourceHTTPExecutor`；身份、制品、元数据、语言及任务仍由各公共服务负责。
调用方提供已初始化并显式升级到当前 revision 的数据库与制品数据根；`prepare` 还要求
已登记的 JGR `feed_id`。Feed 准入、联系标识与 HTTP 安全边界见[Feed 取得](feed-ingestion.md)，
最低完整性的定义见[元数据契约](feed-metadata.md)，语言派生与任务规则见
[任务契约](screening-tasks.md#feed-原题名语言来源)。

## 规则

- `prepare(feed_id, request_id=..., contact_email=...) -> Preparation` 保留 Feed 检查，
  并为每个已关联 Paper 的 item 执行显式元数据补充。返回 `check_id` 和按原位次排列的
  `items`；每项包含 Paper、冲突或元数据请求引用，以及元数据完整性、缺项或条目原因。
  题名置空，不展开摘要正文。相同 Feed/request_id 复用原检查及各 Paper 的元数据请求，
  未完成部分沿用组件的继续机制，不以重放发起新一轮取得；当前版本变化仍可反映在缺项中。
  304 只产生检查结果，不新增 item 或隐式重跑旧论文。
- `Preparation` 不内嵌整次检查的 HTTP 状态或失败原因；须用
  `pipeline.feed.replay(check_id)` 回查。空 `items` 不能单独证明“没有新论文”，也可能是
  304 或检查失败。准备过程不是一个全链原子事务；组件异常会中断本次调用，
  已提交的检查、条目和元数据依据仍保留，恢复使用同一请求或组件的显式继续入口。
- `trace(paper_id)` 提供版本/修订身份、当前版本选择事件、逐字段获选候选引用、全部来源候选引用与仲裁原因、发现和取得事实、元数据路线/缺项、冲突、已保存语言观察及任务回执。候选引用只含来源、定位、解释版本和制品身份，不含字段值或原题名/摘要；元数据结果隐藏题名。论文候选与当前选择来自同一论文事实一致读视图；跨组件组合不承诺全库同一事务时点。该入口只读；正文与原字节通过既有显式读取接口取得。
- `register_value(raw_request, metadata_request_key=..., boundary_success_id=...)`
  接受既有严格 value 登记请求，不接受显式 `original_title_is_zh`。
  请求字段及严格类型沿用[任务登记](screening-tasks.md#8-a7-02-公共登记-api已交付)，
  但语言值由服务派生。元数据须最低完整且对应同 Paper 的当前版本/修订；boundary
  成功须属于同 Paper，且在请求 `snapshot_id` 下对当前输入适用，不要求成功最初使用
  同一个 snapshot ID。`in_scope` 和 `uncertain` 均可继续，`out_of_scope` 拒绝。
  生产入口拒绝 `executor_kind=test` 来源。
- `register_test_value(...)` 使用相同参数，明确用于既有任务的 test 来源工程路径。
  它与生产入口执行相同的 metadata/current/boundary/out_of_scope/语言检查，但允许
  `test` 成功作为前置，不赋予生产模型、B 实验入口或自动 Read 资格。两种登记均返回
  `ValueRegistration`：用途、任务回执、元数据请求、boundary 成功和冻结语言依据；
  `scope` 明确声明仅登记任务。`Preparation.scope` 同样不表示真实来源或执行资格通过。
- 当前任务成功接收只支持 `test` 来源，因此生产入口当前不能完成 value 登记。
  组合服务不生成 boundary 成功、不发送模型请求，不伪造生产成功来满足登记条件。
- 新登记在现有任务写事务中复核预读论文版本/修订及 boundary 指纹；任务、预算、
  语言依据和组合前置引用一起提交。事实并发变化返回 `facts_changed`，事务故障不留下
  没有前置依据的新组合预算。迁移 `feed05_composition` 只追加实际消费的组合引用。
- 精确组合请求（严格请求内容、元数据引用、boundary 引用、用途共同标识）重放原回执，
  即使后到来源引起语言歧义或当前论文变化，仍继承原冻结语言和预算。
  新请求继续执行当前前置检查。已有低层请求不能被补挂新组合依据冒充新的当前授权。
- 组合用途 `test`/`production` 不进入 Stage fingerprint 或 Frozen Contract，也不划分
  新的预算范围。组合入口使用任务服务的 `v1` 语言策略，不接受策略参数；语言派生、
  已有预算及 retry 的冻结/继承语义见[任务语言规则](screening-tasks.md#feed-原题名语言来源)。
- `validate_all()` 只读校验已保存组件事实及组合引用，不修复、不升级、不执行模型。
  [备份验证](backup-restore.md)包含该入口；组合引用损坏映射为备份
  `registration_invalid`。原根不可访问的隔离恢复仍可查询原材料、元数据、语言、
  旧预算和精确请求回执；恢复不激活配置或自动续跑任务。

## 错误与拒绝

`PipelineError.reason` 使用以下封闭类别，异常文本为原因代码加中文说明：

| 原因 | 拒绝条件 |
| --- | --- |
| `invalid_request` | 不是严格 dict、不是 value 阶段、snapshot ID 不是严格字符串或显式携带语言值；其他请求校验由任务服务执行 |
| `metadata_incomplete` | 元数据不属于请求 Paper，或最低结果存在缺项（含当前版本已变化） |
| `metadata_stale` | 最低完整的元数据所引用版本/修订与当前事实不同 |
| `boundary_missing` | 找不到所引用的同 Paper、当前适用 boundary 成功，或输出不是 boundary 类型 |
| `out_of_scope` | boundary 判断为超出研究边界 |
| `test_source` | 生产入口收到 test 执行来源 |
| `corrupt_reference` | 历史组合前置、boundary 指纹或冻结语言等引用核验不一致 |

组件受控错误（例如 `language_missing`、`language_ambiguous`、`facts_changed`、
`request_conflict`，以及组件自身的 `invalid_request`、`corrupt_reference`）继续保留
原异常类型和类别；缺库、旧库及存储错误也不统一包装为 `PipelineError`。新登记拒绝或
事务故障不授予组合登记资格；语言缺失/歧义的观察可依组件规则独立保留，不构成新预算。
HTTP、条目失败、元数据缺项及异常均不被解释成“无新论文”。

## 不提供／不证明

不提供真实导入 CLI、调度、模型调用或完整资格体系；最低元数据完整不等于非截断主
摘要、B 样本、Source 判据、校准或自动精读门禁通过。组合 `purpose=production` 也不
表示普通生产消费资格，不能替代实验根隔离或样本准入。

未提供能力的承接责任：[Audit](../roadmap.md#module-audit)／
[Source](../roadmap.md#module-source)负责真实来源判据，
[Pi](../roadmap.md#module-pi)／[Live](../roadmap.md#module-live)负责生产执行来源与 RPC，
[B](../roadmap.md#module-b)负责实验入口及纵向接线，
[C](../roadmap.md#module-c)负责四刊扩展与元数据生命周期，
[H](../roadmap.md#module-h)负责完整日常 CLI 与调度入口。
离线工程行为不证明真实 JGR 字段/entry 稳定性、语言来源约定或 live 就绪。

## 相关

- [Feed 取得](feed-ingestion.md)、[最低元数据](feed-metadata.md)、
  [论文事实](paper-facts.md)、[任务](screening-tasks.md)。
- [历史工程覆盖与证据边界](../verification/issue-114-feed-delivery.md)。
- 依据：[规格 §4.2–4.5](../../intent/draft.md#42-feed-抓取)、
  [§8.5](../../intent/draft.md#85-任务领取与幂等)、
  [#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)／
  [#119](https://github.com/MeteoBoy4/PaperRadar/issues/119)、
  [ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)、
  [ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)、
  [ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)、
  [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
