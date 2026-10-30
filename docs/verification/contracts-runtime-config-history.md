# 运行配置 Contract 迁入的历史验收边界

本页保留从 `docs/contracts/runtime-config.md` 迁出的既有验收叙述，不是本轮验收台账。
迁入原文的历史记录取自基线 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa`；
其中 #25、A2/A3、revision 和“已实现”等表述属于原记录的时点及证明范围，
不证明当前代码、当前数据库 head、live、正式校准或阶段 B 就绪。
现状见[运行配置快照契约](../contracts/runtime-config.md)；原证据仍以所链离线证据为准。

## 完整 A2 验收边界

以下为迁入原文：

#25 的完整 A2 结论固定聚合以上配置、迁移、投影与 CLI 行为测试，保留 A1 与
A2-01 的历史测试字节及四份 v1 契约。测试只用合成材料与真实临时 SQLite；
版本标签隔离、停用主题、模型/adapter 槽隔离、精确契约字节、只读方式、ISSN
冲突、受控算法、并发与中断恢复均有固定测试范围。验收另建临时库执行 base→head，
从库内 `alembic_version` 读取实际 revision，不将脚本声明的 head 当作已运行迁移。
A3 的存储迁移 head 为 `a302_artifact_store`，快照格式仍为 1，各阶段投影、校准基线及 adapter
语义格式分别登记；未登记的迁移 head 或格式变化不能通过。

配置就绪、固定 fixture 与完整 A2 结论都不能证明正式校准或阶段 B 就绪。
该结论不验收 SQLite 之外的 artifact 发布、全量业务事实、阶段输入指纹、任务/
共享资格与可见性接口、doctor、备份恢复、真实来源及 Pi/Docling/模型执行。
证据、失败状态和父规格覆盖表见[离线验证证据](offline-evidence.md#完整-a2-独立结论)。
