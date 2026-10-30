# Eligibility 与校准可见性

## 用途与范围

`paper_radar.calibration.visibility.evaluate_visibility(hidden_conditions)` 是共享的
校准可见性纯规则入口。输入为调用方本次已经装配的
`frozenset[HiddenCondition]`，返回不可变 `Visibility`，不读取数据库、时间、环境、
网络、模型或 Docling。它不依赖 eligibility；eligibility 消费本入口的动作许可，
不另行定义隐藏动作规则。

`paper_radar.eligibility.evaluate_paper(PaperProjection)` 返回一篇论文的全部概念结果；
`evaluate_concept(Concept, Iterable[PaperProjection])` 返回按 paper_id 排序的批量概念结果。
批量入口复用单篇求值，对同一事实给出相同资格、全部原因与范围限定；输入排列不改变结果，
一篇矛盾论文不污染其他论文。两者只消费已加载事实，不解引用、不查库、不读取当前时间或
环境、不领取任务，也不替代提交事务内的 FeedPipeline/A7 复核。

## 规则

**校准可见性**是基于某次已装配隐藏事实的展示与动作许可，不是制品删除、脱敏或状态迁移。
**隐藏条件**是仍成立的 `waiting_calibration` 或 `unrevealed` 事实。
`HiddenCondition.WAITING_CALIBRATION` 与 `HiddenCondition.UNREVEALED` 按 OR 合并；
空集合允许普通能力，全部条件解除才恢复。揭晓只移除对应未揭晓事实，不能覆盖仍成立的
waiting_calibration 或其他身份链成员上的隐藏事实。

调用方沿 Paper 身份、重复与合并链汇总全部仍成立的条件后传入；存活论文必须继承
被合并论文的隐藏条件。本模块不装配身份链、不实现合并、不从批次或制品内容推测事实。
`Visibility.hidden_conditions` 保留本次判定的受控原因集合；后续事实变化需要重新查询，
不会改写此前结果或历史 Screening/reuse 制品。

`Visibility.permission(VisibilityCapability)` 返回以下闭集许可：

| capability | 空隐藏集合 | 任一隐藏条件成立 |
| --- | --- | --- |
| `paper_facts` | `allowed` | `allowed` |
| `task_details` | `allowed` | `allowed` |
| `agent_content` | `allowed` | `denied` |
| `set_decision` | `allowed` | `denied` |
| `reading_request` | `allowed` | `denied` |
| `calibration_review` | `dedicated_path` | `dedicated_path` |

`paper_facts` 允许按既有规则读取论文事实，不覆盖其他访问或隐私约束。
`task_details` 允许展示任务存在性、stage、attempt、失败类别与失败队列归属。
依 [ADR-0037](../adr/0037-allow-task-details-during-blind-calibration.md)，用户明确接受
任务明细可能暗示边界或预测的推论；关联的 Agent 载荷仍属于 `agent_content`。
本规则不要求日志按校准许可省略 paper_id/stage 等任务字段。

`agent_content` 包括 Screening 建议、阶段二预测与分数、reuse 升级预测、理由和完整制品。
展示面、trace DTO、普通日报、运行摘要明细与错误分支按内容类别选择字段；允许论文事实
或任务明细不代表允许序列化完整对象。普通动作消费者在任何写入前检查许可，拒绝时
只返回受控许可与隐藏条件，不回显隐藏建议、预测或载荷。

`dedicated_path` 表示 calibration review 由专门路径处理，不由本规则判为普通动作；
它不授权 review 提交、不跳过冻结成员与批次约束，也不授权任何普通动作。
`allowed` 仅表示本规则允许，仍须满足各能力的其他前置条件。

枚举新增时同步本 Contract 与消费者 exhaustive 测试；公共入口对六种 capability 的
合成许可表全部断言，不使用默认放行。未知 capability 不走允许分支。

### 资格输入与返回值

`PaperProjection`、`MetadataFacts`、`ArtifactFact`、`DecisionFact`、`ExtractionFact`、
`QualityFact`、`ManualReadRequest` 都是冻结的最小内存事实，不是未来持久化表或外部数据
解析器。调用方先校验外部值、读取同一一致视图，沿身份链装配后传入。
不透明 reference 只用于身份相等检查，A 不解引用，也不按标题、摘要或路径推测归属。

- 身份：paper_id、待判定 version_id、current_version_id、canonical_id、revision_no。
  canonical_id=None 表示合并状态未知，不能默认未合并；被吸收身份和旧版本拒绝下游资格。
- 元数据：`MetadataFacts.from_result(JGRMetadata 的 MetadataResult)` 原样消费
  minimum_complete、nontruncated_complete、current_version 和 missing，附论文/版本/修订。
  不重新检查文本或截断；安全 trace 去掉 title 不改变最低就绪。nontruncated_complete
  不替代最低门槛，不代表 JGR/四刊来源判据已通过。最低标志与 missing 不一致、非截断完整
  却最低不完整或论文不一致是矛盾；旧版本/修订是 stale。
- 制品：presence=`present/absent/unknown`，reference、version_id、applicability。
  `ArtifactFact.from_success(SuccessView, version_id=...)` 原样保留 A7 的
  `current/historical/undeterminable`，不重新算 fingerprint。version_id 由关联领取依据
  装配，不由 A 猜测。未知不能当缺失，历史成功不能当当前成功；声称 current 却引用其他
  版本或 PDF、声称 absent/unknown 却携带成功引用，返回矛盾原因。
- 决定：每个 DecisionFact 有 reference、paper_id、显式审计 sequence、权威
  ScreeningReasonInput、依据 applicability；系统建议另绑定 screening_reference。
  `build_screening_reason` 与 `DECISION_REASON_DEFINITIONS` 是结果/来源/原因合法性及
  身份的唯一权威。先取最新人工事件，否则取最新系统建议；同优先级最新 sequence 并列拒绝。
  五种人工来源均优先于系统；失败 projection 从不成为决定。
  人工事件不因旧依据失效，decision_basis_stale 仅标记其依据已旧；依据未知时保留人工
  决定，但不能断言 stale。旧人工 denied/pending 同样高于新系统 accepted。
  系统建议只有绑定当前 Screening 制品、依据 current、D 输入 enabled 且 Agent 内容
  许可允许时才生效；paused/disabled/unknown 均不能启用系统建议。
  PaperTrace 的 CandidateDecision 是字段仲裁事实，不接受为 Screening 决定。
- PDF 与提取：PDF 绑定版本；提取的 `succeeded/failed/absent/unknown`、不透明 reference、
  pdf_reference 和 applicability 独立输入。失败不自动取得 retry 许可。
  reference_harvest_failed 是可选独立失败事实（未知为 None），完全不影响 PDF/提取/Read，
  也不计算 E 的参考文献资格。成功只表达生产者已接受的结果，不验证 PDF/Docling 内容。
- Read：D 装配 GateState；根级标记装配 RootPurpose；已核对执行链来源装配
  ExecutionSource，三者互不推导。Visibility 必须由共享入口装配；Read 消费
  `permission(READING_REQUEST)`，系统建议消费 `permission(AGENT_CONTENT)`，不复制隐藏条件。

`Eligibility` 返回 eligible、按 `EligibilityReason` 声明顺序去重的 reasons、support、
scope，以及可选的生效 decision、quality_failure、下游 owner。支持概念的 eligible 为
bool，真时 reasons 为空；假时包含所查询概念及其前置的全部不满足项，不附加未提供的
排名/容量/报告条件。effective_screening_decision 的真表示存在生效决定，决定本身可以是
accepted/pending/denied；后续全文需求另要求 accepted。它不是普通展示 DTO，消费者仍须
按 visibility 裁剪字段，不能直接序列化整个 PaperProjection 或历史候选。

support=`partial` 必须连同 scope 保存和展示：最低元数据为 `minimum_metadata_only`，
自动 Read 为 `read_prerequisites_only_no_rank_capacity_claim_or_budget`，waiting_calibration
为 `supplied_visibility_fact_only`。support=`deferred` 时 eligible=None、owner 明确，
scope=`downstream_responsibility`；不能转换成 false、unknown 或 ready_to_claim。
重复 paper_id 的批量条目仅该身份返回 duplicate_paper，清除选择性 evidence；不受排列影响，
deferred 概念仍保留 None。普通单篇 deferred 结果不制造原因。

### Read 质量、用途与请求

质量依据是 `formal_gate/experiment_document_gate/failed/absent/unknown`，
通过依据必须绑定同一 extraction_reference。failed 必须带闭集 QualityFailure：
`pdf_text_layer/body_boundary/reading_order/evidence_replay/content_identity/layout_review/representative_coverage`。
这些是生产者已作判断的失败类别，A 不计算阈值、F 的四刊门槛或 D 的正式 evaluation。
失败同时返回 quality_failed 与 quality_failure；缺少失败类别是矛盾。

| 根用途 | formal_gate | experiment_document_gate | failed | absent | unknown |
| --- | --- | --- | --- | --- | --- |
| production | 质量前置通过 | quality_not_formal | quality_failed | quality_absent | quality_unknown |
| experiment | 质量前置通过 | 质量前置通过 | quality_failed | quality_absent | quality_unknown |
| unknown | root_unknown | root_unknown | root_unknown + quality_failed | root_unknown + quality_absent | root_unknown + quality_unknown |

执行来源独立为 `production/test/unknown`；test 或 unknown 即使实验用途、质量通过也拒绝
Read。production 只是执行来源，不授予生产消费资格，不提升实验制品，不重置预算。
质量和其他前置满足的 experiment + production 来源 + document gate 有显式请求正例；
实验路径不扫描自动队列，eligible_for_auto_read 固定附 experiment_no_auto_queue。
正常消费与实验结果隔离仍由 B/Body 的根装配和消费者验证。

Read 前置要求 canonical/current、最低元数据、有效 accepted、当前 PDF/成功提取、
质量、用途、执行来源与动作许可。人工 accepted 可在系统门禁关闭时获得这些前置资格，
不代表有排名名额；自动领取仍消耗每日名额。requested_manual_read 表示**显式请求的
Read 前置资格**，要求请求引用同一论文的生效人工 accepted，不接受系统 accepted 代替，
并同样检查正文/质量等前置；请求已存在但正文未齐时本结果仍为 false，请求事实本身不删除。
请求不创建决定、不修改预算、不授予租约或执行资源，显式请求不占自动名额的执行纪律归 B/G。
后续新的人工事件使旧请求依据 superseded；后续 denied 阻止未开始的 Read，历史仍保留。

### §5.7 概念矩阵

“身份”指 canonical/current；“全文决定”指身份及生效 accepted。原因详见下节闭集。

| 概念 | 所需事实 | 支持程度／范围 | 主要原因／前置 | 消费者／承接 |
| --- | --- | --- | --- | --- |
| canonical_paper | canonical_id、paper_id | supported | canonical_unknown、not_canonical | B/C |
| current_version | version_id、current_version_id | supported | version_unknown、not_current_version | B/C |
| metadata_ready | 身份、MetadataFacts | partial：仅最低元数据 | metadata_* | B 首接，C 完整生命周期 |
| metadata_unobtainable | 七天复查生命周期 | deferred | 不制造资格 | C |
| current_screening_artifact | 身份、A7 applicability、制品引用 | supported | screening_* | B/D |
| current_screening_suggestion | 建议规则及作用范围 | deferred | 不执行建议规则 | B/D |
| effective_screening_decision | 身份、权威原因记录、sequence；系统另需当前制品/门禁/许可 | supported | decision_*、projection_not_decision、系统前置 | B/D |
| decision_basis_stale | 生效决定、依据 applicability | supported：依据标记 | decision_basis_current/unknown、生效决定前置 | B/D/H |
| needs_reference_harvest | 参考文献取得事实 | deferred | 不制造资格 | E |
| reference_list_completeness | 列表质量 | deferred | 不制造完整性 | E |
| needs_pdf | 全文决定、PDF | supported：absent 或历史产生新需求 | pdf_*、已存在为 pdf_already_present | B/Body/F |
| needs_extraction | 全文决定、当前 PDF、提取 | supported：absent 或历史产生新需求 | extraction_*；当前失败需显式 retry | B/Body/F |
| extraction_failed | 身份、当前 PDF、当前提取失败 | supported | extraction_not_failed、未知/矛盾/历史 | B/Body |
| needs_reuse_assessment | reuse 规则及任务 | deferred | 不制造资格 | D |
| reuse_escalation_unavailable | reuse 失败与回退 | deferred | 不制造资格 | D |
| eligible_for_auto_read | Read 全部前置、生产根 | partial：无排名、容量、领取、预算 | Read 原因；系统 enable；experiment_no_auto_queue | B 首接；D/G/H |
| manual_accepted_channel | 人工通道排名/名额 | deferred | 人工 accepted 不等于获名额 | G/H |
| accepted_read_backlog | 队列及既有分析 | deferred | 不计算积压 | G/H |
| requested_manual_read | 显式请求、人工 accepted、Read 全部前置 | supported：请求的前置资格，不领取 | manual_request_*、manual_decision_required、Read 原因 | B/G |
| model_failure_queue | 真实任务失败队列 | deferred | A7 current_failures 不冒充完整列表 | B |
| waiting_calibration | Visibility.hidden_conditions | partial：仅已给定输入 | visibility_unknown、not_waiting_calibration | C 保留器，D/H |
| waiting_review | 复核成员/规则 | deferred | 不制造资格 | B/H |
| waiting_report | 报告候选/成员 | deferred | 不制造资格 | B/H |
| capacity_warning | 排名/容量估算 | deferred | 不计算容量 | G/H |

## 错误与拒绝

`denied` 是普通动作和 Agent 内容的受控拒绝结果，原因是 `hidden_conditions`，
不是 Screening 业务决定原因。输入是类型化的已装配事实，调用方负责解析和校验外部值；
此入口不接受原始数据库行、完整制品或自由文本错误作为事实。

资格原因使用独立 `EligibilityReason`，不与 DecisionReason/PaperReason/PipelineReason
混用。以下逐项列出闭集；未知与矛盾是事实拒绝，**不**是业务 denied 决定：

| 原因 | 含义／类别 |
| --- | --- |
| canonical_unknown、version_unknown | 身份事实未知 |
| not_canonical、not_current_version | 已知身份不适用 |
| identity_contradictory | 空身份或非法修订号，不能把空值相等当作当前/存活身份 |
| metadata_unknown | 缺少元数据投影，未知 |
| metadata_incomplete、metadata_stale | 权威最低元数据不完整／版本修订已旧 |
| metadata_contradictory | 元数据标志或身份相互矛盾 |
| metadata_no_title、metadata_no_abstract、metadata_no_source_url | 权威已知缺项 |
| metadata_unknown_truncation、metadata_agency_unknown | 权威事实未知 |
| metadata_routes_incomplete、metadata_agency_unsupported | 路线未完成／机构不支持 |
| decision_absent、decision_not_current | 无生效事件候选／系统依据已旧 |
| decision_contradictory | 原因组合非法、跨论文、缺引用或最新事件并列 |
| decision_basis_unknown、decision_basis_current | 不能断言依据旧／已知当前，所以 stale 谓词不成立 |
| projection_not_decision | 只有只读失败投影，不能成为决定 |
| gate_paused、gate_disabled、gate_unknown | D 给定门禁不允许系统建议生效；unknown 是未知 |
| screening_absent、screening_unknown、screening_historical、screening_contradictory | 制品已知缺失／未知适用性／历史／引用矛盾 |
| decision_not_accepted | 有效决定不是 accepted，不改写其业务结果 |
| pdf_absent、pdf_unknown、pdf_historical、pdf_contradictory、pdf_already_present | Read 缺 PDF／未知／历史／矛盾；或 PDF 需求已满足 |
| extraction_absent、extraction_unknown、extraction_historical、extraction_contradictory | Read 缺提取／未知／历史／引用矛盾 |
| extraction_already_present、extraction_retry_required、extraction_not_failed | 需求已满足／当前失败须 retry／不是当前失败 |
| quality_failed、quality_absent、quality_unknown、quality_contradictory、quality_not_formal | 质量失败／依据缺失／未知／引用矛盾／生产拒绝逐文档依据 |
| root_unknown、experiment_no_auto_queue | 根用途未知／实验根不进入自动队列 |
| execution_source_unknown、test_execution_source | 执行来源未知／test 来源不能供给 Read |
| visibility_unknown、visibility_denied | 未给共享许可／共享许可拒绝 |
| manual_request_absent、manual_request_contradictory、manual_request_superseded | 无请求／请求身份或引用缺失矛盾／后续人工事件使旧请求依据失效 |
| manual_decision_required | 显式请求不能借用系统 accepted |
| not_waiting_calibration | 已给定隐藏事实中不存在等待保留事实 |
| duplicate_paper | 批量输入同一身份重复，装配矛盾 |

JGRMetadata missing 与既有组合拒绝的对应关系只用于解释，不替代服务：

| MetadataMissing／现有 PipelineReason | 资格原因／边界 |
| --- | --- |
| current_version_changed | metadata_stale；minimum_complete=false 时也返回 metadata_incomplete |
| no_title / no_abstract / unknown_truncation | metadata_no_title / metadata_no_abstract / metadata_unknown_truncation |
| no_source_url / routes_incomplete | metadata_no_source_url / metadata_routes_incomplete |
| agency_unknown / agency_unsupported | metadata_agency_unknown / metadata_agency_unsupported |
| metadata_incomplete / metadata_stale | 同名资格原因；前者另附全部 missing 映射 |
| boundary_missing | current_screening_artifact 的 screening_absent/unknown/historical；不新算 boundary |
| out_of_scope | 通过既有权威 Screening 原因记录保留 denied；全文前置给 decision_not_accepted，不重新执行映射 |
| test_source | Read 给 test_execution_source；FeedPipeline 仍独立拒绝其生产登记 |
| invalid_request / corrupt_reference | 解析／持久引用完整性仍由 FeedPipeline 拒绝；本入口仅检查内存身份矛盾 |

质量依据缺失（quality_absent）、原始事实未知（*_unknown）和明确业务不满足分别保留，
各 *_contradictory 与 duplicate_paper 表示事实矛盾；这些原因可以并存。

## 不提供／不证明

本入口不提供保留器、校准表、正式 evaluation、展示 DTO、动作写入服务或日志字段过滤。
合成消费者仅证明许可契约，不证明真实产品面的字段裁剪、提交前守卫或身份链装配。
资格入口不实现建议算法、未来表、全文生产、质量门槛计算、队列排名、每日容量、任务领取、
租约或重试；也不证明读取根标记、执行来源装配或事务内再次核验已接线。

| 消费者 | 承接责任 |
| --- | --- |
| [B](../roadmap.md#module-b) | trace 首次消费资格；最低元数据、人工 accepted、PDF/Read 资格及两种投影的真实组合测试；show/trace/最小日报消费 visibility，即使隐藏集合为空；普通动作写入前守卫 |
| [C](../roadmap.md#module-c) | 保留器、waiting_calibration、实际隐藏；身份/合并链装配与存活论文继承 |
| [D](../roadmap.md#module-d) | 未揭晓/揭晓事实、专用 review 路径及新增展示面隔离 |
| [H](../roadmap.md#module-h) | 完整日报、复核与诊断分支的真实隐藏组合测试 |

## 相关

依据：[规格 §4.6](../../intent/draft.md#46-盲评校准)、§10/§11 A；
[#120 最终裁决 D1/D5](https://github.com/MeteoBoy4/PaperRadar/issues/120#issuecomment-6520223100)、
[#121](https://github.com/MeteoBoy4/PaperRadar/issues/121)。
资格依据：[规格 §5.7](../../intent/draft.md#57-派生任务查询)、
[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)、
[#120 最终裁决 D4](https://github.com/MeteoBoy4/PaperRadar/issues/120#issuecomment-6520223100)、
[#122](https://github.com/MeteoBoy4/PaperRadar/issues/122)；既有前置权威见
[Feed 元数据](feed-metadata.md)、[FeedPipeline](feed-pipeline.md)、
[Screening 原因](screening-validation.md)、[A7 applicability](screening-tasks.md)。
独立工程覆盖与未验边界见 [A 窄收口台账](../verification/a-narrow-delivery.md)。
