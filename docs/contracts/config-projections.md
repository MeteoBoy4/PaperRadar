<a id="阶段配置投影校准基线与只读比较23"></a>

# 阶段配置投影、校准基线与只读比较

## 公共边界

公共入口均从 `paper_radar.config` 导入：

| 入口 | 输入与结果 | 副作用 |
| --- | --- | --- |
| `project_config(snapshot)` | 一个已由 check/compile/load 验证的 `RuntimeConfigSnapshot` → `ConfigSemantics` | 纯单快照重建；不依赖 YAML、CLI、数据库或模型。 |
| `compare_config_snapshots(before, after)` | 两个已验证快照 → `ConfigSnapshotDiff` | 分别调用单快照重建，再纯比较。 |
| `diff_config_snapshots(database, before_id, after_id)` | 明确数据库路径与两个完整 ID → `ConfigSnapshotDiff` | 沿用 load 的只读历史验证，不读取当前文件或 selector。 |

单快照重建和纯比较不访问外部材料，也不验证调用方自行构造或修改的快照；已验证快照
是调用前置，不以“配置 ready”为前置。数据库服务先完整加载并验证两个历史快照，再比较，
不读取当前配置。阶段输入等程序消费者直接复用单快照能力，无需调用 diff。

`ConfigSemantics.projections` 是以六值 `StageName` 为键的只读映射；
`StageConfigProjection` 为不可变对象，暴露 `stage`、`format_version`、
`payload_json` 和规范内容身份 `projection_id`。`ConfigSemantics.baseline` 为不可变
`CalibrationBaseline`，暴露 `format_version`、`payload_json` 与 `baseline_id`。
载荷含真实配置语义，只用于受控的程序消费，不写终端或日志；这些对象的 repr 不含载荷。

`RuntimeConfigSnapshot.materials` 提供以 `(MaterialKind, name, version)` 为键的只读映射，
值为不可变 `SnapshotMaterial`（公共导出）：kind/name/version/raw_sha256 与
不进入 repr 的 `config_json`。后者为编译值的规范 JSON 文本，调用方解析后的对象与
快照独立；共享 adapter 的多个声明版本不会被同名键覆盖。
`adapter_selections` 是保存的槽名到声明版本的只读映射，未选择槽不补默认值。
投影和 diff 通过这些访问器消费已验证材料，隐藏快照包络字段布局；访问器不校验
原数据库记录，历史 load 仍独立核对原字节、哈希、引用与重建身份后才返回快照。

配置槽的完整性、占位与拒绝规则见[运行配置契约](runtime-config.md#当前就绪范围)；
投影描述实际消费的配置语义，不代替这些判断。
六投影名称及遍历顺序固定为 boundary/value/reuse/extraction/read/suggestion：

| 投影 | components（缺失时明确为 null） |
| --- | --- |
| boundary | profile、screening model、boundary prompt、boundary contract、screening adapter |
| value | profile、screening model、value prompt、value-prediction contract、screening adapter、topics |
| reuse | profile、reuse_assessment model、reuse prompt、reuse-assessment contract、reuse_assessment adapter、excerpt_selector_version、excerpt_priority |
| extraction | extraction：backend、model_artifacts、backend_config、normalization_version |
| read | profile、reading model、reading prompt、显式 read contract（未选择为 null）、reading adapter、chunking_version |
| suggestion | suggestion_rule_version、reuse_escalation_research_values、decision-reasons contract |

模型阶段的分量键统一为 `profile/model/prompt/contract/adapter`；表中的槽说明从哪里
取内容，不额外把槽选择标签加入载荷。完整 models 文件三个槽分别提取，protocol 与
有效 temperature/top_p 等参数保留；完整文件版本与原始哈希不进入投影。
adapter 分量直接引用对应槽已有的 `AdapterSemantics.semantics_id`，其载荷自带独立
格式版本；不复制 adapter 序列化，也不把 Pi/adapter 执行审计版本当作语义。
分量内容与执行审计边界见[适配器语义契约](adapter-config.md#语义与消费者依赖)；
extraction 分量取[正文提取配置的公共语义](extraction-config.md#公共语义与历史)，不验证本机模型文件。

## 规范内容与缺项

普通配置声明 version、settings 选择标签、原 YAML 字节哈希、注释和字段顺序均不
进入投影或基线。Profile 只取六段登记精确文本；Prompt 取精确 UTF-8 文本，保留换行
与空白，不进行 strip 或折叠。空串与 ASCII `...` 仍是语义内容；占位变真实文本会
改变投影，就绪判定仍独立进行。已存在 Profile 的缺失段落保留 null；未选择 Profile
时整个 profile 分量为 null。材料的声明版本一致性与不可换字节登记规则见
[配置登记与回放](runtime-config.md#身份登记与回放)。

主题只取 enabled 项的 ID/name/description，按 ID 排序；空集合与全部停用都是 `[]`，
缺少 topics 选择为 null。触发研究价值按去重升序集合表示（配置编译仍拒绝重复），
`[2,3]` 与 `[3,2]` 同语义。excerpt_priority 是有序列表，保留次序；合法值与算法版本的
拒绝规则见[复用升级配置](runtime-config.md#复用升级参数与算法身份)。
解析模型按 stage 排序，文件集合按模型仓库相对路径排序；
相对文件路径是模型制品身份，机器安装路径不进入投影。

契约分量组合已登记 schema 与 manifest 的规范 JSON 内容，两份内容内嵌的
`x-paper-radar-contract`、契约标记及哈希均保留，不按普通声明标签剔除。
只读历史加载不会重新导出契约，也不要求旧保存内容追随当前权威 Schema 更新。

normalization_version、excerpt_selector_version、chunking_version、suggestion_rule_version
及 adapter policy.version 都是算法或策略语义身份，不按普通声明标签剔除。
配置编译仍拒绝未知算法版本；纯投影不另做材料校验，也不能自动检测同算法版本下
的代码语义漂移。

全部投影无论文题名、摘要、PDF、摘录、输出语言、时间、完整快照 ID、机器路径、
凭据、执行计划或产物。reuse 与 read 不嵌套 extraction；阶段输入消费者再组合
实际使用的论文事实或来源引用。四阶段配方、历史投影核对与隔离恢复消费者义务见
[阶段输入契约](stage-inputs.md)。完整快照 ID 仍只作审计，不能代替阶段投影 ID。
得到六投影或基线不会使不完整配置变为 ready。Read 契约通过已有 contract 槽进入投影，
旧快照仍保留 null、原 snapshot/projection ID；新选择只改变 Read 投影，不改变其余五
投影或校准基线。Read 配置完整不能推导执行就绪或校准通过。

## 身份载荷与格式演进

投影格式由封闭 `PROJECTION_FORMAT_VERSIONS` 表分别控制，当前六种各为 **1**。
基线独立由 `BASELINE_FORMAT_VERSION` 控制，当前为 **1**。例如缺项 boundary：

```json
{"components":{"adapter":null,"contract":null,"model":null,"profile":null,"prompt":null},"format_version":1,"kind":"stage_config_projection","stage":"boundary"}
```

其 SHA-256 固定为
`aab555b7f9a72aa0defc46e26c2acff8e2c049aa0a1963269f58939b5890edef`。
kind、stage 和格式版本共同分离身份域，各分量的 null 均显式编码。
序列化使用 [`config/identity.py`](../../src/paper_radar/config/identity.py) 的 canonical_json：UTF-8、排序键、紧凑分隔符、
非 ASCII 原样、列表次序保留、拒绝 NaN/Infinity、浮点采用 Python JSON 的浮点表示；
不依赖冻结契约文件的缩进。projection_id 为完整规范载荷 UTF-8 字节的 SHA-256。

基线载荷只组合五个投影身份：

```json
{"format_version":1,"kind":"calibration_baseline","projections":{"boundary":"<projection-id>","extraction":"<projection-id>","reuse":"<projection-id>","suggestion":"<projection-id>","value":"<projection-id>"}}
```

baseline_id 同样是该规范载荷的 SHA-256。不重新序列化第二份语义集合，不物化保存，
不维护可变“当前基线”，diff 不因缓存缺失而写库。read、chunking、reading adapter、
期刊信誉与普通声明版本不进入基线；`calibration_changed` 唯一判据是前后 baseline_id
不同，不能另维护一套类别清单去推断校准影响。

同一投影格式版本固定载荷字段、语义提取与规范化规则，同一基线格式版本固定组合规则；
规则变化不能沿用对应格式身份。
相关投影的格式身份参与基线计算，read 的独立格式身份不进入基线；adapter 的独立
格式身份经 semantics_id 传导，不复制到投影格式字段。

运行快照包络为格式 1，不含新增投影或基线持久字段。数据库服务要求库匹配随包迁移图
的唯一 head，不隐式升级；持久化及加载边界见[配置登记与回放](runtime-config.md#身份登记与回放)。
无 adapter/Read 等材料的旧有效快照按明确 null 重建，原 payload 与快照 ID 保持不变。
load 先核对原字节/哈希、引用、编译值、格式及重建身份；未知或损坏材料拒绝，
不按当前文件或新默认静默修复。

重建使用当前程序的投影与基线格式；本接口不提供旧格式选择、旧投影/基线引用的
持久化或迁移，不证明其他程序版本导出的身份就是历史评价依据。历史评价消费者的
格式记录、匹配重建或显式迁移责任见[路线图 D](../roadmap.md#module-d)；新身份不能冒充旧评价依据。

## diff 结果与 CLI

`ConfigSnapshotDiff` 暴露 before_snapshot_id/after_snapshot_id、snapshot_changed、
identity_changes、projection_changes、before_baseline/after_baseline 和
calibration_changed。身份变化的 category 为公共受控 `ConfigCategory`（StrEnum），
其 `.value` 保留既有 CLI 文本和字符串比较行为。封闭集合包含：

- `profile.profile`、`topics.topics`、`journals.journals`、`models.models`、
  `escalation.escalation`、`extraction.extraction`、`read.read`；
- `prompt.boundary/value/reuse/reading` 四个类别；
- `contract_schema` 与 `contract_manifest` 各自的 boundary/value-prediction/
  reuse-assessment/decision-reasons/read 五个类别；
- `adapters.screening/reuse_assessment/reading` 三个按槽类别。

比较不生成自由类别。身份变化另含前后 `ConfigIdentity` 元组，每个
身份有 kind/name/version/raw_sha256；adapter 按选定槽报告，连同它的系统 Prompt
资源，因而交换两个已登记 adapter 选择时即使材料集合相同也可见。

身份变化按 category 升序排列。投影变化为固定阶段顺序的 `StageProjectionChange`，
含 stage、前后投影与按分量名升序排列的 `ComponentChange` 元组。
`ComponentChange` 只暴露名字与 before_configured/after_configured 布尔（分量是否非 null），
不携带正文；它不是阶段 ready，也不评估 Profile 内容真实性。
前后投影对象仍显式提供 payload_json，程序调用方须按敏感配置处理。

```bash
paper-radar config diff <before-id> <after-id> --database data/paperradar.sqlite3
```

公共 diff 服务只接受两个完整 64 位小写十六进制 ID，必填数据库路径。
CLI 接受完整 ID 或指定数据库内唯一的 8–63 位小写十六进制前缀；两个引用均解析为
完整 ID 后才调用公共 diff 服务。JSON 输出未开放。
发现列表、排序、引用拒绝及只读保证见[历史快照发现与引用](config-snapshots.md)。
ID 格式校验属于加载服务，不耦合进单快照或纯比较领域能力。
相同 ID 也完成存在性与完整性验证；两者相同且有效输出“无差异”并返回 0。
存在差异或涉及校准也返回 0。服务的加载与引用错误为脱敏 `ConfigError`；CLI 的参数
解析错误与服务错误均返回 2，包括引用错误/不存在/歧义、缺少参数、缺库、未初始化、
已知旧 revision、未知或较新 revision、
未知快照格式、材料或引用损坏、加载失败；相应指引要求补充引用、显式 `db upgrade`
或使用匹配程序/检查数据库，不自动纠错或修复。
缺库不创建，重复比较输出一致，只读打开数据库，不写登记、缓存、分级、启用或激活事实。

中文人读输出包含类别、版本/哈希、受影响投影、分量“未配置 → 已配置”等转移和前后
基线身份；不显示完整 Profile/Prompt、原文 diff、输入错误值、原始异常或 SQL 参数。
只有前后分量均非 null 时追加“（语义变化）”；配置与未配置之间的变化仅显示受控转移。
所有 help 在外部 I/O 被拒绝时仍可运行，不读配置或数据库，不创建业务文件。

## 不提供／不证明

- 不提供单快照 CLI；程序入口是 `project_config`。
- 保存快照不是启用；得到投影、基线或 `calibration_changed` 不证明模型执行就绪、
  真实样本质量、fixture gate、校准通过或自动精读资格。
- 本边界不提供完整校准变更审计、minor/major 分级、门禁或自动运行。
  校准审计、分级与门禁由[路线图 D](../roadmap.md#module-d)承接，
  自动运行由[路线图 I](../roadmap.md#module-i)承接。

## 相关

依据：[#23](https://github.com/MeteoBoy4/PaperRadar/issues/23)、[#25](https://github.com/MeteoBoy4/PaperRadar/issues/25)、[#27](https://github.com/MeteoBoy4/PaperRadar/issues/27)、[#97](https://github.com/MeteoBoy4/PaperRadar/issues/97)。

实现：[`projections.py`](../../src/paper_radar/config/projections.py)、
[`diff.py`](../../src/paper_radar/config/diff.py)、[`service.py`](../../src/paper_radar/config/service.py)、
[`cli.py`](../../src/paper_radar/config/cli.py)。
历史工程结论与证明范围见[离线验证证据](../verification/offline-evidence.md#完整-a2-独立结论)，不代替当前验证或 live 验收。

[规格 §3.4](../../intent/draft.md#34-阶段输入指纹)；
[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)；
[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)；
[路线图承接](../roadmap.md#module-d)。
