<a id="论文事实-contracta6"></a>

# 论文事实 Contract

提供 DOI 身份、Feed 发现、四类来源仲裁、人工字段修正、完整历史读取、权威版本关系与正式版升级、Screening 输入映射及强身份冲突证据服务。本文描述确定性论文事实边界，不授予任务、模型、校准或实验资格。

## 1. 范围与格式

公共格式版本如下；同一版本的名称与语义保持固定：

| 名称 | 版本 | 含义 |
| --- | --- | --- |
| `paper_facts` | 1 | 封闭论文事实公共边界 |
| `doi_rules` | 1 | 本文 DOI 接受集合与规范化 |
| `text_norm` | 1 | 规范文本规则 |
| `feed_item_fingerprint` | 1 | 原始 item 字节完整 SHA-256 |
| `reason_catalog` | 1 | 第 9 节原因名称与语义 |
| `mapping_result` | 1 | 第 8 节逐阶段映射返回形状 |

本文只接 DOI、明确的既有 Paper/Version、Feed 发现和出版者结构化、DOI 注册机构、Feed、人工字段修正观察。不接受 arXiv/PMID、自由 scheme 或关系类型、HTTP 状态、失败响应、任意 JSON 属性；未开放字段或关系整笔拒绝，不忽略后当作成功。来源取得及 HTTP 结果由[Feed 取得](feed-ingestion.md)和[元数据补充](feed-metadata.md)服务承载，不是 `PaperFacts.submit` 的输入。

论文事实服务承载确定性规则与事务边界；CLI 和来源适配器调用公共服务。纯 DOI/文本/仲裁/版本规则不依赖 storage 或 SQLAlchemy；config、screening、stage_inputs 不反向导入论文事实服务；事实服务不导入 HTTP/LLM/Docling/外部适配器。

<a id="11-69-出版者切片与公共边界"></a>

### 1.1 公共服务与观察输入

公共 Python 边界为 `paper_radar.papers.PaperFacts(database, data_root=None)`；`database` 指向既有且已显式迁移至当前 revision 的数据库，`submit/correct` 必须提供制品根 `data_root`（制品发布可创建受控目录，构造本身不执行 I/O）：`submit(observation)` 接受严格 `ObservationInput` 或其字段字典，返回 `WriteResult`；`show(paper_id)` 返回当前 `PaperView`，`trace(paper_id, verify_source_bytes=False)` 返回 `PaperTrace`，`validate_all()` 只读校验完整引用与历史修订。所有公开模型 repr/str 隐藏论文内容；服务验证错误只返回受控原因，不透传 Pydantic 输入载荷。原始 `ObservationInput.source_kind`/`RelationInput.kind` 保持字符串，关系项在纯规则层校验，未知值分别返回 `unsupported_source`/`unsupported_relation`；规范事实与仲裁内部使用封闭领域类型，`NormalizedRelation` 另外保留 `raw_*` 原断言。模型 `model_validate*` 将最终校验失败转换为 `PaperError`；直接构造使用脱敏 `ValueError` 参与 Pydantic 联合候选回退，保证合法日期字典可选中 `DateValue`。

`submit` 的 `source_kind` 只接受 `publisher/registry/feed`，人工修正使用独立 `correct` 入口。字段候选是 `{value, locator}`；摘要 value 是 `{text, is_truncated, rule}`，日期 value 是 `{value, precision}`，作者使用有序字符串 tuple。`version_kind` 为 `preprint/journal`，`observed_at` 为明确 UTC datetime，`parser_version` 为严格正整数，必填 `interpretation="complete"` 声明整份材料的完整解释，`payload` 为单份非空 bytes，`fields` 必填但可为空。

观察输入的默认值为 `scheme="doi"`、`provider=""`、`query_key=""`、`relations=()`；`feed_id/entry_id/payload_scope/target_paper_id/target_version_id` 默认 `None`。`doi` 必须显式给出，只有 Feed 可为 `None`。显式目标 Paper/Version 必须成对提供，只用于核对身份。非 Feed 的 provider/query_key 必须为非空合法文本，各最多 2048 UTF-8 字节；不得提供 Feed 专用字段。每个候选 locator 必须为非空合法文本且最多 2048 UTF-8 字节；摘要 rule 必须非空。类型严格、额外属性拒绝，Python 字段字典不做字符串到布尔、整数或时间的宽松转换。

<a id="12-70-feed-发现切片"></a>

### 1.2 Feed 发现输入与读取

`register_feed(url) -> FeedFact` 按规范 URL 幂等返回数据库登记的 `feed_id/url`；非法 URL 为 `invalid_feed_url`。该登记不要求 `data_root`，也不授予生产端点资格。
`submit` 的 Feed 形状使用 `source_kind="feed"`、真实 `feed_id`、非空原样 `entry_id`、
显式 `payload_scope="single_item"`、`doi: str | None`，其余时间、完整解释、候选及原文边界沿用公共模型。
Feed 调用方不能自行设置 provider/query_key；持久化来源流由 feed_id/entry_id 确定，稳定排序使用规范 Feed URL/entry_id。
缺 entry ID 为 `missing_entry_id`；entry 原样保留，须为合法 UTF-8、非空且最多 2048 字节，
写入口与备份引用校验复用同一权威。无效 UUID/未登记 Feed、缺单 item 声明、可识别整份 Feed 或多 item 包装为 `invalid_observation`。
原文 fingerprint 全局绑定同一个 `(feed_id, entry_id)`，不能把相同字节冒充另一条目；不实现任意 XML 真实性识别。

`WriteResult.discovery_id` 指向原始发现；重放返回该解释原结果，只把 last_seen 推进到最大时点。
首次发现即使没有字段，也保留真实版本、完整修订与原文观察；其中首次无 DOI/无字段条目建立无 DOI 版本和空字段修订；
已有原文的全空高版本解释则 `not_retained`，不替换已有字段解释，但保留解析版本门禁和回执。
解释首个请求时间另行保留以区分 parser 升级后的旧请求精确重试与新的低版本请求；
非人工仲裁仍只用原文不可变 first_seen，不使用该请求时间或 last_seen。

`trace.discoveries` 展示发现 ID、版本、Feed UUID/规范 URL、entry ID、fingerprint、原文制品、
first_seen/last_seen 与全部保留解释观察 ID；interpretations 同时公开每个 parser_version 的首个 submitted_at、
acquisition_id 和可空 observation_id（包括全空解释）。完整字段来源仍在 observations/acquisitions 中。
`show` 继续只展示规范事实。文本查询简明显示原题名/身份/受控来源摘要，JSON 与文本均声明
“仅覆盖论文事实；尚未计算完整任务资格”；默认不输出 item 或摘要全文。

出版者、注册机构和 Feed 的取得事实包含 `raw_doi`，保留首次登记请求的原始 DOI 书写，不参与身份键或 StageInput。
已有 a601 事实该列为 NULL，如实表示当时未记录，不能用规范 DOI 冒充原书写；Feed 无 DOI 时也为 NULL。
已登记请求的精确重试继续返回原回执，不因换 DOI 包装而改写原拼写。
备份只读校验全部 Feed 登记（包括尚无发现的 Feed）、entry 输入域、连续归属、原文 fingerprint/blob、解释、取得、候选和修订闭包；
发现时间与解释提交时间须为微秒 UTC，首次解释 submitted_at 等于 first_seen，last_seen 不得早于任何已登记解释的 submitted_at。

<a id="13-71-四类来源仲裁人工修正与公共历史读取"></a>

### 1.3 注册机构、人工修正与公共历史读取

`submit` 接受多个 publisher 来源流，以及 `source_kind="registry"`。普通注册机构输入必须提供
既有 `target_paper_id/target_version_id`，`doi` 与 `query_key` 都按 `doi_rules=1` 规范化后相等，
并且等于目标版本已登记 DOI；不会替无 DOI 版本登记身份，不联网判定 Crossref/DataCite 的真实归属。关系路径可省略既有目标的例外见 §6。
来源流是 `(source_kind, provider, query_key, version_id)`；Feed 稳定键使用规范 URL/entry_id。
`parser_version` 最高解释按来源流与 payload 隔离，不受其他流同字节或高 parser 影响。

`correct(correction) -> WriteResult` 接受严格 `ManualCorrectionInput` 或字段字典，固定字段为
`version_id/request_id/actor/reason/fields`。`fields` 沿用 CandidateInput；只覆盖提供的非空字段。
request_id/actor/reason 必须是合法无 HTML 非空 UTF-8 文本，逐项最多 2048 字节。
request_id 在版本内唯一；完整原请求按 UTF-8、排序 JSON 对象键、无额外空白规范字节绑定请求哈希，
包括 actor/reason、locator、原始候选文本；完整请求最多 8 MiB。相同请求精确重试返回原回执，异内容为
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

完整性校验包含注册机构查询 DOI、人工事件归属与来源原请求对照（显式字节核验和备份），并拒绝外键合法的跨版本候选损坏。当前数据库 revision 与备份格式由[备份 Contract](backup-restore.md)维护。

## 2. Paper、版本与 DOI 身份（D1）

Paper 只表示稳定 UUID，不保存题名、DOI、当前版本或主流程状态。一个 DOI 恰好绑定一个版本，标识同时绑定一致的 `paper_id/version_id`；一个版本最多一个 DOI，全局 `(scheme, normalized_value)` 唯一，scheme 封闭为 `doi`。同 DOI 恒命中同一 Paper/Version，不存在“同 DOI 多公开形态”入口。`preprint/journal` 是创建后不可变的身份类别；online-first 是尚缺卷期页码的 journal，补卷期或改摘要只追加同版本修订。

不同 DOI 的版本只有可回查的权威版本关系才能归属同一 Paper。相似题名、作者、年份、URL 不自动合并、不生成候选记录。显式目标入口只核对既有身份，不能给它挂新 DOI。唯一 DOI 补登记路径是已有无 DOI Feed 版本的新 item 提供未占用 DOI；条目从 X 变 Y、显式目标不符、类别变化、Y 已属别的 Paper 均 `identity_conflict`。X 后续消失仍保留 X。

### 2.1 DOI 规则 v1（D2）

原始包装输入先检查最多 8192 UTF-8 字节，避免无界外围处理；再去外围 Unicode 空白，所得输入与规范值均最多 2048 UTF-8 字节，空值、超长、孤立代理字符、内部空白或 Unicode 控制/格式字符拒绝。只将 ASCII A–Z 折为 a–z，其他 Unicode 原样保留，不做 casefold、NFC/NFKC、翻译、截句或联网核验。

支持裸 DOI、ASCII 大小写不敏感的 `doi:` 前缀、HTTP(S) `doi.org/dx.doi.org` URL。只去外围空白，不再去 `doi:` 后空白，故 `DOI:10.1234/AbC` 接受、`doi: 10.1234/a` 拒绝为 `invalid_doi`。URL scheme/host 不区分 ASCII 大小写；允许相应默认端口（http 80、https 443），拒绝 userinfo、非默认端口、www 子域、尾点主机、双包装与任何 query/fragment（包含空 `?/#` 包装）为 `unsupported_form`。

URL path 去单个起始 `/` 后严格进行一次 UTF-8 百分号解码；错误转义或无效 UTF-8 为 `invalid_doi`。`%2F` 可解为 DOI 分隔斜杠，`%25` 得字面 `%` 且不再解码，`+` 不变。裸 DOI 不百分号解码，其中字面 `?/#/%` 可为后缀，不作为 URL 参数。结构为 `10.` 加非空 ASCII 数字段（可有以点分隔的非空数字细分段）、`/` 和非空后缀；不套用“4–9 位注册前缀”的经验式。不删末尾标点或尾斜杠，后缀 Unicode 大小写相异仍不同。

规范化示例： `HTTPS://DOI.ORG:443/10.1234/AbC` → `10.1234/abc`、`10.1234/Ä` 保留 Ä、`https://doi.org/10.1234%2FA%252F` → `10.1234/a%2f`、裸 `10.1234/a?b#c/` 原样保留后缀；合法 DOI 的 2048 字节边界接受，2049 字节拒绝。

`unsupported_form` 是输入包装超出能力，`invalid_doi` 是本规则下结构非法；拒绝都不表示论文无效。DOI 规范化不从 query 构造 DOI。生产落地页提取属于[Feed 取得契约](feed-ingestion.md)，不改变这里的 DOI 接受集合。

## 3. 四类来源事实与发布

- **来源快照**：`source_snapshot` 内容寻址制品，只有字节内容身份，不含提供方、取得时间或业务目标；制品格式见[制品 Contract](artifact-store.md)。
- **来源观察**：来源类别、提供方、查询键/条目身份、`observed_at`、整数 `parser_version`、目标版本、来源快照引用、字段候选及 locator；Feed 发现是它在 Feed 上的特化。
- **字段候选**：观察中的一个受控字段值、locator 与规则身份，未获选者也保留；摘要是文本、截断标记/未知及判断规则身份的整体。
- **版本修订**：某版本在一次仲裁后全部规范字段的完整状态，以 `(version_id, revision_no)` 标识，逐字段只存获选候选引用与规则版本，不复制整段摘要。缺项用无获选候选表达，不造 NULL/空串值行。

只接非空原始 `bytes`，单份上限 8 MiB，不接调用方“已核验引用”。解析结果由调用方给出、规则由服务确定。先以现有 `ArtifactStore.publish_single` 完整发布来源制品，再提交业务事务；制品已发布但业务失败可以留下完整未引用 `source_snapshot`，重试复用。未引用制品不是已持久化冲突观察，服务不自动清理它。

publisher/注册机构来源流为 `(来源类别, 提供方, 查询键, 目标版本)`。不可变的轻量**取得事实**记录有效请求：每个有效请求记录原始响应 SHA-256、取得时间、parser_version、解释摘要与原结果；相同规范候选集合复用同流历史来源观察及候选引用，不重复保存候选正文，也不发布该次非业务变化响应的大包制品。`response_bytes_retained` 表示该次响应已作为字段或关系来源材料登记保留，内容对象即使去重也为 true；它不表示物理新增 blob，也不表示创建了字段观察。字段材料所属请求与关系材料取得引用分别核验。取得事实明确 `response_bytes_retained=false` 时只保存该响应的哈希，原始来源引用仍指向确实保留的旧材料，不宣称保存了新响应全文。新候选集合才先发布完整原始来源制品，再写入来源观察/候选与取得事实。

精确重试键固定为 `(来源类别, 提供方, 查询键, 规范 DOI, observed_at, payload SHA-256, parser_version)`，不依赖之后创建的 Paper/Version；retained、not_retained 和空候选均登记不可变原结果。相同键及解析内容返回原 acquisition_id、身份、当时修订号与状态；同键异解析内容 `invalid_observation`。首次空候选没有版本/来源引用，不创建空 Paper，不发布空贡献响应，即使日后该 DOI 创建不同类别版本，原请求仍回放原结果。强身份冲突保存独立冲突事实，不登记成功取得事实；其余拒绝不登记取得事实。

`not_retained` 表示没有新增来源材料观察或候选正文，**不表示未持久化任何业务事实**。它可以新增轻量取得事实，并在获选取得 provenance 改变时追加引用式修订。A(t1)→A(t3)→B(t2晚到) 与 A(t1)→B(t2)→A(t3) 均获选 t3 的 A；每次取得使用自身不可变 observed_at、响应 SHA-256、parser_version 参与确定性仲裁。候选引用仍指向旧观察，取得时间/解析依据与原始材料的取得时间分开展示，不能把候选原属观察时间改成新时间。只读发布计划可先找同流同集合依据，ArtifactStore 发布仍在业务写事务之外，写事务重新核对；并发最多留下完整未引用制品，无内部忙锁重试循环。Feed 使用第 4 节首次时间与回摆规则，不能套用本段 publisher 取得时序。

同一 `(来源流, payload SHA-256)` 的 parser_version 单调。已登记请求的精确重试优先返回原结果；新的降版本请求 `invalid_observation`。同一材料、同一 parser_version 的解析字段/locator 也必须恒定，不能借更换 observed_at 偷换解释；需要变化时提升 parser_version。取得事实保存完整声明与解析内容摘要供语义检查，声明本身不是对真实解析器的认证。

更高 parser_version 的**有效非空完整解释**整体替换同材料的旧解释：新解释未提供的字段属于“该解释不含此字段”，旧解释不再参与当前仲裁，因而当前修订可以缺项；其他有效材料/来源仍可按各自优先级补充。旧候选与旧修订保留不变。这与不同 payload 的新观察不对称：不同字节之间仍是缺项不清空，不能把同材料解释替换说成可用缺失撤销字段。

**全空候选集合是明确例外**：v2 全空返回 not_retained，只保留轻量取得原结果与版本门禁，不替换当前规范字段、不形成清空修订；首次空请求仍不创建 Paper，不以空回执派生字段清空影响。此后新的低 parser 请求仍受单调门禁约束，而精确旧请求继续回原结果。

完整解释是调用方的必要承诺，服务拒绝缺失声明、明确 partial/economical 声明以及可检测的降版本/同版本异解释；不能仅从字段减少断定违规，也不声称能识别声明撒谎的真实解析器。论文事实服务不认证调用方真实解析器；生产解析和固定回归范围见[Feed 取得契约](feed-ingestion.md)与[parser 证据](../verification/feed-parser-v1.md)，真实来源核实责任见 §10。

304、限流、失败在 `ObservationInput` 中不可表达，不产生成功来源观察；JGR 生产取得将这些执行结果保存在独立 Feed 检查历史，见[Feed 取得契约](feed-ingestion.md)。轻量取得只记录有效解析请求，不成为通用请求/HTTP 日志框架。

当前来源 URL 与 URL 形式的查询键/提供方/locator 拒绝 userinfo、query（含空 `?`）和 fragment（含空 `#`），不猜测参数名或 opaque 查询键里的 secret；这是防止认证 URL 进入查询面的严格初版能力边界，不表示 URL 可靠性/eligibility 已核验。原始材料按来源发布规则保留。这条规则不能用于 Feed 端点 URL，第 4 节 Feed query 必须逐字保留。

所有时钟事实统一 UTC，精度固定到微秒；输入须明确 UTC 时区，不接受 naive 时间。观察时刻、选择/修订时间和 first_seen/last_seen 与发布日期分开；发布日期按语义和精度保存，不伪造时钟。

## 4. Feed 身份、发现与回摆（D3）

Feed 唯一身份权威是数据库按规范 URL 的唯一登记，`feeds` 保存 UUID 和规范 URL。语言来源在独立不可变关联中登记期刊归属，生产检查独立保存 ETag、Last-Modified 和取得结果；两者引用既有 Feed，不创建第二套身份权威。不提供 feeds.yaml 或真实导入 CLI。规范 URL 接受 HTTP(S)，scheme/host ASCII 小写、移除默认端口；path/query 逐字保留（包括大小写、百分号及尾斜杠），拒绝 userinfo/fragment、空白/控制字符、非法或空端口及超过 8192 UTF-8 字节的输入；合法非默认端口保留。**Feed URL 必须保留 query（包括空 `?`）；DOI URL 当前拒绝 query，两条规则并列而方向不同。**

Feed 发现键为 `(feed_id, entry_id, item_fingerprint)`；缺 entry ID 拒绝，不自造 fallback。无 DOI 版本的连续身份仅 `(feed_id, entry_id)`，内容 A→B 不生成新版本。`item_fingerprint` 为提交的单个原始 item 全部字节的 SHA-256 小写十六进制，无域前缀，等于 payload blob 身份；不重序列化、不补 XML 声明。空字节、超限、整份 Feed 文档、两个 item 共用同字节受控拒绝。可实现边界：受控提交须声明单 item，拒绝可识别的整份文档包装，并核对已登记条目与 payload 身份，避免同一 payload 被冒充另一条目；论文事实服务不验证任意 XML 的上游真实性。生产 XML 解析由[Feed 取得服务](feed-ingestion.md)负责。跨 Feed 同一 DOI 复用版本但保留独立发现；两个不同 item 可以各有不同字节。

相同字节重放仅推进 `last_seen=max(last_seen, observed_at)`，`first_seen` 取首次登记值后永不变。更早重放不改变两者。重新解析不增原始发现，保留所有解释；只有最高有效解释参与仲裁，全空高版本不替换已有字段解释（见 §1.2、§3）。

Feed 同源排序只用不可变的首次 `observed_at` 和稳定 tie-break。A→B→A 第三次只推进 A 的 last_seen，规范值停在 B；last_seen 永不参与仲裁、不会单独形成版本修订。跨 Feed 同为最低优先级，也按 observed_at 和稳定 tie-break，不是“先发现者获胜”。这项回摆限制是已批准取舍。

## 5. 规范文本、字段与仲裁

<a id="51-文本规范形式-v1n1"></a>

### 5.1 文本规范形式 v1（N1）

题名、摘要及作者字符串在服务端仅将 CRLF/CR 统一成 LF，再去首尾 Unicode 空白（与 `str.strip()` 一致，包括全角空格、制表符和换行）；内部空白不折叠，内部制表符和连续三个换行保留，不做 Unicode 归一化、翻译、截句或去 HTML。原字节保留，provenance 记录 `text_norm=1`。外围差异归一后相同；内部排版差异仍能改变规范值与指纹；阶段输入构造的精确文本规则见[StageInput Contract](stage-inputs.md)。

观察中的题名摘要必须已经是无 HTML 标签的已解析文本，含真正标签、注释等标记受控拒绝 `invalid_text`，不得默默剥除。数学比较 `a < b`、`x > 0` 不是 HTML，须接受；`<p>摘要</p>`、`<!-- comment -->` 拒绝，不能用“含尖括号就拒绝”的近似实现。论文事实服务不是 HTML 解析器，对 `<String>` 这类标签形状无法可靠区分泛型与标记，因此 `List<String>`、`Array<int>` 也受控拒绝；这是明确的输入能力限制，不做已知 HTML 标签白名单放宽。数学比较与 `T <: Number` 保持接受。孤立代理字符在登记时拒绝。规范后纯空白候选视为缺项，不能覆盖非空事实；不套用模型输出占位词表删除 “No abstract available”。

### 5.2 字段与优先级

受控字段为 `title`（题名）、`abstract`（摘要整体）、`authors`（有序原样作者字符串 tuple）、`journal`（期刊）、字符串 `volume/issue/pages`（卷/期/页，含 eLocator）、`online_date/print_date`（在线发布日期/卷期印刷日期）、`source_url`（单值 HTTP(S) 来源 URL）。日期按两个独立语义字段各自仲裁；`precision=year/month/day` 分别要求有效日历值 `YYYY/YYYY-MM/YYYY-MM-DD`，不把在线/印刷语义混在同键候选里。日期缺失不伪造。ORCID、引用次数等未知字段整笔 `unsupported_field`。`authors=()` 表示整个作者字段缺项；非空作者列表中任一成员规范后为空白仍整笔 `invalid_observation`，不删除非法成员或放宽成员规则。

摘要来源从获选候选所属观察派生，`observed_at/parser_version` 使用获选取得依据，`source_observed_at` 保留原材料观察时间，不接受独立“摘要来源/取得时间”候选；摘要标记未知不默认为 false，映射返回 `truncation_unknown`。人工摘要修正必须同时给非空文本与标记，不能只改标记；确认完整是同文本加 false 的新修正。本文事实服务不检测截断；生产来源的检测规则见[元数据契约](feed-metadata.md)。

字段优先级：人工明确修正 > 目标版本出版者结构化事实 > 对应 DOI 注册机构 > 目标版本 Feed，不跨版本填缺。注册机构查询 DOI 必须等于版本已登记 DOI，不联网核验 Crossref/DataCite 路由归属。非人工先按来源流内 observed_at 排序，再用 payload SHA-256、parser_version 和封闭来源流键作为稳定 tie-break，绝不用 recorded_at、rowid 或插入顺序；同一材料重解析只由最高有效非空完整解释的整数 parser_version 参与；全空解释沿用第 3 节 not_retained 保护。跨流同优先级也采用相同稳定比较。摘要长度或截断标记不提升低优先级候选，因此高优先级疑似截断摘要仍可获选，不能把获选等同完整。只要获选值或 provenance 改变就追加修订，即使文本相同；相同观察不重复修订。

人工修正带调用方提供的非空 request_id，在目标 version_id 内唯一；精确重试复用原结果、同 request_id 异内容整笔 invalid_manual_correction。新修正按每个版本事务内分配的显式递增事件序号排序，最新者胜，先后本身是语义。修正绑定 version_id，预印本升级正式版后不迁移，当前值可回到正式出版者值；trace 须明示。actor/reason 只是调用方给的未认证审计字符串，不是认证用户身份。论文事实 CLI 无写入/撤销入口，误修正只能通过服务追加更高序号非空修正覆盖并保留历史；空白修正拒绝，不代表清除。不提供修正随当前版本迁移的入口。

修订号在该版本写事务内 `max+1`，唯一约束保护 `(version_id, revision_no)`。历史读取必须以整个修订取逐字段引用，不允许调用方拼出从未同时成立的字段组合。

取得事实另有版本内写事务分配的递增 `event_no`，修订引用触发取得；两者只证明当次修订形成时已经保留的取得集合，不进入非人工获选优先级。只读校验按该历史取得集合复用纯获选规则，逐字段比较完整候选引用，并校验规范候选集合摘要，拒绝同版本错获选候选、缺字段与候选篡改。规范候选摘要不替代原始来源字节核验。

## 6. 权威版本关系与当前选择（N2）

提供的公共输入为 `ObservationInput.relations: tuple[RelationInput, ...]`；每项封闭字段
`{kind, source_doi, target_doi, locator}`，kind 只收 `is-preprint-of/has-preprint`。
前者 source 是预印本，后者 source 是正式版；两者先规范 DOI 并归一为预印本→正式版。
观察 DOI 必须是其中一端，version_kind 必须匹配该端，双方已有版本的类别也须匹配。
locator 规范后必须非空且最多 2048 UTF-8 字节、无敏感 URL 包装；不联网证明来源真实性。同一 DOI 在全部已保留和待入关系中必须保持同一端点类别，即使尚未登记版本；跨请求角色矛盾整笔 `invalid_relation`，已有矛盾事实由共享只读语义校验拒绝为 `corrupt_reference`，不修复历史。

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

新版本到达查询全部已保留关系，唯一确定已有 Paper 才加入；关系可先于端点保留，已保留关系按相同规则处理预印本或正式版先到的情形，不要求随机 UUID 一致。关系晚于双方独立登记时不合并既有 Paper。关系三态为“端点尚未出现”“两端分属不同 Paper（等待合并）”“已生效”，生效由端点归属派生，不存可漂移 active 位，不建关系冲突状态表。两端不同 Paper 或新版本同时关联多个 Paper 时，观察/关系照常保存，无法唯一归属的新版本独立建 Paper，返回已保留成功结果 `requires_merge`，不迁移既有版本。

选择事件只支持初始选择 `initial` 与正式版升级 `journal_upgrade`，按 Paper 内原子递增 event_no 读取，不能按时钟或 UUID 猜顺序。正式版即使无摘要、无卷期也成为当前，映射如实缺项，预印本摘要不搬过去；同级歧义维持已有选择并披露。重复观察不增选择事件。不开放人工选版本、人工归入 Paper、替代关系或 merge/undo；人工字段修正保留。trace 的“未生效版本关系（等待合并）”必须列出对端 DOI、已有对端 Paper、来源/locator 与原因；端点未出现独立措辞，不伪造 UUID。

`trace.relations` 提供规范两端 DOI、可空端点 Version/Paper、派生 state
（endpoint_missing/requires_merge/effective）、首次来源/locator/制品及全部 assertions 原始断言（含该次响应登记保留标志与可空真实制品引用）。
双方 Paper 查询同一关系得到一致结果；`trace.selection_conflicts` 列出与当前同级但未替换当前的版本。
每个版本 view 的 selection 只关联该版本真实被选事件，未曾选过为 null。

关系、原始断言、locator、制品与取得引用共同进入完整性校验；两端未齐、跨 Paper 和已生效都合法。备份闭包与恢复规则见[备份 Contract](backup-restore.md)。

<a id="7-写入结果事务与首次真实-feed-硬门禁d4"></a>

## 7. 写入结果与事务（D4）

强身份冲突 `identity_conflict` 拒绝成功业务行：不写发现、来源观察、候选、关系、修订或选择；独立保存不可变冲突观察及 `source_snapshot` 引用，回执返回 `conflict_id`。细分类别固定为 `doi_owner_conflict`、`target_mismatch`、`version_kind_conflict`、`entry_doi_changed`。关系冲突 `requires_merge` 则观察及关系已保留，是成功结果；`not_retained` 是有效且未新增来源材料/候选正文的独立结果，轻量取得与必要修订已经保存。`WriteResult.status` 区分 `retained/not_retained/rejected`，固定 `reason_catalog_version=1`，不以一个失败布尔值混同三者。其他固定字段为 `reason/conflict/paper_id/version_id/revision_no/observation_id/acquisition_id/discovery_id/conflict_id`，无适用值时为 `None`。`requires_merge` 是本次 DOI 涉及既有跨 Paper 关系的成功提示，优先于 `not_retained`，不是 Paper 的主 status，也不声称本次新增了关系或响应材料。普通元数据取得和候选复用均可返回该提示；是否登记材料由独立的 `response_bytes_retained` 表达。精确旧请求永远重放原回执，不按当前关系重算。

强身份冲突通过[冲突证据公共服务](#强身份冲突证据公共服务)回查，不混作 `not_retained`。JGR 生产取得保存冲突引用；这一工程接线不证明真实来源、四刊生产或 B 实验就绪，责任见[路线图 B](../roadmap.md#module-b)与[C](../roadmap.md#module-c)。

写事务 `BEGIN IMMEDIATE`，沿用既有 5 秒 busy_timeout，服务内部无重试循环；耗尽返回 `database_busy`，调用方决定稍后显式重试。读查询显式 `BEGIN` 固定一致读视图，不能依赖 legacy pysqlite 的 SELECT 自动开事务。一次查询中的身份、当前选择、修订、候选、provenance 必须同一视图；来源制品 I/O 在业务写事务之外。发布后/业务事务中/提交后未返回三类故障均可安全重试，最多完整孤立来源制品，无半条成功事实。

<a id="8-当前查询历史重建与只读-cli"></a>

## 8. 当前查询、历史重建与只读 CLI

服务当前入口是 paper_id（最新选择→版本→最新完整修订），历史入口是 version_id/revision_no，两者互斥；另明确 snapshot_id，从同数据库 `load_config_snapshot(database, snapshot_id)` 加载，不接受外部拼装快照代替登记核对。revision 属于 version，version 属于相应 Paper；业务依据携带 paper_id、version_id、revision_no、适用选择事件、逐字段 provenance、snapshot_id。

公共入口 `PaperFacts(database).map_screening_inputs(*, snapshot_id, paper_id=None, version_id=None, revision_no=None)` 为只读服务。`snapshot_id` 必须是完整小写 SHA-256；明确当前 `paper_id` 与历史 `version_id/revision_no` 互斥，复用同连接 `resolve_revision` 校验。调用方不能提交 `RuntimeConfigSnapshot` 替代登记身份。先在同一个显式 BEGIN 论文读事务中核对 `runtime_config_snapshots` 登记，再经公共 `load_config_snapshot` 的独立只读连接重建不可变配置；不读取当前 selector 或材料文件。

`mapping_result` v1 是 `ScreeningMappingResult`，固定字段为 `format_version=1`、`snapshot_id`、`evidence`、`boundary`、`value`。`boundary`/`value` 各为 `StageMappingResult`，固定 `{value, reason, evidence, snapshot_id}`：成功 `value` 为既有 `StageInput`、`reason=null`；失败 `value=null`、`reason` 为第 9 节 `PaperReason`。两个阶段独立调用 `build_stage_input`；共用 ScreeningFacts，缺题名/摘要或未知截断同时阻断两阶段；配置投影分别判断，boundary 未就绪不阻止已就绪 value，反之亦然。

`MappingEvidence` 包含完整 `RevisionView` 的 `paper_id/version_id/revision_no/version_kind/doi/fields/selection`，另带明确 `snapshot_id` 和固定 `source_bytes_verified=false`。`fields` 为该完整修订全部字段及逐字段 provenance，不只取输入子集；`selection` 只能是请求版本的实际适用选择，也可为 null，不表示该修订创建时曾是当前。业务事实尚未成功解析时 evidence=null；已解析事实但缺快照/输入/配置就绪时保留真实 evidence，不凭失败造依据。缺项优先级为 missing_title、missing_abstract、truncation_unknown；快照未在同库登记为 snapshot_not_found，登记后无法重建或引用链损坏为 corrupt_reference。业务 ID、DOI、来源时间、选择事件和书目字段均不进入载荷哈希。文本相同而来源/取得时间/provenance 改变，指纹不变。结果、evidence 与 StageInput 的 repr 隐藏题名、摘要和配置正文；载荷与显式字段访问仍是敏感业务数据。

历史重建从完整旧修订与明确旧快照重新 `build_stage_input`，不调用 `replay_stage_input`；本文映射不保存 StageInput 载荷或独立期望指纹。规范输入的任务登记与持久化见[任务 Contract](screening-tasks.md)，阶段配方及载荷格式见[StageInput Contract](stage-inputs.md)。本文映射不保存 `original_title_is_zh`，也不派生 `ValuePredictionContext`；语言事实生产与组合登记由[Feed 组合契约](feed-pipeline.md)负责。映射不检查可靠来源 URL、适用路线完成或完整 eligibility，不因映射成功而宣称元数据、模型、校准就绪；元数据最低完整性见[元数据契约](feed-metadata.md)，完整资格由[路线图 C](../roadmap.md#module-c)承接。映射只读，不推进 last_seen、不升级选择。

普通映射仅核对数据库引用链、候选→观察→同一版本及已登记制品 kind=source_snapshot，不全量哈希 blob，不读当前文件补历史。backup verify 与显式 trace 字节核验承担实际字节验证。

CLI 命令为 `paper show PAPER_ID --database PATH` 与 `paper trace PAPER_ID --database PATH`，两者共用可选 `--data-root PATH`、`--json`、`--show-abstract`。database 必须指向既有数据库，data-root 在来源字节核验时指向既有制品根；json 输出与文本同一受控形状，show-abstract 才展开摘要，trace 中未获选摘要也只在此显式选项下展示。所有可选布尔开关默认关闭，`data-root` 默认 `None`；选项不初始化目录或数据库。不提供历史选择器、snapshot 参数、输入指纹或任何写入命令。show 显示 `paper_id/version_id/revision_no/version_kind/doi`、当前题名/书目、摘要是否存在与截断状态、当前选择依据；trace 显示全部版本/修订/选择、Feed 发现及 first_seen/last_seen、来源与 parser_version/locator、未获选候选、关系三态及人工修正不跨版本限制。默认不展开摘要/原始响应；显式展示论文文本仍不暴露 Profile、Prompt、密钥或任意 blob。

`paper trace PAPER_ID --verify-source-bytes` 默认关闭，增加只读制品 I/O，只报原因与受控位置，不转储来源正文。开启时必须同时提供 `--data-root`，遗漏在数据库 I/O 前作为参数错误退出 2；直接服务调用缺制品根返回 `invalid_observation`（`data_root`）。读取接口保留 `StorageError` 的缺库、未初始化、旧 revision 等环境原因及中文指引，不将其改成业务引用损坏；写入和映射结果的封闭原因形状保持不变。退出码固定：正常只读查询（含合法等待端点/等待合并）0，受控拒绝/缺失/损坏/忙 1，CLI 参数语法错误 2。requires_merge 若出现在服务写入结果中是 retained 成功，不按拒绝重试。help 用中文、可复制示例，说明只读/零模型配额；空目录 help 无配置、数据库或网络副作用。

## 9. `reason_catalog` v1

单一枚举与中文指引由 `paper_radar.papers.errors.PaperReason/GUIDANCE` 定义，名称或含义改动须升版本。错误、repr、日志和离线证据不带题名摘要、原响应、Profile、Prompt 或凭据；原因可带受控字段路径/ID，但不可插入原始输入。

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
| `invalid_manual_correction` | 空白、仅改标记、请求 ID 异内容、超限或非法修正 | 只能用非空完整值追加覆盖，不能清除或撤销 |

## 10. 备份、增长与未验证来源假设

论文事实历史只追加，不设保留期、不清理孤立 blob、不压缩修订；制品清理的后续责任见[路线图 I](../roadmap.md#module-i)。备份在固定副本上、恢复在独立目录中执行论文语义校验，不回写源库或修复删除。合法无 DOI 版本、尚缺关系端点、跨 Paper 等待合并不报损坏。错误归属、item fingerprint/payload 不符、跨版本 provenance、坏候选、坏 blob/错 kind 受控拒绝，即使外键合法、外层哈希重算也不能通过。备份格式、数据库 revision 准入和旧批次恢复程序匹配规则见[备份 Contract](backup-restore.md)。

隔离恢复保留完整候选、取得、修订、选择和关系引用；从恢复库的明确历史修订及已登记配置可重建相同 boundary/value 输入，不依赖原目录或请求文件中的题名摘要。后补 DOI 是当前身份登记，不冒充历史冻结 DOI；从未获选版本的历史 selection 为 null。恢复不激活、抓取、重算、清理或续跑。

论文事实服务校验完整解释声明及可检测的一致性，不认证真实解析器是否诚实，也不证明升级实际字段损失或运行成本。生产 parser 固定回归范围见[parser 证据](../verification/feed-parser-v1.md)，真实材料、每次升级的字段差异审查及四刊扩展责任见[路线图 B](../roadmap.md#module-b)与[C](../roadmap.md#module-c)。

以下来源假设仍缺真实来源证明，不能由合成材料或历史 170/170 陈述推定成立：JGR/QJRMS guid 裸 DOI 覆盖；Wiley `?af=R` 落地页行为；页码实际为 eLocator；适配器给出的摘要截断标记可靠性；entry ID 跨抓取稳定性；Crossref `is-preprint-of/has-preprint` 真实供给。首条 JGR 路径的核实由[Audit](../roadmap.md#module-audit)、[Source](../roadmap.md#module-source)和[B](../roadmap.md#module-b)承接，四刊扩展由[C](../roadmap.md#module-c)承接。

本文不提供 merge/undo、arXiv/PMID、人工 DOI/URL/PDF 导入 CLI 或完整 eligibility/visibility；相关身份及四刊资格由[路线图 C](../roadmap.md#module-c)承接。事实映射不执行任务或模型；执行边界见[任务](screening-tasks.md)与[Pi RPC](pi-rpc.md)，正文与 Read 由[Body](../roadmap.md#module-body)承接，NAS 与完整最终验收由[I](../roadmap.md#module-i)承接。离线事实闭环不证明真实来源、RPC、Docling、NAS、B 实验或完整阶段 A 就绪。

<a id="11-实施与验收约定"></a>
<a id="69-重解析裁决的跨票验证归属"></a>
<a id="74-组合恢复证明尚未注册-a6"></a>
<a id="75-最终独立验收"></a>

## 11. 历史证据入口

原实施图、跨票验证归属、组合恢复证明与最终独立验收约定见[迁存历史](../verification/contracts-paper-facts-history.md#11-实施与验收约定)。逐次离线证明范围见[最终 A6 规格对照](../verification/a6-requirements.md)，当前验收结果读取边界见[验证状态 Contract](verification-status.md)。历史结论不授予当前运行或 live 资格。

## 强身份冲突证据公共服务

`PaperFacts(database, data_root).conflicts(conflict_id=..., feed_id=..., entry_id=...,
paper_id=...)` 返回不可变冲突摘要 tuple；所有参数可省略（默认 `None`），组合参数共同过滤，无匹配返回空 tuple。
没有安全 Paper 关联时按 Feed/entry 或 conflict_id 查询，不能创建虚构 Paper。
摘要包含受控冲突类别、中文说明、原 DOI、来源时间、parser_version、来源制品与
原字节 SHA-256，以及当时可确定的版本集合；默认不展开题名、摘要或原始材料。
`conflict_bytes(conflict_id)` 显式取得原字节；`conflict_assertion(conflict_id)`
显式展开完整原断言（含字段 locator、显式目标及关系），在同一一致读事务中核验引用与读取断言。查询摘要也核验来源字节，存在冲突记录时必须提供 `data_root`；缺根、缺失或损坏引用返回 `corrupt_reference`。显式原文入口的 ID 不存在同样返回 `corrupt_reference`，不伪造空原文。

冲突请求按完整解析断言与原字节哈希去重，精确重放返回原冲突回执；材料、时间或解释
变化保留独立记录。来源制品在业务事务外发布；冲突记录及引用原子提交后才返回
conflict_id。事务失败可能留下完整未引用制品，不代表冲突已登记。
已有无贡献响应的发布规则继续适用，拒绝材料不会成为获选字段。

冲突来源字节及断言完整性纳入 `validate_all()`、备份与隔离恢复；损坏引用返回 `corrupt_reference`。恢复不依赖原根目录。迁移 `feed01_identity_conflicts` 保留非空数据库及原取得回执；当前 head 见[备份 Contract](backup-restore.md)。真实 JGR 来源假设的核实责任见[路线图 Audit](../roadmap.md#module-audit)与[B](../roadmap.md#module-b)。

## 相关

依据：[#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)、[#115](https://github.com/MeteoBoy4/PaperRadar/issues/115)、[#67](https://github.com/MeteoBoy4/PaperRadar/issues/67)、[#68](https://github.com/MeteoBoy4/PaperRadar/issues/68)、[#69](https://github.com/MeteoBoy4/PaperRadar/issues/69)、[#70](https://github.com/MeteoBoy4/PaperRadar/issues/70)、[#71](https://github.com/MeteoBoy4/PaperRadar/issues/71)、[#72](https://github.com/MeteoBoy4/PaperRadar/issues/72)、[#73](https://github.com/MeteoBoy4/PaperRadar/issues/73)、[#74](https://github.com/MeteoBoy4/PaperRadar/issues/74)、[#75](https://github.com/MeteoBoy4/PaperRadar/issues/75)、[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111)。

- 规格：[§3](../../intent/draft.md#三领域模型与不变量)、[§4.2–4.4](../../intent/draft.md#42-feed-抓取)；决策依据：[ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)、[ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
- 组件：[来源制品](artifact-store.md)、[配置历史](config-snapshots.md)、[StageInput](stage-inputs.md)、[任务](screening-tasks.md)、[备份恢复](backup-restore.md)。
- 取得与组合：[Feed](feed-ingestion.md)、[元数据](feed-metadata.md)、[Feed 组合](feed-pipeline.md)；后续责任：[B](../roadmap.md#module-b)、[C](../roadmap.md#module-c)。
- 历史证据：[迁存原文](../verification/contracts-paper-facts-history.md)、[A6 规格对照](../verification/a6-requirements.md)、[Feed 离线工程证据](../verification/issue-114-feed-delivery.md)。
