# #193：Screening 失败恢复与组合追踪工程覆盖

本台账记录 B 独立 D1，`stage_a_verified=false`，不进入 A1–A10 历史回执、固定分母
或 required 集合。全部业务材料位于 `/tmp` 合成根；不执行 live、不访问真实实验根
或真实凭据。合成 Pi/HTTP 证据不授予现场执行或正式消费资格。

## 接缝与覆盖

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_screening_recovery_trace_cli.py` | 23 | 全库当前失败及旧指纹历史；retryable/第二次 lease_expired 不入队；唯一父任务、双阶段歧义与显式 stage；非空 request/reason/actor；精确重放优先于后续代际和当前事实变化，异内容拒绝；写前 visibility 拒绝不增代；显式 reclaim→retry→执行后继→continue-value；组合根/Feed/语言/授权/父链/任务与共享资格；历史制品适用性；默认摘要/Agent 内容裁剪与获准展开、隐藏拒绝；show/trace 根中性和空隐藏集合实际求值；冷帮助禁 I/O；真实备份/恢复子进程的失败列表、父链与 trace 相等，第二次过期仍未结算 |

CLI 是主要接缝；公开 A7 API 只用于合成尝试失败、过期/未知结算及历史准备。
跨票执行组合复用已确认的合成 HTTP transport、Pi 供给和 RPC 对端，不替换
PiExecution.run_attempt、内部准入、任务领取或成功接收；waiver/外发授权经真实 CLI。
恢复运行真实 `restore verify` 子进程，再移开原数据库/制品根，在禁 socket 的冷进程
通过真实 CLI 读取固定 `database.sqlite3` 副本；连续查询结果相同，不结算或退款。

## TDD 与验证

可观察 red → green：`screening` 命令不存在；组合追踪公共模块不存在；
显式 `--show-agent-content` 尚未注册；历史成功最初被误报 screening_absent，
回归期望 screening_historical 后修复为消费 A7 原适用性。
冷帮助回归暴露任务包 eager import 提前引入 SQLAlchemy，改用轻量命令壳后通过。

相关子集覆盖新 D1、既有 Screening 执行/选样、A7 查询/retry/attempt、共享资格、
论文 CLI、Feed 组合、备份恢复与任务日志；触发 `check-compatibility cli`。
最终严格 mypy 覆盖本次全部生产文件和新测试，默认 follow-imports；Ruff、format 与
`git diff --check`。实际命令、数量与退出码见外部交付报告；不运行完整离线门禁。

## 持久化与接口

不新增 migration、表、预算模型或队列表，既有 head 保持
`b001_selection_authorizations`。不改冻结测试、fixture、D7 向量或 required 分母。

- `ScreeningTasks.failures(snapshot_id=...)` 在 A7 内枚举全库任务主体，并逐项复用原 query。
- `ScreeningTasks.retry_failed(...)` 唯一定位当前失败，复用 retry 原子权威；精确重放优先，
  新后继同写事务检查 visibility。低层 retry 的第二次过期原子回收能力保持。
- `ScreeningTaskFacts.from_queries` 和共享 evaluate_paper 提供模型失败队列的 partial 支持，
  仅为 Screening 当前指纹最新代际 failed；其他 partial/deferred 含义保持。
- `paper_radar.paper_trace.query_paper_trace` 返回 PaperWorkflowTrace；safe_payload 输出安全
  组件事实及共享概念结果/原因/范围，内部 projection 不默认转储。
  后续 #194 可在此 DTO 增加决定与授权关联；Body/Read/报告事实由后续票逐步装配。
- paper 命令实际调用 visibility，显式快照查询任务；只有显式且获准才由 A7 load_success
  读取结构输出，Profile/Prompt/原始响应从不进入诊断输出。

## 预期漂移与后续责任

source/support 漂移路径为：`src/paper_radar/cli.py`、`papers/cli.py`、
`eligibility/{__init__,models,rules}.py`、`screening_tasks/{errors,query,query_models,retry,service}.py`；
新增 `paper_trace.py`、`screening_cli.py`、独立 D1 及本台账不纳入旧组。
README/GLOSSARY 与现状 Contract 同步公共边界；组件规则与组合路径各有唯一归属。
不机械重绑；#206 负责最终树漂移/S3/最终策略与向量审阅。既有 D7 旧 v25 两项失败
由前置变更引起，本票不放宽运行守卫、不改历史向量。

真实 Feed/Pi 认证与生成、参数效力、现场隔离/资源、Docling/论文质量、NAS 与完整
纵向 live 闭环未验证。恢复只证明历史事实回查，不授予恢复位置执行授权；#201 承接
完整隔离回放。资格前置通过不代表名额、预算或领取许可，实验 auto queue 始终禁止。
