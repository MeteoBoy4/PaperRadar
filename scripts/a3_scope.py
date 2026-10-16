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
