# #198：规范 paper-ID retry 与冻结语言恢复补丁

本票独立 D1，`stage_a_verified=false`；未绑定旧验收组，不扩大 required/历史分母。
基于 integration `11b9835714c28f24436cfd139508429d65ad73ee`（含旧稿 `6828732`）。
[旧稿台账](issue-198-explicit-read.md)的 28/247 是旧稿源码历史，不能作为本补丁最终树结果。
本补丁将规范入口对齐 `intent/draft.md` §8.1 的 `reading retry <paper-id>`；
本文记录本次实际选择，不追改旧台账或冻结材料。

## 接缝与数量

| 模块 | 本次实际节点 | 范围 |
| --- | ---: | --- |
| `tests/test_experiment_read_retry_cli.py` | 9（完整模块） | 标准 PAPER+snapshot 唯一失败父代登记且不运行；后继继续/再增代/换样后精确旧请求仍原回执、无认证/新事实；同 Connection 等待后另一语言结算使父代歧义拒绝；高级 task 明确当前失败且拒绝旧父；succeeded/ready/running/lease_expired 不得 retry、不隐式 reclaim；非当前指纹及高级任务不能绕显式 snapshot；新 paper 请求真正 backup/restore verify 子进程+无运行时冷进程闭包；两次过期查询→显式结算→paper retry→单task执行闭环；已有 en 后继继承语言/指纹、守住两次预算，禁止新增登记/预算/代际的故障注入下仍实际执行 |
| `tests/test_experiment_read_logging.py` | 3（完整模块） | read/retry/reclaim 所选根日志，retry 改成规范 paper 调用；查询只读 |
| `tests/test_experiment_read_cli.py` | 10（明确节点，不是整个24节点模块） | 基础read帮助1、规范paper失败恢复1、原显式reclaim恢复1、原分析冷恢复1、六个冷帮助6 |

新支持 `tests/experiment_read_retry_recovery_worker.py`：标准恢复 `database.sqlite3 + blobs`，
拒绝 Read/Pi 执行运行时与 Docling、网络/子进程；完整验证新 paper 请求/父链/快照与只读文件字节。
测试仅 `/tmp` 合成 HTTP/Pi RPC、parser/cgroup/clock；waiver/egress/six owner review 都走 CLI。
服务 API 只用于失败注入与并发；不 mock ReadExecution 或内部准入成功，不将 test 成功提升 pi_rpc。
不触真实实验根、运行专用 checkout、私有材料/回执/PDF/凭据；不执行任何 live 命令。

## TDD

- 标准 `reading retry PAPER --snapshot ...`：旧 TASK 位置接口实测 red（33.74s），
  公共 retry_paper 和规范 CLI 接入后首个 green（34.76s）。
- 明确 en 后继经 task-id 恢复：旧 zh 硬限实测 task_scope_mismatch red（18.85s）；
  保留现有任务冻结语言后 green（36.05s）。新 request 仍默认 zh，无新增语言入口。
  合成对端故意只返回 zh；en 恢复因此两次 output_invalid，不能改写成 zh 成功。
  SQL 故障守卫禁止新增 read registrations/budgets/tasks，恢复未触发；公开任务身份/指纹/代际与 en 保持。

## 最终源码实际验证

- 上表明确选择合计 **22 passed / 639.26s**。
- 组件 **65 passed / 137.46s**，完整选择：
  `test_read_tasks_preconditions.py`（15）、`test_read_tasks.py`（5）、
  `test_read_tasks_leases.py`（6）、`test_read_tasks_recovery.py`（20）、
  `test_read_tasks_execution.py`（5）、`test_read_queries.py`（7）、
  `test_read_execution_history.py`（7）。
- 先 mkdir 本票独占 TMPDIR 后 `./scripts/check-compatibility cli`：
  **59 passed / 80.77s**；入口总81.51s。
- 所有本补丁触及 Python（6生产+4测试/支持）默认 strict mypy、Ruff、format 及实际差分检查。
  完成提交后另检查 `git diff --check aa58edc HEAD` 与补丁 base→HEAD，不以 clean 空 diff 代替。

完整节点清单、实际命令/结果、静态输出与最终 commit/scope 身份留外部交付报告。
未运行完整离线门禁；未重绑、排除或修改旧冻结测试/fixture/向量/required。

## 公共边界

`ReadTasks.retry_paper` 与 `failure_facts` 共用同 Connection 当前 failed 查询。
PAPER+snapshot 界定当前完整输入；默认唯一定位父，ambiguous_task 拒绝；高级 task 同样须
属于该 paper、当前输入、latest、failed。写事务重新核对集合/父代/正文、visibility 与原 Read 资格/B guard。
`replay_retry_paper` 供 B 样本预验前精确重放；只回原后继，不追加或执行。
现有 registrations 保存带 retry_paper 标记的规范范围（paper/snapshot/可选task/reason/actor），
同一 Read 校验权威复核快照指纹、父链及规范编码；旧 task API/请求仍兼容，不迁移历史字节。

无 migration，head 保持 `b005_layout_recordings`；无 Schema/模型 Frozen Contract/Stage fingerprint 变化。
无 read_requests、manual_read_request、自动队列或自动名额。恢复不更改冻结语言、不另建请求/预算，
仍核 paper/snapshot/current/latest、选择/正文/owner/egress 及原执行准入。
#199 恢复动作文本须使用规范 paper 位置参数及显式 snapshot；task-id 只是高级明确父代或后继执行身份。

所有替身只证明工程路径，真实 Pi/模型/材料质量、现场隔离/脱网、日报/暴露/NAS 均未验；
历史固定材料与 S3 仍留 #206，最终完整集成由主会话/merger 另核。
