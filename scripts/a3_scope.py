"""A3 固定范围的分票登记。完整结论由 #35 追加,不提前声明通过。"""

from scripts.verification_scope_materials import SHARED_MATERIALS

MIGRATION_REVISION = "body01_persistence"
ARTIFACT_MIGRATION_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/storage/migrations/versions/a302_artifact_store.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a302_artifact_store.py"
        ],
    ),
)

ARTIFACT_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_artifact_contract.py",
        "6ce2c81e66b7e8a16e0cc421c3d06d388cb5b59c4d75b36410c31687790f9802",
    ),
    (
        "tests/test_artifact_store.py",
        "4845e90c554214cedb26edbf3c5d018aacc9618e81e71c21e3063b2e3b83486a",
    ),
    (
        "tests/test_storage_migrations.py",
        "aa0f739ec2395e30476067f2f26c64d953ae7fe016feb57ebc8ff59f25f323e2",
    ),
)

ARTIFACT_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    ("tests/a3_process_support.py", SHARED_MATERIALS["tests/a3_process_support.py"]),
    (
        "src/paper_radar/storage/filesystem.py",
        SHARED_MATERIALS["src/paper_radar/storage/filesystem.py"],
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
    ("tests/artifact_support.py", SHARED_MATERIALS["tests/artifact_support.py"]),
    (
        "tests/artifact_process/sitecustomize.py",
        "93a006ce86ff483ac1bd6fdb574533acc859faf82dca5fae074bb173395f2bc4",
    ),
)

EXTRACTION_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_extraction_artifacts.py",
        "30598e956ed5c4edb1a9bd856dd9fd40d1fced6f6e9b07d5952c7ba7d4958d1f",
    ),
)

EXTRACTION_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/extraction_support.py",
        "80256c1af3b704e3af144e86b824a977814ad33e9fc44416cb66a27400db1a62",
    ),
    (
        "tests/extraction_process/sitecustomize.py",
        "d578b4442de5f5cd067856dce0bae7b0ef2b0cdfcc64e4dacf478a28d6399e73",
    ),
    (
        "tests/extraction_process/publish.py",
        "8352771231a938a6f8b0668d7c7773913ce234bb0727feb6652e5e002820b90e",
    ),
    (
        "tests/fixtures/extraction_artifact_vectors.json",
        "efb9f44cbe705bdb5550d330b215907a5da43d6ca07bf743dc156b6521c52db4",
    ),
)

BACKUP_TEST_CASE_COUNTS = {
    "tests/test_backup_service.py": 5,
    "tests/test_backup_integrity.py": 34,
    "tests/test_backup_failures.py": 22,
    "tests/test_backup_cli.py": 11,
    "tests/test_backup_wheel.py": 1,
    "tests/test_backup_architecture.py": 1,
}

BACKUP_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_backup_service.py",
        "2441188d51266e0faa3beeee4ab7cd8cbead67b08ca7c80e151751f2b5c3996e",
    ),
    (
        "tests/test_backup_integrity.py",
        "d3e9f2e0c0946b30ed91848d4684d4847c85b6d47666f22a919d9976ddf87e72",
    ),
    (
        "tests/test_backup_failures.py",
        "8f9ac9003640285f24c6f24bdc751ce96031006cc37fa6b217795b5aee1d6817",
    ),
    (
        "tests/test_backup_cli.py",
        "a816f90c9835dc98b0a41d6e15e9ead4229bf1ae12322ac409e5fa2e748dab24",
    ),
    (
        "tests/test_backup_wheel.py",
        "4e7b6aaff1cfc41b74b3bae993ac3b74e6ff6e14b252a6767783858e0674c338",
    ),
    (
        "tests/test_backup_architecture.py",
        "9a5fc57a6c40d2ac487a399c778c3c130aac1d6ae0d51ece2189374f77ee4558",
    ),
)

BACKUP_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/backup/cli_support.py",
        SHARED_MATERIALS["src/paper_radar/backup/cli_support.py"],
    ),
    (
        "src/paper_radar/backup/__init__.py",
        SHARED_MATERIALS["src/paper_radar/backup/__init__.py"],
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
        "src/paper_radar/backup/service.py",
        SHARED_MATERIALS["src/paper_radar/backup/service.py"],
    ),
    (
        "src/paper_radar/backup/cli.py",
        SHARED_MATERIALS["src/paper_radar/backup/cli.py"],
    ),
    ("tests/backup_support.py", SHARED_MATERIALS["tests/backup_support.py"]),
)

RESTORE_TEST_CASE_COUNTS = {
    "tests/test_restore_service.py": 4,
    "tests/test_restore_failures.py": 25,
    "tests/test_restore_cli.py": 11,
}

RESTORE_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_restore_service.py",
        "4efb6f4378aa966e26826112f4931c7bb7af9180d9fbb08ffb0ba34cc43de023",
    ),
    (
        "tests/test_restore_failures.py",
        "2b836f517c6d26bf28365efec000af4b484f8d245c7b9c4d411be050ef3d9f02",
    ),
    (
        "tests/test_restore_cli.py",
        "909a836ceb590aa3767b016300343cb37403d3266df896cdaf6756d708e5c12d",
    ),
)

RESTORE_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/backup/restore.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore.py"],
    ),
    (
        "src/paper_radar/backup/restore_contract.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore_contract.py"],
    ),
    (
        "src/paper_radar/backup/restore_cli.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore_cli.py"],
    ),
    ("tests/restore_support.py", SHARED_MATERIALS["tests/restore_support.py"]),
    (
        "tests/restore_process/sitecustomize.py",
        "5db3ad1399ca9d83f4a8143f6724f45dd632b72fd6b246feab9dc75f35b713ae",
    ),
    (
        "tests/restore_process/query.py",
        "aaaf457c74e2c996b69b748a81066b0a2f1982a43ac050586413eb576a941877",
    ),
)

# #35 显式聚合;只读这些已审查清单,不扫描测试目录生成期望。
SCOPE = "a3_artifact_backup_restore"
ISSUE = 35
PARENT_ISSUE = 29
FORMAT_VERSION = 1
SUFFIX = ".a3.json"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic", "typer")
FORMAT_VERSIONS = {
    "artifact": 1,
    "blob_layout": 1,
    "backup": 1,
    "backup_database_revision": "body01_persistence",
}
CAPABILITIES = (
    "artifact_publication",
    "migration",
    "wal_backup",
    "manifest_verification",
    "isolated_restore",
    "restored_queries",
)
NOT_ASSESSED = (
    "paper_business_facts",
    "stage_input_fingerprints",
    "attempts_and_leases",
    "shared_eligibility",
    "calibration_visibility",
    "report_rebuild",
    "task_resume",
    "pi_execution",
    "pi_environment_recovery",
    "docling_execution",
    "read_execution",
    "doctor",
    "structured_logs",
    "live_source_audit",
    "nas_restore",
    "automatic_fulltext_reading",
    "stage_b",
)
# 独立收集核对: 制品15/25、迁移23、extraction34;不从运行时收集结果刷新。
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_artifact_contract.py": 15,
    "tests/test_artifact_store.py": 25,
    "tests/test_storage_migrations.py": 23,
    "tests/test_extraction_artifacts.py": 34,
    **BACKUP_TEST_CASE_COUNTS,
    **RESTORE_TEST_CASE_COUNTS,
    "tests/test_a3_acceptance.py": 46,
    "tests/test_a3_combination.py": 1,
    "tests/test_a3_test_receipt.py": 6,
    "tests/test_a3_entry.py": 4,
}
ACCEPTANCE_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_a3_acceptance.py",
        "9f388ea326b86aa2734769629c21d8f47588b7493305c203b7cd88783eedbca3",
    ),
    (
        "tests/test_a3_combination.py",
        "1c24e24f093f7352ca2a115348db2074cd78e46ed8f34f2bf8ab004765992813",
    ),
    (
        "tests/test_a3_test_receipt.py",
        "e17200e1def799e8d0c7fd4709a7cf919cc2e4ab39d0d149a49521b968f15cda",
    ),
    (
        "tests/test_a3_entry.py",
        "ff485b0444053c98c0e771b2c54d703930a2eaa6a2e1f85228f226fabd985d9f",
    ),
)
ACCEPTANCE_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    ("scripts/a3_acceptance.py", SHARED_MATERIALS["scripts/a3_acceptance.py"]),
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
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/offline_evidence.py", SHARED_MATERIALS["scripts/offline_evidence.py"]),
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
    (
        "src/paper_radar/storage/database.py",
        SHARED_MATERIALS["src/paper_radar/storage/database.py"],
    ),
    (
        "src/paper_radar/storage/errors.py",
        SHARED_MATERIALS["src/paper_radar/storage/errors.py"],
    ),
    (
        "src/paper_radar/storage/schema.py",
        SHARED_MATERIALS["src/paper_radar/storage/schema.py"],
    ),
    (
        "src/paper_radar/storage/migrations/env.py",
        SHARED_MATERIALS["src/paper_radar/storage/migrations/env.py"],
    ),
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    (
        "tests/a3_acceptance_support.py",
        SHARED_MATERIALS["tests/a3_acceptance_support.py"],
    ),
)
REQUIRED_TEST_MODULES = (
    *ARTIFACT_TEST_MODULES,
    *EXTRACTION_TEST_MODULES,
    *BACKUP_TEST_MODULES,
    *RESTORE_TEST_MODULES,
    *ACCEPTANCE_TEST_MODULES,
)
REQUIRED_SOURCE_MODULES = (
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
    ),
    *ARTIFACT_MIGRATION_MODULES,
    *ARTIFACT_SOURCE_MODULES,
    *EXTRACTION_SOURCE_MODULES,
    *BACKUP_SOURCE_MODULES,
    *RESTORE_SOURCE_MODULES,
    *ACCEPTANCE_SOURCE_MODULES,
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
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
        "tests/fixtures/a3_storage_recovery.json",
        "c052613cfcbd88f4021d3b16375f194e2b33baf09c1cb749492989a5e3df6c0b",
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = ("scripts/a2_full_scope.py",)
