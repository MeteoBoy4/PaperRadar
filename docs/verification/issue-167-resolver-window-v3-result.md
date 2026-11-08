# #167：resolver/window v3 无网络现场通过与恢复

所有者批准并执行了新的单次 H1/H3 包 `.scratch/issue-167/h1-resolver-window-v3/`，随后报告「已运行」。本轮只读核对其结果、具名资源状态和永久记录元数据，没有重跑、追加网络或运行 Node/Pi。原 c591 案例继续保持 [unknown](issue-167-resolver-run-unknown.md)，原消耗及记录不变。

## 身份与接收范围

| 材料 | 身份 |
| --- | --- |
| run | `d840a7e2c619` |
| review-seal.json SHA256 | `104f6b7f0d886f3e93c5ceb5927871684bcb2576dddfa9b7f8864ff930d85a74` |
| core manifest SHA256 | `835b9c34567c845b08c74b9b5fff3bfc90eefa48e254bf5743b3f97f94dd3f45` |
| driver SHA256 | `f11c0342274065a9631eeb2a993657782a73c0516127ab69dccf0df8646053b4` |
| results/owner-run.json SHA256 | `5f3ddf8bed11def3d6572af4965d573f8d7b274f6f8b9216facf80e9e07721a8` |

owner_result 与内层 result 均为 `observed_expected_and_restored`。fresh 只读复核封印、27 个 core 成员、14 个映射源码及 4 个工具 SHA；ready/result 经既有 Case 验证器接收，五份规则快照经原独立 binding 和完整 verifier 离线重验。没有发现阻断项。`execution-started.json` 保留单次预占的 `reserved_unknown`，它不是最终结果，也不提供重试许可。

这只接收本次无网络合成现场；不改变产品 `LAUNCH_POLICY_VERSION`、`pi_protocol`、`read_evidence`，不登记为历史覆盖、固定分母、required 或正式 Live 回执。

## 实际观测

- worker UID1000、cap 空、NoNewPrivileges、软硬 core 均为零，实际 cgroup 与固定 unit 匹配。服务内只读 resolver SHA 为 `5a79acd72a35d2d00f5f3aa8560921dba5a8503a1136af26aaa0ac88df8ade48`。worker 与 root-caller 的 mount namespace 不同、PID namespace 相同；来源明确不是实际 Apport handler。
- 两个 synthetic Python 角色各 exec 一次，12 个 chain 布尔均为 true：原 FD 继承及共享 offset、父 close 后独立排他锁拒绝、子退出后排他锁允许、匿名非秘密 marker 传递、子 core/cgroup/resolver/NNP，以及不同 session。这里使用合成 worker 与 Python 运行库特许，不是未改装生产 `prepare_launch` 或真实 Pi 路径。
- 真实 inotify 与 kernel-own cgroup 来源的窗口为 `window_complete`：mutation_events=3、终态 regular=1/other=1、独立 directory_deleted=true、post_terminal_mutation_events=0、reasons 为空。它证明所选合成树与该后端窗口，不穷尽任意程序、mmap/别名或其他写入渠道。
- 本表五份快照顺序为 created_deny、activated、cleared、reactivated、post_stop，完整结构和稳定 binding 均通过。独立 live cgroup2 dev=30/inode=847842，table handle=26；允许/拒绝 packet 计数均为零。因此只证明实际规则结构、身份绑定和切换，不证明流量允许/拒绝效力。
- network_operations、真实 auth/model 计数均为零，node_pi=false；未执行 DNS/TLS/HTTP、IPv6 探测、Apport 或崩溃。原 core 方向和所有者接受的残余不变，不将本次 namespace 元数据外推为完整 core 持久化重验。

## 恢复及独立复核

恢复五字段完整：host_policy_restored、global_resolver_unchanged、ledger_retained、table_absent、unit_absent，restoration_stage=complete。resolver_check 的来源为 `root_baseline_file_and_post_restore_read`，同 run 的 before/after SHA 均为 `841c38da2013c6dbcb38c5949622b084ab8372c4115ba71ad377a2288b3e3acf`；这次确有安装/启动前持久化基线和恢复后测量。它不补齐旧 c591 丢失的基线。

artifacts=successful_artifacts_removed，保留永久 ledger。普通用户独立查询该 unit：not-found/inactive/dead、MainPID=0、fragment/drop-ins/cgroup 空；精确 unit 文件、cgroup 目录、代码和 runtime 路径均 absent。本表 absent 由已审 root 程序核验，agent 没有追加 root nft 枚举，不声称普通用户独立验证了该层。

永久记录仅 lstat：宿主 UID/GID0、0600、nlink1、14427 bytes，未读其内容。工具默认沙箱最初将 owner 映射为65534，随后用同一普通用户宿主 lstat 得到真实 UID0，保留来源区别。当前 resolver 的普通用户只读 SHA 也与回执一致，但只是额外当前快照。

独立检查存本包 results/post-run-readonly.json、post-run-systemctl.json、host-ledger-lstat.json。除新增这些派生检查外，封印包、原回执和旧案例不改。内部配置、进程/内核详情、回执及相关哈希仅留本地，不发布到 GitHub。

## 后继与验证

v3 回执核对没有修改已执行源码/测试或重跑该案例；后续网络准备另建材料。包执行前的相关组合183项、6文件静态检查及 fresh 审阅见[修复台账](issue-167-resolver-run-unknown.md)；这些不是本轮重新运行的结果。新增结果仍按独立未绑定 D1 材料处理。文档链接、diff 及最终固定 scope 含 collect 审计另记本轮回记；不运行完整离线门禁。

下一步仍是适用项目服务下的真实网络允许/拒绝与 DNS/TLS、实际 Node/Pi 与内层 DNS 兼容验证。既有普通用户前置 DNS/TLS 已消费，不能借本次成功重用余额或跳过 H1/H2/H3；先准备具体受审字节和新预算。真实凭据、认证/模型、供应商能力及故障、H5 与产品激活均未由本轮授予，Live/B 和缺证据阻断保持。
