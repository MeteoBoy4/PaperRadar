# #167：真实 Node/Pi 的项目局部解析适配审阅

本文件提交A4/H1准备候选，不授权执行、配置变更、Node/Pi、DNS/TLS、认证或模型调用。原H4的应用可见允许集合不由agent扩大；宿主resolver、core处理和产品身份均保持现状。已撤回准备期基于不完整Apport推导的额外core取舍前提；不要求所有者接受那个错误前提。

## 已核对的实际缺口

- 本机仅选择性读取配置：`/etc/resolv.conf` 的nameserver是127.0.0.53；nsswitch的hosts路径为`files mdns4_minimal [NOTFOUND=return] dns`。只筛选API/Auth两域名的`/etc/hosts`条目均为空，没有读取或输出其他主机名。没有实际查询。
- 已接受的DNS目的仍仅192.168.44.1:53；已有前置检查使用普通Python显式发往该目标，不是Node默认解析路径。
- 按所有者指定docs/docs.json导航核对Pi configuration/settings/environment/CLI，再查args/settings-schema/http-dispatcher。未发现可保持现有入口形状而指定resolver的已登记开关；httpProxy是代理URL，不能当作DNS设置。
- 固定dispatcher未传custom lookup，其Undici HTTPS connector使用hostname。官方[Node DNS文档](https://r2.nodejs.org/docs/latest-jod/api/dns.html#dnssetserversservers)说明默认lookup采用OS解析，setServers不改变lookup；[CLI文档](https://r2.nodejs.org/docs/latest-jod/api/cli.html#--dns-result-orderorder)的dns-result-order仅排序，[Net文档](https://r2.nodejs.org/docs/latest-jod/api/net.html#socketconnectoptions-connectlistener)描述默认lookup。没有运行Node/Pi。
- 因而在当前允许集合下，不能把本机stub路径当成已经放行，也不能把Python显式DNS/TLS结果迁移为Node/Pi兼容。模型内层Landlock还仅放TCP443及显式proxy_port；TCP DNS53并未因此加入。

这不是原core第三路的反证。现有服务未增加下列绑定；该问题是新的部署候选会改变事实适用性，必须在实施前说明。

## 具体候选与差异成本

| 候选 | 最小差异 | 对既有边界的影响 | 实施前必须核对 |
| --- | --- | --- | --- |
| A：项目unit专用resolver文件只读绑定 | root-owned本次配置文件仅含`nameserver 192.168.44.1`；unit添加`BindReadOnlyPaths=<本包受保护文件>:/etc/resolv.conf`，不改全机文件、Pi argv/env或安装树 | 保持冻结的应用DNS目的，systemd会建立mount namespace；Apport还存在system.slice例外，不能仅凭namespace inode不同推断提前忽略 | H1核对新服务namespace、实际system.slice归属、collector完整判定及限额；仍显式RLIMIT_CORE软硬0和LimitCORE=0，不修改core判据或把源码推导标为现场通过 |
| B：明确增加本机stub的外层DNS例外 | 在当前范围外新增127.0.0.53的UDP/TCP53；保留宿主resolver和原mount布局 | 改变刚冻结的允许集合；stub上游请求不属于worker cgroup，必须明确这个可信中介及绑定，不能说都受项目表约束 | 所有者显式修订H4范围；冻结实际stub/上游适用性与漂移行为，再给具体H1计划 |
| C：项目cgroup DNS重定向 | 独立项目NAT规则把stub目标转为router；不预设可仅凭一条规则工作 | 应用看到的原目标与filter/NAT后目标不同，需要重新表述证明边界；回程、源地址、hook顺序以及是否需额外配置未验证 | 先证明能保持项目范围，不增加全机sysctl/路由例外；不能以“已有NET_ADMIN”推定获准 |
| D：新Node lookup/dispatcher/loader策略 | 改运行时接线或入口以替换resolver | 属于新的启动/观察器取舍，当前H4没有批准；不是配置小修 | 若确有必要另给身份、影响及重验范围，不能悄悄纳入 |

当前按既定允许集合准备A，作为仅影响项目服务的H1候选，不增加网络目标或产品启动身份；具体root变更与现场仍另审。B/C/D不作为默认fallback；若A需要新的权限、改变已定边界或出现反例，再提交具体H4。所有者不需重复选择已经确定的网络/core方向。

## A 的 namespace/core 适用性须完整核对

本机systemd.exec文档确认BindReadOnlyPaths隐含mount namespace，但当前Apport的`is_same_ns()`在inode不同时继续检查cgroup：以`/system.slice`开头时返回True。当前服务计划正严格绑定`/system.slice/<unit>`，所以不能套用遗漏此例外的泛化结论。`_check_global_pid_and_forward`使用的是该完整函数的结果，不是直接比较两个inode。

已对当前SHA绑定源码仅AST提取两个原样函数，以合成ProcPid数据回放：system.slice及其子组即使模拟mnt不同，same_ns=True且不提前退出；非system.slice控制组同条件会提前退出。没有导入/运行Apport主程序、真正读取进程内容或制造崩溃。这纠正的是推导，不是新的core现场通过证据。

采用A仍保留双层零core限额及原第三路，不回到其他core路线、不重跑原C对照或EXP-2。新H1包需检查实际namespace/cgroup和当前collector源码/配置、UID/可执行路径及限额的适用性；缺失或漂移则unknown停止，不能因一个例外泛化为全部条件已经满足。长期doctor责任保持后续工程。

## 本轮不隐含处理TCP53

四个候选都不能把外层允许TCP53等同于模型内层已放行。当前内层保持原状；下一份无秘密计划须明确验证实际DNS路径与该限制的适用性。若确需新增内层端口或改变隔离身份，拿具体事实另审，不将其藏在resolver设置中，也不改产品LAUNCH_POLICY_VERSION/pi_protocol或重跑EXP-2。

本轮已完成新服务规则与观察窗口的纯逻辑接缝、真实inotify和合成Python factory接缝验证；这些可独立保留。下一步据此准备明确的H1包，不用占位模板索取泛化执行许可。上述本机配置是本轮只读快照，下轮启动前仍须复核。
