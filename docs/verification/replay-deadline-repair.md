# 脱网回放时限与重复校验工程覆盖

本台账只记录独立 D1、`/tmp` 合成闭包和本机 Linux OS 证明，
不扩大 A1–A10 固定分母、required 集合、CI 或真实现场结论。
工程基线 `5f68f6c4ba8ffa838574705e402462a0b4df0fa1`。
不新增 Alembic migration、表定义或 Schema 字段；`ReplaySummary` 与成功输出闭集保持。
现状边界见[备份恢复](../contracts/backup-restore.md#隔离脱网回放)与
[报告恢复接缝](../contracts/reports.md#恢复与消费接缝)。

## 诊断与修复

服务实际 subprocess 接缝注入 `TimeoutExpired` 的初始红环收到
`isolation_unavailable`，而非期望的 `replay_timeout`，**1 failed /3.14s**。
修复将超时、隔离安装/启动失败、隔离自证失败及 worker 业务原因分开，
不回显异常、部分 stdout、私有路径或内容。
`--timeout-seconds` / Python `timeout_seconds` 为整数 1–3600 秒、默认 600 秒。
600 是旧 120 秒的五倍有限工程余量，3600 是显式选择上限，
不从合成时间推导真实闭包必能完成，不因延长时限而绕过任何验证或取得通过。

红环后排序的假设及探针结论：

1. `TimeoutExpired` 被 `SubprocessError` 总捕获吞并：红环确认，独立受控原因修复。
2. `history/rebuild/verify` 重复校验相同固定报告来源：调用计数与 profile 确认，
   新 `Reports.replay()` 每个报告内部实核、核旧投影、原子重建和核发布字节。
   普通 rebuild/verify 仍独立完整校验，无调用方已验证标志，无跨调用缓存。
3. 同份 Read/evidence 多次 load 主导成本：本合成规模不是主因，未引入正文缓存。
4. 前后 `verify_contents` 是必要完整性成本：两次均保留，不跳过闭包、树、原件不可读、
   禁网、后代继承、ordinary 拒绝、证据 orig/pages/bbox/charspan 或预算核验。

进一步的确定性实际 OS 红环确认：外层 1 秒超时原来只杀直接 worker，
唯一自证后代在返回后 0.5 秒观察窗仍可执行，**1 failed /3.98s**。
后代现于 exec 前设置 `PR_SET_PDEATHSIG=SIGKILL` 并复核预期父 PID；
失败映射 `isolation_verification_failed`。实际受限父子进程覆盖：
已 exec 后父死亡、故意在设置前停顿 2 秒使父先死亡（不进入后代解释器/自证）、
无延迟写 views；另有 prctl 失败与父 PID 不符的受控负例。
设置前的合成停顿允许后代暂留 preexec，随后拒绝 exec；不声称父返回瞬间整树同步回收。
生产 preexec 的 arming 前无业务文件写入。
这只利用既有唯一自证后代拓扑：自证分支返回，业务 audit 拒绝再 spawn；
不扩张 Landlock、seccomp、no_new_privs、env、fd 或目录权限。

## 合成成本基准

树外诊断脚本 `/tmp/paperradar-replay-repair/benchmark_replay_cost.py`；
它是计量探针，不进入产品 D1 分母，不把私有方法计数作为永久回归断言。
相同输入：1 个合成 Read、2 份固定 daily/paper 报告、41 个同页源块/evidence 切片，
无暴露导出；完整备份/恢复使用真实产品，外部 HTTP/Pi RPC/parser/clock 为确认替身。
计时只包围实际 `worker.business`，含 cProfile 开销；节点总耗时还含 setup/teardown。
各方法时间是 inclusive 且互相重叠，不能相加。

| 同规模探针 | 修复前 | 消除报告重复来源校验后 |
| --- | ---: | ---: |
| business（含 profile） | 51.479s | 41.660s |
| 节点总耗时 | 126.63s（诊断计数红） | 118.75s |
| 非 business 余量（setup/teardown 等） | 75.151s | 77.090s |
| 报告来源校验次数 / inclusive 时间 | 10 /28.050s | 6 /17.617s |
| extraction load 次数 / inclusive 时间 | 109 /2.312s | 73 /1.700s |

同规模 business 下降约 19.1%，来源校验次数下降 40%。
修复前另一次相同探针 business=51.289s、节点总耗时125.82s，计数相同。
前后完整校验 2 次的修复前 inclusive 时间33.727s，已包含部分报告校验。
这不是复杂 PDF、多论文或真实大批次吞吐保证；没有执行任何真实/live 命令。
profile 还显示反复构建 Alembic revision 图的成本；未扩大到全库缓存，留后续评估。

## 独立 D1 与验证记录

新增未绑定模块：`tests/test_replay_deadline.py` **16** 节点、
`tests/test_replay_descendant_deadline.py` **4** 节点、
`tests/test_report_replay_projection.py` **3** 节点，共 **23**。
覆盖中文 CLI/冷帮助、参数范围、超时/实际 preexec 失败/业务失败分类、
成功输出不扩张、真实受限休眠 worker 时限、父死亡竞态、完整报告字节与日志/库不变、
坏旧投影和跨调用合成登记损坏拒绝。旧冻结测试、fixture、向量、格式及中央哈希未改。

| 相关模块 | 收集节点 |
| --- | ---: |
| `tests/test_replay_deadline.py` | 16 |
| `tests/test_replay_descendant_deadline.py` | 4 |
| `tests/test_report_replay_projection.py` | 3 |
| `tests/test_replay_business.py` | 1 |
| `tests/test_replay_container.py` | 1 |
| `tests/test_replay_entry.py` | 2 |
| `tests/test_replay_faults.py` | 24 |
| `tests/test_replay_os.py` | 1 |
| `tests/test_replay_process.py` | 2 |
| `tests/test_experiment_reports_cli.py` | 14 |
| `tests/test_experiment_reports_faults.py` | 4 |
| `tests/test_experiment_reports_publication.py` | 2 |
| `tests/test_experiment_reports_recovery.py` | 1 |
| 合计 | **75** |

最终相关组合 **75 passed /428.13s /退出 0**，见 `final-regression.log`；
包含实际完整 Read/报告/暴露恢复、原件不可读/禁网/后代继承及 ordinary 拒绝、
坏 evidence-map/缺件、完整表/物理库与日志不变，以及报告故障/发布/恢复消费者。
这次执行中生命周期测试随后仅收窄函数名；最终名称下补跑 **4 passed /7.58s /退出 0**，
见 `descendant-final-names.log`。`test-rename-proof.json` 用 SHA 证明除了函数名替换测试体
逐字相同；最终唯一节点仍为 75，不把这 4 项重复执行计作额外覆盖，不声称最终 75 同一命令。
生命周期修复前的 `regression.log` **71 passed /425.22s** 仅为中间回归，不当作最终 worker 证明。

最终生产源码冻结后 CLI 兼容 **59 passed /81.07s /退出 0**，入口总耗时81.66s，
见 `final-cli-compatibility.log`；没有验收入口/回执接线变更，未触发 acceptance 组合。
全部 **8** 个改动/新增 Python 的 Ruff、format、strict mypy 退出 0，
见 `final-{ruff,format,mypy}.log`；源码哈希与最终测试改名映射均在树外保留。
未改 Schema/表定义，不触发 Schema 一致性节点。

只读 scope 审计显式绑定稳定本地 main 实际 base
`6f0c4e93d43b86cf25e87d90bf5130e7533d19d1`，开发漂移与未确认项保留给 #206，
不机械重绑或更新中央哈希；未请求 scope `--collect`，不声称固定分母收集通过。
最终作者 SHA/tree、双向非空 diff-check、clean 树审计身份/结果见树外 `handoff.md`。
原始日志、源码 `__file__`、独立 worktree venv 身份、profile 和 h/o 均在
`/tmp/paperradar-replay-repair/`，不写正式 `verification-runs/` 回执。
完整离线门禁未获本票授权且未执行；未读取真实实验/研究根、专用运行 checkout 或凭据，
未调用真实 Pi/OAuth/SDK/模型。真实来源、质量、现场 replay、NAS 与执行恢复均未验证。
