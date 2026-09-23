# ica-advise：#1 错误词汇迁入 contracts/errors.py（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #1；grilling Q5。前序：ica-advise-snapshot-verdict-seam.md（Q1）、ica-advise-verdict-takes-target.md（Q4）——本决定是判决入口落地的前置解结步骤。

## 决策是什么

判决入口住进 snapshot.py 后需返回 `ContractExportErrorCategory` / `ContractCheckErrorCategory`，二者现定义于 export.py / check.py，而这两个文件 import snapshot.py，形成 snapshot → export → snapshot 循环。Q5 在三种搬法中抉择：

- (a) 新建 `contracts/errors.py`，收两个 category enum 与 `ContractExportError` / `ContractCheckError`；
- (b) 只搬两个 enum，异常类留在原文件；
- (c) 搬进 snapshot.py。

**选定 (a)。** errors.py 为叶模块（不 import contracts 内其他模块），export / check / snapshot 均从它 import；分层变为 schema/errors → snapshot → export/check 单向无环。

## 为什么

- 仓库已有同款先例：`screening/errors.py` 是"受控错误类别 enum + 异常类"同居的叶模块（`OutputErrorCategory` + `OutputValidationError`），由 validation.py 与 package __init__ 消费。照抄既定模式比发明"只搬一半"的变体更可预期。
- (b) 节省的只是两处三行搬移，代价是异常类与其类别词汇分居两文件、errors.py 只含半套失败词汇；Q2 已删除 `ContractBatchExportError` / `ContractBatchExportFailure`，剩余两个异常类极小，搬移成本近零。
- (c) 使 snapshot 拥有它不会产生的 `write_failed`、`invalid_selection` 等成员，违反"词汇与产生它的模块同住"的 locality 原则。

附带约束：`contracts/__init__.py` 的 re-export 与 `__all__` 不变（Q2 删除两个批量异常类型除外），cli.py 与测试 import 路径零变化；enum 成员值与成员集不变（文档 7+8 类别表原样有效）；只搬失败词汇，`ExportOutcome` 与各结果 dataclass 留在 export.py / check.py，`SnapshotInspection` 等判决内部类型留在 snapshot.py 私有；`ContractSelectionError` 属选择语义，留在 schema.py 不动。

## 是否改变外部行为

否。公共 import 面（`paper_radar.contracts` 门面）、enum 值、文档受控类别表、CLI 行为全部不变；纯模块内部归属调整。

## 是否需要 ADR

否。依赖分层解环属工程组织，`intent/draft.md` 与文档契约不涉及定义模块路径。
