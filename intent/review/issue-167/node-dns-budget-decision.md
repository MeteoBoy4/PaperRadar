# #167：下一份无秘密 Node 诊断的解析预算取舍

[项目服务显式 Python 网络轮](../../../docs/verification/issue-167-service-network-result.md)已通过并恢复。下一步不重复该轮，拟验证固定 Node 在原服务/模型隔离边界内的查址与 TLS 兼容。本文是 A1/A4/A6 的只读事实与范围选择材料；不授权 Node/Pi、DNS/TLS、服务/root 或真实调用，不修改已裁决的模型请求计数口径。

所有者已回复「A」：仅选定本次无秘密诊断的准备范围，接受所列 OS 内部解析次数与 wire QNAME 未穷尽。开始准备具体代码/封印及离线验证；尚未批准 Node、网络、root 或其他现场动作，实际执行仍另申请 H1/H2/H3。B 不作为默认 fallback。

## 事实及为什么此时需要范围选择

- 按所有者指定的 Pi 1.4.0 `docs/docs.json` 导航复核 configuration/settings/environment/CLI：settings.md:125 的 httpProxy 是代理 URL；environment-variables.md:80–101 与 cli.md:242 没有保持现入口而指定 resolver 的开关。固定 dispatcher 的 `dist/core/http-dispatcher.js:73–83` 只设置 autoSelectFamilyAttemptTimeout，没有 family 或 custom lookup。
- Node 默认 lookup 采用 OS/NSS；调用一次不等于发送一次 DNS。它可能包含 A/AAAA、NSS 动作、重试或 TCP fallback。新一轮不能沿用上轮 A-only/最多5查询预算，不能把 lookup×2 写成 wire DNS×2。
- 本机 resolv.conf(5) 的 timeout/attempts 说明单次 API 不保证单 timeout。仅加 attempts:1/timeout:1 不能证明精确 DNS 硬上限；RES_OPTIONS 又是新的每进程环境覆盖。本方案不改产品 env、解析参数或启动策略来假装保留原路径。
- 当前私有 resolver 仅含一个 nameserver、无 search；额外只读结构检查得到本机 hostname 不含点，未输出其值。手册说明此条件下默认 search 为 root 域。下一包应在启动前重新绑定该结构和 NSS 配置、保持空秘密环境，不能静默带入 LOCALDOMAIN/RES_OPTIONS。此检查不穷尽 NSS 或 wire QNAME，默认 lookup 的内部行为仍按未知披露。
- 现 `IsolationBoundary` 只允许 TCP443/显式 proxy，UDP 不受其网络规则覆盖，TCP53未放行。外层服务允许 router:53 不改变这个事实。下一轮应给无秘密正负对照；若默认查址遇到被拒的 TCP fallback，保留 unknown/失败，不自动放宽。
- lookup 不提供可沿用的 TTL。若做 Node TLS，仍须同轮每域名显式 UDP/TCP 参考共4查询，Node 查址与参考唯一池内 IPv4相符；由父进程 before/after 的保守单调区间把整个 Node 查址/TLS 包在两份参考的最早 TTL 内。过期不补查，旧1秒窗口不可复用。

以上仅静态读取公开文档、源码和系统手册，没有执行 Node、查询 DNS 或读取凭据。事实不否定既定 core 路线，也不要求新 loader、Pi SDK 入口或产品启动身份。

## 两条路及差异成本

| 选择 | 下一份计划能诚实承诺什么 | 新成本与残余 |
| --- | --- | --- |
| A：接受本次诊断的内部解析次数 unknown | 明确默认 lookup 调用2次、固定 api/auth 域名及可能的 A/AAAA/NSS/重试；另有显式参考 DNS4、Node TLS2。冻结单项和总绝对 wall，无应用重试/备用域名；OS 内部 DNS 数未知，不声称满足有限 wire 查询数上限 | 最少新增工程，沿真实 OS 解析实现。所有者须在新 H2 范围明确接受这项未知，不能从模型计数 H4 推定。仍可能因 TCP53/TTL/资源或解析失败而 unknown；没有凭据/HTTP/模型消耗，但会有固定域名调用触发的实际解析流量，内部 NSS/wire QNAME 未穷尽 |
| B：先准备项目 DNS 硬配额/计数机制 | 新机制经过验证后，再申请有限 DNS 发出上限的 Node 诊断 | 新增项目规则/受保护计数与截止语义、完整 verifier、并发/超额/中断负例和恢复；需要额外 H1/H3 验证。当前尚未证明可行，不承诺某条现成规则即可实现；没有理由修改全机 DNS 或增加允许目标 |

A 是本次诊断范围的明确未知，不是精确计数工程已完成；B 不得演变成上游全机修改或被本票推定为产品精确请求观测。两路均不改变现有停止条件：缺观察、绑定漂移、失败或清理未知就停止，不退款、不自动重发。

## 按已选 A 准备的最小执行清单

1. 可信 controller 保持原安装 `use_install`/OFD，核对固定 Node 公开字节和实例身份；新诊断代码放安装树外，诊断标签仅在审阅目录，不登记产品身份。
2. 无 Landlock 的固定 Node 对 router TCP53 connect 一次正对照，无 DNS payload，关闭并退出后再进入模型对照。
3. 原 Landlock 下固定 Node 对同一 TCP53 connect 一次，必须拒绝；不因为此项失败或默认 lookup 需要 fallback 就加端口。
4. 每域名先显式 UDP/TCP A 参考各一次，再运行该域名一次 Node 默认 OS lookup 和至匹配 IPv4的一次 TLS 握手。Node 源码/参数须在包里准确说明其与 Pi 实际 connector 的相同点与差异，不能仅凭窄诊断声称未改装 Pi 路径已验。
5. 单次永久预占、零秘密环境、exec前/服务双零 core、原 cgroup/规则/只读 resolver、完整受控元数据、退出/回收/恢复和持久 resolver before/after 沿现审阅机制。HTTP/认证CLI/模型/Pi/IPv6网络连接/崩溃均0；AAAA 查询不冒称 IPv6 连接验证。

拟有4次固定 Node exec：TCP53正例1、隔离负例1、两域名查址/TLS各1；查址调用2、TLS2、显式参考DNS4。内部 DNS 发出数及可能 TCP fallback 尝试仍 unknown，不能用 wall 或 nft packet 数填成固定请求数。最终单项/总 wall、全部字节、Node 入口/树身份、CA行为、调用参数和预算将在所选范围可行后封印，实际执行仍另申请 H1/H2/H3。

本次选择只确定下一步的解析预算准备范围，**不请求或推定批准任何现场动作**。最终可执行材料仍须逐字审阅；不能因 A 已选就降低原观察/清理判据或将兼容项标成通过。
