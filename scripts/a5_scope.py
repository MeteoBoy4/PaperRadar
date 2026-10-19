"""#47 四阶段输入的固定验收范围;预期只在开发时审查登记。"""

SCOPE = "a5_stage_input_fingerprints"
ISSUE = 47
PARENT_ISSUE = 47
FORMAT_VERSION = 1
SUFFIX = ".a5.json"
MIGRATION_REVISION = "a405_pi_cleanup_execution"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML", "pydantic")
FORMAT_VERSIONS = {
    "stage_inputs": {"boundary": 1, "value": 1, "reuse": 1, "extraction": 1},
    "stage_projections": {"boundary": 1, "value": 1, "reuse": 1, "extraction": 1},
}
CAPABILITIES = (
    "boundary",
    "value",
    "reuse",
    "extraction",
    "payload_replay",
    "comparison",
    "isolated_restore_replay",
)
NOT_ASSESSED = (
    "read_fingerprints",
    "suggestion_fingerprints",
    "report_fingerprints",
    "paper_fact_mapping",
    "task_budget",
    "rpc_compatibility",
    "live_source_audit",
    "stage_a",
    "live",
    "automatic_fulltext_reading",
    "calibration_workflow",
    "eligibility",
    "pi_execution",
    "docling_execution",
    "nas_restore",
)
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_stage_input_architecture.py": 1,
    "tests/test_stage_input_common_contract.py": 125,
    "tests/test_stage_input_comparison.py": 28,
    "tests/test_stage_input_dependencies.py": 9,
    "tests/test_stage_input_extraction.py": 38,
    "tests/test_stage_input_extraction_reuse.py": 62,
    "tests/test_stage_input_recovery.py": 1,
    "tests/test_stage_input_replay.py": 29,
    "tests/test_stage_input_reuse.py": 57,
    "tests/test_stage_input_value.py": 26,
    "tests/test_stage_inputs.py": 20,
    "tests/test_a5_acceptance.py": 106,
    "tests/test_a5_entry.py": 5,
    "tests/test_a5_test_receipt.py": 6,
}
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_stage_input_architecture.py",
        "98c5bd8ed397db713c38ce3f634d51ec1454737be21b3c4c0103abbf3ed37bbe",
    ),
    (
        "tests/test_stage_input_common_contract.py",
        "7ad55aa965256560a7950aec8d2ceb39b53034c75d3258ecb20a9d7adb228045",
    ),
    (
        "tests/test_stage_input_comparison.py",
        "8c6a06ed6ba65bcd2a360fc4fae0a2cfd183bd257b09bd973949bd2f4da0fe9f",
    ),
    (
        "tests/test_stage_input_dependencies.py",
        "b8d6079541d7a4038c2af7dcfbe14693ea02751d9992690a62cdb509586cb534",
    ),
    (
        "tests/test_stage_input_extraction.py",
        "2b310243fd84b6fe84da748ce11e22bc90556b12add3287182444d4c9269b8c1",
    ),
    (
        "tests/test_stage_input_extraction_reuse.py",
        "cc7253af1eac49fc9a18a92a86edbbd2d369f614e5f71ec2a9cb7cc899d5ec48",
    ),
    (
        "tests/test_stage_input_recovery.py",
        "956c050f4ba0c652acac4da676fe3d6fd386d1a28592801106ff0f9965ec354c",
    ),
    (
        "tests/test_stage_input_replay.py",
        "829f0498efbc585086c8bb83c3640947156862c332516052039b3e46364862f4",
    ),
    (
        "tests/test_stage_input_reuse.py",
        "2a5ad28f6ea0c08782c66c8f747efda70c86fb27bd87df2e2ddc35f52ff659c7",
    ),
    (
        "tests/test_stage_input_value.py",
        "a963bbc624122fe60e61fcf8132d4bf58812c729fd122aacc235ea1b2b55ecba",
    ),
    (
        "tests/test_stage_inputs.py",
        "af8542793fc4cc99cb50888f6ddbd4a7f8ba0c7db9756b5932d746dd95a5e64e",
    ),
    (
        "tests/test_a5_acceptance.py",
        "1ab32911b43ca927fcb6cd68f314bcae402da6348bc48fe16118555d8bfdcf1a",
    ),
    (
        "tests/test_a5_entry.py",
        "32cf88097078fa30c4ea64697437768e0e51ef7571bfb0f2bb47d234eb79baf0",
    ),
    (
        "tests/test_a5_test_receipt.py",
        "d7259f3952f9e878bb0835be5727ee43d1c203b86d5fd5385125e274258aa097",
    ),
)
REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/stage_inputs/__init__.py",
        "d3a77ae4330d0821ddf84ed6b9f02830292f5b3ba678c69faa48e2bfc7611a87",
    ),
    (
        "src/paper_radar/stage_inputs/service.py",
        "b8f27484e4fd8f09098f07ddff16d0d59f08d0eb671b38f184d9b049b9d8fd3f",
    ),
    (
        "src/paper_radar/config/__init__.py",
        "e8e1844c436c97d48bfca7341cfc855502917767bc8da9e6924c3c12d0b9e4f1",
    ),
    (
        "src/paper_radar/screening/__init__.py",
        "930c9c05dcd3067898c50b4e3250a816e89c0408504e0b77936a27f97a702b2c",
    ),
    (
        "scripts/a5_acceptance.py",
        "d7bcc54ead6d299f1a8fac7b69a1a60e3ce24e822ff202271b34f5cf07164cce",
    ),
    (
        "scripts/a1_scope.py",
        "419e26fe9a858b18ac46dfaf8f008af074ee689a923ff447c57be0a6fad84131",
    ),
    (
        "scripts/a2_full_scope.py",
        "8e6c3848210d34da78240d81a37838953fe589810ca3a02ca1485aa2ea8302ca",
    ),
    (
        "scripts/a3_scope.py",
        "03e31b0bfd630a4107408f843d208ce21ac1e670f12cf0c10bd40153f5eacc66",
    ),
    (
        "scripts/a4_scope.py",
        "4acaab9fba86e37134cd4d5cce4feb1ba89524bfe0cb72eb151c4e4795b3e8e0",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "aad35128fe21a10e1fa949e358bbbea8f1fce171ff2e17fda35c3827eb794fee",
    ),
    (
        "scripts/a2_test_receipt.py",
        "b4577e17babf4f5d9d1fd64e77367e62b621441df46b602fdc58d8a8188f28a8",
    ),
    (
        "scripts/offline_evidence.py",
        "0c613ee51748db53ebba7a9c9c260faa74391be0f3043646ee09867b420f6362",
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
        "scripts/check-offline",
        "b08e2576e8968ea872a3dc44be4562adfb04cb7f99abe372a75469bbe6899cac",
    ),
    (
        "tests/a5_acceptance_support.py",
        "068c60af9011899756f3cb47b861ba1e999a571f75a531d349efb86601aac537",
    ),
    (
        "tests/a4_acceptance_support.py",
        "a32c09d03b6d5523375c27ba5c51c798c48a04bbadb04026583f587e253eff54",
    ),
    (
        "tests/a3_acceptance_support.py",
        "86868063437584e26e02a90f64d4f4c0dc73d5a21292bd501e9bba2af7065f70",
    ),
    (
        "tests/a2_full_support.py",
        "d6c69fe997d026288b4793f4c6fe2225ce9f4e019114463bcb0ef03da7527469",
    ),
    (
        "tests/stage_input_process.py",
        "aacb4a33f296a7caedcc70555196d8fd45cea9df3a13447006da3379ddf3ce9d",
    ),
    (
        "tests/stage_input_recovery_support.py",
        "c6865b96ba4342634e262e6092b5d58f14993b61aaa4a0a4771007a1a130543b",
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
        "tests/backup_support.py",
        "f1ee3e3febb10bcf68212af621c79d0d25951fa1464cd11e23d2afe139e8cc37",
    ),
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
    (
        "tests/fixtures/stage_inputs/boundary-v1.json",
        "e27f19cc566e80158680aecfcf2b3bd41a3cb07201ef6c3a4cec66b4ba11abb2",
    ),
    (
        "tests/fixtures/stage_inputs/boundary-v1.sha256",
        "cb043f6bd4d0f6074799b305ab619a9a64e94a9b4300dd595e7eaa5e306f842d",
    ),
    (
        "tests/fixtures/stage_inputs/value-v1.json",
        "c8d68282f6366900ebadc342034b6ac9272bccbecd7a766e50bd480210533db0",
    ),
    (
        "tests/fixtures/stage_inputs/value-v1.sha256",
        "010d9b9f3e402cb44b6b8f8c88fe7c4342c4d9f5a1a03726c4a7a0c4329c56d8",
    ),
    (
        "tests/fixtures/stage_inputs/extraction-v1.json",
        "6ca4e413c842ded79f4d244ebf278fecc62009b3599aa0cd5e7c39084566b0df",
    ),
    (
        "tests/fixtures/stage_inputs/extraction-v1.sha256",
        "e7e73431779f0cc4f6d6e91ba2da0727a996a97133021c4a746f51518e757fa8",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-structured-v1.json",
        "3c9deffa8929d61e6cb2e96582b0c7af6e3c78ec958630b8be83986684e370b4",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-structured-v1.sha256",
        "811e0ad5537fd2bb148dc1e657a27e1d1a5d3a9de5dc807e4b392ceb38fa464f",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-body-v1.json",
        "e2c035f114b5ae5ac7d598faea42f48dda0ac869809b1d3a25354f0bb1e978f6",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-body-v1.sha256",
        "a1650297ac275cb2b9bea91a45ebb5527eef603052e1af3b46fdaebca2096069",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-mixed-v1.json",
        "4b6c273cfefa6b83532120b7f4b8dc22e6dbf0e64ac63fa5c3f2a84872d82c62",
    ),
    (
        "tests/fixtures/stage_inputs/reuse-mixed-v1.sha256",
        "92e43eb0c584b1599b29f95b7733f7c11f0eccb9a42d0a281e3acf1ffaa3b4f9",
    ),
    (
        "tests/fixtures/stage_inputs/recovery-v1.json",
        "6bf8384d28ebb0ea8dc8f03a2677e8a56761796e099000dc9275928f3e52f355",
    ),
)
