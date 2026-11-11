# #184 专用封印放置入口独立覆盖

本台账为 D1 新增覆盖，不增加既有验收组成员或固定分母，不改写历史回执、
v1–v16 源码向量及 pins。依据为所有者对专用入口和附着该入口的 AppArmor userns
授权的[公开确认](https://github.com/MeteoBoy4/PaperRadar/issues/184#issuecomment-6792224122)。
完整离线门禁由集成收尾时的唯一执行者另行运行，本轮只运行相关离线测试。

## 公开接缝及数量

| 独立未绑定模块 | 节点数 | 证明范围 |
| --- | ---: | --- |
| `tests/test_sealed_placement_protocol.py` | 38 | 闭合 auth/model/negative 语言、精确模板重建、重复键/NUL/超限/未知字段、FD 与临时资源形状 |
| `tests/test_sealed_placement_native.py` | 6 | 两静态 ELF 与精确两 profile 的离线编译、serialized wire ABI、原生 OS adapter 的预先 trace/继承 NNP 拒绝、seccomp 拒绝与线程兼容 |
| `tests/test_sealed_placed_process.py` | 5 | 生产 encoder 和新 wrapper 的真实 socket/ptrace/最终 exec-stop；恶意私有 JSON 独立拒绝 |
| `tests/test_sealed_placement_observation.py` | 5 | 真实文件系统下握手后原子替换观察正常接受，过期/混配/target 漂移/软链拒绝 |
| 合计 | 54 | 不作为现场 AppArmor 或真实放置证明 |

`tests/pi_placement_support.py` 的既有 OS adapter 使用
`tests/fixtures/pi_placement_os_adapter.py` 保留原任意无秘密测试目标语言。
生产入口没有选择该 fixture、任意 Python `-c` 或测试模式的开关。
既有文件隔离、core0、ptrace、NNP、FD 与最终执行身份负例继续运行；冻结测试正文没有减少断言。
新 PlacedProcess adapter 只替换 native/systemd/cgroup 与受保护配置供给，实际 encoder、
JSON 接收校验、真实 socket、parent SEIZE 和最终目标 exec-stop 保持执行。

## 实现边界

`freeze_placement(staged_root, site, source_root, ...)` 只进行非特权离线构建。
它输出固定 `placement-pre`、`placement-post` 静态 ELF；直接解析 ELF64 拒绝动态
INTERP/DYNAMIC、其他架构及可执行栈。程序不带任意目标 CLI，仅有正常固定握手定位参数
和闭合 `--preflight`。后者只允许最终 `/usr/bin/true`，成功无输出且退出 0，拒绝无输出且退出 125。

pre 在 initial userns 中验证 root 保护的路径、配置及 resolver 字节，拒绝正常预先 trace
与继承 NNP=1。它创建 NEWUSER/NEWNS，将产品 UID/GID 映射到同一非零值；写 map 之前
不设置 dumpable0，避免 `/proc/self` owner 变化造成误拒。随后 dumpable0、rprivate、
bind 与只读 remount 保留已绑定的源挂载 flags，撤销 bounding/ambient/全部 capabilities
并锁 securebits。唯一固定 post 通过强制 `Px` 转到独立 enforce profile。

post profile 无 userns/capability/mount/change_profile 权限，仅允许固定冻结 Python、
固定 Node 和闭合 preflight 的 true 执行，不能再执行 pre/post。
post 在动态代码与握手之前设置不可撤销 NNP/seccomp；拒绝 namespace clone、unshare、
setns、mount 及新 mount API、提权和向其他进程注入。clone3 返回 ENOSYS，普通线程和
Landlock 系统调用保留，x32/其他架构拒绝。OS adapter 实测普通 pthread、fork 和
Landlock ABI 查询保留，以及 x32/i386 syscall 路径被 SIGSYS 终止；这不证明 Node/libuv
在新真实 profile 下已通过。

非零映射后 root UID 不可见。pre 只继承固定只读配置 fd3 和 resolver fd4；post 对照
编译内嵌字节与固定路径 inode 再核映射、私有 namespace、cap0 和只读 resolver，
不把 overflow UID 当作 root 所有权证明。Python 仅继承 fd3 并消费后关闭；其他 FD
只能从闭合协议接收精确 install lock 与 auth metadata write pipe。
normal pre 另验证固定 root 保护 inbox 目录并继承只读 fd5；wrapper 通过该目录的
固定名称 openat 在 R 前、执行前读取当次新 target/current/refresh，核规范配对、60 秒租期、
自身真实 scope/祖先/anchor。原子更新 current/refresh 不沿用旧 inode 或旧租期。
执行前关闭 fd5，父 PlacedProcess 仍在握手和最终 exec-stop 处反复核验。

auth/model/negative 的 argv/env/cwd/install/proxy/runtime/resolver 均从冻结程序配置重建。
wire 只携带操作名、受限临时资源和必要的 model token/prompt 或 auth timeout。
没有任意 argv/env、脚本、loader、runtime 路径、resolver 或 metadata FD 索引字段。
敏感 token 只保留在产品进程与私有通道内存，不写构建清单或 root 元数据。

## 构建与安装承接

profile 原文和未压缩 binary 位于 `placement/apparmor.source` 与 `placement/apparmor.bin`。
编译使用 `-Q -K --zstd-compress-level=0 --Werror`、空 parser 配置及固定复制的 ABI/features；
不加载内核或缓存。`placement/build.json` 记录 source/binary/includes/ABI、native/config
摘要、编译器/assembler/linker/cc1 与 headers/static archives/CRT/specs 身份、初始
namespace 身份，以及固定 resolver 源/规范目标/摘要与 mount flags。
`raw_abi` 解析自 serialized stream 的 NAME(version)/U32 头；不能由 policy feature ABI
文件名或现有内核 profile 的 ABI 推导。

实际 profile 精确内核回读、安装/升级/卸载/恢复和 builder 接线由独立安装实现承接。
正常入口要求编译绑定的初始 user/mount namespace；owner 私有 mount namespace 中的
无秘密 preflight 仍要求同一初始 user namespace，随后另建私有 NEWNS。
现场须核 `apparmor_restrict_unprivileged_userns=1` 与
`apparmor_restrict_unprivileged_unconfined=1`，绑定观察并拒绝漂移；源 unconfined 的
显式 `aa-exec`/change_profile 借权路径不能仅由 attachment 名称宣称封闭。

## 威胁与未验证范围

`TracerPid != 0` 是正常预先 trace 的拒绝条件，不构成抵抗已经控制指令的恶意 tracer
的保证。mainline AppArmor 的 domain transition 检查跳过既有 unconfined tracer；
pre 的 `deny tracedby/readby` 不能据此宣称抵抗所有既有 tracer 注入。
既有[证据威胁模型](../contracts/live-evidence.md#不提供不证明)不防同 UID 直接修改源码，
仍依赖代码审阅与策略版本守卫；本实现不把该排除项扩大成任意 JSON/CLI 借权通道。

本台账没有执行 sudo/root helper、加载 AppArmor、实际 NEWUSER/NEWNS/mount、真实 scope、
网络、认证或模型。实际 profile attach、mount option 编码、映射与 securebits、合法 parent
ptrace、最终 Pi exec-stop、文件隔离、Node/libuv、core/Apport、FD、所有原负例及
`aa-exec pre -- python -c` 等借权负例，仍须由所有者审新包后先在无秘密入口逐项验证。
未知或失败继续保持 host gate，不授予资格、不触发 auth/model 自动补跑。
