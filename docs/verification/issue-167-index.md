# #167：探索证据单一入口索引

本文件是 #167 全部探索材料的**唯一入口**，供后续 Live、B、I 与审阅者按需下钻。它只做索引与状态汇总，不改任何原台账字节、不改判据、不构成产品准入或证据激活。所有者已按[接收记录](../../intent/review/issue-167/h5-acceptance.md)签收本阶段有限范围并附加三条修正；执行票仍为 [#167](https://github.com/MeteoBoy4/PaperRadar/issues/167)，产品工程前置为 [#168](https://github.com/MeteoBoy4/PaperRadar/issues/168)。

阅读顺序：本页状态矩阵 → 判据级台账 → 需要时再下钻支撑级台账与工具。

## 一、能力状态矩阵

状态互相独立，不得合并为总布尔值：`verified` 不等于当前可执行，`not_assessed` 不等于失败，`unknown` 不等于零。接收、人工激活、到期与当前绑定适用性是另四个维度，见 [ADR-0051](../adr/0051-separate-live-binding-capabilities-and-activation.md)。

| 主张 | 状态 | 依据 | 到期/时效 | 下游责任 |
| --- | --- | --- | --- | --- |
| 实际 Pi 公共 300 秒截止 | `not_assessed`（T1 未触发） | [T1 结果](issue-167-t1-result.md) | 不适用；目标未取得 | Live 保留现场能力缺口；不重跑，方法改变须新授权 |
| 自然供应商迟延、真实供应商错误 | `not_assessed` | [T1 结果](issue-167-t1-result.md) | 不适用 | Live 仅在以后合法场景补证，不以本机注入替代 |
| low/high 实际参数效力、日期 alias | `unknown` | [事实矩阵](issue-167-facts.md)（DERIVED 逐项覆盖）、[供应商权威复核](../../intent/review/issue-167/provider-authority-review.md) | 无 verified 时点 | Live 阻断该能力主张；B/H 与对外文案不得写成已验 |
| 当前账号可用集合、app cap、剩余量/重置 | `unknown` | [H4 待审材料](../../intent/review/issue-167/post-t1-owner-review.md) | 无 | 可由所有者提供非秘密界面声明补充，Live 限定其时效 |
| 精确模型/刷新 HTTP 计数、隐藏重试/预热 | 可证下界 + `unknown` | [请求路径](issue-167-request-paths.md)、[client 观察](issue-167-client-observation.md)、[ADR-0048](../adr/0048-accept-bounded-request-observability.md) | 不适用 | Live 的 doctor/日报保留口径；精确计数交 I 重评 |
| cache/认证全写史、确切 writer 身份 | `not_assessed`（S 分类下界） | [六格结果](issue-167-live-six-result.md)、[认证输入账](issue-167-auth-input-refresh-ledger.md) | 不适用 | Live 实现可信观察与失观测阻断 |
| IPv6、其他平台、无人值守/NAS | `not_assessed` / `unknown` | [ADR-0050](../adr/0050-bind-egress-to-owner-visible-addresses.md)、[H4 待审材料](../../intent/review/issue-167/post-t1-owner-review.md) | 不适用 | Live 保留现场适用边界；I 承接 NAS 与无人值守资格 |
| 普通产品 CLI、任务租约、全部异常时点 | 未证明 | [pi-execution](../contracts/pi-execution.md) | 不适用 | B 在正式入口落实；不得 patch admission 或绕过私测接口 |

## 二、已核可依赖的有限事实

以下各项仅在自身固定绑定、材料、角色、观察窗口与恢复边界内成立，不跨案例补证。任何一项都没有"整批通过"含义。

| 事实 | 范围 | 依据 |
| --- | --- | --- |
| 六格正常调用：RPC 初态清洁、命令队列空、settled、EOF/退出 0、公共 terminate 返回、业务 validator 与模型身份比对通过；Pi 报告 usage | boundary/value/read × 显式 low/high，本机固定 Pi 1.4.0 绑定；**整批仍 unknown（监督退出缺口）** | [六格结果](issue-167-live-six-result.md) |
| 文件观察 S 分类：session 全窗口零观察写、终态 session/unknown 成员 0、独立目录删除成立、post-terminal 写入 0 | 已知非 session 事件仅为下界 | [六格结果](issue-167-live-six-result.md) |
| 外部 SIGINT → 同一真正 `KeyboardInterrupt` → 公共 `run_call` 与 `prepare/use_install` 后验、S/CG/DB/host/目录恢复 | 单格 value/low；未覆盖确定内部点直接注入（K2 保留 `not_assessed`） | [E01 结果](issue-167-e01-result.md) |
| 项目双向（INPUT+OUTPUT）丢弃机制：正例通信、负例丢弃、同 uid 不同 CG 对照、恢复 | 仅 IPv4 loopback 合成机制，不外推真实 TCP443 | [duplex 结果](issue-167-duplex-result.md) |
| 显式零 core 限额：`RLIMIT_CORE` 软硬 0 时 Apport 非打包分支无 core/report 新增；非零正对照确有 raw core 新增 | 合成 ELF、同 uid、当前 Apport 版本与配置；不外推其他 collector/打包路径。残余：Apport 仍可能在 root 内存瞬时采集 proc 环境而不落盘，Apport 版本/配置漂移由后续 doctor 长期检查；「任何备份/同步与任何上传通道均未覆盖」仍 `unknown`，不由本对照补成排除 | [core 终局](issue-167-final-core-validation.md)、[H4 只读补证](issue-167-h4-readonly.md)、[ADR-0049](../adr/0049-bound-core-persistence-with-explicit-zero-limit.md) |
| 监督收尾接缝（无认证/无模型）：`phase_gate` write_complete 且 gate_published、`wait_exit` complete、独立 cgroup 观察为空、manager success/exited 1/0、MainPID 0、unit 与 CG 恢复 | 单次合成 worker；**整轮仍 `unknown`**，artifact 阶段未完成；不解释 e93 原因为何 | [监督探测结果](issue-167-live-exit-probe-result.md) |
| 隔离与出站：完整规则快照序列一致、allowed/reject 计数、应用可见地址池与路由器 DNS | 本机 IPv4；上游映射与出口身份不核验，IPv6 `not_assessed` | [六格结果](issue-167-live-six-result.md)、[ADR-0050](../adr/0050-bind-egress-to-owner-visible-addresses.md) |
| 合成故障工程控制：pump/清理位置 KI、外部 SIGINT、短墙钟有界 helper、一次真实 300 秒本地对端截止 | 合成对端，不替代实际 Pi 或供应商行为 | [合成故障](issue-167-offline-fault-engineering.md) |
| 宿主与资源恢复、原逻辑选择 CAS 回退、仅清理回执 | 逐案；不补原监督退出证据 | [六格清理](issue-167-live-six-cleanup-result.md)、[监督清理](issue-167-live-exit-cleanup-result.md) |

### 接线时必须遵守的两条操作规则

取自[请求路径核查](issue-167-request-paths.md)，对 B 的真实接线生效：

1. **首批若出现 WS 传输即视为绑定漂移**：替代 provider（Codex）存在独立的 HTTP/WS 路线，只 hook fetch 会漏 WS；出现时应停止并按新授权处理，不得无授权采纳或临时切换 transport。
2. **compaction / branch summarization / 其他 RPC 命令须由有界命令集显式拒绝**：`compaction.enabled=false` 只关闭自动路径；任何总结型模型调用若发生也必须计数，不能只观察前台 prompt。

## 三、运行身份速查

| run | 内容 | 结果 |
| --- | --- | --- |
| `e93f7b82c461` | 六格真实调用批次 | 整批 `unknown`（`failure_stage=exit`）；六格各有有限正常事实 |
| `d5f2a9017c84` | 独立无认证/无模型监督收尾探测 | 整轮 `unknown`（artifact 清理未完成）；退出接缝本身取得严格成功事实 |
| `4e01c7a3b962` | E01 单格外置 SIGINT | `observed_expected_and_restored` |
| `a73d9c02e651` | 双向过滤无凭据合成机制 | `observed_expected_and_restored` |
| `8b31f0a9d672` | T1 实际 Pi 诱导 300 秒单格 | `not_triggered_and_restored`（84.21 秒 error 终态返回） |
| `a840c6d21e97` | H1 自动执行失败与恢复 | 保留原失败，见[失败与修订](issue-167-h1-failures-auto.md) |
| `b6302f9a47e8` | H1 合成组合 v5 | 通过，见[v5 结果](issue-167-h1-v5-result.md) |
| `c591eb6ad204` / `f287c9ad630e` / `b62d4a90e713` | resolver / 服务网络 / Node 诊断 | 逐项见对应台账 |

## 四、文档分层

**判据级（先读这 12 份即可判断本阶段结论）**：[core 终局](issue-167-final-core-validation.md)、[duplex 结果](issue-167-duplex-result.md)、[T1 结果](issue-167-t1-result.md)、[E01 结果](issue-167-e01-result.md)、[六格结果](issue-167-live-six-result.md)、[六格清理](issue-167-live-six-cleanup-result.md)、[监督探测结果](issue-167-live-exit-probe-result.md)、[监督清理](issue-167-live-exit-cleanup-result.md)、[离线故障工程](issue-167-offline-fault-engineering.md)、[事实矩阵](issue-167-facts.md)、[请求路径](issue-167-request-paths.md)、[H4 只读补证](issue-167-h4-readonly.md)；决策面另见 [H5 接收记录](../../intent/review/issue-167/h5-acceptance.md) 与 [H4 待审材料](../../intent/review/issue-167/post-t1-owner-review.md)。

**支撑级（追溯授权、封印与边界，不单独作判据）**：以下链条各含准备包、未知/失败与续办文档，按前缀检索即可：

- 六格：`issue-167-live-six-{afk,s-preparation,exit-followup}.md`
- 监督收尾：`issue-167-live-exit-{probe-preparation,cleanup-followup,freeze}.md`
- 真实案例准备：`issue-167-{e01,t1,duplex}-preparation.md`
- H1 部署与恢复：`issue-167-{core-wiring-h1,h1-synthetic-local,h1-failures-auto,h1-v4-recovery,h1-ipv4-next}.md`
- 服务、resolver 与出口：`issue-167-{resolver-run-unknown,resolver-window-v3-result,service-observation,service-network-preparation,service-network-result,dns-tls-result}.md`
- Node 与认证：`issue-167-{node-diagnostic-preparation,node-diagnostic-result,node-auth-facts,auth-input-refresh-ledger}.md`
- 观察与生命周期原型：`issue-167-{observation,lifecycle,budget,loader,fd-handoff,apport-review,core-feasibility,host-crash-facts,client-observation}.md`

## 五、工具说明

`scripts/issue167_*.py`（130 个）与 `tests/test_issue167_*.py`（71 个）为本次探索的一次性工具，用于启动包封印、宿主/规则编排、观察与合成对端。其性质：

- 不属于任何 required 组，不进固定分母，不产生正式回执（D1 未绑定）。
- 部分文件含宿主编排、root 步骤与固定的本机历史路径（fake-ip 池、探针根），属于当次现场记录，不外推也不作为部署脚本。
- 运行结果已按次冻结于本目录台账；工具本身仅用于复核，重跑任何案例仍须新的具体授权与新的 H1/H2/H3。

## 六、到期与激活

供应商能力证据从**各自原验证完成时刻**起 30 天硬到期（[ADR-0047](../adr/0047-expire-and-explicitly-activate-live-evidence.md)）：六格（2026-11-07/08）与 E01（2026-11-08）分别到期于此后的第 30 天；T1 未取得目标证据，不产生该能力时点。接收、H4/H5 签收与人工激活均不重新计时；到期未激活须另批重验，已激活到期同样阻断受影响的新任务。

当前 `read_evidence` 仍返回 `None`，尚无产品接收机制与人工激活；本索引不改变该事实。证据激活须在 [#168](https://github.com/MeteoBoy4/PaperRadar/issues/168) 建好接收机制后另行显式执行。

## 七、不表示

- 不表示 Live 或 B 已完成，不解除 B 对完整 Live 的依赖。
- 不表示任意 JSON、Markdown、布尔字段或本索引可自证准入通过。
- 不表示历史 unknown、失败、消耗与受控留存被改写或清零。
- 不表示真实研究资料外发、正式校准、无人值守或 NAS 资格获得授予。

## 八、维护

新增 #167 台账须在本页登记类别与依据；本页随台账增补原地更新，不改被索引台账的字节与证明范围。本页不作为历史固定材料的分母，也不进入 required 组。
