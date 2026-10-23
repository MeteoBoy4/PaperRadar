# Screening 任务 Contract

状态：A7-01 已冻结 D1–D4 并收紧权威 JSON 解析；A7-02（#78）已交付公共登记、
冻结输入回放、请求回执、a701 持久化和备份语义闭包。领取/租约、接收、retry、共享
任务查询和完整组合验收仍待 #79–#84。本文不是 A7 passed 证据。
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

## 3. 一致登记（已交付）、领取与有限尝试（待实现）

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
D 为服务常量、不进入配置语义；时钟统一注入，不直接读取系统时间、不启动后台心跳。
凭据为 `(task_id, attempt_no, token)`，attempt_no 即领取代数，不另设计数器。
回收一律结算 `outcome_unknown`，不假定执行者曾经运行或已经停止，不退还预算。
只读查询不回收/续租；第二次 attempt 到期未结算显示 `lease_expired`、剩余 0，
回收后才进入失败终态。普通任务租约与 A4 继承 fd 的安装使用保护独立。

同代第一次失败仅余一次，第二次失败终态不随日期复活。失败类别封闭为
`output_invalid`（携 A1 安全类别/路径）、`model_mismatch`、`timeout`、`cancelled`、
`protocol_error`、`executor_error`、`outcome_unknown`；全部消费已领取预算。
服务 busy/引用损坏/非法调用不是模型失败；已领取但未结算者依租约恢复。
第二次尝试只消费冻结输入和脱敏失败说明，不携前次失败原文或会话。

## 4. 候选接收与筛选制品（D3；接收服务待实现）

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

## 5. 当前适用性完全派生（D2）

明确 snapshot S 下，把 Paper P 的当前修订重新映射得到 fingerprint F；同 Paper/
stage 的已接收筛选制品 fingerprint 等于 F 即当前，否则只是历史。映射缺项时无
当前制品。版本 ID 改变但实际文本/配置指纹相同，制品直接适用；补卷期/来源不重跑。

当前/历史是查询视图，不是成功状态。不建结果使用依据表、再绑定 API 或绑定写入。
后续登记仅追加自己的 version/revision/snapshot 和缓存命中回执作为使用审计，不占
attempt；只读查询不要求先登记。更高 parser 删掉当前摘要时旧成功暂不适用，其他来源
补回相同文本后同制品重新适用，不改写 A6 仲裁或历史。此规则取代原 #76 故事 29/31、
决策 15–16、测试表“当前适用性”“缓存重新使用”的旧绑定语义，见 ADR-0031。

## 6. 显式 retry、共享查询与可见性（D4；服务待实现）

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

## 7. 完整性、备份与验收（待实现）

完整性重建仅复用：历史 snapshot → `replay_stage_input(stored_bytes,
stored_fingerprint, snapshot=...)` → 同源 value context → `validate_output(raw)`
→ 与保存结构比较；核对请求论文依据、代际/attempt/租约/预算和成功引用。不要求每个
model_success_response 都有任务引用，不重哈希已由 A3 验证的 blob。

新 migration 从 a604 增量推进，只新增当前票实际消费的表；非空旧库与空库都测试。
backup format 保持 1，无新 manifest 字段或计数；head 前移后旧批次受控
`unsupported_revision`，旧库 `upgrade_required`，只显式升级、不在 verify 中迁移。
任务 validate_all 钩子放在 PaperFacts 后、manifest 反查前，语义损坏沿用
`registration_invalid`，不新增 BackupReason，不修复源数据。

恢复不激活配置、不回收租约、不执行模型。显式继续仅使用恢复事实的剩余预算。
**两次上限仅对单一档案库连续历史成立；恢复较早备份会丢失其后 attempt，不能保证
跨备份回退的全局调用上限。** 非空异地恢复须证明全部输入、响应、retry 与未结算
历史可独立重建。A7 正式结论依赖同次 A1、完整 A2、A3、A5、A6；A4 仍为总门禁必需。
RPC、live、完整阶段 A 与原题名语言生产来源持续未验收。

## 8. A7-02 公共登记 API（已交付）

`paper_radar.screening_tasks.ScreeningTasks(database, data_root=None)` 是唯一任务服务。
当前 `data_root` 只保留为备份制品根的组合位置；登记与输入回放不读来源文件或配置目录。
登记只接收 `register(mapping)`，请求 Pydantic 模型属于内部实现，不是第二个公共校验入口。
没有默认执行者；此切片全部任务仍是第 0 代、零次 attempt。

| 方法 | 结果与范围 |
| --- | --- |
| `register(request)` | 追加或精确重放 `RequestReceipt`；只写登记事实 |
| `get_receipt(receipt_id)` | 只读返回登记时回执，不重新映射当前论文 |
| `receipts(paper_id)` | 按回执 ID 排序的安全请求历史，不是后续资格/失败查询 |
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
内容摘要和独立论文/配置依据）。head 为 a701_screening_registration；不预建 attempt、
lease、retry 或成功表。A5 格式、artifact kind、backup format/manifest/counts 均保持原值。
新程序不接受 a604 备份批次，须用匹配程序恢复后显式升级；普通旧库准确报 upgrade_required。

现有任务原因目录版本 1：invalid_request、invalid_context、context_conflict、request_conflict、
request_not_found、facts_changed、corrupt_reference、database_busy，各有中文下一步说明。
语言类型错误同时携 A5 原始 BuildReason/InputField；论文映射失败原样抛 PaperError，
缺库/旧库保留 StorageError，均不伪装成模型失败。失败只会回滚登记，不存在预算占用。

当前完整性校验逐条回放冻结输入和每个请求的历史配置/修订，核对论文归属、选择身份、
原始请求内容摘要、回执身份及第 0 代唯一关系。备份 hook 在 PaperFacts 后、manifest
反查前调用，受控语义损坏为 registration_invalid。跨进程恢复仅需副本和已登记材料，
不访问原数据/配置目录。后续表的校验必须随其所属票继续补入此同一闭包。

任务状态词表预先固定为 ready、running、lease_expired、retryable、failed、succeeded，
分别表示待领取、已领取未到期、到期未结算、失败但尚有预算、失败终态、成功；A7-02
只登记 ready，后续票实现其余状态。它们不构成 Paper 主状态或完整 eligibility。
