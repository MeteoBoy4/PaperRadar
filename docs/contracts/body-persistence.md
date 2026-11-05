# 正文附加、提取预算与人工质量

## 用途与范围

`paper_radar.body.BodyService(database, data_root, *, sink=None)` 持久登记根用途、
直接人工决定、PDF 当前选择与实验样本，组合 canonical parser 和规范正文制品服务，
保存全库共享的提取预算及独立人工版式核查。只读查询和备份验证不加载 SDK、调用模型或修补事实。

## 规则

### 根、决定与来源

`register_root(purpose)` 一次写入 `production/experiment`；相同用途重放返回原登记，
不同用途拒绝。SQLite 是唯一事实源：登记包含根 ID、用途、UTC 时间及绑定摘要，
禁止 UPDATE/DELETE；`root()` 对缺失、摘要不符或矛盾返回 `unknown`。不写文件侧标记，
恢复到新位置保留原登记，不按路径猜用途。

`decide(paper_id, record, *, request_id, actor, screening_references=())` 只追加
`direct_manual_decision`，经权威 Screening 原因校验及共享 visibility 的 `set_decision` 检查。
目前持久隐藏条件为空；未来身份链隐藏事实由 C/D 装配。版本与修订取写入时当前事实，
sequence 在论文内全局单调，由 API 在 `BEGIN IMMEDIATE` 内分配；不接受调用方序号。
同论文同序号唯一约束保留先提交者；相同 request 重放幂等，换内容为 `request_conflict`。
`decisions(paper_id)` 保留全部来源、原因、actor、时间与 Screening 成功引用。
共享 `effective_screening_decision` 选择最新人工事件；旧版本/修订的人工决定保持效力，
其依据标为 historical（stale），不因后来 Screening 成功自动改写来源。

上游 `ExecutionSource` 仅取生效决定引用的真实 Screening 成功审计，不要求成功仍 current：
任一 `test` 优先为 `test`，全部 `pi_rpc` 为 `production`，无引用为 `unknown`。
引用须归属同一论文。纯人工 accepted 无上游依据在 Body 内明确拒绝 Read；这是已知能力限制，
专用人工通道由 [B/C](../roadmap.md#module-b) 承接。B 的人工决定命令须提供 Screening 引用。
Read 分析自身成功来源由独立任务记录，不能用上述来源代替。

### PDF 与实验样本

`attach_pdf(paper_id, pdf, *, request_id, version_id=None)` 要求明确 paper；
version 缺省冻结为首次附加时当前版本，显式 version 必须属于该 paper。
只验证文件级 `%PDF-` 签名、至少 1024 字节及 SHA-256，不声称离线证明论文归属。
原字节以 `original_pdf` 发布，访问依据固定 `manual`；失败不追加选择，发布后提交失败
最多留下无业务引用的不可变材料。不同字节保留不同内容对象。
每次显式附加追加选择事件；`pdfs(paper_id)` 返回历史，`current_pdf(paper_id)`
取当前版本最新一次附加。版本退为非当前后，原 PDF 与正文仍保留供历史回查。
附加请求缺省版本的重放不会随当前版本漂移。提取前重新核对真实 PDF 字节与已登记 SHA。

`freeze_sample(paper_id, *, feed_id, pdf_sha256, reason, request_id)` 要求 experiment 根、
当前版本的 Feed 发现及当前 PDF 哈希一致；冻结 paper/version、Feed、PDF、理由与 UTC 时间。
`samples(paper_id)` 保留追加历史，换样另记，不覆盖旧样本。最新样本与当前 PDF 不符即拒绝。

### 公共提取与预算

`extract(paper_id, *, snapshot_id, parser) -> ExtractionView` 从已登记历史配置和当前 PDF
构造并保存 extraction StageInput；不接收裸指纹作为权威。
`CanonicalParser.preflight(ExtractionSemantics)` 在根锁和领取前完成外部诊断及模型核验，
失败不占预算；可返回独立 `PreparedParser`，服务对全部出口调用其 `close()`，
并在领取时保存其可选运行审计。旧 parser 返回 None 时仍调用原 convert。
`convert(pdf: bytes, semantics) -> ParserResult` 只接收 PDF 与 extraction 语义，
返回 canonical、可选审计 JSON、峰值与警告；不提供题名/DOI/摘要。
`ParserFailure(ExtractionFailure, peak_memory_bytes=0)` 表达受控失败。
生产 SDK、进程限额和模型文件核验由[Docling 执行器](docling-execution.md)提供；
Body 复用其准备对象，不在进程内加载 SDK。
规范化、自动质量和四角色定义见[规范正文](fulltext-extraction.md)。

同库 `backend × extraction_fingerprint` 最多两次尝试，跨论文、请求与重启共享；
同 fingerprint 至多一个成功。已有成功、永久失败或预算耗尽时返回原 `ExtractionView`，不再转换。
超时、资源耗尽、executor_error 与 outcome_unknown 消耗预算；只有剩余预算可重试。
无文本层为 `extraction_failed_no_text_layer`，文档转换失败/partial 为
`extraction_failed_quality_gate`，均对该指纹永久。转换未产出完整规范制品时
只有 extraction_failed + quality_absent，不伪造质量评估。
完整规范制品的自动失败保留精确 `QualityFailure`。转换计时从取得锁并领取后开始，
attempt 保存耗时/峰值；manifest 的转换测量不含后续发布耗时。
发布制品后，结算与唯一成功在同一短事务；提交失败不产生半条成功，已领取预算不退还。

`extraction(fingerprint)` 只读返回 backend、PDF SHA、尝试序号/时间/失败/资源、制品、
三元组、质量、永久失败及 remaining_attempts，不自动继续执行或回收失联者。
根级串行与中断规则见[提取配置](extraction-config.md#根级并发与等待)。

### 人工版式核查与同事务事实

`review_layout(identity, *, passed, checks, note, actor, request_id)` 独立追加记录，
绑定 `(extraction_fingerprint, reading_sha256, evidence_map_sha256)`；
checks 必须完整包含 `body_boundary/reading_order/sections/headers_footers/provenance/restricted_content`
六个 bool，passed 必须等于全部检查通过；说明、核查者与时间保留在业务记录中。
自动通过且人工通过才合成 `experiment_document_gate`；缺人工为 absent。
人工否决产生 `failed(layout_review)` 并对指纹永久；后来通过为 `layout_conflict`，
后来否决可继续追加。Body 不产生 formal_gate。
`ExtractionView` 拒绝 basis=failed 却无 failure，及其他 basis 携带 failure 的矛盾 DTO。

`facts_in_connection(connection, paper_id, *, identity=None, fingerprint=None, ordinary=False)`
在调用者同一个 SQLAlchemy Connection 中核对根、决定/上游来源、当前 PDF、提取和样本。
`facts(...)` 是只读事务包装。返回 `BodyFacts` 与全部有序受控 reasons，eligible 只表示
本服务所持有前置均满足；它不伪造最低元数据或完整 `READ_PREREQUISITES` 资格，
不代表 Read 领取、预算、执行准入或普通生产许可。Read 任务须在自身领取事务继续核验。
显式 identity 与已存三元组不符、PDF 换代或样本不符均拒绝；普通消费拒绝实验根及非正式质量。

### 恢复与日志

`validate_all()` 从数据库、历史配置和真实制品重算 PDF、决定引用、请求摘要、样本、
追加序号、StageInput、全库预算/唯一成功、自动质量、人工记录与 manifest 身份/资源闭包。
备份 verify 在完整副本上调用本入口；损坏为 `registration_invalid`，不调用 parser。
根锁不属于备份成员；冷进程无 extra 及原根屏蔽的恢复规则见[备份契约](backup-restore.md)。
`sink=None` 默认 NullSink；显式注入仅发送安全 `body` 事件及截短指纹，
内容与人工说明不进入日志，详见[日志契约](runtime-logging.md)。

## 错误与拒绝

`BodyError.reason` 为 `BodyReason` 闭集，异常只含受控中文指引，不附路径、PDF 或原异常。
主要拒绝包括 root_conflict/root_unknown、invalid_pdf/version_mismatch/pdf_absent、
request_conflict、source_requires_dedicated_path、screening_mismatch、sample_mismatch、
facts_changed、layout_conflict、unsafe_lock、corrupt_reference、database_failed。
事实查询还列出 decision_not_accepted、execution_source_unknown/test_execution_source、
extraction_absent/extraction_failed、quality_absent/quality_failed、ordinary_consumption_denied。
其余专用人工来源 blind_calibration/regular_review/metadata_abandonment/manual_read_request
一律拒绝并指向专用流程；不建立 read_requests。

## 不提供／不证明

产品 CLI、真实选样与版式核查、实验暴露清单及日报由 [B](../roadmap.md#module-b) 接线。
SDK 受限执行、Read 任务与分析、真实 Docling smoke 由 [Body](../roadmap.md#module-body)
其余边界承接；四刊正式质量、PDF 裁切与通用资源阈值由 [F](../roadmap.md#module-f) 验收。
本服务不调用 Read、不自动 accepted、不授予校准、自动队列或生产消费资格。
人工附加合成 PDF 的工程回归不证明真实 PDF 归属、Docling 保真、Pi live、完整 B 或 NAS。

## 相关

- [ADR-0043](../adr/0043-persist-body-prerequisites-before-stage-b.md)、
  [D1 覆盖与责任](../verification/issue-158-body-persistence-delivery.md)。
- [制品存储](artifact-store.md)、[资格](eligibility-visibility.md)、[Screening 任务](screening-tasks.md)。
- 依据：[#158](https://github.com/MeteoBoy4/PaperRadar/issues/158) 与
  [父规格最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6633241060)。
