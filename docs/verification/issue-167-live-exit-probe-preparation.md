# #167：独立无秘密监督收尾待审包

## 目的与身份

所有者已选择[H4 A](../../intent/review/issue-167/live-six-exit-decision.md)，允许采用六格有限事实；[仅清理已完成](issue-167-live-six-cleanup-result.md)。原六格仍unknown，新包只验证未来监督退出接缝，不解释旧e93根因或补写其退出证据，不重发任何认证/模型请求，不改变产品准入。

本地包 `.scratch/issue-167/live-exit-probe-v1/`，run=`d5f2a9017c84`。它尚未预占或执行，results仅有offline-validation.json。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `464ac510a4b082530f7a7624195c743a1bea6a42a77618b3e96dd97f7068ed87` |
| manifest.json | `c4c5dc1ce6e975c23f7e8d5282a2685e238dcd710489041cdcd3cf85c5d71cac` |
| owner-run.sh | `7b17ac43e9c9b0a48e73e205dfa84b452430df4c7acfef71033d4a88bddff0a5` |

manifest14成员为12个安装文件（10个标准库脚本模块、合成worker和unit副本）、scope.json、review.md。root使用先核SHA的字面stdin和空scripts package加载固定模块，不从可写工作区import应用；不是原40成员部署包或2284文件产品runtime闭包，不执行其中原六格run_owner。

## 具体H1动作与上限

仅新增 `paperradar-167-h1net-d5f2a9017c84.service`，代码 `/home/paperradar-probes/issue167-d5f2a9017c84`、控制目录 `/run/paperradar-issue167-d5f2a9017c84`，以及永久单次记录 `/var/lib/paperradar/probe-runs/issue167-d5f2a9017c84.json`。root顶目录0755、worker子目录UID/GID1000的0700，永久记录0600且不删除/退款。

所有者入口核封印后由一次sudo TTY执行：预占→安装本unit及两树→daemon-reload→本unit只start一次→观察ready/terminal→发布一次exit gate7→检查真实退出→本unit stop及必要reset-failed→卸载/daemon-reload→独立缺失与CG空→删除两树、保留记录。旧仅清理授权不包含这次安装或start，因此必须新的H1审阅执行。

worker只用系统Python标准库，检查自身软硬core0、NoNewPrivileges及五个cap集合字段为0；不运行Node/Pi、认证/刷新/模型、真实安装锁、数据库或崩溃。应用网络操作、socket探针、DNS/TLS/连接/发送均0；不查询或修改nft/resolver。root的systemctl使用必要本地manager IPC，不把这写成“完全没有任何IPC”。

worker等待40秒、service RuntimeMaxSec60、监督接缝绝对截止60、每manager命令8秒、清理停态窗口15秒；单次worker1、start1、exit gate1，零自动重试。Type=exec、RemainAfterExit=yes、Restart=no、KillMode=control-group、LimitCORE=0、NNP、空cap和地址族/网络syscall/IP/bind限制均显式列入unit。此轮不发网络探针，不把unit配置当作网络现场通过。

## 复用的真实接缝与证明边界

新Seam直接继承当前 `LiveOperations.phase_gate("exit",7)` 与 `wait_exit`，复用原resolver_owner._write、guardian.Commands.unit_state及phase.read_cgroup_state。唯一适配的_verify只核本probe代码/unit/目录身份与cgroup，不执行原规则/DB/模型全链；返回占位0/0不产生packet计数主张。

严格成功仍要求真实CG空，并且加载中的本unit为active/exited/success、ExecMainCode1/Status0、MainPID0、ControlGroup为本scope或空；不采用卸载后默认Result。gate publication和写入完成分开；fsync失败或缺参照不会改判成功，诊断失效也不能跳过恢复及永久记录。

ready与terminal都必须来自固定受审worker、PID与本unit/CG唯一进程一致、计数/布尔类型严格相同；不调用完整run_owner伪造六格、DB恢复或网络快照。输出只保存封闭类别、计数、完整性和退出状态投影，无任意stderr、异常原文、真实PID/CG路径或凭据内容。

## 恢复限制

不调用旧base.restore，它会访问nft/resolver。新恢复先核具名unit的Id/FragmentPath/DropInPaths/User/Group/CG与原文件字节，stop后确认CG空及精确停态；只在该unit failed时reset-failed，再卸载、reload和核缺失。清理只针对本次创建且身份可核的两树，以NoFollow目录FD相对删除，拒绝陌生成员、alias、跨设备/挂载及缺观察。

部分unit发布、写入或fsync失败可能使安装状态不足以安全恢复；此时严格unknown，保留具名单元和code/runtime，须另由所有者审阅执行仅恢复，不擅自降低归属标准。删除中途失败也可能留下部分树。本包不保证每类失败都自动清空，不重验、不回滚旧账本或删除认证目录。

## 离线验证与执行前快照

新增独立未绑定D1 `tests/test_issue167_live_exit_probe.py` **55 passed**；与既有exit诊断38相关组合 **93 passed**。覆盖真实方法identity/实际调用、严格终态、gate发布后fsync失败、诊断复制失败仍恢复、单start/单消费、unit归属和父链拒绝、部分安装留存、别名/挂载拒绝及清理。fresh审发现的finally诊断、unit父链保护和空/畸形mountinfo三项缺口均已修复并补负例；缺观察仍unknown，不凭空文本认定无挂载。

新probe源码/测试与另一个[合成故障D1](issue-167-offline-fault-engineering.md)共三文件mypy、Ruff check/format通过；没有为复核重发合成SIGINT或重复300秒控制。bash-n、实际固定/usr/bin/python3封印loader的唯一root_main调用移除控制通过：10模块加载、方法身份一致，root_main执行0。精确unit以普通用户只读systemd-analyze verify退出0且无输出；未安装或运行。

fresh最终审及主代理逐字核对seal、14成员、12个字面安装文件、10份当前源码、config、完整driver、worker和unit，无剩余阻断。五个精确FS目标（unit、代码、runtime、ledger、CG目录）均absent；普通用户只读manager为not-found/inactive/dead/MainPID0，Fragment/DropIn/CG/User/Group空。它是执行前快照，owner入口必须再次核验，不替代执行后结论。

本页及新D1不扩历史分母/required/正式回执，不改旧证据、产品LAUNCH/协议身份或安装树。新H1尚待；固定scope收集审计随本次收口记录，未运行完整离线门禁。其余真实故障/供应商能力、H5及产品接收/激活仍待；普通产品缺证据阻断保持。内部配置、metadata、绑定/回执和相关SHA只留本地。
