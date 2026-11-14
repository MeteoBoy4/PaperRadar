# #197：六项版式对照与所有者核查工程覆盖

独立 D1，`stage_a_verified=false`；不进入 A1–A10 回执、固定分母或 required。
仅 `/tmp` 合成 PDF、HTTP transport、Pi RPC、parser worker、cgroup／磁盘替身；
实际 PDFium／Pillow 渲染也只消费本票构造的 PDF（已知色块、cropbox、页旋转）。
不访问真实实验根、运行专用 checkout、私有准备单、真实 PDF、模型或凭据；
不执行真实来源、Pi、Docling、主机资源探测或其他 live 命令。

## 接缝与数量

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_layout_cli.py` | 35 | 冷帮助禁网络／SQLite／建目录；六项独立缺项拒绝且无根写入；所有者角色及六个显式布尔输入，passed 与六项一致；自动／人工质量合成；永久否决不被之后通过覆盖；结构区分 owner reviewer 与 agent recorder；私有说明不出终端／trace／日志；文件日志执行入口守卫；六项 HTML 对照及逐字 evidence／charspan／bbox／orig；真实合成 PDF 两原点、cropbox 与 90° 旋转裁切的尺寸／已知像素；页眉去留、标题层级、公式／表格／不可靠字与生成候选分离；只读业务且材料确定性重建；缺依赖／错身份／链接拒绝；visibility 写前守卫；Body 核查与代录关联写故障整组回滚；修订／换样并发后重核；同 PDF 多成功身份不猜最新；record／关联／所有者／原说明损坏的备份拒绝；新表 UPDATE／DELETE／REPLACE 拒绝；标准 backup + restore verify 子进程与无 SDK 冷进程逐字恢复 |
| `tests/test_experiment_layout_migrations.py` | 6 | 非空 `b004_bounded_extractions` 真升级，保留旧 Body review 与原请求摘要（actor／request 前缀不产生 B 来源）；ALTER／新表／触发器／revision 故障原子回滚；升级后完整回查、FK 空及新核查可写；缺库故障下旧 wrapper 仍先校验输入 |

主接缝为 CLI；服务 API 仅用于 SQL 故障注入与写事务前并发屏障。
外部渲染器替身用于独立观察文字材料；真正裁切由已锁 PDFium/Pillow 对纯合成 PDF
校核，未执行 Docling。六份材料没有预填通过结论，生成候选不进入抽样源字符。

恢复实际执行 `restore verify` 子进程及新的 `experiment_layout_recovery_worker`。
原合成根、输入 PDF、模型和认证替身目录移走后，完整安全 trace 语义一致，
`e000002` 源切片逐字一致，恢复文件哈希前后不变，冷进程拒绝网络与 SDK 导入。
该守卫证明本票持久消费边界，不是现场 OS 隔离或真实恢复验收。

## TDD 与开发验证

可观察 red → green：新命令缺失；所有者核查服务缺失；六类材料模块缺失；
真实渲染中 PDFium page 不支持 context manager；CLI 折叠冻结修订专用原因；
同事务扩展使旧 wrapper 错在开库后才校验六项输入。分别补 CLI、同事务记录与追加关联、
持久成员材料投影及显式 `closing` 句柄生命周期后通过。合成渲染准备曾沿用旧签名字节的
默认参数，改为显式经 PDF 产品 CLI 登记本票真实结构的合成 PDF 后校核坐标与像素。

独立 Schema 精确节点：
`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
验证包括两个新 D1 模块、Body facts/migrations/review-remediation/concurrency、
人工 head 守卫、精选 `check-compatibility cli` 与所有触及 Python 的默认 strict mypy、
Ruff、format 和 diff 检查；实际逐次数量、耗时和 SHA 见外部交付报告。
完整离线门禁未获授权，未运行，不产生正式回执。

## Migration 与固定范围

新增 `b005_layout_recordings`，父节点 `b004_bounded_extractions`，线性 head。
`body_layout_reviews` 追加可空结构标记；旧 review 不回填、不改请求摘要。
`experiment_layout_recordings` 为核查／样本／论文与所有者／代录者的规范追加关联，
和 Body review 同事务提交；两边任一失败没有半条业务结论。
Body 原 wrapper 保持原行为；产品同 Connection 接缝支持可选空说明。
B 新事实仅接 `experiment.validation.validate_all`，backup 不复制校验器；
标准恢复继续 `database.sqlite3 + blobs`，普通库显式根和实验 `root/data` 布局保持。

人工 head 白名单：`tests/migration_expectations.py`、十 scope 的 `MIGRATION_REVISION`、
A3 `backup_database_revision`、生产 `BACKUP_DATABASE_REVISION`、两个当前存储 Contract，
仅重算人工预期与生产备份声明的两个中央 hash。
旧 migration、冻结 fixture、历史测试、冻结负例、required 与历史分母不变。
其他 source/support 漂移及十组敏感 S3 精确确认交 #206；旧三项 trace/workflow 比较与
旧 D7 两项字节向量仍由 #206 具体审阅，本票不改历史材料或策略。

## 边界与下游

`LayoutReviews(database, data_root).history(paper_id=None)` 提供完整核验的安全历史，
所有者说明不包含在默认投影；trace `safe_payload().layout_reviews` 复用该接口。
Read 继续消费 Body 权威 `experiment_document_gate` 与永久 `failed(layout_review)`；
资源执行和代录关联均不独立授予 Read 资格。同 PDF 多成功身份保留歧义。

未验证真实 PDF 保真、所有者六项真实判断、实际主机资源、Pi／Docling、Read、日报、
暴露、现场脱网隔离或 NAS。#198 承接显式 Read 组合，#201 承接现场隔离恢复产品，
#206 承接最终组合／S3 与完整门禁；真实材料核查由主会话与所有者完成。
