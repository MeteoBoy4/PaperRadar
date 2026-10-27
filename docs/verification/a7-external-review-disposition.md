# #76 外部审查 r1/r2 处置

基线 `47dec5870d63bef9c6754f973211b9660b335b3c`，原报告不改写，仅末尾引用本表。
本轮只整理任务包内已触及代码及验证文档；无新 migration、Frozen Contract、
StageInput、预算身份、租约、盲评或资格语义变更。公共测试 seam 为 ScreeningTasks。

| 项目 | 判断及处置 | 可复核依据 |
| --- | --- | --- |
| r1 S1 / r2 F4 | 接受；共享 stage_mapping 选择及 require_stage_mapping 严格守卫 | repository.py；登记/领取/retry 保留 PaperError 优先；query/success 保留携 PaperReason 三值结果；integrity 保留 corrupt_reference 映射，CAS 时点不动 |
| r1 S2 / r2 F6 | 接受；ATTEMPTS_PER_GENERATION=2 统一生产规则 | attempt_models/rules/repository/integrity、execution、retry；DDL 与历史 migration 保留固定字面，测试仍独立断言两次 |
| r1 S3 | 部分接受；共享非空、strict UTF-8、2048 bytes 基础检查 | rules.require_bounded_text；manual/retry 额外 normalize_text 拒 HTML；success_rules 审计不增 HTML 禁令，Contract §10 只要求 bounded UTF-8；原字节、错误类别保留 |
| r1 S4 | 观察/延期 | N+1 形状属实，尚无性能测量证明其阻碍单用户 V1；本次不扩大查询重构 |
| r1 Spec 备查 remaining | 非缺陷，不改 | 成功状态仍 remaining=2-used，仅计预算余额，不表示成功后可继续领取 |
| r1 Spec 备查 IntegrityError | 非缺陷，不改 | database_errors.py 非 busy IntegrityError 仍 corrupt_reference；不改变拒绝类别 |
| r2 F1 | 拒绝“原 HEAD 没有通过证据”；认同静止工作树门禁要求 | 历史 6e818ba30d6a4b7a83ae78cac9007bbf 为 47dec58/dirty=false/passed；19af0e 那次 identity_changed 是并发未跟踪文件触发正确守卫，非代码失败。历史 JSON 哈希见附件 |
| r2 F2 | 接受数字漂移，修正文档 | 原 538=292+93+153，F2 建议的 285 不正确；本次新增 26 后 564=318+93+153；#84 初始529明确标为历史 |
| r2 F3 | 接受低层连接管理合并，拒绝直接复用高层异常策略 | repository.task_database/task_transaction；read-only/BEGIN IMMEDIATE、commit/rollback/close 保留，各入口原有异常处理原位保留，未扩大 AttemptService 捕获范围 |
| r2 F5 | 接受内部 Stage 与边界校验集中 | rules.is_stage/require_stage；query 仍 isinstance 接受 str 子类与 StrEnum 且规范返回普通 str，query_successes 仍严格 type(str) 拒绝；不可 hash 输入报 invalid_request |
| r2 F7 | 接受；共享 EXECUTOR_FAILURES/is_executor_failure | run_once 非法结果仍 protocol_error，直接 fail 仍 invalid_failure；output_invalid/model_mismatch/outcome_unknown 不能由 executor 伪造 |
| r2 F8 | 观察/延期（与原报告建议一致） | 通用验收框架会扩大冻结组及绑定范围，本次不引入跨组重构 |
| r2 F9 | 拒绝缺口判断 | test_a7_registration_migrations.py::test_task_dependencies_and_pure_rules_do_not_acquire_execution_authority 已覆盖反向依赖、网络/LLM、时钟/环境权限；已在 A7 固定6例内，无需复制 AST 测试 |
| r2 F10 | 接受非特权环境前提提示，纠正“root 假通过”表述 | 本次 EUID=1000；0500 权限测试在 root 会因实际可写导致应拒绝断言失败，不是假通过；既有存储测试同前提；不新增 skip 或放宽权限断言 |
| r2 Spec 1 | 接受；补全 A7-06/07/08 与 integration 波次台账 | a7-requirements.md 收口表；a7-history-ledger.json 逐提交/路径/绑定组/旧新 SHA，#83 无旧绑定也明确记录 |
| r2 Spec 2 | 成本前提成立，拒绝顶层探测/进程缓存建议 | prepare_publish 有界256既有 shard 实探；历史 review-fixes-red-namespace-shard.txt 证明真实0500 shard曾在executor调用后失败并占次数；顶层可写不能证明shard可写，权限可变使缓存重开缺陷；无证据删除fsync |
| r2 Spec 3 | 接受可复核性建议，使用不自绑定历史索引 | 附件含历史提交、逐条绑定、原ledger路径哈希及三次历史run的十一份JSON哈希；完整原JSON仅本地verification-runs；本次最终run_id留外部记录避免循环 |

| 聚合核验 | 独立核实结论 |
| --- | --- |
| G1 | 确认推翻F1的主要前提；47dec58有6e818通过，当前工作树变化不否定历史 |
| G2 | 确认并修复；529→535→535→536→538漂移始于72f9938，旧业务小计为292 |
| G3 | 确认推翻F9；现有AST守卫确在registration_migrations模块且固定登记 |
| G4 | 确认台账缺口；本次补齐路径、理由、绑定组及无绑定波次 |
| G5 | 确认成本：领取前最多256既有槽位，每探针有实际建目录/硬链接/fsync；保留安全行为 |
| G6 | 确认原仓库无外部ledger；新增可复核历史附件，明确本地原JSON边界 |

新增 `test_a7_text_boundaries.py` 人工固定26例：UTF-8字节边界、未配对surrogate、
空白和HTML策略覆盖manual/retry/audit三入口，另含字符串子类/StrEnum/不可hash阶段输入。
这是既有公共行为的特征回归；本次未声称发现新语义Bug，不伪造 red→green 证据。
纯整理继续由既有登记、领取、租约、成功、三值适用性、retry、恢复及真实进程回归验证。
最终门禁通过事实、候选提交和本次run_id以外部交接记录为准，不写回已冻结的tracked内容。

未验证 live/RPC/Pi/真实模型用量、语言事实生产来源（该来源后于 2026-10-27 由 ADR-0035 裁决为
Feed 归属；本记录不改写）、完整资格/每日配额/编排、
建议/校准、CLI、NAS 与完整阶段A。N+1性能和跨组验收器通用化留后续有测量依据时处理。
