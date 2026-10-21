"""#25 独立完整 A2 固定范围。修改清单须逐项审查。不在运行时重算期望。"""

# 保留既有导入入口; 回执格式词表归共享核对模块所有。
from scripts.verification_checks import RECEIPT_COUNTERS as RECEIPT_COUNTERS
from scripts.verification_checks import ReceiptCounter as ReceiptCounter

SCOPE = "a2_versioned_config_snapshots"
ISSUE = 25
FORMAT_VERSION = 2
MIGRATION_REVISION = "a405_pi_cleanup_execution"
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
        "df9e411c23bec0d5c17f4734cf693645c277041b3e5bb16723403c5da3c95f96",
    ),
    (
        "tests/test_verification_publication.py",
        "daddcf17b47a0ef946ea6d4a7faa1232252a85dad50a185c5d622e6aae4d5366",
    ),
    (
        "tests/test_verification_run.py",
        "a2a0dafaeab21e86cfbc8560fc550f5238832a87805f54ff8de41402e587d72a",
    ),
    (
        "tests/test_verification_compatibility.py",
        "17dab6cec5f3e02b1411e17a22957e1f9d5288cf11898fbc1aa686d3d1b60b87",
    ),
    (
        "tests/test_config_material_compatibility.py",
        "5774fbef77755da67fad42d1310a2a537ba8ad0f0a1fb19a8b200f290d5e7699",
    ),
    (
        "tests/test_a2_acceptance.py",
        "f2af0847115f44ec8ff73875a8a6a457dcc62cc6a0c59c8559600a9812501c76",
    ),
    (
        "tests/test_a2_full_acceptance.py",
        "bb8c4138b025c70fa9511222bb24247cb2ccda9f2bbc500e4d5bdc62a25d9635",
    ),
    (
        "tests/test_a2_full_entry.py",
        "8b7dde0250043219fb1a11a01954e0f556b275d28d6fe20f8297c30cd6dbeb9f",
    ),
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
        "9b70e25d85fa0d1368f8d46d912dc14ec059f499c93139d5c95fdd1c43edde20",
    ),
    (
        "tests/test_config_boundary.py",
        "fe62dda52501e9a7fa99ce6b4b87c9151e46009e7705b59c23fc0519477641ad",
    ),
    (
        "tests/test_config_cli.py",
        "23d07fffec126cdf8a0af7bd5f3ddbabc5f07a0ba3f1d32f7152594d0f0f6ad0",
    ),
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
        "e76a9b90effb5b516531c370b628dea5da9c238c05d3b787bbb6e1b2a3378035",
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
    (
        "tests/test_config_service.py",
        "ccd7cea316e16348e14bcea400d392568954d5377b5f6a8a5bc36a0c4cad2d98",
    ),
    (
        "tests/test_config_snapshot_architecture.py",
        "30b7f1779cc500793fb1920b21c2016e118c395df4d7e13504f49f4bf1e84e49",
    ),
    (
        "tests/test_config_snapshot_cli.py",
        "d12f1f17109d8695d189b7de8c89fece870a54fb60da42e1b3811d8432db3f37",
    ),
    (
        "tests/test_config_snapshot_queries.py",
        "69b042430c90b1245a366c333aa69fb384b792ac9eaf36e039e30315501c478c",
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
        "ab38e647e40cc03ff138fa7dbf1676f0ab5bb6758d7556d303f5053628344840",
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
        "b16a9dbf5dfb4e54a6231e3177353091ed60ab092ab33478343554df69b143d0",
    ),
    (
        "pyproject.toml",
        "bf36f1fcade0fcbfcf68164e042d826c369d68e0b5da2f5dfa287d05d12fc5b4",
    ),
    (
        "scripts/a1_acceptance.py",
        "6d823619d4a139c5df7d19be39f7c5ec409af2a7d7d1864d757dcc7fa697b4df",
    ),
    (
        "scripts/a1_scope.py",
        "e71257263bed5859e4277c8b0ff399c4986c440e8212c8d1a636c559fcc7d428",
    ),
    (
        "scripts/a2_acceptance.py",
        "0843f426d5d59f9d53d718cd7962cee769d0308eda47138d79f0766f43e01c0b",
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
        "scripts/check-offline",
        "b08e2576e8968ea872a3dc44be4562adfb04cb7f99abe372a75469bbe6899cac",
    ),
    (
        "scripts/offline_evidence.py",
        "7c2585d4aec8416b496f6b2618e14a81a670b03806b10fc7fb3e48f3c7d08497",
    ),
    (
        "src/paper_radar/cli.py",
        "f3157590452d21827f3b9087a6861610dafba7f54259b39faff46a6109b8ba97",
    ),
    (
        "src/paper_radar/config/__init__.py",
        "e8e1844c436c97d48bfca7341cfc855502917767bc8da9e6924c3c12d0b9e4f1",
    ),
    (
        "src/paper_radar/config/adapter_loading.py",
        "ca79d39630e78e81fea0ce8940be91e71ee809f8b5b73aafc14986283f8c94a7",
    ),
    (
        "src/paper_radar/config/adapters.py",
        "09eba6119e74e25d50e493281d00c4ec978ce4e5e874bed7731d1822d92f1c3a",
    ),
    (
        "src/paper_radar/config/cli.py",
        "69f06e69b312af4c4d3ab07652789e20e17bf0d07ee73351ad0d61c2b6872234",
    ),
    (
        "src/paper_radar/config/compile.py",
        "61d2537d0066dd8ee0ab1cd7aba0a2be858f69627feae420fbe0c18e801b30ee",
    ),
    (
        "src/paper_radar/config/diff.py",
        "920553c48bc661893a6b3a3c23c0df0e051888f6161c010f98dced9d1664da30",
    ),
    (
        "src/paper_radar/config/errors.py",
        "3c5bed81535d7d80ff63e4dc1bdf5ea7c1a51795da1db1a7696ab63ecd5a3503",
    ),
    (
        "src/paper_radar/config/escalation.py",
        "086813af87547c24fce5b2940e6fb773b276a63f7ac880637311e3b24443d24d",
    ),
    (
        "src/paper_radar/config/extraction.py",
        "5e40614630817b84fc66aeed221cf65b0aee58012fe7e09148cc1f635bc36c4e",
    ),
    (
        "src/paper_radar/config/extraction_models.py",
        "a25c95e28eef976d63827959e87da3c09bd1124383bb05b298cb114156768c6b",
    ),
    (
        "src/paper_radar/config/extraction_policy.py",
        "5598e53bae6e90eeec8bbf5354013b3f8ae0e3291ab87cabef7310170fab0683",
    ),
    (
        "src/paper_radar/config/extraction_toolchain.py",
        "4f2ae67b03b4ed9d82aba434ca9e30de382804bd73e61217eb8b1559c1f97107",
    ),
    (
        "src/paper_radar/config/identity.py",
        "ed02a7920df6c7967c034fe06da3f0ee92e172163ba61fa6c2115db562d99a0e",
    ),
    (
        "src/paper_radar/config/journals.py",
        "8eeb3287a83bd0cfc8c7e7cd64b67b39cbf82b06fbfbd613cb4208f46b65060a",
    ),
    (
        "src/paper_radar/config/material_names.py",
        "3b9d6d1317ceb2fcaf6f4a27a03a17a1489856009e18a853c7fa08c5204cc959",
    ),
    (
        "src/paper_radar/config/projections.py",
        "be8dcbffc2b1535f9838f90389548c0fa8503a53917a078ad54bb323dad1e63a",
    ),
    (
        "src/paper_radar/config/read.py",
        "f6f3ae3d508ae3d7ecfeb34b22ca47d51990cb123f7047f9474d2487f0a15ae0",
    ),
    (
        "src/paper_radar/config/schema.py",
        "31d98d427c1c14922f08d455324a87bd1674749442d80edc4efdd94e29a6417c",
    ),
    (
        "src/paper_radar/config/material_assembly.py",
        "42223faf33b7e05519164909cfe111639d8f7d8dfe0c2bf26252da7f20f9d894",
    ),
    (
        "src/paper_radar/config/service.py",
        "c9b1e320b42fd840ff091829bcccf8e62e413f006899e6618bd57417e23b1791",
    ),
    (
        "src/paper_radar/config/snapshot_cli.py",
        "b6afba96f094800598419763ef8688bebbe59fd5125dd623e27b404169d19420",
    ),
    (
        "src/paper_radar/config/snapshot_queries.py",
        "6464b7693dfe69530eebf64db78849889481cd04c8e2f88c5d8838f0347de9e3",
    ),
    (
        "src/paper_radar/config/snapshot_summary.py",
        "a882ac057edcfded0b31fcb4c06a376590cdbb5e77c7bd058b22e81312b0b379",
    ),
    (
        "src/paper_radar/config/topics.py",
        "f69f0d0a87f8855ca3db9290c5602f40d34a6189b70cc6b63716626fca6a247a",
    ),
    (
        "src/paper_radar/config/yaml_loader.py",
        "5c5c88473481ba27a71dd4512565e04965fc46a14e23947b953b71a7bdaee1b8",
    ),
    (
        "src/paper_radar/storage/__init__.py",
        "52dd2406b588ddb72767d4621f5bddc12d8b68425e049b562574ca9c1789b236",
    ),
    (
        "src/paper_radar/storage/database.py",
        "ed8aba07f31eb6019c6d656a9147c682d74073bbdf4d268cd488bdb79ff3b7b1",
    ),
    (
        "src/paper_radar/storage/errors.py",
        "a8c859bb0d8a415599887d380218a46490c6e10afa9910c0360a4dda037db19f",
    ),
    (
        "src/paper_radar/storage/migrations/env.py",
        "f22dfaeade1105d7eb46dda731916406fe521051ec0a76b7eeb1e915d42ffd27",
    ),
    (
        "src/paper_radar/storage/migrations/versions/a201_profile_snapshot.py",
        "a19059f3143dd9d05e550bfd77f7d89f75bc43a23636ba375d4ac7d4ea2c3039",
    ),
    (
        "src/paper_radar/storage/records.py",
        "f1e5e7d9ca146fc8439ed8966d6bb3576e838ed7494d831772131731601094ca",
    ),
    (
        "src/paper_radar/storage/repository.py",
        "91a48152f1f2fdd840471f81c6db13ca87dc533a8ce4fa03f5b396b08019f5bf",
    ),
    (
        "src/paper_radar/storage/schema.py",
        "291db5e419f3a5a7fd88afab7f369569d0b8e754fa36932210418c0938050a0f",
    ),
    (
        "src/paper_radar/storage/snapshot_queries.py",
        "e394fb3bbc2e70e5bc92f4c539481e7d9660c026f60d709ef990763022f6acf1",
    ),
    (
        "tests/a2_full_support.py",
        "a15976749dc2ae52448d81ea794c2be1c2e0f53d4e2a09de20f9a9790c16dc38",
    ),
    (
        "tests/config_adapter_support.py",
        "04e71ec7c1a888844a7b55c3a1fe8d2dc3445866f08f3fa8f9481ff5b8a345ce",
    ),
    (
        "tests/config_extraction_support.py",
        "7798711c15be510330d405d7dcef6cc8110214498c6a50b04c454a3d696097d9",
    ),
    (
        "tests/config_journals_support.py",
        "639ea499a5d41e3f914c4c1ba36aeff9a6c3502204f0303fc9c76f893dd508bc",
    ),
    (
        "tests/config_projection_support.py",
        "1a3aa9a7ce2535a9a52c3fde9dc18cde964d1de8b89654e3d50e566aae79ef2a",
    ),
    (
        "tests/config_read_support.py",
        "e7f862a6959c56301046f18a57cb1524262c5e3e321797b6c00f04e5ff8fbf95",
    ),
    (
        "tests/config_reuse_support.py",
        "b9f576eb2a4ae3eead274caae1b0de6c63fea30cd65c2f1188c0ba41f450b91d",
    ),
    (
        "tests/config_snapshot_support.py",
        "454ac40c3cdcb4846ffce9e59dc3e9b075f21100aa9bf0ca952457b19690632b",
    ),
    (
        "tests/config_test_support.py",
        "1bdd4ec7d1c3a3c2274455cfe184ea5ee7d58971d65adc1ccd532a55c295e840",
    ),
    (
        "tests/config_transaction_process/sitecustomize.py",
        "29aa3205e4ad412ed9e0464ab3ac157b8f5a8af7cedda144d6733190668152f9",
    ),
    (
        "tests/config_transaction_support.py",
        "b34d3a45de0d377f3a78db7d6ceed20ec2616ad36eecdfb7257f0d20a80c1ef7",
    ),
    (
        "tests/deny_external_io/sitecustomize.py",
        "f0148752ef89a004fcf76048cbc1f070448152683921b6d9d7c452d102a2d48d",
    ),
    (
        "tests/deny_network/sitecustomize.py",
        "dfce12fb68aaefd9b19ec26f1ff6bfb10b3f726fdafe6f466ec031cc2acc3288",
    ),
)
REQUIRED_FIXTURE_FILES: tuple[tuple[str, str], ...] = (
    (
        "tests/fixtures/verification_transcripts.json",
        "e900793f0280d586be4a1ccd0a814553528dc5e2dd48b3eec5b307bad09450e3",
    ),
    (
        "tests/fixtures/config_material_compatibility.json",
        "01efe4124e80e671e4db621322da1a3c9e34253f0528015b640d529eff1dc8d5",
    ),
    (
        "examples/config/adapters/pi-v1.yaml",
        "4266c0a79632ffb9bfe17ae217893d25f80a0c498690698ebe3e80aaf31ab382",
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
        "e122228e4eb55c61b4dbf85349d75049c309223d83dad0b5edaa5b041c6cd93e",
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
        "bccacc1659b54a36d7da7159616cf276d21558d82036cc9918b46d50d14c38ed",
    ),
    (
        "examples/config/profiles/profile-v1.yaml",
        "f778f80c3e49eb455d90b1bf8a994a5b7ee5d782b2205297c366a4b0f5edb994",
    ),
    (
        "examples/config/prompts/pi-system-v1.md",
        "8b0188e425cc6a77059940a6a5c371f39f8eb28346ef504c5a3ec6b247747c25",
    ),
    (
        "examples/config/read/read-v1.yaml",
        "ff267cfa3280e469b205859a2408c042c4ca7243553c1427971e6ad0d624813d",
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
        "5efa0aec0e41329fe8736dcd533706309fd9c3717aeac14ddbf55d05cce0ed0b",
    ),
    (
        "examples/contracts/screening/boundary/v1/schema.json",
        "9fd5127a8081fb30f62f2b436a4b6067d1b0ae16fea8d4f190c36874ef8805a7",
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
        "674def579de57a15dc71d5a66af1c69725641484b0c79f1c20c2c4b1abfce1fb",
    ),
    (
        "examples/prompts/screening/boundary-v1.md",
        "7d116290291efcff745119919e6d5f827e2fbc38e20d0f93ac974b7530a33d1c",
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
