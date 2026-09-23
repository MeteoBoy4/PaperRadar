# ica-advise：#1 判决入口收 target（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #1；grilling Q4。前序：ica-advise-snapshot-verdict-seam.md（Q1，本决定是其"路径翻译随同收敛"约束的落实方式）。

## 决策是什么

Q1 定下的 `verdict_for_export` / `verdict_for_check` 入参收什么：收 target 根目录并在模块内完成路径解析、路径失败翻译与 check 目标预检（a）；或收已解析的 snapshot_dir、路径解析留在调用方（b）。

**选定 (a)。** 判决入口吃 `(target, contract)`，内部完成 resolve → 路径失败翻译 → 九态检查，判决带回 `snapshot_dir`；`SnapshotPathError`、`SnapshotPathProblem`、`resolve_snapshot_directory` 转为模块私有；逐字重复的 `_PATH_FAILURE_CATEGORIES`（export.py:136-139 / check.py:97-100）在模块内合并为一份；check 的"目标不是目录"预检（check.py:180-186）移入 `verdict_for_check`。

## 为什么

- grep 证实 `resolve_snapshot_directory` / `SnapshotPathError` / `SnapshotPathProblem` 的消费者只有 export.py 与 check.py；`inspect_frozen_snapshot` 无其他调用方，且两个调用方都从 target 起步、三段序列（resolve → catch/translate → inspect）完全同构。没有任何调用方拿着现成 snapshot_dir 前来，收窄到实际用法支持收 target。
- (b) 会把同一判决的三段人为拆开：调用方继续暴露在 SnapshotPathError 与重复翻译表面前，Q1 承诺的"随同一 seam 收敛"要另开一步，无收益。
- 三个转私有的符号本就不在 `contracts/__init__.__all__`，零外部引用，转私有不改变公共面。check 的目标预检只是 check 专用文案的 UX 细化，随 intent 分属表内一行即可。
- 与审视报告 #7 不冲突：#7 若日后要为测试/scripts 公开布局投影，届时另行设计公共入口；本决定只把内部核心收干净。

附带约束：非失败关系（matched / absent）的判决也携带 snapshot_dir，export 预检后直接写入；路径失败文案逐字保留（export 用 SnapshotPathError 原文，check 保持"契约 {identity} 检查失败："前缀与"目标路径不是可访问目录"专用文案）；export 写入阶段的 OSError 翻译（`_write_error`，含 ELOOP → invalid_target）不动，属发布语义。

## 是否改变外部行为

否。错误类别、中文文案、CLI 输出、退出码全部逐字不变；三个转私有符号无任何外部引用；文档不涉及这些内部符号，无需更新。

## 是否需要 ADR

否。模块内部 seam 形状选择，不偏离 `intent/draft.md` 与既有文档承诺，不触碰领域不变量。
