"""#47 四阶段输入的固定验收范围;预期只在开发时审查登记。"""

SCOPE = "a5_stage_input_fingerprints"
ISSUE = 47
PARENT_ISSUE = 47
FORMAT_VERSION = 1
SUFFIX = ".a5.json"
MIGRATION_REVISION = "a1001_fixture_audit"
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
    "tests/test_stage_input_dependencies.py": 14,
    "tests/test_stage_input_extraction.py": 38,
    "tests/test_stage_input_extraction_reuse.py": 62,
    "tests/test_stage_input_recovery.py": 1,
    "tests/test_stage_input_replay.py": 33,
    "tests/test_stage_input_reuse.py": 63,
    "tests/test_stage_input_value.py": 27,
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
        "5216b1cd3c5b87a612f6e6a73cd6eb0c76199b6e6fb53ae02ef1150f98728f83",
    ),
    (
        "tests/test_stage_input_extraction.py",
        "189658296a4cf4e4e0adbb6ba1beb6787f76e1985d90e87ce7bb4fc33c1a49ca",
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
        "87b904272f6129638ec481c8ff2cdad20fa754de0cb03ecd2e5eb07d3006c27f",
    ),
    (
        "tests/test_stage_input_reuse.py",
        "45ccc5f0e016102a451f3b4cdab1fa4e7e31d175e24d59279b156af41130d40e",
    ),
    (
        "tests/test_stage_input_value.py",
        "9c03009b6f9db05ed58819adf9a8631648fb5d0bd4c5547c7ef77d9340c38296",
    ),
    (
        "tests/test_stage_inputs.py",
        "af8542793fc4cc99cb50888f6ddbd4a7f8ba0c7db9756b5932d746dd95a5e64e",
    ),
    (
        "tests/test_a5_acceptance.py",
        "9d3fcede88c46f9c61081a1afe230b72f7d64f6c5d816ff64fb71c33c828c2bf",
    ),
    (
        "tests/test_a5_entry.py",
        "0b4cde834b9fee665da07f4c00f6403584749c955bf23b61d8c6d70e632fe8a6",
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
        "d2dc724da98760240b6fa95e09619b2ca435e506c68a221976ae8c3ffba382da",
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
        "ed5517bec34993540c276c6136b7f30e685559f84a0e9dfd9c9fced3769a95d3",
    ),
    (
        "scripts/a1_scope.py",
        "245cf6e6bd9d1dafe3f747561d2518d32583e6154dc4876ff1cc9a5c78152251",
    ),
    (
        "scripts/a2_full_scope.py",
        "44383d7a39da7e1601a0a0f876c212a68e04b1e5df936bbaf9f573d9cd597f81",
    ),
    (
        "scripts/a3_scope.py",
        "8efe0301841c50ae5e0708d16d4ebba613eee56e988636b66e764e72e5058cb9",
    ),
    (
        "scripts/a4_scope.py",
        "f88eb0fb9a301a3ed13788600ed740f840645b25c0844f8e74d52f3b537011dd",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "ea761e76debed029efb9b37022c2d5dac78fccd32d31184015696618c5a9a204",
    ),
    (
        "scripts/a2_test_receipt.py",
        "38b0fcea6a0028c3652dfc272829f5ac76c201430fcd2d4d187c629db85032e5",
    ),
    (
        "scripts/offline_evidence.py",
        "3c53fd4e272ee346da23b72cd977180b78aeaa55a027064a97f5540ea24d9a28",
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
        "scripts/check-offline",
        "41a205087015281e5a8a921f20815f0828ef8457c57445d40f95be2bdb6d99d8",
    ),
    (
        "tests/a5_acceptance_support.py",
        "528ab9bd6e1a71767083eb514378e028420691d0c61a81237cab85163b2ab1f5",
    ),
    (
        "tests/a4_acceptance_support.py",
        "3e7457b20e193b1076b67c3d8394dcb0b9eebb60fcdc58d3abe44be4d50740cf",
    ),
    (
        "tests/a3_acceptance_support.py",
        "d89e4dff6834d19562ffd9a3a5fde14c353962ee67a8c1df21113c75979b2545",
    ),
    (
        "tests/a2_full_support.py",
        "a15976749dc2ae52448d81ea794c2be1c2e0f53d4e2a09de20f9a9790c16dc38",
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
