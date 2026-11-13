# #188：候选事实快照与私有视图工程覆盖

本台账记录 B 的独立 D1 工程覆盖，不进入 A1–A10 回执、固定分母或 required 集合，
`stage_a_verified=false`。不新增 Alembic migration，不改表定义、旧冻结测试或 fixture。

## 覆盖与接缝

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_candidates_cli.py` | 18 | CLI 七成员全量与完整摘要、私有内容及安全终端、同依据身份及重建字节稳定、补摘要产生新身份并保留旧修订、304 原成员、Feed 重排、缺主摘要、伪造正文或就绪标记拒绝、参数错误、禁外部 I/O 中文帮助、每次调用共享 visibility、只读日志不变、unknown/production 根拒绝、链接越界拒绝、实际备份恢复闭包、强冲突条目保留、截断摘要阻断、登记及文件发布故障恢复 |

主接缝是 CLI；准备数据和回查使用组件公共接口。来源只使用 `MockTransport`，
退避使用注入时钟，不调用模型。共享 visibility 的观察只验证本票明确要求的接线；
SQL 与文件发布仅在故障边界注入。既有执行日志入口守卫不变，本票只读投影不新增日志。

TDD red：缺少 `candidates` 命令；伪造摘要载荷可以被渲染；伪造元数据就绪标记可以被渲染。
对应修正后均通过。完整题名／摘要在私有快照和 Markdown 中存在，与终端／日志不出现
私有文本分别断言，不以全局抹去正文通过隐私检查。

## 验证与边界

- 相关回归包含本 D1 模块、实验 Feed CLI、制品 Contract／存储、Feed 组合与元数据。
- CLI 注册与导入链触发 `./scripts/check-compatibility cli`；定向 Ruff/mypy 与最终数量
  见本票外部交付报告。没有运行完整离线门禁，没有发布正式冻结树验收结论。
- 备份测试经真实 `backup create` 和 `restore verify` 得到已校验业务闭包，再复制数据库
  和 blobs 到独立 working-copy，以实验命令布局重建相同视图。原恢复 manifest 树保持
  原样；该用例不证明转换布局后仍符合恢复 manifest、不证明隔离脱网子进程成立。
  `database.sqlite3` 与 `paper-radar.sqlite3` 以及独立输出区的公共协调留 #201。

## 预期漂移与后续责任

既有 source/support 漂移为 `src/paper_radar/experiment/cli.py` 与
`src/paper_radar/storage/artifact_contract.py`；新增
`src/paper_radar/experiment/candidates.py` 和独立 D1 测试。
README、GLOSSARY、制品与 B 工作流 Contract 同步当前能力。
scope 白名单审阅及必要重绑由 #185 唯一集成收口负责，本票不机械重绑历史材料。

#190 消费 `CandidateViews.load(view_id)` 固定成员及 `revision/current_revision`、
`metadata.request_key`、完整字段来源、语言与冲突；选样前在短事务重查当前依据，
不能把旧视图的就绪状态当当前许可。`load_candidate_snapshot(database, data_root, view_id)`
与 `validate_candidate_snapshots(database, data_root)` 支持显式数据库文件名，供唯一 B
备份校验聚合接入；本票不另向共享备份服务挂第二个聚合。

没有真实来源 HTTP、Pi 供给／认证／探测、模型调用、Docling 解析、真实实验根或凭据访问。
未证明真实 Feed 字段与 entry 稳定、摘要完整、语言来源假设或现场恢复成立；这些 live
与纵向验收责任继续留 B 后续明确授权执行。
