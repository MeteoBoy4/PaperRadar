# Issue #146 Wiley 主摘要规则 v2

依据：[#146](https://github.com/MeteoBoy4/PaperRadar/issues/146)。实施起点为
`94ee2d53180efbdf5f49bc159c517c85e0158e7b`，当前分支 `main`，初始工作树干净。
按 implement 要求在当前分支交付；没有另建 integration worktree。

## 规则与历史路径

交付显式选择的 `audit-abstract-v2`、`jgr-feed-parser-v2` 与生产整数 parser 2；
v1 默认调用、旧身份、成员、选样和历史解释保持。具体规则只在
[公共契约](../contracts/fixture-audit.md#摘要矩阵与显式运行105)维护。
生产 Feed 在 HTTP 前冻结版本，原 item 字节不重序列化；元数据请求/路线冻结规则，
恢复按保存版本解析。`feed07_parser_versions` 只给生产检查增加版本列，历史填 1，
v1 check_id 字节算法不变。按 #139 规则人工推进 head、备份声明和 scope 元数据。
既有 ADR-0008/0030/0034 的版本化与只追加决定直接适用，没有新增架构决定或改变规格。

EXP-1 原计划为 partial，本票明确选择**新计划**路径：离线诊断不是
`reinterpret_audit`，没有绕过其 complete 前置。四刊新规则 live 由 C/F/Abstract
承接，用显式 v2 服务 API 创建新计划；完成后才能登记 acquired fixture。
CLI 和 FeedPipeline.prepare 仍沿用 v1，B 显式采用 v2 前须有该版本适用证据。

## 独立 D1 覆盖

| 未绑定模块 | 用例数量 | 公共边界与验证内容 |
| --- | ---: | --- |
| `tests/test_wiley_abstract_v2.py` | 27 | parse_material：共存优先级、字段顺序、缺项、冲突、主/附加区块隔离、v1 保留与未知规则；嵌套标签及缺主摘要时附加区块定位 |
| `tests/test_wiley_audit_versions.py` | 2 | 新计划版本、v1/v2 回放及隔离恢复、partial 拒绝、内置版本防冒用 |
| `tests/test_wiley_production_versions.py` | 3 | Feed 升级及旧修订、元数据仲裁/版本、隔离恢复、v2 中断继续、不继承旧条件头、实际取得版本错配拒绝 |
| `tests/test_wiley_parser_migration.py` | 1 | 非空上一 revision 检查升级后的原身份与结果 |

以上 33 项不进入历史 A1–A10 回执、分母或 required 集合；原测试、fixture、冻结负例、
EXP-1 与既有 evidence 字节保持。主摘要、审计版本、生产接线的首个新增测试均先观察到
缺少版本入口的失败，再实现至通过。测试边界及审阅基点由本轮用户「继续」确认。

## 固定材料差异诊断

原 EXP-1 Feed、成员与来源材料仅在本机保留。来源见
[首轮审计](exp-1-http-audit.md)，逐字段安全投影见
[差异 JSON](issue-146-field-diff.json)：只含定位、哈希、code point 长度、截断信号、
字段增减及新旧仲裁，不含题名、摘要正文或响应原字节。

诊断仅读原库，以 SQLite backup 生成独立副本后迁移副本；使用 socket 连接/DNS
拒绝守卫，没有网络尝试，没有改原计划、执行新审计、登记 fixture 或追加解释。
重放前后原计划语义 SHA 均为
`257965f98447d368dcc402af5e217440d04a41e8de8bba933f6d5f395b9f1ba9`，状态仍 partial。
新结果只是将保留材料按 v2 瞬时解释、用现有纯仲裁规则计算的诊断，不是新 v2 审计证据。

| 原固定成员 | Feed 长度 v1 → v2 | 字段变化 | 截断信号 v1 → v2 | 最终摘要来源 v1 → 诊断 v2 |
| --- | --- | --- | --- | --- |
| jgr 1 | 85 → 1410 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| jgr 2 | 85 → 1142 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| jgr 3 | 85 → 1673 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| jgr 4 | 85 → 1647 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| jgr 5 | 85 → 1579 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| qjrms 1 | 65 → 1510 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| qjrms 2 | 65 → 2059 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| qjrms 3 | 65 → 1795 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |
| qjrms 4 | 65 → 缺项 | 移除 abstract | short_under_100 → 不适用 | feed → 缺项 |
| qjrms 5 | 65 → 2196 | abstract 文本/定位改变 | short_under_100 → 无 | registry → registry |

全部十篇题名候选不变；九篇更换 abstract，一篇移除 abstract，没有新增字段。
JGR 五篇在生产 parse_items(1/2) 的题名、DOI、entry ID、类别和原 item 物理范围均不变；
主摘要哈希/长度/截断状态与审计 v2 对应结果一致，AbstractValue.rule 升级。
JGR 五篇原最终仲裁依靠 Crossref，获选哈希/长度/信号全部保持；QJRMS 四篇 registry
获选也保持，原来仅由卷期说明支撑的第 4 篇变为缺摘要。无信号不等于已证明科学完整性。

## 验证与范围登记

开发验证：相关消费者组合与审阅新增回归通过；CLI 入口兼容组合 59 项通过；
通用迁移、备份和证据链接组合 66 项通过。全仓库 Ruff 与 mypy 通过，后者覆盖
752 个 Python 文件。具体收尾结果见本轮最终回复。
独立审阅的 Standards 硬违规及 Spec 开放发现已修复，详见
[两轴审阅记录](../../intent/review/issue-146-wiley-abstract-review.md)。
固定范围仅精确重绑实际变化的 source/support 与人工 head 预期，原组成员/计数保持。
逐登记旧新 SHA 见[重绑 JSON](issue-146-scope-rebindings.json)。
敏感变化为十组 migration 元数据、人工 head 预期在全部十组的用途，以及 A10
历史规则注册表；须按当前 base/HEAD/target/工作树身份核对，确认输入存于树外。
本台账不是可复用的身份确认或正式验收结果。

未运行完整离线门禁；没有新四刊 live、fixture acquired 登记、来源长期稳定性、
B 入口/Screening/Read、Pi、Docling 或 NAS 结论。完整门禁只在用户明确指令后运行。
