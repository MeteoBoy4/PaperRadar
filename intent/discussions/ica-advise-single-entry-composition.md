# ica-advise：#2 单份 export 直接组合私有 helper（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #2；grilling Q10。前序：ica-advise-export-batch-partial-failure.md（Q2，其"单份从批量 item 派生"措辞由本决定修订）、ica-advise-outcome-literal-narrowing.md（Q6）。

## 决策是什么

Q6 的 Literal 收窄与 Q2 的"单份从批量 item 派生"相撞：单元素批量的 item 结构上不可能出现 NOT_ATTEMPTED（预检失败与发布失败时该项均为 failed），但 mypy 要求四态分支有去向。Q10 在三种处理中抉择：

- (a) 单份入口不经过批量，直接组合批量循环所用的同一对私有 helper（verdict_for_export + 发布步骤）；
- (b) 仍从 item 派生，NOT_ATTEMPTED 分支抛非受控内部不变量错误（不可达、不可测）；
- (c) NOT_ATTEMPTED 映射到既有 category（捏造失败原因）。

**选定 (a)。**

## 为什么

- 已验证行为逐字不变：`select_contracts` 单名路径的错误文案本就流经 `build_selected_contract`（schema.py:159），"未知契约 / 无效版本 / 组合未实现"三类文案两处相同；批量新增的空选择、重复选择对单份结构上不可能。blocked 与发布失败的 category + guidance 来自同一判决表；成功结果字段相同。
- 是唯一同时满足 Q6 两条约束（Literal 收窄 + 禁 cast/assert）且零死代码的选项：成功类型天然 `Literal[CREATED, UNCHANGED]`（发布步骤只产 CREATED，MATCHED 分支只产 UNCHANGED），失败天然抛 `ContractExportError`。
- (b) 引入不可达、不可测的防御分支——审视报告刚把 check.py 的同款模式（"一致状态不是失败"）列为症状，Q1/Q9 正在消除它。(c) 为不可能状态捏造受控 category，违背不伪造原则。
- "单份 ≡ 单元素批量"从不可达分支转为可测试性质：等价性测试比对两侧的选择文案、类别、指引与结果字段。
- 结构收益：单份与批量成为平级入口，共享同一对私有 helper；check 侧对称同构（`check_frozen_contract` 同样组合 `verdict_for_check`），现状"批量循环调用单份"的倒挂方向在重构中自然消失。

## 是否改变外部行为

否。已验证选择文案逐字一致；blocked / 发布失败类别与指引、成功结果、CLI 输出全部不变。Q2 记录中"从批量结果的对应 item 派生"措辞修订为"从批量所用的同一对私有 helper 派生"，目的（单一逻辑源）不变。

## 是否需要 ADR

否。内部组装方式调整，外部承诺不变。
