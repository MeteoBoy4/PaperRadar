# Screening 任务 Contract

## 用途与范围

本 Contract 定义 Screening 服务层的登记、冻结输入、有限尝试、候选接收、显式 retry、
安全查询与恢复边界，不定义生产调度或筛选决定。

<a id="a8-调用描述与接线边界85-d1d4p3"></a>

### RPC 组合前置

与 RPC 组合时，调用方在 `run_once` 前用 `get_receipt`、`load_input` 和历史配置只读
构造调用描述：语义取预算首次 snapshot，执行审计取本次回执 snapshot，同阶段投影
必须相等。可预检的描述/协议错误在领取前拒绝，不写失败、不占预算；准备不回收租约、
不判断任务状态。详细输入、协议及错误映射见[RPC Contract](pi-rpc.md)。
协议内核只提供完整候选，内层业务 JSON 与最终模型身份仍由本任务服务权威接收；
接线不改变 `executor_kind=test`、唯一成功、两次预算、600 秒租约及 `model_mismatch` 规则。

## 1. 服务边界与身份

低层公共 Screening 任务服务封闭支持 `boundary`、`value`；二者独立登记、领取和计预算。
value 不要求 boundary 成功，boundary 的 `out_of_scope` 不取消 value。
两阶段编排、业务 eligibility、metadata_ready、校准、每日配额、Pi/RPC、真实模型和
默认执行者均不在此公共边界。单任务可领取不代表完整生产运行许可。

| 概念 | 身份 | 冻结或保留的依据 |
| --- | --- | --- |
| 预算范围 | 同库 `(paper_id, stage, fingerprint)` | 规范输入、首次上下文、至多一个筛选制品 |
| 任务代际 | 预算范围 + generation | 第 0 代由首个请求创建；每代最多两次 attempt；显式 retry 追加下一代 |
| 请求 | scheduled 的完整业务依据，或 manual/retry 的显式 request_id | 来源、调度日或 request_id、version/revision/snapshot；多个请求可共用任务 |
| attempt（尝试） | task_id + attempt_no | 领取时请求依据和当前论文依据、领取凭据、预算占用及结算事实 |

来源是请求的属性。scheduled/manual 均跟随最新代际，不能因日期、来源、版本 ID、
配置标签或进程变化重建第 0 代。A→B→A 回到 A 的原预算与筛选制品；跨 Paper 不共享
业务预算或筛选制品，底层字节去重见[制品 Contract](artifact-store.md)。本服务不提供
merge/undo 预算合并，承接见[路线图 C](../roadmap.md#module-c)。

scheduled 身份包含 `(paper_id, stage, fingerprint, 调度日, version_id, revision_no,
snapshot_id)`；完整依据相同才是精确重放，同日书目修订不同会追加请求但共用任务。
调度日由调用方显式提供 ISO 日期，不从时钟猜测、不参与预算。manual/retry 的
request_id 同键不同规范内容报冲突；request_id、reason、actor 均为非空、无 HTML、
不超过 2048 UTF-8 字节的文本，actor 仅为未经认证的本地说明。retry ID 库级唯一。

<a id="2-冻结输入与语言事实d1"></a>

## 2. 冻结输入与语言事实

登记只接收 Paper、阶段、明确已登记 snapshot 和请求审计依据，复用
[PaperFacts 一致读映射](paper-facts.md)及[StageInput 构造/回放](stage-inputs.md)；
不接收自由题名摘要或裸指纹。持久化独立期望 fingerprint、规范载荷原字节、格式和
对应论文/配置依据。ID、日期、generation、语言标记不进入格式 1 的阶段载荷或指纹。

低层 `register` 的 value 登记必须显式提供严格 `bool` 的 `original_title_is_zh`；通过
`StageInput.value_prediction_context(snapshot, original_title_is_zh=...)` 验证，
不新增语言检测器。缺值或非 bool 在登记时失败，不占 attempt。boundary 请求模型
禁止该字段，即使值为 null 也在登记时拒绝，不能等输出校验时才扣预算。
同 `(paper_id, value, fingerprint)` 首次登记冻结原语言事实和匹配 snapshot；后续
相反事实受控拒绝、不新增任务、不刷新预算。retry 必须继承原值，不能传新值更正。

生产来源登记由 `register_feed_value` 从数据库 Feed 发现关系自动派生严格 bool，
并持久化策略版本及来源，详见[Feed 原题名语言来源](#feed-原题名语言来源)。
原 `register` 保留显式 bool 的低层能力，不核验 Feed 来源、不补造生产来源依据；
它不构成无 Feed 归属论文的生产登记许可。

**同预算范围的误标无法纠正。** 映射变化只影响新输入的新预算，不追溯改写已冻结事实、
历史任务或重置次数。主题集合只从匹配冻结输入的同库历史 snapshot 派生，
不从当前 topics 文件取得。

<a id="3-一致登记领取与有限尝试已交付"></a>

## 3. 一致登记、领取与有限尝试

登记/领取的映射可在事务外一致读取；进入 `BEGIN IMMEDIATE` 后必须经同一连接
比较不可变的当前 selection_id、version_id、最新 revision_no 与预读依据。变化则回滚并要求
重新登记，不能把另一连接看到的事实视为写事务锁定。配置快照不可变，可在事务外
加载并在事务内核对已登记。论文仲裁仍由 PaperFacts 负责，任务层不复制另一套仲裁规则。

领取以请求回执为依据，用请求 snapshot 重建当前输入；缺项或指纹变化拒绝且不扣
预算。仅卷期/来源变化或跨版本文本相同、指纹不变均可领取。每次领取在同一短事务
占用 attempt、写凭据及租期，再在事务外执行。领取提交后即使尚未实际调用便崩溃，
也保守占预算。每个 attempt 驱动最多调用一次外部执行者；不宣称外部 exactly-once。

租约有效区间 `[claimed_at, expires_at)`，恰好到期可回收。到期但未结算时，原持有者
仍可续租或提交；回收结算后旧凭据全部失效。续租设为 `now + D`，
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

<a id="4-候选接收与筛选制品d3boundaryvalue-已交付"></a>

## 4. 候选接收与筛选制品

外部执行者返回完整原始字节或封闭失败。服务统一调用 `validate_output`，不接受
`validated=true`、自由解析字典或第二份字段 Schema。任务候选只接受严格 bytes；
JSON 语法、字段及业务规则的详细分类见[权威验证 Contract](screening-validation.md)。
校验失败转为 `output_invalid`，仅保存安全类别和字段路径；合法前后空白保留于原响应。

成功用 A3 `model_success_response` 的 `payload` 角色逐字节保留原始成功响应，
结构结果由权威模型规范序列化，不拆第二套业务字段。预算范围内最多一个筛选制品，
精确提交重放幂等，不同候选竞争不能覆盖。提交核对未结算 attempt/凭据/冻结输入，
**不在提交事务核对当前论文事实**。过期已结算凭据不能写成功或失败，最多留下事务外
已发布的完整孤立制品。发布、业务提交与回包故障不能制造半成功或退还预算。

执行来源封闭为 `executor_kind=test`；test 制品不具有生产建议或校准消费资格。
执行者报告的 provider/model 与冻结配置矛盾即 `model_mismatch`；缺报告则记录未知。
provider request ID 与 token 未报告为 null，报告 0 保持 0；不预建金额/成本字段。
此边界不证明真实模型、settled、输出通道、Pi 供给/安装和隔离通过；承接责任见[路线图 Pi/Live](../roadmap.md#module-live)。

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

<a id="5-当前适用性完全派生d2"></a>

## 5. 当前适用性完全派生

明确 snapshot S 下，把 Paper P 的当前修订重新映射得到 fingerprint F；同 Paper/
stage 的已接收筛选制品 fingerprint 等于 F 即当前，否则为 historical。映射失败为 undeterminable，携原 PaperReason（包括缺摘要、截断未知、配置未就绪、快照未登记），无
当前制品。版本 ID 改变但实际文本/配置指纹相同，制品直接适用；补卷期/来源不重跑。

当前/历史是查询视图，不是成功状态。不建结果使用依据表、再绑定 API 或绑定写入。
后续登记仅追加自己的 version/revision/snapshot 和缓存命中回执作为使用审计，不占
attempt；只读查询不要求先登记。更高 parser 删掉当前摘要时旧成功暂不适用，其他来源
补回相同文本后同制品重新适用，不改写论文仲裁或历史。

<a id="6-显式-retry共享查询与可见性d4服务已实现"></a>

## 6. 显式 retry、共享查询与可见性

显式 retry 对当前输入的失败终态追加唯一后继，保留原终态；同 ID 精确重放返回原
回执，不同 ID 竞争报 `already_retried` 并携已有后继 ID，运行中/尚有预算/成功输入不得借 retry 开新预算。
过期未结算的第二次 attempt 可在同一写事务结算为未知后创建后继。

共享只读查询接收明确 snapshot，统一推导当前性、代际、attempt、剩余预算、租约、
终态及受控原因；当前 failures 仅列当前指纹最新代际的失败终态，历史仍可查询。
不得显示原始输入、成功字段/分数/理由/速览/中文题名、失败原文、Prompt/Profile 或
领取凭据。repr/异常/日志同样脱敏。输入映射失败保留 A6 PaperReason，输出失败保留
A1 类别/安全路径，TaskReason 只承载任务专属原因，不扩 storage/errors。

本任务服务提供服务层 retry 与共享查询，不提供 screening CLI 或对应 help/退出码。
[FeedPipeline.trace](feed-pipeline.md) 提供只读跨组件服务组合；已有
[`paper trace` CLI](paper-facts.md#8-当前查询历史重建与只读-cli)仅覆盖论文事实，不展示这些任务组合。
共享资格与 calibration visibility 的纯规则见[共享 Contract](eligibility-visibility.md)。
本服务尚未消费该规则实现完整盲评隔离或生效筛选决定；
CLI/真实产品接线由[路线图 B](../roadmap.md#module-b)承接，正式校准由
[路线图 D](../roadmap.md#module-d)承接。

<a id="7-完整性备份与验收随已交付事实递增"></a>

## 7. 完整性与恢复

完整性重建仅复用：历史 snapshot → `replay_stage_input(stored_bytes,
stored_fingerprint, snapshot=...)` → 同源 value context → `validate_output(raw)`
→ 与保存结构比较；核对请求论文依据、代际/attempt/租约/预算和成功引用。不要求每个
model_success_response 都有任务引用，不重哈希已由 A3 验证的 blob。

数据库须匹配[随包唯一 head](artifact-store.md#revision-与原因码)；普通旧库报
`upgrade_required`，只显式升级，不在只读核验中迁移。任务与语言事实随备份语义闭包校验，格式、版本支持及
旧批次恢复步骤由[备份恢复 Contract](backup-restore.md)定义。备份格式为 1，
不另加任务 manifest 字段或计数；任务语义损坏映为 `registration_invalid`，不修复源数据。
即使 revision 相同，当前程序仍按当前输出校验/阶段输入语义重验历史响应；
规则收紧后，曾在旧程序通过的备份可能验证失败，不承诺任意旧备份跨程序版本永远可验证。

恢复不激活配置、不回收租约、不执行模型。显式继续仅使用恢复事实的剩余预算。
**两次上限仅对单一档案库连续历史成立；恢复较早备份会丢失其后 attempt，不能保证
跨备份回退的全局调用上限。** 恢复副本保留冻结输入、原始成功响应、retry 父链、
请求依据、语言来源及未结算历史，历史重建不依赖原数据/配置树。
恢复与查询不授予模型执行、校准或 live 资格；历史验收范围见[迁入记录](../verification/contracts-screening-tasks-history.md)。

<a id="8-a7-02-公共登记-api已交付"></a>

## 8. 公共登记 API

`paper_radar.screening_tasks.ScreeningTasks(database, data_root=None, *, clock=None, sink=None, monotonic=None)` 是唯一任务服务。
登记与输入回放不使用 `data_root`，不读来源文件或配置目录；boundary/value 成功的发布和显式读取使用该根，见 §10。
显式语言登记使用 `register(request)`，Feed 派生入口见[语言来源](#feed-原题名语言来源)；
请求 Pydantic 模型属于内部实现，不是第二个公共校验入口。没有默认执行者；
首次登记只创建第 0 代，已有预算的新请求跟随最新代际，登记均不占 attempt。
时间相关方法要求注入时钟；纯登记、回执、回放与 `validate_all()` 不依赖时钟。
`sink/monotonic` 用于[运行日志](runtime-logging.md)，与业务时钟 `clock` 一同注入；
省略 sink 时为 `NullSink`，不写持久日志。

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
scheduled_day 为空。value 的 `original_title_is_zh` 必须由 StageInput 上下文权威接收；
Feed 来源登记由派生入口提供该值，低层 `register` 要求调用方显式提供；boundary 禁该字段。
除此之外的字段一律拒绝，异常不回显调用方字段名/值。

request_id、reason、actor 检查非空、无 HTML、可 UTF-8 编码及最多 2048 字节；合法文本
原样保存，不静默 trim 后改变精确重放身份。request_id 在整个任务请求表唯一，与 A6
版本内的人工修正 ID 分开；回执不展示这些自由文本。

调用方请求的规范 UTF-8 JSON（键排序、无外围空白、非 ASCII 原样编码）单独哈希。
manual 精确重放先查全库 request_id 并核对该哈希，**先于当前论文映射**；当前论文后来
变化/缺项也返回原回执。同 ID 不同内容返回 request_conflict。scheduled 的回执 ID 是
source/paper/stage/fingerprint/day/version/revision/snapshot 的规范 JSON SHA-256；因此
同日补卷期产生新请求、同任务，不发生旧请求身份冲突。两种来源对相同语义输入的新请求
均关联已有预算范围；没有重复第 0 代，也不跨 Paper 复用业务任务。

回执格式 1 的固定安全字段：receipt_id、task_id、budget_id、paper_id、stage、fingerprint、
generation、source、version_id、revision_no、snapshot_id、scheduled_day、selection_id、
cached_success_id、format_version。manual 的回执 ID 由 source/request_id 的规范身份摘要派生；与用户自由
request_id 是两个字段。selection_id 已唯一标识不可变选择事件，无需复制未在 A6 公共
RevisionView 暴露的 event_no。事务外预读后任意修订变化均在写事务复核时受控
回滚为 `facts_changed`；重新登记后仍按相同语义指纹共用预算。

登记保留按指纹去重的规范输入、按 Paper/阶段/指纹冻结的预算、连续任务代际和
请求各自的论文/配置依据；这些身份与原字节随数据库恢复，不以当前目录重建。

任务原因目录版本为 1。登记原因包括 `invalid_request`、`invalid_context`、`context_conflict`、
`request_conflict`、`request_not_found`、`facts_changed`、`corrupt_reference`、`database_busy`，
均有固定中文下一步说明；Feed 派生另有 `language_missing`、`language_ambiguous`。
语言类型错误同时携 A5 原始 BuildReason/InputField；论文映射失败原样抛 PaperError，
缺库/旧库保留 StorageError，均不伪装成模型失败。`register` 登记失败回滚登记，
不占预算；Feed 派生拒绝可独立保留语言观察，见[语言来源](#feed-原题名语言来源)。

登记事实子闭包逐条回放冻结输入和每个请求的历史配置/修订，核对论文归属、选择身份、
原始请求内容摘要、回执身份及第 0 代唯一关系。备份通过组件组合调用该只读校验，受控语义损坏为 `registration_invalid`。
跨进程恢复仅需副本和已登记材料，不访问原数据/配置目录。
§9–11 的尝试、成功、retry 与语言来源校验均纳入同一闭包。

任务状态词表固定为 ready、running、lease_expired、retryable、failed、succeeded，
分别表示待领取、已领取未到期、到期未结算、失败但尚有预算、失败终态、成功。
当前六态均为任务派生状态，不构成 Paper 主状态或完整 eligibility。

<a id="9-a7-03-领取租约与失败-api已交付"></a>

## 9. 领取、租约与失败 API

服务使用注入的 UTC 时钟：回调须返回严格 `datetime` 且 `tzinfo` 是标准库 `UTC` 单例；
未配置、回调抛异常、naive 或其他时区对象均报 `invalid_clock`。
续租/新结算时刻早于本 attempt 的 claimed_at、下一次领取时刻早于前次 settled_at
同样报 `invalid_clock`；精确结算重放保留原时刻。
时间相关操作使用同一注入时钟；没有系统时钟默认值。普通错误、repr 与状态不携带
领取凭据、续租句柄、输入、异常文本或 traceback。

| 方法 | 结果与范围 |
| --- | --- |
| `claim(receipt_id)` | 以请求回执领取新 attempt，原子占一次预算；返回持有者专用 Claim，秘密字段隐藏 repr |
| `renew(renewal_handle)` | 仅持有者可用的不透明字符串句柄；未结算且匹配即设 expires_at=now+600 秒，不追加心跳历史 |
| `fail(claim, report)` | 原子追加封闭失败结算，返回安全 FailureReceipt；同凭据同内容精确重放返回原回执，内容不同拒绝 |
| `reclaim(receipt_id)` | 显式结算已到期 attempt 为 outcome_unknown；不到期不结算、不退预算 |
| `status(receipt_id)` | 只读推导 TaskStatus，包括 used_attempts/remaining_attempts、状态与 last_failure；不回收、不创建事实，和 §11 的版本化 query 结果类型不同 |
| `run_once(receipt_id, executor)` | 先校验可调用执行者、冻结输入和显式制品根的发布前置条件，再持久化领取并至多调用一次 test 执行边界；接收失败报告或 boundary/value 原始成功候选 |

领取先用请求自身 snapshot 映射当前 Paper，只比较阶段指纹；历史 version/revision 与
当前不同本身不阻止领取。写事务使用同连接复核本次预读的 version/revision/selection，
不一致报 facts_changed 且不新增 attempt。attempt 同时保存请求 receipt_id 与领取时的
当前依据，绝不覆盖请求登记依据。领取提交前失败回滚，提交后即使未调用执行者也占预算。
`run_once` 无论预期返回失败还是成功都必须提供 `data_root`；不可调用 executor 返回
`invalid_request`，缺根返回 `data_root_required`，制品路径/权限错误沿用 ArtifactError。
领取前组合预检调用制品库 [`prepare_publish()`](artifact-store.md#公共服务)，
不发布或登记占位制品；实际探测、清理及路径安全由制品组件定义。
预检不能保证领取后 I/O 仍成功，后续不可预知故障仍保守占预算。
纯登记、回执/任务查询、输入回放与手动 `claim` 不要求制品根；
`load_success` 及有成功历史的 `validate_all` 需要该根读取原响应。

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

只读完整性核对最多两次、连续序号、同任务请求、两套历史依据同指纹、
凭据/租约归属、严格 UTC 时间和结算一致性；恢复完整保留已占预算及租约，不自动回收。

领取/结算原因包括 `invalid_clock`、`task_running`、`budget_exhausted`、
`invalid_credential`、`settlement_conflict`、`invalid_failure`，均有固定中文下一步说明。
Claim 公开 task_id、attempt_no、receipt_id、claimed_at、expires_at 及领取时
version_id/revision_no/selection_id，另有隐藏 repr 的 credential、renewal_handle；
FailureReceipt 包含 task_id、attempt_no、kind、origin、settled_at 与安全 issues
（无校验问题时为空元组），不携失败原文。origin 封闭为 `executor`（报告或权威候选接收）、
`exception`（驱动捕获执行者异常）、`recovery`（回收的 outcome_unknown）。


<a id="10-a7-0405-原始候选接收与派生查询已交付"></a>

## 10. 原始候选接收与派生查询

公共 `SuccessCandidate(raw_response, executor_kind="test", reported_provider=None,
reported_model=None, provider_request_id=None, input_tokens=None, output_tokens=None)`
只接受严格 bytes；不接收已解析模型、自由字典或 validated 标记。所有审计字段隐藏 repr。
执行来源仅支持严格字符串 test，provider/model/request ID 为可空非空 UTF-8 字符串
（最多 2048 字节）；token 为可空非负严格整数，bool 非整数。未报告的字段保留 NULL，
报告 0 保持 0。不另设 token 业务上限；运行时不能规范序列化的审计受控拒绝。
run_once 收到非法候选协议形状时结算 protocol_error；直接非法调用
报 invalid_candidate。provider/model 与预算首次冻结 snapshot 的 screening 槽矛盾时
结算 model_mismatch，占用当次预算。test 制品不具有生产建议或校准消费资格。

| 方法 | 结果与范围 |
| --- | --- |
| `submit(claim, candidate)` | 权威校验 boundary/value 原始字节；合法返回 SuccessReceipt，校验/模型失败返回 FailureReceipt |
| `run_once(receipt_id, executor)` | 沿用一次尝试驱动，接受 FailureReport 或 SuccessCandidate；没有生产执行者 |
| `load_success(success_id)` | 显式内部消费 SuccessContent：原始成功字节、A1 权威 BoundaryOutput 或 ValuePredictionOutput、可空审计；敏感内容隐藏 repr |
| `query_successes(paper_id=..., stage=..., snapshot_id=...)` | stage 只接受 boundary/value；只读安全 SuccessView 序列，含成功回执、三值适用性及可空 PaperReason，不含判断/理由/raw |

SuccessReceipt 固定为 success_id、task_id、attempt_no、artifact_id、fingerprint、stage、
executor_kind=test、settled_at。FailureReceipt 的安全 issues 只持久化 A1 原 category/location，
回放为受控说明，不保存失败全文或自由指导文本。第二次执行只取得封闭失败说明及 A1
安全类别/路径。请求格式 1 的 nullable cached_success_id 只在本次登记时命中已有
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

validate_all 沿用同一备份钩子，重验原始响应、权威结构、冻结输入和期望模型、执行
来源、UTC 成功时间、终局排他和缓存归属；失败细节只允许权威 Schema 字段路径和
封闭类别。语义损坏仍映 registration_invalid。完整未引用 model_success_response
合法；备份恢复保留成功、旧请求当时回执、失败和未结算预算，不触发执行。
候选/读取原因包括 `invalid_candidate`、`already_succeeded`、`success_not_found`、
`data_root_required`，各有固定中文下一步说明；缺显式制品根时不猜 cwd。


<a id="11-a7-06-显式-retry-与共享查询已交付"></a>

## 11. 显式 retry 与共享查询

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
固定中文说明。retry 原因包括 `task_not_found`、`already_retried`、`not_latest`、
`not_failed`，各有固定中文下一步。

`validate_all` 重验每预算连续代际、同预算唯一父链、父真实两次失败、每代请求、唯一
retry 请求及其目标/规范摘要、首次预算依据。恢复保留父链与预算，不回收或执行。

<a id="12-a7-07-隔离完整历史恢复已交付"></a>
<a id="13-a7-08-独立验收与可信终态已交付"></a>

## 历史覆盖与验收入口

既有隔离恢复覆盖与 A7 验收叙述见[历史记录](../verification/contracts-screening-tasks-history.md)，
逐项材料见[A7 requirements](../verification/a7-requirements.md)。当前验收结论的格式、
同次终态与状态查询规则见[验证状态 Contract](verification-status.md)；历史通过不证明
当前工作树通过或 live 就绪。

<a id="b-首张真实任务票的责任111尚未交付"></a>

## 不提供／不证明

本服务接受显式 `sink`，默认 `NullSink`；安全事件、提交后记录与只读不写规则见
[运行日志](runtime-logging.md)。[B](../roadmap.md#module-b) 的真实执行入口负责构造所选根
的文件汇，并在真实 trace、展示及普通动作中消费共享资格／可见性。

本服务不提供 screening CLI、含任务组合的 `paper trace` CLI、完整 eligibility/visibility、每日自动配额、
两阶段生产编排、建议/决定、校准、reuse/extraction/Read 任务或真实模型默认执行者。
这些边界不否定 Feed 语言派生与服务层 trace 已实现，也不把最低元数据或登记成功当作
完整生产执行许可。产品组合由[路线图 B](../roadmap.md#module-b)承接，正式校准和复用
执行由[路线图 D](../roadmap.md#module-d)承接，Read 由[Body](../roadmap.md#module-body)/
[G](../roadmap.md#module-g)承接，完整日报与复核由[H](../roadmap.md#module-h)承接。
Pi/真实 RPC 与 NAS 恢复分别由[Live](../roadmap.md#module-live)、
[I](../roadmap.md#module-i)承接；工程 test 成功不授予这些资格。


<a id="feed-原题名语言来源"></a>

## Feed 原题名语言来源

`ScreeningTasks.register_feed_value(request, *, policy_version="v1", feed_gate=None)` 接收
严格 dict 的 `stage=value` 既有登记请求，调用方必须省略 `original_title_is_zh`。
服务由数据库 Feed/发现关系派生严格 bool，再交由原登记权威冻结预算。
`feed_gate` 是[FeedPipeline 组合前置引用](feed-pipeline.md)的事务接线参数，不是独立的
生产准入校验入口；低层调用不提供最低元数据或 boundary 前置保证。
boundary 和原 `register` 的载荷与校验保持原契约。

v1 的期刊约定映射为 dqkx=true，aies/jgr/qjrms=false；false 仅指非中文，不声称英文。
这是来源级约定，不按题名文本、字符集或语言检测判断。四个首发端点
（见[唯一端点声明](../../src/paper_radar/sources/feeds.py)）自动解析期刊；其他已登记 Feed 可通过
`bind_feed_journal(feed_id, journal)` 显式追加不可修改的归属，该操作不创建或订阅 Feed。
已知端点不能改绑到其他期刊；重复同值绑定幂等、改绑报 `context_conflict`，
Feed 不存在或期刊不受支持报 `invalid_request`。同刊多个 Feed 和跨刊同 bool 保存全部发现依据。
无发现或任一发现归属不支持时为 `missing`；所有来源受支持但 bool 不一致时为 `ambiguous`。
两者拒绝新预算，分别返回 `language_missing` 或 `language_ambiguous`。
无 Feed 归属的人工 Paper 没有默认语言值，不具有生产 value 登记资格。

派生结果包含 paper_id、policy_version、status、可空 original_title_is_zh 与 sources。
每项 source 包含 discovery_id、feed_id、可空 journal 和可空 original_title_is_zh。
派生状态封闭为 `missing`、`ambiguous`、`resolved`；预算读面封闭为 `frozen` 或
`historical_unrecorded`。frozen 保留同一组字段；historical_unrecorded 只含 status、
冻结的 original_title_is_zh 与空 sources，不补 policy_version 或 paper_id。
持久 JSON 读取严格验证字段、bool、
来源映射与状态一致性，损坏返回 `corrupt_reference`；既有序列化字节、哈希及冻结预算语义不变。
`record_language_status(paper_id, *, policy_version="v1")` 保存当前派生观察并返回状态和发现引用；
相同规范依据按摘要幂等，不重复追加；
`language_status(...)` 保留为同语义兼容入口，亦会追加保存；
`language_observations(paper_id)` 按 resolution_id 排序只读回查已保存的派生历史
（每项另含 resolution_id，含 missing/ambiguous/resolved，不是时间排序）；
`language_basis(receipt_id)` 查询预算冻结的策略、bool、期刊、Feed 与发现引用，默认没有
原始正文。历史显式 bool 预算返回 `historical_unrecorded`，不补造来源。
`register_language_policy(version, *, mapping=None)` 接受严格 bool 的完整四刊封闭映射，
显式登记新不可变版本；version 为严格字符串，匹配 `[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}`。
省略 mapping 沿用 v1；同版本同映射幂等。v1 保持固定映射，同版本不同映射返回
`context_conflict`，非法版本、缺键、额外键或非 bool 返回 `invalid_request`。
新派生使用未登记策略或不存在的 Paper 时报 `invalid_request`。
历史派生与预算按当时持久策略版本核验与回放，策略版本变化只影响新输入的新预算，
不更正既有值或重置预算。此登记能力不批准真实语言政策变更、来源政策或新订阅；
来源假设核实由[路线图 B](../roadmap.md#module-b)/[C](../roadmap.md#module-c)承接。
策略身份和来源审计不进入阶段指纹、boundary 或 Frozen Contract。

派生与新预算/来源引用在同一 `BEGIN IMMEDIATE` 事务内提交。登记前到达的发现参与派生；
后到发现不回写旧预算。精确 manual 重放先读取原冻结值；已有预算和 retry 沿用原语言值与
依据。来源提交失败不留下无依据的新生产预算。歧义观察可独立持久保留，拒绝不创建预算。

生产预算另存语言依据必存标识，与预算及来源关联同事务提交；旧回执不变。
无生产依据的历史/低层显式 bool 预算如实呈现未记录来源。
标识与语言关联缺失任一方均为 `corrupt_reference`，
不能把新生产关联丢失降级成合法历史。`validate_all` 和备份闭包核对这些引用，恢复后不依赖原根。来源级语言
约定不构成逐篇语言核实，也不授予模型执行、校准或自动精读资格。

## 相关

依据：[#114](https://github.com/MeteoBoy4/PaperRadar/issues/114)、[#118](https://github.com/MeteoBoy4/PaperRadar/issues/118)、[#76](https://github.com/MeteoBoy4/PaperRadar/issues/76)、[#77](https://github.com/MeteoBoy4/PaperRadar/issues/77)、[#78](https://github.com/MeteoBoy4/PaperRadar/issues/78)、[#79](https://github.com/MeteoBoy4/PaperRadar/issues/79)、[#80](https://github.com/MeteoBoy4/PaperRadar/issues/80)、[#81](https://github.com/MeteoBoy4/PaperRadar/issues/81)、[#82](https://github.com/MeteoBoy4/PaperRadar/issues/82)、[#83](https://github.com/MeteoBoy4/PaperRadar/issues/83)、[#84](https://github.com/MeteoBoy4/PaperRadar/issues/84)、[#85](https://github.com/MeteoBoy4/PaperRadar/issues/85)、[#111](https://github.com/MeteoBoy4/PaperRadar/issues/111)。

依据：[D1–D4 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356409213)、
[ADR-0031](../adr/0031-screening-budget-and-derived-applicability.md)、
[ADR-0035](../adr/0035-feed-derived-original-title-language-fact.md)、
[ADR-0026](../adr/0026-control-pi-through-a-bounded-rpc-adapter.md)。

- [规格：任务领取与幂等](../../intent/draft.md#85-任务领取与幂等)、[生产组合目标](../../intent/draft.md#b-screening-产品接线)。
- [任务服务实现](../../src/paper_radar/screening_tasks/service.py)、[语言来源实现](../../src/paper_radar/screening_tasks/language.py)。
- [StageInput](stage-inputs.md)、[输出验证](screening-validation.md)、[RPC](pi-rpc.md)、
  [Feed 组合](feed-pipeline.md)、[备份恢复](backup-restore.md)、[验证状态](verification-status.md)。
- [历史覆盖与验收叙述](../verification/contracts-screening-tasks-history.md)、
  [A7 逐项依据](../verification/a7-requirements.md)、[路线图承接](../roadmap.md#module-b)。
