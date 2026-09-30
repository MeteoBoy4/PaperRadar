# A2-03 运行配置快照契约

当前开放六段式 Research Profile、主题集合、三槽 models 文件、boundary/value 提示词及 A1 boundary/value-prediction 冻结契约。配置就绪仅说明这些本地材料齐全且合法，不证明模型调用、正式校准或自动精读可用。
公共 Python 入口是 `paper_radar.config.check_config(settings_path, database)`、
`compile_config(settings_path, database)`、`load_config_snapshot(database, snapshot_id)` 和
`upgrade_database(database)`。前三个返回 `RuntimeConfigSnapshot`；错误为脱敏的
`ConfigError`。`check` 和 `load` 只读；`compile` 只写已迁移的既有库；只有 `upgrade`
可创建库。不存在、未初始化或 revision 不匹配的库均拒绝配置操作。

## 输入与路径

`settings.yaml` 是可变的纯 selector，不登记为版本，也不在里面填写 Profile 正文、
provider/model、secret 或凭据引用。CLI 必须显式传 `--settings` 和 `--database`。
传入的 settings 所在目录视为 `config/`，其父目录为配置根；路径不依赖当前工作目录。
`profile: profile-v1` 精确选择 `config/profiles/profile-v1.yaml`。声明版本只允许小写
字母开头，后续为小写字母、数字、点、下划线或连字符，长度至多 64。不能用路径
穿越版本目录。当前不支持自定义文件路径。

`settings.yaml` 接受以下固定字段，全部可省略：

| 字段 | 当前值 | 说明 |
| --- | --- | --- |
| `profile` | 声明版本或 `null` | 缺失或 `null` 都表示 `unconfigured`，允许保存未就绪快照。 |
| `topics` | 声明版本或 `null` | 选择 `config/topics/<version>.yaml`；未选择为缺项，空集合与全部停用均合法且已配置。 |
| `journals`, `escalation`, `extraction` | 仅 `null` | 非空选择在后续票开放。 |
| `models` | 声明版本或 `null` | 整份 `config/models/<version>.yaml`；三个模型槽在文件内具名，settings 不内联 provider/model。 |
| `prompts.boundary` | 声明版本或 `null` | 绑定 `prompts/screening/boundary-<version>.md` 的原始 UTF-8 字节。 |
| `contracts.boundary` | `v1` 或 `null` | 从 `contracts/screening/boundary/v1/{schema,manifest}.json` 检查并登记两份原始字节。 |
| `prompts.value` | 声明版本或 `null` | 绑定 `prompts/screening/value-<version>.md` 的原始 UTF-8 字节。 |
| `contracts.value_prediction` | `v1` 或 `null` | 检查并登记 `contracts/screening/value-prediction/v1/{schema,manifest}.json`。 |
| `prompts.reuse`, `prompts.reading`, `contracts.reuse_assessment`, `contracts.decision_reasons` | 仅 `null` | 后续票开放。 |

当前封闭逻辑名称为 `profile/profile`、`topics/topics`、`models/models`、`prompt/boundary`、`prompt/value`，以及 `contract_schema`/`contract_manifest` 下的 `boundary` 与 `value-prediction`。快照包络中的材料条目含
`kind`、`name`、`version`、`raw_sha256` 和编译值；后续新增材料种类只增加带
种类和版本键的条目，不提升编译格式版本。只有包络结构改变时才提升格式版本。
选择了尚未开放的非空字段会返回 2，并给出字段路径；不会忽略选择。

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

读取所选材料和历史回放共用纯配置层的 frozen `SelectedMaterials` 具名对象，
交给 `compile_snapshot(materials)` 编译；对象不包含路径、连接或执行计划。
Profile/models/topics 的活跃 YAML 装载共享声明版本一致性检查，
版本格式由公开 `valid_declared_version` 统一校验。公共 check/compile/load
服务参数、持久包络格式与身份序列化保持一致，无需 migration。

## 模型、提示词与契约

models 文件必须有 `version` 和 `screening`、`reuse_assessment`、`reading` 三个具名槽；每槽写 `null` 或严格对象。对象允许 `provider`、`model`、`protocol`、`temperature`、`top_p`，未知字段均拒绝。`provider` 与 `model` 是文本，`protocol` 为 `json_schema`、`json_object`、`prompt_only` 之一。`temperature` 是 0.0–2.0 的有限数字，默认 0.0；`top_p` 是大于 0 且不超过 1 的有限数字，默认 1.0。不得填写凭据、自由参数字典或 fallback 列表。先判占位：`provider` 或 `model` 去除首尾空白后精确等于 `REQUIRED`、`REQUIRED_FOR_FORMAL_CALIBRATION`、`REQUIRED_FOR_READ` 之一时，槽为 `placeholder`；否则三项缺失、为 `null` 或 provider/model 为空白时，槽为 `unconfigured`。其余非空文本视为已配置；此处不探测供应商能力或读取凭据。三槽可以写相同的 provider/model，但各自保留身份。

```yaml
version: models-v1
screening:
  provider: example-provider
  model: example-model
  protocol: json_schema
  temperature: 0.0
  top_p: 1.0
reuse_assessment: null
reading: null
```

提示词的逻辑名为 `boundary` 或 `value`，声明版本来自对应 `settings.prompts.*`，Prompt 本身无需内嵌版本。文件去除首尾空白后为空或精确等于 ASCII `...` 时为占位。两个声明版本可登记完全相同的 Prompt 原始字节；同一版本任何字节变化都拒绝。Profile 的文件内版本与 selector 一致性仍是强制要求。

活跃 boundary 与 value-prediction 契约只支持 A1 权威 `v1`。check/compile 调用其公开只读检查，并将同一份通过检查的 schema 与 manifest 字节分别登记；它们的哈希和编译值一起进入快照。缺失、损坏、版本错误或内容漂移使整次命令失败，错误显示受控类别与中文处理指引，不会修复或导出。历史 load 从数据库核对已登记字节与快照身份，即使原冻结目录后来被移动或损坏，历史仍可读取。

严格 YAML 只接受单文档、UTF-8、普通标量/列表/映射。重复键、锚点/别名、合并键、
自定义 tag、非有限浮点数和未知字段均拒绝。只有小写 `true`/`false`、`null`/`~`
会隐式转型；`yes`/`on` 是普通文本，日期也保留为文本。字段类型严格校验。
终端错误只给字段路径与受控原因，不回显输入值、原始异常或 Profile 正文。

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

## 当前就绪范围

CLI 显示槽的 `configured`/`unconfigured`/`placeholder`、阶段的 `ready`/
`not_ready` 及受控缺项原因。主题集合单独显示 `configured`/`unconfigured`。

| 阶段 | 必需材料 | 缺项原因（缺失 / 占位） |
| --- | --- | --- |
| boundary | Profile 六段、Screening 模型、boundary 提示词、boundary 契约 | `profile`、`screening_model` / `screening_model_placeholder`、`boundary_prompt` / `boundary_prompt_placeholder`、`boundary_contract` |
| value | Profile 六段、Screening 模型、value 提示词、value-prediction 契约、已配置主题集合 | `profile`、`screening_model` / `screening_model_placeholder`、`value_prompt` / `value_prompt_placeholder`、`value_contract`、`topics` |

value 不依赖 boundary 提示词/契约或期刊信誉；boundary 不依赖主题选择、启用状态
或描述。全部已选材料仍需合法，非法主题或任一已选损坏契约会使整次 check/compile
失败。缺项可以保存明确未就绪的快照；占位 Profile 沿用 `profile` 缺项。
即使 reuse 或 Read 模型槽已配置，这两个阶段仍因其余材料未开放而为 `not_ready`。
不输出“校准就绪”。阶段配置投影、diff 和校准语义基线由 A2-08 实现；不能把本票
完整快照身份当作阶段输入指纹。

下表是后续票实现投影时的**依赖契约**，不是本票已经生成的投影。空格表示该材料
不进入相应投影；校准基线只引用能够改变 Screening、复用升级、摘录或建议的配置。

| 配置材料 | 计划进入的阶段配置投影 | 校准基线 |
| --- | --- | --- |
| Profile | boundary、value、reuse、Read | 是 |
| 已启用主题 | value | 是 |
| 期刊信誉 | 无 | 否 |
| Screening 模型 | boundary、value | 是 |
| boundary 提示词与契约 | boundary | 是 |
| value 提示词与 value-prediction 契约 | value | 是 |
| Reuse 模型、提示词、契约与 excerpt selector | reuse | 是 |
| Read 模型、提示词、契约与 chunking | Read | 否 |
| 解析器、后端、模型制品、解析配置与 normalization | extraction | 是 |
| 复用升级触发参数、建议规则与原因契约 | 建议规则 | 是 |

当前开放 Profile、topics、models、boundary/value 提示词与对应契约登记。
表中其余非空 selector 仍拒绝。后续 value 投影只取 `enabled_topics`，不取完整集合
的原始字节哈希或声明版本；仅改停用主题描述、声明版本或 YAML 注释不会改变
value 语义，空集合与全部停用的 value 投影身份应相同。启用主题的 ID/name/description
变化应进入 value 语义；这些最终投影与基线身份由 A2-08 验收。
本票只保存可分别提取的语义材料，不生成阶段投影。

## 示例与命令

[`examples/`](../../examples/) 是**工程验收用合成材料**，包含四类已选材料（六段
Profile、三槽 models、boundary 提示词与 A1 boundary 冻结契约）；
原 `settings.yaml` 使用占位 Profile，明确未就绪。新增 `settings-boundary.yaml` 使用
完整合成 `profile-example-v1`，演示 boundary 就绪与 value 缺项；`settings-value.yaml`
另选择合法空主题集合、value 提示词和 value-prediction 契约，演示两阶段均就绪。
它们不是真实
Research Profile，不能据此开始正式校准。先确保数据库的父目录已存在：

```bash
paper-radar db upgrade --database data/paperradar.sqlite3
paper-radar config check --settings examples/config/settings-boundary.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings-value.yaml --database data/paperradar.sqlite3
```

命令帮助不读配置、不开数据库。成功返回 0；非法输入、未初始化库、版本冲突或
损坏返回 2。迁移随 wheel 打包，任意工作目录均可运行。
