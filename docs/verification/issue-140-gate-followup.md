# Pi 当前兼容守卫与未绑定覆盖

依据 [#140](https://github.com/MeteoBoy4/PaperRadar/issues/140)、
[#144](https://github.com/MeteoBoy4/PaperRadar/issues/144) 后续完整验收范围。
本地集成基线为 `main=e0f8e39d1aff8b57eadfe60de44b8570423c1d40`。

## 当前边界

历史状态查询读取已发布终态及固定读者格式，不依赖当前生产组登记。
即使当前登记无法导入，完整历史材料仍按自己的受支持格式查询；
未知历史格式和缺失材料继续分别拒绝，查询不写入历史证据。
未绑定pytest安全诊断仅在实际tests失败分支加载，不进入历史文件哈希工具的冷导入链。
具体输出和读取规则见[辅助诊断Contract](../contracts/offline-pytest-diagnostics.md)。

## 覆盖范围

本轮没有新增或修改测试，新增D1节点为0。
[前轮独立D1](issue-140-external-review-followup.md) 的47+13=60、
[原Pi台账](issue-140-pi-delivery.md) 的195及所有旧结论保持原范围。
当前真实全量collection为352模块/6385节点；权威receipt_modules为285模块/5281节点。
其差集由显式67模块/1104节点组成，完整执行结果单列，不能仅凭固定分母全过判断整套通过。

| 未绑定模块 | 节点数 |
| --- | ---: |
| `tests/test_a10_document_obligations.py` | 17 |
| `tests/test_a10_scope_migration.py` | 18 |
| `tests/test_a8_a9_document_scope.py` | 23 |
| `tests/test_a_narrow_composition.py` | 8 |
| `tests/test_calibration_visibility.py` | 11 |
| `tests/test_calibration_visibility_architecture.py` | 14 |
| `tests/test_check_compatibility.py` | 12 |
| `tests/test_cli_import_compatibility.py` | 18 |
| `tests/test_config_error_assertion_architecture.py` | 23 |
| `tests/test_dev_environment.py` | 35 |
| `tests/test_dev_environment_entry.py` | 6 |
| `tests/test_dev_environment_probes.py` | 9 |
| `tests/test_doctor_pi_exec.py` | 31 |
| `tests/test_doctor_process.py` | 35 |
| `tests/test_doctor_readonly.py` | 7 |
| `tests/test_eligibility.py` | 50 |
| `tests/test_eligibility_architecture.py` | 15 |
| `tests/test_eligibility_review.py` | 60 |
| `tests/test_extensible_acceptance.py` | 22 |
| `tests/test_feed_conflicts.py` | 12 |
| `tests/test_feed_independent_review.py` | 7 |
| `tests/test_feed_ingestion.py` | 21 |
| `tests/test_feed_language.py` | 21 |
| `tests/test_feed_metadata.py` | 12 |
| `tests/test_feed_metadata_recovery.py` | 5 |
| `tests/test_feed_pipeline.py` | 13 |
| `tests/test_feed_review_boundaries.py` | 7 |
| `tests/test_live_document_links.py` | 4 |
| `tests/test_migration_expectations.py` | 1 |
| `tests/test_models_v2.py` | 20 |
| `tests/test_offline_unbound_diagnostics.py` | 13 |
| `tests/test_pi_execution_admission.py` | 15 |
| `tests/test_pi_execution_external_review.py` | 47 |
| `tests/test_pi_execution_feed.py` | 1 |
| `tests/test_pi_execution_history_imports.py` | 3 |
| `tests/test_pi_execution_integration.py` | 3 |
| `tests/test_pi_execution_isolation.py` | 3 |
| `tests/test_pi_execution_launch.py` | 18 |
| `tests/test_pi_execution_resources.py` | 15 |
| `tests/test_pi_execution_review.py` | 10 |
| `tests/test_pi_execution_service.py` | 32 |
| `tests/test_pi_rpc_source.py` | 23 |
| `tests/test_pi_rpc_source_backup.py` | 21 |
| `tests/test_runtime_logging_audit.py` | 6 |
| `tests/test_runtime_logging_entries.py` | 2 |
| `tests/test_runtime_logging_feed.py` | 12 |
| `tests/test_runtime_logging_files.py` | 8 |
| `tests/test_runtime_logging_readonly.py` | 3 |
| `tests/test_runtime_logging_tasks.py` | 20 |
| `tests/test_runtime_logging_vocabulary.py` | 59 |
| `tests/test_scope_baseline_audit.py` | 34 |
| `tests/test_scope_central_registration.py` | 17 |
| `tests/test_scope_document_guards.py` | 27 |
| `tests/test_scope_material_inventory.py` | 4 |
| `tests/test_scope_parallel_integration.py` | 7 |
| `tests/test_scope_review_fixes.py` | 16 |
| `tests/test_scope_review_r4.py` | 15 |
| `tests/test_scope_shared_dag.py` | 24 |
| `tests/test_scope_writer_discovery.py` | 5 |
| `tests/test_t07_call_isolation.py` | 6 |
| `tests/test_tmp_path_cleanup.py` | 8 |
| `tests/test_tmp_path_peak_usage.py` | 1 |
| `tests/test_verification_scope_audit.py` | 30 |
| `tests/test_verification_scope_cli.py` | 9 |
| `tests/test_verification_scope_collection.py` | 5 |
| `tests/test_verification_scope_registry.py` | 10 |
| `tests/test_verification_status.py` | 35 |
| 合计 | 1104 |

## 验证与登记

| 验证范围 | 实测结果 |
| --- | --- |
| 原broken_registry历史读取守卫 | 1 passed，3.12秒 |
| 扩展/诊断/状态/离线入口组合 | 81 passed，113.16秒 |
| 显式全部67个未绑定模块/1104节点 | 1104 passed，520.81秒，退出0；无skip/deselect |
| `check-compatibility all` | 176 passed，pytest279.92秒，入口280.52秒，退出0 |
| 全仓Ruff check / format check / mypy | 全通过；格式748文件、mypy747文件 |
| 显式main基线候选scope | 无hash/baseline漂移；最终身份确认与固定collection留树外，289条原计数保持 |

本轮未绑定集合与执行完全覆盖上表；不以局部相关组合代替完整差集。
仅 `scripts/offline_evidence.py` 的实际支持源码哈希更新，组成员、用途、
固定测试/fixture、required与41refs保持。
源码副本确实包含辅助模块，历史读者与当前登记的导入独立性由原broken_registry断言验证。

完整门禁待最终新提交冻结后独立运行；同次入口退出0且状态
`passed/verified/same`才满足最终判据。历史失败证据和既有覆盖台账正文保持原字节。
所有run_id与最终监控记录保存在树外。

## 未验限制

没有live、真实Pi/Node/auth/模型、cwd现场、TLS/DNS或主机级出站验证。
Cwd/Live/B承接不变，产品仍缺当前准入证据并领取前阻断；stage_a_verified=false。
