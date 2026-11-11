# #184 安装审阅恢复窗口：独立 D1 覆盖

本台账独立承接两轴审阅确认的安装幂等与预检顺序问题，不修改此前冻结覆盖结论或扩大旧组分母。

`tests/test_live_install_review_recovery.py`：**26 个**独立节点。

| 边界 | 数量 | 断言 |
| --- | ---: | --- |
| 同一已 prepared 策略预检失败及重试 | 1 | 重新执行 probe，原 journal 字节/inode 不变，无额外 kernel 写入，仍核 exact policy |
| prepared 不能掩盖 kernel 异字节或 partial | 2 | 显式 recover 也在 probe/写入前拒绝，保留原 journal 与 kernel 写入历史 |
| prepared 不能忽略未知策略 .new | 1 | 显式 recover 也在 probe 前拒绝，原 prepared 与未知 .new 字节不变 |
| installed 升级 native/traced 预检失败 | 2 | 旧主 journal、完整 runtime、资源、target、epoch 与账本事实不变，未禁观察/退役；恢复保留原 epoch 和取消轮 |
| installed 完整 probe 的首写顺序 | 1 | 旧 history 首次发布时 native/traced 已各运行一次，旧部署仍安装且主 journal 未变 |
| installed history 已发布、主 journal 尚未切换 | 1 | 真实文件发布后的 fsync 中断，显式 recover 只读复用同字节单链接 history，保留 received、database、40/40、取消轮、原 epoch |
| installed history/archive 冲突 | 9 | 异字节、非规范 JSON、目录、软链、硬链、history.new、独立 .new、archive 与非显式恢复均首写前拒绝 |
| resources replacement 的准备与 history 复用 | 2 | 有/无 history 均在首个旧资源删除前恰好准备一次；已有 history inode 不变，无遗留 .new |
| resources 未知 history/.new | 7 | 异字节、非规范 JSON、目录、软链、硬链及两种 .new 布局均在准备/退役前拒绝并保留现场 |

受测公共边界为 `LiveDeployment.install` 与 `PlacementPolicyLifecycle.prepare/verify`。
继续使用既有 ModelHost/PolicyOS 与文件系统 seam；ModelHost 的 installed 状态明确模拟 live host 使用旧 target 的完整 traced probe。
两代 epoch fixture 均通过真实完整 freezer、83 成员 source guard、静态 native 编译与 compile-only parser；没有替换生产 guard、epoch 或生命周期内核。
同身份策略重验只读复用 prepared 记录，新/absent/partial/未知身份继续原严格恢复规则；不提供未来 profile 替换或未知 marker 清理。

原 resources `history_published` 失败节点保持原断言并由生产修复转绿；原 epoch42、AppArmor44、CLI10、bundle lifecycle18 和最终 fixture12 均完整保留。
仅三个当前源码负例路径切到 guard18，历史 guard1–17 JSON 与已有 pins 保持原字节；launch10/placement2 语义保持。

开发期定向验证只证明离线状态机与有限 OS 替身边界。完整门禁和最终兼容组合由 integration 收口承担；实际 root、profile attach/load/remove、userns/mount/cap/seccomp、scope/ptrace、network、auth/model、receive/激活与 reboot 均未执行。

开发验证：最终 guard18 源码的 20 模块组合 **412 passed，627.61 秒**，包括本模块26、fixture12、epoch42、AppArmor44、CLI10、原 resources28、bundle lifecycle18、source guard18 和 Schema/receipt27，未 skip/deselect。末次把 resources 顺序断言从 sudoers 提前至真正首个 collect wrapper 删除，两个节点增量 **2 passed，3.98 秒**。受影响8个 Python 模块 Ruff check/format 通过，显式包含受测入口的 mypy 共10个源码/测试模块通过；旧 guard1–17 JSON 与所有已有 pins 对基线逐字保持，`git diff --check` 通过。
