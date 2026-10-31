"""#99 固定 A9 Read 离线验收;登记必须人工审阅,不在运行时刷新。"""

from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a9_read_offline_validation_config_recovery"
ISSUE = 92
PARENT_ISSUE = 92
FORMAT_VERSION = 1
SUFFIX = ".a9.json"
MIGRATION_REVISION = "feed06_language_provenance"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "read_contract": "v1",
    "evidence_rules": "read-evidence-v1",
    "numeric_rules": "read-numeric-v1",
    "snapshot": 1,
    "backup": 1,
}
CAPABILITIES = (
    "authoritative_output",
    "strict_json_privacy",
    "immutable_context",
    "provenance_replay",
    "numeric_diagnostics",
    "restricted_content",
    "reduce_scope",
    "frozen_contract",
    "explicit_configuration",
    "historical_identity",
    "isolated_recovery",
    "same_run_acceptance",
)
NOT_ASSESSED = (
    "orig_hash_coverage",
    "real_pdf_provenance",
    "four_journal_fixtures",
    "body_quality",
    "semantic_entailment",
    "model_quality",
    "map_source_chain",
    "read_stage_input",
    "read_tasks_budgets",
    "production_pi_model",
    "calibration",
    "nas_restore",
    "stage_a",
    "live",
    "automatic_fulltext_reading",
)

REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_read_contract.py": 60,
    "tests/test_read_context.py": 60,
    "tests/test_read_validation.py": 76,
    "tests/test_read_numbers.py": 94,
    "tests/test_read_privacy.py": 3,
    "tests/test_read_restricted.py": 56,
    "tests/test_read_reduce.py": 42,
    "tests/test_read_config.py": 29,
    "tests/test_read_config_cli.py": 5,
    "tests/test_read_recovery.py": 11,
    "tests/test_a9_acceptance.py": 7,
    "tests/test_a9_integrity.py": 92,
    "tests/test_a9_entry.py": 10,
    "tests/test_a9_status.py": 11,
    "tests/test_a9_scope.py": 4,
}

REQUIRED_TEST_MODULES = (
    (
        "tests/test_read_contract.py",
        "da4265001ac5280131f14d45eaf9a6215c7592c7c958d67e8257c311b33dfb4a",
    ),
    (
        "tests/test_read_context.py",
        "1d9fb90c3b2fb2b14f9c3c82bc9f9a8e537e322d73a56c8761e2795d030b4805",
    ),
    (
        "tests/test_read_validation.py",
        "b35340b57aa645a0196b11e07e54e3d11ac7f904a4c381a41dea9ceadf52d0f8",
    ),
    (
        "tests/test_read_numbers.py",
        "b9517983721b5cfb727791eafbf29e37b411332538cac75fb5f91f6293dfecd7",
    ),
    (
        "tests/test_read_privacy.py",
        "506b760c8bffdb712844473f6c5aecd536a28f7df162c67f22dcc8f014855ea7",
    ),
    (
        "tests/test_read_restricted.py",
        "ccae8274a573e7291c643f661a65537aa7959b934ca0684a3ca059a499a8e5f5",
    ),
    (
        "tests/test_read_reduce.py",
        "b460104e40e3e2234e0cf3041e818990cf74054be70dbe76da8edc92acb86108",
    ),
    (
        "tests/test_read_config.py",
        "9689d1bc576cd04c78958f7610b7f389c19b98a2fc927fffa33fd367942463a7",
    ),
    (
        "tests/test_read_config_cli.py",
        "70235899106db2b4830b920b499c4c59186c0672f3002b17005bb9caf48ca4de",
    ),
    (
        "tests/test_read_recovery.py",
        "586b2624a6a85edab2d79ba01551f4a1cbaf52a837950d6625c30ded862d50e1",
    ),
    (
        "tests/test_a9_acceptance.py",
        "2cbd937ba93b0cf1de2ef1fe3c5ef2ffd023c22bf5d983d22668368bef3a96cf",
    ),
    (
        "tests/test_a9_integrity.py",
        "ebc1181bcc35320fc097cb2ccae6422372c3fff2e58c795472b12bff10cce1fe",
    ),
    (
        "tests/test_a9_entry.py",
        "87d9cde4deef8d3c4fdd21c002c1502569daac2274683dd6f9c35ec2574e1f81",
    ),
    (
        "tests/test_a9_status.py",
        "bec690ac7434b10693fbb2f3da59fad0088ca5551d1d12144711d852193b4eed",
    ),
    (
        "tests/test_a9_scope.py",
        "1b889334ba376d5b622071c8aee6f15ce9b250448fc2a8ee830201f42321b5b3",
    ),
)

REQUIRED_SOURCE_MODULES = (
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
    ),
    (
        "src/paper_radar/reading/__init__.py",
        SHARED_MATERIALS["src/paper_radar/reading/__init__.py"],
    ),
    (
        "src/paper_radar/reading/schema.py",
        SHARED_MATERIALS["src/paper_radar/reading/schema.py"],
    ),
    (
        "src/paper_radar/reading/value_types.py",
        SHARED_MATERIALS["src/paper_radar/reading/value_types.py"],
    ),
    (
        "src/paper_radar/reading/context.py",
        SHARED_MATERIALS["src/paper_radar/reading/context.py"],
    ),
    (
        "src/paper_radar/reading/errors.py",
        SHARED_MATERIALS["src/paper_radar/reading/errors.py"],
    ),
    (
        "src/paper_radar/reading/diagnostics.py",
        SHARED_MATERIALS["src/paper_radar/reading/diagnostics.py"],
    ),
    (
        "src/paper_radar/reading/parsing.py",
        SHARED_MATERIALS["src/paper_radar/reading/parsing.py"],
    ),
    (
        "src/paper_radar/reading/numbers.py",
        SHARED_MATERIALS["src/paper_radar/reading/numbers.py"],
    ),
    (
        "src/paper_radar/reading/result.py",
        SHARED_MATERIALS["src/paper_radar/reading/result.py"],
    ),
    (
        "src/paper_radar/reading/validation.py",
        SHARED_MATERIALS["src/paper_radar/reading/validation.py"],
    ),
    (
        "src/paper_radar/screening/text.py",
        SHARED_MATERIALS["src/paper_radar/screening/text.py"],
    ),
    (
        "src/paper_radar/contracts/__init__.py",
        SHARED_MATERIALS["src/paper_radar/contracts/__init__.py"],
    ),
    (
        "src/paper_radar/contracts/schema.py",
        SHARED_MATERIALS["src/paper_radar/contracts/schema.py"],
    ),
    (
        "src/paper_radar/contracts/check.py",
        SHARED_MATERIALS["src/paper_radar/contracts/check.py"],
    ),
    (
        "src/paper_radar/contracts/export.py",
        SHARED_MATERIALS["src/paper_radar/contracts/export.py"],
    ),
    (
        "src/paper_radar/contracts/snapshot.py",
        SHARED_MATERIALS["src/paper_radar/contracts/snapshot.py"],
    ),
    (
        "src/paper_radar/contracts/errors.py",
        SHARED_MATERIALS["src/paper_radar/contracts/errors.py"],
    ),
    (
        "src/paper_radar/config/__init__.py",
        SHARED_MATERIALS["src/paper_radar/config/__init__.py"],
    ),
    (
        "src/paper_radar/config/schema.py",
        SHARED_MATERIALS["src/paper_radar/config/schema.py"],
    ),
    (
        "src/paper_radar/config/service.py",
        SHARED_MATERIALS["src/paper_radar/config/service.py"],
    ),
    (
        "src/paper_radar/config/compile.py",
        SHARED_MATERIALS["src/paper_radar/config/compile.py"],
    ),
    (
        "src/paper_radar/config/diff.py",
        SHARED_MATERIALS["src/paper_radar/config/diff.py"],
    ),
    (
        "src/paper_radar/config/projections.py",
        SHARED_MATERIALS["src/paper_radar/config/projections.py"],
    ),
    (
        "src/paper_radar/config/material_names.py",
        SHARED_MATERIALS["src/paper_radar/config/material_names.py"],
    ),
    (
        "src/paper_radar/config/material_assembly.py",
        SHARED_MATERIALS["src/paper_radar/config/material_assembly.py"],
    ),
    (
        "src/paper_radar/config/identity.py",
        SHARED_MATERIALS["src/paper_radar/config/identity.py"],
    ),
    (
        "src/paper_radar/config/read.py",
        SHARED_MATERIALS["src/paper_radar/config/read.py"],
    ),
    (
        "src/paper_radar/config/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_queries.py"],
    ),
    (
        "src/paper_radar/config/snapshot_summary.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_summary.py"],
    ),
    (
        "src/paper_radar/config/adapter_loading.py",
        SHARED_MATERIALS["src/paper_radar/config/adapter_loading.py"],
    ),
    (
        "src/paper_radar/config/adapters.py",
        SHARED_MATERIALS["src/paper_radar/config/adapters.py"],
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        SHARED_MATERIALS["src/paper_radar/config/yaml_loader.py"],
    ),
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    (
        "src/paper_radar/config/cli.py",
        SHARED_MATERIALS["src/paper_radar/config/cli.py"],
    ),
    (
        "src/paper_radar/config/snapshot_cli.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_cli.py"],
    ),
    (
        "src/paper_radar/storage/database.py",
        SHARED_MATERIALS["src/paper_radar/storage/database.py"],
    ),
    (
        "src/paper_radar/storage/repository.py",
        SHARED_MATERIALS["src/paper_radar/storage/repository.py"],
    ),
    (
        "src/paper_radar/storage/records.py",
        SHARED_MATERIALS["src/paper_radar/storage/records.py"],
    ),
    (
        "src/paper_radar/storage/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/storage/snapshot_queries.py"],
    ),
    (
        "src/paper_radar/storage/errors.py",
        SHARED_MATERIALS["src/paper_radar/storage/errors.py"],
    ),
    (
        "src/paper_radar/storage/artifacts.py",
        SHARED_MATERIALS["src/paper_radar/storage/artifacts.py"],
    ),
    (
        "src/paper_radar/storage/artifact_contract.py",
        SHARED_MATERIALS["src/paper_radar/storage/artifact_contract.py"],
    ),
    (
        "src/paper_radar/storage/artifact_repository.py",
        SHARED_MATERIALS["src/paper_radar/storage/artifact_repository.py"],
    ),
    (
        "src/paper_radar/storage/blob_store.py",
        SHARED_MATERIALS["src/paper_radar/storage/blob_store.py"],
    ),
    (
        "src/paper_radar/backup/__init__.py",
        SHARED_MATERIALS["src/paper_radar/backup/__init__.py"],
    ),
    (
        "src/paper_radar/backup/service.py",
        SHARED_MATERIALS["src/paper_radar/backup/service.py"],
    ),
    (
        "src/paper_radar/backup/restore.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore.py"],
    ),
    (
        "src/paper_radar/backup/manifest.py",
        SHARED_MATERIALS["src/paper_radar/backup/manifest.py"],
    ),
    (
        "src/paper_radar/backup/files.py",
        SHARED_MATERIALS["src/paper_radar/backup/files.py"],
    ),
    (
        "src/paper_radar/backup/restore_contract.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore_contract.py"],
    ),
    ("scripts/a9_acceptance.py", SHARED_MATERIALS["scripts/a9_acceptance.py"]),
    (
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/offline_evidence.py", SHARED_MATERIALS["scripts/offline_evidence.py"]),
    (
        "scripts/verification_checks.py",
        SHARED_MATERIALS["scripts/verification_checks.py"],
    ),
    (
        "scripts/verification_identity.py",
        SHARED_MATERIALS["scripts/verification_identity.py"],
    ),
    (
        "scripts/verification_publication.py",
        SHARED_MATERIALS["scripts/verification_publication.py"],
    ),
    ("scripts/verification_run.py", SHARED_MATERIALS["scripts/verification_run.py"]),
    (
        "scripts/verification_status.py",
        SHARED_MATERIALS["scripts/verification_status.py"],
    ),
    (
        "scripts/verification_scope_registry.py",
        SHARED_MATERIALS["scripts/verification_scope_registry.py"],
    ),
    (
        "scripts/verification_scope_audit.py",
        SHARED_MATERIALS["scripts/verification_scope_audit.py"],
    ),
    (
        "scripts/audit_verification_scope.py",
        "6e76fcfa02a50155f06dc30ec3ed7f302614fa927c45070f494463722fe1b37f",
    ),
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
    ("scripts/verification-status", SHARED_MATERIALS["scripts/verification-status"]),
    (
        "tests/read_support.py",
        "74406d6f1049f420a400f008109cbabe0c46bc6ca336dc95a50c8d42514582aa",
    ),
    (
        "tests/read_config_support.py",
        "d0c1a2b1a373b9addc3246ac820bd22629515a10f9886b444356f14dd9f76d02",
    ),
    (
        "tests/read_recovery_support.py",
        "b5569cd43e7decdfe914365a0d2dcefb5069c4b26fc50629925904707a1912b9",
    ),
    (
        "tests/read_recovery_worker.py",
        "2404ff8fe28da8786c68a9853ce135bd20f13582fa8392ab5aafe115c3ae6f86",
    ),
    ("tests/config_read_support.py", SHARED_MATERIALS["tests/config_read_support.py"]),
    ("tests/config_test_support.py", SHARED_MATERIALS["tests/config_test_support.py"]),
    (
        "tests/contract_snapshot_support.py",
        "b3c5738234364731747d370ab152a722350b8d5e78a1e842f80937834cb2da31",
    ),
    (
        "tests/test_screening_architecture.py",
        SHARED_MATERIALS["tests/test_screening_architecture.py"],
    ),
    (
        "tests/deny_network/sitecustomize.py",
        SHARED_MATERIALS["tests/deny_network/sitecustomize.py"],
    ),
    (
        "tests/conftest.py",
        "f455cad8f864d3e764163334a76fcc5ee03bd13a61e5e5b8c6eefe838d505c0e",
    ),
    ("tests/backup_support.py", SHARED_MATERIALS["tests/backup_support.py"]),
    (
        "tests/a9_acceptance_support.py",
        SHARED_MATERIALS["tests/a9_acceptance_support.py"],
    ),
    (
        "tests/a8_acceptance_support.py",
        SHARED_MATERIALS["tests/a8_acceptance_support.py"],
    ),
    (
        "tests/a7_acceptance_support.py",
        SHARED_MATERIALS["tests/a7_acceptance_support.py"],
    ),
    (
        "tests/a6_acceptance_support.py",
        SHARED_MATERIALS["tests/a6_acceptance_support.py"],
    ),
    (
        "tests/a5_acceptance_support.py",
        SHARED_MATERIALS["tests/a5_acceptance_support.py"],
    ),
    (
        "tests/a4_acceptance_support.py",
        SHARED_MATERIALS["tests/a4_acceptance_support.py"],
    ),
    (
        "tests/a3_acceptance_support.py",
        SHARED_MATERIALS["tests/a3_acceptance_support.py"],
    ),
    ("tests/a2_full_support.py", SHARED_MATERIALS["tests/a2_full_support.py"]),
    (
        "tests/test_a2_full_acceptance.py",
        SHARED_MATERIALS["tests/test_a2_full_acceptance.py"],
    ),
    (
        "scripts/verification_scope_baseline.py",
        SHARED_MATERIALS["scripts/verification_scope_baseline.py"],
    ),
    (
        "scripts/verification_scope_collection.py",
        SHARED_MATERIALS["scripts/verification_scope_collection.py"],
    ),
)

REQUIRED_FIXTURE_FILES = (
    (
        "tests/verification_expectations.py",
        SHARED_MATERIALS["tests/verification_expectations.py"],
    ),
    (
        "tests/fixtures/verification_group_expectations.json",
        SHARED_MATERIALS["tests/fixtures/verification_group_expectations.json"],
    ),
    (
        "docs/verification/contracts-read-validation-history.md",
        "649e7cd781d7ca4a55c9baeb4df8cb280a184e19ca6e8884dd74e52c5e7e9cfb",
    ),
    (
        "docs/verification/contracts-backup-restore-history.md",
        SHARED_MATERIALS["docs/verification/contracts-backup-restore-history.md"],
    ),
    (
        "docs/verification/contracts-config-snapshots-history.md",
        "4d3d3e37b659dd060bf8ee0889c3dcedb14e1159cd7148df2fb849c6d2cfa2fa",
    ),
    (
        "docs/verification/contracts-runtime-config-history.md",
        "6d2f5b069cf12fc5895c5bca5a6074c5f3af3b2d7e7c1d6de5f317be122662c8",
    ),
    (
        "contracts/read/read/v1/schema.json",
        "1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111",
    ),
    (
        "contracts/read/read/v1/manifest.json",
        "3add9678f2eaf64e409ef4f02fcc1e87556d987e7c83cf9e94a4f563ce378e2c",
    ),
    (
        "examples/contracts/read/read/v1/schema.json",
        "1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111",
    ),
    (
        "examples/contracts/read/read/v1/manifest.json",
        "3add9678f2eaf64e409ef4f02fcc1e87556d987e7c83cf9e94a4f563ce378e2c",
    ),
    (
        "contracts/screening/boundary/v1/schema.json",
        "9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7",
    ),
    (
        "contracts/screening/boundary/v1/manifest.json",
        "5efa0aec0e41329fe8736dcd533706309fd9c3717aeac14ddbf55d05cce0ed0b",
    ),
    (
        "examples/config/settings-read-ready.yaml",
        "f445dcfadf5807d99c645042b6e1cea8cb316bc56052a491288ed01f977522db",
    ),
    (
        "examples/config/profiles/profile-example-v1.yaml",
        SHARED_MATERIALS["examples/config/profiles/profile-example-v1.yaml"],
    ),
    (
        "examples/config/models/models-read-v1.yaml",
        SHARED_MATERIALS["examples/config/models/models-read-v1.yaml"],
    ),
    (
        "examples/config/read/read-v1.yaml",
        SHARED_MATERIALS["examples/config/read/read-v1.yaml"],
    ),
    (
        "examples/config/adapters/pi-v1.yaml",
        SHARED_MATERIALS["examples/config/adapters/pi-v1.yaml"],
    ),
    (
        "examples/config/prompts/pi-system-v1.md",
        SHARED_MATERIALS["examples/config/prompts/pi-system-v1.md"],
    ),
    (
        "examples/prompts/screening/boundary-v1.md",
        SHARED_MATERIALS["examples/prompts/screening/boundary-v1.md"],
    ),
    (
        "examples/prompts/reading/v1.md",
        SHARED_MATERIALS["examples/prompts/reading/v1.md"],
    ),
    (
        "examples/contracts/screening/boundary/v1/schema.json",
        SHARED_MATERIALS["examples/contracts/screening/boundary/v1/schema.json"],
    ),
    (
        "examples/contracts/screening/boundary/v1/manifest.json",
        SHARED_MATERIALS["examples/contracts/screening/boundary/v1/manifest.json"],
    ),
    (
        "docs/verification/a9-scope-review.md",
        "df26042232b218c2369ce2a231b8713c3c47b9089b4de45f9c71c22213be448e",
    ),
    (
        "docs/verification/offline-evidence.md",
        SHARED_MATERIALS["docs/verification/offline-evidence.md"],
    ),
    (
        "tests/fixtures/a9_coverage.json",
        "94630d67864357a4aa014aae7b9b25b0730ad3cdd5830c9da93142a3f3973c16",
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = (
    "scripts/a1_scope.py",
    "scripts/a2_full_scope.py",
    "scripts/a3_scope.py",
    "scripts/a4_scope.py",
    "scripts/a5_scope.py",
    "scripts/a6_scope.py",
    "scripts/a7_scope.py",
    "scripts/a8_scope.py",
)
