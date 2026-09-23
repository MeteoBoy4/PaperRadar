# ica-advise：#1 快照判决 seam 放在两个具名入口（选 b）

日期：2026-09-22
状态：已决。
来源：架构审视报告（/tmp/architecture-review-20260922-114145.html）候选 #1 + #2；grilling Q1。

## 决策是什么

`inspect_frozen_snapshot` 现返回九态 `SnapshotInspection`，由 `export.py`（dict 查表）和 `check.py`（if 链）各自翻译为公开错误类别与中文指引，且 `_PATH_FAILURE_CATEGORIES` 在两文件逐字重复。Q1 在四个收法中抉择：

- (a) `inspect_frozen_snapshot(dir, contract, intent)`，intent 为 EXPORT | CHECK；
- (b) 两个具名入口 `verdict_for_export(...)` / `verdict_for_check(...)`，各返回已翻译判决；
- (c) 保留九态返回，另加 `describe(inspection, intent)` 纯函数；
- (d) 整个文件系统操作收进 snapshot 模块，interface 变为 `publish` / `verify`，吸收 export.py / check.py。

**选定 (b)。** 九态与翻译表退回 snapshot 模块 implementation，模块内部仍是一张按状态索引的表，两个公共入口各自切片。

## 为什么

- 调查确认 `SnapshotInspection` / `inspect_frozen_snapshot` 仅在 `snapshot.py`、`export.py`、`check.py` 三个源文件出现；`tests/`、`docs/contracts/frozen-contracts.md`、`intent/draft.md` 均无引用。九态是纯内部管道，收进模块不触碰任何外部承诺。
- (a) 的 intent 参数是模式开关，与同一审视 #4 拆除 `validate_output` 的 kind 判别器方向矛盾，还会新增一个公共枚举且无法在结构上阻止 check 侧传 EXPORT。(b) 用函数名绑定意图，配对是结构性的。
- (c) 不消除九态外流，深度不变，是半途方案。
- (d) 把只读检查与耐久写入发布合并进一个模块，吞掉批量编排；与已选的 #2（改 export.py 批量返回形状）范围冲突，且迫使公共 API 搬家与文档联动，违反"能局部改就不扩大范围"。
- 附带约束：外部行为逐字节不变（类别、中文消息原文含 check 消息中嵌入的身份与路径、退出码）；`content_conflict`（export）与 `content_drift`（check）是两份各自已发布的公共词汇，不得借机合并；`_PATH_FAILURE_CATEGORIES` 重复属于 #1 问题陈述的一部分，随同一 seam 收敛，若牵连过大可拆为紧随的独立小步；`SnapshotInspection` 转为模块私有。

## 是否改变外部行为

否。CLI 输出、公开错误类别、中文指引文本、退出码、Python 公共入口（`export_frozen_contracts` 等）全部保持原样；现有测试不因文本变化而需要修改。`SnapshotInspection` 本就不在 `contracts/__init__.__all__`，无公共面变化。

## 是否需要 ADR

否。这是模块内部 seam 的位置选择，不偏离 `intent/draft.md`（:877 只要求 `contracts/` 是权威 Schema 的导出快照，不涉及内部判定结构），不改变领域不变量或公共契约；`docs/contracts/frozen-contracts.md` 未提及九态，无需同步。
