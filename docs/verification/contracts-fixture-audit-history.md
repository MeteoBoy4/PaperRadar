# Fixture 与摘要审计 Contract 历史证明摘录

以下原文迁自基线 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 的
`docs/contracts/fixture-audit.md`。它们保留原章节所述范围与限制，不是本轮验收台账。
原文没有给出对应运行的 run_id 或单独执行日期；章节票号与 2026-10-25 预检日期
不能替代执行时点、同次离线结论或真实来源审计证据。现状规则见
[Fixture 与摘要审计契约](../contracts/fixture-audit.md)。

## 迁移验证范围

原「PDF 字节事实与 backend 期望（#102）」末句：

> a1001 revision 的升级测试从 a704 重新升级。

这只记录该迁移测试的起点，不声明 a1001 是当前数据库 head，也不授权改写已使用的迁移。

## 真实进程测试方法

原「显式恢复、历史回放与追加解释（#106）」摘句：

> 两个必要真实进程用管道
> 握手确认锁内或 HTTP transport 已进入（因此 started 已提交），再释放/kill，不用长 sleep。

这里的“真实进程”指离线测试进程，不表示真实来源 HTTP、浏览器或模型运行通过。
实现指针：[进程测试](../../tests/test_audit_processes.py)。

## 完整恢复证明范围

原「完成审计引用与完整恢复（#107）」末段：

> 隔离恢复证明使用真实 a704 五类非空历史、活跃 WAL 同库混合历史、原目录禁止访问/禁网、移根与独立进程验证；覆盖映射见 tests/a10-recovery-coverage.md。它不代表四刊 live、长期来源稳定、正文/Docling、渲染运行时或完整阶段 A 通过。此处证明仅覆盖所列恢复子集，完整门禁以独立 A10 同次证据为准。

定位：[恢复覆盖映射](../../tests/a10-recovery-coverage.md)、
[完整恢复测试](../../tests/test_a10_complete_recovery.py)、
[A10 规格覆盖与证明边界](a10-requirements.md)。这些测试或映射的存在不证明本轮已执行。

## 真实来源状态的原文时点

原「#103 已交付的取得边界」末句：

> 当前未运行真实来源审计。

“当前”仅指上述基线保留的原文时点，不维护后续 live 状态。后续首轮实测与来源资格分别见
[路线图 Audit](../roadmap.md#module-audit)与[Source](../roadmap.md#module-source)。
