# 用独立受保护账本保存执行准入事实

状态：已接受；日期：2026-11-09；依据：[#168 D-6 所有者裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#170 正文对本 ADR 免另行审阅的特批](https://github.com/MeteoBoy4/PaperRadar/issues/170)；补充 [ADR-0051](0051-separate-live-binding-capabilities-and-activation.md)，关联 [ADR-0052](0052-version-admission-uses-and-capability-requirements.md)、[ADR-0053](0053-expire-capabilities-by-evidence-class-and-coverage.md)、[ADR-0054](0054-separate-execution-binding-from-call-materials.md)。 只追加收紧日志例外由 [ADR-0056](0056-protect-pending-revocations-with-an-append-only-log.md) 补充。 认证事件证明来源与正常刷新语义由 [ADR-0063](0063-observe-normal-oauth-refresh-in-product-process.md) 补充。

产品 uid 可写的业务库不能同时证明该 uid 无法伪造的执行许可。准入账本位于独立 root 所有的 `/var/lib/paperradar/live-evidence/`，使用 SQLite rollback journal；产品 uid 只读，无写入通道。证据接收、人工激活及放宽资格的操作只通过所有者授权的受保护入口；只允许收紧的 helper 可以追加撤销与时间打点，不能授予或恢复资格。入口自身也必须来自 root 所有的冻结副本，不能由 sudo 从用户可写仓库或虚拟环境导入代码。此边界不防范同 uid 直接修改产品源码，也不防范 root 篡改信任根。

「SQLite 是业务事实唯一事实源」仍指业务数据库：论文、任务、attempt、预算及业务制品继续由原有业务库负责。第二个 SQLite 只保存执行准入事实、批准计划和相应审计，不成为第二套业务预算权威。准入资格不修改任务重试代际或刷新余额；计划中的案例、窗口、轮数、上限与停止条件用于核对接收材料，不承担业务 attempt 的原子预占。

账本 schema 版本与回执格式版本分别管理；账本不使用业务 Alembic migration。兼容演进优先只增加字段，旧读写器无法确认兼容的版本一律拒绝，尤其不能向更高版本账本写入。回执格式升级不代表旧账本可读；新账本 schema 同样不自动接受另一格式的回执。接收幂等不覆盖原事实，失败审计只追加。

账本与受保护回执来源单独备份，不随业务数据库快照恢复。恢复只还原历史，必须使全部激活失效并保留恢复审计，随后由所有者重新人工激活；不得以恢复文件或旧激活记录自动恢复许可。发现 journal、来源丢失、权限失信或损坏时拒绝，产品不能自行恢复、修复或重建。采用业务库加签名的备选会增加签名密钥及恢复耦合，并可能让业务恢复复活已撤销资格，因此不采用。

代价是多一套必须封印部署、单独备份和人工恢复的信任根。收益是产品可写来源只能造成拒绝或收紧，无法借配置 passed、普通 JSON、业务恢复或接收动作放宽准入。来源与完整性检查不独立证明没有遗漏失败；失败历史的完备性仍由受保护采集器及 sudoers 边界承担，真实 OS 效果需现场验证。
