<a id="阶段输入载荷与指纹47--48--49--50--51--52--53--54"></a>

# 阶段输入载荷与指纹

<a id="公共边界与交付范围"></a>

## 用途与范围

公共入口从 `paper_radar.stage_inputs` 导入。提供 boundary/value/extraction/reuse
各自独立格式 **1**；reuse 的封闭来源联合包含结构化来源与正文来源，可显式组合。
reuse 使用格式 1，不提供另一份过渡生产格式；本边界不提供 read/suggestion。
未支持的阶段、字符串冒充 `StageName` 或未知阶段均受控拒绝，不产生占位指纹。

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
| `replay_stage_input(payload_bytes, expected_fingerprint, *, snapshot=None)` | 规范载荷字节与明确期望指纹的严格回放；可选核对明确历史快照。 |
| `compare_stage_inputs(before, after)` | 返回不可变 `StageInputComparison`，只解释组件变化。 |
| `value_input.value_prediction_context(snapshot, *, original_title_is_zh=...)` | 验证明确快照匹配该 value 投影，再派生权威 `ValuePredictionContext`；不接收独立主题集合。 |

`StageInput` 只由 build/replay 创建，禁止直接提交未验证字段构造。只读字段为
stage、format_version、projection_format_version、projection_id、facts、payload_bytes；
`fingerprint` 为载荷原始字节完整 SHA-256。没有另一份“载荷 + 指纹”信封格式。
持久化消费者保留规范字节和独立期望指纹；本服务不保存输入文件，不读写数据库，
不提供 migration、artifact kind 或产品 CLI，也不要求特定数据库 revision。
上述事实与来源构造参数均为仅限关键字的必填参数，无默认文本、哈希、定位或布尔值。

模块只通过 config 公共面消费快照、StageName、StageReadiness 与 project_config，
通过 screening 公共面消费 `ValuePredictionContext`、`ReuseAssessmentContext` 与 `ExcerptKind`，
保持既有输出 Schema 与业务规则。
编码/哈希、公共头校验、投影核对和比较前置各有一份权威实现；没有公共“投影 + 事实”
构造入口。模块不读取 YAML、数据库、制品库、文件或网络，不调用 Pi/Docling。
既有配置、Screening 输出与存储各自保持权威；此边界不修改已有投影、基线或 Frozen Contract。

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
这不是 RPC 执行就绪；调用边界见[Pi RPC 契约](pi-rpc.md)。

回放先要求 `payload_bytes` 为严格 bytes、`expected_fingerprint` 为完整小写 SHA-256，
再严格解析、核对封闭字段/身份域/阶段/格式/事实、重建规范字节、逐字节比较，
重算指纹并核对调用方提供的期望指纹。`snapshot` 默认为 None，且只按关键字提供。
多余键、重复 JSON 键、不同排版、尾随换行、
隐式类型转换及未来阶段格式均拒绝。无法解析的文本和孤立代理字符不保留在错误链中。
回放不推断来源存在、不从当前 selector 补项，也不把自洽哈希当作业务来源证明。

载荷的投影格式不受支持时，无论是否提供 `snapshot`，均以
`projection_format_unverifiable` 拒绝。若提供 `snapshot`，只核对该明确快照的同阶段投影：
当前程序无法按同格式核对时为 `projection_format_unverifiable`；同格式 ID 不符为 `projection_mismatch`。
两者不同，不静默改投影、迁移、重新编译或替换历史依据。本模块独立维护封闭的历史投影
回放支持策略，当前只支持投影格式 1；配置当前写出格式提升不会自动扩大支持范围，
本服务不迁移载荷或重建未知格式。回放证明规范身份与可选配置绑定，
不重新授予配置完整性或执行资格；新任务构造必须使用快照门面。

## 比较与受控拒绝

`StageInputComparison` 暴露 `status`、不可变元组 `changed_components` 和可选 `reason`。
`status` 为 `same/changed/incomparable`；可比时 reason 为 None，same 的组件元组为空。
无效输入返回 `incomparable/invalid_input`，不同阶段或格式不可比时组件元组也为空。
同阶段且阶段/投影格式兼容时，组件采用固定顺序：
boundary/value 按 `config_projection`、`title`、`abstract`、`abstract_truncated` 排序，
extraction 按 `config_projection`、`pdf` 排序，
reuse 按 `config_projection`、`excerpts`、`excerpt_sources` 排序，只列发生变化者。
比较不输出原文、旧/新值或自由字段名。不同阶段或格式不兼容返回不可比，细粒度配置
解释由 `compare_config_snapshots` 承担。boundary/value 跨阶段比较返回 `different_stage`，不会混用判断。

事实/来源构造、上下文派生、build/replay 的受控拒绝抛 `StageInputError`；其
`.reason`、`.field` 为封闭 StrEnum，`.readiness`
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

build 的事实类型与阶段错配为 `invalid_facts`。回放中的非法事实、来源字段、重复摘录 ID
或不一致正文来源统一为 `ReplayReason.INVALID_PAYLOAD`（`invalid_payload`），位置为 `facts`，不暴露构造面内部原因。
非规范字节为 `non_canonical`，规范字节与期望指纹不符为 `fingerprint_mismatch`。

事实、结果及其载荷引用不可变，repr 隐藏文本与载荷。载荷内嵌题名、摘要与摘录，按敏感业务
数据处理，不得写入 repr、异常、stdout/stderr、普通日志或验收结论。显式 `.payload_bytes`
仅供受控业务消费。消费载荷时不能额外读取未绑定字段；改变渲染语义需由 adapter policy
或阶段格式版本表达。`original_title_is_zh` 属于输出验证上下文，不进入 boundary/value 身份；
其生产来源由[任务登记契约](screening-tasks.md#feed-原题名语言来源)定义。

相同指纹只证明语义输入相同，不证明缓存存在、成功输出、来源合法性、校准通过或当前
任务资格。changed 不自动调度、刷新预算、判定 minor/major、撤销人工决定或改写历史分析。
指纹不含 Paper 主体，本服务不实现缓存；同库 Screening 预算与筛选制品的主体隔离见
[任务契约](screening-tasks.md#1-服务边界与身份)。书目字段与执行审计字段不能作为额外事实提交；
当前“论文事实 → 阶段输入”映射见[论文事实契约 §8](paper-facts.md#8-当前查询历史重建与只读-cli)。

<a id="value-同源验证上下文与扩展义务"></a>

## value 同源验证上下文

`value_input.value_prediction_context(snapshot, *, original_title_is_zh=...)` 从明确快照派生
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
本服务不识别 Feed 或派生语言事实；生产来源、无归属及歧义拒绝由
[任务登记契约](screening-tasks.md#feed-原题名语言来源)定义。
摘要来源/提供方、阶段二 artifact 链接同样是审计引用，不是指纹分量。
`validate_output` 仍独立负责权威 Schema 与业务校验，校验通过不表示制品已发布或落库。

四阶段共同契约核对：公共头、编码/哈希、就绪与投影选择、严格回放、投影核对、
比较前置与错误格式化共用一份实现，没有按阶段复制公共载荷或通用错误规则。
ScreeningFacts、ExtractionFacts、ReuseFacts 保留各自事实与来源业务校验，
不把阶段差异扩散到新的公开构造入口。

<a id="结构化-reuse-格式-1"></a>

## 结构化 reuse 格式 1

reuse 只消费自身 `StageReadiness` 与既有 reuse 配置投影。没有 extraction 配置或正文
制品时，合法结构化来源摘录仍可构造；未被引用的 PDF、解析配置、题名摘要、阶段二
评分与旧会话不隐式加入输入。excerpt_selector_version 仅经既有投影传播，不复制规则。
算法支持与编译拒绝由[配置投影契约](config-projections.md#规范内容与缺项)定义。

事实形状固定为 `{"excerpts":[...]}`。每项只有 excerpt_id、kind、text、source：

```json
{"excerpt_id":"availability-1","kind":"availability","source":{"content_sha256":"<payload 原始字节 SHA-256>","kind":"source_snapshot","locator":["data-availability","paragraph-1"]},"text":"Synthetic availability text"}
```

`ReuseFacts` 只收非空 list/tuple 并冻结为有序元组，集合顺序就是模型输入顺序。
`SelectedExcerpt` 的 ID/种类沿用权威 `ReuseAssessmentContext`，ID 是严格字符串、
strip 后非空但不归一化；单项只允许 availability/methods，both 是输出组合描述，
data 不作为输入种类接受。构造前仅限制 ID 可安全作为文本映射键及可 UTF-8
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
locator 可回查和摘录确属该范围均由生产者负责，本服务不核验这些来源事实。

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

消费摘录时只能使用载荷已绑定字段；需要页码、章节等时必须来自已绑定 locator，
否则需显式演进 reuse 格式。渲染策略本身变化必须有 adapter policy 或阶段格式版本。
此边界不实现选段、触发规则、PDF 取得、模型或任务。正文来源沿同一来源联合接入，
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
路径及另一种来源的字段一律不接收，不参与规范身份。manifest 审计字节不同、artifact_id
不同但消费内容相同，不改变 reuse 输入；改变 reading 或 evidence_map 实际成员则改变 reuse 指纹。

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
具体制品，
不能任取“最新”解析输出，也不能借不确定重解析不断制造新输入
以重开尝试预算。本服务不实现制品选择、缓存或预算。

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
支持的 normalization 算法与配置拒绝见[正文提取配置契约](extraction-config.md)。

<a id="c1-已知未决问题封面识别的论文元数据依赖"></a>

### C1 封面识别的输入边界

extraction 格式 1 不含题名、DOI、摘要等论文元数据。本服务不实现封面识别或 normalize，
也不把 extraction 指纹当作具体正文输出字节的证明：正文来源同时绑定 extraction 指纹与
实际消费的 reading/evidence_map 成员哈希。

正文生产的 C1 约束及不达标处理见[规格 §4.9](../../intent/draft.md#49-docling-正文提取)，
承接责任见[Body](../roadmap.md#module-body)、[B](../roadmap.md#module-b)与[F](../roadmap.md#module-f)。

<a id="隔离恢复跨进程与后续消费者义务"></a>

## 隔离恢复、跨进程与后续消费者义务

历史重建使用明确历史快照及规范事实；严格回放使用已保存规范字节和独立期望指纹。
两者不同，不从当前 selector、当前文件或“最新制品”补入旧输入。涉及制品的重建从
[ArtifactStore](artifact-store.md#公共服务) 返回的具体成员读取哈希，不以整个 artifact_id
代替内容身份。业务主体、完整历史 snapshot_id 和具体制品引用属于消费者的审计依据，
不额外进入本服务载荷。

本服务的构造、回放和比较不访问原目录或恢复目录，不触发 compile、upgrade、安装、
激活或任务续跑；配置历史加载及隔离恢复的前置与拒绝见
[配置快照](config-snapshots.md)和[备份恢复契约](backup-restore.md#隔离恢复)。
来源存在、合法取得、正文质量、定位可回查、真实摘录范围和选择器顺序由生产者保证；
本服务不代替这些检查，也不授予执行、预算、校准或业务消费资格。

既有跨进程、合成恢复测试覆盖及恢复固定向量见
[历史证明范围](../verification/contracts-stage-inputs-history.md)。

## 格式版本公开访问

`paper_radar.stage_inputs.STAGE_INPUT_FORMAT_VERSIONS` 是只读映射，明确列出
boundary/value/reuse/extraction 各自的当前配方版本 1；构造与回放共同消费这一份
生产权威数据。调用方不能修改映射，也不能把 StageName 的其余成员
视为已支持阶段。该映射只表达阶段输入格式，配置当前投影格式由 config 维护；历史投影
回放是否受支持由本模块的封闭策略决定，核对时还要求明确快照能够重建匹配格式。
公开版本不改变任何既有载荷字节、指纹向量或配置投影配方。

boundary/value 规范载荷持久化、同库预算主体及语言上下文冻结规则见
[任务登记契约](screening-tasks.md#8-a7-02-公共登记-api已交付)。

## 不提供／不证明

本服务不提供 Read、suggestion 或 report 阶段输入，不执行模型、Docling、选段、
调度或业务资格判断；配置 ready、自洽载荷或相同指纹不证明真实来源、成功制品、
正文质量、RPC 兼容、校准或 live 就绪。

Read 输入身份与正文生产消费由[Body](../roadmap.md#module-body)及[B](../roadmap.md#module-b)
承接，通用长文由[G](../roadmap.md#module-g)承接；复用执行与筛选建议由
[D](../roadmap.md#module-d)、报告由[H](../roadmap.md#module-h)承接。

## 相关

依据：[#8](https://github.com/MeteoBoy4/PaperRadar/issues/8)、[#47](https://github.com/MeteoBoy4/PaperRadar/issues/47)、[#48](https://github.com/MeteoBoy4/PaperRadar/issues/48)、[#49](https://github.com/MeteoBoy4/PaperRadar/issues/49)、[#50](https://github.com/MeteoBoy4/PaperRadar/issues/50)、[#51](https://github.com/MeteoBoy4/PaperRadar/issues/51)、[#52](https://github.com/MeteoBoy4/PaperRadar/issues/52)、[#53](https://github.com/MeteoBoy4/PaperRadar/issues/53)、[#54](https://github.com/MeteoBoy4/PaperRadar/issues/54)、[#69](https://github.com/MeteoBoy4/PaperRadar/issues/69)、[#73](https://github.com/MeteoBoy4/PaperRadar/issues/73)、[#75](https://github.com/MeteoBoy4/PaperRadar/issues/75)、[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111)；
[C1 用户裁决](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)。

[规格](../../intent/draft.md#34-阶段输入指纹)；[ADR-0008](../adr/0008-invalidate-artifacts-with-stage-specific-fingerprints.md)；
[ADR-0017](../adr/0017-retain-only-source-and-analysis-bearing-artifacts.md)；
[ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)；
[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)；[路线图承接](../roadmap.md#module-body)。

实现：[`stage_inputs`](../../src/paper_radar/stage_inputs/service.py)。
回归入口：[`test_stage_input_common_contract.py`](../../tests/test_stage_input_common_contract.py)、
[`test_stage_input_replay.py`](../../tests/test_stage_input_replay.py)、
[`test_stage_input_recovery.py`](../../tests/test_stage_input_recovery.py)。
