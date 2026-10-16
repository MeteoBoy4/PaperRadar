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
        "269fad3788d4ba61469aede9a4f265515d37d3366ae496c378cfb476be44fd0b",
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
    "tests/test_backup_integrity.py": 31,
    "tests/test_backup_failures.py": 22,
    "tests/test_backup_cli.py": 10,
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
        "e6e56d22851119a3aadb2a4fc1b4f32d6567897e1d22f1a84562cbf32432f51b",
    ),
    (
        "tests/test_backup_failures.py",
        "e8178f418c0582f3f23baf2085755e7379d032d7da41df53c047f60ad6d9dcbb",
    ),
    (
        "tests/test_backup_cli.py",
        "28e0ed205fffc033b0d08b6b46efbe733b27ab9376e12b73e4865869cae73f4a",
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
        "src/paper_radar/backup/__init__.py",
        "b03e71f04496d78aceb9ab27b399945c72d4ac150db3a47f45e52a6696558078",
    ),
    (
        "src/paper_radar/backup/manifest.py",
        "696f76c0fa36189876666147728e77d6ae17c5decf8a143e263de6b97634816a",
    ),
    (
        "src/paper_radar/backup/files.py",
        "b641f85bae36522e4f797a9880ee950377a336b3c76c4d87434010bbccfbe78a",
    ),
    (
        "src/paper_radar/backup/service.py",
        "9199f46bf7316bb8b236193f07472ae3ef81ad4433df02dcd59baff65d812537",
    ),
    (
        "src/paper_radar/backup/cli.py",
        "2b9b7340a7548be7f625aed12c350200dbeb772ca95d01ac3b1b2c3d4fcad5ae",
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
        "9ad63d654c4e7b96e9edeaba0e08cc9c6b3d4f7daa58d9f4fc626f01cf791caa",
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
