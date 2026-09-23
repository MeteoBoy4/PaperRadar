# ica-advise：#2 outcome 枚举单份收窄用 Literal（选 c）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #2；grilling Q6。前序：ica-advise-export-batch-partial-failure.md（Q2）、ica-advise-not-attempted-single-state.md（Q3）。

## 决策是什么

批量 items 的 outcome 为四值（created / unchanged / failed / not_attempted），而单份入口 `ContractExportResult.outcome` 只可能是前两值（失败时抛 `ContractExportError`）。Q6 在三种扩法中抉择：

- (a) `ExportOutcome` 扩四成员，单份结果靠约定不出现后两值；
- (b) 两个 enum：两态 `ExportOutcome` + 四态 `ExportItemOutcome`；
- (c) 一个四态 `ExportOutcome`，单份字段类型 `Literal[ExportOutcome.CREATED, ExportOutcome.UNCHANGED]`。

**选定 (c)。**

## 为什么

- 项目 mypy `strict = true` 覆盖 src/tests/scripts，且 `screening/validation.py:299-315` 已有 `Literal[OutputKind.BOUNDARY, "boundary"]` 的 Literal-of-enum 惯用法——不是新风格，是既有模式。
- (a) 类型上允许单份结果携带 FAILED / NOT_ATTEMPTED，而这两个状态在单份入口不可构造（失败即抛异常）：类型撒谎，调用方被迫为不可能状态写防御分支或 assert，穷尽检查失效，恰是本次重构要消灭的隐式约定。
- (b) created/unchanged 定义两次，制造"同一事实两个来源"（本次审视 #3 批评的病灶），新增公共枚举名并要求单份入口维护两套词汇间的映射。
- (c) 词汇一份、限制由类型检查器强制、零新增公共名；单份入口从批量 item 派生时用 `is` 分支收窄（本就要在失败项抛异常），构造自然。
- check 侧先例说明形状差异是领域差异：单份 `ContractCheckResult` 无 outcome 字段（成功仅一种），export 单份保留两值 outcome（created/unchanged 对用户是两句话）。不据此"顺手统一"。

附带约束：批量 item 的 outcome 字段为完整四态 `ExportOutcome`；单份派生禁止 cast/assert 强转；随 Q2 更新的文档为一张四值 outcome 表并注明单份入口类型上只返回 created / unchanged；check 侧不动。

## 是否改变外部行为

否。enum 值与 CLI 输出不变；`ExportOutcome` 从两成员扩为四成员属 Q2 已定的批量结果重设计的一部分（消费者仅 cli.py 与测试，随 #2/#8 一并更新），文档按 Q2 约束同步。

## 是否需要 ADR

否。类型层形状选择，不触碰领域不变量、持久化或文档契约的语义。
