# #194：依预先选样授权代执行接受工程覆盖

本台账记录 B 的独立 D1 工程覆盖，不进入 A1–A10 回执、固定分母或 required 集合，
`stage_a_verified=false`。全部数据来自 `/tmp` 合成实验、HTTP transport 替身和合成
Pi RPC/供给；没有执行真实来源、真实 Pi、Docling，没有访问真实实验根或凭据。

## 接缝与覆盖

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_accept_cli.py` | 27 | 显式接受、两阶段引用、owner/agent 区分、安全 trace、获准的模型/摘要展开、精确重放、请求冲突、同授权重复拒绝、历史重放；缺成功、test、out_of_scope、版本/修订变化、授权被取代或 Paper 不匹配拒绝；低预测不否定预授权；写前与写事务 visibility；成功预验后的换样/修订竞态；并发同 request 单次提交及历史查询一致快照；决定引用/关联写入故障、提交失败、中断无半提交；UPDATE/DELETE/REPLACE 拒绝；所选根入口日志及只读不追加；冷帮助无外部 I/O；关联损坏/删除的备份拒绝；原根移开的恢复子进程查询 |
| `tests/test_experiment_accept_migrations.py` | 6 | 从非空历史 `b001_selection_authorizations` 升级；加列、建表、触发器、revision 推进故障完整回滚；选样/根保持；普通 Body 决定使用 `b-accept-64hex` 的历史字节、迁移后重放与新决定兼容，不被误分类 |

主接缝是实际 `paper-radar` CLI。服务公共 API 只用于故障/并发及不适合生产消费的
A7 test 成功注入；来源、认证、供给和 Pi 输出均在已确认外部替身接缝。没有替换
Schema、指纹算法、接收器或决定写入算法。恢复使用真实 `restore verify` 子进程及
禁 socket 的 `tests/experiment_accept_recovery_worker.py`，移开原实验根、合成凭据
及安装目录后，恢复前后 trace 相同；不需要原 views、配置文件或认证。

默认回执、trace 和日志不含原文理由、摘要、模型正文或 token。获准的
`--show-agent-content --show-abstract` 另断言模型结构输出和摘要正确出现，避免通过
删除私有业务内容满足隐私。该覆盖不证明现场网络隔离或恢复位置取得新执行许可。

## TDD 与验证边界

可观察 red → green：accept 命令缺失；修订变化被误报为缺 boundary 成功；
前缀分类误把合法普通 Body 决定当作缺关联的代执行。分别实现显式命令、提前报告
冻结版本变化、改用独立持久标记后通过。并发新授权/接受曾使历史查询混合两个读快照，
误报登记损坏；授权、关联和标记改为同一只读快照后通过。

独立精确 Schema 节点为
`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
相关组合包括本票两模块、Schema、head 单一维护者、Body 决定/并发/迁移/恢复、选样迁移、
Screening 编排/恢复 trace、A7 成功适用性/完整性、backup/restore CLI。
定向 Ruff、format、默认 strict mypy 覆盖全部新生产与测试/恢复支撑；CLI 兼容组合
使用预先建立的独占 TMPDIR。最终数量、耗时与提交身份见外部交付报告。
Schema 比较保留既有 Screening 循环外键排序 SAWarning。

本次组件组合 **154 passed / 320.84s**；合并最新 integration 后的最终 D1 两模块、
Schema 和 head 守卫 **35 passed / 176.59s**，其中 D1 为 **27 + 6**。
最终 Body 决定回归 **13 passed / 4.30s**；CLI 兼容组合 **59 passed / 72.67s**
（入口总耗时）。strict mypy **14 文件**通过，定向 Ruff 与 format 检查通过，
`git diff --check` 通过。首次组件组合 149 项通过不代替结构化标记修正后的上述结果。

没有运行完整离线门禁，没有签发任何正式冻结树回执；这些工程结果不表示 B 真实链成立。

## Migration 与固定材料

新增线性 revision `b002_delegated_acceptances`，上一 revision 为
`b001_selection_authorizations`；原迁移字节不变。新增授权→决定关联表及只追加保护；
Body 决定新增可空受控 `delegation_kind`。普通决定为 NULL，原 request hash/事件保持；
只有明确 `stage_b_preselection` 才绑定新请求摘要和 B 关联反向闭包。
自由 request/actor 字符串不作为来源依据。

人工 head 推进白名单：`tests/migration_expectations.py`、十个 scope 的
`MIGRATION_REVISION`、A3 `FORMAT_VERSIONS["backup_database_revision"]`、
`backup/manifest.py::BACKUP_DATABASE_REVISION`、制品/备份两个当前 Contract，及常量和
生产备份声明的两个中央哈希。该常量在全部十组的 S3 敏感确认由 #185/#206 最终树收口
负责。本票不改冻结 fixtures、历史测试/证据、required 或其它中央哈希，不机械重绑
已有及本票 source/support 漂移。

## 下游接口与未验边界

`BodyService.decide_in_connection` 保持原决定权威并允许调用方原子追加关联。
A7 `require_current_success_in_connection` 在同 Connection 重核完整预验成功及权威
PaperFacts 当前映射；`require_success_reference_in_connection` 供历史闭包，不要求当前。
B 复用 `Selections.require_current_in_connection`，不把旧 request 或成功视为执行许可。

`Acceptances(database, data_root).history()` 返回完整已验证关联；
`paper_trace.query_paper_trace` 的 `delegated_acceptances` 为安全投影，明确
「依预先选样授权代执行」，内部 projection 不默认序列化。后续 PDF/样本消费者应继续
引用选样授权与该决定，独立保存所有者 PDF 归属/合法性确认，不能沿用接受授权代替。
新增 B 事实只扩 `experiment.validation.validate_all`；backup 不增加另一套 B 校验。

实际 Feed 字段/主摘要、Pi 认证/生成/参数/OS 隔离与资源、Docling/正文质量、PDF 确认、
Read、报告、暴露导出、现场脱网回放和 NAS 仍未验证。旧 v25 D7 字节绑定漂移与全部
source/support 的最终审阅和 S3 由 #206 承接，不改旧向量摘要。
