# Pi 离线工程组合覆盖与收口判据

依据 [#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 正文及最终 A/B/N/C/D，
[#144](https://github.com/MeteoBoy4/PaperRadar/issues/144)；实施基线为本地
`main=e0f8e39d1aff8b57eadfe60de44b8570423c1d40`，起始基线登记无漂移。
这是新增 D1 独立覆盖台账，汇总受控启动、pi_rpc 来源、一次任务执行、Feed 消费和只读诊断。
它不重写 A1–A10 历史结论、A4 1.3.0、A2 快照、A8 DERIVED 或阶段 A 冻结收口表。
`stage_a_verified=false`；没有新增历史 required 集合、物理 migration 或产品执行 CLI。

## 独立 D1 分母

| 未绑定测试模块 | 数量 | 公共 seam 与工程范围 |
| --- | ---: | --- |
| `tests/test_pi_execution_resources.py` | 15 | 常量 cwd、系统文本/路径、含 NUL 的单 argv 字节界限、凭据元数据和四根隔离、代理语法 |
| `tests/test_pi_execution_launch.py` | 18 | 真实本机标准库 auth/RPC 对端；固定 argv/env、fd 保护、独占资源、token 隔离、刷新失败、cwd/树变化、exec、清理、激活切换 |
| `tests/test_pi_execution_isolation.py` | 3 | 本机 Landlock 文件读取/写入与 TCP 端口可观察拒绝，低能力失败关闭 |
| `tests/test_pi_rpc_source.py` | 23 | pi_rpc boundary/value 接收、幂等、模型与业务权威、来源闭集、审计身份、首次语义与本次审计 |
| `tests/test_pi_rpc_source_backup.py` | 21 | 混合 test/pi_rpc 冷恢复；供给/安装/版本/格式/隐私等损坏在查询、validate_all、backup verify 中拒绝 |
| `tests/test_models_v2.py` | 20 | 两种采样声明、严格格式分派、历史回放、实际消费者投影和校准影响 |
| `tests/test_pi_execution_admission.py` | 15 | 绑定键逐项不匹配、产品恒缺证据、显式映射为空、纯模块冷导入 |
| `tests/test_pi_execution_service.py` | 32 | 一次任务公共服务：领取前拒绝、真实隔离进程、四类映射、输出权威、cwd opt-in、预算/retry/租约、日志和敏感哨兵 |
| `tests/test_pi_execution_feed.py` | 1 | boundary→实际本机合成 RPC→pi_rpc 权威接收→Feed 生产 value 登记→value 成功→查询/备份/隔离恢复；新执行缺证据零领取 |
| `tests/test_doctor_pi_exec.py` | 31 | 独立冷进程 import/help/用法、显式 snapshot/凭据选择、四态、缺失/损坏/版本/采样/模型、只读和无泄漏；cwd 共享规则 |
| `tests/test_pi_execution_integration.py` | 3 | 真实本机合成成功恢复；原安装消失与当前证据失效均阻断独立新论文、预算不变；审计 install/Pi 版本损坏拒绝查询及备份 |
| 合计 | 182 | S1=36、S2=44、S3=68、S4=34；不计支撑文件或复用历史回归 |

新增支撑为 `tests/pi_execution_support.py`、`tests/pi_rpc_source_support.py`、
`tests/pi_execution_service_support.py`、`tests/pi_execution_rpc_peer.py` 与
`tests/doctor_pi_exec_guard/sitecustomize.py`。没有修改历史 A7/A8 test/helper/count。
S1–S3 的按次证明分别见 [S1](issue-141-pi-launch.md)、[S2](issue-142-pi-rpc-source.md)、
[S3](issue-143-pi-execution.md)；它们不能代替最终合并树验证。

## 最终 C2 收缩与 C3/C4 归属

RPC→任务只保留每类一例：`test_runtime_categories_and_opt_in_cwd_consume_one_attempt`
的 timeout→timeout、environment→executor_error、protocol→protocol_error；
cancelled→cancelled 由 `test_cancelled_attempt_and_explicit_retry_keep_budget_and_new_sessions`
覆盖。cwd opt-in、模型不符、输出非法另按各自新增边界验证，不复制 A8 全矩阵。
leader 提前退出/孤儿组回收只在上述组合参数 `orphan` 保留一例；历史 A8 pipes/lifecycle
的既有矩阵和证明范围不动。

| 五类启动器特有失败 | 独立归属 |
| --- | --- |
| exec/隔离建立失败 | S1 `test_exec_and_isolation_establishment_failure_leave_no_attempt`；S3 领取后 exec 参数断言 executor_error/一次预算 |
| 领取后 cwd 变化 | S1 `test_cwd_change_after_prepare_is_controlled_startup_error`；S3 postclaim cwd 参数验证任务结算 |
| E2BIG 领取前拒绝 | S1 单 argv UTF-8+NUL 界限；S3 `test_system_prompt_and_argv_limits_are_preclaim` 的 argv_limit 参数 |
| 凭据刷新失败 | S1 auth 形状/非零/超时五参数；S3 preclaim auth_failed 验预算为零 |
| sampling_mapping_unavailable | S3 v1/v2 explicit 两参数；S4 snapshot 诊断 invalid，不把合法配置当可执行 |

C3/C4 逐项归属：

- 指令路径与 argv 上限、精确 env：S1 resources/launch；S3 实际组合继续观察固定策略。
- token 不进入 `/proc/self/cmdline`、attempt settings/models、DB、审计、repr：S1 launch；安全日志/模型与指令哨兵：S3 sink 用例。产品没有转储入口。
- Landlock 允许白名单读、拒绝业务 DB/blob、出版方/个人 Pi/宿主 refresh 凭据、安装与 cwd 写：S1 isolation/launch；S3 对端确认当前 DB 和 refresh 凭据不可读。均为测试哨兵，不接触真实秘密。
- `executor_kind="production"` 冻结负例仍由原 A7 用例断言；S2 闭集只增加 pi_rpc。pi_rpc 空 provider/model、install/Pi 版本损坏由 S2 source/backup；S4 用实际组合产生的审计再验证损坏拒绝。
- 无原安装的历史查询/恢复和新执行阻断：S2 冷恢复、S3 Feed 闭环、S4 当前安装与准入失效两种拒绝；独立新论文预算为零，已有成功预算不重置。
- doctor 冷进程、元数据只读和 pi-supply 金样：S4 新模块与原 `test_doctor_process.py`。新守卫拒绝 socket/subprocess/exec/fork/创建/写入/凭据内容 open/预算及审计表读取；import/help 额外拒绝整个执行包导入和 SQLite。原 basic/config 强守卫没有放松。
- C4 的 Node/Pi 为合成供给中的 Python 可执行文件与独立标准库字面量对端，支持 auth 和 RPC 两形状。use_install→Popen→PipeSession→run_call→run_once 为真实本机进程链。Python runtime 白名单只在测试私有注入，合成准入只在测试内存注入。
- 订阅增量：声明 auth_mode 与 token 形状不符由 S1；双形状对端及 min-expiry 超时余量由 S1；额度/环境错误沿既有分类由 S3；models-v2 两声明、v1 黄金身份与校准分量由 S3；doctor 明示不查 token/计划由 S4。没有 token 前缀嗅探后切换通道。

## 父票验收对应

| 条款 | 实现/拒绝边界与证据 |
| --- | --- |
| A1 | 成功来源闭集 test/pi_rpc；不使用 production 标签；S2 与冻结 A7 负例 |
| A2 | 严格审计格式2、必填模型观察、供给/安装/版本与引用核对；S2/S4 查询和恢复损坏拒绝 |
| A3 | PiExecution 在 llm 外；复用 build_call/run_once/唯一接收；S3 服务与 A8 架构回归 |
| A4 | 本次审计 snapshot 与预算首次语义分别使用；保护贯穿 auth/进程回收；S1/S3 |
| A5 | 系统文本路径形状与 argv 字节在领取前拒绝；S1/S3 |
| A6 | 唯一 cwd 常量，产品无 cwd 参数；空目录/无链接共享检查与严格外发段；S1/S3/S4；祖先现场未验 |
| A7 | 模型子进程精确 env 白名单，无宿主敏感 env 继承；S1/S3 |
| A8 | 每 attempt 独占 agent/settings，无历史/session/auth/models；S1/S3 |
| A9 | 仅新增只读 doctor scope；无执行 CLI、证据文件或 passed 产品入口 |
| A10 | read_evidence 恒缺；真实产品领取前阻断，正例只在测试私有注入；S3/S4 |
| A11 | 预检对任务/预算/失败/成功/日志零副作用；唯一宿主例外是有界认证刷新；S1/S3；doctor 连该例外也不执行 |
| A12 | 裸命令、未知 scope、help/config 摘要同步；basic/config 语义与 pi-supply 金样保持；S4 |
| B1/B2 | Landlock+no_new_privs 与 TCP端口限制，主机级出站缺口；ADR-0039、S1 |
| B3/B4 | 显式 owner 目录、订阅 bearer、显式代理且不继承 env；S1；doctor 仅元数据 |
| B5 | 采样唯一规则属 runtime-config；provider_default 与显式映射拒绝；ADR-0040、S3 |
| B6 | RPC 默认关闭的 cwd 核对，生产显式启动策略值；S3；A8默认行为不变 |
| B7 | 仅内存绑定事实，产品无持久化证据来源，无 migration；S3 |
| B8/B9 | 加固旗标/settings 完整构造；只读 pi-exec 四态和严格退出2；S1/S4 |
| N1/N2/N3 | 刷新副作用例外、同一固定入口/Node身份与 auth 调用形状、attempt超时+600s；S1与执行 Contract |
| N4/N7 | 计划限额沿既有失败类别；实际模型不符拒绝且不替换；S3；真实计划能力仍交 Live |
| N5/N6 | provider_default不等于温度0/逐字重现；声明式 auth_mode 与脆弱前缀形状启发式；ADR-0040/执行Contract、S1/S3/S4 |
| D | Contract 原地一致、两ADR、术语/README/路线图、独立分母、精确登记及最终树门禁判据；本台账与外部审计 |

## 开发期验证

相关组合覆盖上述11个新模块及 doctor、Feed、供给保护、配置黄金身份/投影和
A8 call/preflight/lifecycle/pipes/架构的既有回归：**542 passed**，170.62秒。
命令统一 `uv run --offline --locked pytest -q`，精确选择与原始日志留工作树外。
新D1单独 collect：**182 tests collected**；不等于正式组回执。
CLI注册/帮助/导入链触发 `./scripts/check-compatibility cli`：**59 passed**，退出0，
入口总耗时67.39秒。未触及验收发布/回执接线，因此不扩为acceptance/all。
相关19个Python文件Ruff检查、格式检查和mypy全部通过。拆出凭据元数据检查后，
保留原四根检查的受控OSError转换；最终metadata/doctor子集再次**46 passed**。

## 固定登记审阅

稳定 main 基线没有 baseline_drift。只更新15条实际 source 哈希：中央共享12条
（cli；config 的 adapter_loading/compile/material_assembly/schema；llm/models；
pi_supply/cli；screening_tasks 的 __init__/success/success_integrity/success_models/success_rules），
A8 单组3条（llm/calls、rpc、rpc_messages）。成员、用途、测试计数、fixture、negative、
required 与显式 DAG 不变；不恢复 scope 哈希边。精确 group/path/旧新 SHA 的白名单
与最终身份确认保存在工作树外审计报告，最终合并身份须重新确认。

分类控制仅把新增现状契约 `docs/contracts/pi-execution.md` 加入 live_documents 精确路径。
它维护当前已实现接口与权限细节，符合其他现状 Contract 的分类；ADR、D1台账、历史快照、
Schema、代码、测试与fixture保持固定属性。该控制文件变化影响全部11组：A1、A2-01、
完整A2、A3–A10，须逐组审阅确认；不以“新增未绑定文档”跳过分类控制的全组影响。
旧 `tests/test_doctor_process.py` 只改一行独立帮助清单字面量，增加 pi-exec；没有删断言、
改参数化成员或计数。该模块没有历史组登记，affected_groups为空，仍按冻结期望逐字节审阅。
`doctor_pi_supply_golden.json` 与旧守卫保持原字节。旧ADR仅有S1/S3已登记状态反链，正文未改。

## 完成判据与证明限制

开发期相关 pytest、静态检查、CLI兼容组合和 scope collect 供独立审阅使用；不能产生
正式回执或替代最后完整门禁。最终完成要求：独立双轴审阅及修复后提交所有身份材料，
在最终 integration 冻结树由唯一执行者运行 `./scripts/check-offline` 退出0，
并查询同一 run 为 `passed/verified/same`；run_id 与日志留工作树外。
后续 merge/HEAD/target/树变化不得沿用本工作树确认或门禁身份。

工程切片承接冻结 I04/I05/T05/T07/T08/T12：固定受保护执行、隔离独立会话、严格成功与
用量来源、预算/恢复、只读诊断和消费者闭环。原冻结表“未交付”原文不变。
实际 Pi/Node/auth/模型与 `/srv/pi-cwd` 现场仍未验证：Cwd/Live继续承担祖先资源和现场隔离、
主机级出站、全部 DERIVED（尤其02 cwd包装）、订阅刷新/token通道/前缀启发式、
计划模型权限与限额、采样映射、TLS/DNS白名单充分性及隐含retry/预热抑制。
本机Landlock拒绝不等于部署机事实，合成用量不是供应商独立测量。
B继续承担真实产品入口、实验根、所选根安全有限日志与用途资格；非test来源不自动授予
正常生产、正式校准或Read资格，Pi工程通过不使B自动进入前沿。
