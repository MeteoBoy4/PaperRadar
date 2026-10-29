# #114 Feed 离线工程交付覆盖

规格 #114 的工程范围由 #115–#119 实现；本页保管新增覆盖及证明边界，不扩大历史
A6/A7/A10 固定分母、历史通过结论、capabilities 或 live 标志。

## 规格覆盖

| #114 用户故事 | 实际公共接口及行为 | 独立新增测试 |
| --- | --- | --- |
| 1–2、6–8 | JGRFeed 原 item 字节、数据库 Feed 身份、PaperFacts 幂等/回摆、条件304、失败隔离 | test_feed_ingestion.py |
| 3–5、21 | PaperFacts 冲突观察、原断言/原字节、拒绝成功事实、独立回查与恢复 | test_feed_conflicts.py |
| 9–12 | JGRMetadata doiRA/适用注册机构/出版者、字段来源、主摘要/截断、最低完整及缺项结果 | test_feed_metadata.py |
| 13 | 共享 parser 权威、初始关键字段说明、历史完整解释/全空保护回归 | feed-parser-v1.md；test_feed_ingestion.py；既有 Feed 仲裁测试 |
| 14–20 | register_feed_value、Feed 归属与语言策略、歧义拒绝、原预算/retry冻结、历史缺 provenance | test_feed_language.py |
| 21 | 各片隔离恢复；组合原根不可访问后读来源字节、语言、预算和前置引用 | 上述各片恢复；test_feed_pipeline.py |
| 22 | 公共结果 scope/中文拒绝；生产默认拒绝test来源；未验证假设保留 | test_feed_pipeline.py；三个 Feed Contract |

| 实施决定 | 落点 |
| --- | --- |
| 1 边界复用 | HTTP只产材料，PaperFacts维护身份/仲裁；组合复用Tasks/ArtifactStore/备份 |
| 2–3 强冲突持久化/原子幂等 | 独立冲突表、不可变请求回执；来源先发布，短事务登记引用 |
| 4 Feed身份/原字节 | 唯一数据库规范URL、上游entry ID、Expat范围；严格DOI与受控path提取分开 |
| 5 JGR取得/最低元数据 | 有界共享HTTP、条件状态、逐路线执行与受控失败；错误页不保留 |
| 6 共享解释权威 | audit-abstract-v1 / audit-truncation-v1 / audit-http-v1；类别ADR-0033 |
| 7 结果与门禁分开 | minimum_complete/nontruncated_complete和scope；组合检查不授予实验资格 |
| 8–9 语言归属/冻结登记 | ADR-0035 v1；同事务预算/来源/组合前置；旧语言不追改 |
| 10 恢复/公开读面 | 每片追加迁移，公共读取、引用验证及备份闭包；组合默认不展开原材料 |
| 11 parser变更门禁 | 固定合成回归与字段说明；真实材料审查仍属EXP-1/B |

测试决定对应：新增测试穿过真实事实/制品/任务服务，只替换HTTP transport；四类强冲突、
无DOI/补DOI/回摆、HTTP失败及条件请求、来源仲裁/主区块/缺项、语言歧义与冻结，以及
原根不可访问恢复分别由各片公共测试覆盖。组合覆盖生产test来源拒绝、boundary拒绝、
metadata缺项/过时、前置/语言/预算事务故障、并发及恢复，不提交模型请求。

## 证据与最终收口

开发验证统一 `uv run --offline --locked pytest ...`。新增测试模块是独立 Feed 工程
证据，未登记进历史验收组的固定分母。完整门禁仍要求审阅和修复之后在最终集成工作树
运行 `./scripts/check-offline` 返回 0，并由可信 terminal 证明同次全部 required 结论通过。
最终 commit、run_id、status/applicability 及原始十四份 JSON 指针保存在工单收口评论和
工作树外台账；不将运行标识写回受哈希材料造成身份漂移。

scope维护只更新经审阅的现有路径哈希及真实head兼容元数据，不增减旧required测试集合
或计数。旧head的成功断言、人工future migration接点按新head更新；历史fixture及刻意
上一revision升级起点保持原值。按实际scope引用DAG重绑，无自绑定、无循环。

## 后续责任

Feed 工程支持供 B 显式调用；真实 JGR guid/参数/entry稳定性、主摘要可靠性、固定selected
至少5篇及Source判据仍由 EXP-1/Audit/Source/B 核实。生产来源boundary/RPC、实验根入口、
隔离及真实纵向验收也由 B 承接。C 扩展四刊、7天复查、metadata_unobtainable生命周期
及完整eligibility；F承接渲染/授权/TDM与正文。DEC-1/2/3不因本片提前裁决。

不领取 I15/T26，不宣称阶段 A、四刊来源、NAS、Pi/Docling/Read、校准或自动精读已就绪。
