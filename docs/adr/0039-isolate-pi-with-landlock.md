# 用 Landlock 与 no_new_privs 约束 Pi 执行资源

状态：已接受；日期：2026-11-01；依据：[#140 B1–B9/N1–N7](https://github.com/MeteoBoy4/PaperRadar/issues/140#issuecomment-6559173126)、[C/D 确认](https://github.com/MeteoBoy4/PaperRadar/issues/140#issuecomment-6559284609)、[#141](https://github.com/MeteoBoy4/PaperRadar/issues/141)。补充 [ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md) 和 [ADR-0029](0029-protect-installations-through-inherited-flock.md)，不改变其 RPC 接收权威与安装保护规则。 验证责任与当前证明边界见[Pi 当前覆盖摘要](../verification/issue-140-external-review-followup.md)，正文保留接受时上下文。

Pi 的空工具列表、禁发现旗标和隔离 settings 不能阻止 Node 或扩展访问业务文件，chmod 和进程组也不能提供文件权限边界。
V1 需要实际可观察的最小权限，同时不引入固定供给之外的另一套命令运行平台。

采用 Linux Landlock 与 `no_new_privs`，由标准库 ctypes 调用已登记 UAPI。
要求 ABI≥4 以约束 TCP 端口；ABI≥6 追加 signal 与抽象 Unix socket scope。
能力不足或隔离建立失败必须拒绝，不能静默无隔离执行。
逐项白名单及允许权限以 [pi-execution 契约](../contracts/pi-execution.md) 为唯一公开来源，纳入隔离策略版本；
固定安装只读/执行，cwd 只读，仅本 attempt 可写，运行库、证书、DNS 文件、设备与自身进程资源明确列出。

不选 bwrap：它是冻结供给以外的系统程序，身份未被 supply manifest 管理，且可用性依赖部署机 AppArmor profile。
不选 user namespace/netns：当前本机非特权 user namespace 受限，不能以本机存在 unshare/bwrap 推断现场能力。
Landlock 不需要特权或额外依赖，但不能限制 TCP 目标主机，且 TCP 规则不覆盖 UDP/DNS。
本票仅允许 TCP 443 和显式代理端口，将主机级出站约束保留给 Cwd/Live；不能宣称这已是通用网络沙箱。

宿主 OAuth 刷新与模型沙箱分别运行：前者只接触专用 owner-provisioned 凭据目录，允许一次有界网络刷新写回；
后者只得到短期 OPENAI_API_KEY，不能读取 refresh token 或 auth 文件。
代理只写本 attempt settings；完整 env 白名单不继承个人配置或其他凭据。
刷新是领取前唯一获准的宿主副作用，任务/预算/失败/成功事实仍为零写入。

代价是 Linux 专用、依赖内核 ABI，文件白名单需要真实 TLS/DNS 验证；pre-exec 隔离和安装保护也不能替代部署机 Cwd/Live 证据。
本机能力原型观测 ABI 8、no_new_privs 与文件允许/拒绝，后续真实标准库子进程覆盖文件和端口边界。
这些工程证据不证明真实 Pi 1.4.0、认证、参数生效或自动网络抑制；产品仍缺证据即阻断。
策略有反向放宽需求时必须换版本并复核证据，不允许根据一次合成对端成功扩大权限。
