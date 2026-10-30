<a id="运行配置快照契约已交付配置切片"></a>

# 运行配置快照契约

## 用途与范围

本契约定义六段式 Research Profile、主题集合、期刊信誉集合、三槽 models 文件、boundary/value/reuse/reading 提示词、Read 分块身份、五份冻结契约、复用升级参数、正文提取配置，以及三槽 Pi adapter 材料和登记系统 Prompt 的选择、编译、版本登记与历史回放。配置就绪仅说明这些本地材料齐全且合法，不证明模型调用、正式校准或自动精读可用。
公共 Python 入口是 `paper_radar.config.check_config(settings_path, database)`、
`compile_config(settings_path, database)`、`load_config_snapshot(database, snapshot_id)` 和
`upgrade_database(path)`。路径参数均为 `pathlib.Path`；前三个返回
`RuntimeConfigSnapshot`，upgrade 返回升级后的 revision 字符串；错误为脱敏的
`ConfigError`。`check` 和 `load` 只读；`compile` 只写已迁移的既有库；只有 `upgrade`
可创建库。不存在、未初始化或 revision 不匹配的库均拒绝配置操作。
另提供纯单快照 `project_config(snapshot)`、纯比较 `compare_config_snapshots(before, after)`
与只读服务 `diff_config_snapshots(database, before_id, after_id)`；类型、载荷及格式演进见
[阶段配置投影与比较](config-projections.md)。
另提供只读 `list_config_snapshots(database)` 与
`resolve_config_snapshot_reference(database, reference)`；返回类型、排序、前缀规则和
完整操作示例见 [历史快照发现与引用](config-snapshots.md)。数据库选择档案库，
快照引用选择其中的历史配置；列表不表示完整性已验证或配置已启用。

<a id="输入与路径"></a>

## 输入与路径

`settings.yaml` 是可变的纯 selector，不登记为版本，也不在里面填写 Profile 正文、
provider/model、secret 或凭据引用。check/compile 必须显式传 `--settings` 和
`--database`；diff CLI 只需两个快照引用（完整 ID 或唯一短前缀）和必填 `--database`。
公共 load/diff 服务仍只接受完整 ID；`config snapshots list --database ...` 只读发现记录。
传入的 settings 所在目录视为 `config/`，其父目录为配置根；材料路径相对该布局解析，
不额外从当前工作目录查找。相对的 settings/database 参数本身仍相对调用工作目录。
`profile: profile-v1` 精确选择 `config/profiles/profile-v1.yaml`。声明版本只允许小写
字母开头，后续为小写字母、数字、点、下划线或连字符，长度至多 64。不能用路径
穿越版本目录。当前不支持自定义文件路径。

`settings.yaml` 接受以下固定字段，全部可省略。`prompts`、`contracts`、`adapters`
是嵌套映射，省略时为空选择，但整个映射不能为 `null`；其各槽可以为 `null`。
未知字段即使为 `null` 也拒绝：

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
| `contracts.read` | `v1` 或 `null` | 检查并登记 `contracts/read/read/v1/{schema,manifest}.json`；未选择时不自动启用磁盘材料。 |

当前封闭逻辑名称为 `profile/profile`、`topics/topics`、`journals/journals`、`models/models`、`escalation/escalation`、`extraction/extraction`、`read/read`、`adapter/pi-rpc`、`prompt/pi-system`、`prompt/boundary`、`prompt/value`、`prompt/reuse`、`prompt/reading`，以及 `contract_schema`/`contract_manifest` 下的 `boundary`、`value-prediction`、`reuse-assessment`、`decision-reasons` 与 `read`。快照包络中的材料条目含
`kind`、`name`、`version`、`raw_sha256` 和编译值；所有材料使用同一格式 1 包络。
所有 YAML 版本材料的内部 `version` 均须与对应 selector 完全相同。
字段、类型或选择非法时 CLI 返回 2，并给出脱敏字段路径与受控原因，不忽略选择。
`prompt/pi-system` 的版本引用来自 adapter 资源清单，
位置在 `config/prompts/`，与业务 Prompt 分开登记。

Profile 文件的 `version` 必须与 selector 完全相同。六段字段为 `background`、
`core_questions`、`transferable_methods`、`available_data_and_tools`、
`theory_and_cognitive_interests`、`constraints_and_exclusions`。每段为文本或缺失。
缺失或 `null` 是 `unconfigured`；去掉首尾空白后为空或**精确等于 ASCII `...`**
是 `placeholder`；其余文本为 `configured`，包括 `…`、`......`、日期文字。
配置边界仅判断填写状态，不判断资料真实性。只有六段都配置时 Profile 槽为
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
当前配置文件，损坏不回退。
期刊配置只进入完整快照，不进入六个阶段的就绪必需项、阶段语义对象或校准基线；
配置边界不执行论文匹配、评分、排序或来源抓取。期刊变化只影响完整快照与登记身份，
六阶段投影和校准基线保持不变。
合成示例为 `examples/config/settings-journals.yaml`，不能作为正式校准资料。

## 模型、提示词与契约

models 文件必须有 `version` 和 `screening`、`reuse_assessment`、`reading` 三个具名槽；每槽写 `null` 或严格对象。对象允许 `provider`、`model`、`protocol`、`temperature`、`top_p`，未知字段均拒绝。`provider`、`model`、`protocol` 均可省略或为 `null`，默认 `null`；前两项为文本，`protocol` 为 `json_schema`、`json_object`、`prompt_only` 之一。`temperature` 是 0.0–2.0 的有限数字，默认 0.0；`top_p` 是大于 0 且不超过 1 的有限数字，默认 1.0。不得填写凭据、自由参数字典或 fallback 列表。先判占位：`provider` 或 `model` 去除首尾空白后精确等于 `REQUIRED`、`REQUIRED_FOR_FORMAL_CALIBRATION`、`REQUIRED_FOR_READ` 之一时，槽为 `placeholder`；否则三项缺失、为 `null` 或 provider/model 为空白时，槽为 `unconfigured`。其余非空文本视为已配置；此处不探测供应商能力或读取凭据。三槽可以写相同的 provider/model，但各自保留身份。

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

已选择 Pi adapter 时，对应模型槽的非空 protocol 只接受 `prompt_only`，冲突使
整次 check/compile 失败；槽或 protocol 未配置仍可保存未就绪快照，详见
[适配器协议约束](adapter-config.md#字段默认值与固定策略)。
上例与 `examples/config/models/models-pi-v1.yaml` 一致，仅为配置完整性示例。
配置编译器保留 `json_schema`、`json_object` 和 `prompt_only` 的既有受控枚举，
以回放历史材料；它不调用 Pi、不探测 provider 能力，也不执行协议切换。
已有 `models-v1` / `models-reuse-v1` 不改写，改选目标协议应创建新的 models 版本。
配置 `ready` 不证明参数支持、运行资源或隔离；执行边界见 [Pi RPC](pi-rpc.md)，
生产准入承接见[路线图 Pi](../roadmap.md#module-pi)与[Live](../roadmap.md#module-live)。
配置不提供专用提交工具协议或自动协议切换；后续责任见[路线图 Pi](../roadmap.md#module-pi)。

提示词的逻辑名为 `boundary`、`value`、`reuse` 或 `reading`，声明版本来自对应 `settings.prompts.*`，Prompt 本身无需内嵌版本。文件去除首尾空白后为空或精确等于 ASCII `...` 时为占位。两个声明版本可登记完全相同的 Prompt 原始字节；同一版本任何字节变化都拒绝。Profile 的文件内版本与 selector 一致性仍是强制要求。
`prompt/reading` 是 Read 业务提示词，与 `prompt/pi-system` 的登记声明系统指令使用不同登记键；
声明文本不含 Pi 追加的 cwd 段，见[适配器语义边界](adapter-config.md#语义与消费者依赖)。
四个业务逻辑名由 `paper_radar.config.schema.PromptName` 声明，
独立于阶段名（Read 阶段为 `read`，业务 Prompt 为 `reading`）。

所选 boundary、value-prediction、reuse-assessment、decision-reasons 与 read 契约只支持
权威 `v1`。check/compile 调用[冻结契约只读检查](frozen-contracts.md)，并将同一份通过
检查的 schema 与 manifest 字节分别登记；哈希和编译值一起进入快照。缺失、损坏、
版本错误或内容漂移使整次命令失败，错误显示受控类别与中文处理指引，不修复或导出。
历史 load 从数据库核对已登记字节与快照身份，即使原冻结目录被移动或损坏仍可读取。

严格 YAML 只接受单文档、UTF-8、普通标量/列表/映射。重复键、锚点/别名、合并键、
自定义 tag、非有限浮点数和未知字段均拒绝。数字按受控整数或浮点写法解析；布尔与空值仅
小写 `true`/`false`、`null`/`~` 隐式转型；`yes`/`on`、`True` 与日期保留为文本。
字段类型严格校验。
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
默认值为 `[3]`，与显式选择 `[3]` 的编译参数语义相同。

触发字段表达研究价值的**集合成员关系**，不能解释成 `>=3` 阈值；默认集合
只有 `{3}`。唯一输入字段为 `reuse_escalation_research_values`；
`research_value_triggers` 与 `reuse_escalation_research_value` 均为未知字段，拒绝输入。
参数版本文件的全部字节照常登记，
同一已登记版本即使只改注释也拒绝。集合编译为排序列表；公共快照的 `escalation`
是 `EscalationSemantics | None`，提供不可变、升序的 `reuse_escalation_research_values`
元组、固定的 `excerpt_priority` 元组和两个受控算法版本，不包含声明标签或原始哈希。
未选择文件时为 `None`。新版本的 `[2, 3]` 和 `[3, 2]` 原材料及完整身份不同，但
上述集合语义相同；suggestion 投影按升序集合语义生成，校准基线保持相同身份。

`excerpt_priority` 保持 availability 优先于 methods，不接受反转配置；
固定顺序与算法身份进入 reuse 投影及校准基线。

两个算法版本只是代码受控的受支持身份，不登记独立内容文件，不构造假字节或
原始哈希。它们不能作为无意义声明标签从语义输入剔除。参数文件保留它们的真实
选择。**配置编译无法自动检测同算法版本下的代码语义变化**；这项限制由评审与版本
冻结纪律约束。本配置边界不执行摘录选择或筛选建议规则；消费者见
[阶段输入](stage-inputs.md)与[筛选结果校验](screening-validation.md)。

<a id="read-配置与分块身份"></a>

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
必须保留。算法自身没有内容文件或独立字节登记；配置编译无法检测同算法版本下的
代码语义变化，依赖评审与版本冻结纪律。

模型仍使用共同 models 文件中的独立 `reading` 槽，遵循上文模型字段、默认值、
占位词和参数范围；Read 提示词与 chunking 均不要求 Screening/reuse 材料。
合法 Read 变更可保存新快照，boundary 配置完整性不变。历史加载从 SQLite
登记内容重建，即使源文件被删除或当前 selector 已切换，仍保留旧模型和提示词。
没有 Read 材料的历史快照保持原包络格式和身份。

`contracts.read` 显式选择已有权威 Read v1，`contracts.reading` 仍为未知字段。
check/compile 使用当前权威只读 check 检查 Schema/manifest 配对及精确字节；
测试 Schema 或手写替代物不能让 Read 就绪。未选择或 null 时保留缺项 `read_contract`，
即使磁盘已有契约也不读取或自动启用。材料齐全时可报告配置 `ready`；其余缺项见下表。
历史 load 只核对登记原始字节、哈希、selector、引用闭包及重建身份，不重新生成当前
Pydantic Schema 比较；新权威模型不能替换历史材料，历史损坏也不回退到当前文件。
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
本机配置文件路径、时间、数据库行号、凭据或论文输入；模型文件的仓库相对路径
仍是材料身份的一部分，见[正文提取配置](extraction-config.md#按启用阶段冻结模型文件)。
此序列化独立于冻结契约排版。
`selectors` 始终含 `profile`（未选为 `null`）；其他未选顶层材料省略，嵌套组仅保存
非空选择，整组无选择时省略。缺失值在材料编译对象中仍按其字段规则保留。

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

<a id="当前就绪范围"></a>

## 当前就绪范围

CLI 显示槽的 `configured`/`unconfigured`/`placeholder`、阶段的 `ready`/
`not_ready` 及受控缺项原因。主题集合单独显示 `configured`/`unconfigured`。

| 阶段 | 必需材料 | 缺项原因（按输出顺序；缺失 / 占位） |
| --- | --- | --- |
| boundary | Profile 六段、Screening 模型、boundary 提示词、boundary 契约；若已选择 Screening adapter，其系统 Prompt 不得占位 | `profile`、`screening_model` / `screening_model_placeholder`、`screening_adapter_prompt_placeholder`、`boundary_prompt` / `boundary_prompt_placeholder`、`boundary_contract` |
| value | Profile 六段、Screening 模型、value 提示词、value-prediction 契约、已配置主题集合；若已选择 Screening adapter，其系统 Prompt 不得占位 | `profile`、`screening_model` / `screening_model_placeholder`、`screening_adapter_prompt_placeholder`、`value_prompt` / `value_prompt_placeholder`、`value_contract`、`topics` |
| reuse | Profile 六段、reuse_assessment 模型、reuse 提示词、reuse-assessment 契约、升级文件内 excerpt selector；若已选择 reuse adapter，其系统 Prompt 不得占位 | `profile`、`reuse_adapter_prompt_placeholder`、`reuse_model` / `reuse_model_placeholder`、`reuse_prompt` / `reuse_prompt_placeholder`、`reuse_contract`、`excerpt_selector` |
| read | Profile 六段、Read 模型、reading 提示词、Read 配置内 chunking 身份与显式选择的权威 read/v1；若已选择 reading adapter，其系统 Prompt 不得占位 | `profile`、`read_adapter_prompt_placeholder`、`read_model` / `read_model_placeholder`、`read_prompt` / `read_prompt_placeholder`、`read_contract`、`chunking_version` |
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
和 `escalation_parameters`。Read 逐槽判断配置完整性；模型、提示词、
分块、契约及已选择 adapter 的占位缺项分别列出。
不输出“校准就绪”。单快照重建、diff 与校准语义基线已实现；缺项与占位参与身份，
不会因得到投影而变为 ready。完整快照与配置投影身份均不能当作阶段输入指纹。

阶段投影的完整材料依赖、校准基线组合与比较规则由
[阶段配置投影与比较](config-projections.md#公共边界)定义；Pi 材料的分量身份由
[适配器配置](adapter-config.md#语义与消费者依赖)定义。完整快照保留全部选择与登记
身份，投影仅提取实际消费者语义；二者都不证明执行或校准资格。

<a id="投影格式与旧快照兼容"></a>

投影与基线的格式、载荷及兼容边界见
[身份载荷与格式演进](config-projections.md#身份载荷与格式演进)。
本契约的运行快照包络格式为 1，历史 load 不改写原 payload 或快照 ID。

## 示例与命令

以下 `settings-*.yaml` 均位于 [`examples/config/`](../../examples/config/)，
所选业务 Prompt 与冻结契约分别位于 `examples/prompts/`、`examples/contracts/`。
[`examples/`](../../examples/) 是**工程验收用合成材料**，提供六段
Profile、三槽 models、主题、期刊、升级参数、正文提取和 Read 配置、四种业务提示词、
Pi adapter 与系统 Prompt、五份冻结契约；
`settings.yaml` 使用占位 Profile，明确未就绪。`settings-boundary.yaml` 使用
完整合成 `profile-example-v1`，演示 boundary 就绪与 value 缺项；`settings-value.yaml`
另选择合法空主题集合、value 提示词和 value-prediction 契约，演示两阶段均就绪。
`settings-reuse.yaml` 选择单独的合成 models 文件、升级参数、reuse 提示词和两份契约，
演示缺 value/PDF/extraction 时 reuse 与 suggestion 仍配置就绪。
`settings-pi.yaml` 选择 `models-pi-v1`、Profile、主题、升级参数、三阶段提示词
及四份 Screening 契约；三个 adapters 槽分别显式选择 `pi-v1`，登记 Pi 系统 Prompt 和固定策略。
示例演示 boundary/value/reuse/suggestion 均配置就绪；Read 与 extraction
仍未就绪。它不运行 Pi，不是生产提示词、正式校准或真实执行验收。
这些示例不是真实 Research Profile，不能据此开始正式校准。
`settings-read.yaml` 选择 `models-read-v1`、`read-v1`、Read 业务提示词与
reading adapter，演示 boundary 就绪、Read 因未选择契约而缺 `read_contract`。
`settings-read-ready.yaml` 显式选择 `contracts.read: v1`，演示 Read 配置完整。
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

CLI 接受数据库内唯一的小写十六进制短前缀，至少 8 位；完整 64 位 ID
仍可使用。公共 diff 服务继续只接受完整 ID，不接受当前 selector。CLI 先解析引用，
歧义或错误引用返回 2，详见[历史快照发现与引用](config-snapshots.md)。
比较成功返回 0，即使存在校准相关差异；相同且存在的 ID 输出无差异，未知 ID 仍拒绝。
命令帮助不读配置、不开数据库。成功返回 0；非法输入、未初始化库、版本冲突或
损坏返回 2。迁移随 wheel 打包，任意工作目录均可运行。

## 错误与拒绝

配置服务以脱敏 `ConfigError` 报告失败；CLI 将业务错误写到 stderr，退出 2。
`check`/`compile` 成功输出完整快照 ID、Profile 总槽及六段状态、三个模型槽状态、
主题与期刊集合状态、三个 adapter 槽状态，以及六阶段的状态和有序缺项原因；
不打印配置正文。成功退出 0，即使快照 `not_ready`。`compile` 不启用快照或任务。

| 类别 | 拒绝与恢复 |
| --- | --- |
| 文件或字段无效 | 路径不可读、非 UTF-8、YAML 语法/tag、严格类型、未知字段或声明版本不匹配均拒绝；按字段路径检查所选材料。 |
| 冻结契约无效 | 返回所选契约及受控检查类别；从版本控制恢复对应权威字节，不自动修复。类别见[冻结契约](frozen-contracts.md)。 |
| 版本冲突、写入失败或历史损坏 | 不覆盖登记、不从当前文件补历史；事务与重跑规则见[并发、失败与恢复](#并发失败与恢复)。 |
| 快照 ID 无效或不存在 | load 只接受完整 64 位小写十六进制 ID；检查所选档案库与完整 ID。发现和 CLI 前缀解析见[历史快照发现与引用](config-snapshots.md)。 |
| 未支持的历史格式或损坏 | 拒绝加载，不按当前文件或新默认重算；使用匹配版本或核查保护副本。 |
| 数据库不满足前置 | 不存在、未初始化或已知旧 revision 须显式 `db upgrade --database`；未知或较新 revision 须使用匹配程序检查，不自动升级。revision 分类与升级原子性见[制品存储](artifact-store.md#revision-与原因码)。 |

## 不提供／不证明

本边界不调用网络或模型、不读取凭据、不安装 Pi/Node/Docling、不执行 PDF 解析、
Read 分块或业务任务，不消耗自动配额；不提供校准分级、门禁启用或流水线执行授权。
配置完整性和历史快照完整性不证明真实输入、fixture、供应商参数、模型质量、正式校准、
自动精读或生产执行就绪。Pi 生产准入与现场验证由[Pi](../roadmap.md#module-pi)、
[Cwd](../roadmap.md#module-cwd)、[Live](../roadmap.md#module-live)承接；正文生产与
最小 Read 由[Body](../roadmap.md#module-body)、[B](../roadmap.md#module-b)承接，
正式校准由[D](../roadmap.md#module-d)承接。备份恢复规则见[备份恢复](backup-restore.md)，
NAS 与最终恢复验收由[I](../roadmap.md#module-i)承接。

<a id="完整-a2-验收边界"></a>

既有 A2 验收叙述与其时点限制见[历史验收边界](../verification/contracts-runtime-config-history.md#完整-a2-验收边界)，
不作为当前或 live 就绪结论。

## 相关

依据：[#19](https://github.com/MeteoBoy4/PaperRadar/issues/19)、[#25](https://github.com/MeteoBoy4/PaperRadar/issues/25)、[#27](https://github.com/MeteoBoy4/PaperRadar/issues/27)、[规格 §7](../../intent/draft.md#七配置与-agent-契约)、[ADR-0022](../adr/0022-conditionally-upgrade-reuse-feasibility-from-fulltext-excerpts.md)、[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)、[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)。

组件契约：[阶段配置投影与比较](config-projections.md)、[历史快照发现与引用](config-snapshots.md)、
[Pi adapter 配置](adapter-config.md)、[正文提取配置](extraction-config.md)、[冻结契约](frozen-contracts.md)。
实现：[`config/`](../../src/paper_radar/config/)、[`storage/repository.py`](../../src/paper_radar/storage/repository.py)、
[`storage/database.py`](../../src/paper_radar/storage/database.py)。
