# #167 A4：部署候选（供 H1 审阅，未部署）

本方案只针对 PaperRadar。基线 `c0bee235f4ebb0a88be4a60c392c96619ec61683`；采用现有 Landlock 文件白名单作为内层，增加项目专用 system service/cgroup 外层。本文是候选，不是已实现 Contract。未安装 unit、加载 nft、创建 `/srv/pi-cwd`、联网或执行 Pi。

## 服务与权限差异

将宿主认证 worker 与模型 worker 分为两个 oneshot unit，均 `Restart=no`、`KillMode=control-group`、`SendSIGKILL=yes`、`TimeoutStopSec=10s`、`RuntimeMaxSec=330s`、`UMask=0077`、`NoNewPrivileges=yes`、`ProtectSystem=strict`、`ProtectHome=yes`、`PrivateDevices=yes`、`LimitCORE=0`、`CoredumpFilter=0`、`Delegate=no`。不使用可自动重启的 timer/socket activation。每次 worker 新建 unit/cgroup，清空后注销，失败不重启、不追加预算。

候选资源表（真实路径须由所有者补齐并封印；未填即禁止启动）：

| 边界 | 认证 worker | 模型 worker |
| --- | --- | --- |
| 身份 | 所有者明确选定的项目 uid，专用凭据归此 uid | 同项目 uid，额外 Landlock 不开放凭据 |
| cwd | 专用认证目录 | 唯一 `/srv/pi-cwd`，逐祖先 lstat/owner/mode 与资源扫描 |
| 只读 | 固定安装、运行库、证书、必要 DNS 文件 | 同左及 cwd；精确遵循当前 Landlock 白名单 |
| 可写 | 仅专用凭据目录，临时状态不得含普通备份 | 仅本 attempt；父编排器负责受控证据根 |
| 业务根/个人目录 | 不可见 | 不可见；不得以 ReadWritePaths 放开整个 `/tmp` 或 `/home` |
| 出站集合 | 冻结的认证端点 | 冻结的模型端点；不能访问认证端点 |
| 时间 | auth 30s（启动前核对已配置值） | 实际墙钟300s，回收另10s，绝对上界330s |

认证 worker 的外层只读挂载不能充当读取白名单：候选另用项目专用 `RootDirectory=@AUTH_ROOT@`，只绑定实际固定安装、Node运行库/证书、必要解析文件和专用凭据目录到与封印相同的绝对位置；`BindReadOnlyPaths=@EXACT_AUTH_READ_BINDINGS@`，`BindPaths=@EXACT_CREDENTIAL_BINDING@`。新根仅有预建空目录与必要设备，不能把宿主 `/`、`/home` 或整个 `/tmp` 绑定进去，不挂宿主完整proc。凭据目录为唯一可写绑定，运行库符号链接目标/设备与刷新实际依赖逐项封印。`ProtectSystem`/`ReadOnlyPaths` 只限制写，不能据此称其他可读路径不可见；实际读取面由该专用mount根和负对照验证。RootDirectory与固定入口/继承锁/认证TLS是否兼容本轮未测，若须扩大白名单或更改启动器身份先H1/H4，保持不能认证。认证不直接套用模型Landlock（后者不开放凭据）。

当前 `prepare_launch` 在一个宿主上下文完成刷新与模型启动；**现有产品尚不能直接拆成上述 unit**。需要实验专用编排/最小 token 内存传输桥，不用 shell/文件/env dump传递。安装保护 fd 必须贯穿两个 worker 及其后代直到回收。服务 uid、mount 可见性和锁传递不兼容时停止，不通过放开 HOME 或改 owner 偷渡。H1 需审阅最终路径化 unit、桥接代码及差异；本候选不足以直接安装。

## 主机出站、UDP/DNS、IPv6 与漂移

每 unit 配置 `IPAccounting=yes`、`IPAddressDeny=any`，只允许该角色冻结的精确 IPv4/IPv6 地址。再由独立项目 nft 表按精确 cgroup v2 身份匹配 output：允许对应端点 TCP443 及必要回包；其余 TCP、全部 UDP（含53/443）、外部DNS与未列IPv6拒绝并计数。不要按共享 uid 过滤，避免影响其他程序；未命中 cgroup 对照或内核不支持即停止。unit 先创建但 worker 保持门闩，规则加载/负对照成功后释放，避免先启动后装规则的窗口。主机已有规则不替换。

DNS 候选为所有者在授权前提供端点解析结果与独立 TTL/解析来源，模型不做实时 DNS。只读 hosts 或等价显式解析材料须精确绑定，不能忽略 Node 实际解析路径。若必须使用本地 resolver，单独 H4 审阅指定 resolver/端口、其出站与逃逸负例；不得直接打开所有 UDP。双栈分别正负对照；不启用 IPv6 时必须证明相应 socket/路由被拒绝，不能写 not_assessed 后放行。

IP 白名单不证明域名身份；fake-IP/透明代理可能把同IP流量转给其他目标。先核对现有代理/解析模式，不读取认证或解密流；无法绑定实际端点则 H4，禁止沿用 EXP-2 对透明代理的接受作为新许可。解析、证书信任、代理、内核/boot、端点集合、策略或 unit 变化使对应隔离证据失效。

## core 边界

`LimitCORE=0`、`CoredumpFilter=0` 只是附加措施，不单独证明 pipe core handler 不收集秘密。前轮提出的 pre-exec `prctl(PR_SET_DUMPABLE, 0)` 已由[本轮无崩溃探针](../../../docs/verification/issue-167-core-feasibility.md)否定其充分性：普通exec后实际重置为1，no_new_privs不能阻止。该候选不得用于认证或模型执行；不需要制造一次崩溃来证明此重置。后续必须先经H4选择覆盖秘密全生命周期的具体替代，再提供无秘密验证与H1实施差异。特权/可改变身份 exec 一律禁止。崩溃测试只用无秘密合成哨兵，先认证空白 worker，再模型 worker，各1例；只观察专用回执/文件元数据，不读任何已有 core 内容。

若无法证明全过程不会产生含秘密 core，需 H4 决定项目专用 handler/可执行路径级路由的可行方案；**不改全机 core_pattern，不接受临时全机丢弃作为持久解法**。未经 H1 审阅的 handler 或启动策略变更不能自动加入。候选依赖 Node 实际行为，当前未验证，不能供认证调用使用。

## 回收与恢复（由 H1 审阅执行）

1. 开始前保存项目 unit/nft/cgroup/权限的无秘密基线及精确差异，确认没有重名资源。只备份配置，不备份认证、进程环境或 core。
2. 超时/中断/计数失明立即关闭 worker 门闩、停止对应组，等待 cgroup 空；独立观察 attempt 终态集合，随后父编排器删本次目录并独立观察删除。任何失败保留受控失败事实并隔离残留，不复用目录。
3. 先证明所有后代结束，再移除本轮精确 nft 元素、unit 与桥接资源。不能按前缀批量杀进程/删目录；不能先卸防火墙留下活进程。
4. 卸载只删除本轮新增项目 unit/drop-in/nft 表；对已有项目配置恢复备份，daemon-reload 后证明项目无自动激活、cgroup空、nft差异恢复、cwd与凭据权限未变。其他程序 core 行为应与前测相同。清理失败停止所有后续轮次。

## AFK 核查依据与未验

只读核对当前 `pi_execution/{isolation,auth,launcher,process}.py`、`docs/contracts/pi-execution.md`、本机 `/usr/share/man/man5/systemd.exec.5.gz`（ProtectSystem/ReadWritePaths/LimitCORE/CoredumpFilter）、`systemd.resource-control.5.gz`（IPAccounting/IPAddressDeny），未启动系统工具或改宿主。这些支持候选形状，不证明本机 systemd/kernel 支持、nft cgroup匹配、DNS/TLS可用或core零泄漏。H1/H3 逐项补测；不能降级放行。

## 配置候选字节形状

以下为 H1 路径化前模板，`@…@` 均为必填封印值，不得传给 systemd。未提供自动安装脚本。

```ini
[Unit]
Description=PaperRadar isolated probe worker
[Service]
Type=oneshot
User=@PROJECT_USER@
Group=@PROJECT_GROUP@
WorkingDirectory=@ROLE_CWD@
ExecStart=@ABSOLUTE_REVIEWED_WORKER_ENTRY@
Restart=no
KillMode=control-group
SendSIGKILL=yes
TimeoutStartSec=330s
TimeoutStopSec=10s
RuntimeMaxSec=330s
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateDevices=yes
ReadOnlyPaths=@INSTALL_ROOT@ @ROLE_CWD@
ReadWritePaths=@EXACT_ROLE_WRITE_ROOT@
InaccessiblePaths=@BUSINESS_ROOTS@ @OTHER_ROLE_SECRET_ROOTS@
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LimitCORE=0
CoredumpFilter=0
Delegate=no
IPAccounting=yes
IPAddressDeny=any
IPAddressAllow=@EXACT_ROLE_IPV4@ @EXACT_ROLE_IPV6@
StandardOutput=null
StandardError=null
```

不加 `[Install]`，无开机自启；输出由编排器专门匿名管道仅接收白名单元数据，不用 journal 接收模型/认证输出。模板的 `ReadOnlyPaths`/`ReadWritePaths` 不替代内层 Landlock；认证与模型角色分别生成两个文件，任何多余可写根均拒绝。

nft 的候选规则形状：项目独占 `inet paperradar_probe167` 表，output hook 中按 `socket cgroupv2 level @DEPTH@ "@EXACT_CGROUP_PATH@"` 选择角色，匹配 `ip daddr @ROLE_V4_SET@ tcp dport 443` 或 `ip6 daddr @ROLE_V6_SET@ tcp dport 443` 才 accept，之后对该角色 `counter reject`。集合只含字面精确地址，不用域名、网段或共享 uid。IPv6未使用时集合空且拒绝负对照成立。具体 hook priority 必须结合现存规则审阅；该规则不能覆盖主机更早的drop，允许对照不通也停止，不能删除原规则。nft版本/内核不支持 socket cgroupv2 表达式时 H4，不换成按uid。

H1 应先 `systemd-analyze verify` 最终路径化文件和 `nft --check` 最终规则，再人工审阅加载；这些现场命令本轮未执行。必须同时审阅门闩、计数器、PR_SET_DUMPABLE worker、最小传输桥接具体实现；仅复制模板不能满足 H1，也不授予 H2。

后续可执行性审查见[剩余决策](remaining-decisions.md)：同uid进程内存隔离、跨unit原OFD传递、token桥与完整请求观察仍有阻断，模板不构成可安装方案。

所有者随后明确不批准core前置过滤器原型：不得从本候选推定全机分发链许可。当前只读事实与待终局的差异化成本见[core比较](core-cost-comparison.md)；不因loader离线原型获准而采用新生产启动策略。

最新H4终局采用ADR-0049的第三路：项目持密子进程exec前显式设置软硬RLIMIT_CORE=0，服务LimitCORE=0；不以pre-exec dumpable替代，不制作全机分发器。对应合成C两例见[验证](../../../docs/verification/issue-167-final-core-validation.md)。当前模板已有LimitCORE=0，但没有安装服务；实际产品auth/model pre-exec限额接线与部署仍需后续工程/适用H1，不因实验通过就声称已经实现。root内存瞬时读取残余按裁决接受，Apport版本/配置漂移长期doctor检查另承接。

计数终局不采用本候选的新启动身份；loader不接线、不用作真实覆盖、不开启新transport。按ADR-0048披露可证下界/unknown与Pi token用量，精确计数交I。
现行网络范围按 [ADR-0050](../../../docs/adr/0050-bind-egress-to-owner-visible-addresses.md) 与 [DNS/TLS 计划 v1](real-exit-dns-tls-v1.md)；旧网络模板保留为早期候选，不作为当前规则或执行许可。

