# #167：v5 IPv4 合成通过与 H2 前置

本轮回记所有者明确「已批准并运行」的固定 v5 包，并完成不依赖新现场许可的只读补证。承接 [v5 准备快照](issue-167-h1-ipv4-next.md)，旧证据、旧失败、封印和预算记录保持，不将本结果扩大成完整 H1 或 Live。

## 实际结果与独立清理复核

run=`b6302f9a47e8`；review-seal SHA256=`ec7e705f598966b1056a76f879880f6f126e09e5d55f0b84600deca9d7bb4a6e`，core manifest=`7003a4c538037603d1dbf2595341fcfda51bf8351cfe659e0976cce018faca2d`。21/21成员、core、driver 均与原封印一致。没有重跑探针或追加预算。

owner-run.json SHA256=`c80efd7533d98ddeb4635a81b15fed505f65029ec10fee4376f29bbe4ac8bb99`，scope=h1_owner_automation_only、owner_result=observed_expected_and_restored。严格 schema 复核通过；guardian_result 与 ledger 的 JSON 值完全相同：

- result=observed_expected；A/B 两阶段各 allowed_packet_delta=4、rejected_packet_delta=4。它们是 packet 参照，不是 HTTP、模型、刷新或系统调用次数。
- leftover_refused=true、cleanup_complete=true、table_may_remain=false；拒绝在遗留后代尚存时再切阶段，随后按封印程序回收。
- guardian 实际 UID0、NoNewPrivileges=true、core=[0,0]、六项 capabilities 全 true；auth_calls/model_calls=0。
- retry_history 实际核验通过，指向 v4 的 manifest 与 unknown 永久记录，不再错链 v2，不退款。
- restoration=host_policy_restored，随后 artifacts=successful_artifacts_removed，永久账本保留。

主代理以同一普通用户在宿主只读独立复核：两具名 unit 均 not-found/inactive/dead、MainPID0，FragmentPath/DropInPaths/ControlGroup 空；两份精确 fragment、两 cgroup 目录、`/home/paperradar-probes/issue167-b6302f9a47e8` 和 `/run/paperradar-issue167-b6302f9a47e8` 均 absent。永久账本只 lstat，宿主 UID0、0600、nlink1、562 bytes，未读内容。工具沙箱内 UID65534 的初始映射不当作宿主所有者；沙箱外核查为 UID0。

核查留包 results/post-run-readonly.json。本表 absent 和账本内容一致由已审 root runner 在成功前实际检查；本轮没有再次 root nft 枚举，不能把普通用户观察说成该层独立证明。没有 agent root、启停或删除操作。

## 可以采用与不能补造的主张

fresh subagent 独立核对封印、回执及 guardian/owner schema 链，没有发现必须修复的问题。可以采用“该固定 IPv4 合成组合由已审程序验收且恢复”的有限结论：对应两阶段7行检查、合成文件检查、controller/worker 身份与绑定、后代拒切阶段及清理通过程序严格验收。

成功 finish 已按批准边界删除 runtime/code，因此 ready、两份逐行 done、文件观察明细、table-binding 和 nft 快照未独立归档。当前只能复核摘要及其封印程序的接受链，不能逐行重放，不报告具体 IPv6 errno、数字 cgroup ID/handles，也不能断言清理实际走了 numeric 而不是 path 分支。不能为补原始材料重跑本次案例。

v5 没有运行固定 Node/Pi 或生产 auth/controller 组合，没有真实 endpoint/TLS、凭据/刷新、模型、全 Pi session 零写入、任意逃逸或供应商能力证据；没有产品 read_evidence/激活。旧 v2/v3/v4 unknown 原样保留。

## 只读 cwd/祖先补证

按所有者给定 docs/docs.json 导航后核对 configuration/security 与 resource-loader；本轮固定元数据路径覆盖 `/`、`/srv`、`/srv/pi-cwd` 各层：5个 context 候选 AGENTS.override.md、AGENTS.md、AGENTS.MD、CLAUDE.md、CLAUDE.MD，以及 .pi、.agents、.agents/skills。无 symlink 跟随，不读内容、不放哨兵。

宿主 `/`、`/srv` 为 UID/GID0、0755；`/srv/pi-cwd` 为 UID/GID1000、0700、普通目录且枚举成员数0。24个资源候选查询中21个 absent、3个因父目录 absent 而不存在；没有发现资源根或 context 候选。结果留 results/cwd-ancestor-metadata.json。**cwd 是当前用户可写目录，不是 root 不可写目录**，不能从此静态空快照推出整个 Pi 运行期间没有资源变化。模型侧 Landlock 对 cwd 写入的拒绝与其他同 uid 程序的权限分开。

`-na` 单独不关闭 context；当前模型 argv 另有 `-nc`，资源加载源码的 noContextFiles 分支返回空列表。这只是静态依据，仍非 Pi 现场发现实测。`--no-session` 与 project sessionDir 的 trust 前读取规则也须在实际固定入口验证，不凭文档例外直接宣布漏洞或通过。

## v5 后的最小前置矩阵

| 主张 | 当前可采用 | 尚缺与承接 |
| --- | --- | --- |
| 服务、合成文件、IPv4阶段/UDP53、IPv6创建拒绝、后代回收 | v5 该固定程序接受链和独立清理元数据 | 不升级为真实 Pi 组合；新的执行/地址仍另审 H1/H2/H3 |
| 原 OFD/token 父子链 | 生产直接 prepare_launch→auth→model；既有 launcher 与 core_wiring 的合成 Python exec 证据，不需要跨 unit token broker | 缺该实际链与服务/角色切换/完整观察窗口的组合；合成 token 不代替真实认证，不能写 unit 属性或文件 |
| 同 uid 进程隔离 | 已有 process_vm_readv 单域关系正负对照 | ptrace/writev/pidfd/proc/signal 等尚未完整实测；只用自建合成进程准备负例，不读真实内存/凭据，不自动换 uid 或放宽权限 |
| 认证宿主读取面 | 当前 auth 为可信宿主 CLI、exec 前零 core；没有模型式 Landlock 白名单 | H2 包须明确它的实际信任面、专用目录元数据及配置来源；不能自称已受额外 whitelist 隔离。若要求新增隔离，另给具体差异，不凭“无 LL”强加新架构 |
| 真实 IPv4 出口 | 源码声明 API/Auth 域名；v5 仅 loopback | 地址/TTL/解析/TLS/透明上游未绑定，见下方具体 H4 比较；不复用旧 fake-IP 许可 |
| 文件三类事实 | FileObserver 原型及 v5 合成 mutation/终态/删除验收 | 真实 Pi 全窗口与可信 cgroup 清空接线未完成；历史与终态、删除分别签收，不能推零写入 |
| 准入/能力/故障 | 离线生命周期、六格合成材料与历史有限观察 | 新 H2逐批预算、两阶段两档、参数/实际模型身份、自然供应商错误及 H5 仍保留；read_evidence=None 继续阻断 |

认证静态核查还看到固定 main.js 在 runAuthCommand 返回后才进入一般项目 SettingsManager/资源启动路径；auth print 路径会创建 allowModelNetwork=false 的 ModelRuntime。后者仍有专用 agentDir/models.json 等配置来源，不能由“提前返回”推断认证 CLI 什么都不读，也不能宣称扩展资源已现场排除。此次未读实际专用认证目录。指定文档树的 main.js/openai.js SHA 与前轮逐文件登记一致；不把它当整棵项目安装树当前核验。

## 完整观察窗口的下一步接线要求

对本轮声明的每棵观察树，须在其首次可能写入前建立观察并完成起始快照；根目录与新子目录事件连续覆盖。model 会话窗口从真实 Pi 启动前持续到受信服务/cgroup 读者确认全部相关后代退出，再取清理前终态分类/count、执行资源删除并独立检查目录 absent。auth 早于 model attempt 创建；认证目录若纳入观察，须另列范围与预期，不能声称该模型窗口覆盖认证写入。短暂写删不能由终态空替代；必须保存 history/terminal/deletion 三个独立结果。

驱动自报 descendants_reaped 不等于真实 cgroup 事实。未来探索 collector 要把服务/boot/plan/attempt/起止序号及可信清空观察关联起来，并在删除 runtime 前保留允许的元数据摘要与完整性状态。丢事件、overflow、watch 空窗、观察器失败、缺参照或后代未知均 unknown，不缺省填0；不保留内容、原始 session/模型流或凭据。这是 A2/A4 接线设计要求，本轮没有偷偷改产品 launcher、策略身份或接收权威。

## 真实出口的待裁决范围

本轮仅普通用户只读查 netlink：5个 link、3条 IPv4 rule、10条 route，所列 tunnel-like0、non-main/local route0。未查询 DNS/TLS、代理配置或进程环境；不足以证明没有透明上游。详见 [H4 出口边界比较](../../intent/review/issue-167/ipv4-exit-decision.md)：A 接受现有网络路径的较窄应用可见 IPv4+TLS 证明范围；B 先要求核验项目直连路径，必要时另审项目专用 bypass，不能改全机网络。

这是后续真实出口方案的所有者选择，不重新问 IPv4、core、计数终局。选择不授予调用预算；下一份可执行端点/解析/TLS包必须列精确目标、次数、超时、停止与恢复后再申请。v5 成功不自动成为 H2 真实认证/模型许可。

## 本轮验证

本轮没有修改 Python/产品代码，没有新测试模块，也未重跑315项或59项组合；其上一轮结果只在准备快照引用。实际新检查为21成员/封印哈希、真实摘要 schema、普通用户宿主 systemctl/lstat、cwd固定路径元数据、无报文 netlink 摘要和 fresh 独立证据审阅。初始默认沙箱 netlink 拒绝保留，随后普通用户沙箱外只读核查，没有提权或修改策略。

文档本地链接/diff与固定 scope 只读审计结果随本轮回记。未运行完整离线门禁，未读凭据/真实environ/core/日志，没有本轮 Node/Pi、认证/模型/外部网络或新崩溃。Live 仍待探索，B 仍等待完整 Live，#167 不自动关闭或标完整 H1 完成。
