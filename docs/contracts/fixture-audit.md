# Fixture 注册与摘要审计 Contract v1

本 Contract 落实 #100 评论裁决；权威注册格式为 `paper_radar.fixture_audit.models.FixtureDeclaration`，不加入 `CONTRACT_NAMES` 或五份 Frozen Contract。#101 交付声明登记、只读历史与基本恢复；#102 交付本机 PDF 字节及 backend 期望登记；路线执行、选样、矩阵及独立 A10 验收按 #103–#108 后续交付。当前不代表真实来源、Docling、模型或完整阶段 A 通过。

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

审计锁固定在 `resolved_database.parent.parent/.paper-radar-audit-locks/{database_path_sha256}/{plan_id}.lock`，命名空间取解析后的数据库绝对路径，避免同库不同拼法产生另一把锁；执行前确认锁目录在解析后的制品根之外，否则受控拒绝。常见 `database=data/db`、`data_root=data` 的锁位于 data 外；锁不进入备份或代码身份。非阻塞 flock，不 unlink、不写 PID，不在数据库写事务中等待。读取不取锁。联系邮箱每次 live 显式提供，仅当次 UA 使用；来源内容按实际有效解码检查配置邮箱（不区分大小写），无法安全解码或回显邮箱时受控拒绝，不改写合法响应原字节。不持久化邮箱，不读取个人环境或猜测；缺失/非法时连计划也不建立。不联网的帮助/查询不能要求邮箱。

原因沿用 §8.4，审计补充：not_applicable_no_doi、agency_unknown、agency_unsupported、identity_mismatch、unrecognized_page_shape、record_without_abstract、outcome_unknown、deferred_retry_after、not_attempted、disallowed_destination、disallowed_scheme、channel_not_installed。只有有效 Feed 或身份已核验且贡献身份/字段的响应进入 source_snapshot，身份正确但无摘要的页面也保留；失败/限流/挑战/身份未核验 200 仅保留结构化事实。

## CLI 与持久化

`fixture register FILE --database DB --data-root ROOT` 显式写登记，不迁移；`fixture check FILE --database DB` 只读比对；`fixture list --database DB [--history]` 与 `fixture show RECORD_ID --database DB` 只读数据库历史，源文件可不存在。共同支持 --json；帮助为中文并说明副作用、配额及示例，无网络/数据库/凭据访问、不创建目录。审计入口最终为 audit run/resume/list/show/replay，未实现的命令不提前注册。

未发布的本批唯一 revision 为 `a1001_fixture_audit`，基于 `a704_screening_retry`；本批只追加实际用到的表，种子由显式 register 写入。各票如需调整该未发布 revision，必须从 a704 重建临时库验证，不能声称原地修补中间库；一旦发布或用于真实库，不再改写。现有配置/论文/Screening 身份不变。前七票只声明行为子集通过，最后 #108 完成 scope 重绑与完整门禁。

validate_all 只读核验登记原字节哈希、Pydantic 重建、样本身份、完整条目集合与替换关系。备份固定副本调用相同语义检查，恢复不访问声明路径/来源 URL、不运行 live；大型取得字节复用 ArtifactStore 闭包，共享 source_snapshot 的引用今后 GC 必须同时考虑论文与审计。


## #103 已交付的取得边界

`FixtureAudit.create_audit_plan(contact_email=..., target_count=5)` 在网络之前提交唯一 N、四刊端点、安装包/Git 身份、parser、HTTP、策略、通道与 UA 版本。显式 `plan_key` 支持同内容重试，异内容须新计划。邮箱缺失或非法时不创建计划；不从环境或配置猜测。合成测试身份明确记录 basis=synthetic，不能冒充真实 clean-code 审计证据。

`acquire_source(plan_id, request_key=..., request=SourceRequest(...), contact_email=...)` 持有非阻塞计划锁，先提交 started，再在事务外调通道执行器、发布有资格保留的完整 source_snapshot，最后在短事务追加结算。请求身份包含规范请求的策略、通道、来源与条件引用；同键异内容拒绝，已完成精确调用只重放旧结果。未结算请求数为未知，不记零；本票没有隐式补跑。`audit_execution` 可由后续整轮驱动持有，同一个 guard 传给各路线，读取不取锁。

默认注册表只有 SourceHTTPExecutor；测试可显式注入执行器。未注册通道为 channel_not_installed，已注册却未执行可记 not_attempted，均不算失败。事实中的 access_basis=open、credential_class=null，请求头只记类别。无浏览器/凭据实现，不导入 playwright/selenium，不改依赖或 lockfile。外部 Pydantic 输入须重新准入；model_copy 不授予有效性，序列化 warning 不能输出原值。

| 计数 | 定义 | 本轮上限 |
| --- | --- | --- |
| 路线执行 | started 与一次结算 | 一次显式调用 |
| HTTP 轮次 | 首次及允许的重试，各自共享连接、重定向、流式读取 30 秒期限 | 最多 2 轮 |
| retry | 连接错误、429、5xx 后的新轮次 | 最多 1 次 |
| redirect hop | 实际跟随的重定向，不占 retry；物理请求独立计数 | 每轮最多 5 跳 |
| 物理请求 | 实际交给 HTTP transport 的 GET，含重试与每一跳 | 每轮最多 6 次 |
| 等待 | 按主机最少 1 秒间隔及轮次间退避，保存实际等待总量 | 退避至多 5 秒 |

`Retry-After` 支持 delta-seconds/HTTP-date；过去日期为零，无效值使用 1 秒短退避。超过 5 秒为 deferred_retry_after，不睡到下一轮；退避在两轮之间，30 秒是每轮期限。超时、403/404、304、解析与身份错误不获得额外重试。真实异步 socket I/O 用整轮取消期限，确定性测试同时注入单调时钟和等待；gzip/deflate 在累计 8 MiB 限额内解压，先检查再扩张；gzip 的所有拼接 member 共用此上限，完整消费并保留全部解压字节，未完成 member 或无效尾部拒绝。关闭环境继承，代理只能显式提供，每跳清空 cookie；不存 Set-Cookie、认证头、邮箱或原始异常。URL 仅固定路由，Feed 身份复用 A6 的完整 query 规则。

HTTPFacts 只保存安全 URL、状态、轮次/重定向/重试/实际等待与 Content-Type/charset/实际解码方式。响应正文只在瞬时 SourceResponse 中且 repr 隐藏。Feed XML 在原字节和有效解码文本两层拒绝 DOCTYPE/ENTITY，此规则仅用于 Feed。有效 XML Feed 或显式 DOI 身份核验通过的贡献页面可保留；doiRA 只保存结构化机构事实。失败、挑战页、身份冲突与非 Feed 200 不存正文。此处只判断保留资格，不伪造已选成员、摘要命中或完整轮次。

条件头可空；带条件时必须引用已有同策略/通道/来源取得核验的 source_snapshot。无旧材料在 HTTP 前拒绝。304 只复用该既有引用，标记 reused_prior，不产生新材料或假取得时间；原始来源事实保留。取得结算的 `content_decoding` 单独记录保留材料的实际解码依据：200 来自实际取得，304 沿匹配原始材料继承，不能用本次无体 HTTP 的默认 UTF-8 代替。`http.charset/decoding` 仍只表示本次 HTTP 响应，不伪填旧头；回放/恢复按 `content_decoding` 重解析并核对原始/复用关系。计划 created_at、路线 started_at 与 settled_at 使用实际生成的 `datetime.isoformat()` UTC（+00:00）规范字符串；非法值、无时区或非规范表示拒绝，保留原始合法字节。墙钟先后不构成新的门禁，请求期限仍使用单调时钟。声明、材料引用、请求身份、计数和内容资格在 validate_all 中只读核对，并接入原有备份固定副本；恢复不联网、不取得执行锁、不自动继续。

初始 #103 CLI 为 `audit list --database DB [--json]`、`audit show PLAN_ID --database DB [--json]`；普通输出只含安全身份、计数与材料哈希。帮助、list/show 不创建目录或锁。#105 已接通显式 run 和摘要矩阵（见下文）；resume/replay 由 #106 交付，完整混合恢复与独立 A10 仍由后续票收口。当前未运行真实来源审计。

## PDF 字节事实与 backend 期望（#102）

`FixtureAudit.register_pdf(record_id, source, ...)` 读取本机给定文件，由既有 ArtifactStore
按真实字节登记 `original_pdf`，核验长度及 SHA-256。`record_id` 必须指向已登记的 PDF
逻辑样本，handle 仍只是来源定位。取得请求包含 `request_key`、`sample_record_id`、
公开 `source_url`（无 userinfo/query/fragment）、`access_basis`、`license_basis` 与
真实合法的 `observed_date`；可提供 `expected_sha256`，它必须匹配实际字节，不能代替读取。
取得请求和结果仅在 SQLite 中保存，原声明文件不回写，源 PDF 路径不保存。许可/访问依据
是调用方提供的取得记录，不表示许可已被判定或获准在公开仓库再分发。

登记文件只证明本机给定的非空字节被完整保留，不证明 PDF 可解析、DOI/handle 与内容
相符、合法性或版式质量通过。原声明的 `basis` 不因追加本机取得而改写；查询的 `pdf`
投影另列字节事实、当前 PDF 和全部历史。没有本机取得时 `pdf=null`，不填占位 SHA、
默认许可或 backend 结果。普通 acquired 声明仍不能直接绕过实际证据入口。

首次取得形成 PDF 当前选择；再次选择必须显式 `replaces=当前 pdf_id` 及非空
`replacement_reason`。替换只在同一 `(purpose, journal, key)` 下追加，旧字节与旧期望
保持可查；悬空、跨对象、过期或循环关系拒绝。相同样本的 `request_key` 绑定完整取得
事实，精确重试幂等，异字节、异旧记录、异原因或异取得依据均拒绝。失败最多留下合法的
完整未引用制品，不能补出成功取得事实。

`register_pdf_backend(PdfBackendRegistration | Path)` 另行追加期望，必须绑定准确的
`pdf_id/pdf_sha256`。字段为 `request_key`、`backend_component/backend_version`、显式
模型版本集合 `model_versions`、`extraction_fingerprint`、`reading_sha256`，以及各自独立的
`methods_data`、`availability_open_research`。组件/模型版本非空，哈希为64位小写hex，
模型名称不得重复，具名模型集合的输入顺序不进入 backend 身份；历史请求顺序仍原样保留。
同一 PDF、backend 组件/版本、模型版本集合与 extraction fingerprint
绑定一组不可变期望，不用新的请求键覆盖相同身份。旧 backend 的期望不变，更换 PDF 后
不自动复制到新 SHA。登记成功的证明级别恒为 `shape_only`，不重算提取语义或运行 Docling。

两类章节定位分别为：

| state | locator | inspection_basis |
| --- | --- | --- |
| unverified | 不得填写 | 不得填写 |
| located | 必须明确填写 | 必须填写检查依据 |
| confirmed_absent | 不得虚构位置 | 必须填写确认不存在的检查依据 |

未检查或缺材料不能填写 confirmed_absent。期望登记只核对检查依据存在及字段形状，
不自行判定原文是否存在对应章节。

CLI 保持四个子命令，新增显式模式：

```bash
paper-radar fixture register pdf-request.json --pdf-file sample.pdf --database DB --data-root ROOT
paper-radar fixture register backend-request.json --backend --database DB --data-root ROOT
paper-radar fixture check RECORD_ID --pdf --database DB --data-root ROOT --json
paper-radar fixture show RECORD_ID --database DB --data-root ROOT --json
```

`pdf-request.json` 对应 `PdfRegistration`，`backend-request.json` 对应
`PdfBackendRegistration`；JSON 未知/重复字段、无效日期、空版本与无效引用安全拒绝。
公共模型接收在序列化前递归重校验实例，畸形模型只返回安全原因，不产生含字段原值的序列化诊断。
`--pdf-file` 与 `--backend` 不可同用。`fixture check FILE` 仍只对声明原字节比对，
`check RECORD_ID --pdf` 单独验证本机字节，返回 not_registered 或 byte_verified 及期望数；
没有材料不等于声明漂移。`list/show` 无 `--data-root` 时查询历史登记事实，显式提供根时
进一步核验本机字节。`validate_all` 在存在 PDF 事实时必须提供制品根。

PDF 及全部旧 backend 期望进入既有 backup/restore 闭包；恢复只依赖 SQLite 和批次内
制品，不访问原文件、来源 URL 或原声明路径，不下载 PDF、不自动解析。只有远端要求的
待补齐声明不产生缺失制品。相同字节按既有内容寻址复用。语义核验除字节闭包外重建取得
身份、样本作用域、替换链、预期/实际 SHA 一致性及 backend 引用；重算外层备份哈希也
不能绕过这些检查。本批继续使用未发布 a1001 revision，所有测试从 a704 重新升级。


## 固定选样与暂时受阻继续（#104）

公共服务 `select_audit_samples(plan_id, contact_email=..., code_identity=...)` 依次推进四刊，在 `audit show/list` 的 sampling 投影中返回冻结 Feed、成员、排除、暂停位置及完整历史。`continue_audit_sampling` 是显式联网写入继续，只重试尚未冻结的 Feed 与当前受阻候选所需路线；已完成路线复用原取得，不重抓已冻结 Feed。继续前核对代码、parser、策略、选样/类别规则身份，变化须新计划。N 是计划唯一 5–10 值，四刊共享该目标但各自选样和去重。

Feed parser v1 支持 RSS、Atom、RSS 1.0 RDF；拒绝 DOCTYPE/ENTITY、NUL宽字符XML及不支持的形状，不让 XML 工具联网。XML 与最小 Feed 形状通过后才冻结唯一整份 source_snapshot 引用；失败仍可显式重取。RDF 存在 Seq 时按其资源序列排列，同时保存物理 item 定位。每刊考察前 50 原位次，重复项消耗位次。DOI 复用 A6 规范化；无 DOI 仅认原样 guid/id/rdf:about，不用题名、DOI前缀或链接推断身份。跨刊同 DOI 不互相排除；日期和精度只披露，不排序。

类别依据仅 ADR-0033 闭集。类型路径中的 null、数组或标量容器以及非字符串类型值均不提供明确类别依据，按未知结算；原材料与逐来源事实保留，其他刊继续推进。Wiley category/prism:section 原值保留但不产生判定；Crossref/DataCite 其他明确类型为非 journal-article，dqkx 平台表外值/缺字段为未知，明确正负判定矛盾为冲突。Feed 位置、题名、og:type、citation_doi 均不是类别依据。citation_doi 只用于 AIES 无 DOI/guid 时，经受控 Feed link 取得显式身份，再查 doiRA/适用机构；链接本身不成为稳定标识。

选样期只执行身份/类别需要的路线：已有 DOI 则查 doiRA 与其适用 registry；dqkx 还核对出版者显式类型；AIES 缺 DOI 时先取出版者 citation_doi。doiRA 其他机构只关闭 registry，查询失败/404 保留 agency_unknown 与原始 HTTP 状态；单一机构404不表示全球 DOI 不存在。有效身份但无摘要的来源仍可贡献；选样不消费摘要成败，不因先有摘要而换样。

| 原候选结果 | 含义 | 位次行为 |
| --- | --- | --- |
| selected | 稳定身份且有明确 journal-article 依据，无冲突 | 追加成员并推进 |
| excluded_deterministic | 重复、无稳定身份、明确身份冲突、查完无类别、明确非文章或类别冲突 | 保留独立原因后推进 |
| blocked_pending | 身份/类别所需路线暂时失败、未核验或结果未知 | 保留原位次，其他刊继续 |

取得在事务外进行，成员/排除/暂停事件在短事务原子追加。选样事件按同刊显式前驱形成历史，不能回写、跳位或改变既有成员。started未结算在显式选样继续中先追加 outcome_unknown 再新建执行，请求数保持未知。本节描述原选样阶段继续；#106 已补全路线 resume/replay、两个真实进程场景和新 parser 追加解释（见下文）。

每个成员引用整份 Feed SHA、原位次、ID/DOI定位、来源取得和明确类别依据，不伪造 A6 单 item 字节；模型不持有摘要成败。validate_all 从冻结 Feed 重建候选，再用事件原路线材料重放同一选择逻辑，核对成员、来源、排除及历史，不以哈希一致代替语义核验。基本备份恢复包含这些引用与原字节，恢复后 list/show 不读仓库声明或原 Feed 路径、不获取执行锁、不自动继续。四刊实测、来源稳定性、摘要矩阵与完整阶段 A 均未由本票证明。

## 摘要矩阵与显式运行（#105）

`paper-radar audit run --database DB --data-root ROOT --contact-email EMAIL [--count 5] [--json]`
先验证临时联系邮箱，再原子提交计划，最后在同一计划执行锁中全轮串行选样和执行成员矩阵。
整个计划唯一 N=5–10；邮箱只用于如实请求标识，不保存。`run_audit` 是相同公共服务入口，
允许测试在外部 HTTP transport 注入合成响应；本票不执行 live。

计划新增冻结 `audit-matrix-v1`、`audit-abstract-v1`、`audit-truncation-v1`。
矩阵身份为 `(member_id, route, acquisition_strategy_version, channel)`，适用性来自冻结策略：

| 条件 | 适用路线/通道 |
| --- | --- |
| 所有固定成员 | feed/http，引用该刊唯一冻结 Feed 与成员物理 item 定位 |
| 有 DOI | doi_ra/http |
| doiRA 明确为 Crossref 或 DataCite | 对应的 registry/http；其他机构单列 agency_unsupported |
| AIES 有受控出版者链接，或其他三刊有 DOI | publisher/http 与 publisher/browser_render |
| official_api、repository | v1 无成员适用目标，汇总显示 0 适用、执行器未交付，不建行 |

无 DOI、agency 未知、机构不支持及出版者目标未知分别披露；不建立四通道笛卡尔积。
每条适用路线独立执行，不因其他路线已有摘要而短路。选样期取得可直接引用同一 execution、
source_snapshot、payload SHA 和原 settled_at；矩阵解释不制造新取得时间，不为补分母重抓。
仅存在 started 的路线显示 outcome_unknown，物理请求数未知；尚未执行的已交付路线显示
not_attempted。未交付通道显示 channel_not_installed，单列其适用数量，不重试、不计失败，
摘要覆盖分母为零/不适用；不存在“渲染 0/N 成功率”。#106 已交付显式全路线 resume/replay（见下文）。

主摘要采用正向识别。出版者必须有已核验 DOI 身份，且只有已知主容器贡献题名和摘要：
AIES/Wiley 为 class/id `abstract`、`article-section__abstract` 或 `abstractSection`；dqkx
为 `abstract-cn`。零个或多个主容器均为 unrecognized_page_shape；页面其他文本不补齐摘要。
已知 `challenge-form`、`captcha-form`、`login-form`、`subscription-form` 表单为受阻特征，
即使 HTTP 200 或带 citation_doi 也不保存正文。未知形状不能自动推断为访问受阻。
已核验身份但无主容器的材料仍可保留供历史重解析，不能贡献页面题名。
已知主容器存在但为空时为 record_without_abstract，有效记录与非空摘要分开。

RSS/Atom/RDF 按固定成员的物理 item 解析 description/summary/content；Wiley/AMS 有完整
字面 Abstract/摘要标签时只消费该标签后、下一个附加标签前的主区块，之前段落单列前置区块。
dqkx Feed 只取 p 内正文，p 外引文尾行不参与仲裁。Significance Statement、Plain Language
Summary、Key Points 及 abstract-en 只保存存在与定位；已知附加 class/id 也从主容器排除。
Crossref 只取 message.abstract（允许 JATS 标记），DataCite 只取首个 descriptionType=Abstract。
不翻译、不拼接不同来源、不从正文、搜索摘要或未标记页面取摘要。

HTML 实体解码一次、去标记与段落连接整体属于 abstract v1；相邻段落以一个换行连接，
内部空白、Unicode、原语言和数学比较保留，最后调用 A6 normalize_text v1。
实体解码后仍呈真实标签的字面残留先记 markup_residue，再清除真实残留标记后规范化。
受控 HTML 解析最大嵌套深度 100；超过时记录 invalid_response，不影响其他成员。
截断逐项信号是同一纯规则的输出，bool 等于 signals 非空：

| 信号 | 机械条件 |
| --- | --- |
| short_under_100 | 最终规范文本不足 100 Unicode code point，100 不命中 |
| trailing_ellipsis | 去尾随闭引号/括号后以 `...` 或 `…` 结束 |
| read_more | 尾部 Read more（忽略大小写）或阅读更多，可后接空白/句末标点 |
| markup_residue | 实体解码后的文本仍有真实标记残留，数学 `x < y` 不命中 |
| missing_terminal_punctuation | 不以 `.?!。？！` 结束（允许相邻尾随闭引号/括号）；省略号不算终止标点 |

v1 尾随闭字符集合为 ASCII 单/双引号、`”’»）)]}】》」』`。短摘要保留且可获选；未命中
只说明未发现这些信号，不证明完整。候选持久化仅含字段/来源/定位、文本 SHA、code point
长度及截断信号，普通 list/show/repr/异常不含摘要原文。`read_audit_text(plan_id, candidate_id)`
是显式受控读取入口：从原材料按历史 v1 规则重解析并核对安全解释后返回原语言文本。

成员全部适用路线结算后，构造 A6 RankedObservation 并调用原 choose_fields：
`observed_at=原取得 settled_at`，`payload_sha256=原响应体 SHA`，`parser_version=1` 对应
abstract v1，`stream=(plan_id, member_id:route:strategy_version:channel)`；字段引用为
`(candidate_id, acquisition_id)`。保留 A6 同流同 payload 的最高 parser、publisher > registry >
feed、实际取得时间、payload SHA、parser、stream 的稳定降序排序。题名/摘要分别获选，
final_abstract_source 只描述摘要；不按长度或截断改写优先级。候选与每字段获选/低优先级/
较早观察或稳定 tie-break 依据可重建；高优先级获选片段与低优先级未命中截断的冲突按刊计数。
尚未全部结算的成员 `routes_settled=false`，最终字段为空，分布单列 pending。

汇总保持策略/通道分离，列明目标、入样、考察、排除、未知、冲突、不足、原日期跨度与未知日期，
以及路线适用/尝试/未尝试/未安装、有效记录、非空摘要、截断、错误和最终摘要来源。
非空摘要覆盖同时给分子和适用且已交付通道的分母，分母为零给 ratio=null/不适用。
doiRA 只是机构路由，不是摘要提供方，摘要分母恒为零；适用及执行计数独立保留。
物理 HTTP 请求、redirect、retry 和未知执行另列，不混成成员路线覆盖率。

complete 仅表示四刊选样已结算且固定成员应有路线均有终态；不足样本、全无摘要、受阻与
来源稳定性各自披露。暂时受阻的选样或未结算成员使状态为 partial。不会生成 Paper、
metadata_ready、metadata_unobtainable、人工队列、Screening 或门禁事件。完整候选优先、
附加区块是否供 Screening、阶段 B 稳定性阻断判据仍待后续裁决。

每条路线的取得引用、候选安全解释与区块定位在短事务原子追加；汇总从事实派生。
新增 audit_abstract_rows 随唯一未发布 a1001 revision 从 a704 建立，validate_all 和既有
backup/restore 固定副本重读原材料核对解释；重算行 ID/备份 SHA 也不能篡改候选长度或信号，不能将冻结 Feed/选样原取得替换为同路线另一次取得；没有原取得的路线只认确定的 matrix 请求键。
已保存矩阵解释不能以自报 not_attempted 跳过重解析：该状态须与零请求、无原材料/候选及底层未尝试结算一致。校验从同一只读视图取得真实持久化行集合；来源已取得、解释尚未保存时的待解释投影仍可随部分计划备份恢复。

显式恢复/历史重解释由 #106 交付；完整混合恢复与独立 A10 门禁继续由 #107/#108 收口；本票不宣称全量门禁通过。

## 显式恢复、历史回放与追加解释（#106）

| 操作 | 输入与副作用 | 证明范围 |
| --- | --- | --- |
| `audit resume PLAN_ID --database DB --data-root ROOT --contact-email EMAIL [--json]` / `resume_audit` | 同一计划，显式联网写入；每次重新提供邮箱 | 继续未结算或允许的暂时路线；不改旧事实 |
| `audit replay PLAN_ID --database DB --data-root ROOT [--json]` / `replay_audit` | 历史版本，只读、无网络、无执行锁 | 冻结 v1 的成员、候选、截断、仲裁与汇总重建 |
| `reinterpret_audit(plan_id, parser=..., request_key=...)` | 仅服务 API，显式注入新解析器，短事务追加 | 新解释和相对前驱的字段增减；不换成员、不改 v1 汇总 |
| `replay_audit_interpretation(..., parser=...)` | 只读，显式匹配该解释声明的运行时 | 可取得材料按该注入解析器重解析；失败仍只有执行事实 |

resume 在网络或写入前核对原计划代码声明及 acquisition/channels/http/parser/sampling/category/
UA/abstract/truncation/matrix 全部规则版本。任何不匹配提示新计划；不能执行的历史版本在
resume 映射为 plan_identity_mismatch，在只读 replay 为 unsupported_history。
已冻结 Feed 不重取、固定成员不替换，选样只继续原受阻位次；未冻结 Feed 可显式重新取得。
成员路线的 acquired、record_without_abstract、not_found、identity_mismatch、
unrecognized_page_shape、invalid_response、agency_unsupported 及不允许的目的地/协议
为确定性终态，不重抓。channel_not_installed 不重试。允许显式继续的暂时原因闭集为
transient_error、rate_limited、deferred_retry_after、outcome_unknown、agency_unknown、
provider_incomplete、access_blocked_403、not_attempted；这不是单次 HTTP 自动重试的扩张。
访问受阻的显式重试仍使用同一如实身份、受控目标和频率，不更换凭据或规避控制。

新执行通过 `previous_execution_id` 指向同计划、同请求的前一次结算；一个前驱最多一个
后继。选样请求原位次/序号、矩阵请求 resume 序号及前驱一致核对，悬空、跳号、去前驱、
跨请求、跨计划、分叉或循环均拒绝。started 无回执时，先追加 outcome_unknown、请求数保持
未知，再开始后继；内容寻址制品即使已经发布，也不能凭其存在追认旧取得成功。

矩阵行改为带 generation/previous_row_id 的只追加解释链，根仍绑定选样原取得或确定矩阵
请求键；后继绑定旧行与取得前驱，只有受控暂时原因才能推进。当前矩阵按成员/路线/策略/
通道取一个结论，matrix_history 保留全部旧解释；成员分母不会因重试次数增加。物理 HTTP
次数/重定向/重试、未知执行另列。取得成功但解释未提交时复用该原取得完成解释，不再请求。
活动后继尚未提交解释时以 interpretation_pending 投影显示，其 started 为 outcome_unknown；
该成员没有最终字段，整轮为 partial。投影不冒充持久化解释；完整性仍按数据库 stored_ids
核验全部历史解释，不能因行自报状态而跳过。

整轮持计划 flock，SQLite 写事务中不等待锁；文件不写 PID/TTL、不 unlink，进程退出即释放。
同计划竞争返回 execution_busy，show/replay 在执行中依然只读可用。两个必要真实进程用管道
握手确认锁内或 HTTP transport 已进入（因此 started 已提交），再释放/kill，不用长 sleep。
恢复中保留单次内部 HTTP 上限与每次显式继续的独立执行账目，不使用 A7 lease/attempt。

产品历史注册表目前只包含已发布完整 v1 实现；回放按计划保存的版本选择，不以当前默认
常量替代。保存身份/原字节被篡改为 corrupt_reference；合法身份引用无法加载的历史版本
为 unsupported_history。AuditReplay 返回安全视图、semantic_sha256 及逐执行证明等级：
material_reparsed 仅用于真实保留的来源材料，execution_facts_only 用于 doiRA 结构化事实、
失败、未安装和无回执等无原体事实；另列 outcome_unknown。不能据此声称逐字回放失败页。

新 parser 实现 `AuditMaterialParser`：`version`、`implementation_sha256` 与
`parse(request, raw, *, decoding, entry_locator)`；返回 title/abstract/identity_doi/category
的显式值或 None。身份/类别变动只形成新解释与差异，不重新选样。产品不发布测试 v2、
不提供 reinterpret CLI。解析器版本绑定唯一实现 SHA 声明，不能同版本换实现；声明与解释
同一短事务提交。正文只在瞬时回调输入中，输出持久化仅保存规范字段哈希、code point 长度
和截断信号，不把新摘要放入普通查询、repr、日志、SQLite 或备份。

第一份解释相对冻结 v1 比较，此后 added/removed/changed 相对 previous_interpretation_id
对应的同路线字段比较；原 v1、所有旧解释、原成员及汇总保持。解释冻结其 base_row_id、
取得引用、basis SHA、解析器声明、请求键和前驱。精确请求重放幂等，同键异输出/声明拒绝。
未知解析器或原始异常安全映射，不回显原文。

默认 validate_all/backup 会核验新解释的规范安全字节/身份、解析器声明、材料引用、前后
解释链与可重建字段差异，证明级别为 declaration_and_reference_verified；它不声称未安装
的 v2 已被重解析。v2 重解析必须显式提供与 version/implementation_sha256 均匹配的运行时；
缺失为 unsupported_history，匹配运行时但重算不一致为 corrupt_reference，成功级别为
available_material_reparsed。恢复不需要原声明/配置路径、不联网、不自动继续或安装 parser。

代码身份边界：commit + dirty=true 不能区分同一提交后不同工作树内容；resume 的声明相等
只证明声明未变。测试可使用明确 synthetic 身份，真实验收仍要求 clean tree，不能把测试
身份或脏树声明升级为 live 证据。完整混合历史隔离恢复与 scope/必需门禁仍由 #107/#108 收口。

公开取得入口也执行同一准入：精确同键/同请求/同前驱先幂等返回；换新键不能给 complete
计划或已冻结的成员路线新增取得，受控返回 route_already_settled，并指导新计划或显式 resume。
合法 resume 必须引用当前暂时结论的取得前驱及确定的 resume 请求键；未完成的其他候选/路线
仍可推进。无 DOI 的重复候选若请求指向同一个已核验出版者材料，选样直接复用原响应作身份
依据，再按 DOI 判重复，不能借新候选位置重新抓取同一已冻结路线。尚未保存解释的成功取得
通过 interpretation_pending=true 与真实 reason=acquired 同时披露，不再把真实已请求误称未尝试。
