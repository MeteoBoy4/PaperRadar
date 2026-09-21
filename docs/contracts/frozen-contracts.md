# 冻结契约导出与检查

当前交付四份可单独或批量选择的 `v1` 磁盘冻结契约。`contracts export` 可在一次
命令中处理多份；`contracts check` 仍只检查一份，不提供批量汇总。

| CLI 受控名 | 权威定义 | 固定目录 |
| --- | --- | --- |
| `boundary` | `BoundaryOutput` | `screening/boundary/v1/` |
| `value-prediction` | `ValuePredictionOutput` | `screening/value-prediction/v1/` |
| `reuse-assessment` | `ReuseAssessmentOutput` | `screening/reuse-assessment/v1/` |
| `decision-reasons` | `screening_reason_json_schema()` 使用的权威 Pydantic 组合类型 | `screening/decision-reasons/v1/` |

## 命令与公共入口

维护者使用真实安装入口重复提供 `--contract`，显式选择契约、声明版本和目标根
目录。选择顺序不会改变执行顺序；系统始终按上表的 `ContractName` 声明顺序处理：

```bash
paper-radar contracts export \
  --contract boundary \
  --contract value-prediction \
  --contract reuse-assessment \
  --contract decision-reasons \
  --version v1 \
  --target contracts
```

每份契约最多选择一次。全部完成（含 `unchanged`）返回 0；选择、预检或写入失败
返回 2。首次运行创建快照；相同版本和内容再次运行不改写文件。命令不访问网络、
数据库或模型，也不消耗自动处理配额。

只读确认既有快照没有漂移使用同一组显式选择：

```bash
paper-radar contracts check \
  --contract boundary \
  --version v1 \
  --target contracts
```

Python 调用方使用 `paper_radar.contracts.export_frozen_contracts` 执行带预检的
批量导出；单份兼容入口为 `export_frozen_contract`，只读检查入口为
`check_frozen_contract`。纯内容生成可使用
`build_frozen_contract`；三种输出直接调用各自权威 Pydantic 模型的
`model_json_schema()`，原因契约直接调用从权威合法组合生成的 Pydantic Schema，
不会维护第二份字段或组合定义。

## 路径与文件格式

`--target <目标>` 下的固定布局为：

```text
screening/
  boundary/
    v1/
      schema.json
      manifest.json
  value-prediction/
    v1/
      schema.json
      manifest.json
  reuse-assessment/
    v1/
      schema.json
      manifest.json
  decision-reasons/
    v1/
      schema.json
      manifest.json
```

`screening`、四个契约目录名、`v1` 和两个文件名均来自代码中的受控选择，不接受
模型输出或任意路径片段。解析后的快照路径必须仍位于目标根目录内；已有符号链接
若把路径引向根目录外，导出会在写入前失败，`check` 也会直接拒绝检查。

两个 JSON 文件统一使用 UTF-8、键名排序、两空格缩进、非 ASCII 字符原样保存，
并以一个换行结束。内容不含时间、绝对路径或随机值。`schema.json` 包含契约身份
扩展；`manifest.json` 固定包含：

- `format_version`：清单格式，当前为 `1`；
- `contract` 与 `version`：受控契约身份；
- `schema_file`：固定为 `schema.json`；
- `schema_sha256`：对 `schema.json` 完整字节计算的十六进制 SHA-256。

当前四份 Schema SHA-256 为：

| 契约 | SHA-256 |
| --- | --- |
| `boundary/v1` | `9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7` |
| `value-prediction/v1` | `5ba68a0499903e01e733872bbd1967e04ae8149089ae1559a5d0a2c6c2fa351e` |
| `reuse-assessment/v1` | `48c31d66163f7022cd3e7499619d2a97701b11cdc92d9f2e4dfe701cf3d980ff` |
| `decision-reasons/v1` | `eabf88c7679433d52d8b8fa8a9cc3051c978a22ee528c785a187b146c555e4bc` |

## JSON Schema 与上下文校验边界

冻结 Schema 表达 Pydantic 可确定描述的结构规则：字段、必填性、类型、范围、
受控枚举、额外字段拒绝，以及原因契约中合法的结果/来源/原因组合。快照不包含
最终决定、期刊信誉、Rank、priority、urgency、自由标签、主题权重或置信分。

运行时上下文不会被冻结为全局 Schema：已启用主题 ID、原题名是否中文、当次选择器
提供的 excerpt ID 与种类，以及文本占位和“输入不足”约定，仍由
`validate_output` 接收对应只读 context 后校验。调用方不能把仅通过 JSON Schema
等同于通过完整公共契约；原因组合则由其 Schema 和 `validate_screening_reason`
共同使用同一权威组合定义。

## 不可覆盖与失败判据

声明版本一经发布，永久对应同一字节内容。契约语义变化必须在代码中注册新版本，
再导出新的版本目录；旧目录不会被删除或改写。

检查既有目录时按以下顺序给出确定性结果：

1. 任一文件缺失、不可读、不是规范 JSON、清单字段非法，或清单哈希与 Schema
   字节不符：`damaged_snapshot`（损坏或不完整）；
2. 内部一致的快照，其契约名或版本与所选身份不符：`version_mismatch`；
3. 身份正确且内部一致，但同版本 Schema 与当前权威输出不同：
   `content_conflict`，必须新建版本；
4. 两个文件均与当前输出逐字节相同：`unchanged`，不写入任何文件。

批量导出先完成全部选择解析和上述只读检查，再开始任何写入。只要任一既有目标
损坏、版本不一致、内容冲突或路径非法，就不创建或改写任何快照；合法但已一致的
目标报告为“未改写”，其余报告为“未完成”。未知、重复契约和无效版本也在目标
目录创建前失败。

首次导出先在目标版本目录的同级临时目录完整写入、刷新 Schema 和清单，再以目录
重命名一次发布。清单不会先于完整 Schema 可见；中断或权限失败会清理临时目录，
不会把半文件当成成功快照，也不会触碰已经发布的版本。

开始发布后不承诺跨多个版本目录或文件系统事务。若第 N 项发生不可预知的权限、
空间、挂载或中断故障，预检时已经一致的项无论声明顺序都报告“未改写”，故障前
完整发布的新项报告“已创建”；当前失败项和尚未发布的缺失项报告“未完成”，命令
返回 2。修复故障后使用完全相同的命令重跑：完整项逐字节一致且不改写，缺失项
继续补齐；不会回滚已发布的历史版本。

## 受控结果与错误

`export_frozen_contracts` 按声明顺序返回一组 `ContractExportResult`；单份入口返回
一个结果。`outcome` 只有两个成功值：

| 值 | 含义 |
| --- | --- |
| `created` | 首次发布了完整快照 |
| `unchanged` | 既有快照逐字节一致，未执行改写 |

失败抛出 `ContractExportError`；`category` 使用以下完整受控词汇，消息只提供中文
操作指引，不包含文件内容或底层异常文本：

批量发布期间的失败使用其子类 `ContractBatchExportError`，额外携带已完成结果、
逐份失败和完整选择顺序，供 CLI 安全报告“已创建 / 未改写 / 未完成”；不会携带
Schema 内容、输入或底层异常文本。

| 类别 | 含义与操作 |
| --- | --- |
| `invalid_selection` | 契约或声明版本未实现；改用帮助列出的受控选择 |
| `damaged_snapshot` | 既有快照损坏或不完整；先恢复原快照，契约变化则新建版本 |
| `version_mismatch` | 快照身份与选择不一致；核对目标与版本，禁止覆盖 |
| `content_conflict` | 同一版本存在另一份内部一致内容；必须新建版本 |
| `invalid_target` | 目标含非目录组件、不能解析或存在符号链接循环；在批量写入前修复目标路径 |
| `path_escape` | 受控子路径经符号链接逃出目标根；移除该链接 |
| `write_failed` | 权限、空间、只读挂载或其他写入失败；按具体中文指引处理 |

## 只读检查单份快照

`contracts check` 一次只检查一份显式选择的快照，不遍历目录也不汇总多份契约
（批量汇总属于后续 ticket）。命令复用导出使用的权威 Schema、规范序列化、清单
字段和 SHA-256 判据，只把“拒绝覆盖”的写入语义替换为检查语义：

- 一致时返回 0，并输出契约身份、快照位置和 SHA-256；
- 其余情况返回非零，不修复、不刷新、不创建目录，也不写入任何文件；
- 目标根目录、版本目录或必需文件不存在时直接报缺失，不创建数据目录；
- 不访问网络、数据库或模型，不消耗自动处理配额。

`check_frozen_contract` 成功返回 `ContractCheckResult`；失败抛出
`ContractCheckError`。其 `category` 复用导出词汇，并只在检查语义需要时区分
缺失、不可读取与内容漂移：

| 类别 | 判据与操作 |
| --- | --- |
| `invalid_selection` | 契约或声明版本未实现；改用帮助列出的受控选择 |
| `missing_snapshot` | 目标根目录、版本目录，或 `schema.json` / `manifest.json` 不存在；确认选择或先运行 export |
| `unreadable_snapshot` | 快照路径或文件存在但不可读取（目录搜索权限、文件读取权限或文件系统状态）；检查权限后重试 |
| `damaged_snapshot` | 不是严格规范 JSON（含 NaN / Infinity 等非标准常量、未配对代理项、位数超过固定上限 100 位的整数）、清单字段非法，或清单哈希与 Schema 字节不符；从版本控制恢复快照 |
| `version_mismatch` | 快照内部一致但契约或版本身份与选择不符；核对 `--contract` 与 `--version` |
| `content_drift` | 身份正确且内部一致，但 Schema 与当前权威输出不同；有意变更须新建版本，否则恢复快照 |
| `invalid_target` | 目标不是可访问的目录，或快照路径无法解析（符号链接循环、非目录组件）；选择有效目录 |
| `path_escape` | 受控子路径经符号链接逃出目标根目录；移除该链接 |

`scripts/check-offline` 在全部测试之后分别对 `boundary`、`value-prediction`、
`reuse-assessment` 和 `decision-reasons` 运行单份 `contracts check`，因此完整离线
入口会实际执行四份快照的一致性检查。它没有引入批量命令；四次检查继续复用同一
公开路径和同一类别词汇。
