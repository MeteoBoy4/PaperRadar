"""#75 固定 A6 验收范围;运行时不能刷新预期。"""

SCOPE = "a6_paper_facts"
# ISSUE 是最后验收子票;PARENT_ISSUE 是业务规格。
ISSUE = 75
PARENT_ISSUE = 67
FORMAT_VERSION = 1
SUFFIX = ".a6.json"
MIGRATION_REVISION = "a604_version_relations"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "paper_facts": 1,
    "doi_rules": 1,
    "text_norm": 1,
    "feed_item_fingerprint": 1,
    "reason_catalog": 1,
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
        "62190a34deadcb9f688b418bb1ef8b025975446523e7fdf45854c9d3eacc9c4c",
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
        "ddd5b955b9654de8945518a2d0e4229544104bca3f3d2f79fa16f601c475a77a",
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
    (
        "tests/test_paper_mapping.py",
        "8cf3de3591cbc9b2a19cccc8ac93ea9a16909e44121a32f231838b045f956ea0",
    ),
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
        "5948f5c40b9b0eabb2cb53fdb717bb8a5611cb49ff782cc6cabda1cd6ca1ae74",
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
    (
        "tests/test_paper_service.py",
        "b0517a8a0058e544258a2f1b130ec3f1d05fcee8b495b8ea35b7409bc8efc6c2",
    ),
    (
        "tests/test_source_arbitration.py",
        "aaa011e4cfaa2a6be186b26603435c16450104999b543658d7f98b0b5ae2042c",
    ),
    (
        "tests/test_source_backup.py",
        "bcbeaa5ceb6b6587c3316172111abb205a814f500811dcfb8ad7fec5a03239c0",
    ),
    (
        "tests/test_source_cli.py",
        "4004c50f7cacfbcd5e235ba919107dd7fe131f3fb559e617aa1f57ae7bd5fed0",
    ),
    (
        "tests/test_source_migrations.py",
        "94ee389248cde749ea6af899a28fdf8e3f78ecd5f27d44d8c527d3f5731ee40f",
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
        "629b271c9f17590c5851f6e5c8b772301e17bc57ddbb35256af6e9bd2b1500f2",
    ),
    (
        "tests/test_version_relation_process.py",
        "0f417041d677b332742b42725093297387d701fef2dbde49d2031498e4a3389d",
    ),
    (
        "tests/test_version_relations.py",
        "069aa10cc4cb66405e0f093e00b0503bda09200563113ebfaedbf7230805c74e",
    ),
    (
        "tests/test_a6_acceptance.py",
        "eb26aee63e8a83d9a4dd07e14c019d0ef2a18980dfebea4b31309604babccc9e",
    ),
    (
        "tests/test_a6_entry.py",
        "d455379e952b6eb8f64243e8c58012298b946a5d9f08e1408c24fcc46bcbc130",
    ),
    (
        "tests/test_a6_formats.py",
        "d0621a3623a4f0a6b0ea419d1e5376a660c1ef7bb8c1a6c4607aff7d896be278",
    ),
    (
        "tests/test_a6_integrity.py",
        "8f43fa67710333c2654d873aad8f864ed8d8df1e9cab0a5c5b1be04afdbd1fac",
    ),
    (
        "tests/test_a6_status.py",
        "3e1d1b85eb6073c0d1ce51e8cfb163d58942e3a00707ad2b98b627135ca06089",
    ),
    (
        "tests/test_a6_test_receipt.py",
        "368ca0e9e970151070f4859d14254bd8846cddcb2a5890c6ed580203070b5010",
    ),
)
REQUIRED_SOURCE_MODULES = (
    (
        "scripts/a1_scope.py",
        "e71257263bed5859e4277c8b0ff399c4986c440e8212c8d1a636c559fcc7d428",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "2eb2aeec023f8d5b5c13dbe85ba69d6a1c04955e37f62c3a90c15a4724801448",
    ),
    (
        "scripts/a2_full_scope.py",
        "d0cc473a2ec4766e4a3a0b0fa670a741328758a9082ee5ebd7ffc3abacffae9a",
    ),
    (
        "scripts/a2_test_receipt.py",
        "9a5c2eda301e3c9975aac7ab0c07f9884b99c5eea2f45250a4dc7145340b9c2e",
    ),
    (
        "scripts/a3_scope.py",
        "dfe9e9828bbb7323abd855183b0a78d800fe71b2eb4e5f895652ffd254d22843",
    ),
    (
        "scripts/a5_scope.py",
        "13305aab6874eddf456d424653897cd0cac056e4011d0fcff0e904b6437db8c8",
    ),
    (
        "scripts/a6_acceptance.py",
        "21f71e65263d86bb642bee0bd315ab7fa31ac71f427d5f91af55b8003374f861",
    ),
    (
        "scripts/check-offline",
        "24db737f730e4ca445e53ca66a547091ee6bb1a865ced53440f245e15b3bfc6a",
    ),
    (
        "scripts/verification_checks.py",
        "f93113dcaa037ed7b5992133320a58d36dcf438c1d82969c94611c54649788bc",
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
        "a4d08449eb65ac7e2c39d2fe972cccf28ec8af13dcf5d34795ac1c088212ae0a",
    ),
    (
        "scripts/verification_status.py",
        "097fb2c4ae1f4aba366def88afbcbfe0dd6ed4449beb0c431c89e06d62d15fdc",
    ),
    (
        "src/paper_radar/backup/manifest.py",
        "924c659e655ba73ae95108db02a4fc343c2f4d50650be5d3972637a0b3e9cca5",
    ),
    (
        "src/paper_radar/backup/service.py",
        "177ad9459468b9e14c94fad0f9bfe1b0183c7be10d2f0cc04b1285ee5f9fc03b",
    ),
    (
        "src/paper_radar/cli.py",
        "c444c4e16c98e8615c2b5268f0f4288144c7aff3a3890f072bf503e66a55a524",
    ),
    (
        "src/paper_radar/papers/__init__.py",
        "51d6c843c32cefa8782f73cd6238a3cdab8d85faf5350298bf6f4f1bd07a2612",
    ),
    (
        "src/paper_radar/papers/cli.py",
        "9491add71334a8941b11f06b113ece2c68315bc76802f63cee9aff12a8bf54ec",
    ),
    (
        "src/paper_radar/papers/doi.py",
        "c96c878e77717d46ecca7b191e82d1766433bbc85e808365959dbf1bd1faf3b8",
    ),
    (
        "src/paper_radar/papers/errors.py",
        "90764831f8e6c8040350b321110a4bbde46873cf8f7ed8c744bcf390be9d86e5",
    ),
    (
        "src/paper_radar/papers/fact_reads.py",
        "ec29b372e3ce39f17593541158b8b7d51aed8bdbb94927af6120e647977f2a35",
    ),
    (
        "src/paper_radar/papers/feed.py",
        "6212e6b0af9d1d41cf21dc59c85962adcf63402c1d5bb4d7edd9081f50a9722b",
    ),
    (
        "src/paper_radar/papers/feed_queries.py",
        "d6f600faa3745592351d3956e03be9f99064dd0310dcf4920b09ce35e81e4da4",
    ),
    (
        "src/paper_radar/papers/feed_repository.py",
        "ba9773a5324209689fc4bcff73f0d39d37c0f42e3700a32daef09a03ebcc3fac",
    ),
    (
        "src/paper_radar/papers/manual.py",
        "0e13d39d5f176580e448833ea562bd057a5d818dfe601d92bad366dfc14d60db",
    ),
    (
        "src/paper_radar/papers/mapping.py",
        "aa588937228e31d2c8ffd58d565d4f13e08a4e619a89d598614e0284e075ee1e",
    ),
    (
        "src/paper_radar/papers/mapping_models.py",
        "c1770760154967b1e0d4c7090acb79d61ba4a7df379f16af459f3ee7393e5bde",
    ),
    (
        "src/paper_radar/papers/models.py",
        "a99c41a2ddfebfcdfb3437399edd6ce066100708bdd6f5d38ffaace92ccacc69",
    ),
    (
        "src/paper_radar/papers/queries.py",
        "4b0142b1df589c97325ce97851544dc8226a0c2b8a41c9c4e027c19796d91042",
    ),
    (
        "src/paper_radar/papers/read_checks.py",
        "1bbf3ac2e4e1fe12109e11cdbd1e8f37fef4dfd252b5ced1c8fa912b47707d5c",
    ),
    (
        "src/paper_radar/papers/relation_repository.py",
        "45b1e3f9da30a30593d764c2015e648c511efc39ca0f83cc40834057abcae4e3",
    ),
    (
        "src/paper_radar/papers/relations.py",
        "9bd81c1f3371c20311a3906de6748f15c52c3cbbfea2ad3a15c28fd521c77574",
    ),
    (
        "src/paper_radar/papers/repository.py",
        "7ec38d5bf40736f253a6eac244c43773a6075d64fc11dbc55680f6e359663188",
    ),
    (
        "src/paper_radar/papers/rules.py",
        "4790187ffed23c63e8ccaa3a8d51fa0a8edd6b59c79fd39dca34c83803e9d86b",
    ),
    (
        "src/paper_radar/papers/selection_repository.py",
        "27579c3eb0bedbbe90f7da5c5326904b6058023cf3fe1a7576a71afde4b9c7f1",
    ),
    (
        "src/paper_radar/papers/service.py",
        "4d18aa053e13bde442d26dbd404fa4c1584d4cb88b25f874c85321a383b00a45",
    ),
    (
        "src/paper_radar/papers/tables.py",
        "b190ff9f7f1d0ded4bfa559246cd07e5fb8b47290e3c7a76a344c886a6311f21",
    ),
    (
        "src/paper_radar/papers/text.py",
        "e00bbfac6a728ca67f1c465db37630ff924f5152c4a518ef75840ca38cc54897",
    ),
    (
        "src/paper_radar/papers/text_rules.py",
        "9cebd0175cc0730bd65940339e8dd8d01402c5cbc635afb29641b2aced635e6f",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a601_paper_facts.py",
        "c5fcf3d84b03619f79c6720fd5aad83df7af6ac884c00d1ed5a161b286ad056d",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a602_feed_discovery.py",
        "94cee1dfaa7879a3ed54633a45c7fcfa3da6fc78947075c62a2c049ac4a5d513",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a603_source_arbitration.py",
        "e7f62ecd51ac4b4dadb18bd8e8fa55f60e293e05dd88e3bfeeb0c42c4740a9ab",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a604_version_relations.py",
        "223a7e931d9350f8c42eaaa64ce3204fe9a7ae612c4415e7af326e3041064b9c",
    ),
    (
        "tests/a2_full_support.py",
        "a15976749dc2ae52448d81ea794c2be1c2e0f53d4e2a09de20f9a9790c16dc38",
    ),
    (
        "tests/a3_acceptance_support.py",
        "d89e4dff6834d19562ffd9a3a5fde14c353962ee67a8c1df21113c75979b2545",
    ),
    (
        "tests/a4_acceptance_support.py",
        "3e7457b20e193b1076b67c3d8394dcb0b9eebb60fcdc58d3abe44be4d50740cf",
    ),
    (
        "tests/a5_acceptance_support.py",
        "528ab9bd6e1a71767083eb514378e028420691d0c61a81237cab85163b2ab1f5",
    ),
    (
        "tests/a6_acceptance_support.py",
        "b6642636b0e57bb76e4bcbbe94a540e7239075ab5d6872a01e04ad046a4f28a9",
    ),
    (
        "tests/backup_support.py",
        "f1ee3e3febb10bcf68212af621c79d0d25951fa1464cd11e23d2afe139e8cc37",
    ),
    (
        "tests/config_projection_support.py",
        "1a3aa9a7ce2535a9a52c3fde9dc18cde964d1de8b89654e3d50e566aae79ef2a",
    ),
    (
        "tests/config_test_support.py",
        "1bdd4ec7d1c3a3c2274455cfe184ea5ee7d58971d65adc1ccd532a55c295e840",
    ),
    (
        "tests/feed_process/sitecustomize.py",
        "80e11e0116eadc6001357892a5f65ec24d02312a003bd0db6b883f50c3ebb9a8",
    ),
    (
        "tests/feed_support.py",
        "db26ee02a0164e43f116a5d73f5acdd58946f897ac4c2be063722437dd5814a8",
    ),
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
        "5d88105fbf62502c5a36453a4e1f07b21ffe75a29f1207b4c138ab42ee690ec7",
    ),
    (
        "tests/paper_recovery_support.py",
        "1ed06b37d511b6b0ca319067737b2d0b629bb7e7efc542a34cccb579d77066ad",
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
        "tests/fixtures/paper_facts_v1.json",
        "493d8c4b66894f81a969ae3fb31d81354132c66b844fda8425d9762e3b3c6016",
    ),
    (
        "tests/fixtures/a6_capabilities.json",
        "c3171252180a887a7258c7aa2f51ff0da53a5d1d4b9769222495d3c51ffe500f",
    ),
)
