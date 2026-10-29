# 论文事实 Contract（A6）

提供出版者 DOI 事实、Feed 发现与只读历史、四类来源仲裁、人工修正、完整历史读面、权威版本关系与正式升级、阶段输入映射及组合隔离恢复，纳入必需 A6 同次验收。单次是否通过以对应 run_id 的独立结论及终态为准。权威顺序是最新用户裁决、不冲突的后续澄清、实施前补充默认、原 #67 正文。[ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md) 记录覆盖关系；#67 的固定提交链接保留为历史依据。

## 1. 范围与格式

格式权威一次固定如下，实现从生产单一权威读取，验收独立固定期望，不自动刷新：

| 名称 | 版本 | 含义 |
| --- | --- | --- |
| `paper_facts` | 1 | 封闭论文事实公共边界 |
| `doi_rules` | 1 | 本文 DOI 接受集合与规范化 |
| `text_norm` | 1 | 规范文本规则 |
| `feed_item_fingerprint` | 1 | 原始 item 字节完整 SHA-256 |
| `reason_catalog` | 1 | 第 9 节原因名称与语义 |
| `mapping_result` | 1 | 第 8 节逐阶段映射返回形状 |

boundary/value StageInput 沿用既有格式 1，backup format 沿用 1。A6 只接 DOI、明确的既有 Paper/Version、Feed 发现和出版者结构化、DOI 注册机构、Feed、人工字段修正观察。不接受 arXiv/PMID、自由 scheme 或关系类型、HTTP 状态、失败响应、任意 JSON 属性；不建 `duplicate_candidates`、`merge_events`、`manual_intakes`、任务/校准空表。未开放字段或关系整笔拒绝，不忽略后当作成功。

论文事实服务承载确定性规则与事务边界。CLI 与未来适配器只调用公共服务；纯 DOI/文本/仲裁/版本规则不依赖 storage 或 SQLAlchemy。config、screening、stage_inputs 不得反向导入论文事实服务；服务不得导入 HTTP/LLM/Docling/外部适配器。后续 AST 检查固定这些依赖。A6 不新增网络端点适配器、Feed 配置或产品写入命令。

### 1.1 #69 出版者切片与公共边界

本节保留 a601 的历史切片边界；当前完整来源、关系和映射能力分别见 §1.3、§4 与 §8，不以历史拒绝范围限制现行服务。

公共 Python 边界为 `paper_radar.papers.PaperFacts(database, data_root)`：`submit(observation)` 接受严格 `ObservationInput` 或其字段字典，返回 `WriteResult`；`show(paper_id)` 返回当前 `PaperView`，`trace(paper_id, verify_source_bytes=False)` 返回 `PaperTrace`，`validate_all()` 只读校验完整引用与历史修订。所有公开模型 repr/str 隐藏论文内容；服务验证错误只返回受控原因，不透传 Pydantic 输入载荷。原始 `ObservationInput.source_kind`/`RelationInput.kind` 保持字符串，关系项在纯规则层校验，未知值分别返回 `unsupported_source`/`unsupported_relation`；规范事实与仲裁内部使用封闭领域类型，`NormalizedRelation` 另外保留 `raw_*` 原断言。模型 `model_validate*` 将最终校验失败转换为 `PaperError`；直接构造使用脱敏 `ValueError` 参与 Pydantic 联合候选回退，保证合法日期字典可选中 `DateValue`。

本切片仅接受 `source_kind="publisher"`、DOI 目标与同一 `(provider, query_key, version_id)` 出版者流。字段候选是 `{value, locator}`；摘要 value 是 `{text, is_truncated, rule}`，日期 value 是 `{value, precision}`，作者使用有序字符串 tuple。`version_kind` 为 `preprint/journal`，`observed_at` 为明确 UTC datetime，`parser_version` 为正整数，必填 `interpretation="complete"` 声明整份材料的完整解释，`payload` 为单份非空 bytes。其余支持范围以本文目标及下节 #70 扩展为准，在 #69 历史切片中跨出版者流、注册机构、人工入口分别 `unsupported_source`（#71 扩展见 §1.3），关系 `unsupported_relation`，未知字段 `unsupported_field`，均整笔拒绝。

迁移 `a601_paper_facts` 只建立实际使用的 Paper、Version、doi 标识、出版者观察、字段候选/作者成员、完整引用式修订与初始选择表。该条历史 migration 无 Feed、关系、人工修正或未来任务空壳表；#70 只通过下述追加迁移扩展。只读 CLI 为本文 §8 的 show/trace 子集，不开放映射、历史选择器或配置快照参数。

### 1.2 #70 Feed 发现切片

`register_feed(url) -> FeedFact` 返回数据库登记的 `feed_id/url`；非法 URL 为 `invalid_feed_url`。
`submit` 的 Feed 形状使用 `source_kind="feed"`、真实 `feed_id`、非空原样 `entry_id`、
显式 `payload_scope="single_item"`、`doi: str | None`，其余时间、完整解释、候选及原文边界沿用公共模型。
Feed 调用方不能自行设置 provider/query_key；持久化来源流由 feed_id/entry_id 确定，稳定排序使用规范 Feed URL/entry_id。
缺 entry ID 为 `missing_entry_id`；entry 原样保留，须为合法 UTF-8、非空且最多 2048 字节，
写入口与备份引用校验复用同一权威。无效 UUID/未登记 Feed、缺单 item 声明、可识别整份 Feed 或多 item 包装为 `invalid_observation`。
原文 fingerprint 全局绑定同一个 `(feed_id, entry_id)`，不能把相同字节冒充另一条目；不实现任意 XML 真实性识别。

`WriteResult.discovery_id` 指向原始发现；重放返回该解释原结果，只把 last_seen 推进到最大时点。
每个首次原文发现即使没有字段，也保留真实无 DOI 版本、空字段修订与原文观察；
已有原文的全空高版本解释则 `not_retained`，不替换已有字段解释，但保留解析版本门禁和回执。
解释首个请求时间另行保留以区分 parser 升级后的旧请求精确重试与新的低版本请求；
非人工仲裁仍只用原文不可变 first_seen，不使用该请求时间或 last_seen。

`trace.discoveries` 展示发现 ID、版本、Feed UUID/规范 URL、entry ID、fingerprint、原文制品、
first_seen/last_seen 与全部保留解释观察 ID；interpretations 同时公开每个 parser_version 的首个 submitted_at、
acquisition_id 和可空 observation_id（包括全空解释）。完整字段来源仍在 observations/acquisitions 中。
`show` 继续只展示规范事实。文本查询简明显示原题名/身份/受控来源摘要，JSON 与文本均声明
“仅覆盖论文事实；尚未计算完整任务资格”；默认不输出 item 或摘要全文。

`a602_feed_discovery` 顺序追加 Feed、连续条目、原始发现和解释引用表，扩展实际使用的来源类别约束；
以同一事务暂存并重建依赖闭包，非空 a601 升级/故障/强杀后保持旧事实与 FK 完整，不改 a601。
出版者和 Feed 的取得事实新增 `raw_doi`，保留首次登记请求的原始 DOI 书写，不参与身份键或 StageInput。
已有 a601 事实该列为 NULL，如实表示当时未记录，不能用规范 DOI 冒充原书写；Feed 无 DOI 时也为 NULL。
已登记请求的精确重试继续返回原回执，不因换 DOI 包装而改写原拼写。
备份只读校验全部 Feed 登记（包括尚无发现的 Feed）、entry 输入域、连续归属、原文 fingerprint/blob、解释、取得、候选和修订闭包；
发现时间与解释提交时间须为微秒 UTC，首次解释 submitted_at 等于 first_seen，last_seen 不得早于任何已登记解释的 submitted_at。

a602 历史切片只包含同出版者流及 Feed；当前四源/人工修正、权威版本关系和正式映射分别见 §1.3、§4 与 §8。

### 1.3 #71 四类来源仲裁、人工修正与公共历史读取

`submit` 现在接受多个 publisher 来源流，以及 `source_kind="registry"`。注册机构输入必须提供
既有 `target_paper_id/target_version_id`，`doi` 与 `query_key` 都按 `doi_rules=1` 规范化后相等，
并且等于目标版本已登记 DOI；不会替无 DOI 版本登记身份，不联网判定 Crossref/DataCite 的真实归属。
来源流是 `(source_kind, provider, query_key, version_id)`；Feed 稳定键使用规范 URL/entry_id。
`parser_version` 最高解释按来源流与 payload 隔离，不受其他流同字节或高 parser 影响。

`correct(correction) -> WriteResult` 接受严格 `ManualCorrectionInput` 或字段字典，固定字段为
`version_id/request_id/actor/reason/fields`。`fields` 沿用 CandidateInput；只覆盖提供的非空字段。
request_id/actor/reason 必须是合法无 HTML 非空 UTF-8 文本，逐项最多 2048 字节。
request_id 在版本内唯一；完整原请求按 UTF-8、排序 JSON 对象键、无额外空白规范字节绑定请求哈希，
包括 actor/reason、locator、原始候选文本。相同请求精确重试返回原回执，异内容为
`invalid_manual_correction`；空字段集合、任一空白字段、仅改摘要标记或非法文本也受控拒绝。
未知字段仍 `unsupported_field`。actor/reason 是未认证调用方字符串，不表示登录身份。

人工请求完整规范字节作为 source_snapshot 先发布；同一 BEGIN IMMEDIATE 中保存观察、候选、
取得事实、人工审计引用与必要修订。人工选最新依该版本原子追加的 acquisition event_no，
可与非人工事件共用递增序列，明确允许号码间有非人工事件；该号对两条人工修正有真实先后语义。
它不参与非人工排序。普通来源不能覆盖人工结果；修正绑定 version_id，不随 Paper 当前版本升级迁移。
无撤销、删除、清空或产品写 CLI；只能以非空完整值追加覆盖。日期/作者/摘要仍使用相同字段规则。

`revision(version_id, revision_no) -> RevisionView` 是公共完整历史入口；不存在的版本/修订分别
`version_not_found/revision_not_found`。当前/历史的 connection 级共用读面为
`paper_radar.papers.queries.resolve_revision(connection, *, paper_id=None, version_id=None, revision_no=None)`；
调用方先显式 BEGIN，二选一使用 paper_id 或 version_id/revision_no，函数不另开连接。
RevisionView 返回 paper_id/version_id/revision_no/version_kind/doi/fields（完整 FieldFact provenance）与
可空 selection。历史 selection 只关联确实属于该 Paper/请求版本的选择事实，不用事件时钟推断事务先后，
不宣称该修订产生时曾经是当前版本；从未被选当前的版本可为 None。该读面不加载配置、不生成 StageInput。

trace 增加 corrections（request/actor/reason/acquisition/event_no）与 decisions：每个候选及取得引用的
受控说明为 selected、superseded_interpretation、lower_source_priority、earlier_manual_event 或
 earlier_observation_or_stable_tiebreak。说明复用纯仲裁权威；未获选来源与旧修订完整保留。
show/trace 的 JSON 与中文文本共用同次一致读服务，文本显示字段来源/定位、摘要是否存在及标记、
全部修订/候选说明和人工版本绑定限制，摘要仍只在 --show-abstract 时展开。

`a603_source_arbitration` 在原子事务中重建含 Feed 解释引用的依赖闭包，扩展来源类别并新增实际使用的
人工修正事件表；a601/a602 不变。当时备份 head 为 a603（A6 在 §6 追加 a604；当前 head 见备份 Contract）；完整性校验包含注册机构查询 DOI、
人工事件归属与来源原请求对照（显式字节核验和备份），并拒绝外键合法的跨版本候选损坏。
旧 config/Pi/artifact/来源历史与非空恢复路径保持。不注册 A6。

## 2. Paper、版本与 DOI 身份（D1）

Paper 只表示稳定 UUID，不保存题名、DOI、当前版本或主流程状态。一个 DOI 恰好绑定一个版本，标识同时绑定一致的 `paper_id/version_id`；一个版本最多一个 DOI，全局 `(scheme, normalized_value)` 唯一，scheme 封闭为 `doi`。同 DOI 恒命中同一 Paper/Version，不存在“同 DOI 多公开形态”入口。`preprint/journal` 是创建后不可变的身份类别；online-first 是尚缺卷期页码的 journal，补卷期或改摘要只追加同版本修订。

不同 DOI 的版本只有可回查的权威版本关系才能归属同一 Paper。相似题名、作者、年份、URL 不自动合并、不生成候选记录。显式目标入口只核对既有身份，不能给它挂新 DOI。唯一 DOI 补登记路径是已有无 DOI Feed 版本的新 item 提供未占用 DOI；条目从 X 变 Y、显式目标不符、类别变化、Y 已属别的 Paper 均 `identity_conflict`。X 后续消失仍保留 X。B1 原“Y 已属于另一 Paper 返回 requires_merge”已由较新的 D4 覆盖。

### 2.1 DOI 规则 v1（D2）

原始包装输入先检查最多 8192 UTF-8 字节，避免无界外围处理；再去外围 Unicode 空白，所得输入与规范值均最多 2048 UTF-8 字节，空值、超长、孤立代理字符、内部空白或 Unicode 控制/格式字符拒绝。只将 ASCII A–Z 折为 a–z，其他 Unicode 原样保留，不做 casefold、NFC/NFKC、翻译、截句或联网核验。

支持裸 DOI、ASCII 大小写不敏感的 `doi:` 前缀、HTTP(S) `doi.org/dx.doi.org` URL。只去外围空白，不再去 `doi:` 后空白，故 `DOI:10.1234/AbC` 接受、`doi: 10.1234/a` 拒绝为 `invalid_doi`。URL scheme/host 不区分 ASCII 大小写；允许相应默认端口（http 80、https 443），拒绝 userinfo、非默认端口、www 子域、尾点主机、双包装与任何 query/fragment（包含空 `?/#` 包装）为 `unsupported_form`。

URL path 去单个起始 `/` 后严格进行一次 UTF-8 百分号解码；错误转义或无效 UTF-8 为 `invalid_doi`。`%2F` 可解为 DOI 分隔斜杠，`%25` 得字面 `%` 且不再解码，`+` 不变。裸 DOI 不百分号解码，其中字面 `?/#/%` 可为后缀，不作为 URL 参数。结构为 `10.` 加非空 ASCII 数字段（可有以点分隔的非空数字细分段）、`/` 和非空后缀；不套用“4–9 位注册前缀”的经验式。不删末尾标点或尾斜杠，后缀 Unicode 大小写相异仍不同。

固定手写向量须覆盖上述形式，尤其 `HTTPS://DOI.ORG:443/10.1234/AbC` → `10.1234/abc`、`10.1234/Ä` 保留 Ä、`https://doi.org/10.1234%2FA%252F` → `10.1234/a%2f`、裸 `10.1234/a?b#c/` 原样保留后缀，以及 2048/2049 字节边界。

`unsupported_form` 是输入包装超出能力，`invalid_doi` 是本规则下结构非法；拒绝都不表示论文无效。未来只可在 path 已构成合法 DOI 时放宽为忽略 query/fragment，永不从 query 构造 DOI；不得改变任何已接受输入的规范值。未来适配器优先使用 `<guid>` 裸 DOI，缺失才从受控出版者落地页提取；原 URL 保留作证据，A6 不实现提取器。评论的 170/170 是历史来源陈述，未在 A6 重验，不能作本组 live 证据。

## 3. 四类来源事实与发布

- **来源快照**：A3 `source_snapshot` 内容寻址制品，只有字节内容身份，不含提供方、取得时间或业务目标。
- **来源观察**：来源类别、提供方、查询键/条目身份、`observed_at`、整数 `parser_version`、目标版本、来源快照引用、字段候选及 locator；Feed 发现是它在 Feed 上的特化。
- **字段候选**：观察中的一个受控字段值、locator 与规则身份，未获选者也保留；摘要是文本、截断标记/未知及判断规则身份的整体。
- **版本修订**：某版本在一次仲裁后全部规范字段的完整状态，以 `(version_id, revision_no)` 标识，逐字段只存获选候选引用与规则版本，不复制整段摘要。缺项用无获选候选表达，不造 NULL/空串值行。

只接非空原始 `bytes`，单份上限 8 MiB，不接调用方“已核验引用”。解析结果由调用方给出、规则由服务确定。先以现有 `ArtifactStore.publish_single` 完整发布来源制品，再提交业务事务；制品已发布但业务失败可以留下完整未引用 `source_snapshot`，重试复用。无需修改 A3 事务、自动清理或把未引用制品称为已持久化冲突观察。

publisher/注册机构来源流为 `(来源类别, 提供方, 查询键, 目标版本)`。用户后续裁决采用不可变的轻量**取得事实**，覆盖此前“无贡献不写业务行”的默认：每个有效请求记录原始响应 SHA-256、取得时间、parser_version、解释摘要与原结果；相同规范候选集合复用同流历史来源观察及候选引用，不重复保存候选正文，也不发布该次非业务变化响应的大包制品。`response_bytes_retained` 表示该次响应已作为字段或关系来源材料登记保留，内容对象即使去重也为 true；它不表示物理新增 blob，也不表示创建了字段观察。字段材料所属请求与关系材料取得引用分别核验。取得事实明确 `response_bytes_retained=false` 时只保存该响应的哈希，原始来源引用仍指向确实保留的旧材料，不宣称保存了新响应全文。新候选集合才先发布完整原始来源制品，再写入来源观察/候选与取得事实。

精确重试键固定为 `(来源类别, 提供方, 查询键, 规范 DOI, observed_at, payload SHA-256, parser_version)`，不依赖未来创建的 Paper/Version；与仅限已保留观察的旧口径不同，retained、not_retained 和空候选均登记不可变原结果。相同键及解析内容返回原 acquisition_id、身份、当时修订号与状态；同键异解析内容 `invalid_observation`。首次空候选没有版本/来源引用，不创建空 Paper，不发布空贡献响应，即使日后该 DOI 创建不同类别版本，原请求仍回放原结果。强身份冲突保存独立冲突事实，不登记成功取得事实；其余拒绝不登记取得事实。

`not_retained` 现在表示没有新增来源材料观察或候选正文，**不表示未持久化任何业务事实**。它可以新增轻量取得事实，并在获选取得 provenance 改变时追加引用式修订。A(t1)→A(t3)→B(t2晚到) 与 A(t1)→B(t2)→A(t3) 均获选 t3 的 A；每次取得使用自身不可变 observed_at、响应 SHA-256、parser_version 参与确定性仲裁。候选引用仍指向旧观察，取得时间/解析依据与原始材料的取得时间分开展示，不能把候选原属观察时间改成新时间。只读发布计划可先找同流同集合依据，ArtifactStore 发布仍在业务写事务之外，写事务重新核对；并发最多留下完整未引用制品，无内部忙锁重试循环。Feed 后续仍使用第 4 节首次时间与 D3 回摆规则，不能套用本段 publisher 取得时序。

同一 `(来源流, payload SHA-256)` 的 parser_version 单调。已登记请求的精确重试优先返回原结果；新的降版本请求 `invalid_observation`。同一材料、同一 parser_version 的解析字段/locator 也必须恒定，不能借更换 observed_at 偷换解释；需要变化时提升 parser_version。取得事实保存完整声明与解析内容摘要供语义检查，声明本身不是对真实解析器的认证。

更高 parser_version 的**有效非空完整解释**整体替换同材料的旧解释：新解释未提供的字段属于“该解释不含此字段”，旧解释不再参与当前仲裁，因而当前修订可以缺项；其他有效材料/来源仍可按各自优先级补充。旧候选与旧修订保留不变。这与不同 payload 的新观察不对称：不同字节之间仍是缺项不清空，不能把同材料解释替换说成可用缺失撤销字段。

**全空候选集合是明确例外**：v2 全空返回 not_retained，只保留轻量取得原结果与版本门禁，不替换当前规范字段、不形成清空修订；首次空请求仍不创建 Paper，不以空回执派生字段清空影响。此后新的低 parser 请求仍受单调门禁约束，而精确旧请求继续回原结果。

完整解释是调用方的必要承诺，服务拒绝缺失声明、明确 partial/economical 声明以及可检测的降版本/同版本异解释；不能仅从字段减少断定违规，也不声称能识别声明撒谎的真实解析器。A6 没有真实解析器，其真实性由第 10 节首次真实解析器回归门禁（B 起、C 扩展）承接。

304、限流、失败在输入类型上不可表达；这些取得执行历史仍由未来 task_attempts 承担。轻量取得只记录有效解析请求，不成为通用请求/HTTP日志框架。

当前来源 URL 与 URL 形式的查询键/提供方/locator 拒绝 userinfo、query（含空 `?`）和 fragment（含空 `#`），不猜测参数名或 opaque 查询键里的 secret；这是防止认证 URL 进入查询面的严格初版能力边界，不表示 URL 可靠性/eligibility 已核验。原始材料按来源发布规则保留。这条规则不能用于 Feed 端点 URL，第 4 节 Feed query 必须逐字保留。

所有时钟事实统一 UTC，精度固定到微秒；输入须明确 UTC 时区，不接受 naive 时间。观察时刻、选择/修订时间和 first_seen/last_seen 与发布日期分开；发布日期按语义和精度保存，不伪造时钟。

## 4. Feed 身份、发现与回摆（D3）

Feed 唯一权威是数据库按规范 URL 的唯一登记，只有 UUID 和规范 URL；不建期刊关联、ETag、Last-Modified、健康状态空列、feeds.yaml 或 CLI。未来配置接入必须另定与数据库对齐方案，不得形成第二套身份权威。规范 URL 接受 HTTP(S)，scheme/host ASCII 小写、移除默认端口；path/query 逐字保留（包括大小写、百分号及尾斜杠），拒绝 userinfo/fragment。**Feed URL 必须保留 query；DOI URL 当前拒绝 query，两条规则并列而方向不同。**

Feed 发现键为 `(feed_id, entry_id, item_fingerprint)`；缺 entry ID 拒绝，不自造 fallback。无 DOI 版本的连续身份仅 `(feed_id, entry_id)`，内容 A→B 不生成新版本。`item_fingerprint` 为提交的单个原始 item 全部字节的 SHA-256 小写十六进制，无域前缀，等于 payload blob 身份；不重序列化、不补 XML 声明。空字节、超限、整份 Feed 文档、两个 item 共用同字节受控拒绝。可实现边界：受控提交须声明单 item，拒绝可识别的整份文档包装，并核对已登记条目与 payload 身份，避免同一 payload 被冒充另一条目；A6 不验证任意 XML 的上游真实性，也不实现生产 XML 解析。跨 Feed 同一 DOI 复用版本但保留独立发现；两个不同 item 可以各有不同字节。

相同字节重放仅推进 `last_seen=max(last_seen, observed_at)`，`first_seen` 取首次登记值后永不变。更早重放不改变两者。重新解析不增原始发现，保留所有解释，只有最高整数 parser_version 参与仲裁。

Feed 同源排序只用不可变的首次 `observed_at` 和稳定 tie-break。A→B→A 第三次只推进 A 的 last_seen，规范值停在 B；last_seen 永不参与仲裁、不会单独形成版本修订。跨 Feed 同为最低优先级，也按 observed_at 和稳定 tie-break，不是“先发现者获胜”。这项回摆限制是已批准取舍。

## 5. 规范文本、字段与仲裁

### 5.1 文本规范形式 v1（N1）

题名、摘要及作者字符串在服务端仅将 CRLF/CR 统一成 LF，再去首尾 Unicode 空白（与 `str.strip()` 一致，包括全角空格、制表符和换行）；内部空白不折叠，内部制表符和连续三个换行保留，不做 Unicode 归一化、翻译、截句或去 HTML。原字节保留，provenance 记录 `text_norm=1`。外围差异归一后相同；内部排版差异仍能改变规范值与指纹，A5 builder 不再清洗。

观察中的题名摘要必须已经是无 HTML 标签的已解析文本，含真正标签、注释等标记受控拒绝 `invalid_text`，不得默默剥除。数学比较 `a < b`、`x > 0` 不是 HTML，须接受；`<p>摘要</p>`、`<!-- comment -->` 拒绝，不能用“含尖括号就拒绝”的近似实现。A6 不是 HTML 解析器，对 `<String>` 这类标签形状无法可靠区分泛型与标记，因此 `List<String>`、`Array<int>` 也受控拒绝；这是明确的输入能力限制，不做已知 HTML 标签白名单放宽。数学比较与 `T <: Number` 保持接受；B 首次真实解析器及 C 扩展仍须以真实材料核对该边界。固定向量包括 CRLF/CR、全角空格、制表符、连续换行、数学比较与标签边界。孤立代理字符在登记时拒绝。规范后纯空白候选视为缺项，不能覆盖非空事实；不套用模型输出占位词表删除 “No abstract available”。

### 5.2 字段与优先级

受控字段为题名、摘要整体、有序原样作者字符串列表、期刊、字符串卷/期/页（含 eLocator）、在线发布日期、卷期印刷日期、单值来源 URL。日期按两个独立语义字段各自仲裁，精度是该日期字段的属性（年/月/日），不把在线/印刷语义混在同键候选里。日期缺失不伪造。ORCID、引用次数等未知字段整笔 `unsupported_field`。`authors=()` 表示整个作者字段缺项；非空作者列表中任一成员规范后为空白仍整笔 `invalid_observation`，不删除非法成员或放宽成员规则。

摘要来源与取得时间从获选摘要候选所属观察派生，不接受独立候选；摘要标记未知不默认为 false，映射返回 `truncation_unknown`。人工摘要修正必须同时给非空文本与标记，不能只改标记；确认完整是同文本加 false 的新修正。截断检测器不在 A6。

字段优先级：人工明确修正 > 目标版本出版者结构化事实 > 对应 DOI 注册机构 > 目标版本 Feed，不跨版本填缺。注册机构查询 DOI 必须等于版本已登记 DOI，不联网核验 Crossref/DataCite 路由归属。非人工先按来源流内 observed_at 排序，再用 payload SHA-256、parser_version 和封闭来源流键作为稳定 tie-break，绝不用 recorded_at、rowid 或插入顺序；同一材料重解析只由最高有效非空完整解释的整数 parser_version 参与；全空解释沿用第 3 节 not_retained 保护。跨流同优先级也采用相同稳定比较。只要获选值或 provenance 改变就追加修订，即使文本相同；相同观察不重复修订。

人工修正带调用方提供的非空 request_id，在目标 version_id 内唯一；精确重试复用原结果、同 request_id 异内容整笔 invalid_manual_correction。新修正按每个版本事务内分配的显式递增事件序号排序，最新者胜，先后本身是语义。修正绑定 version_id，预印本升级正式版后不迁移，当前值可回到正式出版者值；trace 须明示。actor/reason 只是调用方给的未认证审计字符串，不是认证用户身份。A6 无产品写入/撤销入口，误修正只能通过服务追加更高序号非空修正覆盖并保留历史；空白修正拒绝，不代表清除。期望修正跟随 Paper 需另行裁决。

修订号在该版本写事务内 `max+1`，唯一约束保护 `(version_id, revision_no)`。历史读取必须以整个修订取逐字段引用，不允许调用方拼出从未同时成立的字段组合。

取得事实另有版本内写事务分配的递增 `event_no`，修订引用触发取得；两者只证明当次修订形成时已经保留的取得集合，不进入非人工获选优先级。只读校验按该历史取得集合复用纯获选规则，逐字段比较完整候选引用，并校验规范候选集合摘要，拒绝同版本错获选候选、缺字段与候选篡改。规范候选摘要不替代原始来源字节核验。

## 6. 权威版本关系与当前选择（N2）

提供的公共输入为 `ObservationInput.relations: tuple[RelationInput, ...]`；每项封闭字段
`{kind, source_doi, target_doi, locator}`，kind 只收 `is-preprint-of/has-preprint`。
前者 source 是预印本，后者 source 是正式版；两者先规范 DOI 并归一为预印本→正式版。
观察 DOI 必须是其中一端，version_kind 必须匹配该端，双方已有版本的类别也须匹配。
locator 必须非空、无敏感 URL 包装；不联网证明来源真实性。同一 DOI 在全部已保留和待入关系中必须保持同一端点类别，即使尚未登记版本；跨请求角色矛盾整笔 `invalid_relation`，已有矛盾事实由共享只读语义校验拒绝为 `corrupt_reference`，不修复历史。

仅接受出版者/DOI 注册机构且有 locator 的预印本 DOI→正式版 DOI 关系。`is-preprint-of/has-preprint` 先归一同一个方向再判重；Feed、人工断言、未知关系、自指、类别方向不符和目标不一致拒绝。关系独立保存，另一端可尚未登记，关系本身不创建空版本。

规范关系身份全局唯一于 `(preprint_doi, journal_doi)`，不同来源、不同方向和 locator 的原始断言
经取得引用关联同一个事实。每条引用保留 raw_source_doi/raw_target_doi/raw_kind、locator 与来源流/取得时间/parser/payload hash，
原始书写不参与身份键或 StageInput。首次新关系保留真实 source_snapshot；后来仅复用关系的取得可只保留哈希，
若该次也未新增字段材料，其断言 artifact_id 为 null、response_bytes_retained 为 false，不假称保留了新响应字节。若字段材料已登记保留，断言引用该真实字段制品且标志为 true；关系-only 和字段复用加新关系的保留标志同样为 true。字段与规范关系共同参与贡献判断：新增关系即 retained，
不能因字段候选相同提前丢弃。精确重试返回原结果；同流同材料同 parser 的规范字段/关系解释须恒定。
更高 parser 不会撤销已保留关系；关系事实没有撤销或 active 标志。

空字段加关系是 relation-only：允许两端均未登记，不创建任何版本、修订或选择。
注册机构在这一关系入口可省略既有 target，仍须 query_key DOI 等于观察 DOI；
其后真实关系端点到达也可省略 target。普通无关系且 DOI 不涉及保留关系的 registry 仍须明确既有 target。
显式 target 始终核对强身份，不借关系绕过。Feed 不能声明关系，但其真实新 DOI 版本同样消费已保存的权威关系；
已有无 DOI Feed 版本补登记 DOI 不迁移既有 Paper，若关系跨 Paper 则成功返回 requires_merge。

新版本到达查询全部已保留关系，唯一确定已有 Paper 才加入；预印本先到、正式版先到、关系先到最终身份关系同构，不要求随机 UUID 一致。关系三态为“端点尚未出现”“两端分属不同 Paper（等待合并）”“已生效”，生效由端点归属派生，不存可漂移 active 位，不建冲突表。两端不同 Paper 或新版本同时关联多个 Paper 时，观察/关系照常保存，无法唯一归属的新版本独立建 Paper，返回已保留成功结果 `requires_merge`，不迁移既有版本。

选择事件只支持初始选择 `initial` 与正式版升级 `journal_upgrade`，按 Paper 内原子递增 event_no 读取，不能按时钟或 UUID 猜顺序。正式版即使无摘要、无卷期也成为当前，映射如实缺项，预印本摘要不搬过去；同级歧义维持已有选择并披露。重复观察不增选择事件。不开放人工选版本、人工归入 Paper、替代关系或 merge/undo；人工字段修正保留。trace 的“未生效版本关系（等待合并）”必须列出对端 DOI、已有对端 Paper、来源/locator 与原因；端点未出现独立措辞，不伪造 UUID。

`trace.relations` 提供规范两端 DOI、可空端点 Version/Paper、派生 state
（endpoint_missing/requires_merge/effective）、首次来源/locator/制品及全部 assertions 原始断言（含该次响应登记保留标志与可空真实制品引用）。
双方 Paper 查询同一关系得到一致结果；`trace.selection_conflicts` 列出与当前同级但未替换当前的版本。
每个版本 view 的 selection 只关联该版本真实被选事件，未曾选过为 null。

追加 `a604_version_relations` 建立实际关系/取得引用表与全局规范边唯一约束，给选择追加显式事件序号并允许正式升级，
取得回执保存原 result_reason。a601–a603 不变；非空升级完整保留历史事实。
A6 交付时备份 head 跟随 a604，当前 head 见[备份 Contract](backup-restore.md)；
校验关系、原始断言、locator、制品与取得闭包；两端未齐、跨 Paper 和已生效都合法。

## 7. 写入结果、事务与首次真实 Feed 硬门禁（D4）

强身份冲突 `identity_conflict` 拒绝成功业务行：不写发现、来源观察、候选、关系、修订或选择；独立保存不可变冲突观察及 `source_snapshot` 引用，回执返回 `conflict_id`。细分类别固定为 `doi_owner_conflict`、`target_mismatch`、`version_kind_conflict`、`entry_doi_changed`。关系冲突 `requires_merge` 则观察及关系已保留，是成功结果；`not_retained` 是有效且未新增来源材料/候选正文的独立结果，轻量取得与必要修订已经保存。结果类型须区分 retained/not_retained/rejected，携带 reason_catalog 版本、reason 与可选冲突类别，不用一个失败布尔值混同三者。`requires_merge` 是本次 DOI 涉及既有跨 Paper 关系的成功提示，优先于 `not_retained`，不是 Paper 的主 status，也不声称本次新增了关系或响应材料。普通元数据取得和候选复用均可返回该提示；是否登记材料由独立的 `response_bytes_retained` 表达。精确旧请求永远重放原回执，不按当前关系重算。

**首次真实 Feed 导入前必须完成强身份冲突观察持久化，B 先交付 JGR 所需切片、C 扩展；此前适配器不得直接复用 A6 拒绝路径为生产写入。** A6 没有真实 Feed，仅数据库身份/幂等入口及离线测试调用方，因此当前丢失窗口为空，这也是推迟持久化唯一成立依据。B/C 接入时必须逐类别验证冲突仍有可查询原始观察，避免正式论文被漏掉；A6 的细分类受控结果为适配器保留扩展点，不能将拒绝混作 not_retained。

写事务 `BEGIN IMMEDIATE`，沿用既有 5 秒 busy_timeout，服务内部无重试循环；耗尽返回 `database_busy`，调用方决定稍后显式重试。读查询显式 `BEGIN` 固定一致读视图，不能依赖 legacy pysqlite 的 SELECT 自动开事务。一次查询中的身份、当前选择、修订、候选、provenance 必须同一视图；来源制品 I/O 在业务写事务之外。发布后/业务事务中/提交后未返回三类故障均可安全重试，最多完整孤立来源制品，无半条成功事实。

## 8. 当前查询、历史重建与只读 CLI

服务当前入口是 paper_id（最新选择→版本→最新完整修订），历史入口是 version_id/revision_no，两者互斥；另明确 snapshot_id，从同数据库 `load_config_snapshot(database, snapshot_id)` 加载，不接受外部拼装快照代替登记核对。revision 属于 version，version 属于相应 Paper；业务依据携带 paper_id、version_id、revision_no、适用选择事件、逐字段 provenance、snapshot_id。

公共入口 `PaperFacts(database).map_screening_inputs(*, snapshot_id, paper_id=None, version_id=None, revision_no=None)` 为只读服务。`snapshot_id` 必须是完整小写 SHA-256；明确当前 `paper_id` 与历史 `version_id/revision_no` 互斥，复用同连接 `resolve_revision` 校验。调用方不能提交 `RuntimeConfigSnapshot` 替代登记身份。先在同一个显式 BEGIN 论文读事务中核对 `runtime_config_snapshots` 登记，再经公共 `load_config_snapshot` 的独立只读连接重建不可变配置；不读取当前 selector 或材料文件。

`mapping_result` v1 是 `ScreeningMappingResult`，固定字段为 `format_version=1`、`snapshot_id`、`evidence`、`boundary`、`value`。`boundary`/`value` 各为 `StageMappingResult`，固定 `{value, reason, evidence, snapshot_id}`：成功 `value` 为既有 `StageInput`、`reason=null`；失败 `value=null`、`reason` 为第 9 节 `PaperReason`。两个阶段独立调用 A5 builder；共用 ScreeningFacts，缺题名/摘要或未知截断同时阻断两阶段；配置投影分别判断，boundary 未就绪不阻止已就绪 value，反之亦然。

`MappingEvidence` 包含完整 `RevisionView` 的 `paper_id/version_id/revision_no/version_kind/doi/fields/selection`，另带明确 `snapshot_id` 和固定 `source_bytes_verified=false`。`fields` 为该完整修订全部字段及逐字段 provenance，不只取输入子集；`selection` 只能是请求版本的实际适用选择，也可为 null，不表示该修订创建时曾是当前。业务事实尚未成功解析时 evidence=null；已解析事实但缺快照/输入/配置就绪时保留真实 evidence，不凭失败造依据。缺项优先级为 missing_title、missing_abstract、truncation_unknown；快照未在同库登记为 snapshot_not_found，登记后无法重建或引用链损坏为 corrupt_reference。业务 ID、DOI、来源时间、选择事件和书目字段均不进入载荷哈希。文本相同而来源/取得时间/provenance 改变，指纹不变。结果、evidence 与 StageInput 的 repr 隐藏题名、摘要和配置正文；载荷与显式字段访问仍是敏感业务数据。

历史重建从完整旧修订与明确旧快照重新 `build_stage_input`，不调用 A5 `replay_stage_input`，不保存 StageInput 载荷或独立期望指纹；未来任务层仍负有规范载荷持久化义务。不存 original_title_is_zh、不派生 ValuePredictionContext（该事实的取值规则见 [ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)，由登记侧提供，不在本文映射中产生）。可靠来源 URL 与完整 metadata_ready 属后续 eligibility，不因映射成功而宣称路线尝试、模型、校准就绪。映射只读，不推进 last_seen、不升级选择。

普通映射仅核对数据库引用链、候选→观察→同一版本及已登记制品 kind=source_snapshot，不全量哈希 blob，不读当前文件补历史。backup verify 与显式 trace 字节核验承担实际字节验证。

CLI 目标固定为 `paper show PAPER_ID --database PATH` 与 `paper trace PAPER_ID --database PATH`，两者共用可选 `--data-root PATH`、`--json`、`--show-abstract`。database 必须指向既有数据库，data-root 在来源字节核验时指向既有制品根；json 输出与文本同一受控形状，show-abstract 才展开摘要，trace 中未获选摘要也只在此显式选项下展示。选项不得初始化目录或数据库。不加历史选择器、snapshot 参数、输入指纹或任何写入命令。show 显示 `paper_id/version_id/revision_no/version_kind/doi`、当前题名/书目、摘要是否存在与截断状态、当前选择依据；trace 显示全部版本/修订/选择、Feed 发现及 first_seen/last_seen、来源与 parser_version/locator、未获选候选、关系三态及人工修正不跨版本限制。默认不展开摘要/原始响应；显式展示论文文本仍不暴露 Profile、Prompt、密钥或任意 blob。

`paper trace PAPER_ID --verify-source-bytes` 默认关闭，增加只读制品 I/O，只报原因与受控位置，不转储来源正文。开启时必须同时提供 `--data-root`，遗漏在数据库 I/O 前作为参数错误退出 2；直接服务调用缺制品根返回 `invalid_observation`（`data_root`）。读取接口保留 `StorageError` 的缺库、未初始化、旧 revision 等环境原因及中文指引，不将其改成业务引用损坏；写入和映射结果的封闭原因形状保持不变。退出码固定：正常只读查询（含合法等待端点/等待合并）0，受控拒绝/缺失/损坏/忙 1，CLI 参数语法错误 2。requires_merge 若出现在服务写入结果中是 retained 成功，不按拒绝重试。help 用中文、可复制示例，说明只读/零模型配额；空目录 help 无配置、数据库或网络副作用。

## 9. `reason_catalog` v1

以下原因目录及指引是现行权威边界；其基线文字保留，不将其误标为历史验收记录。

本表为待实现单一枚举和中文文案表的权威；后续首张代码票在新包定义一次，不扩展 storage/errors.py。名称或含义改动须升版本。错误、repr、日志和离线证据不带题名摘要、原响应、Profile、Prompt 或凭据；原因可带受控字段路径/ID，但不可插入原始输入。

| reason | 含义与边界 | 中文下一步 |
| --- | --- | --- |
| `unsupported_form` | DOI/URL 包装超出支持；是输入能力边界，不是论文无效 | 请改用受支持的裸 DOI 或规范 URL |
| `invalid_doi` | 本规则下 DOI 结构、编码或长度非法；不是论文无效或联网核验结论 | 请核对 DOI 字面值 |
| `identity_conflict` | 强身份冲突整笔拒绝，附第 7 节类别；不是无贡献或关系待合并 | 请核对已登记身份，勿自动换绑 |
| `requires_merge` | 本次 DOI 涉及已保留跨 Paper 关系，成功且等待合并，优先于 not_retained；不代表本次新增材料或 Paper 主状态 | 请查看 trace 的等待合并依据 |
| `not_retained` | 有效但空或候选复用，不新增来源材料观察；轻量取得与必要修订已保存，不是冲突或失败响应记录 | 无需重试相同内容 |
| `truncation_unknown` | 获选摘要完整性标记未知；不默认完整 | 请补充文本和明确截断标记 |
| `database_busy` | 5 秒有界锁等待耗尽，业务未部分提交 | 请在写入结束后显式重试 |
| `config_not_ready` | 该阶段已登记配置投影未就绪；不是校准失败 | 请补齐该阶段配置 |
| `corrupt_reference` | 业务引用链、归属、制品 kind 或显式核验字节损坏；不是合法未齐端点 | 请停止使用该批次并检查备份 |
| `missing_title` | 选定版本无非空题名 | 请补齐该版本题名 |
| `missing_abstract` | 选定版本无非空摘要，不跨版本借用 | 请补齐该版本摘要 |
| `paper_not_found` | 请求 Paper 未登记 | 请核对论文 ID |
| `version_not_found` | 请求版本未登记 | 请核对版本 ID |
| `revision_not_found` | 版本下请求修订不存在 | 请核对版本及修订号 |
| `snapshot_not_found` | 配置快照未在同库登记 | 请使用已登记配置快照 |
| `unsupported_scheme` | scheme 不是 doi | 请使用 DOI，其他标识待后续支持 |
| `unsupported_source` | 来源类别/路径尚未支持 | 请使用当前已实现来源入口 |
| `unsupported_field` | 存在未支持字段，整笔拒绝 | 请移除未支持字段后重交 |
| `unsupported_relation` | 关系类别/来源不支持，整笔拒绝 | 请使用出版者或注册机构的预印本到正式版关系 |
| `invalid_observation` | 封闭类型、UTC 时间、parser_version、原始字节、重试内容或目标形状非法 | 请核对受控字段与单条原始材料 |
| `invalid_text` | 孤立代理字符、HTML 标记等非法文本 | 请先解析为无 HTML 的合法文本 |
| `missing_entry_id` | Feed 条目缺上游稳定身份 | 请由适配器提供真实 entry ID |
| `invalid_feed_url` | Feed URL 不在规范规则内 | 请提供受支持的 Feed 端点 URL |
| `invalid_relation` | 自指、方向/类别或观察目标不符 | 请核对关系两端与来源定位 |
| `invalid_manual_correction` | 空白、仅改标记或不合法序号等修正 | 只能用非空完整值追加覆盖，不能清除或撤销 |

## 10. 备份、增长与未验证来源假设

只追加、不设保留期、不清理孤立 blob、不压缩修订；未来 retention/compaction 单独设计并维护备份闭包。每个代码切片同步非空 backup create/verify/restore，语义校验只在副本/恢复目录执行，不回写源库、不修复删除。合法无 DOI 版本、尚缺关系端点、跨 Paper 等待合并各有正例，不能报损坏。错误归属、item fingerprint/payload 不符、跨版本 provenance、坏候选、坏 blob/错 kind 必须受控拒绝，即使外键合法、外层哈希重算也不能通过。旧 a405 批次仍须匹配旧程序恢复后显式升级，不在批次中迁移；新程序拒绝 unsupported_revision。

隔离恢复从活跃 WAL 备份，禁原目录访问、独立目录恢复并搬迁，新进程只持受控 ID/修订/配置引用及独立预期，不从请求文件带原题名摘要，仍由恢复库候选重建相同输入。恢复不激活、抓取、重算、清理或续跑。

首次真实解析器从 B 接入、C 扩展，parser_version 每次升级必须先通过固定样本回归，声明字段减少并检查关键字段变化；不得无声明地减少关键字段。A6 只校验完整解释声明和可检测的一致性，真实解析器是否诚实、升级实际损失与运行成本均未验证，不得用离线类型检查替代此硬门禁。

以下均未在 A6 验证，B 对首条 JGR 路径、C 对四刊扩展逐项回填已核实/已证伪/仍未验证，并将固定来源材料纳入其验收：JGR/QJRMS guid 裸 DOI 覆盖；Wiley `?af=R` 落地页行为；页码实际为 eLocator；适配器给出的摘要截断标记可靠性；entry ID 跨抓取稳定性；Crossref `is-preprint-of/has-preprint` 真实供给。评论里的 170/170 不替代本组证据。A6 NOT_ASSESSED 必须包括这些来源假设、真实来源、截断检测、merge/undo、arXiv/PMID、metadata_ready/eligibility、任务/预算、完整可见性、RPC、Docling、NAS及完整阶段 A；stage_a_verified/live_verified/rpc_verified=false。

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

A7-02 任务层已持久化 boundary/value 规范输入与请求依据，见[任务 Contract](screening-tasks.md)。
论文事实包只公开既有连接级 `resolve_revision` 供调用方在 BEGIN 后复核一致性，
不反向依赖任务服务，不新增语言事实、预算或执行资格。

#111 将首次真实写入责任前移到 B，C 扩展；实验根也是真实写入，不豁免强冲突观察、最终接口或隔离恢复，见 [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。历史 A6 结论不因此获得 live 证明。

## 相关

依据：[#67](https://github.com/MeteoBoy4/PaperRadar/issues/67)、[#68](https://github.com/MeteoBoy4/PaperRadar/issues/68)、[#69](https://github.com/MeteoBoy4/PaperRadar/issues/69)、[#70](https://github.com/MeteoBoy4/PaperRadar/issues/70)、[#71](https://github.com/MeteoBoy4/PaperRadar/issues/71)、[#72](https://github.com/MeteoBoy4/PaperRadar/issues/72)、[#73](https://github.com/MeteoBoy4/PaperRadar/issues/73)、[#74](https://github.com/MeteoBoy4/PaperRadar/issues/74)、[#75](https://github.com/MeteoBoy4/PaperRadar/issues/75)、[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111)。

[规格 §3](../../intent/draft.md#三领域模型与不变量)；[ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)；[路线图 Feed/C](../roadmap.md#module-feed)。


## 强身份冲突证据公共服务

`PaperFacts(database, data_root).conflicts(conflict_id=..., feed_id=..., entry_id=...,
paper_id=...)` 返回不可变冲突摘要；所有参数可省略，组合参数共同过滤。
没有安全 Paper 关联时按 Feed/entry 或 conflict_id 查询，不能创建虚构 Paper。
摘要包含受控冲突类别、中文说明、原 DOI、来源时间、parser_version、来源制品与
原字节 SHA-256，以及当时可确定的版本集合；默认不展开题名、摘要或原始材料。
`conflict_bytes(conflict_id)` 显式取得原字节；`conflict_assertion(conflict_id)`
显式展开完整原断言（含字段 locator、显式目标及关系）。

冲突请求按完整解析断言与原字节哈希去重，精确重放返回原冲突回执；材料、时间或解释
变化保留独立记录。来源制品在业务事务外发布；冲突记录及引用原子提交后才返回
conflict_id。事务失败可能留下完整未引用制品，不代表冲突已登记。
已有无贡献响应的发布规则继续适用，拒绝材料不会成为获选字段。

迁移 `feed01_identity_conflicts` 在 `a1001_fixture_audit` 后追加独立冲突表，
保留非空数据库及原取得回执。冲突来源字节及断言完整性纳入 `validate_all()`、
备份与隔离恢复；损坏引用返回 `corrupt_reference`。恢复不依赖原根目录。
这是离线工程边界；真实 JGR 来源假设仍由路线图 EXP-1/B 核实。
