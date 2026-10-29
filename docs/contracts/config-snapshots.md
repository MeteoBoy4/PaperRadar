# 历史配置快照发现与引用（#27）

数据库选择档案库，快照引用选择其中的历史配置。完整 64 位小写十六进制
SHA-256 仍是权威身份；便捷引用不参与快照、阶段投影或校准基线身份。
本边界提供 CLI 输入与快照发现，不证明完整 A2 或阶段 A 通过。

## 公共查询边界

从 `paper_radar.config` 导入：

| 入口 | 公开结果 | 保证 |
| --- | --- | --- |
| `list_config_snapshots(database)` | `tuple[ConfigSnapshotSummary, ...]` | 读取全库快照索引与版本引用摘要，不加载配置正文，不验证快照内容完整性。 |
| `resolve_config_snapshot_reference(database, reference)` | 唯一完整 ID：`str` | 在解析时的全部快照中匹配，不验证候选载荷。 |
| `diff_config_snapshots(database, before_id, after_id)` | 既有 `ConfigSnapshotDiff` | 仍只接收完整 ID；沿用 #23 存在性、格式、内容与版本引用验证。 |

错误统一为脱敏 `ConfigError`。摘要是不可变对象：`snapshot_id`、`short_reference`、
`created_at`（UTC 的 aware datetime 或 `None`）和 `versions`。版本摘要为不可变
`SnapshotVersion(kind, name, version)`，种类使用 `MaterialKind`，逻辑名称使用
[运行配置契约](runtime-config.md#输入与路径)的封闭集合，声明版本沿用既有格式。
摘要不含配置正文、哈希材料、就绪、启用或完整性验证结论。

列表只读取已有创建时间；未记录（NULL 或空串）展示“未记录”，不补写。
已有时间按实际时刻新到旧，同时间按完整 ID 升序；未记录项最后按完整 ID 升序。
版本摘要按种类、逻辑名称、声明版本升序排列。索引、时间或受控摘要字段损坏时
明确拒绝；列表成功也不表示载荷格式、哈希或材料引用完整性已验证。

存储索引查询位于 `storage/snapshot_queries.py`，公共查询服务位于
`config/snapshot_queries.py`，摘要类型与薄 CLI 分别独立。纯投影和 diff 核心
不消费前缀，也不复制历史加载或校准差异判据。
受控逻辑名称由纯配置模块 `config/material_names.py` 统一维护，列表摘要与历史加载
共用同一集合。存储层用不可变 `VersionRefRecord(kind, name, declared_version)`
传递版本引用，不依赖配置类型。索引与引用在显式只读事务内取得同一读视图；
sqlite3 的 legacy 模式下，SQLAlchemy autobegin 不为 SELECT 启动底层事务。

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

`--database` 必填，不读取当前 settings、原材料或凭据。列表、解析和比较全程只读，
不建库、迁移、登记版本、保存快照、更新时间、写前缀索引或缓存，不导出契约，
不联网、不调用模型、不消耗配额。初始化和升级仍只能通过 `db upgrade`。
不生成 minor/major、校准通过、启用或激活事实。

成功退出 0，包括空库“暂无已保存快照”、有差异、无差异或涉及校准。
非法参数、未找到、歧义、缺库、未初始化、缺迁移、未知或更新的 revision、
未知快照格式、损坏或加载失败退出 2。错误含受控原因和操作指引，
不回显原始异常、SQL 参数、Profile、Prompt 或 secret。沿用中文人读输出，无 `--json`。
所有 help 在空目录、缺配置和缺数据库时返回 0，不连接数据库或创建业务文件。

验证使用真实迁移、临时 SQLite、固定碰撞索引 fixture 和真实安装 CLI，沿用外部
I/O 哨兵；快照发现测试独立于 A1 固定测试和四份历史 v1 契约，不重复 #23 投影/基线算法测试。
没有新增 migration 或持久字段。

#97 另覆盖显式 Read v1 的 `contract_schema.read` / `contract_manifest.read` 摘要及
只读 diff；它们沿用同一材料登记与历史 load，不重新生成 Schema，不依赖当前配置目录。
缺少 Read 契约的旧快照仍保留原身份与 `read_contract`；新选择只影响 Read 投影。

#98 另验证含/不含 Read 契约的双历史快照与候选原字节在阻断原根的新进程恢复，
完整范围和上下文固定常量的限制见 [Read 恢复说明](read-validation.md#恢复范围98)。
`RuntimeConfigSnapshot` 默认 repr/str 隐藏 `payload_json`，显式访问与载荷身份不变。

## 相关

依据：[#23](https://github.com/MeteoBoy4/PaperRadar/issues/23)、[#27](https://github.com/MeteoBoy4/PaperRadar/issues/27)。

[规格](../../intent/draft.md#七配置与-agent-契约)；[ADR-0023](../adr/0023-separate-runtime-config-snapshots-from-calibration-baselines.md)；[路线图承接](../roadmap.md#module-b)。
