# Body 前置事实与持久提取独立覆盖

依据 [#158](https://github.com/MeteoBoy4/PaperRadar/issues/158)、父规格 [#155](https://github.com/MeteoBoy4/PaperRadar/issues/155)
最终评论口径。测试通过公共 BodyService、ArtifactStore、FulltextArtifacts、ScreeningTasks 和
备份/恢复入口，只有外部 canonical parser 使用合成替身；SQL/进程故障用于验证提交及恢复边界。
本页是新增 D1 台账，不加入 A1–A10 成员、固定分母或 required 集合，stage_a_verified=false。

## 独立模块与数量

| 模块 | 节点 | 可观察行为 |
| --- | ---: | --- |
| tests/test_body_facts.py | 13 | 根登记幂等/冲突、PDF 追加选择与重启、有效人工决定及旧依据、四种专用来源拒绝、并发请求冲突、冻结样本与换 PDF、真实 pi_rpc 审计来源/混合 test 优先、同 Connection 未提交视图且禁止另开连接 |
| tests/test_body_extraction.py | 21 | 真实四角色制品、唯一成功复用、跨论文/重启两次预算、人工三元组/永久否决、完整闭包、无文本层、partial 无质量、预检不领取、四类精确自动失败、五个质量 DTO 矛盾、后端换代独立预算、登记 PDF 哈希篡改在领取/parser 前拒绝 |
| tests/test_body_concurrency.py | 5 | 真实 flock 等待后复用、换 PDF 后重核、SIGINT 等待无事实、SIGKILL 持有者未知结算不退款、symlink 锁拒绝 |
| tests/test_body_recovery.py | 8 | 完整业务冷进程异地恢复、原路径审计屏蔽且无 docling/docling-core/torch、锁误入批次 unexpected_entry、三种业务篡改 registration_invalid、成功事务故障无半成功、PDF/样本追加序号缺口拒绝 |
| tests/test_body_migrations.py | 3 | 非空 feed07 升级及旧行保持、DDL/版本写入故障原子回滚、再升级与服务读取 |
| tests/test_body_privacy.py | 1 | 默认 NullSink 静默、显式 body 安全日志、内容/路径/核查者不进入事件 |
| 合计 | 51 | 独立未绑定 D1 |

支撑文件为 tests/body_support.py、tests/body_recovery_worker.py；无固定用例数。
服务与规范制品真实协作，合成 pi_rpc 审计没有调用真实 Pi，不作为生产执行真实性证明。

## 父规格 34 故事承接

| 故事 | 本票覆盖或明确下一责任 |
| --- | --- |
| 1 | facts：明确 paper/version 与文件校验；不能离线证明内容属于该版本 |
| 2 | 父票最终收缩为人工明确关联；DOI 检测移出 Body |
| 3 | facts/recovery：不同 PDF 保留与追加当前选择 |
| 4–7 | 本票注入 parser、预检在领取前；真实 SDK 延迟导入/模型/限额由 #159，真实 smoke 由 #164 |
| 8–11 | 本票 extraction 经真实规范制品链；canonical/normalize 语义主覆盖见 #156，真实 SDK 保真由 #159/#164 |
| 12 | 定位沿用 #156；PDF 裁切渲染移交 B/F，不新增角色 |
| 13 | 自动失败精确值与质量 DTO 已覆盖；受限输出警告见 #157，持久接收由 #161 |
| 14 | extraction/facts：永久失败或缺人工不得取得本票前置资格；本票不调用 Read |
| 15–16 | extraction/concurrency/recovery：两次全库预算、失败资源审计、失联不退款；真实进程资源上限由 #159 |
| 17 | extraction/facts：两层质量、普通消费拒绝实验；formal_gate 归 F |
| 18 | extraction/recovery：三元组绑定；Read 输入/分析分别由 #160/#161 |
| 19–21 | Read 语言、模型、书目与配置轴由 #160/#163 |
| 22 | facts 保存当前 PDF 事件和换样拒绝；分析正文轴由 #163 |
| 23–24 | 本票只覆盖 extraction 预算；Read 预算/租约/retry 由 #161 |
| 25 | 调用前输入预算由 #160/#162 |
| 26 | 独立 Pi Read 会话由 #162，真实 Live 另验 |
| 27–29 | v2 纯接收见 #157；Read 分析原子保存与证据闭包由 #161 |
| 30 | recovery：PDF/正文/前置/预算/质量冷进程异地闭包；Read 业务恢复与全链由 #161/#165 |
| 31 | facts/recovery：实验根普通消费拒绝在恢复后保持；分析查询由 #163/#165 |
| 32 | facts：共享决定与可见性、同 Connection 前置；完整领取/查询由 #161/#163 |
| 33 | privacy：默认静默与安全日志；模型执行日志边界由 #159/#162 |
| 34 | 本台账与精确登记漂移记录；最终集成 S3/审阅/完整门禁归 #165 |

## 迁移、登记与验证边界

本票 migration 1 为 body01_persistence，下接 feed07_parser_versions，十张表仅覆盖前置与提取；
Read 任务/analysis migration 2 由 #161 线性承接，不创建第三个 head。
既有 migration 原字节保留。人工 head 预期、十组 scope revision、A3 备份格式声明、
生产备份 head 和两份 Contract 同步；中央哈希仅更新 migration_expectations、backup/manifest、
backup/service 三个实际消费者。runtime_logging/schema 未被历史 scope 单独登记。
A9 v1 源码、15 测试模块、固定计数与规则格式零字节；A9 scope 只作已授权的迁移窄例外。

只读 scope 审计的所有文件登记匹配，无 hash_drift；十组迁移登记和人工预期仍需最终集成树 S3。
子票不制造人工确认，也不把其 confirmation_required 当作已通过。
相同三文件旧新 SHA、具体组及候选由本次外部审计/白名单记录提供；merge 后按新树重审，
不继承旧工作树身份或回执。新增能力不机械扩入旧组消费闭包。

开发验证使用独立磁盘 UV_PROJECT_ENVIRONMENT 与 uv run --offline --locked；临时测试根在 /tmp。
相关 pytest、触发的 CLI 兼容组合与 Ruff/mypy 只证明相应工程边界。
未运行完整离线门禁或 live；真实 Docling 工程 smoke 由 #164 的用户操作完成，
F 四刊质量/资源、B 真实流程、Pi Cwd/Live、正式校准、正常生产 Read 与 NAS 均未获证明。
