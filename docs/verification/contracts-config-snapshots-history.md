# 配置快照发现与引用：既有验证说明

本页保留 `docs/contracts/config-snapshots.md` 在基线
`2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 中的既有验证说明，不新增验收结论，
不表示本轮运行或 live 验证。现状规则见[配置快照发现与引用契约](../contracts/config-snapshots.md)。

## 快照发现验证（#27）

以下为原文；原段未单列运行日期或独立回执，不能据此推定当前代码通过或完整 A2／阶段 A 通过：

> 验证使用真实迁移、临时 SQLite、固定碰撞索引 fixture 和真实安装 CLI，沿用外部
> I/O 哨兵；快照发现测试独立于 A1 固定测试和四份历史 v1 契约，不重复 #23 投影/基线算法测试。
> 没有新增 migration 或持久字段。

出处：[#27](https://github.com/MeteoBoy4/PaperRadar/issues/27)、[原审阅记录](../../intent/review/issue-27-config-snapshot-list-prefix-review.md)。

## Read 隔离恢复验证（#98）

以下为原文；双历史快照与候选原字节的回放不等于真实正文、源文本或生产 evidence-map 的恢复闭包：

> 隔离恢复验证覆盖含/不含 Read 契约的双历史快照与候选原字节在阻断原根的新进程恢复，
> 完整范围和上下文固定常量的限制见 [Read 恢复说明](../contracts/read-validation.md#恢复范围98)。
> `RuntimeConfigSnapshot` 默认 repr/str 隐藏 `payload_json`，显式访问与载荷身份不变。

出处：[#98](https://github.com/MeteoBoy4/PaperRadar/issues/98)、[A9 scope 历史审阅台账](a9-scope-review.md)。
