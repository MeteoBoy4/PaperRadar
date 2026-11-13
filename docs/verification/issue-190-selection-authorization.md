# #190：选样接受授权与换样工程覆盖

本台账记录 B 的独立 D1 工程覆盖，不进入 A1–A10 回执、固定分母或 required 集合，
`stage_a_verified=false`。所有数据均为 `/tmp` 临时合成材料，没有访问真实实验根、凭据、
真实来源、Pi 或 Docling。工程通过不构成 B 的真实纵向验收。

## 覆盖与接缝

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_selection_cli.py` | 29 | CLI 选样冻结、owner/agent 区分、编号与规范 DOI、仅限本检查唯一成员、同 request 重放与异内容冲突、A→B→A 追加历史、过期换样引用拒绝、完整摘要与元数据修订变化拒绝、加载视图到写锁之间的变化拒绝、缺摘要／截断／强冲突阻断、写前共享 SET_DECISION visibility、安全日志入口守卫与只读无日志、冷进程禁外部 I/O 帮助、SQL UPDATE/DELETE/REPLACE 拒绝、SQL 故障和插入后中断原子性、并发换样单一当前选择、损坏选择／豁免／外发链的备份拒绝、恢复子进程回查完整私有授权 |
| `tests/test_experiment_selection_migrations.py` | 4 | 非空上一 revision `body02_read_tasks` 升级；建表、建立追加保护中断、推进 revision 中断时均回滚原 revision 与全部新对象，重跑成功且根事实不变 |

CLI 是主接缝；服务调用仅用于并发／事务故障边界。基础来源准备复用已确认的
`httpx.MockTransport` 与注入退避时钟。共享 visibility 接线观察是本票明确验收要求。
恢复通过真实 `restore verify` 子进程以及禁 socket 的公共历史查询子进程完成；原实验
布局移开后，查询使用恢复副本的 `database.sqlite3` 和 blobs，不需要 views、原配置文件、
Pi 安装、OAuth 或 Docling 缓存。该用例不证明操作系统隔离、禁网恢复现场或 #201 回放闭环。

私有原文理由、owner/agent、UTC 时间经恢复的完整公共记录单独断言；安全终端、日志与错误
不出现私有摘要／理由标记。没有通过删除业务原文来满足隐私测试。

## TDD 与验证

red → green 的可观察失败包括：

- 未注册 `select` 命令，首条 CLI 授权用例失败；实现后回执与重放通过。
- 备份缺 B 聚合时错误接受被篡改的选择；接入唯一聚合后为 `registration_invalid`。
- 坏 owner waiver 原来被归为 `copy_failed`；聚合统一错误边界后为 `registration_invalid`。
- 同 request 改为不存在的新视图时，原先先报制品错误；只读核对 request 后优先报 request_conflict，写锁内仍重查以处理竞争。
- 只有 UPDATE/DELETE 触发器时，SQLite REPLACE 能覆盖旧行；新增插入链保护后受控拒绝。
- 独立 Schema 节点发现 SQLite INTEGER 主键缺显式 NOT NULL；修正 DDL 后与 metadata 一致。

已运行本票全部 D1、head 单一维护者守卫、独立精确 Schema 节点
`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
受影响组件子集 187 项通过；CLI 兼容组合 59 项通过。定向 Ruff、mypy 与最终本票数量
以外部交付报告为准。Schema 保留既有 Screening 循环外键排序 SAWarning，不影响比较结果。
没有运行完整离线门禁，没有签发正式冻结树的通过回执。

## Migration 与敏感变更白名单

新增线性 revision `b001_selection_authorizations`，上一 revision 固定为
`body02_read_tasks`。开工前已由 #185 交付核实 #139 CLOSED 且交付提交在集成祖先中。
新表与 UPDATE/DELETE/INSERT 触发器仅经 Alembic 创建，ORM metadata 不执行 DDL。

人工 head 推进白名单严格限于：

- `tests/migration_expectations.py` 的人工常量。
- `scripts/a2_scope.py`、`scripts/a2_full_scope.py`、`scripts/a3_scope.py` 至
  `scripts/a10_scope.py` 的 `MIGRATION_REVISION`，及 A3 的
  `FORMAT_VERSIONS["backup_database_revision"]`。
- `src/paper_radar/backup/manifest.py::BACKUP_DATABASE_REVISION`。
- `docs/contracts/artifact-store.md` 与 `docs/contracts/backup-restore.md` 的当前 revision 声明。
- `scripts/verification_scope_materials.py` 中常量与生产备份声明的两个中央哈希。

常量在 A2-01 登记为 source、完整 A2 与 A3–A10 登记为 fixture，仍须全部十组 S3 审阅；最终树身份上的逐组确认和
必要重绑由 #185/#206 唯一集成收口承接。本票不修改历史 revision、历史测试、fixture、
证据或其它中央哈希，不机械重绑随实现产生的 source/support 漂移。

## 预期漂移与下游责任

除人工 head 白名单外，已有 source/support 改动仅为：
`src/paper_radar/experiment/cli.py`、`src/paper_radar/storage/schema.py`、
`src/paper_radar/backup/service.py`。新增生产模块为
`experiment/selections.py`、`experiment/validation.py` 与本 migration；新增 D1 两模块。
README、GLOSSARY、B／日志／备份／制品 Contract 与路线图当前接口导航同步。

唯一 B 聚合是 `experiment.validation.validate_all(database, data_root)`，备份
`verify_contents` 单处调用；后续新增授权、PDF／版式、Read、报告与暴露事实只扩此聚合。
`Selections.history_in_connection/current_in_connection(connection)` 为后续领取事务提供
完整历史／当前授权；领取方仍须重查当前选择、论文版本、外发授权及阶段资格。
旧 request 回执、旧选择或恢复副本历史均不允许自动继续执行。

实际 accepted 代执行、Screening、PDF 确认、正文质量、六项人工核查、Read、报告、
暴露导出与现场脱网回放由 B 后续票承接。没有验证真实 Feed 字段、摘要、模型、正文、
主机资源或任何 live 行为。
