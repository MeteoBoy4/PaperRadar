# A6 规格与裁决对照（#67/#75）

本表按 #67 正文、实施前补充、D1–D4 裁决、六项补充、第三轮 N1–N11 及 N1/N2 裁决核对，
再应用轻量重复取得与完整重解析的最新裁决。历史正文和固定提交链接不追改；覆盖关系见
[ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)与[论文事实 Contract](../contracts/paper-facts.md)。
表内模块均在 `tests/`，除特别注明外省略 `.py`。固定源码和材料字节见 `scripts/a6_scope.py`，
能力的机器可读用例/材料映射见 `tests/fixtures/a6_capabilities.json`。模块内全部固定参数化节点
必须在同一正式 pytest 回执通过；表内名称或总退出码不能代替实际执行。

## 十二项能力与正文覆盖

| capability | 正文归属 | 固定测试与材料；证明及边界 |
| --- | --- | --- |
| doi_identity | US1–6；ID2–5 | test_paper_identity/inputs/service、feed_identity；paper_facts_v1.json 独立 DOI 向量，DOI 一对一 Version/Paper，冲突整笔拒绝，弱相似不归并；combined 恢复 UUID/DOI 归属与无 DOI 正例 |
| feed_discovery | US7–10；ID6–8 | feed_registration/inputs/discovery/identity/arbitration；feed_support 与 combined：完整字节 fingerprint、first/last_seen、跨 Feed、补 DOI、D3 回摆、全部解释 |
| version_selection | US11–15；ID11–12 | version_relations/inputs/materials、pending_relation_roles；**paper_recovery_combined、paper_recovery_support/reader** 汇合正式有/无摘要升级、旧 preprint、同级保持、never-selected、关系三态，不实现人工换版本/同级替代 |
| field_arbitration | US16–23；ID7–10/12 | source_arbitration、manual_corrections、paper_acquisitions/reparse、feed_arbitration；**paper_recovery_combined 与 support/reader** 汇合四源、轻量取得、完整新解释、fallback/provenance、新旧修订，无撤销 |
| consistent_read | US30；ID13/17 | paper_process 的两 SELECT 间确定提交；source_process 人工历史；paper_mapping_process.test_mapping_has_one_read_view_across_concurrent_commit；显式 BEGIN 单一事实时点 |
| input_mapping | US24–28；ID13/15 | paper_mapping/failures/process；实际 build_stage_input 与同库 snapshot，双阶段 readiness 独立，书目/来源审计隔离、文本/flag/主题投影变化；combined 的当前正式缺摘要受控失败 |
| historical_rebuild | US29；ID14 | paper_mapping 的完整重解释历史与旧配置；**paper_recovery_combined、paper_recovery_reader** 只持 ID/revision/snapshot/独立散列，从恢复候选重建，不从外部请求携题名摘要 |
| concurrency | US33；ID16 | paper/feed/source/version_relation_process：真实进程/确定屏障，唯一身份/请求、补 DOI 竞争、5 秒 busy；不以 sleep 猜测竞争 |
| crash_recovery | US34；ID16 | 四类 process：发布后、业务事务中、提交未返回强杀重试，无半事实；旧精确回执与关系依据保留 |
| migration | ID3/19 | paper/feed/source/version_relation_migrations：非空 a405→a601→a602→a603→a604，旧 config/artifact/Pi 历史、FK、失败/kill 原子性；writer 另真实临时 base→head，未来 head 拒绝 |
| cli | US31–32；ID18/20 | paper/feed/source/version_relation_cli；paper_recovery_integrity 显式关系-only 字节核验；show/trace 中文只读、本地 help、默认隐藏摘要、来源三态，不提供写/资格/映射 CLI |
| isolated_restore | US35；ID19/21 | **paper_recovery_combined/integrity/damage、pending_relation_roles 与 support/reader**：同一非空 WAL 批次、多 Paper/版本/四源/Feed/新旧配置，拒原根及改名根/源备份，恢复再搬迁，两新进程；重哈希且 FK 合法语义损坏仍拒绝、不修复 |

US36、ID1/22–24 由 test_a6_acceptance/integrity/entry/test_receipt/status/formats 与实际正式入口
证明：required 组、同次前置、严格九域格式（含 mapping_result）、固定材料、逐模块整数回执、身份、不可覆盖、终态、
applicability，及下面未验收边界。ID1 依赖方向另由 test_paper_migrations 公共架构守卫覆盖；
ID20 的 PaperReason/中文指导/敏感哨兵在 paper_inputs/cli/mapping_failures，paper_model_validation 覆盖 JSON/strings 公开校验入口；ID23 保持原串行
协议，没有新 runner、xdist、性能基准或 #63–#66 功能依赖。

## 首轮补充与 D1–D4 裁决

| 条目 | 最终行为、测试及明确未交付部分 |
| --- | --- |
| D1 | 一个 DOI 恰好一个 Version/Paper、类别不可变，paper_service/feed_identity/version_relations；删除旧“同 DOI 多公开形态”解释 |
| D2 | paper_identity 固定向量：ASCII 折叠/非 ASCII 保留、仅 URL path 严格单次解码、2048/2049 字节、query/fragment 包装受控拒绝；拒绝表示输入能力。未来 guid/落地页提取未实现 |
| D3 | feed_discovery 的 A→B→A 只推进 last_seen，首次仲裁时间不变、停在 B；combined 保持恢复后同义 |
| D4 | feed_identity/paper_service 强冲突整笔 identity_conflict；version_relations 关系冲突成功 requires_merge；阶段 C 强冲突观察持久化仍是硬门禁 |
| T1/T2 | mapping/combined 从历史题名摘要重新 build，不是 Docling 正文或持久 StageInput replay；不承担未来任务层载荷保存义务 |
| T3/T4/T5 | Contract 区分配置快照/来源内容/观察/候选/引用式完整修订；source_arbitration 历史完整读取、paper_backup 与 combined/damage 防错候选/缺字段/跨版本 |
| T6/T7 | paper_inputs、manual_corrections 与 mapping_failures：摘要 text/flag/rule 同候选，unknown 不当 false；online-first 是 journal，无跨版本补摘要 |
| B1 | feed_identity/process：无 DOI→未占用 DOI 唯一补登记；X→Y/占用 Y 按较新 D4 identity_conflict，X→无保 X；不沿用旧 requires_merge |
| B2 | version_relations/inputs：规范预印本→正式版、双向原断言/locator、端点可未出现、关系-only 不造空版本；三态 CLI 与组合恢复可查 |
| B3 | source/feed_arbitration、manual_corrections、paper_inputs：manual>publisher>registry>feed，流/时间/hash/parser/tie，人工按明确事件；结构化日期/有序作者/卷期页/URL，摘要整体修正 |
| B4 | **由最新轻量取得裁决覆盖**，见下表；HTTP 状态不进入类型，空候选 not_retained，不伪造 task_attempts |
| B5 | paper_inputs/process、四类 backup 与 combined/damage：有界原 bytes、先完整发布后业务事务，完整孤立制品允许，无引用输入/事务参与/自动清理 |
| B6 | feed_registration/inputs/backup：DB 为唯一 Feed 身份；query/path/尾斜杠保留，userinfo/fragment 拒绝；无 feeds.yaml、ETag 或健康写面 |
| B7 | mapping/failures/process：当前 paper 与历史 version/revision 二选一、同库 snapshot、双阶段 readiness、默认无 blob I/O；不建 original_title_is_zh 或可靠 URL eligibility |
| S1 | 按实际纵向 68→69→70→71→(72,73)→74→75 集成，逐条追加 a601–a604；中间证据不替代最终集成 run |
| S2 | 只 initial/journal_upgrade，同级维持；人工加入 Paper、人工选同级/替代、merge/undo 延期；version_relations/CLI/combined |
| S3/S4 | paper_cli 与 inputs 只读 show/trace、raw bytes 单入口，无修正/历史选择器/映射写 CLI；失败响应为类型边界 |
| 测试/固定绑定/文档补充 | 全部上述固定模块、A6 自有反例及 scope audit；旧分母不变；旧/新 hash/理由/run_id 台账在工作树外，真实门禁预算和终态另存原 JSON |

## 六项后补与 N1–N11

| 条目 | 固定覆盖与未验收边界 |
| --- | --- |
| 后补1 | feed_registration/backup：数据库身份唯一，未来 feeds 配置必须决定对齐；期刊/ETag/健康不预建 |
| 后补2 | a6_formats 的独立 abc SHA-256 literal、feed_discovery 时间矩阵、combined；版本权威在生产纯规则，UTC 微秒、发布日期精度另存 |
| 后补3 | mapping/readiness/CLI 不派生 original_title_is_zh、不推可靠 URL/metadata_ready；未来 eligibility 负责 |
| 后补4/6 | inputs 的 scheme/extra 字段拒绝，migrations 实际表/约束与无主状态；不实现 duplicate_candidates/merge_events/manual_intakes/任务/校准空壳能力 |
| 后补5 | paper_migrations 架构守卫：config/screening/stage_inputs 不反向依赖、papers 禁外部客户端；纯模块 SQLAlchemy/storage 隔离，新增纯 Feed/relations/text_rules 由 A6 formats 守卫补全 |
| N1 | paper_facts_v1.json 与 paper_inputs：仅 LF+外围 strip、内部空白/Unicode 保留；HTML 标签/注释拒绝而数学尖括号接受，不是 HTML 解析器 |
| N2 | version_relation_cli 与 combined：effective/endpoint_missing/requires_merge 全部可查，等待合并不是静默丢关系 |
| N3 | source_arbitration、backup/damage：修订只引用完整获选候选，同版本事务 max+1 唯一；不复制摘要、不推 as-of 时间 |
| N4 | paper_inputs 的 reason_catalog_and_guidance、CLI/failure 哨兵；单一 PaperReason、格式 1、中文下一步，不扩 StorageReason |
| N5 | process/mapping_process：BEGIN IMMEDIATE、busy 5 秒无内部 retry、显式 BEGIN 一致读，真实屏障/强杀；既有进程组清理协议保持 |
| N6 | manual_corrections/CLI：actor/reason 未认证、无产品写/撤销入口，修正仅追加且绑定版本；不声称认证审计 |
| N7 | a6_integrity/entry/status 与最终 scope audit：同次 identity/哈希/分母/真实 head、缺终态拒绝；先最新 integration/冻结提交再真实 run；旧成功 applicability=different 不能覆盖修改 |
| N8 | ISSUE=75、PARENT_ISSUE=67 注释区分，a604 实际末端；不照旧横向拆票或只绑定 a601 |
| N9 | Contract/ADR 历史只追加，无 retention/孤立 blob 清理/修订压缩；历史恢复不能变成清理功能 |
| N10 | 下列来源假设全部未验证，NOT_ASSESSED 对外保留，阶段 C 逐条回填；不把历史来源 170/170 当本次 live 证据 |
| N11 | ADR 的固定旧正文处置表覆盖原 #67 提交链接；不追改旧 spec/证据来伪造当前范围 |

## 实施中的最新两次裁决

| 要求 | 固定覆盖 |
| --- | --- |
| 轻量重复取得/乱序一致性 | paper_acquisitions、source_arbitration：A(t1)→A(t3)→B(t2) 与时间顺序同值；not_retained 可留取得/引用修订，不复制候选/新响应大包，精确重试原回执；combined 恢复此依据；Feed D3 不变 |
| 完整新解释1 | paper_reparse、mapping、combined：同材料 v2 缺摘要使当前缺项，旧修订/旧 snapshot 重建原输入，别来源可补；不是字段撤销 |
| 完整新解释2 | reparse/feed_discovery/source_arbitration：完整声明必填、partial/economical 拒绝，同流材料 parser 单调，同版本恒定，旧精确请求优先原结果；不能识别撒谎解析器 |
| 完整新解释3 | paper_reparse.different_material_missing_field_still_keeps_prior_candidate：不同 payload 继续缺项不清空 |
| 完整新解释4 | mapping 的缺项/fallback 新 provenance 修订/新文本指纹，reparse/feed_arbitration 全空保护；combined 逐项恢复，独立关系不因字段重解释撤销 |
| 完整新解释5 | 未验证假设公开保留阶段 C parser 升级固定样本门禁，关键字段减少必须声明；没有真实 parser 样本，不声明已通过 |

## 未验收项与交付证据

真实来源真实性、JGR/QJRMS guid 裸 DOI、Wiley 落地页及参数、eLocator、摘要截断标记准确性、
Feed entry 稳定性、Crossref 双向关系与所有真实 parser 完整性均未验证；HTML 抽取和截断检测未实现。
阶段 C 接入真实 Feed 前必须补强冲突观察持久化；parser 升级前必须固定样本回归并声明关键字段减少。
A6 离线 passed 不绕过这两项门禁。

merge/undo、arXiv/PMID、metadata_ready/共享 eligibility、任务 attempt/lease/预算/每日配额、完整
校准可见性、RPC、Pi/Docling/Read 执行、Read/suggestion/report 指纹、NAS、自动精读和完整阶段 A
继续未验收。所有结论 stage_a_verified/live_verified/rpc_verified=false。A5 的 paper_fact_mapping
是历史未覆盖事实，保持原样；新增论文映射闭环由本 A6 结论承担。

正式结论由完整 `check-offline` 实际返回 0 与 `verification-status` passed/verified/same 共同确认。
保留十份原 JSON、旧/新绑定台账、TDD 红绿日志、实际 collect/执行分母、环境检查和至少 30 分钟
观察预算/实际耗时；这些外部运行记录不写回受自身 identity/hash 绑定的 tracked 材料。

## r1/r2 审查后补充绑定

新增独立模块 `test_paper_review_boundaries`（22 例）、`test_paper_review_reads`（18 例）、
`test_a6_review_formats`（4 例）进入 A6 固定范围。前两者覆盖 DOI 双包装类别、精确 URL 路径、
歧义标签拒绝/数学比较接受、原始未知输入原因、关系原书写和日期联合解析，以及读取环境原因、
缺制品根参数、当前版本选择文本、普通元数据等待合并提示与精确重试；最后一个通过公开
writer/status 核对真实 mapping_result 格式及 2/True/1.0 漂移拒绝。原固定回执范围并集 171 模块 3033 例
条数不变，新增后收集并集为 174 模块 3077 例（不是全套 pytest 总数）；A6 原 45 模块 499 例增为 48 模块 543 例。
三条旧 DOI 向量仅对齐 unsupported_form，不增加向量。
完整处置及未采纳理由见[审查处置表](../../intent/review/issue-67-a6-paper-facts-review-resolution.md)。
