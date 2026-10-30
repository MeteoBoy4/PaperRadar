# JGR Feed 生产取得

## 用途与范围

`paper_radar.feed_ingestion.JGRFeed(database, data_root, http=...)` 提供显式调用的
JGR Feed 取得、逐条目论文事实登记、失败回查和故障继续服务。`database`、`data_root`
为 `Path`；数据库须已显式升级到随包当前 head，数据根须含其引用的制品。
服务不创建或迁移数据库。`http` 默认是共享 `SourceHTTPExecutor`，测试替换其 HTTP transport；
本服务不创建审计计划或审计成员。

## 规则

### Feed 身份与调用

- Feed URL/UUID 由 [`PaperFacts.register_feed`](paper-facts.md#4-feed-身份发现与回摆d3) 登记。
  本服务只接受已有 `feed_id`，数据库规范 URL 须等于共享声明中的 JGR eTOC 端点
  （[`sources/feeds.py`](../../src/paper_radar/sources/feeds.py)）；端点 query 保留。
  服务不自动登记 Feed，不批准其他订阅；端点声明也供语言归属使用，不在此定义语言策略。
- `check(feed_id, request_id=..., contact_email=...) -> FeedCheck` 以
  `(feed_id, request_id)` 幂等。`request_id` 是非全空白、至多 128 字符的字符串，原样保存。
  `contact_email` 每次 `check` 都须显式提供并通过共享联系标识校验，包括重放已完成检查时。
  新检查在 HTTP 前保存不可变请求与 UTC `checked_at`；此时间也是所有 item 的 `observed_at`，
  不因继续而刷新。有效整 Feed 发布后结算 HTTP，再逐 item 调用 `PaperFacts.submit`。
- 相同 Feed/request_id 复用原检查：已完成则直接返回，未完成则继续。
  `resume(check_id, contact_email=...) -> FeedCheck` 只补未结算的 HTTP 或 item；
  已结算失败也是完成检查，再次取得须使用新 request_id。
  HTTP 无结算时只读显示 `outcome_unknown`，显式继续可能重新发送 HTTP，不保证外部请求恰好一次。
- `replay(check_id) -> FeedCheck`、`view(feed_id) -> FeedView` 只读、不联网。
  `FeedCheck` 返回检查/Feed/请求身份、固定来源时间、请求与 HTTP 事实、条件值、状态码、
  制品/前次检查引用、`content_decoding`、parser 身份、逐 item 结果和 `complete`。
  `FeedView.checks` 按登记事件顺序包含全部检查；`last_successful_check` 和条件值取最后一个
  `reason=acquired` 检查，HTTP 成功不表示全部 item 成功或已经结算。
  `complete=true` 表示 HTTP 失败已结算、304 已结算，或有效 200 的全部 item 已结算，
  不表示新增论文、来源达标或业务资格通过。

### HTTP 与条件取得

- 请求固定为 JGR/Feed、HTTP、`access_basis=open`、`credential_class=null`，使用共享
  `audit-acquisition-v1`、`audit-http-v1`；联系标识、无环境代理、逐跳白名单、每主机频率、
  超时、8 MiB 解压后上限及有界重试均沿用[共享 HTTP 边界](fixture-audit.md#共同裁决与后续取得边界)。
  连接/重定向/重试计数、退避和解码的详细规则见[HTTP 取得规则](fixture-audit.md#103-已交付的取得边界)，
  不沿用审计计划锁或审计继续资格。失败、受阻目标、非法 Feed 不保留错误页。
- 安全 ETag/Last-Modified 独立保存在生产检查中，不扩展 `HTTPFacts` 序列化身份。
  条件值至多 512 个可打印 ASCII 字符且不含 `@`；不安全响应值舍弃。
  新检查从此前最后一个带保留制品的检查构造条件请求，绑定其检查和制品引用。
  304 引用原制品并继承 `content_decoding`，只推进检查成功事实，不创建 item 或发现，
  也不继续前次检查尚未结算的 item；后者须按原 check_id 显式继续。

### 条目解释与论文登记

- parser 身份为 `jgr-feed-parser-v1`、整数版本 1。生产遍历全部条目，不沿用审计前 50 条
  上限；身份、顺序、类别解释复用共享 parser。RSS 只取唯一 channel 的直接 item，Atom
  只取根级 entry，RDF 只取根级 item 并遵守有效 RDF Seq 顺序。
  缺失或多个 RSS channel、非法 XML、DOCTYPE/ENTITY 等不安全 Feed 被拒绝。
- 原 item 使用 XML 解析器给出的物理字节范围切片，保留原起止标签、实体、命名空间前缀与
  排版，不重序列化或注入根命名空间。候选、字段和物理范围按同一根级集合定位；
  description 内嵌 item/entry 与其他容器不能改变后续论文身份。
  `item_bytes(check_id, position) -> bytes` 显式读取原字节，position 为从 1 开始的严格整数，
  按检查条目顺序定位；304 也可从所引用原 Feed 读取，但不生成本次 item 结果。
- 上游 entry ID 原样沿用，不构造替代 ID；缺失或未通过 entry ID 输入校验时单列
  `missing_entry_id`。`FeedItem` 返回 position、entry_id、规范 DOI、原类别及 reason/result。
  Wiley category/prism:section 原样公开，不按子类型过滤，也不凭 Feed 位置证明 journal-article。
- 题名、主摘要及截断标记共享 `audit-abstract-v1`、`audit-truncation-v1`，详细文本规则见
  [主区块与类别边界](fixture-audit.md#共同裁决与后续取得边界)；字段 locator 使用 item 相对路径，
  防止整 Feed 排序变化制造异解释。生产提交的字段限题名、摘要及可接受的落地页 source_url；
  不将作者、日期、卷期页码或附加摘要区块写为字段候选。
- 显式 DOI 沿用[DOI 规则 v1](paper-facts.md#21-doi-规则-v1d2)。独立落地页提取仅接受
  `https://agupubs.onlinelibrary.wiley.com` 上 `/doi/`、`/doi/abs/`、`/doi/full/`、
  `/doi/epdf/` 的合法 DOI path，拒绝 userinfo、非默认端口及 query/fragment；不从 query
  构造 DOI。与条目其他 DOI 断言不符时记 `conflicting_dois`，不提交论文事实。
- 每个可提交条目使用 `version_kind=journal`、`parser_version=1`、
  `interpretation=complete`、`payload_scope=single_item` 及原 item 字节。
  无 DOI 连续身份、唯一补 DOI、跨 Feed 同 DOI、回摆、完整解释/全空保护和来源仲裁由
  [论文事实](paper-facts.md) 唯一定义。强冲突返回 `conflict_id`，仍拒绝成功业务事实；
  冲突原文与断言通过[冲突读面](paper-facts.md#强身份冲突证据公共服务)回查。
  单条目身份或解析拒绝保留结果，其他条目继续；数据库或引用故障停止本次继续，不伪造 item 终态。

### 持久化与恢复

- 迁移 [`feed03_feed_acquisition`](../../src/paper_radar/storage/migrations/versions/feed03_feed_acquisition.py)
  定义检查与逐 item 结算，服务仍要求随包当前 head，并非只要求此历史 revision。
  制品发布、HTTP 结算、论文事实写入、item 结果写入是独立边界。
  论文已提交而 item 结果未写入时，继续复用原论文事实回执补齐，不重复论文身份或取得事实；
  本服务不操作模型预算。完整未引用制品允许存在，不代表检查已结算。
- `validate_all()` 只读校验检查身份、条件引用、来源字节、解析条目及论文取得/冲突引用。
  [备份验证与隔离恢复](backup-restore.md)经组合服务调用本校验；恢复后查询、原字节读取与
  已完成检查的幂等重放不依赖原根目录、不联网。未完成检查的继续仍可能需要 HTTP。

## 错误与拒绝

- 未知或未批准 Feed、非法 request_id、item_bytes 的非法/越界 position 抛
  `PaperError(invalid_observation)`，路径分别为 `feed_id`、`request_id`、`position`。
  未知 check_id、损坏材料或引用抛 `PaperError(corrupt_reference)`；SQLAlchemy/制品错误
  转为该原因（通常路径 `feed_check`）。论文提交返回 `database_busy` 或 `corrupt_reference`
  时停止并抛相同原因，路径 `feed_item_commit`，保留未完成检查供排障后显式继续。
- 联系标识缺失/非法抛 `FixtureError(invalid_contact)`，路径 `contact_email`，不创建新检查。
  数据库缺失、未初始化、旧/未知 revision 等沿用 `StorageError`，不自动创建或升级。
- 检查原因与逐 item 原因分列。检查沿用共享 `SourceReason`，本路径的 HTTP 结果包括
  `acquired`、`not_found`、`rate_limited`、`transient_error`、`invalid_response`、
  `access_blocked_403`、`deferred_retry_after`、`disallowed_destination`、`disallowed_scheme`；
  HTTP 未结算为 `outcome_unknown`，有效 HTTP 200 但 Feed 不合法为 `invalid_feed`。
  此时 `http.reason` 仍可为 `acquired`，不能仅凭 HTTP 成功判定检查成功。
- item 解析原因闭集为 `missing_entry_id`、`invalid_doi`、`conflicting_dois`、`invalid_item`，
  此类结果没有论文回执；已提交条目的 `result` 是 `WriteResult`，保留论文事实的原 reason、
  成功/无新增材料/拒绝状态及引用，不把 `identity_conflict` 或 `requires_merge` 混为解析错误。
  这些结果都不等于“没有新论文”，失败也不授权绕过访问控制或改绑身份。
- 普通检查输出不展开题名、摘要、原材料或联系邮箱；包含 entry ID、DOI 和原类别，
  不承诺任意上游文本的全面脱敏。题名/摘要值和原始材料需显式读面取得。

## 不提供／不证明

不提供真实导入 CLI、自动调度、其他三刊生产取得或独立的连续失败计数/最近错误健康投影；
检查历史可回查，但不是完整 Feed 健康与日常调度体系，相关补齐责任见[路线图 C](../roadmap.md#module-c)。
不发送模型请求，不授予 B 入口、Screening、校准或自动 Read 资格；组合登记边界见
[Feed 生产服务组合](feed-pipeline.md)，真实纵向入口由[路线图 B](../roadmap.md#module-b)承接。
合成材料只证明工程行为，不证明 live 可用；guid、Wiley 参数、entry ID 稳定性及真实主摘要
可靠性由[Audit](../roadmap.md#module-audit)、[Source](../roadmap.md#module-source)与
[B](../roadmap.md#module-b)核实，四刊扩展由[C](../roadmap.md#module-c)承接。

## 相关

- [论文事实](paper-facts.md)、[fixture 与摘要审计](fixture-audit.md)、
  [最低元数据](feed-metadata.md)、[组合服务](feed-pipeline.md)、[备份恢复](backup-restore.md)。
- 实现：[`feed_ingestion`](../../src/paper_radar/feed_ingestion/)、
  [`sources/feed_xml.py`](../../src/paper_radar/sources/feed_xml.py)。
- 固定合成材料的证明边界：[生产 parser 规则证据](../verification/feed-parser-v1.md)。
- 依据：[规格 §4.2–4.4](../../intent/draft.md#42-feed-抓取)、
  [#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)、
  [#116](https://github.com/MeteoBoy4/PaperRadar/issues/116)、
  [ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)、
  [ADR-0032](../adr/0032-relax-paper-acquisition-without-evading-access-controls.md)、
  [ADR-0033](../adr/0033-classify-journal-articles-from-explicit-source-types.md)、
  [ADR-0034](../adr/0034-separate-fixture-declarations-and-acquisition-audits.md)。
