# #196：有界显式提取工程覆盖

独立 D1，`stage_a_verified=false`；不进入 A1–A10 回执、固定分母或 required。
全部材料为 `/tmp` 合成 PDF、模型部署、cgroup/meminfo/mountinfo、磁盘资源事实，
HTTP transport、Pi 合成 RPC 与 parser worker 替身；不执行真实 Docling、现场资源探测，
不访问真实实验根、运行专用 checkout、私有研究材料或真实凭据。

## 接缝与数量

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_extract_cli.py` | 35 | 冷帮助无网络／SQLite／目录；当前 cgroup 上限、swap、歧义／遍历／链接／挂载拒绝且无领取；实际 DoclingParser 部署哈希及临时快照配合 worker 替身，显式超时／线程／32 GiB RLIMIT_AS；低主机内存与未知／坏编码只披露；组峰值未知／历史口径与 worker 分列；缓存不新转换／不回写旧峰值；C1 无题名／DOI／摘要输入；无文本／质量／资源／超时停止、两次预算和永久失败，不调用 Read；真正自动质量失败保存制品与精确原因；模型／磁盘／运行参数预检及预检后修订变化不领；实际临时根 flock 等待后资源变化／换样不领；B 执行与 Body claim/outcome 写故障原子回滚、不退款；两新表 UPDATE/DELETE/REPLACE 拒绝；安全 trace／日志／错误；新进程无原根／模型／PDF仍重建 trace 和逐字 evidence；损坏闭包备份拒绝 |
| `tests/test_experiment_extract_migrations.py` | 5 | 非空 `b003_pdf_confirmations` 真升级，B 执行表／峰值表／触发器／revision 故障原子回滚；原 PDF 确认和冻结样本不变，升级后 FK 完整 |

主接缝为 CLI；服务只用于等待根锁的并发及故障注入。外部运行探测、worker、磁盘
资源均替身，模型声明／哈希／快照与 Body 质量、预算、制品发布、备份权威为真实代码。
恢复实际运行 `restore verify` 子进程及 `tests/experiment_extract_recovery_worker.py`；
原合成根、模型和输入 PDF 移走后，安全 trace 字节语义一致，`e000002` 的 orig 切片
逐字相同，恢复文件哈希前后不变。此处禁 socket 守卫不构成现场 OS 隔离证明。

## TDD 与验证

可观察 red → green：缺少 `extract` 命令；缺少资源执行模块；未形成 canonical 的永久
转换失败被误披露为已评估自动质量失败；坏编码 MemAvailable 被误当作 cgroup 拒绝。
分别补显式入口、领取前资源核验／事实闭包、质量 unknown 与可选主机披露后通过。
质量负例的源字符保持原 charspan 长度，独立区分字符完整性和 evidence 回放失败。

独立 Schema 精确节点：
`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
开发期验证包括本票两个 D1 模块、Body facts/migrations/review-remediation/concurrency、
人工 head 守卫以及 `check-compatibility cli`。默认 strict mypy、Ruff、format 覆盖
全部 26 个触及 Python 文件，包含生产、migration、scope、中央登记、新测试/support。
每次运行数量、耗时、最终提交身份在同次外部交付报告；Schema 仅有旧 Screening 循环
外键排序 SAWarning。完整离线门禁未获授权，未运行，不产生正式回执。

## Migration 与固定材料

新增线性 `b004_bounded_extractions`，父节点 `b003_pdf_confirmations`；旧迁移原字节不变。
`experiment_extractions` 与 Body claim 同事务，`experiment_extraction_peaks` 与 outcome
同事务；新表只追加。worker 峰值仍在原 attempt，组峰值明确历史 scope，未知不填零。
普通 Body 调用／旧 attempt 不增加资源事实，缓存不补写旧转换的保障。
新增事实只扩唯一 `experiment.validation.validate_all`，备份不复制验证器。

人工 head 白名单：`tests/migration_expectations.py`、十 scope 的 `MIGRATION_REVISION`、
A3 `backup_database_revision`、生产 `BACKUP_DATABASE_REVISION`、两个当前存储 Contract，
仅重算人工预期和生产备份声明的两个中央 hash。其余 source/support 漂移与所有十组
S3 精确人工确认交 #206；不改旧三项 trace workflow 固定比较和旧 D7 两项向量，
不改冻结材料／策略／required，也不扩大历史结论。

## 真实边界与后续消费

没有证明实际宿主 cgroup 限制／峰值、真实 OOM 归因、Docling 保真或真实资源容量，
没有执行现场 Feed／Pi／Docling／六项版式／Read／日报／脱网隔离／NAS。
R3 主会话独占真实 Docling 与逐文档验收；F 承接四刊、复杂版式及通用资源门槛。
后续版式消费者继续使用 `PdfSamples` 双层当前样本 guard，`BodyService.current_body`
保留缺失／歧义，`FulltextArtifacts` 按三元组校验／回放；B 资源记录不授予 Read 资格。
