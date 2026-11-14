# #198：显式实验 Read 与失败恢复工程覆盖

独立 D1，`stage_a_verified=false`；不进入 A1–A10 回执、固定分母或 required。
只使用 `/tmp` 合成 PDF、HTTP transport、parser worker、cgroup/磁盘与独立 Pi RPC 对端。
waiver、egress 与六项所有者核查均经真实 CLI；没有 mock ReadExecution 或内部准入成功，
没有把 Read 的 test 提交端口标为 pi_rpc。合成对端经实际供给、安装保护、认证 helper、
隔离启动、独立 Read 会话与 v2 接收，是工程路径，不能证明真实模型或 live 准入。

不运行真实来源、Pi、Docling、模型下载、现场资源探测或其他 live 命令；不访问真实实验根、
运行专用 checkout、私有准备单/回执、真实 PDF、模型或凭据。

## 接缝与数量

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_read_owner_basis.py` | 1 | 时钟回退与同 PDF/正文重新冻结的真实 CLI 反例，领取必须引用当前冻结样本的结构化所有者核查，不能按 review 时间选其他样本 |
| `tests/test_experiment_read_logging.py` | 3 | read/retry/reclaim 各自显式所选根 FileSink、入口 run_id/开始/完成、Read claimed/succeeded 安全事件；所有查询不建日志，不泄漏模型内容/Prompt/重试原因/合成凭据 |
| `tests/test_experiment_read_cli.py` | 24 | 七项冷帮助/完整中文帮助；当前样本默认中文 manual 登记，真实合成 RPC 进入 v2；接受结构与逐字 evidence 仅获准私有视图，默认回执/trace/日志无内容；ordinary 拒绝；末次降级、规则身份、三类丢弃计数；精确 request 重放不认证/执行/补后来状态；全库当前输入最新 failed、可见性拒绝、唯一 retry 后继与单 task 继续；选样改变后的旧失败仍可查、旧请求仍可回放且新 retry 拒绝；六种资格/授权/完整帧预算/豁免拒绝且不认证、不领 attempt；认证中外发撤销，ready 原回执可显式恢复；过期 Read 查询/继续均不隐式结算，显式 reclaim 后只用剩余尝试；实际 claim 写事务等待后 egress/选样/冻结修订变化拒领；结构化所有者核查优先于后来未标记 actor，损坏关联拒绝备份；同 PDF 多正文不凭参数猜选；backup/restore verify 子进程与无 SDK/模型冷进程保留两轴、逐字 evidence、用途隔离及文件字节 |

支持：`tests/experiment_read_support.py` 只准备合成外部边界；
`tests/experiment_read_recovery_worker.py` 只读恢复副本，拒绝 SDK、网络和模型子进程。
主接缝是 CLI；服务 API 只用于并发屏障、失联/中断、旧来源/介质故障注入。
恢复真正调用 `restore verify` 子进程；移走原合成根、PDF、模型与认证替身后，
冷进程以标准 `database.sqlite3 + blobs` 路径核验完整闭包、实验可见/普通拒绝、
安全 trace 与私有分析/evidence 均一致，恢复文件前后哈希不变。
该测试守卫不等于 #201 的现场 OS 禁网/原根不可访问证明。

## TDD 与开发验证

首个可观察 red：`experiment read --help` 返回不存在命令；同节点补产品接线后 green。
第二个实测产品 red：同 PDF/正文新冻结后，旧样本核查时间较晚导致领取误引旧核查。
以同 Connection 的当前 B 样本关联限定实际 ReadBasis 选择后 green；旧无 B 关联的 Body 历史保持原选择语义。
继而逐片验证合成 tracer、末次降级、失败/retry/显式执行闭环、拒绝与并发/恢复。
恢复测试的早期 JSON 序列化分别遗漏既有 Pydantic 元数据与 datetime；修订竞态的早期合成
修正请求将字段误填为字符串。它们均修正测试输入/编码，不更改产品契约、旧材料或判定规则。
最终组件组合另实测暴露冷恢复提前导入执行运行时与资格纯依赖问题；
将 Read 执行依赖延迟至实际 run、将既有 Extraction→preflight 依赖延迟至实际 extract，
将 ReadTaskFacts 留在纯资格层，并用最小结构协议消费 Screening 查询，
保留既有 NoRuntime/纯度守卫原字节后定向及完整组合复验。

最终开发选择：

- 完整本票独立 D1 模块，未绑定。
- Read 原任务/资格/租约/执行/恢复，ReadExecution RPC/准入/资源/日志/审计历史，
  ReadQueries、Body facts/review-remediation、eligibility 三模块。
- 独立 Schema 精确节点：`tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
- 先创建本票独占 TMPDIR 后执行 `./scripts/check-compatibility cli`；不调用完整门禁。
- 全部触及 Python（18 个生产文件及 5 个新 tests/support）默认 strict mypy、Ruff、format 与 diff 检查。

最终源码实测：D1 三模块 **28 passed / 664.64s**（24/3/1）；上述组件 **247 passed / 217.40s**，
包括独立 Schema 精确节点，仅既有 Screening 循环外键 SAWarning；CLI 兼容 **59 passed / 81.02s**，
入口总耗时 81.76s。默认 strict mypy、Ruff、format 的全部 23 个触及 Python 与 diff 检查通过。
精确完整节点收集清单、逐模块数量、命令与最终提交身份在外部交付报告；前版本子集不替代最终组合。
完整离线门禁未授权、未运行，不生成正式回执。

## 持久边界与固定范围

不新增 migration；head 保持 `b005_layout_recordings`，未更改 Schema、人工 head、旧 migration、
中央 hash、冻结测试/fixture/向量、required 或历史分母。
Read budgets/tasks/registrations、attempt 的 Body/metadata basis 与 v2 analysis 是唯一持久权威，
不新增 B 的平行任务表、read_requests、第二套 attempt/质量/接收规则或自动名额。
登记/领取扩同 Connection guard；完整 PDF 字节与其他文件 I/O 在业务短写事务外核验。
B validate_all 对已关联 B 样本的领取复核结构化所有者来源，backup 不复制 SQL 校验器；
旧无 B 样本的历史不补标、不提升。

固定 source/support 漂移只记录，不机械重绑；既有三项整对象 trace/workflow 比较及 D7 旧
两项字节失败留 #206 逐项审阅。新增字段、两轴与 MODEL_FAILURE_QUEUE 的 Read 范围
不作为修改旧冻结预期的默许。实际最终 scope 身份、边和路径见外部交付报告。

## 接口与下游

`experiment.reading.Reading.run` 组合 current sample/唯一正文/结构化所有者来源及原 Read 权威。
`task_payload` 和 `registration_receipt` 是安全任务与不可变登记投影。
`analysis_payload(database, data_root, analysis_id, snapshot_id=...)` 是获准私有结构结果、
未核对警告、丢弃计数/规则身份与逐字 evidence 的公共投影；可用于标准恢复路径。
`ReadQueries.axes` 为默认 trace 提供无内容的正文/配置两轴，不借 AGENT_CONTENT 权限。
ReadTasks.failure_facts 是 MODEL_FAILURE_QUEUE 的 Read 最小事实，evaluate_paper 是组合规则权威。

#199 复用原 ReadAnalysis/ReadQueries 及上述私有投影固定 report 成员/渲染；不能消费 test 或将
实验结果加入普通报告，也不能把完整 Prompt、原始候选/被丢弃陈述加入默认诊断。
#201 承接现场隔离回放；#206 承接固定材料/S3与最终集成门禁；真实样本及所有者核查、
Pi/模型/Docling、受限内容质量、日报、暴露、NAS 和现场脱网链均未验证，由主会话独占后续。
