# #184 完整无秘密放置预检独立覆盖

本台账是新增 D1 覆盖，不扩大既有验收组成员、固定分母或历史回执。
依据为[专用入口授权](https://github.com/MeteoBoy4/PaperRadar/issues/184#issuecomment-6792224122)
中先以无秘密目标验证放置、撤权和 ptrace 的要求。

| 独立未绑定模块 | 节点数 | 证明范围 |
| --- | ---: | --- |
| `tests/test_sealed_placement_preflight.py` | 14 | 产品身份限定、真实 SEIZE/TRACEEXEC/DETACH、最终 true 身份、EOF/错误释放字节、失信和超时回收 |

## 两种闭合预检

`placement-pre --preflight` 是 namespace-only 模式。它核固定静态 pre/post、私有
resolver、capability 撤除、securebits、NNP/filter 和精确 post label 后仅执行 true。
退出 0 不证明 systemd scope、parent ptrace 或最终 exec-stop。

`run_traced_preflight(target, *, product_uid, product_gid, timeout=10)` 是产品 UID/GID
监督接口。target 由 root owner 核验后提供；函数拒绝 root tracer、不同产品身份和
非法超时，不读取 inbox、观察 lease、凭据、业务资格、配额或秘密。
它使用固定 `systemd-run --user --scope` 创建独立项目 scope，保留调用者的私有 mount
namespace。命令只执行固定 pre 的 `--preflight-traced <controllerPID>`。

post 在 exact post enforce label、cap0、锁定 securebits、NNP/filter 和私有 resolver
核验后关闭内部配置 fd3。它只写固定 ASCII `R <自身PID>\n`，随后阻塞读取 stdin；
唯一有效输入是单字节 `G` 后立即 EOF，随后唯一目标为 `/usr/bin/true`。
没有可变目标、argv、env、socket JSON、认证或模型模式。

产品 controller 在释放前核 pid/start、实际 scope、祖先 kernfs identity、anchor、固定
post executable、产品 UID/GID、cap Inh/Prm/Eff/Bnd/Amb 全0、NNP1、seccomp2、core0、
相对 controller 不同的 user/mount namespace、exact post label 和仅0/1/2 descriptors。
随后真实 SEIZE（TRACEEXEC/EXITKILL），写 G 并关闭 stdin，等待真正 true 的 exec-stop。
同一 pid/start、scope/anchor、true executable 与全部安全状态再次核验后才 DETACH。
最后必须 true 退出0且无额外输出。失败杀死并回收阻塞或被 trace 的进程组，不授予资格。

该 stdio 握手没有 SIGSTOP/group-stop，因此不把 SEIZE 与 group-stop 恢复语义当作假设。

## 真实离线证明与替代范围

OS adapter 编译并调用同一个 native `traced_preflight` 实现，使用真实 stdin/stdout、
seccomp、core0、NNP、pid/start、FD、SEIZE、TRACEEXEC 与 DETACH。
正例在内核 exec-stop 实际读取 true 的 `/proc/<pid>/exe`，并核 TracerPid 为 controller，
完成后确认进程已消失。错执行对象、NNP/capability/namespace/profile 失信、最终放置
漂移、提前退出、非法 ready、超时、EOF、错误 G 或额外字节均拒绝并回收。
ptrace 没有 mock；只有 systemd/cgroup、真实 namespace 创建、AppArmor label 与 capdrop
事实由明确 OS fixture 替代，因此离线通过不证明这些真实部署行为。

原生六节点构建/过滤模块保留原数量，其 profile 过渡 literal 预期修正为
`Px -> paperradar-placement-post-v1`，并拒绝 `Px -> &...`。
前者在 pre NNP0 时替换为 exact post；后者会 stacking，继承 pre deny 并产生不同
label，与 native exact post 检查矛盾。修前该 literal 回归明确失败，修后离线 parser
与静态构建通过；没有放宽 exact label，也没有删除 pre deny tracedby/readby。

## 现场边界

namespace-only 与完整 traced probe 均只执行 true，均不证明 auth/model、Node/libuv、
Landlock 全部行为或任何证据激活。实际 AppArmor 加载、替换式 Px 效力、真实 userns/map、
mount、scope、parent ptrace 和最终 exec-stop 仍由所有者审新包后先无秘密执行。
安装准备阶段无实际 target 时 namespace-only 可以检查局部支持；配置并核真实 anchor/
target 后必须执行完整 traced probe，不能拿前者退出0替代完整链的证明。
既有 pretrace 威胁边界及全部正常路径检查保持，见[入口覆盖](issue-184-sealed-placement-entry.md)。
