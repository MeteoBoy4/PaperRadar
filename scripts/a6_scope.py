"""#75 固定 A6 验收范围;运行时不能刷新预期。"""

from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a6_paper_facts"
# ISSUE 是最后验收子票;PARENT_ISSUE 是业务规格。
ISSUE = 75
PARENT_ISSUE = 67
FORMAT_VERSION = 1
SUFFIX = ".a6.json"
MIGRATION_REVISION = "body01_persistence"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "paper_facts": 1,
    "doi_rules": 1,
    "text_norm": 1,
    "feed_item_fingerprint": 1,
    "reason_catalog": 1,
    "mapping_result": 1,
    "stage_inputs": {"boundary": 1, "value": 1},
    "backup": 1,
}
CAPABILITIES = (
    "doi_identity",
    "feed_discovery",
    "version_selection",
    "field_arbitration",
    "consistent_read",
    "input_mapping",
    "historical_rebuild",
    "concurrency",
    "crash_recovery",
    "migration",
    "cli",
    "isolated_restore",
)
NOT_ASSESSED = (
    "merge_undo",
    "arxiv_pmid",
    "real_source_authenticity",
    "source_assumptions_guid_landing_page_elocator_entry_stability_crossref",
    "parser_completeness_and_stage_c_fixed_sample_upgrade_gate",
    "stage_c_strong_conflict_persistence_gate",
    "html_extraction",
    "truncation_detection",
    "metadata_ready",
    "eligibility",
    "task_budget",
    "complete_visibility",
    "rpc_compatibility",
    "pi_execution",
    "docling_execution",
    "nas_restore",
    "stage_a",
    "live",
    "automatic_fulltext_reading",
    "calibration_workflow",
    "read_fingerprints",
    "suggestion_fingerprints",
    "report_fingerprints",
)
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_paper_review_boundaries.py": 22,
    "tests/test_paper_review_reads.py": 18,
    "tests/test_a6_review_formats.py": 4,
    "tests/test_pending_relation_roles.py": 5,
    "tests/test_paper_model_validation.py": 7,
    "tests/test_feed_arbitration.py": 5,
    "tests/test_feed_backup.py": 18,
    "tests/test_feed_cli.py": 1,
    "tests/test_feed_discovery.py": 4,
    "tests/test_feed_identity.py": 7,
    "tests/test_feed_inputs.py": 18,
    "tests/test_feed_migrations.py": 5,
    "tests/test_feed_process.py": 6,
    "tests/test_feed_registration.py": 9,
    "tests/test_manual_corrections.py": 10,
    "tests/test_paper_acquisitions.py": 5,
    "tests/test_paper_backup.py": 9,
    "tests/test_paper_cli.py": 8,
    "tests/test_paper_identity.py": 31,
    "tests/test_paper_inputs.py": 52,
    "tests/test_paper_mapping.py": 10,
    "tests/test_paper_mapping_failures.py": 17,
    "tests/test_paper_mapping_process.py": 2,
    "tests/test_paper_migrations.py": 4,
    "tests/test_paper_process.py": 6,
    "tests/test_paper_recovery_combined.py": 2,
    "tests/test_paper_recovery_damage.py": 12,
    "tests/test_paper_recovery_integrity.py": 3,
    "tests/test_paper_reparse.py": 10,
    "tests/test_paper_service.py": 7,
    "tests/test_source_arbitration.py": 10,
    "tests/test_source_backup.py": 5,
    "tests/test_source_cli.py": 1,
    "tests/test_source_migrations.py": 5,
    "tests/test_source_process.py": 11,
    "tests/test_version_relation_backup.py": 8,
    "tests/test_version_relation_cli.py": 3,
    "tests/test_version_relation_inputs.py": 14,
    "tests/test_version_relation_materials.py": 2,
    "tests/test_version_relation_migrations.py": 5,
    "tests/test_version_relation_process.py": 7,
    "tests/test_version_relations.py": 13,
    "tests/test_a6_acceptance.py": 2,
    "tests/test_a6_entry.py": 9,
    "tests/test_a6_formats.py": 2,
    "tests/test_a6_integrity.py": 114,
    "tests/test_a6_status.py": 9,
    "tests/test_a6_test_receipt.py": 6,
}
REQUIRED_TEST_MODULES = (
    (
        "tests/test_paper_review_boundaries.py",
        "3c44a6dd132f62b2c7545e793cc72c4331f9da572c7ca45a342f4400d9a8d8b8",
    ),
    (
        "tests/test_paper_review_reads.py",
        "da8524714926494df05b27ef9589c85e0bb693c1578cc8b48a0f7a115b56cf4c",
    ),
    (
        "tests/test_a6_review_formats.py",
        "7e8ca8251efb421fe024eae2bbe8cdc5ff9008d817038c5dfe19bebced1c61b8",
    ),
    (
        "tests/test_pending_relation_roles.py",
        "16c07dad469a2d1cad0407ae995c5193dc91ccefbc617dbe1127b494f2cf972f",
    ),
    (
        "tests/test_paper_model_validation.py",
        "54c9819cb45b972e079379e7cc53d41315b2672be5c431bab2e564016180ded0",
    ),
    (
        "tests/test_feed_arbitration.py",
        "1d49f0e3b22d3b2cdfbd81eb0a79ad9c76a55f1b6204489106b86c0de4f9da13",
    ),
    (
        "tests/test_feed_backup.py",
        "06bbab8bef3bbab03b17427c1cc5b5f5d6375aa7406c556f12015e59a85227d5",
    ),
    (
        "tests/test_feed_cli.py",
        "6dd520a2b6e97b436b4e889f333525c1fa2afdc6eb5b44f264ce99ed8ee8199a",
    ),
    (
        "tests/test_feed_discovery.py",
        "733f7bba464c12d1441f03aedddc60acc801970eb876c1df2978b8dfa7ab8933",
    ),
    (
        "tests/test_feed_identity.py",
        "43bf3cfed8f067dff325893d36d32b6a9270fa6ccf1e85acf1803f203b29b5c6",
    ),
    (
        "tests/test_feed_inputs.py",
        "44b37d3db9c474a3bf96e3de168f5b07062fdd3ec30acc778c7aadf7c84d5b35",
    ),
    (
        "tests/test_feed_migrations.py",
        "bfa4dbdf1aa3c46e1e4e121017c80de1274b6a17a9d72ffb93410b4305f59cb6",
    ),
    (
        "tests/test_feed_process.py",
        "ed2698f4b841d5eba798334510d8aedd11777e451625bd9d0870013d297c92ad",
    ),
    (
        "tests/test_feed_registration.py",
        "b9f5c820509bd5c59715bc7bd2ce208290dc5a414097632f09ca399ccc4fedce",
    ),
    (
        "tests/test_manual_corrections.py",
        SHARED_MATERIALS["tests/test_manual_corrections.py"],
    ),
    (
        "tests/test_paper_acquisitions.py",
        "cc2dcd9439f7e794be3f8fa6c066ccc3031e52b6fc5774be28d44a876bd1b947",
    ),
    (
        "tests/test_paper_backup.py",
        "81e33733173ecbfb1079ad0500ddd23b0a7270f8163b1b961068f94b27444d34",
    ),
    (
        "tests/test_paper_cli.py",
        "6eb989039dcae1f5c6b9ad4b05ded2441345284e168b0d54a42be4ee904e9c02",
    ),
    (
        "tests/test_paper_identity.py",
        "147662dfef881fa9e52de22ed1bbd9630eb44081209ae62b92a4669200553a9d",
    ),
    (
        "tests/test_paper_inputs.py",
        "b35607c5dc3c90800f74c5fe06a8a88d890582e061302c55ea56187f2843ba90",
    ),
    ("tests/test_paper_mapping.py", SHARED_MATERIALS["tests/test_paper_mapping.py"]),
    (
        "tests/test_paper_mapping_failures.py",
        "aef21f904a71aa28ae184831d4837a9b773beedebcef22d1829edb151e5350cb",
    ),
    (
        "tests/test_paper_mapping_process.py",
        "bcf01887ea3f515d81de74d7fb71230a4ea215172292705ea3cfee403386bce0",
    ),
    (
        "tests/test_paper_migrations.py",
        "e563b35c5f427a8ad3c4b751ef1655e96087e8e51fc0154d3b7659c199070bc9",
    ),
    (
        "tests/test_paper_process.py",
        "809edbca563ae13aa696e47ebfa4290e20d1c5f9ad873da6f146a795af8f8296",
    ),
    (
        "tests/test_paper_recovery_combined.py",
        "000d387463e9382075a2a691f79c9de5d482d48b90303553e2eaf8494eadfe81",
    ),
    (
        "tests/test_paper_recovery_damage.py",
        "62d44f1e8cad8f4c2434a38b9881e6a5058a29454f60f4c8a757d67b7c7fbf7b",
    ),
    (
        "tests/test_paper_recovery_integrity.py",
        "d7d7f72c41a3f2742bc8ce633c32a6fd0b6a98ff8dd8066f00fe891ad6434f43",
    ),
    (
        "tests/test_paper_reparse.py",
        "bfb1efebe804aa5ba60e3a3f4c8f4f6c2436211e6111aa286432429f9c35802b",
    ),
    ("tests/test_paper_service.py", SHARED_MATERIALS["tests/test_paper_service.py"]),
    (
        "tests/test_source_arbitration.py",
        "aaa011e4cfaa2a6be186b26603435c16450104999b543658d7f98b0b5ae2042c",
    ),
    (
        "tests/test_source_backup.py",
        "05d2756b4707d7553da72b45f779a5210c8c312b464885e2b14b0ecd8401a80a",
    ),
    (
        "tests/test_source_cli.py",
        "4004c50f7cacfbcd5e235ba919107dd7fe131f3fb559e617aa1f57ae7bd5fed0",
    ),
    (
        "tests/test_source_migrations.py",
        "b55a61641ccd82d09861b82d7aaa94ebfd9eea2a403aa544ece700e3c815283f",
    ),
    (
        "tests/test_source_process.py",
        "8cd0f154bfb8a58c5a97e242de16d64f6e215f7609b776b4515c1ffc248d0eaa",
    ),
    (
        "tests/test_version_relation_backup.py",
        "44e8e92ab367d0e664b447ff70eb148d31cda05583af36c648183aaa105551ea",
    ),
    (
        "tests/test_version_relation_cli.py",
        "ee19784194e8a53de8947b1597db78e76a1e7e39a601a7ff112df2c609d3d1cc",
    ),
    (
        "tests/test_version_relation_inputs.py",
        "652773ff65e3f1b179f8bfe1f783b56f129b7134296bc310ebd2e4ad7d52ed45",
    ),
    (
        "tests/test_version_relation_materials.py",
        "f478bb01ae7fb82a79181191a926b947733760827f61102b9f9729e838183075",
    ),
    (
        "tests/test_version_relation_migrations.py",
        "bbde4bb1cfb06ceda609c26d78e70ed5c4b9048ecb052148ac0c7db04a10b698",
    ),
    (
        "tests/test_version_relation_process.py",
        "0f417041d677b332742b42725093297387d701fef2dbde49d2031498e4a3389d",
    ),
    (
        "tests/test_version_relations.py",
        SHARED_MATERIALS["tests/test_version_relations.py"],
    ),
    (
        "tests/test_a6_acceptance.py",
        "1b6ae4f260ac651041d77758de51663501e72b38a4a3860312810b4873170fd2",
    ),
    (
        "tests/test_a6_entry.py",
        "4cb38e8b25d028d3a7bdba4fb7d95a67b345f8255d59d0be4ef1422fc624bcd6",
    ),
    (
        "tests/test_a6_formats.py",
        "d0621a3623a4f0a6b0ea419d1e5376a660c1ef7bb8c1a6c4607aff7d896be278",
    ),
    (
        "tests/test_a6_integrity.py",
        "353e59b22a320811f1fd851d5db94ce4ca074f36603bd8deee6469c8ddbda646",
    ),
    (
        "tests/test_a6_status.py",
        "78dbdff2595a9039ad1569e2065d32276112e1568a069eb7763a6113cd2e26ea",
    ),
    (
        "tests/test_a6_test_receipt.py",
        "368ca0e9e970151070f4859d14254bd8846cddcb2a5890c6ed580203070b5010",
    ),
)
REQUIRED_SOURCE_MODULES = (
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
    ),
    (
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/a6_acceptance.py", SHARED_MATERIALS["scripts/a6_acceptance.py"]),
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
        "src/paper_radar/backup/manifest.py",
        SHARED_MATERIALS["src/paper_radar/backup/manifest.py"],
    ),
    (
        "src/paper_radar/backup/service.py",
        SHARED_MATERIALS["src/paper_radar/backup/service.py"],
    ),
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    (
        "src/paper_radar/papers/__init__.py",
        SHARED_MATERIALS["src/paper_radar/papers/__init__.py"],
    ),
    (
        "src/paper_radar/papers/cli.py",
        SHARED_MATERIALS["src/paper_radar/papers/cli.py"],
    ),
    (
        "src/paper_radar/papers/doi.py",
        SHARED_MATERIALS["src/paper_radar/papers/doi.py"],
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
        "src/paper_radar/papers/feed.py",
        SHARED_MATERIALS["src/paper_radar/papers/feed.py"],
    ),
    (
        "src/paper_radar/papers/feed_queries.py",
        SHARED_MATERIALS["src/paper_radar/papers/feed_queries.py"],
    ),
    (
        "src/paper_radar/papers/feed_repository.py",
        SHARED_MATERIALS["src/paper_radar/papers/feed_repository.py"],
    ),
    (
        "src/paper_radar/papers/manual.py",
        SHARED_MATERIALS["src/paper_radar/papers/manual.py"],
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
        "src/paper_radar/papers/relation_repository.py",
        SHARED_MATERIALS["src/paper_radar/papers/relation_repository.py"],
    ),
    (
        "src/paper_radar/papers/relations.py",
        SHARED_MATERIALS["src/paper_radar/papers/relations.py"],
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
        "src/paper_radar/papers/service.py",
        SHARED_MATERIALS["src/paper_radar/papers/service.py"],
    ),
    (
        "src/paper_radar/papers/tables.py",
        SHARED_MATERIALS["src/paper_radar/papers/tables.py"],
    ),
    (
        "src/paper_radar/papers/text.py",
        SHARED_MATERIALS["src/paper_radar/papers/text.py"],
    ),
    (
        "src/paper_radar/papers/text_rules.py",
        SHARED_MATERIALS["src/paper_radar/papers/text_rules.py"],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a601_paper_facts.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a601_paper_facts.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a602_feed_discovery.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a602_feed_discovery.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a603_source_arbitration.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a603_source_arbitration.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a604_version_relations.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a604_version_relations.py"
        ],
    ),
    ("tests/a2_full_support.py", SHARED_MATERIALS["tests/a2_full_support.py"]),
    (
        "tests/a3_acceptance_support.py",
        SHARED_MATERIALS["tests/a3_acceptance_support.py"],
    ),
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
    ("tests/backup_support.py", SHARED_MATERIALS["tests/backup_support.py"]),
    (
        "tests/config_projection_support.py",
        SHARED_MATERIALS["tests/config_projection_support.py"],
    ),
    ("tests/config_test_support.py", SHARED_MATERIALS["tests/config_test_support.py"]),
    (
        "tests/feed_process/sitecustomize.py",
        "80e11e0116eadc6001357892a5f65ec24d02312a003bd0db6b883f50c3ebb9a8",
    ),
    ("tests/feed_support.py", SHARED_MATERIALS["tests/feed_support.py"]),
    (
        "tests/paper_mapping_process/sitecustomize.py",
        "08b9ab3c5237c0a7e8053f25f0efabc2264d6703e1600b76c7b2b4ccfad0c4b1",
    ),
    (
        "tests/paper_process/sitecustomize.py",
        "81aa5b1e5e4a6c04d3488da83dcd506b2fbe5abc5ed352953b341b56490642ac",
    ),
    (
        "tests/paper_recovery_reader.py",
        SHARED_MATERIALS["tests/paper_recovery_reader.py"],
    ),
    (
        "tests/paper_recovery_support.py",
        SHARED_MATERIALS["tests/paper_recovery_support.py"],
    ),
    (
        "tests/source_process/sitecustomize.py",
        "5df0b49f2b61cb5cb186f08fa7af0077398f8a0ae6f2c06729629144e09fca85",
    ),
    (
        "tests/version_relation_process/sitecustomize.py",
        "daeb0ed1982b55a08a7c8739bd1383732086958b3765f1e15d74d1a6696d5e3e",
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
        "tests/fixtures/paper_facts_v1.json",
        "0e88876d19ceae6df0654d9c3f2699106ffb11845b24399b1b50f6686e19d425",
    ),
    (
        "tests/fixtures/a6_capabilities.json",
        "1b0380bbd31ece374445f1dd309868cf8b1f315c8031f5fe54f71d9eb9b4bb34",
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = (
    "scripts/a1_scope.py",
    "scripts/a2_full_scope.py",
    "scripts/a3_scope.py",
    "scripts/a5_scope.py",
)
