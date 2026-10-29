# JGR Feed 生产取得

## 用途与范围

`paper_radar.feed_ingestion.JGRFeed(database, data_root, http=...)` 提供显式调用的
JGR Feed 取得、逐条目论文事实登记、失败回查和故障恢复服务。`http` 为共享
`SourceHTTPExecutor`，测试只替换它的 HTTP transport。

## 规则

- Feed URL/UUID 由 `PaperFacts.register_feed` 登记。生产服务接受已有 `feed_id`，
  仅支持与共享获取策略中 JGR eTOC 端点完全对齐的数据库规范 URL；端点 query 保留。
  服务不自动登记 Feed，不批准其他订阅。端点与语言映射共用下层唯一声明，核心不依赖审计服务。
- `check(feed_id, request_id=..., contact_email=...)` 保存不可变请求身份和来源时间，
  发布有效整 Feed 后追加 HTTP 结算，再逐 item 调用 `PaperFacts.submit`。
  相同 Feed/request_id 重放原检查；检查已经完成时不再发送 HTTP。
- `replay(check_id)` 只读；`view(feed_id)` 提供全部检查、最后成功检查时间和条件状态。
  `resume(check_id, contact_email=...)` 继续未完成检查或未结算 item。HTTP 未结算如实显示
  `outcome_unknown`，有明确失败结算则需新 request_id 才产生新检查。
- 使用共享 `audit-acquisition-v1`、`audit-http-v1` 规则：联系标识、无环境代理、
  白名单逐跳检查、每主机频率、超时、8 MiB 解压上限及有界重试继续生效。
  403/404、429/5xx、受阻目标及非法 Feed 保存受控失败，不保存错误页。
- 安全 ETag/Last-Modified 作为独立生产事实保存，不扩展旧审计 `HTTPFacts` 序列化身份。
  条件值限 512 ASCII 字符且无控制字符或 `@`。条件请求绑定前次已保留材料；
  304 引用原制品，继承解码依据，只推进检查成功事实，不创建 item 或发现。
- 原 item 使用 XML 解析器提供的根级条目字节位置切片，包含原起止标签、实体、命名空间前缀与
  排版；不重序列化、不注入根命名空间。候选、字段提取和物理范围均按同一根级集合定位，
  description 内嵌 item/entry 与其他容器不能改变后续论文身份。`item_bytes(check_id, position)` 显式返回原字节。
  上游 entry ID 原样沿用；缺失 ID 单列 `missing_entry_id`，不构造替代 ID。
- 生产完整遍历条目，不沿用审计选样的前 50 条上限。RSS、Atom、RDF 的身份/顺序/类别
  解释复用审计权威。Wiley category/prism:section 原值公开，不按子类型过滤。
- 初始生产 parser 身份为 `jgr-feed-parser-v1`、整数版本 1；主摘要及截断规则共享
  `audit-abstract-v1`、`audit-truncation-v1`。主摘要与题名通过同一审计解析器取得，
  字段定位使用 item 相对路径，防止整 Feed 排序变化制造异解释。
  DOI 规范化边界不变；独立的落地页提取只接受受控 Wiley HTTPS path，query 不生成 DOI。
- 无 DOI 连续身份、唯一补 DOI、跨 Feed 同 DOI、回摆、完整高版本解释/全空保护和
  来源仲裁由 PaperFacts 权威执行。强冲突保存 `conflict_id`，仍拒绝成功业务事实。
  单条目身份或解析错误保留结果，其他条目继续；数据库故障保留未完成检查供显式继续。
- 追加迁移 `feed03_feed_acquisition` 引入检查与逐 item 结算；制品发布、论文事实写入、
  item 结果写入是独立边界。结果写入失败后重跑通过原论文事实回执补齐，不重复预算或身份。
  完整未引用制品允许存在，不代表检查已结算。
- `validate_all()` 校验检查身份、条件引用、来源字节、解析结果和论文取得/冲突引用。
  备份验证调用本服务；隔离恢复后查询、原字节及幂等重放不依赖原根目录。

## 错误与拒绝

未知或未批准 Feed 身份返回 `invalid_observation`；损坏材料、引用或无法提交的 item
返回 `corrupt_reference`。检查有独立 HTTP 原因（例如 `rate_limited`、`not_found`、
`access_blocked_403`、`disallowed_destination`）及 `invalid_feed`；它们不等于没有新论文。
普通检查输出不展开题名、摘要、原材料或联系邮箱，原文需显式读面取得。

## 不提供／不证明

不提供真实导入 CLI、自动调度或模型请求，不授予 B 入口、Screening、校准或自动 Read
资格。合成材料只证明工程行为；guid、Wiley 参数、entry ID 稳定性及真实主摘要可靠性
仍由[路线图 EXP-1/B](../roadmap.md#module-feed)核实。

## 相关

- [论文事实](paper-facts.md)、[fixture 与摘要审计](fixture-audit.md)
- parser 固定回归与字段说明：[生产 parser 规则证据](../verification/feed-parser-v1.md)
- 依据：规格 §4.2–4.4、GitHub #114/#116、ADR-0030/0033/0034。
