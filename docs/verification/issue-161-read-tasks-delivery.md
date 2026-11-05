# Read 显式任务、接收与恢复独立覆盖

依据 [#161](https://github.com/MeteoBoy4/PaperRadar/issues/161) 和
[#155 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155)。主 seam 是真实
BodyService、JGRMetadata、FulltextArtifacts、StageInput、ReadTasks 与 backup/restore
组合；只在 HTTP、parser 和外部模型执行边界使用可控替身。
SQL/事务/进程与时钟故障用于观察持久闭包，不取代公共查询。
本台账为独立 D1，未加入 A1–A10 成员、固定分母或 required，stage_a_verified=false。

## 模块与节点

| 模块 | 节点 | 可观察保证 |
| --- | ---: | --- |
| tests/test_read_tasks.py | 5 | 持久重复登记与预算、首次指针拒绝/唯一安全修正/末次丢弃、评分理由不降级、全空下限、候选extra序号拒绝 |
| tests/test_read_tasks_leases.py | 6 | 600秒到期不退款/显式未知结算/旧token失权、续租与伪ordinal拒绝、失败retry唯一后继及新代1、竞争领取、成功不能重开/竞争候选拒绝、精确并发提交幂等 |
| tests/test_read_tasks_preconditions.py | 11 | 实际metadata/accepted/样本/质量拒绝、领取重核决定、A→B→A/语言/标签预算、历史配置、实际完整帧超额无任务、preclaim拒绝无attempt、实验可见普通拒绝、同Connection未提交routes缺项、换PDF拒绝 |
| tests/test_read_tasks_execution.py | 5 | test入口不能声明Pi来源、专用Pi审计绑定持久供给与历史模型、模型不符失败、NullSink/安全日志、中断保留租约 |
| tests/test_read_tasks_recovery.py | 18 | 原始候选+Context+ordinal重算、序号/丢弃/输出/evidence/规则/payload/登记缺失拒绝、提交故障无半分析、无extra异地冷进程保留代际/未结算租约/来源、未知诊断策略保留、v1合成历史、restore传播unsupported_rule_version、历史资格不因新metadata/决定/PDF/样本变化损坏、三类历史依据缺失拒绝 |
| tests/test_read_tasks_migrations.py | 3 | 非空body01升级、DDL与版本提交故障原子回滚、旧行保持与外键 |
| 合计 | 48 | 独立未绑定 D1 |

支撑：tests/read_tasks_support.py、tests/read_tasks_recovery_worker.py、与正文执行共享的tests/no_extra_runtime.py。
基础冷进程真实检查未安装 docling/docling-core/torch，禁止原根、网络与外部进程，
重建服务后只读核对完整历史与证据；未通过禁导入假装缺少 extra。

## 故事与边界

| 父规格故事 | 本票负责及下一责任 |
| --- | --- |
| 1–17 | 已交付 Body PDF/前置/提取与质量组合由本票实际消费；真实SDK/模型/限额由正文执行实现，真实核查与smoke仍由B及用户操作承担 |
| 18–22 | 持久三元组、历史配置、语言与显式新输入进入Read；完整正文/配置两轴查询由后续查询服务承接，不自动重跑 |
| 23–25 | 同库输入预算、600秒租约、唯一retry、领取前Context和完整帧最坏修正预算 |
| 26 | 本票仅提供独立外部执行端口；实际Pi新会话/准入/进程组回收由Pi组合承担 |
| 27–29 | 唯一v2接收、原始候选/策略/序号/三规则/诊断/丢弃/证据原子保存；精确幂等与故障拒绝 |
| 30–31 | 无extra异地冷恢复、旧代/未结算预算/唯一成功/实验普通拒绝保持；完整真实链与NAS仍归后续验收 |
| 32–34 | 真实共享资格组合、只读历史/分析/evidence、默认NullSink与安全事件、本D1台账和精确范围登记 |

Read上游来源来自决定所引用的历史Screening成功；Read自身test/pi_rpc来源独立判断。
仅有题名/摘要不能替代元数据路线完成。纯人工accepted无引用仍为unknown并拒绝。
formal_gate不由本票制造，实验结果不能被普通生产消费。

本机同根Read显式执行通过独立execution_resource串行；等待先于领取。
Pi组合须在认证前取得资源并持有到清理，低层claim/submit只负责短事务所有权。
不改变Docling锁含义，不引入自动队列、quota或产品CLI。

## 迁移与登记

migration 2 为 body02_read_tasks，线性下接 body01_persistence；新增八张Read表，
并为body_extraction_attempts新增nullable executor_audit_json供正文执行审计使用，旧NULL保留。
该列的DTO/写入/审计语义由正文执行实现持有。本spec没有第三个migration，既有节点保持原字节。

人工head常量、十scope、A3 backup_database_revision、生产备份head及两份契约同步。
中央hash仅对白名单五个实际变化更新：migration_expectations、backup/manifest、backup/service、
storage/artifacts、storage/artifact_repository；最后两项为Read实际消费者所需同Connection只读seam。
新read-tasks Contract沿未知新文档按固定材料处理，不扩live分类或修改冻结分类测试；
本票不制造人工确认。

继承Read输入实现的9个实际路径、15条登记hash_drift保持；既有86条confirmation_required
继续保留；没有新增分类候选。最终绑定身份、旧新hash、分类和全部下游组
由外置白名单与审计报告提供。最终S3与正式门禁归集成收口，不把子树检查当最终树证据。
A9根v1实现、15模块/560节点/格式和A8旧request向量保持原字节；scope仅迁移窄例外。

## 验证与未验证

开发使用独立磁盘环境和 uv run --offline --locked 的相关pytest、Ruff/format/mypy及
触发的CLI兼容组合；实际数量、耗时与最终提交身份记在外部完成报告。
测试只有合成材料和离线替身，不证明真实Pi、Docling保真/公式覆盖、现场EXP-2、
四刊正式质量、B真实闭环、正常生产Read、正式校准、NAS或完整阶段A。
没有完整check-offline、live、产品CLI、push或自动accepted。
