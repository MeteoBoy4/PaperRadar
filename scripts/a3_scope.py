"""A3 固定范围的分票登记。完整结论由 #35 追加,不提前声明通过。"""

MIGRATION_REVISION = "a405_pi_cleanup_execution"
ARTIFACT_MIGRATION_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/storage/migrations/versions/a302_artifact_store.py",
        "0f15648cd3a8fc8cbe8938f1890894cfcba801643aff4204826910b35db88610",
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
        "470907d922401405fd71f3a5b8ea63d4dd6512aa8937bcb18ae2187ff46ddb30",
    ),
)

ARTIFACT_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/a3_process_support.py",
        "4c0ca963d2513532060c5f122f92b09933e234c4c65e342b78d3fd5d06880d74",
    ),
    (
        "src/paper_radar/storage/filesystem.py",
        "b0904b630bb476eb4a7286ec9b6623176e83549be8c0a33faec7e29a1480e91e",
    ),
    (
        "src/paper_radar/storage/artifact_contract.py",
        "ab8284b17b5710fe9e537f6edb88fff7fc84f686417f96e3558405699f1fa999",
    ),
    (
        "src/paper_radar/storage/artifact_repository.py",
        "e81d40c7330f4a2676524ead4c59bea4c263d81b447deeb32403c0599e7d222b",
    ),
    (
        "src/paper_radar/storage/artifacts.py",
        "45f08248581aaaa2681b9851e96039dd24a0743deabebc7c36fbb42535537681",
    ),
    (
        "src/paper_radar/storage/blob_store.py",
        "3507cc6db2ea5b4848790e5a2e25cc7d9f6e38a0f5a1371e18cb20d11953ad29",
    ),
    (
        "tests/artifact_support.py",
        "2771734fb913cb279be6aa9b9518b7d7e2bf70e2b7982f28e47b78be89000664",
    ),
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
        "47735236de9dfe8ce9d16592125f167931f4fd4f013a9434071059e75e995bb0",
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
        "08b5de8379ea9c357d7ed05c1d4a33f145d56066842e993a8cc0e7301dcb298e",
    ),
    (
        "src/paper_radar/backup/__init__.py",
        "b03e71f04496d78aceb9ab27b399945c72d4ac150db3a47f45e52a6696558078",
    ),
    (
        "src/paper_radar/backup/manifest.py",
        "06b1b6b18418ec8b75ef6f3552d6d5a10fae109d728074bcedb7150303a7c387",
    ),
    (
        "src/paper_radar/backup/files.py",
        "8bf4f05fea2085b1e6b25bb0ae426db2c13da47aa314dd695a1cd5c5259d36b8",
    ),
    (
        "src/paper_radar/backup/service.py",
        "82a303457d149beb586dca413688312540b37b3ad317b8777627b87e262672f7",
    ),
    (
        "src/paper_radar/backup/cli.py",
        "731e05af4659eefa8c52707516525e27244265ae0bdbd4a6a364228fda92d838",
    ),
    (
        "tests/backup_support.py",
        "f1ee3e3febb10bcf68212af621c79d0d25951fa1464cd11e23d2afe139e8cc37",
    ),
)

RESTORE_TEST_CASE_COUNTS = {
    "tests/test_restore_service.py": 4,
    "tests/test_restore_failures.py": 25,
    "tests/test_restore_cli.py": 11,
}

RESTORE_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_restore_service.py",
        "5ff4829e9d9fcc9406d1059f92d8523f280233f9dc9b4dc52bd57c43b52e5cde",
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
        "13d80b3ce3239dcc8159d02cc91ac50ac6abec1f526a8337b16fad8aba77b46f",
    ),
    (
        "src/paper_radar/backup/restore_contract.py",
        "9f251dd2aa193d3a6908361fd813c184d6dbe605aec122a7cf0de0db9262bb13",
    ),
    (
        "src/paper_radar/backup/restore_cli.py",
        "d168d5159b481ac48fdeff10c2931052a490cb1eea58b784a8494ce2cf81b6e5",
    ),
    (
        "tests/restore_support.py",
        "0ab9a716354d3c7481596a59e2ea20aac453de1602bc88712f119f1bab726736",
    ),
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
    "backup_database_revision": "a405_pi_cleanup_execution",
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
        "a8cb61f9cc8e05bbc602ec78e533350d49f0c307985b0d0d87e81eaae1775d0b",
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
        "287672af3d88e88c5696e5f73d7d546b709f9704991f332fcaea5fd804cbe6dc",
    ),
)
ACCEPTANCE_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "scripts/a3_acceptance.py",
        "bee7e6b29c2fe1ef4e96311a3c1626e24c7266e440c2e1a685afba1a0448229e",
    ),
    (
        "scripts/verification_checks.py",
        "73486e83dbeb8fd71738593a6cd48a45eb311aca29bbfc6af8dab8be2d9ea266",
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
        "b16a9dbf5dfb4e54a6231e3177353091ed60ab092ab33478343554df69b143d0",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "00525c108e46d3295b64b14e0347e16358747f2bd011631fa5af30104b33fceb",
    ),
    (
        "scripts/a2_test_receipt.py",
        "60073cb71c01c949ee05dd54b7556f598f5f3e8a11a700e51f88e51ac5bb700a",
    ),
    (
        "scripts/offline_evidence.py",
        "0c613ee51748db53ebba7a9c9c260faa74391be0f3043646ee09867b420f6362",
    ),
    (
        "scripts/a2_full_scope.py",
        "cabe2e8a2a0f2b55f7715b762b6dd53447786784d5d84de9a58f3ace1be9fbbd",
    ),
    (
        "scripts/check-offline",
        "bbce8140a002e7fbf4a7cb8af13fb033bfd69b5c85790759e40a0b790ca4a1d2",
    ),
    (
        "src/paper_radar/storage/database.py",
        "ed8aba07f31eb6019c6d656a9147c682d74073bbdf4d268cd488bdb79ff3b7b1",
    ),
    (
        "src/paper_radar/storage/errors.py",
        "a8c859bb0d8a415599887d380218a46490c6e10afa9910c0360a4dda037db19f",
    ),
    (
        "src/paper_radar/storage/schema.py",
        "291db5e419f3a5a7fd88afab7f369569d0b8e754fa36932210418c0938050a0f",
    ),
    (
        "src/paper_radar/storage/migrations/env.py",
        "f22dfaeade1105d7eb46dda731916406fe521051ec0a76b7eeb1e915d42ffd27",
    ),
    (
        "src/paper_radar/cli.py",
        "f3157590452d21827f3b9087a6861610dafba7f54259b39faff46a6109b8ba97",
    ),
    (
        "tests/a3_acceptance_support.py",
        "86868063437584e26e02a90f64d4f4c0dc73d5a21292bd501e9bba2af7065f70",
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
    *ARTIFACT_MIGRATION_MODULES,
    *ARTIFACT_SOURCE_MODULES,
    *EXTRACTION_SOURCE_MODULES,
    *BACKUP_SOURCE_MODULES,
    *RESTORE_SOURCE_MODULES,
    *ACCEPTANCE_SOURCE_MODULES,
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
    (
        "tests/fixtures/a3_storage_recovery.json",
        "c052613cfcbd88f4021d3b16375f194e2b33baf09c1cb749492989a5e3df6c0b",
    ),
)
