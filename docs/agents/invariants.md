# 领域不变量

以下是架构约束；有意偏离时先新增 ADR（见 [文档维护](documentation.md)）。

## 事实与历史

- SQLite 是业务事实的唯一事实源；大型 blob / artifact 存储在文件系统。
- Markdown 报告是持久化事实的只读投影（ADR-0018）。
- Paper 没有单一 lifecycle / status 字段；各处理阶段是独立事实（ADR-0006）。
- 历史只追加：新事实 supersede 旧事实。
- 用户行为和决策以可审计事件追加保存。
- 数据库结构变化通过 Alembic migration 完成；用户数据库只经由 migration 改动。

## 身份与合并

- 只有强标识符或权威版本关系可以自动合并论文（ADR-0001、ADR-0005）。
- 标题、作者、年份、URL 相似度只生成合并候选，由用户确认。
- 外部 Adapter 只写 observation；Paper 事实由确定性代码从 observation 推导。

## 运行

- 单篇论文或单个来源的失败被隔离，同一次运行中的无关任务照常完成。
- 相同输入重复运行保持幂等。

## 版本与 Stage fingerprint

- 已版本化的 Profile、Prompt、Topic、Contract 和语义配置一经引用即冻结；需要变化时创建新版本。
- Frozen Contract 从权威 Pydantic Schema 生成；Pydantic 定义是唯一的 Schema 来源。
- Stage fingerprint 只包含能改变该阶段语义的输入（ADR-0008）。例如：
  - volume、pages 等书目补全不使 Screening 或 Read 失效；
  - PDF 变化只按需使文档解析或 Read 失效。
