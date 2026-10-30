<a id="历史配置快照发现与引用27"></a>

# 历史配置快照发现与引用

数据库选择档案库，快照引用选择其中的历史配置。完整 64 位小写十六进制
SHA-256 是权威身份；便捷引用不参与快照、阶段投影或校准基线身份。
本契约定义只读发现、引用解析及 CLI 将引用交给历史比较的边界；配置编译、
版本登记与历史加载由[运行配置契约](runtime-config.md)定义，比较结果与语义判据由
[配置投影与比较契约](config-projections.md#diff-结果与-cli)定义。

## 公共查询边界

入口从 `paper_radar.config` 导入，`database` 为显式 `pathlib.Path`，必须指向
已有且已升级到当前程序随包迁移 head 的 SQLite 档案库；不隐式初始化或升级：

| 入口 | 公开结果 | 保证 |
| --- | --- | --- |
| `list_config_snapshots(database)` | `tuple[ConfigSnapshotSummary, ...]` | 读取全库快照索引与版本引用摘要，不加载配置正文，不验证快照内容完整性。 |
| `resolve_config_snapshot_reference(database, reference)` | 唯一完整 ID：`str` | 在解析时的全部快照中匹配，不验证候选载荷。 |
| `diff_config_snapshots(database, before_id, after_id)` | `ConfigSnapshotDiff` | 只接收完整 ID；先按[历史加载规则](runtime-config.md#身份登记与回放)验证两份快照，再比较。 |

错误统一为脱敏 `ConfigError`。摘要是不可变对象：`snapshot_id`、`short_reference`、
`created_at`（UTC 的 aware datetime 或 `None`）和 `versions`。版本摘要为不可变
`SnapshotVersion(kind, name, version)`，种类使用 `MaterialKind`，逻辑名称使用
[运行配置契约](runtime-config.md#输入与路径)的封闭集合，声明版本沿用既有格式。
摘要不含配置正文、材料哈希、就绪、启用或完整性验证结论。

列表只读取已有创建时间；未记录（NULL 或空串）展示“未记录”，不补写。
已有时间按实际时刻新到旧，同时间按完整 ID 升序；未记录项最后按完整 ID 升序。
版本摘要按种类、逻辑名称、声明版本升序排列。索引、时间或受控摘要字段损坏时
明确拒绝；列表成功也不表示载荷格式、哈希或材料引用完整性已验证。

单次列表的快照索引与版本引用摘要在同一显式只读事务中读取，保持同一读视图。
列表与历史加载共用受控逻辑名称集合。引用解析只查询索引；纯投影和 diff 核心
不消费前缀。CLI 的两次引用解析与后续 diff 不构成一个整体读取事务。

## 引用规则

- 接受 8–63 位小写十六进制前缀，或完整 64 位小写十六进制 ID。
- 完整 ID 精确匹配；拒绝过短、过长、大写、非十六进制、空白等输入，不纠错或归一化。
- 匹配范围为指定数据库内全部快照。零匹配提示“未找到快照”；多个匹配提示补充字符。
  不按时间、列表顺序或相似度选择，不提供名称、标签、latest/current 或其他别名。
- 列表中的便捷引用从 8 位开始按需延长。若前 63 位仍与其他 ID 相同，则直接显示
  完整 64 位 ID，不截断、不报错。
- 前缀仅在查询时唯一，后续新增快照可能使它变为歧义，使用时重新验证。
  长期记录、脚本和审计引用应保留完整 ID。

CLI 两个引用都成功解析后才把完整 ID 交给既有 diff 服务。不同长度的前缀即使
解析为同一快照，仍执行存在性与完整性验证，成功后报告无差异。

## 中文 CLI 与操作示例

先通过既有显式入口初始化档案库，再保存两份合成配置（工程示例，非校准资料）：

```bash
mkdir -p data
uv run --offline --locked paper-radar db upgrade --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-boundary.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config compile \
  --settings examples/config/settings-value.yaml --database data/paperradar.sqlite3
uv run --offline --locked paper-radar config snapshots list \
  --database data/paperradar.sqlite3
```

从列表中复制两份记录的“便捷引用”或“完整 ID”，替换下面两个占位参数；可以混用：

```bash
uv run --offline --locked paper-radar config diff <before-reference> <after-reference> \
  --database data/paperradar.sqlite3
```

`--database` 必填，不读取当前 settings 或原材料文件，也不读取凭据。列表、解析和比较全程只读，
不建库、迁移、登记版本、保存快照、更新时间、写前缀索引或缓存，不导出契约，
不联网、不调用模型、不消耗配额。初始化和升级仍只能通过 `db upgrade`。
不生成 minor/major、校准通过、启用或激活事实。

成功退出 0，包括空库“暂无已保存快照”、有差异、无差异或涉及校准。
沿用中文人读输出，无 `--json`。所有相关 `--help` 在空目录、缺配置和缺数据库时
返回 0，不连接数据库或创建业务文件。

## 错误与拒绝

公共查询的受控错误为 `ConfigError`，CLI 参数或查询失败退出 2；错误只含脱敏原因
和操作指引，不回显错误输入值、原始异常、SQL 参数、Profile、Prompt 或 secret。

| 情况 | 拒绝边界与处理 |
| --- | --- |
| 引用格式非法 | 解析前拒绝；从列表复制合法引用，不修剪空白或纠正大小写。 |
| 无匹配或前缀歧义 | 分别提示“未找到快照”或补充字符；核对档案库或改用完整 ID。 |
| 缺库、未初始化、revision 缺失或损坏 | 拒绝查询，不建库或修复；检查数据库，初始化使用显式 `db upgrade --database`。 |
| 已知旧 revision | 拒绝查询，提示先显式 `db upgrade --database`。 |
| 未知或较新 revision | 拒绝查询，使用匹配版本的程序检查，不隐式升级。 |
| 索引表缺失或数据库读取失败 | 拒绝查询，检查数据库表、权限与迁移状态，不回显 SQL。 |
| 索引身份损坏 | 列表检查全部 ID；解析检查唯一匹配的 ID，拒绝不合法的完整身份。解析不构成全库完整性检查。 |
| 时间或受控版本摘要损坏 | 列表拒绝；时间须带时区，种类、逻辑名称和声明版本须合法。不补写或修复。 |
| 未知快照编译格式、载荷／原材料／版本引用损坏或加载失败 | diff 按历史加载规则拒绝，即使两份引用解析成相同 ID。列表与解析本身不检查这些内容，不能以其成功替代 diff/load。 |

## 不提供／不证明

- 发现与解析不验证快照载荷、原始材料或引用闭包，不输出就绪、启用或完整性结论。
  `RuntimeConfigSnapshot` 默认 repr/str 隐藏 `payload_json`，不改变显式访问或载荷身份；
  隐藏表示不等于载荷脱敏，显式载荷仍须受控消费。
- 摘要支持已登记的 `contract_schema.read` / `contract_manifest.read`，比较继续使用库内
  历史材料，不重新生成 Schema、不依赖当前配置目录。旧快照身份、Read 缺项与投影隔离
  由[运行配置契约](runtime-config.md#read-配置与分块身份)及[配置投影契约](config-projections.md#规范内容与缺项)定义。
- 不提供名称、标签或 latest/current 别名；不提供完整校准变更审计、minor/major 分级、
  校准门禁或自动运行。校准工作流由[路线图 D](../roadmap.md#module-d)承接，自动运行由
  [路线图 I](../roadmap.md#module-i)承接。
- 查询或比较成功不证明模型、真实来源、正式校准、自动精读、完整 A2 或阶段 A 通过。
  本地配置诊断与阶段 A 收口由[路线图 A](../roadmap.md#module-a)承接；Read 正文与真实
  恢复闭包由[路线图 Body](../roadmap.md#module-body)／[B](../roadmap.md#module-b)承接，
  NAS 恢复由[路线图 I](../roadmap.md#module-i)承接。恢复接口与安全限制见
  [备份恢复契约](backup-restore.md)，既有验证的时点与证明边界见
  [历史证据](../verification/contracts-config-snapshots-history.md)。

## 相关

依据：[#22](https://github.com/MeteoBoy4/PaperRadar/issues/22)、[#23](https://github.com/MeteoBoy4/PaperRadar/issues/23)、[#27](https://github.com/MeteoBoy4/PaperRadar/issues/27)、[#97](https://github.com/MeteoBoy4/PaperRadar/issues/97)、[#98](https://github.com/MeteoBoy4/PaperRadar/issues/98)；[规格 §3.4](../../intent/draft.md#34-阶段输入指纹)、[§7](../../intent/draft.md#七配置与-agent-契约)；[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)。

实现：[公共查询](../../src/paper_radar/config/snapshot_queries.py)、[摘要类型](../../src/paper_radar/config/snapshot_summary.py)、[存储查询](../../src/paper_radar/storage/snapshot_queries.py)、[列表 CLI](../../src/paper_radar/config/snapshot_cli.py)、[diff CLI](../../src/paper_radar/config/cli.py)。

回归定位：[查询](../../tests/test_config_snapshot_queries.py)、[CLI](../../tests/test_config_snapshot_cli.py)、[diff 历史加载](../../tests/test_config_diff_service.py)、[Read 配置](../../tests/test_read_config.py)、[Read 恢复](../../tests/test_read_recovery.py)。
