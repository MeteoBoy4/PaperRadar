# #195：PDF 归属确认、附加与样本冻结工程覆盖

独立 D1 工程覆盖，`stage_a_verified=false`；不进入 A1–A10 回执、固定分母或 required。
材料仅为 `/tmp` 合成实验根、合成 PDF、HTTP transport 与 Pi 合成供给/RPC、受控时钟及
文件系统/数据库故障。未访问真实实验根、运行专用 checkout、私有研究材料或凭据。

## 接缝与覆盖

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_pdf_cli.py` | 30 | 独立 owner 确认与 agent 录入、接受关联、PDF/确认/样本安全 trace、日志装配及只读不追加；冷帮助无 I/O；缺确认/接受、错误签名/体积/哈希/归属/录入者、冻结修订变化拒绝；附件/样本/关联写入故障与中断全回滚、保留确认并按原 request 续办；更换 PDF 与当前样本重判，Screening 指纹/预算不变；三次写前 visibility；原根及材料移走后的冷恢复、前后库/blob 不变；确认/关联/标记/理由损坏的备份拒绝；并发同 request 单附件/单样本；异内容 request 冲突；PDF 发布期间换样/修订竞态；并发确认与样本查询同快照；新增两表 UPDATE/DELETE/REPLACE 拒绝 |
| `tests/test_experiment_pdf_migrations.py` | 6 | 非空 `b002_delegated_acceptances` 库的真实升级；确认表、附件加列、样本关联表、触发器与 revision 更新故障原子回滚；保留选样/接受/旧 Body PDF 字节和重放，升级后可显式确认并通过 Body 验证 |

主接缝为真实 CLI；服务只用于故障/并发注入和原有 Body 事实的受控变化。
文件系统竞态在真实 blob hard-link 发布边界注入，模型与 HTTP 均使用已批准外部替身。
恢复用实际 `restore verify` 子进程和 `tests/experiment_pdf_recovery_worker.py` 冷查询；
原合成实验根、凭据、供给、材料目录及输入 PDF 移走后，恢复 trace 与之前相同，
所有恢复文件哈希前后相同；不需要原 config/views/logs。
这不构成现场 OS 禁网、原位置不可读或真实 PDF 保真证明。

默认回执/trace/日志不含原文理由、摘要、PDF 内容、输入文件路径、原始响应或 token。
原理由仍正确保存在 Body 私有样本事实并与选样原文核验，安全投影只引用 selection。
原论文与模型内容的获准展开由接受/trace 消费者回归保持，不以清空私有业务内容满足隐私。

## TDD 与验证

可观察 red → green：`attach-pdf` 不存在；更换 PDF 时缺少公共当前样本核验接口；
并发新确认/关联使旧样本查询混读快照而抛 `StopIteration`。分别实现显式命令、
公共样本核验与同一只读快照的核验/投影后通过。

独立精确 Schema 节点：
`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
当前合并树已包含 `root.data_root=root/data` 的供给布局修复，数据库路径不变。
相关验证包括本票两 D1 模块、Schema/head 守卫、Body 事实/迁移/人工版式故障、
代执行接受/迁移/trace/恢复回归及触发的 `check-compatibility cli`，使用本票独占临时根。
默认 strict mypy 覆盖全部触及生产、迁移、scope、中央登记与新测试/support；
Ruff/format/diff 检查及最终运行数量、耗时、提交身份见同次外部交付报告。
Schema 比较保留已有 Screening 循环外键排序 SAWarning。

合入最新 integration 的组件组合 **86 passed / 582.07s**；同快照修复后的并发、发布期
换样/修订及冷恢复 **5 passed / 82.30s**。最终本票 D1、Schema 与 head 守卫
**38 passed / 360.06s**，其中独立 D1 为 **30 + 6**；CLI 兼容组合
**59 passed / 84.40s**（入口总耗时 85.12s）。默认 strict mypy **24 文件**、
定向 Ruff、format（24 文件）及 `git diff --check` 均通过。

未运行完整离线门禁，未生成正式验收回执；旧 v25 D7 两项字节漂移保留给 #206，
没有改旧向量或冻结测试/fixture 来消除漂移。

## Migration 与固定材料

新增线性 `b003_pdf_confirmations`，父节点 `b002_delegated_acceptances`；既有节点原字节不变。
新增 `experiment_pdf_confirmations`、`experiment_frozen_samples` 及只追加触发器；
`body_pdfs.confirmation_id` 为可空外键，旧附件为空，普通同形请求字符串不推断确认。
Body 新 Connection 接缝由原 API 复用，保留旧请求摘要；新确认标记加入新请求摘要。

手工 head 推进白名单：`tests/migration_expectations.py`、十 scope 的 `MIGRATION_REVISION`、
A3 `FORMAT_VERSIONS["backup_database_revision"]`、生产备份声明与两个当前 Contract。
仅更新这两个声明的中央哈希：

- `tests/migration_expectations.py`：`e7eda9085c91045665005ce967317cd5a553e361345648cfc974f76196f7c13f` → `3d70f9b8a9d61cb6a01bd0bc1a66772968071614b9d2781b7663f54657a37058`。
- `src/paper_radar/backup/manifest.py`：`ac02c6d132b8ca5f7a7c04c16a1a56d05a31640bc7f24866f21fd6ecdd2ede46` → `4e20c76e16a8dba11c70f5a3809586d230be2ed4ce140c6252ddc262a1801b30`。

全部十组的 S3 人工确认与最终 source/support 精确重绑由 #185/#206 收口。
本票不扩 required、不减固定分母、不重写旧证据、不机械重绑其它中央哈希。

## 下游接口与未验证边界

`PdfSamples(database, data_root).history()/samples()` 返回完整核验历史，允许只确认未附加的
可续办状态；不要求历史记录仍当前。B validation 唯一聚合扩展了此闭包，backup 服务未另写规则。
`query_paper_trace(...).safe_payload()` 包含安全 `pdfs/pdf_confirmations/frozen_samples`。

正文/版式/Read 产品入口先调用 `require_current_sample(paper_id)`，取得 `FrozenSample` 的
选样/接受/确认、附件/样本、Feed/发现/source_check、PDF SHA-256、Paper/版本/修订引用；
在领取短事务内调用 `require_current_sample_in_connection(connection, validated_sample)`
重核当前性，无文件 I/O。它不提供执行来源、配置、外发、资源、正文质量或六项核查许可；
下游仍消费 Body/Read/资源各自权威。更换 PDF 保留旧样本历史，最新样本不匹配当前 PDF 即拒绝。

真实 PDF 所有者确认、Feed、Pi 认证/生成/参数/OS 隔离、Docling/正文质量与峰值、
六项人工版式核查、Read、报告、暴露导出、现场脱网回放及 NAS 均未验证。
