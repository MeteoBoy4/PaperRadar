# #167：认证前观察适配与同 UID 合成 IPC 反馈

本轮继续 A2/A4/A6，仅在工作区与自建临时实例准备下一批次接缝。没有真实 Node/Pi、网络、root、真实安装锁、凭据、业务记录或宿主配置变更。所有者确认的认证目录仅用于准备，不由此取得认证/模型许可。

## 资源观察适配

新增 `scripts/issue167_live_resources.py`，只在独立 controller 的受控 context 内临时替换公共 launcher 的 AttemptResources。原目录建好后、model Popen前arm；原管道/组回收之后，实际CG只剩controller才封终态；先核窗口完整，再原rmtree、独立deleted及receipt。原argv/env/preexec/安装FD与产品身份不变。

默认只接kernel-own CgroupReader，fixture须显式synthetic=True。构造的虚拟close、初始化失败、残留子孙、overflow、post-terminal写入及watch关闭失败均不会产生可接受的完整摘要；模型窗口不完整时保树。退出恢复原工厂和租约，不据此声称任意信号/FD关闭故障必然清理成功；外层unit仍负责失败回收。

独立D1 `tests/test_issue167_live_resources.py`14项通过，含真实自建Python public prepare_launch/Popen/preexec/pipe及inotify的窄反馈，CG来源显式fixture。另一个fresh仅跑回放子集12 passed、2 deselected，不把该子集写成14项实测。watch-close误留完整摘要和清理中断租约泄漏均先红后绿修复。两文件mypy/Ruff/format通过。

window_complete只证明窗口完整。主批次另要求history=zero_observed、mutation=0、终态settings基线regular1/other3、deleted和post-terminal mutation0；不得用终态或完整性替代历史零写入。backend的synthetic_snapshot是既有标签，真实来源、事件后端与stat仍分别登记，不偷改旧身份。

## 一次真实的自建 IPC 反馈

新增 `scripts/issue167_live_ipc.py`，只访问本次新建Python target的固定非秘密buffer/file与自设无害signal handler。PID、地址和FD号仅在匿名管道/私有内存中传递，不进回执；未读取其他进程内存/环境，不接触真实凭据。target的PR_SET_PTRACER_ANY只设置自身，不更改全机Yama。

按已有 A4 的不联网、不提权、不改宿主合成范围，主代理以同一普通用户工具沙箱外执行一次，0.59s退出0；最多7个target、14个peer/探针，本次完整完成。默认工具沙箱曾对旧readv正例施加额外拒绝的历史不改，本次没有重复那个已知受限环境。

| 类别 | 无新增 Landlock 正例 | 原隔离关系负例 |
| --- | --- | --- |
| process_vm_readv | allowed，固定marker吻合 | permission denied |
| process_vm_writev | allowed，仅固定buffer，target确认写入 | permission denied，target确认未改变 |
| ptrace | own target SEIZE/INTERRUPT/DETACH成功 | permission denied |
| pidfd_getfd | own target固定文件FD取得并比对marker | permission denied |
| /proc/target/mem | 仅读固定marker地址/长度，吻合 | permission denied |
| /proc/target/fd/固定fd | 仅读自建固定文件marker，吻合 | permission denied |
| SIGUSR1 | own target确认收到 | permission denied，未收到 |

七项cleanup_complete均true，receipt为observed_expected/integrity=complete。临时target/peer由本次代码有界收尾，临时目录随正常context清理。没有向宿主其他进程发信号或attach，没有新socket/Node/Pi。

反馈在 `.scratch/issue-167/ipc-afk-feedback.json`，SHA=`7f16fc64e9733ed80d878128f25a5a5998132641b12d87532af89b8ae9737e41`。反馈后、元数据型别修订前核对的冻结源码SHA=`289eecd1c988a292dd2790d42e23100686ea519f16b3706b526d921248016977`，身份记录于ipc-afk-feedback-source.json；用精确反向差异重建的ipc-afk-feedback-source.py与此SHA一致，不是另一次执行。

这个结果只支持当前内核、同UID、自建target/peer域关系及选定七条路径；Python peer仅为fixture加版本化stdlib读取权限，产品白名单不变。不证明任意跨进程渠道、真实Pi或未来unit已通过。下一待审服务仍在认证前执行本包IPC门槛，control不成立/unsupported/metadata坏/cleanup未知均unknown停止，不借AFK反馈推免现场。

## 元数据型别修订与验证

fresh纯mock发现target reset/state/signal_state的数值0/1可因Python相等比较伪装bool。主代理补6个直接KernelPair.probe回归并加入严格keys/type/is校验；旧弱比较隔离回放6 failed，当前完整IPC模块 **28 passed**。reset损坏受控拒绝，state损坏变unknown，由上层停止。两个文件mypy/Ruff/format通过，fresh确认无新增阻断。

TARGET/PEER与真实syscall步骤、动作上限未变；当前源码SHA=`8a681f3074e8882f8409a1e060de59e06594ebeada3b47286ccb691d6262f08a`。上述真实反馈来自修订前源码，payload为源码固定true/false，不把它改记为最终源码重跑；新服务仍须认证前复核。没有追加真实IPC矩阵或悄悄复用已消费现场预算。

新增模块按独立未绑定D1分别14/28项登记，不进历史分母、required或正式回执。后续完整批次的root/DB写、认证、模型、材料、预算和恢复仍须具体新H1/H2/H3，H5与产品激活独立；未运行完整离线门禁。内部配置、具体元数据及相关哈希只留本地，不发布GitHub。
