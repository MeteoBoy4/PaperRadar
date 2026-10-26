# A10 #107 需求与测试映射

基线为 #100 正文及六条评论、#107 正文及「完整闭包」评论。用户于 2026-10-26 明确前七票只验证行为子集；本表是 #108 收口入口，不是 A10 / live / 阶段 A 通过记录。测试仅经已批准公共服务、真实 SQLite/migration/ArtifactStore/backup-restore seam；外部 HTTP 和等待时钟用合成输入。原始红绿与实际运行结果保存在 `/tmp/paperradar-a10-context/107-*.txt`，最终数字以 `107-result.md` 为准。

## #107 逐项验收

| 规格 | 实际证明 | 测试入口 |
| --- | --- | --- |
| AC1 完成计划、准确汇总、Feed SHA，拒绝错刊/成员/策略/通道/材料；差结果可登记 | complete + 四刊集合/单刊绑定；错计划/汇总/成员/刊/集合/单SHA、缺材料/根、parser/条件头拒绝；混合不足/失败仍可登记 | `test_fixture_audit_references.py` 的 complete/invalid/partial/missing/request 用例；`test_a10_complete_recovery.py::test_mixed_wal_history_restores_with_denied_sources_and_moves_between_processes`；策略/通道闭包沿 `test_audit_acquisition_recovery.py` |
| AC2 register/check/list/show 与 replay 同依据/核验程度、替换追加 | CLI 与服务比较相同安全投影；有/无 data_root 分级；新声明/replaces 保留旧字节/plan/hash；同计划后续 resume 旧汇总稳定 | references 文件 complete/CLI/proof/replacement/historical-summary 用例 |
| AC3 真实非空 a704 → 单一 a1001 | Alembic 真建 a704，按旧 schema 实际列装入公开服务已产生的配置/Pi/2 Paper/Screening 成功、2失败和retry；升级前后所有旧表旧列值与公共投影逐值相等，FK检查为空，二次升级幂等 | `test_a10_complete_recovery.py::test_real_a704_config_pi_paper_screening_success_failure_retry_upgrade`、`a10_recovery_support.py::upgraded_legacy`；schema/metadata 沿 `test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata` |
| AC4 validate_all 固定副本完整语义闭包 | 已有来源/成员/矩阵/parser核验继续接入；新增完整汇总边界及 fixture引用核验；checkpoint/声明同事务原子，材料回放在写锁外 | references 的 captured-complete/rollback 用例；`test_a10_reference_recovery.py`；既有 acquisition/sampling/matrix/resume recovery 子集 |
| AC5 活跃 WAL 同库全混合历史、禁原目录/禁网/移根/换进程 | 同一个真实升级库中追加历史种子、PDF旧新字节及旧backend、四刊混合、unsupported agency、render未安装、选样暂停、started中断/unknown/resume、v2、共享source_snapshot及未引用制品；WAL最后提交进入同批次；独立worker禁止原/改名目录，sitecustomize禁socket；移动恢复根后二进程再次对比稳定公共投影和受控原文哈希 | mixed WAL 用例 + `a10_recovery_reader.py`；只传 ID/哈希，不传恢复正文 |
| AC6 恢复无执行副作用、以后继续仍需显式身份核对 | worker核验逻辑SQL与文件树不变、无lock/.tools、无激活或续跑；恢复不探测安装；原材料/网络封锁；未来resume规则沿106 | mixed WAL worker；`test_audit_resume.py`/`test_audit_resume_cli.py`/`test_audit_resume_recovery.py`（本票只跑必要相关文件） |
| AC7 format1、自包含、声明原字节、未知PDF不伪缺件 | 既有备份布局不改；恢复读取声明原字节/材料，不依赖源码声明；未取得PDF仍无字节事实 | mixed WAL、`test_fixture_recovery.py`、`test_fixture_pdf_recovery.py`、`test_fixture_registry.py` |
| AC8 旧批次匹配程序恢复后显式upgrade；共享去重GC注记 | 当前manifest revision保证不扩大；真实a704工作库升级单独证明；audit/Paper同字节source_snapshot同一artifact ID；文档明确旧批次路径及双类GC引用 | migration/mixed WAL；Contract/ADR0034。未在本票重跑旧发布程序verify旧备份，无此新增保证 |
| AC9 内外重哈希语义篡改、verify不修复/restore不发布 | 8类新增：错snapshot/summary/journal/member、原声明字节、checkpoint矩阵/settlement、跨逻辑replacement；再加parser version解释篡改；内部声明/记录ID可同步重算，外层SQLite SHA重算，FK仍有效；verify前后树不变，restore目标不存在 | `test_a10_reference_recovery.py` 9参数；来源身份/成员/策略/channel/候选闭包沿既有 recovery 负例 |
| AC10 邮箱/Cookie/secret 隔离 | 合成HTTP UA邮箱、成功Set-Cookie、失败页secret；扫描原SQLite/WAL/材料/批次/恢复树及CLI/repr/异常；受控摘要只读内部比哈希，普通输出也不含原摘要/v2文本 | mixed WAL + reader；解码后联系信息响应拒绝沿 `test_audit_acquisition_recovery.py` |
| AC11 每条规格/评论映射、少量同库代表材料 | 本表；1 Pi供给、2旧论文、1任务成功、2次失败+1retry、少量混合计划；不复制A1–A9整套工厂 | 本文件、`a10_recovery_support.py` |
| AC12 前七票子集、Python统一uv | 所有Python验证 `uv run --offline --locked`；最终子集/Ruff/mypy结果见107-result；无full check-offline/scope变更 | 107日志；#108仍须同次完整门禁 |
| AC13 Contract/CLI同步、live边界 | README/GLOSSARY/ADR0034/draft、fixture及backup Contract与中文CLI帮助；不注册A10、不改父票、不live | reference CLI用例及相关既有帮助子集；文档审阅 |

## #107 补充评论

| 澄清 | 对应证明 |
| --- | --- |
| 合法未引用source_snapshot/original_pdf不能判坏或补成功 | mixed WAL显式用ArtifactStore发布两份无业务引用完整制品，恢复后仍可读取；路由/成员投影未凭制品增补；无GC |
| 源声明不存在为独立状态 | complete引用用例及worker断言 source_missing；list/show/replay及validate正常；无重新登记/刷新时间 |
| feed绑定plan+journal+snapshot，abstract整计划+准确summary+四刊集合；whole plan complete才可登记 | 模型强制abstract_audit journal=null（可省略）；引用拒绝任一刊SHA代整轮及partial；旧用途刊名保持必填有意义 |
| 稳定投影比较而非绝对路径/恢复时间 | 公共ID/时间/字节哈希、成员顺序/候选/解释/汇总投影；Pi安装绝对路径只作为历史事实保留，不探测或重写 |
| 同计划合法resume不使旧完整引用失效 | 一致只读预捕获、短事务checkpoint+声明原子登记；pre-write窗口追加和故障回滚正例；旧边界按显式执行/settlement/矩阵/采样引用恢复，不猜前缀 |

## #100 需求继承与剩余范围

下表覆盖父票 User Stories 1–44、Testing Decisions 全部验收面及六条评论；本票不重做前六票。现有测试按文件列出，#108需登记真实用例名/数量与哈希、绑定实际复用A6模块及同次可信终态。

| 父票需求/验收面 | 已有实际测试或本票接续 | 本票外范围 |
| --- | --- | --- |
| US1–3 底座、固定四刊/current；Feed与身份 | fixture_registry、audit_http、audit_sampling* | live入口稳定性/跨次entry ID假设待真实来源 |
| US4–9 注册性质、历史种子、PDF、替换；注册类型/历史种子/PDF格式 | fixture_registry/fixture_pdf* + 本票references/mixed | Docling/许可/正文质量未实测 |
| US10–11 联系信息、显式执行；联系信息/CLI权限 | audit_cli/audit_matrix_cli/audit_resume_cli、acquisition_recovery + 本票CLI/worker | 本票无live执行；日志平台不新增 |
| US12–15 固定原位次/类别/不足；固定选样 | audit_sampling、boundaries/categories/feed_safety/recovery；本票混合暂停 | 四刊真实5–10篇仍需显式指令 |
| US16–22 全路线、有界HTTP、阻断、正确身份；路线覆盖/HTTP上限 | audit_acquisition/audit_http/audit_matrix_boundaries/recovery + mixed | 浏览器/授权/官方API/仓储运行时未交付 |
| US23–28 原字节、严格解析、五类截断、仲裁、分母；严格解析/截断与仲裁/汇总分母/原始依据 | audit_matrix/boundaries/recovery、audit_replay + 本票引用核验和恢复原文哈希 | 来源长期稳定判据/阶段B降级批准未裁决 |
| US29–32 partial、幂等、补跑、新轮；中断与竞争 | audit_resume/atomicity/processes/replay + 本票checkpoint合法append/原子性 | 本票不重复106真实进程锁/kill矩阵；仍沿已交付边界 |
| US33–37 去重、隐私、分级回放、追踪、新解释；版本化回放 | acquisition/matrix/resume_recovery、audit_reinterpret + 本票mixed/reader/9类篡改 | v2仅显式注入测试parser，默认backup不冒称重解析 |
| US38 生产隔离 | audit_matrix、audit_sampling + 本票同库共享source_snapshot为显式合成Paper写入，审计不调用生产导入 | 真实生产Feed Adapter/metadata_ready/Screening/校准不交付 |
| US39–40 WAL/迁移/隔离与语义篡改 | 本票complete_recovery/reference_recovery + 既有recovery文件 | NAS/旧发布程序live恢复未验 |
| US41 受限材料不自动公开；CLI权限 | 服务受控read_audit_text，普通CLI无原文；mixed worker扫描 | 无一键导出/公开；真实材料公开许可须另行判断 |
| US42–44 完整/稳定/就绪分离、独立结论、剩余阶段A；独立结论 | fixture/audit CLI、Contract范围注记、本映射 | scope/状态/组分母/同次完整check-offline全部归108；不复用旧通过抵扣 |
| 评论0 实施澄清/短事务/隐私/非空旧升级/完整恢复 | 上述107 AC3–6/9–10；既有取得事务和进程测试沿106 | 非本票测试面登记归108 |
| 评论1 类别封闭表/doiRA/主摘要边界/双权威 | ADR0033/0034、sampling_categories/matrix_boundaries + 本票恢复这些事实 | 未将测试材料当本轮live |
| 评论2 四刊预检/风险注记 | historical-v1注记与registry测试；本票保留原声明字节 | 预检不是live结论、AMS403未解决 |
| 评论3 获取限制改为版本策略/独立通道/敏感信息 | acquisition*、matrix route_summaries、mixed/篡改 | 凭据读取/渲染能力不新增 |
| 评论4 总门禁成本/版本/schema/ADR/目录/A6复用 | 本票单一a1001及新边界表真实重建；docs/ADR更新，固定fixtures/a10，A6源码不改 | A8/A9重绑、A10 FORMAT/SOURCE/FIXTURE/DEPENDENCY登记与同次全量归108 |
| 评论5 A10只留渲染枚举/接口，channel_not_installed独立 | acquisition通道测试/matrix/本票恢复与篡改；无依赖/lockfile变化 | browser运行时仍待阶段F；AMS403与长期稳定仍待live |
