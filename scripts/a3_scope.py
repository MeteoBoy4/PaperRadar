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
        "7b3070d5daece329b0ee4d9a0f8c4f6b1560bcbe859532b635edca8734600051",
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
        "26c04d4a915a9ec29fd6db4086ff5eccb50cd2ee32397242178baa445e82503b",
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
        "d11cae9747406968a106eb7e94a3d96d36f85808f1b28867801cab3d75a1c8c8",
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
        "3bd4b1c567638fcd16ed76685e2c6c8e0540383cbbdfb3c5555ac29c38d54cd9",
    ),
    (
        "tests/backup_support.py",
        "f1ee3e3febb10bcf68212af621c79d0d25951fa1464cd11e23d2afe139e8cc37",
    ),
)
