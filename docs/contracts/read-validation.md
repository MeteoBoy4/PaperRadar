# Read 输出与证据校验

## 用途与范围

`paper_radar.reading` 保留冻结 v1 结构与历史验证，
`paper_radar.reading.acceptance_v2` 提供完整候选的 v2 纯接收、末次条目丢弃及安全降级诊断。Schema 合法只是接收的必要条件；公共业务入口还检查语言、价值类型、
证据引用与受限内容。本 Contract 定义该纯验证边界及其配置、恢复组合保证，
不把给定上下文内部一致解释为真实正文来源、质量或生产执行资格。

<a id="当前交付与命名"></a>

## 命名与冻结结构

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
`review_knowledge_map` 综述/知识地图。Screening 词汇变化不隐式改变 Read v1。

Read 自有 `$defs.ValueType.description` 与 `value_types` 属性描述均为
“精读分析允许返回的七类受控价值。”。模型可见描述属于冻结契约文字；业务指引
由版本化 Prompt 提供。Read 的 Schema SHA-256 为
`1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111`。
生成、导出、检查入口及其参数、格式、拒绝原因和退出码见
[Frozen Contract](frozen-contracts.md#命令与公共入口)；该服务支持单选或混选 `read`，
不提供 Read 模型执行命令。

## 字段闭集

以下 18 项全部必填，没有字段默认值；所有层级拒绝额外字段和类型强转。
评分是严格整数 `1..5`，拒绝 bool、float 和字符串。
`EvidenceRef` 仅有严格非空 `evidence_id`；
`SupportedStatement` 仅有 `statement`、`evidence`；`ReusablePoint` 仅有
`item`、`how_to_reuse`、`evidence`。正文身份、provenance、verified、诊断、mode、
Rank、Topic、紧急性和流程决定不是模型输出字段。

“有意义文本”只拒绝空白、纯标点、明确占位文本，不判断科学内容是否充分；列表内
字符串也逐项检查，不套用摘要层输入不足短语。结构校验涵盖类型/评分/必填性；
业务校验涵盖有意义文本、重复检测、条件非空及上下文业务规则。

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
不增加证据、数值或紧急性措辞判定。数值检查只覆盖表中五类保护内容，其余字段
不表示已核对。`data_summary` 仅写“无”被占位规则拒绝，纯理论论文可写
“未使用观测数据”。同一合法 evidence ID 可以由不同条目共享；重复引用只在
同一 evidence 列表内拒绝。

<a id="消费上下文与错误边界源字符与-reduce-已交付"></a>

## 消费上下文与原始候选

新接收入口为
`paper_radar.reading.acceptance_v2.validate_read_output_v2(raw, context, *, degrade_policy="final_attempt", attempt_ordinal=...)`，
返回 `ReadV2Result`。`attempt_ordinal` 是任务层领取时分配的本代接收序号，严格整数闭集
`{1,2}`；末次等于序号 2，与剩余预算、是否打算 retry 无关。唯一策略值是
`final_attempt`，未知策略或序号为受控调用方错误。执行器不能覆盖领取序号；候选 JSON
自带序号字段仍按额外字段拒绝。纯入口不推断序号、不领取或修改预算。

历史公共入口 `paper_radar.reading.validate_read_output(raw, context)` 返回
`ReadValidationResult`，仍使用 v1 原规则。v2 按模块路径直接导入，不经 v1 包入口复导出；
v1 源码、Schema、规则常量及 A9 冻结测试与登记保持原字节。
两版调用方均提交原始 UTF-8 JSON bytes 和合法只读上下文；
str、bytearray、映射或已处理的模型对象不作为候选接收。顶层前后 JSON 空白合法；
BOM、坏 UTF-8、孤立代理字符、任意层重复键、NaN/Infinity（含数值溢出）、非对象、
围栏、截断和非空白尾随内容均拒绝，不作修复。

下表是唯一消费视图的公共字段。页面、源块、evidence、provenance 序列只接受
list/tuple，构造后冻结；不接收已经覆盖重复键的映射作为成员集合。
来源字符串和坐标不改写。

| 类型 | 权威字段 | 自校验口径 |
| --- | --- | --- |
| `ExtractionIdentity` | extraction_fingerprint、reading_sha256、evidence_map_sha256 | 三个不透明严格非空 ID；由上下文统一核对 |
| `PageFact` | identity、page_no、width、height、origin | 同三元组、唯一原页码、有限正 point 尺寸、封闭原点 |
| `SourceBlock` | identity、source_id、orig、kind、unreliable | 同三元组、唯一 ID、合法 Unicode orig、text/table/formula 与严格 bool |
| `Provenance` | source_id、page_no、bbox、start、end | 源/页面闭包、四元 bbox、orig 半开区间、非空白切片；同条 evidence 内拒绝完全重复定位 |
| `Evidence` | identity、evidence_id、provenance | 同三元组、唯一严格 ID、有序非空 provenance |
| `AllowedEvidence` | identity、evidence_ids | 集合级同三元组；有序 ID 接受 list/tuple 后冻结为 tuple；严格 ID、无重复，允许空 tuple |
| `ReadContext` | identity、pages、source_blocks、evidence、expected_language、mode、allowed_evidence | 先验证完整集合，再冻结；语言显式 zh/en；single/reduce 与集合方向约束 |
| `SourceSlice` | identity、evidence_id、provenance、text、kind、unreliable | `replay()` 从 orig 精确切出，保留来源与全部定位 |

`SourceBlock.kind` 默认 `text`，`unreliable` 默认 `False`。`ReadContext` 的
pages、source_blocks、evidence 默认空 tuple，mode 默认 `single`，allowed_evidence
默认 `None`；identity 与 expected_language 即使在调用语法中可省略，也没有合法缺省值，
缺失时为受控上下文错误。`expected_language` 必须显式为 `zh` 或 `en`，验证器不推断
实际自然语言是否匹配。页面、源块和 evidence 成员的完整合法性由 `ReadContext`
检查，不能因某成员未被候选引用而略过。

上下文允许保留合法 table/formula/unreliable 源事实，是否可支持某字段由下方矩阵
决定，不在构造时一概拒绝。未知模式以 unsupported_mode 拒绝。
公式候选、图片/公式占位及生成展示内容没有 SourceBlock 类型分支；将其 ID 用作
provenance 目标因未知源而失败。上下文只解释给定 orig，不生成这些内容。

上下文顶层选择、成员归属和结果绑定都采用消费身份三元组
`(extraction_fingerprint, reading_sha256, evidence_map_sha256)`；相同 fingerprint
但任一消费内容身份不同也不可互换。三元组是不透明身份，不证明当前选择、真实来源、
正文质量，也不实际计算材料哈希。构造在建索引前验证重复页面/源块/evidence、
矛盾归属、闭包、页码、尺寸和全部 provenance，并防御性冻结调用方集合及 bbox。

provenance 只指向源文本块，种类封闭为 text/table/formula，并有不可靠字符标记。
公式候选、图片/公式占位及生成展示文本均不能作为 orig 目标；没有“生成展示文本”
源标记。页面采用原 PDF 严格正整数页码，不要求连续；尺寸与坐标使用 point，原点
明确为 top_left 或 bottom_left。bbox 精确满足 `0 <= x_min < x_max <= width`，y 同理，
坐标有限且拒绝 bool，不加容差或 clamp。同条 evidence 内重复 provenance 拒绝，
顺序保留而不要求页码单调。ID 不 trim、不规范化，拒绝首尾空白、非法 Unicode
及 Unicode 类别 C 字符。

charspan 的 start/end 为严格整数，按 orig 原字符串的 Unicode code point 半开区间
回放，满足 `0 <= start < end <= len(orig)`；切片须含非空白字符（`str.isspace()`），
允许在组合字符或 ZWJ 内切分。回放、切片与非空判断永不执行 NFKC/全角折叠，
数值归一化仅发生在后续等价比较，不产生新切片或改变定位。
跨页 evidence 保留全部 provenance，数值比较不把分段拼接。

single 禁止附带允许集合；reduce 必须提供 `AllowedEvidence(identity, evidence_ids)`，
集合级携带与上下文相同的三元组。成员有序 list/tuple 接收后冻结；调用方后续修改
集合或来源容器不能改变已冻结范围。构造拒绝缺失、重复、未知成员及跨正文
（包括同 fingerprint、不同 reading/evidence-map 哈希）。允许引用合法子集，
不要求用完全部允许 ID；不因缺集合而退回全文范围。

| 位置与违例 | 安全原因 | 异常边界 |
| --- | --- | --- |
| reduce 缺集合 | missing_allowed_evidence | ReadContextError |
| single 附带集合 | unexpected_allowed_evidence | ReadContextError |
| 非权威类型或无序集合 | invalid_allowed_evidence | ReadContextError |
| 集合内重复 / 非法 ID | duplicate_id / invalid_evidence_id | ReadContextError |
| 集合跨正文 / 未知成员 | identity_mismatch / unknown_allowed_evidence | ReadContextError |
| 模型引用正文不存在的 ID | unknown_evidence | v1 整份拒绝；v2 按下节处理 |
| 模型引用正文存在但未被允许的 ID | evidence_not_allowed | v1 整份拒绝；v2 按下节处理 |

空 tuple 可以构造。此时引用都属于越界，五类保护内容没有有效允许引用时同时报告
`evidence_required`；两项评分理由必填且不可丢弃，因此整份分析不能通过。
原模型 evidence 列表为空、ID 为空字符串时按冻结 Schema 整份拒绝。
`evidence_not_allowed` 与业务层 `evidence_required` 仅适用于 reduce；single 无允许集合。
reduce 在此只验证给定集合，不实现 map/reduce，也不证明集合的生产来源。

## v2 判定顺序与末次丢弃

1. 调用方先构造完整合法 `ReadContext`；领取前可用
   `acceptance_v2.validate_read_context_v2(context)` 重验，返回独立冻结上下文。
   接收入口也重验全部上下文，不能因候选未引用某成员而略过。上下文错误不消耗模型预算。
2. 对完整原始候选执行严格 JSON 与 Schema（含评分），再检查全部有意义文本、语言、
   价值类型条件与重复；该阶段出错即整份拒绝，不继续业务指针与警告。丢弃不能掩盖错误。
3. 业务指针依次检查严格 ID、同列表重复、正文存在性、允许范围；reduce 另检查有效引用
   非空。非末次的任何问题整份 `ReadV2OutputError`；末次两项评分理由的任何问题也整份拒绝。
4. 只有末次的 `main_findings`、`reusable_points`、`key_limitations` 完整列表项可以丢弃。
   任一引用坏即整条丢，不去重、不改引用、不保留部分内容；共享坏 ID 的每条分别丢弃。
5. 丢弃后 main_findings 与 reusable_points 同时为空，且丢弃前至少一者非空，返回
   `$ [output_without_support]`。任务层归为既有 `output_invalid`，没有成功结果。
   原本合法为空、仅局限清空与无证据义务字段不触发。
6. 只为保留条目计算数值及受限内容警告；丢弃事件另生成安全丢弃警告。诊断路径保留
   原始候选索引，不随处理视图的列表压缩而改写。

`ReadV2Discard` 每被丢条目一条，按 main_findings、reusable_points、key_limitations
及原始顺序排列；字段为 `location`（原条目路径）、`item_category`、`ordinal`（原条目
从 1 起）、`reason`（该条首个坏指针原因）、`positions`。同条多错按引用原顺序取首因，
该引用同时符合多类时采用步骤 3 的优先级；reduce 缺有效引用排在逐引用问题之后。
`positions` 仅保留能解析的坏引用定位，按上下文 evidence/provenance 原顺序去重；
每项只含 `source_id/page_no/bbox/start/end`，未知或非法 ID 没有定位。
不另存坏 ID、原文或数值。丢弃不改变原始候选字节。

`ReadV2Result` 返回 identity、mode、degrade_policy、attempt_ordinal、三规则版本、
`analysis` 独立副本、discards、model_warnings、diagnostics、warnings 和精确回放 support。
其余集合为 tuple，敏感字段不进入 repr。`ReadV2Diagnostic` 只含 location、reason、ordinal；
数值序号沿用识别器从 0 起，受限源引用为 0，丢弃警告使用原条目从 1 起的序号。
`ReadV2Warning` 以 model/program 区分来源；模型警告逐字保留（含重复项），程序警告不带
原文、字面量或坏 ID。合并视图及 analysis.degraded_content_warnings 先模型后程序；
程序诊断按路径、原因、序号稳定排序。

同一候选字节、上下文、策略、序号和三规则版本可从零重算相同结果与丢弃清单。
持久消费者保存全部接收依据，用同一入口重算并逐字段核对清单；纯入口不保存业务事实。
新代从序号 1 重新判断，不能继承旧代丢弃许可；版本不支持和历史恢复的责任见下节。

<a id="受限内容矩阵95-已交付"></a>

## 受限内容矩阵

合法源块上的 Docling 解析限制在 v2 中只产生降级警告，不使主要发现、评分理由、
可复用点或关键局限失败。警告不等于人工核对或科学语义蕴含证明。

| 所引证据 | v2 全部保护字段 | v1 历史规则 |
| --- | --- | --- |
| 可靠普通文本 | 允许；数值按规则检查 | 相同 |
| 表格源块 | 结构描述允许且无警告；数值仅受限命中则 restricted_numeric_support 警告 | 主要发现/评分理由/可复用点硬失败；关键局限只警告 |
| 公式区域源字符 / 不可靠字符块 | restricted_source_reference 警告；数值仅受限命中另有警告 | 主要发现/评分理由/可复用点硬失败；关键局限只警告 |
| 公式候选 / 图片或公式占位 / 生成展示文本 | 无 evidence 锚点；引用其 ID 按业务坏指针处理 | 未知 evidence 整份拒绝 |
| provenance 指向不存在源块（unknown_source） | 上下文错误整份拒绝，领取前检查 | 相同 |

单条 evidence 任一 provenance 为公式/不可靠源时，对每段保护文本发出
`restricted_source_reference`。不可靠字符使用与 normalization v1 相同的
`content_reliability.is_unreliable` 纯规则（声明标记或 U+FFFD、非排版控制字符、代理/私用字符）；
警告和数值分类共用其判定。表格结构描述不单独告警。数值仍逐字面量、逐实际切片
比较：至少一条受限片段命中且全部可靠片段不支持它时，发出
`restricted_numeric_support`；可靠片段也支持时不产生该数值警告。
数值在所有引用切片中未命中、范围/单位不支持或无法识别的形状也只告警。
公式或不可靠来源的引用警告不因另有可靠数值来源而取消。

provenance 仍只指向 orig，候选 LaTeX、生成展示文本与占位不成为来源。
合法父源块缺失是正文生产能力缺口，不能给候选补造 evidence。
真实公式父源块覆盖的统计口径及未验范围由
[正文提取契约](fulltext-extraction.md)维护；本纯层不统计真实 Docling 覆盖率。

<a id="数值与警告94-已交付"></a>

## 数值与警告

两版只读复用冻结数值识别器：只提取阿拉伯数字（含全角），中文数字不提取、不产生警告。边界显式按
拉丁字母/数字/小数点定义，保留 CJK 邻接数值。
ERA5、CMIP6、PM2.5、CO2、O3、H2O 等拉丁字母直连标识符以及封闭图/表/式/节/
Fig./Figure/Table/Eq./Section 前缀交叉引用编号排除。单位采用封闭列表与中英别名，
英文交叉引用前缀须具有左侧拉丁词元边界，stable 或 intersection 的后缀不构成
Table/Section。未知相邻词不当单位。

v1 历史常量仍为 `read-numeric-v1` / `read-evidence-v1`。v2 自持
`NUMERIC_RULE_VERSION="read-numeric-v2"`、`EVIDENCE_RULE_VERSION="read-evidence-v2"`、
`CONTENT_LIMITATION_RULE_VERSION="read-content-limitation-v1"`。三版本均不进入
StageInput/模型指纹，不自动触发模型重跑或刷新预算。单位与记法闭集两版共用，大小写保持
表中所列；只有比较使用这些归一化，orig/charspan/text 始终原样回放。

| 等价类 | 接受的记法 |
| --- | --- |
| 距离/长度 | km、公里、千米；m、米；不在 km 与 m 之间换算 |
| 气压 | hPa、百帕 |
| 速度 | m/s、m s−1、m s-1、m s⁻¹、米/秒 |
| 温度/百分比 | °C、摄氏度；%、％；允许数值与单位之间空白 |
| 数字与符号 | ASCII/全角阿拉伯数字、小数点/逗号/正负号；U+2212 等同负号 |
| 单位连接 | 850-hPa ≡ 850 hPa；2-m ≡ 2 m |
| 范围 | en dash、~、～、至、to、连字符；裸前端可继承后端单位，显式端点单位分别核对 |
| 千分位/小数 | 1,000 ≡ 1000；.5 ≡ 0.5；不把小数或千分位拆成子串数字 |
| 科学记数 | 1.2e-3、1.2×10⁻³、1.2x10⁻³、1.2×10^-3；10⁻³ / 10^-3 等同 1e-3 |
| 正负范围记号 | ±0.5 作为独立的带 ± 数值；13±5 与 13 ±5 均检查中心值和误差项，不能由裸 0.5 支持 ±0.5 |

科学记数只作数字记法等价比较，不计算新科学结论。形如 1e、1,00、2.3.4、
1.2×10^?、无指数的 1.2×10、10^unknown、210⁻³、110^3 和 1/2 等不能可靠解释的形状产生
unrecognized_numeric_form，不把内部组件数字当支持。识别器只对明确覆盖的形状
负责，不能识别所有自然语言中的数值依赖。10 幂只在完整数值词元边界归一化，
不从其他底数的尾部截取 10；其他底数不作算术求值。中文数字是接受的漏检边界。

30°N 只提取裸 30，°N 不属于单位表；1979–2020 是同切片范围；
(Smith et al., 2020) 中 2020 是普通数值。警告只由陈述侧提取值驱动，来源中多出
的数字不产生诊断。Table 3 比较 12 个流域仅排除编号 3，12 仍需自己的引用支持。

匹配只检查该陈述自己的 provenance 切片，范围端点须同切片出现。裸前端可继承
后端单位，`2–3 m` 仍可由 `2 and 3 m` 支持；陈述与来源各端的显式单位都保留，
`3 km–5 km` 不能由 `3 m and 5 km` 支持，明确的 m/km 冲突不被继承规则消除。
带或不带空格的连字符范围均完整检查两端，`3-5 km` 不能由 `3 to 4 km` 支持；
负数端点保留符号，`-3--1 km` 不把右端点误当成正数。
不同数值可各自命中不同引用切片。`3` 不因 `30`、`13`、`3.5` 或 `0.3` 通过。
不换算单位、不推导、不补数字、不改结论或评分；无法可靠解释的数值形状明确降级。
块越大，论文别处的相同数值越可能落在同一支持片段；本边界不证明科学语义蕴含。

结果提供三个视图：原模型警告逐字保留（含重复项）、安全结构化程序诊断、带 origin
的只读合并视图。程序诊断按字段路径/原因/字面量序号排序；报告定位使用诊断，
不解析警告字符串。模型即使伪造相同模板，也不能改变诊断或来源。
v1 程序模板可在受控分析视图包含触发数值；v2 只生成不含字面量的中/英文核对指引。repr、异常和结构化
诊断仅携安全位置/原因/序号，不含全文、片段、响应或数值字面量；纯验证器不写日志。
幂等指同一原始字节与上下文重复校验结果相等，不把追加警告后的分析当新模型原文。

### v1 历史结果视图

`ReadValidationResult` 提供 `identity`、`mode`、`evidence_rule_version`、
`numeric_rule_version` 与精确回放的 `support`；`support` 保留整个上下文的全部
provenance 切片，不限于本候选引用的成员。结果保存的分析依据为不可变处理后字节，
`analysis` 每次返回独立模型副本，修改副本的 list 不改变结果。该分析的
`degraded_content_warnings` 是模型警告在前、程序警告在后的处理视图；原始 bytes
由调用方另行保存，不能用处理视图冒称原始成功响应。

安全诊断类型与原因定义在不依赖上下文或结果层的 `reading.diagnostics`，
`reading`、`reading.result.ReadDiagnostic`、`reading.numbers.NumericReason` 均保留导出。
安全诊断为 `ReadDiagnostic(location, reason, ordinal)`；ordinal 是该字段抽取值的
零基序号，不含数值或原文。`NumericReason` 闭集为 number_not_supported、
range_not_supported、unit_not_supported、unrecognized_numeric_form、restricted_numeric_support。
程序警告采用固定中/英文模板，包含同一分析中的触发字面量；`ReadWarning` 以
origin=model/program 明确来源。默认 repr/str 隐藏候选、source ID、片段、模型警告和
程序警告正文。

<a id="配置及恢复范围9798-已交付"></a>

## 配置与恢复组合

Read 契约仅经显式 `settings.contracts.read` 选择进入配置版本登记与快照闭包。
未选/null 不读取该契约磁盘材料，保留 `read_contract` 缺项与旧快照身份，
Read 投影中的 contract 保持 `None`。显式选择填入 Read 投影 contract 槽，不改变其余
五投影或校准基线；配置 ready 只说明材料齐全，不授予生产执行或校准资格。
配置材料路径、槽要求、缺项顺序、原子登记、历史 load、diff 和 CLI 退出码分别见
[运行配置](runtime-config.md#模型提示词与契约)、
[Read 配置](runtime-config.md#read-配置与分块身份)和
[阶段配置投影](config-projections.md)。历史加载回放已登记字节，不回退当前文件。

[独立示例](../../examples/config/settings-read-ready.yaml)选择 reading 模型、Prompt、
adapter、read 配置（chunking v1）与 read 契约，配有非占位示例 Profile；它不代表用户
真实 Profile 或执行就绪。[旧示例](../../examples/config/settings-read.yaml)未选择
契约，仍缺 `read_contract`；未选 adapter 单独显示 unconfigured，不增加必选门禁。

<a id="恢复范围98"></a>

### 恢复范围

恢复组合保存历史配置和已登记 `model_success_response` 候选原始字节；无业务引用的
成功响应也可备份。恢复后，调用方从恢复库加载明确历史配置并读取原始响应，提供
相同合法 `ReadContext` 时，公共入口确定性重现绑定、规则、诊断、带 origin 的合并
视图和回放切片。消费上下文不是该恢复组合的持久化产物；不发布合成 extraction、
不定义上下文序列化、不新增 analysis 成功行。

备份/恢复的前置、参数、数据库 revision 准入、目录安全、原子发布、拒绝原因、
退出码及失败后的重试见[备份与隔离恢复](backup-restore.md)。配置登记字节损坏或缺少
引用由历史配置闭包以 `config_invalid` 拒绝；响应物理坏字节/缺文件由 blob/hash 边界
拒绝。拒绝不修改批次、不发布恢复目标；历史配置、原始响应、快照/投影身份不变，
读取不升级、激活或执行任务。默认快照 repr/str 隐藏 payload_json，显式访问不改变
载荷与身份。备份保证已保存字节完整，不在缺少上下文时判断 Read 业务合法；
该判断仍由读回后的公共验证入口完成。

固定上下文回放不证明源文本由生产制品恢复、真实 evidence-map 格式或当前正文选择。
既有双快照/四候选的隔离恢复证明范围见
[历史恢复证据](../verification/contracts-read-validation-history.md#恢复范围98)。

## 错误与拒绝

v1 的 `ReadContextError` / `ReadOutputError` 保留；v2 自持
`ReadV2ContextError` / `ReadV2OutputError` 与 `ReadV2Category`。
直接构造复用的 ReadContext 时仍发 v1 上下文错误，v2 预检/接收把相同安全 wire 原因
转成 v2 issue；错误在退出捕获后转换，无含输入的异常链。
上下文和策略错误不属于 `output_invalid`；纯接收器不创建或消耗预算。

| 拒绝层 | 原因 | v2 结果 |
| --- | --- | --- |
| 上下文类型、身份、重复、归属 | invalid_context、invalid_identity、duplicate_id、identity_mismatch | 整份上下文错误 |
| 页面、源块、provenance | invalid_page、invalid_source、unknown_source、unknown_page、invalid_bbox、invalid_charspan、empty_support、duplicate_provenance | 整份上下文错误 |
| 模式与允许集合 | unsupported_mode、missing_allowed_evidence、unexpected_allowed_evidence、invalid_allowed_evidence、unknown_allowed_evidence | 整份上下文错误 |
| 策略或序号 | invalid_degrade_policy、invalid_attempt_ordinal | 整份调用方错误 |
| JSON/Schema（含空 evidence、空字符串 ID） | invalid_json、missing_field、extra_field、invalid_type、invalid_enum、invalid_score、invalid_evidence_id、evidence_required | 整份输出拒绝 |
| 全部文本/语言/价值类型 | invalid_text、language_mismatch、value_types_required、duplicate_value_type | 整份输出拒绝 |
| 业务指针 | invalid_evidence_id、duplicate_evidence、unknown_evidence、evidence_not_allowed、evidence_required | 非末次/评分理由整份拒绝；末次三类列表项丢弃 |
| 丢弃后主体全空 | output_without_support | 整份输出拒绝，任务层归 output_invalid |
| 合法受限来源、受限数值、普通数值不匹配 | restricted_source_reference、restricted_numeric_support、number_not_supported、range_not_supported、unit_not_supported、unrecognized_numeric_form | 仅安全诊断和警告 |

v2 另以 `evidence_item_discarded` 安全诊断标明整条丢弃；具体首因在丢弃清单中。
issues 只含安全路径、类别和中文指引，额外键统一为 `<额外字段>`。
Schema 失败后不继续业务校验，完整候选检查失败后不继续指针或警告；非末次/评分理由
指针失败也不计算警告。上下文按检查顺序报告首个问题，不承诺一次列出全部问题。
纯函数不自动修复、重试、保存、调用模型，也没有 CLI 退出码。

历史 v1 分析按原接收版本读取；v1 因受限内容失败而不存在的分析不追溯生成。
持久消费者按所记证据规则版本选择重验入口；未知证据版本应以
`unsupported_rule_version` 拒绝。未知数值/受限内容警告版本保留当时警告，不因无法重算
拒绝分析或声称等价；支持旧策略时可重算比对。保存/备份/恢复闭包由
[Body](../roadmap.md#module-body) 的持久消费者实现，纯接收本身不提供该闭包。

<a id="b-首个真实-read-消费者前置111"></a>

## 不提供／不证明

- 不提供正文生产、当前正文选择、真实 PDF provenance 或生产 evidence-map 协议；
  不验证 orig 的持久成员哈希覆盖与真实恢复闭包。承接责任见
  [Body/B](../roadmap.md#module-body)与[四刊正文供给 F](../roadmap.md#module-f)。
- reduce 只检查给定允许集合，不证明它真实来自本轮 map；不提供 map 输出契约、分块、
  长文编排或修正调用，承接责任见[长文 Read G](../roadmap.md#module-g)。
- 不提供 Read StageInput、任务/预算/租约/retry、analysis 业务持久化与生产接收器；
  三规则版本随结果返回且不进入模型指纹；持久化消费承接责任见
  [Body/B](../roadmap.md#module-body)。
- 不调用第二个模型判断语义蕴含，不证明科学正确性或模型质量；真实模型、生产 Pi、
  四刊质量、校准、报告及 NAS 不因纯验证或固定上下文恢复而取得资格。对应责任见
  [Live](../roadmap.md#module-live)、[F](../roadmap.md#module-f)、
  [D](../roadmap.md#module-d)、[G](../roadmap.md#module-g)、
  [H](../roadmap.md#module-h)、[I](../roadmap.md#module-i)。

<a id="集成验收与明确未验证"></a>
<a id="92-覆盖台账"></a>
<a id="42-条-user-stories"></a>
<a id="21-条-implementation-decisions"></a>
<a id="testing-decisions-的-20-个验收面"></a>
<a id="四条评论及最终裁决覆盖"></a>

## 相关

既有覆盖编号、评论裁决覆盖与集成证明范围见
[历史覆盖台账](../verification/contracts-read-validation-history.md#92-覆盖台账)，
本页不以历史通过推断当前门禁或 live 就绪。
验收状态格式、可信终态及范围字段由[验收状态 Contract](verification-status.md)定义。

v2 独立覆盖与差异矩阵见 [D1 台账](../verification/issue-157-read-v2-delivery.md)。

依据：[#157](https://github.com/MeteoBoy4/PaperRadar/issues/157)、[#155](https://github.com/MeteoBoy4/PaperRadar/issues/155)、[#92](https://github.com/MeteoBoy4/PaperRadar/issues/92)、[#93](https://github.com/MeteoBoy4/PaperRadar/issues/93)、[#94](https://github.com/MeteoBoy4/PaperRadar/issues/94)、[#95](https://github.com/MeteoBoy4/PaperRadar/issues/95)、[#96](https://github.com/MeteoBoy4/PaperRadar/issues/96)、[#97](https://github.com/MeteoBoy4/PaperRadar/issues/97)、[#98](https://github.com/MeteoBoy4/PaperRadar/issues/98)、[#99](https://github.com/MeteoBoy4/PaperRadar/issues/99)。

目标与判据：[规格 §4.10](../../intent/draft.md#410-read-agent)；
决策：[ADR-0042](../adr/0042-accept-read-v2-with-final-attempt-degradation.md)、[ADR-0025](../adr/0025-allow-local-formula-candidates-with-source-review.md)、
[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)；
生产消费者责任：[路线图 Body/B](../roadmap.md#module-body)。
