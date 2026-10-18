"""A4 固定审查范围;预期在开发时逐项登记,运行期间只核对。"""

SCOPE = "a4_pi_supply_lifecycle"
ISSUE = 45
PARENT_ISSUE = 36
FORMAT_VERSION = 1
SUFFIX = ".a4.json"
MIGRATION_REVISION = "a405_pi_cleanup_execution"
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
    "tests/test_pi_supply_boundaries.py": 21,
    "tests/test_pi_supply_cleanup.py": 9,
    "tests/test_pi_supply_cleanup_cli.py": 3,
    "tests/test_pi_supply_cleanup_execute.py": 24,
    "tests/test_pi_supply_cleanup_execute_history.py": 6,
    "tests/test_pi_supply_cleanup_history.py": 11,
    "tests/test_pi_supply_cleanup_unreadable.py": 1,
    "tests/test_pi_supply_cli.py": 10,
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
    "tests/test_verification_integrity.py": 3,
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
        "c2c82d0797df60bf3bec9598157713972e6a20f48040503e5b7673651bb8a097",
    ),
    (
        "tests/test_pi_supply_boundaries.py",
        "73fb95885925b3d502595339c008f1341da3f427e1503b112a7f3ebe1e9a8dc2",
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
        "66b7c035a57a62040a5fc2d053a2750aa9eee5ec83fe7f0dac3d37403845fe1b",
    ),
    (
        "tests/test_pi_supply_cleanup_execute_history.py",
        "5878f38e7c624c5fcca26543b26fe8de7c80dba35a5adf5df4da86c83f7d3759",
    ),
    (
        "tests/test_pi_supply_cleanup_history.py",
        "3a8501edeb9677f87b4d0881a2c86e22191247d479752ee962a39d0935e5aef3",
    ),
    (
        "tests/test_pi_supply_cleanup_unreadable.py",
        "c847c710f33262af89d8221171aad538a4258de9b5ad2f87ccdb71664465e980",
    ),
    (
        "tests/test_pi_supply_cli.py",
        "2764d777eb2bcf7947efa3eeab0cd06a10b29e838eb45eed58a0bdf84d517aaa",
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
        "1e8e755cfdab90e3b27b8eb88a52badd51cea0c7dd9d4ee8a8505f061a5dcd7e",
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
        "099ae432f0aa6aacbf3e75222dc938d8508feae17b48b819947a55e046bdbe94",
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
        "c2c2f3830a18d7c3c814d305588328fe654baaeaae014bec8a277e1aee7a0dca",
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
        "cb173ecb8ed39cd0a101e5ef035e47e95b38745b766b53d22836ee9d7009d842",
    ),
    (
        "tests/test_a2_full_entry.py",
        "c5f07175de78046e0273fc372c1dcf2087a84ff00f6c57d3c750f58a301ea7e7",
    ),
    (
        "tests/test_verification_run.py",
        "5c8ac6d7acc6230e06dcebbbeea68d8cea9fbb024f37adaa5881eb2e56901e6b",
    ),
    (
        "tests/test_verification_compatibility.py",
        "524a0eb2274c2e06b5121a7f7b6b24405df4d8b98a1477d01faa2414cf5cb5b1",
    ),
    (
        "tests/test_verification_integrity.py",
        "ad4028d24f94e231884a96976ef80f397453ebb7796cb3a3ec536004a372da91",
    ),
)
REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/pi_supply/__init__.py",
        "ca7a0dd3ba82152124eaec045fd228d84bc79dad5b6634059ec2d4ec19036ca9",
    ),
    (
        "src/paper_radar/pi_supply/cleanup.py",
        "027fab941d5a2b858cb1aafe66fcf826408d9303d8ec94f3e9390f25eb8e7fb8",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_delete.py",
        "927c157458db770b0f74a0cc8856d50fa9027fc2d6c8bd4f66c74f37e977e20e",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_execute.py",
        "4205e391d87ec442abb9520fc4527981d7e55d2d98795f66ec89fc741a153aaf",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_history.py",
        "338188c97db0355f794bc91c18d5002ece95945db9461375f40aa5ebd7508f47",
    ),
    (
        "src/paper_radar/pi_supply/cleanup_models.py",
        "9ecd5026defa653798fc08d21e15249aa0a6d00260ef3647d921e734a4595387",
    ),
    (
        "src/paper_radar/pi_supply/cli.py",
        "a72915b625c96ba7ca5e8fc792d58aaad412a46ad5d53c53e3270472c077b8ad",
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
        "b8e7cfa20d0a18f4d3fcbbe51fd71541fa88d6f6b905c3f83a798fd430c7003b",
    ),
    (
        "src/paper_radar/pi_supply/models.py",
        "4f59921fea118597ff946fc77afa73cec5a722e4c77e8da53f1ffaa0807da960",
    ),
    (
        "src/paper_radar/pi_supply/protection.py",
        "3ed32eee2610343d10dfc482e48fa859af07781c590ce6d29c3e2d3240b8b570",
    ),
    (
        "src/paper_radar/pi_supply/repository.py",
        "45d7d0c878614539a4aa1995790d6bdce5072947947489dc008ab83457007b2e",
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
        "1d241e444c1c99b163d980cec8e270a3c04bd7b7dbe07a7dd77302af122a4749",
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
        "06b1b6b18418ec8b75ef6f3552d6d5a10fae109d728074bcedb7150303a7c387",
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
        "f3157590452d21827f3b9087a6861610dafba7f54259b39faff46a6109b8ba97",
    ),
    (
        "scripts/a4_acceptance.py",
        "c79d1c086dbab4b6f9953271be96cfd74acb29c53657260ea7cb87c0b1699321",
    ),
    (
        "scripts/a3_scope.py",
        "685467df35c8e05c824b842d20611ce31a942ecba38d134b8c05fff7f8cbe398",
    ),
    (
        "scripts/a2_full_scope.py",
        "cabe2e8a2a0f2b55f7715b762b6dd53447786784d5d84de9a58f3ace1be9fbbd",
    ),
    (
        "scripts/a1_scope.py",
        "419e26fe9a858b18ac46dfaf8f008af074ee689a923ff447c57be0a6fad84131",
    ),
    (
        "scripts/a1_acceptance.py",
        "6d823619d4a139c5df7d19be39f7c5ec409af2a7d7d1864d757dcc7fa697b4df",
    ),
    (
        "scripts/a2_full_acceptance.py",
        "00525c108e46d3295b64b14e0347e16358747f2bd011631fa5af30104b33fceb",
    ),
    (
        "scripts/a2_test_receipt.py",
        "60073cb71c01c949ee05dd54b7556f598f5f3e8a11a700e51f88e51ac5bb700a",
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
        "bbce8140a002e7fbf4a7cb8af13fb033bfd69b5c85790759e40a0b790ca4a1d2",
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
        "4770b56ccbf35f373ca3ba565a39605d1a494233a6aa005b65978c124d8349b4",
    ),
)
