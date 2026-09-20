# 冻结契约导出与检查

当前只交付 `BoundaryOutput` 的 `boundary/v1` 冻结契约。价值预测、复用可行性
升级、原因契约和批量导出尚未实现。

## 命令与公共入口

维护者使用真实安装入口显式选择契约、声明版本和目标根目录：

```bash
paper-radar contracts export \
  --contract boundary \
  --version v1 \
  --target contracts
```

成功返回 0。首次运行创建快照；相同版本和内容再次运行返回 0 且不改写文件。
未知契约、无效版本、既有快照异常或写入失败返回非零。命令不访问网络、数据库
或模型，也不消耗自动处理配额。

只读确认既有快照没有漂移使用同一组显式选择：

```bash
paper-radar contracts check \
  --contract boundary \
  --version v1 \
  --target contracts
```

Python 调用方使用 `paper_radar.contracts.export_frozen_contract` 和
`paper_radar.contracts.check_frozen_contract`。纯内容生成可使用
`build_frozen_contract`；它直接调用权威 `BoundaryOutput.model_json_schema()`，不会维护
第二份字段定义。

## 路径与文件格式

`--target <目标>` 下的固定布局为：

```text
screening/
  boundary/
    v1/
      schema.json
      manifest.json
```

`screening`、`boundary`、`v1` 和两个文件名均来自代码中的受控选择，不接受模型
输出或任意路径片段。解析后的快照路径必须仍位于目标根目录内；已有符号链接若把
路径引向根目录外，导出会在写入前失败，`check` 也会直接拒绝检查。

两个 JSON 文件统一使用 UTF-8、键名排序、两空格缩进、非 ASCII 字符原样保存，
并以一个换行结束。内容不含时间、绝对路径或随机值。`schema.json` 包含契约身份
扩展；`manifest.json` 固定包含：

- `format_version`：清单格式，当前为 `1`；
- `contract` 与 `version`：受控契约身份；
- `schema_file`：固定为 `schema.json`；
- `schema_sha256`：对 `schema.json` 完整字节计算的十六进制 SHA-256。

首份快照为 `boundary/v1`，Schema SHA-256 是
`9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7`。

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

首次导出先在目标版本目录的同级临时目录完整写入、刷新 Schema 和清单，再以目录
重命名一次发布。清单不会先于完整 Schema 可见；中断或权限失败会清理临时目录，
不会把半文件当成成功快照，也不会触碰已经发布的版本。

## 受控结果与错误

`export_frozen_contract` 成功返回 `ContractExportResult`。`outcome` 只有两个值：

| 值 | 含义 |
| --- | --- |
| `created` | 首次发布了完整快照 |
| `unchanged` | 既有快照逐字节一致，未执行改写 |

失败抛出 `ContractExportError`；`category` 使用以下完整受控词汇，消息只提供中文
操作指引，不包含文件内容或底层异常文本：

| 类别 | 含义与操作 |
| --- | --- |
| `invalid_selection` | 契约或声明版本未实现；改用帮助列出的受控选择 |
| `damaged_snapshot` | 既有快照损坏或不完整；先恢复原快照，契约变化则新建版本 |
| `version_mismatch` | 快照身份与选择不一致；核对目标与版本，禁止覆盖 |
| `content_conflict` | 同一版本存在另一份内部一致内容；必须新建版本 |
| `invalid_target` | 目标不能解析；检查权限或符号链接循环 |
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
| `unreadable_snapshot` | 快照文件存在但不可读取；检查文件权限和文件系统状态 |
| `damaged_snapshot` | 不是规范 JSON、清单字段非法，或清单哈希与 Schema 字节不符；从版本控制恢复快照 |
| `version_mismatch` | 快照内部一致但契约或版本身份与选择不符；核对 `--contract` 与 `--version` |
| `content_drift` | 身份正确且内部一致，但 Schema 与当前权威输出不同；有意变更须新建版本，否则恢复快照 |
| `invalid_target` | 目标不是可访问的目录，或路径无法解析（例如符号链接循环）；选择有效目录 |
| `path_escape` | 受控子路径经符号链接逃出目标根目录；移除该链接 |

`scripts/check-offline` 在全部测试之后运行
`paper-radar contracts check --contract boundary --version v1 --target contracts`，
因此完整离线入口会实际执行这份快照的一致性检查。未来新增契约继续使用同一检查
路径和同一类别词汇。
