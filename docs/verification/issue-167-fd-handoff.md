# #167：原安装锁 OFD 传递的离线合成验证

本次仅验证 A4/A6 候选共同需要的 fd 生命周期语义，依据 [ADR-0029](../adr/0029-protect-installations-through-inherited-flock.md) 和[剩余决策审查](../../intent/review/issue-167/remaining-decisions.md)。代码为 `scripts/issue167_fd_handoff.py`，独立未绑定测试为 `tests/test_issue167_fd_handoff.py`。没有修改产品 `prepare_launch`、固定供给、manager/unit 或现有历史证据。

## 方法与实测

调用方在 pytest 临时根建立不含秘密的普通合成锁文件。driver 以只读 `O_NOFOLLOW` 打开并取得非阻塞共享 flock，通过匿名 `AF_UNIX/SOCK_SEQPACKET` socketpair 的 `SCM_RIGHTS` 把原 fd 交给固定的合成接收进程。接收者再以 `pass_fds` 让自己的固定 Python 子进程继承收到的 fd；接收者关闭自身 fd 后才发送接管 ACK。全过程不读取锁文件内容，不传 token、不读取环境或认证，不监听地址或建立任何外部连接。

| 主张 | 方法与结果 | 证明边界 |
| --- | --- | --- |
| 接收的是同一 OFD | 后代对收到 fd 执行 `lseek(...,7)`；driver 的原 fd 位置同步变成7 | 共享偏移量证明本合成路径的 OFD 共享；inode相同单独不够 |
| 重新打开不能冒充原 OFD | driver独立重新打开同一普通文件，inode相同但偏移仍为0，原fd仍为7 | 独立open可另获SH锁，但不是同一OFD，不能作为原fd已转交的证明 |
| 父 close 不提前解锁 | driver关闭自身fd，接收者此前已关闭自身副本；后代仍存活时独立 `LOCK_EX|LOCK_NB` 被拒绝 | 保留关闭而非 `LOCK_UN` 语义；没有演示或允许生产显式解锁 |
| 正常收尾释放 | driver发 RELEASE，接收者释放并等待其固定后代，然后退出；driver等待接收者 | 独立EX锁随后可取得；这些固定进程无fork逃逸，不是任意后代/cgroup的完整回收证明 |
| ACK缺失 | 后代已接管并共享fd后，接收者故意不发ACK；driver 0.3s ACK截止触发 `handoff_ack_missing`，关闭通道/有界等待，接收者回收固定后代 | 实测总时长小于2s，独立EX锁可取得；不是manager故障、机器断电或恶意服务的证明 |
| ACK失败 | 接收者发送FAILED，driver只接受精确ACK，返回 `handoff_ack_failed` 并回收 | 失败不作为接管成功，独立EX锁可取得 |
| 无fd帧不能自证 | 匿名对端只发送合法字面帧、没有SCM_RIGHTS，返回 `handoff_frame_invalid` | 协议形状拒绝，不替代生产peer身份/来源校验 |
| 超时参数 | 0、越界、NaN、bool 在打开路径前被拒绝 | 返回受控 `handoff_timeout_invalid` |

driver 使用同一有限超时等待ACK、关闭后的响应和接收进程；超时兜底只针对本次创建的新进程组。接收者对后代就绪/退出分别有限等待，所有控制输出只为固定字面ACK，子进程stderr丢弃。异常处理不导出文件路径、内容、外部异常文本或pid。内部 `PeerProcess.pid` 只用于回收自建进程，不构成公开安装保护事实。

## 运行环境限制与失败保留

本工具沙箱允许匿名socketpair和sendmsg/recvmsg，但对sendall/recv及exec后 `socket(fileno=...)` 的部分底层元数据操作返回EPERM。最初使用这些接口的合成运行失败，未将它们记为通过；没有申请提权或改沙箱/宿主策略。当前用 fork 继承已有 Python socket对象，并明确使用 sendmsg/recvmsg；后代exec仅继承合成锁fd。这条通过路径证明 Linux 匿名IPC/OFD语义，**尚未证明通过exec创建的服务bootstrap能在本环境包装socket或与systemd接线**。

## 没有提供的保证与下一步

- 没有实现systemd manager桥、SCM_RIGHTS命名socket、peer uid/PID/cgroup认证、跨uid转交或部署门闩。匿名socketpair的先天对端绑定不能外推到pathname服务端。
- 原型peer由driver直接fork，manager独立创建服务的差异仍然存在；不能只复制本原型就称双unit方案已可部署。
- 不传实际 `InstallUse` 或真实安装锁，不读取产品数据库/供给树。生产接收还需核验原锁inode、完整绑定、固定安装与接管身份；不能用本回执替代公共 `use_install`。
- 无token内存桥、秘密生命周期、core隔离证明。fork合成peer不提供与driver内存隔离的保证；真实秘密不应因此被引入。
- 未模拟SIGKILL/进程逃逸/manager重启/全部后代验证。测试的“清理完成”只限固定有限后代、正常或ACK失败控制流；H1/H3仍需真实cgroup的独立回收观察。
- socket/wrapper变化、不同uid/挂载视图、bootstrap或manager fd-store方案均需重新验证并交H1/H4；不修改固定安装、不直接激活任何证据。

## 验证记录

命令统一 `uv run --offline --locked …`，环境前缀为 `UV_CACHE_DIR=/tmp/issue167-observation-uv`：

- `pytest -q tests/test_issue167_fd_handoff.py`：5 passed，0.47s。
- `ruff check` 与 `ruff format --check` 两个新增Python文件通过。
- `MYPYPATH=src … mypy scripts/issue167_fd_handoff.py tests/test_issue167_fd_handoff.py`：2 files通过。

五个节点仅为独立未绑定D1覆盖，不进入既有A1–A10分母或历史回执。未运行完整离线门禁，未申请现场调用/认证、root动作或产品激活。
