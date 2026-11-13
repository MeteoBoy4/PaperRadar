# #187：显式实验根与 JGR v2 取得工程覆盖

本台账记录 B 的独立 D1 工程覆盖，不进入 A1–A10 回执、固定分母或 required 集合，
`stage_a_verified=false`。不新增 Alembic migration，不改表定义或冻结旧测试／fixture。

## 覆盖与接缝

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_feed_cli.py` | 21 | CLI 初始化及同根幂等、production/unknown 用途拒绝、旧 experiment revision 显式升级、JGR v2 主摘要与 v1 语言观察、请求重放、304 原成员关联、同响应不增 discovery、新响应增量与历史、强冲突观察、HTTP/条目失败、受控原因及隐私、执行日志装配、冷进程禁 I/O 中文帮助、参数错误、损坏 SQLite、初始化登记/发布故障与恢复、中断 130 |

主接缝是产品 CLI；结果经组件公开读取入口回查。HTTP 全部使用 `MockTransport`，
来源配额与退避使用注入时钟。初始化故障仅在临时根 SQL/文件发布边界注入；
旧 revision 用真实迁移构造，根事实保持原身份。帮助冷进程启用现有
`deny_external_io` 守卫。日志执行入口守卫在本 D1 模块新增，既有冻结审计守卫不变。

TDD red：`init` 缺失命令失败；`feed-fetch` 缺失命令失败；304 缺少原成员投影失败；
旧 experiment revision 被迁移前版本守卫阻断失败；非法联系邮箱丢失封闭原因失败；
新包提前导入 SQLAlchemy 导致禁 I/O 冷进程 help 失败；损坏 SQLite 的初始化异常未受控失败。
相应修正后 21 项通过。

## 验证

- 相关组合：新 D1 模块、`test_feed_pipeline.py`、`test_wiley_production_versions.py`、
  `test_runtime_logging_feed.py`、`test_feed_language.py` 和 Schema 一致性节点
  `test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`：
  75 passed；Schema 比较有已有 Screening 循环外键排序 SAWarning，比较结果一致。
- 触发的 `./scripts/check-compatibility cli` 以及定向 Ruff/mypy 的最终结果见本票外部交付报告。
- 未运行完整离线门禁，未发布正式冻结树验收结论。

## 预期漂移与承接

修改的既有 source/support 路径是 `src/paper_radar/cli.py` 和
`src/paper_radar/feed_pipeline/service.py`；文档变更包括 README、GLOSSARY、
Feed 组合与运行日志 Contract。新增 `stage-b-workflow.md` 是现状组合 Contract，
新增本台账与独立测试不扩大历史范围。scope 白名单审阅、文档分类及必要精确重绑由
#185 唯一集成收口负责，子票不机械重绑旧材料。

后续 B 命令复用 `ExperimentRoot` 的唯一布局与 `require()` 用途守卫。候选清单／固定
元数据视图由 #188 消费 `check_id` 和 `source_check_id`；后续恢复命令需将恢复库与此
固定实验布局正确接线，不改变既有恢复器的 `database.sqlite3` 输出契约。

## 未验证边界

没有真实来源 HTTP、Pi 供给／认证／探测、模型调用、Docling 解析、真实实验根或凭据访问。
未证明当轮 JGR 字段／entry 稳定性、真实完整主摘要、语言来源假设、现场隔离及备份脱网
回放成立；这些 live 与纵向责任继续由 B 明确授权的后续执行承担。
