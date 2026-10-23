"""A4 固定审查范围;预期在开发时逐项登记,运行期间只核对。"""

SCOPE = "a4_pi_supply_lifecycle"
ISSUE = 45
PARENT_ISSUE = 36
FORMAT_VERSION = 1
SUFFIX = ".a4.json"
MIGRATION_REVISION = "a701_screening_registration"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = (
    "alembic",
    "SQLAlchemy",
    "PyYAML",
    "pydantic",
    "typer",
    "httpx",
)
FORMAT_VERSIONS = {
    "supply_manifest": 1,
    "derived_lock": "derived-lock-v1",
    "tree": "tree-v1",
    "install_policy": "install-policy-v1",
    "cleanup_plan": 1,
    "retention_rule": "library-install-window-v1",
    "cleanup_tree": "tree-v1",
    "occupancy_rule": "allocated-inode-v1",
}
CAPABILITIES = (
    "prepare",
    "verify",
    "rebuild",
    "activate",
    "install_protection",
    "cleanup_plan",
    "cleanup_execute",
    "doctor",
    "export",
    "isolated_restore",
)
NOT_ASSESSED = (
    "live_install",
    "rpc_compatibility",
    "stage_a",
    "live_source_audit",
    "nas_restore",
    "automatic_fulltext_reading",
    "pi_execution",
    "stage_b",
)
REQUIRED_TEST_CASE_COUNTS = {
    "tests/test_pi_supply.py": 16,
    "tests/test_pi_supply_activation.py": 12,
    "tests/test_pi_supply_activation_cli.py": 7,
    "tests/test_pi_supply_activation_history.py": 7,
    "tests/test_pi_supply_boundaries.py": 24,
    "tests/test_pi_supply_cleanup.py": 9,
    "tests/test_pi_supply_cleanup_cli.py": 3,
    "tests/test_pi_supply_cleanup_execute.py": 32,
    "tests/test_pi_supply_cleanup_execute_history.py": 6,
    "tests/test_pi_supply_cleanup_history.py": 11,
    "tests/test_pi_supply_cleanup_unreadable.py": 1,
    "tests/test_pi_supply_cli.py": 13,
    "tests/test_pi_supply_export.py": 24,
    "tests/test_pi_supply_export_history.py": 1,
    "tests/test_pi_supply_history.py": 10,
    "tests/test_pi_supply_process.py": 3,
    "tests/test_pi_supply_protection.py": 16,
    "tests/test_pi_supply_rebuild.py": 20,
    "tests/test_pi_supply_rebuild_cli.py": 8,
    "tests/test_pi_supply_rebuild_history.py": 5,
    "tests/test_pi_supply_transport.py": 8,
    "tests/test_pi_supply_tree.py": 4,
    "tests/test_a4_acceptance.py": 84,
    "tests/test_a4_combination.py": 1,
    "tests/test_a4_test_receipt.py": 6,
    "tests/test_a4_entry.py": 5,
    "tests/test_a2_full_entry.py": 7,
    "tests/test_verification_run.py": 5,
    "tests/test_verification_compatibility.py": 9,
    "tests/test_verification_integrity.py": 18,
}
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_pi_supply.py",
        "f9bc6db8d606ae809bfdb259bb2f18d91488f5601f01eebe8bd4965a9429ef28",
    ),
    (
        "tests/test_pi_supply_activation.py",
        "05e8cbba1b7ff842e33a337ec7d0107ebf6b0e88410508bf8b21d076e6067f49",
    ),
    (
        "tests/test_pi_supply_activation_cli.py",
        "4bc0c9973104d11b838c438ebbb401d197fefcccb4c7b0d87cf46f974cc62762",
    ),
    (
        "tests/test_pi_supply_activation_history.py",
        "21a96d49aacf454389a2c94fe542287853534f57fae23dcf9f32d940c70722df",
    ),
    (
        "tests/test_pi_supply_boundaries.py",
        "e2cf8fb4c73fdb00364136352f63cf484b10eddeae2dac0cb5b343321786c1d0",
    ),
    (
        "tests/test_pi_supply_cleanup.py",
        "2920dcf0a746377d97d50df8474be58b25223c1524531c9558369155d7936c50",
    ),
    (
        "tests/test_pi_supply_cleanup_cli.py",
        "56df3ebfb87750da168dc5164412262b89bcb0bfae27891a1568eac70a69a6aa",
    ),
    (
        "tests/test_pi_supply_cleanup_execute.py",
        "7b4cdc43b843dd0843d88d532302af45117884e2765d7e7cb9e677050c2028ab",
    ),
    (
        "tests/test_pi_supply_cleanup_execute_history.py",
        "69932ed51b73925dffc9a5e9a09380b970631137ee3a863bb4848b50ded9e479",
    ),
    (
        "tests/test_pi_supply_cleanup_history.py",
        "aad1ae19fce7a18c3eb98a1c3243b628da16cf4a8b1c782a7cff4f620dba885a",
    ),
    (
        "tests/test_pi_supply_cleanup_unreadable.py",
        "c847c710f33262af89d8221171aad538a4258de9b5ad2f87ccdb71664465e980",
    ),
    (
        "tests/test_pi_supply_cli.py",
        "98c3221db57e475be21f9569a8fbee9710fea66693439420d68228719d1892db",
    ),
    (
        "tests/test_pi_supply_export.py",
        "93469f447f6f83cac935b26e493412aceb1e738729f0600997df1fafe1061941",
    ),
    (
        "tests/test_pi_supply_export_history.py",
        "80264e0b5284b61463e4577e8bae41a9b03271c34b7c8ce8aee9dbe3f93816bc",
    ),
    (
        "tests/test_pi_supply_history.py",
        "cb003a3b8ded2286cd1b05f5beeec6dc709d4e0e85d4c55815c9bf79de1ae835",
    ),
    (
        "tests/test_pi_supply_process.py",
        "494496cb8d1ecb009afa95f2ff83723dd4d9269d9b903662a3d079194a8e0078",
    ),
    (
        "tests/test_pi_supply_protection.py",
        "1af4c0f43138492d376de360a981b32482081790a081082ed8892de048a0b334",
    ),
    (
        "tests/test_pi_supply_rebuild.py",
        "c8c09a64df0a4cfa6d03c1703fe46f7bf84a84546b0ab1fe53d5ca1dc9e1678b",
    ),
    (
        "tests/test_pi_supply_rebuild_cli.py",
        "1208d3e09371b5dd5bd60543e1fd29dd2ac01725e2d68c6bb00e992cf42ddd0a",
    ),
    (
        "tests/test_pi_supply_rebuild_history.py",
        "5060385bcb39165e2945d1e9f905e3ebff2ff02466f2c9187b1f264ee8e826bc",
    ),
    (
        "tests/test_pi_supply_transport.py",
        "c7a82c896870f229fd895ab33672c95d70a08ebcdaba44c4f475e051d4ba12b5",
    ),
    (
        "tests/test_pi_supply_tree.py",
        "499e928386a7e4139a80f23535faa44402182c163cbc971b4ebe4b439c901977",
    ),
    (
        "tests/test_a4_acceptance.py",
        "dfa63392b634989b5398913cc2913034f084774a39ee03afcfdcbaaf281f4286",
    ),
    (
        "tests/test_a4_combination.py",
        "1b5ae28485dfdd7e3621ce0e2dca20cefdc06601c971c60b8bf0f40a8338617e",
    ),
    (
        "tests/test_a4_test_receipt.py",
        "f7322ef1cf207fcd55c34aedf3502aabdfddf0bb07f89d37421ed2a436398b1b",
    ),
    (
        "tests/test_a4_entry.py",
        "c6ee69a9a3f12fae2344a9d24d4149592d3aebf4f938fc152e58447b043ff9d3",
    ),
    (
        "tests/test_a2_full_entry.py",
        "c3d8f2459ce23d5bcbc62bc7db333119bf484c828ac5bf2e7dc43edea850e62f",
    ),
    (
        "tests/test_verification_run.py",
        "62d406f3648f821253e1426959706027bddc170874d4bb45a7f88a9944b7e4eb",
    ),
    (
        "tests/test_verification_compatibility.py",
        "7bdad246df8bb8b05d7f8e1c63b0530ee63b554cbdfe075a240cd8f08389542d",
    ),
    (
        "tests/test_verification_integrity.py",
        "3839644318334ef253835dc5467953b102513f2cc7319b58afdd8586a01d1932",
    ),
)
REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/pi_supply/__init__.py",
        "ca7a0dd3ba82152124eaec045fd228d84bc79dad5b6634059ec2d4ec19036ca9",
    ),
    (
        "src/paper_radar/pi_supply/cleanup.py",
        "1ddbb2730d089ffd95cf867b2321f5f5883c030b23807b6d19a0413282de8170",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_delete.py",
        "927c157458db770b0f74a0cc8856d50fa9027fc2d6c8bd4f66c74f37e977e20e",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_execute.py",
        "c5a26ecd0e5646aa99f12add02f4e7a36447511a539a25ea82799c8e815355f6",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_history.py",
        "302e864f0c51a8d343282f1ac566995e007aab6cce0191fed1d239f9c057240e",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_models.py",
        "79d07bb9aea0a0aeb568f050eab1ef261d5db1aec6f44ed283d136f36bdbd392",
    ),
    (
        "src/paper_radar/pi_supply/cli.py",
        "40e012d487187a2b6828632df0f043dc69a9be84ab66a57744e1f851129cd246",
    ),
    (
        "src/paper_radar/pi_supply/errors.py",
        "be0cb07450ba8ddd01e534683e079357146261886e85e3402b99893010cd7754",
    ),
    (
        "src/paper_radar/pi_supply/execution.py",
        "17906a691ababa7127074bc3c05ea87a12713965975a18d51c51da92a362214d",
    ),
    (
        "src/paper_radar/pi_supply/export.py",
        "c54f8391c6f8c3761d40992aa5798747642cee56829dcbde473302bf6ea3136b",
    ),
    (
        "src/paper_radar/pi_supply/filesystem.py",
        "350548b02c318fd48561c635a3da270330a23e24f500c06f7886c1700b3abc56",
    ),
    (
        "src/paper_radar/pi_supply/materials.py",
        "51aca4864e1aadfed9b13dc0cf2577adb95816c4f1a460a6302f6aecb5566d8e",
    ),
    (
        "src/paper_radar/pi_supply/models.py",
        "3c9d16b75ec97f448e743d4dbccb5c1164021a1d13126f039040513f9fd07afd",
    ),
    (
        "src/paper_radar/pi_supply/protection.py",
        "515c62247f5bcb989b72a1c2a7a846747ffe5be4f77488adfc237492e9ee436b",
    ),
    (
        "src/paper_radar/pi_supply/repository.py",
        "8e989a1df579c0892957b8f5fa0f119cf3719874e7a88000a647a43a70ef5464",
    ),
    (
        "src/paper_radar/pi_supply/retention.py",
        "ef7d2b59419d15865be23903209666b242397b5c68bb10201266cb205c0f79e0",
    ),
    (
        "src/paper_radar/pi_supply/selection.py",
        "00f6ec83a2b0960b10d64130ae80f0b5a9536a7cecf079abf065e149231068e4",
    ),
    (
        "src/paper_radar/pi_supply/service.py",
        "e1d6d8641e334685f5371c62e78f1183100a263749bee2b449886ce008479155",
    ),
    (
        "src/paper_radar/pi_supply/source_policy.py",
        "075b43a8c4d6e1599ebc60458448ecd137f6d028d24be67665d0409e2a262d97",
    ),
    (
        "src/paper_radar/pi_supply/tables.py",
        "28128ae4e40986d804a6ef2b1eb862965b2e13f1282d81cb70acf24022003a29",
    ),
    (
        "src/paper_radar/pi_supply/transport.py",
        "cc15d6982ed610a0248a987af6f9faf94743226a71a9f2194224c2d98129c437",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a401_pi_supply.py",
        "056ee1f2d83aa14ccd6cb28fc2b6ba735244a2378697bea040050560ed60abd8",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a402_pi_rebuild_failures.py",
        "1ffc04c4498325773f773689beadd0b1568254cfcf6a2752760126aabbdd720e",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a403_pi_activation.py",
        "56c2a029b67c5868e5e5b92e79c54b14eabb8b88b1cf87d67fb794e080d0d2a9",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a404_pi_cleanup_plans.py",
        "75b091d3d071aded348fdb71ff7a4505bf87adcff900e38770c254d08f712470",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a405_pi_cleanup_execution.py",
        "2ed24cd0458ad34e2b6f1b681e2a1826c1ed41228d6223939fc4528306dc8eed",
    ),
    (
        "src/paper_radar/storage/database.py",
        "ed8aba07f31eb6019c6d656a9147c682d74073bbdf4d268cd488bdb79ff3b7b1",
    ),
    (
        "src/paper_radar/storage/schema.py",
        "291db5e419f3a5a7fd88afab7f369569d0b8e754fa36932210418c0938050a0f",
    ),
    (
        "src/paper_radar/backup/manifest.py",
        "10a68266985c32b289b16a7a87dfa6219d21c7b667fe31c6f68482048d4c024f",
    ),
    (
        "src/paper_radar/backup/files.py",
        "8bf4f05fea2085b1e6b25bb0ae426db2c13da47aa314dd695a1cd5c5259d36b8",
    ),
    (
        "src/paper_radar/backup/restore.py",
        "13d80b3ce3239dcc8159d02cc91ac50ac6abec1f526a8337b16fad8aba77b46f",
    ),
    (
        "src/paper_radar/cli.py",
        "c444c4e16c98e8615c2b5268f0f4288144c7aff3a3890f072bf503e66a55a524",
    ),
    (
        "scripts/a4_acceptance.py",
        "1fff915ac03183daa659281ad3119e2281bd1f052fe4946a3062d70d454caae2",
    ),
    (
        "scripts/a3_scope.py",
        "b62f0e614aceb71ae7e7cc9613ed0a839934f2250c834bf519ce4e3e91d8e063",
    ),
    (
        "scripts/a2_full_scope.py",
        "172cef8748964067cd30c7da359374b9a4a2fb00e14ba1d553abb9cf9e168ed4",
    ),
    (
        "scripts/a1_scope.py",
        "e71257263bed5859e4277c8b0ff399c4986c440e8212c8d1a636c559fcc7d428",
    ),
    (
        "scripts/a1_acceptance.py",
        "6d823619d4a139c5df7d19be39f7c5ec409af2a7d7d1864d757dcc7fa697b4df",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "2eb2aeec023f8d5b5c13dbe85ba69d6a1c04955e37f62c3a90c15a4724801448",
    ),
    (
        "scripts/a2_test_receipt.py",
        "9a5c2eda301e3c9975aac7ab0c07f9884b99c5eea2f45250a4dc7145340b9c2e",
    ),
    (
        "scripts/offline_evidence.py",
        "7c2585d4aec8416b496f6b2618e14a81a670b03806b10fc7fb3e48f3c7d08497",
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
        "24db737f730e4ca445e53ca66a547091ee6bb1a865ced53440f245e15b3bfc6a",
    ),
    (
        "tests/pi_supply_support.py",
        "083385f8ae08954ae8b02b454704d04700181a443a0878104ae7ad52ada6e479",
    ),
    (
        "tests/pi_supply_process_support.py",
        "9438a164f887442d31c32c4f6039346705c01a8f4111b7d8aba8e2ed189ac01c",
    ),
    (
        "tests/pi_cleanup_process_support.py",
        "dbaae6edc31b469566be19f125bcbdce02ff85c46af11926696f02c01c911fc1",
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
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
    (
        "tests/fixtures/pi_supply/manifest-vector.json",
        "cf6d3aa9f6a91b2fec4594bfdd2f69d4d4e52d809da47fa4842923c4447d8823",
    ),
    (
        "tests/fixtures/pi_supply/1.3.0/package.json",
        "efa2ca2695c003c92febb3bca40c5de5f94d43a8aa78e1ba88420b30156d5e21",
    ),
    (
        "tests/fixtures/pi_supply/1.3.0/package-lock.json",
        "65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719",
    ),
    (
        "tests/fixtures/pi_supply/1.3.0/release.json",
        "c4d719422b35fb65d839fe01e4850a1c19a074cf37f8d1d911f9706b4b22c756",
    ),
    (
        "tests/fixtures/verification_transcripts.json",
        "1ed48f8d4403d399ffa8fc65c620b02ffcc9750bf105615973e30573efcbdf91",
    ),
)
