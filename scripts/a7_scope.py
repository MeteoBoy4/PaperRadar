"""#84 固定 A7 验收范围;预期由人工审阅源码和参数化登记,运行时不能刷新。"""

from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a7_screening_tasks"
ISSUE = 84
PARENT_ISSUE = 76
FORMAT_VERSION = 1
SUFFIX = ".a7.json"
MIGRATION_REVISION = "feed07_parser_versions"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "screening_tasks": 1,
    "task_reason_catalog": 1,
    "task_query_result": 1,
    "stage_inputs": {"boundary": 1, "value": 1},
    "backup": 1,
}
CAPABILITIES = (
    "frozen_input",
    "request_idempotency",
    "budget_scope",
    "atomic_claim",
    "lease",
    "bounded_attempts",
    "authoritative_acceptance",
    "derived_applicability",
    "explicit_retry",
    "shared_query",
    "crash_recovery",
    "migration",
    "isolated_restore",
    "semantic_integrity",
    "privacy",
)
NOT_ASSESSED = (
    "rpc_compatibility",
    "pi_execution",
    "real_model_usage_cost",
    "original_title_language_production_wiring",
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
)
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_a7_text_boundaries.py": 26,
    "tests/test_screening_strict_json.py": 93,
    "tests/test_a7_registration.py": 6,
    "tests/test_a7_registration_failures.py": 34,
    "tests/test_a7_registration_migrations.py": 6,
    "tests/test_a7_registration_backup.py": 10,
    "tests/test_a7_registration_process.py": 7,
    "tests/test_a7_registration_imports.py": 1,
    "tests/test_a7_attempts.py": 12,
    "tests/test_a7_driver_preconditions.py": 9,
    "tests/test_a7_attempt_inputs.py": 6,
    "tests/test_a7_attempts_process.py": 11,
    "tests/test_a7_attempt_integrity.py": 12,
    "tests/test_a7_attempt_backup.py": 2,
    "tests/test_a7_attempt_migrations.py": 5,
    "tests/test_a7_boundary_success.py": 22,
    "tests/test_a7_success_applicability.py": 4,
    "tests/test_a7_success_process.py": 9,
    "tests/test_a7_success_integrity.py": 16,
    "tests/test_a7_success_backup.py": 6,
    "tests/test_a7_success_migrations.py": 5,
    "tests/test_a7_value_success.py": 26,
    "tests/test_a7_value_context.py": 5,
    "tests/test_a7_value_integrity.py": 2,
    "tests/test_a7_value_backup.py": 7,
    "tests/test_a7_retry.py": 27,
    "tests/test_a7_task_query.py": 3,
    "tests/test_a7_retry_process.py": 13,
    "tests/test_a7_retry_integrity.py": 1,
    "tests/test_a7_retry_backup.py": 7,
    "tests/test_a7_retry_migrations.py": 10,
    "tests/test_a7_complete_recovery.py": 1,
    "tests/test_a7_recovery_integrity.py": 7,
    "tests/test_a7_acceptance.py": 2,
    "tests/test_a7_integrity.py": 124,
    "tests/test_a7_entry.py": 9,
    "tests/test_a7_status.py": 10,
    "tests/test_a7_test_receipt.py": 6,
    "tests/test_a7_formats.py": 2,
}
REQUIRED_TEST_MODULES = (
    (
        "tests/test_a7_text_boundaries.py",
        "098c55eb94315e82b7ed056f7707e0c8962ba7b11d99a0731bab1911ad70e577",
    ),
    (
        "tests/test_a7_driver_preconditions.py",
        "f75e3ad8801affb1ed672019e54f98e62cc3400db99d04e61ee3890d172e528d",
    ),
    (
        "tests/test_screening_strict_json.py",
        "49365327a4a2d6599c62c049f5e3dd8d2001aa4c25741a9f545b842b81c48c53",
    ),
    (
        "tests/test_a7_registration.py",
        "7087fc72b6e5053117d43eda641954d0313065e3f8b4e218de5f2478f308f5c9",
    ),
    (
        "tests/test_a7_registration_failures.py",
        "fa43dd827543962c902b536ac9b2040753bde02bfe5a7ced2351c6d99e3b9950",
    ),
    (
        "tests/test_a7_registration_migrations.py",
        "686efabe18a0b5920dabe6fb600c9f07758b295c163252df071b46a9948f27ad",
    ),
    (
        "tests/test_a7_registration_backup.py",
        "7adec86631d46ed281a9ae7e56a9ae0b0d127803039e668752a746d92a6f014a",
    ),
    (
        "tests/test_a7_registration_process.py",
        "4e30dd3b34637a600700d54fbbc585d877c957b8c166a6a0fd9206f542f99e5d",
    ),
    (
        "tests/test_a7_registration_imports.py",
        "4b5bb6f5d7645cb68cdf18f35f52d5349a16d8230b1da47b40a7c09679cf91e0",
    ),
    (
        "tests/test_a7_attempts.py",
        "9a4daf25625d04bccc1f3b6b9a8954fc501499452f38b4e02ff7917a8de4d591",
    ),
    (
        "tests/test_a7_attempt_inputs.py",
        "f141919936cc9ea343c8cc428c07743a9779806081fa259b695c56b5d2613e08",
    ),
    (
        "tests/test_a7_attempts_process.py",
        "1aef93556ed121ff2158807663474f7f200d3dae55413ff3fccaa4edb7b0b837",
    ),
    (
        "tests/test_a7_attempt_integrity.py",
        "8280b4cd30e33cf6836a25b838a3a9018700964ed329cc363fd90c96ab522860",
    ),
    (
        "tests/test_a7_attempt_backup.py",
        "6ada8112da3ef93ded133f0e238a8054c77c5f2333a9780219ec90d92c2736d8",
    ),
    (
        "tests/test_a7_attempt_migrations.py",
        "198f4cf315700145032410d49b3b07fe1ab3fe51e5fb131da45f2ba24b26ca53",
    ),
    (
        "tests/test_a7_boundary_success.py",
        "084419b0317f383d355b75e3ecbb3d24e2570e3eff3542d640a0de98a428368e",
    ),
    (
        "tests/test_a7_success_applicability.py",
        "4439f43c479b9a5ccfa759158936afa0bdce49bf233e30b3dc2e24db31e3e2ef",
    ),
    (
        "tests/test_a7_success_process.py",
        "a4a50ca4e183a7eb552b9c162c9c4092c5115eb61345bc77c813619c57eb6083",
    ),
    (
        "tests/test_a7_success_integrity.py",
        "f55dd205c74297a1dc532160393a0b89a5460791cc5fb2e3e36af3d708d4b70d",
    ),
    (
        "tests/test_a7_success_backup.py",
        "2d5f7156f96947ff16c6ec10581d38515daa7679d38d3c679d762aa78c4bd00b",
    ),
    (
        "tests/test_a7_success_migrations.py",
        "05b70f51724e9d4771042aec3a5fef7b7ca34232b1d76859f076bebc1ee6b20e",
    ),
    (
        "tests/test_a7_value_success.py",
        "c3a1ec47cab7f37ce64085c05888e8e4ff026ad802d436ab2c359698b2a1d65d",
    ),
    (
        "tests/test_a7_value_context.py",
        "599c22d81edd9ad40b596dc848071d68a7df4da595160074343a51de151f2b8e",
    ),
    (
        "tests/test_a7_value_integrity.py",
        "cb87bcc2343088a2b90191224de9ef5223f2c8f18c4c6bf2f43cd8a9b196ab34",
    ),
    (
        "tests/test_a7_value_backup.py",
        "ec3ded1784b54e59438189d99912e8cf6e9afb923c47d8b5e8c1d0750f975f85",
    ),
    (
        "tests/test_a7_retry.py",
        "2854cd2aa8730c35b3be95a21680e7f5fba147ba52f404ffa901b62e4da5e0e2",
    ),
    (
        "tests/test_a7_task_query.py",
        "6d72e8be766747ffdf6dd142780de9a6edbf41698ff38befd7dcfd9fe836a452",
    ),
    (
        "tests/test_a7_retry_process.py",
        "a82636bab2373a79f145d0ab1bc5edadd6eb39703e3477c2e1ddd9777d052b92",
    ),
    (
        "tests/test_a7_retry_integrity.py",
        "28fc7631fca2234f0e42b2db47d87bda4ccb02254026195fc34d1c41c6e6c0e7",
    ),
    (
        "tests/test_a7_retry_backup.py",
        "66766165bf6c73ac8f66108c9cd46a43997dba75dbd8202be4dd781b1ef52d24",
    ),
    (
        "tests/test_a7_retry_migrations.py",
        "64a8c97a09769a0b039aa6e77794a8438f27b2af7dc4c1b2fac3817ed2fa5b54",
    ),
    (
        "tests/test_a7_complete_recovery.py",
        SHARED_MATERIALS["tests/test_a7_complete_recovery.py"],
    ),
    (
        "tests/test_a7_recovery_integrity.py",
        "004720e9612a0245095f94254650b6bb54fdf464cf4bdc37b007889253e73fec",
    ),
    (
        "tests/test_a7_acceptance.py",
        "bc517972142a5ad9336897cb97344e2e31cbcf3e2a7ab5c80c1bee9c66b7cfa2",
    ),
    (
        "tests/test_a7_integrity.py",
        "8a25915cbac7927c8a1b9f1ab6d4a47595628c4119772cff520f46a0fca95986",
    ),
    (
        "tests/test_a7_entry.py",
        "979989f8bdfa59297b181bc29adfeb33b746a9963edc1f93848e966d83d05e0e",
    ),
    (
        "tests/test_a7_status.py",
        "6bd334471fd7f1b8d833f6c6185483fd4cd14f97a61895f8a609b19cbe7391d0",
    ),
    (
        "tests/test_a7_test_receipt.py",
        "f4e218adc18b69209038ffca1b333489b2ec30b0529c0ca2dbc318e0f6fff54f",
    ),
    (
        "tests/test_a7_formats.py",
        "2012379576ac3adc501562862a10c4a42c298586bf58bbaed5b68e57a32107c4",
    ),
)
REQUIRED_SOURCE_MODULES = (
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
    ),
    (
        "src/paper_radar/screening_tasks/attempt_repository.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/attempt_repository.py"],
    ),
    (
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/a7_acceptance.py", SHARED_MATERIALS["scripts/a7_acceptance.py"]),
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
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
        "src/paper_radar/backup/files.py",
        SHARED_MATERIALS["src/paper_radar/backup/files.py"],
    ),
    (
        "src/paper_radar/backup/manifest.py",
        SHARED_MATERIALS["src/paper_radar/backup/manifest.py"],
    ),
    (
        "src/paper_radar/backup/restore.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore.py"],
    ),
    (
        "src/paper_radar/backup/restore_contract.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore_contract.py"],
    ),
    (
        "src/paper_radar/backup/service.py",
        SHARED_MATERIALS["src/paper_radar/backup/service.py"],
    ),
    (
        "src/paper_radar/config/compile.py",
        SHARED_MATERIALS["src/paper_radar/config/compile.py"],
    ),
    (
        "src/paper_radar/config/identity.py",
        SHARED_MATERIALS["src/paper_radar/config/identity.py"],
    ),
    (
        "src/paper_radar/config/projections.py",
        SHARED_MATERIALS["src/paper_radar/config/projections.py"],
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
        "src/paper_radar/papers/errors.py",
        SHARED_MATERIALS["src/paper_radar/papers/errors.py"],
    ),
    (
        "src/paper_radar/papers/fact_reads.py",
        SHARED_MATERIALS["src/paper_radar/papers/fact_reads.py"],
    ),
    (
        "src/paper_radar/papers/mapping.py",
        SHARED_MATERIALS["src/paper_radar/papers/mapping.py"],
    ),
    (
        "src/paper_radar/papers/mapping_models.py",
        SHARED_MATERIALS["src/paper_radar/papers/mapping_models.py"],
    ),
    (
        "src/paper_radar/papers/models.py",
        SHARED_MATERIALS["src/paper_radar/papers/models.py"],
    ),
    (
        "src/paper_radar/papers/queries.py",
        SHARED_MATERIALS["src/paper_radar/papers/queries.py"],
    ),
    (
        "src/paper_radar/papers/read_checks.py",
        SHARED_MATERIALS["src/paper_radar/papers/read_checks.py"],
    ),
    (
        "src/paper_radar/papers/repository.py",
        SHARED_MATERIALS["src/paper_radar/papers/repository.py"],
    ),
    (
        "src/paper_radar/papers/rules.py",
        SHARED_MATERIALS["src/paper_radar/papers/rules.py"],
    ),
    (
        "src/paper_radar/papers/selection_repository.py",
        SHARED_MATERIALS["src/paper_radar/papers/selection_repository.py"],
    ),
    (
        "src/paper_radar/papers/tables.py",
        SHARED_MATERIALS["src/paper_radar/papers/tables.py"],
    ),
    (
        "src/paper_radar/papers/text_rules.py",
        SHARED_MATERIALS["src/paper_radar/papers/text_rules.py"],
    ),
    (
        "src/paper_radar/screening/context.py",
        SHARED_MATERIALS["src/paper_radar/screening/context.py"],
    ),
    (
        "src/paper_radar/screening/errors.py",
        SHARED_MATERIALS["src/paper_radar/screening/errors.py"],
    ),
    (
        "src/paper_radar/screening/schema.py",
        SHARED_MATERIALS["src/paper_radar/screening/schema.py"],
    ),
    (
        "src/paper_radar/screening/text.py",
        SHARED_MATERIALS["src/paper_radar/screening/text.py"],
    ),
    (
        "src/paper_radar/screening/validation.py",
        SHARED_MATERIALS["src/paper_radar/screening/validation.py"],
    ),
    (
        "src/paper_radar/screening/value_types.py",
        SHARED_MATERIALS["src/paper_radar/screening/value_types.py"],
    ),
    (
        "src/paper_radar/screening_tasks/__init__.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/__init__.py"],
    ),
    (
        "src/paper_radar/screening_tasks/attempt_integrity.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/attempt_integrity.py"],
    ),
    (
        "src/paper_radar/screening_tasks/attempt_models.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/attempt_models.py"],
    ),
    (
        "src/paper_radar/screening_tasks/attempt_rules.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/attempt_rules.py"],
    ),
    (
        "src/paper_radar/screening_tasks/database_errors.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/database_errors.py"],
    ),
    (
        "src/paper_radar/screening_tasks/errors.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/errors.py"],
    ),
    (
        "src/paper_radar/screening_tasks/execution.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/execution.py"],
    ),
    (
        "src/paper_radar/screening_tasks/frozen.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/frozen.py"],
    ),
    (
        "src/paper_radar/screening_tasks/integrity.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/integrity.py"],
    ),
    (
        "src/paper_radar/screening_tasks/models.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/models.py"],
    ),
    (
        "src/paper_radar/screening_tasks/query.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/query.py"],
    ),
    (
        "src/paper_radar/screening_tasks/query_models.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/query_models.py"],
    ),
    (
        "src/paper_radar/screening_tasks/repository.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/repository.py"],
    ),
    (
        "src/paper_radar/screening_tasks/retry.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/retry.py"],
    ),
    (
        "src/paper_radar/screening_tasks/rules.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/rules.py"],
    ),
    (
        "src/paper_radar/screening_tasks/service.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/service.py"],
    ),
    (
        "src/paper_radar/screening_tasks/success.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/success.py"],
    ),
    (
        "src/paper_radar/screening_tasks/success_integrity.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/success_integrity.py"],
    ),
    (
        "src/paper_radar/screening_tasks/success_models.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/success_models.py"],
    ),
    (
        "src/paper_radar/screening_tasks/success_rules.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/success_rules.py"],
    ),
    (
        "src/paper_radar/screening_tasks/tables.py",
        SHARED_MATERIALS["src/paper_radar/screening_tasks/tables.py"],
    ),
    (
        "src/paper_radar/stage_inputs/__init__.py",
        SHARED_MATERIALS["src/paper_radar/stage_inputs/__init__.py"],
    ),
    (
        "src/paper_radar/stage_inputs/service.py",
        SHARED_MATERIALS["src/paper_radar/stage_inputs/service.py"],
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
        "src/paper_radar/storage/artifacts.py",
        SHARED_MATERIALS["src/paper_radar/storage/artifacts.py"],
    ),
    (
        "src/paper_radar/storage/blob_store.py",
        SHARED_MATERIALS["src/paper_radar/storage/blob_store.py"],
    ),
    (
        "src/paper_radar/storage/database.py",
        SHARED_MATERIALS["src/paper_radar/storage/database.py"],
    ),
    (
        "src/paper_radar/storage/filesystem.py",
        SHARED_MATERIALS["src/paper_radar/storage/filesystem.py"],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a701_screening_registration.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a701_screening_registration.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a702_screening_attempts.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a702_screening_attempts.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a703_screening_success.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a703_screening_success.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a704_screening_retry.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a704_screening_retry.py"
        ],
    ),
    (
        "src/paper_radar/storage/records.py",
        SHARED_MATERIALS["src/paper_radar/storage/records.py"],
    ),
    (
        "src/paper_radar/storage/repository.py",
        SHARED_MATERIALS["src/paper_radar/storage/repository.py"],
    ),
    (
        "src/paper_radar/storage/schema.py",
        SHARED_MATERIALS["src/paper_radar/storage/schema.py"],
    ),
    ("tests/a2_full_support.py", SHARED_MATERIALS["tests/a2_full_support.py"]),
    (
        "tests/a3_acceptance_support.py",
        SHARED_MATERIALS["tests/a3_acceptance_support.py"],
    ),
    ("tests/a3_process_support.py", SHARED_MATERIALS["tests/a3_process_support.py"]),
    (
        "tests/a4_acceptance_support.py",
        SHARED_MATERIALS["tests/a4_acceptance_support.py"],
    ),
    (
        "tests/a5_acceptance_support.py",
        SHARED_MATERIALS["tests/a5_acceptance_support.py"],
    ),
    (
        "tests/a6_acceptance_support.py",
        SHARED_MATERIALS["tests/a6_acceptance_support.py"],
    ),
    (
        "tests/a7_acceptance_support.py",
        SHARED_MATERIALS["tests/a7_acceptance_support.py"],
    ),
    (
        "tests/a7_attempts_process/sitecustomize.py",
        "9957b8549356b4f540c3c2c41534eff293f25093f2354436c2c3d0257d87433b",
    ),
    (
        "tests/a7_attempts_worker.py",
        "95b9023990a1e7965b36ec0e282345fda8382cf6ee78cf37b055159f74e4b41d",
    ),
    (
        "tests/a7_recovery_support.py",
        "f9f98ea554614ebc7de14795c405d8034bde0bea37f4abb1d46d8c4a818660c9",
    ),
    (
        "tests/a7_registration_process/sitecustomize.py",
        "d41a6eb7bbef9be01c5674dfb3105bbafbc53b7ca564e50e3e0c3e503f367408",
    ),
    (
        "tests/a7_registration_support.py",
        SHARED_MATERIALS["tests/a7_registration_support.py"],
    ),
    (
        "tests/a7_registration_worker.py",
        "aadb871af2c13b4d556e04385fc4a4bb33d11a1e0c0181ac042dffb14525c44c",
    ),
    (
        "tests/a7_retry_process/sitecustomize.py",
        "d09ee675d03850644cb29c48f26318c0eda68e50d4f807a73e985e40c233ac9e",
    ),
    ("tests/a7_retry_support.py", SHARED_MATERIALS["tests/a7_retry_support.py"]),
    (
        "tests/a7_retry_worker.py",
        "cef786836eb08ab21e1cc3677723601e64d6ac9a8048223b51b95226cb16cbc1",
    ),
    (
        "tests/a7_success_process/sitecustomize.py",
        "b28bf74b8c76d6c04db657e6214924cddad585d1ba32a5ac5f8b44d7b0e95d93",
    ),
    (
        "tests/a7_success_worker.py",
        "860935e856f476a96546ab83fb6bfefedc45733be1ec470ac1079cbd7033100a",
    ),
    ("tests/a7_value_support.py", SHARED_MATERIALS["tests/a7_value_support.py"]),
    ("tests/artifact_support.py", SHARED_MATERIALS["tests/artifact_support.py"]),
    ("tests/backup_support.py", SHARED_MATERIALS["tests/backup_support.py"]),
    (
        "tests/config_projection_support.py",
        SHARED_MATERIALS["tests/config_projection_support.py"],
    ),
    ("tests/config_test_support.py", SHARED_MATERIALS["tests/config_test_support.py"]),
    (
        "tests/deny_network/sitecustomize.py",
        SHARED_MATERIALS["tests/deny_network/sitecustomize.py"],
    ),
    ("tests/test_paper_mapping.py", SHARED_MATERIALS["tests/test_paper_mapping.py"]),
    ("tests/test_paper_service.py", SHARED_MATERIALS["tests/test_paper_service.py"]),
    (
        "tests/test_version_relations.py",
        SHARED_MATERIALS["tests/test_version_relations.py"],
    ),
)
REQUIRED_FIXTURE_FILES = (
    (
        "tests/migration_expectations.py",
        SHARED_MATERIALS["tests/migration_expectations.py"],
    ),
    (
        "tests/verification_expectations.py",
        SHARED_MATERIALS["tests/verification_expectations.py"],
    ),
    (
        "tests/fixtures/verification_group_expectations.json",
        SHARED_MATERIALS["tests/fixtures/verification_group_expectations.json"],
    ),
    (
        "tests/fixtures/a7_capabilities.json",
        "60701c091af0700149320a12b011b0883ad58eb933e5062f1fd6a6c1249e44b7",
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = (
    "scripts/a1_scope.py",
    "scripts/a2_full_scope.py",
    "scripts/a3_scope.py",
    "scripts/a5_scope.py",
    "scripts/a6_scope.py",
)
