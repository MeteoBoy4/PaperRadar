# #167：项目服务内 DNS/TLS 与代表性拒绝验证计划

这是 A4/A6 的离线准备材料。上一步[无网络 v3 现场](../../../docs/verification/issue-167-resolver-window-v3-result.md)已通过并恢复；它没有消费本计划的网络动作，也没有为其提供许可。下列配置和预算须绑定最终源码/封印另获 H1/H2/H3 单次授权，所有 root 动作仍由所有者执行。

## 目的及有限差异

把已审的显式 Python DNS/TLS collector 放入同形项目服务，直接补实际服务规则的代表性拒绝与正例。保持单 worker、固定 cwd、cap 空、NoNewPrivileges、seccomp、Delegate=no、软硬零 core、项目内只读 resolver 视图、独立 cgroup 身份、稳定规则 handles 和恢复顺序。worker 仅开启 AF_INET，并在 systemd 地址层允许既定池/router；不装额外 listener、不增加允许地址或端口。

允许集合仍为 TCP443 至 `28.0.0.0/8`，UDP/TCP53 至 `192.168.44.1`。API/auth 共享此池，ACL 不证明两类目标分离；固定域名顺序由受审 collector 约束。最终地址和线路由上游决定，本机不核验上游映射或主张出口身份。无 TLS 中间人的来源仍为所有者陈述，不由证书链检查扩成穷尽证明。IPv6 not_assessed，探测数为零。

这是可信 Python collector 的网络验证，不运行 Node/Pi，不用模型 Landlock 冒充该 collector 的边界，不主张 Node 默认 lookup 已兼容。模型内层 TCP53 缺口原样保留；不改产品权限、启动身份、协议登记或 loader 状态。

## 顺序、预算和受控接收

任何步骤失败或 unknown 都停止；不自动补发、重连、切备用地址或退款。

| 阶段 | 动作及上限 | 接收条件 |
| --- | --- | --- |
| deny-TCP | 初始 deny 表下，仅向 router:53 connect 一次，5s，无 DNS payload | worker 未建成连接；owner 完整验表/绑定且 allowed 不增、rejected 增加。超时本身不足以证明规则生效 |
| deny-UDP | 同一 deny 表下，仅向 router:53 发送一次 api 域名的 UDP A 查询，5s | 未取得响应；owner 再次完整验表/绑定且 allowed 不增、rejected 再增加。若规则失效，查询可能实际到 router，因此预算包含它 |
| active | 两项拒绝均符合后，原子激活既定允许集合；按 api UDP A→TCP A→TLS、auth UDP A→TCP A→TLS 的六步顺序各一次 | 复用原严格 DNS/SNI/hostname/CA/TTL/截止检查；实际允许计数增加且无意外 rejected 增量，完整规则与独立身份持续相符 |
| exit/restore | collector 关闭自身 socket、正常退出；确认 cgroup 空后撤本表和本 unit | 恢复五字段及永久记录完整，持久化 resolver before/after 同 run 且一致；失败保留 unknown 与材料 |

合计上限：DNS 查询5（UDP3/TCP2），UDP send3，router DNS TCP 连接尝试3（含 deny 阶段无 payload 的一次），TLS TCP 连接/握手各2。HTTP、真实认证 CLI、模型 prompt、Node/Pi、IPv6 探测和崩溃均为零。这里计数是明确操作/连接尝试上限，不是 TCP 重传或物理 packet 数；packet counter 只支持规则检查，不改成 HTTP/DNS 请求统计。

active 阶段只接受各域名 UDP/TCP 一致的同轮唯一 A、正 TTL、池内地址，无 CNAME/额外解析。TLS 使用该地址和固定 SNI；记录 TLS 实际调用开始/结束的单调时刻，均须在该域名两次 DNS TTL 最早到期前。缺时间戳、失效或漂移即 unknown，不复用前轮一秒 TTL 快照。

## 可复用部分与新边界

复用完整规则 verifier、独立 live cgroup binding、持久 resolver 基线、恢复子阶段、scope-before-stop、空 cgroup 后删表、永久 ledger、单 sudo 字面 bootstrap。旧已执行包、Root 安装、历史 unknown 和预算均不修改。

新网络 Case/worker/result/owner envelope 必须独立声明实际操作语义；旧 owner 的零网络字段与 `(0,0)` 判据不能移植后再改摘要。拒绝与 active 阶段分别保存完整快照和 counter 检查，缺阶段、漂移、倒退或无归属一律 unknown。原 collector 的 `OS_ACL_assessed=false` 保留其组件语义，由新 owner 单列服务规则事实。

封印只证明所审字节身份，不自带授权。所有者须在审批时确认冻结的 router/fake-IP/sniffer/劫持/redirect/无 TLS 中间人条件仍适用；本机不读取路由器配置。新入口要求显式 `--owner-config-confirmed`，缺失时在预占或 sudo 前拒绝；flag 仅转录外部所有者声明。运行时只需向 sudo 的 TTY 输入一次密码，脚本不读取或保存密码，不再逐条抄命令。

本包不申请真实凭据、认证/模型、供应商能力/故障、H5 或产品激活。不为此提出新 H4 方向；若实现暴露原边界之外的必要差异，再给具体反证与成本，由所有者裁决。
