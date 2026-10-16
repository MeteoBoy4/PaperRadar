# 运行配置快照契约（已交付配置切片）

当前开放六段式 Research Profile、主题集合、期刊信誉集合、三槽 models 文件、boundary/value/reuse/reading 提示词、Read 分块身份、四份 A1 冻结契约、复用升级参数、正文提取配置，以及三槽 Pi adapter 材料和完整有效系统 Prompt。配置就绪仅说明这些本地材料齐全且合法，不证明模型调用、正式校准或自动精读可用。
公共 Python 入口是 `paper_radar.config.check_config(settings_path, database)`、
`compile_config(settings_path, database)`、`load_config_snapshot(database, snapshot_id)` 和
`upgrade_database(database)`。前三个返回 `RuntimeConfigSnapshot`；错误为脱敏的
`ConfigError`。`check` 和 `load` 只读；`compile` 只写已迁移的既有库；只有 `upgrade`
可创建库。不存在、未初始化或 revision 不匹配的库均拒绝配置操作。
另提供纯单快照 `project_config(snapshot)`、纯比较 `compare_config_snapshots(before, after)`
与只读服务 `diff_config_snapshots(database, before_id, after_id)`；类型、载荷及格式演进见
[阶段配置投影与比较](config-projections.md)。
另提供只读 `list_config_snapshots(database)` 与
`resolve_config_snapshot_reference(database, reference)`；返回类型、排序、前缀规则和
完整操作示例见 [历史快照发现与引用](config-snapshots.md)。数据库选择档案库，
快照引用选择其中的历史配置；列表不表示完整性已验证或配置已启用。

## 输入与路径

`settings.yaml` 是可变的纯 selector，不登记为版本，也不在里面填写 Profile 正文、
provider/model、secret 或凭据引用。check/compile 必须显式传 `--settings` 和
`--database`；diff CLI 只需两个快照引用（完整 ID 或唯一短前缀）和必填 `--database`。
公共 load/diff 服务仍只接受完整 ID；`config snapshots list --database ...` 只读发现记录。
传入的 settings 所在目录视为 `config/`，其父目录为配置根；路径不依赖当前工作目录。
`profile: profile-v1` 精确选择 `config/profiles/profile-v1.yaml`。声明版本只允许小写
字母开头，后续为小写字母、数字、点、下划线或连字符，长度至多 64。不能用路径
穿越版本目录。当前不支持自定义文件路径。

`settings.yaml` 接受以下固定字段，全部可省略：

| 字段 | 当前值 | 说明 |
| --- | --- | --- |
| `profile` | 声明版本或 `null` | 缺失或 `null` 都表示 `unconfigured`，允许保存未就绪快照。 |
| `topics` | 声明版本或 `null` | 选择 `config/topics/<version>.yaml`；未选择为缺项，空集合与全部停用均合法且已配置。 |
| `journals` | 声明版本或 `null` | 选择 `config/journals/<version>.yaml`；未选择为未配置，不影响任何阶段就绪。 |
| `extraction` | 声明版本或 `null` | 选择 `config/extraction/<version>.yaml`；[正文提取配置](extraction-config.md) 定义工具链、模型清单和有效策略。 |
| `read` | 声明版本或 `null` | 选择 `config/read/<version>.yaml`，登记 Read 分块算法身份；缺失或 `null` 表示未配置。 |
| `escalation` | 声明版本或 `null` | 选择 `config/screening/<version>.yaml`；文件内登记触发集合、固定摘录顺序和算法身份。 |
| `models` | 声明版本或 `null` | 整份 `config/models/<version>.yaml`；三个模型槽在文件内具名，settings 不内联 provider/model。 |
| `adapters.screening` / `adapters.reuse_assessment` / `adapters.reading` | 各自为声明版本或 `null` | 独立选择 `config/adapters/<version>.yaml`；[Pi adapter 配置](adapter-config.md) 定义系统指令、资源、参数、审计版本与固定策略。 |
| `prompts.boundary` | 声明版本或 `null` | 绑定 `prompts/screening/boundary-<version>.md` 的原始 UTF-8 字节。 |
| `contracts.boundary` | `v1` 或 `null` | 从 `contracts/screening/boundary/v1/{schema,manifest}.json` 检查并登记两份原始字节。 |
| `prompts.value` | 声明版本或 `null` | 绑定 `prompts/screening/value-<version>.md` 的原始 UTF-8 字节。 |
| `contracts.value_prediction` | `v1` 或 `null` | 检查并登记 `contracts/screening/value-prediction/v1/{schema,manifest}.json`。 |
| `prompts.reuse` | 声明版本或 `null` | 绑定 `prompts/screening/reuse-<version>.md` 原始 UTF-8 字节。 |
| `contracts.reuse_assessment` | `v1` 或 `null` | 检查并登记 `contracts/screening/reuse-assessment/v1/{schema,manifest}.json`。 |
| `contracts.decision_reasons` | `v1` 或 `null` | 检查并登记 `contracts/screening/decision-reasons/v1/{schema,manifest}.json`。 |
| `prompts.reading` | 声明版本或 `null` | 绑定 `prompts/reading/<version>.md` 原始 UTF-8 字节；缺失或 `null` 为缺项。 |

当前封闭逻辑名称为 `profile/profile`、`topics/topics`、`journals/journals`、`models/models`、`escalation/escalation`、`extraction/extraction`、`read/read`、`adapter/pi-rpc`、`prompt/pi-system`、`prompt/boundary`、`prompt/value`、`prompt/reuse`、`prompt/reading`，以及 `contract_schema`/`contract_manifest` 下的 `boundary`、`value-prediction`、`reuse-assessment` 与 `decision-reasons`。快照包络中的材料条目含
`kind`、`name`、`version`、`raw_sha256` 和编译值；后续新增材料种类只增加带
种类和版本键的条目，不提升编译格式版本。只有包络结构改变时才提升格式版本。
选择了尚未开放的非空字段会返回 2，并给出字段路径；不会忽略选择。
`prompt/pi-system` 的版本引用来自 adapter 资源清单，
位置在 `config/prompts/`，与业务 Prompt 分开登记。

Profile 文件的 `version` 必须与 selector 完全相同。六段字段为 `background`、
`core_questions`、`transferable_methods`、`available_data_and_tools`、
`theory_and_cognitive_interests`、`constraints_and_exclusions`。每段为文本或缺失。
缺失或 `null` 是 `unconfigured`；去掉首尾空白后为空或**精确等于 ASCII `...`**
是 `placeholder`；其余文本为 `configured`，包括 `…`、`......`、日期文字。
本票仅判断填写状态，不判断资料真实性。只有六段都配置时 Profile 槽为
`configured`；有占位段时为 `placeholder`，否则为 `unconfigured`。

## 主题集合

主题文件必须有与 `settings.topics` 相同的 `version` 和必填列表 `topics`。列表可为空，
不能为 `null`。每项只接受必填 `id`、`name`、`description`、`enabled`：

```yaml
version: topics-v1
topics:
  - id: stable-id
    name: 中文名称
    description: 语义描述
    enabled: true
```

ID 必须匹配 `^[a-z][a-z0-9-]{0,63}$`，不接受大小写或空白变体，不做自动修正，
集合内重复 ID 拒绝。name/description 必须为 strip 后非空的文本，保存原文本；
不设占位词、不判断真实性。enabled 必填，无默认值，只接受明确的 `true`/`false`，
`yes`、`on`、`True`、数字、引号内布尔文本及 `null` 均拒绝。未知字段拒绝；
没有权重、关键词搜索或由 Agent 创建/修改主题的入口。

完整快照保存全部主题（含停用主题），按 ID 排序，保留声明版本、原始字节和哈希。
公共结果 `topics_status` 使用 `paper_radar.config.TopicsStatus` 二值枚举，仅允许
`configured` 或 `unconfigured`，没有 placeholder；`enabled_topics` 为按 ID
排序的不可变元组，每项只有 ID/name/description，不含版本、原始字节哈希或 enabled。
空集合与全部停用的 `enabled_topics` 同为 `()`，但完整快照与历史材料不同。
未选择 topics 版本时即使磁盘有文件也仍未配置，不能与合法空集合混同。
新增版本可切换选择，旧快照仍从 SQLite 中回放，不读取当前文件。

当前装载与历史回放通过 `config/material_assembly.py` 的 `MaterialAssembly`
共用 Profile/models/topics/journals/escalation/extraction/read 的解析、声明版本核对、
编译值生成与选择完整性检查。调用方交入原始 `Material`；配置对象和对应材料记录
由同一次验证配对，并集中组装为纯配置层的 frozen `SelectedMaterials`，交给
`compile_snapshot(materials)` 编译。调用方不再分别构造七类配置对象和材料集合。
`SelectedMaterials` 不包含路径、连接或执行计划；frozen 外壳不表示内部
Pydantic 对象或编译字典具有深度不可变性。

来源仍负责文件读取或历史包络、哈希与引用检查；提示词、冻结契约和 Pi 材料仍由
各自逻辑验证后参与组装。新模块的入口接收材料及历史条目，不采用七个固定配置
参数；当前 YAML 种类、模型与文件布局集中在内部目录中，后续可在该模块内增加
材料解码方式，不要求调用方提供两套配对数据，也不预建通用插件机制。
模型适配器仍可取得已验证的 `Models` 做协议检查；正文提取的
`compiled_config()` 特殊语义保留，纯编译器不引入 YAML、存储或 CLI 依赖。

版本格式继续由公开 `valid_declared_version` 统一校验。当前来源的字段级错误与
历史来源的损坏错误保持原检查顺序和中文文本。公共 check/compile/load 参数、
持久包络格式、快照身份序列化及阶段配置投影保持一致，无需 migration。

## 期刊身份与信誉

`settings.journals` 选择带内部声明版本的 `config/journals/<version>.yaml`；版本必须与
selector 相同。顶层必填 `version` 和 `journals` 列表；空列表合法且已配置，`null`
或缺少列表拒绝。每项接受必填文本 `issn_l`、`name`、`tier` 和可省略的 `issns`
文本列表（默认 `[]`），未知字段拒绝：

```yaml
version: journals-v1
journals:
  - issn_l: 2169-897X
    issns: [2169-897X, 2169-8996]
    name: 用户维护的期刊名称
    tier: preferred
```

ISSN 只接受七位 ASCII 数字加数字或 `X/x` 校验位，可在第四位后加一个连字符；
不接受首尾空白或其他分隔符。按 mod-11 验证校验位后，统一为 `NNNN-NNNC`
（末位大写 `X`）。如 `1477870x` 规范为 `1477-870X`。`issn_l` 作唯一身份，
生效匹配集合为 `{issn_l} ∪ issns`；`issns` 可以显式包含本条 ISSN-L，但其列表内
规范化后重复拒绝。跨条目的匹配集合不得重叠，包括某条 ISSN 撞另一条 ISSN-L。
名称 strip 后必须非空，保存原文本；同名不同号合法。`tier` 仅接受精确的
`preferred`、`normal`、`low`，无默认档位。离线不核验刊名、ISSN-L 映射或刊号归属。

快照保存声明版本、精确原始字节哈希和完整编译集合，期刊按规范 `issn_l` 排序，
`issns` 按规范刊号排序。公共结果 `journals_status` 为 `JournalsStatus` 的
`configured` 或 `unconfigured`；`journals` 是不可变的 `JournalSemantics` 元组，
每项含 `issn_l`、不可变 `issns`、`name` 与 `JournalTier`。未选择时与合法空集合
均返回 `()`，由状态区分；二者的完整快照身份不同。类型由 `paper_radar.config`
公开。CLI check/compile 只显示期刊集合状态，不打印名称、刊号或原始配置正文。

同版本改变任何字节（包括注释、格式或等价刊号写法）拒绝；改变信誉、名称或刊号
须新建声明版本并切换 selector。旧字节和快照永久保留；load 从 SQLite 回放，不读
当前配置文件，损坏不回退。沿用配置版本表与事务，无新增 journals 业务表或 migration。
期刊配置只进入完整快照，不进入六个阶段的就绪必需项、阶段语义对象或校准基线；
本票不执行论文匹配、评分、排序或来源抓取。期刊变化只影响完整快照与登记身份，
六阶段投影和校准基线保持不变。
合成示例为 `examples/config/settings-journals.yaml`，不能作为正式校准资料。

## 模型、提示词与契约

models 文件必须有 `version` 和 `screening`、`reuse_assessment`、`reading` 三个具名槽；每槽写 `null` 或严格对象。对象允许 `provider`、`model`、`protocol`、`temperature`、`top_p`，未知字段均拒绝。`provider` 与 `model` 是文本，`protocol` 为 `json_schema`、`json_object`、`prompt_only` 之一。`temperature` 是 0.0–2.0 的有限数字，默认 0.0；`top_p` 是大于 0 且不超过 1 的有限数字，默认 1.0。不得填写凭据、自由参数字典或 fallback 列表。先判占位：`provider` 或 `model` 去除首尾空白后精确等于 `REQUIRED`、`REQUIRED_FOR_FORMAL_CALIBRATION`、`REQUIRED_FOR_READ` 之一时，槽为 `placeholder`；否则三项缺失、为 `null` 或 provider/model 为空白时，槽为 `unconfigured`。其余非空文本视为已配置；此处不探测供应商能力或读取凭据。三槽可以写相同的 provider/model，但各自保留身份。

```yaml
version: models-pi-v1
screening:
  provider: example-provider
  model: example-model
  protocol: prompt_only
reuse_assessment:
  provider: example-provider
  model: example-model
  protocol: prompt_only
reading: null
```

V1 的 Pi 接入选择 `prompt_only`（[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)）；
上例与新增的 `examples/config/models/models-pi-v1.yaml` 一致，仅为配置完整性示例。
配置编译器保留 `json_schema`、`json_object` 和 `prompt_only` 的既有受控枚举，
以回放历史材料；它不调用 Pi、不探测 provider 能力，也不执行协议切换。
已有 `models-v1` / `models-reuse-v1` 不改写，改选目标协议应创建新的 models 版本。
后续 Pi 执行层需另行检查参数支持、运行资源与隔离，不能把 `ready` 解释为执行就绪。
提交工具升级的协议名称、配置映射与权威 Contract 尚未开放，不能以 `json_schema`
伪装该通道，也不能在失败时自动切换协议。

提示词的逻辑名为 `boundary`、`value`、`reuse` 或 `reading`，声明版本来自对应 `settings.prompts.*`，Prompt 本身无需内嵌版本。文件去除首尾空白后为空或精确等于 ASCII `...` 时为占位。两个声明版本可登记完全相同的 Prompt 原始字节；同一版本任何字节变化都拒绝。Profile 的文件内版本与 selector 一致性仍是强制要求。
`prompt/reading` 是 Read 业务提示词，与 `prompt/pi-system` 的有效系统指令使用不同登记键。
四个业务逻辑名由纯配置类型 `paper_radar.config.schema.PromptName` 统一声明，
独立于阶段名（Read 阶段为 `read`，业务 Prompt 为 `reading`）。加载服务以固定
路径表选择材料；这项内部重构不改变 selector、登记键、文件布局或快照身份。

活跃 boundary、value-prediction、reuse-assessment 与 decision-reasons 契约只支持 A1 权威 `v1`。check/compile 调用其公开只读检查，并将同一份通过检查的 schema 与 manifest 字节分别登记；它们的哈希和编译值一起进入快照。缺失、损坏、版本错误或内容漂移使整次命令失败，错误显示受控类别与中文处理指引，不会修复或导出。历史 load 从数据库核对已登记字节与快照身份，即使原冻结目录后来被移动或损坏，历史仍可读取。

严格 YAML 只接受单文档、UTF-8、普通标量/列表/映射。重复键、锚点/别名、合并键、
自定义 tag、非有限浮点数和未知字段均拒绝。只有小写 `true`/`false`、`null`/`~`
会隐式转型；`yes`/`on` 是普通文本，日期也保留为文本。字段类型严格校验。
终端错误只给字段路径与受控原因，不回显输入值、原始异常或 Profile 正文。

## 复用升级参数与算法身份

`escalation: reuse-escalation-v1` 选择 `config/screening/reuse-escalation-v1.yaml`。
严格类型为 `paper_radar.config.escalation.Escalation`，只接受以下字段：

```yaml
version: reuse-escalation-v1
reuse_escalation_research_values: [3]
excerpt_priority: [availability, methods]
excerpt_selector_version: v1
suggestion_rule_version: v1
```

| 字段 | 必填性、默认值与约束 |
| --- | --- |
| `version` | 必填声明版本，必须与 selector 完全一致。 |
| `reuse_escalation_research_values` | 可省略，默认 `[3]`；非空列表，元素为严格的 1–5 整数，重复拒绝。`null`、布尔、浮点、文本均拒绝。 |
| `excerpt_priority` | 必填列表，只接受精确的 `[availability, methods]`；反转、重复、增减或未知种类拒绝。 |
| `excerpt_selector_version` | 必填，代码受控的 `ExcerptSelectorVersion.V1`（`v1`）；未知版本或非文本拒绝。 |
| `suggestion_rule_version` | 必填，代码受控的 `SuggestionRuleVersion.V1`（`v1`）；未知版本或非文本拒绝。 |

省略触发集合时，代码声明的默认值也经过同一类型、非空、去重与排序校验。
当前默认仍为 `[3]`，不会改变现有合法材料的编译语义或快照身份。

触发字段表达研究价值的**集合成员关系**，不能解释成 `>=3` 阈值；V1 默认集合
只有 `{3}`。父 spec 评论中的 `research_value_triggers` 与 draft §3.7 原单数名
`reuse_escalation_research_value` 都只映射到权威字段 `reuse_escalation_research_values`；
这两个旧名不接受为输入，不能同时维护两份参数。参数版本文件的全部字节照常登记，
同一已登记版本即使只改注释也拒绝。集合编译为排序列表；公共快照的 `escalation`
是 `EscalationSemantics | None`，提供不可变、升序的 `reuse_escalation_research_values`
元组、固定的 `excerpt_priority` 元组和两个受控算法版本，不包含声明标签或原始哈希。
未选择文件时为 `None`。新版本的 `[2, 3]` 和 `[3, 2]` 原材料及完整身份不同，但
上述集合语义相同；suggestion 投影按升序集合语义生成，校准基线保持相同身份。

父 spec 补充二第 26 条提出反转 excerpt_priority 作为有序列表正例，与 draft
§4.5 和 ADR-0022 的 availability 优先约束冲突。按 Issue #19 评论保持既定顺序，
不开放生产反转配置。有序列表的序列化测试使用隔离 fixture。
固定顺序仍是摘录选择语义；它与算法身份应进入相应投影及校准基线。

两个算法版本只是代码受控的受支持身份，不登记独立内容文件，不构造假字节或
原始哈希。它们不能作为无意义声明标签从语义输入剔除。参数文件保留它们的真实
选择。**A2 无法自动检测同算法版本下的代码语义变化**，需要评审和版本冻结纪律
保证有语义变化时声明新受支持算法版本。此票不执行摘录选择或筛选建议规则。

## Read 配置与分块身份

`settings.read: read-v1` 选择独立 `config/read/read-v1.yaml`；权威配置类型为
`paper_radar.config.read.ReadConfig`，只接受以下两个必填字段，无默认值：

```yaml
version: read-v1
chunking_version: v1
```

`version` 是声明版本，格式与其他 YAML 材料一致，必须与 selector 相同；
`chunking_version` 是代码受控 `paper_radar.config.ChunkingVersion.V1`。
只接受文本 `v1`，未知值、`null`、数字、布尔或缺失均拒绝。未知字段拒绝。
读取/编译结果的 `RuntimeConfigSnapshot.read` 为不可变 `ReadSemantics | None`，
只暴露有语义的 `chunking_version`；未选择时为 `None`，不会合成默认算法。
该身份只进入 read 配置投影，不进入 Screening/reuse 或校准基线。

`read/read` 的 YAML 原始字节、声明版本与编译值照常原子登记；修改模型、
业务提示词或 Read YAML 均须新增相应文件版本。同内容可以改用新的声明标签，
完整快照身份会变化；普通声明标签不进入语义投影，但受控 chunking 算法身份
必须保留。算法自身没有内容文件或独立字节登记；A2 无法检测同算法版本下的
代码语义变化，需通过评审与版本冻结纪律保证语义变化时声明新受支持版本。

模型仍使用共同 models 文件中的独立 `reading` 槽，遵循上文模型字段、默认值、
占位词和参数范围；Read 提示词与 chunking 均不要求 Screening/reuse 材料。
合法 Read 变更可保存新快照，boundary 配置完整性不变。历史加载从 SQLite
登记内容重建，即使源文件被删除或当前 selector 已切换，仍保留旧模型和提示词。
没有 Read 材料的历史快照保持包络格式和身份，无需 migration。

当前没有权威 Read 输出契约，`contracts.read` / `contracts.reading` 为未知字段，
不能通过磁盘 Schema、测试 Schema 或手写 JSON Schema 让 Read 就绪。
Read 恒为 `not_ready`，始终包含 `read_contract`；其余缺项见下表。
不执行分块、模型调用、协议探测或凭据读取。输出语言、正文制品、paper ID、
任务及其他论文/调用输入均不属于运行配置快照，配置中出现时按未知字段拒绝。
Read 模型、Prompt、chunking 与 reading adapter 的变化只影响 read 投影，基线不变。

## 身份、登记与回放

`config_versions` 以 `(kind, name, declared_version)` 为不可变键，保存精确 UTF-8
原始字节及 SHA-256。相同键、相同字节幂等；即使只改注释或空白，同键不同字节
也拒绝，必须声明新版本。校验、哈希和登记使用同一份内存材料。

快照身份是以下包络的规范 JSON 字节的 SHA-256（示意仅展示一条条目；materials 含全部已选材料）：

```json
{"format_version":1,"materials":[{"config":{"version":"profile-v1"},"kind":"profile","name":"profile","raw_sha256":"...","version":"profile-v1"}],"selectors":{"profile":"profile-v1"}}
```

示意中的 `config` 实际含 Profile 的全部六段。规范格式使用 UTF-8、按键排序、
紧凑分隔符、非 ASCII 字符原样编码、`null` 明确编码、列表保持给定次序、拒绝
NaN/Infinity；浮点采用 Python `json.dumps` 的浮点表示。材料条目按种类、逻辑名、
声明版本排序。身份包含编译格式版本、选择、版本引用、原始哈希及编译值，不包含
文件路径、时间、数据库行号、凭据或论文输入。此序列化独立于 A1 冻结契约排版。

快照、版本登记及引用在一个 `BEGIN IMMEDIATE` 事务提交；重复编译不刷新
`created_at`。历史加载只使用库内原始材料，重校验版本哈希、引用、编译格式、
规范载荷和身份。当前 selector 或原文件变化、消失都不改变旧快照。未知历史
编译格式直接拒绝，不能按新规则静默重算。SQLite 连接集中开启外键并设 5 秒
`busy_timeout`。显式升级设置 WAL；普通配置操作不切换 journal mode。

### 并发、失败与恢复

公共 `compile_config(settings_path, database)` 在事务前将所选材料一次性固定为
不可变内存字节，校验、哈希与保存始终使用该材料。等待锁期间即使来源文件被
替换，提交也只对应已读取的材料；编译器不写回任何输入文件。这个保证以单次
读取的材料为单位，不承诺多个来源文件在外部编辑期间具有跨文件原子性。

所有材料共用同一登记协议，事务不按 Profile、Prompt 或其他材料种类分支。
`BEGIN IMMEDIATE` 先取得写锁，再读取并核对 `(kind, name, declared_version)` 的
原始哈希和精确字节；新版本、快照与全部引用在同一短事务提交。竞争等待结束后
重新读取已提交事实，不能沿用等待前的“未登记”判断。复用快照前还核对其载荷和
完整引用集合；已有记录损坏则失败，不覆盖或自动修复。
版本行缺失但历史引用仍存在时，check/compile 均报版本引用损坏，不从可变文件
补回历史材料。只读 check 在同一显式读取事务中核对版本与引用，避免并发提交
夹在两次读取之间时误报损坏；该事务不登记任何配置事实。

| 结果 | 公共服务与 CLI 行为 | 后续处理 |
| --- | --- | --- |
| 同材料重复或并发编译 | 返回同一 `RuntimeConfigSnapshot`；CLI 退出 0，成功输出与首次相同，不刷新 `created_at` | 可直接使用返回的完整快照身份 |
| 同声明身份不同字节 | `ConfigError`，原因含“声明版本已登记不同字节”；CLI 退出 2 | 新建声明版本并修改 selector，不能覆盖旧登记 |
| 写锁等待超时 | `ConfigError`：“数据库忙（锁等待上限 5 秒）；请稍后重试”；CLI 退出 2 | 等其他写事务结束，再显式重试原输入 |
| SQL 执行失败或连接中断 | `ConfigError`，受控数据库原因；CLI 退出 2 | 检查数据库状态，排除故障后重跑原输入 |
| 进程在提交前被终止 | 没有成功返回；重开连接不含该事务的任何新版本、快照或引用 | 使用同一数据库重跑原输入，旧快照保留 |
| 提交完成后调用方未收到结果 | 数据库可能已有完整结果 | 原输入重跑会校验并复用该结果 |

锁等待预算是固定的 SQLite `busy_timeout=5000` 毫秒，不提供配置选项；不启动
无界重试或把忙错误解释为版本冲突。错误与普通日志不回显 Profile、Prompt、
secret、原始数据库异常或 SQL 参数。连接中断时由 SQLite 回滚未提交事务；错误
不会被伪装成幂等成功。该协议仅覆盖 SQLite 内的配置事实，不承担跨文件 artifact
发布、任务 lease、备份或 NAS 恢复。

## 当前就绪范围

CLI 显示槽的 `configured`/`unconfigured`/`placeholder`、阶段的 `ready`/
`not_ready` 及受控缺项原因。主题集合单独显示 `configured`/`unconfigured`。

| 阶段 | 必需材料 | 缺项原因（缺失 / 占位） |
| --- | --- | --- |
| boundary | Profile 六段、Screening 模型、boundary 提示词、boundary 契约；若已选择 Screening adapter，其系统 Prompt 不得占位 | `profile`、`screening_model` / `screening_model_placeholder`、`boundary_prompt` / `boundary_prompt_placeholder`、`boundary_contract`、`screening_adapter_prompt_placeholder` |
| value | Profile 六段、Screening 模型、value 提示词、value-prediction 契约、已配置主题集合；若已选择 Screening adapter，其系统 Prompt 不得占位 | `profile`、`screening_model` / `screening_model_placeholder`、`value_prompt` / `value_prompt_placeholder`、`value_contract`、`topics`、`screening_adapter_prompt_placeholder` |
| reuse | Profile 六段、reuse_assessment 模型、reuse 提示词、reuse-assessment 契约、升级文件内 excerpt selector；若已选择 reuse adapter，其系统 Prompt 不得占位 | `profile`、`reuse_model` / `reuse_model_placeholder`、`reuse_prompt` / `reuse_prompt_placeholder`、`reuse_contract`、`excerpt_selector`、`reuse_adapter_prompt_placeholder` |
| Read（当前恒未就绪） | Profile 六段、Read 模型、reading 提示词、Read 配置内 chunking 身份与权威 Read 契约（契约尚未开放）；若已选择 reading adapter，其系统 Prompt 不得占位 | `profile`、`read_model` / `read_model_placeholder`、`read_prompt` / `read_prompt_placeholder`、`read_contract`、`chunking_version`、`read_adapter_prompt_placeholder` |
| suggestion | 升级文件内建议规则身份和触发参数、decision-reasons 契约 | `suggestion_rule`、`escalation_parameters`、`decision_reasons_contract` |
| extraction | 合法完整的 extraction 材料：受控工具链、启用模型文件身份、有效策略及 normalization v1 | `extraction_config` |

adapter 占位缺项只在对应槽已选择且系统 Prompt 为占位时出现；未选择 adapter
仍按既有业务配置完整性判断，并单独显示 `adapters.<slot>: unconfigured`，不合成
默认 Pi 策略。已选择 adapter 的 YAML、资源引用、哈希或协议非法时整次命令失败，
不能伪装成普通缺项。adapter 文件错误会标出对应 `adapters.<slot>`；文件内声明版本
不匹配时指明 `settings.adapters.<slot>`，不回显内容或原始异常。

value 不依赖 boundary 提示词/契约或期刊信誉；boundary 不依赖主题选择、启用状态
或描述。全部已选材料仍需合法，非法主题或任一已选损坏契约会使整次 check/compile
失败。缺项可以保存明确未就绪的快照；占位 Profile 沿用 `profile` 缺项。
reuse 就绪不要求 PDF、正文提取、value 配置或实际模型输出；suggestion 就绪不要求
Screening 制品或模型槽。这些是配置完整性，不是实际任务 eligibility。未选择
escalation 文件时，reuse 缺 `excerpt_selector`，suggestion 同时缺 `suggestion_rule`
和 `escalation_parameters`。Read 始终因缺少权威契约为 `not_ready`；模型、提示词、
分块配置及已选择 adapter 的占位缺项仍分别列出。
不输出“校准就绪”。单快照重建、diff 与校准语义基线已实现；缺项与占位参与身份，
不会因得到投影而变为 ready。完整快照与配置投影身份均不能当作阶段输入指纹。

下表是已实现投影的权威依赖矩阵；校准基线组合 boundary、value、reuse、extraction、
suggestion 五个投影身份。每槽按实际消费者提取，不能使用整个 models/adapter 文件哈希。

| 配置材料 | 进入的阶段配置投影 | 校准基线 |
| --- | --- | --- |
| Profile 六段精确文本（不含普通 version） | boundary、value、reuse、read | 是 |
| 已启用主题 ID/name/description，按 ID 排序；停用项排除 | value | 是 |
| 期刊信誉 | 无 | 否 |
| Screening 模型 | boundary、value | 是 |
| boundary 提示词与契约 | boundary | 是 |
| value 提示词与 value-prediction 契约 | value | 是 |
| Reuse 模型、提示词、契约与摘录选择器版本 excerpt_selector_version 及有序 excerpt_priority | reuse | 是 |
| models.reading、prompt/reading、未来权威 Read 契约（当前 null）与 read/read 内 chunking | read | 否 |
| Screening/reuse 实际消费的适配器语义：输出协议、有效系统提示词、工具声明与实现、运行策略及参数 | 对应 boundary、value、reuse | 是 |
| reading 槽 adapter.semantics_id | read | 否 |
| 解析器、后端、模型制品、解析配置与 normalization | extraction | 是 |
| 复用升级触发集合、建议规则语义版本与原因契约 | suggestion | 是 |

当前开放 Profile、topics、journals、models、escalation、extraction、read、adapters、boundary/value/reuse/reading 提示词、Pi 系统 Prompt 与四份契约登记。
表中其余非空 selector 仍拒绝。value 投影只取 `enabled_topics`，不取完整集合
的原始字节哈希或声明版本；仅改停用主题描述、声明版本或 YAML 注释不会改变
value 语义，空集合与全部停用的 value 投影身份相同；未选择主题为 null，与空集合区分。
启用主题的 ID/name/description 变化进入 value 和基线，不影响 boundary。
触发集合只由 suggestion 消费；复用模型与摘录选择器只由 reuse 消费。
extraction 独立进入基线，不嵌入 reuse 或 read 配置投影。

models 保存 protocol 和模型参数，
Pi 运行策略、系统 Prompt 资源及三槽 selector 已按 [adapter 契约](adapter-config.md)
开放登记和只读语义。六阶段投影直接引用对应槽的 `AdapterSemantics.semantics_id`，
不重复实现 adapter 载荷；Pi/adapter 执行审计版本变化只影响完整快照和登记身份。
投影/比较不执行调用或工具。
共有适配器行为须按实际受影响阶段进入投影与校准基线，不能一概归入 Read；
临时进程/会话 ID、机器路径与纯传输变化不进入语义指纹。

### 投影格式与旧快照兼容

六种投影各有独立格式版本，当前均为 1；校准基线另有独立格式版本 1。
语义提取或规范化规则变化须提升对应格式；相关投影身份变化传导到基线，
read 专用格式变化不影响基线。运行快照包络仍为格式 1，旧有效快照中的未选择材料
按 null 重建，不改写原 payload 或快照 ID；未知格式或损坏记录仍拒绝。
未来保存的历史投影/基线引用必须保留其格式与匹配的重建能力或使用显式迁移，
不能把新格式身份冒充旧评价依据。完整载荷与演进规则见
[阶段配置投影与比较](config-projections.md#身份载荷与格式演进)。

## 示例与命令

[`examples/`](../../examples/) 是**工程验收用合成材料**，提供六段
Profile、三槽 models、主题、升级参数、三阶段提示词及四份 A1 冻结契约；
原 `settings.yaml` 使用占位 Profile，明确未就绪。新增 `settings-boundary.yaml` 使用
完整合成 `profile-example-v1`，演示 boundary 就绪与 value 缺项；`settings-value.yaml`
另选择合法空主题集合、value 提示词和 value-prediction 契约，演示两阶段均就绪。
`settings-reuse.yaml` 选择单独的合成 models 文件、升级参数、reuse 提示词和两份契约，
演示缺 value/PDF/extraction 时 reuse 与 suggestion 仍配置就绪。
`settings-pi.yaml` 使用新 models 版本与既有 Profile、主题、升级参数、三阶段提示词
及四份契约；三个 adapters 槽分别显式选择 `pi-v1`，登记 Pi 系统 Prompt 和固定策略。
示例演示 boundary/value/reuse/suggestion 均配置就绪；Read 与 extraction
仍未就绪。它不运行 Pi，不是生产提示词、正式校准或真实执行验收。
它们不是真实
Research Profile，不能据此开始正式校准。
`settings-read.yaml` 选择新的 `models-read-v1`、`read-v1`、Read 业务提示词与
reading adapter，演示 boundary 就绪、Read 仅缺权威契约。
它不构成真实 Read 或阶段 B 验收。先确保数据库的父目录已存在：

```bash
paper-radar db upgrade --database data/paperradar.sqlite3
paper-radar config check --settings examples/config/settings-boundary.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings-value.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings-reuse.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings-pi.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings-read.yaml --database data/paperradar.sqlite3
paper-radar config diff <before-id> <after-id> --database data/paperradar.sqlite3
```

#27 已在 CLI 开放数据库内唯一的小写十六进制短前缀，至少 8 位；完整 64 位 ID
仍可使用。公共 diff 服务继续只接受完整 ID，不接受当前 selector。CLI 先解析引用，
歧义或错误引用返回 2，详见[历史快照发现与引用](config-snapshots.md)。
比较成功返回 0，即使存在校准相关差异；相同且存在的 ID 输出无差异，未知 ID 仍拒绝。
命令帮助不读配置、不开数据库。成功返回 0；非法输入、未初始化库、版本冲突或
损坏返回 2。迁移随 wheel 打包，任意工作目录均可运行。

## 完整 A2 验收边界

#25 的完整 A2 结论固定聚合以上配置、迁移、投影与 CLI 行为测试，保留 A1 与
A2-01 的历史测试字节及四份 v1 契约。测试只用合成材料与真实临时 SQLite；
版本标签隔离、停用主题、模型/adapter 槽隔离、精确契约字节、只读方式、ISSN
冲突、受控算法、并发与中断恢复均有固定测试范围。验收另建临时库执行 base→head，
从库内 `alembic_version` 读取实际 revision，不将脚本声明的 head 当作已运行迁移。
迁移与快照格式仍为 `a201_profile_snapshot` / 1，各阶段投影、校准基线及 adapter
语义格式分别登记；未登记的迁移 head 或格式变化不能通过。

配置就绪、固定 fixture 与完整 A2 结论都不能证明正式校准或阶段 B 就绪。
该结论不验收 SQLite 之外的 artifact 发布、全量业务事实、阶段输入指纹、任务/
共享资格与可见性接口、doctor、备份恢复、真实来源及 Pi/Docling/模型执行。
证据、失败状态和父规格覆盖表见[离线验证证据](../verification/offline-evidence.md#完整-a2-独立结论)。
