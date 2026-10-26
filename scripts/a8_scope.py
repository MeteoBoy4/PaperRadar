"""#91 固定 A8 验收范围;预期由人工审阅源码和参数化登记,运行时不能刷新。"""

SCOPE = "a8_rpc_offline_protocol_tasks"
ISSUE = 85
PARENT_ISSUE = 85
FORMAT_VERSION = 1
SUFFIX = ".a8.json"
MIGRATION_REVISION = "a1001_fixture_audit"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "render": 1,
    "protocol_profiles": {"1.4.0": "pi-rpc-1.4.0-v1"},
    "screening_tasks": 1,
    "task_reason_catalog": 1,
    "task_query_result": 1,
    "stage_inputs": {"boundary": 1, "value": 1},
    "backup": 1,
}
CAPABILITIES = (
    "frozen_call_description",
    "protocol_version_admission",
    "deterministic_rendering",
    "bounded_framing",
    "correlated_initialization",
    "complete_unique_candidate",
    "model_usage_audit",
    "bounded_cancellation_cleanup",
    "a7_authoritative_acceptance",
    "attempt_budget_correction",
    "isolated_recovery",
    "privacy",
    "same_run_acceptance",
)
NOT_ASSESSED = (
    "rpc_compatibility",
    "pi_execution",
    "real_model_usage_cost",
    "original_title_language_production_source",
    "metadata_ready",
    "complete_eligibility",
    "daily_quota",
    "two_stage_orchestration",
    "suggestions_decisions",
    "calibration_visibility",
    "reuse_tasks",
    "extraction_tasks",
    "read_tasks",
    "merge_budget",
    "screening_cli",
    "paper_trace_cli",
    "nas_restore",
    "stage_a",
    "live",
    "automatic_fulltext_reading",
    "effective_system_instructions_cwd",
    "production_parameter_mapping",
    "provider_retry",
    "cache_warming",
    "automatic_network_activity",
    "actual_session_resource_permission_isolation",
    "model_credentials_preflight",
    "derived_rules_live_verification",
)
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_a8_call_description.py": 6,
    "tests/test_a8_call_rejections.py": 8,
    "tests/test_a8_request_vectors.py": 14,
    "tests/test_a8_llm_architecture.py": 1,
    "tests/test_a8_rpc_protocol.py": 69,
    "tests/test_a8_rpc_boundary.py": 7,
    "tests/test_a8_rpc_preflight.py": 2,
    "tests/test_a8_rpc_candidates.py": 219,
    "tests/test_a8_rpc_value.py": 22,
    "tests/test_a8_rpc_lifecycle.py": 67,
    "tests/test_a8_rpc_pipes.py": 19,
    "tests/test_a8_rpc_recovery.py": 16,
    "tests/test_a8_rpc_history.py": 6,
    "tests/test_a8_rpc_backup.py": 1,
    "tests/test_a8_acceptance.py": 2,
    "tests/test_a8_integrity.py": 136,
    "tests/test_a8_entry.py": 9,
    "tests/test_a8_status.py": 10,
    "tests/test_a8_test_receipt.py": 6,
    "tests/test_a8_formats.py": 9,
}
REQUIRED_TEST_MODULES = (
    (
        "tests/test_a8_call_description.py",
        "8ec81f0a37252cac45dc3412c950c44498fff6437e6cfa984bfd67dd18702690",
    ),
    (
        "tests/test_a8_call_rejections.py",
        "cafdbee50be30f09bdf3c6a885fac35a9d0c0c0c30119b456796d0ee4090b81e",
    ),
    (
        "tests/test_a8_request_vectors.py",
        "604f2842b0898830c8770eaef3183c41279a27da8733590e6037055a56e019c5",
    ),
    (
        "tests/test_a8_llm_architecture.py",
        "7b06f1d89e56b127ce5fe2a9fba7b82542d0faafa89d5fcd309c53d3c309cbd1",
    ),
    (
        "tests/test_a8_rpc_protocol.py",
        "7782e415c5e760fa7a3897bc4d791876eae4f88120382e2007a97361d7e35b5d",
    ),
    (
        "tests/test_a8_rpc_boundary.py",
        "20a233df1d19aa96686c21eecb6fe98240c6fe60ace0feeec3f09e874bb98061",
    ),
    (
        "tests/test_a8_rpc_preflight.py",
        "db1298c48c2708e43640ed27655ca9084c6d182a87bd14e025e9cc9168b0c990",
    ),
    (
        "tests/test_a8_rpc_candidates.py",
        "c9a8ba035c66545b490651807fa9f387eb6db24cbaefafd9d591faf73056beb6",
    ),
    (
        "tests/test_a8_rpc_value.py",
        "6de19451c03cf82bf6e6292e16b42981e6f35d255245bf9117ec515d964794b9",
    ),
    (
        "tests/test_a8_rpc_lifecycle.py",
        "0c98a380fd31188728dc990faaa6f4040e0149876ef973003b88575900137aec",
    ),
    (
        "tests/test_a8_rpc_pipes.py",
        "872cda2c547fb0213ede2461a26f71e92cd5ff008a4fc6a332949d634679724b",
    ),
    (
        "tests/test_a8_rpc_recovery.py",
        "199eeba2e8dde34adace664dfde5772998acb68f92327686d069fa6906b8a020",
    ),
    (
        "tests/test_a8_rpc_history.py",
        "ef7d96c036ce161ac2aeddf2668ca838574a84aed0de28e6b29abd35dbc68377",
    ),
    (
        "tests/test_a8_rpc_backup.py",
        "af5df1479e02ef7707aeb8a049e8cdcd2a5ed4051548008d4aef4d11155965b3",
    ),
    (
        "tests/test_a8_acceptance.py",
        "14ef2c0f21320393a95df27b722e3ae9646dce8380fddd489ff5d3e8ab567d0f",
    ),
    (
        "tests/test_a8_integrity.py",
        "bc4241a064a463e9819baa14e9d81a7e8931ba294c675c21c6b62e9c57bf71e9",
    ),
    (
        "tests/test_a8_entry.py",
        "148090d5270b8a1989ee4681ff52f6a5e1d5a38fe0faf8414c0a769c4fa5d604",
    ),
    (
        "tests/test_a8_status.py",
        "b64aff17415549c62e6f3cb0e92035f34e7e69925a14d2eeee1db4afc843d63a",
    ),
    (
        "tests/test_a8_test_receipt.py",
        "018a6b27fe669ada739abd046895936191036bf801d30cb03a16cef5c85a0adc",
    ),
    (
        "tests/test_a8_formats.py",
        "5f9363cb6b160b491b531e2e84d42105f01ddd066037d02c7a4dc695b0ccbc17",
    ),
)
REQUIRED_SOURCE_MODULES = (
    (
        "src/paper_radar/llm/__init__.py",
        "593aded4206190482fceb1646ad1a37804499340f488c3cd87d5f154590e9ced",
    ),
    (
        "src/paper_radar/llm/calls.py",
        "00df2a1de87c8954546ed0a73613e5cabf7b306b925ebe26b9cae163f104a2db",
    ),
    (
        "src/paper_radar/llm/models.py",
        "e797ee78cfae739a5d705d5d25ee406e2d43e57511f82364bfa6cacd10a44a64",
    ),
    (
        "src/paper_radar/llm/rpc.py",
        "295fca3e595de9003baf76a92e82bb382de83207c23aa0e3ce327d21b0e61857",
    ),
    (
        "src/paper_radar/llm/rpc_frames.py",
        "98628acd0b56b7ac9c1b9896f82abde034aa51120e4d7c08e2c91ffe5cdbae22",
    ),
    (
        "src/paper_radar/llm/rpc_messages.py",
        "c33ce58005583b16142ae0fa6b033ff7b776eb1f5505e6376dc1ddaa1049128c",
    ),
    (
        "src/paper_radar/llm/rpc_pipes.py",
        "d294ca3ab3e1170af072bd7fe2f77387d72adf97b2e49231021213b76b3c3c3a",
    ),
    (
        "src/paper_radar/llm/rpc_types.py",
        "2b3f15472b6c548854d308a9b20ef566fd52e7cc8e635bf5445f6d356cd4a179",
    ),
    (
        "tests/a8_acceptance_support.py",
        "2bc2b90eaa623493b9b4b2ac449d72e8b6e82e0790893146103abada5e2e64fe",
    ),
    (
        "tests/a8_call_support.py",
        "32f467cbe9dfe784deb0274d572025f76fa0a4ddde2f857b2ac96251c06249f1",
    ),
    (
        "tests/a8_call_worker.py",
        "cd0ce99a561fb6b8f1855587448799027f784fdcc9b4d97e9f9c37044d947c0c",
    ),
    (
        "tests/a8_pipe_support.py",
        "e457f0e178683ec2d83aad637828a2a473a8f2a8b3afff71cb0922c18e46d952",
    ),
    (
        "tests/a8_pipe_worker.py",
        "ee1001709a8569f6b4c40791696d59a65b3ef8f8fa88a401771da973289ea175",
    ),
    (
        "tests/a8_recovery_support.py",
        "ed5128a6fe59df9c35207cea180639e2a30d3c34d951be64d25f6a4f4ad59687",
    ),
    (
        "tests/a8_recovery_worker.py",
        "e85e9e2eee5d6e179487446f75f19e8a227f5361586fa383f3eac5f5a100e99c",
    ),
    (
        "tests/a8_rpc_support.py",
        "70750fc6b8ed6bfc6f87c5f3e8af9f30dbcd076b7164acdd1906b80e505770ae",
    ),
    (
        "tests/a8_rpc_task_support.py",
        "1fdc95fcb1be680e5d478c2cedf95c3e2a3ca12319c51940981727362bdd56ad",
    ),
    (
        "scripts/a8_acceptance.py",
        "38d9a4ef5d3078498edefc9d71bf8de1999a0a11db327652fa960147110d2153",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204",
    ),
    (
        "scripts/a2_test_receipt.py",
        "38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5",
    ),
    (
        "scripts/a1_scope.py",
        "245cf6e6bd9d1dafe3f747561d2518d32583e6154dc4876ff1cc9a5c78152251",
    ),
    (
        "scripts/a2_full_scope.py",
        "13652d399793600e37a62314fbb526e4e80b64c5d06fc08eadafac1216f0211a",
    ),
    (
        "scripts/a3_scope.py",
        "7f3988e9cfd9fe791d28dc4e179789b957cdbcd7de8c3d9f3a72eb9eddecedb2",
    ),
    (
        "scripts/a5_scope.py",
        "1577b770d8333b0448ef98677a5be1536bca5408c5aeaf7a3624dec30c3cbf0c",
    ),
    (
        "scripts/a6_scope.py",
        "7129a93e72012c471043bbf0a6fe40f355135d7944a24a487294113ee13ec722",
    ),
    (
        "scripts/a7_scope.py",
        "2c5e6f6aed116c6f67a97e7822b1a19ed4c8f97a92453c7007586cdb21ea8ea1",
    ),
    (
        "scripts/check-offline",
        "41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8",
    ),
    (
        "scripts/offline_evidence.py",
        "3c53fd4e272ee346da23b72cd977180b78aeaa55a027064a97f5540ea24d9a28",
    ),
    (
        "scripts/verification_checks.py",
        "f93113dcaa037ed7b5992133320a58d36dcf438c1d82969c94611c54649788bc",
    ),
    (
        "scripts/verification_identity.py",
        "27ebdd057098256f0419c34cb9dbc410e0c6f0c7a8c3c931f62cc6942ca8d7b5",
    ),
    (
        "scripts/verification_publication.py",
        "337c9efb7ee906486e9de9bb5ec4d60bd9bde7fe358f60098036862e1ac77072",
    ),
    (
        "scripts/verification_run.py",
        "a4d08449eb65ac7e2c39d2fe972cccf28ec8af13dcf5d34795ac1c088212ae0a",
    ),
    (
        "scripts/verification_status.py",
        "081a13f82706ebc16aee21138c40bcf6620ad8daeb8efa6338a1512f07edd1c5",
    ),
    (
        "scripts/verification_scope_registry.py",
        "0245aea1f6fd7fd9fc50bcd34abc6591cc9963876b3e4f72d068b76a02a9e871",
    ),
    (
        "scripts/verification_scope_audit.py",
        "8a83ecbc39fb3a7e692d2c17a48646b20e90945d57c2f6712f88b9232d5d0ce5",
    ),
    (
        "tests/deny_external_io/sitecustomize.py",
        "f0148752ef89a004fcf76048cbc1f070448152683921b6d9d7c452d102a2d48d",
    ),
    (
        "tests/deny_network/sitecustomize.py",
        "dfce12fb68aaefd9b19ec26f1ff6bfb10b3f726fdafe6f466ec031cc2acc3288",
    ),
)
REQUIRED_FIXTURE_FILES = (
    (
        "tests/fixtures/a8_capabilities.json",
        "be2f6c0422550c4f7594e201da0d8408442263b569f7c5ede50ef84055ec31ea",
    ),
    (
        "tests/fixtures/pi_rpc/1.4.0/README",
        "a9e64a7c25493e006121742de6cac827e2b259e4f280dcc4059fa9d701044541",
    ),
    (
        "tests/fixtures/pi_rpc/1.4.0/request-vectors.json",
        "d961aab403cf3e17683bbfe25a62a9eeddd223833d2567984710e8ca9a0f50ad",
    ),
    (
        "docs/contracts/pi-rpc.md",
        "28a0aadcf161ae887e5e6808e35a5fed35ff69b0f9b9cef7fddb1457c10d92d7",
    ),
    (
        "docs/contracts/verification-status.md",
        "2678cca8a20454cdf01b0758bea5a904140a0ab065e573f14e9e527863d3705d",
    ),
    (
        "docs/verification/offline-evidence.md",
        "7e3aec1a3b9742792df7e29e0ba151f29775c5f70ca456f1db48ac30e9946813",
    ),
    (
        "docs/verification/a8-requirements.md",
        "102cb0f2bd14ac6ad57467b9f8cfb766d7f19620058b29bbd23ebd0a5615307f",
    ),
    ("README.md", "9c21c0726ee8b270bebcfbd4c0636656354416089059299f4ea214e15d397173"),
)
