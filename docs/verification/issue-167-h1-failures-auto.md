# #167 H1 失败移交、自动化与 systemd259 capability 取舍

本轮承接[初始H1合成包](issue-167-h1-synthetic-local.md)，保留全部旧包、失败结果、消费记录与历史字节。没有将失败改为passed，没有重启旧run、退款或改ID自动补跑。普通产品read_evidence仍缺失，Live/B不因此完成。

## 两次实际失败与恢复

| run / 包 | 实际事实 | 已复核恢复与限制 |
| --- | --- | --- |
| `6e70b5a31d42` / h1-synthetic-local-v2 | root ledger导出unknown，observer_failure，phase_counts为空，cleanup_complete=true、table_may_remain=false。runtime根root0700，worker目录uid/gid1000、0700；worker_started/ready/go-a/go-b/阶段结果均不存在。root guardian-result实际存在root0644，但普通用户不能穿过父0700，解释了用户复制结果缺失 | 两unit文件已删除，manager无加载路径/活动CG；owner restore报告host_policy_restored。artifacts.json为空不是成功。code/runtime和永久ledger保留，不能声称失败材料已清除；旧observer_failure未记录阶段，不能唯一反推确切异常 |
| `7c93ab04d615` / h1-synthetic-auto-v3 | 自动owner envelope unknown；guardian在peer_start因guardian_runtime_invalid拒绝。root UID、core[0,0]、NoNewPrivs正常；六项必需cap中仅setuid=false，其他5项true。guardian结果与永久ledger一致，未取得phase计数/leftover通过 | 自动restore报告host_policy_restored；两unit文件删除，managernot-found、无FragmentPath/DropInPaths/ControlGroup；guard残留failed退出状态不是活进程。新runtime根已0755，code/runtime与永久ledger保留；artifacts=null是按unknown不finish，不当清理成功 |

v2 ledger导出SHA=`a8d6c5176b08bcc861fb3b6ddd4d6f9fe9adf5f86ad10151d09b748b44b11c6c`；owner只读导出11个固定路径lstat到results/diagnostic-metadata.json，不读内容。已安装公开代码19/19与封印一致。v3 owner-run.json SHA=`f56fbc77f0f5fe2d05985c2dc889a80f80835d8ab8a9b8ee306c1f183dfddb39`；其旧源清单、driver与外部seal维持原值。

## 已复现的初始化缺陷

- 单一真实reserve反馈环：服务UMask0077下，mkdir(mode0755)实际得到0700；0022才得到预期0755。回归先失败再修为只对本次新建目录用nofollow目录FD显式fchmod0755并回读，不更改已存在失败目录或全局umask；worker私有目录仍0700。
- 即使修模式，mkdir/chown中间态仍会被并行worker当最终状态而立即拒绝。独立回归先复现0等待的runtime_metadata_invalid，再改为root原子发布runtime-ready标记后才严格核对；标记前有界等待，标记后错误不重试。root700阶段不遍历私有子树，symlink/错owner/可写根不接受，标记限定root0644、nofollow/nlink/大小/重复key/精确run及状态。
- 新增受控failure_stage、OS错误类别与root自身选定cap/core/NoNew metadata，不保存异常原文、环境、命令行或完整日志。它让v3定位到peer_start，但不能回填v2历史没观测的字段。

## CAP_SETUID 的具体源码解释

本机systemd为259.5-0ubuntu3.4，Linux头文件CAP_SETUID=7；guardian十六进制解码及bit7正确。封印unit声明了SETUID，离线security解析也看到请求了身份变更能力，不能把bounding等同实际effective。

[上游精确v259.5 exec-invoke.c](https://raw.githubusercontent.com/systemd/systemd/v259.5/src/core/exec-invoke.c)中5533–5550：显式有效uid与当前seccomp条件进入keep_seccomp_privileges；5583–5596：Ambient不包含SETUID时明确drop该cap。5773–5804只恢复bounding并撤临时SYS_ADMIN/SETPCAP，不恢复SETUID。[capability-util.c](https://raw.githubusercontent.com/systemd/systemd/v259.5/src/basic/capability-util.c)说明drop清Eff/Prm/Inh。已安装executor包含对应错误标记。该机制与v3唯一缺SETUID精确吻合，是有明确源码依据的解释；不伪称已逐指令证明Ubuntu所有patch或重新执行root对照。

最小候选删除guardian冗余User=root：无User/PAM/DynamicUser/特殊ExecStart前缀时uid保持UID_INVALID，跳过该有效uid分支。[官方文档](https://raw.githubusercontent.com/systemd/systemd/v259.5/man/systemd.exec.xml)与本机man说明system service默认root。Group=root、capBounding六项、Ambient空、NoNewPrivileges、seccomp、Core/cgroup及实际UID/cap检查全部保持。不会增加Ambient或为通过而关防护。

登录环境变量缺省设置会改变，不能声称环境逐字等价；程序未读HOME/LOGNAME/SHELL，使用绝对路径/明确子进程env，Python-I/-S保持。这是同UID与同声明cap目标的源码预测，实际cap是否恢复仍须另获授权的现场验证。新增静态配置反馈环先红再绿，旧未绑定4节点中的布局断言同步改成默认root语义；不改旧封印或历史证据/分母。

## 只输入一次 sudo 密码的执行流程

依据所有者明确要求，后续不再让人复制具体root命令。ordinary driver仅一次调用绝对/usr/bin/sudo，密码只由sudo从TTY接收，不使用sudo-S/密码变量/ask_secret，不记录或保存密码。

- driver先验core与自身封印，排他预占独立execution-started；结果文件与临时stdout分离，失败也写受控unknown，不能又把空文件当成功。
- root stdin字面bootstrap不导入/执行workspace脚本。先fd-relative/nofollow验证源UID、普通文件/nlink1、大小、总量与SHA，再排他创建固定新root目录，显式权限不依赖umask，复制已验证字节。只对本次新建成员按dev/inode回收，不递归删除陌生对象；exec失败保留unknown。
- 之后只exec root-owned runner：scope预检→安装→原unit语法/归属核查→各unit启动一次→有界等待→独立读root结果/账本→finally恢复；预检冲突不stop已有对象，partial安装只做验证后恢复。unknown不finish，成功结果/账本一致才清理本包runtime/code；永久记录不删。
- SIGINT/TERM进入受控恢复，恢复期间屏蔽重复可捕捉信号；SIGKILL不保证。finish前缓存所需材料，删代码后只内存JSON输出，不再读已删文件或起子进程。
- driver成功须同时匹配退出码0、scope/run/coreSHA；非零退出的成功JSON降为unknown/interrupted。可写seal的自检不代表验证外部批准，也不构成产品准入。

为避免hash循环，core manifest及其members.sha256不含driver/review-seal；driver内嵌core SHA，外部review-seal绑定core+driver，实际H1审批绑定该外部封印。

## v4 包身份

`.scratch/issue-167/h1-synthetic-auto-v4-final/`，新run=`a840c6d21e97`，仅请求一次额外合成执行；旧两次unknown与永久记录均保留，不退款。

| 身份 | SHA256 |
| --- | --- |
| review-seal.json | `e2461d9622c0176d9bee26d676b15f835e6c6309c4a03d0dee78130806e3bee6` |
| core manifest | `64fa5e6b65119a0d60eee1f57565c41675887e4ebd7d4f266bfeaaf4c606fba7` |
| automatic driver | `286d1422e9ba9229c4faefe166dd3101073ba2009908722051377393b1e85d09` |

准备时拟将 retry-context 链接 v3；后续实测发现 CLI 未转发参数，实际封印仍指向 v2。准确结果、错误修复与一次性恢复待裁决见 [v4 现场及恢复台账](issue-167-h1-v4-recovery.md)，不按准备期意图重写实际历史。v3 旧 ledger 预期 SHA=`c3cd717342764d779e06d0769c34d0bcee9e1fbed2bf3261caad779a49a80b33`，由已验证 owner envelope 按发布器格式重建，不冒称普通用户已读 root0600 原字节。

端点/端口、20次loopback上限、无凭据/Pi/Node/模型/崩溃、NoNew/seccomp/空Ambient、精确表/资源根及恢复边界不扩大。所有者已明确批准此review-seal和一次额外H1/H3合成尝试，并已运行；现场仍 unknown，恢复尚未闭合，见上述新台账。静态语法副本与离线测试不写成现场通过。

## 验证口径

本轮相关组合198 passed，均为独立D1工程验证；新增能力配置contract1项、最新unknown lineage1项，已有unbound工程模块保持节点数但更新相关普通断言。无历史分母/required/回执扩充。Ruff/format/mypy通过，具体组合与最终scope审计留回帖。root source/bootstrap/自动化只做mock、临时文件与仅LOCAL_RESULT片段的无sudo回归，不运行新的root/service/nft/network。

副本语法校验仅在/tmp把ExecStart解释器替换为已有同字节副本后退出0，原包仍需实际安装后的verify；普通用户host-context一致。未跑完整门禁，未接loader或改变产品launch身份/协议，不重跑EXP-2。真实模型/认证、完整故障矩阵、正式校准、NAS与Live完成仍未验证/授权。
