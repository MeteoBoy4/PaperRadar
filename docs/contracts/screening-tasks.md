# Screening 任务 Contract

状态：A7-01 已冻结 D1–D4 并收紧权威 JSON 解析；A7-02（#78）已交付公共登记、
冻结输入回放、请求回执、a701 持久化和备份语义闭包；A7-03（#79）增加 a702 的
原子领取、两次预算、600 秒租约、失败结算、显式回收和 test 一次尝试驱动。
A7-04（#80）交付 boundary 权威接收、唯一制品、三值适用性和成功恢复闭包。
A7-05（#81）在同一接收链扩展 value 与历史同源上下文重建。
A7-06（#82）交付显式 retry、版本化共享查询和父链恢复闭包；
A7-07（#83）交付完整历史隔离恢复；A7-08（#84）注册独立必需 A7 组及可信终态。
本文规定验收范围，具体通过事实以同次原始证据、真实入口退出码和状态查询为准。
来源为 [#76 正文及全部评论](https://github.com/MeteoBoy4/PaperRadar/issues/76)，
[用户 D1–D4 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356409213)
优先；逐项对照与绑定台账见 [A7 requirements](../verification/a7-requirements.md)。

## 1. 服务边界与身份

公共 Screening 任务服务封闭支持 `boundary`、`value`；二者独立登记、领取和计预算。
value 不要求 boundary 成功，boundary 的 `out_of_scope` 不取消 value。
两阶段编排、业务 eligibility、metadata_ready、校准、每日配额、Pi/RPC、真实模型和
默认执行者都不在本批范围。单任务可领取不代表完整生产运行许可。

| 概念 | 身份 | 冻结或保留的依据 |
| --- | --- | --- |
| 预算范围 | 同库 `(paper_id, stage, fingerprint)` | 规范输入、首次上下文、至多一个筛选制品 |
| 任务代际 | 预算范围 + generation | 第 0 代由首个请求创建；每代最多两次 attempt；显式 retry 追加下一代 |
| 请求 | scheduled 的完整业务依据，或 manual/retry 的显式 request_id | 来源、调度日或 request_id、version/revision/snapshot；多个请求可共用任务 |
| attempt（尝试） | task_id + attempt_no | 领取时请求依据和当前论文依据、领取凭据、预算占用及结算事实 |

来源是请求的属性。scheduled/manual 均跟随最新代际，不能因日期、来源、版本 ID、
配置标签或进程变化重建第 0 代。A→B→A 回到 A 的原预算与筛选制品；跨 Paper 不共享
业务预算或筛选制品，A3 底层字节去重照旧。未来 merge/undo 的预算合并另行设计。

scheduled 身份包含 `(paper_id, stage, fingerprint, 调度日, version_id, revision_no,
snapshot_id)`；完整依据相同才是精确重放，同日书目修订不同会追加请求但共用任务。
调度日由调用方显式提供 ISO 日期，不从时钟猜测、不参与预算。manual/retry 的
request_id 同键不同规范内容报冲突；request_id、reason、actor 均为非空、无 HTML、
不超过 2048 UTF-8 字节的文本，actor 仅为未经认证的本地说明。retry ID 库级唯一。

## 2. 冻结输入与语言事实（D1）

登记只接收 Paper、阶段、明确已登记 snapshot 和请求审计依据，复用 PaperFacts
一致读映射及 A5 构造；不接收自由题名摘要或裸指纹。持久化独立期望 fingerprint、
A5 规范载荷原字节、格式和对应论文/配置依据。ID、日期、generation、语言标记不进入
A5 载荷，不改 A5 格式 1 或阶段指纹。

value 登记必须显式提供严格 `bool` 的 `original_title_is_zh`；通过既有
`StageInput.value_prediction_context(snapshot, original_title_is_zh=...)` 验证，
不新增语言检测器。缺值或非 bool 在登记时失败，不占 attempt。boundary 请求模型
禁止该字段，即使值为 null 也在登记时拒绝，不能等输出校验时才扣预算。
同 `(paper_id, value, fingerprint)` 首次登记冻结原语言事实和匹配 snapshot；后续
相反事实受控拒绝、不新增任务、不刷新预算。retry 必须继承原值，不能传新值更正。

**已知限制：同预算范围的误标暂无法纠正。原题名语言的生产来源尚未裁决，必须在产生
任何真实 value 任务之前另行裁决，最晚在 RPC 票或阶段 D。** 主题集合只从匹配冻结输入
的同库历史 snapshot 派生，不从当前 topics 文件取得。

## 3. 一致登记、领取与有限尝试（已交付）

登记/领取的映射可在事务外一致读取；进入 `BEGIN IMMEDIATE` 后必须经同一连接
比较不可变的当前 selection_id、version_id、最新 revision_no 与预读依据。变化则回滚并要求
重新登记，不能把另一连接看到的事实视为写事务锁定。配置快照不可变，可在事务外
加载并在事务内核对已登记。只开放 papers 的最小只读事务组合接口，不复制仲裁；入口延迟导出，保留既有
CLI 帮助的零外部 I/O 启动路径。

领取以请求回执为依据，用请求 snapshot 重建当前输入；缺项或指纹变化拒绝且不扣
预算。仅卷期/来源变化或跨版本文本相同、指纹不变均可领取。每次领取在同一短事务
占用 attempt、写凭据及租期，再在事务外执行。领取提交后即使尚未实际调用便崩溃，
也保守占预算。每个 attempt 驱动最多调用一次外部执行者；不宣称外部 exactly-once。

租约有效区间 `[claimed_at, expires_at)`，恰好到期可回收。采纳 #76 B4 建议：到期但
未结算时，原持有者仍可续租或提交；回收结算后旧凭据全部失效。续租设为 `now + D`，
D 固定为 600 秒、不进入配置语义；时钟统一注入严格 aware UTC datetime，
不直接读取系统时间、不启动后台心跳。
凭据为 `(task_id, attempt_no, token)`，attempt_no 即领取代数，不另设计数器。
回收一律结算 `outcome_unknown`，不假定执行者曾经运行或已经停止，不退还预算。
租期保存绝对 UTC；从另一台机器或较早时刻恢复后，副本的注入时钟可能使租约立即
过期或长期有效。默认接受这种偏差：它只改变结算时机，不退还、不额外扣除预算；
回收仍一律是 `outcome_unknown`，不能用时钟偏差重置次数。
只读查询不回收/续租；第二次 attempt 到期未结算显示 `lease_expired`、剩余 0，
回收后才进入失败终态。普通任务租约与 A4 继承 fd 的安装使用保护独立。
没有回收守护进程；强杀后的尝试保持未结算，时间到达后仅派生 `lease_expired`，
直到显式回收或下一次领取事务结算它。尚有预算也可能暂不可继续，不能把两次预算
解释为自动调度保证。

同代第一次失败仅余一次，第二次失败终态不随日期复活。失败类别封闭为
`output_invalid`（携 A1 安全类别/路径）、`model_mismatch`、`timeout`、`cancelled`、
`protocol_error`、`executor_error`、`outcome_unknown`；全部消费已领取预算。
服务 busy/引用损坏/非法调用不是模型失败；已领取但未结算者依租约恢复。
第二次尝试只消费冻结输入和脱敏失败说明，不携前次失败原文或会话。

## 4. 候选接收与筛选制品（D3；boundary/value 已交付）

外部执行者返回完整原始字节或封闭失败。服务统一调用现有 `validate_output`，不接受
`validated=true`、自由解析字典或第二份字段 Schema。原始 `str`/`bytes`/`bytearray`
的任意层重复键、NaN/Infinity、BOM、非 UTF-8、截断或非法 JSON 均报根 `$` 的
`invalid_json`；语法判定先于载荷字段和业务校验。合法前后空白保留，Mapping 保持
原路径。见[权威验证 Contract](screening-validation.md)。

成功用 A3 `model_success_response` 的 `payload` 角色逐字节保留原始成功响应，
结构结果由权威模型规范序列化，不拆第二套业务字段。预算范围内最多一个筛选制品，
精确提交重放幂等，不同候选竞争不能覆盖。提交核对未结算 attempt/凭据/冻结输入，
**不在提交事务核对当前论文事实**。过期已结算凭据不能写成功或失败，最多留下事务外
已发布的完整孤立制品。发布、业务提交与回包故障不能制造半成功或退还预算。

A7 执行来源封闭为 `executor_kind=test`。未来建议/校准消费者必须拒绝 test 制品。
执行者报告的 provider/model 与冻结配置矛盾即 `model_mismatch`；缺报告则记录未知。
provider request ID 与 token 未报告为 null，报告 0 保持 0；不预建金额/成本字段。
真实模型、settled、输出通道、Pi 供给/安装和隔离证明由后续 RPC 票承担。

value 与 boundary 共用领取、预算、候选提交、发布及唯一成功事务。value 的唯一
上下文重建顺序是加载预算首次历史 snapshot → A5 严格回放与投影核对 →
`StageInput.value_prediction_context(snapshot, original_title_is_zh=冻结事实)` →
A1 `validate_output("value_prediction", raw, context=...)`。提交和成功回读共用该验证
选择；恢复仍从同一预算基线取历史 snapshot/语言，不用新请求 snapshot 或当前文件
代替。语言不进 A5 载荷。中文原题名只允许 null 显示题名；其他原题名的非空显示题名
须满足 A1 文本规则。分数、可判断性、价值类型、未知/重复主题、重复 JSON 键或缺
必填字段等错误按 A1 类别和字段路径记 `output_invalid`，消费本次 attempt，失败原文
不保留。普通回执、查询与 repr 不显示价值预测、速览、理由或显示题名。

`load_success` 的 `SuccessContent.output` 为权威 `BoundaryOutput | ValuePredictionOutput`；
显式消费方须按类型区分，不能用 stage 标签跳过重新验证。该入口重验原始字节、
规范结构、提交摘要和冻结模型审计。`query_successes` 封闭支持两阶段，适用性均按 §5
派生；查询仍只返回安全回执。没有隐式两阶段编排或生产默认执行者。

## 5. 当前适用性完全派生（D2）

明确 snapshot S 下，把 Paper P 的当前修订重新映射得到 fingerprint F；同 Paper/
stage 的已接收筛选制品 fingerprint 等于 F 即当前，否则为 historical。映射失败为 undeterminable，携原 PaperReason（包括缺摘要、截断未知、配置未就绪、快照未登记），无
当前制品。版本 ID 改变但实际文本/配置指纹相同，制品直接适用；补卷期/来源不重跑。

当前/历史是查询视图，不是成功状态。不建结果使用依据表、再绑定 API 或绑定写入。
后续登记仅追加自己的 version/revision/snapshot 和缓存命中回执作为使用审计，不占
attempt；只读查询不要求先登记。更高 parser 删掉当前摘要时旧成功暂不适用，其他来源
补回相同文本后同制品重新适用，不改写 A6 仲裁或历史。此规则取代原 #76 故事 29/31、
决策 15–16、测试表“当前适用性”“缓存重新使用”的旧绑定语义，见 ADR-0031。

## 6. 显式 retry、共享查询与可见性（D4；服务已实现）

显式 retry 对当前输入的失败终态追加唯一后继，保留原终态；同 ID 精确重放返回原
回执，不同 ID 竞争返回已有后继，运行中/尚有预算/成功输入不得借 retry 开新预算。
过期未结算的第二次 attempt 可在同一写事务结算为未知后创建后继。

共享只读查询接收明确 snapshot，统一推导当前性、代际、attempt、剩余预算、租约、
终态及受控原因；当前 failures 仅列当前指纹最新代际的失败终态，历史仍可查询。
不得显示原始输入、成功字段/分数/理由/速览/中文题名、失败原文、Prompt/Profile 或
领取凭据。repr/异常/日志同样脱敏。输入映射失败保留 A6 PaperReason，输出失败保留
A1 类别/安全路径，TaskReason 只承载任务专属原因，不扩 storage/errors。

本批仅交付服务层 retry 与共享查询，**不交付 screening CLI、paper trace 组合、
相关 help/退出码验收**。原 #76 故事 23/33 的 CLI 部分、故事 39、决策 20–21 的
CLI 部分移至首张产生真实任务事实的 RPC/run-due 票。共享 calibration visibility
也未交付；本服务不能声称完整盲评隔离或产生生效筛选决定。

## 7. 完整性、备份与验收（随已交付事实递增）

完整性重建仅复用：历史 snapshot → `replay_stage_input(stored_bytes,
stored_fingerprint, snapshot=...)` → 同源 value context → `validate_output(raw)`
→ 与保存结构比较；核对请求论文依据、代际/attempt/租约/预算和成功引用。不要求每个
model_success_response 都有任务引用，不重哈希已由 A3 验证的 blob。

新 migration 从前一 revision 增量推进，只新增当前票实际消费的表；非空旧库与空库都测试。
backup format 保持 1，无新 manifest 字段或计数；head 前移后旧批次受控
`unsupported_revision`，旧库 `upgrade_required`，只显式升级、不在 verify 中迁移。
旧 revision 的批次须用匹配旧程序恢复，再显式 upgrade 恢复副本。支持范围由
`BACKUP_DATABASE_REVISION` 固定；即使 revision 相同，当前程序仍按当前 A1/A5
校验语义重验历史响应。规则收紧后，曾在旧程序通过的备份可能验证失败，不承诺
任意旧备份跨程序版本永远可验证。
任务 validate_all 钩子放在 PaperFacts 后、manifest 反查前，语义损坏沿用
`registration_invalid`，不新增 BackupReason，不修复源数据。

恢复不激活配置、不回收租约、不执行模型。显式继续仅使用恢复事实的剩余预算。
**两次上限仅对单一档案库连续历史成立；恢复较早备份会丢失其后 attempt，不能保证
跨备份回退的全局调用上限。** 非空异地恢复须证明全部输入、响应、retry 与未结算
历史可独立重建。A7 正式结论依赖同次 A1、完整 A2、A3、A5、A6；A4 仍为总门禁必需。
RPC、live、完整阶段 A 与原题名语言生产来源持续未验收。

## 8. A7-02 公共登记 API（已交付）

`paper_radar.screening_tasks.ScreeningTasks(database, data_root=None, *, clock=None)` 是唯一任务服务。
登记与输入回放不使用 `data_root`，不读来源文件或配置目录；boundary/value 成功的发布和显式读取使用该根，见 §10。
登记只接收 `register(mapping)`，请求 Pydantic 模型属于内部实现，不是第二个公共校验入口。
没有默认执行者；A7-02 登记切片只创建第 0 代，不占 attempt。A7-03 的时间相关方法
要求注入时钟；纯登记、回执、回放与 `validate_all()` 不依赖时钟。

| 方法 | 结果与范围 |
| --- | --- |
| `register(request)` | 追加或精确重放 `RequestReceipt`；只写登记事实 |
| `get_receipt(receipt_id)` | 只读返回登记时回执，不重新映射当前论文 |
| `receipts(paper_id)` | 按回执 ID 排序的安全请求历史；完整任务历史与当前失败由 §11 的 query 提供 |
| `load_input(receipt_id)` | 显式内部消费：从预算基线的历史 snapshot 严格回放 StageInput；载荷、snapshot、语言事实隐藏 repr |
| `validate_all()` | 只读核验登记关系、原始字节/指纹/投影、历史论文依据及请求身份；不升级、不修复、不执行 |

请求共同字段为严格字符串 `paper_id`、`snapshot_id`、`stage` 和 `source`。stage 封闭为
boundary/value，source 当前为 scheduled/manual。scheduled 必须有严格 ISO `scheduled_day`
（`YYYY-MM-DD`），其 request_id/reason/actor 均为空；manual 必须有 request_id/reason/actor，
scheduled_day 为空。value 的 `original_title_is_zh` 必须由既有 StageInput 上下文权威接收，
boundary 禁该字段。除此之外的字段一律拒绝，异常不回显调用方字段名/值。

request_id、reason、actor 检查非空、无 HTML、可 UTF-8 编码及最多 2048 字节；合法文本
原样保存，不静默 trim 后改变精确重放身份。request_id 在整个任务请求表唯一，与 A6
版本内的人工修正 ID 分开；回执不展示这些自由文本。

调用方请求的规范 UTF-8 JSON（键排序、无外围空白、非 ASCII 原样编码）单独哈希。
manual 精确重放先查全库 request_id 并核对该哈希，**先于当前论文映射**；当前论文后来
变化/缺项也返回原回执。同 ID 不同内容返回 request_conflict。scheduled 的回执 ID 是
source/paper/stage/fingerprint/day/version/revision/snapshot 的规范 JSON SHA-256；因此
同日补卷期产生新请求、同任务，不发生旧请求身份冲突。两种来源的新请求均关联已有预算
范围；没有重复第 0 代，也不跨 Paper 复用业务任务。

回执格式 1 的固定安全字段：receipt_id、task_id、budget_id、paper_id、stage、fingerprint、
generation、source、version_id、revision_no、snapshot_id、scheduled_day、selection_id、
format_version。manual 的回执 ID 由 source/request_id 的规范身份摘要派生；与用户自由
request_id 是两个字段。selection_id 已唯一标识不可变选择事件，无需复制未在 A6 公共
RevisionView 暴露的 event_no。真实进程 CAS 用例证明事务外预读后任意修订变化会受控
回滚 facts_changed，调用方重新登记后仍按相同语义指纹共用预算。

新增四表为 screening_inputs（BLOB 载荷按指纹去重）、screening_budgets（首次 snapshot、
语言事实和论文依据）、screening_tasks（预算范围内第 0 代）、screening_requests（全库 ID、
内容摘要和独立论文/配置依据）。这四表由历史 migration a701_screening_registration 建立；
当前 head 为 a704_screening_retry；a702 历史切片见下一节，成功接收见 §10，retry 迁移见 §11。A5 格式、artifact kind、
backup format/manifest/counts 均保持原值。新程序不接受旧 revision 的备份批次，
须用匹配程序恢复后显式升级；普通旧库准确报 upgrade_required。

登记任务原因目录版本 1：invalid_request、invalid_context、context_conflict、request_conflict、
request_not_found、facts_changed、corrupt_reference、database_busy，各有中文下一步说明。
语言类型错误同时携 A5 原始 BuildReason/InputField；论文映射失败原样抛 PaperError，
缺库/旧库保留 StorageError，均不伪装成模型失败。登记失败只会回滚登记，不占预算。

登记事实子闭包逐条回放冻结输入和每个请求的历史配置/修订，核对论文归属、选择身份、
原始请求内容摘要、回执身份及第 0 代唯一关系。备份 hook 在 PaperFacts 后、manifest
反查前调用，受控语义损坏为 registration_invalid。跨进程恢复仅需副本和已登记材料，
不访问原数据/配置目录。§9–12 的尝试、成功、retry 和恢复校验已纳入此同一闭包。

任务状态词表预先固定为 ready、running、lease_expired、retryable、failed、succeeded，
分别表示待领取、已领取未到期、到期未结算、失败但尚有预算、失败终态、成功；A7-02
当时只登记 ready；A7-03 实现前五项，A7-04/05 已交付两阶段 succeeded。
当前六态均为任务派生状态，不构成 Paper 主状态或完整 eligibility。

## 9. A7-03 领取、租约与失败 API（已交付）

服务使用注入的 UTC 时钟，未配置、非 datetime、naive 或非 UTC 值受控拒绝。
时间相关操作使用同一注入时钟；没有系统时钟默认值。普通错误、repr 与状态不携带
领取凭据、续租句柄、输入、异常文本或 traceback。

| 方法 | 结果与范围 |
| --- | --- |
| `claim(receipt_id)` | 以请求回执领取新 attempt，原子占一次预算；返回持有者专用 Claim，秘密字段隐藏 repr |
| `renew(renewal_handle)` | 仅持有者可用的不透明字符串句柄；未结算且匹配即设 expires_at=now+600 秒，不追加心跳历史 |
| `fail(claim, report)` | 原子追加封闭失败结算，返回安全 FailureReceipt；同凭据同内容精确重放返回原回执，内容不同拒绝 |
| `reclaim(receipt_id)` | 显式结算已到期 attempt 为 outcome_unknown；不到期不结算、不退预算 |
| `status(receipt_id)` | 只读推导 TaskStatus，包括 used_attempts/remaining_attempts、状态与 last_failure；不回收、不创建事实，不是 A7-06 版本化查询序列化 |
| `run_once(receipt_id, executor)` | 先校验可调用执行者、冻结输入和显式制品根的发布前置条件，再持久化领取并至多调用一次 test 执行边界；接收失败报告或 boundary/value 原始成功候选 |

领取先用请求自身 snapshot 映射当前 Paper，只比较阶段指纹；历史 version/revision 与
当前不同本身不阻止领取。写事务使用同连接复核本次预读的 version/revision/selection，
不一致报 facts_changed 且不新增 attempt。attempt 同时保存请求 receipt_id 与领取时的
当前依据，绝不覆盖请求登记依据。领取提交前失败回滚，提交后即使未调用执行者也占预算。
`run_once` 无论预期返回失败还是成功都必须提供 `data_root`；不可调用 executor 返回
`invalid_request`，缺根返回 `data_root_required`，制品路径/权限错误沿用 ArtifactError。
制品库 `prepare_publish` 复用受控目录规则并检查临时写入，不发布或登记占位制品；
它不能保证领取后 I/O 仍成功，后续不可预知故障仍保守占预算。纯登记、只读与手动
`claim` 不要求制品根。

执行者只取得冻结 StageInput、由封闭失败类别生成的必要安全修正说明和续租句柄；
不取得数据库连接、PaperFacts、完整 FrozenInput/snapshot 或前次原始失败字节。
FailureReport 仅有 kind；修正说明从受控类别选择固定中文，不接收调用方自由文本。
执行边界封闭为 test；执行者可报告 timeout、cancelled、protocol_error、executor_error，
真实捕获异常结算 executor_error；执行者不能报告 outcome_unknown 代替回收，也不能
声明 output_invalid/model_mismatch 或已验证成功。后两种失败仅由权威接收服务形成。
直接 fail 的不支持报告返回 invalid_failure；run_once 中不支持的执行者返回值
（自由字典或自称已验证的形状）结算为 protocol_error，不能绕过权威接收。
调用是否发生、token 和用量未报告时保持未知，不把 attempt 占用解释为实际模型调用。

fencing 使用 task_id/attempt_no/领取凭据，不重新领取同一 attempt、不另造领取计数器。
数据库只保存领取凭据和续租句柄的 SHA-256 摘要，原始能力字符串只交给持有者。
失败重放先识别同凭据同结算内容，再判断持有者权限；重放不改变结算时间、当前租期
或预算。回收结算的旧凭据不能伪装成持有者失败重放，也不能影响后续 attempt。
过期但未结算的持有者可续租或提交，renew/fail/reclaim 的竞争由数据库短事务串行化。

历史 head a702_screening_attempts 新增实际消费的 screening_attempts（不可变领取与
预算事实）、screening_leases（当前到期投影）与 screening_failures（追加失败结算）；
不预建成功、retry 或未来成本字段。迁移从非空 a701 登记库前进。只读完整性钩子继续
复用已有 backup 接线，核对最多两次、连续序号、同任务请求、两套历史依据同指纹、
凭据/租约归属、严格 UTC 时间和结算一致性；恢复完整保留已占预算及租约，不自动回收。

A7-03 在原因目录版本 1 追加 invalid_clock、task_running、budget_exhausted、
invalid_credential、settlement_conflict、invalid_failure，均有固定中文下一步说明。
Claim 公开 task_id、attempt_no、receipt_id、claimed_at、expires_at 及领取时
version_id/revision_no/selection_id，另有隐藏 repr 的 credential、renewal_handle；
FailureReceipt 仅有 task_id、attempt_no、kind、origin 与 settled_at，不携失败原文。


## 10. A7-04/05 原始候选接收与派生查询（已交付）

公共 `SuccessCandidate(raw_response, executor_kind="test", reported_provider=None,
reported_model=None, provider_request_id=None, input_tokens=None, output_tokens=None)`
只接受严格 bytes；不接收已解析模型、自由字典或 validated 标记。所有审计字段隐藏 repr。
执行来源仅支持严格字符串 test，provider/model/request ID 为可空非空 UTF-8 字符串
（最多 2048 字节）；token 为可空非负严格整数，bool 非整数。未报告的字段保留 NULL，
报告 0 保持 0。不另设 token 业务上限；运行时不能规范序列化的审计受控拒绝。
run_once 收到非法候选协议形状时结算 protocol_error；直接非法调用
报 invalid_candidate。provider/model 与预算首次冻结 snapshot 的 screening 槽矛盾时
结算 model_mismatch，占用当次预算。A7 test 制品不得由生产建议或校准消费者接收。

| 方法 | 结果与范围 |
| --- | --- |
| `submit(claim, candidate)` | 权威校验 boundary/value 原始字节；合法返回 SuccessReceipt，校验/模型失败返回 FailureReceipt |
| `run_once(receipt_id, executor)` | 沿用一次尝试驱动，接受 FailureReport 或 SuccessCandidate；没有生产执行者 |
| `load_success(success_id)` | 显式内部消费 SuccessContent：原始成功字节、A1 权威 BoundaryOutput 或 ValuePredictionOutput、可空审计；敏感内容隐藏 repr |
| `query_successes(paper_id=..., stage=..., snapshot_id=...)` | stage 只接受 boundary/value；只读安全 SuccessView 序列，含成功回执、三值适用性及可空 PaperReason，不含判断/理由/raw |

SuccessReceipt 固定为 success_id、task_id、attempt_no、artifact_id、fingerprint、stage、
executor_kind=test、settled_at。FailureReceipt 追加安全 issues；只持久化 A1 原 category/location，
回放为受控说明，不保存失败全文或自由指导文本。第二次执行只取得封闭失败说明及 A1
安全类别/路径。请求格式 1 追加 nullable cached_success_id：只在本次登记时命中已有
同预算成功才保存 ID；旧请求原来未命中的精确重放永远不被后来成功改写。
实时 status/query 与不可变请求回执分别表达当前事实和登记当时事实。

提交首先在只读事务验证持有者身份与既有结算。明确已失败/回收的旧凭据先拒绝，不发布
新文件；同原始字节和审计的精确提交直接返回原回执。成功候选经唯一 A1 校验后，
在业务写事务外以 A3 payload 单角色发布原始响应；随后短 BEGIN IMMEDIATE 重新验证
身份并原子写唯一成功。精确身份包含原始字节 SHA-256 与规范审计，空白不同即不同请求。
不检查当前租约是否已到期，不在提交事务映射/比较当前论文。竞争者先回收时发布方只
能留下完整未引用 model_success_response；不删除或改写已发布制品。不允许同 attempt
同时成功失败，claim/renew/fail/reclaim/status 及完整性共享此终局判断，成功不退预算。
成功输入后续领取报 already_succeeded，不创建下一 attempt。

query_successes 复用 PaperFacts 的独立只读一致映射视图，随后读取不可变成功事实；
允许相对并发论文/任务提交滞后，不声称映射读与任务读取属于同一个 SQLite 快照。
指纹相等 current，映射成功且不同 historical，映射失败 undeterminable+PaperReason。
版本切换同文本、书目补全或 Read/期刊配置不改相应阶段指纹时仍为 current；parser
删除摘要暂不可判定，其他来源补回同文本后自然重新适用，无绑定写入。

历史 head a703_screening_success 从 a702 增量增加 screening_successes（每预算唯一、
每 attempt 唯一、A3 原响应引用、单列规范权威结构、规范审计与精确提交身份）；
screening_requests 增加登记时命中引用，screening_failures 增加安全 issues/候选提交
身份与审计。SQLite 原位追加可空 REFERENCES 列，保留既有请求 CHECK 和所有历史。
不新增 ArtifactRecord metadata、artifact kind/role、备份字段/计数或金额字段。

validate_all 沿用同一备份钩子，重验原始响应、权威结构、冻结输入和期望模型、执行
来源、UTC 成功时间、终局排他和缓存归属；失败细节只允许权威 Schema 字段路径和
封闭类别。语义损坏仍映 registration_invalid。完整未引用 model_success_response
合法；备份恢复保留成功、旧请求当时回执、失败和未结算预算，不触发执行。
新增任务原因保持目录版本 1：invalid_candidate、already_succeeded、success_not_found、
data_root_required，各有固定中文下一步说明；缺显式制品根时不猜 cwd。


## 11. A7-06 显式 retry 与共享查询（已交付）

`retry(raw_request) -> RequestReceipt` 只登记后继，不调用执行者。严格请求字段为
paper_id、stage（boundary/value）、snapshot_id、parent_task_id、request_id、reason、actor。
目标必须显式指定任务 UUID；后三项沿用非空、无 HTML、最多 2048 UTF-8 字节的原字节规则。
请求不能携带 source、scheduled_day、语言标记或输入载荷。语言和实际执行输入继承
预算首次冻结上下文；请求 snapshot 只用于核对当前阶段指纹，不能切换输入。

全库 request_id 精确重放先于当前映射，返回原持久化回执；不同内容报 request_conflict，
manual/retry 也不能共用同 ID。新请求先映射当前输入，映射失败保留原 PaperReason，
优先于非最新、已有后继或非失败终态。映射成功后，写事务复核当前修订与目标预算的
Paper/阶段/指纹，随后核验已有后继、唯一成功及最新代际。已有后继报 already_retried，
安全的 TaskError.successor_task_id 给出已有任务 ID，后继后来成功也保留该说明；
无后继但输入已经成功则报 already_succeeded，其他新请求不得借旧代际再开预算。
同 ID 精确重放即使后继已再次 retry，仍返回该 ID 原回执。

只有失败终态可以追加 generation+1，父任务不覆盖；每代重新有至多两次尝试。
ready、running、retryable 与第一次 lease_expired 报 not_failed，并保持原事实。
第二次 lease_expired 在同一 BEGIN IMMEDIATE 内先结算 outcome_unknown，再创建后继及
请求；中断一起回滚。成功、回收、retry 写事务串行化，要么成功并拒绝 retry，要么保留
失败及唯一后继并拒绝旧凭据的迟到成功。scheduled/manual 新请求跟随最新已存在代际，
旧请求的精确重放保持原样。

`query(paper_id=..., stage=..., snapshot_id=...) -> TaskQueryResult` 是共享只读边界。
固定 kind=task_query_result、format_version=1；不增加冻结契约导出。注入 UTC 时钟用于
只读状态派生；未注入时报 invalid_clock。字段如下：

| 层次 | 安全字段 |
| --- | --- |
| 结果 | paper_id、stage、明确 snapshot_id、current_fingerprint、可空 PaperReason、budgets、current_failures |
| 预算 | budget_id、fingerprint、current/historical/undeterminable、可空 reason、latest_generation、latest_task_id、完整 tasks |
| 任务 | task_id、budget_id、generation、parent_task_id、六态 state、used_attempts/remaining_attempts、requests、attempts |
| 请求 | 既有 RequestReceipt v1；登记时 cached_success_id 不随查询重写 |
| 尝试 | attempt_no、receipt_id、version_id/revision_no/selection_id、claimed_at/expires_at、安全 FailureReceipt 或 success_id |

current_failures 只包含当前映射指纹预算的最新代际且 state=failed 的任务；第一次失败
仍为 retryable，第二次过期未结算仍为 lease_expired，旧指纹失败保留在历史中。缺项或配置
不可映射时为 undeterminable+原 PaperReason，不误写 historical。此查询不表示完整业务
eligibility，不创建 pending/denied、建议或决定。映射和任务读取分别使用只读一致视图，
允许相对并发论文变更滞后，和 query_successes 一致。查询不结算、不续租、不写数据库。

共享查询不返回 request_id、自由 reason/actor、语言标记、Profile/Prompt、输入载荷、
响应正文、用量审计或 fencing token/摘要。A1 输出失败仅沿用封闭类别、安全字段路径和
固定中文说明。新增任务原因在目录版本 1 内为 task_not_found、already_retried、not_latest、
not_failed，各有固定中文下一步。

a704_screening_retry 是当前 head：tasks 追加可空 parent_task_id 外键及唯一索引，
requests.source/audit CHECK 扩大到 retry。由于 requests.cached_success_id→successes→
attempts.receipt_id→requests 存在真实 FK 环，迁移在单个写事务内保存五表闭包、暂置空
缓存引用、依子到父清空重建、恢复原行及缓存引用，全程 foreign_keys=ON。旧 a701–a703
源码不变。非空成功/缓存、失败审计、在途事实的迁移与 DDL/恢复/版本戳故障及强杀
均须回滚旧 DDL/行；恢复后继续保留原 CHECK、UNIQUE、FK。

validate_all 重验每预算连续代际、同预算唯一父链、父真实两次失败、每代请求、唯一
retry 请求及其目标/规范摘要、首次预算依据。备份 format/manifest/counts 不变；恢复
保留父链与预算，不回收或执行。完整组合恢复由 #83 交付；独立 A7 验收由 #84 注册。

## 12. A7-07 隔离完整历史恢复（已交付）

公共服务在同一真实 WAL 库产生两篇 Paper 的 boundary/value 成功、耗尽失败、retry
父链和到期未结算 attempt；当前与历史制品共存。新进程在原数据/配置树及其改名
位置均被阻断时执行 restore，搬迁恢复根并阻断备份位置后，仅从副本重建冻结输入、
历史 snapshot/语言上下文、请求依据、每代 attempt/lease、原始响应和权威结构。
恢复及完整只读查询保持目录字节与数据库逻辑事实不变；不会激活配置、回收或调用执行者。

显式 upgrade 后才在测试中继续工作库：旧回执/精确 retry 重放仍属于原代际，新的
scheduled/manual 请求跟随唯一后继；到期 attempt 回收为未知，剩余一次仅调用一次。
耗尽任务拒绝领取，成功缓存命中不调用执行者，value 成功同样拒绝 retry。同文本正式版
替换预印本仍适用，更高 parser 删除摘要后为 undeterminable，其他来源补回同文本后
原制品自然恢复 current；这些查询不写结果再绑定或新增 attempt。

备份负例复用已有载荷/投影/语言/响应和 retry 校验，补齐合法 FK 的请求错属、序号
缺口、前次未结算、租期错属和成功/失败双终局；外层重算哈希仍为 registration_invalid，
不改批次、不发布目标。attempt_no=3 与重复序号分别由既有 CHECK/主键拒绝，测试不
关闭约束制造伪合法结构。完整未引用 model_success_response 仍允许。


## 13. A7-08 独立验收与可信终态（已交付）

标准 `check-offline` 在一次固定六检查后发布必需 `.a7.json`，格式 1，
parent_issue=76、issue=84。直接前置精确为同次 A1、完整 A2、A3、A5、A6；
A4 继续为整体必需组。结论独立核对各前置的范围、格式、issue、严格 verified 状态、
同次身份及 evidence/receipt/前置文件的实际字节链接；只看登记顺序或历史 passed 不足。

结论固定实际 migration head `a704_screening_retry`，从生产读取任务、原因目录、
共享查询、boundary/value 输入和 backup 的格式 1；TaskQueryResult 的真实格式默认值
同样参与核验。固定范围包括 #77 的权威 validation.py 与 93 例严格 JSON、新增任务
代码/fixtures/测试及故障/隔离读者，不将实测数回填为预期。A7 的逐项能力和材料映射见
[A7 requirements](../verification/a7-requirements.md#a7-08--84-独立验收与可信终态)。
`task_query_result`、`task_reason_catalog` 不新增到四份 Frozen Contract；A7 scope 不自绑。

真实 pytest 插件记录固定模块的收集、通过、失败、跳过、取消选择和未完成计数。
缺回执、少执行、skip、deselect、collect-only、非法整数或错误回执均不能通过。
源码/lockfile/代码/工作树漂移、缺前置、前置失败、组失败及中断也不能通过。
控制方最后发布绑定全部组的 terminal；缺失或篡改终态不能证明成功。当前正常运行
九份主要文件加 pytest/terminal 共十一份 JSON。实际入口 exit0 后，状态查询还须显示
passed/verified 且 applicability=same；它不写回历史或补造新证据。

`rpc_verified`、`live_verified`、`stage_a_verified` 恒 false。not_assessed 明列
RPC/Pi、真实调用用量/成本、原题名语言生产来源、metadata_ready/完整 eligibility、
每日配额、两阶段编排、建议/决定、校准可见性、reuse/extraction/Read 任务、merge 预算、
CLI、NAS、完整阶段 A 与 live。本验收不授予 test 筛选制品生产消费或校准资格。
