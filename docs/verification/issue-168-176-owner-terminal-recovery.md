# #176 owner终端停止：无root模型与同SHA恢复边界

本次只记录诊断和恢复入口，不修改已部署v4的39个guarded源码、清单、runtime、sudoers或证据。
没有新增产品能力或pytest模块，不扩旧32模块495节点、历史分母或required。所有实际信号／sudo／激活仍仅由所有者执行。

## 已确认事实与未确认范围

主代理只读确认：第一次输入附近，父shell仍S且为前台组，owner和owner activate两个Python同组T，
无tracer或信号忽略，new receipt仍未激活／未撤销、无phase目录，确认后的collector不在运行。
用户明确未曾CtrlZ或主动暂停；反馈久等后才按CtrlC。后续两个Python存在待处理SIGINT。
这证明不是单纯长I/O，但没有直接捕获现场最初的停止信号或当时stdio／前台转交分支。

现场系统sudo为sudo-rs0.2.13系列。其官方
[监控器源码](https://github.com/trifectatechfoundation/sudo-rs/blob/v0.2.13/src/exec/use_pty/monitor.rs)
在恢复前台时只继续直接命令PID；[PR1530](https://github.com/trifectatechfoundation/sudo-rs/pull/1530)
将其改为命令组。[问题1527](https://github.com/trifectatechfoundation/sudo-rs/issues/1527)
记录了后代未被恢复的行为。该一手机制支持下面的模型解释；不把相似issue等同于现场抓到的信号。

## Tight loop与单变量对照

材料保留在主工作树被忽略的 `.scratch/168/tty-diagnosis/`，包含README、三个普通用户harness与有限results.json。
从仓库根目录以 `uv run --offline --locked python` 调用，所有信号仅发给该harness新建子进程；
没有sudo、真实PID、真实站点／账本／认证／模型／网络访问。fixture-only仅是临时替身输入，不是实际回执确认。

| 命令参数 | 预期／实测 | 信号与终态 |
| --- | --- | --- |
| `loop.py --control none` | exit0 | script(1)嵌套PTY，生产run_entry＋确认后refresh入口（collector外部程序为替身），第一提示／refresh／第二提示／完成均通过 |
| `sudo_monitor_loop.py --resume pid` | **exit1 red** | 内核实际产生SIGTTIN=21；monitor转交前台后只CONT直接shell，shell变S且前台组相同，owner／CLI两个Python均T；第二提示未到 |
| `sudo_monitor_loop.py --resume group` | exit0 green | 相同kernel stop，唯一改变为CONT整个组，确认／refresh／第二提示／完成均通过 |
| `sudo_monitor_loop.py --resume pid --foreground` | exit0 green | 唯一改变为初始命令前台，无stop事件，链完成 |
| `interrupt_loop.py` | exit0 | 新建fixture child的STOP→INT排队→CONT后返回-2／KeyboardInterrupt，后续marker未执行 |

monitor模型使用真实PTY、setsid/setpgid/tcsetpgrp和waitpid，实际内核发SIGTTIN，不注入STOP／TSTP来假造该red。
模型的初始background是受控输入，不是完整sudo实现，也不是对现场二进制的执行测试。
因此结论是：sudo-rs的已知单PID恢复机制**能够无需CtrlZ地产生精确现场形状**；现场最初为何进入该分支仍是推断。
纯应用STDIO／refresh基线通过，不能据此将根因写成collector长I/O或任意用户暂停。

## 当前会话的最小恢复

由于已有待处理SIGINT，继续信号的目标先是处理本人中断并退出，不是保证继续原激活。
主代理已取得所有者对精确旧组的处置，并只读复核旧链退出、完整runtime摘要与保护、原receipt无活／撤销、无phase。
进一步须核plan有效／未停止、deny log有效且无相应意图、锁无持有者。
满足[owner恢复前提](../../intent/review/issue-168/closure-owner-plan.md#已部署同sha流程的终端中断后恢复)后，
所有者可用已核经典sudo显式执行原root冻结owner-closure.py及原config，不重跑升级、不重cutover或接收新证据。
仍三次本人ID、真实刷新观察、原验证时间／预算不续；任何部分状态变化均拒绝，不清理或自动修补。
实际三轮和最终root安全回执尚须所有者完成，不能由这些模型代签。

## 为什么不新增生产工具或镜像测试

实际缺陷位于外部sudo实现的PTY监控路径；本仓库没有该提权实现的可离线执行真实seam。
本次恢复可直接消费原已审同SHA入口，因此不为一次恢复引入新root代码／恢复生成器，也不复制上游常量制造pytest假绿。
按diagnosing-bugs保留可复现red/group-green及限制；独立旧观察不能改写，部署源码与v1/v2/v3/v4原字节均保留。
新文档链接／现有D7共**10passed／0.71s**，git diff --check通过。
完整门禁和旧scope授权仍由主代理处理，本次不关闭#176/#168。
