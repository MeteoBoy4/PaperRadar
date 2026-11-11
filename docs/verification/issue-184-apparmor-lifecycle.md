# #184 AppArmor 封印生命周期独立 D1 覆盖

本模块新增能力沿用 D1，不加入历史固定测试分母、旧 required 集合或旧组回执。测试通过只说明受保护安装业务路径及明确 OS 替身边界；不证明实际 root、AppArmor attach、namespace/mount、scope/ptrace、网络、认证、模型、receive 或证据激活。

`tests/test_live_apparmor_lifecycle.py` 当前 44 个独立节点，覆盖：

- 实际离线 native/profile 编译产物与生命周期 seal reader 的接口组合；不加载 profile，不执行 namespace。
- source/binary/build/ABI/native 两入口的关联，缺部分成员与新 inventory 整体缺失拒绝；旧 inventory 没有 placement 仍按旧协议读取。
- 已知策略 load + exact 回读、同字节幂等、精确卸载及其他项目 profile 保留；未知策略在准备 journal/旧状态首次写入前拒绝。
- preflight 失败保留 preparing，known partial 默认拒绝、仅 explicit recover 处理、unknown 一律保留。
- 实际 self/initial user/mnt namespace、两个既有 sysctl、parser/true/systemd-run/systemctl/loginctl 与 resolver 规范目标；变化或接口缺失受控拒绝。
- observer 稳定缺失/异字节与权限/revision 不稳定的 E7 区别，持久重读及原快照时点保护；root 先核保护链/O_NOFOLLOW 再读取placement成员，拒绝symlink目标预读和非法工具描述。
- 新策略准备/旧资源退役/新资源/target/安装计划等八宿主阶段中断后同字节续行，保留旧 epoch、四份 received、取消轮与 40/40 余额；卸载和 explicit recover 不重置来源或资格。
- 无执行史 resources replacement 的 stop anchor/verify stopped/traced 失败恢复，继续原 legacy 来源链门禁。
- target retirement 未认证 archive 拒绝、rename 前/后中断、完整幂等和同 SHA 多轮不同实际 target；精确历史归档不覆写。

`tests/test_live_bundle_seal_cli.py` 另有 **10 个**独立节点：真实原 epoch/pair 只读派生及错配拒绝，成对参数与原来源必需条件，冷进程中文 help、禁网络/SQLite 及自由部署时点参数拒绝。两个新模块合计 **54 个**D1 节点，不加入历史分母。

真实 fork/O_RDWR fd 回归验证 root 继承句柄在永久 UID/GID 变更调用前关闭、父进程句柄仍在；mount/root/UID 是显式 OS 替身，不是实际 root 降权证明。

`tests/live_apparmor_support.py` 仅替换 kernel policy I/O；真实 AppArmorKernel、PlacementPolicyLifecycle、LiveDeployment、账本/epoch/观察收紧路径均参与。Linux target retirement 测试用 fd/stat 和 command/cgroup OS 替身，不替换 own gate。

安装组合使用 `test_live_epoch_upgrade` 的受保护合成根 fixture；其当前历史 source-root 构造只为旧布局/协议业务测试，不作为新可执行发行包的成功证据。最终 source guard 和完整真实构建仍由 integration 收口验证。原 v1–v16 vectors/pins、Frozen receipt Contract、旧 epoch wire 和历史证据不在本变更重绑。

开发验证均按 `uv run --offline --locked`：最终 native/lifecycle/CLI/kernel/observer/placement/Schema 十二模块组合 **258 passed，87.50s**；本切片11个源/fixture模块 Ruff check/format 与 mypy 通过。较早 epoch/observer/kernel/Schema 六模块组合183 passed，174.72s；后续针对 full traced 失败、resources replacement、target 退役和 FD 的增量均已重新收入上述最终组合。来源读取加固后 lifecycle/observer/nft 相关组合 **83 passed，64.96s**，覆盖新增受控工具描述和保护链；最后工具字段类型收口后实际编译/非法描述/symlink三节点增量再通过。`./scripts/check-compatibility cli`：59 passed，66.93s，exit0。没有运行完整离线门禁；它仅由父任务在最终审阅树单独执行。
