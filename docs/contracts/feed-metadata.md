# JGR 元数据生产补充

## 用途与范围

`paper_radar.feed_metadata.JGRMetadata(database, data_root, http=...)` 为已有 JGR Feed
当前正式版本显式补充公开元数据。网络适配器为共享 `SourceHTTPExecutor`；该服务不提供
导入 CLI、自动调度或模型调用。数据库须已显式升级到当前程序的唯一 head；服务不创建或迁移数据库。

## 规则

### 请求与来源

- `enrich(paper_id, request_id=..., contact_email=...)` 首次登记时冻结 Paper、当前版本、DOI、
  初始修订及 UTC `observed_at`。`request_id` 须为非纯空白的严格字符串，最多 128 字符，
  原样参与同 Paper 内的幂等身份；返回的 `request_key` 用于继续和查询。
  当前版本须为 `journal`，且该版本已有数据库中规范 JGR 端点的发现；其他期刊或仅人工 DOI
  不满足此前置。新请求 ID 表达显式新取得，不修改旧请求依据。
- 同 Paper/request_id 复用原请求：未完成时继续，完成后不再联网。`enrich` 和 `resume`
  即使重放完成请求也要求显式提供合法联系邮箱；只读入口不要求邮箱。
  各路线和提交的来源观察均使用首次请求的 `observed_at`，不是各 HTTP 响应实际完成时间。
- 有 DOI 时先经 doiRA 路由，只访问适用的 Crossref 或 DataCite，随后尝试当前 DOI 的 JGR
  出版者公开页面。完整或截断的首个摘要均不取消其他适用路线。单路线 404、403、429、5xx、
  身份不符、非法响应或空记录不会擦除其他来源。doiRA 未知及不支持机构明确受阻，不推断 DOI 不存在。
- 无 DOI 时 `registry_applicability=not_applicable_no_doi`，不构造外部目标或路线。
  有 DOI 时实际路线为 `doi_ra`、`publisher`，加适用的 `registry_crossref` 或
  `registry_datacite`；只使用公开 `http`，不使用授权会话或其他通道。
- 沿用 `audit-acquisition-v1`、`audit-http-v1`、`audit-abstract-v1` 和
  `audit-truncation-v1`。服务直接调用共享 `inspect_source`、`parse_material` 与封闭类别判据，
  不维护独立主摘要解析器。主摘要切分、规范化、截断信号及类别表由
  [fixture 审计契约](fixture-audit.md#摘要矩阵与显式运行105)定义；类别依据只保存到路线，
  本服务不据此授予 journal-article 或 Screening 资格。生产复用不覆盖旧审计解释；
  版本、追加解释及字段差异回查边界见[审计历史契约](fixture-audit.md#显式恢复历史回放与追加解释106)。
- 主摘要仅取共享规则识别的 Abstract 主区块，不拼接附加区块；附加区块只保存存在及定位。
  题名候选由共享解析器独立提取：出版者页面有合法 `citation_title` 时，即使没有可识别的
  Abstract 主容器，也可能贡献题名；路线 `acquired` 不表示已经取得摘要。
  共享解析器本身不证明生产结果与审计矩阵的候选接收及路线结论等价。
- 身份已核验且具有题名或摘要候选的有效材料作为 `source_snapshot` 保留，再经
  `PaperFacts.submit` 提交候选及该受控请求 URL；无候选材料、doiRA 响应体及错误页不永久保留。
  HTTP、类别及附加区块的安全投影仍保存在路线结果中。字段仲裁和原文保留规则由
  [论文事实契约](paper-facts.md#3-四类来源事实与发布)定义，不按摘要长度或截断标记改变优先级。

### 结果与只读回查

- `MetadataResult` 返回请求/Paper/版本/修订身份、规范题名、`abstract_present`、
  可空的 `suspected_truncated`、`source_url`、路线事实、`routes_settled`、
  `registry_applicability`、`current_version`、完整性及 `missing`。
  `registry_applicability` 为 `applicable`、`not_applicable_no_doi`、`agency_unknown` 或
  `agency_unsupported`；`applicable` 只说明已明确适用机构，不说明该机构的元数据取得成功。
- `routes_settled` 表示请求已固定结果修订，全部预期路线均已保存且材料所需的事实提交已完成；
  HTTP 失败也可结算，不表示每条路线成功。无 DOI 的预期路线集合为空，仍可结算。
  `minimum_complete` 要求当前版本/DOI 仍匹配、题名和非空摘要存在、截断状态已知、
  `source_url` 存在、路线已结算，且机构适用性不是未知或不支持。
  URL 来自该修订的规范字段；本服务不另行证明 URL 此刻可访问或来源长期可靠。
- `missing` 闭集为 `current_version_changed`、`no_title`、`no_abstract`、
  `unknown_truncation`、`no_source_url`、`routes_incomplete`、`agency_unknown`、
  `agency_unsupported`。`nontruncated_complete` 在最低完整之外要求摘要截断状态严格为
  `false`；`true` 可满足最低完整，未知状态不可。共享检测器给出 `false` 只表示未命中截断信号；
  结果也可引用既有人工或 Feed 摘要，完整性标志本身不证明科学意义上的摘要完整性。
- 请求完成后固定所引用的版本修订，不跟随后到字段修订。`replay(request_key)` 只读重建该修订，
  但 `current_version` 及相应缺项按查询时的当前版本/DOI 比较；后到 DOI 或当前版本变化使旧请求
  出现 `current_version_changed`，不再最低完整。重新取得须用新请求 ID，不能重绑旧请求。
- `replay(request_key)`、`requests(paper_id)` 返回题名和路线安全事实，不含摘要正文；
  请求列表按 `request_key` 排序，不是取得时间顺序。`content(request_key)` 显式展开该修订的
  规范摘要及获选来源类别、时间、定位；`source_bytes(request_key, route)` 显式读取该路线
  确实保留的原字节，不是规范摘要文本。候选投影只含文本哈希、长度、定位和截断信号等依据。

### 中断、并发与恢复

- `resume(request_key, contact_email=...)` 复用已保存的路线 HTTP/解析结算，继续缺少的路线
  或完成尚未提交的来源事实；已保存的失败路线也不重新联网，复查须新请求 ID。
  只有 HTTP 已返回并保存结算后才有该路线记录；更早中断或并发可导致重复请求，
  不保证 HTTP 恰好一次，不以制品存在追认路线成功。
- 材料发布与事实提交分离；提交失败可遗留完整未引用制品，但未提交路线不声称成功。
  事实提交后回复中断重跑复用原取得，同请求并发以已保存路线为依据，不重复创建版本或来源观察。
- 请求及路线保存哈希绑定、制品和取得事实引用；非空元数据请求禁止降级删除。
  `validate_all()` 只读核验请求、路线、保留字节重解析及事实引用；备份闭包调用同一核验。
  原根不可访问的隔离恢复仍可读取原字节和历史结果，不激活配置、不执行任务；
  备份/恢复的布局与安全边界见[备份契约](backup-restore.md)。

## 错误与拒绝

- 非法 `request_id`、非 JGR 当前版本发现或非 `journal` 版本返回
  `PaperError.invalid_observation`，路径分别为 `request_id`、`jgr_discovery`、`version_kind`。
  `source_bytes` 的路线不存在或未保留正文时同样返回 `invalid_observation`（`route`）。
  Paper/版本/修订查询与事实提交错误保留[论文事实原因类别](paper-facts.md#9-reason_catalog-v1)，
  不全部归并为参数错误。
- 邮箱缺失或非法由共享准入返回 `FixtureError.invalid_contact`（`contact_email`），
  发生在请求登记或继续之前；共享来源请求准入错误保留 `FixtureError.invalid_request`。
  HTTP 安全、联系标识、频率、退避与来源原因词表沿用
  [fixture 审计契约](fixture-audit.md#共同裁决与后续取得边界)。联系邮箱不持久化；
  响应回显本次邮箱或无法安全解码时以 `invalid_response` 拒绝保留，不改写原字节。
- 未找到请求、损坏请求/路线哈希、保留材料重解析不一致、制品或取得引用不符返回
  `PaperError.corrupt_reference`。元数据路线、原因、机构适用性及缺项使用封闭类型，
  未知持久值在公共读面以 `corrupt_reference` 拒绝。
  SQL/制品错误转换为 `corrupt_reference`，路径为 `metadata`，独立于 Feed 检查路径。
  数据库不存在、未初始化、旧版或未知 revision 等保留 `StorageError`，不会隐式创建或升级。
- 来源未知、受阻、失败、缺项及未结算在路线或结果中明确呈现，不解释为 DOI 不存在、
  自动 denied 或其他来源事实失效。

## 不提供／不证明

- 最低完整结果不授予 Screening、校准、自动 Read 或 B 入口资格，也不是
  `metadata_ready` / `metadata_unobtainable` 生命周期事实。跨组件登记前置由
  [组合契约](feed-pipeline.md)定义；普通 V1 的截断允许规则和 B 的更严入口判据见规格。
- 合成响应只证明工程接线，不证明真实 JGR 来源假设、字段稳定性、非截断主摘要或 live 就绪。
  真实审计与 JGR 判据由[Audit](../roadmap.md#module-audit)、
  [Source](../roadmap.md#module-source)及[B](../roadmap.md#module-b)承接。
- 不提供四刊生产元数据扩展、7 天复查或完整资格调度，责任见[C](../roadmap.md#module-c)。
  附加区块消费语义由[C](../roadmap.md#module-c)承接，四刊摘要稳定阈值与条件降级由
  [Abstract](../roadmap.md#module-abstract)承接；本契约不定义其未来行为。

## 相关

- 实现：[服务](../../src/paper_radar/feed_metadata/service.py)、
  [结果模型](../../src/paper_radar/feed_metadata/models.py)、
  [请求与路线存储](../../src/paper_radar/feed_metadata/repository.py)、
  [迁移 `feed04_metadata`](../../src/paper_radar/storage/migrations/versions/feed04_metadata.py)。
- 依据：[#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)、
  [#117](https://github.com/MeteoBoy4/PaperRadar/issues/117)、
  [主规格 §4.3](../../intent/draft.md#43-元数据与来源仲裁)、
  [§11 B](../../intent/draft.md#阶段-bjgr-feed-第一条真实纵向闭环)、
  [ADR-0009](../adr/0009-retain-only-material-provider-responses.md)、
  [ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)、
  [ADR-0032](../adr/0032-relax-paper-acquisition-without-evading-access-controls.md)、
  [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
- [历史工程证据及证明边界](../verification/issue-114-feed-delivery.md)。
