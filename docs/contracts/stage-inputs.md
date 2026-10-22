# 阶段输入载荷与指纹（#47 / #48 / #49 / #50 / #51 / #52 / #53 / #54）

## 公共边界与交付范围

公共入口从 `paper_radar.stage_inputs` 导入。当前交付 boundary/value/extraction/reuse
各自独立格式 **1**；reuse 的封闭来源联合包含结构化来源与正文来源，可显式组合。
本票补全预定 reuse 格式 1，不发布另一份过渡生产格式；read/suggestion 不属于本次 A5。
未领取的阶段、字符串冒充 `StageName` 或未知阶段均受控拒绝，不产生占位指纹。

| 入口 / 类型 | 契约 |
| --- | --- |
| `ScreeningFacts(title=..., abstract=..., abstract_truncated=...)` | 冻结的精确论文文本与严格布尔事实；未知字段拒绝。 |
| `ExtractionFacts(pdf_sha256=...)` | 冻结的原始 PDF 完整字节 SHA-256；未知字段拒绝，不读取 PDF。 |
| `SourceSnapshotRef(content_sha256=..., locator=...)` | 严格结构化来源内容引用与冻结定位；不收 URL 或审计字段。 |
| `ExtractionRef(extraction_input=..., reading_sha256=..., evidence_map_sha256=..., locator=...)` | 正文来源构造只接收 extraction 输入对象，再绑定实际消费成员与冻结定位；不查询制品库。 |
| `extraction_ref.identity` | 只读的 `(extraction_fingerprint, reading_sha256, evidence_map_sha256)` 正文消费身份；不含定位。 |
| `SelectedExcerpt(excerpt_id=..., kind=..., text=..., source=...)` | 已选精确摘录；ID/种类由权威 ReuseAssessmentContext 校验。 |
| `ReuseFacts(excerpts=...)` | 非空有序冻结摘录，重复 ID 在构造调用级映射前拒绝；全部正文摘录共享同一配方与消费内容身份。 |
| `reuse_input.reuse_assessment_context()` | 仅从该输入冻结摘录派生权威 ID/种类映射；不接收外部映射。 |
| `build_stage_input(snapshot, stage, facts)` | 从已由 check/compile/load 验证的 `RuntimeConfigSnapshot` 选取同阶段 `project_config` 投影，返回不可变 `StageInput`。 |
| `replay_stage_input(payload_bytes, expected_fingerprint, snapshot=None)` | 规范载荷字节与明确期望指纹的严格回放；可选核对明确历史快照。 |
| `compare_stage_inputs(before, after)` | 返回不可变 `StageInputComparison`，只解释组件变化。 |
| `value_input.value_prediction_context(snapshot, original_title_is_zh=...)` | 验证明确快照匹配该 value 投影，再派生权威 `ValuePredictionContext`；不接收独立主题集合。 |

`StageInput` 只由 build/replay 创建，禁止直接提交未验证字段构造。只读字段为
stage、format_version、projection_format_version、projection_id、facts、payload_bytes；
`fingerprint` 为载荷原始字节完整 SHA-256。没有另一份“载荷 + 指纹”信封格式。
程序持久化时应保留规范字节和独立期望指纹；本票不保存输入文件、不增加表、migration、
artifact kind 或产品 CLI。数据库 revision 保持 `a405_pi_cleanup_execution`。

模块只通过 config 公共面消费快照、StageName、StageReadiness 与 project_config，
通过 screening 公共面消费 `ValuePredictionContext`、`ReuseAssessmentContext` 与 `ExcerptKind`，
保持既有输出 Schema 与业务规则。
编码/哈希、公共头校验、投影核对和比较前置各有一份权威实现；没有公共“投影 + 事实”
构造入口。模块不读取 YAML、数据库、制品库、文件或网络，不调用 Pi/Docling。
既有配置、Screening 输出与存储各自保持权威；本票不修改已有投影、基线或 Frozen Contract。

## boundary/value 配方与编码

规范对象包含且只包含以下五个键：

```json
{"config_projection":{"format_version":1,"projection_id":"<完整 projection_id>"},"facts":{"abstract":"<精确论文摘要>","abstract_truncated":false,"title":"<精确原题名>"},"format_version":1,"kind":"stage_input","stage":"boundary"}
```

`kind=stage_input` 分离身份域，`stage=boundary/value` 分离消费者，阶段格式与投影格式分别记录。
两阶段共用 `ScreeningFacts`，各自选择自身配置投影和 StageReadiness，身份彼此独立。
value 仅消费题名、论文摘要、截断标记及 value 投影，不要求 boundary 配置就绪或已有成功
结果；不隐式加入 boundary 输出、会话、artifact 链接、摘要提供方或额外书目字段。
主题 ID/name/description 与启用集合通过既有 value 投影传播；边界阶段不消费主题。
已配置空主题集合合法，缺少 topics 配置仍未就绪；主题权重字段不存在。
载荷只引用本阶段配置投影，不嵌入 Profile/Prompt、完整快照 ID、校准基线、文件哈希、
artifact_id 或执行实例身份。配置实际语义依赖以[配置投影契约](config-projections.md)为准。

题名与论文摘要必须是严格字符串，`str.strip()` 后非空；检查不改变原文，不应用论文占位
词表，因此 `...` 等非空文本在此层不会被当作缺项。保留 Unicode、大小写、所有首尾空白、
CRLF/LF 与次序，不做 NFC/NFD、翻译、清洗、补全或语言识别。截断标记只收 Python bool，
整数 0/1 和字符串均拒绝。孤立代理字符在 typed facts 构造时受控拒绝。

编码由本模块独立拥有：UTF-8、非 ASCII 原样、对象键排序、紧凑 JSON（`,`/`:`）、无结尾换行，
不含浮点或 NaN/Infinity，布尔和整数严格区分。阶段/投影格式是严格整数，当前均为 1。
所有哈希字段只收 64 位小写十六进制字符串，不归一化大写、`0x` 前缀或整数。
本模块不导入配置私有编码器；任何载荷字段/规范化规则/消费者语义配方变化，须提升受影响
阶段的格式，不能静默改变历史含义。

boundary 独立固定向量：完整合成载荷在
[`tests/fixtures/stage_inputs/boundary-v1.json`](../../tests/fixtures/stage_inputs/boundary-v1.json)，
使用已有非空 no-adapter boundary 配置向量（projection 格式 1，
`d67c818c67ecaf6f14361ee4f54cf771a50088c6e2d421031299b35a39c41532`），
合成题名/摘要，其阶段输入格式 1 指纹固定为
`e27f19cc566e80158680aecfcf2b3bd41a3cb07201ef6c3a4cec66b4ba11abb2`。
value 独立固定向量：完整合成载荷在
[`tests/fixtures/stage_inputs/value-v1.json`](../../tests/fixtures/stage_inputs/value-v1.json)，
使用固定 `full_inputs` 合成快照的 value 投影（格式 1，
`2fd0df2a6b58bf52ec64fcae11c27ee427bc8bac215ca87b26eb04e544318209`），
阶段格式 1 指纹为
`c8d68282f6366900ebadc342034b6ac9272bccbecd7a766e50bd480210533db0`。

期望由人工载荷字面量独立核算，不调用被测 builder 更新期望。契约只登记指纹、格式与
合成示例，不记录真实摘要、摘录或 Profile。

## 就绪、回放与身份核对

构造直接沿用 `snapshot.stages[stage]` 的已有 `StageReadiness`；缺项或 placeholder 时
以 `not_ready` 拒绝并携带原就绪事实，不补默认值或人为要求所有阶段就绪。
旧有效快照没有 adapter 时仍按原配置完整性语义判断；此时投影 adapter 为 null。
这不是 RPC 执行就绪，后续执行服务必须另查协议、参数映射、固定环境和凭据。

回放依次严格解析、核对封闭字段/身份域/阶段/格式/事实、重建规范字节、逐字节比较、
重算指纹并核对调用方提供的完整期望指纹。多余键、重复 JSON 键、不同排版、尾随换行、
隐式类型转换及未来阶段格式均拒绝。无法解析的文本和孤立代理字符不保留在错误链中。
回放不推断来源存在、不从当前 selector 补项，也不把自洽哈希当作业务来源证明。

若提供 `snapshot`，只核对该明确快照的同阶段投影：投影格式不受支持或当前程序无法按
同格式核对时为 `projection_format_unverifiable`；同格式 ID 不符为 `projection_mismatch`。
两者不同，不静默改投影、迁移、重新编译或替换历史依据。本模块独立维护封闭的历史投影
回放支持策略，当前只支持投影格式 1；配置当前写出格式提升不会自动扩大支持范围。未来
消费者须保留匹配格式的重建实现或提供显式迁移。回放证明规范身份与可选配置绑定，
不重新授予配置完整性或执行资格；新任务构造必须使用快照门面。

## 比较与受控拒绝

`status` 为 `same/changed/incomparable`。同阶段且阶段/投影格式兼容时，组件采用固定顺序：
boundary/value 按 `config_projection`、`title`、`abstract`、`abstract_truncated` 排序，
extraction 按 `config_projection`、`pdf` 排序，
reuse 按 `config_projection`、`excerpts`、`excerpt_sources` 排序，只列发生变化者。
比较不输出原文、旧/新值或自由字段名。不同阶段或格式不兼容返回不可比，细粒度配置
解释由 `compare_config_snapshots` 承担。boundary/value 跨阶段比较返回 `different_stage`，不会混用判断。

构造/回放抛 `StageInputError`；其 `.reason`、`.field` 为封闭 StrEnum，`.readiness`
仅在配置未就绪时携带已有受控配置事实。错误不保存输入值、未知键名或原始异常。
安全位置集合是 `stage/snapshot/facts/facts.title/facts.abstract/facts.abstract_truncated/facts.pdf_sha256/`
`payload/kind/format_version/config_projection/config_projection.projection_id/`
`expected_fingerprint/inputs/context/original_title_is_zh`，以及
`facts.excerpts/facts.excerpts.excerpt_id/facts.excerpts.kind/facts.excerpts.text/facts.excerpts.source/`
`facts.excerpts.source.content_sha256/facts.excerpts.source.locator/`
`facts.excerpts.source.extraction_input/facts.excerpts.source.extraction_fingerprint/`
`facts.excerpts.source.reading_sha256/facts.excerpts.source.evidence_map_sha256`；
未知键折叠为所属受控容器位置，
不含摘录下标、实际 ID 或自由键名。

| 面 | 封闭原因 |
| --- | --- |
| `BuildReason` | unsupported_stage、invalid_snapshot、not_ready、invalid_facts、invalid_text、invalid_encoding、invalid_hash、invalid_context、projection_format_unverifiable、projection_mismatch、duplicate_excerpt_id、inconsistent_extraction_source |
| `ReplayReason` | invalid_payload、unsupported_stage、unsupported_format、invalid_fingerprint、fingerprint_mismatch、non_canonical、invalid_snapshot、projection_format_unverifiable、projection_mismatch |
| `ComparisonReason` | different_stage、incompatible_format、invalid_input |

事实、结果及其载荷引用不可变，repr 隐藏文本与载荷。载荷内嵌题名、摘要与摘录，按敏感业务
数据处理，不得写入 repr、异常、stdout/stderr、普通日志或验收结论。显式 `.payload_bytes`
仅供受控业务消费。后续 RPC 只能渲染已绑定的冻结事实；渲染语义变化需 adapter policy
或阶段格式版本表达，不能额外读取未绑定字段。`original_title_is_zh` 由上游提供，属于
输出验证上下文，不进入 boundary/value 身份。

相同指纹只证明语义输入相同，不证明缓存存在、成功输出、来源合法性、校准通过或当前
任务资格。changed 不自动调度、刷新预算、判定 minor/major、撤销人工决定或改写历史分析。
指纹不含 Paper 主体；跨 Paper 是否共享成功缓存由后续资格/缓存票决定。书目字段与
执行审计字段不能作为额外事实提交；真实“论文事实 → 阶段输入”映射由后续消费者验收，目标见[论文事实 Contract](paper-facts.md)；#69 首条事实路径尚未实现该映射。

## value 同源验证上下文与扩展义务

`value_input.value_prediction_context(snapshot, original_title_is_zh=...)` 从明确快照派生
`ValuePredictionContext.enabled_topic_ids`，不接受调用方提供另一份启用主题集合。
快照必须已由 check/compile/load 验证，且其 value 投影格式与完整 ID 必须匹配该输入；
复用回放同一投影核对逻辑，但上下文派生属于构造面：非法快照、格式不可核对及投影不符
均抛 `BuildReason`，回放核对仍抛 `ReplayReason`；同名原因的字符串值相同，枚举类型
按调用面区分。普通声明标签
不同但 value 投影相同的历史快照语义等价，可以提供同源上下文。

该方法对新构造与纯载荷回放得到的 value 输入均适用；载荷不复制主题或快照包络，
因此派生上下文时始终明确提供历史快照，不读取当前 selector。启用主题 ID 派生为
不可变 frozenset，调用方修改其独立集合或后来编译新主题，不会改变已派生上下文。
边界输入不能派生 value 上下文。

`original_title_is_zh` 必须显式提供严格布尔；遗漏、字符串、整数和其他类型返回
`invalid_context` 与安全位置，不把 Pydantic 原始错误或提交值留在异常链。语言判断仅改变
权威输出校验（例如中文原题名不接受 display_title_zh），不改变阶段输入载荷或指纹。
摘要来源/提供方、阶段二 artifact 链接同样是审计引用，不是指纹分量。
`validate_output` 仍独立负责权威 Schema 与业务校验，校验通过不表示制品已发布或落库。

四阶段共同契约核对：公共头、编码/哈希、就绪与投影选择、严格回放、投影核对、
比较前置与错误格式化共用一份实现，没有按阶段复制公共载荷或通用错误规则。
ScreeningFacts、ExtractionFacts、ReuseFacts 保留各自事实与来源业务校验，
不把阶段差异扩散到新的公开构造入口。
后续阶段或来源扩展从相同 build/replay/compare 入口进入，只扩展封闭阶段集合与独立
格式、各阶段严格事实及局部一致性、固定比较组件和必要上下文派生；不改既有阶段配方，
不新增“投影 + 事实”公开入口，不引入全可选字段桶、动态注册器或通用工作流。


## 结构化 reuse 格式 1

reuse 只消费自身 `StageReadiness` 与既有 reuse 配置投影。没有 extraction 配置或正文
制品时，合法结构化来源摘录仍可构造；未被引用的 PDF、解析配置、题名摘要、阶段二
评分与旧会话不隐式加入输入。excerpt_selector_version 仅经既有投影传播，不复制规则。
生产未知算法仍被 compile 拒绝；未来算法只用于未登记的 dataclass 纯投影 fixture。

事实形状固定为 `{"excerpts":[...]}`。每项只有 excerpt_id、kind、text、source：

```json
{"excerpt_id":"availability-1","kind":"availability","source":{"content_sha256":"<payload 原始字节 SHA-256>","kind":"source_snapshot","locator":["data-availability","paragraph-1"]},"text":"Synthetic availability text"}
```

`ReuseFacts` 只收非空 list/tuple 并冻结为有序元组，集合顺序就是模型输入顺序。
`SelectedExcerpt` 的 ID/种类沿用权威 `ReuseAssessmentContext`，ID 是严格字符串、
strip 后非空但不归一化；单项只允许 availability/methods，both 是输出组合描述，
data 由上游选择器归入 methods。构造前仅限制 ID 可安全作为文本映射键及可 UTF-8
编码，不另写 ID 语义规则。重复 ID 在调用级映射生成之前拒绝，即使来自不同内容
或 locator 也不能静默合并。text 非空且精确保留，不增加占位词过滤或隐式规范化。
ID/种类语义错误分别定位 `facts.excerpts.excerpt_id` 与 `facts.excerpts.kind`；两者都非法
时先报 ID。位置判断仍委托同一权威上下文，不输出原 ID、种类值或原始校验异常。

结构化来源构造只收 content_sha256 和 locator；序列化另有固定 kind=source_snapshot
标签。哈希必须来自 `ArtifactStore.get_artifact` 返回的 source_snapshot 制品 payload
成员 SHA-256，表示成员原始字节，不使用 artifact_id。artifact_id 属于审计引用，
不进入规范载荷。相同内容哈希、定位、摘录与配置产生相同身份；不按 URL 推测等价，
而是严格拒绝 url、observed_at、artifact_id、PDF 字段或其他未知字段。一个裸合法哈希
不能证明来源存在或识别其身份域；上游须提供正确成员引用，本服务不查询库或伪造证明。

locator 是不透明、有序、非空且每项非空白的严格字符串元组；构造可接收 list 并
防御性冻结，回放从 JSON 数组重建。精确保留 Unicode、空白和次序，不收 dict、自由
JSON 或 URL 特例。locator 与面向模型的 excerpt_id 不同；来源合法取得、真实存在、
locator 可回查和摘录确属该范围均由生产者负责，不属于 A5 验收声明。

从构造或回放得到的 reuse 输入调用 `reuse_assessment_context()`，始终从同一冻结
摘录唯一派生权威 `ReuseAssessmentContext`。不能额外传入 excerpt_kinds 或另一份
摘录映射；调用方事后修改原列表或 locator 不改变指纹、载荷、比较或上下文。现有
`validate_output` 验证合法/未知引用与输出种类，成功不表示业务制品已发布。输入
对象的 repr 隐藏摘录 ID、文本与定位；错误不保留 Pydantic 原始输入或异常链。

比较中，ID/kind/text 及它们的有序序列变化归 `excerpts`，来源引用的有序序列变化
归 `excerpt_sources`。换序至少改变 excerpts；若两项来源不同，也同时改变
excerpt_sources，顺序始终固定。配置语义变化归 config_projection。比较不输出逐项
下标、ID、locator、原文或原始值。

独立固定向量在
[`tests/fixtures/stage_inputs/reuse-structured-v1.json`](../../tests/fixtures/stage_inputs/reuse-structured-v1.json)。
固定合成快照 reuse 投影格式 1、ID 为
`f2c879f0ea03e7292c028e6f7470fb0b1c78c4569ebbbb55d6e0a269520ea791`；
合成 source_snapshot payload 成员哈希为
`abdec00bc1f149e9b543ff79d5f4712097309c61136f95a2fbb52f0802139881`；
reuse 阶段格式 1 指纹为
`3c9deffa8929d61e6cb2e96582b0c7af6e3c78ec958630b8be83986684e370b4`。
完整载荷是人工字面量，期望哈希独立核算，不由 builder 生成。

后续 RPC 渲染只能使用载荷已绑定字段；需要页码、章节等时必须来自已绑定 locator，
否则需显式演进 reuse 格式。渲染策略本身变化必须有 adapter policy 或阶段格式版本。
本票不实现选段、触发规则、PDF 取得、模型或任务。正文来源沿同一来源联合接入，
共用摘录集合、ID 去重、同源上下文、reuse 构造/回放与比较，没有 PDF 专用 reuse builder。

## 正文与混合来源 reuse 格式 1

`ExtractionRef` 的公共构造接收新构造或严格回放所得的 `StageInput`，同时要求对象类型
与 `StageName.EXTRACTION`，取该对象的完整指纹作为正文配方依据。裸 PDF/来源哈希、
结构化来源对象、boundary/value/reuse 输入均拒绝。序列化来源只包含以下封闭字段：

```json
{"evidence_map_sha256":"<evidence_map 成员原始字节 SHA-256>","extraction_fingerprint":"<完整 extraction 输入指纹>","kind":"extraction","locator":["section","block-1"],"reading_sha256":"<reading 成员原始字节 SHA-256>"}
```

三个哈希均严格为 64 位小写十六进制字符串；locator 与结构化来源共用同一非空、有序、
精确保留的冻结规则。reading/evidence_map 哈希由上游从实际制品成员取得，不以整个
artifact_id 代替。manifest 的时间、耗时等审计内容、document 原始后端输出、artifact_id、
路径及另一种来源的字段一律不接收，不参与规范身份。真实 `ArtifactStore` 测试分别发布
manifest 审计字节不同的制品，验证 artifact_id 不同但相同消费内容不改变 reuse 输入；
改变 reading 或 evidence_map 实际成员则改变 reuse 指纹。

同次调用的全部正文摘录必须共享相同 extraction_fingerprint、reading_sha256 与
evidence_map_sha256。不同 extraction 指纹，或同一指纹配不同消费内容，均以
`inconsistent_extraction_source` 拒绝，不输出具体指纹、摘录 ID 或原始值。定位可以不同，
结构化来源可与这唯一一份正文显式组合；任何来源组合的重复 excerpt_id 仍先于上下文
映射构造拒绝。回放通过同一来源字段验证与调用级一致性检查，不另建宽松入口。

reuse 只核对自身配置就绪；正文依据来自明确来源对象，不读取当前 extraction 就绪状态。
切换当前 PDF 或解析配置不会静默替换旧引用；只有调用方明确换用新 extraction 输入或
新的实际消费内容，才改变对应来源依据。引用不变时，未被引用的 PDF、解析配置仍不影响
reuse；正文与结构化来源的变化也不进入题名摘要 Screening 配方。

回放里的裸哈希只能验证结构与编码，不能识别其真实来源域或证明 extraction 制品存在。
来源合法取得、质量门槛、locator 真实有效、摘录确属该正文范围及次序符合选择器优先级，
仍由生产者负责。输出验证只从同一冻结摘录派生 `ReuseAssessmentContext`，不能补入
另一份映射。正文、混合来源沿用既有固定比较组件，不新增逐项 ID、下标或定位输出。

同一 extraction 指纹若在两次独立调用中对应不同 reading/evidence_map 字节，会形成
不同 reuse 输入；同次调用则因自相矛盾拒绝。上游必须固定使用已被历史引用的那份
具体制品（[ADR-0017](../adr/0017-retain-only-source-and-analysis-bearing-artifacts.md)），
不能任取“最新”解析输出，也不能借不确定重解析不断制造新输入
以重开未来尝试预算。本服务不实现制品选择、缓存或预算。

独立合成向量沿用固定 reuse 投影格式 1、ID
`f2c879f0ea03e7292c028e6f7470fb0b1c78c4569ebbbb55d6e0a269520ea791`，
并引用已登记的 extraction 格式 1 合成指纹；期望直接按载荷字面量独立核算：

| 向量 | reuse 格式 1 指纹 |
| --- | --- |
| [正文来源](../../tests/fixtures/stage_inputs/reuse-body-v1.json) | `e2c035f114b5ae5ac7d598faea42f48dda0ac869809b1d3a25354f0bb1e978f6` |
| [混合来源](../../tests/fixtures/stage_inputs/reuse-mixed-v1.json) | `4b6c273cfefa6b83532120b7f4b8dc22e6dbf0e64ac63fa5c3f2a84872d82c62` |


## extraction 格式 1 与正文来源消费义务

extraction 的规范头与编码沿用共享实现，事实只含原始 PDF 完整字节的 SHA-256：

```json
{"config_projection":{"format_version":1,"projection_id":"<完整 extraction projection_id>"},"facts":{"pdf_sha256":"<原始 PDF 完整 SHA-256>"},"format_version":1,"kind":"stage_input","stage":"extraction"}
```

PDF 哈希由上游计算，严格为 64 位小写十六进制字符串，不做大小写转换或其他归一化。
backend descriptor、组件版本、模型材料、完整解析配置与 `normalization_version`
均经既有 extraction 投影进入，不另设事实字段。不接收题名、DOI、论文摘要、路径、下载
时间、耗时、安装/供给身份或其他额外字段。构造只检查 extraction 自身的 StageReadiness，
不要求 Screening、Profile 或模型槽就绪；无关 Screening/Profile 变化不改变此输入。

build/replay 均返回不可直接构造的 `StageInput`，其受控 `stage` 固定为
`StageName.EXTRACTION`，`facts` 为独立强类型 `ExtractionFacts`。与 Screening 的文本
事实错配会拒绝，不通过可空文本字段承载 PDF。正文来源构造 API 同时核对
`StageInput` 对象类型和 extraction 阶段，再读取其指纹；普通 PDF/来源哈希或 boundary
对象不能冒充该输入。序列化中的裸哈希无法反推出原身份域，不宣称能从哈希字节识别冒用。

服务不打开 PDF、不探测 Docling、不调用解析器，不访问数据库或制品库。构造与回放只
证明输入描述、规范编码与可选的明确历史投影绑定合法，不证明 PDF 存在、合法取得、
解析成功或正文质量门槛通过；这些仍是上游义务。

独立固定向量位于
[`tests/fixtures/stage_inputs/extraction-v1.json`](../../tests/fixtures/stage_inputs/extraction-v1.json)，
使用固定 `full_inputs` 合成快照的 extraction 投影（投影格式 1，
`b22ab98cea14fa830d125119b94c051403a7c01eced0ec526e172df74ebb0125`）与合成 PDF 哈希。
阶段输入格式 1 的指纹为
`6ca4e413c842ded79f4d244ebf278fecc62009b3599aa0cd5e7c39084566b0df`。
向量由独立载荷字面量及 SHA-256 核算固定，未用 builder 生成期望。
未来 normalization 语义只用 `dataclasses.replace` 构造不经编译登记的纯 fixture；相同
`fixture-v2` 经真实 `compile_config` 必须拒绝，不新增生产算法或第二套配置枚举校验。

### C1 已知未决问题：封面识别的论文元数据依赖

[`intent/draft.md` §4.9](../../intent/draft.md#49-docling-正文提取) 允许确定性后处理使用
规范题名、DOI、摘要或首个正文节识别仓储封面，而 extraction 格式 1 不包含这些论文
元数据。依 [#47 的 C1 用户裁决](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)，
该分歧留待阶段 F 的 normalize 实现票解决，本票不修改 §4.9 原文或扩充格式 1 配方。

阶段 F 优先仅用首个正文节、版面事实、可靠编号等文档内信号识别封面。只有四刊 fixture
证明文档内信号达不到“正文起点和前置杂页排除”质量门槛时，才允许讨论纳入论文元数据；
届时必须提升 extraction 格式（格式 2），同步修订 §12 矩阵与领域不变量中书目补全/
摘要变化不使正文提取失效的表述，并再次由用户裁决，不能由实现票自行改变。
此未决问题不改变 reuse 的内容绑定义务：正文来源同时引用 extraction 指纹与实际
消费的 reading/evidence-map 内容身份，避免把同一配方误当作具体输出字节证明。

## 隔离恢复、跨进程与后续消费者义务

#53 通过真实 compile/load、临时 SQLite、[ArtifactStore](artifact-store.md#公共服务)
与[备份/恢复公共服务](backup-restore.md#公开边界与使用)验证历史输入重建。
调用方明确传入合成规范事实、载荷和独立期望指纹；原配置、原数据库与原数据根移走后，
新进程只从恢复库加载完整历史 snapshot_id，并从恢复后的 `get_artifact` 返回记录中
重新取得 original_pdf/source_snapshot 的 payload 与 extraction 的 reading/evidence_map
成员哈希，再组装引用。测试不会把旧成员哈希或旧 StageInput 对象作为恢复事实带入。
恢复和纯计算均不隐式 compile、upgrade、安装、激活或任务续跑；恢复数据库保持 DELETE
原字节，构造、回放和比较前后不变。此路径不修改 A3 备份算法或格式。

不同 PYTHONHASHSEED、cwd、主题集合枚举及映射构造顺序均匹配同一独立固定向量；
fixture 含两个启用主题，实际顺序变化受到断言。摘录/locator 顺序、精确 Unicode、空白
与换行仍按其语义保留，不能为了跨进程稳定而归一化。四阶段共同测试还以文件、SQLite
与网络 I/O 拒绝哨兵验证纯构造/回放/比较；架构检查保持 config/screening 公共面单向依赖。
无日志设施时结合空 caplog、repr、异常和 stdout/stderr 检查敏感内容不外泄。

[恢复固定向量](../../tests/fixtures/stage_inputs/recovery-v1.json)只含合成材料，
配置投影按手写 Profile、模型默认值、冻结 Schema/manifest、Prompt、adapter 语义及两主题
独立核算；extraction/reuse 复用先前已固定的投影 ID。阶段载荷和 SHA-256 未由 builder
生成，普通测试不会重写期望：

| 案例 | 输入格式 1 指纹 |
| --- | --- |
| boundary | `2f03c2722378c7d45971c9f3629884b962b806515f8625d0159fc2392de6aac3` |
| value | `8604eb842877279a6aca4aa9174d180569ea4dc6341e90ab25fa148b070b9df7` |
| extraction | `d108b2cc6e9ebe37a6cba1e832916c5d530c3b3fee0c2e795826eeb9ebf0e56d` |
| 结构化 reuse | `8a457a1e793ada05122c1d02a718ef3969442b50f44be855fbdb80273541a6ac` |
| 正文 reuse | `63debebc1c9dc39aef214ef8e663a2b5b2a13bd15636c2cae01d37dbf8e10644` |

后续消费者须另存业务主体、明确历史快照及具体制品审计引用，并保存规范载荷与独立期望
指纹；不能改用“当前 selector”或“最新制品”重解释历史。投影格式演进须保留匹配版本
重建或提供显式迁移。RPC 只能渲染已绑定事实与 locator，新增渲染语义须有 adapter policy
或阶段格式版本。来源存在、合法取得、正文质量、定位可回查、真实摘录范围和选择器顺序
由生产者保证；本服务不代替这些检查。输入相同仍不证明成功缓存、跨 Paper 共享、任务
资格、尝试预算或校准门禁；changed 不撤销人工决定、不改写正式分析或冻结校准事实。

书目与供给身份仅通过封闭输入类型严格拒绝证明隔离，A5 当时没有论文事实模型，不宣称
“卷期页码更新到任务不重跑”已端到端验收；不为此创建 A4 安装记录。A2 的组件矩阵仍是
[配置投影契约](config-projections.md)权威，本切片只核对各阶段一个代表传播及 Read、
期刊 tier、adapter 审计版本和 screening thinking_level 的少量交叉变化。
#73 的[论文事实映射服务](paper-facts.md#8-当前查询历史重建与只读-cli)已在其独立测试中
覆盖真实登记、来源仲裁、人工修正和历史 revision/snapshot 的 boundary/value 输入重建。
该服务只读，不承担未来任务层的规范载荷持久化、任务资格或校准门禁；A5 原固定范围及
当时的 NOT_ASSESSED 历史结论保持，最终 A6 已由 #75 登记，覆盖范围与单次判据见[离线 A6 结论](../verification/offline-evidence.md#a6-独立结论6775)。
独立复现命令与验收边界见[离线证据说明](../verification/offline-evidence.md)。
#53 单独交付时没有登记 A5 验收组；#54 追加独立 A5 结论后，check-offline 输出七份
主要文件，另有实际 pytest 回执。固定范围及规格映射见
[独立 A5 结论](../verification/offline-evidence.md#a5-独立结论4754)。
A5 通过仅声明四阶段输入计算、回放、比较和隔离恢复，不代表阶段 A、真实来源、RPC、
NAS 或自动精读通过。


## 格式版本公开访问

`paper_radar.stage_inputs.STAGE_INPUT_FORMAT_VERSIONS` 是只读映射，明确列出
boundary/value/reuse/extraction 各自的当前配方版本 1；构造、回放和独立 A5 格式核对
共同消费这一份生产权威数据。调用方不能修改映射，也不能把 StageName 的其余成员
视为已支持阶段。该映射只表达阶段输入格式，配置当前投影格式由 config 维护；历史投影
回放是否受支持由本模块的封闭策略决定，核对时还要求明确快照能够重建匹配格式。
公开版本不改变任何既有载荷字节、指纹向量或配置投影配方。
