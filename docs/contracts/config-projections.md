# 阶段配置投影、校准基线与只读比较（#23）

## 公共边界

公共入口均从 `paper_radar.config` 导入：

| 入口 | 输入与结果 | 副作用 |
| --- | --- | --- |
| `project_config(snapshot)` | 一个已由 check/compile/load 验证的 `RuntimeConfigSnapshot` → `ConfigSemantics` | 纯单快照重建；不依赖 YAML、CLI、数据库或模型。 |
| `compare_config_snapshots(before, after)` | 两个已验证快照 → `ConfigSnapshotDiff` | 分别调用单快照重建，再纯比较。 |
| `diff_config_snapshots(database, before_id, after_id)` | 明确数据库路径与两个完整 ID → `ConfigSnapshotDiff` | 沿用 load 的只读历史验证，不读取当前文件或 selector。 |

领域能力在 `config/projections.py`，纯比较在 `config/diff.py`；数据库加载由应用服务
`config/service.py` 组织，CLI 只渲染受控结果。后续校准、诊断与阶段输入指纹可以直接
复用单快照能力，无需调用 diff 或读取数据库；本票不新增单快照 CLI。

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

完整依赖矩阵以 [运行配置契约](runtime-config.md#当前就绪范围) 为权威。
六投影名称固定为 boundary/value/reuse/extraction/read/suggestion：

| 投影 | components（缺失时明确为 null） |
| --- | --- |
| boundary | profile、screening model、boundary prompt、boundary contract、screening adapter |
| value | profile、screening model、value prompt、value-prediction contract、screening adapter、topics |
| reuse | profile、reuse_assessment model、reuse prompt、reuse-assessment contract、reuse_assessment adapter、excerpt_selector_version、excerpt_priority |
| extraction | extraction：backend、model_artifacts、backend_config、normalization_version |
| read | profile、reading model、reading prompt、未来权威 read contract（当前恒 null）、reading adapter、chunking_version |
| suggestion | suggestion_rule_version、reuse_escalation_research_values、decision-reasons contract |

模型阶段的分量键统一为 `profile/model/prompt/contract/adapter`；表中的槽说明从哪里
取内容，不额外把槽选择标签加入载荷。完整 models 文件三个槽分别提取，protocol 与
有效 temperature/top_p 等参数保留；完整文件版本与原始哈希不进入投影。
adapter 分量直接引用对应槽已有的 `AdapterSemantics.semantics_id`，其载荷自带独立
格式版本；不复制 adapter 序列化，也不把 Pi/adapter 执行审计版本当作语义。

## 规范内容与缺项

普通配置声明 version、settings 选择标签、原 YAML 字节哈希、注释和字段顺序均不
进入投影或基线。Profile 只取六段登记精确文本；Prompt 取精确 UTF-8 文本，保留换行
与空白，不进行 strip 或折叠。空串与 ASCII `...` 仍是语义内容；占位变真实文本会
改变投影，就绪判定仍独立进行。已存在 Profile 的缺失段落保留 null；未选择 Profile
时整个 profile 分量为 null。Profile 新版必须同步改变内部 version 并通过一致性验证，
不能用不匹配的旧字节冒充另一声明版本。

主题只取 enabled 项的 ID/name/description，按 ID 排序；空集合与全部停用都是 `[]`，
缺少 topics 选择为 null。触发研究价值按去重升序集合表示（生产编译仍拒绝重复），
`[2,3]` 与 `[3,2]` 同语义。excerpt_priority 是有序列表，保留次序；生产 V1 仍只接受
`[availability, methods]`。解析模型按 stage 排序，文件集合按仓库相对路径排序；
相对文件路径是模型制品身份，机器安装路径不进入投影。

契约分量组合已登记 schema 与 manifest 的规范 JSON 内容，两份内容内嵌的
`x-paper-radar-contract`、契约标记及哈希均保留，不按普通声明标签剔除。
只读历史加载不会重新导出契约，也不要求旧保存内容追随当前权威 Schema 更新。

normalization_version、excerpt_selector_version、chunking_version、suggestion_rule_version
及 adapter policy.version 都是算法或策略语义身份，必须保留。未知生产算法仍拒绝；
测试中的未来版本与顺序反例只存在于纯投影 fixture，不注册假 v2 或改变 V1 就绪。
同算法版本下的代码语义漂移仍靠评审与版本冻结纪律约束，A2 无法自动检测。

全部投影无论文题名、摘要、PDF、摘录、输出语言、时间、完整快照 ID、机器路径、
凭据、执行计划或产物。reuse 与 read 不嵌套 extraction；后续论文侧输入指纹再组合
实际使用的摘录或正文。得到六投影或基线不会使不完整配置变为 ready；Read 始终
缺权威契约，不能据此推导执行就绪或校准通过。

## 身份载荷与格式演进

投影格式由封闭 `PROJECTION_FORMAT_VERSIONS` 表分别控制，当前六种各为 **1**。
基线独立由 `BASELINE_FORMAT_VERSION` 控制，当前为 **1**。例如缺项 boundary：

```json
{"components":{"adapter":null,"contract":null,"model":null,"profile":null,"prompt":null},"format_version":1,"kind":"stage_config_projection","stage":"boundary"}
```

其 SHA-256 固定为
`aab555b7f9a72aa0defc46e26c2acff8e2c049aa0a1963269f58939b5890edef`。
kind、stage 和格式版本共同分离身份域，各分量的 null 均显式编码。
序列化复用配置独立的 canonical_json：UTF-8、排序键、紧凑分隔符、非 ASCII 原样、
列表次序保留、拒绝 NaN/Infinity、浮点采用 Python JSON 的浮点表示；不依赖 A1
文件缩进或私有排版函数。projection_id 为完整规范载荷 UTF-8 字节的 SHA-256。

基线载荷只组合五个投影身份：

```json
{"format_version":1,"kind":"calibration_baseline","projections":{"boundary":"<projection-id>","extraction":"<projection-id>","reuse":"<projection-id>","suggestion":"<projection-id>","value":"<projection-id>"}}
```

baseline_id 同样是该规范载荷的 SHA-256。不重新序列化第二份语义集合，不物化保存，
不维护可变“当前基线”，diff 不因缓存缺失而写库。read、chunking、reading adapter、
期刊信誉与普通声明版本不进入基线；`calibration_changed` 唯一判据是前后 baseline_id
不同，不能另维护一套类别清单去推断校准影响。

投影载荷字段、语义提取或规范化规则改变时提升相应投影格式；基线组合规则改变时
提升基线格式。相关投影格式变化会经其身份传导到基线；read 独立格式变化不影响
基线。adapter 独立格式变化经 semantics_id 传导，无需只为此提升投影格式。
这些身份变化在后续校准工作流中按可能相关变化处理，仍由用户分级。

运行快照包络仍为格式 1；A3 的存储迁移 head 为 `a302_artifact_store`，不写入新增投影字段。
无 adapter/Read 等材料的旧有效快照按明确 null 重建，原 payload 与快照 ID 保持不变。
load 必须先核对原字节/哈希、引用、编译值、格式及重建身份；未知或损坏材料拒绝，
不按当前文件或新默认静默修复。未来程序提升投影格式后，重导出得到新格式身份，
不会修改历史快照；未来消费者若持久化旧投影/基线引用，须记录格式并保留匹配版本
的重建能力或提供显式迁移，不能把当前版本重导出的新身份冒充历史评价依据。

## diff 结果与 CLI

`ConfigSnapshotDiff` 暴露 before_snapshot_id/after_snapshot_id、snapshot_changed、
identity_changes、projection_changes、before_baseline/after_baseline 和
calibration_changed。身份变化的 category 为公共受控 `ConfigCategory`（StrEnum），
其 `.value` 保留既有 CLI 文本和字符串比较行为。封闭集合包含：

- `profile.profile`、`topics.topics`、`journals.journals`、`models.models`、
  `escalation.escalation`、`extraction.extraction`、`read.read`；
- `prompt.boundary/value/reuse/reading` 四个类别；
- `contract_schema` 与 `contract_manifest` 各自的 boundary/value-prediction/
  reuse-assessment/decision-reasons 四个类别；
- `adapters.screening/reuse_assessment/reading` 三个按槽类别。

新增材料消费者须同步扩展枚举，不生成自由类别。身份变化另含前后 `ConfigIdentity` 元组，每个
身份有 kind/name/version/raw_sha256；adapter 按选定槽报告，连同它的系统 Prompt
资源，因而交换两个已登记 adapter 选择时即使材料集合相同也可见。

投影变化为固定阶段顺序的 `StageProjectionChange`，含 stage、前后投影与
`ComponentChange` 元组。分量变化只暴露名字与 before_configured/after_configured
布尔（分量是否非 null），不携带正文；它不是阶段 ready，也不评估 Profile 内容真实性。

```bash
paper-radar config diff <before-id> <after-id> --database data/paperradar.sqlite3
```

#23 原始接口只接受两个完整 64 位小写十六进制 ID，必填数据库路径。
#27 新增 `config snapshots list` 和 CLI 的唯一短前缀输入；便捷查询服务先解析为完整 ID，
再调用本页既有公共 diff 服务，后者继续只接收完整 ID。JSON 输出未开放。
发现列表、排序、引用规则与只读保证见 [历史快照发现与引用](config-snapshots.md)。
ID 格式校验属于加载服务，不耦合进单快照或纯比较领域能力。
存在性与损坏验证先于相同 ID 短路；两者相同且有效输出“无差异”并返回 0。
存在差异或涉及校准也返回 0；ID 错误/不存在、缺库、未迁移、未知格式或损坏返回 2。
缺库不创建，重复比较输出一致，只读打开数据库，不写登记、缓存、分级、启用或激活事实。

中文人读输出包含类别、版本/哈希、受影响投影、分量“未配置 → 已配置”等转移和前后
基线身份；不显示完整 Profile/Prompt、原文 diff、输入错误值、原始异常或 SQL 参数。
只有前后分量均非 null 时追加“（语义变化）”；配置与未配置之间的变化仅显示受控转移。
所有 help 在外部 I/O 被拒绝时仍可运行，不读配置或数据库，不创建业务文件。
保存快照不是启用；完整校准变更审计、minor/major 分级、门禁与自动运行由后续流程接入。
完整 A2 由 #25 的独立结论覆盖本页能力，并保留 A2-01 固定测试与历史 scope；
格式身份及固定范围见[离线验证证据](../verification/offline-evidence.md#完整-a2-独立结论)。
