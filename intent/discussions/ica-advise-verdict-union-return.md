# ica-advise：#1 判决失败侧走返回值 union（选 a）

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #1；grilling Q9。前序：ica-advise-snapshot-verdict-seam.md（Q1）、ica-advise-export-batch-partial-failure.md（Q2）、ica-advise-errors-module.md（Q5）。

## 决策是什么

判决入口的失败侧传输：返回成功/失败 union（ExportReady | ExportBlocked，check 同理），caller 用 match 处理（a）；或成功返回、失败抛 Q5 的两个公共异常（b，其中 verdict_for_check 成功时只返回 Path）。

**选定 (a)。** 逐份失败作为数据在返回类型中流动，异常只保留在文档化的抛出边界。

## 为什么

- Q2 已确立原则：逐份结局是业务事实（items），异常只属于请求层错误（选择无效）。判决函数是逐项事实的产生者，事实应走数据通道。(b) 使批量主路径（CLI 实际路径、#8 测试面）对每次预检失败"抛出→一墙之隔接住"，把 Q2 刚从批量接口拆除的异常传事实模式在下一层复活（现结构即 export.py:291/322、check.py:233 的逐份 catch）。
- 项目 mypy strict 全仓生效：union + match 使"漏处理受阻"成为类型错误；失败在签名中可见，无隐式控制流，利于 Agent 导航。
- 分层更干净：snapshot.py 只引用 errors.py 的类别 enum；公共异常类仍只在 export/check 的文档化边界抛出（单份入口、选择无效、发布 OSError 转换）。(b) 会使"只读判定"模块抛公共命令异常。
- (b) 的收益集中在单份兼容入口（省约三行转换），而单份入口只有测试与兼容文档使用；主战场是批量路径。
- 与 Q1 已记录的"返回已翻译判决"及审视报告 after 图（SnapshotVerdict 为返回值）一致，无需翻案。

附带约束：union 类型为 contracts 包内部类型（snapshot.py），不进 `__init__.__all__`；`verdict_for_export -> ExportReady(relation: MATCHED | ABSENT, snapshot_dir) | ExportBlocked(category, guidance_zh)`，`verdict_for_check -> CheckReady(snapshot_dir) | CheckBlocked(category, guidance_zh)`（check 成功无 relation）；判决函数对逐份发现从不抛异常，异常路径与 Q2 一致（选择无效、发布阶段 OSError 经 _write_error）；单份入口把 Blocked 逐字转换为抛公共异常，消息逐字节不变；批量循环用 match 消费判决生成 items，CLI 输出逐字不变。

## 是否改变外部行为

否。批量 items、单份异常承诺、CLI 输出与退出码全部不变；新增类型为包内部，公共面零增长。

## 是否需要 ADR

否。内部传输形状选择，不触碰领域不变量与公共契约语义。
