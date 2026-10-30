# A 窄收口覆盖台账

本页登记 [#120](https://github.com/MeteoBoy4/PaperRadar/issues/120) 的独立工程覆盖。
`passed` 仅指所列公共行为的离线测试；`deferred` 指向后续消费者；`not_assessed`
保留真实环境与最终工单证据的边界。历史 A1–A10 通过不扩展为本轮新能力通过。
新增测试不加入既有 required 组或固定分母，不改 verification_status 后缀白名单、
「十四份 JSON」及历史 `stage_a_verified=false`；机器可读新组与完整 A 结论留 A 真正收口
（或 #112 之后），B 沿用此规则。全部独立模块均在 `tests/` 下。

## 用户故事 → 公共接口 → 独立测试 → 未验项

| 用户故事 | 公共接口 | 独立模块／节点与窄范围结论 | 未验项／承接 |
| --- | --- | --- | --- |
| US1 | doctor basic/config | passed：test_doctor_readonly.py::test_basic_current_database_passes_readonly；test_doctor_process.py::test_database_failures_are_controlled_and_readonly | not_assessed：真实环境、Pi/Live/Cwd |
| US2 | doctor 检查四态与进程汇总 | passed：test_doctor_readonly.py；test_doctor_process.py::test_invalid_packaged_migration_is_controlled | not_assessed：现场配置、来源审计；passed 不等于运行就绪 |
| US3 | doctor 原因与中文下一步 | passed：test_doctor_process.py::test_help_and_usage_errors_have_no_io_or_sensitive_echo、test_invalid_selection_never_writes_or_falls_back | not_assessed：真实故障 |
| US4 | doctor 显式 settings/snapshot 选择 | passed：test_doctor_process.py::test_selected_config_is_readonly_and_discloses_only_selected_models | not_assessed：用户历史库（未读取） |
| US5 | doctor 基础通过与配置缺项分离 | passed：test_doctor_readonly.py::test_config_missing_stages_passes_without_persisting_snapshot、test_invalid_selection_keeps_basic_passed | not_assessed：正式校准 |
| US6 | doctor 六阶段 readiness | passed：test_doctor_process.py::test_placeholder_or_unconfigured_slots_only_change_stage_readiness | not_assessed：真实 RPC、正文、正式校准 |
| US7 | doctor 分阶段数据外发说明 | passed：test_doctor_readonly.py::test_outbound_categories_follow_stage_data_boundary；所选模型用例 | not_assessed：真实模型外发 |
| US8 | doctor/help 成功与错误只读 | passed：test_doctor_process.py（冷进程禁外部 I/O）；test_a_narrow_composition.py::test_doctor_and_injected_task_queries_preserve_completed_business_bytes | not_assessed：现场环境；SQLite 内部 sidecar 不计业务变更 |
| US9 | doctor 配置／安装／运行证据分离 | passed：test_doctor_process.py::test_valid_pi_supply_output_matches_frozen_baseline_bytes；test_doctor_readonly.py 的九类骨架 | not_assessed：Pi/Live/Cwd；deferred：Pi readiness 填证据 |
| US10 | ScreeningTasks、FixtureAudit、JGRFeed、JGRMetadata、FeedPipeline sink | passed：test_runtime_logging_tasks.py、test_runtime_logging_audit.py、test_runtime_logging_feed.py；test_a_narrow_composition.py 的 Feed→任务事件 | deferred：B 新执行入口逐个注入；not_assessed：生产现场 |
| US11 | stdout/stderr/持久日志三个输出去向 | passed：test_runtime_logging_files.py::test_event_whitelist_and_httpx_records_cannot_persist_payloads；test_runtime_logging_tasks.py；test_doctor_process.py | not_assessed：Pi/Live、真实来源 stderr/外发 |
| US12 | FileSink、audit run/resume | passed：test_runtime_logging_files.py::test_two_processes_rotate_without_lost_or_torn_events、test_capacity_evicts_only_oldest_owned_files；test_runtime_logging_entries.py | not_assessed：生产文件系统、NFS/CIFS |
| US13 | 日志故障与业务隔离 | passed：test_runtime_logging_files.py 的符号链接/部分写故障；test_a_narrow_composition.py 的 unwritable 组合保留业务成功与原字节 | not_assessed：生产磁盘/权限故障 |
| US14 | 成功提交、load_success、只读回查 | passed：test_runtime_logging_tasks.py::test_succeeded_is_observable_from_a_new_connection_before_event、test_commit_failure_cannot_emit_succeeded；test_runtime_logging_readonly.py | deferred：B/C/D/H 真实消费者；日志缺事件不等于业务失败 |
| US15 | evaluate_paper/evaluate_concept | passed：test_eligibility.py::test_batch_matches_trace_in_any_order_and_isolates_bad_paper；test_a_narrow_composition.py 全概念一致；test_eligibility_review.py 的通用 Read 前置与批量一致 | deferred：B/C/D/G/H/I 真实装配 |
| US16 | 人工优先、系统当前性、gate；质量×根用途×执行来源 | passed：test_eligibility.py::test_old_human_decision_wins_over_system_and_projection、test_system_decision_requires_current_artifact_basis_and_explicit_gate_enable、test_read_quality_and_root_purpose_matrix；test_eligibility_review.py 的系统 accepted 请求、人工优先/门禁及无请求实验单篇 | not_assessed：正式校准/真实来源；deferred：G 排名/名额/预算 |
| US17 | accepted 的 PDF/提取/Read 独立前置 | passed：test_eligibility.py::test_reference_harvest_failure_cannot_block_accepted_fulltext_or_read、test_accepted_pdf_and_extraction_demands_are_independent | deferred：E 生命周期、Body/F 正文、B/G Read |
| US18 | A7 applicability、旧人工依据、当前 PDF/提取引用 | passed：test_eligibility.py::test_old_fulltext_triggers_new_demand_and_cannot_supply_current_read、test_later_human_denial_blocks_old_request_without_removing_history、test_a7_success_projection_preserves_undeterminable_applicability；test_eligibility_review.py 的 A7 封闭类型及制品引用矛盾 | deferred：B/C/D/G 当前性装配 |
| US19 | evaluate_visibility：隐藏条件 OR/解除 | passed：test_calibration_visibility.py::test_each_hidden_condition_independently_restricts_ordinary_capabilities、test_partial_release_including_reveal_keeps_other_conditions_and_history | deferred：C 保留器/合并链、D 揭晓 |
| US20 | Visibility.permission：事实/任务可见，Agent 内容受限 | passed：test_calibration_visibility.py::test_synthetic_material_consumer_projects_only_permitted_content；test_a_narrow_composition.py 隐藏任务仍记 paper_id/stage | deferred：B show/trace/最小日报、C/D/H 实际字段裁剪 |
| US21 | 普通决定/精读请求与专用 review 许可 | passed：test_calibration_visibility.py::test_synthetic_actions_reject_before_write_with_controlled_receipts；test_eligibility.py::test_read_consumes_visibility_and_does_not_reimplement_hidden_action_rules | deferred：B/C/D 真实事务前守卫/review |
| US22 | build_call/render_request、任务/RPC 公共入口 | passed：test_t07_call_isolation.py（闭键、value topics、跨论文/阶段/attempt 修正隔离、冻结 Profile、unsupported stage INVALID_CONTEXT） | not_assessed：Pi/Live/Cwd；deferred：reuse/Read 合法生产执行器；详见 T07 映射 |
| US23 | D1 独立模块、台账、scope 与同次门禁判据 | passed：本表列出的独立公共行为及组合；scope 审计证明材料绑定，不能证明业务测试或门禁通过 | D01 实际运行结果唯一归最终工单记录；完整 A 结论未建立 |
| US24 | 默认 NullSink、纯规则支持范围与消费者责任 | passed：test_eligibility_architecture.py、test_calibration_visibility_architecture.py；test_runtime_logging_entries.py 仅守卫已交付入口；本组合 default 情形 | deferred：B 首接、C/D/H 真实隐藏及身份链；未来入口须扩守卫，不能称已验证 |

## I/T/D → 公共接口 → 独立测试 → 未验项

编号原文由[冻结收口表](stage-a-closure.md#原实施逐条处置)维护；本表只登记本轮窄范围。

| 编号 | 公共接口／本轮范围 | 独立证据与结论 | 未验项／承接 |
| --- | --- | --- | --- |
| I01 | 工程入口、独立测试与 D1 登记 | passed：test_a_narrow_composition.py；相关静态检查；最终门禁证明另见 D01 | 完整 A/I 验收不从子集推导 |
| I10 | evaluate_visibility/evaluate_paper/evaluate_concept | passed：test_calibration_visibility.py、test_eligibility.py 及各架构模块；组合全概念一致 | deferred：B 首消费、C 保留器/合并链、D/E/G/H 余下概念；非完整 I10 |
| I11 | doctor 与运行日志公共边界 | passed：test_doctor_readonly.py、test_doctor_process.py；六个 test_runtime_logging_*.py；test_a_narrow_composition.py | deferred：B 新入口、Pi readiness；not_assessed：现场 |
| T06 | doctor 无隐式供给/调用/写入 | passed：test_doctor_process.py 冷进程禁 I/O 与文件树/逻辑库比较；本组合只读查询 | deferred：B/I 真实 run-due 无隐式安装；NAS/恢复仍属 I 独立未验项，本行不证明完整恢复 |
| T07 | 当前 boundary/value 调用隔离及 unsupported stage 拒绝 | passed：test_t07_call_isolation.py；[逐子项映射](t07-call-isolation.md) | not_assessed：Pi/Live/Cwd；deferred：B/D/G 实际消费者，Read 无合法 builder |
| T16 | 共享可见性许可及合成消费 | passed：test_calibration_visibility.py；本组合隐藏任务明细仍记日志、Agent 原文不落盘 | deferred：B/C/D/H 实际隐藏，合成消费者不代表产品面 |
| T17 | 单篇与按概念批量资格 | passed：test_eligibility.py 的多原因/排列/坏论文隔离；本组合全概念一致；test_eligibility_review.py 的 read_prerequisites 与请求/队列分离 | deferred：B/C/D/G/H/I 真调度、名额、积压 |
| T22 | §8.7 三输出去向 | passed：test_runtime_logging_tasks.py、test_runtime_logging_files.py、test_doctor_process.py；本组合安全事件 | not_assessed：真实来源/Pi；阶段任务字段不按隐藏许可省略 |
| T23 | 共同回归：隐私、成功原制品与提交窗口 | passed：test_runtime_logging_tasks.py、test_runtime_logging_readonly.py；本组合只读回查与日志故障原字节 | 仅适用于本轮日志/可见性改动；deferred：B/C/D/H 消费者 |
| T24 | 共同回归：公共 CLI/只读组合与材料绑定 | passed：test_doctor_process.py、test_runtime_logging_entries.py、test_a_narrow_composition.py；compatibility all | 不冒充每模块新功能或 live 验收；deferred：后续真实入口 |
| D01 | 最终树同次完整离线门禁 | 判据：check-offline 返回 0，可信 terminal 全 required 通过，status=passed/applicability=same，十四 JSON，stage_a_verified=false | 本行不提供实际通过结论；实际 SHA/run_id/退出码/终态与原始日志只在 [#125 最终评论](https://github.com/MeteoBoy4/PaperRadar/issues/125) 和工作树外记录，发布须以该记录为准 |
| D03 | 基础通过与 Profile/模型缺项区分 | passed：test_doctor_readonly.py::test_config_missing_stages_passes_without_persisting_snapshot；test_doctor_process.py | not_assessed：正式校准/真实模型配置 |
| D04 | 单一规则权威及持续复用 | passed：两套纯规则及架构模块、三公共 Contract、本组合；D1 登记 | deferred：B 首消费与后续 C/D/E/G/H 持续复用，I 聚合；非完整 D04 |

## 组合证据与收口规则

`test_a_narrow_composition.py` 是独立公共组合模块：默认服务不建日志；显式根文件汇贯通
Feed/元数据/任务；日志目录拒写仍保留成功回执、一次 attempt 与原成功字节；真实公共结果
装配资格并核对单篇/批量一致；隐藏成员仍允许阶段任务明细，安全事件不含 Agent 原文。
这些用例没有让现有 trace 自动消费 visibility，也没有实现未来产品展示或动作服务。

`test_eligibility_review.py` 独立覆盖当前合法系统 accepted 只增请求、pending/denied 须
先有调用方追加的人工 accepted、旧/未知系统依据拒绝、人工依据与系统门禁独立、无请求的
实验单篇前置通过且自动队列拒绝、质量/根用途/执行来源及请求引用一致性。三个 applicability
字段与 A7 共享闭集；制品存在性矛盾在 Screening/PDF 两路保持各自原因。
这些断言不验证动作服务事务、真实正文、排名、预算余额或资源领取。

既有行为的新增回归用隔离副本受控回归检验敏感性；新增 root doctor help 经红→绿。
开发实测与 scope 重绑前后报告保留在 `/tmp/paperradar-issue-120/` 的交接材料，
不复用 A1–A10 历史结果。三份当前公共边界：
[doctor](../contracts/doctor.md)、[运行日志](../contracts/runtime-logging.md)、
[资格／可见性](../contracts/eligibility-visibility.md)。

scope 按实际引用 DAG 仅绑定本轮修改及传递下游；旧 pi-supply 的缺项查询抽到
`config/readiness.py`，登记该文件仅保持既有供给诊断源码闭包，不纳入新 doctor 能力、
新纯规则或新日志模块/测试，不扩大历史测试集合、分母或能力 required 集合。
仅在 A4/A10 的既有 pi-supply 消费处登记这一旧逻辑支撑文件；详细理由与基线对照保留在
工作树外 scope 报告。历史冻结 JSON 保持不变。

发布 A 窄收口状态前，须在全部文档/重绑汇合的同一 integration 树上完成双轴审阅和统一修复，
再由唯一执行者运行完整门禁。退出 0 不能推导本表新增能力通过；同次门禁也不证明完整
阶段 A、B 生产资格或 live。运行标识、实际终态和 SHA 不写回受身份约束文档。

## 逐项未验证边界

- **Pi**：生产离线启动器、资源/权限、真实成功来源未验，本票未调用 Pi 或模型。
- **Live**：固定 1.4.0 安装与 RPC 兼容未验，fake/合成许可不能替代。
- **Cwd**：`/srv/pi-cwd` 仅已确认，现场资源/权限隔离、DERIVED 与实际参数未验（EXP-2）。
- **四刊审计**：EXP-1/DEC-2、JGR selected ≥5 的真实主摘要判据仍归 Audit/Source；四刊稳定阈值与非截断判据 DEC-1 归 Abstract/D，附加区块语义 DEC-3 归 C；未访问网络。
- **Docling**：extra 安装、Python 兼容、模型/样本质量与四刊正文/摘录 fixture 未验（EXP-3/4）；EXP-6/7 仍归 Body/B。
- **正式校准**：保留器、32 篇真实样本、盲评/review/reveal/evaluation 及门禁未验（EXP-5），纯许可规则不构成校准资格。
- **NAS**：恢复与无人值守最终验收未验（EXP-5/I），不能复用历史 A3/Feed 通过代替。
