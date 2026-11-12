# #184 native 操作与策略逐项核对

本台账是新增 D1 覆盖；不增加任何既有验收组成员、固定分母或现场资格，
不改写 v1–v23 历史来源与 pins。仅修正 pre 在强制执行 post 前读取 post
固定文件所缺少的 `r`，并为合法无秘密预检提供有限失败检查点。

## 独立覆盖

| 独立未绑定模块 | 节点数 | 证明范围 |
| --- | ---: | --- |
| `tests/test_native_policy_audit.py` | 20 | 构建产物中 post 只读校验与强制 Px 并存；pre/post 静态入口的合法预检固定诊断、非法参数及普通握手静默；15 类映射、namespace、挂载、resolver 与撤权的 OS 边界拒绝 |

权限修复先由缺少 post `r` 的回归断言复现；诊断先由两个静态入口无法返回
固定 identity 检查点的回归复现，再补实现。新测试不依赖已安装策略：
构建不加载 AppArmor；静态入口在自身固定身份检查处拒绝；后段 OS adapter
替换相关文件、`prctl`、capability、`unshare` 和 `mount` 边界，不实际创建或
修改 namespace/mount。测试 adapter 的选择语言仅存在于临时编译的测试程序，
生产 pre/post 没有 syscall 探针、任意目标或测试模式。

## 操作与规则对应

这里的“覆盖”指源码操作与生成规则的对应；不声称这些规则已在候选真实内核
全部执行通过。目录、真实 resolver 目标、Python/Node/install 由构建配置封印。

| native 操作 | 所需策略或系统约束 | 核对结论与有限检查点 |
| --- | --- | --- |
| 首次 `untraced()`、严格 argv、目录/socket 形状 | pre/post `/proc/self/status`（实际可解析为数字 PID 路径）可读；普通 argv 只接受固定临时 socket 形状 | 初始检查继续位于诊断开启之前；非法 argv、预先 trace 拒绝静默，不能借诊断开放操作 |
| `setrlimit/getrlimit(RLIMIT_CORE,0)` | 只降低本进程限制，无需新增 capability | `entry_core`；没有提高 hard limit 或忽略失败 |
| `close_range`、`clearenv` | 固定 FD 上界、空环境；不需要文件或 capability 规则 | `pre_fd_cleanup`、`post_fd_cleanup`、`entry_environment` |
| pre `PR_GET_NO_NEW_PRIVS` | 必须 NNP0，不能提前设置 NNP 跳过 Px 转换 | `pre_nnp` |
| pre 自身身份、祖先与 xattr、UID/GID | pre 自身 `mr`；每级祖先目录 `r`；无 symlink、root 所有且不可组/其他写、无 setid/filecaps；固定非零三 UID/GID | `pre_identity`；无放宽身份检查 |
| pre 读取并核对 program，固定 fd3 | 固定 program `r`、祖先目录 `r`；内嵌规范字节与 EOF | `pre_program` |
| pre 只读打开 post 并核 root 保护 | 固定 post **`r`**；这是本轮唯一新增文件权限 | `pre_post`；保留独立强制 `Px -> paperradar-placement-post-v1`，不授予 pre `ix/ux` |
| pre 读取 AppArmor current label | `/proc/self/attr/apparmor/current` 和数字 PID attr 固定规则 `r` | `pre_profile`；仍精确要求 enforce label |
| 普通入口固定 inbox 目录 fd5 | 由三受保护来源的祖先目录生成 inbox `r` | `pre_inbox`；仅 normal 路径，静默拒绝 |
| resolver 源保护、字节、fd4、源 mount flags | 固定源 `r`、祖先目录 `r`；`fstatvfs` 必须与封印 flags 相同 | `pre_resolver_source`、`pre_resolver_flags` |
| resolver 目标只读打开与形状 | 规范固定目标 `r`，regular、非产品 owner、不可组/其他写 | `pre_resolver_target` |
| initial user/mount namespace 检查与再次 untraced | proc `ns/user`、`ns/mnt`、status `r` | `pre_initial_userns`、`pre_initial_mountns`、`pre_untraced`；仅无秘密预检可从 owner 私有 mountns 起步，initial userns 仍强制 |
| `unshare(NEWUSER\|NEWNS)` | 仅 pre `userns,` 与 `capability sys_admin,`；宿主限制不修改 | `pre_userns`；post 保持 `deny userns/capability/mount` |
| `setgroups=deny`、同非零 UID/GID 单映射 | proc `setgroups/uid_map/gid_map` `rw`；pre `setuid/setgid` 仅映射所需，不能映射 UID0 | `pre_setgroups`、`pre_uid_map`、`pre_gid_map`；dumpable0 仍在写映射之后 |
| `PR_SET_DUMPABLE=0` | 本进程 prctl，不需额外策略授权 | `pre_dumpable` |
| `/` recursive private | pre `capability sys_admin`、`mount options=(rw,rprivate) -> /` | `pre_mount_private` |
| fd4 resolver 绑定到固定目标 | pre `mount options=(rw,bind) 固定源 -> 固定目标`；proc fd 路径规则与源 `r` 均存在 | `pre_mount_bind`；不接受任意源或目标 |
| 固定目标只读 remount | `mount options=(ro,bind,remount,封印源flags) -> 固定目标` | `pre_mount_readonly`；保留 nosuid/nodev/noexec 等已封印 flags，无通配 mount |
| resolver fd 可继承、inode/只读/字节复核 | 源/目标 `r`、proc fd `r`；内嵌字节、同 inode、ST_RDONLY | `pre_resolver_descriptor`、`pre_resolver_verify` |
| 锁 securebits、清 ambient、逐项清 bounding、拒绝未知未来 capability、清 effective/permitted/inheritable | pre `capability setpcap`；先锁与 drop，再 capset 全零；capget/各 prctl 回读不可省略 | `pre_securebits`、`pre_ambient_caps`、`pre_bounding_caps`、`pre_bounding_limit`、`pre_capset`、`pre_caps_verify` |
| 固定 exec post | 唯一强制 `Px`；`deny change_profile` 限制显式 change_profile，不改为可 fallback 的执行模式 | `pre_exec_post`；真实转域实效仍须现场核验 |
| post 首先安装 NNP/seccomp | 不请求 capability；NNP1 与 filter 必须成功后才能加载动态解释器或握手 | `post_seccomp`；namespace、mount、新 mount API、capset、身份变更、ptrace/跨进程注入仍不可逆拒绝 |
| post 自身身份、program fd3、label | post 自身 `mr`、固定 program `r`、proc exe/attr `r`；inode/xattr/UID/GID/规范字节/enforce label 保持 | `post_identity`、`post_program`、`post_profile` |
| 私有 namespaces、单映射、cap0 与 securebits | post proc `r`；全部 capability 为零、bounding/ambient 零、精确锁位 | `post_userns`、`post_mountns`、`post_uid_map`、`post_gid_map`、`post_caps_verify` |
| resolver 与普通 inbox 复核、dumpable1 | 固定源/目标 `r`、inbox 目录 `r`；继承 fd4/5 固定身份 | `post_resolver_verify`、`post_inbox`、`post_dumpable`；关闭 resolver fd4 后才允许后续握手 |
| traced preflight 允许固定 parent、输出 R、读单字节 G 和 EOF | post `ptrace (readby,tracedby) peer=unconfined`；prctl 限 parent；stdio 是既有管道 | `post_ptracer`、`post_ready`、`post_release`；pre 仍 deny readby/tracedby；没有 `ptrace trace` 授权 |
| preflight 固定 true exec | post 仅真实规范 true 路径 `ix`；动态 loader/系统库由现有 `/lib/**`、`/lib64/**`、`/usr/lib/** mr` 与 ld cache `r` 覆盖 | `post_exec_true`；不增加 true `r`，不增加任意可执行文件规则 |
| 普通固定 Python、wrapper 与依赖加载 | 固定 Python `ix`；runtime Python 与 site-packages `mr`；wrapper 位于封印 site-packages 内；loader/库规则同上 | `post_exec_python`，仅 normal 静默路径；native 前置 NNP/seccomp/cap0 不变 |

## 普通运行后续链

wrapper 只消费 program fd3 和 root 已验证 inbox fd5：program 固定规则 `r`，
三个 inbox 来源各自固定 `r`，proc stat/cgroup 与 sysfs cgroup 树 `r`；配置与
观察在握手前及最终执行前重新验证，不沿用旧 inode。socket 只连接已校验的固定
临时 handshake，现有路径 `rw` 与 Unix stream 规则覆盖。接收的 install lock
仍须 inode/类型/只读 FD 校验，策略有固定 lock `r`；metadata FD 是校验的匿名
非阻塞写 pipe，不开放磁盘 metadata 路径。

auth/model 临时目录固定形状及子项枚举由对应 `/tmp/paper-radar-auth-????????/`
和 `/tmp/paper-radar-pi-????????/` 的现有 `rw`/`rwk` 覆盖。auth 使用固定 Node
`ix`、冻结 helper 的 site-packages `mr`、固定 install `mr` 与 credentials
`rwk`；model 同一固定 Node/install，cwd 只读，执行前额外施加原 Landlock。
negative 使用固定 Python、冻结 probe 及固定 model-manifest `r`，只发封印四类
IPv4 socket 负对照。现有 inet stream/dgram、Unix stream、TLS/hosts/NSS/resolver
只读规则与收到信号/同 profile 子进程信号规则保持，无新增网络族、凭据或执行范围。

Python/Node 和 true 是现有三条固定 `ix`。没有通用 shell、NSS helper exec、
任意解释器、任意 argv/env/path 或第二次 userns 接口；post 不可重执行 pre/post。
真实 Node/libuv、DNS/TLS、Landlock、外部 ptrace、最终 exec-stop 和全部旧负例
仍须 owner 在新包部署后验证，源码/策略 parser 成功不替代其现场结果。

## 有限诊断协议

只有严格 argv 校验通过的 `--preflight` 或 `--preflight-traced PARENT` 才启用
`placement_native_v1:CHECKPOINT\n`。拒绝仍退出 125；消息只含
`NATIVE_PREFLIGHT_CHECKPOINTS` 的 50 个固定源码字面量，不含 errno、路径、内容、
argv/env、token 或 Prompt。未知、超限、混合或不完整消息不得推定成可信检查点。
诊断写入失败不改变拒绝；仅终止前的诊断分支忽略 SIGPIPE，关闭的诊断读端仍由 pre/post 真实静态入口验证退出 125；非法 argv、初始 pretrace 与普通 auth/model/negative
入口保持静默。列表中 normal 专用检查点用于操作清单，normal 不输出它们。
traced 模式 R 之后的 release/true 失败同样要由 supervisor 收集，不能只检查 R 前。

本轮没有执行 root helper、加载/移除策略、实际 namespace/mount、真实 scope、
网络、认证或模型；没有执行完整离线门禁，没有冻结新源码向量。
