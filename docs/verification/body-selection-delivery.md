# 显式正文选择独立工程覆盖

依据：[所有者补充裁决](https://github.com/MeteoBoy4/PaperRadar/issues/185#issuecomment-6879014360)、
[ADR-0071](../adr/0071-record-explicit-body-selection.md)。本台账是独立 D1 覆盖，
不加入 A1–A10 required，不扩大旧固定分母或回写旧证据。

## 接缝与计数

主接缝为实际实验 CLI；辅助接缝为公开选择服务的事务故障与竞争；恢复接缝为
backup → 子进程标准 restore → 移动根 → 旧报告与暴露清单回放。
HTTP transport、Pi 合成 RPC、Docling SDK/parser、PDF 渲染及 clock 是外部替身边界；
mapper、normalize、证据回查、业务准入、CurrentBody 与 Read claim 均使用真实代码。

| 独立模块 | 参数化节点数 | 可观察行为 |
| --- | ---: | --- |
| `tests/test_body_selection_cli.py` | 3 | 冷帮助；多成功原歧义；选择后仍缺所有者质量；六项核查后实际 Read 任务与共享查询消费同三元组 |
| `tests/test_body_selection_facts.py` | 11 | 精确重放/冲突、后继历史、旧否决、UPDATE/DELETE/REPLACE；材料消费者；insert/commit 故障；角色/visibility/成员损坏；版本/选样/可见性竞态；失败提取、错 PDF、并发重放及序号独立于时钟 |
| `tests/test_body_selection_read.py` | 1 | 实际 claim 在锁后重核选择且不耗 attempt；在途旧 basis/预算不换绑，普通消费继续拒绝 |
| `tests/test_body_selection_migrations.py` | 4 | 非空 b007 升 b008；DDL/trigger/revision 故障完整回滚和重试；旧冻结 export 严格回放 |
| `tests/test_body_selection_recovery.py` | 1 | 新选择与旧 Read/report/exposure 经冷备份、原根屏蔽、标准恢复和移动后保留；报告视图重建在独立目录 |
| `tests/test_body_selection_integrity.py` | 2 | 重算摘要也不能伪造冻结修订/通过备份；新增成功不自动改选，同 Connection 查询与公开查询一致 |
| 合计 | 22 | 不计入历史组回执 |

首次红灯为 CLI 不存在 `body-select`，当时同 PDF 双成功仍为 `ambiguous_extractions`。
最终实现的 21 个节点同次执行通过；之后补充“新增成功不自动改选”的独立节点通过。
全部材料仅为独占 `/tmp` 下合成数据，未访问真实实验根或凭据。

## 迁移与消费者验证

- 唯一新增迁移 `b008_body_selection`，父 `b007_exposure`；旧迁移与 fixture 未改。
- `tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`
  精确节点通过；保留既有 Screening 外键环的 SQLAlchemy warning。
- Schema、人工 head 常量、十 scope head、A3 backup format revision、生产备份 revision、
  artifact-store/backup-restore Contract 与两个中央 hash 同步更新。
- 影响面消费者回归 37 节点通过：上述 Schema 节点、migration 单一预期守卫、Body facts、
  Read prerequisites、原多成功 layout/Read 拒绝及历史 exposure 组合。
- CLI 兼容组合 59 节点通过；strict mypy 显式包含全部新增/触及的 tests/support/worker、
  源码/迁移、人工常量与 head/中央登记脚本；442 source files 通过。
  本次全部 29 个新增/触及 Python 文件 Ruff 与 format 检查通过；差分检查通过。

选择历史由 Body 唯一 validate_all 验证，并经 B 聚合进入备份恢复。ReadBasis 的旧固定键集保持，
新登记和领取通过 CurrentBody 选择权威重核，历史 attempt 沿已保存三元组、PDF、样本及核查回放。
Body exposure 捕获表集合保持原样，样本/选样已提供暴露依据；不把新增选择表或今天的主键
注入旧 export scope，不放宽未知字段/表检查。旧报告继续使用原冻结输入。

## 审计与未验边界

只读 scope 审计的基线/目标为 `353cab708aefdb55a37a8b291a879056ece8f7c2` /
`integration/185-stage-b`；head 推进产生的敏感确认及基线既有 source 漂移交由 #206
在最终集成树逐项审阅。只精确重绑人工迁移预期与生产备份声明两个中央 hash，
未重绑其他漂移，未使用未通过的 scope 形成 collect/验收结论。

未运行完整离线门禁；本记录不提供真实 HTTP、Pi/OAuth/模型、Docling SDK/PDF 解析、
真实正文质量、六项 HITL、普通生产消费或真实恢复现场通过结论。
后续真实实验仍由 B 所有者闸门承接，F/D/G/H/I 原责任保持。
