# #167：按 A 准备的无秘密固定 Node 诊断

所有者已选择[解析未知范围 A](node-dns-budget-decision.md)。这只是准备范围；新包的实际 root、固定 Node、DNS/TLS 仍须绑定最终字节另获 H1/H2/H3 单次授权。先前 Python 服务轮的成功与预算不授予本轮执行许可。

## 固定顺序与判据

| 阶段 | 唯一动作 | 必须成立 |
| --- | --- | --- |
| 1 | 无 Landlock 的固定 Node 向 router TCP53 connect 一次，不发送 DNS payload | 连接成功、close/子进程退出、原 FD 继承及身份/限额正确，完整规则/CG与 allowed 增量支持正对照 |
| 2 | 原 `IsolationBoundary(..., proxy_port=None)` 下固定 Node 向同一 TCP53 connect 一次 | EACCES/EPERM、close/退出、原 FD 与身份正确、该段无本表 packet 增量；不把 Landlock 拒绝归到 nft reject |
| 3 | API 的 Python UDP/TCP A 参考各1，随后单个受原隔离约束的 Node：默认 lookup×1、至匹配 IPv4 的 TLS×1 | 参考唯一池内 A 相同且正 TTL；Node 返回 IPv4 必须匹配，校验链/hostname/TLS版本，父区间完整位于最早 TTL 内 |
| 4 | AUTH 同样流程，新参考、新 Node 进程 | 同上；不复用 API/旧轮 TTL 或会话 |

Node exec4、lookup调用2、显式参考DNS4（UDP2/TCP2）、Node TLS连接/握手2、TCP53正负对照各1。OS 内部 A/AAAA/NSS/重试次数、wire QNAME及可能 TCP fallback 尝试均 unknown；不得将其填成总DNS≤2/6。HTTP、认证CLI、模型prompt、Pi、IPv6网络连接和崩溃均0，无应用重试或备用域名。任一失败/unknown停止，不退款、不重发；模型 TCP53不放宽。

父进程区间从 Node Popen 之前至输出接收、正常退出/回收之后，包含查址/TLS/关闭，必须在同轮两份参考收到之后且严格早于它们最早失效时刻。TTL 使本段截止短于一般10秒限额时按更早截止，不以一秒太短为由补查或延长。前置安装/完整树检查不挤入该区间。

## 诊断与产品路径的区别

该脚本使用固定 Node 的 builtin `dns.lookup`、`net`、`tls`，固定 JS 由 `-e` 传入，安装树外保存审阅源码。没有 Pi、loader、SDK桥或产品身份登记。默认 lookup 不传 family/排序/自定义 resolver 参数；如果返回 IPv6或非参考地址则停止，不挑选备用地址。它验证这次默认 lookup 的结果，不穷尽 Pi/Undici connector 的 family/autoselection 行为。

官方固定版本说明 lookup 使用 OS/getaddrinfo，故不把调用数当作 DNS wire 数。[Node v22.23.4 DNS 文档](https://github.com/nodejs/node/blob/v22.23.4/doc/api/dns.md#dnslookuphostname-options-callback)

TLS 使用匹配 IP 与固定 `servername`，开启 `rejectUnauthorized`，不覆盖默认 hostname checker，不提供 client key/cert、session或环境 CA 变量。官方该版本实现按 servername 优先取得校验身份；默认 CA 设置与前轮 Python TLS 的显式系统 CA 不同，不能合并为同一信任材料。本轮父 Python 仅做 DNS 参考，不进行 TLS。[固定 TLS 实现](https://github.com/nodejs/node/blob/v22.23.4/lib/internal/tls/wrap.js#L1663)，[固定 TLS 文档](https://github.com/nodejs/node/blob/v22.23.4/doc/api/tls.md#tlsconnectoptions-callback)

每个 Node 使用空环境、固定 cwd；只筛选自己的 UID、core/NNP/cap、CG 和继承 FD 元数据。单 JSON stdout 有界，不记录外部异常原文、stderr、证书正文或网络流。启动前后核对绑定的 NSS 文件和 hostname 结构；这不是对配置瞬时改回的持续观测证明。AAAA查询不等于 IPv6 网络连接验证，IPv6保持 not_assessed。

## 原安装保护的明确实现范围

根管理进程不导入工作区 SQLAlchemy/application 依赖，也不以 root 读取原数据库或取得原安装锁。UID1000 worker 使用诊断专用 stdlib helper，对固定供给的公开登记列、DB身份、root marker、原实例/当前选择及 Node 字节做只读核查；禁止访问业务记录、认证、配置正文或材料 raw。

helper 打开已存在的原 instance lock，核对已封印 dev/inode/owner/mode/nlink，以 O_RDONLY、SH|NB 取得保护，把同一 FD/OFD传给四个 Node。没有复制 Node、重新给每个 child开锁、新建锁或 LOCK_UN；父/子只 close 自己的 FD。保护作用域两端检查完整 tree-v1、实际 Node ELF SHA和公开登记，子进程完成前不释放保护。

该窄投影明确标记为 `diagnostic_readonly_original_instance_lock_not_product_use_install`。它保持原锁/OFD保护与固定实例，但没有调用完整产品 `use_install`，不重做全部材料/D5/cleanup DAG或配置 snapshot 规则，不能声称产品准入链已通过。公开 manifest 的 node_sha256 是归档摘要，实际 ELF SHA另行绑定，两者不能混用。

## 宿主与执行交付

沿现有单具名 unit/table、冻结应用可见允许集合、cap空/NNP/seccomp/Delegate=no、软硬零core、服务只读 resolver 与实际CG。安装启动前持久 root0600 resolver基线，恢复按 scope→stop→CG空→bound完整验表→删本表/卸unit，保留永久预占及闭集恢复子阶段。失败或创建归属不明保留 unknown，不删旧案例。

只向 sudo TTY输入一次密码；入口必须同时显式确认冻结配置及本次 A 未知范围，任一 flag 缺失都在预占/sudo前拒绝。所有者审阅最终封印后才运行，agent不代行 root。本计划不授权真实凭据、认证/模型、供应商能力/故障、H5 或产品激活。
