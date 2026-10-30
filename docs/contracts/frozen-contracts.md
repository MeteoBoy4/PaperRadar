# 冻结契约导出与检查

当前提供五份可单独或批量选择的 `v1` 磁盘冻结契约。`contracts export` 可在一次
命令中处理多份；`contracts check` 也可在一次命令中逐项检查多份并汇总退出码。

| CLI 受控名 | 权威定义 | 固定目录 |
| --- | --- | --- |
| `boundary` | `BoundaryOutput` | `screening/boundary/v1/` |
| `value-prediction` | `ValuePredictionOutput` | `screening/value-prediction/v1/` |
| `reuse-assessment` | `ReuseAssessmentOutput` | `screening/reuse-assessment/v1/` |
| `decision-reasons` | `screening_reason_json_schema()` 使用的权威 Pydantic 组合类型 | `screening/decision-reasons/v1/` |
| `read` | `paper_radar.reading.ReadAnalysisOutput` | `read/read/v1/` |

本契约定义快照生成、磁盘发布和只读检查；Screening 的结构与上下文接收规则见
[Screening Contract](screening-validation.md)，Read 的结构、独立价值词汇与证据业务
校验见[Read Contract](read-validation.md)。Schema 通过不等于业务接收成功。

配置 check/compile 复用冻结契约检查后，还重新读取 Schema 与清单，分别逐字节
核对当前权威输出；历史 load 核对已登记原始材料与引用，不重新生成当前 Schema。
选择器与配置就绪规则见[运行配置契约](runtime-config.md#模型提示词与契约)，
Read 选择示例见[Read 配置与分块身份](runtime-config.md#read-配置与分块身份)。

## 命令与公共入口

维护者使用真实安装入口重复提供 `--contract`，显式选择契约、声明版本和目标根
目录。`--contract` 至少一次，`--version`、`--target` 均必须显式提供，三者无默认值；
只接受上表契约和 `v1`，不提供隐式 `--all`。选择顺序不会改变执行顺序；系统始终按
上表的 `ContractName` 声明顺序处理：

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

只读确认单份既有快照没有漂移：

```bash
paper-radar contracts check \
  --contract boundary \
  --version v1 \
  --target contracts
```

同时检查四份 Screening 契约时显式列出选择：

```bash
paper-radar contracts check \
  --contract boundary \
  --contract value-prediction \
  --contract reuse-assessment \
  --contract decision-reasons \
  --version v1 \
  --target contracts
```

Python 调用方使用 `paper_radar.contracts.export_frozen_contracts` 执行带预检的
批量导出；单份兼容入口为 `export_frozen_contract`。只读检查分别使用
`check_frozen_contract` 和 `check_frozen_contracts`。纯内容生成可使用
`build_frozen_contract`；四种输出直接调用各自权威 Pydantic 模型的
`model_json_schema()`，原因契约直接调用从权威合法组合生成的 Pydantic Schema，
不会维护第二份字段或组合定义。

导出与检查入口均要求显式 `name`（单份）或 `names`（非空 iterable）、`version`、
`target`；名称和版本接受受控枚举或对应字符串，目标接受 `Path` 或字符串。
`build_frozen_contract(name: ContractName, version: ContractVersion)` 返回
`FrozenContract`，包含 `name`、`version`、`schema_bytes`、`schema_sha256`、
`manifest_bytes`、`snapshot_parts`、`schema_filename`、`manifest_filename`；
它不读写文件系统，未注册的组合抛出 `KeyError`。

Read 可单独选择，或与任意已实现契约混选；声明顺序位于四份 Screening 契约之后：

```bash
paper-radar contracts export --contract read --version v1 --target contracts
paper-radar contracts check --contract read --version v1 --target contracts
```

导出成功项与 `unchanged` 项写标准输出；`failed`、`not_attempted` 项及整体选择
错误写标准错误。检查整批通过时全部项写标准输出；只要一项失败，整批逐项结果均写
标准错误。两条命令均以中文给出原因与处理指引，不生成额外结果文件。

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
read/
  read/
    v1/
      schema.json
      manifest.json
```

area（`screening` / `read`）、契约目录名、`v1` 和两个文件名均来自代码中的受控选择，不接受
模型输出或任意路径片段。目标根按路径解析后的目录确定；版本目录的解析路径必须仍
位于该根内。目录符号链接若把版本目录引向根目录外，导出在写入前失败，`check`
也拒绝检查。此检查不核验 `schema.json` / `manifest.json` 自身的符号链接目标，
也不锁定检查后的路径状态；它不是文件级链接或并发路径替换的隔离保证。

两个 JSON 文件统一使用 UTF-8、键名排序、两空格缩进、非 ASCII 字符原样保存，
并以一个换行结束。内容不含时间、绝对路径或随机值。`schema.json` 的身份扩展为：

- `$schema`：`https://json-schema.org/draft/2020-12/schema`；
- `$id`：`urn:paper-radar:contracts:<area>:<contract>:<version>`；
- `x-paper-radar-contract`：`{"name": "<contract>", "version": "<version>"}`。

`manifest.json` 固定包含：

- `format_version`：清单格式，生成值为整数 `1`；
- `contract` 与 `version`：受控契约身份；
- `schema_file`：固定为 `schema.json`；
- `schema_sha256`：对 `schema.json` 完整字节计算的十六进制 SHA-256。

当前五份 Schema SHA-256 为：

| 契约 | SHA-256 |
| --- | --- |
| `boundary/v1` | `9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7` |
| `value-prediction/v1` | `5ba68a0499903e01e733872bbd1967e04ae8149089ae1559a5d0a2c6c2fa351e` |
| `reuse-assessment/v1` | `48c31d66163f7022cd3e7499619d2a97701b11cdc92d9f2e4dfe701cf3d980ff` |
| `decision-reasons/v1` | `eabf88c7679433d52d8b8fa8a9cc3051c978a22ee528c785a187b146c555e4bc` |
| `read/v1` | `1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111` |

## JSON Schema 与上下文校验边界

冻结 Schema 表达 Pydantic 可确定描述的结构规则：字段、必填性、类型、范围、
受控枚举、额外字段拒绝，以及原因契约中合法的结果/来源/原因组合。
`decision-reasons` 描述结果、来源和原因的合法组合，并不产生实际筛选决定；其余四份
是模型输出结构。快照不包含期刊信誉、Rank、priority、urgency、自由标签、主题权重
或置信分。

运行时上下文不会被冻结为全局 Schema。Screening 的已启用主题、原题名语言事实、
选择器 excerpt ID 与种类，以及文本占位和“输入不足”等业务接收规则由
[Screening 公共验证器](screening-validation.md#公共入口)负责；Read 的消费上下文和
证据规则由[Read Contract](read-validation.md)负责。调用方不能把仅通过 JSON Schema
等同于通过完整公共契约。

## 不可覆盖与失败判据

声明版本一经发布，永久对应同一字节内容。契约语义变化必须在代码中注册新版本，
再导出新的版本目录；旧目录不会被删除或改写。

检查既有目录时按以下顺序给出确定性结果：

1. 任一文件缺失、不可读、不是规范 JSON、清单字段非法，或清单哈希与 Schema
   字节不符：`damaged_snapshot`（损坏或不完整）；
2. 内部一致的快照，其契约名或版本与所选身份不符：`version_mismatch`；
3. 身份正确且内部一致，但同版本 Schema 与当前权威输出不同：
   `content_conflict`，必须新建版本；
4. 通过上述检查且 Schema 与当前权威输出逐字节相同：`unchanged`，不写入任何文件。

这里的清单检查要求规范 JSON、固定键集合、`schema_file`、契约/版本身份和 Schema
哈希匹配，但不与权威清单逐字节比较。`format_version` 使用与 `1` 的值相等判断，
不是严格整数类型检查；因此规范序列化为 `true` 或 `1.0` 的清单也可通过导出预检与
只读检查。生成器仍只生成整数 `1`；这项检查限制不改变声明版本的不可变要求，
也不表示其他清单字节获得发布授权。

批量导出先完成全部选择解析和上述只读检查，再开始任何写入。只要任一既有目标
损坏、版本不一致、内容冲突或路径非法，就不创建或改写任何快照；合法但已一致的
目标报告为“未改写”，其余报告为“未完成”。未知、重复契约和无效版本也在目标
目录创建前失败。

首次导出先在目标版本目录的同级临时目录完整写入、刷新 Schema 和清单，再以目录
重命名一次发布，再刷新父目录。清单不会先于完整 Schema 可见；可捕获的中断或
写入失败通过 `finally` 尝试清理临时目录，不把临时半文件当成成功快照。
进程被强制终止或清理本身失败时不保证临时目录消失；版本目录重命名之后的父目录
刷新失败也可报告 `failed`，此时完整版本目录可能已经存在。

开始发布后不承诺跨多个版本目录或文件系统事务。若第 N 项发生以 `OSError` 返回的
权限、空间或挂载故障，预检时已经一致的项无论声明顺序都报告“未改写”，故障前
完整发布的新项报告“已创建”；当前失败项和尚未尝试发布的缺失项报告“未完成”，命令
返回 2。`KeyboardInterrupt` 或进程强制终止不保证返回整批结果或上述退出码。
修复故障后使用完全相同的命令重跑：完整项重新检查且不改写，缺失项继续补齐；
不会回滚已发布的历史版本。

## 受控结果与错误

`export_frozen_contracts` 按声明顺序返回 `ContractBatchExportResult.items`，每份
契约对应一个 `ContractExportItemResult`；逐份预检或发布失败也返回结果，不抛异常。
只有选择无效时，才在生成任何 item 前整体抛出 `ContractExportError`。
单份入口成功时返回 `ContractExportResult`，其 `outcome` 在类型上只可能是
`created` 或 `unchanged`；失败仍抛出 `ContractExportError`。

| `outcome` | 中文描述 | 含义与操作 |
| --- | --- | --- |
| `created` | 已创建冻结契约 | 首次发布了完整快照。 |
| `unchanged` | 冻结契约内容一致，未改写 | 既有清单通过上述判据且 Schema 与权威输出逐字节一致，未执行改写。 |
| `failed` | 逐份判决的中文指引 | 该份预检或发布失败；按 `error_category` 和指引处理。 |
| `not_attempted` | 批量导出已停止；修复上述问题后原命令重跑即可补齐。 | 其他项预检失败，或发布阶段首次失败后，该份原本待发布的缺失快照没有尝试；两种成因均修复问题后用原命令重跑。预检时已匹配的快照始终为 `unchanged`。 |

逐项结果字段如下。判别字段是 `outcome`；`error_category=None` 不代表成功，
`not_attempted` 的该字段同样为 `None`。只有全部 item 为 `created` 或
`unchanged` 时，批量结果的 `passed` 才为真。

| 字段 | `created` / `unchanged` | `failed` | `not_attempted` |
| --- | --- | --- | --- |
| `name`、`version` | 所选契约身份 | 所选契约身份 | 所选契约身份 |
| `outcome` | 对应成功值 | `failed` | `not_attempted` |
| `error_category` | `None` | 下表类别 | `None` |
| `message_zh` | 上表中文描述 | 失败判决的中文指引 | 上表中文描述 |
| `snapshot_dir`、`schema_sha256` | 快照路径和 SHA-256 | `None` | `None` |

失败类别使用以下完整受控词汇，中文指引不包含文件内容或底层异常文本：

| 类别 | 含义与操作 |
| --- | --- |
| `invalid_selection` | 契约或声明版本未实现；改用帮助列出的受控选择 |
| `damaged_snapshot` | 既有快照损坏或不完整；先恢复原快照，契约变化则新建版本 |
| `version_mismatch` | 快照身份与选择不一致；核对目标与版本，禁止覆盖 |
| `content_conflict` | 同一版本存在另一份内部一致内容；必须新建版本 |
| `invalid_target` | 目标含非目录组件、不能解析或存在符号链接循环；在批量写入前修复目标路径 |
| `path_escape` | 受控子路径经符号链接逃出目标根；移除该链接 |
| `write_failed` | 权限、空间、只读挂载或其他写入失败；按具体中文指引处理 |

## 只读检查与整组汇总

`contracts check` 只检查通过一个或多个 `--contract` 显式选择的快照，不遍历目标
目录。每份最多选择一次，未知或重复选择会在读取任何快照前整体拒绝。合法选择不论
参数顺序均按上表的 `ContractName` 声明顺序处理。命令逐份复用单份检查的权威
Schema、规范序列化、清单字段、SHA-256 判据与错误类别，不维护第二套判断逻辑：

- 所有已选契约一致时返回 0；任一项失败时仍检查其余独立项，全部报告后返回 2；
- 每项固定输出 `contract`、`version`、`result`、`error_category` 和中文处理说明；
  成功项的 `result=passed`、`error_category=none`，失败项为 `result=failed` 和下表类别；
- 成功项同时输出快照位置和 SHA-256；失败项不回显文件内容或底层异常；
- 通过表示清单通过上述判据且 Schema 与当前权威输出逐字节一致，不表示清单与生成器输出逐字节一致；
- 成功或失败都不修复、不刷新、不创建目录，也不写入任何文件；
- 目标根目录、版本目录或必需文件不存在时直接报缺失，不创建数据目录；
- 不访问网络、数据库或模型，不消耗自动处理配额。

`check_frozen_contract` 成功返回 `ContractCheckResult`；失败抛出
`ContractCheckError`。其 `category` 复用导出词汇，并只在检查语义需要时区分
缺失、不可读取与内容漂移。`check_frozen_contracts` 先整体验证选择，然后与单份入口
共享同一只读判决和结果构造逻辑，返回包含全部 `ContractCheckItemResult` 的 `ContractBatchCheckResult`；
`passed` 仅在全部项通过时为真。

单份成功结果含 `name`、`version`、`snapshot_dir` 和 `schema_sha256`；批量逐项还含
`outcome`（`passed` / `failed`）、`error_category` 与 `message_zh`。成功项的
`error_category=None`，失败项的 `snapshot_dir` 和 `schema_sha256` 为 `None`。
Python 的 `outcome` 对应 CLI 的 `result` 字段；CLI 用 `none` 表示无错误类别。

| 类别 | 判据与操作 |
| --- | --- |
| `invalid_selection` | 契约或声明版本未实现；改用帮助列出的受控选择 |
| `missing_snapshot` | 目标根目录或版本目录不存在时确认选择或先运行 export；已存在的版本目录缺少 `schema.json` / `manifest.json` 时从版本控制恢复完整快照，不手工补齐 |
| `unreadable_snapshot` | 快照路径或文件存在但不可读取（目录搜索权限、文件读取权限或文件系统状态）；检查权限后重试 |
| `damaged_snapshot` | 不是严格规范 JSON（含 NaN / Infinity 等非标准常量、未配对代理项、位数超过固定上限 100 位的整数）、清单字段非法，或清单哈希与 Schema 字节不符；从版本控制恢复快照 |
| `version_mismatch` | 快照内部一致但契约或版本身份与选择不符；核对 `--contract` 与 `--version` |
| `content_drift` | 身份正确且内部一致，但 Schema 与当前权威输出不同；有意变更须新建版本，否则恢复快照 |
| `invalid_target` | 目标存在但不是目录，或快照路径无法解析（符号链接循环、非目录组件）；选择有效目录。目录搜索权限拒绝在能够解析到检查阶段时归为 `unreadable_snapshot` |
| `path_escape` | 受控子路径经符号链接逃出目标根目录；移除该链接 |

完整离线入口显式检查四份 Screening 契约，A9 结论另显式检查 Read；契约选择
不从注册表隐式扩张。验收组、同次证据绑定、退出条件和历史证明范围见
[验证状态 Contract](verification-status.md)与[离线验证证据](../verification/offline-evidence.md)。

## 不提供／不证明

- 磁盘检查不证明模型输出通过上下文或证据业务验证，也不证明真实模型、生产接线或
  自动精读就绪；生产消费者责任见[路线图 B](../roadmap.md#module-b)与
  [Read 生产者](../roadmap.md#module-body)。
- 批量导出不提供跨快照事务、并发写者锁或针对敌对文件系统变更的安全隔离。
  同版本清单的严格类型与权威字节核验存在上述实现限制；不以 `unchanged` 或检查
  通过证明两份文件均等于生成器输出。不可变目标见[规格 §7.6](../../intent/draft.md#76-模型配置)，
  尚不能由检查器完整证明，收口入口见[路线图 A](../roadmap.md#module-a)。

## 相关

依据：[#12](https://github.com/MeteoBoy4/PaperRadar/issues/12)、[#97](https://github.com/MeteoBoy4/PaperRadar/issues/97)、[#99](https://github.com/MeteoBoy4/PaperRadar/issues/99)。

[规格](../../intent/draft.md#七配置与-agent-契约)；[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)；[路线图承接](../roadmap.md#module-b)。
