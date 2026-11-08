# Pi 执行资源与隔离

本契约描述 `paper_radar.pi_execution` 的离线工程边界；依据 [#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 最终裁决与 [#141](https://github.com/MeteoBoy4/PaperRadar/issues/141)。它补充 [pi-rpc](pi-rpc.md) 和 [pi-supply](pi-supply.md)，机制取舍见 [ADR-0039](../adr/0039-isolate-pi-with-landlock.md)。资源层不领取任务或接收成功；同包的执行组合复用既有任务权威。没有执行 CLI，也不保存准入证据。产品缺少现场隔离/模型能力准入证据时在领取前阻断；这里的合成对端通过不产生兼容 passed。

## 用途与范围

本边界提供受控会话和一次 Screening 任务执行组合；Read 使用[独立执行组合](read-execution.md)复用其资源公共面；只读诊断见 [doctor](doctor.md#pi-执行诊断)。

## 规则

### 资源所有权

`prepare_launch(database, description, roots=ExecutionRoots(...), credentials_dir=..., auth_mode=...)` 是上下文管理器。
它用 **本次回执审计 snapshot 完整 ID** `description.audit_snapshot_id` 调用既有 `use_install`。
后者要求所有已选槽的 Pi 版本一致，并现场核对激活实例、固定工具链、整树与平台。
保护从准备开始持有到上下文退出；选择切换只影响后续取得，已取得句柄冻结绝对 Node/Pi 入口。
不走 PATH、个人 Pi、供给或激活 fallback。

返回值 `PreparedLaunch` 是只读身份与一次 `SessionFactory` 的接口；实现和 token 构造均私有。
调用它之前，上层仍须完成调用描述、请求帧上限、采样、外发与全部由 Live 接收的执行证据判定，随后领取一次任务。
`prepared(description)` 只允许与准备时完全相同的描述、只启动一次，返回 `ByteSession`。
再次调用返回 RPC `startup_error`；领取后沿既有 `executor_error` 消耗预算，
没有独立的 `launch_reused` 执行原因。
会话沿用 `PipeSession` 的独立进程组、二进制有界管道和整组回收规则。
`terminate` 成功回收整组之后才删除该 attempt 的私有目录；清理失败向上返回失败，不能产生成功。
上下文退出再次确保回收，然后释放安装保护。子进程继承安装保护 fd，父句柄 close 不能替活子进程解锁。
Popen 成功而 PipeSession 拒绝接管时，启动器仍负责有界组回收与管道关闭，确认回收后
删除本次私有目录。接管时的 KeyboardInterrupt/SystemExit 保留中断语义；目录删除
失败不把中断改结算为普通执行失败，残留目录不视为清理成功。

`LaunchIdentity` 只包含供给、安装、Pi/Node 版本、启动/隔离策略版本、声明认证来源以及
`proxy_used`/`proxy_port`。不包含 prompt、模型输入、凭据目录、代理 URL、token 或任何 token 派生值。
它是受控执行身份，不是供应商测量、校准或生产用途许可；生产审计接收仍由上层权威负责。

### 领取前与领取后

领取前只读检查：

- `check_cwd()`：唯一权威常量 `/srv/pi-cwd`，没有公开 cwd 参数或默认回退；lstat 是真实目录、每个路径组件无符号链接、目录为空。测试只能私有替换模块常量。`/srv`、`/` 等祖先的现场 context 检查由 Live 统一承接。
- `check_system_prompt(bytes)`：精确 UTF-8 文本，拒绝空值、NUL、绝对路径或首个路径组件为 `.`/`..`。每个 argv 的字节长度含末尾 NUL 不超过 131072；超限在模型启动之前拒绝。
- `check_credentials_directory`：只查元数据，不读 auth 内容，不执行刷新，执行服务另核对显式四根；doctor 复用其中 `check_credentials_metadata` 的路径/owner/类型规则，
  根隔离有意标为 not_assessed。
- `isolation_capability()`：Linux 已登记 syscall ABI，Landlock ABI≥4 且 ruleset 可创建。只创建内核描述符后立即关闭，不创建文件、不启动进程；不冒称实际 Node/TLS 可用。
- 代理语法、provider/auth_mode 闭集、协议档案与有限正数超时（不接受 bool、NaN、无穷或非数值）。
- `use_install` 的供给与安装保护、平台和完整树检查。

启动器内部唯一获准的领取前宿主副作用是专用凭据刷新：可能联网并写回该凭据目录。它不写任务、预算、失败行或成功制品，也不占有 attempt。上层应先完成其余执行证据门禁，再调用 `prepare_launch`，避免在已知不能执行时刷新。
刷新失败或后续领取前检查拒绝均不占用 attempt；成功取得的短期 token 仅随内存上下文存在，不另存缓存。

领取后复核 cwd、指令与安装整树，然后创建 attempt、建立隔离和 exec。
这些步骤失败经 `RpcProblem(startup_error)` 交给现有任务结算，不重发、不重置预算。
pre-exec 中再次核对 cwd 的无链接与为空条件；低于隔离能力要求或建立失败均不能无隔离降级。
预检不是未来 I/O 成功的保证。

### 子进程零 core 限额

宿主认证子进程和模型隔离子进程均在exec前显式设置 `RLIMIT_CORE` 软硬限额为0，
并回读核对有效值。设置失败或回读不为(0,0)时不得继续exec；认证沿既有 `auth_failed`
拒绝，模型沿 `startup_error` 交上层结算，不以继承的默认软限额替代。限额仅在子进程
pre-exec中更改，不修改调用方进程限额。

该行为不更改固定argv/env、`LAUNCH_POLICY_VERSION`、协议注册或注入loader。
它不证明持有短期token的宿主controller已受服务限额保护，也不自动安装项目服务。
部署仍须配置 `LimitCORE=0` 并核对所选Apport版本/配置、uid与非打包路径适用性；
允许root内存瞬时采集而不落盘及后续doctor漂移检查的目标见
[ADR-0049](../adr/0049-bound-core-persistence-with-explicit-zero-limit.md)。
缺少现场证据时普通执行仍阻断，合成Python对端不构成真实Pi/Node准入。


### 启动策略 `pi-launch-1.4.0-v1`

模型进程固定 argv：

```text
<absolute-node> <absolute-pi-entry> --mode rpc --offline --no-session
-ne -ns -np -nc -nt -na --no-mcp --no-themes --system-prompt <exact-text>
```

不传 `--model`、`--provider`、`--thinking` 或凭据参数。模型与档位仍由 RPC 控制；
`set_auto_retry(false)` 与 `set_auto_compaction(false)` 继续由既有协议执行。
`expected_cwd_section()` 输出启动策略定义的 `<cwd>\n/srv/pi-cwd\n</cwd>`，供上层选择严格 RPC cwd 核对。
这里固定的是构造和拒绝规则，旗标是否在真实 1.4.0 中实现目标仍须由 Live 绑定现场证据验证。

每次调用在 `/tmp` 中用 mkdtemp 建立独有的 0700 所有权单元，必须与显式
`data_root/config_root/material_root/install_root` 各根互不包含。
其下 `home`、`tmp`、`agent` 各为 0700；agent 仅写 `settings.json`，不生成 auth/models、会话或历史文件。
默认 settings 为启动策略绑定的规范 UTF-8 字节（末尾一个 LF）：

```json
{"cacheWarming":"off","compaction":{"enabled":false},"defaultProjectTrust":"never","enableInstallTelemetry":false,"retry":{"enabled":false,"provider":{"maxRetries":0}}}
```

模型子进程完整 env 恰好为：

| 变量 | 值 |
| --- | --- |
| `PI_CODING_AGENT_DIR` | 本 attempt 的 `agent` |
| `PI_SKIP_VERSION_CHECK` / `PI_TELEMETRY` | `1` / `0` |
| `PI_OFFLINE` | `1` |
| `HOME` / `TMPDIR` | 本 attempt 的 `home` / `tmp` |
| `LANG` / `LC_ALL` | `C.UTF-8` / `C.UTF-8` |
| `PATH` | 冻结 Node 的 bin 目录 |
| `OPENAI_API_KEY` | 宿主刷新得到的短期 OAuth bearer token |

不继承 XDG、NODE_OPTIONS、NODE_EXTRA_CA_CERTS、其他 provider 变量或任何代理 env。
代理默认关闭；显式只接受无 userinfo 的 HTTP/HTTPS URL，拒绝非法端口、query、fragment 与空白。
仅在该 attempt 的 settings 写 `httpProxy`，不把 URL 写入身份、日志或数据库。
清理只删除 mkdtemp 登记的完整目录，不按宽泛前缀扫描或删除其他 attempt。

### 宿主认证边界

首批只支持 `provider=openai`、`auth_mode=chatgpt_subscription`、
`credential_source=owner_provisioned_dir`。
凭据目录必须显式提供、为当前 uid 所有的 0700 普通目录、路径组件无符号链接，位于各业务根之外；
`auth.json` 必须是当前 uid 的普通文件。PaperRadar 不解析其内容，Pi 自行维护 OAuth 状态。
不提供 API key、legacy、其他 provider、云环境凭据、`!command` 或自定义 models headers 路线。

宿主用同一个受保护的固定入口调用：

```text
<absolute-node> <absolute-pi-entry> auth print-bearer-token
--provider openai --min-expiry <ceil(attempt-timeout)+600>s
```

这是 `pi-launch-1.4.0-v1` 登记的独立入口形状；供给 Node 身份来自 manifest。
依据 Pi 1.4.0 `docs/cli.md`「Authentication commands」；实际可用性仍需 Live 证据，
不能由 install_check 或这份源码/文档推导证明。
宿主 env 仅含 `PI_CODING_AGENT_DIR`、版本检查/遥测关闭、固定 locale/PATH 及指向专用凭据目录的 HOME/TMPDIR；
不传 `--offline` 或 `PI_OFFLINE`，不继承宿主 provider/代理变量，不启动模型会话。
stdout 仅解析 token，stderr 原文丢弃；合计输出上限 64 KiB，刷新有限超时，所有退出路径有界清组。
非零、超时、空值、非法字符、多行或 `sk-` 前缀均领取前拒绝；声明决定模式，不能嗅探后改选认证模式。
`--min-expiry` 至少覆盖 attempt 超时再加 600 秒余量。

沙箱只得到 OPENAI_API_KEY，不得到凭据目录、refresh token、auth 文件或刷新入口权限。
token 不进入 argv、attempt 文件、DB、审计、日志、repr；也不保存前缀、长度、哈希或其他派生值。
Python 内存引用在启动或上下文退出时释放，不承诺对不可变字符串物理清零。
测试对端的 env/argv 观察只在测试进程内，不提供产品转储能力。

### 隔离策略 `pi-landlock-v1`

Landlock ABI≥4；ABI≥6 追加 signal 与 abstract Unix socket scope。先设置 `no_new_privs` 再限制自身，
不 fallback 到 bwrap 或未隔离运行。全部支持的文件访问权受控：ABI4 包含 refer/truncate，ABI≥5 包含 ioctl_dev；
TCP bind/connect 均默认拒绝，只给指定端口 connect 权限。

| 资源 | 权限 |
| --- | --- |
| 实际固定安装树 | 只读、可执行 |
| 常量 cwd | 只读 |
| 本 attempt 所有权单元 | 读写、执行、创建、删除 |
| `/lib/x86_64-linux-gnu`、`/lib/aarch64-linux-gnu`、`/lib64`（实际存在项） | 运行库只读、执行 |
| `/etc/ld.so.cache`、`/etc/ssl` | 只读 |
| `/etc/resolv.conf`、`/etc/hosts`、`/etc/nsswitch.conf` | 只读 |
| `/dev/null`、`/dev/urandom` | 前者读写，后者只读 |
| 子进程自己的 `/proc/self` | 只读 |
| TCP 443 与显式代理端口 | 仅 connect |

文件规则没有开放业务 DB/blob、出版方凭据、宿主认证目录、个人 Pi 或其他用户文件。
运行文件是否存在、符号链接目标是否还需要额外白名单，以及 Node 的 TLS/DNS 是否足够，由 Live 统一实测；
不能为“跑通”扩大白名单而不更新隔离策略。
Landlock 端口规则不限制主机，也不覆盖 UDP/DNS；主机级出站缺口由 Live 统一承接。
本机 ABI 与可观察拒绝测试仅证明本次工程环境，不能迁移成部署机隔离事实。

### 一次任务执行组合

`paper_radar.pi_execution.service.PiExecution(database, data_root, *, roots,
credentials_dir, auth_mode, proxy=None, sink=None, clock=None)` 提供显式回执
`run_attempt(receipt_id, *, limits=DEFAULT_LIMITS, cancelled=..., clock=monotonic)`。
构造不执行 I/O。wall clock 传给 ScreeningTasks（默认当前 UTC）；run_attempt 的 clock
是协议有界单调时钟。sink 原样交给任务服务，缺省 NullSink；不新增日志类型或 CLI，
B 后续产品入口承担所选根的文件日志与入口守卫。

只读 `prepare_call(tasks, receipt_id)` 通过公共 load_input/load_config_snapshot/build_call
取得预算首次语义与本回执审计；核对同阶段投影而非完整 snapshot ID。通过
`ScreeningTasks.prepare_correction` 只读取得本次领取的受控修正（含将要发生的过期
回收），验证包含该修正的实际外层 RPC 帧、系统指令路径和单参数 argv 上限、超时
界限、采样映射与当前激活供给事实。修正文案及脱敏字段路径由任务服务唯一构造。
`admission.EvidenceBinding` 把 supply/install、启动/隔离策略、cwd 段、provider/model/
thinking、sampling/两参数、protocol_profile、auth_mode 绑定到同一证据。
纯 `admit(binding, evidence)` 返回封闭原因或 None，`load_admission_evidence` 产品恒为 None。独立的[分项登记与纯判定](live-evidence.md)不接入本产品读取路径。
缺失、错配以及 cwd_isolation/rpc_compatibility/model_parameters 任一未通过均拒绝；
当前 explicit 映射为空。没有证据表、migration、产品文件/JSON/布尔导入或自动兼容探测。
合成正例仅由测试私有 `_evidence_for` 注入内存事实。

门禁通过才调用 prepare_launch，避免已知缺证据仍刷新凭据。受保护 identity 必须重新
匹配同一绑定，防止选择在预检与取得间切换。保护从准备、auth 到 run_once 返回及整组
回收持续持有。prepare_launch 的只读资源检查和受控 auth 刷新失败仍在领取前；唯一
宿主副作用仍是专用凭据目录刷新。其余预检失败无任务/预算/失败行/成功/任务日志副作用。
`run_once(..., preclaim=...)` 在领取事务中用同连接的最新修正再次核验实际帧，先于
过期回收及预算写入；认证期间前次尝试结算或到期也不能绕过。拒绝不提交回收事实或
任务日志；已发生的受控认证刷新仍仅属既定宿主例外。
领取后工厂复核 cwd/树，创建独占资源和隔离，再启动一次会话；这些失败按
startup_error→executor_error 消耗 attempt。RPC timeout/cancelled/environment/protocol
分别沿既有 timeout/cancelled/executor_error/protocol_error 结算，不重发或 fallback。
系统正常关闭并完成整组回收后才允许返回完整候选，转换成严格 pi_rpc 执行审计交给
ScreeningTasks 唯一权威；不另建接收器、预算或租约。

KeyboardInterrupt/SystemExit 保留未结算租约；显式过期恢复记 outcome_unknown，
进程重建不加次数。历史成功及 Feed 组合可在原根/安装不可访问时查询和恢复，继续
新执行仍重新检查当前证据/供给/auth，不加载旧会话。Feed 仅接收闭集 pi_rpc，根用途
仍独立于 executor_kind。认证 token 的 `sk-` 前缀拒绝是形状启发式，不能证明 token
确属订阅、有效或具有模型权限；真实认证、额度/用量和参数能力仍交 Live。

纯 admission 模块及包导入不连接 auth/launcher/安装保护；doctor 可从只读快照/供给事实
构造 EvidenceBinding 并调用同一 admit，不虚构任务、不调用 prepare_launch 或 run_attempt。
覆盖与未验边界见 [#143 台账](../verification/issue-143-pi-execution.md)。

## 错误与拒绝

错误只携受控 ExecutionReason，不附输入、路径、token 或外部异常。
未支持采样为 sampling_mapping_unavailable，证据缺失/错配及三类未验分别保留共享准入原因；
固定安装、cwd、凭据、隔离、代理、超时和指令非法在领取前拒绝。
领取后 exec/隔离建立或 cwd/树变化统一沿 startup_error→executor_error 结算。
RPC 四类映射和任务业务拒绝仍由各自权威处理，不新增失败类别或重试器。

## 不提供／不证明

本模块不接收现场准入事实；剩余执行验收责任由 Live 统一承担。实际 cwd/祖先目录、固定 1.4.0 入口、订阅刷新、模型权限、参数能力、
TLS/DNS、主机级出站、旗标/settings 的自动网络抑制和 RPC 兼容均未验。
`provider_default` 不能当作 `temperature=0`，采样声明与校准取舍以 runtime-config 契约与[ADR-0040](../adr/0040-declare-provider-default-sampling.md) 为准；
本模块不删除或注入 sampling 参数。
覆盖分母与历史范围见 [#141 独立台账](../verification/issue-141-pi-launch.md)。

## 相关

依据：[#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 最终 B/N/C/D；
[ADR-0039](../adr/0039-isolate-pi-with-landlock.md)、[ADR-0040](../adr/0040-declare-provider-default-sampling.md)。

[供给](pi-supply.md)、[RPC](pi-rpc.md)、[Screening任务](screening-tasks.md)、
[Feed组合](feed-pipeline.md)、[doctor](doctor.md)、
[独立覆盖与收口判据](../verification/issue-140-pi-delivery.md)。
