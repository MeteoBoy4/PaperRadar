# #184 失败准备退役的历史正常刷新重放 D1 覆盖

本次新增模块不加入历史固定测试分母、旧 required 集合或旧组回执。公开接缝为
`FailedPreparationRetirement.check/prepare`；复用
`tests/preparation_retirement_support.py` 的合成完整封印、旧 MAIN、epoch、受保护账本
与 AppArmor kernel OS 模型，原正常刷新报告由实际 `publish_normal_review` 写出。
不读取现场配置或凭据，不执行实际 profile、namespace/mount、scope/ptrace、认证、
模型、网络、receive 或激活。

| 独立未绑定模块 | 节点数 | 公开行为 |
| --- | ---: | --- |
| `tests/test_retirement_historical_refresh.py` | 30 | 原完整历史绑定报告通过只读 check 和有限退役；25 类缺失、摘要、静态漂移、字段/类型/规范字节与来源保护负例在 check/prepare 均受控拒绝；正常报告 stopped 与全域 stopped 独立保留；静态旧报告及显式恢复兼容 |

25 类负例包括缺 enrollment、错误 manifest/owner 确认摘要、缺失/额外 use ID、缺失/未知
binding 组件、非摘要值、错误完整绑定、全站一致静态漂移且报告摘要同时匹配、错误报告摘要、
enrollment 的 null/布尔或浮点版本/额外字段/非规范字节，以及 enrollment/report 的
可写模式、软链接、硬链接；报告另覆盖 null、非布尔 stopped 与非规范字节。
每个负例都比较两次公开拒绝前后的完整文件集合、内容、模式及链接数，并检查无 kernel
写入、无退役记录或快照。来源拒绝要求确切 `ValueError` 和有限原因
`failed_preparation_refresh_source`，不接受被上层遮成 `installation_unavailable`。

旧 normal-review stopped 测试保留其规范报告并由真实 publisher 重读；全域 stopped
测试经实际 approve/start/reserve/recover_interrupted 留下累计域停止与 auth 消耗。
两者各自成立时都拒绝，报告、enrollment、账本及业务材料保持原字节。
恢复测试在新无秘密预检失败后显式 recover，原失败快照不覆盖，原报告不重写。
既有无报告路径仍由 `tests/test_failed_preparation_retirement.py` 覆盖。

原症状的单节点回归在修复前实际失败：旧报告记录完整绑定 manifest，退役检查却以静态
manifest 调用原 reviewer，在 `normal_auth_refresh.py` 的摘要核对处抛出
`LedgerError(source_untrusted)`；修复后同一节点通过。修复只在退休接缝从唯一受保护
旧 enrollment 恢复原绑定，不改变通用 reviewer、普通旧 marker 读取、原 epoch UTC、
72 小时目标、共同窗口、40/40 累计域、负对照取消、历史回执或撤销规则。

源码策略采用新的 `pi-admission-v22`，旧 v1–21 向量及原 pin 保持原字节；v22 保留
原 84 个显式源码成员，仅更新本次实际改动源码摘要。开发期候选和子 worktree 检查
不构成所有者对最终封印的审阅、集成树完整离线门禁或现场资格。

本覆盖不证明实际旧部署已经可安装、真实 AppArmor/无秘密预检成功、正常认证刷新或
模型可用；仍需所有者审阅最终归档并单独执行授权现场步骤。规则见
[现状契约](../contracts/live-evidence.md#封印放置策略生命周期)，沿用
[原退役决定](../adr/0065-retire-authenticated-failed-placement-preparation.md)。
