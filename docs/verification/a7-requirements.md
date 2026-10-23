# A7 规格对照与固定绑定台账

状态：#77（A7-01）交付裁决文档与严格 JSON；#78（A7-02）已交付登记、冻结回放、
a701 与备份闭包；#79（A7-03）交付 a702 原子领取、有限预算、租约、失败结算、
显式回收与 test 一次尝试驱动；#80（A7-04）交付 boundary 权威接收、唯一制品、
三值适用性及成功恢复闭包；#81（A7-05）交付 value 同源权威接收与恢复。
#82–#84 的 retry/版本化共享查询/完整组合恢复及
独立 A7 验收尚未交付。当前 `check-offline` 通过只证明已有组及本次全套检查，
不表示尚未注册的 A7 passed。运行回执、commit 和 run_id 存在工作树外，不改写历史证据。

## 来源顺序与冻结依据

采用正文 → 实施前补充说明 → 用户 D1–D4 裁决 → 评论之二 → 评论之三 → 对应原生
子票及后续评论；冲突以裁决/后续评论为准。评论之二/三只补落点与验收成本，不重开裁决。
以下 SHA-256 取 GitHub 返回正文/评论的 UTF-8 原字符串，不含临时拼接分隔符。

| 层次 | 固定来源 | SHA-256 |
| --- | --- | --- |
| 正文 | [#76](https://github.com/MeteoBoy4/PaperRadar/issues/76) | `41f950de0570328290f5796600f2d8cb963aea86970f1e522a9e9f7a1b85a488` |
| 补充 | [实施前补充说明](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6355207158) | `fac9ffdc68c3350139a0db9dece22231e50e98e68c86366e6da5c3972b6b76d7` |
| 裁决 | [D1–D4](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356409213) | `19b28cb4435163040038985e7afdff4b2da54440a2bdcc9753af877b7f4b6002` |
| 裁决后核对 | [评论之二](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356573209) | `d04236150818f6b4d135d8aecc60482b7bcfc2c07f2e90218badb53fb935aa4a` |
| 裁决后接线 | [评论之三](https://github.com/MeteoBoy4/PaperRadar/issues/76#issuecomment-6356665663) | `e90c09678f985295eab0197778be231826fb12e2882e9278087bb2d4d38e9ff2` |
| 首张实现票 | [#77 正文](https://github.com/MeteoBoy4/PaperRadar/issues/77) | `96c89cd491f6afb7fb590702bb02387f829222faadbc1c7b686af2956a38d4d9` |
| 首票类别补充 | [#77 评论](https://github.com/MeteoBoy4/PaperRadar/issues/77#issuecomment-6358893774) | `34b433fc0560b226517dddaf50c0cc6d8fe2e757e54ba2f3169acf87aba2c509` |

起点为 `191c9e11759463bd890ff15b9e77db87624dd8ac`（A6 head
`a604_version_relations`）。原生完整图：77→78→79→80→(81,82)→83→84；83 同时依赖
81、82。此图取代补充说明 S1 的建议拆票编号；所有边均来自 blockedBy 全量列表。

## 正文—补充—裁决—验收四层对照

US 表示 #76 User Stories，ID 表示 Implementation Decisions；此表中的“待”明确是
后续子票责任，并非现已实现。公共测试 seam 已由原规格用户确认：任务服务为主，
真实 SQLite/migration/ArtifactStore/配置/PaperFacts，只替换时钟与外部执行者。

| 正文 | 补充及裁决 | 最终规则与文档落点 | 验收责任/当前状态 |
| --- | --- | --- | --- |
| US25–26、ID12 | D1(a)、评论二五、评论三二 | Contract §2：value 必传严格 bool、首次预算范围冻结、retry 继承不接受更正；boundary 禁字段；语言不进 A5 | #78 登记拒绝、#81 接收/回放已交付，#82 retry 待。真实来源列 title_language_source 未验收 |
| US29/31、ID15–16；测试“当前适用性”“缓存重新使用” | D2(a)、S2、评论二五 | Contract §5、ADR-0031、主方案 §8.5：同明确 snapshot 当前指纹匹配即适用；版本不同但同指纹仍适用；去掉绑定表/API/写入、提交事务论文复核 | #80/#81 boundary/value 三值派生已交付；原 US29 改为输入变化只作历史，US31 改为只读重建匹配，删除缓存重新绑定行 |
| 测试“A6 语义联动” | D2(a)、B2/B6、评论二五 | 更高 parser 缺摘要→无当前成功；其他来源补回相同文本→原制品再适用，保留 A6 仲裁 | #80 boundary 两例已交付；#81 value 缺摘要保留历史与只读重建已交付 |
| US24/27、ID12–13 | D3(a)、评论二二、#77 评论 | 原权威内部严格解析；str/bytes/bytearray 任意层重复键/NaN/Infinity 根 `$` invalid_json，先于字段/业务错误；Mapping 路径不变 | #77 已实现；test_screening_strict_json 93 例，新旧相关 332 例；原固定模块/Schema/分母不变 |
| US23、US33 CLI 部分、US39、ID20–21 CLI 部分 | D4、S2、评论二五 | Contract §6：本批仅服务 retry 与共享查询；screening CLI、paper trace 组合、help/退出码移至真实任务生产票 | #82 服务测试待；#84 不得要求 CLI，现有产品 CLI Contract 保持 |
| US1–7/19–20/30、ID3–7/17–18 | T1/T2/T7、B1/B3/B9/B11、评论二四 | Contract §1–3：预算/代际/请求/attempt 四层；完整 scheduled 依据、manual 冲突；A→B→A、跨日/无关配置不刷新 | #78（含真实进程登记竞争）已交付；第 0 代可能由 manual 创建；#79 消费同预算范围 |
| US8–18/32、ID8–11 | T3/T4/T6、B2/B4/B5/B7、S3 | Contract §3/9：原子领取、两次预算、凭据 fencing、回收 outcome_unknown、lease_expired；第二次尝试不等于显式 retry | #79 交付真实子进程/屏障/强杀、注入 UTC 时钟及失败执行边界；成功接收仍归 #80/#81 |
| US24–28/35、ID12–14/19 | T1、B6/B8/B9、评论三三/六 | Contract §4：原始响应+唯一权威结构；test 来源/未知审计；候选竞争、合法迟到、发布/提交/回包故障 | #80/#81 boundary/value 已交付且共用成功事务；D3 已由 #77 阻止重复键入口 |
| US21–22/33–34、ID7/20–22 | T5、B5/B10/B11 | Contract §6：失败终态唯一后继、库级 retry ID、同请求幂等/异请求竞争；安全查询统一格式 1 | #82 待；运行中/可继续/成功/非当前拒绝，测试固定 query shape |
| US28/36–38、ID22–23 | B12、评论三三/四/六 | Contract §7：只读语义钩子、恢复无执行、原目录不可用非空重建；语义损坏 registration_invalid，历史回退预算限制公开 | #78 起随实际表加基础验证，#83 完整跨域恢复/损坏/继续待 |
| US40、ID24–25 | 评论三一/七/八 | 必需 A7 组、同次前置/固定格式/源码/fixture/整数回执/真实 head/可信终态；不新增四份冻结 Contract | #84 待；A7 组注册与 status 识别同提交，不能拿历史通过代替 |

## 补充条目的完整落笔台账

| 条目 | 固定去向及验收 |
| --- | --- |
| T1–T7 | Contract §1/3–6 与 GLOSSARY：筛选制品/原始成功响应；四层身份；attempt_no 即领取代数；第二次尝试与 retry；唯一后继；回收为未知；后续登记请求含明确 snapshot |
| B1–B3 | §1/3：完整 scheduled 元组、回执领取、同事务 CAS；snapshot 可事务外加载，论文当前依据必须同连接锁定；#78/#79 |
| B4–B7 | §3/4：采纳结算前仍有权；半开租期、now+D；过期未结算独立态；失权迟到拒绝；全部封闭失败消费预算；#79/#80/#82 |
| B8–B9 | §4/7：test 来源仅一种、未知不造 0、无金额；SQLite 规范载荷、权威 JSON 结构、A3 原字节；不新增 artifact kind；#78/#80/#81 |
| B10–B12 | §1/6/7：PaperReason 与 A1 类别复用、TaskReason 仅任务原因；retry 文本/身份限制；backup format 1/旧 revision/连续历史预算限制；#78/#82/#83 |
| S1–S4 | 原生图以八票为准；D2/D4 收缩；续租仅更新投影；AST 守卫禁 pi_supply/httpx/LLM/系统时钟；仍实际测 Read/期刊配置；#79/#84 |
| 评论二一/二 | 新 JSON 回归独立模块，不动旧 39/88 等分母与 schema/manifest fixtures；mapping.py 与 __init__.py 两处均需 A6 重审；D3 本票已完成 |
| 评论二三/四 | 真实进程窄缝复用 SQLAlchemy events/sitecustomize，链 deny_network；无长 sleep 推断；boundary/value 不隐式编排；scheduled 可按规范依据哈希派生 |
| 评论二五/六 | D1–D4 覆盖清单落实于本票 Contract/ADR/主方案；不改变旧证明或创造全局配置激活权威 |
| 评论三二/三 | 复用 value_prediction_context 严格 bool、replay_stage_input 的规范字节/独立散列/投影核对；冻 snapshot+flag+payload+fingerprint；旧库报 upgrade_required；#78/#81/#83 |
| 评论三四/五/六 | 钩子在 PaperFacts 后 manifest 反查前；同 try 映 registration_invalid；不要求所有成功 blob 被引用、不改 manifest/counts、不重复 blob 哈希、不放自由 metadata；#78/#80/#83 |
| 评论三七/八 | FORMAT_VERSIONS 固定公共查询/原因形状，不新增冻结导出；a7_scope 不自绑，测试同次前置重用 rebind/same-run 模式，migrated_revision 查实际 head；#84 |
| 评论三一/九 | 业务持久化接入与最终验收注册两类重绑定详见下节；按子票真实触及增加必要波次，不预建其他阶段空表 |

## 绑定成本与集成波次

每波提交前运行只读 `./scripts/audit-verification-scope --collect --json`，逐项查看
`downstream`，记录旧/新 hash、原用例数、重审理由；同一波代码与全部受影响 scope
必须在同一次提交落完。不得自动按实测数更新预期、降低分母或修改历史证据。
正式门禁在最终提交后运行，以该次证据确认通过；运行事实存工作树外，不自改已验证代码。

第一类：业务持久化接入（从 #78 开始，随实际纵向切片重复必要波次）。

| 真实触碰 | 受影响绑定/动作 | 重审理由 |
| --- | --- | --- |
| migration 实际 head | a2_scope、a2_full_scope、a3_scope、a4_scope、a5_scope、a6_scope 的 MIGRATION_REVISION；20 个含 head 字面量旧测试模块与 fixture | #78 增量 a701，#79 增量 a702；后续新消费表需新 migration 时同样推进；不预建未来空表 |
| backup/manifest.py 的 BACKUP_DATABASE_REVISION | A3/A4/A6 源码绑定及必要下游 | head 前移仍保持 format 1 与旧批次受控拒绝 |
| backup/service.py 的语义钩子 | A3/A6 源码绑定及下游 | 从首个任务事实起纳入备份语义闭包；#83 再扩完整验证，不允许中间票带坏备份 |
| papers/mapping.py、papers/__init__.py | A6 两处源码绑定 | 同事务 CAS 的最小只读公共组合入口；不复制仲裁/输入构造 |
| 已绑定测试 head literal/fixtures | 六组各自匹配模块哈希、原固定用例数不变 | 非空/空库升级与旧能力仍有效；新增测试另模块 |

第二类：最终验收注册（#84，同一提交完成）。

| 文件 | 绑定组 | 同提交变更 |
| --- | --- | --- |
| scripts/check-offline | A2-01、完整 A2、A3、A4、A5、A6 | A7 必需组及“九份主要文件”文案 |
| scripts/a2_full_acceptance.py | 完整 A2、A3、A4、A5、A6 | acceptance_groups 追加 A7 |
| scripts/offline_evidence.py | 完整 A2、A3、A4、A5 | 组数/文案；CONTRACT_NAMES 四份显式列表保持 |
| scripts/verification_status.py | A6 | SUPPORTED_GROUP_FORMATS 认识 .a7.json 格式 1，与注册同步 |

同步更新 test_a2_full_entry 的帮助份数、test_verification_status 的 suffix 列表，
verification-status.md/stage-inputs.md/offline-evidence.md/README 的主要文件和 JSON
份数。test_a1_acceptance 现有帮助断言已经足够，不为文案修改其 A1 绑定。
A7 scope 不把自身放进 REQUIRED_SOURCE_MODULES，避免自指哈希。A7 公共格式计划为
screening_tasks/task_reason_catalog/task_query_result 1、boundary/value inputs 1、backup 1。

#77 本票只改未被源码绑定的 screening/validation.py、新增独立回归和裁决文档，
不改 migration、四份冻结 Schema、旧固定模块或 scope；因此无需旧组重绑定。
本票代码/回归 SHA-256 见下方独立记录，后续语义变更须显式更新此记录并解释原因。

| #77 固定材料 | SHA-256 |
| --- | --- |
| `src/paper_radar/screening/validation.py` | `63d26b9b7b5593bb3260a37aacef1d537fa7736f7bbbf7ef25b9198bab17fc62` |
| `tests/test_screening_strict_json.py` | `49365327a4a2d6599c62c049f5e3dd8d2001aa4c25741a9f545b842b81c48c53` |

## 未验收范围与最终结论边界

A7 完成前仍待：版本化共享查询/retry、
完整组合恢复/语义损坏、可信独立 A7 组。最终不得把 `rpc_verified`、`live_verified`、
`stage_a_verified` 置 true。未覆盖项至少保留 rpc_compatibility、pi_execution、
real_model_usage_and_cost、title_language_source、eligibility/metadata_ready、daily_quota、
two_stage_orchestration、suggestion_decision、calibration_visibility、reuse/extraction/read
任务、merge_budget、cli、nas_restore、stage_a、live；test 来源不能进入后续生产建议/校准。

最终验证先新任务/直接论文映射/权威输出/存储子集，再迁移、真实进程故障及隔离恢复，
最后实际 `./scripts/check-offline` 返回 0。A4 虽不为 A7 直接前置，仍是整体必需组。
旧 A1–A6 的历史 not_assessed 不回写，新增 A7 自己承担实际交付证明。

## A7-02 实际交付与本波绑定重审

#78 已完成公共 register/get_receipt/receipts/load_input/validate_all，详见 Contract §8。
正文 US1–7/19–20/30、ID3–7/17–18 的登记责任由以下独立模块证明；后续 attempt、lease、
成功接收与 retry 责任不提前宣称完成。

| 测试模块 | 当前用例 | 证明 |
| --- | --- | --- |
| test_a7_registration | 6 | 冻结/旧精确回执；严格语言；跨日/修订/A→B→A；主体/阶段；同文本跨版本；Read/期刊配置隔离 |
| test_a7_registration_failures | 34 | 非空/HTML/UTF-8/2048 字节、封闭请求、具体 PaperReason、独立 readiness、缺库与隐私 |
| test_a7_registration_process | 7 | 双进程同/异请求唯一预算；事务前/中/提交后强杀；CAS；5 秒忙锁 |
| test_a7_registration_migrations | 6 | 非空 a604→a701、DDL/提交失败和强杀、旧全部 config/artifact/Pi/paper 历史、WAL、依赖守卫 |
| test_a7_registration_imports | 1 | 公共论文词汇包在零外部 I/O 哨兵下可导入，保留既有 CLI 帮助启动边界 |
| test_a7_registration_backup | 10 | 非空恢复；两阶段 WAL、新进程禁原目录后移动回放；八类 FK/SQLite/外层哈希合法语义损坏拒绝 |

共 64 例；全部通过后再执行直接关联旧回归与完整门禁，不把当前收集数动态写入旧分母。
本票不注册 A7 组，这些新增模块在 #84 一次冻结 A7 验收范围。

实际重绑先审查 head 字面量及最小源 diff，再按 scope audit 的 downstream 顺序更新。
六组 MIGRATION_REVISION 前移 a701_screening_registration；A3 的 backup_database_revision
同步。20 个旧测试模块仅替换“当前 head”及 future 假迁移的 down_revision 字面量，
不改历史旧库 fixture 的 revision、不新增/删除旧用例。A6 capabilities fixture 的 a601–a604
**历史源码路径保留原值**：其字节不受本波影响，A7 的新增 migration 由本票实际升级测试
证明，最终源码固定由 #84 负责。没有为表面上符合评论的数量而改写历史能力材料。

| 接入文件 | 本波重审理由 | 旧组 |
| --- | --- | --- |
| backup/manifest.py | a701 批次 revision，format 1 保留 | A3/A4/A6 |
| backup/service.py | PaperFacts 后接任务语义钩子，仍映 registration_invalid | A3/A6 |
| papers/__init__.py | 仅导出已有连接级 resolve_revision；mapping.py 没有改动 | A6 |
| 20 个旧测试模块 | 当前 head 及未来假 head 依据前移，原固定分母保持 | 按原所属 A2-01/完整 A2/A3/A4/A5/A6 |
| a2→a2_full→a3→a4→a5→a6 scopes | 按实际下游重新计算上列已审查字节身份 | 不修改旧历史结论 |

逐条旧/新 SHA-256、路径和原因保存在本次外部 `78-rebinding-ledger.json`，门禁 run_id、
提交与完整审计原 JSON 见 `78-handoff.md` 和 verification-runs，避免 run_id 自哈希循环。
已确认 36 条绑定更新涉及 27 个被绑定路径；正式门禁以最终提交为准，不写回历史证据。


#78 首次完整门禁暴露一项集成回归：直接在 papers 包导出 resolve_revision 会提前
加载 SQLAlchemy，使既有 help 的零外部 I/O 哨兵在 ssl 初始化时失败。独立新回归先红，
再改为与 PaperFacts 一致的 TYPE_CHECKING + __getattr__ 延迟导出；事务组合能力和旧
CLI 契约均保持。旧 CLI 固定用例未改，仅 A6 对 papers/__init__.py 的源绑定再审。
失败 run b3342870a7be45888cc5efda214908a9 保留原始终态，最终通过另起新 run。

## A7-03 实际交付与本波绑定重审

#79 在同一 ScreeningTasks 公共 seam 增加 claim/renew/fail/reclaim/status/run_once，
保留纯登记与 validate_all 无时钟可用。固定 D=600 秒，严格 UTC 注入；没有后台心跳
或回收线程，普通状态只读。领取保存请求 receipt 与领取时当前依据，事务外用请求
snapshot 映射，只按指纹判旧，短事务同连接 CAS；预算从每代不可变 attempt 事实推导。
同版本修订或同文本跨版本不消耗新预算身份，跨日、重启与 A→B→A 不复活次数。

失败类别为封闭七项；本票实际接通执行者报告、捕获异常和回收。output_invalid 与
model_mismatch 留给后续权威接收，不提供成功旁路。过期未结算仍可持有者续租/提交，
已回收则 outcome_unknown 并 fencing；同凭据同失败精确重放返回原安全回执，
冲突内容拒绝。一次尝试先提交领取，再向 test 执行边界至多调用一次，只传冻结
StageInput、安全修正说明和不透明续租句柄；异常文本、凭据、前次原始失败不进入普通输出。

新增独立 test_a7_* 模块承担领取预算、时间与失败、执行边界、真实进程窄缝、非空
a701 升级及备份语义闭包的证明。真实竞争与强杀使用屏障，覆盖领取提交前后、
恰好到期、续租/回收竞争、回收后迟到拒绝及 5 秒 busy；不以长 sleep 推断状态。
新增事实由同一 validate_all 备份钩子验证，恢复保存已占次数和未结算租约，只读不回收。
源库与副本的两次保证分别只适用于各自连续历史，旧备份之后丢失 attempt 不可追回。
各模块固定范围最终在 #84 统一注册，本票不提前登记 A7 组、不改旧分母。

| 接入文件 | 本波重审理由 | 旧组 |
| --- | --- | --- |
| backup/manifest.py | 批次 revision 前移 a702_screening_attempts，format 1 保留 | A3/A4/A6 |
| 20 个旧 current-head 测试模块 | 当前 head/未来假 head 前移；历史 migration 路径与用例数保持 | 原所属 A2-01/完整 A2/A3/A4/A5/A6 |
| test_a7_registration_migrations | 当前升级终点和实际七表集合前移；原 a604 历史 fixture、失败原子性与旧业务数据保留 | A7 最终由 #84 冻结 |
| a2→a2_full→a3→a4→a5→a6 scopes | 按 audit downstream 顺序重审已改字节身份，A3 backup_database_revision 同步 | 不修改历史验收结论 |

本波逐条旧/新 SHA-256、路径及理由保存在外部 `79-rebinding-ledger.json`；相关测试、
正式门禁 run_id/提交与原 JSON 由本票 handoff 和 verification-runs 保留。正式门禁
在最终提交后运行，执行过程中不修改源码，不以收集成功冒充测试执行。
本波已审阅 33 条绑定、25 个被绑定路径；旧固定 174 模块、3077 用例分母保持。


## A7-04 实际交付与本波绑定重审

#80 复用已有 once driver 和 A1 boundary 权威原始字节验证，A3 单 payload 发布在业务
写事务外；短事务仅核对尚未结算领取身份/冻结输入，不复核论文当前字段、不把租约
到期当成失权。唯一成功行与 attempt 终局共同排他；精确提交包含 raw 字节与审计，
重放不发布、不重新调用、不追加次数。所有生命周期路径都认识成功，不能回收成未知。
失败全文不持久化，A1 类别/安全路径保留，审计未知与 0 分开；只有 test 来源。

请求新增不可变 cached_success_id，只在新登记实际命中时保存；旧回执不被后来成功
改写。显式 snapshot 查询复用 PaperFacts 独立一致映射：同指纹 current，映射成功且
不同 historical，失败 undeterminable+PaperReason，允许相对任务读取滞后。parser 删除
摘要/其他来源补回同文本、跨版本同文本及 Read/期刊无关配置均由公共服务证明。

独立 test_a7_boundary_success 与 test_a7_success_applicability 覆盖权威输出、合法三态、
重复键/围栏/截断/未知字段/占位/类型失败、空白原样、模型不符、NULL/0、旧凭据、
精确重放、原回执/新缓存回执及三值变化。test_a7_success_process 使用真实进程屏障
证明发布后/事务中/提交丢回包中断、两种顺序与同时回收竞争、同/异 raw 并发提交；
只有成功或 outcome_unknown 单一终局。test_a7_success_migrations 从非空 a702
保留失败和未结算尝试升级，覆盖 DDL/stamp 失败和强杀、CHECK 保留。

成功完整性复用同一备份 hook 重验 A1 原始响应/规范结构/冻结依据、来源与终局；
test_a7_success_integrity、test_a7_success_backup 覆盖合法 FK 损坏拒绝、非空异地
移动恢复、禁止读取源配置/原库/批次、失败/未结算与完整未引用成功响应合法。
新增表/列均为本票实际消费，不预建 value/retry/成本空壳；value 与共享查询由后票扩展。

本波 head 前移 a703_screening_success，backup format/manifest/counts 与 A5 格式不变；
六组 MIGRATION_REVISION、A3 backup_database_revision、20 个旧 current-head 测试
及原 downstream 哈希同提交重审。a701/a702 历史 migration 不改，旧固定174模块/3077
用例分母不减。逐条旧/新身份及原因见外部 80-rebinding-ledger.json；提交、run_id、
完整门禁和全部原 JSON 见 80-handoff.md/verification-runs，不回写历史证据。

## A7-05 实际交付与本波绑定重审

#81 在已有 SuccessService 扩展 value，不复制执行、预算、租约、失败或成功提交逻辑。
接收/回读共用历史 snapshot → A5 严格 replay/投影 → value_prediction_context →
A1 value_prediction 权威链；仅首次预算语言事实参与上下文，不改 A5 载荷或冻结输出
Schema。成功审计、原始字节/结构/摘要、缓存、三值查询和恢复同源重验适用于两阶段。

独立 test_a7_value_success/context/backup/integrity 的 40 例覆盖合法中文原题名 null、英文合法中文显示
题名、分数/可判断性/价值类型/主题/文本/JSON 错误占 attempt、安全修正说明、两次
预算、boundary out_of_scope 不取消 value；历史主题与模型不被当前文件替换、纯
Read/期刊/声明版本变化保持复用、语义变更只作历史、语言冲突不能刷新缓存或预算。
非空异地恢复在新进程禁止原目录/原批次访问，重建原 snapshot、语言、主题、响应、
失败与未结算预算；合法 FK 且重算外层哈希后，错误 snapshot、投影、语言、结构、
原始响应引用或模型审计均受控 registration_invalid，读写路径不修复损坏数据。
失败路径只允许所属阶段的权威字段，新增 value 字段白名单不放宽 boundary 历史验证。

无新表或 migration，head/backup 格式/A5 与四份冻结 Contract 保持。旧 A7 boundary
测试仅因输出扩为权威联合类型增加显式缩窄断言，原用例数不变；本票新增测试独立
模块，A7 最终固定注册归 #84。旧 scope 只读 collect 审核结果、子集、最终提交和完整
门禁原始 JSON 记录于外部 81-handoff.md/verification-runs，不提前声明 A7 passed。


## A7-06 / #82 retry 与共享查询落地

公共 ScreeningTasks.retry 接收显式父任务及库级 request_id；register 仍不接受 retry 来源。
TaskQueryResult v1 由 query 统一投影范围、最新代际、请求/attempt 历史、预算和当前失败，
安全字段见任务 Contract §11。当前失败不包含第一次失败、旧输入或未结算的到期租约。
父链使用 tasks.parent_task_id 外键与 UNIQUE，先核对当前映射的 PaperReason，再核验
任务资格；第二次过期结算与唯一后继在同一事务。新登记跟随最新，旧精确回执不变。

独立 test_a7_retry、task_query、retry_process、retry_migrations、retry_backup 覆盖两阶段
通用失败、严格上下文继承、同 ID 重放/冲突、跨来源 ID、真实双进程、提交丢回包、
retry/回收/成功竞争、非空五表 FK 环迁移、开启外键的中断回滚和搬迁恢复/语义拒绝。
#81 合入后已以公共真实成功路径交叉验证两阶段成功拒 retry，以及已有后继后来成功
仍返回 successor_task_id；61 项 #82 新例独立于旧固定分母。恢复新进程显式拒绝原目录、
改名根和原批次的 SQLite file: URI，并用拒绝探针证明钩子生效。最终组合恢复与固定
A7 范围由 #83/#84 完成。

本波 head 前移 a704_screening_retry，旧 a701/a702/a703 源码保持；备份格式 1、清单、
计数与 A5 语义不变。六旧 scope、backup revision、20 个当前 head/未来 head 探针及
A7 历史迁移测试的“升级到当前”断言同提交重审；原历史 fixture 不前移，固定分母不减。
旧/新绑定与逐条理由保存在工作树外 82-rebinding-ledger.json，完整门禁仍须最终真实
exit0及 passed/verified/same；此处不是 A7 独立 passed 证据。
