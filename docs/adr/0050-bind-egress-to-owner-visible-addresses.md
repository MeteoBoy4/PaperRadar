# 按所有者冻结的应用可见集合约束本机出站

状态：已接受；日期：2026-11-07；依据：[#167](https://github.com/MeteoBoy4/PaperRadar/issues/167) 所有者 H4 真实出口终局裁决。本条独立记录本机部署范围；关联 [ADR-0039](0039-isolate-pi-with-landlock.md) 与 [ADR-0046](0046-consolidate-pi-readiness-under-live.md)，不改变其 Landlock 策略或 Live 职责归属。

本机上联软路由使用 OpenClash fake-ip 与 sniffer.override-destination=true，上游决定实际线路和最终 IP。本机采用所有者实测并冻结的应用可见出站集合：TCP443 至 `28.0.0.0/8`，UDP/TCP53 至 `192.168.44.1`；原路由器配置池字符串 `28.0.0.1/8` 与规范 CIDR 同时保留，池值变化停止。当前 API/Auth 的两个映射是来源事实，不将允许集合缩为这两个地址，也不换成实际供应端 IP。IPv6 保持 not_assessed。

所有者报告 LAN 的 TCP/UDP53 均被劫持到该路由器，转发 TCP 被 redirect 至 Clash7892，且无 TLS 中间人；这些记录来源于所有者实测，不伪称由本机程序独立检查。本机不核验上游映射、不主张出口身份，证据仅描述应用可见地址、允许规则和适用的 TLS 链/主机名校验。ACL 本身不证明域名或 API/Auth 目标隔离；router7892 不是新增的本机允许目标。

代价是接受这一明确的本机证明范围与上游信任，不能由池内 DNS 答案推断路由器配置没有变化。每份执行计划须绑定来源及适用性确认；发现池/配置变化或无法取得必要确认时，停止并保留 unknown。DNS 查询与 TLS 连接的目标、次数、超时、TTL 窗口和停止条件另行冻结并审批，不自动 fallback、扩大集合或追加余额。本决定只约束项目进程的后续部署模型，不授予当前 DNS/TLS、认证/模型、Node/Pi 执行或任何路由器/宿主配置变更，也不改变 core、计数或产品激活边界。
