# #184 v24 只读前提汇总与无秘密预检诊断

新增独立 D1 覆盖，不改写历史固定向量、pin、测试或分母；本页只描述工程覆盖，
不宣称新的 root 安装、内核策略、manager、scope、mount、认证或模型 live 资格。

`LinuxLiveHost.prerequisite_report` 先核候选保护树和完整 placement seal；不可信时
其余项明确 `blocked`。可信后分别观察宿主工具、安全基线、三项 manager 状态、
产品进程、anchor、sudoers 和 nft check。选定失败准备的原 MAIN resources 与零
业务操作基线独立汇总；策略归属仍重新认证。独立失败不会隐藏其余可执行项，外部
异常正文及 subprocess 输出不进入报告。

只有现存候选策略完整 exact、身份和依赖全部满足时才执行完整 scope/trace/true
预检。已认证的失败准备仍待新候选事务应用，显示 `native_scope_trace` 的
`pending / placement_transaction_required`，不把未执行当通过。未知、混合或不明
策略为失败；已完成准备后的策略缺失也不能归入这个 pending。此次安装前的完整
聚合接线针对失败准备作废事务；正常初装还未建立 anchor 的依赖继续由原安装步骤
建立，最终复验后才可完成。

新构建封印 `placement_preflight_version=2`。缺字段只保留历史 reader 语义；存在时
必须是整数 2，拒绝 bool、float、字符串、null 及未知版本。新协议的事务预检与
安装后复验均保留真实 `/run/systemd/system` 的原目录 fd，在私有 `/run` 中只读
bind，逐层拒绝符号链接、错误属主和可写目录；不以新建空目录冒充真实 boot marker。
所有 root 设置 fd 在降权前关闭。host 与新协议私有 manager 的三项查询均完整执行。

native 只在两个有效无秘密 preflight 模式中输出封闭 marker。监督器只接受单条完整
白名单 marker 和原退出码 125；未知、额外、过长、混合或截断输出均拒绝。诊断涵盖
首次 ready 之前，以及真实 ptrace 释放后、true exec 前的拒绝；初装冷预检也使用固定
无参数语言的有限监督。root 子进程通过固定退出码区间传递 50 个检查点及 manager
失败位集，父进程输出具体分项，无继承 root 可写诊断 fd。该诊断不执行额外探针。

独立测试模块：

| 模块 | 用例数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_prerequisite_report_v24.py` | 12 | 多失败汇总、tree/seal 屏障、依赖阻断、资源/额度、unknown kernel、prepared 缺失、pending 和真实 native 条件 |
| `tests/test_preflight_boot_marker_v24.py` | 11 | 真实原目录内容只读保留、身份拒绝、设置 fd 关闭、root 检查点、私有 manager 三项不短路 |
| `tests/test_preflight_protocol_v24.py` | 9 | 新候选 prepare/final verify 协议选择、历史缺失、未知和非整数版本拒绝 |
| `tests/test_native_preflight_diagnostics_v24.py` | 67 | 50 个有限 marker、畸形输出拒绝、ready 后真实 ptrace 失败、固定冷预检 |

这些用例使用明确的 OS adapter、子进程及有限的本地 ptrace；不实际改变宿主 mount、
AppArmor、systemd units、nft 或任何受保护账本。真实 manager 工具与新策略的整条
系统调用链仍须所有者对新封印包执行安装与实际复验。
