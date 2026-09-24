# A2-01 运行配置快照契约

本票只开放六段式 Research Profile。配置完整性不是正式校准资格，也不启用模型或自动精读。
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
| `topics`, `journals`, `escalation`, `extraction` | 仅 `null` | 非空选择在后续票开放。 |
| `models.screening`, `models.reuse_assessment`, `models.reading` | 仅 `null` | 模型槽目前不读取模型文件。未来模型文件须具名包含三个槽；本票不接受内联模型。 |
| `prompts.boundary`, `prompts.value`, `prompts.reuse`, `prompts.reading` | 仅 `null` | 后续票开放。 |
| `contracts.boundary`, `contracts.value_prediction`, `contracts.reuse_assessment`, `contracts.decision_reasons` | 仅 `null` | 后续票开放。 |

当前封闭逻辑名称只有版本登记键 `profile/profile`。快照包络中的材料条目含
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

严格 YAML 只接受单文档、UTF-8、普通标量/列表/映射。重复键、锚点/别名、合并键、
自定义 tag、非有限浮点数和未知字段均拒绝。只有小写 `true`/`false`、`null`/`~`
会隐式转型；`yes`/`on` 是普通文本，日期也保留为文本。字段类型严格校验。
终端错误只给字段路径与受控原因，不回显输入值、原始异常或 Profile 正文。

## 身份、登记与回放

`config_versions` 以 `(kind, name, declared_version)` 为不可变键，保存精确 UTF-8
原始字节及 SHA-256。相同键、相同字节幂等；即使只改注释或空白，同键不同字节
也拒绝，必须声明新版本。校验、哈希和登记使用同一份内存材料。

快照身份是以下包络的规范 JSON 字节的 SHA-256：

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

CLI 只显示槽的 `configured`/`unconfigured`/`placeholder`、阶段的 `ready`/
`not_ready` 及受控缺项原因。当前模型、提示词、契约、提取与建议规则尚未开放，
因此所有阶段均为 `not_ready`。不输出“校准就绪”。阶段配置投影、diff、模型
材料、提示词和校准语义基线由后续 A2 票实现；不能把本票完整快照身份当作阶段
输入指纹。

下表是后续票实现投影时的**依赖契约**，不是本票已经生成的投影。空格表示该材料
不进入相应投影；校准基线只引用能够改变 Screening、复用升级、摘录或建议的配置。

| 配置材料 | 计划进入的阶段配置投影 | 校准基线 |
| --- | --- | --- |
| Profile | boundary、value、reuse、Read | 是 |
| 已启用主题 | value | 是 |
| 期刊信誉 | 无 | 否 |
| Screening 模型与 boundary/value 提示词、契约 | 各自的 boundary/value | 是 |
| Reuse 模型、提示词、契约与 excerpt selector | reuse | 是 |
| Read 模型、提示词、契约与 chunking | Read | 否 |
| 解析器、后端、模型制品、解析配置与 normalization | extraction | 是 |
| 复用升级触发参数、建议规则与原因契约 | 建议规则 | 是 |

当前只开放 Profile 材料登记；表中其余非空 selector 仍拒绝。未来模型文件的占位
词表固定为 `REQUIRED`、`REQUIRED_FOR_FORMAL_CALIBRATION`、`REQUIRED_FOR_READ`；
这些词只能表示 `placeholder`，不能充当可运行模型身份。本票没有模型文件加载。

## 示例与命令

[`examples/config/`](../../examples/config/) 是**工程验收用合成材料**，不是真实
Research Profile，不能据此开始正式校准。先确保数据库的父目录已存在：

```bash
paper-radar db upgrade --database data/paperradar.sqlite3
paper-radar config check --settings examples/config/settings.yaml --database data/paperradar.sqlite3
paper-radar config compile --settings examples/config/settings.yaml --database data/paperradar.sqlite3
```

命令帮助不读配置、不开数据库。成功返回 0；非法输入、未初始化库、版本冲突或
损坏返回 2。迁移随 wheel 打包，任意工作目录均可运行。
