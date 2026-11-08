# #167 A4：Landlock process_vm_readv 的合成正负对照

本次仅补“同uid不等于必须跨uid部署”这一窄事实。新增独立D1模块 `tests/test_issue167_landlock_process.py`，不改产品源码、身份、固定白名单、旧测试或宿主策略。没有真实Node/Pi、认证、外部网络、崩溃、真实进程环境或凭据读取。

## 实际方法与结论

测试启动一个空环境的合成Python target，只分配固定25字节哨兵buffer，通过匿名管道输出自身pid、buffer地址和长度，随后等待父进程释放。target仅对自身设置PR_SET_PTRACER_ANY，不修改全机Yama；它不是任何真实应用或持密进程。两个peer只对该明确buffer地址调用process_vm_readv，结果在本进程内与固定哨兵比较，仅输出allowed/denied/unknown，不输出读取内容。target在所有peer检查完成前保持存活并由父进程最后回收，未读取其他地址、进程或文件。

| 对照 | 约束 | 普通用户工具沙箱外实际结果 |
| --- | --- | --- |
| 正对照 | 同uid合成peer，显式no_new_privs=1、core软硬限额0；不添加新Landlock域 | `allowed`，准确读到该哨兵buffer |
| 负对照 | 同一peer代码/target/地址，经过现有IsolationBoundary；core限额和no_new_privs同正例 | `denied`，syscall返回-1且errno=EPERM |

这支持**当前内核、同uid、所选target在peer新增Landlock域之外的关系下，现有隔离边界阻止该process_vm_readv读取**。正例先成立，才把负例用于Landlock相关结论；没有以两例都被其他策略拒绝推定Landlock有效。

负对照仅为合成Python对端私有注入Python标准库路径，沿用已有隔离测试方法；生产白名单和ISOLATION_POLICY_VERSION不变。没有读取真实安装/凭据或更改产品启动策略。父进程只对自己新建的固定target在有限等待后结束；正常通过时关闭输入管道使target自退出，不发送调试attach或宿主信号。

## 环境失败保留

第一次在工具默认沙箱内运行，**正对照直接得到denied，测试以positive_control_unknown失败**，未进入可宣称的Landlock正负比较。没有skip、调整Yama、放宽产品策略或将此失败改写为通过。

之后仅以同一普通用户、工具沙箱外执行同一离线测试，得到正例allowed、负例EPERM，`1 passed`。这不是sudo/root，也没有从其他进程读取数据。默认工具沙箱可能额外限制跨进程读取，因此该环境的正例失败仍是unknown；不能把工具边界差异迁移成实际部署证明。

## 本机文档与尚未证明

本机 `landlock(7)` 的Ptrace restrictions说明新增sandbox对操纵其他进程有额外域关系限制，并非只有文件路径限制。本次压缩手册SHA-256：`c00f2a92edf2cd061ee2a56bb69cd09e2491c9a89dd62df6811c4886f667be9f`。此文档与实际对照一致，不从手册外推未测syscall。

本次没有测试ptrace attach、process_vm_writev、pidfd_getfd、/proc内存/fd路径、跨进程信号、不同uid、跨namespace、任意后代逃逸或真实controller/auth/model关系。不能把这一条负例称为“全部同uid内存/进程隔离通过”，也不能把它作为系统服务/网络/文件/H1/H2准入的替代。完整部署仍需按实际域关系和受控案例分别核查；不据此自动采用新拓扑或放宽权限。

## 验证

命令统一 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`：

- 默认工具沙箱内 `pytest -q tests/test_issue167_landlock_process.py`：1 failed，原因positive_control_unknown，实际正例为denied；保留上述限制。
- 普通用户工具沙箱外同命令：1 passed，0.18s。
- 定向Ruff check/format通过；`MYPYPATH=src … mypy tests/test_issue167_landlock_process.py`：1 source file通过。

仅新增一个独立未绑定D1节点，不进入历史分母/required集合或旧回执；未运行完整离线门禁。之后只对内嵌target代码作断行格式修正，未改变语义，没有额外制造内存读取场景；最终树的检查由主代理整合。
