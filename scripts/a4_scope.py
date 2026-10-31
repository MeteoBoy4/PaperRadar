"""A4 固定审查范围;预期在开发时逐项登记,运行期间只核对。"""

from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a4_pi_supply_lifecycle"
ISSUE = 45
PARENT_ISSUE = 36
FORMAT_VERSION = 1
SUFFIX = ".a4.json"
MIGRATION_REVISION = "feed06_language_provenance"
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
        "3681d91c936e3a56f1c98b47e228a127102dbf13119a597de675db1d2969a4ad",
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
        "13c8c0e44fc1ed99c895646a213f4577871e88151ea3fb0bb0980b059ffb22f0",
    ),
    (
        "tests/test_pi_supply_cleanup_history.py",
        "a92978df3e34b386fb8632766831cfe3669fc67cbdc71631e0b752c64841338e",
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
        "c24d20749f95a2e1424c81a0239757d960f4920a9fee17ddf2b3d0c4e63c2632",
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
        "59cf8dabfc4bb74614d6e21e634947b7486ca07fa1e714c637873f814b428f73",
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
        "6ef2a010b5ef1922b7b43b34b91ff998323d0527116f6ad626ae0a5c8e5795f1",
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
        "4ed30b5a4bfee215a6c926f375a5cc865289157ed3a0d11a16fc652e2cd45278",
    ),
    ("tests/test_a2_full_entry.py", SHARED_MATERIALS["tests/test_a2_full_entry.py"]),
    (
        "tests/test_verification_run.py",
        SHARED_MATERIALS["tests/test_verification_run.py"],
    ),
    (
        "tests/test_verification_compatibility.py",
        SHARED_MATERIALS["tests/test_verification_compatibility.py"],
    ),
    (
        "tests/test_verification_integrity.py",
        SHARED_MATERIALS["tests/test_verification_integrity.py"],
    ),
)
REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "src/paper_radar/config/readiness.py",
        SHARED_MATERIALS["src/paper_radar/config/readiness.py"],
    ),
    (
        "src/paper_radar/pi_supply/__init__.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/__init__.py"],
    ),
    (
        "src/paper_radar/pi_supply/cleanup.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cleanup.py"],
    ),
    (
        "src/paper_radar/pi_supply/cleanup_delete.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cleanup_delete.py"],
    ),
    (
        "src/paper_radar/pi_supply/cleanup_execute.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cleanup_execute.py"],
    ),
    (
        "src/paper_radar/pi_supply/cleanup_history.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cleanup_history.py"],
    ),
    (
        "src/paper_radar/pi_supply/cleanup_models.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cleanup_models.py"],
    ),
    (
        "src/paper_radar/pi_supply/cli.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/cli.py"],
    ),
    (
        "src/paper_radar/pi_supply/errors.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/errors.py"],
    ),
    (
        "src/paper_radar/pi_supply/execution.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/execution.py"],
    ),
    (
        "src/paper_radar/pi_supply/export.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/export.py"],
    ),
    (
        "src/paper_radar/pi_supply/filesystem.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/filesystem.py"],
    ),
    (
        "src/paper_radar/pi_supply/materials.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/materials.py"],
    ),
    (
        "src/paper_radar/pi_supply/models.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/models.py"],
    ),
    (
        "src/paper_radar/pi_supply/protection.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/protection.py"],
    ),
    (
        "src/paper_radar/pi_supply/repository.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/repository.py"],
    ),
    (
        "src/paper_radar/pi_supply/retention.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/retention.py"],
    ),
    (
        "src/paper_radar/pi_supply/selection.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/selection.py"],
    ),
    (
        "src/paper_radar/pi_supply/service.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/service.py"],
    ),
    (
        "src/paper_radar/pi_supply/source_policy.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/source_policy.py"],
    ),
    (
        "src/paper_radar/pi_supply/tables.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/tables.py"],
    ),
    (
        "src/paper_radar/pi_supply/transport.py",
        SHARED_MATERIALS["src/paper_radar/pi_supply/transport.py"],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a401_pi_supply.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a401_pi_supply.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a402_pi_rebuild_failures.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a402_pi_rebuild_failures.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a403_pi_activation.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a403_pi_activation.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a404_pi_cleanup_plans.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a404_pi_cleanup_plans.py"
        ],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a405_pi_cleanup_execution.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a405_pi_cleanup_execution.py"
        ],
    ),
    (
        "src/paper_radar/storage/database.py",
        SHARED_MATERIALS["src/paper_radar/storage/database.py"],
    ),
    (
        "src/paper_radar/storage/schema.py",
        SHARED_MATERIALS["src/paper_radar/storage/schema.py"],
    ),
    (
        "src/paper_radar/backup/manifest.py",
        SHARED_MATERIALS["src/paper_radar/backup/manifest.py"],
    ),
    (
        "src/paper_radar/backup/files.py",
        SHARED_MATERIALS["src/paper_radar/backup/files.py"],
    ),
    (
        "src/paper_radar/backup/restore.py",
        SHARED_MATERIALS["src/paper_radar/backup/restore.py"],
    ),
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    ("scripts/a4_acceptance.py", SHARED_MATERIALS["scripts/a4_acceptance.py"]),
    ("scripts/a1_acceptance.py", SHARED_MATERIALS["scripts/a1_acceptance.py"]),
    (
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/offline_evidence.py", SHARED_MATERIALS["scripts/offline_evidence.py"]),
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
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
    ("tests/pi_supply_support.py", SHARED_MATERIALS["tests/pi_supply_support.py"]),
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
        SHARED_MATERIALS["tests/a4_acceptance_support.py"],
    ),
    (
        "tests/a3_acceptance_support.py",
        SHARED_MATERIALS["tests/a3_acceptance_support.py"],
    ),
    ("tests/a2_full_support.py", SHARED_MATERIALS["tests/a2_full_support.py"]),
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
        SHARED_MATERIALS["tests/fixtures/verification_transcripts.json"],
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = (
    "scripts/a3_scope.py",
    "scripts/a2_full_scope.py",
    "scripts/a1_scope.py",
)
