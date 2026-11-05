"""#25 独立完整 A2 固定范围。修改清单须逐项审查。不在运行时重算期望。"""

# 保留既有导入入口; 回执格式词表归共享核对模块所有。
from scripts.verification_checks import RECEIPT_COUNTERS as RECEIPT_COUNTERS
from scripts.verification_checks import ReceiptCounter as ReceiptCounter
from scripts.verification_scope_materials import SHARED_MATERIALS

SCOPE = "a2_versioned_config_snapshots"
ISSUE = 25
FORMAT_VERSION = 2
MIGRATION_REVISION = "body02_read_tasks"
REQUIRED_CHECKS = ("lockfile", "format", "lint", "types", "tests", "contracts")
REQUIRED_DEPENDENCIES = ("alembic", "SQLAlchemy", "PyYAML")
# 固定用例数量在独立收集核对后登记。回执必须同时证明收集和三阶段通过。
REQUIRED_TEST_CASE_COUNTS: dict[str, int] = {
    "tests/test_verification_checks.py": 6,
    "tests/test_verification_integrity.py": 18,
    "tests/test_verification_publication.py": 2,
    "tests/test_verification_run.py": 5,
    "tests/test_verification_compatibility.py": 9,
    "tests/test_a1_acceptance.py": 11,
    "tests/test_a2_acceptance.py": 3,
    "tests/test_a2_full_acceptance.py": 34,
    "tests/test_a2_full_entry.py": 7,
    "tests/test_a2_full_examples.py": 9,
    "tests/test_a2_test_receipt.py": 4,
    "tests/test_boundary_validation.py": 39,
    "tests/test_cli_help.py": 5,
    "tests/test_config_adapter_architecture.py": 1,
    "tests/test_config_adapter_cli.py": 13,
    "tests/test_config_adapter_persistence.py": 11,
    "tests/test_config_adapter_validation.py": 55,
    "tests/test_config_adapters.py": 10,
    "tests/test_config_architecture.py": 3,
    "tests/test_config_boundary.py": 16,
    "tests/test_config_cli.py": 9,
    "tests/test_config_diff_cli.py": 20,
    "tests/test_config_diff_review.py": 2,
    "tests/test_config_diff_service.py": 20,
    "tests/test_config_escalation.py": 41,
    "tests/test_config_extraction.py": 14,
    "tests/test_config_extraction_architecture.py": 1,
    "tests/test_config_extraction_cli.py": 14,
    "tests/test_config_extraction_persistence.py": 8,
    "tests/test_config_extraction_validation.py": 82,
    "tests/test_config_journals.py": 5,
    "tests/test_config_journals_architecture.py": 1,
    "tests/test_config_journals_cli.py": 16,
    "tests/test_config_journals_persistence.py": 10,
    "tests/test_config_journals_validation.py": 48,
    "tests/test_config_material_compatibility.py": 152,
    "tests/test_config_projection_adapters.py": 9,
    "tests/test_config_projection_algorithms.py": 11,
    "tests/test_config_projection_architecture.py": 1,
    "tests/test_config_projection_formats.py": 10,
    "tests/test_config_projections.py": 36,
    "tests/test_config_prompt_identity.py": 4,
    "tests/test_config_prompt_only.py": 3,
    "tests/test_config_read.py": 12,
    "tests/test_config_read_architecture.py": 1,
    "tests/test_config_read_cli.py": 18,
    "tests/test_config_read_persistence.py": 9,
    "tests/test_config_read_validation.py": 28,
    "tests/test_config_reuse.py": 15,
    "tests/test_config_reuse_cli.py": 16,
    "tests/test_config_reuse_persistence.py": 19,
    "tests/test_config_service.py": 13,
    "tests/test_config_snapshot_architecture.py": 1,
    "tests/test_config_snapshot_cli.py": 30,
    "tests/test_config_snapshot_queries.py": 24,
    "tests/test_config_transaction_cli.py": 11,
    "tests/test_config_transactions.py": 13,
    "tests/test_config_validation.py": 26,
    "tests/test_config_value.py": 63,
    "tests/test_config_value_cli.py": 8,
    "tests/test_contract_check.py": 32,
    "tests/test_contract_cli.py": 37,
    "tests/test_contract_export.py": 22,
    "tests/test_contract_schema.py": 11,
    "tests/test_decision_reason_validation.py": 63,
    "tests/test_offline_evidence.py": 11,
    "tests/test_reuse_assessment_validation.py": 49,
    "tests/test_screening_architecture.py": 3,
    "tests/test_value_prediction_validation.py": 88,
}
FORMAT_VERSIONS = {
    "snapshot": 1,
    "stage_projections": {
        "boundary": 1,
        "value": 1,
        "reuse": 1,
        "extraction": 1,
        "read": 1,
        "suggestion": 1,
    },
    "calibration_baseline": 1,
    "adapter_semantics": 1,
}
NOT_ASSESSED = (
    "stage_input_fingerprints",
    "business_facts",
    "blob_artifact_store",
    "tasks_and_shared_interfaces",
    "doctor",
    "structured_logs",
    "backup_and_recovery",
    "live_source_audit",
    "stage_b",
    "read_output_contract",
    "read_execution",
    "body_extraction_execution",
    "algorithm_execution",
    "pi_supply_and_rpc_execution",
    "calibration_workflow_and_gate",
    "automatic_fulltext_reading",
)

# 在首次范围审查完成后固定以下三类文件的字节身份。
REQUIRED_TEST_MODULES: tuple[tuple[str, str], ...] = (
    (
        "tests/test_verification_checks.py",
        "b12b3246d524e1c855b9f851a284e522e15587912be67d387c839ca814f098cc",
    ),
    (
        "tests/test_verification_integrity.py",
        SHARED_MATERIALS["tests/test_verification_integrity.py"],
    ),
    (
        "tests/test_verification_publication.py",
        "daddcf17b47a0ef946ea6d4a7faa1232252a85dad50a185c5d622e6aae4d5366",
    ),
    (
        "tests/test_verification_run.py",
        SHARED_MATERIALS["tests/test_verification_run.py"],
    ),
    (
        "tests/test_verification_compatibility.py",
        SHARED_MATERIALS["tests/test_verification_compatibility.py"],
    ),
    (
        "tests/test_config_material_compatibility.py",
        "5774fbef77755da67fad42d1310a2a537ba8ad0f0a1fb19a8b200f290d5e7699",
    ),
    ("tests/test_a2_acceptance.py", SHARED_MATERIALS["tests/test_a2_acceptance.py"]),
    (
        "tests/test_a2_full_acceptance.py",
        SHARED_MATERIALS["tests/test_a2_full_acceptance.py"],
    ),
    ("tests/test_a2_full_entry.py", SHARED_MATERIALS["tests/test_a2_full_entry.py"]),
    (
        "tests/test_a2_full_examples.py",
        "fd05db2bc50dddfed4de21f978e73c88fd02662f6a3adc38efe1abdd98a693fa",
    ),
    (
        "tests/test_a2_test_receipt.py",
        "cc0ea032dfda4b3c4ae3193c16238b7be0ea75ad0bc5dd309c6e45e95ec41563",
    ),
    (
        "tests/test_config_adapter_architecture.py",
        "b4bacec0a57ea15ddfc4017c76c3eacaf8d404a0375f1a015e3c05d20f239511",
    ),
    (
        "tests/test_config_adapter_cli.py",
        "7c32507c201b6874cc7506d4af274cc6a075e9b5f923d594769b397be0d76936",
    ),
    (
        "tests/test_config_adapter_persistence.py",
        "bb55d6cde40dd22fd2a61734be5b1085e208357b932d10f16b39721e3fdf86ca",
    ),
    (
        "tests/test_config_adapter_validation.py",
        "ad70b6c103a49b87e63fbf716eff6ffa35fdbb1f71fae8a7388717dbf7c959de",
    ),
    (
        "tests/test_config_adapters.py",
        "ce090f31cf2ed430b90f94fb8c267dc23cbee2b24b24051cf20eafdbb28e3ef5",
    ),
    (
        "tests/test_config_architecture.py",
        SHARED_MATERIALS["tests/test_config_architecture.py"],
    ),
    (
        "tests/test_config_boundary.py",
        "fe62dda52501e9a7fa99ce6b4b87c9151e46009e7705b59c23fc0519477641ad",
    ),
    ("tests/test_config_cli.py", SHARED_MATERIALS["tests/test_config_cli.py"]),
    (
        "tests/test_config_diff_cli.py",
        "58091553eb76b474146c0981b205e15f97456bdbd2b2392ac4f0b134f82ece97",
    ),
    (
        "tests/test_config_diff_review.py",
        "1adc8ef6c4348f0d33bebef46c0fd0448bd110947b56fb32c5845c00e727c732",
    ),
    (
        "tests/test_config_diff_service.py",
        "f045ee4ba1f7585eab6596df06142864f2cba9c2a579e7de2de2caa2c944c633",
    ),
    (
        "tests/test_config_escalation.py",
        "73a90d52c64ee87eaeea0a67370ee389b8e9917079206b149f765704f2042df2",
    ),
    (
        "tests/test_config_extraction.py",
        "27d9bdf568db655ee17159c91a6dcd45603c8ddea4d714db133f818749752dac",
    ),
    (
        "tests/test_config_extraction_architecture.py",
        "3feb3f2411386d13d0032c821a40fa1ce5fe8903ba866d26d6349a7ddbde1edc",
    ),
    (
        "tests/test_config_extraction_cli.py",
        "c6349abefbc54a60d42204864d358d00620fd936c8bf5c0c96df5049b24a6be1",
    ),
    (
        "tests/test_config_extraction_persistence.py",
        "b9ff387dcfd7794f5af95b9ece9c0e74fd4ff707966320656a018243d8064b35",
    ),
    (
        "tests/test_config_extraction_validation.py",
        "613071380962f23d802a90dc8a778246c6cb3b36665891f6a9ee43405aed3c9d",
    ),
    (
        "tests/test_config_journals.py",
        "d7efc522c8fd5abfe2ffbf0b81e0c0dd34edca592116da16c565ba4614d71647",
    ),
    (
        "tests/test_config_journals_architecture.py",
        "e097cf31d3cd7252192c3634567ac6cdabb5ee41b0c6fb20dd32f201773292b4",
    ),
    (
        "tests/test_config_journals_cli.py",
        "aeb6aee97a2811131186bc7bab177c4ed8064c42d36b2b978519d4169b1aad36",
    ),
    (
        "tests/test_config_journals_persistence.py",
        "4a091e7cfee73bedaa17fee7071930d1ff031d86aa72b1cc5908f3b4239438d6",
    ),
    (
        "tests/test_config_journals_validation.py",
        "e06dde2cd3700cf2c4a5c52256489fe5dabddb4e4fcdc10c4f1377855a51dfdb",
    ),
    (
        "tests/test_config_projection_adapters.py",
        "05abcbd609a304d7bb8d775506284886c010b4228620b784f4391d8fe086af28",
    ),
    (
        "tests/test_config_projection_algorithms.py",
        "e9a7beeb12a41456181c856cf17067b30502e8c09463823ae5079a2e5fd961a6",
    ),
    (
        "tests/test_config_projection_architecture.py",
        "af9d9ae23b628ed7cf793ce58839613e67b215f62044f9c48658345fbe39604a",
    ),
    (
        "tests/test_config_projection_formats.py",
        "2e5ac50b86287ed84e92892da530acc87599e2e0cf26501489147db02b00fad9",
    ),
    (
        "tests/test_config_projections.py",
        "a4889c4b7db94e499c17971821e2cb20742ca975d792b954c7500084601c43a5",
    ),
    (
        "tests/test_config_prompt_identity.py",
        "8346a0d530ee8553201de36e61ae6abbb13c443d6886e336192fd70014659153",
    ),
    (
        "tests/test_config_prompt_only.py",
        "66d28010fb6f21441028a443ae638158ebd8d565362e0b5338acfe917e76e252",
    ),
    (
        "tests/test_config_read.py",
        "df58e22949ffd3e184d65393b183583c991ae40122a7fb780e57ec12b1e98ea5",
    ),
    (
        "tests/test_config_read_architecture.py",
        "b443381b7c37f0bfafd17a872ae6a933a0ece28c4eb18b50f7a56d3c93320604",
    ),
    (
        "tests/test_config_read_cli.py",
        "b31fca8eccacce4f1621a707e4e18ccc2ec360625b9f75e75b1538051cc4f269",
    ),
    (
        "tests/test_config_read_persistence.py",
        "1c73a846f46219498870430530cf224dbed95fcd2f19686fc337c7f288f18657",
    ),
    (
        "tests/test_config_read_validation.py",
        "fa9a338476fca43b7b95ff369091064c784394eced54d7841989600234bb61ef",
    ),
    (
        "tests/test_config_reuse.py",
        "a93f0d99a590283414d4d65721d088f43f8acfccf24bf1cc8ab57a29cfb032a3",
    ),
    (
        "tests/test_config_reuse_cli.py",
        "b6a12db4a4ec455e6bed49abbac2293547fb4fc521eaa32caf8521fafeec06a0",
    ),
    (
        "tests/test_config_reuse_persistence.py",
        "6ec3bbebed0a4e4bb9c49d5a03bd222ee9b5abc8f053ae2c82a0ca8475fd0fb3",
    ),
    ("tests/test_config_service.py", SHARED_MATERIALS["tests/test_config_service.py"]),
    (
        "tests/test_config_snapshot_architecture.py",
        SHARED_MATERIALS["tests/test_config_snapshot_architecture.py"],
    ),
    (
        "tests/test_config_snapshot_cli.py",
        SHARED_MATERIALS["tests/test_config_snapshot_cli.py"],
    ),
    (
        "tests/test_config_snapshot_queries.py",
        SHARED_MATERIALS["tests/test_config_snapshot_queries.py"],
    ),
    (
        "tests/test_config_transaction_cli.py",
        "f87c4e017b6a07e5c4a90c75060de9fd2371d65dedbecbcf1f495ec2c97c2bc0",
    ),
    (
        "tests/test_config_transactions.py",
        "87e15ff71d768cb5d4754ed1eb7cf60fe669b8a36f16549e773fbac72960e504",
    ),
    (
        "tests/test_config_validation.py",
        SHARED_MATERIALS["tests/test_config_validation.py"],
    ),
    (
        "tests/test_config_value.py",
        "afef4611c27e3b7d2b9793faffbe6c377727132519579180b782e13083be3d3b",
    ),
    (
        "tests/test_config_value_cli.py",
        "1bf5e8ec287ec78ebe1aab9caae2143fabc2a2795e76c63f1c8a290086570cb4",
    ),
)
REQUIRED_SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    (
        "scripts/verification_groups.py",
        SHARED_MATERIALS["scripts/verification_groups.py"],
    ),
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
    ("pyproject.toml", SHARED_MATERIALS["pyproject.toml"]),
    ("scripts/a1_acceptance.py", SHARED_MATERIALS["scripts/a1_acceptance.py"]),
    ("scripts/a2_acceptance.py", SHARED_MATERIALS["scripts/a2_acceptance.py"]),
    (
        "scripts/a2_full_acceptance.py",
        SHARED_MATERIALS["scripts/a2_full_acceptance.py"],
    ),
    ("scripts/a2_test_receipt.py", SHARED_MATERIALS["scripts/a2_test_receipt.py"]),
    ("scripts/check-offline", SHARED_MATERIALS["scripts/check-offline"]),
    ("scripts/offline_evidence.py", SHARED_MATERIALS["scripts/offline_evidence.py"]),
    ("src/paper_radar/cli.py", SHARED_MATERIALS["src/paper_radar/cli.py"]),
    (
        "src/paper_radar/config/__init__.py",
        SHARED_MATERIALS["src/paper_radar/config/__init__.py"],
    ),
    (
        "src/paper_radar/config/adapter_loading.py",
        SHARED_MATERIALS["src/paper_radar/config/adapter_loading.py"],
    ),
    (
        "src/paper_radar/config/adapters.py",
        SHARED_MATERIALS["src/paper_radar/config/adapters.py"],
    ),
    (
        "src/paper_radar/config/cli.py",
        SHARED_MATERIALS["src/paper_radar/config/cli.py"],
    ),
    (
        "src/paper_radar/config/compile.py",
        SHARED_MATERIALS["src/paper_radar/config/compile.py"],
    ),
    (
        "src/paper_radar/config/diff.py",
        SHARED_MATERIALS["src/paper_radar/config/diff.py"],
    ),
    (
        "src/paper_radar/config/errors.py",
        SHARED_MATERIALS["src/paper_radar/config/errors.py"],
    ),
    (
        "src/paper_radar/config/escalation.py",
        SHARED_MATERIALS["src/paper_radar/config/escalation.py"],
    ),
    (
        "src/paper_radar/config/extraction.py",
        SHARED_MATERIALS["src/paper_radar/config/extraction.py"],
    ),
    (
        "src/paper_radar/config/extraction_models.py",
        SHARED_MATERIALS["src/paper_radar/config/extraction_models.py"],
    ),
    (
        "src/paper_radar/config/extraction_policy.py",
        SHARED_MATERIALS["src/paper_radar/config/extraction_policy.py"],
    ),
    (
        "src/paper_radar/config/extraction_toolchain.py",
        SHARED_MATERIALS["src/paper_radar/config/extraction_toolchain.py"],
    ),
    (
        "src/paper_radar/config/identity.py",
        SHARED_MATERIALS["src/paper_radar/config/identity.py"],
    ),
    (
        "src/paper_radar/config/journals.py",
        SHARED_MATERIALS["src/paper_radar/config/journals.py"],
    ),
    (
        "src/paper_radar/config/material_names.py",
        SHARED_MATERIALS["src/paper_radar/config/material_names.py"],
    ),
    (
        "src/paper_radar/config/projections.py",
        SHARED_MATERIALS["src/paper_radar/config/projections.py"],
    ),
    (
        "src/paper_radar/config/read.py",
        SHARED_MATERIALS["src/paper_radar/config/read.py"],
    ),
    (
        "src/paper_radar/config/schema.py",
        SHARED_MATERIALS["src/paper_radar/config/schema.py"],
    ),
    (
        "src/paper_radar/config/material_assembly.py",
        SHARED_MATERIALS["src/paper_radar/config/material_assembly.py"],
    ),
    (
        "src/paper_radar/config/service.py",
        SHARED_MATERIALS["src/paper_radar/config/service.py"],
    ),
    (
        "src/paper_radar/config/snapshot_cli.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_cli.py"],
    ),
    (
        "src/paper_radar/config/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_queries.py"],
    ),
    (
        "src/paper_radar/config/snapshot_summary.py",
        SHARED_MATERIALS["src/paper_radar/config/snapshot_summary.py"],
    ),
    (
        "src/paper_radar/config/topics.py",
        SHARED_MATERIALS["src/paper_radar/config/topics.py"],
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        SHARED_MATERIALS["src/paper_radar/config/yaml_loader.py"],
    ),
    (
        "src/paper_radar/storage/__init__.py",
        SHARED_MATERIALS["src/paper_radar/storage/__init__.py"],
    ),
    (
        "src/paper_radar/storage/database.py",
        SHARED_MATERIALS["src/paper_radar/storage/database.py"],
    ),
    (
        "src/paper_radar/storage/errors.py",
        SHARED_MATERIALS["src/paper_radar/storage/errors.py"],
    ),
    (
        "src/paper_radar/storage/migrations/env.py",
        SHARED_MATERIALS["src/paper_radar/storage/migrations/env.py"],
    ),
    (
        "src/paper_radar/storage/migrations/versions/a201_profile_snapshot.py",
        SHARED_MATERIALS[
            "src/paper_radar/storage/migrations/versions/a201_profile_snapshot.py"
        ],
    ),
    (
        "src/paper_radar/storage/records.py",
        SHARED_MATERIALS["src/paper_radar/storage/records.py"],
    ),
    (
        "src/paper_radar/storage/repository.py",
        SHARED_MATERIALS["src/paper_radar/storage/repository.py"],
    ),
    (
        "src/paper_radar/storage/schema.py",
        SHARED_MATERIALS["src/paper_radar/storage/schema.py"],
    ),
    (
        "src/paper_radar/storage/snapshot_queries.py",
        SHARED_MATERIALS["src/paper_radar/storage/snapshot_queries.py"],
    ),
    ("tests/a2_full_support.py", SHARED_MATERIALS["tests/a2_full_support.py"]),
    (
        "tests/config_adapter_support.py",
        SHARED_MATERIALS["tests/config_adapter_support.py"],
    ),
    (
        "tests/config_extraction_support.py",
        SHARED_MATERIALS["tests/config_extraction_support.py"],
    ),
    (
        "tests/config_journals_support.py",
        SHARED_MATERIALS["tests/config_journals_support.py"],
    ),
    (
        "tests/config_projection_support.py",
        SHARED_MATERIALS["tests/config_projection_support.py"],
    ),
    ("tests/config_read_support.py", SHARED_MATERIALS["tests/config_read_support.py"]),
    (
        "tests/config_reuse_support.py",
        SHARED_MATERIALS["tests/config_reuse_support.py"],
    ),
    (
        "tests/config_snapshot_support.py",
        SHARED_MATERIALS["tests/config_snapshot_support.py"],
    ),
    ("tests/config_test_support.py", SHARED_MATERIALS["tests/config_test_support.py"]),
    (
        "tests/config_transaction_process/sitecustomize.py",
        "29aa3205e4ad412ed9e0464ab3ac157b8f5a8af7cedda144d6733190668152f9",
    ),
    (
        "tests/config_transaction_support.py",
        SHARED_MATERIALS["tests/config_transaction_support.py"],
    ),
    (
        "tests/deny_external_io/sitecustomize.py",
        SHARED_MATERIALS["tests/deny_external_io/sitecustomize.py"],
    ),
    (
        "tests/deny_network/sitecustomize.py",
        SHARED_MATERIALS["tests/deny_network/sitecustomize.py"],
    ),
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
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
        "tests/fixtures/verification_transcripts.json",
        SHARED_MATERIALS["tests/fixtures/verification_transcripts.json"],
    ),
    (
        "tests/fixtures/config_material_compatibility.json",
        "01efe4124e80e671e4db621322da1a3c9e34253f0528015b640d529eff1dc8d5",
    ),
    (
        "examples/config/adapters/pi-v1.yaml",
        SHARED_MATERIALS["examples/config/adapters/pi-v1.yaml"],
    ),
    (
        "examples/config/extraction/extraction-example-v1.yaml",
        "57c593aa0ec4a92955ffb7a1920aaa48d436df7efd7c15c765a22a9950911ba0",
    ),
    (
        "examples/config/journals/journals-v1.yaml",
        "d0f7910dde9175bf063d306d1c7f109699521e9cdff3a5fec4d64f3ed7468708",
    ),
    (
        "examples/config/models/models-pi-v1.yaml",
        "bdc994d67a1a93495ee11a7a804be7f1be3dc13296d52571fd599faa6b8b787d",
    ),
    (
        "examples/config/models/models-read-v1.yaml",
        SHARED_MATERIALS["examples/config/models/models-read-v1.yaml"],
    ),
    (
        "examples/config/models/models-reuse-v1.yaml",
        "2a4a88f5355e1b58c36fde486418850571fbc2aff35dae53b8ac101e274256a9",
    ),
    (
        "examples/config/models/models-v1.yaml",
        "d0808af782529fbb1394cc782024acfbbd9cf83dc218b0da6874806bf8236055",
    ),
    (
        "examples/config/profiles/profile-example-v1.yaml",
        SHARED_MATERIALS["examples/config/profiles/profile-example-v1.yaml"],
    ),
    (
        "examples/config/profiles/profile-v1.yaml",
        "f778f80c3e49eb455d90b1bf8a994a5b7ee5d782b2205297c366a4b0f5edb994",
    ),
    (
        "examples/config/prompts/pi-system-v1.md",
        SHARED_MATERIALS["examples/config/prompts/pi-system-v1.md"],
    ),
    (
        "examples/config/read/read-v1.yaml",
        SHARED_MATERIALS["examples/config/read/read-v1.yaml"],
    ),
    (
        "examples/config/screening/reuse-escalation-v1.yaml",
        "c9859c5393415acabe70d16dc8812f900db627514df18a956d7d1a3e6f0bc421",
    ),
    (
        "examples/config/settings-boundary.yaml",
        "01be2d31e2908e32301b703a4fa162cc521a1d26b94437e293fe27b975974b22",
    ),
    (
        "examples/config/settings-extraction.yaml",
        "fb9677aae1486f9fd8fe62f58e4d143400b5573274eb79fd67b69ccbe8361323",
    ),
    (
        "examples/config/settings-journals.yaml",
        "be82bc9933563c43a61440d6dae051e4370eb271ab4125baa2683e033141beca",
    ),
    (
        "examples/config/settings-pi.yaml",
        "11d8bf76c38576b8182c774ba18a118450fc9b46b117b8445da6b5aa5fe84ddc",
    ),
    (
        "examples/config/settings-read.yaml",
        "e4117877f9ce7784a3768d5350acf0f98033c68ba838eebf62a4e1ad2a38bc74",
    ),
    (
        "examples/config/settings-reuse.yaml",
        "a02bdbba83fff4de94fe43892cbe8cc77c34657398bfc3dc7215fb8a1a7be3c5",
    ),
    (
        "examples/config/settings-value.yaml",
        "728d02bd9138eba08c035f723ba442ad643f6fc036ca4136076ebfac1c1ff31c",
    ),
    (
        "examples/config/settings.yaml",
        "33f036b729c53c5978dbdd46d4da01e63c7fbc57e8a9d57313cc7d437400c92f",
    ),
    (
        "examples/config/topics/topics-v1.yaml",
        "63001acaa9bfa16d747f0dffac11ece4e1f04d49b8da6608d309bf78ee842703",
    ),
    (
        "examples/contracts/screening/boundary/v1/manifest.json",
        SHARED_MATERIALS["examples/contracts/screening/boundary/v1/manifest.json"],
    ),
    (
        "examples/contracts/screening/boundary/v1/schema.json",
        SHARED_MATERIALS["examples/contracts/screening/boundary/v1/schema.json"],
    ),
    (
        "examples/contracts/screening/decision-reasons/v1/manifest.json",
        "cc6c1153775ba2f4bde07f2155cc201fd1ed77ce099af989043a209889e7c124",
    ),
    (
        "examples/contracts/screening/decision-reasons/v1/schema.json",
        "eabf88c7679433d52d8b8fa8a9cc3051c978a22ee528c785a187b146c555e4bc",
    ),
    (
        "examples/contracts/screening/reuse-assessment/v1/manifest.json",
        "c3f5547107ab90d00a7ea4a124f120ce9b97597ed93211968d93eee5f328eae8",
    ),
    (
        "examples/contracts/screening/reuse-assessment/v1/schema.json",
        "48c31d66163f7022cd3e7499619d2a97701b11cdc92d9f2e4dfe701cf3d980ff",
    ),
    (
        "examples/contracts/screening/value-prediction/v1/manifest.json",
        "5602c82d65eec2466eefa7a89a9ad974bb937a51dcc19f98c9bd198609997608",
    ),
    (
        "examples/contracts/screening/value-prediction/v1/schema.json",
        "5ba68a0499903e01e733872bbd1967e04ae8149089ae1559a5d0a2c6c2fa351e",
    ),
    (
        "examples/prompts/reading/v1.md",
        SHARED_MATERIALS["examples/prompts/reading/v1.md"],
    ),
    (
        "examples/prompts/screening/boundary-v1.md",
        SHARED_MATERIALS["examples/prompts/screening/boundary-v1.md"],
    ),
    (
        "examples/prompts/screening/reuse-v1.md",
        "b98802489a1d6f973fb8cc3aeef08b7633df0dec5719f3f2d7a9d0f22795560e",
    ),
    (
        "examples/prompts/screening/value-v1.md",
        "866ae799b84619f2fdb23c692d03412ea5eb051b2251d805b326b0039aa0c696",
    ),
)

# 显式证明引用; 不将 scope 登记数据作为逐文件哈希材料。
REQUIRED_SCOPE_REFERENCES = ("scripts/a1_scope.py",)
