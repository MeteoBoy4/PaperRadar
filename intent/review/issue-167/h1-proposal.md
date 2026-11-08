# #167 H1：保留直接 fork 链的最小无凭据现场包提案

本提案只准备可审阅差异；未运行systemd/nft、root命令、Node/Pi、认证、模型、网络或新崩溃。只读当前产品与明确的旧实验源码，不读认证目录、旧成功/失败输出或core内容。依据最新ADR-0048/0049，不引入loader、新Pi启动策略身份、全机core处理或精确请求计数；不要求重跑EXP-2。

本轮已形成具体现成审阅包及离线验证，见[H1-1台账](../../../docs/verification/issue-167-h1-synthetic-local.md)。旧下表中的候选范围不自动扩成执行许可；当前包精确覆盖双phase/文件/遗留后代组合，其他现场故障仍未验。

## 当前源码已经提供的拓扑

旧EXP-2并非auth/model双unit。`admin/rpc_first_probe_v2.py:173–232`、`rpc_matrix_probe_v1.py:175–234`在**一个worker unit**中启动受审Python controller；`prepare_launch`及其auth/model子进程均由该controller直接fork。worker在`auth-prepared`之后等待`api-go`（首轮`:269–304`，矩阵`:259–290`），unit外的所有者管理程序在这两道门闩间原子切换同一nft phase链（首轮`:371–389`）。`rpc_first_support_v2.py:200–227`按精确unit cgroup选择phase链，`:322–330`独立检查unit状态与cgroup populated。

因此本轮可沿用“**单controller unit、串行角色phase、外部特权规则管理**”形状，保留`prepare_launch/use_install/Popen(pass_fds=...)`的同一OFD和现有token私有内存路径。没有跨manager传锁或秘密传输需求，**无需为了这条路径实现SCM_RIGHTS broker、双unit token桥、manager credential或Delegate**。旧脚本仅为形状依据，不直接重跑或复用旧授权/余额/封印。

需要去掉的旧实验依赖：全机`core_pattern=|true` guard；固定IPv4-only与旧fake-IP/DNS绑定；取完整历史JSON作为新事实的做法。新core约束是产品子进程pre-exec零软硬限额及unit `LimitCORE=0`，没有任何全机core guard。精确HTTP缺口按ADR-0048披露，不把nft counter当HTTP计数。

这条最小拓扑是对现有父子关系的保持，不是新Pi运行入口。H1仍须审阅全部unit/规则/guardian代码；本文不授予安装或现场执行许可。

## 文件与边界矩阵

建议先只生成 **无凭据、无Node/Pi、仅受控loopback对端** 的审阅包。它可以先完成部署隔离与回收负对照；真实端点和凭据均不进入这一包。

| 文件 | 具体内容/拒绝条件 |
| --- | --- |
| `plan.json` | 明确`mode=synthetic_local`、`approval_state=not_granted`、固定case清单/单次上限、绝对路径、uid/gid、unit/table名字、超时/停止/回收顺序；不含凭据路径、token、真实外发地址或自动重试 |
| `manifest.json` | 所有审阅文件、产品触及源码、合成worker/guardian的逐文件SHA，以及目标host/kernel/boot/cgroup绑定；不是产品证据或自动执行授权 |
| `controller.service` | 下文最小unit；调用本包固定synthetic controller，不调用Pi/认证；`Delegate=no`、无自动重启/自启/套接字激活 |
| `guardian.service` | 精确unit生命周期/phase门闩、nft与cgroup元数据守卫；无凭据读取、无秘密输入，不监听对外网络；worker `BindsTo/After` 此guardian；root代码须逐字审阅，不能只是占位脚本 |
| `phase-deny.nft` | 创建本包独占inet table/output链，仅匹配完整cgroup路径；默认匹配后reject；不改其他表/全局policy |
| `phase-a.nft` / `phase-b.nft` | 原子flush并重建本包phase链；仅精确loopback地址和当阶段端口允许，其他TCP/UDP/IPv6均拒绝并计数 |
| `synthetic-worker.py` | 标准库合成父子/后代、固定字面哨兵、无外部网络；实际待执行动作是H3受控loopback测试，当前只写源码/离线测试 |
| `guardian.py` | 严格plan/schema/文件归属与SHA；元数据只读核验和本包表的有限操作；拒绝任意命令/路径、超时和错误状态；不import用户可写runtime中的Python |
| `install.sh` / `run-synthetic.sh` / `restore.sh` | 所有者人工审阅执行；精确白名单路径和表/unit，先验证冲突与字节、后安装/单次运行；恢复先停尽全部进程再撤规则，无宽泛前缀删除 |
| `expected.json` | 每case的受控allow/deny、scope/目录/限额/回收预期，不从实际结果推导预期 |
| `owner-review.md` | 每个root动作的精确差异、影响/恢复、默认不执行；独立H1/H3审批块与后续H2明确分开 |

生成器应拒绝缺文件/占位符、非绝对路径、路径重叠/symlink、不匹配uid、宽网段/非loopback地址、开放UDP或真实provider地址、使用全机core命令、包含loader注入/新Pi启动身份、不可验证的guardian/worker字节。缺实现不能产出`ready_to_install=true`；只写模板不能提交“请批准安装”。

特权执行文件应由所有者安装到精确root所有、普通用户不可写的包目录（例如`/etc/paperradar/probes/<review-name>/`），不能让root直接执行工作区可变脚本。包源与实际安装字节必须相同；运行时只传经校验的metadata，不把caller提供字符串拼成root shell命令。

## 最小unit形状

第一轮的controller只跑合成worker，其真实执行命令形状为：

```text
<absolute-uv> run --offline --locked --no-sync python -I -B <root-owned-fixed-worker.py> --plan <root-owned-plan.json>
```

包生成前准备好离线锁定环境；`--no-sync`避免现场写项目环境、下载或修复。若环境不满足则停止，不fallback到系统Python/个人Pi。此处不是执行命令，也不是把工作区路径当root可信入口。

```ini
[Unit]
BindsTo=<exact-guardian.service>
After=<exact-guardian.service>
[Service]
Type=exec
User=<exact-numeric-uid>
Group=<exact-numeric-gid>
WorkingDirectory=<exact-project-root>
ExecStart=<exact-frozen-command-above>
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
Delegate=no
RestrictNamespaces=yes
SystemCallArchitectures=native
SystemCallFilter=~bpf io_uring_setup:EPERM io_uring_enter:EPERM io_uring_register:EPERM
RestrictAddressFamilies=AF_INET AF_INET6
KillMode=control-group
SendSIGKILL=yes
Restart=no
RuntimeMaxSec=120s
TimeoutStartSec=10s
TimeoutStopSec=10s
LimitCORE=0
UMask=0077
IPAddressDeny=any
IPAddressAllow=127.0.0.1/32 ::1/128
StandardOutput=null
StandardError=null
```

不加`[Install]`，不启用timer/socket。无秘密环境仅明确locale/空白项目HOME/PATH及离线选项；不把token放Environment/EnvironmentFile、unit argv或journal。无凭据轮没有真正token或auth文件，`auth`只是合成阶段名。

避免把新的`RootDirectory/PrivateTmp/ProtectHome/ProtectSystem`挂载设计当必需前置：产品模型侧现有Landlock已有精确文件边界，trusted controller/auth宿主可见性与模型沙箱应分别陈述。第一轮不声称认证宿主具有另一个未实现的OS读取白名单；未来若确有此需求再给具体方案，不先发明双unit/RootDirectory作为硬门槛。

增加mount namespace须核对Apport完整判定：`is_same_ns()`还存在`/system.slice`例外，不能仅凭mnt inode不同推断`_check_global_pid_and_forward`提前忽略。若选额外mount配置，应单列namespace/cgroup绑定、collector适用性和现场验证，不扩大旧C对照的证明范围。`ProtectControlGroups=yes`同样须核对效果；不用它代替`Delegate=no`、空cap、命名空间限制及实际cgroup写入拒绝负例。任何预期拒绝不成立即停止，不临时扩大权限。最新解析绑定审阅见[项目局部适配](resolver-adaptation-decision.md)。

## 文件与同uid进程边界

真正模型仍使用当前`IsolationBoundary`：安装/运行库只读执行、常量cwd只读、attempt所有权单元可写、`/proc/self`只读、无业务根/专用凭据读取许可。controller维持供给保护，auth仅按固定env/入口使用专用凭据；这些都不放进本次无凭据包。

不要把“同uid”直接推成“必须双uid”：本机`landlock(7)`的`Ptrace restrictions`明确有隐式ptrace域关系限制，ABI>=6还可限制signal/abstract Unix；当前实现已有这些scope。旧B02“仅文件规则不能证明所有跨进程访问”仍是**缺少实测**，不是已证明允许。合成负例应在受限model样本内检查对受信父/兄弟的`ptrace`、`process_vm_readv/writev`、`pidfd_getfd`、`/proc/<pid>/mem`及信号访问；用无秘密哨兵与元数据，不读真正内存/凭据。未测或不支持的项unknown，不直接加seccomp/换uid补猜通过。

若实测仍存在不允许的通道，先提交精确反例和服务级denylist/不同uid等代价供H1/H4，不以一次`ProtectProc`或cap为空宣称全部进程内存隔离。模型的Landlock域与父controller不同；受信父需要回收后代，不能反向阻断正常回收。

## phase门闩、原OFD及guardian有限权限

1. 先验证root-owned包/计划和名字无冲突；创建初始全拒绝规则，启动guardian保持其生命周期，再启动单controller unit。guardian先确认实际`ControlGroup`精确为计划路径/层级、unit MainPID/uid匹配，才受理case。不能按共享uid匹配nft。
2. controller不具有CAP_NET_ADMIN、不写cgroup控制文件；所有直接子孙从出生即在同unit cgroup，无需事后迁移或Delegate。供给OFD由controller的`use_install`取得，auth/model沿当前`pass_fds`继承；token不离开当前私有Python/匿名管道，不穿manager。
3. 合成auth阶段规则只放行受控端点A。auth完成且其process group已收尾后，controller保持在门闩；guardian独立核对该unit的递归cgroup成员只剩精确受信controller PID。存在任何未收尾后代、查询不全或身份不符即停机，不切阶段。
4. guardian以单次nft transaction切到端点B，核对本包实际表/规则字节后才释放`api-go`；model仅在该门闩后创建。同unit内的“角色隔离”来自**不重叠生命周期+阶段规则**，不是同时运行两个角色的假想隔离。controller是受信网络静默方，须有源码/行为证据；不把其活动误称模型请求。
5. 正常/异常/外部controller中断均停止worker整unit、等待`inactive/failed`且所有子cgroup populated=0（或确定已移除），再卸本包nft/guardian。guardian失效必须通过BindsTo或独立有界看守停止worker；不得先撤规则留下活动子孙。
6. runtime请求只含closed phase/case/sequence，与计划/单次余额关联。root guardian只接受这些有限请求并操作固定表和unit，不读token、env、model raw、任意路径或以runtime数据执行代码。记录metadata的权限/连续性/丢失拒绝须有离线测试。

guardian需要nft和精确service/cgroup生命周期操作；这些root动作由H1授权，实际由所有者审阅执行。没有manager socket开放给模型或controller任意调用，没有动态sudo许可或新setuid helper。guardian如何安装/运行、root-owned状态与失败恢复代码是包内必须审查的实字节，不能用“已有旧实验guard”替代：旧guard改全机core，已明确不采用。

## 首轮固定合成case和预算

仅受控loopback字面地址，不解析provider域名，不引用旧fake-IP/旧DNS余额。端口可选择计划中的两个未占用固定高端口A/B（例如38167/38169）及负例端口38168；如冲突就停止，不自动换端口/新run。IPv4/IPv6分别明示，nft计数是连接/packet负例，不是HTTP计数。

| case | 预期/本轮上限 |
| --- | --- |
| P01 identity/limits | controller及其固定合成后代实际soft/hard core=0、uid/cgroup匹配、cap为空/no_new_privs=1；不制造新崩溃，不运行Node |
| P02 file/IPC | 临时合成父/兄弟/只读与私有文件，检查既有model Landlock允许/拒绝；不碰业务DB/真实credentials或共享系统资源 |
| P03 phase A | v4/v6连A成功，连B/未列端口拒绝，UDP测试端口/UDP53拒绝；每种各一次，最多7次本地连接/发送尝试 |
| P04 phase transition | auth合成后代全退出，只剩controller；phase切换原子、规则读取完整才放行；故意留一个固定合成后代时必须拒绝切换并回收 |
| P05 phase B | v4/v6连B成功，连A/未列端口、UDP测试端口/UDP53拒绝；与A独立同样最多7次本地尝试 |
| P06 lifecycle | 固定合成后代在不同session/process group仍位于unit cgroup；controller正常/失败/外部中断各按预先冻结的一次case回收；不对真实Pi进程故障注入 |
| P07 metadata failure | 门闩重复、坏phase、缺/乱序metadata、guardian停止、cgroup读取失败、完整性丢失均停止；不退款或换run重试 |

以上case是待H1/H3审的具体计划，不是当前执行许可。合成listener只绑定127.0.0.1/::1；为区分网络拒绝与未监听，允许端点必须独立回显固定字面哨兵，否定case必须核对对应本包reject counter。UDP53负例不得被当成允许DNS，绝不打开任何外部DNS/网段。真实IPv6不可用时unknown并停在此处，不以not_assessed默认放行。

## 生成器必须输出的恢复材料

- 安装前库存：精确目标unit/drop-in/包目录/nft表不存在或已有字节与明确备份；名字冲突拒绝，不覆盖其他项目。
- 任何失败先关闭派发门闩，停止worker整unit，确认递归cgroup空；若不能确认则保留拒绝规则/guardian并报告需所有者处理，不能先卸防火墙。
- 确认全部停止后删除**本包精确**nft表和unit；恢复之前已存在的项目配置（若本计划未授权覆盖则根本不安装）；daemon-reload后检查本包unit不活动/无自启、cgroup/表消失。
- 不碰core_pattern、Apport、whoopsie、系统DNS/代理、其他进程core或服务。上一轮合成正例core的精确清理另列，只由所有者处理，不混入本包通配清理。
- 不归档凭据、模型流、core、完整argv/env或第三方异常。回执区分字段来源、观察窗口与unknown，不能只给passed布尔。

## 未填值与实际下一审批动作

| 未填值 | 原因/如何落到具体字节 |
| --- | --- |
| 最终worker/guardian代码与SHA | 当前只有旧来源和离线原型；新包需要删除全机core/旧授权耦合，并把已裁决元数据语义接入合成流程。没有这些代码前不能请批准安装 |
| root-owned安装目录/unit名与计划case run名 | 由生成器显式参数冻结并做无冲突只读检查；不复制旧EXP-2名字/余额；不是新Pi启动策略身份 |
| 最终uid/gid、project/uv/Python实际绝对路径 | 当前部署者应绑定实际普通用户与prepared环境；controller的**实际解析后Python可执行**也应为/home非打包并核对limit0，不只核对Node。换uid/解释器不能隐式复用core样本结论 |
| 合成loopback端口及IPv6状态 | 明确参数冻结；执行时遇占用/不支持即停止，不扩大目标或自动改值 |
| 现场cgroup路径/层级、nft语法/优先级与现存规则关系 | 在H1批准后的非执行验证与安装前库存阶段查实际值；若不是计划的system.slice/<unit>或不支持socket cgroupv2就停止，不改成按uid过滤 |
| 真实认证/API地址、DNS、透明代理与凭据目录 | **刻意不属于首轮包**。后续H2才需新计划，旧fake-IP/透明代理接受与旧余额不能复用 |

先完成离线审阅包生成器及其负例测试，确保它在缺实现/占位符时保持不可安装；随后向所有者提交**H1：审阅并人工执行这个明确无凭据包的root变更**与适用**H3：一次合成本地验证清单**。不是现在就索取全部授权。只有该轮适用隔离与恢复通过后，才准备H2真实认证/模型材料；当前计数裁决不要求为精确计数重跑EXP-2。

## 常规实施选择与必须停下的选择

- 沿用单unit直接fork、保留OFD/token私有内存、只生成文件/纯函数离线测试、显式失败不重试：可在A4/A6已有AFK范围继续准备。
- 安装unit/root-owned包、nft加载/切换、启动service、合成loopback连接、外部信号/现场回收：提交具体H1/H3，root动作由所有者执行；本提案没有执行。
- Delegate/用户管理子cgroup、跨uid重构、双unit token桥、额外auth mount/read权限、DNS/端点/代理放宽、任意Pi入口/策略身份改变：不是最小方案必要项；若确实出现需求或失败反例，先H4，不作为普通实现细节自动加入。
- loader产品化、精确HTTP计数、全机core分发链：本轮终局已明确不采用/推迟，不重新当作未决阻断或反复要求选择。

## 只读依据

产品`pi_execution/{launcher,auth,process,isolation}.py`及`pi_supply/protection.py`；ADR-0029/0039/0048/0049；旧实验明确源码`rpc_first_probe_v2.py`、`rpc_first_support_v2.py`、`rpc_matrix_probe_v1.py`、`network_probe.py`（仅source，不读历史运行输出）；本机landlock(7)的Ptrace restrictions/IPC scoping与systemd/nft相关手册。上述形状/文档不是新的现场通过证据。
