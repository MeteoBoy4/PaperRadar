# Eligibility 与校准可见性

## 用途与范围

`paper_radar.calibration.visibility.evaluate_visibility(hidden_conditions)` 是共享的
校准可见性纯规则入口。输入为调用方本次已经装配的
`frozenset[HiddenCondition]`，返回不可变 `Visibility`，不读取数据库、时间、环境、
网络、模型或 Docling。它不依赖 eligibility；eligibility 消费本入口的动作许可，
不另行定义隐藏动作规则。本页目前描述 visibility 边界，eligibility 尚无已实现入口。

## 规则

**校准可见性**是基于某次已装配隐藏事实的展示与动作许可，不是制品删除、脱敏或状态迁移。
**隐藏条件**是仍成立的 `waiting_calibration` 或 `unrevealed` 事实。
`HiddenCondition.WAITING_CALIBRATION` 与 `HiddenCondition.UNREVEALED` 按 OR 合并；
空集合允许普通能力，全部条件解除才恢复。揭晓只移除对应未揭晓事实，不能覆盖仍成立的
waiting_calibration 或其他身份链成员上的隐藏事实。

调用方沿 Paper 身份、重复与合并链汇总全部仍成立的条件后传入；存活论文必须继承
被合并论文的隐藏条件。本模块不装配身份链、不实现合并、不从批次或制品内容推测事实。
`Visibility.hidden_conditions` 保留本次判定的受控原因集合；后续事实变化需要重新查询，
不会改写此前结果或历史 Screening/reuse 制品。

`Visibility.permission(VisibilityCapability)` 返回以下闭集许可：

| capability | 空隐藏集合 | 任一隐藏条件成立 |
| --- | --- | --- |
| `paper_facts` | `allowed` | `allowed` |
| `task_details` | `allowed` | `allowed` |
| `agent_content` | `allowed` | `denied` |
| `set_decision` | `allowed` | `denied` |
| `reading_request` | `allowed` | `denied` |
| `calibration_review` | `dedicated_path` | `dedicated_path` |

`paper_facts` 允许按既有规则读取论文事实，不覆盖其他访问或隐私约束。
`task_details` 允许展示任务存在性、stage、attempt、失败类别与失败队列归属。
依 [ADR-0037](../adr/0037-allow-task-details-during-blind-calibration.md)，用户明确接受
任务明细可能暗示边界或预测的推论；关联的 Agent 载荷仍属于 `agent_content`。
本规则不要求日志按校准许可省略 paper_id/stage 等任务字段。

`agent_content` 包括 Screening 建议、阶段二预测与分数、reuse 升级预测、理由和完整制品。
展示面、trace DTO、普通日报、运行摘要明细与错误分支按内容类别选择字段；允许论文事实
或任务明细不代表允许序列化完整对象。普通动作消费者在任何写入前检查许可，拒绝时
只返回受控许可与隐藏条件，不回显隐藏建议、预测或载荷。

`dedicated_path` 表示 calibration review 由专门路径处理，不由本规则判为普通动作；
它不授权 review 提交、不跳过冻结成员与批次约束，也不授权任何普通动作。
`allowed` 仅表示本规则允许，仍须满足各能力的其他前置条件。

枚举新增时同步本 Contract 与消费者 exhaustive 测试；公共入口对六种 capability 的
合成许可表全部断言，不使用默认放行。未知 capability 不走允许分支。

## 错误与拒绝

`denied` 是普通动作和 Agent 内容的受控拒绝结果，原因是 `hidden_conditions`，
不是 Screening 业务决定原因。输入是类型化的已装配事实，调用方负责解析和校验外部值；
此入口不接受原始数据库行、完整制品或自由文本错误作为事实。

## 不提供／不证明

本入口不提供保留器、校准表、正式 evaluation、展示 DTO、动作写入服务或日志字段过滤。
合成消费者仅证明许可契约，不证明真实产品面的字段裁剪、提交前守卫或身份链装配。

| 消费者 | 承接责任 |
| --- | --- |
| [B](../roadmap.md#module-b) | show/trace/最小日报首次调用，即使隐藏集合为空；普通动作写入前守卫与组合测试 |
| [C](../roadmap.md#module-c) | 保留器、waiting_calibration、实际隐藏；身份/合并链装配与存活论文继承 |
| [D](../roadmap.md#module-d) | 未揭晓/揭晓事实、专用 review 路径及新增展示面隔离 |
| [H](../roadmap.md#module-h) | 完整日报、复核与诊断分支的真实隐藏组合测试 |

## 相关

依据：[规格 §4.6](../../intent/draft.md#46-盲评校准)、§10/§11 A；
[#120 最终裁决 D1/D5](https://github.com/MeteoBoy4/PaperRadar/issues/120#issuecomment-6520223100)、
[#121](https://github.com/MeteoBoy4/PaperRadar/issues/121)。
独立工程覆盖与未验边界见 [A 窄收口台账](../verification/a-narrow-delivery.md)。
