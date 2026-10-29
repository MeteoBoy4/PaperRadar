# JGR 元数据生产补充

## 用途与范围

`JGRMetadata(database, data_root, http=...)` 为已有 JGR Feed 当前正式版本显式补充公开元数据。
网络适配器为共享 `SourceHTTPExecutor`；该服务不提供导入 CLI，不发送模型请求。

## 规则

- `enrich(paper_id, request_id=..., contact_email=...)` 冻结 Paper、当前版本、DOI、初始修订及来源时间。
  同 Paper/request_id 精确重放原请求，新的请求 ID 表达显式新取得。要求已有数据库 JGR 端点发现，
  不把任意其他期刊或人工 DOI 转为 JGR 生产请求。
- 有 DOI 时先经 doiRA 路由，只访问适用的 Crossref 或 DataCite，随后尝试当前 DOI 的 JGR
  出版者公开页面。完整或截断的首个摘要均不取消其他适用路线。单路线 404、403、429、5xx、
  身份不符、非法响应或空记录不会擦除其他来源。doiRA 未知及不支持机构明确受阻，不推断 DOI 不存在。
- 沿用 `audit-acquisition-v1`、`audit-http-v1`、`audit-abstract-v1` 和
  `audit-truncation-v1`；生产直接调用审计的 `inspect_source`、`parse_material` 与封闭类别判据。
  当前实现没有独立的元数据主摘要解析器。共享规则升级仍须追加审计解释及审查字段变化，不能覆盖历史审计。
- 主摘要仅取共享规则识别的 Abstract 区块，附加区块只保存存在及定位；候选、来源字段和规范事实
  经真实 `PaperFacts.submit` 仲裁。出版者/注册机构 URL 仅在有效、具有元数据候选的材料上作为来源字段提交。
  无主候选材料及错误页不作为永久来源正文保存。HTTP 和类别/附加区块安全投影保留在路线结果中。
- `MetadataResult` 提供规范题名、摘要存在/截断标记、可靠 URL、适用机构、各路线依据及
  `missing`。`minimum_complete` 要求题名、非空摘要、可靠 URL、适用路线已结算且机构路由明确；
  `nontruncated_complete` 额外要求摘要非疑似截断。普通 V1 截断可带标记，B 仍须通过自身完整主摘要判据。
- 无 DOI 时明确 `not_applicable_no_doi`，不构造外部目标。后到 DOI 或当前版本变化使旧请求
  标记 `current_version_changed`，不能以未尝试新适用路线的旧结果声称完整；新请求重新取得。
- `replay(request_key)`、`requests(paper_id)` 默认只返回安全摘要与路线事实；
  `content(request_key)` 显式展开规范主摘要及来源/时间/定位；
  `source_bytes(request_key, route)` 显式读取被保留的有效来源原字节。
- `resume(request_key, contact_email=...)` 从保存的 HTTP/解析结算继续。材料发布与事实提交分离；
  提交失败可遗留完整未引用制品，但未提交路线不声称成功。事实提交后回复中断重跑复用原观察，
  同请求并发写入以已提交路线为准，不重复创建版本或来源观察。
- `feed04_metadata` 追加迁移保存请求及路线的哈希绑定、制品和事实引用，保留旧非空档案。
  `validate_all()` 和备份闭包验证新事实；原根不可访问的隔离恢复仍可读取原字节与结果，
  恢复不激活配置、不执行任务。

## 错误与拒绝

参数或非 JGR 发现返回受控 `invalid_observation`；损坏请求、路线哈希、制品或来源引用返回
`corrupt_reference`。未知路由、缺项与未结算路线在结果中明确呈现。HTTP 安全、联系标识、
有界频率和退避沿用[fixture 审计契约](fixture-audit.md)，联系邮箱不进入保存的响应正文。

## 不提供／不证明

合成响应只证明工程接线；EXP-1、Audit/Source/B 的真实来源与 JGR 判据仍未验证。
最低结果不授予 Screening、校准、自动 Read 或 B 入口资格。7 天复查与完整资格调度由
[路线图 C](../roadmap.md#module-c) 承接，附加区块消费、四刊稳定阈值与条件降级保持既有裁决边界。

## 相关

依据：[规格 #114](https://github.com/MeteoBoy4/PaperRadar/issues/114)、
[#117](https://github.com/MeteoBoy4/PaperRadar/issues/117)、
[主规格 §4.3](../../intent/draft.md#43-元数据与来源仲裁)、
[论文事实](paper-facts.md)、[fixture 审计](fixture-audit.md)。

元数据路线、原因、注册机构适用性及缺项使用封闭类型；未知持久值在公共读面以
`corrupt_reference` 拒绝。SQL/制品错误使用 `metadata` 路径，独立于 Feed 检查路径。
