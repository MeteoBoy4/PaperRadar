# Feed 生产服务组合

## 用途与范围

`paper_radar.feed_pipeline.FeedPipeline(database, data_root, http=...)` 组合
JGR Feed 取得、当前版本最低元数据结果、语言依据及 value 任务登记。网络执行复用
`SourceHTTPExecutor`；身份、制品、元数据、语言及任务仍由各公共服务负责。

## 规则

- `prepare(feed_id, request_id=..., contact_email=...)` 保留 Feed 检查，并为每个可安全
  关联的 Paper 执行显式元数据补充。返回检查 ID、逐 item Paper/冲突/元数据请求引用、
  完整性和缺项；默认隐藏原题名及摘要正文。重复请求复用原检查和元数据请求。
  304 只产生检查结果，不新增 item 或隐式重跑旧论文。
- `trace(paper_id)` 提供版本/修订身份、元数据路线/候选摘要、冲突、已保存语言观察与
  任务回执。该入口只读；原字节通过既有 Feed/元数据/冲突的显式读取接口取得。
- `register_value(raw_request, metadata_request_key=..., boundary_success_id=...)`
  接受既有严格 value 登记请求，不接受显式 `original_title_is_zh`。
  元数据须最低完整且对应当前版本/修订；boundary 成功须来自同 Paper、当前输入及
  请求 snapshot，且不为 `out_of_scope`。生产入口拒绝 `test` 来源。
- `register_test_value(...)` 明确用于既有任务的 test 来源工程路径。它与生产入口执行
  相同的 metadata/current/boundary/out_of_scope/语言检查，只允许使用既有 test 执行事实
  验证登记工程，不赋予生产模型、B 实验入口或自动 Read 资格。
- 当前成功任务服务只交付 test 来源，因此生产登记仍需 B 后续真实 RPC 前置。
  组合服务不生成 boundary 成功、不发送模型请求，不伪造生产成功来满足登记条件。
- 新登记在现有任务写事务中复核预读论文版本/修订及 boundary 指纹；任务、预算、
  语言依据和组合前置引用一起提交。事实并发变化返回 `facts_changed`，事务故障不留下
  没有前置依据的新组合预算。迁移 `feed05_composition` 只追加实际消费的组合引用。
- 精确组合请求（严格请求内容、元数据引用、boundary 引用、用途共同标识）重放原回执，
  即使后到来源引起语言歧义或当前论文变化，仍继承原冻结语言和预算。
  新请求继续执行当前前置检查。已有低层请求不能被补挂新组合依据冒充新的当前授权。
- 组合用途 `test`/`production` 不进入 Stage fingerprint 或 Frozen Contract。
  语言策略/来源保留既有 ADR-0035 语义，retry 由原任务服务沿用冻结预算。
- `validate_all()` 校验已保存组件事实和组合引用；备份验证包含该入口。
  原根不可访问的隔离恢复仍可查询原材料、元数据、语言、旧预算和精确请求回执。

## 错误与拒绝

组合原因使用中文说明：`invalid_request`、`metadata_incomplete`、`metadata_stale`、
`boundary_missing`、`out_of_scope`、`test_source`、`corrupt_reference`。
组件受控错误（例如 `language_missing`、`language_ambiguous`、`facts_changed`、
`request_conflict`）继续保留原类别，不被解释成“无新论文”。

## 不提供／不证明

不提供真实导入 CLI、调度、模型调用或完整资格体系；完整最低元数据结果不等于 B
样本、Source 判据、校准或自动精读门禁通过。真实 JGR 来源假设、B 隔离入口与真实
RPC 由[路线图 B](../roadmap.md#module-b)承接；四刊扩展由 C 承接。

## 相关

- [Feed 取得](feed-ingestion.md)、[最低元数据](feed-metadata.md)、
  [论文事实](paper-facts.md)、[任务](screening-tasks.md)。
- [交付覆盖与证据边界](../verification/issue-114-feed-delivery.md)。
- 依据：GitHub #114/#119、ADR-0030/0035/0036。
