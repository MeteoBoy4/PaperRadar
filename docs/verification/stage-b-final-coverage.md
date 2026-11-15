# B 最终独立 D1 收集索引

本索引归并原工程收口及双轴审阅修复后的新增独立模块；不追溯改写各票冻结台账，
不扩大 A1–A10 的固定分母、required 集合或回执，`stage_a_verified=false`。
代码树收集来源为 `6f23e08070d2fb744531121cf80492797222993b`；
逐模块文件 SHA 与数量保存在[机器索引](stage-b-final-coverage.json)。

当前实际结果为 **65 模块、637 个唯一用例收集成功**，没有重复节点；这是收集，
不是宣称637项在本次或最终树全部执行通过。各工程组合实际结果见
[原工程收口](stage-b-engineering-closure.md)与[审阅修复](stage-b-review-fixes.md)，
不同源码阶段/进程不拼成一次最终门禁。完整门禁实际结果由最终冻结提交的树外回执判定。
真实版式、真实链与恢复签收分别见其独立脱敏台账，不由本工程索引背书。

| 新增独立模块 | 收集节点 |
| --- | ---: |
| `tests/test_body_selection_cli.py` | 3 |
| `tests/test_body_selection_facts.py` | 11 |
| `tests/test_body_selection_integrity.py` | 2 |
| `tests/test_body_selection_migrations.py` | 4 |
| `tests/test_body_selection_read.py` | 1 |
| `tests/test_body_selection_recovery.py` | 1 |
| `tests/test_experiment_accept_cli.py` | 27 |
| `tests/test_experiment_accept_migrations.py` | 6 |
| `tests/test_experiment_candidates_cli.py` | 18 |
| `tests/test_experiment_exposure_cli.py` | 2 |
| `tests/test_experiment_exposure_entry.py` | 5 |
| `tests/test_experiment_exposure_faults.py` | 14 |
| `tests/test_experiment_exposure_history.py` | 4 |
| `tests/test_experiment_exposure_identity.py` | 9 |
| `tests/test_experiment_exposure_migrations.py` | 4 |
| `tests/test_experiment_exposure_recovery.py` | 1 |
| `tests/test_experiment_extract_cli.py` | 35 |
| `tests/test_experiment_extract_migrations.py` | 5 |
| `tests/test_experiment_feed_cli.py` | 21 |
| `tests/test_experiment_layout_cli.py` | 35 |
| `tests/test_experiment_layout_migrations.py` | 6 |
| `tests/test_experiment_pdf_cli.py` | 30 |
| `tests/test_experiment_pdf_migrations.py` | 6 |
| `tests/test_experiment_read_cli.py` | 24 |
| `tests/test_experiment_read_logging.py` | 3 |
| `tests/test_experiment_read_owner_basis.py` | 1 |
| `tests/test_experiment_read_retry_cli.py` | 9 |
| `tests/test_experiment_reports_capacity.py` | 1 |
| `tests/test_experiment_reports_cli.py` | 14 |
| `tests/test_experiment_reports_decision_order.py` | 4 |
| `tests/test_experiment_reports_disclosure.py` | 4 |
| `tests/test_experiment_reports_faults.py` | 4 |
| `tests/test_experiment_reports_late_results.py` | 2 |
| `tests/test_experiment_reports_logging.py` | 2 |
| `tests/test_experiment_reports_migrations.py` | 5 |
| `tests/test_experiment_reports_publication.py` | 2 |
| `tests/test_experiment_reports_recovery.py` | 1 |
| `tests/test_experiment_reports_sections.py` | 1 |
| `tests/test_experiment_screen_cli.py` | 22 |
| `tests/test_experiment_selection_cli.py` | 29 |
| `tests/test_experiment_selection_migrations.py` | 4 |
| `tests/test_experiment_supply_layout.py` | 10 |
| `tests/test_extraction_normalization_cli.py` | 5 |
| `tests/test_extraction_normalization_repair.py` | 34 |
| `tests/test_extraction_normalization_selection.py` | 1 |
| `tests/test_model_mapping_rpc.py` | 10 |
| `tests/test_replay_business.py` | 1 |
| `tests/test_replay_container.py` | 1 |
| `tests/test_replay_deadline.py` | 16 |
| `tests/test_replay_descendant_deadline.py` | 4 |
| `tests/test_replay_entry.py` | 2 |
| `tests/test_replay_faults.py` | 24 |
| `tests/test_replay_os.py` | 1 |
| `tests/test_replay_process.py` | 2 |
| `tests/test_report_replay_projection.py` | 3 |
| `tests/test_screening_recovery_trace_cli.py` | 23 |
| `tests/test_stage_b_admission_source_closure.py` | 12 |
| `tests/test_stage_b_egress_preflight.py` | 41 |
| `tests/test_stage_b_model_mapping.py` | 11 |
| `tests/test_stage_b_production_prompts.py` | 10 |
| `tests/test_stage_b_review_query_errors.py` | 29 |
| `tests/test_stage_b_review_read_failures.py` | 7 |
| `tests/test_stage_b_review_report_quality.py` | 3 |
| `tests/test_stage_b_review_trace_facts.py` | 3 |
| `tests/test_stage_b_trace_restore_cli.py` | 2 |
| 合计 | **637** |
