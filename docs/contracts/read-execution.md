# 单篇 Read 的 Pi 执行组合

## 用途与范围

`paper_radar.read_execution.ReadExecution(database, data_root, *, roots,
credentials_dir, auth_mode, proxy=None, sink=None, clock=None)` 为 B 提供已登记单篇
Read 的执行服务。`run_attempt(task_id, *, audit_snapshot_id=None, limits=DEFAULT_LIMITS,
cancelled=..., clock=...)` 返回 ReadAnalysis 或 ReadTask；没有产品 CLI、自动队列、
每日 quota、read_requests 或模型 fallback。构造不启动模型、刷新认证或加载 Docling。

复用 prepare_launch、admission、run_call、安装使用保护及 PiRpcExecutionAudit。
Read 的任务权威独立于 ScreeningTasks，使用同一个 Read Schema 与 v2 接收/原子提交链；
不抽取或修改 A7/#140 内核，不向 Pi 开放 PDF、全文获取、Docling 或 evidence 工具。

## 规则

### 准入与领取顺序

1. 取得 `read_tasks.execution.execution_resource(data_root)` 的本机同根 Read 独占资源。
   等待在认证与领取之前，不持 SQLite 事务，不占 attempt，不消耗短期 token 的有效期；
   同根人工与后续自动 Read 消费同一资源。Docling 的独立锁含义不变，B 负责跨阶段调度。
2. `ReadTasks.prepare_execution` 只读重建历史正文、Context 和调用描述，预算以普通值返回。
   默认审计配置为预算首次快照；显式 audit_snapshot_id 必须是该任务已登记的快照。
   语义仍取预算首次配置，本次审计取明确快照，两者 Read 投影必须相等，不读当前 settings。
3. 读取本次激活供给/安装，用 LaunchIdentity、固定 cwd 与历史描述绑定执行准入。
   当前 read_evidence 恒为 None；没有产品证据 JSON、布尔声明、导入、自动探测或模拟生产开关。
   缺失、不匹配、cwd/RPC/模型参数未实测均领取前拒绝；显式采样无已验证映射也拒绝。
4. **准入优先于完整帧预算**。两者同时失败首先报告准入原因。准入通过后才拒绝
   read_input_over_budget；完整首次帧及最坏修正槽均须符合 #160 的边界。
   再检查安全修正的实际完整帧、系统指令及 argv 上限；不截全文、不省 evidence、不转 map/reduce。
5. prepare_launch 获取安装保护并准备认证，保护包住领取、协议、结算和进程清理。
   准备后的 identity 重新绑定，供给/安装/策略/认证身份变化为 evidence_mismatch，不领取。
6. run_pi_once 的短事务重新核对最新资格、唯一成功、租约、代际预算和 ordinal。
   preclaim 使用事务内最新安全 correction 复核实际帧，拒绝没有新 attempt。
   认证等待期间其他执行者的结算不能使本次沿用旧修正。
7. 执行器核对冻结 Read 输入身份，一次调用 run_call。候选携严格审计进入同一个 v2 权威；
   超时/cancelled/environment/protocol 分别进入 timeout/cancelled/executor_error/protocol_error。
   最终报告模型不符由 ReadTasks 判 model_mismatch。没有隐式二次调用。

配置、正文或持久引用损坏仍由原组件安全拒绝；有限正数超时及显式四根约束也保持。
roots.data_root 必须与服务的数据根相同。调用上限最多为 RPC 默认值，完整执行和回收预算
小于 Read 的 600 秒租约；不引入后台续租线程或锁内数据库长事务。

### 一次执行与来源

每个 attempt 新建进程组、私有目录、PreparedLaunch 和独立 RPC session，工厂只用一次。
run_call 只接受唯一完整最终 assistant 消息，必须到 agent_settled；ACK、退出 0 或流式片段
不是成功。工具、compaction、willRetry、额外 turn、重复结束或 cwd 错配拒绝，不产生第二个事实。
整组回收后才能登记候选，清理失败不能登记成功。

一次执行只消耗一次持久 attempt，并只结算一个候选或封闭失败。KeyboardInterrupt/SystemExit
原样重抛，进程整组清理与保护释放仍执行；租约保留未结算，显式 reclaim 追加 outcome_unknown，
次数不退还。不会加载旧 session 或因进程重建补预算。

PiReadCandidate 与 PiReadFailure 是专用 Pi 端口的普通值，均无 executor_kind 开关。
PiReadFailure 只携封闭 ReadFailure，output_invalid/outcome_unknown 仍只能由各自权威产生。
test 端口只接受 bytes 并固定为 test，PiReadCandidate 或附生产来源的对象不能通过它提交。
Pi 端口重建 strict PiRpcAudit，核验真实已登记 supply/install、adapter/protocol/channel/provider
及实际模型。Literal、Schema 形状、登记引用和合成执行成功均不证明模型真实性或现场准入。

成功审计复用 PiRpcAudit 格式 3 的全部字段。新的 Read 执行审计记录另含 audit_snapshot_id，
指向该任务明确登记的本次执行配置；共享 PiRpcAudit Schema 未扩字段。历史不含该字段的
#161 专用端口记录仍以预算首次配置验证并保留原字节。历史回放分别核验快照登记、Read 投影、
固定供给/安装引用、模型观察与审计 Schema，不要求原安装可执行，不重新准入或调用模型。

### 有限日志

sink 默认 NullSink，不猜测数据根、不创建日志文件。B 在选定根后显式注入 FileSink。
组合只消费 ReadTasks 既有 claimed/succeeded/failed 安全事件；准入/预算等领取前拒绝无任务事件。
允许字段闭集见[运行日志](runtime-logging.md#read-执行字段闭集)。完整 JSONL/RPC、stderr、
prompt、Profile、正文、候选、坏 evidence ID、修正、认证及环境值不进入日志；候选只作为必要业务制品保留。

## 错误与拒绝

执行资源、安装、认证、准入、采样映射与超时参数错误保持 ExecutionError 的封闭原因和中文指引，
不占 attempt；ReadTaskError 保留业务前置、完整帧预算、所有权及持久引用拒绝原因。
领取后的协议执行失败结算为既定 ReadFailure，不回显原始 stderr 或认证内容；
文件/数据库发布故障不能留下半条分析。具体闭集由[Pi 执行](pi-execution.md)和
[Read 任务](read-tasks.md#错误与拒绝)拥有，调用者据原原因处理，不包装成通用模型失败。

## 不提供／不证明

离线协议/进程替身只验证工程路径；准入离线测试只证明缺失、不符或未实测时拒绝。
**任何替身运行成功都不得解释为 EXP-2 或真实执行准入已成立。**
真实供给、安装保护、认证刷新、cwd 祖先资源与主机出站、实际 1.4.0 RPC/模型参数与权限归 Cwd/Live/B。
合成 PDF→正文→Pi 工程进程→隔离恢复的独立组合见[组合覆盖](../verification/issue-165-body-read-closure.md)；
真实 PDF→真实模型 Read 的完整组合由[B](../roadmap.md#module-b)承接。

## 相关

依据：[#162](https://github.com/MeteoBoy4/PaperRadar/issues/162)、
[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)、
[ADR-0044](../adr/0044-freeze-read-input-rendering-and-preclaim-budget.md)、
[ADR-0045](../adr/0045-persist-explicit-read-generations.md)。
[Pi 资源](pi-execution.md)、[RPC](pi-rpc.md)、[Read 任务](read-tasks.md)、
[Read 权威接收](read-validation.md)、[D1 覆盖](../verification/issue-162-read-execution-delivery.md)。
