# 显式 Read 任务与分析

## 用途与范围

`paper_radar.read_tasks.ReadTasks(database, data_root, *, clock=None, sink=None)`
提供已有 accepted 论文的显式单篇登记、领取、有限尝试、接收、retry 和历史查询。
它消费 Body 的持久三元组、历史 extraction 配方与明确配置快照，复用唯一的 Read Schema
及 v2 接收器。默认 NullSink；构造不调用模型或加载 Docling。

## 规则

### 登记与历史输入

`register(paper_id, *, snapshot_id, extraction_fingerprint, request_id,
output_language='zh', label='manual')` 返回 ReadTask。
同 request_id 的完整登记参数与原请求哈希相同则只读返回既有任务，后来的资格变化
不阻止此回执重放；异参同 ID 返回 request_conflict，先于输入重建和当前资格核验。
回执重放不登记新事实、不领取或补充预算。新 request_id 仍按当前事实核验。
extraction_fingerprint 只用来定位已登记 Body 输入；artifact、reading/evidence 哈希和
expected_identity 均取持久记录，不能由调用方提交投影或裸指纹自证。
`prepare(task_id)` 返回首次预算配置重建的 PreparedReadInput；
`prepare_correction(task_id)` 返回安全修正或 None。两者只读。
`prepare_execution(task_id, *, audit_snapshot_id=None)` 供 Pi 组合只读加载，返回未提前拒绝的
完整帧预算，以保证准入先于预算；明确审计快照必须在该任务的登记事实中，Read 投影须与预算首次相同。
预算语义仍取首次快照，不使用当前 settings。

预算主体为同库 `(paper, read, fingerprint)`，每个代际最多两次领取。
同输入重复请求、A→B→A、重启、用途或来源标签均回到原预算；标签不进入指纹。
新配置只在显式 register 时构造新输入，不扫描或重跑已有分析。
语言是独立输入。当前性与配置两轴由下述[展示查询](#展示查询与两轴)消费。

新登记及领取都在短写事务内通过 BodyService.facts_in_connection 重新加载 accepted、
决定引用的历史上游成功来源、当前 PDF/正文/质量、根用途和实验样本。
JGRMetadata.facts_in_connection 在同 Connection 读取真实 metadata 请求、路线结算、
agency 与当前字段，缺失保持 unknown；不把题名/摘要存在当路线完成。
完整 READ_PREREQUISITES 经共享 eligibility 计算；不建立 manual_read_request 或自动名额。
PDF 的制品登记和真实字节也在该 Connection 核验。上下文重建和完整帧最坏修正预算
在领取之前完成；不可预见的文件或数据库损坏仍安全拒绝。

### 领取与所有权

`claim(task_id, *, preclaim=None)` 返回 ReadHandle；包含真实本代 ordinal、token、
600 秒截止时间、历史 CallDescription 和安全 correction。preclaim 在领取短事务内取得
最新修正，拒绝时没有 attempt。实际模型运行在事务外。每次领取另存当时decision/root/PDF/sample/质量核查/上游来源及
metadata请求与明确历史修订的引用；历史验证只重放这些依据，来源 acquisition 的结果
修订不能晚于所引修订，不拿后来的当前资格替换。
`renew(handle)` 只允许未过期持有者追加续租，截止时间为续租时刻加 600 秒。
`fail(handle, failure)` 结算封闭执行失败；output_invalid 只能由权威接收产生，
outcome_unknown 只能由回收产生。

过期不退款，也不在只读查询或下一次 claim 自动结算。`reclaim(task_id)` 显式追加
outcome_unknown，旧 token 失权；最后一次过期回收后该代失败。
KeyboardInterrupt/SystemExit 透传并保留已花费但未结算的租约。
`retry(task_id, *, request_id, reason, actor)` 只允许当前失败终态建立唯一后继；
重复父边/请求幂等，原因与操作者保留，成功或运行中不能重开预算。新代 ordinal 从 1 开始。

### 外部执行与串行资源

`run_once(task_id, executor)` 的 test 执行器接收 ReadHandle，只能返回原始 bytes；
`submit_test(handle, raw)` 强制保存 test 来源，没有 executor_kind 或生产审计参数。
未知执行异常结算 executor_error，中断不伪造失败。

`read_tasks.execution.execution_resource(data_root)` 是本机同根 Read 的独占等待资源，
载体 `.body-read.lock`，等待发生在领取之前；run_once 自动持有它。
专用 `run_pi_once(task_id, executor, *, preclaim=None)` 使用独立 PiReadCandidate/PiReadFailure，
由 Pi 执行组合在认证和领取前取得该资源，并持有到结算与进程回收完成。
低层 claim/submit 本身不持有长时间资源锁。Docling 的独立锁含义不变；
B 的跨阶段调度与自动任务仍须遵守规格资源纪律。

PiReadCandidate 没有可变来源字段。专用端口核验严格 PiRpcAudit、持久 supply/install
引用、历史 adapter/protocol/channel/provider 和实际报告模型；模型不符为 model_mismatch。
审计形状和引用不证明实际执行；Pi 组合另行提供准入、真实独立会话和进程组回收。
本服务不授予 EXP-2 现场准入，test 端口不能提交 PiReadCandidate。
PiReadFailure 仅传递封闭执行失败；不允许调用方声明 output_invalid 或 outcome_unknown。
新的 Pi 组合记录另保留 audit_snapshot_id，回放核对该任务登记和历史投影；PiRpcAudit 的
严格格式保持不变。既有无该字段的审计继续按首次配置验证，不迁移历史字节。
实际启动、准入先后与日志范围见[单篇执行组合](read-execution.md)。

### 权威接收与原子保存

完整原始候选调用 validate_read_output_v2；序号重新读取持久 attempt，不取候选或执行器声明。
首次坏指针为 output_invalid，下一次修正唯一使用 build_read_correction 与共享 read_limits。
末次丢弃、评分理由永不降级、Schema 闭集与全空下限见[接收规则](read-validation.md)。

合法成功原子保存 outcome、唯一 analysis、接受输出、原始候选制品、诊断/警告/丢弃清单、
三规则版本、策略/真实序号、配置/输入、执行来源审计和 evidence 成员引用。
制品先完整发布，事务故障可留下未引用制品，但没有半条分析；已领取次数不退。
相同 token、原始字节与审计的精确提交幂等，竞争候选不能覆盖。

### 只读回查与恢复

`task`、`history(paper_id)` 返回失败/尝试/租约和全部代际；retry 原因/操作者不进 repr。
`analysis_ids(paper_id)` 按成功事务追加顺序返回 ID，`analysis_papers()` 返回有成功分析的论文。
`analysis(id)`、`analyses(paper_id)` 是低层历史核验接口，返回候选、输出、来源、根用途、质量、规则和丢弃标记；
`evidence(analysis_id, evidence_id)` 仅回查该分析引用的持久正文源切片。
分析读取重新按已记接收版本验证。ordinary=True 同时拒绝实验根、test 来源和非 formal 质量；
上游成功来源与 Read 自身来源分别保留，不互相授权。

`validate_all()` 校验代际链、连续 ordinal、租约/续租/结算、历史输入和候选/evidence 闭包，
以候选与持久 Context、策略、真实序号重算输出/丢弃及支持的诊断策略。
v1 历史使用冻结 v1 接收器，保留原接收记录；不追溯生成旧失败分析。
未知证据规则为 unsupported_rule_version；已支持版本重算不符为 registration_invalid。
未知数值/限制警告策略保留记录，只核对仍支持的部分，不声称重算等价。
备份和 restore 传播这些原因；冷进程不需要 extra、原根、settings 或配置激活，
不回收租约、不调用模型、不修改历史。数据库 head 见[备份契约](backup-restore.md)。

### 展示查询与两轴

`paper_radar.read_queries.ReadQueries(database, data_root)` 提供安全只读展示：

- `current(paper_id, *, snapshot_id=None, ordinary=False)` 返回 CurrentRead。
- `analysis(analysis_id, *, snapshot_id=None, ordinary=False)` 返回 AnalysisView；
  `history(paper_id, ...)` 按成功事务追加顺序返回全部 AnalysisView。
- `old_configurations(paper_ids=None, *, snapshot_id=None, ordinary=False)` 仅列出当前
  正文上每种语言的当前分析中配置为 old 的条目。省略 paper_ids 时查询全部有分析的论文。
- `evidence(analysis_id, evidence_id, *, ordinary=False)` 只回放保留条目实际引用的合法源切片。

正文轴不读取配置：沿版本表的当前版本、该版本最新一次显式 PDF 附加选择、该 PDF
唯一成功提取的正文三元组判断 current/historical/undeterminable。没有 PDF、没有成功提取
或同 PDF 有多个不同成功三元组均不能猜测当前正文；CurrentRead.state 为 undeterminable，
identity_reason 分别为 pdf_absent/extraction_absent/ambiguous_extractions。
后者等待显式正文选择能力，不能按最新配置或任意传入指纹选取；产品责任见路线图 B/F。
同一依据同时进入 Body 当前资格装配：不能唯一确定时新登记/领取带 facts_changed 拒绝。
历史 claim 引用核验保持独立，歧义、后来决定/样本/元数据/质量变化不抹除合法历史。

正文可判定但没有成功分析时 state 为 no_analysis；有成功分析为 available。每个
paper/正文三元组/输出语言选最后成功提交，zh/en 并列；任务序号、候选时间和 wall-clock
时间不替代提交序。相同指纹重复登记或相同提交幂等回放不改变最后成功位置；显式新指纹
成功才替换该正文/语言的当前分析，新任务登记或失败不替换。PDF 更换与当前版本选择改变
正文轴；volume/pages 等书目补全不改变它。换回旧 PDF 可重新命中其保留的正文/分析。

配置轴只比较调用方明确给出的、同库可经 load_config_snapshot 核对的历史快照。
不读取 settings、不选择最新快照、不接收调用方自证的投影 ID。双方 Read 均 ready 后，
compare_config_snapshots 的 Read 投影相同为 current、不同为 old；缺省、未就绪、缺失
或不可核对均为 unknown。其他 Screening 配置或仅版本标签变化而 Read 语义相同仍为 current。
变化类别闭集是 profile/model/prompt/contract/adapter/chunking；不输出 Profile 或 Prompt。
unknown 不属于 old，不进入旧配置列表。配置变旧不使正文分析失效、不登记任务、不授予
重跑资格、不刷新预算。当前支持的版本保持原语义，查询不创设未来 Contract/chunking 版本。

所有展示入口先实际调用共享 visibility（目前隐藏集合为空）。默认是带明确 test/pi_rpc、
根用途与当前质量标记的历史/实验回查；ordinary=True 拒绝实验/unknown 根，分析消费还
拒绝本次 Read 的 test 来源及非 formal 质量；上游来源不能代替 Read 自身来源。
AnalysisView 只含安全标识、两轴及受控原因、来源/质量、接受后的输出、has_discards、
main_findings/reusable_points/key_limitations 的逐类别丢弃条数、restricted_content_warning。
受限内容的原有警告保留在 output.degraded_content_warnings，不声称已人工核对。
它不透传低层 ReadAnalysis.raw_candidate、候选制品、执行审计、丢弃原文或坏 ID。
旧配置列表仅含 paper_id/analysis_id/output_language/changed_components；证据回查不复活
整条被丢弃项，即使该项中另一个引用本身有效。

数据库查询使用 mode=ro 连接，只从已有持久事实计算，不建投影缓存、不回收租约、
不写决定、不消费预算、不导入 SDK/模型或调用执行器。恢复后使用同一查询与规则。
B/H 负责报告文案与显著警告，Body 没有日报或产品 CLI。

## 错误与拒绝

ReadTaskError.reason 为封闭 ReadReason；前置拒绝的 reasons 保留共享资格或 Body 原因。
常见原因：prerequisites_failed、read_input_over_budget、task_running、budget_exhausted、
invalid_credential、settlement_conflict、not_failed、request_conflict、corrupt_reference、
unsupported_rule_version。输入/Context/配置/存储组件的受控错误保持其原边界，均不等同模型失败。

## 不提供／不证明

没有产品 CLI、自动队列、每日 quota、read_requests、pending/denied 原子 accepted、
通用 map/reduce、正式校准或真实 Pi/Docling 验收。真实产品与现场责任见[路线图](../roadmap.md)。

## 相关

依据：[#161](https://github.com/MeteoBoy4/PaperRadar/issues/161)、[#155 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155)。
[正文前置](body-persistence.md)、[Read 输入](stage-inputs.md)、[备份恢复](backup-restore.md)、
[资格](eligibility-visibility.md)、[日志](runtime-logging.md)、[ADR-0045](../adr/0045-persist-explicit-read-generations.md)。
