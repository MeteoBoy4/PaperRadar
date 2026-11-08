# #167：恢复闭合与 IPv4-only 待审包

本轮属于 A4/A6/A7 准备与已批准的固定恢复回记。承接 [v4 现场及恢复包快照](issue-167-h1-v4-recovery.md)，该历史文件及原封印、账本不改。本轮没有追加现场探针；下述新 H1/H3 尝试仍须所有者明确批准。

## v4 一次性恢复已闭合，实验仍 unknown

所有者收到一次性 H1/H4 数字身份例外请求和封印包后报告「已运行」。固定恢复回执的 scope=h1_fixed_recovery_exception_only、run=a840c6d21e97、restoration_result=host_policy_restored、experiment_result=unknown、probe_attempts/auth_calls/model_calls=0；明确 original_numeric_binding=unknown_owner_exception，原账本、runtime、code 保留。回执 SHA256=`16c47334bde5fc68524a5770879b3f13757510683eeefb1a073be465702c8e9f`。

主代理普通用户独立复核：两份精确 unit fragment 和两个 cgroup 目录均 absent；manager 两个 Id 均为 not-found/inactive/dead、MainPID0、FragmentPath/DropInPaths/ControlGroup 空。结果保存于 `.scratch/issue-167/h1-recovery-a840c6d21e97-v1/post-recovery-readonly.json`。本表 absent 和原账本 SHA 不变由已审 root 恢复脚本在返回成功前核验，本轮未另获 root nft 查询，不把普通用户观察说成独立 root 枚举。所有者恢复预占保留，不重跑。

原 v4 的 IPv6 TCP 超时、阶段材料不足、B/UDP/DNS/遗留后代未完成保持原结论；恢复成功不回写原 cleanup_complete 字段、不使实验通过。v2/v3/v4 均已消费，不退款、不清理或重建历史链。

## 所有者允许收窄为 IPv4，本轮采用

所有者明确「如果 IPv6 被拒绝或超时，可以裁决只走 IPv4，不需要确保双栈」。根据 v4 已观察的超时，本轮将新的受支持候选收窄为 IPv4-only，不再要求 IPv6 可用的正例。不是将超时判为成功拒绝，也不是把尚未观测的 IPv6 出站任意放行。

- 新 plan 显式封印 network_mode=ipv4_only、addresses=[127.0.0.1]；默认旧 dual_stack plan 形状保留，不能省略字段而默认成 IPv4-only。它是审阅原型计划字段，不是产品 LAUNCH_POLICY_VERSION 或 pi_protocol 注册变更。
- worker RestrictAddressFamilies=AF_INET；guardian 为 AF_UNIX AF_NETLINK AF_INET。两 unit 的 IPAddressAllow 仅127.0.0.1/32；独占 inet 表只允许当前阶段 IPv4 地址/端口，末尾 reject 保留。peer 只建两个 IPv4 listener，无 IPv6 listener、域名解析或外部端点。
- 每阶段先检查 IPv6 TCP/UDP **socket 创建**被拒绝，再做5个 IPv4 网络案例。创建成功立即阻断，构造 EPERM/EACCES 或明确不支持该 family/protocol 才是创建拒绝；close 失败、timeout、网络 unreachable 均不能冒充创建拒绝。IPv6 不 connect/send。
- IPv4 当前端口 TCP 正例、其他阶段/blocked TCP、blocked UDP、UDP53 负例保持明确 allowed/denied；unknown 停止，不补发或自动换目标。UDP53 仅固定单字节 P，不构造 DNS 请求。
- guardian 独立核对7行精确元数据；IPv4 packet 参照每阶段 allowed>=1/rejected>=4，只对应1个允许与4个拒绝网络案例。两项 IPv6 创建检查没有报文，不能计入 nft/HTTP 数。owner collector 也从受信 plan 读取模式，不能让结果自报模式降低门槛；旧双栈2/8判据不变。

这只验证新合成部署形状，不证明真实供应商有可用 IPv4 端点、DNS/TLS 可行或真实 Pi 继承边界。RestrictAddressFamilies 限制创建，本包不传入网络 FD；不外推既有恶意 socket、其他服务或真实 Pi。后续真实端点与产品证据绑定仍须 H1/H2/H3 适用授权，不允许自动 fallback 到双栈或改变产品启动身份。

## 停止后归属核验的离线修复

新实现保持原严格路径 verifier。创建规则时，在 live 精确 cgroup2 路径 fd-relative/nofollow 打开目录，独立 fstat 读取 dev/inode，fstatfs 确认 cgroup2，前后核对身份不变；原严格路径验表通过后、任何 go 前，原子发布 root0600 runtime/table-binding.json。它绑定 plan SHA、boot/kernel、精确 cgroup dev/inode，以及 table/scope/chain/counter 的稳定 handles。

官方 [Linux v7.0 nft_socket.c](https://raw.githubusercontent.com/torvalds/linux/v7.0/net/netfilter/nft_socket.c) 取 cgroup_id；[cgroup.h](https://raw.githubusercontent.com/torvalds/linux/v7.0/include/linux/cgroup.h) 返回 kn->id；[kernfs.h](https://raw.githubusercontent.com/torvalds/linux/v7.0/include/linux/kernfs.h) 在64位 ino_t 返回同一 id；[inode.c](https://raw.githubusercontent.com/torvalds/linux/v7.0/fs/kernfs/inode.c) 用该值建立 inode。实现限定本机 x86_64/64位 ABI，不对32位泛化。这是明确上游版本的源码依据加 mock，不冒称逐一证明发行版 patch 或新链路已现场通过。

停止后只接受原精确路径或保存的**精确数字 ID**；stable handles、boot/plan 和全部原规则结构仍须一致，packet 值不封死。切 phase、计数、guardian cleanup 和 owner restore 均核对绑定。坏绑定不退回宽松路径；缺绑定只允许原严格路径，numeric 仍 unknown。没有从当前表自报的数字推定原身份，不复用 v4 一次性归属例外。

实际 LiveOperations 创建/停止后 cleanup 与 owner restore 的 mock 反馈环先失败后通过；漂移/错 ID/缺绑定/坏绑定/句柄重建均拒绝。新增加的受控原因 cgroup_identity_unknown、table_binding_unknown 同步到 owner collector。未增加 cap、mount namespace 或系统策略。创建中断、绑定尚未完成、SIGKILL 或无法验证归属仍可能需要所有者恢复裁决，不能保证任意故障自动恢复。

## 新的具体待审包

`.scratch/issue-167/h1-synthetic-ipv4-v5/`，run=`b6302f9a47e8`；先读 owner-review.md、review-seal.json 及 root guardian/恢复代码。新 run 是待申请的额外一次尝试，不自带余额。

| 身份 | SHA256 |
| --- | --- |
| review-seal.json | `ec7e705f598966b1056a76f879880f6f126e09e5d55f0b84600deca9d7bb4a6e` |
| core manifest | `7003a4c538037603d1dbf2595341fcfda51bf8351cfe659e0976cce018faca2d` |
| automatic owner driver | `052eb5d9ea103945f645aca8eaf878390d75ea3c307b815035edcc24567bc5c3` |

精确资源：两个 unit 为 paperradar-167-h1net-b6302f9a47e8.service / paperradar-167-h1guard-b6302f9a47e8.service；唯一表 inet paperradar167_b6302f9a47e8；代码 /home/paperradar-probes/issue167-b6302f9a47e8、runtime /run/paperradar-issue167-b6302f9a47e8、永久单次账本 /var/lib/paperradar/probe-runs/issue167-b6302f9a47e8.json。其余 UID1000、六项 root cap、空 Ambient、NNP/seccomp、零 core、直接 fork、无 Delegate 与恢复边界保持。

两阶段合计最多10个 IPv4 网络案例：6次 TCP connect，4次 UDP connect 及对应4次单字节 send；UDP connect 本身不发送报文。这是案例上限，不把14个 connect/send 调用混称10个系统调用。另最多4次 IPv6 socket 构造检查，无 IPv6 connect/send。端口仍 A38167/B38169/blocked38168、UDP53；正例 peer 只返回固定 OK。不新增认证、模型、Pi/Node、崩溃或外部网络。首次 unknown 停止，不自动重试/退款。B 后遗留不同 session 同 cgroup 子进程的拒切阶段、停止回收案例保留。

retry-context 明确指向 v4 unknown，前驱 manifest=64fa5e6b65119a0d60eee1f57565c41675887e4ebd7d4f266bfeaaf4c606fba7。前驱 ledger 预期 SHA=`46662ec9969996fa0a5a490380a2a9520fcb1b7428b4e7728d20690e0105af37`，由已读取 owner envelope 按原 root 发布器 sort_keys/default separators/LF 重建，未冒称普通用户读过 root0600 原字节；新 root preflight 必须实际匹配，不一致即停止且不修改旧记录。所有者接受的旧错链不被静默重建。

入口仍由所有者运行 owner-wizard.sh，唯一一次 sudo 从 TTY 取密码；不执行工作区 Python 文件，先核验字节再进入 root-owned runner。成功时核对清理并仅 finish 本次 runtime/code，永久账本保留；失败保留材料和 unknown。IPv4 方向已采纳，**新增这一次 H1/H3 现场尝试尚未批准或执行**，不要求所有者重复裁决双栈取舍。

## 工程验证与边界

相关 H1 组合 **315 passed**。原15个模块242项不扩历史结论；本轮新增独立 D1：test_issue167_h1_ipv4_only.py **26**、test_issue167_h1_ipv4_reconcile.py **7**、test_issue167_h1_ipv4_cli.py **1**、test_issue167_h1_bound_recovery.py **39**。真实 generator CLI 的 IPv4 mode/前驱封印回归、接收端7行/计数回归均先红后绿。追加包内审阅文字后，auto_bundle/CLI 定向组合13项再次通过。

30个相关 Python 文件 Ruff check/format、mypy 通过。21/21 core 成员、core/driver/seal及工作区来源匹配；bash -n 通过。仅将 /tmp 语法副本 ExecStart 解释器替换为已有同字节副本后，普通用户 systemd-analyze verify 退出0；没有安装原 unit，原包仍需 root runner 安装后的原 unit 检查。fresh subagent 独立审阅代码与最后封印材料，不运行入口。

CLI 兼容组合的首次入口被默认只读 uv 缓存阻断，测试未启动；指定 /tmp cache 后 **59 passed、退出0**。显式 base=c0bee235f4ebb0a88be4a60c392c96619ec61683、target=refs/heads/main 的只读固定 scope 审计含 collect 退出0，issues/affected_groups 空、skip/deselect0；最终文档树再审计后随票回记。不扩分母、required 或正式回执。未运行完整离线门禁，产品缺证据仍阻断，Live/B 状态不变。剩余真实身份/供应商/外部中断/超时、正式校准、NAS 与产品激活均未获本轮授权或验证。
