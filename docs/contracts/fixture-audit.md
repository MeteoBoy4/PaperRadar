# Fixture 注册与摘要审计 Contract v1

本 Contract 落实 #100 评论裁决；权威注册格式为 `paper_radar.fixture_audit.models.FixtureDeclaration`，不加入 `CONTRACT_NAMES` 或五份 Frozen Contract。#101 交付声明登记、只读历史与基本恢复；PDF 取得、路线执行、选样、矩阵及独立 A10 验收按 #102–#108 后续交付。当前不代表真实来源、Docling、模型或完整阶段 A 通过。

## 声明与身份

声明唯一目录是仓库 `fixtures/a10/`，历史种子唯一文件 `historical-v1.json`。JSON 原字节先校验，再以 `(declaration_key, declared_version)` 不可变登记；同键同字节幂等，空白/键序/换行变化同样属于同键异字节。修正必须新版本，数据库保留原字节和独立 SHA-256。未知字段/格式/版本拒绝，安全错误仅给字段路径、原因和补救，不回显原输入。

逻辑样本身份为 `(purpose, journal, key)`，key 必须显式给定，DOI/handle/数组下标/路径不能代替。四用途 `feed/abstract_audit/references/pdf`，三种依据 `historical_declaration/synthetic/acquired` 分开。引用及声明原字节在短事务内原子登记。初次登记选择当前项，后续只按显式 `replaces` 及非空原因替换同逻辑样本；禁止悬空、跨用途/期刊/key、分叉与循环。时间和版本字符串排序不参与选择。list 默认当前项，show 可查任何旧记录，history 投影保留完整历史。check 只对源文件与登记字节比较，分别报告 source_missing / unregistered / drift / byte_verified，不切换选择。

参考文献期望保留出版者/Crossref 计数与历史风险；PDF 声明保留 DOI/handle、候选、版式与已知失败，不填假哈希、假许可或 parser 结果。历史说明与 2026-10-25 只读预检注记分开。acquired 证据只能由实际取得入口核验；文件声明自报哈希或尚未完成审计引用不能升级成真实证据。feed/abstract_audit 的 acquired 注册只引用完成计划、汇总哈希与 Feed 快照，不复制审计权威事实。

## 共同裁决与后续取得边界

类别依据闭集（ADR-0033）：Crossref `message.type=journal-article`；DataCite `types.resourceTypeGeneral=JournalArticle`；《大气科学》Feed `dc:type=article` 与文章页 `dc.type=论文`。机构其他明确类型为非 journal-article，平台表外值/缺字段为未知，明确判定矛盾为冲突，分别计数。Wiley `category/prism:section` 原值仅保存；题名、DOI 前缀、URL、Feed 位置与 og:type 不作类别依据。

doiRA `https://doi.org/doiRA/{doi}` 是路由，不是元数据提供方：Crossref/DataCite 只走对应机构，其他 RA 为 agency_unsupported，失败/404 为 agency_unknown。Feed 和出版者均只取主 Abstract/摘要；dqkx 取 abstract-cn，abstract-en/Significance/PLS/Key Points 只记录存在与定位。Wiley Abstract 前置段及 dqkx p 外引文尾行不拼入摘要。切分、实体解码、去标记、连接规则统一版本化。

策略 v1、通道枚举 v1 冻结进计划与请求身份，汇总按 `(member, route, acquisition_strategy_version, channel)` 分开。通道为 http/browser_render/official_api/repository；A10 只注册 http，credential_class 恒空。未注册为 channel_not_installed 终态，与可执行未执行的 not_attempted 分列，均不算失败。策略变化必须新计划，resume 拒绝不同代码/规则/策略版本；产品代码不依赖验收脚本。

| 来源 | 固定端点或出版者 URL 规则 | 允许主机与路径 |
| --- | --- | --- |
| AIES Feed | `https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml` | journals.ametsoc.org 上该精确路径 |
| JGR Feed | `https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss` | agupubs.onlinelibrary.wiley.com 上该精确路径/query |
| QJRMS Feed | `https://rmets.onlinelibrary.wiley.com/feed/1477870x/most-recent` | rmets.onlinelibrary.wiley.com 上该精确路径 |
| dqkx Feed | `https://www.iapjournals.ac.cn/dqkx/rss/current.xml` | www.iapjournals.ac.cn 上该精确路径，不允许 latest.xml |
| AIES 出版者 | Feed link，去 query/fragment 后核查 | journals.ametsoc.org 的 `/view/journals/aies/` 下 `.xml`，不从路径推断 DOI |
| JGR 出版者 | DOI 模板 `https://agupubs.onlinelibrary.wiley.com/doi/{doi}` | 该主机 `/doi/10.1029/`，无 query/fragment |
| QJRMS 出版者 | DOI 模板 `https://rmets.onlinelibrary.wiley.com/doi/{doi}` | 该主机 `/doi/10.1002/`，无 query/fragment |
| dqkx 出版者 | DOI 模板 `https://www.iapjournals.ac.cn/dqkx/article/doi/{doi}` | 该主机 `/dqkx/article/doi/10.3878/`，无 query/fragment |
| DOI 路由 | `https://doi.org/doiRA/{doi}` | doi.org `/doiRA/` |
| Crossref | `https://api.crossref.org/works/{doi}` | api.crossref.org `/works/` |
| DataCite | `https://api.datacite.org/dois/{doi}` | api.datacite.org `/dois/` |

只接受 HTTPS、无 userinfo 和隐含凭据；http 不静默升级，逐跳检查白名单，登录/SSO/挑战页主机为受阻。只用 httpx，关闭环境继承，不发送/复用 Cookie，代理显式提供；按主机至少间隔 1 秒，8 MiB 解压后流式上限，连接 10 秒。每路线执行最多两轮（首次加一次重试）；仅连接错误、429、5xx 触发重试。每轮连接/重定向/流式读取共用单调时钟 30 秒总期限，重定向不占重试额度且最多五跳，所有物理 HTTP 请求逐次计数；Retry-After 超过 5 秒为 deferred_retry_after，等待显式 resume。原字节是 Content-Encoding 解压后、charset 解码前的字节，Content-Type/charset/实际解码另存。HTTP 条件头 `if_none_match/if_modified_since` 可空，304 必须引用已保留响应，不作新字节成功。

审计锁为数据库同目录 `.paper-radar-audit-locks/{plan_id}.lock`，在制品根和备份清单外；非阻塞 flock，不 unlink、不写 PID，不在数据库写事务中等待。读取不取锁。联系邮箱每次 live 显式提供，仅当次 UA 使用，不持久化、读取个人环境或猜测；缺失/非法时连计划也不建立。不联网的帮助/查询不能要求邮箱。

原因沿用 §8.4，审计补充：not_applicable_no_doi、agency_unknown、agency_unsupported、identity_mismatch、unrecognized_page_shape、record_without_abstract、outcome_unknown、deferred_retry_after、not_attempted、disallowed_destination、disallowed_scheme、channel_not_installed。只有有效 Feed 或身份已核验且贡献身份/字段的响应进入 source_snapshot，身份正确但无摘要的页面也保留；失败/限流/挑战/身份未核验 200 仅保留结构化事实。

## CLI 与持久化

`fixture register FILE --database DB --data-root ROOT` 显式写登记，不迁移；`fixture check FILE --database DB` 只读比对；`fixture list --database DB [--history]` 与 `fixture show RECORD_ID --database DB` 只读数据库历史，源文件可不存在。共同支持 --json；帮助为中文并说明副作用、配额及示例，无网络/数据库/凭据访问、不创建目录。审计入口最终为 audit run/resume/list/show/replay，未实现的命令不提前注册。

未发布的本批唯一 revision 为 `a1001_fixture_audit`，基于 `a704_screening_retry`；本批只追加实际用到的表，种子由显式 register 写入。各票如需调整该未发布 revision，必须从 a704 重建临时库验证，不能声称原地修补中间库；一旦发布或用于真实库，不再改写。现有配置/论文/Screening 身份不变。前七票只声明行为子集通过，最后 #108 完成 scope 重绑与完整门禁。

validate_all 只读核验登记原字节哈希、Pydantic 重建、样本身份、完整条目集合与替换关系。备份固定副本调用相同语义检查，恢复不访问声明路径/来源 URL、不运行 live；大型取得字节复用 ArtifactStore 闭包，共享 source_snapshot 的引用今后 GC 必须同时考虑论文与审计。
