# Pi 执行资源与隔离

本契约描述 `paper_radar.pi_execution` 的离线工程边界；依据 [#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 最终裁决与 [#141](https://github.com/MeteoBoy4/PaperRadar/issues/141)。它补充 [pi-rpc](pi-rpc.md) 和 [pi-supply](pi-supply.md)，机制取舍见 [ADR-0039](../adr/0039-isolate-pi-with-landlock.md)。资源层不领取任务或接收成功；同包的执行组合复用既有任务权威。没有执行 CLI；准入事实由独立[受保护账本](live-evidence.md)保存，本模块只读消费。产品缺少现场隔离/模型能力准入证据时在领取前阻断；这里的合成对端通过不产生兼容 passed。

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

领取前准备允许创建临时 scope、阻塞封装、独占认证 HOME/TMPDIR 及其清理资源，并执行专用凭据刷新；刷新可能联网并写回该凭据目录。模型 Pi 仍未 exec，不发送 prompt，不写业务任务、attempt、预算、失败行或成功制品。上层先完成其余执行证据门禁，再调用 `prepare_launch`。
刷新失败或后续领取前检查拒绝均不占用 attempt；成功取得的短期 token 仅随内存上下文存在，不另存缓存。

领取后复核 cwd、指令、安装整树与已准备封装放置，然后创建临时资源、建立隔离和 exec。
这些步骤失败经 `RpcProblem(startup_error)` 交给现有任务结算，不重发、不重置预算。
pre-exec 中再次核对 cwd 的无链接与为空条件；低于隔离能力要求或建立失败均不能无隔离降级。
预检不是未来 I/O 成功的保证。

### 子进程零 core 限额

宿主认证子进程和模型隔离子进程均在exec前显式设置 `RLIMIT_CORE` 软硬限额为0，
并回读核对有效值。设置失败或回读不为(0,0)时不得继续exec；认证沿既有 `auth_failed`
拒绝，模型沿 `startup_error` 交上层结算，不以继承的默认软限额替代。限额仅在子进程
pre-exec中更改，不修改调用方进程限额。

零 core 规则保留固定 Pi argv/env 和协议注册；放置机制另以新版启动策略绑定。
它不证明持有短期token的宿主controller已受服务限额保护，也不自动安装项目服务。
部署仍须配置 `LimitCORE=0` 并核对所选Apport版本/配置、uid与非打包路径适用性；
允许root内存瞬时采集而不落盘及后续doctor漂移检查的目标见
[ADR-0049](../adr/0049-bound-core-persistence-with-explicit-zero-limit.md)。
缺少现场证据时普通执行仍阻断，合成Python对端不构成真实Pi/Node准入。


### 启动策略 `pi-launch-1.4.0-v9`

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
`auth.json` 必须是当前 uid 的普通文件。Pi 原默认存储维护 OAuth 状态；封印产品认证进程仅从公开 API 回调检查到期元数据，其余 credential 不透明透传。
不提供 API key、legacy、其他 provider、云环境凭据、`!command` 或自定义 models headers 路线。

正式准备与 collector 共用受保护的固定入口：

```text
<absolute-supply-node> <sealed-runtime>/paper_radar/pi_execution/auth_helper.mjs
```

固定 argv 无额外参数。入口按该固定安装 `package.exports["."].import` 解析公开入口，核版本、导出形状及已审静态源码摘要；不使用裸包搜索、私有 deep import、loader 或替换 provider。`ModelRuntime.create` 使用所选持久根的 `auth.json`、`modelsPath:null`、`refreshOnCreate:false`、`allowModelNetwork:false`，复用原默认存储；会加载内置静态 catalog，不刷新模型目录或创建模型会话。保留原 CLI 的一次公开 `listCredentials` OAuth 类型核对，拒绝 API-key／`!command` 路线后仅调用一次 `getAuth('openai')`。

本次实例的公开 `provider.auth.oauth.refresh` 包装在原 CredentialStore 锁内观察原 credential 的到期元数据，完整对象与原 signal 原样透传原 refresh。最低有效期仍是 `(ceil(attempt_timeout)+600)*1000` 毫秒。`refresh_called`、`refresh_succeeded` 来自真实回调；仅回调成功且整个 `getAuth` 成功后，按已固定具体 FileAuthStorageBackend 写错会抛出的实现记录 `store_committed=true`。写错、取消、短有效期或 `toAuth` 后置失败均保守未知；竞争跳过时本次 `refresh_called=false`，需要刷新与到期事实保持未知，不认领他人提交。

`auth-refresh-metadata` v1 固定字段为版本／源码策略 ID、pid、开始／完成／刷新 UTC 和五个 bool/unknown 事实。独立 metadata FD 经原放置握手的 `SCM_RIGHTS` 映射；Python 严格拒绝额外字段、错误类型、来源 ID、pid 或时序。token stdout 仅产品父进程解析；root 仅接 v2 worker 元数据及其既有预占绑定，不继承 token FD。错误正文始终丢弃。Pi 存储阈值到期与供应商真实到期分开；后者始终 unknown，正常提前刷新满足 [ADR-0063](../adr/0063-observe-normal-oauth-refresh-in-product-process.md) 的已决口径。

宿主 env 仅含 `PI_CODING_AGENT_DIR`、版本检查/遥测关闭、固定 locale/PATH、独占临时 HOME/TMPDIR，以及产品父进程构造的固定安装路径、原 attempt 超时与 metadata FD；不继承用户变量。这些内部参数不是外部 CLI 或 root 任意脚本入口。
临时根为 `/tmp/paper-radar-auth-*`，根与 home/tmp 均 0700，位于业务／配置／材料／安装和持久凭据根之外。
helper 成功、拒绝、超时或异常退出后先终止进程，再删除并核验整个临时根；删除不完整以 `cleanup_failed` 拒绝模型准备。
compile cache 因此落在临时资源中，模型不会继承 helper 的 HOME/TMPDIR，持久认证根仍不可读。
不传 `--offline` 或 `PI_OFFLINE`，不继承宿主 provider/代理变量，不启动模型会话。
stdout 仅解析 token，stderr 原文丢弃；合计输出上限 64 KiB，刷新有限超时，所有退出路径有界清组。
非零、超时、空值、非法字符、多行或 `sk-` 前缀均领取前拒绝；声明决定模式，不能嗅探后改选认证模式。
原最低有效期至少覆盖 attempt 超时再加 600 秒余量。

沙箱只得到 OPENAI_API_KEY，不得到凭据目录、refresh token、auth 文件或刷新入口权限。
token 不进入 argv、attempt 文件、DB、审计、日志、repr；也不保存前缀、长度、哈希或其他派生值。
Python 内存引用在启动或上下文退出时释放，不承诺对不可变字符串物理清零。
测试对端的 env/argv 观察只在测试进程内，不提供产品转储能力。

### 用户级放置与双阶段握手

`paper_radar.pi_execution.placement.PlacedProcess` 是认证、模型和 collector 的共同放置边界。
构造时仅以固定 `systemd-run --user --scope --slice=paperradar.slice` 启动封装；
要求 user manager 为 running、`Linger=yes`、`paperradar-anchor.service` 为 active。
manager degraded、缺失或异常均拒绝。封装不继承秘密或业务环境，先设置零 core 和
`no_new_privs`，通过 0700 临时目录中的 Unix socket 阻塞等待；对端 pid/uid 由
`SO_PEERCRED` 取得，并核进程组和 `/proc` starttime。

`PlacementTarget` v1 从现有 root 所有 inbox 的 `placement-target-v1.json` 规范字节读取，
包含完整项目 slice 祖先 `(path,device,inode)`、anchor pid/starttime/cgroup、当前
`IPV4_EGRESS` 观察摘要及 resolver 视图路径/摘要。逐次读取同时要求现有短租期
CurrentObservation 的出站摘要匹配且覆盖出站和 observer；不改变历史观察 v1。
`verify_placement(target,pid,start,unit)` 是 observer/collector 可复用的公开 `/proc`/kernfs
核验，不读进程环境或内存。准备句柄还固定本次 scope 的核 ID；slice、scope、祖先、
锚定或受保护目标变化都拒绝，即使路径文本相同。

认证封装先通过同一核验再 exec；模型封装在领取前完成第一阶段、准备后及 preclaim
复核，领取后才执行第二阶段。`execute(...)` 以有界私有 IPC 交付完整受控 argv/env、
隔离参数与安装保护 fd（SCM_RIGHTS），封装先施加 resolver 视图和隔离，再 exec。
普通产品 controller 以 `PTRACE_SEIZE/TRACEEXEC/EXITKILL` 在 exec-stop 核同一
pid/starttime/cgroup、实际 executable、`NoNewPrivs=1` 和软硬零 core，随后 detach；
目标尚未执行其第一条指令，因此认证动作或 prompt 不先于核验。没有 root tracer 或
新的 root Pi 入口；内核、LSM/Yama、userns 或 ptrace 支持不足直接拒绝。
`handoff()` 仅在 PipeSession 接管后移交整组回收权；所有异常路径有界回收，清理失败
保持失败。`recheck()` 供正式消费者在 preclaim 使用；`check_placement_readiness()`
是 doctor 的只读 manager/目标/锚定检查，不创建 scope、不证明未来子进程放置。

`resolver.apply_resolver_view(view,digest)` 是公共只读 resolver 接缝。封印部署提供
`/run/paper-radar/` 下的 root 所有、产品不可改文件；封装在非特权私有 user/mount
namespace 内只读绑定到 `/etc/resolv.conf`，不需要宿主 CAP_SYS_ADMIN。已继承同 inode
视图仅在调用 uid 不可写且摘要相同才复用。非特权 userns、映射、挂载或摘要核验失败
均不能继续 exec；不授额外 capability。离线替身只复用现有系统 resolver，不证明
已部署项目挂载或真实 DNS；确切视图、权限、userns/ptrace 组合与真实出站由
[Live](../roadmap.md#module-live) 封印部署及现场验收确认。模型内层仍不开放 TCP53。

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
构造不执行 I/O。wall clock 同时用于 ScreeningTasks 和准入检查（默认当前 UTC）；run_attempt 的 clock
是协议有界单调时钟。sink 原样交给任务服务，缺省 NullSink；不新增日志类型或 CLI，
产品入口的文件日志与入口守卫接线责任见[路线图 B](../roadmap.md#module-b)。

只读 `prepare_call(tasks, receipt_id)` 通过公共 load_input/load_config_snapshot/build_call
取得预算首次语义与本回执审计；核对同阶段投影而非完整 snapshot ID。通过
`ScreeningTasks.prepare_correction` 只读取得本次领取的受控修正（含将要发生的过期
回收），验证包含该修正的实际外层 RPC 帧、系统指令路径和单参数 argv 上限、超时
界限、采样映射与当前激活供给事实。修正文案及脱敏字段路径由任务服务唯一构造。
`admission.EvidenceBinding` 保留模型元组、供给/安装、启动/隔离策略及显式代理上下文；
完整请求由 `current_binding.build_admission_request(database, binding, *, use,
credentials_dir, now)` 只读构造。准入用途从本次 boundary/value 与 low/high 精确取得；
未登记档位拒绝，不借其他格的资格。`load_admission_evidence(request, now=...)`
读取[受保护账本和统一分项判定](live-evidence.md)，所有必需项均须当前合格。
旧的不完整 EvidenceBinding 加载继续返回 None；三布尔 `admit` 只保留独立工程判定，
产品不保留 `_evidence_for` 证据别名，不接收证据、授予 factory 或工程模式参数。
explicit 的执行映射仍为空。材料保持系统指令形状、argv 与完整 RPC 帧上限检查，
Prompt/Profile 正文不进入内容无关能力身份。

三检查点依次是：

1. `prepare_launch` 前构造完整当前绑定并判定；缺项、过期、漂移或来源失信不刷新认证。
2. 准备后重新构造绑定并重新读取账本；选择、策略、认证/cache 不变量及站点身份变化拒绝；获准演进字段按共享 v2 基线比较。
3. 领取写事务内以最新修正复核帧，并廉价重读受保护观察与账本，核到期、时钟水位线、
   来源完整性、观察新鲜度/覆盖及撤销状态；不重复扫描安装树、宿主或认证/cache。

前两处全树检查均在业务写事务外；安装保护从准备、auth 到 run_once 返回及整组回收持续持有。
当次只读组件、受保护特权观察和共享 stat 基线规则见 [Live evidence](live-evidence.md#当次完整执行绑定)。
观察的本地上下文不一致时，不拼接旧特权覆盖；显式代理变化也改变启动上下文身份。
领取前认证写回仍仅为专用凭据刷新，另允许阻塞放置封装与清理资源；安全侧固定 helper 打点必须成功，
物理来源丢失／失信、已知绑定漂移或实际运行失败，在业务事务外先持久追加收紧意图、
再请求撤销，helper 失败仍拒绝。单纯观察租期结束、能力自然到期、未测或未激活只拒绝本次执行，
不撤销无关已核事实；同事实的新鲜观察可恢复当前适用性，不续原verified_at或翻转真实撤销。
无法落盘时不宣称已有持久意图，也不会继续执行。来源丢失使用当次先前读取的来源请求保守收紧；首次检查没有来源时收紧本格已有回执，
来源或观察恢复不能复活原资格。
准入分项原因在执行边界映射回既有 evidence_missing/evidence_mismatch 等封闭原因；
领取事务内专用拒绝信号在回滚后映射，不会误报 corrupt_reference。

任一检查点拒绝不新增 attempt、预算消耗、失败行、成功或任务日志；
已发生的有界认证刷新保留既定宿主例外。协议运行失败及接收层结算的 MODEL_MISMATCH 均保持原结算和预算，在业务事务外请求收紧；
已知模型身份不匹配只撤销对应MODEL_IDENTITY资格，保留无关已核站点事实；
retry 是新领取，重新执行三检查点；已经派发的 attempt 不因准入期限跨界新增中止行为。
独立账本恢复不刷新业务余额或自动激活。
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

纯 admission 模块及包导入不连接 auth/launcher/安装保护；完整只读构造入口不导入 auth、
launcher 或执行 service，不刷新、不创建会话或写账本，供诊断复用。
开发期 D7 源码守卫绑定准入/RPC 相关源码和准入、启动、隔离、协议版本。
源码变化须显式升版并审阅清单；当前策略、显式清单及旧版保留规则见
[Live 证据契约](live-evidence.md#β-站点采集与封印部署)。
运行时只绑定策略版本，不对 PaperRadar 源码求哈希，不改变 Pi argv 或协议档案。
覆盖与未验边界见 [#143 台账](../verification/issue-143-pi-execution.md)。

当前观察刷新采用 `pi-admission-v11`：正式三检查点在准备前及准备后请求固定零参数
受保护刷新，领取事务内只读核验。临时失败拒绝本次且不领取 attempt/业务预算；
同一站点观察可用于 low/high，但完整模型身份和每格模型证据继续精确比对。
失败分级和来源边界见 [Live 当前观察契约](live-evidence.md#当前观察与认证cache-基线)。


采集专用上下文只分离封印合成 snapshot 与实际 latest activation 安装，不构造业务 task/attempt 或放宽正式 guard。认证 exec-stop 前释放闸点、prompt 首字节闸点、collector metadata 审计及终态／删除分别核验属于当前启动身份；详细规则见 [固定模型采集闭环](live-evidence.md#固定模型采集闭环)。

## 错误与拒绝

错误只携受控 ExecutionReason，不附输入、路径、token 或外部异常。
未支持采样为 sampling_mapping_unavailable，证据缺失/错配及三类未验分别保留共享准入原因；
固定安装、cwd、凭据、隔离、代理、超时和指令非法在领取前拒绝。
领取后 exec/隔离建立或 cwd/树变化统一沿 startup_error→executor_error 结算。
RPC 四类映射和任务业务拒绝仍由各自权威处理，不新增失败类别或重试器。

## 不提供／不证明

本模块只消费受保护准入事实，不创建证据资格；真实部署与执行验收责任由 Live 统一承担。实际 cwd/祖先目录、固定 1.4.0 入口、订阅刷新、模型权限、参数能力、
TLS/DNS、主机级出站、旗标/settings 的自动网络抑制和 RPC 兼容均未验。
`provider_default` 不能当作 `temperature=0`，采样声明与校准取舍以 runtime-config 契约与[ADR-0040](../adr/0040-declare-provider-default-sampling.md) 为准；
本模块不删除或注入 sampling 参数。
覆盖分母与历史范围见 [#141 独立台账](../verification/issue-141-pi-launch.md)。

## 相关

依据：[#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 最终 B/N/C/D；
[ADR-0039](../adr/0039-isolate-pi-with-landlock.md)、[ADR-0040](../adr/0040-declare-provider-default-sampling.md)。

[供给](pi-supply.md)、[RPC](pi-rpc.md)、[Screening任务](screening-tasks.md)、
[Feed组合](feed-pipeline.md)、[doctor](doctor.md)、
[独立覆盖与收口判据](../verification/issue-140-pi-delivery.md)、
[Screening 分项准入覆盖](../verification/issue-168-173-screening-admission.md)。
