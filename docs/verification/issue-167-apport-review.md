# #167 A4：本机 Apport 项目排除边界只读核查

本轮仅读取 `/proc/sys/kernel/core_pattern`、`/proc/sys/fs/suid_dumpable` 和两份已安装公开Python源码；不导入/运行Apport，不读取任何现有crash/core、进程environ、认证或其派生值，不制造崩溃，不改宿主配置。

当前 `core_pattern` 指向 `/usr/share/apport/apport` 的pipe入口（包括PID/pidfd等内核参数），`fs.suid_dumpable=2`。这是本机当次配置，不表示后续仍相同，也不能外推为systemd-coredump行为。具体源码身份见下表；不公开进程/账号或其他用户信息。

## 关键顺序与影响

| 当前入口/行段 | 只读源码事实 | 对项目候选的影响 |
| --- | --- | --- |
| `apport:1015–1047` | 获得core stdin，创建包含CoreDump输入流的Report；SIGQUIT路径更早调用write_user_coredump | 只检查常规report-ignore不足以覆盖全部信号/分支；流对象存在不等于已读完内容，不把静态赋值误称实测写盘 |
| `apport:1073` | 在process_crash和其denylist判定前调用add_proc_info | 需要避免秘密被collector主动采集时，晚期忽略report不能证明符合要求；不运行该函数验证，避免真的读环境 |
| `apport:1120–1153` | 先记录带ProcCmdline的日志；非打包可执行文件等分支可能走write_coredump_callback，之后才check_ignored | 固定项目Node是否打包、LimitCORE实际值与信号会影响路径，不能只加项目可执行文件denylist就宣称安全 |
| `report.py:1398–1438` | check_ignored支持 `/etc/apport/report-ignore/` 的精确ExecutablePath及旧denylist目录；用户ignore又有其他规则 | 这是report呈现/抑制机制，不是可信cgroup下的最早拒收机制；精确Node路径也覆盖不了持有秘密的共享Python controller/后代 |

因此**本机现有Apport ignore列表不是当前要求的完整项目core方案**。本轮没有启用任何列表、关闭Apport、修改core_pattern或运行crash测试。`LimitCORE=0`是否让某个write_user_coredump分支不落文件，不解决此前proc信息读取、其他分支/日志与后代覆盖；不能把它外推成全过程无秘密core。

## H4 所需具体新取舍

若继续固定Node/Pi供给，候选是**在现有Apport之前增加按受保护项目cgroup身份判定的前置分发器**，项目命中时不读core stdin/不采集environ就关闭输入；非项目必须以原有argv/fd语义直接交还原collector。需要核对pidfd与cgroup身份、防PID复用/逃逸、controller与auth/model全链、失败模式、根权限代码、所有非项目透明转发与卸载恢复。它会修改全机分发链，尽管目标是保持其他程序的core语义，仍存在新的失败面，**必须H4明确裁决后才能进入该方案实现/验证，H1仍由所有者审阅root执行**。

替代是更改受控运行时/启动接口，在exec后、秘密到达前于每个持有秘密的进程内完成并保持dumpable控制；需要新身份与重新验收，不能直接patch固定供给。或者继续阻断，均不自动降低core判据。本轮只确定当前简单候选不足，不替所有者选方案。

## 本次来源身份

| 路径 | SHA-256 |
| --- | --- |
| `/usr/share/apport/apport` | `e8b57da9924d461fee6d3b392dc184697bc14d2eb8d717c05e1cbf0bd376041e` |
| `/usr/lib/python3/dist-packages/apport/report.py` | `47bf22887ca462381db48bd0609d6e78db29fa5c193953857d7b5c1db0387615` |

静态分析未新增crash测试或现场通过结论；无崩溃exec实测另见[core可行性](issue-167-core-feasibility.md)。
