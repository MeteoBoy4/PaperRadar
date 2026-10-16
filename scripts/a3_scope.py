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
