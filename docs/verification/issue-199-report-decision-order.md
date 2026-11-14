# #199 报告决定范围与墙钟回退补丁

本台账记录 integration `81b037b0430add24e12857a104961e6aa75e50c9` 后的同票修正。
[原报告台账](issue-199-experiment-reports.md)与[披露补丁台账](issue-199-report-disclosure-followup.md)
均保持原字节；以前的长组合结论不扩大为本补丁全并集结论。
本补丁不新增 migration、不改表定义，head 保持 `b006_reports`。

## 问题与修正

旧 pending 校验用 `accepted_at <= frozen_at` 推断规划时是否已经接受。
报告后追加的合法接受若墙钟回退或相同，会误伤已发布的 pending；
反过来，规划前已接受但其墙钟较晚，又可能被伪装成合法 pending。

非分析 entry 现在冻结 Body 决定范围 `decision_scope`：through_sequence、boundary_decision_id
及有序 ID/sequence/result 元数据的 decisions_sha256。Body 的公共
`decision_metadata_in_connection` 只查询其自身元数据，不读 Paper trace、制品文件或实验接受关联。
Report 使用事务外完整预验的 Acceptances 记录按 decision_id 映射 supporting value 成功。

关联预读后若捕获范围出现未知 accepted ID，报告拒绝变化；范围捕获后若发生新决定提交，
固定写锁内的同 Connection 元数据重核以 facts_changed 回滚，要求显式重规划。
历史校验只解释已冻结的序号范围，后追加决定不因墙钟进入旧范围；
范围内已有接受的同一成功仍不能伪装 pending。日期/时间只作披露。
缺少范围的旧开发树非分析输入受控拒绝，不按墙钟追补、修改或回填；此为本票首次发布输入格式边界。

## 新 D1 与实际验证

新增独立模块 `tests/test_experiment_reports_decision_order.py`，完整 **4 节点**：

1. 报告后追加接受且墙钟回退：旧 pending verify/rebuild/backup、成员与字节保持。
2. 同上，但接受与规划使用完全相同的时钟。
3. 规划前已接受，其墙钟较晚；损坏接缝伪造 pending、重算输入/文件哈希后仍受控拒绝。
4. 事务外规划后、BEGIN IMMEDIATE 前由真实 CLI 提交接受；不持久半个 run，显式重规划产生 blocked。

红测：前两节点 **2 failed /16.85s**，均错误 registration_invalid；反向节点
**1 failed /10.29s**，旧实现错误 verify 退出 0。修正后：

- 四节点最终 **4 passed /60.13s**，批准的服务 clock/故障接缝；所有接受仍走真实 CLI。
- pending 原节点 1 + late 完整 2 + 标准冷恢复 1 + Body facts 完整 13：
  **17 passed /215.19s**，不重建无影响的六成员容量准备链。
- 导入链触发的 `check-compatibility cli`：独占 TMPDIR 先创建，
  **59 passed /86.73s**，入口总 87.33s。
- 全票受影响 **38 个 Python** 默认 strict mypy、Ruff、format 通过；
  实际非空提交范围 diff-check 与最终 clean 身份由外部交接保存。

完整新 D1 去重集合为以前 36 + 本次 4 = **40**；精确收集节点及逐模块计数在外部交接。
收集不是一次执行全部 40，最终合并树的全并集与 Schema 一致性由 merger 另记。

## 范围与未验

只新增 Body 元数据读取接缝与报告冻结 JSON 范围，不改变 Body 写入、接受授权、模型资格、预算或历史。
没有改写旧 migration、测试、fixture、源 hash 或两份旧覆盖台账；新增源码漂移交集成收口。
未运行完整离线门禁，无真实/live 命令、真实实验根/运行 checkout/私有材料或真实凭据读取。
全部使用 /tmp 合成 HTTP/Pi/parser/clock；Python 冷守卫不提升为 OS 隔离、模型质量或 NAS 证明。
