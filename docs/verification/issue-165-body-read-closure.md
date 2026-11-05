# Body 工程覆盖与最终门禁判据（#165）

本台账绑定 #155 全部七条裁决评论及 #165 补充，冻结工程覆盖、证据适用性与最终门禁判据。
完整验收结论只发布于全部合并、独立审阅修复及身份材料冻结后的树外回执与 Issue 闭票回帖；
本文本身不宣称未运行的完整门禁已 passed。`stage_a_verified=false`。
开发期 pytest、scope/兼容检查、#164 单样本工程 smoke 与最终完整门禁分别记账，不能相互替代。
最终门禁只由唯一执行者在独立 review/fix 后的冻结树以 extra+dev 运行；同次退出 0 且
冷查询为 passed/verified/same 才能发布该树结论。HEAD、目标或任何受身份约束材料变化均重新证明，
最终 run_id 留树外，不回写本台账或材料 JSON。

## 公共边界与组合保证

测试的公共 seams 已在 #155 Testing Decisions 与会话确认：BodyService、真实元数据
JGRMetadata、ReadTasks、ReadExecution、ReadQueries、ArtifactStore、FulltextArtifacts、
backup verify/restore。重用合成配置、真实供给登记和真实 Screening 成功引用；HTTP 仅为固定
外部元数据响应，Docling parser 和 Pi 的独立进程为外部执行替身。Pi 工程准入沿 #162 的私有
工程 seam 注入，不增加公开证据/开关；产品 read_evidence 仍恒 None，缺证据仍领取前拒绝。
无真实论文内容、模型调用、PDF 实测或网络请求进入公共测试。

- 正常与末次降级均从真实持久 PDF/正文、样本、人工决定及 metadata 路线取得资格，经
  ReadExecution 的真实协议/进程、ReadTasks 的唯一 v2 接收和 ReadQueries 的安全展示。
- 首次坏指针是 output_invalid；末次按持久 ordinal 丢整项并保存规则/策略/丢弃清单。
  test 来源与 pi_rpc、根用途和质量是独立事实，实验可见而 ordinary 拒绝，Body 不产生 formal_gate。
- 后续决定、质量否决、PDF 与 metadata 变化均在实际模型调用前拒绝，不花 attempt；
  样本缺失、实际完整 Unicode 正文超额也无任务/analysis。准入拒绝先于认证与领取；
  已通过准入后的最新业务前置复核在认证准备之后，不能把“模型前拒绝”写成“认证前拒绝”。
- 同 request_id 精确登记重放在后来决定、PDF、质量或样本变化后仍返回原任务，
  数据库字节保持；五项参数任一变化先返回 request_conflict，新登记与新领取仍核验当前资格。
  历史 metadata 不能把后来 acquisition 拼到较早完整修订；validate_all 受控拒绝，
  backup 返回 registration_invalid；正常早晚两次完整修订均可验证。
- Docling 版本拒绝用固定外部发行包/模块发现事实驱动真实 probe，extra/base 结果一致。
  真实 base 子进程另执行未模拟的 probe 并断言 dependency_missing；extra 主验的
  worker/model/core 映射保持真实 probe，未知内容层明确断言永久质量失败。
- 文件 hard-link 前/后故障和 analysis/evidence 事务前故障均没有半条分析，已领预算不退款；
  DBAPI 已 commit 而回执丢失时唯一分析可回查；并发执行只有一个成功。失败终态的 retry 唯一，
  过期查询不回收，显式 reclaim 才追加 outcome_unknown，旧 token 不能提交。
- 两个独立真实 base 冷进程：第一进程屏蔽原根/改名根并 verify、restore、verify_contents 后搬迁；
  第二进程再屏蔽旧恢复路径与批次，只从搬迁目标回查。每个路径拒绝探针实际命中。
  no-extra 解释器由共享 `tests/no_extra_runtime.py` / `PAPERRADAR_NO_EXTRA_PYTHON` 提供，
  同 Python minor、源码指向当前 ROOT，实际未安装 SDK；不以 importguard 冒充缺依赖。
- 比对所有公开制品角色的完整字节（PDF、document/manifest/reading/evidence_map、候选与其他源），
  逐字回放 `Exact source α = 2.`；比较配置完整持久载荷、三规则、策略/ordinal/discards、
  全部 attempt/basis/metadata_basis/预算、质量、根用途、人工/样本与 metadata 历史引用。
  zh/en 并存、正文 current/配置 old、old 列表、降级标记计数和未结算租约恢复前后相同。
  第二进程的连接强制 mode=ro，禁 SDK/网络/子进程，查询前后全树 SHA 相同，无激活或回收。
- 缺/改 evidence_map 成员分别 file_missing/file_corrupt；同指纹、同 evidence ID 的另一份正文、
  策略、ordinal、丢弃和历史依据损坏均 registration_invalid；未知证据规则独立
  unsupported_rule_version。未知警告策略保留已记警告，不声明当前等价。合成 v1 历史按 v1 恢复，
  不增产品历史导入 API。Docling/Read 根锁均不登记、不进入备份，恢复不要求它们存在。

## 独立 D1 人工预期

以下数量在 collect 前按已有子票台账及新增参数矩阵人工核对；collect 只验证，不反填预期。
全部模块独立未绑定，不进入 A1–A10 required/固定分母，skip/deselect/incomplete 不算通过。

| 模块 | 预期节点 | 责任 |
| --- | ---: | --- |
| tests/test_fulltext_artifacts.py | 10 | #156 源成员与质量 |
| tests/test_fulltext_normalization.py | 7 | #156 文档信号、顺序、受限块 |
| tests/test_fulltext_quality.py | 10 | #156 公开质量原因与可靠性 |
| tests/test_fulltext_restore.py | 4 | #156 源字节/身份恢复 |
| tests/test_read_acceptance_v2.py | 42 | #157 v2 末次接收 |
| tests/test_read_acceptance_v2_compatibility.py | 26 | #157 两版等同与差异 |
| tests/test_body_facts.py | 13 | #158 根/PDF/决定/样本 |
| tests/test_body_extraction.py | 21 | #158 提取预算/质量 |
| tests/test_body_concurrency.py | 5 | #158 真实根锁竞争 |
| tests/test_body_recovery.py | 8 | #158 业务闭包恢复 |
| tests/test_body_migrations.py | 3 | #158 feed07→body01 |
| tests/test_body_privacy.py | 1 | #158 安全日志 |
| tests/test_docling_executor.py | 23 | #159 受限 worker、失败与资源 |
| tests/test_docling_mapping.py | 5 | #159 真实 docling-core 映射，不跳过 |
| tests/test_docling_manifest_compatibility.py | 2 | #159 历史 manifest 字节 |
| tests/test_docling_cold_import.py | 1 | #159 延迟导入 |
| tests/test_no_extra_runtime.py | 1 | #159 实际 base 端口 |
| tests/test_docling_executor_recovery.py | 2 | #159 执行审计冷恢复 |
| tests/test_read_stage_input.py | 27 | #160 Read 身份与纯层回放 |
| tests/test_read_inputs.py | 10 | #160 持久正文/渲染/完整帧 |
| tests/test_read_tasks.py | 5 | #161 接收与修正 |
| tests/test_read_tasks_leases.py | 6 | #161 lease/retry/唯一成功 |
| tests/test_read_tasks_preconditions.py | 15 | #161 同事务实际前置与精确登记重放 |
| tests/test_read_tasks_execution.py | 5 | #161 来源与模型审计 |
| tests/test_read_tasks_recovery.py | 20 | #161 候选/规则/历史依据恢复及跨修订来源拒绝 |
| tests/test_read_tasks_migrations.py | 3 | #161 body01→body02 |
| tests/test_read_execution_admission.py | 18 | #162 产品拒绝/顺序 |
| tests/test_read_execution_rpc.py | 14 | #162 独立协议进程 |
| tests/test_read_execution_resources.py | 7 | #162 锁/认证/安装保护 |
| tests/test_read_execution_history.py | 7 | #162 审计配置与历史 |
| tests/test_read_execution_logging.py | 2 | #162 日志与私密性 |
| tests/test_read_queries.py | 7 | #163 正文轴与安全展示 |
| tests/test_read_query_config.py | 13 | #163 配置轴与语言 |
| tests/test_read_query_readonly.py | 2 | #163 零写与历史依据 |
| tests/test_read_query_recovery.py | 1 | #163 双轴冷恢复 |
| tests/test_body_read_closure.py | 16 | #165 跨消费者正常/降级、拒绝、故障、并发与恢复纪律 |
| tests/test_body_read_closure_integrity.py | 12 | #165 完整 Pi 分析批次的逐类损坏及 v1/未知警告策略 |
| tests/test_body_read_closure_recovery.py | 2 | #165 正常/降级的两次实际 base 冷进程全闭包 |
| 合计 | 376 | 38 个独立模块；不作为旧组覆盖计数 |

## 34 条用户故事逐项处置

表内 `模块::用例` 均为实际 pytest 入口（省略 tests/ 前缀）；参数化行覆盖该用例的全部节点。
故事 2/12 的收缩依据是 #155 评论 2/5，不能声称 DOI 内容归属检测或裁切渲染已交付。

| 故事 | 实际覆盖或明确下游 |
| --- | --- |
| 1 合法 PDF 附加 | test_body_facts.py::test_root_is_immutable_and_pdf_selection_survives_restart；test_body_read_closure.py::test_pdf_to_pi_analysis_is_visible_only_for_experiment |
| 2 版本关联/DOI | test_body_facts.py::test_invalid_pdf_does_not_append_selection；显式 paper/version 与文件签名/体积/哈希已验，无法证明内容归属；DOI 检测候选移交 B/F 取得入口 |
| 3 不同 PDF 保留 | test_body_facts.py::test_frozen_sample_keeps_history_and_rejects_changed_pdf；test_read_query_readonly.py::test_later_decision_quality_and_metadata_do_not_erase_legal_history |
| 4 延迟 SDK | test_docling_cold_import.py；test_body_read_closure_recovery.py::test_full_business_bytes_and_queries_survive_two_no_extra_cold_processes |
| 5 共用诊断 | test_docling_executor.py::test_runtime_probe_refusal_never_claims |
| 6 ABI/缓存独立 | test_docling_executor.py::test_real_worker_settles_import_and_allocation_failures_safely、test_deployment_refusal_never_claims；现场具体失败未触发，B/F 承接 |
| 7 冻结工具链/模型 | test_docling_executor.py::test_model_hash_refusal_precedes_lock_without_claim、test_prepared_models_survive_later_deployment_changes；真实冻结单样本见 #164 |
| 8 文档信号/C1 | test_fulltext_normalization.py::test_cover_margins_hierarchy_cross_page_and_restricted_sources；test_read_stage_input.py::test_pdf_changes_read_while_bibliographic_completion_cannot_enter_facts；真实四刊由 F |
| 9 顺序/层级 | test_docling_mapping.py::test_tree_order_all_provenance_orig_and_candidates_are_preserved；#164 逐项配对，不推论四刊 |
| 10 provenance | test_docling_mapping.py::test_bad_charspan_is_preserved_and_rejected_by_public_artifact_quality；test_body_read_closure_recovery.py 全逐字闭包 |
| 11 orig/候选分离 | test_fulltext_normalization.py::test_generated_candidate_cannot_introduce_an_evidence_anchor；test_read_inputs.py::test_generated_formula_and_placeholder_have_no_evidence_anchor |
| 12 公式裁切入口 | test_fulltext_normalization.py::test_cover_margins_hierarchy_cross_page_and_restricted_sources 保存页码/bbox/占位；PDF 裁切渲染与人工展示归 B/F，Body 无截图入口 |
| 13 受限内容 | test_read_acceptance_v2.py::test_restricted_sources_and_numeric_limitations_only_warn；test_read_queries.py::test_restricted_source_warning_survives_safe_dto；B/H 显著展示 |
| 14 无文本/质量停止 | test_body_read_closure.py::test_permanent_body_failure_cannot_produce_read_analysis、test_later_prerequisite_change_denies_model_execution_without_budget |
| 15 资源与峰值 | test_docling_executor.py::test_supervisor_timeout_reaps_descendants_and_measures_worker_peak、test_virtual_address_limit_is_enforced_without_loading_sdk；#164 双口径峰值，F 通用阈值 |
| 16 两次提取预算 | test_body_extraction.py::test_retry_budget_is_shared_across_papers_and_restarts；test_body_read_closure.py::test_permanent_body_failure_cannot_produce_read_analysis |
| 17 逐用途质量 | test_body_read_closure.py::test_missing_sample_stops_before_any_execution_or_task；test_body_facts.py::test_production_upstream_allows_only_matching_experiment_sample_and_test_wins；F formal/B 真核查 |
| 18 内容身份 | test_read_inputs.py::test_prepare_rejects_swapped_body_identity_before_call；test_body_read_closure_integrity.py::test_complete_pi_backup_refuses_specific_integrity_damage[cross_body-registration_invalid] |
| 19 zh/en 独立 | test_body_read_closure_recovery.py::test_full_business_bytes_and_queries_survive_two_no_extra_cold_processes；test_read_query_config.py::test_latest_success_uses_commit_order_and_idempotent_replay_does_not_replace |
| 20 Read 不污染 Screening | test_read_stage_input.py::test_read_model_change_preserves_screening_calibration_and_historical_replay |
| 21 书目不重跑 | test_read_query_readonly.py::test_later_decision_quality_and_metadata_do_not_erase_legal_history；test_read_stage_input.py::test_pdf_changes_read_while_bibliographic_completion_cannot_enter_facts |
| 22 PDF 当前性 | test_read_queries.py::test_current_version_without_pdf_cannot_borrow_previous_version_body；test_body_read_closure.py::test_later_prerequisite_change_denies_model_execution_without_budget[pdf] |
| 23 持久预算 | test_read_tasks_preconditions.py::test_a_b_a_snapshot_language_and_labels_do_not_refill_budget；test_body_read_closure_recovery.py 全预算/lease 原样 |
| 24 lease/修正/retry | test_body_read_closure.py::test_failed_generation_retry_and_expired_lease_preserve_query_truth；test_read_execution_rpc.py::test_first_reject_then_last_correction_uses_two_distinct_processes_and_one_analysis |
| 25 超额拒绝 | test_body_read_closure.py::test_complete_persisted_body_over_frame_limit_has_no_read_task_or_analysis；test_read_inputs.py::test_budget_reserves_worst_second_frame_before_first_claim |
| 26 独立会话 | test_read_execution_rpc.py::test_first_reject_then_last_correction_uses_two_distinct_processes_and_one_analysis；真实 Pi 现场归 Cwd/Live/B |
| 27 权威接收 | test_read_tasks.py::test_invalid_pointer_then_final_degradation_uses_persisted_ordinal、test_final_attempt_never_accepts_empty_support_or_invalid_score_reason；冻结 A9 仅历史 v1 |
| 28 历史解释 | test_body_read_closure_recovery.py 全成员/metadata_basis/决定/配置；test_body_read_closure_integrity.py 的未知警告策略与 v1 历史 |
| 29 崩溃/唯一成功 | test_body_read_closure.py::test_file_and_database_faults_never_leave_half_or_duplicate_analysis、test_concurrent_explicit_execution_has_one_success_and_one_spent_attempt |
| 30 异地回查/预算 | test_body_read_closure_recovery.py::test_full_business_bytes_and_queries_survive_two_no_extra_cold_processes |
| 31 实验不提升 | test_body_read_closure.py::test_pdf_to_pi_analysis_is_visible_only_for_experiment；test_body_read_closure_recovery.py 搬迁后 ordinary 拒绝，test 英文保留 |
| 32 同资格/可见性/查询 | test_body_read_closure.py 后续前置拒绝；test_read_query_readonly.py::test_all_query_entries_use_visibility_and_zero_write_connections；完整隐藏事实由 C/D 扩展 |
| 33 安全日志 | test_read_execution_logging.py::test_file_sink_is_explicit_and_events_have_only_safe_closed_fields、test_sink_failure_does_not_retry_or_change_analysis；test_body_privacy.py；B 注入所选根文件汇 |
| 34 独立覆盖与未验 | 本 38 模块人工预期、逐故事表与[材料清单](issue-165-body-read-materials.json)；旧分母、A9、41 fixture 与 S3 另核对 |

## Migration 与登记口径

相对 main 的 feed07→body02 是一次最终集成 head 推进；保留 body01/body02 两个线性节点原字节，
不压缩、不重写、不造第三 revision。子票开发验证不冒称已各做一次历史十组 S3。
人工 `EXPECTED_MIGRATION_REVISION`、十 scope `MIGRATION_REVISION`、A3 backup_database_revision、
生产 BACKUP_DATABASE_REVISION、artifact-store/backup-restore 两 Contract 均为 body02。
旧 migration 字节保持。最终实现者对相对 main 的实际字节/用途/旧新成员/计数/格式及全部下游
逐项审阅，审阅主体为 agent，授权来自 #165 的 migration/实际消费者窄例外及会话两次 A5 明确批准；
不声称用户亲自签过最终 SHA。确认输入放树外并绑定当时完整身份，不能复用 811 预审。

只重绑 10 路径/21 展开登记：中央 a5_acceptance、llm/models、stage_inputs/__init__、stage_inputs/service、
storage/schema 五键，A5 四测试字面量与 A8 llm/calls 一个字面量；已有五中央键与十 scope head 保留。
a5_acceptance 的四阶段格式选择影响验收语义，人工另审 A5/A6/A7/A8/A9/A10 六组：
原四阶段格式检查及异常向量、材料哈希循环和 14 模块/529 不变，新增 Read 仅进 D1，不能因
工具机械标签豁免。A5 四模块五处保持 20/33/38/106。A9 十 v1 源码、十五测试及 560、
格式/capabilities、41 旧 fixture 与 A8 向量字节保持；scope 元数据仅迁移窄例外。
审计器/registry/baseline/collection 不修改，11 旧组成员/分母/required、41 refs 不扩展。

共享 schema 修复补齐 Body/Read 的 18 个完整 Table，查询模块只引用共享定义；
冷导入不依赖上层业务模块。字段类型、SQLite 原生主键的 nullable、外键、唯一与 CHECK
均描述 body01/body02 既有 DDL，包含 executor_audit_json，不新增或改写 migration。
回归 seam 为既有 `test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`，
冻结测试原字节保留，不过滤多余表，也不从数据库反射生成声明；D1 38 模块/376 不变。
storage/schema 原已作为 source 登记于 A2-01、完整 A2、A3、A4、A7、A10，传递影响十组；
仅在本次 migration/实际消费者窄例外内重绑这一中央 source 键的六处展开登记。
旧配置与制品表定义保持，Body/Read 查询别名、预算/历史/恢复通过实际服务组合另验。
原门禁失败事实保留树外，新身份必须重新取得同次完整门禁结论，不能复用失败前的确认。

[独立材料 JSON](issue-165-body-read-materials.json)逐精确路径保存 SHA 与用途，覆盖新业务闭包、
ADR 状态、新 Contract、测试/支撑/向量和 #164 证据。未知文档仍固定，不扩 live exact_paths，
不修改冻结分类测试。JSON 不哈希自身，不存 run_id；其自身容器由最终 HEAD/完整树身份保护。

## 实测证据与后续责任

开发检查的最终实际命令/结果、scope 身份和逐项确认在树外报告；本文件先冻结工程判据，
不把未执行的最终门禁写成 passed。#164 的真实执行绑定历史 811 身份，不能转用到本次新 HEAD。
真实 SDK 16 页、216 源、139 evidence、147 切片、unknown 公式 1/父源 1、map 353471 bytes；
行间/行内均零样本，不能解释为 PDF 没有行内公式。质量仍 absent、Read 未运行，
worker/cgroup 峰值分列；范围和原始哈希见[单样本报告](issue-164-docling-smoke.md)。

| 移交模块 | 必须补足 | 入口 |
| --- | --- | --- |
| B | 实验根/选样/决定/PDF/执行/retry/trace 产品命令，真实 metadata 与人工六项版式，注入文件汇，最小日报展示未核对/丢弃各类计数，真实全链和暴露清单；不把合成 pi_rpc 当准入 | [B](../roadmap.md#module-b) |
| B/C | 纯人工 accepted 无 Screening 引用仍 unknown；专用人工通道及后续显式正文选择另扩展，不猜最新成功 | [B](../roadmap.md#module-b)、[C](../roadmap.md#module-c) |
| F | 四刊/中文/复杂版式 fixture、公式行间/行内/无父源类别、PDF 裁切渲染与摘录、代表性资源阈值、formal_gate | [F](../roadmap.md#module-f) |
| G | 通用 section/paragraph map/reduce、自动队列/每日配额、pending/denied 人工请求原子 accepted | [G](../roadmap.md#module-g) |
| H | 完整日报/单篇报告展示、受限内容未核对标记与逐类丢弃计数 | [H](../roadmap.md#module-h) |
| Cwd/Live/I | Pi 现场权限/出站/RPC/参数实测与 NAS；本台账无这些结论 | [Cwd](../roadmap.md#module-cwd)、[Live](../roadmap.md#module-live)、[I](../roadmap.md#module-i) |

未验证：四刊质量、Pi 现场、真实模型科学质量、B 当轮全链、正常生产 Read、正式校准、
NAS 与完整阶段 A；#164 单样本不能覆盖上述范围。
