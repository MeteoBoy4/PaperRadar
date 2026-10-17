"""A3 固定范围的分票登记。完整结论由 #35 追加,不提前声明通过。"""

MIGRATION_REVISION = "a302_artifact_store"
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
        "cbf935e97369de7e8a4d91ae9b9bf0204b97843758b35fddd7843282c4c634a1",
    ),
)

ARTIFACT_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/storage/filesystem.py",
        "b0904b630bb476eb4a7286ec9b6623176e83549be8c0a33faec7e29a1480e91e",
    ),
    (
        "src/paper_radar/storage/artifact_contract.py",
        "2287ecd3a20534fe543e9bb76a9f3f340ffce56f032d02bbac95a2242605c52c",
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
        "5683437b39720416313c52836ceb956ec3cff266e07a0e04c6e0ce985c47d437",
    ),
    (
        "tests/artifact_process/sitecustomize.py",
        "279ca4aee0a554dd5477d6fc29ed4ddc4a21b80945d2ab19d389dc7f667c103c",
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
        "bce97c2f5d2f9bafd0c7c02f3318f26f3234c58363355382321bfa08ba320ab8",
    ),
    (
        "tests/extraction_process/sitecustomize.py",
        "83663351d5dfb4a4d852427bb69d910a225cd851468cf18958bf7e8e9a39b814",
    ),
    (
        "tests/extraction_process/publish.py",
        "c5635659f003aa8fae601b1d8a0c51405a67571b2ccaed88f8f21a2d96252344",
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
        "e8178f418c0582f3f23baf2085755e7379d032d7da41df53c047f60ad6d9dcbb",
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
        "76712aa1788041f06909ccf4e553dc45a689f0b1903c36607939e9e3d36acc1c",
    ),
    (
        "src/paper_radar/backup/__init__.py",
        "b03e71f04496d78aceb9ab27b399945c72d4ac150db3a47f45e52a6696558078",
    ),
    (
        "src/paper_radar/backup/manifest.py",
        "696f76c0fa36189876666147728e77d6ae17c5decf8a143e263de6b97634816a",
    ),
    (
        "src/paper_radar/backup/files.py",
        "8bf4f05fea2085b1e6b25bb0ae426db2c13da47aa314dd695a1cd5c5259d36b8",
    ),
    (
        "src/paper_radar/backup/service.py",
        "558795cd55c8a38d85d443a1706ba8c46c8a6eee911cd666a88319d231f94b00",
    ),
    (
        "src/paper_radar/backup/cli.py",
        "440dfa1ebaed4d9ece76f48d68b6ada8ccd393e8d54c55ef54bba91e352a30aa",
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
        "43111ca84d5314ea4a792c36c966c0b9e79371431f6c0182fb6dc9fd0eff286f",
    ),
    (
        "tests/test_restore_failures.py",
        "2b836f517c6d26bf28365efec000af4b484f8d245c7b9c4d411be050ef3d9f02",
    ),
    (
        "tests/test_restore_cli.py",
        "cf55452b2085cd79270e288efdf6cb667ec7a7b5cf11432765c6b2d00600e99d",
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
        "fd2c22d11b9d8e2ef1d22d64c5214186f3b488b4517fee2326274417b52aa084",
    ),
    (
        "tests/restore_support.py",
        "89271ffd6bfd49a8844a09bb446c3252b296a57ebc050ecab3a1f1f88f4fbe13",
    ),
    (
        "tests/restore_process/sitecustomize.py",
        "bac18aeb70c29cfa677b594507f601353471a389b0bc02905b422eb7e43644d7",
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
    "backup_database_revision": "a302_artifact_store",
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
        "945a121f0f1620739cb05a607fb5c544e127ba388379037d7e3f772a58ccd78d",
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
        "e0a4ae1886025cfada7aa76fa932dc88f67372b5ea0cc49399f96a0899d1f1de",
    ),
    (
        "scripts/a2_test_receipt.py",
        "ae57161b128927697c6bc947f6dcd502482aa388bb3493a7681a1167e5ec58c2",
    ),
    (
        "scripts/offline_evidence.py",
        "0c613ee51748db53ebba7a9c9c260faa74391be0f3043646ee09867b420f6362",
    ),
    (
        "scripts/a2_full_scope.py",
        "3753c37b47adc8aa35efd1b2c5711c5f6381d684201318a1311203f04015d64d",
    ),
    (
        "scripts/check-offline",
        "7c1d116c0e9684a40193d33eb5b8f3862e690e83bd66183dfc00a4ceccd658c9",
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
        "4fc6e1daf4fe4539a1503fda8a1fc15cdef4515f9c17c2958fd2e311377c2dd5",
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
