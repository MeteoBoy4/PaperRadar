# Read 输出与证据校验

本 Contract 记录 #92 正文及后续裁决的唯一 Read 规则。评论优先于父票初稿；
下方覆盖台账区分已交付的结构/证据接收/配置与其余实现票的目标能力。

## 当前交付与命名

#93 已交付 `paper_radar.reading` 的权威 Pydantic 结构及 Read 自有七类价值词汇，
经现有 contracts 服务生成、导出和只读检查。仅通过 Schema 不表示已通过证据业务接收。
#94 已交付原始字节与可靠文本上下文的纯验证、数值 v1 和警告三视图。
#95 已接通表格、公式区域源字符与不可靠字符的字段矩阵；#96 已交付 single/reduce
模式与同正文 map 证据允许集合检查；#97 已交付显式 Read 配置准入与历史比较。
#98 已验证历史配置与候选原字节的非空隔离恢复，固定上下文由测试常量重建；
独立 A9 结论由 #99 收口。

| 名称用途 | 固定名称 |
| --- | --- |
| Python 包、模型槽、Prompt 槽、adapter 槽 | `reading` |
| 契约 selector、CLI 受控名 | `read`；不开放 `contracts.reading` 别名 |
| area、声明版本 | `read`、`v1` |
| 根及示例冻结目录 | `contracts/read/read/v1/`、`examples/contracts/read/read/v1/` |
| Schema `$id` | `urn:paper-radar:contracts:read:read:v1` |

Read `ValueType` 自有冻结定义，不 import Screening 枚举；七个 wire 值与中文含义为
`method` 方法、`data` 数据、`code_tool` 代码/工具、`theory_mechanism` 理论/机制、
`evidence_conclusion` 证据/结论、`question_hypothesis` 问题/假设、
`review_knowledge_map` 综述/知识地图。测试中的独立向量记录冻结时与 Screening v1
相同的集合；未来 Screening 词汇变化不重生成该历史向量，不隐式改变 Read v1。

Read 自有 `$defs.ValueType.description` 与 `value_types` 属性描述均固定为
“精读分析允许返回的七类受控价值。”。其余模型可见描述也由固定向量锁定，属于发送给
模型的冻结契约文字；业务指引留在版本化 Prompt。原 Screening 枚举、描述与四份快照
保持原字节。Read 的 Schema SHA-256 为
`1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111`。

## 字段闭集

以下 18 项全部必填，所有层级拒绝额外字段和类型强转。评分是严格整数 `1..5`，
拒绝 bool、float 和字符串。`EvidenceRef` 仅有严格非空 `evidence_id`；
`SupportedStatement` 仅有 `statement`、`evidence`；`ReusablePoint` 仅有
`item`、`how_to_reuse`、`evidence`。正文身份、provenance、verified、诊断、mode、
Rank、Topic、紧急性和流程决定属于程序边界，不是模型输出字段。

“有意义文本”只拒绝空白、纯标点、明确占位文本，不判断科学内容是否充分；列表内字符串也需
逐项检查，不能套用摘要层输入不足短语。结构类型/评分/必填性由 #93 交付；
有意义文本、重复检测、条件非空及上下文业务规则由 #94 交付。

| 必填字段 | 允许空列表 | 有意义文本 | 数值检查 | 证据义务 |
| --- | --- | --- | --- | --- |
| `output_language` | 不适用 | `zh` / `en`，须与明确请求一致 | 无 | 无 |
| `one_sentence_conclusion` | 不适用 | 是 | 无 | 无 |
| `research_question` | 不适用 | 是 | 无 | 无 |
| `methods_summary` | 不适用 | 是 | 无 | 无 |
| `data_summary` | 不适用 | 是 | 无 | 无 |
| `main_findings` | 是 | 每项 statement | 每项 statement | 每项 evidence 非空、无重复 |
| `research_value` | 不适用 | 严格 `1..5` | 无 | 无 |
| `research_value_reason` | 不适用 | statement | statement | evidence 非空、无重复 |
| `reuse_feasibility` | 不适用 | 严格 `1..5` | 无 | 无 |
| `reuse_feasibility_reason` | 不适用 | statement | statement | evidence 非空、无重复 |
| `required_adaptations` | 是 | 每项 | 无 | 无 |
| `reusable_points` | 是 | 每项 item / how_to_reuse | 两段各自检查 | 每项共用自身非空、无重复 evidence |
| `key_limitations` | 是 | 每项 statement | 每项 statement | 每项 evidence 非空、无重复 |
| `open_questions` | 是 | 每项 | 无 | 无 |
| `value_types` | 研究价值低于 3 时可空 | 封闭七类，无重复 | 无 | 无 |
| `why_it_matters` | 不适用 | 是 | 无 | 无 |
| `next_action` | 不适用 | 是 | 无 | 无 |
| `degraded_content_warnings` | 是 | 每项，逐字保留重复项 | 无 | 无 |

`next_action` 是叙述性下一步建议，不承担流程控制。它仅作非空/有意义文本检查，
不增加证据、数值或紧急性措辞判定。数值检查是表中五类保护内容的闭集，新增字段
默认不检查；其余字段将来不得呈现为已核对。`data_summary` 仅写“无”会被占位
规则拒绝，纯理论论文可写“未使用观测数据”，具体引导留给 Prompt。

## 消费上下文与错误边界（源字符与 reduce 已交付）

调用方提交原始 UTF-8 JSON 字节和已合法构造的只读上下文。顶层前后 JSON 空白合法；
BOM、坏 UTF-8、孤立代理字符、任意层重复键、NaN/Infinity、非对象、围栏、截断和
非空白尾随内容均拒绝，不作修复。上下文构造错误独立于模型输出拒绝，不得变成
`output_invalid` 或消耗模型预算。本票不引入预算或接收器。

公共入口为 `paper_radar.reading.validate_read_output(raw: bytes, context: ReadContext)`。
只接受原始 bytes；str、bytearray、映射或已处理的模型对象均不作为候选接收。
`ReadContextError` 表示调用方上下文不合法；`ReadOutputError` 表示模型候选拒绝。
两者的 issues 都仅携受控 `ReadErrorCategory`、安全字段路径和中文指引，额外键用
`<额外字段>` 替代。解析及 Pydantic 异常在退出捕获后转换，不保留含输入的异常链。

下表是唯一消费视图的公共字段。页面、源块、evidence 序列接受 list/tuple，构造后
转为 tuple；不接收已经覆盖重复键的映射作为成员集合。来源字符串和坐标不改写。

| 类型 | 权威字段 | 自校验口径 |
| --- | --- | --- |
| `ExtractionIdentity` | extraction_fingerprint、reading_sha256、evidence_map_sha256 | 三个不透明非空字符串；由上下文统一核对 |
| `PageFact` | identity、page_no、width、height、origin | 同三元组、唯一原页码、有限正 point 尺寸、封闭原点 |
| `SourceBlock` | identity、source_id、orig、kind、unreliable | 同三元组、唯一 ID、合法 Unicode orig、text/table/formula 与严格 bool |
| `Provenance` | source_id、page_no、bbox、start、end | 源/页面闭包、四元 bbox、orig 半开区间、非空白切片；拒绝完全重复定位 |
| `Evidence` | identity、evidence_id、provenance | 同三元组、唯一严格 ID、有序非空 provenance |
| `AllowedEvidence` | identity、evidence_ids | 集合级同三元组；有序 ID 接受 list/tuple 后冻结为 tuple；严格 ID、无重复，允许空 tuple |
| `ReadContext` | identity、pages、source_blocks、evidence、expected_language、mode、allowed_evidence | 先验证完整集合，再冻结；语言显式 zh/en；single/reduce 与集合方向约束 |
| `SourceSlice` | identity、evidence_id、provenance、text、kind、unreliable | `replay()` 从 orig 精确切出，保留来源与全部定位 |

缺少 identity 或 expected_language 都是受控上下文错误。#95 允许上下文保留合法
table/formula/unreliable 源事实，是否可支持某个字段由下方矩阵接收规则决定，
不在上下文构造时一概拒绝。
#96 已接入 reduce；未知模式仍以 unsupported_mode 拒绝。
公式候选、图片/公式占位及生成展示内容没有 SourceBlock 类型分支；将其 ID 用作
provenance 目标会因未知源而构造失败。上下文只解释给定 orig，不生成这些内容。

上下文顶层选择、成员归属和结果绑定都采用 A5 消费身份三元组
`(extraction_fingerprint, reading_sha256, evidence_map_sha256)`；相同 fingerprint
但任一消费内容身份不同也不可互换。三元组是已给定材料的不透明身份，不证明当前
选择、真实来源或正文质量。上下文构造需在建索引前验证重复页面/源块/evidence、
矛盾归属、闭包、页码、尺寸和全部 provenance，并防御性冻结调用方集合。

provenance 只指向源文本块，种类封闭为 text/table/formula，并有不可靠字符标记。
公式候选、图片/公式占位及生成展示文本都不能作为 orig 目标；不存在“生成展示文本”
源标记。页面采用原 PDF 正整数页码，不要求连续；尺寸与坐标使用 point，原点明确为
top_left 或 bottom_left。bbox 精确满足 `0 <= x_min < x_max <= width`，y 同理，
坐标有限且拒绝 bool，不加容差或 clamp。重复 provenance 拒绝，顺序保留而不要求
页码单调。ID 不 trim、不规范化；首尾空白与控制字符拒绝。

charspan 按 orig 原字符串的 Unicode code point 半开区间回放，切片必须含非空白字符
（`str.isspace()`）；允许在组合字符或 ZWJ 内切分。回放、切片与非空判断永不执行
NFKC/全角折叠，数值归一化仅发生在后续等价比较子步骤，不产生新切片或改变定位。
跨页 evidence 保留全部 provenance，数值比较不把分段拼接。

single 禁止附带允许集合；reduce 必须提供 `AllowedEvidence(identity, evidence_ids)`，
集合级携带与上下文相同的三元组。成员以有序 list/tuple 接收后冻结为 tuple；集合、
上下文与来源容器在构造完成后的修改不能改变已冻结范围。构造时拒绝缺失、重复、
未知成员及跨正文（包括同 fingerprint、不同 reading/evidence-map 哈希）。
允许引用合法子集，不要求用完全部允许 ID；不因缺集合而退回全文范围。

| 位置与违例 | 安全原因 | 异常边界 |
| --- | --- | --- |
| reduce 缺集合 | missing_allowed_evidence | ReadContextError |
| single 附带集合 | unexpected_allowed_evidence | ReadContextError |
| 非权威类型或无序集合 | invalid_allowed_evidence | ReadContextError |
| 集合内重复 / 非法 ID | duplicate_id / invalid_evidence_id | ReadContextError |
| 集合跨正文 / 未知成员 | identity_mismatch / unknown_allowed_evidence | ReadContextError |
| 模型引用正文不存在的 ID | unknown_evidence | ReadOutputError |
| 模型引用正文存在但未被允许的 ID | evidence_not_allowed | ReadOutputError |

空 tuple 可以构造。此时任何实际引用都按越界拒绝，五类保护内容若没有有效允许引用，
同时报告 evidence_required；两项评分理由必填，因而整份分析不能通过。诊断按安全
字段路径排序，保留范围越界和引用义务两种原因，不短路只报其一。原模型的 evidence
列表为空时仍按冻结 Schema 拒绝，不补字段或引用。

reduce 沿用相同严格 JSON、语言、价值、定位、数值与受限内容入口；程序模式和集合
不进入模型 Schema。结果保留 mode、三元组和规则身份，冻结 read/v1 字节不变。
允许集合真实来自本轮 map 的来源链仍未验证，本票不实现 map 契约、分块或任务。

## 受限内容矩阵（#95 已交付）

单条 evidence 只要任一 provenance 落在受限源块上，即作为含受限证据处理；数值匹配
仍按具体切片分类。模型自报 verified 不能放行，额外字段由结构层拒绝。

| 所引证据 | 主要发现 / 两项评分理由 / 可复用点 | 关键局限 |
| --- | --- | --- |
| 可靠普通文本 | 允许；数值按规则检查 | 同左 |
| 表格源块 | 结构描述允许且无警告；某数值仅在受限切片命中则硬失败 | 允许；数值仅受限命中则降级警告 |
| 公式区域源字符 / 不可靠字符块 | 引用即硬失败 | 可以指向局限所在；数值仅受限命中则降级警告 |
| 公式候选 / 公式或图片占位 / 生成展示文本 | 非 provenance 目标，上下文构造失败 | 同左 |

数值在全部引用切片中都未命中时一律降级，不作硬失败。上述窄矩阵是最终 owner
裁决，替代父票初稿“受限证据违例”的模糊定义。未来阶段 G 的修正重试应提示可改引
正文、去掉表格精确值或移入关键局限；本票不实现该修正调用。

“仅在受限切片命中”逐个字面量判定：全部所引可靠切片都不支持它，但至少一条受限
切片支持它。同条 evidence 含可靠与受限 provenance 时仍保留每条实际来源；可靠
切片也能支持的数值不构成表格数值违例。不同数值可分别依赖不同来源，不按整条
evidence 的受限标记抹去可靠片段。范围仍必须在一条切片内同时匹配两端，不跨来源
拼接。公式区域或不可靠字符引用的独立硬失败不因另有可靠数值来源而取消。

关键局限在该矩阵下只有通过或降级；数值仅受限命中使用
`restricted_numeric_support` 诊断，数值完全未命中沿用 number/range/unit 的不支持
原因。结构、引用闭包与定位错误仍按原规则拒绝。主要发现、两项评分理由及可复用点
分别使用 `restricted_source_reference` 和 `restricted_numeric_support` 硬失败类别。
验证入口一次收集全部受限违例，`ReadOutputError.issues` 先列引用类硬失败、再列
数值依赖硬失败，同级按字段路径和条目顺序；随后消费其安全 `diagnostics` 查看同次
数值降级发现。异常不附带警告字符串、字面量或源片段。失败没有分析成功返回值，
将来生产接收器应把这次真实输出拒绝计入一次 attempt，而本票不创建 attempt。

表格切片直接来自 SourceBlock.orig 的字符回放，不重新解析表格，也不把候选 LaTeX
当作来源。块粒度由未来正文生产者决定；块越大，别处的相同数字越可能落进同一片段，
本票不设无规格依据的长度上限，不判断科学语义蕴含或人工复核状态。

## 数值与警告（#94 已交付）

数值规则 v1 只提取阿拉伯数字（含全角），中文数字不提取、不产生警告。边界显式按
拉丁字母/数字/小数点定义，不能用会漏掉 CJK 邻接数值的通用单词边界。
ERA5、CMIP6、PM2.5、CO2、O3、H2O 等拉丁字母直连标识符以及封闭图/表/式/节/
Fig./Figure/Table/Eq./Section 前缀交叉引用编号排除。单位采用封闭列表与中英别名，
英文前缀必须具有左侧拉丁词元边界，stable 或 intersection 的后缀不构成 Table/Section。
包含 hPa/百帕、km/公里/千米、m/s/米/秒、°C/摄氏度、%/％；未知相邻词不当单位。
封闭排版等价覆盖 Unicode 负号、范围连接、空格百分号、850-hPa、2-m、千分位、
科学计数法、上标指数与 ±；其完整词元向量由 #94 固定。

数值规则常量 `NUMERIC_RULE_VERSION="read-numeric-v1"`，证据规则常量
`EVIDENCE_RULE_VERSION="read-evidence-v1"`。v1 的单位与记法闭集如下，大小写保持
表中所列；只有比较使用这些归一化，orig/charspan/text 始终原样回放。

| 等价类 | 接受的记法 |
| --- | --- |
| 距离/长度 | km、公里、千米；m、米；不在 km 与 m 之间换算 |
| 气压 | hPa、百帕 |
| 速度 | m/s、m s−1、m s-1、m s⁻¹、米/秒 |
| 温度/百分比 | °C、摄氏度；%、％；允许数值与单位之间空白 |
| 数字与符号 | ASCII/全角阿拉伯数字、小数点/逗号/正负号；U+2212 等同负号 |
| 单位连接 | 850-hPa ≡ 850 hPa；2-m ≡ 2 m |
| 范围 | en dash、~、～、至、to、连字符；单位仅挂在后一端点 |
| 千分位/小数 | 1,000 ≡ 1000；.5 ≡ 0.5；不把小数或千分位拆成子串数字 |
| 科学记数 | 1.2e-3、1.2×10⁻³、1.2x10⁻³、1.2×10^-3；10⁻³ / 10^-3 等同 1e-3 |
| 正负范围记号 | ±0.5 作为独立的带 ± 数值；不能由裸 0.5 支持 |

科学记数只作数字记法等价比较，不计算新科学结论。形如 1e、1,00、2.3.4、
1.2×10^?、无指数的 1.2×10、10^unknown 和 1/2 等不能可靠解释的形状产生
unrecognized_numeric_form，不把内部组件数字当支持。识别器只对明确覆盖的形状
负责，不能识别所有自然语言中的数值依赖。中文数字是已接受的漏检边界。

固定预期：30°N 只提取裸 30，°N 不属于单位表；1979–2020 是同切片范围；
(Smith et al., 2020) 中 2020 是普通数值。警告只由陈述侧提取值驱动，来源中多出
的数字不产生诊断。Table 3 比较 12 个流域仅排除编号 3，12 仍需自己的引用支持。

匹配只检查该陈述自己的 provenance 切片，范围端点必须同切片出现，单位挂在后端点。
不同数值可各自命中不同引用切片。`3` 不因 `30`、`13`、`3.5` 或 `0.3` 通过。
不换算单位、不推导、不补数字、不改结论或评分；无法可靠解释的数值形状明确降级。
块粒度影响区分力：块越大，论文别处的相同数值越可能落在同一支持片段；本票不设
无规格依据的长度上限，也不证明科学语义蕴含。

验证结果保留证据规则和数值规则公共版本身份、正文绑定及模式。规则是对已保存原始
字节的确定性后处理，是否进入 Read StageInput 指纹留给后续票，A9 不预设模型重跑。
结果提供三个视图：原模型警告逐字保留（含重复项）、安全结构化程序诊断、带 origin
的只读合并视图。程序诊断按字段路径/原因/字面量序号去重排序；报告走诊断定位，
不解析警告字符串。模型即使伪造相同模板，也不能改变诊断或来源。
程序模板按期望语言选中/英文，可在受控分析视图包含触发数值；repr、异常、日志、
结构化诊断仅携安全位置/原因/序号，不含全文、片段、响应或数值字面量。
幂等指同一原始字节与上下文重复校验结果相等，不把追加警告后的分析当新模型原文。

结果 `ReadValidationResult` 还提供 `identity`、`mode`、`evidence_rule_version`、
`numeric_rule_version` 与精确回放的 `support`。其保存的分析依据为不可变字节，
`analysis` 每次返回独立模型副本，修改该副本的 list 不会改变结果。该分析的
`degraded_content_warnings` 是模型警告在前、程序警告在后的处理视图；原始 bytes
始终由调用方另行保存，不能用处理视图冒称原始成功响应。

安全诊断为 `ReadDiagnostic(location, reason, ordinal)`；ordinal 是该字段抽取值的
零基序号，不含数值或原文。`NumericReason` 的当前闭集为 number_not_supported、
range_not_supported、unit_not_supported、unrecognized_numeric_form。程序警告使用
固定中/英文模板，包含同一分析中的触发字面量；`ReadWarning` 以 origin=model/program
明确来源。默认 repr/str 隐藏候选、source ID、片段、模型警告和程序警告正文。

## 配置及恢复范围（#97/#98 已交付）

Read 契约只能经显式 `settings.contracts.read` 选择进入原版本登记与快照闭包。
历史 load 沿用已登记原始字节/哈希/selector 校验，不重新生成当前权威 Schema；
旧快照保持 `contract: None`、原 ID 与缺项。新契约只填 Read 投影已有 contract 槽，
不影响其余五投影或校准基线。配置 ready 仅说明材料齐全，不授予生产执行或校准资格。

`contracts.reading` 不是别名；read 未选/null 不读取磁盘材料，也不改变旧快照身份。
check/compile 检查权威 Schema/manifest 的配对与精确字节，损坏、错版、同版本漂移或
手写替代物受控拒绝；失败不留下部分登记。历史材料损坏不回退当前文件。
`config diff` 的类别含 `contract_schema.read` / `contract_manifest.read`，快照摘要同时
列出两个独立登记身份。无新增 migration，revision 仍为 `a704_screening_retry`。

独立示例 `examples/config/settings-read-ready.yaml` 配齐非占位 Profile、reading 模型、
reading Prompt、reading adapter、read 配置（chunking v1）与 read 契约选择。
旧 `settings-read.yaml` 保留绑定字节，它未选择契约，因此仍缺 `read_contract`。
Read 缺项顺序保持 profile → 已选 adapter 的 Prompt 占位 → 模型 → Prompt → 契约 →
chunking。未选择 adapter 沿用原政策，单独显示 unconfigured，不增加新的必选门禁。

### 恢复范围（#98）

恢复组合只备份历史配置和 `model_success_response` 候选原始字节，上下文由测试固定
常量重建。它不发布合成 extraction、不自造上下文序列化、不新增分析成功行；
无业务引用的成功响应仍可备份。恢复后从新目录/进程加载历史配置与原始响应，复现
绑定、规则、诊断和合并视图，并阻断原目录。固定上下文不是恢复产物。
orig 源文本由 document/canonical 哪个成员哈希覆盖留给阶段 F；A5 三元组不包含
document 成员，本票不发明 evidence-map 生产格式。

#98 通过真实 migration、SQLite、配置编译、制品发布、backup/verify/restore 验证两份
历史快照（未选择/显式选择 Read 契约），以及中文/英文 × single/reduce 的四份合法
原始响应。候选保留 JSON 首尾空白、重复模型警告与和程序模板相同的模型警告；
恢复前后逐项比较配置 ID、Read 投影、校准基线、精确原字节、三元组、规则、诊断、
带 origin 的合并视图及回放切片。比较摘要只保存标识符、受控诊断和哈希。

原配置/数据库/数据根移走后，旧位置放置普通文件哨兵；新进程的审计屏障同时拒绝
旧位置和移走位置的 open、SQLite URI、目录访问，并主动探测屏障确实拒绝。
恢复副本只读回放后再次搬迁，之后禁止访问批次和旧恢复位置；实际数据库及 blob
读取位于新恢复根内。源、批次和恢复 blob 具有独立 inode，读取不升级、激活或执行
任务，数据库中的 Paper/Screening 请求、任务、attempt 与成功事实行始终为零。

恢复后的同一入口仍允许关键局限引用未复核表格并降级，且拒绝允许集合内主要发现
仅依赖表格数值、允许范围外引用和截断 JSON。无效候选仅在内存中构造，不重新登记
成成功响应。模型与程序同字符串警告继续靠 origin/诊断区分。默认快照 repr/str
隐藏 payload_json，显式载荷访问、原始字节、快照和投影身份不变。

坏 Read Schema/manifest 登记字节或缺少快照引用由历史配置闭包以 config_invalid
拒绝；响应物理坏字节/缺文件由 blob/hash 边界拒绝，已发布旧/未知 revision 批次
继续 unsupported_revision。拒绝不修改批次、不发布恢复目标。备份只保证已保存字节
完整，不在缺少上下文时判断 Read 业务合法；该判断仍在读回后的公共验证入口完成。
上述能力不证明真实 evidence-map、当前正文选择、科学语义或真实 PDF provenance。

## 集成验收与明确未验证

#93–#98 仅以各自行为子集验收；#99 最终收口独立必需 A9、可信终态与全量门禁。
六检查计划及 A1 历史四契约保持固定，Read 检查由 A9 writer 内部显式调用现有服务。
直接前置是同次 A1、完整 A2、A3；A4–A8 仍 required，不把其历史成功当 Read 证明。
scope 链按真实 DAG 重绑，A9 不哈希绑定 scope 自身，self_reference/cycle 继续拒绝；
该字节由运行前后完整工作树身份及固定登记审计覆盖。无新增 migration，revision
仍为 `a704_screening_retry`。本首票不声称完整门禁已通过。
前后哈希、固定分母与范围变化原因保存在[scope 审阅台账](../verification/a9-scope-review.md)。

真实 PDF provenance、四刊 fixture、正文质量、语义蕴含、模型质量、map 来源链、
Read StageInput/任务/预算/业务持久化、生产 Pi、校准资格、NAS 与完整阶段 A
均未验证；`stage_a_verified`、`live_verified`、`rpc_verified` 持续为 false。

## #92 覆盖台账

以下编号对应父票正文，后续票在自己的纵向切片完成后更新“已实现”列；
目标列始终给出责任票，避免以设计文字冒充已交付能力。

### 42 条 User Stories

| 条目与已实现 | 目标能力（实现票） | 明确未验证 |
| --- | --- | --- |
| US01：沿用 A1–A8，无重做 | 兼容及最终验收 #93/#99 | 完整阶段 A |
| US02：18 字段及嵌套类型已冻结 | 完整结构 #93 | 证据业务接收 |
| US03：严格独立 1–5 分已实现 | 评分 #93 | 评分正确性 |
| US04：Read 自有七类词汇已冻结 | 冻结时与 Screening v1 同值 #93 | 未来词汇自动同步 |
| US05：高分非空类型已实现 | 高分至少一类 #94 | 真实研究价值 |
| US06：请求语言匹配已实现 | 请求语言匹配 #94 | 翻译质量 |
| US07：可靠/受限源公共纯入口已交付 | 单一纯验证入口 #94/#95/#96 | 生产接收器 |
| US08：严格原始 JSON 已实现 | 严格原始 JSON #94 | 真实响应 |
| US09：额外字段拒绝已实现 | 输出职责闭集 #93/#94 | 自然语言语义分类 |
| US10：五类引用义务已实现 | 五类引用业务义务 #94 | 语义蕴含 |
| US11：跨条目共享引用已实现 | 跨条目共享引用 #94 | 真实证据 |
| US12：重复/未知引用拒绝已实现 | 重复与未知引用拒绝 #94 | 真实映射 |
| US13：三元组绑定已实现 | 三元组结果绑定 #94 | 当前正文选择 |
| US14：构造闭包已实现 | 上下文构造闭包 #94 | 生产上下文构建 |
| US15：页面/bbox 已实现 | 页面/bbox #94 | 真实 PDF |
| US16：orig charspan 回放已实现 | orig charspan #94 | orig 哈希覆盖 |
| US17：多 provenance 已实现 | 多 provenance #94 | 实际跨页解析 |
| US18：原字符保留已实现 | 原字符精确保留 #94 | 解析质量 |
| US19：候选/占位非源拒绝、受限矩阵已接通 | 受限源类型 #94/#95 | 真实 PDF 核查 |
| US20：表格结构/数值矩阵向量通过 | 表格结构/数值区分 #95 | 人工复核入口 |
| US21：verified 额外字段拒绝已实现 | Python 来源控制 #93/#95 | 生产证据可信度 |
| US22：允许集合限制引用已实现 | reduce 子集 #96 | map 来源链 |
| US23：允许集合必填及空集合诊断已实现 | reduce 允许集合必填 #96 | 真实 map |
| US24：逐条引用切片匹配已实现 | 仅各自引用切片匹配 #94 | 科学支持关系 |
| US25：数值/范围/单位降级已实现 | 数值/范围/单位降级 #94 | 精确数值正确性 |
| US26：封闭等价且不换算已实现 | 不换算/改写 #94 | 科学推导 |
| US27：安全字段诊断已实现 | 安全字段诊断 #94 | 报告渲染 |
| US28：原警告/诊断/origin 三视图已实现 | 原警告、诊断、origin 合并 #94 | 产品报告 |
| US29：防御冻结与原始响应隔离已实现 | 原始响应与深度只读上下文 #94 | 生产保存 |
| US30：权威 Pydantic 导出已实现 | Read Frozen Contract #93 | 业务验证成功 |
| US31：幂等与冲突拒绝已实现 | 不可覆盖发布 #93 | 远端发布 |
| US32：既有中文 CLI 已支持 read | 单选/混选 #93 | Read 执行命令 |
| US33：显式配置准入已实现 | 显式配置准入 #97 | 生产可运行 |
| US34：未选/null 保持缺项与身份 | 不自动选择磁盘材料 #97 | 运行器选择 |
| US35：旧四份字节及历史范围保持 | 历史快照兼容 #97/#99 | 全量门禁尚未收口 |
| US36：仅 Read 投影变化已验证 | Read 投影隔离 #97 | 校准效果 |
| US37：删文件后新进程 load 已验证 | 删除当前材料后历史 load #97 | 生产长期保存 |
| US38：两快照/四候选在阻断原根的新进程搬迁回放通过 | 非空恢复配置/响应 #98 | 上下文从库恢复 |
| US39：模型/快照 repr、错误与恢复输出已脱敏 | 安全错误、结果及证据 #94/#98/#99 | 全局日志平台 |
| US40：历史四集合已显式固定 | 哈希/分母审阅及重绑 #93/#99 | 最终门禁 |
| US41：验收接法已记录 | 独立 A9/同次终态 #99 | 新 A9 通过 |
| US42：未验证清单已记录 | 持续准确能力声明 #93–#99 | 模型/PDF/自动精读 |

### 21 条 Implementation Decisions

| 条目与已实现 | 目标能力（实现票） | 明确未验证 |
| --- | --- | --- |
| ID01：可靠/受限源纯服务已交付 | 完整纯服务 #94/#95 | I/O 接收器 |
| ID02：18 字段及嵌套模型已冻结 | 结构 #93 | 业务接收 |
| ID03：JSON/安全错误已交付 | JSON/安全错误 #94 | 真实响应 |
| ID04：语言匹配/条件非空已交付 | 语言/条件非空 #94 | 语言识别 |
| ID05：引用范围/重复/绑定已交付 | 作用域/重复/绑定 #94 | 真实证据 |
| ID06：防御冻结已交付 | 防御冻结 #94 | 正文生产 |
| ID07：完整构造闭包已交付 | 构造一致性 #94 | 内容身份生产验证 |
| ID08：全部 provenance 回放已交付 | 全部 provenance 回放 #94 | PDF 回查 |
| ID09：最终窄矩阵已交付 | 表格/公式裁决 #95 | 人工复核写入 |
| ID10：同正文允许集合与模式约束已交付 | reduce #96 | map 输出来源 |
| ID11：数值规则 v1 已交付 | 数值规则 v1 #94 | 语义蕴含 |
| ID12：降级三视图与受限硬失败已接通 | 硬失败/降级 #94/#95 | 报告 |
| ID13：area read、根/示例已冻结 | 既有发布/检查 #93 | 真实模型 |
| ID14：read selector 与原登记已实现 | 显式 selector #97 | 生产准入 |
| ID15：ready 示例与缺项已验证 | 准确缺项 #97 | 实际执行 |
| ID16：旧向量、null 与投影隔离通过 | 旧向量及 Read 槽 #97 | 完整 Read 指纹 |
| ID17：收缩范围的非空隔离恢复已验证 | 配置/响应恢复 #98 | evidence-map 协议 |
| ID18：历史四集合及变更审阅 | scope 链式重绑 #99 | 新全量结论 |
| ID19：契约/配置帮助及独立示例已实现 | 配置示例/CLI #97/#98 | reading 产品命令 |
| ID20：六计划/四契约保持 | 独立 A9 内部 read check #99 | 最终终态 |
| ID21：公共规则及领域词汇已记录 | 其余文档随实现 #94–#99 | 完整阶段 A |

### Testing Decisions 的 20 个验收面

| 条目与已实现 | 目标能力（实现票） | 明确未验证 |
| --- | --- | --- |
| TD01：完整结构/评分/缺字段向量 | 完整输出与字段 #93/#94 | 内容质量 |
| TD02：严格 JSON 向量通过 | 严格 JSON #94 | live 响应 |
| TD03：语言匹配与价值约束通过 | 语言匹配与业务约束 #94 | 语义识别 |
| TD04：引用集合向量通过 | 引用集合 #94 | 真实映射 |
| TD05：完整性向量通过 | 上下文完整性 #94 | 正文生产 |
| TD06：三元组/冻结向量通过 | 三元组来源绑定 #94 | 当前正文 |
| TD07：页面/bbox 向量通过 | 页面/bbox #94 | PDF 来源 |
| TD08：Unicode/多 provenance 向量通过 | charspan #94 | Docling |
| TD09：全字段/混合来源矩阵向量通过 | 受限版面 #95 | 人工核查 |
| TD10：模式/身份/集合/越界向量通过 | reduce #96 | map 来源 |
| TD11：封闭记法数值向量通过 | 数值正例 #94 | 科学蕴含 |
| TD12：数值降级向量通过 | 数值降级 #94 | 精度判断 |
| TD13：三视图/原始依据向量通过 | 警告与原始依据 #94 | 存储接收器 |
| TD14：纯层/隐私向量通过 | 纯层与隐私 #94 | 全局日志 |
| TD15：根/示例、混选、不覆盖通过 | 冻结 Read 契约 #93 | 模型调用 |
| TD16：原子、幂等、损坏与历史 load 通过 | 配置准入 #97 | 运行就绪 |
| TD17：旧向量及新契约仅影响 Read 通过 | 身份与投影 #97 | 完整 Read 指纹 |
| TD18：四候选/双快照隔离恢复及损坏拒绝通过 | 非空历史恢复 #98 | 恢复正文协议 |
| TD19：新配置 CLI 通过、help 沿用无 I/O 测试 | 配置 CLI #97 | reading CLI |
| TD20：历史计划保持 | 验收扩展 #99 | 独立 A9 终态 |

### 四条评论及最终裁决覆盖

来源：[首次补充](https://github.com/MeteoBoy4/PaperRadar/issues/92#issuecomment-6380859875)、
[第一轮裁决](https://github.com/MeteoBoy4/PaperRadar/issues/92#issuecomment-6380999899)、
[第二次补充](https://github.com/MeteoBoy4/PaperRadar/issues/92#issuecomment-6381074150)、
[最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/92#issuecomment-6381118444)。

| 条目与已实现 | 目标能力（实现票） | 明确未验证 |
| --- | --- | --- |
| C1：上下文/异常/几何/数值/警告规则已记录 | 一-5、二-6~14 由 #94/#95/#96；三配置连锁 #97；四门禁 #99；五恢复收缩 #98；六测试 #94–#99；七文档贯穿 | 可靠/受限源与 reduce 已交付 |
| D1：area=read 已冻结 | #93 | 无新 area 别名 |
| D2：窄受限矩阵已交付 | #95 | 真实 PDF 核对 |
| D3：A5 三元组已记录 | #94 | orig 哈希归属 |
| D4：阿拉伯数字/误报控制已记录 | #94 | 语言语义推断 |
| D11：属性描述已固定，继承描述由最终 A 覆盖 | #93 | 动态 Screening 耦合 |
| C2：第一轮裁决、阶段 F/G 待办已记录 | #93 文档同步；#94/#95 实现 | orig 哈希、Read StageInput、修正重试 |
| C3：字段表/归一化/三视图/链式重绑/门禁/文档/顺序已记录 | 三四五 #93/#94；六七 #99；八 #93/#97/#99；九冻结先行已执行 | scope 收口尚未发生 |
| Final-A：Read 自有词汇替代首轮 import | #93 已交付 | 将来 Screening 演进不隐式更新 |
| Final-next_action：保留叙述字段已冻结 | #93；meaningful-text #94 | 不增加数值/证据/措辞门禁 |
| Split：A9 不绑定 scope 自身、前票子集验收 | #93–#98 子集；#99 DAG 一次重绑 | 最终全量门禁 |
