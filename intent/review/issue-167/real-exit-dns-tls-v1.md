# #167：应用可见 DNS/TLS 计划 v1（待单独授权）

当前 H4 已选 A，目标与来源冻结于 [机器可读计划](real-exit-plan-v1.json) 和 [ADR-0050](../../../docs/adr/0050-bind-egress-to-owner-visible-addresses.md)。本文件准备下一轮明确预算；当前实际执行数为0。不以本次裁决启动 DNS/TLS、认证/模型、Node/Pi 或配置变更。

## 所有者来源与允许集合

所有者实测：软路由192.168.44.1使用OpenClash fake-ip，sniffer.override-destination=true；原池28.0.0.1/8。冻结的规范允许范围为**TCP443至28.0.0.0/8，UDP/TCP53至192.168.44.1**，仅拟约束项目精确cgroup，不是全机规则。LAN TCP/UDP53劫持到该路由器、转发TCP redirect至Clash7892，是上游配置来源事实；本机没有新增至7892的允许规则。IPv6本轮not_assessed、计划探测数0，不把旧v5的创建负例迁移为本轮证据。

当前owner报告api.openai.com→28.0.5.94、auth.openai.com→28.0.5.167，未提供TTL。这两值仅为基线，不替代整个池的允许范围；下一轮TLS使用同轮已核对的DNS A快照，不使用实际供应端IP、其他resolver或系统隐式解析。

无TLS中间人的事实来源是所有者实测陈述。本机不检查上游映射、不主张出口身份，普通TLS链校验也不被当成该来源事实的独立穷尽证明。API与认证共享该允许池及DNS例外，不能凭ACL宣称两类目标已经隔离；本计划封闭域名由受审runner约束。

## 拟申请的一次预算

固定顺序；任一步失败/unknown即停止，后续项目不执行、不补发、不退款。

| 序号 | 动作 | 目标 | 上限 / 绝对截止 |
| --- | --- | --- | --- |
| D1 | UDP DNS A | api.openai.com，192.168.44.1:53 | 1查询、1次datagram send；5s |
| D2 | TCP DNS A | 同域名、同resolver | 1连接、1查询；5s |
| T1 | TCP443+TLS握手 | 同轮api A快照唯一地址；SNI/hostname=api.openai.com | 1连接、1握手；共10s |
| D3 | UDP DNS A | auth.openai.com，192.168.44.1:53 | 1查询、1次datagram send；5s |
| D4 | TCP DNS A | 同域名、同resolver | 1连接、1查询；5s |
| T2 | TCP443+TLS握手 | 同轮auth A快照唯一地址；SNI/hostname=auth.openai.com | 1连接、1握手；共10s |

合计4个DNS查询（UDP2/TCP2）、DNS TCP连接2、TLS TCP连接2、握手2；HTTP请求0、认证CLI0、模型prompt0。TCP DNS是独立预算项，不是UDP失败后的额外fallback；不发AAAA/其他域名、无隐式resolver搜索/自动重试。collector入口起单调wall截止45s，最终化/清理截止10s；每项截止包括该项所有连接/发送/接收，不按每次read重置。Python对write/fsync/close的前后检查不提供硬中断保证；启动器另以55s监督和最多1s终止宽限约束进程，非零/超时退出一律unknown，不能单凭中途result字段接受完成。

DNS只接受来自固定resolver、匹配固定question/transaction且无截断/格式歧义的成功响应。每个域名的UDP/TCP结果必须同一个A地址，TTL均大于0且地址在28.0.0.0/8；多A、CNAME、需要额外查询、池外地址、TC、超时或不一致均unknown并停止。每个响应的单调接收时刻+TTL形成各自截止；TLS开始与握手完成均须早于该域名两份快照的最早截止。失效不补查，不换备用地址。

TLS直接对上述地址创建IPv4 socket，不能再调getaddrinfo或系统resolver；开启证书链与固定hostname校验，最低TLS1.2。仅加载计划SHA绑定的公共系统CA bundle `/etc/ssl/certs/ca-certificates.crt`，不用环境CA覆盖、不加载client certificate/private key；信任材料不符即停止。只握手并关闭，不发送HTTP、认证或应用请求；失败不重连。TLS记录链/hostname校验结果与版本等允许元数据，不保存证书正文、headers/body、原始DNS报文、外部异常原文或完整流。

## 漂移、完整性与回执

入口还须取得所有者对冻结路由器配置仍适用的确认，其来源关联到本次外部授权；软件不能自填true冒充确认。原池字符串28.0.0.1/8、规范池28.0.0.0/8、router/sniffer/DNS劫持/TCP redirect或无TLS中间人条件已知变化即停止。池内DNS结果不能独立证明配置未变；当前没有路由器自动配置读取或监测权限，缺确认时unknown。

仅保留受控类别/序号/次数/完整性、域名角色、应用可见IP及TTL/单调窗口、计划/collector/host绑定、受控错误和清理事实；不主张上游映射、最终IP、线路或出口身份。本轮DNS/TLS成功也不成为HTTP/模型计数或产品准入事实；丢事件、缺参照、观察失败或清理未知均unknown，必须在删除runtime前保存允许摘要。

## 成为可执行包前仍需完成

这一步是**普通用户、无配置变更的前置元数据轮**，由受审collector限制自身目标及次数；不安装unit/nft、不宣称已经有OS出站ACL或服务隔离。下一包须包含闭集DNS解析/TLS实现及纯mock负例、固定collector/工具/host/计划字节、预算预占和无重试守卫、配置适用性确认来源与结果接收校验。它不访问凭据，不运行Pi/Node或认证/模型，不因方便而用root执行。

后续真正部署允许集合仍须另备项目专用unit/nft及安装/恢复代码，以完整池与router DNS规则渲染，root动作交H1；配置或实际规则/权限未核对不能放行实际认证/模型门闩。本次元数据结果不能替代该部署验收。

前置collector字节准备、独立审阅和离线验证完成后，才单独提交明确的网络元数据授权；不将这份计划或H4决定当执行许可。仍保留真实Pi、认证宿主、同uid进程、完整文件窗口、供应商能力与H5等各自前置；不为本网络裁决引入loader或改变产品启动/协议身份。
